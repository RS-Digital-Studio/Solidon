"""Druckeinstellungen, Empfehlung und Slicer-Übergabe (Bauplan §29, §28).

Drei Sachen, die zusammengehören: Solidon hält die Einstellungen, die
Geometrie ändert sie, und der Slicer bekommt sie in seiner eigenen Sprache
geschrieben. Getestet wird ohne installierten Slicer — was einen Fremdprozess
braucht, steht ausdrücklich dabei.
"""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path
from typing import get_args, get_type_hints

import pytest

from app.core.errors import ExternalToolError, ValidationError
from app.core.export import handover, slicer_keys
from app.core.knowledge import print_settings, profiles
from app.core.slice import advise
from app.core.types import (
    BoundingBox,
    LayerInfo,
    SliceResult,
)

MESHES = Path(__file__).parent / "data" / "meshes"


def _layers(
    *areas: float, overhang: float = 0.0, islands: bool = False, min_width: float = 5.0
) -> SliceResult:
    """Ein Schnittergebnis mit vorgegebenen Flächen — für die Vorschläge reicht
    das, sie lesen nur Kennzahlen."""
    square = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))
    layers = tuple(
        LayerInfo(
            z=float(index) * 0.2,
            contours=(square,),
            area=area,
            overhang_area=overhang,
            islands=(square,) if islands and index > 0 else (),
            min_width=min_width,
        )
        for index, area in enumerate(areas)
    )
    return SliceResult(
        layers=layers,
        support_volume=overhang * 0.2 * len(areas),
        first_layer_area=areas[0] if areas else 0.0,
        source="internal",
    )


# --- die drei Ebenen (§29) ----------------------------------------------------------


def test_the_quality_preset_decides_the_layer_height() -> None:
    profile = profiles.make_profile("prusa-mk4s", "pla")
    draft = print_settings.resolve(profile, "draft")
    fine = print_settings.resolve(profile, "fine")

    assert draft.layers.layer_height > fine.layers.layer_height
    assert fine.shell.top_layers > draft.shell.top_layers


def test_the_material_decides_the_temperature() -> None:
    printer = "prusa-mk4s"
    pla = print_settings.resolve(profiles.make_profile(printer, "pla"))
    petg = print_settings.resolve(profiles.make_profile(printer, "petg"))

    assert petg.temperature.nozzle > pla.temperature.nozzle
    assert petg.cooling.fan_speed < pla.cooling.fan_speed
    # Die Stufe ist dieselbe — die Schichthöhe darf sich am Material nicht
    # ändern, sonst wäre die Aufteilung der Ebenen sinnlos.
    assert petg.layers.layer_height == pla.layers.layer_height


def test_a_wider_nozzle_lays_thicker_layers() -> None:
    profile = profiles.make_profile("prusa-mk4s", "pla")
    wide = replace(profile, printer=replace(profile.printer, nozzle_diameter=0.6))

    narrow = print_settings.resolve(profile)
    thick = print_settings.resolve(wide)

    assert thick.layers.layer_height > narrow.layers.layer_height
    assert thick.layers.layer_height <= 0.6 * print_settings.MAX_LAYER_RATIO


def test_the_printer_caps_what_the_material_asks_for() -> None:
    """Ein Profil, das heißer will, als die Maschine kann, ist ein stiller
    Schaden — hier wird er laut."""
    profile = profiles.make_profile("anycubic-kobra-2", "asa")
    settings = print_settings.resolve(profile)

    assert settings.temperature.nozzle <= profile.printer.nozzle_temperature_max


def test_an_open_printer_gets_no_chamber_temperature() -> None:
    open_printer = print_settings.resolve(profiles.make_profile("prusa-mk4s", "abs"))
    closed = print_settings.resolve(profiles.make_profile("bambu-x1c", "abs"))

    assert open_printer.temperature.chamber == 0
    assert closed.temperature.chamber > 0


def test_an_unknown_material_still_yields_settings() -> None:
    """Ein eigenes Filament soll sich benutzen lassen, bevor jemand eine
    Tabelle dafür pflegt."""
    profile = profiles.make_profile("prusa-mk4s", "pla")
    strange = replace(profile, material=replace(profile.material, id="pa-cf-eigenbau"))

    settings = print_settings.resolve(strange)

    assert settings.temperature.nozzle > 0


def test_an_unknown_quality_is_refused_by_name() -> None:
    with pytest.raises(ValidationError):
        print_settings.resolve(profiles.make_profile(), "hochglanz")  # type: ignore[arg-type]


# --- Pfadzugriff --------------------------------------------------------------------


def test_a_value_can_be_read_and_set_through_its_path() -> None:
    settings = print_settings.resolve(profiles.make_profile())

    changed = print_settings.with_path(settings, "support.style", "tree")

    assert print_settings.read_path(changed, "support.style") == "tree"
    # Unveränderlich: der Vorschlag darf das Original nicht anfassen, sonst
    # ließe er sich nicht mehr verwerfen.
    assert settings.support.style == "none"


@pytest.mark.parametrize("path", ["", "support", "erfunden.wert", "support.gibtesnicht"])
def test_a_path_that_points_nowhere_is_refused(path: str) -> None:
    settings = print_settings.resolve(profiles.make_profile())
    with pytest.raises(ValidationError):
        print_settings.read_path(settings, path)


# --- Vorschläge aus der Geometrie (§29) ---------------------------------------------


def _paths(entries: list) -> set[str]:
    return {entry.path for entry in entries}


def test_islands_ask_for_supports() -> None:
    settings = print_settings.resolve(profiles.make_profile())
    result = _layers(500.0, 500.0, 500.0, islands=True)

    entries = advise.advise(settings, profiles.make_profile(), result)

    assert "support.style" in _paths(entries)
    chosen = next(entry for entry in entries if entry.path == "support.style")
    assert chosen.value != "none"
    assert chosen.reason, "ein Vorschlag ohne Grund ist keiner"


def test_a_part_that_floats_nowhere_gets_its_supports_taken_away() -> None:
    settings = print_settings.with_path(
        print_settings.resolve(profiles.make_profile()), "support.style", "grid"
    )
    result = _layers(500.0, 500.0, 500.0)

    entries = advise.advise(settings, profiles.make_profile(), result)

    chosen = next(entry for entry in entries if entry.path == "support.style")
    assert chosen.value == "none"


def test_a_wall_thinner_than_two_lines_asks_for_a_narrower_line() -> None:
    """Die Wandstärkenprüfung sitzt hier und nicht in jeder Operation (E1).

    Konzept P15 hatte sie für ``push_face`` vorgesehen — eine Wand, die der
    Zug unter das Materialminimum bringt, soll das sagen. Sie steht schon, und
    zwar besser: sie misst am **ganzen** Körper statt nur an der gezogenen
    Fläche, sie läuft dort, wo die Schichtanalyse ohnehin rechnet, und sie
    nennt die Linienbreite, mit der die Stelle doch entsteht.

    Sie in eine Operation zu kopieren hieße, je Zug eine Schichtanalyse zu
    fahren — Sekunden für eine Zahl, die der Bericht danach ohnehin nennt.

    Dieser Test hält die Zusage fest; ohne ihn stand die Prüfung ungeprüft im
    Code.
    """
    settings = print_settings.resolve(profiles.make_profile())
    two_lines = 2.0 * settings.layers.line_width
    result = _layers(500.0, 500.0, 500.0, min_width=two_lines * 0.6)

    entries = advise.advise(settings, profiles.make_profile(), result)

    chosen = next(entry for entry in entries if entry.path == "layers.line_width")
    assert chosen.value < settings.layers.line_width, "eine schmalere Linie erreicht die Stelle"
    assert chosen.severity == "warning"
    assert chosen.reason, "ein Vorschlag ohne Grund ist keiner"


def test_a_wall_wide_enough_says_nothing() -> None:
    """Eine Wand, die passt, bekommt keinen Vorschlag — sonst stünde an jedem
    Teil einer."""
    settings = print_settings.resolve(profiles.make_profile())
    result = _layers(500.0, 500.0, 500.0, min_width=5.0)

    entries = advise.advise(settings, profiles.make_profile(), result)

    assert "layers.line_width" not in _paths(entries)


def test_a_small_footprint_asks_for_a_brim() -> None:
    settings = print_settings.resolve(profiles.make_profile())
    result = _layers(80.0, 80.0, 80.0)

    entries = advise.advise(settings, profiles.make_profile(), result)

    brim = [entry for entry in entries if entry.path == "adhesion.kind"]
    assert brim and brim[0].value == "brim"


def test_a_tall_slim_part_asks_for_a_brim() -> None:
    settings = print_settings.resolve(profiles.make_profile())
    result = _layers(*[600.0] * 6)
    bounds = BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(20.0, 20.0, 200.0))

    entries = advise.advise(settings, profiles.make_profile(), result, bounds=bounds)

    assert "adhesion.kind" in _paths(entries)


def test_warping_material_on_an_open_printer_is_a_finding_not_a_change() -> None:
    """Die Materialtabelle setzt für ABS schon Brim und wenig Lüfter — es gibt
    nichts zu ändern. Gesagt werden muss es trotzdem."""
    profile = profiles.make_profile("prusa-mk4s", "abs")
    settings = print_settings.resolve(profile)

    assert settings.adhesion.kind == "brim"
    assert not [
        entry for entry in advise.advise(settings, profile) if entry.path == "adhesion.kind"
    ]

    findings = advise.warnings_for(settings, profile)
    codes = {finding.code for finding in findings}
    assert "settings.warping_material_open_printer" in codes
    assert all(finding.source == "internal" for finding in findings)


