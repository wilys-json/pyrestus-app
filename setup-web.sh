#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

command -v python3 >/dev/null || { echo 'Python 3 is required.'; exit 1; }
command -v flutter >/dev/null || { echo 'Flutter SDK is required.'; exit 1; }

# Reuse the venv if it already exists
[ -x "$ROOT/.venv/bin/python" ] || python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install --upgrade pip
"$ROOT/.venv/bin/python" -m pip install -r "$ROOT/app/backend/requirements.txt"

# # Fail early if DICOM decoders are missing
# "$ROOT/.venv/bin/python" - <<'PY'
# import importlib, sys
# missing = [m for m in ("pydicom", "pylibjpeg", "libjpeg", "openjpeg", "PIL", "cv2")
#            if importlib.util.find_spec(m) is None]
# if missing:
#     sys.exit(f"Missing Python modules: {', '.join(missing)}")
# print("Python dependencies OK")
# PY

(
  cd "$ROOT/app"
  flutter clean
  flutter pub get
  flutter build web --no-wasm-dry-run --dart-define=API_URL=/api
)

echo 'Setup complete. Start with: ./pyrestus-web.sh start'
