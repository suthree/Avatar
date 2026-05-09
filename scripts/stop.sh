#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PIDFILE="$ROOT/run/jarvis-stapp.pid"

if [[ ! -f "$PIDFILE" ]]; then
  echo "Jarvis not running (no pidfile)."
  exit 0
fi
pid="$(cat "$PIDFILE")"
if kill -0 "$pid" 2>/dev/null; then
  kill "$pid"
  for _ in $(seq 1 20); do
    sleep 0.5
    if ! kill -0 "$pid" 2>/dev/null; then break; fi
  done
  if kill -0 "$pid" 2>/dev/null; then
    kill -TERM "$pid" 2>/dev/null || true
  fi
  echo "Jarvis stopped: pid=$pid"
else
  echo "Jarvis process already dead: pid=$pid"
fi
rm -f "$PIDFILE"
