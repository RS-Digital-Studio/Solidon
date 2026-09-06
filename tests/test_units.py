"""Millimeter, doppelte Genauigkeit, und nie ein nacktes ``==`` (Bauplan
§11).
"""

from __future__ import annotations

import math

import pytest

from app.core.units import (
    EPS_DISPLAY,
    EPS_GEOM,
    LengthUnit,
    clamp,
    format_area,
    format_length,
    format_volume,
    from_mm,
    is_close,
    is_greater,
    is_less,
    is_zero,
    match_tolerance,
    quantize,
    round_display,
    to_mm,
    weld_tolerance,
)


def test_import_conversion_hits_the_core_unit() -> None:
    assert to_mm(1.0, "in") == pytest.approx(25.4)
    assert to_mm(1.0, "cm") == pytest.approx(10.0)
    assert to_mm(1.0, "m") == pytest.approx(1000.0)
    assert to_mm(3.5, "mm") == pytest.approx(3.5)


def test_display_conversion_is_the_exact_inverse() -> None:
    for unit in ("mm", "cm", "m", "in"):
        assert from_mm(to_mm(7.25, unit), unit) == pytest.approx(7.25)


def test_comparisons_use_the_geometry_tolerance() -> None:
    assert is_close(1.0, 1.0 + EPS_GEOM / 2)
    assert not is_close(1.0, 1.0 + EPS_GEOM * 10)
    assert is_zero(EPS_GEOM / 2)
    assert is_greater(1.0, 1.0 - 10 * EPS_GEOM)
    assert not is_greater(1.0, 1.0)
    assert is_less(1.0 - 10 * EPS_GEOM, 1.0)


def test_clamp_keeps_the_range() -> None:
    assert clamp(5.0, 0.0, 1.0) == 1.0
    assert clamp(-5.0, 0.0, 1.0) == 0.0
    assert clamp(0.5, 0.0, 1.0) == 0.5
    with pytest.raises(ValueError):
        clamp(0.5, 1.0, 0.0)


def test_match_tolerance_scales_with_the_model() -> None:
    assert match_tolerance(1000.0) == pytest.approx(5.0)
    # Kleine Modelle fallen nie unter die Anzeigetoleranz.
    assert match_tolerance(0.1) == pytest.approx(EPS_DISPLAY)


def test_weld_tolerance_never_drops_below_the_geometry_tolerance() -> None:
    assert weld_tolerance(0.0) == EPS_GEOM
    assert weld_tolerance(100.0) == pytest.approx(1e-4)


def test_rounding_happens_only_for_display() -> None:
    assert round_display(4.19999) == pytest.approx(4.2)
    assert round_display(-4.19999) == pytest.approx(-4.2)
    assert quantize(0.005) == pytest.approx(0.01)
    assert quantize(-0.005) == pytest.approx(-0.01)
    with pytest.raises(ValueError):
        quantize(1.0, 0.0)


def test_a_volume_keeps_its_meaning_at_every_size() -> None:
    """§19.3: Eine Nachkommastelle Kubikzentimeter ist unter einem
    Kubikzentimeter keine Auskunft mehr.

    Ein Teil von zwei Millimetern Kantenlaenge stand im Pruefbericht als
    "0,0 cm3", und die Ueberschneidungswarnung meldete fuer einen Streifschuss
    von einem Kubikmillimeter dasselbe wie fuer zwei Teile, die zur Haelfte
    ineinander stecken — genau den Unterschied, den sie zeigen soll. Oben
    dasselbe von der anderen Seite: 30 000 cm3 auf ein Zehntel genau behauptet
    eine Messung, die es nicht gibt.
    """
    assert format_volume(4.0) == "4 mm³"
    assert format_volume(999.0) == "999 mm³"
    assert format_volume(1000.0) == "1.0 cm³"
    assert format_volume(12500.0) == "12.5 cm³"
    assert format_volume(30_000_000.0) == "30000 cm³"

    # In Zoll bleibt es bei Kubikzoll — zwei Systeme in einer Zeile waeren
    # schlimmer als eine kleine Zahl. Die Stellen wachsen, bis zwei geltende
    # Ziffern dastehen.
    assert format_volume(4.0, "in") == "0.00024 in³"
    assert format_volume(12500.0, "in") == "0.76 in³"
    assert float(format_volume(1.0, "in").split()[0]) > 0.0, (
        "was nicht null ist, sieht nicht so aus"
    )

    # **Und dieselbe Zusage in Millimetern.** Sie galt nur in Zoll, und der
    # Fall darunter ist kein erdachter: Ein Bildmodell normiert seine Ausgabe
    # auf einen Einheitswürfel, ein erzeugtes Netz misst also Zehntel eines
    # Kubikmillimeters. Gemessen an einem echten Wurf durch ComfyUI: 0,125 mm³,
    # angezeigt als „0 mm³" — neben „geschlossen" in derselben Zeile des
    # Erzeugungsdialogs, und ein geschlossener Körper ohne Volumen ist keiner.
    assert format_volume(0.1248) == "0.12 mm³"
    assert format_volume(0.005) == "0.0050 mm³", "die Stellen wachsen wie in Zoll"
    assert float(format_volume(0.1248).split()[0]) > 0.0, (
        "was nicht null ist, sieht auch in Millimetern nicht so aus"
    )
    # Null bleibt null, und ab einem Kubikmillimeter ändert sich nichts.
    assert format_volume(0.0) == "0 mm³"
    assert format_volume(1.0) == "1 mm³"


