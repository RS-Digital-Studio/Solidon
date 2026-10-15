"""Längenmaße der Parameterleiste in der Anzeigeeinheit (FD-125, Zwilling der Leiste).

*Parameter anlegen …* zeigt und nimmt eine Länge seit F2b in der eingestellten
Einheit; die Leiste daneben zeigte dieselbe *Breite* weiter in Millimetern,
mit „mm“ in der Einheitenauswahl. Ein Projektmaß der Einheit „mm“ steht jetzt
in einem Längenfeld: außen die Anzeigeeinheit, innen Millimeter
(``labels.LengthSpin``). Gespeichert wird weiter in Millimetern, und ein
unberührtes Feld gibt den gespeicherten Wert ohne Rundungsrest zurück.

Die Einheit steht in der Auswahl neben dem Feld, nicht im Feld — deshalb ohne
Suffix. Die Leiste fragt ihre Felder über die Helfer hier in Millimetern, gleich
ob Länge oder nicht; so bleibt jede Stelle, die Werte liest oder setzt, eine.
"""

from __future__ import annotations

from typing import override

from PySide6.QtWidgets import QDoubleSpinBox

from app.core.units import decimals_for, from_mm
from app.ui.labels import BoundedLengthSpin, LengthSpin, display_unit, localised


def is_length(unit: str | None) -> bool:
    """Ob ein Projektmaß mit dieser Einheit eine Länge ist — „mm“ oder ohne Angabe."""
    return (unit or "mm") == "mm"


class ParameterLengthSpin(BoundedLengthSpin):
    """Ein Längenfeld der Parameterleiste: ohne Suffix, die Einheit steht daneben."""

    @override
    def _apply_unit(self) -> None:
        super()._apply_unit()
        self.setSuffix("")


def value_mm(editor: QDoubleSpinBox) -> float:
    """Der Wert eines Feldes der Leiste in der Einheit des Dokuments."""
    return editor.value_mm() if isinstance(editor, LengthSpin) else float(editor.value())


def set_value_mm(editor: QDoubleSpinBox, value: float) -> None:
    """Setzt einen Wert in der Einheit des Dokuments."""
    if isinstance(editor, LengthSpin):
        editor.set_value_mm(value)
    else:
        editor.setValue(value)


def set_range_mm(editor: QDoubleSpinBox, low: float, high: float) -> None:
    """Grenzen in der Einheit des Dokuments."""
    if isinstance(editor, LengthSpin):
        editor.set_range_mm(low, high)
    else:
        editor.setRange(low, high)


def in_field(editor: QDoubleSpinBox, value: float) -> float:
    """Eine Zahl in der Einheit des Dokuments, wie das Feld sie zeigt."""
    if isinstance(editor, LengthSpin):
        return from_mm(value, display_unit())
    return value


def text_mm(editor: QDoubleSpinBox, value: float) -> str:
    """Eine Zahl in der Einheit des Dokuments in der Schreibweise des Feldes."""
    return str(editor.textFromValue(in_field(editor, value)))


def derived_text(value: float, unit: str | None) -> str:
    """Ein abgeleitetes Maß, wie die Leiste es zeigt — eine Länge in der Anzeigeeinheit."""
    if is_length(unit):
        shown_unit = display_unit()
        return localised(f"{from_mm(value, shown_unit):.{decimals_for(shown_unit)}f}")
    return localised(f"{value:.2f}")
