"""Structure-aware chunking (PRD D4): keeps the heading path, page range and table content type with each chunk."""

import re
from dataclasses import dataclass

from app.core.tokens import estimate_tokens
from app.modules.documents.extraction import Block

CHARS_PER_TOKEN = 4  # matches estimate_tokens


@dataclass
class Chunk:
    text: str
    heading_path: str  # "Chapter > Section > Subsection" where the chunk starts
    page_start: int | None
    page_end: int | None
    content_type: str  # text | table | mixed
    token_count: int


def _split_oversized(block: Block, limit_tokens: int) -> list[Block]:
    """Split a block bigger than the limit: tables by row, text by word. Each piece keeps the block's metadata."""
    if estimate_tokens(block.text) <= limit_tokens:
        return [block]
    units = [u + "\n" for u in block.text.split("\n")] if block.table else re.findall(r"\S+\s*", block.text)
    limit = limit_tokens * CHARS_PER_TOKEN
    pieces, current = [], ""
    for unit in units:
        if current and len(current) + len(unit) > limit:
            pieces.append(current)
            current = ""
        current += unit
    pieces.append(current)
    return [Block(p.strip(), page=block.page, table=block.table) for p in pieces if p.strip()]


def _tail(text: str, tokens: int) -> str:
    """Last ~`tokens` of text, starting at a word boundary: the overlap carried into the next chunk."""
    if tokens <= 0:
        return ""
    tail = text[-tokens * CHARS_PER_TOKEN :]
    if len(tail) < len(text) and " " in tail:
        tail = tail[tail.index(" ") + 1 :]
    return tail.strip()


def chunk_blocks(blocks: list[Block], max_tokens: int, min_tokens: int, overlap_tokens: int) -> list[Chunk]:
    """Greedy packing. A heading starts a new chunk once the current one has `min_tokens`;
    a chunk that hits `max_tokens` mid-section continues with `overlap_tokens` of overlap."""
    chunks: list[Chunk] = []
    stack: list[str] = []  # current heading path, index = level - 1
    parts: list[Block] = []
    size = 0
    start_path = ""

    def emit(overlap: bool) -> None:
        nonlocal parts, size, start_path
        if any(not b.heading for b in parts):  # skip chunks that are only headings
            text = "\n\n".join(b.text for b in parts)
            pages = [b.page for b in parts if b.page is not None]
            kinds = {b.table for b in parts if not b.heading}
            content_type = "table" if kinds == {True} else "mixed" if kinds == {True, False} else "text"
            chunks.append(
                Chunk(text, start_path, min(pages, default=None), max(pages, default=None), content_type, estimate_tokens(text))
            )
        tail = _tail("\n\n".join(b.text for b in parts), overlap_tokens) if overlap and parts else ""
        parts = [Block(tail, page=parts[-1].page, table=parts[-1].table)] if tail else []
        size = estimate_tokens(tail) if tail else 0
        start_path = " > ".join(stack)

    for block in blocks:
        if block.heading:
            if size >= min_tokens:
                emit(overlap=False)
            level = min(block.heading, len(stack) + 1)  # H1 then H3 nests one level, not two
            stack[:] = stack[: level - 1] + [block.text]
            if not parts:
                start_path = " > ".join(stack)
        for piece in _split_oversized(block, max_tokens - overlap_tokens):
            tokens = estimate_tokens(piece.text)
            if parts and size + tokens > max_tokens:
                emit(overlap=True)
            parts.append(piece)
            size += tokens
    emit(overlap=False)
    return chunks
