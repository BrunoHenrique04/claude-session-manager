"""Launch `claude --resume <id>` in the session's own project directory,
inside whatever terminal emulator is available on this system.

No embedded terminal widget (VTE) is used: this system doesn't have the
GTK4 VTE bindings installed, and pulling them in needs root. Spawning an
external terminal is simpler, has no extra dependency, and is good enough
for "one click to get back into a session".
"""

from __future__ import annotations

import shlex
import shutil
import subprocess

# (binary, argv-builder). Tried in order; first one found on PATH wins.
_TERMINALS = [
    ("konsole", lambda cmd: ["konsole", "-e", "bash", "-lc", cmd]),
    ("gnome-terminal", lambda cmd: ["gnome-terminal", "--", "bash", "-lc", cmd]),
    ("kitty", lambda cmd: ["kitty", "bash", "-lc", cmd]),
    ("alacritty", lambda cmd: ["alacritty", "-e", "bash", "-lc", cmd]),
    ("wezterm", lambda cmd: ["wezterm", "start", "--", "bash", "-lc", cmd]),
    ("foot", lambda cmd: ["foot", "bash", "-lc", cmd]),
    ("xterm", lambda cmd: ["xterm", "-e", "bash", "-lc", cmd]),
]


def find_terminal() -> str | None:
    for binary, _ in _TERMINALS:
        if shutil.which(binary):
            return binary
    return None


# Extra flags `claude --resume` can be launched with, offered from the
# dropdown next to the resume button. (mode_id, label, extra claude flags)
RESUME_MODES: list[tuple[str, str, list[str]]] = [
    ("default", "Padrão", []),
    (
        "dangerous",
        "Modo perigoso (--dangerously-skip-permissions)",
        ["--dangerously-skip-permissions"],
    ),
]


def resume_command(
    session_id: str, cwd: str | None, extra_args: list[str] | None = None
) -> str:
    """Shell command that cds into the project dir (if known) and resumes."""
    parts = []
    if cwd:
        parts.append(f"cd {shlex.quote(cwd)}")
    claude_cmd = ["claude", "--resume", session_id, *(extra_args or [])]
    parts.append(" ".join(shlex.quote(p) for p in claude_cmd))
    # Keep the shell open after Claude exits so errors are visible.
    return " && ".join(parts) + "; exec bash"


def launch_resume(
    session_id: str, cwd: str | None, extra_args: list[str] | None = None
) -> tuple[bool, str]:
    """Spawn a terminal running the resume command.

    Returns (ok, message) — message is an error to surface on failure, or
    the command itself on success (useful for a status line / toast).
    """
    cmd = resume_command(session_id, cwd, extra_args)
    for binary, build_argv in _TERMINALS:
        path = shutil.which(binary)
        if not path:
            continue
        try:
            subprocess.Popen(build_argv(cmd), start_new_session=True)
            return True, cmd
        except OSError as exc:
            return False, f"Failed to launch {binary}: {exc}"
    return False, "No supported terminal emulator found on PATH."
