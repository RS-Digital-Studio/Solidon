"""STEP als Baugruppe (P7.4): Instanzen, Namen, Farben, Lagen — und alles danach.

Die Sollwerte stehen in ``tests/data/make_step_assembly_corpus.py``: Maße,
Lagen und Farben, aus denen die Korpusdateien gebaut sind. Die Tests prüfen,
was ``brep.step.read_assembly`` und ``load_step`` daraus machen — die Zahl der
Körper, ihre Weltlage, Maße, Namen und Farben, dass jeder Körper danach für
sich bearbeitet wird, und dass ein gespeichertes Projekt dasselbe wieder
ergibt.
"""

from __future__ import annotations

import json
import math
import zipfile
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app.core.brep import step
from app.core.brep.kernel import Solid, available
from app.core.errors import OperationCancelled, ValidationError
from app.core.ingest import plan as ingest_plan
from app.core.registry.params import WHOLE_FILE, body_keys
from app.core.scene import FORMAT_VERSION, History, OperationDraft, evaluate
from app.core.scene.cancel import CancelSignal
from app.core.scene.project import MAX_PROJECT_OBJECTS, ProjectSources, load, new_project, save
from app.core.types import Profile, SceneObject, Source
from tests.data import make_step_assembly_corpus as corpus

pytestmark = pytest.mark.skipif(not available(), reason="ohne OpenCASCADE gibt es kein STEP")

STEPS = Path(__file__).parent / "data" / "step"
PROJECTS = Path(__file__).parent / "data" / "projects"

#: Wie genau Weltgrenzen stimmen müssen: ``AddOptimal`` ohne Toleranzzuschlag
#: auf analytischen Flächen — die Grenze ist die Rechengenauigkeit, nicht ein
#: Messfehler.
BOUNDS = 1e-6


def payload(name: str) -> bytes:
    return (STEPS / f"{name}.step").read_bytes()


def bounds_of(body: Any) -> tuple[float, ...]:
    shape = body.shape if isinstance(body, step.StepBody | Solid) else body
    return step.shape_bounds(shape)


def assert_bounds(actual: tuple[float, ...], expected: tuple[float, ...]) -> None:
    assert actual == pytest.approx(expected, abs=BOUNDS), (actual, expected)


def bolt_bounds(
    shift: tuple[float, float, float], turned: bool
) -> tuple[float, float, float, float, float, float]:
    """Wo ein Bolzen nach seiner Instanzlage liegt — aus den Maßen des Erzeugers."""
    radius, height = corpus.BOLT
    x, y, z = shift
    if not turned:
        return (x - radius, y - radius, z, x + radius, y + radius, z + height)
    # 90° um X: +Z zeigt danach nach minus Y.
    return (x - radius, y - height, z - radius, x + radius, y, z + radius)


def face_colours_by_height(body: step.StepBody) -> dict[str | None, list[float]]:
    """Welche Farbe die Flächen in welcher Höhe tragen (Mittelpunkt der Fläche)."""
    from OCP.BRepGProp import BRepGProp
    from OCP.collections import IndexedMap_TopoDS_Shape_TopTools_ShapeMapHasher as ShapeMap
    from OCP.GProp import GProp_GProps
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp

    faces = ShapeMap()
    TopExp.MapShapes_s(body.shape, TopAbs_FACE, faces)
    found: dict[str | None, list[float]] = {}
    for index in range(1, faces.Extent() + 1):
        properties = GProp_GProps()
        BRepGProp.SurfaceProperties_s(faces.FindKey(index), properties)
        found.setdefault(body.face_colours[index - 1], []).append(properties.CentreOfMass().Z())
    return found


# --- der Korpus -------------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(corpus.BUILDERS))
def test_the_corpus_matches_its_generator(name: str) -> None:
    """Die abgelegten Dateien sagen, was der Erzeuger sagt — Baum, Namen, Lagen, Farben."""
    same, text = corpus.compare(name)
    assert same, text


@pytest.mark.parametrize("fresh", [False, True])
def test_the_corpus_summary_compares_zero_without_a_sign(fresh: bool) -> None:
    """Spiegelung und Versatz zählen, das plattformabhängige Vorzeichen der Null nicht."""
    data = corpus.build("nested") if fresh else payload("nested")
    reflected = next(line for line in corpus.summary(data) if "instance Halter gespiegelt " in line)

    cells = reflected.split("[", 1)[1].split("]", 1)[0].split()
    assert cells == [
        "-1.000000",
        "0.000000",
        "0.000000",
        f"{corpus.MIRRORED_SHIFT:.6f}",
        "0.000000",
        "1.000000",
        "0.000000",
        "0.000000",
        "0.000000",
        "0.000000",
        "1.000000",
        "0.000000",
    ]


