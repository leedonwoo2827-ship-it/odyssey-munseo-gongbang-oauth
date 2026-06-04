"""Markdown 출력 — 원문 보존(미리보기/백업용). 항상 동시 생성된다."""
from __future__ import annotations

import json
from typing import Any


def to_markdown(payload: Any) -> str:
    """어떤 payload 든 사람이 읽을 Markdown 으로 변환(미리보기 공용)."""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict) and "slides" in payload:
        lines = [f"# {payload.get('title', '')}".rstrip()]
        if payload.get("subtitle"):
            lines.append(f"*{payload['subtitle']}*")
        for i, s in enumerate(payload.get("slides", []), 1):
            lines.append(f"\n## {i}. {s.get('title', '')}".rstrip())
            for b in s.get("bullets", []):
                lines.append(f"- {b}")
        return "\n".join(lines)
    if isinstance(payload, dict) and "rows" in payload:
        cols = payload.get("columns", [])
        lines = []
        if payload.get("title"):
            lines.append(f"# {payload['title']}")
        if cols:
            lines.append("| " + " | ".join(map(str, cols)) + " |")
            lines.append("| " + " | ".join("---" for _ in cols) + " |")
        for row in payload.get("rows", []):
            lines.append("| " + " | ".join("" if c is None else str(c) for c in row) + " |")
        return "\n".join(lines)
    return "```json\n" + json.dumps(payload, ensure_ascii=False, indent=2) + "\n```"


def render(payload: Any, out_path: str) -> str:
    text = to_markdown(payload)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    return out_path
