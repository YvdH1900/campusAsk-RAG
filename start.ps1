# ================================================
# CampusAsk-RAG Test Env One-Click Start (Windows)
# ================================================
# Pre-requisites:
#   - MySQL, Redis, RabbitMQ installed and running locally
#   - Docker Desktop installed and running
#   - Python 3.11+ installed
#   - Node.js 18+ installed
#
# Usage:
#   .\start.ps1
# ================================================

$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$PROJECT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $PROJECT_DIR

function Write-Step { Write-Host "`n>>> $args" -ForegroundColor Cyan }
function Write-Info  { Write-Host "[INFO]  $args" -ForegroundColor Green }
function Write-Warn  { Write-Host "[WARN]  $args" -ForegroundColor Yellow }
function Write-Err   { Write-Host "[ERROR] $args" -ForegroundColor Red }

# ==================== 1. Check Docker ====================
Write-Step "1. Checking Docker..."
try {
    docker info 2>&1 | Out-Null
    Write-Info "Docker is running"

    if (Get-Command "docker-compose" -ErrorAction SilentlyContinue) {
        $composeCmd = "docker-compose"
    } else {
        docker compose version 2>&1 | Out-Null
        $composeCmd = "docker compose"
    }
    Write-Info "Using: $composeCmd"
} catch {
    Write-Err "Docker is not running. Please start Docker Desktop first."
    exit 1
}

# ==================== 2. Check local services ====================
Write-Step "2. Checking local services..."

function Test-Port($port, $serviceName) {
    $tcp = New-Object System.Net.Sockets.TcpClient
    try {
        $tcp.Connect("localhost", $port)
        Write-Info "$serviceName (port $port) - OK"
        return $true
    } catch {
        Write-Err "$serviceName (port $port) - NOT RUNNING"
        return $false
    } finally {
        $tcp.Close()
    }
}

$servicesToCheck = @(
    @{ Port = 3306; Name = "MySQL" },
    @{ Port = 6379; Name = "Redis" },
    @{ Port = 5672; Name = "RabbitMQ" }
)

$failedServices = @()

foreach ($service in $servicesToCheck) {
    if (-not (Test-Port $service.Port $service.Name)) {
        $failedServices += $service
    }
}

