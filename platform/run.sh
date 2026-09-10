#!/usr/bin/env bash
cd "$(dirname "$0")/backend"
echo
echo "  Locomotive CTS Platform"
echo "  http://127.0.0.1:8000"
echo
echo "  Mode auto-reload aktif: perubahan kode langsung dimuat ulang."
echo
python -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
