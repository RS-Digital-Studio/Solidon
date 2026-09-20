"""S3: Gruppe Verbindungen — sechs Bausteine, Netzweg gegen exakten Weg.

Je Baustein wird dieselbe Konstruktion einmal über ``spec.fn`` (heutiger
Netzweg) und einmal über die vorhandene B-Rep-API gebaut, mit denselben
Normteilmaßen aus ``standards``. Geprüft werden native Gültigkeit, Körperzahl,
die **Funktionsmaße in Richtung** (Bohrung unter der Mündung, Senkung an der
Mündung, Kopfzone über der Senkung, Gewindekern gegen Gangspitze) und das
Volumen gegen eine unabhängige Rechnung. Der Vergleich mit dem Netz weist
den Facettierungsanteil (48-Eck gegen Kreis) getrennt aus.

Gewinde: das Außengewinde kommt aus ``profiles.threaded_rod`` (vorhanden),
das Innengewinde als Differenz mit dem um das Spiel weiteren Bolzen. Der
Gangquerschnitt des exakten Kerns ist ein anderer als der des Netzgewindes —
das ist ein Formunterschied, kein Facettierungsunterschied, und wird als
solcher gemessen.
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
from app.core.knowledge.parts.fasteners import INSERT_LEAD_IN  # noqa: E402
from app.core.knowledge.parts.registry import PARTS  # noqa: E402

FACET = pr.polygon_ratio(shapes.SEGMENTS)
pr.out(f"Facettierungsverhältnis 48-Eck/Kreis: {FACET:.6f}")


def build_mesh(name: str, **values: object):  # type: ignore[no-untyped-def]
    spec = PARTS.get(name)
    params = spec.params(**values)
    return spec, spec.fn(params)


# --- screw_hole ---------------------------------------------------------------------

pr.out()
pr.out("== screw_hole (M4, Tiefe 10, Senkung, Kopftiefe 2) ==")
screw = standards.screw("M4")
depth, head_room = 10.0, 2.0
spec, produced = build_mesh(
    "screw_hole", size="M4", depth=depth, countersink=True, head_room=head_room
)
mesh_info = pr.mesh_report("screw_hole", produced.mesh)

top = -head_room
sink_depth = (screw.countersink - screw.clearance) / 2.0
shaft = pr.moved(pr.cylinder(screw.clearance, depth + BOOLEAN_OVERLAP), (0.0, 0.0, -depth))
sink = pr.moved(
    pr.cone(screw.clearance, screw.countersink, sink_depth), (0.0, 0.0, top - sink_depth)
)
room = pr.moved(pr.cylinder(screw.countersink, head_room + BOOLEAN_OVERLAP), (0.0, 0.0, top))
tool = pr.union(shaft, sink, room)
info = pr.expect_solid("screw_hole exakt", tool)
pr.check("screw_hole: Kegelfläche vorhanden", info["types"].get("cone") == 1, str(info["types"]))
r_c, r_cs = screw.clearance / 2.0, screw.countersink / 2.0
cone_volume = math.pi * sink_depth / 3.0 * (r_c**2 + r_c * r_cs + r_cs**2)
expected = (
    math.pi * r_c**2 * (depth + BOOLEAN_OVERLAP)
    + (cone_volume - math.pi * r_c**2 * sink_depth)
    + (math.pi * r_cs**2 - math.pi * r_c**2) * (head_room + BOOLEAN_OVERLAP)
)
pr.close("screw_hole: Volumen gegen Analytik", info["volume"], expected, 1e-6)
pr.check(
    "screw_hole: Werkzeug liegt unter der Mündung",
    info["bounds"][5] <= BOOLEAN_OVERLAP + 1e-9 and info["bounds"][2] < -depth + 1e-9,
    str(info["bounds"]),
)
pr.close("screw_hole: Bohrung Ø bei z=-8", 2 * pr.radial_extent(tool, -8.0), screw.clearance, 1e-6)
pr.close(
    "screw_hole: Kopfzone Ø bei z=-1", 2 * pr.radial_extent(tool, -1.0), screw.countersink, 1e-6
)
pr.close(
    "screw_hole: Senkung Ø in halber Senktiefe",
    2 * pr.radial_extent(tool, top - sink_depth / 2),
    (screw.clearance + screw.countersink) / 2,
    1e-6,
)
pr.ratio(
    "screw_hole: Netz/exakt Volumen = Facettierung", mesh_info["volume"], info["volume"], 0.004
)
pr.check(
    "screw_hole: Netzbounds == exakte Bounds (Umkreis)",
    all(abs(a - b) < 1e-6 for a, b in zip(mesh_info["bounds"], info["bounds"], strict=True)),
    f"{mesh_info['bounds']} / {info['bounds']}",
)
pr.step_roundtrip("screw_hole", tool)

# --- heatset_m4 --------------------------------------------------------------------

pr.out()
pr.out("== heatset_m4 (M4, Einführfase, Zusatztiefe 0,5) ==")
entry = standards.insert("M4")
spec, produced = build_mesh("heatset_m4", size="M4", lead_in=True, extra_depth=0.5)
mesh_info = pr.mesh_report("heatset", produced.mesh)
d = entry.length + 0.5
shaft = pr.moved(pr.cylinder(entry.hole, d + BOOLEAN_OVERLAP), (0.0, 0.0, -d))
lead = pr.moved(
    pr.cone(entry.hole, entry.hole + 2 * INSERT_LEAD_IN, INSERT_LEAD_IN),
    (0.0, 0.0, -INSERT_LEAD_IN),
)
tool = pr.union(shaft, lead)
info = pr.expect_solid("heatset exakt", tool)
pr.close("heatset: Bohrung Ø unten", 2 * pr.radial_extent(tool, -d + 0.1), entry.hole, 1e-6)
pr.close(
    "heatset: Fase weitet an der Mündung",
    2 * pr.radial_extent(tool, -1e-4),
    entry.hole + 2 * INSERT_LEAD_IN - 4e-4,
    1e-3,
)
pr.check(
    "heatset: Werkzeug unter der Mündung",
    info["bounds"][5] <= BOOLEAN_OVERLAP + 1e-9,
    str(info["bounds"]),
)
pr.ratio("heatset: Netz/exakt Volumen = Facettierung", mesh_info["volume"], info["volume"], 0.004)
pr.step_roundtrip("heatset", tool)

# --- nut_trap ----------------------------------------------------------------------

pr.out()
pr.out("== nut_trap (M4, seitlich, Einschub 12, Schraubenloch) ==")
nut = standards.nut("M4")
play = 0.2
spec, produced = build_mesh(
    "nut_trap", size="M4", direction="side", slide=12.0, play=play, screw_hole=True
)
mesh_info = pr.mesh_report("nut_trap", produced.mesh)
width, height = nut.width + play, nut.height + play / 2
pocket = pr.hexagon(width, height)
channel = pr.moved(pr.box(width, 12.0, height), (0.0, 6.0, 0.0))
bolt = pr.moved(pr.cylinder(screw.clearance, height + 20.0), (0.0, 0.0, -10.0))
tool = pr.union(pocket, channel, bolt)
info = pr.expect_solid("nut_trap exakt", tool)
hex_area = math.sqrt(3) / 2 * width**2
pr.close(
    "nut_trap: Schlüsselweite über X (die Ecken liegen in Y)",
    2 * pr.radial_extent(tool, height / 2, (1.0, 0.0)),
    width,
    1e-6,
)
pr.close(
    "nut_trap: Umkreis über Y",
    2 * pr.radial_extent(tool, height / 2, (0.0, -1.0)),
    2 * width / math.sqrt(3.0),
    1e-6,
)
pr.check(
    "nut_trap: Sechskant sitzt als Prisma (Ebenen ≥ 8)",
    info["types"].get("plane", 0) >= 8,
    str(info["types"]),
)
pr.check(
    "nut_trap: Netz ist dieselbe Form (Bounds)",
    all(abs(a - b) < 1e-6 for a, b in zip(mesh_info["bounds"], info["bounds"], strict=True)),
    f"{mesh_info['bounds']} / {info['bounds']}",
)
pr.ratio(
    "nut_trap: Netz/exakt Volumen (nur Schraubenloch facettiert)",
    mesh_info["volume"],
    info["volume"],
    0.003,
)
bottom = pr.turned(tool, 90.0, (1.0, 0.0, 0.0))
spec, produced_b = build_mesh(
    "nut_trap", size="M4", direction="bottom", slide=12.0, play=play, screw_hole=True
)
bi = pr.expect_solid("nut_trap bottom exakt", bottom)
mb = pr.mesh_report("nut_trap bottom", produced_b.mesh)
pr.check(
    "nut_trap bottom: Öffnung zeigt nach unten (Netz wie exakt)",
    all(abs(a - b) < 1e-6 for a, b in zip(mb["bounds"], bi["bounds"], strict=True)),
    f"{mb['bounds']} / {bi['bounds']}",
)
pr.step_roundtrip("nut_trap", tool)

# --- printed_thread außen -----------------------------------------------------------

pr.out()
pr.out("== printed_thread außen (M6, Länge 12) ==")
m6 = standards.screw("M6")
spec, produced = build_mesh("printed_thread", size="M6", length=12.0, internal=False, play=0.0)
mesh_info = pr.mesh_report("printed_thread außen", produced.mesh)
with pr.Timed("threaded_rod M6 x 12"):
    rod = profiles.threaded_rod(m6.nominal, m6.pitch, 12.0)
info = pr.expect_solid("threaded_rod exakt", rod)
pr.check(
    "thread außen: Länge exakt 12",
    abs(info["bounds"][5] - 12.0) < 1e-6 and abs(info["bounds"][2]) < 1e-6,
    str(info["bounds"]),
)
core_exact, crest_exact = pr.radial_minmax(rod, 6.0)
mesh_core = m6.nominal - 2 * m6.pitch * shapes.RIDGE_SHARE
pr.out(
    f"  exakt bei z=6 über den Umfang: Kern Ø {2 * core_exact:.5f}, Gang Ø {2 * crest_exact:.5f}"
    f" (Netz: Kern Ø {mesh_core:.4f}, Gang Ø {m6.nominal:.4f})"
)
pr.close(
    "thread außen: Gang-Ø = Nenn-Ø (Sweep-Approximation ≤ 1e-4)", 2 * crest_exact, m6.nominal, 1e-4
)
pr.check(
    "thread außen: exakter Kern unter dem Netzkern (Gangprofil 0,6134 p statt 0,55 p)",
    2 * core_exact < mesh_core - 0.05,
)
q = mesh_info["volume"] / info["volume"]
pr.out(f"  Volumen Netz/exakt = {q:.4f} — Formunterschied des Gangprofils, keine Facettierung")
pr.check(
    "thread außen: Volumenunterschied ist ein Formunterschied (> Facettierung)", abs(q - 1.0) > 0.01
)
pr.step_roundtrip("threaded_rod", rod, faces=False)

pr.out()
pr.out("== Prototyp: Gangprofil des Netzwegs (0,55 p, flacher Kamm) als exakter Sweep ==")
with pr.Timed("thread_ridge_exact M6 x 12"):
    same_profile = pr.thread_ridge_exact(m6.nominal, m6.pitch, 12.0)
si = pr.expect_solid("Netzprofil exakt", same_profile)
core_s, crest_s = pr.radial_minmax(same_profile, 6.0)
pr.out(f"  exakt (Netzprofil) bei z=6: Kern Ø {2 * core_s:.5f}, Gang Ø {2 * crest_s:.5f}")
pr.close(
    "Netzprofil exakt: Kern-Ø wie im Netz (+ 2·Überlappung)", 2 * core_s, mesh_core + 0.02, 1e-3
)
pr.close("Netzprofil exakt: Gang-Ø wie im Netz", 2 * crest_s, m6.nominal, 1e-3)
# Kern (48-Eck) und Gang (Vierpunkt-Ringe je Segment) sind beide facettiert.
pr.ratio(
    "Netzprofil exakt: Volumen Netz/exakt = Facettierung von Kern und Gang",
    mesh_info["volume"],
    si["volume"],
    0.012,
)
# BSpline-Sweepflächen kommen aus STEP um ~1e-5 relativ anders zurück (threaded_rod: 1e-8).
back = pr.step.read(pr.step.write(same_profile, "Netzprofil"))
pr.check("Netzprofil exakt: STEP-Rundreise gültig", pr.is_valid(back))
pr.ratio(
    "Netzprofil exakt: STEP-Rundreise Volumen (Sweep-Approximation)",
    back.volume,
    si["volume"],
    1e-4,
)

# --- printed_thread innen ------------------------------------------------------------

pr.out()
pr.out("== printed_thread innen als Werkzeug (M6, Länge 8, Spiel 0,2) ==")
play = 0.2
spec, produced = build_mesh("printed_thread", size="M6", length=8.0, internal=True, play=play)
mesh_info = pr.mesh_report("printed_thread innen", produced.mesh)
tool = pr.moved(profiles.threaded_rod(m6.nominal + play, m6.pitch, 8.0), (0.0, 0.0, -8.0))
info = pr.expect_solid("thread innen exakt (Bolzen + Spiel unter der Mündung)", tool)
pr.check(
    "thread innen: Werkzeug unter der Mündung (Hüllenzuschlag der NURBS-Bounds ≤ 1e-5)",
    info["bounds"][5] <= 1e-5 and abs(info["bounds"][2] + 8.0) < 1e-6,
    str(info["bounds"]),
)
_core_i, crest_i = pr.radial_minmax(tool, -4.0)
pr.close("thread innen: Werkzeug-Gang-Ø = nominal + Spiel", 2 * crest_i, m6.nominal + play, 1e-4)
pr.check(
    "thread innen: Netzwerkzeug liegt ebenfalls unter der Mündung",
    mesh_info["bounds"][5] <= 1e-6,
    str(mesh_info["bounds"]),
)
block = pr.box(20.0, 20.0, 8.0)
with pr.Timed("Block minus Innengewinde"):
    nut_body = pr.subtract(pr.moved(block, (0.0, 0.0, -8.0)), tool)
ni = pr.expect_solid("Block minus Innengewinde", nut_body)
pr.check("Block minus Innengewinde: Volumen kleiner als Block", ni["volume"] < 3200.0 - 1.0)
core_left = (
    2 * pr.radial_extent_of_hole(nut_body, -4.0) if hasattr(pr, "radial_extent_of_hole") else None
)
pr.step_roundtrip("Block minus Innengewinde", nut_body, faces=False)

# --- printed_screw -------------------------------------------------------------------

pr.out()
pr.out("== printed_screw (M5, Länge 12, Sechskantkopf) ==")
m5 = standards.screw("M5")
spec, produced = build_mesh("printed_screw", size="M5", length=12.0, countersunk=False, play=0.0)
mesh_info = pr.mesh_report("printed_screw", produced.mesh)
head = pr.hexagon(m5.head, m5.head_height)
threaded = pr.moved(
    profiles.threaded_rod(m5.nominal, m5.pitch, 12.0), (0.0, 0.0, -12.0 + BOOLEAN_OVERLAP)
)
body = pr.union(head, threaded)
info = pr.expect_solid("printed_screw exakt", body)
pr.check(
    "printed_screw: Kopf oben, Gewinde unten",
    abs(info["bounds"][5] - m5.head_height) < 1e-6
    and abs(info["bounds"][2] + 12.0 - BOOLEAN_OVERLAP) < 1e-6,
    str(info["bounds"]),
)
pr.check(
    "printed_screw: Netz hat dieselbe Höhe",
    abs(mesh_info["bounds"][5] - info["bounds"][5]) < 1e-6
    and abs(mesh_info["bounds"][2] - info["bounds"][2]) < 1e-6,
    f"{mesh_info['bounds']} / {info['bounds']}",
)
pr.step_roundtrip("printed_screw", body, faces=False)

pr.out()
pr.out("== printed_screw (M5, Senkkopf) + host_cut ==")
spec, produced = build_mesh("printed_screw", size="M5", length=12.0, countersunk=True, play=0.0)
mesh_info = pr.mesh_report("printed_screw senk", produced.mesh)
head_height = (m5.countersink - m5.nominal) / 2.0
head = pr.moved(pr.cone(m5.nominal, m5.countersink, head_height), (0.0, 0.0, -head_height))
threaded = pr.moved(
    profiles.threaded_rod(m5.nominal, m5.pitch, 12.0),
    (0.0, 0.0, -head_height - 12.0 + BOOLEAN_OVERLAP),
)
body = pr.union(head, threaded)
info = pr.report("printed_screw senk exakt, Überlappung 0,01 wie im Netz", body)
pr.check(
    "BEFUND printed_screw senk: 0,01 mm Überlappung von Kegelkopf und Gewinde -> zwei Körper",
    info["solids"] == 2,
    f"solids={info['solids']} — der Netzweg verschmilzt dieselbe Lage zu einem",
)
# Der Weg, den ``threaded_rod`` selbst geht: Fuzzy-Vereinigung mit kleiner Toleranz.
from app.core.brep.kernel import Solid, boolean_builder  # noqa: E402

fuzzy = boolean_builder("union", head.shape, threaded.shape, tolerance=1e-4)
fuzzy.Build()
body = Solid(fuzzy.Shape())
info = pr.expect_solid("printed_screw senk exakt, Fuzzy-Vereinigung 1e-4", body)
pr.check(
    "printed_screw senk: breiter Rand bündig bei z=0, Gewinde 12 unter der Kopfspitze",
    abs(info["bounds"][5]) < 1e-6
    and abs(info["bounds"][2] + head_height + 12.0 - BOOLEAN_OVERLAP) < 1e-6,
    str(info["bounds"]),
)
pr.check(
    "printed_screw senk: Netz hat dieselbe Höhe",
    abs(mesh_info["bounds"][2] - info["bounds"][2]) < 1e-6,
)
# BEFUND (s3b): Die Fuzzy-Vereinigung ist hier gültig, kommt aber aus STEP ungültig
# zurück — bei jeder Stufe, auch nach ShapeFix. Der STEP-fähige Weg ist der Compound
# aus Kopf und Bolzen (zwei Solids, wie das lösbare Teil ohnehin neben dem Träger liegt).
fuzzy_back = pr.step.read(pr.step.write(body, "senkkopf"))
pr.out(f"  Beobachtung: Fuzzy-Senkkopf nach STEP-Rundreise valid={pr.is_valid(fuzzy_back)}")
from OCP.BRep import BRep_Builder  # noqa: E402
from OCP.TopoDS import TopoDS_Compound  # noqa: E402

compound = TopoDS_Compound()
builder = BRep_Builder()
builder.MakeCompound(compound)
builder.Add(compound, head.shape)
builder.Add(compound, threaded.shape)
pair = Solid(compound)
pi = pr.report("printed_screw senk als Compound (Kopf + Bolzen)", pair)
pr.check("printed_screw senk Compound: zwei Solids, gültig", pi["solids"] == 2 and pi["valid"])
pr.step_roundtrip("printed_screw senk Compound", pair, faces=False)
host_cut = spec.host_cut(spec.params(size="M5", length=12.0, countersunk=True, play=0.0))
assert host_cut is not None
hc = pr.mesh_report("host_cut Senkung", host_cut.mesh)
sink_depth = (m5.countersink - m5.clearance) / 2.0
cutter = pr.moved(pr.cone(m5.clearance, m5.countersink, sink_depth), (0.0, 0.0, -sink_depth))
ci = pr.expect_solid("host_cut exakt", cutter)
pr.check(
    "host_cut: Senkung unter der Mündung, weit oben",
    abs(ci["bounds"][5]) < 1e-6
    and abs(2 * pr.radial_extent(cutter, -1e-4) - m5.countersink) < 1e-3,
    str(ci["bounds"]),
)
pr.ratio("host_cut: Netz/exakt = Facettierung", hc["volume"], ci["volume"], 0.004)

# --- printed_nut ----------------------------------------------------------------------

pr.out()
pr.out("== printed_nut (M5, Spiel 0,2) ==")
nut5 = standards.nut("M5")
spec, produced = build_mesh("printed_nut", size="M5", play=0.2)
mesh_info = pr.mesh_report("printed_nut", produced.mesh)
hull = pr.hexagon(nut5.width, nut5.height)
cutter = pr.moved(
    profiles.threaded_rod(
        m5.nominal + 0.2, m5.pitch, nut5.height + 2 * BOOLEAN_OVERLAP + 2 * m5.pitch
    ),
    (0.0, 0.0, -BOOLEAN_OVERLAP - m5.pitch),
)
with pr.Timed("printed_nut: Sechskant minus Bolzen"):
    body = pr.subtract(hull, cutter)
info = pr.expect_solid("printed_nut exakt", body)
pr.check(
    "printed_nut: Höhe = Normhöhe",
    abs(info["bounds"][5] - nut5.height) < 1e-6 and abs(info["bounds"][2]) < 1e-6,
    str(info["bounds"]),
)
pr.check(
    "printed_nut: Gewinde geht durch (Achse frei)", not pr.inside(body, (0.0, 0.0, nut5.height / 2))
)
pr.step_roundtrip("printed_nut", body, faces=False)

pr.finish("S3 Verbindungen")
