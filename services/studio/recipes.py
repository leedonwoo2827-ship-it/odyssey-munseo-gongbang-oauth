"""레시피 카탈로그 — knowledge/recipes/*.yaml 로딩/검증.

레시피 1개 = 산출물 1종 정의 (= 스튜디오의 버튼 1개).

스키마 예시:
  id: pmc-10th-visit-result          # 파일명과 무관한 고유 id (kebab-case)
  name: "PMC 10차 방문결과"           # 버튼에 표시될 이름
  category: "방문결과"                # 버튼 그룹
  description: "9차 결과를 토대로 10차 방문결과 보고서 초안 생성"
  model: claude-sonnet-4-6           # (선택) 모델 override
  output:
    format: hwpx                     # hwpx|docx|pptx|xlsx|md
    template: hwpx_template.hwpx     # (선택) 회사 양식. 없으면 내장 기본
    filename: "PMC_10차_방문결과_{date}"   # 확장자는 format 으로 자동
  inputs:                            # C열 이후 입력 정의 (없어도 됨)
    - { key: inputA, label: "9차 방문결과최종본", required: true,  accept: [docx, hwpx, pdf] }
    - { key: inputB, label: "협력 현황표",         required: false, accept: [xlsx, docx] }
  prompt: |
    당신은 해외 ODA 사업 PMC 문서 작성 전문가입니다.
    아래 입력을 바탕으로 'PMC 10차 방문결과' 보고서를 한국어로 작성하세요.
    {{inputs}}            # 모든 입력이 라벨과 함께 자동 주입되는 자리
    {{instruction}}       # 사용자가 생성 전 채팅으로 준 추가 지시
"""
from __future__ import annotations

import os
from typing import Any, Dict, List, Optional

from . import config

ALLOWED_FORMATS = {"hwpx", "docx", "pptx", "xlsx", "md", "mckinsey", "design"}


class RecipeError(Exception):
    pass


def _slug_from_path(path: str) -> str:
    return os.path.splitext(os.path.basename(path))[0]


def _normalize(raw: Dict[str, Any], src: str) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise RecipeError(f"{src}: 최상위가 매핑(dict)이 아닙니다")

    rid = str(raw.get("id") or _slug_from_path(src)).strip()
    name = str(raw.get("name") or rid).strip()
    out = raw.get("output") or {}
    if not isinstance(out, dict):
        raise RecipeError(f"{src}: output 은 매핑이어야 합니다")
    fmt = str(out.get("format", "md")).lower().strip()
    if fmt not in ALLOWED_FORMATS:
        raise RecipeError(f"{src}: 지원하지 않는 출력 형식 '{fmt}' (가능: {sorted(ALLOWED_FORMATS)})")

    # 'mckinsey'/'design' 은 별칭: 파일 확장자는 pptx, 전용 mode 로 렌더.
    forced_mode = None
    if fmt == "mckinsey":
        fmt = "pptx"
        forced_mode = "mckinsey_deck"
    elif fmt == "design":
        fmt = "pptx"
        forced_mode = "design_deck"

    # mode 는 format 에서 추론(override 가능): pptx→slides, xlsx→table, 그 외→report
    mode = str(out.get("mode") or forced_mode
               or ("slides" if fmt == "pptx" else "table" if fmt == "xlsx" else "report")).lower()

    # workflow: 근거 기반 5단계 노출 여부(레시피 종류별 자동, 레시피에서 override 가능).
    #   full   = 보고서/발표자료/계획서류(hwpx/docx/pptx) → 5단계 스트립 자동 표시
    #   simple = 단순 양식/표(xlsx, md)            → 기존 '한 번에 생성'만
    workflow = str(raw.get("workflow") or "").lower().strip()
    if workflow not in ("full", "simple"):
        workflow = "full" if fmt in ("hwpx", "docx", "pptx") else "simple"

    inputs: List[Dict[str, Any]] = []
    for i, item in enumerate(raw.get("inputs") or []):
        if not isinstance(item, dict):
            raise RecipeError(f"{src}: inputs[{i}] 가 매핑이 아닙니다")
        key = str(item.get("key") or f"input{i+1}")
        accept = item.get("accept") or ["docx", "hwpx", "pdf", "xlsx", "pptx", "txt", "md"]
        accept = [str(a).lower().lstrip(".") for a in accept]
        inputs.append({
            "key": key,
            "label": str(item.get("label") or key),
            "required": bool(item.get("required", False)),
            "accept": accept,
        })

    return {
        "id": rid,
        "name": name,
        "category": str(raw.get("category") or "기타"),
        "description": str(raw.get("description") or ""),
        "workflow": workflow,
        "model": raw.get("model") or None,
        "output": {
            "format": fmt,
            "mode": mode,
            "template": out.get("template") or None,
            "filename": out.get("filename") or rid,
        },
        "inputs": inputs,
        "prompt": str(raw.get("prompt") or "").strip(),
        "_source": src,
    }


def load_all() -> List[Dict[str, Any]]:
    """knowledge/recipes/*.yaml 전부 로드. 깨진 파일은 건너뛰되 콘솔에 경고."""
    import yaml  # 지연 import (의존성 미설치 환경에서도 모듈 import 자체는 가능하게)

    config.ensure_dirs()
    recipes: List[Dict[str, Any]] = []
    if not os.path.isdir(config.RECIPES_DIR):
        return recipes
    for fn in sorted(os.listdir(config.RECIPES_DIR)):
        if fn.startswith("_") or not fn.lower().endswith((".yaml", ".yml")):
            continue
        path = os.path.join(config.RECIPES_DIR, fn)
        try:
            with open(path, "r", encoding="utf-8") as f:
                raw = yaml.safe_load(f)
            recipes.append(_normalize(raw, path))
        except Exception as e:  # 한 파일 오류가 전체 카탈로그를 막지 않도록
            print(f"[studio] 레시피 로드 실패 {fn}: {e}")
    return recipes


def get(recipe_id: str) -> Optional[Dict[str, Any]]:
    for r in load_all():
        if r["id"] == recipe_id:
            return r
    return None


def save_from_form(data: Dict[str, Any]) -> Dict[str, Any]:
    """앱 내 폼 빌더용 — 레시피 dict 를 YAML 파일로 저장(2차 기능)."""
    import re
    import yaml

    config.ensure_dirs()
    rid = str(data.get("id") or data.get("name") or "untitled").strip()
    rid = re.sub(r"[^0-9A-Za-z가-힣_-]+", "-", rid).strip("-") or "untitled"
    normalized = _normalize({**data, "id": rid}, f"<form:{rid}>")
    normalized.pop("_source", None)
    path = os.path.join(config.RECIPES_DIR, f"{rid}.yaml")
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(normalized, f, allow_unicode=True, sort_keys=False)
    return {"id": rid, "path": path}
