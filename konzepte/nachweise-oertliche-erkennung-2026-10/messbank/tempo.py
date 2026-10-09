"""Messbank A4 (RM-592): die Erkennung nach einem Schritt an festen Stellen, in CPU-Sekunden.

Aufruf::

    python tempo.py <baum> <ausgabe.jsonl> <fall> [--gedaechtnis aus]

Fälle (Konzept §10, A4):

- ``staender``, ``eiffel``: laden wie das Fenster (``import_plan``, Auswertung mit
  Erkennung), dann einen senkrechten Zylinder Ø 6, Höhe 400, z -100 an der festen Stelle
  aus Konzept §4.2 anlegen und abziehen; gemessen wird die Erkennung dieser Auswertung.
- ``leer``: wie ``staender``, aber der Zylinder steht neben dem Körper (die wirkungslose
  Boolesche): Erkennung und ob der Merkmalscache traf.
- ``spiderman``: Netz lesen und normalisieren, kalt erkennen, dann derselbe Körper mit
  vertauschten Dreiecken 0 und 1 (die Untergrenze aus Konzept §4.2).
- ``garten``: Gartenschlauchhalter, *Merkmal verschieben* an ``hole_10``, ``hole_4``,
  ``hole_9`` übernehmen (Sonde ``p08_schritte.py``); je Schritt die Erkennung.

Je Fall eine Zeile: CPU der Erkennung nach dem Schritt (``process_time``, alle Fäden),
CPU je Stufe (äußerste Ebene), der Abdruck der Erkennung Bit für Bit (Gleichheit gegen
den Ausgangsstand), die Wanduhr daneben.
"""

from __future__ import annotations

import functools
import hashlib
import importlib
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _baum

ARGS = sys.argv[1:]
TREE = _baum.setup(ARGS[0])
_baum.activation_free()

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402
from app.core.geom.mesh import MeshData, as_mesh_data, read_mesh  # noqa: E402
from app.core.ingest.loader import normalise  # noqa: E402
from app.core.ingest.plan import import_plan  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.perceive import features as feats  # noqa: E402
from app.core.scene import History, evaluate  # noqa: E402
from app.core.scene.cache import ResultCache, feature_to_data  # noqa: E402
from app.core.scene.history import OperationDraft  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Source  # noqa: E402

load_operations()
EVALUATE = importlib.import_module("app.core.scene.evaluate")
OUTPUT = Path(ARGS[1])
CASE = ARGS[2]
if "--gedaechtnis" in ARGS and ARGS[ARGS.index("--gedaechtnis") + 1] == "aus":
    if hasattr(feats, "remember_across_bodies"):
        feats.remember_across_bodies(False)
    else:
        feats._by_geometry = lambda name, body, support, compute, *read: compute()
        feats._answered_by_geometry = lambda name, support, *read: False

RISER = _baum.KUNDE / "parametric-laptop-riser.stl"
EIFFEL = (
    _baum.KUNDE / "埃菲尔铁塔（高18cm+、22cm、28cm）、一体无支撑" / "埃菲尔铁塔18cm_repariert.stl"  # noqa: RUF001
)
SPIDER = _baum.KUNDE / "spiderman+voronoi+bambu+10cm_stls" / "obj_1_spiderman.stl"
GARDEN = _baum.KUNDE / "garden-hose-holder.3mf"
#: Die festen Stellen aus Konzept §4.2 (``probe_local.py --at auto --rank 0``).
SPOTS = {"staender": (-87.9, -6.8), "eiffel": (-34.2, 2.1)}

STAGES = (
    "_one_body",
    "_large_facet_faces",
    "_fitted",
    "_connected_patches",
    "_screening",
    "curvature_jumps",
    "_split_patches_by_curvature",
    "_tangential_pieces",
    "find_helices",
    "_merged_cylinders",
    "_read_surface_support",
    "detect_holes",
    "detect_edge_loops",
    "slots_instead_of_half_bores",
    "patterns_instead_of_cells",
    "_faces_finished_in",
    "_detect_voids",
    "_corners_named_as_fillets",
    "narrowings_marked",
    "detect_curved_faces",
)
SPENT: dict[str, float] = {}
CALLS: Counter[str] = Counter()
STACK: list[str] = []
ARMED = [False]


