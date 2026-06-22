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

import copy
import os
import re
import zipfile
from typing import Dict, List, Optional

from .. import mdblocks
from . import md_gen

HH = "http://www.hancom.co.kr/hwpml/2011/head"
HP = "http://www.hancom.co.kr/hwpml/2011/paragraph"
HS = "http://www.hancom.co.kr/hwpml/2011/section"

# 진짜 표 렌더링 토글. 한글이 표를 못 열면 .env 에 STUDIO_HWPX_REAL_TABLES=0 → 즉시 평탄화 폴백.
_REAL_TABLES = os.environ.get("STUDIO_HWPX_REAL_TABLES", "1") not in ("0", "false", "False", "")


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

    # 2-b) 진짜 표를 만들기 위한 청사진: 템플릿에 있는 표 단락 1개를 복제용으로 추출
    #      (맨땅에서 표 XML 을 짜면 한글이 안 여는 위험 → 검증된 구조를 복제)
    tbl_tmpl = _extract_table_template(blobs, section_names_hint=None)

    # 3) 본문 section 파일들 처리 (첫 섹션에만 콘텐츠 주입)
    section_names = sorted(n for n in blobs if n.startswith("Contents/section") and n.endswith(".xml"))
    blocks = mdblocks.parse(md)
    for idx, name in enumerate(section_names):
        blobs[name] = _rewrite_section(blobs[name], blocks if idx == 0 else [], style_map, tbl_tmpl)

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
                     style_map: Dict[str, Dict[str, str]], tbl_tmpl=None) -> bytes:
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
        if _is_divider(blk):
            continue
        if blk["type"] == "table":
            # 진짜 표(템플릿 복제). 실패하면 평탄화(불릿)로 폴백 → 문서는 무조건 나오게.
            if tbl_tmpl is not None and _REAL_TABLES:
                try:
                    root.append(_make_table(tbl_tmpl, blk, style_map))
                    continue
                except Exception as e:  # noqa: BLE001
                    print(f"[hwpx_export] 표 렌더 실패, 평탄화 폴백: {e}")
            for b in _table_to_blocks(blk):
                st = _style_for_block(b, style_map, normal)
                root.append(_make_para(b, st, emph, normal))
            continue
        st = _style_for_block(blk, style_map, normal)
        root.append(_make_para(blk, st, emph, normal))

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


# ── 진짜 표(테이블) 렌더링 — 템플릿의 기존 표를 복제해 행/열/텍스트만 교체 ──────────
_ID_SEQ = [2000000000]


def _next_id() -> str:
    _ID_SEQ[0] += 1
    return str(_ID_SEQ[0])


def _extract_table_template(blobs: Dict[str, bytes], section_names_hint=None):
    """템플릿 섹션에서 표를 감싼 단락(<hp:p>)을 1개 찾아 deepcopy 로 반환. 없으면 None.
    이 단락을 복제해 행/열/텍스트만 바꾸면 한글이 여는 표 구조를 그대로 재사용한다."""
    from lxml import etree
    ptag = f"{{{HP}}}p"
    tbltag = f"{{{HP}}}tbl"
    for name in sorted(n for n in blobs if n.startswith("Contents/section") and n.endswith(".xml")):
        try:
            root = etree.fromstring(blobs[name])
        except Exception:
            continue
        tbl = root.find(f".//{tbltag}")
        if tbl is None:
            continue
        p = tbl
        while p is not None and p.tag != ptag:
            p = p.getparent()
        if p is not None:
            return copy.deepcopy(p)
    return None


def _set_cell(tc, text: str, style: Optional[Dict[str, str]], col: int, row: int,
              width: int, height: int) -> None:
    """복제한 <hp:tc> 의 주소/크기/스타일/텍스트를 교체. linesegarray 는 제거(한글이 재계산)."""
    P = f"{{{HP}}}"
    ca = tc.find(f"{P}cellAddr")
    if ca is not None:
        ca.set("colAddr", str(col)); ca.set("rowAddr", str(row))
    cspan = tc.find(f"{P}cellSpan")
    if cspan is not None:
        cspan.set("colSpan", "1"); cspan.set("rowSpan", "1")
    csz = tc.find(f"{P}cellSz")
    if csz is not None:
        csz.set("width", str(width)); csz.set("height", str(height))
    # 레이아웃 캐시 제거 → 한글이 새 텍스트로 재배치
    for lsa in list(tc.iter(f"{P}linesegarray")):
        lsa.getparent().remove(lsa)
    sub = tc.find(f"{P}subList")
    cp = sub.find(f"{P}p") if sub is not None else None
    if cp is None:
        return
    cp.set("id", _next_id())
    if style:
        cp.set("styleIDRef", style["styleId"])
        cp.set("paraPrIDRef", style["paraPrIDRef"])
    runs = cp.findall(f"{P}run")
    for extra in runs[1:]:
        cp.remove(extra)
    run = runs[0] if runs else None
    if run is None:
        from lxml import etree
        run = etree.SubElement(cp, f"{P}run")
    if style:
        run.set("charPrIDRef", style["charPrIDRef"])
    ts = run.findall(f"{P}t")
    if ts:
        ts[0].text = text
        for extra in ts[1:]:
            run.remove(extra)
    else:
        from lxml import etree
        etree.SubElement(run, f"{P}t").text = text


