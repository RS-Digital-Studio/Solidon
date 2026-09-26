"""Vorschau-Wartezeit an großen Netzen (RM-208, übernommen für RM-212): grob erstmals, grob danach, genau.

Der Baum kommt aus ``SONDE_TREE``; ohne ihn bricht die Sonde ab.

Aufruf: python probe_preview.py [--exact] [--change] datei [datei ...]

Gemessen über ``Session._preview_outcome`` wie der Dialog (``detect_features=False``),
ein Entwurf *Bohrung* durch die Mitte der Oberseite, Ø 5 → 6 → 7. Gezählt werden
die Aufrufe beider Verkleinerungen (Operation und Anzeigeweg).
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

TREE = os.environ["SONDE_TREE"]
sys.path.insert(0, TREE)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_ISOLATED = tempfile.mkdtemp(prefix="sonde-vorschau-")
for _variable in (
    "APPDATA",
    "LOCALAPPDATA",
    "HOME",
    "XDG_DATA_HOME",
    "XDG_CONFIG_HOME",
    "XDG_CACHE_HOME",
):
    os.environ[_variable] = _ISOLATED

import app  # noqa: E402

assert str(Path(app.__file__).resolve()).startswith(str(Path(TREE).resolve())), app.__file__
print("app aus", app.__file__, flush=True)

from PySide6.QtWidgets import QApplication  # noqa: E402

QT = QApplication.instance() or QApplication([])

from app.core import bootstrap  # noqa: E402

bootstrap.load_operations()

import app.core.geom.mesh_ops as mesh_ops  # noqa: E402
from app.core.scene import OperationDraft  # noqa: E402
from app.ui.session import Session  # noqa: E402

calls: list[tuple[str, float]] = []


def _wrap(name: str) -> None:
    original = getattr(mesh_ops, name, None)
    if original is None:
        return

    def counted(*args, **kwargs):
        started = time.perf_counter()
        try:
            return original(*args, **kwargs)
        finally:
            calls.append((name, time.perf_counter() - started))

    setattr(mesh_ops, name, counted)


_wrap("_decimate_with_solver")
_wrap("decimate_for_display")

args = [a for a in sys.argv[1:] if not a.startswith("--")]
exact = "--exact" in sys.argv
change = "--change" in sys.argv


def drill(body: str, entry, diameter: float) -> OperationDraft:
    bounds = entry.mesh.bounds
    low, high = bounds.minimum, bounds.maximum
    return OperationDraft(
        op="drill_hole",
        params={
            "diameter": diameter,
            "x": (low[0] + high[0]) / 2.0,
            "y": (low[1] + high[1]) / 2.0,
            "z": high[2],
            "depth": 0.0,
        },
        inputs=(body,),
    )


def run(session: Session, label: str, **kwargs) -> None:
    calls.clear()
    seen: list[int] = []
    started = time.perf_counter()
    _scene, difference, reason = session._preview_outcome(
        detect_features=False, coarsened=seen.append if kwargs.pop("coarse") else None, **kwargs
    )
    elapsed = time.perf_counter() - started
    removed = getattr(difference, "removed_volume", None)
    decimations = ", ".join(f"{name.strip('_')} {seconds:.2f} s" for name, seconds in calls)
    print(
        f"  {label:<24} {elapsed:7.2f} s  grob={bool(seen)}  "
        f"abgetragen={removed if removed is None else round(removed, 1)}  "
        f"Verkleinerung=[{decimations}]  {reason[:60]}",
        flush=True,
    )


for name in args:
    path = Path(name)
    session = Session()
    started = time.perf_counter()
    session.import_model(path, unit="mm")
    result = session.evaluate_now()
    body, entry = max(result.scene.objects.items(), key=lambda item: item[1].mesh.triangle_count)
    total = sum(item.mesh.triangle_count for item in result.scene.objects.values())
    print(
        f"{path.name}: {len(result.scene.objects)} Körper, {total} Dreiecke "
        f"(größter {entry.mesh.triangle_count}), geöffnet in {time.perf_counter() - started:.1f} s",
        flush=True,
    )
    for number, diameter in enumerate((5.0, 6.0, 7.0)):
        run(session, f"grob Ø{diameter:g}", drafts=[drill(body, entry, diameter)], coarse=True)
    if exact:
        for diameter in (5.0, 6.0):
            run(session, f"genau Ø{diameter:g}", drafts=[drill(body, entry, diameter)], coarse=False)
    if change:
        session.history.apply("Bohren", [drill(body, entry, 5.0)])
        session.evaluate_now()
        op_id = session.project.document.ops[-1].id
        for diameter in (6.0, 7.0, 8.0):
            run(
                session,
                f"ändern grob Ø{diameter:g}",
                drafts=[],
                change_op=op_id,
                change_values={"diameter": diameter},
                coarse=True,
            )
    session.release() if hasattr(session, "release") else None
    del session
