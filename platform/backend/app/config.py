"""Konfigurasi aplikasi.

Semua nilai bisa ditimpa lewat environment variable, sehingga deployment
tidak perlu mengubah kode.
"""

import os
import tempfile
from pathlib import Path

# platform/backend/app/config.py -> platform/backend/app -> backend -> platform -> KAI
APP_DIR = Path(__file__).resolve().parent
BACKEND_DIR = APP_DIR.parent
PLATFORM_DIR = BACKEND_DIR.parent
PROJECT_ROOT = PLATFORM_DIR.parent


def _load_dotenv() -> None:
    """Muat variabel dari berkas .env ke os.environ.

    Uvicorn dan os.getenv tidak membaca .env secara otomatis — hanya melihat
    environment proses. Fungsi ini dijalankan sebelum semua os.getenv di bawah,
    jadi nilai di .env sudah tersedia saat modul lain (mis. db.py) membacanya.

    Aturan: environment nyata menang atas .env (perilaku standar dotenv), jadi
    override lewat shell atau Cloud Run tetap didahulukan.
    """
    env_path = Path(os.getenv("KAI_ENV_FILE", BACKEND_DIR / ".env"))

    if not env_path.is_file():
        return

    for raw in env_path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()

        if not line or line.startswith("#") or "=" not in line:
            continue

        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        # Jangan timpa nilai yang sudah ada di environment nyata.
        os.environ.setdefault(key, value)


_load_dotenv()

# Hasil build React (rail-comp-tracker). Kalau belum di-build, backend jalan
# sebagai API mandiri — lihat SERVE_FRONTEND di main.py. Bisa ditimpa lewat env
# FRONTEND_DIR bila frontend di-deploy dari lokasi lain.
FRONTEND_DIR = Path(os.getenv("FRONTEND_DIR", PLATFORM_DIR / "frontend-dist"))

# Database hasil ingestion notebook dipakai langsung sebagai sumber data.
DB_PATH = Path(os.getenv("KAI_DB_PATH", PROJECT_ROOT / "kai.db"))

# Folder sumber Excel dan tempat menyimpan file yang diunggah lewat UI.
# Unggahan bersifat sementara (diparsing lalu tidak dibutuhkan lagi), jadi di
# Cloud Run diarahkan ke /tmp lewat env — direktori aplikasi bisa read-only.
DATA_DIR = Path(os.getenv("KAI_DATA_DIR", PROJECT_ROOT))
UPLOAD_DIR = Path(os.getenv("KAI_UPLOAD_DIR", BACKEND_DIR / "uploads"))

FILE_PATTERN = "Daftar Nomor Equipment Lokomotif *.xlsx"

# Master data SAP: 00 Loco.xlsx + satu file per jenis komponen.
COMPONENT_DIR = Path(os.getenv("KAI_COMPONENT_DIR", PROJECT_ROOT / "component"))

SECRET_KEY = os.getenv("KAI_SECRET_KEY", "kai-locomotive-cts-dev-secret-change-me")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("KAI_TOKEN_MINUTES", "720"))

SCHEMA_VERSION = 3
BLOCK_WIDTH = 7

APP_NAME = "Locomotive CTS Platform"
APP_VERSION = "1.0.0"

# Kalau direktori tujuan tidak bisa dibuat (mis. filesystem read-only), jatuh
# ke direktori sementara sistem supaya aplikasi tetap bisa start.
try:
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    UPLOAD_DIR = Path(tempfile.gettempdir()) / "kai-uploads"
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
