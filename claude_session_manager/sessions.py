"""Discover Claude Code sessions stored under ~/.claude/projects/.

Claude Code writes one *.jsonl transcript per session, named by session UUID,
inside a per-project directory (the project's cwd with path separators
sanitized). We scan those files for the recorded cwd, a preview of the
first user message, and the tail for model/context/state info — without
touching Claude's own data.
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

# Context window sizes (tokens) used to turn a raw token count into a
# percentage. Best-effort match on substrings found in the model id;
# falls back to the standard 200k window.
CONTEXT_WINDOWS: list[tuple[str, int]] = [
    ("[1m]", 1_000_000),
    ("haiku", 200_000),
    ("sonnet", 200_000),
    ("opus", 200_000),
]
DEFAULT_CONTEXT_WINDOW = 200_000


def context_window_for(model: str | None) -> int:
    if not model:
        return DEFAULT_CONTEXT_WINDOW
    lowered = model.lower()
    for needle, size in CONTEXT_WINDOWS:
        if needle in lowered:
            return size
    return DEFAULT_CONTEXT_WINDOW


def short_model_name(model: str | None) -> str | None:
    """'claude-haiku-4-5-20251001' -> 'Haiku 4.5', best-effort."""
    if not model:
        return None
    name = model
    if name.startswith("claude-"):
        name = name[len("claude-") :]
    # Drop a trailing date stamp segment like -20260514.
    parts = name.split("-")
    if parts and parts[-1].isdigit() and len(parts[-1]) == 8:
        parts = parts[:-1]
    if not parts:
        return model
    words = [parts[0].capitalize()]
    numeric_run: list[str] = []
    for part in parts[1:]:
        if part.isdigit():
            numeric_run.append(part)
            continue
        if numeric_run:
            words.append(".".join(numeric_run))
            numeric_run = []
        words.append(part.capitalize())
    if numeric_run:
        words.append(".".join(numeric_run))
    return " ".join(words)


@dataclass
class Session:
    session_id: str
    jsonl_path: Path
    cwd: str | None
    preview: str
    mtime: float
    size: int = 0
    state: str = ""  # "" | "waiting" | "interrupted"
    model: str | None = None  # raw model id from the latest assistant turn
    context_tokens: int | None = None  # approx. tokens in context after that turn
    turns: int = 0  # assistant messages seen in the scanned tail (lower bound)

    @property
    def project_name(self) -> str:
        if self.cwd:
            return Path(self.cwd).name or self.cwd
        return self.jsonl_path.parent.name

    @property
    def last_active(self) -> datetime:
        return datetime.fromtimestamp(self.mtime)

    @property
    def context_window(self) -> int:
        return context_window_for(self.model)

    @property
    def context_fraction(self) -> float | None:
        if self.context_tokens is None:
            return None
        return min(1.0, self.context_tokens / self.context_window)

    @property
    def model_label(self) -> str | None:
        return short_model_name(self.model)


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


@dataclass
class _TailInfo:
    state: str = ""
    model: str | None = None
    context_tokens: int | None = None
    turns: int = 0


def _tail_info(path: Path) -> _TailInfo:
    """Cheaply read the transcript's tail for state, model and context size.

    - state "waiting": Claude's last message was a question with no reply.
    - state "interrupted": the last event was the user stopping Claude.
    - model / context_tokens come from the most recent assistant turn seen
      in the tail window (usage.input_tokens + cache_read + cache_creation
      approximates how much context that turn was carrying).
    """
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > _TAIL_BYTES:
                fh.seek(-_TAIL_BYTES, os.SEEK_END)
            blob = fh.read().decode("utf-8", errors="replace")
    except OSError:
        return _TailInfo()

    latest: str | None = None  # "assistant", "user", or "interrupted"
    latest_assistant_text = ""
    model: str | None = None
    context_tokens: int | None = None
    turns = 0

    for line in blob.splitlines():
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, ValueError):
            continue  # likely a partial first line from the tail window
        if not isinstance(entry, dict):
            continue
        message = entry.get("message") or {}
        text = _extract_text(message.get("content")).strip()

        if entry.get("type") == "assistant":
            turns += 1
            m = message.get("model")
            if isinstance(m, str) and not m.startswith("<"):
                model = m
            usage = message.get("usage") or {}
            input_tokens = usage.get("input_tokens") or 0
            cache_read = usage.get("cache_read_input_tokens") or 0
            cache_creation = usage.get("cache_creation_input_tokens") or 0
            output_tokens = usage.get("output_tokens") or 0
            total = input_tokens + cache_read + cache_creation + output_tokens
            if total:
                context_tokens = total

        if not text:
            continue
        if "[Request interrupted by user" in text:
            latest = "interrupted"
        elif entry.get("type") == "assistant":
            latest = "assistant"
            latest_assistant_text = text
        elif entry.get("type") == "user" and not text.startswith("<"):
            latest = "user"

    state = ""
    if latest == "interrupted":
        state = "interrupted"
    elif latest == "assistant" and latest_assistant_text.rstrip().endswith("?"):
        state = "waiting"

    return _TailInfo(state=state, model=model, context_tokens=context_tokens, turns=turns)


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
            tail = _tail_info(jsonl_path)
            sessions.append(
                Session(
                    session_id=jsonl_path.stem,
                    jsonl_path=jsonl_path,
                    cwd=cwd,
                    preview=preview,
                    mtime=stat.st_mtime,
                    size=stat.st_size,
                    state=tail.state,
                    model=tail.model,
                    context_tokens=tail.context_tokens,
                    turns=tail.turns,
                )
            )

    sessions.sort(key=lambda s: s.mtime, reverse=True)
    return sessions
