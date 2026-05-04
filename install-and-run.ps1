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

# winget exit codes that mean "package is fine; nothing to do" (these are NOT errors).
# Source: https://learn.microsoft.com/windows/package-manager/winget/returnCodes
$script:WingetBenignExitCodes = @(
    0,
    -1978335189,  # APPINSTALLER_CLI_ERROR_UPDATE_NOT_APPLICABLE  (no newer version)
    -1978335212,  # APPINSTALLER_CLI_ERROR_NO_APPLICATIONS_FOUND  (already there)
    -1978335215,  # APPINSTALLER_CLI_ERROR_PACKAGE_ALREADY_INSTALLED
    -1978335135   # APPINSTALLER_CLI_ERROR_INSTALL_PACKAGE_IN_USE_BY_APPLICATION (rare; usually fine after retry)
)

# Run a native exe and never let its stderr crash the script. Returns the exit code.
# This is the workaround for the long-standing PowerShell 5.1 quirk where a
# native command writing to stderr is wrapped as a NativeCommandError that, under
# $ErrorActionPreference = 'Stop', terminates the whole script even when the
# command itself succeeded or the situation is recoverable.
function Invoke-NativeSafe {
    param(
        [Parameter(Mandatory)] [string]   $File,
        [string[]]                         $Arguments = @(),
        [switch]                           $ShowOutput
    )
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        if ($ShowOutput) {
            & $File @Arguments 2>&1 | ForEach-Object { Write-Host $_ }
        } else {
            & $File @Arguments *>&1 | Out-Null
        }
        return $LASTEXITCODE
    } catch {
        Write-Host "  [native] $File raised: $($_.Exception.Message)" -ForegroundColor DarkGray
        return -1
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Test-WingetPackageInstalled {
    param([string]$Id)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $output = & winget list --id $Id --exact --source winget 2>&1 | Out-String
        return ($output -match [regex]::Escape($Id))
    } catch {
        return $false
    } finally {
        $ErrorActionPreference = $prev
    }
}

function Install-WingetPackage {
    param([string]$Id, [string]$Label)
    Write-Host "  [winget] Ensuring $Label ($Id) ..."
    if (Test-WingetPackageInstalled -Id $Id) {
        Write-Host "  [winget] $Label already installed - skipping."
        Refresh-EnvironmentPath
        return
    }
    $code = Invoke-NativeSafe -ShowOutput -File "winget" -Arguments @(
        "install", "-e", "--id", $Id, "--source", "winget",
        "--accept-package-agreements", "--accept-source-agreements", "--silent"
    )
    if ($code -eq 0) {
        Write-Host "  [winget] $Label installed."
    } elseif ($script:WingetBenignExitCodes -contains $code -or (Test-WingetPackageInstalled -Id $Id)) {
        Write-Host "  [winget] $Label already present (winget exit $code) - continuing."
    } else {
        Write-Warning "  [winget] $Label install exited $code. Continuing; the next step will surface it if it's actually missing."
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
    Write-Host "[ollama] Starting background service with CUDA_VISIBLE_DEVICES=0, KEEP_ALIVE=24h, NUM_PARALLEL=4 ..."
    $env:CUDA_VISIBLE_DEVICES = "0"
    # Keep models pinned in VRAM across requests; otherwise long ingestion runs
    # pay a model-reload tax every few minutes when the default 5min idle hits.
    $env:OLLAMA_KEEP_ALIVE = "24h"
    # Allow Ollama to serve multiple embed/chat requests concurrently from the
    # same loaded model. Pairs with the parallel ingest workers in ingest.py.
    $env:OLLAMA_NUM_PARALLEL = "4"
    # Allow more than one model resident at once (LLM + embedding model).
    $env:OLLAMA_MAX_LOADED_MODELS = "2"
    Start-Process -FilePath "ollama" -ArgumentList "serve" -WindowStyle Hidden -ErrorAction SilentlyContinue | Out-Null
    if (-not (Wait-OllamaServer)) { throw "Ollama HTTP API did not start (localhost:11434)." }
}

function Test-DockerEngineUp {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) { return $false }
    return ((Invoke-NativeSafe -File "docker" -Arguments @("info")) -eq 0)
}

