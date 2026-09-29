"""Nachbau der gs-100-Mündung für einen Test: Zylindersenkung Ø 10 in einer
Unterseite, die ein Zylinder R ist (gs-100: R 13), die Mündungskante gerundet
(R 1). Findet ``_filled_cap`` an den Rundungsflächen allein eine Fläche
(Trichter), und was ergibt Versetzen/Entfernen mit und ohne Füllung?

Aufruf: ``t11_rounded_mouth.py <R> <Rundung>``.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import TREE, as_mesh_data, np  # noqa: E402

sys.path.insert(0, TREE)
from OCP.BRepAdaptor import BRepAdaptor_Curve  # noqa: E402
from tests.test_bore_depth import _evaluated  # noqa: E402
from tests.test_feature_moves_keep_shape import BOTH_ENDS, _body, _narrowest_hole  # noqa: E402

from app.core.brep import edit  # noqa: E402
from app.core.geom import mouth_cap  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.perceive.relations import cavity_chains  # noqa: E402
from app.core.sketch.planes import frame_of  # noqa: E402

radius, rounding = float(sys.argv[1]), float(sys.argv[2])
out = open(Path(__file__).with_name(f"t11_rounded_mouth_R{radius:g}_r{rounding:g}.txt"), "w", encoding="utf-8", buffering=1)


def say(*parts):
    print(*parts, flush=True)
    print(*parts, file=out)


shipped_filled = edit._filled_cap
shipped_surface = mouth_cap.mouth_surface
seen: list[str] = []


def watched_surface(mesh, excluded, rim):
    surface = shipped_surface(mesh, excluded, rim)
    seen.append("keine" if surface is None else f"Rand max {float(np.abs(surface.rim_error).max()):.4f}")
    return surface


mouth_cap.mouth_surface = watched_surface
profile = profiles.make_profile("centauri-carbon-2", "petg")
plate = edit.box(44.0, 24.0, 12.0)
roll = edit.revolved_bore_tool(
    [(0.0, -30.0), (radius, -30.0), (radius, 30.0), (0.0, 30.0), (0.0, -30.0)],
    frame_of((1.0, 0.0, 0.0), (0.0, 0.0, radius)),
)
plate = edit.unified(edit.boolean("intersection", [plate, roll]))
solid = edit.bore_profile(plate, list(BOTH_ENDS["Zylindersenkung und Fase"]), frame_of((0, 0, 1), (-8.0, 0, 0)))
picked = []
for index, edge in enumerate(solid.edges()):
    curve = BRepAdaptor_Curve(edge)
    middle = curve.Value((curve.FirstParameter() + curve.LastParameter()) / 2.0)
    if abs(((middle.X() + 8.0) ** 2 + middle.Y() ** 2) ** 0.5 - 5.0) < 0.05 and middle.Z() < 2.0:
        picked.append(index)
body = edit.fillet(solid, rounding, selected_edges=picked) if rounding > 0.0 else solid
say(f"R {radius:g}, Rundung {rounding:g}: Kanten {picked}")
for kernel in ("mesh", "brep"):
    source = _body(kernel, body)
    bore = _narrowest_hole(source)
    chains = cavity_chains(source.features, as_mesh_data(source.mesh))
    members = next(([f.id for f in c] for c in chains if any(f.id == bore.id for f in c)), None)
    x, y, z = (float(v) for v in bore.params["centre"])
    for label, filled in (("ausgeliefert", shipped_filled), ("ohne Füllung", lambda *a, **k: None)):
        edit._filled_cap = filled
        seen.clear()
        try:
            moved, _f1 = _evaluated(source, profile, "move_feature", at_feature=bore.id, x=x + 5.0, y=y, z=z)
            removed, _f2 = _evaluated(source, profile, "remove_feature", at_feature=bore.id, sections="chain")
            say(
                f"  {kernel} {label}: Kette {members}; versetzen 5 mm "
                f"{abs(float(moved.mesh.volume)) - abs(float(source.mesh.volume)):+.3f}, entfernen "
                f"{abs(float(removed.mesh.volume)) - abs(float(source.mesh.volume)):+.3f} | {seen}"
            )
        except Exception as problem:  # noqa: BLE001
            say(f"  {kernel} {label}: {type(problem).__name__}: {getattr(problem, 'detail', problem)}")
    edit._filled_cap = shipped_filled
