"""Tutor answers (PRD Module G, Workflow 5): context → evidence → streamed answer → citations → saved message.

Evidence: the student's materials (hybrid retrieval), the topic's recent research, and, only when the student asks
for it, one quick web search. The lesson outline is context, not evidence. One streamed LLM call per answer.
"""

import json
import logging
import re
import uuid
from collections.abc import Callable, Iterator
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import providers, usage
from app.ai.llm import UNTRUSTED
from app.ai.prompts import tutor as prompts
from app.core.exceptions import AppError
from app.core.tokens import estimate_tokens
from app.modules.courses.models import Course
from app.modules.lessons.models import Lesson, LessonVersion
from app.modules.rag import service as rag
from app.modules.rag.schemas import SearchRequest
from app.modules.research import service as research_service
from app.modules.research import tavily
from app.modules.research.models import ResearchSource
from app.modules.research.quality import classify
from app.modules.research.urls import dedupe_key, domain, safe_public_url
from app.modules.syllabus.models import Topic, Unit
from app.modules.tutor.models import TutorMessage, TutorSession
from app.modules.users.models import User
from app.modules.tutor.schemas import MessageOut
from app.orchestration.lesson_pipeline import Evidence, evidence_block, label_evidence
from app.orchestration.research_pipeline import keywords, select_passages

log = logging.getLogger(__name__)
MAX_MATERIAL, MAX_WEB, HISTORY, HISTORY_CHARS = 6, 4, 10, 2000
LABELS = re.compile(r"\[((?:[MW]\d+)(?:\s*,\s*[MW]\d+)*)\]")


def sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, default=str)}\n\n"


def resolve_citations(answer: str, known: set[str]) -> tuple[str, list[str]]:
    """Keep only labels that exist ("[M1, M2]" becomes "[M1][M2]"); returns the text and the labels used."""
    used: list[str] = []

    def keep(match: re.Match[str]) -> str:
        labels = [label.strip() for label in match.group(1).split(",") if label.strip() in known]
        used.extend(labels)
        return "".join(f"[{label}]" for label in labels)

    return LABELS.sub(keep, answer), list(dict.fromkeys(used))


def split_follow_ups(full: str) -> tuple[str, list[str]]:
    answer, _, tail = full.partition(prompts.FOLLOW_UPS)
    suggestions = [line.strip(" -*•\t").lstrip("0123456789.) ").strip() for line in tail.splitlines()]
    return answer.rstrip(" *\n"), [s for s in suggestions if s][:3]


# --- Context and evidence -----------------------------------------------------------------------------------------


def _context(db: Session, tutor: TutorSession) -> tuple[str, Topic | None]:
    course = db.get(Course, tutor.course_id) if tutor.course_id else None
    topic = db.get(Topic, tutor.topic_id) if tutor.topic_id else None
    unit = db.get(Unit, topic.unit_id) if topic else None
    lines = []
    student = db.get(User, tutor.user_id)
    if student:
        lines.append(f"Student: {student.display_name}. Answer in {student.preferred_language} unless they write in "
                     "another language." + (f" Level: {student.academic_level}." if student.academic_level else "")
                     + (f" Learning preferences: {student.learning_preferences[:500]}" if student.learning_preferences else ""))
    if course:
        lines.append(f"Course: {course.title}" + (f" ({course.code})" if course.code else ""))
    if topic and unit:
        lines.append(f"Current topic: {unit.title} > {topic.title}")
    lesson = db.get(Lesson, tutor.lesson_id) if tutor.lesson_id else None
    if lesson and lesson.current_version:
        version = db.scalar(select(LessonVersion).where(
            LessonVersion.lesson_id == lesson.id, LessonVersion.version == lesson.current_version))
        if version:
            outline = "; ".join(s["title"] for s in version.document["sections"])
            lines.append(f"The student is reading the {lesson.depth} lesson on this topic. Its sections: {outline}")
    return ("\n".join(lines) or "No course context: a general academic question."), topic


def _quick_search(db: Session, workspace_id: uuid.UUID, query: str) -> list[ResearchSource]:
    """One Tavily search for this answer, filtered like research (E2/E3/E6). Sources aren't stored: the
    message's citations keep the URL and quote."""
    results = tavily.search(query, 5)
    usage.record(db, workspace_id=workspace_id, provider="tavily", model="search-basic", operation="web_search", input_tokens=0)
    db.commit()
    terms, seen, sources = keywords(query), set(), []
    for r in sorted(results, key=lambda r: r.score, reverse=True):
        url = safe_public_url(r.url)
        if url is None or dedupe_key(url) in seen:
            continue
        seen.add(dedupe_key(url))
        host = domain(url)
        passages = (select_passages(r.content, terms, 2) if r.content else []) or [" ".join(r.snippet.split())[:1200]]
        source_type, quality = classify(host)
        sources.append(ResearchSource(url=url, title=r.title or host, domain=host, source_type=source_type,
                                      quality=quality, relevance=r.score, passages=passages))
    return sorted(sources, key=lambda s: 0.6 * s.quality + 0.4 * s.relevance, reverse=True)[:MAX_WEB]


def gather(db: Session, tutor: TutorSession, topic: Topic | None, query: str, web: bool) -> list[Evidence]:
    material = rag.search(db, tutor.workspace_id, SearchRequest(query=query, course_id=tutor.course_id, top_k=MAX_MATERIAL))
    sources: list[ResearchSource] = []
    research = research_service.fresh_for_topic(db, topic.id) if topic else None
    if research and research.source_count:
        sources = list(db.scalars(select(ResearchSource).where(ResearchSource.research_id == research.id)
                                  .order_by(ResearchSource.quality.desc(), ResearchSource.relevance.desc()).limit(MAX_WEB)))
    if web:
        sources += _quick_search(db, tutor.workspace_id, query)
    return label_evidence(material, sources)


