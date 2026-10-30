# AI Business OS - local dev launcher.
#
# Starts the backend (uvicorn, from backend/.venv) and the frontend (next dev)
# in their own PowerShell windows so both stay running side by side, then
# opens the browser on the frontend URL once it is actually reachable.
#
# Contains no secrets, tokens or credentials -- it only runs the same local
# commands documented in README.md's "Getting Started" section.

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

# --- Backend -----------------------------------------------------------
$backendPython = Join-Path $backendDir ".venv\Scripts\python.exe"

if (Test-PortOpen -Port $backendPort) {
    Write-Host "[Backend]  Port $backendPort is already in use -- assuming the backend is already running, skipping." -ForegroundColor Yellow
    Write-Host "[Backend]  -> http://localhost:$backendPort" -ForegroundColor Green
} elseif (-not (Test-Path $backendPython)) {
    Write-Host "[Backend]  No virtual environment found at backend\.venv -- not starting." -ForegroundColor Red
    Write-Host "[Backend]  Run the backend setup steps in README.md (Getting Started) first." -ForegroundColor Red
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
    Write-Host "[Frontend] Run 'npm install' in frontend\ first (see README.md)." -ForegroundColor Red
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
        Start-Process "http://localhost:$frontendPort"
    } else {
        Write-Host "[Frontend] Still not responding after 60s -- open http://localhost:$frontendPort manually once it's ready." -ForegroundColor Yellow
    }
}

Write-Host ""
Write-Host "Backend and frontend each run in their own window; closing this window does not stop them." -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to close this launcher window" | Out-Null
