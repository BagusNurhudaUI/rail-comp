"""Schema master data SAP: lokomotif dan komponen.

Sumber: folder `component/` — `00 Loco.xlsx` untuk lokomotif, sisanya satu file
per jenis komponen.

## Kenapa PK-nya tidak strict dan tanpa cascade

Data ini ekspor dari SAP, bukan hasil rancangan relasional, jadi relasinya
tidak pernah lengkap:

* `Superord.Equip.` menunjuk induk komponen. Dari 124.152 baris yang terisi,
  hanya 26.442 yang induknya ada di `00 Loco.xlsx` — sisanya menunjuk rakitan
  antara (bogie, perangkat roda) yang belum tentu ikut terekspor.
* 25.563 baris tidak punya induk sama sekali karena posisinya di gudang.
* `No. K A I` hanya cocok 45–54% dengan kode cetak pada data perawatan; sisanya
  equipment baru yang belum pernah masuk catatan perawatan.

Kalau relasi ini dipasang sebagai `FOREIGN KEY`, mayoritas baris akan ditolak
saat impor. Karena itu semua relasi dibiarkan sebagai **referensi lunak**: kolom
biasa yang diberi index, tanpa `FOREIGN KEY` dan tanpa `ON DELETE CASCADE`.
Menghapus satu lokomotif tidak menyentuh komponennya, dan komponen yatim tetap
boleh ada.

## Pilihan primary key

* `locomotives.equipment` — natural key. 550 baris, seluruhnya unik, dan tidak
  pernah bentrok dengan nomor equipment komponen (diperiksa: 0 tabrakan).
* `components.id` — surrogate. Nomor equipment komponen **hampir** unik
  (150.243 unik dari 150.265), tetapi ada 21 nomor yang muncul dua kali: 15
  lintas file (misalnya nomor yang sama terdaftar di `Oil Pump.xlsx` dan
  `Water Pump.xlsx`) dan 6 di dalam file yang sama. Natural key akan menolak
  baris-baris itu, jadi identitas barisnya dipegang surrogate, sementara
  `equipment` cukup diberi index biasa yang membolehkan duplikat.

Idempotensi impor dipegang `UNIQUE (source_file, source_row)`: menjalankan
ulang impor menulis ulang baris yang sama, bukan menggandakannya.
"""

import os

_IS_PG = os.getenv("DATABASE_URL", "").strip().startswith(("postgres://", "postgresql://"))
_COMP_PK = (
    "id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY"
    if _IS_PG
    else "id INTEGER PRIMARY KEY AUTOINCREMENT"
)

MASTER_SCHEMA_VERSION = 1

# Kolom baku hasil ekspor SAP, dipakai kedua tabel.
SAP_COLUMNS = """
    planning_plant TEXT,
    equipment TEXT,
    description TEXT,
    no_kai TEXT,
    manufacturer TEXT,
    manuf_serial_no TEXT,
    position TEXT,
    system_status TEXT,
    superord_equipment TEXT,
    maint_plant TEXT,
    user_status TEXT,
    main_work_ctr TEXT,
    cost_center TEXT,
    planner_group TEXT,
    catalog_profile TEXT,
    model_number TEXT,
    kapasitas TEXT,
    functional_loc TEXT,
    functional_loc_desc TEXT,
    changed_on TEXT,
    changed_by TEXT,
    criticality TEXT
"""

CREATE_LOCOMOTIVES_SQL = f"""
CREATE TABLE IF NOT EXISTS locomotives (
    -- Natural key: nomor equipment SAP, unik untuk seluruh 550 lokomotif.
    equipment TEXT PRIMARY KEY,

{SAP_COLUMNS.replace("    equipment TEXT,", "    -- kolom equipment sudah menjadi PK di atas")},

    -- Turunan untuk menyambung ke data perawatan.
    -- no_kai "CC20008" -> lokomotif_key "20008", sejajar dengan
    -- maintenance_events.lokomotif_key yang juga hanya menyimpan digit.
    lokomotif_key TEXT,
    -- Bentuk tampilan berspasi, diambil dari ManufSerialNo. ("CC 200 08").
    lokomotif_no TEXT,

    -- Kolom non-baku yang muncul di sebagian file disimpan apa adanya.
    extra_json TEXT,

    source_file TEXT NOT NULL,
    source_sheet TEXT,
    source_row INTEGER,
    imported_at TEXT NOT NULL
);
"""

CREATE_COMPONENTS_SQL = f"""
CREATE TABLE IF NOT EXISTS components (
    -- Surrogate PK: nomor equipment komponen tidak sepenuhnya unik.
    {_COMP_PK},

{SAP_COLUMNS},

    -- Jenis komponen, diambil dari nama file sumber ("Motor Diesel.xlsx").
    component_group TEXT,

    -- no_kai yang sudah dirapikan, dipakai mencocokkan ke kode cetak pada
    -- equipment_components (asal_kode_cetak / pengganti_kode_cetak).
    no_kai_norm TEXT,

    extra_json TEXT,

    source_file TEXT NOT NULL,
    source_sheet TEXT,
    source_row INTEGER,
    imported_at TEXT NOT NULL,

    -- Kunci idempotensi impor, bukan kunci identitas bisnis.
    UNIQUE (source_file, source_row)
);
"""

