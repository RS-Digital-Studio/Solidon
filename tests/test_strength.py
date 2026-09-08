"""Die Blattfederrechnung — was ein gedruckter Federarm aushält.

Die Rechnung selbst ist eine Zeile Schulmechanik. Was sie wert ist, zeigt
sich an den beiden Fällen, die sie am Tag ihrer Entstehung als Erstes gefunden
hat, und beide standen vorher in einem Docstring: eine Sicherheit, die
zweimal verschieden gerechnet war, und eine Spannung, die schlicht falsch
war. Beide gehören deshalb hierher — nicht als Beispiel, sondern als
Zusicherung, dass die Zahlen stimmen.
"""

from __future__ import annotations

import dataclasses
from dataclasses import replace

import pytest

from app.core.knowledge import profiles
from app.core.knowledge.strength import (
    ACROSS_LAYERS,
    cantilever_stress,
    safe_thickness,
    spring_load,
)


@pytest.fixture
def pla():
    return profiles.make_profile("centauri-carbon-2", "pla").material


def test_the_formula_matches_what_was_worked_out_by_hand(pla) -> None:
    """``sigma = 3·E·t·delta / (2·L²)`` — gegen zwei von Hand gerechnete Fälle.

    Die Klemmzunge der Auffangrinne ist der Beleg: 0,8 mm dick, 1,65 mm
    Federweg, und im Skript stehen zwei Längen mit ihren Spannungen. Beide
    Zahlen müssen herauskommen, sonst rechnet diese Funktion etwas anderes als
    der Mensch, der sie hergeleitet hat.
    """
    kurz = cantilever_stress(12.5, 0.8, 1.65, pla.youngs_modulus)
    lang = cantilever_stress(20.0, 0.8, 1.65, pla.youngs_modulus)

    assert kurz == pytest.approx(44.4, abs=0.2), "im Skript: „rund 44 MPa“"
    assert lang == pytest.approx(17.3, abs=0.2), "im Skript: „17,3 MPa“"


def test_the_length_counts_twice_as_much_as_the_thickness(pla) -> None:
    """Verdoppelte Länge viertelt, halbierte Dicke halbiert.

    Das ist der Satz, an dem eine Entwurfsentscheidung hängt: Ein Arm, der
    bricht, wird durch **Länge** gerettet und nicht durch Material. Wer die
    Dicke anfasst, bewegt die Spannung nur halb so stark.
    """
    grund = cantilever_stress(20.0, 1.0, 1.0, pla.youngs_modulus)

    assert cantilever_stress(40.0, 1.0, 1.0, pla.youngs_modulus) == pytest.approx(grund / 4.0)
    assert cantilever_stress(20.0, 0.5, 1.0, pla.youngs_modulus) == pytest.approx(grund / 2.0)


def test_the_layer_direction_decides_and_it_is_not_a_property_of_the_filament(pla) -> None:
    """Derselbe Arm trägt verschieden, je nachdem wie er liegt.

    **Und daran hing ein Rechenfehler**: Die Herleitung der Klemmzunge setzte
    den Abschlag für die kurze Länge an und ließ ihn bei der langen weg — aus
    1,73-facher Sicherheit wurden so 2,9. Zwei Zahlen aus derselben Rechnung,
    zwei verschiedene Grenzen, und keine der beiden Stellen sagte es.
    """
    quer = spring_load(pla, length=20.0, thickness=0.8, deflection=1.65, across_layers=True)
    laengs = spring_load(pla, length=20.0, thickness=0.8, deflection=1.65)
    assert quer is not None and laengs is not None

    assert quer.stress == pytest.approx(laengs.stress), "die Spannung hängt nicht an der Lage"
    assert quer.limit == pytest.approx(laengs.limit * ACROSS_LAYERS), "die Grenze schon"
    assert quer.safety == pytest.approx(1.73, abs=0.02), "nicht 2,9 — das war ohne Abschlag"


def test_a_two_millimetre_cheek_would_have_held_after_all(pla) -> None:
    """Der zweite gefundene Fehler, und er ging in die andere Richtung.

    Der Naht-Adapter der Auffangrinne bekam 1,2 mm dicke Wangen mit der
    Begründung, zwei Millimeter ergäben 51,9 MPa und lägen damit über der
    Streckgrenze. Nachgerechnet sind es **28,6 MPa** bei 21 mm Länge und
    1,2 mm Federweg — 1,75-fache Sicherheit, also tragfähig.

    Die dünnere Wange bleibt trotzdem die bessere: Sie fügt sich mit weniger
    Kraft. Aber die Begründung war falsch, und niemand konnte das sehen,
    solange die Rechnung in einem Kommentar stand statt hier.
    """
    dick = spring_load(pla, length=21.0, thickness=2.0, deflection=1.2)
    duenn = spring_load(pla, length=21.0, thickness=1.2, deflection=1.2)
    assert dick is not None and duenn is not None

    assert dick.stress == pytest.approx(28.6, abs=0.2), "nicht 51,9 — das war falsch gerechnet"
    assert dick.holds, "zwei Millimeter tragen mit Reserve"
    assert duenn.stress == pytest.approx(17.1, abs=0.2)
    assert duenn.safety > dick.safety, "dünner federt williger"


def test_the_answer_to_a_thickness_is_an_upper_bound(pla) -> None:
    """„Wie dick darf er sein" — nicht „wie dick muss er sein".

    Bei einer Blattfeder macht mehr Material den Arm steifer und die Spannung
    größer. Wer sie mit Dicke bekämpft, verschlimmert sie; die Antwort ist
    deshalb eine Obergrenze, und ein Arm knapp darunter muss die geforderte
    Sicherheit gerade halten.
    """
    grenze = safe_thickness(pla, length=21.0, deflection=1.2)
    assert grenze is not None

    gerade_noch = spring_load(pla, length=21.0, thickness=grenze, deflection=1.2)
    zu_dick = spring_load(pla, length=21.0, thickness=grenze * 1.2, deflection=1.2)
    assert gerade_noch is not None and zu_dick is not None

    assert gerade_noch.holds, "an der Grenze trägt er noch"
    assert not zu_dick.holds, "darüber nicht mehr"