def test_the_same_material_in_a_closed_chamber_is_no_warning() -> None:
    profile = profiles.make_profile("bambu-x1c", "abs")
    settings = print_settings.resolve(profile)

    codes = {finding.code for finding in advise.warnings_for(settings, profile)}
    assert "settings.warping_material_open_printer" not in codes


def test_a_ceiling_spanning_free_air_is_reported() -> None:
    """Der Fall, der einen Satz Gewürzbehälter gekostet hat (§22.2).

    Eine waagerechte Ringschulter im Becher: der Slicer überspannte sie mit
    geraden Bahnen quer über die Öffnung, 27 mm frei. Keine Einstellung behebt
    das — also ein Befund, kein Vorschlag, und er nennt die Höhe, damit man
    hinsehen kann.
    """
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    spanning = _layers(100.0, 100.0, 100.0)
    spanning = SliceResult(
        layers=tuple(
            replace(layer, bridge_width=26.8 if index == 2 else 0.0)
            for index, layer in enumerate(spanning.layers)
        ),
        support_volume=spanning.support_volume,
        first_layer_area=spanning.first_layer_area,
    )

    findings = advise.warnings_for(settings, profile, spanning)
    spans = [finding for finding in findings if finding.code == "slice.long_bridge"]

    assert spans, "27 mm free air has to be said out loud"
    assert spans[0].values["span_mm"] == pytest.approx(26.8)
    assert spans[0].values["z_mm"] == pytest.approx(0.4)
    assert spans[0].severity == "warning"
    assert all(finding.source == "internal" for finding in findings)


def test_a_short_bridge_is_no_warning() -> None:
    """Zehn Millimeter überbrückt jeder Drucker — sonst warnte der Bericht bei
    jedem Schraubenloch."""
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    short = _layers(100.0, 100.0)
    short = SliceResult(
        layers=tuple(replace(layer, bridge_width=8.0) for layer in short.layers),
        support_volume=0.0,
        first_layer_area=100.0,
    )

    codes = {finding.code for finding in advise.warnings_for(settings, profile, short)}
    assert "slice.long_bridge" not in codes


def test_a_support_gap_under_one_layer_welds_itself_on() -> None:
    profile = profiles.make_profile()
    settings = print_settings.with_path(
        print_settings.with_path(print_settings.resolve(profile), "support.style", "grid"),
        "support.z_gap",
        0.05,
    )

    codes = {finding.code for finding in advise.warnings_for(settings, profile)}
    assert "settings.support_gap_too_small" in codes


def test_a_lax_setting_change_needs_a_reason_everywhere() -> None:
    """Regel: eine Zahl ohne Begründung ist schlechter als die Vorgabe."""
    profile = profiles.make_profile("prusa-mk4s", "tpu-95a")
    settings = print_settings.resolve(profile)
    entries = advise.advise(settings, profile, _layers(80.0, 80.0, islands=True))

    assert entries
    for entry in entries:
        assert entry.reason, f"{entry.path} kommt ohne Grund"
        assert entry.value != entry.was, f"{entry.path} schlägt vor, was schon gilt"


def test_flexible_material_caps_the_speed() -> None:
    profile = profiles.make_profile("prusa-mk4s", "tpu-95a")
    settings = print_settings.resolve(profile)

    entries = advise.advise(settings, profile)

    speeds = [entry for entry in entries if entry.path.startswith("speed.")]
    assert speeds
    assert all(float(entry.value) <= advise.FLEXIBLE_MAX_SPEED for entry in speeds)  # type: ignore[arg-type]


def test_too_much_flow_asks_for_a_hotter_nozzle() -> None:
    """Die Grenze, die kein Feld zeigt: Schichthöhe mal Bahnbreite mal Tempo
    ist der Volumenstrom, und darüber wird die Bahn dünner als gerechnet —
    ohne dass an den Einstellungen etwas falsch aussähe."""
    profile = profiles.make_profile("prusa-mk4s", "pla")
    settings = print_settings.resolve(profile, "draft")
    assert advise.flow_of(settings, settings.speed.infill) > settings.filament.max_flow

    entries = advise.advise(settings, profile)

    hotter = next(entry for entry in entries if entry.path == "temperature.nozzle")
    assert int(hotter.value) > settings.temperature.nozzle  # type: ignore[call-overload]


def test_a_calm_setting_needs_no_flow_advice() -> None:
    profile = profiles.make_profile("prusa-mk4s", "petg")
    settings = print_settings.resolve(profile, "fine")

    entries = advise.advise(settings, profile)

    assert not [entry for entry in entries if entry.path == "temperature.nozzle"]


def test_a_nozzle_at_its_limit_slows_down_instead() -> None:
    """Heißer geht nicht immer — dann ist der andere Weg der einzige, und ein
    Vorschlag über die Maschinengrenze hinaus wäre keiner."""
    profile = profiles.make_profile("anycubic-kobra-2", "pla")
    settings = print_settings.with_path(
        print_settings.resolve(profile, "draft"),
        "temperature.nozzle",
        profile.printer.nozzle_temperature_max,
    )

    entries = advise.advise(settings, profile)

    slower = next(entry for entry in entries if entry.path == "speed.infill")
    assert float(slower.value) < settings.speed.infill  # type: ignore[arg-type]
    assert not [
        entry
        for entry in entries
        if entry.path == "temperature.nozzle"
        and int(entry.value) > profile.printer.nozzle_temperature_max  # type: ignore[call-overload]
    ]


def test_the_flow_rule_sees_what_the_others_changed() -> None:
    """Bei weichem Filament senkt die Materialregel das Tempo. Rechnete der
    Volumenstrom gegen das alte, empfähle er eine heißere Düse für ein Tempo,
    das nebenan schon gesenkt wurde."""
    profile = profiles.make_profile("prusa-mk4s", "tpu-95a")
    settings = print_settings.resolve(profile, "draft")

    entries = advise.advise(settings, profile)
    after = advise.apply(settings, entries)

    assert after.speed.infill <= advise.FLEXIBLE_MAX_SPEED
    assert advise.flow_of(after, after.speed.infill) < advise.flow_of(
        settings, settings.speed.infill
    )


def test_no_setting_gets_two_suggestions() -> None:
    """Zwei Zeilen für dieselbe Einstellung wären keine zwei Vorschläge,
    sondern eine Liste, die sich selbst widerspricht."""
    profile = profiles.make_profile("prusa-mk4s", "tpu-95a")
    settings = print_settings.resolve(profile, "draft")

    paths = [entry.path for entry in advise.advise(settings, profile, fit_kinds=("clearance",))]

    assert len(paths) == len(set(paths))


def test_a_flush_fit_asks_for_ironing() -> None:
    """Eine bündige Passung legt zwei Flächen aufeinander — die obere gleitet.

    Gebügelt sitzt sie auf einer geschlossenen Fläche statt auf den Kanten der
    Bahnen. Bisher war das ein Schalter im Dialog, den man kennen musste.
    """
    profile = profiles.make_profile()
    settings = print_settings.with_path(print_settings.resolve(profile), "shell.ironing", False)

    paths = [entry.path for entry in advise.advise(settings, profile, fit_kinds=("flush",))]

    assert "shell.ironing" in paths


def test_a_sliding_fit_does_not_ask_for_ironing() -> None:
    """Bei einem Schiebesitz oder einem Gewinde wäre Bügeln verlorene Zeit auf
    einer Fläche, die nichts berührt — die Art zählt, nicht nur das Ob.
    """
    profile = profiles.make_profile()
    settings = print_settings.with_path(print_settings.resolve(profile), "shell.ironing", False)

    for kind in ("clearance", "press", "thread"):
        paths = [entry.path for entry in advise.advise(settings, profile, fit_kinds=(kind,))]
        assert "shell.ironing" not in paths, kind
        assert "shell.precise_outer_wall" in paths, f"die anderen Regeln gelten weiter ({kind})"


def test_a_heated_chamber_gets_used_when_it_is_there() -> None:
    profile = profiles.make_profile("bambu-x1c", "abs")
    settings = print_settings.with_path(print_settings.resolve(profile), "temperature.chamber", 0)

    entries = advise.advise(settings, profile)

    chamber = next(entry for entry in entries if entry.path == "temperature.chamber")
    assert int(chamber.value) > 0  # type: ignore[call-overload]


def test_the_flow_limit_reaches_the_slicer() -> None:
    """Die Zahl gehört ins Filamentprofil — dort setzt der Slicer sie durch,
    auch für die Wege, die Solidon nicht einzeln einstellt."""
    settings = print_settings.resolve(profiles.make_profile("prusa-mk4s", "tpu-95a"))

    for flavour in ("prusa", "orca"):
        written = handover.as_mapping(settings, flavour)  # type: ignore[arg-type]
        assert written["filament_max_volumetric_speed"] == "3.5"


def test_fits_slow_the_outer_wall_down() -> None:
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)

    entries = advise.advise(settings, profile, fit_kinds=("clearance",))

    assert "speed.outer_wall" in _paths(entries)
    assert "shell.outer_wall_first" in _paths(entries)


