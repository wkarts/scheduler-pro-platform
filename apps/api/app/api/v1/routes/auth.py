from fastapi import APIRouter
from pydantic import BaseModel, EmailStr

from app.core.responses import success
from app.core.security import create_access_token

router = APIRouter()


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@router.post("/login")
async def login(payload: LoginRequest):
    # Integração real com platform_users/tenant_users entra no próximo incremento.
    token = create_access_token(payload.email, tenant_id=None, permissions=["appointments.read"])
    return success({"access_token": token, "token_type": "bearer", "expires_in": 900})


@router.post("/refresh")
async def refresh():
    return success({"message": "refresh token rotativo reservado para implementação persistente"})
