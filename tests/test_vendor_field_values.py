"""Was die Hersteller in ihren Profilen tragen, steht im Druckfeld ungekürzt (FD-197 F1, FD-203).

Die Grundlage des Druckdialogs ist das Herstellerprofil des Slicers. Ein Wert
außerhalb der Feldgrenzen stand dort still gekürzt: 180 % Brückenfluss der
Creality Hi als „150 %“, die 40 000 mm/s² des Sovol Zero als „30000“, die
Leerfahrt 1 200 mm/s des FLSun S1 als „1000“ — Prüfbericht und Slicer nannten
und druckten den echten Wert, und ein Pfeil machte die gekürzte Zahl zur
eigenen Wahl.

Was die Hersteller tragen, steht in ``tests/data/vendor_print_values.json``,
geschrieben von ``tools/scan_vendor_values.py`` aus den installierten Slicern;
die Suite öffnet keine fremde Datei. Die Grenzen decken jeden Wert, der ein
Maß ist; was ein Merkzeichen oder ein Fehler des Profils ist, steht in
:data:`SHOWN_OUTSIDE` und wird ungekürzt gezeigt (``print_fields.shown_range``).
Am gebauten Feld prüft es ``test_bridge_flow_dialog.py``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.core import units
from app.core.knowledge import print_fields
from app.core.knowledge.print_fields import field_of

VENDOR_FILE = Path(__file__).parent / "data" / "vendor_print_values.json"
NOZZLE = "printer.nozzle_diameter"

#: Herstellerwerte jenseits der Grenzen, die kein Maß sind — gezeigt wie sie
#: stehen, die Grenzen bleiben. Schlüssel in Modelleinheit.
SHOWN_OUTSIDE: dict[tuple[str, float], str] = {
    ("shell.bottom_layers", 999.0): "HueForge @LH Stinger: 999 heißt „alles massiv“",
    ("cooling.disable_first_layers", 1000.0): "ABS @iQ TiQ8: 1000 Schichten heißt „nie kühlen“",
    ("cooling.fan_speed", 10.0): "TPU @RH3D: 1000 %, Orca nimmt höchstens 100",
    ("filament.density", 0.0): "Afinia: 0 heißt „unbekannt“",
    ("filament.flow_ratio", 0.1): "Volumic „desactive“: ein abgeschaltetes Profil",
    ("retraction.speed", 0.4): "Bambu ASA @BBL X1 0.6: 0,4 mm/s",
}


def vendor_values() -> dict[str, Any]:
    """Die eingecheckte Liste — geprüft, dass sie den Bestand wirklich trägt."""
    data = json.loads(VENDOR_FILE.read_text(encoding="utf-8"))
    assert set(data["programs"]) >= {
        "orcaslicer",
        "crealityprint",
        "elegooslicer",
        "anycubicslicernext",
        "bambustudio",
        "prusaslicer",
    }
    assert data["files"] > 10_000 and data["values"] > 100_000
    assert len(data["paths"]) >= 50
    return dict(data["paths"])


def vendor_extremes() -> list[tuple[str, float, str]]:
    """Kleinster und größter Herstellerwert je Druckfeld, mit der Datei."""
    return [
        (path, float(entry[end]), str(entry[f"{end}_from"]))
        for path, entry in vendor_values().items()
        if path != NOZZLE
        for end in ("min", "max")
    ]


def _shown_outside(path: str, value: float) -> bool:
    return any(path == key and value == pytest.approx(known) for key, known in SHOWN_OUTSIDE)


@pytest.mark.parametrize(
    ("path", "value", "source"), vendor_extremes(), ids=lambda item: str(item)[:40]
)
def test_every_vendor_value_is_inside_its_field_or_named(
    path: str, value: float, source: str
) -> None:
    field = field_of(path)
    assert field is not None, path
    shown = value * field.factor
    if not _shown_outside(path, value):
        assert field.minimum - 1e-9 <= shown <= field.maximum + 1e-9, (
            f"{path}: {shown:g} {field.unit} aus {source}, Feld {field.minimum:g}…{field.maximum:g}"
        )


def test_every_named_exception_is_really_outside() -> None:
    """Eine Ausnahme, die der Bestand nicht mehr braucht, fällt auf."""
    found = {(path, round(value, 6)) for path, value, _source in vendor_extremes()}
    for (path, value), _reason in SHOWN_OUTSIDE.items():
        field = field_of(path)
        assert field is not None
        assert (path, round(value, 6)) in found, path
        shown = value * field.factor
        assert not field.minimum <= shown <= field.maximum, path
        low, high = print_fields.shown_range(field, value)
        assert low <= shown <= high, path


def test_the_largest_vendor_nozzle_fits_the_nozzle_fields() -> None:
    """Ginger G1 trägt 8 mm; Druckdialog und Ersteinrichtung endeten bei 2 und 10 mm."""
    largest = float(vendor_values()[NOZZLE]["max"])
    assert largest >= 8.0
    assert largest <= units.LARGEST_NOZZLE


def test_the_range_widens_only_to_the_loaded_value() -> None:
    field = field_of("shell.bridge_flow")
    assert field is not None
    assert print_fields.shown_range(field, 0.9) == (50.0, 200.0)
    assert print_fields.shown_range(field, 2.5) == (50.0, pytest.approx(250.0))
    assert print_fields.shown_range(field, 0.3) == (pytest.approx(30.0), 200.0)
    assert print_fields.shown_range(field, None) == (50.0, 200.0)
    assert print_fields.shown_range(field, True) == (50.0, 200.0)


@pytest.mark.parametrize(
    ("path", "value", "source"), vendor_extremes(), ids=lambda item: str(item)[:40]
)
def test_the_built_field_shows_every_vendor_value_whole(
    qt_app: Any, path: str, value: float, source: str
) -> None:
    """Am gebauten Feld des Druckdialogs: der Wert, auf die Stellen des Felds
    gerundet, nicht auf seine Grenze gekürzt — auch nach einem Wert innerhalb."""
    from PySide6.QtWidgets import QWidget

    from app.ui.print_settings_dialog import _make_setting_editor, _set_setting_editor

    field = field_of(path)
    assert field is not None
    holder = QWidget()
    try:
        editor = _make_setting_editor(field, holder, lambda *_args: None)
        decimals = 0 if field.kind == "int" else field.decimals
        # Auf die Stellen des Felds gelegt: Ein halber Schritt rundet Qt anders als Python.
        middle = round((field.minimum + field.maximum) / 2.0, decimals) / field.factor
        for loaded in (value, middle, value):
            _set_setting_editor(editor, field, int(loaded) if field.kind == "int" else loaded)
            expected = round(
                (int(loaded) if field.kind == "int" else loaded) * field.factor, decimals
            )
            assert editor.value() == pytest.approx(expected), f"{path} aus {source}"  # type: ignore[attr-defined]
            # Ein Wert über null steht nicht als null da: 0,4 mm/s Rückzug der
            # Bambu ASA wären bei null Stellen „0 mm/s“ (Nachprüfung R2-4).
            assert loaded == 0 or editor.value() != 0, f"{path} aus {source}"  # type: ignore[attr-defined]
            if loaded is middle:
                # Nach einem Wert innerhalb gilt wieder die Spanne des Felds
                # (Nachprüfung R2-3); der Raft-Abstand trägt seinen Sonderwert
                # eine Anzeigestufe tiefer.
                low = field.minimum - (10.0**-decimals if path == "adhesion.raft_gap" else 0.0)
                assert editor.minimum() == pytest.approx(low), path  # type: ignore[attr-defined]
                assert editor.maximum() == pytest.approx(field.maximum), path  # type: ignore[attr-defined]
    finally:
        holder.deleteLater()