# --- Lesen: Körper, Lagen, Namen, Farben ------------------------------------------


def test_three_instances_of_one_bolt_become_three_bodies_where_the_file_puts_them() -> None:
    assembly = step.read_assembly(payload("instances"), "instances")

    names = [body.name for body in assembly.bodies]
    assert names == ["Grundplatte", *(name for name, *_rest in corpus.BOLT_INSTANCES)]
    plate, *bolts = assembly.bodies
    assert_bounds(bounds_of(plate), (0.0, 0.0, 0.0, *corpus.PLATE))
    for body, (_name, shift, axis, _degrees) in zip(bolts, corpus.BOLT_INSTANCES, strict=True):
        assert_bounds(bounds_of(body), bolt_bounds(shift, axis is not None))
        radius, height = corpus.BOLT
        assert Solid(body.shape).volume == pytest.approx(math.pi * radius * radius * height)
    assert len({body.geometry for body in bolts}) == 1, "dasselbe Teil, dreimal eingesetzt"
    assert len({body.key for body in assembly.bodies}) == 4


def test_the_instance_colour_wins_over_the_part_and_the_face_colour_over_the_body() -> None:
    """Instanz vor Referenz; im Teil die Fläche vor dem Teil (Vorrang, ``read_assembly``)."""
    plate, left, lying, right = step.read_assembly(payload("instances")).bodies

    assert left.colours == lying.colours == (corpus.BLUE,)
    assert right.colours == (corpus.RED,), "Rot am Vorkommen schlägt das blaue Teil"
    heights = face_colours_by_height(plate)
    assert set(heights) == {corpus.GREY, corpus.YELLOW}
    assert heights[corpus.YELLOW] == pytest.approx([corpus.PLATE[2]]), "nur die Oberseite"
    assert len(heights[corpus.GREY]) == 5


def test_the_colours_are_read_in_the_srgb_of_the_file() -> None:
    """OCCT hält Farben linear; zurück kommt, was in der Datei steht."""
    text = payload("instances").decode("ascii")
    assert "0.843137" in text, "Gelb #ffd700 steht als 215/255 in der Datei"

    plate = step.read_assembly(payload("instances")).bodies[0]

    assert corpus.YELLOW in plate.colours


def test_a_colour_for_one_nested_occurrence_colours_only_that_one() -> None:
    """Die SHUO färbt die Welle der hinteren Achse; die vordere bleibt, wie das Teil ist."""
    bodies = {body.name: body for body in step.read_assembly(payload("nested")).bodies}

    assert bodies["Welle (Achse vorn)"].colours == (corpus.BLUE,)
    assert bodies["Welle (Achse hinten)"].colours == (corpus.RED,)
    assert bodies["Halter (Achse hinten)"].colours == (corpus.GREEN,)


def test_equal_names_are_told_apart_by_the_occurrence_above() -> None:
    assembly = step.read_assembly(payload("nested"))

    assert [body.name for body in assembly.bodies] == [
        "Welle (Achse vorn)",
        "Halter (Achse vorn)",
        "Welle (Achse hinten)",
        "Halter (Achse hinten)",
        "Halter gespiegelt",
    ]
    assert [body.key for body in assembly.bodies] == ["1.1.1", "1.1.2", "1.2.1", "1.2.2", "1.3"]
    back = assembly.bodies[2]
    radius, height = corpus.BOLT
    assert_bounds(
        bounds_of(back),
        (-radius, corpus.AXLE_OFFSET - radius, 0.0, radius, corpus.AXLE_OFFSET + radius, height),
    )


