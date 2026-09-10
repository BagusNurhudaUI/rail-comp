"""Login, profil, dan ganti password."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr, Field

from .. import db
from ..deps import get_current_user, log_activity
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class PasswordChangeRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


@router.post("/login")
def login(payload: LoginRequest):
    user = db.query_one(
        "SELECT * FROM app_users WHERE lower(email) = lower(?)",
        (payload.email,),
    )

    if user is None or not verify_password(payload.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Email atau password salah")

    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Akun dinonaktifkan")

    token, expires_in = create_access_token(user)

    db.execute(
        "UPDATE app_users SET last_login_at = ? WHERE id = ?",
        (datetime.now(timezone.utc).isoformat(), user["id"]),
    )

    log_activity(
        action="LOGIN",
        title=f"{user['full_name']} masuk ke platform",
        actor=user["full_name"],
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "full_name": user["full_name"],
            "title": user["title"],
            "role": user["role"],
        },
    }


@router.get("/me")
def me(user: dict = Depends(get_current_user)):
    return user


@router.post("/change-password")
def change_password(
    payload: PasswordChangeRequest,
    user: dict = Depends(get_current_user),
):
    record = db.query_one(
        "SELECT password_hash FROM app_users WHERE id = ?", (user["id"],)
    )

    if not verify_password(payload.current_password, record["password_hash"]):
        raise HTTPException(status_code=400, detail="Password lama tidak cocok")

    db.execute(
        "UPDATE app_users SET password_hash = ? WHERE id = ?",
        (hash_password(payload.new_password), user["id"]),
    )

    return {"status": "ok"}
