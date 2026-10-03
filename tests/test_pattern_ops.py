"""Muster am Körper und die Direktbearbeitung (Konzept P15 §7 Etappe 6).

Ein Lochbild, ein Kranz Schraubdome, eine Reihe Clips: bis hierher hieß das
neun Mal duplizieren und neun Mal verschieben, jeder Schritt eine Zeile im
Verlauf. Ein Muster ist **eine** Operation mit einer Zahl darin.

Und die Prüfung, die dazugehört (E1): vierzig Kopien, die über den Bauraum
hinausreichen, sind kein Muster, sondern ein Missverständnis — das sagt die
Operation, bevor sie rechnet.
"""

from __future__ import annotations

import itertools
import math

import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import (
    OpContext,
    OpResult,
    PrinterProfile,
    Profile,
    Scene,
    SceneObject,
)

PRINTER = PrinterProfile(id="test", title="Test", build_volume=(220.0, 220.0, 250.0))


def run(op: str, entry: SceneObject, **params: object) -> OpResult:
    load_operations()
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}, parameters={}),
            inputs=[entry],
            params=spec.params(**params),
            profile=Profile(printer=PRINTER, material=None),
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def cube(size: float = 10.0) -> SceneObject:
    return SceneObject(
        id="obj_1", name="Würfel", mesh=MeshData.of(trimesh.creation.box(extents=(size,) * 3))
    )


def centres(result: OpResult) -> list[tuple[float, float, float]]:
    return [tuple(round(value, 6) for value in out.mesh.bounds.centre) for out in result.outputs]


def test_a_linear_pattern_spaces_its_copies_evenly() -> None:
    """Vier Kopien im Abstand fünfzehn — der erste bleibt, wo er war."""
    result = run("pattern", cube(), kind="linear", count=4, spacing=15.0, dx=1.0, dy=0.0, dz=0.0)

    assert len(result.outputs) == 4
    xs = sorted(centre[0] for centre in centres(result))
    assert xs == pytest.approx([0.0, 15.0, 30.0, 45.0])
    assert all(centre[1] == pytest.approx(0.0) for centre in centres(result))


def test_a_circular_pattern_puts_its_copies_on_the_circle() -> None:
    """Sechs Kopien um die Z-Achse: alle auf demselben Radius, gleich verteilt.

    Das ist der Schraubdom-Kranz im Deckel — und von Hand sechs Mal Winkel
    ausrechnen.
    """
    start = cube()
    start.mesh = MeshData.of(
        trimesh.creation.box(extents=(4.0, 4.0, 4.0)).apply_translation((25.0, 0.0, 0.0))
    )

    result = run(
        "pattern", start, kind="circular", count=6, angle=360.0, axis="z", cx=0.0, cy=0.0, cz=0.0
    )

    assert len(result.outputs) == 6
    for x, y, _z in centres(result):
        assert math.hypot(x, y) == pytest.approx(25.0, abs=1e-6)
    angles = sorted(math.degrees(math.atan2(y, x)) % 360.0 for x, y, _z in centres(result))
    steps = [round(second - first, 4) for first, second in itertools.pairwise(angles)]
    assert all(step == pytest.approx(60.0, abs=1e-3) for step in steps)


def test_a_pattern_that_leaves_the_build_volume_is_refused() -> None:
    """E1: dreißig Kopien im Abstand zwanzig sind sechshundert Millimeter.

    Der Bauraum ist zweihundertzwanzig. Das zu sagen, bevor gerechnet wird,
    ist billiger als dreißig Körper, die niemand drucken kann — und ehrlicher
    als sie anzulegen und beim Anordnen zu meckern.
    """
    with pytest.raises(ValidationError) as problem:
        run("pattern", cube(), kind="linear", count=30, spacing=20.0, dx=1.0, dy=0.0, dz=0.0)

    assert problem.value.field == "count"
    assert problem.value.suggestions, "Regel 17: ein Fehler nennt, was jetzt möglich ist"


def test_a_pattern_of_one_is_refused() -> None:
    """Ein Muster aus einem Element ist kein Muster."""
    with pytest.raises(ValidationError):
        run("pattern", cube(), kind="linear", count=1, spacing=15.0, dx=1.0, dy=0.0, dz=0.0)


