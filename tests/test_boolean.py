"""Die Boolesche Rückfallkette (Bauplan §17.2, §35).

Jede Stufe wird einmal erzwungen, damit keine von ihnen still verrottet: die
Kette lohnt nur, wenn Stufe 4 an dem Tag noch funktioniert, an dem Stufe 1
aufgibt.
"""

from __future__ import annotations

import math
import time
import warnings
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import BooleanFailedError, GeometryError, OperationCancelled
from app.core.geom import lathe
from app.core.geom.attributes import used_slots, with_slot
from app.core.geom.boolean import (
    CROSSING_SHELL_IN_THE_WAY,
    DRAFT_CHAIN,
    FULL_CHAIN,
    BooleanKind,
    boolean,
    shared_volume,
)
from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest.loader import normalise
from app.core.knowledge import profiles
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import Feature, MaterialSlot, OpContext, OpResult, Scene, SceneObject
from tests.helpers import two_cubes

MESHES = Path(__file__).parent / "data" / "meshes"


def solid(name: str = "cube_clean.stl") -> MeshData:
    return normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh


def box(size: float, offset: tuple[float, float, float]) -> MeshData:
    body = trimesh.creation.box(extents=(size, size, size))
    body.apply_translation(offset)
    return MeshData.of(body)


def crossing_shell_with_overlapping_part() -> MeshData:
    """Eine geschlossene Eigenkreuzung plus ein zweites, sie schneidendes Teil."""
    shell = trimesh.creation.box(extents=(20.0, 20.0, 20.0)).subdivide()
    corners = np.asarray(shell.vertices).copy()
    top = np.flatnonzero(np.all(np.abs(corners - 10.0) < 1e-9, axis=1))
    assert len(top) == 1
    corners[top[0]] = (0.0, 0.0, -18.0)
    shell = trimesh.Trimesh(vertices=corners, faces=shell.faces.copy(), process=False)
    part = trimesh.creation.box(extents=(4.0, 4.0, 4.0))
    part.apply_translation((8.0, 0.0, 0.0))
    return MeshData.of(trimesh.util.concatenate([shell, part]))


def _crossing_shell(at: tuple[float, float, float]) -> trimesh.Trimesh:
    """Eine geschlossene Schale, die sich selbst kreuzt: ein Würfel 20, eine Ecke durchgezogen."""
    shell = trimesh.creation.box(extents=(20.0, 20.0, 20.0)).subdivide()
    corners = np.asarray(shell.vertices).copy()
    top = np.flatnonzero(np.all(np.abs(corners - 10.0) < 1e-9, axis=1))
    assert len(top) == 1
    corners[top[0]] = (0.0, 0.0, -18.0)
    shell = trimesh.Trimesh(vertices=corners, faces=shell.faces.copy(), process=False)
    shell.apply_translation(at)
    return shell


def laptop_twin() -> MeshData:
    """Der Laptop-Ständer im Kleinen (RM-382): zwei Würfel 10, die einander durchdringen,
    und abseits eine Schale, die sich selbst kreuzt.

    Vereinigen lassen sich die Teile deshalb nicht (``repair.self_crossing``),
    und die Kette rechnet mit ihnen, wie sie sind.
    """
    first = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    second = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    second.apply_translation((5.0, 0.0, 0.0))
    return MeshData.of(trimesh.util.concatenate([first, second, _crossing_shell((40.0, 0.0, 0.0))]))


@pytest.mark.parametrize(
    "offset, angle",
    [(0.0, 0), (0.0, 17), (100.0, 0), (100.0, 17)],
)
def test_differently_subdivided_edge_contact_survives_transform(offset: float, angle: int) -> None:
    """Ein reiner Kantenkontakt blockiert Boolesch auch nach starrer Bewegung nicht."""
    from app.core.geom.repair import parts_that_cross

    lower = trimesh.creation.box(extents=(1.0, 1.0, 10.0))
    lower.apply_translation((0.5, 0.5, 5.0))
    upper = trimesh.creation.box(extents=(1.0, 1.0, 5.0))
    upper.apply_translation((-0.5, -0.5, 2.5))
    transform = trimesh.transformations.rotation_matrix(math.radians(angle), (1.0, 2.0, 3.0))
    transform[:3, 3] = (offset, -offset, offset)
    lower.apply_transform(transform)
    upper.apply_transform(transform)
    body = MeshData.of(trimesh.util.concatenate([lower, upper]))

    cutter = trimesh.creation.box(extents=(0.3, 0.3, 15.0))
    cutter.apply_translation((0.5, 0.5, 5.0))
    cutter.apply_transform(transform)

    assert parts_that_cross(body.raw) is None
    result = boolean("difference", [body, MeshData.of(cutter)], stages=("direct",), quality="fine")

    assert result.mesh.component_count == 2
    assert result.mesh.volume == pytest.approx(14.1, abs=1e-6)
    assert result.solver.strategy == "direct"


@pytest.mark.parametrize("order", [(False, True), (True, False)])
def test_united_parts_cache_separates_face_contact_mode(order: tuple[bool, bool]) -> None:
    """Kontaktflächen werden nur im angeforderten Vorprüfmodus vereinigt (RM-319)."""
    from app.core.geom.boolean import _united_parts

    lower = trimesh.creation.box(extents=(40.0, 20.0, 10.0))
    lower.apply_translation((0.0, 0.0, 5.0))
    upper = trimesh.creation.box(extents=(40.0, 20.0, 10.0))
    upper.apply_translation((0.0, 0.0, 15.0))
    mesh = MeshData.of(trimesh.util.concatenate([lower, upper]))

    answers = {
        include_contacts: _united_parts(mesh, None, merge_face_contacts=include_contacts)
        for include_contacts in order
    }

    assert answers[False] is None, "normale Boolesche Ops lassen Flächenkontakt getrennt"
    merged = answers[True]
    assert merged is not None and merged.body is not None
    assert merged.body.component_count == 1


def _tubes(sections: int) -> MeshData:
    """Zwei ineinanderliegende Röhren aus langen Seitendreiecken, die sich nirgends
    berühren — der Zwilling des Besenhalters (RM-381)."""
    inner = lathe.annulus(r_min=8.0, r_max=10.0, height=60.0, sections=sections)
    outer = lathe.annulus(r_min=11.0, r_max=13.0, height=60.0, sections=sections)
    return MeshData.of(trimesh.util.concatenate([inner, outer]))


def test_nested_tubes_are_checked_completely_without_a_quadratic_search() -> None:
    """Die vollständige Vorfrage zählt Paare, die sich überdecken, nicht Achsenläufe (RM-381).

    Lange Seitendreiecke überdecken sich entlang jeder Achse fast alle. Die
    Suche bis RM-381 zählte jedes Dreieck des einen Teils gegen alles im Bereich
    der längsten Hülle des anderen: am Besenhalter 55,7 Millionen
    Grobkandidaten für 14 058 echte Paare, 3,9 s vor jeder Booleschen
    Operation; an diesen Röhren 1,8 s bei 2 048 Abschnitten, quadratisch
    wachsend. Über die Hüllquaderbäume bleibt es bei den Paaren, die sich
    wirklich überdecken — hier keine. Die Schranke liegt weit über der
    gemessenen Zeit (0,2 s unter Last) und weit unter der alten.
    """
    from app.core.geom.repair import parts_that_cross

    body = _tubes(4096)
    started = time.perf_counter()
    place = parts_that_cross(body.raw, max_pairs=None, require_complete=True)
    elapsed = time.perf_counter() - started

    assert place is None
    assert elapsed < 2.0, f"{elapsed:.2f} s — die Vorfrage darf nicht quadratisch suchen"


def test_a_crossing_beside_nested_tubes_is_found_within_the_import_budget() -> None:
    """Was das Einlesen mit Budget fragt, findet es jetzt auch neben langen Dreiecken (RM-381).

    Die Achsensuche gab am ersten Teilepaar — den zwei Röhren — nach 20 Budgets
    Grobkandidaten auf und sagte für den ganzen Körper nichts, auch über den
    Würfel, der quer durch die Wand der inneren Röhre geht. Das Einlesen
    meldete „mehrere Teile" statt „stecken ineinander".
    """
    from app.core.geom.repair import CROSSING_PARTS_PAIRS, parts_that_cross

    pin = trimesh.creation.box(extents=(4.0, 4.0, 4.0))
    pin.apply_translation((9.0, 0.0, 0.0))
    body = trimesh.util.concatenate([_tubes(4096).raw, pin])

    place = parts_that_cross(body, max_pairs=CROSSING_PARTS_PAIRS)

    assert place is not None
    assert 7.0 - 1e-9 <= place[0] <= 11.0 + 1e-9, (
        "der Ort liegt an der Wand, durch die der Würfel geht"
    )


@pytest.mark.parametrize("size", [0.0001, 0.001, 0.01])
@pytest.mark.parametrize("offset", [0.0, 1000.0])
def test_a_small_positive_intersection_does_not_trigger_a_geometric_fallback(
    size: float, offset: float
) -> None:
    """Ein positiver Schnittkörper hat kein Mindestvolumen aus einer Längentoleranz."""
    first = box(size, (offset, 0.0, 0.0))
    second = box(size, (offset, 0.0, 0.0))

    outcome = boolean("intersection", [first, second], allow_empty=True, stages=("direct",))

    assert outcome.mesh.is_watertight and outcome.mesh.component_count == 1
    assert outcome.mesh.volume == pytest.approx(size**3, rel=1e-8, abs=0.0)
    assert outcome.solver.attempted == ("direct",)


@pytest.mark.parametrize("offset", [0.0, 1000.0])
@pytest.mark.parametrize("angle", [0.0, 37.0])
def test_a_thin_positive_intersection_is_not_rounded_into_contact(
    offset: float, angle: float
) -> None:
    """Auch fern vom Ursprung bleibt ein echter Schnitt von einer Kontaktfläche verschieden."""
    overlap = 0.00001
    matrix = trimesh.transformations.rotation_matrix(math.radians(angle), (1.0, 2.0, 3.0))
    matrix[:3, 3] = (offset, 0.0, 0.0)
    bodies = [box(20.0, (0.0, 0.0, 0.0)), box(20.0, (20.0 - overlap, 0.0, 0.0))]
    for body in bodies:
        body.raw.apply_transform(matrix)
    outcome = boolean(
        "intersection",
        bodies,
        allow_empty=True,
    )
    assert outcome.mesh.volume == pytest.approx(400.0 * overlap, rel=1e-7)
    assert outcome.solver.attempted == ("direct",)


