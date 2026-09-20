"""S4: Gruppe Mechanik — acht Bausteine, Netzweg gegen exakten Weg.

Bolzenscharnier (zwei erklärte Körper mit Spalt), Lagersitz, Passstift in
drei Querschnitten als Stift und als Bohrung, Scharnierauge, Rastnase (Nase
und Aussparung), Filmscharnier, Schnappverbinder (Arm und Tasche mit
Rastkante) und Schnappverbindung. Geprüft werden Gültigkeit, Körperzahl,
die Richtung der Sperrflächen und die Funktionsmaße (Spalt, Bohrung,
Wandstärke, Rastkante an der Mündung), dazu Volumen gegen Netz mit getrennt
ausgewiesener Facettierung.
"""

from __future__ import annotations

import math

import _probe as pr

from app.core import bootstrap

bootstrap.load_operations()

from app.core.geom.boolean import BOOLEAN_OVERLAP  # noqa: E402
from app.core.knowledge import standards  # noqa: E402
from app.core.knowledge.parts import shapes  # noqa: E402
from app.core.knowledge.parts.mechanics import (  # noqa: E402
    SNAP_LEAD_ANGLE,
    SNAP_MIN_ARM,
    SNAP_RATIO,
)
from app.core.knowledge.parts.registry import PARTS  # noqa: E402

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


def lying_x(diameter: float, length: float, at: tuple[float, float, float]):  # type: ignore[no-untyped-def]
    """Zylinder mit Achse in X, zentriert bei ``at``."""
    body = pr.moved(pr.cylinder(diameter, length), (0.0, 0.0, -length / 2.0))
    return pr.moved(pr.turned(body, 90.0, (0.0, 1.0, 0.0)), at)


# --- barrel_hinge -----------------------------------------------------------------

pr.out("== barrel_hinge (Bolzen 4, Breite 24, Ausladung 12, Wand 2,5, Spiel 0,3) ==")
pin, width, reach, wall, play = 4.0, 24.0, 12.0, 2.5, 0.3
spec, produced = build_mesh("barrel_hinge", pin=pin, width=width, reach=reach, wall=wall, play=play)
mi = pr.mesh_report("barrel_hinge", produced.mesh)
gap = max(play, BOOLEAN_OVERLAP)
outer = pin + 2.0 * (gap + wall)
half = (width - gap) / 2.0
x_left, x_right = -(width - half) / 2.0, (width - half) / 2.0
left = pr.union(
    lying_x(outer, half, (x_left, reach, outer / 2.0)),
    pr.moved(pr.box(half, reach, outer), (x_left, reach / 2.0, 0.0)),
)
left = pr.union(left, lying_x(pin, width, (0.0, reach, outer / 2.0)))
right = pr.union(
    lying_x(outer, half, (x_right, reach, outer / 2.0)),
    pr.moved(pr.box(half, reach, outer), (x_right, reach / 2.0, 0.0)),
)
right = pr.subtract(
    right, lying_x(pin + 2.0 * gap, width + 2.0 * BOOLEAN_OVERLAP, (0.0, reach, outer / 2.0))
)
hinge = pr.union(left, right)
info = pr.expect_solid("barrel_hinge exakt", hinge, solids=2)
pr.check(
    "barrel_hinge: Netz erklärt ebenfalls zwei Körper", mi["components"] == 2, str(mi["components"])
)
# Der Spalt: auf der Achse zwischen Bolzen (r = pin/2) und Bohrung (r = pin/2 + gap) ist Luft.
probe_r = pin / 2.0 + gap / 2.0
pr.check(
    "barrel_hinge: radialer Spalt ist Luft (rechte Lasche)",
    not pr.inside(hinge, (x_right, reach, outer / 2.0 + probe_r)),
)
pr.check(
    "barrel_hinge: Bolzen ist Material (rechte Lasche)",
    pr.inside(hinge, (x_right, reach, outer / 2.0 + pin / 2.0 - 0.05)),
)
pr.check(
    "barrel_hinge: axialer Spalt ist Luft",
    not pr.inside(hinge, (0.0, reach, outer / 2.0 + pin / 2.0 + gap + wall / 2.0)),
)
pr.check(
    "barrel_hinge: Wand über der Bohrung genau wall",
    abs(info["bounds"][5] - (outer / 2.0 + pin / 2.0 + gap + wall)) < 1e-9,
    str(info["bounds"]),
)
pr.ratio("barrel_hinge: Netz/exakt Volumen ~ Facettierung", mi["volume"], info["volume"], 0.006)
same_bounds("barrel_hinge: Bounds Netz = exakt", mi, info)
pr.step_roundtrip("barrel_hinge", hinge)

