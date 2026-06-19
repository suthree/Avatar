#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${PORT:-18601}"
PIDFILE="$ROOT/run/jarvis-stapp.pid"
LOGFILE="$ROOT/logs/jarvis-stapp.log"

if [[ ! -f "$PIDFILE" ]]; then
  echo "Jarvis not running (no pidfile). port=$PORT"
  exit 1
fi
pid="$(cat "$PIDFILE")"
if kill -0 "$pid" 2>/dev/null; then
  echo "Jarvis running: pid=$pid port=$PORT"
  curl -Is "http://127.0.0.1:$PORT" | sed -n '1,5p' || true
  exit 0
else
  echo "Jarvis pidfile exists but process not alive: pid=$pid"
  echo "--- log tail ---"
  tail -n 40 "$LOGFILE" || true
  exit 2
fi