@pytest.mark.parametrize("offset", [0.0, 1000.0])
def test_contact_shells_do_not_survive_beside_a_hollow_and_a_tiny_part(offset: float) -> None:
    """Echte Kontaktreste verschwinden; innere Schale und 10⁻¹²-mm³-Teil bleiben erhalten."""
    from app.core.knowledge.parts.testbodies import FitLadderParams, fit_ladder

    built = fit_ladder(FitLadderParams(diameter=6.0, steps=4, first=0.1, step=0.05))
    male, female = sorted(built.mesh.raw.split(), key=lambda body: body.bounds[0, 1])
    pin, bore = (built.features[name].params["centre"] for name in ("pin_1", "bore_1"))
    female.apply_translation((pin[0] - bore[0], pin[1] - bore[1], 3.0))
    outer = box(20.0, (300.0, 0.0, 0.0)).raw
    inner = box(10.0, (300.0, 0.0, 0.0)).raw
    inner.invert()
    tiny = box(0.0001, (330.0, 0.0, 0.0)).raw
    envelope = trimesh.creation.box(extents=(80.0, 40.0, 40.0))
    envelope.apply_translation((315.0, 0.0, 0.0))
    left = trimesh.util.concatenate((male, outer, inner, tiny))
    right = trimesh.util.concatenate((female, envelope))
    matrix = trimesh.transformations.rotation_matrix(math.radians(37.0), (1.0, 2.0, 3.0))
    matrix[:3, 3] = (offset, 0.0, 0.0)
    for body in (left, right):
        body.apply_transform(matrix)

    outcome = boolean("intersection", [MeshData.of(left), MeshData.of(right)], stages=("direct",))

    shells = outcome.mesh.raw.split(only_watertight=False)
    assert len(shells) == 3, "only outer shell, hollow inner shell and tiny solid remain"
    assert all(shell.is_watertight and shell.is_winding_consistent for shell in shells)
    volumes = sorted(float(shell.volume) for shell in shells)
    assert volumes[0] == pytest.approx(-1000.0, abs=1e-7)
    assert volumes[1] == pytest.approx(1e-12, rel=1e-6, abs=0.0)
    assert volumes[2] == pytest.approx(8000.0, abs=1e-7)
    assert outcome.mesh.volume == pytest.approx(7000.0, abs=1e-7)
    assert outcome.solver.attempted == ("direct",)
    following = boolean("intersection", [outcome.mesh, MeshData.of(right)], stages=("direct",))
    assert following.mesh.raw.body_count == 3
    assert following.mesh.volume == pytest.approx(outcome.mesh.volume, abs=1e-7)
    assert following.solver.attempted == ("direct",)


@pytest.mark.parametrize(
    "diameter,steps,first,step", [(6.0, 4, 0.1, 0.05), (2.0, 8, 0.0, 0.01), (30.0, 8, 1.0, 0.5)]
)
@pytest.mark.parametrize("angle", [0.0, 37.0])
@pytest.mark.parametrize("offset", [0.0, 1000.0])
def test_real_fit_ladder_contacts_remain_empty_after_a_rigid_transform(
    diameter: float, steps: int, first: float, step: float, angle: float, offset: float
) -> None:
    """Kontakt an Sockel und Lochmantel bleibt nach Drehen und Verschieben volumenlos."""
    from app.core.knowledge.parts.testbodies import FitLadderParams, fit_ladder

    built = fit_ladder(FitLadderParams(diameter=diameter, steps=steps, first=first, step=step))
    male, female = sorted(built.mesh.raw.split(), key=lambda body: body.bounds[0, 1])
    pin, bore = (built.features[name].params["centre"] for name in ("pin_1", "bore_1"))
    female.apply_translation((pin[0] - bore[0], pin[1] - bore[1], 3.0))
    matrix = trimesh.transformations.rotation_matrix(math.radians(angle), (1.0, 2.0, 3.0))
    matrix[:3, 3] = (offset, 0.0, 0.0)
    for body in (male, female):
        body.apply_transform(matrix)

    outcome = boolean(
        "intersection",
        [MeshData.of(male), MeshData.of(female)],
        allow_empty=True,
        stages=("direct",),
    )

    assert outcome.mesh.triangle_count == 0
    assert outcome.mesh.volume == 0.0
    assert outcome.solver.attempted == ("direct",)


@pytest.mark.parametrize("kind", ["flat", "open", "inverted", "thin"])
def test_degenerate_results_do_not_raise_during_plausibility(kind: str) -> None:
    """Kein Schwerpunkt wird aus Nullvolumen dividiert; ungültige Körper bleiben abgelehnt."""
    from app.core.geom.boolean import _plausible

    body = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    if kind == "flat":
        body.vertices[:, 2] = 0.0
    elif kind == "open":
        body.update_faces(list(range(len(body.faces) - 1)))
    elif kind == "inverted":
        body.invert()
    else:
        body.apply_scale((1.0, 1.0, 0.000001))
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        assert _plausible(MeshData.of(body), allow_empty=True) is (kind == "thin")


