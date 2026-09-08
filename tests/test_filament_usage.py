"""Spulenbindung, Ausgabeumfang und Herkunft bleiben unabhängig (§20, §29)."""

import json
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.export import handover, threemf
from app.core.filament_usage import from_gcode, prepare, spool_for, with_spool
from app.core.geom.mesh import MeshData
from app.core.knowledge import profiles
from app.core.scene.migrations import FORMAT_VERSION, migrate
from app.core.scene.project import PROJECT_ENTRY, load, save
from app.core.scene.serialise import print_settings_from_data, print_settings_to_data
from app.core.slice.gcode import GcodeMetrics
from app.core.types import FilamentSettings, MaterialSlot, PrintSettings, SceneObject, SlotOverride
from app.i18n import TranslatableText


def body(identifier: str = "body", *, plate: int = 0) -> SceneObject:
    """Ein druckbarer Würfel mit benanntem Filament."""
    return SceneObject(
        id=identifier,
        name="Würfel",
        mesh=MeshData(trimesh.creation.box((20, 20, 20))),
        plate=plate,
        material_slots=[MaterialSlot(0, "PETG Rot", (1.0, 0.0, 0.0), None, "PETG")],
    )


def test_spool_binding_is_portable_and_does_not_replace_the_profile() -> None:
    slot = body().material_slots[0]
    original = PrintSettings(slot_profiles=("Maker PETG",))
    chosen = with_spool(original, slot, "spool-123")
    restored = print_settings_from_data(print_settings_to_data(chosen))
    assert spool_for(restored, slot) == "spool-123"
    assert restored.slot_profiles == ("Maker PETG",)
    assert spool_for(restored, replace(slot, material_type="PLA")) == ""
    assert spool_for(with_spool(restored, slot, ""), slot) == ""


def test_old_project_keeps_geometry_and_has_no_guessed_inventory_binding(tmp_path: Path) -> None:
    fixture = Path(__file__).parent / "data/projects/example_v20.p3d"
    project = load(fixture)
    before = [(one.id, one.op, one.params) for one in project.document.ops]
    assert project.document.format_version == FORMAT_VERSION
    if project.document.print_settings is not None:
        assert project.document.print_settings.spool_bindings == ()
    target = tmp_path / "again.p3d"
    save(project, target)
    reopened = load(target)
    assert [(one.id, one.op, one.params) for one in reopened.document.ops] == before
    converted = migrate({"format_version": 20, "print_settings": {"slot_profiles": ["PETG"]}})
    assert converted["print_settings"]["slot_profiles"] == ["PETG"]
    assert converted["print_settings"]["spool_bindings"] == []


def test_preparation_ignores_output_name_but_includes_scope_and_print_values() -> None:
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = PrintSettings(inventory_project_id="project-one")
    first = body()
    request = prepare([first], settings, profile, "Projekt")[0]
    assert request.fingerprint == prepare([first], settings, profile, "Umbenannt")[0].fingerprint
    assert (
        request.fingerprint
        != prepare([first, body("second")], settings, profile, "Projekt")[0].fingerprint
    )
    modified = replace(settings, infill=replace(settings.infill, density=0.75))
    assert request.fingerprint != prepare([first], modified, profile, "Projekt")[0].fingerprint
    bound = with_spool(settings, first.material_slots[0], "spool-123")
    assert request.fingerprint == prepare([first], bound, profile, "Projekt")[0].fingerprint
    assert prepare([first, body("second", plate=1)], settings, profile, "Projekt")[1].plate == 1


def test_fingerprint_keeps_each_bodys_material_assignment() -> None:
    first, second = body("large"), body("small")
    second.mesh = MeshData(trimesh.creation.box((10, 10, 10)))
    second.material_slots = [MaterialSlot(0, "PLA Blau", (0.0, 0.0, 1.0), None, "PLA")]
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = PrintSettings(inventory_project_id="project-one")
    before = prepare([first, second], settings, profile, "Projekt")[0]
    first.material_slots, second.material_slots = second.material_slots, first.material_slots
    after = prepare([first, second], settings, profile, "Projekt")[0]
    assert before.fingerprint != after.fingerprint
    before_weights = {line.slot.name: line.grams for line in before.lines}
    after_weights = {line.slot.name: line.grams for line in after.lines}
    assert before_weights != after_weights


