from fastapi import APIRouter

from app.core.responses import success

router = APIRouter()


@router.post("/signed-url")
async def signed_url():
    return success({"url": None, "message": "URLs assinadas serão emitidas pelo FileService/S3"})