def test_advice_without_a_slice_still_works() -> None:
    """Vor dem ersten Schnitt soll der Bericht nicht leer sein."""
    profile = profiles.make_profile("prusa-mk4s", "tpu-95a")
    entries = advise.advise(print_settings.resolve(profile), profile)
    assert entries


def test_applying_advice_changes_exactly_what_it_named() -> None:
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    entries = advise.advise(settings, profile, _layers(500.0, 500.0, islands=True))

    changed = advise.apply(settings, entries)

    for entry in entries:
        assert print_settings.read_path(changed, entry.path) == entry.value
    assert changed.layers.layer_height == settings.layers.layer_height


# --- Übergabe an den Slicer (§29) ---------------------------------------------------


@pytest.mark.parametrize("flavour", ["prusa", "orca", "cura"])
def test_every_setting_in_a_table_actually_exists(flavour: str) -> None:
    """Ein Tippfehler im Punktpfad wäre sonst erst beim Slicen zu sehen."""
    settings = print_settings.resolve(profiles.make_profile())
    for entry in slicer_keys.TABLES[flavour]:  # type: ignore[index]
        print_settings.read_path(settings, entry.path)
        assert entry.key, f"{entry.path} hat keinen Namen beim Slicer"


@pytest.mark.parametrize("flavour", ["prusa", "orca", "cura"])
def test_the_core_settings_reach_every_slicer(flavour: str) -> None:
    """Was die Oberfläche anbietet, muss überall ankommen — sonst stellt der
    Nutzer etwas ein, das für seinen Slicer folgenlos bleibt."""
    covered = {entry.path for entry in slicer_keys.TABLES[flavour]}  # type: ignore[index]
    for path in (
        "layers.layer_height",
        "shell.wall_count",
        "infill.density",
        "temperature.nozzle",
        "temperature.bed",
        "cooling.fan_speed",
        "speed.outer_wall",
        "support.style",
        "retraction.length",
    ):
        assert path in covered, f"{flavour} bekommt {path} nicht"


def test_shares_are_written_as_percentages() -> None:
    """Solidon rechnet in 0…1, die Slicer in 0…100 — die Stelle, an der ein
    Fehler fünfzehn Prozent Füllung zu fünfzehn Hundertsteln macht."""
    settings = print_settings.resolve(profiles.make_profile())
    written = handover.as_mapping(settings, "prusa")

    assert written["fill_density"] == "15%"
    assert written["max_fan_speed"] == "100"


def test_the_colour_reaches_the_slicer() -> None:
    profile = profiles.make_profile("prusa-mk4s", "petg")
    settings = print_settings.resolve(profile)

    for flavour in ("prusa", "orca"):
        written = handover.as_mapping(settings, flavour)  # type: ignore[arg-type]
        assert written["filament_colour"] == settings.filament.colour


def test_support_off_is_written_as_off_everywhere() -> None:
    settings = print_settings.resolve(profiles.make_profile())
    assert settings.support.style == "none"

    assert handover.as_mapping(settings, "prusa")["support_material"] == "0"
    assert handover.as_mapping(settings, "orca")["enable_support"] == "0"
    assert handover.as_mapping(settings, "cura")["support_enable"] == "false"


def test_support_on_actually_reaches_the_slicer() -> None:
    """Der Fehler, den erst ein echter Lauf zeigte: Orca schreibt Wahrheits-
    werte als ``0``/``1`` wie PrusaSlicer, nicht als ``true``/``false`` wie
    Cura. Ein ``true`` dort ist geräuschlos wirkungslos — der Slicer meldet
    nichts, er stützt bloß nicht, und die Stützenart daneben stimmt sogar.
    """
    settings = print_settings.with_path(
        print_settings.resolve(profiles.make_profile()), "support.style", "tree"
    )

    orca = handover.as_mapping(settings, "orca")
    assert orca["enable_support"] == "1"
    assert orca["support_type"] == "tree(auto)"
    assert handover.as_mapping(settings, "prusa")["support_material"] == "1"
    cura = handover.as_mapping(settings, "cura")
    assert cura["support_enable"] == "true"
    # Nicht nur das An/Aus: `support_structure` steht in der
    # fdmprinter-Definition — ohne den Schlüssel druckte Cura Gitterstützen,
    # wo Baumstützen eingestellt waren, und `verify()` sah nichts.
    assert cura["support_structure"] == "tree"


#: Was die Orca-Familie an diesen Stellen annimmt, abgelesen am ausgelieferten
#: Profilbestand von OrcaSlicer und seinen Ablegern. Ein Name daneben fällt
#: still auf die Vorgabe zurück — geprüft wird deshalb hier und nicht im Druck.
ORCA_VALUES = {
    "sparse_infill_pattern": {
        "grid",
        "gyroid",
        "cubic",
        "rectilinear",
        "alignedrectilinear",
        "triangles",
        "3dhoneycomb",
        "zig-zag",
        "crosshatch",
    },
    "seam_position": {"aligned", "nearest", "back", "aligned_back", "random"},
    "support_type": {"normal(auto)", "tree(auto)", "normal(manual)", "tree(manual)"},
    "brim_type": {"no_brim", "outer_only", "auto_brim", "inner_only", "outer_and_inner"},
    "wall_sequence": {"inner wall/outer wall", "outer wall/inner wall", "inner-outer-inner wall"},
}


@pytest.mark.parametrize("key", sorted(ORCA_VALUES))
def test_orca_gets_names_it_knows(key: str) -> None:
    """Über jeden Wert, den ein Feld annehmen kann — ein Muster, das der Slicer
    nicht kennt, druckt trotzdem, nur eben anders als eingestellt."""
    settings = print_settings.resolve(profiles.make_profile())
    path = next(entry[0] for entry in slicer_keys.ORCA if entry[1] == key)
    for choice in _possible(path):
        written = handover.as_mapping(print_settings.with_path(settings, path, choice), "orca")[key]
        assert written in ORCA_VALUES[key], f"{path}={choice} wird zu {written!r}"


def _possible(path: str) -> tuple[object, ...]:
    """Alle Werte, die eine Einstellung annehmen kann — aus ihrem Typ, nicht
    aus einer zweiten Liste, die veralten könnte."""
    group, _dot, name = path.partition(".")
    hints = get_type_hints(type(getattr(print_settings.resolve(profiles.make_profile()), group)))
    arguments = get_args(hints[name])
    return arguments or (True, False)


@pytest.mark.parametrize("flavour", ["prusa", "orca", "cura"])
@pytest.mark.parametrize("kind", ["skirt", "brim", "raft", "none"])
def test_only_the_chosen_adhesion_gets_measurements(flavour: str, kind: str) -> None:
    """Skirt, Brim und Raft sind Maße *ihrer* Art, keine unabhängigen
    Schalter — aber die Slicer lesen sie als solche.

    Alle drei zu schreiben hieße, alle drei zu bekommen: ein Raft unter einem
    Teil, für das „Skirt" eingestellt war. Das kostet Material, Zeit und die
    Unterseite, und es fällt erst auf der Platte auf.
    """
    settings = print_settings.with_path(
        print_settings.resolve(profiles.make_profile()), "adhesion.kind", kind
    )
    written = handover.as_mapping(settings, flavour)  # type: ignore[arg-type]

    for wanted, keys in slicer_keys.ADHESION_KEYS[flavour].items():  # type: ignore[index]
        for key in keys:
            if key not in written:
                continue
            value = float(written[key])
            if wanted == kind:
                assert value > 0.0, f"{kind}: {key} muss ein Maß haben"
            else:
                assert value == 0.0, f"{kind}: {key} gehört zu {wanted} und muss null sein"


# --- Gegenprobe: kam an, was geschrieben wurde? (§28.2) ----------------------------

ECHTER_GCODE = """
; generated by ElegooSlicer 1.5.2.2
G1 X10 Y10 E0.5
; layer_height = 0.2
; wall_loops = 3
; sparse_infill_density = 15%
; enable_support = 0
; nozzle_temperature = 240
"""


def test_the_check_stays_quiet_when_everything_arrived() -> None:
    assert handover.verify(ECHTER_GCODE, {"layer_height": "0.2", "wall_loops": "3"}) == []


def test_the_check_finds_what_the_slicer_ignored() -> None:
    """Das ist die Auskunft, die vom Slicer selbst kommt statt aus einer
    Dokumentation, die für die installierte Fassung gelten mag oder nicht.

    Damit prüft sich auch ein Slicer selbst, den beim Bauen der Tabelle
    niemand vorliegen hatte — und genau daran hing, dass PrusaSlicer und
    CuraEngine hier nie liefen.
    """
    findings = handover.verify(ECHTER_GCODE, {"layer_height": "0.3", "wall_loops": "99"})

    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert findings[0].source == "gcode", "gemessen, nicht geschätzt (Regel 14)"
    assert "layer_height" in str(findings[0].values["settings"])


def test_a_key_the_file_never_mentions_says_nothing() -> None:
    """Kein Slicer schreibt alles. Was nicht dasteht, ist keine Abweichung —
    sonst meldete die Gegenprobe bei jedem Lauf zwanzig Fehler und würde nach
    dem dritten Mal weggesehen."""
    assert handover.verify(ECHTER_GCODE, {"gibtesnichtimformat": "7"}) == []


