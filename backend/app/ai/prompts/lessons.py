"""Lesson prompts. Bump PROMPT_VERSION on any change: it's stored with every lesson version (PRD F7, rule 19)."""

PROMPT_VERSION = "lesson-v1"

SYSTEM = (
    "You are an expert university teacher. You write structured, accurate study lessons that explain one syllabus "
    "topic progressively, from simple to complex, with examples and visuals. You never pad, and you never invent facts "
    "or sources."
)

DEPTH_GUIDE = {
    "beginner": "Assume no background. Plain language, analogies, short sentences, one idea at a time. About 900–1300 words.",
    "conceptual": "Focus on why and how things work: intuition first, then the formal view. About 1200–1800 words.",
    "detailed": "A thorough academic treatment: precise definitions, how each mechanism works, worked examples, edge cases. About 2000–3000 words.",
    "exam": (
        "Aim at semester exams: definitions to memorise, likely questions, and model-answer structures for 2-mark "
        "(about 60 words), 5-mark (about 250 words) and 10-mark (about 600 words) answers. About 1500–2500 words."
    ),
    "revision": "Compact revision notes: key points, definitions, formulas, flashcards. About 600–900 words.",
    "advanced": (
        "Go beyond the syllabus: deeper theory, trade-offs, current practice. Put beyond-syllabus material in callouts "
        "titled as such. About 2000–3000 words."
    ),
}

ROLES = """Section roles (use these, in this order; skip ones the depth doesn't need, repeat "concept" for sub-ideas):
- introduction: what the topic is and why it matters
- concept: the explanation itself, progressing from simple to complex
- visual: a diagram (block type "diagram") of a process, structure or relationship, with a sentence on how to read it
- examples: worked examples, each with a problem and a step-by-step solution
- definitions: exam-relevant terms as concept blocks (title = the term)
- comparison: comparison of related concepts (block type "comparison")
- common_mistakes: misconceptions and how to avoid them
- exam_preparation: likely question formats and model-answer structures
- quick_revision: a summary block of key points, plus flashcards
- practice: a quiz block of 3–5 multiple-choice questions with explanations"""

BLOCKS = """Block fields: fill the ones for the block's type and set the rest to null.
- paragraph: text (markdown). heading: text. concept: title = the term, text = its explanation.
- diagram: title = caption; diagram = {kind, nodes: [{id, label, details}], edges: [{source, target, label, cardinality}]}.
  kind: flowchart (steps/process), concept_map (related ideas), sequence (messages over time), state (states and
  transitions), er (entities: details = attributes like "student_id PK"; cardinality 1:1, 1:N or M:N), class (details =
  members). At most 12 nodes; edges refer to node ids.
- table: title = caption, headers, rows. comparison: title = caption, headers = ["Aspect", item A, item B, …],
  rows = [[aspect, value for A, value for B, …], …].
- formula: latex (no $ delimiters), text = what each symbol means. code: language, code, text = explanation.
- example: title, problem, solution (markdown, step by step). callout: variant = note | tip | warning | exam, text.
- steps: title, items (one per step). summary: items (one point each).
- quiz: questions = [{question, options (4), answer_index (0-based), explanation}]. flashcards: cards = [{front, back}].
Markdown only, never HTML. Math only as $…$ inline or $$…$$ display in KaTeX-compatible LaTeX. Never use $ for money
(write "Rs 500" or "USD 5")."""

CITATIONS = """Evidence: <source> blocks M1, M2, … are the student's own course materials; W1, W2, … are web pages.
- Prefer the student's materials for anything course-specific (scope, notation, definitions as taught).
- A block that states facts from a source lists that source's id in "citations". Use only ids shown here.
- Explanations, analogies and examples you write yourself get empty citations: the app shows them as AI-written.
- Never invent sources, page numbers, authors, quotes or statistics."""


def generate_prompt(*, path: str, subtopics: str, depth: str, evidence: str, feedback: str = "") -> str:
    return f"""Write the lesson for this syllabus topic.

Topic: {path}
Subtopics to cover: {subtopics or "none listed: cover the topic as a whole"}
Depth: {depth}. {DEPTH_GUIDE[depth]}

{ROLES}

{BLOCKS}

{CITATIONS}

estimated_minutes: realistic study time. learning_objectives: 3–6 "you will be able to …" statements.
prerequisites: concepts to know first (may be empty). Write in English.
{feedback}
{evidence}"""


ENRICH_SYSTEM = "You extend an existing study lesson with one focused new section that answers the student's request."


def enrich_prompt(*, path: str, outline: str, request: str, evidence: str) -> str:
    return f"""Topic: {path}

The lesson already has these sections:
{outline}

The student asks: "{request}"

Write ONE new section (role "extension") that answers this: a targeted explanation, extra example, diagram or
practice, whatever the request needs. Don't repeat what the lesson already covers. Title it after the request.

{BLOCKS}

{CITATIONS}

{evidence}"""


MATH_SYSTEM = "You fix LaTeX expressions so KaTeX can render them, keeping their meaning."


def math_prompt(broken: list[tuple[int, str, str]]) -> str:
    items = "\n".join(f"{i}. {tex}\n   KaTeX error: {error}" for i, tex, error in broken)
    return f"""These LaTeX expressions fail to render in KaTeX. Return a fixed version of each, same index, same
meaning, KaTeX-supported commands only, no $ delimiters.

{items}"""
