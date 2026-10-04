"""Ein Konturdeckel mit Scharnier oder Stift (RM-184, Dateiaudit §6).

Die Quelle im Audit ist der Klappdeckel für ein Three-Sixty-Glas
(``06_Glasdeckel_ThreeSixty/Versuch 1/Deckel_ThreeSixty.py``): rund Ø 77 oder
eckig 77 mm mit R 12, Deckel 3 mm, Zentrieransatz, Scharnierstift Ø 3 in
Bohrungen Ø 3,4, zwei Augen am Ring und eines am Deckel. Die Abnahme des Audits
steht hier als Tests:

* Rund und eckig folgen derselben Quellkontur.
* Der Deckelkragen kollidiert beim Öffnen nicht — gemessen am Fügeweg, der
  den Deckel um die Achse schwenkt, mit der Gegenprobe ohne Kragenbeschnitt.
* Beide Hälften und der Stift bleiben gemeinsam parametriert: Der Stift ist
  ein Schritt an der Scharnierbohrung des Deckels und folgt ihr.
"""

from __future__ import annotations

import math

import pytest

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom.boolean import boolean, shared_volume
from app.core.geom.lid_hinge import (
    BORE_PIN_FEATURE,
    HINGE_HOLE_FEATURE,
    HINGE_PIN_FEATURE,
)
from app.core.geom.mesh import as_mesh_data
from app.core.geom.prepare import check_join_path
from app.core.knowledge import profiles
from app.core.knowledge.parts import shapes
from app.core.lid_flow import apply_lid
from app.core.scene import History, evaluate
from app.core.scene.fits import active_fits, check
from app.core.scene.history import OperationDraft
from app.core.scene.project import ProjectSources, new_project
from app.core.types import Feature, OpResult, Profile, SceneObject
from tests.helpers import exact_kernel
from tests.helpers import run_operation as run

#: Die Maße der Quelle: Glasrand 77 mm, Wand des Rings 3 mm, Ecken R 12.
RIM = 77.0
WALL = 3.0
CORNER = 12.0
HEIGHT = 30.0


@pytest.fixture(autouse=True)
def _operations() -> None:
    load_operations()


@pytest.fixture
def pla() -> Profile:
    """PLA wie in der Quelle; das Spiel kommt aus dem Profil."""
    return profiles.make_profile("centauri-carbon-2", "pla")


def _glass(kind: str, shape: str) -> SceneObject:
    """Der Ring um das Glas als oben offenes Gehäuse — rund oder eckig, wie die Quelle."""
    if kind == "brep":
        exact_kernel()
    inner = RIM - 2.0 * WALL
    with shapes.building(kind):  # type: ignore[arg-type]
        if shape == "round":
            outer = shapes.cylinder(RIM, HEIGHT)
            hollow = shapes.moved(shapes.cylinder(inner, HEIGHT), (0.0, 0.0, 2.0))
        else:
            outer = shapes.rounded_box(RIM, RIM, HEIGHT, CORNER)
            hollow = shapes.moved(
                shapes.rounded_box(inner, inner, HEIGHT, CORNER - WALL), (0.0, 0.0, 2.0)
            )
    if kind == "brep":
        from app.core.brep import edit

        body = edit.unified(edit.boolean("difference", [outer, hollow]))  # type: ignore[list-item]
    else:
        body = boolean("difference", [outer, hollow], quality="fine").mesh  # type: ignore[list-item]
    return SceneObject(id="obj_1", name="Ring", mesh=body, kind=kind, features={})


def _opens(result: OpResult, *, turn: float = 110.0) -> list[str]:
    """Die Befunde des Fügewegs, der den Deckel aus der Endlage um die Achse schwenkt."""
    housing, lid = result.outputs[0], result.outputs[1]
    axis = lid.features[HINGE_HOLE_FEATURE].params
    findings = check_join_path(
        as_mesh_data(lid.mesh),
        as_mesh_data(housing.mesh),
        (0.0, 0.0, 1.0),
        0.0,
        steps=72,
        turn=turn,
        turn_axis=tuple(axis["axis"]),
        pivot=tuple(axis["centre"]),
    )
    return [finding.code for finding in findings]


