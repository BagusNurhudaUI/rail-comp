"""Akses database — mendukung SQLite (dev lokal) dan PostgreSQL (produksi).

Backend dipilih otomatis lewat env `DATABASE_URL`:

* diawali `postgres://` / `postgresql://`  -> PostgreSQL via psycopg
* kosong                                    -> SQLite pada `KAI_DB_PATH`

Seluruh kode aplikasi memakai placeholder gaya SQLite (`?`) dan API koneksi
mirip-sqlite (`conn.execute(...).fetchone()`, `conn.executemany(...)`). Untuk
PostgreSQL, adapter tipis di bawah menerjemahkan placeholder ke `%s`,
mengubah `PRAGMA` menjadi no-op, dan meneruskan `BEGIN/COMMIT/ROLLBACK` apa
adanya (didukung psycopg pada mode autocommit).
"""

import os
import sqlite3
from contextlib import contextmanager
from typing import Any, Iterable

from .config import DB_PATH

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
IS_POSTGRES = DATABASE_URL.startswith(("postgres://", "postgresql://"))

# Token primary key auto-increment berbeda antar dialek.
_AUTO_PK = (
    "id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY"
    if IS_POSTGRES
    else "id INTEGER PRIMARY KEY AUTOINCREMENT"
)


# ── PostgreSQL: adapter agar terlihat seperti koneksi sqlite3 ──────────

if IS_POSTGRES:
    from psycopg.rows import dict_row

    def _translate(sql: str) -> str:
        """`?` -> `%s`. Aman karena SQL aplikasi tak memuat `?` literal."""
        return sql.replace("?", "%s")

    # Connection pool. Tanpa ini setiap query membuka koneksi baru (~400 ms di
    # PostgreSQL karena handshake + auth), sehingga satu halaman dashboard bisa
    # makan beberapa detik. Pool menyimpan koneksi hangat dan memakainya ulang.
    _POOL = None

    def _get_pool():
        global _POOL

        if _POOL is None:
            from psycopg_pool import ConnectionPool

            _POOL = ConnectionPool(
                DATABASE_URL,
                min_size=int(os.getenv("KAI_DB_POOL_MIN", "1")),
                max_size=int(os.getenv("KAI_DB_POOL_MAX", "8")),
                kwargs={"autocommit": True, "row_factory": dict_row},
                timeout=30,
                open=True,
            )

        return _POOL

    class _PgConnection:
        """Antarmuka mirip sqlite3.Connection di atas koneksi dari pool.

        Memakai satu cursor yang dipakai ulang. Aman karena setiap pemanggil
        selalu memfetch hasilnya (fetchone/fetchall) sebelum execute berikutnya
        — tidak ada iterasi cursor yang tumpang tindih di basis kode ini.

        Autocommit aktif, sehingga BEGIN/COMMIT/ROLLBACK manual yang dikirim
        modul ingestion membuka dan menutup transaksi eksplisit, persis seperti
        SQLite dengan isolation_level=None. Saat close(), koneksi dikembalikan
        ke pool (pool me-reset/rollback transaksi yang tersisa), bukan ditutup.
        """

        def __init__(self):
            self._pool = _get_pool()
            self._conn = self._pool.getconn()
            self._cursor = self._conn.cursor()

        def execute(self, sql: str, params: Iterable[Any] = ()):
            # PRAGMA tidak ada di PostgreSQL; abaikan dengan aman.
            if sql.strip().upper().startswith("PRAGMA"):
                return self._cursor

            self._cursor.execute(_translate(sql), tuple(params) if params else None)
            return self._cursor

        def executemany(self, sql: str, seq):
            self._cursor.executemany(_translate(sql), [tuple(row) for row in seq])
            return self._cursor

        def close(self):
            try:
                self._cursor.close()
            except Exception:  # noqa: BLE001
                pass

            self._pool.putconn(self._conn)

    def _raw_connect():
        return _PgConnection()

