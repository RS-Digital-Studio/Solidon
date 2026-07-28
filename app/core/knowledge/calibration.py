"""Self-calibration (Bauplan §28.3).

Three steps, and the third is the one that matters:

1. print a test body — pins and bores with staggered play, a wall thickness
   ladder, an overhang fan;
2. measure it;
3. **the values go into the material profile**, not into a model.

Because tolerances in the stack are references and never numbers (§12,
AGENTS.md rule 7), every existing project recomputes with the calibrated values
afterwards. That is the whole point: calibrating once fixes every fit that was
ever built with ``auto:petg``.

Written into the user's own profile file, never into the shipped one — the
starting set stays as it was, and it stays obvious which of the two a number
came from.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.errors import ValidationError
from app.core.knowledge import profiles
from app.core.log import get_logger
from app.core.paths import ensure_dir, user_profiles_dir
from app.core.types import MaterialProfile
from app.i18n import _

_log = get_logger(__name__)

#: Name of the file the calibrated values are written into.
USER_MATERIALS = "materials.toml"

#: What a calibration may set. Anything else stays as the shipped profile has it.
FIELDS: tuple[str, ...] = (
    "clearance",
    "press",
    "hole_compensation",
    "elephant_foot",
    "shrinkage",
)


@dataclass(slots=True)
class Measurement:
    """One measured value for one property."""

    field: str
    value: float
    note: str = ""


@dataclass(slots=True)
class Calibration:
    """What was measured on one material."""

    material: str
    measurements: list[Measurement] = field(default_factory=list)

    def value(self, name: str) -> float | None:
        for entry in self.measurements:
            if entry.field == name:
                return entry.value
        return None

    def as_table(self) -> dict[str, float]:
        return {entry.field: entry.value for entry in self.measurements}


def check(calibration: Calibration) -> None:
    """Refuse what cannot be a measurement, before anything is written."""
    known = profiles.material_profiles()
    if calibration.material not in known:
        raise ValidationError(
            field="material",
            detail=_("Dieses Materialprofil ist nicht bekannt."),
            values={"requested": calibration.material, "known": ", ".join(sorted(known))},
        )
    for entry in calibration.measurements:
        if entry.field not in FIELDS:
            raise ValidationError(
                field=entry.field,
                detail=_("Dieser Wert gehört nicht ins Materialprofil."),
                values={"field": entry.field, "known": ", ".join(FIELDS)},
            )
        if entry.field != "press" and entry.value < 0.0:
            raise ValidationError(
                field=entry.field,
                detail=_("Ein gemessener Wert kann hier nicht negativ sein."),
                constraint="negative",
                values={"field": entry.field, "value": entry.value},
            )


def apply(calibration: Calibration, directory: Path | None = None) -> MaterialProfile:
    """Write the measured values into the user's material profile (§28.3).

    The shipped file is never touched. What comes back is the profile as it
    reads afterwards — calibrated, and saying so.
    """
    check(calibration)
    target = (directory or user_profiles_dir()) / USER_MATERIALS
    ensure_dir(target.parent)

    # The user's file is read on its own, so it has to be complete: it starts
    # from the shipped profile and only then takes the measured values.
    shipped = profiles.material(calibration.material)
    entry: dict[str, Any] = {
        "title": shipped.title,
        "clearance": shipped.clearance,
        "press": shipped.press,
        "hole_compensation": shipped.hole_compensation,
        "elephant_foot": shipped.elephant_foot,
        "shrinkage": shipped.shrinkage,
    }
    table = _read(target)
    entry.update(table.get(calibration.material, {}))
    entry.update(calibration.as_table())
    entry["calibrated"] = True
    table[calibration.material] = entry

    target.write_text(_as_toml(table), encoding="utf-8")
    profiles.reload()
    _log.info("calibrated %s with %d values", calibration.material, len(calibration.measurements))
    return profiles.material(calibration.material)


def _read(path: Path) -> dict[str, dict[str, Any]]:
    if not path.is_file():
        return {}
    with path.open("rb") as stream:
        return dict(tomllib.load(stream))


def _as_toml(table: dict[str, dict[str, Any]]) -> str:
    """Write the table back. Small and readable — this file is meant to be read."""
    lines = [
        "# Kalibrierte Materialwerte (Bauplan §28.3).",
        "# Von Formwerk geschrieben. Die mitgelieferten Startwerte bleiben unberührt;",
        "# was hier steht, gilt vor ihnen.",
        "",
    ]
    for name, entry in sorted(table.items()):
        lines.append(f"[{name}]")
        for key, value in entry.items():
            lines.append(f"{key} = {_literal(value)}")
        lines.append("")
    return "\n".join(lines)


def _literal(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, str):
        return f'"{value}"'
    return f"{value}"


def from_measurements(material: str, **values: float) -> Calibration:
    """Convenience for the dialog and the tests: named values in, calibration out."""
    return Calibration(
        material=material,
        measurements=[
            Measurement(field=name, value=float(value)) for name, value in values.items()
        ],
    )
