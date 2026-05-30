from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query

from app.core.security import decode_token
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.websockets.manager import manager

router = APIRouter()


@router.websocket("/notifications")
async def notifications_ws(ws: WebSocket, token: str = Query(...)):
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await ws.close(code=4001)
        return

    user_id = int(payload["sub"])

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if not user or not user.is_active:
            await ws.close(code=4001)
            return

    room = f"notifications:{user_id}"
    await manager.connect(room, user_id, ws)
    try:
        while True:
            await ws.receive_text()  # keep-alive ping only
    except WebSocketDisconnect:
        manager.disconnect(room, ws)
