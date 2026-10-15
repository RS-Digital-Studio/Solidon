"""Orte und Helfer der Pakettests, ohne eigene Tests.

Beide Pakettests, ``tests/test_packaging.py`` und
``tests/test_packaging_platform.py``, lesen ``ROOT``, ``SPEC``, ``WORKFLOW``,
``workflow_shell`` und ``start_report``. Diese stehen hier einmal unter
öffentlichen Namen, denn eine Testdatei importiert nichts Privates aus einer
anderen (``tests/test_toolchain.py``), und eine Kopie liefe beim nächsten
Wechsel auseinander. Jede Testdatei bindet die Pfade mit ``from … import`` an
ihr eigenes Modul: Ein Test, der dort ``WORKFLOW`` umbiegt
(``monkeypatch.setattr(sys.modules[__name__], …)``), trifft genau die
Prüfungen seiner Datei.

``as_tested`` und ``stays_in_linux_bundle`` samt ``_EXCLUDED_MODULES`` braucht
nur ``tests/test_packaging.py``. Sie stehen trotzdem hier, weil jene Datei über
2 000 Zeilen hat und die Sperrklinke (``tests/data/size_ratchet.toml``,
Codestruktur Regel 6) dort keine neue Definition annimmt; solange die Datei
gelistet ist, gehören sie nicht zurück. ``LINUX_RUNNER`` und
``LINUX_PACKAGE_RUNNER`` stehen bei ``as_tested``, das sie vergleicht, und der
Pakettest liest sie von hier.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Final

from tests.shell_helpers import bash_executable

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

    Wo die bash liegt, sagt allein ``bash_executable`` (``tests/shell_helpers.py``),
    das den Starter von WSL verwirft. Gefragt wird nach der bash, die den
    ``PATH`` lässt: Die Tests tragen Attrappen für ``git`` und ``python`` vorn
    ein, und der Starter aus Git für Windows überdeckte sie mit den echten.
    """
    found = bash_executable(keep_path=True)
    return None if found is None else str(found)


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
