"""Nachbau: registrierte Schritte, unabhängige Formprüfung und atomarer Verlauf."""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.helpers import exact_kernel

exact_kernel()

from app.core.scene import History  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Profile, Source  # noqa: E402

MESHES = Path(__file__).parent / "data" / "meshes"


def imported(name: str):
    return imported_payload(name, (MESHES / name).read_bytes())


def imported_payload(name: str, payload: bytes):
    """Ein Projekt, das ``payload`` als Datei ``name`` in Millimetern einliest."""
    from dataclasses import replace

    from app.core.bootstrap import load_operations
    from app.core.ingest.plan import import_plan

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = payload
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/{name}", sha256=""
    )
    plan = import_plan("src_1", name, payload)
    History(project.document).apply(
        plan.title, [replace(plan.draft, params={**plan.draft.params, "unit": "mm"})]
    )
    return project


@pytest.mark.parametrize(
    "name, expected",
    [
        ("plate_holes.stl", ["create_brep_box", *["drill_brep_hole"] * 4]),
        ("plate_countersunk.stl", ["create_brep_box", "drill_brep_hole"]),
        ("plate_coarse_slots.stl", ["create_brep_box", "drill_brep_hole", "drill_brep_hole"]),
        ("dense_cylinder.stl", ["create_brep_cylinder"]),
        ("torus_ring.stl", ["create_brep_torus"]),
        ("sphere_socket.stl", ["create_brep_box", "create_brep_sphere", "subtract_objects"]),
    ],
)
def test_corpus_has_an_exact_editable_construction(
    name: str, expected: list[str], profile: Profile
):
    from app.core.scene.rebuild import RebuildBudget, propose
    from app.core.scene.serialise import document_to_data

    project = imported(name)
    before = document_to_data(project.document)
    proposals = propose(
        project.document,
        "obj_1",
        profile,
        sources=ProjectSources(project),
        budget=RebuildBudget(local_mm=0.2, volume_relative=0.02),
    )
    assert proposals.accepted, [
        (entry.check.reason, entry.check.surface) for entry in proposals.candidates
    ]
    chosen = proposals.accepted[0]
    assert [draft.op for draft in chosen.drafts] == expected
    assert chosen.result.kind == "brep"
    assert chosen.result.mesh.is_watertight
    assert all(
        draft.params.get("compensate") is False for draft in chosen.drafts if "drill" in draft.op
    )
    assert before == document_to_data(project.document)


@pytest.mark.parametrize("name", ("bridge_two_end_supports.ply", "island_tower.stl"))
def test_a_full_box_cannot_pass_for_a_bridge_or_step(name: str, profile: Profile):
    from app.core.scene.rebuild import RebuildBudget, propose

    project = imported(name)
    proposals = propose(
        project.document,
        "obj_1",
        profile,
        sources=ProjectSources(project),
        budget=RebuildBudget(local_mm=0.1, volume_relative=0.01),
    )
    boxes = [
        entry
        for entry in proposals.candidates
        if [step.op for step in entry.drafts] == ["create_brep_box"]
    ]
    assert boxes
    assert all(not entry.check.accepted for entry in boxes)


@pytest.mark.parametrize("name", ("bridge_two_end_supports.ply", "island_tower.stl"))
def test_planar_steps_have_an_exact_construction_without_filling_the_air(
    name: str, profile: Profile
):
    from app.core.scene.rebuild import RebuildBudget, propose

    project = imported(name)
    proposal = propose(
        project.document,
        "obj_1",
        profile,
        sources=ProjectSources(project),
        budget=RebuildBudget(0.1, 0.01),
    )
    assert proposal.accepted, [entry.check.reason for entry in proposal.candidates]
    chosen = proposal.accepted[0]
    assert any(draft.op == "sketch_extrude" for draft in chosen.drafts)
    assert chosen.result.mesh.volume == pytest.approx(proposal.source.mesh.volume, rel=1e-6)
    assert chosen.check.surface is not None and chosen.check.surface.within_limit


def _as_stl(solid) -> bytes:
    """Der exakte Körper als binäre STL, wie ein fremdes Programm sie schriebe."""
    import io

    import numpy as np
    import trimesh

    from app.core.geom.mesh import as_mesh_data

    twin = as_mesh_data(solid)
    stream = io.BytesIO()
    trimesh.Trimesh(
        vertices=np.asarray(twin.raw.vertices), faces=np.asarray(twin.raw.faces), process=False
    ).export(stream, file_type="stl")
    return stream.getvalue()


def _stepped_part(name: str):
    """Gestufte Grundformen aus Konzept §§8.2 und 13.5, am exakten Kern gebaut."""
    import math

    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Line

    from app.core.brep import edit

    def drilled(solid, x: float, top: float, depth: float):
        tool = edit.moved(edit.cylinder(4.0, depth), (x, 0.0, top - depth))
        return edit.boolean("difference", [solid, tool])

    def straight(solid, direction, near) -> tuple[str, ...]:
        return tuple(
            edit.edge_key(edge)
            for edge in edit.edges_of(solid)
            if BRepAdaptor_Curve(edge.edge).GetType() == GeomAbs_Line
            and abs(sum(a * b for a, b in zip(edge.direction, direction, strict=True))) > 0.999
            and near(edge.middle)
        )

    upright = edit.moved(edit.box(4.0, 20.0, 30.0), (-18.0, 0.0, 0.0))
    bracket = edit.unified(edit.boolean("union", [edit.box(40.0, 20.0, 4.0), upright]))
    high = edit.moved(edit.box(30.0, 20.0, 8.0), (15.0, 0.0, 0.0))
    steps = edit.unified(edit.boolean("union", [edit.box(60.0, 20.0, 4.0), high]))
    if name == "bracket":
        return drilled(drilled(bracket, 5.0, 4.0, 4.0), 12.0, 4.0, 4.0)
    if name == "stepped_plate":
        return drilled(drilled(steps, -15.0, 4.0, 4.0), 15.0, 8.0, 8.0)
    if name == "ledge":
        cut = edit.moved(edit.box(10.0, 30.0, 4.0), (15.0, 0.0, 6.0))
        return edit.boolean("difference", [edit.box(40.0, 30.0, 10.0), cut])
    if name == "pocket":
        cut = edit.moved(edit.box(16.0, 12.0, 4.0), (0.0, 0.0, 6.0))
        return drilled(edit.boolean("difference", [edit.box(40.0, 30.0, 10.0), cut]), 0.0, 6.0, 6.0)
    if name == "stairs":
        blocks = [
            edit.moved(edit.box(10.0, 20.0, 5.0 * (n + 1)), (-10.0 + 10.0 * n, 0.0, 0.0))
            for n in range(3)
        ]
        return edit.unified(edit.boolean("union", blocks))
    if name == "bracket_drilled_through_both_legs":
        body = drilled(drilled(bracket, 5.0, 4.0, 4.0), 12.0, 4.0, 4.0)
        for z in (15.0, 24.0):
            body = edit.bore(body, position=(-18.0, 0.0, z), axis="x", diameter=4.0)
        return body
    if name == "bracket_with_cove_and_holes":
        inner = straight(
            bracket, (0.0, 1.0, 0.0), lambda m: math.dist((m[0], m[2]), (-16.0, 4.0)) < 1e-6
        )
        assert len(inner) == 1
        coved = edit.fillet(bracket, 3.0, "named", inner)
        return drilled(drilled(coved, 5.0, 4.0, 4.0), 12.0, 4.0, 4.0)
    if name == "stepped_plate_with_round_corners":
        corners = straight(
            steps,
            (0.0, 0.0, 1.0),
            lambda m: abs(abs(m[0]) - 30.0) < 1e-6 and abs(abs(m[1]) - 10.0) < 1e-6,
        )
        assert len(corners) == 4
        return edit.fillet(steps, 3.0, "named", corners)
    assert name == "stepped_plate_countersunk"
    shaft = edit.moved(edit.cylinder(4.0, 6.0), (-15.0, 0.0, -1.0))
    sink = edit.moved(edit.cone(4.0, 8.0, 2.0), (-15.0, 0.0, 2.0))
    return edit.boolean("difference", [edit.boolean("difference", [steps, shaft]), sink])


