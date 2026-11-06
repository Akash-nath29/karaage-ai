"""Web research for one topic (PRD E2): existing material → sufficiency + focused queries → search → safe-URL
filter, dedupe, quality → relevant passages → cross-checked claims → stored evidence.

Bounded (PRD E4): ≤ RESEARCH_MAX_QUERIES searches, ≤ RESEARCH_MAX_SOURCES kept, 2 LLM calls, no loops.
"""

import hashlib
import re
import uuid
from collections import Counter
from datetime import UTC, datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ai import llm, usage
from app.ai.llm import fence
from app.ai.prompts import research as prompts
from app.config import settings
from app.modules.courses.models import Course
from app.modules.documents.models import Document
from app.modules.jobs import repository as job_repository
from app.modules.jobs import service as jobs
from app.modules.jobs.models import Job
from app.modules.rag import service as rag
from app.modules.rag.schemas import Passage, SearchRequest
from app.modules.research import tavily
from app.modules.research.models import ResearchJob, ResearchSource
from app.modules.research.quality import AUTHORITATIVE, classify
from app.modules.research.urls import dedupe_key, domain, safe_public_url
from app.modules.syllabus import repository as syllabus_repository
from app.modules.syllabus.models import Topic, Unit

MAX_PAGE_CHARS = 30_000  # bounded extraction: only the start of very long pages is considered
PASSAGE_CHARS = 1200
MAX_PER_DOMAIN = 2  # source diversity
MATERIAL_PASSAGES = 6
STOPWORDS = set(
    "the and for with from that this into are its their what how when which using use used between about over "
    "under than then them they there these those such each other also only more most some any all can may will "
    "introduction basics basic concept concepts overview".split()
)


class Plan(BaseModel):
    covered: list[str]
    missing: list[str]
    sufficient: bool
    queries: list[str]


class ClaimCheck(BaseModel):
    claim: str
    supporting: list[str]
    contradicting: list[str]


class Verification(BaseModel):
    claims: list[ClaimCheck]


def keywords(*texts: str) -> set[str]:
    return {w for text in texts for w in re.findall(r"[a-z0-9][a-z0-9+#-]{2,}", text.lower())} - STOPWORDS


def select_passages(text: str, terms: set[str], k: int) -> list[str]:
    """The k windows (~PASSAGE_CHARS) of a page that mention the most topic terms, in page order."""
    paragraphs = [" ".join(p.split()) for p in re.split(r"\n\s*", text[:MAX_PAGE_CHARS])]
    windows, current = [], ""
    for p in (p for p in paragraphs if len(p) >= 40):
        if current and len(current) + len(p) > PASSAGE_CHARS:
            windows.append(current)
            current = ""
        current = f"{current} {p}".strip()
    if current:
        windows.append(current)

    def score(window: str) -> int:
        if len(re.findall(r"[.!?](?:\s|$)", window)) < 2:
            return 0  # menus, link lists and headers have topic words but no sentences
        words = Counter(re.findall(r"[a-z0-9][a-z0-9+#-]{2,}", window.lower()))
        return 3 * sum(1 for t in terms if words[t]) + min(sum(words[t] for t in terms), 20)

    ranked = sorted(range(len(windows)), key=lambda i: score(windows[i]), reverse=True)[:k]
    return [windows[i][:PASSAGE_CHARS] for i in sorted(ranked) if score(windows[i]) > 0]


def run(db: Session, research_id: uuid.UUID, *, can_retry: bool, skip_search_if_sufficient: bool = False) -> bool:
    """`skip_search_if_sufficient`: when lesson generation asks for evidence, stop after the gap check if the
    student's materials already cover the topic (PRD E1: research isn't automatic for every request)."""
    research = db.get(ResearchJob, research_id)
    job = job_repository.get(db, research.job_id) if research and research.job_id else None
    if research is None or job is None:
        return False

    def fail(message: str) -> None:
        jobs.fail(db, job, message)
        research.status, research.error, research.finished_at = "failed", message, datetime.now(UTC)
        db.commit()

    return jobs.guarded(
        db, job, lambda: _research(db, job, research, skip_search_if_sufficient), fail, can_retry=can_retry
    )