@pytest.mark.parametrize(
    ("value", "unit", "expected"),
    [
        (1e-9, "mm", "<0.00001 mm³"),
        (-1e-9, "mm", ">-0.00001 mm³"),
        (1e-9, "in", "<0.00001 in³"),
        (-1e-9, "in", ">-0.00001 in³"),
        (1e-9 * 25.4**3, "in", "<0.00001 in³"),
        (-1e-9 * 25.4**3, "in", ">-0.00001 in³"),
        (0.0, "mm", "0 mm³"),
        (0.0, "in", "0.00 in³"),
        (0.00001, "mm", "0.00001 mm³"),
        (-0.00001, "mm", "-0.00001 mm³"),
        (math.nextafter(0.00001, 0.0), "mm", "<0.00001 mm³"),
        (-math.nextafter(0.00001, 0.0), "mm", ">-0.00001 mm³"),
        (math.nextafter(0.00001, math.inf), "mm", "0.00001 mm³"),
        (-math.nextafter(0.00001, math.inf), "mm", "-0.00001 mm³"),
        (0.000009 * 25.4**3, "in", "<0.00001 in³"),
        (-0.000009 * 25.4**3, "in", ">-0.00001 in³"),
        (0.00001 * 25.4**3, "in", "0.00001 in³"),
        (-0.00001 * 25.4**3, "in", "-0.00001 in³"),
        (0.00002 * 25.4**3, "in", "0.00002 in³"),
        (-0.00002 * 25.4**3, "in", "-0.00002 in³"),
    ],
)
def test_tiny_volumes_keep_their_sign_and_display_bound(
    value: float, unit: LengthUnit, expected: str
) -> None:
    """Nichtnull bleibt als Schranke sichtbar; an der Grenze stehen wieder Zahlen."""
    assert format_volume(value, unit) == expected


def test_formatting_matches_the_display_precision() -> None:
    assert format_length(4.2) == "4.20 mm"
    assert format_length(25.4, "in") == "1.0000 in"
    assert format_length(4.2, with_unit=False) == "4.20"
    assert not format_length(-0.001).startswith("-")


def test_an_area_follows_the_display_unit() -> None:
    """Länge und Volumen folgten der Umschaltung seit je, die Fläche nicht.

    Wer in Zoll arbeitete, sah Maße in Zoll, Volumen in Kubikzoll — und
    daneben "4334 mm²". Vier Stellen der Oberfläche zeigen Flächen, und alle
    vier hatten die Einheit fest eingebaut.

    Kleine Flächen bleiben sichtbar; ab einem Quadratmillimeter genügt die
    ganze Zahl. In Zoll wachsen die Stellen wie beim Volumen.
    """
    assert format_area(4334.0) == "4334 mm²"
    assert format_area(0.6) == "0.60 mm²"
    assert format_area(645.16, "in") == "1.00 in²"
    assert format_area(4334.0, "in") == "6.72 in²"
    assert float(format_area(1.0, "in").split()[0]) > 0.0, "was nicht null ist, sieht nicht so aus"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0.0, "0 mm²"),
        (1.0, "1 mm²"),
        (0.125, "0.12 mm²"),
        (0.005, "0.0050 mm²"),
        (0.00001, "0.00001 mm²"),
        (0.000009, "<0.00001 mm²"),
        (1e-12, "<0.00001 mm²"),
        (-0.005, "-0.0050 mm²"),
        (-1e-12, ">-0.00001 mm²"),
    ],
)
def test_small_layer_areas_never_disappear_in_rounding(value: float, expected: str) -> None:
    """Vorhandene Schichten und Überhänge bleiben auch unter der Anzeigegrenze erkennbar."""
    assert format_area(value) == expected


def test_tiny_square_inches_show_a_bound_instead_of_zero() -> None:
    """Die Zusage kleiner Flächen gilt auch nach der Einheitenumrechnung."""
    assert format_area(1e-9, "in") == "<0.00001 in²"
    assert format_area(-1e-9, "in") == ">-0.00001 in²"
    assert format_area(0.0, "in") == "0.00 in²"
