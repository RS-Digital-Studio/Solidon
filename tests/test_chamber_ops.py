"""Kammer ändern: Innenmaß und Tiefe einer Kammer, einer Nut oder eines Kanals als Ganzes.

Die Sollwerte folgen aus der Konstruktion: Ein Kasten 40 × 30 × 20 mit 2 mm
Wand und Boden hat innen 36 × 26 × 18; wird er innen 1 mm breiter, fehlen
genau 1 × 26 × 18 mm³ Material, und außen bleibt er 40 × 30 × 20.
"""

from __future__ import annotations

import math

import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import GeometryError
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData, signed_volume
from app.core.knowledge import profiles
from app.core.perceive.features import detect
from app.core.perceive.groups import FunctionalGroup, functional_groups
from app.core.registry import REGISTRY
from tests.helpers import feature_operation, walled_bin

load_operations()


def _box(size: tuple[float, float, float], centre: tuple[float, float, float]) -> MeshData:
    body = trimesh.creation.box(extents=size)
    body.apply_translation(centre)
    return MeshData.of(body)


def _minus(body: MeshData, *tools: MeshData) -> MeshData:
    for tool in tools:
        body = boolean("difference", [body, tool]).mesh
    return body


def _bin() -> MeshData:
    return walled_bin()


def _group(mesh: MeshData) -> tuple[dict[str, object], FunctionalGroup]:
    features = detect(mesh)
    group = next(
        entry for entry in functional_groups(features, mesh) if entry.kind in ("chamber", "channel")
    )
    return dict(features), group


def _resize(mesh: MeshData, **values: float) -> tuple[MeshData, list[object]]:
    """*Kammer ändern* über den registrierten Kundenvertrag, am Boden der Kammer."""
    features, group = _group(mesh)
    result = feature_operation(
        "resize_chamber",
        mesh,
        features,  # type: ignore[arg-type]
        features[group.anchor],  # type: ignore[arg-type]
        profiles.make_profile("centauri-carbon-2", "petg"),
        **values,
    )
    return result.outputs[0].mesh, list(result.findings)  # type: ignore[return-value]


def _measures(mesh: MeshData) -> dict[str, float]:
    _features, group = _group(mesh)
    return {entry.name: entry.value for entry in group.measures}


def _width_axis_is_x(mesh: MeshData) -> bool:
    measures = _measures(mesh)
    return measures["width"] == pytest.approx(36.0, abs=1e-6)


def test_a_wider_chamber_keeps_its_outside_and_loses_exactly_the_strip() -> None:
    """36 → 37 innen: 1 × 26 × 18 = 468 mm³ weniger, außen weiter 40 × 30 × 20."""
    mesh = _bin()
    wide_axis = "width" if _width_axis_is_x(mesh) else "length"
    changed, _findings = _resize(mesh, **{wide_axis: 37.0})
    assert signed_volume(changed.raw) == pytest.approx(signed_volume(mesh.raw) - 468.0, abs=1e-6)
    assert tuple(changed.bounds.minimum) == pytest.approx((-20.0, -15.0, 0.0), abs=1e-9)
    assert tuple(changed.bounds.maximum) == pytest.approx((20.0, 15.0, 20.0), abs=1e-9)
    assert changed.raw.is_watertight
    assert _measures(changed)[wide_axis] == pytest.approx(37.0, abs=1e-6)


def test_a_smaller_chamber_fills_in_both_directions() -> None:
    """36 × 26 → 34 × 24: (936 − 816) × 18 = 2160 mm³ mehr Material."""
    mesh = _bin()
    names = ("width", "length") if _width_axis_is_x(mesh) else ("length", "width")
    changed, _findings = _resize(mesh, **{names[0]: 34.0, names[1]: 24.0})
    assert signed_volume(changed.raw) == pytest.approx(signed_volume(mesh.raw) + 2160.0, abs=1e-6)
    measures = _measures(changed)
    assert measures[names[0]] == pytest.approx(34.0, abs=1e-6)
    assert measures[names[1]] == pytest.approx(24.0, abs=1e-6)


@pytest.mark.parametrize(("depth", "change"), [(16.0, 2.0 * 936.0), (19.0, -936.0)])
def test_the_floor_moves_and_the_rim_stays(depth: float, change: float) -> None:
    """Tiefe 18 → 16 füllt 2 × 36 × 26, Tiefe 19 trägt 1 × 36 × 26 vom Boden ab."""
    mesh = _bin()
    changed, _findings = _resize(mesh, depth=depth)
    assert signed_volume(changed.raw) == pytest.approx(signed_volume(mesh.raw) + change, abs=1e-6)
    assert _measures(changed)["depth"] == pytest.approx(depth, abs=1e-6)
    assert float(changed.bounds.maximum[2]) == pytest.approx(20.0, abs=1e-9)


