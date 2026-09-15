"""Daftar lokomotif, detail, dan riwayat perawatannya."""

from fastapi import APIRouter, Depends, HTTPException, Query

from .. import db
from ..deps import get_current_user
from ..excel_parser import augment_component_rows

router = APIRouter(prefix="/api/locomotives", tags=["locomotives"])


@router.get("")
def list_locomotives(
    search: str | None = Query(None),
    dipo: str | None = Query(None),
    year: int | None = Query(None),
    jenis: str | None = Query(None),
    sort: str = Query("lokomotif_no"),
    order: str = Query("asc"),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=5, le=200),
    user: dict = Depends(get_current_user),
):
    where = ["lokomotif_key IS NOT NULL"]
    params: list = []

    if search:
        where.append("(lokomotif_no LIKE ? OR lokomotif_key LIKE ?)")
        params += [f"%{search.upper()}%", f"%{''.join(ch for ch in search if ch.isdigit())}%"]

    if dipo:
        where.append("upper(trim(dipo_induk)) = ?")
        params.append(dipo.upper())

    if year:
        where.append("tahun_maintenance = ?")
        params.append(year)

    if jenis:
        where.append("upper(trim(jenis_perawatan)) = ?")
        params.append(jenis.upper())

    clause = " AND ".join(where)

    sortable = {
        "lokomotif_no": "lokomotif_no",
        "total_perawatan": "total_perawatan",
        "total_komponen": "total_komponen",
        "terakhir_masuk": "terakhir_masuk",
    }
    sort_col = sortable.get(sort, "lokomotif_no")
    direction = "DESC" if order.lower() == "desc" else "ASC"

    total = db.scalar(
        f"SELECT COUNT(DISTINCT lokomotif_key) FROM maintenance_events WHERE {clause}",
        params,
    )

    rows = db.query(
        f"""
        SELECT lokomotif_key,
               MAX(lokomotif_no) AS lokomotif_no,
               COUNT(*) AS total_perawatan,
               (SELECT COUNT(DISTINCT ec.component_no)
                  FROM equipment_components ec
                 WHERE ec.lokomotif_key = maintenance_events.lokomotif_key) AS total_komponen,
               MAX(masuk) AS terakhir_masuk,
               MAX(keluar) AS terakhir_keluar,
               MIN(tahun_maintenance) AS tahun_awal,
               MAX(tahun_maintenance) AS tahun_akhir,
               COUNT(DISTINCT upper(trim(dipo_induk))) AS jumlah_dipo,
               SUM(CASE WHEN keluar IS NULL THEN 1 ELSE 0 END) AS belum_keluar
        FROM maintenance_events
        WHERE {clause}
        GROUP BY lokomotif_key
        ORDER BY {sort_col} {direction}
        LIMIT ? OFFSET ?
        """,
        params + [page_size, (page - 1) * page_size],
    )

    for row in rows:
        dipo_row = db.query_one(
            """
            SELECT upper(trim(dipo_induk)) AS dipo
            FROM maintenance_events
            WHERE lokomotif_key = ? AND dipo_induk IS NOT NULL
            ORDER BY masuk DESC LIMIT 1
            """,
            (row["lokomotif_key"],),
        )

        row["dipo_induk"] = dipo_row["dipo"] if dipo_row else None
        row["status"] = "Dalam perawatan" if row["belum_keluar"] else "Operasional"

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
        "items": rows,
    }


@router.get("/{lokomotif_key}")
def detail(lokomotif_key: str, user: dict = Depends(get_current_user)):
    header = db.query_one(
        """
        SELECT lokomotif_key,
               MAX(lokomotif_no) AS lokomotif_no,
               COUNT(*) AS total_perawatan,
               SUM(component_count) AS total_komponen,
               MIN(masuk) AS pertama_masuk,
               MAX(masuk) AS terakhir_masuk,
               MAX(keluar) AS terakhir_keluar
        FROM maintenance_events
        WHERE lokomotif_key = ?
        GROUP BY lokomotif_key
        """,
        (lokomotif_key,),
    )

    if header is None:
        raise HTTPException(status_code=404, detail="Lokomotif tidak ditemukan")

    riwayat = db.query(
        """
        SELECT id, tahun_maintenance, source_file, source_sheet, block_index,
               dipo_induk, jenis_perawatan, program_bulan,
               masuk, keluar, masuk_source, keluar_source, component_count
        FROM maintenance_events
        WHERE lokomotif_key = ?
        ORDER BY tahun_maintenance DESC, masuk DESC
        """,
        (lokomotif_key,),
    )

    # "Total komponen" & jumlah tiap komponen mengikuti struktur form Excel (per
    # perawatan), bukan menjumlahkan seluruh baris di semua perawatan. Baris
    # diambil lalu dilengkapi nama induknya supaya data lama pun benar.
    rows = db.query(
        """
        SELECT maintenance_event_id, component_no, component_seq,
               component_name, component_base
        FROM equipment_components
        WHERE lokomotif_key = ? AND component_name IS NOT NULL
        ORDER BY maintenance_event_id, id
        """,
        (lokomotif_key,),
    )
    augment_component_rows(rows)

    # Total komponen = jumlah nomor komponen unik (≈32, sesuai form), bukan
    # akumulasi semua perawatan.
    header["total_komponen"] = len({r["component_no"] for r in rows if r["component_no"]})

    # Kolom "Komp." per perawatan juga dihitung dari nomor komponen unik (≈32),
    # bukan jumlah baris tersimpan — berlaku walau data belum di-ingest ulang.
    per_event_groups: dict = {}
    for row in rows:
        if row["component_no"]:
            per_event_groups.setdefault(row["maintenance_event_id"], set()).add(
                row["component_no"]
            )

    for visit in riwayat:
        visit["component_count"] = len(per_event_groups.get(visit["id"], set()))

    # Jumlah tiap komponen = terbanyak dalam satu perawatan (mis. Cylinder Assy
    # 8, Injection Pump 8), bukan dijumlah lintas perawatan.
    per_event: dict = {}
    for row in rows:
        base = row.get("component_base") or row.get("component_name")
        bucket = per_event.setdefault(row["maintenance_event_id"], {})
        bucket[base] = bucket.get(base, 0) + 1

    per_component: dict = {}
    for bucket in per_event.values():
        for base, count in bucket.items():
            if count > per_component.get(base, 0):
                per_component[base] = count

    komponen_teratas = [
        {"label": label, "value": value}
        for label, value in sorted(
            per_component.items(), key=lambda item: (-item[1], item[0])
        )
    ][:10]

    per_tahun = db.query(
        """
        SELECT tahun_maintenance AS label, COUNT(*) AS value
        FROM equipment_components
        WHERE lokomotif_key = ?
        GROUP BY tahun_maintenance
        ORDER BY tahun_maintenance
        """,
        (lokomotif_key,),
    )

    return {
        "header": header,
        "riwayat": riwayat,
        "komponen_teratas": komponen_teratas,
        "komponen_per_tahun": per_tahun,
    }
