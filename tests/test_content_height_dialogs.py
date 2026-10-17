"""Dialoge mit ``ContentHeight`` passen ihren Inhalt vor und nach jeder Klappe (FD-198, FD-199).

Der R1-Fix (Messung ohne vorläufigen Rollbalken) stand nur im Operationsdialog.
*Parameter anlegen* behielt nach dem Aufklappen 16 Punkte leer über den Knöpfen,
*Material kalibrieren* rollte bei 16 pt 18 Punkte, obwohl unter dem Dialog
Platz war (Review 2 F2a/D, N2). Baustein, Erste Schritte, Chat und Freischalten
gaben zugeklappt keine Höhe zurück: Ihre Klappen maßen nur passiv. Geprüft bei
9 bis 16 pt, je beim Öffnen und nach jedem Auf- und Zuklappen.
"""

from __future__ import annotations

import time
from collections.abc import Callable

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QHBoxLayout,
    QLayout,
    QToolButton,
    QWidget,
)

from app.ui.style import NORMAL, DialogScrollArea, apply_style
from app.ui.theme import apply_theme
from tests.bundled_fonts import bundled_font

#: So viele Punkte darf der Rollbereich höher sein als sein Inhalt — Rundung.
SLACK = 1


def _calibration() -> QDialog:
    from app.core.knowledge import profiles
    from app.ui.calibration_dialog import CalibrationDialog

    return CalibrationDialog("petg", process=profiles.make_profile("centauri-carbon-2", "petg"))


def _parameter() -> QDialog:
    from app.core.types import Parameter
    from app.ui.parameter_dialog import ParameterDialog

    return ParameterDialog({"breite": Parameter(name="breite", value=40.0, unit="mm")})


def _counterpart() -> QDialog:
    from app.ui.counterpart_dialog import CounterpartDialog

    return CounterpartDialog("Erste Fläche", "Zweite Fläche")


def _recipe() -> QDialog:
    from dataclasses import replace

    from app.core.scene.project import new_project
    from app.core.types import Feature, Parameter
    from app.ui.recipe_dialog import RecipeDialog

    document = replace(
        new_project().document,
        parameters={"breite": Parameter(name="breite", value=40.0, unit="mm", title="Breite")},
    )
    hole = Feature(id="hole_1", kind="hole", provenance="detected", params={"diameter": 5.2})
    return RecipeDialog(document, {}, (0,), (hole,), None)  # type: ignore[arg-type]


def _first_run() -> QDialog:
    from app.ui.first_run import FirstRunDialog
    from app.ui.settings import UiSettings

    return FirstRunDialog(UiSettings())


def _chat() -> QDialog:
    from app.ui.dialogs import KeyDialog
    from app.ui.settings import UiSettings

    return KeyDialog(settings=UiSettings())


def _activation() -> QDialog:
    from app.ui.dialogs import ActivationDialog

    return ActivationDialog()


def _settings() -> QDialog:
    from app.ui.settings import UiSettings
    from app.ui.settings_dialog import SettingsDialog

    return SettingsDialog(UiSettings(), slicer_path="")


MAKERS = [
    _calibration,
    _parameter,
    _counterpart,
    _recipe,
    _first_run,
    _chat,
    _activation,
    _settings,
]
NAMES = [
    "kalibrieren",
    "parameter",
    "gegenstueck",
    "baustein",
    "erste",
    "chat",
    "freischalten",
    "einstellungen",
]


def _settle(qt_app: QApplication, dialog: QDialog) -> None:
    """Bis die Größe acht Umläufe lang steht, höchstens drei Sekunden."""
    last = None
    still = 0
    end = time.monotonic() + 3.0
    while time.monotonic() < end and still < 8:
        qt_app.processEvents()
        time.sleep(0.005)
        now = (dialog.width(), dialog.height())
        still = still + 1 if now == last else 0
        last = now


def _waits(dialog: QDialog) -> Callable[[], object] | None:
    """Worauf der Dialog nach dem Öffnen wartet, bevor sein Inhalt steht."""
    found = getattr(dialog, "wait_for_look", None) or getattr(dialog, "wait_for_survey", None)
    return found if callable(found) else None


def _strip(dialog: QDialog, *, may_stay: bool = False) -> str:
    """Leer über den Knöpfen, gerollt mit Platz darunter, oder quer gerollt.

    ``may_stay``: Der Inhalt ist nach dem Öffnen nachgereicht kürzer geworden;
    passiv gibt der Dialog die Höhe vertragsgemäß nicht zurück (RM-487).
    """
    found = []
    screen = dialog.screen().availableGeometry().adjusted(NORMAL, NORMAL, -NORMAL, -NORMAL)
    for scroll in dialog.findChildren(DialogScrollArea):
        content = scroll.widget()
        layout = content.layout() if content is not None else None
        if not scroll.isVisible() or content is None or layout is None:
            continue
        # Quer rollen darf er nur, wenn der Bildschirm keine Breite mehr hergibt.
        wider = screen.width() - dialog.frameGeometry().width()
        sideways = scroll.horizontalScrollBar().maximum()
        if scroll.horizontalScrollBar().isVisibleTo(scroll) and wider >= sideways:
            found.append(f"rollt quer {sideways} Punkte, daneben {wider} frei")
        need = layout.totalHeightForWidth(scroll.viewport().width())
        if need < 0:
            need = content.sizeHint().height()
        empty = scroll.viewport().height() - need
        if empty > SLACK and not may_stay:
            found.append(f"{empty} Punkte leer")
        rolls = scroll.verticalScrollBar().maximum()
        room = screen.bottom() - dialog.frameGeometry().bottom()
        if rolls > 0 and room > rolls:
            found.append(f"rollt {rolls} Punkte, darunter {room} frei")
    return ", ".join(found)