@pytest.mark.parametrize("hinge", ["barrel", "loose_pin"])
@pytest.mark.parametrize("shape", ["square", "round"])
@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_hinged_lid_opens_without_its_collar_touching_the_wall(
    kind: str, shape: str, hinge: str, pla: Profile
) -> None:
    """Geschlossen gebaut, um 110 Grad aufgeschwenkt: Der Weg ist frei — rund wie eckig.

    Ein Kragen von 12 mm reicht tief genug, dass seine Unterkante gegenüber
    der Achse ohne Beschnitt die Wand träfe (die Gegenprobe darunter).
    """
    result = run(
        "create_lid",
        _glass(kind, shape),
        pla,
        hinge=hinge,
        opening_angle=0.0,
        collar=12.0,
        thickness=3.0,
    )
    housing, lid = result.outputs
    assert as_mesh_data(housing.mesh).is_watertight and as_mesh_data(lid.mesh).is_watertight
    assert _opens(result) == ["join.clear"]
    hole = lid.features[HINGE_HOLE_FEATURE]
    clearance = pla.material.clearance
    gap = clearance / 2.0
    radius = 3.0 / 2.0 + gap + 2.5
    # Die Achse liegt um Augenradius und halbes Spiel hinter der Außenwand,
    # um denselben Betrag über dem Rand (Quelle: Achse auf halber Deckelhöhe
    # über einem Auge Ø 8,4 — hier ohne Berührung zwischen Deckel und Gehäuse).
    assert hole.params["centre"][1] == pytest.approx(RIM / 2.0 + radius + gap, abs=1e-6)
    assert hole.params["centre"][2] == pytest.approx(HEIGHT + radius + gap, abs=1e-6)
    assert hole.params["diameter"] == pytest.approx(3.0 + clearance)
    assert tuple(hole.params["axis"]) == pytest.approx((1.0, 0.0, 0.0))


