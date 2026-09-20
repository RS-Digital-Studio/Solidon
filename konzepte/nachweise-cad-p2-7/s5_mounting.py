"""S5: Gruppe Befestigung — sieben Bausteine, Netzweg gegen exakten Weg.

Standfuß (Fuß und Tasche als Drehkörper), Schlüsselloch (Einstieg, Kopfkanal
unter der Rückhaltekante, Schaftschlitz), Magnettasche mit Haltelippe
(Verengung als fehlendes Werkzeugvolumen), Lochwand-Einhänger (Langloch-
Zapfen, Nase, Rastzunge; ``joined_by_host``), Wandhalter mit Normlöchern
und die beiden Profilklemmen-Bausteine (Normalversatz einer gezeichneten
Kontur, Halbierung, Ohren, Normteilaufnahmen).

Bei den Klemmen liegt die einzige Stelle, an der der exakte Weg mehr
braucht als Prisma, Drehkörper und Boolesche Operationen: den **Normalversatz
einer Skizzenkontur**. Geprüft wird ``BRepOffsetAPI_MakeOffset`` auf dem
Draht der Kontur — vorhanden in der festgeschriebenen OCP-Bindung.
"""

from __future__ import annotations

import math

import _probe as pr

from app.core import bootstrap

bootstrap.load_operations()

from app.core.brep import profiles  # noqa: E402
from app.core.geom.boolean import BOOLEAN_OVERLAP  # noqa: E402
from app.core.knowledge import standards  # noqa: E402
from app.core.knowledge.parts import shapes  # noqa: E402
from app.core.knowledge.parts.mounting import (  # noqa: E402
    HEAD_CLEARANCE,
    MAGNET_LIP_HEIGHT,
    MIN_FOOT_TIP,
    POCKET_LEAD,
)
from app.core.knowledge.parts.registry import PARTS  # noqa: E402
from app.core.sketch import shapes as sketch_shapes  # noqa: E402
from app.core.sketch.profile import Profile, profile_of  # noqa: E402
from app.core.sketch.serialize import sketch_from_text, sketch_to_text  # noqa: E402
from app.core.sketch.solver import solve_sketch  # noqa: E402

FACET = pr.polygon_ratio(shapes.SEGMENTS)


def build_mesh(name: str, **values: object):  # type: ignore[no-untyped-def]
    spec = PARTS.get(name)
    params = spec.params(**values)
    return spec, spec.fn(params)


def same_bounds(label: str, mesh_info: dict, info: dict, tol: float = 1e-6) -> None:  # type: ignore[type-arg]
    pr.check(
        label,
        all(abs(a - b) < tol for a, b in zip(mesh_info["bounds"], info["bounds"], strict=True)),
        f"{mesh_info['bounds']} / {info['bounds']}",
    )


def falling_slot(width: float, length: float, height: float):  # type: ignore[no-untyped-def]
    """Langloch mit der Länge in Y — wie ``keyhole.falling``."""
    return pr.turned(pr.slot(width, length, height), 90.0)


# --- foot ---------------------------------------------------------------------------

pr.out("== foot: Fuß Ø10 h3 und Tasche Ø10 h3 (Spiel 0,2) ==")
diameter, height = 10.0, 3.0
spec, produced = build_mesh(
    "foot", kind="foot", diameter=diameter, height=height, chamfer=0.0, play=0.0
)
mi = pr.mesh_report("foot", produced.mesh)
chamfer = min(height / 5.0, height / 2.0, (diameter - MIN_FOOT_TIP) / 2.0)
narrow = diameter - 2.0 * chamfer
body = pr.revolved(
    [
        (0.0, 0.0),
        (diameter / 2.0, 0.0),
        (diameter / 2.0, height - chamfer),
        (narrow / 2.0, height),
        (0.0, height),
    ]
)
info = pr.expect_solid("foot exakt", body)
pr.check(
    "foot: Kegelfläche am Standende (oben, z=height)",
    info["types"].get("cone") == 1
    and abs(2 * pr.radial_extent(body, height - 1e-4) - narrow) < 1e-3,
    str(info["types"]),
)
pr.close("foot: Säule Ø am Teil", 2 * pr.radial_extent(body, 0.5), diameter, 1e-6)
pr.ratio("foot: Netz/exakt = Facettierung", mi["volume"], info["volume"], 0.004)
pr.step_roundtrip("foot", body)

