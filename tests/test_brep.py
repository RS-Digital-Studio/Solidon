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
from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere

from app.core.brep import edit, step
from app.core.brep.features import features_of
from app.core.brep.kernel import Solid, available, tessellate
from app.core.errors import GeometryError, NeedsSolidError, ValidationError
from app.core.export.writer import export_bytes, plan_export, write_plan
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.perceive.features import detect
from app.core.registry import REGISTRY
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.cancel import NeverCancelled
from app.core.scene.project import ProjectSources, new_project
from app.core.types import Mesh, OpContext, Profile, Scene, SceneObject, Source, kind_of
from app.core.units import EPS_DISPLAY, EPS_GEOM

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


def test_the_bounding_box_comes_from_the_shape_not_from_the_triangles() -> None:
    """Der Hüllquader eines exakten Körpers ist exakt (§30, Regel 6).

    Er kam aus der Tessellation und war damit konstant rund 0,025 mm zu klein —
    die halbe Abweichung, die das Anzeigenetz haben darf. Bei Ø 50 stand
    49,9755 mm, wo Fusion denselben Körper mit 25,00 mm Radius misst. Daran
    hängen die Maße im Baum, die Bauraumprüfung, das Anordnen, der Haftungsrand
    und jede Passungsprüfung: ein Zapfen Ø 6 verlor so ein Zehntel seines
    Spiels, bevor jemand gedruckt hatte.
    """
    solid = edit.cylinder(diameter=50.0, height=40.0)
    box = solid.bounds

    assert box.size[0] == pytest.approx(50.0, abs=EPS_GEOM)
    assert box.size[1] == pytest.approx(50.0, abs=EPS_GEOM)
    assert box.size[2] == pytest.approx(40.0, abs=EPS_GEOM)
    # Und die Tessellation bleibt, was sie ist: eine Annäherung, die es nicht
    # trifft. Stünde hier dieselbe Zahl, käme der Hüllquader weiter von dort.
    assert solid.to_mesh().bounds.size[0] < 50.0 - EPS_GEOM


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


