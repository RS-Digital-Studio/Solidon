"""Ein Operationsdialog bleibt so hoch wie sein Inhalt, auch nach dem Aufklappen.

Beim Aufklappen von *Weitere Einstellungen* steht für einen Umlauf der
senkrechte Rollbalken, und der Ausschnitt ist um seine Breite schmaler. Die
Klappenmessung las den Inhalt in dieser vorläufigen Breite: Der
Beschreibungssatz brach eine Zeile mehr um, eine Merkmalsliste behielt ihre
Querleiste, und über den Knöpfen blieben 12 bis 28 Punkte leer, die das passive
Nachmessen nie zurückgibt (``fenster.md``, RM-487). Geprüft wird jede
Operation in jeder Sprache beim Öffnen und nach dem Aufklappen, dazu Deutsch in
großer Schrift. Quer rollen darf ein Dialog nur, wenn der Bildschirm keine
Breite mehr hergibt: *Bohrung setzen* rollte bei 16 und 18 pt acht Punkte quer,
und eine Ausnahme für jede Querleiste verdeckte es (FD-200).
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app.core import bootstrap
from app.core.registry import REGISTRY
from app.i18n import get_language, set_language
from app.i18n.catalog import available_languages, install_language
from app.ui.style import NORMAL, apply_style
from app.ui.theme import apply_theme
from tests.bundled_fonts import bundled_font

#: So viele Punkte darf der Rollbereich höher sein als sein Inhalt — Rundung.
SLACK = 1

#: Grundschrift unter Windows und die große Schrift aus den Einstellungen.
CASES = [(language, 9) for language in available_languages()] + [("de", 16), ("de", 18)]

FEATURES = {"hole_1": "Bohrung 1 · Ø5,20 mm", "hole_2": "Bohrung 2 · Ø5,20 mm"}


@contextmanager
def _spoken(qt_app: QApplication, language: str, points: int) -> Iterator[None]:
    """Sprache und gebündelte Prüfschrift: Die synthetische Offscreen-Schrift
    misst jede Familie gleich, und die Querleiste aus FD-200 zeigte sich nur
    mit echter Metrik."""
    spoken = get_language()
    previous = QFont(qt_app.font())
    install_language(language)
    set_language(language)
    try:
        with bundled_font(qt_app, points):
            apply_theme(qt_app, "light")
            apply_style(qt_app, "light")
            yield
    finally:
        qt_app.setFont(previous)
        apply_style(qt_app, "light")
        install_language(spoken)
        set_language(spoken)


def _settle(qt_app: QApplication, dialog: object) -> None:
    """Bis die Größe acht Umläufe lang steht, höchstens drei Sekunden."""
    last = None
    still = 0
    end = time.monotonic() + 3.0
    while time.monotonic() < end and still < 8:
        qt_app.processEvents()
        time.sleep(0.005)
        now = (dialog.width(), dialog.height())  # type: ignore[attr-defined]
        still = still + 1 if now == last else 0
        last = now


def _strip(dialog: object) -> str:
    """Leer über den Knöpfen, gerollt mit Platz darunter oder quer mit Platz daneben."""
    scroll = dialog._scroll  # type: ignore[attr-defined]
    # Bis zum Rand, den ``fit_dialog_to_screen`` frei lässt.
    screen = dialog.screen().availableGeometry().adjusted(NORMAL, NORMAL, -NORMAL, -NORMAL)  # type: ignore[attr-defined]
    if scroll.horizontalScrollBar().isVisibleTo(scroll):
        sideways = scroll.horizontalScrollBar().maximum()
        wider = screen.width() - dialog.frameGeometry().width()  # type: ignore[attr-defined]
        if wider >= sideways:
            return f"rollt quer {sideways} Punkte, daneben {wider} frei"
        # Den Rest deckelt der Prüfbildschirm (offscreen 800 Punkte); über
        # die Höhe auf dem Kundenbildschirm sagt der Dialog dann nichts.
        return ""
    layout = scroll.widget().layout()
    empty = scroll.viewport().height() - layout.totalHeightForWidth(scroll.viewport().width())
    if empty > SLACK:
        return f"{empty} Punkte leer"
    rolls = scroll.verticalScrollBar().maximum()
    room = screen.bottom() - dialog.frameGeometry().bottom()  # type: ignore[attr-defined]
    if rolls > 0 and room > rolls:
        return f"rollt {rolls} Punkte, darunter {room} frei"
    return ""


@pytest.mark.parametrize(("language", "points"), CASES)
def test_every_dialog_fits_its_content_before_and_after_the_flap(
    qt_app: QApplication, language: str, points: int
) -> None:
    from app.ui.op_dialog import OperationDialog

    bootstrap.load_operations()
    found: list[str] = []
    flaps = 0
    with _spoken(qt_app, language, points):
        for spec in sorted(REGISTRY.all(), key=lambda entry: entry.name):
            dialog = OperationDialog(spec, {"obj_1": "Quader"}, None, features=FEATURES)
            try:
                dialog.show()
                _settle(qt_app, dialog)
                if said := _strip(dialog):
                    found.append(f"{spec.name} beim Öffnen: {said}")
                # Ohne Rückseite baut der Dialog keine Klappe.
                advanced = getattr(dialog, "advanced", None)
                if advanced is not None and advanced.isVisible() and not advanced.isChecked():
                    advanced.click()
                    _settle(qt_app, dialog)
                    flaps += 1
                    if said := _strip(dialog):
                        found.append(f"{spec.name} aufgeklappt: {said}")
            finally:
                dialog.reject()
                dialog.deleteLater()
                qt_app.processEvents()
    # Eine Klappenprüfung über eine leere Menge wäre immer grün.
    assert flaps > 100, f"nur {flaps} Dialoge mit Klappe aufgeklappt"
    assert not found, f"{language} {points} pt, {len(found)} Dialoge:\n" + "\n".join(found)
