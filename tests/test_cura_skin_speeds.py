"""RM-482: Sichtbare Oberseiten und innere Vollschichten behalten ihre Tempi.

Am SV06-Pilz fuhr Cura 19,98 m innere Haut mit 30 statt 60 mm/s. Prusa
unterscheidet ``Solid infill`` und ``Top solid infill``; Cura braucht dafür
eine Dachschicht. Die echte Gegenprobe liegt im Abschluss von RM-482.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from app.core.export import handover
from app.core.knowledge import print_settings, profiles


@pytest.mark.parametrize("top_layers", [0, 1, 4])
@pytest.mark.parametrize("path", [None, "speed.top_surface", "shell.top_layers"])
def test_only_the_outermost_top_skin_uses_the_surface_speed(top_layers, path) -> None:
    profile = profiles.make_profile("sovol-sv06", "pla")
    settings = print_settings.resolve(profile)
    settings = replace(
        settings,
        shell=replace(settings.shell, top_layers=top_layers),
        speed=replace(settings.speed, infill=73.0, top_surface=30.0),
    )
    paths = None if path is None else frozenset({path})

    written = handover.as_mapping(settings, "cura", paths)

    assert written["roofing_layer_count"] == ("1" if top_layers else "0")
    if path != "shell.top_layers":
        assert float(written["speed_roofing"]) == pytest.approx(30.0)
    if path is None:
        assert float(written["speed_topbottom"]) == pytest.approx(73.0)


def test_the_engine_gets_distinct_skin_speeds_globally_and_on_the_extruder(tmp_path: Path) -> None:
    profile = profiles.make_profile("sovol-sv06", "pla")
    settings = print_settings.resolve(profile)
    settings = replace(settings, speed=replace(settings.speed, infill=73.0, top_surface=30.0))
    setup = handover.SlicerSetup(tmp_path / "CuraEngine.exe", "cura")

    config = handover.write_config(settings, profile, setup, tmp_path)
    command = handover._command(setup, [tmp_path / "pilz.stl"], config, tmp_path)

    expected = {
        "speed_topbottom": 73.0,
        "speed_roofing": 30.0,
        "speed_flooring": 73.0,
        "roofing_layer_count": 1,
        "flooring_layer_count": 0,
        "speed_ironing": 20.0,
    }
    for section in (command[: command.index("-e0")], command[command.index("-e0") + 1 :]):
        actual = dict(value.split("=", 1) for value in section if "=" in value)
        for key, value in expected.items():
            assert float(actual[key]) == pytest.approx(value), key


def test_a_change_to_infill_does_not_replace_the_surface_speed() -> None:
    profile = profiles.make_profile("sovol-sv06", "pla")
    settings = print_settings.resolve(profile)
    settings = replace(settings, speed=replace(settings.speed, infill=73.0, top_surface=30.0))

    written = handover.as_mapping(settings, "cura", frozenset({"speed.infill"}))

    assert float(written["speed_infill"]) == pytest.approx(73.0)
    assert float(written["speed_topbottom"]) == pytest.approx(73.0)
    assert "speed_roofing" not in written
    assert "roofing_layer_count" not in written
