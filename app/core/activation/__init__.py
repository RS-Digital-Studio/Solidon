"""Freischaltung: Testlauf, Lizenzschlüssel, und wo die Grenze verläuft.

Die Grenze in einem Satz: **was das Dokument ändert oder ein Ergebnis
herausgibt, braucht einen Schlüssel — was nur liest, nicht.** Nach Ablauf des
Testlaufs bleibt Formwerk damit ein vollständiger Betrachter seiner eigenen
Projekte: öffnen, drehen, messen, Prüfbericht lesen, Schichtanalyse ansehen,
speichern, zurücknehmen. Wer nichts mehr ändern kann, kann auch nichts kaputt
speichern; die Freigabe kostet nichts und nimmt dem Ablauf die Härte an der
einen Stelle, an der sie niemandem nützt.

Geprüft wird an vier Stellen, und alle vier liegen im **Datenpfad**, nicht an
der Oberfläche:

======================  ==============================================
``History.apply``       jede Dokumentänderung — nichts schreibt daran
                        vorbei, das ist eine Kernregel
``export.writer``       jeder Export
``export.handover``     Slicer-Übergabe und Druckdatei
``agent.session``       der Chat
======================  ==============================================

Jede holt den Zustand selbst und wirft selbst. Die Oberfläche graut gesperrte
Einträge vorher aus — sie ist Freundlichkeit, nicht die Hürde. Ein Patch an
einem Menüeintrag bringt darum nichts.

Es gibt **keine Hintertür**: keine Umgebungsvariable, keinen Schalter, keine
Freigabedatei. Die Suite setzt den Zustand über eine Fixture, die dieses Modul
patcht — ein eingebauter Umschalter wäre genau das, was ein Angreifer sucht.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from app.core.activation.key import Licence, LicenceKeyError, parse
from app.core.activation.store import (
    TRIAL_DAYS,
    forget_key,
    read_key,
    trial_days_left,
    write_key,
)
from app.core.errors import LicenceRequired
from app.core.log import get_logger

_log = get_logger(__name__)

__all__ = [
    "TRIAL_DAYS",
    "Activation",
    "Licence",
    "LicenceKeyError",
    "LicenceRequired",
    "forget_cache",
    "forget_key",
    "read_key",
    "remember",
    "require",
    "state",
]

#: Die vier Handlungen, die einen Schlüssel brauchen. Der Name reist in die
#: Ausnahme und ins Protokoll — damit sich später sagen lässt, an welcher
#: Grenze Leute tatsächlich anstoßen.
CHANGE: Final = "change"
EXPORT: Final = "export"
SLICER: Final = "slicer"
CHAT: Final = "chat"


@dataclass(frozen=True, slots=True)
class Activation:
    """Der Freischaltzustand dieses Rechners."""

    licence: Licence | None = None
    days_left: int = 0
    """Resttage des Testlaufs. Ohne Belang, sobald eine Lizenz vorliegt."""

    @property
    def unlocked(self) -> bool:
        """Ob die schreibenden Funktionen offenstehen."""
        return self.licence is not None or self.days_left > 0

    @property
    def in_trial(self) -> bool:
        return self.licence is None and self.days_left > 0

    @property
    def expired(self) -> bool:
        return self.licence is None and self.days_left <= 0


_cached: Activation | None = None


def state() -> Activation:
    """Der Zustand, einmal je Prozess ermittelt.

    Gehalten, weil ``History.apply`` bei jeder Änderung fragt und eine
    Signaturprüfung in reinem Python nicht kostenlos ist. Nach dem Eintragen
    eines Schlüssels räumt :func:`forget_cache` ihn weg.
    """
    global _cached
    if _cached is None:
        _cached = _determine()
    return _cached


def forget_cache() -> None:
    """Vergisst den gehaltenen Zustand — nach dem Eintragen eines Schlüssels."""
    global _cached
    _cached = None


def _determine() -> Activation:
    stored = read_key()
    if stored is not None:
        try:
            return Activation(licence=parse(stored))
        except LicenceKeyError as problem:
            # Ein abgelegter Schlüssel, der nicht mehr passt: nach einem
            # Hauptversionswechsel der normale Fall. Der Testlauf entscheidet
            # dann weiter — und der Dialog sagt, was mit dem Schlüssel ist.
            _log.info("stored licence key not accepted: %s", problem.detail)
    return Activation(days_left=trial_days_left())


def remember(text: str) -> Activation:
    """Prüft einen eingegebenen Schlüssel und legt ihn bei Erfolg ab.

    Wirft :class:`LicenceKeyError` mit Grund, wenn er nicht passt — der Dialog
    zeigt den Grund, nicht ein „ungültig".
    """
    parse(text)  # wirft, wenn er nicht passt — abgelegt wird nur Geprüftes
    write_key(text)
    forget_cache()
    return state()


def require(action: str) -> None:
    """Lässt durch oder wirft :class:`LicenceRequired`.

    Die eine Funktion, die alle vier Grenzstellen aufrufen. Sie gibt nichts
    zurück: ein Rückgabewert wäre ein Wahrheitswert, den eine Stelle
    versehentlich ignoriert.
    """
    if not state().unlocked:
        raise LicenceRequired(action=action)