def test_fingerprint_keeps_values_of_translatable_material_names() -> None:
    first = body()
    first.material_slots[0] = replace(
        first.material_slots[0], name=TranslatableText("Slot {number}", values={"number": 2})
    )
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = PrintSettings(inventory_project_id="project-one")
    before = prepare([first], settings, profile, "Projekt")[0]
    first.material_slots[0] = replace(
        first.material_slots[0], name=TranslatableText("Slot {number}", values={"number": 3})
    )
    assert before.fingerprint != prepare([first], settings, profile, "Projekt")[0].fingerprint


def test_two_materials_have_no_invented_internal_mass_split() -> None:
    first = body()
    first.material_slots.append(MaterialSlot(1, "PLA Weiß", (1.0, 1.0, 1.0), None, "PLA"))
    first.mesh = MeshData(first.mesh.raw, tuple([0] * 6 + [1] * 6))
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    request = prepare([first], PrintSettings(), profile, "Projekt")[0]
    assert [line.grams for line in request.lines] == [None, None]
    only_total = from_gcode(request, GcodeMetrics(filament_grams=53.0))
    assert [line.grams for line in only_total.lines] == [None, None]
    per_tool = from_gcode(request, GcodeMetrics(filament_grams_by_tool=(47.0, 6.0)))
    assert [line.grams for line in per_tool.lines] == pytest.approx([47.0, 6.0])
    assert all(line.source == "gcode" for line in per_tool.lines)


def test_gcode_length_uses_the_individual_filament_diameter_and_density() -> None:
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    request = prepare([body()], PrintSettings(), profile, "Projekt")[0]
    request = replace(request, lines=(replace(request.lines[0], diameter=2.85, density=1.2),))
    result = from_gcode(request, GcodeMetrics(filament_mm_by_tool=(1000.0,)))
    assert result.lines[0].grams == pytest.approx(7.655276)
    assert result.lines[0].converted_from_length


@pytest.mark.parametrize("total_only", [False, True])
@pytest.mark.parametrize("field", ["density", "diameter"])
@pytest.mark.parametrize("invalid", [None, 0.0, -1.0, float("nan"), float("inf")])
def test_gcode_conversion_requires_positive_finite_material_values(
    total_only: bool, field: str, invalid: float | None
) -> None:
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    request = prepare([body()], PrintSettings(), profile, "Projekt")[0]
    request = replace(request, lines=(replace(request.lines[0], **{field: invalid}),))
    metrics = (
        GcodeMetrics(filament_mm=1000.0)
        if total_only
        else GcodeMetrics(filament_mm_by_tool=(1000.0,))
    )
    line = from_gcode(request, metrics).lines[0]
    assert line.grams is None
    assert not line.converted_from_length


def test_single_total_uses_the_same_conversion_and_explicit_zero_wins() -> None:
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    request = prepare([body()], PrintSettings(), profile, "Projekt")[0]
    request = replace(request, lines=(replace(request.lines[0], diameter=2.85, density=1.2),))
    line = from_gcode(request, GcodeMetrics(filament_mm=1000.0)).lines[0]
    assert line.grams == pytest.approx(7.655276)
    assert line.converted_from_length
    zero = from_gcode(
        request, GcodeMetrics(filament_grams=53.0, filament_grams_by_tool=(0.0,))
    ).lines[0]
    assert zero.grams == pytest.approx(0.0)
    assert not zero.converted_from_length


@pytest.mark.parametrize(
    "metrics",
    [
        GcodeMetrics(filament_grams=53.0, filament_grams_by_tool=(None, 6.0)),
        GcodeMetrics(filament_grams=53.0, filament_grams_by_tool=(None, None)),
        GcodeMetrics(filament_grams=53.0, filament_mm_by_tool=(None, 1000.0)),
    ],
)
def test_single_model_material_does_not_absorb_other_gcode_tools(metrics: GcodeMetrics) -> None:
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    request = prepare([body()], PrintSettings(), profile, "Projekt")[0]
    assert from_gcode(request, metrics).lines[0].grams is None


def test_different_tools_convert_with_their_own_properties_without_compressing_gaps() -> None:
    first = body()
    first.material_slots.insert(0, MaterialSlot(7, "Alt", None, None, "ABS"))
    first.material_slots.append(MaterialSlot(1, "PLA Weiß", None, None, "PLA"))
    first.mesh = MeshData(first.mesh.raw, tuple([0] * 6 + [1] * 6))
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    request = prepare([first], PrintSettings(), profile, "Projekt")[0]
    request = replace(
        request,
        lines=(
            replace(request.lines[0], diameter=2.85, density=1.2),
            replace(request.lines[1], diameter=1.75, density=1.24),
        ),
    )
    converted = from_gcode(request, GcodeMetrics(filament_mm_by_tool=(0.0, 1000.0, 2000.0)))
    assert [line.slot.index for line in converted.lines] == [1, 2]
    assert [line.grams for line in converted.lines] == pytest.approx([7.655276, 5.965099])
    assert all(line.converted_from_length for line in converted.lines)


