"""Druckeinstellungen, Empfehlung und Slicer-Übergabe (Bauplan §29, §28).

Drei Sachen, die zusammengehören: Solidon hält die Einstellungen, die
Geometrie ändert sie, und der Slicer bekommt sie in seiner eigenen Sprache
geschrieben. Getestet wird ohne installierten Slicer — was einen Fremdprozess
braucht, steht ausdrücklich dabei.
"""

from __future__ import annotations

import json
import re
from dataclasses import fields, replace
from pathlib import Path
from typing import Any, Final, get_args, get_type_hints

import pytest

from app.core.errors import ExternalToolError, ValidationError
from app.core.export import handover, slicer_keys
from app.core.knowledge import print_settings, profiles
from app.core.slice import advise
from app.core.types import (
    BoundingBox,
    LayerInfo,
    MaterialSlot,
    Polygon,
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
            contours=(Polygon(outline=square),),
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


#: Einstellungen, die ein Slicer nicht kennt — mit dem Grund daneben.
#:
#: Der Test darunter prüft **alle** Einstellungen gegen alle drei Familien.
#: Wer eine neue anlegt und irgendwo nicht zuordnet, muss sich hier erklären;
#: eine Liste ohne Begründung wäre nur eine Liste von Ausreden.
UNREACHABLE: dict[str, dict[str, str]] = {
    "prusa": {
        "shell.precise_outer_wall": "PrusaSlicer kompensiert die Bahnbreite immer, ohne Schalter.",
        "adhesion.kind": "kennt keine Art, nur die Maße — ``ADHESION_KEYS`` nullt die anderen.",
    },
    "orca": {
        "adhesion.kind": "in ``brim_type`` enthalten, das die Tabelle schreibt.",
    },
    "cura": {
        "shell.wall_generator": "CuraEngine rechnet immer mit variabler Bahnbreite.",
        "shell.precise_outer_wall": "wie oben — es gibt keinen Schalter dafür.",
        "adhesion.kind": "in ``adhesion_type`` enthalten, das die Tabelle schreibt.",
        "retraction.wipe": "kennt kein Abstreifen beim Rückzug, nur das zwischen den Schichten.",
        "filament.density": "steht im Materialprofil des Fensters, nicht in der Rechenmaschine.",
        "filament.colour": "wie oben",
        "filament.cost_per_kg": "wie oben",
    },
}


@pytest.mark.parametrize("flavour", ["prusa", "orca", "cura"])
def test_every_setting_reaches_every_slicer(flavour: str) -> None:
    """Was der Dialog anbietet, muss überall ankommen — sonst stellt der
    Nutzer etwas ein, das für seinen Slicer folgenlos bleibt.

    Genau das war der Fall: ``support.placement`` erreichte PrusaSlicer nicht,
    obwohl es dort ``support_material_buildplate_only`` heißt, und die
    Stützdichte kam bei zwei von drei Familien nie an. Neun handverlesene
    Pfade zu prüfen hat das nicht gefunden — alle zu prüfen schon.
    """
    profile = profiles.make_profile()
    base = print_settings.resolve(profile)
    excused = UNREACHABLE[flavour]
    for path in _every_setting():
        if path in excused:
            continue
        # Ein Haftungsmaß gilt nur für seine Art — die anderen werden
        # ausdrücklich genullt (``_only_chosen_adhesion``). Also erst die Art
        # einstellen, sonst prüft der Test die Nullung statt die Zuordnung.
        settings = _with_context(base, path)
        # Gegen ``values_for`` und nicht gegen die Tabelle: was der Slicer
        # bekommt, ist die Frage — ob es aus der Zuordnung kommt oder aus der
        # Ableitungsstufe, ist seine Sache nicht.
        before = handover.values_for(settings, profile, flavour)  # type: ignore[arg-type]
        after = handover.values_for(
            print_settings.with_path(settings, path, _other_value(settings, path)),
            profile,
            flavour,  # type: ignore[arg-type]
        )
        assert before != after, f"{flavour} bekommt {path} nicht, und nichts begründet das"


def _with_context(
    settings: print_settings.PrintSettings, path: str
) -> print_settings.PrintSettings:
    """Stellt ein, was der Pfad braucht, um überhaupt wirksam zu sein."""
    needed = {
        "adhesion.skirt_loops": "skirt",
        "adhesion.skirt_distance": "skirt",
        "adhesion.brim_width": "brim",
        "adhesion.raft_layers": "raft",
    }.get(path)
    if needed is not None:
        settings = print_settings.with_path(settings, "adhesion.kind", needed)
    if path.startswith("support.") and path != "support.style":
        settings = print_settings.with_path(settings, "support.style", "grid")
    return settings


def _every_setting() -> list[str]:
    """Jede Einstellung als Punktpfad, aus dem Modell gelesen."""
    settings = print_settings.resolve(profiles.make_profile())
    paths: list[str] = []
    for group in (
        "layers",
        "shell",
        "infill",
        "temperature",
        "cooling",
        "speed",
        "support",
        "adhesion",
        "retraction",
        "filament",
    ):
        paths += [f"{group}.{field.name}" for field in fields(getattr(settings, group))]
    return paths


def _other_value(settings: print_settings.PrintSettings, path: str) -> object:
    """Irgendein anderer Wert derselben Art — für die Frage, ob er ankommt."""
    current = print_settings.read_path(settings, path)
    if isinstance(current, bool):
        return not current
    if isinstance(current, int):
        return current + 3
    if isinstance(current, float):
        return current + 3.0
    choices = {
        "shell.seam_position": "rear",
        "shell.wall_generator": "classic",
        "infill.pattern": "gyroid",
        "support.style": "tree",
        "support.placement": "build_plate",
        "adhesion.kind": "raft",
        "filament.colour": "#123456",
    }
    return choices[path]


def test_the_support_angle_is_counted_from_the_right_side() -> None:
    """Derselbe Zahlenwert heißt in zwei Zählweisen das Gegenteil.

    Solidon misst gegen die Senkrechte — 0° stützt jeden Überhang, 90° keinen.
    Das ist Curas Zählweise; PrusaSlicer und die Orca-Familie messen gegen die
    Horizontale. Gemessen an einem Keil mit 30° Neigung: die beiden kippten
    zwischen 20 und 40, Cura zwischen 50 und 70 — an den Rändern wurde aus
    „stütze fast alles" ein „stütze fast nichts".
    """
    profile = profiles.make_profile()
    settings = print_settings.with_path(
        print_settings.resolve(profile), "support.threshold_angle", 50.0
    )

    assert handover.as_mapping(settings, "cura")["support_angle"] == "50"
    assert handover.as_mapping(settings, "prusa")["support_material_threshold"] == "40"
    assert handover.as_mapping(settings, "orca")["support_threshold_angle"] == "40"


def test_no_support_at_all_never_becomes_automatic() -> None:
    """Der Rand, an dem die Umrechnung kippen würde.

    Solidons 90° heißen „stütze nichts". Umgerechnet wäre das eine 0 — und
    die heißt bei PrusaSlicer „automatische Erkennung", bei Orca „nimm beim
    Baum 30". Aus der Absicht würde ihr Gegenteil.
    """
    profile = profiles.make_profile()
    settings = print_settings.with_path(
        print_settings.resolve(profile), "support.threshold_angle", 90.0
    )

    assert handover.as_mapping(settings, "prusa")["support_material_threshold"] == "1"
    assert handover.as_mapping(settings, "orca")["support_threshold_angle"] == "1"


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
    Dokumentation, die für die installierte Version gelten mag oder nicht.

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


def _two_plate_scene() -> object:
    """Eine Szene mit zwei Platten: rot allein, dann weiß und rot."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene.evaluate import EvaluationResult
    from app.core.types import MaterialSlot, Scene, SceneObject

    def body(name: str, plate: int, slots: tuple[MaterialSlot, ...]) -> SceneObject:
        mesh = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
        mesh.apply_translation((0.0, 0.0, 10.0))
        return SceneObject(
            id=name, name=name, mesh=MeshData.of(mesh), plate=plate, material_slots=slots
        )

    rot = MaterialSlot(index=0, name="Rot", colour=(1.0, 0.0, 0.0))
    weiss = MaterialSlot(index=0, name="Weiss", colour=(1.0, 1.0, 1.0))
    return EvaluationResult(
        scene=Scene(
            objects={
                "a": body("a", 0, (rot,)),
                "b": body("b", 1, (weiss,)),
                "c": body("c", 1, (rot,)),
            }
        )
    )


def test_the_plate_choice_appears_and_narrows_what_gets_sliced(qt_app: object) -> None:
    """Die Wahl erscheint nur, wenn es etwas zu wählen gibt — und sie wirkt.

    Beides in einem Test, und das ist eine Entscheidung gegen den üblichen
    Zuschnitt „ein Test, eine Zusage": Zwei Tests bauen zwei Dialoge, und der
    zweite riss die Datei in eine Zugriffsverletzung (Position 57, im Abbau
    von ``_no_worker_outlives_its_window``). Gemessen am 26.08.2026 — ohne
    einen der beiden lief die Datei grün, mit beiden dreimal von dreimal
    nicht, und ein trivialer 75. Test an derselben Stelle war folgenlos. Es
    ist also nicht die Zahl, sondern dieser Dialog ein zweites Mal.

    Das ist die bekannte Mine aus ``conftest.py`` — die Zerstörung eines
    Fensters mit VTK-Zustand mitten in der Suite —, kein eigener Fehler und
    hier nicht zu beheben. Ihr wird ausgewichen, und das steht hier, damit
    der Nächste den Test trennen kann, sobald sie entschärft ist, statt sich
    über den Zuschnitt zu wundern.

    **Die Zusagen selbst:** Bei einer Platte bleibt die Zeile verborgen — eine
    Wahl ohne Alternative ist keine, und der Kunde liest sie doch. Ab der
    zweiten erscheint sie mit „Alle Platten" als Vorgabe, denn das ist der
    bisherige Weg. Und die Wahl wirkt auf beides: den Lauf und die Spulen, die
    er braucht. Solange ``_plate_slots`` fest die erste Platte nahm, ordnete
    der Kunde Filamente einer Platte zu, die er gar nicht slicte.
    """
    from app.ui.print_settings_dialog import PrintSettingsDialog
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    dialog = PrintSettingsDialog(Session(), UiSettings())
    assert dialog.plate_row.isHidden(), "leere Szene: keine Wahl"

    dialog.session.last_result = _two_plate_scene()  # type: ignore[assignment]
    dialog._refresh_plates()

    # ``isHidden`` und nicht ``isVisible``: Letzteres antwortet ``False``,
    # solange der Dialog nicht angezeigt wurde, und zwar für jedes Widget.
    assert not dialog.plate_row.isHidden(), "zwei Platten: jetzt gibt es etwas zu wählen"
    assert dialog.plate_choice.count() == 3, "die Sammelzeile und zwei einzelne"
    assert dialog.plate_choice.currentData() is None, "Vorgabe ist die Sammelzeile"
    assert dialog._chosen_plates() == [0, 1], "und die umfasst beide"

    # Platte 1 trägt nur Rot, Platte 2 trägt Weiß und Rot.
    dialog.plate_choice.setCurrentIndex(1)
    assert dialog._chosen_plates() == [0]
    assert [slot.name for slot in dialog._plate_slots()] == ["Rot"]

    dialog.plate_choice.setCurrentIndex(2)
    assert dialog._chosen_plates() == [1]
    assert sorted(slot.name for slot in dialog._plate_slots()) == ["Rot", "Weiss"]

    # Und zurück auf „Alle": beide Platten, alle Spulen.
    dialog.plate_choice.setCurrentIndex(0)
    assert dialog._chosen_plates() == [0, 1]
    assert sorted(slot.name for slot in dialog._plate_slots()) == ["Rot", "Weiss"]


def test_each_slot_can_carry_its_own_spool_settings(tmp_path: Path) -> None:
    """Vier Spulen sind nicht vier Farben desselben Materials (§20).

    Ein Schriftzug in PLA auf einem Gehäuse aus PETG fährt 210 Grad statt 250.
    Solange alle Slots die Werte des Projektmaterials bekamen, verkohlte
    entweder die Schrift oder das Gehäuse hielt nicht — und zu sehen war es
    erst am fertigen Druck.

    Geprüft wird an der Datei, die der Slicer lädt, nicht am Modell: Ein
    Übersteuerer, der die Übergabe nicht erreicht, ist folgenlos.
    """
    from dataclasses import replace

    from app.core.types import MaterialSlot, SlotOverride

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    assert settings.temperature.nozzle == 240, "das Projekt fährt PETG"

    schrift = replace(settings.temperature, nozzle=210, nozzle_first_layer=215, bed=60)
    settings = replace(
        settings,
        slot_overrides=(SlotOverride(name="Schrift", colour=(1.0, 1.0, 1.0), temperature=schrift),),
    )
    slots = (
        MaterialSlot(index=0, name="Gehäuse", colour=(0.1, 0.1, 0.1)),
        MaterialSlot(index=1, name="Schrift", colour=(1.0, 1.0, 1.0)),
    )
    setup = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")

    written = handover.write_config(settings, profile, setup, tmp_path, slots=slots)
    assert len(written.filaments) == 2, "je Slot eine Datei"

    gehaeuse = json.loads(written.filaments[0].read_text(encoding="utf-8"))
    schriftzug = json.loads(written.filaments[1].read_text(encoding="utf-8"))

    # Der Slot ohne eigene Werte bleibt beim Projekt …
    assert gehaeuse["nozzle_temperature"] == ["240"]
    assert gehaeuse["hot_plate_temp"] == ["80"]
    # … der mit eigenen fährt seine.
    assert schriftzug["nozzle_temperature"] == ["210"]
    assert schriftzug["nozzle_temperature_initial_layer"] == ["215"]
    assert schriftzug["hot_plate_temp"] == ["60"]


def test_a_spool_keeps_its_settings_when_the_order_changes(tmp_path: Path) -> None:
    """Die Werte gehören dem Filament, nicht dem Platz in einer Liste (§20).

    Der Dialog zeigt die Zusammenlegung der gewählten Platten; gedruckt wird
    Platte für Platte, und jede legt für sich zusammen. Bei Rot auf Platte 1
    und Weiß+Rot auf Platte 2 steht [Rot, Weiß] im Dialog und [Weiß, Rot] im
    Lauf der zweiten. Solange der Übersteuerer an der Position hing, bekam
    **Weiß die 210 Grad, die für Rot eingestellt waren** — gemessen am
    26.08.2026, und schwerer als derselbe Fehler bei den Filamentprofilen:
    Dort wandert die Temperatur mit dem Profil, hier *ist* sie der Wert. 210
    Grad auf ein PETG, das 240 braucht, geben einen Druck, der auseinanderfällt.
    """
    from dataclasses import replace

    from app.core.types import MaterialSlot, SlotOverride

    rot = MaterialSlot(index=0, name="Rot", colour=(1.0, 0.0, 0.0))
    weiss = MaterialSlot(index=1, name="Weiß", colour=(1.0, 1.0, 1.0))

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    kalt = replace(settings.temperature, nozzle=210)
    settings = replace(
        settings,
        slot_overrides=(SlotOverride(name="Rot", colour=(1.0, 0.0, 0.0), temperature=kalt),),
    )
    setup = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")

    # Die Reihenfolge des **Laufs**: Weiß zuerst, Rot danach — anders als im
    # Dialog, wo Rot oben stand.
    written = handover.write_config(settings, profile, setup, tmp_path, slots=(weiss, rot))

    erste = json.loads(written.filaments[0].read_text(encoding="utf-8"))
    zweite = json.loads(written.filaments[1].read_text(encoding="utf-8"))
    assert erste["nozzle_temperature"] == ["240"], "Weiß fährt das Projektmaterial"
    assert zweite["nozzle_temperature"] == ["210"], "Rot fährt seine eigenen Werte"


def test_a_slot_override_can_be_added_changed_and_removed() -> None:
    """Die Oberfläche braucht einen einzigen, identitätsfesten Schreibweg.

    Name und Farbe sind der Schlüssel. Würde der Wähler stattdessen an eine
    Listenposition schreiben, bekäme nach einer anderen Plattenauswahl wieder
    die falsche Spule die Temperatur.
    """
    from app.core.types import MaterialSlot, SlotOverride

    slot = MaterialSlot(index=3, name="PLA Weiß", colour=(1.0, 1.0, 1.0))
    settings = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "petg"))
    first = SlotOverride(name=slot.name, colour=slot.colour, temperature=settings.temperature)
    changed = SlotOverride(name=slot.name, colour=slot.colour, cooling=settings.cooling)

    settings = handover.with_slot_override(settings, slot, first)
    assert handover.override_for(settings, slot) == first

    settings = handover.with_slot_override(settings, slot, changed)
    assert settings.slot_overrides == (changed,), "ändern verdoppelt die Spule nicht"

    settings = handover.with_slot_override(settings, slot, None)
    assert handover.override_for(settings, slot) is None
    assert settings.slot_overrides == (), "Projektwerte brauchen keinen leeren Eintrag"


def test_a_slicer_that_takes_one_filament_says_so() -> None:
    """Was ein Slicer nicht entgegennimmt, wird gesagt — nicht verschwiegen.

    Nur die Orca-Familie lädt ein Filamentprofil je Slot. PrusaSlicer bekommt
    eine ``.ini`` und ``CuraEngine`` einen Satz Schlüssel; die Werte der
    zweiten Spule fallen dort weg. Still wäre das der schlechteste Fall: Der
    Kunde sieht seine Einstellung im Dialog stehen und bekommt einen Druck,
    der sie nicht verwendet.
    """
    from dataclasses import replace

    from app.core.types import SlotOverride

    settings = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "petg"))
    eigen = replace(settings.temperature, nozzle=210)
    mit = replace(settings, slot_overrides=(SlotOverride(name="Rot", temperature=eigen),))

    for flavour in ("prusa", "cura"):
        setup = handover.SlicerSetup(executable=Path("slicer.exe"), flavour=flavour)
        findings = handover.unreachable_overrides(mit, setup)
        assert len(findings) == 1, f"{flavour}: der Kunde erfährt es"
        assert findings[0].severity == "warning", "kein Fehler — der Slicer kann nicht mehr"
        # Regel 17: nie mit „fehlgeschlagen" enden, sondern mit einem Weg.
        assert "Orca" in str(findings[0].message), "und wo er es bekäme"

    # Die Orca-Familie nimmt sie an, also gibt es nichts zu melden.
    orca = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")
    assert handover.unreachable_overrides(mit, orca) == []

    # Und ohne eigene Werte schweigt auch Prusa — eine Warnung ohne Anlass
    # ist schlimmer als keine.
    prusa = handover.SlicerSetup(executable=Path("slicer.exe"), flavour="prusa")
    assert handover.unreachable_overrides(settings, prusa) == []
    leer = replace(settings, slot_overrides=(SlotOverride(name="Rot"),))
    assert handover.unreachable_overrides(leer, prusa) == []


def test_a_single_profile_slicer_uses_the_first_filaments_values(tmp_path: Path) -> None:
    """Ein Satz heißt erster Extruder, nicht Projektwert trotz eigener Wahl.

    PrusaSlicer und CuraEngine können auf diesem Weg keine zwei Filamentprofile
    laden. Den ersten Satz können sie sehr wohl übernehmen; ihn ebenfalls zu
    verwerfen und zugleich nur zu warnen wäre unnötiger Datenverlust.
    """
    from app.core.types import MaterialSlot, SlotOverride

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    first = MaterialSlot(index=0, name="PLA Weiß", colour=(1.0, 1.0, 1.0))
    second = MaterialSlot(index=1, name="PETG Rot", colour=(1.0, 0.0, 0.0))
    pla = replace(settings.temperature, nozzle=210)
    petg = replace(settings.temperature, nozzle=245)
    settings = replace(
        settings,
        slot_overrides=(
            SlotOverride(name=first.name, colour=first.colour, temperature=pla),
            SlotOverride(name=second.name, colour=second.colour, temperature=petg),
        ),
    )
    setup = handover.SlicerSetup(executable=Path("prusa-slicer.exe"), flavour="prusa")

    written = handover.write_config(settings, profile, setup, tmp_path, slots=(first, second))
    text = written.process.read_text(encoding="utf-8")

    assert "temperature = 210" in text, "der erreichbare erste Satz kommt an"
    findings = handover.unreachable_overrides(settings, setup, (first, second))
    assert len(findings) == 1
    assert findings[0].values["slots"] == 1, "nur die zweite Spule ist unerreichbar"
    assert handover.unreachable_overrides(settings, setup, (first,)) == []


def test_a_slot_override_survives_the_project_file(tmp_path: Path) -> None:
    """Was der Kunde je Spule einstellt, steht beim nächsten Öffnen noch da.

    Ohne diesen Weg wäre die Übersteuerung eine Sitzungseinstellung: einmal
    gesetzt, beim Speichern verloren, und der zweite Druck desselben Projekts
    liefe wieder mit den Werten des Projektmaterials.
    """
    from dataclasses import replace

    from app.core.scene import serialise
    from app.core.types import SlotOverride

    settings = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "petg"))
    eigen = replace(settings.temperature, nozzle=210)
    settings = replace(
        settings,
        slot_overrides=(SlotOverride(name="Rot", colour=(1.0, 0.0, 0.0), temperature=eigen),),
    )

    # Durch JSON hindurch, nicht nur durch die beiden Funktionen: Ein Wert,
    # den ``json.dumps`` nicht schreiben kann, fiele sonst nicht auf.
    zurueck = serialise.print_settings_from_data(
        json.loads(json.dumps(serialise.print_settings_to_data(settings)))
    )
    assert zurueck.slot_overrides == settings.slot_overrides

    # Ein Slot ohne eigene Werte steht als ``null`` da und nicht als vier
    # leere Gruppen, die vortäuschen, jemand hätte etwas eingestellt.
    daten = serialise.print_settings_to_data(settings)
    # Die Identität reist mit — ohne sie fände der Übersteuerer sein Filament
    # beim nächsten Öffnen nicht wieder.
    assert daten["slot_overrides"][0]["name"] == "Rot"
    assert daten["slot_overrides"][0]["colour"] == [1.0, 0.0, 0.0]
    assert set(daten["slot_overrides"][0]) == {"name", "colour", "temperature"}

    # Und eine Datei ohne das Feld öffnet weiterhin — der Normalfall bei
    # jedem Projekt, das vor dieser Fassung entstanden ist.
    alt = serialise.print_settings_to_data(settings)
    del alt["slot_overrides"]
    assert serialise.print_settings_from_data(alt).slot_overrides == ()


def test_the_handover_kind_travels_with_the_project() -> None:
    """§29 wörtlich: Die Übergabeart wird je Projekt gemerkt — sie reist in
    den Druckeinstellungen. Eine ältere Datei ohne das Feld bleibt auf
    „slice", dem bisher einzigen Weg, und ein fremder Wert fällt dorthin
    zurück, statt bis in die Knopfleiste zu reisen."""
    from dataclasses import replace

    from app.core.scene import serialise

    settings = replace(print_settings.resolve(profiles.make_profile()), handover="open")

    zurueck = serialise.print_settings_from_data(
        json.loads(json.dumps(serialise.print_settings_to_data(settings)))
    )
    assert zurueck.handover == "open"

    alt = serialise.print_settings_to_data(settings)
    del alt["handover"]
    assert serialise.print_settings_from_data(alt).handover == "slice"
    assert serialise.print_settings_from_data({"handover": "quatsch"}).handover == "slice"


def test_the_orca_machine_profile_is_written_out_not_referenced(tmp_path: Path) -> None:
    """Solidon schreibt das Maschinenprofil aus, statt auf eines zu verweisen.

    Bisher bekam der Slicer den **Namen** eines Profils aus seinem Bestand
    und löste alles Weitere selbst auf. Gemessen am Elegoo-Bestand stehen in
    ``Elegoo Centauri 0.2 nozzle`` sechzehn Schlüssel und im Lauf
    dreiundachtzig — die übrigen siebenundsechzig kamen aus einer Erbkette,
    die dem Slicer gehört.

    Der Anfahrcode ist dabei der Prüfstein: Er steht nie in der obersten
    Datei, sondern immer eine Stufe tiefer. Kommt er hier an, ist die Kette
    aufgelöst; fehlt er, fährt der Drucker ohne Bettvermessung los.
    """
    wurzel = tmp_path / "fdm_machine_common.json"
    wurzel.write_text(
        json.dumps(
            {
                "type": "machine",
                "name": "fdm_machine_common",
                "machine_start_gcode": "G28 ;Startpunkt anfahren",
                "printable_height": "256",
                "retraction_length": ["0.8"],
            }
        ),
        encoding="utf-8",
    )
    oben = tmp_path / "Drucker 0.4 nozzle.json"
    oben.write_text(
        json.dumps(
            {
                "type": "machine",
                "name": "Drucker 0.4 nozzle",
                "inherits": "fdm_machine_common",
                "nozzle_diameter": ["0.4"],
            }
        ),
        encoding="utf-8",
    )
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(
        executable=Path("orca-slicer.exe"),
        flavour="orca",
        machine_profile=str(oben),
    )
    written = handover.write_config(settings, profile, setup, tmp_path)

    assert written.machine is not None, "die Übergabe trägt ein Maschinenprofil"
    document = json.loads(written.machine.read_text(encoding="utf-8"))
    # Der geerbte Anfahrcode — der Grund für die ganze Auflösung.
    assert document["machine_start_gcode"] == "G28 ;Startpunkt anfahren"
    assert document["retraction_length"] == ["0.8"], "auch der geerbte Rückzug"
    assert document["nozzle_diameter"] == ["0.4"], "und der eigene Wert der Stufe"
    # Nichts wird nachgeladen: Was in der Datei steht, gilt.
    assert "inherits" not in document, "ausgeschrieben, nicht verwiesen"
    assert document["from"] == "system", (
        "ElegooSlicer ordnet ein User-Maschinenprofil keinem Prozessprofil zu"
    )
    assert document["name"].startswith("Solidon"), "und es ist Solidons Datei"


def test_the_orca_process_names_the_machine_solidon_wrote(tmp_path: Path) -> None:
    """Prozess und Maschine tragen denselben Namen — sonst nimmt der Slicer nichts.

    Die Orca-Familie bricht mit „process not compatible with printer" ab,
    bevor sie das Modell ansieht. Solange die Bindung geerbt war, hielt sie
    ``inherits``; da die Werte jetzt ausgeschrieben sind, setzt Solidon sie
    selbst — und beide Namen kommen aus derselben Funktion.
    """
    maschine = tmp_path / "Drucker 0.4 nozzle.json"
    maschine.write_text(
        json.dumps({"type": "machine", "name": "Drucker 0.4 nozzle", "printable_height": "256"}),
        encoding="utf-8",
    )
    prozess = tmp_path / "0.20mm Standard.json"
    prozess.write_text(
        json.dumps(
            {
                "type": "process",
                "name": "0.20mm Standard",
                "compatible_printers": ["Ein ganz anderer Drucker"],
                "wall_loops": "2",
            }
        ),
        encoding="utf-8",
    )
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(
        executable=Path("orca-slicer.exe"),
        flavour="orca",
        machine_profile=str(maschine),
        base_process=str(prozess),
    )
    written = handover.write_config(settings, profile, setup, tmp_path)

    assert written.machine is not None
    maschinendatei = json.loads(written.machine.read_text(encoding="utf-8"))
    prozessdatei = json.loads(written.process.read_text(encoding="utf-8"))
    assert prozessdatei["compatible_printers"] == [maschinendatei["name"]], (
        "der Prozess nennt die Maschine, die daneben geschrieben wurde"
    )
    assert prozessdatei["from"] == maschinendatei["from"] == "system", (
        "nur dieselbe CLI-Kategorie nimmt die Bindung als verträglich an"
    )
    # Und nicht mehr die des Herstellers: Sie zeigte auf ein Profil aus
    # seinem Bestand, das hier gar nicht mitgeliefert wird.
    assert prozessdatei["compatible_printers"] != ["Ein ganz anderer Drucker"]


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


def _cura_definitions() -> dict[str, dict[str, object]] | None:
    """Curas Einstellungsdefinition aus einer Installation, flach gelesen.

    Sie liegt neben jeder ``CuraEngine`` und nennt jeden gültigen Schlüssel,
    seine Einheit und seinen Vorgabewert. Das ist die einzige Auskunft
    darüber, ob eine Zuordnung trifft — und sie kommt vom Programm selbst,
    nicht aus einer Dokumentation, die für die installierte Version gelten mag
    oder nicht. Bei Prusa und Orca leistet das die Gegenprobe im G-Code; bei
    Cura kann sie es nicht, weil dort keine Einstellung in der Druckdatei
    steht.
    """
    flat: dict[str, dict[str, object]] = {}

    def walk(node: dict[str, object]) -> None:
        for key, value in node.items():
            if isinstance(value, dict):
                flat[key] = value
                children = value.get("children")
                if isinstance(children, dict):
                    walk(children)

    found = False
    for base in (Path("C:/Program Files"), Path("/usr/share"), Path("/opt")):
        if not base.is_dir():
            continue
        for folder in base.iterdir():
            for definitions in (
                folder / "share" / "cura" / "resources" / "definitions",
                folder / "resources" / "definitions",
            ):
                for name in ("fdmprinter.def.json", "fdmextruder.def.json"):
                    path = definitions / name
                    if not path.is_file():
                        continue
                    try:
                        loaded = json.loads(path.read_text(encoding="utf-8"))
                    except (OSError, ValueError):
                        continue
                    settings = loaded.get("settings")
                    if isinstance(settings, dict):
                        walk(settings)
                        found = True
    return flat if found else None


def test_every_cura_key_exists_in_the_definition() -> None:
    """Ein Schlüssel, den Cura nicht kennt, wird stillschweigend verworfen.

    Genau das geschah mit ``outer_inset_first``: den Namen kennt Cura 5 nicht
    mehr, er heißt dort ``inset_direction``. Der Wert war geschrieben,
    gemessen wurde nichts davon — null von fünfzig Lagen begannen außen.
    Auffallen konnte es nicht, weil die Gegenprobe bei Cura nichts findet:
    ``CuraEngine`` schreibt seine Einstellungen nicht in die Druckdatei.
    """
    known = _cura_definitions()
    if known is None:
        pytest.skip("keine Cura-Installation, deren Definition sich lesen ließe")

    profile = profiles.make_profile()
    written = handover.values_for(print_settings.resolve(profile), profile, "cura")
    unknown = sorted(key for key in written if key not in known)
    assert not unknown, "Schlüssel, die Cura nicht kennt: " + ", ".join(unknown)


def test_nothing_cura_derives_is_left_to_its_default() -> None:
    """Die Gegenprobe zur Ableitungsstufe — und der Grund, warum es sie gibt.

    ``CuraEngine`` löst keine Vererbung auf: was Solidon schreibt, erreicht
    die abgeleiteten Schlüssel nicht, und die bleiben bei ihrem Vorgabewert.
    Gemessen an einem 20-mm-Würfel kostete das 1100 mm Filament statt 818.

    Geprüft wird beides: dass nichts offen bleibt, und dass keine Ausnahme in
    ``CURA_UNTOUCHED`` steht, die es nicht mehr braucht. Eine Liste, die nur
    wächst, erklärt am Ende nichts mehr.
    """
    known = _cura_definitions()
    if known is None:
        pytest.skip("keine Cura-Installation, deren Definition sich lesen ließe")

    profile = profiles.make_profile()
    written = handover.values_for(print_settings.resolve(profile), profile, "cura")
    derived: set[str] = set()
    frontier, seen = set(written), set(written)
    while frontier:
        found = set()
        for key, spec in known.items():
            if key in seen:
                continue
            formula = spec.get("value")
            if not isinstance(formula, str):
                continue
            if any(re.search(rf"\b{re.escape(source)}\b", formula) for source in frontier):
                found.add(key)
                derived.add(key)
        seen |= found
        frontier = found

    open_ended = sorted(derived - set(slicer_keys.CURA_UNTOUCHED))
    assert not open_ended, "bleibt auf Curas Vorgabe stehen: " + ", ".join(open_ended)
    stale = sorted(set(slicer_keys.CURA_UNTOUCHED) - derived)
    assert not stale, "in CURA_UNTOUCHED, aber ohne Anlass: " + ", ".join(stale)


def test_a_key_cura_does_not_know_becomes_a_finding(tmp_path: Path) -> None:
    """Was der Gegenprobe bei Cura fehlt, holt die Definition nach.

    ``CuraEngine`` schreibt seine Einstellungen nicht in die Druckdatei —
    ``verify`` findet dort null von den geschriebenen Schlüsseln wieder. Ein
    Name, den diese Version nicht kennt, wird stillschweigend verworfen; die
    Definition daneben ist die einzige Stelle, an der es auffallen kann.
    """
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    engine = tmp_path / "CuraEngine.exe"
    engine.write_bytes(b"")
    setup = handover.SlicerSetup(executable=engine, flavour="cura")

    # Eine Definition, die alles kennt außer einem — so ist der Befund genau
    # der eine und nicht eine Liste von zweihundert.
    written = sorted(handover.values_for(settings, profile, "cura"))
    dropped = written[0]
    definitions = tmp_path / "share" / "cura" / "resources" / "definitions"
    definitions.mkdir(parents=True)
    (definitions / "fdmprinter.def.json").write_text(
        json.dumps(
            {"settings": {"alles": {"children": {key: {} for key in written[1:]}}}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    findings = handover.unknown_keys(settings, profile, setup)

    assert findings and findings[0].code == "slicer.unknown_key"
    assert findings[0].values["count"] == 1
    assert findings[0].values["settings"] == dropped


def test_without_a_definition_nothing_is_claimed(tmp_path: Path) -> None:
    """Liegt keine Definition da, läuft der Slicer aus einem Paket, dessen
    Aufbau Solidon nicht kennt — dann wird auch nichts behauptet."""
    engine = tmp_path / "CuraEngine.exe"
    engine.write_bytes(b"")
    profile = profiles.make_profile()
    setup = handover.SlicerSetup(executable=engine, flavour="cura")

    assert not handover.unknown_keys(print_settings.resolve(profile), profile, setup)


def test_a_missing_model_says_so_before_starting_anything(tmp_path: Path) -> None:
    profile = profiles.make_profile()
    setup = handover.SlicerSetup(executable=Path("PrusaSlicer.exe"), flavour="prusa")

    with pytest.raises(ExternalToolError) as raised:
        handover.slice_model(
            tmp_path / "gibtesnicht.stl", print_settings.resolve(profile), profile, setup
        )
    assert raised.value.suggestions


def test_a_slicer_that_moved_away_points_at_the_extra_programs(tmp_path: Path) -> None:
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    profile = profiles.make_profile()
    setup = handover.SlicerSetup(executable=tmp_path / "weg.exe", flavour="prusa")

    with pytest.raises(ExternalToolError) as raised:
        handover.slice_model(model, print_settings.resolve(profile), profile, setup)
    assert any(action.id == "install" for action in raised.value.suggestions)


class _Finished:
    """Ein Slicerlauf, der zurückkam, ohne etwas zu schreiben."""

    def __init__(self, output: bytes) -> None:
        self.returncode = 0
        self.stdout = output
        self.stderr = b""


def _slicer_saying(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, output: bytes
) -> tuple[Path, handover.SlicerSetup]:
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    executable = tmp_path / "prusa-slicer.exe"
    executable.write_bytes(b"")
    monkeypatch.setattr(handover, "_run_slicer", lambda *args, **kwargs: _Finished(output))
    return model, handover.SlicerSetup(executable=executable, flavour="prusa")


def test_a_plate_outside_the_volume_offers_arranging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regel 17: Der Satz nennt die Ursache, und eine Handlung behebt sie.

    Gemessen an PrusaSlicer 2.9.6: Eine Platte in Bettkoordinaten — so kommt
    sie aus einer fremden 3MF — endet mit Rückgabewert 0 und dem Satz „All
    objects are outside of the print volume." Daraus wurde bisher „Der Slicer
    hat keine Druckdatei geschrieben", dazu drei Handlungen, von denen keine
    hilft. Was hilft, ist ein Klick auf *Auf dem Bett anordnen*.
    """
    profile = profiles.make_profile()
    model, setup = _slicer_saying(
        monkeypatch, tmp_path, b"All objects are outside of the print volume.\n"
    )

    with pytest.raises(ExternalToolError) as raised:
        handover.slice_model(model, print_settings.resolve(profile), profile, setup)

    assert "Bauraum" in str(raised.value), str(raised.value)
    assert any(action.id == "arrange_on_bed" for action in raised.value.suggestions)
    assert raised.value.values["output"], "die Ausgabe des Slicers bleibt lesbar"


def test_any_other_silence_keeps_the_old_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Gegenprobe. Die Orca-Familie verschluckt die Ursache — ihr CLI
    meldet nur „Slic3r::CLI::run found error, exit", und denselben Satz auch bei
    einem fehlenden Maschinenprofil. Daraus etwas über den Bauraum zu schließen
    wäre geraten.
    """
    profile = profiles.make_profile()
    model, setup = _slicer_saying(monkeypatch, tmp_path, b"Slic3r::CLI::run found error, exit\n")

    with pytest.raises(ExternalToolError) as raised:
        handover.slice_model(model, print_settings.resolve(profile), profile, setup)

    assert "Bauraum" not in str(raised.value), str(raised.value)
    assert not any(action.id == "arrange_on_bed" for action in raised.value.suggestions)
    assert any(action.id == "check_profile" for action in raised.value.suggestions)


def test_no_layers_points_at_the_model_instead_of_the_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ElegooSlicer 1.5.3.4 benennt den Fall, und Solidon nutzt die Auskunft.

    Ein offener Würfel endete vorher bei „Maschinenprofil prüfen“. Das Profil
    hatte gerade einen gesunden Würfel geslicet; repariert werden muss das
    Modell, und die Ausgabe lässt offen, ob die Ursache eine Öffnung, ein zu
    dünner Körper oder eine falsche Einheit ist.
    """
    profile = profiles.make_profile()
    model, setup = _slicer_saying(
        monkeypatch,
        tmp_path,
        b"No layers were detected. You might want to repair your STL file(s).\n",
    )

    with pytest.raises(ExternalToolError) as raised:
        handover.slice_model(model, print_settings.resolve(profile), profile, setup)

    text = str(raised.value)
    assert "keine druckbaren Schichten" in text
    assert all(word in text for word in ("offene Stellen", "Einheit", "Wandstärke"))
    offered = {action.id for action in raised.value.suggestions}
    assert {"repair_and_retry", "show_locations"} <= offered
    assert "check_profile" not in offered, "der Slicer hat das Modell benannt, nicht das Profil"


def test_a_failed_run_offers_switching_the_slicer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§2.1: Scheitert der eingestellte Slicer, ist der Wechsel der kürzeste
    Ausweg — auf dieser Maschine standen zwei arbeitende neben dem einen, der
    nicht wollte, und die Absage bot nur „Nur exportieren" an (30.08.2026).
    """
    profile = profiles.make_profile()
    model, setup = _slicer_saying(monkeypatch, tmp_path, b"Slic3r::CLI::run found error, exit\n")

    with pytest.raises(ExternalToolError) as raised:
        handover.slice_model(model, print_settings.resolve(profile), profile, setup)

    offered = [action.id for action in raised.value.suggestions]
    assert "choose_slicer" in offered
    assert offered.index("choose_slicer") == 0, "der Wechsel steht vorn, nicht hinter dem Export"


def test_window_program_finds_the_sibling_of_a_console(tmp_path: Path) -> None:
    """Die zweite Übergabeart (§29) braucht ein Fenster, und das liegt bei
    zwei Familien neben dem Konsolenprogramm — nur dort wird gesucht."""
    console = tmp_path / "prusa-slicer-console.exe"
    console.write_bytes(b"")
    window = tmp_path / "prusa-slicer.exe"
    window.write_bytes(b"")
    assert handover.window_program(console) == window

    engine = tmp_path / "CuraEngine.exe"
    engine.write_bytes(b"")
    cura = tmp_path / "Ultimaker-Cura.exe"
    cura.write_bytes(b"")
    assert handover.window_program(engine) == cura

    orca = tmp_path / "elegoo-slicer.exe"
    orca.write_bytes(b"")
    assert handover.window_program(orca) == orca, "die Orca-Familie ist ihr eigenes Fenster"


def test_open_in_slicer_without_a_window_offers_a_way_out(tmp_path: Path) -> None:
    """Eine CuraEngine ohne Cura daneben kann die Datei nicht zeigen — die
    Absage nennt den Wechsel und den Export, nicht nur das Scheitern."""
    engine = tmp_path / "CuraEngine.exe"
    engine.write_bytes(b"")
    model = tmp_path / "teil.3mf"
    model.write_bytes(b"x")
    setup = handover.SlicerSetup(executable=engine, flavour="cura")

    with pytest.raises(ExternalToolError) as raised:
        handover.open_in_slicer(model, setup)

    offered = {action.id for action in raised.value.suggestions}
    assert {"choose_slicer", "export_only"} <= offered


def test_open_in_slicer_starts_the_window_with_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Aufruf ist eine feste Argumentliste (§32): das Fenster, die Datei,
    sonst nichts — und gewartet wird nicht."""
    executable = tmp_path / "elegoo-slicer.exe"
    executable.write_bytes(b"")
    model = tmp_path / "teil.3mf"
    model.write_bytes(b"x")
    started: list[list[str]] = []

    class _Detached:
        def __init__(self, command: list[str], **kwargs: object) -> None:
            started.append(list(command))

    monkeypatch.setattr(handover.subprocess, "Popen", _Detached)
    handover.open_in_slicer(model, handover.SlicerSetup(executable=executable, flavour="orca"))

    assert started == [[str(executable), str(model)]]


def test_an_unknown_arrange_flag_falls_back_and_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ElegooSlicer 1.5.3.4 bricht auf ``--arrange`` mit „found error" ab —
    Exit 127, kein Wort über den Grund (gemessen 30.08.2026). Der Rückfall
    läuft einmal ohne den Schalter, weist die verworfene Anordnung als Befund
    aus und merkt sich das Programm, damit die nächste Platte sofort richtig
    läuft."""
    profile = profiles.make_profile()
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    executable = tmp_path / "elegoo-slicer.exe"
    executable.write_bytes(b"")
    setup = handover.SlicerSetup(executable=executable, flavour="orca")
    commands: list[list[str]] = []

    def fake_run(command: list[str], *args: object, **kwargs: object) -> _Finished:
        commands.append(list(command))
        if "--arrange" in command:
            failed = _Finished(b"Slic3r::CLI::run found error, exit\n")
            failed.returncode = 127
            return failed
        target = Path(command[command.index("--outputdir") + 1])
        (target / "plate_1.gcode").write_text(_gcode_printing_at(1.0, 5.0), encoding="utf-8")
        return _Finished(b"")

    monkeypatch.setattr(handover, "_run_slicer", fake_run)
    outcome = handover.slice_model(
        model, print_settings.resolve(profile), profile, setup, keep_arrangement=True
    )

    assert len(commands) == 2, "erst mit Schalter, dann die Rückfallstufe ohne"
    assert "--arrange" in commands[0] and "--arrange" not in commands[1]
    assert any(entry.code == "slicer.arranged_itself" for entry in outcome.findings)

    # Gemerkt: derselbe Slicer bekommt den Schalter nicht noch einmal — und
    # der Befund bleibt, denn die Anordnung liegt weiter beim Slicer.
    again = handover.slice_model(
        model, print_settings.resolve(profile), profile, setup, keep_arrangement=True
    )
    assert len(commands) == 3, "die zweite Platte läuft in einem Zug"
    assert "--arrange" not in commands[2]
    assert any(entry.code == "slicer.arranged_itself" for entry in again.findings)


def test_a_print_file_shorter_than_the_model_is_an_error() -> None:
    """CuraEngine schneidet unter ``z = 0`` wortlos ab (gemessen 30.08.2026:
    50 Schichten statt 100 bei einem zentriert importierten Würfel, Exit 0).
    Keine andere Gegenprobe sieht das — die halbe Höhe liegt brav im Bauraum.
    """
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    half = "G90\nM82\n" + "".join(
        f"G1 Z{z / 10.0:g}\nG1 X10 Y0 E{z / 10.0:g}\n" for z in range(2, 102, 2)
    )

    short = handover.too_short(half, 20.0, settings)
    assert short is not None, "10 mm Druck bei 20 mm Modell ist ein Befund"
    assert short.severity == "error"
    assert short.source == "gcode", "die Aussage kommt aus der Druckdatei (Regel 14)"

    assert handover.too_short(half, 10.0, settings) is None, "volle Höhe: kein Befund"
    assert handover.too_short(half, 10.3, settings) is None, (
        "zwei Schichthöhen Luft für Rundung und erste Schicht"
    )


def test_open_in_slicer_reports_a_missing_file(tmp_path: Path) -> None:
    """Die Datei ist zwischen Export und Öffnen verschwunden — derselbe Satz
    und derselbe Ausweg wie beim Konsolenlauf."""
    executable = tmp_path / "elegoo-slicer.exe"
    executable.write_bytes(b"")
    setup = handover.SlicerSetup(executable=executable, flavour="orca")

    with pytest.raises(ExternalToolError) as raised:
        handover.open_in_slicer(tmp_path / "fehlt.3mf", setup)

    assert any(action.id == "retry" for action in raised.value.suggestions)


def _gcode_printing_at(*xs: float) -> str:
    """Eine kleinste Druckdatei, die genau an diesen X-Stellen Material legt."""
    lines = ["G90", "M82", "G1 Z0.2 F300"]
    lines += [f"G1 X{x:g} Y0 E{index / 10.0 + 0.1:g}" for index, x in enumerate(xs)]
    return "\n".join(lines) + "\n"


def _slicer_writing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, payload: str, flavour: str = "cura"
) -> tuple[Path, handover.SlicerSetup]:
    """Ein Slicer, der durchläuft und genau diese Datei schreibt.

    Geschrieben wird in ``tmp_path``, denn genau der geht als ``output_dir``
    hinein — ``_find_gcode`` sucht dort.
    """
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    executable = tmp_path / f"{flavour}.exe"
    executable.write_bytes(b"")

    def _writes(*_args: object, **_kwargs: object) -> _Finished:
        (tmp_path / "geschrieben.gcode").write_text(payload, encoding="utf-8")
        return _Finished(b"")

    monkeypatch.setattr(handover, "_run_slicer", _writes)
    return model, handover.SlicerSetup(executable=executable, flavour=flavour)  # type: ignore[arg-type]


def test_the_first_spools_value_is_verified_as_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Gegenprobe vergleicht mit dem Satz, den der Slicer wirklich bekam.

    Prusa und Cura nehmen einen Filamentsatz. Ist die erste Spule auf 210 °C
    gestellt und das Projekt auf 240 °C, ist 210 im G-Code ein Erfolg und kein
    angebliches Übergehen der Einstellung.
    """
    from app.core.types import SlotOverride

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    slot = MaterialSlot(index=0, name="PLA Weiß", colour=(1.0, 1.0, 1.0))
    own_temperature = replace(settings.temperature, nozzle=210)
    settings = replace(
        settings,
        slot_overrides=(
            SlotOverride(
                name=slot.name,
                colour=slot.colour,
                temperature=own_temperature,
            ),
        ),
    )
    payload = _gcode_printing_at(-10.0, 10.0) + "; temperature = 210\n"
    model, setup = _slicer_writing(monkeypatch, tmp_path, payload, flavour="prusa")

    outcome = handover.slice_model(
        model,
        settings,
        profile,
        setup,
        output_dir=tmp_path,
        slots=(slot,),
    )

    assert "slicer.setting_ignored" not in {finding.code for finding in outcome.findings}


def test_a_gcode_that_prints_beside_the_bed_becomes_a_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gemessen an CuraEngine 5.13.0: ein Würfel 150 mm neben der Mitte, ein
    Bett von 220 mm — PrusaSlicer rückt ihn selbst in die Mitte, CuraEngine
    schreibt eine Datei, die bei x 130,2 bis 169,8 druckt. Es prüft den Bauraum
    nicht, und sein Kopf sagt dazu ``MINX:2.14748e+06``, also nichts.

    Gesperrt wird nichts (§29) — die Datei kommt zurück, der Befund steht
    daneben, und er trägt ``source="gcode"``, weil er an den Bahnen gemessen
    ist und nicht geschätzt (Regel 14).
    """
    profile = profiles.make_profile()
    model, setup = _slicer_writing(monkeypatch, tmp_path, _gcode_printing_at(150.0, 170.0))

    outcome = handover.slice_model(
        model, print_settings.resolve(profile), profile, setup, output_dir=tmp_path
    )

    beyond = [entry for entry in outcome.findings if entry.code == "gcode.off_the_bed"]
    assert beyond, [entry.code for entry in outcome.findings]
    assert beyond[0].severity == "error"
    assert beyond[0].source == "gcode"
    assert beyond[0].values["axis"] == "X"
    # 170 gedruckt, 110 erlaubt — das halbe Bett von 220.
    assert beyond[0].values["excess_mm"] == pytest.approx(60.0)
    assert outcome.gcode_path.is_file(), "die Datei bleibt trotzdem"


def test_a_gcode_that_stays_on_the_bed_says_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Gegenprobe: derselbe Weg, dieselbe Prüfung, ein Druck in der Mitte.

    Ohne sie prüfte der Test oben bloß, dass irgendein Befund entsteht.
    """
    profile = profiles.make_profile()
    model, setup = _slicer_writing(monkeypatch, tmp_path, _gcode_printing_at(-30.0, 30.0))

    outcome = handover.slice_model(
        model, print_settings.resolve(profile), profile, setup, output_dir=tmp_path
    )

    assert not [entry for entry in outcome.findings if entry.code == "gcode.off_the_bed"]


def test_the_orca_family_is_measured_from_the_corner() -> None:
    """Zwei Welten, und sie zu verwechseln kostet einen falschen Befund bei
    jedem Lauf: Cura und PrusaSlicer bekommen von Solidon eine Maschine um den
    Ursprung, die Orca-Familie lädt ihr eigenes Profil und misst von der Ecke.

    Dieselbe Datei ist deshalb für die eine Familie in Ordnung und für die
    andere daneben — und zwar in beide Richtungen.
    """
    profile = profiles.make_profile()
    mitte = _gcode_printing_at(-30.0, 30.0)
    ecke = _gcode_printing_at(80.0, 140.0)

    assert handover.off_the_bed(mitte, profile, "cura") is None
    assert handover.off_the_bed(mitte, profile, "orca") is not None, "unter Null gibt es kein Bett"
    assert handover.off_the_bed(ecke, profile, "orca") is None
    assert handover.off_the_bed(ecke, profile, "cura") is not None, "140 statt höchstens 110"


def test_the_bed_in_the_file_beats_the_one_in_the_profile() -> None:
    """Wo der Slicer sein Bett selbst nennt, gilt seines.

    Die Orca-Familie und PrusaSlicer schreiben ihre Bettform in die Datei; ihr
    Maschinenprofil kommt aus dem Bestand des Slicers und nicht von Solidon
    (§29). Gemessen an einem Würfel in der Mitte eines 256er Betts, während im
    Dokument ein 220er Drucker steht — bei x 230 bis 250, also jenseits von
    220 und diesseits von 256. Ohne diese Vorfahrt stünde dort ein
    Befund über einen Druck, der genau dort liegt, wo er hingehört — und die
    Ursache wäre nicht der Druck, sondern zwei Profile, die verschiedene
    Maschinen meinen.
    """
    profile = profiles.make_profile()
    assert profile.printer.build_volume[0] == 220.0, "der Ausgangspunkt des Tests"
    weit_draussen = _gcode_printing_at(230.0, 250.0)
    mit_bett = "; printable_area = 0x0,256x0,256x256,0x256\n" + weit_draussen

    assert handover.off_the_bed(weit_draussen, profile, "orca") is not None
    assert handover.off_the_bed(mit_bett, profile, "orca") is None, "auf seinem Bett liegt es"


def test_a_file_without_a_single_path_is_not_judged() -> None:
    """Eine Datei ohne Materialbahn sagt nichts über den Bauraum — dazu steht
    schon der Abbruch aus :func:`gcode.extrudes` bereit."""
    profile = profiles.make_profile()

    assert handover.off_the_bed("G90\nG0 X400 Y400\nM104 S210\n", profile, "cura") is None


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
    denen prüfte die Orca-Familie die Verträglichkeit, und der Lauf brach mit
    „can not find setting file" ab, bevor das Modell an die Reihe kam.

    Seit dem 26.08.2026 löst Solidon die Kette selbst auf, ``inherits``
    fällt weg — die Bindung bleibt, sie ist der Teil, der bleiben muss.
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
    # Keine Erbschaft mehr: Die Werte stehen seit dem 26.08.2026
    # ausgeschrieben in der Datei, und ein ``inherits`` daneben lüde
    # die Kette ein zweites Mal — aus einem Bestand, der sich ändern
    # kann, während die geschriebene Datei es nicht tut.
    assert "inherits" not in daten, "die Erbkette ist aufgelöst, nicht verwiesen"
    assert daten["layer_height"] == "0.2", "und ihr Wert steht in der Datei"
    # Die Bindung überlebt das Auflösen — hier die geerbte, weil dieser
    # Aufruf kein eigenes Maschinenprofil kennt (``machine_profile``
    # ist leer). Ohne sie bräche der Slicer mit „process not compatible
    # with printer" ab.
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


def test_project_settings_keep_profile_wide_lists_flat(tmp_path: Path) -> None:
    """Profil-Metadaten und Vektoren sind keine zweite Extruderliste.

    Ein äußerer Eintrag je Spule um eine bereits vollständige Liste erzeugte
    ``[[], []]`` beziehungsweise ``[[a, b], [a, b]]``. Diese Form kennt das
    Slicerformat nicht; beschreibende Felder fallen weg, ein gemeinsamer
    Profilwert bleibt flach.
    """
    filament = _filament_profile(
        tmp_path,
        "Haus PLA",
        compatible_prints=[],
        filament_custom_curve=["a", "b"],
    )
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.resolve(profile)
    slots = (
        MaterialSlot(index=0, name="PLA Weiß", material=str(filament)),
        MaterialSlot(index=1, name="PLA Schwarz", material=str(filament)),
    )
    setup = handover.SlicerSetup(executable=Path("orca.exe"), flavour="orca")

    document = handover.project_settings(settings, profile, setup, slots=slots)

    assert "compatible_prints" not in document, "Profilbeschreibung ist kein Druckwert"
    assert document["filament_custom_curve"] == ["a", "b"], (
        "ein gemeinsamer Vektor bleibt eine flache Liste"
    )


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
        MaterialSlot(
            index=1,
            name="Schrift",
            colour=(1.0, 1.0, 1.0),
            material=str(pla),
            material_type="PLA",
        ),
    ]

    config = handover.write_config(settings, profile, setup, tmp_path, slots)

    assert len(config.filaments) == 2, "je Slot ein Profil"
    erste, zweite = (json.loads(f.read_text(encoding="utf-8")) for f in config.filaments)
    assert erste["nozzle_temperature"] == ["240"], "der Hersteller des Slots gilt"
    assert zweite["nozzle_temperature"] == ["210"], "und für den zweiten ein anderer"
    assert zweite["filament_max_volumetric_speed"] == ["21"]
    assert zweite["filament_type"] == ["PLA"], "der Typ reist mit derselben Spule"
    assert erste["filament_colour"] == ["#000000"], "die Farbe kommt vom Slot"
    assert zweite["filament_colour"] == ["#FFFFFF"]
    assert zweite["name"] == "Solidon Schrift"

    befehl = handover._command(setup, [tmp_path / "platte.3mf"], config, tmp_path)
    stelle = befehl.index("--load-filaments")
    assert befehl[stelle + 1].count(";") == 1, "beide gehen an den Slicer, nicht nur eines"


