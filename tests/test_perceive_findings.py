"""Befunde der Durchsicht von ``perceive/`` und ``knowledge/`` (02.09.2026).

Jedes gefundene Fehlerbild wird eine Testdatei und kein Sonderfall im Code
(AGENTS.md). Hier stehen die Fälle, für die es bisher keinen gab: die Leiter
aus gestapelten Wänden, der Kratzer als Erhebung, die Beschriftung der
Toleranzleiter, die still gedeckelten Temperaturen und die Reihenfolge der
Normteiltabellen.
"""

from __future__ import annotations

from pathlib import Path

import trimesh

from app.core.geom.mesh import MeshData
from app.core.knowledge import print_settings, profiles, standards
from app.core.knowledge.parts import PARTS
from app.core.knowledge.parts.testbodies import _label
from app.core.perceive.features import (
    MIN_CYLINDER_DIAMETER,
    detect,
    detect_holes,
    detect_pins,
    forget_cache,
)
from app.core.slice.advise import warnings_for

# --- Befund 1: drei koaxiale Bohrungen gleichen Durchmessers ----------------------


def ladder(walls: int) -> MeshData:
    """``walls`` Lappen übereinander, alle von einer Bohrung Ø 6 durchbohrt.

    Ein Scharnier, ein Gelenk, eine Durchführung durch mehrere Wände — die
    Form, an der die Gewindeerkennung sich verschluckt hat. Zwischen den
    Lappen liegen vier Millimeter Luft; ein Gewinde hat dort nichts.
    """
    lugs = []
    for index in range(walls):
        lug = trimesh.creation.box(extents=(30.0, 30.0, 6.0))
        lug.apply_translation((0.0, 0.0, index * 10.0))
        lugs.append(lug)
    bore = trimesh.creation.cylinder(radius=3.0, height=200.0, sections=64)
    return MeshData.of(trimesh.util.concatenate(lugs).difference(bore))


def test_a_stack_of_lugs_keeps_every_one_of_its_bores() -> None:
    """Ab drei Wänden verschwand die Durchführung vollständig.

    ``_without_thread_turns`` bildete seinen Gewindestapel aus paralleler
    Achse (±2°), kleinem Querversatz (≤ 25 % des Radius) und gleichem Radius
    (±8 %) — **ohne axiale Bedingung**. Drei Bohrungen durch drei Wände
    erfüllen alle drei, und ab dem dritten Treffer galten sie als
    Gewindegänge und fielen weg: gemessen eine Bohrung bei einer Wand, zwei
    bei zweien, null bei dreien, null bei vieren.

    Ein Gewinde ist ein **durchgehender** Lauf: seine Gänge berühren oder
    überlappen sich auf der Achse. Gemessen an ``printed_thread`` über sechs
    Größen, beide Richtungen und drei Längen liegt die größte Lücke innerhalb
    eines Gangstapels bei 0,0000 mm; drei Wände haben Lücken von vier
    Millimetern.
    """
    for walls in (1, 2, 3, 4):
        forget_cache()
        holes = detect_holes(ladder(walls))
        assert len(holes) == walls, f"{walls} Wände tragen {walls} Bohrungen, nicht {len(holes)}"


def test_the_stack_of_lugs_reaches_the_named_features() -> None:
    """Die Gegenprobe über ``detect``: sonst wäre nur der Teilweg geprüft.

    Gemeldet war der ganze Aufruf — ``detect`` lieferte auf der Leiter aus
    drei Wänden nur noch ``face`` und keine einzige Bohrung.
    """
    forget_cache()
    kinds = {feature.kind for feature in detect(ladder(3)).values()}

    assert "hole" in kinds, f"nur {sorted(kinds)} auf einer Leiter mit drei Bohrungen"


# --- Befund 3: der Artefaktfilter gilt beiden Richtungen --------------------------