def test_kernel_contact_is_empty_without_geometrical_fallback() -> None:
    """Zwei nur an der Außenfläche anliegende Würfel erzeugen kein Druckvolumen."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        outcome = boolean(
            "intersection",
            [box(20.0, (0.0, 0.0, 0.0)), box(20.0, (20.0, 0.0, 0.0))],
            allow_empty=True,
        )
    assert outcome.mesh.triangle_count == 0
    assert outcome.mesh.volume == 0.0
    assert outcome.solver.attempted == ("direct",)


@pytest.mark.parametrize("residual", [-1e-13, 1e-13])
def test_a_planar_native_contact_is_empty_despite_volume_roundoff(
    monkeypatch: pytest.MonkeyPatch, residual: float
) -> None:
    """Ein flacher Kontakt bleibt leer, wenn das native Integral Rundungsreste trägt."""
    import manifold3d

    monkeypatch.setattr(manifold3d.Manifold, "volume", lambda self: residual)
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        outcome = boolean(
            "intersection",
            [box(20.0, (0.0, 0.0, 0.0)), box(20.0, (20.0, 0.0, 0.0))],
            allow_empty=True,
            stages=("direct",),
        )
    assert outcome.mesh.triangle_count == 0
    assert outcome.solver.attempted == ("direct",)


def test_a_native_boolean_result_can_be_used_by_the_next_operation() -> None:
    """Native Ausgabepuffer sind gültige Eingaben der nächsten Operation."""
    joined = boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))]).mesh
    joined.raw.vertices.flags.writeable = False
    joined.raw.faces.flags.writeable = False

    outcome = boolean("difference", [joined, box(20.0, (10.0, 0.0, 0.0))])

    assert outcome.mesh.volume == pytest.approx(4000.0, rel=1e-7)
    assert outcome.solver.attempted == ("direct",)


@pytest.mark.parametrize("following", ["remesh", "subdivided", "surface_gap"])
def test_a_boolean_result_satisfies_the_existing_mesh_consumers(following: str) -> None:
    """Die natürliche Ausgabe bleibt für Netzverfeinerung und Abstandsmessung verwendbar."""
    from app.core.geom.measure import surface_gap
    from app.core.geom.mesh_ops import remesh, subdivided

    joined = boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))]).mesh
    if following == "surface_gap":
        assert surface_gap(joined, box(20.0, (50.0, 0.0, 0.0)), 25.0) == pytest.approx(20.0)
    else:
        refined = remesh(joined, 8.0) if following == "remesh" else subdivided(joined, 8.0, 30.0)
        assert refined.is_watertight
        assert refined.volume == pytest.approx(12000.0, rel=1e-7)
        assert refined.triangle_count > joined.triangle_count
    assert joined.raw.vertices.flags.writeable
    assert joined.raw.vertices.flags.c_contiguous
    assert joined.raw.faces.flags.writeable
    assert joined.raw.faces.flags.c_contiguous


@pytest.mark.parametrize("offset", [0.0, 1000.0])
@pytest.mark.parametrize("overlap", [0.0, 0.00001])
def test_shared_volume_distinguishes_contact_from_a_thin_overlap(
    offset: float, overlap: float
) -> None:
    """Die Montagemessung verwendet dieselbe Genauigkeit wie der schneidende Kern."""
    with warnings.catch_warnings():
        warnings.simplefilter("error", RuntimeWarning)
        volume = shared_volume(
            box(20.0, (offset, 0.0, 0.0)).raw,
            box(20.0, (offset + 20.0 - overlap, 0.0, 0.0)).raw,
        )
    assert volume == pytest.approx(400.0 * overlap, rel=1e-7, abs=1e-12)


def run_op(
    op: str,
    first: MeshData,
    second: MeshData,
    *,
    first_slots: tuple[MaterialSlot, ...] = (),
    second_slots: tuple[MaterialSlot, ...] = (),
) -> OpResult:
    """Eine boolesche Operation über das Register fahren — mit Profil, damit
    ``without_effect`` an der Düse misst und nicht am Rechenepsilon."""
    return run_many_op(op, ((first, first_slots), (second, second_slots)))


def run_many_op(
    op: str,
    entries: tuple[tuple[MeshData, tuple[MaterialSlot, ...]], ...],
) -> OpResult:
    """Eine Boolesche mit ihrer wirklichen, variablen Eingangszahl fahren."""
    load_operations()
    spec = REGISTRY.get(op)
    objects = [
        SceneObject(
            id=f"obj_{index}",
            name=chr(ord("A") + index - 1),
            mesh=mesh,
            material_slots=list(slots),
        )
        for index, (mesh, slots) in enumerate(entries, start=1)
    ]
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry for entry in objects}, parameters={}),
            inputs=objects,
            params=spec.params(),
            profile=profiles.make_profile(),
            quality="fine",
            seed=0,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def test_union_of_two_overlapping_cubes() -> None:
    result = boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))])

    assert result.solver.strategy == "direct"
    assert result.mesh.is_watertight
    assert result.mesh.volume == pytest.approx(12000.0, rel=1e-6), "8000 + 8000 - 4000 overlap"
    assert not result.findings, "the plain case has nothing to report"


@pytest.mark.parametrize(
    ("kind", "tool", "volume"),
    [
        # Ein Würfel 4 mm auf der Oberseite, 1 mm eingesenkt: 12 000 + 4·4·3.
        ("union", ((0.0, 0.0, 11.0), 4.0), 12048.0),
        # Ein Würfel 2 mm halb in der Oberseite, nur im ersten Teil und im
        # gemeinsamen Raum: je 12 000 - 2·2·1.
        ("difference", ((-8.0, 0.0, 10.0), 2.0), 11996.0),
        ("difference", ((5.0, 0.0, 10.0), 2.0), 11996.0),
    ],
    ids=["union", "difference beside", "difference inside"],
)
def test_parts_that_stick_into_each_other_are_united_first_and_it_says_so(
    kind: BooleanKind, tool: tuple[tuple[float, float, float], float], volume: float
) -> None:
    """RM-221: An zwei ineinandersteckenden Teilen rechnete der Kern Beliebiges.

    Am Piratenschiff (``obj_11_Cylinder_B.stl``) verschmolz *Fläche versetzen*
    die zwei Zylinder still — 2 → 1 Teile, +10,01 statt +19,63 mm³, kein Wort.
    An zwei ineinandergeschobenen Würfeln blieb die Vereinigung zweiteilig, und
    eine Differenz machte aus zwei Teilen drei oder vier (gemessen 25.09.2026).
    Gedruckt werden die Teile ohnehin als eines; die Kette vereinigt sie
    deshalb zuerst, wie *Überschneidungen auflösen* es tut, und sagt es. Das
    Volumen ist danach das des Drucks — der gemeinsame Raum zählt einmal.
    """
    body = two_cubes(10.0)
    assert body.component_count == 2
    assert body.volume == pytest.approx(16000.0), "vorher zählt der gemeinsame Raum doppelt"
    place, size = tool

    result = boolean(kind, [body, box(size, place)])

    assert result.mesh.component_count == 1
    assert result.mesh.volume == pytest.approx(volume, rel=1e-9)
    united = [finding for finding in result.findings if finding.code == "boolean.parts_united"]
    assert len(united) == 1, [finding.code for finding in result.findings]
    assert united[0].severity == "info"
    assert united[0].location is not None
    assert -10.0 <= united[0].location[0] <= 20.0, "der Ort liegt am Körper"


def _cube_in_a_cube() -> MeshData:
    """Würfel 20 mit einem Würfel 10 ganz in seinem Material, beide nach außen gewickelt."""
    outer = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    inner = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    return MeshData.of(trimesh.util.concatenate([outer, inner]))


@pytest.mark.parametrize(
    ("kind", "tool", "volume"),
    [
        # Ein Würfel 4 mm mitten durch beide: 8 000 - 4·4·20.
        ("difference", ((0.0, 0.0, 0.0), (4.0, 4.0, 30.0)), 8000.0 - 320.0),
        # Ein Würfel 4 mm auf der Oberseite, 1 mm eingesenkt: 8 000 + 4·4·3.
        ("union", ((0.0, 0.0, 11.0), (4.0, 4.0, 4.0)), 8000.0 + 48.0),
    ],
    ids=["difference", "union"],
)
def test_a_part_inside_the_material_of_another_is_united_first_and_it_says_so(
    kind: BooleanKind,
    tool: tuple[tuple[float, float, float], tuple[float, float, float]],
    volume: float,
) -> None:
    """Ein Teil ganz im Material eines anderen steckt auch darin (Durchsicht
    0.5.1, BOHRUNG-02).

    Es schneidet keine Wand, und die Vorfrage nach durchdringenden Teilen sah
    es nicht: Eine Bohrung Ø 6 durch einen Würfel 20 mit einem Würfel 10 ganz
    innen ließ 8 154 statt 7 434 mm³ — das innere Teil zählte weiter doppelt,
    und der Bericht schwieg. Sollwert ist das Volumen wie gedruckt, mit dem
    inneren Teil als Material des äußeren.
    """
    body = _cube_in_a_cube()
    assert body.volume == pytest.approx(9000.0), "vorher zählt das innere Teil doppelt"
    place, extents = tool
    cutter = trimesh.creation.box(extents=extents)
    cutter.apply_translation(place)

    result = boolean(kind, [body, MeshData.of(cutter)])

    assert result.mesh.component_count == 1
    assert result.mesh.volume == pytest.approx(volume, rel=1e-9)
    codes = [finding.code for finding in result.findings]
    assert codes.count("boolean.parts_united") == 1, codes


def test_a_part_in_a_hollow_stays_a_part() -> None:
    """Ein Teil frei in einem Hohlraum liegt in Luft (die Rassel): Es bleibt, und
    niemand vereinigt etwas. Sollwert: der hohle Würfel (Wand 2 mm), der Würfel
    darin und ein Würfel 2 mm, der ganz in der Wand abgetragen wird."""
    outer = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    hollow = trimesh.creation.box(extents=(16.0, 16.0, 16.0))
    hollow.invert()
    rattle = trimesh.creation.box(extents=(4.0, 4.0, 4.0))
    body = MeshData.of(trimesh.util.concatenate([outer, hollow, rattle]))
    cutter = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    cutter.apply_translation((9.0, 9.0, 9.0))

    result = boolean("difference", [body, MeshData.of(cutter)])

    assert result.mesh.volume == pytest.approx(8000.0 - 4096.0 + 64.0 - 8.0, rel=1e-9)
    assert "boolean.parts_united" not in [finding.code for finding in result.findings]


@pytest.mark.parametrize(("kind", "volume"), [("difference", 2398.0), ("union", 2408.0)])
def test_three_hundred_separate_parts_do_not_stop_a_boolean(
    kind: BooleanKind, volume: float
) -> None:
    """300 getrennte Würfel: Ein Schritt an einem davon rechnet, wie vor ``eab5f4f47`` (RM-383).

    Über :data:`~app.core.geom.repair.CROSSING_PARTS_MAX` Teilen hielt jede
    Boolesche an, mit dem Rat, die Teile im CAD-Programm zu vereinigen — für
    getrennte Teile unmöglich. Getrennte Teile kosten die Vorfrage über die
    Hüllquaderbäume nichts. Sollwert: 300 Würfel 2 mm (2 400 mm³), ein Stab
    1 × 1 × 10 durch den ersten nimmt 2 mm³ heraus oder setzt 8 mm³ an.
    """
    cubes = []
    for index in range(300):
        cube = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
        cube.apply_translation((4.0 * (index % 20), 4.0 * (index // 20), 0.0))
        cubes.append(cube)
    body = MeshData.of(trimesh.util.concatenate(cubes))
    rod = trimesh.creation.box(extents=(1.0, 1.0, 10.0))

    result = boolean(kind, [body, MeshData.of(rod)], object_ids=("obj_wuerfel", None))

    assert result.mesh.volume == pytest.approx(volume, rel=1e-9)
    assert result.mesh.component_count == 300


def test_a_crossing_pair_among_many_parts_is_still_united() -> None:
    """Zwei Würfel, die einander durchdringen, neben 255 weiteren: vereinigt, nicht angehalten.

    Sollwert: 8 + 8 − 2 (gemeinsamer Raum 1 × 1 × 2) + 255 = 269 mm³, der
    Würfel 1 in der Mitte nimmt 1 mm³ aus dem vereinigten Teil.
    """
    first = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
    second = first.copy()
    second.apply_translation((1.0, 1.0, 0.0))
    distant = []
    for index in range(255):
        piece = trimesh.creation.box(extents=(1.0, 1.0, 1.0))
        piece.apply_translation((100.0 + 3.0 * index, 0.0, 0.0))
        distant.append(piece)
    body = MeshData.of(trimesh.util.concatenate([first, second, *distant]))

    result = boolean("difference", [body, box(1.0, (0.0, 0.0, 0.0))])

    assert result.mesh.volume == pytest.approx(268.0, rel=1e-9)
    assert "boolean.parts_united" in [finding.code for finding in result.findings]


def test_a_crossing_shell_stops_before_the_boolean_solver_and_keeps_its_object(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Trifft das Werkzeug die selbstkreuzende Schale, hält die Kette vor dem Solver (RM-382).

    Der Satz nennt Grund und Weg, der Ort ist der Treffpunkt, und *Stellen
    zeigen* öffnet die Netzfehlerkarte am Körper, der die Schale trägt.
    """
    from app.core.errors import CANCEL, CORRECT_INPUT, SHOW_LOCATIONS
    from app.core.geom import boolean as boolean_module

    body = crossing_shell_with_overlapping_part()
    assert body.component_count == 2
    assert body.is_watertight
    monkeypatch.setattr(
        boolean_module,
        "_run_stage",
        lambda *_args, **_kwargs: pytest.fail(
            "Solver trotz fehlgeschlagener Vereinigung gestartet"
        ),
    )

    with pytest.raises(GeometryError) as caught:
        boolean(
            "difference",
            [body, box(2.0, (0.0, 0.0, 8.0))],
            object_ids=("laptop-riser", None),
        )

    assert caught.value.suggestions == (SHOW_LOCATIONS, CORRECT_INPUT, CANCEL)
    assert caught.value.object_id == "laptop-riser"
    assert caught.value.detail == CROSSING_SHELL_IN_THE_WAY
    location = caught.value.values["location"]
    assert all(-10.0 - 1e-9 <= value <= 10.0 + 1e-9 for value in location), location


@pytest.mark.parametrize(
    ("tool", "place"),
    [
        (((2.0, 2.0, 30.0), (45.0, -5.0, 0.0)), "durch die Wand"),
        (((1.0, 1.0, 1.0), (33.0, -7.0, -7.0)), "ganz darin"),
    ],
    ids=["durch", "darin"],
)
def test_a_tool_at_the_crossing_shell_stops_with_its_body_and_place(
    tool: tuple[tuple[float, float, float], tuple[float, float, float]], place: str
) -> None:
    """Am Laptop-Zwilling hält ein Werkzeug, das die kaputte Schale trifft (RM-382).

    Getroffen ist sie auch, wenn das Werkzeug ganz in ihr liegt: Dort entscheidet
    ihre falsche Windung, ob ein Hohlraum entsteht.
    """
    from app.core.errors import CANCEL, CORRECT_INPUT, SHOW_LOCATIONS

    extents, centre = tool
    cutter = trimesh.creation.box(extents=extents)
    cutter.apply_translation(centre)

    with pytest.raises(GeometryError) as caught:
        boolean("difference", [laptop_twin(), MeshData.of(cutter)], object_ids=("obj_1", None))

    assert caught.value.object_id == "obj_1", place
    assert caught.value.suggestions == (SHOW_LOCATIONS, CORRECT_INPUT, CANCEL)
    assert caught.value.detail == CROSSING_SHELL_IN_THE_WAY
    location = caught.value.values["location"]
    assert 30.0 - 1e-9 <= location[0] <= 50.0 + 1e-9, "der Ort liegt an der kaputten Schale"


@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_a_step_away_from_the_crossing_shell_computes_and_says_so(quality: str) -> None:
    """Abseits der kaputten Schale rechnet der Schritt wie vor ``eab5f4f47`` (RM-382).

    Entscheidung Robert: „Das Beste für Kunden, damit sie bearbeiten können." Am
    Laptop-Ständer hielt seit ``eab5f4f47`` jede Bohrung an, auch wo sie nichts
    traf. Hier geht ein Stab 2 × 2 × 20 nur durch den ersten Würfel: Er trägt
    2 · 2 · 10 = 40 mm³ ab, und der Befund sagt, dass sich die Teile nicht
    vereinigen ließen — mit dem Körper und den Wegen zur Karte und zur Stelle.
    """
    from app.core.errors import SHOW_LOCATION, SHOW_LOCATIONS

    body = laptop_twin()
    rod = trimesh.creation.box(extents=(2.0, 2.0, 20.0))
    rod.apply_translation((-3.0, 0.0, 0.0))

    result = boolean(
        "difference", [body, MeshData.of(rod)], quality=quality, object_ids=("obj_1", None)
    )

    assert body.volume - result.mesh.volume == pytest.approx(40.0, rel=1e-9)
    stuck = [finding for finding in result.findings if finding.code == "boolean.parts_not_united"]
    assert len(stuck) == 1, [finding.code for finding in result.findings]
    assert stuck[0].severity == "warning"
    assert stuck[0].object_id == "obj_1"
    assert stuck[0].suggestions == (SHOW_LOCATIONS, SHOW_LOCATION)
    assert stuck[0].location is not None