def test_a_mirrored_instance_is_the_mirror_image_and_a_valid_body() -> None:
    """Gespiegelt heißt: dieselbe Form, seitenverkehrt — nicht umgestülpt."""
    mirrored = step.read_assembly(payload("nested")).bodies[-1]
    solid = Solid(mirrored.shape)

    assert mirrored.mirrored
    width = max(x for x, _z in corpus.BRACKET_OUTLINE)
    height = max(z for _x, z in corpus.BRACKET_OUTLINE)
    shift = corpus.MIRRORED_SHIFT
    assert_bounds(
        bounds_of(mirrored), (shift - width, 0.0, 0.0, shift, corpus.BRACKET_DEPTH, height)
    )
    assert solid.volume == pytest.approx(corpus.BRACKET_VOLUME), "positiv, nicht umgestülpt"
    assert solid.is_closed
    mesh = solid.mesh.raw
    assert mesh.is_winding_consistent and mesh.volume > 0.0
    # Der senkrechte Schenkel stand bei x = 0 … 4, gespiegelt bei x = -4 … 0 und
    # verschoben um -30: Material bei x = -32, keines bei x = -48 in derselben Höhe.
    assert inside_of(solid, (shift - 2.0, corpus.BRACKET_DEPTH / 2.0, 15.0))
    assert not inside_of(solid, (shift - 18.0, corpus.BRACKET_DEPTH / 2.0, 15.0))


def inside_of(solid: Solid, point: tuple[float, float, float]) -> bool:
    """Ob ein Punkt im exakten Körper liegt — gefragt an der Form, nicht am Netz."""
    from OCP.BRepClass3d import BRepClass3d_SolidClassifier
    from OCP.gp import gp_Pnt
    from OCP.TopAbs import TopAbs_IN

    classifier = BRepClass3d_SolidClassifier(solid.shape, gp_Pnt(*point), 1e-7)
    return bool(classifier.State() == TopAbs_IN)


def test_the_bodies_of_one_part_carry_their_own_names() -> None:
    """Ein Teil mit mehreren Körpern: der Körpername geht vor, ohne ihn das Teil mit Nummer."""
    assembly = step.read_assembly(payload("multibody"))

    assert [body.name for body in assembly.bodies] == ["Unterteil", "Deckel", "Gehäuse 3"]
    assert [body.colours for body in assembly.bodies] == [(corpus.RED,), (corpus.GREEN,), ()]
    for body, (_name, corner, size, _colour) in zip(assembly.bodies, corpus.HOUSING, strict=True):
        assert_bounds(bounds_of(body), (*corner, *(corner[axis] + size[axis] for axis in range(3))))
    assert [body.key for body in assembly.bodies] == ["1#1", "1#2", "1#3"]


def test_a_file_without_names_numbers_its_bodies_and_a_lone_body_takes_the_file_name() -> None:
    assembly = step.read_assembly(payload("unnamed"), "unnamed")

    assert [body.name for body in assembly.bodies] == ["Körper 1", "Körper 2", "Körper 3"]
    assert not any(body.named for body in assembly.bodies)
    assert all(not body.colours for body in assembly.bodies)
    document, shapes, _colours = corpus._document()
    shapes.AddShape(corpus.bolt(), False)
    lone = step.read_assembly(corpus.written(document), "wuerfel")
    assert [body.name for body in lone.bodies] == ["wuerfel"], "ein Körper ohne Namen"


def test_an_inch_file_comes_in_millimetres_and_says_its_unit() -> None:
    assembly = step.read_assembly(payload("inch"))

    assert assembly.unit == "INCH" and not assembly.millimetres
    (body,) = assembly.bodies
    assert_bounds(bounds_of(body), (0.0, 0.0, 0.0, *corpus.INCH_BLOCK))
    assert body.name == "Zollklotz"


def test_a_closed_shell_becomes_a_body_an_open_one_stays_open_and_edges_are_left_out() -> None:
    assembly = step.read_assembly(payload("surfaces"))

    closed, open_shell = assembly.bodies
    assert (closed.name, closed.solid) == ("Hülle", True)
    assert Solid(closed.shape).is_closed
    assert Solid(closed.shape).volume == pytest.approx(1000.0)
    assert (open_shell.name, open_shell.solid) == ("Wanne", False)
    assert not Solid(open_shell.shape).is_closed, "fünf Flächen sind keine geschlossene Hülle"
    assert assembly.skipped == 1, "die Skizze trägt keine Fläche"


def test_reading_twice_gives_the_same_keys_names_and_colours() -> None:
    first = step.read_assembly(payload("nested"))
    second = step.read_assembly(payload("nested"))

    def summary(assembly: step.StepAssembly) -> list[tuple[str, str, tuple[str | None, ...]]]:
        return [(body.key, body.name, body.face_colours) for body in assembly.bodies]

    assert summary(first) == summary(second)


def test_cancelling_stops_the_reading() -> None:
    signal = CancelSignal()
    signal.cancel()

    with pytest.raises(OperationCancelled):
        step.read_assembly(payload("instances"), cancelled=signal)


