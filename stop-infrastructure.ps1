# Stop infrastructure services
# Add Docker to PATH if not already present
$env:Path += ";C:\Program Files\Docker\Docker\resources\bin"

Write-Host "🛑 Stopping infrastructure services..." -ForegroundColor Red
docker compose -f docker-compose.infrastructure.yml down

Write-Host "✅ Infrastructure stopped!" -ForegroundColor Green
