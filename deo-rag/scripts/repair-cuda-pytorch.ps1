#Requires -Version 5.1
<#
.SYNOPSIS
  Re-install PyTorch with NVIDIA CUDA wheels (no full installer run).

.DESCRIPTION
  Uninstalls torch/torchvision/torchaudio then tries PyTorch indexes in order:
  cu126, cu124, cu121, cu118 — stopping when `torch.cuda.is_available()` is True.
  Pins numpy<2.4 for paddlex (paddleocr) and keeps paddlepaddle on CPU to avoid
  cuDNN ABI clashes with CUDA PyTorch on Windows (same policy as install-and-run.ps1).

.PARAMETER VenvPython
  Path to python.exe in the project venv. Default: repo-root\.venv\Scripts\python.exe
  relative to this script (deo-rag\scripts\ -> ..\..\.venv\...).

.EXAMPLE
  powershell -ExecutionPolicy Bypass -File .\repair-cuda-pytorch.ps1
#>
param(
    [string] $VenvPython = ""
)

$ErrorActionPreference = "Stop"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $here "..\..")).Path
if (-not $VenvPython) {
    $VenvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
}
if (-not (Test-Path $VenvPython)) {
    throw "Python not found at $VenvPython. Create the venv at the repo root or pass -VenvPython."
}

Write-Host "[repair] Using: $VenvPython"

& $VenvPython -m pip uninstall -y torch torchvision torchaudio 2>&1 | Out-Null

$ok = $false
foreach ($cuTag in @("cu126", "cu124", "cu121", "cu118")) {
    $url = "https://download.pytorch.org/whl/$cuTag"
    Write-Host "[repair] Trying $url ..."
    & $VenvPython -m pip install --upgrade --force-reinstall `
        --disable-pip-version-check --no-input --retries 5 --timeout 120 `
        --index-url $url torch torchvision torchaudio
    if ($LASTEXITCODE -eq 0) {
        $probe = & $VenvPython -c "import torch; print(torch.cuda.is_available())" 2>$null
        if ($probe -match "True") {
            $ok = $true
            Write-Host "[repair] CUDA PyTorch OK ($cuTag)."
            break
        }
    }
    Write-Warning "[repair] $cuTag did not yield a usable CUDA runtime; trying next."
}

if (-not $ok) {
    Write-Warning "[repair] No CUDA wheel worked. Installing CPU PyTorch from PyPI."
    & $VenvPython -m pip install --upgrade --force-reinstall torch torchvision torchaudio
    Write-Host "[repair] Install a current NVIDIA driver from https://www.nvidia.com/Download/index.aspx then re-run this script."
}

Write-Host "[repair] Pinning numpy<2.4 for paddleocr / paddlex ..."
& $VenvPython -m pip install --upgrade "numpy<2.4"

Write-Host "[repair] CPU-only paddlepaddle (avoids cuDNN conflict with CUDA torch on Windows) ..."
& $VenvPython -m pip uninstall -y paddlepaddle-gpu 2>&1 | Out-Null
& $VenvPython -m pip install --upgrade paddlepaddle

Write-Host "[repair] Done. Restart the backend and POST /hardware/recalibrate if the API is running."
