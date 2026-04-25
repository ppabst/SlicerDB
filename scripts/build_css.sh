#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

TAILWIND_VERSION="${TAILWIND_VERSION:-v4.1.13}"
BIN_DIR=".bin"
mkdir -p "$BIN_DIR"
TW="$BIN_DIR/tailwindcss"

if [[ ! -x "$TW" ]]; then
    case "$(uname -s)-$(uname -m)" in
        Darwin-arm64) ASSET="tailwindcss-macos-arm64" ;;
        Darwin-x86_64) ASSET="tailwindcss-macos-x64" ;;
        Linux-x86_64) ASSET="tailwindcss-linux-x64" ;;
        Linux-aarch64) ASSET="tailwindcss-linux-arm64" ;;
        *) echo "Unsupported platform: $(uname -s)-$(uname -m)"; exit 1 ;;
    esac
    echo "Downloading Tailwind $TAILWIND_VERSION ($ASSET)..."
    curl -fsSL -o "$TW" \
        "https://github.com/tailwindlabs/tailwindcss/releases/download/${TAILWIND_VERSION}/${ASSET}"
    chmod +x "$TW"
fi

"$TW" -i app/static/css/input.css -o app/static/css/output.css "$@"
