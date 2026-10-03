"""Eigenständiger Raftabstand: Herkunft, Wahl und tatsächliche Übergabe."""

from dataclasses import replace
from pathlib import Path

import pytest

from app.core.export import handover, manufacturer
from app.core.knowledge import print_settings, profiles
from app.core.scene.serialise import print_settings_from_data, print_settings_to_data
from app.core.types import AdhesionSettings

FAMILIES = (
    ("prusa", "raft_contact_distance", "support_material_contact_distance"),
    ("orca", "raft_contact_distance", "support_top_z_distance"),
    ("cura", "raft_airgap", "support_z_distance"),
)


def setting(kind="raft", gap=None):
    settings = print_settings.resolve(profiles.make_profile())
    assert hasattr(settings.adhesion, "raft_gap"), "Das eigenständige Raftfeld fehlt."
    return replace(
        settings,
        adhesion=replace(settings.adhesion, kind=kind, raft_gap=gap),
        support=replace(settings.support, z_gap=0.2, style="none"),
    )


@pytest.mark.parametrize("flavour,key,support_key", FAMILIES)
@pytest.mark.parametrize("gap", (0.0, 0.16, 0.35))
def test_own_gap_is_written_even_without_supports(flavour, key, support_key, gap):
    settings = print_settings.with_choice(setting(gap=gap), "adhesion.raft_gap", gap)
    values = handover.as_mapping(settings, flavour, paths=settings.explicit)
    assert float(values[key]) == pytest.approx(gap)
    assert support_key not in values
    assert settings.support.style == "none"
    assert settings.support.z_gap == pytest.approx(0.2)


@pytest.mark.parametrize("flavour,key,support_key", FAMILIES)
def test_unknown_gap_preserves_native_default(flavour, key, support_key):
    settings = setting()
    values = handover.values_for(settings, profiles.make_profile(), flavour)
    assert key not in values
    assert "layer_0_z_overlap" not in values
    assert settings.adhesion.raft_gap is None


@pytest.mark.parametrize("flavour,key,support_key", FAMILIES)
@pytest.mark.parametrize("kind", ("none", "skirt", "brim"))
def test_dormant_gap_is_not_written(flavour, key, support_key, kind):
    settings = print_settings.with_choice(setting(kind, 0.16), "adhesion.raft_gap", 0.16)
    assert key not in handover.as_mapping(settings, flavour, paths=settings.explicit)


@pytest.mark.parametrize("flavour", ("prusa", "orca"))
def test_native_reader_separates_two_gaps(flavour):
    values = {
        "raft_contact_distance": "0.15",
        "support_material_contact_distance": "0.2",
        "support_top_z_distance": "0.2",
    }
    context = manufacturer._Context(0.4)
    read, foreign = (
        manufacturer._read_prusa(values, context)
        if flavour == "prusa"
        else manufacturer._read_process(values, context, {})
    )
    assert read["support.z_gap"] == pytest.approx(0.2)
    assert read["adhesion.raft_gap"] == pytest.approx(0.15)
    assert "adhesion.raft_gap" not in foreign


@pytest.mark.parametrize("flavour,key,support_key", FAMILIES)
def test_own_support_gap_never_changes_raft(flavour, key, support_key):
    settings = print_settings.with_choice(setting(gap=0.15), "support.z_gap", 0.16)
    values = handover.as_mapping(settings, flavour, paths=settings.explicit)
    assert key not in values
    assert float(values[support_key]) == pytest.approx(0.16)
    assert settings.adhesion.raft_gap == pytest.approx(0.15)


def test_old_settings_do_not_invent_a_raft_choice():
    old = {
        "adhesion": {"kind": "raft", "raft_layers": 2},
        "support": {"z_gap": 0.16},
        "chosen": ["adhesion.kind", "support.z_gap"],
        "accepted": [],
    }
    loaded = print_settings_from_data(old, "pla")
    assert hasattr(loaded.adhesion, "raft_gap")
    assert loaded.adhesion.raft_gap is None
    assert loaded.chosen == frozenset(old["chosen"])
    assert loaded.support.z_gap == pytest.approx(0.16)


