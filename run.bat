@echo off
REM ASCII-only on purpose: non-ASCII in a .bat can break on CP949 consoles.
REM Flat structure (single-line IFs + GOTO, no nested () blocks, no self-relaunch)
REM so it can never mis-parse into an infinite loop.
cd /d "%~dp0"
set "PORT=7001"

if not exist "venv\Scripts\python.exe" goto :noinstall

REM Check OpenAI Codex CLI (codex) - needed for LLM calls (no API key).
set "CODEX_OK="
where codex >nul 2>nul && set "CODEX_OK=1"
if not defined CODEX_OK if exist "%APPDATA%\npm\codex.cmd" set "CODEX_OK=1"
if not defined CODEX_OK echo [NOTE] codex not found. Run setup.bat again, or: npm i -g @openai/codex  then  codex login

echo ============================================================
echo   Local Report Writer - running
echo   URL: http://127.0.0.1:%PORT%   (sign in, then go to /studio)
echo   Close this black window to stop.  (Ctrl+C also stops)
echo ============================================================
echo.

REM Open the browser ~3s after start (give the server time to boot)
start "" /b cmd /c "timeout /t 3 >nul & start "" http://127.0.0.1:%PORT%/"

venv\Scripts\python -m uvicorn app:app --host 0.0.0.0 --port %PORT%

echo.
echo Server stopped.
pause
goto :eof

:noinstall
echo [NOTE] Not installed yet. Please double-click setup.bat first.
pause
