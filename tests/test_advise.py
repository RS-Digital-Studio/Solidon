"""Die Vorschläge aus der Schichtanalyse (Bauplan §22.2, §29).

`test_print_settings.py` prüft die drei Ebenen und den Weg zum Slicer. Hier
stehen die Fälle, an denen die Regeln aus ``slice/advise.py`` selbst falsch
geurteilt haben — jeder mit dem Körper, der sie widerlegt hat.
"""

from __future__ import annotations

import math
from dataclasses import replace
from pathlib import Path

import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData
from app.core.knowledge import print_settings, profiles, rules
from app.core.slice import advise
from app.core.slice.analysis import OVERHANG_LAYER_WORTH_SUPPORT, WIDTH_INTERESTING, slice_body
from app.core.types import (
    LayerInfo,
    PrintSettings,
    Profile,
    SettingAdvice,
    SliceContour,
    SliceResult,
    SpeedSettings,
)
from tests.helpers import slice_contour

SQUARE = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))


@pytest.mark.parametrize("flavour", ["orca", "prusa", "cura"])
@pytest.mark.parametrize("kind", ["brim", "auto", "skirt", "raft"])
def test_a_tall_rod_needs_a_brim_touching_its_small_foot(flavour, kind) -> None:
    """Ein fest liegender Brim mit Lücke hält die dünne Stange nicht mit."""
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    settings = print_settings.with_path(settings, "adhesion.kind", kind)
    settings = print_settings.with_path(settings, "adhesion.brim_gap", 0.1)
    raw = trimesh.creation.cylinder(radius=3.85, height=122.0, sections=64)
    raw.apply_translation((0.0, 0.0, 61.0))
    mesh = MeshData.of(raw)
    result = slice_body(mesh, layer_height=0.2, support_volume=False)
    offered = advise.advise(settings, profile, result=result, bounds=mesh.bounds, flavour=flavour)
    gaps = [entry for entry in offered if entry.path == "adhesion.brim_gap"]
    if kind == "raft":
        assert not gaps
    else:
        assert len(gaps) == 1
        assert gaps[0].value == pytest.approx(0.0)
        assert gaps[0].was == pytest.approx(0.1)
    unchanged = print_settings.with_path(settings, "adhesion.brim_gap", 0.0)
    assert not any(
        entry.path == "adhesion.brim_gap"
        for entry in advise.advise(
            unchanged, profile, result=result, bounds=mesh.bounds, flavour=flavour
        )
    )


@pytest.mark.parametrize("size", [(30.0, 30.0, 200.0), (8.0, 8.0, 12.0)])
def test_a_broad_foot_or_short_body_keeps_its_brim_gap(size) -> None:
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    settings = print_settings.with_path(settings, "adhesion.kind", "brim")
    settings = print_settings.with_path(settings, "adhesion.brim_gap", 0.1)
    raw = trimesh.creation.box(extents=size)
    raw.apply_translation((0.0, 0.0, size[2] / 2.0))
    mesh = MeshData.of(raw)
    offered = advise.advise(
        settings,
        profile,
        result=slice_body(mesh, support_volume=False),
        bounds=mesh.bounds,
        flavour="orca",
    )
    assert not any(entry.path == "adhesion.brim_gap" for entry in offered)


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
            contours=(slice_contour(SQUARE),),
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


def test_the_flow_advice_can_be_told_apart() -> None:
    """Die Orca-Familie und PrusaSlicer deckeln das Tempo selbst nach dem
    Volumenstrom, den Solidon ihnen als Filamentwert schreibt. Derselbe Deckel
    als Vorschlag ändert dort nichts am Druck, und an der Kobra 2 hob er über
    die Innenwand die Lückenfüllung an (Gesamtprüfung, 27.09.2026). Der
    Druckdialog muss ihn erkennen können, ohne am angezeigten Text zu raten."""
    settings, profile = hot_and_fast()

    entries = advise.advise(settings, profile)

    inner = next(entry for entry in entries if entry.path == "speed.inner_wall")
    assert advise.limits_flow(inner)
    other = replace(inner, reason="Ein anderer Grund für dasselbe Feld")
    assert not advise.limits_flow(other), "am Grund erkannt, nicht am Feld"


@pytest.mark.parametrize("flavour", [None, "other", "cura", "orca", "prusa"])
@pytest.mark.parametrize("material, fitting", [("pla", False), ("pla", True), ("tpu-95a", False)])
def test_native_flow_limits_preserve_the_actual_reason_for_slow_walls(flavour, material, fitting):
    """B7: Ein später weggefilterter Volumenstromgrund verschluckte den
    Passungs- oder Materialgrund, der dieselbe Außenwand tatsächlich braucht.
    Platte und Einzelteil müssen dieselbe wirksame Empfehlung zurückgeben."""
    from app.core.types import BoundingBox

    profile = profiles.make_profile("bambu-p1s", material)
    settings = print_settings.with_path(print_settings.resolve(profile), "speed.outer_wall", 200.0)
    settings = print_settings.with_path(settings, "filament.max_flow", 0.6)
    fit_kinds = ("clearance",) if fitting else ()
    for entries in (
        advise.advise(settings, profile, fit_kinds=fit_kinds, flavour=flavour),
        advise.for_part(
            settings,
            BoundingBox((0.0, 0.0, 0.0), (30.0, 30.0, 10.0)),
            900.0,
            profile=profile,
            fit_kinds=fit_kinds,
            flavour=flavour,
        ),
    ):
        outer = [entry for entry in entries if entry.path == "speed.outer_wall"]
        if flavour in ("orca", "prusa"):
            assert not any(advise.limits_flow(entry) for entry in entries)
            if fitting or material == "tpu-95a":
                assert len(outer) == 1
                assert number(outer[0]) == pytest.approx(30.0)
            else:
                assert outer == []
        else:
            assert len(outer) == 1
            assert advise.limits_flow(outer[0])
            assert number(outer[0]) == pytest.approx(print_settings.flow_speed_limit(settings))


