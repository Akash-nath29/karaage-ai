"""Lesson generation (PRD F1, Workflow 4): materials → gap check / research → generate → validate → cite → save.

Every run saves a new immutable version (F7). On-demand enrichment (F1 mode 2) adds one section to the current
version instead of regenerating the whole lesson. LLM calls per lesson: research plan (+ verify if it searches),
the lesson itself (+ one repair if sections are missing), and a formula fix only if KaTeX rejects something.
"""

import hashlib
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import llm
from app.ai.llm import fence
from app.ai.prompts import lessons as prompts
from app.core.exceptions import AppError
from app.modules.courses.models import Course
from app.modules.documents.models import Document
from app.modules.jobs import repository as job_repository
from app.modules.jobs import service as jobs
from app.modules.jobs.models import Job
from app.modules.lessons import mathcheck
from app.modules.lessons.document import (
    LessonDocument,
    LlmLesson,
    LlmSection,
    absorb_inline_labels,
    missing_roles,
    to_document,
)
from app.modules.lessons.models import Lesson, LessonCitation, LessonVersion
from app.modules.rag import repository as rag_repository
from app.modules.rag import service as rag
from app.modules.rag.schemas import Passage, SearchRequest
from app.modules.research import service as research_service
from app.modules.research.models import ResearchJob, ResearchSource
from app.modules.syllabus import repository as syllabus_repository
from app.modules.syllabus.models import DocumentTopic, Topic, Unit
from app.orchestration import research_pipeline

MAX_MATERIAL, MAX_WEB, EVIDENCE_CHARS = 10, 6, 1500


@dataclass
class Evidence:
    label: str
    kind: str  # material | web
    text: str
    passage: Passage | None = None
    source: ResearchSource | None = None
    citation: dict[str, Any] = field(default_factory=dict)


class MathFix(BaseModel):
    index: int
    latex: str


class MathFixes(BaseModel):
    fixes: list[MathFix]


def run(db: Session, lesson_id: uuid.UUID, *, request: str | None = None, can_retry: bool) -> bool:
    """Generate (or, with `request`, enrich) one lesson. Returns True if the caller should retry later."""
    lesson = db.get(Lesson, lesson_id)
    job = job_repository.get(db, lesson.job_id) if lesson and lesson.job_id else None
    if lesson is None or job is None or lesson.status == "cancelled":
        return False

    def fail(message: str) -> None:
        jobs.fail(db, job, message)
        lesson.status, lesson.error = "failed", message
        db.commit()

    return jobs.guarded(db, job, lambda: _generate(db, job, lesson, request), fail, can_retry=can_retry)


# --- Evidence ---------------------------------------------------------------------------------------------------


def gather_material(db: Session, course: Course, topic: Topic, subtopics: list[str]) -> list[Passage]:
    """Pinned documents first (D12), then passages mapped to the topic, then retrieval. Syllabi excluded."""
    query = f"{topic.title}: {', '.join(subtopics)}"[:1000]
    found: dict[uuid.UUID, Passage] = {}
    pinned = list(db.scalars(select(DocumentTopic.document_id).where(DocumentTopic.topic_id == topic.id)))
    if pinned:
        for p in rag.search(db, course.workspace_id, SearchRequest(query=query, document_ids=pinned, top_k=4)):
            found.setdefault(p.chunk_id, p)
    for row in rag_repository.fetch(db, syllabus_repository.material_chunk_ids(db, topic.id, 8)):
        found.setdefault(row.id, Passage(chunk_id=row.id, score=0.0, **row._asdict()))
    for p in rag.search(db, course.workspace_id, SearchRequest(query=query, course_id=course.id, top_k=8)):
        found.setdefault(p.chunk_id, p)
    syllabi = set(db.scalars(select(Document.id).where(
        Document.id.in_({p.document_id for p in found.values()}), Document.kind == "syllabus")))
    return [p for p in found.values() if p.document_id not in syllabi][:MAX_MATERIAL]


