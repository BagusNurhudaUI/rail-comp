"""Ringkasan KPI, data grafik, alert, dan aktivitas terbaru."""

from fastapi import APIRouter, Depends, Query

from .. import db
from ..deps import get_current_user

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


def _year_filter(year: int | None, alias: str = "") -> tuple[str, list]:
    prefix = f"{alias}." if alias else ""

    if year:
        return f" AND {prefix}tahun_maintenance = ?", [year]

    return "", []


@router.get("/summary")
def summary(
    year: int | None = Query(None),
    user: dict = Depends(get_current_user),
):
    where, params = _year_filter(year)

    total_lokomotif = db.scalar(
        f"SELECT COUNT(DISTINCT lokomotif_key) FROM maintenance_events WHERE 1=1{where}",
        params,
    )
    total_event = db.scalar(
        f"SELECT COUNT(*) FROM maintenance_events WHERE 1=1{where}", params
    )
    selesai = db.scalar(
        f"SELECT COUNT(*) FROM maintenance_events WHERE keluar IS NOT NULL{where}",
        params,
    )
    berjalan = db.scalar(
        f"SELECT COUNT(*) FROM maintenance_events WHERE keluar IS NULL{where}",
        params,
    )
    total_komponen = db.scalar(
        f"SELECT COUNT(*) FROM equipment_components WHERE 1=1{where}", params
    )
    diganti = db.scalar(
        f"""
        SELECT COUNT(*) FROM equipment_components
        WHERE (pengganti_kode_cetak IS NOT NULL OR pengganti_no_manuf IS NOT NULL)
        {where}
        """,
        params,
    )
    pemasangan_baru = db.scalar(
        f"""
        SELECT COUNT(*) FROM equipment_components
        WHERE asal_kode_cetak IS NULL AND asal_no_manuf IS NULL
          AND (pengganti_kode_cetak IS NOT NULL OR pengganti_no_manuf IS NOT NULL)
        {where}
        """,
        params,
    )

    # Rincian "Total komponen" sebagai tiga kelompok yang SALING LEPAS (mengikuti
    # pewarnaan form: dismantle/refurbish/penambahan). Warna sel tak terbaca
    # pandas, jadi didekati lewat kolom Asal/Pengganti:
    #   dismantle  = ada asal & ada pengganti  -> lama dilepas & diganti (swap)
    #   refurbish  = ada asal, tanpa pengganti -> diperiksa, tetap dipakai
    #   penambahan = ada pengganti, tanpa asal -> part baru tanpa gantian
    # (Dulu "terinstall" = "ada pengganti" — selalu sama dengan dismantle karena
    #  setiap penggantian selalu punya asal, jadi diganti dengan penambahan.)
    dismantle = db.scalar(
        f"""
        SELECT COUNT(*) FROM equipment_components
        WHERE (asal_kode_cetak IS NOT NULL OR asal_no_manuf IS NOT NULL)
          AND (pengganti_kode_cetak IS NOT NULL OR pengganti_no_manuf IS NOT NULL)
        {where}
        """,
        params,
    )
    refurbish = db.scalar(
        f"""
        SELECT COUNT(*) FROM equipment_components
        WHERE (asal_kode_cetak IS NOT NULL OR asal_no_manuf IS NOT NULL)
          AND pengganti_kode_cetak IS NULL AND pengganti_no_manuf IS NULL
        {where}
        """,
        params,
    )
    penambahan = pemasangan_baru
    estimasi = db.scalar(
        f"""
        SELECT COUNT(*) FROM maintenance_events
        WHERE (masuk_source = 'program_bulan' OR keluar_source = 'program_bulan')
        {where}
        """,
        params,
    )

    operasional = round(selesai / total_event * 100, 1) if total_event else 0.0
    terpasang = round(diganti / total_komponen * 100, 1) if total_komponen else 0.0

    return {
        "total_lokomotif": total_lokomotif,
        "total_event": total_event,
        "selesai": selesai,
        "berjalan": berjalan,
        "total_komponen": total_komponen,
        "komponen_diganti": diganti,
        # Terinstall = semua part yang dipasang (punya pengganti) = swap + penambahan.
        "komponen_terinstall": dismantle + penambahan,
        "komponen_dismantle": dismantle,
        "komponen_refurbish": refurbish,
        "komponen_penambahan": penambahan,
        "pemasangan_baru": pemasangan_baru,
        "tanggal_estimasi": estimasi,
        "persen_selesai": operasional,
        "persen_diganti": terpasang,
    }


