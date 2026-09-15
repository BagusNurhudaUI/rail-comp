"""API master data SAP: lokomotif dan katalog komponen.

Relasi di sini lunak, jadi seluruh penggabungan memakai LEFT JOIN dan
ketidakcocokan dilaporkan sebagai angka, bukan disembunyikan.
"""

import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from pydantic import BaseModel

from .. import db
from ..config import COMPONENT_DIR, UPLOAD_DIR
from ..deps import get_current_user, log_activity, require_role

router = APIRouter(prefix="/api/master", tags=["master"])


class ImportRequest(BaseModel):
    file_name: str | None = None


@router.get("/summary")
def summary(user: dict = Depends(get_current_user)):
    total_loco = db.scalar("SELECT COUNT(*) FROM locomotives")
    total_comp = db.scalar("SELECT COUNT(*) FROM components")

    terpasang = db.scalar(
        """
        SELECT COUNT(*) FROM components c
        JOIN locomotives l ON l.equipment = c.superord_equipment
        """
    )
    tanpa_induk = db.scalar(
        "SELECT COUNT(*) FROM components WHERE superord_equipment IS NULL"
    )
    induk_lain = total_comp - terpasang - tanpa_induk

    return {
        "total_lokomotif": total_loco,
        "total_komponen": total_comp,
        "komponen_terpasang_loko": terpasang,
        "komponen_rakitan_lain": max(0, induk_lain),
        "komponen_tanpa_induk": tanpa_induk,
        "jenis_komponen": db.scalar(
            "SELECT COUNT(DISTINCT component_group) FROM components"
        ),
        "per_group": db.query(
            """
            SELECT component_group AS label, COUNT(*) AS value
            FROM components
            WHERE component_group IS NOT NULL
            GROUP BY component_group
            ORDER BY value DESC
            LIMIT 15
            """
        ),
        "per_status": db.query(
            """
            SELECT COALESCE(system_status, 'TIDAK DIISI') AS label, COUNT(*) AS value
            FROM components
            GROUP BY label
            ORDER BY value DESC
            LIMIT 8
            """
        ),
        "loco_per_dipo": db.query(
            """
            SELECT COALESCE(functional_loc_desc, 'TIDAK DIISI') AS label,
                   COUNT(*) AS value
            FROM locomotives
            GROUP BY label
            ORDER BY value DESC
            LIMIT 12
            """
        ),
    }


@router.get("/filters")
def filters(user: dict = Depends(get_current_user)):
    def values(sql):
        return [row["value"] for row in db.query(sql) if row["value"]]

    return {
        "component_groups": values(
            "SELECT DISTINCT component_group AS value FROM components ORDER BY value"
        ),
        "component_status": values(
            "SELECT DISTINCT system_status AS value FROM components ORDER BY value"
        ),
        "loco_status": values(
            "SELECT DISTINCT system_status AS value FROM locomotives ORDER BY value"
        ),
        "loco_dipo": values(
            """
            SELECT DISTINCT functional_loc_desc AS value
            FROM locomotives ORDER BY value
            """
        ),
    }


@router.get("/locomotives")
def list_locomotives(
    search: str | None = Query(None),
    status: str | None = Query(None),
    dipo: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=5, le=200),
    user: dict = Depends(get_current_user),
):
    where, params = ["1=1"], []

    if search:
        like = f"%{search.upper()}%"
        where.append(
            "(upper(equipment) LIKE ? OR upper(no_kai) LIKE ? "
            "OR upper(description) LIKE ? OR upper(manuf_serial_no) LIKE ?)"
        )
        params += [like] * 4

    if status:
        where.append("system_status = ?")
        params.append(status)

    if dipo:
        where.append("functional_loc_desc = ?")
        params.append(dipo)

    clause = " AND ".join(where)
    total = db.scalar(f"SELECT COUNT(*) FROM locomotives WHERE {clause}", params)

    items = db.query(
        f"""
        SELECT l.equipment, l.no_kai, l.lokomotif_key, l.lokomotif_no,
               l.description, l.manufacturer, l.manuf_serial_no,
               l.system_status, l.user_status, l.kapasitas,
               l.functional_loc, l.functional_loc_desc, l.maint_plant,
               l.criticality, l.changed_on,
               (SELECT COUNT(*) FROM components c
                 WHERE c.superord_equipment = l.equipment) AS komponen_terpasang,
               (SELECT COUNT(*) FROM maintenance_events m
                 WHERE m.lokomotif_key = l.lokomotif_key) AS riwayat_perawatan
        FROM locomotives l
        WHERE {clause}
        ORDER BY l.no_kai
        LIMIT ? OFFSET ?
        """,
        params + [page_size, (page - 1) * page_size],
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
        "items": items,
    }