@pytest.mark.parametrize(
    "name, least_drilled, widened",
    [
        ("bracket", 0, None),
        ("stepped_plate", 0, None),
        ("ledge", 0, None),
        ("pocket", 0, None),
        ("stairs", 0, None),
        ("bracket_drilled_through_both_legs", 2, None),
        ("bracket_with_cove_and_holes", 2, None),
        ("stepped_plate_with_round_corners", 0, None),
        ("stepped_plate_countersunk", 1, 8.0),
    ],
)
def test_steps_and_shoulders_from_a_mesh_are_rebuilt_as_sketches_and_extrusions(
    name: str, least_drilled: int, widened: float | None, profile: Profile
):
    """Stufen und Absätze aus einer STL werden Skizze plus Extrusion je Höhe (RM-022).

    Die Grundformen neben Brücke und Inselturm: Winkel, Stufenplatte, Absatz,
    Tasche und Treppe; dazu, was ein Querschnitt nicht trägt und deshalb
    danach gebohrt wird — Bohrungen quer zur Stufenrichtung und Senkungen —,
    und Rundungen längs der Stufenrichtung, die im Querschnitt als Bögen
    stehen. Sollwert ist der gebaute Körper: sein Volumen, die Formgrenze, die
    Senkung Ø 8. Der Vollquader besteht nie. Keine Zusage für jede STL.
    """
    from app.core.scene.rebuild import RebuildBudget, propose

    solid = _stepped_part(name)
    project = imported_payload("part.stl", _as_stl(solid))
    proposal = propose(
        project.document,
        "obj_1",
        profile,
        sources=ProjectSources(project),
        budget=RebuildBudget(0.1, 0.01),
    )
    assert proposal.accepted, [
        (entry.check.reason, entry.check.unexplained) for entry in proposal.candidates
    ]
    chosen = proposal.accepted[0]
    drills = [draft for draft in chosen.drafts if draft.op == "drill_brep_hole"]
    assert any(draft.op == "sketch_extrude" for draft in chosen.drafts)
    assert len(drills) >= least_drilled
    assert all(draft.params["compensate"] is False for draft in drills)
    if widened is not None:
        assert [draft.params.get("widening_diameter") for draft in drills] == [
            pytest.approx(widened, abs=0.05)
        ]
    assert chosen.result.mesh.volume == pytest.approx(solid.volume, rel=1e-4)
    assert chosen.check.surface is not None and chosen.check.surface.within_limit
    assert all(
        not entry.check.accepted
        for entry in proposal.candidates
        if [draft.op for draft in entry.drafts] == ["create_brep_box"]
    )


