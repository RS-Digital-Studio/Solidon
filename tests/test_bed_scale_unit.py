"""Die Maßzahlen am Druckbett folgen der Anzeigeeinheit (FD-92, §19.3).

In Zoll stand am Bett „100" — Millimeter ohne Einheit, während Kopfzeile und
Objektbaum Zoll zeigten. Die reinen Rechnungen laufen ohne Fenster; der
Anschluss an den Einheitenwechsel braucht die Ansicht (``qt_app``).
"""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from app.core.types import Profile
from app.core.units import UNIT_TO_MM, LengthUnit
from app.ui.bed_scale import BED_SCALE_STEP, bed_scale, scale_step
from app.ui.labels import display_unit, set_display_unit
from tests.render_fakes import RecordingLabels, RecordingRenderer


@pytest.fixture
def unit_back() -> Iterator[None]:
    """Die Anzeigeeinheit ist ein Prozesszustand; jeder Test gibt ihn zurück."""
    before = display_unit()
    try:
        yield
    finally:
        set_display_unit(before)


def _front(marks: list[tuple[tuple[float, float, float], str]]) -> list[tuple[float, str]]:
    """Die Marken der Vorderkante, von links nach rechts.

    Sie stehen weiter vorn als seitlich, die der linken Kante umgekehrt — das
    trennt die Kanten, solange die Platte annähernd quadratisch ist.
    """
    return sorted((point[0], text) for point, text in marks if abs(point[1]) > abs(point[0]))


@pytest.mark.parametrize(("unit", "step"), [("mm", 50.0), ("in", 2.0), ("cm", 5.0), ("m", 0.05)])
def test_the_step_is_a_round_number_of_the_unit_near_fifty_millimetres(
    unit: LengthUnit, step: float
) -> None:
    """Eine Skala in Zoll zählt in runden Zoll, nicht in 1,97."""
    assert scale_step(unit) == pytest.approx(step)
    assert 0.5 * BED_SCALE_STEP <= step * UNIT_TO_MM[unit] <= 2.0 * BED_SCALE_STEP


def test_in_inches_the_numbers_are_inches_at_their_true_place() -> None:
    """Die Zahl „2" steht bei 50,8 mm, nicht „50" bei 50 mm."""
    marks = bed_scale(256.0, 256.0, "in")
    front = _front(marks)
    assert [text for _x, text in front] == ["-4", "-2", "0", "2", "4 in"]
    assert [x for x, _text in front] == pytest.approx([-101.6, -50.8, 0.0, 50.8, 101.6])
    left = sorted((point[1], text) for point, text in marks if abs(point[0]) > abs(point[1]))
    assert [text for _y, text in left] == ["-4", "-2", "0", "2", "4"]


@pytest.mark.parametrize("unit", ["mm", "in"])
def test_the_unit_stands_once_at_the_scale(unit: LengthUnit) -> None:
    """Einmal je Platte, an der größten Zahl der Vorderkante — kein Zaun aus Einheiten."""
    marks = bed_scale(220.0, 220.0, unit)
    carrying = [text for _point, text in marks if text.endswith(f" {unit}")]
    assert len(carrying) == 1
    front = _front(marks)
    assert front[-1][1] == carrying[0]


def test_a_bed_narrower_than_a_step_names_its_unit_at_zero() -> None:
    """Steht nur die Null da, trägt sie die Einheit."""
    marks = bed_scale(60.0, 60.0, "in")
    assert sorted(text for _point, text in marks) == ["0", "0 in"]


def test_without_a_unit_the_display_unit_counts(unit_back: None) -> None:
    """Die Ansicht ruft ohne Einheit; dann gilt die Einstellung."""
    set_display_unit("in")
    assert any(text.endswith(" in") for _point, text in bed_scale(256.0, 256.0))
    set_display_unit("mm")
    assert any(text.endswith(" mm") for _point, text in bed_scale(256.0, 256.0))


@pytest.fixture
def bed_view(qt_app: QApplication) -> Iterator[tuple[object, RecordingRenderer]]:
    from app.ui.viewport import Viewport

    view = Viewport()
    renderer = RecordingRenderer()
    view.renderer = renderer
    try:
        yield view, renderer
    finally:
        view.renderer = None
        view.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_a_unit_change_redraws_the_bed_numbers(
    bed_view: tuple[object, RecordingRenderer], profile: Profile, unit_back: None
) -> None:
    """Der Einheitenwechsel des Fensters ruft ``refresh_labels``; das Bett zieht nach."""
    from app.ui.viewport import Viewport

    view, renderer = bed_view
    assert isinstance(view, Viewport)
    set_display_unit("mm")
    view.set_theme("dark")
    view.show_build_volume(profile)
    labels = renderer.item_of("bed_scale_0")
    assert isinstance(labels, RecordingLabels)
    assert "100" in labels.texts and not any(text.endswith(" in") for text in labels.texts)

    set_display_unit("in")
    view.refresh_labels()
    labels = renderer.item_of("bed_scale_0")
    assert isinstance(labels, RecordingLabels)
    assert any(text.endswith(" in") for text in labels.texts)
    assert "100" not in labels.texts
    xs = np.sort(labels.points[np.abs(labels.points[:, 1]) > np.abs(labels.points[:, 0]), 0])
    assert xs[-1] == pytest.approx(101.6)

    # Ohne Wechsel baut die Kulisse nicht neu (RM-124).
    view.refresh_labels()
    assert renderer.item_of("bed_scale_0") is labels