@pytest.mark.parametrize(
    ("actual", "wanted"),
    [("0.20", "0.2"), ("15%", "15"), ('["0.4"]', "0.4"), ("  3  ", "3")],
)
def test_the_check_compares_leniently(actual: str, wanted: str) -> None:
    """``0.2`` und ``0.20`` meinen dasselbe. Eine Gegenprobe, die darüber
    stolpert, meldet Unterschiede, die keine sind."""
    text = f"; irgendein_wert = {actual}\n"
    assert handover.verify(text, {"irgendein_wert": wanted}) == []


def test_recomputed_keys_are_left_alone() -> None:
    """Manches rechnet der Slicer bewusst um — eine Farbe wird zur Liste, weil
    ein Drucker mehrere Filamente führt. Das ist keine Abweichung."""
    text = '; filament_colour = ["#FF0000";"#00FF00"]\n'
    assert handover.verify(text, {"filament_colour": "#FF0000"}) == []


@pytest.mark.parametrize("flavour", ["prusa", "orca"])
def test_the_prusa_family_writes_no_word_booleans(flavour: str) -> None:
    """Beide erben von Slic3r und lesen nur Zahlen. Ein ``true`` oder
    ``false`` in einem dieser Profile ist immer ein Fehler."""
    settings = print_settings.resolve(profiles.make_profile())
    written = handover.as_mapping(settings, flavour)  # type: ignore[arg-type]

    wrong = {key: value for key, value in written.items() if value in ("true", "false")}
    assert not wrong, f"{flavour} bekommt Wortwerte: {wrong}"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("prusa-slicer-console.exe", "prusa"),
        ("PrusaSlicer", "prusa"),
        ("superslicer", "prusa"),
        ("orca-slicer.exe", "orca"),
        ("elegoo-slicer.exe", "orca"),
        ("BambuStudio.exe", "orca"),
        ("CuraEngine.exe", "cura"),
        ("notepad.exe", None),
    ],
)
def test_the_slicer_family_is_recognised_by_name(name: str, expected: str | None) -> None:
    assert slicer_keys.flavour_of(name) == expected


def test_an_unknown_program_is_refused_with_a_way_out() -> None:
    with pytest.raises(ExternalToolError) as raised:
        handover.detect(Path("notepad.exe"))
    assert raised.value.suggestions, "Regel 17: jede Ausnahme trägt einen Vorschlag"


def test_a_prusa_config_stands_on_its_own(tmp_path: Path) -> None:
    """PrusaSlicer lädt eine ``.ini`` ohne weiteres Profil — dann muss die
    Bettform darin stehen."""
    profile = profiles.make_profile("prusa-mk4s", "pla")
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(executable=Path("PrusaSlicer.exe"), flavour="prusa")

    written = handover.write_config(settings, profile, setup, tmp_path)
    text = written.process.read_text(encoding="utf-8")

    assert written.filament is None, "PrusaSlicer nimmt alles in einer Datei"
    assert "bed_shape" in text
    assert "nozzle_diameter" in text
    assert f"layer_height = {settings.layers.layer_height:g}" in text
    assert f"temperature = {settings.temperature.nozzle:d}" in text


def test_an_orca_process_keeps_what_the_base_profile_knew(tmp_path: Path) -> None:
    """Die Orca-Familie prüft Verträglichkeit gegen den Drucker. Was Solidon
    nicht anfasst, muss deshalb stehen bleiben."""
    base = tmp_path / "base.json"
    base.write_text(
        json.dumps(
            {
                "type": "process",
                "name": "0.20mm Standard",
                "compatible_printers": ["Irgendein Drucker 0.4 nozzle"],
                "wall_loops": "2",
            }
        ),
        encoding="utf-8",
    )
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(
        executable=Path("orca-slicer.exe"), flavour="orca", base_process=str(base)
    )

    written = handover.write_config(settings, profile, setup, tmp_path)
    document = json.loads(written.process.read_text(encoding="utf-8"))

    assert document["compatible_printers"] == ["Irgendein Drucker 0.4 nozzle"]
    assert document["wall_loops"] == str(settings.shell.wall_count)
    # Was ins Filamentprofil gehört, hat im Prozessprofil nichts verloren —
    # dort liest der Slicer es nicht.
    assert "nozzle_temperature" not in document
    assert "hot_plate_temp" not in document


def test_the_orca_filament_profile_carries_what_hangs_on_the_filament(tmp_path: Path) -> None:
    """Temperatur, Kühlung und Rückzug gehören ins Filamentprofil.

    Standen sie im Prozessprofil, übernahm der Slicer sie nicht — geräuschlos,
    und gedruckt wurde mit dem, was zuletzt bei ihm eingestellt war.
    """
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")

    written = handover.write_config(settings, profile, setup, tmp_path)
    assert written.filament is not None
    document = json.loads(written.filament.read_text(encoding="utf-8"))

    assert document["type"] == "filament"
    assert document["filament_type"] == [slicer_keys.filament_type(profile.material.id)]
    # Werte stehen dort als Liste, ein Eintrag je Platz. Ein blanker String
    # wird nicht angenommen.
    assert document["nozzle_temperature"] == [str(settings.temperature.nozzle)]
    assert document["hot_plate_temp"] == [str(settings.temperature.bed)]
    assert document["filament_retraction_length"] == [f"{settings.retraction.length:g}"]
    meta = {"type", "name", "from", "instantiation"}
    assert all(isinstance(value, list) for key, value in document.items() if key not in meta)


def test_the_filament_profile_keeps_what_the_maker_knows(tmp_path: Path) -> None:
    """Solidon legt seine Werte auf das Profil des Herstellers, statt eines zu
    erfinden — und löst dessen Erbkette vorher auf.

    Der Unterschied ist keiner der Feinheit: ein Filamentprofil bei Elegoo
    setzt selbst drei Werte und erbt zweiundfünfzig. Ohne Auflösung stünde in
    der Übergabe ein Bruchstück, und der Slicer ergänzte den Rest aus dem, was
    zufällig eingestellt war.
    """
    root = tmp_path / "filament"
    root.mkdir()
    (root / "grund.json").write_text(
        json.dumps(
            {
                "type": "filament",
                "name": "Hersteller PETG @base",
                "filament_density": ["1.27"],
                "pressure_advance": ["0.04"],
                "nozzle_temperature": ["999"],
            }
        ),
        encoding="utf-8",
    )
    besonders = root / "besonders.json"
    besonders.write_text(
        json.dumps(
            {
                "type": "filament",
                "name": "Hersteller PETG Transluzent",
                "inherits": "Hersteller PETG @base",
                "instantiation": "true",
                "temperature_vitrification": ["70"],
            }
        ),
        encoding="utf-8",
    )
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(
        executable=Path("orca-slicer.exe"), flavour="orca", base_filament=str(besonders)
    )

    written = handover.write_config(settings, profile, setup, tmp_path)
    assert written.filament is not None
    document = json.loads(written.filament.read_text(encoding="utf-8"))

    assert document["pressure_advance"] == ["0.04"], "geerbt, und Solidon kennt es gar nicht"
    assert document["temperature_vitrification"] == ["70"], "eigener Wert des Profils"
    # Wo beide etwas sagen, gewinnt Solidon: die Einstellung ist die
    # Entscheidung des Nutzers, das Profil nur die Unterlage.
    assert document["nozzle_temperature"] == [str(settings.temperature.nozzle)]
    # Und der Name sagt, welche Spule gemeint ist. „Solidon Standard — PETG"
    # stand einmal über Werten von Elegoo PETG PRO — richtig gerechnet, falsch
    # beschriftet: wer die Druckdatei später liest, legt die falsche Rolle ein.
    assert document["name"] == "Solidon besonders", "der Name nennt das gewählte Profil"


def test_the_orca_call_loads_the_filament_profile(tmp_path: Path) -> None:
    """Ein eigener Schalter, nicht ``--load-settings``: dorthin gegeben würde
    das Filamentprofil nach seinem ``type`` aussortiert statt geladen."""
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")

    config = handover.write_config(settings, profile, setup, tmp_path)
    command = handover._command(setup, [tmp_path / "teil.stl"], config, tmp_path)

    assert "--load-filaments" in command
    assert command[command.index("--load-filaments") + 1] == str(config.filament)
    assert str(config.filament) not in command[command.index("--load-settings") + 1]


def _profile_keys(root: Path, kind: str) -> set[str]:
    """Alle Schlüssel, die der Bestand eines Slicers unter dieser Art führt."""
    found: set[str] = set()
    for path in (root / kind).rglob("*.json"):
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(loaded, dict):
            found |= set(loaded)
    return found


def _installed_orca_profiles() -> Path | None:
    """Der Profilbestand eines installierten Slicers der Orca-Familie."""
    for base in (Path("C:/Program Files"), Path("/usr/share"), Path("/opt")):
        if not base.is_dir():
            continue
        for folder in base.iterdir():
            root = folder / "resources" / "profiles"
            if not root.is_dir():
                continue
            for vendor in root.iterdir():
                if (vendor / "filament").is_dir() and (vendor / "process").is_dir():
                    return vendor
    return None