def _wall_holder():
    """Ein Wandhalter nach dem Vorbild des Besenhalters aus Roberts Test (0.5.2).

    Eine Leiste 80 x 4 x 20 mit 3-mm-Fasen an den vier Kanten ihrer Enden,
    darunter ein offener Klemmring Ø 42/34, durch die Leiste zwei Löcher Ø 4,5
    mit 90-Grad-Senkung Ø 9. Längs Z ist alles Wand außer den Fasen und den
    Querbohrungen — genau, was ein Querschnitt nicht trägt.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Line

    from app.core.brep import edit

    bar = edit.moved(edit.box(80.0, 4.0, 20.0), (0.0, 22.0, 0.0))
    ends = tuple(
        edit.edge_key(edge)
        for edge in edit.edges_of(bar)
        if BRepAdaptor_Curve(edge.edge).GetType() == GeomAbs_Line
        and abs(edge.direction[1]) > 0.999
        and abs(abs(edge.middle[0]) - 40.0) < 1e-6
    )
    assert len(ends) == 4
    bar = edit.chamfer(bar, 3.0, "named", ends)
    ring = edit.boolean("difference", [edit.cylinder(42.0, 20.0), edit.cylinder(34.0, 20.0)])
    ring = edit.boolean(
        "difference", [ring, edit.moved(edit.box(12.0, 10.0, 20.0), (0.0, -20.0, 0.0))]
    )
    holder = edit.unified(edit.boolean("union", [bar, ring]))
    for x in (-30.0, 30.0):
        holder = edit.bore(holder, position=(x, 24.0, 10.0), axis="y", diameter=4.5)
        sink = edit.transformed(
            edit.cone(4.5, 9.0, 2.25),
            (
                (1.0, 0.0, 0.0, x),
                (0.0, 0.0, 1.0, 21.75),
                (0.0, -1.0, 0.0, 10.0),
                (0.0, 0.0, 0.0, 1.0),
            ),
        )
        holder = edit.boolean("difference", [holder, sink])
    return holder


def test_a_wall_holder_is_rebuilt_from_its_profile_with_cuts_and_countersunk_holes(
    profile: Profile,
):
    """Profilkörper längs der Plattenachse, Fasen als Abzug, Senkbohrungen gebohrt (RM-022).

    Weder Quader noch gestufte Querschnitte tragen dieses Teil: Die Fasen
    stehen schräg zur Achse, die Senkungen quer. Sollwert ist der gebaute
    Körper — Volumen, Formgrenze, Senkung Ø 9; Roberts Datei selbst gehört
    nicht ins Repository.
    """
    from app.core.scene.rebuild import RebuildBudget, propose

    solid = _wall_holder()
    project = imported_payload("part.stl", _as_stl(solid))
    proposal = propose(
        project.document,
        "obj_1",
        profile,
        sources=ProjectSources(project),
        budget=RebuildBudget(0.1, 0.01),
    )

    assert proposal.accepted, [
        (entry.check.reason, entry.check.unexplained) for entry in proposal.candidates
    ]
    chosen = proposal.accepted[0]
    drills = [draft for draft in chosen.drafts if draft.op == "drill_brep_hole"]
    assert chosen.drafts[0].op == "sketch_extrude"
    assert any(draft.op == "subtract_objects" for draft in chosen.drafts)
    assert [draft.params.get("widening_diameter") for draft in drills] == [
        pytest.approx(9.0, abs=0.05)
    ] * 2
    assert all(draft.params["compensate"] is False for draft in drills)
    assert chosen.result.mesh.volume == pytest.approx(solid.volume, rel=1e-3)
    assert chosen.check.surface is not None and chosen.check.surface.within_limit


def test_a_needle_of_the_triangulation_leaves_a_plane_explained():
    """Ein unbedeckter Rest zählt erst ab der Ebenengenauigkeit (``_uncovered``).

    Am Besenhalter verwarf eine Nadel von 2,65·10⁻⁶ mm² am Rand eines Bodens
    den ganzen Vorschlag. Ein 0,05 mm breiter Streifen, der wirklich fehlt,
    bleibt ein Befund, auch schmaler als die Formgrenze.
    """
    import shapely

    from app.core.scene.rebuild import _uncovered

    floor = shapely.box(0.0, 0.0, 10.0, 10.0)
    needle = shapely.union(floor, shapely.Polygon([(5.0, 10.0), (5.0001, 10.0), (5.0, 10.3)]))
    strip = shapely.union(floor, shapely.box(5.0, 10.0, 5.05, 10.3))

    assert not _uncovered(needle, floor, 0.1, 0.001)
    assert _uncovered(strip, floor, 0.1, 0.001)
    assert not shapely.buffer(floor, 0.1).covers(needle)


def test_two_sections_differ_by_a_shallow_engraving_but_not_by_a_sliver():
    """Gleich heißt: kein Stück mit echter Breite dazwischen (``_same``).

    Die Schrift des Besenhalters nahm einem Querschnitt mit 763 mm Umfang
    4,08 mm² — weniger als ein Hundertstel mal Umfang, und die Schicht ging
    in ihrer Nachbarin auf. Ein Streifen von 0,005 mm längs der ganzen Wand
    ist dagegen Rauschen der Vernetzung.
    """
    import shapely

    from app.core.scene.rebuild import RebuildBudget, _same

    budget = RebuildBudget(0.1, 0.01)
    plate = shapely.box(-110.0, 0.0, 110.0, 4.0)
    engraved = shapely.difference(plate, shapely.box(-3.0, 3.32, 3.0, 4.0))
    shaved = shapely.box(-110.0, 0.0, 110.0, 3.995)

    assert float(plate.symmetric_difference(engraved).area) < 0.01 * float(plate.length)
    assert not _same(plate, engraved, budget)
    assert _same(plate, shaved, budget)


def test_an_engraving_is_a_pocket_and_an_open_notch_is_not():
    """Luft quer zur Achse, ringsum Material: eine Tasche (``_cross_pockets``).

    Ein Ring Ø 6/4, 0,6 mm tief in der Seite einer Platte, wird eine Tasche
    mit einem Abzug längs seiner Tiefe; eine gerundete Ecke R 5 durch die
    ganze Platte ist quer auch ein Prisma, längs der Achse aber keines, und
    zur Seite offen — sie bleibt den Schichten wie die Plattenecken des
    Besenhalters. Die Füllung reicht bis an die Wand und deckt die Gravur.
    """
    import math

    import manifold3d
    import numpy as np
    import shapely
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene.cancel import NeverCancelled
    from app.core.scene.rebuild import RebuildBudget, _cross_pockets

    def as_mesh(body: manifold3d.Manifold) -> MeshData:
        out = body.to_mesh()
        return MeshData.of(
            trimesh.Trimesh(
                vertices=np.asarray(out.vert_properties)[:, :3],
                faces=np.asarray(out.tri_verts),
                process=False,
            )
        )

    plate = manifold3d.Manifold.cube((40.0, 4.0, 20.0))
    ring = manifold3d.Manifold.cylinder(1.2, 3.0, 3.0, 96) - manifold3d.Manifold.cylinder(
        1.2, 2.0, 2.0, 96
    )
    ring = ring.rotate((-90.0, 0.0, 0.0)).translate((20.0, 3.4, 10.0))
    corner = manifold3d.Manifold.cube((5.0, 4.0, 5.0)) - manifold3d.Manifold.cylinder(
        4.0, 5.0, 5.0, 96
    ).rotate((-90.0, 0.0, 0.0)).translate((5.0, 0.0, 5.0))
    body = as_mesh(plate - ring - corner)
    engraving = math.pi * (3.0 * 3.0 - 2.0 * 2.0) * 0.6
    frame = (
        np.zeros(3),
        np.array([1.0, 0.0, 0.0]),
        np.array([0.0, 1.0, 0.0]),
        np.array([0.0, 0.0, 1.0]),
    )

    pockets, cuts = _cross_pockets(
        body,
        shapely.box(0.0, 0.0, 40.0, 4.0),
        20.0,
        frame,
        (),
        body,
        (),
        RebuildBudget(0.1, 0.01),
        NeverCancelled(),
    )

    assert len(pockets) == 1
    assert [draft.op for draft in cuts] == ["sketch_extrude", "subtract_objects"]
    centre = (pockets[0].bounds.minimum[0] + pockets[0].bounds.maximum[0]) / 2.0
    assert centre == pytest.approx(20.0, abs=0.05)
    assert pockets[0].volume >= engraving * 0.98


def test_an_engraving_across_the_profile_is_cut_as_one_pocket(profile: Profile):
    """Eine Gravur quer zur Plattenachse wird ein Abzug, nicht Dutzende Schichtreste.

    Am Besenhalter steht auf der Rückseite eine 0,68 mm tiefe Schrift. Längs
    der Plattenachse ändert ein runder Buchstabe seinen Querschnitt mit jeder
    Höhe; die Schichten ließen ihn erst in einer Nachbarschicht verschwinden,
    dann stießen Säulen und Reste mit deckungsgleichen Böden aneinander. Hier
    ein Ring Ø 6/4, 0,6 mm tief, zwischen den beiden Senkbohrungen.
    """
    from app.core.brep import edit
    from app.core.scene.rebuild import RebuildBudget, propose

    ring = edit.boolean("difference", [edit.cylinder(6.0, 1.2), edit.cylinder(4.0, 1.2)])
    ring = edit.transformed(
        ring,
        (
            (1.0, 0.0, 0.0, 0.0),
            (0.0, 0.0, 1.0, 23.4),
            (0.0, -1.0, 0.0, 10.0),
            (0.0, 0.0, 0.0, 1.0),
        ),
    )
    solid = edit.boolean("difference", [_wall_holder(), ring])
    project = imported_payload("part.stl", _as_stl(solid))
    proposal = propose(
        project.document,
        "obj_1",
        profile,
        sources=ProjectSources(project),
        budget=RebuildBudget(0.1, 0.01),
    )

    assert proposal.accepted, [
        (entry.check.reason, entry.check.unexplained) for entry in proposal.candidates
    ]
    chosen = proposal.accepted[0]
    assert chosen.result.mesh.volume == pytest.approx(solid.volume, rel=1e-3)
    assert chosen.check.surface is not None and chosen.check.surface.within_limit


@pytest.mark.parametrize("name", ("openscad_ascii.stl", "plate_countersunk_blind.stl"))
def test_round_base_and_blind_countersink_preserve_their_complete_shape(
    name: str, profile: Profile
):
    from app.core.scene.rebuild import RebuildBudget, propose

    project = imported(name)
    proposal = propose(
        project.document,
        "obj_1",
        profile,
        sources=ProjectSources(project),
        budget=RebuildBudget(0.2, 0.02),
    )
    if not proposal.accepted:
        pytest.fail(
            str(
                [
                    ([(draft.op, draft.params) for draft in entry.drafts], entry.check)
                    for entry in proposal.candidates
                ]
            )
        )


@pytest.mark.parametrize("rotated", (False, True))
def test_rounded_edge_is_rebuilt_from_support_planes_and_a_registered_fillet(
    profile: Profile, rotated: bool
):
    import math

    import numpy as np
    import trimesh

    from app.core.geom.mesh import read_mesh
    from app.core.ingest.loader import normalise
    from app.core.scene.rebuild import RebuildBudget, propose

    project = imported("block_with_rounded_edge.stl")
    if rotated:
        mesh = normalise(read_mesh(project.sources["src_1"], ".stl"), "mm").mesh.raw.copy()
        matrix = trimesh.transformations.rotation_matrix(np.radians(37.0), (1.0, 2.0, 3.0))
        matrix[:3, 3] = (13.0, -9.0, 7.0)
        mesh.apply_transform(matrix)
        project.sources["src_1"] = mesh.export(file_type="stl")
    proposal = propose(
        project.document,
        "obj_1",
        profile,
        sources=ProjectSources(project),
        budget=RebuildBudget(0.1, 0.01),
    )
    assert proposal.accepted, [entry.check.reason for entry in proposal.candidates]
    chosen = proposal.accepted[0]
    assert [draft.op for draft in chosen.drafts] == ["create_brep_box", "fillet_edges"]
    expected = 40.0 * 30.0 * 20.0 - (9.0 - 9.0 * math.pi / 4.0) * 30.0
    assert chosen.result.mesh.volume == pytest.approx(expected, abs=0.001)


@pytest.mark.parametrize("local_mm, accepted", ((0.1, False), (0.3, True)))
def test_a_body_with_multiple_attached_primitives_is_rebuilt_as_their_union(
    profile: Profile, local_mm: float, accepted: bool
):
    from app.core.scene.rebuild import RebuildBudget, propose

    project = imported("clean_figure.stl")
    proposal = propose(
        project.document,
        "obj_1",
        profile,
        sources=ProjectSources(project),
        # Die grobe Kugelfacettierung liegt bereits rund 0,16 mm innerhalb
        # ihres Trägers. 0,1 mm darf deshalb trotz richtiger Konstruktion
        # nicht freigegeben werden; 0,3 mm lässt die volle Messreserve zu.
        budget=RebuildBudget(local_mm, 0.02),
    )
    assert bool(proposal.accepted) is accepted, [entry.check for entry in proposal.candidates]
    if not accepted:
        composed = [
            entry
            for entry in proposal.candidates
            if any(step.op == "union_objects" for step in entry.drafts)
        ]
        assert composed and any(
            entry.check.surface is not None and not entry.check.surface.within_limit
            for entry in composed
        )
        return
    chosen = proposal.accepted[0]
    operations = [step.op for step in chosen.drafts]
    assert operations.count("create_brep_box") == 1
    assert operations.count("create_brep_cylinder") == 4
    assert operations.count("create_brep_sphere") == 1
    assert operations.count("union_objects") == 5
    assert chosen.check.surface is not None and chosen.check.surface.within_limit


@pytest.mark.parametrize("rotated", (False, True))
def test_a_fully_rounded_box_keeps_its_cylinders_and_spherical_corners(
    profile: Profile, rotated: bool
):
    from app.core.brep.features import features_of
    from app.core.scene.history import OperationDraft
    from app.core.scene.rebuild import RebuildBudget, propose

    project = new_project("centauri-carbon-2", "petg")
    placement = {"nx": 1.0, "ny": 2.0, "nz": 3.0, "angle": 37.0} if rotated else {}
    History(project.document).apply(
        "Vollständig gerundeter Quader",
        [
            OperationDraft(
                "create_brep_box",
                params={"width": 40.0, "depth": 30.0, "height": 20.0, **placement},
                outputs=("obj_1",),
            ),
            OperationDraft("fillet_edges", ("obj_1",), {"radius": 3.0, "edges": "all"}),
        ],
    )
    proposal = propose(
        project.document,
        "obj_1",
        profile,
        sources=ProjectSources(project),
        budget=RebuildBudget(0.1, 0.01),
    )
    assert proposal.accepted, [
        (entry.check.reason, entry.check.unexplained) for entry in proposal.candidates
    ]
    chosen = proposal.accepted[0]
    assert [draft.op for draft in chosen.drafts] == ["create_brep_box", "fillet_edges"]
    fillets = [
        feature for feature in features_of(chosen.result.mesh).values() if feature.kind == "fillet"
    ]
    assert sum("axis" in feature.params for feature in fillets) == 12
    assert sum("axis" not in feature.params for feature in fillets) == 8
    assert chosen.result.mesh.volume == pytest.approx(proposal.source.mesh.volume, abs=1e-6)


@pytest.mark.parametrize("rotated", (False, True))
def test_a_post_with_fillet_is_extended_to_its_support_plane(profile: Profile, rotated: bool):
    import math

    import trimesh
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Circle

    from app.core.brep import edit, step
    from app.core.ingest.plan import import_plan
    from app.core.scene.rebuild import RebuildBudget, propose

    plate = edit.moved(edit.box(60.0, 60.0, 6.0), (0.0, 0.0, -6.0))
    sharp = edit.boolean("union", [plate, edit.cylinder(12.0, 30.0)])
    foot_edges = [
        edge
        for edge in edit.edges_of(sharp)
        if BRepAdaptor_Curve(edge.edge).GetType() == GeomAbs_Circle
        and math.dist(edge.middle, (0.0, 0.0, 0.0)) < 1e-6
    ]
    assert len(foot_edges) == 1
    source = edit.fillet(sharp, 3.0, "named", (edit.edge_key(foot_edges[0]),))
    if rotated:
        matrix = trimesh.transformations.rotation_matrix(math.radians(37.0), (1.0, 2.0, 3.0))
        matrix[:3, 3] = (15.0, -7.0, 9.0)
        source = edit.transformed(source, matrix)
    payload = step.write(source)
    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = payload
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/valid_post.step", sha256=""
    )
    plan = import_plan("src_1", "valid_post.step", payload)
    History(project.document).apply(plan.title, [plan.draft])
    proposal = propose(
        project.document,
        "obj_1",
        profile,
        sources=ProjectSources(project),
        budget=RebuildBudget(0.1, 0.01),
    )
    assert proposal.accepted, [
        (entry.check.reason, entry.check.unexplained) for entry in proposal.candidates
    ]
    chosen = proposal.accepted[0]
    assert [draft.op for draft in chosen.drafts] == [
        "create_brep_box",
        "create_brep_cylinder",
        "union_objects",
        "fillet_edges",
    ]
    assert chosen.drafts[1].params["height"] == pytest.approx(30.0, abs=1e-6)
    assert chosen.result.mesh.volume == pytest.approx(source.volume, abs=1e-6)


def test_a_post_with_a_cove_from_a_mesh_is_rebuilt_like_the_exact_one(profile: Profile):
    """Derselbe Zapfen mit Hohlkehle, als STL eingelesen, wird gleich nachgebaut (RM-022).

    Mantel und Kehle gehen tangential ineinander über; am Netz lagen beide bis
    zur tangentialen Trennung (RM-226) in einer gekrümmten Fläche, und der
    Nachbau fand keinen Zapfen — jeder Kandidat blieb mit unerklärten Flächen
    stehen. Jetzt liest das Netz Zapfen und Kehle wie der exakte Kern, und der
    Nachbau nimmt dieselbe Folge wie aus der STEP-Datei. Sollwert aus der
    Konstruktion: das Volumen des exakten Körpers.
    """
    import io
    import math

    import numpy as np
    import trimesh
    from OCP.BRepAdaptor import BRepAdaptor_Curve
    from OCP.GeomAbs import GeomAbs_Circle

    from app.core.brep import edit
    from app.core.geom.mesh import as_mesh_data
    from app.core.scene.rebuild import RebuildBudget, propose

    plate = edit.moved(edit.box(60.0, 60.0, 6.0), (0.0, 0.0, -6.0))
    sharp = edit.boolean("union", [plate, edit.cylinder(12.0, 30.0)])
    foot = [
        edge
        for edge in edit.edges_of(sharp)
        if BRepAdaptor_Curve(edge.edge).GetType() == GeomAbs_Circle
        and math.dist(edge.middle, (0.0, 0.0, 0.0)) < 1e-6
    ]
    assert len(foot) == 1
    solid = edit.fillet(sharp, 3.0, "named", (edit.edge_key(foot[0]),))
    twin = as_mesh_data(solid)
    stream = io.BytesIO()
    trimesh.Trimesh(
        vertices=np.asarray(twin.raw.vertices), faces=np.asarray(twin.raw.faces), process=False
    ).export(stream, file_type="stl")
    project = imported_payload("post_with_a_cove.stl", stream.getvalue())
    proposal = propose(
        project.document,
        "obj_1",
        profile,
        sources=ProjectSources(project),
        budget=RebuildBudget(0.1, 0.01),
    )
    kinds = sorted(feature.kind for feature in proposal.source.features.values())
    assert kinds == ["face"] * 7 + ["pin", "torus"]
    assert proposal.accepted, [
        (entry.check.reason, entry.check.unexplained) for entry in proposal.candidates
    ]
    chosen = proposal.accepted[0]
    assert [draft.op for draft in chosen.drafts] == [
        "create_brep_box",
        "create_brep_cylinder",
        "union_objects",
        "fillet_edges",
    ]
    assert chosen.result.mesh.volume == pytest.approx(solid.volume, abs=1e-3)


def test_rebuild_is_one_transaction_with_parameters_sources_and_disk_round_trip(
    tmp_path: Path, profile: Profile
):
    from app.core.scene import evaluate
    from app.core.scene.project import load, save
    from app.core.scene.rebuild import RebuildBudget, commit, prepare_application, propose
    from app.core.scene.serialise import document_to_data

    project = imported("cube_clean.stl")
    history = History(project.document)
    before = document_to_data(project.document)
    sources = ProjectSources(project)
    proposal = propose(
        project.document, "obj_1", profile, sources=sources, budget=RebuildBudget(0.1, 0.01)
    )
    application = prepare_application(
        project.document, proposal, proposal.accepted[0], profile, sources=sources
    )
    assert before == document_to_data(project.document)
    transaction = commit(history, application)
    assert len(project.document.transactions) == 2
    assert len(transaction.ops) >= 3
    assert project.document.parameters
    result = evaluate(project.document, profile, sources=sources)
    assert result.complete
    assert set(result.scene.objects) == {application.result.id}
    assert application.result.id != "obj_1"
    assert project.document.sources["src_1"].kind == "import"
    assert project.sources["src_1"] == (MESHES / "cube_clean.stl").read_bytes()
    expected_volume = application.result.mesh.volume
    path = tmp_path / "rebuilt.p3d"
    save(project, path)
    reopened = load(path)
    disk = evaluate(reopened.document, profile, sources=ProjectSources(reopened))
    assert disk.complete
    assert disk.scene.objects[application.result.id].mesh.volume == pytest.approx(expected_volume)
    history.undo()
    assert len(project.document.ops) == 1
    assert not project.document.parameters
    original = evaluate(project.document, profile, sources=sources)
    assert set(original.scene.objects) == {"obj_1"}
    history.redo()
    again = evaluate(project.document, profile, sources=sources)
    assert again.complete
    assert again.scene.objects[application.result.id].mesh.volume == pytest.approx(expected_volume)


def test_changed_proposal_and_unacknowledged_attribute_losses_are_atomic(profile: Profile):
    from app.core.errors import UserError
    from app.core.scene.rebuild import RebuildBudget, commit, prepare_application, propose
    from app.core.scene.serialise import document_to_data

    project = imported("cube_clean.stl")
    project.document.protected["obj_1"] = ("face_1",)
    history = History(project.document)
    sources = ProjectSources(project)
    proposal = propose(
        project.document, "obj_1", profile, sources=sources, budget=RebuildBudget(0.1, 0.01)
    )
    application = prepare_application(
        project.document, proposal, proposal.accepted[0], profile, sources=sources
    )
    assert application.losses
    before = document_to_data(project.document)
    with pytest.raises(UserError):
        commit(history, application)
    assert document_to_data(project.document) == before
    application.drafts[0].params["width"] = 123.0
    with pytest.raises(UserError):
        commit(history, application, accept_losses=True)
    assert document_to_data(project.document) == before


def test_the_session_takes_a_rebuild_of_an_unchanged_linked_source(
    profile: Profile, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Übernahme der Sitzung prüft verknüpfte Dateien gegen ihren Ort (RM-022).

    ``Session.commit_rebuild`` gab dem Kern keine Quellen mit. Jede verknüpfte
    Datei galt dadurch als geändert, und ein Nachbau ließ sich an einem solchen
    Projekt nie übernehmen — die Meldung verlangte einen neuen Vergleich, der
    wieder an derselben Stelle endete.
    """
    from dataclasses import replace

    from app.core.scene.project import checksum, save
    from app.core.scene.rebuild import RebuildBudget, prepare_application, propose
    from app.ui.session import Session

    project = imported("cube_clean.stl")
    payload = project.sources.pop("src_1")
    (tmp_path / "cube.stl").write_bytes(payload)
    project.document.sources["src_1"] = replace(
        project.document.sources["src_1"],
        path="cube.stl",
        embedded=False,
        sha256=checksum(payload),
    )
    path = tmp_path / "verknuepft.p3d"
    save(project, path)
    session = Session()
    # Ohne Ereignisschleife käme kein Arbeiterergebnis an; geprüft wird die Übernahme.
    monkeypatch.setattr(session, "evaluate_async", lambda *_args, **_kwargs: None)
    session.open_project(path)
    assert not session.busy
    sources = ProjectSources(session.project, base_dir=session.base_dir)
    proposal = propose(
        session.project.document,
        "obj_1",
        session.profile,
        sources=sources,
        budget=RebuildBudget(0.1, 0.01),
    )
    application = prepare_application(
        session.project.document,
        proposal,
        proposal.accepted[0],
        session.profile,
        sources=sources,
    )
    before = len(session.project.document.transactions)

    assert session.commit_rebuild(application, accept_losses=True)
    assert len(session.project.document.transactions) == before + 1


