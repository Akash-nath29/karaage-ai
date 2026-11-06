"""Assessment AI work (PRD H3–H5): question extraction from papers, quiz building, rubric grading.

LLM calls: extraction, one per ~12k characters of paper; a quiz, one call (answer keys for bank questions that
lack them, plus the new questions it needs) or none when the bank has enough keyed questions; grading, one call
per attempt with written answers, at temperature 0 (R16).
"""

import logging
import random
import re
import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.ai import llm, providers, usage
from app.ai.llm import fence
from app.ai.prompts import assessments as prompts
from app.ai.providers.base import ProviderError
from app.core import storage
from app.core import permissions
from app.core.exceptions import AppError
from app.core.tokens import estimate_tokens
from app.modules.assessments import grading
from app.modules.assessments import service as assessments
from app.modules.assessments.models import (
    AttemptAnswer,
    Question,
    Quiz,
    QuizAttempt,
    QuizQuestion,
)
from app.modules.assessments.schemas import LlmGrades, LlmPaper, LlmQuizWork
from app.modules.courses.models import Course
from app.modules.documents import extraction
from app.modules.documents.models import Document
from app.modules.jobs import repository as job_repository
from app.modules.jobs import service as jobs
from app.modules.jobs.models import Job
from app.modules.rag import repository as rag_repository
from app.modules.rag.schemas import Passage
from app.modules.syllabus import mapping
from app.modules.syllabus import repository as syllabus_repository
from app.modules.syllabus.models import Topic
from app.orchestration.lesson_pipeline import evidence_block, label_evidence

log = logging.getLogger(__name__)
BATCH_CHARS, PASSAGES_PER_TOPIC, MAX_PASSAGES = 12_000, 2, 10


def _guard(db: Session, job: Job | None, work: Callable[[Job], None], on_fail: Callable[[str], None], can_retry: bool) -> bool:
    if job is None or job.status in jobs.TERMINAL:
        return False
    return jobs.guarded(db, job, lambda: work(job), on_fail, can_retry=can_retry)


# --- Extraction (H3) ----------------------------------------------------------------------------------------------


def run_extraction(db: Session, job_id: uuid.UUID, *, can_retry: bool) -> bool:
    job = job_repository.get(db, job_id)

    def fail(message: str) -> None:
        jobs.fail(db, job, message)  # type: ignore[arg-type]  # _guard checked it
        db.commit()

    return _guard(db, job, lambda j: _extract(db, j), fail, can_retry)


def batches(pages: list[tuple[int, str]]) -> list[list[tuple[int, str]]]:
    out: list[list[tuple[int, str]]] = [[]]
    for page in pages:
        if out[-1] and sum(len(t) for _, t in out[-1]) + len(page[1]) > BATCH_CHARS:
            out.append([])
        out[-1].append(page)
    return [b for b in out if b]