# Semua index non-unik: relasi di sini bersifat lunak, duplikat dibolehkan.
MASTER_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_loco_no_kai ON locomotives(no_kai);",
    "CREATE INDEX IF NOT EXISTS idx_loco_key ON locomotives(lokomotif_key);",
    "CREATE INDEX IF NOT EXISTS idx_loco_floc ON locomotives(functional_loc);",
    "CREATE INDEX IF NOT EXISTS idx_loco_status ON locomotives(system_status);",

    "CREATE INDEX IF NOT EXISTS idx_comp_equipment ON components(equipment);",
    "CREATE INDEX IF NOT EXISTS idx_comp_no_kai ON components(no_kai_norm);",
    "CREATE INDEX IF NOT EXISTS idx_comp_superord ON components(superord_equipment);",
    "CREATE INDEX IF NOT EXISTS idx_comp_group ON components(component_group);",
    "CREATE INDEX IF NOT EXISTS idx_comp_status ON components(system_status);",
    "CREATE INDEX IF NOT EXISTS idx_comp_floc ON components(functional_loc);",
]

# View pembantu: menyambung relasi lunak tanpa memaksakannya di level tabel.
# LEFT JOIN dipakai supaya komponen yang induknya tidak ada tetap muncul.
CREATE_MASTER_VIEWS = [
    """
    CREATE VIEW v_component_location AS
    SELECT
        c.id,
        c.equipment,
        c.no_kai,
        c.component_group,
        c.description,
        c.system_status,
        c.superord_equipment,
        l.equipment          AS loco_equipment,
        l.no_kai             AS loco_no_kai,
        l.lokomotif_key      AS loco_key,
        l.lokomotif_no       AS loco_no,
        CASE
            WHEN l.equipment IS NOT NULL THEN 'terpasang di lokomotif'
            WHEN c.superord_equipment IS NOT NULL THEN 'terpasang di rakitan lain'
            ELSE 'tidak terpasang'
        END                  AS posisi_pasang,
        COALESCE(c.functional_loc_desc, l.functional_loc_desc) AS lokasi
    FROM components c
    LEFT JOIN locomotives l
        ON l.equipment = c.superord_equipment;
    """,
    """
    CREATE VIEW v_component_maintenance AS
    SELECT
        c.id                 AS component_id,
        c.equipment,
        c.no_kai,
        c.component_group,
        ec.id                AS maintenance_component_id,
        ec.maintenance_event_id,
        ec.lokomotif_no,
        ec.tahun_maintenance,
        ec.masuk,
        ec.keluar,
        CASE
            WHEN upper(trim(ec.asal_kode_cetak)) = c.no_kai_norm THEN 'dilepas'
            ELSE 'dipasang'
        END                  AS peran
    FROM components c
    JOIN equipment_components ec
        ON upper(trim(ec.asal_kode_cetak)) = c.no_kai_norm
        OR upper(trim(ec.pengganti_kode_cetak)) = c.no_kai_norm;
    """,
]


MASTER_VIEW_NAMES = ["v_component_location", "v_component_maintenance"]


def ensure_master_schema(conn) -> None:
    """Buat tabel master, index, dan view. Aman dipanggil berulang."""
    conn.execute(CREATE_LOCOMOTIVES_SQL)
    conn.execute(CREATE_COMPONENTS_SQL)

    for statement in MASTER_INDEXES:
        conn.execute(statement)

    # DROP dulu supaya idempoten: PostgreSQL tak mendukung
    # CREATE VIEW IF NOT EXISTS, dan DROP VIEW IF EXISTS jalan di kedua dialek.
    for name in MASTER_VIEW_NAMES:
        conn.execute(f"DROP VIEW IF EXISTS {name};")

    for statement in CREATE_MASTER_VIEWS:
        conn.execute(statement)


# Pemetaan header Excel -> nama kolom. Pencocokan dilakukan setelah header
# dinormalisasi (huruf besar, tanpa karakter non-alfanumerik), sehingga varian
# penulisan seperti "No. K A I", "No.KAI", dan "NOKAI" jatuh ke kunci yang sama.
COLUMN_MAP = {
    "PLANNINGPLANT": "planning_plant",
    "EQUIPMENT": "equipment",
    "DESCRIPTION": "description",
    "NOKAI": "no_kai",
    "MANUFACTURER": "manufacturer",
    "MANUFSERIALNO": "manuf_serial_no",
    "POSITION": "position",
    "SYSTEMSTATUS": "system_status",
    "SUPERORDEQUIP": "superord_equipment",
    "MAINTPLANT": "maint_plant",
    "USERSTATUS": "user_status",
    "MAINWORKCTR": "main_work_ctr",
    "COSTCENTER": "cost_center",
    "PLANNERGROUP": "planner_group",
    "CATALOGPROFILE": "catalog_profile",
    "MODELNUMBER": "model_number",
    "KAPASITAS": "kapasitas",
    "FUNCTIONALLOC": "functional_loc",
    # Kolom "Description" kedua (dibaca pandas sebagai "Description.1") berisi
    # nama lokasi, misalnya "DIPO LOKOMOTIF CIREBON".
    "DESCRIPTION1": "functional_loc_desc",
    "CHANGEDON": "changed_on",
    "CHANGEDBY": "changed_by",
    "CRITICALITY": "criticality",
}
