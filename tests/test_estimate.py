"""Die Schätzung ohne Schnitt (Bauplan §22, §29).

Geprüft wird gegen analytische Körper, deren Volumen und Oberfläche man von
Hand ausrechnen kann — ein Würfel, ein hohler Würfel, ein dünnes Blech. Was
diese Datei sicherstellt, ist nicht die Genauigkeit gegen einen echten Drucker
(dafür gibt es die G-Code-Gegenprobe, §28.2), sondern dass die Rechnung sich
in die richtige Richtung bewegt und an ihren Rändern nicht kippt.
"""

from __future__ import annotations

import pytest

from app.core.knowledge import print_settings, profiles
from app.core.slice.estimate import estimate, flow_rate, shell_thickness, total


@pytest.fixture
def settings() -> object:
    """Die aufgelösten Einstellungen für den Vorgabedrucker."""
    profile = profiles.make_profile(profiles.DEFAULT_PRINTER, profiles.DEFAULT_MATERIAL)
    return print_settings.resolve(profile)


def test_a_solid_block_never_needs_more_than_it_is(settings: object) -> None:
    """Ein Würfel von 20 mm ist 8 cm³ — mehr kann nicht hineingehen.

    Der Fall, an dem eine Schätzung als Erstes kippt: die Schale wird über die
    Oberfläche gerechnet, und bei einem kleinen, kompakten Körper wäre sie
    ohne Deckelung dicker als der Körper selbst.
    """
    volume = 20.0**3
    area = 6 * 20.0**2

    result = estimate(volume, area, settings)  # type: ignore[arg-type]

    assert result.material_mm3 <= volume, "nie mehr Material als Volumen"
    assert result.material_mm3 > 0.0
    assert result.grams > 0.0
    assert result.seconds > 0.0


def test_a_hollow_body_costs_more_than_its_volume_suggests(settings: object) -> None:
    """Der Grund, warum die Oberfläche mitgerechnet wird.

    Zwei Körper mit demselben Volumen: einer kompakt, einer ausgehöhlt mit
    viel Fläche. „Volumen mal Dichte" hielte sie für gleich teuer — der
    ausgehöhlte ist es nicht, weil seine Schale fast alles ist.
    """
    volume = 20.0**3
    compact = estimate(volume, 6 * 20.0**2, settings)  # type: ignore[arg-type]
    hollow = estimate(volume, 6 * 20.0**2 * 4, settings)  # type: ignore[arg-type]

    assert hollow.material_mm3 > compact.material_mm3
    assert hollow.grams > compact.grams


def test_a_thin_sheet_is_printed_solid(settings: object) -> None:
    """Ein Blech, dünner als seine Schale, hat keine Füllung.

    Dann ist das Material genau das Volumen — nicht mehr (das wäre unmöglich)
    und nicht weniger (dünner als die Wandstärke wird nichts hohl gedruckt).
    """
    volume = 100.0 * 100.0 * 0.6
    area = 2 * 100.0 * 100.0

    result = estimate(volume, area, settings)  # type: ignore[arg-type]

    assert result.material_mm3 == pytest.approx(volume)


def test_more_infill_costs_more(settings: object) -> None:
    """Die Fülldichte muss durchschlagen, sonst rechnet sie niemand."""
    import dataclasses

    volume = 50.0**3
    area = 6 * 50.0**2

    sparse = dataclasses.replace(
        settings,  # type: ignore[type-var]
        infill=dataclasses.replace(settings.infill, density=0.1),  # type: ignore[attr-defined]
    )
    dense = dataclasses.replace(
        settings,  # type: ignore[type-var]
        infill=dataclasses.replace(settings.infill, density=0.9),  # type: ignore[attr-defined]
    )

    assert estimate(volume, area, dense).material_mm3 > estimate(volume, area, sparse).material_mm3


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

    Zwei getrennte Körper haben zusammen mehr Oberfläche als einer mit
    demselben Volumen — jeder bekommt seine eigene Schale.
    """
    one = total([(20.0**3, 6 * 20.0**2)], settings)  # type: ignore[arg-type]
    two = total([(20.0**3, 6 * 20.0**2)] * 2, settings)  # type: ignore[arg-type]

    assert two.material_mm3 == pytest.approx(2 * one.material_mm3)
    assert two.seconds == pytest.approx(2 * one.seconds)


def test_the_flow_never_exceeds_what_the_filament_allows(settings: object) -> None:
    """Der Volumenstrom ist die Grenze, die kein Feld zeigt (§29).

    Eine Zeitschätzung, die darüber hinausrechnet, verspricht einen Druck,
    den die Maschine nicht liefert.
    """
    import dataclasses

    fast = dataclasses.replace(
        settings,  # type: ignore[type-var]
        speed=dataclasses.replace(settings.speed, infill=10_000.0),  # type: ignore[attr-defined]
    )
    assert flow_rate(fast) <= fast.filament.max_flow


def test_the_shell_follows_the_wall_count(settings: object) -> None:
    """Mehr Wände heißt dickere Schale — sonst ist die Zahl Zierde."""
    import dataclasses

    thick = dataclasses.replace(
        settings,  # type: ignore[type-var]
        shell=dataclasses.replace(settings.shell, wall_count=6),  # type: ignore[attr-defined]
    )
    assert shell_thickness(thick) > shell_thickness(settings)  # type: ignore[arg-type]
