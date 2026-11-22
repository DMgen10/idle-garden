#!/usr/bin/env bash
# Build dist/idle-garden_<version>_all.deb (and a copy named idle-garden.deb).
#   bash packaging/build_deb.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VERSION="$(python3 -c "import sys; sys.path.insert(0, '$ROOT'); import idle_garden; print(idle_garden.__version__)")"
BUILD="$(mktemp -d)"
trap 'rm -rf "$BUILD"' EXIT
PKG="$BUILD/idle-garden"

install -d "$PKG/DEBIAN" "$PKG/usr/bin" "$PKG/usr/lib/idle-garden" \
    "$PKG/etc/xdg/autostart" "$PKG/usr/share/applications" \
    "$PKG/usr/share/doc/idle-garden" "$PKG/usr/share/man/man1"

cp -r "$ROOT/idle_garden" "$PKG/usr/lib/idle-garden/"
find "$PKG" -name '__pycache__' -type d -prune -exec rm -rf {} +

cat > "$PKG/usr/bin/idle-garden" <<'EOF'
#!/bin/sh
PYTHONPATH="/usr/lib/idle-garden${PYTHONPATH:+:$PYTHONPATH}" exec python3 -m idle_garden "$@"
EOF
chmod 755 "$PKG/usr/bin/idle-garden"

cat > "$PKG/etc/xdg/autostart/idle-garden.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Idle Garden
Comment=An ASCII tree slowly grows over your screen while you are away
Exec=idle-garden
Icon=weather-clear
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=5
NoDisplay=true
EOF

cat > "$PKG/usr/share/applications/idle-garden.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Idle Garden
Comment=Watch the ASCII tree grow now (move the mouse to close)
Exec=idle-garden --preview
Icon=weather-clear
Categories=Utility;
Terminal=false
EOF

gzip -9n -c "$ROOT/packaging/idle-garden.1" > "$PKG/usr/share/man/man1/idle-garden.1.gz"
cp "$ROOT/README.md" "$PKG/usr/share/doc/idle-garden/README.md"
gzip -9n -c "$ROOT/CHANGELOG.md" > "$PKG/usr/share/doc/idle-garden/changelog.gz"
{
    echo "Format: https://www.debian.org/doc/packaging-manuals/copyright-format/1.0/"
    echo "Upstream-Name: idle-garden"
    echo "Source: https://github.com/DMgen10/idle-garden"
    echo
    echo "Files: *"
    echo "License: MIT"
    sed 's/^/ /; s/^ $/ ./' "$ROOT/LICENSE"
} > "$PKG/usr/share/doc/idle-garden/copyright"

SIZE="$(du -sk "$PKG" | cut -f1)"
cat > "$PKG/DEBIAN/control" <<EOF
Package: idle-garden
Version: $VERSION
Section: x11
Priority: optional
Architecture: all
Depends: python3 (>= 3.8), python3-gi, python3-gi-cairo, gir1.2-gtk-3.0
Installed-Size: $SIZE
Maintainer: DMgen10 <DMgen10@users.noreply.github.com>
Homepage: https://github.com/DMgen10/idle-garden
Description: ASCII tree that slowly grows over your screen while you are away
 When you leave the computer alone, a tree starts growing from a small patch
 of earth in the middle of the screen: trunk, crown, branches, vines and ivy,
 until the whole screen is overgrown. Any mouse movement or key press makes it
 disappear instantly. It does not lock the session.
 .
 Works on GNOME (Wayland and X11) and other X11 desktops.
EOF

cat > "$PKG/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if [ "$1" = "configure" ]; then
    echo "Idle Garden is installed. It starts automatically after your next login."
    echo "To start it now:   idle-garden --restart"
    echo "To watch it now:   idle-garden --preview -g 2"
fi
EOF
cat > "$PKG/DEBIAN/prerm" <<'EOF'
#!/bin/sh
set -e
# stop running copies so no orphaned windows stay around
pkill -f 'python3 -m idle_garden' 2>/dev/null || true
EOF
chmod 755 "$PKG/DEBIAN/postinst" "$PKG/DEBIAN/prerm"

mkdir -p "$ROOT/dist"
OUT="$ROOT/dist/idle-garden_${VERSION}_all.deb"
dpkg-deb --root-owner-group --build "$PKG" "$OUT" >/dev/null
cp "$OUT" "$ROOT/dist/idle-garden.deb"
echo "$OUT"
