"""출력 렌더러 디스패치.

render(fmt, payload, out_path, template=None) → 실제 파일 생성.
payload 는 mode 에 따라 다르다:
  - report : Markdown 문자열
  - slides : {"title","subtitle","slides":[{"title","bullets":[...]}]}
  - table  : {"title","columns":[...],"rows":[[...],...]}  또는 Markdown(표 포함)
모든 포맷은 실패 시 예외를 올리며 pipeline 이 잡아 사용자에게 보여준다.
"""
from __future__ import annotations

from typing import Any, Optional

from . import md_gen, docx_gen, hwpx_gen, pptx_gen, xlsx_gen


def render(fmt: str, payload: Any, out_path: str, template: Optional[str] = None,
           mode: Optional[str] = None) -> str:
    fmt = (fmt or "md").lower()
    if fmt == "md":
        return md_gen.render(payload, out_path)
    if fmt == "docx":
        return docx_gen.render(payload, out_path, template=template)
    if fmt == "hwpx":
        return hwpx_gen.render(payload, out_path, template=template)
    if fmt == "pptx":
        # McKinsey 덱 모드 → 템플릿 복제 + 네이티브 차트 렌더러
        if (mode or "").lower() == "mckinsey_deck":
            from . import mckinsey_pptx_gen
            return mckinsey_pptx_gen.render(payload, out_path, template=template)
        return pptx_gen.render(payload, out_path, template=template)
    if fmt == "xlsx":
        return xlsx_gen.render(payload, out_path)
    raise ValueError(f"지원하지 않는 출력 형식: {fmt}")