@router.get("/charts")
def charts(
    year: int | None = Query(None),
    user: dict = Depends(get_current_user),
):
    where, params = _year_filter(year)

    status_komponen = db.query_one(
        f"""
        SELECT
            SUM(CASE WHEN (asal_kode_cetak IS NOT NULL OR asal_no_manuf IS NOT NULL)
                      AND (pengganti_kode_cetak IS NOT NULL OR pengganti_no_manuf IS NOT NULL)
                     THEN 1 ELSE 0 END) AS diganti,
            SUM(CASE WHEN (asal_kode_cetak IS NULL AND asal_no_manuf IS NULL)
                      AND (pengganti_kode_cetak IS NOT NULL OR pengganti_no_manuf IS NOT NULL)
                     THEN 1 ELSE 0 END) AS baru,
            SUM(CASE WHEN (asal_kode_cetak IS NOT NULL OR asal_no_manuf IS NOT NULL)
                      AND pengganti_kode_cetak IS NULL AND pengganti_no_manuf IS NULL
                     THEN 1 ELSE 0 END) AS tetap,
            SUM(CASE WHEN asal_kode_cetak IS NULL AND asal_no_manuf IS NULL
                      AND pengganti_kode_cetak IS NULL AND pengganti_no_manuf IS NULL
                     THEN 1 ELSE 0 END) AS lainnya
        FROM equipment_components WHERE 1=1{where}
        """,
        params,
    )

    top_komponen = db.query(
        f"""
        SELECT COALESCE(component_base, component_name) AS label, COUNT(*) AS value
        FROM equipment_components
        WHERE component_name IS NOT NULL{where}
        GROUP BY COALESCE(component_base, component_name)
        ORDER BY value DESC
        LIMIT 10
        """,
        params,
    )

    per_tahun = db.query(
        """
        SELECT tahun_maintenance AS label,
               COUNT(*) AS events,
               COUNT(DISTINCT lokomotif_key) AS lokomotif,
               SUM(component_count) AS komponen
        FROM maintenance_events
        WHERE tahun_maintenance IS NOT NULL
        GROUP BY tahun_maintenance
        ORDER BY tahun_maintenance
        """
    )

    per_dipo = db.query(
        f"""
        SELECT COALESCE(upper(trim(dipo_induk)), 'TIDAK DIISI') AS label,
               COUNT(*) AS value
        FROM maintenance_events WHERE 1=1{where}
        GROUP BY label
        ORDER BY value DESC
        LIMIT 12
        """,
        params,
    )

    per_perawatan = db.query(
        f"""
        SELECT COALESCE(upper(trim(jenis_perawatan)), 'TIDAK DIISI') AS label,
               COUNT(*) AS value
        FROM maintenance_events WHERE 1=1{where}
        GROUP BY label
        ORDER BY value DESC
        LIMIT 8
        """,
        params,
    )

    per_bulan = db.query(
        f"""
        SELECT substr(masuk, 1, 7) AS label, COUNT(*) AS value
        FROM maintenance_events
        WHERE masuk IS NOT NULL{where}
        GROUP BY label
        ORDER BY label
        """,
        params,
    )

    return {
        "status_komponen": status_komponen,
        "top_komponen": top_komponen,
        "per_tahun": per_tahun,
        "per_dipo": per_dipo,
        "per_perawatan": per_perawatan,
        "per_bulan": per_bulan[-24:],
    }


