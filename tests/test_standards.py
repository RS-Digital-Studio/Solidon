"""Normteilmaße werden geprüft, bevor sie die Reihenfolge der Auswahl bestimmen."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.errors import ValidationError
from app.core.knowledge import standards


@pytest.mark.parametrize(
    ("table_name", "field", "values"),
    [
        (
            "screws",
            "nominal",
            {
                "nominal": 4.0,
                "clearance": 4.5,
                "tap": 3.3,
                "head": 7.0,
                "head_height": 4.0,
                "countersink": 8.0,
                "hex": 7.0,
                "pitch": 0.7,
            },
        ),
        ("inserts", "hole", {"thread": "M4", "outer": 6.0, "length": 8.0, "hole": 5.0}),
        ("bearings", "inner", {"inner": 5.0, "outer": 10.0, "width": 3.0}),
    ],
)
@pytest.mark.parametrize("invalid", ["5.0", []], ids=["text", "list"])
def test_invalid_leading_dimensions_are_reported_before_sorting(
    tmp_path: Path, table_name: str, field: str, values: dict, invalid: object
) -> None:
    """Ein zweiter Eintrag darf aus dem Profilfehler keinen rohen Sortierfehler machen."""
    path = tmp_path / "standards.toml"
    lines = []
    for name, dimensions in (("invalid", {**values, field: invalid}), ("valid", values)):
        lines.extend([f"[[{table_name}]]", f"size = {json.dumps(name)}"])
        lines.extend(f"{key} = {json.dumps(value)}" for key, value in dimensions.items())
    path.write_text("\n".join(lines), encoding="utf-8")

    with pytest.raises(ValidationError) as caught:
        standards.load(path)

    assert caught.value.field == f"{table_name}.invalid.{field}_number"
    assert caught.value.values["file"] == str(path)
    assert caught.value.suggestions


def test_valid_leading_dimensions_keep_numeric_order_and_name_ties(tmp_path: Path) -> None:
    """Die kleinste passende Größe kommt zuerst, gleiche Maße bleiben stabil sortiert."""
    path = tmp_path / "standards.toml"
    path.write_text(
        "\n".join(
            f'[[bearings]]\nsize = "{name}"\ninner = {inner}\nouter = 12.0\nwidth = 3.0'
            for name, inner in (("large", 9.0), ("second", 5.0), ("first", 5.0))
        ),
        encoding="utf-8",
    )

    assert tuple(standards.load(path).bearings) == ("first", "second", "large")


@pytest.mark.parametrize("value", ['"false"', "0", "[]"])
def test_profile_taper_requires_a_boolean(tmp_path: Path, value: str) -> None:
    """Die Zeichenkette false darf keine konische Nutfeder einschalten."""
    path = tmp_path / "standards.toml"
    source = standards._DATA_FILE.read_text(encoding="utf-8")
    assert "taper_to_slot = true" in source
    path.write_text(
        source.replace("taper_to_slot = true", f"taper_to_slot = {value}", 1), encoding="utf-8"
    )

    with pytest.raises(ValidationError) as caught:
        standards.load(path)

    assert caught.value.field.endswith("taper_to_slot_boolean")
    assert caught.value.suggestions
