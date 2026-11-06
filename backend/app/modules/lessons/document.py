"""The lesson document (PRD F3–F5, Q5): sections with a pedagogical role (F3), each holding typed blocks (F5).

Two schemas:
- LessonDocument: strict, versioned (SCHEMA_VERSION), a discriminated union of block types. Stored and rendered.
- LlmLesson: what the model fills in. One flexible block object with optional fields, because big unions are
  unreliable in providers' structured-output modes (R5). `to_document` converts it, dropping anything invalid
  and recording why.
"""

import re
import uuid
from typing import Annotated, Any, Literal

from pydantic import BaseModel, Field, ValidationError

from app.modules.lessons.diagrams import DiagramEdge, DiagramError, DiagramKind, DiagramNode, to_mermaid

SCHEMA_VERSION = "1.0"

Depth = Literal["beginner", "conceptual", "detailed", "exam", "revision", "advanced"]
DEPTHS: dict[str, str] = {
    "beginner": "Beginner-friendly",
    "conceptual": "Conceptual understanding",
    "detailed": "Detailed academic explanation",
    "exam": "Exam-oriented",
    "revision": "Quick revision",
    "advanced": "Advanced exploration",
}
Role = Literal[
    "introduction", "concept", "visual", "examples", "definitions", "comparison",
    "common_mistakes", "exam_preparation", "quick_revision", "practice", "extension",
]
# Sections a lesson must have at each depth (§11.5 "required sections"). Objectives and prerequisites are
# top-level fields, so F3's 12 parts = these roles + those two lists.
REQUIRED: dict[str, set[str]] = {
    "beginner": {"introduction", "concept", "examples", "quick_revision"},
    "conceptual": {"introduction", "concept", "visual", "examples", "quick_revision"},
    "detailed": {"introduction", "concept", "visual", "examples", "definitions", "common_mistakes", "quick_revision", "practice"},
    "exam": {"introduction", "concept", "definitions", "exam_preparation", "quick_revision", "practice"},
    "revision": {"definitions", "quick_revision", "practice"},
    "advanced": {"introduction", "concept", "visual", "examples", "comparison", "practice"},
}

Text = Annotated[str, Field(min_length=1)]


# --- Strict document --------------------------------------------------------------------------------------------


class _Block(BaseModel):
    citations: list[str] = []  # evidence labels (M1… materials, W1… web); resolved in lesson_citations


class Paragraph(_Block):
    type: Literal["paragraph"] = "paragraph"
    markdown: Text


class Heading(_Block):
    type: Literal["heading"] = "heading"
    text: Text


class Concept(_Block):
    type: Literal["concept"] = "concept"
    term: Text
    markdown: Text


class Diagram(_Block):
    type: Literal["diagram"] = "diagram"
    kind: DiagramKind
    caption: str = ""
    renderer: Literal["mermaid"] = "mermaid"
    source: Text


class Table(_Block):
    type: Literal["table"] = "table"
    caption: str = ""
    headers: list[str]
    rows: list[list[str]]


class ComparisonRow(BaseModel):
    aspect: str
    values: list[str]


class Comparison(_Block):
    type: Literal["comparison"] = "comparison"
    caption: str = ""
    items: list[str]  # the things compared (columns)
    rows: list[ComparisonRow]


class Formula(_Block):
    type: Literal["formula"] = "formula"
    latex: Text
    explanation: str = ""


class Code(_Block):
    type: Literal["code"] = "code"
    language: str = ""
    code: Text
    explanation: str = ""


class Example(_Block):
    type: Literal["example"] = "example"
    title: str = ""
    problem: Text
    solution: Text


class Callout(_Block):
    type: Literal["callout"] = "callout"
    variant: Literal["note", "tip", "warning", "exam"] = "note"
    markdown: Text


class Steps(_Block):
    type: Literal["steps"] = "steps"
    title: str = ""
    steps: list[str]


class QuizQuestion(BaseModel):
    question: Text
    options: list[str] = Field(min_length=2, max_length=6)
    answer: int  # index into options
    explanation: str = ""


class Quiz(_Block):
    type: Literal["quiz"] = "quiz"
    questions: list[QuizQuestion]


class Card(BaseModel):
    front: Text
    back: Text


class Flashcards(_Block):
    type: Literal["flashcards"] = "flashcards"
    cards: list[Card]


