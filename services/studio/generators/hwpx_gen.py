"""HWPX 생성 — 회사 양식 스펙(hwpx_template_spec.md)에 맞춘 두 가지 경로.

(A) 한컴 OLE 모드 [권장·목표 PC]
    Windows + 한컴 한글 + pywin32 환경에서 HWPFrame.HwpObject 로 본문을 주입.
    템플릿(assets/hwpx_template.hwpx)이 있으면 열고 없으면 새 문서.

(B) ZIP 클론 모드 [폴백]
    회사 템플릿 .hwpx 를 그대로 복제하여 header.xml(폰트/스타일/페이지설정)을
    100% 재사용하고, 본문 섹션 내용만 생성 단락으로 교체한다.
    header 의 명명 스타일(제목/제목 1~3/본문/목록/인용)을 이름으로 찾아 매핑.

(C) 둘 다 불가하면 HwpxUnavailable 을 올려 pipeline 이 Markdown 으로 대체한다.
"""
from __future__ import annotations

import os
import zipfile
from typing import Dict, List, Optional

from .. import mdblocks
from . import md_gen

HH = "http://www.hancom.co.kr/hwpml/2011/head"
HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HS = "http://www.hancom.co.kr/hwpml/2011/section"


class HwpxUnavailable(RuntimeError):
    pass


# ── 진단 ────────────────────────────────────────────────────────────
def hancom_available() -> bool:
    try:
        import win32com.client  # noqa: F401
        import pythoncom  # noqa: F401
    except Exception:
        return False
    return os.name == "nt"


def render(payload, out_path: str, template: Optional[str] = None) -> str:
    md = md_gen.to_markdown(payload)

    # (A) 한컴 OLE
    if hancom_available():
        try:
            return _render_hancom(md, out_path, template)
        except Exception as e:
            print(f"[hwpx_export] 한컴 OLE 실패, ZIP 폴백 시도: {e}")

    # (B) ZIP 클론 (템플릿 필요)
    if template and os.path.exists(template):
        return _render_zip(md, out_path, template)

    raise HwpxUnavailable(
        "HWPX 를 생성할 수 없습니다.\n"
        " - 한컴 한글+pywin32 가 설치된 Windows 에서 실행하거나\n"
        " - assets/hwpx_template.hwpx 회사 양식을 넣어주세요.\n"
        "지금은 Markdown(.md) 으로 결과를 제공합니다."
    )


# ── (A) 한컴 OLE 모드 ────────────────────────────────────────────────
def _render_hancom(md: str, out_path: str, template: Optional[str]) -> str:
    import pythoncom
    import win32com.client as win32

    pythoncom.CoInitialize()
    try:
        hwp = win32.Dispatch("HWPFrame.HwpObject")
        try:
            hwp.RegisterModule("FilePathCheckDLL", "AutomationModule")
        except Exception:
            pass
        if template and os.path.exists(template):
            hwp.Open(os.path.abspath(template), "HWPX", "")
            hwp.MovePos(3)  # 문서 끝으로
        else:
            hwp.HAction.Run("FileNew")

        text = _md_to_plain(md)
        pset = hwp.HParameterSet.HInsertText
        hwp.HAction.GetDefault("InsertText", pset.HSet)
        pset.Text = text
        hwp.HAction.Execute("InsertText", pset.HSet)

        save = hwp.HParameterSet.HFileOpenSave
        hwp.HAction.GetDefault("FileSaveAs_S", save.HSet)
        save.filename = os.path.abspath(out_path)
        save.Format = "HWPX"
        hwp.HAction.Execute("FileSaveAs_S", save.HSet)
        try:
            hwp.Quit()
        except Exception:
            pass
        return out_path
    finally:
        pythoncom.CoUninitialize()


