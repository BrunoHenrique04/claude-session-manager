#!/usr/bin/env bash
# User-local install: no sudo needed. Adds the app to the applications menu.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
APPS_DIR="$HOME/.local/share/applications"
ICONS_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"

mkdir -p "$APPS_DIR" "$ICONS_DIR"

sed "s#@APP_DIR@#${APP_DIR}#" "$APP_DIR/data/io.github.claude-session-manager.desktop" \
    > "$APPS_DIR/io.github.claude-session-manager.desktop"

cp "$APP_DIR/data/icons/io.github.claude-session-manager.svg" "$ICONS_DIR/"

update-desktop-database "$APPS_DIR" 2>/dev/null || true
gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "Instalado. Procure por \"Claude Session Manager\" no menu de aplicativos."
echo "(Se não aparecer de imediato, faça log out/login ou reinicie o shell do desktop.)"
