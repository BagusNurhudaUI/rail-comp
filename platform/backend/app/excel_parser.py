"""Parser Excel "DAFTAR NOMOR EQUIPMENT LOKOMOTIF".

Port dari notebook `main.ipynb` (schema v3). Aturan yang dipegang:

* block dicari lewat marker `NAMA KOMPONEN`, bukan nomor row absolut;
* varian label antar tahun dipetakan ke satu field;
* block tanpa nomor lokomotif dianggap form template dan dibuang;
* baris legenda (`= DISMANTLE`, ...) menutup tabel komponen;
* `MASUK` / `KELUAR` kosong diturunkan dari `PROGRAM BULAN`.
"""

import calendar
import re
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from .config import BLOCK_WIDTH

COMPONENT_COLUMNS = [
    "component_no",
    "component_name",
    "asal_kode_cetak",
    "asal_no_manuf",
    "pengganti_kode_cetak",
    "pengganti_no_manuf",
    "keterangan",
]

COMPONENT_DETAIL_COLUMNS = [
    "asal_kode_cetak",
    "asal_no_manuf",
    "pengganti_kode_cetak",
    "pengganti_no_manuf",
    "keterangan",
]

METADATA_LABELS = {
    "no_seri_lokomotif": [
        "NO.SERI LOKOMOTIF",
        "NO. SERI LOKOMOTIF",
        "NO SERI LOKOMOTIF",
        "NO.SERI LOKO",
        "NO. SERI LOKO",
        "NO SERI LOKO",
    ],
    "dipo_induk": ["DIPO INDUK"],
    "jenis_perawatan": ["JENIS PERAWATAN"],
    "program_bulan": ["PROGRAM BULAN"],
    "masuk": ["MASUK", "MASUK BY", "MSK"],
    "keluar": ["KELUAR", "KELUAR BY", "SELESAI"],
    "ganti_di_dipo": ["GANTI DI DIPO"],
}

BULAN_INDONESIA = {
    "JANUARI": 1,
    "FEBRUARI": 2,
    "MARET": 3,
    "APRIL": 4,
    "MEI": 5,
    "JUNI": 6,
    "JULI": 7,
    "AGUSTUS": 8,
    "SEPTEMBER": 9,
    "OKTOBER": 10,
    "NOVEMBER": 11,
    "DESEMBER": 12,
}

BULAN_SINGKAT = {
    "JAN": 1, "FEB": 2, "PEB": 2, "MAR": 3, "APR": 4, "MEI": 5, "JUN": 6,
    "JUL": 7, "AGU": 8, "AGS": 8, "AGT": 8, "SEP": 9, "SEPT": 9, "OKT": 10,
    "NOP": 11, "NOV": 11, "DES": 12,
}


def clean_cell(value):
    if value is None:
        return None

    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass

    if isinstance(value, str):
        value = re.sub(r"\s+", " ", value.replace("\n", " ")).strip()

        if value == "":
            return None

    return value


def blank_placeholder(value):
    """Anggap kosong bila nilainya hanya tanda hubung/tanda baca.

    Di form sumber, sel kosong sering diisi "-", "–", "—", ".", atau "?" sebagai
    penanda "tidak ada". Kalau disimpan apa adanya, "-" pada kolom pengganti
    terbaca seolah ada part pengganti. Kode asli seperti "CA-1152133" tetap
    dipertahankan karena memuat karakter alfanumerik.
    """
    if value is None:
        return None

    if isinstance(value, str) and not any(ch.isalnum() for ch in value):
        return None

    return value


def normalize_label(value) -> str:
    value = clean_cell(value)

    if value is None:
        return ""

    text = re.sub(r"[^A-Z0-9]+", " ", str(value).upper().strip())

    return re.sub(r"\s+", " ", text).strip()


ALL_LABEL_FORMS = {
    normalize_label(variant)
    for variants in METADATA_LABELS.values()
    for variant in variants
} | {
    "NO",
    "NAMA KOMPONEN",
    "KOMPONEN ASAL",
    "KOMPONEN PENGGANTI",
    "KET",
    "KODE CETAK",
    "NO MANUF",
}


def strip_leading_colon(value):
    if isinstance(value, str):
        value = re.sub(r"^\s*:\s*", "", value).strip()

        if value == "":
            return None

    return value


def extract_year(file_name) -> int | None:
    match = re.search(r"(20\d{2})", str(file_name))

    return int(match.group(1)) if match else None


def detect_block_start_columns(df) -> list[int]:
    starts = []

    for r in range(df.shape[0]):
        for c in range(df.shape[1]):
            if normalize_label(df.iat[r, c]) == "NAMA KOMPONEN" and c - 1 >= 0:
                starts.append(c - 1)

    return sorted(set(starts))


