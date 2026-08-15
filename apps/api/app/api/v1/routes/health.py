from fastapi import APIRouter

from app.core.responses import success

router = APIRouter()


@router.get("/health")
async def health():
    return success({"status": "ok", "service": "scheduler-pro-api"})


@router.get("/health/live")
async def live():
    return success({"live": True})


@router.get("/health/ready")
async def ready():
    # A checagem profunda deve validar PostgreSQL, Redis, RabbitMQ e S3.
    return success({"ready": True, "checks": {"api": "ok"}})
