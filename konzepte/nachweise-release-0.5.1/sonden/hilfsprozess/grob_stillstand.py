"""Abnahme RM-212: keine grobe Vorschau über 0,2 s Stillstand im Hauptfaden.

Je Modell die grobe Vorschau einer Bohrung durch die Mitte der Oberseite,
Ø 5 → 6 → 7, gerechnet wie der ``_PreviewWorker``: ``Session._preview_outcome``
in einem Nebenfaden, ``detect_features=False``. Der Hauptfaden tickt dabei alle
2 ms und misst seine längste Verspätung — das ist der Stillstand, den das
Fenster erlebt. Die erste Zahl trägt die Verkleinerung des Körpers (RM-212:
0,1–0,5 s im Hauptfaden), die weiteren rechnen am gemerkten groben Netz.

Aufruf (gebunden, aus dem Arbeitsbaum): python ../sonden/hilfsprozess/grob_stillstand.py <baum> <modell> [...]
Modelle: platte5, spiderman, schiff, eiffel, schuessel, wuerfel.
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

TREE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
sys.path.insert(0, str(TREE))
HERE = Path(__file__).resolve().parent
MODELS = {
    "platte5": HERE / "plate_holes_x5.stl",
    "spiderman": Path(r"F:\3D Dateien\spiderman+voronoi+bambu+10cm_stls\obj_1_spiderman.stl"),
    "schiff": Path(r"F:\3D Dateien\pirate+ship+with+sails_stls\obj_15_Assembly.stl"),
    "eiffel": Path(r"F:\3D Dateien\埃菲尔铁塔（高18cm+、22cm、28cm）、一体无支撑\埃菲尔铁塔18cm.stl"),
    "schuessel": Path(r"F:\3D Dateien\HydroBowl+–+Smart+Fruit+&+Veggie+Washer (1)\washing bowl v1.stl"),
    "wuerfel": Path(r"F:\3D Dateien\dice_w6_16mm_v00.stl"),
}


def main() -> None:
    home = Path(tempfile.mkdtemp(prefix="sonde-grob-"))
    for name in ("APPDATA", "LOCALAPPDATA"):
        (home / name).mkdir()
        os.environ[name] = str(home / name)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import app

    assert str(Path(app.__file__).resolve()).startswith(str(TREE)), app.__file__
    from PySide6.QtWidgets import QApplication

    QApplication.instance() or QApplication([])
    from app.core import bootstrap

    bootstrap.load_operations()
    from app.core.scene import OperationDraft
    from app.ui.session import Session

    try:
        from app.core.geom import kernel_process

        kernel_process.warm_up()  # wie ``app.ui.app.main`` hinter dem Fenster
    except ImportError:
        kernel_process = None
    print(f"app aus {app.__file__}, Hilfsprozess {'ja' if kernel_process else 'nein'}", flush=True)

    for key in sys.argv[2:]:
        path = MODELS[key]
        session = Session()
        started = time.perf_counter()
        session.import_model(path, unit="mm")
        result = session.evaluate_now()
        body, entry = max(result.scene.objects.items(), key=lambda item: item[1].mesh.triangle_count)
        low, high = entry.mesh.bounds.minimum, entry.mesh.bounds.maximum
        print(
            f"{path.name}: {entry.mesh.triangle_count} Dreiecke, geöffnet in "
            f"{time.perf_counter() - started:.1f} s",
            flush=True,
        )
        for diameter in (5.0, 6.0, 7.0):
            draft = OperationDraft(
                op="drill_hole",
                params={
                    "diameter": diameter,
                    "x": (low[0] + high[0]) / 2.0,
                    "y": (low[1] + high[1]) / 2.0,
                    "z": float(high[2]),
                    "depth": 0.0,
                },
                inputs=(body,),
            )
            seen: list[int] = []
            outcome: dict[str, object] = {}
            done = threading.Event()

            def preview(draft=draft, seen=seen, outcome=outcome, done=done) -> None:
                begun = time.perf_counter()
                _scene, difference, reason = session._preview_outcome(
                    [draft], coarsened=seen.append, detect_features=False
                )
                outcome["seconds"] = time.perf_counter() - begun
                outcome["removed"] = getattr(difference, "removed_volume", None)
                outcome["reason"] = reason
                done.set()

            late = 0.0
            worker = threading.Thread(target=preview)
            worker.start()
            while not done.is_set():
                tick = time.perf_counter()
                time.sleep(0.002)
                late = max(late, time.perf_counter() - tick - 0.002)
            worker.join()
            removed = outcome["removed"]
            print(
                f"  grob Ø{diameter:g}  {outcome['seconds']:6.2f} s  grob={bool(seen)}  "
                f"längster Stillstand {late * 1000:6.0f} ms  "
                f"abgetragen={None if removed is None else round(float(removed), 1)}",
                flush=True,
            )
        session.cancel_preview()
    if kernel_process is not None:
        print("Hilfsprozess:", kernel_process.statistics(), flush=True)
        kernel_process.shutdown()


if __name__ == "__main__":
    main()
