# Run ingestion pool service
Write-Host "Starting Ingestion Pool..." -ForegroundColor Green
# python launcher.py ingestion_pool main.py --port 8003
.\venv\Scripts\python.exe launcher.py ingestion_pool main.py --port 8003
