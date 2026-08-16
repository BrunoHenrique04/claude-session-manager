"""Opt-in, project-scoped context sharing between sessions.

Claude Code has its own global auto-memory that lets any session recall
context from any other — useful, but not something everyone wants on for
*everything*. This gives the same idea a hard boundary: only sessions the
user has explicitly grouped into the same custom Project (see state.py)
get told about each other, and only when that project's "cross-session"
switch is on.

It works by building a short digest of sibling sessions and handing it to
`claude` as an extra system-prompt fragment (`--append-system-prompt`) —
no Claude-side feature is touched, no data leaves the machine that wasn't
already going into the prompt anyway.
"""

from __future__ import annotations

from .sessions import Session
from .state import State

MAX_SIBLINGS = 8
PREVIEW_LEN = 140


def build_digest(
    state: State,
    sessions: list[Session],
    session_id: str,
    project_id: str | None,
) -> tuple[str | None, list[str]]:
    """Returns (system_prompt_fragment, extra_dirs) — both empty/None when
    cross-session sharing isn't on for this session's project."""
    if not project_id or not state.project_cross_session(project_id):
        return None, []

    siblings = [
        s
        for s in sessions
        if s.session_id != session_id and state.project_of(s.session_id) == project_id
    ]
    if not siblings:
        return None, []

    siblings.sort(key=lambda s: s.mtime, reverse=True)
    project_name = state.project_name(project_id) or "este projeto"

    lines = [
        f'Você faz parte do projeto "{project_name}" no Claude Session Manager, '
        "junto com outras sessões do Claude Code (possivelmente em pastas "
        "diferentes). Isso é só contexto de fundo sobre o que elas fazem — "
        "não é preciso agir sobre nada disso a menos que o usuário peça:",
        "",
    ]
    dirs: list[str] = []
    for s in siblings[:MAX_SIBLINGS]:
        title = state.custom_name(s.session_id) or s.preview or s.session_id[:8]
        preview = (s.preview or "").strip().replace("\n", " ")
        if len(preview) > PREVIEW_LEN:
            preview = preview[:PREVIEW_LEN].rstrip() + "…"
        lines.append(f"- **{title}** — `{s.cwd or '?'}` — {preview}")
        if s.cwd and s.cwd not in dirs:
            dirs.append(s.cwd)

    if len(siblings) > MAX_SIBLINGS:
        lines.append(f"- (+{len(siblings) - MAX_SIBLINGS} outra(s) sessão/sessões no projeto)")

    return "\n".join(lines), dirs
