"""Die Vorschläge aus der Schichtanalyse (Bauplan §22.2, §29).

`test_print_settings.py` prüft die drei Ebenen und den Weg zum Slicer. Hier
stehen die Fälle, an denen die Regeln aus ``slice/advise.py`` selbst falsch
geurteilt haben — jeder mit dem Körper, der sie widerlegt hat.
"""

from __future__ import annotations

from app.core.knowledge import print_settings, profiles
from app.core.slice import advise
from app.core.slice.analysis import WIDTH_INTERESTING
from app.core.types import (
    LayerInfo,
    Polygon,
    PrintSettings,
    Profile,
    SettingAdvice,
    SliceResult,
)

SQUARE = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))


def result_with(
    overhangs: list[float], *, area: float = 5000.0, min_width: float = 5.0
) -> SliceResult:
    """Ein Schnittergebnis mit vorgegebener Überhangfläche je Schicht.

    Die Vorschläge lesen nur Kennzahlen; die Konturen stehen dabei, damit die
    Schichten nicht leer sind.
    """
    layers = tuple(
        LayerInfo(
            z=float(index) * 0.2,
            contours=(Polygon(outline=SQUARE),),
            area=area,
            overhang_area=overhang,
            islands=(),
            min_width=min_width,
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


def test_that_same_place_is_said_out_loud() -> None:
    """Und die andere Hälfte: Wo kein Wert hilft, steht ein Befund."""
    settings, profile, least = barely_narrow()
    thin = 1.5 * least

    findings = advise.warnings_for(settings, profile, result_with([0.0] * 20, min_width=thin))

    hits = [entry for entry in findings if entry.code == "settings.wall_below_nozzle"]
    assert hits, "zwischen einer und zwei Bahnen schwieg vorher alles"
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
    """Geprüft wurden zwei von sechs Geschwindigkeiten.

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
