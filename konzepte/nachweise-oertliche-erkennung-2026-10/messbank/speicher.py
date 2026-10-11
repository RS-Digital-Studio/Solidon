"""Messbank A5 (RM-592): was die Merker am Eiffelturm nach acht Bohrungen halten.

Aufruf::

    python speicher.py <baum> <ausgabe.jsonl>

Laden wie das Fenster, dann acht senkrechte Zylinder Ø 6 an den acht größten nach
oben weisenden Dreiecksmitten abziehen, je Schritt eine Auswertung mit Erkennung.
Gemessen: die Bytes, die ``features.held_answers`` für die Körper der Szene hält
(``memory.held_bytes``, wie der Ergebniscache sie wiegt), dazu die Spitze des
Python-Speichers (``tracemalloc``) über alle Schritte.
"""

from __future__ import annotations

import json
import sys
import tracemalloc
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _baum

ARGS = sys.argv[1:]
TREE = _baum.setup(ARGS[0])
_baum.activation_free()

import numpy as np  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402
from app.core.geom.mesh import as_mesh_data  # noqa: E402
from app.core.ingest.plan import import_plan  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.memory import held_bytes  # noqa: E402
from app.core.perceive import features as feats  # noqa: E402
from app.core.scene import History, evaluate  # noqa: E402
from app.core.scene.cache import ResultCache  # noqa: E402
from app.core.scene.history import OperationDraft  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Source  # noqa: E402

load_operations()
EIFFEL = (
    _baum.KUNDE / "埃菲尔铁塔（高18cm+、22cm、28cm）、一体无支撑" / "埃菲尔铁塔18cm_repariert.stl"  # noqa: RUF001
)


def main() -> None:
    tracemalloc.start()
    payload = EIFFEL.read_bytes()
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/model.stl", sha256=""
    )
    project.sources["src_1"] = payload
    plan = import_plan("src_1", EIFFEL.name, payload, "mm", first_model=True)
    history = History(project.document)
    history.apply("Laden", [plan.draft])
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    sources = ProjectSources(project)
    cache = ResultCache()

    def run():
        return evaluate(
            project.document, profile, sources=sources, ask=lambda q, c: c[0], cache=cache
        )

    result = run()
    body = next(iter(result.scene.objects))
    raw = as_mesh_data(result.scene.objects[body].mesh).raw
    up = np.flatnonzero(np.asarray(raw.face_normals)[:, 2] > 0.9)
    order = up[np.argsort(-np.asarray(raw.area_faces)[up], kind="stable")]
    spots = np.asarray(raw.triangles_center)[order[:8]]
    for number, spot in enumerate(spots, start=1):
        before = set(result.scene.objects)
        history.apply(
            f"Zylinder {number}",
            [
                OperationDraft(
                    op="create_cylinder",
                    params={
                        "diameter": 6.0,
                        "height": 400.0,
                        "z": -100.0,
                        "x": float(spot[0]),
                        "y": float(spot[1]),
                    },
                )
            ],
        )
        result = run()
        tool = next(key for key in result.scene.objects if key not in before)
        history.apply(
            f"Bohrung {number}", [OperationDraft(op="subtract_objects", inputs=(body, tool))]
        )
        result = run()
    seen: set[int] = set()
    held = 0
    for entry in result.scene.objects.values():
        mesh = as_mesh_data(entry.mesh)
        held += sum(held_bytes(answer, seen) for answer in feats.held_answers(mesh.raw))
    _current, peak = tracemalloc.get_traced_memory()
    line = {
        "baum": TREE.name,
        "gehalten_mb": round(held / 2**20, 2),
        "spitze_mb": round(peak / 2**20, 1),
    }
    with Path(ARGS[1]).open("a", encoding="utf-8") as out:
        out.write(json.dumps(line) + "\n")
    print(line, flush=True)
    import os

    os._exit(0)


if __name__ == "__main__":
    main()
