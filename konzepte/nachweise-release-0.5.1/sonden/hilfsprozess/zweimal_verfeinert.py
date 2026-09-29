"""Warum zählte ``test_applying_a_large_refinement_refines_in_the_helper`` zwei Verfeinerungen?

Einmal im Lauf ``hp-nachtrag-merge-kern`` (xdist, 13 Dateien), allein und in
der eigenen Datei nie. Nachgestellt wie der Test (Ellipsoid, Schwelle null,
``run_evaluation`` im Nebenfaden) — einmal ohne und einmal mit einer
``QApplication`` im Prozess, wie sie ein früherer Test im selben
xdist-Arbeiter hinterlässt. Gezählt wird je Durchgang, dazu welche Fäden die
Verfeinerung riefen.

Aufruf (gebunden, aus dem Arbeitsbaum): python ../sonden/hilfsprozess/zweimal_verfeinert.py <baum> [qt]
"""

if __name__ == "__main__":
    import os
    import sys
    import tempfile
    import threading
    import traceback
    from pathlib import Path

    TREE = Path(sys.argv[1]).resolve()
    sys.path.insert(0, str(TREE))
    home = Path(tempfile.mkdtemp(prefix="sonde-zweimal-"))
    for name in ("APPDATA", "LOCALAPPDATA"):
        (home / name).mkdir()
        os.environ[name] = str(home / name)
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import app

    assert str(Path(app.__file__).resolve()).startswith(str(TREE)), app.__file__
    if "qt" in sys.argv[2:]:
        from PySide6.QtWidgets import QApplication

        QApplication.instance() or QApplication([])
    from app.core import bootstrap

    bootstrap.load_operations()
    from app.core.geom import kernel_process, mesh_ops
    from app.core.scene import OperationDraft
    from app.ui.session import Session

    callers: list[str] = []
    original = mesh_ops._split_conforming

    def noted(*args, **kwargs):  # noqa: ANN002, ANN003, ANN202
        stack = "".join(traceback.format_stack(limit=12)[:-1])
        callers.append(f"{threading.current_thread().name}\n{stack}")
        return original(*args, **kwargs)

    mesh_ops._split_conforming = noted
    starts: list[str] = []
    original_async = Session.evaluate_async

    def async_noted(self):  # noqa: ANN001, ANN202
        stack = "".join(traceback.format_stack(limit=8)[:-1])
        starts.append(threading.current_thread().name + chr(10) + stack)
        return original_async(self)

    Session.evaluate_async = async_noted
    kernel_process.OFFLOAD_ABOVE = 0
    corpus = TREE / "tests" / "data" / "meshes" / "near_sphere_ellipsoid.stl"
    rounds = int(os.environ.get("SONDE_RUNDEN", "3"))
    for round_number in range(rounds):
        kernel_process.shutdown()
        kernel_process._POOL.counts.clear()
        callers.clear()
        starts.clear()
        session = Session()
        assert session.import_model(corpus, unit="mm")
        session._leash.wait_all()
        before_now = len(starts)
        result = session.evaluate_now()
        print(f"  evaluate_async vor evaluate_now {before_now}, danach {len(starts)}", flush=True)
        for start in starts[before_now:]:
            print("  +++ " + start.replace(chr(10), chr(10) + "      "), flush=True)
        body = next(iter(result.scene.objects))
        session.history.apply(
            "Verfeinern", [OperationDraft(op="remesh_mesh", params={"edge": 0.8 + 0.01 * round_number}, inputs=(body,))]
        )
        box: dict[str, object] = {}
        worker = threading.Thread(target=lambda: box.setdefault("r", session.run_evaluation()))
        worker.start()
        worker.join(120)
        print(f"Durchgang {round_number}: {kernel_process.statistics()}", flush=True)
        print(f"  _split_conforming {len(callers)}-mal", flush=True)
        for caller in callers:
            print("  --- " + caller.replace(chr(10), chr(10) + "      "), flush=True)
    kernel_process.shutdown()