def test_a_failed_difference_names_the_editing_not_a_connection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine Bohrung zieht ab; ihre Meldung darf nicht vom Verbinden sprechen."""
    import OCP.BRepAlgoAPI as brep_api  # noqa: N813 - Name der externen OCP-API

    class BrokenBoolean:
        """Kleinster Ersatz für einen Booleschen Builder ohne Ergebnis."""

        def __init__(self) -> None:
            pass

        def SetNonDestructive(self, _value: bool) -> None:  # noqa: N802
            pass

        def SetArguments(self, _values: object) -> None:  # noqa: N802
            pass

        def SetTools(self, _values: object) -> None:  # noqa: N802
            pass

        def Build(self) -> None:  # noqa: N802 - bildet die externe OCP-API nach
            pass

        def IsDone(self) -> bool:  # noqa: N802 - bildet die externe OCP-API nach
            return False

    monkeypatch.setattr(brep_api, "BRepAlgoAPI_Cut", BrokenBoolean)
    part = block()

    with pytest.raises(GeometryError) as caught:
        edit.boolean("difference", [part, part])

    text = str(caught.value.detail)
    assert "Bearbeitung" in text
    assert "Verschieben Sie" in text
    assert "verbinden" not in text.casefold()


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


def test_the_object_name_travels_into_the_step_file() -> None:
    """Sonst heißt das Teil in Fusion „Körper1" (§29).

    Der Übersetzer schreibt ohne Zutun seinen eigenen Namen in das PRODUCT —
    „Open CASCADE STEP translator 7.9 1" —, und das ist der Name, den ein
    fremdes Programm anzeigt. Der Objektname steht im Dokument die ganze Zeit
    da; er ging nur auf dem Weg verloren. Beim 3MF war das schon einmal ein
    Fund, dort kam eine Baugruppe als „Object 1, Object 2" an.
    """
    payload = step.write(block(), "Halteklotz").decode("utf-8", errors="replace")

    assert "Halteklotz" in payload
    assert "Open CASCADE STEP translator" not in payload.split("DATA;")[1].split("ENDSEC;")[0]


def test_a_step_export_carries_the_name_from_the_scene(profile: Profile, tmp_path: Path) -> None:
    """Und zwar über den ganzen Weg, nicht nur in der einen Funktion."""
    entry = SceneObject(id="obj_1", name="Lagerbock", mesh=block(), kind="brep")

    plan = plan_export([entry], project_name="Teil", profile=profile, export_format="step")
    written = write_plan(plan, tmp_path, "step")

    assert "Lagerbock" in written[0].read_text(encoding="utf-8", errors="replace")


def test_a_broken_step_file_is_a_user_error() -> None:
    with pytest.raises(ValidationError):
        step.read(b"this is not a STEP file")


def test_step_knows_its_own_suffixes() -> None:
    assert step.is_step(".STEP") and step.is_step(".stp")
    assert not step.is_step(".stl")


# --- Features aus der Topologie -------------------------------------------------


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


def test_a_brep_feature_names_all_its_viewport_triangles() -> None:
    """Eine exakte Fläche ist nicht dasselbe wie ein Dreieck des Anzeigenetzes.

    Die Bohrungswand ist im B-Rep genau **eine** Fläche. Im Viewport besteht
    sie aus vielen Dreiecken. ``features_of`` schrieb früher die Nummer der
    B-Rep-Fläche als ``face_indices`` hinein; der Viewport las sie als
    Dreiecksnummer und färbte dadurch einen einzelnen Keil der Außenwand.
    """
    import numpy as np

    diameter = 5.2
    drilled = edit.boolean(
        "difference",
        [edit.cylinder(9.0, 13.0), edit.moved(edit.cylinder(diameter, 20.0), (0.0, 0.0, -3.0))],
    )

    hole = next(entry for entry in features_of(drilled).values() if entry.kind == "hole")
    assert len(hole.face_indices) > 12, "ein runder Mantel braucht viele Anzeigedreiecke"

    triangles = np.asarray(drilled.raw.triangles)[list(hole.face_indices)]
    radii = np.linalg.norm(triangles[:, :, :2], axis=2)
    assert radii == pytest.approx(diameter / 2.0, abs=drilled.deflection), (
        "jede markierte Ecke liegt auf der Bohrungswand, keine auf der Außenwand"
    )


def test_brep_features_partition_the_whole_simple_body() -> None:
    """Beim einfachen Rohr bleibt kein Dreieck fremd und keines doppelt."""
    drilled = edit.boolean(
        "difference",
        [edit.cylinder(9.0, 13.0), edit.moved(edit.cylinder(5.2, 20.0), (0.0, 0.0, -3.0))],
    )
    groups = [set(feature.face_indices) for feature in features_of(drilled).values()]

    assert set().union(*groups) == set(range(drilled.triangle_count))
    assert sum(len(group) for group in groups) == drilled.triangle_count, (
        "jedes Dreieck gehört genau einer exakten Fläche"
    )


def test_a_rounded_corner_is_not_reported_as_a_hole() -> None:
    """Eine Verrundung ist auch ein Zylinder — sie eine Bohrung zu nennen
    setzte eine Schraube in eine Wand.
    """
    rounded = edit.fillet(block(), 3.0, "vertical")

    found = features_of(rounded)

    assert not [entry for entry in found.values() if entry.kind == "hole"]
    # **Und sie ist auch nicht nichts.** Solange der Ausschnitt verworfen wurde,
    # war die Zusicherung oben grün, weil überhaupt kein Merkmal entstand — sie
    # hätte nicht gemerkt, dass die vier Kanten spurlos verschwinden.
    fillets = [entry for entry in found.values() if entry.kind == "fillet"]
    assert len(fillets) == 4, f"vier senkrechte Kanten: {sorted(found)}"
    # Kein Einpassen: der Radius steht exakt in der Topologie.
    assert {entry.params["radius"] for entry in fillets} == {3.0}
    assert not any(entry.params["recess"] for entry in fillets), "Außenkanten, keine Kehlen"


def test_a_hollow_corner_is_a_throat_and_an_outer_one_is_not() -> None:
    """Beide sind Zylinderausschnitte mit demselben Radius; unterscheiden lässt
    sie nur, auf welcher Seite das Material liegt.

    Nicht über die Flächenorientierung — die kam an den vier gleichen Kanten
    eines Quaders zweimal so und zweimal anders heraus.
    """
    profile = edit.boolean("union", [edit.box(40.0, 10.0, 10.0), edit.box(10.0, 10.0, 40.0)])

    fillets = [
        entry
        for entry in features_of(edit.fillet(profile, 3.0, "all")).values()
        # **Nur die Kanten.** Die Ecken, an denen drei zusammenlaufen, sind
        # Kugelstücke und heißen seit derselben Erweiterung auch ``fillet``;
        # ihre Zahl hängt an der Gestalt und nicht an der Frage dieses Tests.
        if entry.kind == "fillet" and entry.params["length"] > 0.0
    ]

    throats = [entry for entry in fillets if entry.params["recess"]]
    assert len(throats) == 2, f"das L hat eine einspringende Ecke: {len(fillets)} Ausschnitte"
    assert len(fillets) - len(throats) == 26


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
    assert "bearbeitbare Flächen und Kanten" in str(error.title)
    assert error.detail is not None and "festen Dreiecken" in str(error.detail)
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


# --- der ganze Weg --------------------------------------------------------------


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
    """Und der Fehler sagt, worum es geht.

    Er war eine ``ValidationError``, und deren Titel lautet „Ein Wert liegt
    außerhalb des zulässigen Bereichs" — im Dialog stand er über der richtigen
    Erklärung. Hier ist kein Wert außerhalb eines Bereichs; hier hat der Körper
    die falsche Art.
    """
    mesh = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))

    with pytest.raises(NeedsSolidError) as problem:
        export_bytes(mesh, "step", None, "", mesh)

    assert problem.value.values["constraint"] == "needs_brep"
    assert "STEP" in str(problem.value.detail)


def test_step_comes_back_addressable_and_stable() -> None:
    """Ein STEP-Körper ist adressierbar, und zwar bei jedem Laden gleich.

    Das Konzept P15 führte das als Lücke D16 („STEP-Import wird nicht
    kanonisiert — Flächen kommen nicht adressierbar zurück"). Der Befund kam
    aus dem Vergleich mit einer anderen Anwendung und wurde ungeprüft
    übernommen; er trifft auf Solidon nicht zu. `load_step` ruft `features_of`
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
            key: (
                round(entry.params["area"], 4),
                tuple(round(v, 6) for v in entry.params["centre"]),
            )
            for key, entry in features_of(step.read(payload)).items()
        }
        for _ in range(3)
    ]

    assert len(runs[0]) == 6, "sechs Wände, sechs Namen"
    assert runs[0] == runs[1] == runs[2], "und jedes Laden ergibt dieselben"


def test_a_round_stud_is_not_a_hole() -> None:
    """Auf welcher Seite das Material liegt, entscheidet den Namen (§21).

    Jede geschlossene Zylinderfläche galt als Bohrung. Ein Ø-8-Zapfen, in
    Fusion gebaut und über STEP zurückgeholt, kam damit als „hole,
    diameter 8.0, depth 40" an — und dasselbe galt für jede Säule, jeden Dom
    und jeden Gewindekern. Das Vokabular aus §21 hat ``pin`` seit je; benutzt
    wurde es nur von den Bausteinen, die ihre Merkmale selbst benennen.
    """
    stud = edit.cylinder(diameter=8.0, height=40.0)

    kinds = {feature.kind for feature in features_of(stud).values()}

    assert "pin" in kinds, "ein Vollzylinder ist ein Zapfen"
    assert "hole" not in kinds, "und ganz sicher keine Bohrung"


def test_a_bore_through_a_block_stays_a_hole() -> None:
    """Die Gegenprobe — sonst wäre die Unterscheidung nur umgedreht."""
    from app.core.brep import edit as brep_edit

    drilled = brep_edit.boolean("difference", [block(), brep_edit.cylinder(8.0, 60.0)])

    kinds = {feature.kind for feature in features_of(drilled).values()}

    assert "hole" in kinds
    assert "pin" not in kinds


