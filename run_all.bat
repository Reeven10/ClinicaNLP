@echo off
echo ========================================================
echo   Starting ClinicaNLP - Clinical NLP Mini Project
echo ========================================================
echo [1/2] Starting FastAPI Backend on port 8000...
if exist ".venv\Scripts\python.exe" (
    start "ClinicaNLP - Backend" .venv\Scripts\python.exe -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
) else (
    start "ClinicaNLP - Backend" python -m uvicorn backend.server:app --host 127.0.0.1 --port 8000
)

echo [2/2] Starting Frontend Vite Server on port 3000...
start "ClinicaNLP - Frontend" npm start

echo.
echo ========================================================
echo  ClinicaNLP is running!
echo  Backend API Docs: http://127.0.0.1:8000/docs
echo  Frontend Web App: http://localhost:3000
echo ========================================================
