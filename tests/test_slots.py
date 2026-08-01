"""Materialslots: sie durch Operationen tragen und nach 3MF hinausbringen
(§20, §29).

Das Abnahmekriterium von P9 ist kurz und hart: „die Slot-Zuweisung überlebt
Boolesche Operationen einschließlich der Voxelstufe". Beide Hälften werden
geprüft — die leichte, in der der Kern die Dreiecke durchreicht, und die, in
der das Netz vollständig ersetzt wurde und jedes Dreieck fragen muss, woher es
kam.
"""

from __future__ import annotations

import zipfile
from io import BytesIO
from xml.etree import ElementTree as ET

import pytest
import trimesh

from app.core.export import threemf
from app.core.export.writer import export_bytes, plan_export
from app.core.geom.attributes import counts, transfer, used_slots, with_slot
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData
from app.core.types import MaterialSlot, Profile, SceneObject

NAMESPACE = {"c": threemf.CORE_NAMESPACE}


def cube(size: float = 20.0, offset: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> MeshData:
    body = trimesh.creation.box(extents=(size, size, size))
    body.apply_translation(offset)
    return MeshData.of(body)


def pin(radius: float = 3.0, height: float = 40.0) -> MeshData:
    return MeshData.of(trimesh.creation.cylinder(radius=radius, height=height))


def area_share(mesh: MeshData, slot: int) -> float:
    """Welcher Anteil der Oberfläche in einem Slot sitzt — das ehrliche Maß.

    Dreieckszahlen lügen nach einem Voxellauf: die Treppe erzeugt viele kleine
    Flächen, wo das Original wenige große hatte.
    """
    areas = mesh.raw.area_faces
    chosen = [area for area, entry in zip(areas, mesh.slots, strict=True) if entry == slot]
    return float(sum(chosen) / areas.sum())


def test_with_slot_paints_every_triangle() -> None:
    painted = with_slot(cube(), 2)

    assert len(painted.slots) == painted.triangle_count
    assert counts(painted) == {2: painted.triangle_count}
    assert used_slots(painted) == (2,)


def test_a_body_without_slots_counts_as_one_material() -> None:
    assert counts(cube()) == {0: 12}
    assert used_slots(cube()) == (0,)


def test_slots_survive_a_direct_difference() -> None:
    result = boolean("difference", [with_slot(cube(), 1), pin()])

    assert result.solver.strategy == "direct"
    assert used_slots(result.mesh) == (0, 1), "the bore wall is new, the outside is not"
    outside = 6 * 400 - 2 * 9 * 3.14159
    assert area_share(result.mesh, 1) == pytest.approx(
        outside / (outside + 2 * 3.14159 * 3 * 20), abs=0.01
    ), "exactly the cube surface minus the two mouths of the bore"


def test_slots_survive_the_voxel_stage() -> None:
    """§20, der Fall, der die Arbeit kostet: die Vernetzung wurde weggeworfen."""
    result = boolean("difference", [with_slot(cube(), 1), pin()], stages=("voxel",))

    assert result.solver.strategy == "voxel"
    assert used_slots(result.mesh) == (0, 1)
    assert area_share(result.mesh, 1) == pytest.approx(0.82, abs=0.08), (
        "the outside of the cube keeps its colour, the bore does not get it"
    )


def test_the_cutter_does_not_paint_the_body_it_cuts() -> None:
    """Ein Loch durch ein rotes Teil hat graue Wände, nicht die Farbe des
    Bohrers.
    """
    result = boolean("difference", [with_slot(cube(), 1), with_slot(pin(), 7)])

    assert 7 not in used_slots(result.mesh)


def test_a_named_cut_slot_lands_on_the_new_faces() -> None:
    result = boolean("difference", [with_slot(cube(), 1), pin()], cut_slot=3)

    assert used_slots(result.mesh) == (1, 3)


def test_without_slots_nothing_is_invented() -> None:
    result = boolean("difference", [cube(), pin()])

    assert not result.mesh.slots, "one material in, one material out"


def test_transfer_keeps_a_union_of_two_colours_apart() -> None:
    left = with_slot(cube(), 1)
    right = with_slot(cube(offset=(20.0, 0.0, 0.0)), 2)

    result = boolean("union", [left, right])

    assert used_slots(result.mesh) == (1, 2)
    assert area_share(result.mesh, 1) == pytest.approx(0.5, abs=0.05)


def test_the_assignment_is_reproducible() -> None:
    """Gleiche Eingabe, gleiche Zuweisung — nichts hier darf zufällig
    sein (§11.3).
    """
    first = boolean("difference", [with_slot(cube(), 1), pin()], stages=("voxel",))
    second = boolean("difference", [with_slot(cube(), 1), pin()], stages=("voxel",))

    assert first.mesh.slots == second.mesh.slots


def test_transfer_takes_the_surfaces_it_is_given() -> None:
    """Die Regel aus §20 lebt in ``transfer``; wer als Quelle zählt, wird
    außerhalb entschieden.
    """
    result = boolean("difference", [with_slot(cube(), 1), with_slot(pin(), 7)])
    including_the_tool = transfer(result.mesh, [with_slot(cube(), 1), with_slot(pin(), 7)])

    assert used_slots(including_the_tool) == (1, 7), "asked for the tool, gets the tool"
    assert used_slots(result.mesh) == (0, 1), "the operation does not ask for it"


def model_of(data: bytes) -> ET.Element:
    with zipfile.ZipFile(BytesIO(data)) as container:
        return ET.fromstring(container.read(threemf.MODEL_PATH))


def test_3mf_is_a_readable_container() -> None:
    data = threemf.write(cube())

    with zipfile.ZipFile(BytesIO(data)) as container:
        assert container.testzip() is None
        assert set(container.namelist()) == {
            "[Content_Types].xml",
            "_rels/.rels",
            threemf.MODEL_PATH,
        }


def test_3mf_carries_one_colour_group_per_slot() -> None:
    body = boolean("union", [with_slot(cube(), 1), with_slot(cube(offset=(20, 0, 0)), 2)]).mesh
    slots = [
        MaterialSlot(index=1, name="Rot", colour=(1.0, 0.0, 0.0)),
        MaterialSlot(index=2, name="Schwarz", colour=(0.0, 0.0, 0.0)),
    ]

    model = model_of(threemf.write(body, slots, "Zweifarbig"))

    materials = model.findall(".//c:basematerials/c:base", NAMESPACE)
    assert [entry.get("name") for entry in materials] == ["Rot", "Schwarz"]
    assert [entry.get("displaycolor") for entry in materials] == ["#FF0000", "#000000"]

    triangles = model.findall(".//c:triangle", NAMESPACE)
    assert len(triangles) == body.triangle_count
    assert {entry.get("p1") for entry in triangles} == {"0", "1"}, "both groups are used"


def test_3mf_only_declares_the_slots_the_body_uses() -> None:
    """Ein Objekt darf fünf Filamente kennen; die Datei nennt nur die, die auf
    ihm sind.
    """
    slots = [MaterialSlot(index=index, name=f"Farbe {index}") for index in range(5)]

    model = model_of(threemf.write(with_slot(cube(), 3), slots))

    materials = model.findall(".//c:basematerials/c:base", NAMESPACE)
    assert [entry.get("name") for entry in materials] == ["Farbe 3"]
    assert {entry.get("p1") for entry in model.findall(".//c:triangle", NAMESPACE)} == {"0"}


def test_3mf_gives_a_slot_without_a_colour_a_neutral_grey() -> None:
    model = model_of(threemf.write(with_slot(cube(), 1), [MaterialSlot(index=1, name="Sonder")]))

    base = model.find(".//c:basematerials/c:base", NAMESPACE)
    assert base is not None and base.get("displaycolor") == "#B8B8B8"


def test_3mf_keeps_the_geometry_and_the_unit() -> None:
    model = model_of(threemf.write(cube(), name="Würfel"))

    assert model.get("unit") == "millimeter", "millimetres are the unit of §11.1"
    assert len(model.findall(".//c:vertex", NAMESPACE)) == 8
    assert len(model.findall(".//c:triangle", NAMESPACE)) == 12
    assert model.find(".//c:build/c:item", NAMESPACE) is not None


def test_3mf_written_here_can_be_read_here_again() -> None:
    """§20, Import: eine aus Formwerk exportierte Datei darf ihre Farben nicht
    verlieren.
    """
    body = boolean("union", [with_slot(cube(), 1), with_slot(cube(offset=(20, 0, 0)), 2)]).mesh
    slots = [
        MaterialSlot(index=1, name="Rot", colour=(1.0, 0.0, 0.0)),
        MaterialSlot(index=2, name="Schwarz", colour=(0.0, 0.0, 0.0)),
    ]

    groups = threemf.read(threemf.write(body, slots), body.triangle_count)

    assert groups is not None
    assert [entry.name for entry in groups.materials] == ["Rot", "Schwarz"]
    assert groups.materials[0].colour == pytest.approx((1.0, 0.0, 0.0))
    assert len(groups.slots) == body.triangle_count
    assert set(groups.slots) == {0, 1}, "3MF numbers groups by position, not by our slot number"


def test_reading_a_3mf_without_groups_says_so() -> None:
    assert threemf.read(threemf.write(cube()), 12) is None, "one material is not a group"
    assert threemf.read(threemf.write(with_slot(cube(), 4)), 12) is None
    assert threemf.read(b"not a container", 12) is None


def test_a_3mf_with_a_different_triangle_count_is_not_guessed_at() -> None:
    """Mehrere Körper werden auf dem Weg hinein aneinandergehängt — dann ist
    die Reihenfolge unbekannt.
    """
    assert threemf.read(threemf.write(with_slot(cube(), 1)), 999) is None


def test_loading_a_3mf_brings_its_colours_into_the_scene(profile: Profile) -> None:
    """Die ganze Importseite von §20: Datei auf der Platte, farbiges Objekt in
    der Szene.
    """
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source
    from app.i18n import _

    body = boolean("union", [with_slot(cube(), 1), with_slot(cube(offset=(20, 0, 0)), 2)]).mesh
    payload = threemf.write(
        body,
        [
            MaterialSlot(index=1, name="Rot", colour=(1.0, 0.0, 0.0)),
            MaterialSlot(index=2, name="Schwarz", colour=(0.0, 0.0, 0.0)),
        ],
        "Zweifarbig",
    )

    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = payload
    document = project.document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/zweifarbig.3mf", sha256=""
    )
    History(document).apply(
        _("Laden"),
        [OperationDraft(op="load", params={"source": "src_1", "unit": "mm", "weld": False})],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    entry = result.scene.objects["obj_1"]
    assert [slot.name for slot in entry.material_slots] == ["Rot", "Schwarz"]
    assert set(entry.mesh.slots) == {0, 1}


def test_export_writes_3mf_with_the_slots_of_the_object(profile: Profile) -> None:
    """The whole way through: scene object, plan, bytes."""
    entry = SceneObject(
        id="obj-1",
        name="Zweifarbig",
        mesh=with_slot(cube(), 1),
        material_slots=[MaterialSlot(index=1, name="Rot", colour=(1.0, 0.0, 0.0))],
    )

    plan = plan_export([entry], project_name="Test", profile=profile, export_format="3mf")
    data = export_bytes(plan.entries[0].mesh, "3mf", list(plan.entries[0].slots))

    assert plan.entries[0].filename == "Test_Zweifarbig.3mf"
    base = model_of(data).find(".//c:basematerials/c:base", NAMESPACE)
    assert base is not None and base.get("displaycolor") == "#FF0000"
