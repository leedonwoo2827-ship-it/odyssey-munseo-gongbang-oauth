# knowledge/recipes/ — 산출물 레시피 카탈로그

이 폴더의 **YAML 파일 1개 = 산출물 유형 1개 = 스튜디오 화면의 버튼 1개**입니다.
엑셀 목록표의 16종이 시드로 들어 있고, **파일을 복사·수정**해서 90여 종까지 늘리면 됩니다.

## 새 유형 추가하는 가장 쉬운 방법
1. 비슷한 기존 `.yaml` 을 복사해 새 이름으로 저장 (예: `17-새보고서.yaml`).
2. 아래 항목만 고친다 → 저장 → 스튜디오 새로고침하면 버튼이 생깁니다.

```yaml
id: 17-새보고서                 # 고유 id (파일명과 같게 권장)
name: 새 보고서                 # 버튼에 보일 이름
category: 보고서                # 버튼 묶음(그룹)
description: 무엇을 만드는지 한 줄 설명
model: claude-sonnet-4-6        # (선택) 모델 지정. 비우면 기본값
output:
  format: hwpx                  # hwpx | docx | pptx | xlsx | md
  template: hwpx_template.hwpx  # (선택) assets/ 의 회사 양식
  filename: 새보고서_{date}      # 확장자는 format 으로 자동, {date}=오늘
inputs:                         # 필요한 입력 문서들 (없어도 됨)
  - { key: inputA, label: "이전 차수 보고서", required: true,  accept: [docx, hwpx, pdf] }
  - { key: inputB, label: "현황표",           required: false, accept: [xlsx] }
prompt: |
  당신은 ... 전문가입니다. 아래 자료로 '새 보고서'를 한국어로 작성하세요.
  {{inputs}}        # 업로드한 입력들이 라벨과 함께 자동으로 들어가는 자리
  {{instruction}}   # 생성 화면에서 사용자가 채팅으로 준 추가 지시가 들어가는 자리
```

## 규칙
- `format` 이 `pptx` 면 슬라이드(제목+부제+불릿), `xlsx` 면 표(JSON) 로 생성됩니다.
- `{{inputs}}`, `{{instruction}}` 자리표시자는 자동 치환됩니다(없으면 끝에 덧붙임).
- `_` 로 시작하는 파일(이 README, 생성 스크립트)은 레시피로 읽지 않습니다.

## 엑셀에서 한 번에 다시 만들기
```
python knowledge/recipes/_generate_from_xlsx.py
```
이미 있는 `.yaml` 은 보존하고, 없는 항목만 새로 만듭니다(손본 내용 안전).

자세한 안내: [docs/studio/04_레시피_추가하기.md](../../docs/studio/04_레시피_추가하기.md)
