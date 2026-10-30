# AI Business OS - temporary public demo via Cloudflare Tunnel (trycloudflare.com).
#
# Exposes the local backend (FastAPI, SQLite) and frontend (Next.js) with two
# free, anonymous, ephemeral tunnels -- no Cloudflare account, no DNS setup,
# no secrets. The tunnels (and the demo) disappear the moment their windows
# are closed. Everything still runs on this machine; only the URLs are public.
#
# Solves the circular dependency between the two apps' own env vars
# (NEXT_PUBLIC_API_URL is inlined into the frontend at `next dev` startup;
# ALLOWED_ORIGINS is read once by the backend at startup) by opening BOTH
# tunnels first -- a quick tunnel gets a URL immediately, before the local
# port it points to is even listening -- then starting backend and frontend
# each already knowing the other's public URL.
#
# Each spawned window runs from its own small generated .ps1 file rather
# than an inline -Command string: a piped/native-command -Command string
# passed through Start-Process's -ArgumentList was found unreliable (it
# could silently not execute) during testing, while -File is not.

param(
    [int]$BackendPort = 8000,
    [int]$FrontendPort = 3000,
    [int]$TunnelTimeoutSeconds = 30
)

$ErrorActionPreference = "Stop"
$repoRoot = $PSScriptRoot
$backendDir = Join-Path $repoRoot "backend"
$frontendDir = Join-Path $repoRoot "frontend"
$logDir = Join-Path $env:TEMP "ai-business-os-tunnels"
New-Item -ItemType Directory -Path $logDir -Force | Out-Null

function Test-PortOpen {
    param([int]$Port)
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect("127.0.0.1", $Port, $null, $null)
        $connected = $async.AsyncWaitHandle.WaitOne(300)
        if ($connected -and $client.Connected) { $client.Close(); return $true }
        $client.Close()
        return $false
    } catch {
        return $false
    }
}

function Find-Cloudflared {
    $candidates = @("cloudflared", "C:\Program Files (x86)\cloudflared\cloudflared.exe", "C:\Program Files\cloudflared\cloudflared.exe")
    foreach ($c in $candidates) {
        $resolved = Get-Command $c -ErrorAction SilentlyContinue
        if ($resolved) { return $resolved.Source }
        if (Test-Path $c) { return $c }
    }
    return $null
}

# Writes $Body to a small .ps1 file under $logDir and launches it in its own
# visible, persistent window (-NoExit). Using a real file rather than an
# inline -Command string is the reliability fix described above.
function Start-InWindow {
    param([string]$Name, [string]$Body)
    $scriptPath = Join-Path $logDir "$Name.ps1"
    Set-Content -Path $scriptPath -Value $Body -Encoding UTF8
    Start-Process powershell -ArgumentList @("-NoExit", "-ExecutionPolicy", "Bypass", "-File", $scriptPath) | Out-Null
}

function Wait-ForTunnelUrl {
    param([string]$LogFile, [int]$TimeoutSeconds)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        if (Test-Path $LogFile) {
            $content = Get-Content $LogFile -Raw -ErrorAction SilentlyContinue
            if ($content -match "https://[a-zA-Z0-9\-]+\.trycloudflare\.com") {
                return $Matches[0]
            }
        }
        Start-Sleep -Milliseconds 500
    }
    return $null
}

Write-Host ""
Write-Host "=== AI Business OS - demo publique temporaire (Cloudflare Tunnel) ===" -ForegroundColor Cyan
Write-Host "Gratuit, anonyme, ephemere -- disparait a la fermeture des fenetres ouvertes." -ForegroundColor DarkGray
Write-Host ""

$cloudflared = Find-Cloudflared
if (-not $cloudflared) {
    Write-Host "cloudflared est introuvable sur cette machine." -ForegroundColor Red
    Write-Host "Installe-le puis relance ce script : https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/" -ForegroundColor Red
    exit 1
}
Write-Host "cloudflared trouve : $cloudflared" -ForegroundColor DarkGray

$backendPython = Join-Path $backendDir ".venv\Scripts\python.exe"
if (-not (Test-Path $backendPython)) {
    Write-Host "Aucun environnement virtuel dans backend\.venv -- voir README.md (Getting Started) avant de lancer la demo." -ForegroundColor Red
    exit 1
}
$frontendModules = Join-Path $frontendDir "node_modules"
if (-not (Test-Path $frontendModules)) {
    Write-Host "Aucun node_modules dans frontend\ -- lance 'npm install' dans frontend\ avant la demo." -ForegroundColor Red
    exit 1
}
if (Test-PortOpen -Port $BackendPort) {
    Write-Host "[Backend]  Le port $BackendPort est deja utilise -- ferme l'instance existante avant de lancer la demo (elle n'aurait pas le bon ALLOWED_ORIGINS)." -ForegroundColor Red
    exit 1
}
if (Test-PortOpen -Port $FrontendPort) {
    Write-Host "[Frontend] Le port $FrontendPort est deja utilise -- ferme l'instance existante avant de lancer la demo (elle n'aurait pas le bon NEXT_PUBLIC_API_URL)." -ForegroundColor Red
    exit 1
}

$backendTunnelLog = Join-Path $logDir "backend-tunnel.log"
$frontendTunnelLog = Join-Path $logDir "frontend-tunnel.log"
if (Test-Path $backendTunnelLog) { Remove-Item $backendTunnelLog -Force }
if (Test-Path $frontendTunnelLog) { Remove-Item $frontendTunnelLog -Force }

