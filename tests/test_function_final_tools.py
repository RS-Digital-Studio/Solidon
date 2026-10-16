"""Werkzeug für den Schlusslauf am echten Fenster (Plan Schluss §1.5, Entscheidungen §6).

Was der Prüfstand für die Punkte braucht, die der finale Lauf nicht belegen
konnte: 125 % (FD-109), die Inhaltsschrift 14 und 18 pt samt Wechsel
(FD-54, 57, 58, 185), das Bild im gehaltenen Zug (FD-73), der Weg aus dem
Verlauf in den Zeichenmodus, die Kurzhilfe am grauen *Übernehmen* (FD-99), der
Tastaturweg ab der Reiterleiste (FD-177), der zweite Schritt eines Wegs
(FD-36) und eine Gesamtfrist für ``file_acceptance run``. Ohne natives
Fenster; die Fälle mit ``qt_app`` laufen offscreen.
"""

from __future__ import annotations

from tools import function_setup
from tools.function_checks import SCALES, SMALLEST_AVAILABLE

#: Der Messschirm des Schlusslaufs (MSI MAG271CQR): 2560 x 1440 bei 100 %, die
#: Taskleiste 48 Punkte hoch.
MSI: tuple[int, int] = (2560, 1440)
TASKBAR = 48


def _logical(scale: float) -> list[int]:
    """Die verfügbare logische Fläche des Messschirms bei ``scale`` (wie ``availableGeometry``)."""
    return [0, 0, int(MSI[0] / scale), int((MSI[1] - TASKBAR) / scale)]


def test_125_percent_is_a_case_on_the_measuring_screen_and_150_200_are_not() -> None:
    """FD-109 „bei 125 %“: 2048 x 1152 logisch am MSI, ein gültiger Fall (Entscheidung §6.3).

    150 und 200 % drücken den Schirm unter die kleinste Arbeitsfläche; das
    Protokoll nennt dann den Grund, statt zu messen.
    """
    assert 1.25 in SCALES
    scaled = {
        entry["scale"] for entry in function_setup.variant_sets()["skalierung"] if "scale" in entry
    }
    assert scaled == {scale for scale in SCALES if scale != 1.0}
    assert (int(MSI[0] / 1.25), int(MSI[1] / 1.25)) == (2048, 1152)
    quarter = function_setup.Variant.of({"set": "skalierung", "scale": 1.25})
    area = _logical(1.25)
    assert area[2] >= SMALLEST_AVAILABLE[0] and area[3] >= SMALLEST_AVAILABLE[1]
    assert function_setup.below_smallest({"screen": "MSI", "geometry": area}, quarter) == ""
    for scale in (1.5, 2.0):
        variant = function_setup.Variant.of({"set": "skalierung", "scale": scale})
        reason = function_setup.below_smallest(
            {"screen": "MSI", "geometry": _logical(scale)}, variant
        )
        assert "kein Fall" in reason and "kleinsten Arbeitsfläche" in reason, reason
