"""Gemeinsamer Unterbau der Sonden des Prüfers bohrung.

Der Baum kommt aus ``SONDE_TREE`` (Vorgabe: wt-bohrung) und steht als erster
Suchpfad; ``app`` muss aus ihm geladen sein, sonst bricht die Sonde ab.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

TREE = os.environ.get("SONDE_TREE", r"F:\3D Druck.review-051\wt-bohrung")
sys.path.insert(0, TREE)
_ISOLATED = tempfile.mkdtemp(prefix="sonde-bohrung-")
for _variable in ("APPDATA", "LOCALAPPDATA"):
    os.environ[_variable] = _ISOLATED

import app  # noqa: E402

if not str(Path(app.__file__).resolve()).lower().startswith(str(Path(TREE).resolve()).lower()):
    raise SystemExit(f"app aus falschem Baum: {app.__file__}")
print("app aus", app.__file__, flush=True)

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

import numpy as np  # noqa: E402

from app.core.geom.mesh import as_mesh_data  # noqa: E402
from app.core.ingest.plan import import_plan  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.registry import REGISTRY  # noqa: E402
from app.core.scene import History, evaluate  # noqa: E402
from app.core.scene.cancel import NeverCancelled  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import OpContext, Scene, Source  # noqa: E402

AXES = {
    "x": np.array([1.0, 0.0, 0.0]),
    "y": np.array([0.0, 1.0, 0.0]),
    "z": np.array([0.0, 0.0, 1.0]),
}


def _ask(question: str, choices: list[str]) -> str:
    for choice in choices:
        if choice == "mm":
            return choice
    return choices[0]


def load(path: Path, printer: str = "centauri-carbon-2", material: str = "petg"):
    """Datei über den Kundenweg laden: Importplan, Verlauf, Auswertung."""
    payload = path.read_bytes()
    project = new_project(printer, material)
    document = project.document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/{path.name}", sha256=""
    )
    project.sources["src_1"] = payload
    plan = import_plan("src_1", path.name, payload, unit="auto", first_model=True)
    History(document).apply("Laden", [plan.draft])
    profile = profiles.make_profile(printer, material)
    started = time.perf_counter()
    result = evaluate(document, profile, sources=ProjectSources(project), ask=_ask)
    return project, profile, result, time.perf_counter() - started


def run(op: str, entry, profile, quality: str = "fine", **params):
    """Eine Operation direkt auf ``entry`` rechnen, wie die Auswertung sie ruft."""
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality=quality,
            seed=1,
            progress=lambda *_: None,
            ask=lambda _q, c: c[0],
            cancelled=NeverCancelled(),
        )
    )


def volume(mesh) -> float:
    return float(as_mesh_data(mesh).volume)


def tight(mesh) -> bool:
    return bool(as_mesh_data(mesh).is_watertight)


def codes(result) -> list[str]:
    return sorted({f.code for f in result.findings})
