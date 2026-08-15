import httpx
import pytest_asyncio

from app.main import create_app


@pytest_asyncio.fixture
async def client():
    transport = httpx.ASGITransport(app=create_app(), raise_app_exceptions=False)
    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://localhost",
        headers={"host": "localhost"},
    ) as test_client:
        yield test_client