spec, produced = build_mesh(
    "foot", kind="pocket", diameter=diameter, height=height, chamfer=0.0, play=0.2
)
mi = pr.mesh_report("foot pocket", produced.mesh)
wide = diameter + 0.2
lead = min(POCKET_LEAD, height / 2.0)
tool = pr.revolved(
    [
        (0.0, -height),
        (wide / 2.0, -height),
        (wide / 2.0, -lead),
        (wide / 2.0 + lead, 0.0),
        (0.0, 0.0),
    ]
)
info = pr.expect_solid("foot pocket exakt", tool)
pr.check(
    "foot pocket: unter der Mündung",
    abs(info["bounds"][5]) < 1e-9 and abs(info["bounds"][2] + height) < 1e-9,
    str(info["bounds"]),
)
pr.close(
    "foot pocket: Sitz hat vollen Ø (nicht den schmalen)",
    2 * pr.radial_extent(tool, -height + 0.3),
    wide,
    1e-6,
)
pr.check(
    "foot pocket: Schräge weitet die Mündung",
    2 * pr.radial_extent(tool, -1e-4) > wide + 2 * lead - 1e-3,
)
pr.ratio("foot pocket: Netz/exakt = Facettierung", mi["volume"], info["volume"], 0.004)

# --- keyhole ---------------------------------------------------------------------------

pr.out()
pr.out("== keyhole (M4, Einhängeweg 8, Tiefe 4, Kopftiefe 2,5, Spiel 0,2) ==")
screw = standards.screw("M4")
drop, depth, head_room, play = 8.0, 4.0, 2.5, 0.2
spec, produced = build_mesh(
    "keyhole", size="M4", drop=drop, depth=depth, head_room=head_room, play=play
)
mi = pr.mesh_report("keyhole", produced.mesh)
clearance = HEAD_CLEARANCE + play
half_drop = -drop / 2.0
entrance = pr.moved(
    pr.cylinder(screw.head + clearance, depth + BOOLEAN_OVERLAP), (0.0, 0.0, -depth)
)
pocket = pr.moved(
    falling_slot(screw.head + clearance, screw.head + clearance + drop, head_room),
    (0.0, half_drop, -depth),
)
shaft = pr.moved(
    falling_slot(screw.clearance, screw.clearance + drop, depth + 2.0 * BOOLEAN_OVERLAP),
    (0.0, half_drop, -depth - BOOLEAN_OVERLAP),
)
tool = pr.union(entrance, pocket, shaft)
info = pr.expect_solid("keyhole exakt", tool)
pr.check(
    "keyhole: unter der Mündung", info["bounds"][5] <= BOOLEAN_OVERLAP + 1e-9, str(info["bounds"])
)
pr.check(
    "keyhole: Schlitz läuft in -Y (Bounds ymin < -ymax)",
    info["bounds"][1] < -info["bounds"][4] + 1e-9,
    str(info["bounds"]),
)
# Rückhaltekante: über dem Kopfkanal (z zwischen -depth+head_room und 0) ist am
# Schlitzende nur der Schaft frei.
y_end = half_drop - drop / 2.0
pr.check(
    "keyhole: Kopfkanal am Schlitzende offen (unten)",
    pr.inside(tool, (0.0, y_end, -depth + head_room / 2.0)),
)
head_w = 0.0
for x in (screw.clearance / 2.0 + 0.05, (screw.head + clearance) / 2.0 - 0.05):
    head_w += 1.0 if pr.inside(tool, (x, y_end, -depth + head_room + 0.5)) else 0.0
pr.check(
    "keyhole: über dem Kopfkanal nur der Schaft frei (Kopfbreite ist Material)",
    head_w == 0.0,
    f"Treffer {head_w}",
)
pr.check(
    "keyhole: Einstieg kopfbreit bis zur Mündung",
    pr.inside(tool, ((screw.head + clearance) / 2.0 - 0.05, 0.0, -0.1)),
)
pr.ratio("keyhole: Netz/exakt = Facettierung", mi["volume"], info["volume"], 0.004)
pr.step_roundtrip("keyhole", tool)

