"""Fachmaße, Grenzen und Bezüge der fünf Organizer-Vorlagen."""

from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

from app.core.errors import AppError, ValidationError
from app.core.organizer.layout import resolve_layout
from app.core.organizer.serialize import layout_from_text, layout_references, layout_to_text

CASES = json.loads((Path(__file__).parent / "data" / "organizer_layouts.json").read_text("utf-8"))


def resolve(case, **changes):
    """Die Referenzwerte mit einzeln veränderten Außenmaßen auswerten."""
    values = {**case["values"], **changes}
    return resolve_layout(
        layout_from_text(json.dumps(case["data"])),
        values,
        width=values["width"],
        depth=values["depth"],
        height=values["height"],
        wall=values["wall"],
        floor=values["floor"],
        radius=8,
    )


@pytest.mark.parametrize("case", CASES, ids=lambda case: case["name"])
def test_five_original_layouts_keep_clear_sizes_low_wall_and_module_feet(case):
    layout = resolve(case)
    assert len(layout.cells) == 6
    assert len(layout.walls) == 5
    assert np.allclose([cell.rect.size for cell in layout.cells], case["expected_sizes"])
    assert layout.width == pytest.approx(case["values"]["width"])
    assert layout.depth == pytest.approx(case["values"]["depth"])
    low = [wall for wall in layout.walls if wall.height < layout.height]
    assert len(low) == 1
    assert low[0].height == pytest.approx(case["values"]["divider_h"])
    assert low[0].radius == pytest.approx(case["values"]["divider_opening_radius"])
    feet = layout.foot_positions(12, each_cell=case["expected_feet"] == 24)
    assert len(feet) == case["expected_feet"]
    assert len(set(feet)) == len(feet)
    assert layout == resolve(case)


def test_outer_resize_changes_cell_sizes_positions_but_not_their_ids():
    before, after = resolve(CASES[0]), resolve(CASES[0], width=200)
    assert after.width == pytest.approx(200)
    assert [cell.id for cell in before.cells] == [cell.id for cell in after.cells]
    assert [cell.rect for cell in before.cells] != [cell.rect for cell in after.cells]
    assert before.foot_positions(12) != after.foot_positions(12)
    assert [wall.height for wall in before.walls] == [wall.height for wall in after.walls]


def test_inner_basis_derives_outer_dimensions_and_rejects_incompatible_siblings():
    case = copy.deepcopy(CASES[0])
    case["data"]["basis"] = "inner"
    assert resolve(case, width=999, depth=999).width == pytest.approx(180)
    case["values"]["right_width"] += 20
    with pytest.raises(ValidationError):
        resolve(case)


def test_repeat_parameter_changes_count_and_keeps_surviving_ids():
    before, after = resolve(CASES[0]), resolve(CASES[0], back_columns=4)
    assert len(after.cells) == 7
    assert {cell.id for cell in before.cells} <= {cell.id for cell in after.cells}
    assert sum(cell.rect.width for cell in after.cells[-4:]) + 9 == pytest.approx(174)


def test_nested_parameters_are_collected_and_roundtrip_preserves_every_expression():
    text = json.dumps(CASES[0]["data"])
    parsed = layout_from_text(text)
    assert layout_from_text(layout_to_text(parsed)) == parsed
    assert {"row_depth", "left_width", "divider_h", "back_columns"} <= layout_references(text)
    assert layout_references("{broken") == frozenset()
    with pytest.raises(ValidationError):
        layout_references("{broken", strict=True)


@pytest.mark.parametrize("value", [0, -1, 1.5, 257, float("inf"), True])
def test_count_boundaries_are_checked_before_expansion(value):
    with pytest.raises(AppError):
        resolve(CASES[0], back_columns=value)


@pytest.mark.parametrize(
    "change",
    [
        {"extra": "ignored?"},
        {"version": 99},
        {"basis": "guess"},
        {"layout": []},
    ],
)
def test_unknown_or_damaged_structure_is_not_silently_accepted(change):
    with pytest.raises(ValidationError):
        layout_from_text(json.dumps({**CASES[0]["data"], **change}))


def test_duplicate_ids_code_strings_and_too_deep_layout_are_rejected():
    case = copy.deepcopy(CASES[0]["data"])
    case["layout"]["children"][1]["id"] = "front_back"
    with pytest.raises(ValidationError):
        layout_from_text(json.dumps(case))
    case = copy.deepcopy(CASES[0]["data"])
    case["layout"]["wall"] = "=__import__('os')"
    with pytest.raises(AppError):
        layout_from_text(json.dumps(case))
    for index in range(20):
        case = {
            "kind": "repeat",
            "id": f"deep{index}",
            "axis": "x",
            "wall": 1,
            "count": 1,
            "child": case,
            "heights": {},
            "opening_radius": 0,
        }
    with pytest.raises(ValidationError):
        layout_from_text(json.dumps({"version": 1, "basis": "outer", "layout": case}))


def test_low_wall_cannot_drop_below_floor_or_exceed_outer_height():
    for height in (3, 161):
        with pytest.raises(ValidationError):
            resolve(CASES[0], divider_h=height)
    assert min(w.height for w in resolve(CASES[0], divider_h=4).walls) == pytest.approx(4)


def test_one_repeated_wall_height_keeps_its_parameter_when_count_temporarily_shrinks():
    case = copy.deepcopy(CASES[0])
    identifier = next(w.id for w in resolve(case).walls if "back_row/wall_2" in w.id)
    case["data"]["wall_heights"] = {identifier: "=@individual_height"}
    case["values"]["individual_height"] = 42
    layout = resolve(case)
    assert next(w.height for w in layout.walls if w.id == identifier) == pytest.approx(42)
    assert "individual_height" in layout_references(json.dumps(case["data"]), strict=True)
    assert resolve(case, back_columns=2).inactive_heights == (identifier,)
    assert resolve(case) == layout


@pytest.mark.parametrize(
    "key",
    [
        "root/wall_wrong",
        "root/wall_0",
        "root/wall_32",
        "root/01/wall_1",
        "root/" + "1" * 4500 + "/wall_1",
    ],
)
def test_malformed_wall_identifiers_are_rejected_as_actionable_errors(key):
    case = copy.deepcopy(CASES[0]["data"])
    case["wall_heights"] = {key: 30}
    with pytest.raises(ValidationError):
        layout_from_text(json.dumps(case))


def test_huge_wall_index_does_not_escape_the_layout_error_contract():
    case = copy.deepcopy(CASES[0]["data"])
    case["layout"]["heights"] = {"1" * 4500: 30}
    with pytest.raises(ValidationError):
        layout_from_text(json.dumps(case))