def test_a_manual_slot_type_wins_over_the_projects_base_filament(tmp_path: Path) -> None:
    """Die sichtbare Spulenwahl steht über der allgemeinen Profilunterlage.

    Eine lokal angelegte PLA-Spule hat einen Typ, aber kein eigenes
    Herstellerprofil. Das globale PETG-Profil darf seinen Typ beim Auffüllen
    der übrigen Werte nicht wieder über die ausdrückliche Wahl schreiben.
    """
    petg = _filament_profile(tmp_path, "Haus PETG", filament_type=["PETG"])
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(
        executable=Path("orca-slicer.exe"),
        flavour="orca",
        base_filament=str(petg),
    )
    slot = MaterialSlot(index=0, name="PLA Lokal", material_type="PLA")

    config = handover.write_config(settings, profile, setup, tmp_path, (slot,))

    written = json.loads(config.filaments[0].read_text(encoding="utf-8"))
    assert written["filament_type"] == ["PLA"]


def test_a_slot_override_wins_over_its_selected_filament_profile(tmp_path: Path) -> None:
    """Die ausdrückliche Kundenwahl ist die oberste Schicht des Profils.

    Das Herstellerprofil liefert weiterhin alles, was nicht geändert wurde.
    Eine aktivierte Temperaturgruppe darf es aber nicht still wieder auf seine
    eigene Temperatur zurücksetzen.
    """
    from app.core.types import MaterialSlot, SlotOverride

    pla = _filament_profile(
        tmp_path,
        "Haus PLA",
        nozzle_temperature=["205"],
        filament_max_volumetric_speed=["21"],
    )
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    temperature = replace(settings.temperature, nozzle=215)
    slot = MaterialSlot(
        index=0,
        name="PLA Weiß",
        colour=(1.0, 1.0, 1.0),
        material=str(pla),
    )
    settings = replace(
        settings,
        slot_overrides=(
            SlotOverride(
                name=slot.name,
                colour=slot.colour,
                temperature=temperature,
            ),
        ),
    )
    setup = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")

    config = handover.write_config(settings, profile, setup, tmp_path, (slot,))

    written = json.loads(config.filaments[0].read_text(encoding="utf-8"))
    assert written["nozzle_temperature"] == ["215"], "die sichtbare Spulenwahl gewinnt"
    assert written["filament_max_volumetric_speed"] == ["21"], (
        "nicht geänderte Gruppen bleiben beim Herstellerprofil"
    )


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
    """``subprocess.run`` warf einen rohen
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


def test_slicing_without_a_model_offers_nothing_to_install(tmp_path: Path) -> None:
    """Regel 17 heißt nicht „irgendein Knopf".

    Beide Fehler erbten die Vorschläge von :class:`ExternalToolError`, und der
    erste davon heißt „Zusätzliche Programme …". Es fehlt hier aber kein
    Programm: Übergeben wurde nichts, beziehungsweise die Datei ist weg. Wer
    dem Knopf folgt, landet in einer Liste, die mit seinem Fehler nichts zu
    tun hat.
    """
    profile = profiles.make_profile()
    setup = handover.SlicerSetup(executable=tmp_path / "cura.exe", flavour="cura")

    with pytest.raises(ExternalToolError) as leer:
        handover.slice_model([], print_settings.resolve(profile), profile, setup)
    assert leer.value.suggestions
    assert "install" not in {action.id for action in leer.value.suggestions}
    assert "change_selection" in {action.id for action in leer.value.suggestions}

    with pytest.raises(ExternalToolError) as weg:
        handover.slice_model(
            tmp_path / "verschwunden.stl", print_settings.resolve(profile), profile, setup
        )
    assert "install" not in {action.id for action in weg.value.suggestions}
    assert "retry" in {action.id for action in weg.value.suggestions}


def test_a_semicolon_in_a_profile_path_is_refused_before_the_slicer_sees_it(
    tmp_path: Path,
) -> None:
    """``--load-settings`` trennt seine Profile mit Semikolon.

    Ein Semikolon im Pfad macht aus einem Profil zwei, und der Slicer
    antwortet mit „can not find setting file" auf einen Pfad, den es so nie
    gab. Ein Maskierungsweg ist für diesen Schalter nirgends zugesagt — also
    wird die Lage benannt, statt sie zu raten.
    """
    heikel = tmp_path / "ma;schine.json"
    heikel.write_text("{}", encoding="utf-8")
    setup = handover.SlicerSetup(
        executable=tmp_path / "orca.exe", flavour="orca", machine_profile=str(heikel)
    )
    config = handover.SlicerConfig(process=tmp_path / "prozess.json")

    with pytest.raises(ExternalToolError) as caught:
        handover._command(setup, [tmp_path / "platte.3mf"], config, tmp_path)

    assert ";" in str(caught.value.values.get("path", "")), "der Pfad, um den es geht"
    assert caught.value.suggestions, "Regel 17"

    harmlos = tmp_path / "maschine.json"
    harmlos.write_text("{}", encoding="utf-8")
    gut = handover.SlicerSetup(
        executable=tmp_path / "orca.exe", flavour="orca", machine_profile=str(harmlos)
    )
    assert "--load-settings" in handover._command(gut, [tmp_path / "p.3mf"], config, tmp_path)


def test_the_print_file_we_asked_for_beats_a_stranger_in_the_folder(tmp_path: Path) -> None:
    """§22.5: Kennzahlen sind nur etwas wert, wenn sie aus *dieser* Datei
    kommen.

    Prusa und Cura schreiben dorthin, wohin Solidon zeigt, und unter dem
    Namen, den Solidon nennt. Gesucht wurde trotzdem nur nach Endung, und die
    jüngste gewann — in einem Zielordner des Nutzers ist das die Datei eines
    fremden Programms, und ihre Zahlen standen dann im Prüfbericht.
    """
    import os

    unser = tmp_path / handover.OUTPUT_NAME
    unser.write_text("G1 X1 Y1 E1\n", encoding="utf-8")
    fremd = tmp_path / "irgendwas.gcode"
    fremd.write_text("G1 X2 Y2 E2\n", encoding="utf-8")
    spaeter = unser.stat().st_mtime + 60.0
    os.utime(fremd, (spaeter, spaeter))

    assert handover._find_gcode(tmp_path, handover.OUTPUT_NAME) == unser
    assert handover._find_gcode(tmp_path) == fremd, "wo der Slicer selbst benennt, die jüngste"

    unser.unlink()
    assert handover._find_gcode(tmp_path, handover.OUTPUT_NAME) == fremd, "Rückfall bleibt"


def test_the_slicer_run_reads_back_the_file_it_asked_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Und die Anschlussprüfung dazu: nicht „``_find_gcode`` kann es", sondern
    „der Lauf tut es"."""
    import os

    profile = profiles.make_profile()
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    executable = tmp_path / "cura.exe"
    executable.write_bytes(b"")

    def _writes(*_args: object, **_kwargs: object) -> _Finished:
        (tmp_path / handover.OUTPUT_NAME).write_text(
            _gcode_printing_at(-10.0, 10.0), encoding="utf-8"
        )
        fremd = tmp_path / "fremd.gcode"
        fremd.write_text(_gcode_printing_at(400.0), encoding="utf-8")
        spaeter = fremd.stat().st_mtime + 60.0
        os.utime(fremd, (spaeter, spaeter))
        return _Finished(b"")

    monkeypatch.setattr(handover, "_run_slicer", _writes)
    setup = handover.SlicerSetup(executable=executable, flavour="cura")

    outcome = handover.slice_model(
        model, print_settings.resolve(profile), profile, setup, output_dir=tmp_path
    )

    assert outcome.gcode_path.name == handover.OUTPUT_NAME