function Start-DockerDesktopIfNeeded {
    if (Test-DockerEngineUp) {
        Write-Host "[docker] Engine already up."
        return
    }
    $dd = @(
        "$env:ProgramFiles\Docker\Docker\Docker Desktop.exe",
        "$env:ProgramFiles(x86)\Docker\Docker\Docker Desktop.exe"
    ) | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($dd) {
        Write-Host "[docker] Launching Docker Desktop ..."
        try { Start-Process -FilePath $dd -ErrorAction SilentlyContinue | Out-Null } catch {
            Write-Warning "[docker] Could not launch Docker Desktop: $($_.Exception.Message)"
        }
    } else {
        Write-Warning "[docker] Docker Desktop.exe not found in the default install location."
    }
}

function Wait-DockerDaemon {
    $deadline = (Get-Date).AddMinutes(10)
    while ((Get-Date) -lt $deadline) {
        if (Test-DockerEngineUp) {
            $compose = Invoke-NativeSafe -File "docker" -Arguments @("compose", "version")
            if ($compose -eq 0) { return $true }
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

function Get-VideoAdapters {
    try {
        return @(Get-CimInstance Win32_VideoController -ErrorAction SilentlyContinue)
    } catch {
        return @()
    }
}

function Test-NvidiaGpuPresent {
    try {
        if (Get-Command nvidia-smi -ErrorAction SilentlyContinue) {
            $proc = Start-Process -FilePath "nvidia-smi" -ArgumentList "-L" `
                -NoNewWindow -PassThru -Wait -RedirectStandardOutput "$env:TEMP\nvsmi.out" `
                -RedirectStandardError "$env:TEMP\nvsmi.err" -ErrorAction SilentlyContinue
            if ($proc -and $proc.ExitCode -eq 0) { return $true }
        }
    } catch {}
    foreach ($a in Get-VideoAdapters) {
        if ($a.Name -match "NVIDIA") { return $true }
    }
    return $false
}

function Test-IntelArcGpuPresent {
    foreach ($a in Get-VideoAdapters) {
        # Intel Arc / Battlemage discrete cards. Intel iGPUs (UHD/Iris) are
        # excluded here because XPU wheels target only the discrete line.
        if ($a.Name -match "Intel" -and $a.Name -match "Arc|Battlemage") { return $true }
    }
    return $false
}

function Test-AmdOrIntelGpuPresent {
    foreach ($a in Get-VideoAdapters) {
        if ($a.Name -match "AMD|Radeon|Intel") { return $true }
    }
    return $false
}

function Get-PreferredAcceleratorTier {
    # CUDA strictly wins because it's the only path the whole pipeline
    # (Docling + HuggingFace + Ollama) can fully exploit.
    if (Test-NvidiaGpuPresent)        { return "cuda" }
    if (Test-IntelArcGpuPresent)      { return "xpu" }
    if (Test-AmdOrIntelGpuPresent)    { return "directml" }
    return "cpu"
}

function Install-GpuPyTorch {
    param([Parameter(Mandatory)] [string] $VenvPython)
    Write-Host "[gpu] NVIDIA GPU detected - replacing the CPU PyTorch wheel with a CUDA build."
    # IMPORTANT: requirements.txt pulls torch transitively (sentence-transformers,
    # docling, unstructured), and the default PyPI Windows wheel is CPU-only.
    # Without --force-reinstall, a plain `pip install torch --index-url ...`
    # is a no-op because pip sees torch as already-satisfied.
    & $VenvPython -m pip uninstall -y torch torchvision torchaudio 2>&1 | Out-Null
    # Try the newest CUDA index first, then fall back. PyTorch keeps
    # compatibility with older drivers on cu121.
    $ok = $false
    # cu118 last: older Windows drivers (pre-525) can load CUDA 11.8 runtimes; CUDA 12
    # wheels need recent Game Ready / Studio drivers. See NVIDIA download if all probes fail.
    foreach ($cuTag in @("cu126", "cu124", "cu121", "cu118")) {
        $url = "https://download.pytorch.org/whl/$cuTag"
        Write-Host "[gpu] pip install torch torchvision torchaudio --index-url $url"
        try {
            & $VenvPython -m pip install --upgrade --force-reinstall `
                --disable-pip-version-check --no-input --retries 5 --timeout 120 `
                --index-url $url torch torchvision torchaudio
            if ($LASTEXITCODE -eq 0) {
                $probe = & $VenvPython -c "import torch; print(torch.cuda.is_available())" 2>$null
                if ($probe -match "True") {
                    $ok = $true
                    Write-Host "[gpu] PyTorch CUDA wheel installed and detected the GPU ($cuTag)."
                    break
                }
            }
        } catch {}
        Write-Warning "[gpu] $cuTag PyTorch wheel did not produce a usable CUDA runtime; trying next."
    }
    if (-not $ok) {
        Write-Warning "[gpu] No CUDA PyTorch wheel installed cleanly. Reverting to CPU PyTorch so the app still works."
        Write-Warning "[gpu] If you have an NVIDIA GPU, update the display driver from https://www.nvidia.com/Download/index.aspx then re-run this script (CUDA 12 wheels typically need driver 525+; cu118 may work on older drivers)."
        Invoke-Pip -PipArgs @("install", "--upgrade", "--force-reinstall", "torch", "torchvision", "torchaudio")
    }
    # paddlex (a transitive dep of paddleocr) caps numpy<2.4. The CUDA torch
    # wheels happily pull numpy 2.4+, which then breaks paddlex at import time.
    Invoke-Pip -PipArgs @("install", "--upgrade", "numpy<2.4")
}

function Repair-CpuPaddle {
    param([Parameter(Mandatory)] [string] $VenvPython)
    # NOTE: We deliberately do NOT install paddlepaddle-gpu alongside CUDA torch
    # on Windows. Both wheels ship their own copy of cuDNN (cudnn_cnn64_9.dll)
    # with different ABIs; whichever is loaded first prevents the other from
    # importing. Since Docling already does GPU OCR via torch, PaddleOCR's role
    # (creating a searchable-PDF sidecar in `ensure_searchable_pdf`) is a
    # redundant safety net and can stay on CPU without hurting throughput.
    Write-Host "[gpu] Keeping paddlepaddle on CPU to avoid the cuDNN ABI conflict with CUDA PyTorch on Windows."
    & $VenvPython -m pip uninstall -y paddlepaddle paddlepaddle-gpu 2>&1 | Out-Null
    Invoke-Pip -PipArgs @("install", "--upgrade", "paddlepaddle")
}

function Install-XpuPyTorch {
    param([Parameter(Mandatory)] [string] $VenvPython)
    Write-Host "[gpu] Intel Arc discrete GPU detected - installing PyTorch XPU wheels."
    & $VenvPython -m pip uninstall -y torch torchvision torchaudio 2>&1 | Out-Null
    $url = "https://download.pytorch.org/whl/xpu"
    try {
        & $VenvPython -m pip install --upgrade --force-reinstall `
            --disable-pip-version-check --no-input --retries 5 --timeout 120 `
            --index-url $url torch torchvision torchaudio
        $probe = & $VenvPython -c "import torch; xpu = getattr(torch, 'xpu', None); print(bool(xpu and xpu.is_available()))" 2>$null
        if ($probe -match "True") {
            Write-Host "[gpu] PyTorch XPU wheel installed and detected an Intel GPU."
            return
        }
    } catch {}
    Write-Warning "[gpu] PyTorch XPU wheel did not produce a usable XPU runtime. Falling back to CPU PyTorch."
    Invoke-Pip -PipArgs @("install", "--upgrade", "--force-reinstall", "torch", "torchvision", "torchaudio")
}

function Install-DirectMLPyTorch {
    param([Parameter(Mandatory)] [string] $VenvPython)
    Write-Host "[gpu] AMD/Intel GPU detected on Windows - installing torch-directml for cross-vendor GPU support."
    # torch-directml ships its own CPU torch build it links against. Reset to a
    # clean CPU torch first so we don't carry over any stale CUDA wheel that
    # would conflict with directml's chosen torch version.
    & $VenvPython -m pip uninstall -y torch torchvision torchaudio torch-directml 2>&1 | Out-Null
    Invoke-Pip -PipArgs @("install", "--upgrade", "torch", "torchvision", "torchaudio")
    try {
        & $VenvPython -m pip install --upgrade --no-input --retries 3 --timeout 120 torch-directml
        $probe = & $VenvPython -c "import torch_directml; print(torch_directml.is_available() if hasattr(torch_directml,'is_available') else (torch_directml.device_count() > 0))" 2>$null
        if ($probe -match "True") {
            Write-Host "[gpu] torch-directml installed and detected a DirectML device."
            Write-Host "[gpu] Note: Docling and HuggingFace embeddings stay on CPU; DirectML is exposed for custom torch code."
            return
        }
    } catch {}
    Write-Warning "[gpu] torch-directml install did not produce a usable device. Continuing with CPU PyTorch only."
}

function Install-AcceleratedPyTorch {
    param(
        [Parameter(Mandatory)] [string] $VenvPython,
        [Parameter(Mandatory)] [string] $Tier
    )
    switch ($Tier) {
        "cuda"     { Install-GpuPyTorch     -VenvPython $VenvPython; Repair-CpuPaddle -VenvPython $VenvPython }
        "xpu"      { Install-XpuPyTorch     -VenvPython $VenvPython }
        "directml" { Install-DirectMLPyTorch -VenvPython $VenvPython }
        default    { Write-Host "[gpu] No supported GPU detected - keeping CPU PyTorch wheels." }
    }
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

# ---------- reboot + resume helpers ----------
# Docker Desktop's first-time install enables WSL2 / VirtualMachinePlatform /
# Hyper-V Windows features. Those features only activate after a system reboot,
# so the very first 'docker info' on a fresh machine ALWAYS fails with
# "The system cannot find the file specified" against npipe:////./pipe/docker_engine.
# We detect that case, schedule the installer to relaunch at the next logon
# via a Task Scheduler ONLOGON task running elevated, and reboot automatically.

$script:ResumeTaskName = "DEO-RAG-Installer-Resume"
$script:StateDir       = Join-Path $env:ProgramData "DEO-RAG-Installer"
$script:StateFile      = Join-Path $script:StateDir "state.json"
$script:ResumeBatPath  = $null   # set in main once $ScriptRoot is known

function Get-InstallState {
    if (Test-Path $script:StateFile) {
        try {
            $raw = Get-Content -Path $script:StateFile -Raw -Encoding UTF8 -ErrorAction Stop
            if ($raw) { return ($raw | ConvertFrom-Json) }
        } catch {}
    }
    return [pscustomobject]@{
        reboot_count                     = 0
        docker_post_install_reboot_done  = $false
    }
}

function Set-InstallState {
    param($State)
    if (-not (Test-Path $script:StateDir)) {
        New-Item -ItemType Directory -Force -Path $script:StateDir | Out-Null
    }
    ($State | ConvertTo-Json -Depth 5) | Set-Content -Path $script:StateFile -Encoding UTF8
}

function Test-PendingReboot {
    $paths = @(
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootPending",
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\RebootInProgress",
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\PackagesPending",
        "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\WindowsUpdate\Auto Update\RebootRequired"
    )
    foreach ($p in $paths) { if (Test-Path $p) { return $true } }
    try {
        $sm = Get-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\Session Manager" `
            -Name "PendingFileRenameOperations" -ErrorAction SilentlyContinue
        if ($sm -and $sm.PendingFileRenameOperations) { return $true }
    } catch {}
    return $false
}

function Register-ResumeAfterReboot {
    if (-not $script:ResumeBatPath -or -not (Test-Path $script:ResumeBatPath)) {
        Write-Warning "[reboot] Resume launcher not found at '$script:ResumeBatPath'. Auto-resume is disabled."
        return $false
    }
    & schtasks.exe /Delete /F /TN $script:ResumeTaskName *> $null
    $tr   = '"' + $env:ComSpec + '" /c """' + $script:ResumeBatPath + '"""'
    $user = "$env:USERDOMAIN\$env:USERNAME"
    & schtasks.exe /Create /F /TN $script:ResumeTaskName /TR $tr /SC ONLOGON /RU $user /RL HIGHEST /IT *> $null
    if ($LASTEXITCODE -eq 0) {
        Write-Host "[reboot] Auto-resume task '$script:ResumeTaskName' will fire at next logon."
        return $true
    }
    Write-Warning "[reboot] Could not register resume task (schtasks exit $LASTEXITCODE). You will need to re-run install-and-run.bat manually after reboot."
    return $false
}

function Unregister-ResumeAfterReboot {
    & schtasks.exe /Delete /F /TN $script:ResumeTaskName *> $null
}

function Invoke-RebootAndResume {
    param(
        [int]    $DelaySeconds = 30,
        [string] $Reason       = "DEO RAG installer: rebooting to finish Docker Desktop / WSL2 setup."
    )
    Register-ResumeAfterReboot | Out-Null
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host "  REBOOT REQUIRED" -ForegroundColor Yellow
    Write-Host "  Reason : $Reason"
    Write-Host "  Action : Windows will restart in $DelaySeconds seconds." -ForegroundColor Yellow
    Write-Host "  After login, the installer continues automatically."
    Write-Host "  To cancel the restart now, open a terminal and run:  shutdown /a" -ForegroundColor Yellow
    Write-Host "============================================================" -ForegroundColor Yellow
    Write-Host ""
    Start-Sleep -Seconds 5
    & shutdown.exe /r /t $DelaySeconds /c $Reason | Out-Null
    Pop-Location -ErrorAction SilentlyContinue
    exit 0
}

function Test-Wsl2Installed {
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) { return $false }
    # cmd.exe owns the redirection, so its child process never streams stderr
    # back to PowerShell. This is what makes the check safe even when WSL is
    # missing and writes "The Windows Subsystem for Linux is not installed."
    $null = & cmd.exe /c "wsl --status >nul 2>&1"
    return ($LASTEXITCODE -eq 0)
}

function Install-Wsl2IfNeeded {
    try {
        if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
            Write-Host "[wsl] wsl.exe not on PATH yet - Docker Desktop installer will pull WSL2 components and a reboot will follow."
            return
        }
        if (Test-Wsl2Installed) {
            Write-Host "[wsl] WSL2 already installed."
            return
        }
        Write-Host "[wsl] Installing WSL2 (no distribution; required for Docker Desktop) ..."
        $null = & cmd.exe /c "wsl --install --no-distribution >nul 2>&1"
        if ($LASTEXITCODE -ne 0) {
            Write-Warning "[wsl] 'wsl --install' returned exit $LASTEXITCODE - Docker Desktop will pull / activate WSL2 itself; the auto-reboot below will finish the job."
        } else {
            Write-Host "[wsl] WSL2 install requested - a reboot will activate it."
        }
    } catch {
        Write-Warning "[wsl] WSL2 setup skipped: $($_.Exception.Message). Docker Desktop will handle WSL2 itself."
    }
}

# ---------- main ----------
if (-not (Test-Administrator)) { throw "Run this script elevated (Run as Administrator)." }

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:ResumeBatPath = Join-Path $ScriptRoot "install-and-run.bat"
$installState         = Get-InstallState

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
        # Track whether Docker Desktop existed BEFORE we ran the installer, so we
        # can tell a "fresh install" (which forces WSL2/HyperV feature activation
        # and therefore needs a reboot before the engine can come up) apart from
        # an upgrade / no-op install.
        $ddExePath        = Join-Path $env:ProgramFiles "Docker\Docker\Docker Desktop.exe"
        $ddWasPresent     = Test-Path $ddExePath
        $pendingBefore    = Test-PendingReboot

        Install-Wsl2IfNeeded
        Install-WingetPackage -Id "Docker.DockerDesktop" -Label "Docker Desktop"

        $ddIsPresentNow   = Test-Path $ddExePath
        $ddJustInstalled  = ($ddIsPresentNow -and -not $ddWasPresent)
        $pendingAfter     = Test-PendingReboot

        # If Docker Desktop was just installed, OR Windows reports a pending reboot
        # (typically because WSL2 / VirtualMachinePlatform / Hyper-V was just turned
        # on), reboot now and resume automatically. Without this, the next call to
        # 'docker info' fails with:
        #   "open //./pipe/docker_engine: The system cannot find the file specified."
        # which is exactly the error you hit on a fresh machine.
        if (($ddJustInstalled -or $pendingAfter -or (-not $pendingBefore -and $pendingAfter)) `
            -and -not $installState.docker_post_install_reboot_done) {
            $installState.docker_post_install_reboot_done = $true
            $installState.reboot_count = ([int]$installState.reboot_count) + 1
            Set-InstallState $installState

            $why = if ($ddJustInstalled) {
                "Docker Desktop was just installed; WSL2 / VirtualMachinePlatform features need a reboot to activate."
            } else {
                "Windows is reporting a pending reboot (likely from the WSL2 / Hyper-V feature install)."
            }
            Invoke-RebootAndResume -Reason $why
        }
    }
    Refresh-EnvironmentPath

    # Docker engine
    if (-not $SkipDockerSetup) {
        Start-DockerDesktopIfNeeded
        Write-Host "[docker] Waiting for daemon (first start can take several minutes) ..."
        if (-not (Wait-DockerDaemon)) {
            # Defensive: should be rare since we already reboot pre-emptively above.
            # If we still can't reach the engine and we haven't already used up our
            # reboot budget, schedule one more auto-reboot + auto-resume.
            if ([int]$installState.reboot_count -lt 2) {
                $installState.reboot_count = ([int]$installState.reboot_count) + 1
                Set-InstallState $installState
                Write-Warning "[docker] Daemon still not responding. Auto-rebooting once more."
                Invoke-RebootAndResume -Reason "Docker daemon did not respond after install + start. Rebooting to retry."
            }
            throw "Docker daemon did not start after $([int]$installState.reboot_count) automatic reboots. Open Docker Desktop manually, wait until the whale icon turns steady, then re-run install-and-run.bat."
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

    $accelTier = Get-PreferredAcceleratorTier
    Write-Host "`n[python] Accelerator tier resolved: $accelTier  (preference order: cuda > xpu > directml > cpu)"
    Install-AcceleratedPyTorch -VenvPython $script:VenvPython -Tier $accelTier

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
INGEST_EMBED_BATCH_SIZE=32
INGEST_MAX_WORKERS=0
INGEST_HF_ENCODE_BATCH_SIZE=0
RETRIEVER_TOP_K=4

LLM_TEMPERATURE=0
OLLAMA_NUM_CTX=4096
OLLAMA_NUM_PREDICT=512
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

    Write-Host "`n[settings] Pushing UI defaults (llama3.2, top_k=4, num_predict=512) ..."
    $settingsBody = @{
        llm_model          = "llama3.2:latest"
        retriever_top_k    = 4
        ollama_num_predict = 512
        ollama_num_ctx     = 4096
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

    # Successful end-to-end run: clear the resume-on-logon scheduled task and the
    # state file so the next logon doesn't re-launch the installer.
    Unregister-ResumeAfterReboot
    Remove-Item -Path $script:StateFile -ErrorAction SilentlyContinue

    Write-Host ""
    Write-Host "Done."
    Write-Host "  Frontend : $FrontendUrl"
    Write-Host "  Backend  : $BackendBase/docs"
    Write-Host "  Stop     : $AppRoot\stop.ps1"
}
catch {
    $msg = $_.Exception.Message
    $where = ""
    if ($_.InvocationInfo -and $_.InvocationInfo.PositionMessage) {
        $where = $_.InvocationInfo.PositionMessage
    }
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host "  Installer error" -ForegroundColor Red
    Write-Host "  $msg" -ForegroundColor Red
    if ($where) { Write-Host $where -ForegroundColor DarkGray }
    Write-Host "============================================================" -ForegroundColor Red
    Write-Host ""
    Write-Host "What to do next:" -ForegroundColor Yellow
    Write-Host "  1. Read the message above. Most failures here are environmental (network, antivirus, missing reboot)." -ForegroundColor Yellow
    Write-Host "  2. If Docker / WSL2 looks involved, just re-run install-and-run.bat - the script is idempotent and will pick up where it stopped." -ForegroundColor Yellow
    Write-Host "  3. Backend / frontend logs (if the stack already started): $AppRoot\.run-logs\backend.log  and  frontend.log" -ForegroundColor Yellow
    Write-Host ""
    exit 1
}
finally {
    Pop-Location
}
