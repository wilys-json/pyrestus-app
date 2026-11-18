#!/usr/bin/env bash
# Creates a double-clickable launcher for Pyrestus Web
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
GUI="$ROOT/pyrestus-gui.sh"
chmod +x "$GUI" "$ROOT/pyrestus-web.sh"

if [[ "$(uname)" == "Darwin" ]]; then
  # ---------- macOS: build a minimal .app bundle
  APP="$ROOT/Pyrestus Web.app"
  rm -rf "$APP"
  mkdir -p "$APP/Contents/MacOS"

  cat >"$APP/Contents/MacOS/launcher" <<EOF
#!/bin/bash
exec "$GUI"
EOF
  chmod +x "$APP/Contents/MacOS/launcher"

  cat >"$APP/Contents/Info.plist" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key>            <string>Pyrestus Web</string>
  <key>CFBundleIdentifier</key>      <string>local.pyrestus.web.launcher</string>
  <key>CFBundleExecutable</key>      <string>launcher</string>
  <key>CFBundlePackageType</key>     <string>APPL</string>
  <key>CFBundleVersion</key>         <string>1.0</string>
</dict>
</plist>
EOF
  echo "Created: $APP"
  echo "First launch: right-click it > Open (macOS asks once for unsigned apps)."

else
  # ---------- Linux: .desktop file (desktop icon + app menu entry)
  DESKTOP_FILE="$ROOT/Pyrestus Web.desktop"
  cat >"$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=Pyrestus Web
Comment=Start, stop and monitor Pyrestus Web
Exec="$GUI"
Path=$ROOT
Icon=utilities-terminal
Terminal=false
Categories=Utility;
EOF
  chmod +x "$DESKTOP_FILE"

  mkdir -p "$HOME/.local/share/applications"
  cp "$DESKTOP_FILE" "$HOME/.local/share/applications/"
  [[ -d "$HOME/Desktop" ]] && cp "$DESKTOP_FILE" "$HOME/Desktop/" && \
    chmod +x "$HOME/Desktop/Pyrestus Web.desktop"

  command -v zenity >/dev/null || command -v kdialog >/dev/null || \
    echo "Tip: install zenity for the window UI:  sudo apt install zenity"

  echo "Created: $DESKTOP_FILE (also added to your app menu and Desktop)"
  echo "GNOME: right-click the Desktop icon > 'Allow Launching' the first time."
fi