@pytest.mark.parametrize("points", [9, 11, 14, 16])
@pytest.mark.parametrize(
    "make",
    MAKERS,
    ids=NAMES,
)
def test_the_dialog_fits_its_content_before_and_after_each_flap(
    qt_app: QApplication, make: Callable[[], QDialog], points: int
) -> None:
    found: list[str] = []
    with bundled_font(qt_app, points):
        apply_theme(qt_app, "light")
        apply_style(qt_app, "light")
        dialog = make()
        try:
            dialog.show()
            _settle(qt_app, dialog)
            # Chat und Einstellungen reichen Schlüsselstatus und Slicersuche aus
            # einem Arbeiter nach.
            looks = _waits(dialog)
            if looks is not None:
                looks()
                _settle(qt_app, dialog)
            if said := _strip(dialog, may_stay=looks is not None):
                found.append(f"beim Öffnen: {said}")
            for heading in dialog.findChildren(QToolButton, "sectionHeading"):
                if not (heading.isCheckable() and heading.isVisible()):
                    continue
                for _ in range(2):
                    heading.click()
                    _settle(qt_app, dialog)
                    if said := _strip(dialog):
                        state = "auf" if heading.isChecked() else "zu"
                        found.append(f"„{heading.text()}“ {state}: {said}")
        finally:
            dialog.reject()
            dialog.deleteLater()
            qt_app.processEvents()
    apply_style(qt_app, "light")
    assert not found, found


def _spare_notes(dialog: QDialog) -> list[str]:
    """Umbrochene Sätze, die höher stehen, als ihr Text in ihrer Breite braucht.

    Steht der Satz in einer Reihe neben einem Knopf, darf er so hoch sein wie der höchste
    Nachbar: Die Reihe hat dessen Höhe, und der Satz steht mittig daneben — das ist keine
    leere Zeile. Auf den Läufern ohne Ollama wurde die Dienstzeile von *Chat einrichten*
    nach 14 → 9 pt einzeilig und stand 26 Punkte hoch neben dem Knopf (CI-Lauf 39035816730).
    """
    from app.ui.style import WrappedNote

    found = []
    for note in dialog.findChildren(WrappedNote):
        if not note.isVisible() or not note.text():
            continue
        least, most = note.minimumHeight(), note.maximumHeight()
        note.setMinimumHeight(0)
        note.setMaximumHeight(16_777_215)
        needed = max(note.heightForWidth(note.width()), 0)
        note.setMinimumHeight(least)
        note.setMaximumHeight(most)
        if note.height() - max(needed, _tallest_neighbour(note)) > SLACK:
            found.append(f"{note.text()[:30]!r} {note.height()} hoch für {needed}")
    return found


def _tallest_neighbour(note: QWidget) -> int:
    """Die Höhe des höchsten sichtbaren Nachbarn in der waagrechten Reihe des Satzes, sonst 0."""
    from app.ui.layout_lifetime import layout_parts

    parent = note.parentWidget()
    top = parent.layout() if parent is not None else None
    pending: list[QLayout] = [top] if top is not None else []
    while pending:
        layout = pending.pop()
        parts = layout_parts(layout)
        widgets = [widget for widget, _inner in parts if widget is not None]
        pending += [inner for _widget, inner in parts if inner is not None]
        if note in widgets and isinstance(layout, QHBoxLayout):
            return max(
                (other.height() for other in widgets if other is not note and other.isVisible()),
                default=0,
            )
    return 0


@pytest.mark.parametrize("make", MAKERS, ids=NAMES)
def test_the_dialog_gives_back_its_height_after_a_font_change(
    qt_app: QApplication, make: Callable[[], QDialog]
) -> None:
    """Nach 9 → 14 → 9 pt steht nichts leer, weder über den Knöpfen noch zwischen
    den Sätzen (L5: *Erste Schritte* 12 Punkte; P4: *Chat einrichten* 750 statt
    606, die Lücken zwischen den Sätzen)."""
    from PySide6.QtGui import QFont

    found: list[str] = []
    with bundled_font(qt_app, 9):
        apply_theme(qt_app, "light")
        apply_style(qt_app, "light")
        dialog = make()
        try:
            dialog.show()
            _settle(qt_app, dialog)
            looks = _waits(dialog)
            if looks is not None:
                looks()
                _settle(qt_app, dialog)
            for points in (14, 9):
                qt_app.setFont(QFont("DejaVu Sans", points))
                _settle(qt_app, dialog)
                # Ein Satz misst eine Runde nach der Schrift, das Fenster danach.
                _settle(qt_app, dialog)
            if said := _strip(dialog):
                found.append(f"nach 9 → 14 → 9 pt: {said}")
            found += [f"Satz: {said}" for said in _spare_notes(dialog)]
        finally:
            dialog.reject()
            dialog.deleteLater()
            qt_app.processEvents()
    apply_style(qt_app, "light")
    assert not found, found
