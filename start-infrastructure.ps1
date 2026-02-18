# Start infrastructure services only
$env:Path += ";C:\Program Files\Docker\Docker\resources\bin"
Write-Host "Starting infrastructure services..." -ForegroundColor Green
docker compose -f docker-compose.infrastructure.yml up -d
Start-Sleep -Seconds 5
Write-Host "Infrastructure started!" -ForegroundColor Green
Write-Host "  Redis:      localhost:6379" -ForegroundColor Cyan
Write-Host "  PostgreSQL: localhost:5432" -ForegroundColor Cyan
Write-Host "  ChromaDB:   localhost:8001" -ForegroundColor Cyan
Write-Host "  Phoenix:    localhost:6006" -ForegroundColor Cyan
