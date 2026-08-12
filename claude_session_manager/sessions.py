"""Discover Claude Code sessions stored under ~/.claude/projects/.

Claude Code writes one *.jsonl transcript per session, named by session UUID,
inside a per-project directory (the project's cwd with path separators
sanitized). We scan those files for the recorded cwd and a preview of the
first user message, without touching Claude's own data.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

CLAUDE_PROJECTS_DIR = Path(
    os.environ.get("CSM_PROJECTS_DIR") or Path.home() / ".claude" / "projects"
)

_UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)

_MAX_SCAN_LINES = 50
_MAX_SCAN_BYTES = 256 * 1024


@dataclass
class Session:
    session_id: str
    jsonl_path: Path
    cwd: str | None
    preview: str
    mtime: float
    size: int = 0
    state: str = ""  # "" | "waiting" | "interrupted"

    @property
    def project_name(self) -> str:
        if self.cwd:
            return Path(self.cwd).name or self.cwd
        return self.jsonl_path.parent.name

    @property
    def last_active(self) -> datetime:
        return datetime.fromtimestamp(self.mtime)


def _extract_text(content) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            b.get("text", "")
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        return " ".join(p for p in parts if p)
    return ""


def _scan_transcript(path: Path) -> tuple[str | None, str]:
    """Return (cwd, preview) by peeking at the start of a transcript."""
    cwd: str | None = None
    preview = ""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            read = 0
            for i, line in enumerate(fh):
                read += len(line)
                if i >= _MAX_SCAN_LINES or read > _MAX_SCAN_BYTES:
                    break
                try:
                    entry = json.loads(line)
                except (json.JSONDecodeError, ValueError):
                    continue
                if not isinstance(entry, dict):
                    continue
                if cwd is None and isinstance(entry.get("cwd"), str):
                    cwd = entry["cwd"]
                if not preview and entry.get("type") == "user":
                    message = entry.get("message") or {}
                    text = _extract_text(message.get("content")).strip()
                    if text and not text.startswith("<"):
                        preview = " ".join(text.split())[:140]
                if cwd and preview:
                    break
    except OSError:
        pass
    return cwd, preview


_TAIL_BYTES = 64 * 1024


def _tail_state(path: Path) -> str:
    """Cheaply read the transcript's tail to classify its state.

    - "waiting": Claude's last message was a question with no user reply after.
    - "interrupted": the last event was the user stopping Claude mid-task.
    - "" otherwise.
    """
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > _TAIL_BYTES:
                fh.seek(-_TAIL_BYTES, os.SEEK_END)
            blob = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return ""

    latest: str | None = None  # "assistant", "user", or "interrupted"
    latest_assistant_text = ""
    for line in blob.splitlines():
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue  # likely a partial first line from the tail window
        if not isinstance(entry, dict):
            continue
        text = _extract_text((entry.get("message") or {}).get("content")).strip()
        if not text:
            continue
        if "[Request interrupted by user" in text:
            latest = "interrupted"
        elif entry.get("type") == "assistant":
            latest = "assistant"
            latest_assistant_text = text
        elif entry.get("type") == "user" and not text.startswith("<"):
            latest = "user"

    if latest == "interrupted":
        return "interrupted"
    if latest == "assistant" and latest_assistant_text.rstrip().endswith("?"):
        return "waiting"
    return ""


def discover_sessions() -> list[Session]:
    """All sessions found under CLAUDE_PROJECTS_DIR, newest activity first."""
    sessions: list[Session] = []
    if not CLAUDE_PROJECTS_DIR.is_dir():
        return sessions

    for project_dir in CLAUDE_PROJECTS_DIR.iterdir():
        if not project_dir.is_dir():
            continue
        for jsonl_path in project_dir.glob("*.jsonl"):
            if not _UUID_RE.match(jsonl_path.stem):
                continue
            try:
                stat = jsonl_path.stat()
            except OSError:
                continue
            cwd, preview = _scan_transcript(jsonl_path)
            sessions.append(
                Session(
                    session_id=jsonl_path.stem,
                    jsonl_path=jsonl_path,
                    cwd=cwd,
                    preview=preview,
                    mtime=stat.st_mtime,
                    size=stat.st_size,
                    state=_tail_state(jsonl_path),
                )
            )

    sessions.sort(key=lambda s: s.mtime, reverse=True)
    return sessions
