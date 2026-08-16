from __future__ import annotations

import shutil
import subprocess
import time

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Adw, Gdk, GLib, Gtk  # noqa: E402

from . import terminal
from .depcheck import vte_install_hint
from .sessions import Session, discover_sessions
from .state import State
from .vte_terminal import VTE_AVAILABLE, build_terminal_widget

REFRESH_INTERVAL_MS = 5000

_STATE_ICON = {
    "waiting": ("dialog-question-symbolic", "Aguardando sua resposta"),
    "interrupted": ("process-stop-symbolic", "Interrompida"),
}


def _relative_time(mtime: float) -> str:
    delta = time.time() - mtime
    if delta < 60:
        return "agora"
    if delta < 3600:
        return f"{int(delta // 60)}m atrás"
    if delta < 86400:
        return f"{int(delta // 3600)}h atrás"
    return f"{int(delta // 86400)}d atrás"


def _chip(text: str, css_class: str | None = None, tooltip: str | None = None) -> Gtk.Widget:
    label = Gtk.Label(label=text)
    label.add_css_class("csm-chip")
    if css_class:
        label.add_css_class(css_class)
    if tooltip:
        label.set_tooltip_text(tooltip)
    return label


def _context_chip(session: Session) -> Gtk.Widget | None:
    fraction = session.context_fraction
    if fraction is None:
        return None
    pct = round(fraction * 100)
    if fraction < 0.6:
        css = "csm-chip-context-ok"
        bar_class = ""
    elif fraction < 0.85:
        css = "csm-chip-context-warn"
        bar_class = "warn"
    else:
        css = "csm-chip-context-danger"
        bar_class = "danger"

    box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
    box.add_css_class("csm-chip")
    box.add_css_class(css)

    bar = Gtk.ProgressBar()
    bar.set_fraction(fraction)
    bar.set_size_request(40, -1)
    bar.set_valign(Gtk.Align.CENTER)
    bar.add_css_class("csm-context-bar")
    if bar_class:
        bar.add_css_class(bar_class)
    box.append(bar)

    box.append(Gtk.Label(label=f"{pct}% ctx"))
    box.set_tooltip_text(
        f"~{session.context_tokens:,} / {session.context_window:,} tokens de contexto"
        .replace(",", ".")
    )
    return box


class ProjectPopover(Gtk.Popover):
    """Lets a row be assigned to (or removed from) a user-defined project."""

    def __init__(self, window: "MainWindow", session: Session):
        super().__init__()
        self._window = window
        self._session = session

        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        box.set_margin_top(8)
        box.set_margin_bottom(8)
        box.set_margin_start(8)
        box.set_margin_end(8)
        self.set_child(box)

        current = window.state.project_of(session.session_id)
        projects = window.state.list_projects()

        if projects:
            listbox = Gtk.ListBox()
            listbox.set_selection_mode(Gtk.SelectionMode.NONE)
            listbox.add_css_class("boxed-list")
            for pid, name in projects:
                row = Adw.ActionRow()
                row.set_title(GLib.markup_escape_text(name))
                row.set_activatable(True)
                if pid == current:
                    check = Gtk.Image.new_from_icon_name("object-select-symbolic")
                    row.add_suffix(check)
                row.connect("activated", self._assign, pid)
                listbox.append(row)
            box.append(listbox)

        if current:
            remove_btn = Gtk.Button(label="Remover do projeto")
            remove_btn.add_css_class("flat")
            remove_btn.connect("clicked", self._assign, None)
            box.append(remove_btn)

        box.append(Gtk.Separator())

        entry_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        entry = Gtk.Entry()
        entry.set_placeholder_text("Novo projeto…")
        entry.set_hexpand(True)
        create_btn = Gtk.Button(icon_name="list-add-symbolic")
        create_btn.add_css_class("flat")

        def do_create(*_a):
            name = entry.get_text().strip()
            if not name:
                return
            pid = window.state.create_project(name)
            self._assign(None, pid)

        entry.connect("activate", do_create)
        create_btn.connect("clicked", do_create)
        entry_row.append(entry)
        entry_row.append(create_btn)
        box.append(entry_row)

    def _assign(self, _widget, project_id: str | None) -> None:
        self._window.state.assign_project(self._session.session_id, project_id)
        self.popdown()
        self._window._rebuild()


