"""Die eigene Wahl der Platte bleibt neben einem Vorschlag je Teil (RM-289, B2/B6).

Wer im Druckdialog „Keine Haftung“ wählt und danach den Brim für den schlanken
Turm übernimmt, meint: der Turm mit Brim, die übrigen Teile ohne. Ein Pfad hat
aber nur einen Wert; die Übernahme löschte die Wahl, und die Platte fiel auf
die Grundlage zurück — dort ein Skirt, den niemand gewählt hatte. Der Dialog
zeigte danach „Brim“ im Feld, als gälte er der Platte (B6).
"""

from __future__ import annotations

import json
import zipfile
from dataclasses import replace
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
import trimesh

from app.core.export.writer import write_assembly
from app.core.geom.mesh import MeshData
from app.core.knowledge import print_settings, profiles
from app.core.scene import serialise
from app.core.types import PrintSettings, Profile, SceneObject


@pytest.fixture
def cc2() -> Profile:
    return profiles.make_profile("centauri-carbon-2", "pla")


def _own_then_accepted(profile: Profile) -> PrintSettings:
    settings = print_settings.resolve(profile, "standard")
    assert settings.adhesion.kind == "skirt", "die Vorbedingung: die Grundlage hat einen Skirt"
    chosen = print_settings.with_choice(settings, "adhesion.kind", "none")
    return print_settings.with_accepted(chosen, "adhesion.kind", "brim")


def test_accepting_a_suggestion_keeps_the_own_choice_for_the_plate(cc2: Profile) -> None:
    settings = _own_then_accepted(cc2)

    assert settings.adhesion.kind == "brim"
    assert "adhesion.kind" in settings.accepted and "adhesion.kind" not in settings.chosen
    assert print_settings.plate_choice(settings, "adhesion.kind") == ("none",)


def test_the_own_choice_ends_with_a_new_choice_or_a_reset(cc2: Profile) -> None:
    settings = _own_then_accepted(cc2)
    base = print_settings.resolve(cc2, "standard")

    chosen = print_settings.with_choice(settings, "adhesion.kind", "raft")
    assert print_settings.plate_choice(chosen, "adhesion.kind") is None

    cleared = print_settings.without_choice(settings, "adhesion.kind", base)
    assert print_settings.plate_choice(cleared, "adhesion.kind") is None
    assert cleared.adhesion.kind == "skirt"


def test_resetting_the_suggestion_returns_to_the_own_choice(cc2: Profile) -> None:
    """*Zurücksetzen* am Feld nimmt den Vorschlag zurück, nicht die eigene Wahl
    darunter."""
    settings = _own_then_accepted(cc2)
    base = print_settings.resolve(cc2, "standard")

    back = print_settings.reset(settings, "adhesion.kind", base)

    assert back.adhesion.kind == "none"
    assert "adhesion.kind" in back.chosen and "adhesion.kind" not in back.accepted
    assert print_settings.plate_choice(back, "adhesion.kind") is None


def test_the_plate_choice_travels_in_the_project_file(cc2: Profile) -> None:
    settings = _own_then_accepted(cc2)
    data = serialise.print_settings_to_data(settings)

    assert data["plate_choices"] == {"adhesion.kind": "none"}
    restored = serialise.print_settings_from_data(json.loads(json.dumps(data)))
    assert restored.plate_choices == settings.plate_choices


@pytest.mark.parametrize(
    "stored",
    [
        {"shell.wall_count": 4},  # kein übernommener Pfad
        {"adhesion.kind": 3},  # ein Wert falscher Art
        {"no.such_path": 1},
    ],
)
def test_a_plate_choice_nobody_can_see_is_dropped(cc2: Profile, stored: dict) -> None:
    data = serialise.print_settings_to_data(_own_then_accepted(cc2))
    data["plate_choices"] = stored

    assert serialise.print_settings_from_data(data).plate_choices == ()


def test_an_older_file_without_plate_choices_still_reads(cc2: Profile) -> None:
    data = serialise.print_settings_to_data(_own_then_accepted(cc2))
    del data["plate_choices"]

    restored = serialise.print_settings_from_data(data)
    assert restored.plate_choices == ()
    assert "adhesion.kind" in restored.accepted


def _object_values(written: Path) -> dict[str, dict[str, str]]:
    config = ET.fromstring(zipfile.ZipFile(written).read("Metadata/model_settings.config"))
    values: dict[str, dict[str, str]] = {}
    for node in config.iter("object"):
        own = {item.get("key", ""): item.get("value", "") for item in node.findall("metadata")}
        values[own.get("name", "")] = own
    return values


def _plate_value(written: Path, key: str) -> object:
    return json.loads(zipfile.ZipFile(written).read("Metadata/project_settings.config")).get(key)


def test_the_plate_prints_the_own_choice_and_the_tower_its_brim(
    tmp_path: Path, cc2: Profile
) -> None:
    """Die Datei für den Slicer: Platte ohne Haftung (die eigene Wahl), der
    schlanke Turm mit Brim als Objektwert. Bis 0.5.1 bekam die Platte den
    Skirt der Grundlage (B2)."""
    tower = MeshData.of(trimesh.creation.box(extents=(4.0, 4.0, 80.0)))
    wide = MeshData.of(trimesh.creation.box(extents=(60.0, 60.0, 10.0)))
    objects = [
        SceneObject(id="obj_1", name="Turm", mesh=tower),
        SceneObject(id="obj_2", name="Platte", mesh=wide),
    ]

    written, findings = write_assembly(
        objects, tmp_path, project_name="Satz", profile=cc2, settings=_own_then_accepted(cc2)
    )

    assert str(_plate_value(written, "skirt_loops")) in ("0", "['0']")
    assert _plate_value(written, "brim_type") == "no_brim"
    values = _object_values(written)
    assert values["Turm"]["brim_type"] == "outer_only"
    assert "brim_type" not in values["Platte"]
    assert [entry.object_id for entry in findings if entry.code == "export.part_setting"] == [
        "obj_1"
    ]


def test_without_an_own_choice_the_plate_keeps_the_foundation(tmp_path: Path, cc2: Profile) -> None:
    """Gegenstück: Ohne eigene Wahl bleibt die Platte bei der Grundlage."""
    settings = print_settings.with_accepted(
        print_settings.resolve(cc2, "standard"), "adhesion.kind", "brim"
    )
    objects = [
        SceneObject(
            id="obj_1", name="Turm", mesh=MeshData.of(trimesh.creation.box(extents=(4, 4, 80)))
        ),
        SceneObject(
            id="obj_2",
            name="Platte",
            mesh=MeshData.of(trimesh.creation.box(extents=(60, 60, 10))),
        ),
    ]
    written, _findings = write_assembly(
        objects, tmp_path, project_name="Satz", profile=cc2, settings=replace(settings)
    )
    assert str(_plate_value(written, "skirt_loops")) not in ("0", "['0']")