def _research_if_needed(db: Session, job: Job, topic_id: uuid.UUID, warnings: list[str]) -> ResearchJob | None:
    """Reuse recent research; otherwise run it now, stopping after the gap check if materials suffice (E1)."""
    research = research_service.fresh_for_topic(db, topic_id)
    if research:
        return research
    latest = research_service.latest_for_topic(db, topic_id)
    if latest and latest.status in ("queued", "running") and jobs.is_active(db, latest.job_id):
        warnings.append("Web research for this topic was still running: written from your materials only.")
        return None
    jobs.event(db, job, "researching", "Checking your materials for gaps (searching the web only if needed)", 20)
    db.commit()
    research = research_service.create(db, topic_id)
    research_pipeline.run(db, research.id, can_retry=False, skip_search_if_sufficient=True)
    if research.status != "succeeded":
        warnings.append(f"Web research failed ({research.error}): written from your materials only.")
        return None
    return research


def label_evidence(
    material: list[Passage], web: list[ResearchSource], first_m: int = 1, first_w: int = 1
) -> list[Evidence]:
    evidence = []
    for i, p in enumerate(material, start=first_m):
        where = f", p. {p.page_start}" + (f"–{p.page_end}" if p.page_end != p.page_start else "") if p.page_start else ""
        evidence.append(Evidence(
            label=f"M{i}", kind="material", passage=p,
            text=f"{p.heading_path}\n{p.content}".strip()[:EVIDENCE_CHARS],
            citation={"chunk_id": p.chunk_id, "document_id": p.document_id, "filename": p.filename,
                      "page_start": p.page_start, "page_end": p.page_end, "heading_path": p.heading_path},
        ))
        evidence[-1].citation["where"] = where
    for i, s in enumerate(web, start=first_w):
        evidence.append(Evidence(
            label=f"W{i}", kind="web", source=s, text=" … ".join(s.passages)[:EVIDENCE_CHARS],
            citation={"research_source_id": s.id, "url": s.url, "title": s.title, "domain": s.domain},
        ))
    return evidence


def evidence_block(evidence: list[Evidence]) -> str:
    if not evidence:
        return "No evidence was found: write from general knowledge, with empty citations everywhere."
    blocks = []
    for e in evidence:
        if e.kind == "material":
            about = f'file="{e.citation["filename"]}{e.citation["where"]}"'
        else:
            about = f'site="{e.citation["domain"]}"'
        blocks.append(f'<source id="{e.label}" {about}>\n{fence(e.text)}\n</source>')
    return "Evidence:\n" + "\n".join(blocks)


# --- Generation ---------------------------------------------------------------------------------------------------


def _convert(llm_lesson: LlmLesson, topic_id: uuid.UUID, depth: str, labels: set[str]) -> tuple[LessonDocument | None, list[str]]:
    try:
        return to_document(llm_lesson, topic_id=topic_id, depth=depth, labels=labels)
    except ValidationError as e:
        return None, [f"invalid lesson: {e.errors()[0]['msg']}"]


def _fix_math(db: Session, doc: dict[str, Any], workspace_id: uuid.UUID, tally: list[tuple[int, int]]) -> list[str]:
    """KaTeX-check every expression; one repair call for the broken ones; whatever still fails shows as source."""
    expressions = list(dict.fromkeys(mathcheck.find_math(doc)))
    errors = mathcheck.check(expressions)
    if errors is None:
        return ["Math not checked: Node/KaTeX unavailable (npm install --prefix backend/tools)."]
    broken = [(i, tex, err) for i, ((tex, _), err) in enumerate(zip(expressions, errors, strict=True)) if err]
    if not broken:
        return []
    fixes, _ = llm.structured(
        db, schema=MathFixes, system=prompts.MATH_SYSTEM, prompt=prompts.math_prompt(broken),
        operation="lesson_math_fix", workspace_id=workspace_id, tally=tally,
    )
    proposed = {i: f.latex.strip().strip("$").strip() for f in fixes.fixes for i, _, _ in broken if f.index == i}
    candidates = [(i, proposed[i]) for i, _, _ in broken if proposed.get(i)]
    rechecked = mathcheck.check([(tex, expressions[i][1]) for i, tex in candidates]) or [None] * len(candidates)
    good = {i: tex for (i, tex), err in zip(candidates, rechecked, strict=True) if err is None}
    mathcheck.replace_math(doc, {expressions[i]: good.get(i) for i, _, _ in broken})
    failed = len(broken) - len(good)
    return [f"Repaired {len(good)} formula(s)"] + ([f"{failed} formula(s) shown as LaTeX source"] if failed else [])


