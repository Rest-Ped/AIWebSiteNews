#!/usr/bin/env bash
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
VENV_DIR="$ROOT_DIR/.venv"
MODE="${1:-start}"

log() {
  printf '[setup] %s\n' "$*"
}

detect_python() {
  if command -v python3 >/dev/null 2>&1; then
    echo "python3"
    return
  fi

  if command -v python >/dev/null 2>&1; then
    echo "python"
    return
  fi

  log "Python 3 is required to deploy this project."
  exit 1
}

PYTHON_BIN="$(detect_python)"

bootstrap() {
  log "Preparing virtual environment"

  if [[ ! -d "$VENV_DIR" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"

  python -m pip install --upgrade pip setuptools wheel
  python -m pip install -r "$BACKEND_DIR/requirements.txt"

  mkdir -p "$BACKEND_DIR/instance" "$BACKEND_DIR/logs" "$ROOT_DIR/instance" "$ROOT_DIR/logs"
}

activate_venv() {
  if [[ ! -f "$VENV_DIR/bin/activate" ]]; then
    bootstrap
    return
  fi

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"
}

start_app() {
  activate_venv

  export PORT="${PORT:-5000}"
  export BACKEND_PORT="${BACKEND_PORT:-$PORT}"
  export DEBUG="${DEBUG:-false}"
  export SECRET_KEY="${SECRET_KEY:-change-this-in-production}"
  export DATABASE_URL="${DATABASE_URL:-sqlite:///database.db}"
  export PYTHONUNBUFFERED=1
  export PYTHONPATH="$BACKEND_DIR${PYTHONPATH:+:$PYTHONPATH}"

  cd "$BACKEND_DIR"

  log "Starting Railway web service on 0.0.0.0:${PORT}"
  exec gunicorn \
    --bind "0.0.0.0:${PORT}" \
    --workers "${GUNICORN_WORKERS:-2}" \
    --threads "${GUNICORN_THREADS:-4}" \
    --timeout "${GUNICORN_TIMEOUT:-120}" \
    app:app
}

start_bot() {
  activate_venv

  export PYTHONUNBUFFERED=1
  export PYTHONPATH="$BACKEND_DIR${PYTHONPATH:+:$PYTHONPATH}"

  cd "$BACKEND_DIR"

  log "Starting Railway bot worker"
  exec python telegram_bot.py
}

case "$MODE" in
  build)
    bootstrap
    ;;
  start)
    start_app
    ;;
  start-bot)
    start_bot
    ;;
  *)
    log "Usage: bash ./setup.sh [build|start|start-bot]"
    exit 1
    ;;
esac