# --- bearing_seat ---------------------------------------------------------------------

pr.out()
pr.out("== bearing_seat (608, fest, Übermaß 0,1) ==")
entry = standards.bearing("608")
spec, produced = build_mesh("bearing_seat", size="608", removable=False, grip=0.1, extra_depth=0.0)
mi = pr.mesh_report("bearing_seat", produced.mesh)
diameter = entry.outer - 0.1
tool = pr.moved(pr.cylinder(diameter, entry.width + BOOLEAN_OVERLAP), (0.0, 0.0, -entry.width))
info = pr.expect_solid("bearing_seat exakt", tool)
pr.close(
    "bearing_seat: Sitz-Ø = außen minus Übermaß",
    2 * pr.radial_extent(tool, -entry.width / 2),
    diameter,
    1e-6,
)
pr.check(
    "bearing_seat: unter der Mündung",
    info["bounds"][5] <= BOOLEAN_OVERLAP + 1e-9,
    str(info["bounds"]),
)
pr.ratio("bearing_seat: Netz/exakt = Facettierung", mi["volume"], info["volume"], 0.004)
pr.close("bearing_seat: Facettierungsverhältnis genau", mi["volume"] / info["volume"], FACET, 1e-6)

# --- dowel ---------------------------------------------------------------------------

pr.out()
pr.out("== dowel: Stift rund/hex/dovetail, Bohrung rund mit Fase ==")
d, length, chamfer, play = 6.0, 8.0, 0.6, 0.2


def ring_exact(diameter: float, chamfer: float):  # type: ignore[no-untyped-def]
    outer = pr.cylinder(diameter + 2.0 * BOOLEAN_OVERLAP, chamfer + BOOLEAN_OVERLAP)
    inner = pr.cone(diameter, diameter - 2.0 * chamfer, chamfer)
    return pr.subtract(outer, inner)


for shape in ("round", "hex", "dovetail"):
    spec, produced = build_mesh(
        "dowel", diameter=d, length=length, kind="pin", shape=shape, chamfer=chamfer, play=play
    )
    mi = pr.mesh_report(f"dowel pin {shape}", produced.mesh)
    if shape == "round":
        core = pr.cylinder(d, length)
    elif shape == "hex":
        core = pr.hexagon(d * math.sqrt(3.0) / 2.0, length)
    else:
        # Gerundeter Schwalbenschwanz: 300°-Bogen im Umkreis, hinten die Sehne.
        from app.core.sketch.profile import Profile, ProfileSegment

        r = d / 2.0
        a0, a1 = -math.pi / 3.0, -math.pi / 3.0 + 5.0 * math.pi / 3.0
        start = (r * math.cos(a0), r * math.sin(a0))
        end = (r * math.cos(a1), r * math.sin(a1))
        mid = (r * math.cos((a0 + a1) / 2.0), r * math.sin((a0 + a1) / 2.0))
        from app.core.brep import profiles

        core = profiles.extrude(
            Profile(
                segments=(
                    ProfileSegment("arc", start, end, via=mid),
                    ProfileSegment("line", end, start),
                )
            ),
            length,
        )
    body = pr.subtract(core, pr.moved(ring_exact(d, chamfer), (0.0, 0.0, length - chamfer)))
    info = pr.expect_solid(f"dowel pin {shape} exakt", body)
    pr.check(
        f"dowel pin {shape}: steht auf der Fläche, Länge {length}",
        abs(info["bounds"][2]) < 1e-9 and abs(info["bounds"][5] - length) < 1e-9,
        str(info["bounds"]),
    )
    pr.check(
        f"dowel pin {shape}: Umkreis ≤ Ø",
        info["bounds"][3] - info["bounds"][0] <= d + 1e-9
        and info["bounds"][4] - info["bounds"][1] <= d + 1e-9,
        str(info["bounds"]),
    )
    # Die Fase bricht die Oberkante auf Ø - 2·Fase; eine Flachseite, die schon
    # innerhalb liegt (Sechskant-Apothem), wird nur bis dorthin beschnitten.
    expected_top = min(pr.radial_extent(body, length / 2.0), d / 2.0 - chamfer)
    pr.close(
        f"dowel pin {shape}: Fase verengt oben auf min(Apothem, r - Fase)",
        pr.radial_extent(body, length - 1e-4),
        expected_top,
        1e-3,
    )
    tol = 0.004 if shape != "hex" else 0.02
    pr.ratio(f"dowel pin {shape}: Netz/exakt Volumen", mi["volume"], info["volume"], tol)
    pr.step_roundtrip(f"dowel pin {shape}", body)

