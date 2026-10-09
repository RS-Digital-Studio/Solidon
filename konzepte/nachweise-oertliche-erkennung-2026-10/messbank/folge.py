"""Messbank A1/A2 (RM-592): die Schrittfolge aus Konzept §10 über den Korpus.

Aufruf::

    python folge.py <baum> <ausgabe.jsonl> [--gedaechtnis an|aus] [--weglassen TEIL]
        [--pruefen] [--min N] [--max N] [--objekte N] <fall> [<fall> ...]

``<fall>`` ist eine Modelldatei oder ``beispiel:<kennung>`` (ein Beispielprojekt) oder
``@liste.txt`` (je Zeile ein Fall). Je Fall wie im Fenster: ein Projekt, Laden über
``import_plan`` (Beispiele: ``load``), Auswertung in voller Güte mit Erkennung und
Ergebniscache. Dann je Netzkörper zwischen ``--min`` und ``--max`` Dreiecken (höchstens
``--objekte`` je Fall, die größten zuerst) die Folge über ``History.apply``:

1. Bohrung Ø 3, 2 mm tief, achsparallel, an drei Stellen (Mitte des größten Dreiecks der
   drei größten achsparallelen ebenen Flächen),
2. die erste Bohrung 1 mm quer versetzen, 3. auf Ø 4 aufweiten, 4. entfernen,
5. einen Quader an der Kante (größtes x, größtes y) über die ganze Höhe abziehen,
6. einen Zapfen oben aufsetzen und vereinen, 7. oben 15 % abschneiden,
8. um 5 mm verschieben und 9. erneut bohren.

Nach jedem Schritt eine Zeile je Zustand: der Abdruck der rohen Erkennung Bit für Bit
(``feature_to_data`` jedes Merkmals, Maße als Hex) samt Nebentabellen, die Namen der Szene
und ``object_hash(features=)``, ob das ferne Merkmal unter seinem Namen weiterlebt (A2),
CPU der Erkennung und der Auswertung, Treffer und Rechnungen je gemerkter Frage. Die
Bohrung wird an ihrer Lage gesucht, nicht am Namen.

``--gedaechtnis aus`` schaltet jedes Gedächtnis über die Körpergrenze ab (die Kontrolle):
den Testhaken ``features.remember_across_bodies`` wo es ihn gibt, sonst ``_by_geometry``
als Rechnung. ``--weglassen TEIL`` lässt einen Schlüsselteil weg (Gegenprobe, A1).
``--pruefen`` rechnet je Zustand dieselbe Erkennung an einer Kopie ohne Gedächtnis und
ohne Erkennungscache nach (``kopie_gleich``) — die Zeiten zählen dann nicht.
"""

from __future__ import annotations

import hashlib
import importlib
import json
import os
import sys
import threading
import time
import traceback
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
from app.core.geom.mesh import MeshData, as_mesh_data  # noqa: E402
from app.core.ingest.plan import import_plan  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.perceive import features as feats  # noqa: E402
from app.core.perceive import matching  # noqa: E402
from app.core.scene import History, evaluate  # noqa: E402
from app.core.scene.cache import ResultCache, feature_to_data  # noqa: E402
from app.core.scene.hashing import object_hash  # noqa: E402
from app.core.scene.history import OperationDraft  # noqa: E402
from app.core.scene.project import ProjectSources, load, new_project  # noqa: E402
from app.core.types import Source  # noqa: E402

load_operations()
EVALUATE = importlib.import_module("app.core.scene.evaluate")


def option(name: str, default: str | None = None) -> str | None:
    """Der Wert hinter ``--name`` oder die Vorgabe."""
    if name in ARGS:
        return ARGS[ARGS.index(name) + 1]
    return default