def test_a_linked_source_cannot_change_after_the_comparison(profile: Profile, tmp_path: Path):
    from dataclasses import replace

    from app.core.errors import UserError
    from app.core.scene.project import checksum
    from app.core.scene.rebuild import RebuildBudget, commit, prepare_application, propose
    from app.core.scene.serialise import document_to_data

    project = imported("cube_clean.stl")
    payload = project.sources.pop("src_1")
    linked = tmp_path / "cube.stl"
    linked.write_bytes(payload)
    project.document.sources["src_1"] = replace(
        project.document.sources["src_1"],
        path="cube.stl",
        embedded=False,
        sha256=checksum(payload),
    )
    sources = ProjectSources(project, base_dir=tmp_path)
    proposal = propose(
        project.document, "obj_1", profile, sources=sources, budget=RebuildBudget(0.1, 0.01)
    )
    application = prepare_application(
        project.document, proposal, proposal.accepted[0], profile, sources=sources
    )
    before = document_to_data(project.document)
    linked.write_bytes((MESHES / "plate_holes.stl").read_bytes())
    with pytest.raises(UserError):
        commit(History(project.document), application, sources=sources)
    assert document_to_data(project.document) == before
    linked.write_bytes(payload)
    commit(History(project.document), application, sources=sources)


def test_a_freely_rotated_import_retains_its_shape_and_position(profile: Profile):
    import numpy as np
    import trimesh

    from app.core.geom.mesh import read_mesh
    from app.core.ingest.loader import normalise
    from app.core.scene.rebuild import RebuildBudget, propose

    project = imported("cube_clean.stl")
    mesh = normalise(read_mesh(project.sources["src_1"], ".stl"), "mm").mesh
    matrix = trimesh.transformations.rotation_matrix(np.radians(37.0), (1.0, 2.0, 3.0))
    matrix[:3, 3] = (60.0, -20.0, 40.0)
    raw = mesh.raw.copy()
    raw.apply_transform(matrix)
    project.sources["src_1"] = raw.export(file_type="stl")
    proposal = propose(
        project.document,
        "obj_1",
        profile,
        sources=ProjectSources(project),
        budget=RebuildBudget(0.1, 0.01),
    )
    assert proposal.accepted, [
        (entry.check.reason, entry.check.volume_relative) for entry in proposal.candidates
    ]
    assert proposal.accepted[0].result.mesh.volume == pytest.approx(mesh.volume, rel=1e-6)