def test_a_print_file_that_cannot_be_kept_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne ``output_dir`` verschwindet der Arbeitsordner, und die Druckdatei
    wandert neben das Modell. Ging das nicht, flog ein roher ``OSError`` —
    aus einem Arbeits-Thread, der nur ``AppError`` fängt.
    """
    from app.core.errors import FileWriteError

    profile = profiles.make_profile()
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    (tmp_path / "model.gcode").mkdir()  # der Platz ist belegt, und zwar von einem Ordner
    executable = tmp_path / "cura.exe"
    executable.write_bytes(b"")

    def _writes(*args: object, **_kwargs: object) -> _Finished:
        workspace = args[1]
        assert isinstance(workspace, Path)
        (workspace / handover.OUTPUT_NAME).write_text(
            _gcode_printing_at(-10.0, 10.0), encoding="utf-8"
        )
        return _Finished(b"")

    monkeypatch.setattr(handover, "_run_slicer", _writes)
    setup = handover.SlicerSetup(executable=executable, flavour="cura")

    with pytest.raises(FileWriteError) as caught:
        handover.slice_model(model, print_settings.resolve(profile), profile, setup)

    assert caught.value.suggestions, "Regel 17"


def test_an_unknown_material_is_reported_not_silent() -> None:
    """Regel 21: `_material_table` fällt mit Absicht still auf die
    Modellvorgaben zurück — der Satz an den Nutzer fehlte: ein selbst
    angelegtes Material druckt sonst mit PLA-nahen Werten, ohne dass es
    irgendwo steht."""
    from dataclasses import replace as dc_replace

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    unknown = dc_replace(profile, material=dc_replace(profile.material, id="eigenes-filament"))
    settings = print_settings.resolve(unknown)

    codes = {entry.code for entry in advise.warnings_for(settings, unknown)}

    assert "settings.material_without_profile" in codes
    known_codes = {entry.code for entry in advise.warnings_for(settings, profile)}
    assert "settings.material_without_profile" not in known_codes


def test_without_a_slicer_the_dialog_offers_a_way_to_one(
    qt_app: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regel 17 an der Stelle, an der jemand gerade slicen wollte.

    „Kein Slicer eingerichtet — die Einstellungen lassen sich trotzdem
    pflegen." sagte, was fehlt, und bot nichts an. Der Satz bleibt (§27: das
    Backend meldet sich ab, es nörgelt nicht), der Weg kommt dazu.
    """
    from app.core import discover
    from app.ui.print_settings_dialog import PrintSettingsDialog
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    monkeypatch.setattr(discover, "find_program", lambda *_args: None)
    monkeypatch.setattr(discover, "find_programs", lambda *_args: ())
    dialog = PrintSettingsDialog(Session(), UiSettings())

    assert not dialog.slice_button.isEnabled(), "ohne Slicer gibt es nichts zu starten"
    assert not dialog.setup_button.isHidden(), "aber einen Weg zu einem"
    assert "Kein Slicer" in dialog.state.text()

    asked: list[bool] = []
    dialog.setupRequested.connect(lambda: asked.append(True))
    dialog.setup_button.click()

    assert asked == [True]


