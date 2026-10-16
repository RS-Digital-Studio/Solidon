"""Der Grund eines grauen Bedienelements als eigenes Bild (RM-737, FD-149).

Ein grauer Knopf sagt seinen Sperrgrund in der Kurzhilfe — sichtbar erst, wenn
der Kunde mit dem Zeiger darauf bleibt. Das Bild des Fehlfalls zeigt den Knopf,
nicht den Satz; der Satz stand nur im Protokoll (``messages``), und beide
Prüfer stützten Prüfpunkt 7 auf eine Zeile, die sie nie gesehen hatten (Lauf
002, ``04-fehlfall.png``). Eine Eigenschaft im Protokoll ersetzt kein
angezeigtes Bild: :func:`reason_picture` zeigt die Kurzhilfe, wie Qt sie beim
Überfahren zeigt, und nimmt sie auf.

Aufgerufen aus dem Fehlfall des Prüfstands (``function_bench``) neben dem Bild
``04-fehlfall`` über :func:`reason_pictures`.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Final

#: Die Klasse, als die Qt eine Kurzhilfe zeigt (``QToolTip``).
TIP_CLASS: Final = "QTipLabel"
#: Grund in ``unmeasured``: grau, aber ohne Kurzhilfe — beim Überfahren zeigt Qt nichts.
NO_VISIBLE_REASON: Final = "kein sichtbarer Sperrgrund: grau ohne Kurzhilfe"


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
    from PySide6.QtWidgets import QApplication, QToolTip

    text = str(widget.toolTip() or "")
    if widget.isEnabled() or not text.strip() or not widget.isVisible():
        return False
    QToolTip.showText(widget.mapToGlobal(widget.rect().center()), text, widget)
    QApplication.processEvents()
    tip = _shown_tip()
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
) -> list[str]:
    """Je graues Ziel der Zeile das Bild seines Sperrgrunds, relativ zu ``out``.

    ``find`` liest das Widget hinter einem Wortschatznamen (``FunctionFlow.widget``).
    Die Bilder heißen ``04-fehlfall-grund-<n>.png`` in der Folge der Ziele. Ein
    sichtbares graues Ziel ohne Kurzhilfe bekommt kein Bild; ``silent`` nennt es.
    """
    images = []
    for number, target in enumerate(targets, 1):
        widget = find(target)
        path = folder / f"04-fehlfall-grund-{number}.png"
        if widget is None:
            continue
        if reason_picture(widget, path):
            images.append(path.relative_to(out).as_posix())
        elif widget.isVisible() and not widget.isEnabled() and not str(widget.toolTip() or ""):
            silent(target)
    return images
