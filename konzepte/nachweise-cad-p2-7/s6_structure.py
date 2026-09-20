"""S6: Gruppen Struktur und Kabel — elf Bausteine, Netzweg gegen exakten Weg.

Kabelclip (C-Bügel mit Verengung), Kabeldurchführung mit ``host_add``
(Trägeraufbau hinter der Wand plus Werkzeug), Eckwinkel, Nutfeder (T-Profil
mit Einführschräge), Versteifungsrippe mit Auslauf, die vier Organizer-Teile
(gerundete Prismen mit exakten Viertelkreisen) sowie Dichtnut und Dichtung
(Band eines gezeichneten Wegs; runde Schnur als Kugel-Sweep bzw. Torus).
"""

from __future__ import annotations

import math

import _probe as pr

from app.core import bootstrap

bootstrap.load_operations()

from app.core.geom.boolean import BOOLEAN_OVERLAP  # noqa: E402
from app.core.knowledge import standards  # noqa: E402
from app.core.knowledge.parts import shapes  # noqa: E402
from app.core.knowledge.parts.registry import PARTS  # noqa: E402
from app.core.knowledge.parts.structure import MIN_RIB, RIB_SHARE  # noqa: E402
from app.core.sketch import shapes as sketch_shapes  # noqa: E402
from app.core.sketch.profile import profile_of  # noqa: E402
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


def lying_y(diameter: float, length: float):  # type: ignore[no-untyped-def]
    """Zylinder mit Achse in Y, zentriert im Ursprung."""
    body = pr.moved(pr.cylinder(diameter, length), (0.0, 0.0, -length / 2.0))
    return pr.turned(body, 90.0, (1.0, 0.0, 0.0))


# --- cable_clip ---------------------------------------------------------------------

pr.out("== cable_clip (cable-5, Breite 8, Wand 2, Verengung 0 -> Ø/5, Spiel 0,2) ==")
entry = standards.tube("cable-5")
width, wall, play = 8.0, 2.0, 0.2
spec, produced = build_mesh(
    "cable_clip", size="cable-5", diameter=0.0, width=width, wall=wall, grip=0.0, play=play
)
mi = pr.mesh_report("cable_clip", produced.mesh)
diameter = entry.outer
inner = diameter + play
outer = inner + 2.0 * wall
base = wall
centre = base + inner / 2.0
grip = diameter / 5.0
gap = diameter - 2.0 * grip
ring = pr.subtract(
    pr.moved(lying_y(outer, width), (0.0, 0.0, centre)),
    pr.moved(lying_y(inner, width + 2.0 * BOOLEAN_OVERLAP), (0.0, 0.0, centre)),
)
mouth = pr.moved(pr.box(gap, width + 2.0 * BOOLEAN_OVERLAP, outer), (0.0, 0.0, centre))
body = pr.union(pr.box(outer, width, base), pr.subtract(ring, mouth))
info = pr.expect_solid("cable_clip exakt", body)
pr.check(
    "cable_clip: Öffnung oben = Ø minus 2·Verengung",
    not pr.inside(body, (0.0, 0.0, centre + inner / 2.0 + wall / 2.0))
    and pr.inside(body, (gap / 2.0 + 0.05, 0.0, centre + inner / 2.0 + wall / 2.0)),
)
# Die Bügelwand: vom Ringzentrum in +X ist bis inner/2 Luft, dann genau ``wall`` Material.
pr.check(
    "cable_clip: Bügelwand seitlich genau wall (exakt, keine Facettenkorrektur)",
    not pr.inside(body, (inner / 2.0 - 0.01, 0.0, centre))
    and pr.inside(body, (inner / 2.0 + 0.01, 0.0, centre))
    and pr.inside(body, (outer / 2.0 - 0.01, 0.0, centre))
    and not pr.inside(body, (outer / 2.0 + 0.01, 0.0, centre)),
)
pr.close(
    "cable_clip: exakte Außenbreite = inner + 2 wall",
    info["bounds"][3] - info["bounds"][0],
    outer,
    1e-9,
)
mesh_outer = mi["bounds"][3] - mi["bounds"][0]
pr.out(f"  Netz-Außenbreite {mesh_outer:.6f} (Facettenkorrektur), exakt {outer:.6f}")
pr.check(
    "cable_clip: Netz um die Facettenkorrektur breiter (erlaubter Unterschied)",
    0.0 < (mi["bounds"][3] - mi["bounds"][0]) - outer < 0.02,
)
pr.check("cable_clip: Kabelauflage bei z=wall frei", not pr.inside(body, (0.0, 0.0, base + 0.5)))
pr.step_roundtrip("cable_clip", body)