OUTPUT = Path(ARGS[1])
MEMORY = option("--gedaechtnis", "an")
LEAVE_OUT = option("--weglassen")
CHECK = "--pruefen" in ARGS
MINIMUM = int(option("--min", "1000") or 1000)
MAXIMUM = int(option("--max", "1000000") or 1000000)
PER_CASE = int(option("--objekte", "8") or 8)
VALUED = {"--gedaechtnis", "--weglassen", "--min", "--max", "--objekte"}
CASES: list[str] = []
skip = False
for argument in ARGS[2:]:
    if skip:
        skip = False
        continue
    if argument in VALUED:
        skip = True
        continue
    if argument.startswith("--"):
        continue
    if argument.startswith("@"):
        listed = Path(argument[1:]).read_text(encoding="utf-8").splitlines()
        CASES.extend(line.strip() for line in listed if line.strip())
    else:
        CASES.append(argument)

# --- Gedächtnis an/aus und Gegenprobe ------------------------------------------------

if MEMORY == "aus":
    if hasattr(feats, "remember_across_bodies"):
        feats.remember_across_bodies(False)
    else:
        feats._by_geometry = lambda name, body, support, compute, *read: compute()
        feats._answered_by_geometry = lambda name, support, *read: False
if LEAVE_OUT:
    hook = getattr(feats, "_leave_out_for_counterproof", None)
    if hook is None:
        raise SystemExit(f"dieser Baum kennt keine Gegenprobe ({LEAVE_OUT})")
    hook(LEAVE_OUT)

# --- Zähler -------------------------------------------------------------------------

PHASE = {"name": "op"}
SPENT: Counter[str] = Counter()
ANSWERS: Counter[str] = Counter()
ASKED = [0]
_shipped_detect = EVALUATE.detect


def timed_detect(mesh: Any, **kwargs: Any) -> Any:
    """Die Erkennung der Auswertung, in CPU-Sekunden gezählt."""
    started = time.process_time()
    PHASE["name"] = "detect"
    try:
        return _shipped_detect(mesh, **kwargs)
    finally:
        PHASE["name"] = "op"
        SPENT["detect"] += time.process_time() - started


EVALUATE.detect = timed_detect
_shipped_match = matching.match


def counted_match(*args: Any, **kwargs: Any) -> Any:
    """Jede Zuordnungsfrage zählt (A2)."""
    SPENT["match_calls"] += 1
    return _shipped_match(*args, **kwargs)


matching.match = counted_match
if hasattr(EVALUATE, "match"):
    EVALUATE.match = counted_match


def counting(name: str) -> None:
    """Treffer und Rechnungen einer gemerkten Ablage zählen, wo der Baum sie hat."""
    shipped = getattr(feats, name, None)
    if shipped is None:
        return

    def wrapped(question: str, *args: Any, **kwargs: Any) -> Any:
        ran: list[bool] = []
        args = list(args)
        position = next((number for number, value in enumerate(args) if callable(value)), None)
        if position is not None:
            compute = args[position]

            def watched() -> Any:
                ran.append(True)
                return compute()

            args[position] = watched
        value = shipped(question, *args, **kwargs)
        ANSWERS[f"{PHASE['name']} {question} {'gerechnet' if ran else 'Treffer'}"] += 1
        return value

    setattr(feats, name, wrapped)


if MEMORY == "an":
    for memo in ("_by_geometry", "_by_patch_print"):
        counting(memo)


def ask(question: Any, choices: Any) -> Any:
    """Erste Wahl, gezählt; die Frage vor der langen Vollerkennung wird bejaht."""
    ASKED[0] += 1
    for choice in choices:
        if str(choice).startswith("Sofort"):
            return choice
    return choices[0]


# --- Abdrücke ----------------------------------------------------------------------