else:

    def _raw_connect():
        conn = sqlite3.connect(DB_PATH, isolation_level=None, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA busy_timeout = 10000;")
        return conn


def connect():
    return _raw_connect()


def close_pool() -> None:
    """Tutup connection pool dengan rapi (mematikan thread pemeliharaannya).

    Dipanggil saat shutdown aplikasi dan lewat atexit untuk skrip singkat, agar
    tidak muncul peringatan 'couldn't stop thread' saat proses keluar.
    """
    global _POOL

    if IS_POSTGRES and _POOL is not None:
        _POOL.close()
        _POOL = None


if IS_POSTGRES:
    import atexit

    atexit.register(close_pool)


@contextmanager
def get_db():
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def transaction():
    """Blok transaksi eksplisit yang portabel.

    Menggantikan `conn.execute("BEGIN")` … `COMMIT` yang tersebar, sehingga
    ingestion dan flush tidak perlu tahu dialek yang dipakai.
    """
    conn = connect()

    try:
        conn.execute("BEGIN")
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def query(sql: str, params: Iterable[Any] = ()) -> list[dict]:
    with get_db() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
        return [dict(row) for row in rows]


def query_one(sql: str, params: Iterable[Any] = ()) -> dict | None:
    with get_db() as conn:
        row = conn.execute(sql, tuple(params)).fetchone()
        return dict(row) if row else None


def scalar(sql: str, params: Iterable[Any] = (), default: Any = 0) -> Any:
    with get_db() as conn:
        row = conn.execute(sql, tuple(params)).fetchone()

    if row is None:
        return default

    value = row["count"] if isinstance(row, dict) and "count" in row else _first(row)

    return default if value is None else value


def _first(row):
    """Ambil kolom pertama, apa pun tipe row-nya (sqlite Row / dict)."""
    if isinstance(row, dict):
        return next(iter(row.values()))

    return row[0]


def execute(sql: str, params: Iterable[Any] = ()) -> int | None:
    """Jalankan satu statement; kembalikan id baris baru untuk INSERT.

    Pada PostgreSQL, `INSERT` disisipi `RETURNING id` karena psycopg tidak
    punya `lastrowid`.
    """
    if IS_POSTGRES and sql.strip().upper().startswith("INSERT") and "RETURNING" not in sql.upper():
        with get_db() as conn:
            row = conn.execute(sql.rstrip().rstrip(";") + " RETURNING id", tuple(params)).fetchone()
            return row["id"] if row else None

    with get_db() as conn:
        cursor = conn.execute(sql, tuple(params))
        return getattr(cursor, "lastrowid", None)


# ── Skema ──────────────────────────────────────────────────────────────

from .master_schema import ensure_master_schema  # noqa: E402

CREATE_USERS_SQL = f"""
CREATE TABLE IF NOT EXISTS app_users (
    {_AUTO_PK},
    email TEXT NOT NULL UNIQUE,
    full_name TEXT NOT NULL,
    title TEXT,
    role TEXT NOT NULL DEFAULT 'viewer',
    password_hash TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_login_at TEXT
);
"""

CREATE_ACTIVITY_SQL = f"""
CREATE TABLE IF NOT EXISTS activity_log (
    {_AUTO_PK},
    created_at TEXT NOT NULL,
    actor TEXT,
    action TEXT NOT NULL,
    title TEXT NOT NULL,
    detail TEXT,
    level TEXT NOT NULL DEFAULT 'info'
);
"""

CREATE_EVENTS_SQL = f"""
CREATE TABLE IF NOT EXISTS maintenance_events (
    {_AUTO_PK},
    source_file TEXT NOT NULL,
    source_year INTEGER,
    source_sheet TEXT NOT NULL,
    block_index INTEGER NOT NULL,
    no_seri_lokomotif TEXT,
    lokomotif_no TEXT,
    lokomotif_key TEXT,
    dipo_induk TEXT,
    jenis_perawatan TEXT,
    program_bulan TEXT,
    ganti_di_dipo TEXT,
    masuk TEXT,
    keluar TEXT,
    masuk_source TEXT,
    keluar_source TEXT,
    tahun_maintenance INTEGER,
    component_count INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    UNIQUE (source_file, source_sheet, block_index)
);
"""

CREATE_COMPONENTS_SQL = f"""
CREATE TABLE IF NOT EXISTS equipment_components (
    {_AUTO_PK},
    maintenance_event_id INTEGER NOT NULL,
    source_file TEXT NOT NULL,
    source_year INTEGER,
    source_sheet TEXT NOT NULL,
    block_index INTEGER NOT NULL,
    lokomotif_no TEXT,
    lokomotif_key TEXT,
    masuk TEXT,
    keluar TEXT,
    tahun_maintenance INTEGER,
    component_no TEXT,
    component_name TEXT,
    asal_kode_cetak TEXT,
    asal_no_manuf TEXT,
    pengganti_kode_cetak TEXT,
    pengganti_no_manuf TEXT,
    keterangan TEXT
);
"""

CREATE_AVAILABILITY_SQL = f"""
CREATE TABLE IF NOT EXISTS sheet_availability (
    {_AUTO_PK},
    source_file TEXT NOT NULL,
    source_year INTEGER,
    sheet_index INTEGER,
    source_sheet TEXT NOT NULL,
    block_count INTEGER DEFAULT 0,
    template_block_count INTEGER DEFAULT 0,
    event_count INTEGER DEFAULT 0,
    component_count INTEGER DEFAULT 0,
    status TEXT NOT NULL,
    message TEXT,
    scanned_at TEXT NOT NULL,
    UNIQUE (source_file, source_sheet)
);
"""

CREATE_LOG_SQL = f"""
CREATE TABLE IF NOT EXISTS ingestion_history (
    {_AUTO_PK},
    source_file TEXT NOT NULL,
    source_year INTEGER,
    schema_version INTEGER,
    started_at TEXT NOT NULL,
    finished_at TEXT,
    sheet_count INTEGER DEFAULT 0,
    event_count INTEGER DEFAULT 0,
    component_count INTEGER DEFAULT 0,
    status TEXT NOT NULL,
    error_message TEXT
);
"""

INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_events_loco ON maintenance_events(lokomotif_key);",
    "CREATE INDEX IF NOT EXISTS idx_events_tahun ON maintenance_events(tahun_maintenance);",
    "CREATE INDEX IF NOT EXISTS idx_components_event ON equipment_components(maintenance_event_id);",
    "CREATE INDEX IF NOT EXISTS idx_components_loco ON equipment_components(lokomotif_key);",
    "CREATE INDEX IF NOT EXISTS idx_components_name ON equipment_components(component_name);",
    "CREATE INDEX IF NOT EXISTS idx_components_asal ON equipment_components(asal_kode_cetak);",
]


def init_db() -> None:
    if not IS_POSTGRES:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with get_db() as conn:
        for ddl in (
            CREATE_EVENTS_SQL,
            CREATE_COMPONENTS_SQL,
            CREATE_AVAILABILITY_SQL,
            CREATE_LOG_SQL,
            CREATE_USERS_SQL,
            CREATE_ACTIVITY_SQL,
        ):
            conn.execute(ddl)

        for statement in INDEXES:
            conn.execute(statement)

        ensure_master_schema(conn)
