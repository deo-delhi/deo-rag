#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"
BACKEND_PORT="${BACKEND_PORT:-5200}"
FRONTEND_PORT="${FRONTEND_PORT:-5201}"
POSTGRES_PORT="${POSTGRES_PORT:-5202}"
DOCKER=(docker)

configure_docker_command() {
  if docker info >/dev/null 2>&1; then
    DOCKER=(docker)
    return
  fi

  if command -v sudo >/dev/null 2>&1 && sudo -n docker info >/dev/null 2>&1; then
    DOCKER=(sudo docker)
    return
  fi

  DOCKER=(docker)
}

kill_port() {
  local port="$1"
  local label="$2"

  if command -v lsof >/dev/null 2>&1; then
    local pids
    pids="$(lsof -tiTCP:"$port" -sTCP:LISTEN 2>/dev/null || true)"
    if [[ -n "$pids" ]]; then
      echo "Stopping $label process on port $port"
      kill $pids 2>/dev/null || true
    fi
  elif command -v ss >/dev/null 2>&1; then
    local pids
    pids="$(ss -ltnp "sport = :$port" 2>/dev/null | awk -F',' '/pid=/{gsub(/pid=|[^0-9]/, "", $2); if ($2 != "") print $2}' | sort -u)"
    if [[ -n "$pids" ]]; then
      echo "Stopping $label process on port $port"
      kill $pids 2>/dev/null || true
    fi
  fi
}

main() {
  configure_docker_command

  echo "Stopping compose services..."
  "${DOCKER[@]}" compose -f "$COMPOSE_FILE" down --remove-orphans || true

  kill_port "$BACKEND_PORT" "backend"
  kill_port "$FRONTEND_PORT" "frontend"

  if command -v lsof >/dev/null 2>&1 && lsof -iTCP:"$POSTGRES_PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "Port $POSTGRES_PORT is still in use by another process."
  fi

  echo "All project services stopped."
}

main "$@"