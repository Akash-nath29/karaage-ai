"""File sniffing and text extraction (PRD D3 steps 6–8).

Every format becomes one ordered list of Blocks (heading / paragraph / table, with page numbers),
so chunking is format-agnostic.
"""

import io
import re
import zipfile
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

import docx
import pptx
import pymupdf
from docx.table import Table

from app.core.exceptions import AppError

CONTENT_TYPES = {
    "pdf": "application/pdf",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "txt": "text/plain; charset=utf-8",
    "md": "text/markdown; charset=utf-8",
    "png": "image/png",
    "jpeg": "image/jpeg",
}
MAX_UNZIPPED_BYTES = 500 * 1024 * 1024  # zip-bomb guard for DOCX/PPTX
MIN_TEXT_CHARS = 20  # a PDF page with less text than this is treated as scanned and OCR'd

ProgressFn = Callable[[int, int], None]


@dataclass
class Block:
    text: str
    page: int | None = None  # 1-based page or slide; None for formats without pages
    heading: int = 0  # 0 = body, 1–6 = heading level
    table: bool = False


class ExtractionError(AppError):
    """The file can't be turned into text. The message is shown to the user; retrying won't help."""

    def __init__(self, detail: str) -> None:
        super().__init__(422, detail)


def sniff(data: bytes, filename: str) -> str | None:
    """Detect the real file type from content. The extension is only used to tell Markdown from plain text."""
    if data.startswith(b"%PDF-"):
        return "pdf"
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    if data.startswith(b"PK\x03\x04"):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if sum(i.file_size for i in z.infolist()) > MAX_UNZIPPED_BYTES:
                    return None
                names = set(z.namelist())
        except zipfile.BadZipFile:
            return None
        if "word/document.xml" in names:
            return "docx"
        if "ppt/presentation.xml" in names:
            return "pptx"
        return None
    if b"\x00" not in data[:8192]:
        try:
            data.decode("utf-8-sig")
        except UnicodeDecodeError:
            return None
        return "md" if filename.lower().endswith((".md", ".markdown")) else "txt"
    return None


def extract(file_type: str, data: bytes, progress: ProgressFn | None = None) -> tuple[list[Block], int | None]:
    """Return the document's blocks and its page/slide count (None when the format has no pages)."""
    if file_type == "pdf":
        return _pdf(_open_pdf(data, "pdf"), progress)
    if file_type in ("png", "jpeg"):
        image = _open_pdf(data, file_type)
        return _pdf(pymupdf.open("pdf", image.convert_to_pdf()), progress)
    if file_type == "docx":
        return _docx(data), None
    if file_type == "pptx":
        return _pptx(data)
    if file_type in ("txt", "md"):
        return _text(data.decode("utf-8-sig"), markdown=file_type == "md"), None
    raise ExtractionError(f"Unsupported file type: {file_type}")


def page_texts(file_type: str, data: bytes) -> list[tuple[int, str]]:
    """Plain text per page for an LLM to read: fast (no table detection), OCR for scanned pages.
    Formats without pages come back as a single page 1."""
    if file_type in ("pdf", "png", "jpeg"):
        doc = _open_pdf(data, file_type)
        if file_type != "pdf":
            doc = pymupdf.open("pdf", doc.convert_to_pdf())
        pages = []
        for n, page in enumerate(doc, start=1):
            text = page.get_text()
            if len(text.strip()) < MIN_TEXT_CHARS:
                text = page.get_text(textpage=_ocr_textpage(page))
            pages.append((n, re.sub(r"[ \t]+", " ", text).strip()))
        return pages
    by_page: dict[int, list[str]] = {}
    for block in extract(file_type, data)[0]:
        by_page.setdefault(block.page or 1, []).append(block.text)
    return sorted((page, "\n".join(texts)) for page, texts in by_page.items())


# --- PDF and images -----------------------------------------------------------------------------


@dataclass
class _Line:
    text: str
    spans: list[dict[str, Any]]
    bbox: tuple[float, float, float, float]
    block: int


def _open_pdf(data: bytes, filetype: str) -> pymupdf.Document:
    try:
        doc = pymupdf.open(stream=data, filetype=filetype)
    except Exception as e:
        raise ExtractionError(f"Could not read this file: {e}") from e
    if doc.needs_pass:
        raise ExtractionError("This PDF is password-protected. Remove the password and upload it again.")
    return doc


def _ocr_textpage(page: pymupdf.Page) -> pymupdf.TextPage:
    try:
        return page.get_textpage_ocr(language="eng", dpi=300, full=True)
    except Exception as e:
        raise ExtractionError(
            "This file needs OCR (scanned pages or an image), but Tesseract isn't available on the worker. "
            f"Details: {e}"
        ) from e


