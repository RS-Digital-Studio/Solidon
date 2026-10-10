"""Eine Spule aus 0.5.3 überschreibt nach dem Update keine neuen Felder (RM-707).

Die Spulenwerte von 0.5.3 kannten ``cooling.minimum_speed`` und
``cooling.support_interface_cooling`` nicht. Füllte der Leser sie mit der
Vorgabe der Dataclass, ginge diese als eigener Wert der Spule an den Slicer:
Elegoos 20 mm/s Mindesttempo würden still zu 10. ``data/projects/
usage_spool_v46.p3d`` hat Solidon 0.5.3 selbst geschrieben — Würfel 20 mm,
CC2, PLA, eine Spule mit Düse 215 °C und Lüfter 80 %, der Druck gebucht.
"""

from __future__ import annotations

import json
import shutil
import zipfile
from dataclasses import replace
from pathlib import Path

import pytest

from app.core import filament_usage as usage
from app.core.export import handover
from app.core.knowledge import print_settings, profiles
from app.core.scene import evaluate
from app.core.scene.project import PROJECT_ENTRY, ProjectSources, load, save
from app.core.types import PrintSettings, SlotOverride

DATA = Path(__file__).parent / "data/projects/usage_spool_v46.p3d"

#: Der Abdruck dieser Buchung unter 0.5.3 (Codekopie des Tags, Grundlage aus der Tabelle).
SPOOL_053 = "613fd5537962aa20f379935a2649c3d1"
#: Die Kühlfelder nach 0.5.3, die die Spule nicht kannte.
LATER = ("cooling.minimum_speed", "cooling.support_interface_cooling")
#: Eine Herstellergrundlage wie die des ElegooSlicers: andere Werte als die Dataclass.
MAKER = {"cooling.minimum_speed": 20.0, "cooling.support_interface_cooling": True}


def opened(path: Path, maker: bool = True):
    """Wie der Druckdialog: gespeicherte Werte über der Grundlage, die Spule des Würfels."""
    project = load(path)
    profile = profiles.make_profile(project.document.printer, project.document.material)
    stored = project.document.print_settings
    assert stored is not None
    base = print_settings.resolve(profile, stored.quality)
    if maker:
        for path_name, value in MAKER.items():
            base = print_settings.with_path(base, path_name, value)
    settings = print_settings.on_base(stored, base)
    objects = list(
        evaluate(project.document, profile, sources=ProjectSources(project)).scene.objects.values()
    )
    slot = usage.prepare(objects, settings, profile, "Würfel")[0].lines[0].slot
    return project, objects, settings, profile, slot


@pytest.fixture
def spool_053(tmp_path: Path) -> Path:
    target = tmp_path / "spule.p3d"
    shutil.copyfile(DATA, target)
    return target


def test_a_053_spool_keeps_its_own_values_and_follows_the_maker_in_later_fields(
    spool_053: Path,
) -> None:
    _project, _objects, settings, profile, slot = opened(spool_053)
    override = handover.override_for(settings, slot)
    assert override is not None and override.cooling is not None
    mine = handover.settings_for_slot(settings, profile, slot)

    assert mine.temperature.nozzle == 215
    assert mine.cooling.fan_speed == pytest.approx(0.8)
    assert mine.cooling.minimum_speed == pytest.approx(20.0)
    assert mine.cooling.support_interface_cooling is True


def test_only_the_spools_own_values_go_to_the_slicer(spool_053: Path) -> None:
    _project, _objects, settings, profile, slot = opened(spool_053)
    written = handover._for_the_slot(frozenset(), settings, slot, profile)
    assert written is not None
    assert {"temperature.nozzle", "cooling.fan_speed"} <= written
    assert not set(LATER) & written


def test_saving_keeps_the_later_fields_unset(spool_053: Path, tmp_path: Path) -> None:
    project, _objects, _settings, _profile, _slot = opened(spool_053)
    again = tmp_path / "wieder.p3d"
    save(project, again)
    with zipfile.ZipFile(again) as container:
        written = json.loads(container.read(PROJECT_ENTRY))
    cooling = written["print_settings"]["slot_overrides"][0]["cooling"]
    assert not {path.partition(".")[2] for path in LATER} & cooling.keys()
    assert cooling["fan_speed"] == pytest.approx(0.8)
    _project, _objects, settings, profile, slot = opened(again)
    mine = handover.settings_for_slot(settings, profile, slot)
    assert mine.cooling.minimum_speed == pytest.approx(20.0)


