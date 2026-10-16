"""Der Weg einer Meldung, Schritt für Schritt gegangen (Prüfpunkt 7, V5, FD-36, RM-737).

Eine Meldung, die einen Weg in mehreren Schritten nennt — „Zum Entfernen zuerst
„Abbrechen“ wählen, danach „Merkmal entfernen“.“ (FD-36) —, wurde bisher nur
gelesen: ``way_out`` sagte, dass sie einen Ausweg nennt, und die erste Handlung
einer Meldung im Hausstil wurde geklickt. Ob der zweite Schritt danach frei ist
und wirkt, prüfte niemand. :meth:`WayPhase.walk_ways` geht jeden genannten
Knopf in seiner Folge: Er wartet, bis der Knopf frei dasteht, klickt ihn mit
Probe (``function_walk.click_button``) und hält fest, ob er wirkte — im
Protokoll unter ``messages[].way``.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, Final

from tools import function_surface as surfaces
from tools.function_machine import Step, StepMachine
from tools.function_protocol import compare_prints
from tools.function_walk import click_button

if TYPE_CHECKING:
    from tools.function_bench import FunctionFlow

#: Ein Knopf, den eine Meldung beim Namen nennt: in deutschen Anführungszeichen.
TITLE: Final = re.compile(r"„([^“]+)“")
#: Wie lange ein genannter Schritt höchstens braucht, bis sein Knopf frei steht (Sekunden).
WAY_STEP_S: Final = 10.0


def way_titles(text: str) -> list[str]:
    """Die Knöpfe, die ein Text der Reihe nach nennt."""
    return TITLE.findall(text)


def titled_button(title: str) -> Any | None:
    """Ein sichtbarer, freier Knopf mit diesem Titel in einem sichtbaren Fenster."""
    from PySide6.QtWidgets import QAbstractButton, QApplication

    for top in QApplication.topLevelWidgets():
        if not top.isVisible():
            continue
        for button in top.findChildren(QAbstractButton):
            text = button.text().replace("&", "").rstrip(" …").strip()
            if text == title.rstrip(" …").strip() and button.isVisible() and button.isEnabled():
                return button
    return None


class WayPhase:
    """Der Weg einer Meldung als Teil des Fehlfalls von ``FunctionFlow``."""

    def walk_ways(self: FunctionFlow, messages: Sequence[dict[str, Any]]) -> None:
        """Geht den Weg jeder Meldung mit mindestens zwei genannten Knöpfen.

        Nur, wenn die Meldung einen Ausweg nennt (``way_out``) und keine ihrer
        Handlungen schon geklickt wurde. Je Schritt ``title``, ``clicked`` und
        ``effect`` — Szene anders, ein Fenster offen oder der Knopf weg.
        """
        for message in messages:
            titles = way_titles(str(message.get("text") or ""))
            clicked = any(action.get("clicked") for action in message.get("actions", ()))
            if len(titles) < 2 or not message.get("way_out") or clicked:
                continue
            way: list[dict[str, Any]] = [
                {"title": title, "clicked": False, "effect": None} for title in titles
            ]
            message["way"] = way
            steps: list[Step] = []
            for entry in way:
                steps.append(self.way_step(entry))
            self.run_steps("weg der meldung", steps)

    def way_step(self: FunctionFlow, entry: dict[str, Any]) -> Step:
        """Ein Schritt des Wegs: warten, bis der Knopf frei ist, klicken, Wirkung lesen."""
        title = str(entry["title"])

        def act(machine: StepMachine) -> None:
            button = titled_button(title)
            before = self.scene_now()
            dialog_before = surfaces.open_dialog(self.window)
            entry["clicked"] = bool(click_button(self.ports, self.walker, button, title))
            self.pump()
            gone = titled_button(title) is None
            opened = surfaces.open_dialog(self.window) is not dialog_before
            changed = compare_prints(before, self.scene_now())["same"] is False
            entry["effect"] = bool(entry["clicked"] and (gone or opened or changed))

        return Step(
            f"weg: {title}",
            act,
            ready=lambda: titled_button(title) is not None,
            timeout_s=WAY_STEP_S,
        )