def scratch_and_dent(diameter: float) -> MeshData:
    """Eine Erhebung und eine Vertiefung desselben Durchmessers auf einer Platte."""
    plate = trimesh.creation.box(extents=(30.0, 30.0, 6.0))
    bump = trimesh.creation.cylinder(radius=diameter / 2.0, height=4.0, sections=48)
    bump.apply_translation((0.0, 0.0, 3.0))
    dent = trimesh.creation.cylinder(radius=diameter / 2.0, height=4.0, sections=48)
    dent.apply_translation((10.0, 0.0, 3.0))
    return MeshData.of(trimesh.boolean.difference([trimesh.boolean.union([plate, bump]), dent]))


def test_a_scratch_is_no_more_a_pin_than_it_is_a_bore() -> None:
    """Dieselbe Schranke in beide Richtungen.

    ``detect_holes`` warf Zylinder unter dem Mindestdurchmesser weg,
    ``detect_pins`` nicht: Eine Erhebung von 0,05 mm kam als Zapfen zurück,
    die gleich große Vertiefung daneben als gar nichts. Eine Düse legt 0,4 mm
    breite Bahnen — was kein Werkzeug gemacht hat, ist auch kein Zapfen.
    """
    for diameter in (0.05, 0.2, 0.4):
        forget_cache()
        body = scratch_and_dent(diameter)
        assert not detect_pins(body), f"Ø {diameter} ist kein Zapfen"
        assert not detect_holes(body), f"Ø {diameter} ist keine Bohrung"


def test_a_real_pin_and_a_real_bore_survive_the_limit() -> None:
    """Die Gegenprobe: Über der Schranke wird beides gemeldet.

    Ohne sie wäre der Test darüber auch dann grün, wenn ``detect_pins`` gar
    nichts mehr fände.
    """
    forget_cache()
    body = scratch_and_dent(MIN_CYLINDER_DIAMETER + 0.1)

    assert detect_pins(body), "über der Schranke ist die Erhebung ein Zapfen"
    assert detect_holes(body), "und die Vertiefung eine Bohrung"


# --- Befund 2: die Beschriftung der Toleranzleiter --------------------------------


def test_every_step_of_the_fit_ladder_carries_its_own_number() -> None:
    """Zwei Stufen mit gleich vielen Strichen sind keine Beschriftung.

    Gezählt wurde die letzte Ziffer des Spiels statt der Stufennummer:
    0,10 → zehn Striche, 0,15 → fünf, 0,20 → wieder zehn. Mit der Vorgabe
    (0,10 mm, Schritt 0,05 mm) trugen Stufe eins und drei dieselbe Zahl und
    Stufe zwei und vier ebenfalls — auf einem Körper, dessen einziger Zweck
    es ist, vier Spiele auseinanderzuhalten. Mit Schrittweite 0,10 mm waren
    sogar alle vier gleich.

    Gezählt werden die Striche an der Geometrie: Jeder ist ein eigener
    Quader mit Luft dazwischen, also ist die Strichzahl die Zahl der
    Bestandteile.
    """
    counts = [_label(step, (0.0, 0.0, 0.0)).component_count for step in range(1, 9)]

    assert counts == list(range(1, 9)), counts


def test_the_fit_ladder_still_prints_as_one_piece() -> None:
    """Die Striche werden eingraviert — sie dürfen die Grundplatte nicht zerlegen.

    Gefahren wird die Leiter dabei mit der größten Stufenzahl, denn dort ist
    die Beschriftung am breitesten.
    """
    spec = PARTS.get("fit_ladder")
    result = spec.fn(spec.params(diameter=6.0, steps=8, first=0.10, step=0.05))

    assert result.mesh.is_watertight
    assert result.mesh.component_count == 1


# --- Befund 4: gedeckelte Temperaturen werden gesagt ------------------------------


