"""Freie Position und Richtung der fünf analytischen Grundkörper."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

import numpy as np
import pytest

from app.core.bootstrap import load_operations
from app.core.geom.mesh import as_mesh_data
from app.core.geom.primitive_ops import (
    placement_transform,
    placement_values_of,
    primitive_local_tool,
)
from app.core.geom.transform import apply
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.sketch.planes import frame_of
from app.core.types import OpContext, OpResult, Profile, Quality, Scene
from app.core.units import DEGREE_UNIT

load_operations()

CASES: tuple[tuple[str, dict[str, Any]], ...] = (
    (
        "create_box",
        {"width": 12.0, "depth": 8.0, "height": 5.0, "anchor": "centre", "name": ""},
    ),
    (
        "create_cylinder",
        {"diameter": 10.0, "height": 7.0, "segments": 32, "name": ""},
    ),
    (
        "create_cone",
        {
            "bottom_diameter": 12.0,
            "top_diameter": 6.0,
            "height": 9.0,
            "segments": 32,
            "name": "",
        },
    ),
    ("create_sphere", {"diameter": 10.0, "segments": 24, "name": ""}),
    (
        "create_torus",
        {"outer_diameter": 20.0, "tube_diameter": 4.0, "segments": 32, "name": ""},
    ),
)


def _run(
    name: str,
    values: Mapping[str, Any],
    profile: Profile,
    quality: Quality = "fine",
) -> OpResult:
    spec = REGISTRY.get(name)
    return spec.fn(
        OpContext(
            scene=Scene(),
            inputs=[],
            params=spec.params(**values),
            profile=profile,
            quality=quality,
            seed=None,
            progress=lambda _fraction, _text: None,
            ask=lambda _question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


@pytest.mark.parametrize(("name", "values"), CASES)
def test_mesh_primitives_offer_one_advanced_position_and_normal(
    name: str, values: dict[str, Any]
) -> None:
    schema = {entry.name: entry for entry in REGISTRY.get(name).params.spec()}

    for field in ("x", "y", "z", "nx", "ny", "nz", "angle"):
        assert schema[field].default == 0.0
        assert schema[field].placement == "advanced"
    assert schema["angle"].unit == DEGREE_UNIT, "die Drehung ist ein Winkel und kein Maß"


@pytest.mark.parametrize(("name", "values"), CASES)
def test_the_angle_turns_the_body_around_its_own_upright_axis(
    name: str, values: dict[str, Any], profile: Profile
) -> None:
    """Die Richtung sagt, wohin der Körper zeigt — die Drehung, wie er dabei steht.

    ``frame_of`` legt die Querachse zu einer gegebenen Normalen deterministisch
    fest, aber nicht wählbar: Für einen Zylinder ist das gleichgültig, für
    einen Quader nicht. Wer ihn um seine Hochachse drehen wollte, musste die
    Richtung verbiegen — und die meint etwas anderes (Robert, 09.09.2026:
    „verschieben und drehen wie unter dem Bewegungsmenü").

    **Gemessen wird an der Geometrie, nicht am Parameter**: Eine volle
    Umdrehung bringt denselben Körper zurück, und eine Vierteldrehung dreht
    die Hüllmaße in der Ebene, ohne Volumen oder Bezugspunkt zu bewegen.
    """
    gerade = as_mesh_data(_run(name, {**values, "angle": 0.0}, profile).outputs[0].mesh)
    gedreht = as_mesh_data(_run(name, {**values, "angle": 90.0}, profile).outputs[0].mesh)
    ganz = as_mesh_data(_run(name, {**values, "angle": 360.0}, profile).outputs[0].mesh)

    # **Zuerst: Sie wirkt überhaupt.** Die drei Zusicherungen darunter sind
    # Invarianten — Volumen, Bezugspunkt und die volle Umdrehung stimmen auch
    # dann, wenn der Winkel gar nichts tut. Ohne diese Zeile blieb der Test
    # grün, als die Drehung abgeschaltet war (gemessen, bevor sie hier stand).
    #
    # Gemessen wird an den Eckpunkten und nicht an den Hüllmaßen: Zylinder,
    # Kegel, Kugel und Ring sind um ihre Hochachse symmetrisch, ihre Hülle
    # ändert sich also nicht. Ihre Facetten drehen sich trotzdem mit — beim
    # Zylinder um 7,07 mm, beim Ring um 14,14.
    bewegung = float(
        np.abs(np.asarray(gerade.raw.vertices) - np.asarray(gedreht.raw.vertices)).max()
    )
    assert bewegung > 1.0, f"{name}: eine Vierteldrehung bewegt den Körper ({bewegung:.3f} mm)"

    assert gedreht.volume == pytest.approx(gerade.volume, rel=1e-9), (
        "eine Drehung nimmt kein Material weg"
    )
    gerade_mitte = (gerade.raw.bounds[0] + gerade.raw.bounds[1]) / 2.0
    gedrehte_mitte = (gedreht.raw.bounds[0] + gedreht.raw.bounds[1]) / 2.0
    assert gedrehte_mitte == pytest.approx(gerade_mitte, abs=1e-9), (
        "und sie verschiebt den Bezugspunkt nicht"
    )
    # **Eine volle Umdrehung ist dieselbe Lage.** Das prüft die Rechnung
    # selbst: Ein Winkel, der irgendwo in Grad und Bogenmaß verwechselt wird,
    # käme hier nicht zurück.
    assert np.asarray(ganz.raw.vertices) == pytest.approx(np.asarray(gerade.raw.vertices), abs=1e-9)


@pytest.mark.parametrize(("name", "values"), CASES)
def test_zero_placement_keeps_the_previous_primitive_geometry(
    name: str, values: dict[str, Any], profile: Profile
) -> None:
    spec = REGISTRY.get(name)
    params = spec.params(**values)
    local = primitive_local_tool(name, params.as_dict(), "fine")
    actual = as_mesh_data(_run(name, values, profile).outputs[0].mesh)

    assert np.asarray(actual.raw.vertices) == pytest.approx(
        np.asarray(local.raw.vertices), abs=1e-12
    )
    assert np.array_equal(actual.raw.faces, local.raw.faces)


@pytest.mark.parametrize(("name", "values"), CASES)
def test_zero_normal_translates_the_existing_local_anchor(
    name: str, values: dict[str, Any], profile: Profile
) -> None:
    position = np.asarray((7.25, -3.5, 11.0))
    spec = REGISTRY.get(name)
    params = spec.params(**values)
    local = primitive_local_tool(name, params.as_dict(), "fine")
    actual = as_mesh_data(
        _run(
            name,
            {**values, "x": position[0], "y": position[1], "z": position[2]},
            profile,
        )
        .outputs[0]
        .mesh
    )

    assert np.asarray(actual.raw.vertices) == pytest.approx(
        np.asarray(local.raw.vertices) + position, abs=1e-12
    )
    assert np.array_equal(actual.raw.faces, local.raw.faces)


@pytest.mark.parametrize(("name", "values"), CASES)
def test_slanted_operation_and_surface_ghost_share_the_same_local_basis(
    name: str, values: dict[str, Any], profile: Profile
) -> None:
    position = (7.25, -3.5, 11.0)
    normal = (2.0, -3.0, 6.0)
    spec = REGISTRY.get(name)
    params = spec.params(**values)
    local = primitive_local_tool(name, params.as_dict(), "fine")
    frame = frame_of(normal, position)
    matrix = np.eye(4)
    matrix[:3, :3] = np.column_stack((frame.x_axis, frame.y_axis, frame.normal))
    matrix[:3, 3] = position
    shown = apply(local, matrix)
    actual = _run(
        name,
        {
            **values,
            "x": position[0],
            "y": position[1],
            "z": position[2],
            "nx": normal[0],
            "ny": normal[1],
            "nz": normal[2],
        },
        profile,
    ).outputs[0]
    actual_mesh = as_mesh_data(actual.mesh)

    assert np.asarray(actual_mesh.raw.vertices) == pytest.approx(
        np.asarray(shown.raw.vertices), abs=1e-12
    )
    assert np.array_equal(actual_mesh.raw.faces, shown.raw.faces)
    if "face_top" in actual.features:
        assert actual.features["face_top"].params["normal"] == pytest.approx(frame.normal)
        expected_centre = matrix @ np.asarray((0.0, 0.0, float(values["height"]), 1.0))
        assert actual.features["face_top"].params["centre"] == pytest.approx(expected_centre[:3])


def test_box_corner_remains_the_local_anchor_when_it_is_moved(profile: Profile) -> None:
    position = np.asarray((4.0, 5.0, 6.0))
    result = _run(
        "create_box",
        {
            "width": 12.0,
            "depth": 8.0,
            "height": 5.0,
            "anchor": "corner",
            "name": "",
            "x": position[0],
            "y": position[1],
            "z": position[2],
        },
        profile,
    )

    assert as_mesh_data(result.outputs[0].mesh).bounds.minimum == pytest.approx(position)


@pytest.mark.parametrize(
    "placed",
    (
        {"x": 0.0, "y": 0.0, "z": 0.0, "nx": 0.0, "ny": 0.0, "nz": 0.0, "angle": 0.0},
        {"x": 15.0, "y": -8.0, "z": 3.0, "nx": 0.0, "ny": 0.0, "nz": 0.0, "angle": 0.0},
        {"x": 0.0, "y": 0.0, "z": 0.0, "nx": 0.0, "ny": 0.0, "nz": 1.0, "angle": 37.0},
        {"x": 5.0, "y": 2.0, "z": 1.0, "nx": 1.0, "ny": 0.0, "nz": 0.0, "angle": 90.0},
        {"x": -3.0, "y": 4.0, "z": 7.0, "nx": 0.3, "ny": 0.6, "nz": 0.74, "angle": -125.0},
    ),
)
def test_the_placement_survives_the_round_trip(placed: dict[str, float]) -> None:
    """Aus Zahlen wird eine Lage — und aus der Lage wieder dieselben Zahlen.

    Ein Griff im Bild liefert eine Matrix, das Dokument trägt Zahlen. Wer
    beide Richtungen getrennt rechnet, bekommt zwei Rechnungen, die
    auseinanderlaufen: Die Querachse zu einer Richtung wählt ``frame_of``
    deterministisch, aber nicht wählbar — wer sie beim Zurückrechnen anders
    wählt, verdreht den Körper bei jedem Zug ein Stück weiter.

    Geprüft wird deshalb gegen den Hinweg selbst und nicht gegen von Hand
    ausgerechnete Zahlen: ``placement_values_of(placement_transform(p))``
    muss ``p`` sein, auch bei schräger Richtung und negativem Winkel.
    """
    spec = REGISTRY.get("create_box")
    params = spec.params(width=10.0, depth=5.0, height=3.0, **placed)
    matrix = np.asarray(placement_transform(params), dtype=float)

    back = placement_values_of(matrix)

    assert (back["x"], back["y"], back["z"]) == pytest.approx(
        (placed["x"], placed["y"], placed["z"]), abs=1e-9
    )
    wanted = np.array([placed["nx"], placed["ny"], placed["nz"]], dtype=float)
    length = float(np.linalg.norm(wanted))
    got = np.array([back["nx"], back["ny"], back["nz"]], dtype=float)
    if length:
        assert got == pytest.approx(wanted / length, abs=1e-9), "die Richtung kommt normiert zurück"
        # **Der Winkel wird auf dem kürzesten Weg verglichen.** -125 und 235
        # sind dieselbe Lage; ein roher Vergleich hinge an der Schreibweise.
        apart = abs((back["angle"] - placed["angle"] + 180.0) % 360.0 - 180.0)
        assert apart == pytest.approx(0.0, abs=1e-9), (
            f"Winkel {back['angle']} statt {placed['angle']}"
        )
    else:
        # **Der Nullvektor kommt als (0, 0, 1) zurück, und das ist richtig.**
        # Er heißt „behält die aufrechte Lage", und die aufrechte Lage *ist*
        # +Z: Beide Schreibweisen ergeben dieselbe Matrix, und aus ihr lässt
        # sich die eine nicht von der anderen unterscheiden. Umgekehrt wird
        # also die Lage, nicht die Schreibweise.
        assert got == pytest.approx(np.array([0.0, 0.0, 1.0]), abs=1e-12)
        assert back["angle"] == pytest.approx(0.0, abs=1e-12)
