"""Ganzzahlfelder in Dreiergruppen — „1 051 736“ statt „1051736“ (FD-124, FD-184).

Eine Anzahl ab vier Stellen schreibt die Anwendung überall in Dreiergruppen
mit geschütztem Leerzeichen (:func:`app.ui.labels.count_text`), in jeder
Sprache dieselbe Schreibweise: Punkt oder Komma als Tausendertrennung hieße in
der Hälfte der Sprachen etwas anderes. Jedes Ganzzahlfeld schreibt genauso und
liest beides — mit und ohne Trennzeichen. ``tests/test_grouped_count_fields.py``
hält fest, dass kein Ganzzahlfeld an diesen Klassen vorbei entsteht.

**Gelesen wird in einem Ganzzahlfeld anders als in einem Zahlenfeld mit
Nachkomma.** :class:`~app.ui.labels.NumberSpin` liest das letzte Trennzeichen
als Dezimalzeichen; im Ganzzahlfeld wurde „2.103.472“ damit 2103,472, also
eine Zahl, die das Feld gar nicht kennt. Hier trennen Leerzeichen zwischen
Ziffern immer Gruppen, Punkt und Komma, wenn genau drei Ziffern folgen.

Drei Bauarten für drei Bedürfnisse: :class:`GroupedSpin` lehnt eine Zahl
jenseits der Grenzen ab (Operationsdialog, Druckeinstellungen, Merkmalfenster),
:class:`GroupedNumberSpin` klemmt wie ein gewöhnliches Zahlenfeld, und
:class:`GroupedIntSpin` ist ein ``QSpinBox`` — wer ``value()`` als ``int``
liest, liest weiter ein ``int``. Eine Kennung (Dreiecksnummer, Startwert,
Port) ist keine Menge und steht ohne Gruppen: :class:`IdentifierSpin` und
:class:`IdentifierIntSpin`.
"""

from __future__ import annotations

import re
from typing import Any, Final, override

from PySide6.QtWidgets import QSpinBox, QWidget

from app.ui.labels import BoundedSpin, NumberSpin, count_text

#: Leerzeichen zwischen zwei Ziffern trennen Gruppen: gewöhnlich, geschützt,
#: schmal und schmal geschützt.
_SPACE_GROUP: Final = re.compile("(?<=\\d)[    ](?=\\d)")

#: Punkt oder Komma vor genau drei Ziffern trennen in einem Ganzzahlfeld Gruppen.
_MARK_GROUP: Final = re.compile(r"(?<=\d)[.,](?=\d{3}(?!\d))")


def whole_text(value: int) -> str:
    """Eine ganze Zahl, wie jedes Ganzzahlfeld sie zeigt."""
    return ("-" if value < 0 else "") + count_text(abs(value))


def ungrouped(text: str, *, whole: bool = True) -> str:
    """Der Text ohne Gruppentrennung — in einer ganzen Zahl auch ohne Punkt und Komma davor."""
    text = _SPACE_GROUP.sub("", text)
    return _MARK_GROUP.sub("", text) if whole else text


class GroupedNumberSpin(NumberSpin):
    """Ein Zahlenfeld für ganze Zahlen in Dreiergruppen; klemmt an den Grenzen wie Qt.

    Steht ohne Nachkommastellen da. Wer später Stellen setzt, bekommt ein
    gewöhnliches Zahlenfeld zurück.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setDecimals(0)
        self.setSingleStep(1.0)

    def _whole(self) -> bool:
        return self.decimals() == 0

    @override
    def textFromValue(self, value: float) -> str:
        if not self._whole():
            return super().textFromValue(value)
        return whole_text(round(value))

    @override
    def _as_shown(self, text: str) -> str:
        return super()._as_shown(ungrouped(text, whole=self._whole()))

    @override
    def _as_grouped(self, text: str) -> str:
        return super()._as_grouped(ungrouped(text, whole=self._whole()))


class GroupedSpin(GroupedNumberSpin, BoundedSpin):
    """:class:`~app.ui.labels.BoundedSpin` für ganze Zahlen, in Dreiergruppen geschrieben."""


class GroupedIntSpin(QSpinBox):
    """Ein ``QSpinBox`` in Dreiergruppen, das beide Schreibweisen liest."""

    @override
    def textFromValue(self, value: int) -> str:
        return whole_text(int(value))

    def _digits(self, text: str) -> str:
        """Die Zahl ohne Vor- und Nachsatz und ohne Gruppen."""
        body = text.strip()
        prefix, suffix = self.prefix(), self.suffix()
        if prefix and body.startswith(prefix):
            body = body[len(prefix) :]
        if suffix and body.endswith(suffix):
            body = body[: -len(suffix)]
        return ungrouped(body.strip())

    @override
    def validate(self, text: str, pos: int) -> Any:
        """Geprüft wird der Text ohne Gruppen; zurück kommt er, wie er getippt wurde."""
        plain = self.prefix() + self._digits(text) + self.suffix()
        checked: Any = super().validate(plain, min(pos, len(plain)))
        return checked[0], text, pos

    @override
    def valueFromText(self, text: str) -> int:
        try:
            return int(self._digits(text))
        except ValueError:
            return int(super().valueFromText(text))


class IdentifierSpin(GroupedSpin):
    """Eine Kennung im Operationsdialog, etwa eine Dreiecksnummer — keine Menge.

    Geschrieben ohne Gruppen, damit sie sich abschreiben lässt wie ein
    Startwert; gelesen wie jedes Ganzzahlfeld, auch mit Gruppen. Welches Feld
    eine Kennung ist, sagt das Schema (``param(identifier=True)``), nicht sein
    Name (Review F2a, R5).
    """

    @override
    def textFromValue(self, value: float) -> str:
        if not self._whole():
            return super().textFromValue(value)
        return str(round(value))


class IdentifierIntSpin(GroupedIntSpin):
    """Eine Kennung als ``QSpinBox``: Startwert, Port. Ohne Gruppen geschrieben —
    Leerzeichen wären beim Abschreiben in die Kommandozeile ein Fehler."""

    @override
    def textFromValue(self, value: int) -> str:
        return str(int(value))