@pytest.mark.parametrize("flavour", [None, "cura", "orca", "prusa"])
@pytest.mark.parametrize("material", ["pla", "tpu-95a"])
def test_plate_wide_reasons_respect_the_slicers_own_flow_limit(flavour, material):
    """B7: Der Deckel des Slicers macht einen Flow-Vorschlag entbehrlich,
    aber nicht den langsameren Materialtransport von TPU."""
    profile = profiles.make_profile("bambu-p1s", material)
    settings = print_settings.with_path(print_settings.resolve(profile), "speed.outer_wall", 200.0)
    settings = print_settings.with_path(settings, "filament.max_flow", 12.0)

    wanted = advise.plate_paths(settings, profile, flavour=flavour)

    assert ("speed.outer_wall" in wanted) is (
        material == "tpu-95a" or flavour not in ("orca", "prusa")
    )


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
    settings = print_settings.with_path(
        print_settings.resolve(profiles.make_profile()), "cooling.minimum_layer_time", 0.0
    )
    rod = result_with([0.0] * 20, area=advise.THIN_LAYER_AREA / 2.0)

    entries = advise.advise(settings, profiles.make_profile(), rod)

    chosen = next(entry for entry in entries if entry.path == "cooling.minimum_layer_time")
    assert "spitz" not in str(chosen.reason), "das Teil verjüngt sich nicht, es ist überall dünn"


def test_a_minimum_layer_time_of_the_profile_stays() -> None:
    """Die Mindestzeit je Schicht ist die Antwort des Slicers auf kleine
    Schichten, und die Hersteller stimmen sie auf ihre Lüfter ab (Elegoo 4 s,
    Prusa 6 s). Vorgeschlagen wird nur, wo keine gilt — mit 15 s überstimmte
    der Rat sie im Druckerplan der Gesamtprüfung 97-mal."""
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    rod = result_with([0.0] * 20, area=advise.THIN_LAYER_AREA / 2.0)

    def advised(seconds: float) -> bool:
        settings = print_settings.with_path(
            print_settings.resolve(profile), "cooling.minimum_layer_time", seconds
        )
        return "cooling.minimum_layer_time" in {
            entry.path for entry in advise.advise(settings, profile, rod)
        }

    assert not advised(4.0), "Elegoos Wert"
    assert not advised(8.0), "Solidons Stufe"
    assert advised(0.0), "ohne Mindestzeit legt die Düse auf weiches Material"


@pytest.mark.parametrize(
    ("tip_layers", "area", "speed", "advised"),
    [
        pytest.param(20, 5.0, 20.0, True, id="spitze-bei-20-mm-s"),
        pytest.param(20, 5.0, advise.TIP_SPEED, False, id="schon-langsam-genug"),
        pytest.param(20, 400.0, 20.0, False, id="breite-schichten"),
        pytest.param(3, 5.0, 20.0, False, id="nur-die-letzten-schichten"),
    ],
)
def test_small_tips_get_a_slower_minimum_speed(
    tip_layers: int, area: float, speed: float, advised: bool
) -> None:
    """Der Slicer bremst eine kurze Schicht nur bis zum Mindesttempo. Elegoo,
    Bambu und Creality nennen für PLA 20 mm/s, und die obersten 12 mm des
    Drachen (08.10.2026) druckten in jedem Slicer unter ihrer Mindestzeit, die
    Spitzen in 0,1 bis 1,3 s je Schicht. Vorgeschlagen wird ein kleineres
    Mindesttempo, nicht eine längere Mindestzeit: Die bleibt beim Hersteller.
    Die letzten Schichten einer Kuppe allein lösen es nicht aus."""
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.resolve(profile)
    settings = print_settings.with_path(settings, "cooling.minimum_layer_time", 4.0)
    settings = print_settings.with_path(settings, "cooling.minimum_speed", speed)
    body = result_with([0.0] * 40)
    layers = tuple(
        replace(layer, area=area) if index >= len(body.layers) - tip_layers else layer
        for index, layer in enumerate(body.layers)
    )

    entries = advise.advise(settings, profile, replace(body, layers=layers))

    chosen = [entry for entry in entries if entry.path == "cooling.minimum_speed"]
    assert bool(chosen) is advised
    if advised:
        assert chosen[0].value == pytest.approx(advise.TIP_SPEED)
        assert "cooling.minimum_layer_time" not in {entry.path for entry in entries}


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


