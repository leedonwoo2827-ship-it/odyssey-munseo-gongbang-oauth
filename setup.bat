@echo off
REM ASCII-only on purpose: non-ASCII in a .bat can break on CP949 consoles.
REM Flat structure (single-line IFs + GOTO, no nested () blocks, no self-relaunch).
cd /d "%~dp0"
set "LOG=%~dp0setup_log.txt"
echo setup start > "%LOG%"

echo ============================================================
echo   Local Report Writer (AIM) - SETUP
echo ============================================================
echo.

REM 1) Python (prefer the py launcher)
set "PY="
where py >nul 2>nul && set "PY=py -3"
if not defined PY where python >nul 2>nul && set "PY=python"
if not defined PY goto :nopy
echo [1/3] Python: %PY%

REM 2) Virtual environment
if not exist "venv\Scripts\python.exe" %PY% -m venv venv
set "VPY=venv\Scripts\python.exe"
if not exist "%VPY%" goto :novenv
echo [1/3] venv ready

REM 3) Libraries
echo [2/3] Installing libraries ... (first time takes a few minutes)
"%VPY%" -m pip install --upgrade pip
"%VPY%" -m pip install -r requirements.txt
if errorlevel 1 goto :pipfail
echo [2/3] libraries ready

REM 4) OpenAI Codex CLI (codex) - LLM backend (no API key), best effort via npm
echo [3/3] Checking OpenAI Codex CLI (codex) ...
set "CODEX_OK="
where codex >nul 2>nul && set "CODEX_OK=1"
if not defined CODEX_OK where npm >nul 2>nul && cmd /c npm i -g @openai/codex
where codex >nul 2>nul && set "CODEX_OK=1"
if not defined CODEX_OK if exist "%APPDATA%\npm\codex.cmd" set "CODEX_OK=1"
if defined CODEX_OK echo       [OK] codex available
if not defined CODEX_OK echo       [NOTE] codex not installed - install Node.js then run: npm i -g @openai/codex  (see docs\openai-codex\install.md)

REM 5) First-time setup - data dirs / DB (no prompt)
set "ODYSSEUS_SKIP_ADMIN_PROMPT=1"
"%VPY%" setup.py

echo.
echo ============================================================
echo   SETUP COMPLETE.  Next: double-click run.bat
echo.
echo   Sign in once with ChatGPT: on the login page click [Login]
echo   (it runs: codex login) and sign in in the browser. No API key.
echo ============================================================
echo.
echo (log: setup_log.txt)
pause
goto :eof

:nopy
echo [ERROR] Python 3.11+ required. Install from https://www.python.org/downloads/
echo         Tick "Add Python to PATH" during install, then re-run.
pause
goto :eof

:novenv
echo [ERROR] venv creation failed. Reinstall Python and retry.
pause
goto :eof

:pipfail
echo [ERROR] pip install failed. See the red messages above.
pause
goto :eof
