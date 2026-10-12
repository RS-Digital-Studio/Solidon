"""Misst die Zeit je Tastendruck in der Suche — Palette (vorher) oder Suchfeld (nachher).

Aufruf: python sonde_tastendruck.py <baum> <art: palette|feld|feld-frueh> <ausgabe.json>

Gemessen wird am gebauten Fenster (offscreen) mit einem Körper aus dem Korpus,
gewählt wie nach einem Klick. Je Wort wird Zeichen für Zeichen getippt; die
Zeit je Zeichen umfasst ``setText`` und das Abarbeiten der Ereignisse. Der
erste Tastendruck baut die Zeilen (beide Fassungen bauen sie dort), er steht
getrennt. Drei Durchgänge, jeweils frisch geöffnet.

``palette`` braucht einen Baum vor RM-735 (``d2f8d4916``). ``feld-frueh``
setzt den frühen Ausstieg aus ``023c9c703`` vor ``_filter`` und ist nur an
einem Baum davor ein Vergleich; ab dort hat ``feld`` ihn schon.
"""

import json
import os
import sys
import tempfile
import time
from pathlib import Path

TREE = Path(sys.argv[1]).resolve()
KIND = sys.argv[2]
OUT = Path(sys.argv[3])

os.environ["QT_QPA_PLATFORM"] = "offscreen"
home = Path(tempfile.mkdtemp(prefix="sonde-taste-"))
for name in ("APPDATA", "LOCALAPPDATA"):
    os.environ[name] = str(home / name)
    (home / name).mkdir()
sys.path.insert(0, str(TREE))

from PySide6.QtWidgets import QApplication  # noqa: E402

app = QApplication([])

import app as solidon  # noqa: E402

assert Path(solidon.__file__).resolve().is_relative_to(TREE), solidon.__file__

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.selection_operations import SelectionOperationsPanel  # noqa: E402
from app.ui.session import Session  # noqa: E402
from app.ui.settings import UiSettings  # noqa: E402

if KIND == "feld-frueh":
    # Variante: Bei Suchtext ruht die verdeckte Karte; nur Treffer und Umbruch.
    full_filter = SelectionOperationsPanel._filter

    def early_filter(self, query=None):
        """Der frühe Ausstieg aus ``023c9c703`` vor der Fassung des Baums."""
        if query is not None:
            self._query = query
        wanted = self._query.strip()
        if wanted:
            self._show_hits(wanted)
            self._wrap_labels()
            return
        full_filter(self, query)

    SelectionOperationsPanel._filter = early_filter

WORDS = ("verrunden", "bohrung", "boolesch", "speichern", "qqq")
ROUNDS = 3


def settle(window: MainWindow) -> None:
    """Bis Auswertung und Berichtsanalyse ruhen, dann zwei Sekunden Ereignisse."""
    for _round in range(3):
        assert window.session.wait_for_idle(60_000)
        for _again in range(5):
            worker = window._print_findings.worker
            if worker is None or not worker.isRunning():
                break
            assert worker.wait(60_000)
            app.processEvents()
        deadline = time.monotonic() + 2.0
        while time.monotonic() < deadline:
            app.processEvents()
            time.sleep(0.02)


def window_with_a_body() -> MainWindow:
    window = MainWindow(Session(), UiSettings())
    window.show()
    window.resize(1600, 1000)
    window._show_start_screen(False)
    app.processEvents()
    window.open_path(TREE / "tests" / "data" / "meshes" / "clean_figure.stl")
    assert window.session.wait_for_idle(60_000)
    app.processEvents()
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    item.setSelected(True)
    app.processEvents()
    settle(window)
    return window


def typed(field, word: str) -> list[float]:
    """Sekunden je Zeichen, das Wort Zeichen für Zeichen."""
    times = []
    for end in range(1, len(word) + 1):
        start = time.perf_counter()
        field.setText(word[:end])
        app.processEvents()
        times.append(time.perf_counter() - start)
    return times


result: dict[str, object] = {"tree": str(TREE), "kind": KIND, "rounds": []}
for _round in range(ROUNDS):
    window = window_with_a_body()
    measured: dict[str, object] = {}
    if KIND == "palette":
        from app.ui.command_palette import CommandPalette

        start = time.perf_counter()
        commands = window.window_commands()
        palette = CommandPalette(window.palette_rows(commands), parent=window, query="")
        palette.show()
        app.processEvents()
        measured["open"] = time.perf_counter() - start
        field = palette.search
    else:
        start = time.perf_counter()
        window.action_function_search()
        app.processEvents()
        measured["open"] = time.perf_counter() - start
        field = window.selection_operations.search
    settle(window)
    for word in WORDS:
        measured[word] = typed(field, word)
        field.setText("")
        app.processEvents()
    if KIND == "palette":
        palette.close()
        palette.deleteLater()
    window.close()
    window.deleteLater()
    app.processEvents()
    result["rounds"].append(measured)

OUT.write_text(json.dumps(result, indent=1), encoding="utf-8")
print("ok", OUT)
