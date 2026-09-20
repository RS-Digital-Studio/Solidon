"""S8: Der Einsetzweg am exakten Träger — heute, exakt, und die Gegenfälle.

Der Konvertierungspunkt liegt in ``parts/ops._insert_at``: ``as_mesh_data``
tesselliert den Träger, und das Ergebnis ist ein Netz. Diese Sonde stellt den
Weg mit dem vorhandenen Kern nach: dieselbe ``_anchor``/``_matrix``-Lage wie
im Netzweg, das exakte Werkzeug über ``edit.transformed`` platziert, dann
``edit.boolean``. Geprüft werden Bauart, Volumen gegen den Netzweg, die
Merkmale, die ``features_of`` am Ergebnis liest, die STEP-Rundreise — und
bewusste Gegenfälle: Berührung ohne Überlappung, Werkzeug gleich der
Bohrung, Werkzeug neben dem Körper, geneigte Fläche, mehrere Ziele, lösbares
Teil neben dem Träger. Zum Schluss der Kundenweg aus Konzept §5.1.
"""

from __future__ import annotations

import math

import _probe as pr

from app.core import bootstrap

bootstrap.load_operations()

from app.core.brep import edit  # noqa: E402
from app.core.brep.features import features_of  # noqa: E402
from app.core.brep.kernel import Solid  # noqa: E402
from app.core.geom.boolean import BOOLEAN_OVERLAP  # noqa: E402
from app.core.knowledge import standards  # noqa: E402
from app.core.knowledge.parts import ops as part_ops  # noqa: E402
from app.core.knowledge.parts.fasteners import INSERT_LEAD_IN  # noqa: E402
from app.core.knowledge.parts.registry import PARTS  # noqa: E402
from app.core.knowledge.profiles import make_profile  # noqa: E402
from app.core.registry import REGISTRY  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402

PROFILE = make_profile("centauri-carbon-2", "petg")


def fresh(*steps: tuple[str, dict[str, object]]):  # type: ignore[no-untyped-def]
    project = new_project("centauri-carbon-2", "petg")
    doc = project.document
    history = History(doc)
    history.apply(
        "Quader",
        [
            OperationDraft(
                op="create_brep_box", params={"width": 40.0, "depth": 30.0, "height": 10.0}
            )
        ],
    )
    history.apply(
        "Bohrung",
        [
            OperationDraft(
                op="drill_brep_hole", inputs=("obj_1",), params={"diameter": 5.0, "z": 10.0}
            )
        ],
    )
    for op, params in steps:
        history.apply(op, [OperationDraft(op=op, inputs=("obj_1",), params=params)])
    result = evaluate(doc, PROFILE, sources=ProjectSources(project))
    return project, doc, history, result


def first_feature(obj, kind: str) -> str:  # type: ignore[no-untyped-def]
    for feature in obj.features.values():
        if feature.kind == kind:
            return feature.id
    return ""


def kinds_of(features) -> dict[str, int]:  # type: ignore[no-untyped-def]
    found: dict[str, int] = {}
    for feature in features.values():
        found[feature.kind] = found.get(feature.kind, 0) + 1
    return dict(sorted(found.items()))


def heatset_tool_exact(size: str, extra_depth: float = 0.5) -> Solid:
    entry = standards.insert(size)
    d = entry.length + extra_depth
    shaft = pr.moved(pr.cylinder(entry.hole, d + BOOLEAN_OVERLAP), (0.0, 0.0, -d))
    lead = pr.moved(
        pr.cone(entry.hole, entry.hole + 2 * INSERT_LEAD_IN, INSERT_LEAD_IN),
        (0.0, 0.0, -INSERT_LEAD_IN),
    )
    return pr.union(shaft, lead)


def insert_exact(source, op_name: str, tool: Solid, **values: object):  # type: ignore[no-untyped-def]
    """Der Prototyp des exakten Einsetzwegs: dieselbe Lage wie ``_insert_at``, exakter Schnitt."""
    spec = PARTS.get(part_ops.part_of(op_name).name)
    params = REGISTRY.get(op_name).params(**values)
    built = spec.fn(spec.params(**part_ops._part_values(spec, params, PROFILE))).mesh
    anchor, direction = part_ops._anchor(source, params, spec, built)
    subtractive = part_ops.cuts(spec, params)
    sink = 0.0 if subtractive or spec.separate_from_host else BOOLEAN_OVERLAP
    flip = subtractive and part_ops._builds_upward_on_a_face(source, params, built)
    matrix = part_ops._matrix(params, anchor, sink, direction, spec.keeps_up, flip)
    placed = edit.transformed(tool, matrix)
    if spec.separate_from_host:
        return placed, "separate"
    kind = "difference" if subtractive else "union"
    return edit.boolean(kind, [source.mesh, placed]), kind


