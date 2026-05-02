#Requires -RunAsAdministrator
<#
.SYNOPSIS
  One-click Windows bootstrap for https://github.com/deo-delhi/deo-rag.
  Installs the toolchain (Python, Node.js, Ollama, Docker Desktop, VC++ Runtime),
  pulls llama3.2 + mxbai-embed-large via Ollama, sets up the Python venv, builds
  the React frontend deps, copies the bundled court-case PDFs into the
  "court-cases-sample" Data Library, starts Postgres+pgvector, the FastAPI
  backend, the Vite frontend, ingests the PDFs, and opens the web UI.

  Run from an elevated PowerShell. No further input required.

.PARAMETER ForceReIngest
  Re-index "court-cases-sample" even if retrieval already finds chunks.

.PARAMETER SkipDockerSetup
  Do not winget-install / start Docker Desktop; assumes Docker is already up.

.PARAMETER SkipSampleIngest
  Copy PDFs and create the library but skip the (slow) ingestion step.

.PARAMETER SkipAvastUnlock
  Do not call "smc -stop" (Avast for Business agent unlock).

.EXAMPLE
  .\install-and-run.ps1
#>
param(
    [switch] $ForceReIngest,
    [switch] $SkipDockerSetup,
    [switch] $SkipSampleIngest,
    [switch] $SkipAvastUnlock
)

$ErrorActionPreference = "Stop"
$ProgressPreference    = "SilentlyContinue"   # speeds up Invoke-WebRequest

$SampleLibrary    = "court-cases-sample"
$BackendBase      = "http://127.0.0.1:5200"
$FrontendUrl      = "http://127.0.0.1:5201"
$BackendHealthUrl = "$BackendBase/health"

