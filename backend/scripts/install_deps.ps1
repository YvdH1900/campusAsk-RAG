# ================================================
# Install Dependencies Script (Windows)
# ================================================
# This script ensures the venv is healthy and installs
# all project dependencies.
# Auto-detects fastest Chinese PyPI mirror.
# ================================================

$ErrorActionPreference = "Stop"
$OutputEncoding = [Console]::OutputEncoding = [System.Text.Encoding]::UTF8

$SCRIPT_DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$BACKEND_DIR = Split-Path -Parent $SCRIPT_DIR
Set-Location $BACKEND_DIR

function Write-Step { Write-Host "`n>>> $args" -ForegroundColor Cyan }
function Write-Info  { Write-Host "[INFO]  $args" -ForegroundColor Green }
function Write-Warn  { Write-Host "[WARN]  $args" -ForegroundColor Yellow }
function Write-Err   { Write-Host "[ERROR] $args" -ForegroundColor Red }

$mirrors = @(
    @{ Name = "Tsinghua (TUNA)"; Url = "https://pypi.tuna.tsinghua.edu.cn/simple"; Host = "pypi.tuna.tsinghua.edu.cn" },
    @{ Name = "Aliyun";           Url = "https://mirrors.aliyun.com/pypi/simple";      Host = "mirrors.aliyun.com" },
    @{ Name = "USTC";             Url = "https://pypi.mirrors.ustc.edu.cn/simple";     Host = "pypi.mirrors.ustc.edu.cn" },
    @{ Name = "Douban";           Url = "https://pypi.doubanio.com/simple";            Host = "pypi.doubanio.com" },
    @{ Name = "Huawei Cloud";     Url = "https://repo.huaweicloud.com/repository/pypi/simple"; Host = "repo.huaweicloud.com" }
)

function Set-PipMirrorConfig($venvDir, $mirrorUrl, $mirrorHost) {
    $iniPath = "$venvDir\pip.ini"
    @"
[global]
index-url = $mirrorUrl
trusted-host = $mirrorHost
"@ | Set-Content -Path $iniPath -Encoding ASCII
    Write-Info "pip mirror config: $mirrorUrl"
}

function Remove-PipMirrorConfig($venvDir) {
    $iniPath = "$venvDir\pip.ini"
    if (Test-Path $iniPath) {
        Remove-Item $iniPath -Force
        Write-Info "pip mirror config removed"
    }
}

function Invoke-PipWithRetry {
    param($Python, $PipArgs, $MirrorFound, $VenvDir)

    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $Python -m pip @PipArgs
    $exitCode = $LASTEXITCODE
    $ErrorActionPreference = $prevEAP

    if ($exitCode -eq 0) { return $true }

    if ($MirrorFound) {
        Write-Warn "Mirror download failed, retrying with official PyPI..."
        Remove-PipMirrorConfig $VenvDir
        $ErrorActionPreference = "Continue"
        & $Python -m pip @PipArgs
        $exitCode = $LASTEXITCODE
        $ErrorActionPreference = $prevEAP
    }

    return ($exitCode -eq 0)
}

Write-Step "0. Detecting fastest PyPI mirror..."

$mirrorFound = $false
$PIP_INDEX_URL = ""
$PIP_TRUSTED = ""

foreach ($m in $mirrors) {
    try {
        $response = Invoke-WebRequest -Uri $m.Url -TimeoutSec 3 -UseBasicParsing 2>$null
        if ($response.StatusCode -eq 200) {
            $PIP_INDEX_URL = $m.Url
            $PIP_TRUSTED = $m.Host
            Write-Info "Using $($m.Name) mirror: $($m.Url)"
            $mirrorFound = $true
            break
        }
    } catch {}
}

if (-not $mirrorFound) {
    Write-Warn "No Chinese mirror reachable, using official PyPI"
}

Write-Step "1. Checking virtual environment..."

if (-not (Test-Path "venv")) {
    Write-Err "Virtual environment not found at: $BACKEND_DIR\venv"
    Write-Err ""
    Write-Err "Please run start.ps1 from the project root first to create the venv."
    exit 1
}

$PYTHON = "venv\Scripts\python.exe"
$VENV_DIR = "$BACKEND_DIR\venv"