def _generate(db: Session, job: Job, lesson: Lesson, request: str | None) -> None:
    topic = db.get(Topic, lesson.topic_id)
    if topic is None:
        raise AppError(422, "The topic was deleted.")
    unit, course = db.get(Unit, topic.unit_id), db.get(Course, topic.course_id)
    assert unit is not None and course is not None  # FKs
    subtopics = [t.title for t in syllabus_repository.topics(db, course.id) if t.parent_id == topic.id]
    path = f"{course.title} > {unit.title} > {topic.title}"
    current = _version(db, lesson.id, lesson.current_version) if lesson.current_version else None
    if request and current is None:
        raise AppError(409, "Generate the lesson before asking for more.")

    jobs.start(db, job, f"Extending “{topic.title}”" if request else f"Writing the lesson on “{topic.title}”")
    lesson.status, lesson.error = "generating", None
    db.commit()

    warnings: list[str] = []
    tally: list[tuple[int, int]] = []
    material = gather_material(db, course, topic, subtopics)
    jobs.event(db, job, "gathering", f"Found {len(material)} relevant passages in your materials", 10)
    db.commit()
    research = research_service.fresh_for_topic(db, topic.id) if request else _research_if_needed(db, job, topic.id, warnings)
    web: list[ResearchSource] = []
    if research and research.source_count:
        web = list(db.scalars(select(ResearchSource).where(ResearchSource.research_id == research.id)
                              .order_by(ResearchSource.quality.desc(), ResearchSource.relevance.desc()).limit(MAX_WEB)))

    jobs.event(db, job, "writing", f"Writing with {len(material)} material and {len(web)} web sources", 40)
    db.commit()
    if request:
        assert current is not None
        used = {c.label for c in _citations(db, current.id)}
        first = {k: 1 + max([int(lbl[1:]) for lbl in used if lbl[0] == k] or [0]) for k in "MW"}
        evidence = label_evidence(material, web, first["M"], first["W"])  # continue numbering: no label collisions
        labels = {e.label for e in evidence}
        outline = "\n".join(f"- {s['title']} ({s['role']})" for s in current.document["sections"])
        section, model = llm.structured(
            db, schema=LlmSection, system=prompts.ENRICH_SYSTEM, tier="smart", tally=tally,
            prompt=prompts.enrich_prompt(path=path, outline=outline, request=request, evidence=evidence_block(evidence)),
            operation="lesson_enrich", workspace_id=course.workspace_id,
        )
        section.role = "extension"
        wrapper = LlmLesson(title="x", estimated_minutes=5, learning_objectives=[], prerequisites=[], sections=[section])
        added, problems = _convert(wrapper, topic.id, lesson.depth, labels)
        warnings += problems
        if added is None:
            raise AppError(422, "Couldn't write a valid extension for that request. Try rephrasing it.")
        doc = dict(current.document)
        new_section = added.sections[0].model_dump(mode="json")
        new_section["id"] = f"s{len(doc['sections']) + 1}"
        doc["sections"] = [*doc["sections"], new_section]
        doc["estimated_minutes"] = min(240, doc["estimated_minutes"] + 5)
        kind, inherited = "enriched", _citations(db, current.id)
    else:
        evidence = label_evidence(material, web)
        labels = {e.label for e in evidence}

        def write(feedback: str = "") -> tuple[LessonDocument | None, list[str], str]:
            draft, model = llm.structured(
                db, schema=LlmLesson, system=prompts.SYSTEM, tier="smart", tally=tally,
                prompt=prompts.generate_prompt(path=path, subtopics=", ".join(subtopics), depth=lesson.depth,
                                               evidence=evidence_block(evidence), feedback=feedback),
                operation="lesson_generate", workspace_id=course.workspace_id,
            )
            document, problems = _convert(draft, topic.id, lesson.depth, labels)
            return document, problems, model

        document, problems, model = write()
        missing = missing_roles(document) if document else set()
        if document is None or missing:  # one bounded repair (§11.5)
            issues = ([f"missing required sections: {', '.join(sorted(missing))}"] if missing else []) + problems[:10]
            jobs.event(db, job, "repairing", "Fixing the lesson's structure", 60)
            db.commit()  # never hold uncommitted writes (and their row locks) across an LLM call
            document, problems, model = write(
                "Your previous attempt had problems. Fix them and return the complete lesson:\n- " + "\n- ".join(issues)
            )
            if document is None:
                raise AppError(422, f"The model didn't produce a valid lesson ({problems[0]}). Try regenerating.")
            if missing := missing_roles(document):
                warnings.append(f"Missing sections after repair: {', '.join(sorted(missing))}")
        warnings += problems
        doc, kind, inherited = document.model_dump(mode="json"), "generated", []

    jobs.event(db, job, "checking", "Checking formulas and citations", 85)
    db.commit()
    absorb_inline_labels(doc, labels | {c.label for c in inherited})
    warnings += _fix_math(db, doc, course.workspace_id, tally)
    final = LessonDocument.model_validate(doc)  # the stored document always matches the schema
    _save(db, lesson, final, kind, model, evidence, inherited, research, warnings, tally, request)
    blocks = sum(len(s.blocks) for s in final.sections)
    jobs.succeed(db, job, f"Version {lesson.current_version} ready: {len(final.sections)} sections, {blocks} blocks")
    db.commit()


