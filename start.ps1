# AI Business OS 3.0 - local launcher (double-click start.bat).
#
# Prepares everything that is missing, then starts the backend (uvicorn, from
# backend/.venv) and the frontend (next dev) in their own PowerShell windows
# and opens the browser once the frontend answers:
#
#   1. .env       created from .env.example if absent; an AUTH_SECRET_KEY is
#                 generated and written into it if empty (V3 sign-in needs it).
#   2. backend    virtual environment created if absent; dependencies
#                 (re)installed when requirements.txt changed; database
#                 migrated to the latest version (alembic upgrade head).
#   3. frontend   npm install when package-lock.json changed.
#
# Contains no secrets: the generated key only ever lives in your local .env.

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"
$backendPort = 8000
$frontendPort = 3000

function Test-PortOpen {
    param([int]$Port)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        $connected = $async.AsyncWaitHandle.WaitOne(300)
        if ($connected -and $client.Connected) {
            $client.Close()
            return $true
        }
        $client.Close()
        return $false
    } catch {
        return $false
    }
}

Write-Host ""
Write-Host "=== AI Business OS - launcher ===" -ForegroundColor Cyan
Write-Host ""

# --- Setup: .env and the sign-in secret ---------------------------------
$envFile = Join-Path $repoRoot ".env"
if (-not (Test-Path $envFile)) {
    Copy-Item (Join-Path $repoRoot ".env.example") $envFile
    Write-Host "[Setup]    .env created from .env.example" -ForegroundColor Cyan
}
$envLines = @(Get-Content $envFile)
$keyLine = $envLines | Where-Object { $_ -match '^\s*AUTH_SECRET_KEY\s*=' } | Select-Object -First 1
if (-not $keyLine -or $keyLine -match '^\s*AUTH_SECRET_KEY\s*=\s*$') {
    $bytes = New-Object byte[] 48
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    $secret = [Convert]::ToBase64String($bytes).Replace("+", "-").Replace("/", "_").TrimEnd("=")
    if ($keyLine) {
        $envLines = $envLines | ForEach-Object { if ($_ -match '^\s*AUTH_SECRET_KEY\s*=') { "AUTH_SECRET_KEY=$secret" } else { $_ } }
    } else {
        $envLines += "AUTH_SECRET_KEY=$secret"
    }
    [System.IO.File]::WriteAllLines($envFile, [string[]]$envLines, (New-Object System.Text.UTF8Encoding($false)))
    Write-Host "[Setup]    AUTH_SECRET_KEY generated in .env" -ForegroundColor Cyan
}

# --- Setup: backend environment and database -----------------------------
$backendPython = Join-Path $backendDir ".venv\Scripts\python.exe"
$backendRunning = Test-PortOpen -Port $backendPort

if (-not $backendRunning) {
    if (-not (Test-Path $backendPython)) {
        Write-Host "[Setup]    Creating the Python virtual environment (backend\.venv) ..." -ForegroundColor Cyan
        Push-Location $backendDir
        try { python -m venv .venv } catch { Write-Host "[Setup]    Python not found: install Python 3.10+ and tick 'Add to PATH'." -ForegroundColor Red }
        Pop-Location
    }
    if (Test-Path $backendPython) {
        $requirements = Join-Path $backendDir "requirements.txt"
        $stamp = Join-Path $backendDir ".venv\requirements.sha256"
        $hash = (Get-FileHash $requirements -Algorithm SHA256).Hash
        if (-not (Test-Path $stamp) -or (Get-Content $stamp -Raw).Trim() -ne $hash) {
            Write-Host "[Setup]    Installing backend dependencies ..." -ForegroundColor Cyan
            & $backendPython -m pip install -q -r $requirements
            if ($LASTEXITCODE -eq 0) { Set-Content -Path $stamp -Value $hash }
        }
        Write-Host "[Setup]    Updating the database (alembic upgrade head) ..." -ForegroundColor Cyan
        Push-Location $backendDir
        & $backendPython -m alembic upgrade head
        $migrated = $LASTEXITCODE
        Pop-Location
        if ($migrated -ne 0) {
            Write-Host "[Setup]    The database update failed: read the error above (DATABASE_URL in .env?)." -ForegroundColor Red
        }
    }
}

