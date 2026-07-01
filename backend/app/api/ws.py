"""WebSocket: push aktualizovaných predikcí do frontendu support týmu."""

from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    def __init__(self):
        self.connections: dict[int, list[WebSocket]] = defaultdict(list)

    async def connect(self, runner_id: int, ws: WebSocket):
        await ws.accept()
        self.connections[runner_id].append(ws)

    def disconnect(self, runner_id: int, ws: WebSocket):
        if ws in self.connections[runner_id]:
            self.connections[runner_id].remove(ws)

    async def broadcast(self, runner_id: int, message: dict):
        for ws in list(self.connections[runner_id]):
            try:
                await ws.send_json(message)
            except Exception:
                self.disconnect(runner_id, ws)


manager = ConnectionManager()


@router.websocket("/ws/runners/{runner_id}")
async def runner_updates(ws: WebSocket, runner_id: int):
    await manager.connect(runner_id, ws)
    try:
        while True:
            # Klient nic neposílá, jen drží spojení
            await ws.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(runner_id, ws)
