"""Bausteine am exakten Kern (P2.7) — alle mitgelieferten, Verbindungen bis Kalibrierung.

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
from app.core.knowledge.parts.structure import MIN_RIB, RIB_SHARE
from app.core.knowledge.parts.testbodies import LABEL_DEPTH
from app.core.types import Profile, SceneObject
from app.core.units import MAX_FACET_SAG
from tests.helpers import exact_kernel, thread_volume
from tests.helpers import run_operation as run

#: Volumen eines einbeschriebenen 48-Ecks gegen den Kreis — der einzige erlaubte
#: Unterschied zwischen Netz und exaktem Körper bei runden Formen.
FACET = shapes.SEGMENTS * math.sin(2.0 * math.pi / shapes.SEGMENTS) / (2.0 * math.pi)
HOST = (100.0, 100.0, 10.0)
ON_TOP = {"x": 0.0, "y": 0.0, "z": 10.0, "nx": 0.0, "ny": 0.0, "nz": 1.0}


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


def _host(size: tuple[float, float, float] = HOST) -> SceneObject:
    from app.core.brep import edit
    from app.core.brep.features import features_of

    body = edit.box(*size)
    return SceneObject(
        id="obj_1", name="Träger", mesh=body, kind="brep", features=features_of(body)
    )


# --- die Gruppe ------------------------------------------------------------------


def test_every_built_in_part_builds_exactly() -> None:
    builtin.load()
    assert {spec.name for spec in PARTS.all()} == EXACT_PARTS


# --- die Grundformen: Zwillinge ---------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "make", "ratio"),
    [
        ("cylinder", lambda: shapes.cylinder(6.0, 10.0), FACET),
        ("box", lambda: shapes.box(4.0, 6.0, 8.0), 1.0),
        ("rounded_box_square", lambda: shapes.rounded_box(4.0, 6.0, 8.0, 0.0), 1.0),
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
    exact_kernel()
    mesh = make()
    assert isinstance(mesh, MeshData), name
    with building("brep"):
        exact = _sound(make())
    assert exact.bounds.minimum == pytest.approx(mesh.bounds.minimum, abs=1e-6), name
    assert exact.bounds.maximum == pytest.approx(mesh.bounds.maximum, abs=1e-6), name
    assert mesh.volume / exact.volume == pytest.approx(ratio, rel=1e-9), name


def test_the_slot_keeps_its_ends_as_true_arcs() -> None:
    """Das Netz hat keinen Punkt auf der Achse seiner Halbkreise; exakt endet es genau bei ±L/2."""
    exact_kernel()
    mesh = shapes.slot(4.0, 12.0, 3.0)
    with building("brep"):
        exact = _sound(shapes.slot(4.0, 12.0, 3.0))
    assert exact.bounds.maximum[0] == pytest.approx(6.0, abs=1e-9)
    assert mesh.bounds.maximum[0] == pytest.approx(
        6.0 - 2.0 * (1.0 - math.cos(math.pi / 46)), abs=1e-3
    )
    assert exact.volume == pytest.approx(3.0 * (8.0 * 4.0 + math.pi * 4.0), rel=1e-9)
    assert FACET < mesh.volume / exact.volume < 1.0


def test_the_rod_no_longer_carries_a_fuzzy_ladder() -> None:
    """RM-195: Der Gewindebolzen entsteht genäht; seine Fuzzy-Leiter ist gefallen.

    Die Zahlen standen noch in ``profiles.ROD_FUZZ_RATIOS``, gelesen nur von
    einem Test, der sie gegen die Leiter der Bausteine hielt. Eine Konstante,
    die niemand mehr benutzt, sieht aus wie eine, auf die sich jemand verlässt.
    """
    from app.core.brep import profiles
    from app.core.knowledge.parts import exact

    assert not hasattr(profiles, "ROD_FUZZ_RATIOS")
    assert exact.UNION_FUZZ_MM == (1e-4, 1e-3, 1e-2)


def test_a_union_that_leaves_two_bodies_is_refused_with_advice() -> None:
    from app.core.errors import GeometryError

    exact_kernel()
    with building("brep"):
        apart = shapes.moved(shapes.box(2.0, 2.0, 2.0), (10.0, 0.0, 0.0))
        with pytest.raises(GeometryError) as refused:
            build.union(shapes.box(2.0, 2.0, 2.0), apart)
    assert refused.value.suggestions


def test_a_compound_carries_filament_slots_and_the_finest_deflection() -> None:
    """Ein Verbund verliert weder die Farben seiner Teile noch ihre Vernetzungsfeinheit (§20)."""
    import dataclasses

    exact_kernel()
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
    exact_kernel()
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
    exact_kernel()
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
    exact_kernel()
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
    exact_kernel()
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
    # Nur der Bolzen ist facettiert. Die Untergrenze **ist** der Facettenverlust
    # des Bolzens, das Netz trifft sie bis auf die letzten Stellen — verglichen
    # wird deshalb mit einem Rundungsspielraum, nicht mit ``<`` auf der Grenze
    # (seit ``MeshData.volume`` mit ``math.fsum`` summiert, lag es 10⁻¹³ darunter).
    lower = 1.0 - (1.0 - FACET) * bolt * 20.0 / expected
    assert lower - 1e-9 < mesh.mesh.volume / tool.volume < 1.0
    # Nach unten gedreht: dieselbe Lage wie am Netz, gemessen an den Hüllen.
    below = _sound(_built("nut_trap", True, **{**values, "direction": "bottom"}).mesh)
    below_mesh = _built("nut_trap", False, **{**values, "direction": "bottom"}).mesh
    assert below.bounds.maximum == pytest.approx(below_mesh.bounds.maximum, abs=1e-6)
    assert below.bounds.minimum == pytest.approx(below_mesh.bounds.minimum, abs=1e-6)
    _roundtrip(tool)


@pytest.mark.parametrize("internal", [False, True])
def test_printed_thread_exact_is_core_and_ridge_without_a_seam(internal: bool) -> None:
    """Kern und Gang sind ein genähter Körper; das Volumen ist das der Analytik."""
    exact_kernel()
    screw = standards.screw("M6")
    length = 8.0
    produced = _built("printed_thread", True, size="M6", length=length, internal=internal, play=0.0)
    body = _sound(produced.mesh)
    depth = screw.pitch * shapes.RIDGE_SHARE
    diameter = screw.nominal - 2.0 * depth if internal else screw.nominal
    # Das Innengewinde reicht als Werkzeug ein Hundertstel über seine Mündung.
    built = length + BOOLEAN_OVERLAP if internal else length
    expected = thread_volume(diameter, screw.pitch, built, internal=internal)
    assert body.volume == pytest.approx(expected, rel=1e-6)
    top, bottom = (BOOLEAN_OVERLAP, -length) if internal else (length, 0.0)
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
    exact_kernel()
    screw = standards.screw("M5")
    produced = _built("printed_screw", True, size="M5", length=12.0, countersunk=False, play=0.0)
    body = _sound(produced.mesh)
    head = math.sqrt(3.0) / 2.0 * screw.head**2 * screw.head_height
    thread = thread_volume(screw.nominal, screw.pitch, 12.0, internal=False)
    overlap = math.pi * (screw.nominal / 2.0) ** 2 * BOOLEAN_OVERLAP
    assert head + thread - overlap <= body.volume <= head + thread
    assert body.bounds.maximum[2] == pytest.approx(screw.head_height, abs=1e-6)
    assert body.bounds.minimum[2] == pytest.approx(-12.0 + BOOLEAN_OVERLAP, abs=1e-6)
    assert produced.features["thread_1"].params["length"] == 12.0
    _roundtrip(body)


def test_printed_countersunk_screw_exact_is_a_compound_of_head_and_thread() -> None:
    """Kegel und Gang berühren sich tangential; ein Verbund bleibt gültig und STEP-fähig (B2)."""
    exact_kernel()
    screw = standards.screw("M5")
    builtin.load()
    spec = PARTS.get("printed_screw")
    params = spec.params(size="M5", length=12.0, countersunk=True, play=0.0)
    with building("brep"):
        produced = spec.fn(params)
        host_cut = spec.host_cut(params)
    body = _sound(produced.mesh, bodies=2)
    head_height = (screw.countersink - screw.nominal) / 2.0
    expected = _frustum(screw.nominal, screw.countersink, head_height) + thread_volume(
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
    exact_kernel()
    screw, nut, play = standards.screw("M5"), standards.nut("M5"), 0.2
    produced = _built("printed_nut", True, size="M5", play=play)
    body = _sound(produced.mesh)
    depth = screw.pitch * shapes.RIDGE_SHARE
    bore = screw.nominal - 2.0 * depth + play
    prism = math.sqrt(3.0) / 2.0 * nut.width**2 * nut.height
    removed = thread_volume(bore, screw.pitch, nut.height, internal=True)
    assert body.volume == pytest.approx(prism - removed, rel=1e-6)
    # Die Mutter steht um das Spiel über ihrer Fläche (RM-276).
    assert body.bounds.maximum[2] == pytest.approx(play + nut.height, abs=1e-6)
    assert body.bounds.maximum[0] == pytest.approx(nut.width / 2.0, abs=1e-6)
    assert produced.features["thread_1"].params["internal"] is True
    mesh = _built("printed_nut", False, size="M5", play=play)
    assert abs(mesh.mesh.volume / body.volume - 1.0) < 0.02
    _roundtrip(body)


# --- der Weg durch die Operation: ein exakter Träger bleibt exakt --------------------------


def test_a_screw_hole_cuts_an_exact_host_and_keeps_it_exact(profile: Profile) -> None:
    exact_kernel()
    from app.core.brep import kernel

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
    exact_kernel()
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
    exact_kernel()
    from app.core.knowledge.parts.ops import _built_part
    from app.core.knowledge.profiles import for_object

    host = _host()
    values = {"size": "M5", "length": 6.0, "countersunk": True}
    outcome = run("insert_printed_screw", host, profile, **values, **ON_TOP)
    (result,) = outcome.outputs
    body = _sound(result.mesh, bodies=3)
    assert result.kind == "brep"
    screw = standards.screw("M5")
    # Die Senkung steht um das Spiel senkrecht zur 90°-Flanke vom Kopf ab (RM-276).
    mouth = screw.countersink + 2.0 * math.sqrt(2.0) * for_object(profile, host).material.clearance
    sink = (mouth - screw.clearance) / 2.0
    prepared = HOST[0] * HOST[1] * HOST[2] - _frustum(screw.clearance, mouth, sink)
    spec = PARTS.get("printed_screw")
    _params, produced = _built_part(
        spec, spec.params(**values), for_object(profile, host), "fine", kernel="brep"
    )
    part = _sound(produced.mesh, bodies=2)
    assert body.volume == pytest.approx(prepared + part.volume, rel=1e-9)
    assert {"printed_screw_thread_1", "printed_screw_countersink_1"} <= set(result.features)


def test_a_part_that_misses_its_exact_host_says_so(profile: Profile) -> None:
    exact_kernel()
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
    exact_kernel()
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
    exact_kernel()
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
    exact_kernel()
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
        # Ein Hundertstel über die Mündung, in der Weite der Einführung.
        + math.pi * (radius + chamfer) ** 2 * BOOLEAN_OVERLAP
    )
    assert tool.volume == pytest.approx(expected, rel=1e-9)
    assert tool.bounds.maximum[2] == pytest.approx(BOOLEAN_OVERLAP, abs=1e-9)
    assert tool.bounds.minimum[2] == pytest.approx(-length, abs=1e-9)
    assert tool.bounds.maximum[0] == pytest.approx(radius + chamfer, abs=1e-9)
    assert "bore_1" in produced.features


def test_hinge_eye_exact_keeps_exactly_its_wall_without_the_facet_correction() -> None:
    """Am Netz wächst der Außendurchmesser um die Facettenkorrektur, exakt nicht."""
    exact_kernel()
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
    exact_kernel()
    values = {"width": 6.0, "depth": 1.0, "height": 3.0}
    body = _sound(_built("latch", True, **values, negative=False).mesh)
    mesh = _built("latch", False, **values, negative=False).mesh
    assert body.volume == pytest.approx(6.0 * 1.0 * 3.0 / 2.0, rel=1e-9)
    assert mesh.volume == pytest.approx(body.volume, rel=1e-9)
    assert body.bounds.minimum == pytest.approx(mesh.bounds.minimum, abs=1e-9)
    assert body.bounds.maximum == pytest.approx(mesh.bounds.maximum, abs=1e-9)
    # Die Nase liegt auf ihrer Grundfläche: Höhe entlang -Y, Überstand in Z.
    assert body.bounds.minimum[2] == pytest.approx(0.0, abs=1e-9)
    assert body.bounds.maximum[2] == pytest.approx(1.0, abs=1e-9)
    assert body.bounds.minimum[1] == pytest.approx(-3.0, abs=1e-9)
    assert body.bounds.maximum[1] == pytest.approx(0.0, abs=1e-9)
    negative = _sound(_built("latch", True, **values, negative=True, play=0.2).mesh)
    assert negative.volume > body.volume


def test_living_hinge_exact_matches_its_analytic_volume() -> None:
    exact_kernel()
    values = {"width": 30.0, "leaf": 15.0, "thickness": 2.0, "film": 0.4, "gap": 1.5}
    produced = _built("living_hinge", True, **values)
    body = _sound(produced.mesh)
    assert body.volume == pytest.approx(30.0 * 31.5 * 2.0 - 30.0 * 1.5 * 1.6, rel=1e-9)
    assert _built("living_hinge", False, **values).mesh.volume == pytest.approx(
        body.volume, rel=1e-9
    )
    assert produced.features["hinge_1"].params["centre"][2] == pytest.approx(0.4)
    _roundtrip(body)


def test_snap_connector_exact_pin_and_bore_match_the_mesh_and_the_analytic_pocket() -> None:
    exact_kernel()
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
    expected = (width + play) * across * (depth + BOOLEAN_OVERLAP) - (
        width + play
    ) * thickness * catch
    assert tool.volume == pytest.approx(expected, rel=1e-9)
    assert tool.bounds.maximum[2] == pytest.approx(BOOLEAN_OVERLAP, abs=1e-9)
    assert "catch_1" in produced.features
    _roundtrip(tool)


def test_snap_fit_exact_is_one_side_profile_with_the_ramp_at_the_tip() -> None:
    exact_kernel()
    values = {"width": 8.0, "length": 16.0, "thickness": 1.6, "hook": 1.2, "lead_angle": 35.0}
    produced = _built("snap_fit", True, **values)
    body = _sound(produced.mesh)
    hook_height = 1.2 / math.tan(math.radians(35.0))
    arm = max(16.0, 1.6 * 10.0, hook_height)
    half = 0.8
    catch = arm - hook_height
    points = [
        (-half, 0.0),
        (half, 0.0),
        (half, catch),
        (half + 1.2, catch),
        (half, arm),
        (-half, arm),
    ]
    assert body.volume == pytest.approx(8.0 * _polygon_area(points), rel=1e-9)
    assert body.bounds.maximum[2] == pytest.approx(arm, abs=1e-9)
    assert body.bounds.maximum[1] == pytest.approx(half + 1.2, abs=1e-9)
    assert body.bounds.minimum[0] == pytest.approx(-4.0, abs=1e-9)
    assert _built("snap_fit", False, **values).mesh.volume == pytest.approx(body.volume, rel=1e-9)
    assert produced.features["hook_1"].params["normal"] == (0.0, 0.0, -1.0)
    assert produced.features["hook_1"].params["centre"][2] == pytest.approx(catch, abs=1e-9)
    _roundtrip(body)


def test_barrel_hinge_exact_is_two_bodies_with_air_between_them() -> None:
    exact_kernel()
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
    exact_kernel()
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

    exact_kernel()
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
    expected = (
        math.pi * (wide / 2.0) ** 2 * (height - lead)
        + _frustum(wide, wide + 2.0 * lead, lead)
        + math.pi * (wide / 2.0 + lead) ** 2 * BOOLEAN_OVERLAP
    )
    assert tool.volume == pytest.approx(expected, rel=1e-9)
    assert tool.bounds.maximum[2] == pytest.approx(BOOLEAN_OVERLAP, abs=1e-9)
    assert tool.bounds.minimum[2] == pytest.approx(-height, abs=1e-9)
    assert tool.bounds.maximum[0] == pytest.approx(wide / 2.0 + lead, abs=1e-9)
    assert "foot_1" in produced.features


def test_keyhole_exact_runs_down_minus_y_with_true_slot_ends() -> None:
    exact_kernel()
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

    exact_kernel()
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
    exact_kernel()
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


@pytest.mark.parametrize(
    ("values", "width", "length"),
    [
        ({"size": "M4", "width": 0.0, "length": 0.0, "thickness": 4.0}, 9.0, 9.0),
        ({"size": "M5", "width": 16.0, "length": 20.0, "thickness": 5.0}, 16.0, 20.0),
        ({"size": "M8", "width": 0.0, "length": 30.0, "thickness": 6.0}, 16.0, 30.0),
    ],
)
def test_lug_exact_is_half_a_slot_with_a_true_arc_and_the_hole_along_y(
    values: dict[str, Any], width: float, length: float
) -> None:
    """Rechteck und Halbkreis mit dem Durchgangsloch der Tabelle, exakt bis auf die Rundung.

    Ohne Eintrag ist die Lasche so breit wie die Unterlegscheibe (M4: 9 mm,
    M8: 16 mm) und so lang, dass sie neben der Fläche Platz hat; das Loch sitzt
    in der Mitte des runden Endes. Sie steht von der Fläche nach +Z ab und
    liegt in Y von null bis zur Dicke nach -Y — dorthin, wo ``keeps_up`` oben
    hinlegt.
    """
    exact_kernel()
    produced = _built("lug", True, **values)
    body = _sound(produced.mesh)
    clearance = standards.screw(str(values["size"])).clearance
    thickness = float(values["thickness"])
    reach = length - width / 2.0
    area = width * reach + math.pi * width**2 / 8.0 - math.pi * clearance**2 / 4.0
    assert body.volume == pytest.approx(area * thickness, rel=1e-9)
    assert tuple(body.bounds.minimum) == pytest.approx((-width / 2.0, -thickness, 0.0), abs=1e-9)
    assert tuple(body.bounds.maximum) == pytest.approx((width / 2.0, 0.0, length), abs=1e-9)
    hole = produced.features["bore_1"]
    assert hole.params["axis"] == (0.0, 1.0, 0.0)
    assert hole.params["diameter"] == pytest.approx(clearance)
    assert hole.params["centre"] == pytest.approx((0.0, -thickness / 2.0, reach))
    assert hole.params["through"] is True
    assert produced.features["lug_1"].params["normal"] == (0.0, -1.0, 0.0)
    # Nur Bogen und Loch sind am Netz facettiert, und beide fast gleich.
    mesh = _built("lug", False, **values).mesh
    assert abs(mesh.volume / body.volume - 1.0) < 0.005
    _roundtrip(body)


def test_a_lug_grows_on_an_exact_host_and_stays_exact(profile: Profile) -> None:
    exact_kernel()
    host = _host()
    grown = run("insert_lug", host, profile, size="M4", thickness=4.0, **ON_TOP)
    body = _sound(grown.outputs[0].mesh)
    assert grown.outputs[0].kind == "brep"
    assert body.volume > HOST[0] * HOST[1] * HOST[2]
    # Aufgesetzt sinkt sie um die Überlappung in den Träger (``ops._place``).
    assert body.bounds.maximum[2] == pytest.approx(HOST[2] + 9.0 - BOOLEAN_OVERLAP, abs=1e-6)
    assert {"lug_bore_1", "lug_lug_1"} <= set(grown.outputs[0].features)


def _strip(radius: float, half: float) -> float:
    """Fläche eines Halbkreises vom Radius ``radius``, auf ``|x| <= half`` beschnitten."""
    half = min(half, radius)
    return half * math.sqrt(radius**2 - half**2) + radius**2 * math.asin(half / radius)


def _clamp_volume(pipe: float, play: float, wall: float, width: float, screw: str) -> float:
    """Die Rohrschelle aus Kreisen, Rechtecken und Kreisstreifen, unabhängig vom Baustein.

    Ring um die Rohrmitte eine Wand über dem Fuß; Fuß bis zur Ringmitte, so
    breit wie die Ringmitte der Wand; Ohrenblock von der Ringmitte bis eine
    Unterlegscheibe über den Ring; Spalt ``π · Spiel + 1``; die Querschraube
    nimmt aus beiden Ohren je eine Wanddicke.
    """
    nut = standards.nut(screw)
    seat = max(
        standards.washer(screw).outer,
        standards.screw(screw).head,
        nut.width * 2.0 / math.sqrt(3.0),
    )
    clearance = standards.screw(screw).clearance
    inner = (pipe + play) / 2.0
    outer = inner + wall
    centre = outer + wall
    foot = inner + wall / 2.0
    gap = math.pi * play + 1.0
    ear = gap / 2.0 + wall
    rise = outer + seat
    section = (
        math.pi * outer**2
        + (2.0 * foot * centre - _strip(outer, foot))
        + (2.0 * ear * rise - _strip(outer, ear))
        - math.pi * inner**2
        - (gap * rise - _strip(inner, gap / 2.0))
    )
    return width * section - 2.0 * wall * math.pi * clearance**2 / 4.0


@pytest.mark.parametrize(
    ("values", "pipe"),
    [
        # Klemmschelle aus dem Nachbau: Ring Ø 16,9 innen, Klemmohren mit M5.
        (
            {
                "size": "15",
                "diameter": 16.65,
                "width": 30.0,
                "wall": 3.0,
                "screw_size": "M5",
                "play": 0.25,
            },
            16.65,
        ),
        ({"size": "22", "width": 15.0, "wall": 3.0, "screw_size": "M4", "play": 0.25}, 22.0),
        ({"size": "40", "width": 20.0, "wall": 4.0, "screw_size": "M6", "play": 0.35}, 40.0),
    ],
)
def test_pipe_clamp_exact_matches_its_analytic_volume_and_keeps_the_pipe_free(
    values: dict[str, Any], pipe: float
) -> None:
    """Rohrschelle am exakten Kern: Volumen gegen die Analytik, Merkmale, STEP-Rundreise.

    Und die Zusage des Bausteins als Paar geprüft: Ein Rohr des Nennmaßes
    in der Schelle schneidet sie nirgends, und die Querschraube läuft über
    dem Ring, nicht durch das Rohr.
    """
    exact_kernel()
    produced = _built("pipe_clamp", True, **values)
    body = _sound(produced.mesh)
    play, wall = float(values["play"]), float(values["wall"])
    expected = _clamp_volume(pipe, play, wall, float(values["width"]), str(values["screw_size"]))
    assert body.volume == pytest.approx(expected, rel=1e-9)
    inner = (pipe + play) / 2.0
    centre = inner + 2.0 * wall
    seat = produced.features["seat_1"]
    assert seat.params["diameter"] == pytest.approx(pipe + play)
    assert seat.params["axis"] == (0.0, 1.0, 0.0)
    assert seat.params["centre"] == pytest.approx((0.0, 0.0, centre))
    bolt = produced.features["bore_1"]
    clearance = standards.screw(str(values["screw_size"])).clearance
    assert bolt.params["axis"] == (1.0, 0.0, 0.0)
    assert bolt.params["diameter"] == pytest.approx(clearance)
    assert bolt.params["centre"][2] - clearance / 2.0 > centre + inner + wall - 1e-9
    assert body.bounds.minimum[2] == pytest.approx(0.0, abs=1e-9)

    from app.core.brep import edit

    length = float(values["width"]) + 2.0

    def rod(diameter: float) -> Any:
        upright = edit.moved(edit.cylinder(diameter, length), (0.0, 0.0, -length / 2.0))
        return edit.moved(edit.transformed(upright, _turn_about_x()), (0.0, 0.0, centre))

    assert float(edit.boolean("intersection", [body, rod(pipe)]).volume) == pytest.approx(
        0.0, abs=1e-6
    )
    # Gegenprobe: Dasselbe Rohr eine halbe Wand dicker steckt im Ring.
    assert float(edit.boolean("intersection", [body, rod(pipe + play + wall)]).volume) > 1.0
    mesh = _built("pipe_clamp", False, **values).mesh
    assert abs(mesh.volume / body.volume - 1.0) < 0.005
    assert mesh.is_watertight and mesh.component_count == 1
    _roundtrip(body)


def _turn_about_x() -> Any:
    """Eine Vierteldrehung um X — die Rohrachse liegt in der Schelle entlang Y."""
    from app.core.geom.ops import as_transform
    from app.core.geom.transform import rotation

    return as_transform(rotation("x", 90.0))


def test_a_pipe_clamp_grows_on_an_exact_host_and_stays_exact(profile: Profile) -> None:
    exact_kernel()
    host = _host()
    grown = run("insert_pipe_clamp", host, profile, size="22", **ON_TOP)
    body = _sound(grown.outputs[0].mesh)
    assert grown.outputs[0].kind == "brep"
    assert body.volume > HOST[0] * HOST[1] * HOST[2]
    assert {"pipe_clamp_seat_1", "pipe_clamp_bore_1"} <= set(grown.outputs[0].features)


def test_pegboard_hook_exact_is_two_hooks_without_a_plate_and_one_body_with_it() -> None:
    exact_kernel()
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
    exact_kernel()
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


def test_an_exact_host_reads_its_features_anew_after_a_part(profile: Profile) -> None:
    """Nach einem Baustein trägt der exakte Körper die Merkmale seiner Topologie.

    Bis zur Durchsicht 0.5.1 reichte der Baustein die Merkmale des Trägers
    durch — ohne Dreiecke, weil deren Nummern dem Körper vor dem Schnitt
    gehören, und mit den Maßen von vorher (ERKENNUNG-10). Nach einer
    Magnettasche mitten in der Oberseite hieß die Deckfläche weiter
    10 000 mm² „aus der Konstruktion“, keine Fläche des Trägers ließ sich im
    Bild treffen, und der Boden der Tasche fehlte.

    Der Name des Trägers bleibt, die aktuelle Oberfläche geht mit: dieselben
    Namen, jede mit Dreiecken, die Deckfläche um die Mündung kleiner. Die
    Tasche trägt ihre Dreiecke unter ihrem eigenen Namen und steht nicht ein
    zweites Mal als erkannte Bohrung daneben.
    """
    exact_kernel()
    host = _host()
    outcome = run(
        "insert_magnet_pocket", host, profile, size="8x3", cover=0.0, press_lip=False, **ON_TOP
    )
    (result,) = outcome.outputs
    features = result.features
    assert set(host.features) <= set(features), "die Namen des Trägers bleiben"
    blind = [name for name in host.features if not features[name].face_indices]
    assert not blind, f"ohne Dreiecke, im Bild nicht zu treffen: {blind}"

    top = next(
        name
        for name, feature in host.features.items()
        if feature.kind == "face" and feature.params["normal"][2] > 0.5
    )
    pocket = features["magnet_pocket_pocket_1"]
    assert pocket.face_indices, "die Tasche ist im Bild zu treffen"
    # Ohne Haltelippe ist die Mündung so weit wie die Tasche selbst.
    mouth = math.pi * (float(pocket.params["diameter"]) / 2.0) ** 2
    assert features[top].params["area"] == pytest.approx(HOST[0] * HOST[1] - mouth, rel=1e-9)

    twins = [
        name
        for name, feature in features.items()
        if feature.kind == "hole"
        and name != pocket.id
        and math.dist(feature.params["centre"][:2], pocket.params["centre"][:2]) < 1.0
    ]
    assert not twins, f"die Tasche steht zweimal im Baum: {twins}"
    floor = [
        name
        for name, feature in features.items()
        if name not in host.features
        and feature.kind == "face"
        and feature.params["centre"][2] == pytest.approx(HOST[2] - 3.0, abs=1e-6)
    ]
    assert floor, "der Boden der Tasche ist eine Fläche"


# --- die Profilklemmen: Querschnitte mit zwei Auswertern -----------------------------------------


def _circle_sketch(diameter: float) -> str:
    from app.core.sketch import shapes as sketch_shapes
    from app.core.sketch.serialize import sketch_to_text

    return sketch_to_text(sketch_shapes.circle(diameter))


def _rectangle_sketch(width: float, height: float) -> str:
    from app.core.sketch import shapes as sketch_shapes
    from app.core.sketch.serialize import sketch_to_text

    return sketch_to_text(sketch_shapes.rectangle(width, height))


def test_an_offset_circle_section_stays_a_circle_exactly() -> None:
    """Der Versatz eines Kreises um vier Millimeter ist exakt wieder ein Kreis (Bericht 4.3)."""
    from app.core.knowledge.parts.section import CONTOUR_SAG, Section
    from app.core.sketch.profile import Profile

    exact_kernel()
    with building("brep"):
        seat = Section.of(Profile(circle=((0.0, 0.0), 10.125)))
        outer = seat.offset(4.0)
        ring = _sound(outer.minus(seat).extrude(40.0))
        prism = _sound(outer.extrude(40.0, bottom=1.5))
    assert prism.bounds.maximum[0] == pytest.approx(14.125, abs=1e-9)
    assert prism.bounds.minimum[2] == pytest.approx(1.5, abs=1e-9)
    assert prism.volume == pytest.approx(math.pi * 14.125**2 * 40.0, rel=1e-9)
    assert ring.volume == pytest.approx(math.pi * (14.125**2 - 10.125**2) * 40.0, rel=1e-9)
    assert outer.bounds() == pytest.approx((-14.125, -14.125, 14.125, 14.125), abs=CONTOUR_SAG)
    with building("brep"):
        lower = seat.clipped(Section.rectangle(-50.0, 50.0, -50.0, -0.5))
        assert lower.pieces() == 1
        half = _sound(lower.extrude(40.0))
    assert half.bounds.maximum[1] == pytest.approx(-0.5, abs=1e-9)


def test_profile_clamp_shell_exact_has_cylindrical_seat_ears_and_holes() -> None:
    exact_kernel()
    screw, nut = standards.screw("M4"), standards.nut("M4")
    values = {
        "seat_sketch": _circle_sketch(20.25),
        "depth": 40.0,
        "wall": 4.0,
        "half": "lower",
        "joint_gap": 1.0,
        "split_angle": 0.0,
        "split_offset": 0.0,
        "screw_size": "M4",
        "play": 0.2,
    }
    produced = _built("profile_clamp_shell", True, **values)
    shell = _sound(produced.mesh)
    mesh = _built("profile_clamp_shell", False, **values).mesh
    head = screw.head + 0.2
    nut_across = (nut.width + 0.2) * 2.0 / math.sqrt(3.0)
    ear_width = max(head, nut_across) + 2.0 * 4.0
    ear_height = max(screw.head_height, nut.height) + 4.0 + 0.5
    # Die untere Hälfte endet am halben Teilungsspalt; die Ohren reichen über den Sitz hinaus.
    assert shell.bounds.maximum[1] == pytest.approx(-0.5, abs=1e-9)
    assert shell.bounds.maximum[0] == pytest.approx(14.125 + ear_width - 4.0, abs=1e-9)
    assert shell.bounds.minimum[1] == pytest.approx(-14.125, abs=1e-9)
    assert shell.bounds.minimum[2] == pytest.approx(0.0, abs=1e-9)
    assert shell.bounds.maximum[2] == pytest.approx(40.0, abs=1e-9)
    assert shell.bounds.minimum == pytest.approx(mesh.bounds.minimum, abs=0.02)
    assert shell.bounds.maximum == pytest.approx(mesh.bounds.maximum, abs=0.02)
    # Sitz und Löcher sind am Netz facettiert, der Sitz nach CONTOUR_SAG feiner als 48 Ecken.
    assert abs(mesh.volume / shell.volume - 1.0) < 0.01
    # Ein Ohr ohne Loch wäre um das Loch schwerer: Ø Durchgang mal Ohrhöhe.
    ear_volume_with_holes = shell.volume
    assert ear_volume_with_holes < (
        math.pi * (14.125**2 - 10.125**2) / 2.0 * 40.0 + 2.0 * ear_width * ear_height * 40.0
    )
    for name, height, sign in (("front", 0.0, -1.0), ("back", 40.0, 1.0)):
        feature = produced.features[name]
        assert feature.params["centre"][2] == pytest.approx(height, abs=1e-6)
        assert feature.params["normal"] == (0.0, 0.0, sign)
        assert feature.face_indices
        assert max(feature.face_indices) < shell.triangle_count
    _roundtrip(shell)


def test_profile_clamp_liner_exact_has_its_flange_in_front_and_relief_behind() -> None:
    exact_kernel()
    values = {
        "counter_sketch": _circle_sketch(20.0),
        "outer_sketch": "",
        "depth": 40.0,
        "liner_thickness": 2.0,
        "half": "lower",
        "flange_width": 1.2,
        "flange_height": 1.5,
        "rear_relief": 2.0,
        "split_angle": 0.0,
        "split_offset": 0.0,
        "play": 0.2,
        "grip": 0.1,
    }
    produced = _built("profile_clamp_liner", True, **values)
    liner = _sound(produced.mesh)
    mesh = _built("profile_clamp_liner", False, **values).mesh
    inner = 10.0 - 0.05
    outer = inner + 2.0
    assert liner.bounds.minimum[2] == pytest.approx(0.0, abs=1e-9)
    assert liner.bounds.maximum[2] == pytest.approx(1.5 + 38.0, abs=1e-9)
    assert liner.bounds.minimum[1] == pytest.approx(-(outer + 1.2), abs=1e-9)
    assert liner.bounds.maximum[1] == pytest.approx(-0.1, abs=1e-9)
    # Ein halber Ring plus ein halber Bundring, beide um das Spiel unter der Trennebene —
    # gegen das Netz statt gegen die Analytik, weil die Halbebene beide Ringe schneidet.
    assert abs(mesh.volume / liner.volume - 1.0) < 0.01
    assert liner.bounds.minimum == pytest.approx(mesh.bounds.minimum, abs=0.02)
    assert liner.bounds.maximum == pytest.approx(mesh.bounds.maximum, abs=0.02)
    assert produced.features["front"].params["centre"][2] == pytest.approx(0.0, abs=1e-6)
    assert produced.features["back"].params["centre"][2] == pytest.approx(39.5, abs=1e-6)
    _roundtrip(liner)


def test_a_clamp_shell_grows_on_an_exact_host(profile: Profile) -> None:
    exact_kernel()
    host = _host()
    grown = run(
        "insert_profile_clamp_shell",
        host,
        profile,
        seat_sketch=_circle_sketch(20.25),
        depth=20.0,
        wall=4.0,
        half="lower",
        **ON_TOP,
    )
    body = _sound(grown.outputs[0].mesh)
    assert grown.outputs[0].kind == "brep"
    assert body.volume > HOST[0] * HOST[1] * HOST[2]
    assert {"profile_clamp_shell_front", "profile_clamp_shell_back"} <= set(
        grown.outputs[0].features
    )


# --- Struktur, Kabel und Organizer -------------------------------------------------------------


def _rounded_area(width: float, depth: float, radius: float) -> float:
    """Ein Rechteck mit vier Viertelkreisen an den Ecken."""
    return width * depth - (4.0 - math.pi) * radius**2


def _strip_area(radius: float, half_width: float) -> float:
    """Die Fläche eines Kreises innerhalb ``|x| <= half_width``."""
    return 2.0 * (
        half_width * math.sqrt(radius**2 - half_width**2)
        + radius**2 * math.asin(half_width / radius)
    )


def test_a_rounded_box_is_four_true_quarter_circles_exactly() -> None:
    exact_kernel()
    mesh = shapes.rounded_box(40.0, 30.0, 15.0, 4.0)
    assert isinstance(mesh, MeshData)
    with building("brep"):
        exact = _sound(shapes.rounded_box(40.0, 30.0, 15.0, 4.0))
    assert exact.volume == pytest.approx(_rounded_area(40.0, 30.0, 4.0) * 15.0, rel=1e-9)
    # Vier Ebenen, vier Zylinder, Boden und Deckel.
    assert exact.face_count == 10
    assert exact.bounds.minimum == pytest.approx((-20.0, -15.0, 0.0), abs=1e-9)
    assert exact.bounds.maximum == pytest.approx((20.0, 15.0, 15.0), abs=1e-9)
    assert exact.bounds.minimum == pytest.approx(mesh.bounds.minimum, abs=1e-6)
    assert exact.bounds.maximum == pytest.approx(mesh.bounds.maximum, abs=1e-6)
    # Die Sehnen liegen innerhalb der Bögen: Das Netz ist um die Ecken leichter.
    assert 0.999 < mesh.volume / exact.volume < 1.0
    _roundtrip(exact)


def test_a_fully_rounded_box_is_a_cylinder_without_a_degenerate_edge() -> None:
    exact_kernel()
    with building("brep"):
        exact = _sound(shapes.rounded_box(10.0, 10.0, 4.0, 5.0))
    assert exact.volume == pytest.approx(math.pi * 25.0 * 4.0, rel=1e-9)
    _roundtrip(exact)


def test_rib_exact_is_the_bar_and_two_ramps_of_the_mesh() -> None:
    exact_kernel()
    values = {"length": 20.0, "height": 10.0, "wall": 2.0, "thickness": 0.0, "fillet": 2.0}
    produced = _built("rib", True, **values)
    rib = _sound(produced.mesh)
    mesh = _built("rib", False, **values).mesh
    thickness = max(2.0 * RIB_SHARE, min(2.0, MIN_RIB))
    assert rib.volume == pytest.approx(thickness * (20.0 * 10.0 + 2.0**2), rel=1e-9)
    assert mesh.volume == pytest.approx(rib.volume, rel=1e-9)
    assert rib.bounds.minimum == pytest.approx((-thickness / 2.0, -12.0, 0.0), abs=1e-9)
    assert rib.bounds.maximum == pytest.approx((thickness / 2.0, 12.0, 10.0), abs=1e-9)
    assert produced.features["rib_1"].params["normal"] == (1.0, 0.0, 0.0)
    _roundtrip(rib)


def test_gusset_exact_is_the_same_wedge_as_the_mesh() -> None:
    exact_kernel()
    values = {"legs": 12.0, "thickness": 2.0, "wall": 2.0}
    produced = _built("gusset", True, **values)
    gusset = _sound(produced.mesh)
    mesh = _built("gusset", False, **values).mesh
    assert gusset.volume == pytest.approx(2.0 * 12.0**2 / 2.0, rel=1e-9)
    assert mesh.volume == pytest.approx(gusset.volume, rel=1e-9)
    assert gusset.face_count == 5
    assert gusset.bounds.minimum == pytest.approx((-1.0, 0.0, 0.0), abs=1e-9)
    assert gusset.bounds.maximum == pytest.approx((1.0, 12.0, 12.0), abs=1e-9)
    assert produced.features["gusset_1"].params["centre"] == (0.0, 6.0, 0.0)
    _roundtrip(gusset)


def test_profile_tongue_exact_is_neck_and_tapered_head_from_the_table() -> None:
    exact_kernel()
    entry = standards.profile_slot("2020")
    values = {"size": "2020", "length": 20.0, "lead_in": 1.5, "play": 0.2, "head": 0.0}
    produced = _built("profile_tongue", True, **values)
    tongue = _sound(produced.mesh)
    mesh = _built("profile_tongue", False, **values).mesh
    neck_width, head_width = entry.slot - 0.2, entry.core - 0.2
    neck_height, head_height = entry.lip + 0.2, entry.depth - 0.4
    # Der Kopf: volle Breite in der Mitte, an beiden Enden über die Schräge auf Halsbreite.
    head_area = head_width * (20.0 - 3.0) + (head_width + neck_width) * 1.5
    expected = neck_width * 20.0 * neck_height + head_area * head_height
    assert tongue.volume == pytest.approx(expected, rel=1e-9)
    assert mesh.volume == pytest.approx(expected, rel=1e-9)
    assert tongue.bounds.maximum == pytest.approx(
        (head_width / 2.0, 10.0, neck_height + head_height), abs=1e-9
    )
    feature = produced.features["tongue_1"]
    assert feature.params["normal"] == (0.0, 0.0, -1.0)
    assert feature.params["centre"][2] == pytest.approx(neck_height)
    _roundtrip(tongue)


def test_cable_gland_exact_is_bore_and_relief_channel_under_the_mouth() -> None:
    exact_kernel()
    values = {
        "size": "cable-5",
        "diameter": 0.0,
        "wall": 3.0,
        "play": 0.2,
        "strain_relief": True,
        "relief_gap": 4.0,
    }
    produced = _built("cable_gland", True, **values)
    tool = _sound(produced.mesh)
    mesh = _built("cable_gland", False, **values).mesh
    diameter = standards.tube("cable-5").outer + 0.2
    radius = diameter / 2.0
    bore = math.pi * radius**2 * (3.0 + 2.0 * BOOLEAN_OVERLAP)
    channel = 4.0 * 2.5 * diameter * diameter
    shared = BOOLEAN_OVERLAP * _strip_area(radius, 2.0)
    assert tool.volume == pytest.approx(bore + channel - shared, rel=1e-9)
    # Unter der Mündung: die Bohrung ragt um die Überlappung heraus, der Kanal endet tief.
    assert tool.bounds.maximum[2] == pytest.approx(BOOLEAN_OVERLAP, abs=1e-9)
    assert tool.bounds.minimum[2] == pytest.approx(-3.0 - diameter, abs=1e-9)
    assert tool.bounds.maximum[0] == pytest.approx(radius, abs=1e-9)
    # Nur die Bohrung ist am Netz facettiert.
    assert (mesh.volume - channel) / (tool.volume - channel) == pytest.approx(FACET, rel=1e-3)
    assert produced.features["bore_1"].params["centre"][2] == pytest.approx(-1.5)
    assert produced.features["relief_1"].params["normal"] == (-1.0, 0.0, 0.0)
    _roundtrip(tool)


def test_cable_clip_exact_keeps_exactly_its_wall_and_opens_by_the_grip() -> None:
    exact_kernel()
    values = {
        "size": "cable-5",
        "diameter": 0.0,
        "width": 8.0,
        "wall": 2.0,
        "grip": 0.0,
        "play": 0.2,
    }
    produced = _built("cable_clip", True, **values)
    clip = _sound(produced.mesh)
    mesh = _built("cable_clip", False, **values).mesh
    cable = standards.tube("cable-5").outer
    inner = cable + 0.2
    small, big = inner / 2.0, inner / 2.0 + 2.0
    gap = cable - 2.0 * (cable / 5.0)
    centre = 2.0 + small
    # Exakt ist die Bügelwand genau ``wall``; das Netz trägt die Facettenkorrektur.
    assert clip.bounds.maximum[0] == pytest.approx(big, abs=1e-9)
    assert mesh.bounds.maximum[0] > big + 1e-4
    # Der höchste Punkt ist der Rand der Öffnung, nicht der Scheitel des Bügels.
    assert clip.bounds.maximum[2] == pytest.approx(
        centre + math.sqrt(big**2 - (gap / 2.0) ** 2), abs=1e-9
    )
    ring = math.pi * (big**2 - small**2)
    mouth = (_strip_area(big, gap / 2.0) - _strip_area(small, gap / 2.0)) / 2.0
    # Der Ring taucht bis zur Standfläche in den Sockel: das Kreissegment unter der Sockeloberseite.
    sunk = big**2 * math.acos(small / big) - small * math.sqrt(big**2 - small**2)
    expected = 2.0 * big * 8.0 * 2.0 + (ring - mouth - sunk) * 8.0
    assert clip.volume == pytest.approx(expected, rel=1e-9)
    assert abs(mesh.volume / clip.volume - 1.0) < 0.01
    seat = produced.features["seat_1"]
    assert seat.params["centre"] == (0.0, 0.0, 2.0)
    assert seat.params["normal"] == (0.0, 0.0, 1.0)
    _roundtrip(clip)


def test_organizer_tray_exact_has_eight_cylinder_faces_and_native_face_areas() -> None:
    exact_kernel()
    values = {
        "width": 120.0,
        "depth": 80.0,
        "height": 40.0,
        "wall": 3.0,
        "floor": 3.0,
        "radius": 8.0,
    }
    produced = _built("organizer_tray", True, **values)
    tray = _sound(produced.mesh)
    mesh = _built("organizer_tray", False, **values)
    outer, inner = _rounded_area(120.0, 80.0, 8.0), _rounded_area(114.0, 74.0, 5.0)
    assert tray.volume == pytest.approx(outer * 40.0 - inner * 37.0, rel=1e-9)
    # Außen und innen je vier Ebenen und vier Zylinder, dazu Boden, Bodenfläche und Rand.
    assert tray.face_count == 19
    assert tray.bounds.minimum == pytest.approx((-60.0, -40.0, 0.0), abs=1e-9)
    assert tray.bounds.maximum == pytest.approx((60.0, 40.0, 40.0), abs=1e-9)
    assert abs(mesh.mesh.volume / tray.volume - 1.0) < 1e-3
    features = produced.features
    assert features["base"].params["area"] == pytest.approx(outer, rel=1e-9)
    assert features["floor"].params["area"] == pytest.approx(inner, rel=1e-9)
    assert features["rim"].params["area"] == pytest.approx(outer - inner, rel=1e-9)
    assert features["floor"].params["centre"] == (0, 0, 3.0)
    for name in ("base", "floor", "rim"):
        assert features[name].measure_sources["area"] == "native"
        assert mesh.features[name].measure_sources["area"] == "facets"
    # Das Netz zählt dieselbe Fläche aus Dreiecken — bis auf die Sehnen der Ecken.
    assert mesh.features["rim"].params["area"] == pytest.approx(outer - inner, rel=1e-3)
    _roundtrip(tray)


def test_organizer_divider_exact_is_the_box_of_the_mesh() -> None:
    exact_kernel()
    values = {"length": 30.0, "height": 15.0, "thickness": 3.0}
    produced = _built("organizer_divider", True, **values)
    divider = _sound(produced.mesh)
    assert divider.volume == pytest.approx(30.0 * 3.0 * 15.0, rel=1e-9)
    assert _built("organizer_divider", False, **values).mesh.volume == pytest.approx(
        divider.volume, rel=1e-9
    )
    assert produced.features["front"].params["normal"] == (0, -1, 0)
    _roundtrip(divider)


def test_organizer_rim_exact_stands_on_material_with_its_analytic_volume() -> None:
    exact_kernel()
    values = {"width": 40.0, "depth": 30.0, "height": 3.0, "thickness": 3.0, "radius": 4.0}
    produced = _built("organizer_rim", True, **values)
    rim = _sound(produced.mesh)
    outer, inner = _rounded_area(40.0, 30.0, 4.0), _rounded_area(34.0, 24.0, 1.0)
    assert rim.volume == pytest.approx((outer - inner) * 3.0, rel=1e-9)
    # Um die halbe Tiefe minus die halbe Randbreite nach hinten: der Ursprung liegt auf dem Rand.
    assert rim.bounds.minimum == pytest.approx((-20.0, -28.5, 0.0), abs=1e-9)
    assert rim.bounds.maximum == pytest.approx((20.0, 1.5, 3.0), abs=1e-9)
    feature = produced.features["rim"]
    assert feature.params["area"] == pytest.approx(outer - inner, rel=1e-9)
    assert feature.params["centre"] == (0, 0, 3.0)
    assert feature.measure_sources["area"] == "native"
    _roundtrip(rim)


def test_organizer_foot_exact_is_flange_and_pin_with_native_ring_areas() -> None:
    exact_kernel()
    values = {"diameter": 18.0, "height": 11.0, "pin_diameter": 13.0, "pin_length": 8.0}
    produced = _built("organizer_foot", True, **values)
    foot = _sound(produced.mesh)
    mesh = _built("organizer_foot", False, **values).mesh
    assert foot.volume == pytest.approx(math.pi * (9.0**2 * 11.0 + 6.5**2 * 8.0), rel=1e-9)
    assert mesh.volume / foot.volume == pytest.approx(FACET, rel=1e-9)
    assert foot.bounds.maximum == pytest.approx((9.0, 9.0, 19.0), abs=1e-9)
    features = produced.features
    assert features["base"].params["area"] == pytest.approx(math.pi * 81.0, rel=1e-9)
    assert features["seat"].params["area"] == pytest.approx(math.pi * (81.0 - 6.5**2), rel=1e-9)
    assert features["pin"].params["diameter"] == 13.0
    assert features["pin"].params["centre"] == (0, 0, 15.0)
    _roundtrip(foot)


def test_a_rib_and_a_cable_clip_grow_on_an_exact_host(profile: Profile) -> None:
    exact_kernel()
    host = _host()
    grown = run(
        "insert_rib",
        host,
        profile,
        length=20.0,
        height=10.0,
        wall=2.0,
        thickness=0.0,
        fillet=2.0,
        **ON_TOP,
    )
    body = _sound(grown.outputs[0].mesh)
    assert grown.outputs[0].kind == "brep"
    thickness = max(2.0 * RIB_SHARE, min(2.0, MIN_RIB))
    # Die Rippe sinkt um die Überlappung ein: der Riegel voll, die Rampen verjüngt.
    sunk = thickness * (
        20.0 * BOOLEAN_OVERLAP + 2.0 * (2.0 * BOOLEAN_OVERLAP - BOOLEAN_OVERLAP**2 / 2.0)
    )
    expected = HOST[0] * HOST[1] * HOST[2] + thickness * (20.0 * 10.0 + 4.0) - sunk
    assert body.volume == pytest.approx(expected, rel=1e-9)
    assert "rib_rib_1" in grown.outputs[0].features
    clipped = run(
        "insert_cable_clip",
        host,
        profile,
        size="cable-5",
        diameter=0.0,
        width=8.0,
        wall=2.0,
        grip=0.0,
        **ON_TOP,
    )
    clip = _sound(clipped.outputs[0].mesh)
    assert clipped.outputs[0].kind == "brep"
    assert clip.volume > HOST[0] * HOST[1] * HOST[2]
    assert "cable_clip_seat_1" in clipped.outputs[0].features


def test_a_cable_gland_builds_its_relief_block_behind_an_exact_wall(profile: Profile) -> None:
    exact_kernel()
    wall = 3.0
    host = _host((100.0, 100.0, wall))
    cut = run(
        "insert_cable_gland",
        host,
        profile,
        size="cable-5",
        diameter=0.0,
        wall=wall,
        strain_relief=True,
        relief_gap=4.0,
        x=0.0,
        y=0.0,
        z=wall,
        nx=0.0,
        ny=0.0,
        nz=1.0,
    )
    body = _sound(cut.outputs[0].mesh)
    assert cut.outputs[0].kind == "brep"
    features = cut.outputs[0].features
    diameter = features["cable_gland_bore_1"].params["diameter"]
    radius = diameter / 2.0
    # Der Klemmblock wächst unter der Wand, dann schneiden Bohrung und Kanal.
    support = (diameter + 2.0 * wall) * (2.5 * diameter + 2.0 * wall) * diameter
    bore = math.pi * radius**2 * (wall + BOOLEAN_OVERLAP)
    channel = 4.0 * 2.5 * diameter * diameter
    shared = BOOLEAN_OVERLAP * _strip_area(radius, 2.0)
    expected = 100.0 * 100.0 * wall + support - bore - channel + shared
    assert body.volume == pytest.approx(expected, rel=1e-9)
    assert body.bounds.minimum[2] == pytest.approx(-diameter, abs=1e-9)
    assert body.bounds.maximum[2] == pytest.approx(wall, abs=1e-9)
    assert "cable_gland_relief_1" in features


# --- Dichtungen: Band und Schnur -------------------------------------------------------------


def _band_area(width: float, depth: float, band: float) -> float:
    """Ein Band um ein Rechteck: außen gerundet um die halbe Bandbreite, innen scharf."""
    half = band / 2.0
    outer = (width + band) * (depth + band) - (4.0 - math.pi) * half**2
    return outer - (width - band) * (depth - band)


def _surface_kinds(solid: Any) -> dict[str, int]:
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Sphere, GeomAbs_Torus

    names = {
        GeomAbs_Plane: "plane",
        GeomAbs_Cylinder: "cylinder",
        GeomAbs_Sphere: "sphere",
        GeomAbs_Torus: "torus",
    }
    kinds: dict[str, int] = {}
    for face in solid.faces():
        kind = names.get(BRepAdaptor_Surface(face).GetType(), "other")
        kinds[kind] = kinds.get(kind, 0) + 1
    return kinds


def _cord_volume(perimeter: float, radius: float) -> float:
    """Eine Schnur um ein Rechteck: je Seite ein Zylinder, je Ecke ein Viertel-Steinmetz
    weniger und eine Viertelkugel mehr."""
    return (
        perimeter * math.pi * radius**2
        - 4.0 * (4.0 / 3.0) * radius**3
        + 4.0 * (math.pi / 3.0) * radius**3
    )


def test_seal_groove_exact_is_a_band_with_round_outer_corners_under_the_mouth() -> None:
    exact_kernel()
    values = {
        "path_sketch": _rectangle_sketch(20.0, 12.0),
        "offset": 0.0,
        "width": 3.0,
        "depth": 2.0,
    }
    produced = _built("seal_groove", True, **values)
    tool = _sound(produced.mesh)
    mesh = _built("seal_groove", False, **values)
    ring = _band_area(20.0, 12.0, 3.0)
    assert tool.volume == pytest.approx(ring * (2.0 + BOOLEAN_OVERLAP), rel=1e-9)
    # Außen vier Ebenen und vier Zylinder, innen vier scharfe Ebenen, Mündung und Boden.
    assert tool.face_count == 14
    assert tool.bounds.minimum[2] == pytest.approx(-2.0, abs=1e-9)
    assert tool.bounds.maximum[2] == pytest.approx(BOOLEAN_OVERLAP, abs=1e-9)
    assert tool.bounds.maximum[0] == pytest.approx(11.5, abs=1e-9)
    assert abs(mesh.mesh.volume / tool.volume - 1.0) < 2e-3
    features = produced.features
    for name, height, sign in (
        ("groove_mouth", BOOLEAN_OVERLAP, 1.0),
        ("groove_floor", -2.0, -1.0),
    ):
        feature = features[name]
        assert feature.params["area"] == pytest.approx(ring, rel=1e-9)
        assert feature.measure_sources["area"] == "native"
        assert feature.params["centre"][2] == pytest.approx(height, abs=1e-9)
        assert feature.params["normal"] == (0.0, 0.0, sign)
        assert feature.face_indices and max(feature.face_indices) < tool.triangle_count
        assert mesh.features[name].measure_sources["area"] == "facets"
        assert mesh.features[name].params["area"] == pytest.approx(ring, rel=2e-3)
    assert features["groove_walls"].measure_sources["area"] == "facets"
    _roundtrip(tool)


def test_seal_gasket_exact_rectangle_stands_on_its_base_with_the_band_of_the_groove() -> None:
    exact_kernel()
    values = {
        "path_sketch": _rectangle_sketch(20.0, 12.0),
        "offset": 0.0,
        "section": "rectangle",
        "width": 2.6,
        "height": 2.4,
    }
    produced = _built("seal_gasket", True, **values)
    gasket = _sound(produced.mesh)
    mesh = _built("seal_gasket", False, **values).mesh
    assert gasket.volume == pytest.approx(_band_area(20.0, 12.0, 2.6) * 2.4, rel=1e-9)
    assert gasket.bounds.minimum[2] == pytest.approx(0.0, abs=1e-9)
    assert gasket.bounds.maximum[2] == pytest.approx(2.4, abs=1e-9)
    assert abs(mesh.volume / gasket.volume - 1.0) < 2e-3
    contact = produced.features["gasket_contact"]
    assert contact.params["centre"][2] == pytest.approx(2.4, abs=1e-9)
    assert contact.measure_sources["area"] == "native"
    assert produced.features["gasket_bottom"].params["normal"] == (0.0, 0.0, -1.0)
    _roundtrip(gasket)


def test_seal_gasket_exact_round_is_cylinders_and_sphere_pieces_around_a_rectangle() -> None:
    exact_kernel()
    values = {
        "path_sketch": _rectangle_sketch(20.0, 12.0),
        "offset": 0.0,
        "section": "round",
        "width": 2.6,
        "height": 2.4,
    }
    produced = _built("seal_gasket", True, **values)
    cord = _sound(produced.mesh)
    mesh = _built("seal_gasket", False, **values).mesh
    assert cord.volume == pytest.approx(_cord_volume(64.0, 1.2), rel=1e-9)
    # Vier Zylinder, vier Kugeln an den Ecken — und kein Sehnenzug dazwischen.
    kinds = _surface_kinds(cord)
    assert kinds["cylinder"] == 4 and kinds["sphere"] == 4 and set(kinds) == {"cylinder", "sphere"}
    assert cord.bounds.minimum[2] == pytest.approx(0.0, abs=1e-6)
    assert cord.bounds.maximum[2] == pytest.approx(2.4, abs=1e-6)
    assert cord.bounds.maximum[0] == pytest.approx(11.2, abs=1e-6)
    # Das Netz facettiert Bahn und Kugeln (Bericht Abschnitt 5: 0,988 bis 0,993).
    assert 0.985 < mesh.volume / cord.volume < 1.0
    contact = produced.features["gasket_contact"]
    assert contact.kind == "curved_face"
    assert contact.measure_sources["area"] == "facets"
    assert contact.face_indices and max(contact.face_indices) < cord.triangle_count
    _roundtrip(cord)


def test_seal_gasket_exact_round_on_a_circle_is_one_torus() -> None:
    exact_kernel()
    values = {
        "path_sketch": _circle_sketch(20.0),
        "offset": 0.0,
        "section": "round",
        "width": 2.6,
        "height": 2.4,
    }
    produced = _built("seal_gasket", True, **values)
    ring = _sound(produced.mesh)
    mesh = _built("seal_gasket", False, **values).mesh
    assert ring.face_count == 1 and _surface_kinds(ring) == {"torus": 1}
    assert ring.volume == pytest.approx(2.0 * math.pi**2 * 10.0 * 1.2**2, rel=1e-9)
    assert ring.bounds.maximum[0] == pytest.approx(11.2, abs=1e-6)
    assert 0.98 < mesh.volume / ring.volume < 1.0
    _roundtrip(ring)


def test_a_seal_groove_cuts_an_exact_host_and_a_gasket_lies_loose_beside_it(
    profile: Profile,
) -> None:
    exact_kernel()
    host = _host()
    sketch = _rectangle_sketch(20.0, 12.0)
    cut = run(
        "insert_seal_groove",
        host,
        profile,
        path_sketch=sketch,
        offset=0.0,
        width=3.0,
        depth=2.0,
        **ON_TOP,
    )
    body = _sound(cut.outputs[0].mesh)
    assert cut.outputs[0].kind == "brep"
    assert body.volume == pytest.approx(
        HOST[0] * HOST[1] * HOST[2] - _band_area(20.0, 12.0, 3.0) * 2.0, rel=1e-9
    )
    assert "seal_groove_groove_floor" in cut.outputs[0].features
    loose = run(
        "insert_seal_gasket",
        host,
        profile,
        path_sketch=sketch,
        offset=0.0,
        section="round",
        width=2.6,
        height=2.4,
        **ON_TOP,
    )
    pair = _sound(loose.outputs[0].mesh, bodies=2)
    assert loose.outputs[0].kind == "brep"
    assert pair.volume == pytest.approx(
        HOST[0] * HOST[1] * HOST[2] + _cord_volume(64.0, 1.2), rel=1e-9
    )
    assert "seal_gasket_gasket_contact" in loose.outputs[0].features


# --- Kalibrierung ------------------------------------------------------------------------------


def _ladder_layout(
    diameter: float, steps: int, first: float, step: float
) -> tuple[float, float, float]:
    """Breite, Leistentiefe und Abstand der Toleranzleiter — wie im Baustein."""
    largest = diameter + first + step * (steps - 1)
    spacing = max(diameter * 2.2, largest * 1.5, steps * 1.4 + 2.8)
    return spacing * steps + spacing, max(spacing, largest + 8.0), spacing


def _ladder_volume(diameter: float, steps: int, first: float, step: float, height: float) -> float:
    width, rail_depth, _ = _ladder_layout(diameter, steps, first, step)
    rails = 2.0 * width * rail_depth * 3.0
    studs = steps * math.pi * (diameter / 2.0) ** 2 * height
    holes = sum(
        math.pi * ((diameter + first + step * index) / 2.0) ** 2 * 3.0 for index in range(steps)
    )
    bars = 2.0 * sum(range(1, steps + 1)) * 0.8 * 3.0 * LABEL_DEPTH
    return rails + studs - holes - bars


def test_fit_ladder_exact_is_two_rails_with_staggered_bores_and_engraved_bars() -> None:
    exact_kernel()
    values = {"diameter": 6.0, "steps": 4, "first": 0.10, "step": 0.05, "height": 6.0}
    produced = _built("fit_ladder", True, **values)
    ladder = _sound(produced.mesh, bodies=2)
    mesh = _built("fit_ladder", False, **values).mesh
    assert ladder.volume == pytest.approx(_ladder_volume(6.0, 4, 0.10, 0.05, 6.0), rel=1e-9)
    assert abs(mesh.volume / ladder.volume - 1.0) < 5e-3
    width, _, _ = _ladder_layout(6.0, 4, 0.10, 0.05)
    assert ladder.bounds.maximum[2] == pytest.approx(9.0, abs=1e-9)
    assert ladder.bounds.maximum[0] == pytest.approx(width / 2.0, abs=1e-9)
    for index in range(4):
        bore = produced.features[f"bore_{index + 1}"]
        assert bore.params["diameter"] == pytest.approx(6.0 + 0.10 + 0.05 * index)
        assert produced.features[f"pin_{index + 1}"].params["diameter"] == 6.0
    _roundtrip(ladder)


def test_wall_ladder_exact_is_the_box_row_of_the_mesh() -> None:
    exact_kernel()
    values = {"extrusion": 0.42, "steps": 6, "height": 15.0, "length": 25.0}
    produced = _built("wall_ladder", True, **values)
    ladder = _sound(produced.mesh)
    mesh = _built("wall_ladder", False, **values).mesh
    thicknesses = [0.42 * (index + 1) for index in range(6)]
    width = sum(thicknesses) + 0.42 * 6.0 * 7
    expected = width * 25.0 * 2.0 + sum(thicknesses) * 25.0 * 15.0
    assert ladder.volume == pytest.approx(expected, rel=1e-9)
    assert mesh.volume == pytest.approx(expected, rel=1e-9)
    assert ladder.bounds.maximum[2] == pytest.approx(17.0, abs=1e-9)
    # Die freie Oberseite des Sockels in der ersten Lücke, nicht unter einer Wand.
    assert produced.features["face_1"].params["centre"] == pytest.approx(
        (-width / 2.0 + 0.42 * 3.0, 0.0, 2.0)
    )
    _roundtrip(ladder)


def test_overhang_fan_exact_leans_its_ramps_like_the_mesh() -> None:
    exact_kernel()
    values = {"first": 20.0, "step": 10.0, "steps": 3, "width": 8.0, "length": 15.0}
    produced = _built("overhang_fan", True, **values)
    fan = _sound(produced.mesh)
    mesh = _built("overhang_fan", False, **values).mesh
    expected = 24.0 * 6.0 * 3.0
    for index in range(3):
        angle = math.radians(20.0 + 10.0 * index)
        reach, rise = 15.0 * math.sin(angle), 15.0 * math.cos(angle)
        # Die Rampe beginnt um die Überlappung im Sockel; dort ist sie noch schmal.
        expected += 8.0 * (reach * rise / 2.0 - reach * BOOLEAN_OVERLAP**2 / (2.0 * rise))
    assert fan.volume == pytest.approx(expected, rel=1e-9)
    assert mesh.volume == pytest.approx(expected, rel=1e-9)
    # Die letzte Rampe lehnt am weitesten hinaus.
    assert fan.bounds.maximum[1] == pytest.approx(
        2.0 + 15.0 * math.sin(math.radians(40.0)), abs=1e-9
    )
    assert fan.bounds.maximum[2] == pytest.approx(
        3.0 - BOOLEAN_OVERLAP + 15.0 * math.cos(math.radians(20.0)), abs=1e-9
    )
    _roundtrip(fan)


def test_a_fit_ladder_grows_on_an_exact_host_as_one_body(profile: Profile) -> None:
    exact_kernel()
    host = _host()
    grown = run(
        "insert_fit_ladder",
        host,
        profile,
        diameter=6.0,
        steps=4,
        first=0.10,
        step=0.05,
        height=6.0,
        **ON_TOP,
    )
    body = _sound(grown.outputs[0].mesh)
    assert grown.outputs[0].kind == "brep"
    width, rail_depth, _ = _ladder_layout(6.0, 4, 0.10, 0.05)
    # Eingesunken sind beide Leisten — ohne die Bohrungen, die der Träger wieder füllt.
    holes = sum(math.pi * ((6.0 + 0.10 + 0.05 * index) / 2.0) ** 2 for index in range(4))
    sunk = (2.0 * width * rail_depth - holes) * BOOLEAN_OVERLAP
    assert body.volume == pytest.approx(
        HOST[0] * HOST[1] * HOST[2] + _ladder_volume(6.0, 4, 0.10, 0.05, 6.0) - sunk, rel=1e-9
    )
    assert {"fit_ladder_pin_1", "fit_ladder_bore_4"} <= set(grown.outputs[0].features)


# --- Halter (RM-399) ----------------------------------------------------------------


def _clipped(form: Any, low: tuple[float, float, float], high: tuple[float, float, float]) -> Any:
    """Was von einer exakten Form zwischen zwei Ecken liegt — ein Quader als Schnitt."""
    box = shapes.box(high[0] - low[0], high[1] - low[1], high[2] - low[2])
    window = shapes.moved(box, ((low[0] + high[0]) / 2.0, (low[1] + high[1]) / 2.0, low[2]))
    return build.intersect(form, window)


def _against_mesh(name: str, body: Any, values: dict[str, object]) -> None:
    """Das Netz unterscheidet sich nur um die Sehnen seiner Rundungen."""
    mesh = _built(name, False, **values).mesh
    assert mesh.is_watertight and mesh.component_count == 1
    assert mesh.volume / body.volume == pytest.approx(1.0, abs=2e-3)


def test_holder_u_exact_with_keyholes_is_box_minus_room_minus_two_keyholes() -> None:
    """U-Halter mit Schlüsselloch: Rückwand und Wände analytisch, die Löcher vom Baustein.

    Abgezogen wird je Schlüsselloch genau das Werkzeug des Bausteins
    ``keyhole`` unter seiner Mündung — das Haar darüber liegt hinter der Wand
    in der Luft.
    """
    exact_kernel()
    from app.core.knowledge.parts import holders
    from app.core.knowledge.parts.mounting import HEAD_CLEARANCE

    values: dict[str, object] = {
        "width": 40.0,
        "depth": 30.0,
        "height": 40.0,
        "mount": "keyhole",
        "floor": False,
        "wall": 3.0,
        "play": 0.2,
    }
    produced = _built("holder_u", True, **values)
    body = _sound(produced.mesh)
    keyhole = holders.KEYHOLE
    inner_width, inner_depth, wall, height = 40.2, 30.2, 3.0, 40.0
    outer_width, outer_depth = inner_width + 2.0 * wall, inner_depth + wall
    thickness = wall + keyhole.depth
    across = standards.screw(keyhole.size).head + HEAD_CLEARANCE + 0.2
    plate_width = max(outer_width, 2.0 * across + 3.0 * wall)
    plate_height = max(height, across + keyhole.drop + 2.0 * wall)
    with building("brep"):
        tool = PARTS.get("keyhole").fn(PARTS.get("keyhole").params(size=keyhole.size, play=0.2))
        below = _clipped(build.form_of(tool), (-50.0, -50.0, -50.0), (50.0, 50.0, 0.0))
    expected = (
        plate_width * thickness * plate_height
        + outer_width * outer_depth * height
        - inner_width * inner_depth * height
        - 2.0 * below.volume
    )
    assert body.volume == pytest.approx(expected, rel=1e-9)
    assert body.bounds.size == pytest.approx((plate_width, thickness + outer_depth, plate_height))
    _against_mesh("holder_u", body, values)
    _roundtrip(body)


def test_holder_shelf_exact_with_screws_is_plate_brace_and_two_countersunk_holes() -> None:
    """L-Halter mit Schraublöchern: Rückwand, Ablage mit 45-Grad-Stütze, zwei Senkungen.

    Die Stütze unter der Ablage ist ein Dreieck plus der Streifen der Ablage,
    ``front²/2 + Wand · front`` je Millimeter Breite. Jedes Loch ist ein
    Kegelstumpf unter 45 Grad von der Vorderseite bis zum Bohrdurchmesser und
    die Bohrung durch den Rest der Lasche.
    """
    exact_kernel()
    from app.core.knowledge.parts import holders

    values: dict[str, object] = {
        "width": 60.0,
        "depth": 40.0,
        "height": 50.0,
        "lip": 0.0,
        "mount": "screws",
        "wall": 3.0,
        "play": 0.2,
    }
    produced = _built("holder_shelf", True, **values)
    body = _sound(produced.mesh)
    screw = standards.screw(holders.SCREW_SIZE)
    wall, inner_width, front = 3.0, 60.2, 40.2
    sink = (screw.countersink - screw.clearance) / 2.0
    thickness = wall + sink
    plate_width = inner_width + 2.0 * (screw.countersink + 2.0 * wall)
    plate_height = 50.0
    hole = _frustum(
        screw.clearance, screw.clearance + 2.0 * (sink - BOOLEAN_OVERLAP), sink - BOOLEAN_OVERLAP
    ) + math.pi * (screw.clearance / 2.0) ** 2 * (thickness - sink + BOOLEAN_OVERLAP)
    expected = (
        plate_width * thickness * plate_height
        + inner_width * (front**2 / 2.0 + wall * front)
        - 2.0 * hole
    )
    assert body.volume == pytest.approx(expected, rel=1e-9)
    assert body.bounds.size == pytest.approx((plate_width, thickness + front, plate_height))
    assert {"plate_1", "shelf_1", "bore_1", "bore_2"} == set(produced.features)
    _against_mesh("holder_shelf", body, values)
    _roundtrip(body)


def test_holder_fork_exact_with_pegboard_hooks_is_plate_prongs_and_the_hooks_behind() -> None:
    """Gabel mit rundem Grund und Lochwand-Haken: vor der Rückseite analytisch, dahinter die Haken.

    Vor der Rückseite der Rückwand liegen Rückwand und Block mit dem
    halbrunden Langloch. Dahinter liegt genau, was der Baustein
    ``pegboard_hook`` jenseits des Hundertstels baut, um das er in die
    Rückwand sinkt.
    """
    exact_kernel()
    from app.core.knowledge.parts import holders

    values: dict[str, object] = {
        "width": 25.0,
        "depth": 25.0,
        "height": 15.0,
        "mount": "pegboard",
        "wall": 4.0,
        "play": 0.2,
    }
    produced = _built("holder_fork", True, **values)
    body = _sound(produced.mesh)
    wall, height, radius, reach = 4.0, 15.0, 12.6, 25.2
    outer_width = 2.0 * (radius + wall)
    hook_spec = PARTS.get("pegboard_hook")
    with building("brep"):
        hooks = build.form_of(
            hook_spec.fn(
                hook_spec.params(
                    system=holders.HOOKS.system,
                    count=holders.HOOKS.count,
                    steps=holders.HOOKS.steps,
                    upright=holders.HOOKS.upright,
                    latch=holders.HOOKS.latch,
                    plate=holders.HOOKS.plate,
                    lip=holders.HOOKS.lip,
                    play=0.2,
                )
            )
        )
        behind = _clipped(hooks, (-200.0, -200.0, BOOLEAN_OVERLAP), (200.0, 200.0, 200.0))
        size = hooks.bounds.size
        plate_width = max(outer_width, size[0] + 2.0 * wall)
        plate_height = max(height, size[1] + 2.0 * wall)
        front_part = _clipped(body, (-200.0, -wall, -1.0), (200.0, 200.0, 200.0))
        back_part = _clipped(body, (-200.0, -200.0, -1.0), (200.0, -wall, 200.0))
    seat = math.pi * radius**2 / 2.0 + 2.0 * radius * (reach - radius)
    assert front_part.volume == pytest.approx(
        plate_width * wall * plate_height + height * (outer_width * reach - seat), rel=1e-9
    )
    assert back_part.volume == pytest.approx(behind.volume, rel=1e-9)
    assert body.volume == pytest.approx(front_part.volume + back_part.volume, rel=1e-9)
    assert {"hook_1", "hook_2", "latch_1", "latch_2", "prong_1", "prong_2"} <= set(
        produced.features
    )
    _against_mesh("holder_fork", body, values)
    _roundtrip(body)


def test_holder_ring_exact_with_a_clamp_is_a_ring_on_the_plate_and_a_clip_behind() -> None:
    """Becher mit Klemme: ganz analytisch, der Ring taucht eine halbe Wand in die Rückwand."""
    exact_kernel()
    from app.core.knowledge.parts import holders

    values: dict[str, object] = {
        "diameter": 70.0,
        "height": 40.0,
        "mount": "clamp",
        "board": 18.0,
        "floor": True,
        "wall": 3.0,
        "play": 0.2,
    }
    produced = _built("holder_ring", True, **values)
    body = _sound(produced.mesh)
    wall, height, board = 3.0, 40.0, 18.0
    inner = 35.1
    outer = inner + wall
    centre = holders.ring_centre(70.0, 0.2, wall)
    plate_width = 2.0 * outer
    # Der Kreisabschnitt, mit dem der Ring hinter die Vorderseite der Rückwand taucht.
    segment = outer**2 * math.acos(centre / outer) - centre * math.sqrt(outer**2 - centre**2)
    expected = (
        plate_width * wall * height
        + height * (math.pi * outer**2 - segment)
        - math.pi * inner**2 * (height - wall)
        + plate_width * wall * (board + height)
    )
    assert body.volume == pytest.approx(expected, rel=1e-9)
    assert body.bounds.size == pytest.approx(
        (plate_width, wall + board + wall + centre + outer, height)
    )
    assert produced.features["seat_1"].params["through"] is False
    _against_mesh("holder_ring", body, values)
    _roundtrip(body)


@pytest.mark.parametrize("name", ["holder_u", "holder_ring", "holder_fork", "holder_shelf"])
def test_the_holder_creator_builds_the_exact_holder_where_the_kernel_is_there(
    name: str, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Kundenweg erreicht den exakten Halter (RM-443), wie ein Grundkörper.

    Katalog, Agent und Kommandozeile setzen einen Halter über ``create_…``.
    Dieser Erzeuger baute bis hierher immer im Netzkern; die exakte Fassung
    gab es nur in den Tests oben. Jetzt entsteht eine Vorlage wie ein
    Grundkörper exakt, wo der Kern da ist — mit denselben Maßen und Merkmalen
    wie das Netz —, und als Netz, wo er fehlt.
    """
    exact_kernel()
    from app.core.geom.mesh import as_mesh_data
    from app.core.knowledge.parts import ops as part_ops

    builtin.load()
    first = "diameter" if name == "holder_ring" else "width"
    values: dict[str, object] = {first: 30.0, "height": 40.0, "mount": "screws"}
    exact = run(f"create_{name}", None, profile, **values)
    (body,) = exact.outputs
    assert body.kind == "brep", "wo der Kern da ist, entsteht der Halter exakt"
    solid = _sound(body.mesh)
    assert f"{name}_plate_1" in body.features
    monkeypatch.setattr(part_ops, "_exact_kernel_here", lambda: False)
    meshed = run(f"create_{name}", None, profile, **values)
    (twin,) = meshed.outputs
    assert twin.kind == "mesh", "ohne den Kern bleibt der Netzweg"
    mesh = as_mesh_data(twin.mesh)
    assert mesh.is_watertight and mesh.component_count == 1
    # Rund ist das Netz ein Sehnenzug, der höchstens ``MAX_FACET_SAG`` innen liegt.
    assert solid.bounds.size == pytest.approx(mesh.bounds.size, abs=MAX_FACET_SAG)
    # Das Volumen weicht höchstens um den Sehnenabstand über die Oberfläche ab.
    assert abs(mesh.volume - solid.volume) <= MAX_FACET_SAG * float(mesh.raw.area)
    declared = {key for key in twin.features if key.startswith(name)}
    assert declared and declared <= set(body.features), "dieselben erklärten Merkmale"


