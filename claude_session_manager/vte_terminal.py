"""Embedded terminal tab using VTE, when available.

VTE's GTK4 bindings (`vte291-gtk4` on Fedora) aren't installed on every
system by default and need root to install, so this whole module is
optional: `VTE_AVAILABLE` tells the rest of the app whether embedding is
possible. When it isn't, window.py falls back to spawning an external
terminal (see terminal.py).
"""

from __future__ import annotations

import gi

try:
    gi.require_version("Vte", "3.91")
    from gi.repository import Vte

    VTE_AVAILABLE = True
except (ImportError, ValueError):
    Vte = None  # type: ignore[assignment]
    VTE_AVAILABLE = False

from gi.repository import Adw, GLib, Gtk  # noqa: E402

from . import terminal


def build_terminal_page(
    session_id: str,
    cwd: str | None,
    title: str,
    extra_args: list[str] | None = None,
) -> Adw.TabPage:
    """A ready-to-insert Adw.TabPage running `claude --resume` in cwd."""
    if not VTE_AVAILABLE:
        raise RuntimeError("VTE is not available")

    term = Vte.Terminal()
    term.set_hexpand(True)
    term.set_vexpand(True)
    term.set_scrollback_lines(10000)

    scrolled = Gtk.ScrolledWindow()
    scrolled.set_child(term)
    scrolled.set_hexpand(True)
    scrolled.set_vexpand(True)

    cmd = terminal.resume_command(session_id, cwd, extra_args)
    argv = ["/bin/bash", "-lc", cmd]
    spawn_cwd = cwd if cwd and GLib.file_test(cwd, GLib.FileTest.IS_DIR) else GLib.get_home_dir()

    term.spawn_async(
        Vte.PtyFlags.DEFAULT,
        spawn_cwd,
        argv,
        None,  # inherit environment
        GLib.SpawnFlags.DEFAULT,
        None,
        None,
        -1,
        None,
        None,
    )

    page = Adw.TabPage.new(scrolled, title)
    page.set_tooltip(f"{title} · {session_id[:8]}")
    return page
