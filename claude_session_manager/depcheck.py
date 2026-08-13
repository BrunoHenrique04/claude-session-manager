"""Best-effort OS detection so we can point at the right package-install
command for VTE (embedded terminal), instead of assuming plain `dnf`/`apt`
everywhere. Atomic/image-based distros (Bazzite, Silverblue, Kinoite, ...)
use `rpm-ostree` and need a reboot, which is different enough from a normal
Fedora that getting it wrong just sends people down a dead end.
"""

from __future__ import annotations

import shutil
from pathlib import Path


def _os_release() -> dict[str, str]:
    data: dict[str, str] = {}
    try:
        for line in Path("/etc/os-release").read_text(encoding="utf-8").splitlines():
            if "=" in line:
                key, _, value = line.partition("=")
                data[key] = value.strip().strip('"')
    except OSError:
        pass
    return data


def vte_install_hint() -> str:
    info = _os_release()
    ids = {info.get("ID", "")} | set(info.get("ID_LIKE", "").split())

    if shutil.which("rpm-ostree") and (
        "bazzite" in ids or "atomic" in info.get("VARIANT_ID", "") or "silverblue" in ids
    ):
        return (
            "rpm-ostree install vte291-gtk4   "
            "(sistema imutável — Bazzite/Silverblue/Kinoite; pede reboot)"
        )
    if ids & {"fedora", "rhel", "centos"}:
        return "sudo dnf install vte291-gtk4"
    if ids & {"debian", "ubuntu"}:
        return "sudo apt install gir1.2-vte-3.91-common libvte-2.91-gtk4-0 (nome pode variar por versão)"
    if ids & {"arch", "manjaro"}:
        return "sudo pacman -S vte4"
    return (
        "instale o pacote VTE com bindings GTK4 do seu gerenciador de pacotes "
        "(ex.: vte291-gtk4 / gir1.2-vte-3.91 / vte4)"
    )


if __name__ == "__main__":
    print(vte_install_hint())
