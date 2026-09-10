"""Entry point Locomotive CTS Platform.

Menjalankan API sekaligus menyajikan frontend statis:

    python main.py
    uvicorn main:app --reload
"""

import sys
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).resolve().parent))

from app import db  # noqa: E402
from app.config import (  # noqa: E402
    APP_NAME,
    APP_VERSION,
    DB_PATH,
    FRONTEND_DIR,
)
from app.routers import (  # noqa: E402
    auth,
    components,
    dashboard,
    imports,
    locomotives,
    master,
    reports,
    users,
)
from app.security import seed_users  # noqa: E402

app = FastAPI(
    title=APP_NAME,
    version=APP_VERSION,
    description=(
        "API untuk data perawatan lokomotif: autentikasi, import Excel, "
        "pencarian, filter, dan visualisasi."
    ),
)

# Frontend (Vercel) berada di origin berbeda, jadi CORS harus mengizinkannya.
# CORS_ORIGINS = daftar origin dipisah koma, mis:
#   https://rail-comp-tracker.vercel.app,https://app.contoh.com
# Default "*" memudahkan awal; sempitkan ke domain Vercel Anda di produksi.
# Auth memakai Bearer token (bukan cookie), jadi allow_credentials=False aman.
import os as _os  # noqa: E402

_cors = _os.getenv("CORS_ORIGINS", "*").strip()
_cors_origins = ["*"] if _cors in ("", "*") else [o.strip() for o in _cors.split(",") if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(locomotives.router)
app.include_router(components.router)
app.include_router(imports.router)
app.include_router(master.router)
app.include_router(reports.router)
app.include_router(users.router)


def bootstrap() -> None:
    """Pastikan tabel dan akun awal ada sebelum request pertama dilayani."""
    db.init_db()
    seed_users()


bootstrap()


@app.on_event("shutdown")
def _shutdown() -> None:
    # Kembalikan koneksi & matikan thread pool dengan rapi.
    db.close_pool()


PROCESS_STARTED_AT = datetime.now(timezone.utc)


def code_last_modified() -> datetime:
    """Waktu modifikasi terakhir dari source backend.

    Kalau nilainya lebih baru daripada waktu proses dijalankan, artinya server
    masih memuat kode lama dan perlu di-restart. Ini penyebab tersering
    "sudah diperbaiki tapi masih error".
    """
    newest = 0.0

    for path in Path(__file__).resolve().parent.rglob("*.py"):
        try:
            newest = max(newest, path.stat().st_mtime)
        except OSError:
            continue

    return datetime.fromtimestamp(newest, tz=timezone.utc)


@app.get("/api/health")
def health():
    tables = {}

    for table in (
        "maintenance_events",
        "equipment_components",
        "sheet_availability",
        "ingestion_history",
        "app_users",
    ):
        try:
            tables[table] = db.scalar(f"SELECT COUNT(*) FROM {table}")
        except Exception:  # noqa: BLE001
            tables[table] = None

    code_mtime = code_last_modified()
    stale = code_mtime > PROCESS_STARTED_AT

    return {
        "status": "ok",
        "app": APP_NAME,
        "version": APP_VERSION,
        "database": str(DB_PATH),
        "tables": tables,
        "server_started_at": PROCESS_STARTED_AT.isoformat(),
        "code_modified_at": code_mtime.isoformat(),
        "code_stale": stale,
    }


@app.api_route(
    "/api/{path:path}",
    methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
    include_in_schema=False,
)
def api_not_found(path: str):
    """Jaring pengaman untuk path /api yang tidak dikenal.

    Tanpa ini, POST ke endpoint yang belum terdaftar akan jatuh ke fallback SPA
    (yang hanya melayani GET) dan menghasilkan 405 Method Not Allowed - pesan
    yang menyesatkan. Penyebab tersering: server belum di-restart setelah route
    baru ditambahkan.
    """
    return JSONResponse(
        {
            "detail": (
                f"Endpoint /api/{path} tidak dikenal. "
                "Kalau route ini baru ditambahkan, restart server terlebih dahulu."
            )
        },
        status_code=404,
    )


class RevalidatingStaticFiles(StaticFiles):
    """Aset selalu divalidasi ulang ke server sebelum dipakai.

    Tanpa ini peramban menyimpan `app.js` lama di cache dan perubahan frontend
    tidak muncul sampai hard refresh - penyebab tersering keluhan "fiturnya
    belum ada padahal sudah dibuat".

    ETag tetap dikirim, jadi kalau file memang tidak berubah jawabannya 304 dan
    tidak ada biaya transfer.
    """

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache, must-revalidate"

        return response


def html_response(name: str) -> FileResponse:
    return FileResponse(
        FRONTEND_DIR / name,
        headers={"Cache-Control": "no-cache, must-revalidate"},
    )


# Frontend hanya disajikan bila hasil build-nya benar-benar ada. Kalau tidak,
# backend berjalan sebagai API mandiri (standalone) — berguna saat frontend
# di-deploy terpisah atau saat mengembangkan API saja.
SERVE_FRONTEND = FRONTEND_DIR.is_dir() and (FRONTEND_DIR / "index.html").is_file()
_ASSETS_DIR = FRONTEND_DIR / "assets"

if SERVE_FRONTEND:
    if _ASSETS_DIR.is_dir():
        app.mount(
            "/assets",
            RevalidatingStaticFiles(directory=_ASSETS_DIR),
            name="assets",
        )

    @app.get("/", include_in_schema=False)
    def index():
        return html_response("index.html")

    @app.get("/{path:path}", include_in_schema=False)
    def spa_fallback(path: str):
        candidate = FRONTEND_DIR / path

        if candidate.is_file():
            return FileResponse(candidate)

        if path.startswith("api/"):
            return JSONResponse({"detail": "Not Found"}, status_code=404)

        # Rute klien (mis. /login, /lokomotif) dilayani index.html; react-router
        # yang menentukan halaman mana yang tampil.
        return html_response("index.html")

else:

    @app.get("/", include_in_schema=False)
    def api_root():
        """Mode API mandiri: tidak ada frontend yang di-bundle."""
        return {
            "app": APP_NAME,
            "version": APP_VERSION,
            "mode": "api-only",
            "docs": "/docs",
            "health": "/api/health",
        }


if __name__ == "__main__":
    import os

    import uvicorn

    # Cloud Run menyuntikkan $PORT dan mengharuskan bind ke 0.0.0.0.
    uvicorn.run(
        "main:app",
        host=os.getenv("HOST", "0.0.0.0"),
        port=int(os.getenv("PORT", "8000")),
        reload=False,
    )
