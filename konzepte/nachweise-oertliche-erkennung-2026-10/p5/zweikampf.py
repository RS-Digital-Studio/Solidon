"""P5: eine Funktion alt gegen neu an denselben Eingängen — Ergebnis Bit für Bit, CPU im Wechsel.

Aufruf: python zweikampf.py <neuer-baum> <alter-baum> <modul> <funktion> <fall> [runden]

``fall`` wie in tempo.py (staender, eiffel) oder ein Netzpfad (kalt erkannt). Die
Funktion wird bei der Erkennung nach dem Schritt mitgeschnitten (jeder Aufruf), dann
je Aufruf alt und neu im Wechsel gerechnet. Die alte Fassung ist der Quelltext der
Funktion aus dem alten Baum, übersetzt im Namensraum des neuen Moduls — alle Helfer
sind die neuen. Gleich heißt: ``pickle`` der Ergebnisse gleich.
"""

from __future__ import annotations

import ast
import copy
import importlib
import pickle
import sys
import time
from pathlib import Path

sys.path.insert(0, r"F:\sl-e\konzepte\nachweise-oertliche-erkennung-2026-10\messbank")
import _baum

NEW = _baum.setup(sys.argv[1])
_baum.activation_free()
OLD = Path(sys.argv[2])
MODULE, NAME, CASE = sys.argv[3], sys.argv[4], sys.argv[5]
ROUNDS = int(sys.argv[6]) if len(sys.argv) > 6 else 3

module = importlib.import_module(MODULE)
old_source = (OLD / Path(*MODULE.split("."))).with_suffix(".py").read_text(encoding="utf-8")
tree = ast.parse(old_source)
node = next(
    n for n in tree.body if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name == NAME
)
namespace = dict(vars(module))
exec(compile(ast.Module(body=[node], type_ignores=[]), f"<alt {NAME}>", "exec"), namespace)
if "--alt-helfer" in sys.argv:
    # Die genannten Helfer ebenfalls in ihrer alten Fassung, im Namensraum der alten Funktion.
    helpers = sys.argv[sys.argv.index("--alt-helfer") + 1].split(",")
    nodes = [
        n
        for n in tree.body
        if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef) and n.name in helpers
    ]
    exec(compile(ast.Module(body=nodes, type_ignores=[]), "<alte Helfer>", "exec"), namespace)
old_function = namespace[NAME]
new_function = getattr(module, NAME)

calls: list[tuple[tuple, dict]] = []
recording = [False]


def recorder(*args, **kwargs):
    if recording[0]:
        calls.append((args, kwargs))
    return new_function(*args, **kwargs)


setattr(module, NAME, recorder)

from app.core.bootstrap import load_operations  # noqa: E402
from app.core.geom.mesh import MeshData, read_mesh  # noqa: E402
from app.core.ingest.loader import normalise  # noqa: E402
from app.core.ingest.plan import import_plan  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.perceive import features as feats  # noqa: E402
from app.core.scene import History, evaluate  # noqa: E402
from app.core.scene.cache import ResultCache  # noqa: E402
from app.core.scene.history import OperationDraft  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Source  # noqa: E402

load_operations()
EVALUATE = importlib.import_module("app.core.scene.evaluate")
SPOTS = {"staender": (-87.9, -6.8), "eiffel": (-34.2, 2.1)}
FILES = {
    "staender": _baum.KUNDE / "parametric-laptop-riser.stl",
    "eiffel": _baum.KUNDE
    / "埃菲尔铁塔（高18cm+、22cm、28cm）、一体无支撑"  # noqa: RUF001
    / "埃菲尔铁塔18cm_repariert.stl",
}