def test_a_material_without_numbers_says_so_instead_of_guessing(pla) -> None:
    """Regel 21 an einer Stelle, an der Raten besonders verführerisch wäre.

    Ein selbst angelegtes Materialprofil führt keine mechanischen Kennwerte.
    Eine Rechnung mit einem eingesetzten Standard-E-Modul sähe genauso aus wie
    eine gerechnete — dieselbe Zahl, dieselbe Einheit, dieselbe scheinbare
    Genauigkeit —, und niemand könnte den Unterschied sehen.
    """
    ohne = replace(pla, youngs_modulus=0.0, yield_strength=0.0)

    assert spring_load(ohne, length=21.0, thickness=1.2, deflection=1.2) is None
    assert safe_thickness(ohne, length=21.0, deflection=1.2) is None
    assert spring_load(pla, length=21.0, thickness=1.2, deflection=1.2) is not None, (
        "und mit Kennwerten kommt eine Antwort — sonst prüft der Test nur, dass nichts geht"
    )


def test_every_material_that_ships_carries_its_numbers() -> None:
    """Die sechs mitgelieferten Profile können die Frage beantworten.

    Ein Verbotstest über eine leere Menge wäre immer grün, deshalb zählt er
    zuerst. Und TPU steht ausdrücklich mit dabei: Es ist das Material, bei dem
    die Rechnung am meisten zu sagen hat — ein Elastomer federt bei
    Spannungen, bei denen PLA längst gebrochen wäre.
    """
    bekannt = tuple(profiles.material_profiles())
    assert len(bekannt) >= 6, "die Startbestückung ist da"

    for kennung in bekannt:
        material = profiles.make_profile("centauri-carbon-2", kennung).material
        assert material.youngs_modulus > 0.0, f"{kennung} ohne E-Modul"
        assert material.yield_strength > 0.0, f"{kennung} ohne Streckgrenze"

    tpu = profiles.make_profile("centauri-carbon-2", "tpu-95a").material
    pla = profiles.make_profile("centauri-carbon-2", "pla").material
    assert tpu.youngs_modulus < pla.youngs_modulus / 10.0, (
        "TPU ist um Größenordnungen weicher — sonst stimmt die Tabelle nicht"
    )


def test_the_spring_table_names_parts_and_parameters_that_exist() -> None:
    """``SPRING_ARMS`` zeigt auf Bausteine, die es gibt — und auf ihre Maße.

    Eine Tabelle, die Namen nennt, altert an jeder Umbenennung still: Sie
    findet den Baustein nicht mehr, ``_spring_finding`` gibt ``None`` zurück,
    und die Prüfung hört auf zu prüfen, ohne rot zu werden. Genau der Fall,
    für den ein Verbotstest über eine leere Menge immer grün ist — deshalb
    zählt dieser zuerst.
    """
    from app.core.bootstrap import load_operations
    from app.core.knowledge.parts.ops import SPRING_ARMS
    from app.core.knowledge.parts.registry import PARTS

    load_operations()
    assert SPRING_ARMS, "die Tabelle ist nicht leer — sonst prüft dieser Test nichts"

    for name, felder in SPRING_ARMS.items():
        assert PARTS.has(name), f"{name} steht in SPRING_ARMS, aber nicht in der Bibliothek"
        vorhanden = {feld.name for feld in PARTS.get(name).params.fields()}
        fehlen = set(felder) - vorhanden
        assert not fehlen, f"{name} hat diese Parameter nicht (mehr): {sorted(fehlen)}"


def test_an_overloaded_snap_arm_is_reported_and_a_sound_one_is_not() -> None:
    """Gemeldet wird, was nicht trägt — und nur das.

    Ein Bericht, der jeden gelungenen Fall bestätigt, ist einer, den man zu
    überblättern lernt. Beide Richtungen stehen hier, weil eine allein nichts
    sagt: Ein Prüfer, der immer schweigt, besteht die eine Hälfte; einer, der
    immer meldet, die andere.
    """
    from app.core.knowledge.parts.ops import _spring_finding
    from app.core.knowledge.parts.registry import PARTS

    pla = profiles.make_profile("centauri-carbon-2", "pla")
    schema = PARTS.get("snap_fit").params

    # Kurz und dick mit großem Haken: Der Arm müsste sich weit aufbiegen.
    knapp = schema(length=8.0, thickness=1.6, hook=3.0)
    befund = _spring_finding("snap_fit", knapp, pla)
    assert befund is not None, "ein überlasteter Arm bleibt nicht unerwähnt"
    assert befund.code == "part.spring_overloaded"
    assert befund.values["safety"] < 1.5

    # Lang und dünn mit kleinem Haken: derselbe Baustein, tragfähig.
    grosszuegig = schema(length=30.0, thickness=1.0, hook=0.8)
    assert _spring_finding("snap_fit", grosszuegig, pla) is None, (
        "ein tragfähiger Arm bekommt keinen Befund"
    )

    # Und ohne Materialkennwerte schweigt sie ganz, statt zu raten.
    ohne = dataclasses.replace(
        pla, material=dataclasses.replace(pla.material, youngs_modulus=0.0, yield_strength=0.0)
    )
    assert _spring_finding("snap_fit", knapp, ohne) is None
