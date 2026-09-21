"""Bausteine am exakten Kern (P2.7) — die Gruppe Verbindungen.

Eine Formbeschreibung, zwei Auswerter: Jeder Baustein wird einmal als Netz und
einmal als exakter Körper gebaut, und der exakte Körper muss gültig,
geschlossen und ein Körper sein, sein Volumen die Analytik treffen, die
Funktionsmaße in der richtigen Richtung liegen, seine Provenienzmerkmale
tragen und die STEP-Rundreise bestehen (Bericht ``konzepte/nachweise-cad-p2-7``,
Abschnitt 7). Das Netz daneben darf sich nur um die Facettierung unterscheiden.
"""

from __future__ import annotations

import math
from itertools import pairwise
from typing import Any

import pytest

from app.core.errors import InternalError
from app.core.geom.boolean import BOOLEAN_OVERLAP
from app.core.geom.mesh import MeshData
from app.core.knowledge import standards
from app.core.knowledge.parts import build, builtin, shapes
from app.core.knowledge.parts.fasteners import INSERT_LEAD_IN
from app.core.knowledge.parts.ops import EXACT_PARTS
from app.core.knowledge.parts.registry import PARTS
from app.core.knowledge.parts.shapes import building
from app.core.types import Profile, SceneObject
from tests.test_missing_ops import run

#: Volumen eines einbeschriebenen 48-Ecks gegen den Kreis — der einzige erlaubte
#: Unterschied zwischen Netz und exaktem Körper bei runden Formen.
FACET = shapes.SEGMENTS * math.sin(2.0 * math.pi / shapes.SEGMENTS) / (2.0 * math.pi)
HOST = (100.0, 100.0, 10.0)
ON_TOP = {"x": 0.0, "y": 0.0, "z": 10.0, "nx": 0.0, "ny": 0.0, "nz": 1.0}


def _kernel() -> Any:
    kernel = pytest.importorskip("app.core.brep.kernel")
    if not kernel.available():
        pytest.skip("ohne OpenCASCADE gibt es den exakten Kern nicht")
    return kernel


def _built(name: str, exact: bool, **values: object) -> Any:
    builtin.load()
    spec = PARTS.get(name)
    params = spec.params(**values)
    if not exact:
        return spec.fn(params)
    with building("brep"):
        return spec.fn(params)


def _sound(solid: Any, *, bodies: int = 1) -> Any:
    """Gültig, geschlossen, die erklärte Körperzahl — und kein Netz."""
    from OCP.BRepCheck import BRepCheck_Analyzer

    assert not isinstance(solid, MeshData)
    assert BRepCheck_Analyzer(solid.shape).IsValid()
    assert solid.is_closed
    assert solid.solid_count == bodies
    assert solid.volume > 0.0
    return solid


def _roundtrip(solid: Any) -> None:
    from app.core.brep import step

    back = step.read(step.write(solid, "baustein"))
    _sound(back, bodies=solid.solid_count)
    assert back.volume == pytest.approx(solid.volume, rel=1e-9)
    assert back.face_count == solid.face_count


def _frustum(bottom: float, top: float, height: float) -> float:
    lower, upper = bottom / 2.0, top / 2.0
    return math.pi * height / 3.0 * (lower**2 + lower * upper + upper**2)


def _thread_volume(diameter: float, pitch: float, length: float, *, internal: bool) -> float:
    """Kern plus Gang des Bausteingewindes: Pappus je Umlauf über das Gangprofil,
    schraubensymmetrisch je Länge — gerechnet aus derselben Quelle wie beide Kerne.
    """
    profile = list(shapes.ridge_profile(diameter, pitch, internal=internal))
    root = profile[0][0]
    # Das Profil schließt am Fuß; Schwerpunkt und Fläche über die Schuhbandformel.
    corners = [*profile, profile[0]]
    area = 0.0
    moment = 0.0
    for (r_a, z_a), (r_b, z_b) in pairwise(corners):
        cross = r_a * z_b - r_b * z_a
        area += cross
        moment += (r_a + r_b) * cross
    area, moment = abs(area) / 2.0, abs(moment) / 6.0
    return math.pi * root**2 * length + 2.0 * math.pi * moment * (length / pitch)


def _host() -> SceneObject:
    from app.core.brep import edit
    from app.core.brep.features import features_of

    body = edit.box(*HOST)
    return SceneObject(
        id="obj_1", name="Träger", mesh=body, kind="brep", features=features_of(body)
    )


# --- die Gruppe ------------------------------------------------------------------


def test_the_exact_groups_are_fasteners_mechanics_and_mounting_without_clamps() -> None:
    builtin.load()
    groups = {
        spec.name
        for spec in PARTS.all()
        if spec.group in {"fasteners", "mechanics", "mounting"}
        and not spec.name.startswith("profile_clamp")
    }
    assert groups == EXACT_PARTS


