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


def test_the_fastener_group_is_the_one_that_builds_exactly() -> None:
    builtin.load()
    fasteners = {spec.name for spec in PARTS.all() if spec.group == "fasteners"}
    assert fasteners == EXACT_PARTS


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
