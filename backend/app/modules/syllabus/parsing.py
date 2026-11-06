"""Syllabus parsing (PRD C2/C3): find the course in the document, extract units/topics/subtopics as a draft.

Two LLM calls at most. Long documents (a whole programme's curriculum) first get a page-outline pass to locate
this course; the extraction pass then reads only those pages.
"""

import uuid

from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.ai import llm
from app.ai.prompts import syllabus as prompts
from app.core import storage
from app.core.exceptions import AppError
from app.modules.courses.models import Course
from app.modules.documents import extraction
from app.modules.documents.models import Document
from app.modules.jobs import repository as job_repository
from app.modules.jobs import service as jobs
from app.modules.jobs.models import Job
from app.modules.syllabus import repository
from app.modules.syllabus.models import Syllabus
from app.modules.syllabus.schemas import SubtopicNode, SyllabusDraft, TopicNode, UnitNode

LOCATE_ABOVE_CHARS = 60_000  # ~15k tokens: shorter documents are read whole
OUTLINE_CHARS_PER_PAGE = 300
MAX_PAGES = 40  # a located range longer than this is cut (one course's syllabus is a few pages)
MAX_EXTRACT_CHARS = 150_000


class Location(BaseModel):
    found: bool
    start_page: int
    end_page: int


class LlmTopic(BaseModel):
    title: str
    subtopics: list[str]


class LlmUnit(BaseModel):
    title: str
    hours: int | None
    topics: list[LlmTopic]


class LlmSyllabus(BaseModel):
    found: bool
    subject_name: str
    subject_code: str
    units: list[LlmUnit]
    references: list[str]
    exam_structure: str


def course_label(course: Course) -> str:
    return f"{course.title} (code {course.code})" if course.code else course.title


def to_draft(extracted: LlmSyllabus) -> SyllabusDraft:
    """Drop empty titles, duplicate subtopics and runaway lists the LLM may produce."""

    def clean(text: str) -> str:
        return " ".join(text.split())[:300]

    units = []
    for unit in extracted.units[:50]:
        topics = []
        for topic in unit.topics[:80]:
            subtopics = list(dict.fromkeys(clean(s) for s in topic.subtopics if clean(s)))[:60]
            if clean(topic.title):
                topics.append(TopicNode(title=clean(topic.title), subtopics=[SubtopicNode(title=s) for s in subtopics]))
        if clean(unit.title) and topics:
            hours = unit.hours if unit.hours is not None and 0 <= unit.hours <= 500 else None
            units.append(UnitNode(title=clean(unit.title), hours=hours, topics=topics))
    return SyllabusDraft(
        units=units,
        subject_name=clean(extracted.subject_name),
        subject_code=clean(extracted.subject_code)[:100],
        exam_structure=extracted.exam_structure.strip()[:5000],
        references=[r.strip()[:1000] for r in extracted.references if r.strip()][:50],
    )


def run(db: Session, job_id: uuid.UUID, *, can_retry: bool) -> bool:
    """Process one parse job. Returns True if the caller should retry later."""
    job = job_repository.get(db, job_id)
    syllabus = repository.get_by_job(db, job_id) if job else None
    if job is None or syllabus is None:
        return False

    def fail(message: str) -> None:
        jobs.fail(db, job, message)
        syllabus.status, syllabus.error = "failed", message
        db.commit()

    return jobs.guarded(db, job, lambda: _parse(db, job, syllabus), fail, can_retry=can_retry)


def _parse(db: Session, job: Job, syllabus: Syllabus) -> None:
    course = db.get(Course, syllabus.course_id)
    document = db.get(Document, syllabus.document_id) if syllabus.document_id else None
    if course is None or document is None:
        raise AppError(422, "The syllabus document was deleted. Choose another document.")
    jobs.start(db, job, f"Reading {document.filename}")
    syllabus.status, syllabus.error = "parsing", None
    db.commit()

    pages = extraction.page_texts(document.file_type, storage.get(document.storage_key))
    label = course_label(course)
    start, end = 1, len(pages)
    if sum(len(text) for _, text in pages) > LOCATE_ABOVE_CHARS:
        jobs.event(db, job, "locating", f"Finding “{course.title}” in {len(pages)} pages", 20)
        db.commit()
        outline = "\n".join(f"[page {n}] {' '.join(text.split())[:OUTLINE_CHARS_PER_PAGE]}" for n, text in pages)
        location, _ = llm.structured(
            db,
            schema=Location,
            system=prompts.LOCATE_SYSTEM,
            prompt=prompts.locate_prompt(label, outline),
            operation="syllabus_locate",
            workspace_id=course.workspace_id,
        )
        db.commit()  # keep the usage row even if a later step fails
        if not location.found:
            raise AppError(422, f"Couldn't find a syllabus for “{course.title}” in {document.filename}. "
                                "Check the course title and code, or choose another document.")
        start = min(max(1, location.start_page), len(pages))
        # +1: the outline shows only each page's first lines, so the course may run onto the next page.
        end = min(max(start, location.end_page) + 1, len(pages), start + MAX_PAGES - 1)
        jobs.event(db, job, "locating", f"Found on pages {start}–{end}", 40)

    jobs.event(db, job, "extracting", "Extracting units and topics", 50)
    db.commit()
    text = "\n\n".join(f"[page {n}]\n{t}" for n, t in pages if start <= n <= end)[:MAX_EXTRACT_CHARS]
    extracted, model = llm.structured(
        db,
        schema=LlmSyllabus,
        system=prompts.EXTRACT_SYSTEM,
        prompt=prompts.extract_prompt(label, text),
        operation="syllabus_extract",
        workspace_id=course.workspace_id,
    )
    db.commit()
    draft = to_draft(extracted)
    if not extracted.found or not draft.units:
        raise AppError(422, f"Couldn't find units or topics for “{course.title}” in {document.filename}.")

    syllabus.draft = draft.model_dump(mode="json")
    syllabus.status, syllabus.page_start, syllabus.page_end = "draft", start, end
    syllabus.model, syllabus.prompt_version = model, prompts.PROMPT_VERSION
    topics = sum(len(u.topics) for u in draft.units)
    jobs.succeed(db, job, f"Draft ready: {len(draft.units)} units, {topics} topics. Review it, then confirm.")
    db.commit()
