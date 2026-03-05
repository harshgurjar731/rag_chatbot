# Run worker pool service
Write-Host "Starting Worker Pool..." -ForegroundColor Green
# python launcher.py worker_pool main.py --port 8002
.\venv\Scripts\python.exe launcher.py worker_pool main.py --port 8002
