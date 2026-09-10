# syntax=docker/dockerfile:1
#
# Image backend saja (API mandiri). Context build = folder backend/ ini.
# Frontend di-deploy terpisah ke Vercel, jadi tidak ada tahap build Node.

FROM python:3.12-slim

# - PYTHONUNBUFFERED: log langsung terlihat di Cloud Run
# - PYTHONDONTWRITEBYTECODE: tak perlu .pyc di container
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8080 \
    KAI_UPLOAD_DIR=/tmp/kai-uploads

WORKDIR /app

# Manifest lebih dulu supaya layer dependency ter-cache selama tak berubah.
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

# Pengguna non-root; /tmp tetap bisa ditulis untuk unggahan sementara.
RUN useradd --create-home --uid 10001 appuser
USER appuser

# exec + shell agar $PORT dari Cloud Run terbaca.
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT}
