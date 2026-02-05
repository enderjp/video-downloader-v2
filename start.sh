#!/bin/sh
set -e

echo "[start.sh] Using system Chromium at ${CHROME_BIN:-/usr/bin/chromium}"
if [ -n "${CHROMEDRIVER_PATH}" ]; then
  echo "[start.sh] Using chromedriver at ${CHROMEDRIVER_PATH}"
else
  echo "[start.sh] CHROMEDRIVER_PATH not set; relying on PATH"
fi

echo "[start.sh] Starting uvicorn..."
exec uvicorn main_selenium:app --host 0.0.0.0 --port ${PORT:-8000}
