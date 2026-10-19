"""
A minimal in-memory WebSocket connection manager. Every connected
client (an open Gantt chart tab) is registered here; when a re-solve
completes or a manual override is validated, we broadcast the new
state so every open dashboard updates without a manual refresh.

For a multi-process deployment (more than one uvicorn worker), swap
the in-memory set for a Redis pub/sub channel — the public interface
(`connect`, `disconnect`, `broadcast`) would stay identical.
"""
import asyncio
import json
from typing import Any, Dict, List

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.append(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._connections:
            self._connections.remove(websocket)

    async def broadcast(self, event_type: str, payload: Dict[str, Any]) -> None:
        message = json.dumps({"type": event_type, "payload": payload}, default=str)
        stale: List[WebSocket] = []
        for connection in self._connections:
            try:
                await connection.send_text(message)
            except Exception:
                stale.append(connection)
        for s in stale:
            self.disconnect(s)


manager = ConnectionManager()

_main_loop: "asyncio.AbstractEventLoop | None" = None


def set_main_loop(loop: "asyncio.AbstractEventLoop") -> None:
    """Called once at app startup (from the actual serving event loop)
    so broadcast_sync() has somewhere real to schedule work onto."""
    global _main_loop
    _main_loop = loop


def broadcast_sync(event_type: str, payload: Dict[str, Any]) -> None:
    """
    Fire a broadcast from SYNCHRONOUS code — both our FastAPI route
    handlers (`def`, not `async def`) and our BackgroundTasks solver
    job are plain sync functions running in a worker thread. The live
    WebSocket connections belong to uvicorn's main event loop, so the
    broadcast coroutine MUST run there too — `asyncio.run()` would spin
    up a brand-new, unrelated event loop on the calling thread and the
    send would silently never reach any real connection. Instead we
    hand the coroutine to the actual main loop via
    `run_coroutine_threadsafe`, which is the documented way to call
    asyncio code from a non-event-loop thread.
    """
    if _main_loop is None:
        return
    try:
        future = asyncio.run_coroutine_threadsafe(
            manager.broadcast(event_type, payload), _main_loop
        )
        future.result(timeout=5)
    except Exception:
        # Never let a broadcast failure break the actual business
        # operation (schedule was still saved correctly) — just skip
        # the live-update push this one time.
        pass