def test_every_orca_setting_sits_in_the_profile_it_claims() -> None:
    """Die Probe aufs Exempel: stimmt die Zuordnung gegen einen echten Bestand?

    Ein Wert im falschen Profil wird von der Orca-Familie stillschweigend
    übergangen. Genau das war lange der Fall — vierzehn Filamentwerte und der
    Rückzug standen im Prozessprofil und kamen nie an. Auffallen konnte es
    nicht, weil kein Test die Aufteilung kannte.
    """
    root = _installed_orca_profiles()
    if root is None:
        pytest.skip("kein Slicer der Orca-Familie installiert")

    known = {kind: _profile_keys(root, kind) for kind in ("process", "filament", "machine")}
    misplaced: list[str] = []
    for entry in slicer_keys.TABLES["orca"]:
        found = [kind for kind, keys in known.items() if entry.key in keys]
        if found and entry.section not in found:
            misplaced.append(f"{entry.key}: laut Tabelle {entry.section}, laut Slicer {found}")
    assert not misplaced, "Werte im falschen Profil:\n  " + "\n  ".join(misplaced)


def test_a_missing_model_says_so_before_starting_anything(tmp_path: Path) -> None:
    profile = profiles.make_profile()
    setup = handover.SlicerSetup(executable=Path("PrusaSlicer.exe"), flavour="prusa")

    with pytest.raises(ExternalToolError) as raised:
        handover.slice_model(
            tmp_path / "gibtesnicht.stl", print_settings.resolve(profile), profile, setup
        )
    assert raised.value.suggestions


def test_a_slicer_that_moved_away_points_at_the_settings(tmp_path: Path) -> None:
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    profile = profiles.make_profile()
    setup = handover.SlicerSetup(executable=tmp_path / "weg.exe", flavour="prusa")

    with pytest.raises(ExternalToolError) as raised:
        handover.slice_model(model, print_settings.resolve(profile), profile, setup)
    assert any(action.id == "open_settings" for action in raised.value.suggestions)


def test_the_newest_gcode_in_the_folder_wins(tmp_path: Path) -> None:
    """Orca hängt Plattennummern an; ein zweiter Lauf darf nicht die Zahlen des
    ersten melden."""
    import os
    import time

    old = tmp_path / "plate_1.gcode"
    old.write_text("; alt\n", encoding="utf-8")
    time.sleep(0.01)
    new = tmp_path / "plate_2.gcode"
    new.write_text("; neu\n", encoding="utf-8")
    os.utime(new, (time.time() + 5, time.time() + 5))

    assert handover._find_gcode(tmp_path) == new


def test_an_empty_folder_has_no_gcode(tmp_path: Path) -> None:
    assert handover._find_gcode(tmp_path) is None


def test_a_filament_profile_that_disagrees_is_reported(tmp_path: Path) -> None:
    """Beide Seiten haben recht: Solidons Tabelle sagt, was PETG im
    Allgemeinen verträgt, das Herstellerprofil, was diese Spule verträgt.

    Beim transluzenten Elegoo-PETG liegen dazwischen fünfzehn Grad an der Düse
    und zehn am Bett. Gemeldet wird es, übernommen nicht — die Einstellung ist
    die Entscheidung des Nutzers.
    """
    besonders = tmp_path / "besonders.json"
    besonders.write_text(
        json.dumps(
            {
                "type": "filament",
                "name": "Hersteller PETG Transluzent",
                "instantiation": "true",
                "nozzle_temperature": ["255"],
                "hot_plate_temp": ["70"],
            }
        ),
        encoding="utf-8",
    )
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    settings = print_settings.with_path(settings, "temperature.nozzle", 240)
    settings = print_settings.with_path(settings, "temperature.bed", 80)
    setup = handover.SlicerSetup(
        executable=Path("orca-slicer.exe"), flavour="orca", base_filament=str(besonders)
    )

    findings = handover.profile_differences(settings, setup)

    assert len(findings) == 1
    assert findings[0].code == "slicer.filament_differs"
    assert findings[0].source == "internal", "Regel 14: Herkunft ausweisen"
    named = findings[0].values["settings"]
    assert "nozzle_temperature: 240 statt 255" in named
    assert "hot_plate_temp: 80 statt 70" in named


def test_a_filament_profile_that_agrees_says_nothing(tmp_path: Path) -> None:
    """Ein Hinweis, der bei jedem Lauf erscheint, wird nach dem dritten Mal
    überlesen — also erscheint er nur, wenn wirklich etwas auseinandergeht."""
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    passend = tmp_path / "passend.json"
    passend.write_text(
        json.dumps(
            {
                "type": "filament",
                "name": "Hersteller PETG",
                "instantiation": "true",
                "nozzle_temperature": [str(settings.temperature.nozzle)],
            }
        ),
        encoding="utf-8",
    )
    setup = handover.SlicerSetup(
        executable=Path("orca-slicer.exe"), flavour="orca", base_filament=str(passend)
    )

    assert handover.profile_differences(settings, setup) == []
    # Ohne gewähltes Profil gibt es nichts zu vergleichen — und keine Meldung.
    ohne = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")
    assert handover.profile_differences(settings, ohne) == []


# --- Stellschrauben aus Stufe 3 -----------------------------------------------------


def test_a_narrow_wall_asks_for_the_variable_generator() -> None:
    """Ein Steg, der auf keine ganze Zahl von Bahnen aufgeht, ist der Fall, für
    den es den variablen Generator gibt.

    Der Anlass steht im Gewürzset: Federarme von 1,1 mm und eine Rastzunge von
    1,4 mm. Mit fester Linienbreite legt der Slicer zwei Bahnen à 0,42 und
    schließt den Rest mit Lückenfüllung — die trägt nicht, und die Feder bricht
    beim ersten Aufdrücken.
    """
    settings = print_settings.resolve(profiles.make_profile())
    settings = print_settings.with_path(settings, "shell.wall_generator", "classic")
    schmal = 2.5 * settings.layers.line_width
    result = _layers(500.0, 500.0, 500.0, min_width=schmal)

    entries = advise.advise(settings, profiles.make_profile(), result)

    chosen = next(entry for entry in entries if entry.path == "shell.wall_generator")
    assert chosen.value == "arachne"
    assert chosen.severity == "warning"


def test_a_wall_that_fits_whole_paths_keeps_the_generator() -> None:
    """Ein Vorschlag, der bei jedem Teil erscheint, ist keiner."""
    settings = print_settings.resolve(profiles.make_profile())
    settings = print_settings.with_path(settings, "shell.wall_generator", "classic")
    breit = 6.0 * settings.layers.line_width
    result = _layers(500.0, 500.0, 500.0, min_width=breit)

    entries = advise.advise(settings, profiles.make_profile(), result)

    assert "shell.wall_generator" not in _paths(entries)


def test_fits_ask_for_the_precise_wall_and_a_calmer_acceleration() -> None:
    """Beides zielt auf dasselbe: das Maß, auf das die Passung gerechnet ist."""
    settings = print_settings.resolve(profiles.make_profile())

    entries = advise.advise(settings, profiles.make_profile(), fit_kinds=("clearance",))

    precise = next(entry for entry in entries if entry.path == "shell.precise_outer_wall")
    assert precise.value is True
    calmer = next(entry for entry in entries if entry.path == "speed.outer_wall_acceleration")
    assert calmer.value == advise.CAREFUL_ACCELERATION
    assert calmer.value < settings.speed.outer_wall_acceleration


def test_without_fits_nothing_is_slowed_down() -> None:
    settings = print_settings.resolve(profiles.make_profile())

    entries = advise.advise(settings, profiles.make_profile())

    assert "shell.precise_outer_wall" not in _paths(entries)
    assert "speed.outer_wall_acceleration" not in _paths(entries)


def test_an_overhang_slows_the_bridge_down_to_the_outer_wall() -> None:
    """Über einer Lücke trägt nichts von unten."""
    settings = print_settings.resolve(profiles.make_profile())
    settings = print_settings.with_path(settings, "speed.bridge", 120.0)
    result = _layers(500.0, 500.0, 500.0, overhang=200.0)

    entries = advise.advise(settings, profiles.make_profile(), result)

    chosen = next(entry for entry in entries if entry.path == "speed.bridge")
    assert chosen.value == settings.speed.outer_wall


def test_the_new_settings_reach_the_slicers_that_know_them() -> None:
    """Was ein Slicer nicht kennt, bekommt keinen Eintrag — eine Zuordnung auf
    das Nächstbeste wäre eine Einstellung, die woanders landet.

    CuraEngine hat keinen umschaltbaren Wandgenerator, PrusaSlicer keine
    gesonderte genaue Außenwand. Beide rechnen ohnehin mit variabler
    Bahnbreite.
    """
    settings = print_settings.resolve(profiles.make_profile())

    orca = handover.as_mapping(settings, "orca")
    assert orca["wall_generator"] == settings.shell.wall_generator
    assert orca["bridge_speed"] == f"{settings.speed.bridge:g}"
    assert orca["outer_wall_acceleration"] == f"{settings.speed.outer_wall_acceleration:g}"
    assert orca["ironing_type"] == "no ironing"

    prusa = handover.as_mapping(settings, "prusa")
    assert prusa["perimeter_generator"] == settings.shell.wall_generator
    assert "precise_outer_wall" not in prusa

    cura = handover.as_mapping(settings, "cura")
    assert cura["bridge_wall_speed"] == f"{settings.speed.bridge:g}"
    assert "wall_generator" not in cura


