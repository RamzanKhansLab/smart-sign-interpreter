from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/sensor-stream")
async def sensor_stream(websocket: WebSocket):
    manager = websocket.app.state.ws_manager
    pipeline = websocket.app.state.pipeline
    await manager.connect(websocket)
    latest_message = pipeline.get_latest_message()
    if latest_message is not None:
        await websocket.send_json(latest_message)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