@router.get("/locomotives/{equipment}")
def locomotive_detail(equipment: str, user: dict = Depends(get_current_user)):
    loco = db.query_one(
        "SELECT * FROM locomotives WHERE equipment = ?", (equipment,)
    )

    if loco is None:
        raise HTTPException(status_code=404, detail="Lokomotif tidak ditemukan")

    komponen = db.query(
        """
        SELECT id, equipment, no_kai, component_group, description,
               system_status, functional_loc_desc, manufacturer, changed_on
        FROM components
        WHERE superord_equipment = ?
        ORDER BY component_group, no_kai
        LIMIT 500
        """,
        (equipment,),
    )

    # Referensi lunak: cocokkan ke data perawatan lewat lokomotif_key.
    riwayat = db.query(
        """
        SELECT id, tahun_maintenance, dipo_induk, jenis_perawatan,
               masuk, keluar,
               (SELECT COUNT(DISTINCT ec.component_no)
                  FROM equipment_components ec
                 WHERE ec.maintenance_event_id = maintenance_events.id) AS component_count
        FROM maintenance_events
        WHERE lokomotif_key = ?
        ORDER BY tahun_maintenance DESC, masuk DESC
        """,
        (loco["lokomotif_key"],),
    )

    return {"locomotive": loco, "komponen": komponen, "riwayat": riwayat}