def _pieces(count: int, side: float) -> tuple[SliceContour, ...]:
    """``count`` getrennte Quadrate mit Kantenlänge ``side`` auf einer Schicht."""
    return tuple(
        slice_contour(
            (
                (x, 0.0),
                (x + side, 0.0),
                (x + side, side),
                (x, side),
            )
        )
        for x in (index * (side + 1.0) for index in range(count))
    )


def _overhang_layers(pieces: tuple[SliceContour, ...], layers: int = 20) -> SliceResult:
    """Ein Körper, dessen Schichten alle dieselben Überhangstücke tragen.

    Das Material jeder Schicht ist ein Steg, an dem die Stücke hängen, wie im
    Schnitt: Ein Stück liegt neben dem Material der Schicht darunter. Weit davon
    entfernt hingen alle Stücke für die Decken (``analysis._Ceilings``)
    aneinander, und der Stapel sah aus wie eine schräge Fläche (RM-570).
    """
    from shapely.geometry import Polygon as ShapelyPolygon
    from shapely.ops import unary_union

    area = sum(ShapelyPolygon(piece.outline).area for piece in pieces)
    low_x, low_y, high_x, _high_y = unary_union(
        [ShapelyPolygon(piece.outline) for piece in pieces]
    ).bounds
    web = (
        (low_x - 1.0, low_y - 1.0),
        (high_x + 1.0, low_y - 1.0),
        (high_x + 1.0, low_y),
        (low_x - 1.0, low_y),
    )
    stack = tuple(
        LayerInfo(
            z=float(index) * 0.2,
            contours=(slice_contour(web),),
            area=5000.0,
            overhang_area=area,
            islands=(),
            min_width=5.0,
            overhangs=pieces,
        )
        for index in range(layers)
    )
    return SliceResult(layers=stack, support_volume=0.0, first_layer_area=5000.0, source="internal")


def _slope(width: float, length: float, count: int) -> SliceResult:
    """Eine schräge Unterseite aus ``count`` Streifen, je Schicht einer:
    ``width`` breit, ``length`` lang, jeder neben dem Material der Schicht
    darunter, das bis zum vorigen Streifen reicht."""
    stack = tuple(
        LayerInfo(
            z=float(index) * 0.2,
            contours=(
                slice_contour(
                    (
                        (-10.0, 0.0),
                        ((index + 1) * width, 0.0),
                        ((index + 1) * width, length),
                        (-10.0, length),
                    )
                ),
            ),
            area=10.0 * length,
            overhang_area=width * length,
            islands=(),
            min_width=5.0,
            overhangs=(
                slice_contour(
                    (
                        (index * width, 0.0),
                        ((index + 1) * width, 0.0),
                        ((index + 1) * width, length),
                        (index * width, length),
                    )
                ),
            ),
        )
        for index in range(count)
    )
    return SliceResult(layers=stack, support_volume=0.0, first_layer_area=500.0, source="internal")


@pytest.mark.parametrize(
    ("width", "length", "count", "needed"),
    [
        pytest.param(0.4, 16.0, 30, True, id="kinn"),
        pytest.param(0.4, 16.0, 22, True, id="kinn-unter-der-summe"),
        pytest.param(0.4, 16.0, 16, False, id="feld-unter-hundert"),
        pytest.param(0.03, 100.0, 100, False, id="rauschen-einer-wand"),
    ],
)
def test_a_sloped_underside_is_one_field(
    width: float, length: float, count: int, needed: bool
) -> None:
    """Eine schräge Unterseite zerfällt im Schnitt in Streifen unter 10 mm², und
    der Rat sagte „keine Stützen“ — an einem Kinn mit 18° flacher Unterseite
    (Review vom 08.10.2026, 31 Streifen bis 6,4 mm², zusammen 189 mm²). In der
    Aufsicht ist sie ein Feld (``analysis.largest_sloped_patch``, RM-570).
    Ein Feld über 100 mm² trägt allein, auch wenn die Summe unter 150 bleibt
    (Review 3: 22 Streifen, Feld 134 mm²). Streifen schmaler als das
    Vernetzungsrauschen bleiben eine Wand, die sich selbst auffängt."""
    need = advise.support_need(_slope(width, length, count))

    assert need.needed is needed


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
    assert lattice.layers[0].overhang_area > OVERHANG_LAYER_WORTH_SUPPORT

    entries = advise.advise(settings, profile, lattice)

    assert "support.style" not in paths(entries)


