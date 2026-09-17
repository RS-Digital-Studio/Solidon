"""Millimeter, doppelte Genauigkeit, und nie ein nacktes ``==`` (Bauplan
§11).
"""

from __future__ import annotations

import math
import struct

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


# --- Das Vorzeichen einer gemessenen Achse ---------------------------------------


def signs_of(axis: tuple[float, float, float]) -> tuple[str, ...]:
    """Die Vorzeichen, wie sie eine Datei schreibt — ``==`` sieht sie nicht.

    ``-0.0 == 0.0`` ist wahr; ``json.dumps`` und jede Textform trennen die
    beiden trotzdem. Gefragt ist genau diese Trennung.
    """
    return tuple(f"{value:.1f}" for value in axis)


@pytest.mark.parametrize(
    "axis",
    [
        (1.0, -0.0, 0.0),
        (0.0, -0.0, 1.0),
        (-1.0, -0.0, 0.0),
        (-0.0, -0.0, -1.0),
    ],
)
def test_a_measured_axis_never_carries_a_negative_zero(axis: tuple[float, ...]) -> None:
    """Die Zusage gilt in beiden Zweigen, nicht nur im gespiegelten.

    Bis zum 13.09.2026 strich nur der gespiegelte Zweig die negative Null;
    ``positive_axis((1.0, -0.0, 0.0))`` gab sie unverändert zurück. Zwei
    Schlüssel, die dieselbe Achse meinen, standen damit als ``0.0`` und
    ``-0.0`` nebeneinander — im Cache-Schlüssel und in der Projektdatei.
    """
    from app.core.units import positive_axis

    found = positive_axis(axis)

    assert "-0.0" not in signs_of(found), f"negative Null in {found}"
    assert math.isclose(sum(abs(value) for value in found), sum(abs(value) for value in axis))


def test_a_measured_axis_keeps_its_line_and_turns_the_leading_sign() -> None:
    """Gespiegelt wird die ganze Achse, und zwar an der größten Komponente.

    Nicht an der ersten Zahl: ``(-3 | 4 | 0)`` hat sein Maximum bei ``4``, und
    das ist bereits positiv — die Achse bleibt, wie sie ist.
    """
    from app.core.units import positive_axis

    assert positive_axis((-3.0, 4.0, 0.0)) == (-3.0, 4.0, 0.0)
    assert positive_axis((3.0, -4.0, 0.0)) == (-3.0, 4.0, 0.0), "|−4| ist das Maximum"
    assert positive_axis((-4.0, 3.0, 0.0)) == (4.0, -3.0, 0.0)
    assert positive_axis((0.0, 0.0, -1.0)) == (0.0, 0.0, 1.0)


# --- Winkelfunktionen, die auf jeder Maschine dieselbe Zahl geben (RM-187) --------


def test_circle_points_are_the_same_bits_on_every_machine() -> None:
    """Die festgeschriebenen Bits eines 120-Ecks — der eigentliche Vertrag.

    **Warum ausgerechnet Bits und nicht ``is_close``** (Regel 6 gilt hier
    ausdrücklich nicht): Die Zusage *ist* die bitgenaue Gleichheit. Gemessen am
    17.09.2026 über drei CI-Runner mit demselben Python und demselben NumPy
    liefert ``np.cos`` drei verschiedene Zahlenfolgen — Ubuntu rechnet mit
    AVX-512, Windows mit AVX2, macOS mit NEON. Der Unterschied betrug
    3,4·10⁻¹⁵ mm und wuchs durch eine Boolesche Operation zu 1224, 1226 und
    1228 Dreiecken an demselben Körper. Ein Test mit Toleranz hätte das nie
    gesehen, und genau deshalb hat es niemand gesehen.

    Der Hash steht hier als Zahl und nicht als Formel: Eine Formel würde
    dieselbe Bibliothek fragen, über die der Test urteilt.

    **Woher die Zahl kommt und was sie noch nicht beweist.** Sie ist auf dieser
    Maschine gemessen — ein Sollwert aus dem Prüfling also, und der ist nur
    erlaubt, weil dies ein Determinismusnachweis ist und der Test das sagt
    (`.claude/rules/tests.md`, „Korpus"). Dass sie auf **jeder** Maschine
    dieselbe ist, belegt nicht dieser Lauf, sondern der über drei Runner. Wird
    er auf einem davon rot, ist genau das die Aussage: Dort rechnet etwas
    anders, und die Zusage gilt nicht.
    """
    import hashlib

    from app.core.units import circle_cos_sin

    values = circle_cos_sin(120)
    raw = b"".join(struct.pack("<dd", cos, sin) for cos, sin in values)
    digest = hashlib.sha256(raw).hexdigest()[:16]

    assert len(values) == 120
    assert digest == "169ba88212acfdba", f"andere Bits als festgeschrieben: {digest}"