# TLS 1.2 for legacy Windows where some package mirrors still negotiate down.
try { [Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12 } catch {}

# ---------- helpers ----------
function Refresh-EnvironmentPath {
    $machine = [Environment]::GetEnvironmentVariable("Path", "Machine")
    $user    = [Environment]::GetEnvironmentVariable("Path", "User")
    $env:Path = "$machine;$user"
}

function Test-Administrator {
    $p = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
    return $p.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Disable-Avast {
    if ($SkipAvastUnlock) { return }
    Write-Host "`n[avast] Attempting 'smc -stop' to unlock Avast Business agent ..."
    try {
        $smc = Get-Command smc -ErrorAction SilentlyContinue
        if (-not $smc) {
            $candidates = @(
                "C:\Program Files\Avast Software\Avast Business Agent\smc.exe",
                "C:\Program Files\Avast Software\Avast\smc.exe",
                "C:\Program Files (x86)\AVAST Software\Avast Business Agent\smc.exe"
            )
            $smc = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
        } else {
            $smc = $smc.Source
        }
        if (-not $smc) {
            Write-Host "[avast] smc.exe not found - skipping (this is fine on non-Avast machines)."
            return
        }
        & $smc -stop *> $null
        Write-Host "[avast] smc -stop issued (exit $LASTEXITCODE)."
    } catch {
        Write-Warning "[avast] smc -stop failed: $($_.Exception.Message)"
    }
    # Also wipe the SSLKEYLOGFILE that some Avast builds inject and that breaks pip.
    [Environment]::SetEnvironmentVariable("SSLKEYLOGFILE", $null, "Process")
    [Environment]::SetEnvironmentVariable("SSLKEYLOGFILE", $null, "User")
    $env:SSLKEYLOGFILE = $null
}

function Enable-WindowsLongPaths {
    try {
        $key = "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem"
        New-ItemProperty -Path $key -Name "LongPathsEnabled" -Value 1 -PropertyType DWord -Force | Out-Null
        Write-Host "[fs] Long path support enabled (LongPathsEnabled=1)."
    } catch {
        Write-Warning "[fs] Could not enable long paths: $($_.Exception.Message)"
    }
}

function Find-AppRoots {
    param([string]$RepoRoot)
    $here = $RepoRoot

    # Flat clone: RepoRoot/deo-rag/docker-compose.yml
    $nested = Join-Path $here "deo-rag"
    if (Test-Path (Join-Path $nested "docker-compose.yml")) {
        return @{ WsRoot = $here; AppRoot = $nested; DeoFiles = (Join-Path $here "deo-files") }
    }
    # Nested clone: RepoRoot/deo-rag/deo-rag/docker-compose.yml
    $innerNested = Join-Path $nested "deo-rag"
    if (Test-Path (Join-Path $innerNested "docker-compose.yml")) {
        $deoFiles = Join-Path $here "deo-files"
        if (-not (Test-Path $deoFiles)) { $deoFiles = Join-Path $nested "deo-files" }
        return @{ WsRoot = $here; AppRoot = $innerNested; DeoFiles = $deoFiles }
    }
    # Script colocated with the app folder (no parent layer)
    if (Test-Path (Join-Path $here "docker-compose.yml")) {
        $parent = Split-Path $here -Parent
        return @{ WsRoot = $parent; AppRoot = $here; DeoFiles = (Join-Path $parent "deo-files") }
    }
    throw "Cannot locate docker-compose.yml. Place this script next to (or inside) the deo-rag app folder."
}

function Install-WingetPackage {
    param([string]$Id, [string]$Label)
    Write-Host "  [winget] Ensuring $Label ($Id) ..."
    & winget install -e --id $Id --source winget --accept-package-agreements --accept-source-agreements --silent
    if ($LASTEXITCODE -ne 0) {
        Write-Warning "  [winget] $Id returned exit $LASTEXITCODE (likely already installed)."
    }
    Refresh-EnvironmentPath
}

function Wait-Tcp {
    param([int]$Port, [int]$TimeoutSeconds = 60)
    $deadline = (Get-Date).AddSeconds($TimeoutSeconds)
    while ((Get-Date) -lt $deadline) {
        $tcp = New-Object System.Net.Sockets.TcpClient
        try {
            $iar = $tcp.BeginConnect("127.0.0.1", $Port, $null, $null)
            if ($iar.AsyncWaitHandle.WaitOne(1500) -and $tcp.Connected) { $tcp.EndConnect($iar); $tcp.Close(); return $true }
        } catch {} finally { try { $tcp.Close() } catch {} }
        Start-Sleep -Seconds 2
    }
    return $false
}

function Wait-OllamaServer {
    $deadline = (Get-Date).AddMinutes(10)
    while ((Get-Date) -lt $deadline) {
        try { Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 3 | Out-Null; return $true } catch {}
        Start-Sleep -Seconds 2
    }
    return $false
}

function Start-OllamaIfNeeded {
    try {
        Invoke-RestMethod -Uri "http://127.0.0.1:11434/api/tags" -TimeoutSec 2 | Out-Null
        Write-Host "[ollama] Already responding on 11434. Restarting to ensure NVIDIA GPU usage..."
        Stop-Process -Name "ollama" -Force -ErrorAction SilentlyContinue
        Start-Sleep -Seconds 2
    } catch {}
    Write-Host "[ollama] Starting background service with CUDA_VISIBLE_DEVICES=0 ..."
    $env:CUDA_VISIBLE_DEVICES = "0"
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue | Out-Null
    if (-not (Wait-OllamaServer)) { throw "Ollama HTTP API did not start (localhost:11434)." }
}

function Start-DockerDesktopIfNeeded {
    docker info 2>$null | Out-Null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[docker] Engine already up."
        return
    }
    $dd = @(
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
        "$env:ProgramFiles(x86)\Docker\Docker\Docker Desktop.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($dd) {
        Write-Host "[docker] Launching Docker Desktop ..."
        Start-Process -FilePath $dd -ErrorAction SilentlyContinue | Out-Null
    } else {
        Write-Warning "[docker] Docker Desktop.exe not found in default install location."
    }
}

function Wait-DockerDaemon {
    $deadline = (Get-Date).AddMinutes(10)
    while ((Get-Date) -lt $deadline) {
        docker info 2>$null | Out-Null
        if ($LASTEXITCODE -eq 0) {
            docker compose version 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { return $true }
        }
        Start-Sleep -Seconds 5
    }
    return $false
}

function Invoke-Pip {
    param([string[]]$PipArgs, [int]$MaxRetries = 3)
    for ($attempt = 1; $attempt -le $MaxRetries; $attempt++) {
        & $script:VenvPython -m pip @PipArgs --disable-pip-version-check --no-input --retries 5 --timeout 60
        if ($LASTEXITCODE -eq 0) { return }
        Write-Warning "pip $($PipArgs -join ' ') failed (attempt $attempt/$MaxRetries, exit $LASTEXITCODE). Retrying in 5s ..."
        Start-Sleep -Seconds 5
    }
    throw "pip $($PipArgs -join ' ') failed after $MaxRetries attempts."
}

function Wait-IngestFinished {
    param([string]$BaseUrl, [string]$LibraryName)
    $encoded = [Uri]::EscapeDataString($LibraryName)
    $deadline = (Get-Date).AddMinutes(240)
    $script:_ingestLastPct = ""
    while ((Get-Date) -lt $deadline) {
        try { $status = Invoke-RestMethod -Uri "$BaseUrl/ingest/status?knowledge_base=$encoded" -TimeoutSec 30 }
        catch { Start-Sleep -Seconds 5; continue }

        switch ($status.status) {
            "completed" {
                $chunks = if ($status.progress) { $status.progress.chunks_indexed } else { "?" }
                Write-Host "[ingest] completed. chunks_indexed=$chunks"
                return $status
            }
            "failed"    { throw "Ingest failed: $($status.error)" }
            default {
                $p = $status.progress
                if ($null -ne $p) {
                    $line = "[ingest] files $($p.completed_files)/$($p.total_files)  chunks=$($p.chunks_indexed)  current=$($p.current_file)"
                    if ($line -ne $script:_ingestLastPct) { Write-Host $line; $script:_ingestLastPct = $line }
                }
                Start-Sleep -Seconds 4
            }
        }
    }
    throw "Ingest timed out after 240 minutes."
}

function Test-RetrieverHasChunks {
    param([string]$BaseUrl, [string]$LibraryName)
    $body = @{ question = "overview"; knowledge_base = $LibraryName; query_scope = "active" } | ConvertTo-Json
    try {
        $r = Invoke-RestMethod -Method Post -Uri "$BaseUrl/debug/retrieve" -Body $body -ContentType "application/json" -TimeoutSec 120
        return ([int]$r.retrieved_count -gt 0)
    } catch { return $false }
}

function Stop-PreviousStack {
    param([string]$AppRoot)
    $stop = Join-Path $AppRoot "stop.ps1"
    if (Test-Path $stop) {
        Write-Host "[stack] Cleaning up any previous run via stop.ps1 ..."
        try { & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $stop *> $null } catch {}
    }
    foreach ($port in 5200, 5201) {
        Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue | ForEach-Object {
            try { Stop-Process -Id $_.OwningProcess -Force -ErrorAction SilentlyContinue } catch {}
        }
    }
}

# ---------- main ----------
if (-not (Test-Administrator)) { throw "Run this script elevated (Run as Administrator)." }

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Push-Location $ScriptRoot
try {
    Disable-Avast
    Enable-WindowsLongPaths

    if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
        throw "winget not found. Install/update 'App Installer' from the Microsoft Store and re-run."
    }

    $workingRepo = $ScriptRoot
    if (-not (Test-Path (Join-Path $workingRepo "deo-rag\docker-compose.yml")) -and -not (Test-Path (Join-Path $workingRepo "docker-compose.yml"))) {
        Write-Host "`n[git] Source code not found locally. Cloning from GitHub..."
        if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
            Install-WingetPackage -Id "Git.Git" -Label "Git"
            Refresh-EnvironmentPath
        }
        $workingRepo = Join-Path $ScriptRoot "deo-rag-repo"
        if (-not (Test-Path $workingRepo)) {
            & git clone "https://github.com/deo-delhi/deo-rag.git" $workingRepo
            if ($LASTEXITCODE -ne 0) { throw "Failed to clone repository from GitHub." }
        }
    }

    $roots    = Find-AppRoots -RepoRoot $workingRepo
    $WsRoot   = $roots.WsRoot
    $AppRoot  = $roots.AppRoot
    $DeoFiles = $roots.DeoFiles

    Write-Host "`n=== DEO RAG - Windows one-click setup ==="
    Write-Host "Workspace : $WsRoot"
    Write-Host "App       : $AppRoot"
    Write-Host "Samples   : $DeoFiles`n"

    # Toolchain
    Refresh-EnvironmentPath
    Install-WingetPackage -Id "Microsoft.VCRedist.2015+.x64" -Label "VC++ 2015-2022 Redistributable"
    Install-WingetPackage -Id "Python.Python.3.12"           -Label "Python 3.12"
    Install-WingetPackage -Id "OpenJS.NodeJS.LTS"            -Label "Node.js LTS"
    Install-WingetPackage -Id "Nvidia.CUDA"                  -Label "NVIDIA CUDA Toolkit"
    Install-WingetPackage -Id "Ollama.Ollama"                -Label "Ollama"
    if (-not $SkipDockerSetup) {
        Install-WingetPackage -Id "Docker.DockerDesktop" -Label "Docker Desktop"
    }
    Refresh-EnvironmentPath

    # Docker engine
    if (-not $SkipDockerSetup) {
        Start-DockerDesktopIfNeeded
        Write-Host "[docker] Waiting for daemon (first start can take a few minutes) ..."
        if (-not (Wait-DockerDaemon)) {
            throw "Docker did not respond in time. Open Docker Desktop manually, wait until it finishes starting, then re-run this script."
        }
    } else {
        docker info | Out-Null
        if ($LASTEXITCODE -ne 0) { throw "Docker is not reachable; remove -SkipDockerSetup or start Docker Desktop." }
    }

    # Ollama
    Refresh-EnvironmentPath
    if (-not (Get-Command ollama -ErrorAction SilentlyContinue)) {
        throw "ollama CLI not on PATH after install. Open a new elevated terminal and re-run."
    }
    Start-OllamaIfNeeded

    Write-Host "`n[ollama] Pulling chat model llama3.2:latest ..."
    & ollama pull llama3.2:latest
    if ($LASTEXITCODE -ne 0) { throw "ollama pull llama3.2:latest failed." }

    Write-Host "[ollama] Pulling embedding model mxbai-embed-large:latest ..."
    & ollama pull mxbai-embed-large:latest
    if ($LASTEXITCODE -ne 0) { throw "ollama pull mxbai-embed-large:latest failed." }

    # Python venv
    $script:VenvPython = Join-Path $WsRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $script:VenvPython)) {
        Write-Host "`n[python] Creating venv at $WsRoot\.venv ..."
        Refresh-EnvironmentPath
        $pyExe = $null
        foreach ($c in @("py", "python")) {
            if (Get-Command $c -ErrorAction SilentlyContinue) { $pyExe = $c; break }
        }
        if (-not $pyExe) { throw "Neither 'py' nor 'python' is on PATH." }
        & $pyExe -m venv "$(Join-Path $WsRoot '.venv')"
        if (-not (Test-Path $script:VenvPython)) { throw "venv creation failed (Avast may still be blocking 'ensurepip'; rerun after smc -stop or with -SkipAvastUnlock omitted)." }
    }

    # Pre-clear any antivirus SSL injection for pip
    $env:SSLKEYLOGFILE = $null

    Invoke-Pip -PipArgs @("install", "--upgrade", "pip", "wheel", "setuptools")
    Write-Host "`n[python] Installing backend requirements (large download, several minutes) ..."
    Invoke-Pip -PipArgs @("install", "-r", (Join-Path $AppRoot "backend\requirements.txt"))
    Write-Host "`n[python] Overriding with CUDA PyTorch and PaddlePaddle GPU versions ..."
    & $script:VenvPython -m pip uninstall -y paddlepaddle 2>&1 | Out-Null
    Invoke-Pip -PipArgs @("install", "torch", "torchvision", "torchaudio", "--index-url", "https://download.pytorch.org/whl/cu118")
    Invoke-Pip -PipArgs @("install", "paddlepaddle-gpu")

    # .env
    $envPath = Join-Path $AppRoot ".env"
    $envContent = @"
