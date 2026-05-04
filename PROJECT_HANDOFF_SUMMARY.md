# DEO RAG Project Handoff Summary

Last updated: 2026-05-04

## Project Overview

DEO RAG is a local Retrieval-Augmented Generation system for Defence Estates Organisation records. It provides:

- A FastAPI backend in `deo-rag/backend`.
- A React/Vite frontend in `deo-rag/frontend`.
- PostgreSQL with pgvector through Docker Compose in `deo-rag/docker-compose.yml`.
- PDF parsing with Docling first, PyPDF fallback, and optional OCR/searchable-PDF sidecars.
- Chunking and embedding into pgvector.
- Retrieval, debug retrieval, and source-linked answers through the UI/API.
- Local model support through Ollama and optional OpenAI provider support.

Default local endpoints:

- Frontend: `http://127.0.0.1:5201`
- Backend: `http://127.0.0.1:5200`
- Backend docs: `http://127.0.0.1:5200/docs`
- PostgreSQL: `localhost:5202`

## Current Direction

The project is moving from a Windows-only one-click setup toward robust cross-platform deployment:

- Keep the Windows `install-and-run.bat` / `install-and-run.ps1` path working.
- Add a similar one-command Ubuntu / WSL Ubuntu setup path.
- Improve GPU/CUDA detection and PyTorch installation so ingestion uses CUDA where the hardware and driver support it.
- Keep CPU fallback reliable on older GPUs or machines without NVIDIA support.

## Recent Work Completed

### GitHub Sync And Runtime

- Pulled latest upstream changes from `origin/main`.
- Restarted the local stack after pull.
- Ran frontend `npm run build` successfully.
- Verified backend health returned HTTP 200.

### CUDA / Ingestion Tuning

The local machine reported:

- NVIDIA driver: `474.44`
- CUDA runtime from driver: `11.4`
- GPU: GeForce GT 730
- PyTorch CUDA wheels can detect the GPU, but current PyTorch cannot execute kernels on this card because it is too old for modern wheel support.

Changes made:

- Added `cu118` fallback to Windows CUDA PyTorch installation in `install-and-run.ps1`.
- Added `deo-rag/scripts/repair-cuda-pytorch.ps1` to repair CUDA PyTorch wheels without rerunning the whole Windows installer.
- Kept PaddlePaddle CPU-only on Windows to avoid cuDNN conflicts with CUDA PyTorch.
- Added `INGEST_HF_ENCODE_BATCH_SIZE`.
- Tuned HuggingFace embedding batch size defaults:
  - CUDA: 96
  - XPU: 64
  - CPU: 16
- Capped ingestion worker concurrency when CUDA is actually usable:
  - HuggingFace embeddings on CUDA: 1 PDF worker
  - Other CUDA paths: max 2 PDF workers
- Adjusted Docling thread defaults so CUDA parsing does not over-subscribe CPU threads.
- Improved hardware calibration notes for old GPUs, driver mismatch, or CPU wheel fallback.

Important: chunking itself is CPU work. CUDA helps mainly with Docling model work and HuggingFace embeddings when PyTorch can actually run CUDA kernels.

### Ubuntu / WSL Ubuntu Installer

Added a Linux equivalent of the Windows one-click installer:

- `setup-deo-rag.sh`
  - Downloads or updates the repo under `~/deo-rag-setup/deo-rag`.
  - Runs `install-and-run.sh`.
- `install-and-run.sh`
  - Installs Ubuntu dependencies through `apt`.
  - Installs Docker and Docker Compose.
  - Installs Node.js 20 when the existing Node is too old.
  - Installs Ollama and starts it.
  - Creates or updates the Python virtual environment.
  - Installs backend Python requirements.
  - Attempts CUDA PyTorch wheels if `nvidia-smi` is visible.
  - Builds the frontend.
  - Creates `.env` defaults.
  - Copies bundled sample PDFs if `deo-files` exists.
  - Starts the stack in detached mode.
  - Recalibrates hardware.
  - Creates/activates the sample library.
  - Starts sample ingestion unless skipped.

One-command Ubuntu / WSL Ubuntu install:

```bash
curl -fsSL https://raw.githubusercontent.com/deo-delhi/deo-rag/main/setup-deo-rag.sh | bash
```

Useful options:

```bash
curl -fsSL https://raw.githubusercontent.com/deo-delhi/deo-rag/main/setup-deo-rag.sh | bash -s -- --skip-sample-ingest
curl -fsSL https://raw.githubusercontent.com/deo-delhi/deo-rag/main/setup-deo-rag.sh | bash -s -- --force-reingest
```

For WSL:

- The script assumes Ubuntu is already installed in WSL.
- Linux-side dependencies are installed inside Ubuntu.
- NVIDIA display drivers must be installed or updated on Windows; the Linux script cannot install Windows GPU drivers.
- Docker can work either through Docker Desktop WSL integration or an Ubuntu-side Docker engine.

### Linux Runtime Script Changes

Updated:

- `deo-rag/script.sh`
  - Supports foreground mode: `bash script.sh`
  - Supports detached mode: `bash script.sh --detach`
  - Writes `.run-logs/pids.json`
  - Uses `sudo docker` automatically when direct Docker access is not available but passwordless sudo Docker works.
- `deo-rag/stop.sh`
  - Uses the same Docker/sudo fallback.

## Important Files

- `README.md`: top-level one-click install commands for Ubuntu/WSL and Windows.
- `install-and-run.sh`: Ubuntu/WSL full installer.
- `setup-deo-rag.sh`: Ubuntu/WSL downloader and launcher.
- `install-and-run.ps1`: Windows full installer.
- `install-and-run.bat`: Windows elevated launcher.
- `deo-rag/script.sh`: Linux/WSL runtime launcher.
- `deo-rag/stop.sh`: Linux/WSL shutdown.
- `deo-rag/script.ps1`: Windows runtime launcher.
- `deo-rag/stop.ps1`: Windows shutdown.
- `deo-rag/backend/config.py`: environment-backed settings.
- `deo-rag/backend/hardware_calibration.py`: accelerator detection and UI/API profile.
- `deo-rag/backend/torch_device.py`: runtime device selection.
- `deo-rag/backend/ingest.py`: PDF parse/chunk/index flow and concurrency.
- `deo-rag/backend/parser.py`: Docling/PyPDF/OCR parsing.
- `deo-rag/backend/rag_pipeline.py`: embeddings, LLM, retrieval chain.

## Known Caveats

- Generated artifacts such as `deo-rag/frontend/dist`, runtime logs, pycache files, and vectorstore data should generally not be committed.
- The current local Windows environment's `bash.exe` points to a broken or missing WSL `/bin/bash`, so shell syntax checks should be rerun inside a working Ubuntu/WSL environment.
- On older GPUs like the GT 730, current PyTorch CUDA wheels may detect CUDA but cannot execute kernels. The app should fall back to CPU in that case.
- If Docker access requires group membership changes, users may need to close and reopen the Ubuntu shell after the installer adds them to the `docker` group.

## Suggested Next Steps

1. Test `install-and-run.sh` in a clean WSL Ubuntu VM.
2. Test `install-and-run.sh` on bare-metal Ubuntu.
3. Add a `.gitignore` update for generated artifacts if not already covered.
4. Consider adding CI shell checks for `*.sh`.
5. Consider adding a non-interactive smoke test that starts the stack with `--skip-sample-ingest` and checks `/health`.
6. Validate CUDA behavior on a modern NVIDIA GPU with a current driver.
