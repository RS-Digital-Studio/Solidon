"""Genaue Vorschau von *Bohrung ändern* an der Senkplatte (RM-212, dritter Posten).

Übernommen aus ``rm-212-2026-09-26/probe_profile_exact.py``: Modell lesen wie die
Anwendung, die erste Bohrung wählen, ``resize_hole`` auf Ø 6 / 6,5 / 7
vorschauen wie der Dialog (``detect_features=False``, genau, ohne grobe Stufe) —
aber aus einem Nebenfaden wie der ``_PreviewWorker``, mit dem längsten
Stillstand des Hauptfadens daneben, und der mittlere Lauf profiliert (im
Nebenfaden). Ob der Hilfsprozess die Zeit löst, sagt die Dauer; wohin sie
geht, das Profil.

Modell: ``plate_countersunk_x5.stl`` (Korpus ``plate_countersunk.stl`` fünfmal
geteilt, 393 216 Facetten in der Datei, nach dem Import 311 296 Dreiecke — so
viele wie die Platte aus RM-212, deren Quelle nicht mehr da ist).

Aufruf (gebunden, aus dem Arbeitsbaum): python ../sonden/hilfsprozess/senkplatte.py <baum>
"""

from __future__ import annotations

import cProfile
import io
import os
import pstats
import sys
import tempfile
import threading
import time
from pathlib import Path

TREE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
sys.path.insert(0, str(TREE))
MODEL = Path(__file__).resolve().parent / "plate_countersunk_x5.stl"


def main() -> None:
    home = Path(tempfile.mkdtemp(prefix="sonde-senk-"))
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

        if "improzess" in sys.argv[2:]:
            kernel_process.OFFLOAD_ABOVE = 10**12
        else:
            kernel_process.warm_up()
        if "normal" in sys.argv[2:]:
            # Gegenprobe: den vorab gestarteten Hilfsprozess zurück auf normale
            # Priorität (NORMAL_PRIORITY_CLASS), von außen über seinen Griff.
            import ctypes

            kernel32 = ctypes.WinDLL("kernel32")
            kernel32.SetPriorityClass.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
            for helper in kernel_process.processes():
                handle = helper._popen._handle  # noqa: SLF001
                print("normal:", kernel32.SetPriorityClass(ctypes.c_void_p(int(handle)), 0x20), flush=True)
    except ImportError:
        kernel_process = None
    print(f"Variante: {sys.argv[2:]}", flush=True)
    session = Session()
    started = time.perf_counter()
    session.import_model(MODEL, unit="mm")
    result = session.evaluate_now()
    body, entry = next(iter(result.scene.objects.items()))
    holes = sorted(name for name, feature in entry.features.items() if feature.kind == "hole")
    print(
        f"app aus {app.__file__}; {MODEL.name}: {entry.mesh.triangle_count} Dreiecke, "
        f"dicht={entry.mesh.is_watertight}, {len(entry.features)} Merkmale, Bohrungen {holes}, "
        f"geöffnet in {time.perf_counter() - started:.1f} s",
        flush=True,
    )
    hole = holes[0]
    print(f"  {hole}: Ø {entry.features[hole].params.get('diameter')}", flush=True)
    profile_text = ""
    for number, diameter in enumerate((6.0, 6.5, 7.0)):
        draft = OperationDraft(
            op="resize_hole", params={"at_feature": hole, "diameter": diameter}, inputs=(body,)
        )
        outcome: dict[str, object] = {}
        done = threading.Event()

        def preview(draft=draft, outcome=outcome, done=done, profiled=number == 1) -> None:
            profile = cProfile.Profile() if profiled and "profil" in sys.argv[2:] else None
            begun = time.perf_counter()
            if profile is not None:
                profile.enable()
            _scene, difference, reason = session._preview_outcome([draft], detect_features=False)
            if profile is not None:
                profile.disable()
                text = io.StringIO()
                pstats.Stats(profile, stream=text).sort_stats("cumulative").print_stats(40)
                outcome["profile"] = text.getvalue()
            outcome["seconds"] = time.perf_counter() - begun
            outcome["removed"] = getattr(difference, "removed_volume", None)
            outcome["added"] = getattr(difference, "added_volume", None)
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
        removed, added = outcome["removed"], outcome["added"]
        print(
            f"  Ø{diameter:g}: {outcome['seconds']:.2f} s, längster Stillstand {late * 1000:.0f} ms, "
            f"abgetragen={None if removed is None else round(float(removed), 3)}, "
            f"dazu={None if added is None else round(float(added), 3)} {outcome['reason'][:50]}",
            flush=True,
        )
        profile_text = str(outcome.get("profile", profile_text))
    print(profile_text, flush=True)
    if kernel_process is not None:
        print("Hilfsprozess:", kernel_process.statistics(), flush=True)
        kernel_process.shutdown()


if __name__ == "__main__":
    main()
