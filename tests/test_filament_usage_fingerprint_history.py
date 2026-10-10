"""Ein vor dem Update gebuchter Druck wird danach wiedererkannt (RM-705).

Der Abdruck einer Verbrauchsbuchung bildet sich über die Druckeinstellungen.
Kommt ein Einstellungsfeld dazu, darf er sich für denselben Druck nicht
ändern — sonst findet Solidon nach dem Update keine Buchung von davor.

Die Sollwerte kommen **von außen**: gerechnet an Codekopien der Tags
(``git archive v0.5.3``, ``v0.5.1``) mit demselben Körper und denselben
Einstellungen. ``data/projects/usage_booking_v46.p3d`` und
``data/usage_booking_v46_inventory.json`` hat Solidon 0.5.3 selbst geschrieben:
Projekt mit Würfel und Spulenbindung, Lager mit der gebuchten Ausgabe.
"""

from __future__ import annotations

import shutil
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import trimesh

from app.core import filament_usage as usage
from app.core.export import handover, manufacturer
from app.core.geom.mesh import MeshData
from app.core.knowledge import filaments, print_settings, profiles
from app.core.scene import evaluate
from app.core.scene.project import ProjectSources, load
from app.core.scene.serialise import print_settings_to_data
from app.core.types import PrintSettings, SceneObject, SlotOverride
from app.ui import filament_usage as ui

DATA = Path(__file__).parent / "data"

#: Der Abdruck des Würfels unten, gerechnet von Solidon 0.5.3 und 0.5.2
#: (``filament_usage.prepare`` an der Codekopie des Tags, Tabelle des Centauri
#: Carbon 2, PLA, Standard, Kennung ``rm705-probe``).
CUBE_053 = "158d8f5d34a2bdc399712066b36e8e5d"
#: Derselbe Würfel unter 0.5.1 — ohne Brim-/Raftabstand und ohne Wahl der Platte.
CUBE_051 = "3cae285a9a19a5369c1367806477b874"
#: Die Buchung im Lager von 0.5.3 (``usage_booking_v46_inventory.json``).
BOOKED_053 = "aa373e5e86b4471cf557a31589dc8383"
#: Derselbe Druck, unter 0.5.1 gebucht (Kopie des Tags, Kennung ``rm705-bestand``).
BOOKED_051 = "c62cddf4e25ed2cdaa6ed4fd65c6e94d"

#: Die Einstellungsfelder von 0.5.3, gelesen aus ``git show v0.5.3:app/core/types.py``
#: über ``print_settings_to_data(PrintSettings())``. Der Code führt dieselbe Menge.
FIELDS_053 = {
    "adhesion": {
        "brim_gap",
        "brim_width",
        "kind",
        "raft_gap",
        "raft_layers",
        "skirt_distance",
        "skirt_loops",
    },
    "cooling": {
        "bridge_fan_speed",
        "disable_first_layers",
        "fan_below_layer_time",
        "fan_speed",
        "minimum_fan_speed",
        "minimum_layer_time",
    },
    "filament": {"colour", "cost_per_kg", "density", "diameter", "flow_ratio", "max_flow"},
    "infill": {"angle", "density", "pattern"},
    "layers": {"first_layer_height", "first_layer_line_width", "layer_height", "line_width"},
    "retraction": {"avoid_crossing_walls", "length", "speed", "wipe", "z_hop"},
    "shell": {
        "bottom_layers",
        "ironing",
        "outer_wall_first",
        "precise_outer_wall",
        "scarf_seam",
        "seam_position",
        "top_layers",
        "wall_count",
        "wall_generator",
    },
    "speed": {
        "acceleration",
        "bridge",
        "first_layer",
        "infill",
        "inner_wall",
        "outer_wall",
        "outer_wall_acceleration",
        "top_surface",
        "travel",
    },
    "support": {
        "block_channels",
        "density",
        "interface_layers",
        "placement",
        "style",
        "threshold_angle",
        "xy_gap",
        "z_gap",
    },
    "temperature": {"bed", "bed_first_layer", "chamber", "nozzle", "nozzle_first_layer"},
}
#: Die Kopfschlüssel von 0.5.3 neben den Gruppen.
TOP_053 = {
    "accepted",
    "chosen",
    "handover",
    "id",
    "inventory_project_id",
    "plate_choices",
    "quality",
    "slot_overrides",
    "slot_profile_bindings",
    "slot_profiles",
    "spool_bindings",
    "title",
}


