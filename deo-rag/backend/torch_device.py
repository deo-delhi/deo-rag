"""PyTorch / Docling device selection using startup hardware calibration when present."""

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


def _fallback_torch_accelerator() -> str:
    if pytorch_cuda_can_execute():
        return "cuda"
    try:
        import torch

        xpu = getattr(torch, "xpu", None)
        if xpu is not None and callable(getattr(xpu, "is_available", None)):
            if xpu.is_available():
                return "xpu"
    except Exception:
        pass
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
