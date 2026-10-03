"""Curas Lüfterkurve bleibt bei Cura (RM-228).

Solidons Materialtabelle führt die Lüfterkurve eines Herstellers — PLA 50 bis
100 % mit der Schwelle bei 80 s, wie Elegoos Profil für den Centauri Carbon 2.
Bei der Orca-Familie und PrusaSlicer liegt darunter das Filamentprofil des
Herstellers, und die Tabelle geht nur auf ausdrückliche Wahl hinaus. Cura
bekam sie dagegen ganz: ``cool_min_layer_time_fan_speed_max = 80`` ließ Cura
jede erste Schicht unter 80 s hochkühlen (Okarina 49 % in Schicht 1 trotz
Pause), wo Curas eigene Definition 10 s und kein unteres Ende unter dem
oberen nennt (``cool_fan_speed_min = cool_fan_speed``).

Entscheidung (Konsolidierung 03.10.2026, Robert: „Druckrat als Vorschlag,
Herstellerprofil maßgeblich“): Unteres Ende und Schwelle kommen bei Cura aus
der Druckerdefinition; eine eigene Wahl bleibt die eigene Wahl. Das obere
Ende bleibt Solidons Materialwert, denn die Konsole bekommt kein
Cura-Materialprofil, und ``fdmprinter`` nennt für jedes Material 100 %.
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from app.core.export import handover, manufacturer
from app.core.knowledge import print_settings, profiles
from app.core.types import MaterialSlot


def _cura(tmp_path: Path, *, printer_threshold: float | None = None) -> Path:
    """Eine Cura-Installation mit ``fdmprinter`` (Kühlung wie Cura 5.13) und
    der Definition des Ender-3 V3 SE."""
    install = tmp_path / "UltiMaker Cura 5.13.0"
    definitions = install / "share" / "cura" / "resources" / "definitions"
    definitions.mkdir(parents=True)
    cooling = {
        "cool_fan_speed": {"default_value": 100, "value": "100.0 if cool_fan_enabled else 0.0"},
        "cool_fan_speed_min": {"default_value": 100, "value": "cool_fan_speed"},
        "cool_fan_speed_max": {"default_value": 100, "value": "cool_fan_speed"},
        "cool_min_layer_time_fan_speed_max": {"default_value": 10},
        "cool_min_layer_time": {"default_value": 5},
    }
    (definitions / "fdmprinter.def.json").write_text(
        json.dumps(
            {
                "version": 2,
                "name": "FFF",
                "metadata": {"setting_version": 27},
                "settings": {"cooling": {"children": cooling}},
            }
        ),
        encoding="utf-8",
    )
    overrides: dict[str, object] = {"cool_min_layer_time": {"value": 10}}
    if printer_threshold is not None:
        overrides["cool_min_layer_time_fan_speed_max"] = {"default_value": printer_threshold}
    (definitions / "creality_ender3v3se.def.json").write_text(
        json.dumps(
            {
                "version": 2,
                "name": "Creality Ender-3 V3 SE",
                "inherits": "fdmprinter",
                "overrides": overrides,
            }
        ),
        encoding="utf-8",
    )
    engine = install / "CuraEngine.exe"
    engine.write_bytes(b"")
    return engine


def _foundation(engine: Path, material: str = "pla") -> manufacturer.Foundation:
    profile = profiles.make_profile("creality-ender3-v3-se", material)
    return manufacturer.base_settings(profile, "standard", handover.SlicerSetup(engine, "cura"))


def test_the_table_carries_a_curve_cura_does_not_have() -> None:
    """Die Voraussetzung des Befunds: Ohne Slicer bleibt die Tabelle, wie sie ist."""
    profile = profiles.make_profile("creality-ender3-v3-se", "pla")
    cooling = manufacturer.base_settings(profile, "standard", None).settings.cooling
    assert cooling.minimum_fan_speed == pytest.approx(0.5)
    assert cooling.fan_below_layer_time == pytest.approx(80.0)


@pytest.mark.parametrize(("printer_threshold", "expected"), [(None, 10.0), (15.0, 15.0)])
def test_cura_keeps_its_own_threshold_and_no_lower_end(
    tmp_path: Path, printer_threshold: float | None, expected: float
) -> None:
    """Die Schwelle aus der Erbkette des Druckers, das untere Ende nach Curas
    Formel gleich dem oberen — im Dialog wie in der Konsole."""
    engine = _cura(tmp_path, printer_threshold=printer_threshold)
    foundation = _foundation(engine)
    cooling = foundation.settings.cooling
    assert cooling.fan_below_layer_time == pytest.approx(expected)
    assert cooling.minimum_fan_speed == pytest.approx(cooling.fan_speed)

    profile = profiles.make_profile("creality-ender3-v3-se", "pla")
    written = handover.values_for(manufacturer.effective(None, foundation), profile, "cura")
    assert written["cool_min_layer_time_fan_speed_max"] == f"{expected:g}"
    assert written["cool_fan_speed_min"] == written["cool_fan_speed"] == "100"


def test_petg_keeps_its_upper_end_and_follows_it_below(tmp_path: Path) -> None:
    """Das obere Ende bleibt der Materialwert (PETG 50 %), das untere folgt ihm."""
    cooling = _foundation(_cura(tmp_path), "petg").settings.cooling
    table = print_settings.resolve(profiles.make_profile("creality-ender3-v3-se", "petg")).cooling
    assert cooling.fan_speed == pytest.approx(table.fan_speed)
    assert cooling.minimum_fan_speed == pytest.approx(table.fan_speed)
    assert cooling.fan_below_layer_time == pytest.approx(10.0)


def test_an_own_choice_stays_the_own_choice(tmp_path: Path) -> None:
    """Wer die Kurve im Dialog setzt, bekommt sie — über Cura wie überall."""
    engine = _cura(tmp_path)
    foundation = _foundation(engine)
    chosen = print_settings.with_choice(foundation.settings, "cooling.fan_below_layer_time", 80.0)
    chosen = print_settings.with_choice(chosen, "cooling.minimum_fan_speed", 0.5)
    effective = manufacturer.effective(chosen, foundation)
    profile = profiles.make_profile("creality-ender3-v3-se", "pla")
    written = handover.values_for(effective, profile, "cura")
    assert written["cool_min_layer_time_fan_speed_max"] == "80"
    assert written["cool_fan_speed_min"] == "50"


def test_an_unreadable_installation_falls_back_to_curas_documented_values(
    tmp_path: Path,
) -> None:
    """Ohne lesbare Definition gelten Curas Grundwerte — nicht die Tabelle."""
    engine = tmp_path / "Cura" / "CuraEngine.exe"
    engine.parent.mkdir()
    engine.write_bytes(b"")
    cooling = _foundation(engine).settings.cooling
    assert cooling.fan_below_layer_time == pytest.approx(manufacturer.CURA_FAN_THRESHOLD)
    assert cooling.minimum_fan_speed == pytest.approx(cooling.fan_speed)


def test_a_second_material_on_cura_follows_the_same_rule(tmp_path: Path) -> None:
    """Eine PETG-Spule in einem PLA-Projekt bekommt die Kurve von Cura, nicht
    PETGs Tabellenkurve 50/20 % bei 30 s."""
    engine = _cura(tmp_path)
    setup = handover.SlicerSetup(engine, "cura")
    profile = profiles.make_profile("creality-ender3-v3-se", "pla")
    settings = manufacturer.effective(None, _foundation(engine))
    slot = MaterialSlot(index=1, name="PETG", material_type="PETG")
    cooling = handover.settings_for_slot(settings, profile, slot, setup).cooling
    assert cooling.fan_speed == pytest.approx(0.5)
    assert cooling.minimum_fan_speed == pytest.approx(0.5)
    assert cooling.fan_below_layer_time == pytest.approx(10.0)


def test_the_orca_and_prusa_paths_are_untouched(tmp_path: Path) -> None:
    """Die Regel gilt Cura; ohne Herstellerprozess behalten die anderen
    Familien Solidons ganzen Satz, wie bisher (``slicer.filament_from_table``)."""
    engine = _cura(tmp_path)
    profile = profiles.make_profile("creality-ender3-v3-se", "pla")
    for flavour in ("orca", "prusa"):
        setup = handover.SlicerSetup(engine.with_name(f"{flavour}.exe"), flavour)  # type: ignore[arg-type]
        cooling = manufacturer.base_settings(profile, "standard", setup).settings.cooling
        assert cooling.minimum_fan_speed == pytest.approx(0.5), flavour
        assert cooling.fan_below_layer_time == pytest.approx(80.0), flavour


def _window_values(target: Path) -> dict[str, str]:
    with zipfile.ZipFile(target.with_suffix(handover.CURA_PROFILE_SUFFIX)) as archive:
        body = archive.read("solidon").decode("utf-8")
    values = body.split("[values]", 1)[1]
    pairs = (line.partition("=") for line in values.splitlines() if "=" in line)
    return {key.strip(): value.strip() for key, _sep, value in pairs}


def test_the_cura_window_keeps_its_own_curve(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das Fenster rechnet unteres Ende und Schwelle selbst (Formel und
    Qualitätsstufe); das importierte Profil nennt sie nur als eigene Wahl."""
    engine = _cura(tmp_path)
    setup = handover.SlicerSetup(engine, "cura")
    profile = profiles.make_profile("creality-ender3-v3-se", "pla")
    active = handover.slicer_profiles.CuraActiveMachine(
        name="Ender",
        definition=engine.parent
        / "share"
        / "cura"
        / "resources"
        / "definitions"
        / "creality_ender3v3se.def.json",
    )
    monkeypatch.setattr(handover.slicer_profiles, "cura_active_machine", lambda _exe: active)
    monkeypatch.setattr(
        handover.slicer_profiles, "cura_quality_types", lambda *_a, **_k: {"standard": 0.2}
    )
    monkeypatch.setattr(handover.slicer_profiles, "cura_setting_version", lambda _exe: 27)
    monkeypatch.setattr(
        handover.slicer_profiles, "cura_quality_definition", lambda *_a: "creality_base"
    )
    settings = manufacturer.effective(None, _foundation(engine))
    model = tmp_path / "model.3mf"
    model.write_bytes(b"")
    assert handover.cura_profile_beside(model, settings, profile, setup) is not None
    values = _window_values(model)
    assert "cool_fan_speed_min" not in values
    assert "cool_min_layer_time_fan_speed_max" not in values
    assert values["cool_fan_speed"] == "100"

    chosen = print_settings.with_choice(settings, "cooling.fan_below_layer_time", 30.0)
    handover.cura_profile_beside(model, replace(chosen), profile, setup)
    assert _window_values(model)["cool_min_layer_time_fan_speed_max"] == "30"