# --- Tunnels first: a quick tunnel gets a URL right away, even before the
# local port it targets is listening -- this is what breaks the circular
# dependency between NEXT_PUBLIC_API_URL and ALLOWED_ORIGINS. -------------
Write-Host ""
Write-Host "[1/4] Ouverture du tunnel backend (localhost:$BackendPort) ..." -ForegroundColor Cyan
$backendTunnelScript = @"
Write-Host 'AI Business OS - Tunnel Backend -> localhost:$BackendPort' -ForegroundColor Cyan
& '$cloudflared' tunnel --url http://localhost:$BackendPort 2>&1 | Tee-Object -FilePath '$backendTunnelLog'
"@
Start-InWindow -Name "tunnel-backend" -Body $backendTunnelScript
$backendUrl = Wait-ForTunnelUrl -LogFile $backendTunnelLog -TimeoutSeconds $TunnelTimeoutSeconds
if (-not $backendUrl) {
    Write-Host "Pas d'URL de tunnel backend recue apres $TunnelTimeoutSeconds s. Voir $backendTunnelLog" -ForegroundColor Red
    exit 1
}
Write-Host "      -> $backendUrl" -ForegroundColor Green

Write-Host "[2/4] Ouverture du tunnel frontend (localhost:$FrontendPort) ..." -ForegroundColor Cyan
$frontendTunnelScript = @"
Write-Host 'AI Business OS - Tunnel Frontend -> localhost:$FrontendPort' -ForegroundColor Cyan
& '$cloudflared' tunnel --url http://localhost:$FrontendPort 2>&1 | Tee-Object -FilePath '$frontendTunnelLog'
"@
Start-InWindow -Name "tunnel-frontend" -Body $frontendTunnelScript
$frontendUrl = Wait-ForTunnelUrl -LogFile $frontendTunnelLog -TimeoutSeconds $TunnelTimeoutSeconds
if (-not $frontendUrl) {
    Write-Host "Pas d'URL de tunnel frontend recue apres $TunnelTimeoutSeconds s. Voir $frontendTunnelLog" -ForegroundColor Red
    exit 1
}
Write-Host "      -> $frontendUrl" -ForegroundColor Green

# --- Now start the two apps, each already knowing the other's public URL. -
Write-Host ""
Write-Host "[3/4] Demarrage du backend (ALLOWED_ORIGINS=$frontendUrl) ..." -ForegroundColor Cyan
$backendScript = @"
Set-Location '$backendDir'
`$env:ALLOWED_ORIGINS = '$frontendUrl'
Write-Host 'AI Business OS - Backend (demo)' -ForegroundColor Cyan
Write-Host 'local  : http://localhost:$BackendPort' -ForegroundColor Green
Write-Host 'public : $backendUrl' -ForegroundColor Green
& '$backendPython' -m uvicorn app.main:app --reload --port $BackendPort
"@
Start-InWindow -Name "backend" -Body $backendScript

Write-Host "[4/4] Demarrage du frontend (NEXT_PUBLIC_API_URL=$backendUrl) ..." -ForegroundColor Cyan
$devCommand = if ($FrontendPort -eq 3000) { "npm run dev" } else { "npm run dev -- -p $FrontendPort" }
$frontendScript = @"
Set-Location '$frontendDir'
`$env:NEXT_PUBLIC_API_URL = '$backendUrl'
Write-Host 'AI Business OS - Frontend (demo)' -ForegroundColor Cyan
Write-Host 'local  : http://localhost:$FrontendPort' -ForegroundColor Green
Write-Host 'public : $frontendUrl' -ForegroundColor Green
$devCommand
"@
Start-InWindow -Name "frontend" -Body $frontendScript

Write-Host ""
Write-Host "Attente que le backend et le frontend locaux repondent ..." -ForegroundColor Cyan
$backendReady = $false
for ($i = 0; $i -lt 60; $i++) { if (Test-PortOpen -Port $BackendPort) { $backendReady = $true; break }; Start-Sleep -Seconds 1 }
$frontendReady = $false
for ($i = 0; $i -lt 60; $i++) { if (Test-PortOpen -Port $FrontendPort) { $frontendReady = $true; break }; Start-Sleep -Seconds 1 }

Write-Host ""
Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " AI Business OS - demo publique" -ForegroundColor Cyan
Write-Host "=================================================="  -ForegroundColor Cyan
Write-Host " Frontend : $frontendUrl" -ForegroundColor Green
Write-Host " Backend  : $backendUrl" -ForegroundColor Green
Write-Host "==================================================" -ForegroundColor Cyan
if (-not ($backendReady -and $frontendReady)) {
    Write-Host "Le backend et/ou le frontend local ne repondaient pas encore apres 60s -- verifie leurs fenetres." -ForegroundColor Yellow
}
Write-Host ""
Write-Host "Ouvre l'URL Frontend depuis un telephone ou un autre PC (le reseau local n'a pas besoin d'etre le meme)." -ForegroundColor Cyan
Write-Host "Pour tout arreter : ferme les 4 fenetres ouvertes (2 tunnels + backend + frontend)." -ForegroundColor Yellow
Write-Host ""
Read-Host "Appuie sur Entree pour fermer cette fenetre de lancement (les 4 autres continuent de tourner)" | Out-Null
