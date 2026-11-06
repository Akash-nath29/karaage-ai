"""Syllabus parser benchmark (PRD §16): locate + extract against hand-checked courses, with the real chat model.

Run from backend/ with the compose services up (and the retrieval benchmark ingested once):
    python -m scripts.eval_syllabus [--course "Machine Learning"]
Creates/reuses courses in the "Retrieval benchmark" workspace and parses the shared syllabus for each.
"""

import argparse
import json
from difflib import SequenceMatcher
from pathlib import Path

from sqlalchemy import select

from app.config import settings
from app.database.session import SessionLocal
from app.modules.courses.models import Course
from app.modules.documents.models import Document
from app.modules.syllabus import parsing
from app.modules.syllabus import service as syllabus
from app.modules.syllabus.schemas import SyllabusDraft
from app.modules.workspaces import service as workspaces

BENCHMARK = Path(__file__).resolve().parents[1] / "tests" / "benchmark" / "aiml_r23_syllabus.json"


def similar(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--course", action="append", help="only this course title (repeatable)")
    only = parser.parse_args().course
    bench = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    with SessionLocal() as db:
        ws = next((w for w in workspaces.list_all(db) if w.name == "Retrieval benchmark"), None)
        if ws is None:
            raise SystemExit("Run `python -m scripts.eval_retrieval` first: it ingests the syllabus document.")
        doc = db.scalar(select(Document).where(Document.workspace_id == ws.id,
                                               Document.filename == Path(bench["document"]).name))
        assert doc is not None
        print(f"model {settings.llm_model_fast} · {doc.filename} ({doc.page_count} pages)\n")
        print(f"{'course':34} {'pages':>9} {'located':>8} {'units':>7} {'titles':>7} {'hours':>6} {'topics':>6}")
        syllabus.enqueue_parse = lambda job_id: parsing.run(db, job_id, can_retry=False)  # inline, no worker
        for case in (c for c in bench["courses"] if not only or c["title"] in only):
            course = db.scalar(select(Course).where(Course.workspace_id == ws.id, Course.title == case["title"]))
            if course is None:
                course = Course(workspace_id=ws.id, title=case["title"], code=case["code"])
                db.add(course)
                db.commit()
            result = syllabus.link(db, course.id, doc.id)
            if result.status != "draft":
                print(f"{case['title']:34} FAILED: {result.error}")
                continue
            draft = SyllabusDraft.model_validate(result.draft)
            located = result.page_start == case["start_page"] and result.page_end >= case["last_content_page"]
            expected_units = case["units"] or [None] * case["unit_count"]
            titles = (
                sum(similar(u.title, e) >= 0.6 for u, e in zip(draft.units, case["units"], strict=False)) / len(case["units"])
                if case["units"] else None
            )
            hours = (
                [u.hours for u in draft.units] == case["hours"] if case["hours"] else None
            )
            print(f"{case['title']:34} {result.page_start:>4}–{result.page_end:<4} {'yes' if located else 'NO':>8} "
                  f"{len(draft.units)}/{len(expected_units):<5} {'—' if titles is None else f'{titles:.0%}':>7} "
                  f"{'—' if hours is None else ('yes' if hours else 'NO'):>6} {sum(len(u.topics) for u in draft.units):>6}")
            for unit in draft.units:
                topics = "; ".join(t.title + (f" ({len(t.subtopics)})" if t.subtopics else "") for t in unit.topics)
                print(f"    {unit.title} [{unit.hours}h]: {topics[:150]}")


if __name__ == "__main__":
    main()
