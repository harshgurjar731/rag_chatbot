Write-Host "Starting Video Processing Pool..." -ForegroundColor Green
$env:PYTHONPATH = (Get-Location).Path + "\video_processing_pool"
.\venv\Scripts\python.exe .\launcher.py video_processing_pool main.py --port 8004