def test_too_many_bodies_is_a_refusal_with_a_way_and_not_a_hang(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(step, "MAX_BODIES", 3)

    with pytest.raises(ValidationError) as caught:
        step.read_assembly(payload("instances"))

    assert caught.value.constraint == "too_many_bodies"
    assert caught.value.suggestions


def test_the_body_limit_is_the_project_limit() -> None:
    from app.core.ingest import threemf

    assert step.MAX_BODIES == threemf.MAX_BODIES == MAX_PROJECT_OBJECTS
    assert step.MAX_DEPTH == threemf.MAX_DEPTH


@pytest.mark.parametrize(
    ("text", "usable"),
    [
        ("Bolzen links", True),
        ("Open CASCADE STEP translator 8.0 1.2", False),
        ("3", False),
        ("NAUO12", False),
        ("=>[0:1:1:2]", False),
        ("SOLID", False),
        ("Solid 4", False),
        ("", False),
        ("   ", False),
        (None, False),
        ("Body1", True),
        ("Deckel 2", True),
    ],
)
def test_names_nobody_gave_are_not_names(text: str | None, usable: bool) -> None:
    assert step.usable_name(text) is usable


def test_a_broken_step_file_is_a_refusal_with_a_way() -> None:
    with pytest.raises(ValidationError) as caught:
        step.read_assembly(b"ISO-10303-21;\nHEADER;\nENDSEC;\nDATA;\nENDSEC;\n")

    assert caught.value.suggestions


# --- Import: Plan, Auswahl, Szene ---------------------------------------------------


def imported(
    name: str,
    *,
    keys: list[str] | None = None,
    first_model: bool = False,
    stem: str | None = None,
) -> tuple[Any, History]:
    """Ein Projekt, in das eine Korpusdatei über den Einleseplan gekommen ist."""
    project = new_project("centauri-carbon-2", "petg")
    data = payload(name)
    file_name = f"{stem or name}.step"
    project.sources["src_1"] = data
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/{file_name}", sha256=""
    )
    chosen = ingest_plan.import_plan("src_1", file_name, data, first_model=first_model)
    if keys is not None:
        chosen = ingest_plan.with_selection(chosen, keys)
    history = History(project.document)
    history.apply(chosen.title, [chosen.draft])
    return project, history


def scene_of(project: Any, profile: Profile) -> dict[str, SceneObject]:
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete, [finding.values for finding in result.scene.report.findings]
    return dict(result.scene.objects)


def codes_of(project: Any, profile: Profile) -> set[str]:
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    return {finding.code for finding in result.scene.report.findings}


def findings_of(project: Any, profile: Profile, code: str) -> list[Any]:
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    return [finding for finding in result.scene.report.findings if finding.code == code]


def test_the_plan_lists_every_body_and_selects_them_all() -> None:
    chosen = ingest_plan.import_plan("src_1", "instances.step", payload("instances"))

    assert chosen.draft.op == "load_step"
    assert body_keys(chosen.draft.params["bodies"]) == ("1.1", "1.2", "1.3", "1.4")
    assert chosen.draft.produces == 4
    assert [entry.name for entry in chosen.choices][:2] == ["Grundplatte", "Bolzen links"]
    assert chosen.choices[0].size == pytest.approx(corpus.PLATE)
    assert chosen.choices[0].colours == (corpus.GREY, corpus.YELLOW)
    assert len({entry.part for entry in chosen.choices[1:]}) == 1
    assert not chosen.asks_unit


def test_a_file_with_one_body_offers_no_choice() -> None:
    chosen = ingest_plan.import_plan("src_1", "inch.step", payload("inch"))

    assert chosen.choices == ()
    assert body_keys(chosen.draft.params["bodies"]) == ("1",)


