"""Ein Ganzzahlfeld in Dreiergruppen — „1 051 736“ statt „1051736“ (FD-124).

Eine Anzahl ab vier Stellen schreibt die Anwendung überall in Dreiergruppen
mit geschütztem Leerzeichen (:func:`app.ui.labels.count_text`), in jeder
Sprache dieselbe Schreibweise: Punkt oder Komma als Tausendertrennung hieße in
der Hälfte der Sprachen etwas anderes. Das Feld schreibt jetzt genauso und
liest beides — mit und ohne Trennzeichen.

**Gelesen wird in einem Ganzzahlfeld anders als in einem Zahlenfeld mit
Nachkomma.** :class:`~app.ui.labels.NumberSpin` liest das letzte Trennzeichen
als Dezimalzeichen; im Ganzzahlfeld wurde „2.103.472“ damit 2103,472, also
eine Zahl, die das Feld gar nicht kennt. Hier trennen Leerzeichen zwischen
Ziffern immer Gruppen, Punkt und Komma, wenn genau drei Ziffern folgen. „1,5“
bleibt, was es ist, und Qt rundet es wie bisher.
"""

from __future__ import annotations

import re
from typing import Final, override

from app.ui.labels import BoundedSpin, count_text

#: Leerzeichen zwischen zwei Ziffern trennen Gruppen: gewöhnlich, geschützt,
#: schmal und schmal geschützt.
_SPACE_GROUP: Final = re.compile(r"(?<=\d)[    ](?=\d)")

#: Punkt oder Komma vor genau drei Ziffern trennen in einem Ganzzahlfeld Gruppen.
_MARK_GROUP: Final = re.compile(r"(?<=\d)[.,](?=\d{3}(?!\d))")


class GroupedSpin(BoundedSpin):
    """:class:`~app.ui.labels.BoundedSpin` für ganze Zahlen, in Dreiergruppen geschrieben.

    Ohne Nachkommastellen gedacht (``setDecimals(0)``); mit Nachkomma verhält
    es sich wie ein gewöhnliches Zahlenfeld.
    """

    def _whole(self) -> bool:
        return self.decimals() == 0

    def _ungrouped(self, text: str) -> str:
        """Der Text ohne Gruppentrennung — im Ganzzahlfeld auch ohne Punkt und Komma davor."""
        text = _SPACE_GROUP.sub("", text)
        return _MARK_GROUP.sub("", text) if self._whole() else text

    @override
    def textFromValue(self, value: float) -> str:
        if not self._whole():
            return super().textFromValue(value)
        whole = round(value)
        return ("-" if whole < 0 else "") + count_text(abs(whole))

    @override
    def _as_shown(self, text: str) -> str:
        return super()._as_shown(self._ungrouped(text))

    @override
    def _as_grouped(self, text: str) -> str:
        return super()._as_grouped(self._ungrouped(text))