# --- cable_gland (host_add + Werkzeug) -----------------------------------------------------

pr.out()
pr.out("== cable_gland (cable-5, Wand 3, Zugentlastung, Spiel 0,2) ==")
spec, produced = build_mesh(
    "cable_gland",
    size="cable-5",
    diameter=0.0,
    wall=3.0,
    play=0.2,
    strain_relief=True,
    relief_gap=0.0,
)
mi = pr.mesh_report("cable_gland Werkzeug", produced.mesh)
wall = 3.0
d = entry.outer + 0.2
gap = entry.outer * 0.8
through = pr.moved(
    pr.cylinder(d, wall + 2.0 * BOOLEAN_OVERLAP), (0.0, 0.0, -wall - BOOLEAN_OVERLAP)
)
channel = pr.moved(pr.box(gap, d * 2.5, d), (0.0, 0.0, -wall - d))
tool = pr.union(through, channel)
info = pr.expect_solid("cable_gland Werkzeug exakt", tool)
pr.check(
    "cable_gland: Loch geht durch die Wand (z -wall..0)",
    pr.inside(tool, (0.0, 0.0, -wall / 2.0)) and info["bounds"][5] >= BOOLEAN_OVERLAP - 1e-9,
)
pr.close(
    "cable_gland: Klemmspalt = 0,8·Ø",
    2 * pr.radial_extent(tool, -wall - d / 2.0, (1.0, 0.0)),
    gap,
    1e-6,
)
pr.ratio("cable_gland Werkzeug: Netz/exakt (Loch facettiert)", mi["volume"], info["volume"], 0.004)
host_add = spec.host_add(
    spec.params(
        size="cable-5", diameter=0.0, wall=3.0, play=0.2, strain_relief=True, relief_gap=0.0
    )
)
assert host_add is not None
ha = pr.mesh_report("cable_gland host_add", host_add.mesh)
support = pr.moved(
    pr.box(d + 2.0 * wall, d * 2.5 + 2.0 * wall, d + BOOLEAN_OVERLAP), (0.0, 0.0, -wall - d)
)
si = pr.expect_solid("cable_gland host_add exakt", support)
pr.close("cable_gland host_add: Netz = exakt (Quader)", ha["volume"], si["volume"], 1e-9)
# Der Weg der Operation: Träger + host_add, dann minus Werkzeug — exakt am Träger nachgestellt.
host = pr.moved(pr.box(40.0, 40.0, wall), (0.0, 0.0, -wall))
with pr.Timed("cable_gland: Träger + Aufbau - Werkzeug"):
    joined = pr.union(host, support)
    cut = pr.subtract(joined, tool)
ci = pr.expect_solid("cable_gland am Träger exakt", cut)
# Analytik: Der Durchgangszylinder ragt um die Überlappung unter die Platte, wo er
# außerhalb des Kanalrechtecks (gap breit) noch Material des Aufbaus nimmt.
r = d / 2.0
half = gap / 2.0
rect_in_circle = 2.0 * (half * math.sqrt(r * r - half * half) + r * r * math.asin(half / r))
expected = (
    40 * 40 * wall
    + (d + 2 * wall) * (d * 2.5 + 2 * wall) * d
    - math.pi * r**2 * wall
    - gap * d * 2.5 * d
    - BOOLEAN_OVERLAP * (math.pi * r**2 - rect_in_circle)
)
pr.close("cable_gland am Träger: Volumen gegen Analytik", ci["volume"], expected, 1e-6)
pr.check(
    "cable_gland am Träger: Kabelweg frei (Loch und Klemmspalt)",
    not pr.inside(cut, (0.0, 0.0, -wall / 2.0))
    and not pr.inside(cut, (0.0, 0.0, -wall - d / 2.0))
    and pr.inside(cut, (gap / 2.0 + 0.2, 0.0, -wall - d / 2.0)),
)
pr.step_roundtrip("cable_gland am Träger", cut)

