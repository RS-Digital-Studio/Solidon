"""Der Weg einer Meldung, Schritt für Schritt gegangen (Prüfpunkt 7, V5, FD-36, RM-737).

Eine Meldung, die einen Weg in mehreren Schritten nennt — „Zum Entfernen zuerst
„Abbrechen“ wählen, danach „Merkmal entfernen“.“ (FD-36) —, wurde bisher nur
gelesen: ``way_out`` sagte, dass sie einen Ausweg nennt, und die erste Handlung
einer Meldung im Hausstil wurde geklickt. Ob der zweite Schritt danach frei ist
und wirkt, prüfte niemand. :meth:`WayPhase.walk_ways` geht jeden genannten
Knopf in seiner Folge: Er wartet, bis der Knopf frei dasteht, klickt ihn mit
Probe (``function_walk.click_button``) und hält fest, ob er wirkte — im
Protokoll unter ``messages[].way``.

Gesucht wird zuerst im Fenster der Meldung (dem Hauptfenster, aus dem
``message_entries`` sie liest), dann in den offenen Fenstern daneben. Stehen
dort zwei Knöpfe desselben Titels, wird nicht geraten; bleibt ein Knopf grau
oder fehlt er, ist das eine Messung (``way[n].reason``) und kein Fehler des
Prüfstands (RC2-6) — genau diese Lage soll FD-36 belegen.
"""

from __future__ import annotations

import re
import time
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
#: Gründe in ``way[n].reason``, warum ein Schritt nicht geklickt wurde.
STILL_GREY: Final = "grau"
NOT_THERE: Final = "nicht da"
AMBIGUOUS: Final = "mehrdeutig"
AFTER_MISSED: Final = "der Schritt davor ging nicht"


def way_titles(text: str) -> list[str]:
    """Die Knöpfe, die ein Text der Reihe nach nennt."""
    return TITLE.findall(text)


def titled_buttons(roots: Sequence[Any], title: str) -> list[Any]:
    """Jeder sichtbare Knopf mit diesem Titel, frei oder grau, im Fenster eines der ``roots``."""
    from PySide6.QtWidgets import QAbstractButton

    wanted = title.rstrip(" …").strip()
    return [
        button
        for root in roots
        for button in root.findChildren(QAbstractButton)
        if button.window() is root
        and button.isVisible()
        and button.text().replace("&", "").rstrip(" …").strip() == wanted
    ]


def way_button(window: Any, title: str) -> tuple[Any | None, str]:
    """Der Knopf eines Wegschritts, oder warum keiner eindeutig frei dasteht.

    Zuerst das Fenster der Meldung, dann die offenen Fenster daneben
    (``function_surface.windows_to_picture``). Zwei Treffer am selben Ort:
    :data:`AMBIGUOUS` — welcher gemeint ist, sagt die Meldung nicht.
    """
    for roots in ([window], surfaces.windows_to_picture(window)):
        found = titled_buttons(roots, title)
        if len(found) > 1:
            return None, f"{AMBIGUOUS}: {len(found)} Knöpfe „{title}“"
        if found:
            return (found[0], "") if found[0].isEnabled() else (None, STILL_GREY)
    return None, NOT_THERE


class WayPhase:
    """Der Weg einer Meldung als Teil des Fehlfalls von ``FunctionFlow``."""

    def walk_ways(self: FunctionFlow, messages: Sequence[dict[str, Any]]) -> None:
        """Geht den Weg jeder Meldung mit mindestens zwei genannten Knöpfen.

        Nur, wenn die Meldung einen Ausweg nennt (``way_out``) und keine ihrer
        Handlungen schon geklickt wurde. Je Schritt ``title``, ``clicked`` und
        ``effect`` — Szene anders, ein Fenster offen oder der Knopf weg —, und
        ``reason``, wenn er nicht geklickt wurde.
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
            self.run_steps("weg der meldung", [self.way_step(entry, way) for entry in way])

    def way_step(self: FunctionFlow, entry: dict[str, Any], way: Sequence[dict[str, Any]]) -> Step:
        """Ein Schritt des Wegs: warten, bis der Knopf frei ist, klicken, Wirkung lesen.

        Bleibt er :data:`WAY_STEP_S` grau oder fehlt, steht der Grund im
        Eintrag; die Frist des Automaten liegt darüber, sie trifft den Schritt nie.
        """
        title = str(entry["title"])
        until: list[float] = []

        def missed() -> bool:
            return any(not earlier["clicked"] for earlier in way[: way.index(entry)])

        def ready() -> bool:
            if missed():
                return True
            if not until:
                until.append(time.perf_counter() + WAY_STEP_S)
            button, why = way_button(self.window, title)
            return button is not None or why.startswith(AMBIGUOUS) or time.perf_counter() > until[0]

        def act(machine: StepMachine) -> None:
            if missed():
                entry["reason"] = AFTER_MISSED
                return
            button, why = way_button(self.window, title)
            if button is None:
                entry["reason"] = (
                    why if why.startswith(AMBIGUOUS) else f"nach {WAY_STEP_S:g} s {why}"
                )
                return
            before = self.scene_now()
            dialog_before = surfaces.open_dialog(self.window)
            entry["clicked"] = bool(click_button(self.ports, self.walker, button, title))
            self.pump()
            from shiboken6 import isValid

            # Weg ist der geklickte Knopf selbst — nicht irgendeiner gleichen Titels.
            gone = not isValid(button) or not (button.isVisible() and button.isEnabled())
            opened = surfaces.open_dialog(self.window) is not dialog_before
            changed = compare_prints(before, self.scene_now())["same"] is False
            entry["effect"] = bool(entry["clicked"] and (gone or opened or changed))

        return Step(f"weg: {title}", act, ready=ready, timeout_s=2 * WAY_STEP_S)