if CASE in FILES:
    path = FILES[CASE]
    payload = path.read_bytes()
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/model{path.suffix.lower()}", sha256=""
    )
    project.sources["src_1"] = payload
    plan = import_plan("src_1", path.name, payload, "mm", first_model=True)
    history = History(project.document)
    history.apply("Laden", [plan.draft])
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    sources = ProjectSources(project)
    cache = ResultCache()

    def run():
        return evaluate(
            project.document, profile, sources=sources, ask=lambda q, c: c[0], cache=cache
        )

    ids = list(run().scene.objects)
    x, y = SPOTS[CASE]
    history.apply(
        "Zylinder",
        [
            OperationDraft(
                op="create_cylinder",
                params={"diameter": 6.0, "height": 400.0, "z": -100.0, "x": x, "y": y},
            )
        ],
    )
    tool = [key for key in run().scene.objects if key not in ids][-1]
    history.apply("Abziehen", [OperationDraft(op="subtract_objects", inputs=(ids[0], tool))])
    recording[0] = True
    run()
else:
    path = Path(CASE)
    mesh = normalise(read_mesh(path.read_bytes(), path.suffix), "mm").mesh
    recording[0] = True
    feats.detect(MeshData.of(mesh.raw))
recording[0] = False
print(f"{len(calls)} Aufrufe mitgeschnitten", flush=True)

if "--profil" in sys.argv:
    import cProfile
    import io
    import pstats

    for label, function in (("alt", old_function), ("neu", new_function)):
        profiler = cProfile.Profile()
        profiler.enable()
        for args, kwargs in calls:
            function(*copy.copy(args), **kwargs)
        profiler.disable()
        out = io.StringIO()
        pstats.Stats(profiler, stream=out).sort_stats("tottime").print_stats(25)
        print("=== Profil", label, flush=True)
        print(out.getvalue()[:6000], flush=True)


def norm(value):
    """Ergebnisse vergleichbar: Mengen sortiert, numpy-Zahlen als Python-Zahlen, Felder mit Typ."""
    import numpy as np

    if isinstance(value, np.ndarray):
        return ("feld", value.dtype.str, value.shape, value.tobytes())
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, (set, frozenset)):
        return ("menge", sorted(norm(item) for item in value))
    if isinstance(value, dict):
        return ("dict", [(norm(k), norm(v)) for k, v in value.items()])
    if isinstance(value, (list, tuple)):
        return (type(value).__name__, [norm(item) for item in value])
    return value


different = 0
spent = {"alt": 0.0, "neu": 0.0}
for number in range(ROUNDS):
    order = (("alt", old_function), ("neu", new_function))
    if number % 2:
        order = order[::-1]
    for label, function in order:
        results = []
        took = 0.0
        for args, kwargs in calls:
            if "--vergessen" in sys.argv:
                feats.forget_cache()
            started = time.process_time()
            results.append(function(*copy.copy(args), **kwargs))
            took += time.process_time() - started
        spent[label] += took
        if label == "alt":
            old_results = results
        else:
            new_results = results
    if number == 0:
        for index, (left, right) in enumerate(zip(old_results, new_results, strict=True)):
            if pickle.dumps(norm(left)) != pickle.dumps(norm(right)):
                different += 1
                if different <= 5:
                    if isinstance(left, dict) and isinstance(right, dict):
                        keys = [
                            key
                            for key in sorted(set(left) | set(right), key=str)
                            if pickle.dumps(left.get(key)) != pickle.dumps(right.get(key))
                        ]
                        print("ANDERS Aufruf", index, "Schlüssel", len(keys), flush=True)
                        for key in keys[:10]:
                            print(
                                "   ", key, str(left.get(key))[:150], "|", str(right.get(key))[:150]
                            )
                    else:
                        print("ANDERS Aufruf", index, str(left)[:300], "|", str(right)[:300])
print(
    f"{NAME} {CASE}: {len(calls)} Aufrufe, {different} anders; CPU je Runde alt "
    f"{spent['alt'] / ROUNDS:.3f} s, neu {spent['neu'] / ROUNDS:.3f} s",
    flush=True,
)
import os  # noqa: E402

os._exit(0)