# --- 1. heute: der Konvertierungspunkt ----------------------------------------------------

pr.out("== 1. heute: insert_heatset_m4 am exakten Träger ==")
project, doc, history, result = fresh()
source = next(iter(result.scene.objects.values()))
hole = first_feature(source, "hole")
pr.check("Träger ist exakt", source.kind == "brep" and isinstance(source.mesh, Solid))
host_volume = source.mesh.volume
pr.out(f"  Träger: V={host_volume:.6f} Merkmale {kinds_of(source.features)}")
_, _, _, today = fresh(("insert_heatset_m4", {"at_feature": hole, "size": "M4"}))
today_obj = next(iter(today.scene.objects.values()))
pr.check(
    "heute: Ergebnis ist ein Netz (Konvertierungspunkt _insert_at/as_mesh_data)",
    today_obj.kind == "mesh",
)
codes = sorted({f.code for f in today.scene.report.findings})
pr.check(
    "heute: Befund evaluate.exact_became_mesh", "evaluate.exact_became_mesh" in codes, str(codes)
)
pr.out(f"  heute: V={today_obj.mesh.volume:.6f} Merkmale {kinds_of(today_obj.features)}")

# --- 2. exakt: derselbe Weg mit exaktem Werkzeug --------------------------------------------

pr.out()
pr.out("== 2. exakt: heatset M4 an der Bohrung ==")
with pr.Timed("exakter Schnitt"):
    cut, kind = insert_exact(
        source, "insert_heatset_m4", heatset_tool_exact("M4"), at_feature=hole, size="M4"
    )
info = pr.expect_solid("Träger minus Buchse", cut)
entry = standards.insert("M4")
host_hole = source.features[hole].params
host_d = float(host_hole["diameter"])
pr.out(
    f"  Trägerbohrung laut Merkmal: Ø{host_d} (materialkompensiert, bore.compensated), {host_hole}"
)
tool_depth = entry.length + 0.5
r_h, r_t, r_c = host_d / 2.0, entry.hole / 2.0, entry.hole / 2.0 + INSERT_LEAD_IN
cone_volume = math.pi * INSERT_LEAD_IN / 3.0 * (r_t**2 + r_t * r_c + r_c**2)
expected = host_volume - (
    math.pi * (r_t**2 - r_h**2) * tool_depth + (cone_volume - math.pi * r_t**2 * INSERT_LEAD_IN)
)
pr.close("exakt: Volumen gegen Analytik (Aufweitung + Fase)", info["volume"], expected, 1e-6)
pr.close(
    "exakt: Bohrung Ø unter der Mündung = Buchsenbohrung",
    pr.hole_diameter(cut, (0.0, 0.0), 8.0),
    entry.hole,
    1e-6,
)
pr.close(
    "exakt: Rest der Trägerbohrung darunter bleibt",
    pr.hole_diameter(cut, (0.0, 0.0), 0.5),
    host_d,
    1e-6,
)
pr.ratio(
    "Netz/exakt Volumen = Facettierung der Bohrungen", today_obj.mesh.volume, info["volume"], 0.001
)
found = features_of(cut)
pr.out(f"  features_of am exakten Ergebnis: {kinds_of(found)}")
holes = [f for f in found.values() if f.kind == "hole"]
pr.out(
    "  Bohrungen: "
    + ", ".join(f"Ø{f.params.get('diameter'):.4f} tief {f.params.get('depth'):.4f}" for f in holes)
)
pr.check(
    "exakt: features_of liest die aufgeweitete Bohrung Ø5,6",
    any(abs(f.params.get("diameter", 0) - entry.hole) < 1e-6 for f in holes),
)
pr.check(
    "exakt: features_of liest den Rest der Trägerbohrung",
    any(abs(f.params.get("diameter", 0) - host_d) < 1e-6 for f in holes),
)
pr.check(
    "exakt: Kegelfläche der Fase erkannt (cone/countersink)",
    any(f.kind in ("cone", "countersink") for f in found.values()) or "cone" in pr.face_types(cut),
    str(kinds_of(found)),
)
heat_spec = PARTS.get("heatset_m4")
heat_params = REGISTRY.get("insert_heatset_m4").params(at_feature=hole, size="M4")
heat_built = heat_spec.fn(heat_spec.params(size="M4"))
heat_anchor, heat_direction = part_ops._anchor(source, heat_params, heat_spec, heat_built.mesh)
placed_features = part_ops._placed_features(
    heat_built, heat_spec, heat_params, heat_anchor, 0.0, heat_direction, False, False
)
pr.out(f"  Provenienz-Merkmale über _placed_features: {sorted(placed_features)}")
pr.check(
    "Provenienz-Merkmale entstehen unabhängig von der Bauart (moved_features)",
    "heatset_m4_bore_1" in placed_features and "heatset_m4_chamfer_1" in placed_features,
)
bore_feature = placed_features["heatset_m4_bore_1"]
bore_centre = tuple(round(v, 4) for v in bore_feature.params["centre"])
pr.out(f"  heatset_m4_bore_1: centre={bore_centre} Ø{bore_feature.params['diameter']}")
matching = [f for f in holes if abs(f.params.get("diameter", 0) - entry.hole) < 1e-6]
if matching:
    native = matching[0]
    native_centre = tuple(float(v) for v in native.params["centre"])
    pr.check(
        "Provenienz-Bohrung und native Bohrung teilen die Achse (X, Y)",
        all(
            abs(a - b) < 1e-6
            for a, b in zip(native_centre[:2], bore_feature.params["centre"][:2], strict=True)
        ),
        f"nativ {tuple(round(v, 4) for v in native_centre)}",
    )
    # Beobachtung: Das Provenienz-Merkmal beschreibt das Werkzeug (Mitte der ganzen
    # Buchsentiefe), das native die Zylinderfläche ohne Fase — halbe Fasenhöhe Versatz.
    pr.close(
        "Provenienz-Mitte liegt um die halbe Fasenhöhe über der nativen Zylindermitte",
        bore_feature.params["centre"][2] - native_centre[2],
        INSERT_LEAD_IN / 2.0,
        1e-6,
    )
    pr.check(
        "native Bohrung trägt Dreiecke (face_indices) für die Auswahl", len(native.face_indices) > 0
    )