# --- die Grundformen: Zwillinge ---------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "make", "ratio"),
    [
        ("cylinder", lambda: shapes.cylinder(6.0, 10.0), FACET),
        ("box", lambda: shapes.box(4.0, 6.0, 8.0), 1.0),
        ("hexagon", lambda: shapes.hexagon(8.0, 5.0), 1.0),
        ("dovetail", lambda: shapes.dovetail(8.0, 5.0), 1.0),
        ("cone", lambda: shapes.cone(10.0, 4.0, 3.0), FACET),
        ("cone_tip", lambda: shapes.cone(10.0, 0.0, 3.0), FACET),
        ("slot_round", lambda: shapes.slot(4.0, 3.0, 3.0), FACET),
        ("tapered_bar", lambda: shapes.tapered_bar(10.0, 6.0, 20.0, 4.0, 3.0), 1.0),
        ("tapered_bar_short", lambda: shapes.tapered_bar(10.0, 6.0, 4.0, 4.0, 3.0), 1.0),
        ("wedge", lambda: shapes.wedge(8.0, 6.0, 4.0, 1.5), 1.0),
        ("wedge_tip", lambda: shapes.wedge(8.0, 6.0, 4.0), 1.0),
        ("moved", lambda: shapes.moved(shapes.box(4.0, 6.0, 8.0), (1.0, 2.0, 3.0)), 1.0),
        (
            "turned",
            lambda: shapes.turned(
                shapes.moved(shapes.box(4.0, 6.0, 8.0), (1.0, 0.0, 0.0)), 90.0, (0.0, 1.0, 0.0)
            ),
            1.0,
        ),
    ],
)
def test_every_basic_shape_has_an_exact_twin_with_the_same_frame(
    name: str, make: Any, ratio: float
) -> None:
    """Gleicher Rahmen, gleiche Maße; das Volumen weicht nur um die Facettierung ab."""
    _kernel()
    mesh = make()
    assert isinstance(mesh, MeshData), name
    with building("brep"):
        exact = _sound(make())
    assert exact.bounds.minimum == pytest.approx(mesh.bounds.minimum, abs=1e-6), name
    assert exact.bounds.maximum == pytest.approx(mesh.bounds.maximum, abs=1e-6), name
    assert mesh.volume / exact.volume == pytest.approx(ratio, rel=1e-9), name


def test_the_slot_keeps_its_ends_as_true_arcs() -> None:
    """Das Netz hat keinen Punkt auf der Achse seiner Halbkreise; exakt endet es genau bei ±L/2."""
    _kernel()
    mesh = shapes.slot(4.0, 12.0, 3.0)
    with building("brep"):
        exact = _sound(shapes.slot(4.0, 12.0, 3.0))
    assert exact.bounds.maximum[0] == pytest.approx(6.0, abs=1e-9)
    assert mesh.bounds.maximum[0] == pytest.approx(
        6.0 - 2.0 * (1.0 - math.cos(math.pi / 46)), abs=1e-3
    )
    assert exact.volume == pytest.approx(3.0 * (8.0 * 4.0 + math.pi * 4.0), rel=1e-9)
    assert FACET < mesh.volume / exact.volume < 1.0


def test_the_fuzzy_ladders_of_parts_and_rod_carry_the_same_steps() -> None:
    """Absolut in Millimetern hier, als Anteil der Steigung dort — dieselben Zahlen."""
    from app.core.brep import profiles
    from app.core.knowledge.parts import exact

    assert exact.UNION_FUZZ_MM == profiles.ROD_FUZZ_RATIOS


def test_a_union_that_leaves_two_bodies_is_refused_with_advice() -> None:
    from app.core.errors import GeometryError

    _kernel()
    with building("brep"):
        apart = shapes.moved(shapes.box(2.0, 2.0, 2.0), (10.0, 0.0, 0.0))
        with pytest.raises(GeometryError) as refused:
            build.union(shapes.box(2.0, 2.0, 2.0), apart)
    assert refused.value.suggestions


def test_a_compound_carries_filament_slots_and_the_finest_deflection() -> None:
    """Ein Verbund verliert weder die Farben seiner Teile noch ihre Vernetzungsfeinheit (§20)."""
    import dataclasses

    _kernel()
    with building("brep"):
        coloured = shapes.box(2.0, 2.0, 2.0)
        plain = shapes.moved(shapes.box(2.0, 2.0, 2.0), (10.0, 0.0, 0.0))
    coloured = dataclasses.replace(coloured, face_slots=(2,) * coloured.face_count, deflection=0.01)
    joined = build.compound(coloured, plain)
    assert joined.solid_count == 2
    assert joined.face_slots == (2,) * coloured.face_count + (0,) * plain.face_count
    assert joined.deflection == 0.01
    assert build.compound(plain, plain).face_slots == ()


def test_a_mesh_only_path_refuses_an_exact_body_instead_of_failing_later() -> None:
    _kernel()
    with building("brep"):
        exact = shapes.box(1.0, 1.0, 1.0)
        with pytest.raises(InternalError):
            shapes.mesh_only(exact)
        with pytest.raises(InternalError):
            shapes.thread_body(6.0, 1.0, 8.0)
    with pytest.raises(InternalError):
        build.union(shapes.box(1.0, 1.0, 1.0), exact)


# --- die Verbindungen: Volumen gegen Analytik, Richtung, Merkmale, STEP -----------------------


def test_screw_hole_exact_matches_its_analytic_volume_and_lies_under_the_mouth() -> None:
    _kernel()
    screw = standards.screw("M4")
    depth, head_room = 10.0, 2.0
    produced = _built(
        "screw_hole", True, size="M4", depth=depth, countersink=True, head_room=head_room
    )
    tool = _sound(produced.mesh)
    sink = (screw.countersink - screw.clearance) / 2.0
    radius, wide = screw.clearance / 2.0, screw.countersink / 2.0
    expected = (
        math.pi * radius**2 * (depth + BOOLEAN_OVERLAP)
        + _frustum(screw.clearance, screw.countersink, sink)
        - math.pi * radius**2 * sink
        + math.pi * (wide**2 - radius**2) * (head_room + BOOLEAN_OVERLAP)
    )
    assert tool.volume == pytest.approx(expected, rel=1e-9)
    assert tool.bounds.maximum[2] == pytest.approx(BOOLEAN_OVERLAP, abs=1e-9)
    assert tool.bounds.minimum[2] == pytest.approx(-depth, abs=1e-9)
    assert tool.bounds.maximum[0] == pytest.approx(wide, abs=1e-9)
    assert {"bore_1", "countersink_1", "head_room_1"} <= set(produced.features)
    mesh = _built(
        "screw_hole", False, size="M4", depth=depth, countersink=True, head_room=head_room
    )
    assert mesh.mesh.volume / tool.volume == pytest.approx(FACET, rel=1e-6)
    assert mesh.mesh.bounds.maximum == pytest.approx(tool.bounds.maximum, abs=1e-6)
    _roundtrip(tool)


