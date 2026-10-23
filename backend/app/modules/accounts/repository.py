"""
Accounts repository (FR-101 to FR-104, NFR-06, NFR-07).
Only this file touches the users table.
Uses parameterized queries only.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import select, delete
from app.db.models.accounts import User


class AccountsRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_by_id(self, user_id: uuid.UUID) -> Optional[User]:
        stmt = select(User).where(User.user_id == user_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def get_by_email(self, email: str) -> Optional[User]:
        stmt = select(User).where(User.email == email)
        return self.db.execute(stmt).scalar_one_or_none()

    def create_user(self, email: str, password_hash: str, role: str) -> User:
        user = User(
            user_id=uuid.uuid4(),
            email=email,
            password_hash=password_hash,
            role=role,
            is_active=True
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def record_consent(self, user_id: uuid.UUID) -> Optional[User]:
        user = self.get_by_id(user_id)
        if user:
            user.consent_at = datetime.now(timezone.utc)
            self.db.commit()
            self.db.refresh(user)
        return user

    def delete_user(self, user_id: uuid.UUID) -> bool:
        """
        SRS section 5.3, NFR-07: Permanently remove the user account and personal fields.
        """
        stmt = delete(User).where(User.user_id == user_id)
        result = self.db.execute(stmt)
        self.db.commit()
        return result.rowcount > 0
