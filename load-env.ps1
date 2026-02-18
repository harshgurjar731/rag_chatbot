# Localhost Configuration for Hybrid Setup (Reloaded)

# Load .env.local into PowerShell environment
Write-Host "📦 Loading .env.local..." -ForegroundColor Green

if (-not (Test-Path .env.local)) {
    Write-Host "❌ .env.local not found!" -ForegroundColor Red
    Write-Host "   Please create .env.local with localhost configuration" -ForegroundColor Yellow
    exit 1
}

$lines = Get-Content .env.local
foreach ($line in $lines) {
    if ($line -match '^\s*([^#][^=]+)=(.*)$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        Set-Item -Path "env:$name" -Value $value
        Write-Host "   ✓ $name" -ForegroundColor Gray
    }
}

Write-Host "✅ Environment loaded!" -ForegroundColor Green
Write-Host "   DB_HOST: $env:DB_HOST" -ForegroundColor Cyan
Write-Host "   REDIS_HOST: $env:REDIS_HOST" -ForegroundColor Cyan
Write-Host "   CHROMA_SERVER_HOST: $env:CHROMA_SERVER_HOST" -ForegroundColor Cyan