def test_losing_the_exact_body_is_said_where_it_happens(profile: Profile) -> None:
    """Der Weg von B-Rep zu Netz ist erlaubt, aber eine Einbahnstraße.

    Vorher ging man sie unbemerkt: „Aushöhlen" auf einem exakten Quader gibt
    Dreiecke zurück, und erst drei Schritte später lehnte „Tasche schneiden"
    mit „hier liegt ein Netz" ab — neben einer Operation, die nichts dafür
    kann. Gesagt wird es jetzt bei der Operation, die es verursacht.
    """
    project = new_project("centauri-carbon-2", "pla")
    history = History(project.document)
    history.apply(
        "Exakter Quader",
        [OperationDraft(op="create_brep_box", params={"width": 40, "depth": 40, "height": 40})],
    )

    before = evaluate(project.document, profile, sources=ProjectSources(project))
    assert [entry.kind for entry in before.scene.objects.values()] == ["brep"]
    assert not [f for f in before.scene.report.findings if f.code == "evaluate.exact_became_mesh"]

    history.apply(
        "Aushöhlen",
        [OperationDraft(op="hollow_object", inputs=("obj_1",), outputs=("obj_1",), params={})],
    )
    after = evaluate(project.document, profile, sources=ProjectSources(project))

    assert [entry.kind for entry in after.scene.objects.values()] == ["mesh"]
    said = [f for f in after.scene.report.findings if f.code == "evaluate.exact_became_mesh"]
    assert said, "der Verlust der Exaktheit gehört in den Bericht"
    assert said[0].severity == "info", "es ist ein erlaubter Weg, keine Warnung"
    assert said[0].values["op"] == "hollow_object", "und er nennt, wer ihn gegangen ist"


def test_the_exact_bore_takes_exactly_what_the_formula_says() -> None:
    """Die Kennzahl gegen den analytischen Körper, nicht gegen einen Vorlauf.

    Ein Zylinderschnitt hat eine geschlossene Formel, und der exakte Kern muss
    sie treffen — nicht ungefähr, sondern bis auf die Rechengenauigkeit. Genau
    das ist der Grund, aus dem es ihn gibt: Auf einem Netz wäre die Bohrung ein
    Vieleck mit ``BORE_SECTIONS`` Seiten und das Volumen um ein knappes Promille
    daneben.
    """
    from app.core.brep import edit as brep_edit

    solid = brep_edit.box(40.0, 30.0, 20.0)
    drilled = brep_edit.bore(solid, position=(0.0, 0.0, 20.0), axis="z", diameter=6.0)

    assert drilled.volume == pytest.approx(24000.0 - math.pi * 9.0 * 20.0, rel=1e-9)
    assert drilled.is_closed


def test_a_blind_bore_stops_at_its_depth() -> None:
    """Tiefe null bohrt durch, jede andere hört auf — dieselbe Zusicherung wie
    auf der Mesh-Seite, weil dieselben Parameter dasselbe bedeuten müssen.
    """
    from app.core.brep import edit as brep_edit

    solid = brep_edit.box(40.0, 30.0, 20.0)
    blind = brep_edit.bore(solid, position=(0.0, 0.0, 20.0), axis="z", diameter=6.0, depth=8.0)

    assert blind.volume == pytest.approx(24000.0 - math.pi * 9.0 * 8.0, rel=1e-9)
    assert blind.is_closed, "ein Sackloch lässt den Boden stehen"


def test_resizing_a_bore_keeps_an_exact_body(profile: Profile) -> None:
    """Derselbe Kundenweg auf STEP: Maß ändern, ohne Flächen und Kanten in
    feste Dreiecke umzuwandeln.

    Vergrößern und Verkleinern werden gegen die analytischen Zylindervolumen
    geprüft. Ein Bild oder eine Tessellation wäre gerade bei diesem Kern die
    falsche Wahrheit.
    """
    original = edit.bore(block(), position=(0.0, 0.0, HEIGHT), axis="z", diameter=6.0)
    features = features_of(original)
    bore = next(entry for entry in features.values() if entry.kind == "hole")
    source = SceneObject(id="obj_1", name="Block", mesh=original, kind="brep", features=features)

    larger = run("resize_hole", source, profile, at_feature=bore.id, diameter=10.0).outputs[0]
    smaller = run("resize_hole", source, profile, at_feature=bore.id, diameter=4.0).outputs[0]

    assert larger.kind == smaller.kind == "brep"
    assert larger.mesh.volume == pytest.approx(
        WIDTH * DEPTH * HEIGHT - math.pi * (10.0 / 2.0) ** 2 * HEIGHT,
        rel=1e-9,
    )
    assert smaller.mesh.volume == pytest.approx(
        WIDTH * DEPTH * HEIGHT - math.pi * (4.0 / 2.0) ** 2 * HEIGHT,
        rel=1e-9,
    )
    assert larger.mesh.is_closed and smaller.mesh.is_closed
    assert larger.features[bore.id].params["diameter"] == pytest.approx(10.0)
    assert smaller.features[bore.id].params["diameter"] == pytest.approx(4.0)


def test_resizing_a_step_bore_uses_the_unrounded_topology(profile: Profile) -> None:
    """Ein STEP-Maß reist in doppelter Genauigkeit bis zum Werkzeug.

    Vier Nachkommastellen gehören in die Anzeige, nicht zwischen den exakten
    Körper und seinen Füllring. Sonst bleibt beim Vergrößern eine hauchdünne
    alte Lippe stehen; beim Verkleinern schwimmt ein loser Ring im Loch.
    """
    original_diameter = 6.00004
    original_depth = 8.00004
    original = edit.bore(
        block(),
        position=(0.0, 0.0, HEIGHT),
        axis="z",
        diameter=original_diameter,
        depth=original_depth,
    )
    features = features_of(original)
    bore = next(entry for entry in features.values() if entry.kind == "hole")
    source = SceneObject(id="obj_1", name="Block", mesh=original, kind="brep", features=features)

    assert bore.params["diameter"] == pytest.approx(original_diameter, abs=EPS_GEOM)
    assert bore.params["depth"] == pytest.approx(original_depth, abs=EPS_GEOM)

    unchanged = run(
        "resize_hole",
        source,
        profile,
        at_feature=bore.id,
        diameter=float(bore.params["diameter"]),
    )
    assert unchanged.outputs[0] is source, "bloßes Bestätigen ändert den exakten Körper nicht"

    for target in (10.0, 4.0):
        changed = run("resize_hole", source, profile, at_feature=bore.id, diameter=target).outputs[
            0
        ]
        holes = [entry for entry in changed.features.values() if entry.kind == "hole"]
        expected = WIDTH * DEPTH * HEIGHT - math.pi * (target / 2.0) ** 2 * original_depth

        assert changed.mesh.volume == pytest.approx(expected, rel=1e-9)
        assert len(holes) == 1, "kein alter Rand und kein loser Füllring"
        assert holes[0].params["diameter"] == pytest.approx(target, abs=EPS_GEOM)
        assert holes[0].params["depth"] == pytest.approx(original_depth, abs=EPS_GEOM)