def test_ironing_is_off_until_something_asks_for_it() -> None:
    """Bügeln kostet Zeit und nützt nur auf Flächen, die man sieht oder auf
    denen etwas gleitet."""
    settings = print_settings.resolve(profiles.make_profile())

    assert settings.shell.ironing is False
    assert handover.as_mapping(settings, "orca")["ironing_type"] == "no ironing"

    ironed = print_settings.with_path(settings, "shell.ironing", True)
    assert handover.as_mapping(ironed, "orca")["ironing_type"] == "top"


def test_a_part_on_little_ground_asks_for_a_brim_on_its_own() -> None:
    """Die Plattenhaftung ist die eine Einstellung, die je Teil zählt.

    Der Anlass ist das Gewürzset: zwölf Behälter auf Ø 40 und Streuscheiben,
    die auf drei 1,1-mm-Federarmen stehen. Ein Brim gehört unter die Scheiben
    und unter keinen Behälter — plattenweit gäbe es nur beides oder nichts.
    """
    settings = print_settings.resolve(profiles.make_profile())
    weit = BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(40.0, 40.0, 20.0))

    viel = advise.for_part(settings, weit, footprint=1200.0)
    wenig = advise.for_part(settings, weit, footprint=60.0)

    assert viel == []
    assert [entry.path for entry in wenig] == ["adhesion.kind"]
    assert wenig[0].value == "brim"


def test_a_tall_thin_part_asks_for_one_too() -> None:
    settings = print_settings.resolve(profiles.make_profile())
    schlank = BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(10.0, 10.0, 90.0))

    entries = advise.for_part(settings, schlank, footprint=900.0)

    assert [entry.path for entry in entries] == ["adhesion.kind"]


def test_a_part_keeps_quiet_when_the_plate_already_has_a_brim() -> None:
    """Ein Vorschlag, der das vorschlägt, was schon eingestellt ist, ist keiner."""
    settings = print_settings.resolve(profiles.make_profile())
    settings = print_settings.with_path(settings, "adhesion.kind", "brim")
    eng = BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(40.0, 40.0, 20.0))

    assert advise.for_part(settings, eng, footprint=60.0) == []


def test_an_object_override_carries_the_measures_of_its_group() -> None:
    """Wer die Haftungsart umstellt, braucht auch deren Maß — und die Maße der
    Arten, die nicht gewählt sind, müssen auf null.

    Sonst liefe unter dem einen Teil zusätzlich ein Raft mit, und das fällt
    erst auf der Platte auf.
    """
    settings = print_settings.resolve(profiles.make_profile())
    entries = advise.for_part(
        settings,
        BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(40.0, 40.0, 20.0)),
        footprint=60.0,
    )

    keys = handover.object_keys(settings, entries, "orca")

    assert keys["brim_type"] == "outer_only"
    assert keys["brim_width"] == f"{settings.adhesion.brim_width:g}"
    assert keys["raft_layers"] == "0"
    assert keys["skirt_loops"] == "0"
    # Nur die betroffene Gruppe — die Wandzahl des Teils ist die der Platte.
    assert "wall_loops" not in keys


def test_without_advice_a_part_gets_no_override() -> None:
    settings = print_settings.resolve(profiles.make_profile())

    assert handover.object_keys(settings, [], "orca") == {}


def test_a_profile_that_says_nothing_is_no_disagreement(tmp_path: Path) -> None:
    """``nil`` heißt in einem Filamentprofil „dazu sage ich nichts" — der Wert
    bleibt beim Drucker.

    Das als Abweichung zu melden hieße, fünf Zeilen Rauschen neben die drei zu
    stellen, auf die es ankommt: beim Elegoo-PETG waren es der ganze Rückzug
    und das Wischen, alle vier auf ``nil``.
    """
    schweigend = tmp_path / "schweigend.json"
    schweigend.write_text(
        json.dumps(
            {
                "type": "filament",
                "name": "Hersteller PETG",
                "instantiation": "true",
                "filament_retraction_length": ["nil"],
                "filament_wipe": ["nil"],
                "nozzle_temperature": ["250"],
            }
        ),
        encoding="utf-8",
    )
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    settings = print_settings.with_path(settings, "temperature.nozzle", 240)
    setup = handover.SlicerSetup(
        executable=Path("orca-slicer.exe"), flavour="orca", base_filament=str(schweigend)
    )

    findings = handover.profile_differences(settings, setup)

    assert len(findings) == 1
    named = findings[0].values["settings"]
    assert "nozzle_temperature" in named, "der echte Unterschied bleibt"
    assert "retraction" not in named, "nil ist keine Gegenaussage"
    assert "wipe" not in named


def test_a_profile_name_finds_its_file(tmp_path, monkeypatch) -> None:
    """Der Name gehört in die Projektdatei, die Datei braucht der Slicer.

    Beides muss gehen, und dazwischen fehlte die Auflösung: ``base_process``
    trug einen Namen, ``Path(name).is_file()`` sagte nein, und das
    geschriebene Prozessprofil hatte zweiundvierzig Schlüssel statt
    zweiundsechzig — ohne ``inherits``, ohne ``compatible_printers``. Genau an
    denen prüft die Orca-Familie die Verträglichkeit, und der Lauf brach mit
    „can not find setting file" ab, bevor das Modell an die Reihe kam.
    """
    from pathlib import Path

    from app.core.export import slicer_profiles

    echte = tmp_path / "0.20mm Standard.json"
    echte.write_text(
        json.dumps(
            {
                "type": "process",
                "name": "0.20mm Standard",
                "inherits": "fdm_process_common",
                "compatible_printers": ["Elegoo Centauri Carbon 2 0.4 nozzle"],
                "layer_height": "0.2",
            }
        ),
        encoding="utf-8",
    )

    class Eintrag:
        name = "0.20mm Standard"
        kind = "process"
        path = echte

    gefragt: list[object] = []

    def suche(_executable, _flavour, kinds=None):
        gefragt.append(kinds)
        return [Eintrag()]

    monkeypatch.setattr(slicer_profiles, "find_profiles", suche)
    setup = handover.SlicerSetup(
        executable=Path("elegoo-slicer.exe"), flavour="orca", base_process="0.20mm Standard"
    )

    gefunden = handover.profile_file("0.20mm Standard", setup, "process")
    assert gefunden == echte, "der Name führt zur Datei"
    assert gefragt == [("process",)], "gefragt wird nach der gesuchten Art, nicht nach allen"

    # Ein Pfad geht weiterhin unverändert durch
    assert handover.profile_file(str(echte), setup, "process") == echte

    # Und was das Prozessprofil trägt, kommt aus dem Systemprofil
    settings = print_settings.resolve(
        profiles.make_profile("centauri-carbon-2", "petg"), "standard"
    )
    written = handover.write_config(
        settings, profiles.make_profile("centauri-carbon-2", "petg"), setup, tmp_path
    )
    daten = json.loads(written.process.read_text(encoding="utf-8"))
    assert daten["inherits"] == "fdm_process_common", "die Erbschaft bleibt erhalten"
    assert daten["compatible_printers"] == ["Elegoo Centauri Carbon 2 0.4 nozzle"]
    assert daten["name"].startswith("Solidon"), "aber der Name ist Solidons eigener"


def test_a_filament_profile_is_found_by_name_too(tmp_path, monkeypatch) -> None:
    """Derselbe Weg für das Filament — und der war es nicht.

    ``find_profiles`` lässt Filamentprofile weg, wenn niemand nach ihnen
    fragt: sie vervielfachen den Bestand, und die Vorgabe kennt nur Maschinen
    und Prozesse. ``profile_file`` fragte aber nicht nach der Art, die es
    suchte — also lief die Schleife über Maschinen und Prozesse und fand nie
    ein Filament, egal wie es hieß.

    Das kostete mehr als einen Namen: ohne das Herstellerprofil fehlten die
    Temperaturen aller Druckplatten außer der einen, die Solidon selbst setzt.
    Der Slicer wählte „Cool Plate", fand dort seine eigenen 35 Grad, und ein
    PETG-Druck ging mit kaltem Bett hinaus.
    """
    from pathlib import Path

    from app.core.export import slicer_profiles

    datei = tmp_path / "Elegoo PETG PRO.json"
    datei.write_text(json.dumps({"name": "Elegoo PETG PRO"}), encoding="utf-8")

    class Eintrag:
        name = "Elegoo PETG PRO"
        kind = "filament"
        path = datei

    def suche(_executable, _flavour, kinds=None):
        # Genau wie im Bestand: ohne Nachfrage gibt es keine Filamentprofile.
        return [Eintrag()] if kinds and "filament" in kinds else []

    monkeypatch.setattr(slicer_profiles, "find_profiles", suche)
    setup = handover.SlicerSetup(
        executable=Path("elegoo-slicer.exe"), flavour="orca", base_filament="Elegoo PETG PRO"
    )

    assert handover.profile_file("Elegoo PETG PRO", setup, "filament") == datei


