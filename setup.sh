#!/usr/bin/env bash
# IDO SKILLS News — build & start script
# Usage:
#   bash ./setup.sh build       — create venv, install deps
#   bash ./setup.sh start       — start Flask/Gunicorn web service
#   bash ./setup.sh start-bot   — start Telegram bot worker
set -Eeuo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
VENV_DIR="$ROOT_DIR/.venv"
MODE="${1:-start}"

log() {
  printf '[setup] %s\n' "$*"
}

detect_python() {
  for bin in python3 python python3.12 python3.11 python3.10; do
    if command -v "$bin" >/dev/null 2>&1; then
      echo "$bin"
      return
    fi
  done
  log "ERROR: Python 3.10+ is required."
  exit 1
}

PYTHON_BIN="$(detect_python)"

bootstrap() {
  log "Python: $($PYTHON_BIN --version)"
  log "Preparing virtual environment at $VENV_DIR"

  if [[ ! -d "$VENV_DIR" ]]; then
    "$PYTHON_BIN" -m venv "$VENV_DIR"
  fi

  # shellcheck disable=SC1091
  source "$VENV_DIR/bin/activate"

  pip install --upgrade pip setuptools wheel --quiet
  pip install -r "$BACKEND_DIR/requirements.txt" --quiet

  # Create required directories
  mkdir -p \
    "$BACKEND_DIR/instance" \
    "$BACKEND_DIR/logs" \
    "$ROOT_DIR/instance" \
    "$ROOT_DIR/logs"

  log "Build complete."
}

activate_venv() {
  if [[ -f "$VENV_DIR/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "$VENV_DIR/bin/activate"
  else
    log "venv not found — running bootstrap first"
    bootstrap
  fi
}

# Export all runtime env vars with safe defaults
export_env() {
  export PORT="${PORT:-5000}"
  export BACKEND_PORT="${BACKEND_PORT:-$PORT}"
  export DEBUG="${DEBUG:-false}"
  export PYTHONUNBUFFERED=1
  export PYTHONPATH="$BACKEND_DIR${PYTHONPATH:+:$PYTHONPATH}"

  # Database
  export DATABASE_URL="${DATABASE_URL:-sqlite:///database.db}"
  export SECRET_KEY="${SECRET_KEY:-change-this-in-production}"
  export AUTH_TOKEN_SALT="${AUTH_TOKEN_SALT:-ido-skills-auth}"
  export AUTH_TOKEN_MAX_AGE="${AUTH_TOKEN_MAX_AGE:-604800}"

  # AI / OpenRouter (Gemini 2.0)
  export OPENROUTER_API_KEY="${OPENROUTER_API_KEY:-}"
  export OPENROUTER_BASE_URL="${OPENROUTER_BASE_URL:-https://openrouter.ai/api/v1}"
  export OPENROUTER_MODEL="${OPENROUTER_MODEL:-google/gemini-2.0-flash-001}"
  export TAVILY_API_KEY="${TAVILY_API_KEY:-}"

  # App metadata
  export APP_HTTP_TITLE="${APP_HTTP_TITLE:-IDO-SKILLS-News}"
  export APP_SITE_URL="${APP_SITE_URL:-https://idoskillsnews.local}"
  export CORS_ORIGINS="${CORS_ORIGINS:-*}"
  export NEWS_THRESHOLD="${NEWS_THRESHOLD:-6}"

  # Telegram (optional)
  export TELEGRAM_BOT_TOKEN="${TELEGRAM_BOT_TOKEN:-}"
  export TELEGRAM_BOT_NAME="${TELEGRAM_BOT_NAME:-IDO SKILLS News Bot}"
  export TELEGRAM_BOT_TIMEOUT="${TELEGRAM_BOT_TIMEOUT:-30}"
  export BACKEND_PUBLIC_URL="${BACKEND_PUBLIC_URL:-}"
}

start_app() {
  activate_venv
  export_env

  cd "$BACKEND_DIR"

  # Number of gunicorn workers — Railway recommends 2–4
  WORKERS="${GUNICORN_WORKERS:-2}"
  THREADS="${GUNICORN_THREADS:-4}"
  # AI news endpoint can take up to 50 s (Gemini + external RSS fetch)
  TIMEOUT="${GUNICORN_TIMEOUT:-120}"

  log "Starting web service on 0.0.0.0:${PORT} (workers=${WORKERS}, threads=${THREADS}, timeout=${TIMEOUT}s)"

  exec gunicorn \
    --bind "0.0.0.0:${PORT}" \
    --workers "$WORKERS" \
    --threads "$THREADS" \
    --timeout "$TIMEOUT" \
    --keep-alive 5 \
    --access-logfile - \
    --error-logfile - \
    --log-level info \
    app:app
}

start_bot() {
  activate_venv
  export_env

  cd "$BACKEND_DIR"

  log "Starting Telegram bot worker"
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
