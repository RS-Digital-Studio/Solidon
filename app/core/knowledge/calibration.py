"""Selbstkalibrierung (Bauplan §28.3).

Drei Schritte, und der dritte ist der, auf den es ankommt:

1. einen Prüfkörper drucken — Stifte und Bohrungen mit gestaffeltem Spiel,
   eine Wandstärkenleiter, ein Überhangfächer;
2. ihn ausmessen;
3. **die Werte gehen ins Materialprofil**, nicht in ein Modell.

Weil Toleranzen im Stapel Verweise sind und nie Zahlen (§12, AGENTS.md Regel
7), rechnet danach jedes bestehende Projekt mit den kalibrierten Werten neu.
Das ist der ganze Sinn: einmal kalibrieren richtet jede Passung, die je mit
``auto:petg`` gebaut wurde.

Geschrieben wird in die eigene Profildatei des Nutzers, nie in die
mitgelieferte — der Startbestand bleibt, wie er war, und es bleibt
offensichtlich, aus welcher der beiden eine Zahl kam.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.errors import ValidationError
from app.core.knowledge import profiles
from app.core.knowledge.tables import read_table
from app.core.log import get_logger
from app.core.paths import ensure_dir, user_profiles_dir
from app.core.types import MaterialProfile
from app.i18n import _

_log = get_logger(__name__)

#: Name der Datei, in die die kalibrierten Werte geschrieben werden.
USER_MATERIALS = "materials.toml"

#: Was eine Kalibrierung setzen darf. Alles andere bleibt so, wie das
#: mitgelieferte Profil es hat.
FIELDS: tuple[str, ...] = (
    "clearance",
    "press",
    "hole_compensation",
    "elephant_foot",
    "shrinkage",
)


@dataclass(slots=True)
class Measurement:
    """Ein Messwert für eine Eigenschaft."""

    field: str
    value: float
    note: str = ""


@dataclass(slots=True)
class Calibration:
    """Was an einem Material gemessen wurde."""

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
    """Weist ab, was keine Messung sein kann, bevor irgendetwas geschrieben
    wird.
    """
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
    """Schreibt die gemessenen Werte in das Materialprofil des Nutzers (§28.3).

    Die mitgelieferte Datei wird nie angefasst. Zurück kommt das Profil, wie es
    sich danach liest — kalibriert, und das sagt es auch.
    """
    check(calibration)
    target = (directory or user_profiles_dir()) / USER_MATERIALS
    ensure_dir(target.parent)

    # Die Datei des Nutzers wird für sich gelesen, sie muss also vollständig
    # sein: sie beginnt beim mitgelieferten Profil und nimmt erst dann die
    # gemessenen Werte.
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
    # Die Datei ist zum Lesen — und damit zum Anfassen — gedacht. Ein
    # Tippfehler darin ist ein Satz mit Dateinamen, kein Startabbruch, aus dem
    # nur das Löschen der Datei herausführt (Regel 17).
    return read_table(path, title=_("Die Kalibrierdatei lässt sich nicht lesen."))


def _as_toml(table: dict[str, dict[str, Any]]) -> str:
    """Schreibt die Tabelle zurück. Klein und lesbar — diese Datei ist zum
    Lesen gedacht.
    """
    lines = [
        "# Kalibrierte Materialwerte (Bauplan §28.3).",
        "# Von Solidon geschrieben. Die mitgelieferten Startwerte bleiben unberührt;",
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
        # `json.dumps` erzeugt gültige TOML-Basic-Strings: ein
        # Anführungszeichen im Materialtitel — „PLA "matt"" — machte die
        # Datei sonst unlesbar, und zusammen mit dem Leser darüber war das
        # ein Startabbruch.
        return json.dumps(value, ensure_ascii=False)
    return f"{value}"


def from_measurements(material: str, **values: float) -> Calibration:
    """Bequemlichkeit für Dialog und Tests: benannte Werte hinein,
    Kalibrierung heraus.
    """
    return Calibration(
        material=material,
        measurements=[
            Measurement(field=name, value=float(value)) for name, value in values.items()
        ],
    )
