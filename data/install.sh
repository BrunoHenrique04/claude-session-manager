#!/usr/bin/env bash
# User-local install: no sudo needed. Adds the app to the applications menu.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPS_DIR="$HOME/.local/share/applications"
ICON_BASE="$HOME/.local/share/icons/hicolor"
ICON_NAME="io.github.claude-session-manager"

mkdir -p "$APPS_DIR"

sed "s#@APP_DIR@#${APP_DIR}#" "$APP_DIR/data/io.github.claude-session-manager.desktop" \
    > "$APPS_DIR/io.github.claude-session-manager.desktop"

# SVG (scalable, used by most GTK/GNOME contexts)...
mkdir -p "$ICON_BASE/scalable/apps"
cp "$APP_DIR/data/icons/${ICON_NAME}.svg" "$ICON_BASE/scalable/apps/"

# ...plus raster fallbacks at every standard hicolor size: some launchers,
# panels and thumbnailers (notably parts of KDE Plasma) don't resolve a
# scalable-only icon reliably and fall back to a generic one instead.
for size in 16 22 24 32 48 64 128 256 512; do
    dir="$ICON_BASE/${size}x${size}/apps"
    mkdir -p "$dir"
    cp "$APP_DIR/data/icons/png/${size}.png" "$dir/${ICON_NAME}.png"
done

update-desktop-database "$APPS_DIR" 2>/dev/null || true
gtk-update-icon-cache -f -t "$ICON_BASE" 2>/dev/null || true
kbuildsycoca6 2>/dev/null || kbuildsycoca5 2>/dev/null || true

echo "Instalado. Procure por \"Claude Session Manager\" no menu de aplicativos."
echo "(Se não aparecer de imediato, faça log out/login ou reinicie o shell do desktop.)"
