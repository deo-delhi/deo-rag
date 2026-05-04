#!/usr/bin/env bash

set -euo pipefail

FORCE_REINGEST=0
SKIP_SAMPLE_INGEST=0
SKIP_MODEL_PULL=0
SKIP_START=0

for arg in "$@"; do
  case "$arg" in
    --force-reingest) FORCE_REINGEST=1 ;;
    --skip-sample-ingest) SKIP_SAMPLE_INGEST=1 ;;
    --skip-model-pull) SKIP_MODEL_PULL=1 ;;
    --no-start) SKIP_START=1 ;;
    -h|--help)
      cat <<'EOF'
Usage: bash install-and-run.sh [options]

Options:
  --force-reingest       Re-index bundled sample PDFs even if chunks already exist.
  --skip-sample-ingest   Install and start the stack, but do not ingest sample PDFs.
  --skip-model-pull      Skip Ollama model pulls.
  --no-start             Install/configure only; do not start the stack.
EOF
      exit 0
      ;;
    *) echo "Unknown option: $arg" >&2; exit 1 ;;
  esac
done

SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ "$(uname -s)" != "Linux" ]]; then
  echo "This installer must be run from Ubuntu or WSL Ubuntu." >&2
  exit 1
fi

if [[ -f "$SCRIPT_ROOT/deo-rag/docker-compose.yml" ]]; then
  REPO_ROOT="$SCRIPT_ROOT"
  APP_ROOT="$SCRIPT_ROOT/deo-rag"
elif [[ -f "$SCRIPT_ROOT/docker-compose.yml" ]]; then
  APP_ROOT="$SCRIPT_ROOT"
  REPO_ROOT="$(cd "$SCRIPT_ROOT/.." && pwd)"
else
  echo "Cannot locate deo-rag/docker-compose.yml. Run this from the repository root." >&2
  exit 1
fi

VENV_DIR="$REPO_ROOT/.venv"
VENV_PY="$VENV_DIR/bin/python"
BACKEND_BASE="${BACKEND_BASE:-http://127.0.0.1:5200}"
FRONTEND_URL="${FRONTEND_URL:-http://127.0.0.1:5201}"
SAMPLE_LIBRARY="${SAMPLE_LIBRARY:-court-cases-sample}"
DEO_FILES_DIR="$REPO_ROOT/deo-files"

is_wsl() {
  grep -qiE "microsoft|wsl" /proc/version 2>/dev/null || [[ -n "${WSL_INTEROP:-}" || -n "${WSL_DISTRO_NAME:-}" ]]
}

need_sudo() {
  [[ "${EUID:-$(id -u)}" -ne 0 ]]
}

sudo_cmd() {
  if need_sudo; then
    sudo "$@"
  else
    "$@"
  fi
}

log() {
  printf '\n[%s] %s\n' "$1" "$2"
}

apt_install() {
  sudo_cmd env DEBIAN_FRONTEND=noninteractive apt-get install -y "$@"
}

install_nodejs() {
  local major=0
  if command -v node >/dev/null 2>&1; then
    major="$(node -p "parseInt(process.versions.node.split('.')[0], 10)" 2>/dev/null || echo 0)"
  fi
  if [[ "$major" -ge 18 ]]; then
    return
  fi

  log node "Installing Node.js 20.x from NodeSource ..."
  curl -fsSL https://deb.nodesource.com/setup_20.x | sudo_cmd bash -
  apt_install nodejs
}

install_compose_plugin_manually() {
  local arch
  arch="$(uname -m)"
  case "$arch" in
    x86_64|amd64) arch="x86_64" ;;
    aarch64|arm64) arch="aarch64" ;;
    *)
      echo "Unsupported architecture for Docker Compose plugin auto-install: $arch" >&2
      return 1
      ;;
  esac

  log docker "Installing Docker Compose v2 plugin manually ..."
  local plugin_dir="/usr/local/lib/docker/cli-plugins"
  sudo_cmd mkdir -p "$plugin_dir"
  curl -fL "https://github.com/docker/compose/releases/latest/download/docker-compose-linux-$arch" \
    -o /tmp/docker-compose
  sudo_cmd install -m 0755 /tmp/docker-compose "$plugin_dir/docker-compose"
  rm -f /tmp/docker-compose
}

