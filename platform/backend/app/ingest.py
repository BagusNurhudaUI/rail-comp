"""Ingestion hasil parsing ke SQLite, transaksional dan idempoten."""

from datetime import datetime, timezone

from . import db
from .config import SCHEMA_VERSION
from .excel_parser import parse_workbook

EVENT_FIELDS = [
    "source_file",
    "source_year",
    "source_sheet",
    "block_index",
    "no_seri_lokomotif",
    "lokomotif_no",
    "lokomotif_key",
    "dipo_induk",
    "jenis_perawatan",
    "program_bulan",
    "ganti_di_dipo",
    "masuk",
    "keluar",
    "masuk_source",
    "keluar_source",
    "tahun_maintenance",
    "component_count",
]

EVENT_UPDATE_FIELDS = [
    f for f in EVENT_FIELDS if f not in ("source_file", "source_sheet", "block_index")
]

UPSERT_EVENT_SQL = f"""
INSERT INTO maintenance_events (
    {", ".join(EVENT_FIELDS)}, created_at, updated_at
)
VALUES ({", ".join(["?"] * (len(EVENT_FIELDS) + 2))})
ON CONFLICT (source_file, source_sheet, block_index)
DO UPDATE SET
    {", ".join(f"{f} = excluded.{f}" for f in EVENT_UPDATE_FIELDS)},
    updated_at = excluded.updated_at;
"""

COMPONENT_FIELDS = [
    "maintenance_event_id",
    "source_file",
    "source_year",
    "source_sheet",
    "block_index",
    "lokomotif_no",
    "lokomotif_key",
    "masuk",
    "keluar",
    "tahun_maintenance",
    "component_no",
    "component_name",
    "asal_kode_cetak",
    "asal_no_manuf",
    "pengganti_kode_cetak",
    "pengganti_no_manuf",
    "keterangan",
]

INSERT_COMPONENT_SQL = f"""
INSERT INTO equipment_components ({", ".join(COMPONENT_FIELDS)})
VALUES ({", ".join(["?"] * len(COMPONENT_FIELDS))});
"""

UPSERT_AVAILABILITY_SQL = """
INSERT INTO sheet_availability (
    source_file, source_year, sheet_index, source_sheet,
    block_count, template_block_count, event_count, component_count,
    status, message, scanned_at
)
VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
ON CONFLICT (source_file, source_sheet)
DO UPDATE SET
    source_year = excluded.source_year,
    sheet_index = excluded.sheet_index,
    block_count = excluded.block_count,
    template_block_count = excluded.template_block_count,
    event_count = excluded.event_count,
    component_count = excluded.component_count,
    status = excluded.status,
    message = excluded.message,
    scanned_at = excluded.scanned_at;
"""


def _text(value):
    """Nomor komponen terbaca float oleh pandas: 1.0 harus tersimpan "1"."""
    if value is None:
        return None

    if isinstance(value, float):
        if value != value:  # NaN
            return None

        if value.is_integer():
            return str(int(value))

        return str(value)

    if isinstance(value, (int,)):
        return str(value)

    text = str(value).strip()

    return text or None


