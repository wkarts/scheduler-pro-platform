from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProfileInput(StrictModel):
    display_name: str = Field(min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=40)


class UserCreate(ProfileInput):
    email: EmailStr = Field(max_length=180)
    professional_id: UUID | None = None
    group_ids: list[UUID] = Field(default_factory=list, max_length=100)


class UserUpdate(ProfileInput):
    is_active: bool
    professional_id: UUID | None = None
    group_ids: list[UUID] = Field(default_factory=list, max_length=100)


class GroupInput(StrictModel):
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=1000)
    is_active: bool = True
    permissions: list[str] = Field(default_factory=list, max_length=200)

    @field_validator("name")
    @classmethod
    def normalized_name(cls, value: str) -> str:
        return " ".join(value.split())


# Password whitespace is meaningful; never strip it.
class PasswordInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: str = Field(min_length=1, max_length=512)
    new_password: str = Field(min_length=8, max_length=512)


class EmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(max_length=180)
    current_password: str = Field(min_length=1, max_length=512)


class ConfirmEmailInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: str = Field(min_length=32, max_length=128)
    new_password: str | None = Field(default=None, min_length=8, max_length=512)