if (-not (Test-Path $PYTHON)) {
    Write-Err "Python executable missing in venv! The virtual environment is corrupted."
    Write-Err ""
    Write-Err "Please run the following commands to recreate the venv:"
    Write-Err "  1. cd backend"
    Write-Err "  2. Remove-Item -Recurse -Force venv"
    Write-Err "  3. python -m venv venv"
    Write-Err "  4. Re-run this script"
    exit 1
}

Write-Step "2. Checking pip integrity..."

$pipOk = $false
if (Test-Path "venv\Scripts\pip.exe") {
    try {
        & $PYTHON -m pip --version 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Info "pip is functional"
            $pipOk = $true
        }
    } catch {}
}

if (-not $pipOk) {
    Write-Warn "pip is broken or missing, attempting repair via ensurepip..."
    try {
        & $PYTHON -m ensurepip --upgrade --default-pip 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) {
            Write-Info "pip repaired successfully via ensurepip"
        } else {
            throw "ensurepip failed"
        }
    } catch {
        Write-Err "Unable to repair pip. The virtual environment is corrupted."
        Write-Err ""
        Write-Err "Please run the following commands to recreate the venv:"
        Write-Err "  1. cd backend"
        Write-Err "  2. Remove-Item -Recurse -Force venv"
        Write-Err "  3. python -m venv venv"
        Write-Err "  4. Re-run this script"
        exit 1
    }
}

Write-Step "3. Configuring pip mirror..."

if ($mirrorFound) {
    Set-PipMirrorConfig $VENV_DIR $PIP_INDEX_URL $PIP_TRUSTED
}

Write-Step "4. Pre-installing setuptools (ensures pkg_resources for deps)..."
$setupArgs = @(
    "install", "--upgrade", "setuptools>=69.5.1,<70.0",
    "--ignore-installed", "--no-cache-dir",
    "--disable-pip-version-check", "--timeout", "300", "--retries", "5"
)
if (-not (Invoke-PipWithRetry -Python $PYTHON -PipArgs $setupArgs -MirrorFound $mirrorFound -VenvDir $VENV_DIR)) {
    Write-Err "setuptools pre-installation failed!"
    exit 1
}
Write-Info "setuptools pre-installed"

Write-Step "5. Installing project dependencies..."
$env:PYTHONUTF8 = "1"
$installArgs = @(
    "install", "-r", "requirements.txt",
    "--no-cache-dir", "--disable-pip-version-check",
    "--timeout", "300", "--retries", "5"
)
if (-not (Invoke-PipWithRetry -Python $PYTHON -PipArgs $installArgs -MirrorFound $mirrorFound -VenvDir $VENV_DIR)) {
    Write-Err "Dependency installation failed!"
    exit 1
}
Write-Info "Dependencies installed"

Write-Step "6. Final pkg_resources check..."
$prevEAP = $ErrorActionPreference
$ErrorActionPreference = "Continue"
& $PYTHON -c "import pkg_resources" *>$null
$pkgOk = ($LASTEXITCODE -eq 0)
$ErrorActionPreference = $prevEAP

if (-not $pkgOk) {
    Write-Warn "pkg_resources missing after full install (likely downgraded by transitive dep)"
    Write-Info "Force-reinstalling setuptools to restore pkg_resources..."
    $fixArgs = @(
        "install", "--force-reinstall", "--no-deps",
        "setuptools>=69.5.1,<70.0",
        "--no-cache-dir", "--disable-pip-version-check",
        "--timeout", "300", "--retries", "5"
    )
    if (-not (Invoke-PipWithRetry -Python $PYTHON -PipArgs $fixArgs -MirrorFound $mirrorFound -VenvDir $VENV_DIR)) {
        Write-Err "Failed to restore pkg_resources!"
        exit 1
    }
    $prevEAP = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $PYTHON -c "import pkg_resources" *>$null
    $pkgOk = ($LASTEXITCODE -eq 0)
    $ErrorActionPreference = $prevEAP
    if (-not $pkgOk) {
        Write-Err "pkg_resources still missing after force reinstall!"
        exit 1
    }
    Write-Info "pkg_resources restored successfully"
} else {
    Write-Info "pkg_resources verified"
}

Write-Info "All dependencies installed and verified!"