def test_one_ceiling_of_the_same_area_still_gets_supports() -> None:
    """Dieselbe Fläche an einem Stück ist die Decke, um die es beim Deckel ging.

    Vorgeschlagen wird „Stützen an", die Art bestimmt das Profil des Slicers
    (Konzept Herstellerprofil, Entscheidung J) — bis zum 27.09.2026 hieß das
    Gitter, auch über Elegoos und Bambus Baum. **Unter einer großen flachen
    Decke wieder Gitter** (RM-584): Zwischen Baumspitzen hängt sie durch. Ohne
    Programm zählt „automatisch“ vorsichtig als Baum, wie bei Elegoo und Bambu;
    wo das Programm dafür normale Stütze druckt, bleibt es
    (``test_grid_over_automatic_only_where_automatic_means_trees``).
    """
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
    Waagerechte, PrusaSlicer für den MINI ``support_material_threshold`` 40 —
    im Prozess mit Input Shaper, den Prusa heute vorwählt; der ältere ohne ihn
    führt 50 und stand hier zuerst. Ohne Herstellerwert bleibt die Startregel."""
    centauri = profiles.make_profile("centauri-carbon-2", "pla")
    mini = profiles.make_profile("prusa-mini", "pla")
    plain = profiles.make_profile("generic-220", "pla")

    assert centauri.overhang_limit_degrees == pytest.approx(60.0)
    assert mini.overhang_limit_degrees == pytest.approx(50.0)
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

    # Die andere Richtung an einem Drucker, der strenger ist als die
    # Startregel. Der Bestand führt keinen mehr, seit MINI und XL die Grenze
    # ihres Input-Shaper-Prozesses tragen — die Regel gilt trotzdem.
    plain = profiles.make_profile("generic-220", "pla")
    strict = Profile(replace(plain.printer, overhang_limit=40.0), plain.material)
    looser = print_settings.with_path(
        print_settings.resolve(strict), "support.threshold_angle", 45.0
    )
    stricter = [e for e in advise.advise(looser, strict) if e.path == "support.threshold_angle"]
    assert [number(entry) for entry in stricter] == [40.0]
    assert stricter[0].reason != offered[0].reason, "die andere Richtung hat ihren eigenen Grund"


@pytest.mark.parametrize("angle", [0.0, 90.0, -5.0, "steil"])
def test_an_overhang_limit_outside_the_quadrant_is_refused(angle: object) -> None:
    table = {"title": "Probe", "build_volume": [200.0, 200.0, 200.0], "overhang_limit": angle}

    with pytest.raises(ValidationError) as raised:
        profiles._printer_from_table("probe", table, Path("printers.toml"))
    assert raised.value.suggestions, "Regel 17"


def _plate_with_webs(web: float) -> MeshData:
    """Eine Platte 60 × 60 × 2 mm mit einem Raster aus 8-mm-Löchern, zwischen
    denen Stege von ``web`` mm stehen — wie die Bahnen der Minigolf-Platte
    zwischen Loch 3, Loch 4 und dem inneren Bogen (27.09.2026)."""
    plate = trimesh.creation.box(extents=(60.0, 60.0, 2.0))
    hole, step = 8.0, 8.0 + web
    count = int(50.0 // step)
    start = -(count * step - web) / 2.0 + hole / 2.0
    holes = []
    for i in range(count):
        for j in range(count):
            box = trimesh.creation.box(extents=(hole, hole, 4.0))
            box.apply_translation((start + i * step, start + j * step, 0.0))
            holes.append(box)
    body = trimesh.boolean.difference([plate, *holes], engine="manifold")
    body.apply_translation((0.0, 0.0, 1.0))
    return MeshData.of(body)


def test_narrow_webs_get_a_slow_first_layer() -> None:
    """Roberts Minigolf-Platte am Centauri Carbon 2 (27.09.2026): Bei 105 mm/s
    rissen an den schmalen Stegen die kurzen Bodenbahnen der ersten Schicht,
    mit 50 mm/s für die ganze erste Schicht lief derselbe Druck sauber. Breite
    Stege halten, und eine erste Schicht, die schon langsam ist, bleibt."""
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    fast = print_settings.with_path(print_settings.resolve(profile), "speed.first_layer", 105.0)

    def first_layer_advice(body: MeshData, settings: PrintSettings) -> list[SettingAdvice]:
        result = slice_body(
            body,
            settings.layers.layer_height,
            first_layer_height=settings.layers.first_layer_height,
            overhang_angle=profile.overhang_limit_degrees,
            bridge_from=profile.minimum_wall_thickness,
            support_volume=False,
        )
        entries = advise.advise(settings, profile, result, bounds=body.bounds)
        return [entry for entry in entries if entry.path == "speed.first_layer"]

    narrow = first_layer_advice(_plate_with_webs(2.0), fast)

    assert len(narrow) == 1 and number(narrow[0]) == pytest.approx(advise.NARROW_WEB_SPEED)
    assert narrow[0].severity == "warning"
    assert not first_layer_advice(_plate_with_webs(6.0), fast), "breite Stege halten"
    slow = print_settings.with_path(fast, "speed.first_layer", 40.0)
    assert not first_layer_advice(_plate_with_webs(2.0), slow), "schon langsam genug"


def _slotted_plate(slots: int, length: float) -> MeshData:
    """Eine Platte 150 × 80 × 2 mm mit ``slots`` Schlitzen zu 22 × ``length``
    mm nebeneinander, dazwischen Stege von 2 mm — viel Steg auf einer großen
    ersten Schicht, wie beim Bahnteil ``Gövde59`` aus Roberts Minigolf-Satz
    (8,6 % der ersten Schicht, 195 mm², 27.09.2026)."""
    plate = trimesh.creation.box(extents=(150.0, 80.0, 2.0))
    step = 22.0 + 2.0
    start = -(slots * step - 2.0) / 2.0 + 11.0
    cuts = []
    for index in range(slots):
        cut = trimesh.creation.box(extents=(22.0, length, 4.0))
        cut.apply_translation((start + index * step, 0.0, 0.0))
        cuts.append(cut)
    body = trimesh.boolean.difference([plate, *cuts], engine="manifold")
    body.apply_translation((0.0, 0.0, 1.0))
    return MeshData.of(body)


def test_a_large_part_with_long_narrow_webs_gets_a_slow_first_layer() -> None:
    """Gefragt wird auch die Fläche der Stege, nicht nur ihr Anteil.

    Robert, 27.09.2026: Der Rumpf ``Gövde59`` trägt 8,6 % seiner ersten
    Schicht in Stegen unter drei Millimetern, zusammen 195 mm², und genau dort
    rissen bei 105 mm/s die Bodenbahnen. Gegen den Anteil allein blieb die
    Regel stumm: Geeicht war sie an der ganzen Platte (22 % mit den Schäften),
    gefragt wird sie je Teil. Im Korpus (186 Körper) liegen nur sieben
    zwischen 3 und 10 %; mit 100 mm² kommen der Rumpf und ein Besenhalter
    dazu, der Wedge-Lock mit 78 mm² nicht.
    """
    from app.core.slice.analysis import narrow_share

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    fast = print_settings.with_path(print_settings.resolve(profile), "speed.first_layer", 105.0)
    width = advise.NARROW_WEB_LINES * fast.layers.first_layer_line_width

    def measured(body: MeshData) -> tuple[float, float, list[SettingAdvice]]:
        result = slice_body(
            body,
            fast.layers.layer_height,
            first_layer_height=fast.layers.first_layer_height,
            overhang_angle=profile.overhang_limit_degrees,
            bridge_from=profile.minimum_wall_thickness,
            support_volume=False,
        )
        share = narrow_share(result.layers[0], width)
        entries = advise.advise(fast, profile, result, bounds=body.bounds)
        return (
            share,
            share * result.layers[0].area,
            [entry for entry in entries if entry.path == "speed.first_layer"],
        )

    share, area, advice = measured(_slotted_plate(5, 60.0))
    assert share < advise.NARROW_WEB_SHARE, "die Vorbedingung: unter dem Anteil"
    assert area >= advise.NARROW_WEB_AREA, "die Vorbedingung: über der Fläche"
    assert [number(entry) for entry in advice] == [pytest.approx(advise.NARROW_WEB_SPEED)]

    share, area, advice = measured(_slotted_plate(2, 20.0))
    assert share < advise.NARROW_WEB_SHARE and area < advise.NARROW_WEB_AREA, (
        "die Gegenprobe: ein kurzer Steg auf einer großen Platte"
    )
    assert not advice


def test_a_sloped_foot_the_printer_carries_gets_no_supports() -> None:
    """Der Minigolf-Satz am Centauri Carbon 2 (Robert, 27.09.2026): Die
    Startregel verlangte für 52 Grad Stützen, der Slicer baute einen
    treppenförmigen Stützfuß, der Brim zerfiel. Elegoo stützt ab 60 Grad —
    mit derselben Grenze bleibt der Vorschlag weg. Die Gegenprobe ist der
    allgemeine Drucker: Dort gilt 45, und dort bleibt er."""
    from tests.helpers import plate_on_a_sloped_foot

    body = plate_on_a_sloped_foot(52.0)

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


# --- je Teil (Konzept Herstellerprofil, Entscheidung G) ---------------------------


def test_a_part_asks_for_supports_only_where_its_own_geometry_needs_them() -> None:
    """Was an der Geometrie hängt, gilt dem Körper: Der mit der freien Decke
    bekommt Stützen, der daneben ohne Überhang nichts. Plattenweite Regeln —
    Maschine, Material, Volumenstrom — gehören nicht in den Rat je Teil."""
    from app.core.types import BoundingBox

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    box = BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(40.0, 40.0, 20.0))

    hanging = advise.for_part(
        settings, box, 1600.0, profile=profile, result=result_with([0.0, 0.0, 138.0, 0.0])
    )
    plain = advise.for_part(
        settings, box, 1600.0, profile=profile, result=result_with([0.0, 0.0, 0.0, 0.0])
    )

    assert "support.style" in paths(hanging)
    assert paths(hanging) <= advise.PART_PATHS
    assert "support.style" not in paths(plain)
    assert advise.for_part(settings, box, 1600.0) == [], "ohne Profil nur die Brim-Regeln"


def test_a_material_reason_keeps_its_value_on_the_plate() -> None:
    """ABS auf einem offenen Drucker verlangt einen Brim wegen des Materials.
    Übernommen gilt er der ganzen Platte, auch wo die Geometrie eines Teils ihn
    ebenfalls verlangt (:func:`advise.plate_paths`)."""
    abs_open = profiles.make_profile("prusa-mk4s", "abs")
    pla_open = profiles.make_profile("prusa-mk4s", "pla")

    def skirted(profile: Profile) -> PrintSettings:
        # Eine Grundlage mit Schürze, wie der Hersteller sie oft trägt;
        # Solidons Tabelle legt für ABS schon selbst einen Brim.
        return print_settings.with_path(print_settings.resolve(profile), "adhesion.kind", "skirt")

    assert "adhesion.kind" in advise.plate_paths(skirted(abs_open), abs_open)
    assert "adhesion.kind" not in advise.plate_paths(skirted(pla_open), pla_open)


def test_the_stack_tells_which_body_carries_a_fit() -> None:
    """Der Deckel legt zwei Flächen mit Spiel aufeinander; der Stift daneben
    trägt keine Passung. Der Dialog fragt für die Platte, der Export je Teil
    (``fits.fit_kinds_for``)."""
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.fits import fit_kinds_for
    from app.core.types import Document

    document = Document(format_version=1, app_version="0.0.1")
    history = History(document)
    history.apply(
        "Dose", [OperationDraft(op="create_cylinder", params={"diameter": 40.0, "height": 20.0})]
    )
    history.apply(
        "Stift", [OperationDraft(op="create_cylinder", params={"diameter": 8.0, "height": 10.0})]
    )
    lid = history.apply(
        "Deckel", [OperationDraft(op="create_lid", inputs=("obj_1",), params={"thickness": 2.4})]
    )
    result = evaluate(document, profiles.make_profile())
    lid_outputs = set(document.ops[-1].outputs)
    pin_id = next(
        entry.id
        for entry in result.scene.objects.values()
        if entry.id not in lid_outputs and entry.id != "obj_1"
    )

    assert lid is not None
    assert fit_kinds_for(document, lid_outputs) == ("clearance",)
    assert fit_kinds_for(document, {pin_id}) == ()


def test_a_suppressed_fit_step_does_not_suggest_a_slicer_fit() -> None:
    """Ein ausgeschalteter Einsatz verlangt keine langsame Außenwand."""
    from app.core.scene.fits import fit_kinds_for
    from app.core.types import Document, Operation, Suppression

    operation = Operation(id=1, op="insert_nut_trap", outputs=("obj_1",))
    active = Document(format_version=1, app_version="0.0.1", ops=(operation,))
    suppressed = Document(
        format_version=1,
        app_version="0.0.1",
        ops=(replace(operation, suppressed=Suppression()),),
    )

    assert fit_kinds_for(active, {"obj_1"}) == ("clearance",)
    assert fit_kinds_for(suppressed, {"obj_1"}) == ()


# --- Schrägnaht an runden Außenwänden -------------------------------------------


def _standing(mesh: trimesh.Trimesh) -> SliceResult:
    """Der Körper auf dem Bett, geschnitten im Raster von 0,2 mm."""
    mesh.apply_translation((0.0, 0.0, -mesh.bounds[0][2]))
    return slice_body(MeshData.of(mesh), 0.2)


def test_a_round_outer_wall_asks_for_a_scarf_seam() -> None:
    """Roberts Minigolf-Schäfte (27.09.2026): Auf der runden Außenwand fand die
    Naht keine Ecke und zog sich als Linie über 200 mm. Der runde Körper
    bekommt die Schrägnaht vorgeschlagen, der eckige nicht — dort verschwindet
    die Naht in einer Kante —, und ein Stift unter zwei Rampenlängen Umfang
    auch nicht."""
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)

    def scarf(mesh: trimesh.Trimesh) -> list[SettingAdvice]:
        return [
            entry
            for entry in advise.advise(settings, profile, _standing(mesh))
            if entry.path == "shell.scarf_seam"
        ]

    round_one = scarf(trimesh.creation.cylinder(radius=12.5, height=40.0, sections=128))
    assert [(entry.value, entry.severity) for entry in round_one] == [(True, "info")]
    assert not scarf(trimesh.creation.box(extents=(25.0, 25.0, 40.0)))
    assert not scarf(trimesh.creation.cylinder(radius=4.0, height=40.0, sections=64))
    assert not scarf(trimesh.creation.cylinder(radius=12.5, height=6.0, sections=128)), (
        "unter der Mindesthöhe wird aus der Naht keine Linie"
    )
    assert "shell.scarf_seam" in advise.PART_PATHS


def test_scarf_advice_follows_a_changed_shared_ramp_length(monkeypatch: pytest.MonkeyPatch) -> None:
    """B12: Bei einer längeren ausgegebenen Rampe darf ein kleiner Umfang
    nicht weiter die Empfehlung für die abgeschriebene 20-mm-Rampe bekommen."""
    import importlib

    from app.core.export import handover, slicer_keys

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    round_one = _standing(trimesh.creation.cylinder(radius=12.5, height=20.0, sections=128))
    try:
        with monkeypatch.context() as changed:
            changed.setattr(print_settings, "SCARF_LENGTH", 50.0, raising=False)
            importlib.reload(slicer_keys)
            importlib.reload(advise)
            assert "shell.scarf_seam" not in paths(advise.advise(settings, profile, round_one))
            selected = print_settings.with_choice(settings, "shell.scarf_seam", True)
            for flavour, key in (
                ("orca", "seam_slope_min_length"),
                ("prusa", "scarf_seam_length"),
                ("cura", "scarf_joint_seam_length"),
            ):
                assert float(handover.as_mapping(selected, flavour)[key]) == pytest.approx(50.0)
    finally:
        importlib.reload(slicer_keys)
        importlib.reload(advise)


def test_a_polygon_with_corners_hides_its_seam_itself() -> None:
    """Glatt heißt: kein Knick über 25°, das Gegenstück zu Orcas Schwelle von
    155°. Ein Zwölfkant knickt an jeder Ecke um 30° und behält seine Naht in
    einer Ecke; mit 128 Seiten knickt der Zylinder um knapp 3°."""
    from app.core.slice.analysis import smooth_outline_height

    twelve = _standing(trimesh.creation.cylinder(radius=12.5, height=20.0, sections=12))
    fine = _standing(trimesh.creation.cylinder(radius=12.5, height=20.0, sections=128))

    assert smooth_outline_height(twelve, advise.SCARF_MIN_LOOP, 0.4) == 0.0
    assert smooth_outline_height(fine, advise.SCARF_MIN_LOOP, 0.4) == pytest.approx(20.0, abs=0.3)


def test_a_tight_rounding_is_a_corner_for_the_slicer() -> None:
    """Der Knick zählt über Arme von der Düsenbreite, wie im Slicer. Zwischen
    benachbarten Facetten gemessen, galt der Rumpf von Roberts Minigolf-Satz
    als glatt — seine engen Rundungen knicken dort nur wenige Grad je Facette —,
    und ElegooSlicer sah Ecken von 45° und setzte keine Schrägnaht. Eine
    Rundung von 0,3 mm ist eine Ecke, eine von 4 mm nicht."""
    import shapely

    from app.core.slice.analysis import smooth_outline_height

    def extruded(radius: float) -> SliceResult:
        outline = shapely.box(-10.0, -10.0, 10.0, 10.0).buffer(radius, quad_segs=16)
        return _standing(trimesh.creation.extrude_polygon(outline, 20.0))

    assert smooth_outline_height(extruded(0.3), advise.SCARF_MIN_LOOP, 0.4) == 0.0
    assert smooth_outline_height(extruded(4.0), advise.SCARF_MIN_LOOP, 0.4) == pytest.approx(
        20.0, abs=0.3
    )


# --- Unterschrittene Materialtemperatur bleibt nach der Auflösung sichtbar ------------


@pytest.mark.parametrize("maximum,expected", [(230.0, True), (240.0, False), (260.0, False)])
def test_the_nozzle_limit_compares_the_material_request(maximum: float, expected: bool) -> None:
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    profile = replace(profile, printer=replace(profile.printer, nozzle_temperature_max=maximum))
    settings = print_settings.resolve(profile)
    findings = advise.warnings_for(settings, profile)
    matches = [item for item in findings if item.code == "settings.nozzle_below_material"]
    assert bool(matches) is expected
    if expected:
        assert matches[0].values["wanted"] == pytest.approx(240.0)
        assert matches[0].values["possible"] == pytest.approx(maximum)


def _table_on_corner_feet(top: float):
    """Vier Füße 10 × 10 mm (kleine Standflächen) bündig an den Ecken einer
    Platte ``top`` mm im Quadrat — wie die Waschschüssel, deren Füße am Rand
    stehen: Der Rand um die erste Schicht reicht so weit wie die Platte."""
    reach = (top - 10.0) / 2.0
    feet = []
    for x in (-reach, reach):
        for y in (-reach, reach):
            foot = trimesh.creation.box(extents=(10.0, 10.0, 2.0))
            foot.apply_translation((x, y, 1.0))
            feet.append(foot)
    plate = trimesh.creation.box(extents=(top, top, 2.0))
    plate.apply_translation((0.0, 0.0, 3.0))
    mesh = MeshData.of(trimesh.boolean.union([*feet, plate]))
    return mesh, slice_body(mesh, 0.2)


def _table_on_a_foot(top: float):
    """Ein Fuß 10 × 10 mm in der Mitte, darauf eine Platte ``top`` mm im Quadrat."""
    foot = trimesh.creation.box(extents=(10.0, 10.0, 2.0))
    foot.apply_translation((0.0, 0.0, 1.0))
    plate = trimesh.creation.box(extents=(top, top, 2.0))
    plate.apply_translation((0.0, 0.0, 3.0))
    mesh = MeshData.of(trimesh.boolean.union([foot, plate]))
    return mesh, slice_body(mesh, 0.2)


@pytest.mark.parametrize(
    ("top", "width"),
    [
        (120.0, None),  # 30 mm Rand: der Brim des Profils (5 mm) passt
        (172.0, "schmaler"),  # 4 mm Rand: ein schmalerer Brim
        (179.6, "keiner"),  # 0,2 mm: kein Brim, dafür ein Befund
    ],
)
def test_a_brim_is_suggested_only_as_wide_as_the_bed_allows(top, width) -> None:
    """Auf 180 × 180 mm (MINI): Die Waschschüssel bekam auf 220 × 220 mm einen
    Brim von 5 mm vorgeschlagen und passte nur schräg mit 0,15 mm Rand —
    CuraEngine druckte den Rand neben das Bett (04.10.2026)."""
    profile = profiles.make_profile("prusa-mini", "pla")
    settings = print_settings.with_path(print_settings.resolve(profile), "adhesion.kind", "skirt")
    mesh, result = _table_on_corner_feet(top)

    entries = advise.advise(settings, profile, result, bounds=mesh.bounds)
    kinds = [entry.value for entry in entries if entry.path == "adhesion.kind"]
    widths = [entry.value for entry in entries if entry.path == "adhesion.brim_width"]
    findings = [item.code for item in advise.located_warnings(result, profile)]
    room = (180.0 - top) / 2.0

    assert advise.brim_room(result, profile) == pytest.approx(room, abs=0.01)
    if width is None:
        assert kinds == ["brim"] and not widths
        assert "settings.brim_no_room" not in findings
    elif width == "keiner":
        # Auch der Skirt des Profils hätte keinen Platz: ohne ihn.
        assert kinds == ["none"] and not widths
        assert "settings.brim_no_room" in findings
    else:
        measured = advise.brim_room(result, profile)
        assert measured is not None
        assert kinds == ["brim"] and widths == [pytest.approx(math.floor(measured * 10.0) / 10.0)]
        assert 3.5 < widths[0] <= measured
        assert "settings.brim_no_room" not in findings


def test_the_brim_room_is_measured_around_the_first_layer() -> None:
    """RM-312: Brim und Skirt liegen um die erste Schicht, nicht um die Aufsicht.

    Dieselbe Platte (179,6 mm auf dem MINI, 0,2 mm Luft) auf einem Fuß in der
    Mitte: Um den Fuß hat ein Brim Platz, und vorgeschlagen wird der des
    Profils. Gemessen an der Aufsicht hieß es „kein Platz“ — wie beim
    garden-hose-holder, der oben breiter ist als am Fuß. Die Gegenprobe mit
    Füßen an den Ecken steht im Test darüber."""
    profile = profiles.make_profile("prusa-mini", "pla")
    settings = print_settings.with_path(print_settings.resolve(profile), "adhesion.kind", "skirt")
    mesh, result = _table_on_a_foot(179.6)

    entries = advise.advise(settings, profile, result, bounds=mesh.bounds)
    kinds = [entry.value for entry in entries if entry.path == "adhesion.kind"]
    widths = [entry.value for entry in entries if entry.path == "adhesion.brim_width"]
    findings = [item.code for item in advise.located_warnings(result, profile)]

    # Fuß 10 mm, Bett 180 mm: (180 - 10) / 2 = 85 mm um ihn, die Platte passt dabei.
    assert advise.brim_room(result, profile) == pytest.approx(85.0, abs=0.01)
    assert kinds == ["brim"] and not widths
    assert "settings.brim_no_room" not in findings


def _reason_texts() -> list[tuple[int, str]]:
    """Jeder Grund des Druckrats als Quelltext — Zeile und deutscher Satz.

    Gelesen am Quelltext und nicht an Läufen: Ein Grund, den kein Testkörper
    auslöst, steht trotzdem im Dialog. Ein Grund ist jedes ``_()`` in
    ``advise.py`` außerhalb eines ``Finding`` und einer ``ValidationError`` —
    deren Sätze gehen in den Prüfbericht, nicht in die Tabelle des Dialogs.
    Dazu der Satz jedes Ersatzes (``slicer_keys.NOT_OFFERED_BY_PROGRAM``): Er
    steht als Grund in derselben Tabelle, wo ein Vorschlag die Art wechselt
    (``slicer_keys.offered``, Review RM-584, M2), Zeile 0.
    """
    from app.core.export import slicer_keys

    substitutes = {
        replaced.reason.msgid
        for paths in slicer_keys.NOT_OFFERED_BY_PROGRAM.values()
        for choices in paths.values()
        for replaced in choices.values()
    }
    return _advise_reason_texts() + [(0, text) for text in sorted(substitutes)]


def _advise_reason_texts() -> list[tuple[int, str]]:
    """Die Gründe aus ``advise.py`` (:func:`_reason_texts`)."""
    import ast

    tree = ast.parse(Path(advise.__file__).read_text(encoding="utf-8"))
    elsewhere: set[int] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id in {"Finding", "ValidationError"}
        ):
            elsewhere.update(id(inner) for inner in ast.walk(node))
    return [
        (node.lineno, node.args[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_"
        and node.args
        and isinstance(node.args[0], ast.Constant)
        and isinstance(node.args[0].value, str)
        and id(node) not in elsewhere
    ]


def test_every_reason_fits_under_the_table_of_the_print_dialog() -> None:
    """Ein Grund ist ein Satz von höchstens 60 Zeichen, in jeder Sprache lesbar.

    Der Druckdialog zeigt den Grund der gewählten Zeile unter der Tabelle; in
    der Spalte daneben endeten 40 von 45 Gründen auf „…“ (RM-514). Deutsch
    höchstens 60 Zeichen, jeder Katalog höchstens 70 — Übersetzungen sind in
    Zeichen bis zu einem Zehntel länger. Und jeder Grund steht einmal: Wo zwei
    Regeln dasselbe sagen, teilen sie sich eine Konstante, sonst laufen die
    Sätze auseinander.
    """
    from collections import Counter

    from app.i18n.catalog import available_languages, read_catalog

    reasons = _reason_texts()
    assert len(reasons) >= 30, f"nur {len(reasons)} Gründe gefunden — liest der Test noch?"
    long = [f"{line}: {len(text)} {text}" for line, text in reasons if len(text) > 60]
    assert not long, f"länger als 60 Zeichen: {long}"
    twice = [text for text, count in Counter(text for _, text in reasons).items() if count > 1]
    assert not twice, f"derselbe Grund an zwei Stellen, gehört in eine Konstante: {twice}"
    for language in available_languages():
        if language == "de":
            continue
        catalog = read_catalog(language)
        wide = [
            f"{catalog[text]!r} ({len(catalog[text])})"
            for _, text in reasons
            if len(catalog.get(text, "")) > 70
        ]
        assert not wide, f"{language}: länger als 70 Zeichen: {wide}"
