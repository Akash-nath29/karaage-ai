"""Small generated sample files and a deterministic test embedder."""

import hashlib
import io
import json
import re
from collections.abc import Iterator

import docx
import pptx
import pymupdf
from pptx.util import Inches

from app.ai.providers.base import EMBEDDING_DIM, ChatResult, Message, StreamUsage

LOREM = (
    "Normalization organizes relational tables to reduce redundancy. Functional dependencies describe how "
    "attributes determine each other, and each normal form removes a specific kind of anomaly. "
)


def make_pdf(sections: list[tuple[str, str]], header: str | None = "Course Pack 2026", repeat: int = 1) -> bytes:
    """One page per (heading, body) section; a running header on every page."""
    doc = pymupdf.open()
    for heading, body in sections:
        page = doc.new_page()
        if header:
            page.insert_text((72, 30), header, fontsize=9)
        page.insert_text((72, 90), heading, fontsize=18, fontname="hebo")
        page.insert_textbox(pymupdf.Rect(72, 110, 520, 780), body * repeat, fontsize=11)
        page.insert_text((300, 820), str(doc.page_count), fontsize=9)  # page number footer
    return doc.tobytes()


def make_docx() -> bytes:
    document = docx.Document()
    document.add_heading("Database Normalization", level=1)
    document.add_paragraph("First normal form requires atomic values.")
    document.add_heading("Comparison", level=2)
    table = document.add_table(rows=2, cols=2)
    for r, row in enumerate([("Form", "Removes"), ("2NF", "Partial dependency")]):
        for c, value in enumerate(row):
            table.cell(r, c).text = value
    buf = io.BytesIO()
    document.save(buf)
    return buf.getvalue()


def make_pptx() -> bytes:
    deck = pptx.Presentation()
    slide = deck.slides.add_slide(deck.slide_layouts[5])  # title only
    slide.shapes.title.text = "Transactions"
    box = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(6), Inches(1))
    box.text_frame.text = "ACID: atomicity, consistency, isolation, durability."
    table = slide.shapes.add_table(2, 2, Inches(1), Inches(3.5), Inches(6), Inches(1)).table
    for r, row in enumerate([("Level", "Prevents"), ("Serializable", "Phantom reads")]):
        for c, value in enumerate(row):
            table.cell(r, c).text = value
    slide.notes_slide.notes_text_frame.text = "Mention the bank transfer example."
    deck.slides.add_slide(deck.slide_layouts[5]).shapes.title.text = "Locking"
    buf = io.BytesIO()
    deck.save(buf)
    return buf.getvalue()


def make_png(text: str) -> bytes:
    """An image of text, for OCR."""
    doc = pymupdf.open()
    page = doc.new_page(width=600, height=200)
    page.insert_text((30, 100), text, fontsize=28)
    return page.get_pixmap(dpi=150).tobytes("png")


def make_blank_pdf() -> bytes:
    doc = pymupdf.open()
    doc.new_page()
    return doc.tobytes()


class FakeEmbedder:
    """Deterministic bag-of-words vectors: texts sharing words are similar. Tests only (PRD rule 24)."""

    provider = "fake"
    model = "fake-bow"

    def __init__(self) -> None:
        self.calls = 0

    def embed(self, texts: list[str], task: str) -> list[list[float]]:
        self.calls += 1
        vectors = []
        for text in texts:
            vector = [0.0] * EMBEDDING_DIM
            for word in re.findall(r"[a-z0-9]+", text.lower()):
                vector[int(hashlib.md5(word.encode()).hexdigest(), 16) % EMBEDDING_DIM] += 1.0
            vector[0] += 0.01  # never all-zero (cosine undefined)
            vectors.append(vector)
        return vectors


class FakeChat:
    """Scripted chat model. `replies` maps a schema name to a dict (returned as JSON) or to a function of the
    prompt returning one. Records every call. Tests only (PRD rule 24)."""

    provider = "fake"
    model = "fake-chat"

    def __init__(self) -> None:
        self.replies: dict[str, object] = {}
        self.calls: list[tuple[str, str, str]] = []  # (schema name, system, prompt)
        self.temperatures: list[float] = []
        self.stream_reply: object = "A fake answer."  # str, or a function of (system, messages) returning one
        self.stream_error: Exception | None = None  # raised after the first chunk
        self.streams: list[tuple[str, list[Message]]] = []  # (system, messages)

    def generate_json(self, system: str, prompt: str, schema: type, temperature: float = 0.2) -> ChatResult:
        self.calls.append((schema.__name__, system, prompt))
        self.temperatures.append(temperature)
        reply = self.replies[schema.__name__]
        value = reply(prompt) if callable(reply) else reply
        text = value if isinstance(value, str) else json.dumps(value)
        return ChatResult(text=text, input_tokens=100, output_tokens=20, model=self.model)

    def stream_text(self, system: str, messages: list[Message]) -> tuple[Iterator[str], StreamUsage]:
        self.streams.append((system, messages))
        text = self.stream_reply(system, messages) if callable(self.stream_reply) else str(self.stream_reply)
        usage = StreamUsage(model=self.model)

        def chunks() -> Iterator[str]:
            for i in range(0, len(text), 7):
                yield text[i : i + 7]
                if self.stream_error:
                    raise self.stream_error
            usage.input_tokens, usage.output_tokens = 200, len(text) // 4

        return chunks(), usage

    def prompts(self, schema_name: str) -> list[str]:
        return [p for name, _, p in self.calls if name == schema_name]


def make_text_pdf(pages: list[str]) -> bytes:
    """A PDF with the given text on each page (wrapped)."""
    doc = pymupdf.open()
    for text in pages:
        doc.new_page().insert_textbox(pymupdf.Rect(50, 50, 560, 800), text, fontsize=9)
    return doc.tobytes()
