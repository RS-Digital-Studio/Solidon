"""Gemeinsame Orte und Helfer der Pakettests, ohne eigene Tests.

``tests/test_packaging.py`` und ``tests/test_packaging_platform.py`` lesen
dieselben Repositorypfade, Läufer und Helfer. Sie stehen hier einmal unter
öffentlichen Namen, denn eine Testdatei importiert nichts Privates aus einer
anderen (``tests/test_toolchain.py``), und eine Kopie liefe beim nächsten
Wechsel auseinander. Jede Testdatei bindet die Pfade mit ``from … import`` an
ihr eigenes Modul: Ein Test, der dort ``WORKFLOW`` umbiegt
(``monkeypatch.setattr(sys.modules[__name__], …)``), trifft genau die
Prüfungen seiner Datei.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent
SPEC: Final = ROOT / "packaging" / "solidon3d.spec"
WORKFLOW: Final = ROOT / ".github" / "workflows" / "build.yml"
#: Das Ubuntu, auf dem Linux geprüft wird (Suite, Fensterverträge, Auswahlen).
LINUX_RUNNER: Final = "ubuntu-24.04"
#: Das Ubuntu, dessen Systembibliotheken das Linux-Paket mitnimmt: das älteste
#: unterstützte System, dessen glibc die Untergrenze des Pakets ist
#: (``tools/check_glibc_floor.OLDEST_GLIBC``). Gebaut wird dort, geprüft auf
#: :data:`LINUX_RUNNER` — dieselbe Plattform, Linux x86_64.
LINUX_PACKAGE_RUNNER: Final = "ubuntu-22.04"


def as_tested(runner: str) -> str:
    """Der Prüfläufer derselben Plattform: Linux wird auf 22.04 gebaut, auf 24.04 geprüft."""
    return LINUX_RUNNER if runner == LINUX_PACKAGE_RUNNER else runner


def workflow_shell() -> str | None:
    """Die Shell, mit der die CI ihre ``run:``-Blöcke fährt — bash.

    Jeder hier geprüfte Block deklariert ``shell: bash``, und er verlässt sich
    darauf: ``set -o pipefail`` kennt POSIX-``sh`` nicht, ``dash`` weist es mit
    ``Illegal option`` ab. Wer den Block zum Messen mit ``sh`` fährt, misst eine
    Umgebung, in der er nie läuft — unter Windows fällt das nicht auf, weil die
    ``sh`` aus Git für Windows eine bash ist.

    Für das Linux-Installationsskript gilt das Gegenteil: Es ist bewusst
    POSIX-``sh`` und wird mit ``_posix_shell`` aus ``tests/test_packaging.py`` gefahren.
    """
    found = shutil.which("bash")
    if found is not None:
        return found

    program_files = Path(os.environ.get("PROGRAMFILES", r"C:\Program Files"))
    git_bash = program_files / "Git" / "usr" / "bin" / "bash.exe"
    if git_bash.is_file():
        return str(git_bash)
    return None


# Der Bericht eines gelungenen Starts, wie ihn ``app.ui.start_check`` schreibt;
# ``changes`` ersetzt einzelne Teile für die Gegenproben.
def start_report(**changes: Any) -> dict[str, Any]:
    from app.branding import APP_VERSION
    from app.ui.start_check import FORMAT

    report: dict[str, Any] = {
        "format": FORMAT,
        "version": APP_VERSION,
        "window": {"visible": True, "title": "Unbenannt"},
        "renderer": {"present": True, "kind": "GfxRenderer", "brightest": 74},
    }
    report.update(changes)
    return report


#: Was die Spec über ``excludes`` gar nicht erst einsammelt (GPL-3, Regel 15).
_EXCLUDED_MODULES: Final = ("readline.cpython", "_curses.cpython", "_curses_panel.cpython")


def stays_in_linux_bundle(path: str) -> bool:
    """Bleibt eine Datei des Korpus im Linux-Paket? Gefragt wird die Quelle selbst.

    ``make_linux_packages.trim_linux_binaries`` entscheidet über verwaiste
    Bibliotheken, ausgebaute Qt-Plugins und die Bibliotheken des Rechners
    (``HOST_LIBRARIES``); ein Nachbau hier hatte die letzten vergessen
    (Review 1, G2). Die Zielnamen der Spec stehen ohne ``_internal/``.
    """
    from tools import make_linux_packages as tool

    target = path.removeprefix("_internal/")
    if Path(target).name.startswith(_EXCLUDED_MODULES):
        return False
    return bool(tool.trim_linux_binaries([(target, path, "BINARY")]))
