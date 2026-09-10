"""Impor master data SAP dari folder `component/`.

Tantangan utamanya bukan pemetaan kolom, melainkan menemukan sheet yang benar:

* sheet data berpindah-pindah (`Sheet1`, `Sheet3`, `Sheet4`, `DATA MASTER`);
* banyak file memuat sheet pivot yang ikut memakai kata "Equipment" sehingga
  menyamar sebagai data — pemilihan sheet karena itu memakai jumlah baris
  terbanyak, bukan sheet pertama yang cocok;
* penulisan header tidak seragam (`No. K A I`, `No.KAI`, `NOKAI`).
"""

import json
import re
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from . import db
from .config import COMPONENT_DIR
from .master_schema import COLUMN_MAP

LOCO_FILE = "00 Loco.xlsx"

# Kolom yang wajib ada supaya sebuah sheet dianggap tabel master.
REQUIRED = {"EQUIPMENT"}
SUPPORTING = {"DESCRIPTION", "NOKAI", "SYSTEMSTATUS", "MAINTPLANT", "CRITICALITY"}

LOCO_FIELDS = [
    "planning_plant", "description", "no_kai", "manufacturer", "manuf_serial_no",
    "position", "system_status", "superord_equipment", "maint_plant", "user_status",
    "main_work_ctr", "cost_center", "planner_group", "catalog_profile",
    "model_number", "kapasitas", "functional_loc", "functional_loc_desc",
    "changed_on", "changed_by", "criticality",
]

COMPONENT_FIELDS = ["equipment"] + LOCO_FIELDS


def norm_header(value) -> str:
    return re.sub(r"[^A-Z0-9]", "", str(value).upper())


def clean(value):
    """Nilai sel -> teks rapi, atau None."""
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, datetime):
        return value.date().isoformat()

    if isinstance(value, float) and value.is_integer():
        return str(int(value))

    text = re.sub(r"\s+", " ", str(value)).strip()

    return text or None


def find_data_sheet(excel_path: Path):
    """Kembalikan (sheet, baris_header, dataframe) dengan baris terbanyak."""
    xls = pd.ExcelFile(excel_path, engine="openpyxl")
    best = None

    for sheet in xls.sheet_names:
        head = pd.read_excel(
            xls, sheet_name=sheet, header=None, dtype=object, nrows=12
        )

        for row in range(len(head)):
            names = {norm_header(v) for v in head.iloc[row].tolist()}

            if not REQUIRED <= names or not (names & SUPPORTING):
                continue

            frame = pd.read_excel(
                xls, sheet_name=sheet, header=row, dtype=object
            ).dropna(how="all")

            if best is None or len(frame) > len(best[2]):
                best = (sheet, row, frame)

            break

    return best


def split_columns(frame):
    """Pisahkan kolom baku (dipetakan) dari kolom tambahan (masuk extra_json)."""
    mapped: dict[str, str] = {}
    extra: list[str] = []
    seen: set[str] = set()

    for column in frame.columns:
        key = norm_header(column)
        target = COLUMN_MAP.get(key)

        if target and target not in seen:
            mapped[target] = column
            seen.add(target)
        elif str(column).startswith("Unnamed:"):
            continue
        else:
            extra.append(column)

    return mapped, extra


def build_row(record, mapped, extra):
    values = {field: clean(record.get(mapped[field])) for field in mapped}

    payload = {
        str(col): clean(record.get(col))
        for col in extra
        if clean(record.get(col)) is not None
    }

    values["extra_json"] = json.dumps(payload, ensure_ascii=False) if payload else None

    return values


