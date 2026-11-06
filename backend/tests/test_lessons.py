import re
import shutil
import uuid
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.config import settings
from app.modules.lessons import mathcheck
from app.modules.lessons.diagrams import DiagramEdge, DiagramError, DiagramNode, to_mermaid
from app.modules.lessons.document import LlmLesson, absorb_inline_labels, missing_roles, to_document
from app.modules.research import tavily
from app.orchestration import lesson_pipeline
from tests.samples import FakeChat, make_docx, make_pdf
from tests.test_documents import upload, workspace
from tests.test_syllabus import parsed

KATEX = shutil.which("node") and (Path(mathcheck.TOOL).parent / "node_modules" / "katex").exists()
LLM_FIELDS = ["text", "title", "variant", "headers", "rows", "latex", "language", "code", "problem", "solution",
              "items", "diagram", "questions", "cards"]


def blk(type_: str, *citations: str, **fields: Any) -> dict[str, Any]:
    return {**dict.fromkeys(LLM_FIELDS), "type": type_, "citations": list(citations), **fields}


def section(role: str, title: str, *blocks: dict[str, Any]) -> dict[str, Any]:
    return {"role": role, "title": title, "blocks": list(blocks)}


def lesson_reply(*, roles: set[str] | None = None, latex: str = r"\frac{n(n-1)}{2}") -> dict[str, Any]:
    """A complete 'detailed' lesson, optionally keeping only some section roles."""
    sections = [
        section("introduction", "Why ACID matters", blk("paragraph", "M1", text="Transactions keep data correct [M1].")),
        section("concept", "The four properties",
                blk("concept", "M1", title="Atomicity", text="All or nothing."),
                blk("paragraph", "M9", text="Pairs of transactions: $" + latex + "$ orderings.")),  # M9 doesn't exist
        section("visual", "Transaction states", blk("diagram", title="States", diagram={
            "kind": "state",
            "nodes": [{"id": "a", "label": "Active", "details": []}, {"id": "c", "label": "Committed", "details": []}],
            "edges": [{"source": "a", "target": "Committed", "label": "commit", "cardinality": ""}]})),
        section("examples", "Bank transfer", blk("example", title="Transfer", problem="Move Rs 500.", solution="Debit then credit.")),
        section("definitions", "Terms", blk("concept", title="Durability", text="Survives crashes.")),
        section("comparison", "Isolation levels", blk("comparison", title="Levels",
                headers=["Aspect", "Read committed", "Serializable"], rows=[["Dirty reads", "No", "No"]])),
        section("common_mistakes", "Mistakes", blk("callout", variant="warning", text="Consistency ≠ isolation.")),
        section("quick_revision", "Revise", blk("summary", items=["A", "C", "I", "D"]), blk("formula", latex=latex, text="n items")),
        section("practice", "Check yourself", blk("quiz", questions=[
            {"question": "Which is all-or-nothing?", "options": ["Atomicity", "Durability"], "answer_index": 0, "explanation": "A."},
            {"question": "Bad index", "options": ["x", "y"], "answer_index": 5, "explanation": ""}]),
            blk("table")),  # table without headers → dropped
    ]
    return {"title": "ACID Properties", "estimated_minutes": 25, "learning_objectives": ["Explain ACID"],
            "prerequisites": ["Transactions"], "sections": [s for s in sections if roles is None or s["role"] in roles]}


# --- units --------------------------------------------------------------------------------------------------------


def test_diagrams_compile_and_escape() -> None:
    nodes = [DiagramNode(id="a", label='Say "hi"; #1 <= x'), DiagramNode(id="b", label="End"), DiagramNode(id="x", label=" ")]
    edges = [DiagramEdge(source="a", target="End", label="go"), DiagramEdge(source="a", target="ghost")]
    flow = to_mermaid("flowchart", nodes, edges)
    assert flow.splitlines() == ["flowchart TD", '  n0["Say #quot;hi#quot;#59; #35;1 #lt;= x"]', '  n1["End"]', '  n0 -->|"go"| n1']
    assert to_mermaid("concept_map", nodes[:2], []).startswith("flowchart LR\n  n0(")
    assert "s0 --> s1 : go" in to_mermaid("state", nodes, edges)
    assert "p0->>p1: go" in to_mermaid("sequence", nodes, edges)
    er = to_mermaid("er", [DiagramNode(id="s", label="Student", details=["int student_id PK", "full name"]),
                           DiagramNode(id="c", label="Course", details=[])],
                    [DiagramEdge(source="s", target="c", label="enrolls", cardinality="M:N")])
    assert "    int student_id PK" in er and "    string full_name" in er and 'Student }o--o{ Course : "enrolls"' in er
    cls = to_mermaid("class", [DiagramNode(id="a", label="Animal", details=["+eat()", "{bad}"]), DiagramNode(id="d", label="Dog")],
                     [DiagramEdge(source="d", target="a", label="is-a")])
    assert "class Animal {" in cls and "    +eat()" in cls and "    bad" in cls and "Dog --> Animal : is-a" in cls
    with pytest.raises(DiagramError):
        to_mermaid("flowchart", [DiagramNode(id="a", label="  ")], [])


