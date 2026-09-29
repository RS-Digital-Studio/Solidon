"""Wie lange hält die Merkmalsbuchhaltung an 5,8 Mio. Dreiecken den GIL? (RM-212, Nachgang)

Nach dem Hilfsprozess stehen beim Übernehmen von *Kanten verfeinern* am
Spielwürfel (0,05 mm) noch Lücken von 0,2 bis 0,8 s im Qt-Takt — keine davon
in ``manifold3d`` (``fenster-nachher-wuerfel3``). Diese Sonde misst die
Verdächtigen einzeln an genau diesem Netz und seinen Merkmalen: Dauer und
längster Stillstand eines 2-ms-Taktfadens, während die Funktion im Hauptfaden
rechnet. Dazu der Abdruck des Ergebnisses — ein Umbau muss dasselbe liefern.

Das feine Netz samt Merkmalen wird einmal gerechnet und abgelegt
(``wuerfel-fein.pkl``); jeder weitere Lauf liest es.

Aufruf (gebunden, aus dem Arbeitsbaum): python ../sonden/hilfsprozess/buchhaltung.py <baum> <ausgabe.json>
"""

from __future__ import annotations

import hashlib
import json
import pickle
import sys
import threading
import time
from pathlib import Path

TREE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
sys.path.insert(0, str(TREE))
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("buchhaltung.json")
CACHE = Path(__file__).resolve().parent / "wuerfel-fein.pkl"
MODEL = Path(r"F:\3D Dateien\dice_w6_16mm_v00.stl")


class Ticker:
    def __init__(self) -> None:
        self.late = 0.0
        self.done = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        while not self.done.is_set():
            started = time.perf_counter()
            time.sleep(0.002)
            self.late = max(self.late, time.perf_counter() - started - 0.002)

    def __enter__(self) -> Ticker:
        self.thread.start()
        time.sleep(0.03)
        self.late = 0.0
        self.started = time.perf_counter()
        return self

    def __exit__(self, *_exc: object) -> None:
        self.spent = time.perf_counter() - self.started
        self.done.set()
        self.thread.join()


def fingerprint(value: object) -> str:
    return hashlib.sha256(repr(value).encode("utf-8")).hexdigest()[:16]


def fine_body():
    import numpy as np
    import trimesh

    from app.core.geom.mesh import MeshData

    if CACHE.is_file():
        with CACHE.open("rb") as stream:
            vertices, faces, units, features, coarse, coarse_count = pickle.load(stream)
        body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        if units is not None:
            from app.core.geom.mesh import remember_refined_units

            remember_refined_units(body, units)
        return MeshData.of(body), features, units, coarse, coarse_count
    from app.core.scene import OperationDraft
    from app.ui.session import Session

    session = Session()
    assert session.import_model(MODEL, unit="mm")
    result = session.evaluate_now()
    body, first = next(iter(result.scene.objects.items()))
    coarse, coarse_count = dict(first.features), first.mesh.triangle_count
    session.history.apply(
        "Verfeinern", [OperationDraft(op="remesh_mesh", params={"edge": 0.05}, inputs=(body,))]
    )
    result = session.evaluate_now()
    entry = next(iter(result.scene.objects.values()))
    from app.core.geom.mesh import refined_units

    units = refined_units(entry.mesh.raw)
    with CACHE.open("wb") as stream:
        pickle.dump(
            (
                np.asarray(entry.mesh.raw.vertices),
                np.asarray(entry.mesh.raw.faces),
                None if units is None else np.asarray(units),
                dict(entry.features),
                coarse,
                coarse_count,
            ),
            stream,
        )
    return entry.mesh, dict(entry.features), units, coarse, coarse_count


def main() -> None:
    import numpy as np

    import app

    assert str(Path(app.__file__).resolve()).startswith(str(TREE)), app.__file__
    from app.core import bootstrap

    bootstrap.load_operations()
    mesh, features, units, coarse, coarse_count = fine_body()
    sizes = sorted((len(feature.face_indices) for feature in features.values()), reverse=True)
    print(
        f"{mesh.triangle_count} Dreiecke, {len(features)} Merkmale, größte {sizes[:6]}", flush=True
    )
    from app.core.geom import mesh as mesh_module
    from app.core.perceive import features as features_module
    from app.core.perceive import local
    from app.core.scene import hashing

    results: dict[str, dict[str, object]] = {}

    def measured(name: str, work) -> None:
        with Ticker() as ticker:
            value = work()
        results[name] = {
            "sekunden": round(ticker.spent, 3),
            "stillstand_ms": round(ticker.late * 1000),
            "abdruck": fingerprint(value),
        }
        print(
            f"  {name:<34} {ticker.spent * 1000:8.0f} ms, längster Stillstand "
            f"{ticker.late * 1000:6.0f} ms, Abdruck {results[name]['abdruck']}",
            flush=True,
        )

    measured("features._mesh_key", lambda: features_module._mesh_key(mesh))
    measured(
        "hashing.feature_digest (alle)",
        lambda: [hashing.feature_digest(feature, name) for name, feature in sorted(features.items())],
    )
    measured("local._known_key", lambda: local._known_key(mesh, features, None, ()))
    measured("local._numbered", lambda: sorted(local._numbered(list(features.values())).items()))
    measured("mesh.enclosed_volume", lambda: mesh_module.enclosed_volume(mesh.raw).hex())
    if units is not None:
        origin = np.asarray(units, dtype=np.int64)
        measured(
            "features.refined_features",
            lambda: sorted(features_module.refined_features(coarse, origin, coarse_count).items()),
        )
    slots = tuple(range(3)) * (mesh.triangle_count // 3 + 1)
    largest = max(features.values(), key=lambda feature: len(feature.face_indices))

    def panel_slots_old(slots=slots) -> object:
        return sorted({slots[face] if slots else 0 for face in largest.face_indices})

    def panel_slots_new(slots=slots) -> object:
        # Wie ``panels.show_scene`` nach dem Umbau.
        return sorted(
            {slots[face] for face in largest.face_indices}
            if slots
            else ({0} if largest.face_indices else set())
        )

    measured("panels Slots alt (mit Slots)", panel_slots_old)
    measured("panels Slots neu (mit Slots)", panel_slots_new)
    measured("panels Slots alt (ohne Slots)", lambda: panel_slots_old(()))
    measured("panels Slots neu (ohne Slots)", lambda: panel_slots_new(()))
    measured("mesh.component_count", lambda: mesh_module.face_components(mesh.raw).__len__())
    OUT.write_text(json.dumps(results, indent=1, sort_keys=True), encoding="utf-8")


if __name__ == "__main__":
    main()