@pytest.mark.parametrize("where", ["abseits", "durch die Schale"])
def test_drill_hole_on_the_laptop_twin_keeps_its_body_either_way(where: str) -> None:
    """*Bohren* am Laptop-Zwilling, wie der Kunde es aufruft (RM-382, Abnahme).

    Abseits der kaputten Schale bohrt es und warnt, durch sie hält es — beide
    Male mit der Kennung des Körpers, damit *Stellen zeigen* ihn findet. Bis
    RM-382 gab ``prepare.drill`` keine Kennung an ``boolean()``, und der Halt
    stand ohne Körper im Prüfbericht.
    """
    from app.core.errors import CANCEL, CORRECT_INPUT, SHOW_LOCATIONS

    load_operations()
    spec = REGISTRY.get("drill_hole")
    entry = SceneObject(id="obj_staender", name="Ständer", mesh=laptop_twin())
    x, y = (-3.0, 0.0) if where == "abseits" else (45.0, -5.0)
    context = OpContext(
        scene=Scene(objects={entry.id: entry}),
        inputs=[entry],
        params=spec.params(diameter=2.0, x=x, y=y, z=10.0, nx=0.0, ny=0.0, nz=1.0, depth=0.0),
        profile=profiles.make_profile("centauri-carbon-2", "petg"),
        quality="draft",
        seed=7,
        progress=lambda fraction, text: None,
        ask=lambda question, choices: choices[0],
        cancelled=NeverCancelled(),
    )
    if where == "abseits":
        result = spec.fn(context)
        stuck = [
            finding for finding in result.findings if finding.code == "boolean.parts_not_united"
        ]
        assert len(stuck) == 1
        assert stuck[0].object_id == entry.id
        assert result.outputs[0].mesh.volume < entry.mesh.volume
        return
    with pytest.raises(GeometryError) as caught:
        spec.fn(context)
    assert caught.value.object_id == entry.id
    assert caught.value.suggestions == (SHOW_LOCATIONS, CORRECT_INPUT, CANCEL)
    assert caught.value.detail == CROSSING_SHELL_IN_THE_WAY


def test_a_crossing_scene_tool_stops_a_difference_with_its_own_id() -> None:
    """Ein Szenenkörper als Werkzeug wird geprüft wie der Körper selbst (Review RM-253, Fund 5).

    ``subtract_objects [gut, kaputt]`` rechnete still mit der Schale, die sich
    selbst kreuzt. Trifft der bearbeitete Körper sie, hält die Differenz mit
    der Kennung des Werkzeugs, und der Weg ist eine andere Auswahl.
    """
    from app.core.errors import CANCEL, CHANGE_SELECTION, SHOW_LOCATIONS

    with pytest.raises(GeometryError) as caught:
        boolean(
            "difference",
            [box(6.0, (40.0, 0.0, 0.0)), laptop_twin()],
            object_ids=("obj_gut", "obj_kaputt"),
        )

    assert caught.value.object_id == "obj_kaputt"
    assert caught.value.suggestions == (SHOW_LOCATIONS, CHANGE_SELECTION, CANCEL)


def test_a_scene_tool_with_parts_that_cross_is_united_first() -> None:
    """Auch ein Werkzeug aus der Szene geht mit vereinigten Teilen in den Kern (Fund 5).

    Sollwert: Würfel 20 (8 000 mm³), das Werkzeug aus zwei Würfeln 10, die sich
    um 5 mm durchdringen, reicht von x = 0 bis 15; im Körper liegen 10 · 10 · 10.
    """
    near = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    near.apply_translation((5.0, 0.0, 0.0))
    far = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    far.apply_translation((10.0, 0.0, 0.0))
    tool = MeshData.of(trimesh.util.concatenate([near, far]))

    result = boolean("difference", [box(20.0, (0.0, 0.0, 0.0)), tool], object_ids=("a", "b"))

    assert result.mesh.volume == pytest.approx(7000.0, rel=1e-9)
    assert "boolean.parts_united" in [finding.code for finding in result.findings]


def test_closed_at_keeps_the_source_id_on_an_unsafe_body(monkeypatch: pytest.MonkeyPatch) -> None:
    """Beim Schließen bleibt die Handlung an den Szenenkörper gebunden (RM-253)."""
    from app.core.errors import CANCEL, CORRECT_INPUT, SHOW_LOCATIONS
    from app.core.geom import prepare_ops

    body = crossing_shell_with_overlapping_part()
    feature = Feature(id="thread_1", kind="thread", provenance="detected", params={})
    monkeypatch.setattr(prepare_ops, "_tool_for", lambda *_args, **_kwargs: box(2.0, (0, 0, 8)))

    with pytest.raises(GeometryError) as caught:
        prepare_ops._closed_at(
            body,
            feature,
            (0.0, 0.0, 0.0),
            False,
            quality="fine",
            seed=7,
            cancelled=NeverCancelled(),
            object_id="laptop-riser",
        )

    assert caught.value.object_id == "laptop-riser"
    assert caught.value.suggestions == (SHOW_LOCATIONS, CORRECT_INPUT, CANCEL)
    assert caught.value.detail == CROSSING_SHELL_IN_THE_WAY


def test_a_crossing_shell_without_object_id_does_not_offer_show_locations() -> None:
    """Ohne belegtes Ziel darf die Fehlermeldung keine Defektkarte versprechen."""
    from app.core.errors import CANCEL, CORRECT_INPUT, SHOW_LOCATIONS

    with pytest.raises(GeometryError) as caught:
        boolean(
            "difference",
            [crossing_shell_with_overlapping_part(), box(2.0, (0.0, 0.0, 8.0))],
        )

    assert caught.value.object_id is None
    assert caught.value.suggestions == (CORRECT_INPUT, CANCEL)
    assert SHOW_LOCATIONS not in caught.value.suggestions
    assert caught.value.detail == CROSSING_SHELL_IN_THE_WAY


def test_a_union_beside_the_crossing_shell_computes_and_names_the_operand() -> None:
    """Abseits der kaputten Schale rechnet auch die Vereinigung; der Befund nennt den Körper."""
    result = boolean(
        "union",
        [box(3.0, (-30.0, 0.0, 0.0)), crossing_shell_with_overlapping_part()],
        object_ids=("clean-body", "laptop-riser"),
    )

    stuck = [finding for finding in result.findings if finding.code == "boolean.parts_not_united"]
    assert len(stuck) == 1
    assert stuck[0].object_id == "laptop-riser"


def test_a_failed_union_names_the_crossing_operand() -> None:
    """Trifft der andere Körper die kaputte Schale, nennt der Halt genau diesen Körper."""
    body = crossing_shell_with_overlapping_part()

    with pytest.raises(GeometryError) as caught:
        boolean(
            "union",
            [box(3.0, (-9.0, 0.0, 0.0)), body],
            object_ids=("clean-body", "laptop-riser"),
        )

    assert caught.value.object_id == "laptop-riser"
    from app.core.scene.evaluate import _finding_from
    from app.core.types import Operation
    from app.ui.panels import actions_for_document

    finding = _finding_from(
        caught.value,
        Operation(
            id=12,
            op="union_objects",
            inputs=("clean-body", "laptop-riser"),
            outputs=("joined-body",),
        ),
    )
    assert finding.object_id == "laptop-riser"
    assert finding.location is not None
    assert "show_locations" in [
        action.id for action in actions_for_document(finding, document=None)
    ]


def test_object_ids_must_align_with_boolean_inputs() -> None:
    """Eine falsche Zuordnung darf keinen Defekt am falschen Körper zeigen."""
    with pytest.raises(ValueError, match="object_ids must match meshes"):
        boolean(
            "difference",
            [box(2.0, (0.0, 0.0, 0.0)), box(1.0, (0.0, 0.0, 0.0))],
            object_ids=("body",),
        )


def test_a_failed_face_contact_merge_computes_and_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Kontakt-Merge, der nicht geht, rechnet weiter und sagt es (RM-382).

    Ohne selbstkreuzende Schale gibt es keinen Grund zu halten; der Schritt kann
    Material stehen lassen, und der Befund sagt das, ohne eine Durchdringung zu
    behaupten. Sollwert: zwei Platten 40 × 20 × 10 übereinander, der Würfel 2
    in ihrer Fuge nimmt aus jeder 2 · 2 · 1 heraus.
    """
    from app.core.geom import boolean as boolean_module

    monkeypatch.setattr(
        boolean_module, "resolve_self_intersections", lambda mesh, _cancelled: (mesh, False)
    )
    lower = trimesh.creation.box(extents=(40.0, 20.0, 10.0))
    lower.apply_translation((0.0, 0.0, 5.0))
    upper = trimesh.creation.box(extents=(40.0, 20.0, 10.0))
    upper.apply_translation((0.0, 0.0, 15.0))
    body = MeshData.of(trimesh.util.concatenate([lower, upper]))

    result = boolean(
        "difference",
        [body, box(2.0, (0.0, 0.0, 10.0))],
        merge_face_contacts=True,
    )

    assert result.mesh.volume == pytest.approx(16000.0 - 8.0, rel=1e-9)
    stuck = [finding for finding in result.findings if finding.code == "boolean.parts_not_united"]
    assert len(stuck) == 1
    assert "selbst" not in str(stuck[0].message)


def test_face_contact_mode_keeps_crossing_diagnosis_and_locations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Flächenkontaktmodus kann auch an einer selbstkreuzenden Schale scheitern."""
    from app.core.errors import CANCEL, CORRECT_INPUT, SHOW_LOCATIONS
    from app.core.geom import boolean as boolean_module

    body = crossing_shell_with_overlapping_part()
    monkeypatch.setattr(
        boolean_module,
        "_run_stage",
        lambda *_args, **_kwargs: pytest.fail(
            "Solver trotz fehlgeschlagener Vereinigung gestartet"
        ),
    )

    with pytest.raises(GeometryError) as caught:
        boolean(
            "difference",
            [body, box(2.0, (0.0, 0.0, 8.0))],
            merge_face_contacts=True,
            object_ids=("laptop-riser", None),
        )

    assert caught.value.detail == CROSSING_SHELL_IN_THE_WAY
    assert caught.value.object_id == "laptop-riser"
    assert caught.value.suggestions == (SHOW_LOCATIONS, CORRECT_INPUT, CANCEL)