install_system_packages() {
  log apt "Installing Ubuntu dependencies ..."
  sudo_cmd apt-get update
  apt_install \
    ca-certificates curl git gnupg lsb-release lsof \
    build-essential pkg-config python3 python3-dev python3-venv python3-pip \
    libgl1 libglib2.0-0 libmagic1 poppler-utils tesseract-ocr \
    docker.io

  install_nodejs

  if ! docker compose version >/dev/null 2>&1; then
    sudo_cmd apt-get update
    apt_install docker-compose-plugin || apt_install docker-compose-v2 || apt_install docker-compose || true
  fi
  if ! docker compose version >/dev/null 2>&1; then
    install_compose_plugin_manually
  fi
  if ! docker compose version >/dev/null 2>&1; then
    echo "Docker Compose v2 is not available after package install. Install docker-compose-plugin and re-run." >&2
    exit 1
  fi
}

start_docker() {
  log docker "Starting Docker engine ..."
  if docker info >/dev/null 2>&1; then
    return
  fi

  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files docker.service >/dev/null 2>&1; then
    sudo_cmd systemctl enable --now docker || true
  fi

  if ! docker info >/dev/null 2>&1 && command -v service >/dev/null 2>&1; then
    sudo_cmd service docker start || true
  fi

  if ! docker info >/dev/null 2>&1 && sudo_cmd docker info >/dev/null 2>&1; then
    if need_sudo; then
      sudo_cmd usermod -aG docker "$USER" || true
      echo "[docker] Docker works via sudo. You may need to open a new Ubuntu shell for non-sudo docker access."
    fi
    return
  fi

  if ! docker info >/dev/null 2>&1; then
    if is_wsl; then
      echo "Docker did not start inside WSL. Enable systemd in /etc/wsl.conf or install Docker Desktop with WSL integration, then re-run." >&2
    else
      echo "Docker did not start. Check: sudo systemctl status docker" >&2
    fi
    exit 1
  fi
}

install_ollama() {
  if command -v ollama >/dev/null 2>&1; then
    return
  fi

  log ollama "Installing Ollama ..."
  curl -fsSL https://ollama.com/install.sh | sh
}

start_ollama() {
  if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    return
  fi

  log ollama "Starting Ollama ..."
  if command -v systemctl >/dev/null 2>&1 && systemctl list-unit-files ollama.service >/dev/null 2>&1; then
    sudo_cmd systemctl enable --now ollama || true
  fi

  if ! curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
    mkdir -p "$APP_ROOT/.run-logs"
    nohup ollama serve >"$APP_ROOT/.run-logs/ollama.log" 2>"$APP_ROOT/.run-logs/ollama.log.err" &
    sleep 3
  fi

  for _ in $(seq 1 30); do
    if curl -fsS http://127.0.0.1:11434/api/tags >/dev/null 2>&1; then
      return
    fi
    sleep 2
  done

  echo "Ollama did not become reachable at http://127.0.0.1:11434." >&2
  exit 1
}

env_get() {
  local key="$1"
  local file="$APP_ROOT/.env"
  if [[ -f "$file" ]]; then
    grep -E "^${key}=" "$file" | tail -n 1 | cut -d= -f2- || true
  fi
}

ensure_env_key() {
  local key="$1"
  local value="$2"
  local file="$APP_ROOT/.env"
  if grep -qE "^${key}=" "$file"; then
    return
  fi
  printf '%s=%s\n' "$key" "$value" >>"$file"
}

configure_env() {
  log env "Preparing $APP_ROOT/.env ..."
  if [[ ! -f "$APP_ROOT/.env" ]]; then
    cp "$APP_ROOT/.env.example" "$APP_ROOT/.env"
  fi

  ensure_env_key LANGCHAIN_TRACING_V2 false
  ensure_env_key LLM_PROVIDER ollama
  ensure_env_key LLM_MODEL llama3.2:latest
  ensure_env_key OLLAMA_BASE_URL http://127.0.0.1:11434
  ensure_env_key EMBEDDING_PROVIDER huggingface
  ensure_env_key EMBEDDING_MODEL BAAI/bge-small-en
  ensure_env_key INGEST_CHUNK_SIZE 1000
  ensure_env_key INGEST_CHUNK_OVERLAP 150
  ensure_env_key INGEST_EMBED_BATCH_SIZE 32
  ensure_env_key INGEST_MAX_WORKERS 0
  ensure_env_key INGEST_HF_ENCODE_BATCH_SIZE 0
  ensure_env_key RETRIEVER_TOP_K 4
  ensure_env_key OLLAMA_KEEP_ALIVE 24h
  ensure_env_key DATABASE_URL postgresql+psycopg2://admin:admin123@localhost:5202/deorag
  ensure_env_key COLLECTION_NAME deo_docs
  ensure_env_key DOCUMENTS_DIR ../documents
}