def test_heatset_exact_widens_at_the_mouth_and_matches_its_analytic_volume() -> None:
    _kernel()
    entry = standards.insert("M4")
    produced = _built("heatset_m4", True, size="M4", lead_in=True, extra_depth=0.5)
    tool = _sound(produced.mesh)
    depth = entry.length + 0.5
    radius = entry.hole / 2.0
    expected = (
        math.pi * radius**2 * (depth + BOOLEAN_OVERLAP)
        + _frustum(entry.hole, entry.hole + 2.0 * INSERT_LEAD_IN, INSERT_LEAD_IN)
        - math.pi * radius**2 * INSERT_LEAD_IN
    )
    assert tool.volume == pytest.approx(expected, rel=1e-9)
    assert tool.bounds.maximum[2] == pytest.approx(BOOLEAN_OVERLAP, abs=1e-9)
    assert tool.bounds.minimum[2] == pytest.approx(-depth, abs=1e-9)
    assert tool.bounds.maximum[0] == pytest.approx(radius + INSERT_LEAD_IN, abs=1e-9)
    assert {"bore_1", "chamfer_1"} <= set(produced.features)
    _roundtrip(tool)


def test_nut_trap_exact_is_pocket_channel_and_bolt_in_one_body() -> None:
    _kernel()
    nut, screw, play = standards.nut("M4"), standards.screw("M4"), 0.2
    values = {"size": "M4", "direction": "side", "slide": 12.0, "play": play, "screw_hole": True}
    produced = _built("nut_trap", True, **values)
    tool = _sound(produced.mesh)
    width, height = nut.width + play, nut.height + play / 2.0
    hexagon = math.sqrt(3.0) / 2.0 * width**2
    bolt = math.pi * (screw.clearance / 2.0) ** 2
    # Der Kanal deckt die obere Hälfte des Sechskants, der Bolzen liegt ganz darin.
    expected = (hexagon / 2.0 + width * 12.0) * height + bolt * 20.0
    assert tool.volume == pytest.approx(expected, rel=1e-9)
    assert tool.bounds.maximum[0] == pytest.approx(width / 2.0, abs=1e-9)
    assert tool.bounds.minimum[1] == pytest.approx(-width / math.sqrt(3.0), abs=1e-9)
    assert tool.bounds.maximum[1] == pytest.approx(12.0, abs=1e-9)
    assert {"pocket_1", "bore_1"} <= set(produced.features)
    mesh = _built("nut_trap", False, **values)
    assert mesh.mesh.bounds.maximum == pytest.approx(tool.bounds.maximum, abs=1e-6)
    assert mesh.mesh.bounds.minimum == pytest.approx(tool.bounds.minimum, abs=1e-6)
    # Nur der Bolzen ist facettiert.
    assert 1.0 - (1.0 - FACET) * bolt * 20.0 / expected < mesh.mesh.volume / tool.volume < 1.0
    # Nach unten gedreht: dieselbe Lage wie am Netz, gemessen an den Hüllen.
    below = _sound(_built("nut_trap", True, **{**values, "direction": "bottom"}).mesh)
    below_mesh = _built("nut_trap", False, **{**values, "direction": "bottom"}).mesh
    assert below.bounds.maximum == pytest.approx(below_mesh.bounds.maximum, abs=1e-6)
    assert below.bounds.minimum == pytest.approx(below_mesh.bounds.minimum, abs=1e-6)
    _roundtrip(tool)


@pytest.mark.parametrize("internal", [False, True])
def test_printed_thread_exact_is_core_and_ridge_without_a_seam(internal: bool) -> None:
    """Kern und Gang sind ein genähter Körper; das Volumen ist das der Analytik."""
    _kernel()
    screw = standards.screw("M6")
    length = 8.0
    produced = _built("printed_thread", True, size="M6", length=length, internal=internal, play=0.0)
    body = _sound(produced.mesh)
    depth = screw.pitch * shapes.RIDGE_SHARE
    diameter = screw.nominal - 2.0 * depth if internal else screw.nominal
    expected = _thread_volume(diameter, screw.pitch, length, internal=internal)
    assert body.volume == pytest.approx(expected, rel=1e-6)
    top, bottom = (0.0, -length) if internal else (length, 0.0)
    assert body.bounds.maximum[2] == pytest.approx(top, abs=1e-6)
    assert body.bounds.minimum[2] == pytest.approx(bottom, abs=1e-6)
    assert body.bounds.maximum[0] == pytest.approx(screw.nominal / 2.0, abs=1e-6)
    thread = produced.features["thread_1"]
    assert thread.params["pitch"] == screw.pitch
    assert thread.params["internal"] is internal
    mesh = _built("printed_thread", False, size="M6", length=length, internal=internal, play=0.0)
    assert 0.98 < mesh.mesh.volume / body.volume < 1.0
    _roundtrip(body)