pr.step_roundtrip("Träger minus Buchse", cut)

# --- 3. Gegenfälle ----------------------------------------------------------------------------

pr.out()
pr.out("== 3a. aufgesetzt ohne Einsenken: Rippe berührt den Träger nur in einer Fläche ==")
face = first_feature(source, "face")
rib_spec = PARTS.get("rib")
rib_tool = pr.box(1.4, 20.0, 10.0)
rib_tool = pr.union(
    rib_tool,
    pr.moved(pr.wedge(1.4, 2.0, 2.0, 0.0), (0.0, 10.0, 0.0)),
    pr.moved(pr.turned(pr.wedge(1.4, 2.0, 2.0, 0.0), 180.0), (0.0, -10.0, 0.0)),
)
touching = pr.moved(rib_tool, (10.0, 0.0, 10.0))
try:
    fused = edit.boolean("union", [source.mesh, touching])
    fi = pr.report("Vereinigung bei reiner Flächenberührung", fused)
    pr.check(
        "3a: exakte Vereinigung bei Berührung ergibt einen Körper (Netz braucht OVERLAP)",
        fi["solids"] == 1 and fi["valid"],
        f"solids={fi['solids']}",
    )
    pr.close("3a: Volumen = Träger + Rippe", fi["volume"], host_volume + rib_tool.volume, 1e-6)
except Exception as error:
    pr.check(
        "3a: exakte Vereinigung bei Berührung", False, f"{type(error).__name__}: {error}"[:160]
    )
sunk = pr.moved(rib_tool, (10.0, 0.0, 10.0 - BOOLEAN_OVERLAP))
fused = edit.boolean("union", [source.mesh, sunk])
fi = pr.expect_solid("Vereinigung mit Einsenkung 0,01", fused)
pr.close(
    "3a: eingesenkt: Volumen = Träger + Rippe - Überlappung",
    fi["volume"],
    host_volume
    + rib_tool.volume
    - 1.4 * 20.0 * BOOLEAN_OVERLAP
    - 2 * 1.4 * 2.0 * BOOLEAN_OVERLAP
    + 2 * 1.4 * 0.5 * BOOLEAN_OVERLAP**2,
    1e-4,
)