# --- gusset / rib ------------------------------------------------------------------------

pr.out()
pr.out("== gusset (Schenkel 12, Dicke 0 -> aus Wand 2) und rib (20 x 10, Wand 2, Anlauf 2) ==")
spec, produced = build_mesh("gusset", legs=12.0, thickness=0.0, wall=2.0)
mi = pr.mesh_report("gusset", produced.mesh)
thickness = max(2.0 * RIB_SHARE, min(2.0, MIN_RIB))
body = pr.wedge(thickness, 12.0, 12.0, 0.0)
info = pr.expect_solid("gusset exakt", body)
pr.close("gusset: Volumen = t·l²/2", info["volume"], thickness * 144.0 / 2.0, 1e-9)
pr.close("gusset: Netz = exakt", mi["volume"], info["volume"], 1e-9)
same_bounds("gusset: Bounds Netz = exakt", mi, info)

spec, produced = build_mesh("rib", length=20.0, height=10.0, wall=2.0, thickness=0.0, fillet=2.0)
mi = pr.mesh_report("rib", produced.mesh)
body = pr.box(thickness, 20.0, 10.0)
ramp = pr.wedge(thickness, 2.0, 2.0, 0.0)
body = pr.union(
    body, pr.moved(ramp, (0.0, 10.0, 0.0)), pr.moved(pr.turned(ramp, 180.0), (0.0, -10.0, 0.0))
)
info = pr.expect_solid("rib exakt", body)
pr.close(
    "rib: Volumen = Rippe + 2 Ausläufe", info["volume"], thickness * (20.0 * 10.0 + 2.0 * 2.0), 1e-9
)
pr.close("rib: Netz = exakt", mi["volume"], info["volume"], 1e-9)
same_bounds("rib: Bounds Netz = exakt", mi, info)
pr.step_roundtrip("rib", body)

# --- profile_tongue ------------------------------------------------------------------------

pr.out()
pr.out("== profile_tongue (2020, Länge 20, Schräge 1,5, Spiel 0,2) ==")
slot_entry = standards.profile_slot("2020")
play = 0.2
spec, produced = build_mesh(
    "profile_tongue", size="2020", length=20.0, lead_in=1.5, play=play, head=0.0
)
mi = pr.mesh_report("profile_tongue", produced.mesh)
neck_w = slot_entry.slot - play
head_w = slot_entry.core - play
neck_h = slot_entry.lip + play
head_h = slot_entry.depth - 2.0 * play
lead = min(1.5, 20.0 / 3.0)
neck = pr.box(neck_w, 20.0, neck_h + BOOLEAN_OVERLAP)
head = pr.tapered_bar(head_w, neck_w, 20.0, head_h, lead)
body = pr.union(neck, pr.moved(head, (0.0, 0.0, neck_h)))
info = pr.expect_solid("profile_tongue exakt", body)
pr.close(
    "profile_tongue: Hals = Nutbreite - Spiel",
    2 * pr.radial_extent(body, neck_h / 2.0, (1.0, 0.0)),
    neck_w,
    1e-6,
)
pr.close(
    "profile_tongue: Kopf = Kern - Spiel",
    2 * pr.radial_extent(body, neck_h + head_h / 2.0, (1.0, 0.0)),
    head_w,
    1e-6,
)
pr.check(
    "profile_tongue: Enden laufen auf Halsbreite zu",
    abs(pr.radial_extent(body, neck_h + head_h / 2.0, (1.0, 0.0)) - head_w / 2.0) < 1e-6
    and not pr.inside(body, (head_w / 2.0 - 0.05, 10.0 - 0.05, neck_h + head_h / 2.0)),
)
pr.close("profile_tongue: Netz = exakt", mi["volume"], info["volume"], 1e-6)
same_bounds("profile_tongue: Bounds Netz = exakt", mi, info)
pr.step_roundtrip("profile_tongue", body)