def test_printed_screw_exact_has_its_head_on_top_and_the_thread_below() -> None:
    _kernel()
    screw = standards.screw("M5")
    produced = _built("printed_screw", True, size="M5", length=12.0, countersunk=False, play=0.0)
    body = _sound(produced.mesh)
    head = math.sqrt(3.0) / 2.0 * screw.head**2 * screw.head_height
    thread = _thread_volume(screw.nominal, screw.pitch, 12.0, internal=False)
    overlap = math.pi * (screw.nominal / 2.0) ** 2 * BOOLEAN_OVERLAP
    assert head + thread - overlap <= body.volume <= head + thread
    assert body.bounds.maximum[2] == pytest.approx(screw.head_height, abs=1e-6)
    assert body.bounds.minimum[2] == pytest.approx(-12.0 + BOOLEAN_OVERLAP, abs=1e-6)
    assert produced.features["thread_1"].params["length"] == 12.0
    _roundtrip(body)


def test_printed_countersunk_screw_exact_is_a_compound_of_head_and_thread() -> None:
    """Kegel und Gang berühren sich tangential; ein Verbund bleibt gültig und STEP-fähig (B2)."""
    _kernel()
    screw = standards.screw("M5")
    builtin.load()
    spec = PARTS.get("printed_screw")
    params = spec.params(size="M5", length=12.0, countersunk=True, play=0.0)
    with building("brep"):
        produced = spec.fn(params)
        host_cut = spec.host_cut(params)
    body = _sound(produced.mesh, bodies=2)
    head_height = (screw.countersink - screw.nominal) / 2.0
    expected = _frustum(screw.nominal, screw.countersink, head_height) + _thread_volume(
        screw.nominal, screw.pitch, 12.0, internal=False
    )
    assert body.volume == pytest.approx(expected, rel=1e-6)
    assert body.bounds.maximum[2] == pytest.approx(0.0, abs=1e-6)
    assert body.bounds.minimum[2] == pytest.approx(-head_height - 12.0 + BOOLEAN_OVERLAP, abs=1e-6)
    _roundtrip(body)
    assert host_cut is not None
    cutter = _sound(host_cut.mesh)
    sink = (screw.countersink - screw.clearance) / 2.0
    assert cutter.volume == pytest.approx(
        _frustum(screw.clearance, screw.countersink, sink), rel=1e-9
    )
    assert cutter.bounds.maximum[2] == pytest.approx(0.0, abs=1e-9)
    assert "countersink_1" in host_cut.features


def test_printed_nut_exact_carries_the_internal_thread_through() -> None:
    _kernel()
    screw, nut, play = standards.screw("M5"), standards.nut("M5"), 0.2
    produced = _built("printed_nut", True, size="M5", play=play)
    body = _sound(produced.mesh)
    depth = screw.pitch * shapes.RIDGE_SHARE
    bore = screw.nominal - 2.0 * depth + play
    prism = math.sqrt(3.0) / 2.0 * nut.width**2 * nut.height
    removed = _thread_volume(bore, screw.pitch, nut.height, internal=True)
    assert body.volume == pytest.approx(prism - removed, rel=1e-6)
    assert body.bounds.maximum[2] == pytest.approx(nut.height, abs=1e-6)
    assert body.bounds.maximum[0] == pytest.approx(nut.width / 2.0, abs=1e-6)
    assert produced.features["thread_1"].params["internal"] is True
    mesh = _built("printed_nut", False, size="M5", play=play)
    assert abs(mesh.mesh.volume / body.volume - 1.0) < 0.02
    _roundtrip(body)


# --- der Weg durch die Operation: ein exakter Träger bleibt exakt --------------------------


def test_a_screw_hole_cuts_an_exact_host_and_keeps_it_exact(profile: Profile) -> None:
    kernel = _kernel()
    host = _host()
    outcome = run(
        "insert_screw_hole", host, profile, size="M3", depth=8.0, countersink=True, **ON_TOP
    )
    (result,) = outcome.outputs
    assert result.kind == "brep"
    body = _sound(result.mesh)
    assert isinstance(body, kernel.Solid)
    screw = standards.screw("M3")
    sink = (screw.countersink - screw.clearance) / 2.0
    removed = (
        math.pi * (screw.clearance / 2.0) ** 2 * 8.0
        + _frustum(screw.clearance, screw.countersink, sink)
        - math.pi * (screw.clearance / 2.0) ** 2 * sink
    )
    assert body.volume == pytest.approx(HOST[0] * HOST[1] * HOST[2] - removed, rel=1e-9)
    assert {"screw_hole_bore_1", "screw_hole_countersink_1"} <= set(result.features)
    assert set(host.features) <= set(result.features)
    assert not [finding for finding in outcome.findings if finding.severity == "error"]


def test_a_printed_thread_grows_on_an_exact_host_as_one_body(profile: Profile) -> None:
    _kernel()
    host = _host()
    outcome = run(
        "insert_printed_thread",
        host,
        profile,
        size="M6",
        length=8.0,
        internal=False,
        play=0.0,
        **ON_TOP,
    )
    (result,) = outcome.outputs
    body = _sound(result.mesh)
    assert result.kind == "brep"
    assert body.volume > HOST[0] * HOST[1] * HOST[2]
    # Aufgesetzt sinkt der Baustein ein Hundertstel ein — exakt wie am Netz (B4).
    assert body.bounds.maximum[2] == pytest.approx(18.0 - BOOLEAN_OVERLAP, abs=1e-6)
    assert "printed_thread_thread_1" in result.features
    assert result.features["printed_thread_thread_1"].params["centre"][2] == pytest.approx(
        14.0 - BOOLEAN_OVERLAP, abs=1e-9
    )


