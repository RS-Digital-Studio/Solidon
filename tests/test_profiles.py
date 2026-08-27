"""Der mitgelieferte Startbestand ist vollständig und benutzbar (Bauplan
§38, §28.3).
"""

from __future__ import annotations

import pytest

from app.core.errors import ValidationError
from app.core.knowledge import profiles
from app.core.types import Profile


def test_starting_set_is_present() -> None:
    printers = profiles.printer_profiles()
    assert profiles.DEFAULT_PRINTER in printers
    assert "centauri-carbon-2" in printers
    assert len(printers) >= 10, "nobody should have to type build volumes on first start"


def test_every_printer_has_a_plausible_build_volume() -> None:
    for identifier, printer in profiles.printer_profiles().items():
        width, depth, height = printer.build_volume
        assert min(width, depth, height) > 50.0, identifier
        assert max(width, depth, height) < 1000.0, identifier
        assert printer.nozzle_diameter > 0.0, identifier
        assert printer.extrusion_width >= printer.nozzle_diameter, identifier


def test_every_material_is_marked_uncalibrated() -> None:
    materials = profiles.material_profiles()
    assert profiles.DEFAULT_MATERIAL in materials
    for identifier, material in materials.items():
        assert not material.calibrated, f"{identifier} ships as a starting point, not a measurement"
        assert material.clearance > 0.0, identifier
        assert material.hole_compensation > 0.0, identifier


def test_minimum_wall_thickness_follows_the_rule_set() -> None:
    profile = profiles.make_profile()
    assert profile.minimum_wall_thickness == pytest.approx(2 * profile.printer.extrusion_width)


def test_tolerance_reference_resolves_against_the_material() -> None:
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    petg = profiles.material("petg")
    assert profiles.resolve_tolerance("auto:", "clearance", profile) == pytest.approx(
        petg.clearance
    )
    assert profiles.resolve_tolerance("auto:petg", "clearance", profile) == pytest.approx(
        petg.clearance
    )
    assert profiles.resolve_tolerance("auto:tpu-95a", "clearance", profile) == pytest.approx(
        profiles.material("tpu-95a").clearance
    )
    assert profiles.resolve_tolerance(0.3, "clearance", profile) == pytest.approx(0.3)
    assert profiles.resolve_tolerance("auto:", "flush", profile) == pytest.approx(0.0)


def test_unknown_profile_is_a_user_error_with_a_suggestion() -> None:
    with pytest.raises(ValidationError) as caught:
        profiles.printer("does-not-exist")
    assert caught.value.suggestions

    with pytest.raises(ValidationError):
        profiles.material("does-not-exist")


def test_plain_string_is_not_a_tolerance() -> None:
    with pytest.raises(ValidationError):
        profiles.resolve_tolerance("0.2mm", "clearance", profiles.make_profile())


def test_make_profile_pairs_printer_and_material() -> None:
    profile = profiles.make_profile("bambu-p1s", "asa")
    assert isinstance(profile, Profile)
    assert profile.printer.enclosed, "ASA wants a closed chamber; the profile has to say so"
