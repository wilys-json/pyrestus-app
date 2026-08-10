#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; PID="$ROOT/.pyrestus-web.pid"; LOG="$ROOT/.pyrestus-web.log"
running(){ [[ -f "$PID" ]] && kill -0 "$(cat "$PID")" 2>/dev/null; }
start(){ if running;then echo 'Pyrestus Web is already running at http://127.0.0.1:8080';return;fi;[[ -x "$ROOT/.venv/bin/python" && -d "$ROOT/app/build/web" ]]||{ echo 'Run ./setup-web.sh first.';exit 1;};(cd "$ROOT";exec .venv/bin/python -m uvicorn app.backend.app.main:app --host 127.0.0.1 --port 8080)>"$LOG" 2>&1 & echo $! >"$PID";for i in {1..20};do curl -fsS http://127.0.0.1:8080/api/health >/dev/null&&{ echo 'Pyrestus Web is ready at http://127.0.0.1:8080';command -v xdg-open >/dev/null&&xdg-open http://127.0.0.1:8080 >/dev/null 2>&1||true;command -v open >/dev/null&&open http://127.0.0.1:8080 >/dev/null 2>&1||true;return;};sleep .5;done;echo "Start failed; see $LOG";}
stop(){ if running;then kill "$(cat "$PID")"||true;echo 'Pyrestus Web stopped.';else echo 'Pyrestus Web is not running.';fi;rm -f "$PID";}
case "${1:-}" in start)start;;stop)stop;;restart)stop;start;;status)running&&echo 'Pyrestus Web is running.'||echo 'Pyrestus Web is not running.';;logs)tail -n 100 -f "$LOG";;*)echo "Usage: $0 {start|stop|restart|status|logs}";exit 2;;esac