def cube_job() -> tuple[list[SceneObject], PrintSettings, Any]:
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = replace(print_settings.resolve(profile), inventory_project_id="rm705-probe")
    cube = SceneObject("obj_1", "Würfel", MeshData.of(trimesh.creation.box(extents=(20, 20, 20))))
    return [cube], settings, profile


def fingerprint(settings: PrintSettings) -> usage.UsageRequest:
    objects, _settings, profile = cube_job()
    return usage.prepare(objects, settings, profile, "Probe")[0]


def later_paths() -> list[str]:
    """Jedes Einstellungsfeld, das nach 0.5.3 dazukam — gezählt, nicht aufgezählt."""
    return [
        path
        for path in print_settings.all_paths()
        if path.partition(".")[2] not in FIELDS_053.get(path.partition(".")[0], set())
    ]


def other_value(value: object) -> object:
    """Ein anderer Wert derselben Art, wie ihn ein Herstellerprofil bringen kann."""
    if isinstance(value, bool):
        return not value
    if isinstance(value, int):
        return value + 1
    if isinstance(value, float):
        return value * 2.0 + 1.0
    if value is None:
        return 1.25
    if isinstance(value, str):
        return value + "-anders"
    if isinstance(value, tuple):
        return (*value, value[-1] if value else 1.0)
    raise AssertionError(f"unbekannte Art {type(value).__name__}: Wächter erweitern")


def test_the_frozen_fields_are_those_of_053() -> None:
    """Die Menge im Code ist die von 0.5.3, und keines ihrer Felder ist verschwunden."""
    assert {group: set(names) for group, names in usage.FINGERPRINT_FIELDS.items()} == FIELDS_053
    data = print_settings_to_data(PrintSettings())
    groups = {key for key, value in data.items() if key in print_settings.GROUPS}
    assert set(data) - groups == TOP_053, "neuer Kopfschlüssel: Regel in prepare festlegen"
    for group, names in FIELDS_053.items():
        assert names <= set(data[group]), f"Feld aus 0.5.3 fehlt in {group}"


def test_the_cube_keeps_its_053_fingerprint() -> None:
    _objects, settings, _profile = cube_job()
    request = fingerprint(settings)
    assert request.fingerprint == CUBE_053
    assert CUBE_051 in request.legacy_fingerprints


def test_every_later_field_at_its_base_keeps_the_fingerprint() -> None:
    """Der Wächter: Jedes Feld nach 0.5.3 fällt als Grundlage aus dem Abdruck.

    Die Grundlage eines solchen Felds ist, was der Slicer ohnehin täte — unter
    0.5.3 nahm er es aus dem Herstellerprofil. Der ElegooSlicer bringt etwa
    ``cooling.minimum_speed`` 20 statt der 10 der Dataclass mit; jeder Wert ohne
    eigene Wahl muss deshalb den Abdruck von 0.5.3 behalten.
    """
    paths = later_paths()
    assert len(paths) >= 6, paths
    _objects, settings, _profile = cube_job()
    unchanged = fingerprint(settings).fingerprint
    assert unchanged == CUBE_053
    # Jedes Feld für sich gegen den unveränderten Abdruck, alle Abweichler auf
    # einmal: Der erste Pfad ist nicht der schuldige (Review RM-705, L3).
    leaking = [
        path
        for path in paths
        if fingerprint(
            print_settings.with_path(
                settings, path, other_value(print_settings.read_path(settings, path))
            )
        ).fingerprint
        != unchanged
    ]
    assert not leaking, f"als Grundlage im Abdruck: {leaking}"