def test_a_circle_point_lands_on_the_circle() -> None:
    """Jede Ecke liegt auf dem Einheitskreis, und zwar bis auf die letzte Stelle."""
    import math

    from app.core.units import circle_point

    for sections in (3, 4, 5, 7, 8, 60, 120, 192, 360):
        for index in range(sections):
            cos, sin = circle_point(sections, index)
            assert abs(math.hypot(cos, sin) - 1.0) < 1e-15, f"{sections}-Eck, Ecke {index}"


def test_a_circle_point_matches_the_angle_it_stands_for() -> None:
    """Dieselben Werte wie ``math.cos``/``math.sin`` — nur eben überall dieselben.

    Die Zusage ist Plattformgleichheit, nicht eine andere Geometrie. Weicht
    eine Ecke mehr als eine Rundungsstelle von ihrem Winkel ab, ist die Reihe
    falsch und nicht bloß anders.
    """
    import math

    from app.core.units import circle_point

    for sections in (3, 5, 7, 60, 120, 192):
        for index in range(sections):
            angle = index * math.tau / sections
            cos, sin = circle_point(sections, index)
            assert abs(cos - math.cos(angle)) < 1e-14, f"{sections}-Eck, Ecke {index}"
            assert abs(sin - math.sin(angle)) < 1e-14, f"{sections}-Eck, Ecke {index}"


def test_no_circle_point_carries_a_negative_zero() -> None:
    """Der Viertelpunkt eines 120-Ecks gab ``-0.0``, und das trennt Schlüssel.

    Die Spiegelung, mit der drei Viertel des Kreises entstehen, dreht auch das
    Vorzeichen der Null um. ``-0.0`` schreibt sich als ``-0.000``, vergleicht
    sich gleich und sortiert sich anders — dieselbe Falle, die
    :func:`app.core.units.positive_axis` schon einmal gestellt hat.
    """
    import math

    from app.core.units import circle_cos_sin

    for sections in (4, 8, 12, 120, 360, 1920):
        for index, (cos, sin) in enumerate(circle_cos_sin(sections)):
            for value in (cos, sin):
                assert not (value == 0.0 and math.copysign(1.0, value) < 0.0), (
                    f"negative Null im {sections}-Eck an Ecke {index}"
                )


def test_a_quarter_turn_is_exact() -> None:
    """Bei einer durch vier teilbaren Teilung stehen die Viertelpunkte genau.

    ``math.cos(math.pi / 2)`` ist 6,1·10⁻¹⁷ und nicht null — der Winkel selbst
    trägt schon einen Rundungsfehler. Aus Ganzzahlen gerechnet gibt es den
    nicht, und das ist mehr als Kosmetik: Ein Kreis, dessen Viertelpunkte
    exakt auf den Achsen liegen, erzeugt koplanare Flächen, die auch koplanar
    bleiben.
    """
    from app.core.units import circle_point

    assert circle_point(120, 0) == (1.0, 0.0)
    assert circle_point(120, 30) == (0.0, 1.0)
    assert circle_point(120, 60) == (-1.0, 0.0)
    assert circle_point(120, 90) == (0.0, -1.0)
    assert circle_point(4, 1) == (0.0, 1.0)


def test_the_index_wraps_around_the_circle() -> None:
    """Ecke ``n`` ist Ecke ``0`` — ein Kreis hat keinen Rand."""
    from app.core.units import circle_point

    assert circle_point(60, 60) == circle_point(60, 0)
    assert circle_point(60, 61) == circle_point(60, 1)
    assert circle_point(60, -1) == circle_point(60, 59)


def test_a_circle_needs_at_least_three_corners() -> None:
    """Zwei Punkte sind kein Kreis, und stillschweigend geraten wird nicht."""
    import pytest

    from app.core.units import circle_cos_sin, circle_point

    for sections in (2, 1, 0, -5):
        with pytest.raises(ValueError, match="drei Ecken"):
            circle_point(sections, 0)
        with pytest.raises(ValueError, match="drei Ecken"):
            circle_cos_sin(sections)


def test_exact_cos_and_sin_agree_with_the_library() -> None:
    """Für einen beliebigen Winkel dieselbe Zahl wie ``math`` — auf dieser Maschine.

    Dass sie auf **jeder** Maschine dieselbe ist, kann kein Test hier belegen;
    das belegt der festgeschriebene Hash oben und der Lauf über drei Runner.
    Dieser Test hält nur fest, dass die Reihe rechnet und nicht rät.
    """
    import math

    from app.core.units import exact_cos, exact_sin

    for angle in (0.0, 0.7, -3.9, 1.5707963267948966, 100.0, -0.000001, math.tau * 3):
        assert abs(exact_cos(angle) - math.cos(angle)) < 1e-15, f"cos bei {angle}"
        assert abs(exact_sin(angle) - math.sin(angle)) < 1e-15, f"sin bei {angle}"