def test_a_linear_pattern_without_a_direction_is_refused() -> None:
    """Ohne Richtung lägen alle Kopien übereinander — das ist kein Abstand,
    das ist ein Stapel."""
    with pytest.raises(ValidationError) as problem:
        run("pattern", cube(), kind="linear", count=3, spacing=15.0, dx=0.0, dy=0.0, dz=0.0)

    assert problem.value.field == "dx"


@pytest.mark.parametrize("operation", ["pattern", "mirror_object"])
def test_pattern_and_mirror_store_the_initial_body_centre(operation: str) -> None:
    """Eine verschobene Quelle behält ihre Mitte als gespeicherten Bewegungsanker."""
    source = cube()
    source.mesh.raw.apply_translation((40.0, 12.0, 5.0))
    parameters = {"kind": "circular", "count": 4} if operation == "pattern" else {}
    result = run(operation, source, **parameters)
    assert result.answered == {"cx": 40.0, "cy": 12.0, "cz": 5.0}
    assert all(centre == pytest.approx((40.0, 12.0, 5.0)) for centre in centres(result))


@pytest.mark.parametrize("operation", ["pattern", "mirror_object"])
def test_pattern_and_mirror_accept_a_fixed_world_point(operation: str) -> None:
    """180 Grad oder Spiegeln an X=10 führt X=40 nach X=-20."""
    source = cube()
    source.mesh.raw.apply_translation((40.0, 0.0, 5.0))
    parameters = {"kind": "circular", "count": 2, "angle": 180.0} if operation == "pattern" else {}
    result = run(operation, source, cx=10.0, cy=0.0, cz=5.0, **parameters)
    assert centres(result)[-1] == pytest.approx((-20.0, 0.0, 5.0))
    assert result.answered == {}


@pytest.mark.parametrize("operation", ["pattern", "mirror_object"])
def test_pattern_and_mirror_refuse_an_incomplete_fixed_point(operation: str) -> None:
    """Ein halber Punkt wird nicht mit stillen Nullwerten vervollständigt."""
    parameters = {"kind": "circular", "count": 2} if operation == "pattern" else {}
    with pytest.raises(ValidationError) as problem:
        run(operation, cube(), cx=10.0, **parameters)
    assert problem.value.suggestions


# --- Aufdicken (D15) -------------------------------------------------------------


def open_shell() -> SceneObject:
    """Eine Schale ohne Boden — genau das, was aus dem Netz kommt, wenn jemand
    eine Fläche gescannt oder ein STL falsch exportiert hat."""
    box = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    keep = [index for index, normal in enumerate(box.face_normals) if normal[2] > -0.9]
    shell = trimesh.Trimesh(vertices=box.vertices, faces=box.faces[keep], process=True)
    return SceneObject(id="obj_1", name="Schale", mesh=MeshData.of(shell))


def test_thicken_turns_an_open_surface_into_a_body() -> None:
    """Sechs von 68 echten Modellen sind nicht geschlossen — das ist bei
    Community-Modellen normal, und bis hierher war es eine Sackgasse.

    Der Prüfbericht meldete es korrekt, und danach konnte man nichts tun: eine
    Boolesche Operation braucht ein Volumen, und eine Fläche hat keines.
    ``thicken`` gibt ihr eine Wand.
    """
    shell = open_shell()
    assert not shell.mesh.raw.is_watertight, "die Schale ist offen"

    result = run("thicken", shell, thickness=2.0)

    body = result.outputs[0].mesh
    assert body.raw.is_watertight, "danach ist sie ein Körper"
    assert body.volume > 0.0
    # Fünf Seiten zu 20 mal 20 bei 2 mm Wand sind grob 2000 mm³; die Ecken
    # überlappen, also liegt das Ergebnis darunter statt darüber.
    assert 1000.0 < body.volume < 2600.0


