#!/usr/bin/env bash

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"
LOG_DIR="$ROOT_DIR/.run-logs"
BACKEND_HOST="${BACKEND_HOST:-0.0.0.0}"
BACKEND_PORT="${BACKEND_PORT:-5200}"
FRONTEND_HOST="${FRONTEND_HOST:-0.0.0.0}"
FRONTEND_PORT="${FRONTEND_PORT:-5201}"
VENV_PY="${VENV_PY:-$ROOT_DIR/../.venv/bin/python}"
POSTGRES_PORT="${POSTGRES_PORT:-5202}"
CHECK_HOST="${CHECK_HOST:-127.0.0.1}"

detect_access_host() {
  if [[ -n "${PUBLIC_HOST:-}" ]]; then
    printf '%s\n' "$PUBLIC_HOST"
    return
  fi

  if command -v hostname >/dev/null 2>&1; then
    local detected_host
    detected_host="$(hostname -I 2>/dev/null | awk '{print $1}')"
    if [[ -n "$detected_host" ]]; then
      printf '%s\n' "$detected_host"
      return
    fi
  fi

  printf '%s\n' "127.0.0.1"
}

backend_pid=""
frontend_pid=""

cleanup() {
  local exit_code=$?

  trap - EXIT INT TERM

  if [[ -n "${backend_pid}" ]] && kill -0 "$backend_pid" 2>/dev/null; then
    kill "$backend_pid" 2>/dev/null || true
  fi

  if [[ -n "${frontend_pid}" ]] && kill -0 "$frontend_pid" 2>/dev/null; then
    kill "$frontend_pid" 2>/dev/null || true
  fi

  wait "${backend_pid:-}" 2>/dev/null || true
  wait "${frontend_pid:-}" 2>/dev/null || true

  exit "$exit_code"
}

ensure_command() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "Missing required command: $1" >&2
    exit 1
  fi
}

ensure_port_free() {
  local port="$1"
  local name="$2"

  if command -v lsof >/dev/null 2>&1; then
    if lsof -iTCP:"$port" -sTCP:LISTEN -t >/dev/null 2>&1; then
      echo "$name port $port is already in use. Stop the existing process first." >&2
      exit 1
    fi
  elif command -v ss >/dev/null 2>&1; then
    if ss -ltn "sport = :$port" | grep -q LISTEN; then
      echo "$name port $port is already in use. Stop the existing process first." >&2
      exit 1
    fi
  fi
}

wait_for_http() {
  local url="$1"
  local label="$2"
  local attempts=60

  for _ in $(seq 1 "$attempts"); do
    if curl -fsS "$url" >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  echo "Timed out waiting for $label at $url" >&2
  return 1
}

start_postgres() {
  echo "Starting PostgreSQL..."
  docker compose -f "$COMPOSE_FILE" up -d postgres

  echo "Waiting for PostgreSQL to be ready..."
  for _ in $(seq 1 60); do
    if docker compose -f "$COMPOSE_FILE" exec -T postgres pg_isready -U admin -d deorag >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  echo "PostgreSQL did not become ready in time." >&2
  exit 1
}

start_backend() {
  echo "Starting backend..."
  (
    cd "$ROOT_DIR"
    exec "$VENV_PY" -m uvicorn backend.app:app --host "$BACKEND_HOST" --port "$BACKEND_PORT" --app-dir "$ROOT_DIR"
  ) >"$LOG_DIR/backend.log" 2>&1 &
  backend_pid=$!
}

start_frontend() {
  echo "Starting frontend..."
  (
    cd "$FRONTEND_DIR"
    exec npm run dev -- --host "$FRONTEND_HOST" --port "$FRONTEND_PORT"
  ) >"$LOG_DIR/frontend.log" 2>&1 &
  frontend_pid=$!
}

main() {
  if [[ "${1:-start}" != "start" ]]; then
    echo "Usage: $0 [start]" >&2
    exit 1
  fi

  ensure_command docker
  ensure_command npm
  ensure_command curl

  if [[ ! -f "$ROOT_DIR/.env" ]]; then
    echo "Missing .env file at $ROOT_DIR/.env" >&2
    exit 1
  fi

  if command -v ollama >/dev/null 2>&1; then
    echo "Pulling the latest llama3.2 model in Ollama (this may take a while if not cached)..."
    ollama pull llama3.2:latest || true
  else
    echo "Ollama is not installed or not in PATH, skipping model pull."
  fi

  if [[ ! -x "$VENV_PY" ]]; then
    echo "Python executable not found at $VENV_PY" >&2
    exit 1
  fi

  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    echo "Installing frontend dependencies..."
    npm --prefix "$FRONTEND_DIR" install
  fi

  mkdir -p "$LOG_DIR"

  ensure_port_free "$BACKEND_PORT" "Backend"
  ensure_port_free "$FRONTEND_PORT" "Frontend"
  ensure_port_free "$POSTGRES_PORT" "PostgreSQL"

  trap cleanup EXIT INT TERM

  start_postgres
  start_backend
  start_frontend

  wait_for_http "http://$CHECK_HOST:$BACKEND_PORT/health" "backend health endpoint"
  wait_for_http "http://$CHECK_HOST:$FRONTEND_PORT" "frontend dev server"

  ACCESS_HOST="$(detect_access_host)"

  echo ""
  echo "Stack is running:"
  echo "  Backend:  http://$ACCESS_HOST:$BACKEND_PORT"
  echo "  Frontend: http://$ACCESS_HOST:$FRONTEND_PORT"
  echo "  Logs:     $LOG_DIR/backend.log and $LOG_DIR/frontend.log"
  echo ""
  echo "Press Ctrl+C to stop everything."

  wait -n "$backend_pid" "$frontend_pid"
  echo "A service stopped. Shutting down the rest..."
}

main "$@"
