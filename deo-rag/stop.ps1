# DEO RAG shutdown (Windows PowerShell)
# Stops backend (uvicorn), frontend (vite) and the docker compose Postgres service.

$ErrorActionPreference = "Continue"

$RootDir     = Split-Path -Parent $MyInvocation.MyCommand.Path
$ComposeFile = Join-Path $RootDir "docker-compose.yml"
$LogDir      = Join-Path $RootDir ".run-logs"
$PidsFile    = Join-Path $LogDir "pids.json"

$BackendPort  = if ($env:BACKEND_PORT)  { $env:BACKEND_PORT }  else { "5200" }
$FrontendPort = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "5201" }
$PostgresPort = if ($env:POSTGRES_PORT) { $env:POSTGRES_PORT } else { "5202" }

function Stop-PortListeners([int]$Port, [string]$Label) {
    $conns = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        try {
            Write-Host "Stopping $Label on port $Port (pid $($c.OwningProcess))"
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
        } catch {}
    }
}

if (Test-Path $PidsFile) {
    try {
        $pids = Get-Content $PidsFile | ConvertFrom-Json
        foreach ($p in @($pids.backend, $pids.frontend)) {
            if ($p) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }
        }
    } catch {}
    Remove-Item $PidsFile -ErrorAction SilentlyContinue
}

Stop-PortListeners -Port ([int]$BackendPort)  -Label "backend"
Stop-PortListeners -Port ([int]$FrontendPort) -Label "frontend"

Write-Host "Stopping docker compose services..."
docker compose -f $ComposeFile down --remove-orphans | Out-Null

if (Get-NetTCPConnection -State Listen -LocalPort $PostgresPort -ErrorAction SilentlyContinue) {
    Write-Host "Port $PostgresPort is still in use by another process."
}

Write-Host "All DEO RAG services stopped."