def test_unexplained_small_recess_is_not_silently_filled_within_the_form_budget(profile: Profile):
    import trimesh

    from app.core.geom.boolean import boolean
    from app.core.geom.mesh import MeshData, read_mesh
    from app.core.ingest.loader import normalise
    from app.core.scene.rebuild import RebuildBudget, propose

    project = imported("cube_clean.stl")
    mesh = normalise(read_mesh(project.sources["src_1"], ".stl"), "mm").mesh
    tool = trimesh.creation.box(extents=(0.2, 0.2, 0.04))
    tool.apply_translation((0.0, 0.0, mesh.bounds.maximum[2]))
    recessed = boolean("difference", [mesh, MeshData.of(tool)]).mesh
    project.sources["src_1"] = recessed.raw.export(file_type="stl")
    proposal = propose(
        project.document,
        "obj_1",
        profile,
        sources=ProjectSources(project),
        budget=RebuildBudget(0.1, 0.01),
    )
    boxes = [
        entry
        for entry in proposal.candidates
        if [draft.op for draft in entry.drafts] == ["create_brep_box"]
    ]
    assert boxes and all(not entry.check.accepted and entry.check.unexplained for entry in boxes)
    # Die neue Querschnittsfolge darf die Stufe vollständig rekonstruieren.
    # Die kleine fehlende Materialmenge darf dabei nicht im Volumenbudget verschwinden.
    for candidate in proposal.accepted:
        assert candidate.result.mesh.volume == pytest.approx(proposal.source.mesh.volume, abs=1e-9)


