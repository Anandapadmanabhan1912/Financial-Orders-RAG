@echo off
echo ===================================================
echo   ORDERWISE - Kerala Finance Order Knowledge Engine
echo ===================================================
echo [1/3] Installing Python dependencies...
python -m pip install -r requirements.txt

echo [2/3] Generating Seed Kerala Finance GO PDFs...
python backend/seed_data/generate_seed_gos.py

echo [3/3] Launching FastAPI Backend & Frontend Server...
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
pause