def test_a_printed_screw_stays_a_loose_part_next_to_its_exact_host(profile: Profile) -> None:
    """Ein lösbares Teil wird nicht verschweißt: Träger und Schraube sind ein Verbund (B9).

    Der Senkkopf ist selbst ein Verbund aus Kegel und Gang (B2) — drei Körper.
    Das Teil kommt über denselben Bauweg wie in der Operation, denn dort trägt
    es das Spiel aus dem Materialprofil des Trägers.
    """
    _kernel()
    from app.core.knowledge.parts.ops import _built_part
    from app.core.knowledge.profiles import for_object

    host = _host()
    values = {"size": "M5", "length": 6.0, "countersunk": True}
    outcome = run("insert_printed_screw", host, profile, **values, **ON_TOP)
    (result,) = outcome.outputs
    body = _sound(result.mesh, bodies=3)
    assert result.kind == "brep"
    screw = standards.screw("M5")
    sink = (screw.countersink - screw.clearance) / 2.0
    prepared = HOST[0] * HOST[1] * HOST[2] - _frustum(screw.clearance, screw.countersink, sink)
    spec = PARTS.get("printed_screw")
    _params, produced = _built_part(
        spec, spec.params(**values), for_object(profile, host), "fine", kernel="brep"
    )
    part = _sound(produced.mesh, bodies=2)
    assert body.volume == pytest.approx(prepared + part.volume, rel=1e-9)
    assert {"printed_screw_thread_1", "printed_screw_countersink_1"} <= set(result.features)


def test_a_part_that_misses_its_exact_host_says_so(profile: Profile) -> None:
    _kernel()
    host = _host()
    beside = {**ON_TOP, "x": 80.0}
    missed = run("insert_screw_hole", host, profile, size="M3", depth=8.0, **beside)
    assert missed.outputs[0].mesh.volume == pytest.approx(HOST[0] * HOST[1] * HOST[2], rel=1e-9)
    assert [finding.code for finding in missed.findings] == ["boolean.without_effect"]
    loose = run("insert_printed_thread", host, profile, size="M6", length=8.0, **beside)
    assert "parts.hanging_loose" in {finding.code for finding in loose.findings}
    assert loose.outputs[0].mesh.solid_count == 2


def test_a_mesh_host_keeps_the_mesh_path(profile: Profile) -> None:
    """Am Netzträger ändert sich nichts: Der Baustein bleibt ein Netz."""
    from app.core.geom.mesh import as_mesh_data

    host = _host()
    meshed = SceneObject(id="obj_1", name="Träger", mesh=as_mesh_data(host.mesh), kind="mesh")
    outcome = run(
        "insert_screw_hole", meshed, profile, size="M3", depth=8.0, countersink=True, **ON_TOP
    )
    assert isinstance(outcome.outputs[0].mesh, MeshData)
    assert outcome.outputs[0].mesh.volume < HOST[0] * HOST[1] * HOST[2]


# --- die Mechanik: Volumen gegen Analytik, Richtung, Merkmale, STEP ------------------------------


def _polygon_area(points: list[tuple[float, float]]) -> float:
    corners = [*points, points[0]]
    return abs(sum(x_a * y_b - x_b * y_a for (x_a, y_a), (x_b, y_b) in pairwise(corners))) / 2.0


def test_bearing_seat_exact_matches_its_analytic_volume() -> None:
    _kernel()
    entry = standards.bearing("608")
    produced = _built("bearing_seat", True, size="608", removable=False, grip=0.1, extra_depth=0.0)
    tool = _sound(produced.mesh)
    diameter = entry.outer - 0.1
    depth = entry.width
    assert tool.volume == pytest.approx(
        math.pi * (diameter / 2.0) ** 2 * (depth + BOOLEAN_OVERLAP), rel=1e-9
    )
    assert tool.bounds.maximum[2] == pytest.approx(BOOLEAN_OVERLAP, abs=1e-9)
    assert tool.bounds.minimum[2] == pytest.approx(-depth, abs=1e-9)
    assert "seat_1" in produced.features
    mesh = _built("bearing_seat", False, size="608", removable=False, grip=0.1, extra_depth=0.0)
    assert mesh.mesh.volume / tool.volume == pytest.approx(FACET, rel=1e-6)
    _roundtrip(tool)


def test_a_round_dowel_pin_exact_carries_its_chamfer_at_the_top() -> None:
    _kernel()
    diameter, length, chamfer = 6.0, 8.0, 0.6
    values = {"diameter": diameter, "length": length, "kind": "pin", "chamfer": chamfer}
    pin_body = _sound(_built("dowel", True, **values, shape="round").mesh)
    radius = diameter / 2.0
    # Der Fasenring nimmt oben ``chamfer`` hoch alles außerhalb des Kegels weg.
    expected = math.pi * radius**2 * (length - chamfer) + _frustum(
        diameter, diameter - 2.0 * chamfer, chamfer
    )
    assert pin_body.volume == pytest.approx(expected, rel=1e-9)
    assert pin_body.bounds.minimum[2] == pytest.approx(0.0, abs=1e-9)
    assert pin_body.bounds.maximum[2] == pytest.approx(length, abs=1e-9)
    assert pin_body.bounds.maximum[0] == pytest.approx(radius, abs=1e-9)
    _roundtrip(pin_body)
    for shape in ("hex", "dovetail"):
        body = _sound(_built("dowel", True, **values, shape=shape).mesh)
        mesh = _built("dowel", False, **values, shape=shape).mesh
        assert body.bounds.maximum[2] == pytest.approx(length, abs=1e-9), shape
        # Umkreis: keine Form ragt über den Nenn-Durchmesser hinaus (§24.1).
        assert max(body.bounds.maximum[0], body.bounds.maximum[1]) <= radius + 1e-9, shape
        assert FACET - 0.01 < mesh.volume / body.volume <= 1.0 + 1e-9, shape
        _roundtrip(body)