@router.get("/components")
def list_components(
    search: str | None = Query(None),
    group: str | None = Query(None),
    status: str | None = Query(None),
    terpasang: str | None = Query(None),
    loco: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=5, le=200),
    user: dict = Depends(get_current_user),
):
    where, params = ["1=1"], []

    if search:
        like = f"%{search.upper()}%"
        where.append(
            "(upper(c.equipment) LIKE ? OR upper(c.no_kai) LIKE ? "
            "OR upper(c.description) LIKE ? OR upper(c.manuf_serial_no) LIKE ?)"
        )
        params += [like] * 4

    if group:
        where.append("c.component_group = ?")
        params.append(group)

    if status:
        where.append("c.system_status = ?")
        params.append(status)

    if loco:
        where.append("c.superord_equipment = ?")
        params.append(loco)

    if terpasang == "loko":
        where.append("l.equipment IS NOT NULL")
    elif terpasang == "rakitan":
        where.append("c.superord_equipment IS NOT NULL AND l.equipment IS NULL")
    elif terpasang == "gudang":
        where.append("c.superord_equipment IS NULL")

    clause = " AND ".join(where)

    total = db.scalar(
        f"""
        SELECT COUNT(*) FROM components c
        LEFT JOIN locomotives l ON l.equipment = c.superord_equipment
        WHERE {clause}
        """,
        params,
    )

    items = db.query(
        f"""
        SELECT c.id, c.equipment, c.no_kai, c.no_kai_norm, c.component_group,
               c.description, c.manufacturer, c.manuf_serial_no,
               c.system_status, c.user_status, c.kapasitas, c.criticality,
               c.superord_equipment, c.functional_loc, c.functional_loc_desc,
               c.changed_on, c.source_file,
               l.no_kai AS loco_no_kai, l.lokomotif_no AS loco_no,
               CASE
                   WHEN l.equipment IS NOT NULL THEN 'Terpasang di lokomotif'
                   WHEN c.superord_equipment IS NOT NULL THEN 'Terpasang di rakitan'
                   ELSE 'Tidak terpasang'
               END AS posisi_pasang
        FROM components c
        LEFT JOIN locomotives l ON l.equipment = c.superord_equipment
        WHERE {clause}
        ORDER BY c.component_group, c.no_kai
        LIMIT ? OFFSET ?
        """,
        params + [page_size, (page - 1) * page_size],
    )

    return {
        "total": total,
        "page": page,
        "page_size": page_size,
        "pages": max(1, -(-total // page_size)),
        "items": items,
    }


@router.get("/components/{component_id}")
def component_detail(component_id: int, user: dict = Depends(get_current_user)):
    component = db.query_one("SELECT * FROM components WHERE id = ?", (component_id,))

    if component is None:
        raise HTTPException(status_code=404, detail="Komponen tidak ditemukan")

    induk = None

    if component["superord_equipment"]:
        induk = db.query_one(
            """
            SELECT equipment, no_kai, lokomotif_no, description, functional_loc_desc
            FROM locomotives WHERE equipment = ?
            """,
            (component["superord_equipment"],),
        ) or db.query_one(
            """
            SELECT equipment, no_kai, component_group AS description, functional_loc_desc
            FROM components WHERE equipment = ? LIMIT 1
            """,
            (component["superord_equipment"],),
        )

    # Riwayat pemakaian dari data perawatan, dicocokkan lewat kode cetak.
    riwayat = db.query(
        """
        SELECT ec.id, ec.lokomotif_no, ec.tahun_maintenance, ec.masuk, ec.keluar,
               ec.component_name, ec.asal_kode_cetak, ec.pengganti_kode_cetak,
               ec.keterangan, ec.source_file, ec.source_sheet,
               CASE WHEN upper(trim(ec.asal_kode_cetak)) = ? THEN 'Dilepas'
                    ELSE 'Dipasang' END AS peran
        FROM equipment_components ec
        WHERE upper(trim(ec.asal_kode_cetak)) = ?
           OR upper(trim(ec.pengganti_kode_cetak)) = ?
        ORDER BY ec.tahun_maintenance, ec.id
        """,
        [component["no_kai_norm"]] * 3,
    )

    return {"component": component, "induk": induk, "riwayat": riwayat}


@router.get("/files")
def files(user: dict = Depends(get_current_user)):
    """File master di folder component/ beserta status impornya."""
    imported = {
        row["source_file"]: row
        for row in db.query(
            """
            SELECT source_file, COUNT(*) AS rows, MAX(imported_at) AS imported_at
            FROM components GROUP BY source_file
            UNION ALL
            SELECT source_file, COUNT(*), MAX(imported_at)
            FROM locomotives GROUP BY source_file
            """
        )
    }

    items = []

    if not COMPONENT_DIR.exists():
        return {"items": items, "folder": str(COMPONENT_DIR), "exists": False}

    for path in sorted(COMPONENT_DIR.glob("*.xlsx")):
        if path.name.startswith("~$"):
            continue

        row = imported.get(path.name)
        stat = path.stat()

        items.append(
            {
                "file_name": path.name,
                "size_kb": round(stat.st_size / 1024),
                "rows": row["rows"] if row else 0,
                "imported_at": row["imported_at"] if row else None,
            }
        )

    return {"items": items, "folder": str(COMPONENT_DIR), "exists": True}


ALLOWED_SUFFIXES = {".xlsx", ".xlsm"}


@router.post("/upload")
def upload_master(
    target: str = Query(..., pattern="^(locomotives|components)$"),
    file: UploadFile = File(...),
    user: dict = Depends(require_role("supervisor")),
):
    """Unggah satu berkas master langsung dari UI.

    Dengan ini aplikasi tidak lagi bergantung pada folder `component/` yang
    harus tersedia di disk server — penting untuk deployment yang
    filesystem-nya sementara.

    `target` ditentukan pemanggil, bukan ditebak dari nama berkas: berkas
    unggahan bisa bernama apa saja, sedangkan importer folder mengandalkan
    nama "00 Loco.xlsx" untuk membedakannya.
    """
    from ..master_import import import_components, import_locomotives

    suffix = Path(file.filename or "").suffix.lower()

    if suffix not in ALLOWED_SUFFIXES:
        raise HTTPException(
            status_code=400, detail="Hanya menerima berkas .xlsx atau .xlsm"
        )

    destination = UPLOAD_DIR / file.filename

    with destination.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    try:
        if target == "locomotives":
            result = import_locomotives(destination)
        else:
            result = import_components(destination)
    except Exception as exc:  # noqa: BLE001
        log_activity(
            action="MASTER",
            title=f"Impor master {file.filename} gagal",
            detail=str(exc),
            actor=user["full_name"],
            level="critical",
        )
        raise HTTPException(status_code=422, detail=f"Gagal memproses berkas: {exc}")

    log_activity(
        action="MASTER",
        title=f"{file.filename} diimpor ke {result['target']}",
        detail=f"{result['rows']} baris",
        actor=user["full_name"],
        level="success",
    )

    return result


@router.post("/import")
def run_import(
    payload: ImportRequest,
    user: dict = Depends(require_role("supervisor")),
):
    from ..master_import import import_all, import_file

    try:
        if payload.file_name:
            target = COMPONENT_DIR / payload.file_name

            if not target.exists():
                raise HTTPException(status_code=404, detail="File tidak ditemukan")

            result = import_file(target)
            detail = f"{result['rows']} baris ke {result['target']}"
        else:
            result = import_all(verbose=False)
            detail = (
                f"{result['locomotives']} lokomotif, "
                f"{result['components']} komponen dari {result['berhasil']} file"
            )
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=422, detail=f"Gagal impor master: {exc}")

    log_activity(
        action="MASTER",
        title="Impor master data",
        detail=detail,
        actor=user["full_name"],
        level="success",
    )

    return result
