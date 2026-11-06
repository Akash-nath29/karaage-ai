"""Deterministic grading (PRD H5) and answer-key checks. No AI here."""

import math
import re
from typing import Any

OBJECTIVE = {"mcq", "true_false", "numerical", "fill_blank"}
WRITTEN = {"short", "long", "descriptive"}
TYPES = OBJECTIVE | WRITTEN
DIFFICULTIES = {"easy", "medium", "hard"}
NUMBER = re.compile(r"-?\d+(?:\.\d+)?(?:[eE]-?\d+)?")


def _words(text: str) -> str:
    return " ".join(re.sub(r"[^\w\s.-]", " ", text.lower()).split()).strip(" .")


def _number(text: str) -> float | None:
    found = NUMBER.search(text.replace(",", ""))
    return float(found.group()) if found else None


def grade_objective(type_: str, key: str, given: str) -> bool:
    """Is the student's answer right? mcq/true_false: option index. numerical: within 1% (or 0.01).
    fill_blank: any accepted alternative, ignoring case and punctuation."""
    given = given.strip()
    if not given:
        return False
    if type_ in ("mcq", "true_false"):
        return given == key.strip()
    if type_ == "numerical":
        expected, actual = _number(key), _number(given)
        # ponytail: fixed tolerance; per-question tolerance/units if papers need it
        return expected is not None and actual is not None and math.isclose(actual, expected, rel_tol=0.01, abs_tol=0.01)
    if type_ == "fill_blank":
        return _words(given) in {_words(alt) for alt in key.split("|") if alt.strip()}
    raise ValueError(f"{type_} isn't graded deterministically")


def default_rubric(marks: int) -> list[dict[str, Any]]:
    """PRD H5's example split (5 marks: accuracy 2, explanation 1, example 1, presentation 1), scaled."""
    if marks <= 2:
        return [{"criterion": "Correct and complete answer", "marks": marks}]
    accuracy = math.ceil(marks * 0.4)
    rest = marks - accuracy
    split = [rest - 2 * (rest // 3), rest // 3, rest // 3]
    names = ["Explanation", "Example or application", "Presentation and structure"]
    return [{"criterion": "Conceptual accuracy", "marks": accuracy}] + [
        {"criterion": n, "marks": m} for n, m in zip(names, split, strict=True) if m]


def check_key(type_: str, options: list[str], answer: str | None, rubric: list[dict[str, Any]], marks: int) -> tuple[str | None, list[dict[str, Any]], str | None]:
    """Validate an answer key. Returns (answer, rubric, problem): an unusable key comes back as (None, …, reason);
    a written answer's rubric is replaced by the default when it doesn't add up to the marks."""
    answer = (answer or "").strip()
    if not answer:
        return None, [], "no answer key"
    if type_ in ("mcq", "true_false"):
        if not answer.isdigit() or int(answer) >= len(options):
            return None, [], f"answer {answer!r} isn't an option index"
        return answer, [], None
    if type_ == "numerical":
        return (answer, [], None) if _number(answer) is not None else (None, [], f"answer {answer!r} isn't a number")
    if type_ == "fill_blank":
        return answer, [], None
    return answer, normalize_rubric(rubric, marks), None


def normalize_rubric(rubric: list[dict[str, Any]], marks: int) -> list[dict[str, Any]]:
    """Criteria that add up to the marks, or the default split."""
    criteria = [{"criterion": str(c.get("criterion", "")).strip()[:200], "marks": int(c.get("marks", 0))} for c in rubric]
    criteria = [c for c in criteria if c["criterion"] and c["marks"] > 0]
    return criteria if sum(c["marks"] for c in criteria) == marks else default_rubric(marks)


def normalize_question(raw: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    """Clean an LLM-written or extracted question: known type and difficulty, sane marks, options that fit."""
    text = str(raw.get("text") or "").strip()
    if len(text) < 5:
        return None, "empty question"
    type_ = str(raw.get("type") or "").strip().lower().replace("-", "_").replace(" ", "_")
    type_ = {"multiple_choice": "mcq", "truefalse": "true_false", "fill_in_the_blank": "fill_blank",
             "fill_in_the_blanks": "fill_blank", "long_answer": "long", "short_answer": "short"}.get(type_, type_)
    marks = raw.get("marks")
    marks = int(marks) if isinstance(marks, int | float) and 0 < marks <= 100 else None
    if type_ not in TYPES:
        type_ = "short" if (marks or 2) <= 3 else "long"
    options = [str(o).strip() for o in raw.get("options") or [] if str(o).strip()]
    if type_ == "true_false":
        options = ["True", "False"]
    elif type_ == "mcq" and len(options) < 2:
        return None, "multiple choice without options"
    elif type_ != "mcq":
        options = []
    marks = marks or (1 if type_ in OBJECTIVE else 2 if type_ == "short" else 5)
    difficulty = str(raw.get("difficulty") or "medium").lower()
    return {"text": text, "type": type_, "marks": marks, "options": options,
            "difficulty": difficulty if difficulty in DIFFICULTIES else "medium"}, None
