"""Password hashing with Argon2. Plain passwords are never stored or logged."""

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import HTTPException

MIN_PASSWORD_LENGTH = 10

_hasher = PasswordHasher()
# Checked when the email is unknown, so a wrong email takes as long as a wrong password.
_UNKNOWN_USER_HASH = _hasher.hash("not-a-real-password")


def check_password_rules(password: str) -> None:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise HTTPException(422, f"Use at least {MIN_PASSWORD_LENGTH} characters for the password.")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def password_matches(password_hash: str | None, password: str) -> bool:
    """password_hash is None when the email is unknown: still does the same work, then says no."""
    try:
        _hasher.verify(password_hash or _UNKNOWN_USER_HASH, password)
    except (VerificationError, InvalidHashError):
        return False
    return password_hash is not None
