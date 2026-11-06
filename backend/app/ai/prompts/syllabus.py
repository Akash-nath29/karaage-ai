"""Syllabus parsing prompts. Bump PROMPT_VERSION on any change: it's stored with every parsed draft (PRD rule 19)."""

from app.ai.llm import fence

PROMPT_VERSION = "syllabus-v1"

LOCATE_SYSTEM = (
    "You locate one course's syllabus inside a long curriculum document. "
    "You see the first few lines of every page."
)


def locate_prompt(course: str, outline: str) -> str:
    return f"""Course to find: {course}

Which consecutive pages contain this course's syllabus: its course details and its content (units / modules /
topics), plus its textbooks and references if they follow? Rules:
- Match the course by title and code. If both a theory course and a lab exist, pick the one the title names
  (pick the lab only if the course title says Lab/Practical).
- start_page is where this course's syllabus begins; end_page is the last page before the next course starts.
- If the document has no syllabus for this course, set found to false.

<document>
{fence(outline)}
</document>"""


EXTRACT_SYSTEM = "You turn a course syllabus into a clean study structure: units, topics and subtopics."


def extract_prompt(course: str, pages: str) -> str:
    return f"""Course: {course}

Extract this course's syllabus from the pages below. Ignore any other courses on these pages.
- units: the syllabus's own units/modules, in order, with their titles (e.g. "Module 3: Branch and Loop" →
  "Branch and Loop"). hours: lecture hours if given (e.g. "9L" → 9), else null.
- topics: what a student would study in one sitting (roughly 20–45 minutes). Group closely related items into
  one topic; keep the syllabus's own wording. Put the finer items of a topic in subtopics.
- references: textbooks and reference books, one string each.
- exam_structure: the marks distribution or exam pattern if stated, else "".
- If these pages don't contain this course's content, set found to false.

<document>
{fence(pages)}
</document>"""