def test_a_part_creator_that_is_no_template_stays_on_the_mesh(profile: Profile) -> None:
    """Nur die Vorlagen entstehen exakt; die übrigen Erzeuger bleiben, wie sie waren.

    Ein Prüfkörper oder eine Organizerschale ist kein Anfang einer Konstruktion
    wie ein Grundkörper oder Halter, und ihr gespeicherter Schritt rechnet
    weiter genau so wie in 0.5.1.
    """
    exact_kernel()
    builtin.load()
    outcome = run("create_fit_ladder", None, profile)
    assert outcome.outputs[0].kind == "mesh"


# --- RM-184: Bausteine aus dem Dateiaudit ---------------------------------------------


def _pappus(outline: list[tuple[float, float]]) -> float:
    """Volumen eines um Z gedrehten geschlossenen Umrisses (x = Radius) nach Pappus."""
    area = moment = 0.0
    for (x0, y0), (x1, y1) in zip(outline, [*outline[1:], outline[0]], strict=True):
        cross = x0 * y1 - x1 * y0
        area += cross
        moment += (x0 + x1) * cross
    area /= 2.0
    centroid = moment / (6.0 * area)
    return 2.0 * math.pi * abs(area) * abs(centroid)


@pytest.mark.parametrize("screw", ["none", "M4"])
@pytest.mark.parametrize("layout", ["sleeve", "tee", "corner_3d"])
def test_rod_connector_exact_matches_its_analytic_volume(layout: str, screw: str) -> None:
    """Stangenverbinder am exakten Kern: Knoten, Aufnahmen und Bohrungen analytisch.

    Ohne Klemmschraube ist das Volumen geschlossen rechenbar: Knotenwürfel und
    die Aufnahmen außerhalb von ihm, weniger die runden Bohrungen ab dem
    Anschlag. Mit Schraube bleibt das Netz der Vergleich.
    """
    exact_kernel()
    from app.core.knowledge.parts.rods import ROD_LAYOUTS

    values: dict[str, object] = {
        "layout": layout,
        "rod": 16.0,
        "depth": 30.0,
        "wall": 3.0,
        "screw": screw,
        "play": 0.25,
    }
    produced = _built("rod_connector", True, **values)
    body = _sound(produced.mesh)
    bore_radius = (16.0 + 0.25) / 2.0
    outer = 2.0 * bore_radius + 6.0
    sockets = len(ROD_LAYOUTS[layout])
    if layout == "sleeve":
        expected = outer * outer * (3.0 + 30.0) - math.pi * bore_radius**2 * 30.0
    else:
        hub = bore_radius + 4.5
        expected = (2.0 * hub) ** 3 + sockets * (
            30.0 * outer * outer - math.pi * bore_radius**2 * 30.0
        )
    if screw == "none":
        assert body.volume == pytest.approx(expected, rel=1e-9)
    else:
        assert body.volume < expected
    assert {f"socket_{index}" for index in range(1, sockets + 1)} <= set(produced.features)
    assert body.bounds.minimum[2] == pytest.approx(0.0, abs=1e-9)
    mesh = _built("rod_connector", False, **values).mesh
    assert mesh.is_watertight and mesh.component_count == 1
    assert abs(mesh.volume - body.volume) <= 0.003 * body.volume
    _roundtrip(body)