def test_a_project_file_carries_its_values_written_out(tmp_path, monkeypatch) -> None:
    """Eine Projektdatei kennt kein ``inherits`` — sie muss alles enthalten.

    Ein Profil darf sich auf seine Erbkette verlassen: der Slicer lädt es und
    löst selbst auf. Ein Projekt nicht. Was darin fehlt, füllt der Slicer aus
    dem Profil, das gerade eingestellt ist — und das ist nicht Solidons.

    Genau daran ging ein Druck vorbei: die 3MF trug 122 der 546 Schlüssel, in
    ihr standen drei Wände, gedruckt wurden zwei, und der Unterschied waren
    127 Gramm. Geprüft wird deshalb, dass die Erbkette **aufgelöst** wird und
    Solidons eigene Werte trotzdem obenauf liegen.
    """
    from pathlib import Path

    from app.core.export import slicer_profiles

    geerbt = tmp_path / "basis.json"
    geerbt.write_text(
        json.dumps({"name": "basis", "wall_loops": "2", "bridge_angle": "45"}),
        encoding="utf-8",
    )

    class Eintrag:
        name = "basis"
        kind = "process"
        path = geerbt

    monkeypatch.setattr(slicer_profiles, "find_profiles", lambda *_, **__: [Eintrag()])
    monkeypatch.setattr(
        slicer_profiles, "resolve_values", lambda _: {"wall_loops": "2", "bridge_angle": "45"}
    )

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile, "standard")
    setup = handover.SlicerSetup(
        executable=Path("elegoo-slicer.exe"), flavour="orca", base_process="basis"
    )

    werte = handover.project_settings(settings, profile, setup)

    assert werte["bridge_angle"] == "45", "was nur geerbt ist, steht trotzdem in der Datei"
    assert werte["wall_loops"] == str(settings.shell.wall_count), (
        "Solidons eigener Wert liegt über dem geerbten"
    )


def test_the_project_settings_ids_are_names_not_paths() -> None:
    """Regel 12: Der Pfad des eigenen Rechners reist nicht in einer Datei
    mit, die weitergegeben wird — und die Orca-Familie trifft mit einem Pfad
    ohnehin kein Preset. Prozess und Filament tragen den Solidon-Namen, unter
    dem `write_config` sie wirklich schreibt; unter dem Namen eines
    Systemprofils lüde der Slicer sein eigenes darunter."""
    from pathlib import Path

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile, "standard")
    root = "C:/Program Files/ElegooSlicer/resources/profiles/Elegoo"
    setup = handover.SlicerSetup(
        executable=Path("elegoo-slicer.exe"),
        flavour="orca",
        machine_profile=f"{root}/machine/ECC2/Elegoo Centauri Carbon 2 0.4 nozzle.json",
        base_process=f"{root}/process/ECC2/0.12mm Fine @Elegoo CC2 0.4 nozzle.json",
        base_filament=f"{root}/filament/ECC2/Elegoo PLA @ECC2.json",
    )

    werte = handover.project_settings(settings, profile, setup, extruders=2)

    assert werte["printer_settings_id"] == "Elegoo Centauri Carbon 2 0.4 nozzle"
    assert werte["print_settings_id"] == f"Solidon {settings.title}"
    assert werte["filament_settings_id"] == ["Solidon Elegoo PLA @ECC2"] * 2
    for key in ("printer_settings_id", "print_settings_id"):
        assert "/" not in str(werte[key]) and "\\" not in str(werte[key])


def test_a_profile_name_with_dots_is_not_truncated() -> None:
    """`.stem` auf „0.12mm Fine @…" schnitte mitten ins Maß — ein Name, der
    schon ein Name ist, bleibt unangetastet."""
    from pathlib import Path

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile, "standard")
    setup = handover.SlicerSetup(
        executable=Path("elegoo-slicer.exe"),
        flavour="orca",
        machine_profile="Elegoo Centauri Carbon 2 0.4 nozzle",
        base_process="0.12mm Fine @Elegoo CC2 0.4 nozzle",
    )

    werte = handover.project_settings(settings, profile, setup)

    assert werte["printer_settings_id"] == "Elegoo Centauri Carbon 2 0.4 nozzle"


def test_the_bed_temperature_reaches_every_plate(tmp_path) -> None:
    """Die Temperatur gehört dem Material, der Plattentyp der Maschine.

    Solidon weiß nicht, welche Platte aufliegt — also bekommt jede denselben
    Wert. Sonst steht die Betttemperatur auf genau einer Platte, der Slicer
    liest eine andere, und niemand hat über diesen Wert entschieden.
    """
    from pathlib import Path

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile, "standard")
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")

    werte = handover.project_settings(settings, profile, setup)

    erwartet = [str(settings.temperature.bed)]
    for platte in handover.PLATE_KINDS:
        assert werte[f"{platte}_plate_temp"] == erwartet, f"{platte} bekommt dieselbe Temperatur"


def test_cura_gets_its_values_on_the_extruder_too(tmp_path) -> None:
    """``CuraEngine`` liest das meiste vom Extruder-Zug, nicht global.

    Was nur global steht, wird nicht übernommen, sondern von der Vorgabe der
    Definition überschrieben. Gemessen an einem 20-mm-Würfel gegen PrusaSlicer
    mit denselben Einstellungen: 748 mm Filament statt 1410, weil Wandzahl,
    Bahnbreite und Füllung nie beim Extruder ankamen. Nur auf dem Zug ist
    ebenso falsch — dann fehlen der Zeitrechnung die Geschwindigkeiten (38,4
    Minuten statt 20,9).
    """
    from pathlib import Path

    setup = handover.SlicerSetup(executable=Path("CuraEngine.exe"), flavour="cura")
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    config = handover.write_config(print_settings.resolve(profile), profile, setup, tmp_path)

    command = handover._command(setup, [tmp_path / "cube.stl"], config, tmp_path)
    assert "-e0" in command, "ohne Extruder-Zug kommt kein Wert dort an"
    wall = [index for index, entry in enumerate(command) if entry.startswith("wall_line_count=")]
    assert len(wall) == 2, "einmal global, einmal auf dem Zug"
    assert wall[0] < command.index("-e0") < wall[1], "und in dieser Reihenfolge"


def test_curas_first_line_width_is_a_share_not_a_size() -> None:
    """``initial_layer_line_width_factor`` will Prozent von ``line_width``.

    Solidon schrieb den Millimeterwert hinein: 0,449 wurde zu 0,449 Prozent,
    und die erste Schicht bekam ein Zweihundertstel der Breite, die sie haben
    sollte. Bei PrusaSlicer ist dasselbe Feld ein Maß — deshalb fiel es nur
    gegen einen echten Lauf auf.
    """
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.resolve(profile)
    written = handover.as_mapping(settings, "cura")

    share = float(written["initial_layer_line_width_factor"])
    expected = settings.layers.first_layer_line_width / settings.layers.line_width * 100.0
    # Geschrieben wird mit sechs geltenden Ziffern, wie jede andere Zahl auch.
    assert share == pytest.approx(expected, abs=1e-3)
    assert share > 50.0, "ein Anteil, kein Millimeterwert"


def test_cura_switches_acceleration_on_before_using_it(tmp_path) -> None:
    """Ohne den Schalter rechnet ``CuraEngine`` mit ``machine_acceleration``
    weiter und übergeht, was daneben steht."""
    from pathlib import Path

    setup = handover.SlicerSetup(executable=Path("CuraEngine.exe"), flavour="cura")
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    config = handover.write_config(print_settings.resolve(profile), profile, setup, tmp_path)
    lines = config.process.read_text(encoding="utf-8").splitlines()

    assert "acceleration_enabled=true" in lines
    assert any(line.startswith("acceleration_print=") for line in lines)


def test_an_unknown_profile_name_is_no_crash(tmp_path) -> None:
    """Ein Name, den dieser Slicer nicht kennt, liefert nichts — und keinen
    Stapelabzug."""
    from pathlib import Path

    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")
    assert handover.profile_file("gibt es nicht", setup, "process") is None
    assert handover.profile_file("", setup, "machine") is None


def test_a_spread_overhang_is_no_reason_for_supports() -> None:
    """Die Summe allein sprach ein Fehlurteil.

    Ein Becher verteilt seinen Überhang über dreihundert Schichten — keine
    trägt mehr als ein paar Quadratmillimeter, und jede Wand fängt das in sich
    auf. Gemessen am echten Teil: 239,8 mm² Summe, 3,7 mm² auf der schlimmsten
    Schicht. Er bekam trotzdem dieselbe Stützenwarnung wie ein Deckel, dessen
    Lochplatte mit 845,6 mm² auf einmal über einem Hohlraum beginnt.
    """
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile, "standard")
    assert settings.support.style == "none", "die Vorgabe kommt ohne Stützen"

    # Dreihundert Schichten à 0,8 mm² — Summe 240, keine einzelne kritisch.
    verteilt = _layers(*([200.0] * 300), overhang=0.8)
    # Zwei Schichten, davon eine mit 400 mm² auf einmal.
    geballt = _layers(200.0, 200.0, overhang=400.0)

    zu_verteilt = advise.advise(settings, profile, verteilt)
    zu_geballt = advise.advise(settings, profile, geballt)

    assert not [a for a in zu_verteilt if a.path == "support.style"], (
        "was sich über dreihundert Schichten verteilt, trägt sich selbst"
    )
    assert [a for a in zu_geballt if a.path == "support.style"], (
        "was auf einer Schicht anfängt, braucht Stützen"
    )


