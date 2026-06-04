@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   문서 생산 스튜디오 (AIM N팀) - 설치 setup
echo ============================================================
echo.

REM 1) Python 3.11+ 확인 (py 런처 우선)
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY ( where python >nul 2>nul && set "PY=python" )
if not defined PY (
  echo [오류] Python 3.11 이상이 필요합니다.
  echo        https://www.python.org/downloads/ 에서 설치 후 다시 실행하세요.
  echo        설치 시 "Add Python to PATH" 체크를 꼭 해주세요.
  pause & exit /b 1
)
echo [확인] Python 사용: %PY%

REM 2) 가상환경 생성
if not exist "venv\Scripts\python.exe" (
  echo [1/3] 가상환경 venv 생성 중...
  %PY% -m venv venv
  if errorlevel 1 ( echo [오류] 가상환경 생성 실패 & pause & exit /b 1 )
) else (
  echo [1/3] 가상환경 이미 있음 - 건너뜀
)
set "VPY=venv\Scripts\python.exe"

REM 3) 라이브러리 설치
echo [2/3] 라이브러리 설치 중... 처음엔 몇 분 걸립니다
"%VPY%" -m pip install --upgrade pip
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 (
  echo [오류] 라이브러리 설치 실패. 위 빨간 메시지를 확인하세요.
  pause & exit /b 1
)

REM 4) 최초 설정 - 데이터 폴더 / DB 초기화 (프롬프트 없이)
echo [3/3] 최초 설정 - 데이터 폴더/DB 초기화...
set "ODYSSEUS_SKIP_ADMIN_PROMPT=1"
"%VPY%" setup.py

echo.
echo ============================================================
echo   설치 완료!  이제 run.bat 을 더블클릭하세요.
echo.
echo   * 회사 liteLLM 주소와 API 키는 실행 후 화면의
echo     '연결 설정' 창에서 입력하면 됩니다. 자동으로 뜹니다.
echo ============================================================
pause
