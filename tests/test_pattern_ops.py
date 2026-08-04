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

    result = run("pattern", start, kind="circular", count=6, angle=360.0, axis="z")

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