def _extract(db: Session, job: Job) -> None:
    document = db.get(Document, job.document_id) if job.document_id else None
    course = db.get(Course, document.course_id) if document and document.course_id else None
    if document is None or course is None:
        raise AppError(422, "The paper was deleted or isn't assigned to a course.")
    jobs.start(db, job, f"Reading the questions in {document.filename}")
    db.commit()

    pages = [(n, text) for n, text in extraction.page_texts(document.file_type, storage.get(document.storage_key)) if text.strip()]
    if not pages:
        raise AppError(422, "No text found in this document.")

    def progress(done: int, total: int, found: int) -> None:
        jobs.event(db, job, "extracting", f"Read {done} of {total} parts: {found} questions so far", 10 + 70 * done // total)
        db.commit()

    approved = {_key(t) for t in db.scalars(select(Question.text).where(
        Question.document_id == document.id, Question.status == "approved"))}
    clean, skipped = read_questions(db, course, pages, approved, progress)
    topics = _map_topics(db, course, [q["text"] for q in clean])
    db.execute(delete(Question).where(Question.document_id == document.id, Question.status == "draft",
                                      Question.source_kind == "extracted"))  # re-extraction replaces unreviewed drafts
    db.add_all(Question(
        workspace_id=course.workspace_id, course_id=course.id, topic_id=topic.id if topic else None,
        text=q["text"], type=q["type"], marks=q["marks"], difficulty=q["difficulty"], options=q["options"],
        source_kind="extracted", document_id=document.id, source_page=q["page"], source_label=q["label"], status="draft",
    ) for q, topic in zip(clean, topics, strict=True))
    mapped = sum(1 for t in topics if t)
    jobs.succeed(db, job, f"{len(clean)} questions ready for review, {mapped} matched to syllabus topics"
                          + (f" ({skipped} unreadable skipped)" if skipped else ""))
    db.commit()


def _key(text: str) -> str:
    return " ".join(re.findall(r"\w+", text.lower()))


def read_questions(
    db: Session, course: Course, pages: list[tuple[int, str]], known: set[str] = frozenset(),  # type: ignore[assignment]
    progress: Callable[[int, int, int], None] | None = None,
) -> tuple[list[dict[str, Any]], int]:
    """The LLM pass: cleaned, de-duplicated questions with label and page; returns them and how many were unusable.
    `known`: normalized texts to skip (questions already approved from this paper). Commits after each call (R23)."""
    found, parts = [], batches(pages)
    for i, batch in enumerate(parts, start=1):
        text = "\n".join(f'<document page="{n}">\n{fence(t)}\n</document>' for n, t in batch)
        paper, _ = llm.structured(
            db, schema=LlmPaper, system=prompts.EXTRACT_SYSTEM, operation="question_extract", workspace_id=course.workspace_id,
            prompt=prompts.extract_prompt(course=f"{course.title} {course.code}".strip(), pages=text),
        )
        found += [(q, {n for n, _ in batch}) for q in paper.questions]
        if progress:
            progress(i, len(parts), len(found))
        db.commit()
    clean, seen, skipped = [], set(known), 0
    for raw, batch_pages in found:
        question, problem = grading.normalize_question(raw.model_dump())
        if question is None or _key(question["text"]) in seen:
            skipped += problem is not None
            continue
        seen.add(_key(question["text"]))
        clean.append({**question, "label": raw.label.strip()[:50],
                      "page": raw.page if raw.page in batch_pages else min(batch_pages)})
    return clean, skipped


def _map_topics(db: Session, course: Course, texts: list[str]) -> list[Topic | None]:
    """Best-effort, like chunk mapping: without embeddings the questions stay unmapped for the reviewer."""
    if not texts or not syllabus_repository.topics(db, course.id):
        return [None] * len(texts)
    try:
        embedder = providers.get_embedder()
        vectors = embedder.embed(texts, "document")
        usage.record(db, workspace_id=course.workspace_id, provider=embedder.provider, model=embedder.model,
                     operation="embed_questions", input_tokens=sum(estimate_tokens(t) for t in texts))
        topics, matrix = mapping.topic_vectors(db, course)
        return mapping.best_topics(topics, matrix, vectors)  # same 0.6 threshold as passages (D22)
    except ProviderError as e:
        log.warning("question → topic mapping for course %s skipped: %s", course.id, e)
        return [None] * len(texts)


# --- Quiz building (H4) -------------------------------------------------------------------------------------------


def run_quiz(db: Session, quiz_id: uuid.UUID, *, can_retry: bool) -> bool:
    quiz = db.get(Quiz, quiz_id)
    job = job_repository.get(db, quiz.job_id) if quiz and quiz.job_id else None
    if quiz is None or quiz.status != "generating":
        return False

    def fail(message: str) -> None:
        jobs.fail(db, job, message)  # type: ignore[arg-type]
        quiz.status, quiz.error = "failed", message
        db.commit()

    return _guard(db, job, lambda j: _build_quiz(db, j, quiz), fail, can_retry)


def _usable(q: Question) -> bool:
    return q.answer is not None or q.type in grading.WRITTEN and bool(q.rubric)


def _build_quiz(db: Session, job: Job, quiz: Quiz) -> None:
    s = quiz.settings
    course = db.get(Course, quiz.course_id)
    assert course is not None  # FK
    topics = assessments.scope_topics(db, course.id, s)
    if not topics:
        raise AppError(409, "The quiz's topics no longer exist.")
    jobs.start(db, job, f"Building “{quiz.title}”")
    db.commit()

    query = select(Question).where(Question.course_id == course.id, Question.status == "approved",
                                   Question.topic_id.in_([t.id for t in topics]))
    if s.get("difficulty"):
        query = query.where(Question.difficulty == s["difficulty"])
    if s.get("marks"):
        query = query.where(Question.marks == s["marks"])
    if s.get("types"):
        query = query.where(Question.type.in_(s["types"]))
    pool = list(db.scalars(query))
    bank = random.sample(pool, min(len(pool), s["count"]))  # ponytail: uniform; prefer unseen/weak-topic questions later
    unkeyed = [q for q in bank if not _usable(q)]
    new_count = s["count"] - len(bank)
    new: list[Question] = []
    if unkeyed or new_count:
        jobs.event(db, job, "writing", f"{len(bank)} from your question bank; writing {new_count} new and "
                                       f"{len(unkeyed)} missing answer keys", 30)
        db.commit()
        new = _write(db, quiz, course, topics, unkeyed, new_count, bank)
    chosen = [q for q in bank if _usable(q)] + new
    if not chosen:
        raise AppError(422, "Couldn't write any valid questions for these filters. Try different ones.")
    db.add_all(QuizQuestion(quiz_id=quiz.id, question_id=q.id, position=i) for i, q in enumerate(chosen, start=1))
    quiz.status, quiz.error = "ready", None
    short = s["count"] - len(chosen)
    jobs.succeed(db, job, f"{len(chosen)} questions ready ({len(chosen) - len(new)} from your question bank)"
                          + (f"; {short} couldn't be written" if short else ""))
    db.commit()


def _write(
    db: Session, quiz: Quiz, course: Course, topics: list[Topic], unkeyed: list[Question], count: int, bank: list[Question]
) -> list[Question]:
    """One LLM call: keys for bank questions without them, and `count` new questions. Returns the new ones (added)."""
    s = quiz.settings
    units = {u.id: u.title for u in syllabus_repository.units(db, course.id)}
    topic_list = "\n".join(f"{i}: {units.get(t.unit_id, '')} > {t.title}" for i, t in enumerate(topics, start=1))
    keys_needed = "\n".join(
        f"{i}. [{q.type}, {q.marks} marks]" + (f" options: {' | '.join(f'{j}={o}' for j, o in enumerate(q.options))}" if q.options else "")
        + f" {q.text}" for i, q in enumerate(unkeyed, start=1))
    constraints = ", ".join(filter(None, [
        f"difficulty {s['difficulty']}" if s.get("difficulty") else "",
        f"{s['marks']} marks each" if s.get("marks") else "",
        f"types: {', '.join(s['types'])}" if s.get("types") else "a mix of types suited to the topics",
    ]))
    chunk_ids = [c for t in topics[:MAX_PASSAGES] for c in syllabus_repository.material_chunk_ids(db, t.id, PASSAGES_PER_TOPIC)]
    material = [Passage(chunk_id=r.id, score=0.0, **r._asdict()) for r in rag_repository.fetch(db, chunk_ids[:MAX_PASSAGES])]
    work, model = llm.structured(
        db, schema=LlmQuizWork, system=prompts.QUIZ_SYSTEM, operation="quiz_generate", workspace_id=course.workspace_id,
        prompt=prompts.quiz_prompt(topics=topic_list, keys_needed=keys_needed, count=count, constraints=constraints,
                                   evidence=evidence_block(label_evidence(material, [])),
                                   existing="\n".join(f"- {q.text[:300]}" for q in bank)),
    )
    for k in work.keys:
        if 1 <= k.index <= len(unkeyed):
            q = unkeyed[k.index - 1]
            answer, rubric, _ = grading.check_key(q.type, q.options, k.answer, [c.model_dump() for c in k.rubric], q.marks)
            if answer:
                q.answer, q.rubric, q.explanation = answer, rubric, k.explanation.strip() or q.explanation
    reviewed = permissions.role_of(db, quiz.user_id, quiz.workspace_id) in ("editor", "admin", "owner")
    new = []
    for raw in work.questions[:count]:
        clean, _ = grading.normalize_question(raw.model_dump())
        if clean is None or (s.get("types") and clean["type"] not in s["types"]):
            continue
        clean["marks"] = s.get("marks") or clean["marks"]
        clean["difficulty"] = s.get("difficulty") or clean["difficulty"]
        answer, rubric, problem = grading.check_key(clean["type"], clean["options"], raw.answer,
                                                    [c.model_dump() for c in raw.rubric], clean["marks"])
        if problem:
            continue
        topic = topics[raw.topic - 1] if 1 <= raw.topic <= len(topics) else topics[0] if len(topics) == 1 else None
        question = Question(workspace_id=course.workspace_id, course_id=course.id, topic_id=topic.id if topic else None,
                            answer=answer, rubric=rubric, explanation=raw.explanation.strip(), source_kind="generated",
                            status="approved" if reviewed else "draft", **clean)
        db.add(question)
        new.append(question)
    db.flush()
    log.info("quiz %s: %d keys, %d new questions from %s", quiz.id, len(work.keys), len(new), model)
    return new


# --- Rubric grading (H5) ------------------------------------------------------------------------------------------


def run_grading(db: Session, attempt_id: uuid.UUID, *, can_retry: bool) -> bool:
    attempt = db.get(QuizAttempt, attempt_id)
    job = job_repository.get(db, attempt.job_id) if attempt and attempt.job_id else None
    if attempt is None or attempt.status != "grading":
        return False

    def fail(message: str) -> None:
        jobs.fail(db, job, message)  # type: ignore[arg-type]
        attempt.status, attempt.error = "failed", message
        db.commit()

    return _guard(db, job, lambda j: _grade(db, j, attempt), fail, can_retry)


def _grade(db: Session, job: Job, attempt: QuizAttempt) -> None:
    quiz = db.get(Quiz, attempt.quiz_id)
    assert quiz is not None  # FK
    jobs.start(db, job, "Marking your written answers against their rubrics")
    db.commit()
    pending = list(db.execute(
        select(AttemptAnswer, Question).join(Question, Question.id == AttemptAnswer.question_id)
        .where(AttemptAnswer.attempt_id == attempt.id, AttemptAnswer.score.is_(None)).order_by(AttemptAnswer.position)))
    if pending:
        blocks = []
        for i, (a, q) in enumerate(pending, start=1):
            rubric = q.rubric or grading.default_rubric(q.marks)
            criteria = "; ".join(f"{c['criterion']} ({c['marks']})" for c in rubric)
            blocks.append(
                f"Answer {i}. Question ({q.marks} marks): {q.text}\n"
                f"Rubric: {criteria}\n"
                f"Reference answer: {q.answer or 'none: mark from the rubric and your own subject knowledge'}\n"
                f'<document id="A{i}">\n{fence(a.answer)}\n</document>'
            )
        grades, model = llm.structured(
            db, schema=LlmGrades, system=prompts.GRADE_SYSTEM, prompt=prompts.grade_prompt("\n\n".join(blocks)),
            operation="answer_grade", workspace_id=quiz.workspace_id, temperature=0,
        )
        by_index = {g.index: g for g in grades.grades}
        if missing := [i for i in range(1, len(pending) + 1) if i not in by_index]:
            raise ProviderError(f"the grader skipped answer(s) {', '.join(map(str, missing))}")
        for i, (a, q) in enumerate(pending, start=1):
            g, rubric = by_index[i], q.rubric or grading.default_rubric(q.marks)
            criteria = [{**c, "awarded": min(max(round(g.criteria[j].awarded * 2) / 2, 0), c["marks"]) if j < len(g.criteria) else 0}
                        for j, c in enumerate(rubric)]
            a.score, a.graded_by = sum(c["awarded"] for c in criteria), "ai"
            a.feedback = {"criteria": criteria, "correct_concepts": g.correct_concepts, "missing_concepts": g.missing_concepts,
                          "incorrect_statements": g.incorrect_statements, "suggestions": g.suggestions, "model": model,
                          "prompt_version": prompts.PROMPT_VERSION}
    assessments.finish_attempt(db, attempt)
    jobs.succeed(db, job, f"Graded: {attempt.score:g} of {attempt.max_score:g} (written answers are AI estimates)")
    db.commit()