# --- organizer ---------------------------------------------------------------------------------

pr.out()
pr.out("== organizer_tray / _divider / _rim / _foot ==")
spec, produced = build_mesh(
    "organizer_tray", width=120.0, depth=80.0, height=40.0, wall=3.0, floor=3.0, radius=8.0
)
mi = pr.mesh_report("organizer_tray", produced.mesh)
with pr.Timed("organizer_tray exakt"):
    base = pr.rounded_prism(120.0, 80.0, 40.0, 8.0)
    cavity = pr.rounded_prism(114.0, 74.0, 37.0 + BOOLEAN_OVERLAP, 5.0)
    body = pr.subtract(base, pr.moved(cavity, (0.0, 0.0, 3.0)))
info = pr.expect_solid("organizer_tray exakt", body)
outer_area = 120 * 80 - (4 - math.pi) * 64
inner_area = 114 * 74 - (4 - math.pi) * 25
pr.close(
    "organizer_tray: Volumen gegen Analytik",
    info["volume"],
    outer_area * 40 - inner_area * 37,
    1e-6,
)
pr.check(
    "organizer_tray: acht Zylinderflächen (Ecken außen und innen)",
    info["types"].get("cylinder") == 8,
    str(info["types"]),
)
pr.check(
    "organizer_tray: Außenmaße exakt",
    abs(info["bounds"][3] - 60.0) < 1e-9 and abs(info["bounds"][4] - 40.0) < 1e-9,
    str(info["bounds"]),
)
pr.out(f"  Netz/exakt = {mi['volume'] / info['volume']:.6f} (Ecken nach MAX_FACET_SAG facettiert)")
pr.ratio("organizer_tray: Netz/exakt (Ecken facettiert)", mi["volume"], info["volume"], 0.001)
pr.step_roundtrip("organizer_tray", body)

spec, produced = build_mesh("organizer_divider", length=80.0, height=30.0, thickness=3.0)
mi = pr.mesh_report("organizer_divider", produced.mesh)
body = pr.box(80.0, 3.0, 30.0)
info = pr.expect_solid("organizer_divider exakt", body)
pr.close("organizer_divider: Netz = exakt", mi["volume"], info["volume"], 1e-9)
same_bounds("organizer_divider: Bounds Netz = exakt", mi, info)

spec, produced = build_mesh(
    "organizer_rim", width=120.0, depth=80.0, height=3.0, thickness=3.0, radius=8.0
)
mi = pr.mesh_report("organizer_rim", produced.mesh)
base = pr.rounded_prism(120.0, 80.0, 3.0, 8.0)
cut = pr.rounded_prism(114.0, 74.0, 3.0 + 2 * BOOLEAN_OVERLAP, 5.0)
body = pr.moved(
    pr.subtract(base, pr.moved(cut, (0.0, 0.0, -BOOLEAN_OVERLAP))), (0.0, -(80.0 - 3.0) / 2.0, 0.0)
)
info = pr.expect_solid("organizer_rim exakt", body)
pr.close(
    "organizer_rim: Volumen gegen Analytik", info["volume"], (outer_area - inner_area) * 3.0, 1e-6
)
pr.ratio("organizer_rim: Netz/exakt (Ecken facettiert)", mi["volume"], info["volume"], 0.002)
same_bounds("organizer_rim: Bounds Netz = exakt (Ecken tangieren Achsen)", mi, info, tol=1e-6)