def _version(db: Session, lesson_id: uuid.UUID, version: int) -> LessonVersion | None:
    return db.scalar(select(LessonVersion).where(LessonVersion.lesson_id == lesson_id, LessonVersion.version == version))


def _citations(db: Session, version_id: uuid.UUID) -> list[LessonCitation]:
    return list(db.scalars(select(LessonCitation).where(LessonCitation.version_id == version_id)))


def _save(
    db: Session, lesson: Lesson, document: LessonDocument, kind: str, model: str, evidence: list[Evidence],
    inherited: list[LessonCitation], research: ResearchJob | None, warnings: list[str],
    tally: list[tuple[int, int]], request: str | None,
) -> None:
    cited = {label for s in document.sections for b in s.blocks for label in b.citations}
    version = LessonVersion(
        lesson_id=lesson.id, version=lesson.current_version + 1, kind=kind,
        document=document.model_dump(mode="json"), model=model, prompt_version=prompts.PROMPT_VERSION,
        source_snapshot={
            "evidence": [{"label": e.label, "kind": e.kind,
                          "id": str(e.passage.chunk_id if e.passage else e.source.id if e.source else ""),
                          "sha256": hashlib.sha256(e.text.encode()).hexdigest()[:16]} for e in evidence],
            "research_id": str(research.id) if research else None,
            "request": request,
        },
        document_ids=sorted({e.passage.document_id for e in evidence if e.passage and e.label in cited}
                            | {c.document_id for c in inherited if c.document_id}),
        warnings=warnings,
        input_tokens=sum(i for i, _ in tally), output_tokens=sum(o for _, o in tally),
    )
    db.add(version)
    db.flush()
    for old in inherited:  # an enriched version keeps the citations of the sections it copied
        db.add(LessonCitation(**{c: getattr(old, c) for c in (
            "label", "kind", "chunk_id", "document_id", "filename", "page_start", "page_end", "heading_path",
            "research_source_id", "url", "title", "domain", "quote")}, version_id=version.id))
    for e in evidence:
        if e.label in cited:
            fields = {k: v for k, v in e.citation.items() if k != "where"}
            db.add(LessonCitation(version_id=version.id, label=e.label, kind=e.kind, quote=e.text, **fields))
    lesson.current_version, lesson.status, lesson.outdated_reason = version.version, "ready", None

