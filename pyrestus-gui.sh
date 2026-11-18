#!/usr/bin/env bash
# Pyrestus Web - graphical launcher (double-click friendly)
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MAIN="$ROOT/pyrestus-web.sh"
LOG_FILE="$ROOT/.pyrestus-web.log"
TITLE="Pyrestus Web"
ACTIONS=("Start" "Stop" "Restart" "Status" "View logs" "Open in browser" "Quit")

# Apps launched by double-click get a minimal PATH
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

# ---------------------------------------------------------- pick a UI toolkit
if   [[ "$(uname)" == "Darwin" ]];     then UI=mac
elif command -v zenity  >/dev/null;    then UI=zenity
elif command -v kdialog >/dev/null;    then UI=kdialog
else UI=none
fi

# ---------------------------------------------------------- dialog helpers
ask() {   # $1 = prompt text; prints the chosen label, non-zero on cancel
  case "$UI" in
    mac)
      osascript - "$1" "$TITLE" "${ACTIONS[@]}" <<'EOF'
on run argv
  set p to item 1 of argv
  set t to item 2 of argv
  set opts to items 3 thru -1 of argv
  set r to choose from list opts with title t with prompt p default items {item 1 of opts}
  if r is false then error number -128
  return item 1 of r
end run
EOF
      ;;
    zenity)
      zenity --list --title="$TITLE" --text="$1" --column="Action" \
             --hide-header --width=360 --height=400 "${ACTIONS[@]}"
      ;;
    kdialog)
      local args=()
      for a in "${ACTIONS[@]}"; do args+=("$a" "$a"); done
      kdialog --title "$TITLE" --menu "$1" "${args[@]}"
      ;;
  esac
}

tell() {  # $1 = message
  case "$UI" in
    mac)
      osascript - "$1" "$TITLE" >/dev/null <<'EOF'
on run argv
  display dialog (item 1 of argv) with title (item 2 of argv) buttons {"OK"} default button "OK"
end run
EOF
      ;;
    zenity)  zenity --info --title="$TITLE" --no-markup --width=440 --text="$1" ;;
    kdialog) kdialog --title "$TITLE" --msgbox "$1" ;;
  esac
}

show_logs() {
  [[ -f "$LOG_FILE" ]] || { tell "No log file yet. Start the server first."; return; }
  case "$UI" in
    mac)     open -a Console "$LOG_FILE" ;;   # live-updating log viewer
    zenity)  tail -n 300 "$LOG_FILE" | zenity --text-info --title="$TITLE - logs" \
                                              --width=900 --height=600 ;;
    kdialog) kdialog --title "$TITLE - logs" --textbox "$LOG_FILE" 900 600 ;;
  esac
}

run() {   # run an action of the main script and show its output
  local out
  out="$("$MAIN" "$1" 2>&1)"
  tell "${out:-Done.}"
}

# ---------------------------------------------------------- main loop
[[ -x "$MAIN" ]] || chmod +x "$MAIN" 2>/dev/null || true
[[ -f "$MAIN" ]] || { echo "Cannot find $MAIN"; exit 1; }

# No GUI toolkit available: use the terminal menu instead
[[ "$UI" == "none" ]] && exec "$MAIN"

while true; do
  state="$("$MAIN" status 2>/dev/null | head -n 1)"
  choice="$(ask "${state}"$'\n\n'"Choose an action:")" || exit 0   # Cancel/close -> exit

  case "$choice" in
    "Start")           run start ;;
    "Stop")            run stop ;;
    "Restart")         run restart ;;
    "Status")          run status ;;
    "View logs")       show_logs ;;
    "Open in browser") run open ;;
    "Quit")            exit 0 ;;
    *)                 continue ;;   # nothing selected
  esac
done