if ($failedServices.Count -gt 0) {
    Write-Host ""
    Write-Warn "Detected the following services not running:"
    foreach ($service in $failedServices) {
        Write-Host "   - $($service.Name) (Port $($service.Port))"
    }
    Write-Host ""
    
    # 检查是否所有服务都未运行
    if ($failedServices.Count -eq $servicesToCheck.Count) {
        Write-Info "All basic services (MySQL, Redis, RabbitMQ) are not running"
        $response = Read-Host "Do you want to install and start all services using Docker at once? (Y/N)"
        
        if ($response -eq 'Y' -or $response -eq 'y') {
            $servicesToInstall = $failedServices
            Write-Info "Will install all services: $($servicesToInstall.Name -join ', ')"
        } else {
            Write-Host ""
            Write-Warn "Skipped automatic installation"
            Write-Info "Please manually start the following services and re-run this script:"
            foreach ($service in $failedServices) {
                Write-Info "   - $($service.Name)"
            }
            Write-Host ""
            Write-Info "To install using Docker, run:"
            Write-Info "   docker-compose -f docker-compose.services.yml up -d"
            Write-Host ""
            exit 1
        }
    } else {
        # 部分服务未运行，逐个询问
        Write-Info "Detected partial services not running, will confirm installation requirements one by one"
        Write-Host ""
        
        $servicesToInstall = @()
        
        foreach ($service in $failedServices) {
            $response = Read-Host "Do you want to install and start $($service.Name) using Docker? (Y/N)"
            
            if ($response -eq 'Y' -or $response -eq 'y') {
                $servicesToInstall += $service
                Write-Info "[OK] Selected to install $($service.Name)"
            } else {
                Write-Host ""
                Write-Warn "Skipped installing $($service.Name)"
                Write-Info "Please manually start $($service.Name) and re-run this script"
                Write-Info "To install $($service.Name) using Docker, run:"
                
                switch ($service.Name) {
                    "MySQL" {
                        Write-Info "   docker run -d --name campusask_mysql -p 3306:3306 -e MYSQL_ROOT_PASSWORD=root -e MYSQL_DATABASE=campus_ask mysql:8.0"
                    }
                    "Redis" {
                        Write-Info "   docker run -d --name campusask_redis -p 6379:6379 redis:7-alpine"
                    }
                    "RabbitMQ" {
                        Write-Info "   docker run -d --name campusask_rabbitmq -p 5672:5672 -p 15672:15672 rabbitmq:3-management-alpine"
                    }
                }
                Write-Host ""
                exit 1
            }
        }
    }
    
    # 安装选中的服务
    if ($servicesToInstall.Count -gt 0) {
        Write-Step "2.1 Installing selected services with Docker..."
        
        # 检查是否安装所有服务
        $installAll = ($servicesToInstall.Count -eq $servicesToCheck.Count)
        
        if ($installAll) {
            # 使用现有的 docker-compose.services.yml
            if (-not (Test-Path "docker-compose.services.yml")) {
                Write-Err "未找到 docker-compose.services.yml 文件"
                exit 1
            }
        } else {
            # 创建临时的 docker-compose 配置，只包含选中的服务
            $composeContent = "version: '3.8'`n`nservices:`n"
            
            foreach ($service in $servicesToInstall) {
                switch ($service.Name) {
                    "MySQL" {
                        $composeContent += @"
  mysql:
    image: mysql:8.0
    container_name: campusask_mysql
    restart: always
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: campus_ask
      TZ: Asia/Shanghai
    ports:
      - "3306:3306"
    volumes:
      - mysql_data:/var/lib/mysql
    command:
      - --character-set-server=utf8mb4
      - --collation-server=utf8mb4_unicode_ci

"@
                    }
                    "Redis" {
                        $composeContent += @"
  redis:
    image: redis:7-alpine
    container_name: campusask_redis
    restart: always
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

"@
                    }
                    "RabbitMQ" {
                        $composeContent += @"
  rabbitmq:
    image: rabbitmq:3-management-alpine
    container_name: campusask_rabbitmq
    restart: always
    environment:
      RABBITMQ_DEFAULT_USER: guest
      RABBITMQ_DEFAULT_PASS: guest
    ports:
      - "5672:5672"
      - "15672:15672"
    volumes:
      - rabbitmq_data:/var/lib/rabbitmq

"@
                    }
                }
            }
            
            $composeContent += "volumes:`n  mysql_data:`n  redis_data:`n  rabbitmq_data:`n"
            
            $tempComposePath = Join-Path $PROJECT_DIR "docker-compose.temp.yml"
            $composeContent | Out-File -FilePath $tempComposePath -Encoding UTF8
            Write-Info "Created temporary Docker Compose configuration file: $tempComposePath"
        }
        
        # 启动服务
        Write-Info "Starting selected services..."
        
        $prevEAP = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        
        if ($installAll) {
            & $composeCmd -f "docker-compose.services.yml" up -d 2>$null
        } else {
            & $composeCmd -f "docker-compose.temp.yml" up -d 2>$null
        }
        
        $ErrorActionPreference = $prevEAP
        
        Write-Info "Waiting for services to start (approximately 30-60 seconds)..."
        $waited = 0
        $maxWait = 90
        
        do {
            Start-Sleep -Seconds 5
            $waited += 5
            $progress = [math]::Min(($waited / $maxWait) * 100, 100)
            Write-Host -NoNewline "`r[$('=' * ([int]($progress / 5)))$(' ' * (20 - [int]($progress / 5)))] $([int]$progress)% ($waited sec/$maxWait sec)"
        } while ($waited -lt $maxWait)
        
        Write-Host ""
        
        # 验证服务是否启动成功
        $allServicesReady = $true
        foreach ($service in $servicesToInstall) {
            $tcp = New-Object System.Net.Sockets.TcpClient
            try {
                $tcp.Connect("localhost", $service.Port)
                Write-Info "$($service.Name) (port $($service.Port)) - Running"
            } catch {
                Write-Warn "$($service.Name) (port $($service.Port)) - Not responding, please check later"
                $allServicesReady = $false
            } finally {
                $tcp.Close()
            }
        }
        
        if ($allServicesReady) {
            Write-Info "[SUCCESS] All selected services started successfully!"
        } else {
            Write-Warn "[WARNING] Some services may not be fully ready, please retry later"
            Write-Info "You can use the following commands to check service status:"
            Write-Info "   docker ps"
            foreach ($service in $servicesToInstall) {
                Write-Info "   docker logs campusask_$($service.Name.ToLower())"
            }
        }
        
        # 清理临时文件
        if (-not $installAll -and (Test-Path "docker-compose.temp.yml")) {
            Remove-Item "docker-compose.temp.yml" -Force
            Write-Info "Cleaned up temporary configuration file"
        }
    }
}

# ==================== 3. Start Milvus Docker ====================
Write-Step "3. Starting Milvus Docker services..."

$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"

& $composeCmd down --remove-orphans 2>$null
& $composeCmd up -d 2>$null

Write-Info "Waiting for Milvus (may take 60-90s)..."
$waited = 0
$maxWait = 180
do {
    Start-Sleep -Seconds 3
    $waited += 3
    $status = docker inspect --format='{{.State.Health.Status}}' milvus-standalone 2>$null
    Write-Host -NoNewline "."
} while ($status -ne "healthy" -and $waited -lt $maxWait)

if ($status -eq "healthy") {
    Write-Host ""
    Write-Info "Milvus is ready"
} else {
    Write-Host ""
    Write-Warn "Milvus may not be fully ready, continuing..."
}

$ErrorActionPreference = $prevEAP

# ==================== 4. Init backend ====================
Write-Step "4. Setting up backend..."

$pyVersion = python -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')"
Write-Info "Python version: $pyVersion"

