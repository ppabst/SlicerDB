#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

mkdir -p app/static/js
HTMX_VERSION="${HTMX_VERSION:-2.0.4}"
if [[ ! -f app/static/js/htmx.min.js ]]; then
    echo "Downloading htmx $HTMX_VERSION..."
    curl -fsSL -o app/static/js/htmx.min.js \
        "https://unpkg.com/htmx.org@${HTMX_VERSION}/dist/htmx.min.js"
fi

./scripts/build_css.sh --watch &
TW_PID=$!
trap "kill $TW_PID 2>/dev/null || true" EXIT

uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8080
