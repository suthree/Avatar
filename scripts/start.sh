#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-18601}"
PIDFILE="$ROOT/run/jarvis-stapp.pid"
LOGFILE="$ROOT/logs/jarvis-stapp.log"
APP="${APP:-frontends/stapp.py}"

mkdir -p "$ROOT/run" "$ROOT/logs"

if [[ -f "$PIDFILE" ]]; then
  oldpid="$(cat "$PIDFILE" 2>/dev/null || true)"
  if [[ -n "${oldpid:-}" ]] && kill -0 "$oldpid" 2>/dev/null; then
    echo "Jarvis already running: pid=$oldpid port=$PORT"
    exit 0
  fi
  rm -f "$PIDFILE"
fi

cd "$ROOT"
nohup "$ROOT/.venv/bin/python" -m streamlit run "$APP" \
  --server.port "$PORT" \
  --server.address 0.0.0.0 \
  --server.headless true \
  > "$LOGFILE" 2>&1 &
echo $! > "$PIDFILE"
echo "Jarvis started: pid=$(cat "$PIDFILE") port=$PORT log=$LOGFILE"
