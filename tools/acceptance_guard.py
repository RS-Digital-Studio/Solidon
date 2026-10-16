"""Gesamtfrist und Siegel eines Laufs von ``file_acceptance.py run`` (Schlusslauf, Werkzeug 6).

``run`` hatte je Fall eine Frist (mindestens 1 800 s je Funktions-, 3 600 s je
Sprachfall), aber keine für den ganzen Lauf: Ein Lauf über alle Fälle konnte
eine Nacht und den nächsten Tag dauern, ohne dass jemand eine Grenze gesetzt
hatte. Und das Siegel der nativen Läufe (``native_binding``) prüfte nur der
Aufseher vor und nach einem Einzelfall — ein ``run`` über viele Fälle prüfte
nichts, während der Baum unter ihm sich ändern konnte.

:class:`RunGuard` hält beides, ohne den Lauf umzubauen: ``--total`` ist die
Gesamtfrist in Sekunden — kein neuer Fall beginnt danach, und jeder Fall
bekommt höchstens die verbleibende Zeit —, ``--binding`` die Bindung, deren
Stand vor jedem Fall noch gelten muss. Bricht eines davon, endet der Lauf mit
dem Grund und dem nächsten Schritt (Regel 17); was gelaufen ist, bleibt.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tools import native_binding
from tools.native_binding import SealError

#: Weniger Restzeit als das beginnt keinen Fall mehr: Er würde nur abgebrochen.
SHORTEST_CASE_S = 60.0


class RunGuard:
    """Gesamtfrist und Siegel über die Fälle eines Laufs."""

    def __init__(
        self,
        total_s: float | None = None,
        binding: Path | None = None,
        clock: Callable[[], float] = time.monotonic,
        root: Path = native_binding.ROOT,
    ) -> None:
        if total_s is not None and not total_s > 0:
            raise ValueError(f"Gesamtfrist {total_s} s ist nicht positiv")
        self.total_s = total_s
        self.binding: dict[str, Any] | None = (
            native_binding.read_binding(binding) if binding is not None else None
        )
        self.clock = clock
        self.root = root
        self.began = clock()

    def remaining(self) -> float | None:
        """Was von der Gesamtfrist übrig ist; ``None`` ohne Gesamtfrist."""
        if self.total_s is None:
            return None
        return self.total_s - (self.clock() - self.began)

    def stop_reason(self) -> str:
        """Warum der nächste Fall nicht beginnt — leer, wenn er beginnen darf."""
        left = self.remaining()
        if left is not None and left < SHORTEST_CASE_S:
            return (
                f"Gesamtfrist {self.total_s:g} s abgelaufen (Rest {max(left, 0.0):.0f} s);"
                " die übrigen Fälle laufen nicht."
                "\nHandlungsvorschlag: Setzen Sie den Lauf mit `run --first <nächster Fall>`"
                " fort oder geben Sie eine längere `--total`."
            )
        if self.binding is not None:
            try:
                native_binding.verify(self.binding, self.root)
            except SealError as problem:
                return str(problem)
        return ""

    def case_limit(self, wanted: float) -> float:
        """Die Frist eines Falls: seine eigene, höchstens die verbleibende Gesamtzeit."""
        left = self.remaining()
        return wanted if left is None else min(wanted, left)