def test_face_contacts_that_cannot_be_united_get_a_neutral_finding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein fehlgeschlagener Kontaktversuch behauptet keine Durchdringung (RM-319)."""
    from app.core.errors import SHOW_LOCATION
    from app.core.geom import boolean as boolean_module

    monkeypatch.setattr(
        boolean_module, "resolve_self_intersections", lambda mesh, _cancelled: (mesh, False)
    )
    lower = trimesh.creation.box(extents=(40.0, 20.0, 10.0))
    lower.apply_translation((0.0, 0.0, 5.0))
    upper = trimesh.creation.box(extents=(40.0, 20.0, 10.0))
    upper.apply_translation((0.0, 0.0, 15.0))
    body = MeshData.of(trimesh.util.concatenate([lower, upper]))

    _prepared, findings, _stuck = boolean_module._parts_united_first(
        "difference", [body], None, merge_face_contacts=True
    )

    stuck = [finding for finding in findings if finding.code == "boolean.parts_not_united"]
    assert len(stuck) == 1, [finding.code for finding in findings]
    assert stuck[0].message == (
        "Teile des Modells ließen sich vor diesem Schritt nicht vereinigen. "
        "Der Schritt kann Material stehen lassen."
    )
    assert stuck[0].location is not None
    assert stuck[0].suggestions == (SHOW_LOCATION,)


def test_a_tool_made_of_crossing_pieces_is_left_to_the_kernel() -> None:
    """Bei Differenz und Schnittmenge gilt die Vorvereinigung dem bearbeiteten Körper.

    Ein Werkzeug baut Solidon selbst, und manche bestehen aus Stücken, die
    einander überschneiden — das Gitter von *Gitter füllen* an jedem Knoten.
    Über ihm stand sonst „Ineinandersteckende Teile wurden dabei vereinigt"
    zu Teilen, die der Kunde nie hatte.
    """
    body = box(20.0, (0.0, 0.0, 0.0))
    tool = two_cubes(10.0)
    tool.raw.apply_translation((-15.0, 0.0, 12.0))

    kinds: tuple[BooleanKind, ...] = ("difference", "intersection")
    for kind in kinds:
        result = boolean(kind, [body, tool], allow_empty=True)
        assert "boolean.parts_united" not in [finding.code for finding in result.findings], kind


def test_union_leaves_an_internal_crossing_tool_out_of_input_preflight() -> None:
    """Interne Werkzeuge dürfen sich überschneiden; echte Eingänge prüft die Vorfrage."""
    from app.core.geom import boolean as boolean_module

    body = box(20.0, (0.0, 0.0, 0.0))
    tool = crossing_shell_with_overlapping_part()

    prepared, findings, stuck = boolean_module._parts_united_first(
        "union", [body, tool], None, object_ids=("customer-body", None)
    )

    assert prepared[0] is body
    assert prepared[1] is tool
    assert not any(finding.code == "boolean.parts_not_united" for finding in findings)
    assert stuck == []


def test_parts_that_only_share_a_tool_are_not_named_as_united() -> None:
    """Zwei getrennte Würfel, verbunden durch einen Steg: eine gewöhnliche Vereinigung."""
    apart = two_cubes(30.0)
    bar = trimesh.creation.box(extents=(40.0, 4.0, 4.0))
    bar.apply_translation((15.0, 0.0, 0.0))

    result = boolean("union", [apart, MeshData.of(bar)])

    assert result.mesh.component_count == 1
    assert result.mesh.volume == pytest.approx(16000.0 + 10.0 * 4.0 * 4.0, rel=1e-9)
    assert "boolean.parts_united" not in [finding.code for finding in result.findings]


def test_difference_removes_the_overlap() -> None:
    result = boolean("difference", [solid(), box(20.0, (10.0, 0.0, 0.0))])

    assert result.mesh.volume == pytest.approx(4000.0, rel=1e-6)
    assert result.solver.strategy == "direct"


def test_intersection_keeps_only_the_overlap() -> None:
    result = boolean("intersection", [solid(), box(20.0, (10.0, 0.0, 0.0))])

    assert result.mesh.volume == pytest.approx(4000.0, rel=1e-6)


def test_union_keeps_the_filament_descriptions_of_both_bodies() -> None:
    """Die Flächen trugen beide Slotnummern, aber der zweite Name und seine
    Farbe verschwanden am Operationsrand — die Ansicht und der 3MF-Export
    konnten die korrekt übertragene Nummer dadurch nicht mehr erklären.
    """
    white = MaterialSlot(index=0, name="PLA Weiß", colour=(1.0, 1.0, 1.0))
    black = MaterialSlot(index=1, name="PLA Schwarz", colour=(0.05, 0.05, 0.05))

    result = run_op(
        "union_objects",
        with_slot(solid(), 0),
        with_slot(box(20.0, (10.0, 0.0, 0.0)), 1),
        first_slots=(white,),
        second_slots=(black,),
    )

    output = result.outputs[0]
    assert used_slots(output.mesh) == (0, 1), "die Geometrie trägt beide Filamente"
    assert output.material_slots == [white, black], "Name und Farbe erklären beide Nummern"


def test_union_keeps_the_filament_descriptions_of_every_selected_body() -> None:
    """Variable Eingänge gelten auch für die Materialbeschreibung.

    Die Geometrie trug den Slot des dritten Körpers bereits korrekt, aber die
    Operation erklärte nur die ersten zwei Nummern. Ansicht und 3MF-Ausgabe
    verloren dadurch Name, Farbe und Filamenttyp genau der Eingänge, für die
    die Mehrfachauswahl neu eingeführt wurde.
    """
    red = MaterialSlot(index=0, name="PLA Rot", colour=(0.8, 0.05, 0.05))
    green = MaterialSlot(index=1, name="PETG Grün", colour=(0.05, 0.7, 0.1))
    blue = MaterialSlot(index=2, name="ASA Blau", colour=(0.05, 0.15, 0.8))

    result = run_many_op(
        "union_objects",
        (
            (with_slot(box(20.0, (0.0, 0.0, 0.0)), 0), (red,)),
            (with_slot(box(20.0, (10.0, 0.0, 0.0)), 1), (green,)),
            (with_slot(box(20.0, (-10.0, 0.0, 0.0)), 2), (blue,)),
        ),
    )

    output = result.outputs[0]
    assert used_slots(output.mesh) == (0, 1, 2), "die Geometrie trägt alle drei Filamente"
    assert output.material_slots == [red, green, blue]


def test_the_stage_that_worked_is_recorded() -> None:
    """§17.2: die erfolgreiche Stufe wird in die Operation geschrieben."""
    result = boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))])

    assert result.solver.attempted == ("direct",)
    assert result.solver.seed is None


@pytest.mark.parametrize("stage", ["welded", "jittered", "voxel"])
def test_every_stage_can_carry_the_operation_alone(stage: str) -> None:
    """§35: jede Stufe einmal erzwungen — eine Kette, die niemand übt, ist
    eine Kette, die verrottet.
    """
    result = boolean(
        "union",
        [solid(), box(20.0, (10.0, 0.0, 0.0))],
        seed=20260728,
        stages=(stage,),  # type: ignore[arg-type]
    )

    assert result.solver.strategy == stage
    assert result.mesh.triangle_count > 0
    # Jitter bewegt Eckpunkte, Voxel runden auf ein Raster — beide tauschen
    # Genauigkeit gegen eine Antwort, und genau dafür sind die späteren Stufen
    # da (§17.2).
    tolerance = {"welded": 1e-6, "jittered": 1e-3, "voxel": 0.05}[stage]
    assert result.mesh.volume == pytest.approx(12000.0, rel=tolerance)


def test_the_voxel_stage_says_that_it_rounded() -> None:
    """§17.3: Stufe 4 kostet Genauigkeit und wird nie stillschweigend benutzt."""
    result = boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))], stages=("voxel",))

    codes = {finding.code for finding in result.findings}
    assert "boolean.voxel" in codes
    assert any(finding.severity == "warning" for finding in result.findings)


def test_the_voxel_stage_says_how_far_its_volume_is_off() -> None:
    """RM-246: Legt das Raster mehr zu, als die Operation erklärt, steht die Zahl im Befund.

    Eine Differenz nimmt vom ersten Körper höchstens das Werkzeug weg und fügt
    nichts hinzu. Am Laptop-Ständer wuchs das Volumen auf dem Raster um
    31 Prozent, und der Bericht sagte nur „gerundet". Eine Kugel zeigt dasselbe
    im Kleinen: Jede Zelle, die ihre Oberfläche berührt, zählt als Material.
    """
    sphere = MeshData.of(trimesh.creation.icosphere(subdivisions=3, radius=20.0))
    tool = MeshData.of(trimesh.creation.cylinder(radius=2.0, height=60.0))

    result = boolean("difference", [sphere, tool], stages=("voxel",))

    [finding] = [entry for entry in result.findings if entry.code == "boolean.voxel"]
    assert finding.severity == "warning"
    values = dict(finding.values or {})
    grown = float(result.mesh.raw.volume) - float(sphere.raw.volume)
    assert grown > 0.0
    assert values["deviation_mm3"] == pytest.approx(grown, rel=1e-9)
    assert values["share_percent"] == pytest.approx(100.0 * grown / float(sphere.raw.volume))
    # Die Zahl steht in den Werten, nicht im Satz.
    assert "{" not in finding.message.msgid


def test_the_voxel_stage_stays_short_when_its_volume_is_plausible() -> None:
    """RM-246: Innerhalb dessen, was die Operation bewirken kann, bleibt es bei „gerundet"."""
    result = boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))], stages=("voxel",))

    [finding] = [entry for entry in result.findings if entry.code == "boolean.voxel"]
    assert not finding.values


def test_the_jitter_stage_carries_its_seed() -> None:
    """§11.3: ohne gespeicherten Startwert wäre das Ergebnis nicht
    reproduzierbar.
    """
    first = boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))], seed=42, stages=("jittered",))
    second = boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))], seed=42, stages=("jittered",))
    other = boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))], seed=43, stages=("jittered",))

    assert first.solver.seed == 42
    # **Gleich heißt bitgleich.** Hier stand ein Volumenvergleich auf zwölf
    # Stellen, und den bestand auch ein Ergebnis mit anderen Ecken — dieselbe
    # Datei soll aber dasselbe Netz ergeben, nicht ein ähnlich großes (§11.3).
    assert np.array_equal(first.mesh.raw.vertices, second.mesh.raw.vertices)
    assert np.array_equal(first.mesh.raw.faces, second.mesh.raw.faces)
    # Und der Startwert muss etwas bewirken: Ein Stups, der jeden Startwert
    # gleich ausführt, bestünde die Zeilen darüber ebenso.
    assert not np.array_equal(first.mesh.raw.vertices, other.mesh.raw.vertices)


def test_the_jitter_stage_draws_the_same_on_every_machine() -> None:
    """RM-187: Der Stups kommt aus ganzen Zahlen, nicht aus der Mathebibliothek.

    ``Generator.normal`` zieht in NumPy über die Zikkurat, und deren Rand und
    Schwanz rechnen ``exp`` und ``log1p`` der Plattform — NumPy verspricht
    dort gleiche Werte nur „bis auf Rundung". Ein Stups, der auf einem Mac um
    eine letzte Stelle anders fällt, entscheidet bei einem Körper, dessen
    Flächen genau zusammenfallen, über ein anderes Netz; genau dafür ist die
    Stufe da. Gleichverteilt aus den Rohbits des Generators ist er dagegen
    Ganzzahlarithmetik und eine Multiplikation — auf jeder Maschine dieselbe.

    Der Sollwert entsteht hier aus den Rohbits selbst, nicht aus der Stufe.
    """
    from app.core.geom import boolean as chain

    body = MeshData.of(trimesh.creation.icosphere(subdivisions=3, radius=20.0))
    corners = np.asarray(body.raw.vertices, dtype=float)
    seed, index = 42, 1

    moved = np.asarray(chain._jitter(body, seed, index).raw.vertices, dtype=float)

    raw = np.random.PCG64(seed + index).random_raw(corners.size)
    unit = (raw >> np.uint64(11)).astype(np.float64) * 2.0**-53
    reach = max(body.bounds.diagonal, 1.0) * chain.JITTER_AMPLITUDE * math.sqrt(3.0)
    expected = corners + (unit.reshape(corners.shape) * 2.0 - 1.0) * reach
    assert np.array_equal(moved, expected)