def watch(name: str) -> None:
    """Eine Stufe in CPU-Sekunden zählen, nur auf ihrer äußersten Ebene."""
    original = getattr(feats, name, None)
    if original is None:
        return

    @functools.wraps(original)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if not ARMED[0]:
            return original(*args, **kwargs)
        CALLS[name] += 1
        if name in STACK:
            return original(*args, **kwargs)
        STACK.append(name)
        started = time.process_time()
        try:
            return original(*args, **kwargs)
        finally:
            SPENT[name] = SPENT.get(name, 0.0) + time.process_time() - started
            STACK.pop()

    setattr(feats, name, wrapped)


for stage in STAGES:
    watch(stage)

DETECTED: list[tuple[float, float]] = []
_shipped_detect = EVALUATE.detect


def timed_detect(mesh: Any, **kwargs: Any) -> Any:
    """Die Erkennung der Auswertung: CPU und Wanduhr."""
    cpu, wall = time.process_time(), time.perf_counter()
    try:
        return _shipped_detect(mesh, **kwargs)
    finally:
        DETECTED.append((time.process_time() - cpu, time.perf_counter() - wall))


EVALUATE.detect = timed_detect


def exact(value: Any) -> Any:
    """Werte für den Abdruck: Gleitkommazahlen als Hex, Bit für Bit."""
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, dict):
        return {str(key): exact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [exact(item) for item in value]
    return value


def fingerprint(found: dict[str, Any] | None) -> str | None:
    """Der Abdruck einer rohen Erkennung über ``feature_to_data``."""
    if found is None:
        return None
    rows = [[name, exact(feature_to_data(found[name]))] for name in sorted(found)]
    text = json.dumps(rows, sort_keys=True, default=repr)
    return hashlib.blake2b(text.encode("utf-8"), digest_size=12).hexdigest()


def ask(question: Any, choices: Any) -> Any:
    for choice in choices:
        if str(choice).startswith("Sofort"):
            return choice
    return choices[0]


class Project:
    """Ein geladenes Modell im Kernweg des Fensters."""

    def __init__(self, path: Path) -> None:
        payload = path.read_bytes()
        self.project = new_project("centauri-carbon-2", "petg")
        self.project.document.sources["src_1"] = Source(
            id="src_1", kind="import", path=f"sources/model{path.suffix.lower()}", sha256=""
        )
        self.project.sources["src_1"] = payload
        plan = import_plan("src_1", path.name, payload, "mm", first_model=True)
        self.history = History(self.project.document)
        self.history.apply("Laden", [plan.draft])
        self.profile = profiles.make_profile("centauri-carbon-2", "petg")
        self.sources = ProjectSources(self.project)
        self.cache = ResultCache()

    def run(self) -> Any:
        return evaluate(
            self.project.document, self.profile, sources=self.sources, ask=ask, cache=self.cache
        )


def measured(work: Any) -> dict[str, Any]:
    """Eine Auswertung nach dem Schritt, mit Stufen und Erkennung gezählt."""
    SPENT.clear()
    CALLS.clear()
    DETECTED.clear()
    ARMED[0] = True
    cpu, wall = time.process_time(), time.perf_counter()
    try:
        result = work()
    finally:
        ARMED[0] = False
    return {
        "cpu_gesamt": round(time.process_time() - cpu, 3),
        "wand_gesamt": round(time.perf_counter() - wall, 3),
        "cpu_erkennung": round(sum(entry[0] for entry in DETECTED), 3),
        "wand_erkennung": round(sum(entry[1] for entry in DETECTED), 3),
        "erkennungen": len(DETECTED),
        "stufen": {name: round(value, 3) for name, value in sorted(SPENT.items())},
        "aufrufe": dict(CALLS),
        "_ergebnis": result,
    }


def bore(case: str) -> list[dict[str, Any]]:
    """Ständer, Eiffelturm oder die wirkungslose Boolesche."""
    project = Project(EIFFEL if case == "eiffel" else RISER)
    loaded = project.run()
    ids = list(loaded.scene.objects)
    body = as_mesh_data(loaded.scene.objects[ids[0]].mesh)
    if case == "leer":
        _low, high = (np.asarray(value, dtype=float) for value in body.raw.bounds)
        x, y = float(high[0]) + 20.0, float(high[1]) + 20.0
    else:
        x, y = SPOTS[case]
    project.history.apply(
        "Zylinder",
        [
            OperationDraft(
                op="create_cylinder",
                params={"diameter": 6.0, "height": 400.0, "z": -100.0, "x": x, "y": y},
            )
        ],
    )
    tool = [key for key in project.run().scene.objects if key not in ids][-1]
    project.history.apply(
        "Abziehen", [OperationDraft(op="subtract_objects", inputs=(ids[0], tool))]
    )
    row = measured(project.run)
    after = as_mesh_data(row.pop("_ergebnis").scene.objects[ids[0]].mesh)
    row["dreiecke"] = after.triangle_count
    row["abdruck"] = fingerprint(feats.known_detection(after))
    row["dasselbe_netz"] = feats._mesh_key(after) == feats._mesh_key(body)
    return [row]


def spiderman() -> list[dict[str, Any]]:
    """Kalt erkennen, dann zwei vertauschte Dreiecke — die Untergrenze."""
    mesh = normalise(read_mesh(SPIDER.read_bytes(), ".stl"), "mm").mesh
    feats.forget_cache()
    cold = measured(lambda: feats.detect(mesh))
    cold.pop("_ergebnis")
    faces = np.asarray(mesh.raw.faces).copy()
    faces[[0, 1]] = faces[[1, 0]]
    twin = MeshData.of(trimesh.Trimesh(np.asarray(mesh.raw.vertices).copy(), faces, process=False))
    row = measured(lambda: feats.detect(twin))
    found = row.pop("_ergebnis")
    row["cpu_erkennung"] = row["cpu_gesamt"]
    row["wand_erkennung"] = row["wand_gesamt"]
    row["abdruck"] = fingerprint(found)
    row["kalt"] = cold["cpu_gesamt"]
    return [row]


def garden() -> list[dict[str, Any]]:
    """*Merkmal verschieben* am Gartenschlauchhalter, drei Bohrungen nacheinander."""
    project = Project(GARDEN)
    result = project.run()
    entry = next(iter(result.scene.objects.values()))
    rows = []
    for step, name in enumerate(("hole_10", "hole_4", "hole_9"), start=1):
        if name not in entry.features:
            rows.append({"schritt": name, "fehlt": True})
            continue
        bore_feature = entry.features[name]
        axis = np.asarray(bore_feature.params["axis"], dtype=float)
        helper = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
        across = np.cross(axis, helper)
        across /= np.linalg.norm(across)
        target = np.asarray(bore_feature.params["centre"], dtype=float) + across
        project.history.apply(
            f"Versetzen {name}",
            [
                OperationDraft(
                    op="move_feature",
                    inputs=(entry.id,),
                    params={
                        "at_feature": name,
                        "x": float(target[0]),
                        "y": float(target[1]),
                        "z": float(target[2]),
                    },
                    seed=step,
                )
            ],
        )
        row = measured(project.run)
        result = row.pop("_ergebnis")
        entry = next(iter(result.scene.objects.values()))
        mesh = as_mesh_data(entry.mesh)
        row["schritt"] = name
        row["dreiecke"] = mesh.triangle_count
        row["abdruck"] = fingerprint(feats.known_detection(mesh))
        rows.append(row)
    return rows


def main() -> None:
    if CASE in ("staender", "eiffel", "leer"):
        rows = bore(CASE)
    elif CASE == "spiderman":
        rows = spiderman()
    elif CASE == "garten":
        rows = garden()
    else:
        raise SystemExit(f"unbekannter Fall {CASE}")
    with OUTPUT.open("a", encoding="utf-8") as out:
        for row in rows:
            row.update({"fall": CASE, "baum": TREE.name})
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            print(
                CASE,
                row.get("schritt", ""),
                "Erkennung CPU",
                row.get("cpu_erkennung"),
                "Abdruck",
                row.get("abdruck"),
                flush=True,
            )
    import os

    os._exit(0)


if __name__ == "__main__":
    main()