def test_a_dowel_bore_exact_lies_under_the_mouth_and_widens_there() -> None:
    _kernel()
    diameter, length, chamfer = 4.0, 8.0, 0.6
    produced = _built(
        "dowel", True, diameter=diameter, length=length, kind="bore", chamfer=chamfer, play=0.0
    )
    tool = _sound(produced.mesh)
    radius = diameter / 2.0
    expected = (
        math.pi * radius**2 * length
        + _frustum(diameter, diameter + 2.0 * chamfer, chamfer)
        - math.pi * radius**2 * chamfer
    )
    assert tool.volume == pytest.approx(expected, rel=1e-9)
    assert tool.bounds.maximum[2] == pytest.approx(0.0, abs=1e-9)
    assert tool.bounds.minimum[2] == pytest.approx(-length, abs=1e-9)
    assert tool.bounds.maximum[0] == pytest.approx(radius + chamfer, abs=1e-9)
    assert "bore_1" in produced.features


def test_hinge_eye_exact_keeps_exactly_its_wall_without_the_facet_correction() -> None:
    """Am Netz wächst der Außendurchmesser um die Facettenkorrektur, exakt nicht."""
    _kernel()
    values = {"pin": 3.0, "width": 8.0, "reach": 8.0, "wall": 2.0, "play": 0.2}
    produced = _built("hinge_eye", True, **values)
    body = _sound(produced.mesh)
    bore_width = 3.2
    outer = bore_width + 2.0 * 2.0
    # Liegender Zylinder über der Lasche: die untere Hälfte liegt im Kasten.
    expected = (
        math.pi * (outer / 2.0) ** 2 * 8.0 / 2.0
        + 8.0 * 8.0 * outer
        - math.pi * (bore_width / 2.0) ** 2 * 8.0
    )
    assert body.volume == pytest.approx(expected, rel=1e-9)
    assert body.bounds.maximum[1] == pytest.approx(8.0 + outer / 2.0, abs=1e-9)
    assert body.bounds.maximum[2] == pytest.approx(outer, abs=1e-9)
    eye = produced.features["eye_1"]
    assert eye.params["axis"] == (1.0, 0.0, 0.0)
    mesh = _built("hinge_eye", False, **values).mesh
    assert mesh.bounds.maximum[2] > body.bounds.maximum[2]  # die Korrektur, nur am Netz
    _roundtrip(body)


def test_latch_exact_is_the_same_wedge_as_the_mesh() -> None:
    _kernel()
    values = {"width": 6.0, "depth": 1.0, "height": 3.0}
    body = _sound(_built("latch", True, **values, negative=False).mesh)
    mesh = _built("latch", False, **values, negative=False).mesh
    assert body.volume == pytest.approx(6.0 * 1.0 * 3.0 / 2.0, rel=1e-9)
    assert mesh.volume == pytest.approx(body.volume, rel=1e-9)
    assert body.bounds.minimum == pytest.approx(mesh.bounds.minimum, abs=1e-9)
    assert body.bounds.maximum == pytest.approx(mesh.bounds.maximum, abs=1e-9)
    assert body.bounds.minimum[2] == pytest.approx(0.0, abs=1e-9)
    assert body.bounds.maximum[2] == pytest.approx(3.0, abs=1e-9)
    negative = _sound(_built("latch", True, **values, negative=True, play=0.2).mesh)
    assert negative.volume > body.volume


def test_living_hinge_exact_matches_its_analytic_volume() -> None:
    _kernel()
    values = {"width": 30.0, "leaf": 15.0, "thickness": 2.0, "film": 0.4, "gap": 1.5}
    produced = _built("living_hinge", True, **values)
    body = _sound(produced.mesh)
    assert body.volume == pytest.approx(30.0 * 31.5 * 2.0 - 30.0 * 1.5 * 1.6, rel=1e-9)
    assert _built("living_hinge", False, **values).mesh.volume == pytest.approx(
        body.volume, rel=1e-9
    )
    assert produced.features["hinge_1"].params["centre"][2] == pytest.approx(0.2)
    _roundtrip(body)


def test_snap_connector_exact_pin_and_bore_match_the_mesh_and_the_analytic_pocket() -> None:
    _kernel()
    values = {"diameter": 6.0, "length": 9.0, "play": 0.2}
    pin_body = _sound(_built("snap_connector", True, **values, kind="pin").mesh)
    assert _built("snap_connector", False, **values, kind="pin").mesh.volume == pytest.approx(
        pin_body.volume, rel=1e-9
    )
    assert pin_body.bounds.maximum[2] == pytest.approx(9.0, abs=1e-9)
    produced = _built("snap_connector", True, **values, kind="bore")
    tool = _sound(produced.mesh)
    # Dieselbe Rechnung wie im Baustein: Tasche minus Rastkante.
    play = 0.2
    room = math.sqrt(6.0**2 - (0.8 + play) ** 2)
    thickness = min(9.0 / 10.0, (room - play) / 3.0)
    across = 3.0 * thickness + play
    width = max(0.8, math.sqrt(6.0**2 - across**2) - play)
    run = thickness / math.tan(math.radians(35.0))
    catch = 9.0 - run
    depth = 9.0 + shapes.SEAT_RELIEF
    expected = (width + play) * across * depth - (width + play) * thickness * catch
    assert tool.volume == pytest.approx(expected, rel=1e-9)
    assert tool.bounds.maximum[2] == pytest.approx(0.0, abs=1e-9)
    assert "catch_1" in produced.features
    _roundtrip(tool)


