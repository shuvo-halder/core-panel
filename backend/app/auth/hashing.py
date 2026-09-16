import argon2
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from backend.app.core.logging import logger


class PasswordHasher:
    """
    Argon2id cryptographic password hasher.
    Enforces time_cost=3, memory_cost=65536 (64MB), parallelism=4, 16-byte random salt.
    """

    def __init__(self) -> None:
        self._hasher = argon2.PasswordHasher(
            time_cost=3,
            memory_cost=65536,
            parallelism=4,
            hash_len=32,
            salt_len=16,
            type=argon2.Type.ID,
        )

    def hash(self, password: str) -> str:
        """Hash a plaintext password with a unique random salt."""
        if not password or len(password) < 8:
            raise ValueError("Password must be at least 8 characters in length.")
        return self._hasher.hash(password)

    def verify(self, password_hash: str, password: str) -> bool:
        """Verify a plaintext password against an Argon2id hash in constant time."""
        if not password_hash or not password:
            return False
        try:
            return self._hasher.verify(password_hash, password)
        except (VerifyMismatchError, InvalidHashError):
            return False
        except Exception as exc:
            logger.warning(f"Unexpected error during password verification: {exc}")
            return False

    def check_needs_rehash(self, password_hash: str) -> bool:
        """Check if the hash needs to be upgraded to new parameters."""
        try:
            return self._hasher.check_needs_rehash(password_hash)
        except Exception:
            return True


# Singleton password hasher
hasher = PasswordHasher()