def test_every_later_field_counts_as_own_choice_and_accepted_advice() -> None:
    _objects, settings, _profile = cube_job()
    for path in later_paths():
        value = other_value(print_settings.read_path(settings, path))
        chosen = print_settings.with_choice(settings, path, value)
        accepted = print_settings.with_accepted(settings, path, value)
        assert fingerprint(chosen).fingerprint != CUBE_053, path
        # Woher ein Wert kommt, ändert den Druck nicht (H10).
        assert fingerprint(chosen).fingerprint == fingerprint(accepted).fingerprint, path


def test_a_later_field_of_a_spool_counts_where_it_differs_from_the_value_without_it() -> None:
    """Ein Wert der Spule zählt, wo er vom Wert ohne Spule abweicht — in jeder der
    vier Spulengruppen, dieselbe Auskunft wie ``handover._for_the_slot``."""
    objects, settings, profile = cube_job()
    slot = usage.prepare(objects, settings, profile, "Probe")[0].lines[0].slot
    groups = handover.SLOT_GROUPS
    later = [path for path in later_paths() if path.partition(".")[0] in groups]
    assert later
    # Eine Spule mit allen vier Gruppen, vorbelegt mit den Werten ohne Spule.
    plain = SlotOverride(
        name=slot.name,
        colour=slot.colour,
        material=slot.material,
        material_type=slot.material_type,
        **{group: getattr(settings, group) for group in groups},
    )
    spooled = handover.with_slot_override(settings, slot, plain)
    assert fingerprint(spooled).fingerprint == CUBE_053
    for path in later:
        group, _dot, name = path.partition(".")
        section = getattr(plain, group)
        own = replace(
            plain, **{group: replace(section, **{name: other_value(getattr(section, name))})}
        )
        mine = handover.with_slot_override(settings, slot, own)
        assert fingerprint(mine).fingerprint != CUBE_053, path
        # Derselbe Wert wie ohne Spule ist keine Abweichung.
        assert path not in (handover._for_the_slot(frozenset(), spooled, slot, profile) or ()), path


def test_a_booking_written_by_053_is_found_after_the_update(tmp_path: Path) -> None:
    """Der Kundenweg: Lager und Projekt aus 0.5.3, derselbe Druck neu angesehen."""
    target = filaments.catalogue_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(DATA / "usage_booking_v46_inventory.json", target)
    project_file = tmp_path / "wuerfel.p3d"
    shutil.copyfile(DATA / "projects/usage_booking_v46.p3d", project_file)
    project = load(project_file)
    profile = profiles.make_profile(project.document.printer, project.document.material)
    stored = project.document.print_settings
    assert stored is not None
    # Der Weg der Anwendung (``MainWindow.effective_print_settings``), ohne Slicer.
    settings = manufacturer.effective(
        stored, manufacturer.base_settings(profile, stored.quality, None)
    )
    objects = list(
        evaluate(project.document, profile, sources=ProjectSources(project)).scene.objects.values()
    )
    request = usage.prepare(objects, settings, profile, "Würfel")[0]

    assert request.fingerprint == BOOKED_053
    snapshot = filaments.read_snapshot()
    assert [one.operation_id for one in ui._previous(request, snapshot)] == ["rm705-druck"]
    assert ui._legacy_bookings(request, snapshot) == ()
    # Unter 0.5.1 gebucht, kommt derselbe Druck als frühere Buchung zur Prüfung.
    assert BOOKED_051 in request.legacy_fingerprints


@pytest.mark.parametrize("path", ["support.tree_walls", "cooling.minimum_speed"])
def test_the_guard_turns_red_for_a_later_field_without_the_rule(
    monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    """Gegenprobe: Gehört ein späteres Feld zur eingefrorenen Menge, kippt der Abdruck."""
    group, _dot, name = path.partition(".")
    widened = {**usage.FINGERPRINT_FIELDS, group: usage.FINGERPRINT_FIELDS[group] | {name}}
    monkeypatch.setattr(usage, "FINGERPRINT_FIELDS", widened)
    _objects, settings, _profile = cube_job()
    assert fingerprint(settings).fingerprint != CUBE_053