pr.out()
pr.out("== 3b. Werkzeug genau so groß wie die Bohrung: Passbohrung Ø5 in Ø5 ==")
same = pr.moved(pr.cylinder(5.0, 8.0), (0.0, 0.0, 2.0))
try:
    no_effect = edit.boolean("difference", [source.mesh, same])
    ni = pr.report("Differenz mit koinzidenter Zylinderfläche", no_effect)
    pr.check(
        "3b: exakt gültig und ohne Wirkung (Volumen gleich)",
        ni["valid"] and abs(ni["volume"] - host_volume) < 1e-6,
        f"V {ni['volume']:.6f} gegen {host_volume:.6f}",
    )
except Exception as error:
    pr.check(
        "3b: Differenz mit koinzidenter Zylinderfläche",
        False,
        f"{type(error).__name__}: {error}"[:160],
    )

pr.out()
pr.out("== 3c. Werkzeug neben dem Körper ==")
beside = pr.moved(heatset_tool_exact("M4"), (60.0, 0.0, 10.0))
missed = edit.boolean("difference", [source.mesh, beside])
mi = pr.expect_solid("Differenz ohne Treffer", missed)
pr.close(
    "3c: Volumen unverändert -> without_effect greift wie im Netz", mi["volume"], host_volume, 1e-9
)

pr.out()
pr.out("== 3d. geneigte Fläche: Träger um 30° um X gedreht, Buchse an die Deckfläche ==")
_, _, _, tilted = fresh(("rotate_object", {"axis": "x", "angle": 30.0}))
tilted_obj = next(iter(tilted.scene.objects.values()))
pr.check("3d: gedrehter Träger bleibt exakt", tilted_obj.kind == "brep")
top_faces = [
    k
    for k, f in tilted_obj.features.items()
    if f.kind == "face" and f.params.get("normal", (0, 0, 0))[2] > 0.8
]
pr.check("3d: Deckfläche nach der Drehung erkannt (Normale ~ (0, -0,5, 0,87))", bool(top_faces))
if top_faces:
    target = top_faces[0]
    normal = tilted_obj.features[target].params["normal"]
    with pr.Timed("exakter Schnitt an geneigter Fläche"):
        cut_t, _ = insert_exact(
            tilted_obj,
            "insert_heatset_m4",
            heatset_tool_exact("M4"),
            at_feature=target,
            size="M4",
            x=10.0,
        )
    ti = pr.expect_solid("geneigt: Träger minus Buchse", cut_t)
    found_t = features_of(cut_t)
    new_holes = [
        f
        for f in found_t.values()
        if f.kind == "hole" and abs(f.params.get("diameter", 0) - entry.hole) < 1e-6
    ]
    pr.check("3d: aufgeweitete Bohrung Ø5,6 erkannt", bool(new_holes))
    if new_holes:
        axis = new_holes[0].params["axis"]
        dot = abs(sum(a * b for a, b in zip(axis, normal, strict=True)))
        pr.close("3d: Bohrungsachse folgt der Flächennormalen", dot, 1.0, 1e-6)
    pr.close(
        "3d: Volumenabtrag = volle Buchse + Fase (neben der Bohrung, x = 10 im Flächenrahmen)",
        tilted_obj.mesh.volume - ti["volume"],
        math.pi * r_t**2 * tool_depth + (cone_volume - math.pi * r_t**2 * INSERT_LEAD_IN),
        1e-6,
    )

pr.out()
pr.out("== 3e. zwei Ziele: zweite Bohrung, Buchse an beide ==")
_, _, _, two = fresh(("drill_brep_hole", {"diameter": 5.0, "x": 12.0, "z": 10.0}))
two_obj = next(iter(two.scene.objects.values()))
two_holes = [k for k, f in two_obj.features.items() if f.kind == "hole"]
pr.check("3e: zwei Bohrungen am exakten Träger", len(two_holes) == 2, str(two_holes))
# Wie ``_insert_at``: Die Merkmale des Trägers werden fortgeführt, nicht neu erkannt —
# ``features_of`` vergäbe nach dem ersten Schnitt neue Namen, und das zweite Ziel
# träfe die falsche Bohrung (gemessen: 38,6 statt 63,0 mm³ Abtrag).
import dataclasses  # noqa: E402

body = two_obj
for target in two_holes:
    cut_two, _ = insert_exact(
        body, "insert_heatset_m4", heatset_tool_exact("M4"), at_feature=target, size="M4"
    )
    body = dataclasses.replace(body, mesh=cut_two)
recognised = features_of(body.mesh)
bi = pr.expect_solid("beide Buchsen exakt", body.mesh)
pr.check(
    "3e: zwei Bohrungen Ø5,6 erkannt",
    sum(
        1
        for f in recognised.values()
        if f.kind == "hole" and abs(f.params.get("diameter", 0) - entry.hole) < 1e-6
    )
    == 2,
)
pr.close(
    "3e: doppelter Abtrag",
    two_obj.mesh.volume - bi["volume"],
    2 * (host_volume - info["volume"]),
    1e-6,
)