def test_a_rod_sleeve_grows_on_an_exact_host_and_stays_exact(profile: Profile) -> None:
    exact_kernel()
    grown = run(
        "insert_rod_connector", _host(), profile, layout="sleeve", rod=16.0, depth=20.0, **ON_TOP
    )
    body = _sound(grown.outputs[0].mesh)
    assert grown.outputs[0].kind == "brep"
    assert body.volume > HOST[0] * HOST[1] * HOST[2]
    assert {"rod_connector_socket_1", "rod_connector_stop_1"} <= set(grown.outputs[0].features)


@pytest.mark.parametrize("name", ["rod_connector", "room_floor", "room_wall", "room_pane"])
def test_the_rm184_templates_are_created_exactly_where_the_kernel_is_there(
    name: str, profile: Profile
) -> None:
    """Stangenverbinder und Raumplatten sind Vorlagen und entstehen wie ein Grundkörper exakt."""
    exact_kernel()
    builtin.load()
    outcome = run(f"create_{name}", None, profile)
    (body,) = outcome.outputs
    assert body.kind == "brep"
    _sound(body.mesh)


def test_hose_barb_exact_body_and_passage_match_their_analytic_volumes() -> None:
    """Schlauchtülle exakt: der Drehkörper nach Pappus, weniger der Durchgang."""
    exact_kernel()
    from app.core.knowledge.parts.channels import hose_barb_outline

    values: dict[str, object] = {
        "hose": 30.0,
        "grip": 1.5,
        "count": 4,
        "length": 35.0,
        "wall": 3.0,
        "collar": 3.0,
        "through": 4.0,
    }
    builtin.load()
    spec = PARTS.get("hose_barb")
    params = spec.params(**values)
    with building("brep"):
        body = _sound(spec.host_add(params).mesh)
        cutter = _sound(spec.fn(params).mesh)
    passage = 24.0 / 2.0
    expected = _pappus(list(hose_barb_outline(params))) - math.pi * passage**2 * (
        3.0 + 35.0 + BOOLEAN_OVERLAP
    )
    assert body.volume == pytest.approx(expected, rel=1e-9)
    assert cutter.volume == pytest.approx(
        math.pi * passage**2 * (4.0 + 2.0 * BOOLEAN_OVERLAP), rel=1e-9
    )
    _roundtrip(body)


