"""
Detect available accelerators and choose a stable fallback chain:

    NVIDIA CUDA (PyTorch kernels)
        → Intel XPU (PyTorch + IPEX / oneAPI, if installed)
        → AMD/Intel DirectML (Windows, via torch-directml, advisory only)
        → CPU.

The chosen tier is recorded as `accelerator_tier` and drives the device
strings used by Docling, HuggingFace embeddings, and PaddleOCR.

Ollama GPU use is probed live via /api/ps; this process cannot force a
specific GPU for Ollama (Ollama picks NVIDIA / ROCm / Metal / Vulkan
depending on the Ollama build).
"""

from __future__ import annotations

import json
import logging
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

PROFILE_FILENAME = "hardware_profile.json"

# Populated at FastAPI startup and on POST /hardware/recalibrate.
ACTIVE_PROFILE: dict[str, Any] | None = None


def profile_path() -> Path:
    return Path(__file__).resolve().parent / PROFILE_FILENAME


@dataclass
class VideoAdapter:
    name: str
    adapter_ram_bytes: int | None
    driver_version: str | None = None


def _windows_video_adapters() -> list[VideoAdapter]:
    if sys.platform != "win32":
        return []
    cmd = [
        "powershell",
        "-NoProfile",
        "-NoLogo",
        "-Command",
        "Get-CimInstance Win32_VideoController | Select-Object Name, AdapterRAM, DriverVersion | ConvertTo-Json -Depth 3 -Compress",
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        if proc.returncode != 0 or not proc.stdout.strip():
            return []
        raw = json.loads(proc.stdout)
        rows = raw if isinstance(raw, list) else [raw]
        out: list[VideoAdapter] = []
        for row in rows:
            name = (row.get("Name") or "").strip()
            if not name:
                continue
            ram = row.get("AdapterRAM")
            ram_i = int(ram) if isinstance(ram, int) and ram > 0 else None
            dv = row.get("DriverVersion")
            dv_s = str(dv).strip() if dv else None
            out.append(VideoAdapter(name=name, adapter_ram_bytes=ram_i, driver_version=dv_s))
        return out
    except Exception as exc:
        logger.debug("WMI video probe failed: %s", exc)
        return []


def _nvidia_smi_gpu_name() -> str | None:
    try:
        proc = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            return proc.stdout.strip().splitlines()[0].strip()
    except Exception:
        pass
    return None


def _classify_adapters(adapters: list[VideoAdapter]) -> tuple[list[str], list[str], list[str]]:
    nvidia, intel, amd = [], [], []
    for a in adapters:
        u = a.name.upper()
        if "NVIDIA" in u:
            nvidia.append(a.name)
        elif "INTEL" in u:
            intel.append(a.name)
        elif "AMD" in u or "RADEON" in u:
            amd.append(a.name)
    return nvidia, intel, amd


def _pytorch_xpu_available() -> bool:
    try:
        import torch

        xpu = getattr(torch, "xpu", None)
        if xpu is not None and callable(getattr(xpu, "is_available", None)):
            return bool(xpu.is_available())
    except Exception:
        pass
    return False


def _torch_directml_available() -> bool:
    """True when the `torch-directml` plugin is installed and exposes a device."""
    try:
        import torch_directml  # type: ignore[import-not-found]

        is_avail = getattr(torch_directml, "is_available", None)
        if callable(is_avail):
            return bool(is_avail())
        device_count = getattr(torch_directml, "device_count", None)
        if callable(device_count):
            return int(device_count()) > 0
        return True
    except Exception:
        return False


def _paddle_cuda_compiled() -> bool:
    try:
        import paddle

        return bool(paddle.device.is_compiled_with_cuda())
    except Exception:
        return False


def _probe_ollama(base_url: str) -> dict[str, Any]:
    import urllib.error
    import urllib.request

    out: dict[str, Any] = {
        "reachable": False,
        "models": [],
        "summary": "Could not reach Ollama",
    }
    try:
        url = base_url.rstrip("/") + "/api/ps"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            if resp.status != 200:
                out["summary"] = f"Ollama /api/ps HTTP {resp.status}"
                return out
            raw = resp.read().decode("utf-8", errors="replace")
        data = json.loads(raw)
        out["reachable"] = True
        models = data.get("models") or []
        slim = []
        for m in models:
            name = m.get("name") or m.get("model") or "unknown"
            details = m.get("details") or {}
            fam = details.get("family") or ""
            vram = m.get("size_vram")
            slim.append(
                {
                    "name": name,
                    "size_vram_bytes": vram,
                    "family": fam,
                }
            )
        out["models"] = slim
        if not slim:
            out["summary"] = (
                "Ollama running — no models loaded in memory yet "
                "(VRAM usage appears after you run chat/embed)."
            )
        else:
            parts = []
            for s in slim:
                vr = s.get("size_vram_bytes")
                label = "GPU VRAM" if isinstance(vr, int) and vr > 0 else "CPU"
                parts.append(f'{s["name"]}: {label}')
            out["summary"] = "; ".join(parts)
        return out
    except urllib.error.HTTPError as exc:
        out["summary"] = f"Ollama /api/ps HTTP {exc.code}"
        return out
    except Exception as exc:
        out["summary"] = f"Ollama probe failed: {exc.__class__.__name__}"
        return out


def calibrate(*, ollama_base_url: str) -> dict[str, Any]:
    from .torch_device import pytorch_cuda_can_execute

    notes: list[str] = []
    adapters = _windows_video_adapters()
    nvidia_names, intel_names, amd_names = _classify_adapters(adapters)
    nvidia_smi = _nvidia_smi_gpu_name()
    nvidia_present = bool(nvidia_names) or bool(nvidia_smi)
    primary_nvidia = (nvidia_names[0] if nvidia_names else None) or nvidia_smi

    nvidia_pytorch_ok = pytorch_cuda_can_execute()
    xpu_ok = _pytorch_xpu_available()
    directml_ok = _torch_directml_available()
    intel_igpu = bool(intel_names)
    amd_present = bool(amd_names)

    if nvidia_present and not nvidia_pytorch_ok:
        notes.append(
            "NVIDIA GPU present but PyTorch cannot run CUDA kernels on it "
            "(unsupported compute capability, missing CUDA wheel, or driver mismatch). "
            "Run install-and-run.ps1 again, or `pip install --force-reinstall --index-url "
            "https://download.pytorch.org/whl/cu126 torch torchvision torchaudio`."
        )
    if intel_igpu and not xpu_ok and not directml_ok:
        notes.append(
            "Intel graphics detected but neither PyTorch XPU nor torch-directml is installed. "
            "Install one to unlock GPU acceleration: `pip install --index-url "
            "https://download.pytorch.org/whl/xpu torch torchvision torchaudio` (Arc / Iris) "
            "or `pip install torch-directml` (any Intel GPU on Windows)."
        )
    if amd_present and not directml_ok:
        if sys.platform == "win32":
            notes.append(
                "AMD GPU detected. Stock PyTorch wheels do not use AMD GPUs on Windows. "
                "Install the cross-vendor DirectML backend with `pip install torch-directml` "
                "to enable GPU offload for any custom torch code; Docling and sentence-"
                "transformers still fall back to CPU because they do not accept DirectML "
                "as a device string."
            )
        else:
            notes.append(
                "AMD GPU detected. Use ROCm PyTorch wheels on Linux (e.g. cu-rocm6.x) "
                "to enable GPU acceleration for Docling and HuggingFace embeddings."
            )

    # ---- Tier resolution ---------------------------------------------------
    # The tier is the highest-quality device this app can actually drive.
    # For Docling and sentence-transformers that means cuda > xpu > cpu (they
    # don't accept DirectML). DirectML is still recorded so the UI can show
    # that *some* GPU acceleration is available for custom code paths and
    # surface it when nothing better is reachable.
    if nvidia_pytorch_ok:
        accelerator_tier = "nvidia_cuda"
        accelerator_tier_label = "NVIDIA CUDA"
        docling_device = "cuda"
        hf_device = "cuda"
    elif xpu_ok:
        accelerator_tier = "intel_xpu"
        accelerator_tier_label = "Intel PyTorch XPU"
        docling_device = "xpu"
        hf_device = "xpu"
        notes.append("Using Intel XPU for PyTorch-backed Docling and HuggingFace embeddings.")
    elif directml_ok:
        accelerator_tier = "directml"
        accelerator_tier_label = "DirectML (advisory)"
        # Docling/HuggingFace can't target DirectML directly, so keep them on
        # CPU but flag the GPU as available for any future / custom code.
        docling_device = "cpu"
        hf_device = "cpu"
        notes.append(
            "DirectML is installed and can run plain torch ops on any DX12 GPU, but "
            "Docling and sentence-transformers do not yet accept DirectML as a device. "
            "Heavy PDF parsing and embeddings stay on CPU on this tier."
        )
    else:
        accelerator_tier = "cpu"
        accelerator_tier_label = "CPU"
        docling_device = "cpu"
        hf_device = "cpu"

    fallback_chain_applied = ["nvidia_cuda", "intel_xpu", "directml", "cpu"]

    paddle_gpu = bool(nvidia_pytorch_ok and _paddle_cuda_compiled())
    if _paddle_cuda_compiled() and not nvidia_pytorch_ok:
        notes.append("PaddlePaddle has CUDA support but no usable NVIDIA device for kernels — OCR stays on CPU.")

    ollama_info = _probe_ollama(ollama_base_url)
    if ollama_info["reachable"] and ollama_info.get("models"):
        notes.append(
            "Ollama GPU offload is independent of this app: it needs a supported "
            "GPU in the Ollama build (NVIDIA / ROCm / Metal / Vulkan)."
        )

    adapter_dump = [
        {
            "name": a.name,
            "adapter_ram_bytes": a.adapter_ram_bytes,
            "driver_version": a.driver_version,
        }
        for a in adapters
    ]

    profile: dict[str, Any] = {
        "calibrated_at": datetime.now(timezone.utc).isoformat(),
        "platform": sys.platform,
        "accelerator_tier": accelerator_tier,
        "accelerator_tier_label": accelerator_tier_label,
        "fallback_chain_applied": fallback_chain_applied,
        "video_adapters": adapter_dump,
        "nvidia_detected": nvidia_present,
        "nvidia_primary_name": primary_nvidia,
        "nvidia_pytorch_cuda_usable": nvidia_pytorch_ok,
        "intel_graphics_detected": intel_igpu,
        "intel_adapter_names": intel_names,
        "amd_graphics_detected": amd_present,
        "amd_adapter_names": amd_names,
        "pytorch_xpu_usable": xpu_ok,
        "directml_usable": directml_ok,
        "docling_accelerator": docling_device,
        "huggingface_torch_device": hf_device,
        "paddleocr_use_gpu": paddle_gpu,
        "ollama": ollama_info,
        "notes": notes,
    }
    return profile


def calibrate_and_save(ollama_base_url: str | None = None) -> dict[str, Any]:
    from .config import SETTINGS

    base = ollama_base_url or SETTINGS.ollama_base_url
    profile = calibrate(ollama_base_url=base)
    try:
        profile_path().write_text(json.dumps(profile, indent=2), encoding="utf-8")
    except OSError as exc:
        logger.warning("Could not write hardware profile: %s", exc)
    return profile


def initialize_hardware_profile() -> dict[str, Any]:
    global ACTIVE_PROFILE
    ACTIVE_PROFILE = calibrate_and_save()
    return ACTIVE_PROFILE


def get_active_profile() -> dict[str, Any] | None:
    return ACTIVE_PROFILE


def profile_for_api() -> dict[str, Any]:
    from .config import SETTINGS

    base = dict(ACTIVE_PROFILE or {})
    base["app_providers"] = {
        "llm_provider": SETTINGS.llm_provider,
        "embedding_provider": SETTINGS.embedding_provider,
        "ollama_base_url": SETTINGS.ollama_base_url,
    }
    # Human-facing rows for the UI
    emb = SETTINGS.embedding_provider.lower()
    if emb == "ollama":
        emb_compute = "Ollama (see ollama.summary — CPU/GPU decided by Ollama)"
    elif emb == "huggingface":
        emb_compute = f"HuggingFace embeddings → PyTorch `{base.get('huggingface_torch_device', 'cpu')}`"
    elif emb == "openai":
        emb_compute = "OpenAI API (remote)"
    else:
        emb_compute = SETTINGS.embedding_provider

    tier_label = base.get("accelerator_tier_label") or "CPU"
    base["usage_summary"] = {
        "accelerator_tier": tier_label,
        "docling_pdf": f"Docling layout/OCR models → `{base.get('docling_accelerator', 'cpu')}`",
        "embeddings": emb_compute,
        "llm": f"LLM via `{SETTINGS.llm_provider}` — if Ollama, see `ollama.summary`",
        "paddleocr_searchable_pdf": (
            "PaddleOCR → NVIDIA CUDA"
            if base.get("paddleocr_use_gpu")
            else "PaddleOCR → CPU"
        ),
        "directml": (
            "torch-directml available for custom GPU code"
            if base.get("directml_usable")
            else "torch-directml not installed"
        ),
    }
    return base


def recalibrate() -> dict[str, Any]:
    global ACTIVE_PROFILE
    ACTIVE_PROFILE = calibrate_and_save()
    return profile_for_api()
