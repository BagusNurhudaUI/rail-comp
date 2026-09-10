"""Pencarian komponen, riwayat satu nomor equipment, dan daftar perawatan."""

import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from .. import db
from ..deps import get_current_user

router = APIRouter(prefix="/api", tags=["components"])

COMPONENT_SELECT = """
SELECT id, maintenance_event_id, source_file, source_year, source_sheet, block_index,
       lokomotif_no, lokomotif_key, masuk, keluar, tahun_maintenance,
       component_no, component_name,
       asal_kode_cetak, asal_no_manuf,
       pengganti_kode_cetak, pengganti_no_manuf, keterangan
FROM equipment_components
"""


def _component_filters(
    search: str | None,
    name: str | None,
    year: int | None,
    loco: str | None,
    source_file: str | None,
    status: str | None,
) -> tuple[str, list]:
    where = ["1=1"]
    params: list = []

    if search:
        like = f"%{search.upper()}%"
        where.append(
            """(
                upper(component_name) LIKE ?
                OR upper(asal_kode_cetak) LIKE ?
                OR upper(asal_no_manuf) LIKE ?
                OR upper(pengganti_kode_cetak) LIKE ?
                OR upper(pengganti_no_manuf) LIKE ?
                OR upper(lokomotif_no) LIKE ?
                OR upper(keterangan) LIKE ?
            )"""
        )
        params += [like] * 7

    if name:
        where.append("component_name = ?")
        params.append(name)

    if year:
        where.append("tahun_maintenance = ?")
        params.append(year)

    if loco:
        where.append("lokomotif_key = ?")
        params.append(loco)

    if source_file:
        where.append("source_file = ?")
        params.append(source_file)

    if status == "baru":
        where.append(
            "asal_kode_cetak IS NULL AND asal_no_manuf IS NULL "
            "AND (pengganti_kode_cetak IS NOT NULL OR pengganti_no_manuf IS NOT NULL)"
        )
    elif status == "diganti":
        where.append(
            "(asal_kode_cetak IS NOT NULL OR asal_no_manuf IS NOT NULL) "
            "AND (pengganti_kode_cetak IS NOT NULL OR pengganti_no_manuf IS NOT NULL)"
        )
    elif status == "tetap":
        where.append(
            "(asal_kode_cetak IS NOT NULL OR asal_no_manuf IS NOT NULL) "
            "AND pengganti_kode_cetak IS NULL AND pengganti_no_manuf IS NULL"
        )

    return " AND ".join(where), params


@router.get("/components")
def list_components(
    search: str | None = Query(None),
    name: str | None = Query(None),
    year: int | None = Query(None),
    loco: str | None = Query(None),
    source_file: str | None = Query(None),
    status: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=5, le=200),
    user: dict = Depends(get_current_user),
):
    clause, params = _component_filters(search, name, year, loco, source_file, status)

    total = db.scalar(
        f"SELECT COUNT(*) FROM equipment_components WHERE {clause}", params
    )

    items = db.query(
        f"""
        {COMPONENT_SELECT}
        WHERE {clause}
        ORDER BY tahun_maintenance DESC, id
        LIMIT ? OFFSET ?
        """,
        params + [page_size, (page - 1) * page_size],
    )

    for row in items:
        punya_asal = bool(row["asal_kode_cetak"] or row["asal_no_manuf"])
        punya_pengganti = bool(
            row["pengganti_kode_cetak"] or row["pengganti_no_manuf"]
        )

        if punya_asal and punya_pengganti:
            row["status"] = "Diganti"
        elif punya_pengganti:
            row["status"] = "Pemasangan baru"
        elif punya_asal:
            row["status"] = "Terpasang"
        else:
            row["status"] = "Catatan"

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
        "items": items,
    }


@router.get("/components/export")
def export_components(
    search: str | None = Query(None),
    name: str | None = Query(None),
    year: int | None = Query(None),
    loco: str | None = Query(None),
    source_file: str | None = Query(None),
    status: str | None = Query(None),
    user: dict = Depends(get_current_user),
):
    clause, params = _component_filters(search, name, year, loco, source_file, status)

    rows = db.query(
        f"{COMPONENT_SELECT} WHERE {clause} ORDER BY tahun_maintenance DESC, id LIMIT 50000",
        params,
    )

    buffer = io.StringIO()

    if rows:
        writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)

    buffer.seek(0)

    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=equipment_components.csv"
        },
    )


