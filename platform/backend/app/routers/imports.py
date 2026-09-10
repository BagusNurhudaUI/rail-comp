"""Import Excel: unggah file baru atau proses ulang file yang sudah ada."""

import shutil
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel

from .. import db
from ..config import DATA_DIR, FILE_PATTERN, UPLOAD_DIR
from ..deps import log_activity, require_role
from ..ingest import ingest_workbook

router = APIRouter(prefix="/api/imports", tags=["imports"])

ALLOWED_SUFFIXES = {".xlsx", ".xlsm"}


class ReingestRequest(BaseModel):
    file_name: str


class FlushRequest(BaseModel):
    """Konfirmasi wajib supaya penghapusan tidak terjadi karena salah klik.

    `scope` menentukan seberapa luas penghapusannya:

    * `all`         - seluruh data, termasuk master SAP dan catatan log
    * `maintenance` - hanya data hasil Excel perawatan
    * `master`      - hanya master lokomotif dan katalog komponen

    Akun pengguna tidak pernah ikut terhapus pada scope manapun.
    """

    confirm: str
    scope: str = "all"
    source_file: str | None = None
    year: int | None = None


@router.get("/history")
def history(user: dict = Depends(require_role("viewer"))):
    return {
        "items": db.query(
            """
            SELECT id, source_file, source_year, schema_version, started_at,
                   finished_at, sheet_count, event_count, component_count,
                   status, error_message
            FROM ingestion_history
            ORDER BY id DESC
            LIMIT 50
            """
        )
    }


@router.get("/sources")
def sources(user: dict = Depends(require_role("viewer"))):
    """File Excel yang tersedia di folder data, beserta status ingest terakhirnya."""
    items = []

    for path in sorted(DATA_DIR.glob(FILE_PATTERN)):
        if path.name.startswith("~$"):
            continue

        last = db.query_one(
            """
            SELECT status, finished_at, event_count, component_count
            FROM ingestion_history
            WHERE source_file = ?
            ORDER BY id DESC LIMIT 1
            """,
            (path.name,),
        )

        stat = path.stat()

        items.append(
            {
                "file_name": path.name,
                "size_kb": round(stat.st_size / 1024),
                "modified_at": datetime.fromtimestamp(stat.st_mtime).isoformat(
                    timespec="seconds"
                ),
                "last_status": last["status"] if last else None,
                "last_run": last["finished_at"] if last else None,
                "events": last["event_count"] if last else 0,
                "components": last["component_count"] if last else 0,
            }
        )

    return {"items": items}


@router.post("/upload")
def upload(
    file: UploadFile = File(...),
    user: dict = Depends(require_role("supervisor")),
):
    suffix = "." + file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""

    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400, detail="Hanya menerima file .xlsx atau .xlsm"
        )

    target = UPLOAD_DIR / file.filename

    with target.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    try:
        summary = ingest_workbook(target, actor=user["full_name"])
    except Exception as exc:  # noqa: BLE001
        log_activity(
            action="IMPORT",
            title=f"Import {file.filename} gagal",
            detail=str(exc),
            actor=user["full_name"],
            level="critical",
        )
        raise HTTPException(status_code=422, detail=f"Gagal memproses file: {exc}")

    log_activity(
        action="IMPORT",
        title=f"{file.filename} diimpor lewat UI",
        detail=f"{summary['events']} perawatan, {summary['components']} komponen",
        actor=user["full_name"],
        level="success",
    )

    return summary


CONFIRM_PHRASE = "HAPUS"