def test_an_assembly_becomes_independent_scene_bodies(profile: Profile) -> None:
    """Die Abnahme aus P7.4: Zahl, Weltlage, Maße, Namen, Farben — und jeder für sich."""
    project, history = imported("instances")
    objects = scene_of(project, profile)

    assert [str(entry.name) for entry in objects.values()] == [
        "Grundplatte",
        "Bolzen links",
        "Bolzen liegend",
        "Bolzen rechts",
    ]
    assert all(entry.kind == "brep" for entry in objects.values())
    plate, left, lying, right = objects.values()
    assert_bounds(bounds_of(plate.mesh.shape), (0.0, 0.0, 0.0, *corpus.PLATE))
    for entry, (_name, shift, axis, _degrees) in zip(
        (left, lying, right), corpus.BOLT_INSTANCES, strict=True
    ):
        assert_bounds(bounds_of(entry.mesh.shape), bolt_bounds(shift, axis is not None))
    assert any(feature.kind == "pin" for feature in lying.features.values()), (
        "die Merkmale gelten der gedrehten Lage"
    )

    # Jeder Körper wird für sich bearbeitet: Den linken Bolzen verschieben,
    # in die Platte bohren — die beiden anderen Bolzen bleiben, wo sie sind.
    history.apply(
        "Verschieben",
        [OperationDraft(op="translate_object", inputs=(left.id,), params={"dx": 3.0})],
    )
    history.apply(
        "Bohrung",
        [
            OperationDraft(
                op="drill_hole",
                inputs=(plate.id,),
                params={"diameter": 6.0, "x": 40.0, "y": 20.0, "z": 5.0, "compensate": False},
            )
        ],
    )
    after = scene_of(project, profile)
    assert_bounds(
        bounds_of(after[left.id].mesh.shape),
        bolt_bounds((corpus.BOLT_INSTANCES[0][1][0] + 3.0, 20.0, 5.0), False),
    )
    for entry in (lying, right):
        assert_bounds(bounds_of(after[entry.id].mesh.shape), bounds_of(entry.mesh.shape))
    width, depth, height = corpus.PLATE
    assert after[plate.id].mesh.volume == pytest.approx(
        width * depth * height - math.pi * 9.0 * height, rel=1e-9
    )


def test_colours_become_filament_slots_of_their_bodies(profile: Profile) -> None:
    project, _history = imported("instances")
    plate, left, _lying, right = scene_of(project, profile).values()

    assert [(slot.index, slot.colour) for slot in plate.material_slots] == [
        (0, pytest.approx(tuple(int(corpus.GREY[i : i + 2], 16) / 255 for i in (1, 3, 5)))),
        (1, pytest.approx(tuple(int(corpus.YELLOW[i : i + 2], 16) / 255 for i in (1, 3, 5)))),
    ]
    assert isinstance(plate.mesh, Solid)
    assert sorted(plate.mesh.face_slots) == [0, 0, 0, 0, 0, 1]
    top = [
        slot
        for slot, centre in zip(
            plate.mesh.mesh.slots, plate.mesh.mesh.raw.triangles_center, strict=True
        )
        if centre[2] > corpus.PLATE[2] - 1e-6
    ]
    assert top and set(top) == {1}, "die Dreiecke der Oberseite tragen das Gelb"
    assert [slot.colour for slot in left.material_slots] == [
        pytest.approx(tuple(int(corpus.BLUE[i : i + 2], 16) / 255 for i in (1, 3, 5)))
    ]
    assert [slot.colour for slot in right.material_slots] == [
        pytest.approx(tuple(int(corpus.RED[i : i + 2], 16) / 255 for i in (1, 3, 5)))
    ]


def test_a_file_that_knows_one_colour_brings_no_filament(profile: Profile, tmp_path: Path) -> None:
    """Die eine Farbe, in der ein CAD-Programm alles zeigt, hat niemand gewählt (3MF-Regel)."""
    grey = step.write_bodies(
        [
            step.StepExport(Solid(shape), name, (corpus.GREY,) * Solid(shape).face_count)
            for name, shape in (("A", corpus.plate()), ("B", corpus.bolt()))
        ]
    )
    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = grey
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/grau.step", sha256=""
    )
    chosen = ingest_plan.import_plan("src_1", "grau.step", grey)
    History(project.document).apply(chosen.title, [chosen.draft])

    objects = scene_of(project, profile)

    assert [str(entry.name) for entry in objects.values()] == ["A", "B"]
    assert all(not entry.material_slots for entry in objects.values())


def test_the_customer_takes_only_the_bodies_he_chose(profile: Profile) -> None:
    project, _history = imported("instances", keys=["1.2", "1.4"])
    objects = scene_of(project, profile)

    assert [str(entry.name) for entry in objects.values()] == ["Bolzen links", "Bolzen rechts"]
    assert "step.partial" in codes_of(project, profile)


def test_the_selection_can_grow_later_while_nothing_builds_on_it(profile: Profile) -> None:
    project, history = imported("instances", keys=["1.2"])
    step_id = project.document.ops[-1].id

    history.change_params(step_id, {"bodies": ingest_plan.selection(["1.2", "1.3", "1.4"])})

    assert len(project.document.ops[-1].outputs) == 3
    assert [str(entry.name) for entry in scene_of(project, profile).values()] == [
        "Bolzen links",
        "Bolzen liegend",
        "Bolzen rechts",
    ]