def test_a_capped_bed_temperature_is_not_kept_quiet() -> None:
    """ABS will 100 °C Bett, der A1 mini kann 80 — und es stand nirgends.

    ``_temperatures`` deckelt auf das, was die Maschine kann, und sagt dazu
    „gedeckelt wird, aber ``advise`` sagt es auch". Für die Düse stimmte das,
    für das Bett nicht: Der Druck lief mit zwanzig Grad zu kaltem Bett los,
    und im Bericht stand kein Wort.
    """
    profile = profiles.make_profile("bambu-a1-mini", "abs")
    settings = print_settings.resolve(profile)

    assert settings.temperature.bed == profile.printer.bed_temperature_max
    codes = [finding.code for finding in warnings_for(settings, profile)]
    assert "settings.bed_below_material" in codes, codes


def test_a_missing_chamber_is_not_kept_quiet() -> None:
    """ASA will 50 °C Bauraum, ein offener Drucker hat keinen.

    ``_temperatures`` setzt die Kammer auf null, wo kein geschlossener
    Bauraum da ist. Der Zweig in ``_from_machine``, der davor warnt, sieht
    deshalb nie einen Wert über null — er greift allein bei einer von Hand
    eingetragenen Temperatur.
    """
    profile = profiles.make_profile("bambu-a1-mini", "asa")
    settings = print_settings.resolve(profile)

    assert settings.temperature.chamber == 0
    codes = [finding.code for finding in warnings_for(settings, profile)]
    assert "settings.chamber_without_enclosure" in codes, codes


def test_a_printer_that_can_do_it_gets_no_such_finding() -> None:
    """Die Gegenprobe: Wo Bett und Kammer reichen, wird nichts gemeldet."""
    profile = profiles.make_profile("centauri-carbon-2", "abs")
    settings = print_settings.resolve(profile)

    codes = [finding.code for finding in warnings_for(settings, profile)]
    assert "settings.bed_below_material" not in codes, codes
    assert "settings.chamber_without_enclosure" not in codes, codes


# --- Befund 7: die Reihenfolge der Normteiltabellen -------------------------------


def test_screw_sizes_come_in_ascending_order() -> None:
    """``size_for_nut_trap`` nimmt die **erste** passende als die kleinste.

    Die Reihenfolge stand bisher allein in der Datendatei; ``placement.py``
    schreibt die Annahme in einen Kommentar, und niemand prüfte sie. Ein
    neuer Eintrag an der falschen Stelle hätte die Größenauswahl der
    Bausteine still verdreht.
    """
    sizes = standards.screw_sizes()
    nominal = [standards.screw(size).nominal for size in sizes]
    clearance = [standards.screw(size).clearance for size in sizes]

    assert nominal == sorted(nominal), dict(zip(sizes, nominal, strict=True))
    assert clearance == sorted(clearance), dict(zip(sizes, clearance, strict=True))


def test_insert_sizes_come_in_ascending_order() -> None:
    """``size_for_insert`` sucht die kleinste Buchse, die eine Bohrung aufweitet."""
    sizes = standards.insert_sizes()
    hole = [standards.insert(size).hole for size in sizes]

    assert hole == sorted(hole), dict(zip(sizes, hole, strict=True))


def test_an_unsorted_table_is_put_in_order_when_it_is_read(tmp_path: Path) -> None:
    """Sortiert wird beim Lesen und nicht in der Datei.

    Eine Reihenfolge, die nur in der Datendatei steht, hält bis zu dem Tag,
    an dem jemand einen Eintrag anhängt statt einsortiert.
    """
    path = tmp_path / "standards.toml"
    path.write_text(
        'version = "9"\n'
        "[[screws]]\n"
        'size = "M8"\n'
        "nominal = 8.0\nclearance = 9.0\ntap = 6.8\nhead = 13.0\n"
        "head_height = 8.0\ncountersink = 16.0\nhex = 6.0\npitch = 1.25\n"
        "[[screws]]\n"
        'size = "M3"\n'
        "nominal = 3.0\nclearance = 3.4\ntap = 2.5\nhead = 5.5\n"
        "head_height = 3.0\ncountersink = 6.0\nhex = 2.5\npitch = 0.5\n",
        encoding="utf-8",
    )

    tables = standards.load(path)

    assert list(tables.screws) == ["M3", "M8"]
