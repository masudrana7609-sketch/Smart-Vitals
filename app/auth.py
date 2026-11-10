"""Logins (R5): argon2 password hashes and short-lived signed tokens (JWT, HS256).

- Passwords are only ever stored as argon2 hashes (pwdlib's recommended settings).
- A token names the clinician and their role, and expires after access_token_minutes.
- Repeated failed logins for the same name are refused for login_lock_minutes (in memory: a prototype).
"""

import time
from collections import defaultdict, deque
from datetime import UTC, datetime, timedelta

import jwt
from pwdlib import PasswordHash

ALGORITHM = "HS256"
MIN_SECRET_LENGTH = 32
MIN_PASSWORD_LENGTH = 12
_hasher = PasswordHash.recommended()
# A hash to check against when the login name does not exist, so both cases take the same time
_DUMMY_HASH = _hasher.hash("not-a-real-password-used-for-timing")


def check_secret(secret: str) -> None:
    if len(secret) < MIN_SECRET_LENGTH or secret == "change-me":  # noqa: S105 (rejects the placeholder)
        raise RuntimeError(
            "SECRET_KEY is missing or too short. Put a random value of at least 32 characters in .env: "
            'python -c "import secrets; print(secrets.token_urlsafe(48))"'
        )


def hash_password(password: str) -> str:
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValueError(f"passwords need at least {MIN_PASSWORD_LENGTH} characters")
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    if not password_hash:
        _hasher.verify(password, _DUMMY_HASH)
        return False
    return _hasher.verify(password, password_hash)


def make_token(clinician_id: str, role: str, secret: str, minutes: int) -> str:
    now = datetime.now(UTC)
    claims = {"sub": clinician_id, "role": role, "iat": now, "exp": now + timedelta(minutes=minutes)}
    return jwt.encode(claims, secret, algorithm=ALGORITHM)


def read_token(token: str, secret: str) -> dict:
    """The token's claims. Raises jwt.InvalidTokenError if it is forged, damaged or expired."""
    return jwt.decode(token, secret, algorithms=[ALGORITHM], options={"require": ["sub", "role", "exp"]})


class LoginThrottle:
    def __init__(self, max_failures: int, minutes: int):
        self.max_failures = max_failures
        self.window = minutes * 60
        self.failures: dict[str, deque] = defaultdict(deque)

    def _prune(self, name: str) -> deque:
        recent = self.failures[name]
        while recent and time.monotonic() - recent[0] > self.window:
            recent.popleft()
        return recent

    def locked(self, name: str) -> bool:
        return len(self._prune(name)) >= self.max_failures

    def failed(self, name: str) -> None:
        self._prune(name).append(time.monotonic())

    def succeeded(self, name: str) -> None:
        self.failures.pop(name, None)