def test_a_selection_others_build_on_is_not_swapped_silently(profile: Profile) -> None:
    project, history = imported("instances", keys=["1.2", "1.3"])
    load_step = project.document.ops[-1]
    history.apply(
        "Verschieben",
        [OperationDraft(op="translate_object", inputs=(load_step.outputs[0],), params={"dx": 1.0})],
    )

    with pytest.raises(ValidationError) as swapped:
        history.change_params(load_step.id, {"bodies": ingest_plan.selection(["1.4", "1.3"])})
    with pytest.raises(ValidationError) as grown:
        history.change_params(load_step.id, {"bodies": ingest_plan.selection(["1.2"])})

    assert swapped.value.constraint == "members_in_use"
    assert grown.value.constraint == "count_in_use"
    assert project.document.ops[0].params["bodies"] == ingest_plan.selection(["1.2", "1.3"])


def test_an_empty_selection_is_no_selection() -> None:
    with pytest.raises(ValidationError) as caught:
        body_keys("[]")
    assert caught.value.constraint == "empty_selection"
    assert body_keys("") == ()
    assert body_keys('["1.2","1.3"]') == ("1.2", "1.3")


def test_a_body_the_file_no_longer_has_halts_with_a_way(profile: Profile) -> None:
    project, _history = imported("instances", keys=["1.2"])
    project.document.ops[0].params["bodies"] = ingest_plan.selection(["9.9"])

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.stopped_at == project.document.ops[0].id
    (halt,) = [f for f in result.scene.report.findings if f.severity == "error"]
    assert halt.code == "op.load_step.ValidationError"
    assert halt.values["constraint"] == "unknown_body"
    assert halt.suggestions


def test_the_first_model_goes_onto_the_bed_as_one_group(profile: Profile) -> None:
    project, _history = imported("nested", first_model=True)
    objects = scene_of(project, profile)

    boxes = [bounds_of(entry.mesh.shape) for entry in objects.values()]
    low = [min(box[axis] for box in boxes) for axis in range(3)]
    high = [max(box[axis + 3] for box in boxes) for axis in range(3)]
    assert low[2] == pytest.approx(0.0, abs=BOUNDS)
    assert (low[0] + high[0]) / 2.0 == pytest.approx(0.0, abs=BOUNDS)
    assert (low[1] + high[1]) / 2.0 == pytest.approx(0.0, abs=BOUNDS)
    front, back = boxes[0], boxes[2]
    assert back[1] - front[1] == pytest.approx(corpus.AXLE_OFFSET), "die Lage zueinander bleibt"
    assert "load.assembly_on_bed" in codes_of(project, profile)


def test_the_findings_say_what_came_and_what_did_not(profile: Profile) -> None:
    project, _history = imported("surfaces")
    assert {"load.assembly", "step.skipped", "ingest.not_watertight"} <= codes_of(project, profile)

    project, _history = imported("nested")
    assert "step.mirrored" in codes_of(project, profile)

    project, _history = imported("unnamed")
    assert "step.unnamed" in codes_of(project, profile)

    project, _history = imported("inch")
    units = findings_of(project, profile, "ingest.declared_unit")
    assert units and units[0].values["unit"] == "INCH"


