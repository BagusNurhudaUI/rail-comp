"""Dependency FastAPI: autentikasi bearer token dan kontrol peran."""

from datetime import datetime, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from . import db
from .security import decode_token

bearer_scheme = HTTPBearer(auto_error=False)

ROLE_RANK = {"viewer": 1, "supervisor": 2, "admin": 3}


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tidak ditemukan",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token tidak valid atau sudah kedaluwarsa",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query_one(
        "SELECT id, email, full_name, title, role, is_active FROM app_users WHERE id = ?",
        (payload["sub"],),
    )

    if user is None or not user["is_active"]:
        raise HTTPException(status_code=401, detail="Akun tidak aktif")

    return user


def require_role(minimum: str):
    """Batas minimal peran: viewer < supervisor < admin."""

    def checker(user: dict = Depends(get_current_user)) -> dict:
        if ROLE_RANK.get(user["role"], 0) < ROLE_RANK[minimum]:
            raise HTTPException(
                status_code=403,
                detail=f"Butuh peran minimal {minimum}",
            )

        return user

    return checker


def log_activity(
    action: str,
    title: str,
    detail: str | None = None,
    actor: str | None = None,
    level: str = "info",
) -> None:
    db.execute(
        """
        INSERT INTO activity_log (created_at, actor, action, title, detail, level)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            datetime.now(timezone.utc).isoformat(),
            actor,
            action,
            title,
            detail,
            level,
        ),
    )
