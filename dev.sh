#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_DIR="$ROOT_DIR/logs"
PID_FILE="$LOG_DIR/dev.pid"
RUN_LOG="$LOG_DIR/dev_run.log"
PYTHON_BIN="$ROOT_DIR/.venv/bin/python"
HOST="127.0.0.1"

if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="python3"
fi

load_env() {
  if [[ ! -f "$ROOT_DIR/.env" && ! -f "$ROOT_DIR/.env.local" ]]; then
    echo "[dev] missing .env/.env.local (copy .env.example first)"
    exit 1
  fi

  set -a
  [[ -f "$ROOT_DIR/.env" ]] && source "$ROOT_DIR/.env"
  [[ -f "$ROOT_DIR/.env.local" ]] && source "$ROOT_DIR/.env.local"
  set +a
}

is_true() {
  local v="${1:-}"
  [[ "${v,,}" == "1" || "${v,,}" == "true" || "${v,,}" == "yes" || "${v,,}" == "on" ]]
}

mask() {
  local v="${1:-}"
  if [[ -z "$v" ]]; then
    echo ""
  elif [[ ${#v} -le 8 ]]; then
    echo "***"
  else
    echo "${v:0:4}***${v: -4}"
  fi
}

validate_env() {
  if is_true "${URL_CHECK_ENABLE_DINGDING:-true}" && [[ -z "${URL_CHECK_DINGDING_ACCESS_TOKEN:-}" ]]; then
    echo "[dev] invalid: URL_CHECK_DINGDING_ACCESS_TOKEN is empty while dingding enabled"
    exit 1
  fi

  if is_true "${URL_CHECK_ENABLE_MAIL:-false}" && [[ -z "${URL_CHECK_MAIL_RECEIVERS:-}" ]]; then
    echo "[dev] invalid: URL_CHECK_MAIL_RECEIVERS is empty while mail enabled"
    exit 1
  fi
}

show_config() {
  echo "[dev] config summary"
  echo "  alerts:   ${URL_CHECK_ENABLE_ALERTS:-true}"
  echo "  dingding: ${URL_CHECK_ENABLE_DINGDING:-true}"
  echo "  mail:     ${URL_CHECK_ENABLE_MAIL:-false}"
  echo "  report:   ${URL_CHECK_REPORT_ENABLED:-true}"
  echo "  port:     ${URL_CHECK_PORT:-4000}"
  echo "  token:    $(mask "${URL_CHECK_DINGDING_ACCESS_TOKEN:-}")"
  echo "  receivers:${URL_CHECK_MAIL_RECEIVERS:-}"
}

check_port() {
  local port="${URL_CHECK_PORT:-4000}"
  "$PYTHON_BIN" - <<PY
import socket
import sys

host = "${HOST}"
port = int("${port}")
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    s.bind((host, port))
except OSError:
    print(f"[dev] port {port} is already in use")
    sys.exit(1)
finally:
    s.close()
PY
}

start_service() {
  mkdir -p "$LOG_DIR"

  if [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "[dev] already running (pid=$(cat "$PID_FILE"))"
    exit 0
  fi

  check_port

  nohup "$PYTHON_BIN" "$ROOT_DIR/url_check.py" >"$RUN_LOG" 2>&1 &
  echo $! >"$PID_FILE"
  sleep 1

  if kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "[dev] started (pid=$(cat "$PID_FILE"))"
    echo "[dev] log: $RUN_LOG"
  else
    echo "[dev] failed to start, check: $RUN_LOG"
    exit 1
  fi
}

stop_service() {
  if [[ -f "$PID_FILE" ]]; then
    local pid
    pid="$(cat "$PID_FILE")"
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid"
      sleep 1
      echo "[dev] stopped pid=$pid"
    else
      echo "[dev] pid file exists but process not running"
    fi
    rm -f "$PID_FILE"
  else
    echo "[dev] not running"
  fi
}

smoke_test() {
  "$PYTHON_BIN" - <<PY
import json
import urllib.request
import os

port = int(os.getenv('URL_CHECK_PORT', '4000'))
base = f'http://127.0.0.1:{port}'

def get(url):
    with urllib.request.urlopen(url, timeout=5) as r:
        return r.read().decode('utf-8')

def post(url, payload):
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode('utf-8'),
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.read().decode('utf-8')

print('[dev] /health =>', get(base + '/health'))
print('[dev] /job/opt list_jobs =>', post(base + '/job/opt', {'list_jobs': 1}))
PY
}

usage() {
  cat <<'EOF'
Usage: ./dev.sh <command>

Commands:
  check   Load .env/.env.local and validate required variables
  up      Start local service with loaded env vars
  down    Stop local service started by this script
  test    Run API smoke tests (/health and list_jobs)
EOF
}

main() {
  local cmd="${1:-}"
  case "$cmd" in
    check)
      load_env
      validate_env
      show_config
      ;;
    up)
      load_env
      validate_env
      show_config
      start_service
      ;;
    down)
      stop_service
      ;;
    test)
      load_env
      smoke_test
      ;;
    *)
      usage
      exit 1
      ;;
  esac
}

main "$@"