@router.get("/alerts")
def alerts(user: dict = Depends(get_current_user)):
    """Temuan yang perlu tindak lanjut, diturunkan langsung dari data."""
    items: list[dict] = []

    belum_keluar = db.query(
        """
        SELECT lokomotif_no, dipo_induk, masuk, tahun_maintenance, source_file
        FROM maintenance_events
        WHERE keluar IS NULL AND masuk IS NOT NULL
        ORDER BY masuk DESC
        LIMIT 6
        """
    )

    for row in belum_keluar:
        items.append(
            {
                "level": "warning",
                "title": f"{row['lokomotif_no']} belum tercatat keluar",
                "meta": f"masuk {row['masuk']}",
                "context": row["dipo_induk"] or "-",
            }
        )

    dipo_aneh = db.query(
        """
        SELECT lokomotif_no, dipo_induk, jenis_perawatan, source_file, source_sheet
        FROM maintenance_events
        WHERE dipo_induk IS NOT NULL
          AND upper(trim(dipo_induk)) NOT IN (
            'SDT','CPN','YK','PWT','BD','SMC','CN','JR','MN','JNG','THB','SMG','BYYK','TNK'
          )
        LIMIT 5
        """
    )

    for row in dipo_aneh:
        items.append(
            {
                "level": "critical",
                "title": f"Dipo tidak dikenal: {row['dipo_induk']}",
                "meta": f"{row['lokomotif_no']} - {row['source_sheet']}",
                "context": "Perlu verifikasi ke file sumber",
            }
        )

    sheet_bermasalah = db.query(
        """
        SELECT source_file, source_sheet, status, message
        FROM sheet_availability
        WHERE status != 'OK'
        ORDER BY source_year DESC
        LIMIT 5
        """
    )

    for row in sheet_bermasalah:
        items.append(
            {
                "level": "info",
                "title": f"Sheet {row['source_sheet']} tanpa data ({row['status']})",
                "meta": row["source_file"],
                "context": row["message"] or "-",
            }
        )

    estimasi = db.scalar(
        "SELECT COUNT(*) FROM maintenance_events WHERE masuk_source = 'program_bulan'"
    )

    if estimasi:
        items.append(
            {
                "level": "info",
                "title": f"{estimasi} perawatan memakai tanggal estimasi",
                "meta": "diturunkan dari PROGRAM BULAN",
                "context": "Tanggal perlu konfirmasi",
            }
        )

    return {"items": items[:12]}


@router.get("/activity")
def activity(limit: int = Query(12, le=50), user: dict = Depends(get_current_user)):
    ingestions = db.query(
        """
        SELECT source_file, status, event_count, component_count,
               COALESCE(finished_at, started_at) AS at
        FROM ingestion_history
        ORDER BY id DESC LIMIT ?
        """,
        (limit,),
    )

    logs = db.query(
        """
        SELECT created_at AS at, actor, action, title, detail, level
        FROM activity_log
        ORDER BY id DESC LIMIT ?
        """,
        (limit,),
    )

    items = [
        {
            "at": row["at"],
            "action": "IMPORT",
            "level": "success" if row["status"] == "SUCCESS" else "critical",
            "title": f"{row['source_file']} diimpor",
            "detail": f"{row['event_count']} perawatan, {row['component_count']} komponen",
            "actor": "System",
        }
        for row in ingestions
    ] + [
        {
            "at": row["at"],
            "action": row["action"],
            "level": row["level"],
            "title": row["title"],
            "detail": row["detail"],
            "actor": row["actor"] or "System",
        }
        for row in logs
    ]

    items.sort(key=lambda x: x["at"] or "", reverse=True)

    return {"items": items[:limit]}


@router.get("/filters")
def filter_options(user: dict = Depends(get_current_user)):
    return {
        "years": [
            row["value"]
            for row in db.query(
                """
                SELECT DISTINCT tahun_maintenance AS value
                FROM maintenance_events
                WHERE tahun_maintenance IS NOT NULL
                ORDER BY value DESC
                """
            )
        ],
        "dipo": [
            row["value"]
            for row in db.query(
                """
                SELECT DISTINCT upper(trim(dipo_induk)) AS value
                FROM maintenance_events
                WHERE dipo_induk IS NOT NULL
                ORDER BY value
                """
            )
        ],
        "jenis_perawatan": [
            row["value"]
            for row in db.query(
                """
                SELECT DISTINCT upper(trim(jenis_perawatan)) AS value
                FROM maintenance_events
                WHERE jenis_perawatan IS NOT NULL
                ORDER BY value
                """
            )
        ],
        "component_names": [
            row["value"]
            for row in db.query(
                """
                SELECT COALESCE(component_base, component_name) AS value, COUNT(*) AS n
                FROM equipment_components
                WHERE component_name IS NOT NULL
                GROUP BY COALESCE(component_base, component_name)
                ORDER BY n DESC
                LIMIT 60
                """
            )
        ],
        "files": [
            row["value"]
            for row in db.query(
                "SELECT DISTINCT source_file AS value FROM maintenance_events ORDER BY value"
            )
        ],
    }