def test_a_wall_that_would_break_through_is_refused() -> None:
    """Innen 41 bei außen 40: Die Wand bräche durch — eine Absage mit Weg, kein Loch."""
    mesh = _bin()
    wide_axis = "width" if _width_axis_is_x(mesh) else "length"
    with pytest.raises(GeometryError) as raised:
        _resize(mesh, **{wide_axis: 41.0})
    assert "durchbrechen" in str(raised.value.detail)
    assert raised.value.suggestions


def test_a_chamber_cannot_shrink_past_what_stands_in_it() -> None:
    """Ein Ablaufloch neben der Mitte: Weiter als bis zur Lücke daneben geht es nicht.

    Gestreckt wird in der größten Lücke zwischen den Ecken (zwischen der linken
    Wand bei −18 und dem Loch bei 4,5); verkleinert wird höchstens um sie, sonst
    kämen die Hälften einander in die Quere — eine Absage, kein verdrehter Körper.
    """
    hole = trimesh.creation.cylinder(radius=1.5, height=6.0, sections=32)
    hole.apply_translation((6.0, 0.0, 1.0))
    drained = _minus(_bin(), MeshData.of(hole))
    names = ("width", "length") if _width_axis_is_x(drained) else ("length", "width")
    with pytest.raises(GeometryError) as raised:
        _resize(drained, **{names[0]: 6.0})
    assert "verkleinern" in str(raised.value.detail)
    narrower, _findings = _resize(drained, **{names[0]: 30.0})
    assert _measures(narrower)[names[0]] == pytest.approx(30.0, abs=1e-6)


def test_nothing_to_change_says_so() -> None:
    """Alle drei Felder auf dem gemessenen Wert: Die Operation sagt, dass nichts geschieht."""
    mesh = _bin()
    measures = _measures(mesh)
    with pytest.raises(GeometryError) as raised:
        _resize(mesh, **measures)
    assert "nichts" in str(raised.value.detail)


def test_a_face_without_a_chamber_is_refused() -> None:
    """Die Oberseite eines Blocks gehört zu keiner Kammer — der Satz nennt den Weg."""
    block = _box((20.0, 20.0, 10.0), (0.0, 0.0, 5.0))
    features = detect(block)
    top = next(
        entry
        for entry in features.values()
        if entry.kind == "face" and float(entry.params["centre"][2]) > 9.0
    )
    with pytest.raises(GeometryError) as raised:
        feature_operation(
            "resize_chamber",
            block,
            dict(features),
            top,
            profiles.make_profile("centauri-carbon-2", "petg"),
            width=10.0,
        )
    assert "weder zu einer erkannten Kammer" in str(raised.value.detail)


def test_a_round_groove_widens_radially() -> None:
    """Ringnut 20 bis 24 mm, 3 tief: auf 5 breit sind es 19,5 bis 24,5 — π·44·3 mm³ mehr Luft."""
    ring = boolean(
        "difference",
        [
            MeshData.of(_cylinder(24.0, 3.0, 8.5)),
            MeshData.of(_cylinder(20.0, 3.2, 8.5)),
        ],
    ).mesh
    plate = _minus(_box((60.0, 60.0, 10.0), (0.0, 0.0, 5.0)), ring)
    changed, _findings = _resize(plate, width=5.0)
    removed = signed_volume(plate.raw) - signed_volume(changed.raw)
    assert removed == pytest.approx(math.pi * 44.0 * 3.0, rel=0.01)
    assert _measures(changed)["width"] == pytest.approx(5.0, abs=0.03)


def _cylinder(radius: float, height: float, z: float) -> trimesh.Trimesh:
    body = trimesh.creation.cylinder(radius=radius, height=height, sections=96)
    body.apply_translation((0.0, 0.0, z))
    return body


def test_a_simple_trough_moves_its_two_walls() -> None:
    """Kanal 26 breit, 18 tief, 100 lang: auf 28 breit fehlen 2 × 18 × 100 mm³."""
    trough = _minus(
        _box((100.0, 30.0, 20.0), (0.0, 0.0, 10.0)), _box((120.0, 26.0, 20.0), (0.0, 0.0, 12.0))
    )
    changed, _findings = _resize(trough, width=28.0)
    assert signed_volume(changed.raw) == pytest.approx(signed_volume(trough.raw) - 3600.0, abs=1e-6)
    assert _measures(changed)["width"] == pytest.approx(28.0, abs=1e-6)


def test_a_notched_rim_is_refused_with_the_way_on() -> None:
    """Eine Aussparung im Rand: als Ganzes nicht streckbar, der Satz nennt „Fläche versetzen“."""
    notched = _minus(_bin(), _box((10.0, 4.0, 10.0), (0.0, 14.0, 20.0)))
    with pytest.raises(GeometryError) as raised:
        _resize(notched, width=37.0)
    assert "Fläche versetzen" in str(raised.value.detail)


def test_the_operation_is_registered_for_faces_with_its_fields() -> None:
    """Ein Eintrag, drei Maße, das Merkmal als Verweis — vollständig wie jede Operation."""
    spec = REGISTRY.get("resize_chamber")
    assert spec.applies_to == ("face",)
    names = [entry.name for entry in spec.params.spec()]
    assert names == ["at_feature", "width", "length", "depth"]
