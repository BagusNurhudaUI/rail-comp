"""Manajemen pengguna dan peran (khusus admin)."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from .. import db
from ..deps import get_current_user, log_activity, require_role
from ..security import hash_password

router = APIRouter(prefix="/api/users", tags=["users"])

ROLES = ("viewer", "supervisor", "admin")


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2)
    title: str | None = None
    role: str = "viewer"
    password: str = Field(min_length=6)


class UserUpdate(BaseModel):
    full_name: str | None = None
    title: str | None = None
    role: str | None = None
    is_active: bool | None = None
    password: str | None = None


@router.get("")
def list_users(user: dict = Depends(get_current_user)):
    return {
        "items": db.query(
            """
            SELECT id, email, full_name, title, role, is_active,
                   created_at, last_login_at
            FROM app_users
            ORDER BY id
            """
        ),
        "roles": list(ROLES),
    }


@router.post("")
def create_user(payload: UserCreate, user: dict = Depends(require_role("admin"))):
    if payload.role not in ROLES:
        raise HTTPException(status_code=400, detail="Peran tidak dikenal")

    exists = db.query_one(
        "SELECT id FROM app_users WHERE lower(email) = lower(?)", (payload.email,)
    )

    if exists:
        raise HTTPException(status_code=409, detail="Email sudah terdaftar")

    user_id = db.execute(
        """
        INSERT INTO app_users (
            email, full_name, title, role, password_hash, is_active, created_at
        )
        VALUES (?, ?, ?, ?, ?, 1, ?)
        """,
        (
            payload.email,
            payload.full_name,
            payload.title,
            payload.role,
            hash_password(payload.password),
            datetime.now(timezone.utc).isoformat(),
        ),
    )

    log_activity(
        action="USER",
        title=f"Pengguna {payload.full_name} ditambahkan",
        detail=f"peran {payload.role}",
        actor=user["full_name"],
    )

    return {"id": user_id, "status": "created"}


@router.patch("/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdate,
    user: dict = Depends(require_role("admin")),
):
    target = db.query_one("SELECT * FROM app_users WHERE id = ?", (user_id,))

    if target is None:
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan")

    updates: list[str] = []
    params: list = []

    if payload.full_name:
        updates.append("full_name = ?")
        params.append(payload.full_name)

    if payload.title is not None:
        updates.append("title = ?")
        params.append(payload.title)

    if payload.role:
        if payload.role not in ROLES:
            raise HTTPException(status_code=400, detail="Peran tidak dikenal")

        updates.append("role = ?")
        params.append(payload.role)

    if payload.is_active is not None:
        if user_id == user["id"] and not payload.is_active:
            raise HTTPException(
                status_code=400, detail="Tidak bisa menonaktifkan akun sendiri"
            )

        updates.append("is_active = ?")
        params.append(1 if payload.is_active else 0)

    if payload.password:
        updates.append("password_hash = ?")
        params.append(hash_password(payload.password))

    if not updates:
        return {"status": "no-change"}

    db.execute(
        f"UPDATE app_users SET {', '.join(updates)} WHERE id = ?", params + [user_id]
    )

    log_activity(
        action="USER",
        title=f"Pengguna {target['full_name']} diperbarui",
        actor=user["full_name"],
    )

    return {"status": "updated"}


@router.delete("/{user_id}")
def delete_user(user_id: int, user: dict = Depends(require_role("admin"))):
    if user_id == user["id"]:
        raise HTTPException(status_code=400, detail="Tidak bisa menghapus akun sendiri")

    target = db.query_one("SELECT full_name FROM app_users WHERE id = ?", (user_id,))

    if target is None:
        raise HTTPException(status_code=404, detail="Pengguna tidak ditemukan")

    db.execute("DELETE FROM app_users WHERE id = ?", (user_id,))

    log_activity(
        action="USER",
        title=f"Pengguna {target['full_name']} dihapus",
        actor=user["full_name"],
        level="warning",
    )

    return {"status": "deleted"}