def test_snap_fit_exact_is_one_side_profile_with_the_hook_on_top() -> None:
    _kernel()
    values = {"width": 8.0, "length": 16.0, "thickness": 1.6, "hook": 1.2, "lead_angle": 35.0}
    produced = _built("snap_fit", True, **values)
    body = _sound(produced.mesh)
    hook_height = 1.2 / math.tan(math.radians(35.0))
    arm = max(16.0, 1.6 * 10.0, hook_height)
    half = 0.8
    points = [(-half, 0.0), (half, 0.0), (half, arm - hook_height), (half + 1.2, arm), (-half, arm)]
    assert body.volume == pytest.approx(8.0 * _polygon_area(points), rel=1e-9)
    assert body.bounds.maximum[2] == pytest.approx(arm, abs=1e-9)
    assert body.bounds.maximum[1] == pytest.approx(half + 1.2, abs=1e-9)
    assert body.bounds.minimum[0] == pytest.approx(-4.0, abs=1e-9)
    assert _built("snap_fit", False, **values).mesh.volume == pytest.approx(body.volume, rel=1e-9)
    assert produced.features["hook_1"].params["normal"] == (0.0, 0.0, -1.0)
    _roundtrip(body)


def test_barrel_hinge_exact_is_two_bodies_with_air_between_them() -> None:
    _kernel()
    values = {"pin": 4.0, "width": 24.0, "reach": 12.0, "wall": 2.5, "play": 0.3}
    produced = _built("barrel_hinge", True, **values)
    hinge = _sound(produced.mesh, bodies=2)
    mesh = _built("barrel_hinge", False, **values).mesh
    assert mesh.component_count == 2
    gap = 0.3
    outer = 4.0 + 2.0 * (gap + 2.5)
    assert hinge.bounds.maximum[2] == pytest.approx(outer / 2.0 + 2.0 + gap + 2.5, abs=1e-9)
    assert hinge.bounds.minimum == pytest.approx(mesh.bounds.minimum, abs=1e-6)
    assert hinge.bounds.maximum == pytest.approx(mesh.bounds.maximum, abs=1e-6)
    assert FACET - 0.01 < mesh.volume / hinge.volume < 1.0
    assert produced.features["hinge_1"].params["axis"] == (1.0, 0.0, 0.0)
    _roundtrip(hinge)


def test_a_snap_fit_grows_on_an_exact_host_and_a_bearing_seat_cuts_it(profile: Profile) -> None:
    _kernel()
    host = _host()
    grown = run(
        "insert_snap_fit",
        host,
        profile,
        width=8.0,
        length=16.0,
        thickness=1.6,
        hook=1.2,
        lead_angle=35.0,
        **ON_TOP,
    )
    body = _sound(grown.outputs[0].mesh)
    assert grown.outputs[0].kind == "brep"
    assert body.volume > HOST[0] * HOST[1] * HOST[2]
    assert {"snap_fit_arm_1", "snap_fit_hook_1"} <= set(grown.outputs[0].features)
    cut = run("insert_bearing_seat", host, profile, size="608", removable=False, **ON_TOP)
    seat = _sound(cut.outputs[0].mesh)
    assert seat.volume < HOST[0] * HOST[1] * HOST[2]
    assert "bearing_seat_seat_1" in cut.outputs[0].features


# --- die Befestigung ohne Profilklemmen --------------------------------------------------------


def test_foot_exact_is_one_revolved_outline_with_the_chamfer_at_the_standing_end() -> None:
    from app.core.knowledge.parts.mounting import MIN_FOOT_TIP, POCKET_LEAD

    _kernel()
    diameter, height = 10.0, 3.0
    body = _sound(
        _built(
            "foot", True, kind="foot", diameter=diameter, height=height, chamfer=0.0, play=0.0
        ).mesh
    )
    chamfer = min(height / 5.0, height / 2.0, (diameter - MIN_FOOT_TIP) / 2.0)
    narrow = diameter - 2.0 * chamfer
    expected = math.pi * (diameter / 2.0) ** 2 * (height - chamfer) + _frustum(
        diameter, narrow, chamfer
    )
    assert body.volume == pytest.approx(expected, rel=1e-9)
    assert body.bounds.maximum[2] == pytest.approx(height, abs=1e-9)
    assert body.bounds.maximum[0] == pytest.approx(diameter / 2.0, abs=1e-9)
    mesh = _built("foot", False, kind="foot", diameter=diameter, height=height, chamfer=0.0).mesh
    assert mesh.volume / body.volume == pytest.approx(FACET, rel=1e-6)
    _roundtrip(body)
    produced = _built(
        "foot", True, kind="pocket", diameter=diameter, height=height, chamfer=0.0, play=0.2
    )
    tool = _sound(produced.mesh)
    wide = diameter + 0.2
    lead = min(POCKET_LEAD, height / 2.0)
    expected = math.pi * (wide / 2.0) ** 2 * (height - lead) + _frustum(
        wide, wide + 2.0 * lead, lead
    )
    assert tool.volume == pytest.approx(expected, rel=1e-9)
    assert tool.bounds.maximum[2] == pytest.approx(0.0, abs=1e-9)
    assert tool.bounds.minimum[2] == pytest.approx(-height, abs=1e-9)
    assert tool.bounds.maximum[0] == pytest.approx(wide / 2.0 + lead, abs=1e-9)
    assert "foot_1" in produced.features


