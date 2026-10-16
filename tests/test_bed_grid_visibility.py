"""Das Bettraster bleibt auf seiner beleuchteten Fläche sichtbar und dem Thema treu."""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication

from app.core.types import Profile
from app.core.units import LengthUnit
from app.ui.labels import display_unit, set_display_unit
from app.ui.render.api import rgb
from app.ui.theme import THEMES, Theme, contrast_ratio
from app.ui.viewport import BED_FRAME, BED_SURFACE_DROP, Viewport
from tests.render_fakes import RecordingItem, RecordingLabels, RecordingRenderer


@pytest.fixture
def bed_view(qt_app: QApplication) -> Iterator[tuple[Viewport, RecordingRenderer]]:
    view = Viewport()
    renderer = RecordingRenderer()
    view.renderer = renderer
    try:
        yield view, renderer
    finally:
        view.renderer = None
        view.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _mixed_colour(item: RecordingItem, background: str) -> str:
    """Die konfigurierte Deckkraft gegen den gesicherten Vorher-Bettpixel rechnen.

    Das ist ein Materialgegenfall, kein Ersatz für geglättete native Bildpunkte.
    """
    mixed = np.asarray(rgb(item.colour())) * item.opacity()
    mixed += np.asarray(rgb(background)) * (1.0 - item.opacity())
    return "#" + "".join(f"{round(value * 255):02x}" for value in mixed)


def test_light_grid_has_contrast_against_the_observed_shaded_bed(
    bed_view: tuple[Viewport, RecordingRenderer],
) -> None:
    view, renderer = bed_view
    view.set_theme("light")
    view._draw_one_bed(0, 0.0, 256.0, 256.0, 256.0)
    # Originalpixel der freien Bettfläche im nativen D4-Bild vom 13.10.2026.
    background = "#b8c0c9"
    minor = renderer.item_of("bed_0")
    assert contrast_ratio(_mixed_colour(minor, background), background) >= 1.5


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_bed_has_distinct_major_lines_without_changing_volume_or_sketch_colours(
    bed_view: tuple[Viewport, RecordingRenderer], theme: Theme
) -> None:
    view, renderer = bed_view
    view.set_theme(theme)
    view._draw_one_bed(0, 0.0, 256.0, 192.0, 250.0)
    minor = renderer.item_of("bed_0")
    major = renderer.item_of("bed_major_0")
    assert minor.colour() == major.colour() == THEMES[theme]["bed_grid"]
    assert major.opacity() > minor.opacity()
    assert major.line_width >= minor.line_width  # type: ignore[operator]
    assert renderer.item_of("build_volume_0").colour() == THEMES[theme]["bed"]
    assert renderer.item_of("build_volume_0").opacity() == pytest.approx(0.35)
    assert view._grid_minor_colour == view._grid_major_colour == THEMES[theme]["grid_major"]


@pytest.mark.parametrize("unit", ["mm", "in"])
@pytest.mark.parametrize("shift,width,depth", [(0.0, 256.0, 192.0), (306.0, 256.0, 256.0)])
def test_grid_major_lines_lie_at_the_scale_numbers_on_every_plate(
    bed_view: tuple[Viewport, RecordingRenderer],
    shift: float,
    width: float,
    depth: float,
    unit: LengthUnit,
) -> None:
    """Die Hauptlinien stehen an den Maßzahlen, auch auf Platte 2 und in Zoll (FD-170)."""
    view, renderer = bed_view
    before = display_unit()
    set_display_unit(unit)
    try:
        view._draw_one_bed(1, shift, width, depth, 250.0)
    finally:
        set_display_unit(before)
    minor = renderer.item_of("bed_1").points.reshape(-1, 2, 3)
    major = renderer.item_of("bed_major_1").points.reshape(-1, 2, 3)
    first = {tuple(pair.ravel()) for pair in minor}
    second = {tuple(pair.ravel()) for pair in major}
    assert not first & second, "Hauptlinien dürfen nicht doppelt übereinander gemischt werden"
    np.testing.assert_allclose(major[:, :, 2], 0.0)
    np.testing.assert_allclose(renderer.item_of("bed_surface_1").points[:, 2], -BED_SURFACE_DROP)
    numbers = renderer.item_of("bed_scale_1").points
    front = np.sort(numbers[numbers[:, 1] < -depth / 2.0, 0])
    left = np.sort(numbers[numbers[:, 0] < shift - width / 2.0, 1])
    across = np.isclose(major[:, 0, 0], major[:, 1, 0])
    np.testing.assert_allclose(np.sort(major[across, 0, 0]), front)
    np.testing.assert_allclose(np.sort(major[~across, 0, 1]), left)
    # Der Rand schließt das Raster, auch wo keine Zahl steht.
    every_x = np.concatenate((minor[:, 0, 0], major[:, 0, 0]))
    assert every_x.min() == pytest.approx(shift - width / 2.0)
    assert every_x.max() == pytest.approx(shift + width / 2.0)


def test_theme_switch_rebuilds_both_grid_levels_and_keeps_bed_visibility(
    bed_view: tuple[Viewport, RecordingRenderer], profile: Profile
) -> None:
    view, renderer = bed_view
    view.show_build_volume(profile)
    old = renderer.item_of("bed_0")
    for theme in ("light", "dark", "light"):
        view.set_theme(theme)
        assert old in renderer.removed
        minor = renderer.item_of("bed_0")
        major = renderer.item_of("bed_major_0")
        assert minor.colour() == major.colour() == THEMES[theme]["bed_grid"]
        view.set_bed_visible(False)
        assert not minor.visible() and not major.visible()
        view.set_bed_visible(True)
        assert minor.visible() and major.visible()
        view._sketch_frame = BED_FRAME
        view.show_build_volume(profile)
        assert not minor.visible() and not major.visible()
        view._sketch_frame = None
        view.show_build_volume(profile)
        assert minor.visible() and major.visible()
        old = minor


@pytest.mark.parametrize("first_theme", ["light", "dark"])
def test_bed_scale_uses_text_colour_and_returns_without_changing_volume(
    bed_view: tuple[Viewport, RecordingRenderer], profile: Profile, first_theme: Theme
) -> None:
    view, renderer = bed_view
    view.set_theme(first_theme)
    view.show_build_volume(profile)
    first = renderer.item_of("bed_scale_0")
    assert isinstance(first, RecordingLabels)
    points, texts = first.points.copy(), first.texts.copy()
    other: Theme = "dark" if first_theme == "light" else "light"
    for theme in (first_theme, other, first_theme):
        view.set_theme(theme)
        labels = renderer.item_of("bed_scale_0")
        assert isinstance(labels, RecordingLabels)
        assert labels.colour() == THEMES[theme]["text"]
        np.testing.assert_array_equal(labels.points, points)
        assert labels.texts == texts
        assert labels.style.font_size == 9 and labels.style.always_visible
        assert renderer.item_of("build_volume_0").colour() == THEMES[theme]["bed"]
        assert renderer.item_of("build_volume_0").opacity() == pytest.approx(0.35)
