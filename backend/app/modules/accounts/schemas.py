"""
Accounts schemas (FR-101 to FR-104, NFR-05, NFR-07).
Input validation through schemas (NFR-06).
"""
import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr, ConfigDict, Field


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, description="Password must be at least 6 characters")
    role: Optional[str] = "learner"


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    email: str
    role: str
    consent_at: Optional[datetime] = None
    is_active: bool


class ConsentRequest(BaseModel):
    consent_given: bool = True


class ConsentResponse(BaseModel):
    user_id: uuid.UUID
    consent_recorded: bool
    consent_at: datetime


class AccountDeletionResponse(BaseModel):
    message: str
    user_id: uuid.UUID
    anonymized_id: uuid.UUID
