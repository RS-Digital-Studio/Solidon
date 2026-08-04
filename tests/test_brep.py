"""Der zweite Konstruktionskern (Bauplan §30; §40 für P12).

Drei Sätze entscheiden diese Phase: eine Verrundung an einer Referenzkante
geometrisch exakt, STEP fähig zur runden Reise, und die Mesh/B-Rep-Markierung
richtig. Jeder davon wird gegen eine Zahl gemessen, die sich von Hand
nachrechnen lässt, nicht gegen ein Bild.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest
import trimesh

from app.core.brep import edit, step
from app.core.brep.features import features_of
from app.core.brep.kernel import Solid, available, tessellate
from app.core.errors import GeometryError, NeedsSolidError, ValidationError
from app.core.export.writer import export_bytes, plan_export, write_plan
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.registry import REGISTRY
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.cancel import NeverCancelled
from app.core.scene.project import ProjectSources, new_project
from app.core.types import Mesh, OpContext, Profile, Scene, SceneObject, Source, kind_of

pytestmark = pytest.mark.skipif(not available(), reason="OpenCASCADE is an optional dependency")

WIDTH, DEPTH, HEIGHT = 40.0, 30.0, 20.0


def block() -> Solid:
    return edit.box(WIDTH, DEPTH, HEIGHT)


# --- exactness ------------------------------------------------------------------


def test_the_body_answers_from_the_kernel_not_from_the_triangles() -> None:
    solid = block()

    assert solid.volume == pytest.approx(WIDTH * DEPTH * HEIGHT, rel=1e-9)
    assert solid.area == pytest.approx(2 * (40 * 30 + 40 * 20 + 30 * 20), rel=1e-9)
    assert (solid.face_count, solid.edge_count) == (6, 12)


def test_a_fillet_on_a_reference_edge_is_geometrically_exact() -> None:
    """§40 für P12. Vier Stehende mit r gerundet: die Rechnung ist geschlossen."""
    radius = 3.0

    rounded = edit.fillet(block(), radius, "vertical")

    corner = radius**2 - math.pi * radius**2 / 4.0
    expected = WIDTH * DEPTH * HEIGHT - 4.0 * corner * HEIGHT
    assert rounded.volume == pytest.approx(expected, rel=1e-9)


def test_a_chamfer_takes_off_exactly_its_triangle() -> None:
    distance = 2.0

    broken = edit.chamfer(block(), distance, "vertical")

    expected = WIDTH * DEPTH * HEIGHT - 4.0 * (distance**2 / 2.0) * HEIGHT
    assert broken.volume == pytest.approx(expected, rel=1e-9)


def test_a_precise_boolean_needs_no_fallback_chain() -> None:
    """§30: zwei exakte Körper sind sich nicht uneinig, was innen ist."""
    drilled = edit.boolean(
        "difference", [block(), edit.moved(edit.cylinder(8.0, 40.0), (0.0, 0.0, -5.0))]
    )

    expected = WIDTH * DEPTH * HEIGHT - math.pi * 16.0 * HEIGHT
    assert drilled.volume == pytest.approx(expected, rel=1e-9)


def test_a_radius_that_does_not_fit_is_an_error_not_a_guess() -> None:
    with pytest.raises(GeometryError):
        edit.fillet(block(), 100.0, "vertical")


def test_a_selection_that_matches_nothing_says_so() -> None:
    with pytest.raises(GeometryError):
        edit.fillet(edit.cylinder(10.0, 20.0), 1.0, "vertical")


# --- which edges ----------------------------------------------------------------


def test_the_named_selections_pick_what_they_say() -> None:
    solid = block()

    assert len(edit.choose(solid, "all")) == 12
    assert len(edit.choose(solid, "vertical")) == 4, "the four uprights"
    assert len(edit.choose(solid, "horizontal")) == 8
    assert len(edit.choose(solid, "top")) == 4
    assert all(entry.middle[2] == pytest.approx(HEIGHT) for entry in edit.choose(solid, "top"))
    assert all(entry.middle[2] == pytest.approx(0.0) for entry in edit.choose(solid, "bottom"))


# --- Der Weg zum Netz -----------------------------------------------------------


def test_the_tessellation_is_closed_and_keeps_the_volume() -> None:
    mesh = edit.fillet(block(), 3.0, "vertical").to_mesh()

    assert isinstance(mesh, MeshData)
    assert mesh.is_watertight
    assert mesh.volume > 0.0, "not inside out"


def test_a_finer_setting_gives_more_triangles_and_less_error() -> None:
    solid = edit.fillet(block(), 3.0, "vertical")

    coarse = tessellate(solid.shape, 0.5)
    fine = tessellate(solid.shape, 0.01)

    assert fine.triangle_count > coarse.triangle_count
    assert abs(fine.volume - solid.volume) < abs(coarse.volume - solid.volume)


def test_a_mesh_operation_gets_the_tessellation(profile: Profile) -> None:
    """§30: der Weg zum Netz steht jederzeit offen."""
    solid = block()

    converted = as_mesh_data(solid)

    assert isinstance(converted, MeshData)
    assert converted.triangle_count == 12


def test_the_marking_follows_the_body_not_the_claim() -> None:
    assert kind_of(block()) == "brep"
    assert kind_of(MeshData.of(trimesh.creation.box(extents=(1.0, 1.0, 1.0)))) == "mesh"


def test_a_solid_satisfies_the_mesh_protocol() -> None:
    """Genau das lässt Viewport und Prüfbericht unverändert mit ihm
    arbeiten (§9).
    """
    assert isinstance(block(), Mesh)


# --- STEP -----------------------------------------------------------------------


def test_step_makes_the_round_trip() -> None:
    """§40 für P12: zurück als derselbe Körper, nicht als dasselbe Bild."""
    solid = edit.fillet(block(), 3.0, "vertical")

    again = step.read(step.write(solid))

    assert again.volume == pytest.approx(solid.volume, rel=1e-9)
    assert again.face_count == solid.face_count
    assert again.edge_count == solid.edge_count


def test_a_broken_step_file_is_a_user_error() -> None:
    with pytest.raises(ValidationError):
        step.read(b"this is not a STEP file")


def test_step_knows_its_own_suffixes() -> None:
    assert step.is_step(".STEP") and step.is_step(".stp")
    assert not step.is_step(".stl")


# --- features off the topology --------------------------------------------------


def test_a_bore_is_read_off_the_topology_rather_than_fitted() -> None:
    """§30: kein Gruppieren, keine Zylindereinpassung — eine zylindrische
    Fläche nennt ihren Radius.
    """
    drilled = edit.boolean(
        "difference", [block(), edit.moved(edit.cylinder(8.0, 40.0), (0.0, 0.0, -5.0))]
    )

    found = features_of(drilled)

    holes = {name: entry for name, entry in found.items() if entry.kind == "hole"}
    assert len(holes) == 1
    assert holes["hole_1"].params["diameter"] == pytest.approx(8.0)
    assert holes["hole_1"].params["axis"][2] == pytest.approx(1.0)


def test_a_rounded_corner_is_not_reported_as_a_hole() -> None:
    """Eine Verrundung ist auch ein Zylinder — sie eine Bohrung zu nennen
    setzte eine Schraube in eine Wand.
    """
    rounded = edit.fillet(block(), 3.0, "vertical")

    found = features_of(rounded)

    assert not [entry for entry in found.values() if entry.kind == "hole"]


def test_the_planar_faces_come_with_their_area() -> None:
    found = features_of(block())

    areas = sorted(entry.params["area"] for entry in found.values() if entry.kind == "face")
    assert areas == [600.0, 600.0, 800.0, 800.0, 1200.0, 1200.0]


# --- as operations --------------------------------------------------------------


def run(op: str, entry: SceneObject | None, profile: Profile, **params: object):
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry} if entry else {}),
            inputs=[entry] if entry else [],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def test_the_primitives_come_out_marked_as_brep(profile: Profile) -> None:
    result = run("create_brep_box", None, profile, width=40.0, depth=30.0, height=20.0)

    assert result.outputs[0].kind == "brep"
    assert result.outputs[0].mesh.volume == pytest.approx(24000.0, rel=1e-9)


def test_create_brep_cylinder_stands_on_the_bed(profile: Profile) -> None:
    result = run("create_brep_cylinder", None, profile, diameter=20.0, height=15.0)

    assert result.outputs[0].mesh.bounds.minimum[2] == pytest.approx(0.0, abs=1e-6)


def test_fillet_edges_runs_as_an_operation(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Block", mesh=block(), kind="brep")

    result = run("fillet_edges", entry, profile, radius=3.0, edges="vertical")

    corner = 9.0 - math.pi * 9.0 / 4.0
    assert result.outputs[0].mesh.volume == pytest.approx(24000.0 - 4 * corner * 20.0, rel=1e-9)
    assert result.outputs[0].kind == "brep"


def test_chamfer_edges_runs_as_an_operation(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Block", mesh=block(), kind="brep")

    result = run("chamfer_edges", entry, profile, distance=2.0, edges="vertical")

    assert result.outputs[0].mesh.volume == pytest.approx(24000.0 - 4 * 2.0 * 20.0, rel=1e-9)


def test_a_mesh_body_is_turned_away_with_a_sentence(profile: Profile) -> None:
    """§33.1: der Titel nennt die Art des Fehlers, das Detail seinen Grund.

    Vorher war das eine ValidationError, und die heißt „Ein Wert liegt
    außerhalb des zulässigen Bereichs" — für einen Radius, der einwandfrei war.
    Der erklärende Satz stand im Detail und erreichte den Prüfbericht nicht;
    wer danach suchte, suchte bei den Zahlen.
    """
    entry = SceneObject(
        id="obj_1", name="Netz", mesh=MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    )

    with pytest.raises(NeedsSolidError) as problem:
        run("fillet_edges", entry, profile, radius=1.0, edges="all")

    error = problem.value
    assert "exakten Körper" in str(error.title)
    assert error.detail is not None and "Netz" in str(error.detail)
    assert error.object_id == "obj_1", "der Fehler nennt den Körper, den er meint"
    assert error.suggestions, "Regel 17: nie ohne Handlungsvorschlag"


def test_brep_to_mesh_is_a_step_in_the_stack(profile: Profile) -> None:
    """§30: eine Richtung — und rücknehmbar, weil es eine Operation ist wie
    jede andere.
    """
    entry = SceneObject(id="obj_1", name="Block", mesh=block(), kind="brep")

    result = run("brep_to_mesh", entry, profile, deflection=0.05)

    assert result.outputs[0].kind == "mesh"
    assert isinstance(result.outputs[0].mesh, MeshData)
    assert [finding.code for finding in result.findings] == ["brep.converted"]


# --- the whole way --------------------------------------------------------------


def test_a_step_file_becomes_a_scene_object(profile: Profile, tmp_path: Path) -> None:
    payload = step.write(edit.fillet(block(), 3.0, "vertical"))
    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = payload
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/teil.step", sha256=""
    )
    History(project.document).apply(
        "STEP laden", [OperationDraft(op="load_step", params={"source": "src_1"})]
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    entry = result.scene.objects["obj_1"]
    assert entry.kind == "brep"
    assert entry.mesh.volume == pytest.approx(23845.4867, rel=1e-6)


def test_the_stack_carries_a_body_through_fillet_and_conversion(
    profile: Profile,
) -> None:
    """Markierung an jedem Schritt richtig — das dritte P12-Kriterium (§40)."""
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Quader",
        [
            OperationDraft(
                op="create_brep_box", params={"width": 40.0, "depth": 30.0, "height": 20.0}
            )
        ],
    )
    history.apply(
        "Verrunden",
        [OperationDraft(op="fillet_edges", inputs=("obj_1",), params={"radius": 3.0})],
    )
    history.apply("Netz", [OperationDraft(op="brep_to_mesh", inputs=("obj_1",), params={})])

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    assert result.scene.objects["obj_1"].kind == "mesh"

    History(project.document).undo()
    back = evaluate(project.document, profile, sources=ProjectSources(project))
    assert back.scene.objects["obj_1"].kind == "brep", "one undo brings the exact body back"


def test_a_brep_object_exports_as_step(profile: Profile, tmp_path: Path) -> None:
    entry = SceneObject(
        id="obj_1", name="Block", mesh=edit.fillet(block(), 3.0, "vertical"), kind="brep"
    )

    plan = plan_export([entry], project_name="Teil", profile=profile, export_format="step")
    written = write_plan(plan, tmp_path, "step")

    assert written[0].name == "Teil_Block.step"
    again = step.read(written[0].read_bytes())
    assert again.volume == pytest.approx(entry.mesh.volume, rel=1e-9)


def test_a_mesh_cannot_pretend_to_be_a_step(profile: Profile) -> None:
    mesh = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))

    with pytest.raises(ValidationError) as problem:
        export_bytes(mesh, "step", None, "", mesh)

    assert problem.value.constraint == "needs_brep"


def test_step_comes_back_addressable_and_stable() -> None:
    """Ein STEP-Körper ist adressierbar, und zwar bei jedem Laden gleich.

    Das Konzept P15 führte das als Lücke D16 („STEP-Import wird nicht
    kanonisiert — Flächen kommen nicht adressierbar zurück"). Der Befund kam
    aus dem Vergleich mit einer anderen Anwendung und wurde ungeprüft
    übernommen; er trifft auf Formwerk nicht zu. `load_step` ruft `features_of`
    wie jede andere B-Rep-Operation.

    Geprüft wird trotzdem, und zwar das, worauf es ankommt: nicht nur *dass*
    Flächen zurückkommen, sondern dass dieselbe Datei dieselben Namen ergibt.
    Wäre die Reihenfolge zufällig, zeigte eine gespeicherte Skizzenebene
    (`feature:face_3`) morgen auf eine andere Wand — und niemand sähe, warum.
    """
    if not available():
        pytest.skip("ohne OpenCASCADE gibt es kein STEP")

    payload = step.write(edit.box(40.0, 30.0, 20.0))
    runs = [
        {
            key: (round(entry.params["area"], 4), tuple(round(v, 6) for v in entry.params["centre"]))
            for key, entry in features_of(step.read(payload)).items()
        }
        for _ in range(3)
    ]

    assert len(runs[0]) == 6, "sechs Wände, sechs Namen"
    assert runs[0] == runs[1] == runs[2], "und jedes Laden ergibt dieselben"
