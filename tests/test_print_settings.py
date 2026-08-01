"""Druckeinstellungen, Empfehlung und Slicer-Übergabe (Bauplan §29, §28).

Drei Sachen, die zusammengehören: Formwerk hält die Einstellungen, die
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


def _layers(*areas: float, overhang: float = 0.0, islands: bool = False) -> SliceResult:
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
            min_width=5.0,
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

    paths = [entry.path for entry in advise.advise(settings, profile, has_fits=True)]

    assert len(paths) == len(set(paths))


def test_a_heated_chamber_gets_used_when_it_is_there() -> None:
    profile = profiles.make_profile("bambu-x1c", "abs")
    settings = print_settings.with_path(print_settings.resolve(profile), "temperature.chamber", 0)

    entries = advise.advise(settings, profile)

    chamber = next(entry for entry in entries if entry.path == "temperature.chamber")
    assert int(chamber.value) > 0  # type: ignore[call-overload]


def test_the_flow_limit_reaches_the_slicer() -> None:
    """Die Zahl gehört ins Filamentprofil — dort setzt der Slicer sie durch,
    auch für die Wege, die Formwerk nicht einzeln einstellt."""
    settings = print_settings.resolve(profiles.make_profile("prusa-mk4s", "tpu-95a"))

    for flavour in ("prusa", "orca"):
        written = handover.as_mapping(settings, flavour)  # type: ignore[arg-type]
        assert written["filament_max_volumetric_speed"] == "3.5"


def test_fits_slow_the_outer_wall_down() -> None:
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)

    entries = advise.advise(settings, profile, has_fits=True)

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
    for path, key, _convert in slicer_keys.TABLES[flavour]:  # type: ignore[index]
        print_settings.read_path(settings, path)
        assert key, f"{path} hat keinen Namen beim Slicer"


@pytest.mark.parametrize("flavour", ["prusa", "orca", "cura"])
def test_the_core_settings_reach_every_slicer(flavour: str) -> None:
    """Was die Oberfläche anbietet, muss überall ankommen — sonst stellt der
    Nutzer etwas ein, das für seinen Slicer folgenlos bleibt."""
    covered = {path for path, _key, _convert in slicer_keys.TABLES[flavour]}  # type: ignore[index]
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
    """Formwerk rechnet in 0…1, die Slicer in 0…100 — die Stelle, an der ein
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
    assert handover.as_mapping(settings, "cura")["support_enable"] == "true"


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
    text = written.read_text(encoding="utf-8")

    assert "bed_shape" in text
    assert "nozzle_diameter" in text
    assert f"layer_height = {settings.layers.layer_height:g}" in text


def test_an_orca_process_keeps_what_the_base_profile_knew(tmp_path: Path) -> None:
    """Die Orca-Familie prüft Verträglichkeit gegen den Drucker. Was Formwerk
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
    document = json.loads(written.read_text(encoding="utf-8"))

    assert document["compatible_printers"] == ["Irgendein Drucker 0.4 nozzle"]
    assert document["wall_loops"] == str(settings.shell.wall_count)


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
