from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginIn(BaseModel):
    email: EmailStr
    password: str
class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
class SectionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    key: str
    title: str
    content: dict[str, Any]
    visible: bool
    position: int
    updated_at: datetime


class SectionUpdate(BaseModel):
    title: str | None = None
    content: dict[str, Any] | None = None
    visible: bool | None = None
    position: int | None = None


class SectionCreate(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9-]{2,40}$")
    title: str = Field(min_length=1, max_length=200)
    visible: bool = True
    position: int | None = None
    content: dict[str, Any] = Field(default_factory=dict)


class ContactIn(BaseModel):
    name: str = Field(min_length=2, max_length=150)
    email: EmailStr
    phone: str | None = Field(default=None, max_length=50)
    message: str = Field(min_length=5, max_length=3000)


class ContactOut(ContactIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    read: bool
    created_at: datetime