def test_a_file_the_assembly_reader_cannot_resolve_comes_as_one_body_and_says_so(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Rückfall mit Metadatenverlust wird angezeigt, nicht verschwiegen (Konzept §13.9)."""

    def broken(*_args: object, **_kwargs: object) -> step.StepAssembly:
        raise RuntimeError("Standard_Failure")

    monkeypatch.setattr(step, "read_assembly", broken)
    project, _history = imported("multibody", stem="gehaeuse")

    assert body_keys(project.document.ops[0].params["bodies"]) == (WHOLE_FILE,)
    (entry,) = scene_of(project, profile).values()
    assert str(entry.name) == "gehaeuse"
    assert entry.mesh.volume == pytest.approx(
        sum(math.prod(size) for _n, _c, size, _col in corpus.HOUSING)
    )
    lost = findings_of(project, profile, "step.metadata_lost")
    assert lost and lost[0].severity == "warning"


def test_the_features_of_a_further_instance_are_those_of_a_fresh_search(
    profile: Profile,
) -> None:
    """Übertragen heißt: dieselben Merkmale wie eine eigene Suche, nur ohne sie."""
    from app.core.brep.features import features_of

    project, _history = imported("instances")
    objects = list(scene_of(project, profile).values())

    for entry in objects[2:]:
        assert isinstance(entry.mesh, Solid)
        fresh = features_of(Solid(entry.mesh.shape))
        assert sorted(entry.features) == sorted(fresh)
        for key, feature in entry.features.items():
            other = fresh[key]
            assert feature.kind == other.kind
            assert sorted(feature.face_indices) == sorted(other.face_indices)
            for name in ("centre", "diameter", "depth", "normal", "area"):
                if name in other.params:
                    assert feature.params[name] == pytest.approx(other.params[name], abs=1e-6)
            if "axis" in other.params:
                # Die Achse folgt der Lage wie beim Verschieben
                # (``transformed_features``); die frische Suche nennt dieselbe
                # Gerade womöglich andersherum.
                carried, found = feature.params["axis"], other.params["axis"]
                assert carried == pytest.approx(found, abs=1e-6) or carried == pytest.approx(
                    tuple(-value for value in found), abs=1e-6
                )


def test_a_mirrored_body_in_the_scene_is_a_valid_exact_body(profile: Profile) -> None:
    project, _history = imported("nested")
    mirrored = list(scene_of(project, profile).values())[-1]

    assert isinstance(mirrored.mesh, Solid)
    assert mirrored.mesh.volume == pytest.approx(corpus.BRACKET_VOLUME)
    assert mirrored.mesh.is_closed and mirrored.mesh.mesh.is_watertight
    assert mirrored.features


# --- Wiederöffnen und Formatstand ---------------------------------------------------


def test_reopening_gives_the_same_bodies_names_positions_and_colours(
    profile: Profile, tmp_path: Path
) -> None:
    """Die Quelle bleibt die STEP-Datei im Projekt; gespeichert werden Schritt und Auswahl."""
    project, _history = imported("nested")
    before = scene_of(project, profile)
    path = save(project, tmp_path / "gestell.p3d")

    with zipfile.ZipFile(path) as archive:
        stored = json.loads(archive.read("project.json"))
        assert archive.read("sources/nested.step") == payload("nested")
    (step_entry,) = stored["ops"]
    assert step_entry["params"]["bodies"] == ingest_plan.selection(
        ["1.1.1", "1.1.2", "1.2.1", "1.2.2", "1.3"]
    )
    assert not any(
        ":" in str(value) or "\\" in str(value) for value in step_entry["params"].values()
    ), "keine absoluten Pfade in der Projektdatei (Regel 12)"
    again = load(path)
    after = scene_of(again, profile)

    assert [str(entry.name) for entry in after.values()] == [
        str(entry.name) for entry in before.values()
    ]
    for first, second in zip(before.values(), after.values(), strict=True):
        assert_bounds(bounds_of(second.mesh.shape), bounds_of(first.mesh.shape))
        assert [slot.colour for slot in second.material_slots] == [
            slot.colour for slot in first.material_slots
        ]
        assert second.mesh.face_slots == first.mesh.face_slots


def test_a_step_import_saved_before_the_assembly_reader_keeps_its_one_body(
    profile: Profile,
) -> None:
    """Ein alter Schritt ohne ``bodies`` bleibt nach allen Migrationen ein Körper."""
    project = load(PROJECTS / "step_assembly_v32.p3d")

    assert project.document.format_version == FORMAT_VERSION
    assert "bodies" not in project.document.ops[0].params
    (entry,) = scene_of(project, profile).values()
    assert str(entry.name) == "gehaeuse"
    assert entry.mesh.volume == pytest.approx(
        sum(math.prod(size) for _n, _c, size, _col in corpus.HOUSING)
    )
    assert isinstance(entry.mesh, Solid) and entry.mesh.solid_count == 3


# --- Hinaus: STEP-Rundreise ---------------------------------------------------------


def test_a_step_export_keeps_names_colours_and_positions(profile: Profile) -> None:
    project, _history = imported("instances")
    objects = list(scene_of(project, profile).values())
    exports = []
    for entry in objects:
        assert isinstance(entry.mesh, Solid)
        by_slot = {slot.index: slot for slot in entry.material_slots}
        colours = tuple(
            step.hex_colour(*by_slot[slot].colour)
            if slot in by_slot and by_slot[slot].colour
            else None
            for slot in (entry.mesh.face_slots or (0,) * entry.mesh.face_count)
        )
        exports.append(step.StepExport(entry.mesh, str(entry.name), colours))

    again = step.read_assembly(step.write_bodies(exports, "Baugruppe"))

    assert [body.name for body in again.bodies] == [str(entry.name) for entry in objects]
    for body, entry in zip(again.bodies, objects, strict=True):
        assert_bounds(bounds_of(body), bounds_of(entry.mesh.shape))
        assert sorted(body.face_colours, key=str) == sorted(
            (
                step.hex_colour(*{s.index: s for s in entry.material_slots}[slot].colour)
                for slot in (entry.mesh.face_slots or (0,) * entry.mesh.face_count)
            ),
            key=str,
        )


def test_a_name_with_umlauts_goes_out_encoded_and_comes_back_whole() -> None:
    """ISO 10303-21 kodiert, was nicht ASCII ist; roh stand „GehÃ¤use“ in fremden Programmen."""
    data = step.write(Solid(corpus.plate()), "Gehäuse Größe")

    assert data.isascii()
    assert b"\\X2\\00E4\\X0\\" in data
    assert "Open CASCADE STEP translator" not in data.decode("ascii").split("DATA;")[1]
    (body,) = step.read_assembly(data).bodies
    assert body.name == "Gehäuse Größe"
    assert "Gehäuse Größe 1" not in data.decode("ascii"), "der Name ohne angehängte Nummer"


def test_the_scene_export_writes_the_filament_colours_into_the_step_file(
    profile: Profile, tmp_path: Path
) -> None:
    from app.core.export.writer import plan_export, write_plan

    project, _history = imported("instances", keys=["1.1"])
    (plate,) = scene_of(project, profile).values()

    written = write_plan(
        plan_export([plate], project_name="Teil", profile=profile, export_format="step"),
        tmp_path,
        "step",
    )

    (body,) = step.read_assembly(written[0].read_bytes()).bodies
    assert body.name == "Grundplatte"
    assert set(body.colours) == {corpus.GREY, corpus.YELLOW}


# --- Filament je Körper ------------------------------------------------------------


def test_assigning_a_filament_to_one_body_leaves_the_others(profile: Profile) -> None:
    project, history = imported("instances")
    plate, left, lying, right = scene_of(project, profile).values()

    history.apply(
        "Filament",
        [
            OperationDraft(
                op="assign_slot",
                inputs=(lying.id,),
                params={"slot": 2, "name": "PETG Weiß", "colour": "#ffffff"},
            )
        ],
    )
    after = scene_of(project, profile)

    assert {slot.index for slot in after[lying.id].material_slots} >= {2}
    assert set(after[lying.id].mesh.mesh.slots) == {2}
    for entry in (plate, left, right):
        assert [slot.colour for slot in after[entry.id].material_slots] == [
            slot.colour for slot in entry.material_slots
        ]


@pytest.fixture
def many_instances(tmp_path: Path) -> Iterator[bytes]:
    """Eine Baugruppe mit vielen Instanzen eines Teils, im Test gebaut statt abgelegt."""
    document, shapes, colours = corpus._document()
    root = shapes.NewShape()
    corpus._name(root, "Reihe")
    part = shapes.AddShape(corpus.bolt(), False)
    corpus._name(part, "Stift")
    corpus._paint(colours, part, corpus.BLUE)
    for number in range(40):
        component = shapes.AddComponent(
            root, part, corpus.placement((12.0 * (number % 8), 12.0 * (number // 8), 0.0))
        )
        corpus._name(component, f"Stift:{number + 1}")
    shapes.UpdateAssemblies()
    yield corpus.written(document)


def test_many_instances_share_one_search_and_each_gets_its_features(
    profile: Profile, many_instances: bytes, caplog: pytest.LogCaptureFixture
) -> None:
    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = many_instances
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/reihe.step", sha256=""
    )
    chosen = ingest_plan.import_plan("src_1", "reihe.step", many_instances)
    History(project.document).apply(chosen.title, [chosen.draft])

    with caplog.at_level("INFO", logger="app.core.ingest.step_ops"):
        objects = scene_of(project, profile)

    assert len(objects) == 40
    assert [str(entry.name) for entry in objects.values()][:2] == ["Stift:1", "Stift:2"]
    assert all(any(f.kind == "pin" for f in entry.features.values()) for entry in objects.values())
    assert "carried the features of 39 STEP instance(s)" in caplog.text
