"""
Accounts service (FR-101 to FR-104, NFR-05, NFR-06, NFR-07).
Public interface for accounts. Other modules import ONLY from this file.
"""
import uuid
from typing import Optional
from sqlalchemy.orm import Session
from app.core.auth import get_password_hash, verify_password, create_access_token
from app.core.errors import AppException, NotFoundException, UnauthorizedException
from app.modules.accounts.repository import AccountsRepository
from app.modules.accounts.schemas import (
    UserRegisterRequest,
    UserLoginRequest,
    TokenResponse,
    UserResponse,
    ConsentResponse,
    AccountDeletionResponse,
)


class AccountsService:
    def __init__(self, db: Session):
        self.db = db
        self.repo = AccountsRepository(db)

    def register(self, req: UserRegisterRequest) -> UserResponse:
        """FR-101: Register user."""
        existing = self.repo.get_by_email(req.email)
        if existing:
            raise AppException(message="Email already registered", status_code=400, code="EMAIL_EXISTS")

        hashed = get_password_hash(req.password)
        role = req.role if req.role in ("learner", "instructor", "administrator") else "learner"
        user = self.repo.create_user(email=req.email, password_hash=hashed, role=role)
        return UserResponse.model_validate(user)

    def login(self, req: UserLoginRequest) -> TokenResponse:
        """FR-101, NFR-05: Authenticate user and issue short-lived JWT."""
        user = self.repo.get_by_email(req.email)
        if not user or not verify_password(req.password, user.password_hash):
            raise UnauthorizedException("Invalid email or password")

        token = create_access_token(subject=str(user.user_id), role=user.role)
        return TokenResponse(access_token=token)

    def record_consent(self, user_id: uuid.UUID) -> ConsentResponse:
        """FR-104, NFR-07: Record learner's consent before tracking."""
        user = self.repo.record_consent(user_id)
        if not user:
            raise NotFoundException("User not found")
        return ConsentResponse(
            user_id=user.user_id,
            consent_recorded=True,
            consent_at=user.consent_at
        )

    def get_user_by_id(self, user_id: uuid.UUID) -> Optional[UserResponse]:
        """Public interface for other modules to check user existence/role."""
        user = self.repo.get_by_id(user_id)
        if not user:
            return None
        return UserResponse.model_validate(user)

    def delete_account(self, user_id: uuid.UUID) -> AccountDeletionResponse:
        """
        SRS Section 5.3, NFR-07: Remove account and personal fields, and replace
        learner id on attempts, events and recommendations with an anonymous id so
        past experiment results stay valid without identifying anyone.
        """
        user = self.repo.get_by_id(user_id)
        if not user:
            raise NotFoundException("User not found")

        anonymous_id = uuid.uuid4()

        # Anonymize through service boundaries
        from app.modules.knowledge.service import KnowledgeService
        from app.modules.recommender.service import RecommenderService
        from app.modules.experiments.service import ExperimentsService

        knowledge_svc = KnowledgeService(self.db)
        knowledge_svc.anonymize_learner_data(user_id=user_id, anonymous_id=anonymous_id)

        recommender_svc = RecommenderService(self.db)
        recommender_svc.anonymize_learner_data(user_id=user_id, anonymous_id=anonymous_id)

        experiments_svc = ExperimentsService(self.db)
        experiments_svc.anonymize_learner_data(user_id=user_id, anonymous_id=anonymous_id)

        # Permanently purge user account and personal credentials
        self.repo.delete_user(user_id)

        return AccountDeletionResponse(
            message="Account permanently deleted and interaction history anonymized.",
            user_id=user_id,
            anonymized_id=anonymous_id
        )