def test_a_slot_profile_follows_its_slot_across_plates(qt_app: object, tmp_path: Path) -> None:
    """Das Profil gehört dem Filament, nicht der Zeilennummer (§20).

    Angezeigt wird die Zusammenlegung der gewählten Platten, gedruckt wird
    Platte für Platte, und jede legt für sich zusammen. Bei „Alle Platten"
    mit Rot auf Platte 1 und Weiß+Rot auf Platte 2 stand deshalb
    [Rot, Weiß] im Dialog und [Weiß, Rot] im Lauf der zweiten Platte —
    positionsweise zugeordnet bekam **Weiß das Rot-Profil**, und mit dem
    Profil wandert die Temperatur (Fund 26.08.2026, am Lauf gemessen).

    Die Gegenprobe steht im Test mit drin: Positionsweise wäre die
    Zuordnung vertauscht, und genau das darf sie nicht mehr sein.
    """
    from types import SimpleNamespace

    import trimesh

    from app.core.export import handover
    from app.core.geom.mesh import MeshData
    from app.core.types import MaterialSlot, SceneObject
    from app.ui.print_settings_dialog import PrintSettingsDialog
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    dialog = PrintSettingsDialog(Session(), UiSettings())

    box = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    rot = MaterialSlot(index=0, name="Rot")
    weiss = MaterialSlot(index=0, name="Weiß")
    erste = SceneObject(id="A", name="A", mesh=box, material_slots=[rot], plate=0)
    zweite = SceneObject(id="B", name="B", mesh=box, material_slots=[weiss, rot], plate=1)
    dialog.session.last_result = SimpleNamespace(
        scene=SimpleNamespace(objects={"A": erste, "B": zweite})
    )
    # Was der Kunde bei „Alle Platten" sieht und zuordnet: Rot, dann Weiß.
    assert [str(slot.name) for slot in dialog._plate_slots()] == ["Rot", "Weiß"]
    dialog.settings = replace(dialog.settings, slot_profiles=("Rotes PLA", "Weißes PLA"))
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")

    run = dialog._plate_run([erste, zweite], 1, tmp_path, "satz", setup)

    gewählt = {str(slot.name): slot.material for slot in run.slots}
    assert gewählt == {"Weiß": "Weißes PLA", "Rot": "Rotes PLA"}
    assert [str(slot.name) for slot in run.slots] == ["Weiß", "Rot"], (
        "die Reihenfolge des Laufs ist eine andere — daran hing der Fehler"
    )


