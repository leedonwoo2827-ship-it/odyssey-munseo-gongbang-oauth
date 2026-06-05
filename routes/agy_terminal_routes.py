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

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

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


def setup_agy_terminal_routes() -> APIRouter:
    router = APIRouter(tags=["agy-terminal"])

    @router.websocket("/api/agy/terminal/ws")
    async def terminal_ws(ws: WebSocket):
        if not _is_direct_loopback(ws):
            await ws.close(code=1008)
            return

        from services.agy.pty_terminal import PtySession, backend_available
        if not backend_available():
            await ws.accept()
            await ws.send_text(json.dumps({
                "type": "error",
                "data": ("PTY 백엔드가 없습니다. 설치 필요: pip install pywinpty (Windows) "
                         "또는 ptyprocess (macOS/Linux).\r\n"),
            }))
            await ws.close()
            return

        await ws.accept()
        loop = asyncio.get_running_loop()
        try:
            session = PtySession()
        except Exception as e:
            await ws.send_text(json.dumps({"type": "error", "data": f"터미널 시작 실패: {e}\r\n"}))
            await ws.close()
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
