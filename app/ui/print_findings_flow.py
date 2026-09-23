"""Die Schichtanalyse im Prüfbericht, abseits des Oberflächen-Threads (§2.8, §22).

Nach jeder Auswertung fragt dieser Ablauf den Kern, was die Schichtanalyse
über die Körper zu berichten hat (:func:`app.core.slice.findings.print_findings`)
— Inseln, frei hängende Flächen, lange Brücken, die schmalste Stelle, eine
Lage mit weniger Stützen, und was an Material und Drucker hängt. Die
Befunde kommen **nach** dem Bericht der Auswertung: Die Auswertung wird nicht
länger, und was nachkommt, reiht der Bericht mit ``add_findings`` ein.

Ein neuer Stand löst den laufenden ab. Was ein abgelöster Arbeiter noch
liefert, beschreibt eine Szene, die es nicht mehr gibt, und wird verworfen.
"""

from __future__ import annotations

import weakref
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, Signal

from app.core.errors import OperationCancelled
from app.core.log import get_logger
from app.core.scene.cancel import CancelSignal
from app.core.slice.findings import print_findings
from app.core.types import Finding, PrintSettings, Profile
from app.ui.leash import Worker, WorkerLeash

_log = get_logger(__name__)


class _PrintFindingsWorker(Worker):
    """Rechnet die Befunde einer Szene; abbrechbar über ``cancel``."""

    done = Signal(object)

    def __init__(self, scene: Any, profile: Profile, settings: PrintSettings) -> None:
        super().__init__()
        self._scene = scene
        self._profile = profile
        self._settings = settings
        self.cancel = CancelSignal()

    def work(self) -> None:
        try:
            found = print_findings(
                self._scene, self._profile, self._settings, cancelled=self.cancel
            )
        except OperationCancelled:
            return
        if not self.cancel.is_cancelled:
            self.done.emit(found)


class PrintFindingsFlow(QObject):
    """Startet, ersetzt und bricht die Berichtsanalyse ab."""

    found = Signal(object)
    """Die Befunde des aktuellen Stands, als ``list[Finding]``."""

    def __init__(self, parent: QObject, leash: WorkerLeash, is_current: Callable[[Any], bool]):
        super().__init__(parent)
        self._leash = leash
        # Schwach gehalten: Die Frage gehört dem Fenster, und der Ablauf ist
        # sein Kind — eine starke Referenz schlösse einen Ring über den
        # Python-Umschlag, den erst ein GC-Lauf irgendwann auflöst.
        self._is_current = weakref.WeakMethod(is_current)
        self._worker: _PrintFindingsWorker | None = None

    @property
    def worker(self) -> Worker | None:
        """Der laufende Arbeiter — für das Warten beim Schließen."""
        return self._worker

    def start(self, result: Any, profile: Profile, settings: PrintSettings) -> None:
        """Die Befunde für diesen Auswertungsstand rechnen lassen."""
        self.cancel()
        if result is None or not result.scene.objects:
            return
        worker = _PrintFindingsWorker(result.scene, profile, settings)
        worker.done.connect(
            lambda found, result=result, worker=worker: self._arrived(found, result, worker)
        )
        # Eine Ausnahme im Arbeiter ist hier kein Dialog wert: Der Bericht der
        # Auswertung steht, nur die Zusatzzeilen fehlen. Ins Protokoll geht sie
        # über ``Worker.run``.
        worker.crashed.connect(lambda detail: _log.info("print findings failed: %s", detail))
        worker.finished.connect(lambda done=worker: self._finished(done))
        self._worker = worker
        self._leash.start(worker)

    def cancel(self) -> None:
        """Den laufenden Arbeiter anhalten; sein Ergebnis kommt nicht mehr an."""
        if self._worker is not None:
            self._worker.cancel.cancel()
            self._leash.retire(self._worker)
            self._worker = None

    def _arrived(self, found: list[Finding], result: Any, worker: Any) -> None:
        asks = self._is_current()
        if worker is self._worker and asks is not None and asks(result):
            self.found.emit(found)

    def _finished(self, worker: Any) -> None:
        if worker is self._worker:
            self._worker = None
        self._leash.hold_until_done(worker)