def _research(db: Session, job: Job, research: ResearchJob, skip_search_if_sufficient: bool = False) -> None:
    topic = db.get(Topic, research.topic_id)
    if topic is None:
        raise RuntimeError("topic deleted")
    unit, course = db.get(Unit, topic.unit_id), db.get(Course, topic.course_id)
    assert unit is not None and course is not None  # FKs
    subtopics = ", ".join(t.title for t in syllabus_repository.topics(db, course.id) if t.parent_id == topic.id)
    path = f"{course.title} > {unit.title} > {topic.title}"
    jobs.start(db, job, f"Researching “{topic.title}”")
    research.status = "running"
    db.commit()

    # 1. What the student's own materials already cover (E2 steps 2–4)
    # The syllabus says what to learn; it isn't evidence. Only notes, textbooks, papers count as material.
    found = rag.search(
        db,
        course.workspace_id,
        SearchRequest(query=f"{topic.title}: {subtopics}"[:1000], course_id=course.id, top_k=MATERIAL_PASSAGES * 2),
    )
    syllabus_docs = set(db.scalars(select(Document.id).where(
        Document.id.in_({p.document_id for p in found}), Document.kind == "syllabus")))
    material: list[Passage] = [p for p in found if p.document_id not in syllabus_docs][:MATERIAL_PASSAGES]
    jobs.event(db, job, "planning", f"Checking {len(material)} passages from your materials for gaps", 10)
    db.commit()
    materials_text = "\n\n".join(
        f"[{p.filename}, p. {p.page_start}] {p.content[:800]}" if p.page_start else f"[{p.filename}] {p.content[:800]}"
        for p in material
    )
    plan, model = llm.structured(
        db,
        schema=Plan,
        system=prompts.PLAN_SYSTEM,
        prompt=prompts.plan_prompt(path, subtopics, fence(materials_text), settings.research_max_queries),
        operation="research_plan",
        workspace_id=course.workspace_id,
    )
    queries = list(dict.fromkeys(" ".join(q.split()) for q in plan.queries if q.strip()))[: settings.research_max_queries]
    research.covered, research.missing = plan.covered[:20], plan.missing[:20]
    research.sufficient, research.queries = plan.sufficient, queries or [f"{topic.title} {course.title}"]
    research.model, research.prompt_version = model, prompts.PROMPT_VERSION
    db.commit()
    if skip_search_if_sufficient and plan.sufficient and material:
        research.queries, research.status, research.finished_at = [], "succeeded", datetime.now(UTC)
        jobs.succeed(db, job, "Your materials cover this topic: no web search needed")
        db.commit()
        return

    # 2. Search (E2 steps 5–7)
    results: list[tavily.WebResult] = []
    for i, query in enumerate(research.queries, start=1):
        usage.check_budget(db, course.workspace_id, searches=1)
        results += tavily.search(query, settings.research_results_per_query)
        usage.record(db, workspace_id=course.workspace_id, provider="tavily", model="search-basic",
                     operation="web_search", input_tokens=0)
        jobs.event(db, job, "searching", f"Search {i} of {len(research.queries)}: {query}", 10 + 40 * i // len(research.queries))
        db.commit()

    # 3. Safe URLs only, deduplicated, quality-scored, relevant passages (E2 steps 8–9, E3, E6)
    terms = keywords(topic.title, subtopics, " ".join(research.missing))
    seen_urls: set[str] = set()
    seen_text: set[str] = set()
    per_domain: Counter[str] = Counter()
    candidates: list[ResearchSource] = []
    for result in sorted(results, key=lambda r: r.score, reverse=True):
        url = safe_public_url(result.url)
        if url is None or dedupe_key(url) in seen_urls:
            continue
        host = domain(url)
        if per_domain[host] >= MAX_PER_DOMAIN:
            continue
        passages = select_passages(result.content, terms, settings.research_passages_per_source) if result.content else []
        passages = passages or [" ".join(result.snippet.split())[:PASSAGE_CHARS]]
        fingerprint = hashlib.sha256(passages[0].lower().encode()).hexdigest()
        if not passages[0] or fingerprint in seen_text:  # mirrors and syndicated copies
            continue
        seen_urls.add(dedupe_key(url))
        seen_text.add(fingerprint)
        per_domain[host] += 1
        source_type, quality = classify(host)
        candidates.append(ResearchSource(
            id=uuid.uuid4(), research_id=research.id, url=url, title=result.title or host, domain=host,
            source_type=source_type, quality=quality, relevance=round(result.score, 3),
            published_date=result.published_date, content_kind="page" if result.content else "snippet",
            passages=passages,
        ))
    sources = sorted(candidates, key=lambda s: 0.6 * s.quality + 0.4 * s.relevance, reverse=True)
    sources = sources[: settings.research_max_sources]
    jobs.event(db, job, "evaluating", f"Kept {len(sources)} of {len(results)} results after safety, duplicate and quality checks", 60)
    db.commit()

    # 4. Cross-check important claims (E2 step 10); citations must resolve to known ids (PRD rule 16)
    research.claims = _cross_check(db, path, sources, material, course.workspace_id) if sources else []
    for source in sources:
        sid = str(source.id)
        if any(sid in c["contradicting"] for c in research.claims):
            source.verification_status = "disputed"
        elif any(sid in c["sources"] and c["status"] == "verified" for c in research.claims):
            source.verification_status = "verified"
        else:
            source.verification_status = "unverified"
    db.add_all(sources)

    research.status, research.source_count, research.finished_at = "succeeded", len(sources), datetime.now(UTC)
    verified = sum(1 for c in research.claims if c["status"] == "verified")
    jobs.succeed(db, job, f"{len(sources)} sources, {verified} of {len(research.claims)} claims verified")
    db.commit()


def _cross_check(
    db: Session, path: str, sources: list[ResearchSource], material: list[Passage], workspace_id: uuid.UUID
) -> list[dict[str, object]]:
    web = {f"S{i}": s for i, s in enumerate(sources, start=1)}
    mine = {f"M{i}": p for i, p in enumerate(material, start=1)}
    blocks = [f'<source id="{label}" site="{s.domain}">\n{fence(" … ".join(s.passages))[:3000]}\n</source>'
              for label, s in web.items()]
    blocks += [f'<source id="{label}" file="{p.filename}">\n{fence(p.content)[:1500]}\n</source>' for label, p in mine.items()]
    checked, _ = llm.structured(
        db,
        schema=Verification,
        system=prompts.VERIFY_SYSTEM,
        prompt=prompts.verify_prompt(path, "\n".join(blocks)),
        operation="research_verify",
        workspace_id=workspace_id,
    )
    claims = []
    for item in checked.claims[:8]:
        supporting_web = [web[l] for l in dict.fromkeys(item.supporting) if l in web]
        supporting_mine = [mine[l] for l in dict.fromkeys(item.supporting) if l in mine]
        contradicting = [web[l] for l in dict.fromkeys(item.contradicting) if l in web]
        if not supporting_web and not supporting_mine:
            continue  # unknown or missing ids: never keep an uncited claim
        independent = len({s.domain for s in supporting_web}) + (1 if supporting_mine else 0)
        authoritative = any(s.quality >= AUTHORITATIVE for s in supporting_web) or bool(supporting_mine)
        status = "disputed" if contradicting else "verified" if independent >= 2 or authoritative else "unverified"
        claims.append({
            "claim": " ".join(item.claim.split())[:500],
            "status": status,
            "sources": [str(s.id) for s in supporting_web],
            "materials": [str(p.chunk_id) for p in supporting_mine],
            "contradicting": [str(s.id) for s in contradicting],
        })
    return claims
