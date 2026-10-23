"""
Accounts router (thin HTTP handlers, FR-101, FR-104, NFR-05, NFR-06, NFR-07).
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.dependencies import get_current_user
from app.db.models.accounts import User
from app.modules.accounts.service import AccountsService
from app.modules.accounts.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
    ConsentRequest,
    ConsentResponse,
    AccountDeletionResponse,
)

router = APIRouter(tags=["Accounts & Access"])


@router.post("/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(payload: UserRegisterRequest, db: Session = Depends(get_db)):
    """FR-101: Public user registration."""
    service = AccountsService(db)
    return service.register(payload)


@router.post("/auth/login", response_model=TokenResponse)
def login(payload: UserLoginRequest, db: Session = Depends(get_db)):
    """FR-101, NFR-05, NFR-06: Public login issuing short-lived JWT token."""
    service = AccountsService(db)
    return service.login(payload)


@router.get("/me", response_model=UserResponse)
def get_profile(current_user: User = Depends(get_current_user)):
    """FR-101, FR-103: Get current user profile."""
    return UserResponse.model_validate(current_user)


@router.post("/me/consent", response_model=ConsentResponse)
def record_consent(
    payload: ConsentRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """FR-104, NFR-07: Record learner consent before tracking activity."""
    service = AccountsService(db)
    return service.record_consent(current_user.user_id)


@router.delete("/me", response_model=AccountDeletionResponse)
def delete_account(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    SRS Section 5.3, NFR-07: Remove account and personal fields, replacing
    learner ID on attempts, events and recommendations with an anonymous ID.
    """
    service = AccountsService(db)
    return service.delete_account(current_user.user_id)
