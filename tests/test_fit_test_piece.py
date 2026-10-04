"""Prüfausschnitt einer Passung (RM-184, Audit §8 „Prüfausschnitt einer Passung“).

*Prüfstück erzeugen* schnitt einen Würfel aus **einem** Teil. Eine Passung hat
zwei: Dose und Deckel, Bohrung und Zapfen. Der Ausschnitt nimmt beide mit
demselben Fenster, sagt das Spiel, das im Ausschnitt zwischen ihnen steht, und
legt sie nebeneinander aufs Bett — gedruckt werden beide, gesteckt wird von Hand.
"""

from __future__ import annotations

from typing import Any

import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData
from app.core.registry import REGISTRY, VARIABLE
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, Profile, Scene, SceneObject

#: Bohrung Ø 10,4 in einer Platte, Zapfen Ø 10 darin: 0,2 mm Luft je Seite.
BORE = 10.4
PIN = 10.0


def _plate_and_pin() -> tuple[SceneObject, SceneObject]:
    plate = trimesh.creation.box(extents=(60.0, 40.0, 12.0))
    plate.apply_translation((0.0, 0.0, 6.0))
    bore = trimesh.creation.cylinder(radius=BORE / 2.0, height=40.0, sections=128)
    plate = trimesh.boolean.difference([plate, bore])
    pin = trimesh.creation.cylinder(radius=PIN / 2.0, height=30.0, sections=128)
    pin.apply_translation((0.0, 0.0, 9.0))
    return (
        SceneObject(id="obj_1", name="Platte", mesh=MeshData.of(plate)),
        SceneObject(id="obj_2", name="Zapfen", mesh=MeshData.of(pin)),
    )


def _run(entries: list[SceneObject], profile: Profile, **params: object) -> Any:
    spec = REGISTRY.get("test_piece")
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry for entry in entries}),
            inputs=entries,
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def test_the_test_piece_takes_every_chosen_part_of_a_fit() -> None:
    spec = REGISTRY.get("test_piece")
    assert spec.consumes == VARIABLE and spec.minimum_inputs == 1
    assert spec.produces == VARIABLE, "ein Stück je Teil, und die Teile bleiben dieselben"


def test_both_halves_of_a_fit_come_out_of_one_window(profile: Profile) -> None:
    """Platte und Zapfen: ein Fenster an der engsten Stelle, zwei Stücke, das Spiel genannt."""
    plate, pin = _plate_and_pin()
    result = _run([plate, pin], profile, size=18.0, spot="closest", on_bed=True)

    assert [entry.id for entry in result.outputs] == ["obj_1", "obj_2"]
    first, second = (entry.mesh for entry in result.outputs)
    assert first.is_watertight and second.is_watertight
    assert first.volume < plate.mesh.volume and second.volume < pin.mesh.volume
    assert first.volume > 0.0 and second.volume > 0.0
    # Die engste Stelle liegt am Mantel der Bohrung.
    x, y, z = (result.answered[key] for key in ("x", "y", "z"))
    assert result.answered["spot"] == "point", "die Stelle wird einmal festgehalten"
    assert 4.8 <= (x * x + y * y) ** 0.5 <= 5.6, (x, y)
    assert 0.0 <= z <= 12.0

    gap = next(finding for finding in result.findings if finding.code == "prepare.test_piece_gap")
    assert gap.values["gap_mm"] == pytest.approx((BORE - PIN) / 2.0, abs=0.03)
    assert "0.2" in str(gap.message), "das Spiel steht im Satz"

    # Beide aufs Bett, nebeneinander, ohne sich zu berühren.
    assert first.bounds.minimum[2] == pytest.approx(0.0, abs=1e-9)
    assert second.bounds.minimum[2] == pytest.approx(0.0, abs=1e-9)
    assert second.bounds.minimum[0] >= first.bounds.maximum[0] + 1.0


def test_a_window_that_misses_one_part_names_it(profile: Profile) -> None:
    plate, pin = _plate_and_pin()
    with pytest.raises(ValidationError) as problem:
        _run([plate, pin], profile, size=8.0, x=24.0, y=0.0, z=6.0)
    assert problem.value.constraint == "empty"
    assert "Zapfen" in str(problem.value.values.get("object", "")), problem.value.values


def test_the_closest_spot_needs_two_parts(profile: Profile) -> None:
    plate, _pin = _plate_and_pin()
    with pytest.raises(ValidationError) as problem:
        _run([plate], profile, size=10.0, spot="closest")
    assert problem.value.constraint == "one_part"


def test_parts_that_overlap_in_the_window_say_so(profile: Profile) -> None:
    """Ein Zapfen dicker als die Bohrung: Das Stück zeigt die Überschneidung, nicht ein Spiel."""
    plate, _pin = _plate_and_pin()
    thick = trimesh.creation.cylinder(radius=5.4, height=30.0, sections=128)
    thick.apply_translation((0.0, 0.0, 9.0))
    pressed = SceneObject(id="obj_2", name="Zapfen", mesh=MeshData.of(thick))
    result = _run([plate, pressed], profile, size=18.0, spot="closest", on_bed=False)
    codes = {finding.code for finding in result.findings}
    assert "prepare.test_piece_overlap" in codes, codes
    assert "prepare.test_piece_gap" not in codes
