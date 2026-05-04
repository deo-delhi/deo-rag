One-click install

## Ubuntu / WSL Ubuntu

Open an Ubuntu terminal (bare-metal Ubuntu or WSL Ubuntu) and run:

```bash
curl -fsSL https://raw.githubusercontent.com/deo-delhi/deo-rag/main/setup-deo-rag.sh | bash
```

Useful options:

```bash
curl -fsSL https://raw.githubusercontent.com/deo-delhi/deo-rag/main/setup-deo-rag.sh | bash -s -- --skip-sample-ingest
curl -fsSL https://raw.githubusercontent.com/deo-delhi/deo-rag/main/setup-deo-rag.sh | bash -s -- --force-reingest
```

The installer clones or updates the repo under `~/deo-rag-setup/deo-rag`, installs Ubuntu packages, Docker, Node.js 20, Python dependencies, Ollama, CUDA PyTorch when a supported NVIDIA GPU is visible, builds the frontend, starts the stack, and ingests the bundled sample PDFs.

For WSL, install Ubuntu first. If you want CUDA acceleration in WSL, install/update the NVIDIA driver on Windows before running the command; the Linux script can install CUDA PyTorch wheels, but it cannot install the Windows display driver.

After install:

- Frontend: `http://127.0.0.1:5201`
- Backend docs: `http://127.0.0.1:5200/docs`
- Stop: `cd ~/deo-rag-setup/deo-rag/deo-rag && bash stop.sh`
- Start again: `cd ~/deo-rag-setup/deo-rag/deo-rag && bash script.sh --detach`

## Windows

Create a new folder: `C:\data\code`
Then open Command Prompt in that folder.

Run:

```
curl -o setup.bat https://raw.githubusercontent.com/deo-delhi/deo-rag/main/setup-deo-rag.bat && setup.bat
```

The script may stop after Docker installation due to a Docker/WSL-related error.
Simply reboot your system and re-run the above command in the same folder.

The installation will complete eventually. It may take around 20–60 minutes, depending on your system.

