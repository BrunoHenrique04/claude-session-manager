#!/usr/bin/env bash
# Quick installer for Claude Session Manager.
#
#   ./install.sh            install (or re-install after a git pull)
#   ./install.sh --uninstall   remove the command + menu entry
#
# Everything is user-local — no sudo, nothing touches system paths.
set -euo pipefail

APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_LINK="$HOME/.local/bin/claude-session-manager"
DESKTOP_FILE="$HOME/.local/share/applications/io.github.claude-session-manager.desktop"
ICON_FILE="$HOME/.local/share/icons/hicolor/scalable/apps/io.github.claude-session-manager.svg"

info() { printf '\033[1;34m==>\033[0m %s\n' "$1"; }
warn() { printf '\033[1;33m!!\033[0m %s\n' "$1"; }
ok()   { printf '\033[1;32m✓\033[0m %s\n' "$1"; }
err()  { printf '\033[1;31m✗\033[0m %s\n' "$1" >&2; }

if [[ "${1:-}" == "--uninstall" ]]; then
    info "Removendo Claude Session Manager…"
    rm -f "$BIN_LINK" "$DESKTOP_FILE" "$ICON_FILE"
    update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
    gtk-update-icon-cache "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
    ok "Desinstalado. (Favoritos/projetos/nomes em ~/.config/claude-session-manager foram mantidos —"
    echo "   apague essa pasta também se quiser um estado limpo.)"
    exit 0
fi

info "Verificando dependências…"

if ! command -v python3 >/dev/null 2>&1; then
    err "python3 não encontrado. Instale-o e rode este script de novo."
    exit 1
fi

if ! python3 -c "
import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw
" 2>/dev/null; then
    err "GTK4 + libadwaita (PyGObject) não encontrados."
    echo "   Instale os pacotes equivalentes a python3-gobject, gtk4 e libadwaita"
    echo "   pelo gerenciador de pacotes da sua distro e rode este script de novo."
    exit 1
fi
ok "GTK4 + libadwaita OK"

if python3 -c "
import gi
gi.require_version('Vte', '3.91')
from gi.repository import Vte
" 2>/dev/null; then
    ok "VTE (terminal embutido) disponível"
else
    warn "VTE não encontrado — sessões vão abrir num terminal externo por enquanto."
    warn "Para terminal embutido: $(python3 "$APP_DIR/claude_session_manager/depcheck.py")"
fi

info "Instalando comando…"
mkdir -p "$HOME/.local/bin"
ln -sf "$APP_DIR/bin/claude-session-manager" "$BIN_LINK"
ok "'claude-session-manager' instalado em ~/.local/bin (aponta para este diretório)"

case ":${PATH}:" in
    *":$HOME/.local/bin:"*) ;;
    *)
        warn "~/.local/bin não está no seu PATH."
        echo "   Adicione ao seu shell rc (~/.bashrc, ~/.zshrc, ...):"
        echo "     export PATH=\"\$HOME/.local/bin:\$PATH\""
        ;;
esac

info "Instalando entrada no menu de aplicativos…"
bash "$APP_DIR/data/install.sh"

echo
ok "Instalação concluída."
echo "  • Terminal:      claude-session-manager"
echo "  • Menu de apps:  \"Claude Session Manager\""
echo "  • Desinstalar:   ./install.sh --uninstall"
