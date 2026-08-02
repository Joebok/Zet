#!/bin/zsh
set -e

SCRIPT_DIR="${0:a:h}"
cd "$SCRIPT_DIR"

PORT=8080
HOST="0.0.0.0"

ZET_WEB_PID="$(lsof -nP -iTCP:${PORT} -sTCP:LISTEN -t 2>/dev/null | head -n 1 || true)"
if [[ -n "$ZET_WEB_PID" ]]; then
  echo "Zet Web is already listening on http://${HOST}:${PORT}/ with PID ${ZET_WEB_PID}."
  echo "Close that process before starting another instance."
  exit 0
fi

exec python3 -B -m zet.web.app --config config.toml --host "$HOST" --port "$PORT"
