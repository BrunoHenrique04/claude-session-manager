from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw  # noqa: E402

from .window import MainWindow


class Application(Adw.Application):
    def __init__(self) -> None:
        super().__init__(application_id="io.github.claude-session-manager")
        self.window: MainWindow | None = None

    def do_activate(self) -> None:
        if self.window is None:
            self.window = MainWindow(self)
        self.window.present()


def main() -> int:
    return Application().run(None)
