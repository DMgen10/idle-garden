#!/usr/bin/env bash
# Remove Idle Garden. Add --purge to delete your settings too.
set -euo pipefail

APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/idle-garden"
BIN="$HOME/.local/bin/idle-garden"
CONFIG_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/idle-garden"

if [[ -x "$BIN" ]]; then "$BIN" --stop >/dev/null 2>&1 || true; fi
pkill -u "$(id -u)" -f 'python3 -m idle_garden' 2>/dev/null || true

rm -rf "$APP_DIR"
rm -f "$BIN" \
      "${XDG_CONFIG_HOME:-$HOME/.config}/autostart/idle-garden.desktop" \
      "${XDG_DATA_HOME:-$HOME/.local/share}/applications/idle-garden.desktop"

if [[ "${1:-}" == "--purge" ]]; then
    rm -rf "$CONFIG_DIR"
    echo "Idle Garden and its settings were removed."
else
    echo "Idle Garden was removed. Your settings are kept in $CONFIG_DIR (use --purge to delete them)."
fi
