# McKinsey식 마켓리포트 덱 — 스튜디오 통합 메모

영상(Copilot) 워크플로의 McKinsey 덱(템플릿 A/B 복제 + 네이티브 차트)을 스튜디오 레시피로 통합한 내역.
일반 pptx(제목+불릿)와 달리, LLM 이 낸 **구조화된 deck spec(JSON)** 을 받아 박스 안에 네이티브 차트/표/KPI 를 그린다.

## 흐름
```
[/studio "McKinsey식 마켓리포트 덱" 버튼] → 토픽/참고자료
  → pipeline._build_prompt (mckinsey_deck 모드 → deck-spec JSON 스키마 주입)
  → llm.generate_json (OAuth: agy/codex)         ← LLM 이 deck spec JSON 반환
  → generators.render("pptx", spec, …, mode="mckinsey_deck")
  → mckinsey_pptx_gen.render (템플릿 A/B 복제 + add_chart/표/KPI)
  → .pptx
```

## 추가/수정 파일
- **추가** `services/studio/generators/mckinsey_pptx_gen.py` — deck spec → 네이티브 차트 pptx 렌더러.
- `services/studio/recipes.py` — `ALLOWED_FORMATS` 에 `mckinsey` 추가. `format: mckinsey` 는 별칭으로
  확장자 `pptx` + `mode: mckinsey_deck` 로 정규화.
- `services/studio/generators/__init__.py` — `render(..., mode=None)`; `pptx`+`mckinsey_deck` → 새 렌더러로 분기.
- `services/studio/pipeline.py` — `_build_prompt` 에 `mckinsey_deck` 스키마 분기,
  `_generate_content`/`_run_refine` 의 JSON 모드 집합에 `mckinsey_deck` 포함(토큰 12k),
  `_render_outputs` 가 `generators.render` 에 `mode` 전달.
- **추가** `knowledge/recipes/17-mckinsey-deck.yaml` — `output.format: mckinsey`, `template: mckinsey_template.pptx`.
- **추가** `assets/mckinsey_template.pptx` — 영상 brandlogy 템플릿(슬라이드1=A, 2=B). 회사화 시 교체.

## deck spec(JSON) 스키마
`mckinsey_pptx_gen.py` 상단 docstring 참조. 핵심: `slides[].template`(A/B), `slides[].boxes[].kind`
(`column|bar|line|doughnut|table|kpi`)에 맞는 데이터 필드 + `header/unit/insight/source`.

## 회사화
- 템플릿: `assets/mckinsey_template.pptx` 를 회사 로고/색/폰트본으로 교체(로고·푸터는 슬라이드마스터).
- 렌더러 색/폰트: `mckinsey_pptx_gen.py` 상단 `FONT`, `BLUE_L1` 등 상수.
- 자세한 절차: 준비 저장소 `../../docs/03-회사-템플릿-만드는법.md`(루트 260614-report-gongbang).

## 남은 환경 의존(코드 아님)
LLM 호출은 OAuth 로그인(`agy`=Gemini 또는 `codex`=ChatGPT)이 되어 있어야 동작.
`setup.bat` 으로 CLI 설치 후 로그인 페이지에서 로그인. 폰트 Pretendard 미설치 시 자동 대체.
