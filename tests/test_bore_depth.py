"""Die Tiefe einer erkannten Bohrung ändern — an beiden Kernen über *Bohrung ändern*.

An einer erkannten STL-Bohrung war die Tiefe kein Feld, nur Auskunft
(„Gemessene Tiefe"), die Website zeigte sie als Feld (Sollliste der Durchsicht
vor 0.5.0). Seit dem 22.09.2026 trägt ``resize_hole`` einen Wert ``depth``:
tiefer schneidet nach, flacher füllt vom Grund her auf, null oder eine Tiefe
über die Wand hinaus macht eine Durchgangsbohrung, eine Tiefe an einer
Durchgangsbohrung macht ein Sackloch — und wenn beide Seiten offen sind, wird
gefragt, welche offen bleibt (Regel 21).

Die Sollwerte kommen aus der Analytik: Platte 60 x 40 x 10, Bohrung Ø 6, das
Volumen eines Zylinders ist π·r²·h. Der exakte Kern trifft es auf 10⁻⁶ mm³ (das
native Volumen, nicht das der Tessellierung); das Netz schneidet die neue
Bohrung als regelmäßiges Vieleck mit ``BORE_SECTIONS`` Ecken und trifft dessen
Fläche mal Länge ebenso genau.
"""

from __future__ import annotations

import importlib
import math
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np
import pytest

from app.core.bootstrap import load_operations
from app.core.geom.mesh import as_mesh_data
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import (
    Feature,
    Finding,
    OpContext,
    Operation,
    OpResult,
    Profile,
    Scene,
    SceneObject,
)
from tests.helpers import evaluated_operation

pytest.importorskip("OCP", reason="OpenCASCADE baut die analytischen Vorlagen")

PLATE = 60.0 * 40.0 * 10.0
RADIUS = 3.0


def _cylinder(radius: float, height: float) -> float:
    return math.pi * radius * radius * height


def _bore(kernel: str, radius: float, height: float) -> float:
    """Was eine Bohrung dieser Länge abträgt — am Netz als Vieleck ihres Werkzeugs."""
    from app.core.geom.prepare import BORE_SECTIONS

    if kernel == "brep":
        return _cylinder(radius, height)
    area = BORE_SECTIONS / 2.0 * radius * radius * math.sin(math.tau / BORE_SECTIONS)
    return area * height


def _plate(kernel: str, outline: Sequence[tuple[float, float]], *, box=(60.0, 40.0, 10.0)):
    """Eine Platte mit einer gedrehten Bohrung aus ``outline`` (Radius, Höhe)."""
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.perceive.features import detect
    from app.core.sketch.planes import frame_of

    solid = edit.bore_profile(edit.box(*box), list(outline), frame_of((0, 0, 1), (0, 0, 0)))
    if kernel == "brep":
        return SceneObject("plate", "Platte", solid, kind="brep", features=features_of(solid))
    mesh = as_mesh_data(solid)
    return SceneObject("plate", "Platte", mesh, features=detect(mesh))


def _blind(kernel: str) -> SceneObject:
    """Sackloch Ø 6, 6 mm tief von der Oberseite: Boden bei z = 4."""
    return _plate(kernel, [(0, 4), (3, 4), (3, 10), (0, 10), (0, 4)])


def _through(kernel: str) -> SceneObject:
    return _plate(kernel, [(0, 0), (3, 0), (3, 10), (0, 10), (0, 0)])


def _hole(source: SceneObject) -> Feature:
    return next(feature for feature in source.features.values() if feature.kind == "hole")


def _floor(source: SceneObject, height: float) -> Feature:
    found = [
        feature
        for feature in source.features.values()
        if feature.kind == "face"
        and np.allclose(feature.params["centre"], (0, 0, height), atol=1e-4)
        and np.allclose(np.abs(feature.params["normal"]), (0, 0, 1), atol=1e-4)
    ]
    assert len(found) == 1, f"kein eindeutiger Boden bei z = {height}"
    return found[0]