@pytest.mark.parametrize("stage", (0.0, 0.1, 0.2))
def test_cancellation_during_proposal_leaves_no_partial_history(profile: Profile, stage: float):
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal
    from app.core.scene.rebuild import RebuildBudget, propose
    from app.core.scene.serialise import document_to_data

    project = imported("cube_clean.stl")
    before = document_to_data(project.document)
    token = CancelSignal()
    seen = []

    def progress(value: float, _label: str) -> None:
        seen.append(value)
        if value >= stage:
            token.cancel()

    with pytest.raises(OperationCancelled):
        propose(
            project.document,
            "obj_1",
            profile,
            sources=ProjectSources(project),
            budget=RebuildBudget(0.1, 0.01),
            cancelled=token,
            progress=progress,
        )
    assert seen and seen == sorted(seen)
    assert document_to_data(project.document) == before


@pytest.mark.parametrize("stage", (0.0, 0.8))
def test_cancellation_during_application_leaves_all_attributes_intact(
    profile: Profile, stage: float
):
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal
    from app.core.scene.rebuild import RebuildBudget, prepare_application, propose
    from app.core.scene.serialise import document_to_data

    project = imported("cube_clean.stl")
    before = document_to_data(project.document)
    sources = ProjectSources(project)
    proposal = propose(
        project.document, "obj_1", profile, sources=sources, budget=RebuildBudget(0.1, 0.01)
    )
    token = CancelSignal()

    def progress(value: float, _label: str) -> None:
        if value >= stage:
            token.cancel()

    with pytest.raises(OperationCancelled):
        prepare_application(
            project.document,
            proposal,
            proposal.accepted[0],
            profile,
            sources=sources,
            cancelled=token,
            progress=progress,
        )
    assert document_to_data(project.document) == before


def test_a_stale_comparison_cannot_replace_a_more_recent_model(profile: Profile):
    from app.core.errors import UserError
    from app.core.scene.history import OperationDraft
    from app.core.scene.rebuild import RebuildBudget, commit, prepare_application, propose
    from app.core.scene.serialise import document_to_data

    project = imported("cube_clean.stl")
    history = History(project.document)
    sources = ProjectSources(project)
    proposal = propose(
        project.document, "obj_1", profile, sources=sources, budget=RebuildBudget(0.1, 0.01)
    )
    application = prepare_application(
        project.document, proposal, proposal.accepted[0], profile, sources=sources
    )
    history.apply("Neuer Name", [OperationDraft("rename_object", ("obj_1",), {"name": "Neu"})])
    before = document_to_data(project.document)
    with pytest.raises(UserError):
        prepare_application(
            project.document, proposal, proposal.accepted[0], profile, sources=sources
        )
    with pytest.raises(UserError):
        commit(history, application)
    assert document_to_data(project.document) == before