@router.post("/flush")
def flush(payload: FlushRequest, user: dict = Depends(require_role("admin"))):
    """Kosongkan data. Akun pengguna (`app_users`) selalu dipertahankan.

    Tabel dihapus dari anak ke induk supaya tidak ada baris yatim sekalipun
    proses terhenti di tengah jalan.
    """
    if payload.confirm != CONFIRM_PHRASE:
        raise HTTPException(
            status_code=400,
            detail=f"Ketik {CONFIRM_PHRASE} pada kolom konfirmasi untuk melanjutkan",
        )

    if payload.scope not in ("all", "maintenance", "master"):
        raise HTTPException(status_code=400, detail="Scope tidak dikenal")

    if payload.source_file and payload.year:
        raise HTTPException(
            status_code=400, detail="Pilih salah satu: per berkas atau per tahun"
        )

    per_file = bool(payload.source_file or payload.year)

    if per_file and payload.scope != "maintenance":
        raise HTTPException(
            status_code=400,
            detail="Penyaringan per berkas hanya berlaku untuk scope maintenance",
        )

    if payload.source_file:
        scope_label = payload.source_file
        where, params = "WHERE source_file = ?", (payload.source_file,)
    elif payload.year:
        scope_label = f"tahun {payload.year}"
        where, params = "WHERE source_year = ?", (payload.year,)
    else:
        scope_label = {
            "all": "seluruh data",
            "maintenance": "data perawatan",
            "master": "master data",
        }[payload.scope]
        where, params = "", ()

    MAINTENANCE = ["equipment_components", "maintenance_events", "sheet_availability"]
    MASTER = ["components", "locomotives"]
    LOGS = ["ingestion_history", "activity_log"]

    if payload.scope == "maintenance":
        tables = MAINTENANCE
    elif payload.scope == "master":
        tables = MASTER
    else:
        tables = MAINTENANCE + MASTER + LOGS

    started_at = datetime.now(timezone.utc).isoformat()

    before = {
        table: db.scalar(f"SELECT COUNT(*) FROM {table} {where}", params)
        for table in tables
    }

    if not any(before.values()):
        raise HTTPException(status_code=404, detail=f"Tidak ada data untuk {scope_label}")

    conn = db.connect()

    try:
        conn.execute("BEGIN")

        for table in tables:
            conn.execute(f"DELETE FROM {table} {where}", params)

        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    # VACUUM hanya relevan (dan aman dijalankan begini) di SQLite; pada
    # PostgreSQL autovacuum menangani ruang secara otomatis.
    if not db.IS_POSTGRES:
        try:
            with db.get_db() as vacuum_conn:
                vacuum_conn.execute("VACUUM")
        except Exception:  # noqa: BLE001 - VACUUM gagal tidak membatalkan flush
            pass

    # Dicatat setelah penghapusan supaya barisnya tidak ikut terhapus sendiri.
    db.execute(
        """
        INSERT INTO ingestion_history (
            source_file, source_year, schema_version, started_at, finished_at,
            sheet_count, event_count, component_count, status, error_message
        )
        VALUES (?, ?, NULL, ?, ?, ?, ?, ?, 'FLUSHED', ?)
        """,
        (
            payload.source_file or scope_label,
            payload.year,
            started_at,
            datetime.now(timezone.utc).isoformat(),
            before.get("sheet_availability", 0),
            before.get("maintenance_events", 0),
            before.get("equipment_components", 0),
            f"Dikosongkan oleh {user['full_name']}",
        ),
    )

    log_activity(
        action="FLUSH",
        title=f"Data dikosongkan: {scope_label}",
        detail=", ".join(f"{table} {count}" for table, count in before.items() if count),
        actor=user["full_name"],
        level="warning",
    )

    return {
        "status": "FLUSHED",
        "scope": payload.scope,
        "scope_label": scope_label,
        "deleted": before,
        "total": sum(before.values()),
        "kept": ["app_users"],
    }


@router.post("/reingest")
def reingest(
    payload: ReingestRequest,
    user: dict = Depends(require_role("supervisor")),
):
    candidates = [DATA_DIR / payload.file_name, UPLOAD_DIR / payload.file_name]
    path = next((p for p in candidates if p.exists()), None)

    if path is None:
        raise HTTPException(status_code=404, detail="File tidak ditemukan")

    try:
        summary = ingest_workbook(path, actor=user["full_name"])
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Gagal memproses file: {exc}")

    log_activity(
        action="IMPORT",
        title=f"{path.name} diproses ulang",
        detail=f"{summary['events']} perawatan, {summary['components']} komponen",
        actor=user["full_name"],
        level="success",
    )

    return summary
