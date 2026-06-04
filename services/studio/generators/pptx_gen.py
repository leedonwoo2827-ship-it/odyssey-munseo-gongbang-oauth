"""PPTX 생성 — 회사 마스터 양식의 Layout #0(표지)·#1(본문)에 콘텐츠 주입.

스펙(pptx_template_spec.md):
  - 16:9, Layout #0 = 제목+부제, Layout #1 = 제목+본문(불릿 3~5).
payload(slides 모드):
  {"title": "...", "subtitle": "...",
   "slides": [{"title": "...", "bullets": ["...", ...]}, ...]}
템플릿이 없으면 16:9 기본 테마로 생성.
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from . import md_gen

_ACCENT = "2E5BFF"   # 스펙 기본 강조색
_BG_TITLE = "1F2A44"


def _coerce_slides(payload: Any) -> Dict:
    """payload 가 Markdown 이면 슬라이드 구조로 최대한 변환."""
    if isinstance(payload, dict) and "slides" in payload:
        return payload
    # Markdown → 슬라이드: # = 표지 제목, ## = 슬라이드, 불릿 = 본문
    from .. import mdblocks
    md = payload if isinstance(payload, str) else md_gen.to_markdown(payload)
    blocks = mdblocks.parse(md)
    title, subtitle = "", ""
    slides: List[Dict] = []
    cur: Optional[Dict] = None
    for b in blocks:
        if b["type"] == "heading" and b["level"] == 1 and not title:
            title = b["text"]
        elif b["type"] == "heading":
            cur = {"title": b["text"], "bullets": []}
            slides.append(cur)
        elif b["type"] == "bullet":
            (cur or _new(slides))["bullets"].append(b["text"])
        elif b["type"] == "para":
            if cur is None and not subtitle:
                subtitle = b["text"]
            else:
                (cur or _new(slides))["bullets"].append(b["text"])
    if not slides:
        slides = [{"title": title or "내용", "bullets": [subtitle] if subtitle else []}]
    return {"title": title or "제목", "subtitle": subtitle, "slides": slides}


def _new(slides: List[Dict]) -> Dict:
    d = {"title": "내용", "bullets": []}
    slides.append(d)
    return d


def render(payload: Any, out_path: str, template: Optional[str] = None) -> str:
    from pptx import Presentation
    from pptx.util import Inches

    data = _coerce_slides(payload)

    if template and os.path.exists(template):
        prs = Presentation(template)
    else:
        prs = Presentation()
        prs.slide_width = Inches(13.333)
        prs.slide_height = Inches(7.5)

    layouts = prs.slide_layouts
    title_layout = layouts[0] if len(layouts) > 0 else layouts[0]
    body_layout = layouts[1] if len(layouts) > 1 else title_layout

    # ── 표지 ──
    s = prs.slides.add_slide(title_layout)
    _set_title(s, data.get("title", ""))
    _set_subtitle(s, data.get("subtitle", ""))

    # ── 본문 슬라이드 ──
    for slide in data.get("slides", []):
        s = prs.slides.add_slide(body_layout)
        _set_title(s, slide.get("title", ""))
        _set_body(s, slide.get("bullets", []))

    prs.save(out_path)
    return out_path


def _set_title(slide, text: str) -> None:
    if slide.shapes.title is not None:
        slide.shapes.title.text = text or ""
        return
    # title placeholder 가 없으면 첫 placeholder 사용
    for ph in slide.placeholders:
        ph.text = text or ""
        return


def _set_subtitle(slide, text: str) -> None:
    for ph in slide.placeholders:
        # idx 1 = subtitle(표준 제목 슬라이드)
        if ph.placeholder_format.idx == 1:
            ph.text = text or ""
            return


def _set_body(slide, bullets: List[str]) -> None:
    body = None
    for ph in slide.placeholders:
        idx = ph.placeholder_format.idx
        if idx != 0:  # 0 = title
            body = ph
            break
    if body is None:
        return
    tf = body.text_frame
    tf.clear()
    bullets = bullets or [""]
    for i, b in enumerate(bullets[:6]):
        para = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        para.text = str(b)
        para.level = 0