def _page_lines(page: pymupdf.Page) -> tuple[list[_Line], list[pymupdf.Rect], float]:
    """Lines in content-stream order (usually reading order), plus table regions."""
    if len(page.get_text().strip()) < MIN_TEXT_CHARS:
        data = page.get_text("dict", textpage=_ocr_textpage(page))
        tables: list[pymupdf.Rect] = []  # no vector ruling lines on scans, so table detection finds nothing
    else:
        data = page.get_text("dict")
        # ponytail: find_tables is ~0.3 s/page (most of extraction time); fine for background jobs.
        tables = [pymupdf.Rect(t.bbox) for t in page.find_tables().tables]
    lines = []
    for block_no, block in enumerate(data["blocks"]):
        for line in block.get("lines", []):
            text = "".join(s["text"] for s in line["spans"]).strip()
            if text:
                spans = [s for s in line["spans"] if s["text"].strip()]
                lines.append(_Line(text, spans, tuple(line["bbox"]), block_no))
    return lines, tables, page.rect.height


def _norm(text: str) -> str:
    return re.sub(r"\d+", "#", text.lower())


def _is_bold(span: dict[str, Any]) -> bool:
    return bool(span["flags"] & pymupdf.TEXT_FONT_BOLD) or "bold" in span["font"].lower()


def _heading_level(line: _Line, body_size: float) -> int:
    """Font-size and bold heuristics. Bigger than body → 1 or 2; bold at body size → 3."""
    text = line.text
    if len(text) > 120 or text.endswith((".", ",", ";")) or not re.search(r"[A-Za-z]{3}", text):
        return 0
    size = max(s["size"] for s in line.spans)
    if size >= body_size + 3:
        return 1
    if size >= body_size + 1:
        return 2
    if all(_is_bold(s) for s in line.spans) and len(text) <= 100:
        return 3
    # "Module-2: Introduction to C": a bold label followed by a short title
    if _is_bold(line.spans[0]) and line.spans[0]["text"].rstrip().endswith(":") and len(text) <= 80:
        return 3
    return 0


def _join(lines: list[_Line]) -> str:
    text = ""
    for line in lines:
        if text.endswith("-") and line.text[:1].islower():
            text = text[:-1] + line.text  # re-join hyphenated words
        else:
            text = f"{text} {line.text}" if text else line.text
    return text


def _table_text(lines: list[_Line]) -> str:
    """Rebuild rows from line positions. Uses page text, not cell detection, which splits words on some PDFs."""
    rows: list[list[_Line]] = []
    for line in sorted(lines, key=lambda l: ((l.bbox[1] + l.bbox[3]) / 2, l.bbox[0])):
        mid = (line.bbox[1] + line.bbox[3]) / 2
        if rows and abs(mid - (rows[-1][0].bbox[1] + rows[-1][0].bbox[3]) / 2) <= 3:
            rows[-1].append(line)
        else:
            rows.append([line])
    return "\n".join(" | ".join(l.text for l in sorted(row, key=lambda l: l.bbox[0])) for row in rows)


def _pdf(doc: pymupdf.Document, progress: ProgressFn | None) -> tuple[list[Block], int]:
    pages = []
    for i, page in enumerate(doc):
        pages.append(_page_lines(page))
        if progress and (i % 10 == 9 or i == doc.page_count - 1):
            progress(i + 1, doc.page_count)

    # Running headers/footers: the same text in the top or bottom 10% of many pages.
    # By position, not text order: on table-heavy pages the header isn't among the first lines.
    def at_edge(line: _Line, height: float) -> bool:
        return line.bbox[3] < 0.1 * height or line.bbox[1] > 0.9 * height

    def edge_key(line: _Line) -> tuple[str, int]:
        return _norm(line.text), round(line.bbox[1] / 10)  # digits normalized ("Page 3" ~ "Page 4"); same spot

    edges: Counter[tuple[str, int]] = Counter()
    for lines, _, height in pages:
        edges.update({edge_key(l) for l in lines if at_edge(l, height)})
    threshold = max(3, 0.2 * len(pages))
    repeated = {k for k, n in edges.items() if n >= threshold}

    def is_furniture(line: _Line, height: float) -> bool:
        return at_edge(line, height) and (edge_key(line) in repeated or line.text.isdigit())  # digits: page numbers

    sizes: Counter[float] = Counter()
    for lines, _, _ in pages:
        for line in lines:
            for s in line.spans:
                sizes[round(s["size"] * 2) / 2] += len(s["text"])
    body_size = sizes.most_common(1)[0][0] if sizes else 0.0

    blocks: list[Block] = []
    for page_no, (lines, tables, height) in enumerate(pages, start=1):
        lines = [l for l in lines if not is_furniture(l, height)]
        para: list[_Line] = []
        table_lines: dict[int, list[_Line]] = {}
        table_blocks: dict[int, Block] = {}

        def flush(para: list[_Line] = para, page_no: int = page_no) -> None:
            if para:
                blocks.append(Block(_join(para), page=page_no))
                para.clear()

        for line in lines:
            center = pymupdf.Point((line.bbox[0] + line.bbox[2]) / 2, (line.bbox[1] + line.bbox[3]) / 2)
            t = next((i for i, rect in enumerate(tables) if center in rect), None)
            if t is not None:
                flush()
                if t not in table_blocks:  # the table sits where its first line appears
                    table_blocks[t] = Block("", page=page_no, table=True)
                    table_lines[t] = []
                    blocks.append(table_blocks[t])
                table_lines[t].append(line)
                continue
            level = _heading_level(line, body_size)
            if level:
                flush()
                blocks.append(Block(line.text, page=page_no, heading=level))
                continue
            if para and line.block != para[-1].block:
                flush()
            para.append(line)
        flush()
        for t, block in table_blocks.items():
            block.text = _table_text(table_lines[t])
    return blocks, doc.page_count