def test_document_conversion_drops_invalid_and_reports() -> None:
    doc, warnings = to_document(LlmLesson.model_validate(lesson_reply()), topic_id=uuid.uuid4(), depth="detailed", labels={"M1", "M2"})
    roles = [s.role for s in doc.sections]
    assert roles == ["introduction", "concept", "visual", "examples", "definitions", "comparison", "common_mistakes", "quick_revision", "practice"]
    assert missing_roles(doc) == set()
    assert doc.sections[1].blocks[1].citations == []  # unknown M9 dropped
    assert any("unknown citation labels ['M9']" in w for w in warnings)
    assert any("dropped a table block" in w for w in warnings)
    quiz = doc.sections[-1].blocks[0]
    assert quiz.type == "quiz" and len(quiz.questions) == 1  # out-of-range answer dropped
    comparison = doc.sections[5].blocks[0]
    assert comparison.items == ["Read committed", "Serializable"] and comparison.rows[0].aspect == "Dirty reads"
    assert doc.sections[2].blocks[0].source.startswith("stateDiagram-v2")
    partial, _ = to_document(LlmLesson.model_validate(lesson_reply(roles={"introduction", "concept"})),
                             topic_id=uuid.uuid4(), depth="detailed", labels=set())
    assert "visual" in missing_roles(partial)


def test_inline_labels_move_into_citations() -> None:
    doc = {"sections": [{"blocks": [{"type": "paragraph", "markdown": "Fact one [M1]. Fact two [M2, W1]. Fake [M7].", "citations": []}]}]}
    absorb_inline_labels(doc, {"M1", "M2", "W1"})
    block = doc["sections"][0]["blocks"][0]
    assert block["citations"] == ["M1", "M2", "W1"]
    assert block["markdown"] == "Fact one. Fact two. Fake."


@pytest.mark.skipif(not KATEX, reason="Node + KaTeX (npm install --prefix backend/tools) not available")
def test_katex_validation_and_fallback() -> None:
    assert mathcheck.check([("x^2", False), ("\\frac{a}{", True), ("\\mathbb{R}", False)]) == [None, mathcheck.check([("\\frac{a}{", True)])[0], None]
    assert mathcheck.check([("\\frac{a}{", True)])[0].startswith("KaTeX parse error")
    doc = {"sections": [{"blocks": [
        {"type": "paragraph", "markdown": "Costs $5 and $10. Area $\\pi r^2$ and $\\frac{a}{$.", "citations": []},
        {"type": "formula", "latex": "\\frac{a}{", "explanation": "where $n$ counts", "citations": []}]}]}
    assert mathcheck.find_math(doc) == [("\\pi r^2", False), ("\\frac{a}{", False), ("\\frac{a}{", True), ("n", False)]
    mathcheck.replace_math(doc, {("\\frac{a}{", False): None, ("\\frac{a}{", True): None, ("\\pi r^2", False): "\\pi r^{2}"})
    para, formula = doc["sections"][0]["blocks"]
    assert para["markdown"] == "Costs $5 and $10. Area $\\pi r^{2}$ and `\\frac{a}{`."
    assert formula["type"] == "code" and formula["language"] == "latex"


# --- pipeline -----------------------------------------------------------------------------------------------------


def run_queued(db: Session, queue: list[tuple[uuid.UUID, str | None]]) -> None:
    while queue:
        lesson_id, request = queue.pop(0)
        lesson_pipeline.run(db, lesson_id, request=request, can_retry=False)


