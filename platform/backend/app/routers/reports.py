"""Laporan availability data dan kualitas hasil parsing."""

from datetime import date

from fastapi import APIRouter, Depends, Query

from .. import db
from ..deps import get_current_user

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/availability")
def availability(user: dict = Depends(get_current_user)):
    per_tahun = db.query(
        """
        SELECT source_year,
               COUNT(*) AS sheets,
               SUM(CASE WHEN status = 'OK' THEN 1 ELSE 0 END) AS sheets_ok,
               SUM(block_count) AS blocks,
               SUM(template_block_count) AS blocks_template,
               SUM(event_count) AS events,
               SUM(component_count) AS komponen
        FROM sheet_availability
        GROUP BY source_year
        ORDER BY source_year
        """
    )

    bermasalah = db.query(
        """
        SELECT source_year, source_file, sheet_index, source_sheet,
               block_count, template_block_count, status, message
        FROM sheet_availability
        WHERE status != 'OK'
        ORDER BY source_year, sheet_index
        """
    )

    kelengkapan = db.query(
        """
        SELECT tahun_maintenance AS tahun,
               COUNT(*) AS events,
               ROUND(100.0 * SUM(CASE WHEN dipo_induk IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS dipo,
               ROUND(100.0 * SUM(CASE WHEN jenis_perawatan IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS jenis,
               ROUND(100.0 * SUM(CASE WHEN program_bulan IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS program,
               ROUND(100.0 * SUM(CASE WHEN masuk IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS masuk,
               ROUND(100.0 * SUM(CASE WHEN keluar IS NOT NULL THEN 1 ELSE 0 END) / COUNT(*), 1) AS keluar
        FROM maintenance_events
        GROUP BY tahun_maintenance
        ORDER BY tahun_maintenance
        """
    )

    sumber_tanggal = db.query(
        """
        SELECT tahun_maintenance AS tahun,
               SUM(CASE WHEN masuk_source = 'excel' THEN 1 ELSE 0 END) AS masuk_excel,
               SUM(CASE WHEN masuk_source = 'program_bulan' THEN 1 ELSE 0 END) AS masuk_estimasi,
               SUM(CASE WHEN masuk IS NULL THEN 1 ELSE 0 END) AS masuk_kosong,
               SUM(CASE WHEN keluar IS NULL THEN 1 ELSE 0 END) AS keluar_kosong
        FROM maintenance_events
        GROUP BY tahun_maintenance
        ORDER BY tahun_maintenance
        """
    )

    return {
        "per_tahun": per_tahun,
        "sheet_bermasalah": bermasalah,
        "kelengkapan": kelengkapan,
        "sumber_tanggal": sumber_tanggal,
    }


@router.get("/anomalies")
def anomalies(user: dict = Depends(get_current_user)):
    dipo_aneh = db.query(
        """
        SELECT id, source_file, source_sheet, block_index, lokomotif_no,
               dipo_induk, jenis_perawatan, tahun_maintenance
        FROM maintenance_events
        WHERE dipo_induk IS NOT NULL
          AND upper(trim(dipo_induk)) NOT IN (
            'SDT','CPN','YK','PWT','BD','SMC','CN','JR','MN','JNG','THB','SMG','BYYK','TNK'
          )
        ORDER BY tahun_maintenance DESC
        """
    )

    tanpa_komponen = db.query(
        """
        SELECT id, source_file, source_sheet, block_index, lokomotif_no,
               tahun_maintenance, component_count
        FROM maintenance_events
        WHERE component_count = 0
        ORDER BY tahun_maintenance DESC
        LIMIT 100
        """
    )

    # Selisih hari dihitung di Python, bukan lewat julianday() (fungsi khusus
    # SQLite), supaya query yang sama jalan di SQLite maupun PostgreSQL.
    kandidat = db.query(
        """
        SELECT id, lokomotif_no, source_file, source_sheet, masuk, keluar
        FROM maintenance_events
        WHERE masuk IS NOT NULL AND keluar IS NOT NULL
        """
    )

    durasi_aneh = []

    for row in kandidat:
        try:
            selisih = (
                date.fromisoformat(row["keluar"][:10])
                - date.fromisoformat(row["masuk"][:10])
            ).days
        except (ValueError, TypeError):
            continue

        if selisih < 0:
            durasi_aneh.append({**row, "durasi": selisih})

    durasi_aneh.sort(key=lambda item: item["durasi"])

    return {
        "dipo_tidak_dikenal": dipo_aneh,
        "event_tanpa_komponen": tanpa_komponen,
        "tanggal_terbalik": durasi_aneh[:100],
    }


@router.get("/top-components")
def top_components(
    limit: int = Query(20, le=100),
    year: int | None = Query(None),
    user: dict = Depends(get_current_user),
):
    where = "WHERE component_name IS NOT NULL"
    params: list = []

    if year:
        where += " AND tahun_maintenance = ?"
        params.append(year)

    return {
        "items": db.query(
            f"""
            SELECT component_name AS label,
                   COUNT(*) AS total,
                   COUNT(DISTINCT lokomotif_key) AS lokomotif,
                   SUM(CASE WHEN pengganti_kode_cetak IS NOT NULL
                             OR pengganti_no_manuf IS NOT NULL THEN 1 ELSE 0 END) AS diganti
            FROM equipment_components
            {where}
            GROUP BY component_name
            ORDER BY total DESC
            LIMIT ?
            """,
            params + [limit],
        )
    }
