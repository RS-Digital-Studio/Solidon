"""Quelltext lesen, wie der Baum ist: rekursiv, sortiert, nie leer (Codestruktur W4).

Quelltextprüfungen lesen ein Paket über diesen Helfer und nie über ein flaches
``glob("*.py")``. Ein flacher Glob sieht kein Unterpaket — ``app/ui/render/``
lag lange außerhalb jeder Verbotsprüfung über ``app/ui`` —, und eine
Verbotsprüfung über eine Teilmenge ist grün, weil sie nicht hingesehen hat
(CS-2). Wird eine Datei später zum Paket (``main_window.py`` →
``main_window/``), liest jede Prüfung weiter alles. ``test_source_readers.py``
hält fest, dass in ``tests/`` und ``tools/`` niemand mehr flach liest, und legt
jeder Prüfung einen Verstoß in ein Unterpaket einer Kopie des Baums.

``ROOT`` ist die Wurzel, aus der gelesen wird; diese Gegenproben setzen sie auf
die Kopie. Ordner werden deshalb relativ zu ``ROOT`` genannt
(``python_files("app/ui")``), Pfade über :func:`relative` gemeldet und Dateien,
die eine Prüfung meint, über :func:`definition_file` gefunden — nie über
``Path(modul.__file__)`` oder das Arbeitsverzeichnis, die beide an der Kopie
vorbei in den echten Baum zeigen. Aufgerufen wird über das Modul
(``source_tree.python_files``), damit eine Gegenprobe den Helfer selbst
verfälschen kann.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

#: Die Wurzel des Baums, aus dem die Prüfungen lesen.
ROOT = Path(__file__).resolve().parent.parent


def python_files(folder: str) -> list[Path]:
    """Jede ``*.py`` unter ``folder`` (relativ zu ``ROOT``), rekursiv und sortiert.

    ``__pycache__`` bleibt draußen. Ein leerer Ordner ist ein Fehler: Eine
    Verbotsprüfung über null Dateien meldet „kein Verstoß“ und meint „nicht
    nachgesehen“.
    """
    base = ROOT / folder
    found = sorted(
        path for path in base.rglob("*.py") if "__pycache__" not in path.relative_to(base).parts
    )
    if not found:
        raise AssertionError(f"keine Python-Datei unter {base} — falscher Ordner?")
    return found


def relative(path: Path) -> str:
    """``path`` relativ zu ``ROOT`` mit Schrägstrichen — für Meldungen und genaue Vergleiche.

    Der Dateiname allein ist nach dem rekursiven Lesen nicht mehr eindeutig:
    ``app/ui/__init__.py`` und ``app/ui/render/__init__.py`` heißen gleich.
    """
    return path.relative_to(ROOT).as_posix()


def definition_file(name: str, folder: str = "app") -> Path:
    """Die eine Datei unter ``folder``, die ``class name`` oder ``def name`` auf Modulebene trägt.

    Statisch gelesen, ohne Import: So findet eine Prüfung die Datei, die sie
    meint, auch nachdem ein Schritt die Definition in ein Unterpaket verschoben
    hat — und in der Kopie des Baums die Kopie. Keine oder mehrere Fundstellen
    sind ein Fehler mit den Kandidaten; mehrdeutige Namen wie ``detect`` nennen
    deshalb ihren Ordner.
    """
    heading = re.compile(rf"^(?:async\s+def|def|class)\s+{re.escape(name)}\b", re.MULTILINE)
    found = []
    for path in python_files(folder):
        text = path.read_text(encoding="utf-8")
        # Erst der Text, dann der Baum: Nur wenige Dateien tragen die Zeile,
        # und den Baum von main_window.py zu bauen kostet eine halbe Sekunde.
        if heading.search(text) and any(
            isinstance(node, ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
            and node.name == name
            for node in ast.parse(text).body
        ):
            found.append(path)
    if len(found) != 1:
        raise AssertionError(
            f"{name} ist unter {folder} {len(found)}-mal auf Modulebene definiert, "
            f"erwartet genau einmal: {[relative(path) for path in found]}"
        )
    return found[0]
