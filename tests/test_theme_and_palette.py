"""Themenkontrast und die Befehlspalette (Bauplan §19.2, §19.3)."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from app.core.registry import REGISTRY
from app.ui.command_palette import CommandPalette, matches
from app.ui.theme import THEMES, contrast_ratio, viewport_colours

#: WCAG AA for body text.
MINIMUM_CONTRAST = 4.5


@pytest.mark.parametrize("theme", list(THEMES))
def test_text_has_enough_contrast_in_both_themes(theme: str) -> None:
    """§19.3: ausreichender Kontrast im hellen und im dunklen Thema."""
    colours = THEMES[theme]  # type: ignore[index]
    assert contrast_ratio(colours["text"], colours["window"]) >= MINIMUM_CONTRAST
    assert contrast_ratio(colours["text"], colours["base"]) >= MINIMUM_CONTRAST
    assert contrast_ratio(colours["highlight_text"], colours["highlight"]) >= 3.0


@pytest.mark.parametrize("theme", list(THEMES))
def test_the_viewport_follows_the_theme(theme: str) -> None:
    colours = viewport_colours(theme)  # type: ignore[arg-type]
    assert set(colours) == {"bottom", "top", "object", "bed", "edge"}
    assert contrast_ratio(colours["object"], colours["bottom"]) >= 1.8, "a body stands out"
    # Eine Körperkante, die man suchen muss, hilft niemandem — dieselbe
    # Schwelle, die WCAG für lesbaren Text nennt, und aus demselben Grund.
    assert contrast_ratio(colours["edge"], colours["object"]) >= 4.0, (
        "die Kante muss sich vom Körper abheben"
    )


def test_the_two_themes_are_actually_different() -> None:
    assert THEMES["dark"]["window"] != THEMES["light"]["window"]
    assert contrast_ratio(THEMES["dark"]["window"], THEMES["light"]["window"]) > 5.0


def test_contrast_ratio_matches_the_known_extremes() -> None:
    assert contrast_ratio("#000000", "#ffffff") == pytest.approx(21.0, abs=0.01)
    assert contrast_ratio("#123456", "#123456") == pytest.approx(1.0)


# --- command palette ------------------------------------------------------------


def test_the_search_finds_by_title_name_and_documentation() -> None:
    entry = next(entry for entry in _palette_entries() if entry.name == "rename_object")
    assert matches(entry, "")
    assert matches(entry, "umbenennen")
    assert matches(entry, "rename")
    assert matches(entry, "objekt umbenennen")
    assert not matches(entry, "bohrung")


def test_the_palette_lists_every_operation(qt_app: object) -> None:
    palette = CommandPalette()
    listed = {
        palette.list.item(index).data(0x0100)  # Qt.ItemDataRole.UserRole
        for index in range(palette.list.count())
    }
    assert listed == {spec.name for spec in REGISTRY.all()}


def test_the_palette_shows_the_shortcut_so_it_gets_learned(qt_app: object) -> None:
    """§2.6: das Kürzel steht neben dem Eintrag — so lernt es sich."""
    palette = CommandPalette()
    labels = [palette.list.item(index).text() for index in range(palette.list.count())]
    assert any("F2" in label for label in labels), "rename_object carries F2"


def test_typing_narrows_the_list_and_picks_the_first(qt_app: object) -> None:
    palette = CommandPalette()
    palette.search.setText("duplizieren")

    assert palette.list.count() == 1
    assert palette.chosen() == "duplicate_object"


def test_a_search_without_hits_chooses_nothing(qt_app: object) -> None:
    palette = CommandPalette()
    palette.search.setText("gibtsnicht")

    assert palette.list.count() == 0
    assert palette.chosen() is None


def _palette_entries():
    from app.core.registry import palette_entries

    return list(palette_entries())
