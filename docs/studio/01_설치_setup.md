# 01 · 설치 (setup.bat)

## 준비물
- **Python 3.11~3.13** ([python.org](https://www.python.org/downloads/)). 설치 시 **"Add Python to PATH"** 체크 필수.
- **사내망/VPN** 연결 (liteLLM 프록시 접근).
- (선택) HWPX 네이티브 생성을 원하면 **한컴 한글** 설치.

## 설치 방법 — `setup.bat` 더블클릭
탐색기에서 `setup.bat` 을 더블클릭하면 검은 창이 뜨고 자동으로 진행됩니다.

`setup.bat` 이 하는 일(순서대로):
1. Python 확인 (`py` 또는 `python`).
2. 가상환경 `venv\` 생성. (프로젝트만의 독립 공간 — PC 전체에 영향 없음)
3. 라이브러리 설치 (`pip install -r requirements.txt`). **처음엔 몇 분** 걸립니다.
4. 최초 설정(`setup.py`) — 데이터 폴더/DB 초기화. (질문 없이 진행)
5. liteLLM 프록시 환경변수(`UBION_LITELLM_URL`, `UBION_LITELLM_KEY`) 등록.
6. 프록시 연결 점검(`sanity-check.py`).

마지막에 **"설치 완료!"** 가 보이면 성공입니다. 창은 아무 키나 누르면 닫힙니다.

## 정상 동작 확인 포인트
- "라이브러리 설치" 단계에서 빨간 오류 없이 끝났는가.
- "프록시 연결 점검"에서 성공 메시지가 보였는가. (실패해도 설치는 완료 — [07 FAQ](07_문제해결_FAQ.md) 참고)

## 다시 실행해도 안전
`setup.bat` 은 여러 번 눌러도 됩니다. 이미 만들어진 것은 건너뛰고, 라이브러리만 최신으로 맞춥니다.

## 자주 나는 문제
- **"Python 3.11 이상이 필요합니다"** → Python 미설치 또는 PATH 누락. 재설치 시 PATH 체크.
- **설치가 느리다/멈춘 듯하다** → 첫 설치는 수 분 정상. 네트워크 상태 확인.
- **프록시 점검 실패** → VPN 연결, `.env` 의 `UBION_LITELLM_KEY` 확인. → [06 문서](06_liteLLM_연결과_모델.md)

설치가 끝나면 → [02 · 실행](02_실행_run.md)
