"""Diagrams (PRD F6) compiled to Mermaid from structured nodes and edges (docs/decisions.md D15).

The LLM describes *what* to draw; this module writes the Mermaid source, so syntax is valid by construction:
no "generate → validate → retry" loop and no JavaScript runtime on the server. Labels are escaped with
Mermaid entity codes; ids are generated, so the LLM can't produce reserved words or broken syntax.
"""

import re
from typing import Literal

from pydantic import BaseModel

DiagramKind = Literal["flowchart", "concept_map", "sequence", "state", "er", "class"]
MAX_NODES, MAX_EDGES = 20, 30
ER_CARDINALITY = {
    "1:1": "||--||", "1:n": "||--o{", "1:m": "||--o{", "n:1": "}o--||", "m:1": "}o--||",
    "n:m": "}o--o{", "m:n": "}o--o{", "n:n": "}o--o{",
}
ER_TYPES = {"int", "integer", "string", "varchar", "char", "text", "date", "datetime", "float", "decimal", "boolean", "bool"}


class DiagramNode(BaseModel):
    id: str
    label: str
    details: list[str] = []  # ER attributes ("student_id PK") or class members ("+enroll()")


class DiagramEdge(BaseModel):
    source: str
    target: str
    label: str = ""
    cardinality: str = ""  # ER only: 1:1, 1:N, N:1, M:N


class DiagramError(ValueError):
    pass


def _text(s: str, limit: int = 80) -> str:
    """Label text safe inside Mermaid quotes/messages: one line, entity-coded # " ; < > (strict mode sanitizes
    HTML, so a bare "<" can swallow text) and no backticks."""
    s = " ".join(s.replace("`", "'").split())[:limit]
    codes = {"#": "#35;", '"': "#quot;", ";": "#59;", "<": "#lt;", ">": "#gt;"}
    return re.sub(r'[#";<>]', lambda m: codes[m[0]], s)


def _name(s: str, fallback: str) -> str:
    """An identifier for ER entities and classes, which display their own name."""
    name = re.sub(r"\W+", "_", s).strip("_")[:40]
    return name if name and not name[0].isdigit() else fallback


def _resolve(nodes: list[DiagramNode], edges: list[DiagramEdge]) -> tuple[list[DiagramNode], list[tuple[int, int, DiagramEdge]]]:
    """Index nodes; resolve edge endpoints by id, else by label (LLMs often use labels). Drop dangling edges."""
    nodes = [n for n in nodes if n.label.strip()][:MAX_NODES]
    if not nodes:
        raise DiagramError("diagram has no nodes")
    by_key: dict[str, int] = {}
    for i, n in enumerate(nodes):
        by_key.setdefault(n.id.strip().lower(), i)
        by_key.setdefault(" ".join(n.label.lower().split()), i)
    resolved = []
    for e in edges[:MAX_EDGES]:
        a, b = by_key.get(e.source.strip().lower()), by_key.get(e.target.strip().lower())
        if a is not None and b is not None:
            resolved.append((a, b, e))
    return nodes, resolved


def to_mermaid(kind: DiagramKind, nodes: list[DiagramNode], edges: list[DiagramEdge]) -> str:
    nodes, links = _resolve(nodes, edges)
    lines: list[str]
    if kind in ("flowchart", "concept_map"):
        rounded = kind == "concept_map"
        lines = ["flowchart LR" if rounded else "flowchart TD"]
        lines += [f'  n{i}("{_text(n.label)}")' if rounded else f'  n{i}["{_text(n.label)}"]' for i, n in enumerate(nodes)]
        for a, b, e in links:
            label = _text(e.label, 40)
            lines.append(f'  n{a} -->|"{label}"| n{b}' if label else f"  n{a} --> n{b}")
    elif kind == "state":
        lines = ["stateDiagram-v2"]
        lines += [f'  state "{_text(n.label)}" as s{i}' for i, n in enumerate(nodes)]
        for a, b, e in links:
            label = _text(e.label, 40)
            lines.append(f"  s{a} --> s{b}" + (f" : {label}" if label else ""))
    elif kind == "sequence":
        lines = ["sequenceDiagram"]
        lines += [f"  participant p{i} as {_text(n.label, 40)}" for i, n in enumerate(nodes)]
        for a, b, e in links:
            lines.append(f"  p{a}->>p{b}: {_text(e.label, 60) or '…'}")
    elif kind == "er":
        names = [_name(n.label, f"E{i}") for i, n in enumerate(nodes)]
        lines = ["erDiagram"]
        for name, n in zip(names, nodes, strict=True):
            attributes = []
            for detail in n.details[:12]:
                words = detail.replace(",", " ").split()
                key = words.pop() if len(words) > 1 and words[-1].upper() in ("PK", "FK", "UK") else ""
                kind_word = words.pop(0).lower() if len(words) > 1 and words[0].lower() in ER_TYPES else "string"
                attr = _name("_".join(words), "")
                if attr:
                    attributes.append(f"    {kind_word} {attr}" + (f" {key.upper()}" if key else ""))
            lines += [f"  {name} {{", *attributes, "  }"] if attributes else [f"  {name} {{", "  }"]
        for a, b, e in links:
            shape = ER_CARDINALITY.get(e.cardinality.replace(" ", "").lower(), "||--o{")
            lines.append(f'  {names[a]} {shape} {names[b]} : "{_text(e.label, 40) or "relates to"}"')
    elif kind == "class":
        names = [_name(n.label, f"C{i}") for i, n in enumerate(nodes)]
        lines = ["classDiagram"]
        for name, n in zip(names, nodes, strict=True):
            members = [re.sub(r"[^\w\s()+\-#:,<>~\[\]]", "", m).strip()[:60] for m in n.details[:12]]
            members = [m for m in members if m]
            lines += [f"  class {name} {{", *[f"    {m}" for m in members], "  }"] if members else [f"  class {name}"]
        for a, b, e in links:
            label = re.sub(r"[^\w\s\-]", "", e.label).strip()[:40]
            lines.append(f"  {names[a]} --> {names[b]}" + (f" : {label}" if label else ""))
    else:
        raise DiagramError(f"unknown diagram kind {kind!r}")
    return "\n".join(lines)