def test_a_hose_barb_grows_on_an_exact_host_with_its_passage_through(profile: Profile) -> None:
    """Auf einem exakten Träger: Tülle aufgebaut, Durchgang durch die ganze Wand, exakt."""
    exact_kernel()
    host = _host()
    grown = run(
        "insert_hose_barb",
        host,
        profile,
        hose=12.0,
        grip=1.0,
        count=3,
        length=24.0,
        wall=1.5,
        collar=3.0,
        through=HOST[2],
        **ON_TOP,
    )
    body = _sound(grown.outputs[0].mesh)
    assert grown.outputs[0].kind == "brep"
    from app.core.brep import edit

    probe = edit.moved(edit.cylinder(8.8, 40.0), (0.0, 0.0, -1.0))
    assert float(edit.boolean("intersection", [body, probe]).volume) == pytest.approx(0.0, abs=1e-6)
    assert "hose_barb_passage_1" in grown.outputs[0].features


def test_channel_joint_exact_outside_is_box_minus_pockets_and_channel() -> None:
    exact_kernel()
    values: dict[str, object] = {
        "style": "outer_sleeve",
        "width": 44.0,
        "height": 27.0,
        "wall": 2.0,
        "overlap": 18.0,
        "thickness": 1.2,
        "play": 0.25,
    }
    produced = _built("channel_joint", True, **values)
    body = _sound(produced.mesh)
    inner = 44.25
    outer = inner + 2.4
    length = 2.0 * 18.0 + 1.2
    expected = (
        length * outer * (1.2 + 27.0)
        - 2.0 * 18.0 * inner * 27.0
        - 1.2 * (44.0 - 4.0) * (27.0 - 2.0)
    )
    assert body.volume == pytest.approx(expected, rel=1e-9)
    mesh = _built("channel_joint", False, **values).mesh
    assert mesh.volume == pytest.approx(body.volume, rel=1e-9)
    _roundtrip(body)