def ingest_workbook(excel_path, actor: str | None = None) -> dict:
    """Parse lalu tulis satu workbook. Aman dijalankan berulang."""
    # Dicatat sebelum parsing: bagian terlama justru membaca worksheet, jadi
    # menghitungnya dari sini membuat durasi di riwayat mencerminkan waktu
    # yang benar-benar dirasakan pengguna.
    started_at = datetime.now(timezone.utc).isoformat()

    parsed = parse_workbook(excel_path)

    source_file = parsed["source_file"]

    log_id = db.execute(
        """
        INSERT INTO ingestion_history (
            source_file, source_year, schema_version, started_at, status
        )
        VALUES (?, ?, ?, ?, 'RUNNING')
        """,
        (source_file, parsed["source_year"], SCHEMA_VERSION, started_at),
    )

    conn = db.connect()

    try:
        conn.execute("BEGIN")

        # Blok yang hilang dari file terbaru (mis. sheet dihapus) ikut dibersihkan.
        conn.execute(
            "DELETE FROM maintenance_events WHERE source_file = ?", (source_file,)
        )
        conn.execute(
            "DELETE FROM equipment_components WHERE source_file = ?", (source_file,)
        )

        components_by_block: dict[tuple[str, int], list[dict]] = {}

        for component in parsed["components"]:
            key = (component["source_sheet"], component["block_index"])
            components_by_block.setdefault(key, []).append(component)

        total_components = 0

        for event in parsed["events"]:
            conn.execute(
                UPSERT_EVENT_SQL,
                tuple(
                    _text(event[field])
                    if field
                    not in (
                        "source_year",
                        "block_index",
                        "tahun_maintenance",
                        "component_count",
                    )
                    else event[field]
                    for field in EVENT_FIELDS
                )
                + (started_at, started_at),
            )

            # Kunci pencarian wajib memakai bentuk yang sama dengan yang ditulis:
            # _text() memangkas spasi, sehingga mencari dengan nilai mentah akan
            # meleset untuk sheet seperti "Sheet1 " dan mengembalikan None.
            row = conn.execute(
                """
                SELECT id FROM maintenance_events
                WHERE source_file = ? AND source_sheet = ? AND block_index = ?
                """,
                (
                    _text(event["source_file"]),
                    _text(event["source_sheet"]),
                    event["block_index"],
                ),
            ).fetchone()

            if row is None:
                raise RuntimeError(
                    "Event gagal tersimpan untuk "
                    f"{event['source_file']} / {event['source_sheet']} "
                    f"blok {event['block_index']}"
                )

            event_id = row["id"]

            block_rows = components_by_block.get(
                (event["source_sheet"], event["block_index"]), []
            )

            if not block_rows:
                continue

            records = [
                tuple(
                    [event_id]
                    + [
                        row[field]
                        if field
                        in ("source_year", "block_index", "tahun_maintenance")
                        else _text(row[field])
                        for field in COMPONENT_FIELDS[1:]
                    ]
                )
                for row in block_rows
            ]

            conn.executemany(INSERT_COMPONENT_SQL, records)
            total_components += len(records)

        scanned_at = datetime.now(timezone.utc).isoformat()

        for sheet in parsed["availability"]:
            conn.execute(
                UPSERT_AVAILABILITY_SQL,
                (
                    sheet["source_file"],
                    sheet["source_year"],
                    sheet["sheet_index"],
                    sheet["source_sheet"],
                    sheet["block_count"],
                    sheet["template_block_count"],
                    sheet["event_count"],
                    sheet["component_count"],
                    sheet["status"],
                    sheet["message"],
                    scanned_at,
                ),
            )

        conn.execute("COMMIT")

        summary = {
            "source_file": source_file,
            "source_year": parsed["source_year"],
            "status": "SUCCESS",
            "sheets": len(parsed["availability"]),
            "events": len(parsed["events"]),
            "components": total_components,
            "templates": sum(
                s["template_block_count"] for s in parsed["availability"]
            ),
            "problem_sheets": [
                s for s in parsed["availability"] if s["status"] != "OK"
            ],
        }

        conn.execute(
            """
            UPDATE ingestion_history
            SET finished_at = ?, sheet_count = ?, event_count = ?,
                component_count = ?, status = 'SUCCESS'
            WHERE id = ?
            """,
            (
                datetime.now(timezone.utc).isoformat(),
                summary["sheets"],
                summary["events"],
                summary["components"],
                log_id,
            ),
        )

        return summary

    except Exception as exc:
        conn.execute("ROLLBACK")

        conn.execute(
            """
            UPDATE ingestion_history
            SET finished_at = ?, status = 'FAILED', error_message = ?
            WHERE id = ?
            """,
            (datetime.now(timezone.utc).isoformat(), str(exc), log_id),
        )

        raise

    finally:
        conn.close()
