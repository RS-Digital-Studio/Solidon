"""Die Vorschläge aus der Schichtanalyse (Bauplan §22.2, §29).

`test_print_settings.py` prüft die drei Ebenen und den Weg zum Slicer. Hier
stehen die Fälle, an denen die Regeln aus ``slice/advise.py`` selbst falsch
geurteilt haben — jeder mit dem Körper, der sie widerlegt hat.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData
from app.core.knowledge import print_settings, profiles, rules
from app.core.slice import advise
from app.core.slice.analysis import WIDTH_INTERESTING, slice_body
from app.core.types import (
    LayerInfo,
    Polygon,
    PrintSettings,
    Profile,
    SettingAdvice,
    SliceResult,
    SpeedSettings,
)

SQUARE = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))


def result_with(
    overhangs: list[float],
    *,
    area: float = 5000.0,
    min_width: float = 5.0,
    tapers: list[float] | None = None,
) -> SliceResult:
    """Ein Schnittergebnis mit vorgegebener Überhangfläche je Schicht.

    Die Vorschläge lesen nur Kennzahlen; die Konturen stehen dabei, damit die
    Schichten nicht leer sind. ``tapers`` gibt je Schicht die Keilstrecke vor.
    """
    layers = tuple(
        LayerInfo(
            z=float(index) * 0.2,
            contours=(Polygon(outline=SQUARE),),
            area=area,
            overhang_area=overhang,
            islands=(),
            min_width=min_width,
            taper_length=0.0 if tapers is None else tapers[index],
        )
        for index, overhang in enumerate(overhangs)
    )
    return SliceResult(
        layers=layers,
        support_volume=sum(overhangs) * 10.0,
        first_layer_area=area,
        source="internal",
    )


def paths(entries: list[SettingAdvice]) -> set[str]:
    return {entry.path for entry in entries}


def number(entry: SettingAdvice) -> float:
    """Der Zahlenwert eines Vorschlags — ``value`` trägt je nach Pfad auch
    Text oder Wahrheitswerte."""
    assert isinstance(entry.value, int | float)
    return float(entry.value)


# --- Stützen: wie viel auf einmal (§22.2) ---------------------------------------


def test_a_ceiling_hanging_free_in_the_air_gets_supports() -> None:
    """Der Fund: Eine Decke von 138 mm² über einem Hohlraum bekam nichts.

    Die Bedingung verlangte beides — mehr als 150 mm² insgesamt **und** mehr
    als 100 mm² auf einer Schicht. Weil die zweite Zahl nie größer sein kann
    als die erste, blieb davon in Wahrheit „mehr als 100 auf einer Schicht"
    übrig, mit einem toten Streifen zwischen 100 und 150: Genau dort liegt die
    Decke eines kleinen Kastens, und die hängt vollständig in der Luft.
    """
    settings = print_settings.resolve(profiles.make_profile())
    ceiling = result_with([0.0, 0.0, 138.0, 0.0])

    entries = advise.advise(settings, profiles.make_profile(), ceiling)

    chosen = next(entry for entry in entries if entry.path == "support.style")
    assert chosen.value != "none"
    assert chosen.reason, "ein Vorschlag ohne Grund ist keiner"


def test_a_cup_that_spreads_its_overhang_over_three_hundred_layers_gets_none() -> None:
    """Die Gegenprobe, und der Grund, warum die Bedingung überhaupt zwei
    Zahlen hatte.

    Ein Becher sammelt über dreihundertachtunddreißig Schichten
    zweihundertvierzig Quadratmillimeter Überhang; keine Schicht trägt mehr
    als knapp vier, und jede Wand fängt ihren Anteil selbst auf. Er darf
    dieselbe Warnung **nicht** bekommen wie die Decke darüber.
    """
    settings = print_settings.resolve(profiles.make_profile())
    cup = result_with([0.7] * 338)

    entries = advise.advise(settings, profiles.make_profile(), cup)

    assert "support.style" not in paths(entries)


# --- Volumenstrom: gedeckelt wird, wer die Grenze reißt --------------------------


def hot_and_fast() -> tuple[PrintSettings, Profile]:
    """Einstellungen, bei denen die Innenwand den Volumenstrom reißt, während
    die Füllung langsam läuft — und ohne Luft nach oben an der Düse.
    """
    profile = profiles.make_profile("prusa-mk4s", "pla")
    settings = print_settings.resolve(profile, "fine")
    settings = print_settings.with_path(settings, "speed.infill", 20.0)
    settings = print_settings.with_path(settings, "speed.inner_wall", 500.0)
    settings = print_settings.with_path(
        settings, "temperature.nozzle", profile.printer.nozzle_temperature_max - 1
    )
    return settings, profile


def test_the_flow_advice_caps_the_value_that_breaks_the_limit() -> None:
    """Der Fund: Gedeckelt wurde immer ``speed.infill``, auch wenn die
    Innenwand die Grenze riss.

    Herausgekommen ist dabei ein Rat, der das Tempo **erhöht** — „Füllung 20
    → 143" —, während der Wert, der die Grenze reißt, unangetastet blieb. Ein
    Vorschlag, der die Sache verschlimmert und das Problem stehenlässt, ist
    schlimmer als keiner.
    """
    settings, profile = hot_and_fast()
    limit = settings.filament.max_flow
    assert advise.flow_of(settings, settings.speed.inner_wall) > limit
    assert advise.flow_of(settings, settings.speed.infill) < limit

    entries = advise.advise(settings, profile)

    inner = next(entry for entry in entries if entry.path == "speed.inner_wall")
    assert number(inner) < 500.0, "gedeckelt wird der Wert, der die Grenze reißt"
    assert "speed.infill" not in paths(entries), "die langsame Füllung wird nicht angehoben"


def test_after_the_flow_advice_the_limit_holds() -> None:
    """Die Zusage dahinter: angewandt liegt der Volumenstrom unter der Grenze.

    Der alte Rat ließ ihn verletzt — er deckelte einen Wert, der ihn gar nicht
    riss.
    """
    settings, profile = hot_and_fast()

    applied = advise.apply(settings, advise.advise(settings, profile))

    fastest = max(applied.speed.infill, applied.speed.inner_wall)
    assert advise.flow_of(applied, fastest) <= applied.filament.max_flow + 1e-6


# --- die Deckelung der Strukturbreite ist keine Messung --------------------------


def test_a_solid_block_gets_no_warning_about_its_thinnest_spot() -> None:
    """Der Fund: Der Deckel von 2,0 mm wurde als Messwert weiterverrechnet.

    ``narrowest`` meldet ``WIDTH_INTERESTING``, wenn der Körper nirgends dünner
    ist — „mindestens zwei Millimeter", keine Messung. An einer 0,8er-Düse sind
    drei Linienbreiten aber 2,55 mm, und damit stand über einem massiven Klotz
    „die schmalste Stelle geht auf keine ganze Zahl von Bahnen auf".
    """
    settings = print_settings.resolve(profiles.make_profile())
    settings = print_settings.with_path(settings, "layers.line_width", 0.85)
    settings = print_settings.with_path(settings, "shell.wall_generator", "classic")
    block = result_with([0.0] * 20, min_width=WIDTH_INTERESTING)
    assert advise.LINES_FOR_CLASSIC * settings.layers.line_width > WIDTH_INTERESTING, (
        "sonst liegt der Deckel über der Schwelle und der Fall prüft nichts"
    )

    entries = advise.advise(settings, profiles.make_profile(), block)

    assert "shell.wall_generator" not in paths(entries)
    assert "layers.line_width" not in paths(entries)


def test_a_measured_thin_wall_still_warns() -> None:
    """Die Gegenprobe: Unterhalb des Deckels ist die Zahl eine Messung, und
    dann bleibt die Warnung.
    """
    settings = print_settings.resolve(profiles.make_profile())
    settings = print_settings.with_path(settings, "shell.wall_generator", "classic")
    thin = result_with([0.0] * 20, min_width=0.5)

    entries = advise.advise(settings, profiles.make_profile(), thin)

    assert "shell.wall_generator" in paths(entries)


# --- Fließkomma (Regel 6) --------------------------------------------------------


def test_an_advice_that_changes_nothing_measurable_is_dropped() -> None:
    """Regel 6: kein ``==`` und kein ``!=`` auf Fließkomma.

    Zusammengeführt wurden die Vorschläge über ``entry.value != entry.was``.
    Eine Zahl, die sich erst in der zwölften Stelle unterscheidet, blieb damit
    als Vorschlag stehen — im Dialog eine Zeile „0,42 → 0,42", die der Kunde
    nicht deuten kann.
    """
    settings = print_settings.resolve(profiles.make_profile())
    same = settings.layers.line_width + 1e-12

    kept = advise._merged(
        settings,
        [SettingAdvice(path="layers.line_width", value=same, was=0.0, reason="Prüffall")],
    )

    assert kept == []


# --- der tote Bereich zwischen Vorschlag und Befund ------------------------------


def barely_narrow() -> tuple[PrintSettings, Profile, float]:
    """Eine Stelle, die eine Bahn dieser Düse trägt, aber keine zwei.

    Bei einer 0,4er Düse ist die schmalste Bahn 0,34 mm breit; eine Stelle von
    0,50 mm liegt darüber und unter dem Doppelten. Der Vorschlag senkte die
    Bahnbreite auf 0,34 — zwei davon sind 0,68 und passen weiterhin nicht.
    """
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    least = advise.NARROW_LINE_SHARE * profile.printer.nozzle_diameter
    return settings, profile, least


def test_a_place_between_one_and_two_nozzle_lines_gets_no_empty_advice() -> None:
    """Ein Vorschlag, der nichts behebt, ist keiner (§22.2).

    Er stand trotzdem da: „Bahnbreite 0,42 → 0,34" über einer Stelle von
    0,50 mm, an der auch zwei Bahnen von 0,34 nicht ankommen.
    """
    settings, profile, least = barely_narrow()
    thin = 1.5 * least
    assert thin < 2.0 * settings.layers.line_width, "sonst greift die Regel gar nicht"

    entries = advise.advise(settings, profile, result_with([0.0] * 20, min_width=thin))

    assert "layers.line_width" not in paths(entries)


def test_one_variable_nozzle_line_is_not_reported_as_missing() -> None:
    """Eine einzelne Arachne-Bahn ist druckbar; zwei sind keine Druckbarkeitsgrenze."""
    settings, profile, least = barely_narrow()
    thin = 1.5 * least

    findings = advise.warnings_for(settings, profile, result_with([0.0] * 20, min_width=thin))

    assert "settings.wall_below_nozzle" not in {entry.code for entry in findings}


def test_below_one_nozzle_line_the_slicer_check_is_still_required() -> None:
    """Unterhalb der angesetzten Mindestbahnbreite bleibt die konkrete Gegenprüfung nötig."""
    settings, profile, least = barely_narrow()
    thin = 0.75 * least

    findings = advise.warnings_for(settings, profile, result_with([0.0] * 20, min_width=thin))

    hits = [entry for entry in findings if entry.code == "settings.wall_below_nozzle"]
    assert hits, "unterhalb der angesetzten Mindestbahnbreite muss die Warnung bleiben"
    assert hits[0].values["width_mm"] == thin


def test_above_two_nozzle_lines_the_advice_works_again() -> None:
    """Die Gegenprobe: Ab der doppelten schmalsten Bahn hilft eine schmalere
    Linie wirklich, und dann kommt sie auch.
    """
    settings, profile, least = barely_narrow()
    thin = 2.2 * least
    assert thin < 2.0 * settings.layers.line_width

    entries = advise.advise(settings, profile, result_with([0.0] * 20, min_width=thin))
    findings = advise.warnings_for(settings, profile, result_with([0.0] * 20, min_width=thin))

    chosen = next(entry for entry in entries if entry.path == "layers.line_width")
    assert 2.0 * number(chosen) <= thin, "zwei solche Bahnen passen jetzt hinein"
    assert "settings.wall_below_nozzle" not in {entry.code for entry in findings}


# --- der Volumenstrom prüft alle Geschwindigkeiten -------------------------------


def test_the_outer_wall_is_checked_too() -> None:
    """Geprüft wurden nur einzelne Geschwindigkeiten.

    Eine Stufe, die nur an der Außenwand zieht, kam damit ohne einen Satz
    durch — und die Außenwand ist die Bahn, die man sieht.
    """
    profile = profiles.make_profile("prusa-mk4s", "pla")
    settings = print_settings.resolve(profile, "fine")
    settings = print_settings.with_path(settings, "speed.outer_wall", 500.0)
    settings = print_settings.with_path(
        settings, "temperature.nozzle", profile.printer.nozzle_temperature_max - 1
    )
    assert advise.flow_of(settings, settings.speed.outer_wall) > settings.filament.max_flow

    entries = advise.advise(settings, profile)

    chosen = next(entry for entry in entries if entry.path == "speed.outer_wall")
    assert number(chosen) < 500.0


def test_the_first_layer_is_measured_with_its_own_size() -> None:
    """Die erste Schicht ist höher und breiter als alle über ihr — 0,25 auf
    0,45 gegen 0,20 auf 0,42, ein Drittel mehr Material je Millimeter.

    Mit den Maßen der übrigen gerechnet fiel genau der Wert durch, der als
    erster reißt.
    """
    profile = profiles.make_profile("prusa-mk4s", "pla")
    settings = print_settings.resolve(profile, "fine")
    settings = print_settings.with_path(
        settings, "temperature.nozzle", profile.printer.nozzle_temperature_max - 1
    )
    limit = settings.filament.max_flow
    per_millimetre = settings.layers.first_layer_height * settings.layers.first_layer_line_width
    speed = 1.05 * limit / per_millimetre
    settings = print_settings.with_path(settings, "speed.first_layer", speed)
    assert advise.flow_of(settings, speed) < limit, "mit den Maßen der übrigen fiele es durch"
    assert advise.flow_of(settings, speed, first_layer=True) > limit

    entries = advise.advise(settings, profile)

    chosen = next(entry for entry in entries if entry.path == "speed.first_layer")
    assert advise.flow_of(settings, number(chosen), first_layer=True) <= limit


# --- die Verbinder rechnen gegen den Stand, der herauskommt ----------------------


def test_the_connector_rule_sees_the_narrower_line() -> None:
    """Gerechnet wurde gegen den Ausgangsstand.

    Die Wandzahl hängt an der Bahnbreite, und genau die senkt die Regel über
    die dünnste Stelle zwei Absätze weiter oben. Vorher gerechnet stand im
    Bericht eine Wandzahl, die zu einer Breite passte, die daneben schon
    zurückgenommen war.
    """
    import math

    settings, profile, least = barely_narrow()
    thin = 2.2 * least
    thickest = 6.5

    entries = advise.advise(
        settings, profile, result_with([0.0] * 20, min_width=thin), connectors=[thickest]
    )

    line = next(entry for entry in entries if entry.path == "layers.line_width")
    walls = next(entry for entry in entries if entry.path == "shell.wall_count")
    assert walls.value == math.ceil(thickest / (4.0 * number(line)))
    assert walls.value > math.ceil(thickest / (4.0 * settings.layers.line_width)), (
        "gegen den alten Stand gerechnet wären es weniger Wände, als der Zapfen braucht"
    )


# --- die Begründung sagt, was gemessen wurde ------------------------------------


def test_the_minimum_layer_time_reason_stays_with_the_measurement() -> None:
    """Geprüft wird „irgendeine kleine Schicht weiter oben", begründet wurde
    „das Teil läuft nach oben spitz zu".

    Ein gleichmäßig dünner Stab hat kleine Schichten und keine Verjüngung —
    der Satz beschrieb einen Körper, den niemand gemessen hatte.
    """
    settings = print_settings.resolve(profiles.make_profile())
    rod = result_with([0.0] * 20, area=advise.THIN_LAYER_AREA / 2.0)

    entries = advise.advise(settings, profiles.make_profile(), rod)

    chosen = next(entry for entry in entries if entry.path == "cooling.minimum_layer_time")
    assert "spitz" not in str(chosen.reason), "das Teil verjüngt sich nicht, es ist überall dünn"


# --- eine Überhanglinie, nicht zwei ---------------------------------------------


def test_the_support_angle_comes_from_the_rule_set() -> None:
    """Zwei Winkel für dieselbe Frage sind nur so lange einig, wie niemand
    einen davon anfasst (§39).

    Die Einstellung stand auf 50 Grad, die Schichtanalyse rechnete mit 45: Ein
    Dach von 48 Grad fiel zwischen beide Zahlen — im Bericht ein Überhang, im
    Slicer keiner.
    """
    from app.core.knowledge.rules import OVERHANG_LIMIT_DEGREES
    from app.core.types import SupportSettings

    assert SupportSettings().threshold_angle == OVERHANG_LIMIT_DEGREES


#: Feld -> Maschinengrenze, gegen die es läuft. Der Wächter darunter setzt
#: jeden Wert über seine Grenze und verlangt ein Wort dazu.
#:
#: **Die Tabelle ist der Punkt, nicht die fünf Regeln.** Am 03.09.2026 prüfte
#: `_from_machine` genau eines dieser sechs Felder — der Kunde konnte 400 Grad
#: erste Schicht und 150 Grad Bett einstellen, und niemand sagte etwas.
#: Auffällig war das nicht, weil zwei ordentliche Prüfungen dastanden: Eine
#: Regel, die den Hauptwert prüft und seinen `_first_layer`-Nachbarn nicht,
#: sieht aus wie eine ganze.
MACHINE_LIMITS: dict[str, str] = {
    "layers.layer_height": "nozzle_diameter",
    "layers.first_layer_height": "nozzle_diameter",
    "layers.line_width": "nozzle_diameter",
    "temperature.nozzle": "nozzle_temperature_max",
    "temperature.nozzle_first_layer": "nozzle_temperature_max",
    "temperature.bed": "bed_temperature_max",
    "temperature.bed_first_layer": "bed_temperature_max",
}


def test_no_setting_can_exceed_the_machine_without_a_word() -> None:
    """Was der Drucker nicht kann, wird gesagt — bei jedem Feld, nicht bei einem.

    `_from_machine` trägt den Satz „Was die Maschine nicht kann, muss vor dem
    Druck gesagt werden" im Docstring und löste ihn für ein Feld von sieben
    ein. Gemessen: 400 Grad erste Schicht und 150 Grad Bett ließen sich
    einstellen, der Drucker kann 260 und 100, und der Bericht blieb leer.

    Der Test setzt jeden Wert über seine Grenze und verlangt einen Vorschlag
    **auf dasselbe Feld** — ein Vorschlag zu einem Nachbarn wäre keine Antwort
    auf die gestellte Frage.
    """
    profile = Profile(
        printer=next(iter(profiles.printer_profiles().values())),
        material=next(iter(profiles.material_profiles().values())),
    )
    base = print_settings.resolve(profile, next(iter(print_settings.quality_presets())))

    silent: list[str] = []
    for path, limit in MACHINE_LIMITS.items():
        ceiling = float(getattr(profile.printer, limit))
        # Deutlich darüber, damit kein Rundungsrand die Frage beantwortet.
        beyond = ceiling * 2.0 if "temperature" not in path else ceiling + 100.0
        if path == "layers.line_width":
            # Dieses Feld läuft nach **unten** gegen seine Grenze: Schmaler als
            # ein Anteil der Düse reißt die Bahn ab, statt dünner zu werden.
            beyond = ceiling * 0.4
        current = print_settings.read_path(base, path)
        wanted = int(beyond) if isinstance(current, int) else beyond
        spoken = advise.advise(print_settings.with_path(base, path, wanted), profile, None)
        if not any(entry.path == path for entry in spoken):
            silent.append(f"{path} = {wanted} (Maschine: {limit} = {ceiling:g})")

    assert not silent, "ohne ein Wort einstellbar:\n" + "\n".join(silent)


# --- der Keil in der Wand: Außenwand zuerst (§22.2, §29) ---------------------------


def _tapered(layers: int = 100, share: float = 1.0) -> SliceResult:
    """Ein Körper ohne Überhang, dessen Wand auf einem Anteil der Schichten
    einen Keil trägt — der Organizer, auf Kennzahlen reduziert."""
    tapered = round(layers * share)
    return result_with([0.0] * layers, tapers=[40.0] * tapered + [0.0] * (layers - tapered))


def test_a_taper_in_the_wall_puts_the_outer_wall_first() -> None:
    """Der Fund vom 20.09.2026: Ein Organizer mit 1,0-mm-Wand und einem Becher
    in jedem Ende, gedruckt mit Solidons Werten — ein Band aus Rillen über
    die ganze Höhe, genau an der Stelle, an der die Wand von 1,0 auf 3,0 mm
    läuft. Arachne wechselt dort die Wandzahl, die Innenwände zuerst, und
    ihre Übergänge wölben die Außenwand darüber. Solidon hatte für das Teil
    keinen einzigen Vorschlag.
    """
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    assert settings.shell.wall_generator == "arachne" and not settings.shell.outer_wall_first

    entries = advise.advise(settings, profile, _tapered())

    chosen = next(entry for entry in entries if entry.path == "shell.outer_wall_first")
    assert chosen.value is True
    assert chosen.severity == "warning"


def test_the_taper_rule_stays_quiet_where_it_would_not_help() -> None:
    """Vier Lagen, in denen der Vorschlag nichts bringt oder schadet: Die
    Außenwand liegt schon vorn; der Wandgenerator hat feste Bahnen und keine
    Übergänge; das Teil braucht Stützen, und eine zuerst gelegte Außenwand
    kragt an steilen Überhängen ohne Nachbarn vor; und ein Keil auf ein paar
    Schichten ist eine Schulter, kein Band.
    """
    profile = profiles.make_profile()
    base = print_settings.resolve(profile)

    first = print_settings.with_path(base, "shell.outer_wall_first", True)
    assert "shell.outer_wall_first" not in paths(advise.advise(first, profile, _tapered()))

    classic = print_settings.with_path(base, "shell.wall_generator", "classic")
    assert "shell.outer_wall_first" not in paths(advise.advise(classic, profile, _tapered()))

    hanging = result_with([0.0, 0.0, 500.0, 0.0], tapers=[40.0] * 4)
    spoken = advise.advise(base, profile, hanging)
    assert "support.style" in paths(spoken), "die Lage verlangt Stützen"
    assert "shell.outer_wall_first" not in paths(spoken)

    shoulder = _tapered(share=advise.TAPERED_LAYERS_SHARE / 2.0)
    assert "shell.outer_wall_first" not in paths(advise.advise(base, profile, shoulder))


# --- Stützen: an einem Stück, nicht auf einer Schicht (§22.2) --------------------


def _pieces(count: int, side: float) -> tuple[Polygon, ...]:
    """``count`` getrennte Quadrate mit Kantenlänge ``side`` auf einer Schicht."""
    return tuple(
        Polygon(
            outline=(
                (x, 0.0),
                (x + side, 0.0),
                (x + side, side),
                (x, side),
            )
        )
        for x in (index * (side + 1.0) for index in range(count))
    )


def _overhang_layers(pieces: tuple[Polygon, ...], layers: int = 20) -> SliceResult:
    """Ein Körper, dessen Schichten alle dieselben Überhangstücke tragen."""
    from shapely.geometry import Polygon as ShapelyPolygon

    area = sum(ShapelyPolygon(piece.outline).area for piece in pieces)
    stack = tuple(
        LayerInfo(
            z=float(index) * 0.2,
            contours=(Polygon(outline=SQUARE),),
            area=5000.0,
            overhang_area=area,
            islands=(),
            min_width=5.0,
            overhangs=pieces,
        )
        for index in range(layers)
    )
    return SliceResult(layers=stack, support_volume=0.0, first_layer_area=5000.0, source="internal")


def test_a_lattice_of_small_self_supporting_pieces_gets_no_supports() -> None:
    """Der Gitterbecher vom 20.09.2026: auf der schlimmsten Schicht 278 mm²
    Überhang — in 56 Stegunterseiten zu je 5 mm², jede über 4,7 mm frei,
    jede trägt sich selbst. Gedruckt ohne eine einzige Stütze; Solidon riet
    zu einem Gitter, weil die Schichtsumme aussah wie eine Decke.
    """
    from math import sqrt

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    lattice = _overhang_layers(_pieces(56, sqrt(5.0)))
    assert lattice.layers[0].overhang_area > advise.OVERHANG_LAYER_WORTH_SUPPORT

    entries = advise.advise(settings, profile, lattice)

    assert "support.style" not in paths(entries)


def test_one_ceiling_of_the_same_area_still_gets_supports() -> None:
    """Dieselbe Fläche an einem Stück ist die Decke, um die es beim Deckel ging."""
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    ceiling = _overhang_layers(_pieces(1, 16.7), layers=1)

    entries = advise.advise(settings, profile, ceiling)

    chosen = next(entry for entry in entries if entry.path == "support.style")
    assert chosen.value == "grid"


# --- Die Leerfahrt gehört dem Drucker -------------------------------------------


def test_the_travel_speed_comes_from_the_printer() -> None:
    """Der Centauri Carbon 2 fährt leer mit 500 mm/s (Standardprozess seines
    Herstellerprofils, eingetragen in ``printers.toml``); die Waschschüssel
    ging mit den allgemeinen 150 hinaus und zog Fäden (25.09.2026)."""
    fast = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "pla"))
    plain = print_settings.resolve(profiles.make_profile("generic-220", "pla"))

    assert profiles.printer("centauri-carbon-2").travel_speed == 500.0
    assert fast.speed.travel == 500.0
    assert profiles.printer("generic-220").travel_speed is None
    assert plain.speed.travel == SpeedSettings().travel, "ohne Angabe die Vorgabe"


def test_an_older_project_is_offered_the_printers_travel_speed() -> None:
    """Ein Projekt trägt seine Einstellungen selbst — eines von vorher fährt
    weiter mit 150, bis der Vorschlag es auf die Maschine hebt."""
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    current = print_settings.resolve(profile)
    older = print_settings.with_path(current, "speed.travel", 150.0)

    offered = [entry for entry in advise.advise(older, profile) if entry.path == "speed.travel"]
    assert [number(entry) for entry in offered] == [500.0]
    assert "speed.travel" not in paths(advise.advise(current, profile)), "schon da"
    plain = profiles.make_profile("generic-220", "pla")
    assert "speed.travel" not in paths(advise.advise(print_settings.resolve(plain), plain))


def test_a_travel_speed_that_does_not_move_is_refused() -> None:
    table = {"title": "Probe", "build_volume": [200.0, 200.0, 200.0], "travel_speed": 0}

    with pytest.raises(ValidationError):
        profiles._printer_from_table("probe", table, Path("printers.toml"))


# --- Ab welchem Winkel gestützt wird, sagt der Drucker ----------------------------


def test_the_overhang_limit_comes_from_the_manufacturer() -> None:
    """Die Stützgrenze des Standardprozesses im Slicer des Herstellers
    (27.09.2026): ElegooSlicer ``support_threshold_angle`` 30 gegen die
    Waagerechte, PrusaSlicer für den MINI ``support_material_threshold`` 50.
    Ohne Herstellerwert bleibt die Startregel."""
    centauri = profiles.make_profile("centauri-carbon-2", "pla")
    mini = profiles.make_profile("prusa-mini", "pla")
    plain = profiles.make_profile("generic-220", "pla")

    assert centauri.overhang_limit_degrees == pytest.approx(60.0)
    assert mini.overhang_limit_degrees == pytest.approx(40.0), "strenger als die Startregel"
    assert plain.printer.overhang_limit is None
    assert plain.overhang_limit_degrees == pytest.approx(rules.OVERHANG_LIMIT_DEGREES)


def test_a_measured_overhang_angle_goes_before_the_manufacturer() -> None:
    """§28.3: Die Probe am eigenen Drucker schlägt jede Angabe über ihn."""
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    measured = Profile(
        profile.printer,
        replace(
            profile.material,
            overhang_angle=52.0,
            calibration_printer=profile.printer.id,
            calibration_nozzle_diameter=profile.printer.nozzle_diameter,
            calibration_layer_height=profile.printer.layer_height,
            calibration_extrusion_width=profile.printer.extrusion_width,
        ),
    )

    assert measured.has_process_calibration
    assert measured.overhang_limit_degrees == pytest.approx(52.0)
    assert print_settings.resolve(measured).support.threshold_angle == pytest.approx(52.0)


def test_the_slicer_supports_from_the_angle_the_analysis_uses() -> None:
    """Bis zum 27.09.2026 schrieb jede Übergabe 45 Grad über Elegoos 60 — der
    ElegooSlicer stützte am Minigolf-Satz Fasen, die die Analyse für druckbar
    hielt, und legte 46 m Stütze in die untersten 5 mm."""
    for printer in ("centauri-carbon-2", "prusa-mk4s", "generic-220"):
        profile = profiles.make_profile(printer, "pla")
        settings = print_settings.resolve(profile)
        assert settings.support.threshold_angle == pytest.approx(profile.overhang_limit_degrees)


def test_an_older_project_is_offered_the_printers_overhang_limit() -> None:
    """Ein gespeichertes Projekt trägt noch die 45 Grad — der Vorschlag holt es
    auf den Drucker, in beide Richtungen, und bleibt still, wo es passt."""
    centauri = profiles.make_profile("centauri-carbon-2", "pla")
    current = print_settings.resolve(centauri)
    older = print_settings.with_path(current, "support.threshold_angle", 45.0)

    offered = [e for e in advise.advise(older, centauri) if e.path == "support.threshold_angle"]
    assert [number(entry) for entry in offered] == [60.0]
    assert "support.threshold_angle" not in paths(advise.advise(current, centauri))

    mini = profiles.make_profile("prusa-mini", "pla")
    looser = print_settings.with_path(print_settings.resolve(mini), "support.threshold_angle", 45.0)
    stricter = [e for e in advise.advise(looser, mini) if e.path == "support.threshold_angle"]
    assert [number(entry) for entry in stricter] == [40.0]
    assert stricter[0].reason != offered[0].reason, "die andere Richtung hat ihren eigenen Grund"


@pytest.mark.parametrize("angle", [0.0, 90.0, -5.0, "steil"])
def test_an_overhang_limit_outside_the_quadrant_is_refused(angle: object) -> None:
    table = {"title": "Probe", "build_volume": [200.0, 200.0, 200.0], "overhang_limit": angle}

    with pytest.raises(ValidationError) as raised:
        profiles._printer_from_table("probe", table, Path("printers.toml"))
    assert raised.value.suggestions, "Regel 17"


def _plate_on_a_sloped_foot(angle: float) -> MeshData:
    """Eine Platte 60 mm im Quadrat, deren untere 4 mm ringsum unter ``angle``
    gegen die Senkrechte nach außen laufen — die Bodenkante des Bahnteils
    ``Gövde59`` aus dem Minigolf-Satz (``F:\\3D Dateien``, 27.09.2026):
    2 mm Bodenplatte mit gut 50 Grad Fase, darüber 45 bis 50 Grad nach außen
    geneigte Wände, zusammen 320 mm² Überhang über 45 Grad in Stücken bis
    25 mm², darüber nichts."""
    reach = 4.0 * math.tan(math.radians(angle))
    foot = [(x, y, 0.0) for x in (-30.0, 30.0) for y in (-30.0, 30.0)]
    wide = 30.0 + reach
    top = [(x, y, z) for x in (-wide, wide) for y in (-wide, wide) for z in (4.0, 10.0)]
    return MeshData.of(trimesh.convex.convex_hull(np.array(foot + top)))


def test_a_sloped_foot_the_printer_carries_gets_no_supports() -> None:
    """Der Minigolf-Satz am Centauri Carbon 2 (Robert, 27.09.2026): Die
    Startregel verlangte für 52 Grad Stützen, der Slicer baute einen
    treppenförmigen Stützfuß, der Brim zerfiel. Elegoo stützt ab 60 Grad —
    mit derselben Grenze bleibt der Vorschlag weg. Die Gegenprobe ist der
    allgemeine Drucker: Dort gilt 45, und dort bleibt er."""
    body = _plate_on_a_sloped_foot(52.0)

    def support_advised(printer: str) -> bool:
        profile = profiles.make_profile(printer, "pla")
        settings = print_settings.resolve(profile)
        result = slice_body(
            body,
            settings.layers.layer_height,
            first_layer_height=settings.layers.first_layer_height,
            overhang_angle=profile.overhang_limit_degrees,
            bridge_from=profile.minimum_wall_thickness,
            support_volume=False,
        )
        entries = advise.advise(settings, profile, result, bounds=body.bounds)
        return "support.style" in paths(entries)

    assert support_advised("generic-220"), "unter der Startregel ist es ein Überhang"
    assert not support_advised("centauri-carbon-2")