def _run(
    source: SceneObject,
    profile: Profile,
    *,
    ask: Callable[[str, list[str]], str] | None = None,
    **params: Any,
) -> tuple[SceneObject, list[Finding], OpResult]:
    """Den Kundenweg samt der Zuordnung der Auswertung fahren."""
    load_operations()
    spec = REGISTRY.get("resize_hole")
    hole = _hole(source)
    values = {"at_feature": hole.id, "diameter": 6.0, "compensate": False, **params}

    def refuse(*_args: object) -> str:
        pytest.fail("unerwartete Rückfrage")

    result = spec.fn(
        OpContext(
            scene=Scene(objects={source.id: source}),
            inputs=[source],
            params=spec.params(**values),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda *_args: None,
            ask=ask or refuse,
            cancelled=NeverCancelled(),
        )
    )
    findings: list[Finding] = list(result.findings)
    evaluation = importlib.import_module("app.core.scene.evaluate")
    changed = evaluation._with_features(
        result.outputs[0],
        source.features,
        Operation(9, "resize_hole", params=values),
        lambda *_args: pytest.fail("unerwartete Zuordnungsfrage"),
        findings,
        previous_bounds=source.mesh.bounds,
    )
    return changed, findings, result


def _volume(entry: SceneObject) -> float:
    """Am exakten Körper das native Volumen, sonst das des Netzes."""
    if entry.kind == "brep":
        return float(entry.mesh.volume)
    return float(as_mesh_data(entry.mesh).volume)


def _material_at(entry: SceneObject, *points: tuple[float, float, float]) -> list[bool]:
    """Innen/Außen über den Raumwinkel — ``contains`` bräuchte ``rtree``."""
    from tests.test_slot_features import _inside

    return [bool(value) for value in _inside(as_mesh_data(entry.mesh), list(points))]


def _assert_volume(entry: SceneObject, expected: float, bore: float = 0.0) -> None:
    """``bore`` weitet die Toleranz nur, wo ein erkannter Netzabschnitt stehen bleibt."""
    assert _volume(entry) == pytest.approx(expected, abs=0.005 * bore + 1e-6)


def _codes(findings: Sequence[Finding]) -> list[str]:
    return [finding.code for finding in findings]


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("depth", [8.0, 3.0], ids=["tiefer", "flacher"])
def test_a_blind_hole_goes_deeper_or_shallower_from_its_mouth(
    profile: Profile, kernel: str, depth: float
) -> None:
    """Tiefer schneidet nach, flacher füllt vom Grund auf — die Mündung bleibt."""
    source = _blind(kernel)
    hole, floor = _hole(source), _floor(source, 4.0)

    changed, findings, _result = _run(source, profile, depth=depth)

    _assert_volume(changed, PLATE - _bore(kernel, RADIUS, depth))
    bottom = 10.0 - depth
    assert _material_at(changed, (0, 0, bottom - 0.1), (0, 0, bottom + 0.1), (0, 0, 9.9)) == [
        True,
        False,
        False,
    ], "der Boden liegt bei der neuen Tiefe, die Mündung oben bleibt offen"
    kept = changed.features[hole.id]
    assert kept.kind == "hole" and not kept.params.get("through")
    assert float(kept.params["depth"]) == pytest.approx(depth, abs=0.01)
    assert float(kept.params["diameter"]) == pytest.approx(6.0, abs=0.01)
    moved_floor = changed.features[floor.id]
    assert moved_floor.kind == "face"
    assert moved_floor.params["centre"][2] == pytest.approx(bottom, abs=1e-4), (
        "der Boden behält seine Kennung und wandert mit"
    )
    assert "perceive.orphaned" not in _codes(findings)
    assert as_mesh_data(changed.mesh).is_watertight


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_diameter_and_depth_change_together(profile: Profile, kernel: str) -> None:
    source = _blind(kernel)

    changed, _findings, _result = _run(source, profile, diameter=8.0, depth=8.0)

    _assert_volume(changed, PLATE - _bore(kernel, 4.0, 8.0))
    kept = changed.features[_hole(source).id]
    assert float(kept.params["diameter"]) == pytest.approx(8.0, abs=0.02)
    assert float(kept.params["depth"]) == pytest.approx(8.0, abs=0.01)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("depth", [0.0, 14.0], ids=["null", "ueber-die-wand"])
