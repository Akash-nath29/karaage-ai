"""Question extraction benchmark (PRD H3, §16) on the SYNTHETIC Operating System paper, with the real models.

Run from backend/ with the compose services up and the AM401 syllabus confirmed (scripts.eval_syllabus):
    python -m scripts.eval_questions [--code AM401]
Reads the paper, extracts questions (LLM), maps them to the course's topics (embeddings), and scores the result
against tests/benchmark/synthetic_os_paper.EXPECTED. Nothing is saved except the usage log.
"""

import argparse
import re

import numpy as np
from sqlalchemy import select

from app.database.session import SessionLocal
from app.modules.courses.models import Course
from app.modules.documents import extraction
from app.modules.syllabus import mapping
from app.modules.syllabus.models import Syllabus
from app.orchestration import assessment_pipeline
from tests.benchmark.synthetic_os_paper import EXPECTED, pdf_bytes


def words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def label(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower().replace("q", "", 1) if text.lower().startswith("q") else text.lower())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--code", default="AM401")
    code = parser.parse_args().code
    with SessionLocal() as db:
        course = db.scalar(select(Course).join(Syllabus, Syllabus.course_id == Course.id)
                           .where(Course.code == code, Syllabus.status == "confirmed").limit(1))
        if course is None:
            raise SystemExit(f"No course {code} with a confirmed syllabus.")
        pages = extraction.page_texts("pdf", pdf_bytes())
        clean, skipped = assessment_pipeline.read_questions(db, course, pages)

        # Topic mapping, with the similarity scores so the threshold can be calibrated
        topics, matrix = mapping.topic_vectors(db, course)
        from app.ai import providers

        vectors = providers.get_embedder().embed([q["text"] for q in clean], "document")
        similarity = mapping._normalized(vectors) @ matrix.T
        best, scores = similarity.argmax(axis=1), similarity.max(axis=1)
        titles = [t.title for t in topics]
        db.rollback()  # cached topic vectors etc.: nothing from the benchmark is kept

    # One-to-one matching: share of an expected question's distinctive words found in the extracted text
    pairs = sorted(((len(words(e[5]) & words(q["text"])) / len(words(e[5])), i, j)
                    for i, e in enumerate(EXPECTED) for j, q in enumerate(clean)), reverse=True)
    matched: dict[int, int] = {}
    for score, i, j in pairs:
        if score >= 0.6 and i not in matched and j not in matched.values():
            matched[i] = j

    rows = []
    for i, (lbl, marks, types, topic, page, _) in enumerate(EXPECTED):
        j = matched.get(i)
        q = clean[j] if j is not None else None
        rows.append({
            "label": lbl, "found": q is not None,
            "label_ok": q is not None and label(q["label"]) == label(lbl),
            "marks_ok": q is not None and q["marks"] == marks,
            "type_ok": q is not None and q["type"] in types,
            "page_ok": q is not None and q["page"] == page,
            "topic": topic, "mapped": titles[best[j]] if j is not None else None,
            "score": float(scores[j]) if j is not None else 0.0,
            "got": f"{q['label']} [{q['type']}, {q['marks']}m, p{q['page']}]" if q else "-",
        })
    found = [r for r in rows if r["found"]]
    n = len(found) or 1
    print(f"{'expected':8} {'got':32} {'expected topic':28} {'mapped (score)':36}")
    for r in rows:
        flags = "".join(c if r[k] else "." for c, k in (("L", "label_ok"), ("M", "marks_ok"), ("T", "type_ok"), ("P", "page_ok")))
        mapped = f"{r['mapped']} ({r['score']:.3f})" if r["mapped"] else "-"
        mark = " " if r["mapped"] == r["topic"] else "x"
        print(f"{r['label']:8} {r['got']:32} {r['topic']:28} {mark} {mapped:36} {flags}")
    extra = [q for j, q in enumerate(clean) if j not in matched.values()]
    print(f"\nExtracted {len(clean)} (skipped {skipped} unusable); expected {len(EXPECTED)}")
    print(f"Recall {len(found) / len(EXPECTED):.2f}  precision {len(found) / max(len(clean), 1):.2f}  "
          f"labels {sum(r['label_ok'] for r in found) / n:.2f}  marks {sum(r['marks_ok'] for r in found) / n:.2f}  "
          f"types {sum(r['type_ok'] for r in found) / n:.2f}  pages {sum(r['page_ok'] for r in found) / n:.2f}")
    print("Topic mapping (top-1 accuracy over found questions, coverage at threshold):")
    right = np.array([r["mapped"] == r["topic"] for r in found])
    score = np.array([r["score"] for r in found])
    for threshold in (0.0, 0.5, 0.55, 0.6, 0.65, 0.7):
        kept = score >= threshold
        acc = right[kept].mean() if kept.any() else 0
        print(f"  >={threshold:.2f}: mapped {kept.mean():.2f} of questions, {acc:.2f} of those correct")
    for q in extra:
        print(f"  unmatched extraction: {q['label']}: {q['text'][:90]}")


if __name__ == "__main__":
    main()