# --- Office formats -----------------------------------------------------------------------------


def _row_text(cells: list[str]) -> str:
    deduped: list[str] = []
    for cell in (" ".join(c.split()) for c in cells):
        if not deduped or deduped[-1] != cell:  # merged cells repeat their text
            deduped.append(cell)
    return " | ".join(deduped)


def _docx(data: bytes) -> list[Block]:
    try:
        document = docx.Document(io.BytesIO(data))
    except Exception as e:
        raise ExtractionError(f"Could not read this Word document: {e}") from e
    blocks = []
    for item in document.iter_inner_content():
        if isinstance(item, Table):
            text = "\n".join(r for r in (_row_text([c.text for c in row.cells]) for row in item.rows) if r.strip(" |"))
            if text:
                blocks.append(Block(text, table=True))
            continue
        text = item.text.strip()
        if text:
            style = item.style.name if item.style is not None else ""
            match = re.fullmatch(r"Heading (\d)", style)
            level = 1 if style == "Title" else int(match.group(1)) if match else 0
            blocks.append(Block(text, heading=level))
    return blocks


def _pptx(data: bytes) -> tuple[list[Block], int]:
    try:
        deck = pptx.Presentation(io.BytesIO(data))
    except Exception as e:
        raise ExtractionError(f"Could not read this PowerPoint file: {e}") from e
    blocks = []
    for n, slide in enumerate(deck.slides, start=1):
        title = slide.shapes.title
        if title is not None and title.text_frame.text.strip():
            blocks.append(Block(title.text_frame.text.strip(), page=n, heading=1))
        for shape in slide.shapes:  # ponytail: shapes nested in groups are skipped
            if title is not None and shape.shape_id == title.shape_id:
                continue
            if shape.has_table:
                rows = [_row_text([c.text for c in row.cells]) for row in shape.table.rows]
                blocks.append(Block("\n".join(rows), page=n, table=True))
            elif shape.has_text_frame and shape.text_frame.text.strip():
                blocks.append(Block(shape.text_frame.text.strip(), page=n))
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                blocks.append(Block(notes, page=n))
    return blocks, len(deck.slides)


# --- Plain text and Markdown --------------------------------------------------------------------


def _text(text: str, markdown: bool) -> list[Block]:
    blocks: list[Block] = []
    para: list[str] = []
    table: list[str] = []
    in_fence = False

    def flush() -> None:
        if para:
            blocks.append(Block("\n".join(para)))
            para.clear()
        if table:
            blocks.append(Block("\n".join(table), table=True))
            table.clear()

    for raw in text.splitlines():
        line = raw.rstrip()
        if markdown and line.lstrip().startswith("```"):
            in_fence = not in_fence
        if not line.strip() and not in_fence:
            flush()
            continue
        if markdown and not in_fence:
            heading = re.match(r"\s*(#{1,6})\s+(.+)", line)
            if heading:
                flush()
                blocks.append(Block(heading.group(2).strip(" #"), heading=len(heading.group(1))))
                continue
            if line.lstrip().startswith("|"):
                if para:
                    blocks.append(Block("\n".join(para)))
                    para.clear()
                if not re.fullmatch(r"\s*\|[\s|:-]+\|?\s*", line):  # skip |---|---| separator rows
                    table.append(line.strip())
                continue
        if table:
            flush()
        para.append(line)
    flush()
    return blocks