def label_matches(value, variants) -> bool:
    normalized = normalize_label(value)

    if normalized == "":
        return False

    return normalized in {normalize_label(v) for v in variants}


def first_value_to_right(df, row_idx, label_col, block_end, label_text):
    label_tokens = set(normalize_label(label_text).split())

    for c in range(label_col + 1, block_end + 1):
        value = strip_leading_colon(clean_cell(df.iat[row_idx, c]))

        if value is None:
            continue

        normalized = normalize_label(value)

        # "INDUK" adalah pecahan label "DIPO INDUK", bukan nilai.
        if normalized and set(normalized.split()) <= label_tokens:
            continue

        if normalized in ALL_LABEL_FORMS:
            continue

        return value

    return None


def parse_metadata(df, block_start, block_width=BLOCK_WIDTH, search_rows=20):
    block_end = min(block_start + block_width - 1, df.shape[1] - 1)
    result = {key: None for key in METADATA_LABELS}

    for r in range(min(search_rows, df.shape[0])):
        for c in range(block_start, block_end + 1):
            cell = df.iat[r, c]

            for key, variants in METADATA_LABELS.items():
                if result[key] is not None or not label_matches(cell, variants):
                    continue

                value = first_value_to_right(
                    df, r, c, block_end, str(clean_cell(cell))
                )

                if value is not None:
                    result[key] = value

    return result


def normalize_loco(value):
    value = clean_cell(value)

    if value is None:
        return None, None

    text = re.sub(r"\([^)]*\)", "", str(value)).upper()
    text = strip_leading_colon(text) or ""
    text = re.sub(r"\s+", " ", re.sub(r"[^A-Z0-9]+", " ", text).strip())

    if text == "":
        return None, None

    digits = re.sub(r"\D", "", text)

    return text, (digits or None)


def parse_date(value):
    value = clean_cell(value)

    if value is None:
        return None

    parsed = pd.to_datetime(value, errors="coerce", dayfirst=True)

    if pd.isna(parsed):
        return None

    return parsed.date()


def parse_program_bulan(value, fallback_year):
    """PROGRAM BULAN -> (tanggal 1, tanggal akhir bulan)."""
    text = normalize_label(value)

    if text == "":
        return None, None

    month = None

    for token in text.split():
        if token in BULAN_INDONESIA:
            month = BULAN_INDONESIA[token]
            break

        if token in BULAN_SINGKAT:
            month = BULAN_SINGKAT[token]
            break

    if month is None:
        return None, None

    year = fallback_year
    match = re.search(r"(20\d{2})", text)

    if match:
        year = int(match.group(1))

    if year is None:
        return None, None

    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def find_component_header_row(df, block_start, block_width=BLOCK_WIDTH):
    block_end = min(block_start + block_width, df.shape[1])

    for r in range(df.shape[0]):
        for c in range(block_start, block_end):
            if normalize_label(df.iat[r, c]) == "NAMA KOMPONEN":
                return r

    return None


def row_is_empty(values) -> bool:
    return all(v is None for v in values)


def row_is_legend(values) -> bool:
    texts = [str(v).strip() for v in values if v is not None]

    return bool(texts) and any(t.startswith("=") for t in texts)


def row_is_header_repeat(values) -> bool:
    normalized = {normalize_label(v) for v in values}

    return bool(normalized & {"NAMA KOMPONEN", "KODE CETAK", "NO MANUF"})


def parse_components(df, block_start, block_width=BLOCK_WIDTH):
    header_row = find_component_header_row(df, block_start, block_width)

    if header_row is None:
        return pd.DataFrame(columns=COMPONENT_COLUMNS), None

    rows = []

    for r in range(header_row + 2, df.shape[0]):
        values = [
            clean_cell(df.iat[r, c]) if c < df.shape[1] else None
            for c in range(block_start, block_start + block_width)
        ]

        if row_is_legend(values):
            break

        if row_is_empty(values) or row_is_header_repeat(values):
            continue

        rows.append(values)

    result = pd.DataFrame(rows, columns=COMPONENT_COLUMNS)

    if result.empty:
        return result, header_row

    for col in ("component_no", "component_name"):
        result[col] = result[col].replace("", np.nan).ffill()

    # Bersihkan placeholder "-" dsb. pada kolom detail supaya tidak terbaca
    # sebagai kode/keterangan sungguhan (mis. pengganti "-" -> kosong).
    for col in COMPONENT_DETAIL_COLUMNS:
        result[col] = result[col].map(blank_placeholder)

    result = result[
        result[COMPONENT_DETAIL_COLUMNS].notna().any(axis=1)
    ].reset_index(drop=True)

    return result, header_row


def maintenance_year(masuk, keluar, source_year):
    for value in (masuk, keluar):
        if value is not None:
            return value.year

    return source_year