pr.out()
pr.out("== 3f. lösbares Teil: Schraube M5 neben dem Träger (separate_from_host) ==")
from app.core.brep import profiles  # noqa: E402

m5 = standards.screw("M5")
screw_tool = pr.union(
    pr.hexagon(m5.head, m5.head_height),
    pr.moved(
        profiles.threaded_rod(m5.nominal, m5.pitch, 12.0), (0.0, 0.0, -12.0 + BOOLEAN_OVERLAP)
    ),
)
placed_screw, kind = insert_exact(
    source,
    "insert_printed_screw",
    screw_tool,
    at_feature=hole,
    size="M5",
    length=12.0,
    countersunk=False,
)
pr.check("3f: Schraube wird nicht vereinigt (separate)", kind == "separate")
from OCP.BRep import BRep_Builder  # noqa: E402
from OCP.TopoDS import TopoDS_Compound  # noqa: E402

compound = TopoDS_Compound()
builder = BRep_Builder()
builder.MakeCompound(compound)
builder.Add(compound, source.mesh.shape)
builder.Add(compound, placed_screw.shape)
pair = Solid(compound)
pi = pr.report("Träger + Schraube als Compound", pair)
pr.check("3f: Compound trägt zwei Körper", pi["solids"] == 2)
pr.close("3f: Volumen = Träger + Schraube", pi["volume"], host_volume + screw_tool.volume, 1e-6)
pr.check(
    "3f: Schraubenkopf liegt an der Mündung (z = 10 .. 10 + Kopfhöhe)",
    abs(pi["bounds"][5] - (10.0 + m5.head_height)) < 1e-6,
    str(pi["bounds"]),
)
pr.step_roundtrip("Träger + Schraube", pair, faces=False)

# --- 4. Kundenweg §5.1 exakt ------------------------------------------------------------------

pr.out()
pr.out("== 4. Kundenweg §5.1: Quader, Bohrung, Verrunden R3, Aushöhlen 2, Buchse, Senkung ==")
_, _, _, way = fresh(("fillet_edges", {"radius": 3.0}), ("shell_exact", {"wall": 2.0}))
way_obj = next(iter(way.scene.objects.values()))
pr.check("Schritte 1-4 exakt", way_obj.kind == "brep")
way_hole = first_feature(way_obj, "hole")
pr.out(f"  nach Aushöhlen: V={way_obj.mesh.volume:.4f} Merkmale {kinds_of(way_obj.features)}")
with pr.Timed("Schritt 5 exakt: Buchse"):
    step5, _ = insert_exact(
        way_obj, "insert_heatset_m4", heatset_tool_exact("M4"), at_feature=way_hole, size="M4"
    )
s5 = pr.expect_solid("Schritt 5: Buchse exakt", step5)
m4 = standards.screw("M4")
sink_depth = (m4.countersink - entry.hole) / 2.0
sink_tool = pr.moved(pr.cone(entry.hole, m4.countersink, sink_depth), (0.0, 0.0, -sink_depth))
mouth = (0.0, 0.0, 10.0)
step6 = edit.boolean("difference", [step5, pr.moved(sink_tool, mouth)])
s6 = pr.expect_solid("Schritt 6: Senkung exakt", step6)
pr.check(
    "Schritt 6: Senkung nimmt Material (Kegel an der Mündung)",
    s6["volume"] < s5["volume"] and "cone" in s6["types"],
    str(s6["types"]),
)
pr.out(f"  Kundenweg exakt: V={s6['volume']:.4f}, Flächen {s6['faces']}, Arten {s6['types']}")
pr.step_roundtrip("Kundenweg §5.1 exakt", step6)
_, _, _, way_today = fresh(
    ("fillet_edges", {"radius": 3.0}),
    ("shell_exact", {"wall": 2.0}),
    ("insert_heatset_m4", {"at_feature": way_hole, "size": "M4"}),
)
today_way = next(iter(way_today.scene.objects.values()))
pr.check("heute kippt der Kundenweg in Schritt 5 ins Netz", today_way.kind == "mesh")
pr.ratio(
    "Kundenweg Schritt 5: Netz/exakt = Facettierung", today_way.mesh.volume, s5["volume"], 0.002
)

pr.finish("S8 Einsetzweg")
