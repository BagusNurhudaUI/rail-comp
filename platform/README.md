# Locomotive CTS Platform

Platform web untuk data perawatan lokomotif hasil normalisasi dari file
`Daftar Nomor Equipment Lokomotif <tahun>.xlsx` (2019–2026).

Satu proyek, dua folder terpisah:

```
platform/
  backend/          FastAPI + SQLite
    main.py         entry point, sekaligus menyajikan frontend
    app/
      config.py     konfigurasi (path DB, secret, dll)
      db.py         koneksi SQLite + DDL
      security.py   hashing password, JWT, seed user
      deps.py       dependency auth & kontrol peran
      excel_parser.py   parser Excel (port dari main.ipynb)
      ingest.py     ingestion transaksional & idempoten
      master_schema.py  DDL master SAP (locomotives + components)
      master_import.py  importer folder component/
      routers/      auth, dashboard, locomotives, components,
                    imports, master, reports, users
    requirements.txt
  frontend/         SPA vanilla JS, tanpa build step
    index.html      shell aplikasi
    login.html      halaman masuk
    assets/css/app.css
    assets/js/      api.js, charts.js, app.js
```

## Menjalankan

```bash
cd platform/backend
pip install -r requirements.txt
python main.py
```

Buka <http://127.0.0.1:8000>. Dokumentasi API otomatis: `/docs`.

Untuk port lain:

```bash
python -m uvicorn main:app --host 127.0.0.1 --port 8010
```

## Akun demo

| Email | Password | Peran | Akses |
|---|---|---|---|
| `admin@kai.id` | `admin123` | admin | semua, termasuk kelola pengguna |
| `supervisor@kai.id` | `supervisor123` | supervisor | termasuk import Excel |
| `viewer@kai.id` | `viewer123` | viewer | baca saja |

Password disimpan sebagai PBKDF2-SHA256 (180.000 putaran, salt acak).
Token JWT HS256 berlaku 12 jam.

Ganti secret di produksi:

```bash
set KAI_SECRET_KEY=...            # Windows
export KAI_SECRET_KEY=...         # Linux/macOS
```

## Sumber data

Database yang dipakai adalah `kai.db` di root proyek — sama dengan yang
dihasilkan notebook `main.ipynb`. Tabel `app_users` dan `activity_log` milik
aplikasi dibuat terpisah, sehingga rebuild schema oleh notebook tidak
menghapus akun.

Path bisa ditimpa lewat `KAI_DB_PATH`, `KAI_DATA_DIR`, `KAI_UPLOAD_DIR`.

## Halaman

| Halaman | Isi |
|---|---|
| Dashboard | 6 KPI, donut status komponen, komponen terbanyak, aktivitas per tahun, tren bulanan, sebaran dipo, panel temuan, aktivitas terbaru |
| Lokomotif | tabel + cari/filter dipo, tahun, urutan; klik baris → drawer riwayat perawatan |
| Komponen | pencarian lintas kode cetak / no. manuf / nama, filter status, export CSV |
| Riwayat Komponen | telusuri satu nomor equipment melintasi tahun dan lokomotif |
| Perawatan | daftar event + filter status (berjalan/selesai/estimasi), drawer detail komponen |
| Laporan | availability per tahun, kelengkapan metadata, asal tanggal, anomali data |
| Master Lokomotif | 550 lokomotif dari 00 Loco.xlsx; detail berisi komponen terpasang + riwayat perawatan |
| Katalog Komponen | 149.714 baris master SAP; filter jenis/status/posisi pasang, detail berisi induk + riwayat pemakaian |
| Pengguna & Peran | kelola akun (admin) |
| Pengaturan | upload Excel multi-file (drag & drop, dengan konfirmasi), proses ulang file, kosongkan data, riwayat import dengan durasi, ganti password |

## API

Semua endpoint kecuali `/api/auth/login` dan `/api/health` butuh
`Authorization: Bearer <token>`.