def test_a_blind_hole_becomes_a_through_hole_and_says_so(
    profile: Profile, kernel: str, depth: float
) -> None:
    source = _blind(kernel)

    changed, findings, _result = _run(source, profile, depth=depth)

    _assert_volume(changed, PLATE - _bore(kernel, RADIUS, 10.0))
    assert changed.features[_hole(source).id].params.get("through")
    through = [finding for finding in findings if finding.code == "bore.now_through"]
    assert len(through) == 1
    # Null ist der ausdrückliche Wunsch „durch"; 14 mm war ein Sackloch, das
    # nicht in die Wand passt — das sagt eine Warnung mit der größten Tiefe.
    if depth:
        assert through[0].severity == "warning"
        assert float(through[0].values["largest"]) == pytest.approx(10.0 - 0.84, abs=0.01)
    else:
        assert through[0].severity == "info"


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("side", ["Oberseite", "Unterseite"])
def test_a_through_hole_asks_which_side_stays_open(
    profile: Profile, kernel: str, side: str
) -> None:
    """Beide Enden sind offen — welches die Mündung bleibt, sagt der Kunde."""
    source = _through(kernel)
    asked: list[list[str]] = []

    def answer(_question: str, choices: list[str]) -> str:
        asked.append(list(choices))
        return side

    changed, _findings, result = _run(source, profile, depth=4.0, ask=answer)

    assert asked == [["Oberseite", "Unterseite"]]
    _assert_volume(changed, PLATE - _bore(kernel, RADIUS, 4.0))
    bottom = 6.0 if side == "Oberseite" else 4.0
    open_at = (0.0, 0.0, 8.0) if side == "Oberseite" else (0.0, 0.0, 2.0)
    solid_at = (0.0, 0.0, 2.0) if side == "Oberseite" else (0.0, 0.0, 8.0)
    assert _material_at(changed, open_at, solid_at) == [False, True]
    kept = changed.features[_hole(source).id]
    assert not kept.params.get("through")
    assert float(kept.params["centre"][2]) == pytest.approx(
        (bottom + (10.0 if side == "Oberseite" else 0.0)) / 2.0, abs=0.01
    )

    # Die Antwort steht im Schritt; die nächste Auswertung fragt nicht noch einmal.
    again, _findings, _result = _run(source, profile, depth=4.0, **result.answered)
    assert _volume(again) == pytest.approx(_volume(changed), abs=1e-6)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_the_depth_of_a_sunk_bore_moves_its_floor_and_keeps_the_countersink(
    profile: Profile, kernel: str
) -> None:
    """Senkbohrung: Die Mündung der Bohrung liegt unter der Senkung — die bleibt."""
    source = _plate(
        kernel,
        [(0, 2), (3, 2), (3, 10), (5, 12), (0, 12), (0, 2)],
        box=(30.0, 24.0, 12.0),
    )
    cone = next(feature for feature in source.features.values() if feature.kind == "cone")
    floor = _floor(source, 2.0)
    # Kegelstumpf r 3 → 5 über 2 mm, darunter der Schaft, jetzt 6 mm lang.
    funnel = math.pi * 2.0 / 3.0 * (25.0 + 15.0 + 9.0)
    cavity = funnel + _cylinder(RADIUS, 6.0)

    changed, findings, _result = _run(source, profile, depth=6.0)

    # Am Netz bleibt der erkannte Trichter als Vieleck der Vorlage stehen.
    _assert_volume(changed, 30.0 * 24.0 * 12.0 - cavity, cavity if kernel == "mesh" else 0.0)
    assert _material_at(changed, (0, 0, 3.9), (0, 0, 4.1), (0, 0, 11.0)) == [True, False, False]
    assert changed.features[cone.id].kind == "cone", "die Senkung bleibt"
    assert changed.features[floor.id].params["centre"][2] == pytest.approx(4.0, abs=1e-4)
    assert "perceive.orphaned" not in _codes(findings)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_a_floor_left_too_thin_says_so(profile: Profile, kernel: str) -> None:
    source = _blind(kernel)

    changed, findings, _result = _run(source, profile, depth=9.6)

    _assert_volume(changed, PLATE - _bore(kernel, RADIUS, 9.6))
    thin = [finding for finding in findings if finding.code == "bore.floor_thin"]
    assert len(thin) == 1 and thin[0].suggestions
    assert float(thin[0].values["thickness"]) == pytest.approx(0.4, abs=0.01)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_a_deeper_hole_near_a_neighbour_says_what_it_does_to_the_wall(
    profile: Profile, kernel: str
) -> None:
    """Eine Querbohrung unter dem Sackloch: tiefer heißt dünnere Wand, dann offen."""
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.perceive.features import detect

    plate = edit.box(60.0, 40.0, 20.0)
    plate = edit.cut_bore(
        plate, position=(0.0, 0.0, 17.0), direction=(0.0, 0.0, 1.0), diameter=6.0, depth=6.0
    )
    plate = edit.cut_bore(
        plate, position=(0.0, 0.0, 8.0), direction=(1.0, 0.0, 0.0), diameter=6.0, depth=80.0
    )
    if kernel == "brep":
        source = SceneObject("plate", "Platte", plate, kind="brep", features=features_of(plate))
    else:
        mesh = as_mesh_data(plate)
        source = SceneObject("plate", "Platte", mesh, features=detect(mesh))
    vertical = next(
        feature
        for feature in source.features.values()
        if feature.kind == "hole" and abs(float(feature.params["axis"][2])) > 0.9
    )
    load_operations()

    def run(depth: float) -> list[str]:
        spec = REGISTRY.get("resize_hole")
        result = spec.fn(
            OpContext(
                scene=Scene(objects={source.id: source}),
                inputs=[source],
                params=spec.params(
                    at_feature=vertical.id, diameter=6.0, compensate=False, depth=depth
                ),
                profile=profile,
                quality="fine",
                seed=7,
                progress=lambda *_args: None,
                ask=lambda *_args: pytest.fail("unerwartete Rückfrage"),
                cancelled=NeverCancelled(),
            )
        )
        return _codes(result.findings)

    # Boden bei 20 - 8.5 = 11.5, Querbohrung oben bei 11: 0,5 mm Wand.
    assert "bore.neighbour_wall_thin" in run(8.5)
    assert "bore.neighbour_opened" in run(10.0)
    assert not {"bore.neighbour_wall_thin", "bore.neighbour_opened"} & set(run(5.0))


