"""Unterschrittene Materialtemperatur bleibt nach Auflösung sichtbar."""

from dataclasses import replace

import pytest

from app.core.knowledge import print_settings, profiles
from app.core.slice.advise import warnings_for


@pytest.mark.parametrize("maximum,expected", [(230.0, True), (240.0, False), (260.0, False)])
def test_the_nozzle_limit_compares_the_material_request(maximum: float, expected: bool) -> None:
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    profile = replace(profile, printer=replace(profile.printer, nozzle_temperature_max=maximum))
    settings = print_settings.resolve(profile)
    findings = warnings_for(settings, profile)
    matches = [item for item in findings if item.code == "settings.nozzle_below_material"]
    assert bool(matches) is expected
    if expected:
        assert matches[0].values["wanted"] == pytest.approx(240.0)
        assert matches[0].values["possible"] == pytest.approx(maximum)
