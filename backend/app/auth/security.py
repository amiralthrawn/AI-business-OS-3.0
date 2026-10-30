"""Passwords, access tokens and invitation tokens (V3).

Passwords are hashed with scrypt from the standard library (no extra
dependency, memory-hard). Access tokens are short-lived signed JWTs (HS256)
carrying the profile id and its company id. Invitation tokens are random,
single-use, and only their SHA-256 is stored.
"""

import base64
import hashlib
import hmac
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings

_SCRYPT_N, _SCRYPT_R, _SCRYPT_P = 2**14, 8, 1
MIN_PASSWORD_LENGTH = 10


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _unb64(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=32, maxmem=64 * 1024 * 1024)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = _scrypt(password, salt, _SCRYPT_N, _SCRYPT_R, _SCRYPT_P)
    return f"scrypt${_SCRYPT_N}${_SCRYPT_R}${_SCRYPT_P}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        computed = _scrypt(password, _unb64(salt), int(n), int(r), int(p))
    except (ValueError, TypeError):
        return False
    return hmac.compare_digest(computed, _unb64(digest))


# Verified against when the email is unknown, so a login answers in the same
# time whether or not the account exists.
_DUMMY_HASH = hash_password(secrets.token_urlsafe(16))


def burn_password_check(password: str) -> None:
    verify_password(password, _DUMMY_HASH)


def _secret() -> str:
    secret = get_settings().auth_secret_key
    if not secret:
        raise RuntimeError("AUTH_SECRET_KEY must be set to issue or verify access tokens.")
    return secret


def create_access_token(profile_id: uuid.UUID, company_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    claims = {
        "sub": str(profile_id),
        "cid": str(company_id),
        "typ": "access",
        "iat": now,
        "exp": now + timedelta(hours=get_settings().access_token_ttl_hours),
    }
    return jwt.encode(claims, _secret(), algorithm="HS256")


def decode_access_token(token: str) -> tuple[uuid.UUID, uuid.UUID] | None:
    """(profile id, company id) of a valid, unexpired access token, else None."""

    try:
        claims = jwt.decode(token, _secret(), algorithms=["HS256"], options={"require": ["sub", "cid", "exp"]})
        if claims.get("typ") != "access":
            return None
        return uuid.UUID(claims["sub"]), uuid.UUID(claims["cid"])
    except (jwt.PyJWTError, ValueError):
        return None


def new_invite_token() -> tuple[str, str]:
    """(token to put in the link, hash to store)."""

    token = secrets.token_urlsafe(32)
    return token, hash_invite_token(token)


def hash_invite_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def normalize_email(email: str | None) -> str | None:
    if email is None:
        return None
    email = email.strip().lower()
    return email or None