def _history(db: Session, tutor_id: uuid.UUID, before: TutorMessage) -> list[tuple[str, str]]:
    rows = list(db.scalars(
        select(TutorMessage).where(TutorMessage.session_id == tutor_id, TutorMessage.id != before.id,
                                   TutorMessage.created_at <= before.created_at, TutorMessage.content != "")
        .order_by(TutorMessage.created_at.desc()).limit(HISTORY)))[::-1]
    turns: list[tuple[str, str]] = []
    for m in rows:  # merge same-role neighbours (a failed answer leaves two user turns in a row)
        if turns and turns[-1][0] == m.role:
            turns[-1] = (m.role, f"{turns[-1][1]}\n\n{m.content[:HISTORY_CHARS]}")
        else:
            turns.append((m.role, m.content[:HISTORY_CHARS]))
    while turns and turns[0][0] == "assistant":  # conversations start with the student
        turns.pop(0)
    return turns


# --- The answer stream --------------------------------------------------------------------------------------------


def answer(session_factory: Callable[[], Session], question_id: uuid.UUID, web: bool) -> Iterator[str]:
    """SSE events: status, token (answer text, follow-ups held back), then done (the saved message) or error.
    The answer is saved however the stream ends: complete, error (partial text kept), or interrupted when the
    client disconnects."""
    db = session_factory()
    full, model, evidence = "", None, []
    spent = (0, 0)
    try:
        question = db.get(TutorMessage, question_id)
        assert question is not None  # saved by service.add_question before the stream opened
        tutor = db.get(TutorSession, question.session_id)
        assert tutor is not None
        db.info["user_id"] = tutor.user_id  # usage is the student's (D30)
        mode = question.mode

        def save(status: str) -> TutorMessage:
            text, suggestions = split_follow_ups(full)
            labelled = {e.label: e for e in evidence}
            text, used = resolve_citations(text, set(labelled))
            message = TutorMessage(
                session_id=tutor.id, role="assistant", mode=mode, content=text, status=status,
                suggestions=suggestions if status == "complete" else [],
                citations=[_citation(labelled[label]) for label in used],
                model=model, prompt_version=prompts.PROMPT_VERSION, input_tokens=spent[0], output_tokens=spent[1],
            )
            db.add(message)
            if model:
                usage.record(db, workspace_id=tutor.workspace_id, provider=provider, model=model,
                             operation="tutor_answer", input_tokens=spent[0], output_tokens=spent[1])
            db.commit()
            return message

        error, provider = None, ""
        try:
            chat = providers.get_chat_model("fast")
            provider = chat.provider
            yield sse("status", {"message": "Searching your materials" + (" and the web" if web else "")})
            context, topic = _context(db, tutor)
            previous = _history(db, tutor.id, question)
            last_question = next((text for role, text in reversed(previous) if role == "user"), "")
            query = " ".join(filter(None, [topic.title if topic else "", last_question[:300], question.content]))[:1000]
            evidence = gather(db, tutor, topic, query, web)
            materials = sum(1 for e in evidence if e.kind == "material")
            yield sse("status", {"message": f"Answering with {materials} passages from your materials"
                                            + (f" and {len(evidence) - materials} web sources" if len(evidence) > materials else "")})
            system = prompts.system_prompt(mode, UNTRUSTED)
            turns = [*previous, ("user", prompts.turn(context=context, evidence=evidence_block(evidence), question=question.content))]
            spent = (estimate_tokens(system + "".join(t for _, t in turns)), 0)
            chunks, stream_usage = chat.stream_text(system, turns)
            model = stream_usage.model
            emitted = 0
            for chunk in chunks:
                full += chunk
                cut = full.find(prompts.FOLLOW_UPS)
                safe = cut if cut >= 0 else len(full) - len(prompts.FOLLOW_UPS) + 1  # hold back a partial marker
                if safe > emitted:
                    yield sse("token", {"text": full[emitted:safe]})
                    emitted = safe
            tail = full.partition(prompts.FOLLOW_UPS)[0][emitted:]
            if tail:
                yield sse("token", {"text": tail})
            spent = (stream_usage.input_tokens or spent[0], stream_usage.output_tokens or estimate_tokens(full))
            status = "complete"
        except GeneratorExit:
            # ponytail: runs wherever the closed generator is finalised (the event loop thread); one short write.
            spent = (spent[0], estimate_tokens(full))
            save("interrupted")
            raise
        except Exception as e:
            log.exception("tutor answer for %s failed", question_id)
            db.rollback()
            error = str(e) if isinstance(e, AppError) else f"The tutor couldn't answer: {type(e).__name__}: {e}"[:500]
            spent, status = (spent[0], estimate_tokens(full)), "error"
        message = save(status)
        if error:
            yield sse("error", {"detail": error})
        yield sse("done", {"message": MessageOut.model_validate(message).model_dump(mode="json")})
    finally:
        db.close()


def _citation(e: Evidence) -> dict[str, Any]:
    fields = {k: str(v) if isinstance(v, uuid.UUID) else v for k, v in e.citation.items() if k not in ("where", "research_source_id")}
    return {"label": e.label, "kind": e.kind, "quote": e.text[:600], **fields}