@pytest.mark.parametrize("gap", (None, 0.0, 0.16))
def test_gap_and_origin_survive_roundtrip(gap):
    original = setting(gap=gap)
    if gap is not None:
        original = print_settings.with_choice(original, "adhesion.raft_gap", gap)
    restored = print_settings_from_data(print_settings_to_data(original), "pla")
    assert restored == original
    assert restored.adhesion.raft_gap == gap


def test_raft_gap_active_without_supports_and_support_gap_hidden():
    inactive = print_settings.inactive_paths("none", "raft")
    assert "adhesion.raft_gap" in print_settings.ADHESION_DETAILS
    assert "adhesion.raft_gap" not in inactive
    assert "support.z_gap" in inactive
    assert "adhesion.raft_gap" in print_settings.inactive_paths("none", "brim")
    assert "adhesion.raft_gap" not in print_settings.inactive_paths(
        "none", "skirt", also=frozenset({"raft"})
    )


def test_choosing_raft_does_not_invent_a_gap():
    chosen = print_settings.with_choice(setting("skirt"), "adhesion.kind", "raft")
    assert chosen.adhesion.raft_gap is None
    assert "adhesion.raft_gap" not in chosen.explicit


def test_returning_to_foundation_restores_only_raft_gap():
    foundation = setting(gap=0.15)
    own = print_settings.with_choice(foundation, "support.z_gap", 0.16)
    own = print_settings.with_choice(own, "adhesion.raft_gap", 0.3)
    cleared = print_settings.without_choice(own, "adhesion.raft_gap", foundation)
    restored = print_settings.on_base(cleared, foundation)
    assert restored.adhesion.raft_gap == pytest.approx(0.15)
    assert restored.support.z_gap == pytest.approx(0.16)


def test_dataclass_default_does_not_claim_native_number():
    assert hasattr(AdhesionSettings(), "raft_gap")
    assert AdhesionSettings().raft_gap is None


def test_cura_fixed_follower_is_preserved():
    settings = setting(gap=0.16)
    values = {"raft_airgap": "0.16", "layer_0_z_overlap": "0.07"}
    result = handover._cura_dependants(values, settings, profiles.make_profile())
    assert float(result["layer_0_z_overlap"]) == pytest.approx(0.07)


def test_cura_formula_is_not_guessed_without_its_native_definition():
    settings = setting(gap=0.16)
    values = handover.values_for(settings, profiles.make_profile(), "cura")
    assert float(values["raft_airgap"]) == pytest.approx(0.16)
    assert "layer_0_z_overlap" not in values


@pytest.mark.parametrize("flavour,key,support_key", FAMILIES)
def test_zero_raft_layers_follow_the_native_family_meaning(flavour, key, support_key):
    settings = print_settings.with_choice(setting(gap=0.16), "adhesion.raft_gap", 0.16)
    settings = print_settings.with_choice(settings, "adhesion.raft_layers", 0)
    values = handover.as_mapping(settings, flavour, paths=settings.explicit)
    assert (key in values) is (flavour == "cura")


@pytest.mark.parametrize("gap", (None, 0.0, 0.15, 0.2))
def test_prusa_foundation_and_both_output_paths_preserve_unselected_gap(monkeypatch, gap):
    native = {"support_material_contact_distance": "0.2", "raft_layers": "2"}
    if gap is not None:
        native["raft_contact_distance"] = str(gap)
    chain = manufacturer.PrusaChain("Printer", "Process", "Filament", native)
    monkeypatch.setattr(manufacturer, "prusa_chain", lambda *args: chain)
    profile = profiles.make_profile()
    setup = handover.SlicerSetup(Path("prusa-slicer-console.exe"), "prusa", base_process="Process")
    base = manufacturer.base_settings(profile, "standard", setup)
    assert base.settings.adhesion.raft_gap == gap
    assert base.settings.support.z_gap == pytest.approx(0.2)
    original = print_settings_from_data(
        {"adhesion": {"kind": "raft"}, "support": {"z_gap": 0.16}, "chosen": ["support.z_gap"]}
    )
    combined = print_settings.on_base(original, base.settings)
    assert combined.adhesion.raft_gap == gap
    assert "adhesion.raft_gap" not in combined.explicit
    for console in (False, True):
        written, _expected = handover.prusa_values(combined, profile, setup, (), console=console)
        assert written.get("raft_contact_distance") == native.get("raft_contact_distance")
        assert float(written["support_material_contact_distance"]) == pytest.approx(0.16)