def test_channel_joint_exact_inside_matches_the_mesh() -> None:
    exact_kernel()
    values: dict[str, object] = {"style": "inner_insert", "ramp": 8.0, "play": 0.25}
    body = _sound(_built("channel_joint", True, **values).mesh)
    mesh = _built("channel_joint", False, **values).mesh
    assert mesh.volume == pytest.approx(body.volume, rel=1e-9)
    _roundtrip(body)


@pytest.mark.parametrize("kind", ["socket", "plug"])
def test_bayonet_exact_matches_its_analytic_volume(kind: str) -> None:
    """Bajonett exakt: Ring, Einführschlitze als Kreisstreifen, Drehschlitze als Sektoren."""
    exact_kernel()
    from app.core.knowledge.parts.closures import bayonet_frame

    values: dict[str, object] = {
        "kind": kind,
        "diameter": 75.0,
        "wall": 2.0,
        "lugs": 3,
        "lug_width": 6.0,
        "lug_height": 3.5,
        "entry": 6.0,
        "turn": 13.0,
        "play": 0.25,
    }
    produced = _built("bayonet", True, **values)
    body = _sound(produced.mesh)
    builtin.load()
    frame = bayonet_frame(PARTS.get("bayonet").params(**values))
    if kind == "socket":
        inner, outer, rim = frame["bore"], frame["outer"], frame["rim"]
        slot = frame["slot_top"] - frame["slot_bottom"]
        sweep = math.radians(13.0 + 2.0 * frame["margin"])
        half = (6.0 + 0.25) / 2.0
        expected = math.pi * (outer**2 - inner**2) * rim - 3.0 * (
            sweep / 2.0 * (outer**2 - inner**2) * slot
            + (_strip(outer, half) - _strip(inner, half)) * (rim - frame["slot_top"])
        )
    else:
        radius = 37.5
        near = radius - 1.0
        half = 3.0
        lug = 6.0 * (frame["outer"] - near) - (_strip(radius, half) - 2.0 * half * near)
        expected = math.pi * (radius**2 - (radius - 2.0) ** 2) * frame["collar"] + 3.0 * lug * 3.5
    assert body.volume == pytest.approx(expected, rel=1e-9)
    _roundtrip(body)


