#!/usr/bin/env bash

set -euo pipefail

REPO_URL="${DEO_RAG_REPO_URL:-https://github.com/deo-delhi/deo-rag.git}"
BASE_DIR="${DEO_RAG_BASE_DIR:-$HOME/deo-rag-setup}"
INSTALL_DIR="${DEO_RAG_INSTALL_DIR:-$BASE_DIR/deo-rag}"

need_sudo() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    return 1
  fi
  return 0
}

sudo_cmd() {
  if need_sudo; then
    sudo "$@"
  else
    "$@"
  fi
}

ensure_bootstrap_tools() {
  if command -v git >/dev/null 2>&1 && command -v curl >/dev/null 2>&1; then
    return
  fi

  if ! command -v apt-get >/dev/null 2>&1; then
    echo "This installer supports Ubuntu / WSL Ubuntu systems with apt-get." >&2
    exit 1
  fi

  sudo_cmd apt-get update
  sudo_cmd env DEBIAN_FRONTEND=noninteractive apt-get install -y git curl ca-certificates
}

main() {
  if [[ "$(uname -s)" != "Linux" ]]; then
    echo "Run this from Ubuntu or WSL Ubuntu, not from Windows PowerShell/CMD." >&2
    exit 1
  fi

  ensure_bootstrap_tools
  mkdir -p "$BASE_DIR"

  if [[ -d "$INSTALL_DIR/.git" ]]; then
    echo "[setup] Updating existing clone at $INSTALL_DIR ..."
    git -C "$INSTALL_DIR" pull --ff-only
  else
    echo "[setup] Cloning $REPO_URL into $INSTALL_DIR ..."
    git clone "$REPO_URL" "$INSTALL_DIR"
  fi

  echo "[setup] Running Ubuntu/WSL installer ..."
  bash "$INSTALL_DIR/install-and-run.sh" "$@"
}

main "$@"
