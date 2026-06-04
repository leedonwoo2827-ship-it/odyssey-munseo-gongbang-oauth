"""아주 가벼운 Markdown → 블록 파서.

생성기(docx/hwpx)가 '제목/본문/목록/강조' 스타일로 매핑하기 위한 최소 구조만 추출한다.
지원: # ~ ###### 헤딩, 불릿(-,*,+ / 1.), 인용(>), 코드펜스(```), 일반 단락, **굵게**.
"""
from __future__ import annotations

import re
from typing import Dict, List, Tuple

_HEADING = re.compile(r"^(#{1,6})\s+(.*)$")
_BULLET = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
_QUOTE = re.compile(r"^>\s?(.*)$")
_BOLD = re.compile(r"\*\*(.+?)\*\*|__(.+?)__")


def parse(md: str) -> List[Dict]:
    """블록 리스트 반환. 각 블록: {type, ...}.

    type: heading(level,text) | para(text) | bullet(level,text) | quote(text) | code(text)
    text 는 인라인 마크업이 제거된 평문, runs 는 [(텍스트, bold)] 형태로 함께 제공.
    """
    blocks: List[Dict] = []
    lines = (md or "").replace("\r\n", "\n").split("\n")
    i = 0
    para: List[str] = []

    def flush_para():
        if para:
            text = " ".join(s.strip() for s in para).strip()
            if text:
                blocks.append(_mk("para", text))
            para.clear()

    while i < len(lines):
        line = lines[i]
        # 코드펜스
        if line.strip().startswith("```"):
            flush_para()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1  # 닫는 펜스 skip
            blocks.append({"type": "code", "text": "\n".join(buf), "runs": [("\n".join(buf), False)]})
            continue
        if not line.strip():
            flush_para()
            i += 1
            continue
        m = _HEADING.match(line)
        if m:
            flush_para()
            blocks.append(_mk("heading", m.group(2).strip(), level=len(m.group(1))))
            i += 1
            continue
        m = _BULLET.match(line)
        if m:
            flush_para()
            indent = len(m.group(1))
            level = 1 + indent // 2
            blocks.append(_mk("bullet", m.group(3).strip(), level=level))
            i += 1
            continue
        m = _QUOTE.match(line)
        if m:
            flush_para()
            blocks.append(_mk("quote", m.group(1).strip()))
            i += 1
            continue
        para.append(line)
        i += 1
    flush_para()
    return blocks


def _mk(btype: str, text: str, level: int = 0) -> Dict:
    return {"type": btype, "level": level, "text": _strip_inline(text), "runs": _runs(text)}


def _runs(text: str) -> List[Tuple[str, bool]]:
    """**굵게** 를 (조각, bold) 런 리스트로 분해."""
    runs: List[Tuple[str, bool]] = []
    pos = 0
    for m in _BOLD.finditer(text):
        if m.start() > pos:
            runs.append((_strip_inline(text[pos:m.start()]), False))
        runs.append((m.group(1) or m.group(2) or "", True))
        pos = m.end()
    if pos < len(text):
        runs.append((_strip_inline(text[pos:]), False))
    return [r for r in runs if r[0]] or [(_strip_inline(text), False)]


def _strip_inline(text: str) -> str:
    text = _BOLD.sub(lambda m: m.group(1) or m.group(2) or "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)          # 인라인 코드
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # 링크 → 텍스트만
    return text.strip()
