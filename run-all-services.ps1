# Master script to run all RAG Chatbot services
Write-Host "Starting all services..." -ForegroundColor Cyan

# 1. Start Infrastructure (Redis, Database, etc. via Docker if needed)
# Uncomment the line below if you want to automatically start infrastructure
.\start-infrastructure.ps1

# 2. Start Backend
Write-Host "[*] Starting Backend..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\run-backend.ps1"

# 3. Start Worker Pool
Write-Host "[*] Starting Worker Pool..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\run-worker-pool.ps1"

# 4. Start Ingestion Pool
Write-Host "[*] Starting Ingestion Pool..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\run-ingestion-pool.ps1"

# 5. Start Evaluation Pool
Write-Host "[*] Starting Evaluation Pool..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", ".\run-evaluation-pool.ps1"

# 6. Start Frontend
Write-Host "[*] Starting Frontend..."
Start-Process powershell -ArgumentList "-NoExit", "-Command", "Set-Location Frontend\docu-chatter-main; npm run dev"

Write-Host "`n[!] All services have been launched in separate windows." -ForegroundColor Green
Write-Host "[!] Please check each window for its specific logs." -ForegroundColor Yellow
