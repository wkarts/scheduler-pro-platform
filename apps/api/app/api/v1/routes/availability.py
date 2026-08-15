from datetime import datetime, timedelta
from typing import Any

from fastapi import APIRouter, Query

from app.core.responses import success

router = APIRouter()


@router.get("")
async def availability(
    date: datetime = Query(...), professional_id: str | None = None
) -> dict[str, Any]:
    slots = []
    start = date.replace(hour=8, minute=0, second=0, microsecond=0)
    for idx in range(20):
        slots.append(
            {
                "starts_at": (start + timedelta(minutes=30 * idx)).isoformat(),
                "available": True,
                "professional_id": professional_id,
            }
        )
    return success(slots)
