"""근거 기반 워크플로 프롬프트 빌더 + 근거 컨텍스트 조립 (문서공방).

영상공방 services/vodstudio/enrich.py 를 이식하되, '영상 대본'이 아니라 '문서'에 맞춰
- 리서치 브리프에 **채워야 할 데이터 체크리스트** 섹션을 추가하고,
- 자동 검수에 **📝 채워야 할 항목([확인 필요])** 분류를 추가했다.

순수 함수(동기) 모음 — LLM 호출 자체는 pipeline 에서 한다.
근거 검색은 `evidence.search`(naive, 외부 서비스 불필요)만 호출한다.
→ 다음 단계에서 임베딩 리트리버를 끼워넣어도 이 모듈은 그대로다.

build_* 는 명령줄 길이/토큰 한계를 넘지 않도록 컨텍스트를 max_chars 로 제한한다.
"""
from __future__ import annotations

import re
from typing import List, Optional

from . import evidence


# ── 문서 분할/질의 ───────────────────────────────────────────────────
def doc_sections(md_text: str, *, per_chars: int = 4000) -> List[str]:
    """마크다운을 상위 헤딩 경계로 나눠 ~per_chars 크기로 묶는다.

    검수 반영(수정)을 묶음 단위로 처리해 출력 토큰 한계(잘림)를 피하기 위함.
    헤딩이 없으면 통째로 한 덩어리.
    """
    t = (md_text or "").strip()
    if not t:
        return []
    blocks = [b.strip() for b in re.split(r"(?=^#{1,3}\s)", t, flags=re.MULTILINE) if b.strip()]
    if len(blocks) <= 1:
        return [t]
    groups: List[str] = []
    buf = ""
    for b in blocks:
        if buf and len(buf) + len(b) + 2 > per_chars:
            groups.append(buf)
            buf = b
        else:
            buf = (buf + "\n\n" + b).strip()
    if buf:
        groups.append(buf)
    return groups


