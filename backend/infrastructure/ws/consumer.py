"""ProjectConsumer — Django Channels WebSocket consumer (Fase A).

Clients connect to ws://<host>/ws/projects/<project_id>/
On connect: receives a snapshot of the last 100 events.
Streaming: new events are polled from the in-process store every 300 ms.
"""
import asyncio

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer

from infrastructure.ws.event_store import current_index, get_events_since


class ProjectConsumer(AsyncJsonWebsocketConsumer):

    async def connect(self):
        user = self.scope.get('user')
        self.project_id = self.scope['url_route']['kwargs']['project_id']
        self._stream_task: asyncio.Task | None = None
        if not user or not user.is_authenticated:
            await self.close(code=4401)
            return
        if not await self._user_can_access_project(user.id, self.project_id):
            await self.close(code=4403)
            return
        await self.accept()
        await self._send_snapshot()
        self._stream_task = asyncio.create_task(self._stream_events())

    async def disconnect(self, close_code):
        if self._stream_task:
            self._stream_task.cancel()

    async def receive_json(self, content):
        pass  # future: subscribe / unsubscribe commands

    async def _send_snapshot(self):
        """Send the last 100 stored events on initial connect."""
        total = current_index(self.project_id)
        since = max(0, total - 100)
        events = get_events_since(self.project_id, since)
        await self.send_json({
            'event': 'project.snapshot',
            'data': {
                'projectId': self.project_id,
                'recentEvents': events,
            },
        })

    async def _stream_events(self):
        """Poll in-process store every 300 ms; forward new events to client."""
        idx = current_index(self.project_id)
        try:
            while True:
                await asyncio.sleep(0.3)
                events = get_events_since(self.project_id, idx)
                if events:
                    idx += len(events)
                    for event in events:
                        await self.send_json(event)
        except asyncio.CancelledError:
            pass

    @database_sync_to_async
    def _user_can_access_project(self, user_id: int, project_id: str) -> bool:
        from studio.models import ProjectModel
        return ProjectModel.objects.filter(id=project_id, owner_id=user_id).exists()