create_venv_and_install_backend() {
  log python "Creating/updating Python virtual environment ..."
  if [[ ! -x "$VENV_PY" ]]; then
    python3 -m venv "$VENV_DIR"
  fi

  "$VENV_PY" -m pip install --upgrade pip wheel setuptools
  "$VENV_PY" -m pip install -r "$APP_ROOT/backend/requirements.txt"
  "$VENV_PY" -m pip install --upgrade "numpy<2.4"
}

probe_torch_cuda() {
  "$VENV_PY" - <<'PY'
import sys
try:
    import torch
    ok = bool(torch.cuda.is_available())
    if ok:
        major, minor = torch.cuda.get_device_capability(0)
        ok = (major, minor) >= (3, 7)
    print("true" if ok else "false")
except Exception:
    print("false")
PY
}

install_cuda_pytorch_if_possible() {
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    if is_wsl; then
      echo "[gpu] nvidia-smi not found in WSL. Install/update the NVIDIA Windows driver with WSL CUDA support, then re-run."
    else
      echo "[gpu] nvidia-smi not found. Skipping CUDA PyTorch; CPU wheels remain installed."
    fi
    return
  fi

  log gpu "NVIDIA GPU detected; installing CUDA PyTorch wheels when supported ..."
  nvidia-smi || true

  "$VENV_PY" -m pip uninstall -y torch torchvision torchaudio >/dev/null 2>&1 || true

  local ok=0
  for cu_tag in cu126 cu124 cu121 cu118; do
    local url="https://download.pytorch.org/whl/$cu_tag"
    echo "[gpu] Trying PyTorch index: $url"
    if "$VENV_PY" -m pip install --upgrade --force-reinstall \
      --disable-pip-version-check --no-input --retries 5 --timeout 120 \
      --index-url "$url" torch torchvision torchaudio; then
      if [[ "$(probe_torch_cuda)" == "true" ]]; then
        echo "[gpu] CUDA PyTorch is usable with $cu_tag."
        ok=1
        break
      fi
    fi
    echo "[gpu] $cu_tag did not produce a usable CUDA runtime; trying next."
  done

  if [[ "$ok" -ne 1 ]]; then
    echo "[gpu] CUDA PyTorch is not usable on this GPU/driver. Falling back to CPU PyTorch."
    echo "[gpu] On WSL, update the Windows NVIDIA driver first. On bare Ubuntu, install a current NVIDIA driver."
    "$VENV_PY" -m pip install --upgrade --force-reinstall torch torchvision torchaudio
  fi

  "$VENV_PY" -m pip install --upgrade "numpy<2.4"
}

install_frontend() {
  log frontend "Installing frontend dependencies and building production bundle ..."
  npm --prefix "$APP_ROOT/frontend" install --no-audit --no-fund
  npm --prefix "$APP_ROOT/frontend" run build
}

copy_sample_pdfs() {
  local docs_lib="$APP_ROOT/documents/$SAMPLE_LIBRARY"
  mkdir -p "$docs_lib"

  if [[ -d "$DEO_FILES_DIR" ]]; then
    local count=0
    while IFS= read -r -d '' pdf; do
      cp -f "$pdf" "$docs_lib/"
      count=$((count + 1))
    done < <(find "$DEO_FILES_DIR" -maxdepth 1 -type f -iname "*.pdf" -print0)
    echo "[pdfs] Copied $count sample PDFs into documents/$SAMPLE_LIBRARY."
  else
    echo "[pdfs] No $DEO_FILES_DIR directory found; upload PDFs through the UI or place them under $docs_lib."
  fi
}

pull_models() {
  if [[ "$SKIP_MODEL_PULL" -eq 1 ]]; then
    return
  fi

  local llm_model
  llm_model="$(env_get LLM_MODEL)"
  llm_model="${llm_model:-llama3.2:latest}"
  log ollama "Pulling chat model: $llm_model"
  ollama pull "$llm_model"

  local emb_provider emb_model
  emb_provider="$(env_get EMBEDDING_PROVIDER)"
  emb_model="$(env_get EMBEDDING_MODEL)"
  if [[ "${emb_provider,,}" == "ollama" && -n "$emb_model" ]]; then
    log ollama "Pulling embedding model: $emb_model"
    ollama pull "$emb_model"
  fi
}