# --- magnet_pocket -----------------------------------------------------------------------

pr.out()
pr.out("== magnet_pocket (8x3, Spiel 0,2, Lippe, Übermaß 0,15, ohne Deckschicht) ==")
entry = standards.magnet("8x3")
play, grip = 0.2, 0.15
spec, produced = build_mesh(
    "magnet_pocket", size="8x3", play=play, cover=0.0, press_lip=True, grip=grip
)
mi = pr.mesh_report("magnet_pocket", produced.mesh)
diameter = entry.diameter + play
narrow = entry.diameter - grip
lip_height = min(MAGNET_LIP_HEIGHT, entry.height / 2.0)
pocket = pr.moved(pr.cylinder(diameter, entry.height - lip_height), (0.0, 0.0, -entry.height))
lip = pr.moved(pr.cone(diameter, narrow, lip_height), (0.0, 0.0, -lip_height))
skin = pr.moved(pr.cylinder(narrow, BOOLEAN_OVERLAP), (0.0, 0.0, 0.0))
tool = pr.union(pocket, lip, skin)
info = pr.expect_solid("magnet_pocket exakt", tool)
pr.close(
    "magnet_pocket: Öffnung an der Mündung = Magnet minus Übermaß",
    2 * pr.radial_extent(tool, -1e-5),
    narrow,
    1e-3,
)
pr.close(
    "magnet_pocket: Tasche unten = Magnet plus Spiel",
    2 * pr.radial_extent(tool, -entry.height + 0.5),
    diameter,
    1e-6,
)
pr.check("magnet_pocket: Öffnung enger als Tasche (hält)", narrow < diameter)
pr.ratio("magnet_pocket: Netz/exakt = Facettierung", mi["volume"], info["volume"], 0.004)
pr.step_roundtrip("magnet_pocket", tool)

# --- wall_mount ------------------------------------------------------------------------

pr.out()
pr.out("== wall_mount (30 x 25 x 3, M4, 2 Löcher, Auflage 12) ==")
spec, produced = build_mesh(
    "wall_mount", width=30.0, height=25.0, thickness=3.0, size="M4", holes=2, lip=12.0
)
mi = pr.mesh_report("wall_mount", produced.mesh)
width, height, thickness, lip = 30.0, 25.0, 3.0, 12.0
plate = pr.box(width, thickness, height)
join = min(thickness / 2.0, lip)
shelf = pr.moved(
    pr.box(width, lip + join, thickness), (0.0, thickness / 2.0 + lip / 2.0 - join / 2.0, 0.0)
)
body = pr.union(plate, shelf)
spacing = width / 3.0
for index in range(1, 3):
    x = -width / 2.0 + spacing * index
    hole = pr.turned(
        pr.cylinder(screw.clearance, thickness + 2 * BOOLEAN_OVERLAP), -90.0, (1.0, 0.0, 0.0)
    )
    body = pr.subtract(body, pr.moved(hole, (x, -thickness / 2.0 - BOOLEAN_OVERLAP, height / 2.0)))
info = pr.expect_solid("wall_mount exakt", body)
pr.check(
    "wall_mount: zwei Zylinderflächen (Löcher)",
    info["types"].get("cylinder") == 2,
    str(info["types"]),
)
pr.check(
    "wall_mount: Loch geht durch (Y-Achse)",
    not pr.inside(body, (-width / 2.0 + spacing, 0.0, height / 2.0)),
)
expected = (
    width * thickness * height
    + width * lip * thickness
    - 2 * math.pi * (screw.clearance / 2) ** 2 * thickness
)
pr.close("wall_mount: Volumen gegen Analytik", info["volume"], expected, 1e-6)
pr.ratio("wall_mount: Netz/exakt (nur Löcher facettiert)", mi["volume"], info["volume"], 0.001)
pr.step_roundtrip("wall_mount", body)

# --- pegboard_hook ---------------------------------------------------------------------