@router.get("/components/history")
def component_history(
    code: str = Query(..., min_length=2),
    user: dict = Depends(get_current_user),
):
    """Lacak satu kode cetak / nomor manufaktur melintasi tahun dan lokomotif."""
    like = f"%{code.upper()}%"

    rows = db.query(
        f"""
        {COMPONENT_SELECT}
        WHERE upper(asal_kode_cetak) LIKE ?
           OR upper(pengganti_kode_cetak) LIKE ?
           OR upper(asal_no_manuf) LIKE ?
           OR upper(pengganti_no_manuf) LIKE ?
        ORDER BY tahun_maintenance, masuk, id
        LIMIT 400
        """,
        [like] * 4,
    )

    for row in rows:
        matched_asal = code.upper() in (
            (row["asal_kode_cetak"] or "") + (row["asal_no_manuf"] or "")
        ).upper()

        row["peran"] = "Dilepas" if matched_asal else "Dipasang"

    return {
        "code": code,
        "total": len(rows),
        "lokomotif": sorted({r["lokomotif_no"] for r in rows if r["lokomotif_no"]}),
        "items": rows,
    }


@router.get("/maintenance")
def list_maintenance(
    search: str | None = Query(None),
    dipo: str | None = Query(None),
    jenis: str | None = Query(None),
    year: int | None = Query(None),
    status: str | None = Query(None),
    source_file: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=5, le=200),
    user: dict = Depends(get_current_user),
):
    where = ["1=1"]
    params: list = []

    if search:
        like = f"%{search.upper()}%"
        where.append(
            "(upper(lokomotif_no) LIKE ? OR upper(source_sheet) LIKE ? "
            "OR upper(no_seri_lokomotif) LIKE ?)"
        )
        params += [like] * 3

    if dipo:
        where.append("upper(trim(dipo_induk)) = ?")
        params.append(dipo.upper())

    if jenis:
        where.append("upper(trim(jenis_perawatan)) = ?")
        params.append(jenis.upper())

    if year:
        where.append("tahun_maintenance = ?")
        params.append(year)

    if source_file:
        where.append("source_file = ?")
        params.append(source_file)

    if status == "berjalan":
        where.append("keluar IS NULL")
    elif status == "selesai":
        where.append("keluar IS NOT NULL")
    elif status == "estimasi":
        where.append("(masuk_source = 'program_bulan' OR keluar_source = 'program_bulan')")

    clause = " AND ".join(where)

    total = db.scalar(
        f"SELECT COUNT(*) FROM maintenance_events WHERE {clause}", params
    )

    items = db.query(
        f"""
        SELECT id, source_file, source_year, source_sheet, block_index,
               no_seri_lokomotif, lokomotif_no, lokomotif_key,
               dipo_induk, jenis_perawatan, program_bulan,
               masuk, keluar, masuk_source, keluar_source,
               tahun_maintenance, component_count
        FROM maintenance_events
        WHERE {clause}
        ORDER BY tahun_maintenance DESC, masuk DESC, id DESC
        LIMIT ? OFFSET ?
        """,
        params + [page_size, (page - 1) * page_size],
    )

    for row in items:
        row["status"] = "Berjalan" if row["keluar"] is None else "Selesai"
        row["durasi_hari"] = None

        if row["masuk"] and row["keluar"]:
            try:
                from datetime import date

                masuk = date.fromisoformat(row["masuk"][:10])
                keluar = date.fromisoformat(row["keluar"][:10])
                row["durasi_hari"] = (keluar - masuk).days
            except ValueError:
                row["durasi_hari"] = None

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
        "items": items,
    }


@router.get("/maintenance/{event_id}")
def maintenance_detail(event_id: int, user: dict = Depends(get_current_user)):
    event = db.query_one(
        "SELECT * FROM maintenance_events WHERE id = ?", (event_id,)
    )

    components = db.query(
        f"{COMPONENT_SELECT} WHERE maintenance_event_id = ? ORDER BY id",
        (event_id,),
    )

    return {"event": event, "components": components}
