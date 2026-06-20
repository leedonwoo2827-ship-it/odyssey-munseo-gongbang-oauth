"""근거 저장/검색 — 외부 서비스·임베딩 없이 동작하는 naive 리트리버 (문서공방).

설계 의도:
- 자료학습/검수 워크플로의 '근거 검색'은 오직 `evidence.search(...)`만 호출한다.
  → 다음 단계에서 임베딩 리트리버(`EmbeddingRetriever`)를 `set_retriever()`로 끼워넣으면
    UI/엔드포인트/`enrich.gather_context` 변경 없이 그대로 RAG 로 확장된다.
- 오늘(Phase A)은 fastembed/ChromaDB 미설치 머신에서도 동작해야 하므로,
  한국어 토큰(글자 2-그램) 겹침 기반의 가벼운 점수 검색을 쓴다.

근거 채널(role):
- "data"  : 이번에 첨부된 입력 파일 → 사실·수치·본문 내용의 근거
- "style" : 지난 산출물(과거 완성 문서) → 톤·문체·완성도 앵커

저장: 잡(job)별로 data/studio/evidence/<job_id>/chunks.json
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from . import config

_CHUNKS_NAME = "chunks.json"


def _job_dir(job_id: str) -> str:
    return os.path.join(config.EVIDENCE_DIR, job_id)


# ── 청킹 ─────────────────────────────────────────────────────────────
def chunk_text(text: str, *, target_chars: int = 1100, overlap: int = 150) -> List[str]:
    """마크다운 헤딩/조문/문단 경계를 존중하며 ~target_chars 크기로 자른다.

    영상공방 local_rag.chunk_text 를 이식하되, 보고서/제안서가 많은 문서공방 특성상
    마크다운 헤딩(#, ##, ###) 경계도 우선 분할 대상에 포함한다.
    """
    text = (text or "").replace("\r\n", "\n").strip()
    if not text:
        return []
    # 1) 헤딩/조문 경계 우선 분할(경계 토큰 보존)
    parts = re.split(r"(?=(?:^|\n)\s*(?:#{1,3}\s|제\s*\d+\s*조(?:의\s*\d+)?))", text)
    parts = [p.strip() for p in parts if p and p.strip()]
    if len(parts) <= 1:
        # 헤딩/조문 형식이 아니면 빈 줄/문단 기준
        parts = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: List[str] = []
    buf = ""
    for p in parts:
        if len(buf) + len(p) + 1 <= target_chars:
            buf = (buf + "\n" + p).strip()
        else:
            if buf:
                chunks.append(buf)
            if len(p) <= target_chars:
                buf = p
            else:
                i = 0
                while i < len(p):
                    chunks.append(p[i:i + target_chars])
                    i += max(1, target_chars - overlap)
                buf = ""
    if buf:
        chunks.append(buf)
    return chunks


# ── 색인(저장) ───────────────────────────────────────────────────────
def build_index(job_id: str, sources: List[Tuple[str, str, str]],
                *, target_chars: int = 1100, overlap: int = 150) -> Dict[str, Any]:
    """sources=[(파일명, 텍스트, role), ...] 를 청킹해 잡 폴더에 저장.

    role 은 "data"|"style". 반환: {chunks, sources:[{name,role,chunks}]}.
    """
    all_chunks: List[Dict[str, Any]] = []
    per_source: List[Dict[str, Any]] = []
    for name, text, role in sources:
        cs = chunk_text(text, target_chars=target_chars, overlap=overlap)
        for c in cs:
            all_chunks.append({"text": c, "source": name, "role": role or "data"})
        per_source.append({"name": name, "role": role or "data", "chunks": len(cs)})
    if not all_chunks:
        raise ValueError("색인할 텍스트가 없습니다.")
    job = _job_dir(job_id)
    os.makedirs(job, exist_ok=True)
    with open(os.path.join(job, _CHUNKS_NAME), "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, ensure_ascii=False)
    return {"chunks": len(all_chunks), "sources": per_source}


def load_chunks(job_id: str) -> Optional[List[Dict[str, Any]]]:
    p = os.path.join(_job_dir(job_id), _CHUNKS_NAME)
    if not os.path.exists(p):
        return None
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def index_status(job_id: str) -> Dict[str, Any]:
    chunks = load_chunks(job_id)
    if not chunks:
        return {"indexed": False, "chunks": 0, "sources": [],
                "retriever": get_retriever().name}
    srcs: Dict[str, Dict[str, Any]] = {}
    for c in chunks:
        s = srcs.setdefault(c["source"], {"name": c["source"],
                                          "role": c.get("role", "data"), "chunks": 0})
        s["chunks"] += 1
    return {"indexed": True, "chunks": len(chunks),
            "sources": list(srcs.values()), "retriever": get_retriever().name}


# ── 검색(naive) ──────────────────────────────────────────────────────
def _tokens(s: str) -> List[str]:
    """한국어(글자 2-그램) + 영문/숫자(단어) 토큰. 형태소 분석기 없이 견고하게."""
    s = (s or "").lower()
    toks: List[str] = re.findall(r"[a-z0-9]+", s)
    for run in re.findall(r"[가-힣]+", s):
        if len(run) == 1:
            toks.append(run)
        else:
            toks += [run[i:i + 2] for i in range(len(run) - 1)]
    return toks


class NaiveRetriever:
    """토큰 겹침 점수 기반 검색. 임베딩/외부 서비스 불필요."""
    name = "naive"

    def search(self, job_id: str, query: str, k: int = 6,
               role: Optional[str] = None) -> List[Dict[str, Any]]:
        chunks = load_chunks(job_id) or []
        if role:
            chunks = [c for c in chunks if c.get("role", "data") == role]
        qset = set(_tokens(query))
        if not qset or not chunks:
            return []
        scored: List[Tuple[float, Dict[str, Any]]] = []
        for c in chunks:
            cset = set(_tokens(c["text"]))
            if not cset:
                continue
            inter = len(qset & cset)
            if not inter:
                continue
            # 질의 커버리지 위주 + 청크 길이에 약한 패널티(긴 청크 과대평가 방지)
            score = inter / (len(qset) ** 0.5) / (1 + len(cset) / 600.0)
            scored.append((score, c))
        scored.sort(key=lambda x: -x[0])
        return [{"text": c["text"], "source": c["source"],
                 "role": c.get("role", "data"), "score": float(s)}
                for s, c in scored[:max(1, k)]]


_RETRIEVER: Any = NaiveRetriever()


def set_retriever(retriever: Any) -> None:
    """리트리버 교체 시임 — 다음 단계에서 임베딩 리트리버를 끼워넣을 자리."""
    global _RETRIEVER
    _RETRIEVER = retriever


def get_retriever() -> Any:
    return _RETRIEVER


def search(job_id: str, query: str, k: int = 6,
           role: Optional[str] = None) -> List[Dict[str, Any]]:
    return _RETRIEVER.search(job_id, query, k=k, role=role)