def test_keyhole_exact_runs_down_minus_y_with_true_slot_ends() -> None:
    _kernel()
    values = {"size": "M4", "drop": 8.0, "depth": 4.0, "head_room": 2.5, "play": 0.2}
    produced = _built("keyhole", True, **values)
    tool = _sound(produced.mesh)
    mesh = _built("keyhole", False, **values).mesh
    assert tool.bounds.maximum[2] == pytest.approx(BOOLEAN_OVERLAP, abs=1e-9)
    assert tool.bounds.minimum[2] == pytest.approx(-4.0 - BOOLEAN_OVERLAP, abs=1e-9)
    assert tool.bounds.minimum[1] < -tool.bounds.maximum[1]
    # Die Langlochenden sind exakt Halbkreise; das Netz endet um den Sag früher.
    assert tool.bounds.minimum[1] == pytest.approx(mesh.bounds.minimum[1], abs=0.01)
    assert tool.bounds.minimum[1] < mesh.bounds.minimum[1]
    assert FACET - 0.01 < mesh.volume / tool.volume < 1.0
    assert {"pocket_1", "bore_1"} <= set(produced.features)
    _roundtrip(tool)


def test_magnet_pocket_exact_narrows_at_the_lip_and_matches_its_analytic_volume() -> None:
    from app.core.knowledge.parts.mounting import MAGNET_LIP_HEIGHT

    _kernel()
    entry = standards.magnet("8x3")
    values = {"size": "8x3", "play": 0.2, "cover": 0.0, "press_lip": True, "grip": 0.15}
    produced = _built("magnet_pocket", True, **values)
    tool = _sound(produced.mesh)
    diameter = entry.diameter + 0.2
    narrow = entry.diameter - 0.15
    lip = min(MAGNET_LIP_HEIGHT, entry.height / 2.0)
    expected = (
        math.pi * (diameter / 2.0) ** 2 * (entry.height - lip)
        + _frustum(diameter, narrow, lip)
        + math.pi * (narrow / 2.0) ** 2 * BOOLEAN_OVERLAP
    )
    assert tool.volume == pytest.approx(expected, rel=1e-9)
    assert tool.bounds.maximum[2] == pytest.approx(BOOLEAN_OVERLAP, abs=1e-9)
    assert tool.bounds.minimum[2] == pytest.approx(-entry.height, abs=1e-9)
    assert tool.bounds.maximum[0] == pytest.approx(diameter / 2.0, abs=1e-9)
    assert "pocket_1" in produced.features
    mesh = _built("magnet_pocket", False, **values).mesh
    assert mesh.volume / tool.volume == pytest.approx(FACET, rel=1e-6)
    _roundtrip(tool)


def test_wall_mount_exact_matches_its_analytic_volume_with_holes_along_y() -> None:
    _kernel()
    screw = standards.screw("M4")
    values = {
        "width": 30.0,
        "height": 25.0,
        "thickness": 3.0,
        "size": "M4",
        "holes": 2,
        "lip": 12.0,
    }
    produced = _built("wall_mount", True, **values)
    body = _sound(produced.mesh)
    expected = (
        30.0 * 3.0 * 25.0 + 30.0 * 12.0 * 3.0 - 2.0 * math.pi * (screw.clearance / 2.0) ** 2 * 3.0
    )
    assert body.volume == pytest.approx(expected, rel=1e-9)
    assert body.bounds.maximum[1] == pytest.approx(1.5 + 12.0, abs=1e-9)
    assert produced.features["bore_1"].params["axis"] == (0.0, 1.0, 0.0)
    assert produced.features["bore_2"].params["through"] is True
    # Nur die Löcher sind facettiert, und ein 48-Eck-Loch nimmt weniger weg als ein rundes.
    mesh = _built("wall_mount", False, **values).mesh
    assert 1.0 < mesh.volume / body.volume < 1.0 + 0.001
    _roundtrip(body)


def test_pegboard_hook_exact_is_two_hooks_without_a_plate_and_one_body_with_it() -> None:
    _kernel()
    values = {
        "system": "skadis",
        "count": 2,
        "steps": 1,
        "upright": False,
        "latch": True,
        "play": 0.2,
        "lip": 0.0,
    }
    produced = _built("pegboard_hook", True, **values, plate=0.0)
    hooks = _sound(produced.mesh, bodies=2)
    mesh = _built("pegboard_hook", False, **values, plate=0.0).mesh
    assert mesh.component_count == 2
    assert {"hook_1", "hook_2", "latch_1", "latch_2"} <= set(produced.features)
    # Bounds bis auf den Sag der Langlochenden gleich; nur die Langlöcher sind facettiert.
    assert hooks.bounds.minimum == pytest.approx(mesh.bounds.minimum, abs=0.01)
    assert hooks.bounds.maximum == pytest.approx(mesh.bounds.maximum, abs=0.01)
    assert FACET - 0.01 < mesh.volume / hooks.volume < 1.0
    _roundtrip(hooks)
    joined = _sound(_built("pegboard_hook", True, **values, plate=2.0).mesh)
    assert joined.volume > hooks.volume
    assert joined.bounds.minimum[2] == pytest.approx(-2.0, abs=1e-9)


def test_a_magnet_pocket_cuts_and_a_wall_mount_grows_on_an_exact_host(profile: Profile) -> None:
    _kernel()
    host = _host()
    cut = run(
        "insert_magnet_pocket", host, profile, size="8x3", cover=0.0, press_lip=False, **ON_TOP
    )
    tool = _sound(cut.outputs[0].mesh)
    assert cut.outputs[0].kind == "brep"
    assert tool.volume < HOST[0] * HOST[1] * HOST[2]
    assert "magnet_pocket_pocket_1" in cut.outputs[0].features
    grown = run(
        "insert_wall_mount",
        host,
        profile,
        width=30.0,
        height=25.0,
        thickness=3.0,
        size="M4",
        holes=2,
        lip=12.0,
        **ON_TOP,
    )
    body = _sound(grown.outputs[0].mesh)
    assert body.volume > HOST[0] * HOST[1] * HOST[2]
    assert {"wall_mount_plate_1", "wall_mount_bore_1", "wall_mount_bore_2"} <= set(
        grown.outputs[0].features
    )
