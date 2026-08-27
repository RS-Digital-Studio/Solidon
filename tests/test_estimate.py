"""Die Schätzung ohne Schnitt (Bauplan §22, §29).

Geprüft wird gegen analytische Körper, deren Volumen und Oberfläche man von
Hand ausrechnen kann — ein Würfel, eine Kugel, ein dünnes Blech, ein Stab.

**Und gegen vier gemessene Zahlen.** Der Rest dieser Datei hält die Rechnung an
ihren Rändern; ``test_the_estimate_stays_close_to_what_the_slicer_measured``
hält sie an der Wirklichkeit. Die Werte darin kommen aus einem Lauf gegen
PrusaSlicer 2.9.6 mit abgeschalteter Haftung — ohne diesen Test war die
Schätzung fünf bis zweiundzwanzig Prozent zu hoch, ohne dass eine Zeile davon
wusste.

Der Test daneben, ``test_a_frame_costs_far_more_than_a_block_of_the_same_size``,
hält die andere Hälfte: Es gab einen Zwischenstand, der die Schale aus den
Hüllmaßen rechnete und damit die vier Körper hier auf zwei Prozent traf — und
bei zwei Regalteilen 41 und 49 Prozent zu niedrig lag, weil ein Hüllquader
einen Rahmen für einen Klotz hält.
"""

from __future__ import annotations

import dataclasses

import pytest

from app.core.knowledge import print_settings, profiles
from app.core.slice.estimate import core_share, estimate, flow_rate, shell_thickness, total

#: Ein Würfel von 20 mm — der Körper, an dem jede Druckerrechnung anfängt.
CUBE = (20.0**3, 6 * 20.0**2)


@pytest.fixture
def settings() -> object:
    """Die aufgelösten Einstellungen für den Vorgabedrucker."""
    profile = profiles.make_profile(profiles.DEFAULT_PRINTER, profiles.DEFAULT_MATERIAL)
    return print_settings.resolve(profile)


def test_a_solid_block_never_needs_more_than_it_is(settings: object) -> None:
    """Ein Würfel von 20 mm ist 8 cm³ — mehr kann nicht hineingehen.

    Der Fall, an dem eine Schätzung als Erstes kippt: Käme die Schale aus
    „Fläche mal Dicke", wäre sie bei einem kleinen, kompakten Körper dicker als
    der Körper selbst. Als Differenz zweier Körper kann das nicht passieren —
    und das ist der Grund, warum die Deckelung von früher verschwunden ist.
    """
    result = estimate(*CUBE, settings)  # type: ignore[arg-type]

    assert result.material_mm3 <= CUBE[0], "nie mehr Material als Volumen"
    assert result.material_mm3 > 0.0
    assert result.grams > 0.0
    assert result.seconds > 0.0


def test_a_hollow_body_costs_more_than_its_volume_suggests(settings: object) -> None:
    """Der Grund, warum überhaupt zwischen Schale und Kern getrennt wird.

    Zwei Körper mit demselben Volumen: ein kompakter Würfel und ein Gehäuse,
    das dieselbe Masse auf die dreifache Kantenlänge verteilt. „Volumen mal
    Dichte" hielte sie für gleich teuer — der große ist es nicht, weil bei ihm
    fast alles Schale ist.
    """
    compact = estimate(*CUBE, settings)  # type: ignore[arg-type]
    gehaeuse = estimate(CUBE[0], 6 * 60.0**2, settings)  # type: ignore[arg-type]

    assert gehaeuse.material_mm3 > compact.material_mm3
    assert gehaeuse.grams > compact.grams


def test_a_thin_sheet_is_printed_solid(settings: object) -> None:
    """Ein Blech, dünner als seine Deckel, hat keine Füllung.

    Dann ist das Material genau das Volumen — nicht mehr (das wäre unmöglich)
    und nicht weniger (dünner als die Deckellagen wird nichts hohl gedruckt).
    """
    volume = 100.0 * 100.0 * 0.6

    result = estimate(volume, 2 * 100.0 * 100.0, settings)  # type: ignore[arg-type]

    assert result.material_mm3 == pytest.approx(volume)


def test_more_infill_costs_more(settings: object) -> None:
    """Die Fülldichte muss durchschlagen, sonst rechnet sie niemand."""
    body = (50.0**3, 6 * 50.0**2)
    sparse = dataclasses.replace(
        settings,  # type: ignore[type-var]
        infill=dataclasses.replace(settings.infill, density=0.1),  # type: ignore[attr-defined]
    )
    dense = dataclasses.replace(
        settings,  # type: ignore[type-var]
        infill=dataclasses.replace(settings.infill, density=0.9),  # type: ignore[attr-defined]
    )

    assert estimate(*body, dense).material_mm3 > estimate(*body, sparse).material_mm3


def test_nothing_costs_nothing(settings: object) -> None:
    """Ein leeres Ergebnis ist keine Null-Division und kein Fehler.

    Der Fall tritt bei jedem neuen Projekt ein — die Anzeige fragt, bevor
    etwas da ist.
    """
    empty = estimate(0.0, 0.0, settings)  # type: ignore[arg-type]
    assert (empty.material_mm3, empty.grams, empty.seconds) == (0.0, 0.0, 0.0)

    assert total([], settings).seconds == 0.0  # type: ignore[arg-type]