def _md_to_plain(md: str) -> str:
    """OLE InsertText 용 평문. 표는 탭 정렬 텍스트로, <br>는 이미 ' / '로 정규화됨."""
    lines = []
    for b in mdblocks.parse(md):
        t = b["type"]
        if t == "table":
            if b.get("header"):
                lines.append("\t".join(b["header"]))
            for row in b.get("rows", []):
                lines.append("\t".join(row))
        elif t == "heading":
            lines.append(b["text"])
        elif t == "bullet":
            lines.append("· " + b["text"])
        elif t == "quote":
            lines.append("  " + b["text"])
        else:
            lines.append(b["text"])
    return "\r\n".join(lines)


# ── (B) ZIP 클론 모드 ────────────────────────────────────────────────
def _render_zip(md: str, out_path: str, template: str) -> str:
    # 1) 템플릿 통째로 메모리에 로드 (압축정보 보존)
    src = zipfile.ZipFile(template)
    members = src.infolist()
    blobs: Dict[str, bytes] = {m.filename: src.read(m.filename) for m in members}

    # 2) header.xml 에서 명명 스타일 맵 구성
    style_map = _style_map(blobs.get("Contents/header.xml", b""))

    # 3) 본문 section 파일들 처리 (첫 섹션에만 콘텐츠 주입)
    section_names = sorted(n for n in blobs if n.startswith("Contents/section") and n.endswith(".xml"))
    blocks = mdblocks.parse(md)
    for idx, name in enumerate(section_names):
        blobs[name] = _rewrite_section(blobs[name], blocks if idx == 0 else [], style_map)

    # 4) 표지 placeholder 치환(_제목_입력_ 등)이 본문에 있으면 첫 헤딩으로
    title = next((b["text"] for b in blocks if b["type"] == "heading"), "")
    if title:
        for name in section_names:
            xml = blobs[name].decode("utf-8", "replace")
            if "_제목_입력_" in xml:
                xml = xml.replace("_제목_입력_", _xml_escape(title))
                blobs[name] = xml.encode("utf-8")

    # 5) re-zip — mimetype 을 STORED 로 가장 먼저
    _write_hwpx(out_path, members, blobs)
    src.close()
    return out_path


def _style_map(header_bytes: bytes) -> Dict[str, Dict[str, str]]:
    """style name → {styleId, paraPrIDRef, charPrIDRef}. 실패해도 빈 dict."""
    from lxml import etree
    out: Dict[str, Dict[str, str]] = {}
    if not header_bytes:
        return out
    try:
        root = etree.fromstring(header_bytes)
    except Exception:
        return out
    for st in root.iter(f"{{{HH}}}style"):
        name = st.get("name")
        if not name:
            continue
        out[name.strip()] = {
            "styleId": st.get("id", "0"),
            "paraPrIDRef": st.get("paraPrIDRef", "0"),
            "charPrIDRef": st.get("charPrIDRef", "0"),
        }
    return out


def _pick(style_map: Dict[str, Dict[str, str]], *names: str) -> Optional[Dict[str, str]]:
    for n in names:
        if n in style_map:
            return style_map[n]
    return None


def _rewrite_section(section_bytes: bytes, blocks: List[Dict],
                     style_map: Dict[str, Dict[str, str]]) -> bytes:
    """섹션의 본문 단락을 교체. 첫 단락(secPr=페이지설정)은 보존."""
    from lxml import etree

    root = etree.fromstring(section_bytes)
    ptag = f"{{{HP}}}p"
    paras = [c for c in root if c.tag == ptag]

    # 페이지 설정(secPr)을 가진 첫 단락 찾기
    secpr_para = None
    for p in paras:
        if p.find(f".//{{{HP}}}secPr") is not None:
            secpr_para = p
            break
    if secpr_para is None and paras:
        secpr_para = paras[0]

    # 기존 단락 전부 제거
    for p in paras:
        root.remove(p)

    # 페이지설정 단락 복원(텍스트는 비움 → secPr 만 유지)
    if secpr_para is not None:
        _strip_text(secpr_para)
        root.append(secpr_para)

    # 생성 단락 추가
    normal = _pick(style_map, "본문") or {"styleId": "0", "paraPrIDRef": "0", "charPrIDRef": "0"}
    emph = _pick(style_map, "강조")
    for blk in blocks:
        for b in (_table_to_blocks(blk) if blk["type"] == "table" else [blk]):
            st = _style_for_block(b, style_map, normal)
            root.append(_make_para(b, st, emph, normal))

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)


