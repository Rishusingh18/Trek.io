"""
Authentication & Password hashing tests adhering to NFR-05 and FR-101.
"""
from datetime import datetime, timedelta, timezone
import pytest
from app.core.auth import (
    get_password_hash,
    verify_password,
    create_access_token,
    decode_access_token,
)
from app.core.errors import UnauthorizedException


def test_nfr05_salted_adaptive_password_hashing():
    """Verify NFR-05: Passwords shall be stored using a salted adaptive hash."""
    plain = "SuperSecret123!"
    hash1 = get_password_hash(plain)
    hash2 = get_password_hash(plain)

    # Starts with standard bcrypt identifier ($2b$)
    assert hash1.startswith("$2b$") or hash1.startswith("$2a$")
    # Adaptive salting ensures two hashes of identical password differ
    assert hash1 != hash2

    assert verify_password(plain, hash1) is True
    assert verify_password("WrongPassword!", hash1) is False


def test_nfr05_jwt_token_creation_and_validation():
    """Verify NFR-05 & FR-101: JWT tokens carry subject, role, and expiration."""
    user_id = "11111111-1111-1111-1111-111111111111"
    token = create_access_token(subject=user_id, role="learner")

    payload = decode_access_token(token)
    assert payload["sub"] == user_id
    assert payload["role"] == "learner"
    assert "exp" in payload
    assert "iat" in payload
    assert "last_active" in payload


def test_nfr05_jwt_inactivity_expiration():
    """Verify NFR-05: Sessions expire after inactivity."""
    user_id = "11111111-1111-1111-1111-111111111111"
    # Token with last activity 35 minutes ago, threshold 30 minutes
    thirty_five_mins_ago = datetime.now(timezone.utc) - timedelta(minutes=35)
    token = create_access_token(
        subject=user_id,
        role="learner",
        inactivity_minutes=30,
        last_active=thirty_five_mins_ago
    )

    with pytest.raises(UnauthorizedException) as exc:
        decode_access_token(token)
    assert "inactivity" in str(exc.value.message).lower()


def test_nfr05_jwt_expired_token():
    """Verify NFR-05: Expired tokens are rejected."""
    user_id = "11111111-1111-1111-1111-111111111111"
    # Token expired 10 seconds in the past
    token = create_access_token(subject=user_id, expires_delta=timedelta(seconds=-10))

    with pytest.raises(UnauthorizedException):
        decode_access_token(token)
