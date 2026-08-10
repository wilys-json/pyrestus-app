#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
command -v python3 >/dev/null || { echo 'Python 3 is required.'; exit 1; }
command -v flutter >/dev/null || { echo 'Flutter SDK is required.'; exit 1; }
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/pip" install --upgrade pip
"$ROOT/.venv/bin/pip" install -r "$ROOT/app/backend/requirements.txt"
(cd "$ROOT/app" && flutter pub get && flutter build web --dart-define=API_URL=/api)
echo 'Setup complete. Start with: ./pyrestus-web.sh start'
