"""Messbank RM-695: ein gespeichertes Projekt nach einem Neustart wieder öffnen.

Aufruf::

    python wieder.py <baum> <arbeitsordner> erst <modell>
    python wieder.py <baum> <arbeitsordner> wieder <ausgabe.jsonl>

``erst`` legt ein neues Projekt an, lädt das Modell, wertet mit einem Plattencache in
``<arbeitsordner>/cache`` aus und speichert ``<arbeitsordner>/projekt.p3d``. ``wieder``
ist der Neustart: ein frischer Prozess öffnet das Projekt über denselben Plattencache.
Gemessen werden CPU-Sekunden und Wanduhr der Auswertung, die vollen Erkennungsläufe
(``_fitted`` mit den ebenen Facetten, wie in ``detect``) und ein Abdruck aller
Merkmale Bit für Bit — gleich gegen den ersten Lauf und gegen den anderen Baum.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _baum

ARGS = sys.argv[1:]
TREE = _baum.setup(ARGS[0])
_baum.activation_free()

from app.core.bootstrap import load_operations  # noqa: E402
from app.core.geom.mesh import MeshCodec  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.perceive import features  # noqa: E402
from app.core.scene import History, evaluate  # noqa: E402
from app.core.scene import project as project_module  # noqa: E402
from app.core.scene.cache import DiskCache, ResultCache  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Source  # noqa: E402
from app.i18n import _  # noqa: E402

FOLDER = Path(ARGS[1])
PHASE = ARGS[2]


def exact(value: Any) -> Any:
    """Werte für den Abdruck typgenau: Gleitkommazahlen als Hex, Tupel und Listen getrennt."""
    if isinstance(value, float):
        return ["f", value.hex()]
    if isinstance(value, dict):
        return ["d", sorted((str(key), exact(item)) for key, item in value.items())]
    if isinstance(value, tuple):
        return ["t", [exact(item) for item in value]]
    if isinstance(value, list):
        return ["l", [exact(item) for item in value]]
    return [type(value).__name__, value]


def imprint(result: Any) -> str:
    digest = hashlib.blake2b(digest_size=12)
    for object_id in sorted(result.scene.objects):
        body = result.scene.objects[object_id]
        for name, feature in body.features.items():
            row = [
                object_id,
                name,
                feature.kind,
                exact(dict(feature.params)),
                list(feature.face_indices),
                feature.recognised,
                feature.created_by,
                exact(dict(feature.measure_sources)),
                [
                    [patch.kind, patch.source, exact(dict(patch.params)), list(patch.face_indices)]
                    for patch in feature.surface_patches
                ],
            ]
            digest.update(json.dumps(row, default=repr).encode("utf-8"))
    return digest.hexdigest()


def answer_full(question: str, choices: list[str]) -> str:
    for choice in choices:
        if str(choice).startswith("Mit Merkmalserkennung"):
            return choice
    return choices[0]


def main() -> None:
    load_operations()
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=FOLDER / "cache"))
    runs: list[int] = []
    real = features._fitted

    def counted(*args: Any, **kwargs: Any) -> Any:
        if "planar" in kwargs:
            runs.append(args[0].triangle_count)
        return real(*args, **kwargs)

    features._fitted = counted  # type: ignore[assignment]
    if PHASE == "erst":
        from app.core.ingest.plan import import_plan

        model = Path(ARGS[3])
        FOLDER.mkdir(parents=True, exist_ok=True)
        project = new_project("centauri-carbon-2", "petg")
        payload = model.read_bytes()
        suffix = model.suffix.lower()
        project.document.sources["src_1"] = Source(
            id="src_1", kind="import", path=f"sources/model{suffix}", sha256=""
        )
        project.sources["src_1"] = payload
        unit = "mm" if suffix in (".stl", ".obj", ".ply") else "auto"
        plan = import_plan("src_1", model.name, payload, unit, first_model=True)
        History(project.document).apply(_("Laden"), [plan.draft])
    else:
        project = project_module.load(FOLDER / "projekt.p3d")
    started = time.perf_counter(), time.process_time()
    result = evaluate(
        project.document, profile, sources=ProjectSources(project), cache=cache, ask=answer_full
    )
    wall = time.perf_counter() - started[0]
    cpu = time.process_time() - started[1]
    if PHASE == "erst":
        project_module.save(project, FOLDER / "projekt.p3d")
        (FOLDER / "erst.txt").write_text(imprint(result), encoding="utf-8")
        print(f"erst {cpu:.2f} s CPU, {wall:.2f} s, Erkennung an {runs}", flush=True)
    else:
        line = {
            "baum": TREE.name,
            "ordner": FOLDER.name,
            "cpu": round(cpu, 3),
            "wand": round(wall, 3),
            "erkennungen": runs,
            "merkmale": sum(len(body.features) for body in result.scene.objects.values()),
            "abdruck": imprint(result),
            "wie_erst": imprint(result) == (FOLDER / "erst.txt").read_text(encoding="utf-8"),
            "vollstaendig": bool(result.complete),
        }
        with Path(ARGS[3]).open("a", encoding="utf-8") as out:
            out.write(json.dumps(line, ensure_ascii=False) + "\n")
        print(line, flush=True)
    sys.stdout.flush()
    os._exit(0)


main()