$REQUIRED_PY = "3.11"
if ($pyVersion -ne $REQUIRED_PY) {
    Write-Err "This project requires Python $REQUIRED_PY (detected: $pyVersion)."
    Write-Err ""
    Write-Err "Python $REQUIRED_PY is the industry standard for AI/ML projects."
    Write-Err "Python 3.13 has breaking changes that make many packages incompatible."
    Write-Err ""
    Write-Err "Please install Python $REQUIRED_PY and re-run this script:"
    Write-Err "  1. Download: https://www.python.org/downloads/release/python-3119/"
    Write-Err "  2. Check 'Add Python to PATH' during installation"
    Write-Err "  3. Verify: python --version  (should show 3.11.x)"
    Write-Err "  4. Delete backend\\venv (if exists)"
    Write-Err "  5. Run: .\\start.ps1"
    exit 1
}

if (-not (Test-Path "backend\.env")) {
    Copy-Item "backend\.env.example" "backend\.env"
    Write-Warn ".env created from .env.example. Please set DASHSCOPE_API_KEY."
}

Push-Location backend

if (Test-Path "venv") {
    $pythonOk = Test-Path "venv\Scripts\python.exe"
    $pipOk = Test-Path "venv\Scripts\pip.exe"
    if (-not ($pythonOk -and $pipOk)) {
        Write-Warn "Virtual environment is corrupted (missing executables), recreating..."
        Remove-Item -Recurse -Force venv
    }
}

if (-not (Test-Path "venv")) {
    Write-Info "Creating Python venv..."
    python -m venv venv
    if (-not (Test-Path "venv\Scripts\python.exe")) {
        Write-Err "Failed to create virtual environment. Please check your Python installation."
        Pop-Location
        exit 1
    }
    Write-Info "Virtual environment created successfully"
}

$markerFile = "venv\.deps_installed"
if (Test-Path $markerFile) {
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & venv\Scripts\python.exe -c "import pkg_resources" *>$null
    $depsOk = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prevEAP
    if ($depsOk) {
        Write-Info "Python dependencies already installed, skipping..."
    } else {
        Write-Warn "pkg_resources check failed, reinstalling..."
        Remove-Item $markerFile -Force
    }
}

if (-not (Test-Path $markerFile)) {
    Write-Info "Installing Python dependencies..."
    & ".\scripts\install_deps.ps1"
    if ($LASTEXITCODE -eq 0) {
        New-Item -ItemType File -Path $markerFile -Force | Out-Null
        Write-Info "Dependencies installed successfully."
    } else {
        Write-Err "Dependency installation failed. See error above."
        Pop-Location
        exit 1
    }
}

Pop-Location

# ==================== 5. Start backend + celery ====================
Write-Step "5. Launching backend (3 new windows)..."

$backendDir = "$PROJECT_DIR\backend"

Write-Info "Starting FastAPI (port 8000) with auto-reload..."
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$backendDir'; .\venv\Scripts\activate; uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-include '*.py' --log-level info"
)

Write-Info "Starting Celery Worker..."
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$backendDir'; .\venv\Scripts\activate; celery -A app.core.celery:celery_app worker --loglevel=info -P solo"
)

# ==================== 6. Start frontend ====================
Write-Step "6. Setting up frontend..."

$frontendDir = "$PROJECT_DIR\frontend"
if (Test-Path "$frontendDir\node_modules") {
    Write-Info "Frontend deps already installed"
} else {
    Write-Info "Installing frontend dependencies..."
    Push-Location $frontendDir
    npm install
    Pop-Location
}

Write-Info "Starting Vite dev server (port 5173)..."
Start-Process powershell -ArgumentList @(
    "-NoExit",
    "-Command",
    "cd '$frontendDir'; npm run dev"
)

# ==================== 7. Done ====================
Write-Step "7. All services launched!"

$B = [ConsoleColor]::Cyan
Write-Host ""
Write-Host "+===========================================+" -ForegroundColor $B
Write-Host "|  CampusAsk-RAG Test Environment Ready       |" -ForegroundColor $B
Write-Host "+===========================================+" -ForegroundColor $B
Write-Host "|                                           |" -ForegroundColor $B
Write-Host "|  Frontend:   http://localhost:5173        |" -ForegroundColor $B
Write-Host "|  API Docs:   http://localhost:8000/docs   |" -ForegroundColor $B
Write-Host "|  RabbitMQ:   http://localhost:15672       |" -ForegroundColor $B
Write-Host "|  MinIO:      http://localhost:9001        |" -ForegroundColor $B
Write-Host "|                                           |" -ForegroundColor $B
Write-Host "|  Admin:      admin（密码请查看环境变量）   |" -ForegroundColor $B
Write-Host "|                                           |" -ForegroundColor $B
Write-Host "+===========================================+" -ForegroundColor $B
Write-Host ""
Write-Info "3 new windows opened: FastAPI, Celery, Vite"
Write-Info "Close each window to stop the corresponding service."
Write-Host ""
Write-Host "Press any key to close this window..." -ForegroundColor Yellow
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")
