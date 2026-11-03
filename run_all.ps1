Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "  Starting ClinicaNLP - Clinical NLP Mini Project" -ForegroundColor Green
Write-Host "========================================================" -ForegroundColor Cyan

$pyCmd = if (Test-Path "$PSScriptRoot\.venv\Scripts\python.exe") { "$PSScriptRoot\.venv\Scripts\python.exe" } elseif (Get-Command py -ErrorAction SilentlyContinue) { "py" } else { "python" }
$pyArgs = "-m uvicorn backend.server:app --host 127.0.0.1 --port 8000"

Write-Host "[1/2] Starting FastAPI NLP Backend on port 8000..." -ForegroundColor Yellow
$backend = Start-Process $pyCmd -ArgumentList $pyArgs -PassThru

Write-Host "[2/2] Starting Frontend Vite Server on port 3000..." -ForegroundColor Yellow
$frontend = Start-Process npm -ArgumentList "start" -PassThru

Write-Host "`n========================================================" -ForegroundColor Cyan
Write-Host " ClinicaNLP is running!" -ForegroundColor Green
Write-Host " Backend API Docs: http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host " Frontend Web App: http://localhost:3000" -ForegroundColor White
Write-Host "========================================================" -ForegroundColor Cyan
