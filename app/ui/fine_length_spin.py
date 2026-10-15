"""Ein Längenfeld für Feinmaße — eine Stelle mehr, als die Einheit sonst zeigt (FD-176).

Spiel, Übermaß, Lochkorrektur und Elefantenfuß leben unter einem Millimeter,
und ihre dritte Stelle unterscheidet zwei Messungen (0,075 und 0,08 mm). Ein
gewöhnliches :class:`~app.ui.labels.LengthSpin` zeigt in Millimetern zwei
Stellen und in Zoll vier (``units.decimals_for``); mit ihm hätte *Material
kalibrieren* die Zollanzeige zwar befolgt, die gemessene dritte Stelle aber
beim Öffnen gerundet. Dieselbe Feinheitsregel wie im Operationsdialog
(``op_dialog._decimals_for``): eine Stelle mehr — 0,075 mm, 0,00295 in.
"""

from __future__ import annotations

from typing import Final, override

from app.core.units import decimals_for, from_mm
from app.ui.labels import LengthSpin

#: So viele Stellen mehr als die Einheit sonst zeigt.
FINE_PLACES: Final = 1


class FineLengthSpin(LengthSpin):
    """:class:`~app.ui.labels.LengthSpin` mit einer Nachkommastelle mehr; innen Millimeter."""

    @override
    def _apply_unit(self) -> None:
        super()._apply_unit()
        # Erst die Feinheit, dann die Grenzen noch einmal: Qt schneidet eine
        # Grenze auf die Stellenzahl zu, die beim Setzen galt.
        self.setDecimals(decimals_for(self._unit) + FINE_PLACES)
        low, high = (from_mm(value, self._unit) for value in self._bounds_mm)
        self.setRange(low, high)