spec, produced = build_mesh(
    "organizer_foot", diameter=18.0, height=11.0, pin_diameter=13.0, pin_length=8.0
)
mi = pr.mesh_report("organizer_foot", produced.mesh)
body = pr.union(pr.cylinder(18.0, 11.0), pr.moved(pr.cylinder(13.0, 8.0), (0.0, 0.0, 11.0)))
info = pr.expect_solid("organizer_foot exakt", body)
pr.close("organizer_foot: Volumen", info["volume"], math.pi * 81 * 11 + math.pi * 42.25 * 8, 1e-6)
pr.close("organizer_foot: Zapfen-Ø", 2 * pr.radial_extent(body, 15.0), 13.0, 1e-6)
pr.ratio("organizer_foot: Netz/exakt = Facettierung", mi["volume"], info["volume"], 0.004)
pr.close(
    "organizer_foot: Facettierungsverhältnis genau", mi["volume"] / info["volume"], FACET, 1e-6
)

# --- seal_groove / seal_gasket -----------------------------------------------------------------

pr.out()
pr.out("== seal_groove (Rechteckweg 20 x 12, Nut 3 x 2) ==")
path_text = sketch_to_text(sketch_shapes.rectangle(20.0, 12.0))
path_profile = profile_of(solve_sketch(sketch_from_text(path_text)))
spec, produced = build_mesh("seal_groove", path_sketch=path_text, offset=0.0, width=3.0, depth=2.0)
mi = pr.mesh_report("seal_groove", produced.mesh)
with pr.Timed("seal_groove Band exakt"):
    tool = pr.band(path_profile, 3.0, 2.0, -2.0)
info = pr.expect_solid("seal_groove exakt", tool)
pr.check(
    "seal_groove: unter der Mündung",
    abs(info["bounds"][5]) < 1e-9 and abs(info["bounds"][2] + 2.0) < 1e-9,
    str(info["bounds"]),
)
pr.check(
    "seal_groove: Ecken außen sind Kreisbögen (Zylinderflächen)",
    info["types"].get("cylinder") == 4,
    str(info["types"]),
)
# Analytik: Band der Breite w um ein Rechteck a x b, außen gerundet, innen scharf:
# außen (a+w)(b+w) - (4-pi)(w/2)^2, innen (a-w)(b-w); Ring = außen - innen.
a, b, w, h = 20.0, 12.0, 3.0, 2.0
ring_area = ((a + w) * (b + w) - (4 - math.pi) * (w / 2) ** 2) - (a - w) * (b - w)
pr.close(
    "seal_groove: Volumen gegen Analytik (außen gerundet, innen scharf)",
    info["volume"],
    ring_area * h,
    1e-6,
)
pr.check(
    "seal_groove: Nutbreite 3 symmetrisch um die Wegmitte (X-Schenkel bei x = 10)",
    pr.inside(tool, (10.0 - 1.5 + 0.01, 0.0, -1.0))
    and not pr.inside(tool, (10.0 - 1.5 - 0.01, 0.0, -1.0))
    and pr.inside(tool, (10.0 + 1.5 - 0.01, 0.0, -1.0))
    and not pr.inside(tool, (10.0 + 1.5 + 0.01, 0.0, -1.0)),
)
pr.ratio("seal_groove: Netz/exakt (Ecken facettiert)", mi["volume"], info["volume"], 0.002)
pr.step_roundtrip("seal_groove", tool)

pr.out()
pr.out("== seal_gasket rechteckig (Weg 20 x 12, 2,6 x 2,4) und rund (Ø 2,4) ==")
spec, produced = build_mesh(
    "seal_gasket", path_sketch=path_text, offset=0.0, section="rectangle", width=2.6, height=2.4
)
mi = pr.mesh_report("seal_gasket rect", produced.mesh)
gasket = pr.band(path_profile, 2.6, 2.4, 0.0)
info = pr.expect_solid("seal_gasket rect exakt", gasket)
pr.check(
    "seal_gasket rect: steht auf der Fläche (0..2,4)",
    abs(info["bounds"][2]) < 1e-9 and abs(info["bounds"][5] - 2.4) < 1e-9,
    str(info["bounds"]),
)
pr.ratio("seal_gasket rect: Netz/exakt (Ecken facettiert)", mi["volume"], info["volume"], 0.002)
pr.step_roundtrip("seal_gasket rect", gasket)

