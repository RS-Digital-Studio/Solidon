"""Farbe trägt nie allein Bedeutung (Bauplan §19.1).

Das ist die Barrierefreiheits-Prüfung, die §40 in P1 verlangt: was auch immer
eine Farbe sagt, ein Muster und ein Symbol sagen es auch — und die Kartenrampe
behält ihre Ordnung in Graustufen.
"""

from __future__ import annotations

import pytest

from app.ui.palette import (
    DIFF_PALETTES,
    SEVERITY_ENCODING,
    VIRIDIS,
    distinguishable_without_colour,
    is_monotonic,
    map_colour,
)
from app.ui.theme import contrast_ratio, relative_luminance


@pytest.mark.parametrize("name", list(DIFF_PALETTES))
def test_added_and_removed_differ_in_more_than_colour(name: str) -> None:
    palette = DIFF_PALETTES[name]  # type: ignore[index]

    assert distinguishable_without_colour(palette.added, palette.removed)
    assert palette.added.symbol != palette.removed.symbol
    assert palette.added.pattern != palette.removed.pattern
    assert palette.added.label_key and palette.removed.label_key


@pytest.mark.parametrize("name", list(DIFF_PALETTES))
def test_added_and_removed_also_differ_in_brightness(name: str) -> None:
    """Auch in reinen Graustufen müssen die zwei auseinanderbleiben."""
    palette = DIFF_PALETTES[name]  # type: ignore[index]
    difference = abs(
        relative_luminance(palette.added.colour) - relative_luminance(palette.removed.colour)
    )
    assert difference > 0.1, "a greyscale print must not turn both into the same grey"


def test_the_default_is_blue_and_orange_not_red_and_green() -> None:
    """§19.1: Rot und Grün wären das denkbar schlechteste Paar für die
    wichtigste Ansicht der Anwendung.
    """
    default = DIFF_PALETTES["blue_orange"]
    assert default.added.colour.lower() != default.removed.colour.lower()
    assert "red_green" in DIFF_PALETTES, "still available for those who prefer it"
    assert "greyscale" in DIFF_PALETTES


def test_severity_markers_are_readable_without_colour() -> None:
    symbols = {name: entry.symbol for name, entry in SEVERITY_ENCODING.items()}
    assert len(set(symbols.values())) == len(symbols)
    for entry in SEVERITY_ENCODING.values():
        assert entry.symbol.strip()


def test_the_map_ramp_rises_in_luminance() -> None:
    """§19.1: wahrnehmungsgleich, kein Regenbogen — ein Regenbogen erfindet
    Kanten.
    """
    assert is_monotonic(VIRIDIS)
    assert not is_monotonic(("#ff0000", "#00ff00", "#0000ff")), "the check would catch a rainbow"


