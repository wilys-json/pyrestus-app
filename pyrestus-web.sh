#!/usr/bin/env bash
# Pyrestus Web launcher
# Usage: ./pyrestus-web.sh [start|stop|restart|status|logs|open]
#        ./pyrestus-web.sh          (no argument -> interactive menu)
set -Eeuo pipefail

# ------------------------------------------------------------- config
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8080}"
URL="http://$HOST:$PORT"
PID_FILE="$ROOT/.pyrestus-web.pid"
LOG_FILE="$ROOT/.pyrestus-web.log"
PYTHON="$ROOT/.venv/bin/python"
WEB_BUILD="$ROOT/app/build/web"
APP_MODULE="app.backend.app.main:app"

# ------------------------------------------------------------- helpers
say()  { printf '%s\n' "$*"; }
die()  { printf 'Error: %s\n' "$*" >&2; exit 1; }

is_running() {
  [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

is_healthy() {
  curl -fsS "$URL/api/health" >/dev/null 2>&1
}

open_browser() {
  if command -v xdg-open >/dev/null; then xdg-open "$URL" >/dev/null 2>&1 &
  elif command -v open >/dev/null;   then open "$URL" >/dev/null 2>&1
  else say "Open $URL in your browser."
  fi
}

# ------------------------------------------------------------- actions
do_start() {
  if is_running; then
    say "Pyrestus Web is already running at $URL"
    return
  fi

  [[ -x "$PYTHON" && -d "$WEB_BUILD" ]] || die "Run ./setup-web.sh first."
  command -v curl >/dev/null || die "curl is required."

  say "Starting Pyrestus Web..."
  (
    cd "$ROOT"
    exec nohup "$PYTHON" -m uvicorn "$APP_MODULE" --host "$HOST" --port "$PORT"
  ) </dev/null >"$LOG_FILE" 2>&1 &
  echo $! >"$PID_FILE"

  # Wait up to 10 s for the health check
  for _ in {1..20}; do
    if is_healthy; then
      say "Pyrestus Web is ready at $URL"
      open_browser
      return
    fi
    is_running || break          # process died early, stop waiting
    sleep 0.5
  done

  rm -f "$PID_FILE"
  die "Start failed. Last log lines:
$(tail -n 15 "$LOG_FILE" 2>/dev/null)"
}

do_stop() {
  if ! is_running; then
    say "Pyrestus Web is not running."
    rm -f "$PID_FILE"
    return
  fi

  local pid; pid="$(cat "$PID_FILE")"
  kill "$pid" 2>/dev/null || true

  # Wait up to 5 s for a clean exit, then force it
  for _ in {1..10}; do
    kill -0 "$pid" 2>/dev/null || break
    sleep 0.5
  done
  kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true

  rm -f "$PID_FILE"
  say "Pyrestus Web stopped."
}

do_status() {
  if is_running; then
    say "Pyrestus Web is running (PID $(cat "$PID_FILE")) at $URL"
    is_healthy && say "Health check: OK" || say "Health check: not responding"
  else
    say "Pyrestus Web is not running."
  fi
}

do_logs() {
  [[ -f "$LOG_FILE" ]] || die "No log file yet ($LOG_FILE)."
  say "Showing logs (Ctrl+C to exit)..."
  tail -n 100 -f "$LOG_FILE"
}

do_open() {
  is_running || die "Pyrestus Web is not running. Start it first."
  open_browser
}

run_action() {
  case "$1" in
    start)   do_start ;;
    stop)    do_stop ;;
    restart) do_stop; do_start ;;
    status)  do_status ;;
    logs)    do_logs ;;
    open)    do_open ;;
    *)       say "Usage: $0 [start|stop|restart|status|logs|open]"; exit 2 ;;
  esac
}

# ------------------------------------------------------------- menu UI
menu_dialog() {
  # Uses whiptail/dialog if installed (nice boxed menu)
  local tool="$1" state="stopped"
  is_running && state="running"
  "$tool" --title "Pyrestus Web" \
    --menu "Status: $state   ($URL)\nChoose an option:" 17 60 7 \
    start   "Start the server" \
    stop    "Stop the server" \
    restart "Restart the server" \
    status  "Show status" \
    logs    "Follow the logs" \
    open    "Open in browser" \
    quit    "Exit" \
    3>&1 1>&2 2>&3
}

menu_plain() {
  # Fallback: simple numbered menu, works in any terminal
  local options=(start stop restart status logs open quit)
  local state="stopped"; is_running && state="running"
  say "" >&2
  say "=== Pyrestus Web ($state) - $URL ===" >&2
  PS3="Choose an option [1-${#options[@]}]: "
  select choice in "${options[@]}"; do
    [[ -n "${choice:-}" ]] && { echo "$choice"; return; }
    say "Invalid choice." >&2
  done
}

interactive() {
  local tool=""
  command -v whiptail >/dev/null && tool=whiptail
  [[ -z "$tool" ]] && command -v dialog >/dev/null && tool=dialog

  while true; do
    local choice
    if [[ -n "$tool" ]]; then
      choice="$(menu_dialog "$tool")" || exit 0   # Esc/Cancel -> exit
      clear
    else
      choice="$(menu_plain)" || exit 0
    fi

    [[ "$choice" == "quit" ]] && exit 0

    # Run the action, but don't let an error close the menu
    ( run_action "$choice" ) || true
    [[ "$choice" == "logs" ]] && continue
    read -rp $'\nPress Enter to return to the menu...' _
  done
}

# ------------------------------------------------------------- main
if [[ $# -eq 0 ]]; then
  interactive
else
  run_action "$1"
fi