# --- Setup: frontend dependencies ----------------------------------------
$frontendLock = Join-Path $frontendDir "package-lock.json"
$frontendStamp = Join-Path $frontendDir "node_modules\.package-lock.sha256"
$lockHash = (Get-FileHash $frontendLock -Algorithm SHA256).Hash
if (-not (Test-PortOpen -Port $frontendPort) -and (-not (Test-Path $frontendStamp) -or (Get-Content $frontendStamp -Raw).Trim() -ne $lockHash)) {
    Write-Host "[Setup]    Installing frontend dependencies (npm install) ..." -ForegroundColor Cyan
    Push-Location $frontendDir
    try { npm install --no-audit --no-fund; $npmOk = $LASTEXITCODE -eq 0 } catch { $npmOk = $false; Write-Host "[Setup]    npm not found: install Node.js 20.9+." -ForegroundColor Red }
    Pop-Location
    if ($npmOk) { Set-Content -Path $frontendStamp -Value $lockHash }
}

# --- Backend -----------------------------------------------------------

if ($backendRunning) {
    Write-Host "[Backend]  Port $backendPort is already in use -- assuming the backend is already running, skipping." -ForegroundColor Yellow
    Write-Host "[Backend]  -> http://localhost:$backendPort" -ForegroundColor Green
} elseif (-not (Test-Path $backendPython)) {
    Write-Host "[Backend]  No virtual environment found at backend\.venv -- not starting." -ForegroundColor Red
    Write-Host "[Backend]  Is Python 3.10+ installed and on PATH? (python --version)" -ForegroundColor Red
} else {
    Write-Host "[Backend]  Starting FastAPI (uvicorn) ..." -ForegroundColor Cyan
    $backendCommand = "cd `"$backendDir`"; Write-Host 'AI Business OS - Backend' -ForegroundColor Cyan; Write-Host 'http://localhost:$backendPort' -ForegroundColor Green; & `"$backendPython`" -m uvicorn app.main:app --reload"
    Start-Process powershell -ArgumentList @("-NoExit", "-Command", $backendCommand) | Out-Null
    Write-Host "[Backend]  -> http://localhost:$backendPort (own window)" -ForegroundColor Green
}

# --- Frontend ------------------------------------------------------------
$frontendModules = Join-Path $frontendDir "node_modules"

if (Test-PortOpen -Port $frontendPort) {
    Write-Host "[Frontend] Port $frontendPort is already in use -- assuming the frontend is already running (or another app is using it), skipping." -ForegroundColor Yellow
} elseif (-not (Test-Path $frontendModules)) {
    Write-Host "[Frontend] No node_modules found in frontend\ -- not starting." -ForegroundColor Red
    Write-Host "[Frontend] Is Node.js installed? (node --version), then run start.bat again." -ForegroundColor Red
} else {
    Write-Host "[Frontend] Starting Next.js (npm run dev) ..." -ForegroundColor Cyan
    $frontendCommand = "cd `"$frontendDir`"; Write-Host 'AI Business OS - Frontend' -ForegroundColor Cyan; Write-Host 'http://localhost:$frontendPort' -ForegroundColor Green; npm run dev"
    Start-Process powershell -ArgumentList @("-NoExit", "-Command", $frontendCommand) | Out-Null

    Write-Host "[Frontend] Waiting for http://localhost:$frontendPort to respond before opening the browser ..." -ForegroundColor Cyan
    $ready = $false
    for ($i = 0; $i -lt 60; $i++) {
        if (Test-PortOpen -Port $frontendPort) { $ready = $true; break }
        Start-Sleep -Seconds 1
    }
    if ($ready) {
        Write-Host "[Frontend] -> http://localhost:$frontendPort" -ForegroundColor Green
        Write-Host "First time on 3.0? Click 'Creer un compte' to create your company's space." -ForegroundColor Green
        Start-Process "http://localhost:$frontendPort"
    } else {
        Write-Host "[Frontend] Still not responding after 60s -- open http://localhost:$frontendPort manually once it's ready." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Backend and frontend each run in their own window; closing this window does not stop them." -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to close this launcher window" | Out-Null