def test_a_candidate_cannot_change_between_comparison_and_application(profile: Profile):
    from app.core.errors import UserError
    from app.core.scene.rebuild import RebuildBudget, prepare_application, propose
    from app.core.scene.serialise import document_to_data

    project = imported("cube_clean.stl")
    sources = ProjectSources(project)
    proposal = propose(
        project.document, "obj_1", profile, sources=sources, budget=RebuildBudget(0.1, 0.01)
    )
    chosen = proposal.accepted[0]
    chosen.drafts[0].params["width"] += 0.001
    before = document_to_data(project.document)
    with pytest.raises(UserError):
        prepare_application(project.document, proposal, chosen, profile, sources=sources)
    assert document_to_data(project.document) == before


def test_material_spool_plate_and_name_survive_the_new_construction(
    profile: Profile, tmp_path: Path
):
    from app.core.scene import evaluate
    from app.core.scene.history import OperationDraft
    from app.core.scene.project import load, save
    from app.core.scene.rebuild import RebuildBudget, commit, prepare_application, propose
    from app.core.types import PrintSettings, SpoolBinding

    project = imported("cube_clean.stl")
    history = History(project.document)
    history.apply(
        "Attribute",
        [
            OperationDraft("rename_object", ("obj_1",), {"name": "Grüner Würfel"}),
            OperationDraft("set_material", ("obj_1",), {"material": "pla"}),
            OperationDraft(
                "assign_slot",
                ("obj_1",),
                {
                    "slot": 2,
                    "name": "Grüne Spule",
                    "colour": "#339966 #ccff99",
                    "material_type": "PLA",
                    "slicer_profile": "Generic PLA",
                },
            ),
            OperationDraft("translate_object", ("obj_1",), {"plate": 3, "keep_on_bed": False}),
        ],
    )
    sources = ProjectSources(project)
    source = evaluate(project.document, profile, sources=sources).scene.objects["obj_1"]
    slot = source.material_slots[0]
    binding = SpoolBinding("local-spool", slot.name, slot.colour, slot.material, slot.material_type)
    project.document.print_settings = PrintSettings(spool_bindings=(binding,))
    proposal = propose(
        project.document, "obj_1", profile, sources=sources, budget=RebuildBudget(0.1, 0.01)
    )
    application = prepare_application(
        project.document, proposal, proposal.accepted[0], profile, sources=sources
    )
    assert not application.losses
    commit(history, application)
    path = tmp_path / "attributes.p3d"
    save(project, path)
    restored = load(path)
    rebuilt = evaluate(restored.document, profile, sources=ProjectSources(restored))
    actual = rebuilt.scene.objects[application.result.id]
    assert (actual.name, actual.material, actual.plate) == (
        source.name,
        source.material,
        source.plate,
    )
    assert actual.material_slots == source.material_slots
    assert set(actual.mesh.slot_indices) == {2}
    assert restored.document.print_settings.spool_bindings == (binding,)
    history.undo()
    original = evaluate(project.document, profile, sources=sources).scene.objects["obj_1"]
    assert original.material_slots == source.material_slots


def test_fit_losses_are_visible_and_return_with_undo(profile: Profile):
    from app.core.scene import evaluate
    from app.core.scene.rebuild import RebuildBudget, commit, prepare_application, propose
    from app.core.types import FeatureRef, Fit

    project = imported("cube_clean.stl")
    sources = ProjectSources(project)
    source = evaluate(project.document, profile, sources=sources).scene.objects["obj_1"]
    feature = next(iter(source.features))
    fit = Fit("Bestehender Bezug", FeatureRef("obj_1", feature), FeatureRef("obj_1", feature))
    project.document.fits.append(fit)
    proposal = propose(
        project.document, "obj_1", profile, sources=sources, budget=RebuildBudget(0.1, 0.01)
    )
    application = prepare_application(
        project.document, proposal, proposal.accepted[0], profile, sources=sources
    )
    assert any("Passungen" in str(loss) for loss in application.losses)
    history = History(project.document)
    commit(history, application, accept_losses=True)
    assert not project.document.fits
    history.undo()
    assert project.document.fits == [fit]
    history.redo()
    assert not project.document.fits


def test_individual_face_filaments_need_acknowledgement_and_return_with_undo(profile: Profile):
    from app.core.errors import UserError
    from app.core.scene import evaluate
    from app.core.scene.history import OperationDraft
    from app.core.scene.rebuild import RebuildBudget, commit, prepare_application, propose

    project = imported("cube_clean.stl")
    history = History(project.document)
    sources = ProjectSources(project)
    original = evaluate(project.document, profile, sources=sources).scene.objects["obj_1"]
    face = next(feature.id for feature in original.features.values() if feature.kind == "face")
    history.apply(
        "Zwei Filamente",
        [
            OperationDraft("assign_slot", ("obj_1",), {"slot": 2, "name": "Blau"}),
            OperationDraft(
                "paint_slot",
                ("obj_1",),
                {
                    "slot": 3,
                    "name": "Rot",
                    "at_feature": face,
                },
            ),
        ],
    )
    before = evaluate(project.document, profile, sources=sources).scene.objects["obj_1"]
    assert set(before.mesh.slot_indices) == {2, 3}
    proposal = propose(
        project.document, "obj_1", profile, sources=sources, budget=RebuildBudget(0.1, 0.01)
    )
    application = prepare_application(
        project.document, proposal, proposal.accepted[0], profile, sources=sources
    )
    assert any("Filamentzuweisung einzelner Flächen" in str(loss) for loss in application.losses)
    count = len(project.document.transactions)
    with pytest.raises(UserError):
        commit(history, application)
    assert len(project.document.transactions) == count
    commit(history, application, accept_losses=True)
    assert len(project.document.transactions) == count + 1
    history.undo()
    restored = evaluate(project.document, profile, sources=sources).scene.objects["obj_1"]
    assert tuple(restored.mesh.slot_indices) == tuple(before.mesh.slot_indices)
    assert restored.material_slots == before.material_slots


def test_an_imported_texture_is_named_before_replacing_the_model(profile: Profile):
    from dataclasses import replace

    from app.core.scene.rebuild import RebuildBudget, prepare_application, propose
    from tests.helpers import pbr_glb

    project = imported("cube_clean.stl")
    project.sources["src_1"] = pbr_glb()
    project.document.sources["src_1"] = replace(
        project.document.sources["src_1"], path="sources/textured.glb"
    )
    sources = ProjectSources(project)
    proposal = propose(
        project.document, "obj_1", profile, sources=sources, budget=RebuildBudget(0.1, 0.01)
    )
    assert proposal.accepted
    application = prepare_application(
        project.document, proposal, proposal.accepted[0], profile, sources=sources
    )
    assert any("Oberflächentexturen" in str(loss) for loss in application.losses)