def test_draft_quality_stops_after_the_second_stage() -> None:
    """§31: das Iterieren bleibt schnell, der Entwurf gibt also keine Zeit für
    Voxel aus.
    """
    assert DRAFT_CHAIN == ("direct", "welded")
    assert FULL_CHAIN[:2] == DRAFT_CHAIN
    assert "voxel" in FULL_CHAIN and "voxel" not in DRAFT_CHAIN


def test_an_impossible_operation_ends_with_a_finding_and_a_way_forward() -> None:
    """§17.2 Stufe 5: aufgeben ist erlaubt, still aufgeben nicht."""
    with pytest.raises(BooleanFailedError) as caught:
        boolean(
            "intersection",
            [solid(), box(2.0, (500.0, 0.0, 0.0))],
            stages=("direct", "welded"),
        )

    assert caught.value.attempted == ("direct", "welded")
    assert caught.value.suggestions, "an error without a way forward is unfinished"


def test_at_least_two_bodies_are_needed() -> None:
    with pytest.raises(ValueError):
        boolean("union", [solid()])


# --- as operations --------------------------------------------------------------


def two_body_document(document, profile):
    """Zwei überlappende Würfel in einem Dokument, bereit für eine Boolesche
    Operation.
    """
    from app.core.registry import REGISTRY
    from app.core.scene import History, OperationDraft
    from app.core.scene.project import new_project
    from app.core.types import Source
    from app.i18n import _

    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    for index, name in enumerate(("cube_clean.stl", "cube_clean.stl"), start=1):
        document.sources[f"src_{index}"] = Source(
            id=f"src_{index}", kind="import", path=f"sources/{index}_{name}", sha256=""
        )
        project.sources[f"src_{index}"] = (MESHES / name).read_bytes()

    history = History(document)
    history.apply(
        _("Laden"),
        [
            OperationDraft(op="load", params={"source": "src_1", "unit": "mm"}),
            OperationDraft(op="load", params={"source": "src_2", "unit": "mm"}),
        ],
    )
    history.apply(
        _("Verschieben"),
        [OperationDraft(op="translate_object", inputs=("obj_2",), params={"dx": 10.0})],
    )
    assert REGISTRY.has("union_objects")
    return project, history


def test_a_boolean_operation_records_its_stage(document, profile) -> None:
    """§17.2: die Stufe, die die Operation getragen hat, wird in den Stapel
    geschrieben.
    """
    from app.core.scene import OperationDraft, evaluate
    from app.core.scene.project import ProjectSources
    from app.i18n import _

    project, history = two_body_document(document, profile)
    history.apply(
        _("Vereinigen"),
        [OperationDraft(op="union_objects", inputs=("obj_1", "obj_2"))],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    # Zwei Körper hinein, einer heraus — und der eine ist der **erste**: Das
    # Vereinigen setzt fort, was der Nutzer zuerst angeklickt hat, mit seiner
    # Kennung, seinem Namen und seinem Material (``keeps_inputs=1``). Der
    # zweite ist verbraucht.
    assert result.scene.objects["obj_1"].mesh.volume == pytest.approx(12000.0, rel=1e-6)
    assert "obj_2" not in result.scene.objects, "der zweite Körper ist aufgegangen"

    union_op = history.operations[-1]
    assert union_op.seed is not None, "a randomised operation carries a seed (§11.3)"
    assert result.solvers[union_op.id].strategy == "direct"

    history.record_solvers(result.solvers)
    assert history.operation(union_op.id).solver is not None
    assert history.operation(union_op.id).solver.strategy == "direct"


def test_subtracting_and_intersecting_run_as_operations(document, profile) -> None:
    from app.core.scene import OperationDraft, evaluate
    from app.core.scene.project import ProjectSources
    from app.i18n import _

    project, history = two_body_document(document, profile)
    history.apply(
        _("Abziehen"),
        [OperationDraft(op="subtract_objects", inputs=("obj_1", "obj_2"))],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))
    assert result.scene.objects["obj_1"].mesh.volume == pytest.approx(4000.0, rel=1e-6)
    assert "obj_2" not in result.scene.objects, "both inputs were consumed"


def test_intersect_objects_runs_as_an_operation(document, profile) -> None:
    from app.core.scene import OperationDraft, evaluate
    from app.core.scene.project import ProjectSources
    from app.i18n import _

    project, history = two_body_document(document, profile)
    history.apply(
        _("Schnittmenge"),
        [OperationDraft(op="intersect_objects", inputs=("obj_1", "obj_2"))],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))
    assert result.complete
    assert result.scene.objects["obj_1"].mesh.volume == pytest.approx(4000.0, rel=1e-6)


# --- Eine boolesche Op, die nichts bewirkt, sagt das (§2.7, operationen.md) ------


def test_subtracting_a_body_that_does_not_touch_says_so() -> None:
    """„Wer Boolesches rechnet, fragt danach — ohne Ausnahme." Ein Abzugskörper
    weit neben dem Teil trägt nichts ab, und das stand nirgends: ein Schritt im
    Verlauf, dasselbe Teil im Bild."""
    result = run_op("subtract_objects", solid(), box(20.0, (100.0, 0.0, 0.0)))

    assert result.outputs[0].mesh.volume == pytest.approx(8000.0, rel=1e-6)
    assert "boolean.without_effect" in [finding.code for finding in result.findings]


def test_a_union_that_adds_nothing_says_so() -> None:
    """Ein Körper, der ganz im anderen steckt, fügt der Vereinigung nichts
    hinzu — dieselbe Auskunft, andersherum."""
    result = run_op("union_objects", solid(), box(4.0, (0.0, 0.0, 0.0)))

    assert result.outputs[0].mesh.volume == pytest.approx(8000.0, rel=1e-6)
    assert "boolean.without_effect" in [finding.code for finding in result.findings]


def test_an_intersection_of_two_separate_bodies_says_it_is_empty() -> None:
    """Zwei Körper, die sich nicht treffen, haben keine Schnittmenge. Statt die
    ganze Rückfallkette bis zur Voxelstufe zu fahren und dann „das Werkzeug
    deckt ihn vollständig ab" zu melden, hält die Operation sofort an und nennt
    den zutreffenden Grund."""
    with pytest.raises(GeometryError) as problem:
        run_op("intersect_objects", solid(), box(20.0, (100.0, 0.0, 0.0)))

    assert problem.value.suggestions, "Regel 17: der Fehler nennt einen Weg"
    said = f"{problem.value.title} {problem.value.detail}"
    assert "gemeinsam" in said.lower(), "der zutreffende Grund, nicht der der Vereinigung"
    assert "deckt" not in said, "nicht die alte, falsche Begründung aus der Rückfallkette"


# --- Ein falscher Aufruf ist keine Antwort (§33.1) -------------------------------


def test_a_wrong_call_into_the_kernel_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Lektion der konvexen Zerlegung, dort festgehalten, wo es geht.

    Handler um einen Kern fangen breit, denn ein Kern scheitert auf Kernarten,
    und das ist eine Antwort. Ein TypeError ist keine: er heißt, dass der
    Aufruf falsch ist, und ihn zu verschlucken macht aus einem Fehler ein leeres
    Ergebnis. Die Zerlegung aus §22.3 tat genau das, zwei Phasen lang, hinter
    einer grünen Suite.
    """

    import manifold3d

    def wrong(*_args: object, **_kwargs: object) -> None:
        raise TypeError("intersection(): incompatible function arguments")

    monkeypatch.setattr(manifold3d, "Manifold", wrong)

    with pytest.raises(TypeError):
        shared_volume(solid().raw, solid().raw)


def test_the_fallback_chain_does_not_swallow_a_wrong_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Dieselbe Regel eine Ebene höher — dort, wo sie am meisten verdeckt.

    ``shared_volume`` ließ Programmfehler durch, die Rückfallkette nicht: Sie
    fing jede Ausnahme, notierte „Stufe gescheitert" ins Protokoll und probierte
    die nächste. Ein falscher Aufruf sah damit aus wie vier Kerne, die nacheinander
    aufgeben — und der Nutzer las am Ende, seine Geometrie sei schuld.

    Die Stufen rufen mit eigenen Argumenten (``voxelized(pitch=...)``,
    ``matrix_to_marching_cubes(matrix=..., pitch=...)``), also gilt hier genau
    die Vorsichtsmaßnahme, die ``errors.PROGRAMMING_ERRORS`` beschreibt.
    """

    import manifold3d

    def wrong(*_args: object, **_kwargs: object) -> None:
        raise TypeError("union(): incompatible function arguments")

    monkeypatch.setattr(manifold3d, "Manifold", wrong)

    with pytest.raises(TypeError):
        boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))])


