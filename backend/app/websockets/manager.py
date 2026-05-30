from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        # room_id → list of (user_id, websocket)
        self._rooms: dict[str, list[tuple[int, WebSocket]]] = {}

    async def connect(self, room: str, user_id: int, ws: WebSocket):
        await ws.accept()
        self._rooms.setdefault(room, []).append((user_id, ws))

    def disconnect(self, room: str, ws: WebSocket):
        if room in self._rooms:
            self._rooms[room] = [(uid, w) for uid, w in self._rooms[room] if w is not ws]
            if not self._rooms[room]:
                del self._rooms[room]

    async def broadcast(self, room: str, data: dict, exclude: WebSocket = None):
        for _, ws in self._rooms.get(room, []):
            if ws is not exclude:
                await ws.send_json(data)

    async def send_to_user(self, user_id: int, data: dict):
        """Push to a specific user across all rooms (used for notifications)."""
        for connections in self._rooms.values():
            for uid, ws in connections:
                if uid == user_id:
                    await ws.send_json(data)


manager = ConnectionManager()