@pytest.mark.parametrize("name", ("broken_selfint.stl",))
def test_crossing_source_surfaces_stop_before_candidate_generation(name: str, profile: Profile):
    from app.core.errors import UserError
    from app.core.scene.rebuild import RebuildBudget, propose
    from app.core.scene.serialise import document_to_data

    project = imported(name)
    before = document_to_data(project.document)
    with pytest.raises(UserError) as caught:
        propose(
            project.document,
            "obj_1",
            profile,
            sources=ProjectSources(project),
            budget=RebuildBudget(0.1, 0.01),
        )
    assert caught.value.suggestions
    assert "überschneidungsfrei" in str(caught.value)
    assert document_to_data(project.document) == before


def test_a_small_crossing_at_a_seam_does_not_stop_the_rebuild(profile: Profile):
    """Vier Dreiecke an der Kehle des Zapfens kreuzen sich (0,07 % der Fläche).

    Das hielt den Nachbau bisher an, wie an 16 Körpern des Korpus. Unter
    ``CROSSING_SHARE`` entstehen Kandidaten, und die unabhängige Formprüfung
    entscheidet über sie; die zwei durcheinanderlaufenden Quader halten
    weiter an (oben).
    """
    from app.core.geom.mesh import as_mesh_data
    from app.core.geom.repair import self_intersection_check
    from app.core.scene.evaluate import evaluate
    from app.core.scene.rebuild import CROSSING_SHARE, RebuildBudget, _crossing_share, propose

    project = imported("post_with_fillet.stl")
    source = evaluate(project.document, profile, sources=ProjectSources(project)).scene
    mesh = as_mesh_data(source.objects["obj_1"].mesh)
    crossed, complete = self_intersection_check(mesh)
    assert complete and crossed, "die Probe muss sich selbst kreuzen"
    assert 0.0 < _crossing_share(mesh, crossed) < CROSSING_SHARE

    proposal = propose(
        project.document,
        "obj_1",
        profile,
        sources=ProjectSources(project),
        budget=RebuildBudget(0.1, 0.01),
    )

    assert proposal.candidates


@pytest.mark.parametrize("width, offset", ((2.0, 3.0), (0.05, 0.04)))
def test_equal_plane_heights_do_not_explain_a_missing_separate_pocket(width: float, offset: float):
    import numpy as np

    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.geom.mesh import as_mesh_data
    from app.core.scene.cancel import NeverCancelled
    from app.core.scene.rebuild import RebuildBudget, _unexplained_planes, check_shape
    from app.core.types import SceneObject

    base = edit.box(20, 20, 4)
    pockets = []
    for x, y in ((-offset, -offset), (-offset, offset), (offset, -offset), (offset, offset)):
        matrix = np.eye(4)
        matrix[:3, 3] = (x, y, 3.97)
        pockets.append(
            edit.transformed(
                edit.box(width, width, 1), tuple(tuple(float(v) for v in row) for row in matrix)
            )
        )
    original = edit.boolean("difference", [base, *pockets])
    reduced = edit.boolean("difference", [base, *pockets[:-1]])
    source = SceneObject("obj_1", "Vier Taschen", original, features=features_of(original))
    candidate = SceneObject("obj_2", "Drei Taschen", reduced)
    assert check_shape(as_mesh_data(original), candidate, RebuildBudget(0.1, 0.01)).accepted
    assert _unexplained_planes(source, candidate, NeverCancelled(), boundary_mm=0.1)


@pytest.mark.parametrize("void", (True, False))
def test_small_voids_and_separate_pieces_cannot_disappear_inside_the_form_budget(void: bool):
    import trimesh

    from app.core.brep import edit
    from app.core.geom.mesh import MeshData
    from app.core.scene.rebuild import RebuildBudget, check_shape
    from app.core.types import SceneObject

    solid = edit.box(20.0, 20.0, 20.0)
    small = trimesh.creation.box(extents=(0.02, 0.02, 0.02))
    small.apply_translation((0.0, 0.0, 10.0 if void else 20.04))
    if void:
        small.invert()
    source = MeshData.of(trimesh.util.concatenate((solid.to_mesh().raw, small)))
    result = check_shape(
        source, SceneObject("new", "Vollquader", solid, kind="brep"), RebuildBudget(0.1, 0.01)
    )
    assert not result.accepted and result.reason == "topology"


@pytest.mark.parametrize(
    "local, volume", ((0.0, 0.01), (float("nan"), 0.01), (0.1, 0.0), (0.1, 1.0))
)
def test_invalid_explicit_form_budgets_have_an_actionable_error(local: float, volume: float):
    from app.core.errors import ValidationError
    from app.core.scene.rebuild import RebuildBudget

    with pytest.raises(ValidationError) as caught:
        RebuildBudget(local, volume)
    assert caught.value.suggestions


def test_a_modified_rebuild_parameter_drives_later_geometry_and_survives_reopening(
    profile: Profile, tmp_path: Path
):
    from dataclasses import replace

    from app.core.scene import evaluate
    from app.core.scene.history import OperationDraft, change_for
    from app.core.scene.project import load, save
    from app.core.scene.rebuild import RebuildBudget, commit, prepare_application, propose

    project = imported("cube_clean.stl")
    history = History(project.document)
    sources = ProjectSources(project)
    proposal = propose(
        project.document, "obj_1", profile, sources=sources, budget=RebuildBudget(0.1, 0.01)
    )
    application = prepare_application(
        project.document, proposal, proposal.accepted[0], profile, sources=sources
    )
    commit(history, application)
    output = application.result.id
    history.apply(
        "Spätere Bohrung",
        [
            OperationDraft(
                "drill_brep_hole",
                (output,),
                {
                    "diameter": 4.0,
                    "compensate": False,
                    "x": 0.0,
                    "y": 0.0,
                    "z": 10.0,
                },
            )
        ],
    )
    name = next(name for name in project.document.parameters if name.endswith("_width"))
    parameter = project.document.parameters[name]
    before = evaluate(project.document, profile, sources=sources)
    history.apply(
        "Breite ändern",
        [],
        changes=change_for(
            project.document,
            parameters={
                name: replace(parameter, value=30.0),
            },
        ),
    )
    after = evaluate(project.document, profile, sources=sources)
    assert after.complete
    rebuilt = after.scene.objects[output]
    assert rebuilt.mesh.bounds.size[0] == pytest.approx(30.0, abs=1e-6)
    assert rebuilt.mesh.volume - before.scene.objects[output].mesh.volume == pytest.approx(4000.0)
    assert any(feature.kind == "hole" for feature in rebuilt.features.values())
    path = tmp_path / "dimension-with-following-hole.p3d"
    save(project, path)
    restored = load(path)
    again = evaluate(restored.document, profile, sources=ProjectSources(restored))
    assert again.complete
    assert again.scene.objects[output].mesh.volume == pytest.approx(rebuilt.mesh.volume)
    history.undo()
    undone = evaluate(project.document, profile, sources=sources)
    assert undone.scene.objects[output].mesh.volume == pytest.approx(
        before.scene.objects[output].mesh.volume
    )
