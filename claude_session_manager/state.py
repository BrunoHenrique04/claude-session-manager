"""Persistent, app-local state: favorites, custom names, and user-defined
projects that group sessions across folders.

Kept separate from Claude's own data (~/.claude/projects) so this app never
writes anything into it.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

STATE_DIR = Path(
    os.environ.get("CSM_STATE_DIR")
    or Path.home() / ".config" / "claude-session-manager"
)
STATE_FILE = STATE_DIR / "state.json"


class State:
    def __init__(self) -> None:
        self._data: dict = {}
        self.load()

    def load(self) -> None:
        try:
            raw = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = {}
        if not isinstance(raw, dict):
            raw = {}
        # Migrate the old flat {session_id: {...}} layout from before projects
        # existed: anything that isn't "sessions"/"projects" is a leftover
        # per-session entry.
        if "sessions" not in raw and "projects" not in raw:
            raw = {"sessions": raw, "projects": {}}
        raw.setdefault("sessions", {})
        raw.setdefault("projects", {})
        self._data = raw

    def save(self) -> None:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = STATE_FILE.with_suffix(".tmp")
        tmp.write_text(json.dumps(self._data, indent=2, sort_keys=True), encoding="utf-8")
        tmp.replace(STATE_FILE)

    def _session_entry(self, session_id: str) -> dict:
        return self._data["sessions"].setdefault(session_id, {})

    # -- favorites / naming ------------------------------------------------

    def is_favorite(self, session_id: str) -> bool:
        return bool(self._data["sessions"].get(session_id, {}).get("favorite", False))

    def set_favorite(self, session_id: str, value: bool) -> None:
        self._session_entry(session_id)["favorite"] = value
        self.save()

    def custom_name(self, session_id: str) -> str | None:
        return self._data["sessions"].get(session_id, {}).get("name")

    def set_custom_name(self, session_id: str, name: str | None) -> None:
        if name:
            self._session_entry(session_id)["name"] = name
        else:
            self._data["sessions"].get(session_id, {}).pop("name", None)
        self.save()

    # -- projects ------------------------------------------------------------
    # A project is a user-defined label (e.g. "API", "Frontend", "Docs")
    # that a session can be tagged with, independent of which folder it
    # actually lives in. Lets sessions from different repos/folders be found
    # together under one project.

    def list_projects(self) -> list[tuple[str, str]]:
        """[(project_id, name), ...] sorted by name."""
        return sorted(
            ((pid, p.get("name", "")) for pid, p in self._data["projects"].items()),
            key=lambda pair: pair[1].lower(),
        )

    def project_name(self, project_id: str) -> str | None:
        p = self._data["projects"].get(project_id)
        return p.get("name") if p else None

    def create_project(self, name: str) -> str:
        name = name.strip()
        # Reuse an existing project with the same name instead of duplicating.
        for pid, existing in self._data["projects"].items():
            if existing.get("name", "").strip().lower() == name.lower():
                return pid
        pid = uuid.uuid4().hex[:12]
        self._data["projects"][pid] = {"name": name}
        self.save()
        return pid

    def rename_project(self, project_id: str, name: str) -> None:
        name = name.strip()
        if not name or project_id not in self._data["projects"]:
            return
        self._data["projects"][project_id]["name"] = name
        self.save()

    def delete_project(self, project_id: str) -> None:
        self._data["projects"].pop(project_id, None)
        for entry in self._data["sessions"].values():
            if entry.get("project") == project_id:
                entry.pop("project", None)
        self.save()

    def project_of(self, session_id: str) -> str | None:
        return self._data["sessions"].get(session_id, {}).get("project")

    def assign_project(self, session_id: str, project_id: str | None) -> None:
        if project_id:
            self._session_entry(session_id)["project"] = project_id
        else:
            self._data["sessions"].get(session_id, {}).pop("project", None)
        self.save()

    def forget_session(self, session_id: str) -> None:
        """Drop favorite/name/project bookkeeping for a deleted session."""
        if self._data["sessions"].pop(session_id, None) is not None:
            self.save()
