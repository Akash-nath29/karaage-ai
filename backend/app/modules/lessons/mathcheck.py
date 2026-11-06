"""LaTeX validation with real KaTeX (PRD F6/§11.5) via `tools/check_math.cjs` (Node).

Math appears as formula blocks (display) and as $…$ / $$…$$ inside any markdown text of a block. If Node or
KaTeX isn't installed, `check` returns None and the lesson records "math not checked" instead of failing:
the frontend renders with throwOnError off, so a bad expression shows as red source text, not a broken page.
"""

import json
import logging
import re
import shutil
import subprocess
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)
TOOL = Path(__file__).resolve().parents[3] / "tools" / "check_math.cjs"

# $$display$$ or $inline$ (not \$, no space just inside the delimiters: "costs $5 and $10" isn't math)
MATH = re.compile(r"\$\$(.+?)\$\$|(?<![\\$\w])\$(?![\s$])([^$\n]+?)(?<![\s\\])\$(?![\w$])", re.DOTALL)
# Keys of block fields that are never markdown
NOT_MARKDOWN = {"type", "kind", "renderer", "source", "variant", "language", "code", "latex", "citations", "answer"}


def check(expressions: list[tuple[str, bool]]) -> list[str | None] | None:
    """KaTeX error per (tex, display) expression, None where it renders. None if the checker isn't available."""
    if not expressions:
        return []
    node = shutil.which("node")
    if node is None:
        log.warning("math not checked: node isn't on PATH")
        return None
    try:
        proc = subprocess.run(
            [node, str(TOOL)],
            input=json.dumps([{"tex": t, "display": d} for t, d in expressions]),
            capture_output=True, text=True, encoding="utf-8", timeout=60,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        log.warning("math not checked: %s", e)
        return None
    if proc.returncode != 0:  # e.g. KaTeX not installed (npm install --prefix backend/tools)
        log.warning("math not checked: %s", proc.stderr.strip()[:300])
        return None
    return json.loads(proc.stdout)


def iter_texts(node: Any, setter: Callable[[str], None] | None = None) -> Iterator[tuple[str, Callable[[str], None]]]:
    """Every markdown string in a block dict, with a function that replaces it in place."""
    if isinstance(node, str) and setter:
        yield node, setter
    elif isinstance(node, dict):
        for key, value in node.items():
            if key not in NOT_MARKDOWN:
                yield from iter_texts(value, lambda v, d=node, k=key: d.__setitem__(k, v))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from iter_texts(value, lambda v, lst=node, j=i: lst.__setitem__(j, v))


def find_math(document: dict[str, Any]) -> list[tuple[str, bool]]:
    """All (tex, display) expressions in a lesson document dict, in a stable order."""
    found: list[tuple[str, bool]] = []
    for section in document["sections"]:
        for block in section["blocks"]:
            if block["type"] == "formula":
                found.append((block["latex"], True))
            for text, _ in iter_texts(block):
                found += [(m[1], True) if m[1] is not None else (m[2], False) for m in MATH.finditer(text)]
    return found


def replace_math(document: dict[str, Any], replacements: dict[tuple[str, bool], str | None]) -> None:
    """Swap expressions in place, keyed by (tex, display): the same LaTeX can be fixable inline and not in display
    mode. A None replacement means "give up": formula blocks become LaTeX code blocks and inline math becomes
    `code`, so the lesson still renders and shows the source."""
    for section in document["sections"]:
        for i, block in enumerate(section["blocks"]):
            if block["type"] == "formula" and (block["latex"], True) in replacements:
                fixed = replacements[(block["latex"], True)]
                if fixed is None:
                    section["blocks"][i] = {"type": "code", "language": "latex", "code": block["latex"],
                                            "explanation": block.get("explanation", ""), "citations": block["citations"]}
                else:
                    block["latex"] = fixed
            for text, set_text in iter_texts(section["blocks"][i]):

                def swap(m: re.Match[str]) -> str:
                    display = m[1] is not None
                    tex = m[1] if display else m[2]
                    if (tex, display) not in replacements:
                        return m[0]
                    fixed = replacements[(tex, display)]
                    if fixed is None:
                        return f"`{tex}`"
                    return f"$${fixed}$$" if display else f"${fixed}$"

                new = MATH.sub(swap, text)
                if new != text:
                    set_text(new)