@pytest.mark.parametrize("maker", [False, True])
def test_the_053_booking_keeps_its_fingerprint(spool_053: Path, maker: bool) -> None:
    _project, objects, settings, profile, _slot = opened(spool_053, maker=maker)
    assert usage.prepare(objects, settings, profile, "Würfel")[0].fingerprint == SPOOL_053


def test_a_value_the_spool_sets_itself_still_counts(spool_053: Path) -> None:
    """Gegenprobe: Ein späteres Feld, das die Spule selbst setzt, geht an den Slicer."""
    _project, objects, settings, profile, slot = opened(spool_053)
    override = handover.override_for(settings, slot)
    assert override is not None and override.cooling is not None
    own = replace(
        override,
        cooling=replace(override.cooling, minimum_speed=12.0),
        inherited=override.inherited - {"cooling.minimum_speed"},
    )
    changed = handover.with_slot_override(settings, slot, own)
    assert handover.settings_for_slot(changed, profile, slot).cooling.minimum_speed == 12.0
    written = handover._for_the_slot(frozenset(), changed, slot, profile)
    assert written is not None and "cooling.minimum_speed" in written
    assert usage.prepare(objects, changed, profile, "Würfel")[0].fingerprint != SPOOL_053


def test_a_new_spool_carries_every_field() -> None:
    """Was eine Spule heute bekommt, ist ganz gesetzt; nur Fehlendes erbt."""
    settings = PrintSettings()
    override = SlotOverride(name="PLA", cooling=settings.cooling)
    assert (
        handover.override_section(
            override, "cooling", replace(settings.cooling, minimum_speed=30.0)
        )
        == settings.cooling
    )
    inherited = replace(override, inherited=frozenset({"cooling.minimum_speed"}))
    shown = handover.override_section(
        inherited, "cooling", replace(settings.cooling, minimum_speed=30.0)
    )
    assert shown.minimum_speed == 30.0
    assert handover.override_section(None, "cooling", settings.cooling) is settings.cooling


def test_advice_for_an_inherited_field_belongs_to_the_spool(spool_053: Path) -> None:
    """Ein übernommener Vorschlag je Spule für ein geerbtes Feld geht nicht verloren
    (Review RM-707, L1) — der Druckrat schlägt etwa die Kühlung der Kontaktschicht vor."""
    _project, _objects, settings, profile, slot = opened(spool_053, maker=False)
    path = "cooling.support_interface_cooling"
    override = handover.override_for(settings, slot)
    assert override is not None and path in override.inherited
    effective = handover.settings_for_slot(settings, profile, slot)
    assert effective.cooling.support_interface_cooling is False
    advised = handover.with_slot_advice(settings, slot, effective, path, True)
    taken = handover.override_for(advised, slot)
    assert taken is not None and path not in taken.inherited
    assert "cooling.minimum_speed" in taken.inherited, "nur der Pfad des Vorschlags"
    assert handover.settings_for_slot(advised, profile, slot).cooling.support_interface_cooling
    written = handover._for_the_slot(frozenset(), advised, slot, profile)
    assert written is not None and path in written


def test_the_fan_curve_of_an_old_spool_comes_from_the_material() -> None:
    """Fehlen Unterkante und Schwelle der Lüfterkurve, ergänzt der Leser sie bewusst aus
    dem Material — sie sind gesetzt, nicht geerbt (Review RM-707, L6)."""
    from app.core.scene.serialise import _override_from_data

    stored = {
        "name": "PETG Schwarz",
        "colour": [0.0, 0.0, 0.0],
        "material": None,
        "material_type": "PETG",
        "cooling": {"fan_speed": 0.4, "bridge_fan_speed": 0.8, "minimum_layer_time": 6.0},
    }
    override = _override_from_data(stored, "pla")
    assert override is not None and override.cooling is not None
    curve = print_settings.fan_curve("petg", 0.4)
    assert override.cooling.minimum_fan_speed == pytest.approx(curve["minimum_fan_speed"])
    assert override.cooling.fan_below_layer_time == pytest.approx(curve["fan_below_layer_time"])
    assert not {"cooling.minimum_fan_speed", "cooling.fan_below_layer_time"} & override.inherited
    assert {"cooling.disable_first_layers", "cooling.minimum_speed"} <= override.inherited