pr.out()
pr.out("== pegboard_hook (skadis, 2 Haken, Rastzunge, ohne Rückplatte, Spiel 0,2) ==")
board = standards.board("skadis")
play = 0.2
spec, produced = build_mesh(
    "pegboard_hook",
    system="skadis",
    count=2,
    steps=1,
    upright=False,
    latch=True,
    plate=0.0,
    play=play,
    lip=0.0,
)
mi = pr.mesh_report("pegboard_hook", produced.mesh)
from app.core.knowledge.parts.mounting import _latch_tongue  # noqa: E402

width = board.slot_width - play
lip = board.thickness * (2.0 / 3.0)
usable = board.slot_height - play
travel = usable / 4.0
nose = travel
shank = usable - nose - travel
reach = board.pitch
span = reach
through = board.thickness + play
sunk = 0.0
tongue = _latch_tongue(
    width=width,
    slot_width=board.slot_width,
    travel=travel,
    through=through,
    lip=lip,
    sunk=sunk,
    system="skadis",
)
parts = []
for index in range(2):
    x = index * reach - span / 2.0
    shaft = pr.turned(pr.slot(width, shank, through - sunk), 90.0)
    parts.append(pr.moved(shaft, (x, -nose / 2.0, sunk)))
    hook_join = min(through / 2.0, lip / 2.0)
    catch = pr.turned(pr.slot(width, shank + nose, lip + hook_join), 90.0)
    parts.append(pr.moved(catch, (x, 0.0, through - hook_join)))
    crown = -nose / 2.0 - shank / 2.0
    base = crown - tongue.gap
    crest = base - tongue.thickness
    arm = pr.box(tongue.width, tongue.thickness, tongue.lock - sunk)
    parts.append(pr.moved(arm, (x, crest + tongue.thickness / 2.0, sunk)))
    reachdown = tongue.gap + tongue.thickness + width / 2.0
    root = pr.box(tongue.width, reachdown, tongue.thickness)
    parts.append(pr.moved(root, (x, crest + reachdown / 2.0, sunk)))
    barb = pr.turned(pr.wedge(tongue.width, tongue.step + BOOLEAN_OVERLAP, tongue.run), 180.0)
    parts.append(pr.moved(barb, (x, crest + BOOLEAN_OVERLAP, tongue.lock)))
hook_body = pr.union(*parts)
info = pr.expect_solid("pegboard_hook exakt (ohne Träger: zwei Haken)", hook_body, solids=2)
pr.check(
    "pegboard_hook: Netz ebenfalls zwei Körper (joined_by_host)",
    mi["components"] == 2,
    str(mi["components"]),
)
pr.check(
    "pegboard_hook: Nase greift hinter die Platte (z > through)",
    info["bounds"][5] > through + lip - 1e-6,
    str(info["bounds"]),
)
pr.check(
    "pegboard_hook: Zapfen sitzt oben = -Y (ymin trägt Zunge)",
    info["bounds"][1] < -shank / 2.0,
    str(info["bounds"]),
)
pr.check(
    "pegboard_hook: Langloch-Zapfen trägt Zylinderflächen",
    info["types"].get("cylinder", 0) >= 4,
    str(info["types"]),
)
# Die Nasenspitze ist im Netz ein Bogen aus 24 Punkten ohne Punkt auf der Achse:
# ihr Extremum liegt um r·(1 - cos(pi/46)) innerhalb des exakten Halbkreises.
sag = (width / 2.0) * (1.0 - math.cos(math.pi / 46.0))
pr.out(f"  Facettierungs-Sag der Langlochenden: {sag:.6f}")
same_bounds(
    "pegboard_hook: Bounds Netz = exakt bis auf den Facettierungs-Sag", mi, info, tol=sag + 1e-6
)
pr.ratio(
    "pegboard_hook: Netz/exakt Volumen (Langlochenden facettiert)",
    mi["volume"],
    info["volume"],
    0.004,
)
pr.step_roundtrip("pegboard_hook", hook_body)

# --- profile_clamp: Normalversatz einer Kontur ---------------------------------------------

