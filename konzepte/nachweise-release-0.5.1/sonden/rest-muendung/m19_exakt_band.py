"""RM-259, exakter Kern, Versuch: Stopfen durch Wegnehmen der Hohlraumflächen samt Band
(``edit.defeatured``), Werkzeug = (wiederhergestellt − Körper) ∪ (Säule über dem
äußeren Rand bis hinter die Fläche − wiederhergestellt), starr versetzt.

An gs-100 (STEP, Band = Spline-Flächen 0–3) und am Nachbau R 40 / r 1
(exakt, Band = die Rundungsfläche). Versetzen in drei Richtungen, dazu hin und
zurück; Entfernen.
"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import MODELS, TREE, as_mesh_data, load, np  # noqa: E402

sys.path.insert(0, TREE)
from nachbau import built  # noqa: E402
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace, BRepBuilderAPI_MakePolygon  # noqa: E402
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism  # noqa: E402
from OCP.gp import gp_Pnt, gp_Vec  # noqa: E402
from tests.test_feature_moves_keep_shape import _body, _narrowest_hole  # noqa: E402

from app.core.brep import edit  # noqa: E402
from app.core.brep.kernel import _FACE_ATTRIBUTE, Solid  # noqa: E402
from app.core.perceive import relations  # noqa: E402
from app.core.perceive.relations import (  # noqa: E402
    _face_boundary_rings,
    cavity_chain_state_at,
    cavity_chains,
    cavity_surface_indices,
    ring_in_order,
)

out = open(Path(__file__).with_name("m19_exakt_band.txt"), "w", encoding="utf-8", buffering=1)


def say(*parts):
    print(*parts, flush=True)
    print(*parts, file=out)


def construction(solid, chain, band_faces, outward, lift=0.02):
    twin = as_mesh_data(solid)
    body = relations._one_body(twin).raw
    owners = np.asarray(solid.raw.face_attributes[_FACE_ATTRIBUTE], dtype=np.int64)
    cavity_tris = set(int(i) for i in cavity_surface_indices(twin, chain))
    native = sorted(set(solid.faces_of_triangles(sorted(cavity_tris))) | set(band_faces))
    band_tris = set(int(i) for i in np.flatnonzero(np.isin(owners, band_faces)))
    started = time.perf_counter()
    restored = edit.defeatured(solid, native)
    say(f"   Wegnehmen {native}: {'None' if restored is None else f'+{restored.volume - solid.volume:.4f} mm³'} ({time.perf_counter() - started:.1f} s)")
    if restored is None:
        return None
    # Der äußere Rand des Bands, entlang der Achse projiziert: die Säule.
    rings = _face_boundary_rings(body, np.asarray(sorted(cavity_tris | band_tris), dtype=np.int64))
    before = _face_boundary_rings(body, np.asarray(sorted(cavity_tris), dtype=np.int64))
    ring = [r for r in rings if r not in before][0]
    points = np.asarray(body.vertices)[np.asarray(ring_in_order(ring), dtype=np.int64)]
    heights = points @ outward
    corners = np.asarray(body.vertices)[np.unique(np.asarray(body.faces)[sorted(cavity_tris)])]
    reach = corners @ outward
    low = float(reach.min()) - lift  # hinter der fernen Mündung, um die Zugabe
    top = float(heights.max()) + lift
    flat = points - np.outer(heights - low, outward)
    polygon = BRepBuilderAPI_MakePolygon()
    for x, y, z in flat.tolist():
        polygon.Add(gp_Pnt(x, y, z))
    polygon.Close()
    face = BRepBuilderAPI_MakeFace(polygon.Wire(), True).Face()
    prism = Solid(BRepPrimAPI_MakePrism(face, gp_Vec(*(outward * (top - low)))).Shape())
    tool = edit.unified(edit.boolean("difference", [prism, solid]))
    say(f"   Werkzeug: {tool.volume:.4f} mm³ (Säule {prism.volume:.1f}), Teile {len(tool.solids()) if hasattr(tool, 'solids') else '?'}")
    return restored, tool


def moved(restored, tool, travel):
    placed = edit.boolean("difference", [restored, edit.moved(tool, tuple(float(v) for v in travel))])
    return placed


# gs-100
_p, prof, result, _t = load(MODELS / "pegboard-gs-100-v2.step")
entry = next(iter(result.scene.objects.values()))
solid = entry.mesh
chain = next(c for c in cavity_chains(entry.features, as_mesh_data(solid)) if any(f.id == "hole_3" for f in c))
say(f"== gs-100 STEP, Volumen {solid.volume:.4f}")
built_parts = construction(solid, chain, [0, 1, 2, 3], np.array([0.0, -1.0, 0.0]))
if built_parts is not None:
    restored, tool = built_parts
    for lift in (0.02, 0.04, 0.06):
        restored, tool = construction(solid, chain, [0, 1, 2, 3], np.array([0.0, -1.0, 0.0]), lift)
        for label, travel in (("-z", (0, 0, -1)), ("+z", (0, 0, 1)), ("+x", (1, 0, 0))):
            placed = moved(restored, tool, np.asarray(travel, dtype=float))
            say(f"   Zugabe {lift}: versetzen 1 mm {label}: {placed.volume - solid.volume:+.4f} mm³, dicht {as_mesh_data(placed).is_watertight}")
    say(f"   entfernen: {restored.volume - solid.volume:+.4f} mm³")

# Nachbau R 40 / r 1, exakt: das Band ist die Rundungsfläche an der Senkung
for radius, rounding in ((40.0, 1.0), (40.0, 2.0), (20.0, 1.0)):
    body_solid = built(radius, rounding)
    source = _body("brep", body_solid)
    bore = _narrowest_hole(source)
    chain = cavity_chain_state_at(bore, source.features, as_mesh_data(source.mesh)).chain
    if chain is None:
        say(f"== Nachbau R {radius:g} r {rounding:g}: keine Kette")
        continue
    twin = as_mesh_data(body_solid)
    owners = np.asarray(body_solid.raw.face_attributes[_FACE_ATTRIBUTE], dtype=np.int64)
    cavity_tris = set(int(i) for i in cavity_surface_indices(twin, chain))
    native = set(body_solid.faces_of_triangles(sorted(cavity_tris)))
    # Band: native Flächen, deren Dreiecke an die Senkung grenzen und nicht zum Hohlraum gehören
    from app.core.perceive.features import _neighbour_index

    neighbours, _ = _neighbour_index(relations._one_body(twin).raw)
    near = neighbours[np.asarray(sorted(cavity_tris), dtype=np.int64)].ravel()
    near = near[near >= 0]
    candidates = sorted(set(int(owners[i]) for i in near) - native)
    from OCP.BRepAdaptor import BRepAdaptor_Surface

    kinds = {f: str(BRepAdaptor_Surface(body_solid.faces()[f]).GetType()).split(".")[-1] for f in candidates}
    band = [f for f, k in kinds.items() if "Plane" not in k and "Cylinder" not in k]
    say(f"== Nachbau R {radius:g} r {rounding:g}: Kette {[f.id for f in chain]}, Nachbarflächen {kinds}, Band {band}")
    parts = construction(body_solid, chain, band, np.array([0.0, 0.0, -1.0]))
    if parts is None:
        continue
    restored, tool = parts
    placed = moved(restored, tool, np.array([5.0, 0.0, 0.0]))
    reference = built(radius, rounding, at=-3.0)
    say(f"   versetzen 5 mm +x: {placed.volume - body_solid.volume:+.4f} mm³ (Vergleichskörper {reference.volume - body_solid.volume:+.4f}), dicht {as_mesh_data(placed).is_watertight}")
    from nachbau import plate

    say(f"   entfernen: {restored.volume - body_solid.volume:+.4f} (Soll {plate(radius).volume - body_solid.volume:+.4f})")
