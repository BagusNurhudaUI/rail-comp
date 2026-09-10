"""Password hashing, JWT, dan seed user awal."""

import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from . import db
from .config import ACCESS_TOKEN_EXPIRE_MINUTES, JWT_ALGORITHM, SECRET_KEY

PBKDF2_ROUNDS = 180_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt, PBKDF2_ROUNDS
    )
    return f"pbkdf2_sha256${PBKDF2_ROUNDS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False

    if algorithm != "pbkdf2_sha256":
        return False

    expected = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        bytes.fromhex(salt_hex),
        int(rounds),
    )

    return hmac.compare_digest(expected.hex(), digest_hex)


def create_access_token(user: dict) -> tuple[str, int]:
    expires_in = ACCESS_TOKEN_EXPIRE_MINUTES * 60
    now = datetime.now(timezone.utc)

    payload = {
        "sub": str(user["id"]),
        "email": user["email"],
        "role": user["role"],
        "name": user["full_name"],
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(seconds=expires_in)).timestamp()),
    }

    token = jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)

    return token, expires_in


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None


DEFAULT_USERS = [
    {
        "email": "admin@kai.id",
        "full_name": "Admin KAI",
        "title": "Administrator KAI",
        "role": "admin",
        "password": "ayamayam123",
    },
]


def seed_users() -> None:
    """Buat akun awal hanya ketika tabel pengguna benar-benar kosong.

    Akun tambahan dibuat lewat halaman Pengguna, bukan di sini, supaya
    menghapus seorang pengguna tidak membuatnya muncul lagi saat restart.
    """
    if db.scalar("SELECT COUNT(*) FROM app_users"):
        return

    now = datetime.now(timezone.utc).isoformat()

    for user in DEFAULT_USERS:
        db.execute(
            """
            INSERT INTO app_users (
                email, full_name, title, role, password_hash, is_active, created_at
            )
            VALUES (?, ?, ?, ?, ?, 1, ?)
            """,
            (
                user["email"],
                user["full_name"],
                user["title"],
                user["role"],
                hash_password(user["password"]),
                now,
            ),
        )