def parse_workbook(excel_path) -> dict:
    """Parse satu workbook menjadi events, components, dan availability."""
    excel_path = Path(excel_path)
    source_file = excel_path.name
    source_year = extract_year(source_file)

    xls = pd.ExcelFile(excel_path, engine="openpyxl")

    events: list[dict] = []
    components: list[dict] = []
    availability: list[dict] = []

    for sheet_index, sheet_name in enumerate(xls.sheet_names, start=1):
        # Nama sheet ikut menjadi kunci identitas block, sedangkan sebagian file
        # menyimpannya dengan spasi di ujung ("Sheet1 " pada 2020, dua sheet pada
        # 2021). Dinormalisasi sekali di sini supaya event, komponen, dan
        # availability memakai nilai yang persis sama. Pembacaan worksheet tetap
        # memakai nama asli karena itu yang dikenal openpyxl.
        sheet_label = sheet_name.strip() or sheet_name

        record = {
            "source_file": source_file,
            "source_year": source_year,
            "sheet_index": sheet_index,
            "source_sheet": sheet_label,
            "block_count": 0,
            "template_block_count": 0,
            "event_count": 0,
            "component_count": 0,
            "status": "OK",
            "message": None,
        }

        try:
            df = pd.read_excel(
                xls,
                sheet_name=sheet_name,
                header=None,
                dtype=object,
                engine="openpyxl",
            )

            starts = detect_block_start_columns(df)
            record["block_count"] = len(starts)

            if not starts:
                record["status"] = "NO_BLOCK"
                record["message"] = "marker NAMA KOMPONEN tidak ditemukan"
                availability.append(record)
                continue

            for block_index, start_col in enumerate(starts, start=1):
                metadata = parse_metadata(df, start_col)
                block_rows, _ = parse_components(df, start_col)

                # Block tanpa nomor lokomotif = form template, dibuang.
                if metadata["no_seri_lokomotif"] is None:
                    record["template_block_count"] += 1
                    continue

                lokomotif_no, lokomotif_key = normalize_loco(
                    metadata["no_seri_lokomotif"]
                )

                masuk = parse_date(metadata["masuk"])
                keluar = parse_date(metadata["keluar"])
                masuk_source = "excel" if masuk else None
                keluar_source = "excel" if keluar else None

                if masuk is None or keluar is None:
                    awal, akhir = parse_program_bulan(
                        metadata["program_bulan"], source_year
                    )

                    if masuk is None and awal is not None:
                        masuk, masuk_source = awal, "program_bulan"

                    if keluar is None and akhir is not None:
                        keluar, keluar_source = akhir, "program_bulan"

                tahun = maintenance_year(masuk, keluar, source_year)

                events.append(
                    {
                        "source_file": source_file,
                        "source_year": source_year,
                        "source_sheet": sheet_label,
                        "block_index": block_index,
                        "no_seri_lokomotif": metadata["no_seri_lokomotif"],
                        "lokomotif_no": lokomotif_no,
                        "lokomotif_key": lokomotif_key,
                        "dipo_induk": metadata["dipo_induk"],
                        "jenis_perawatan": metadata["jenis_perawatan"],
                        "program_bulan": metadata["program_bulan"],
                        "ganti_di_dipo": metadata["ganti_di_dipo"],
                        "masuk": masuk.isoformat() if masuk else None,
                        "keluar": keluar.isoformat() if keluar else None,
                        "masuk_source": masuk_source,
                        "keluar_source": keluar_source,
                        "tahun_maintenance": tahun,
                        "component_count": len(block_rows),
                    }
                )

                record["event_count"] += 1
                record["component_count"] += len(block_rows)

                for row in block_rows.to_dict("records"):
                    row_value = {
                        key: (None if pd.isna(value) else value)
                        for key, value in row.items()
                    }

                    components.append(
                        {
                            "source_file": source_file,
                            "source_year": source_year,
                            "source_sheet": sheet_label,
                            "block_index": block_index,
                            "lokomotif_no": lokomotif_no,
                            "lokomotif_key": lokomotif_key,
                            "masuk": masuk.isoformat() if masuk else None,
                            "keluar": keluar.isoformat() if keluar else None,
                            "tahun_maintenance": tahun,
                            **row_value,
                        }
                    )

            if record["event_count"] == 0 and record["block_count"]:
                record["status"] = "TEMPLATE_ONLY"
                record["message"] = "seluruh block masih form kosong"

        except Exception as exc:  # noqa: BLE001 - dicatat, tidak menggagalkan file
            record["status"] = "ERROR"
            record["message"] = f"{type(exc).__name__}: {exc}"

        availability.append(record)

    return {
        "source_file": source_file,
        "source_year": source_year,
        "events": events,
        "components": components,
        "availability": availability,
    }