```
POST   /api/auth/login              masuk, mengembalikan JWT
GET    /api/auth/me                 profil aktif
POST   /api/auth/change-password

GET    /api/dashboard/summary       KPI
GET    /api/dashboard/charts        data seluruh grafik
GET    /api/dashboard/alerts        temuan yang perlu tindak lanjut
GET    /api/dashboard/activity      aktivitas terbaru
GET    /api/dashboard/filters       opsi filter (tahun, dipo, jenis, dll)

GET    /api/locomotives             ?search &dipo &year &jenis &sort &page
GET    /api/locomotives/{key}       detail + riwayat + komponen teratas

GET    /api/components              ?search &name &year &loco &status &page
GET    /api/components/export       CSV sesuai filter
GET    /api/components/history      ?code= telusuri satu nomor equipment

GET    /api/maintenance             ?search &dipo &jenis &year &status &page
GET    /api/maintenance/{id}        detail event + daftar komponen

GET    /api/imports/sources         file Excel di folder data
GET    /api/imports/history         log ingestion
POST   /api/imports/upload          unggah + proses satu file (supervisor/admin)
                                    multi-file dikirim berurutan dari UI
POST   /api/imports/reingest        proses ulang file yang sudah ada
POST   /api/imports/flush           kosongkan data Excel (admin)

GET    /api/master/summary          KPI + sebaran master data
GET    /api/master/filters          opsi filter master
GET    /api/master/locomotives      ?search &status &dipo &page
GET    /api/master/locomotives/{equipment}
GET    /api/master/components       ?search &group &status &terpasang &loco &page
GET    /api/master/components/{id}
GET    /api/master/files            file di folder component/
POST   /api/master/import           impor master (supervisor/admin)

GET    /api/reports/availability    cakupan & kelengkapan data
GET    /api/reports/anomalies       dipo tak dikenal, tanggal terbalik, dll
GET    /api/reports/top-components

GET    /api/users                   daftar pengguna
POST   /api/users                   tambah (admin)
PATCH  /api/users/{id}              ubah peran / status / password (admin)
DELETE /api/users/{id}              hapus (admin)
```

## Catatan teknis

- **Tanpa dependensi frontend.** Grafik digambar sebagai SVG di
  `assets/js/charts.js`, jadi aplikasi tetap jalan tanpa internet dan tanpa
  `npm install`.
- **Import idempoten.** Mengunggah file yang sama dua kali tidak menggandakan
  data: seluruh baris milik file itu dihapus lalu ditulis ulang dalam satu
  transaksi.
- **Kosongkan data (flush).** `POST /api/imports/flush` — khusus admin, wajib
  mengirim `confirm: "HAPUS"`. Menghapus `maintenance_events`,
  `equipment_components`, dan `sheet_availability`; bisa dibatasi per file lewat
  `source_file` atau per tahun lewat `year`. Akun pengguna, riwayat import, dan
  catatan aktivitas tidak ikut terhapus — flush-nya sendiri dicatat di
  `ingestion_history` dengan status `FLUSHED`. Setelah penghapusan file
  di-`VACUUM` supaya ukurannya menyusut.
- **Master data SAP tanpa FK dan tanpa cascade.** `locomotives` memakai natural
  key `equipment` (550 baris, unik, nol tabrakan dengan nomor komponen);
  `components` memakai surrogate `id` karena 21 nomor equipment muncul dua kali.
  Relasi `superord_equipment` dan `no_kai` dibiarkan lunak: hanya 26.442 dari
  124.152 induk yang ada di `00 Loco`, dan `No. K A I` cocok 45-54% dengan kode
  cetak perawatan. Constraint ketat akan menolak mayoritas baris.
- **Aturan data mengikuti notebook.** Block tanpa nomor lokomotif dianggap form
  template dan dibuang; komponen tanpa asal tetapi punya pengganti disimpan
  sebagai pemasangan baru; `MASUK`/`KELUAR` yang kosong diturunkan dari
  `PROGRAM BULAN` dan ditandai lewat `masuk_source` / `keluar_source`.