class ResumeModePopover(Gtk.Popover):
    """Extra ways to launch `claude --resume`: default vs. dangerous mode,
    each either embedded (VTE, when available) or in an external terminal."""

    def __init__(self, window: "MainWindow", session: Session):
        super().__init__()
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(6)
        box.set_margin_end(6)
        self.set_child(box)

        vte_here = VTE_AVAILABLE and window.tab_view is not None
        modes = terminal.RESUME_MODES
        for i, (mode_id, label, extra_args) in enumerate(modes):
            danger = mode_id == "dangerous"
            if vte_here:
                self._add(box, window, session, f"{label} · Aqui no app", extra_args, "vte", danger)
            self._add(
                box, window, session, f"{label} · Terminal externo", extra_args, "external", danger
            )
            if i < len(modes) - 1:
                box.append(Gtk.Separator())

    def _add(
        self,
        box: Gtk.Box,
        window: "MainWindow",
        session: Session,
        label: str,
        extra_args: list[str],
        target: str,
        danger: bool,
    ) -> None:
        btn = Gtk.Button(label=label)
        btn.add_css_class("flat")
        btn.get_child().set_xalign(0)
        if danger:
            btn.add_css_class("csm-danger-item")

        def handler(*_a, args=extra_args, target=target):
            self.popdown()
            window.resume(session, extra_args=args, target=target)

        btn.connect("clicked", handler)
        box.append(btn)


class SessionContextPopover(Gtk.Popover):
    """Right-click menu: actions that don't fit as row icon buttons."""

    def __init__(self, window: "MainWindow", session: Session):
        super().__init__()
        self.set_has_arrow(False)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        box.set_margin_top(6)
        box.set_margin_bottom(6)
        box.set_margin_start(6)
        box.set_margin_end(6)
        self.set_child(box)

        def add(label: str, handler, danger: bool = False) -> None:
            btn = Gtk.Button(label=label)
            btn.add_css_class("flat")
            btn.get_child().set_xalign(0)
            if danger:
                btn.add_css_class("csm-danger-item")

            def _h(*_a, handler=handler):
                self.popdown()
                handler()

            btn.connect("clicked", _h)
            box.append(btn)

        add("▶  Retomar", lambda: window.resume(session))
        add(
            "⚠  Retomar (modo perigoso)",
            lambda: window.resume(session, extra_args=["--dangerously-skip-permissions"]),
        )
        box.append(Gtk.Separator())
        add("📂  Abrir local da sessão", lambda: window.open_session_location(session))
        add("🆔  Copiar ID da sessão", lambda: window.copy_to_clipboard(session.session_id))
        add(
            "📋  Copiar caminho",
            lambda: window.copy_to_clipboard(session.cwd or str(session.jsonl_path.parent)),
        )
        box.append(Gtk.Separator())
        fav_label = (
            "☆  Remover dos favoritos"
            if window.state.is_favorite(session.session_id)
            else "⭐  Favoritar"
        )
        add(fav_label, lambda: window.toggle_favorite(session))
        add("✏️  Renomear", lambda: window.prompt_rename(session))
        box.append(Gtk.Separator())
        add("🗑  Excluir sessão…", lambda: window.prompt_delete_session(session), danger=True)