@pytest.fixture
def no_web(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(query: str, max_results: int) -> list:  # type: ignore[type-arg]
        raise AssertionError("web search should not run when materials suffice")

    monkeypatch.setattr(tavily, "search", fail)


@pytest.fixture
def course_with_notes(client: TestClient, chat: FakeChat, monkeypatch: pytest.MonkeyPatch) -> dict[str, str]:
    """Confirmed DBMS syllabus + notes mapped to topics. Returns ids; the confirm's batch is in lesson_queue."""
    monkeypatch.setattr(settings, "topic_match_threshold", 0.2)
    ws, cid, _ = parsed(client, chat)
    notes = make_pdf([("ACID", "ACID properties of a transaction: atomicity, consistency, isolation, durability. " * 20)])
    doc = upload(client, ws, notes, name="notes.pdf", kind="notes", course_id=cid).json()
    structure = client.post(f"/api/v1/courses/{cid}/syllabus/confirm").json()
    acid = next(t for u in structure["units"] for t in u["topics"] if t["title"] == "ACID Properties")
    chat.replies["Plan"] = {"covered": ["ACID"], "missing": [], "sufficient": True, "queries": ["unused"]}
    chat.replies["MathFixes"] = lambda prompt: {"fixes": [  # fix every expression the prompt lists
        {"index": int(i), "latex": r"\frac{n(n-1)}{2}"} for i in re.findall(r"^(\d+)\. ", prompt, re.MULTILINE)]}
    return {"ws": ws, "course": cid, "doc": doc["id"], "topic": acid["id"]}


def reset(client: TestClient, ids: dict[str, str], queue: list) -> None:  # type: ignore[type-arg]
    """Cancel the batch the confirm queued, so a test generates exactly what it asks for."""
    client.post(f"/api/v1/courses/{ids['course']}/lessons/cancel")
    queue.clear()


def test_confirm_queues_batch_and_cancel(client: TestClient, chat: FakeChat, db: Session,
                                         lesson_queue: list, course_with_notes: dict[str, str]) -> None:
    cid = course_with_notes["course"]
    assert len(lesson_queue) == 3  # one per top-level topic, at the default depth
    assert client.post(f"/api/v1/courses/{cid}/lessons/cancel").json() == {"count": 3}
    run_queued(db, lesson_queue)  # cancelled tasks are skipped
    assert {l["status"] for l in client.get(f"/api/v1/topics/{course_with_notes['topic']}/lessons").json()} == {"cancelled"}
    assert client.post(f"/api/v1/courses/{cid}/lessons/generate").json() == {"count": 3}  # requeue the missing ones
    assert client.post(f"/api/v1/courses/{cid}/lessons/generate").json() == {"count": 0}  # already queued


def test_generate_lesson_with_citations(client: TestClient, chat: FakeChat, db: Session, lesson_queue: list,
                                        course_with_notes: dict[str, str], no_web: None) -> None:
    ids = course_with_notes
    reset(client, ids, lesson_queue)
    # unbalanced brace: KaTeX rejects it, so the MathFixes repair runs
    chat.replies["LlmLesson"] = lesson_reply(latex=r"\frac{n(n-1)}{2" if KATEX else r"\frac{n(n-1)}{2}")
    queued = client.post(f"/api/v1/topics/{ids['topic']}/lessons/generate", json={"depth": "detailed"}).json()
    assert queued["status"] == "queued" and queued["current_version"] == 0
    run_queued(db, lesson_queue)

    lesson = client.get(f"/api/v1/lessons/{queued['id']}").json()
    assert lesson["lesson"]["status"] == "ready" and lesson["lesson"]["current_version"] == 1
    assert (lesson["topic_title"], lesson["unit_title"]) == ("ACID Properties", "Transactions")
    doc = lesson["document"]
    assert doc["schema_version"] == "1.0" and doc["depth"] == "detailed" and doc["topic_id"] == ids["topic"]
    first = doc["sections"][0]["blocks"][0]
    assert first["markdown"] == "Transactions keep data correct." and first["citations"] == ["M1"]  # inline label absorbed
    citation = lesson["citations"][0]
    assert (citation["label"], citation["kind"], citation["filename"], citation["available"]) == ("M1", "material", "notes.pdf", True)
    assert "atomicity" in citation["quote"].lower()
    version = lesson["version"]
    assert version["model"] == "fake-chat" and version["prompt_version"] == "lesson-v1" and version["input_tokens"] > 0
    assert any("M9" in w for w in version["warnings"])
    if KATEX:  # the broken formula was repaired by the MathFixes call, inline and display copies alike
        assert any(b["type"] == "formula" and b["latex"] == r"\frac{n(n-1)}{2}" for s in doc["sections"] for b in s["blocks"])
        assert any(r"$\frac{n(n-1)}{2}$" in b.get("markdown", "") for s in doc["sections"] for b in s["blocks"])
        assert "Repaired 2 formula(s)" in version["warnings"]
    research = client.get(f"/api/v1/topics/{ids['topic']}/research").json()
    assert research["sufficient"] is True and research["source_count"] == 0  # materials sufficed: no web search
    prompt = chat.prompts("LlmLesson")[0]
    assert '<source id="M1" file="notes.pdf' in prompt and "Depth: detailed" in prompt

    structure = client.get(f"/api/v1/courses/{ids['course']}/units").json()
    acid = next(t for u in structure["units"] for t in u["topics"] if t["title"] == "ACID Properties")
    assert acid["status"] == "lesson_available" and acid["lesson_id"] == queued["id"]


def test_missing_sections_get_one_repair(client: TestClient, chat: FakeChat, db: Session, lesson_queue: list,
                                         course_with_notes: dict[str, str], no_web: None) -> None:
    reset(client, course_with_notes, lesson_queue)
    replies = iter([lesson_reply(roles={"introduction", "concept"}), lesson_reply()])
    chat.replies["LlmLesson"] = lambda prompt: next(replies)
    lesson = client.post(f"/api/v1/topics/{course_with_notes['topic']}/lessons/generate").json()
    run_queued(db, lesson_queue)
    assert client.get(f"/api/v1/lessons/{lesson['id']}").json()["lesson"]["status"] == "ready"
    second = chat.prompts("LlmLesson")[1]
    assert "missing required sections: common_mistakes, definitions, examples, practice, quick_revision, visual" in second

    chat.replies["LlmLesson"] = {"title": "Empty", "estimated_minutes": 5, "learning_objectives": [], "prerequisites": [], "sections": []}
    client.post(f"/api/v1/lessons/{lesson['id']}/regenerate")
    run_queued(db, lesson_queue)
    failed = client.get(f"/api/v1/topics/{course_with_notes['topic']}/lessons").json()[0]
    assert failed["status"] == "failed" and "didn't produce a valid lesson" in failed["error"]
    assert failed["current_version"] == 1  # the earlier version is still there to read


def test_versions_enrich_and_feedback(client: TestClient, chat: FakeChat, db: Session, lesson_queue: list,
                                      course_with_notes: dict[str, str], no_web: None) -> None:
    reset(client, course_with_notes, lesson_queue)
    chat.replies["LlmLesson"] = lesson_reply()
    lesson = client.post(f"/api/v1/topics/{course_with_notes['topic']}/lessons/generate").json()
    run_queued(db, lesson_queue)
    assert client.post(f"/api/v1/topics/{course_with_notes['topic']}/lessons/generate").json()["status"] == "queued"
    assert client.post(f"/api/v1/lessons/{lesson['id']}/regenerate").status_code == 409  # already queued
    run_queued(db, lesson_queue)

    chat.replies["LlmSection"] = section("concept", "Another example", blk("example", "M1", title="ATM", problem="Withdraw.", solution="Lock, debit, commit."))
    client.post(f"/api/v1/lessons/{lesson['id']}/enrich", json={"request": "another worked example"})
    run_queued(db, lesson_queue)

    versions = client.get(f"/api/v1/lessons/{lesson['id']}/versions").json()
    assert [(v["version"], v["kind"]) for v in versions] == [(3, "enriched"), (2, "generated"), (1, "generated")]
    v3 = client.get(f"/api/v1/lessons/{lesson['id']}").json()
    added = v3["document"]["sections"][-1]
    assert added["role"] == "extension" and added["title"] == "Another example"
    labels = [c["label"] for c in v3["citations"]]
    assert "M1" in labels and len(labels) == len(set(labels))  # inherited M1 + the new section's own label
    assert added["blocks"][0]["citations"] != ["M1"]  # new evidence was numbered after the existing labels
    assert 'another worked example' in chat.prompts("LlmSection")[0]
    v1 = client.get(f"/api/v1/lessons/{lesson['id']}", params={"version": 1}).json()
    assert v1["version"]["version"] == 1 and len(v1["document"]["sections"]) == len(v3["document"]["sections"]) - 1

    assert client.post(f"/api/v1/lessons/{lesson['id']}/feedback", json={"rating": 1, "comment": "clear"}).status_code == 204
    assert client.post(f"/api/v1/lessons/{lesson['id']}/feedback", json={"rating": 5}).status_code == 422
    assert client.post(f"/api/v1/lessons/{lesson['id']}/enrich", json={"request": "x"}).status_code == 422


def test_outdated_when_sources_change(client: TestClient, chat: FakeChat, db: Session, lesson_queue: list,
                                      course_with_notes: dict[str, str], no_web: None) -> None:
    ids = course_with_notes
    reset(client, ids, lesson_queue)
    chat.replies["LlmLesson"] = lesson_reply()
    lesson = client.post(f"/api/v1/topics/{ids['topic']}/lessons/generate").json()
    run_queued(db, lesson_queue)
    assert client.get(f"/api/v1/lessons/{lesson['id']}").json()["lesson"]["outdated_reason"] is None

    # bag-of-words test vectors: share the topic's words ("ACID Properties", "Transactions", "Atomicity")
    more = make_pdf([("ACID", "Transactions and ACID properties: atomicity means all or nothing. " * 20)])
    upload(client, ids["ws"], more, name="more.pdf", kind="notes", course_id=ids["course"])
    assert "New material" in client.get(f"/api/v1/lessons/{lesson['id']}").json()["lesson"]["outdated_reason"]

    client.delete(f"/api/v1/documents/{ids['doc']}")
    after = client.get(f"/api/v1/lessons/{lesson['id']}").json()
    assert "deleted" in after["lesson"]["outdated_reason"]
    m1 = next(c for c in after["citations"] if c["label"] == "M1")
    assert m1["available"] is False and "atomicity" in m1["quote"].lower()  # the snapshot survives


def test_budget_and_pins(client: TestClient, chat: FakeChat, db: Session, lesson_queue: list,
                         course_with_notes: dict[str, str], no_web: None, monkeypatch: pytest.MonkeyPatch) -> None:
    ids = course_with_notes
    reset(client, ids, lesson_queue)
    other_doc = upload(client, workspace(client, "elsewhere"), make_docx(), name="x.docx").json()
    assert client.put(f"/api/v1/topics/{ids['topic']}/documents", json={"document_ids": [other_doc["id"]]}).status_code == 422
    extra = upload(client, ids["ws"], make_pdf([("Recovery", "Log-based recovery with undo and redo. " * 20)]), name="pinned.pdf").json()
    pinned = client.put(f"/api/v1/topics/{ids['topic']}/documents", json={"document_ids": [extra["id"]]}).json()
    assert [d["filename"] for d in pinned] == ["pinned.pdf"]

    chat.replies["LlmLesson"] = lesson_reply()
    client.post(f"/api/v1/topics/{ids['topic']}/lessons/generate")
    run_queued(db, lesson_queue)
    assert 'file="pinned.pdf' in chat.prompts("LlmLesson")[-1]  # pinned document offered as evidence (D12)

    monkeypatch.setattr(settings, "workspace_monthly_tokens", 1)
    lesson = client.post(f"/api/v1/topics/{ids['topic']}/lessons/generate", json={"depth": "exam"}).json()
    run_queued(db, lesson_queue)
    failed = next(l for l in client.get(f"/api/v1/topics/{ids['topic']}/lessons").json() if l["id"] == lesson["id"])
    assert failed["status"] == "failed" and "monthly AI budget" in failed["error"]


def test_estimate_shown_for_draft(client: TestClient, chat: FakeChat) -> None:
    _, cid, _ = parsed(client, chat)
    estimate = client.get(f"/api/v1/courses/{cid}/syllabus").json()["generation_estimate"]
    assert estimate["lessons"] == 3 and estimate["ai_calls"] > 0 and estimate["web_searches_max"] == 3 * settings.research_max_queries
    assert client.post(f"/api/v1/topics/{uuid.uuid4()}/lessons/generate").status_code == 404
    # the topic is checked (exists, you're a member) before the request body
    assert client.post(f"/api/v1/topics/{uuid.uuid4()}/lessons/generate", json={"depth": "nonsense"}).status_code == 404