def test_unused_historical_slots_need_no_spool_but_keep_the_active_tool_number() -> None:
    first = body()
    first.material_slots.insert(0, MaterialSlot(7, "Alt", None, None, "PLA"))
    first.material_slots.append(MaterialSlot(9, "Auch alt", None, None, "ABS"))
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = PrintSettings()
    request = prepare([first], settings, profile, "Projekt")[0]
    assert len(request.lines) == 1
    assert request.lines[0].slot.index == 1
    assert request.lines[0].slot.name == "PETG Rot"
    assert request.lines[0].grams is not None and request.lines[0].grams > 0.0
    per_tool = from_gcode(request, GcodeMetrics(filament_grams_by_tool=(0.0, 47.0, 0.0)))
    assert per_tool.lines[0].grams == pytest.approx(47.0)
    first.material_slots[0] = replace(first.material_slots[0], name="Alter Name geändert")
    assert prepare([first], settings, profile, "Projekt")[0].fingerprint == request.fingerprint


@pytest.mark.parametrize("material_type", [None, "", "UNKNOWN", "NewBlend-X"])
def test_unknown_material_has_no_invented_density_or_internal_grams(
    material_type: str | None,
) -> None:
    first = body()
    slot = replace(first.material_slots[0], material_type=material_type)
    first.material_slots = [slot]
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    request = prepare([first], PrintSettings(), profile, "Projekt")[0]
    assert request.lines[0].grams is None
    assert request.lines[0].density is None
    assert request.lines[0].diameter is None
    assert from_gcode(request, GcodeMetrics(filament_mm=1000.0)).lines[0].grams is None
    assert from_gcode(request, GcodeMetrics(filament_grams=47.0)).lines[0].grams == pytest.approx(
        47.0
    )
    explicit = PrintSettings(
        slot_overrides=(
            SlotOverride(
                name=slot.name,
                colour=slot.colour,
                material_type=material_type,
                filament=FilamentSettings(density=1.2, diameter=2.85),
            ),
        )
    )
    known = prepare([first], explicit, profile, "Projekt")[0]
    assert known.lines[0].grams is not None and known.lines[0].grams > 0.0
    assert known.lines[0].density == pytest.approx(1.2)
    assert known.lines[0].diameter == pytest.approx(2.85)


def test_external_profile_requires_explicit_properties_for_mass_conversion() -> None:
    first = body()
    slot = replace(first.material_slots[0], material="Vendor PETG")
    first.material_slots = [slot]
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    request = prepare([first], PrintSettings(), profile, "Projekt")[0]
    assert request.lines[0].grams is None
    assert request.lines[0].density is None and request.lines[0].diameter is None
    assert from_gcode(request, GcodeMetrics(filament_mm_by_tool=(1000.0,))).lines[0].grams is None
    assert from_gcode(request, GcodeMetrics(filament_grams_by_tool=(47.0,))).lines[
        0
    ].grams == pytest.approx(47.0)
    explicit = handover.with_slot_override(
        PrintSettings(), slot, SlotOverride(filament=FilamentSettings(density=2.0, diameter=2.85))
    )
    known = prepare([first], explicit, profile, "Projekt")[0]
    converted = from_gcode(known, GcodeMetrics(filament_mm_by_tool=(1000.0,))).lines[0]
    assert converted.grams == pytest.approx(12.758793)
    assert converted.converted_from_length


def test_missing_used_slot_stays_visible_as_unassigned_material() -> None:
    first = body()
    first.material_slots = [replace(first.material_slots[0], index=1)]
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    request = prepare([first], PrintSettings(), profile, "Projekt")[0]
    assert len(request.lines) == 1
    assert request.lines[0].slot.index == 1
    assert request.lines[0].slot.material_type is None
    assert request.lines[0].grams is None
    assert request.lines[0].spool_identifier == ""