def test_thicken_leaves_a_closed_body_alone() -> None:
    """Ein Körper, der schon einer ist, braucht keine Wand — und bekommt eine
    Meldung statt einer stillen Verdopplung seiner Haut."""
    with pytest.raises(ValidationError) as problem:
        run("thicken", cube(), thickness=2.0)

    assert problem.value.field == "thickness"


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("quality", ["draft", "fine"])
@pytest.mark.parametrize("operation", ["pattern", "mirror_object", "pattern_feature"])
def test_fixed_centre_survives_cache_source_change_undo_and_project_round_trip(
    kernel, quality, operation, profile, tmp_path
) -> None:
    """Die gespeicherte Mitte bleibt bei Quelländerung, Cache, Undo und Dateirundreise fest."""
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.cache import ResultCache
    from app.core.scene.project import load, new_project, save

    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    cache = ResultCache()
    create = "create_brep_box" if kernel == "brep" else "create_box"
    history.apply(
        "Platte", [OperationDraft(op=create, params={"width": 60.0, "depth": 40.0, "height": 10.0})]
    )
    body = project.document.ops[-1].outputs[0]
    history.apply(
        "Verschieben",
        [OperationDraft(op="translate_object", inputs=(body,), params={"dx": 50.0, "dy": 20.0})],
    )
    move = project.document.ops[-1].id

    def measured():
        result = evaluate(project.document, profile, quality=quality, cache=cache)
        assert result.complete, result.scene.report.findings
        History(project.document).record_answers(result.answers)
        return result

    if operation == "pattern_feature":
        history.apply(
            "Bohren",
            [
                OperationDraft(
                    op="drill_hole",
                    inputs=(body,),
                    params={
                        "x": 65.0,
                        "y": 20.0,
                        "z": 10.0,
                        "diameter": 6.0,
                        "depth": 0.0,
                        "compensate": False,
                    },
                )
            ],
        )
        drilled = measured().scene.objects[body]
        hole = next(feature.id for feature in drilled.features.values() if feature.kind == "hole")
        parameters = {"kind": "circular", "count": 2, "angle": 180.0, "at_features": [hole]}
    else:
        parameters = (
            {"kind": "circular", "count": 2, "angle": 180.0} if operation == "pattern" else {}
        )
    history.apply(
        "Drehen oder spiegeln", [OperationDraft(op=operation, inputs=(body,), params=parameters)]
    )
    step = project.document.ops[-1].id

    def signature():
        scene = measured().scene
        return sorted(
            (
                entry.id,
                tuple(round(v, 6) for v in entry.mesh.bounds.centre),
                round(entry.mesh.volume, 5),
            )
            for entry in scene.objects.values()
        )

    initial = signature()
    assert signature() == initial
    assert {key: project.document.ops[-1].params[key] for key in ("cx", "cy", "cz")} == {
        "cx": 50.0,
        "cy": 20.0,
        "cz": 5.0,
    }
    history.change_params(move, {"dx": 55.0})
    changed = signature()
    assert changed != initial
    if operation != "pattern_feature":
        assert any(entry[1][0] == pytest.approx(45.0) for entry in changed)
    else:
        # Die vor dem Muster gesetzte Bohrung bleibt bei X=65, ihre Kopie bei X=35.
        holes = [
            feature
            for entry in measured().scene.objects.values()
            for feature in entry.features.values()
            if feature.kind == "hole"
        ]
        assert sorted(round(feature.params["centre"][0], 5) for feature in holes) == [35.0, 65.0]
    history.undo()
    assert signature() == initial
    history.redo()
    assert signature() == changed
    path = tmp_path / f"{operation}-{kernel}-{quality}.p3d"
    save(project, path)
    project = load(path)
    cache = ResultCache()
    assert signature() == changed
    assert next(op for op in project.document.ops if op.id == step).params["cx"] == pytest.approx(
        50.0
    )
    History(project.document).undo()
    assert signature() == initial


@pytest.mark.parametrize(
    "about, expected", [("origin", (-40.0, 12.0, 5.0)), ("bed", (40.0, 12.0, 5.0))]
)
def test_explicit_legacy_mirror_anchor_is_honoured(about, expected) -> None:
    """Direkte API-Aufrufe behalten Ursprung und Druckbett als gültige Anker."""
    source = cube()
    source.mesh.raw.apply_translation((40.0, 12.0, 5.0))
    result = run("mirror_object", source, about=about)
    assert centres(result)[0] == pytest.approx(expected)
    assert result.answered
    following = run("mirror_object", source, about=about, follow_anchor=True)
    assert centres(following) == centres(result)
    assert not following.answered
    explicit = run(
        "mirror_object", source, about=about, follow_anchor=True, cx=10.0, cy=0.0, cz=5.0
    )
    assert centres(explicit)[0] == pytest.approx((-20.0, 12.0, 5.0))


def test_linear_pattern_ignores_unused_partial_centre() -> None:
    assert centres(run("pattern", cube(), kind="linear", count=2, spacing=15.0, cx=3.0)) == [
        (0.0, 0.0, 0.0),
        (15.0, 0.0, 0.0),
    ]