def test_without_the_trimmed_collar_the_lid_would_strike_the_wall(
    pla: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gegenprobe: Derselbe Deckel mit einem Kragenraum, der nichts beschneidet, stößt an."""
    from app.core.geom import lid_hinge

    original = lid_hinge.keep_profile

    def generous(footprint: object, hinge: object) -> list[tuple[float, float]]:
        return [(radius * 10.0, along) for radius, along in original(footprint, hinge)]  # type: ignore[arg-type]

    monkeypatch.setattr(lid_hinge, "keep_profile", generous)
    result = run(
        "create_lid",
        _glass("mesh", "square"),
        pla,
        hinge="barrel",
        opening_angle=0.0,
        collar=12.0,
        thickness=3.0,
    )
    assert "join.interference" in _opens(result)


def test_the_printed_hinge_comes_out_open_with_its_halves_on_one_axis(pla: Profile) -> None:
    """Mitgedruckt entsteht der Deckel um 180 Grad aufgeklappt — getrennt vom Gehäuse.

    Bolzen am Gehäuse und Bohrung am Deckel liegen auf derselben Achse; die
    Bohrung ist um das Spiel weiter als der Bolzen.
    """
    result = run("create_lid", _glass("mesh", "square"), pla, hinge="barrel", thickness=3.0)
    housing, lid = result.outputs
    assert shared_volume(as_mesh_data(lid.mesh).raw, as_mesh_data(housing.mesh).raw) <= 1e-3
    pin = housing.features[HINGE_PIN_FEATURE]
    hole = lid.features[HINGE_HOLE_FEATURE]
    assert tuple(pin.params["centre"]) == pytest.approx(tuple(hole.params["centre"]), abs=1e-6)
    assert hole.params["diameter"] - pin.params["diameter"] == pytest.approx(pla.material.clearance)
    # Aufgeklappt liegt der Deckel hinter der Achse.
    assert as_mesh_data(lid.mesh).bounds.minimum[1] > RIM / 2.0
    assert [finding.code for finding in result.findings] == ["parts.lid", "parts.lid_hinge"]


def test_the_hinge_sits_on_the_side_that_was_chosen(pla: Profile) -> None:
    """Rechts heißt +x: Die Achse läuft längs Y, hinter der rechten Wand."""
    result = run(
        "create_lid",
        _glass("mesh", "square"),
        pla,
        hinge="loose_pin",
        hinge_side="hinge_right",
        collar=4.0,
        thickness=3.0,
    )
    hole = result.outputs[1].features[HINGE_HOLE_FEATURE]
    gap = pla.material.clearance / 2.0
    assert hole.params["centre"][0] == pytest.approx(RIM / 2.0 + 3.0 / 2.0 + 2 * gap + 2.5)
    assert abs(hole.params["axis"][1]) == pytest.approx(1.0)
    assert _opens(result) == ["join.clear"]


def test_a_side_opening_gets_its_hinge_on_the_side_too(pla: Profile) -> None:
    """Ein Kasten, vorn offen (RM-087): Der Deckel steht vor der Öffnung, die Augen daneben."""
    with shapes.building("mesh"):
        outer = shapes.box(60.0, 40.0, 40.0)
        hollow = shapes.moved(shapes.box(54.0, 40.0, 34.0), (0.0, -3.0, 3.0))
    body = boolean("difference", [outer, hollow], quality="fine").mesh  # type: ignore[list-item]
    front = Feature(
        id="face_front",
        kind="face",
        provenance="native",
        params={"normal": (0.0, -1.0, 0.0), "centre": (0.0, -20.0, 20.0), "area": 2400.0},
    )
    box = SceneObject(id="obj_1", name="Kasten", mesh=body, kind="mesh", features={front.id: front})
    result = run(
        "create_lid",
        box,
        pla,
        at_feature="face_front",
        hinge="loose_pin",
        collar=4.0,
        thickness=3.0,
    )
    housing, lid = result.outputs
    hole = lid.features[HINGE_HOLE_FEATURE]
    # Die Platte vor der Öffnung (y kleiner als -20), der Kragen 4 mm hinein,
    # die Achse waagerecht längs X und vor der Öffnung.
    bounds = as_mesh_data(lid.mesh).bounds
    assert bounds.maximum[1] == pytest.approx(-20.0 + 4.0, abs=1e-6)
    assert bounds.minimum[1] < -20.0
    assert hole.params["centre"][1] < -20.0
    assert abs(hole.params["axis"][0]) == pytest.approx(1.0)
    assert as_mesh_data(housing.mesh).bounds.minimum[1] < -20.0, "die Augen hängen am Gehäuse"


def test_a_hinge_wider_than_the_side_is_refused_with_its_measure(pla: Profile) -> None:
    with pytest.raises(ValidationError) as problem:
        run("create_lid", _glass("mesh", "square"), pla, hinge="barrel", hinge_width=100.0)
    assert problem.value.constraint == "hinge_width"
    assert problem.value.suggestions, "Regel 17"


def test_a_lid_without_hinge_is_built_as_before(pla: Profile) -> None:
    """Ohne Scharnier ändert sich nichts — dasselbe Gehäuse, derselbe Deckel."""
    source = _glass("mesh", "square")
    plain = run("create_lid", source, pla, collar=4.0, thickness=3.0)
    assert plain.outputs[0].mesh is source.mesh, "das Gehäuse bleibt unangetastet"
    assert HINGE_HOLE_FEATURE not in plain.outputs[1].features


def _ring_document(profile: Profile) -> tuple[object, str]:
    """Ein Dokument mit dem eckigen Ring als Quader, ausgehöhlt und oben offen."""
    document = new_project("centauri-carbon-2", "pla").document
    history = History(document)
    history.apply(
        "Ring",
        [OperationDraft(op="create_box", params={"width": RIM, "depth": RIM, "height": HEIGHT})],
    )
    history.apply(
        "Aushöhlen",
        [
            OperationDraft(
                op="hollow_object",
                inputs=(document.ops[-1].outputs[0],),
                params={"wall": WALL, "open_top": True},
            )
        ],
    )
    return document, str(document.ops[-1].outputs[0])


def test_the_pin_is_a_step_of_its_own_that_follows_the_lid(pla: Profile) -> None:
    """Mit Stift: drei Teile in einer Transaktion, der Stift an der Bohrung des Deckels.

    Er ist so dick wie das Stiftmaß und so lang wie das Scharnier; ändert sich
    der Deckelschritt, folgt der Stift — beide Hälften und der Stift bleiben
    gemeinsam parametriert (Abnahme des Audits).
    """
    document, ring = _ring_document(pla)
    steps = len(document.ops)
    applied = apply_lid(document, ring, {"hinge": "loose_pin", "collar": 4.0, "thickness": 3.0})
    assert [entry.op for entry in document.ops[steps:]] == ["create_lid", "pin_for_bore"]
    assert len(applied.object_ids) == 3
    result = evaluate(document, pla, sources=ProjectSources(new_project()))
    assert result.stopped_at is None
    pin_body = result.scene.objects[applied.object_ids[2]]
    pin = pin_body.features[BORE_PIN_FEATURE]
    assert pin.params["diameter"] == pytest.approx(3.0)
    assert pin.params["depth"] == pytest.approx(27.0)
    volume = as_mesh_data(pin_body.mesh).volume
    assert volume == pytest.approx(math.pi * 1.5 * 1.5 * 27.0, rel=0.02)

    names = {fit.name for fit in active_fits(document)}
    assert names == {"deckel", "scharnier"}
    problems = [
        finding.code
        for finding in check(result.scene, pla, document=document)
        if finding.code.startswith("fit.") and finding.severity != "info"
    ]
    assert not problems, problems

    lid_step = document.ops[steps]
    History(document).change_params(lid_step.id, {**lid_step.params, "hinge_width": 33.0})
    changed = evaluate(document, pla)
    assert changed.scene.objects[applied.object_ids[2]].features[BORE_PIN_FEATURE].params[
        "depth"
    ] == pytest.approx(33.0)

    History(document).undo()
    History(document).undo()
    assert len(document.ops) == steps, "ein Strg+Z nahm Deckel, Stift und Passungen"
    assert not active_fits(document)


def test_the_printed_hinge_carries_its_fit(pla: Profile) -> None:
    document, ring = _ring_document(pla)
    apply_lid(document, ring, {"hinge": "barrel", "collar": 4.0, "thickness": 3.0})
    fits = {fit.name: fit for fit in active_fits(document)}
    assert fits["scharnier"].a.feature_id == HINGE_PIN_FEATURE
    assert fits["scharnier"].b.feature_id == HINGE_HOLE_FEATURE
    result = evaluate(document, pla)
    violated = [
        finding.code
        for finding in check(result.scene, pla, document=document)
        if finding.code in {"fit.violated", "fit.missing_feature", "fit.collision"}
    ]
    assert not violated, violated


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_pin_for_bore_makes_a_loose_pin_in_any_bore(kind: str, pla: Profile) -> None:
    """*Stift für Bohrung* an einer Bohrung, die nicht vom Deckel kommt: Ø 6, 10 tief."""
    from app.core.knowledge.parts.build import bore

    if kind == "brep":
        exact_kernel()
    with shapes.building(kind):  # type: ignore[arg-type]
        plate = shapes.box(30.0, 30.0, 10.0)
        cut = shapes.moved(shapes.cylinder(6.0, 12.0), (0.0, 0.0, -1.0))
    if kind == "brep":
        from app.core.brep import edit

        body = edit.boolean("difference", [plate, cut])  # type: ignore[list-item]
    else:
        body = boolean("difference", [plate, cut], quality="fine").mesh  # type: ignore[list-item]
    key, hole = bore("hole_1", 6.0, (0.0, 0.0, 5.0), depth=10.0, through=True)
    source = SceneObject(id="obj_1", name="Platte", mesh=body, kind=kind, features={key: hole})
    result = run("pin_for_bore", source, pla, at_feature="hole_1")
    kept, made = result.outputs
    assert kept is source
    clearance = pla.material.clearance
    pin = made.features[BORE_PIN_FEATURE]
    assert pin.params["diameter"] == pytest.approx(6.0 - clearance)
    mesh = as_mesh_data(made.mesh)
    assert mesh.volume == pytest.approx(math.pi * (3.0 - clearance / 2.0) ** 2 * 10.0, rel=0.02)
    assert shared_volume(mesh.raw, as_mesh_data(source.mesh).raw) <= 1e-3, "er steckt lose"
    with pytest.raises(ValidationError) as problem:
        run("pin_for_bore", source, pla, at_feature="nothing")
    assert problem.value.constraint == "not_a_hole"
