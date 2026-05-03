"""PyTorch / Docling device selection using startup hardware calibration when present.

Preference order applied across the app:
    1. NVIDIA CUDA  (CUDA wheels, or AMD ROCm on Linux which masquerades as CUDA)
    2. Intel XPU    (Arc / Iris with PyTorch XPU wheels)
    3. DirectML     (any DX12 GPU on Windows via `torch-directml`; usable for
                     plain torch ops, but Docling and sentence-transformers
                     do not accept it as a device string yet)
    4. CPU          (final fallback)
"""

from __future__ import annotations

from typing import Any


def get_active_hardware_profile() -> dict[str, Any] | None:
    try:
        from .hardware_calibration import ACTIVE_PROFILE

        return ACTIVE_PROFILE
    except Exception:
        return None


def pytorch_cuda_can_execute() -> bool:
    """True when PyTorch can run CUDA kernels on GPU 0 (not just detect the driver)."""
    try:
        import torch

        if not torch.cuda.is_available():
            return False
        major, minor = torch.cuda.get_device_capability(0)
        # Current PyTorch wheels target sm_37+; Kepler 3.5 reports cuda_available but kernels fail.
        return (major, minor) >= (3, 7)
    except Exception:
        return False


def pytorch_xpu_can_execute() -> bool:
    """True when PyTorch can run kernels on an Intel XPU device."""
    try:
        import torch

        xpu = getattr(torch, "xpu", None)
        if xpu is None or not callable(getattr(xpu, "is_available", None)):
            return False
        return bool(xpu.is_available())
    except Exception:
        return False


def directml_usable() -> bool:
    """True when the optional `torch-directml` plugin is installed and reports a device.

    DirectML provides cross-vendor GPU acceleration on Windows for AMD and
    Intel GPUs (and as a fallback for NVIDIA). It does not integrate with
    Docling or sentence-transformers via a device string, but having it
    installed lets advanced/custom code paths (and Ollama, indirectly) use
    the GPU. We surface it in the calibration so users see *something*
    other than `cpu` on AMD/Intel-only Windows machines.
    """
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


def _fallback_torch_accelerator() -> str:
    """Pick the best device string accepted by Docling and sentence-transformers."""
    if pytorch_cuda_can_execute():
        return "cuda"
    if pytorch_xpu_can_execute():
        return "xpu"
    # DirectML deliberately not returned here: Docling's AcceleratorDevice enum
    # is {auto, cpu, cuda, mps, xpu} and sentence-transformers does not accept
    # "privateuseone" device strings. DirectML still appears in the profile
    # under `directml_usable` so the UI can advertise it.
    return "cpu"


def preferred_torch_device() -> str:
    """Device string for HuggingFace embeddings (`cuda`, `xpu`, or `cpu`)."""
    p = get_active_hardware_profile()
    if p and p.get("huggingface_torch_device"):
        return str(p["huggingface_torch_device"])
    return _fallback_torch_accelerator()


def docling_accelerator_device() -> str:
    """Docling `AcceleratorOptions.device` value."""
    p = get_active_hardware_profile()
    if p and p.get("docling_accelerator"):
        return str(p["docling_accelerator"])
    return _fallback_torch_accelerator()


def paddleocr_use_gpu_preferred() -> bool:
    p = get_active_hardware_profile()
    if p is not None and "paddleocr_use_gpu" in p:
        return bool(p["paddleocr_use_gpu"])
    try:
        import paddle

        return bool(paddle.device.is_compiled_with_cuda() and pytorch_cuda_can_execute())
    except Exception:
        return False