@pytest.mark.parametrize("kind", ["base", "disc"])
def test_detent_disc_exact_is_sound_and_matches_the_mesh(kind: str) -> None:
    """Rastdrehscheibe exakt: gültig, ein Körper, und das Netz weicht nur um seine Sehnen ab."""
    exact_kernel()
    values: dict[str, object] = {"kind": kind, "play": 0.25}
    produced = _built("detent_disc", True, **values)
    body = _sound(produced.mesh)
    mesh = _built("detent_disc", False, **values).mesh
    assert mesh.is_watertight and mesh.component_count == 1
    sag = 25.0 * (1.0 - math.cos(math.pi / shapes.SEGMENTS))
    assert abs(mesh.volume - body.volume) <= sag * float(mesh.raw.area)
    assert set(produced.features) == set(_built("detent_disc", False, **values).features)
    _roundtrip(body)


@pytest.mark.parametrize(
    ("name", "values", "expected"),
    [
        (
            "room_floor",
            {"length": 120.0, "depth": 90.0, "thickness": 4.0, "wall": 4.0, "play": 0.25},
            # Platte mit einer Wand Überstand hinten und seitlich, weniger der hinteren
            # Nut über die ganze Breite und der zwei seitlichen bis an sie heran.
            128.0 * 94.0 * 4.0 - 2.0 * (128.0 * 2.25 + 2.0 * 2.25 * (88.0 - 2.25 / 2.0)),
        ),
        (
            "room_pane",
            {"opening_width": 100.0, "opening_height": 120.0, "wall": 4.0, "play": 0.25},
            (100.0 + 8.0 - 0.25) * (120.0 + 8.0 - 0.25) * 2.0,
        ),
    ],
)
def test_room_panels_exact_are_boxes_minus_their_grooves(
    name: str, values: dict[str, object], expected: float
) -> None:
    exact_kernel()
    produced = _built(name, True, **values)
    body = _sound(produced.mesh)
    mesh = _built(name, False, **values).mesh
    assert mesh.volume == pytest.approx(body.volume, rel=1e-9)
    assert body.volume == pytest.approx(expected, rel=1e-9)
    _roundtrip(body)


def test_room_wall_exact_matches_its_mesh_with_door_and_window() -> None:
    exact_kernel()
    for values in (
        {"role": "room_back", "opening": "window", "opening_width": 100.0, "play": 0.25},
        {
            "role": "room_side",
            "opening": "door",
            "opening_width": 90.0,
            "opening_height": 200.0,
            "play": 0.25,
        },
    ):
        body = _sound(_built("room_wall", True, **values).mesh)
        mesh = _built("room_wall", False, **values).mesh
        assert mesh.volume == pytest.approx(body.volume, rel=1e-9)
        _roundtrip(body)
