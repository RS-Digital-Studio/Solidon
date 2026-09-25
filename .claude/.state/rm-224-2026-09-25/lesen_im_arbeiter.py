"""Sonde RM-224: ``open_path`` liest und plant ein Modell außerhalb des Hauptthreads.

Zwei Teile, beide ohne pytest (Fenstertests laufen erst beim Release):

1. Die drei Lagen der neuen Fenstertests an einer echten ``Session`` —
   gelesen im Arbeiter, unlesbare Datei als Hinweis, verspätete Lesung nach
   einem Projektwechsel. Im alten Baum sind die ersten beiden anders.
2. Die längste Lücke im Hauptthread, während ``MainWindow.open_path`` ein
   Modell öffnet: ein 5-ms-Takt im Hauptthread, gemessen vom Aufruf bis zur
   ersten Antwort der Sitzung (``importFinished``), mehrmals.

Aufruf: python lesen_im_arbeiter.py <baum> <modell> [--runs N]
"""

from __future__ import annotations

import os
import statistics
import sys
import tempfile
import time
from pathlib import Path

TREE = Path(sys.argv[1])
sys.path.insert(0, str(TREE))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import app.ui  # noqa: E402  — setzt die PySide-Vorgabe vor dem ersten Qt-Import

where = str(Path(app.ui.__file__).resolve())
if not where.startswith(str(TREE.resolve())):
    raise SystemExit(f"falscher Baum geladen: {where}")
print(f"gemessen wird {where}")

from PySide6.QtCore import QElapsedTimer, QEventLoop, QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402

application = QApplication.instance() or QApplication([])
# Wie ``app.ui.app.main``: Ohne das volle Register baut das Fenster keine Menüs.
load_operations()

from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.session import Session  # noqa: E402
from app.ui.settings import UiSettings  # noqa: E402

MODEL = Path(sys.argv[2])
RUNS = int(sys.argv[sys.argv.index("--runs") + 1]) if "--runs" in sys.argv else 5


def settle(session: Session, call: object, seconds: float = 60.0) -> dict[str, object]:
    """``call`` ausführen und seine Antwort abwarten — auch eine, die im Aufruf kommt.

    Der alte Stand antwortet synchron; verbunden wird deshalb vor dem Aufruf,
    und gewartet nur, wenn noch nichts da ist.
    """
    seen: dict[str, object] = {}
    loop = QEventLoop()
    session.importFinished.connect(lambda ok: (seen.update(accepted=ok), loop.quit()))
    session.importFailed.connect(lambda error: (seen.update(error=error), loop.quit()))
    QTimer.singleShot(int(seconds * 1000), loop.quit)
    call()  # type: ignore[operator]
    if not seen:
        loop.exec()
    return seen


# --- 1. Die drei Lagen --------------------------------------------------------
folder = Path(tempfile.mkdtemp())
cube = folder / "wuerfel.stl"
cube.write_bytes(MODEL.read_bytes() if MODEL.suffix.lower() == ".stl" else b"")
if not cube.read_bytes():
    import trimesh

    trimesh.creation.box(extents=(10, 10, 10)).export(cube)

session = Session()
embedded: list[bool] = []


def first_call() -> None:
    session.import_model_async(cube)
    embedded.append(bool(session.project.document.sources))


seen = settle(session, first_call)
embedded_at_once = embedded[0]
print(
    f"Lage 1: sofort eingebettet {embedded_at_once}, angenommen {seen.get('accepted')}, "
    f"Schritte {[entry.op for entry in session.project.document.ops]}"
)
session.release()

session = Session()
try:
    seen = settle(session, lambda: session.import_model_async(folder / "verschoben.stl"))
    error = seen.get("error")
    print(
        f"Lage 2: {type(error).__name__}: {getattr(error, 'title', '')} — "
        f"{[action.id for action in getattr(error, 'suggestions', ())]}"
    )
except Exception as problem:  # der alte Baum wirft im Aufruf
    print(f"Lage 2: geworfen im Aufruf — {type(problem).__name__}: {problem}")
session.release()

session = Session()
session.import_model_async(cube)
session.start_new("centauri-carbon-2", "petg")
idle = session.wait_for_idle(20_000)
print(
    f"Lage 3: Leerlauf {idle}, Quellen {list(session.project.document.sources)}, "
    f"Schritte {[entry.op for entry in session.project.document.ops]}"
)
session.release()

# --- 2. Die längste Lücke im Hauptthread -------------------------------------
def longest_gap() -> float:
    """Ein ``open_path`` bis zur ersten Antwort, mit Takt im Hauptthread."""
    window = MainWindow(Session(), UiSettings())
    ticker = QTimer()
    ticker.setInterval(5)
    clock = QElapsedTimer()
    last = [0.0]
    worst = [0.0]

    def tick() -> None:
        now = clock.nsecsElapsed() / 1e6
        worst[0] = max(worst[0], now - last[0])
        last[0] = now

    ticker.timeout.connect(tick)
    answered = QEventLoop()
    done: list[bool] = []

    def answer(*_args: object) -> None:
        done.append(True)
        answered.quit()

    window.session.importFinished.connect(answer)
    window.session.importFailed.connect(answer)
    clock.start()
    ticker.start()
    started = time.perf_counter()
    window.open_path(MODEL)
    # Was der Aufruf selbst im Hauptthread hielt, zählt als erste Lücke —
    # im alten Stand kommt die Antwort schon darin.
    worst[0] = max(worst[0], (time.perf_counter() - started) * 1000.0)
    last[0] = clock.nsecsElapsed() / 1e6
    if not done:
        QTimer.singleShot(120_000, answered.quit)
        answered.exec()
    ticker.stop()
    window.session.wait_for_idle(120_000)
    window.release()
    window.deleteLater()
    application.processEvents()
    return worst[0]


gaps: list[float] = []
for _run in range(RUNS):
    gaps.append(longest_gap())
    print(f"  Lauf: längste Lücke bis zur Antwort {gaps[-1]:.0f} ms")
print(f"{MODEL.name}: Median der längsten Lücke {statistics.median(gaps):.0f} ms")
