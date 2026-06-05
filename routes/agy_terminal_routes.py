"""웹 내장 터미널 — agy(Antigravity CLI) 로그인/계정전환/모델변경/사용량조회용.

xterm.js(브라우저) ↔ WebSocket ↔ PtySession ↔ 셸(cmd/bash). 사용자는 이 터미널에서
일반 터미널과 동일하게 `agy` 명령을 입력한다.

보안: 호스트 셸 접근이므로 **loopback(127.0.0.1) 직접 연결만 허용**한다(프록시/터널 차단).
각 PC 로컬 단독 사용 전제. 최초 agy 로그인을 위해 인증 없이 접근 가능해야 하므로
app.py 의 AUTH_EXEMPT 에 등록한다.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)

_PROXY_FWD_HEADERS = (
    "cf-connecting-ip", "cf-ray", "cf-visitor",
    "x-forwarded-for", "x-forwarded-host", "x-real-ip", "forwarded",
)


def _is_direct_loopback(ws: WebSocket) -> bool:
    host = ws.client.host if ws.client else None
    if host not in ("127.0.0.1", "::1"):
        return False
    for h in _PROXY_FWD_HEADERS:
        if ws.headers.get(h):
            return False
    return True


def _client_is_loopback(request: Request) -> bool:
    host = request.client.host if request.client else None
    if host not in ("127.0.0.1", "::1"):
        return False
    for h in _PROXY_FWD_HEADERS:
        if request.headers.get(h):
            return False
    return True


def setup_agy_terminal_routes() -> APIRouter:
    router = APIRouter(tags=["agy-terminal"])

    @router.post("/api/agy/open-terminal")
    async def open_os_terminal(request: Request):
        """진짜 OS 터미널 창을 하나 띄워 그 안에서 `agy` 를 실행한다.

        브라우저 내장 터미널(pywinpty) 대신 사용하는 기본 방식. 사용자는 새로 뜬
        cmd/터미널 창에서 `agy` 로 Google 로그인·계정전환을 한다. (로컬 전용)
        """
        import os
        import subprocess
        import sys

        if not _client_is_loopback(request):
            return JSONResponse(status_code=403,
                                content={"ok": False, "message": "로컬(127.0.0.1)에서만 가능합니다."})

        agy = os.environ.get("AGY_BIN", "agy")
        try:
            if sys.platform == "win32":
                # 새 콘솔 창에서 agy 실행 후 창 유지(/k). agy 미설치면 그 창에 오류가 보임.
                # start 의 첫 인자("")는 창 제목 — 공백/괄호 파싱 문제를 피하려 빈 제목 사용.
                subprocess.Popen(["cmd", "/c", "start", "", "cmd", "/k", agy], close_fds=True)
                method = "windows-cmd"
            elif sys.platform == "darwin":
                subprocess.Popen(["osascript", "-e",
                                  f'tell application "Terminal" to do script "{agy}"'])
                method = "macos-terminal"
            else:
                # 리눅스: 흔한 터미널 에뮬레이터 순서대로 시도
                launched = False
                for term in (["x-terminal-emulator", "-e", agy],
                             ["gnome-terminal", "--", agy],
                             ["konsole", "-e", agy],
                             ["xterm", "-e", agy]):
                    try:
                        subprocess.Popen(term)
                        launched = True
                        break
                    except FileNotFoundError:
                        continue
                if not launched:
                    return JSONResponse(status_code=500, content={
                        "ok": False,
                        "message": "터미널을 열지 못했습니다. 직접 터미널에서 `agy` 를 실행하세요.",
                    })
                method = "linux-terminal"
            return {"ok": True, "method": method,
                    "message": "새 터미널 창이 열렸습니다. 그 창에서 Google 로그인을 진행하세요. "
                               "(계정 전환은 agy logout 후 다시 agy)"}
        except FileNotFoundError as e:
            return JSONResponse(status_code=500, content={
                "ok": False,
                "message": f"터미널 실행 파일을 찾지 못했습니다: {e}. 직접 cmd 에서 `agy` 실행하세요.",
            })
        except Exception as e:
            return JSONResponse(status_code=500, content={
                "ok": False, "message": f"터미널 열기 실패: {e}",
            })

    @router.post("/api/agy/logout")
    async def agy_logout(request: Request):
        """agy 자격증명을 지워 로그아웃(계정 전환 준비). 로컬 전용."""
        if not _client_is_loopback(request):
            return JSONResponse(status_code=403, content={"ok": False, "message": "로컬에서만 가능합니다."})
        from services.agy import auth as agy_auth
        removed = agy_auth.logout()
        return {
            "ok": True,
            "removed": removed,
            "message": ("로그아웃되었습니다. [agy 로그인] 버튼(또는 실제 cmd 창)에서 다른 Google 계정으로 로그인하세요."
                        if removed else "이미 로그아웃 상태입니다."),
        }

    @router.get("/api/agy/models")
    async def agy_models():
        """`agy models` 목록 + 현재 선택된 모델. ''(빈값)=agy 기본 모델."""
        from services.agy import runner
        models = await asyncio.to_thread(runner.list_models)
        return {"models": models, "selected": runner.get_model()}

    @router.post("/api/agy/model")
    async def agy_set_model(request: Request):
        """화면에서 고른 모델 저장(빈 문자열이면 agy 기본). 로컬 전용."""
        if not _client_is_loopback(request):
            return JSONResponse(status_code=403, content={"ok": False, "message": "로컬에서만 가능합니다."})
        from services.agy import runner
        body = await request.json()
        runner.set_model((body.get("model") or "").strip())
        return {"ok": True, "selected": runner.get_model()}

    @router.get("/api/agy/terminal/diag")
    async def terminal_diag(request: Request):
        """진단: PTY 백엔드/agy 설치 상태 + 호출자 호스트."""
        from services.agy.pty_terminal import diag
        host = request.client.host if request.client else None
        d = diag()
        d["client_host"] = host
        d["loopback_ok"] = host in ("127.0.0.1", "::1")
        return JSONResponse(d)

    @router.websocket("/api/agy/terminal/ws")
    async def terminal_ws(ws: WebSocket):
        if not _is_direct_loopback(ws):
            await ws.accept()
            await ws.send_text(json.dumps({
                "type": "error",
                "data": ("이 터미널은 로컬(127.0.0.1) 접속에서만 사용할 수 있습니다.\r\n"),
            }))
            # 메시지가 렌더되도록 즉시 닫지 않고 입력 대기로 유지
            try:
                while True:
                    await ws.receive_text()
            except Exception:
                pass
            return

        from services.agy.pty_terminal import PtySession, backend_available, diag
        if not backend_available():
            await ws.accept()
            d = diag()
            await ws.send_text(json.dumps({
                "type": "error",
                "data": ("[PTY 백엔드 없음] 내장 터미널을 쓰려면 설치가 필요합니다:\r\n"
                         "  pip install pywinpty   (Windows)\r\n"
                         "  pip install ptyprocess (macOS/Linux)\r\n\r\n"
                         "또는 윈도우 cmd 에서 직접 `agy` 를 실행해 로그인해도 됩니다.\r\n"
                         f"\r\n진단: {json.dumps(d, ensure_ascii=False)}\r\n"),
            }))
            try:
                while True:
                    await ws.receive_text()
            except Exception:
                pass
            return

        await ws.accept()
        loop = asyncio.get_running_loop()
        try:
            session = PtySession()
        except Exception as e:
            logger.warning("agy terminal spawn failed: %r", e)
            await ws.send_text(json.dumps({"type": "error", "data": f"터미널 시작 실패: {e!r}\r\n"}))
            try:
                while True:
                    await ws.receive_text()
            except Exception:
                pass
            return

        stop = threading.Event()

        def _reader():
            while not stop.is_set():
                try:
                    data = session.read(65536)
                except (EOFError, OSError):
                    break
                except Exception:
                    break
                if not data:
                    if not session.isalive():
                        break
                    continue
                asyncio.run_coroutine_threadsafe(
                    ws.send_text(json.dumps({"type": "out", "data": data})), loop)
            asyncio.run_coroutine_threadsafe(_notify_exit(), loop)

        async def _notify_exit():
            try:
                await ws.send_text(json.dumps({"type": "exit"}))
            except Exception:
                pass

        t = threading.Thread(target=_reader, name="agy-pty-reader", daemon=True)
        t.start()

        try:
            while True:
                msg = await ws.receive_text()
                try:
                    obj = json.loads(msg)
                except Exception:
                    obj = {"type": "in", "data": msg}
                mtype = obj.get("type")
                if mtype == "in":
                    session.write(obj.get("data", ""))
                elif mtype == "resize":
                    try:
                        session.setwinsize(int(obj.get("rows", 30)), int(obj.get("cols", 120)))
                    except Exception:
                        pass
        except WebSocketDisconnect:
            pass
        except Exception:
            logger.debug("agy terminal ws error", exc_info=True)
        finally:
            stop.set()
            session.terminate()

    return router