def _table_to_blocks(blk: Dict) -> List[Dict]:
    """표 블록 → 단락 블록들(헤더는 굵게 한 줄, 각 행은 ' / '로 이은 불릿)."""
    out: List[Dict] = []
    hdr = [c for c in (blk.get("header") or []) if c]
    if hdr:
        txt = " · ".join(hdr)
        out.append({"type": "para", "level": 0, "text": txt, "runs": [(txt, True)]})
    for row in blk.get("rows", []):
        cells = [c for c in row if c]
        if not cells:
            continue
        txt = " / ".join(cells)
        out.append({"type": "bullet", "level": 1, "text": txt, "runs": [(txt, False)]})
    return out


def _style_for_block(blk: Dict, style_map, normal) -> Dict[str, str]:
    t = blk["type"]
    if t == "heading":
        lvl = min(max(blk["level"], 1), 3)
        return _pick(style_map, f"제목 {lvl}", "제목", f"Heading {lvl}") or normal
    if t == "bullet":
        return _pick(style_map, "목록") or normal
    if t == "quote":
        return _pick(style_map, "인용") or normal
    return normal


def _make_para(blk: Dict, st: Dict[str, str], emph, normal):
    from lxml import etree
    p = etree.Element(f"{{{HP}}}p")
    p.set("paraPrIDRef", st["paraPrIDRef"])
    p.set("styleIDRef", st["styleId"])
    prefix = "· " if blk["type"] == "bullet" else ""
    runs = blk.get("runs") or [(blk.get("text", ""), False)]
    first = True
    for text, bold in runs:
        if not text:
            continue
        if first and prefix:
            text = prefix + text
        first = False
        char_id = (emph or normal)["charPrIDRef"] if bold and emph else st["charPrIDRef"]
        run = etree.SubElement(p, f"{{{HP}}}run")
        run.set("charPrIDRef", char_id)
        t = etree.SubElement(run, f"{{{HP}}}t")
        t.text = text
    if first:  # 빈 단락 보장
        run = etree.SubElement(p, f"{{{HP}}}run")
        run.set("charPrIDRef", st["charPrIDRef"])
        etree.SubElement(run, f"{{{HP}}}t").text = ""
    return p


def _strip_text(p) -> None:
    """단락에서 텍스트 run 만 제거하고 secPr/ctrl 등 구조는 유지."""
    for run in list(p):
        if run.tag == f"{{{HP}}}run":
            # secPr/ctrl 류가 들어있는 run 은 보존, 순수 텍스트 run 만 제거
            if run.find(f"{{{HP}}}secPr") is not None or run.find(f"{{{HP}}}ctrl") is not None:
                # 텍스트만 비움
                for t in run.iter(f"{{{HP}}}t"):
                    t.text = ""
            else:
                p.remove(run)


def _write_hwpx(out_path: str, members, blobs: Dict[str, bytes]) -> None:
    # mimetype 을 가장 먼저 STORED 로
    order = ["mimetype"] + [m.filename for m in members if m.filename != "mimetype"]
    seen = set()
    with zipfile.ZipFile(out_path, "w") as zf:
        for name in order:
            if name in seen or name not in blobs:
                continue
            seen.add(name)
            data = blobs[name]
            if name == "mimetype":
                zf.writestr(name, data, compress_type=zipfile.ZIP_STORED)
            else:
                zf.writestr(name, data, compress_type=zipfile.ZIP_DEFLATED)


def _xml_escape(s: str) -> str:
    return (s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
