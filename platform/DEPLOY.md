# Deploy: backend (Cloud Run) + frontend (Vercel)

Arsitekturnya terpisah:

- **Backend** — image [`backend/Dockerfile`](backend/Dockerfile) *backend-only*
  (API mandiri), jalan di Cloud Run, database PostgreSQL (Cloud SQL) lewat
  `DATABASE_URL`. Context build = folder `backend/`.
- **Frontend** — React (`rail-comp-tracker`) di-deploy terpisah ke Vercel,
  memanggil API backend.

## 1. Cloud SQL (PostgreSQL)

```bash
gcloud sql instances create rail-comp-db \
  --database-version=POSTGRES_16 --tier=db-f1-micro --region=asia-southeast2
gcloud sql databases create railcomp --instance=rail-comp-db
gcloud sql users set-password postgres --instance=rail-comp-db --password='PASSWORD_KUAT'
```

Catat nama koneksi instance: `PROJECT:REGION:rail-comp-db`.

## 2. Secret JWT

```bash
python -c "import secrets;print(secrets.token_hex(32))" | \
  gcloud secrets create kai-secret-key --data-file=-
```

## 3. Deploy backend

```bash
# dari folder platform/backend/
gcloud run deploy rail-comp-api \
  --source . \
  --region asia-southeast2 \
  --allow-unauthenticated \
  --add-cloudsql-instances PROJECT:REGION:rail-comp-db \
  --set-secrets KAI_SECRET_KEY=kai-secret-key:latest \
  --set-env-vars "DATABASE_URL=postgresql://postgres:PASSWORD_KUAT@/railcomp?host=/cloudsql/PROJECT:REGION:rail-comp-db"
```

`--source .` (dijalankan dari `backend/`) memakai Cloud Build dengan
`backend/Dockerfile` ini. Cloud Run menyuntik `$PORT`; container sudah bind ke
`0.0.0.0`. Saat start pertama, tabel
dibuat otomatis dan satu akun admin di-seed (`admin@kai.id` / `ayamayam123`).
**Segera ganti passwordnya lewat menu Pengaturan.**

Catat URL backend, mis. `https://rail-comp-api-xxxx.run.app`.

## 4. Deploy frontend ke Vercel

Frontend jadi origin berbeda, jadi hubungkan ke backend dengan salah satu cara:

**A. Rewrite Vercel — disarankan, tanpa CORS.** Peramban memanggil `/api/*` di
domain Vercel, Vercel meneruskan ke Cloud Run. `vercel.json` di repo frontend:

```json
{
  "rewrites": [
    { "source": "/api/:path*", "destination": "https://rail-comp-api-xxxx.run.app/api/:path*" }
  ]
}
```

**B. Panggil langsung + CORS.** Set `VITE_API_BASE_URL=https://rail-comp-api-xxxx.run.app`
di Vercel, lalu di Cloud Run tambahkan `--set-env-vars CORS_ORIGINS=https://NAMA.vercel.app`.
(Auth pakai Bearer token, bukan cookie, jadi aman.)

> Cara A tidak butuh CORS karena dari sudut peramban semuanya satu origin
> (domain Vercel). Cara B perlu `CORS_ORIGINS` diisi domain Vercel.

## 5. Isi data

Semua lewat UI, tak ada berkas yang perlu ada di server:

- **Perawatan** → *Impor data perawatan* (berkas tahunan)
- **Master Lokomotif** / **Katalog Komponen** → tombol impor masing-masing

## Environment backend

| Variabel | Wajib | Keterangan |
|---|---|---|
| `DATABASE_URL` | ya (produksi) | `postgresql://…`; kosong = SQLite (dev lokal saja) |
| `KAI_SECRET_KEY` | ya | kunci tanda tangan JWT |
| `CORS_ORIGINS` | jika pakai cara B | domain Vercel, dipisah koma; default `*` |
| `KAI_DB_POOL_MIN` / `MAX` | opsional | ukuran connection pool (default 1 / 8) |
| `PORT` | — | disuntik Cloud Run |

## Catatan

- **Penyimpanan ephemeral.** Filesystem Cloud Run tidak persisten; itulah alasan
  database di Cloud SQL. Folder unggahan diarahkan ke `/tmp` dan hanya transit.
- **`DATABASE_URL` kosong = SQLite** — hanya untuk dev lokal (`run.bat`), bukan
  Cloud Run (datanya ikut hilang saat instance di-recycle).
- **Connection pool** dipakai otomatis di PostgreSQL, menghindari overhead
  connect-per-query. Cloud SQL satu region memberi latensi query rendah.

## Menjalankan image backend secara lokal (opsional)

```bash
docker build -t rail-comp-api platform/backend/
docker run -p 8080:8080 \
  -e KAI_SECRET_KEY=dev-secret \
  -e DATABASE_URL="postgresql://postgres:pass@host.docker.internal:5432/railcomp" \
  rail-comp-api
```