def test_repeated_mesh_resizing_keeps_a_blind_bore_blind(profile: Profile) -> None:
    """Ein gerundeter Anzeigewert darf die Bohrung nicht schrittweise vertiefen."""
    exact = edit.bore(
        edit.box(30.0, 30.0, 20.0),
        position=(0.0, 0.0, 20.0),
        axis="z",
        diameter=6.00004,
        depth=8.00004,
    )
    mesh = as_mesh_data(exact.to_mesh())
    features = detect(mesh)
    bore = next(entry for entry in features.values() if entry.kind == "hole")
    source = SceneObject(id="obj_1", name="Block", mesh=mesh, features=features)

    smaller = run("resize_hole", source, profile, at_feature=bore.id, diameter=4.0).outputs[0]
    reduced = smaller.features[bore.id]
    larger = run("resize_hole", smaller, profile, at_feature=bore.id, diameter=8.0).outputs[0]
    enlarged = larger.features[bore.id]

    assert not reduced.params["through"]
    assert not enlarged.params["through"]
    assert reduced.params["depth"] == pytest.approx(bore.params["depth"], abs=EPS_DISPLAY / 10.0)
    assert enlarged.params["depth"] == pytest.approx(bore.params["depth"], abs=EPS_DISPLAY / 10.0)
    assert larger.mesh.bounds.minimum == pytest.approx(mesh.bounds.minimum, abs=EPS_GEOM)
    assert larger.mesh.bounds.maximum == pytest.approx(mesh.bounds.maximum, abs=EPS_GEOM)


def test_the_exact_bore_agrees_with_the_mesh_on_direction_at_the_centre() -> None:
    """Skizze 10: bei der Vorgabeposition — der Achsmitte — entschieden die zwei
    Kerne den Tiebreak verschieden. Das Netz nimmt ``>=`` (nach unten), der
    exakte Kern nahm ``>`` (nach oben); wer zwischen ``create_box`` und
    ``create_brep_box`` umschaltete, bohrte in die Gegenrichtung — und
    ``MENU_TWINS`` ist dann kein Umschalten. Beide gehen jetzt zur
    tieferliegenden Hälfte, gemessen am Schwerpunkt.
    """
    from app.core.brep import edit as brep_edit

    solid = brep_edit.box(40.0, 30.0, 20.0)  # z 0..20, Mitte bei z = 10
    bored = brep_edit.bore(solid, position=(0.0, 0.0, 10.0), axis="z", diameter=6.0, depth=5.0)

    # Nach unten gebohrt (z 5..10 entfernt) steigt der Schwerpunkt über die Mitte.
    assert float(bored.mesh.raw.center_mass[2]) > 10.0, "ins Material nach unten, wie das Netz"


def test_a_bore_across_the_body_follows_its_axis() -> None:
    """Quer durch, entlang X — die Achse geht in den Zylinder und nicht in eine
    nachträgliche Drehung.
    """
    from app.core.brep import edit as brep_edit

    solid = brep_edit.box(40.0, 30.0, 20.0)
    across = brep_edit.bore(solid, position=(-20.0, 0.0, 10.0), axis="x", diameter=6.0)

    assert across.volume == pytest.approx(24000.0 - math.pi * 9.0 * 40.0, rel=1e-9)