class SessionRow(Gtk.ListBoxRow):
    """A card: title/subtitle/actions on top, model+context chips below —
    kept on separate lines so the action buttons never crowd the title into
    an unreadable sliver."""

    def __init__(self, session: Session, window: "MainWindow"):
        super().__init__()
        self.session = session
        self._window = window
        state = window.state
        self.add_css_class("csm-card")
        self.set_margin_top(3)
        self.set_margin_bottom(3)

        right_click = Gtk.GestureClick(button=Gdk.BUTTON_SECONDARY)
        right_click.connect("pressed", self._on_right_click)
        self.add_controller(right_click)

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        outer.set_margin_top(4)
        outer.set_margin_bottom(4)
        self.set_child(outer)

        content = Adw.ActionRow()
        content.add_css_class("csm-card-content")
        # Adw.ActionRow wraps title/subtitle onto unlimited lines by default
        # instead of ellipsizing; force single-line + ellipsis.
        content.set_title_lines(1)
        content.set_subtitle_lines(1)
        outer.append(content)

        title = state.custom_name(session.session_id) or (
            session.preview or f"Sessão {session.session_id[:8]}"
        )
        content.set_title(GLib.markup_escape_text(title))

        subtitle_path = session.cwd or str(session.jsonl_path.parent)
        project_name = state.project_name(state.project_of(session.session_id) or "")
        tag = f"  ·  🏷 {project_name}" if project_name else ""
        content.set_subtitle(
            f"{GLib.markup_escape_text(subtitle_path)}  ·  {_relative_time(session.mtime)}  ·  "
            f"{session.session_id[:8]}{GLib.markup_escape_text(tag)}"
        )

        if session.state in _STATE_ICON:
            icon_name, tooltip = _STATE_ICON[session.state]
            state_icon = Gtk.Image.new_from_icon_name(icon_name)
            state_icon.set_tooltip_text(tooltip)
            state_icon.add_css_class("accent" if session.state == "waiting" else "warning")
            content.add_prefix(state_icon)

        self.fav_button = Gtk.ToggleButton()
        self.fav_button.set_icon_name("starred-symbolic")
        self.fav_button.set_valign(Gtk.Align.CENTER)
        self.fav_button.add_css_class("flat")
        self.fav_button.set_active(state.is_favorite(session.session_id))
        self.fav_button.set_tooltip_text("Favorito")
        self.fav_button.connect("toggled", self._toggled_fav)
        content.add_prefix(self.fav_button)

        project_btn = Gtk.MenuButton()
        project_btn.set_icon_name("tag-symbolic")
        project_btn.set_valign(Gtk.Align.CENTER)
        project_btn.add_css_class("flat")
        project_btn.set_tooltip_text("Atribuir a um projeto")
        project_popover = ProjectPopover(window, session)
        window.track_popover(project_popover)
        project_btn.set_popover(project_popover)
        content.add_suffix(project_btn)

        rename_button = Gtk.Button()
        rename_button.set_icon_name("document-edit-symbolic")
        rename_button.set_valign(Gtk.Align.CENTER)
        rename_button.add_css_class("flat")
        rename_button.set_tooltip_text("Renomear sessão")
        rename_button.connect("clicked", lambda *_: window.prompt_rename(session))
        content.add_suffix(rename_button)

        resume_split = Adw.SplitButton()
        resume_split.set_icon_name("media-playback-start-symbolic")
        resume_split.set_valign(Gtk.Align.CENTER)
        resume_split.add_css_class("flat")
        resume_split.add_css_class("circular")
        resume_split.set_tooltip_text("Retomar")
        resume_split.connect("clicked", lambda *_: window.resume(session))
        resume_popover = ResumeModePopover(window, session)
        window.track_popover(resume_popover)
        resume_split.set_popover(resume_popover)
        content.add_suffix(resume_split)

        # -- chips: model, context usage, on their own line -------------------
        chips = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        chips.set_margin_start(16)
        chips.set_margin_end(12)
        chips.set_margin_bottom(2)
        if session.model_label:
            chips.append(_chip(session.model_label, "csm-chip-model", tooltip=session.model))
        ctx_chip = _context_chip(session)
        if ctx_chip is not None:
            chips.append(ctx_chip)
        if chips.get_first_child() is not None:
            outer.append(chips)

    def _toggled_fav(self, button: Gtk.ToggleButton) -> None:
        self._window.state.set_favorite(self.session.session_id, button.get_active())

    def _on_right_click(self, gesture, _n_press, x: float, y: float) -> None:
        # Claim the sequence: popping a popover up from a "pressed" handler
        # without this can make GTK treat the matching button-release (which
        # lands outside the popover, since it's only just appeared) as a
        # click-away and immediately dismiss it again.
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        popover = SessionContextPopover(self._window, self.session)
        self._window.track_popover(popover)
        popover.set_parent(self)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        popover.set_pointing_to(rect)
        popover.connect("closed", lambda p: p.unparent())
        popover.popup()

    @property
    def search_text(self) -> str:
        s = self.session
        return " ".join(
            filter(None, [s.preview, s.project_name, s.cwd, s.session_id, s.model])
        ).lower()


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app, title="Claude Sessions")
        self.set_default_size(1180, 760)
        self.add_css_class("csm-window")

        self.state = State()
        self.sessions: list[Session] = []
        self._open_pages: dict[str, Adw.TabPage] = {}
        # Bumped while any row popover (project/resume-mode/right-click menu)
        # is open, so the periodic refresh below can skip rebuilding the
        # sidebar — _rebuild() throws away and recreates every row widget,
        # which yanks an open popover out from under the user mid-click.
        self._popups_open = 0

        split_view = Adw.NavigationSplitView()
        split_view.set_min_sidebar_width(380)
        split_view.set_max_sidebar_width(520)
        self.set_content(split_view)

        # -- sidebar: session list ------------------------------------------------
        sidebar_toolbar = Adw.ToolbarView()
        sidebar_page = Adw.NavigationPage(title="Sessões", child=sidebar_toolbar)
        split_view.set_sidebar(sidebar_page)

        header = Adw.HeaderBar()
        sidebar_toolbar.add_top_bar(header)

        refresh_btn = Gtk.Button(icon_name="view-refresh-symbolic")
        refresh_btn.set_tooltip_text("Atualizar")
        refresh_btn.add_css_class("flat")
        refresh_btn.connect("clicked", lambda *_: self.refresh())
        header.pack_end(refresh_btn)

        new_project_btn = Gtk.Button(icon_name="folder-new-symbolic")
        new_project_btn.set_tooltip_text("Novo projeto")
        new_project_btn.add_css_class("flat")
        new_project_btn.connect("clicked", lambda *_: self._prompt_new_project())
        header.pack_end(new_project_btn)

        self.search_entry = Gtk.SearchEntry()
        self.search_entry.add_css_class("csm-searchbar")
        self.search_entry.set_placeholder_text("Buscar sessões, projetos, modelos, ids…")
        self.search_entry.connect("search-changed", lambda *_: self._apply_filter())
        header.set_title_widget(self.search_entry)

        self.toast_overlay = Adw.ToastOverlay()
        sidebar_toolbar.set_content(self.toast_overlay)

        scrolled = Gtk.ScrolledWindow()
        scrolled.set_vexpand(True)
        self.toast_overlay.set_child(scrolled)

        clamp = Adw.Clamp()
        clamp.set_maximum_size(920)
        scrolled.set_child(clamp)

        self.status_page = Adw.StatusPage()
        self.status_page.set_icon_name("folder-symbolic")
        self.status_page.set_title("Nenhuma sessão encontrada")
        self.status_page.set_description(
            "Nenhuma sessão do Claude Code em ~/.claude/projects ainda."
        )

        self.groups_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=22)
        self.groups_box.set_margin_top(18)
        self.groups_box.set_margin_bottom(22)
        self.groups_box.set_margin_start(14)
        self.groups_box.set_margin_end(14)
        clamp.set_child(self.groups_box)

        # -- content: embedded terminal tabs (or a fallback notice) ---------------
        content_toolbar = Adw.ToolbarView()
        content_page = Adw.NavigationPage(title="Terminal", child=content_toolbar)
        split_view.set_content(content_page)
        content_header = Adw.HeaderBar()
        content_toolbar.add_top_bar(content_header)

        if VTE_AVAILABLE:
            self.tab_view = Adw.TabView()
            tab_bar = Adw.TabBar()
            tab_bar.set_view(self.tab_view)
            content_toolbar.add_top_bar(tab_bar)
            content_toolbar.set_content(self.tab_view)
        else:
            self.tab_view = None
            placeholder = Adw.StatusPage()
            placeholder.set_icon_name("utilities-terminal-symbolic")
            placeholder.set_title("Terminal embutido indisponível")
            placeholder.set_description(
                "Instale os bindings GTK4 do VTE para abrir sessões aqui dentro:\n"
                f"{vte_install_hint()}\n\n"
                "Por enquanto, retomar abre um terminal externo "
                f"({terminal.find_terminal() or 'nenhum encontrado'})."
            )
            content_toolbar.set_content(placeholder)

        # Ctrl+F focuses search.
        controller = Gtk.ShortcutController()
        controller.add_shortcut(
            Gtk.Shortcut.new(
                Gtk.ShortcutTrigger.parse_string("<Control>f"),
                Gtk.CallbackAction.new(self._focus_search),
            )
        )
        self.add_controller(controller)

        self.refresh()
        GLib.timeout_add(REFRESH_INTERVAL_MS, self._on_timeout)

    def _focus_search(self, *_args):
        self.search_entry.grab_focus()
        return True

    def _on_timeout(self) -> bool:
        if self._popups_open <= 0:
            self.refresh()
        return True

    def track_popover(self, popover: Gtk.Popover) -> None:
        """Keep the periodic refresh from rebuilding the sidebar (and
        yanking away this popover) while it's open."""

        def _on_visible(p: Gtk.Popover, _pspec) -> None:
            self._popups_open += 1 if p.get_visible() else -1

        popover.connect("notify::visible", _on_visible)

    def refresh(self) -> None:
        self.sessions = discover_sessions()
        self._rebuild()

    def _prompt_new_project(self) -> None:
        dialog = Adw.AlertDialog(
            heading="Novo projeto",
            body="Sessões de qualquer pasta poderão ser atribuídas a ele.",
        )
        entry = Gtk.Entry()
        entry.set_placeholder_text("ex.: API, Frontend, Docs")
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("create", "Criar")
        dialog.set_response_appearance("create", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("create")

        def on_response(_dlg, response):
            if response == "create":
                name = entry.get_text().strip()
                if name:
                    self.state.create_project(name)
                    self._rebuild()

        dialog.connect("response", on_response)
        dialog.present(self)

    def _rebuild(self) -> None:
        child = self.groups_box.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.groups_box.remove(child)
            child = nxt

        if not self.sessions:
            self.groups_box.append(self.status_page)
            return

        favorites = [s for s in self.sessions if self.state.is_favorite(s.session_id)]
        projects = self.state.list_projects()
        assigned_ids: set[str] = set()

        if favorites:
            self._append_group("★  Favoritos", favorites, group_key="fav")

        for pid, name in projects:
            members = [
                s for s in self.sessions if self.state.project_of(s.session_id) == pid
            ]
            assigned_ids.update(s.session_id for s in members)
            self._append_group(
                f"🏷  {name}", members, group_key=f"project:{pid}", empty_hint=not members
            )

        remaining = [s for s in self.sessions if s.session_id not in assigned_ids]
        by_folder: dict[str, list[Session]] = {}
        for s in remaining:
            by_folder.setdefault(s.project_name, []).append(s)

        if projects and remaining:
            label = Gtk.Label(label="Por pasta", xalign=0)
            label.add_css_class("csm-group-hint")
            label.add_css_class("dim-label")
            self.groups_box.append(label)

        for folder in sorted(by_folder, key=lambda p: by_folder[p][0].mtime, reverse=True):
            self._append_group(f"📁  {folder}", by_folder[folder], group_key=f"folder:{folder}")

        self._apply_filter()

    def _append_group(
        self,
        label: str,
        sessions: list[Session],
        group_key: str,
        empty_hint: bool = False,
    ) -> None:
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        collapsed = self.state.is_group_collapsed(group_key)

        # The whole header is a flat button: click anywhere on it (not just a
        # tiny chevron) to fold the group away — this is what keeps the
        # sidebar from turning into a wall of cards once there are a lot of
        # sessions/projects.
        header_btn = Gtk.Button()
        header_btn.add_css_class("flat")
        header_btn.add_css_class("csm-group-header-btn")
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        header.add_css_class("csm-group-header")
        chevron = Gtk.Image.new_from_icon_name(
            "pan-end-symbolic" if collapsed else "pan-down-symbolic"
        )
        chevron.add_css_class("dim-label")
        header.append(chevron)
        title_label = Gtk.Label(label=label, xalign=0)
        title_label.add_css_class("csm-group-title")
        title_label.set_hexpand(True)
        header.append(title_label)
        if sessions:
            count = Gtk.Label(label=str(len(sessions)))
            count.add_css_class("csm-group-count")
            header.append(count)
        header_btn.set_child(header)
        box.append(header_btn)

        if empty_hint:
            hint = Gtk.Label(
                label="Nenhuma sessão ainda — use o ícone 🏷 numa sessão para atribuí-la aqui.",
                xalign=0,
            )
            hint.add_css_class("dim-label")
            hint.add_css_class("caption")
            hint.set_visible(not collapsed)
            box.append(hint)
            box.listbox = None
            content_widget = hint
        else:
            listbox = Gtk.ListBox()
            listbox.add_css_class("csm-list")
            listbox.set_selection_mode(Gtk.SelectionMode.NONE)
            listbox.connect("row-activated", lambda _lb, row: self.resume(row.session))
            listbox.set_visible(not collapsed)
            box.append(listbox)

            for session in sessions:
                row = SessionRow(session, self)
                listbox.append(row)

            box.listbox = listbox
            content_widget = listbox

        box.group_key = group_key

        def _toggle(*_a) -> None:
            now_collapsed = not self.state.is_group_collapsed(group_key)
            self.state.set_group_collapsed(group_key, now_collapsed)
            chevron.set_from_icon_name("pan-end-symbolic" if now_collapsed else "pan-down-symbolic")
            if not self.search_entry.get_text().strip():
                content_widget.set_visible(not now_collapsed)

        header_btn.connect("clicked", _toggle)
        self.groups_box.append(box)

    def _apply_filter(self) -> None:
        query = self.search_entry.get_text().strip().lower()
        group_box = self.groups_box.get_first_child()
        while group_box is not None:
            if group_box is self.status_page:
                group_box = group_box.get_next_sibling()
                continue
            listbox = getattr(group_box, "listbox", None)
            group_key = getattr(group_box, "group_key", None)
            collapsed = bool(group_key) and self.state.is_group_collapsed(group_key)
            any_visible = not query  # groups with no listbox (e.g. section labels) stay
            if listbox is not None:
                any_visible = False
                row = listbox.get_first_child()
                while row is not None:
                    visible = not query or query in row.search_text
                    row.set_visible(visible)
                    any_visible = any_visible or visible
                    row = row.get_next_sibling()
                # While searching, force the group open so matches are
                # visible even if the user had it collapsed; otherwise
                # respect the saved collapsed state.
                listbox.set_visible(any_visible if query else not collapsed)
            group_box.set_visible(any_visible)
            group_box = group_box.get_next_sibling()

    def resume(
        self,
        session: Session,
        extra_args: list[str] | None = None,
        target: str | None = None,
    ) -> None:
        """target: None (auto: embedded when available, else external),
        "vte" (embedded), or "external" (always spawn a terminal emulator)."""
        extra_args = extra_args or []
        tab_key = f"{session.session_id}:{','.join(extra_args)}"

        if target != "external" and VTE_AVAILABLE and self.tab_view is not None:
            existing = self._open_pages.get(tab_key)
            if existing is not None and existing.get_parent() is not None:
                self.tab_view.set_selected_page(existing)
                return
            title = self.state.custom_name(session.session_id) or session.project_name
            if extra_args:
                title += " ⚠"
            widget = build_terminal_widget(session.session_id, session.cwd, extra_args)
            page = self.tab_view.append(widget)
            page.set_title(title)
            page.set_tooltip(f"{title} · {session.session_id[:8]}")
            self.tab_view.set_selected_page(page)
            self._open_pages[tab_key] = page
            return

        ok, message = terminal.launch_resume(session.session_id, session.cwd, extra_args)
        toast = Adw.Toast(title=message if ok else f"⚠ {message}")
        toast.set_timeout(4)
        self.toast_overlay.add_toast(toast)

    def _toast(self, text: str) -> None:
        toast = Adw.Toast(title=text)
        toast.set_timeout(3)
        self.toast_overlay.add_toast(toast)

    def toggle_favorite(self, session: Session) -> None:
        self.state.set_favorite(session.session_id, not self.state.is_favorite(session.session_id))
        self._rebuild()

    def copy_to_clipboard(self, text: str) -> None:
        self.get_clipboard().set(text)
        self._toast("Copiado.")

    def open_session_location(self, session: Session) -> None:
        path = session.cwd or str(session.jsonl_path.parent)
        for binary, build_argv in (
            ("xdg-open", lambda p: ["xdg-open", p]),
            ("dolphin", lambda p: ["dolphin", p]),
            ("nautilus", lambda p: ["nautilus", p]),
            ("thunar", lambda p: ["thunar", p]),
            ("nemo", lambda p: ["nemo", p]),
            ("pcmanfm", lambda p: ["pcmanfm", p]),
        ):
            if shutil.which(binary):
                try:
                    subprocess.Popen(build_argv(path), start_new_session=True)
                    return
                except OSError:
                    continue
        self._toast("⚠ Nenhum gerenciador de arquivos encontrado.")

    def prompt_delete_session(self, session: Session) -> None:
        title = self.state.custom_name(session.session_id) or session.preview or session.session_id[:8]
        dialog = Adw.AlertDialog(
            heading="Excluir sessão?",
            body=(
                f'"{title}" será apagada permanentemente do disco '
                f"({session.jsonl_path.name}). Isso não pode ser desfeito."
            ),
        )
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("delete", "Excluir")
        dialog.set_response_appearance("delete", Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response("cancel")

        def on_response(_dlg, response):
            if response == "delete":
                self._delete_session(session)

        dialog.connect("response", on_response)
        dialog.present(self)

    def _delete_session(self, session: Session) -> None:
        try:
            session.jsonl_path.unlink()
        except OSError as exc:
            self._toast(f"⚠ Não foi possível excluir: {exc}")
            return
        self.state.forget_session(session.session_id)
        self._toast("Sessão excluída.")
        self.refresh()

    def prompt_rename(self, session: Session) -> None:
        current = self.state.custom_name(session.session_id) or session.preview or ""
        dialog = Adw.AlertDialog(
            heading="Renomear sessão",
            body="Deixe em branco para voltar ao preview automático.",
        )
        entry = Gtk.Entry()
        entry.set_text(current)
        dialog.set_extra_child(entry)
        dialog.add_response("cancel", "Cancelar")
        dialog.add_response("save", "Salvar")
        dialog.set_response_appearance("save", Adw.ResponseAppearance.SUGGESTED)
        dialog.set_default_response("save")

        def on_response(_dlg, response):
            if response == "save":
                self.state.set_custom_name(session.session_id, entry.get_text().strip() or None)
                self._rebuild()

        dialog.connect("response", on_response)
        dialog.present(self)