def _make_table(tbl_tmpl, blk: Dict, style_map: Dict[str, Dict[str, str]]):
    """템플릿 표 단락(deepcopy 원본)을 복제해 blk(header/rows)로 채운 <hp:p> 반환."""
    P = f"{{{HP}}}"
    p = copy.deepcopy(tbl_tmpl)
    for lsa in list(p.iter(f"{P}linesegarray")):  # 표 단락 레이아웃 캐시 제거
        lsa.getparent().remove(lsa)
    tbl = p.find(f".//{P}tbl")
    if tbl is None:
        raise ValueError("표 템플릿에 <hp:tbl> 없음")

    rows_src = tbl.findall(f"{P}tr")
    if not rows_src:
        raise ValueError("표 템플릿에 <hp:tr> 없음")
    tc_tmpl = copy.deepcopy(rows_src[0].find(f"{P}tc"))
    tr_tmpl = copy.deepcopy(rows_src[0])
    for tc in tr_tmpl.findall(f"{P}tc"):
        tr_tmpl.remove(tc)
    for tr in rows_src:
        tbl.remove(tr)

    header = [str(c) for c in (blk.get("header") or [])]
    body = [[str(c) for c in r] for r in (blk.get("rows") or [])]
    ncol = blk.get("ncol") or len(header) or (max((len(r) for r in body), default=1))
    ncol = max(1, int(ncol))
    data = ([header] if header else []) + body
    if not data:
        raise ValueError("빈 표")
    nrow = len(data)

    total_w = 45354          # A4 본문 폭(약 160mm, HWPUNIT). noAdjust=0 이라 한글이 재조정.
    colw = max(900, total_w // ncol)
    rowh = 1400

    th = _pick(style_map, "표제목", "강조")
    bh = _pick(style_map, "표본문", "본문")

    tbl.set("rowCnt", str(nrow))
    tbl.set("colCnt", str(ncol))
    tbl.set("id", _next_id())
    sz = tbl.find(f"{P}sz")
    if sz is not None:
        sz.set("width", str(colw * ncol)); sz.set("height", str(rowh * nrow))

    for r, cells in enumerate(data):
        is_head = (r == 0 and bool(header))
        style = th if is_head else bh
        tr = copy.deepcopy(tr_tmpl)
        for c in range(ncol):
            tc = copy.deepcopy(tc_tmpl)
            txt = cells[c] if c < len(cells) else ""
            _set_cell(tc, txt, style, c, r, colw, rowh)
            tr.append(tc)
        tbl.append(tr)
    return p


_DIVIDER_RE = re.compile(r"\s*[-_*=—–]{3,}\s*")


def _is_divider(blk: Dict) -> bool:
    """마크다운 구분선(--- *** === 등)은 단락으로 찍지 않고 버린다."""
    if blk.get("type") not in ("para", "bullet"):
        return False
    t = (blk.get("text") or "").strip()
    return bool(t) and _DIVIDER_RE.fullmatch(t) is not None


def _style_for_block(blk: Dict, style_map, normal) -> Dict[str, str]:
    t = blk["type"]
    if t == "heading":
        lvl = min(max(blk["level"], 1), 3)
        return _pick(style_map, f"제목 {lvl}", "제목", f"Heading {lvl}") or normal
    if t == "bullet":
        # 1단계(-) → 동그라미(○), 2단계 이상(  -) → 마이너스(−). 없으면 목록/본문 폴백.
        lvl = blk.get("level", 1) or 1
        if lvl >= 2:
            return _pick(style_map, "마이너스", "목록") or normal
        return _pick(style_map, "동그라미", "목록") or normal
    if t == "quote":
        return _pick(style_map, "인용") or normal
    return normal


def _make_para(blk: Dict, st: Dict[str, str], emph, normal):
    from lxml import etree
    p = etree.Element(f"{{{HP}}}p")
    p.set("paraPrIDRef", st["paraPrIDRef"])
    p.set("styleIDRef", st["styleId"])
    # 글머리표(○/−)는 동그라미/마이너스 스타일의 문단모양에 내장 — 글자 접두를 넣지 않는다.
    prefix = ""
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
