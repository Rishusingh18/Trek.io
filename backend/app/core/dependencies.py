"""
Core FastAPI dependencies for authentication, role-based access control, and consent gating.
Adheres to FR-102, FR-103, FR-104, NFR-06, and NFR-07.
"""
import uuid
from typing import Callable, List, Optional
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.db.session import get_db
from app.core.auth import decode_access_token
from app.core.errors import UnauthorizedException, ForbiddenException, ConsentRequiredException
from app.db.models.accounts import User

security_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer),
    x_user_id: Optional[str] = Header(None, description="Optional explicit user id for internal/test calls"),
    db: Session = Depends(get_db)
) -> User:
    """
    Authenticate and extract the active User.
    Supports JWT Bearer token via Authorization header or x-user-id header.
    """
    user_id: Optional[uuid.UUID] = None

    if credentials and credentials.credentials:
        payload = decode_access_token(credentials.credentials)
        sub = payload.get("sub")
        if not sub:
            raise UnauthorizedException("Token payload missing subject identifier")
        try:
            user_id = uuid.UUID(sub)
        except ValueError:
            raise UnauthorizedException("Invalid user identifier in token")
    elif x_user_id:
        try:
            user_id = uuid.UUID(x_user_id)
        except ValueError:
            raise UnauthorizedException("Invalid x-user-id header value")
    else:
        raise UnauthorizedException("Authentication token or credentials required")

    from app.modules.accounts.repository import AccountsRepository
    repo = AccountsRepository(db)
    user = repo.get_by_id(user_id)
    if not user or not user.is_active:
        raise UnauthorizedException("User not found or inactive")

    return user


def require_role(*allowed_roles: str) -> Callable:
    """
    Role dependency (learner, instructor, admin) enforcing RBAC (FR-102, FR-103, NFR-06).
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        if current_user.role not in allowed_roles:
            raise ForbiddenException(
                f"Role '{current_user.role}' is not authorized to perform this action. Required: {list(allowed_roles)}"
            )
        return current_user

    return role_checker


def require_consent(current_user: User = Depends(get_current_user)) -> User:
    """
    FR-104, NFR-07: Tracking endpoints refuse requests until the learner has recorded consent.
    """
    if current_user.consent_at is None:
        raise ConsentRequiredException(
            "Learner consent has not been recorded. Please submit consent via POST /v1/me/consent before tracking activity."
        )
    return current_user