def test_two_bodies_cost_more_than_one(settings: object) -> None:
    """Summiert wird das Ergebnis, nicht die Eingabe.

    Zwei getrennte Körper haben zusammen mehr Schale als einer mit demselben
    Volumen — jeder bekommt seine eigene.
    """
    one = total([CUBE], settings)  # type: ignore[arg-type]
    two = total([CUBE] * 2, settings)  # type: ignore[arg-type]

    assert two.material_mm3 == pytest.approx(2 * one.material_mm3)
    assert two.seconds == pytest.approx(2 * one.seconds)


def test_the_flow_never_exceeds_what_the_filament_allows(settings: object) -> None:
    """Der Volumenstrom ist die Grenze, die kein Feld zeigt (§29).

    Eine Zeitschätzung, die darüber hinausrechnet, verspricht einen Druck,
    den die Maschine nicht liefert.
    """
    fast = dataclasses.replace(
        settings,  # type: ignore[type-var]
        speed=dataclasses.replace(settings.speed, infill=10_000.0),  # type: ignore[attr-defined]
    )
    assert flow_rate(fast) <= fast.filament.max_flow


def test_the_shell_follows_the_wall_count(settings: object) -> None:
    """Mehr Wände heißt dickere Schale — sonst ist die Zahl Zierde."""
    thick = dataclasses.replace(
        settings,  # type: ignore[type-var]
        shell=dataclasses.replace(settings.shell, wall_count=6),  # type: ignore[attr-defined]
    )
    assert shell_thickness(thick) > shell_thickness(settings)  # type: ignore[arg-type]
    assert core_share(*CUBE, thick) < core_share(*CUBE, settings)  # type: ignore[arg-type]


def test_a_frame_costs_far_more_than_a_block_of_the_same_size(settings: object) -> None:
    """Der Test, der über das Modell entschieden hat.

    Ein Regalteil ist ein flacher Rahmen aus dünnen Stegen: dasselbe Hüllmaß
    wie ein Klotz, ein Bruchteil des Volumens, und **viel** mehr Oberfläche.
    Ein Zwischenstand rechnete die Schale aus den Hüllmaßen und hielt den
    Rahmen für einen flachen Klotz — gemessen lag er damit bei zwei
    Regalteilen 41 und 49 Prozent zu niedrig.

    Über die mittlere Wanddicke ``3V/A`` kann das nicht passieren: Ein Rahmen
    aus 3 mm Stegen hat eine mittlere Dicke von 3 mm, und davon bleibt hinter
    1,26 mm Wand fast nichts als Kern übrig.
    """
    # 160 auf 231 auf 14, Stege von 3 mm — die Maße des Regalfußes.
    rahmen = estimate(52_000.0, 62_000.0, settings)  # type: ignore[arg-type]
    klotz = estimate(52_000.0, 9_000.0, settings)  # type: ignore[arg-type]

    # 89 Prozent des Volumens sind Schale — der Kern ist bei 2,5 mm mittlerer
    # Dicke hinter 1,26 mm Wand fast weg.
    assert rahmen.material_mm3 > 0.85 * 52_000.0, "ein Rahmen ist fast ganz Schale"
    assert rahmen.material_mm3 > 2.0 * klotz.material_mm3


def test_the_estimate_stays_close_to_what_the_slicer_measured(settings: object) -> None:
    """Vier Körper, vier Messungen — der einzige Test hier, der die Rechnung an
    der Wirklichkeit hält.

    Gemessen mit PrusaSlicer 2.9.6 auf einem Elegoo Centauri Carbon 2, PETG,
    Haftung ausgeschaltet, damit der Skirt die Zahl nicht mitträgt. Die
    Schätzung darf abweichen — sie kennt keine Fahrwege und keine Nahtstellen —,
    aber nicht um ein Sechstel: Genau das war der Stand, als die Schale als
    „Fläche mal Dicke" gerechnet wurde.

    | Körper | gemessen | vorher | jetzt |
    |---|---|---|---|
    | Würfel 20 mm | 4,15 g | +15 % | +5,9 % |
    | Kugel r 15 | 6,21 g | +5 % | +0,1 % |
    | Blech 60 auf 60 auf 2 | 8,61 g | +6 % | -9,0 % |
    | Stab 120 auf 12 auf 12 | 9,43 g | +22 % | +9,9 % |

    Die Schwelle steht bei zwölf Prozent und nicht bei fünf: Was der Slicer aus
    einem Körper macht, hängt an Dingen, die Solidon bewusst nicht nachbaut
    (§22) — Nahtstellen, Lückenfüllung, die Frage, ob die dritte Wand in einen
    12-mm-Querschnitt noch hineinpasst. Was sie **nicht** durchlässt, ist der
    Aufschlag von vorher: der lag bei allen vier auf derselben Seite.
    """
    petg = profiles.make_profile("centauri-carbon-2", "petg")
    fein = dataclasses.replace(
        print_settings.resolve(petg),
        adhesion=dataclasses.replace(print_settings.resolve(petg).adhesion, kind="none"),
    )
    gemessen = (
        ("Würfel", 8000.0, 2400.0, 4.15),
        ("Kugel", 14107.0, 2824.0, 6.21),
        ("Blech", 7200.0, 7680.0, 8.61),
        ("Stab", 17280.0, 6048.0, 9.43),
    )

    for name, volume, area, gramm in gemessen:
        result = estimate(volume, area, fein)
        abweichung = result.grams / gramm - 1.0
        assert abs(abweichung) < 0.12, f"{name}: {result.grams:.2f} g gegen {gramm:.2f} g gemessen"
