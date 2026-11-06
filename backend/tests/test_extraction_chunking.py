import shutil

import pytest

from app.core.tokens import estimate_tokens
from app.modules.documents.chunking import chunk_blocks
from app.modules.documents.extraction import Block, ExtractionError, extract, sniff
from tests.samples import LOREM, make_blank_pdf, make_docx, make_pdf, make_png, make_pptx


def test_sniff_by_content_not_extension() -> None:
    assert sniff(make_pdf([("A", "b")]), "notes.txt") == "pdf"
    assert sniff(make_docx(), "x.bin") == "docx"
    assert sniff(make_pptx(), "x") == "pptx"
    assert sniff(make_png("hi"), "x.pdf") == "png"
    assert sniff(b"\xff\xd8\xff\xe0rest", "x") == "jpeg"
    assert sniff(b"# Title\nbody", "README.md") == "md"
    assert sniff(b"plain words", "a.txt") == "txt"
    assert sniff(b"MZ\x90\x00\x03\x00\x00\x00", "app.exe") is None  # binary
    assert sniff(b"\xc3\x28 not utf-8", "a.txt") is None
    assert sniff(b"PK\x03\x04garbage", "a.docx") is None  # corrupt zip


def test_pdf_headings_pages_and_running_header_removed() -> None:
    sections = [(f"Chapter {i}", LOREM) for i in range(1, 6)]
    blocks, pages = extract("pdf", make_pdf(sections, header="Course Pack 2026"))
    assert pages == 5
    assert not any("Course Pack" in b.text for b in blocks)  # header on every page → dropped
    assert not any(b.text.strip().isdigit() for b in blocks)  # page-number footers → dropped
    headings = [(b.text, b.page) for b in blocks if b.heading]
    assert headings == [(f"Chapter {i}", i) for i in range(1, 6)]
    assert any(b.page == 3 and "Normalization" in b.text and not b.heading for b in blocks)


def test_pdf_blank_page_needs_ocr_or_fails_cleanly() -> None:
    if shutil.which("tesseract"):
        assert extract("pdf", make_blank_pdf())[0] == []
    else:
        with pytest.raises(ExtractionError, match="OCR"):
            extract("pdf", make_blank_pdf())


@pytest.mark.skipif(not shutil.which("tesseract"), reason="Tesseract not installed (runs in the worker image)")
def test_image_ocr() -> None:
    blocks, pages = extract("png", make_png("Entity relationship diagram"))
    assert pages == 1
    assert "relationship" in " ".join(b.text for b in blocks).lower()


def test_docx_headings_and_tables() -> None:
    blocks, pages = extract("docx", make_docx())
    assert pages is None
    assert [(b.text, b.heading) for b in blocks if b.heading] == [("Database Normalization", 1), ("Comparison", 2)]
    table = next(b for b in blocks if b.table)
    assert table.text == "Form | Removes\n2NF | Partial dependency"


def test_pptx_slides_tables_and_notes() -> None:
    blocks, pages = extract("pptx", make_pptx())
    assert pages == 2
    assert [(b.text, b.page) for b in blocks if b.heading] == [("Transactions", 1), ("Locking", 2)]
    assert any(b.table and "Serializable | Phantom reads" in b.text for b in blocks)
    assert any("bank transfer" in b.text and b.page == 1 for b in blocks)


def test_markdown_headings_tables_and_code_fences() -> None:
    md = "# Joins\nInner join keeps matches.\n\n| Join | Keeps |\n|---|---|\n| Left | All left rows |\n\n```sql\n# not a heading\nSELECT 1;\n```"
    blocks, _ = extract("md", md.encode())
    assert [b.text for b in blocks if b.heading] == ["Joins"]
    assert next(b for b in blocks if b.table).text == "| Join | Keeps |\n| Left | All left rows |"
    assert any("# not a heading" in b.text for b in blocks)


def test_chunks_respect_size_overlap_and_headings() -> None:
    long_body = " ".join(f"word{i}" for i in range(2000))  # ~4000 tokens → several chunks
    blocks = [Block("Unit 1", page=1, heading=1), Block("Intro text " * 20, page=1),
              Block("Topic A", page=2, heading=2), Block(long_body, page=2), Block(long_body, page=3)]
    chunks = chunk_blocks(blocks, max_tokens=800, min_tokens=300, overlap_tokens=100)

    assert all(c.token_count <= 800 + 100 for c in chunks)
    assert chunks[0].heading_path == "Unit 1"
    assert chunks[-1].heading_path == "Unit 1 > Topic A"
    assert chunks[-1].page_end == 3
    for a, b in zip(chunks[1:], chunks[2:], strict=False):  # size-split chunks carry the previous chunk's tail
        assert a.text.split()[-1] in b.text.split()[:60]  # ~100-token overlap ≈ 50 of these words


def test_heading_starts_new_chunk_only_after_min_tokens() -> None:
    small = [Block("H1", heading=1), Block("short " * 10), Block("H2", heading=1), Block("short " * 10)]
    assert len(chunk_blocks(small, 800, 300, 100)) == 1  # tiny sections are merged
    big = [Block("H1", heading=1), Block("long " * 400), Block("H2", heading=1), Block("long " * 400)]
    chunks = chunk_blocks(big, 800, 300, 100)
    assert [c.heading_path for c in chunks] == ["H1", "H2"]
    assert not chunks[1].text.startswith("long")  # heading boundary: no overlap carried


def test_tables_split_by_row_and_typed() -> None:
    rows = "\n".join(f"Row {i} | value {i} | more text here" for i in range(400))
    chunks = chunk_blocks([Block(rows, page=1, table=True)], 800, 300, 100)
    assert len(chunks) > 1
    assert all(c.content_type == "table" for c in chunks)
    for c in chunks:  # no row is cut in half
        body = [line for line in c.text.split("\n") if line.startswith("Row ")]
        assert all(line.endswith("more text here") for line in body[1:])
    assert estimate_tokens(rows) > 800
