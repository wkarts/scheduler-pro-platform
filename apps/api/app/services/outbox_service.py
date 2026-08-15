from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models_tenant import OutboxEvent


class OutboxService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def append(self, event_name: str, aggregate_id: str, payload: dict) -> OutboxEvent:
        event = OutboxEvent(event_name=event_name, aggregate_id=aggregate_id, payload=payload)
        self.session.add(event)
        return event
