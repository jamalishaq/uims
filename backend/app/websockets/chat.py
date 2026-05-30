from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from sqlalchemy import select

from app.core.security import decode_token
from app.core.database import AsyncSessionLocal
from app.models.user import User
from app.models.course import CourseSection, CourseEnrollment
from app.websockets.manager import manager

router = APIRouter()


@router.websocket("/chat/{section_id}")
async def course_chat(section_id: int, ws: WebSocket, token: str = Query(...)):
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await ws.close(code=4001)
        return

    user_id = int(payload["sub"])
    role = payload.get("role")

    async with AsyncSessionLocal() as db:
        user = await db.get(User, user_id)
        if not user or not user.is_active:
            await ws.close(code=4001)
            return

        section = await db.get(CourseSection, section_id)
        if not section:
            await ws.close(code=4004)
            return

        if role == "student":
            result = await db.execute(
                select(CourseEnrollment).where(
                    CourseEnrollment.student_id == user_id,
                    CourseEnrollment.section_id == section_id,
                )
            )
            if not result.scalar_one_or_none():
                await ws.close(code=4003)
                return
        elif role == "lecturer" and section.lecturer_id != user_id:
            await ws.close(code=4003)
            return

    room = f"chat:{section_id}"
    await manager.connect(room, user_id, ws)
    try:
        while True:
            data = await ws.receive_json()
            await manager.broadcast(room, {
                "type": "message",
                "user_id": user_id,
                "username": user.username,
                "content": data.get("content", ""),
            })
    except WebSocketDisconnect:
        manager.disconnect(room, ws)