def import_locomotives(excel_path: Path) -> dict:
    """`00 Loco.xlsx` -> tabel `locomotives` (upsert pada natural key)."""
    found = find_data_sheet(excel_path)

    if found is None:
        raise ValueError(f"Sheet master tidak ditemukan di {excel_path.name}")

    sheet, header_row, frame = found
    mapped, extra = split_columns(frame)

    if "equipment" not in mapped:
        raise ValueError("Kolom Equipment tidak ada")

    imported_at = datetime.now(timezone.utc).isoformat()
    records = []

    for offset, record in enumerate(frame.to_dict("records")):
        equipment = clean(record.get(mapped["equipment"]))

        if not equipment:
            continue

        values = build_row(record, mapped, extra)

        no_kai = values.get("no_kai")
        digits = re.sub(r"\D", "", no_kai) if no_kai else None

        serial = values.get("manuf_serial_no")

        records.append(
            tuple(
                [equipment]
                + [values.get(field) for field in LOCO_FIELDS]
                + [
                    digits or None,
                    serial or no_kai,
                    values.get("extra_json"),
                    excel_path.name,
                    sheet,
                    header_row + 2 + offset,
                    imported_at,
                ]
            )
        )

    columns = (
        ["equipment"]
        + LOCO_FIELDS
        + ["lokomotif_key", "lokomotif_no", "extra_json",
           "source_file", "source_sheet", "source_row", "imported_at"]
    )

    updatable = [c for c in columns if c != "equipment"]

    sql = f"""
    INSERT INTO locomotives ({", ".join(columns)})
    VALUES ({", ".join(["?"] * len(columns))})
    ON CONFLICT (equipment) DO UPDATE SET
        {", ".join(f"{c} = excluded.{c}" for c in updatable)};
    """

    conn = db.connect()

    try:
        conn.execute("BEGIN")
        conn.executemany(sql, records)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    return {
        "file": excel_path.name,
        "target": "locomotives",
        "sheet": sheet,
        "rows": len(records),
    }


def import_components(excel_path: Path) -> dict:
    """Satu file komponen -> tabel `components`.

    Baris lama milik file dihapus lebih dulu supaya impor ulang menulis ulang,
    bukan menggandakan.
    """
    found = find_data_sheet(excel_path)

    if found is None:
        raise ValueError(f"Sheet master tidak ditemukan di {excel_path.name}")

    sheet, header_row, frame = found
    mapped, extra = split_columns(frame)

    if "equipment" not in mapped:
        raise ValueError("Kolom Equipment tidak ada")

    # Nama file adalah satu-satunya penanda jenis komponen.
    component_group = excel_path.stem.replace("Copy of ", "").strip()
    imported_at = datetime.now(timezone.utc).isoformat()

    records = []

    for offset, record in enumerate(frame.to_dict("records")):
        values = build_row(record, mapped, extra)

        if not values.get("equipment") and not values.get("no_kai"):
            continue

        no_kai = values.get("no_kai")

        records.append(
            tuple(
                [values.get(field) for field in COMPONENT_FIELDS]
                + [
                    component_group,
                    no_kai.upper() if no_kai else None,
                    values.get("extra_json"),
                    excel_path.name,
                    sheet,
                    header_row + 2 + offset,
                    imported_at,
                ]
            )
        )

    columns = COMPONENT_FIELDS + [
        "component_group", "no_kai_norm", "extra_json",
        "source_file", "source_sheet", "source_row", "imported_at",
    ]

    sql = f"""
    INSERT INTO components ({", ".join(columns)})
    VALUES ({", ".join(["?"] * len(columns))})
    ON CONFLICT (source_file, source_row) DO UPDATE SET
        {", ".join(f"{c} = excluded.{c}" for c in columns)};
    """

    conn = db.connect()

    try:
        conn.execute("BEGIN")
        conn.execute(
            "DELETE FROM components WHERE source_file = ?", (excel_path.name,)
        )
        conn.executemany(sql, records)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()

    return {
        "file": excel_path.name,
        "target": "components",
        "group": component_group,
        "sheet": sheet,
        "rows": len(records),
    }


def import_file(excel_path) -> dict:
    excel_path = Path(excel_path)

    if excel_path.name == LOCO_FILE:
        return import_locomotives(excel_path)

    return import_components(excel_path)


def list_master_files(folder=None) -> list[Path]:
    folder = Path(folder or COMPONENT_DIR)

    if not folder.exists():
        return []

    return sorted(
        path
        for path in folder.glob("*.xlsx")
        if not path.name.startswith("~$")
    )


def import_all(folder=None, verbose: bool = True) -> dict:
    files = list_master_files(folder)
    results, errors = [], []

    for path in files:
        try:
            result = import_file(path)
            results.append(result)

            if verbose:
                print(
                    f"  {result['file'][:38]:38} -> {result['target']:12} "
                    f"{result['rows']:7} baris  (sheet {result['sheet']})",
                    flush=True,
                )
        except Exception as exc:  # noqa: BLE001 - satu file gagal tidak menghentikan sisanya
            errors.append({"file": path.name, "error": str(exc)})

            if verbose:
                print(f"  {path.name[:38]:38} -> GAGAL: {exc}", flush=True)

    return {
        "files": len(files),
        "berhasil": len(results),
        "gagal": len(errors),
        "locomotives": sum(r["rows"] for r in results if r["target"] == "locomotives"),
        "components": sum(r["rows"] for r in results if r["target"] == "components"),
        "detail": results,
        "errors": errors,
    }