wait_backend() {
  for _ in $(seq 1 120); do
    if curl -fsS "$BACKEND_BASE/health" >/dev/null 2>&1; then
      return
    fi
    sleep 3
  done
  echo "Backend did not become healthy. See $APP_ROOT/.run-logs/backend.log" >&2
  exit 1
}

configure_running_app() {
  wait_backend

  log app "Setting default runtime options and sample library ..."
  curl -fsS -X PUT "$BACKEND_BASE/settings" \
    -H "Content-Type: application/json" \
    -d '{"llm_model":"'"$(env_get LLM_MODEL)"'","retriever_top_k":4,"ollama_num_predict":512,"ollama_num_ctx":4096}' >/dev/null || true

  curl -fsS -X POST "$BACKEND_BASE/knowledge-bases" \
    -H "Content-Type: application/json" \
    -d '{"knowledge_base":"'"$SAMPLE_LIBRARY"'"}' >/dev/null || true
  curl -fsS -X PUT "$BACKEND_BASE/knowledge-bases/active" \
    -H "Content-Type: application/json" \
    -d '{"knowledge_base":"'"$SAMPLE_LIBRARY"'"}' >/dev/null || true

  curl -fsS -X POST "$BACKEND_BASE/hardware/recalibrate" >/dev/null || true
}

retriever_has_chunks() {
  curl -fsS -X POST "$BACKEND_BASE/debug/retrieve" \
    -H "Content-Type: application/json" \
    -d '{"question":"overview","knowledge_base":"'"$SAMPLE_LIBRARY"'","query_scope":"active"}' \
    | grep -Eq '"retrieved_count"[[:space:]]*:[[:space:]]*[1-9]'
}

start_ingest_and_wait() {
  if [[ "$SKIP_SAMPLE_INGEST" -eq 1 ]]; then
    return
  fi
  if [[ "$FORCE_REINGEST" -ne 1 ]] && retriever_has_chunks; then
    echo "[ingest] Vector store already has chunks for $SAMPLE_LIBRARY; skipping. Use --force-reingest to redo."
    return
  fi

  log ingest "Starting sample ingestion for $SAMPLE_LIBRARY ..."
  curl -fsS -X POST "$BACKEND_BASE/ingest/start" \
    -H "Content-Type: application/json" \
    -d '{"knowledge_base":"'"$SAMPLE_LIBRARY"'","replace_collection":true,"chunk_size":1000,"chunk_overlap":150}' >/dev/null

  local encoded
  encoded="$(python3 - <<PY
from urllib.parse import quote
print(quote("$SAMPLE_LIBRARY"))
PY
)"

  for _ in $(seq 1 3600); do
    local status
    status="$(curl -fsS "$BACKEND_BASE/ingest/status?knowledge_base=$encoded" || true)"
    if echo "$status" | grep -q '"status":"completed"'; then
      echo "[ingest] Completed."
      return
    fi
    if echo "$status" | grep -q '"status":"failed"'; then
      echo "$status" >&2
      exit 1
    fi
    sleep 4
  done

  echo "Ingest timed out. Check the UI or backend logs for progress." >&2
  exit 1
}

start_stack() {
  log stack "Restarting DEO RAG services ..."
  bash "$APP_ROOT/stop.sh" || true
  VENV_PY="$VENV_PY" bash "$APP_ROOT/script.sh" --detach
}

main() {
  if is_wsl; then
    echo "[host] WSL Ubuntu detected. This script installs Linux-side dependencies; NVIDIA drivers must be installed on Windows."
  else
    echo "[host] Bare-metal/VM Ubuntu detected."
  fi

  install_system_packages
  start_docker
  install_ollama
  start_ollama
  configure_env
  create_venv_and_install_backend
  install_cuda_pytorch_if_possible
  install_frontend
  copy_sample_pdfs
  pull_models

  if [[ "$SKIP_START" -eq 1 ]]; then
    echo "[done] Installed/configured. Start later with: cd \"$APP_ROOT\" && bash script.sh --detach"
    return
  fi

  start_stack
  configure_running_app
  start_ingest_and_wait

  echo ""
  echo "Done."
  echo "  Frontend: $FRONTEND_URL"
  echo "  Backend : $BACKEND_BASE/docs"
  echo "  Stop    : cd \"$APP_ROOT\" && bash stop.sh"
}

main "$@"
