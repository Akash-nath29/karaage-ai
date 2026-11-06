import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RegisterIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)


class LoginIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(max_length=320)
    password: str = Field(max_length=128)


class EmailIn(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: str = Field(max_length=320)


class PasswordIn(BaseModel):
    password: str = Field(max_length=128)


class TokenIn(BaseModel):
    token: str = Field(max_length=200)


class ResetIn(TokenIn):
    password: str = Field(min_length=8, max_length=128)


class ProfilePatch(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    preferred_language: str | None = Field(default=None, min_length=1, max_length=50)
    academic_level: str | None = Field(default=None, max_length=100)
    learning_preferences: str | None = Field(default=None, max_length=1000)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    avatar_url: str | None
    preferred_language: str
    academic_level: str
    learning_preferences: str
    email_verified: bool
    created_at: datetime


class PersonOut(BaseModel):
    """Another user as members see them."""

    id: uuid.UUID
    email: str
    display_name: str
    avatar_url: str | None