@pytest.mark.parametrize(
    ("through", "depth", "unchanged"),
    [
        (False, None, True),
        (True, None, True),
        (False, 0.0, False),
        (True, 0.0, True),
        (False, 6.0, True),
        (True, 6.0, True),
        (False, 6.004, True),
        (False, 6.006, False),
        (True, 5.996, True),
        (True, 5.994, False),
        (False, 12.0, False),
        (True, 12.0, True),
    ],
)
def test_the_depth_wish_distinguishes_real_changes_from_display_rounding(
    through: bool, depth: float | None, unchanged: bool
) -> None:
    """Formwechsel und Tiefenoperation lesen denselben Wunsch ohne Geometrie oder Fenster."""
    from app.core.geom.prepare_ops import bore_depth_is_unchanged

    feature = Feature(
        id="hole_1", kind="hole", provenance="detected", params={"depth": 6.0, "through": through}
    )

    assert bore_depth_is_unchanged(feature, depth) is unchanged


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_an_unchanged_depth_changes_nothing(profile: Profile, kernel: str) -> None:
    blind = _blind(kernel)
    _changed, findings, result = _run(blind, profile, depth=6.0)
    assert result.outputs[0] is blind
    assert "bore.resize_unchanged" in _codes(findings)

    through = _through(kernel)
    _changed, findings, result = _run(through, profile, depth=12.0)
    assert result.outputs[0] is through
    assert "bore.already_through" in _codes(findings)


def test_the_depth_is_a_field_at_the_hole_and_the_side_is_asked() -> None:
    """Im Merkmalfenster steht die Tiefe als Feld; die offene Seite wird erfragt."""
    from app.core.perceive.actions import actions_for
    from app.core.registry.surfaces import asked_fields

    load_operations()
    spec = REGISTRY.get("resize_hole")
    assert "open_side" in asked_fields(spec)
    source = _blind("mesh")
    hole = _hole(source)
    action = next(
        entry
        for entry in actions_for(hole, source.features, mesh=as_mesh_data(source.mesh))
        if entry.op == "resize_hole"
    )
    fields = {field.name: field for field in action.fields}
    assert "depth" in fields and "open_side" not in fields
    assert float(fields["depth"].value) == pytest.approx(6.0, abs=1e-6)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("depth", [9.0, 4.0, 0.0], ids=["tiefer", "flacher", "durch"])