LANGCHAIN_TRACING_V2=false
LANGCHAIN_ENDPOINT=https://api.smith.langchain.com
LANGCHAIN_API_KEY=
LANGCHAIN_PROJECT=deo-rag

LLM_PROVIDER=ollama
LLM_MODEL=llama3.2:latest
OLLAMA_BASE_URL=http://127.0.0.1:11434

EMBEDDING_PROVIDER=ollama
EMBEDDING_MODEL=mxbai-embed-large:latest

INGEST_CHUNK_SIZE=1000
INGEST_CHUNK_OVERLAP=150
RETRIEVER_TOP_K=6

LLM_TEMPERATURE=0
OLLAMA_NUM_CTX=8192
OLLAMA_NUM_PREDICT=2048
OLLAMA_REQUEST_TIMEOUT_SECONDS=300
ASK_TIMEOUT_SECONDS=300

OPENAI_API_KEY=

DATABASE_URL=postgresql+psycopg2://admin:admin123@localhost:5202/deorag
COLLECTION_NAME=deo_docs_unflagged
DOCUMENTS_DIR=../documents

ALLOWED_ORIGINS=
ALLOWED_ORIGIN_REGEX=
"@
    Set-Content -Path $envPath -Value $envContent -Encoding UTF8
    Write-Host "[env] Wrote $envPath"

    # Sample PDFs
    $docsLib = Join-Path $AppRoot "documents\$SampleLibrary"
    New-Item -ItemType Directory -Force -Path $docsLib | Out-Null
    if (Test-Path $DeoFiles) {
        $pdfs = Get-ChildItem -Path $DeoFiles -Filter "*.pdf" -File -ErrorAction SilentlyContinue
        if ($pdfs.Count -eq 0) {
            Write-Warning "[pdfs] No PDFs under $DeoFiles - drop your court PDFs there and re-run, or upload via UI."
        } else {
            Write-Host "[pdfs] Copying $($pdfs.Count) sample PDFs into documents\$SampleLibrary ..."
            foreach ($pdf in $pdfs) { Copy-Item -Force -Path $pdf.FullName -Destination (Join-Path $docsLib $pdf.Name) }
        }
    } else {
        Write-Warning "[pdfs] Folder not found: $DeoFiles - clone the repo with deo-files/, or copy PDFs into $docsLib."
    }

    # Frontend deps
    Push-Location (Join-Path $AppRoot "frontend")
    try {
        Write-Host "`n[frontend] npm install ..."
        & npm install --no-audit --no-fund
        if ($LASTEXITCODE -ne 0) { throw "npm install failed (exit $LASTEXITCODE)." }
    } finally { Pop-Location }

    # Stack
    Stop-PreviousStack -AppRoot $AppRoot

    Push-Location $AppRoot
    try {
        Write-Host "`n[stack] Starting Postgres + backend + frontend via script.ps1 ..."
        $launcher = Join-Path $AppRoot "script.ps1"
        & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $launcher
        if ($LASTEXITCODE -ne 0) {
            throw "script.ps1 failed (exit $LASTEXITCODE). See $AppRoot\.run-logs\backend.log and frontend.log."
        }
    } finally { Pop-Location }

    # Wait up to ~6 min for backend (cold ML imports on Windows can be slow)
    $backendReady = $false
    for ($k = 0; $k -lt 120; $k++) {
        try { Invoke-RestMethod -Uri $BackendHealthUrl -TimeoutSec 3 | Out-Null; $backendReady = $true; break }
        catch { Start-Sleep -Seconds 3 }
    }
    if (-not $backendReady) {
        throw "Backend /health did not respond. Inspect $AppRoot\.run-logs\backend.log and re-run."
    }

    Write-Host "`n[settings] Pushing UI defaults (llama3.2, top_k=6, num_predict=2048) ..."
    $settingsBody = @{
        llm_model          = "llama3.2:latest"
        retriever_top_k    = 6
        ollama_num_predict = 2048
        ollama_num_ctx     = 8192
    } | ConvertTo-Json
    try {
        Invoke-RestMethod -Method Put -Uri "$BackendBase/settings" -Body $settingsBody -ContentType "application/json" -TimeoutSec 60 | Out-Null
    } catch {
        Write-Warning "[settings] Could not PATCH settings: $($_.Exception.Message). You can set llama3.2 in the Settings panel."
    }

    # Create + activate library (treat 409 'already exists' as success)
    foreach ($call in @(
        @{ Method = "Post"; Url = "$BackendBase/knowledge-bases" },
        @{ Method = "Put";  Url = "$BackendBase/knowledge-bases/active" }
    )) {
        try {
            Invoke-RestMethod -Method $call.Method -Uri $call.Url `
                -Body (@{ knowledge_base = $SampleLibrary } | ConvertTo-Json) `
                -ContentType "application/json" -TimeoutSec 60 | Out-Null
        } catch {
            $msg = $_.Exception.Message
            if ($msg -notmatch "409") { Write-Warning "[kb] $($call.Url): $msg" }
        }
    }

    # Ingest
    $doIngest = -not $SkipSampleIngest
    if ($doIngest -and -not $ForceReIngest) {
        if (Test-RetrieverHasChunks -BaseUrl $BackendBase -LibraryName $SampleLibrary) {
            Write-Host "[ingest] Vector store already populated for '$SampleLibrary' - skipping (use -ForceReIngest to redo)."
            $doIngest = $false
        }
    }

    if ($doIngest) {
        Write-Host "`n[ingest] Starting ingestion for '$SampleLibrary' (CPU-only machines: this can take a long time) ..."
        $ingestBody = @{
            knowledge_base     = $SampleLibrary
            replace_collection = $true
            chunk_size         = 1000
            chunk_overlap      = 150
        } | ConvertTo-Json
        Invoke-RestMethod -Method Post -Uri "$BackendBase/ingest/start" -Body $ingestBody `
            -ContentType "application/json" -TimeoutSec 120 | Out-Null
        Wait-IngestFinished -BaseUrl $BackendBase -LibraryName $SampleLibrary | Out-Null
    }

    Write-Host "`n[ui] Opening $FrontendUrl ..."
    Start-Process $FrontendUrl

    Write-Host ""
    Write-Host "Done."
    Write-Host "  Frontend : $FrontendUrl"
    Write-Host "  Backend  : $BackendBase/docs"
    Write-Host "  Stop     : $AppRoot\stop.ps1"
}
finally {
    Pop-Location
}