def test_a_slicer_that_arrived_is_picked_up_without_reopening(
    qt_app: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Wer einen Slicer gerade installiert hat, soll nicht schließen müssen.

    Gemessen mit einem PrusaSlicer, nicht mit der Orca-Familie: Die verlangt
    seit dem Profil-Wächter zu Recht erst eine Profilwahl, und ihr Knopf
    bliebe hier grau — dann prüfte dieser Test zwei Zusagen auf einmal und
    keine sauber. Das Aufgreifen misst sich an einem Slicer ohne
    Profilpflicht; den Wächter der Orca-Familie hält
    ``tests/test_print_settings_ui.py`` fest.
    """
    from app.core import discover
    from app.ui.print_settings_dialog import PrintSettingsDialog
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    monkeypatch.setattr(discover, "find_program", lambda *_args: None)
    monkeypatch.setattr(discover, "find_programs", lambda *_args: ())
    dialog = PrintSettingsDialog(Session(), UiSettings())
    assert not dialog.slice_button.isEnabled()

    program = tmp_path / "prusa-slicer.exe"
    program.write_text("")
    monkeypatch.setattr(discover, "find_program", lambda *_args: program)
    monkeypatch.setattr(discover, "find_programs", lambda *_args: (program,))

    dialog.recheck_slicer()

    assert dialog.slice_button.isEnabled(), "jetzt gibt es einen"
    assert dialog.setup_button.isHidden(), "und nichts mehr zu holen"


def test_a_wall_below_one_nozzle_line_becomes_a_finding_not_a_suggestion() -> None:
    """Unter einer schmalsten Bahn der Düse behebt keine Einstellung mehr etwas.

    Die Bahnbreiten-Regel senkt höchstens bis ``NARROW_LINE_SHARE`` mal
    Düsendurchmesser — darunter blieb bisher ein Vorschlag stehen, der die
    Stelle weiter wegfallen ließ, und der eigentliche Ausweg (kleinere Düse
    oder breitere Wand) stand nirgends. Nach der Doktrin aus
    ``schichtanalyse.md`` gehört dorthin ein Befund: Was kein Wert behebt,
    wird ein Finding (Roberts Auftrag vom 26.08.2026, „Düse als Empfehlung").
    """
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    least = advise.NARROW_LINE_SHARE * profile.printer.nozzle_diameter
    result = _layers(500.0, 500.0, 500.0, min_width=least * 0.8)

    findings = advise.warnings_for(settings, profile, result)
    hits = [entry for entry in findings if entry.code == "settings.wall_below_nozzle"]

    assert hits, "eine Wand unter einer Bahnbreite gehört gesagt"
    assert hits[0].severity == "warning"
    assert hits[0].values["nozzle_mm"] == pytest.approx(profile.printer.nozzle_diameter)
    assert hits[0].values["width_mm"] == pytest.approx(least * 0.8)
    assert hits[0].values["least_mm"] == pytest.approx(least)
    assert hits[0].source == "internal"

    # Und der Vorschlag daneben verschwindet: Eine Bahnbreite, die die Stelle
    # trotzdem verliert, ist kein Vorschlag (dieselbe Doktrin, andere Hälfte).
    entries = advise.advise(settings, profile, result)
    assert not [entry for entry in entries if entry.path == "layers.line_width"], (
        "unter der Düsengrenze darf keine Bahnbreite mehr vorgeschlagen werden"
    )


def test_a_wall_the_nozzle_can_print_is_not_that_finding() -> None:
    """Die Gegenrichtung, sonst warnte der Bericht an jedem gesunden Teil."""
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    least = advise.NARROW_LINE_SHARE * profile.printer.nozzle_diameter
    result = _layers(500.0, 500.0, 500.0, min_width=least * 1.5)

    codes = {entry.code for entry in advise.warnings_for(settings, profile, result)}
    assert "settings.wall_below_nozzle" not in codes


def test_what_can_be_opened_can_also_be_found() -> None:
    """Der Öffnen-Dialog und die Suche im Ausgabeordner meinen dieselbe Menge.

    Die Endungen standen zweimal: im Kern (`handover`), der nach dem Lauf die
    erzeugte Druckdatei sucht, und in der Oberfläche, die den Dateifilter
    baut. Sie liefen auseinander — der Filter kannte `.nc`, die Suche nicht.
    Ein Slicer, der eine `.nc` schreibt, wäre damit unauffindbar gewesen, und
    der Kunde hätte „Der Slicer hat keine Druckdatei geschrieben." gelesen,
    während die Datei danebenlag (gefunden am 27.08.2026).

    Zwei Stellen, die dieselbe Frage beantworten, und nur eine wird gepflegt —
    dasselbe Muster wie bei `setdefault` gegen `merged_slots` und bei den
    beiden Parameterart-Tabellen. Der Test hält jetzt fest, dass es **eine**
    Menge ist, nicht zwei gleiche.
    """
    from app.ui.main_window import GCODE_SUFFIXES as AUS_DER_OBERFLAECHE

    assert AUS_DER_OBERFLAECHE is handover.GCODE_SUFFIXES, (
        "die Oberfläche holt die Endungen aus dem Kern, statt sie zu wiederholen"
    )
    assert ".nc" in handover.GCODE_SUFFIXES, "und die längere der beiden Listen gewinnt"


#: Feld/Slicer-Paare, bei denen eine Einstellung den Slicer **nicht** erreicht —
#: und der Grund, warum das richtig ist.
#:
#: Gemessen am 27.08.2026 auf Roberts Architekturauftrag zu den Zwillingen. Die
#: drei Slicer-Familien sind das teuerste Zwillingspaar des Projekts: 24
#: Verzweigungen über `flavour`, und die Übersetzung lebt an **zwei** Orten —
#: in `slicer_keys.TABLES` und in den Sonderfällen von `handover` (Haftung,
#: Stützabstand, Cura-Ableitungen). Eine Lücke in der Tabelle ist deshalb noch
#: kein Befund; erst die echte Ausgabe sagt es.
#:
#: Jeder Eintrag hier ist eine Zusage: *Dieses Feld erreicht diesen Slicer
#: nicht, und das ist in Ordnung.* Wer einen hinzufügt, schreibt den Grund
#: dazu — eine Ausnahmeliste ohne Gründe wird zur Halde.
UNREACHED: Final[dict[tuple[str, str], str]] = {
    ("shell.wall_generator", "cura"): (
        "CuraEngine wählt den Wandgenerator nicht über einen Schalter: Arachne "
        "ist seit 5.0 der einzige Weg, und die Klassik gibt es dort nicht mehr."
    ),
    ("shell.precise_outer_wall", "prusa"): (
        "Die genaue Außenwand ist eine Eigenheit der Orca-Familie; PrusaSlicer "
        "kennt keinen entsprechenden Schalter."
    ),
    ("shell.precise_outer_wall", "cura"): (
        "Dasselbe für CuraEngine — dort heißt der nächste Verwandte "
        "``outer_inset_first`` und meint die Reihenfolge, nicht das Maß."
    ),
    ("retraction.wipe", "cura"): (
        "CuraEngine wischt nicht auf Anweisung, sondern über das Einzugsmuster; "
        "ein eigener Schalter dafür existiert nicht."
    ),
    ("filament.density", "cura"): (
        "Dichte und Preis dienen der Verbrauchsschätzung, und die rechnet "
        "Solidon selbst aus dem G-Code (§22.5). CuraEngine nimmt sie nicht "
        "entgegen; sie zum Slicer zu tragen brächte niemandem etwas."
    ),
    ("filament.cost_per_kg", "cura"): "Wie die Dichte darüber — Solidon rechnet, nicht der Slicer.",
}


def _read_path(settings: object, path: str) -> object:
    obj: object = settings
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


def _with_value(settings: Any, path: str, value: object) -> Any:
    group, _, name = path.partition(".")
    return replace(settings, **{group: replace(getattr(settings, group), **{name: value})})


def _another_value(current: object, choices: tuple[str, ...]) -> object | None:
    """Ein anderer **gültiger** Wert — bei Auswahlfeldern aus ihren Werten.

    Der erste Anlauf setzte überall dieselbe Zeichenkette, auch in
    ``infill.pattern`` und ``support.placement``: Die Übersetzung fand den
    Wert nicht, schrieb nichts, und die Messung meldete zehn taube Felder,
    die keine waren. Ein Prüfstand, der ungültige Werte einsetzt, misst seine
    eigene Untauglichkeit.
    """
    if choices:
        other = [entry for entry in choices if entry != current]
        return other[0] if other else None
    if isinstance(current, bool):
        return not current
    if isinstance(current, (int, float)):
        return type(current)(current + 1) if current < 90 else type(current)(current - 1)
    return None


def test_every_setting_reaches_every_slicer_or_stands_in_the_list() -> None:
    """Ein Feld, das der Dialog anbietet, wirkt — oder es steht hier, warum nicht.

    Der Kunde stellt 56 Werte ein und kann keinem ansehen, ob sein Slicer ihn
    versteht. Bis heute fehlte die Zusicherung dazu ganz: ``support.density``
    stand nur in der Cura-Tabelle und erreichte PrusaSlicer und die
    Orca-Familie erst über eine Umrechnung, die jemand von Hand nachgetragen
    hat — bemerkt hat es niemand, weil nichts danach fragte.

    Gemessen wird an der **echten Ausgabe** (`values_for`), nicht an der
    Tabelle: Die Übersetzung lebt an zwei Orten, und wer nur die Tabelle liest,
    meldet sechs Lücken, die längst geschlossen sind. Geändert wird je Feld ein
    gültiger Wert; ändert sich daraufhin kein einziger Schlüssel dieses
    Slicers, kommt die Einstellung dort nicht an.
    """
    from app.ui.print_settings_dialog import FIELDS

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    base = print_settings.resolve(profile)
    unreached: list[tuple[str, str]] = []
    for field in FIELDS:
        current = _read_path(base, field.path)
        value = _another_value(current, field.choices)
        if value is None or value == current:
            continue
        # Haftungsabhängige Felder wirken nur unter ihrer Art — sonst misst
        # man die Bedingung statt des Feldes.
        start = base
        art = {
            "brim_width": "brim",
            "raft_layers": "raft",
            "skirt_loops": "skirt",
            "skirt_distance": "skirt",
        }.get(field.path.partition(".")[2] if field.path.startswith("adhesion.") else "")
        if art:
            start = _with_value(base, "adhesion.kind", art)
        changed = _with_value(start, field.path, value)
        for flavour in ("prusa", "orca", "cura"):
            if handover.values_for(start, profile, flavour) == handover.values_for(
                changed, profile, flavour
            ):
                unreached.append((field.path, flavour))

    assert unreached, "keine Messung gelaufen — die Grundmenge ist leer"
    neu = [pair for pair in unreached if pair not in UNREACHED]
    weg = [pair for pair in UNREACHED if pair not in unreached]
    assert not neu, "Einstellungen ohne Wirkung und ohne Begründung: " + str(sorted(neu))
    assert not weg, "steht als unerreichbar in der Liste, wirkt aber: " + str(sorted(weg))


def test_the_dialog_writes_time_and_mass_like_the_status_line() -> None:
    """Eine Sitzung, eine Schreibweise für dieselbe Größe.

    Gemessen am 27.08.2026: Die Statuszeile sagte „10 h 5 min" und „18 g", der
    Druckdialog für dieselben Werte „605 min" und „18,4 g". Zwei Stellen, die
    beide entschieden, wie eine Dauer und eine Masse aussehen — und `min` und
    `g` standen im Dialog als feste Zeichenketten, obwohl `facts.py` sie
    ausdrücklich durch `tr()` schickt (Regel 20).

    Geprüft wird die Quelle, nicht das Fenster: Was der Dialog daraus baut,
    ist eine Zeile mit Doppelpunkt davor, und die Zahl darin kommt seit dem
    Umbau aus derselben Funktion wie die der Statuszeile.
    """
    from app.ui.facts import duration, mass

    assert duration(605 * 60.0) == "10 h 5 min", "über einer Stunde in Stunden und Minuten"
    assert duration(90 * 60.0) == "1 h 30 min"
    # Über zehn Gramm ohne Nachkommastelle — bei einer Schätzung ist „18,4 g"
    # dieselbe Aussage wie „18 g", und die kürzere liest sich im Vorbeigehen.
    assert mass(18.44) == "18 g"
    assert mass(250.0) == "250 g"


def test_several_slicers_become_a_choice(
    qt_app: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Wer drei Slicer installiert hat, soll wählen können.

    Bis zum 30.08.2026 entschied die Suchreihenfolge: ``find_program`` hört
    beim ersten Treffer auf. Auf dieser Maschine fand sie ElegooSlicer und
    bot PrusaSlicer und Cura nicht an, obwohl beide danebenstanden — und als
    ElegooSlicers Kommandozeile nicht slicen wollte, war das eine Sackgasse
    statt einer Wahl (Robert: „auswahl bei mehreren slicern wäre auch
    sinnvoll").

    Geprüft wird beides: dass drei zu einer Auswahl werden **und** dass einer
    keine wird. Eine Zeile mit einem einzigen Eintrag ist eine Frage ohne
    Antwortmöglichkeit (§2.4) — ohne die zweite Hälfte wäre der Test auch
    grün, wenn das Feld immer erschiene.
    """
    from app.core import discover
    from app.ui.print_settings_dialog import PrintSettingsDialog
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    drei = tuple(
        tmp_path / name / f"{name}.exe" for name in ("ElegooSlicer", "PrusaSlicer", "Cura")
    )
    for entry in drei:
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_bytes(b"")

    monkeypatch.setattr(discover, "remembered_path", lambda _tool: "")
    monkeypatch.setattr(discover, "find_program", lambda *_args: drei[0])

    monkeypatch.setattr(discover, "find_programs", lambda *_args: drei)
    dialog = PrintSettingsDialog(Session(), UiSettings())
    assert dialog.slicer_choice.count() == 3, "drei Slicer, drei Zeilen"
    assert [dialog.slicer_choice.itemText(i) for i in range(3)] == [
        "ElegooSlicer",
        "PrusaSlicer",
        "Cura",
    ], "benannt nach dem Installationsordner, nicht nach der Datei"
    assert dialog._slicer_path == drei[0]

    monkeypatch.setattr(discover, "find_programs", lambda *_args: drei[:1])
    einer = PrintSettingsDialog(Session(), UiSettings())
    assert einer.slicer_choice.count() == 1
    assert not einer.slicer_choice.isVisibleTo(einer), "bei einem gibt es nichts zu wählen"


def test_choosing_another_slicer_drops_the_profiles_of_the_old_one(
    qt_app: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ein Wechsel nimmt die Profile nicht mit.

    Maschinen- und Prozessprofil gehören dem Slicer, aus dessen Bestand sie
    stammen. Ein Elegoo-Druckerprofil an PrusaSlicer zu reichen wäre kein
    Fehler, den jemand sähe — der Slicer lehnte still ab oder rechnete mit
    etwas anderem, als im Feld steht.
    """
    from app.core import discover
    from app.ui.print_settings_dialog import PrintSettingsDialog
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    zwei = tuple(tmp_path / name / f"{name}.exe" for name in ("ElegooSlicer", "PrusaSlicer"))
    for entry in zwei:
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_bytes(b"")

    gemerkt: list[str] = []
    monkeypatch.setattr(discover, "remembered_path", lambda _tool: "")
    monkeypatch.setattr(discover, "find_program", lambda *_args: zwei[0])
    monkeypatch.setattr(discover, "find_programs", lambda *_args: zwei)
    monkeypatch.setattr(discover, "remember_path", lambda _tool, value: gemerkt.append(value))

    dialog = PrintSettingsDialog(Session(), UiSettings())
    dialog.machine_choice.addItem("Elegoo Centauri Carbon 2 0.4 nozzle")
    dialog.process_choice.addItem("0.20mm Standard @Elegoo CC2 0.4 nozzle")

    dialog._slicer_chosen(1)

    assert dialog._slicer_path == zwei[1], "der gewählte gilt"
    assert gemerkt == [str(zwei[1])], "und er wird gemerkt"
    assert dialog.machine_choice.count() == 0, "das Druckerprofil des alten ist weg"
    assert dialog.process_choice.count() == 0, "das Prozessprofil auch"
