#!/usr/bin/env bash
# Idle Garden installer — installs for the current user only (no root needed,
# except to install missing GTK packages with apt).
#
#   bash install.sh                   # from a cloned repository
#   curl -fsSL https://raw.githubusercontent.com/DMgen10/idle-garden/main/install.sh | bash
set -euo pipefail

REPO_URL="${IDLE_GARDEN_REPO:-https://github.com/DMgen10/idle-garden}"
BRANCH="${IDLE_GARDEN_BRANCH:-main}"

APP_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/idle-garden"
BIN_DIR="$HOME/.local/bin"
BIN="$BIN_DIR/idle-garden"
AUTOSTART_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
APPS_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/applications"

green() { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
red() { printf '\033[31m%s\033[0m\n' "$*"; }

cat <<'BANNER'

        &&&@&
      &%&*|&&@&
     &&*\~|/~&&
        \\|//          idle garden
         ||            installer
   ,.,'"`||`',.,"
   ~~~~~~~~~~~~~~~
BANNER

# --- 1. Python ---------------------------------------------------------------
if ! command -v python3 >/dev/null 2>&1; then
    red "python3 is not installed. Run: sudo apt install python3"
    exit 1
fi
if ! python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)'; then
    red "Python 3.8 or newer is required."
    exit 1
fi

# --- 2. GTK 3 bindings ---------------------------------------------------------
check_gtk() {
    python3 - <<'PY' >/dev/null 2>&1
import gi, cairo
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk
PY
}
if ! check_gtk; then
    yellow "GTK 3 for Python is missing. Needed packages: python3-gi python3-gi-cairo gir1.2-gtk-3.0"
    if command -v apt-get >/dev/null 2>&1; then
        read -r -p "Install them now with sudo apt? [Y/n] " answer </dev/tty || answer="n"
        if [[ -z "$answer" || "$answer" =~ ^[Yy] ]]; then
            sudo apt-get install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0
        fi
    fi
    if ! check_gtk; then
        red "GTK bindings are still missing; please install the packages above and run the installer again."
        exit 1
    fi
fi

# --- 3. Get the source ---------------------------------------------------------
SRC_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" 2>/dev/null && pwd || true)"
TMP=""
if [[ -z "$SRC_DIR" || ! -d "$SRC_DIR/idle_garden" ]]; then
    TMP="$(mktemp -d)"
    trap 'rm -rf "$TMP"' EXIT
    echo "Downloading $REPO_URL ($BRANCH)…"
    curl -fsSL "$REPO_URL/archive/refs/heads/$BRANCH.tar.gz" | tar -xz -C "$TMP" --strip-components=1
    SRC_DIR="$TMP"
fi

# stop an old copy before replacing its files
if [[ -x "$BIN" ]]; then "$BIN" --stop >/dev/null 2>&1 || true; fi

mkdir -p "$APP_DIR" "$BIN_DIR" "$AUTOSTART_DIR" "$APPS_DIR"
rm -rf "$APP_DIR/idle_garden"
cp -r "$SRC_DIR/idle_garden" "$APP_DIR/"
find "$APP_DIR" -name '__pycache__' -type d -prune -exec rm -rf {} +

# --- 4. Launcher ---------------------------------------------------------------
cat > "$BIN" <<EOF
#!/bin/sh
PYTHONPATH="$APP_DIR\${PYTHONPATH:+:\$PYTHONPATH}" exec python3 -m idle_garden "\$@"
EOF
chmod +x "$BIN"

# --- 5. Start automatically after login ------------------------------------------
cat > "$AUTOSTART_DIR/idle-garden.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Idle Garden
Comment=An ASCII tree slowly grows over your screen while you are away
Exec=$BIN
Icon=weather-clear
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
NoDisplay=true
EOF

# menu entry to see it right away
cat > "$APPS_DIR/idle-garden.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Idle Garden
Comment=Watch the ASCII tree grow now (move the mouse to close)
Exec=$BIN --preview
Icon=weather-clear
Categories=Utility;
Terminal=false
EOF

"$BIN" --edit-config >/dev/null

# --- 6. Start now ----------------------------------------------------------------
if [[ -n "${DISPLAY:-}${WAYLAND_DISPLAY:-}" ]]; then
    "$BIN" --restart >/dev/null
    STARTED=1
else
    STARTED=0
fi

echo
green "✔ Idle Garden is installed."
echo "  Leave the computer alone for 2 minutes and a tree will start growing."
echo
echo "  Try it now:       idle-garden --preview"
echo "  In a terminal:    idle-garden --terminal"
echo "  Settings:         ${XDG_CONFIG_HOME:-$HOME/.config}/idle-garden/config.ini  (then: idle-garden --restart)"
echo "  Uninstall:        bash uninstall.sh  (or: curl -fsSL ${REPO_URL/github.com/raw.githubusercontent.com}/$BRANCH/uninstall.sh | bash)"
[[ "$STARTED" == 1 ]] || yellow "  It will start automatically the next time you log in."
case ":$PATH:" in
    *":$BIN_DIR:"*) ;;
    *) yellow "  Note: $BIN_DIR is not in your PATH yet; log out and back in, or run $BIN" ;;
esac