def test_a_tilted_blind_hole_keeps_its_mouth_in_the_face(
    profile: Profile, kernel: str, depth: float
) -> None:
    """Um 20° gekippt: Die Tiefe zählt, wie gemessen, bis zum höchsten Punkt des Rands.

    Gemessen wird die Wandlänge entlang der Achse (7,09 mm an einer Bohrung, deren
    Achse von der Mündungsmitte 6 mm tief reicht); eine neue Tiefe verschiebt nur
    den Boden. Abgetragen wird damit π·r²·(Tiefe − r·tan 20°); die schräge
    Mündung bleibt in der Oberseite, und über die Platte wächst nichts.
    """
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.perceive.features import detect

    tilt = math.radians(20.0)
    axis = np.array([0.0, math.sin(tilt), math.cos(tilt)])
    length = 10.0
    centre = np.array([0.0, 0.0, 20.0]) - axis * 6.0 + axis * length / 2.0
    solid = edit.cut_bore(
        edit.box(60.0, 40.0, 20.0),
        position=(float(centre[0]), float(centre[1]), float(centre[2])),
        direction=(float(axis[0]), float(axis[1]), float(axis[2])),
        diameter=6.0,
        depth=length,
    )
    if kernel == "brep":
        source = SceneObject("plate", "Platte", solid, kind="brep", features=features_of(solid))
    else:
        mesh = as_mesh_data(solid)
        source = SceneObject("plate", "Platte", mesh, features=detect(mesh))
    hole = _hole(source)
    spread = RADIUS * math.tan(tilt)
    assert float(hole.params["depth"]) == pytest.approx(6.0 + spread, abs=1e-3)

    changed, findings, _result = _run(source, profile, depth=depth)

    plate = 60.0 * 40.0 * 20.0
    # Am Netz ist die Achse gemessen (Abweichung um 10⁻⁶), das trägt ein
    # Hundertstel mm³ bei; der exakte Körper trifft die Analytik.
    slack = 2.0 if kernel == "mesh" else 0.0
    if depth:
        _assert_volume(changed, plate - _bore(kernel, RADIUS, depth - spread), slack)
    else:
        _assert_volume(changed, plate - _bore(kernel, RADIUS, 20.0 / math.cos(tilt)), slack)
        assert "bore.now_through" in _codes(findings)
    assert as_mesh_data(changed.mesh).bounds.maximum[2] == pytest.approx(20.0, abs=1e-6)
    assert as_mesh_data(changed.mesh).is_watertight


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("depth", [8.0, 3.0], ids=["tiefer", "flacher"])
def test_a_blind_slot_changes_its_depth_like_a_hole(
    profile: Profile, kernel: str, depth: float
) -> None:
    """Ein Langloch 16 x 6, 6 mm tief: dieselbe Tiefe, derselbe Umriss, dieselbe Mündung."""
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.perceive.features import detect

    solid = edit.slot_bore(
        edit.box(60.0, 40.0, 10.0),
        position=(0.0, 0.0, 7.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=6.0,
        length=16.0,
        angle_deg=0.0,
        overlap=0.0,
    )
    if kernel == "brep":
        source = SceneObject("plate", "Platte", solid, kind="brep", features=features_of(solid))
    else:
        mesh = as_mesh_data(solid)
        source = SceneObject("plate", "Platte", mesh, features=detect(mesh))
    slot = next(feature for feature in source.features.values() if feature.kind == "slot")
    load_operations()
    spec = REGISTRY.get("resize_hole")
    result = spec.fn(
        OpContext(
            scene=Scene(objects={source.id: source}),
            inputs=[source],
            params=spec.params(at_feature=slot.id, diameter=6.0, compensate=False, depth=depth),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda *_args: None,
            ask=lambda *_args: pytest.fail("unerwartete Rückfrage"),
            cancelled=NeverCancelled(),
        )
    )
    changed = result.outputs[0]

    ends = _bore(kernel, RADIUS, depth)
    # Der gerade Teil des Umrisses ist 10 mm lang und 6 mm breit.
    expected = PLATE - ends - 10.0 * 6.0 * depth
    assert _volume(changed) == pytest.approx(expected, abs=0.005 * ends + 1e-6)
    kept = changed.features[slot.id]
    assert kept.kind == "slot" and float(kept.params["depth"]) == pytest.approx(depth, abs=0.01)
    assert float(kept.params["length"]) == pytest.approx(16.0, abs=0.01)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_a_wider_entrance_and_a_new_depth_in_one_step(profile: Profile, kernel: str) -> None:
    """„Senkung, Stufen und Verengung mitnehmen" mit Ø 8 und 6 mm Tiefe.

    Erst der Einlauf, dann der Boden.
    """
    source = _plate(
        kernel,
        [(0, 2), (3, 2), (3, 10), (5, 12), (0, 12), (0, 2)],
        box=(30.0, 24.0, 12.0),
    )
    cone = next(feature for feature in source.features.values() if feature.kind == "cone")

    changed, findings, _result = _run(
        source, profile, diameter=8.0, depth=6.0, entrance_mode="follow"
    )

    funnel = math.pi * 2.0 / 3.0 * (36.0 + 24.0 + 16.0)
    cavity = funnel + _cylinder(4.0, 6.0)
    _assert_volume(changed, 30.0 * 24.0 * 12.0 - cavity, cavity if kernel == "mesh" else 0.0)
    assert float(changed.features[cone.id].params["diameter"]) == pytest.approx(12.0, abs=0.02)
    hole = changed.features[_hole(source).id]
    assert float(hole.params["diameter"]) == pytest.approx(8.0, abs=0.02)
    assert float(hole.params["depth"]) == pytest.approx(6.0, abs=0.01)
    assert "resize.widening_kept" not in _codes(findings), "die Senkung ist mitgegangen"


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_a_new_depth_says_nothing_about_the_countersink(profile: Profile, kernel: str) -> None:
    """Nur die Tiefe geändert: Die Senkung bleibt, wie sie war — kein Satz über sie."""
    source = _plate(
        kernel,
        [(0, 2), (3, 2), (3, 10), (5, 12), (0, 12), (0, 2)],
        box=(30.0, 24.0, 12.0),
    )
    _changed, findings, _result = _run(source, profile, depth=6.0, entrance_mode="follow")
    assert not {"resize.widening_kept", "resize.cavity_sections_kept"} & set(_codes(findings))


def _sunk_blind(kernel: str) -> SceneObject:
    """Sackloch Ø 6 mit Senkung Ø 10: Boden bei z = 2, Senkung 10 … 12."""
    return _plate(
        kernel, [(0, 2), (3, 2), (3, 10), (5, 12), (0, 12), (0, 2)], box=(30.0, 24.0, 12.0)
    )


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_a_tilted_countersunk_blind_hole_keeps_its_floor(profile: Profile, kernel: str) -> None:
    """Eine gesenkte Sackbohrung um 10° kippen: Der Boden bleibt, wo die Drehung ihn hinlegt.

    Das Werkzeug der Kette verlängerte die Bohrung über ihr fernes Ende hinaus,
    um die gekippte Mündung zu durchstoßen — an einem Sackloch ist das ferne
    Ende der Boden. Gemessen am 23.09.2026: Das Netz trug 18,3 mm³ zu viel ab,
    bis 0,6 mm unter den gedrehten Boden; der exakte Kern traf die Vorlage.
    Und der Boden verlor seine Kennung (Netz ``perceive.orphaned``).
    """
    from app.core.brep import edit
    from app.core.sketch.planes import frame_of

    tilt = math.radians(10.0)
    axis = (0.0, -math.sin(tilt), math.cos(tilt))
    # Die Vorlage: dieselbe Kontur um die Bohrungsmitte gedreht, der Kegel über
    # die Oberseite hinaus weitergeführt.
    truth = edit.bore_profile(
        edit.box(30.0, 24.0, 12.0),
        [(0, -4), (3, -4), (3, 4), (8, 9), (0, 9), (0, -4)],
        frame_of(axis, (0.0, 0.0, 6.0)),
    )
    source = _sunk_blind(kernel)
    floor = _floor(source, 2.0)

    changed, findings = evaluated_operation(
        source, profile, "rotate_feature", at_feature=_hole(source).id, axis="x", angle=10.0
    )

    removed = 30.0 * 24.0 * 12.0 - _volume(changed)
    expected = 30.0 * 24.0 * 12.0 - float(truth.volume)
    # Am Netz schneiden Vielecke; ein halbes Prozent des Hohlraums deckt sie.
    assert removed == pytest.approx(expected, abs=1e-6 if kernel == "brep" else 0.005 * expected)
    kept = changed.features[floor.id]
    assert kept.kind == "face"
    assert kept.params["centre"] == pytest.approx(
        (0.0, 4.0 * math.sin(tilt), 6.0 - 4.0 * math.cos(tilt)), abs=1e-3
    )
    assert "perceive.orphaned" not in _codes(findings)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_a_tilted_blind_hole_stays_open_at_its_mouth(profile: Profile, kernel: str) -> None:
    """Ein Sackloch um 10° kippen: Die Mündung bleibt ganz offen, der Boden kippt mit (RM-263).

    Das Werkzeug einer einzelnen Sackbohrung war die gemessene Bohrung, gedreht —
    ohne Verlängerung über die Mündung, die eine Kette und eine
    Durchgangsbohrung längst bekommen. Auf der Seite, zu der die Mündung sank,
    blieb eine Haut aus Material über der Öffnung stehen, bis 0,5 mm dick; am
    Netz um die Zugabe aus §39 dünner als am exakten Körper, und so kippte die
    Magnettasche ohne Lippe an den Kernen um 0,56 mm³ verschieden.
    """
    from app.core.brep import edit
    from app.core.sketch.planes import frame_of

    tilt = math.radians(10.0)
    axis = (0.0, -math.sin(tilt), math.cos(tilt))
    # Die Vorlage: dasselbe Sackloch um seine Mitte (z = 7) gedreht und über
    # die Oberseite hinaus weitergeführt; was darüber liegt, ist Luft.
    truth = edit.bore_profile(
        edit.box(60.0, 40.0, 10.0),
        [(0, -3), (3, -3), (3, 6), (0, 6), (0, -3)],
        frame_of(axis, (0.0, 0.0, 7.0)),
    )
    source = _blind(kernel)

    changed, findings = evaluated_operation(
        source, profile, "rotate_feature", at_feature=_hole(source).id, axis="x", angle=10.0
    )

    removed = PLATE - _volume(changed)
    expected = PLATE - float(truth.volume)
    assert removed == pytest.approx(expected, abs=1e-6 if kernel == "brep" else 0.005 * expected)
    # 3,3 mm entlang der gekippten Achse über der Mitte und 2,5 mm zur tiefen
    # Seite: Das liegt über dem alten Deckel der Bohrung und unter der
    # Oberseite — Luft, wo vorher die Haut stand. Unter dem gekippten Boden
    # bleibt Material.
    mouth = (
        0.0,
        -3.3 * math.sin(tilt) - 2.5 * math.cos(tilt),
        7.0 + 3.3 * math.cos(tilt) - 2.5 * math.sin(tilt),
    )
    floor = (0.0, 3.1 * math.sin(tilt), 7.0 - 3.1 * math.cos(tilt))
    assert _material_at(changed, mouth, floor) == [False, True]
    assert [code for code in _codes(findings) if code.endswith(".mouth_covered")] == []


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("op", ["move_feature", "rotate_feature"])
def test_a_moved_or_tilted_countersunk_bore_leaves_no_scars(
    profile: Profile, kernel: str, op: str
) -> None:
    """Versetzen und Kippen einer Senkbohrung: Die alte Stelle ist glatt, der Boden reist mit.

    Die Kappen des Stopfens blieben am Netz als Dreiecke in der Oberseite
    stehen (Senkbohrung 304 → 470 beim ersten Versetzen; nach dem Entfernen
    trug die Platte aus zwölf Dreiecken 374), und der Sackboden bekam an beiden
    Kernen eine neue Kennung (gemessen 23.09.2026).
    """
    source = _sunk_blind(kernel)
    hole = _hole(source)
    floor = _floor(source, 2.0)
    params: dict[str, Any] = (
        {"x": 5.0, "y": 0.0, "z": float(hole.params["centre"][2])}
        if op == "move_feature"
        else {"axis": "x", "angle": 10.0}
    )

    changed, findings = evaluated_operation(source, profile, op, at_feature=hole.id, **params)

    assert "perceive.orphaned" not in _codes(findings)
    assert changed.features[floor.id].kind == "face"
    if kernel == "mesh":
        before = as_mesh_data(source.mesh).triangle_count
        assert as_mesh_data(changed.mesh).triangle_count <= before + 16, (
            "die Kappen des Stopfens sind zusammengelegt"
        )
