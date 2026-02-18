# Run evaluation pool service
Write-Host "🚀 Starting Evaluation Pool..." -ForegroundColor Green
python launcher.py evaluation_pool evaluation_worker.py
