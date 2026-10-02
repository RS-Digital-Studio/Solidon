"""Listenhaken und runde Farbpunkte (RM-342, D-N7).

Beide hatten keinen Test: die Haken, die in einer markierten Zeile im dunklen
Thema sonst unsichtbar werden, und der runde Farbpunkt, der neben einem Haken
nicht wie ein zweites Kästchen aussehen soll.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication

from app.ui import style
from app.ui.filament_picker import swatch


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_every_check_state_gets_its_own_picture(qt_app: QApplication, theme: str) -> None:
    """Sechs Bilder je Thema, gesperrt in der Sperrfarbe, sonst in Text- und Linienfarbe."""
    paths = style.check_files(theme)  # type: ignore[arg-type]
    assert paths is not None
    assert set(paths) == {
        "unchecked",
        "checked",
        "indeterminate",
        "unchecked-disabled",
        "checked-disabled",
        "indeterminate-disabled",
    }
    colours = style.THEMES[theme]  # type: ignore[index]
    checked = Path(paths["checked"]).read_text(encoding="utf-8")
    locked = Path(paths["checked-disabled"]).read_text(encoding="utf-8")
    assert colours["text"] in checked and colours["disabled"] not in checked
    assert colours["disabled"] in locked

    rules = style._check_rules(paths)
    for state, path in paths.items():
        assert path in rules, state
    assert style._check_rules(None) == "", "ohne Bilder zeichnet Qt selbst"


def _alpha(icon_size: int, colour: object, x: int, y: int, **kwargs: object) -> QColor:
    image = swatch(colour, icon_size, **kwargs).pixmap(icon_size, icon_size).toImage()  # type: ignore[arg-type]
    return image.pixelColor(x, y)


def test_a_swatch_is_round_and_split_into_its_colours(qt_app: QApplication) -> None:
    """Der Punkt ist rund — die Ecke bleibt leer —, und zwei Farben teilen ihn."""
    size = 24
    # Nicht der Pixel (0, 0): Den lässt auch ein eckiger Punkt frei, weil die
    # Scheibe einen Bildpunkt Rand hat (D-N7). (2, 2) liegt im Quadrat der
    # Scheibe, aber außerhalb des Kreises; die Mitte der Oberkante liegt in beiden.
    assert _alpha(size, "#ff0000", 2, 2).alpha() == 0, "die Ecke eines Kreises ist leer"
    assert _alpha(size, "#ff0000", size // 2, 2).alpha() > 200, "die Oberkante ist gefüllt"
    left = _alpha(size, "#ff0000 #0000ff", size // 4, size // 2)
    right = _alpha(size, "#ff0000 #0000ff", 3 * size // 4, size // 2)
    assert left.red() > 200 and left.blue() < 60
    assert right.blue() > 200 and right.red() < 60


def test_an_empty_swatch_is_empty_unless_it_should_show_a_ring(qt_app: QApplication) -> None:
    """„Keine Farbe“ ist kein weißer Punkt; wo es eine Auskunft ist, steht der Rand."""
    size = 24
    plain = swatch(None, size).pixmap(size, size).toImage()
    assert all(plain.pixelColor(x, y).alpha() == 0 for x in range(size) for y in range(size))
    ringed = swatch(None, size, ring_when_empty=True).pixmap(size, size).toImage()
    assert any(ringed.pixelColor(x, size // 2).alpha() > 0 for x in range(size))
    assert ringed.pixelColor(size // 2, size // 2).alpha() == 0, "innen bleibt er leer"