def test_the_worst_layer_is_reported_separately() -> None:
    """Summe und Spitze sind zwei Zahlen, und nur die zweite entscheidet."""
    from app.core.slice.analysis import total_overhang, worst_overhang

    result = _layers(200.0, 200.0, 200.0, overhang=50.0)

    assert total_overhang(result) == pytest.approx(150.0)
    assert worst_overhang(result) == pytest.approx(50.0)
    assert worst_overhang(_layers()) == 0.0, "ohne Schichten kein Überhang"


# --- mehrere Filamente auf einer Platte (§20, §29) ------------------------------


def _filament_profile(directory: Path, name: str, **werte: object) -> Path:
    datei = directory / f"{name}.json"
    datei.write_text(json.dumps({"name": name, **werte}), encoding="utf-8")
    return datei


def test_every_slot_gets_its_own_filament(tmp_path: Path) -> None:
    """Ein Slot ist ein Filament, kein Objektmerkmal (§20).

    Ein Schriftzug in Weiß auf einem Gehäuse in Schwarz sind zwei Spulen mit
    zwei Temperaturen. Solange die Übergabe eine Datei kannte, bekam jeder
    Slot dasselbe Filament — die zweite Farbe fuhr mit den Werten der ersten,
    und im G-Code stand nirgends, dass das so gemeint war.
    """
    from app.core.types import MaterialSlot

    petg = _filament_profile(
        tmp_path, "Haus PETG", nozzle_temperature=["240"], filament_max_volumetric_speed=["5"]
    )
    pla = _filament_profile(
        tmp_path, "Haus PLA", nozzle_temperature=["210"], filament_max_volumetric_speed=["21"]
    )
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")
    slots = [
        MaterialSlot(index=0, name="Gehäuse", colour=(0.0, 0.0, 0.0), material=str(petg)),
        MaterialSlot(index=1, name="Schrift", colour=(1.0, 1.0, 1.0), material=str(pla)),
    ]

    config = handover.write_config(settings, profile, setup, tmp_path, slots)

    assert len(config.filaments) == 2, "je Slot ein Profil"
    erste, zweite = (json.loads(f.read_text(encoding="utf-8")) for f in config.filaments)
    assert erste["nozzle_temperature"] == ["240"], "der Hersteller des Slots gilt"
    assert zweite["nozzle_temperature"] == ["210"], "und für den zweiten ein anderer"
    assert zweite["filament_max_volumetric_speed"] == ["21"]
    assert erste["filament_colour"] == ["#000000"], "die Farbe kommt vom Slot"
    assert zweite["filament_colour"] == ["#FFFFFF"]
    assert zweite["name"] == "Solidon Schrift"

    befehl = handover._command(setup, [tmp_path / "platte.3mf"], config, tmp_path)
    stelle = befehl.index("--load-filaments")
    assert befehl[stelle + 1].count(";") == 1, "beide gehen an den Slicer, nicht nur eines"


def test_without_slots_it_stays_one_filament(tmp_path: Path) -> None:
    """Der einfarbige Druck ist der Sonderfall mit einem Eintrag, nicht ein
    anderer Weg — und dort gelten Solidons Werte, nicht die des Herstellers."""
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")

    config = handover.write_config(settings, profile, setup, tmp_path)

    assert len(config.filaments) == 1
    assert config.filament == config.filaments[0], (
        "das eine bleibt über die alte Auskunft erreichbar"
    )
    document = json.loads(config.filaments[0].read_text(encoding="utf-8"))
    assert document["nozzle_temperature"] == [str(settings.temperature.nozzle)]


# --- Verbinder, am Querschnitt gemessen (§25, §29) ----------------------------


def test_a_connector_made_mostly_of_infill_asks_for_more_walls() -> None:
    """Die Stiftplanung rechnet in Geometrie, gedruckt wird ein Ring mit Muster.

    Nachgemessen am Querschnitt: Ein Verbinder mit Ø 5,00 mm ist bei zwei
    Wänden à 0,42 mm innen 3,32 mm Füllung und außen 1,68 mm Material. Genau
    dort sitzt die Verbindung, die die beiden Hälften zusammenhalten soll —
    ein Gyroid mit fünfzehn Prozent trifft diesen Kern womöglich gar nicht.
    """
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    settings = replace(
        settings,
        shell=replace(settings.shell, wall_count=2),
        layers=replace(settings.layers, line_width=0.42),
    )

    assert advise.solid_core(5.0, settings) == pytest.approx(3.32)

    entries = [
        entry
        for entry in advise.advise(settings, profile, connectors=(5.0,))
        if entry.path == "shell.wall_count"
    ]

    assert entries, "der Verbinder besteht überwiegend aus Füllung"
    # 5,00 / (4 · 0,42) aufgerundet: die Schwelle, ab der das Material um den
    # Zapfen mindestens so breit ist wie sein Kern — nicht bis vollmassiv, das
    # wären zehn Wände auf dem ganzen Teil.
    assert entries[0].value == 3
    danach = replace(settings, shell=replace(settings.shell, wall_count=3))
    assert advise.solid_core(5.0, danach) <= 2.0 * 3 * 0.42


def test_a_connector_that_prints_solid_needs_no_advice() -> None:
    """Ein Zapfen mit ein paar Zehnteln Muster in der Mitte trägt — erst wenn
    der Füllkern breiter ist als das Material um ihn herum, ist es eine Sache.
    """
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    settings = replace(
        settings,
        shell=replace(settings.shell, wall_count=3),
        layers=replace(settings.layers, line_width=0.42),
    )

    # 3,00 minus 2 mal 3 mal 0,42 sind 0,48 mm Kern gegen 2,52 mm Material.
    assert advise.solid_core(3.0, settings) == pytest.approx(0.48)
    paths = {entry.path for entry in advise.advise(settings, profile, connectors=(3.0,))}

    assert "shell.wall_count" not in paths


def test_without_connectors_nothing_is_said() -> None:
    """Wer nicht geteilt hat, bekommt keinen Vorschlag über Verbinder."""
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)

    paths = {entry.path for entry in advise.advise(settings, profile)}

    assert "shell.wall_count" not in paths


# --- der Lauf selbst: Zeitgrenze, Abbruch, Start (§2.8, Regel 17) -----------------


def test_a_slicer_over_the_time_limit_is_an_answer_not_a_crash(tmp_path: Path) -> None:
    """Der Zwilling zu ``test_openscad``: ``subprocess.run`` warf einen rohen
    ``TimeoutExpired`` aus dem Arbeits-Thread, der nur ``AppError`` fing —
    der Dialog stand dauerhaft auf „Der Slicer rechnet …"."""
    import sys

    setup = handover.SlicerSetup(executable=Path(sys.executable), flavour="orca")
    command = [sys.executable, "-c", "import time; time.sleep(30)"]

    with pytest.raises(ExternalToolError) as caught:
        handover._run_slicer(command, tmp_path, 0.5, setup, None)

    assert caught.value.suggestions, "eine Zeitgrenze ist eine Antwort, kein Absturz"


def test_a_cancelled_slicer_run_stops_the_child_quickly(tmp_path: Path) -> None:
    """Abbrechen beendet den Kindprozess, statt ihn auslaufen zu lassen —
    daran hängt, dass Schließen nicht mehr minutenlang einfriert."""
    import sys
    import time as clock

    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    signal = CancelSignal()
    signal.cancel()
    setup = handover.SlicerSetup(executable=Path(sys.executable), flavour="orca")
    command = [sys.executable, "-c", "import time; time.sleep(30)"]
    started = clock.perf_counter()

    with pytest.raises(OperationCancelled):
        handover._run_slicer(command, tmp_path, 60.0, setup, signal)

    assert clock.perf_counter() - started < 15.0, "der Kindprozess stirbt, nicht der Nutzer wartet"


def test_a_slicer_that_cannot_start_is_an_answer(tmp_path: Path) -> None:
    """Eine gewählte Datei kann ``flavour_of`` bestehen und trotzdem kein
    Programm sein — eine DLL zum Beispiel. Der ``OSError`` beim Start flog
    roh aus dem Thread."""
    fake = tmp_path / "elegoo-slicer.exe"
    fake.write_text("kein programm", encoding="utf-8")
    setup = handover.SlicerSetup(executable=fake, flavour="orca")

    with pytest.raises(ExternalToolError) as caught:
        handover._run_slicer([str(fake)], tmp_path, 5.0, setup, None)

    assert caught.value.suggestions


def test_an_unknown_material_is_reported_not_silent() -> None:
    """Regel 21: `_material_table` fällt mit Absicht still auf die
    Modellvorgaben zurück — der Satz an den Nutzer fehlte: ein selbst
    angelegtes Material druckt sonst mit PLA-nahen Werten, ohne dass es
    irgendwo steht."""
    from dataclasses import replace as dc_replace

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    unknown = dc_replace(
        profile, material=dc_replace(profile.material, id="eigenes-filament")
    )
    settings = print_settings.resolve(unknown)

    codes = {entry.code for entry in advise.warnings_for(settings, unknown)}

    assert "settings.material_without_profile" in codes
    known_codes = {entry.code for entry in advise.warnings_for(settings, profile)}
    assert "settings.material_without_profile" not in known_codes
