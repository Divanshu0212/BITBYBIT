from pydantic import BaseModel, EmailStr, Field
from uuid import UUID
from datetime import datetime
from typing import Literal


class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    role: Literal["employer", "freelancer"]
    skills: list[str] | None = None  # Only for freelancers
    bio: str | None = None


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class UserResponse(BaseModel):
    id: UUID
    email: str
    name: str
    role: str
    created_at: datetime
    skills: list[str] | None = None
    bio: str | None = None

    model_config = {"from_attributes": True}


class GroqKeyUpdate(BaseModel):
    api_key: str = Field(min_length=1)
