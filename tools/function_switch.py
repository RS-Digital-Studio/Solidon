"""Der Projektwechsel eines Funktionsfalls: Prüfpunkt 16 (D0-P, RM-737).

Aus ``function_bench`` gelöst, damit der Fall unter der Größengrenze der
Codestruktur bleibt (Regel 6, 2 000 Zeilen). :class:`SwitchPhase` wechselt
während Vorschau, Entwurf und Rechnung über *Datei → Neu* und „Zuletzt
geöffnet“ ins zweite Projekt und hält fest, was danach noch ins neue Projekt
meldet; ``FunctionFlow`` erbt die Phase.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
from typing import Any, Final, Protocol

from tools.function_checks import (
    COVERED,
    NOT_FOUND,
    SWITCH_RUN_OVER,
    SWITCH_WITHOUT_INPUTS,
    SWITCH_WITHOUT_PREVIEW,
)
from tools.function_machine import SETTLE_MS, BenchFinding, Step, StepMachine
from tools.function_protocol import compare_prints, unmeasured
from tools.function_setup import SECOND_SCENE
from tools.function_walk import click_button

#: Wie lange nach einem Abbruch oder Projektwechsel auf späte Ereignisse gewartet wird.
LATE_WINDOW_S: Final = 3.0

#: Die Einträge unter „Zuletzt geöffnet“ auf dem Startbildschirm (Prüfpunkt 16):
#: ``start.recent:<n>``, n ab 1 in der Folge der Liste. Ein Menü dafür gibt es
#: nicht; zum Startbildschirm führt *Datei → Neu* (``MainWindow.new_action``).
RECENT_KIND: Final = "start.recent"


class _Flow(Protocol):
    """Was der Projektwechsel am Funktionsfall braucht (``FunctionFlow``)."""

    window: Any
    session: Any
    ports: Any
    walker: Any
    watch: Any
    data: dict[str, Any]
    spec: dict[str, Any]
    apply_target: str | None

    def run_steps(self, label: str, steps: Sequence[Step], timeout_s: float = ...) -> bool: ...
    def until_step(
        self, name: str, condition: Callable[[], bool], at_most_s: float = ...
    ) -> Step: ...
    def wait_step(self, name: str, ready: Callable[[], bool], timeout_s: float = ...) -> Step: ...
    def path_steps(self) -> list[Step]: ...
    def input_steps(self, inputs: Mapping[str, Any]) -> list[Step]: ...
    def preview_steps(self) -> list[Step]: ...
    def apply_step(self) -> Step: ...
    def expects_preview(self) -> bool: ...
    def reset(self) -> bool: ...
    def scene_path(self, key: str) -> Path | None: ...
    def scene_now(self) -> dict[str, Any]: ...
    def snapshot(self, label: str) -> dict[str, Any]: ...
    def new_project_line(self) -> str: ...
    def idle(self) -> bool: ...
    def recent_number(self, stem: str) -> int | None: ...
    def switch_once(
        self, situation: str, inputs: Mapping[str, Any], new_line: str
    ) -> list[dict[str, Any]] | str: ...
    def on_start_screen(self) -> bool: ...
    def answer_discard(self, machine: StepMachine) -> None: ...


class SwitchPhase:
    """Der Projektwechsel (Prüfpunkt 16) — eine Phase von ``FunctionFlow``."""

    def recent_number(self: _Flow, stem: str) -> int | None:
        """Die Stelle eines Projekts unter „Zuletzt geöffnet“ (ab 1), abgelesen an der Liste."""
        listing = self.window.start_screen.recent_list
        for row in range(listing.count()):
            item = listing.item(row)
            if item is not None and stem in f"{item.text()} {item.toolTip()}":
                return row + 1
        return None

    def phase_switch(self: _Flow) -> None:
        """Prüfpunkt 16: Projektwechsel während Vorschau, Entwurf und Rechnung (Konzept §4).

        Der Weg des Kunden: *Datei → Neu* führt zum Startbildschirm, dort steht
        „Zuletzt geöffnet“ (``start.recent:<n>``); die Stelle des zweiten Projekts
        wird an der Liste abgelesen, wenn sie dasteht. Eine Speicherfrage
        beantwortet der Prüfstand mit *Verwerfen* (:meth:`answer_discard`). Je
        Lage (``function_checks.SWITCH_PHASES``):

        * ``vorschau`` — Eingaben getippt, die Vorschau steht;
        * ``entwurf`` — Eingaben getippt, gewechselt wird sofort, ohne auf die
          Vorschau zu warten;
        * ``rechnung`` — *Übernehmen* geklickt, gewechselt wird, während die
          Sitzung rechnet. War die Rechnung beim ersten Wechselklick schon vorbei,
          hat die Zeile diese Lage nicht (FD-128).

        Spät heißt: Nach dem Wechsel, wenn das neue Projekt steht, kommt binnen
        :data:`LATE_WINDOW_S` noch ein Fenster, eine neue Meldung oder eine
        Änderung am Abdruck des neuen Projekts.
        """
        from tools.function_checks import SWITCH_PHASES

        inputs = self.spec.get("inputs") or {}
        if self.scene_path(SECOND_SCENE) is None:
            unmeasured(self.data, "switch", f"Szene {SECOND_SCENE} fehlt")
            return
        new_line = self.new_project_line()
        if not new_line:
            unmeasured(self.data, "switch", "Datei → Neu trägt keinen Namen im Wortschatz")
            return
        measured: list[str] = []
        late: list[dict[str, Any]] = []
        notes: list[str] = []
        for number, situation in enumerate(SWITCH_PHASES):
            if number and not self.reset():
                notes.append(f"{situation}: Startszene nicht herstellbar")
                continue
            if situation in ("vorschau", "entwurf") and not inputs:
                notes.append(f"{situation}: {SWITCH_WITHOUT_INPUTS}, kein {situation}")
                continue
            if situation == "vorschau" and not self.expects_preview():
                notes.append(f"vorschau: {SWITCH_WITHOUT_PREVIEW}")
                continue
            outcome = self.switch_once(situation, inputs, new_line)
            if isinstance(outcome, str):
                notes.append(f"{situation}: {outcome}")
                continue
            measured.append(situation)
            late += outcome
            if situation == SWITCH_PHASES[0]:
                self.snapshot("after_switch")
        if notes:
            unmeasured(self.data, "switch", "; ".join(notes))
        if measured:
            self.data["switch"] = {"phases": measured, "late_events": late}

    def switch_once(
        self: _Flow, situation: str, inputs: Mapping[str, Any], new_line: str
    ) -> list[dict[str, Any]] | str:
        """Ein Wechsel in einer Lage: die späten Ereignisse, oder warum er nicht gemessen ist."""
        from tools import function_capture as capture

        project = self.session.project
        computing: dict[str, bool | None] = {"busy": None}

        def to_the_recent(machine: StepMachine) -> None:
            number = self.recent_number(SECOND_SCENE)
            if number is None:
                raise BenchFinding(
                    NOT_FOUND,
                    f"{RECENT_KIND}:?",
                    f"{SECOND_SCENE} steht nicht unter „Zuletzt geöffnet“",
                )
            machine.insert([self.walker.step(f"{RECENT_KIND}:{number}")])

        def note_busy(machine: StepMachine) -> None:
            computing["busy"] = bool(self.session.busy)

        steps = [*self.path_steps(), *self.input_steps(inputs)]
        if situation == "vorschau":
            steps += self.preview_steps()
        elif situation == "rechnung":
            if inputs:
                steps += self.preview_steps()
            if self.apply_target:
                steps.append(self.apply_step())
            steps.append(Step("rechnet sie?", note_busy))
        # Die Speicherfrage kann vor dem Startbildschirm kommen (*Datei → Neu*)
        # oder erst beim Öffnen aus „Zuletzt geöffnet“ — beide Stellen bekommen
        # einen Schritt, der sie beantwortet, wenn sie dasteht.
        steps += [
            self.walker.step(f"menu:{new_line}"),
            Step(
                "rückfrage vor dem neuen",
                self.answer_discard,
                ready=lambda: capture.modal_now() is not None or self.on_start_screen(),
            ),
            self.wait_step("startbildschirm", self.on_start_screen),
            Step("liste lesen", to_the_recent, settle_ms=SETTLE_MS),
            Step(
                "rückfrage beim öffnen",
                self.answer_discard,
                ready=lambda: (
                    capture.modal_now() is not None or self.session.project is not project
                ),
            ),
            self.wait_step(
                "anderes projekt", lambda: self.session.project is not project and self.idle()
            ),
        ]
        if not self.run_steps(f"wechsel {situation}", steps):
            return "der Wechsel kam nicht an"
        if situation == "rechnung" and not computing["busy"]:
            # Rechnet die Operation schneller als der Weg zum ersten Wechselklick,
            # gibt es keine Rechnung, in die der Kunde wechseln könnte — diese
            # Lage hat die Zeile nicht, Prüfpunkt 16 verlangt sie nicht (FD-128).
            return SWITCH_RUN_OVER
        self.watch.poll()
        modals_before = len(self.watch.modals)
        print_before = self.scene_now()
        texts_before = {entry["text"] for entry in capture.message_entries(self.window)}
        # Das Spätfenster läuft im Automaten: Ein spätes Fenster bleibt so nicht
        # in einer Schleife ohne Takt hängen, es wird notiert und mit Escape geschlossen.
        self.run_steps(
            f"spät {situation}",
            [self.until_step("spätfenster", lambda: False, at_most_s=LATE_WINDOW_S)],
        )
        self.watch.poll()
        events = [
            {"kind": "fenster", "text": entry["title"], "phase": situation}
            for entry in self.watch.modals[modals_before:]
        ]
        events += [
            {"kind": "meldung", "text": entry["text"], "phase": situation}
            for entry in capture.message_entries(self.window)
            if entry["text"] and entry["text"] not in texts_before
        ]
        changed = compare_prints(print_before, self.scene_now())
        if changed["same"] is False:
            events.append(
                {
                    "kind": "abdruck",
                    "text": f"das neue Projekt änderte sich danach: {changed['differs']}",
                    "phase": situation,
                }
            )
        return events

    def on_start_screen(self: _Flow) -> bool:
        return bool(self.window.stack.currentWidget() is self.window.start_screen)

    def answer_discard(self: _Flow, machine: StepMachine) -> None:
        """Steht die Speicherfrage, klickt der Prüfstand *Verwerfen* — wie der Kunde, der wechselt.

        Die Frage (``confirm_unsaved``, ``confirm_discard``) trägt keinen
        Wortschatznamen (Lücke für W); geklickt wird der Knopf mit der Rolle
        „verwerfen“, mit Probe (:func:`click_button`).
        """
        from PySide6.QtWidgets import QApplication, QMessageBox

        box = QApplication.activeModalWidget()
        if not isinstance(box, QMessageBox):
            return
        discard = next(
            (
                button
                for button in box.buttons()
                if box.buttonRole(button) == QMessageBox.ButtonRole.DestructiveRole
            ),
            None,
        )
        if discard is None:
            raise RuntimeError(f"Rückfrage „{box.windowTitle()}“ ohne Knopf zum Verwerfen")
        if not click_button(self.ports, self.walker, discard, "Verwerfen"):
            raise BenchFinding(COVERED, "Verwerfen", "der Knopf liegt unter etwas anderem")
