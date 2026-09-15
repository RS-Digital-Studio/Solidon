"""Organizer-Geometrie und registrierter Parameterweg gegen den Fachkorpus."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from app.core.geom.mesh import on_surface
from app.core.organizer.build import build_organizer
from app.core.organizer.layout import resolve_layout
from app.core.organizer.serialize import grid_layout, layout_from_text

CASES = json.loads((Path(__file__).parent / "data" / "organizer_layouts.json").read_text("utf-8"))


def test_square_two_cell_body_and_lower_divider_have_independent_volumes():
    spec = grid_layout(1, 2, wall=3, radius=0)
    layout = resolve_layout(spec, {}, width=100, depth=80, height=40, wall=3, floor=4, radius=0)
    result = build_organizer(layout)
    clear_area = (94 - 3) * 74
    assert result.mesh.volume == pytest.approx(100 * 80 * 40 - clear_area * 36)
    assert result.mesh.is_watertight and result.mesh.component_count == 1
    assert result.solver.strategy == "direct"
    assert sum(f.params.get("organizer_role") == "floor" for f in result.features.values()) == 2


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_five_templates_build_closed_with_exact_envelope_and_stable_provenance(case):
    values = case["values"]
    layout = resolve_layout(
        layout_from_text(json.dumps(case["data"])),
        values,
        width=values["width"],
        depth=values["depth"],
        height=values["height"],
        wall=values["wall"],
        floor=values["floor"],
        radius=8,
    )
    first = build_organizer(layout)
    second = build_organizer(layout)
    assert first.mesh.is_watertight and first.mesh.component_count == 1
    assert np.allclose(first.mesh.bounds.size, (values["width"], values["depth"], values["height"]))
    assert np.array_equal(first.mesh.raw.vertices, second.mesh.raw.vertices)
    assert np.array_equal(first.mesh.raw.faces, second.mesh.raw.faces)
    assert all(feature.provenance == "generated" for feature in first.features.values())
    centres = np.asarray([f.params["centre"] for f in first.features.values()])
    _, distance, _ = on_surface(first.mesh.raw, centres)
    assert np.max(distance) < 1e-6
    for wall in layout.walls:
        assert {f"{wall.id}/{side}" for side in ("top", "side_a", "side_b")} <= set(first.features)
