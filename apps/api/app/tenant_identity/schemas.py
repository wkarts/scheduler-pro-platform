from uuid import UUID
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProfileInput(StrictModel):
    display_name: str = Field(min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=40)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Informe um nome válido.")
        return value


class UserUpdate(ProfileInput):
    group_ids: list[UUID] = Field(default_factory=list, max_length=50)
    professional_id: UUID | None = None
    is_active: bool = True


class UserCreate(ProfileInput):
    email: EmailStr = Field(max_length=180)
    group_ids: list[UUID] = Field(default_factory=list, max_length=50)
    professional_id: UUID | None = None


class GroupInput(StrictModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)
    is_active: bool = True
    permissions: list[str] = Field(default_factory=list, max_length=300)

    @field_validator("name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) < 2:
            raise ValueError("Informe um nome válido.")
        return value


class PasswordInput(StrictModel):
    current_password: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=8, max_length=512)


class EmailInput(StrictModel):
    email: EmailStr = Field(max_length=180)
    current_password: str = Field(min_length=1, max_length=512)


class ConfirmationInput(StrictModel):
    token: str = Field(min_length=40, max_length=128)
    new_password: str | None = Field(default=None, min_length=8, max_length=512)