def test_the_exact_branch_survives_a_bore(profile: Profile) -> None:
    """**Der Punkt, um den es geht.** Wer einen exakten Quader anlegt und eine
    Bohrung setzt, hatte danach ein Netz — und damit fielen Fase, Verrundung,
    Formschräge, Fläche versetzen, exaktes Aushöhlen, Tasche schneiden und der
    STEP-Export aus. Der exakte Zweig endete nach einem Schritt.

    Geprüft wird deshalb nicht die Bohrung, sondern was **nach** ihr noch geht:
    eine Verrundung, die einen exakten Körper braucht.
    """
    project = new_project("centauri-carbon-2", "pla")
    history = History(project.document)
    history.apply(
        "Exakter Quader",
        [OperationDraft(op="create_brep_box", params={"width": 40, "depth": 30, "height": 20})],
    )
    history.apply(
        "Bohrung",
        [
            OperationDraft(
                op="drill_brep_hole",
                inputs=("obj_1",),
                params={"diameter": 6.0, "z": 20.0, "compensate": False},
            )
        ],
    )
    history.apply(
        "Verrundung",
        [OperationDraft(op="fillet_edges", inputs=("obj_1",), params={"radius": 2.0})],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.stopped_at is None, "die Kette läuft durch"
    assert [entry.kind for entry in result.scene.objects.values()] == ["brep"]
    assert not [
        f for f in result.scene.report.findings if f.code == "evaluate.exact_became_mesh"
    ], "eine exakte Bohrung verliert die Exaktheit nicht"


def test_the_exact_bore_and_its_twin_read_the_same_parameters() -> None:
    """Beide Kerne teilen **ein** Schema, keine zwei gleichlautenden.

    Daran hängt ``change_kernel``: Es reicht die Parameter des einen Schritts
    an den anderen weiter, und wortgleiche Schemata laufen beim nächsten
    Nachbessern auseinander. Dasselbe Objekt kann das nicht.
    """
    from app.core.registry import MENU_TWINS, REGISTRY

    assert MENU_TWINS["drill_brep_hole"] == "drill_hole"
    exact = REGISTRY.get("drill_brep_hole")
    mesh = REGISTRY.get("drill_hole")
    assert exact.params is mesh.params, "ein Schema, nicht zwei gleichlautende"
    assert exact.deterministic, "ohne Rückfallkette braucht es keinen Startwert"


def test_switching_a_bore_between_the_kernels_keeps_its_values(profile: Profile) -> None:
    """Ein gesetzter Schritt lässt sich nachträglich umstellen — mit denselben
    Werten, sonst wäre es eine andere Bohrung.
    """
    project = new_project("centauri-carbon-2", "pla")
    history = History(project.document)
    history.apply(
        "Exakter Quader",
        [OperationDraft(op="create_brep_box", params={"width": 40, "depth": 30, "height": 20})],
    )
    values = {"diameter": 6.0, "x": 0.0, "y": 0.0, "z": 20.0, "compensate": False}
    history.apply(
        "Bohrung im Netz",
        [OperationDraft(op="drill_hole", inputs=("obj_1",), params=dict(values))],
    )
    bore_step = project.document.ops[-1]

    history.change_kernel(bore_step.id, "drill_brep_hole", dict(values))

    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert [entry.kind for entry in result.scene.objects.values()] == ["brep"]
    body = next(iter(result.scene.objects.values()))
    assert body.mesh.volume == pytest.approx(24000.0 - math.pi * 9.0 * 20.0, rel=1e-9)


def test_the_corner_where_three_fillets_meet_is_one_too() -> None:
    """Verrundet man alle Kanten, bleibt an jeder Ecke ein Kugelstück übrig.

    Es fiel bis dahin durch: ``_describe`` kannte Ebene und Zylinder, und acht
    von 26 Flächen waren damit nichts — ausgerechnet die, die der Kunde als
    „abgerundete Ecke" sieht.
    """
    rounded = edit.fillet(block(), 2.0, "all")

    found = features_of(rounded)

    fillets = [entry for entry in found.values() if entry.kind == "fillet"]
    # Zwölf Kanten und acht Ecken: der Quader hat keine Fläche mehr, die durchfällt.
    assert len(fillets) == 20, f"12 Kanten + 8 Ecken: {sorted(found)}"
    assert len(found) == len(rounded.faces()), "keine Fläche bleibt unbenannt"
    corners = [entry for entry in fillets if entry.params["length"] == 0.0]
    assert len(corners) == 8
    assert {entry.params["radius"] for entry in corners} == {2.0}


def test_a_socket_is_a_sphere_and_not_a_corner() -> None:
    """Beide sind Kugelausschnitte — die Größe trennt sie nicht.

    Der erste Versuch maß den Anteil an der Vollkugel: Eckverrundung 0,125,
    volle Kugel 1,000. Das trennt falsch, denn eine Pfanne ist nie mehr als
    eine Halbkugel, und eine flache Kalotte deckt selbst 0,1 ab. Was sie
    trennt, ist die Nachbarschaft: An einer Ecke laufen verrundete Kanten
    zusammen, an einer Pfanne nicht.
    """
    ball = Solid(BRepPrimAPI_MakeSphere(6.0).Shape())
    hollowed = edit.boolean("difference", [block(), edit.moved(ball, (0.0, 0.0, 20.0))])

    found = features_of(hollowed)

    spheres = [entry for entry in found.values() if entry.kind == "sphere"]
    assert len(spheres) == 1, f"die Mulde ist eine Kugel: {sorted(found)}"
    assert spheres[0].params["recess"], "eingelassen, keine Kuppel"
    assert not [entry for entry in found.values() if entry.kind == "fillet"]


def test_a_corner_fillet_leaves_no_degenerate_triangles() -> None:
    """Am Pol einer Kugelfläche entstand ein Dreieck mit zwei gleichen Ecken.

    **Die Fläche war dabei nie kaputt** — Euler-Zahl 2, Volumen unverändert,
    kein Loch. Aber ``is_watertight`` meldete „nein", weil trimesh die
    degenerierten Kanten als offen zählt, und das ist die Prüfung, die viele
    Werkzeuge fahren, unsere eigenen Tests eingeschlossen. In die exportierte
    STL wanderten die acht Dreiecke mit.

    **Zwei Fehlschlüsse liegen auf dem Weg dorthin, beide gemessen und
    verworfen:** ``is_watertight`` als Beweis für ein Loch — es ist keiner —,
    und „die drei Knotennummern sind nicht paarweise verschieden" als
    Bedingung. OCCT vergibt am Pol *zwei* Nummern für denselben Ort; erst
    trimesh führt sie beim Einlesen zusammen. Geprüft wird deshalb über die
    Koordinaten.
    """
    import numpy as np

    from app.core.geom.mesh import as_mesh_data

    solid = edit.fillet(edit.box(WIDTH, DEPTH, HEIGHT), 2.0, "all")
    mesh = as_mesh_data(solid.mesh).raw

    entartet = int(np.sum(mesh.area_faces <= EPS_GEOM))
    assert entartet == 0, f"{entartet} Dreiecke mit Fläche null"
    assert mesh.is_watertight, "acht Pole, acht offene Kanten — so sah es aus"
    assert mesh.euler_number == 2, "die Oberfläche war schon vorher geschlossen"
    assert solid.volume == pytest.approx(mesh.volume, rel=1e-3), (
        "das Weglassen darf am Körper nichts ändern"
    )


# --- was der Netz-Zwilling meldete und dieser nicht ------------------------------


def test_a_bore_that_swallows_the_body_is_refused(profile: Profile) -> None:
    """Ein Körper, der nichts ist, kommt nicht als Erfolg zurück.

    **Der schwerste Zwillingsbefund vom 27.08.2026.** OCCT rechnet sauber
    durch, wenn das Werkzeug den Körper vollständig deckt, und gibt eine leere
    Form zurück: null Volumen, null Flächen, nicht wasserdicht. Bis dahin ging
    die als Ergebnis durch — im Objektbaum stand danach ein Objekt mit Namen,
    das man anklicken, umbenennen und **speichern** konnte, und der Prüfbericht
    sagte kein Wort; gemeldet hätte es erst der Export.

    Der Netz-Zwilling wirft an derselben Stelle seit je, und zwar mit genau
    diesem Satz — er ist deshalb geteilt (``boolean.NOTHING_LEFT_*``) und nicht
    ein zweites Mal geschrieben. ``without_effect`` fängt den Fall nicht: Es
    prüft auf *nichts abgetragen*, hier wurde *alles* abgetragen.
    """
    from app.core.errors import GeometryError
    from app.core.geom.boolean import NOTHING_LEFT_TITLE

    body = run("create_brep_box", None, profile, width=40.0, depth=30.0, height=20.0).outputs[0]

    with pytest.raises(GeometryError) as caught:
        run("drill_brep_hole", body, profile, diameter=50.0)

    assert str(caught.value.title) == str(NOTHING_LEFT_TITLE)
    assert caught.value.suggestions, "ein Fehler ohne Weg nach vorn ist unfertig (Regel 17)"


def test_a_bore_over_the_edge_says_so_in_the_exact_kernel_too(profile: Profile) -> None:
    """Dieselbe Warnung wie im Netz — sie fehlte nur, weil die Signatur ein
    ``MeshData`` verlangte.

    Gemessen waren sechs von sechs Fällen still, bei geometrisch identischem
    Ergebnis (Abweichung unter 0,005 %). Die Prüfung liest nichts als den
    Hüllquader, und den trägt ``Solid`` auch; sie fragt jetzt nach einem
    Protokoll, wie ``without_effect`` es mit ``HasVolume`` vormacht.
    """
    body = run("create_brep_box", None, profile, width=40.0, depth=30.0, height=20.0).outputs[0]

    over = run("drill_brep_hole", body, profile, diameter=10.0, x=18.0)
    inside = run("drill_brep_hole", body, profile, diameter=10.0, x=0.0)

    assert "bore.over_the_edge" in {entry.code for entry in over.findings}
    # Die Gegenprobe: eine Bohrung im Material warnt nicht, sonst warnt jede.
    assert "bore.over_the_edge" not in {entry.code for entry in inside.findings}


def test_the_exact_shell_reports_what_the_mesh_twin_reports(profile: Profile) -> None:
    """*Exakt aushöhlen* gab in keinem einzigen Fall einen Befund zurück.

    Dreizehn Wandstärken gemessen, von 0,2 bis 50: Bei 15 mm kam ein Körper mit
    Nullspalt zurück — unverändertes Volumen und nicht mehr wasserdicht —,
    zwischen 16 und 50 passierte fast immer gar nichts, und gesagt wurde nie
    etwas. OCCT gibt bei zu großem negativem Offset die Eingangsform zurück,
    ohne zu werfen. Der Netz-Zwilling kennt für dieselbe Lage fünf Codes.

    Beide Befunde kommen aus derselben Fabrik wie beim Zwilling — sonst wäre
    hier der nächste Zwilling entstanden, statt einen zu beseitigen.
    """
    body = run("create_brep_box", None, profile, width=40.0, depth=30.0, height=20.0).outputs[0]

    hopeless = run("shell_exact", body, profile, wall=15.0)
    unprintable = run("shell_exact", body, profile, wall=0.3)
    sound = run("shell_exact", body, profile, wall=2.0)

    assert "hollow.too_thin" in {entry.code for entry in hopeless.findings}
    assert "hollow.wall_below_nozzle" in {entry.code for entry in unprintable.findings}

    # **Und der brauchbare Fall schweigt nicht — er berichtet.** Hier stand
    # „bleibt still" als Gegenprobe, und das schrieb den letzten Unterschied
    # zwischen den Zwillingen fest: Mit einer Wandstärke, die funktioniert,
    # sagte der Netz-Zwilling ``hollow.done`` mit seinen Zahlen und der exakte
    # gar nichts. Wie viel Material weg ist, ist der Grund, aus dem man
    # aushöhlt. Was die Gegenprobe wirklich meint, ist „keine **Warnung**".
    codes = {entry.code for entry in sound.findings}
    assert codes == {"hollow.done"}, codes
    assert all(entry.severity == "info" for entry in sound.findings)
    fertig = next(entry for entry in sound.findings if entry.code == "hollow.done")
    assert fertig.values["removed_cm3"] > 0.0, "ohne die Zahl ist die Meldung leer"


def test_the_printable_wall_comes_from_the_profile_not_from_a_number(profile: Profile) -> None:
    """Die Grenze ist zwei Extrusionsbreiten — je Drucker eine andere Zahl.

    Im Schema stand ``minimum=0.4`` am Netz und ``0.2`` am exakten Kern. Die
    Abweichung fiel auf; der eigentliche Fund ist, dass auch die 0,4 nur
    zufällig stimmt — für eine 0,4er Düse. Ein Schema-Minimum kann das nicht
    leisten, es steht zur Deklarationszeit fest und das Profil kommt mit dem
    Auftrag (§39, Regel 7).
    """
    from app.core.geom.hollow import below_printable_wall

    least = profile.minimum_wall_thickness
    assert least > 0.4, (
        f"dieser Drucker muss über der alten Schemazahl liegen, sonst prüft der "
        f"Test nichts: {least}"
    )

    assert below_printable_wall(least - 0.1, profile) is not None
    assert below_printable_wall(least + 0.1, profile) is None


def test_without_a_printer_there_is_no_wall_verdict(profile: Profile) -> None:
    """Ohne Drucker keine Aussage über die Wandstärke.

    Der Fall kommt vor — ein direkter Aufruf der Operation ohne Profil, wie
    ihn Tests und die Kommandozeile bauen. Die alte Zahlenkonstante brauchte
    keinen Drucker, ``Profile.minimum_wall_thickness`` schon; ohne diesen
    Zweig endete `shell_exact` dort in einem AttributeError. Gefunden von ce
    im Torlauf, an `test_the_exact_shell_leaves_exactly_the_wall`.

    Dieselbe Regel wie bei ``boolean.without_effect``: Die Grenze *ist* der
    Drucker, also gibt es sie ohne ihn nicht — und ein Aufrufer, der keinen
    kennt, soll keinen erfinden.
    """
    from app.core.geom.hollow import below_printable_wall

    assert below_printable_wall(0.1, None) is None
    # Die Gegenprobe: mit Drucker gibt es sehr wohl ein Urteil.
    assert below_printable_wall(0.1, profile) is not None


# --- Was die Tessellierung hinterlässt ------------------------------------------


def _with_a_t_junction() -> MeshData:
    """Zwei Dreiecke, deren gemeinsame Kante nur eines von ihnen kennt.

    Der Defekt aus dem Eiffelturm-Fund, im Kleinen: Die lange Kante des einen
    Dreiecks wurde beim Bau des Nachbarn von einem Punkt geteilt, und der
    anderen Seite hat es nie jemand gesagt. Kein Loch — die Flächen liegen
    lückenlos aneinander —, und trotzdem melden beide Seiten offene Kanten.
    """
    import numpy as np
    import trimesh

    from app.core.geom.mesh import MeshData

    punkte = np.array(
        [
            [0.0, 0.0, 0.0],  # 0
            [2.0, 0.0, 0.0],  # 1
            [1.0, 1.0, 0.0],  # 2  Spitze oben
            [1.0, 0.0, 0.0],  # 3  sitzt auf der Kante 0-1
            [1.0, -1.0, 0.0],  # 4 Spitze unten
        ],
        dtype=float,
    )
    # Oben ein ungeteiltes Dreieck über 0-1, unten zwei, die den Punkt 3 kennen.
    dreiecke = np.array([[0, 1, 2], [0, 3, 4], [3, 1, 4]], dtype=np.int64)
    return MeshData.of(trimesh.Trimesh(vertices=punkte, faces=dreiecke, process=False))


def test_the_stitcher_closes_a_seam_the_hole_filler_cannot() -> None:
    """Der Riss an der Flanke ist eine T-Kreuzung, kein Loch.

    Der Fall ist macOS: Ein Gewindebolzen ist dort als **Form** in Ordnung —
    geschlossen, ein Stück, richtiges Volumen, STEP trägt ihn —, aber seine
    Vernetzung ritzt an der Flanke. `_finely_meshed` half nicht, weil es
    ausschließlich versucht, feiner zu vernetzen; repariert wurde nie.

    Warum **Vernähen** und nicht Füllen: Gemessen an einem M6-Netz mit einem
    echten Loch lässt `repair.fill_holes` es offen und rührt kein Dreieck an —
    zu Recht, denn ein Dreieck über kollinearen Punkten hat keine Fläche. Was
    hier fehlt, ist kein Material, sondern ein Punkt, den die Nachbarfläche
    nicht kennt.

    Der echte Riss lässt sich auf dieser Plattform nicht erzeugen (unter
    Windows ist jede Größe dicht), also bekommt der Vernäher den Defekt
    vorgesetzt, den der Befund beschreibt.
    """
    from app.core.geom.repair import open_edge_count, stitch_t_junctions

    kaputt = _with_a_t_junction()
    vorher = open_edge_count(kaputt)
    assert vorher > 0, "der Prüfling muss offene Kanten haben, sonst prüft nichts"

    geheilt, naehte = stitch_t_junctions(kaputt)

    assert naehte > 0, "die T-Kreuzung muss gefunden werden"
    assert open_edge_count(geheilt) < vorher


def test_a_repair_that_makes_it_worse_is_dropped() -> None:
    """Drei Nähte heißen nicht drei geschlossene Kanten.

    Beim Bauen gemessen und beinahe übersehen: An einem Netz, dessen Ränder
    gar keine T-Kreuzungen sind — ein absichtlich zerlegter Würfel —, findet
    der Vernäher trotzdem drei Nähte und hinterlässt **18 offene Kanten statt
    15**. Er teilt Flächen an Punkten, die dort zufällig aufsitzen.

    Die Zahl der Nähte ist damit kein Erfolgsmaß. `_stitched` vergleicht
    deshalb die offenen Kanten und gibt das Original zurück, wenn es nicht
    besser wurde: Eine Reparatur, die verschlimmert, ist keine.
    """
    import trimesh

    from app.core.brep.kernel import _stitched
    from app.core.geom.mesh import MeshData
    from app.core.geom.repair import open_edge_count

    box = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    fein = box.subdivide()
    zerlegt = MeshData.of(
        trimesh.util.concatenate(
            [
                trimesh.Trimesh(vertices=fein.vertices, faces=fein.faces[:6], process=False),
                trimesh.Trimesh(vertices=box.vertices, faces=box.faces[3:], process=False),
            ]
        )
    )
    assert not zerlegt.is_watertight

    ergebnis = _stitched(zerlegt)

    assert ergebnis is zerlegt, "verschlimmerte Reparatur muss verworfen werden"
    assert open_edge_count(ergebnis) == open_edge_count(zerlegt)


def test_a_closed_mesh_never_reaches_the_stitcher(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Normalfall kostet die Frage, nicht die Arbeit.

    `is_watertight` sind 0,1 ms an einem Netz mit 13 744 Dreiecken, das
    Vernähen 2,6 ms. Die Abkürzung lohnt also — aber sie ist **nur** eine
    Abkürzung: Auch ohne sie käme dasselbe Netz heraus, weil der Vernäher an
    einem dichten Netz nichts findet.

    Deshalb prüft dieser Test nicht das Ergebnis, sondern ob der teure Weg
    überhaupt betreten wird. Der erste Anlauf verglich die Objektidentität und
    blieb grün, als die Bedingung ausgeschaltet war — er prüfte eine Zusage,
    die auch ohne sie gilt.
    """
    import trimesh

    from app.core.brep import kernel
    from app.core.geom import repair
    from app.core.geom.mesh import MeshData

    gerufen: list[int] = []
    echt = repair.stitch_t_junctions

    def zaehlend(mesh: MeshData) -> tuple[MeshData, int]:
        gerufen.append(1)
        return echt(mesh)

    monkeypatch.setattr(repair, "stitch_t_junctions", zaehlend)

    dicht = MeshData.of(trimesh.creation.box(extents=(4.0, 4.0, 4.0)))
    assert dicht.is_watertight

    assert kernel._stitched(dicht) is dicht
    assert not gerufen, "ein dichtes Netz darf den Vernäher nicht kosten"


def test_every_twin_pair_answers_the_same_question_the_same_way(profile: Profile) -> None:
    """Vier Paare, dieselben Eingaben, dieselben Befunde.

    Ein Zwilling ist dieselbe Handlung in zwei Rechenkernen, und der Kunde
    wählt zwischen ihnen über einen Haken im selben Dialog. Er erwartet also
    dasselbe Verhalten — und vor allem dieselben **Auskünfte**. Läuft ein Paar
    auseinander, merkt es niemand: Beide Wege funktionieren, nur einer
    schweigt.

    Drei Unterschiede sind einzeln gemeldet und einzeln behoben worden
    (`bore.over_the_edge`, der leere Körper beim zu großen Loch,
    `hollow.too_thin`), und beim vierten Anlauf stellte sich heraus, dass noch
    einer offen war: Mit einer Wandstärke, die *funktioniert*, meldete das Netz
    `hollow.done` und der exakte Kern nichts. Einzeln gemeldete Fälle finden
    den nächsten nicht — dieser Test fährt alle Paare gegeneinander.

    Die Werte treffen absichtlich die Grenzen: ein Loch größer als der Körper,
    eine Wand dicker als das halbe Teil. Dort trennt sich, wer etwas sagt und
    wer schweigt.
    """
    from app.core.registry.registry import MENU_TWINS

    assert len(MENU_TWINS) >= 4, f"zu wenige Paare gefunden: {MENU_TWINS}"

    quader_exakt = run(
        "create_brep_box", None, profile, width=40.0, depth=30.0, height=20.0
    ).outputs[0]
    quader_netz = run("create_box", None, profile, width=40.0, depth=30.0, height=20.0).outputs[0]

    faelle: list[tuple[str, str, dict[str, object]]] = [
        ("drill_brep_hole", "drill_hole", {"diameter": 6.0}),
        ("drill_brep_hole", "drill_hole", {"diameter": 10.0, "x": 18.0}),
        ("shell_exact", "hollow_object", {"wall": 2.0}),
        ("shell_exact", "hollow_object", {"wall": 15.0}),
    ]

    abweichend: list[str] = []
    for exakt, netz, werte in faelle:
        assert MENU_TWINS.get(exakt) == netz, f"{exakt} ist nicht mehr mit {netz} gepaart"
        codes_exakt = {entry.code for entry in run(exakt, quader_exakt, profile, **werte).findings}
        codes_netz = {entry.code for entry in run(netz, quader_netz, profile, **werte).findings}
        # Verglichen wird die **Menge** der Codes, nicht ihre Zahl: Der
        # Netz-Zwilling darf zusätzlich über sein Raster sprechen, das der
        # exakte Kern nicht hat. Was beide kennen, müssen beide sagen.
        gemeinsam = codes_exakt | codes_netz
        fehlt_exakt = {code for code in gemeinsam if code in codes_netz and code not in codes_exakt}
        if fehlt_exakt & {"hollow.done", "hollow.too_thin", "bore.over_the_edge"}:
            abweichend.append(f"{exakt} schweigt zu {sorted(fehlt_exakt)} bei {werte}")

    assert not abweichend, abweichend


def test_every_opencascade_import_in_the_application_resolves() -> None:
    """Jeder ``from OCP.… import …`` in ``app/`` und ``tools/`` trifft einen Namen.

    OCP 8 hat Module leer zurückgelassen, statt sie zu entfernen: ``OCP.GCE2d``
    und ``OCP.TColgp`` importieren, aber ``GCE2d_MakeSegment`` und
    ``TColgp_Array1OfPnt2d`` gibt es nicht mehr. Der Fehler fällt erst, wenn die
    Zeile läuft — bei der Selbstschnittprüfung der Skizze war das kein Test in
    dieser Datei, sondern das Beispielprojekt „skizze-mit-massen" (05.09.2026).
    Statisch geprüft trifft es jede Stelle, auch die, die kein Test hier fährt.
    """
    import ast
    import importlib

    root = Path(__file__).resolve().parent.parent
    missing: list[str] = []
    for path in sorted([*(root / "app").rglob("*.py"), *(root / "tools").rglob("*.py")]):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom) or not node.module:
                continue
            if node.module != "OCP" and not node.module.startswith("OCP."):
                continue
            for alias in node.names:
                try:
                    getattr(importlib.import_module(node.module), alias.name)
                except Exception as problem:
                    missing.append(
                        f"{path.relative_to(root)}:{node.lineno} {node.module}.{alias.name}"
                        f" ({type(problem).__name__})"
                    )
    assert not missing, "\n".join(missing)


def test_an_open_result_of_an_exact_resize_is_an_error_not_a_scene_object(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Vertrag, nicht die Ursache: Ein offener Körper kommt nie in die Szene.

    An der Teppichklammer (Durchsicht vom 05.09.2026, Datei 19) kam
    ``resize_hole`` mit offener Tessellation zurück, und die Operation galt
    als gelungen — Volumen und Flächen waren da. Die Ursache ist behoben
    (``brep.features`` legt die Mitte auf die Achse); hier wird der Fall
    gestellt, damit die Frage nach der Geschlossenheit zum Erfolg gehört.
    """
    from app.core.geom import prepare_ops

    original = edit.bore(block(), position=(0.0, 0.0, HEIGHT), axis="z", diameter=6.0)
    features = features_of(original)
    bore = next(entry for entry in features.values() if entry.kind == "hole")
    source = SceneObject(id="obj_1", name="Block", mesh=original, kind="brep", features=features)

    class Open(Solid):
        @property
        def is_closed(self) -> bool:
            return False

    honest = edit.resize_bore(
        original,
        position=bore.params["centre"],
        direction=bore.params["axis"],
        previous_diameter=6.0,
        diameter=7.0,
        depth=float(bore.params["depth"]),
    )
    monkeypatch.setattr(
        edit,
        "resize_bore",
        lambda *args, **kwargs: Open(honest.shape),
    )

    with pytest.raises(GeometryError) as caught:
        run("resize_hole", source, profile, at_feature=bore.id, diameter=7.0)

    assert caught.value.title == prepare_ops.OPEN_BODY_TITLE
    assert caught.value.suggestions, "Regel 17: ein Fehler trägt einen Handlungsvorschlag"


def test_the_exact_primitives_take_the_same_placement_as_their_twins(profile: Profile) -> None:
    """Ein Umschalten zwischen den Kernen lässt den Körper, wo er ist (§15.4).

    Seit die Grundkörper eine freie Position und Richtung tragen, müssen beide
    Zwillinge sie kennen — sonst stünde der exakte Quader nach dem Haken
    „Flächen und Kanten später bearbeiten" wieder im Ursprung, und der
    Umschalter verschwiege sechs Felder (``test_a_twin_toggle_says_what_it_takes_away``).
    Gemessen an den Hüllquadern: Der Quader ist in beiden Kernen exakt, der
    Zylinder des Netzes ein 128-Eck, das der Anzeigetoleranz genügt.
    """
    placement = {"x": 12.0, "y": -7.0, "z": 30.0, "nx": 1.0, "ny": 0.0, "nz": 1.0}
    size = {"width": 40.0, "depth": 30.0, "height": 20.0}

    twin = run("create_box", None, profile, anchor="centre", **size, **placement).outputs[0]
    exact = run("create_brep_box", None, profile, **size, **placement).outputs[0]
    assert exact.kind == "brep"
    assert exact.mesh.bounds.minimum == pytest.approx(twin.mesh.bounds.minimum, abs=EPS_DISPLAY)
    assert exact.mesh.bounds.maximum == pytest.approx(twin.mesh.bounds.maximum, abs=EPS_DISPLAY)

    round_twin = run(
        "create_cylinder", None, profile, diameter=20.0, height=15.0, segments=128, **placement
    ).outputs[0]
    round_exact = run(
        "create_brep_cylinder", None, profile, diameter=20.0, height=15.0, **placement
    ).outputs[0]
    assert round_exact.mesh.bounds.centre == pytest.approx(
        round_twin.mesh.bounds.centre, abs=EPS_DISPLAY
    )
    assert round_exact.mesh.volume == pytest.approx(math.pi * 100.0 * 15.0, rel=1e-9)

    # Und ohne Angaben steht alles, wo es stand: kein Versatz, keine Drehung.
    plain = run("create_brep_box", None, profile, **size).outputs[0]
    assert plain.mesh.bounds.minimum == pytest.approx((-20.0, -15.0, 0.0), abs=EPS_GEOM)
