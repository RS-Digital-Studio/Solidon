"""Der Sprachfall: je Fläche eines Pakets die Aufnahmen in einer Sprache (D0-P, RM-737).

:class:`LanguageFlow` geht für jede Zeile eines Pakets bis zu ihrer Fläche
(``FunctionFlow`` mit der Phase ``surface``) und schreibt je Fläche ein
Protokoll unter ``surfaces/``. Vor jeder Fläche steht ein Anfangsvermerk in
``bench.json``; ein Vermerk ohne Ergebnis heißt, der vorige Lauf starb dort, und
die Fläche wird mit diesem Fehler übersprungen (Review M14).

**Jede Fläche beginnt im Ausgangszustand eines frischen Starts** (FD-132): Eine
Fläche kann der nächsten einen aufgeklappten Abschnitt, den sich die Anwendung
merkt, oder eine gerollte Karte hinterlassen; der Weg dorthin erschien dann
kürzer, als er ist. Vor jeder Fläche steht der Prüfbericht vorn, wie nach dem
Öffnen eines Projekts, und was sich darüber hinaus vom Ausgangszustand
unterscheidet (:func:`ground_state`), beendet den Prozess vor dieser Fläche:
``file_acceptance.run`` startet den Fall neu (``function_cases.RESTART_EXIT``), mit
frischem Profil, und er nimmt seine Flächen ab dieser wieder auf.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final

from tools.function_bench import FunctionFlow
from tools.function_machine import MOST_UNSTICKS, SETTLE_MS, Step
from tools.function_protocol import empty_protocol, safe_name, unmeasured
from tools.function_setup import Variant, place_window
from tools.function_surface import without_way

#: Wie viele Ereignisrunden ein Fenster höchstens braucht, um nach vorn zu kommen.
FORWARD_ROUNDS: Final = 50


def ground_state(window: Any) -> tuple[Any, ...]:
    """Was eine Fläche der nächsten hinterlassen kann (FD-132).

    Der Reiter vorn in der rechten Karte, die Abschnitte, deren Zustand sich die
    Anwendung merkt (``UiSettings.open_sections``), und die Rolllage jedes
    Rollbereichs in den Karten. Nach dem Öffnen einer Szene ist nichts gewählt;
    was hier abweicht, stammt von einer vorigen Fläche.
    """
    from PySide6.QtWidgets import QAbstractScrollArea, QWidget

    from app.ui.overlay import CARD

    cards = [widget for widget in window.findChildren(QWidget) if widget.objectName() == CARD]
    rolled = tuple(
        area.verticalScrollBar().value()
        for card in cards
        for area in card.findChildren(QAbstractScrollArea)
    )
    page = window.right.currentWidget()
    return (
        type(page).__name__ if page is not None else "",
        tuple(sorted(window.settings.open_sections.items())),
        rolled,
    )


def bring_forward(widget: Any) -> None:
    """Holt ein Fenster nach vorn, wie der Kunde, der es anklickt, bevor er eine Taste drückt."""
    import time

    from PySide6.QtWidgets import QApplication

    if QApplication.activeWindow() is widget:
        return
    widget.activateWindow()
    for _round in range(FORWARD_ROUNDS):
        QApplication.processEvents()
        if QApplication.activeWindow() is widget:
            return
        time.sleep(0.01)


class LanguageFlow:
    """Ein Sprachfall: je Zeile eines Pakets die Fläche öffnen und ihre Texte messen (Prüfpunkt 9).

    Ein Prozess je Sprache und Paket — sechs Sprachen in einem Prozess brechen
    ab (``tools/CLAUDE.md``). Je Fläche ein Protokoll nach demselben Schema unter
    ``surfaces/<zeile>.json``, mit ``texts`` und ``fields``; was dort steht, wird
    beim nächsten Lauf übersprungen (wieder aufnehmbar je Fläche).
    """

    def __init__(
        self,
        application: Any,
        window: Any,
        folder: Path,
        bench: dict[str, Any],
        persist: Callable[[], None],
        rows: Sequence[Mapping[str, Any]],
        variant: Variant,
        scenes: Path,
        version: Mapping[str, str],
    ) -> None:
        self.application = application
        self.window = window
        self.folder = folder
        self.bench = bench
        self.persist = persist
        self.rows = rows
        self.variant = variant
        self.scenes = scenes
        self.version = version
        #: Der Ausgangszustand nach dem ersten Öffnen in diesem Prozess (FD-132).
        self.pristine: tuple[Any, ...] | None = None

    def grounded(self, flow: FunctionFlow) -> bool:
        """Steht die Fläche im Ausgangszustand eines frischen Starts? (FD-132)

        Nach dem Öffnen eines Projekts steht der Prüfbericht vorn; ließ die vorige
        Fläche die Auswahl vorn, holt ihn ein Klick auf seinen Reiter zurück, wie
        der Kunde es täte (Phase ``ausgangszustand``, kein Teil des Wegs).
        Weicht danach etwas vom ersten Öffnen dieses Prozesses ab, ist die Fläche
        nicht im Ausgangszustand.
        """
        right, report = self.window.right, self.window.report
        if right.isVisible() and right.currentWidget() is not report:
            flow.run_steps("ausgangszustand", [flow.walker.step("report", stop_before_target=True)])
        state = ground_state(self.window)
        if self.pristine is None:
            self.pristine = state
        return state == self.pristine

    def run(self) -> bool:
        """Die Flächen der Zeilen; ``False``, wenn vor einer ein neuer Prozess nötig ist."""
        from tools.file_acceptance import write_json

        surfaces = self.folder / "surfaces"
        done: list[str] = []
        placed = place_window(self.application, self.window, self.variant)
        crashed = str(self.bench.get("surface_started") or "")
        for row in self.rows:
            path = surfaces / f"{safe_name(str(row.get('id', '')))}.json"
            if path.exists():
                done.append(str(row.get("id")))
                continue
            size = [self.window.width(), self.window.height()]
            protocol = empty_protocol(row, self.variant.protocol(placed, size), self.version)
            if crashed and str(row.get("id")) == crashed:
                # Die Fläche, an der der vorige Lauf starb, kommt nicht wieder dran —
                # sonst begänne jeder neue Lauf mit ihr und stürbe wieder (Review M14).
                protocol["errors"].append("Die Fläche brach im vorigen Lauf den Prozess ab")
                unmeasured(protocol, "texts", "abgestürzt")
                write_json(path, protocol)
                done.append(crashed)
                self.bench["surface_started"] = None
                self.persist()
                continue
            unreachable = without_way(row)
            if unreachable:
                # Ohne Szene, die ihren Befund trägt, oder ohne Klick, der ihr Fenster
                # öffnet, erreicht der Fall die Fläche nicht: nicht gelaufen, kein
                # Fund (Probelauf F-32).
                unmeasured(protocol, "texts", unreachable)
                write_json(path, protocol)
                done.append(str(row.get("id")))
                continue
            # Vor jeder Fläche ein Anfangsvermerk; ohne Ergebnis danach war es ein Absturz.
            self.bench["surface_started"] = str(row.get("id"))
            self.persist()
            flow = FunctionFlow(
                self.application,
                self.window,
                self.folder,
                protocol,
                lambda: None,
                row,
                self.variant,
                self.scenes,
                bench=self.bench,
                out=self.folder.parent.parent,
            )
            if flow.reset():
                if not self.grounded(flow):
                    # Die vorige Fläche hat den Ausgangszustand verändert: Diese
                    # beginnt in einem neuen Prozess (FD-132), nichts ist gemessen.
                    self.bench["restart_before"] = str(row.get("id"))
                    self.bench["surfaces_done"] = done
                    self.bench["surface_started"] = None
                    self.persist()
                    return False
                flow.phase_surface()
            cleaned = self.close_surfaces(flow)
            write_json(path, protocol)
            done.append(str(row.get("id")))
            self.bench["surfaces_done"] = done
            self.bench["surface_started"] = None
            self.persist()
            if not cleaned:
                self.bench["surface_cleanup_failed"] = str(row.get("id"))
                self.persist()
                raise RuntimeError("Fenster der vorigen Fläche blieb offen; den Rückweg prüfen")
        self.bench["surfaces_done"] = done
        self.bench.pop("restart_before", None)
        self.persist()
        return True

    def close_surfaces(self, flow: FunctionFlow) -> bool:
        """Rückweg vor dem nächsten Projekt, auch aus nichtmodalen Fenstern.

        Der Schrittautomat löst nur noch laufende modale Aufrufe mit Escape.
        Ein nichtmodaler Generator kehrt sofort zurück und blieb deshalb über
        Projektwechsel sichtbar. Er wird über dieselbe Kundentaste geschlossen;
        bleibt ein Fenster stehen, beginnt keine weitere Messung darin. Escape
        drückt der Kunde in dem Fenster, das vorn steht: Steht das Hauptfenster
        vorn, nimmt seine Taste *Auswahl leeren* den Druck, und der Dialog
        bleibt offen — es wird erst nach vorn geholt.
        """
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest

        from tools.function_surface import windows_to_picture

        for _attempt in range(MOST_UNSTICKS):
            opened = windows_to_picture(self.window)
            if not opened:
                return True
            widget = opened[-1]

            def escape(machine: Any, widget: Any = widget) -> None:
                flow.walker.record(
                    {"target": type(widget).__name__, "key": "Escape", "button": None}
                )
                bring_forward(widget)
                QTest.keyClick(widget, Qt.Key.Key_Escape)

            if not flow.run_steps(
                "rückweg fläche", [Step("fenster verlassen", escape, settle_ms=SETTLE_MS)]
            ):
                break
        remaining = windows_to_picture(self.window)
        if not remaining:
            return True
        names = ", ".join(type(widget).__name__ for widget in remaining)
        flow.data["errors"].append(f"Rückweg der Fläche: Fenster bleibt offen ({names})")
        return False
