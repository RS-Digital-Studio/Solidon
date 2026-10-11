"""Misst ``_filter`` bei Suchtext: heute gegen frühen Ausstieg, im Wechsel, ein Prozess.

Aufruf: python sonde_filter.py <baum> <ausgabe.txt>

Je Durchgang jedes Wortpräfix einmal mit jeder Fassung, samt Abarbeiten der
Ereignisse; gezählt werden Wandzeit und CPU-Zeit des Hauptfadens.
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
home = Path(tempfile.mkdtemp(prefix="sonde-filter-", dir="F:/tmp-suche"))
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

full_filter = SelectionOperationsPanel._filter


def early_filter(self, query=None):
    if query is not None:
        self._query = query
    wanted = self._query.strip()
    if wanted:
        self._show_hits(wanted)
        self._wrap_labels()
        return
    full_filter(self, query)


def settle(window: MainWindow) -> None:
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
cpu: dict[str, list[float]] = {name: [] for name in VARIANTS}

# Einmal bauen, damit kein Durchgang die Zeilen bezahlt.
full_filter(panel, "a")
app.processEvents()
for _round in range(20):
    for prefix in PREFIXES:
        order = ("heute", "frueh") if _round % 2 == 0 else ("frueh", "heute")
        for name in order:
            # Gleicher Ausgangszustand: leeres Feld, ruhende Karte.
            full_filter(panel, "")
            app.processEvents()
            start_wall = time.perf_counter()
            start_cpu = time.perf_counter()
            VARIANTS[name](panel, prefix)
            app.processEvents()
            cpu[name].append(time.perf_counter() - start_cpu)
            wall[name].append(time.perf_counter() - start_wall)

lines = []
pairs = [b - a for a, b in zip(wall["heute"], wall["frueh"])]
lines.append(f"gepaart frueh-heute Median {statistics.median(pairs) * 1000:6.2f} ms  Mittel {statistics.fmean(pairs) * 1000:6.2f} ms  frueh schneller in {sum(p < 0 for p in pairs)}/{len(pairs)}")
for name in VARIANTS:
    lines.append(
        f"{name:6} Wand Median {statistics.median(wall[name]) * 1000:6.2f} ms"
        f"  Mittel {statistics.fmean(wall[name]) * 1000:6.2f} ms"
        f"  | CPU Median {statistics.median(cpu[name]) * 1000:6.2f} ms"
        f"  Mittel {statistics.fmean(cpu[name]) * 1000:6.2f} ms  (n={len(wall[name])})"
    )
# Ergebnisgleichheit: dieselben Treffer in derselben Reihenfolge.
for prefix in PREFIXES:
    full_filter(panel, "")
    full_filter(panel, prefix)
    a = [panel.hits.item(i).text() for i in range(panel.hits.count())]
    full_filter(panel, "")
    early_filter(panel, prefix)
    b = [panel.hits.item(i).text() for i in range(panel.hits.count())]
    assert a == b, prefix
lines.append("Treffer gleich: ja")
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
print("\n".join(lines))
window.close()
