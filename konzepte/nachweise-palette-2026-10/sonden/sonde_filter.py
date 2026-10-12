"""Misst ``_filter`` bei Suchtext: volle Fassung gegen frühen Ausstieg, im Wechsel.

Aufruf: python sonde_filter.py <baum> <ausgabe.txt>

Beide Fassungen stehen hier, damit die Sonde auf jedem Stand nach RM-735
dasselbe misst: die volle bis ``cce701ed1``, der frühe Ausstieg ab
``023c9c703``. Je Durchgang jedes Wortpräfix einmal mit jeder Fassung, aus
demselben Ausgangszustand (leeres Feld), samt Abarbeiten der Ereignisse.
Gezählt wird die Wandzeit; die CPU-Uhr des Hauptfadens löst unter Windows nur
15,6 ms auf. Am Ende prüft die Sonde, dass beide dieselben Treffer zeigen.
"""

import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

TREE = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])

os.environ["QT_QPA_PLATFORM"] = "offscreen"
home = Path(tempfile.mkdtemp(prefix="sonde-filter-"))
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
from app.ui.selection_operations import OPEN_UP_TO  # noqa: E402
from app.ui.session import Session  # noqa: E402
from app.ui.settings import UiSettings  # noqa: E402


def full_filter(self, query=None):
    """``_filter`` bis ``cce701ed1``: rechnet die Karte auch bei Suchtext."""
    if query is not None:
        self._query = query
    found = 0
    for title, (section, toggle, buttons) in self._groups.items():
        shown = 0
        for button in buttons:
            name = str(button.property("operationName"))
            visible = (
                self._fits_the_level(name) and button.isEnabled() and name not in self._quick_shown
            )
            button.setVisible(visible)
            shown += visible
        section.setVisible(shown > 0)
        if title not in self._folded_by_hand:
            toggle.setChecked(shown <= OPEN_UP_TO)
        found += shown
    wanted = self._query.strip()
    if wanted:
        self._show_hits(wanted)
    else:
        self._say_there_is_nothing(found)
    self._arrange_groups()
    self._wrap_labels()


def early_filter(self, query=None):
    """``_filter`` ab ``023c9c703``: bei Suchtext nur Treffer und Umbruch."""
    if query is not None:
        self._query = query
    wanted = self._query.strip()
    if wanted:
        self._show_hits(wanted)
        self._wrap_labels()
        return
    full_filter(self, query)


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
window.action_function_search()
app.processEvents()
panel = window.selection_operations
panel.search.blockSignals(True)

WORDS = ("verrunden", "bohrung", "boolesch", "speichern", "qqq")
PREFIXES = [word[:end] for word in WORDS for end in range(1, len(word) + 1)]
VARIANTS = {"heute": full_filter, "frueh": early_filter}
wall: dict[str, list[float]] = {name: [] for name in VARIANTS}

# Einmal bauen, damit kein Durchgang die Zeilen bezahlt.
full_filter(panel, "a")
app.processEvents()
for round_number in range(20):
    for prefix in PREFIXES:
        order = ("heute", "frueh") if round_number % 2 == 0 else ("frueh", "heute")
        for name in order:
            # Gleicher Ausgangszustand: leeres Feld, ruhende Karte.
            full_filter(panel, "")
            app.processEvents()
            start = time.perf_counter()
            VARIANTS[name](panel, prefix)
            app.processEvents()
            wall[name].append(time.perf_counter() - start)

pairs = [early - full for full, early in zip(wall["heute"], wall["frueh"], strict=True)]
lines = [
    f"gepaart frueh-heute Median {statistics.median(pairs) * 1000:6.2f} ms"
    f"  Mittel {statistics.fmean(pairs) * 1000:6.2f} ms"
    f"  frueh schneller in {sum(pair < 0 for pair in pairs)}/{len(pairs)}"
]
for name in VARIANTS:
    lines.append(
        f"{name:6} Median {statistics.median(wall[name]) * 1000:6.2f} ms"
        f"  Mittel {statistics.fmean(wall[name]) * 1000:6.2f} ms  (n={len(wall[name])})"
    )
# Ergebnisgleichheit: dieselben Treffer in derselben Reihenfolge.
for prefix in PREFIXES:
    full_filter(panel, "")
    full_filter(panel, prefix)
    before = [panel.hits.item(row).text() for row in range(panel.hits.count())]
    full_filter(panel, "")
    early_filter(panel, prefix)
    after = [panel.hits.item(row).text() for row in range(panel.hits.count())]
    assert before == after, prefix
lines.append("Treffer gleich: ja")
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
window.close()
