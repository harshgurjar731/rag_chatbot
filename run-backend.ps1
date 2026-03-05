# Run backend service
Write-Host "Starting Backend service..." -ForegroundColor Green
# python launcher.py Backend -m uvicorn main:app --port 8000 --host 0.0.0.0
.\venv\Scripts\python.exe launcher.py Backend -m uvicorn main:app --port 8000 --host 0.0.0.0