def test_global_export_and_local_slicer_keep_identity_with_effective_profile_choice() -> None:
    first, second = body(), body("second", plate=1)
    first.material_slots = [MaterialSlot(0, "PLA Weiß", None, None, "PLA")]
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = PrintSettings(
        inventory_project_id="project-one", slot_profiles=("Maker PLA", "Maker PETG")
    )
    stale_binding = with_spool(settings, second.material_slots[0], "old-spool")
    export = prepare([first, second], stale_binding, profile, "Projekt")[1]
    assert export.lines[0].slot.index == 1
    assert export.lines[0].slot.material == "Maker PETG"
    assert export.lines[0].spool_identifier == ""
    local = threemf.merge_slots(
        [threemf.AssemblyPart(second.mesh, slots=tuple(second.material_slots))]
    )
    chosen = handover.with_slot_profiles(local, ("Maker PETG",))
    sliced = prepare(
        [first, second], stale_binding, profile, "Projekt", slots_by_plate={1: chosen}
    )[1]
    assert sliced.lines[0].slot.index == 0
    assert sliced.fingerprint == export.fingerprint
    assert from_gcode(sliced, GcodeMetrics(filament_grams_by_tool=(6.0,))).lines[
        0
    ].grams == pytest.approx(6.0)
    changed = prepare(
        [first, second],
        stale_binding,
        profile,
        "Projekt",
        slots_by_plate={1: handover.with_slot_profiles(local, ("Other PETG",))},
    )[1]
    assert changed.fingerprint != export.fingerprint


def test_multimaterial_body_keeps_shared_material_unknown_regardless_of_body_order() -> None:
    mixed, single = body("mixed"), body("single")
    mixed.material_slots.append(MaterialSlot(1, "PLA Weiß", None, None, "PLA"))
    mixed.mesh = MeshData(mixed.mesh.raw, tuple([0] * 6 + [1] * 6))
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    for objects in ([mixed, single], [single, mixed]):
        request = prepare(objects, PrintSettings(), profile, "Projekt")[0]
        assert [line.grams for line in request.lines] == [None, None]


def test_spool_binding_survives_a_real_project_roundtrip(tmp_path: Path) -> None:
    project = load(Path(__file__).parent / "data/projects/example_v20.p3d")
    before = [(one.id, one.op, one.params) for one in project.document.ops]
    slot = replace(
        body().material_slots[0], name=TranslatableText("Slot {number}", values={"number": 2})
    )
    settings = with_spool(
        PrintSettings(inventory_project_id="project-one", slot_profiles=("Maker PETG",)),
        slot,
        "spool-123",
    )
    project.document.print_settings = settings
    target = tmp_path / "bound.p3d"
    save(project, target)
    reopened = load(target)
    assert reopened.document.print_settings == settings
    assert spool_for(reopened.document.print_settings, slot) == "spool-123"
    assert [(one.id, one.op, one.params) for one in reopened.document.ops] == before
    with zipfile.ZipFile(target) as container:
        written = json.loads(container.read(PROJECT_ENTRY))
    stored = written["print_settings"]["spool_bindings"][0]
    assert stored["name"]["msgid"] == "Slot {number}"
    assert stored["name"]["values"] == {"number": 2}
    assert not ({"remaining_grams", "spool_grams", "ledger", "bookings"} & stored.keys())


@pytest.mark.parametrize(
    "invalid",
    [
        None,
        17,
        ["name"],
        {"wrong": "key"},
        {"msgid": 17},
        {"msgid": "Name", "context": []},
        {"msgid": "Name", "values": []},
    ],
)
def test_invalid_spool_name_is_rejected_as_project_data(tmp_path: Path, invalid: object) -> None:
    project = load(Path(__file__).parent / "data/projects/example_v21.p3d")
    project.document.print_settings = with_spool(
        PrintSettings(), body().material_slots[0], "spool-123"
    )
    target = tmp_path / "invalid-name.p3d"
    save(project, target)
    with zipfile.ZipFile(target) as container:
        entries = {name: container.read(name) for name in container.namelist()}
    written = json.loads(entries[PROJECT_ENTRY])
    written["print_settings"]["spool_bindings"][0]["name"] = invalid
    entries[PROJECT_ENTRY] = json.dumps(written).encode("utf-8")
    with zipfile.ZipFile(target, "w") as container:
        for name, payload in entries.items():
            container.writestr(name, payload)
    with pytest.raises(ValidationError) as caught:
        load(target)
    assert "spool_bindings[0].name" in str(caught.value.values.get("reason", ""))