def test_a_kernel_that_gives_up_is_still_an_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die andere Hälfte der Regel: wofür der Handler wirklich da ist, bleibt
    gefangen.
    """

    import manifold3d

    def gave_up(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("manifold: could not solve")

    monkeypatch.setattr(manifold3d, "Manifold", gave_up)

    assert shared_volume(solid().raw, solid().raw) == 0.0


def test_an_emptied_body_says_so_instead_of_blaming_the_solver() -> None:
    """Kein Rückfall hilft gegen Maße.

    Eine Bohrung mit 200 mm Durchmesser in einer 80er Platte frisst sie ganz.
    Vier Stufen liefen durch, und der Nutzer las am Ende „Auch die letzte
    Rückfallstufe hat kein brauchbares Ergebnis geliefert" — die Sprache des
    Rechenkerns für etwas, das aus den Maßen folgt, und ohne den
    Handlungsvorschlag, den Regel 17 verlangt.
    """
    plate = MeshData.of(trimesh.creation.box(extents=(80.0, 50.0, 8.0)))
    tool = MeshData.of(trimesh.creation.box(extents=(300.0, 300.0, 300.0)))

    with pytest.raises(BooleanFailedError) as caught:
        boolean("difference", [plate, tool])

    detail = str(caught.value.detail)
    assert "bleibt nichts übrig" in detail, "der Satz sagt, was zu sehen wäre"
    assert "Rückfallstufe" not in detail, "und nicht, woran der Kern gescheitert ist"
    assert any(action.id == "correct_input" for action in caught.value.suggestions), (
        "die Handlung ist nachrechnen, nicht reparieren"
    )
    # **Und der Titel dazu.** Er blieb der Vorgabetitel der Klasse — „Die
    # boolesche Operation ist auf allen Stufen gescheitert." — und stand damit
    # über einem Detailsatz, der das Gegenteil sagt. Der Dialog zeichnet den
    # Titel groß und das Detail klein: Wer hinsieht, liest zuerst, der Kern sei
    # gescheitert, und sucht einen Netzfehler statt einer falschen Zahl.
    title = str(caught.value.title)
    assert "gescheitert" not in title, f"der Titel widerspricht seinem eigenen Detail: {title!r}"
    assert "kein Körper" in title, title


@pytest.mark.parametrize("way", ["drill", "slot_bore", "resize_bore"])
def test_cancelling_during_the_parts_preflight_stops_the_bore(
    way: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Bohrwege reichen den Abbruch bis in die Vorfrage (RM-381, §2.8).

    Am Besenhalter liefen die Sekunden der Vorfrage ungebremst, weil
    ``prepare.drill``, ``slot_bore`` und ``resize_bore`` kein ``cancelled``
    an ``boolean()`` gaben. Hier wird während der Vorfrage abgebrochen.
    """
    from app.core.geom import boolean as boolean_module
    from app.core.geom import prepare
    from app.core.knowledge import profiles
    from app.core.scene.cancel import CancelSignal

    token = CancelSignal()
    real = boolean_module.parts_that_cross

    def cancelled_while_searching(*args: object, **kwargs: object) -> object:
        token.cancel()
        return real(*args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(boolean_module, "parts_that_cross", cancelled_while_searching)
    body = two_cubes(30.0)
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    common: dict[str, object] = {"profile": profile, "cancelled": token}
    with pytest.raises(OperationCancelled):
        if way == "drill":
            prepare.drill(body, position=(0.0, 0.0, 10.0), axis="z", diameter=3.0, **common)
        elif way == "slot_bore":
            prepare.slot_bore(
                body,
                position=(0.0, 0.0, 0.0),
                direction=(0.0, 0.0, 1.0),
                diameter=3.0,
                depth=20.0,
                through=True,
                length=8.0,
                angle_deg=0.0,
                overlap=0.0,
                **common,
            )
        else:
            prepare.resize_bore(
                body,
                position=(0.0, 0.0, 0.0),
                direction=(0.0, 0.0, 1.0),
                previous_diameter=0.0,
                diameter=3.0,
                depth=20.0,
                through=True,
                **common,
            )


def test_a_cancelled_chain_stops_before_the_first_stage() -> None:
    """§15.6: Vier Kernversuche plus Voxelisierung an einem großen Netz waren
    als Ganzes unabbrechbar — das Token wird jetzt zwischen den Stufen
    gefragt, und der Abbruch ist eine ``OperationCancelled``, kein Befund."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    signal = CancelSignal()
    signal.cancel()

    with pytest.raises(OperationCancelled):
        boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))], cancelled=signal)


def test_a_boolean_keeps_the_feature_names_where_they_were(document, profile) -> None:
    """Ein Bohrungsname zeigt nach dem Abziehen auf dieselbe Bohrung wie davor.

    **Das war der teuerste Teil des Kennungsfehlers, und er ist kein
    Anzeigefehler.** Die Merkmale des Vorgängers hängen an seiner
    Eingangskennung; bekam der Ausgang eine frische, griff die Zuordnung ins
    Leere und vergab die Namen neu — nach Lage sortiert. Eine Senkung oder ein
    Gewinde, das an ``hole_1`` hängt, sitzt danach am falschen Loch, und
    gemeldet wird nichts (§21.2).

    **Der Aufbau muss die Sortierung kippen lassen, sonst prüft er nichts.**
    Der erste Anlauf verschob das Werkzeug so, dass die Reihenfolge gleich
    blieb — der Test war grün, auch ohne die Deklaration. Hier wandert das
    Werkzeug von der einen Seite des gebohrten Lochs auf die andere: Ohne
    ``keeps_inputs`` trägt danach ein anderes Loch den Namen ``hole_1``.
    """
    from app.core.bootstrap import load_operations
    from app.core.scene import History, OperationDraft, evaluate
    from app.i18n import _

    load_operations()
    history = History(document)
    history.apply(
        _("Platte"),
        [OperationDraft(op="create_box", params={"width": 80.0, "depth": 80.0, "height": 10.0})],
    )
    history.apply(
        _("Loch"),
        [
            OperationDraft(
                op="drill_hole", inputs=("obj_1",), params={"diameter": 5.0, "x": 0.0, "y": 0.0}
            )
        ],
    )
    history.apply(_("Werkzeug"), [OperationDraft(op="create_cylinder", params={"diameter": 5.0})])
    tool = document.ops[-1].outputs[0]
    history.apply(
        _("Setzen"),
        [
            OperationDraft(
                op="translate_object",
                inputs=(tool,),
                params={"dx": -25.0, "dy": -25.0, "dz": -5.0},
            )
        ],
    )
    history.apply(
        _("Abziehen"), [OperationDraft(op="subtract_objects", inputs=("obj_1", tool), params={})]
    )

    def holes() -> dict[str, tuple[float, float]]:
        found: dict[str, tuple[float, float]] = {}
        for entry in evaluate(document, profile).scene.objects.values():
            for name, feature in entry.features.items():
                centre = feature.params.get("centre") if feature.kind == "hole" else None
                if centre:
                    found[name] = (round(float(centre[0]), 1), round(float(centre[1]), 1))
        return found

    before = holes()
    assert len(before) == 2, f"der Aufbau braucht zwei Bohrungen, hat aber {before}"
    drilled = next(name for name, place in before.items() if place == (0.0, 0.0))

    # Das Werkzeug wandert auf die andere Seite — die Sortierung kippt.
    moved = next(entry for entry in history.operations if entry.op == "translate_object")
    history.change_params(moved.id, {"dx": 25.0, "dy": 25.0, "dz": -5.0})
    after = holes()

    assert after[drilled] == (0.0, 0.0), (
        f"{drilled} zeigt jetzt auf eine andere Bohrung: {before} -> {after}"
    )


@pytest.mark.parametrize("overlap", [0.05, 0.01, 0.001, 0.0])
def test_coplanar_faces_survive_every_overlap(overlap: float) -> None:
    """Die Zugabe schützt vor einem Bruch, den dieser Kern nicht mehr hat.

    ``BOOLEAN_OVERLAP`` stand an drei Stellen mit zwei Werten — zuletzt sogar
    zweimal unter demselben Namen (``geom/boolean.py`` 0,05,
    ``geom/prepare.py`` 0,01), beide importiert. Damit hing es am Importpfad,
    welche Zugabe eine Operation bekam.

    Die Messung hat die Frage verschoben: nicht „welcher Wert ist richtig",
    sondern „wirkt der Wert überhaupt". Drei koplanare Lagen, jede mit vier
    Zugaben bis hinunter zu **null** — alle über Stufe 1, alle wasserdicht,
    alle mit exaktem Volumen. ``manifold3d`` ist feste Abhängigkeit und rechnet
    zusammenfallende Flächen robust.

    Der Test hält diese Aussage fest, damit die eine Zahl nicht wieder zu
    zweien wird: Wer sie ändert, ändert nichts an der Rechnung — und wer sie
    verdoppelt, hat keinen Grund dafür.
    """
    plate = MeshData.of(trimesh.creation.box(extents=[40, 30, 10]))

    through = trimesh.creation.box(extents=[10, 10, 10 + overlap])
    through.apply_translation([0, 0, overlap / 2])
    on_top = trimesh.creation.box(extents=[8, 8, 4 + overlap])
    on_top.apply_translation([0, 0, 5 + (4 - overlap) / 2])
    at_the_side = trimesh.creation.box(extents=[10 + overlap, 8, 4])
    at_the_side.apply_translation([20 - (10 - overlap) / 2, 0, 0])

    for kind, tool, expected in (
        ("difference", through, 11000.0),
        ("union", on_top, 12256.0),
        ("difference", at_the_side, 11680.0),
    ):
        outcome = boolean(kind, [plate, MeshData.of(tool)], quality="fine")
        assert outcome.solver.strategy == "direct", (
            f"{kind} mit {overlap} mm Zugabe fiel auf {outcome.solver.strategy} zurück"
        )
        assert outcome.mesh.is_watertight, f"{kind} mit {overlap} mm ließ ein offenes Netz"
        assert outcome.mesh.volume == pytest.approx(expected, abs=0.5), (
            f"{kind} mit {overlap} mm: {outcome.mesh.volume:.1f} statt {expected}"
        )


def test_the_overlap_is_one_number_for_the_whole_core() -> None:
    """Wer die Zugabe braucht, importiert sie — er schreibt sie nicht ab.

    Drei Stellen trugen sie einmal, und zwei davon unter demselben Namen mit
    verschiedenen Zahlen. Am Namen sah man den Unterschied nicht; am Ergebnis
    auch nicht, denn die Zugabe liegt außerhalb des Materials. Genau deshalb
    wäre es unbemerkt geblieben.
    """
    import ast
    from pathlib import Path as _Path

    core = _Path(__file__).resolve().parent.parent / "app" / "core"
    defined: list[str] = []
    for path in sorted(core.rglob("*.py")):
        for node in ast.parse(path.read_text(encoding="utf-8")).body:
            names = [t.id for t in getattr(node, "targets", []) if isinstance(t, ast.Name)]
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                names = [node.target.id]
            if any(name in ("BOOLEAN_OVERLAP", "OVERLAP") for name in names):
                defined.append(path.name)
    assert defined == ["boolean.py"], f"die Zugabe steht an {len(defined)} Stellen: {defined}"


def test_an_empty_result_in_draft_quality_points_at_the_stages_left() -> None:
    """„Nichts übrig" ist keine Aussage über die Maße, solange Stufen offen sind.

    Der Test darüber gilt der **vollen** Kette, und dort stimmt der Satz. Im
    Fenster läuft die kurze (:data:`DRAFT_CHAIN`, §31), und dieselbe Handlung
    an demselben Körper endete dort mit „Prüfen Sie Maß und Lage" — ohne einen
    Weg weiter und mit einer Ursache, die es nicht war.

    Gemessen am Mast des Piratenschiffs (``obj_1_Cylinder.stl``, Ø 5 auf
    115 mm, 04.09.2026): ``resize_feature`` liefert über *direkt* und
    *verschweißt* nichts, und die dritte Stufe löst es (Befund
    ``boolean.jittered``). In feiner Qualität bekam der Kunde sein Ergebnis, in
    Entwurfsqualität eine Absage — dieselbe Datei, derselbe Klick.
    """
    plate = MeshData.of(trimesh.creation.box(extents=(80.0, 50.0, 8.0)))
    tool = MeshData.of(trimesh.creation.box(extents=(300.0, 300.0, 300.0)))

    with pytest.raises(BooleanFailedError) as caught:
        boolean("difference", [plate, tool], quality="draft")

    detail = str(caught.value.detail)
    assert "Rechenstufen" in detail, f"der Satz nennt die offenen Stufen nicht: {detail!r}"
    assert "Maß und Lage" not in detail, (
        f"er behauptet weiter eine Ursache, die nicht feststeht: {detail!r}"
    )
    assert any(action.id == "use_voxel_stage" for action in caught.value.suggestions), (
        "der Weg zur vollständigen Kette fehlt — genau die Handlung, die hier hilft"
    )
    # Und der Titel kommt aus derselben Entscheidung wie die Handlung: Die
    # Ausnahme wählt ihn danach, ob die Voxelstufe dran war. Zwei Stellen für
    # dieselbe Frage liefen auseinander, sobald jemand eine davon ändert.
    assert "schnellen Rechnung" in str(caught.value.title), str(caught.value.title)


def test_the_voxel_stage_refuses_a_grid_it_cannot_afford(caplog: pytest.LogCaptureFixture) -> None:
    """Gesamtreview 05.09.2026, G-13: Die Rasterweite folgt der größten
    Einzeldiagonale, die Ausdehnung dem gemeinsamen Hüllquader. Zwei
    1-mm-Würfel, einer um (1000, 1000, 1000) verschoben, forderten bei 0,05 mm
    Rasterweite 20025³ Zellen an — acht Terabyte, ohne Budget vor
    ``np.zeros``. Die Stufe gibt jetzt auf, bevor sie allokiert."""
    from app.core.geom import boolean as boolean_module

    near = box(1.0, (0.0, 0.0, 0.0))
    far = box(1.0, (1000.0, 1000.0, 1000.0))

    with caplog.at_level("WARNING"):
        assert boolean_module._voxel("union", [near, far]) is None
    assert any("budget" in record.message for record in caplog.records)


def test_the_voxel_grid_of_a_difference_spans_only_the_body_that_shrinks() -> None:
    """Eine Differenz macht den ersten Körper nur kleiner: Das Werkzeug daneben
    braucht keine Zellen. Der ferne Würfel wird damit rechenbar, statt das
    Raster über tausend Millimeter Leere zu spannen."""
    from app.core.geom import boolean as boolean_module

    near = box(10.0, (0.0, 0.0, 0.0))
    far = box(1.0, (1000.0, 1000.0, 1000.0))

    result = boolean_module._voxel("difference", [near, far])

    assert result is not None
    assert result.volume == pytest.approx(near.volume, rel=0.05), "das ferne Werkzeug trifft nichts"


def _needled_cube(size: float = 10.0) -> trimesh.Trimesh:
    """Ein dichter Würfel, in dessen Deckfläche eine Nadel sitzt.

    Das erste Dreieck ``[a, b, c]`` wird zu ``[a, p, c]``, ``[p, b, c]`` und
    ``[a, b, p]`` — ``p`` liegt in der Fläche, eine Zehntel-Mikrometer neben der
    Kante ``ab``. Das dritte Dreieck hat drei verschiedene Ecken, keine Höhe und
    ist an ``ab`` der einzige Nachbar des Dreiecks von nebenan: Wer es
    streicht, reißt dort ein Loch.
    """
    box = trimesh.creation.box(extents=(size, size, size))
    faces = box.faces.tolist()
    a, b, c = faces[0]
    va, vb, vc = box.vertices[[a, b, c]]
    inward = (vc - (va + vb) / 2.0) / float(np.linalg.norm(vc - (va + vb) / 2.0))
    p = (va + vb) / 2.0 + inward * 1e-7
    vertices = np.vstack([box.vertices, p])
    q = len(vertices) - 1
    faces = [[a, q, c], [q, b, c], [a, b, q], *faces[1:]]
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def test_the_welded_stage_keeps_a_needle_that_holds_a_closed_tool_together() -> None:
    """Stufe 2 entnadelt die Eingänge — und macht dabei kein dichtes Netz auf (RM-166).

    Dieselbe Zusicherung wie beim Import und in ``repair()``. Der Fall kam
    mit dem Überstand der Fasenkeile: Zwölf Keilstücke um einen Bohrkreis
    vereinigen sich zu einem Werkzeug mit Nadeln an den Stoßstellen, roh
    dicht; die Stufe strich die Nadeln, und ``_kernel`` wies das Werkzeug als
    „nicht positiv geschlossen" ab — an einer nur verschweißten Platte lief
    die Kette bis in die Voxel, und in der Vorschau brach sie ab.
    """
    from app.core.geom.boolean import _welded_input
    from app.core.geom.repair import remove_degenerate_faces

    tool = MeshData.of(_needled_cube())
    assert tool.is_watertight, "die Nadel hält das Werkzeug zusammen"
    stripped, dropped = remove_degenerate_faces(tool)
    assert dropped == 1 and not stripped.is_watertight, (
        "ohne diese Voraussetzung prüft der Test nichts: das Streichen muss reißen"
    )

    kept = _welded_input(tool)
    assert kept.is_watertight, "die Stufe lässt die Nadel stehen, statt das Netz aufzureißen"

    body = MeshData.of(trimesh.creation.box(extents=(30.0, 30.0, 30.0)))
    outcome = boolean("difference", [body, tool], stages=("welded",))
    assert outcome.solver.strategy == "welded"
    assert outcome.mesh.is_watertight
    assert outcome.mesh.raw.volume == pytest.approx(27000.0 - 1000.0, abs=1e-6)


def test_a_boolean_keeps_the_origin_of_every_triangle_it_did_not_cut() -> None:
    """Der Ursprung je Dreieck nach *Kanten verfeinern* überlebt eine Bohrung (R1-Rest).

    Die Erkennung zählt die Stücke eines Ursprungs als eines
    (``geom.mesh.refined_units``); nach der nächsten Booleschen Operation
    erkennt sie frisch, und ohne den Ursprung zählte sie wieder jedes Stück.
    Jedes Dreieck, das der Schnitt nicht berührt, übernimmt der Kern
    bitgleich — es behält seinen Ursprung. Was der Schnitt neu baut, hat
    keinen. Zwei geteilte Eingänge behalten verschiedene Nummern.
    """
    from app.core.geom.mesh import refined_units
    from app.core.geom.mesh_ops import remesh

    refined = remesh(box(20.0, (0.0, 0.0, 0.0)), 2.0)
    before = refined_units(refined.raw)
    assert before is not None
    tool = MeshData.of(trimesh.creation.cylinder(radius=3.0, height=40.0, sections=32))

    cut = boolean("difference", [refined, tool]).mesh
    after = refined_units(cut.raw)
    assert after is not None, "die Bohrung hat den Ursprung verloren"
    kept = after >= 0
    assert 0 < int((~kept).sum()) < len(after), "Schnittflächen ohne Ursprung, der Rest mit"
    # Jedes Dreieck mit Ursprung steht bitgleich im Eingang, mit demselben Ursprung.
    old = {
        tuple(sorted(map(tuple, triangle))): unit
        for triangle, unit in zip(
            np.asarray(refined.raw.triangles).tolist(), before.tolist(), strict=True
        )
    }
    triangles = np.asarray(cut.raw.triangles).tolist()
    for triangle, unit in zip(triangles, after.tolist(), strict=True):
        if unit >= 0:
            assert old[tuple(sorted(map(tuple, triangle)))] == unit

    other = remesh(box(20.0, (30.0, 0.0, 0.0)), 2.0)
    joined = refined_units(boolean("union", [refined, other]).mesh.raw)
    assert joined is not None
    assert np.unique(joined[joined >= 0]).size == 2 * np.unique(before).size, (
        "zwei geteilte Körper teilen sich keine Nummer"
    )


def test_a_boolean_keeps_the_layout_of_every_triangle_it_did_not_cut() -> None:
    """Was der Schnitt nicht berührt, behält Eckenfolge und Eckenreihenfolge (RM-261).

    ``manifold3d`` übernimmt ein unberührtes Dreieck mit denselben drei Ecken,
    beginnt es aber an einer anderen Ecke und nummeriert die Ecken neu. Die
    Erkennung rechnet Normalen aus der Eckenfolge und summiert in der
    Reihenfolge der Ecken; nach der ersten Booleschen las sie deshalb jeden
    Fleck mit anderen letzten Stellen. Der Eingang hier ist absichtlich
    durcheinander nummeriert und gedreht — so, wie ihn der Kern nie liefern
    würde. Die Dreiecksfolge und die Geometrie bleiben die des Kerns.
    """
    from app.core.geom import attributes
    from app.core.geom.boolean import _run_stage
    from app.core.geom.mesh_ops import remesh

    refined = remesh(box(20.0, (0.0, 0.0, 0.0)), 2.0).raw
    rng = np.random.default_rng(261)
    order = rng.permutation(len(refined.vertices))
    renumbered = np.empty(len(order), dtype=np.int64)
    renumbered[order] = np.arange(len(order))
    turns = rng.integers(0, 3, size=len(refined.faces))
    faces = renumbered[np.asarray(refined.faces, dtype=np.int64)]
    faces = faces[np.arange(len(faces))[:, None], (np.arange(3)[None, :] + turns[:, None]) % 3]
    source = MeshData.of(trimesh.Trimesh(np.asarray(refined.vertices)[order], faces, process=False))
    tool = MeshData.of(trimesh.creation.cylinder(radius=3.0, height=40.0, sections=32))

    cut = boolean("difference", [source, tool]).mesh
    kernel = _run_stage("difference", [source, tool], "direct", None)
    assert kernel is not None
    # Dieselben Dreiecke in derselben Folge und dieselben Orte: umgelegt, nicht umgebaut.
    assert cut.triangle_count == kernel.triangle_count
    assert np.array_equal(
        np.sort(np.asarray(cut.raw.triangles).reshape(-1, 9), axis=1),
        np.sort(np.asarray(kernel.raw.triangles).reshape(-1, 9), axis=1),
    )
    match = attributes._same_triangles(source.raw, cut.raw)
    kept = np.flatnonzero(match >= 0)
    assert 0 < len(kept) < cut.triangle_count, "ein Teil übernommen, der Schnitt neu"
    # Jedes übernommene Dreieck beginnt an derselben Ecke wie sein Vorbild ...
    assert np.array_equal(
        np.asarray(cut.raw.triangles)[kept], np.asarray(source.raw.triangles)[match[kept]]
    )
    assert np.array_equal(
        np.asarray(cut.raw.face_normals)[kept], np.asarray(source.raw.face_normals)[match[kept]]
    )
    # ... und seine Ecken stehen in der Reihenfolge des Eingangs.
    ours = np.asarray(cut.raw.faces, dtype=np.int64)[kept].ravel()
    theirs = np.asarray(source.raw.faces, dtype=np.int64)[match[kept]].ravel()
    pairs = np.unique(np.column_stack((ours, theirs)), axis=0)
    assert len(np.unique(pairs[:, 0])) == len(pairs), "jede Ecke hat genau ein Vorbild"
    assert np.all(np.diff(pairs[:, 1]) > 0), "die übernommenen Ecken folgen dem Eingang"
    # Der Kern selbst tat es nicht — sonst prüfte der Test nichts.
    rotated = np.asarray(kernel.raw.triangles)[kept]
    assert not np.array_equal(rotated, np.asarray(source.raw.triangles)[match[kept]])