class Summary(_Block):
    type: Literal["summary"] = "summary"
    points: list[str]


Block = Annotated[
    Paragraph | Heading | Concept | Diagram | Table | Comparison | Formula | Code | Example | Callout | Steps
    | Quiz | Flashcards | Summary,
    Field(discriminator="type"),
]


class Section(BaseModel):
    id: str
    role: Role
    title: Text
    blocks: list[Block] = Field(min_length=1)


class LessonDocument(BaseModel):
    schema_version: Literal["1.0"] = SCHEMA_VERSION
    title: Text
    topic_id: uuid.UUID
    depth: Depth
    estimated_minutes: int = Field(ge=1, le=240)
    learning_objectives: list[str]
    prerequisites: list[str]
    sections: list[Section] = Field(min_length=1)


# --- What the model fills in ------------------------------------------------------------------------------------

BlockType = Literal[
    "paragraph", "heading", "concept", "diagram", "table", "comparison", "formula", "code", "example", "callout",
    "steps", "quiz", "flashcards", "summary",
]


class LlmDiagram(BaseModel):
    kind: DiagramKind
    nodes: list[DiagramNode]
    edges: list[DiagramEdge]


class LlmQuestion(BaseModel):
    question: str
    options: list[str]
    answer_index: int
    explanation: str


class LlmCard(BaseModel):
    front: str
    back: str


class LlmBlock(BaseModel):
    type: BlockType
    text: str | None  # paragraph/concept/callout body (markdown), heading text, formula/code explanation
    title: str | None  # concept term; example/steps title; diagram/table/comparison caption
    variant: str | None  # callout: note | tip | warning | exam
    headers: list[str] | None  # table headers; comparison: ["Aspect", item1, item2, …]
    rows: list[list[str]] | None  # table rows; comparison: [aspect, value1, value2, …]
    latex: str | None  # formula, without $ delimiters
    language: str | None
    code: str | None
    problem: str | None
    solution: str | None
    items: list[str] | None  # steps or summary points
    diagram: LlmDiagram | None
    questions: list[LlmQuestion] | None
    cards: list[LlmCard] | None
    citations: list[str]


class LlmSection(BaseModel):
    role: Role
    title: str
    blocks: list[LlmBlock]


class LlmLesson(BaseModel):
    title: str
    estimated_minutes: int
    learning_objectives: list[str]
    prerequisites: list[str]
    sections: list[LlmSection]


# --- Conversion ---------------------------------------------------------------------------------------------------


def _clean(text: str | None) -> str:
    return (text or "").strip()


def _list(items: list[str] | None) -> list[str]:
    return [i.strip() for i in items or [] if i and i.strip()]


