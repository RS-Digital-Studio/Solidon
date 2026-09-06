"""Gespeicherte Entscheidungen bleiben eindeutig, auch nach Formatwechseln."""

from dataclasses import replace
from pathlib import Path

import pytest

from app.core.export import handover
from app.core.scene.migrations import migrate
from app.core.scene.project import load, new_project, save
from app.core.types import ChatEntry, FeatureRef, Fit, MaterialSlot, PrintSettings, SlotOverride


def test_same_colour_materials_keep_distinct_print_temperatures(tmp_path: Path) -> None:
    import json

    from app.core.knowledge import profiles

    settings = PrintSettings()
    pla = MaterialSlot(0, "Weiß", (1.0, 1.0, 1.0), material="PLA", material_type="PLA")
    petg = replace(pla, index=1, material="PETG", material_type="PETG")
    settings = handover.with_slot_override(
        settings, pla, SlotOverride(temperature=replace(settings.temperature, nozzle=210.0))
    )
    settings = handover.with_slot_override(
        settings, petg, SlotOverride(temperature=replace(settings.temperature, nozzle=250.0))
    )
    assert len(settings.slot_overrides) == 2
    assert handover.override_for(settings, pla).temperature.nozzle == 210.0
    assert handover.override_for(settings, petg).temperature.nozzle == 250.0
    setup = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    config = handover.write_config(settings, profile, setup, tmp_path, (pla, petg))
    written = [json.loads(path.read_text(encoding="utf-8")) for path in config.filaments]
    assert [float(entry["nozzle_temperature"][0]) for entry in written] == [210.0, 250.0]
    assert [entry["filament_type"][0] for entry in written] == ["PLA", "PETG"]
    removed = handover.with_slot_override(settings, pla, None)
    assert handover.override_for(removed, pla) is None
    assert handover.override_for(removed, petg).temperature.nozzle == 250.0


def test_legacy_override_requires_explicit_binding_to_known_material() -> None:
    settings = PrintSettings()
    old = SlotOverride(name="Weiß", temperature=replace(settings.temperature, nozzle=210.0))
    settings = replace(settings, slot_overrides=(old,))
    slot = MaterialSlot(0, "Weiß", material_type="PETG")
    assert handover.override_for(settings, slot) is None
    assert handover.unbound_override_for(settings, slot) is old
    chosen = handover.with_slot_override(settings, slot, old)
    assert len(chosen.slot_overrides) == 1
    assert handover.override_for(chosen, slot).material_type == "PETG"
    assert handover.unbound_override_for(chosen, slot) is None


def test_choices_survive_a_saved_project(tmp_path: Path) -> None:
    project = new_project()
    settings = PrintSettings()
    project.document.print_settings = replace(
        settings,
        slot_overrides=(
            SlotOverride(
                name="Weiß",
                material="PETG Generic",
                material_type="PETG",
                temperature=replace(settings.temperature, nozzle=250.0),
            ),
        ),
    )
    project.document.chat.append(ChatEntry(id="c1", role="agent", text="Vorschlag", discarded=True))
    project.document.fits.append(
        Fit(
            name="Kragen",
            a=FeatureRef("obj_1", "hole_1"),
            b=FeatureRef("obj_2", "collar"),
            when_positive=(2, "collar"),
        )
    )
    path = tmp_path / "choices.p3d"
    save(project, path)
    restored = load(path)
    assert restored.document.chat[-1].discarded
    assert restored.document.fits[-1].when_positive == (2, "collar")
    assert restored.document.print_settings == project.document.print_settings


def test_v19_keeps_values_without_inventing_missing_identity() -> None:
    data = {
        "format_version": 19,
        "chat": [{"role": "assistant", "text": "Antwort"}],
        "print_settings": {"slot_overrides": [{"name": "Weiß", "temperature": {"nozzle": 210}}]},
    }
    updated = migrate(data)
    assert updated["format_version"] == 20
    assert updated["chat"][0]["discarded"] is False
    slot = updated["print_settings"]["slot_overrides"][0]
    assert slot["material"] is None and slot["material_type"] is None
    assert slot["temperature"]["nozzle"] == 210


@pytest.mark.parametrize("condition", [[True, "collar"], [1, ""], [1], "collar"])
def test_invalid_fit_condition_is_rejected(condition: object) -> None:
    from app.core.scene.project import _validate_fit_schema

    with pytest.raises(ValueError, match="when_positive"):
        _validate_fit_schema(
            {"name": "Kragen", "a": "a.hole", "b": "b.collar", "when_positive": condition}, "fit"
        )