def exact(value: Any) -> Any:
    """Werte für den Abdruck: Gleitkommazahlen als Hex, Bit für Bit."""
    if isinstance(value, float):
        return value.hex()
    if isinstance(value, dict):
        return {str(key): exact(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [exact(item) for item in value]
    return value


def detection_print(found: dict[str, Any] | None) -> str | None:
    """Der Abdruck einer rohen Erkennung über ``feature_to_data``, Bit für Bit."""
    if found is None:
        return None
    rows = [[name, exact(feature_to_data(found[name]))] for name in sorted(found)]
    text = json.dumps(rows, sort_keys=True, default=repr)
    return hashlib.blake2b(text.encode("utf-8"), digest_size=12).hexdigest()


def scene_print(features: dict[str, Any]) -> tuple[str, str]:
    """Namen samt Merkmalen der Szene und ``object_hash(features=)``."""
    rows = [[name, exact(feature_to_data(features[name]))] for name in sorted(features)]
    text = json.dumps(rows, sort_keys=True, default=repr)
    names = hashlib.blake2b(text.encode("utf-8"), digest_size=12).hexdigest()
    return names, object_hash("messbank", 0, features=features)


def fresh_detection(mesh: MeshData) -> dict[str, Any]:
    """Dieselbe Erkennung an einer Kopie, ohne Erkennungscache und ohne jedes Gedächtnis."""
    raw = mesh.raw
    copy = MeshData.of(
        trimesh.Trimesh(
            np.array(raw.vertices, dtype=np.float64, copy=True),
            np.array(raw.faces, dtype=np.int64, copy=True),
            process=False,
        )
    )
    shipped_cached = feats._cached_detection
    feats._cached_detection = lambda key: None
    switch = getattr(feats, "remember_across_bodies", None)
    shipped_geometry = feats._by_geometry
    shipped_answered = feats._answered_by_geometry
    if switch is not None:
        before = switch(False)
    else:
        feats._by_geometry = lambda name, body, support, compute, *read: compute()
        feats._answered_by_geometry = lambda name, support, *read: False
    try:
        return feats.detect(copy)
    finally:
        feats._cached_detection = shipped_cached
        if switch is not None:
            switch(before)
        else:
            feats._by_geometry = shipped_geometry
            feats._answered_by_geometry = shipped_answered


# --- Der Weg je Fall ---------------------------------------------------------------

AXES = {0: "x", 1: "y", 2: "z"}


class Case:
    """Ein Projekt im Lauf: Verlauf, Cache, Profil und die Zeilen dazu."""

    def __init__(self, name: str, out: Any) -> None:
        self.name = name
        self.out = out
        self.cache = ResultCache()
        if name.startswith("beispiel:"):
            from app.core import examples

            self.project = load(examples.directory() / f"{name.split(':', 1)[1]}.p3d")
        else:
            path = Path(name)
            payload = path.read_bytes()
            self.project = new_project("centauri-carbon-2", "petg")
            self.project.document.sources["src_1"] = Source(
                id="src_1", kind="import", path=f"sources/model{path.suffix.lower()}", sha256=""
            )
            self.project.sources["src_1"] = payload
            plan = import_plan("src_1", path.name, payload, "mm", first_model=True)
            History(self.project.document).apply("Laden", [plan.draft])
        self.history = History(self.project.document)
        document = self.project.document
        self.profile = profiles.make_profile(
            document.printer or "centauri-carbon-2", document.material or "petg"
        )
        self.sources = ProjectSources(self.project)
        self.result: Any = None

    def run(self) -> tuple[float, float]:
        """Eine Auswertung wie nach *Übernehmen*; zurück CPU gesamt und Erkennung."""
        SPENT["detect"] = 0.0
        started = time.process_time()
        self.result = evaluate(
            self.project.document,
            self.profile,
            sources=self.sources,
            ask=ask,
            cache=self.cache,
        )
        return time.process_time() - started, SPENT["detect"]

    def record(self, objekt: str, step: str, spent: tuple[float, float], far: str | None) -> dict:
        """Eine Zeile für den Zustand dieses Körpers nach dem Schritt."""
        entry = self.result.scene.objects.get(objekt) if self.result is not None else None
        line: dict[str, Any] = {
            "fall": self.name,
            "objekt": objekt,
            "schritt": step,
            "cpu": round(spent[0], 3),
            "cpu_erkennung": round(spent[1], 3),
            "fertig": bool(self.result.complete) if self.result is not None else False,
        }
        if entry is None:
            line["fehlt"] = True
            self.write(line)
            return line
        mesh = as_mesh_data(entry.mesh)
        raw = feats.known_detection(mesh)
        line["dreiecke"] = mesh.triangle_count
        line["erkennung"] = detection_print(raw)
        line["neben"] = [
            feats.freeform_dropped(mesh),
            feats.recognised_as_freeform(mesh),
            feats.unreadable_void_shells(mesh),
        ]
        names, hashed = scene_print(dict(entry.features))
        line["namen"] = names
        line["object_hash"] = hashed
        line["merkmale"] = len(entry.features)
        if far is not None:
            line["fern"] = far in entry.features
        # Nach einer starren Bewegung trägt ``carry_detection`` die Merkmale mit
        # (bewegt gerechnet, nicht neu erkannt) — dort ist die Kopie kein Maßstab.
        line["getragen"] = feats.MOVED_FROM_KEY in mesh.raw._cache
        if CHECK and raw is not None:
            line["kopie_gleich"] = detection_print(fresh_detection(mesh)) == line["erkennung"]
        self.write(line)
        return line

    def write(self, line: dict) -> None:
        self.out.write(json.dumps(line, ensure_ascii=False) + "\n")
        self.out.flush()

    def apply(self, title: str, drafts: list[OperationDraft]) -> None:
        self.history.apply(title, drafts)


def axis_faces(entry: Any) -> list[tuple[float, Any, int]]:
    """Achsparallele ebene Flächen ab 20 mm², die größte zuerst."""
    found = []
    for feature in entry.features.values():
        if feature.kind != "face":
            continue
        normal = np.asarray(feature.params.get("normal", (0.0, 0.0, 0.0)), dtype=float)
        axis = int(np.argmax(np.abs(normal)))
        if abs(float(normal[axis])) < 0.999:
            continue
        area = float(feature.params.get("area", 0.0))
        if area >= 20.0:
            found.append((area, feature, axis))
    found.sort(key=lambda item: (-item[0], item[1].id))
    return found


def spot_on(entry: Any, feature: Any) -> np.ndarray:
    """Die Mitte des größten Dreiecks einer Fläche."""
    mesh = as_mesh_data(entry.mesh)
    faces = np.asarray(sorted(feature.face_indices), dtype=np.int64)
    areas = np.asarray(mesh.raw.area_faces)[faces]
    return np.asarray(mesh.raw.triangles_center)[faces[int(np.argmax(areas))]]


def hole_near(entry: Any, point: np.ndarray, reach: float = 2.5) -> str | None:
    """Die Bohrung, deren Mitte am nächsten an ``point`` liegt."""
    holes = []
    for feature in entry.features.values():
        if feature.kind != "hole":
            continue
        centre = np.asarray(feature.params.get("centre", (1e9, 1e9, 1e9)), dtype=float)
        distance = float(np.linalg.norm(centre - point))
        if distance <= reach:
            holes.append((distance, feature.id))
    return min(holes)[1] if holes else None


def far_feature(entry: Any, point: np.ndarray) -> str | None:
    """Ein Merkmal weit weg von der ersten Bohrung — sein Name soll jeden Schritt überleben."""
    best = None
    for feature in entry.features.values():
        centre = feature.params.get("centre")
        if centre is None or feature.kind not in {"hole", "pin", "fillet", "face"}:
            continue
        distance = float(np.linalg.norm(np.asarray(centre, dtype=float) - point))
        if best is None or distance > best[0]:
            best = (distance, feature.id)
    return best[1] if best else None


def sequence(case: Case, objekt: str) -> None:
    """Die Folge aus Konzept §10 an einem Körper."""
    entry = case.result.scene.objects[objekt]
    faces = axis_faces(entry)
    spots: list[tuple[np.ndarray, int]] = []
    for _area, feature, axis in faces[:3]:
        spots.append((spot_on(entry, feature), axis))
    first = spots[0][0] if spots else None
    far = far_feature(entry, first) if first is not None else None
    for number, (centre, axis) in enumerate(spots, start=1):
        case.apply(
            f"Bohren {number}",
            [
                OperationDraft(
                    op="drill_hole",
                    inputs=(objekt,),
                    params={
                        "diameter": 3.0,
                        "x": float(centre[0]),
                        "y": float(centre[1]),
                        "z": float(centre[2]),
                        "axis": AXES[axis],
                        "depth": 2.0,
                    },
                )
            ],
        )
        case.record(objekt, f"1_bohren_{number}", case.run(), far)
    if spots:
        entry = case.result.scene.objects[objekt]
        centre, axis = spots[0]
        hole = hole_near(entry, centre)
        if hole is not None:
            along = np.zeros(3)
            along[(axis + 1) % 3] = 1.0
            target = np.asarray(entry.features[hole].params["centre"], dtype=float) + along
            case.apply(
                "Versetzen",
                [
                    OperationDraft(
                        op="move_feature",
                        inputs=(objekt,),
                        params={
                            "at_feature": hole,
                            "x": float(target[0]),
                            "y": float(target[1]),
                            "z": float(target[2]),
                        },
                    )
                ],
            )
            case.record(objekt, "2_versetzen", case.run(), far)
            entry = case.result.scene.objects[objekt]
            hole = hole_near(entry, target)
            if hole is not None:
                case.apply(
                    "Aufweiten",
                    [
                        OperationDraft(
                            op="resize_hole",
                            inputs=(objekt,),
                            params={"at_feature": hole, "diameter": 4.0},
                        )
                    ],
                )
                case.record(objekt, "3_aufweiten", case.run(), far)
                entry = case.result.scene.objects[objekt]
                hole = hole_near(entry, target)
                if hole is not None:
                    case.apply(
                        "Entfernen",
                        [
                            OperationDraft(
                                op="remove_feature",
                                inputs=(objekt,),
                                params={"at_feature": hole},
                            )
                        ],
                    )
                    case.record(objekt, "4_entfernen", case.run(), far)
    entry = case.result.scene.objects[objekt]
    low, high = (np.asarray(value, dtype=float) for value in as_mesh_data(entry.mesh).raw.bounds)
    extent = high - low
    side = max(1.0, 0.3 * float(min(extent[0], extent[1])))
    tool = case.history.next_object_id()
    case.apply(
        "Quader abziehen",
        [
            OperationDraft(
                op="create_box",
                params={
                    "width": side,
                    "depth": side,
                    "height": float(extent[2]) + 2.0,
                    "x": float(high[0]),
                    "y": float(high[1]),
                    "z": float(low[2]) - 1.0,
                },
                outputs=(tool,),
            ),
            OperationDraft(op="subtract_objects", inputs=(objekt, tool), seed=592),
        ],
    )
    case.record(objekt, "5_quader", case.run(), far)
    entry = case.result.scene.objects[objekt]
    low, high = (np.asarray(value, dtype=float) for value in as_mesh_data(entry.mesh).raw.bounds)
    extent = high - low
    middle = (low + high) / 2.0
    peg = case.history.next_object_id()
    width = max(1.0, min(5.0, 0.2 * float(min(extent[0], extent[1]))))
    case.apply(
        "Zapfen vereinen",
        [
            OperationDraft(
                op="create_cylinder",
                params={
                    "diameter": width,
                    "height": max(2.0, 0.2 * float(extent[2])),
                    "x": float(middle[0]),
                    "y": float(middle[1]),
                    "z": float(high[2]) - 0.5,
                },
                outputs=(peg,),
            ),
            OperationDraft(op="union_objects", inputs=(objekt, peg), seed=592),
        ],
    )
    case.record(objekt, "6_zapfen", case.run(), far)
    entry = case.result.scene.objects[objekt]
    low, high = (np.asarray(value, dtype=float) for value in as_mesh_data(entry.mesh).raw.bounds)
    case.apply(
        "Abschneiden",
        [
            OperationDraft(
                op="cut_away",
                inputs=(objekt,),
                params={
                    "plane": "along_axis",
                    "axis": "z",
                    "position": float(low[2] + 0.85 * (high[2] - low[2])),
                    "keep": "below",
                },
            )
        ],
    )
    case.record(objekt, "7_abschneiden", case.run(), far)
    case.apply(
        "Verschieben",
        [OperationDraft(op="translate_object", inputs=(objekt,), params={"dx": 5.0})],
    )
    case.record(objekt, "8_verschieben", case.run(), far)
    entry = case.result.scene.objects[objekt]
    faces = axis_faces(entry)
    if faces:
        centre, axis = spot_on(entry, faces[0][1]), faces[0][2]
        case.apply(
            "Bohren nach dem Verschieben",
            [
                OperationDraft(
                    op="drill_hole",
                    inputs=(objekt,),
                    params={
                        "diameter": 3.0,
                        "x": float(centre[0]),
                        "y": float(centre[1]),
                        "z": float(centre[2]),
                        "axis": AXES[axis],
                        "depth": 2.0,
                    },
                )
            ],
        )
        case.record(objekt, "9_bohren", case.run(), far)


def main() -> None:
    done: set[str] = set()
    if OUTPUT.exists():
        for line in OUTPUT.read_text(encoding="utf-8").splitlines():
            if line.strip():
                record = json.loads(line)
                if record.get("schritt") == "ende":
                    done.add(record["fall"])
    with OUTPUT.open("a", encoding="utf-8") as out:
        for name in CASES:
            if name in done:
                continue
            watchdog = threading.Timer(7200.0, lambda: os._exit(9))
            watchdog.daemon = True
            watchdog.start()
            ANSWERS.clear()
            SPENT.clear()
            ASKED[0] = 0
            why = "fertig"
            try:
                case = Case(name, out)
                spent = case.run()
                bodies = sorted(
                    (
                        (as_mesh_data(entry.mesh).triangle_count, key)
                        for key, entry in case.result.scene.objects.items()
                        if entry.kind != "brep"
                    ),
                    reverse=True,
                )
                chosen = [key for count, key in bodies if MINIMUM <= count <= MAXIMUM]
                for objekt in sorted(case.result.scene.objects):
                    case.record(objekt, "0_geladen", spent, None)
                for objekt in chosen[:PER_CASE]:
                    try:
                        sequence(case, objekt)
                    except Exception as error:
                        case.write(
                            {
                                "fall": name,
                                "objekt": objekt,
                                "schritt": "halt",
                                "warum": f"{type(error).__name__}: {error}"[:300],
                            }
                        )
            except Exception as error:
                why = f"{type(error).__name__}: {error}"[:300]
                traceback.print_exc()
            finally:
                watchdog.cancel()
            out.write(
                json.dumps(
                    {
                        "fall": name,
                        "schritt": "ende",
                        "warum": why,
                        "zuordnungen": SPENT["match_calls"],
                        "fragen": ASKED[0],
                        "antworten": dict(sorted(ANSWERS.items())),
                        "baum": TREE.name,
                        "gedaechtnis": MEMORY,
                        "weglassen": LEAVE_OUT,
                    },
                    ensure_ascii=False,
                )
                + "\n"
            )
            out.flush()
            print(name, why, flush=True)
    os._exit(0)


if __name__ == "__main__":
    main()