def review_queries(doc_md: str, *, n: int = 8) -> List[str]:
    """문서 전체를 골고루 덮는 근거 질의 목록(문서에서 직접 추출).

    앞부분만 보던 방식과 달리 문서를 여러 구간으로 나눠 각 구간을 질의로 써서
    근거 검색이 자료 전체를 훑게 한다 → '근거에 없음' 오탐 방지.
    """
    t = (doc_md or "").strip()
    if not t:
        return []
    blocks = [b.strip() for b in re.split(r"(?=^#{1,3}\s)", t, flags=re.MULTILINE) if b.strip()]
    if len(blocks) < 2:
        size = max(1, len(t) // n)
        blocks = [t[i:i + size] for i in range(0, len(t), size)]
    if len(blocks) > n:
        step = len(blocks) / n
        blocks = [blocks[int(i * step)] for i in range(n)]
    return [b[:400] for b in blocks if b.strip()]


def auto_queries(recipe_name: str, instruction: str, sources: List[str]) -> List[str]:
    """레시피명/지시/파일명 + 일반 facet 으로 다면 질의를 만든다(특정 도메인 하드코딩 없음)."""
    facets = ["배경 목적", "추진 경과 일정", "성과 결과", "수치 예산 지표", "현황 문제점", "향후 계획 과제"]
    qs: List[str] = [recipe_name]
    if (instruction or "").strip():
        qs.append(instruction.strip()[:200])
    qs += [f"{recipe_name} {f}" for f in facets]
    qs += [s for s in (sources or []) if s][:5]
    return [q for q in qs if (q or "").strip()]


def gather_context(job_id: str, queries: List[str], *, k: int = 6,
                   max_chars: int = 18000, role: Optional[str] = None) -> str:
    """여러 질의로 근거 검색 → 중복 제거 → max_chars 까지 모은 근거 텍스트."""
    seen = set()
    picked: List[str] = []
    total = 0
    pools = [evidence.search(job_id, q, k=k, role=role)
             for q in queries if (q or "").strip()]
    i = 0
    while pools and total < max_chars:
        progressed = False
        for pool in pools:
            if i < len(pool):
                progressed = True
                h = pool[i]
                key = h["text"][:60]
                if key in seen:
                    continue
                seen.add(key)
                block = f"[{h['source']}]\n{h['text']}"
                if total + len(block) > max_chars:
                    continue
                picked.append(block)
                total += len(block)
        if not progressed:
            break
        i += 1
    return "\n\n---\n".join(picked)


# ── 프롬프트 빌더 ────────────────────────────────────────────────────
def build_research_prompt(topic: str, context: str) -> str:
    """딥리서치(자료 심층분석) — 쟁점 분해 + 채워야 할 데이터 점검 브리프 생성."""
    return (
        "당신은 문서 작성 리서처입니다. 아래 [자료]만 근거로, 이 문서의 설계도가 될 "
        "'리서치 브리프'를 한국어로 작성하세요. 인터넷 지식이 아니라 자료에 있는 내용만 씁니다.\n\n"
        f"## 주제\n{topic}\n\n"
        "## 출력 형식 (반드시 따르기)\n"
        "1) 핵심 쟁점 6~10개 (한 줄씩, 자료 근거 키워드/항목 표기)\n"
        "2) 논리적 흐름 제안 (도입 → 본론 단계 → 마무리)\n"
        "3) 주의·오해하기 쉬운 점 3~5개\n"
        "4) 꼭 다뤄야 할 정의/용어 목록\n"
        "5) ★채워야 할 데이터 체크리스트 — 문서 완성에 필요하나 [자료]에서 "
        "확인되지 않는 수치·일정·인명·기관명·금액을 '[확인 필요: …]' 형식으로 나열\n\n"
        f"## 자료\n{context}\n"
    )


def build_review_prompt(doc_md: str, context: str) -> str:
    """자동 검수 — 근거 대비 부정확/과장/누락 + 채워야 할 항목 점검."""
    return (
        "당신은 문서 감수자입니다. 아래 [문서]를 [근거 자료]와 대조해 "
        "문제를 한국어로 점검하세요. 근거에 없는 주장, 사실과 다른 서술, 과장, 누락된 중요 항목을 찾습니다.\n\n"
        "## 중요 원칙\n"
        "- [근거 자료]는 전체의 '발췌'입니다. 발췌에서 확인되는 수치·서술은 정확한 것으로 인정하세요.\n"
        "- 발췌에 없다는 이유만으로 곧장 🔴로 단정하지 말고, 명백히 자료와 어긋날 때만 🔴로 표시하세요.\n"
        "- 이 문서는 '초안'입니다. 빠진 데이터는 작성자가 회의 전에 채워야 하니 명확히 짚어주세요.\n\n"
        "## 출력 형식\n"
        "- 🔴 부정확/근거없음: (위치/소제목 — 문제 — 올바른 내용)\n"
        "- 🟡 과장/모호: (위치/소제목 — 문제 — 수정 제안)\n"
        "- 🟢 누락(자료엔 있는데 문서에 빠짐): (항목 — 어디에 넣으면 좋을지)\n"
        "- 📝 채워야 할 항목: 문서에 남은 '[확인 필요]' 및 근거가 없어 못 채운 데이터(수치·일정·인명·금액 등) 목록\n"
        "- 한 줄 총평\n"
        "문제가 없으면 '발견된 문제 없음'이라고 쓰세요.\n\n"
        f"## 문서\n{doc_md[:30000]}\n\n"
        f"## 근거 자료\n{context}\n"
    )


def build_revise_prompt(doc_md: str, review_report: str, context: str = "") -> str:
    """검수 결과를 반영해 문서를 다듬어 **같은 형식 그대로 재출력**.

    문서 구간(헤딩) 단위로 호출되므로 doc_md 는 일부일 수 있다.
    """
    ctx_block = f"\n## 근거 자료(사실 확인용 발췌)\n{context}\n" if context.strip() else ""
    return (
        "당신은 문서 에디터입니다. 아래 [문서]를 [검수 결과]에 따라 수정해 "
        "**문서 전체를 같은 형식(Markdown) 그대로 다시 출력**하세요. 설명·머리말 없이 문서 본문만 출력합니다.\n\n"
        "## 수정 규칙 (반드시 지킬 것)\n"
        "1) 🟡(과장/모호) 지적은 모두 반영해 표현을 사실에 맞게 완화·명확화한다.\n"
        "2) 🟢(누락) 지적 중 자연스러운 것은 해당 위치에 한 줄만 보강한다(분량 과다 금지).\n"
        "3) 🔴(근거없음)으로 표시된 수치라도 함부로 지우지 말 것 — 근거가 발췌라 생긴 오탐일 수 있다. "
        "근거 자료에서 확인되거나 일반적으로 타당하면 유지하고, 정말 자료와 어긋날 때만 고친다.\n"
        "4) 📝(채워야 할 항목)에서 자료로 확인되지 않는 값은 임의로 채우지 말고 '[확인 필요: …]' 표기를 그대로 둔다.\n"
        "5) 지적되지 않은 문장·수치·구조·소제목·형식은 그대로 유지한다(임의 재작성 금지).\n"
        "6) 받은 구간만, 받은 순서·구조 그대로 출력한다.\n\n"
        f"## 검수 결과\n{review_report[:6000]}\n"
        f"{ctx_block}"
        f"\n## 문서\n{doc_md[:16000]}\n"
    )
