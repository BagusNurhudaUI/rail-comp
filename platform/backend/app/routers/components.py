"""Pencarian komponen, riwayat satu nomor equipment, dan daftar perawatan."""

import csv
import io

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse

from .. import db
from ..deps import get_current_user
from ..excel_parser import augment_component_rows

router = APIRouter(prefix="/api", tags=["components"])

COMPONENT_SELECT = """
SELECT id, maintenance_event_id, source_file, source_year, source_sheet, block_index,
       lokomotif_no, lokomotif_key, masuk, keluar, tahun_maintenance,
       component_no, component_seq, component_name, component_base,
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
        where.append("COALESCE(component_base, component_name) = ?")
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

    # Lengkapi nomor sub-komponen + nama walau data belum di-ingest ulang.
    augment_component_rows(items)

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

    augment_component_rows(rows)

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


def _trace_component(code: str) -> dict:
    """Lacak satu kode melintasi tahun & lokomotif, lengkap dengan perannya."""
    like = f"%{code.upper()}%"

    # jenis_perawatan (P24/P48/P72) tersimpan di maintenance_events, bukan di
    # equipment_components, jadi diambil lewat JOIN untuk tabel riwayat.
    rows = db.query(
        """
        SELECT ec.id, ec.maintenance_event_id, ec.source_file, ec.source_year,
               ec.source_sheet, ec.block_index, ec.lokomotif_no, ec.lokomotif_key,
               ec.masuk, ec.keluar, ec.tahun_maintenance,
               ec.component_no, ec.component_seq, ec.component_name, ec.component_base,
               ec.asal_kode_cetak, ec.asal_no_manuf,
               ec.pengganti_kode_cetak, ec.pengganti_no_manuf, ec.keterangan,
               me.jenis_perawatan
        FROM equipment_components ec
        LEFT JOIN maintenance_events me ON me.id = ec.maintenance_event_id
        WHERE upper(ec.asal_kode_cetak) LIKE ?
           OR upper(ec.pengganti_kode_cetak) LIKE ?
           OR upper(ec.asal_no_manuf) LIKE ?
           OR upper(ec.pengganti_no_manuf) LIKE ?
        ORDER BY ec.tahun_maintenance, ec.masuk, ec.id
        LIMIT 400
        """,
        [like] * 4,
    )

    for row in rows:
        matched_asal = code.upper() in (
            (row["asal_kode_cetak"] or "") + (row["asal_no_manuf"] or "")
        ).upper()

        # Placeholder "-"/"–"/"." dsb. bukan pengganti sungguhan. Pengganti
        # dianggap ada hanya bila nilainya memuat karakter alfanumerik. Ini
        # menjaga data lama (yang mungkin masih menyimpan "-") tetap benar.
        def _has_code(value):
            return bool(value) and any(ch.isalnum() for ch in str(value))

        has_pengganti = _has_code(row["pengganti_kode_cetak"]) or _has_code(
            row["pengganti_no_manuf"]
        )

        # Kode ini di kolom asal:
        #   - ada pengganti  -> benar-benar Dilepas (digantikan part lain)
        #   - tidak ada      -> Tetap (diperiksa tapi tidak diganti)
        # Kode ini di kolom pengganti -> Dipasang (part baru yang masuk).
        if matched_asal:
            row["peran"] = "Dilepas" if has_pengganti else "Tetap"
        else:
            row["peran"] = "Dipasang"

    return {
        "code": code,
        "total": len(rows),
        "lokomotif": sorted({r["lokomotif_no"] for r in rows if r["lokomotif_no"]}),
        "items": rows,
    }


@router.get("/components/history")
def component_history(
    code: str = Query(..., min_length=2),
    user: dict = Depends(get_current_user),
):
    """Lacak satu kode cetak / nomor manufaktur melintasi tahun dan lokomotif."""
    return _trace_component(code)


# ── Export Excel riwayat komponen ──────────────────────────────────────

_BRAND = "FF6E00"
_BRAND_INK = "8E3F00"
_BRAND_SOFT = "FFF3E8"
_LINE = "ECE3DA"


def _parse_date(value):
    from datetime import date

    if not value:
        return None

    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _most_common_name(items) -> str:
    from collections import Counter

    names = Counter(i["component_name"] for i in items if i.get("component_name"))

    return names.most_common(1)[0][0] if names else ""


def _history_workbook(code: str, layout: str):
    """Bangun workbook openpyxl bergaya untuk riwayat satu komponen.

    layout "table"  -> satu baris per catatan (seperti tabel di UI, tanpa sumber)
    layout "wide"   -> satu baris ringkas: komponen + tiap perhentiannya melebar
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
    from openpyxl.utils import get_column_letter

    data = _trace_component(code)
    items = data["items"]
    nama = _most_common_name(items)

    thin = Side(style="thin", color=_LINE)
    border = Border(left=thin, right=thin, top=thin, bottom=thin)
    header_fill = PatternFill("solid", fgColor=_BRAND)
    header_font = Font(bold=True, color="FFFFFF", size=10)
    hit_fill = PatternFill("solid", fgColor=_BRAND_SOFT)
    hit_font = Font(bold=True, color=_BRAND_INK)
    title_font = Font(bold=True, size=14, color=_BRAND_INK)
    center = Alignment(horizontal="center", vertical="center")

    wb = Workbook()
    ws = wb.active
    ws.title = "Riwayat Komponen"

    # Judul + ringkasan
    ws["A1"] = f"Riwayat Servis Komponen — {code}"
    ws["A1"].font = title_font
    ws["A2"] = nama
    ws["A2"].font = Font(italic=True, color="57493E")
    ws["A3"] = (
        f"{data['total']} catatan · {len(data['lokomotif'])} lokomotif · "
        f"tahun {items[0]['tahun_maintenance'] if items else '-'}"
        f"–{items[-1]['tahun_maintenance'] if items else '-'}"
    )
    ws["A3"].font = Font(color="6B5B4E", size=10)

    target = code.strip().upper()
    start_row = 5

    if layout == "wide":
        # Satu baris: Kode | Nama | Kemunculan | Lokomotif 1 | Masuk 1 | Keluar 1 | Peran 1 | ...
        headers = ["Kode", "Nama Komponen", "Kemunculan"]
        for i in range(1, len(items) + 1):
            headers += [f"Lokomotif {i}", f"Masuk {i}", f"Keluar {i}", f"Peran {i}"]

        widths = [16, 26, 12] + [16, 13, 13, 12] * len(items)
        row_values = [code, nama, data["total"]]
        for it in items:
            row_values += [
                it["lokomotif_no"],
                _parse_date(it["masuk"]),
                _parse_date(it["keluar"]),
                it["peran"],
            ]
        body_rows = [row_values]
    else:  # table
        headers = [
            "Tahun", "Lokomotif", "Komponen", "Peran",
            "Asal (No KAI)", "Asal (Serial Number)",
            "Pengganti (No KAI)", "Pengganti (Serial Number)",
            "Jenis Perawatan", "Masuk", "Keluar", "Sumber",
        ]
        widths = [8, 16, 24, 12, 16, 18, 16, 18, 14, 13, 13, 28]
        # Kolom kode yang perlu disorot saat cocok dengan komponen yang dilacak.
        code_headers = {
            "Asal (No KAI)", "Asal (Serial Number)",
            "Pengganti (No KAI)", "Pengganti (Serial Number)",
        }
        body_rows = [
            [
                it["tahun_maintenance"],
                it["lokomotif_no"],
                it["component_name"],
                it["peran"],
                it["asal_kode_cetak"],
                it["asal_no_manuf"],
                it["pengganti_kode_cetak"],
                it["pengganti_no_manuf"],
                it.get("jenis_perawatan"),
                _parse_date(it["masuk"]),
                _parse_date(it["keluar"]),
                " · ".join(
                    part
                    for part in (
                        it.get("source_file"),
                        it.get("source_sheet"),
                        f"blok {it['block_index']}" if it.get("block_index") else None,
                    )
                    if part
                ),
            ]
            for it in items
        ]

    # Header
    for col, name in enumerate(headers, start=1):
        cell = ws.cell(row=start_row, column=col, value=name)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = center
        cell.border = border
        ws.column_dimensions[get_column_letter(col)].width = widths[col - 1]

    # Body
    for r, values in enumerate(body_rows, start=start_row + 1):
        for c, value in enumerate(values, start=1):
            cell = ws.cell(row=r, column=c, value=value)
            cell.border = border
            cell.font = Font(size=10)

            if isinstance(value, object) and hasattr(value, "isoformat") and not isinstance(value, str):
                cell.number_format = "dd mmm yyyy"

            # Sorot sel kode yang cocok dengan komponen yang dilacak.
            header_name = headers[c - 1]
            is_code_col = header_name in code_headers if layout != "wide" else False
            if is_code_col and str(value or "").strip().upper() == target:
                cell.fill = hit_fill
                cell.font = hit_font

    ws.freeze_panes = ws.cell(row=start_row + 1, column=1)

    return wb


@router.get("/components/history/export")
def export_component_history(
    code: str = Query(..., min_length=2),
    layout: str = Query("table", pattern="^(table|wide)$"),
    user: dict = Depends(get_current_user),
):
    """Unduh riwayat satu komponen sebagai berkas Excel bergaya."""
    wb = _history_workbook(code, layout)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)

    safe = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in code)
    filename = f"riwayat_{safe}_{layout}.xlsx"

    return StreamingResponse(
        buffer,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


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
               tahun_maintenance,
               (SELECT COUNT(DISTINCT ec.component_no)
                  FROM equipment_components ec
                 WHERE ec.maintenance_event_id = maintenance_events.id) AS component_count
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

    # Nomor sub-komponen + nama lengkap diturunkan di sini juga, supaya data yang
    # belum di-ingest ulang tetap tampil benar (2.1 Cylinder Assy 1R, dst.).
    augment_component_rows(components)

    # "Total komponen" = jumlah nomor komponen unik (≈32 sesuai form), bukan
    # jumlah baris yang membengkak karena sub-komponen.
    total_komponen = len({c["component_no"] for c in components if c["component_no"]})

    return {"event": event, "components": components, "total_komponen": total_komponen}
