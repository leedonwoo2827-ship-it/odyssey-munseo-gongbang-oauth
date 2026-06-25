@echo off
REM ASCII-only on purpose: Korean text in a .bat breaks on CP949 consoles.
REM Keep the window open even when double-clicked, so output/errors stay visible.
if not defined _ODY_KEEPOPEN (
  set "_ODY_KEEPOPEN=1"
  cmd /k ""%~f0""
  exit /b
)
cd /d "%~dp0"

REM Port for this instance. Change here if it conflicts with another app.
set "PORT=7001"

if not exist "venv\Scripts\python.exe" (
  echo [NOTE] Not installed yet. Please double-click setup.bat first.
  pause & exit /b 1
)

REM Check OpenAI Codex CLI (codex) — needed for LLM calls (no API key).
where codex >nul 2>nul
if errorlevel 1 (
  if not exist "%APPDATA%\npm\codex.cmd" (
    echo [NOTE] codex ^(OpenAI Codex CLI^) not found.
    echo        Run setup.bat again, or:  npm i -g @openai/codex   then   codex login
    echo        You can also open the login page and use the [Login] button.
  )
)

echo ============================================================
echo   Odyssey Studio - running
echo   URL: http://127.0.0.1:%PORT%   (sign in, then /studio)
echo   (Close this black window to stop. Stop: Ctrl+C)
echo ============================================================
echo.

REM Open the browser ~3s after start (give the server time to boot)
start "" /b cmd /c "timeout /t 3 >nul & start "" http://127.0.0.1:%PORT%/"

venv\Scripts\python -m uvicorn app:app --host 0.0.0.0 --port %PORT%

echo.
echo Server stopped.
pause
