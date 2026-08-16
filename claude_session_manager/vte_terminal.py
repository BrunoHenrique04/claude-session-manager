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

from gi.repository import GLib, Gtk  # noqa: E402

from . import terminal


def build_terminal_widget(
    session_id: str,
    cwd: str | None,
    extra_args: list[str] | None = None,
    system_prompt: str | None = None,
    add_dirs: list[str] | None = None,
) -> Gtk.Widget:
    """A ready-to-embed widget running `claude --resume` in cwd.

    Returns the plain widget rather than an Adw.TabPage: TabPage has no
    public constructor (`Adw.TabPage.new` doesn't exist) — it only comes
    into being as the return value of `Adw.TabView.append(widget)`, so the
    caller does that and sets title/tooltip on the page it gets back.
    """
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

    cmd = terminal.resume_command(session_id, cwd, extra_args, system_prompt, add_dirs)
    argv = ["/bin/bash", "-lc", cmd]
    spawn_cwd = cwd if cwd and GLib.file_test(cwd, GLib.FileTest.IS_DIR) else GLib.get_home_dir()

    def _on_spawn(_terminal, pid, error, _user_data=None):
        # Without this callback the process silently never spawns: the
        # binding's `callback` argument doesn't accept None, and getting the
        # positional order wrong (as a previous version of this code did)
        # raises a TypeError that's swallowed by the GTK main loop — the tab
        # opens but stays a blank, dead terminal with no visible error.
        if error is not None:
            print(f"claude-session-manager: VTE spawn failed: {error}")

    # Keyword args, not positional: this binding's positional dispatch is
    # off by one somewhere (a bare `None` in the cancellable slot raises
    # "Argument 9 does not allow None" even though the same value works
    # fine passed by name) — keywords sidestep that entirely.
    term.spawn_async(
        pty_flags=Vte.PtyFlags.DEFAULT,
        working_directory=spawn_cwd,
        argv=argv,
        envv=None,  # inherit environment
        spawn_flags=GLib.SpawnFlags.DEFAULT,
        child_setup=None,
        timeout=-1,  # -1 = default
        cancellable=None,
        callback=_on_spawn,
        user_data=None,
    )

    return scrolled