def test_the_map_ramp_covers_its_range() -> None:
    assert map_colour(0.0) == VIRIDIS[0]
    assert map_colour(1.0) == VIRIDIS[-1]
    assert map_colour(0.5) == VIRIDIS[len(VIRIDIS) // 2]
    assert map_colour(-5.0) == VIRIDIS[0], "values outside the range are clamped"
    assert map_colour(5.0) == VIRIDIS[-1]
    assert contrast_ratio(VIRIDIS[0], VIRIDIS[-1]) > 4.5


def test_an_empty_ramp_is_refused() -> None:
    with pytest.raises(ValueError):
        map_colour(0.5, ())


def test_a_role_has_one_colour_across_the_interface() -> None:
    """§19.1: dieselbe Bedeutung, überall derselbe Wert.

    Jedes Modul führte seine eigenen Konstanten: „Warnung" hatte drei Werte,
    „Hinweis" fünf. Keiner davon war falsch — sie kannten einander nur nicht,
    und die nächste Stelle hätte einen sechsten bekommen.
    """
    from app.ui import viewport
    from app.ui.palette import ROLES

    assert ROLES["select"] == viewport.SELECTED_COLOUR
    assert ROLES["measure"] == viewport.MEASURE_COLOUR
    assert ROLES["layer"] == viewport.LAYER_COLOUR
    assert ROLES["island"] == viewport.ISLAND_COLOUR
    assert ROLES["overhang"] == viewport.OVERHANG_COLOUR
    assert ROLES["feature"] == viewport.FEATURE_LABEL_COLOUR
    assert ROLES["backface"] == viewport.BACKFACE_COLOUR
    assert ROLES["protected"] == viewport.PROTECTED_COLOUR

    for severity, encoding in SEVERITY_ENCODING.items():
        assert encoding.colour == ROLES[severity]  # type: ignore[literal-required]


def test_selecting_looks_the_same_in_the_list_and_in_the_view() -> None:
    """Dieselbe Handlung, dieselbe Farbe.

    Der Objektbaum färbte in Qts Blau, der Viewport in Bernstein. Wer im Baum
    klickte, sah eine blaue Zeile und einen orangen Körper und musste selbst
    schließen, dass das dasselbe meint.
    """
    from app.ui.palette import ROLES
    from app.ui.theme import THEMES

    for theme in THEMES.values():
        assert theme["highlight"] == ROLES["select"]


def test_the_selection_bar_carries_readable_text() -> None:
    """Ein heller Balken verlangt dunkle Schrift, auch im dunklen Thema.

    Bernstein gegen Weiß bringt 2,06 — unter jeder Schwelle. Die Farbe zu
    nehmen und die Schrift zu vergessen hieße, eine Auswahl unlesbar zu machen,
    um sie einheitlich zu machen.
    """
    from app.ui.theme import THEMES

    for name, theme in THEMES.items():
        ratio = contrast_ratio(theme["highlight"], theme["highlight_text"])
        assert ratio >= 4.5, f"{name}: Auswahlbalken trägt nur {ratio:.2f} Kontrast"


def test_a_pressed_button_keeps_its_label_readable() -> None:
    """Gedrückt ist auch ein Zustand, und die Beschriftung ist auch dann Text.

    Der gedrückte Bernstein kam mit 4,466 herein — knapp unter den 4,5, die
    dieselbe Suite an jeder anderen Textfläche verlangt, und das auf dem
    lautesten Knopf der Anwendung. „Knapp" ist keine Schwelle: Es gibt eine,
    und die gilt für jede Fläche, die Text trägt. Ein Schritt heller im Grün
    genügte.
    """
    from app.ui.theme import THEMES

    for name, theme in THEMES.items():
        ratio = contrast_ratio(theme["highlight_pressed"], theme["highlight_text"])
        assert ratio >= 4.5, f"{name}: der gedrückte Knopf trägt nur {ratio:.3f} Kontrast"
        # Und er bleibt vom Ruhezustand zu unterscheiden — sonst wäre die
        # Rückmeldung wieder weg, für die die Farbe überhaupt entstanden ist.
        apart = contrast_ratio(theme["highlight"], theme["highlight_pressed"])
        assert apart >= 1.7, f"{name}: gedrückt sieht aus wie losgelassen ({apart:.3f})"


def test_a_legend_field_carries_readable_text_on_every_step() -> None:
    """Die Schrift auf einem Farbfeld wird gerechnet, nicht geschätzt.

    ``_readable_on`` entschied an einer festen Luminanzschwelle von 0,35, und
    eine feste Zahl ist immer nur für eine Rampe richtig: Über den mittleren
    Tönen von Viridis kippte sie auf die schlechtere der beiden Schriften —
    3,47 bei ``#21918c`` und 2,56 bei ``#28ae80``. Verglichen wird jetzt, was
    der Vergleich entscheiden soll: die zwei Kontraste gegeneinander.
    """
    pytest.importorskip("PySide6")

    from app.ui.analysis_bar import _readable_on

    for colour in VIRIDIS:
        ratio = contrast_ratio(_readable_on(colour), colour)
        assert ratio >= 4.5, f"Legendenfeld {colour} trägt nur {ratio:.2f} Kontrast"


def test_the_layer_roles_differ_in_more_than_colour() -> None:
    """Kontur, Insel und Überhang liegen im selben Bild übereinander.

    Unterschieden wurden sie allein durch die Farbe — drei gleich dicke Ringe,
    ohne Legende (Regel 18). Jetzt trägt jede Rolle ihre eigene Strichstärke,
    und die Ablesezeile nennt sie beim Namen.
    """
    from app.ui.palette import LAYER_WIDTHS

    assert set(LAYER_WIDTHS) == {"layer", "island", "overhang"}
    widths = sorted(LAYER_WIDTHS.values())
    assert len(set(widths)) == len(widths), (
        "Zwei Rollen mit derselben Strichstärke unterscheiden sich wieder nur in der Farbe."
    )


@pytest.mark.parametrize("name", list(DIFF_PALETTES))
def test_the_difference_legend_gives_each_entry_its_own_colour(name: str) -> None:
    """Eine Legende, die beide Einträge gleich färbt, sagt das Falsche.

    Die ganze Zeile stand in der Farbe von „Hinzugefügt" — auch das Wort
    „Entfernt". In Graustufen kam sie damit auf 1,16 gegen ihr Band. Jedes Feld
    trägt jetzt seine eigene Kodierungsfarbe, und die Schrift darauf wird
    gerechnet statt geraten.
    """
    from app.ui.palette import readable_on

    palette = DIFF_PALETTES[name]  # type: ignore[index]
    for encoding in (palette.added, palette.removed):
        ratio = contrast_ratio(readable_on(encoding.colour), encoding.colour)
        assert ratio >= 4.5, f"{name}/{encoding.label_key}: nur {ratio:.2f} auf dem Feld"

    assert palette.added.colour != palette.removed.colour or name == "greyscale", (
        "Zwei Kodierungen, eine Farbe — dann trägt allein das Zeichen."
    )