pr.out()
pr.out("== profile_clamp_shell: Sitzkontur Kreis Ø20,25, Wand 4, Tiefe 40, untere Hälfte, M4 ==")
seat_text = sketch_to_text(sketch_shapes.circle(20.25))
spec, produced = build_mesh(
    "profile_clamp_shell",
    seat_sketch=seat_text,
    depth=40.0,
    wall=4.0,
    half="lower",
    joint_gap=1.0,
    split_angle=0.0,
    split_offset=0.0,
    screw_size="M4",
    play=0.2,
)
mi = pr.mesh_report("profile_clamp_shell", produced.mesh)


def offset_wire(profile: Profile, distance: float):  # type: ignore[no-untyped-def]
    """Exakter Normalversatz der Kontur über ``BRepOffsetAPI_MakeOffset``.

    Der eine Baustein, den die Klemmen zusätzlich brauchen; ``_face`` ist der
    Sondenzugriff auf den vorhandenen Flächenbau, kein Produktionsweg."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakeOffset
    from OCP.GeomAbs import GeomAbs_Arc
    from OCP.TopoDS import TopoDS

    face = profiles._face(profile, profiles._lift_xy)
    offset = BRepOffsetAPI_MakeOffset(TopoDS.Face(face), GeomAbs_Arc)
    offset.Perform(distance)
    if not offset.IsDone():
        raise RuntimeError("Offset scheiterte")
    wire = TopoDS.Wire(offset.Shape())
    return BRepBuilderAPI_MakeFace(wire, True).Face()


seat_profile = profile_of(solve_sketch(sketch_from_text(seat_text)))
pr.check("Sitzkontur ist ein exakter Kreis im Profil", seat_profile.circle is not None)
from OCP.BRepPrimAPI import BRepPrimAPI_MakePrism  # noqa: E402
from OCP.gp import gp_Vec  # noqa: E402

from app.core.brep.kernel import Solid  # noqa: E402

outer_face = offset_wire(seat_profile, 4.0)
outer_solid = Solid(BRepPrimAPI_MakePrism(outer_face, gp_Vec(0.0, 0.0, 40.0)).Shape())
oi = pr.expect_solid("Offset-Kontur (Kreis + 4) extrudiert", outer_solid)
pr.close("Offset: Außen-Ø = 20,25 + 8", oi["bounds"][3] - oi["bounds"][0], 28.25, 1e-6)
pr.check("Offset: bleibt ein exakter Zylinder", oi["types"].get("cylinder") == 1, str(oi["types"]))
seat_solid = profiles.extrude(seat_profile, 40.0)
shell_ring = pr.subtract(outer_solid, seat_solid)
screw, nut = standards.screw("M4"), standards.nut("M4")
wall, play, joint_gap, depth = 4.0, 0.2, 1.0, 40.0
head_d = screw.head + play
nut_d = (nut.width + play) * 2.0 / math.sqrt(3.0)
ear_w = max(head_d, nut_d) + 2.0 * wall
ear_h = max(screw.head_height, nut.height) + wall + joint_gap / 2.0
left, right = -28.25 / 2.0, 28.25 / 2.0
centres = (left - ear_w / 2.0 + wall, right + ear_w / 2.0 - wall)
shell = shell_ring
for x in centres:
    shell = pr.union(shell, pr.moved(pr.box(ear_w, 2 * ear_h, depth), (x, 0.0, 0.0)))
# untere Hälfte: alles unter y = -joint_gap/2
reach_box = 100.0
lower_box = pr.moved(
    pr.box(2 * reach_box, reach_box, depth + 2), (0.0, -joint_gap / 2.0 - reach_box / 2.0, -1.0)
)
shell = pr.intersect(shell, lower_box)
for x in centres:
    through = pr.turned(
        pr.cylinder(screw.clearance, 2 * ear_h + 2 * BOOLEAN_OVERLAP), 90.0, (1.0, 0.0, 0.0)
    )
    shell = pr.subtract(shell, pr.moved(through, (x, ear_h + BOOLEAN_OVERLAP, depth / 2.0)))
    pocket = pr.turned(
        pr.cylinder(head_d, screw.head_height + BOOLEAN_OVERLAP), -90.0, (1.0, 0.0, 0.0)
    )
    shell = pr.subtract(shell, pr.moved(pocket, (x, -ear_h - BOOLEAN_OVERLAP, depth / 2.0)))
info = pr.expect_solid("profile_clamp_shell exakt", shell)
pr.check(
    "clamp shell: Hälfte endet bei y = -0,5",
    abs(info["bounds"][4] + joint_gap / 2.0) < 1e-6,
    str(info["bounds"]),
)
pr.check(
    "clamp shell: Schraubenloch geht durchs Ohr",
    not pr.inside(shell, (centres[0], -ear_h / 2.0, depth / 2.0)),
)
pr.check(
    "clamp shell: Kopftasche unten am Ohr",
    not pr.inside(
        shell, (centres[0] + head_d / 2.0 - 0.1, -ear_h + screw.head_height / 2.0, depth / 2.0)
    ),
)
q = mi["volume"] / info["volume"]
pr.out(f"  Netz V={mi['volume']:.4f}  exakt V={info['volume']:.4f}  Verhältnis {q:.5f}")
pr.ratio("clamp shell: Netz/exakt (Sitz und Löcher facettiert)", mi["volume"], info["volume"], 0.01)
same_bounds("clamp shell: Bounds Netz = exakt", mi, info, tol=0.02)
pr.step_roundtrip("profile_clamp_shell", shell)

pr.out()
pr.out("== profile_clamp_liner: Gegenkontur Ø20, Stärke 2, Bund 1,2/1,5, hinten 2, Übermaß 0,1 ==")
counter_text = sketch_to_text(sketch_shapes.circle(20.0))
spec, produced = build_mesh(
    "profile_clamp_liner",
    counter_sketch=counter_text,
    outer_sketch="",
    depth=40.0,
    liner_thickness=2.0,
    half="lower",
    flange_width=1.2,
    flange_height=1.5,
    rear_relief=2.0,
    split_angle=0.0,
    split_offset=0.0,
    play=0.2,
    grip=0.1,
)
mi = pr.mesh_report("profile_clamp_liner", produced.mesh)
counter_profile = profile_of(solve_sketch(sketch_from_text(counter_text)))
inside_face = offset_wire(counter_profile, -0.05)
outside_face = offset_wire(Profile(circle=((0.0, 0.0), 10.0 - 0.05)), 2.0)
inside_solid = Solid(BRepPrimAPI_MakePrism(inside_face, gp_Vec(0.0, 0.0, 60.0)).Shape())
outside_solid = Solid(BRepPrimAPI_MakePrism(outside_face, gp_Vec(0.0, 0.0, 38.0)).Shape())
core = pr.moved(
    pr.subtract(outside_solid, pr.moved(inside_solid, (0.0, 0.0, -10.0))), (0.0, 0.0, 1.5)
)
flange_face = offset_wire(Profile(circle=((0.0, 0.0), 10.0 - 0.05 + 2.0)), 1.2)
flange = pr.subtract(
    Solid(BRepPrimAPI_MakePrism(flange_face, gp_Vec(0.0, 0.0, 1.5)).Shape()),
    pr.moved(inside_solid, (0.0, 0.0, -10.0)),
)
liner = pr.union(core, flange)
lower_box = pr.moved(pr.box(200.0, 100.0, 60.0), (0.0, -0.1 - 50.0, -1.0))
liner = pr.intersect(liner, lower_box)
info = pr.expect_solid("profile_clamp_liner exakt", liner)
pr.check(
    "liner: Bund vorn (z 0..1,5) breiter als Kern",
    abs(info["bounds"][2]) < 1e-9
    and pr.inside(liner, (0.0, -(10.0 - 0.05 + 2.0 + 0.6), 0.75))
    and not pr.inside(liner, (0.0, -(10.0 - 0.05 + 2.0 + 0.6), 3.0)),
)
pr.check(
    "liner: Freiraum hinten (Länge = 1,5 + 38)",
    abs(info["bounds"][5] - 39.5) < 1e-6,
    str(info["bounds"]),
)
q = mi["volume"] / info["volume"]
pr.out(f"  Netz V={mi['volume']:.4f}  exakt V={info['volume']:.4f}  Verhältnis {q:.5f}")
pr.ratio("liner: Netz/exakt (Kreise facettiert)", mi["volume"], info["volume"], 0.01)
pr.step_roundtrip("profile_clamp_liner", liner)

pr.finish("S5 Befestigung")