spec, produced = build_mesh(
    "seal_gasket", path_sketch=path_text, offset=0.0, section="round", width=2.6, height=2.4
)
mi = pr.mesh_report("seal_gasket round", produced.mesh)
with pr.Timed("seal_gasket rund: Kugel-Sweep exakt (4 Zylinder + 4 Kugeln)"):
    cord = pr.capsule_chain([(-10.0, -6.0), (10.0, -6.0), (10.0, 6.0), (-10.0, 6.0)], 1.2, 1.2)
info = pr.expect_solid("seal_gasket round exakt", cord)
pr.check(
    "seal_gasket round: Zylinder- und Kugelflächen",
    info["types"].get("cylinder", 0) >= 4 and info["types"].get("sphere", 0) >= 4,
    str(info["types"]),
)
# Analytik: je Seite ein Zylinder (Umfang·pi·r²); an jeder 90°-Ecke überlappen zwei
# Zylinder in einem Viertel-Steinmetz-Körper (4/3·r³), und die Kugel ergänzt dort
# eine Viertelkugel (pi/3·r³) außerhalb beider Zylinder.
r = 1.2
expected = 64.0 * math.pi * r**2 - 4.0 * (4.0 / 3.0) * r**3 + 4.0 * (math.pi / 3.0) * r**3
pr.close("seal_gasket round: Volumen gegen Analytik", info["volume"], expected, 1e-6)
pr.check(
    "seal_gasket round: Schnur 0..2,4 hoch",
    abs(info["bounds"][2]) < 1e-9 and abs(info["bounds"][5] - 2.4) < 1e-9,
    str(info["bounds"]),
)
pr.out(f"  Netz/exakt = {mi['volume'] / info['volume']:.6f} (Kugeln und Kapseln facettiert)")
pr.ratio("seal_gasket round: Netz/exakt (Facettierung)", mi["volume"], info["volume"], 0.01)
pr.step_roundtrip("seal_gasket round", cord)

pr.out()
pr.out("== seal_gasket rund auf Kreisweg Ø 20 -> exakter Torus ==")
circle_text = sketch_to_text(sketch_shapes.circle(20.0))
spec, produced = build_mesh(
    "seal_gasket", path_sketch=circle_text, offset=0.0, section="round", width=2.6, height=2.4
)
mi = pr.mesh_report("seal_gasket round circle", produced.mesh)
ring = pr.torus(10.0, 1.2, 1.2)
info = pr.expect_solid("seal_gasket torus exakt", ring)
pr.check("seal_gasket torus: eine Torusfläche", info["types"].get("torus") == 1, str(info["types"]))
pr.close("seal_gasket torus: Volumen 2π²Rr²", info["volume"], 2 * math.pi**2 * 10.0 * 1.2**2, 1e-6)
# Das Netz facettiert zweimal: die Kreisbahn nach _SEAL_SAG und jede Kugel nach
# Winkel/Sag. Ob 1,2 % Volumen Facettierung sind, sagt der Abstand der Netzpunkte
# zur exakten Fläche — er muss unter der Summe beider Sags bleiben.
worst = pr.mesh_distance(produced.mesh, ring, samples=600)
pr.out(f"  größter Abstand abgetasteter Netzpunkte zum exakten Torus: {worst:.5f}")
pr.check(
    "seal_gasket torus: Netzabstand ≤ Bahn-Sag + Kugel-Sag (Facettierung)",
    worst <= 0.05 / 8 + 0.05 + 1e-6,
)
pr.ratio(
    "seal_gasket torus: Netz/exakt (zweifache Facettierung)", mi["volume"], info["volume"], 0.02
)
pr.step_roundtrip("seal_gasket torus", ring)

pr.finish("S6 Struktur und Kabel")
