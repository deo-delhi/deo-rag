# DEO RAG launcher (Windows PowerShell)
# Starts: PostgreSQL+pgvector (docker compose) -> FastAPI backend (uvicorn) -> React frontend (vite)
# Run from inside the deo-rag/ folder:   .\script.ps1
# Stop with:                              .\stop.ps1   (or Ctrl+C in this window)

$ErrorActionPreference = "Stop"

$RootDir       = Split-Path -Parent $MyInvocation.MyCommand.Path
$BackendDir    = Join-Path $RootDir "backend"
$FrontendDir   = Join-Path $RootDir "frontend"
$ComposeFile   = Join-Path $RootDir "docker-compose.yml"
$LogDir        = Join-Path $RootDir ".run-logs"

$BackendHost   = if ($env:BACKEND_HOST)  { $env:BACKEND_HOST }  else { "0.0.0.0" }
$BackendPort   = if ($env:BACKEND_PORT)  { $env:BACKEND_PORT }  else { "5200" }
$FrontendHost  = if ($env:FRONTEND_HOST) { $env:FRONTEND_HOST } else { "0.0.0.0" }
$FrontendPort  = if ($env:FRONTEND_PORT) { $env:FRONTEND_PORT } else { "5201" }
$PostgresPort  = if ($env:POSTGRES_PORT) { $env:POSTGRES_PORT } else { "5202" }
$CheckHost     = if ($env:CHECK_HOST)    { $env:CHECK_HOST }    else { "127.0.0.1" }

# Resolve the venv Python. Prefer workspace-root .venv (matches the bash script.sh layout),
# then deo-rag/.venv, then fall back to system 'py' so the launcher still works.
$VenvCandidates = @(
    (Join-Path $RootDir "..\.venv\Scripts\python.exe"),
    (Join-Path $RootDir ".venv\Scripts\python.exe")
)
if ($env:VENV_PY) { $VenvCandidates = @($env:VENV_PY) + $VenvCandidates }
$VenvPy = $VenvCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

function Require-Command([string]$Name) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        Write-Error "Missing required command on PATH: $Name"
        exit 1
    }
}

function Test-PortFree([int]$Port, [string]$Label) {
    $hit = Get-NetTCPConnection -State Listen -LocalPort $Port -ErrorAction SilentlyContinue
    if ($hit) {
        Write-Error "$Label port $Port is already in use. Stop the existing process first."
        exit 1
    }
}

function Wait-ForHttp([string]$Url, [string]$Label, [int]$Attempts = 60) {
    for ($i = 0; $i -lt $Attempts; $i++) {
        try {
            $resp = Invoke-WebRequest -Uri $Url -UseBasicParsing -TimeoutSec 3 -ErrorAction Stop
            if ($resp.StatusCode -ge 200 -and $resp.StatusCode -lt 500) { return $true }
        } catch { Start-Sleep -Seconds 2 }
    }
    Write-Error "Timed out waiting for $Label at $Url"
    return $false
}

Require-Command "docker"
Require-Command "npm"

if (-not (Test-Path (Join-Path $RootDir ".env"))) {
    Write-Error "Missing .env at $RootDir\.env  -- copy .env.example to .env first."
    exit 1
}

# Pull the Ollama model automatically
if (Get-Command "ollama" -ErrorAction SilentlyContinue) {
    Write-Host "Pulling the latest llama3.2 model in Ollama (this may take a while if not cached)..."
    ollama pull llama3.2:latest
} else {
    Write-Host "Ollama is not installed or not in PATH, skipping model pull."
}
if (-not $VenvPy) {
    Write-Error @"
No Python venv found. Create one at the workspace root with:
    py -m venv ..\.venv
    ..\.venv\Scripts\python -m pip install --upgrade pip
    ..\.venv\Scripts\python -m pip install -r backend\requirements.txt
Or set VENV_PY to point at your interpreter.
"@
    exit 1
}

if (-not (Test-Path (Join-Path $FrontendDir "node_modules"))) {
    Write-Host "Installing frontend dependencies..."
    Push-Location $FrontendDir
    npm install
    Pop-Location
}

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

Test-PortFree -Port ([int]$BackendPort)  -Label "Backend"
Test-PortFree -Port ([int]$FrontendPort) -Label "Frontend"
Test-PortFree -Port ([int]$PostgresPort) -Label "PostgreSQL"

Write-Host "Starting PostgreSQL + pgvector via docker compose..."
docker compose -f $ComposeFile up -d postgres | Out-Null

Write-Host "Waiting for PostgreSQL to be ready..."
$ready = $false
for ($i = 0; $i -lt 60; $i++) {
    docker compose -f $ComposeFile exec -T postgres pg_isready -U admin -d deorag *> $null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 2
}
if (-not $ready) { Write-Error "PostgreSQL did not become ready in time."; exit 1 }

Write-Host "Starting FastAPI backend on $BackendHost`:$BackendPort..."
$backendLog = Join-Path $LogDir "backend.log"
$backend = Start-Process -FilePath $VenvPy `
    -ArgumentList @("-m", "uvicorn", "backend.app:app", "--host", $BackendHost, "--port", $BackendPort, "--app-dir", $RootDir) `
    -WorkingDirectory $RootDir `
    -RedirectStandardOutput $backendLog -RedirectStandardError "$backendLog.err" `
    -PassThru -WindowStyle Hidden

Write-Host "Starting Vite frontend on $FrontendHost`:$FrontendPort..."
$frontendLog = Join-Path $LogDir "frontend.log"
$frontend = Start-Process -FilePath "cmd.exe" `
    -ArgumentList @("/c", "npm", "run", "dev", "--", "--host", $FrontendHost, "--port", $FrontendPort) `
    -WorkingDirectory $FrontendDir `
    -RedirectStandardOutput $frontendLog -RedirectStandardError "$frontendLog.err" `
    -PassThru -WindowStyle Hidden

@{ backend = $backend.Id; frontend = $frontend.Id } |
    ConvertTo-Json | Out-File -Encoding ascii (Join-Path $LogDir "pids.json")

if (-not (Wait-ForHttp -Url "http://$CheckHost`:$BackendPort/health" -Label "backend health endpoint")) { exit 1 }
if (-not (Wait-ForHttp -Url "http://$CheckHost`:$FrontendPort"        -Label "frontend dev server"   )) { exit 1 }

Write-Host ""
Write-Host "Stack is running:"
Write-Host "  Backend:  http://$CheckHost`:$BackendPort"
Write-Host "  Frontend: http://$CheckHost`:$FrontendPort"
Write-Host "  Logs:     $backendLog and $frontendLog"
Write-Host ""
Write-Host "Run .\stop.ps1 to shut everything down."
