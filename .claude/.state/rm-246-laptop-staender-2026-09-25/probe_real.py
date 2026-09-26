"""RM-220 an echten Modellen: gesenkte Bohrungen kippen und versetzen.

Je Körper bis zu drei Ketten mit Senkung und bis zu zwei einzelne
Durchgangsbohrungen: 15° kippen (um die Hauptachse, die am weitesten quer zur
Bohrungsachse liegt) und 1,5 mm quer versetzen. Gemessen wird, was vor den
alten Mündungen abgetragen wird, die Volumenänderung und die Befunde.

Aufruf: PROBE_TREE=<baum> python probe_real.py <datei> [winkel]
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

TREE = os.environ["PROBE_TREE"]
sys.path.insert(0, TREE)
sys.path.insert(0, str(Path(__file__).parent))

import numpy as np  # noqa: E402
from probe_actions import load  # noqa: E402

from app.core.geom import prepare_ops  # noqa: E402
from app.core.geom.boolean import boolean  # noqa: E402
from app.core.geom.mesh import as_mesh_data  # noqa: E402
from app.core.geom.section import cut  # noqa: E402
from app.core.perceive.relations import cavity_chains  # noqa: E402
from app.core.registry import REGISTRY  # noqa: E402
from app.core.scene.cancel import NeverCancelled  # noqa: E402
from app.core.types import OpContext, Scene  # noqa: E402

AXES = {"x": np.array([1.0, 0.0, 0.0]), "y": np.array([0.0, 1.0, 0.0]), "z": np.array([0.0, 0.0, 1.0])}


def run(op, entry, profile, **params):
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=1,
            progress=lambda *_: None,
            ask=lambda _q, c: c[0],
            cancelled=NeverCancelled(),
        )
    )


def beyond(mesh, plane) -> float:
    """Volumen von ``mesh`` jenseits der Ebene (auf der Seite ihrer Normalen)."""
    from app.core.geom.section import SectionPlane

    if not len(mesh.raw.faces):
        return 0.0
    kept = cut(mesh, SectionPlane(normal=tuple(-v for v in plane.normal), position=-plane.position)).mesh
    return abs(float(kept.volume)) if len(kept.raw.faces) else 0.0


def main() -> int:
    path = Path(sys.argv[1])
    angle = float(sys.argv[2]) if len(sys.argv) > 2 else 15.0
    _project, profile, result, seconds = load(path)
    print(f"{path.name}: geladen in {seconds:.1f} s, {len(result.scene.objects)} Körper", flush=True)
    for object_id, entry in result.scene.objects.items():
        mesh = as_mesh_data(entry.mesh)
        chains = [c for c in cavity_chains(entry.features, mesh) if any(f.kind == "cone" for f in c)]
        chained = {f.id for c in cavity_chains(entry.features, mesh) for f in c}
        singles = [
            f
            for f in entry.features.values()
            if f.kind == "hole" and f.params.get("through") and f.id not in chained
        ]
        print(f"  {object_id} ({entry.kind}): {len(chains)} Ketten mit Senkung, {len(singles)} einzelne Durchgänge")
        cases = [(c[0], tuple(c)) for c in chains[:3]] + [(f, (f,)) for f in singles[:2]]
        for bore, chain in cases:
            axis = np.asarray(bore.params["axis"], dtype=float)
            turn = min(AXES, key=lambda name: abs(float(AXES[name] @ axis)))
            caps_of = getattr(prepare_ops, "_old_rim_caps", None)
            caps = caps_of(mesh, bore, entry.features, chain if len(chain) > 1 else None) if caps_of else ()
            started = time.perf_counter()
            try:
                done = run("rotate_feature", entry, profile, at_feature=bore.id, axis=turn, angle=angle)
            except Exception as error:  # noqa: BLE001
                print(f"    {bore.id} kippen: {type(error).__name__}: {getattr(error, 'detail', error)}")
                continue
            took = time.perf_counter() - started
            after = as_mesh_data(done.outputs[0].mesh)
            lost = boolean("difference", [mesh, after], allow_empty=True).mesh
            front = sum(beyond(lost, plane) for plane in caps)
            codes = sorted({f.code for f in done.findings if f.severity != "info"})
            print(
                f"    {bore.id}{'+' + chain[-1].id if len(chain) > 1 else ''} gekippt {angle:g}° um {turn}: "
                f"weg {lost.volume:.1f} mm³, vor den Mündungen {front:.2f} mm³, {took:.1f} s, {codes}"
            )
            across = np.cross(axis, AXES[turn])
            across /= np.linalg.norm(across)
            target = np.asarray(bore.params["centre"], dtype=float) + across * 1.5
            try:
                moved = run("move_feature", entry, profile, at_feature=bore.id, x=float(target[0]), y=float(target[1]), z=float(target[2]))
            except Exception as error:  # noqa: BLE001
                print(f"    {bore.id} versetzen: {type(error).__name__}: {getattr(error, 'detail', error)}")
                continue
            shifted = as_mesh_data(moved.outputs[0].mesh)
            codes = sorted({f.code for f in moved.findings if f.severity != "info"})
            print(f"    {bore.id} 1,5 mm quer: Volumen {mesh.volume:.2f} -> {shifted.volume:.2f}, {codes}")
            wide = max(float(f.params.get("diameter", 0.0)) for f in chain)
            beside = np.asarray(bore.params["centre"], dtype=float) + across * (wide + 3.0)
            try:
                copied = run("duplicate_feature", entry, profile, at_feature=bore.id, x=float(beside[0]), y=float(beside[1]), z=float(beside[2]))
            except Exception as error:  # noqa: BLE001
                print(f"    {bore.id} verdoppeln: {type(error).__name__}: {getattr(error, 'detail', error)}")
                continue
            doubled = as_mesh_data(copied.outputs[0].mesh)
            codes = sorted({f.code for f in copied.findings if f.severity != "info"})
            print(f"    {bore.id} verdoppelt {wide + 3.0:.1f} mm daneben: Volumen {mesh.volume:.2f} -> {doubled.volume:.2f}, {codes}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
