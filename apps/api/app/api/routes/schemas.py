"""Request/response schemas. Every request body is validated here (PLANNING §25)."""
from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class SignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=200)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=200)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=500)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=1, max_length=500)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserPublic(BaseModel):
    id: str
    email: str
    role: str


class MeResponse(BaseModel):
    id: str
    email: str
    role: str
    capabilities: list[str]
