from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.websocket_manager import manager

router = APIRouter(tags=["live"])


@router.websocket("/ws/schedule")
async def schedule_ws(websocket: WebSocket):
    """
    Clients (open Gantt dashboards) connect here and receive push
    events whenever a re-optimization completes or an override is
    validated. The client's own polling of /schedule/gantt after a
    'schedule_updated' event is what actually refreshes the view —
    this socket only carries the "something changed, go refetch"
    signal plus a lightweight payload for optimistic UI updates.
    """
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect inbound messages from the client on this
            # channel; just keep the connection alive.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
