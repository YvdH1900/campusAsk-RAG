# ================================================
# CampusAsk-RAG Stop Script (Windows)
# ================================================
# Usage: .\stop.ps1
# ================================================

$PROJECT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $PROJECT_DIR

function Write-Step { Write-Host "`n>>> $args" -ForegroundColor Cyan }
function Write-Info  { Write-Host "[INFO]  $args" -ForegroundColor Green }
function Write-Warn  { Write-Host "[WARN]  $args" -ForegroundColor Yellow }

$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"

if (Get-Command "docker-compose" -ErrorAction SilentlyContinue) {
    $composeCmd = "docker-compose"
} else {
    $composeCmd = "docker compose"
}

# ==================== 1. Stop Docker containers ====================
Write-Step "1. Stopping Docker containers..."
& $composeCmd down 2>$null
Write-Info "Docker containers stopped."

# ==================== 2. Kill local backend processes ====================
Write-Step "2. Stopping local Python processes..."

$killed = $false
Get-Process -Name "python" -ErrorAction SilentlyContinue | ForEach-Object {
    $cmdline = (Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
    if ($cmdline -match "app\.main|celery") {
        Stop-Process -Id $_.Id -Force
        Write-Info "Stopped PID $($_.Id) ($cmdline)"
        $killed = $true
    }
}
if (-not $killed) {
    Write-Info "No backend/Celery processes found running."
}

# ==================== 3. Kill frontend Node ====================
Write-Step "3. Stopping Vite frontend..."
$nodeKilled = $false
Get-Process -Name "node" -ErrorAction SilentlyContinue | ForEach-Object {
    $cmdline = (Get-WmiObject Win32_Process -Filter "ProcessId=$($_.Id)").CommandLine
    if ($cmdline -match "vite") {
        Stop-Process -Id $_.Id -Force
        Write-Info "Stopped Node PID $($_.Id) (vite)"
        $nodeKilled = $true
    }
}
if (-not $nodeKilled) {
    Write-Info "No Vite processes found running."
}

$ErrorActionPreference = $prevEAP

Write-Step "All services stopped."
Write-Host ""
Write-Host "To also delete Docker volumes (Milvus data, etc.):" -ForegroundColor Yellow
Write-Host "  $composeCmd down -v" -ForegroundColor Yellow
Write-Host ""
Write-Host "Press any key to close..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
