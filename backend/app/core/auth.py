"""
Authentication, password hashing, and JWT utilities adhering to NFR-05 and FR-101.
- Salted adaptive password hash (native bcrypt).
- Short-lived JWT that expires after inactivity or validity duration.
"""
from datetime import datetime, timedelta, timezone
from typing import Any, Optional, Dict
import bcrypt
from jose import jwt, JWTError
from app.core.config import settings
from app.core.errors import UnauthorizedException


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against hashed password."""
    try:
        pwd_bytes = plain_password.encode("utf-8")[:72]
        hashed_bytes = hashed_password.encode("utf-8")
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception:
        return False


def get_password_hash(password: str) -> str:
    """
    Generate salted adaptive bcrypt hash (NFR-05).
    Truncates to 72 bytes as per bcrypt specification.
    """
    pwd_bytes = password.encode("utf-8")[:72]
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")


def create_access_token(
    subject: str | Any,
    role: Optional[str] = None,
    expires_delta: Optional[timedelta] = None,
    inactivity_minutes: Optional[int] = 30,
    last_active: Optional[datetime] = None,
) -> str:
    """
    Generate short-lived JWT token adhering to NFR-05.
    Records issued_at ('iat'), expiry ('exp'), and inactivity limit ('inactivity_minutes').
    """
    now = datetime.now(timezone.utc)
    if expires_delta:
        expire = now + expires_delta
    else:
        expire = now + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)

    active_ts = int(last_active.timestamp()) if last_active else int(now.timestamp())

    payload: Dict[str, Any] = {
        "sub": str(subject),
        "iat": int(now.timestamp()),
        "exp": int(expire.timestamp()),
        "last_active": active_ts,
        "inactivity_minutes": inactivity_minutes,
    }
    if role:
        payload["role"] = role

    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> Dict[str, Any]:
    """
    Decode and validate JWT token adhering to NFR-05.
    Verifies signature, expiration, and inactivity timeout.
    """
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
    except JWTError as e:
        raise UnauthorizedException(f"Invalid or expired token: {str(e)}")

    # Check inactivity expiration (NFR-05)
    last_active = payload.get("last_active")
    inactivity_minutes = payload.get("inactivity_minutes")
    if last_active is not None and inactivity_minutes is not None:
        current_ts = int(datetime.now(timezone.utc).timestamp())
        if current_ts - last_active >= (inactivity_minutes * 60):
            raise UnauthorizedException("Session expired due to inactivity")

    return payload