spec, produced = build_mesh(
    "dowel", diameter=d, length=length, kind="bore", shape="round", chamfer=chamfer, play=play
)
mi = pr.mesh_report("dowel bore round", produced.mesh)
bore_d = d + play
tool = pr.moved(pr.cylinder(bore_d, length), (0.0, 0.0, -length))
lead = pr.moved(pr.cone(bore_d, bore_d + 2.0 * chamfer, chamfer), (0.0, 0.0, -chamfer))
tool = pr.union(tool, lead)
info = pr.expect_solid("dowel bore exakt", tool)
pr.check(
    "dowel bore: unter der Mündung",
    abs(info["bounds"][5]) < 1e-9 and abs(info["bounds"][2] + length) < 1e-9,
    str(info["bounds"]),
)
pr.close("dowel bore: Ø = Nenn + Spiel", 2 * pr.radial_extent(tool, -length / 2), bore_d, 1e-6)
pr.check(
    "dowel bore: Fase weitet an der Mündung",
    2 * pr.radial_extent(tool, -1e-4) > bore_d + 2 * chamfer - 1e-3,
)
pr.ratio("dowel bore: Netz/exakt = Facettierung", mi["volume"], info["volume"], 0.004)

# --- hinge_eye -----------------------------------------------------------------------

pr.out()
pr.out("== hinge_eye (Stift 3, Breite 8, Abstand 8, Wand 2, Spiel 0,2) ==")
pin, width, reach, wall, play = 3.0, 8.0, 8.0, 2.0, 0.2
spec, produced = build_mesh("hinge_eye", pin=pin, width=width, reach=reach, wall=wall, play=play)
mi = pr.mesh_report("hinge_eye", produced.mesh)
bore_w = pin + play
outer = bore_w + 2.0 * wall
eye = lying_x(outer, width, (0.0, reach, outer / 2.0))
lug = pr.moved(pr.box(width, reach, outer), (0.0, reach / 2.0, 0.0))
body = pr.subtract(
    pr.union(eye, lug), lying_x(bore_w, width + 2.0 * BOOLEAN_OVERLAP, (0.0, reach, outer / 2.0))
)
info = pr.expect_solid("hinge_eye exakt", body)
pr.check("hinge_eye: Bohrung frei", not pr.inside(body, (0.0, reach, outer / 2.0)))
pr.check(
    "hinge_eye: Wand hinter der Bohrung genau wall (exakt, keine Facettenkorrektur)",
    abs((info["bounds"][4] - reach) - (bore_w / 2.0 + wall)) < 1e-9,
    str(info["bounds"]),
)
mesh_reach, exact_reach = mi["bounds"][4] - reach, info["bounds"][4] - reach
pr.out(f"  Netz-Außenradius: {mesh_reach:.6f} (mit Facettenkorrektur), exakt {exact_reach:.6f}")
pr.check(
    "hinge_eye: Netz ist um die Facettenkorrektur größer (erlaubter Unterschied)",
    (mi["bounds"][4] - reach) > (info["bounds"][4] - reach)
    and (mi["bounds"][4] - reach) - (info["bounds"][4] - reach) < 0.02,
)
pr.step_roundtrip("hinge_eye", body)

# --- latch --------------------------------------------------------------------------

