"""App-wide CSS. Uses libadwaita's named colors (@accent_color, @card_bg_color,
etc.) so it follows the system theme and light/dark switching for free.
"""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gdk, Gtk  # noqa: E402

CSS = """
.csm-group-header {
    padding: 4px 4px 0 4px;
}

.csm-group-title {
    font-weight: 800;
    font-size: 1.05rem;
    letter-spacing: -0.01em;
}

.csm-group-count {
    background-color: alpha(currentColor, 0.10);
    border-radius: 999px;
    padding: 1px 9px;
    font-size: 0.8rem;
    font-weight: 700;
    color: alpha(currentColor, 0.65);
}

.csm-group-hint {
    padding: 2px 4px 2px 4px;
}

.csm-group-header-btn {
    background: none;
    box-shadow: none;
    border: none;
    padding: 2px 4px;
    border-radius: 8px;
    min-height: 0;
}

.csm-group-header-btn:hover {
    background-color: alpha(currentColor, 0.06);
}

.csm-list, .csm-list row {
    background: none;
    box-shadow: none;
    border: none;
    padding: 0;
    outline: none;
}

row.csm-card {
    background-color: var(--card-bg, @card_bg_color);
    color: @card_fg_color;
    border-radius: 16px;
    border: 1px solid alpha(currentColor, 0.06);
    padding: 0;
    transition: background-color 150ms ease, border-color 150ms ease;
}

row.csm-card:hover {
    background-color: shade(@card_bg_color, 1.06);
}

.csm-card-content, .csm-card-content:hover {
    background: none;
    box-shadow: none;
}

.csm-card.csm-waiting {
    border-color: alpha(@accent_color, 0.55);
    background-color: alpha(@accent_color, 0.06);
}

.csm-card.csm-interrupted {
    border-color: alpha(@warning_color, 0.5);
}

.csm-title {
    font-weight: 700;
    font-size: 1.02rem;
}

.csm-path {
    color: alpha(currentColor, 0.55);
    font-family: monospace;
    font-size: 0.82rem;
}

.csm-chip {
    border-radius: 999px;
    padding: 2px 10px;
    font-size: 0.78rem;
    font-weight: 600;
    background-color: alpha(currentColor, 0.08);
    color: alpha(currentColor, 0.75);
}

.csm-chip-model {
    background-color: alpha(@accent_color, 0.14);
    color: @accent_color;
}

.csm-chip-context-ok {
    background-color: alpha(@success_color, 0.14);
    color: @success_color;
}

.csm-chip-context-warn {
    background-color: alpha(@warning_color, 0.18);
    color: shade(@warning_color, 0.75);
}

.csm-chip-context-danger {
    background-color: alpha(@error_color, 0.16);
    color: @error_color;
}

.csm-chip-state-waiting {
    background-color: alpha(@accent_color, 0.16);
    color: @accent_color;
}

.csm-chip-state-interrupted {
    background-color: alpha(@warning_color, 0.18);
    color: shade(@warning_color, 0.75);
}

.csm-context-bar {
    min-height: 5px;
    border-radius: 999px;
}

.csm-context-bar trough {
    min-height: 5px;
    border-radius: 999px;
    background-color: alpha(currentColor, 0.10);
}

.csm-context-bar block.filled {
    border-radius: 999px;
    background-color: @accent_color;
}

.csm-context-bar.warn block.filled {
    background-color: @warning_color;
}

.csm-context-bar.danger block.filled {
    background-color: @error_color;
}

.csm-searchbar {
    min-width: 320px;
}

.csm-hero-subtitle {
    color: alpha(currentColor, 0.6);
    font-size: 0.9rem;
}

.csm-danger-item {
    color: @error_color;
}
"""


def load_css() -> None:
    provider = Gtk.CssProvider()
    provider.load_from_string(CSS)
    display = Gdk.Display.get_default()
    if display is not None:
        Gtk.StyleContext.add_provider_for_display(
            display, provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION
        )