def _block(b: LlmBlock, labels: set[str]) -> Block:
    """One model block → a strict block. Raises ValueError (with a reason) when it can't be rendered."""
    citations = [c.strip() for c in dict.fromkeys(b.citations) if c.strip() in labels]
    t = b.type
    if t == "paragraph":
        return Paragraph(markdown=_clean(b.text), citations=citations)
    if t == "heading":
        return Heading(text=_clean(b.text or b.title), citations=citations)
    if t == "concept":
        return Concept(term=_clean(b.title), markdown=_clean(b.text), citations=citations)
    if t == "diagram":
        if b.diagram is None:
            raise ValueError("diagram without nodes")
        source = to_mermaid(b.diagram.kind, b.diagram.nodes, b.diagram.edges)
        return Diagram(kind=b.diagram.kind, caption=_clean(b.title), source=source, citations=citations)
    if t == "table":
        headers = _list(b.headers)
        rows = [([c.strip() for c in r] + [""] * len(headers))[: len(headers)] for r in b.rows or [] if any(c.strip() for c in r)]
        if not headers or not rows:
            raise ValueError("table without headers or rows")
        return Table(caption=_clean(b.title), headers=headers, rows=rows, citations=citations)
    if t == "comparison":
        headers = _list(b.headers)
        items = headers[1:]
        rows = [ComparisonRow(aspect=r[0].strip(), values=([c.strip() for c in r[1:]] + [""] * len(items))[: len(items)])
                for r in b.rows or [] if r and r[0].strip()]
        if len(items) < 2 or not rows:
            raise ValueError("comparison needs two or more items and some rows")
        return Comparison(caption=_clean(b.title), items=items, rows=rows, citations=citations)
    if t == "formula":
        latex = _clean(b.latex).strip("$").strip()
        return Formula(latex=latex, explanation=_clean(b.text), citations=citations)
    if t == "code":
        return Code(language=_clean(b.language).lower()[:20], code=(b.code or "").strip("\n"), explanation=_clean(b.text), citations=citations)
    if t == "example":
        return Example(title=_clean(b.title), problem=_clean(b.problem or b.text), solution=_clean(b.solution), citations=citations)
    if t == "callout":
        variant = _clean(b.variant).lower()
        return Callout(variant=variant if variant in ("note", "tip", "warning", "exam") else "note",
                       markdown=_clean(b.text), citations=citations)
    if t == "steps":
        steps = _list(b.items)
        if not steps:
            raise ValueError("steps without steps")
        return Steps(title=_clean(b.title), steps=steps, citations=citations)
    if t == "quiz":
        questions = [
            QuizQuestion(question=q.question.strip(), options=_list(q.options), answer=q.answer_index, explanation=q.explanation.strip())
            for q in b.questions or [] if 0 <= q.answer_index < len(_list(q.options))
        ]
        if not questions:
            raise ValueError("quiz without valid questions")
        return Quiz(questions=questions, citations=citations)
    if t == "flashcards":
        cards = [Card(front=c.front.strip(), back=c.back.strip()) for c in b.cards or [] if c.front.strip() and c.back.strip()]
        if not cards:
            raise ValueError("flashcards without cards")
        return Flashcards(cards=cards, citations=citations)
    if t == "summary":
        points = _list(b.items) or [p for p in re.split(r"\n+[-*•]?\s*", _clean(b.text)) if p]
        if not points:
            raise ValueError("summary without points")
        return Summary(points=points, citations=citations)
    raise ValueError(f"unknown block type {t}")


def to_document(
    lesson: LlmLesson, *, topic_id: uuid.UUID, depth: str, labels: set[str]
) -> tuple[LessonDocument, list[str]]:
    """Convert and validate. Returns the document and warnings (blocks dropped, unknown citations, missing roles)."""
    warnings: list[str] = []
    sections = []
    for s in lesson.sections:
        blocks = []
        for b in s.blocks:
            unknown = [c for c in b.citations if c.strip() and c.strip() not in labels]
            if unknown:
                warnings.append(f"dropped unknown citation labels {unknown} in “{s.title}”")
            try:
                blocks.append(_block(b, labels))
            except (ValueError, ValidationError, DiagramError) as e:
                reason = e.errors()[0]["msg"] if isinstance(e, ValidationError) else str(e)
                warnings.append(f"dropped a {b.type} block in “{s.title}”: {reason}")
        if blocks and s.title.strip():
            sections.append(Section(id=f"s{len(sections) + 1}", role=s.role, title=s.title.strip(), blocks=blocks))
    document = LessonDocument(
        title=lesson.title.strip() or "Untitled lesson",
        topic_id=topic_id,
        depth=depth,  # type: ignore[arg-type]  # validated by the API
        estimated_minutes=min(max(lesson.estimated_minutes, 1), 240),
        learning_objectives=_list(lesson.learning_objectives)[:10],
        prerequisites=_list(lesson.prerequisites)[:10],
        sections=sections,
    )
    return document, warnings


def missing_roles(document: LessonDocument) -> set[str]:
    return REQUIRED[document.depth] - {s.role for s in document.sections}


INLINE_LABELS = re.compile(r"\s?\[((?:[MW]\d+)(?:\s*,\s*[MW]\d+)*)\]")


def absorb_inline_labels(document: dict[str, Any], labels: set[str]) -> None:
    """Models sometimes write "[M1]" in prose despite the citations field. Move known labels into the block's
    citations and strip all of them from the text, in place."""
    from app.modules.lessons.mathcheck import iter_texts

    for section in document["sections"]:
        for block in section["blocks"]:
            for text, set_text in iter_texts(block):
                found = INLINE_LABELS.findall(text)
                if not found:
                    continue
                for group in found:
                    for label in (x.strip() for x in group.split(",")):
                        if label in labels and label not in block["citations"]:
                            block["citations"].append(label)
                set_text(INLINE_LABELS.sub("", text))