pr.out()
pr.out("== latch (Breite 6, Überstand 1, Höhe 3; Nase und Aussparung mit Spiel 0,2) ==")
width, depth, height = 6.0, 1.0, 3.0
for negative in (False, True):
    grow = 0.2 if negative else 0.0
    spec, produced = build_mesh(
        "latch", width=width, depth=depth, height=height, negative=negative, play=0.2
    )
    mi = pr.mesh_report(f"latch negative={negative}", produced.mesh)
    body = pr.wedge(width + 2 * grow, depth + grow, height + grow, 0.0)
    body = pr.moved(pr.turned(body, 180.0, (1.0, 0.0, 0.0)), (0.0, 0.0, height + grow))
    info = pr.expect_solid(f"latch negative={negative} exakt", body)
    pr.close(
        f"latch negative={negative}: Volumen",
        info["volume"],
        (width + 2 * grow) * (depth + grow) * (height + grow) / 2.0,
        1e-9,
    )
    # Lage der Sperrfläche: Netz und exakt müssen an denselben Punkten Material
    # haben. Nach der Drehung um X liegt die Nase in -Y; wo sie voll tief ist
    # (Sperrfläche) und wo sie ausläuft (Schräge), sagt der Punkttest.
    probes = [
        (0.0, -(depth + grow) + 0.01, 0.01),
        (0.0, -(depth + grow) + 0.01, height + grow - 0.01),
        (0.0, -(depth + grow) * 0.5, 0.01),
        (0.0, -(depth + grow) * 0.5, height + grow - 0.01),
    ]
    exact_hits = [pr.inside(body, q) for q in probes]
    mesh_hits = pr.mesh_contains(produced.mesh, probes)
    pr.check(
        f"latch negative={negative}: Sperrfläche und Schräge liegen wie im Netz",
        exact_hits == mesh_hits,
        f"exakt {exact_hits} / Netz {mesh_hits}",
    )
    full_depth_at_top = exact_hits[1] and not exact_hits[0]
    pr.out(f"  volle Tiefe liegt {'oben (z = Höhe)' if full_depth_at_top else 'unten (z = 0)'}")
    same_bounds(f"latch negative={negative}: Bounds Netz = exakt", mi, info)
    pr.close(
        f"latch negative={negative}: Netz = exakt (keine Rundformen)",
        mi["volume"],
        info["volume"],
        1e-9,
    )

# --- living_hinge ---------------------------------------------------------------------

pr.out()
pr.out("== living_hinge (30, Flügel 15, Stärke 2, Film 0,4, Spalt 1,5) ==")
spec, produced = build_mesh("living_hinge", width=30.0, leaf=15.0, thickness=2.0, film=0.4, gap=1.5)
mi = pr.mesh_report("living_hinge", produced.mesh)
plate = pr.box(30.0, 31.5, 2.0)
groove = pr.moved(pr.box(30.0 + 2 * BOOLEAN_OVERLAP, 1.5, 2.0), (0.0, 0.0, 0.4))
body = pr.subtract(plate, groove)
info = pr.expect_solid("living_hinge exakt", body)
pr.close("living_hinge: Volumen", info["volume"], 30 * 31.5 * 2 - 30 * 1.5 * 1.6, 1e-9)
pr.check(
    "living_hinge: Film liegt unten (0..0,4)",
    pr.inside(body, (0.0, 0.0, 0.2)) and not pr.inside(body, (0.0, 0.0, 0.6)),
)
pr.close("living_hinge: Netz = exakt", mi["volume"], info["volume"], 1e-9)

# --- snap_connector --------------------------------------------------------------------

pr.out()
pr.out("== snap_connector (Ø 6, Länge 9; Arm und Tasche, Spiel 0,2) ==")
diameter, length, play = 6.0, 9.0, 0.2
room = math.sqrt(max(diameter**2 - (SNAP_MIN_ARM + play) ** 2, 0.0))
thickness = min(length / SNAP_RATIO, (room - play) / 3.0)
hook = thickness
across = 3.0 * thickness + play
width = max(SNAP_MIN_ARM, math.sqrt(max(diameter**2 - across**2, 0.0)) - play)
run = hook / math.tan(math.radians(SNAP_LEAD_ANGLE))
catch = length - run
rest = across / 2.0 - play / 2.0
arm_centre = rest - hook - thickness / 2.0

