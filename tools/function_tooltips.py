"""Der Grund eines grauen Bedienelements als eigenes Bild (RM-737, FD-149).

Ein grauer Knopf sagt seinen Sperrgrund in der Kurzhilfe — sichtbar erst, wenn
der Kunde mit dem Zeiger darauf bleibt. Das Bild des Fehlfalls zeigt den Knopf,
nicht den Satz; der Satz stand nur im Protokoll (``messages``), und beide
Prüfer stützten Prüfpunkt 7 auf eine Zeile, die sie nie gesehen hatten (Lauf
002, ``04-fehlfall.png``). Eine Eigenschaft im Protokoll ersetzt kein
angezeigtes Bild: :func:`reason_picture` zeigt die Kurzhilfe, wie Qt sie beim
Überfahren zeigt, und nimmt sie auf.

Aufgerufen aus dem Fehlfall des Prüfstands (``function_bench``) neben dem Bild
``04-fehlfall`` über :func:`reason_pictures`, und überall, wo eine Fläche mit
ihrem *Übernehmen* aufgenommen wird, am grauen Hauptknopf (FD-99,
:func:`grey_apply_pictures`): auf dem Hauptweg vor den Eingaben oder, wenn erst
der Klick auf das Ziel die Fläche öffnet, danach; im Sprachfall an jeder
aufgenommenen Fläche.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Final

from tools.function_machine import Step, StepMachine

#: Die Klasse, als die Qt eine Kurzhilfe zeigt (``QToolTip``).
TIP_CLASS: Final = "QTipLabel"
#: Wie lange höchstens auf die Kurzhilfe gewartet wird (Sekunden): Unter Windows
#: blendet Qt sie mit ``UI_AnimateTooltip`` ein, sichtbar erst nach der Animation.
TIP_WAIT_S: Final = 1.0
#: Grund in ``unmeasured``: grau, aber ohne Kurzhilfe — beim Überfahren zeigt Qt nichts.
NO_VISIBLE_REASON: Final = "kein sichtbarer Sperrgrund: grau ohne Kurzhilfe"
#: Das Bild der Kurzhilfe am grauen *Übernehmen*, bevor der Kunde etwas ändert (FD-99).
GREY_APPLY_PICTURE: Final = "02-uebernehmen-grund"
#: Dasselbe Bild, wenn erst der Klick auf das Ziel die Fläche öffnete (Änderungsweg).
OPENED_APPLY_PICTURE: Final = "03-uebernehmen-grund"
#: Der Hauptknopf einer Fläche, wenn die Zeile kein Ziel des Übernehmens nennt:
#: der eines geöffneten Dialogs, *Übernehmen* des Merkmalfensters.
APPLY_TARGETS: Final = ("dialog.accept", "feature.apply")
#: Grund in ``grey_apply``: Kein Hauptknopf stand sichtbar da — kein Bild, kein Fund.
NO_APPLY_TARGET: Final = "kein Hauptknopf der Fläche sichtbar"
#: Grund in ``unmeasured``: grau mit Kurzhilfe, aber Qt zeigte sie nicht.
SHOWN_NOT: Final = "Kurzhilfe gesetzt, aber nicht gezeigt"


def _shown_tip() -> Any | None:
    from PySide6.QtWidgets import QApplication

    tips = [
        widget
        for widget in QApplication.topLevelWidgets()
        if widget.isVisible() and widget.inherits(TIP_CLASS)
    ]
    return tips[0] if tips else None


def reason_picture(widget: Any, path: Path) -> bool:
    """Zeigt die Kurzhilfe eines grauen Elements wie beim Überfahren und speichert ihr Bild.

    Der Satz ist der, den der Kunde beim Überfahren liest: nur die Kurzhilfe.
    Die zugängliche Beschreibung zeigt Qt dort nicht; ein Bild mit ihr zeigte
    einen Grund, den der Kunde nicht sieht (RC-7). Ohne Kurzhilfe, an einem
    offenen Element oder wenn Qt keine Kurzhilfe zeigt: kein Bild, ``False``.
    """
    import time

    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QApplication, QToolTip

    text = str(widget.toolTip() or "")
    if widget.isEnabled() or not text.strip() or not widget.isVisible():
        return False
    # Erst der Zeiger über den Knopf, wie die Hand: Qt blendet eine Kurzhilfe mit
    # Widget aus, sobald der Zeiger außerhalb steht — am echten Fenster stand er
    # noch am letzten Klickort (Schlusslauf, clear_filament bei 125 %).
    centre = widget.rect().center()
    QTest.mouseMove(widget, centre + QPoint(1, 1))  # von der Seite, sonst keine Bewegung
    QTest.mouseMove(widget, centre)
    for _round in range(5):
        QApplication.processEvents()
    QToolTip.showText(widget.mapToGlobal(centre), text, widget)
    # Bis sie steht, höchstens :data:`TIP_WAIT_S` — ein Durchlauf sah nativ nie eine.
    until = time.perf_counter() + TIP_WAIT_S
    QApplication.processEvents()
    while (tip := _shown_tip()) is None and time.perf_counter() < until:
        time.sleep(0.01)
        QApplication.processEvents()
    try:
        return bool(tip is not None and tip.grab().save(str(path)))
    finally:
        # ``hideText`` blendet erst nach einer Frist aus; die nächste Aufnahme
        # soll die Kurzhilfe nicht mehr sehen.
        QToolTip.hideText()
        if tip is not None:
            tip.hide()
        QApplication.processEvents()


def reason_pictures(
    find: Callable[[str], Any | None],
    targets: Sequence[str],
    folder: Path,
    out: Path,
    *,
    silent: Callable[[str], None] = lambda target: None,
    prefix: str = "04-fehlfall-grund",
) -> list[str]:
    """Je graues Ziel der Zeile das Bild seines Sperrgrunds, relativ zu ``out``.

    ``find`` liest das Widget hinter einem Wortschatznamen (``FunctionFlow.widget``).
    Die Bilder heißen ``04-fehlfall-grund-<n>.png`` in der Folge der Ziele. Ein
    sichtbares graues Ziel ohne Kurzhilfe bekommt kein Bild; ``silent`` nennt es.
    """
    images = []
    for number, target in enumerate(targets, 1):
        widget = find(target)
        path = folder / f"{prefix}-{number}.png"
        if widget is None:
            continue
        if reason_picture(widget, path):
            images.append(path.relative_to(out).as_posix())
        elif widget.isVisible() and not widget.isEnabled() and not str(widget.toolTip() or ""):
            silent(target)
    return images


def grey_apply_pictures(flow: Any, targets: Sequence[str], prefix: str) -> None:
    """FD-99: der Grund an jedem grauen Hauptknopf der aufgenommenen Fläche, als Bild.

    ``flow`` ist ein ``FunctionFlow`` (``widget``, ``folder``, ``out``, ``data``).
    Je sichtbarem Ziel ein Eintrag in ``data["grey_apply"]``: wo, welches Ziel,
    grau oder frei, das Bild der Kurzhilfe. Grau ohne Kurzhilfe ist
    ``unmeasured`` (:data:`NO_VISIBLE_REASON`); steht kein Ziel da, sagt es der
    Eintrag (:data:`NO_APPLY_TARGET`) — ein fehlendes Bild bleibt nie stumm.
    """
    from tools.function_protocol import unmeasured

    entries = flow.data["grey_apply"] = flow.data.get("grey_apply") or []
    shown = [
        (target, widget)
        for target in targets
        if (widget := flow.widget(target)) is not None and widget.isVisible()
    ]
    for number, (target, widget) in enumerate(shown, 1):
        path = flow.folder / f"{prefix}-{number}.png"
        image = path.relative_to(flow.out).as_posix() if reason_picture(widget, path) else None
        grey = not widget.isEnabled()
        if image is not None:
            flow.data["images"].append(image)
        elif grey:
            said = str(widget.toolTip() or "").strip()
            unmeasured(flow.data, f"sperrgrund:{target}", SHOWN_NOT if said else NO_VISIBLE_REASON)
        entries.append({"where": prefix, "target": target, "grey": grey, "image": image})
    if not shown:
        entries.append({"where": prefix, "target": None, "reason": NO_APPLY_TARGET})


def main_buttons(target: str | None) -> tuple[str, ...]:
    """Die Hauptknöpfe einer Fläche: das Ziel des Übernehmens, ohne eines :data:`APPLY_TARGETS`."""
    return (target,) if target else APPLY_TARGETS


def grey_apply_step(flow: Any, targets: Sequence[str], prefix: str = GREY_APPLY_PICTURE) -> Step:
    """FD-99: :func:`grey_apply_pictures` als Schritt des Hauptwegs.

    Ein Änderungsweg öffnet sein Formular mit grauem *Übernehmen* („Erst
    „{Feld}“ ändern, dann übernehmen.“); die Kurzhilfe sah bisher nur der
    Fehlfall. ``targets`` meist aus :func:`main_buttons`.
    """

    def act(machine: StepMachine) -> None:
        grey_apply_pictures(flow, targets, prefix)

    return Step("grund am grauen übernehmen", act)
