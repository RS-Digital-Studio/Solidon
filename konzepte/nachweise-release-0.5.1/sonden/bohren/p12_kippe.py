"""Sonde p12: Wie oft verliert *Bohrung ändern* (Ø 6, keep) den Senkkegel der schrägen Senkbohrung?

Aufruf: python p12_kippe.py <baum>

Derselbe Aufbau wie p8, aber über eine Reihe von Drehungen: um (1, 2, 3) mit
Winkeln um 0,73 rad in Schritten von 1e-4 und weiteren Winkeln, dazu um (3, -1, 2).
Je Drehung: Kegel wiedergefunden (``cone``), als Torus gelesen, oder verwaist.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _baum  # noqa: E402

TREE = _baum.setup(sys.argv[1])
sys.path.insert(1, str(TREE))

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

from app.core.geom.mesh import MeshData, as_mesh_data  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.perceive.features import detect, forget_cache  # noqa: E402
from app.core.types import SceneObject  # noqa: E402
from tests.helpers import sloping_bore  # noqa: E402
from tests.test_bore_floor_resize import _resize  # noqa: E402

PROFILE = profiles.make_profile("centauri-carbon-2", "petg")


def one(angle: float, axis: tuple[float, float, float], diameter: float, mode: str) -> str:
    forget_cache()
    mesh, _features, _hole = sloping_bore()
    transform = trimesh.transformations.rotation_matrix(angle, axis)
    transform[:3, 3] = (17, -31, 9)
    raw = mesh.raw.copy()
    raw.apply_transform(transform)
    mesh = MeshData.of(raw)
    features = detect(mesh)
    if not any(f.kind == "cone" for f in features.values()):
        return "Eingang ohne Kegel"
    inverse = np.linalg.inv(transform)
    hole = min(
        (f for f in features.values() if f.kind == "hole"),
        key=lambda f: abs(trimesh.transform_points([f.params["centre"]], inverse)[0, 0]),
    )
    source = SceneObject("own", "Senkbohrung", mesh, features=features)
    try:
        changed, findings, _result = _resize(source, hole, diameter, PROFILE, entrance_mode=mode)
    except Exception as error:  # noqa: BLE001
        return f"Fehler {type(error).__name__}"
    orphaned = any(f.code == "perceive.orphaned" for f in findings)
    forget_cache()
    kinds = sorted(f.kind for f in detect(as_mesh_data(changed.mesh)).values() if f.kind in ("cone", "torus"))
    return f"{'verwaist' if orphaned else 'gehalten'} {kinds}"


def main() -> None:
    angles = [0.73 + step * 1e-4 for step in range(-5, 6)] + [0.35, 0.5, 0.9, 1.1, 1.3, 2.0]
    for axis in ((1.0, 2.0, 3.0), (3.0, -1.0, 2.0)):
        for diameter, mode in ((6.0, "keep"), (10.0, "keep")):
            results = [one(angle, axis, diameter, mode) for angle in angles]
            lost = sum(1 for r in results if r.startswith("verwaist"))
            print(f"Achse {axis} Ø {diameter} {mode}: verwaist {lost} von {len(results)}", flush=True)
            for angle, text in zip(angles, results, strict=True):
                print(f"    {angle:.4f}: {text}", flush=True)


if __name__ == "__main__":
    main()