spec, produced = build_mesh(
    "snap_connector", diameter=diameter, length=length, kind="pin", play=play
)
mi = pr.mesh_report("snap_connector pin", produced.mesh)
arm = pr.moved(pr.box(width, thickness, length), (0.0, arm_centre, 0.0))
tip = pr.moved(
    pr.wedge(width, hook + BOOLEAN_OVERLAP, run),
    (0.0, arm_centre + thickness / 2.0 - BOOLEAN_OVERLAP, catch),
)
body = pr.union(arm, tip)
info = pr.expect_solid("snap_connector pin exakt", body)
pr.check(
    "snap_connector pin: Haken sitzt oben (Keil ab z=catch)",
    pr.inside(body, (0.0, arm_centre + thickness / 2.0 + hook * 0.5, catch + 0.01))
    and not pr.inside(body, (0.0, arm_centre + thickness / 2.0 + hook * 0.5, catch - 0.01)),
)
same_bounds("snap_connector pin: Bounds Netz = exakt", mi, info)
pr.close("snap_connector pin: Netz = exakt", mi["volume"], info["volume"], 1e-6)

spec, produced = build_mesh(
    "snap_connector", diameter=diameter, length=length, kind="bore", play=play
)
mi = pr.mesh_report("snap_connector bore", produced.mesh)
depth = length + shapes.SEAT_RELIEF
slot = pr.moved(pr.box(width + play, across, depth), (0.0, 0.0, -depth))
lip = pr.moved(
    pr.box(width + play + 2.0 * BOOLEAN_OVERLAP, hook, catch),
    (0.0, across / 2.0 - hook / 2.0, -catch),
)
body = pr.subtract(slot, lip)
info = pr.expect_solid("snap_connector bore exakt", body)
# Richtung: Die Rastkante (fehlendes Werkzeugmaterial) liegt zwischen Mündung und -catch,
# nicht am tiefen Ende. Im Werkzeug ist dort **kein** Volumen.
pr.check(
    "snap_connector bore: Rastkante zwischen Mündung und Haken (Werkzeug leer)",
    not pr.inside(body, (0.0, across / 2.0 - hook / 2.0, -catch / 2.0)),
)
pr.check(
    "snap_connector bore: unter der Rastkante ist das Werkzeug voll (Haken-Raum)",
    pr.inside(body, (0.0, across / 2.0 - hook / 2.0, -catch - 0.05)),
)
pr.check(
    "snap_connector bore: unter der Mündung", abs(info["bounds"][5]) < 1e-9, str(info["bounds"])
)
same_bounds("snap_connector bore: Bounds Netz = exakt", mi, info)
pr.close("snap_connector bore: Netz = exakt", mi["volume"], info["volume"], 1e-6)

# --- snap_fit ------------------------------------------------------------------------

pr.out()
pr.out("== snap_fit (Breite 8, Länge 16, Arm 1,6, Haken 1,2, Winkel 35) ==")
width, length, thickness, hook, angle = 8.0, 16.0, 1.6, 1.2, 35.0
spec, produced = build_mesh(
    "snap_fit", width=width, length=length, thickness=thickness, hook=hook, lead_angle=angle
)
mi = pr.mesh_report("snap_fit", produced.mesh)
hook_height = hook / math.tan(math.radians(angle))
arm_len = max(length, thickness * SNAP_RATIO, hook_height)
half = thickness / 2.0
points = [(-half, 0.0), (half, 0.0)]
if hook_height < arm_len:
    points.append((half, arm_len - hook_height))
points.extend(((half + hook, arm_len), (-half, arm_len)))
from app.core.brep import profiles as bp  # noqa: E402

body = pr.moved(bp.extrude(pr.polygon(points), width, "plane:yz"), (-width / 2.0, 0.0, 0.0))
info = pr.expect_solid("snap_fit exakt", body)
pr.close(
    "snap_fit: Volumen",
    info["volume"],
    width * (thickness * arm_len + hook * hook_height / 2.0),
    1e-9,
)
pr.check(
    "snap_fit: Haltefläche oben (Haken bei z=arm_len voll breit)",
    pr.inside(body, (0.0, half + hook - 0.01, arm_len - 0.01))
    and not pr.inside(body, (0.0, half + hook - 0.01, arm_len - hook_height - 0.01)),
)
same_bounds("snap_fit: Bounds Netz = exakt", mi, info)
pr.close("snap_fit: Netz = exakt", mi["volume"], info["volume"], 1e-6)
pr.step_roundtrip("snap_fit", body)

pr.finish("S4 Mechanik")
