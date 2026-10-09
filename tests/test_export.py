"""Export und die Prüfung, die davor läuft (Bauplan §29, §16.3)."""

from __future__ import annotations

import json
import re
import zipfile
from dataclasses import replace
from io import BytesIO
from pathlib import Path
from typing import Any, get_args
from xml.etree import ElementTree as ET

import pytest
import trimesh

from app.core.errors import FileWriteError, NeedsSolidError, ValidationError
from app.core.export import handover, manufacturer, slicer_keys, threemf, writer
from app.core.export.handover import with_slot_profiles
from app.core.export.slicer_keys import SlicerFlavour
from app.core.export.writer import (
    arrangement_holds,
    check_adhesion_clearance,
    check_adhesion_on_bed,
    check_before_export,
    check_filament_changes,
    export_bytes,
    plan_export,
    plates_by_material,
    safe_name,
    write_assembly,
    write_plan,
)
from app.core.geom.mesh import MeshData, as_mesh_data, read_mesh
from app.core.geom.prepare import check_build_volume
from app.core.geom.transform import apply, place_on_bed, translation
from app.core.ingest import threemf as threemf_reader
from app.core.ingest.loader import normalise, read_model
from app.core.knowledge import print_settings, profiles
from app.core.slice import advise
from app.core.types import (
    Finding,
    MaterialSlot,
    Profile,
    Scene,
    SceneObject,
    SettingAdvice,
    SlotProfileBinding,
    Source,
    SourceOrigin,
)
from app.core.units import MAX_FACET_SAG, format_length
from app.i18n import source_text

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.mark.parametrize("flavour", ["orca", "prusa", "cura"])
@pytest.mark.parametrize("reported", [False, True])
def test_export_reuses_its_own_layers_for_advice_and_blocker(
    tmp_path: Path,
    profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
    flavour: SlicerFlavour,
    reported: bool,
) -> None:
    """B9: Ohne vorbereiteten Bericht wird derselbe Körper genau einmal geschnitten."""
    from app.core.slice import analysis

    entry = scene_object(mesh=tunnel_block())
    settings = print_settings.with_choice(print_settings.resolve(profile), "support.style", "grid")
    settings = print_settings.with_accepted(settings, "support.block_channels", True)
    if reported:
        from app.core.slice.findings import analysed

        split = handover.split_for_parts(settings, profile, None, flavour)
        own = profiles.for_process(profile, split.base, effective=True)
        wall, angle = profiles.analysis_limits(own, entry)
        analysed(as_mesh_data(entry.mesh), split.base, angle, wall)
    calls = []
    original = analysis.slice_body

    def measured(*args, **kwargs):
        calls.append(kwargs.get("detail", "full"))
        return original(*args, **kwargs)

    monkeypatch.setattr(analysis, "slice_body", measured)
    written, findings = write_assembly(
        [entry],
        tmp_path,
        project_name="t",
        profile=profile,
        settings=settings,
        flavour=flavour,
        for_slicer=True,
        mesh_plan=({entry.id: as_mesh_data(entry.mesh)}, False),
    )
    assert "export.support_blocker" in {item.code for item in findings}
    if flavour == "orca":
        assert _orca_parts(written) == [("2", "normal_part"), ("2", "support_blocker")]
    elif flavour == "prusa":
        assert [row[0] for row in _blocker_ranges(written)] == ["ModelPart", "SupportBlocker"]
    else:
        assert any(
            dict(mesh.settings).get("anti_overhang_mesh") == "true"
            for mesh in handover.cura_meshes(written)
        )
    assert calls == ([] if reported else ["full"]), (
        "Rat und Sperre benutzen denselben vollständigen Schnitt"
    )


@pytest.mark.parametrize("shared", [False, True])
def test_every_plate_reuses_the_jobs_part_advice(
    tmp_path: Path,
    profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
    shared: bool,
) -> None:
    """N8: Ein übernommener Vorschlag ohne Bedarf fragt jeden Körper nur einmal."""
    objects = [replace(scene_object(f"obj_{n}"), plate=n) for n in range(3)]
    if shared:
        for number, entry in enumerate(objects):
            entry.mesh = objects[0].mesh
            entry.material = ("pla", "petg", "tpu-95a")[number]
    settings = print_settings.with_accepted(
        print_settings.resolve(profile), "adhesion.kind", "brim"
    )
    calls = []
    original = advise.for_part

    def measured(*args, **kwargs):
        calls.append(args[1])
        return original(*args, **kwargs)

    monkeypatch.setattr(advise, "for_part", measured)
    for plate in range(3):
        written, findings = write_assembly(
            objects,
            tmp_path / str(plate),
            project_name="t",
            profile=profile,
            settings=settings,
            plate=plate,
            for_slicer=False,
            job=objects,
        )
        assert written.is_file()
        assert any(item.code == "export.part_setting_all" for item in findings)
    assert len(calls) == len(objects), "die Plattenzahl vervielfacht den Rat nicht"


@pytest.mark.parametrize("checked", [None, []])
def test_a_cancelled_file_export_stops_before_checking_or_writing(
    tmp_path: Path, profile: Profile, checked: list[Finding] | None
) -> None:
    """B9: Auch ohne Rat oder Stützsperre gilt der Abbruch im Dateipfad."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    token = CancelSignal()
    token.cancel()
    with pytest.raises(OperationCancelled):
        write_assembly(
            [scene_object()],
            tmp_path,
            project_name="t",
            profile=profile,
            for_slicer=False,
            checked=checked,
            cancelled=token,
        )
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("phase", ["advice", "payload", "write"])
def test_file_worker_can_cancel_during_part_advice_without_a_window(
    tmp_path: Path,
    profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
    phase: str,
) -> None:
    """B9: Die echten Arbeitermethoden bleiben vor der Schreibgrenze abbrechbar.

    Nur die Qt-Hülle wird weggelassen; der gelesene Methodenrumpf ruft den
    echten Schreiber und den echten Rat auf. Fenster bleiben der Freigabe vorbehalten.
    """
    import ast
    from threading import Lock
    from types import SimpleNamespace

    from app.core.errors import AppError, OperationCancelled
    from app.core.export import manufacturer, writer
    from app.core.scene.cancel import CancelSignal

    source = Path(__file__).parents[1] / "app/ui/main_window.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    worker = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "_ExportWorker"
    )
    methods = [
        node
        for node in worker.body
        if isinstance(node, ast.FunctionDef)
        and node.name in {"work", "cancel", "_assembly", "_begin_write"}
    ]
    isolated = ast.Module(
        body=[
            ast.ImportFrom(module="__future__", names=[ast.alias(name="annotations")], level=0),
            ast.ClassDef(
                name="ExportWorker", bases=[], keywords=[], body=methods, decorator_list=[]
            ),
        ],
        type_ignores=[],
    )
    namespace = {
        "AppError": AppError,
        "OperationCancelled": OperationCancelled,
        "write_assembly": write_assembly,
        "check_before_export": check_before_export,
        "remembered_setup": lambda *_, **__: None,
        "tools": SimpleNamespace(SLICERS=(), slicer_program=lambda: None),
        "manufacturer": manufacturer,
        "prepare_usage": lambda *_: (),
        "handover": handover,
        # Der Übergabebeleg (RM-090) ist Oberfläche; hier zählt nur der Abbruch.
        "handoff_receipt": lambda **_kwargs: None,
        # Seine Gegenprobe ebenso (``test_export_readback.py``).
        "readback": SimpleNamespace(
            read_back=lambda *_args, **_kwargs: None,
            read_back_bodies=lambda *_args, **_kwargs: None,
            expected_for_plan=lambda *_args, **_kwargs: [],
        ),
        "tr": str,
    }
    exec(compile(ast.fix_missing_locations(isolated), str(source), "exec"), namespace)
    instance = namespace["ExportWorker"]()
    events = []
    for name in ("writing", "aborted", "done", "failed", "checked", "usageReady"):
        setattr(
            instance,
            name,
            SimpleNamespace(emit=lambda *args, event=name: events.append((event, args))),
        )
    entry = scene_object()
    instance.__dict__.update(
        _objects=[entry],
        _all_objects=[entry],
        _target=tmp_path / "t.3mf",
        _format="3mf",
        _profile=profile,
        _sources={},
        _settings=print_settings.with_accepted(
            print_settings.resolve(profile), "adhesion.kind", "brim"
        ),
        _ui_settings=None,
        _material="pla",
        _inventory_settings=None,
        _project_name="t",
        _scene=None,
        _document=None,
        _checked=[],
        _evaluated=(),
        _chosen=None,
        cancelled=CancelSignal(),
        _phase_lock=Lock(),
        _writing=False,
        _profiles_for_selection=lambda settings: settings,
    )
    owner, name = {
        "advice": (advise, "for_part"),
        "payload": (threemf, "write_assembly"),
        "write": (writer, "_written"),
    }[phase]
    original = getattr(owner, name)

    def stopped(*args, **kwargs):
        assert instance.cancel() is (phase != "write")
        return original(*args, **kwargs)

    monkeypatch.setattr(owner, name, stopped)
    instance.work()
    if phase == "write":
        assert [name for name, _ in events] == ["writing", "done"]
        assert (tmp_path / "t.3mf").is_file()
    else:
        assert [name for name, _ in events] == ["aborted"]
        assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("changed", ["height", "first", "angle", "wall", "mesh"])
def test_export_layers_follow_every_geometric_input(profile: Profile, changed: str) -> None:
    """Ein gemerkter Exportschnitt ersetzt nur dieselbe Analyse, nie einen anderen Druck."""
    from app.core.export import writer

    entry = scene_object()
    mesh = as_mesh_data(entry.mesh)
    settings = print_settings.resolve(profile)
    first = writer._body_analysis(entry, mesh, settings, profile, None, detail="support")
    full = writer._body_analysis(entry, mesh, settings, profile, None)
    assert first is not full, "die Sparstufe genügt dem vollständigen Rat nicht"
    assert writer._body_analysis(entry, mesh, settings, profile, None, detail="support") is full
    if changed == "mesh":
        mesh.raw.apply_scale(1.1)
    elif changed == "wall":
        settings = print_settings.with_path(settings, "layers.line_width", 0.6)
    else:
        path, value = {
            "height": ("layers.layer_height", 0.3),
            "first": ("layers.first_layer_height", 0.3),
            "angle": ("support.threshold_angle", 20.0),
        }[changed]
        settings = print_settings.with_path(settings, path, value)
    assert writer._body_analysis(entry, mesh, settings, profile, None) is not full


@pytest.mark.parametrize(
    "changed", ["material", "settings", "fits", "accepted", "mesh", "slot_profile", "program"]
)
def test_part_advice_cache_follows_its_inputs(
    profile: Profile, monkeypatch: pytest.MonkeyPatch, changed: str
) -> None:
    """Der Rat überlebt keine geänderte Eingabe; native Profile werden erneut aufgelöst."""
    from app.core.export import writer

    entry = scene_object()
    mesh = as_mesh_data(entry.mesh)
    settings = print_settings.resolve(profile)
    fits = ()
    accepted = {}
    setup = None
    calls = []
    original = advise.for_part

    def measured(*args, **kwargs):
        calls.append(1)
        return original(*args, **kwargs)

    monkeypatch.setattr(advise, "for_part", measured)

    def ask():
        return writer.part_advice(
            entry,
            mesh,
            settings,
            profile,
            setup,
            {},
            result=None,
            fit_kinds=fits,
            accepted=accepted,
            flavour="orca",
        )

    before = ask()
    assert ask() == before
    assert len(calls) == 1
    if changed == "material":
        entry.material = "tpu-95a"
    elif changed == "settings":
        settings = print_settings.with_path(settings, "speed.outer_wall", 200.0)
    elif changed == "fits":
        fits = ("press",)
    elif changed == "accepted":
        accepted["adhesion.kind"] = "brim"
    elif changed == "mesh":
        mesh.raw.apply_scale(1.1)
    elif changed == "slot_profile":
        slot_processes = handover.slot_processes

        def new_profile(*args, **kwargs):
            return tuple(
                replace(
                    item,
                    settings=print_settings.with_path(item.settings, "speed.outer_wall", 200.0),
                )
                for item in slot_processes(*args, **kwargs)
            )

        monkeypatch.setattr(handover, "slot_processes", new_profile)
    else:
        setup = handover.SlicerSetup(Path("SuperSlicer.exe"), "prusa")
    ask()
    assert len(calls) > 1


def test_export_cache_is_not_a_full_report_and_cannot_hide_cancellation(profile: Profile) -> None:
    """Der Exportschnitt ohne Stützvolumen ist kein Bericht; auch warm gilt Abbrechen."""
    from app.core.errors import OperationCancelled
    from app.core.export import writer
    from app.core.scene.cancel import CancelSignal
    from app.core.slice.findings import remembered_analysis

    entry = scene_object()
    mesh = as_mesh_data(entry.mesh)
    settings = print_settings.resolve(profile)
    writer._body_analysis(entry, mesh, settings, profile, None)
    own = profiles.for_process(profile, settings, effective=True)
    wall, angle = profiles.analysis_limits(own, entry)
    assert remembered_analysis(mesh, settings, angle, wall) is None
    token = CancelSignal()
    token.cancel()
    with pytest.raises(OperationCancelled):
        writer._body_analysis(entry, mesh, settings, profile, token)


def test_export_retains_only_the_latest_layers_per_detail(profile: Profile) -> None:
    """Viele Prozesswahlen halten höchstens zwei Schnitte, fremde Merker bleiben bestehen."""
    from app.core.export import writer

    entry = scene_object()
    mesh = as_mesh_data(entry.mesh)
    cache = mesh.raw._cache
    foreign = object()
    cache["unrelated_analysis"] = foreign
    settings = print_settings.resolve(profile)
    for number in range(6):
        current = print_settings.with_path(settings, "layers.layer_height", 0.2 + number * 0.01)
        writer._body_analysis(entry, mesh, current, profile, None, detail="support")
        last = writer._body_analysis(entry, mesh, current, profile, None)
        assert writer._body_analysis(entry, mesh, current, profile, None, detail="support") is last
    own_keys = [key for key in cache.cache if key.startswith("solidon_export_slice|")]
    assert len(own_keys) <= 2, own_keys
    assert cache["unrelated_analysis"] is foreign


def body(name: str = "cube_clean.stl"):
    """Auf dem Bett, wohin ein Teil kurz vor dem Export gehört.

    ``mend=False``: Der Export prüft, was ein Defekt auslöst — ein Import, der
    ihn vorher behebt, nähme den Prüflingen ihren Gegenstand."""
    return place_on_bed(
        normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm", mend=False).mesh
    )


def scene_object(object_id: str = "obj_1", name: str = "Halterung", mesh=None) -> SceneObject:
    return SceneObject(id=object_id, name=name, mesh=mesh or body())


_OLD_RED = MaterialSlot(0, "Rot", (1.0, 0.0, 0.0), material_type="PLA")
_OLD_BLUE = MaterialSlot(1, "Blau", (0.0, 0.0, 1.0), material_type="PLA")
_OLD_UNUSED = MaterialSlot(2, "Alt", (0.0, 1.0, 0.0), material_type="PETG")


def _old_spool_part(*slots, used=(0,), name="Körper", plate=0):
    raw = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    raw.apply_translation((0.0, 0.0, 5.0))
    mesh = MeshData.of(raw, slots=tuple(used[i % len(used)] for i in range(len(raw.faces))))
    return threemf.AssemblyPart(mesh=mesh, slots=slots, name=name, plate=plate)


def _material_bases(payload):
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        model = ET.fromstring(archive.read(threemf.MODEL_PATH))
    return [node.attrib for node in model.iter() if node.tag.endswith("}base")]


@pytest.mark.parametrize("unused_position", [0, 1, 2])
def test_unpainted_old_spool_is_not_an_extruder(unused_position):
    """Altspulen dürfen an keiner Stelle der alten Liste hinausgehen."""
    declared = [_OLD_RED, _OLD_BLUE]
    declared.insert(unused_position, _OLD_UNUSED)
    entry = _old_spool_part(*declared, used=(0, 1))
    assert [(slot.index, str(slot.name)) for slot in threemf.merge_slots([entry])] == [
        (0, "Rot"),
        (1, "Blau"),
    ]
    assert [row["name"] for row in _material_bases(threemf.write_assembly([entry]))] == [
        "Rot",
        "Blau",
    ]


def test_only_remaining_colour_becomes_first_extruder():
    """Alle roten Flächen gelöscht: Blau rückt vor, ohne seine Farbe zu ändern."""
    entry = _old_spool_part(_OLD_RED, _OLD_BLUE, used=(1,))
    assert [(slot.index, str(slot.name)) for slot in threemf.merge_slots([entry])] == [(0, "Blau")]
    assert threemf.tools_in_use([entry]) == (0,)
    with zipfile.ZipFile(BytesIO(threemf.write_assembly([entry]))) as archive:
        model = ET.fromstring(archive.read(threemf.MODEL_PATH))
    assert {node.get("p1") for node in model.iter() if node.tag.endswith("}triangle")} == {"0"}
    assert _material_bases(threemf.write_assembly([entry])) == [
        {"name": "Blau", "displaycolor": "#0000FF"}
    ]


def test_across_numbers_only_used_spools_by_first_actual_occurrence():
    """Eine anderswo verwendete Spule behält ihre Auftragsnummer; Alt entfällt."""
    first = _old_spool_part(_OLD_UNUSED, _OLD_BLUE, _OLD_RED, used=(0,), plate=0)
    second = _old_spool_part(_OLD_UNUSED, _OLD_BLUE, _OLD_RED, used=(1,), plate=1)
    job = [first, second]
    assert [(slot.index, str(slot.name)) for slot in threemf.merge_slots(job)] == [
        (0, "Rot"),
        (1, "Blau"),
    ]
    assert [(slot.index, str(slot.name)) for slot in threemf.merge_slots([second], across=job)] == [
        (1, "Blau")
    ]
    assert threemf.tools_in_use([second], across=job) == (1,)
    assert [
        row["name"] for row in _material_bases(threemf.write_assembly([second], across=job))
    ] == ["Slot 0", "Blau"]


def test_used_but_undeclared_slot_stays_neutral():
    """Fehlende Deklaration darf die echte Bemalung nicht unterschlagen."""
    entry = _old_spool_part(_OLD_UNUSED, used=(7,))
    merged = threemf.merge_slots([entry])
    assert len(merged) == 1
    assert (
        merged[0].colour is None and merged[0].material is None and merged[0].material_type is None
    )
    assert str(merged[0].name) == "Slot 7"
    assert threemf.tools_in_use([entry]) == (0,)


def test_colourless_body_keeps_one_neutral_tool():
    """Ein Körper ohne Spulen bleibt druckbar."""
    raw = MeshData.of(trimesh.creation.box())
    entry = threemf.AssemblyPart(raw)
    slots = threemf.merge_slots([entry])
    assert len(slots) == 1 and slots[0].material_type is None
    assert threemf.tools_in_use([entry]) == (0,)


def test_same_colour_with_different_material_keeps_both_tools():
    """Filamentidentität bleibt die bestehende gemeinsame Regel."""
    other = replace(_OLD_RED, material_type="PETG")
    entries = [_old_spool_part(_OLD_RED), _old_spool_part(other)]
    assert [slot.material_type for slot in threemf.merge_slots(entries)] == ["PLA", "PETG"]


def test_legacy_profile_positions_are_bound_before_unused_slots_disappear():
    """Blau erhält sein gespeichertes Profil und niemals das der unbemalten roten Spule."""
    entry = _old_spool_part(_OLD_RED, _OLD_BLUE, used=(1,))
    body = SceneObject(id="one", name="Körper", mesh=entry.mesh, material_slots=entry.slots)
    settings = replace(
        print_settings.resolve(profiles.make_profile()),
        slot_profiles=("Altes rotes Profil", "Eigenes blaues Profil"),
        slot_profile_bindings=None,
    )
    assert handover.chosen_slot_profiles([body], settings) == {
        threemf.slot_identity(_OLD_BLUE): "Eigenes blaues Profil"
    }


def test_identity_bound_profiles_survive_removal_and_new_indices():
    """Bereits gebundene Profilwahl wird nicht erneut über ihre Nummer gelesen."""
    entry = _old_spool_part(_OLD_RED, _OLD_BLUE, used=(1,))
    body = SceneObject(id="one", name="Körper", mesh=entry.mesh, material_slots=entry.slots)
    binding = SlotProfileBinding(
        profile_name="Eigenes blaues Profil",
        name=_OLD_BLUE.name,
        colour=_OLD_BLUE.colour,
        material=_OLD_BLUE.material,
        material_type=_OLD_BLUE.material_type,
    )
    settings = replace(
        print_settings.resolve(profiles.make_profile()),
        slot_profiles=("Falsches altes Profil",),
        slot_profile_bindings=(binding,),
    )
    assert handover.chosen_slot_profiles([body], settings) == {
        threemf.slot_identity(_OLD_BLUE): "Eigenes blaues Profil"
    }


@pytest.mark.parametrize("flavour", ["orca", "prusa"])
def test_normal_export_does_not_deliver_or_warn_about_an_unused_spool(tmp_path, flavour):
    """Der normale Exportanschluss liefert eine Spule und keinen falschen Materialbefund."""
    entry = _old_spool_part(_OLD_UNUSED, _OLD_RED, used=(0,))
    body = SceneObject(id="one", name="Körper", mesh=entry.mesh, material_slots=entry.slots)
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    path, findings = write_assembly(
        [body],
        tmp_path,
        project_name="Altspule",
        profile=profile,
        settings=settings,
        flavour=flavour,
    )
    assert [row["name"] for row in _material_bases(path.read_bytes())] == ["Rot"]
    assert "slicer.overrides_unreachable" not in {finding.code for finding in findings}
    if flavour == "orca":
        with zipfile.ZipFile(path) as archive:
            settings = json.loads(archive.read(threemf.PROJECT_SETTINGS_PATH))
        assert settings["filament_type"] == ["PLA"]


# --- naming ---------------------------------------------------------------------


def test_names_stay_recognisable_while_becoming_safe() -> None:
    """§29: file-system-safe without becoming unreadable."""
    assert safe_name("Gehäuse oben") == "Gehaeuse_oben"
    assert safe_name("Halter/2") == "Halter2"
    assert safe_name("Größe: 20mm") == "Groesse_20mm"
    assert safe_name("") == "teil"


def test_a_single_part_gets_a_plain_name(profile: Profile) -> None:
    plan = plan_export([scene_object()], project_name="Projekt", profile=profile)

    assert [entry.filename for entry in plan.entries] == ["Projekt_Halterung.stl"]


def test_several_parts_are_numbered(profile: Profile) -> None:
    """§29: bei drei Teilen auf einer Platte will man sehen, welches welches
    ist.
    """
    objects = [
        scene_object("obj_1", "Deckel"),
        scene_object("obj_2", "Boden"),
        scene_object("obj_3", "Ring"),
    ]
    plan = plan_export(objects, project_name="Dose", profile=profile)

    assert [entry.filename for entry in plan.entries] == [
        "Dose_Deckel_1von3.stl",
        "Dose_Boden_2von3.stl",
        "Dose_Ring_3von3.stl",
    ]


def test_the_scheme_can_be_changed(profile: Profile) -> None:
    plan = plan_export(
        [scene_object()], project_name="P", profile=profile, scheme="{object}-{index}"
    )
    assert plan.entries[0].filename == "Halterung-1.stl"


def test_two_parts_that_would_share_a_name_are_numbered(profile: Profile) -> None:
    """H2: zwei Objekte, die auf denselben Dateinamen fallen, überschrieben
    sich — eine Datei, zwei Erfolgsmeldungen, das erste Teil weg. Ein Schema
    ohne unterscheidendes Feld (hier ``{object}`` bei zwei gleichnamigen Körpern)
    bekommt jetzt eine laufende Nummer, statt sich zu überschreiben.
    """
    objects = [scene_object("obj_1", "Halterung"), scene_object("obj_2", "Halterung")]

    plan = plan_export(objects, project_name="P", profile=profile, scheme="{object}")

    names = [entry.filename for entry in plan.entries]
    assert names == ["Halterung-1.stl", "Halterung-2.stl"]
    assert len(set(names)) == 2, "keine zwei Dateien mit demselben Namen"


def test_a_typo_in_the_scheme_names_the_placeholders(profile: Profile) -> None:
    """``--scheme "{name}"`` endete in einem rohen ``KeyError``.

    Das Schema ist eine Eingabe des Nutzers — in der Kommandozeile getippt, im
    Dialog eingetragen —, und der Platzhalter heißt ``{object}``. Ein
    Stapelabzug sagt ihm das nicht; er sagt ihm nicht einmal, dass er selbst
    etwas ändern kann (§2.7, Regel 17).
    """
    with pytest.raises(ValidationError) as falsch:
        plan_export(
            [scene_object()],
            project_name="Projekt",
            profile=profile,
            scheme="{name}_{index}",
        )

    assert falsch.value.field == "scheme"
    assert falsch.value.values["requested"] == "{name}"
    known = str(falsch.value.values["known"])
    for platzhalter in ("{project}", "{object}", "{index}", "{count}", "{plate}"):
        assert platzhalter in known, platzhalter
    assert falsch.value.suggestions


def test_a_scheme_with_a_stray_brace_says_so(profile: Profile) -> None:
    """Der zweite Weg, dasselbe falsch zu tippen — und er wirft eine andere
    Ausnahme, die genauso roh durchflog."""
    with pytest.raises(ValidationError) as kaputt:
        plan_export([scene_object()], project_name="Projekt", profile=profile, scheme="{project")

    assert kaputt.value.constraint == "broken_scheme"
    assert kaputt.value.suggestions


def test_exporting_nothing_is_a_user_error(profile: Profile) -> None:
    with pytest.raises(ValidationError) as caught:
        plan_export([], project_name="P", profile=profile)
    assert caught.value.suggestions


# --- die Prüfung ----------------------------------------------------------------


def test_a_clean_part_has_nothing_to_report(profile: Profile) -> None:
    assert check_before_export([scene_object()], profile, {}) == []


def test_the_check_before_export_repeats_a_pierced_sculpt_stroke(profile: Profile) -> None:
    """Ein Formzug, der die Wand durchstochen hat, stand im Prüfbericht — der
    Export lief ohne Hinweis (RM-419). Die Prüfung vor dem Schreiben sagt ihn
    weiter, für die Körper, die geschrieben werden."""
    from app.core.types import Finding

    pierced = Finding(code="sculpt.pierced", severity="warning", message="", object_id="obj_1")
    elsewhere = Finding(code="sculpt.pierced", severity="warning", message="", object_id="obj_9")
    unrelated = Finding(code="sculpt.applied", severity="info", message="", object_id="obj_1")

    findings = check_before_export(
        [scene_object()], profile, {}, evaluated=[pierced, elsewhere, unrelated]
    )

    assert findings == [pierced]


def test_a_part_below_the_bed_is_reported(profile: Profile) -> None:
    """Der Bauraum beginnt bei Z = 0; ein halber Würfel darunter ist es wert,
    gesagt zu werden.
    """
    sunk = normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh
    findings = check_before_export([scene_object(mesh=sunk)], profile, {})

    assert "arrange.below_bed" in {finding.code for finding in findings}


def test_a_part_below_the_bed_is_not_called_too_big(profile: Profile) -> None:
    """Der häufigste Fall von Weg 1 bekam den irreführendsten Satz.

    Ein heruntergeladenes Teil ist meist um den Ursprung zentriert und liegt
    darum zur Hälfte unter der Platte — ein 8 mm hohes Teil auf einem
    256-mm-Drucker. „Steht über den Bauraum hinaus" schickt den Nutzer zum
    Skalieren, obwohl ein Aufsetzen genügt.

    **Und die Kennung sagt es mit.** Sie tat es nicht, und der Prüfbericht
    hängt seine Handlungen an ihr auf: Damit bekam der verrutschte Körper
    *Modell teilen* und *Auf den Bauraum verkleinern* angeboten — zwei
    Handlungen, die hier nichts ausrichten (``FINDING_ACTIONS``).
    """
    sunk = normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh
    findings = check_before_export([scene_object(mesh=sunk)], profile, {})

    said = str(next(f.message for f in findings if f.code == "arrange.below_bed"))
    assert "unter dem Druckbett" in said
    assert "hinaus" not in said, "das ist der Satz für zu groß"
    assert "arrange.out_of_build_volume" not in {f.code for f in findings}, (
        "the too-big code belongs to the case that really is too big"
    )


def test_a_part_that_really_is_too_big_still_says_so(profile: Profile) -> None:
    """Die Unterscheidung darf den echten Fall nicht verschlucken."""
    huge = read_mesh((MESHES / "oversized.stl").read_bytes(), ".stl")
    findings = check_before_export([scene_object(mesh=place_on_bed(huge))], profile, {})

    said = str(next(f.message for f in findings if f.code == "arrange.out_of_build_volume"))
    assert "hinaus" in said


def test_an_open_part_is_reported_but_not_blocked(profile: Profile) -> None:
    """§29: wer trotzdem exportieren will, kann das — er weiß dann nur, was er
    tut.
    """
    open_body = place_on_bed(
        normalise(
            read_mesh((MESHES / "broken_open.stl").read_bytes(), ".stl"), "mm", mend=False
        ).mesh
    )
    plan = plan_export([scene_object(mesh=open_body)], project_name="P", profile=profile)

    codes = {finding.code for finding in plan.findings}
    assert "export.not_watertight" in codes
    assert not plan.blocked
    assert plan.entries, "the file would still be written"


def test_a_part_outside_the_build_volume_is_reported(profile: Profile) -> None:
    """Ein Würfel 400 mm neben dem Bett wird gemeldet — und zwar als **Lage**.

    Er ist 20 mm groß und passt zehnmal auf das Bett; was hilft, ist ein Klick
    auf *Auf dem Bett anordnen*. „Steht über den Bauraum hinaus" hieße „zu
    groß" und bot *Modell teilen* und *Verkleinern* an (``_fits_at_all``).
    """
    far = apply(body(), translation((400.0, 0.0, 0.0)))
    findings = check_before_export([scene_object(mesh=far)], profile, {})

    assert "arrange.off_the_plate" in {finding.code for finding in findings}
    assert "arrange.out_of_build_volume" not in {finding.code for finding in findings}


def test_before_writing_a_misplaced_part_is_a_warning(profile: Profile) -> None:
    """Derselbe Körper, zwei Anlässe, zwei Schweregrade — und das ist Absicht.

    Im Editor ist eine falsche Lage ein Hinweis: ein Klick auf *Auf dem Bett
    anordnen* behebt sie, und stünde dort eine Warnung, warnte fast jede
    geladene Datei (`_severity_for`). Vor dem **Schreiben** fällt genau diese
    Voraussetzung weg — der Klick ist nicht passiert, und was jetzt entsteht,
    ist eine Datei. Gemessen: CuraEngine prüft den Bauraum nicht und schreibt
    eine Druckdatei, die neben der Platte druckt.

    Gesperrt wird trotzdem nichts (§29) — der Befund steht nur nicht mehr
    zwischen zwei Dutzend Hinweisen.
    """
    verschoben = apply(body(), translation((400.0, 0.0, 0.0)))
    im_editor = check_build_volume([verschoben], profile)
    vor_dem_schreiben = check_before_export([scene_object(mesh=verschoben)], profile, {})

    assert [finding.severity for finding in im_editor] == ["info"], "im Editor behebt ein Klick es"
    schwer = [
        finding.severity for finding in vor_dem_schreiben if finding.code == "arrange.off_the_plate"
    ]
    assert schwer == ["warning"], vor_dem_schreiben


def test_the_licence_of_a_source_is_mentioned_once(profile: Profile) -> None:
    """§16.3: once, factual, without a lecture."""
    sources = {
        "src_1": Source(
            id="src_1",
            kind="import",
            path="sources/a.stl",
            sha256="",
            origin=SourceOrigin(title="Halterung", licence="CC BY-NC 4.0"),
        )
    }
    findings = check_before_export([scene_object()], profile, sources)
    licence_findings = [f for f in findings if f.code == "export.source_licence"]

    assert len(licence_findings) == 1
    assert licence_findings[0].severity == "info"
    assert "CC BY-NC 4.0" in str(licence_findings[0].values["sources"])


# --- die zwei Fragen, die kein Körper allein beantwortet (§29, RM-140) ----------


def _tube_scene(profile: Profile, inner: float, outer: float) -> tuple[Scene, SceneObject]:
    """Ein Rohr als Szene — das kleinste Teil, an dem eine Wand entsteht."""
    from app.core.perceive.features import detect

    mesh = MeshData.of(
        trimesh.creation.annulus(r_min=inner / 2.0, r_max=outer / 2.0, height=20.0, sections=96)
    )
    entry = SceneObject(id="obj_1", name="Rohr", mesh=mesh, features=detect(mesh))
    return Scene(objects={"obj_1": entry}, profile=profile), entry


def test_a_wall_too_thin_to_print_is_named_before_the_file_exists(profile: Profile) -> None:
    """§29 zählt „keine Dünnstellen unter der Mindestwandstärke" auf.

    Die Zeile stand seit je im Bauplan und in keiner Prüfung: Eine Wand steht
    nicht in einem Körper, sondern zwischen einer Bohrung und dem Mantel um
    sie herum — und die Prüfung sah nur die Auswahl. Mit der Szene sieht sie
    das Verhältnis.
    """
    scene, entry = _tube_scene(profile, inner=19.0, outer=20.0)

    findings = check_before_export([entry], profile, {}, scene=scene)

    assert "perceive.thin_wall" in {finding.code for finding in findings}


def test_without_the_scene_the_export_makes_nothing_up(profile: Profile) -> None:
    """Die Gegenprobe, und sie ist zugleich die Zusage aus Regel 21.

    Ein Aufrufer ohne Szene — die Kommandozeile hatte lange keine — bekommt
    den Bericht, den er belegen kann. Geraten wird nichts.
    """
    _scene, entry = _tube_scene(profile, inner=19.0, outer=20.0)

    findings = check_before_export([entry], profile, {})

    assert "perceive.thin_wall" not in {finding.code for finding in findings}


def test_a_violated_fit_is_named_before_the_file_exists(profile: Profile) -> None:
    """Die zweite Zeile aus §29: „keine verletzten Passungen".

    Gemessen an einer Bohrung, die kleiner ist als ihr Stift — das Teil lässt
    sich fügen, sobald man es mit einem Hammer meint.
    """
    from tests.test_digest_and_fits import clearance_fit, pin_and_hole

    scene = pin_and_hole(4.9, 5.0, profile)
    scene.fits.append(clearance_fit())

    findings = check_before_export(list(scene.objects.values()), profile, {}, scene=scene)

    assert [finding.code for finding in findings if finding.code.startswith("fit.")], (
        "eine Passung, die nicht aufgeht, gehört vor die Datei und nicht dahinter"
    )


def test_a_fit_is_reported_for_either_partner_but_not_an_unrelated_body(profile: Profile) -> None:
    """Eine Beziehung betrifft auch den einzeln exportierten Stift.

    Gefragt wird trotzdem an der **ganzen** Szene: Die zweite Hälfte einer
    Passung mag außen vor bleiben, aufgelöst werden muss sie dennoch — sonst
    käme „Merkmal verloren" zurück, und das ist eine andere Aussage.
    """
    from tests.test_digest_and_fits import clearance_fit, pin_and_hole

    scene = pin_and_hole(4.9, 5.0, profile)
    scene.fits.append(clearance_fit())
    ohne = [entry for key, entry in scene.objects.items() if key != "obj_1"]

    findings = check_before_export(ohne, profile, {}, scene=scene)

    codes = [finding.code for finding in findings if finding.code.startswith("fit.")]
    assert "fit.violated" in codes
    unrelated = replace(scene.objects["obj_2"], id="obj_3", features={})
    scene.objects[unrelated.id] = unrelated
    findings = check_before_export([unrelated], profile, {}, scene=scene)
    assert not [finding.code for finding in findings if finding.code.startswith("fit.")]


def test_a_report_that_was_already_taken_is_not_taken_twice(
    tmp_path: Path, profile: Profile
) -> None:
    """``checked`` schreibt mit dem Bericht, den der Kunde gesehen hat (RM-140).

    Die Prüfung ist der teure Teil des Exports; zweimal zu prüfen hieße, den
    Kunden zweimal warten zu lassen — und ein zweites Ergebnis wäre auch ein
    zweiter Zustand. Gemessen wird an einer Zusage, die kein zweiter Lauf
    erzeugen würde.
    """
    fremd = [
        Finding(code="export.not_watertight", severity="warning", message="aus dem ersten Lauf")
    ]
    plan = plan_export([scene_object()], project_name="Dose", profile=profile, checked=fremd)

    assert [finding.message for finding in plan.findings] == ["aus dem ersten Lauf"]
    assert write_plan(plan, tmp_path)


# --- writing --------------------------------------------------------------------


def test_writing_produces_readable_files(tmp_path: Path, profile: Profile) -> None:
    plan = plan_export(
        [scene_object("obj_1", "Deckel"), scene_object("obj_2", "Boden")],
        project_name="Dose",
        profile=profile,
    )
    written = write_plan(plan, tmp_path)

    assert len(written) == 2
    for path in written:
        assert path.is_file()
        reread = read_mesh(path.read_bytes(), ".stl")
        assert reread.triangle_count == 12


def test_two_same_named_parts_write_two_files(tmp_path: Path, profile: Profile) -> None:
    """Die Kollisionsauflösung schreibt wirklich zwei Dateien — nicht eine, über
    die zweimal Erfolg gemeldet wird."""
    objects = [scene_object("obj_1", "Halterung"), scene_object("obj_2", "Halterung")]
    plan = plan_export(objects, project_name="P", profile=profile, scheme="{object}")

    written = write_plan(plan, tmp_path)

    assert len(written) == 2
    assert len(set(written)) == 2, "zwei verschiedene Pfade"
    assert len(list(tmp_path.glob("*.stl"))) == 2, "zwei Dateien auf der Platte"


@pytest.mark.parametrize("export_format", ["stl", "3mf", "obj", "ply", "glb"])
def test_every_format_writes_something_readable(export_format: str, profile: Profile) -> None:
    data = export_bytes(body(), export_format)  # type: ignore[arg-type]

    assert data, f"{export_format} produced no bytes"
    if export_format in ("stl", "obj", "ply", "3mf", "glb"):
        suffix = f".{export_format}"
        assert read_model(data, suffix).triangle_count == 12


def test_glb_keeps_the_measurements_it_was_given() -> None:
    """§29: Ein GLB ist zum Zeigen da — und was es zeigt, muss stimmen.

    Der glTF-2.0-Standard verlangt in seinem Abschnitt 3.5 ein Y-oben-Format,
    Solidon rechnet Z-oben, und der
    Schreiber dreht deshalb (``writer._glb_bytes``). Der Leser dreht
    **bewusst nicht** zurück — die Begründung steht in ``read_mesh`` —, also
    kommt die Höhe auf der Y-Achse wieder herein. Der Körper selbst bleibt
    derselbe: gleiche Dreiecke, gleiches Volumen, dieselben drei Kantenmaße.

    Gemessen an einem Quader statt am Würfel des Korpus: Bei drei gleichen
    Kanten ist jede Drehung unsichtbar, und der Test bliebe grün, gleich wie
    oft jemand dreht.
    """
    original = MeshData.of(trimesh.creation.box(extents=(10.0, 20.0, 40.0)))
    back = read_mesh(export_bytes(original, "glb"), ".glb")

    assert back.triangle_count == original.triangle_count
    # In Metern, seit dem 05.09.2026 (CORE-33): der Leser skaliert bewusst nicht
    # zurück, die Einheit fragt die Eingangsstufe.
    assert back.volume == pytest.approx(original.volume * 1e-9, rel=1e-6)
    assert back.bounds.size == pytest.approx((0.010, 0.040, 0.020), abs=1e-9)


def test_glb_carries_the_slot_colours() -> None:
    """§20: Ein zweifarbiges Teil, das grau ankommt, zeigt nicht, wofür man
    es verschickt hat."""
    plain = body()
    two_tone = MeshData(raw=plain.raw, slots=tuple(0 if index < 6 else 1 for index in range(12)))
    slots = [
        MaterialSlot(index=0, name="Grundkörper", colour=(1.0, 0.0, 0.0)),
        MaterialSlot(index=1, name="Schrift", colour=(0.0, 0.0, 1.0)),
    ]

    written = trimesh.load_mesh(
        BytesIO(export_bytes(two_tone, "glb", slots=slots, name="Schild")),
        file_type="glb",
    )
    seen = {tuple(colour[:3]) for colour in written.visual.face_colors}

    assert (255, 0, 0, 255)[:3] in seen
    assert (0, 0, 255, 255)[:3] in seen


def test_a_single_colour_stays_undecided() -> None:
    """Ein Teil ohne Materialslots bekommt keine erfundene Farbe."""
    data = export_bytes(body(), "glb", slots=[MaterialSlot(index=0, name="PLA")])

    assert read_mesh(data, ".glb").triangle_count == 12


def test_a_name_keeps_its_alphabet() -> None:
    """§29: sicher, nicht von allem befreit, was nicht englisch ist.

    Der Export zwang früher den ganzen Namen durch ASCII: ein
    heruntergeladenes ``埃菲尔铁塔18cm`` kam als ``18cm`` heraus und ein
    ``Соединитель`` als ``teil``.
    """
    assert safe_name("埃菲尔铁塔18cm") == "埃菲尔铁塔18cm"
    assert safe_name("Соединитель") == "Соединитель"
    assert safe_name("Boîtier") == "Boîtier", "a French accent is not a hazard either"


def test_what_is_actually_unsafe_still_goes() -> None:
    """Der Teil, der immer richtig war: Trenner und reservierte Satzzeichen."""
    assert safe_name(r"a/b\c") == "abc"
    assert safe_name('Teil: "gross" <1>') == "Teil_gross_1"
    assert safe_name("*?|") == "teil", "and nothing left over is still the fallback"


# --- Baugruppe: alles einer Platte in eine Datei (§20, §29) -------------------------


def test_an_assembly_is_one_file_for_every_object(tmp_path: Path, profile: Profile) -> None:
    """Der Unterschied zu ``write_plan`` ist nicht das Format, sondern die Zahl
    der Dateien: der Slicer bekommt einen Druckauftrag statt einer Handvoll
    Teile, über deren Zusammengehörigkeit er selbst entscheiden müsste."""
    objects = [scene_object("obj_1", "Deckel"), scene_object("obj_2", "Boden")]

    written, _findings = write_assembly(objects, tmp_path, project_name="Gehäuse", profile=profile)

    assert written.suffix == ".3mf"
    assert len(list(tmp_path.glob("*.3mf"))) == 1
    assert threemf_reader.count_objects(written.read_bytes()) == 2


def test_the_assembly_carries_the_object_names(tmp_path: Path, profile: Profile) -> None:
    objects = [scene_object("obj_1", "Deckel"), scene_object("obj_2", "Boden")]

    written, _findings = write_assembly(objects, tmp_path, project_name="x", profile=profile)

    assert [part.name for part in threemf_reader.read_objects(written.read_bytes())] == [
        "Deckel",
        "Boden",
    ]


def test_only_the_named_plate_goes_into_the_file(tmp_path: Path, profile: Profile) -> None:
    """Mehr Teile, als auf eine Platte passen, ist normal (§25) — aber eine
    Druckdatei ist eine Platte."""
    erste = scene_object("obj_1", "Vorne")
    zweite = scene_object("obj_2", "Naechste")
    zweite.plate = 1
    objects = [erste, zweite]

    written, _findings = write_assembly(
        objects, tmp_path, project_name="x", profile=profile, plate=0
    )

    assert threemf_reader.count_objects(written.read_bytes()) == 1


def test_without_a_named_plate_every_plate_goes_in(tmp_path: Path, profile: Profile) -> None:
    """Und ohne Einschränkung kommen alle hinein — mit ihrer Platte dazu.

    Die Orca-Familie legt ihre Platten in einem Koordinatenraum nebeneinander.
    Ohne den Versatz stünde die zweite auf der ersten: Beide fangen am selben
    Bettursprung an, und am modularen Besteckkorb überlagerten sich zwei
    Platten um neunundzwanzig Millimeter.

    Der Abstand ist gemessen und nicht gewählt — siehe ``SLICER_PLATE_GAP``. Hier
    steht die Gegenprobe: Zwei gleiche Teile auf zwei Platten liegen um genau
    eine Bettbreite plus ein Fünftel auseinander.
    """
    erste = scene_object("obj_1", "Vorne")
    zweite = scene_object("obj_2", "Naechste")
    zweite.plate = 1

    written, _findings = write_assembly(
        [erste, zweite], tmp_path, project_name="x", profile=profile
    )

    payload = written.read_bytes()
    assert threemf_reader.count_objects(payload) == 2, "beide Teile in einer Datei"

    beilage = zipfile.ZipFile(BytesIO(payload)).read(threemf.SETTINGS_PATH).decode("utf-8")
    assert beilage.count("<plate>") == 2, "und beide Platten benannt"

    # Die erste Platte steht, wo sie steht, und bekommt gar keine Matrix — eine
    # Verschiebung um null wäre eine Angabe ohne Aussage. Verschoben ist nur,
    # was auf die zweite gehört.
    model = zipfile.ZipFile(BytesIO(payload)).read(threemf.MODEL_PATH).decode("utf-8")
    offsets = [float(entry.split()[9]) for entry in re.findall(r'transform="([^"]+)"', model)]
    width = profile.printer.build_volume[0]
    assert offsets == [pytest.approx(width * (1.0 + threemf.SLICER_PLATE_GAP))]


def test_plates_go_into_the_grid_of_the_slicer(tmp_path: Path, profile: Profile) -> None:
    """Vier Platten sind beim Slicer ein Quadrat, fünf brauchen drei Spalten.

    **Roberts Bild aus dem ElegooSlicer** (11.09.2026: „so ganz passt die
    ausrichtung an den platten von den druckern bei den slicern nicht"): Die
    Buchstaben der Platten 3 und 4 lagen rechts neben allem, Platte 03 und 04
    standen leer **unter** 01 und 02. Solidon reihte die Platten auf, der
    Slicer legt sie ins Raster — ``ceil(sqrt(n))`` Spalten, die Zeilen nach
    unten, ein Fünftel Luft (``PartPlate.cpp``; gemessen am installierten
    Slicer, siehe ``SLICER_PLATE_GAP``).

    Gemessen wird an der Matrix in der Datei: Platte 3 von 4 steht bei
    (0, −Tiefe·1,2), Platte 4 rechts daneben; bei fünf Platten liegt die
    dritte noch in der ersten Zeile.
    """
    width, depth, _height = profile.printer.build_volume
    pitch = 1.0 + threemf.SLICER_PLATE_GAP

    def offsets_of(count: int) -> list[tuple[float, float]]:
        objects = []
        for plate in range(count):
            entry = scene_object(f"obj_{plate + 1}", f"Teil {plate + 1}")
            entry.plate = plate
            objects.append(entry)
        written, _findings = write_assembly(
            objects, tmp_path, project_name=f"raster{count}", profile=profile
        )
        model = zipfile.ZipFile(BytesIO(written.read_bytes())).read(threemf.MODEL_PATH)
        found = {}
        for item in re.findall(
            r"<item objectid=\"(\d+)\"(?: transform=\"([^\"]+)\")?", model.decode()
        ):
            values = item[1].split() if item[1] else ["0"] * 12
            found[int(item[0]) - 2] = (float(values[9]), float(values[10]))
        return [found[index] for index in range(count)]

    four = offsets_of(4)
    assert four[0] == (0.0, 0.0)
    assert four[1] == pytest.approx((width * pitch, 0.0)), "die zweite rechts daneben"
    assert four[2] == pytest.approx((0.0, -depth * pitch)), "die dritte darunter, nicht rechts"
    assert four[3] == pytest.approx((width * pitch, -depth * pitch))

    five = offsets_of(5)
    assert five[2] == pytest.approx((2 * width * pitch, 0.0)), "fünf Platten: drei Spalten"
    assert five[3] == pytest.approx((0.0, -depth * pitch))

    # Und die Plattenblöcke zählen durch, wie der Slicer zählt.
    beilage = zipfile.ZipFile(BytesIO((tmp_path / "raster5.3mf").read_bytes())).read(
        threemf.SETTINGS_PATH
    )
    assert re.findall(r'plater_id" value="(\d+)"', beilage.decode()) == ["1", "2", "3", "4", "5"]


def test_an_empty_plate_says_so(tmp_path: Path, profile: Profile) -> None:
    with pytest.raises(ValidationError):
        write_assembly([scene_object()], tmp_path, project_name="x", profile=profile, plate=7)


def test_the_assembly_reports_before_writing(tmp_path: Path, profile: Profile) -> None:
    """§29: die Prüfung vor dem Export berichtet, sie blockiert nicht."""
    objects = [scene_object("obj_1", "Teil", mesh=body("broken_open.stl"))]

    written, findings = write_assembly(objects, tmp_path, project_name="x", profile=profile)

    assert written.is_file(), "geschrieben wird trotzdem"
    assert findings, "aber der Befund steht dabei"


@pytest.mark.parametrize("flavour", ["orca", "cura"])
def test_an_assembly_that_cannot_be_written_names_the_way_out(
    tmp_path: Path, profile: Profile, flavour: str
) -> None:
    """Ein ``OSError`` ist kein Programmfehler, sondern ein Ziel, das nicht
    geht (§2.7).

    ``write_plan`` wandelt ihn seit je; die Baugruppe daneben tat es nicht —
    dieselbe Handlung, zwei Antworten. In der Kommandozeile endete sie in
    einem Stapelabzug, im Fenster stiller und schlimmer: Der Export-Arbeiter
    fängt ``AppError``, ein ``OSError`` riss den Thread ab, und danach geschah
    gar nichts mehr.

    Beide Wege, denn es sind zwei Schreibstellen: die Orca-Familie bekommt
    eine 3MF, CuraEngine ein STL.
    """
    versperrt = tmp_path / "platte"
    versperrt.write_bytes(b"eine Datei, kein Ordner")

    with pytest.raises(FileWriteError) as gescheitert:
        write_assembly(
            [scene_object()],
            versperrt,
            project_name="Projekt",
            profile=profile,
            flavour=flavour,  # type: ignore[arg-type]
        )

    assert gescheitert.value.suggestions, "Regel 17"
    assert gescheitert.value.detail, "der Grund des Betriebssystems steht dabei"


# --- Einstellungen je Teil (§29, Stufe 4) -------------------------------------------


def test_the_assembly_carries_the_part_names_where_the_slicer_reads_them() -> None:
    """Der Standard hat ein ``name``-Attribut am Objekt, und Solidon schreibt
    es auch — aber die Orca-Familie schreibt es selbst nie und liest die Namen
    aus ``model_settings.config``. Ohne diese Beilage kam eine Baugruppe als
    „Object 1, Object 2" an, obwohl die Namen in der Datei standen.
    """
    parts = [
        threemf.AssemblyPart(mesh=MeshData.of(trimesh.creation.box((10, 10, 10))), name="Behälter"),
        threemf.AssemblyPart(mesh=MeshData.of(trimesh.creation.box((5, 5, 5))), name="Deckel"),
    ]

    payload = threemf.write_assembly(parts, "Gewürzset")

    with zipfile.ZipFile(BytesIO(payload)) as container:
        config = container.read(threemf.SETTINGS_PATH).decode("utf-8")
    assert 'key="name" value="Behälter"' in config
    assert 'key="name" value="Deckel"' in config


def test_a_prusa_assembly_carries_its_settings(tmp_path: Path, profile: Profile) -> None:
    """Eine exportierte 3MF soll man drucken können, nicht erst einrichten.

    Für die Orca-Familie war das längst so; für PrusaSlicer trug dieselbe
    Datei nur Geometrie, und beim Öffnen galt das Profil, das gerade
    eingestellt war. Er liest seine Einstellungen aus einer eigenen Beilage —
    gemessen: ohne ``--load`` geslict kamen Solidons Werte an.
    """
    settings = print_settings.resolve(profile)
    target, _findings = write_assembly(
        [scene_object()],
        tmp_path,
        project_name="Halter",
        profile=profile,
        settings=settings,
        flavour="prusa",
    )

    with zipfile.ZipFile(target) as container:
        config = container.read(threemf.PRUSA_CONFIG_PATH).decode("utf-8")
    lines = config.splitlines()
    assert lines[0] == threemf.PRUSA_CONFIG_HEADER, (
        "die erste Zeile überspringt PrusaSlicer — ohne Kopf fehlt der erste Wert"
    )
    written = {
        line.split("=", 1)[0].removeprefix(";").strip(): line.split("=", 1)[1].strip()
        for line in lines[1:]
        if "=" in line
    }
    assert written["perimeters"] == str(settings.shell.wall_count)
    assert written["first_layer_temperature"] == str(settings.temperature.nozzle_first_layer)


def test_a_filament_keeps_its_extruder_across_the_plates_of_one_job() -> None:
    """Vier Spulen sind nicht vier Farben desselben Materials — und eine Farbe
    ist nicht auf jeder Platte ein anderer Extruder.

    ``merge_slots`` nummeriert nach dem ersten Auftreten, und der Export ruft
    es **je Platte**. Damit lag dieselbe Farbe in einem Auftrag an
    verschiedenen Düsen: Platte 1 nur Rot (Extruder 0), Platte 2 Weiß und Rot
    (Rot dann Extruder 1). Wer den Auftrag am Stück druckt, müsste mittendrin
    umstecken — und merkt es an der zweiten Platte.

    Die Zuordnung gehört deshalb dem **Auftrag**: Wer alle Platten kennt,
    nummeriert einmal für alle. ``across`` nimmt die Teile des ganzen Auftrags
    und gibt die gemeinsame Belegung; ohne Angabe bleibt es beim alten
    Verhalten je Platte, denn eine einzelne exportierte Platte *ist* der
    Auftrag.
    """
    red = MaterialSlot(index=1, name="Rot")
    white = MaterialSlot(index=1, name="Weiß")
    red_again = MaterialSlot(index=2, name="Rot")

    box = trimesh.creation.box()
    first = [
        threemf.AssemblyPart(
            mesh=MeshData.of(box, slots=(1,) * len(box.faces)), name="A", slots=(red,)
        )
    ]
    second = [
        threemf.AssemblyPart(
            mesh=MeshData.of(box, slots=(1, 2) * (len(box.faces) // 2)),
            name="B",
            slots=(white, red_again),
        )
    ]

    whole_job = [*first, *second]
    plate_one = threemf.merge_slots(first, across=whole_job)
    plate_two = threemf.merge_slots(second, across=whole_job)

    def extruder_of(name: str, slots: list[MaterialSlot]) -> int:
        return next(slot.index for slot in slots if str(slot.name) == name)

    assert extruder_of("Rot", plate_one) == extruder_of("Rot", plate_two), (
        "dieselbe Farbe, derselbe Extruder — sonst wird mitten im Auftrag umgesteckt"
    )
    assert extruder_of("Rot", plate_one) != extruder_of("Weiß", plate_two), (
        "und zwei Farben teilen sich keine Düse"
    )


def test_only_painted_faces_count_as_a_tool_in_use() -> None:
    """Die Gegenprobe nach dem Slicen fragt nach den **Flächen**, nicht nach
    der Slotliste.

    Ein Körper darf einen Slot deklarieren, den keines seiner Dreiecke trägt —
    eine alte Spulenwahl, eine gelöschte Bemalung. Zählte ``tools_in_use`` die
    Deklaration mit, meldete ``handover.spools_left_out`` bei jedem solchen
    Druck eine verlorene Spule, obwohl nichts fehlt; und ein Fehlalarm, den
    der Kunde dreimal gesehen hat, nimmt dem echten Befund die Wirkung.
    """
    red = MaterialSlot(index=0, name="Rot")
    white = MaterialSlot(index=1, name="Weiß")
    box = trimesh.creation.box()
    faces = len(box.faces)

    declared_only = threemf.AssemblyPart(
        mesh=MeshData.of(box, slots=(0,) * faces), name="A", slots=(red, white)
    )
    assert threemf.tools_in_use([declared_only]) == (0,), (
        "Weiß steht in der Liste, aber auf keinem Dreieck"
    )

    painted = threemf.AssemblyPart(
        mesh=MeshData.of(box, slots=tuple(0 if i < faces // 2 else 1 for i in range(faces))),
        name="B",
        slots=(red, white),
    )
    assert threemf.tools_in_use([painted]) == (0, 1), "bemalt: beide Werkzeuge"

    # Und die Nummern sind die des Auftrags, nicht die der Platte — dieselbe
    # Unterscheidung wie bei ``merge_slots`` eine Zeile darüber.
    second = threemf.AssemblyPart(
        mesh=MeshData.of(box, slots=(1,) * faces), name="C", slots=(white,)
    )
    whole = [painted, second]
    assert threemf.tools_in_use([second], across=whole) == (1,), (
        "Weiß bleibt Werkzeug 2, auch wenn es auf dieser Platte allein liegt"
    )
    assert threemf.tools_in_use([second]) == (0,), (
        "ohne den Auftrag ist die Platte der Auftrag — dann ist Weiß das erste Werkzeug"
    )


def test_a_lettering_split_into_letters_keeps_its_one_filament(
    tmp_path: Path, profile: Profile
) -> None:
    """Zerlegt ist ein Schriftzug auf Slot 7 im Slicer immer noch **ein** Filament.

    **Roberts Bild aus dem ElegooSlicer** (11.09.2026: „Filamente auch
    nicht"): zwei Filamente, „PLAOrange" und ein „Slot 0", und alle
    Buchstaben auf dem zweiten — orange lag daneben, unbenutzt. Die Zerlegung
    hatte die Slots je Dreieck verloren, die Teile trugen nur noch die
    Beschreibung (``material_slots``), und der Export ergänzte für die nun
    unbemalten Dreiecke den neutralen Platzhalter.

    Hier steht die ganze Kette: bemalen, zerlegen, als Baugruppe schreiben —
    und in der Datei ein Material, jedes Teil an Extruder 1.
    """
    from app.core.geom.attributes import with_slot
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    left = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    right = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    right.apply_translation((50.0, 0.0, 0.0))
    orange = MaterialSlot(index=7, name="PLAOrange", colour=(0.7, 0.4, 0.05), material_type="PLA")
    lettering = SceneObject(
        id="obj_1",
        name="Schrift",
        mesh=with_slot(MeshData.of(trimesh.util.concatenate([left, right])), 7),
        material_slots=(orange,),
    )
    spec = REGISTRY.get("split_bodies")
    pieces = spec.fn(
        OpContext(
            scene=Scene(objects={lettering.id: lettering}),
            inputs=[lettering],
            params=spec.params(count=2),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    ).outputs

    written, _findings = write_assembly(
        list(pieces), tmp_path, project_name="schrift", profile=profile
    )
    archive = zipfile.ZipFile(BytesIO(written.read_bytes()))
    model = archive.read(threemf.MODEL_PATH).decode("utf-8")
    assert re.findall(r'<base name="([^"]*)"', model) == ["PLAOrange"], (
        "ein Filament — kein Platzhalter „Slot 0“ daneben"
    )
    settings = archive.read(threemf.SETTINGS_PATH).decode("utf-8")
    assert re.findall(r'key="extruder" value="(\d+)"', settings) == ["1", "1"], (
        "und beide Buchstaben liegen auf ihm"
    )


def test_every_object_names_its_tool_even_without_a_spool() -> None:
    """Creality Print 7.2 rechnet auf der Konsole kein Objekt ohne Werkzeug.

    RM-164: Ohne ``extruder`` in ``model_settings.config`` blieb die
    Werkzeugfolge leer, und jede 3MF endete mit −100 und „The print is
    empty" — Solidons Übergabe genauso wie eine nackte aus trimesh; dieselbe
    Datei mit ``extruder = 1`` am Objekt schneidet (29.09.2026, Sonde
    ``output/review/rm164-2026-09-29/varianten.py``). Ein Teil ohne Spule
    druckt mit dem neutralen Platz, den :func:`threemf.tools_in_use` für die
    Gegenprobe zählt — also steht genau dieses Werkzeug in der Datei, auch
    neben bemalten Teilen.
    """
    red = MaterialSlot(index=0, name="Rot")
    white = MaterialSlot(index=1, name="Weiß")
    box = trimesh.creation.box()
    faces = len(box.faces)

    def extruders(parts: list[threemf.AssemblyPart]) -> list[int]:
        archive = zipfile.ZipFile(BytesIO(threemf.write_assembly(parts)))
        settings = archive.read(threemf.SETTINGS_PATH).decode("utf-8")
        return [int(value) for value in re.findall(r'key="extruder" value="(\d+)"', settings)]

    plain = threemf.AssemblyPart(mesh=MeshData.of(box), name="Würfel")
    assert extruders([plain]) == [1], "ein Teil ohne Spule steht an Werkzeug 1"

    painted = threemf.AssemblyPart(
        mesh=MeshData.of(box, slots=tuple(0 if i < faces // 2 else 1 for i in range(faces))),
        name="Bemalt",
        slots=(red, white),
    )
    parts = [painted, plain]
    assert extruders(parts) == [1, 3], "der neutrale Platz ist das dritte Filament"
    assert threemf.tools_in_use(parts) == (0, 1, 2), (
        "und genau dieses Werkzeug erwartet die Gegenprobe"
    )


def test_the_exported_plates_of_one_job_agree_on_the_extruders(
    profile: Profile, tmp_path: Path
) -> None:
    """Der Anschluss: Die Zusage wird im **Export** eingelöst, nicht in
    ``merge_slots``.

    Der Test daneben prüft die Zählung; dieser prüft, dass der Weg dorthin sie
    auch benutzt. Ohne das könnte ``across`` richtig rechnen und der Export es
    trotzdem nie mitgeben — genau die Sorte Lücke, die die Testart „Anschluss"
    meint: nicht „die Funktion kann es", sondern „die Anwendung tut es".
    """
    red = MaterialSlot(index=1, name="Rot")
    white = MaterialSlot(index=1, name="Weiß")
    red_again = MaterialSlot(index=2, name="Rot")
    objects = [
        SceneObject(
            id="obj_1",
            name="A",
            mesh=MeshData.of(trimesh.creation.box((10, 10, 10)), slots=(1,) * 12),
            material_slots=[red],
            plate=0,
        ),
        SceneObject(
            id="obj_2",
            name="B",
            mesh=MeshData.of(trimesh.creation.box((10, 10, 10)), slots=(1, 2) * 6),
            material_slots=[white, red_again],
            plate=1,
        ),
    ]

    def extruders(plate: int) -> dict[str, int]:
        target, _findings = write_assembly(
            objects,
            tmp_path / f"platte{plate}",
            project_name="auftrag",
            profile=profile,
            plate=plate,
        )
        with zipfile.ZipFile(target) as container:
            root = ET.fromstring(container.read(threemf.MODEL_PATH))
        found: dict[str, int] = {}
        for index, node in enumerate(root.iter()):
            label = node.get("name")
            if label and node.tag.endswith("base"):
                found[label] = index
        return found

    first, second = extruders(0), extruders(1)

    assert "Rot" in first and "Rot" in second, "beide Platten führen die Farbe"
    order_first = sorted(first, key=lambda name: first[name])
    order_second = sorted(second, key=lambda name: second[name])
    assert order_first.index("Rot") == order_second.index("Rot"), (
        "dieselbe Farbe steht in beiden Dateien an derselben Extruderstelle"
    )


def test_the_chosen_filament_profile_follows_the_colour_not_the_position() -> None:
    """Die zweite Hälfte der Extruderfrage — und die teurere.

    ``slot_profiles`` und ``slot_overrides`` sind **positionsbasiert**: Der
    Kunde wählt im Dialog „Position 0 druckt mit PETG-Rot", und
    ``with_slot_profiles`` heftet den Namen an den Slot an dieser Stelle. Das
    ist richtig — solange die Stelle für den ganzen Auftrag dieselbe bedeutet.

    Solange jede Platte für sich nummerierte, tat sie das nicht: Auf Platte 2
    stand an Position 0 Weiß statt Rot, und der Kunde bekam sein
    Rot-Profil auf das weiße Filament gedruckt. Das ist schlimmer als eine
    vertauschte Düse — die Temperatur stimmt dann nicht mehr.

    Der Auftrag als Zählung (``across``) behebt es, ohne dass die
    Positionslogik angefasst werden muss: Wenn die Reihenfolge über alle
    Platten gleich ist, meint Position 0 überall dasselbe Filament.
    """
    red = MaterialSlot(index=1, name="Rot")
    white = MaterialSlot(index=1, name="Weiß")
    red_again = MaterialSlot(index=2, name="Rot")
    job = [
        threemf.AssemblyPart(
            mesh=MeshData(trimesh.creation.box(), slots=(1,) * 12), name="A", slots=(red,)
        ),
        threemf.AssemblyPart(
            mesh=MeshData(trimesh.creation.box(), slots=(1,) * 6 + (2,) * 6),
            name="B",
            slots=(white, red_again),
        ),
    ]
    chosen = ["PETG-Rot", "PLA-Weiss"]

    def profile_of(colour: str, plate: list[threemf.AssemblyPart]) -> str | None:
        slots = with_slot_profiles(threemf.merge_slots(plate, across=job), chosen)
        return next(slot.material for slot in slots if str(slot.name) == colour)

    assert profile_of("Rot", [job[0]]) == profile_of("Rot", [job[1]]) == "PETG-Rot", (
        "dasselbe Filament bekommt auf jeder Platte dasselbe Profil"
    )
    assert profile_of("Weiß", [job[1]]) == "PLA-Weiss"
    assert profile_of("Weiß", [replace(job[1], slots=(white,))]) == "PLA-Weiss", (
        "auch eine Platte mit nur dem späteren Auftragsslot behält dessen Profil"
    )


def test_an_exported_3mf_carries_each_filaments_temperature(
    profile: Profile, tmp_path: Path
) -> None:
    """Der Anschluss vom Projektwert bis in die exportierte Kundendatei.

    ``write_config`` konnte bereits je Extruder schreiben. Der direkte
    3MF-Export ging aber an diesem Weg vorbei und legte nur den gemeinsamen
    PETG-Satz in ``project_settings.config`` ab. Eine PLA-Schrift kam dadurch
    mit der richtigen Farbe und der falschen Temperatur im Slicer an.
    """
    from app.core.types import SlotOverride

    black = MaterialSlot(index=0, name="PETG Schwarz", colour=(0.05, 0.05, 0.05))
    white = MaterialSlot(index=0, name="PLA Weiß", colour=(1.0, 1.0, 1.0))
    objects = [
        SceneObject(id="body", name="Gehäuse", mesh=body(), material_slots=[black]),
        SceneObject(id="label", name="Schrift", mesh=body(), material_slots=[white]),
    ]
    settings = print_settings.resolve(profile)
    pla_temperature = replace(settings.temperature, nozzle=210, nozzle_first_layer=215)
    settings = replace(
        settings,
        slot_overrides=(
            SlotOverride(
                name=white.name,
                colour=white.colour,
                temperature=pla_temperature,
            ),
        ),
    )

    written, _findings = write_assembly(
        objects,
        tmp_path,
        project_name="Schild",
        profile=profile,
        settings=settings,
        flavour="orca",
    )

    with zipfile.ZipFile(written) as archive:
        embedded = json.loads(archive.read(threemf.PROJECT_SETTINGS_PATH))
    assert embedded["nozzle_temperature"] == [
        str(settings.temperature.nozzle),
        "210",
    ]
    assert embedded["nozzle_temperature_initial_layer"] == [
        str(settings.temperature.nozzle_first_layer),
        "215",
    ]
    imported = threemf_reader.read_objects(written.read_bytes())
    assert [[str(slot.name) for slot in part.slots] for part in imported] == [
        ["PETG Schwarz"],
        ["PLA Weiß"],
    ], "der Import liest dieselben benannten Filamente zurück"
    for part, expected in zip(imported, (black, white), strict=True):
        assert part.slots[0].colour == pytest.approx(expected.colour, abs=1 / 255), (
            "auch die sichtbaren Spulenfarben überstehen den Reimport"
        )


def test_a_direct_3mf_export_uses_each_chosen_filament_profile(
    profile: Profile, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Profilwahl aus dem Druckdialog gilt auch beim normalen Export.

    Der Slicerlauf heftete die Namen bereits an die Slots; der direkte Export
    ging an diesem Schritt vorbei und nahm für beide Spulen das eine
    Basisprofil. Eine PLA-Schrift erbte dadurch die PETG-Temperatur, solange
    der Kunde nicht zusätzlich dieselbe Temperatur von Hand übersteuerte.
    """
    from app.core.export import slicer_profiles

    petg_path = tmp_path / "Haus PETG.json"
    petg_path.write_text(
        json.dumps(
            {
                "name": "Haus PETG",
                "nozzle_temperature": ["240"],
                "filament_max_volumetric_speed": ["5"],
            }
        ),
        encoding="utf-8",
    )
    pla_path = tmp_path / "Haus PLA.json"
    pla_path.write_text(
        json.dumps(
            {
                "name": "Haus PLA",
                "nozzle_temperature": ["210"],
                "filament_max_volumetric_speed": ["21"],
            }
        ),
        encoding="utf-8",
    )
    available = [
        slicer_profiles.SlicerProfile(path=petg_path, name="Haus PETG", kind="filament"),
        slicer_profiles.SlicerProfile(path=pla_path, name="Haus PLA", kind="filament"),
    ]
    monkeypatch.setattr(slicer_profiles, "find_profiles", lambda *_args, **_kwargs: available)

    black = MaterialSlot(index=0, name="PETG Schwarz", colour=(0.05, 0.05, 0.05))
    white = MaterialSlot(index=0, name="PLA Weiß", colour=(1.0, 1.0, 1.0))
    objects = [
        SceneObject(id="body", name="Gehäuse", mesh=body(), material_slots=[black]),
        SceneObject(id="label", name="Schrift", mesh=body(), material_slots=[white]),
    ]
    settings = replace(
        print_settings.resolve(profile),
        slot_profiles=("Haus PETG", "Haus PLA"),
    )
    setup = handover.SlicerSetup(
        executable=tmp_path / "orca.exe",
        flavour="orca",
        base_filament="Haus PETG",
    )

    written, _findings = write_assembly(
        objects,
        tmp_path,
        project_name="Schild mit Profilen",
        profile=profile,
        settings=settings,
        flavour="orca",
        setup=setup,
    )

    with zipfile.ZipFile(written) as archive:
        embedded = json.loads(archive.read(threemf.PROJECT_SETTINGS_PATH))
    assert embedded["nozzle_temperature"] == ["240", "210"]
    assert embedded["filament_max_volumetric_speed"] == ["5", "21"]


def test_only_the_part_that_needs_it_gets_the_setting() -> None:
    """Eine Platte hat einen Satz Werte, aber nicht jedes Teil darauf braucht
    dasselbe — ohne diesen Ort gäbe es nur „alle" oder „keiner"."""
    parts = [
        threemf.AssemblyPart(mesh=MeshData.of(trimesh.creation.box((10, 10, 10))), name="gross"),
        threemf.AssemblyPart(
            mesh=MeshData.of(trimesh.creation.box((5, 5, 5))),
            name="klein",
            settings={"brim_type": "outer_only", "brim_width": "3"},
        ),
    ]

    payload = threemf.write_assembly(parts, "")

    with zipfile.ZipFile(BytesIO(payload)) as container:
        root = ET.fromstring(container.read(threemf.SETTINGS_PATH))
    by_name = {
        node.find("metadata[@key='name']").get("value"): {  # type: ignore[union-attr]
            entry.get("key"): entry.get("value") for entry in node.findall("metadata")
        }
        for node in root.findall("object")
    }
    assert by_name["klein"]["brim_type"] == "outer_only"
    assert "brim_type" not in by_name["gross"]


def _boxed(
    name: str,
    size: tuple[float, float, float],
    at: tuple[float, float],
    slot: str = "",
    material: str | None = None,
) -> SceneObject:
    """Ein Quader an einer Stelle der Platte, mit optionaler Spule und Material.

    ``slot`` ist die zugewiesene Spule, ``material`` das ausdrücklich am Teil
    gesetzte Material — zwei verschiedene Dinge, und die Plattenverteilung
    braucht beide (siehe ``plates_by_material``).
    """
    raw = trimesh.creation.box(size)
    raw.apply_translation((at[0], at[1], size[2] / 2.0))
    return SceneObject(
        id=name,
        name=name,
        mesh=MeshData.of(raw),
        material=material,
        material_slots=[MaterialSlot(index=0, name=slot)] if slot else [],
    )


def test_two_parts_may_be_apart_and_their_brims_still_collide() -> None:
    """Die Körper haben Luft, der Druck scheitert trotzdem.

    Genau das passierte beim Gewürzset: die Deckelplatte sah in der Rechnung
    frei aus, weil der Brim nicht mitzählte — und zwischen zwei Nachbarn zählt
    er zweimal.
    """
    settings = print_settings.resolve(profiles.make_profile())
    settings = print_settings.with_path(settings, "adhesion.kind", "brim")
    settings = print_settings.with_path(settings, "adhesion.brim_width", 3.0)
    meshes = [
        (_boxed("links", (10.0, 10.0, 5.0), (0.0, 0.0)).mesh),
        (_boxed("rechts", (10.0, 10.0, 5.0), (14.0, 0.0)).mesh),
    ]

    findings = check_adhesion_clearance(meshes, settings)

    assert [entry.code for entry in findings] == ["arrange.adhesion_too_close"]
    weit = [
        meshes[0],
        (_boxed("weit", (10.0, 10.0, 5.0), (30.0, 0.0)).mesh),
    ]
    assert check_adhesion_clearance(weit, settings) == []


def test_a_rim_beyond_the_bed_edge_is_said() -> None:
    """Die Körper liegen auf dem Bett, ihr Rand nicht (27.09.2026): Am
    Minigolf-Auftrag für den Centauri Carbon 2 fuhr der Auto-Brim am Neptune 4
    210 Züge neben das Bett, PrusaSlicers Skirt am SV06 24. Der Skirt zählt
    dabei mit seiner Breite — am Bettrand liegt er ganz außen."""
    profile = profiles.make_profile()
    half = profile.printer.build_volume[0] / 2.0
    settings = print_settings.resolve(profile)
    brim = print_settings.with_path(settings, "adhesion.kind", "brim")
    brim = print_settings.with_path(brim, "adhesion.brim_width", 5.0)
    skirt = print_settings.with_path(settings, "adhesion.kind", "skirt")
    skirt = print_settings.with_path(skirt, "adhesion.skirt_distance", 2.0)
    skirt = print_settings.with_path(skirt, "adhesion.skirt_loops", 1)
    edge = _boxed("Rand", (10.0, 10.0, 5.0), (half - 7.0, 0.0)).mesh
    middle = _boxed("Mitte", (10.0, 10.0, 5.0), (0.0, 0.0)).mesh
    beside = _boxed("Daneben", (10.0, 10.0, 5.0), (half + 20.0, 0.0)).mesh

    [found] = check_adhesion_on_bed([edge, middle], brim, profile, ["Rand", "Mitte"])

    assert found.code == "arrange.adhesion_off_bed" and found.object_id == "Rand"
    assert found.suggestions, "Regel 17: Anordnen"
    assert [f.code for f in check_adhesion_on_bed([edge], skirt, profile)] == [
        "arrange.adhesion_off_bed"
    ], "2 mm Abstand und eine Bahn über 2 mm Luft"
    assert check_adhesion_on_bed([middle], brim, profile) == []
    assert check_adhesion_on_bed([beside], brim, profile) == [], "das sagt die Bauraumprüfung"
    none = print_settings.with_path(settings, "adhesion.kind", "none")
    assert check_adhesion_on_bed([edge], none, profile) == []


def test_a_rim_reaching_into_a_bed_exclusion_is_said() -> None:
    """Der Centauri Carbon 2 sperrt vorn rechts 10 mal 20 mm (``bed_exclude_area``).
    In der Slicer-Matrix (RM-312) stand ein Teil von Rack system for
    Filament.3mf 3 mm davor; der Auto-Brim des ElegooSlicers lief 5 mm breit
    hinein, und erst die G-Code-Prüfung sagte es. Die Prüfung vor dem Export
    fragte nur den Bettrand."""
    profile = profiles.make_profile()
    half = profile.printer.build_volume[0] / 2.0
    corner = (
        (half - 10.0, -half),
        (half, -half),
        (half, -half + 20.0),
        (half - 10.0, -half + 20.0),
    )
    profile = replace(profile, printer=replace(profile.printer, bed_exclusions=(corner,)))
    settings = print_settings.resolve(profile)
    brim = print_settings.with_path(settings, "adhesion.kind", "brim")
    brim = print_settings.with_path(brim, "adhesion.brim_width", 5.0)
    # 3 mm vor der Sperrfläche, 10 mm vom vorderen Bettrand.
    near = _boxed("Nah", (10.0, 10.0, 5.0), (half - 18.0, -half + 15.0)).mesh
    # 8 mm vor der Sperrfläche: Der Rand bleibt draußen.
    far = _boxed("Fern", (10.0, 10.0, 5.0), (half - 23.0, -half + 15.0)).mesh

    [found] = check_adhesion_on_bed([near, far], brim, profile, ["Nah", "Fern"])

    assert found.code == "arrange.adhesion_off_bed" and found.object_id == "Nah"
    assert found.values["distance"] == format_length(5.0 - 3.0)
    assert "Sperrfläche" in source_text(found.message)
    assert found.suggestions, "Regel 17: Anordnen"
    none = print_settings.with_path(settings, "adhesion.kind", "none")
    assert check_adhesion_on_bed([near], none, profile) == []


def _near_the_edge(profile: Profile, gap: float) -> MeshData:
    """Ein Quader, dessen rechte Kante ``gap`` mm vor dem Bettrand liegt."""
    half = profile.printer.build_volume[0] / 2.0
    return _boxed("Rand", (10.0, 10.0, 5.0), (half - gap - 5.0, 0.0)).mesh


def test_the_orca_auto_brim_is_warned_at_its_largest_width() -> None:
    """Entscheidung zu RM-312 (J): Der Auto-Brim der Orca-Familie wählt seine
    Breite selbst, bis :data:`writer.ORCA_AUTO_BRIM_MAX` (OrcaSlicer
    ``Brim.cpp``); am Rack legte ElegooSlicer 14,7 mm statt der 5 mm des
    Profils und lief über das Bett. Ein Teil näher am Rand bekommt die Warnung
    mit *Brim-Breite festlegen*; eine gewählte Brimbreite geht ausdrücklich
    hinaus und gilt so, wie sie ist."""
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    auto = print_settings.with_path(settings, "adhesion.kind", "auto")
    auto = print_settings.with_path(auto, "adhesion.brim_width", 5.0)
    auto = print_settings.with_path(auto, "adhesion.brim_gap", 0.0)
    auto = print_settings.with_path(auto, "adhesion.skirt_loops", 0)
    near = _near_the_edge(profile, 10.0)
    far = _near_the_edge(profile, writer.ORCA_AUTO_BRIM_MAX + 1.0)

    [found] = check_adhesion_on_bed([near], auto, profile, ["Rand"], flavour="orca")

    assert found.code == "arrange.adhesion_off_bed"
    assert found.values["distance"] == format_length(writer.ORCA_AUTO_BRIM_MAX - 10.0)
    assert found.values["field"] == "adhesion.kind"
    assert found.suggestions[0] is writer.FIX_BRIM_WIDTH
    assert found.suggestions[0].id == "open_print_settings"
    assert check_adhesion_on_bed([far], auto, profile, flavour="orca") == []
    assert check_adhesion_on_bed([near], auto, profile, flavour="prusa") == [], (
        "nur die Orca-Familie kennt den Auto-Brim"
    )
    chosen = print_settings.with_choice(auto, "adhesion.kind", "brim")
    assert check_adhesion_on_bed([near], chosen, profile, flavour="orca") == [], (
        "ein gewählter Brim hat seine Breite"
    )


def test_the_support_foot_and_its_skirt_are_warned_at_the_bed_edge() -> None:
    """RM-312: SuperSlicer verbreitert die erste Stützschicht um
    ``raft_first_layer_expansion`` (3 mm) und legt den Skirt darum; an
    garden-hose-holder.3mf (2,4 mm vor dem Rand des MINI) lief beides 2,5 mm
    über das Bett, gewarnt hatte Solidon 0,01 mm."""
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    skirt = print_settings.with_path(settings, "adhesion.kind", "skirt")
    skirt = print_settings.with_path(skirt, "adhesion.skirt_loops", 1)
    skirt = print_settings.with_path(skirt, "adhesion.skirt_distance", 2.0)
    supported = print_settings.with_path(skirt, "support.style", "grid")
    unsupported = print_settings.with_path(skirt, "support.style", "none")
    line = supported.layers.first_layer_line_width
    near = _near_the_edge(profile, 4.0)

    [found] = check_adhesion_on_bed(
        [near], supported, profile, ["Rand"], flavour="prusa", support_foot=3.0
    )

    assert found.values["distance"] == format_length(3.0 + 2.0 + line - 4.0)
    assert found.values["field"] == "adhesion.skirt_loops"
    assert writer.SMALLER_SKIRT in found.suggestions
    assert check_adhesion_on_bed([near], unsupported, profile, flavour="prusa") == []
    # Ein Vorschlag je Teil schaltet die Stütze am Objekt ein, die Platte bleibt ohne.
    [per_part] = check_adhesion_on_bed(
        [near], unsupported, profile, per_part=[supported], flavour="prusa", support_foot=3.0
    )
    assert per_part.values["field"] == "adhesion.skirt_loops"
    unknown = check_adhesion_on_bed([near], supported, profile, flavour="cura")
    assert [entry.code for entry in unknown] == ["arrange.support_foot_unknown"], (
        "ohne Wert im Profil wird nichts geschätzt, sondern gesagt"
    )


def _wide_on_a_foot(profile: Profile, gap: float) -> MeshData:
    """Ein Teil, das oben breiter ist als am Fuß: Fuß 10 × 10 mm, darüber eine
    Platte 30 × 30 mm, deren rechte Kante ``gap`` mm vor dem Bettrand liegt;
    der Fuß steht 10 mm weiter innen."""
    half = profile.printer.build_volume[0] / 2.0
    centre = half - gap - 15.0
    foot = trimesh.creation.box((10.0, 10.0, 2.0))
    foot.apply_translation((centre, 0.0, 1.0))
    plate = trimesh.creation.box((30.0, 30.0, 3.0))
    plate.apply_translation((centre, 0.0, 3.5))
    return MeshData.of(trimesh.boolean.union([foot, plate]))


def _slab_with_an_inner_overhang(profile: Profile, gap: float) -> MeshData:
    """Eine Platte 60 × 60 × 4 mm, deren rechte Kante ``gap`` mm vor dem Bettrand
    liegt; mitten darauf eine Säule mit einem Tisch 20 × 20 mm. Gestützt wird
    nur unter dem Tisch, und der steht 20 mm innerhalb der Platte."""
    half = profile.printer.build_volume[0] / 2.0
    centre = half - gap - 30.0
    slab = trimesh.creation.box((60.0, 60.0, 4.0))
    slab.apply_translation((centre, 0.0, 2.0))
    column = trimesh.creation.box((6.0, 6.0, 8.0))
    column.apply_translation((centre, 0.0, 8.0))
    table = trimesh.creation.box((20.0, 20.0, 2.0))
    table.apply_translation((centre, 0.0, 13.0))
    return MeshData.of(trimesh.boolean.union([slab, column, table]))


def test_the_support_foot_stands_under_the_overhangs_only() -> None:
    """RM-312: Der Stützfuß stand um die ganze Aufsicht, die Slicer stützen nur
    die Überhänge. Die Waschschüssel am Kobra 2 mit Stützen bekam die Warnung,
    obwohl die erste Stützschicht im G-Code 15 mm vom Rand blieb. Gemessen wird
    jetzt an den Überhängen der Schichtanalyse (``analysis.overhang_outline``):
    Eine Platte bis 4 mm vor dem Rand (der Skirt um sie bleibt auf dem Bett) mit
    einem Tisch in der Mitte bekommt keine Warnung, ein Teil, dessen Überhang
    bis an den Rand reicht, weiter die alte. Ohne Überhang gibt es keinen Fuß.
    Am Kundenmodell (Waschschüssel am Kobra 2, Öffnung oben, schräg) stehen die
    Überhänge 20 mm vom Rand: vorher 5,61 mm Warnung, jetzt keine."""
    from app.core.slice.analysis import overhang_outline, slice_body

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    skirt = print_settings.with_path(settings, "adhesion.kind", "skirt")
    skirt = print_settings.with_path(skirt, "adhesion.skirt_loops", 1)
    skirt = print_settings.with_path(skirt, "adhesion.skirt_distance", 2.0)
    supported = print_settings.with_path(skirt, "support.style", "grid")
    line = supported.layers.first_layer_line_width

    def outline(mesh: MeshData) -> Any:
        return overhang_outline(slice_body(mesh, 0.2, "support", overhang_angle=45.0))

    inner = _slab_with_an_inner_overhang(profile, 4.0)
    under_the_table = outline(inner)
    assert under_the_table is not None
    assert under_the_table.bounds[2] == pytest.approx(inner.bounds.maximum[0] - 20.0, abs=0.5)
    assert check_adhesion_on_bed([inner], supported, profile, flavour="prusa", support_foot=3.0), (
        "Gegenprobe: an der ganzen Aufsicht gemessen warnt es"
    )
    assert (
        check_adhesion_on_bed(
            [inner],
            supported,
            profile,
            flavour="prusa",
            support_foot=3.0,
            support_outline=lambda _index: under_the_table,
        )
        == []
    ), "der Fuß steht unter dem Tisch, 20 mm vom Rand der Platte"

    wide = _wide_on_a_foot(profile, 2.0)
    [found] = check_adhesion_on_bed(
        [wide],
        supported,
        profile,
        flavour="prusa",
        support_foot=3.0,
        support_outline=lambda _index: outline(wide),
    )
    assert found.values["field"] == "adhesion.skirt_loops"
    assert found.values["distance"] == format_length(3.0 + 2.0 + line - 2.0), (
        "der Überhang der Platte reicht bis an ihre Kante"
    )

    plain = _near_the_edge(profile, 4.0)
    assert outline(plain) is None, "ein Quader hat keinen Überhang"
    assert (
        check_adhesion_on_bed(
            [plain],
            supported,
            profile,
            flavour="prusa",
            support_foot=3.0,
            support_outline=lambda _index: None,
        )
        == []
    ), "ohne Überhang keine Stütze und kein Fuß"


def test_the_export_asks_the_overhangs_for_the_support_foot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Anschluss zu RM-312: ``write_assembly`` fragt die Überhänge (Review, K7).

    Gefragt wird nur, wo der Fuß schon um die ganze Aufsicht aus dem Bett
    reichte (K6). Die Platte mit dem Tisch in der Mitte bekommt über den
    Exportweg keine Warnung, das Teil mit Überhang bis zur Kante die Warnung des
    Stützfußes; ein Teil in der Mitte des Betts schneidet nichts nach. Ersetzt
    ist nur die Verbreiterung aus dem Herstellerprofil — ohne Slicer bliebe
    sie unbekannt.
    """
    from app.core.slice import analysis

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    skirt = print_settings.with_path(settings, "adhesion.kind", "skirt")
    skirt = print_settings.with_path(skirt, "adhesion.skirt_loops", 1)
    skirt = print_settings.with_path(skirt, "adhesion.skirt_distance", 2.0)
    supported = print_settings.with_choice(skirt, "support.style", "grid")
    monkeypatch.setattr(writer, "support_foot_for", lambda *_args, **_kwargs: 3.0)
    asked: list[int] = []
    original = analysis.overhang_outline

    def counted(result: Any) -> Any:
        asked.append(1)
        return original(result)

    monkeypatch.setattr(analysis, "overhang_outline", counted)

    def codes(mesh: MeshData, name: str) -> list[str]:
        entry = scene_object(object_id=name, mesh=mesh)
        _written, findings = write_assembly(
            [entry],
            tmp_path / name,
            project_name=name,
            profile=profile,
            settings=supported,
            flavour="prusa",
            for_slicer=True,
            mesh_plan=({entry.id: mesh}, False),
        )
        return [item.code for item in findings]

    assert "arrange.adhesion_off_bed" not in codes(
        _slab_with_an_inner_overhang(profile, 4.0), "innen"
    )
    assert asked == [1], "der Fuß um die Aufsicht reichte hinaus, also wurde gefragt"
    assert "arrange.adhesion_off_bed" in codes(_wide_on_a_foot(profile, 2.0), "breit")
    asked.clear()
    middle = _boxed("Mitte", (10.0, 10.0, 5.0), (0.0, 0.0)).mesh
    assert "arrange.adhesion_off_bed" not in codes(middle, "mitte")
    assert asked == [], "in der Mitte des Betts kein Schnitt für den Fuß"


def test_brim_and_skirt_are_measured_around_the_first_layer() -> None:
    """RM-312: Brim und Skirt legen die Slicer um die erste Schicht, gemessen
    wurde an der Aufsicht. Teile, die oben breiter sind als am Fuß, bekamen
    eine Warnung, obwohl der Rand auf dem Bett blieb (garden-hose-holder am
    MINI ohne Stützen; Waschschüssel am Kobra 2: Brim im G-Code 4,5 mm, 21 mm
    vom Rand). Der Stützfuß liegt unter den Überhängen; ohne deren Umriss misst
    die Prüfung ihn an der ganzen Aufsicht (die Überhänge prüft
    :func:`test_the_support_foot_stands_under_the_overhangs_only`)."""
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    brim = print_settings.with_path(settings, "adhesion.kind", "brim")
    brim = print_settings.with_path(brim, "adhesion.brim_width", 5.0)
    skirt = print_settings.with_path(settings, "adhesion.kind", "skirt")
    skirt = print_settings.with_path(skirt, "adhesion.skirt_distance", 2.0)
    skirt = print_settings.with_path(skirt, "adhesion.skirt_loops", 1)
    auto = print_settings.with_path(settings, "adhesion.kind", "auto")
    auto = print_settings.with_path(auto, "adhesion.brim_gap", 0.0)
    auto = print_settings.with_path(auto, "adhesion.skirt_loops", 0)
    line = skirt.layers.first_layer_line_width
    # Platte 2 mm vor dem Rand, Fuß 12 mm.
    wide = _wide_on_a_foot(profile, 2.0)

    assert check_adhesion_on_bed([wide], brim, profile) == [], "5 mm Brim um den Fuß"
    assert check_adhesion_on_bed([wide], skirt, profile) == [], "Skirt um den Fuß"
    assert [
        f.code for f in check_adhesion_on_bed([_near_the_edge(profile, 2.0)], brim, profile)
    ] == ["arrange.adhesion_off_bed"], "Gegenprobe: ein Quader bis zur selben Kante"
    [auto_found] = check_adhesion_on_bed([wide], auto, profile, flavour="orca")
    assert auto_found.values["distance"] == format_length(writer.ORCA_AUTO_BRIM_MAX - 12.0)
    supported = print_settings.with_path(skirt, "support.style", "grid")
    [foot_found] = check_adhesion_on_bed(
        [wide], supported, profile, flavour="prusa", support_foot=3.0
    )
    assert foot_found.values["field"] == "adhesion.skirt_loops"
    assert foot_found.values["distance"] == format_length(3.0 + 2.0 + line - 2.0), (
        "der Stützfuß und sein Skirt von der Aufsicht"
    )


def test_the_profiles_skirt_beside_a_brim_counts_until_solidon_writes_the_kind() -> None:
    """Prusa und Orca drucken Skirt und Brim nebeneinander, wenn das Profil
    beide nennt; schreibt Solidon eine Haftungsart, nullt die Übergabe die
    übrigen (``handover._only_chosen_adhesion``)."""
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    both = print_settings.with_path(settings, "adhesion.kind", "brim")
    both = print_settings.with_path(both, "adhesion.brim_width", 3.0)
    both = print_settings.with_path(both, "adhesion.skirt_loops", 1)
    both = print_settings.with_path(both, "adhesion.skirt_distance", 6.0)
    line = both.layers.first_layer_line_width

    assert writer.rim_reach(both, "prusa") == pytest.approx(3.0 + 6.0 + line)
    assert writer.rim_reach(both, "cura") == pytest.approx(3.0)
    chosen = print_settings.with_choice(both, "adhesion.kind", "brim")
    assert writer.rim_reach(chosen, "prusa") == pytest.approx(3.0)


@pytest.mark.parametrize(
    ("values", "program", "expected"),
    [
        ({"raft_first_layer_expansion": "1.5"}, "orcaslicer", 1.5),
        ({}, "elegooslicer", 2.0),
        ({}, "anycubicslicernext", 2.0),
        ({}, "superslicer", 3.0),
        ({"raft_first_layer_expansion": "-1"}, "bambustudio", None),
        ({}, "bambustudio", None),
        ({}, "cura", None),
    ],
)
def test_the_support_foot_comes_from_the_chain_or_the_measured_program(
    values: dict[str, str], program: str, expected: float | None
) -> None:
    """Eine Breite nur, wo Kette oder gemessene Programmvorgabe sie nennen."""
    assert manufacturer.support_foot(values, program) == expected


def test_a_part_too_tall_for_the_printer_is_named_as_such() -> None:
    """PrusaSlicer sagt „outside of the print volume", gleich ob ein Teil
    daneben liegt oder zu hoch ist. Am Minigolf-Auftrag auf dem MINI war es
    ein Teil von 200 mm bei 180 mm Bauhöhe, und „Anordnen" half dort nicht."""
    profile = profiles.make_profile("prusa-mini", "pla")
    setup = handover.SlicerSetup(executable=Path("prusa-slicer-console.exe"), flavour="prusa")

    tall = handover._outside_the_volume(setup, profile, "outside of the print volume", 200.0)
    flat = handover._outside_the_volume(setup, profile, "outside of the print volume", 20.0)

    assert tall.values["height_mm"] == 200.0 and tall.values["limit_mm"] == 180.0
    assert tall.suggestions[0].id == "split_model"
    assert "limit_mm" not in flat.values
    assert flat.suggestions[0].id == "arrange_on_bed"


def test_the_support_structure_needs_its_own_room_beside_the_part() -> None:
    """Nicht nur der Brim steht über — die Stütze auch (Robert, 09.09.2026).

    Sie steht unter dem Überhang und damit überwiegend in der Aufsicht des
    Körpers, an einer senkrechten Wand aber ``xy_gap`` außerhalb. Zwischen zwei
    Nachbarn zählt dieser Rand zweimal, genau wie der Brim. Gemessen ohne
    Haftung, damit allein die Stütze die Aussage trägt: 2 mm ``xy_gap`` je
    Seite brauchen 4 mm, und 3 mm Luft sind zu wenig.

    **Und ohne Stützstil bleibt der Rand aus.** Wo keine Struktur entsteht,
    verschenkte ein Rand für sie Bettfläche.
    """
    settings = print_settings.resolve(profiles.make_profile())
    settings = print_settings.with_path(settings, "adhesion.kind", "none")
    settings = print_settings.with_path(settings, "support.xy_gap", 2.0)
    meshes = [
        (_boxed("links", (10.0, 10.0, 5.0), (0.0, 0.0)).mesh),
        (_boxed("rechts", (10.0, 10.0, 5.0), (13.0, 0.0)).mesh),
    ]

    ohne = print_settings.with_path(settings, "support.style", "none")
    assert check_adhesion_clearance(meshes, ohne) == [], "ohne Stützen kein Rand"

    mit = print_settings.with_path(settings, "support.style", "grid")
    assert [entry.code for entry in check_adhesion_clearance(meshes, mit)] == [
        "arrange.adhesion_too_close"
    ]
    weit = [
        meshes[0],
        (_boxed("weit", (10.0, 10.0, 5.0), (16.0, 0.0)).mesh),
    ]
    assert check_adhesion_clearance(weit, mit) == [], "5 mm Luft reichen für 2 + 2"


def test_parts_on_different_plates_never_crowd_each_other() -> None:
    settings = print_settings.resolve(profiles.make_profile())
    settings = print_settings.with_path(settings, "adhesion.kind", "brim")
    meshes = [
        (_boxed("a", (10.0, 10.0, 5.0), (0.0, 0.0)).mesh),
        (_boxed("b", (10.0, 10.0, 5.0), (11.0, 0.0)).mesh),
    ]

    assert check_adhesion_clearance(meshes, settings, plates=[0, 1]) == []


def test_two_filaments_on_one_plate_are_counted_not_forbidden() -> None:
    """Ein Wechsel ist ein Spülgang je gemeinsamer Schicht. Beim Gewürzset
    waren das hundertzehn — der Behälter 68 mm hoch, der Deckel 22."""
    settings = print_settings.resolve(profiles.make_profile())
    settings = print_settings.with_path(settings, "layers.layer_height", 0.2)
    objects = [
        _boxed("behaelter", (10.0, 10.0, 68.0), (0.0, 0.0), slot="transluzent"),
        _boxed("deckel", (10.0, 10.0, 22.0), (30.0, 0.0), slot="grau"),
    ]

    findings = check_filament_changes(objects, settings)

    assert [entry.code for entry in findings] == ["arrange.filament_changes"]
    assert findings[0].severity == "info", "eine Rechnung, kein Verbot"
    assert findings[0].values["layers"] == 110
    assert findings[0].values["changes"] == 220


def test_two_filaments_on_separate_plates_cost_no_changes() -> None:
    """Getrennte Platten werden nacheinander gedruckt, nie schichtweise.

    Der Export einer mehrplattigen 3MF übergibt ``plate=None``. Bis hier jede
    Farbe trotzdem gemeinsam gezählt wurde, meldete die fertige
    CC2-Werkzeugbox 230 Filamentwechsel, obwohl jede Platte genau eine Farbe
    trägt.
    """
    settings = print_settings.resolve(profiles.make_profile())
    objects = [
        replace(
            _boxed("weiss", (10.0, 10.0, 23.0), (0.0, 0.0), slot="weiß"),
            plate=0,
        ),
        replace(
            _boxed("schwarz", (10.0, 10.0, 27.0), (0.0, 0.0), slot="schwarz"),
            plate=1,
        ),
    ]

    assert check_filament_changes(objects, settings) == []


def test_one_filament_costs_no_changes() -> None:
    settings = print_settings.resolve(profiles.make_profile())
    objects = [
        _boxed("a", (10.0, 10.0, 60.0), (0.0, 0.0), slot="grau"),
        _boxed("b", (10.0, 10.0, 20.0), (30.0, 0.0), slot="grau"),
    ]

    assert check_filament_changes(objects, settings) == []


def test_a_plate_is_suggested_per_filament() -> None:
    """Ein Filament je Platte: zwei kosten je gemeinsamer Schicht einen
    Spülgang, und die Rechnung steht in check_filament_changes."""
    objects = [
        _boxed("behaelter", (10.0, 10.0, 68.0), (0.0, 0.0), slot="transluzent"),
        _boxed("basis", (10.0, 10.0, 22.0), (30.0, 0.0), slot="grau"),
        _boxed("scheibe", (10.0, 10.0, 5.0), (60.0, 0.0), slot="grau"),
        _boxed("zweiter", (10.0, 10.0, 68.0), (90.0, 0.0), slot="transluzent"),
    ]

    plates = plates_by_material(objects)

    assert plates["behaelter"] == plates["zweiter"]
    assert plates["basis"] == plates["scheibe"]
    assert plates["behaelter"] != plates["basis"]
    # Reihenfolge nach erstem Auftreten — eine Vorgabe, die zwischen zwei
    # Aufrufen springt, ist keine.
    assert plates["behaelter"] == 0


def test_parts_without_a_named_filament_stay_together() -> None:
    objects = [
        _boxed("a", (10.0, 10.0, 10.0), (0.0, 0.0)),
        _boxed("b", (10.0, 10.0, 10.0), (30.0, 0.0)),
    ]

    assert set(plates_by_material(objects).values()) == {0}


def test_a_material_set_on_the_part_gets_its_own_plate() -> None:
    """Eine TPU-Dichtung gehört nicht auf die Platte des PETG-Gehäuses.

    ``SceneObject.material`` ist kein Beiwerk: ``for_object`` rechnet damit
    Spiel, Schrumpf und Elefantenfuß, und ``types.py`` nennt genau diesen Fall
    („Eine TPU-Dichtung im PETG-Gehäuse schrumpft anders"). Die
    Plattenverteilung sah es bis zum 03.09.2026 trotzdem nicht: Sie gruppierte
    allein nach dem Spulennamen, und ohne zugewiesene Spule trugen alle Teile
    denselben leeren Schlüssel. Gehäuse und Dichtung kamen auf eine Platte,
    ``check_filament_changes`` schwieg, und so ging es an den Slicer.
    """
    objects = [
        _boxed("gehaeuse", (10.0, 10.0, 10.0), (0.0, 0.0)),
        _boxed("dichtung", (10.0, 10.0, 10.0), (30.0, 0.0), material="tpu-95a"),
    ]

    plates = plates_by_material(objects)

    assert plates["gehaeuse"] != plates["dichtung"], (
        "zwei Materialien sind zwei Filamente, auch ohne zugewiesene Spule"
    )
    assert plates["gehaeuse"] == 0, "die Reihenfolge folgt dem ersten Auftreten"


def test_two_spools_of_the_same_material_stay_apart() -> None:
    """Und die Gegenrichtung, an der der einfache Fix gescheitert wäre.

    „Material schlägt Spule" ist die Rangfolge aus ``for_object``, und für die
    **Rechnung** ist sie richtig. Für die **Platte** ist sie falsch: Grau und
    Weiß sind zwei Spulen, auch wenn beide PETG sind — zwei Filamente, zwei
    Platten. Gemessen an vier Lagen war das der einzige Fall, in dem sich die
    naheliegende Fassung und die gewählte unterscheiden, und er entscheidet.
    """
    objects = [
        _boxed("links", (10.0, 10.0, 10.0), (0.0, 0.0), slot="grau", material="petg"),
        _boxed("rechts", (10.0, 10.0, 10.0), (30.0, 0.0), slot="weiss", material="petg"),
    ]

    assert plates_by_material(objects)["links"] != plates_by_material(objects)["rechts"]


# --- die Anordnung geht nur mit, wenn sie eine ist (§29) ------------------------


def at(x: float, y: float, size: float = 20.0, z: float = 0.0) -> MeshData:
    """Ein Würfel mit seiner Mitte auf (x, y), auf der Platte stehend.

    ``z`` hebt oder senkt ihn — die Unterkante liegt dann dort statt auf null.
    """
    cube = trimesh.creation.box((size, size, size))
    cube.apply_translation((x, y, size / 2.0 + z))
    return MeshData.of(cube)


def test_two_parts_side_by_side_are_an_arrangement(profile: Profile) -> None:
    assert arrangement_holds([at(-30.0, 0.0), at(30.0, 0.0)], profile)


def test_parts_on_top_of_each_other_are_not(profile: Profile) -> None:
    """Der Grund für die ganze Prüfung: ohne sie ginge ``--arrange 0`` auch
    dann mit, wenn zwei Teile am selben Platz stehen — und der Slicer druckte
    sie übereinander, statt sie zu retten."""
    assert not arrangement_holds([at(0.0, 0.0), at(5.0, 0.0)], profile)


def test_a_part_outside_the_bed_is_not(profile: Profile) -> None:
    """Der Bauraum des Testprofils ist 256 mm; ein Würfel bei x = 200 ragt
    über die Kante."""
    assert not arrangement_holds([at(200.0, 0.0)], profile)


def test_a_part_sunk_into_the_bed_is_no_arrangement(profile: Profile) -> None:
    """Geprüft wurde nur nach oben — und die Anordnung wird beim Slicer
    **durchgesetzt** (``--arrange 0``).

    Ein Teil bei z = -15 steckt zur Hälfte im Druckbett. Der Slicer ordnet
    nicht an, weil Solidon sagt, die Anordnung halte; er schneidet ab, was
    unter null liegt, und druckt einen halben Körper. Die Grenze ist dieselbe
    wie in ``check_build_volume``: unter dem Bett ist unter dem Bett.
    """
    assert not arrangement_holds([at(0.0, 0.0, z=-15.0)], profile)
    assert not arrangement_holds([at(-30.0, 0.0), at(30.0, 0.0, z=-15.0)], profile)


def test_a_floating_part_is_no_arrangement(profile: Profile) -> None:
    """Und die andere Richtung: Ein Teil bei z = 50 hängt in der Luft.

    Mit übernommener Anordnung druckt der Slicer es dort — fünfzig Millimeter
    Stützmaterial oder ein Klumpen auf der Platte. Wird stattdessen ihm das
    Anordnen überlassen, setzt er es ab, und genau dafür gibt es diese
    Prüfung.

    Die Grenze ist die von ``prepare._floats``: ein Hundertstelmillimeter ist
    Rundung, darüber ist ein Spalt.
    """
    assert not arrangement_holds([at(0.0, 0.0, z=50.0)], profile)
    assert arrangement_holds([at(0.0, 0.0, z=0.005)], profile), "Rundung ist kein Schweben"


def test_nothing_at_all_is_no_arrangement(profile: Profile) -> None:
    assert not arrangement_holds([], profile)


def test_the_handover_places_the_parts_the_export_does_not(
    tmp_path: Path, profile: Profile
) -> None:
    """Zwei Zwecke, zwei Dateien: was zum Slicer geht, trägt die Platzierung;
    was der Nutzer exportiert, bleibt im Koordinatensystem des Dokuments —
    sonst läge eine zurückgelesene Platte um den halben Bauraum verschoben im
    nächsten Dokument.
    """
    objects = [scene_object(), scene_object("obj_2", "Zweites")]

    plain, _findings = write_assembly(objects, tmp_path, project_name="export", profile=profile)
    placed, _more = write_assembly(
        objects, tmp_path, project_name="uebergabe", profile=profile, place_on_bed=True
    )

    assert "transform" not in plain.read_bytes().decode("utf-8", errors="replace")
    text = zipfile.ZipFile(BytesIO(placed.read_bytes())).read(threemf.MODEL_PATH).decode("utf-8")
    assert 'transform="1 0 0 0 1 0 0 0 1 128 128 0"' in text


def _dremel(profile: Profile, origin: tuple[float, float]) -> Profile:
    """Ein Drucker mit dem Bett des Dremel 3D45, wie OrcaSlicer es führt."""
    printer = replace(
        profile.printer,
        build_volume=(225.0, 155.0, 170.0),
        printable_area=(),
        bed_exclusions=(),
        bed_origin=origin,
    )
    return replace(profile, printer=printer)


@pytest.mark.parametrize(
    ("origin", "first", "second"),
    [
        # Dremel 3D45 (Orca): Bett von -127,5 bis 97,5 und -77,5 bis 77,5.
        ((15.0, 0.0), "-15 0 0", "255 0 0"),
        # Ein Bett um den Ursprung: Solidons Mitte ist die der Maschine.
        ((0.0, 0.0), None, "270 0 0"),
    ],
)
def test_the_handover_places_the_parts_around_the_machines_own_origin(
    tmp_path: Path,
    profile: Profile,
    origin: tuple[float, float],
    first: str | None,
    second: str,
) -> None:
    """RM-424: Die Übergabe verschob jedes Teil um das halbe Bett, auch an einer
    Maschine, deren Nullpunkt nicht in der Ecke liegt. Die 3MF für den Dremel
    3D45 setzte einen Würfel aus der Bettmitte auf (112,5 / 77,5) — an den
    hinteren Rand eines Betts, das bei 77,5 endet. Die zweite Platte rückt um
    dasselbe Raster wie an jeder Maschine (``plate_origin``)."""
    on_dremel = _dremel(profile, origin)
    two = [scene_object(), replace(scene_object("obj_2", "Zweites"), plate=2)]

    placed, _findings = write_assembly(
        two, tmp_path, project_name="dremel", profile=on_dremel, place_on_bed=True
    )

    text = zipfile.ZipFile(BytesIO(placed.read_bytes())).read(threemf.MODEL_PATH).decode("utf-8")
    transforms = re.findall(r'<item objectid="(\d+)"(?: transform="([^"]+)")?', text)
    shifts = [entry[1].removeprefix("1 0 0 0 1 0 0 0 1 ") or None for entry in transforms]
    assert shifts == [first, second]


def test_the_handover_to_cura_is_stl_because_curaengine_reads_no_3mf(
    tmp_path: Path, profile: Profile
) -> None:
    """CuraEngine liest kein 3MF — die 3MF-Seite sitzt in Curas Oberfläche.

    Der Slicen-Knopf schrieb trotzdem immer eine 3MF-Baugruppe und reichte sie
    weiter: jeder Lauf endete in „Der Slicer hat keine Druckdatei
    geschrieben", ohne dass irgendwo stand, warum. Derselbe Körper als STL
    läuft durch.
    """
    written, _findings = write_assembly(
        [scene_object()], tmp_path, project_name="uebergabe", profile=profile, flavour="cura"
    )

    assert written.suffix == ".stl"
    assert read_mesh(written.read_bytes(), ".stl").volume > 0.0


def test_the_cura_handover_carries_every_part_of_the_plate(
    tmp_path: Path, profile: Profile
) -> None:
    """Ein Druckauftrag bleibt einer, auch wenn das Format keine Baugruppe kennt."""
    first = scene_object()
    second = scene_object("obj_2", "Zweites")
    second = replace(second, mesh=apply(second.mesh, translation((60.0, 0.0, 0.0))))

    written, _findings = write_assembly(
        [first, second], tmp_path, project_name="uebergabe", profile=profile, flavour="cura"
    )

    joined = read_mesh(written.read_bytes(), ".stl")
    assert joined.volume == pytest.approx(first.mesh.volume + second.mesh.volume, rel=1e-6)
    assert joined.bounds.size[0] > first.mesh.bounds.size[0], "beide Teile, nicht eines"


def test_cura_input_stays_centred_before_the_engine_moves_it(
    tmp_path: Path, profile: Profile
) -> None:
    """CuraEngine verschiebt das STL selbst vom Bettzentrum zum Maschinenursprung."""
    written, _findings = write_assembly(
        [scene_object()],
        tmp_path,
        project_name="uebergabe",
        profile=profile,
        flavour="cura",
        place_on_bed=True,
    )

    before = scene_object().mesh.bounds.centre
    centre = read_mesh(written.read_bytes(), ".stl").bounds.centre
    assert centre[0] == pytest.approx(before[0], abs=0.01)
    assert centre[1] == pytest.approx(before[1], abs=0.01)


def test_every_family_gets_the_parts_in_bed_coordinates(tmp_path: Path, profile: Profile) -> None:
    """Nur die Projektleser benötigen schon verschobene Eingabepunkte."""
    width, depth, _height = profile.printer.build_volume
    for flavour in ("cura", "prusa", "orca"):
        written, _findings = write_assembly(
            [scene_object()],
            tmp_path / flavour,
            project_name="uebergabe",
            profile=profile,
            flavour=flavour,  # type: ignore[arg-type]
            place_on_bed=True,
        )
        if flavour == "cura":
            centre = read_mesh(written.read_bytes(), ".stl").bounds.centre
            assert centre[0] == pytest.approx(0.0, abs=0.01), flavour
            assert centre[1] == pytest.approx(0.0, abs=0.01), flavour
        else:
            text = (
                zipfile.ZipFile(BytesIO(written.read_bytes()))
                .read(threemf.MODEL_PATH)
                .decode("utf-8")
            )
            assert f'transform="1 0 0 0 1 0 0 0 1 {width / 2.0:g} {depth / 2.0:g} 0"' in text, (
                flavour
            )


def _asks_only_a_flavour(function: object) -> bool:
    """Ist das eine Funktion, die genau eine Slicer-Familie beantwortet?

    Erkannt an der Signatur und nicht am Namen: **ein** Parameter, und der
    heißt ``flavour``. Das trifft die sieben, die es gab, und jedes weitere,
    das jemand daneben schreibt — und es trifft nicht ``flavour_of`` (nimmt
    einen Dateinamen) oder ``values_for`` (nimmt drei Dinge).
    """
    import inspect

    if not inspect.isfunction(function):
        return False
    parameters = list(inspect.signature(function).parameters)
    return parameters == ["flavour"]


def test_every_flavour_answers_every_property() -> None:
    """Jede Familie hat zu jeder Eigenschaft eine Antwort — und sie steht hier.

    Die Prädikate in ``slicer_keys`` sind der eine Ort, an dem einer
    Slicer-Familie eine Eigenschaft zugeordnet wird. Diese Tabelle ist ihr
    Gegenstück im Test: Sie schreibt den Bestand fest, damit ein Prädikat sich
    nicht unbemerkt umdreht, und sie ist die Liste, die jemand ausfüllen muss,
    der eine vierte Familie einführt.

    Der Bestand ist ausdrücklich **kein** Muster: Sechs der elf Zeilen
    trennen die Orca-Familie von den anderen beiden, eine gilt für alle, eine stellt Cura allein
    (``has_key_definitions``), und wer daraus „Orca kann alles" liest, hat die
    Ursache verwechselt. Sie kann es, weil sie ihre
    Profile als Dateien führt, die Solidon lesen kann; Cura führt seine
    Einstellungen ausschließlich auf der Kommandozeile, und PrusaSlicer legt
    keine Profile ab, die eine Auswahl trügen.

    Gegenprobe gefahren: Jedes der Prädikate einmal auf ``True`` festgenagelt,
    jedes Mal wird diese Tabelle rot.
    """
    # ``other`` ist seit dem 22.09.2026 die vierte Familie: ein Programm, dem
    # Solidon nur die Datei ins Fenster gibt (RM-071). Es antwortet auf jede
    # Eigenschaft mit „nein" — bis auf die Bettkoordinaten, die eine Aussage
    # über einen G-Code sind, den es nie schreibt.
    expected: dict[str, dict[SlicerFlavour, bool]] = {
        # Seit dem 05.09.2026 jede: Der Drucker misst von der Ecke, gleich
        # welcher Slicer die Datei schreibt (CORE-17, siehe das Prädikat).
        "wants_bed_coordinates": {"prusa": True, "orca": True, "cura": True, "other": True},
        "needs_bed_translation": {"prusa": True, "orca": True, "cura": False, "other": False},
        "has_user_profile_tree": {"prusa": False, "orca": True, "cura": False, "other": False},
        "has_filament_profiles": {"prusa": False, "orca": True, "cura": False, "other": False},
        "reads_settings_from_project_file": {
            "prusa": False,
            "orca": True,
            "cura": False,
            "other": False,
        },
        "names_its_own_output": {"prusa": False, "orca": True, "cura": False, "other": False},
        "has_readable_profiles": {"prusa": True, "orca": True, "cura": True, "other": False},
        "reads_assembly_file": {"prusa": True, "orca": True, "cura": False, "other": False},
        "takes_a_machine_profile": {"prusa": False, "orca": True, "cura": False, "other": False},
        # **Die einzige Zeile, in der Cura allein steht**, und sie fehlte hier,
        # bis die Vollständigkeitsprüfung darunter sie ans Licht holte: Nur
        # neben CuraEngine liegt eine Datei, die jeden gültigen Schlüssel nennt
        # (``fdmprinter.def.json``). Sie ist dort die einzige Gegenprobe, die
        # es gibt, denn CuraEngine schreibt seine wirksame Konfiguration nicht
        # in den G-Code — Prusa und Orca tun es und prüfen sich damit selbst.
        "has_key_definitions": {"prusa": False, "orca": False, "cura": True, "other": False},
        # Die Maschine aus einer Druckerdefinition der Installation (Stufe D,
        # 27.09.2026): Nur CuraEngine bekommt sie so; die Orca-Familie lädt
        # ein Profil, PrusaSlicer bekommt sie in Solidons ``.ini``.
        "machine_from_definition": {"prusa": False, "orca": False, "cura": True, "other": False},
        # Je Teil ein Netz mit eigenen Werten auf der Kommandozeile (Stufe D):
        # So reist die Stützsperre zu CuraEngine als ``anti_overhang_mesh``.
        "takes_mesh_settings": {"prusa": False, "orca": False, "cura": True, "other": False},
        # Mehrere Platten in einer Projektdatei — die Orca-Familie speichert
        # ihre Projekte so; PrusaSlicer und Cura kennen eine Platte je Datei.
        "knows_plates": {"prusa": False, "orca": True, "cura": False, "other": False},
        # Die Stützsperre als eigenes Teil (Orca-Beilage) statt als Bereich im
        # Netz (Prusa-Beilage) — jede Familie liest nur ihre Schreibweise und
        # druckte die andere als Kunststoff (26.09.2026). Cura bekommt ein STL.
        "helpers_as_parts": {"prusa": False, "orca": True, "cura": False, "other": False},
        # Das Tempo nach dem Volumenstrom des Filaments deckeln PrusaSlicer und
        # die Orca-Familie selbst; ein Tempodeckel als Vorschlag ändert dort
        # nichts am Druck (Gesamtprüfung, 27.09.2026). Cura liest den Wert nicht.
        "caps_volumetric_speed": {"prusa": True, "orca": True, "cura": False, "other": False},
    }
    flavours = set(get_args(SlicerFlavour))
    assert len(flavours) >= 4, f"zu wenige Familien gefunden: {flavours}"

    for name, answers in expected.items():
        assert set(answers) == flavours, f"{name}: Tabelle und Literal weichen ab"
        predicate = getattr(slicer_keys, name)
        for flavour, wanted in answers.items():
            assert predicate(flavour) is wanted, f"{name}({flavour})"

    # **Und die Tabelle muss vollständig sein, nicht nur richtig.** Sie ist
    # bis zum 03.09.2026 über ``expected`` gelaufen und hat damit nur geprüft,
    # was jemand eingetragen hatte. Ein achtes Prädikat kam an diesem Tag dazu
    # (``takes_a_machine_profile``, aus dem Fall „Cura bekam eine Warnung über
    # ein Maschinenprofil, das es nie lädt") — und wäre stillschweigend
    # ungeprüft geblieben, weil die Schleife es nie zu Gesicht bekommt.
    #
    # Der Docstring nennt diese Tabelle „die Liste, die jemand ausfüllen muss,
    # der eine vierte Familie einführt". Ein Versprechen, das nur gilt, wenn
    # jemand daran denkt, ist keines.
    found = {
        name
        for name in dir(slicer_keys)
        if not name.startswith("_")
        and callable(getattr(slicer_keys, name))
        and _asks_only_a_flavour(getattr(slicer_keys, name))
    }
    assert found == set(expected), (
        f"nicht in der Tabelle: {sorted(found - set(expected))}; "
        f"nicht als Prädikat gefunden: {sorted(set(expected) - found)}"
    )


@pytest.mark.parametrize("flavour", get_args(SlicerFlavour))
def test_the_print_file_is_checked_in_machine_coordinates(
    profile: Profile, flavour: SlicerFlavour
) -> None:
    """Alle Familien prüfen Bahnen ohne Bettkopf vom Ursprung bis zur vollen Größe."""
    width, depth, height = profile.printer.build_volume
    start = "G90\nM83\n;LAYER:0\nG0 X0 Y0 Z0\n"
    inside = start + f"G1 X{width} Y{depth} Z{height} E1\n"
    assert handover.off_the_bed(inside, profile, flavour) is None

    for axis, bound in zip("XYZ", (width, depth, height), strict=True):
        for outside in (-2.0, bound + 2.0):
            moving_axis = "Y" if axis == "X" else "X"
            text = start + f"G1 {moving_axis}1 {axis}{outside} E1\n"
            finding = handover.off_the_bed(text, profile, flavour)
            assert finding is not None, (flavour, axis, outside)
            assert finding.code == "gcode.off_the_bed"
            assert finding.source == "gcode"


def test_a_machine_with_its_origin_in_the_middle_is_checked_around_it(profile: Profile) -> None:
    """Eine Cura-Maschine mit ``machine_center_is_zero`` misst von der Bettmitte (RM-330)."""
    width, depth, height = profile.printer.build_volume
    start = "G90\nM83\n;LAYER:0\n"
    corner, opposite = f"X{-width / 2} Y{-depth / 2}", f"X{width / 2} Y{depth / 2}"
    around = start + f"G0 {corner} Z0\nG1 {opposite} Z{height} E1\n"

    assert handover.off_the_bed(around, profile, "cura", origin_at_centre=True) is None
    assert handover.off_the_bed(around, profile, "cura") is not None, "ab der Ecke ragt es hinaus"
    beyond = start + f"G0 X0 Y0 Z0\nG1 X{width / 2 + 2.0} Y1 E1\n"
    finding = handover.off_the_bed(beyond, profile, "cura", origin_at_centre=True)
    assert finding is not None and finding.values["excess_mm"] == pytest.approx(2.0)


@pytest.mark.parametrize("flavour", get_args(SlicerFlavour))
def test_a_print_file_without_a_bed_is_checked_around_the_printers_origin(
    profile: Profile, flavour: SlicerFlavour
) -> None:
    """RM-424: Ohne Bett in der Druckdatei gilt das des Druckerprofils — und
    dessen Nullpunkt. Am Dremel 3D45 reicht das Bett von -127,5 bis 97,5; die
    Gegenprobe maß bis dahin von 0 bis 225 und meldete jeden Druck links der
    Maschinenmitte als daneben."""
    on_dremel = _dremel(profile, (15.0, 0.0))
    start = "G90\nM83\n;LAYER:0\n"
    across = start + "G0 X-127 Y-77 Z0\nG1 X97 Y77 Z100 E1\n"
    assert handover.off_the_bed(across, on_dremel, flavour) is None

    beyond = start + "G0 X0 Y0 Z0\nG1 X100 Y1 E1\n"
    finding = handover.off_the_bed(beyond, on_dremel, flavour)
    assert finding is not None and finding.values["excess_mm"] == pytest.approx(2.5)


def _solid(object_id: str = "obj_2", name: str = "Flansch") -> SceneObject:
    """Ein Körper, der seine Flächen kennt — als Attrappe, ohne OpenCASCADE.

    ``BRepBody`` ist ein Protokoll (§30), und ``kind_of`` prüft es zur
    Laufzeit. Drei Mitglieder reichen also, und der Test läuft auch dort, wo
    der zweite Kern nicht installiert ist.
    """

    class Attrappe:
        @property
        def shape(self) -> object:
            return object()

        @property
        def deflection(self) -> float:
            return MAX_FACET_SAG

        @property
        def solid_count(self) -> int:
            return 1

        def to_mesh(self, *, deflection: float | None = None) -> object:
            return body()

    return SceneObject(id=object_id, name=name, mesh=Attrappe())  # type: ignore[arg-type]


def test_a_mesh_exported_as_step_is_told_before_the_file_is_written(
    profile: Profile,
) -> None:
    """**Der Plan war ohne einen Befund, und der Fehler kam beim Schreiben.**

    Wer ``teil.step`` tippte, wählte Format, Ordner und Namen — und erfuhr erst
    danach, dass ein Netz keine Flächen hat. Die Auskunft war die ganze Zeit
    verfügbar: Der Körper weiß, ob er exakt ist, und das Format weiß, ob es das
    braucht.

    Das Fenster bietet STEP inzwischen nur an, wenn ein exakter Körper dabei
    ist; die Kommandozeile hat keinen Dialog, der etwas ausgraut, und zeigt die
    Befunde des Plans **vor** dem Schreiben.
    """
    plan = plan_export(
        [scene_object()], project_name="Projekt", profile=profile, export_format="step"
    )

    codes = {finding.code for finding in plan.findings}
    assert "export.needs_solid" in codes
    finding = next(entry for entry in plan.findings if entry.code == "export.needs_solid")
    assert finding.severity == "error"
    assert finding.object_id == "obj_1", "welcher Körper es ist"
    gesagt = str(finding.message)
    assert "bearbeitbare Flächen und Kanten" in gesagt
    assert "festen Dreiecken" in gesagt
    assert "B-Rep" not in gesagt and "exakter Körper" not in gesagt
    assert "STL" in gesagt and "3MF" in gesagt, "Regel 17: was jetzt geht"


def test_a_solid_exported_as_step_is_not_complained_about(profile: Profile) -> None:
    """Die Prüfung darf das Format nicht abschaffen, nur erklären."""
    plan = plan_export([_solid()], project_name="Projekt", profile=profile, export_format="step")

    assert "export.needs_solid" not in {finding.code for finding in plan.findings}


def test_a_mixed_selection_names_the_body_that_cannot_go(profile: Profile) -> None:
    """**Der Fall, der auch im Fenster bleibt.** STEP wird angeboten, sobald
    *ein* exakter Körper dabei ist — die Netze daneben scheitern einzeln, und
    dann will der Nutzer wissen, welche.
    """
    plan = plan_export(
        [scene_object(), _solid()],
        project_name="Projekt",
        profile=profile,
        export_format="step",
    )

    betroffen = [f.object_id for f in plan.findings if f.code == "export.needs_solid"]
    assert betroffen == ["obj_1"], "nur das Netz, nicht der exakte Körper"


def test_a_mixed_step_export_writes_the_solids_and_leaves_the_meshes(
    tmp_path: Path, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Zusage der Prüfung wird eingelöst, statt beim ersten Netz
    abzubrechen.

    ``check_before_export`` sagt es je Objekt, „weil der Export die exakten
    Körper schreibt und die Netze auslässt" — geschrieben wurde stattdessen
    bis zum ersten Netz, und dann flog der Fehler. Was schon auf der Platte
    lag, blieb liegen: ein halber Export mit einer Fehlermeldung darüber.

    Der zweite Kern ist hier nicht installiert, also schreibt eine Attrappe
    die Bytes; geprüft wird der Ablauf, nicht der Inhalt einer STEP-Datei.
    """
    from app.core.export import writer

    monkeypatch.setattr(writer, "_step_bytes", lambda body, name="", slots=None: b"ISO-10303-21;\n")
    plan = plan_export(
        [scene_object(), _solid(), scene_object("obj_3", "Winkel")],
        project_name="Projekt",
        profile=profile,
        export_format="step",
    )

    written = write_plan(plan, tmp_path, "step")

    assert [entry.name for entry in written] == ["Projekt_Flansch_2von3.step"]
    assert {
        finding.object_id for finding in plan.findings if finding.code == "export.needs_solid"
    } == {
        "obj_1",
        "obj_3",
    }, "und der Bericht nennt die beiden, die nicht gehen"


def test_step_for_meshes_alone_still_refuses(tmp_path: Path, profile: Profile) -> None:
    """Die Grenze der Nachsicht: Bleibt nichts übrig, wird nichts geschrieben
    — und das wird gesagt.

    Ein Aufruf, der leise null Dateien schreibt und Erfolg meldet, ist
    schlimmer als der Fehler davor.
    """
    plan = plan_export(
        [scene_object()], project_name="Projekt", profile=profile, export_format="step"
    )

    with pytest.raises(NeedsSolidError) as caught:
        write_plan(plan, tmp_path, "step")

    text = f"{caught.value.title} {caught.value.detail}"
    assert "bearbeitbare Flächen und Kanten" in text
    assert "festen Dreiecken" in text
    assert "B-Rep" not in text and "exakter Körper" not in text
    assert caught.value.suggestions, "Regel 17"
    assert not list(tmp_path.iterdir()), "und keine halbe Bescherung im Ordner"


@pytest.mark.parametrize("export_format", ["stl", "3mf", "obj", "ply"])
def test_the_mesh_formats_say_nothing_about_solids(profile: Profile, export_format: str) -> None:
    """Ein Netz als STL ist der Normalfall und kein Befund."""
    plan = plan_export(
        [scene_object()],
        project_name="Projekt",
        profile=profile,
        export_format=export_format,  # type: ignore[arg-type]
    )

    assert "export.needs_solid" not in {finding.code for finding in plan.findings}


def test_a_part_in_bed_coordinates_is_offered_the_arranging(profile: Profile) -> None:
    """Der häufigste Fall von Weg 1, und er bekam drei Handlungen, die nicht
    helfen.

    Eine 3MF aus Bambu Studio, Orca oder Elegoo führt **Bettkoordinaten**.
    Gemessen an einer heruntergeladenen Ente: die drei Körper liegen bei x 83
    bis 216 und y 43 bis 113, auf einem Bett um den Ursprung also rechts
    draußen. Der größte ist 132 mm breit und passt dreimal aufs Bett.

    Angeboten wurden über die Kennung ``arrange.out_of_build_volume`` genau die
    drei Handlungen, die hier nichts ausrichten — teilen, verkleinern, anderen
    Drucker wählen (``FINDING_ACTIONS``). Was hilft, ist das Anordnen, und das
    hängt an ``arrange.off_the_plate``.
    """
    from app.ui import panels

    ente = apply(body(), translation((150.0, 78.0, 0.0)))
    findings = check_before_export([scene_object(mesh=ente)], profile, {})

    codes = {finding.code for finding in findings}
    assert "arrange.off_the_plate" in codes, codes
    handlungen = {
        action.id
        for finding in findings
        if finding.code == "arrange.off_the_plate"
        for action in panels.actions_for(finding)
    }
    assert "arrange_on_bed" in handlungen
    assert not handlungen & {"split_model", "scale_to_fit", "choose_printer"}, (
        "keine Handlung, die an der Größe ansetzt — die Größe stimmt"
    )


def test_the_export_says_why_the_machine_side_is_missing(
    tmp_path: Path, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anschlusstest: Der Befund liegt nicht nur bereit, er kommt auch heraus.

    ``handover.machine_missing`` allein zu prüfen hieße zu prüfen, dass die
    Auskunft *gerechnet* werden **kann**. Der Fall vom 03.09.2026 war ein
    anderer: Die Begründung existierte längst als Protokollzeile und erreichte
    niemanden. Also wird hier der Weg gefahren, den die Anwendung geht — eine
    Baugruppe schreiben und nachsehen, was in den Befunden steht.
    """
    from app.core.export import slicer_profiles

    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_: "Bambu Lab A1 0.2 nozzle")
    # ElegooSlicer kennt den Centauri Carbon 2; der Kunde kann umstellen (RM-431).
    monkeypatch.setattr(slicer_profiles, "supports_printer", lambda *_: True)
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")
    settings = print_settings.resolve(profile, "standard")

    _written, findings = write_assembly(
        [scene_object("obj_1", "Deckel")],
        tmp_path,
        project_name="Gehäuse",
        profile=profile,
        settings=settings,
        setup=setup,
    )

    treffer = [finding for finding in findings if finding.code == "slicer.machine_mismatch"]
    assert treffer, [finding.code for finding in findings]
    assert "Bambu Lab A1 0.2 nozzle" in str(treffer[0].values["machine"])
    assert treffer[0].suggestions, "Regel 17"


def test_a_plain_export_hears_nothing_about_a_foreign_slicer(
    tmp_path: Path, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne gewählten Slicer bleibt die Einstellung eines fremden Programms außen vor.

    ``write_assembly`` baut sich für die Filamentprüfung einen Platzhalter aus
    dem Familiennamen. Diesen nach seiner eingestellten Maschine zu fragen
    ergäbe einen Satz über einen Slicer, den der Kunde gerade nicht benutzt —
    er speichert eine 3MF und sonst nichts.
    """
    from app.core.export import slicer_profiles

    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_: "Bambu Lab A1 0.2 nozzle")
    # ElegooSlicer kennt den Centauri Carbon 2; der Kunde kann umstellen (RM-431).
    monkeypatch.setattr(slicer_profiles, "supports_printer", lambda *_: True)
    settings = print_settings.resolve(profile, "standard")

    _written, findings = write_assembly(
        [scene_object("obj_1", "Deckel")],
        tmp_path,
        project_name="Gehäuse",
        profile=profile,
        settings=settings,
    )

    assert not [f for f in findings if f.code.startswith("slicer.machine_")]


def test_the_step_refusal_offers_the_way_out_it_names(profile: Profile) -> None:
    """Derselbe Fall, zwei Wege — und nur einer trug den Knopf.

    ``export.needs_solid`` erreicht den Kunden auf zwei Wegen: als Befund im
    Prüfbericht und als geworfener Fehler, wenn er ``teil.step`` tippt. Der
    Befund bietet seit dem 30.08.2026 *Als 3MF speichern* an; die Ausnahme bot
    nur *Abbrechen*. Gemessen am selben Tag:

        geworfen    ['cancel']
        als Befund  ['export_as_mesh', 'show_details']

    Formal genügte das Regel 17 — ein Vorschlag war da. Praktisch endete der
    häufigere der beiden Wege mit „geht nicht, brich ab", während die Handlung
    dazu im Fenster fertig lag: ``_export_as_mesh_after_error`` trägt den Fall
    im Namen und wurde nie gerufen.

    **Seit P4.0 sind es zwei Auswege, und der zum Körper steht vorn:** *In
    Flächen und Kanten umwandeln* macht aus dem Netz, was STEP tragen kann;
    *Als 3MF speichern* bleibt für den, der kein STEP braucht. Beide stehen vor
    dem Abbruch.
    """
    from app.core.errors import CANCEL, CONVERT_TO_EXACT, EXPORT_AS_MESH
    from app.core.export.writer import _needs_solid

    ausgaenge = [action.id for action in _needs_solid().suggestions]

    assert EXPORT_AS_MESH.id in ausgaenge, ausgaenge
    assert ausgaenge[:2] == [CONVERT_TO_EXACT.id, EXPORT_AS_MESH.id], ausgaenge
    assert ausgaenge.index(CANCEL.id) > 1, "die Auswege stehen vor dem Abbruch"


def test_a_name_the_customer_typed_reaches_the_disc_unchanged(
    tmp_path: Path, profile: Profile
) -> None:
    """Wer den Dateinamen selbst eingibt, hat entschieden.

    Der ``_ExportWorker`` reicht den Stem des im Speichern-Dialog gewählten
    Pfads als ``project_name`` durch, und der ging durch dieselbe Bereinigung
    wie ein erzeugter Name: „Gehäuse Deckel" wurde ``Gehaeuse_Deckel``, ein
    „Halter V2+" verlor sein Plus. Gemessen am 03.09.2026 über den Weg der
    Oberfläche — drei Exporte, dreimal ein anderer Name als der getippte
    (Entscheidung Robert: unverändert nehmen).

    Der **Objektname** im selben Dateinamen bleibt bereinigt: Er entsteht, statt
    getippt zu werden, und für ihn gilt die Konvention weiter.
    """
    plan = plan_export(
        [scene_object("obj_1", "Größe L")],
        project_name="Gehäuse Deckel V2+",
        profile=profile,
        scheme="{project}",
    )
    written = write_plan(plan, tmp_path)

    assert [path.stem for path in written] == ["Gehäuse Deckel V2+"], (
        "Umlaut, Leerzeichen und Plus stehen so da, wie sie getippt wurden"
    )

    beides = plan_export(
        [scene_object("obj_1", "Größe L")],
        project_name="Gehäuse Deckel",
        profile=profile,
        scheme="{project}_{object}",
    )
    assert [path.stem for path in write_plan(beides, tmp_path)] == ["Gehäuse Deckel_Groesse_L"], (
        "der getippte Teil bleibt, der erzeugte wird transliteriert"
    )


def test_a_typed_name_still_loses_what_no_disc_can_hold(tmp_path: Path, profile: Profile) -> None:
    """Erlaubt ist, was möglich ist — und Pfadtrenner sind es nicht.

    Die Gegenrichtung zum Test darüber: Ohne sie wäre „unverändert nehmen" die
    Erlaubnis, mit einem Doppelpunkt oder einem Schrägstrich ein Verzeichnis zu
    wechseln. Ein leerer Rest fällt auf den Rückfall zurück, sonst entstünde
    eine Datei, die nur ihre Endung ist.
    """
    plan = plan_export(
        [scene_object("obj_1", "Teil")],
        project_name="../ganz/woanders:x?",
        profile=profile,
        scheme="{project}",
    )
    written = write_plan(plan, tmp_path)

    assert len(written) == 1
    assert written[0].parent == tmp_path, "die Datei bleibt im gewählten Ordner"
    assert "/" not in written[0].stem and ":" not in written[0].stem

    leer = plan_export(
        [scene_object("obj_1", "Teil")],
        project_name=":::",
        profile=profile,
        scheme="{project}",
    )
    assert write_plan(leer, tmp_path)[0].stem == "projekt", "ein leerer Rest bekommt den Rückfall"


def _object_values(written: Path, member: str) -> dict[str, dict[str, str]]:
    """Die Objektwerte einer Baugruppe je Objektname — aus
    ``model_settings.config`` (Orca-Familie) oder ``Slic3r_PE_model.config``
    (PrusaSlicer)."""
    config = ET.fromstring(zipfile.ZipFile(written).read(member))
    values: dict[str, dict[str, str]] = {}
    for node in config.iter("object"):
        own = {meta.get("key", ""): meta.get("value", "") for meta in node.findall("metadata")}
        values[own.pop("name", node.get("id", ""))] = own
    return values


def _plate_value(written: Path, flavour: SlicerFlavour, key: str) -> object:
    """Ein Wert der Platte, wie die Baugruppe ihn trägt."""
    archive = zipfile.ZipFile(written)
    if flavour == "prusa":
        for line in archive.read("Metadata/Slic3r_PE.config").decode("utf-8").splitlines():
            name, _sep, value = line.removeprefix("; ").partition(" = ")
            if name == key:
                return value
        return None
    return json.loads(archive.read("Metadata/project_settings.config")).get(key)


def test_an_accepted_brim_goes_only_to_the_part_that_needs_it(
    tmp_path: Path, profile: Profile
) -> None:
    """*Vorschläge übernehmen* setzt „brim" als übernommenen Vorschlag
    (``advise.apply``), und seit Stufe E bekommt ihn nur das Teil, das ihn
    braucht (Konzept Herstellerprofil, Entscheidung G; RM-250). Die Platte
    behält die Grundlage, der schlanke Turm trägt den Brim als Objektwert, die
    breite Platte nichts. Vorher bekam jedes Teil einen Rand, auch das, das
    breit auf dem Bett steht — Material, das der Kunde wieder abschneidet.
    """
    schlank = MeshData.of(trimesh.creation.box(extents=(4.0, 4.0, 80.0)))
    breit = MeshData.of(trimesh.creation.box(extents=(60.0, 60.0, 10.0)))
    objects = [
        replace(scene_object("obj_1", "Turm"), mesh=schlank),
        replace(scene_object("obj_2", "Platte"), mesh=breit),
    ]
    settings = print_settings.resolve(profile, "standard")
    assert settings.adhesion.kind == "skirt", "die Vorbedingung des Tests"
    brim = SettingAdvice(
        path="adhesion.kind",
        value="brim",
        was="skirt",
        reason="Dieses Teil ist hoch und schmal.",
        severity="warning",
    )
    settings = advise.apply(settings, [brim])
    assert "adhesion.kind" in settings.accepted

    written, findings = write_assembly(
        objects, tmp_path, project_name="Gehäuse", profile=profile, settings=settings
    )

    treffer = [finding for finding in findings if finding.code == "export.part_setting"]
    assert [finding.object_id for finding in treffer] == ["obj_1"], "nur der Turm"
    assert _plate_value(written, "orca", "brim_type") == "no_brim", "die Platte bleibt"
    values = _object_values(written, "Metadata/model_settings.config")
    assert values["Turm"]["brim_type"] == "outer_only"
    assert "brim_type" not in values["Platte"]


def _two_blocks() -> list[SceneObject]:
    """Zwei Klötze, die keines Rats je Teil bedürfen: kein Überhang, breiter Fuß."""
    return [
        replace(
            scene_object("obj_1", "Klotz"),
            mesh=MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 10.0))),
        ),
        replace(
            scene_object("obj_2", "Platte"),
            mesh=MeshData.of(trimesh.creation.box(extents=(30.0, 30.0, 10.0))),
        ),
    ]


def test_an_accepted_suggestion_no_part_asks_for_goes_to_every_part(
    tmp_path: Path, profile: Profile
) -> None:
    """Ein übernommener Vorschlag verschwindet nie still (Durchsicht 0.5.1, B2).

    Fragt der Export den Rat je Teil und keines verlangt ihn — weil die
    Grundlage des Herstellers schon hält oder weil Dialog und Export an
    verschiedenen Netzen rechnen —, bekommt jedes Teil den übernommenen Wert
    als Objektwert, und der Bericht sagt es. Die Platte bleibt die Grundlage,
    damit Datei und Konsolenlauf dieselbe Platte tragen. Bis dahin stand der
    Wert nirgends in der Datei.
    """
    settings = print_settings.resolve(profile, "standard")
    assert settings.support.style == "none", "die Vorbedingung des Tests"
    settings = print_settings.with_accepted(settings, "support.style", "auto")

    written, findings = write_assembly(
        _two_blocks(), tmp_path, project_name="Klötze", profile=profile, settings=settings
    )

    assert _plate_value(written, "orca", "enable_support") in ("0", ["0"]), "die Platte bleibt"
    values = _object_values(written, "Metadata/model_settings.config")
    assert values["Klotz"]["enable_support"] == "1"
    assert values["Platte"]["enable_support"] == "1"
    said = [
        (entry.values["setting"], entry.values["value"])
        for entry in findings
        if entry.code == "export.part_setting_all"
    ]
    assert said == [("support.style", "auto")]
    assert not [entry for entry in findings if entry.code == "export.part_setting"]


def test_an_accepted_width_below_display_precision_is_still_exported(
    tmp_path: Path, profile: Profile
) -> None:
    """N3: Kein Teil verlangt die übernommene Breite von sich aus. Der
    Rückfall muss auch 0,005 mm Änderung erhalten; Anzeigepräzision ist kein
    Gleichheitsmaß für gespeicherte Druckeinstellungen."""
    settings = print_settings.resolve(profile)
    width = settings.layers.line_width + 0.005
    settings = print_settings.with_accepted(settings, "layers.line_width", width)

    written, findings = write_assembly(
        _two_blocks(), tmp_path, project_name="Bahnbreite", profile=profile, settings=settings
    )

    values = _object_values(written, "Metadata/model_settings.config")
    assert all(float(item["line_width"]) == pytest.approx(width) for item in values.values())
    assert any(
        finding.code == "export.part_setting_all"
        and finding.values["setting"] == "layers.line_width"
        for finding in findings
    )


def test_calm_walls_of_a_slender_rod_go_only_to_the_rod(tmp_path: Path, profile: Profile) -> None:
    """Die ruhigen Wände der schlanken Stange gehören nur an die Stange (RM-328).

    Der Druckdialog fragt mit gemessenen Schichten und nennt nur die Stange
    (8 × 8 × 122 mm auf 64 mm²). Der Export schnitt den Körper nur, wenn ein
    Pfad aus Stützen, Haftung oder Wandbild je Teil ging; Wandtempo und
    Beschleunigung fehlten, der Rat je Teil kam ohne Schnitt und schwieg, und
    ``_unserved`` legte die übernommenen Werte an jedes Teil — auch an den
    breiten Block daneben, mit ``export.part_setting_all``.
    """
    stange = MeshData.of(trimesh.creation.box(extents=(8.0, 8.0, 122.0)))
    block = MeshData.of(trimesh.creation.box(extents=(60.0, 60.0, 10.0)))
    objects = [
        replace(scene_object("obj_1", "Stange"), mesh=stange),
        replace(scene_object("obj_2", "Block"), mesh=block),
    ]
    settings = print_settings.resolve(profile, "standard")
    calm = {
        "speed.outer_wall": advise.SLENDER_WALL_SPEED,
        "speed.inner_wall": advise.SLENDER_WALL_SPEED,
        "speed.outer_wall_acceleration": advise.CAREFUL_ACCELERATION,
        "speed.acceleration": advise.CAREFUL_ACCELERATION,
    }
    for path, value in calm.items():
        assert float(print_settings.read_path(settings, path)) > value, (
            f"die Vorbedingung des Tests: {path}"
        )
        settings = print_settings.with_accepted(settings, path, value)

    written, findings = write_assembly(
        objects,
        tmp_path,
        project_name="Stange",
        profile=profile,
        settings=settings,
        setup=handover.SlicerSetup(Path("OrcaSlicer.exe"), "orca"),
    )

    assert not [entry for entry in findings if entry.code == "export.part_setting_all"]
    treffer = {
        (finding.object_id, finding.values["setting"])
        for finding in findings
        if finding.code == "export.part_setting"
    }
    assert treffer == {("obj_1", path) for path in calm}, treffer
    values = _object_values(written, "Metadata/model_settings.config")
    for key in ("outer_wall_speed", "inner_wall_speed", "default_acceleration"):
        assert key in values["Stange"], (key, values["Stange"])
        assert key not in values["Block"], (key, values["Block"])


def test_cura_keeps_the_rods_calm_walls_on_the_rod(tmp_path: Path, profile: Profile) -> None:
    """RM-317: Cura nimmt alle vier ruhigen Wandwerte je Netz an; die
    Referenz erhält auch die abgeleiteten Rollenwerte ihrer Grundlage."""
    stange = MeshData.of(trimesh.creation.box(extents=(8.0, 8.0, 122.0)))
    block = MeshData.of(trimesh.creation.box(extents=(60.0, 60.0, 10.0)))
    objects = [
        replace(scene_object("obj_1", "Stange"), mesh=stange),
        replace(scene_object("obj_2", "Block"), mesh=block),
    ]
    settings = print_settings.resolve(profile, "standard")
    calm = {
        "speed.outer_wall": advise.SLENDER_WALL_SPEED,
        "speed.inner_wall": advise.SLENDER_WALL_SPEED,
        "speed.outer_wall_acceleration": advise.CAREFUL_ACCELERATION,
        "speed.acceleration": advise.CAREFUL_ACCELERATION,
    }
    for path, value in calm.items():
        settings = print_settings.with_accepted(settings, path, value)

    written, findings = write_assembly(
        objects, tmp_path, project_name="Stange", profile=profile, settings=settings, flavour="cura"
    )

    per_part = {
        (finding.object_id, finding.values["setting"])
        for finding in findings
        if finding.code == "export.part_setting"
    }
    assert per_part == {
        ("obj_1", "speed.outer_wall"),
        ("obj_1", "speed.inner_wall"),
        ("obj_1", "speed.acceleration"),
        ("obj_1", "speed.outer_wall_acceleration"),
    }
    plate_wide = [entry for entry in findings if entry.code == "export.part_setting_unavailable"]
    assert not plate_wide
    meshes = {mesh.path.name: dict(mesh.settings) for mesh in handover.cura_meshes(written)}
    assert meshes["Stange-part-1.stl"]["speed_wall_0"] == "60"
    baseline = print_settings.resolve(profile, "standard")
    assert float(meshes["Stange-part-2.stl"]["speed_wall_x"]) == baseline.speed.inner_wall
    assert float(meshes["Stange-part-2.stl"]["acceleration_wall_x"]) == baseline.speed.acceleration


def test_the_calm_walls_of_a_slender_rod_keep_the_limit_of_soft_filament() -> None:
    """Eine spätere Regel lockert keine frühere (RM-328).

    TPU-95A darf höchstens 30 mm/s fahren (``FLEXIBLE_MAX_SPEED``). Die
    ruhigen Wände der schlanken Stange kamen danach mit 60 mm/s, verglichen
    mit den Ausgangswerten statt mit dem schon geltenden Vorschlag, und der
    Volumenstrom machte 41 mm/s daraus — schneller, als das Filament fördert.
    """
    from app.core.slice.analysis import slice_body

    profile = profiles.make_profile("centauri-carbon-2", "tpu-95a")
    settings = print_settings.resolve(profile, "standard")
    for path in ("speed.outer_wall", "speed.inner_wall"):
        settings = print_settings.with_path(settings, path, 100.0)
    rod = MeshData.of(trimesh.creation.box(extents=(8.0, 8.0, 122.0)))
    result = slice_body(rod, settings.layers.layer_height, support_volume=False)
    assert 0.0 < result.first_layer_area < advise.SMALL_FOOTPRINT, "die Vorbedingung"

    for entries in (
        advise.advise(settings, profile, result, bounds=rod.bounds, flavour="orca"),
        advise.for_part(settings, rod.bounds, 64.0, profile=profile, result=result, flavour="orca"),
    ):
        speeds = {entry.path: entry.value for entry in entries}
        assert speeds["speed.outer_wall"] == pytest.approx(advise.FLEXIBLE_MAX_SPEED)
        assert speeds["speed.inner_wall"] == pytest.approx(advise.FLEXIBLE_MAX_SPEED)


def test_every_path_the_cut_decides_makes_the_export_cut_the_part() -> None:
    """Wächter zu RM-328: Jeder Pfad, den der Rat aus dem Schnitt setzt, steht
    in ``advise.SLICED_PATHS``. Fehlt einer, fragt der Export den Rat je Teil
    ohne Schnitt, und der übernommene Wert landet an jedem Teil."""
    import ast
    import inspect
    import textwrap

    from app.core.knowledge.print_settings import read_path

    settings = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "pla"))

    def is_path(text: str) -> bool:
        try:
            read_path(settings, text)
        except ValidationError:
            return False
        return "." in text

    found: set[str] = set()
    for rule in (advise._from_geometry, advise._calm_walls):
        tree = ast.parse(textwrap.dedent(inspect.getsource(rule)))
        found |= {
            node.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and is_path(node.value)
        }

    assert found, "die Gegenprobe: der Wächter findet Pfade"
    assert found <= advise.SLICED_PATHS, sorted(found - advise.SLICED_PATHS)


def test_cura_keeps_an_accepted_suggestion_no_part_asks_for(
    tmp_path: Path, profile: Profile
) -> None:
    """Bei Cura trägt die Platte die Übernahme, und ein Netz, das sie nicht
    braucht, bekommt die Grundlage zurück. Braucht sie keines, nahm jedes sie
    zurück — der Vorschlag war weg (B2). Jetzt bleibt sie an allen."""
    settings = print_settings.with_accepted(
        print_settings.resolve(profile, "standard"), "support.style", "auto"
    )

    written, findings = write_assembly(
        _two_blocks(),
        tmp_path,
        project_name="Klötze",
        profile=profile,
        settings=settings,
        flavour="cura",
    )

    meshes = {mesh.path.name: dict(mesh.settings) for mesh in handover.cura_meshes(written)}
    assert [entry.get("support_enable") for entry in meshes.values()] == ["true", "true"], meshes
    assert "export.part_setting_all" in {entry.code for entry in findings}


def test_the_export_adds_no_brim_by_itself(tmp_path: Path, profile: Profile) -> None:
    """Ohne *Vorschläge übernehmen* bekommt kein Teil einen Brim (RM-250).

    Seit dem 03.09.2026 setzte der Export einem hohen, schmalen Teil einen
    Brim, auch wenn die Platte auf Skirt stand — mit Befund, aber ohne Klick.
    Roberts Regel vom 26.09.2026: Nur mit „Vorschläge übernehmen" wird auf das
    Modell zugeschnitten, sonst geht der Standard zum Slicer. Am Minigolf-Satz
    im ElegooSlicer lief deshalb ein anderer Rand als mit dem Profil des
    Herstellers allein (8,5 statt 11,7 m), bei gleicher Konfiguration.
    """
    schlank = MeshData.of(trimesh.creation.box(extents=(4.0, 4.0, 80.0)))
    breit = MeshData.of(trimesh.creation.box(extents=(60.0, 60.0, 10.0)))
    objects = [
        replace(scene_object("obj_1", "Turm"), mesh=schlank),
        replace(scene_object("obj_2", "Platte"), mesh=breit),
    ]
    settings = print_settings.resolve(profile, "standard")
    assert settings.adhesion.kind == "skirt", "die Vorbedingung des Tests"

    written, findings = write_assembly(
        objects, tmp_path, project_name="Gehäuse", profile=profile, settings=settings
    )

    assert not [finding for finding in findings if finding.code == "export.part_setting"]
    config = zipfile.ZipFile(written).read("Metadata/model_settings.config").decode("utf-8")
    assert "brim" not in config, "kein Brim je Teil in der Beilage"


def test_an_accepted_brim_for_a_part_is_said_out_loud(tmp_path: Path, profile: Profile) -> None:
    """Ist die Haftung übernommen, schreibt der Export den Brim je Teil — und
    sagt es.

    Gleich, welcher Wert übernommen ist: Die Platte bekommt die Grundlage, und
    der Brim steht an den Teilen, deren Geometrie ihn verlangt (Konzept
    Herstellerprofil, Entscheidung G; siehe
    :func:`test_an_accepted_brim_goes_only_to_the_part_that_needs_it`).

    **Der Grund lag dabei fertig da.** ``SettingAdvice`` trägt ihn mit, und
    sein Docstring sagt warum: „eine Zahl ohne Begründung ist im Zweifel
    schlechter als die Vorgabe, weil niemand sie nachprüfen kann." Gemessen am
    03.09.2026 kam aus ``for_part`` der fertige Satz „Dieses Teil ist hoch und
    schmal. Die Düse kann es beim Anfahren kippen." — und ``object_keys``
    machte daraus Slicer-Schlüssel und warf den Satz weg.

    Für den Kunden zählt es doppelt: Ein Brim kostet Material und muss
    abgeschnitten werden. Wer drei von fünfzehn Teilen mit Rand aus dem Drucker
    nimmt und seine Platte auf Skirt gestellt hat, sucht den Fehler bei sich.

    Einmal je Grund und nicht je Teil — dieselbe Zurückhaltung wie beim
    ungedeckelten Schnitt: Zwölf gleiche Sätze verdrängen elf andere.
    """
    schlank = MeshData.of(trimesh.creation.box(extents=(4.0, 4.0, 80.0)))
    breit = MeshData.of(trimesh.creation.box(extents=(60.0, 60.0, 10.0)))
    objects = [
        replace(scene_object("obj_1", "Turm"), mesh=schlank),
        replace(scene_object("obj_2", "Platte"), mesh=breit),
    ]
    settings = print_settings.resolve(profile, "standard")
    assert settings.adhesion.kind == "skirt", "die Vorbedingung des Tests"
    settings = print_settings.with_accepted(settings, "adhesion.kind", "skirt")

    _written, findings = write_assembly(
        objects, tmp_path, project_name="Gehäuse", profile=profile, settings=settings
    )

    treffer = [finding for finding in findings if finding.code == "export.part_setting"]
    assert treffer, [finding.code for finding in findings]
    assert [finding.object_id for finding in treffer] == ["obj_1"], "nur der Turm"
    assert "Brim" in str(treffer[0].message), treffer[0].message
    assert treffer[0].values["setting"] == "adhesion.kind"
    assert treffer[0].values["value"] == "brim"


@pytest.mark.parametrize("adhesion", ["skirt", "brim"])
def test_cura_says_when_part_settings_cannot_be_carried(
    tmp_path: Path, profile: Profile, adhesion: str
) -> None:
    """Curas STL trägt keinen Brim je Körper; der Export erklärt den unerfüllten Rat."""
    mesh = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 80.0)))
    body = replace(scene_object("obj_1", "Turm"), mesh=mesh)
    settings = print_settings.resolve(profile, "standard")
    settings = print_settings.with_accepted(settings, "adhesion.kind", adhesion)

    written, findings = write_assembly(
        [body], tmp_path, project_name="Turm", profile=profile, settings=settings, flavour="cura"
    )

    assert written.suffix == ".stl"
    assert read_mesh(written.read_bytes(), ".stl").volume == pytest.approx(mesh.volume)
    unavailable = [entry for entry in findings if entry.code == "export.part_setting_unavailable"]
    assert len(unavailable) == (1 if adhesion == "skirt" else 0)
    assert not [entry for entry in findings if entry.code == "export.part_setting"]
    if unavailable:
        assert unavailable[0].severity == "warning"
        assert unavailable[0].values["setting"] == "adhesion.kind"
        assert unavailable[0].values["value"] == "brim"
        assert unavailable[0].object_id == "obj_1"
        assert str(unavailable[0].values["reason"])


def _mushroom_and_block() -> list[SceneObject]:
    """Ein Pilz — Stiel 10 × 10 × 20, Hut 40 × 40 × 3, 15 mm frei auskragend,
    ohne Stützen nicht zu drucken — und daneben ein Klotz ohne Überhang."""
    stem = trimesh.creation.box(extents=(10.0, 10.0, 20.0))
    stem.apply_translation((0.0, 0.0, 10.0))
    cap = trimesh.creation.box(extents=(40.0, 40.0, 3.0))
    cap.apply_translation((0.0, 0.0, 21.5))
    block = trimesh.creation.box(extents=(30.0, 30.0, 10.0))
    block.apply_translation((0.0, 0.0, 5.0))
    return [
        replace(
            scene_object("obj_1", "Pilz"), mesh=MeshData.of(trimesh.boolean.union([stem, cap]))
        ),
        replace(scene_object("obj_2", "Klotz"), mesh=MeshData.of(block)),
    ]


@pytest.mark.parametrize(
    ("flavour", "member", "key"),
    [
        ("orca", "Metadata/model_settings.config", "enable_support"),
        ("prusa", "Metadata/Slic3r_PE_model.config", "support_material"),
    ],
)
def test_supports_go_only_to_the_part_whose_geometry_needs_them(
    tmp_path: Path, profile: Profile, flavour: SlicerFlavour, member: str, key: str
) -> None:
    """Ein übernommener Stützvorschlag gilt dem Körper, der ihn braucht
    (Konzept Herstellerprofil, Entscheidung G): Die Platte bleibt ohne
    Stützen, der Pilz bekommt sie als Objektwert, der Klotz nichts. Vorher
    stützte der Slicer die ganze Platte, und an jedem Teil ohne Überhang stand
    ein Satz Stützeinstellungen, der nur Zeit kostete, wo er griff."""
    settings = print_settings.resolve(profile, "standard")
    assert settings.support.style == "none", "die Vorbedingung des Tests"
    settings = print_settings.with_accepted(settings, "support.style", "auto")

    written, findings = write_assembly(
        _mushroom_and_block(),
        tmp_path,
        project_name="Pilze",
        profile=profile,
        settings=settings,
        flavour=flavour,
    )

    assert _plate_value(written, flavour, key) in ("0", ["0"]), "die Platte stützt nicht"
    values = _object_values(written, member)
    assert values["Pilz"][key] == "1"
    assert key not in values["Klotz"]
    if flavour == "prusa":
        # Prusas Grundlage stützt nur an Verstärkern (``support_material_auto =
        # 0``); ohne den zweiten Schalter am Teil blieb der Pilz ohne Stütze —
        # gemessen in der Abnahme von Stufe E, PrusaSlicer 2.9.6.
        assert values["Pilz"]["support_material_auto"] == "1"
    treffer = [finding for finding in findings if finding.code == "export.part_setting"]
    assert [(finding.object_id, finding.values["setting"]) for finding in treffer] == [
        ("obj_1", "support.style")
    ]


def test_cura_takes_supports_back_where_a_part_does_not_need_them(
    tmp_path: Path, profile: Profile
) -> None:
    """CuraEngine nimmt ob gestützt wird je Netz an (``support_enable``), die
    Stützart aber nur für die Platte (``support_structure``, Cura 5.13). Die
    Übernahme bleibt deshalb auf der Platte, und der Klotz bekommt sie je Netz
    zurückgenommen; der Pilz verlangt automatische Stützen und erhält die
    Stützart der Platte. Je Netz steht nur, was Cura dort liest."""
    settings = print_settings.with_accepted(
        print_settings.resolve(profile, "standard"), "support.style", "tree"
    )

    written, findings = write_assembly(
        _mushroom_and_block(),
        tmp_path,
        project_name="Pilze",
        profile=profile,
        settings=settings,
        flavour="cura",
    )

    meshes = {mesh.path.name: dict(mesh.settings) for mesh in handover.cura_meshes(written)}
    assert meshes == {
        "Pilze-part-1.stl": {"support_enable": "true"},
        "Pilze-part-2.stl": {"support_enable": "false"},
    }
    treffer = [finding for finding in findings if finding.code == "export.part_setting"]
    assert [(finding.object_id, finding.values["value"]) for finding in treffer] == [
        ("obj_1", "tree")
    ]


def test_the_scarf_seam_goes_to_the_round_part_only(tmp_path: Path, profile: Profile) -> None:
    """Die Schrägnaht gilt dem runden Teil (Entscheidung G): Das Rohr hat
    keine Ecke, in der die Naht verschwindet, der Klotz daneben vier. Die
    Platte bleibt ohne, das Rohr bekommt sie als Objektwert bei der
    Orca-Familie und PrusaSlicer, und bei Cura nimmt das Netz des Klotzes sie
    zurück."""
    tube = trimesh.creation.cylinder(radius=12.5, height=40.0, sections=128)
    tube.apply_translation((0.0, 0.0, 20.0))
    block = trimesh.creation.box(extents=(25.0, 25.0, 40.0))
    block.apply_translation((0.0, 0.0, 20.0))
    objects = [
        replace(scene_object("obj_1", "Rohr"), mesh=MeshData.of(tube)),
        replace(scene_object("obj_2", "Klotz"), mesh=MeshData.of(block)),
    ]
    settings = print_settings.with_accepted(
        print_settings.resolve(profile, "standard"), "shell.scarf_seam", True
    )

    def written(flavour: SlicerFlavour) -> tuple[Path, list[Finding]]:
        return write_assembly(
            objects,
            tmp_path / flavour,
            project_name="Rohre",
            profile=profile,
            settings=settings,
            flavour=flavour,
        )

    orca, findings = written("orca")
    assert _plate_value(orca, "orca", "seam_slope_type") == "none", "die Platte bleibt"
    values = _object_values(orca, "Metadata/model_settings.config")
    assert values["Rohr"]["seam_slope_type"] == "external"
    assert values["Rohr"]["seam_slope_min_length"] == "20"
    assert "seam_slope_type" not in values["Klotz"]
    said = [finding.object_id for finding in findings if finding.code == "export.part_setting"]
    assert said == ["obj_1"], "einmal, für das Rohr"

    prusa, _findings = written("prusa")
    parts = _object_values(prusa, "Metadata/Slic3r_PE_model.config")
    assert parts["Rohr"]["scarf_seam_placement"] == "contours"
    assert "scarf_seam_placement" not in parts["Klotz"]

    cura, _findings = written("cura")
    meshes = {mesh.path.name: dict(mesh.settings) for mesh in handover.cura_meshes(cura)}
    assert meshes["Rohre-part-1.stl"]["scarf_joint_seam_length"] == "20"
    assert meshes["Rohre-part-2.stl"]["scarf_joint_seam_length"] == "0"


def test_superslicer_gets_no_scarf_seam_it_cannot_read(tmp_path: Path, profile: Profile) -> None:
    """RM-459: SuperSlicer 2.5.59.13 kennt die Schrägnaht aus PrusaSlicer 2.9
    nicht, und sein 3MF-Leser stürzt ab zwei unbekannten Schlüsseln ab — die
    vier ``scarf_seam_*`` genügten. Weder Platte noch Teil bekommen sie, auch
    wenn das Projekt die Schrägnaht selbst gewählt hat; PrusaSlicer behält sie."""
    tube = trimesh.creation.cylinder(radius=12.5, height=40.0, sections=128)
    tube.apply_translation((0.0, 0.0, 20.0))
    objects = [replace(scene_object("obj_1", "Rohr"), mesh=MeshData.of(tube))]
    accepted = print_settings.with_accepted(
        print_settings.resolve(profile, "standard"), "shell.scarf_seam", True
    )
    chosen = print_settings.with_choice(
        print_settings.resolve(profile, "standard"), "shell.scarf_seam", True
    )
    scarf = {entry.key for entry in slicer_keys.TABLES["prusa"] if entry.path == "shell.scarf_seam"}
    assert len(scarf) == 4, "die Vorbedingung"

    for name, settings in (("vorschlag", accepted), ("wahl", chosen)):
        written, _findings = write_assembly(
            objects,
            tmp_path / name,
            project_name="Rohr",
            profile=profile,
            settings=settings,
            flavour="prusa",
            setup=handover.SlicerSetup(Path("superslicer_console.exe"), "prusa"),
        )
        archive = zipfile.ZipFile(written)
        plate = archive.read("Metadata/Slic3r_PE.config").decode("utf-8")
        parts = archive.read("Metadata/Slic3r_PE_model.config").decode("utf-8")
        assert not [key for key in scarf if key in plate or key in parts], name

    prusa, _findings = write_assembly(
        objects,
        tmp_path / "prusa",
        project_name="Rohr",
        profile=profile,
        settings=chosen,
        flavour="prusa",
        setup=handover.SlicerSetup(Path("prusa-slicer-console.exe"), "prusa"),
    )
    assert _plate_value(prusa, "prusa", "scarf_seam_placement") == "contours"


@pytest.mark.parametrize("accepted", [False, True])
def test_superslicer_gets_grid_instead_of_an_unsupported_tree(
    tmp_path: Path, profile: Profile, accepted: bool
) -> None:
    """RM-480: Auch ein übernommener Baumvorschlag erreicht Platte und Teil als
    Kreuzgitter; der Export sagt dem Kunden, dass er die Stützart ersetzt."""
    choose = print_settings.with_accepted if accepted else print_settings.with_choice
    settings = choose(print_settings.resolve(profile), "support.style", "tree")
    settings = print_settings.with_choice(settings, "shell.seam_position", "nearest")
    setup = handover.SlicerSetup(Path("superslicer_console.exe"), "prusa")
    written, findings = write_assembly(
        [scene_object()],
        tmp_path,
        project_name="Stützen",
        profile=profile,
        settings=settings,
        flavour="prusa",
        setup=setup,
    )
    with zipfile.ZipFile(written) as archive:
        plate = archive.read("Metadata/Slic3r_PE.config").decode("utf-8")
        parts = archive.read("Metadata/Slic3r_PE_model.config").decode("utf-8")
    assert "organic" not in plate + parts
    assert "rectilinear-grid" in plate + parts
    assert "seam_position = cost" in plate
    assert any(item.code == "slicer.choice_substituted" for item in findings)
    assert settings.support.style == "tree", "Die gespeicherte Wahl bleibt erhalten."


def test_superslicer_reads_the_fill_pattern_of_its_own_bundle_under_todays_name() -> None:
    """RM-459: ``external_fill_pattern`` steht in SuperSlicers eigenem Bündel,
    sein 3MF-Leser kennt nur ``top_fill_pattern`` und ``bottom_fill_pattern``.
    Ein eigener Wert für einen der beiden bleibt."""
    values = {"external_fill_pattern": "rectilinear", "top_fill_pattern": "monotonic"}

    read = slicer_keys.for_program(values, "prusa", "superslicer")

    assert read == {"top_fill_pattern": "monotonic", "bottom_fill_pattern": "rectilinear"}
    assert slicer_keys.for_program(values, "prusa", "prusaslicer") == values
    assert not slicer_keys.takes("prusa", "shell.scarf_seam", "superslicer")
    assert slicer_keys.takes("prusa", "shell.scarf_seam", "prusaslicer")


def test_every_key_solidon_writes_for_superslicer_is_one_its_reader_knows() -> None:
    """Wächter zu RM-459: jede Zeile der Prusa-Tabelle, die SuperSlicer nach
    :func:`slicer_keys.for_program` bekommt, gegen den gemessenen Bestand seines
    3MF-Lesers (``tests/data/superslicer_3mf_keys.json``). Eine neue Zeile, die
    er nicht kennt, macht den Test rot, bevor ein Kunde den Absturz sieht."""
    measured = json.loads(
        (Path(__file__).parent / "data" / "superslicer_3mf_keys.json").read_text(encoding="utf-8")
    )
    written = dict.fromkeys(
        {entry.key for entry in slicer_keys.TABLES["prusa"]}
        | {key for keys in slicer_keys.ADHESION_KEYS["prusa"].values() for key in keys}
        | {"external_fill_pattern"},
        "1",
    )

    read = slicer_keys.for_program(written, "prusa", "superslicer")

    unknown = sorted(key for key in read if key not in measured["known"])
    assert not unknown, f"SuperSlicer {measured['version']} kennt nicht: {unknown}"
    assert not set(read) & set(measured["unknown"])


def test_a_part_gets_what_its_second_spool_asks_for(tmp_path: Path, profile: Profile) -> None:
    """Der Rat je Teil fragt jede Spule des Teils, nicht nur Slot 0.

    Ein Deckel in PETG mit einem Griff aus TPU: Der Druckdialog fragt je Spule
    und schlägt für das weiche Filament die langsame Außenwand vor. Übernommen
    geht sie je Teil (Entscheidung G) — und der Export fragte bis dahin nur das
    Material von Slot 0. Der Griff bekam den Vorschlag nicht, den der Dialog
    für ihn gezeigt hatte, und das TPU lief mit dem Tempo des PETG.
    """
    from app.core.geom.attributes import used_slots

    griff_netz = MeshData.of(trimesh.creation.box(extents=(30.0, 30.0, 10.0)))
    griff_netz = replace(griff_netz, slots=(0, 1) * (griff_netz.triangle_count // 2))
    assert used_slots(griff_netz) == (0, 1), "die Vorbedingung des Tests"
    objects = [
        replace(
            scene_object("obj_1", "Griff"),
            mesh=griff_netz,
            material_slots=[
                MaterialSlot(0, "Grau", material_type="PETG"),
                MaterialSlot(1, "Weich", material_type="TPU"),
            ],
        ),
        replace(
            scene_object("obj_2", "Deckel"),
            mesh=MeshData.of(trimesh.creation.box(extents=(30.0, 30.0, 10.0))),
        ),
    ]
    settings = print_settings.resolve(profile, "standard")
    assert settings.speed.outer_wall > advise.FLEXIBLE_MAX_SPEED, "die Vorbedingung des Tests"
    assert "speed.outer_wall" not in advise.plate_paths(settings, profile), (
        "für PETG ist das Tempo kein Grund der ganzen Platte"
    )
    settings = print_settings.with_accepted(settings, "speed.outer_wall", advise.FLEXIBLE_MAX_SPEED)

    written, findings = write_assembly(
        objects, tmp_path, project_name="Deckel", profile=profile, settings=settings
    )

    values = _object_values(written, "Metadata/model_settings.config")
    assert float(values["Griff"]["outer_wall_speed"]) == pytest.approx(advise.FLEXIBLE_MAX_SPEED)
    assert "outer_wall_speed" not in values["Deckel"]
    treffer = [finding for finding in findings if finding.code == "export.part_setting"]
    assert [(finding.object_id, finding.values["setting"]) for finding in treffer] == [
        ("obj_1", "speed.outer_wall")
    ]


def test_a_plate_wide_reason_keeps_the_accepted_value_on_the_plate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verlangt das Material den Brim (ABS auf einem offenen Drucker), gilt er
    übernommen der ganzen Platte — auch wo zusätzlich ein Teil schlank ist.
    Bei PLA auf demselben Drucker geht er je Teil (``advise.plate_paths``).

    Die Grundlage ist hier eine mit Schürze, wie der Hersteller sie oft führt;
    Solidons eigene Tabelle legt für ABS schon selbst einen Brim, und dann
    gäbe es nichts zu trennen."""
    from app.core.export import manufacturer

    def split(material: str) -> handover.PartSplit:
        chosen = profiles.make_profile("prusa-mk4s", material)
        skirted = print_settings.with_path(print_settings.resolve(chosen), "adhesion.kind", "skirt")
        monkeypatch.setattr(
            manufacturer,
            "base_settings",
            lambda *_args, **_kwargs: manufacturer.Foundation(skirted, profile=chosen),
        )
        accepted = print_settings.with_accepted(skirted, "adhesion.kind", "brim")
        return handover.split_for_parts(accepted, chosen, None, "orca")

    material = split("abs")
    assert material.per_part == frozenset()
    assert material.plate.adhesion.kind == "brim"

    geometry = split("pla")
    assert geometry.per_part == frozenset({"adhesion.kind"})
    assert geometry.plate.adhesion.kind == "skirt"
    assert geometry.base.adhesion.kind == "skirt"


@pytest.mark.parametrize("flavour", ["orca", "prusa", "cura"])
def test_a_native_flow_limit_does_not_spread_fitting_speed_to_the_plain_block(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flavour: SlicerFlavour
) -> None:
    """B7: P1S/Generic PLA 12 mm³/s und MK4S/Prusament PLA 15 mm³/s
    machten aus der Passungsbremse einen plattenweiten Wert. Das Filament
    deckelt dort der Slicer selbst; nur Cura braucht Solidons Tempodeckel."""
    from app.core.export import manufacturer
    from app.core.scene.project import new_project
    from app.core.types import FeatureRef, Fit

    profile = profiles.make_profile("bambu-p1s", "pla")
    foundation = print_settings.with_path(
        print_settings.resolve(profile), "speed.outer_wall", 200.0
    )
    foundation = print_settings.with_path(foundation, "filament.max_flow", 12.0)
    monkeypatch.setattr(
        manufacturer,
        "base_settings",
        lambda *_args, **_kwargs: manufacturer.Foundation(foundation, profile=profile),
    )
    settings = print_settings.with_accepted(foundation, "speed.outer_wall", 30.0)
    document = new_project(profile.printer.id, "pla").document
    document.fits.append(
        Fit("Passung", FeatureRef("fit", "top"), FeatureRef("mate-other-plate", "bottom"))
    )
    objects = [scene_object("fit", "Passungsteil"), scene_object("block", "Klotz")]
    split = handover.split_for_parts(settings, profile, None, flavour)

    written, _ = write_assembly(
        objects,
        tmp_path,
        project_name="Passung",
        profile=profile,
        settings=settings,
        flavour=flavour,
        document=document,
        checked=[],
    )

    if flavour == "cura":
        assert split.per_part == frozenset()
        assert split.plate.speed.outer_wall == pytest.approx(30.0)
    else:
        assert split.per_part == frozenset({"speed.outer_wall"})
        assert split.plate.speed.outer_wall == pytest.approx(200.0)
        member = (
            "Metadata/model_settings.config"
            if flavour == "orca"
            else "Metadata/Slic3r_PE_model.config"
        )
        key = "outer_wall_speed" if flavour == "orca" else "external_perimeter_speed"
        values = _object_values(written, member)
        assert float(values["Passungsteil"][key]) == pytest.approx(30.0)
        assert key not in values["Klotz"]


def _tapered_cup() -> MeshData:
    """Der Organizer vom 20.09.2026 als Querschnitt: Außenwand 1,0 mm, in einer
    Ecke ein Becher, der die Wand berührt — dort läuft die Stärke stetig von
    1,0 auf 3,0 mm, ein Keil auf jeder Schicht (``test_slice``), ohne Überhang."""
    from shapely.geometry import Point, box

    outer = (
        box(0.0, 0.0, 60.0, 40.0).buffer(6.0, join_style="round").buffer(-6.0, join_style="round")
    )
    block = box(-1.0, -1.0, 21.0, 21.0)
    hole = Point(10.9, 10.9).buffer(9.0, quad_segs=64)
    shape = outer.difference(outer.buffer(-1.0).difference(block)).difference(hole)
    return MeshData.of(trimesh.creation.extrude_polygon(shape, 10.0))


@pytest.mark.parametrize("support", [False, True], ids=["ohne-stuetze", "mit-stuetze"])
def test_a_rule_behind_an_accepted_part_value_is_asked_with_it(
    tmp_path: Path, profile: Profile, monkeypatch: pytest.MonkeyPatch, support: bool
) -> None:
    """Eine Regel, die einen anderen übernommenen Wert je Teil voraussetzt,
    wird mit ihm gefragt (Entscheidung G; Fehldruck vom 29.09.2026).

    „Außenwand zuerst" schlägt die Keil-Regel nur bei variabler Bahnbreite
    vor, und nie, wo Stützen nötig sind. Beide Pfade gehen je Teil, und der
    Split setzt beide auf die Grundlage zurück — beim Centauri Carbon 2
    ``classic``. Einmal dort gefragt, bekam der Keilbecher nur Arachne, kein
    Teil bediente „Außenwand zuerst", und ``_unserved`` legte es an jedes,
    auch an die Schüssel, die Stützen brauchte. Jetzt fragt der Rat je Teil
    nach den übernommenen Werten dieses Teils erneut, bis nichts dazukommt.
    """
    from app.core.export import manufacturer

    classic = print_settings.with_path(
        print_settings.resolve(profile, "standard"), "shell.wall_generator", "classic"
    )
    assert not classic.shell.outer_wall_first, "die Vorbedingung des Tests"
    monkeypatch.setattr(
        manufacturer,
        "base_settings",
        lambda *_args, **_kwargs: manufacturer.Foundation(classic, profile=profile),
    )
    settings = print_settings.with_accepted(classic, "shell.wall_generator", "arachne")
    settings = print_settings.with_accepted(settings, "shell.outer_wall_first", True)
    if support:
        settings = print_settings.with_accepted(settings, "support.style", "auto")
    mushroom = next(entry for entry in _mushroom_and_block() if entry.name == "Pilz")
    objects = [
        replace(scene_object("obj_1", "Becher"), mesh=_tapered_cup()),
        replace(mushroom, id="obj_2"),
    ]

    written, findings = write_assembly(
        objects, tmp_path, project_name="Regelkette", profile=profile, settings=settings
    )

    assert _plate_value(written, "orca", "wall_generator") == "classic", "die Platte bleibt"
    values = _object_values(written, "Metadata/model_settings.config")
    assert values["Becher"]["wall_generator"] == "arachne"
    assert values["Becher"]["wall_sequence"] == "outer wall/inner wall"
    assert "wall_sequence" not in values["Pilz"], "der Pilz braucht Stützen"
    assert "wall_generator" not in values["Pilz"]
    if support:
        assert values["Pilz"]["enable_support"] == "1"
    assert not [entry for entry in findings if entry.code == "export.part_setting_all"]
    said = {
        (entry.object_id, entry.values["setting"])
        for entry in findings
        if entry.code == "export.part_setting"
    }
    assert {("obj_1", "shell.wall_generator"), ("obj_1", "shell.outer_wall_first")} <= said
    assert not {path for owner, path in said if owner == "obj_2"} & {
        "shell.wall_generator",
        "shell.outer_wall_first",
    }


def test_nothing_is_said_when_every_part_takes_the_plates_setting(
    tmp_path: Path, profile: Profile
) -> None:
    """Die Gegenprobe: Wo nichts abweicht, steht auch nichts."""
    breit = MeshData.of(trimesh.creation.box(extents=(60.0, 60.0, 10.0)))
    objects = [replace(scene_object("obj_1", "Platte"), mesh=breit)]

    _written, findings = write_assembly(
        objects,
        tmp_path,
        project_name="Gehäuse",
        profile=profile,
        settings=print_settings.resolve(profile, "standard"),
    )

    assert not [finding for finding in findings if finding.code == "export.part_setting"]


def test_an_empty_object_says_what_to_do_about_it(tmp_path: Path, profile: Profile) -> None:
    """Der schwerste Befund des Exports endete mit „hat keine Geometrie".

    ``export.empty`` ist ``error`` — das Stärkste, was der Prüfbericht sagen
    kann — und trug weder einen eigenen Ausweg noch einen in der Tabelle des
    Fensters. Damit ist es „geht nicht" an einem anderen Ort; Regel 17 gilt im
    Bericht so gut wie im Dialog.

    Gefunden am 03.09.2026 beim Durchzählen aller Fehlerbefunde: Von fünfzehn
    tragen sieben einen Knopf über ``panels.FINDING_ACTIONS``, acht gar nichts.
    Dieser hier liegt im Export und damit an der Stelle, an der er entsteht.

    **Zwei Auswege, beide verdrahtet und beide wahr.** Ein Objekt ohne
    Dreiecke ist entweder das falsche in der Auswahl — dann hilft eine andere
    Auswahl — oder das Ergebnis eines Schritts, der nichts übrig gelassen hat;
    dann steht im Verlauf, welcher. Ein dritter Knopf wäre geraten.

    Am Befund selbst und nicht in der Tabelle des Fensters: ``_actions_for``
    liest ``finding.suggestions`` zuerst und die Tabelle nur als Rückfall. Der
    Grund, warum es hier gehört, ist derselbe wie bei jeder Operation — wer den
    Befund erzeugt, weiß am besten, was hilft.
    """
    leer = MeshData.of(trimesh.Trimesh())
    objects = [replace(scene_object("obj_1", "Nichts"), mesh=leer)]

    _written, findings = write_assembly(objects, tmp_path, project_name="Gehäuse", profile=profile)

    treffer = [finding for finding in findings if finding.code == "export.empty"]
    assert treffer, [finding.code for finding in findings]
    wege = [action.id for action in treffer[0].suggestions]
    assert "change_selection" in wege, wege
    assert "show_history" in wege, wege
    assert treffer[0].object_id == "obj_1", "der Befund nennt das Objekt, um das es geht"


def test_numbering_never_lands_on_a_name_the_job_already_uses(profile: Profile) -> None:
    """Gesamtreview 05.09.2026, CORE-18: ``A``, ``A`` und ``A-1`` wurden
    ``A-1``, ``A-2``, ``A-1`` — die laufende Nummer wurde nie gegen die
    geplanten Namen geprüft, und das erste Teil verschwand unter dem dritten,
    während ``write_plan`` drei Pfade meldete."""
    objects = [
        scene_object("obj_1", "A"),
        scene_object("obj_2", "A"),
        scene_object("obj_3", "A-1"),
    ]

    plan = plan_export(objects, project_name="P", profile=profile, scheme="{object}")

    names = [entry.filename for entry in plan.entries]
    assert names == ["A-2.stl", "A-3.stl", "A-1.stl"], "was allein steht, behält seinen Namen"
    assert len({name.casefold() for name in names}) == 3


def test_numbering_treats_upper_and_lower_case_as_one_name(
    tmp_path: Path, profile: Profile
) -> None:
    """``A.stl`` und ``a.stl`` sind auf Windows und macOS dieselbe Datei:
    zwei gemeldete Pfade, einer auf der Platte, der erste Körper weg. Die
    Kollisionsregel faltet den Namen, auf jeder Plattform."""
    objects = [scene_object("obj_1", "A"), scene_object("obj_2", "a")]

    plan = plan_export(objects, project_name="P", profile=profile, scheme="{object}")
    names = [entry.filename for entry in plan.entries]
    assert len({name.casefold() for name in names}) == 2, names

    written = write_plan(plan, tmp_path)
    assert len(written) == 2
    assert len(list(tmp_path.glob("*.stl"))) == 2, "zwei Dateien auf der Platte"


def test_glb_keeps_every_region_when_slot_names_collide() -> None:
    """Gesamtreview 05.09.2026, CORE-19: Die Teilnetze wurden nach dem
    bereinigten Anzeigenamen abgelegt — zwei Slots namens „Farbe", oder
    ``A/B`` neben ``AB``, ersetzten einander: sechs statt zwölf Dreiecke,
    eine ganze Farbregion fehlte. Die Slotnummer ist die Identität."""
    plain = body()
    two_tone = MeshData(raw=plain.raw, slots=tuple(0 if index < 6 else 1 for index in range(12)))
    for names in (("Farbe", "Farbe"), ("A/B", "AB")):
        slots = [
            MaterialSlot(index=0, name=names[0], colour=(1.0, 0.0, 0.0)),
            MaterialSlot(index=1, name=names[1], colour=(0.0, 0.0, 1.0)),
        ]
        written = trimesh.load(
            BytesIO(export_bytes(two_tone, "glb", slots=slots, name="Schild")),
            file_type="glb",
        )
        assert sum(len(geometry.faces) for geometry in written.geometry.values()) == 12, names


def test_same_colour_but_another_material_stays_its_own_extruder() -> None:
    """Gesamtreview 05.09.2026, CORE-21: Zwei Teile, je ein Slot „Schwarz" in
    Schwarz — eines PLA, eines PETG. Zusammengelegt wurde über Name und
    Farbe: ein Materialeintrag, jedes Dreieck an Düse 0, das PETG-Profil weg.
    Gleicher Name und gleiche Farbe fallen nur zusammen, wenn auch Profil und
    Materialart gleich sind."""
    black = (0.0, 0.0, 0.0)
    pla = MaterialSlot(
        index=0, name="Schwarz", colour=black, material="PLA Basic", material_type="PLA"
    )
    petg = MaterialSlot(
        index=0, name="Schwarz", colour=black, material="PETG Basic", material_type="PETG"
    )
    parts = [
        threemf.AssemblyPart(mesh=MeshData.of(trimesh.creation.box()), name="A", slots=(pla,)),
        threemf.AssemblyPart(mesh=MeshData.of(trimesh.creation.box()), name="B", slots=(petg,)),
    ]

    merged = threemf.merge_slots(parts)
    assert [(slot.index, slot.material_type) for slot in merged] == [(0, "PLA"), (1, "PETG")]

    payload = threemf.write_assembly(parts)
    model = zipfile.ZipFile(BytesIO(payload)).read(threemf.MODEL_PATH).decode("utf-8")
    assert model.count("<base ") == 2, "zwei Materialien in der Baugruppe"
    assert 'p1="1"' in model, "und das zweite Teil zeigt auf das zweite"

    twin = MaterialSlot(
        index=0, name="Schwarz", colour=black, material="PLA Basic", material_type="PLA"
    )
    assert (
        len(
            threemf.merge_slots(
                [parts[0], threemf.AssemblyPart(mesh=parts[1].mesh, name="C", slots=(twin,))]
            )
        )
        == 1
    ), "dasselbe Filament bleibt eine Düse"


def test_glb_is_written_in_metres(tmp_path: Path) -> None:
    """Gesamtreview 05.09.2026, CORE-33: glTF 2.0 legt den Meter als Einheit
    fest (Abschnitt 3.4). Die Millimeter gingen unverändert hinaus — ein
    Quader 10 x 20 x 40 mm kam als 10 x 40 x 20 m an, und nur ein Betrachter
    mit automatischem Einpassen verbarg das."""
    original = MeshData.of(trimesh.creation.box(extents=(10.0, 20.0, 40.0)))
    written = trimesh.load(BytesIO(export_bytes(original, "glb")), file_type="glb")
    extents = written.bounds[1] - written.bounds[0]

    assert sorted(extents) == pytest.approx([0.01, 0.02, 0.04], abs=1e-9)


def test_prusa_gets_the_individual_brim_in_its_own_object_configuration(
    tmp_path: Path, profile: Profile
) -> None:
    """Die zugesagte Objektabweichung muss in Prusas gelesener Beilage stehen."""
    import xml.etree.ElementTree as ET

    tower = trimesh.creation.box(extents=(4.0, 4.0, 20.0))
    tower.apply_translation((0.0, 0.0, 10.0))
    objects = [scene_object(mesh=MeshData.of(tower))]
    settings = print_settings.resolve(profile)
    settings = print_settings.with_accepted(settings, "adhesion.kind", settings.adhesion.kind)
    path, findings = write_assembly(
        objects,
        tmp_path,
        project_name="Turm",
        profile=profile,
        settings=settings,
        flavour="prusa",
    )
    assert "export.part_setting" in {entry.code for entry in findings}
    with zipfile.ZipFile(path) as archive:
        config = ET.fromstring(archive.read("Metadata/Slic3r_PE_model.config"))
    obj = config.find("object")
    assert obj is not None and obj.get("id") == "2"
    assert obj.find("metadata[@type='object'][@key='brim_width']").get("value") == "5"
    assert obj.find("volume").get("lastid") == str(len(tower.faces) - 1)


def test_cura_export_reports_lost_second_material_values(tmp_path: Path, profile: Profile) -> None:
    """Auch der früh zurückkehrende STL-Weg benennt den verlorenen Materialwertsatz."""
    first = replace(
        scene_object("obj_1"), material_slots=(MaterialSlot(0, "PLA", material_type="PLA"),)
    )
    second = replace(
        scene_object("obj_2"), material_slots=(MaterialSlot(0, "PETG", material_type="PETG"),)
    )
    _, findings = write_assembly(
        [first, second],
        tmp_path,
        project_name="Materialien",
        profile=profile,
        settings=print_settings.resolve(profile),
        flavour="cura",
    )
    assert "slicer.overrides_unreachable" in {entry.code for entry in findings}


def test_legacy_body_material_gets_its_own_slot_without_changing_declared_slots() -> None:
    """Ein altes ABS-Körpermaterial darf nicht mit einem unbekannten PLA-Platz verschmelzen."""
    legacy = replace(scene_object(), material="abs")
    original = tuple(legacy.material_slots)
    slots = threemf.slots_for_object(legacy)
    assert len(slots) == 1
    assert slots[0].index == 0 and slots[0].material_type == "ABS"
    assert tuple(legacy.material_slots) == original
    assert threemf.slots_for_object(scene_object()) == ()

    declared = MaterialSlot(0, "Eigene Spule", material="Hersteller PLA", material_type="PLA")
    supplied = replace(legacy, material_slots=[declared])
    assert threemf.slots_for_object(supplied) == (declared,)
    assert threemf.slots_for_object(supplied)[0] is declared

    mesh = replace(legacy.mesh, slots=(0, 1) * (legacy.mesh.triangle_count // 2))
    completed = threemf.assembly_slots(threemf.AssemblyPart(mesh, slots=slots))
    assert [(slot.index, slot.material_type) for slot in completed] == [(0, "ABS"), (1, None)]


def test_legacy_body_material_reaches_assembly_and_single_file_export(
    tmp_path: Path,
) -> None:
    """PLA und altes ABS behalten getrennte Werkzeuge und die jeweils wirksame Temperatur."""
    profile = profiles.make_profile(material_id="pla")
    first = scene_object("obj_1")
    second = replace(scene_object("obj_2"), material="abs")
    target, _ = write_assembly(
        [first, second],
        tmp_path,
        project_name="Alte Materialangaben",
        profile=profile,
        settings=print_settings.resolve(profile),
        flavour="orca",
    )
    with zipfile.ZipFile(target) as archive:
        project = json.loads(archive.read(threemf.PROJECT_SETTINGS_PATH))
    assert project["filament_type"] == ["PLA", "ABS"]
    assert project["nozzle_temperature"] == ["210", "250"]

    plan = plan_export([second], profile=profile, export_format="3mf", project_name="ABS")
    assert plan.entries[0].slots[0].material_type == "ABS"


@pytest.mark.parametrize("flavour", ["prusa", "cura"])
def test_shared_slicer_reports_legacy_material_loss_and_keeps_the_first_material(
    tmp_path: Path, profile: Profile, flavour
) -> None:
    """Ein gemeinsam beschränkter Export rät nicht still das Material der Projektvorgabe."""
    from app.core.export import handover

    legacy = replace(scene_object("obj_1"), material="abs")
    ordinary = scene_object("obj_2")
    settings = print_settings.resolve(profile)
    slots = threemf.merge_slots(
        [
            threemf.AssemblyPart(entry.mesh, slots=threemf.slots_for_object(entry))
            for entry in (legacy, ordinary)
        ]
    )
    effective = handover.settings_for_handover(settings, profile, flavour, slots)
    assert effective.temperature.nozzle == 250
    _, findings = write_assembly(
        [legacy, ordinary],
        tmp_path,
        project_name="Alt und neu",
        profile=profile,
        settings=settings,
        flavour=flavour,
    )
    assert "slicer.overrides_unreachable" in {entry.code for entry in findings}


# --- die Vorgabe steht an einer Stelle (RM-141) -----------------------------------


def test_the_default_scheme_is_asked_and_not_recomputed(profile: Profile) -> None:
    """Das Fenster zeigt dasselbe Muster, nach dem der Kern benennt (§29, RM-141).

    Es schreibt es bei mehreren Dateien ins Namensfeld des Dateidialogs,
    damit der Kunde es ändern kann. Zwei Stellen, die es ausrechnen, wären
    zwei Antworten — und die des Dialogs wäre die sichtbare.
    """
    from app.core.export.writer import DEFAULT_SCHEME, PLATE_SCHEME, SINGLE_SCHEME, default_scheme

    one = scene_object()
    two = [scene_object(), scene_object("obj_2", "Deckel")]
    plates = [scene_object(), replace(scene_object("obj_2", "Deckel"), plate=1)]

    assert default_scheme([one]) == SINGLE_SCHEME
    assert default_scheme(two) == DEFAULT_SCHEME
    assert default_scheme(plates) == PLATE_SCHEME

    plan = plan_export(two, project_name="Projekt", profile=profile)
    assert [entry.filename for entry in plan.entries] == [
        "Projekt_Halterung_1von2.stl",
        "Projekt_Deckel_2von2.stl",
    ], "und der Plan benennt danach"


def test_a_chosen_scheme_decides_the_names(profile: Profile) -> None:
    """Ein selbst gewähltes Muster gilt, Feld für Feld (§29, RM-141).

    Der Kunde tippt es ins Namensfeld; was dort mit Klammern steht, ist ein
    Muster und kein Name. Hier steht, was daraus wird — auch die Reihenfolge,
    denn genau dafür stellt jemand ein Schema um.
    """
    two = [scene_object(), scene_object("obj_2", "Deckel")]

    plan = plan_export(
        two,
        project_name="Projekt",
        profile=profile,
        scheme="{index}_{object}",
    )

    assert [entry.filename for entry in plan.entries] == ["1_Halterung.stl", "2_Deckel.stl"]


def test_a_body_named_like_the_geometry_mark_still_exports() -> None:
    # Der Name reist unverändert ins XML. Vorher zählte die Marke doppelt,
    # und ein RuntimeError riss den Export-Arbeiter ohne einen Weg ab.
    part = threemf.AssemblyPart(
        mesh=MeshData.of(trimesh.creation.box((10, 10, 10))), name="[SOLIDON-MESH-2]"
    )
    with zipfile.ZipFile(BytesIO(threemf.write_assembly([part], "Test"))) as archive:
        model = archive.read("3D/3dmodel.model").decode("utf-8")
    assert 'name="[SOLIDON-MESH-2]"' in model
    assert "SOLIDON-MESH-" not in model.replace("[SOLIDON-MESH-2]", "")
    assert model.count("<vertex ") == 8


@pytest.mark.parametrize("route", ("single", "orca", "prusa", "cura"))
@pytest.mark.parametrize("painted", (False, True))
def test_threemf_preserves_coordinates_for_parts_and_support_blockers(
    route: str, painted: bool
) -> None:
    """RM-252: Die Ausgabe darf Koordinaten auch unter EPS_GEOM nicht runden.

    Am zweifarbigen Besteckeinsatz stürzte Elegoo mit Gitterstützen erst nach
    dieser Rundung ab. Hier bleiben zusätzlich Sperrkörper und alle drei
    Projektformate gegen denselben Verlust abgesichert.
    """
    raw = body().raw.copy()
    raw.apply_transform(trimesh.transformations.rotation_matrix(0.123456789, (1, 2, 3)))
    slots = tuple(index % 2 for index in range(len(raw.faces))) if painted else ()
    mesh = MeshData.of(raw, slots=slots)
    blocker_raw = raw.copy()
    blocker_raw.apply_translation((0.123456789123456, -0.987654321987654, 0.000000123456789))
    blocker = MeshData.of(blocker_raw)
    expected = list(raw.vertices)
    if route == "single":
        payload = threemf.write(mesh)
    else:
        expected.extend(blocker_raw.vertices)
        part = threemf.AssemblyPart(mesh=mesh, support_blocker=blocker)
        payload = threemf.write_assembly(
            [part], blocker_as_part=route != "prusa", cura=route == "cura"
        )
    with zipfile.ZipFile(BytesIO(payload)) as archive:
        root = ET.fromstring(archive.read(threemf.MODEL_PATH))
    written = [
        tuple(float(vertex.attrib[axis]).hex() for axis in ("x", "y", "z"))
        for vertex in root.findall(".//{*}vertex")
    ]
    # Die Bitdarstellung prüft hier die verlustfreie Speicherung, keine
    # geometrische Nähe. Ein EPS-Vergleich hätte den Absturz übersehen.
    assert sorted(written) == sorted(tuple(float(value).hex() for value in row) for row in expected)


# --- Der Kundenweg STL → Operation → STL → Import (RM-166) --------------------


def _drilled_plate_after_an_stl_round(profile: Profile) -> MeshData:
    """Die Platte der Werkstattfilme: 100 x 55 x 8 mit zwei 6-mm-Bohrungen —
    einmal durch eine STL geschickt, damit sie in float32 ankommt wie beim
    Kunden."""
    from app.core.geom.prepare import drill

    plate = MeshData.of(trimesh.creation.box(extents=(100.0, 55.0, 8.0)))
    for x in (-28.0, 28.0):
        plate = drill(
            plate,
            position=(x, 0.0, 4.0),
            axis="z",
            diameter=6.0,
            depth=0.0,
            profile=profile,
            compensate=False,
        ).mesh
    return normalise(read_model(plate.to_stl(), ".stl"), "mm").mesh


def _run_registered(name: str, entry: SceneObject, profile: Profile, **params):
    """Derselbe registrierte Aufruf wie im Dialog."""
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext

    load_operations()
    spec = REGISTRY.get(name)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=1,
            progress=lambda *_: None,
            ask=lambda _, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


@pytest.mark.parametrize("source", ["plate_holes.stl", "gebohrte Platte"])
@pytest.mark.parametrize(
    "operation", ["resize_hole", "move_feature", "fillet_edges", "chamfer_edges"]
)
def test_a_mesh_op_result_on_an_stl_survives_the_weld(
    operation: str, source: str, profile: Profile
) -> None:
    """Was Solidon exportiert, muss der nächste Import — und jeder Slicer — als
    geschlossen lesen (RM-166).

    Gefunden am 13.09.2026 beim Prüfen der Werkstattfilme: Nach *Bohrung
    ändern*, *Merkmal verschieben* und *Fase anbringen* an einer **eingelesenen**
    STL war das Ergebnis per Index dicht, nach dem Verschweißen nicht mehr —
    Solidons eigener Import derselben Datei meldete „Das Modell ist nicht
    geschlossen". Zwei Ursachen: ``manifold3d`` ließ auf dem alten Bohrkreis
    Eckpunktpaare unter der Schweißtoleranz und Sliver stehen (jetzt räumt
    ``boolean._tidied`` auf), und der abziehende Keil der Fase stand mit seinen
    Flanken **in** der fast koplanaren Körperfläche und ließ Haut ohne Dicke
    zurück (jetzt ``BOOLEAN_OVERLAP`` in ``edges.rounding_tool``).

    Zwei Quellen, weil sie verschiedene Fehler zeigen: Am Korpus
    ``plate_holes.stl`` rissen die Bohrungsoperationen, an der gebohrten
    Platte der Filme zusätzlich die Fase über die Bohrungsränder. Der Weg ist
    der des Kunden — ``read_model`` + ``normalise``, Operation über das
    Register, ``to_stl()``, wieder ``read_model`` + ``normalise`` — und die
    Zusicherung ist die von ``repair()``: dicht, Volumen unverändert.
    """
    from app.core.perceive.features import detect

    if source == "plate_holes.stl":
        plate = normalise(read_model((MESHES / source).read_bytes(), ".stl"), "mm").mesh
    else:
        plate = _drilled_plate_after_an_stl_round(profile)
    assert plate.is_watertight
    entry = SceneObject("obj_1", "Platte", plate, features=detect(plate))
    hole = next(feature for feature in entry.features.values() if feature.kind == "hole")
    cx, cy, cz = hole.params["centre"]
    params = {
        "resize_hole": {"at_feature": hole.id, "diameter": 9.0, "compensate": False, "x": cx + 4.0},
        "move_feature": {"at_feature": hole.id, "x": cx + 6.0, "y": cy, "z": cz},
        "fillet_edges": {"radius": 3.0, "edges": "vertical"},
        "chamfer_edges": {"distance": 0.8, "edges": "top"},
    }[operation]

    result = _run_registered(operation, entry, profile, **params)
    made = result.outputs[0].mesh
    assert made.is_watertight, "per Index dicht ist die Voraussetzung, nicht der Befund"

    back = normalise(read_model(made.to_stl(), ".stl"), "mm")
    codes = {finding.code for finding in back.findings}
    assert back.mesh.is_watertight, f"nach der STL-Runde nicht mehr geschlossen — {sorted(codes)}"
    assert "ingest.not_watertight" not in codes and "ingest.degenerate_removed" not in codes, codes
    assert back.mesh.raw.volume == pytest.approx(made.raw.volume, abs=1e-3), (
        "das Verschweißen ändert das Volumen nicht"
    )
    if operation == "move_feature":
        assert made.raw.volume == pytest.approx(plate.raw.volume, abs=1e-3), (
            "ein verschobenes Loch nimmt nichts weg und legt nichts dazu"
        )
    else:
        assert made.raw.volume < plate.raw.volume, "die drei anderen tragen ab"


# --- Cura im Fenster: die Einstellungen als Profil (Durchsicht 0.5.0) --------------


def _cura_install(tmp_path: Path) -> Path:
    """Eine Cura-Installation mit dem, was ihr Profilleser prüft.

    ``fdmprinter.def.json`` trägt die Einstellungsversion und die Typen der
    Einstellungen, zwei allgemeine Qualitätsstufen daneben — gebaut nach Cura
    5.13 (``share/cura/resources``), nicht nach Solidons Vorstellung davon.
    """
    install = tmp_path / "UltiMaker Cura 5.13.0"
    resources = install / "share" / "cura" / "resources"
    (resources / "definitions").mkdir(parents=True)
    (resources / "definitions" / "fdmprinter.def.json").write_text(
        json.dumps(
            {
                "version": 2,
                "name": "FDM Printer",
                "metadata": {"setting_version": 27},
                "settings": {"machine_nozzle_size": {"default_value": 0.4}},
            }
        ),
        encoding="utf-8",
    )
    (resources / "definitions" / "fdmextruder.def.json").write_text(
        json.dumps({"version": 2, "name": "Extruder", "inherits": "fdmprinter"}),
        encoding="utf-8",
    )
    (resources / "quality").mkdir()
    for kind, height in (("draft", 0.2), ("normal", 0.1)):
        (resources / "quality" / f"{kind}.inst.cfg").write_text(
            f"[general]\ndefinition = fdmprinter\nname = {kind}\nversion = 4\n\n"
            f"[metadata]\nglobal_quality = True\nquality_type = {kind}\n"
            "setting_version = 27\ntype = quality\n\n"
            f"[values]\nlayer_height = {height}\n",
            encoding="utf-8",
        )
    # Ein Drucker ohne eigene Qualitäten, wie der Kobra 2 in Cura: Er nimmt
    # die allgemeinen Stufen von ``fdmprinter``.
    (resources / "definitions" / "werkstatt.def.json").write_text(
        json.dumps({"version": 2, "name": "Werkstatt", "inherits": "fdmprinter"}),
        encoding="utf-8",
    )
    engine = install / "CuraEngine.exe"
    engine.write_bytes(b"")
    return engine


def _cura_active(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    name: str = "Werkstatt",
    definition: str = "werkstatt",
    *,
    variant: str = "empty_variant",
    material: str = "empty_material",
) -> None:
    """Curas Konfigurationsordner mit einem eingerichteten, aktiven Drucker.

    Wie Cura 5.13 ihn schreibt: ``cura.cfg`` nennt ihn, sein Stapel in
    ``machine_instances`` die Definition an letzter Stelle, der Stapel des
    ersten Fachs Düse (Stelle 5) und Spule (Stelle 4).
    """
    from app.core.export import slicer_profiles

    config = tmp_path / "config"
    root = config / "cura" / "5.13"
    (root / "machine_instances").mkdir(parents=True)
    (root / "extruders").mkdir()
    (root / "cura.cfg").write_text(
        f"[general]\nversion = 7\n\n[cura]\nactive_machine = {name}\n", encoding="utf-8"
    )
    (root / "machine_instances" / f"{name.replace(' ', '+')}.global.cfg").write_text(
        f"[general]\nversion = 5\nname = {name}\nid = {name}\n\n"
        "[metadata]\nsetting_version = 27\ntype = machine\n\n"
        "[containers]\n0 = empty_user_changes\n1 = empty_quality_changes\n2 = empty_intent\n"
        "3 = empty_quality\n4 = empty_material\n5 = empty_variant\n6 = empty_definition_changes\n"
        f"7 = {definition}\n",
        encoding="utf-8",
    )
    (root / "extruders" / f"{name.replace(' ', '+')}_0.extruder.cfg").write_text(
        f"[general]\nversion = 5\nname = Extruder 1\nid = {name}_0\n\n"
        f"[metadata]\ntype = extruder_train\nmachine = {name}\nposition = 0\n\n"
        "[containers]\n0 = empty_user_changes\n1 = empty_quality_changes\n"
        f"2 = empty_intent\n3 = empty_quality\n4 = {material}\n5 = {variant}\n"
        "6 = empty_definition_changes\n7 = fdmextruder\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(slicer_profiles, "config_home", lambda _platform: str(config))


def _cura_containers(target: Path) -> dict[str, dict[str, dict[str, str]]]:
    """Die Einträge so gelesen wie Curas ``CuraProfileReader``: INI ohne Interpolation."""
    import configparser

    found: dict[str, dict[str, dict[str, str]]] = {}
    with zipfile.ZipFile(target) as archive:
        for name in archive.namelist():
            parser = configparser.ConfigParser(interpolation=None)
            parser.read_string(archive.read(name).decode("utf-8"))
            found[name] = {section: dict(parser[section]) for section in parser.sections()}
    return found


def test_cura_opens_with_its_settings_as_an_importable_profile(
    tmp_path: Path, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """„Im Slicer öffnen" gab Cura ein bloßes STL — die Einstellungen blieben zurück.

    Cura liest aus einer geöffneten Datei nur Geometrie; Einstellungen nimmt
    sein Fenster als Profil an. Seit der Durchsicht 0.5.0 liegt deshalb eine
    ``.curaprofile`` neben dem Modell, und der Befund sagt, wo sie in Cura
    hineingeht. Geprüft wie Curas eigener Leser: Container Version 4, die
    Einstellungsversion der Installation, eine Qualitätsstufe, die es gibt,
    und Wahrheitswerte als ``True`` — ``ast.literal_eval`` liest kein
    ``true``. Maschinenwerte und Abgeleitetes gehören nicht hinein: Das
    Fenster rechnet seine Formeln selbst.
    """
    engine = _cura_install(tmp_path)
    _cura_active(tmp_path, monkeypatch)
    setup = handover.SlicerSetup(engine, "cura")
    settings = print_settings.resolve(profile)
    settings = replace(settings, support=replace(settings.support, style="tree"))
    model = tmp_path / "halter.stl"
    model.write_bytes(b"solid halter\nendsolid halter\n")

    said = handover.cura_profile_beside(model, settings, profile, setup)

    assert said is not None and said.code == "handover.cura_profile"
    assert said.values["file"] == "halter.curaprofile"
    assert said.values["machine"] == "Werkstatt", "der Befund nennt den Drucker in Cura"
    containers = _cura_containers(model.with_suffix(".curaprofile"))
    assert list(containers) == ["solidon"], "eine einzelne Spule legt Cura selbst aufs erste Fach"
    entry = containers["solidon"]
    assert entry["general"]["version"] == "4"
    assert entry["metadata"]["setting_version"] == "27"
    assert entry["metadata"]["type"] == "quality_changes"
    assert entry["metadata"]["quality_type"] == "draft", "die Stufe mit der nächsten Schichthöhe"
    values = entry["values"]
    assert values["layer_height"] == "0.2"
    assert values["support_enable"] == "True"
    assert not [key for key in values if key.startswith("machine_")], "die Maschine bleibt Curas"
    assert "infill_line_distance" not in values, "Abgeleitetes rechnet das Fenster selbst"
    assert not [value for value in values.values() if value in {"true", "false"}]


@pytest.mark.parametrize("top_layers", [0, 4])
def test_the_importable_profile_keeps_surface_and_ironing_at_the_surface_speed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, top_layers: int
) -> None:
    """RM-482: Auch das Fenster bügelt mit dem Tempo der sichtbaren Oberseite."""
    engine = _cura_install(tmp_path)
    _cura_active(tmp_path, monkeypatch)
    profile = profiles.make_profile("sovol-sv06", "pla")
    settings = print_settings.resolve(profile)
    settings = replace(
        settings,
        shell=replace(settings.shell, top_layers=top_layers, ironing=True),
        speed=replace(settings.speed, infill=73.0, top_surface=30.0),
    )
    model = tmp_path / "pilz.stl"

    finding = handover.cura_profile_beside(
        model, settings, profile, handover.SlicerSetup(engine, "cura")
    )

    assert finding is not None and finding.code == "handover.cura_profile"
    written = _cura_containers(model.with_suffix(".curaprofile"))["solidon"]["values"]
    assert written["roofing_layer_count"] == ("1" if top_layers else "0")
    assert written["ironing_enabled"] == "True"
    assert float(written["speed_topbottom"]) == pytest.approx(73.0)
    assert float(written["speed_roofing"]) == pytest.approx(30.0)
    assert float(written["speed_ironing"]) == pytest.approx(20.0)


def test_cura_gets_one_extruder_profile_per_spool(
    tmp_path: Path, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zwei Spulen, zwei Fächer: je Spule ein Extruderprofil mit ``position``."""
    engine = _cura_install(tmp_path)
    _cura_active(tmp_path, monkeypatch)
    model = tmp_path / "zweifarbig.stl"
    model.write_bytes(b"solid z\nendsolid z\n")
    slots = (
        MaterialSlot(index=0, name="Rot", colour="#ff0000", material_type="PETG"),
        MaterialSlot(index=1, name="Weiß", colour="#ffffff", material_type="PLA"),
    )

    handover.cura_profile_beside(
        model,
        print_settings.resolve(profile),
        profile,
        handover.SlicerSetup(engine, "cura"),
        slots,
    )

    containers = _cura_containers(model.with_suffix(".curaprofile"))
    assert [entry["metadata"].get("position") for entry in containers.values()] == [None, "0", "1"]
    assert (
        containers["solidon_extruder_0"]["values"]["material_print_temperature"]
        != containers["solidon_extruder_1"]["values"]["material_print_temperature"]
    ), "PETG und PLA fahren verschiedene Temperaturen"


def test_the_profile_takes_a_quality_of_the_printer_active_in_cura(
    tmp_path: Path, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mit den Stufen von ``fdmprinter`` lehnte Cura das Profil ab oder versteckte es.

    An Elegoos Druckern hieß es „Quality type 'draft' is not compatible", an
    Creality und Sovol war es importiert und unsichtbar (Prüfbericht Cura,
    B9). Die Stufe kommt jetzt vom Drucker, der in Cura aktiv ist, und zwar
    eine, die es für seine Düse und seine Spule gibt: „fein" liegt genau auf
    der Schichthöhe, ein Profil für 0,4 mm und PLA hat aber nur „standard".
    """
    engine = _cura_install(tmp_path)
    resources = engine.parent / "share" / "cura" / "resources"
    for name, body in (
        ("kaste_basis", {"inherits": "fdmprinter", "metadata": {"has_machine_quality": True}}),
        (
            "kaste_k1",
            {"inherits": "kaste_basis", "metadata": {"quality_definition": "kaste_basis"}},
        ),
    ):
        (resources / "definitions" / f"{name}.def.json").write_text(
            json.dumps({"version": 2, "name": name, **body}), encoding="utf-8"
        )
    quality = resources / "quality" / "kaste"
    quality.mkdir()
    for kind, height in (("fein", 0.2), ("standard", 0.24), ("draft", 0.32)):
        (quality / f"kaste_global_{kind}.inst.cfg").write_text(
            f"[general]\ndefinition = kaste_basis\nname = {kind}\nversion = 4\n\n"
            f"[metadata]\nglobal_quality = True\nquality_type = {kind}\n"
            "setting_version = 27\ntype = quality\n\n"
            f"[values]\nlayer_height = {height}\n",
            encoding="utf-8",
        )
    (quality / "kaste_0.4_pla_standard.inst.cfg").write_text(
        "[general]\ndefinition = kaste_basis\nname = Standard\nversion = 4\n\n"
        "[metadata]\nmaterial = generic_pla\nquality_type = standard\n"
        "setting_version = 27\ntype = quality\nvariant = 0.4mm Nozzle\n\n[values]\n",
        encoding="utf-8",
    )
    (resources / "variants" / "kaste").mkdir(parents=True)
    (resources / "variants" / "kaste" / "kaste_basis_0.4.inst.cfg").write_text(
        "[general]\ndefinition = kaste_basis\nname = 0.4mm Nozzle\nversion = 4\n\n"
        "[metadata]\nhardware_type = nozzle\ntype = variant\n",
        encoding="utf-8",
    )
    (resources / "materials").mkdir()
    (resources / "materials" / "generic_pla.xml.fdm_material").write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<fdmmaterial xmlns="http://www.ultimaker.com/material" version="1.3">\n'
        "  <metadata><name><brand>Generic</brand><material>PLA</material>"
        "<color>Generic</color></name></metadata>\n"
        "</fdmmaterial>\n",
        encoding="utf-8",
    )
    _cura_active(
        tmp_path,
        monkeypatch,
        "Kaste K1",
        "kaste_k1",
        variant="kaste_basis_0.4",
        material="generic_pla_175_kaste_k1_0.4",
    )
    model = tmp_path / "halter.stl"
    model.write_bytes(b"solid halter\nendsolid halter\n")
    settings = print_settings.resolve(profile)
    assert settings.layers.layer_height == pytest.approx(0.2), "die Probe braucht 0,2 mm"

    said = handover.cura_profile_beside(
        model, settings, profile, handover.SlicerSetup(engine, "cura")
    )

    assert said is not None and said.code == "handover.cura_profile"
    assert said.values["machine"] == "Kaste K1"
    entry = _cura_containers(model.with_suffix(".curaprofile"))["solidon"]
    assert entry["general"]["definition"] == "kaste_basis", "so führt Cura die Qualitäten"
    assert entry["metadata"]["quality_type"] == "standard", "die Stufe für Düse und Spule"


def test_without_a_printer_in_cura_there_is_no_profile_but_a_way(
    tmp_path: Path, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne eingerichteten Drucker gibt es keine Stufe, auf die das Profil passt.

    Vorher entstand die Datei trotzdem, mit ``draft`` von ``fdmprinter``, und
    ging beim Import still verloren (Prüfbericht Cura, B9). Jetzt sagt ein
    Befund, was zu tun ist, und es liegt keine Datei neben dem Modell.
    """
    from app.core.export import slicer_profiles

    engine = _cura_install(tmp_path)
    monkeypatch.setattr(slicer_profiles, "config_home", lambda _platform: str(tmp_path / "leer"))
    model = tmp_path / "halter.stl"
    model.write_bytes(b"solid halter\nendsolid halter\n")

    said = handover.cura_profile_beside(
        model, print_settings.resolve(profile), profile, handover.SlicerSetup(engine, "cura")
    )

    assert said is not None and said.code == "handover.cura_profile_unbound"
    assert said.severity == "warning"
    assert [action.id for action in said.suggestions] == ["choose_slicer"]
    assert not model.with_suffix(".curaprofile").exists()


def test_only_cura_gets_a_profile_beside_the_model(tmp_path: Path, profile: Profile) -> None:
    """Die anderen Familien tragen ihre Einstellungen in der Datei selbst."""
    model = tmp_path / "teil.3mf"
    model.write_bytes(b"")
    setup = handover.SlicerSetup(tmp_path / "orca-slicer.exe", "orca")

    assert (
        handover.cura_profile_beside(model, print_settings.resolve(profile), profile, setup) is None
    )
    assert not model.with_suffix(".curaprofile").exists()


@pytest.mark.parametrize(
    ("program", "stripped"),
    [("CrealityPrint.exe", True), ("orca-slicer.exe", False)],
)
def test_the_creality_window_gets_the_file_its_console_gets(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: Profile, program: str, stripped: bool
) -> None:
    """Das Fenster bekam die volle Datei, die Konsole eine Kopie ohne Plattenblock.

    Creality Print 7.2 stürzt an diesem Block einer Mehrfilament-3MF ab, und
    Fenster und Konsole sind dasselbe Programm mit demselben 3MF-Leser. Seit
    der Durchsicht 0.5.0 öffnet auch das Fenster die Datei ohne den Block —
    an Ort und Stelle, mit dem Namen, den der Kunde im Austauschordner sieht.
    Namen und Werkzeuge der Körper bleiben; die anderen Slicer bekommen die
    Datei unverändert.
    """
    from app.core.export import slicer_keys

    executable = tmp_path / program
    executable.write_bytes(b"")
    flavour = slicer_keys.flavour_of(program)
    assert flavour == "orca"
    setup = handover.SlicerSetup(executable=executable, flavour=flavour)
    settings = print_settings.resolve(profile)
    parts = [
        threemf.AssemblyPart(
            MeshData.of(trimesh.creation.box((12.0, 12.0, 3.0))),
            name=name,
            slots=(MaterialSlot(index=0, name=name, colour=colour, material_type=kind),),
        )
        for name, colour, kind in (
            ("PLA Orange", (177 / 255, 99 / 255, 10 / 255), "PLA"),
            ("PETG Weiß", (1.0, 1.0, 1.0), "PETG"),
        )
    ]
    slots = threemf.merge_slots(parts)
    model = tmp_path / "Halter.3mf"
    model.write_bytes(
        threemf.write_assembly(
            parts,
            project_settings=handover.project_settings(settings, profile, setup, slots=slots),
        )
    )
    with zipfile.ZipFile(model) as container:
        before = ET.fromstring(container.read(threemf.SETTINGS_PATH))
    assert len(before.findall("plate")) == 1
    opened: list[list[str]] = []
    monkeypatch.setattr(
        handover.subprocess, "Popen", lambda command, **_options: opened.append(command)
    )

    handover.open_in_slicer(model, setup)

    assert len(opened) == 1 and opened[0][-1] == str(model.resolve())
    with zipfile.ZipFile(model) as container:
        after = ET.fromstring(container.read(threemf.SETTINGS_PATH))
    assert len(after.findall("plate")) == (0 if stripped else 1)
    assert [
        entry.find("metadata[@key='name']").get("value") for entry in after.findall("object")
    ] == ["PLA Orange", "PETG Weiß"]
    assert [
        entry.find("metadata[@key='extruder']").get("value") for entry in after.findall("object")
    ] == ["1", "2"]
    assert not list(tmp_path.glob("*.staging.3mf")), "die Zwischenkopie bleibt nicht liegen"


def test_creality_print_7_3_arranges_a_plate_whose_arrangement_does_not_hold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RM-331: Hält Solidons Anordnung nicht (Teil im Ring), geht die Platte ohne
    Bettverschiebung an Creality Print 7.3, und die Konsole ordnet selbst an.

    Gemessen am 02.10.2026 mit 7.3.0.6149: Ring mit Kern, ein schwebendes Teil,
    eines über den Rand und zwei überlappende Teile kamen getrennt und mittig
    auf dem Bett zurück, ohne Abbruch -50 und ohne ``gcode.off_the_bed``. Eine
    Absage mit *Anordnen* nähme dem Kunden hier einen Lauf, der gelingt; der
    Aufruf ist derselbe wie bei haltender Anordnung, nur ohne Zusage.
    """
    profile = profiles.make_profile("creality-ender3-v3-se", "pla")
    settings = print_settings.resolve(profile)
    outer = trimesh.creation.cylinder(radius=30.0, height=10.0, sections=48)
    ring = outer.difference(trimesh.creation.cylinder(radius=25.0, height=12.0, sections=48))
    core = trimesh.creation.cylinder(radius=10.0, height=10.0, sections=32)
    objects = [
        replace(scene_object("obj_1", "Ring"), mesh=place_on_bed(MeshData.of(ring))),
        replace(scene_object("obj_2", "Kern"), mesh=place_on_bed(MeshData.of(core))),
    ]
    keep = arrangement_holds([as_mesh_data(entry.mesh) for entry in objects], profile)
    assert keep is False, "die Vorbedingung: der Kern steht im Grundriss des Rings"
    executable = tmp_path / "Creality Print" / "CrealityPrint.exe"
    executable.parent.mkdir()
    executable.write_bytes(b"")
    setup = handover.SlicerSetup(executable, "orca")
    written, _findings = write_assembly(
        objects,
        tmp_path,
        project_name="Ring",
        profile=profile,
        plate=0,
        settings=settings,
        flavour="orca",
        place_on_bed=keep,
        setup=setup,
    )
    commands: list[list[str]] = []

    class _Finished:
        returncode = 0
        stdout = b""
        stderr = b""

    def creality(command: list[str], *_args: object, **_kwargs: object) -> _Finished:
        commands.append(list(command))
        target = Path(command[command.index("--outputdir") + 1])
        # Wie gemessen: beide Teile mittig auf dem Bett, nebeneinander.
        (target / "plate_1.gcode").write_text(
            "G90\nM82\nG1 Z0.2 F300\nG1 X72.6 Y110 E0.1\nG1 X148.2 Y110 E0.2\n",
            encoding="utf-8",
        )
        return _Finished()

    monkeypatch.setattr(handover, "_run_slicer", creality)
    monkeypatch.setattr(handover, "_REFUSES_THE_CLI_FLAG", set())

    outcome = handover.slice_model(
        [written], settings, profile, setup, keep_arrangement=keep, output_dir=tmp_path / "aus"
    )

    assert len(commands) == 1, "ein Lauf, keine Absage vorher"
    assert "--cli" in commands[0] and "--need-gcode-file" in commands[0]
    assert "--arrange" not in commands[0]
    codes = {entry.code for entry in outcome.findings}
    assert "gcode.off_the_bed" not in codes
    assert "slicer.arranged_itself" not in codes, "Solidon hat keine Anordnung zugesagt"


# --- RM-191: jede Rolle bekommt Solidons Werte (Durchsicht 0.5.0) ---------------


def test_prusa_gets_the_infill_speed_for_solid_infill_and_no_guessed_machine_limits(
    tmp_path: Path, profile: Profile
) -> None:
    """PrusaSlicer fuhr die volle Füllung mit seinen eingebauten 20 mm/s.

    Gemessen am Gewürzregal (RM-191): 48 532 s gegen 23 655 s bei Orca für
    dieselbe Platte; danach 31 387 s gegen 26 471 s, Material innerhalb von
    drei Prozent. Dazu schätzte Prusa mit seinen 1500 mm/s² statt mit den
    angeforderten 8000 (``machine_limits_usage``).
    """
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(tmp_path / "prusa-slicer-console.exe", "prusa")

    written = handover.write_config(settings, profile, setup, tmp_path).written

    assert written["solid_infill_speed"] == f"{settings.speed.infill:g}"
    assert written["gap_fill_speed"] == f"{settings.speed.inner_wall:g}"
    assert written["machine_limits_usage"] == "ignore"


def test_the_orca_family_gets_solidons_speed_and_width_for_every_role(profile: Profile) -> None:
    """Die Orca-Familie fuhr volle Füllung und Lücken mit dem Herstellerprofil.

    Beim Centauri Carbon 2 mit 250 mm/s, während Wände und dünne Füllung
    Solidons Werte bekamen — und Innenwand und Füllung mit 0,45 mm statt
    Solidons Bahnbreite (RM-191).
    """
    settings = print_settings.resolve(profile)

    process = handover.by_section(settings, "orca")["process"]

    assert process["internal_solid_infill_speed"] == f"{settings.speed.infill:g}"
    assert process["gap_infill_speed"] == f"{settings.speed.inner_wall:g}"
    width = f"{settings.layers.line_width:g}"
    for key in (
        "outer_wall_line_width",
        "inner_wall_line_width",
        "sparse_infill_line_width",
        "internal_solid_infill_line_width",
        "top_surface_line_width",
    ):
        assert process[key] == width, key


# --- Die Stützsperre reist nur mit, wenn der Vorschlag übernommen ist ------------


def tunnel_block() -> MeshData:
    """Ein Block 60 × 40 × 40 mit einem Tunnel 20 × 20 quer hindurch.

    Die Tunneldecke hängt über dem Tunnelboden, 20 mm weit — ein Kanal
    (``analysis.CHANNEL_WIDTH``).
    """
    block = trimesh.creation.box(extents=(60.0, 40.0, 40.0))
    block.apply_translation((0.0, 0.0, 20.0))
    tunnel = trimesh.creation.box(extents=(20.0, 50.0, 20.0))
    tunnel.apply_translation((0.0, 0.0, 18.0))
    return MeshData.of(trimesh.boolean.difference([block, tunnel]))


def _blocker_ranges(written: Path) -> list[tuple[str, int, int]]:
    config = ET.fromstring(zipfile.ZipFile(written).read("Metadata/Slic3r_PE_model.config"))
    return [
        (
            volume.find("metadata[@key='volume_type']").get("value", ""),  # type: ignore[union-attr]
            int(volume.get("firstid", "-1")),
            int(volume.get("lastid", "-1")),
        )
        for volume in config.iter("volume")
    ]


def _orca_parts(written: Path) -> list[tuple[str, str]]:
    """Die Teile, die ``model_settings.config`` je Objekt nennt: (Objekt, Art)."""
    config = ET.fromstring(zipfile.ZipFile(written).read("Metadata/model_settings.config"))
    return [
        (node.get("id", ""), part.get("subtype", ""))
        for node in config.iter("object")
        for part in node.iter("part")
    ]


def test_the_support_blocker_travels_only_after_the_advice(
    tmp_path: Path, profile: Profile
) -> None:
    """Ohne „Vorschläge übernehmen" gehen die Standardeinstellungen hinaus,
    und in denen ist nichts auf dieses Modell zugeschnitten (Robert,
    26.09.2026). Mit übernommenem Vorschlag bekommt die Orca-Familie die
    Sperre als eigenes Teil desselben Objekts — so, wie sie es selbst
    schreibt. Als Bereich hinter den Dreiecken des Körpers liest der
    ElegooSlicer die Orca-Beilage, übergeht die Bereichsart und druckte die
    Sperre als Kunststoff in den Kanal (22,8 g mehr an der Waschschüssel)."""
    entry = scene_object(mesh=tunnel_block())
    settings = print_settings.with_path(print_settings.resolve(profile), "support.style", "grid")

    plain, _plain_findings = write_assembly(
        [entry], tmp_path / "ohne", project_name="t", profile=profile, settings=settings
    )
    assert _orca_parts(plain) == []
    assert [kind for kind, _first, _last in _blocker_ranges(plain)] == ["ModelPart"]

    taken = print_settings.with_path(settings, "support.block_channels", True)
    written, findings = write_assembly(
        [entry], tmp_path / "mit", project_name="t", profile=profile, settings=taken
    )
    kinds = _orca_parts(written)
    assert [kind for _object, kind in kinds] == ["normal_part", "support_blocker"]
    assert {owner for owner, _kind in kinds} == {"2"}, "beide Teile gehören zum einen Objekt"
    assert [kind for kind, _first, _last in _blocker_ranges(written)] == ["ModelPart"]
    assert "export.support_blocker" in {finding.code for finding in findings}
    model = zipfile.ZipFile(written).read("3D/3dmodel.model").decode("utf-8")
    assert "slic3rpe:Version3mf" not in model, "die Orca-Familie bleibt bei ihrer Beilage"

    # Und Solidon liest seine eigene Übergabe als den einen Körper zurück.
    read_back = threemf_reader.read_objects(written.read_bytes(), [])
    assert len(read_back) == 1
    assert read_back[0].mesh.triangle_count == as_mesh_data(entry.mesh).triangle_count


def test_prusaslicer_gets_the_blocker_as_a_range_of_the_mesh(
    tmp_path: Path, profile: Profile
) -> None:
    """PrusaSlicer liest die andere Schreibweise: einen Bereich hinter den
    Dreiecken des Körpers, den ``Slic3r_PE_model.config`` benennt. Als eigene
    Komponente druckte er die Sperre als Kunststoff (38,8 g mehr an der
    Waschschüssel) — jede Familie bekommt ihre (``helpers_as_parts``)."""
    entry = scene_object(mesh=tunnel_block())
    taken = print_settings.with_path(
        print_settings.with_path(print_settings.resolve(profile), "support.style", "grid"),
        "support.block_channels",
        True,
    )
    written, _findings = write_assembly(
        [entry], tmp_path, project_name="t", profile=profile, settings=taken, flavour="prusa"
    )

    body, blocker = _blocker_ranges(written)
    triangles = as_mesh_data(entry.mesh).triangle_count
    assert body == ("ModelPart", 0, triangles - 1)
    assert blocker[0] == "SupportBlocker" and blocker[1] == triangles and blocker[2] > triangles
    assert _orca_parts(written) == []
    # Ohne diese Angabe übersprang PrusaSlicer die Bereichsarten ganz: 91,0 m
    # Stütze im Sperrkörper mit und ohne Sperre, mit ihr 6,5 m.
    model = zipfile.ZipFile(written).read("3D/3dmodel.model").decode("utf-8")
    assert '<metadata name="slic3rpe:Version3mf">1</metadata>' in model
    read_back = threemf_reader.read_objects(written.read_bytes(), [])
    assert [part.mesh.triangle_count for part in read_back] == [triangles]


@pytest.mark.parametrize("flavour", ["orca", "cura"])
def test_only_the_part_that_is_supported_gets_a_blocker(
    tmp_path: Path, profile: Profile, flavour: SlicerFlavour
) -> None:
    """Die Sperre folgt den Stützen (Entscheidung G): Übernommen sind Stützen
    und Sperre, aber nur der Tunnelblock mit dem auskragenden Arm braucht
    Stützen — also sperrt nur er seine Kanäle, und der Klotz daneben bekommt
    weder das eine noch das andere. Gesagt wird es einmal, im Befund der
    Sperre mit dem Namen des Teils, nicht noch einmal als „andere Einstellung
    je Teil"."""
    arm = trimesh.creation.box(extents=(30.0, 20.0, 4.0))
    arm.apply_translation((44.0, 0.0, 36.0))
    with_arm = trimesh.boolean.union([tunnel_block().raw, arm])
    block = trimesh.creation.box(extents=(30.0, 30.0, 10.0))
    block.apply_translation((0.0, 0.0, 5.0))
    objects = [
        replace(scene_object("obj_1", "Tunnel"), mesh=MeshData.of(with_arm)),
        replace(scene_object("obj_2", "Klotz"), mesh=MeshData.of(block)),
    ]
    settings = print_settings.resolve(profile, "standard")
    settings = print_settings.with_accepted(settings, "support.style", "auto")
    settings = print_settings.with_accepted(settings, "support.block_channels", True)

    written, findings = write_assembly(
        objects, tmp_path, project_name="t", profile=profile, settings=settings, flavour=flavour
    )

    blocked = [
        finding.object_id for finding in findings if finding.code == "export.support_blocker"
    ]
    assert blocked == ["obj_1"]
    said = [
        finding.values["setting"] for finding in findings if finding.code == "export.part_setting"
    ]
    assert said == ["support.style"], "die Sperre nennt sich selbst"
    if flavour == "orca":
        assert _orca_parts(written) == [("2", "normal_part"), ("2", "support_blocker")]
    else:
        meshes = [(mesh.path.name, dict(mesh.settings)) for mesh in handover.cura_meshes(written)]
        assert meshes == [
            ("t-part-1.stl", {"support_enable": "true"}),
            ("t-blocker-1.stl", {"anti_overhang_mesh": "true"}),
            ("t-part-2.stl", {"support_enable": "false"}),
        ]


@pytest.mark.parametrize("flavour", ["orca", "prusa", "cura"])
def test_the_ledge_blocker_travels_alone_in_every_family(
    tmp_path: Path, profile: Profile, flavour: SlicerFlavour
) -> None:
    """„Ränder ohne Stütze“ allein, ohne Kanalsperre, reist als dieselbe Stützsperre
    wie die Kanäle — Teil der Orca-Familie, Bereich bei PrusaSlicer, eigenes Netz
    bei Cura — und nennt sich in einem eigenen Befund (RM-582). Den Weg hielt bis
    zur Durchsicht vom 08.10.2026 kein Test: Ohne den Schalter im Tor blieb die
    Suite grün."""
    entry = replace(scene_object("obj_1", "Flansch"), mesh=_flange_with_arm())
    settings = print_settings.resolve(profile, "standard")
    settings = print_settings.with_accepted(settings, "support.style", "auto")
    settings = print_settings.with_accepted(settings, "support.spare_ledges", True)

    written, findings = write_assembly(
        [entry], tmp_path, project_name="t", profile=profile, settings=settings, flavour=flavour
    )

    codes = [finding.code for finding in findings]
    assert "export.ledge_blocker" in codes
    assert "export.support_blocker" not in codes, "ohne Kanalsperre kein Kanalbefund"
    said = [
        finding.values["setting"] for finding in findings if finding.code == "export.part_setting"
    ]
    assert "support.spare_ledges" not in said, "die Sperre nennt sich selbst"
    if flavour == "orca":
        assert _orca_parts(written) == [("2", "normal_part"), ("2", "support_blocker")]
    elif flavour == "prusa":
        assert [kind for kind, _first, _last in _blocker_ranges(written)] == [
            "ModelPart",
            "SupportBlocker",
        ]
    else:
        meshes = [(mesh.path.name, dict(mesh.settings)) for mesh in handover.cura_meshes(written)]
        assert ("t-blocker-1.stl", {"anti_overhang_mesh": "true"}) in meshes


def _flange_with_arm() -> MeshData:
    """Eine Säule 30 auf 30 mm mit einem Flansch von 2,5 mm auf 20 mm Höhe, ein
    Rand, und knapp darüber einem Arm von 15 mm, der Stütze braucht."""
    column = trimesh.creation.box(extents=(30.0, 30.0, 40.0))
    column.apply_translation((0.0, 0.0, 20.0))
    flange = trimesh.creation.box(extents=(35.0, 35.0, 1.0))
    flange.apply_translation((0.0, 0.0, 20.5))
    arm = trimesh.creation.box(extents=(15.0, 10.0, 2.0))
    arm.apply_translation((22.5, 0.0, 21.4))
    return MeshData.of(trimesh.boolean.union([column, flange, arm]))


def test_the_ledge_finding_counts_a_ledge_only_at_the_height_of_its_slab(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zwei gleiche Flansche übereinander: Spart die Sperre den oberen aus, deckt
    ihn die Scheibe des unteren in der Aufsicht trotzdem. Gezählt wird ein Rand
    nur von einer Scheibe seiner Höhe (zweites Review vom 08.10.2026). Als
    Attrappe fehlt die Scheibe des oberen Flansches, wie bei einem Arm daneben."""
    import math

    from app.core.slice import analysis

    column = trimesh.creation.box(extents=(30.0, 30.0, 40.0))
    column.apply_translation((0.0, 0.0, 20.0))
    flanges = []
    for height in (20.5, 30.5):
        flange = trimesh.creation.box(extents=(35.0, 35.0, 1.0))
        flange.apply_translation((0.0, 0.0, height))
        flanges.append(flange)
    body = MeshData.of(trimesh.boolean.union([column, *flanges]))
    entry = replace(scene_object("obj_1", "Flansche"), mesh=body)
    settings = print_settings.with_path(print_settings.resolve(profile), "support.style", "auto")
    settings = print_settings.with_path(settings, "support.spare_ledges", True)
    result = writer._body_analysis(entry, body, settings, profile, None, detail="support")
    real = analysis.ledges(result)
    lower = [
        slab for slab in analysis.ledge_space(result, settings.layers.line_width) if slab[1] < 25.0
    ]
    below = {(index, number) for index, number in real if result.layers[index].z < 25.0}
    assert lower and below and real - below, "beide Flansche sind Ränder"
    monkeypatch.setattr(analysis, "ledge_space", lambda *_args: lower)

    _blocker, found = writer._support_blocker(entry, body, settings, profile, result=result)

    [said] = [finding for finding in found if finding.code == "export.ledge_blocker"]
    area = math.fsum(analysis.piece_area(result.layers[i].overhangs[n]) for i, n in below)
    assert said.values["area_mm2"] == pytest.approx(round(area, 1)), "nur der untere Flansch"


def test_a_part_that_spares_its_ledges_keeps_its_own_support_count(profile: Profile) -> None:
    """Zwei Teile auf einer Platte, nur das zweite mit „Ränder ohne Stütze“: Ihr
    Stützvertrag ist nicht gleich, und die Gegenprobe rechnet nicht mit den Werten
    des ersten (``same_support``, zweites Review vom 08.10.2026). Sonst wüsste sie
    nichts von der Sperre und erwartete Stütze, die der Slicer nicht druckt."""
    import dataclasses

    from app.core.slice.estimate import plate_comparison

    plain = print_settings.resolve(profile)
    supported = dataclasses.replace(
        plain, support=dataclasses.replace(plain.support, style="normal")
    )
    sparing = dataclasses.replace(
        supported, support=dataclasses.replace(supported.support, spare_ledges=True)
    )
    cube = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    cube.apply_translation((-40.0, 0.0, 5.0))
    flanged = apply(_flange_with_arm(), translation((20.0, 0.0, 0.0)))
    parts = [
        (scene_object("obj_1", "Würfel"), MeshData.of(cube), supported),
        (scene_object("obj_2", "Flansch"), flanged, sparing),
    ]

    compared = plate_comparison(0, parts, profile, keep_arrangement=True, separate_objects=False)

    assert compared.ledges_blocked, "die Sperre des zweiten Teils zählt"
    assert compared.support_material_mm3 is None


def test_the_ledge_finding_names_only_the_spared_ledges(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Randbefund nennt Ort und Fläche der Ränder, die die Sperre deckt — wie
    der Kanalbefund nur die gesperrten Decken. Einen Rand neben einem Überhang,
    der Stütze braucht, spart die Sperre aus; mit allen Rändern wären Ort und
    Fläche falsch (Review vom 08.10.2026). Als Attrappe zählt hier der Arm zu den
    Rändern, die Sperrscheiben bleiben die echten, und die sparen ihn aus."""
    import math

    import shapely

    from app.core.slice import analysis

    body = _flange_with_arm()
    entry = replace(scene_object("obj_1", "Flansch"), mesh=body)
    settings = print_settings.with_path(print_settings.resolve(profile), "support.style", "auto")
    settings = print_settings.with_path(settings, "support.spare_ledges", True)
    result = writer._body_analysis(entry, body, settings, profile, None, detail="support")
    real = analysis.ledges(result)
    slabs = analysis.ledge_space(result, settings.layers.line_width)
    arm = {
        (index, number)
        for index, layer in enumerate(result.layers)
        for number, piece in enumerate(layer.overhangs)
        if shapely.Polygon(piece.outline, piece.holes).representative_point().x > 18.0
    }
    assert real and slabs, "der Flansch ist ein Rand und wird gesperrt"
    assert arm and not arm & real, "der Arm braucht Stütze"
    monkeypatch.setattr(analysis, "ledges", lambda *_args, **_kwargs: real | arm)
    monkeypatch.setattr(analysis, "ledge_space", lambda *_args: slabs)

    _blocker, found = writer._support_blocker(entry, body, settings, profile, result=result)

    [said] = [finding for finding in found if finding.code == "export.ledge_blocker"]
    flange = math.fsum(analysis.piece_area(result.layers[i].overhangs[n]) for i, n in real)
    assert said.values["area_mm2"] == pytest.approx(round(flange, 1)), "nur der Flansch"
    assert said.location is not None and said.location[0] < 18.0, "der Ort liegt am Flansch"


def test_the_blocker_finding_names_only_the_blocked_ceilings(profile: Profile) -> None:
    """Der Sperrbefund nennt Ort und Fläche der gesperrten Decken. Nicht jede
    Kanaldecke bekommt eine Sperre (``worth_support``), und mit Ort und Fläche
    aller Kanaldecken zeigte er am Drachen bei 130 % auf eine Decke ohne Sperre,
    die Fläche fast fünfmal zu groß (Review vom 08.10.2026). Hier ein Schlitz mit
    Satteldach und Sperre — seine Decke zerfällt in Streifen von 16 bis 32 mm² —
    neben vier kurzen Schlitzen ohne, deren flache Decken je ein Stück von
    80 mm² sind: Das größte Kanalstück liegt ohne Sperre (Review 3)."""
    import math

    import numpy as np

    from app.core.slice.analysis import model_support, piece_area

    def block(length: float, centres: list[float], x: float) -> trimesh.Trimesh:
        body = trimesh.creation.box(extents=(10.0 * len(centres) + 20.0, length, 20.0))
        body.apply_translation((x, 0.0, 10.0))
        for centre in centres:
            cut = trimesh.creation.box(extents=(5.0, length + 10.0, 6.0))
            cut.apply_translation((x + centre, 0.0, 7.0))
            body = trimesh.boolean.difference([body, cut])
        return body

    def gabled(length: float, x: float) -> trimesh.Trimesh:
        body = trimesh.creation.box(extents=(28.0, length, 20.0))
        body.apply_translation((x, 0.0, 10.0))
        rise = 4.0 * math.tan(math.radians(18.0))
        cut = trimesh.convex.convex_hull(
            [
                (x + offset, y, z)
                for y in (-length / 2.0 - 5.0, length / 2.0 + 5.0)
                for offset, z in (
                    (-4.0, 4.0),
                    (4.0, 4.0),
                    (-4.0, 10.0),
                    (4.0, 10.0),
                    (0.0, 10.0 + rise),
                )
            ]
        )
        return trimesh.boolean.difference([body, cut])

    long_slot = gabled(60.0, -40.0)
    short_slots = block(16.0, [-15.0, -5.0, 5.0, 15.0], 40.0)
    mesh = MeshData.of(trimesh.util.concatenate([long_slot, short_slots]))
    entry = scene_object(mesh=mesh)
    settings = print_settings.with_path(print_settings.resolve(profile), "support.style", "grid")
    settings = print_settings.with_path(settings, "support.block_channels", True)

    blocker, found = writer._support_blocker(entry, as_mesh_data(entry.mesh), settings, profile)

    assert blocker is not None
    model = model_support(
        writer._body_analysis(entry, mesh, settings, profile, None, detail="support")
    )
    blocked = math.fsum(piece_area(outline) for outline, _low, _high in model.channel_columns)
    assert model.channel_area > blocked + 50.0, "die kurzen Schlitze sind Kanal ohne Sperre"
    assert model.channel_at is not None and model.channel_at[0] > 0.0, (
        "das größte Kanalstück liegt in einem kurzen Schlitz"
    )
    (finding,) = found
    assert finding.values["area_mm2"] == pytest.approx(blocked, abs=0.1)
    assert finding.location is not None
    assert np.isclose(finding.location[0], -40.0, atol=3.0), "der Ort liegt im langen Schlitz"


def test_the_simplified_blocker_still_covers_the_whole_channel(profile: Profile) -> None:
    """Die Kanalscheiben werden vor dem Sperrkörper um
    ``writer.BLOCKER_SIMPLIFY`` vereinfacht — am Eiffelturm aus dem Korpus
    404 464 statt 177 454 Dreiecke, 12,6 statt 1,4 s. Ebenso weit schiebt der
    Schreiber den Umriss danach hinaus; vom Kanalraum darf deshalb nichts
    außerhalb der Sperre liegen."""
    import manifold3d
    import numpy as np

    from app.core.export import writer
    from app.core.knowledge import profiles as profile_table
    from app.core.slice.analysis import channel_space, model_support, slice_body

    # Eine geschlossene runde Kammer Ø 20: Am Kreis ändert Vereinfachen den
    # Umriss, an einem quer liegenden Tunnel nicht — dessen Scheiben sind
    # Rechtecke, und dort wäre jede Toleranz grün (gegengeprüft mit 3 mm).
    block = trimesh.creation.box(extents=(40.0, 40.0, 40.0))
    block.apply_translation((0.0, 0.0, 20.0))
    chamber = trimesh.creation.cylinder(radius=10.0, height=20.0, sections=96)
    chamber.apply_translation((0.0, 0.0, 18.0))
    entry = scene_object(mesh=MeshData.of(trimesh.boolean.difference([block, chamber])))
    mesh = as_mesh_data(entry.mesh)
    settings = print_settings.with_path(print_settings.resolve(profile), "support.style", "grid")
    settings = print_settings.with_path(settings, "support.block_channels", True)
    blocker, _found = writer._support_blocker(entry, mesh, settings, profile)
    assert blocker is not None

    wall, angle = profile_table.analysis_limits(profile, entry)
    result = slice_body(
        mesh,
        settings.layers.layer_height,
        first_layer_height=settings.layers.first_layer_height,
        overhang_angle=angle,
        bridge_from=wall,
        detail="support",
        support_volume=False,
    )
    exact = []
    for bottom, top, region in channel_space(
        result, model_support(result), settings.layers.line_width
    ):
        rings = [
            ring
            for part in getattr(region, "geoms", [region])
            for ring in (
                np.asarray(part.exterior.coords)[:-1],
                *(np.asarray(hole.coords)[:-1] for hole in part.interiors),
            )
        ]
        section = manifold3d.CrossSection(rings, manifold3d.FillRule.EvenOdd)
        exact.append(manifold3d.Manifold.extrude(section, top - bottom).translate((0, 0, bottom)))
    free = manifold3d.Manifold.batch_boolean(exact, manifold3d.OpType.Add)
    raw = blocker.raw
    shield = manifold3d.Manifold(
        manifold3d.Mesh(
            vert_properties=np.asarray(raw.vertices, dtype=np.float32),
            tri_verts=np.asarray(raw.faces, dtype=np.uint32),
        )
    )

    assert free.volume() > 0.0
    assert (free - shield).volume() < 1e-6 * free.volume(), "nichts vom Kanal liegt außerhalb"


def test_the_blocker_takes_the_reports_layers(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """DRUCK-14: Hat der Prüfbericht das Netz geschnitten, schneidet die Sperre nicht.

    Seine Überhänge und Inseln sind dieselben wie bei ``detail="support"``;
    also ist auch die Sperre dieselbe. Am Eiffelturm aus dem Korpus kostete
    der zweite Schnitt vor dem Start des Slicers den größten Teil von 17 s.
    """
    from app.core.export import writer
    from app.core.knowledge import profiles as profile_table
    from app.core.slice import analysis
    from app.core.slice.findings import analysed

    block = trimesh.creation.box(extents=(40.0, 40.0, 40.0))
    block.apply_translation((0.0, 0.0, 20.0))
    tunnel = trimesh.creation.box(extents=(12.0, 50.0, 14.0))
    tunnel.apply_translation((0.0, 0.0, 16.0))
    entry = scene_object(mesh=MeshData.of(trimesh.boolean.difference([block, tunnel])))
    mesh = as_mesh_data(entry.mesh)
    settings = print_settings.with_path(print_settings.resolve(profile), "support.style", "grid")
    settings = print_settings.with_path(settings, "support.block_channels", True)
    fresh, _found = writer._support_blocker(entry, MeshData.of(mesh.raw.copy()), settings, profile)
    assert fresh is not None

    wall, angle = profile_table.analysis_limits(profile, entry)
    analysed(mesh, settings, angle, wall)

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("die Schichten des Prüfberichts genügen")

    monkeypatch.setattr(analysis, "slice_body", refuse)
    reused, _found = writer._support_blocker(entry, mesh, settings, profile)

    assert reused is not None
    assert reused.raw.volume == pytest.approx(fresh.raw.volume, rel=1e-9)
    assert reused.triangle_count == fresh.triangle_count


def test_the_blocker_cuts_with_the_threshold_that_goes_out(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Entscheidung L: Die Sperre schneidet mit der Stützschwelle der
    Einstellungen, die hinausgehen — auf einem Herstellerprozess dessen
    Schwelle, nicht die des Druckers in Solidons Tabelle (am Centauri 60°).
    Sonst sperrte sie nach einer Grenze, nach der der Slicer nicht stützt."""
    from app.core.export import writer
    from app.core.slice import analysis

    class SeenError(Exception):
        pass

    angles: list[float] = []

    def capture(*_args: object, **kwargs: float) -> None:
        angles.append(kwargs["overhang_angle"])
        raise SeenError

    block = trimesh.creation.box(extents=(30.0, 30.0, 30.0))
    block.apply_translation((0.0, 0.0, 15.0))
    entry = scene_object(mesh=MeshData.of(block))
    settings = print_settings.with_path(print_settings.resolve(profile), "support.style", "grid")
    printed = print_settings.with_path(settings, "support.threshold_angle", 41.0)
    monkeypatch.setattr(analysis, "slice_body", capture)

    with pytest.raises(SeenError):
        writer._support_blocker(entry, as_mesh_data(entry.mesh), printed, profile)

    assert profile.overhang_limit_degrees == pytest.approx(60.0)
    assert angles == [pytest.approx(41.0)]


def test_the_blocker_stops_when_the_customer_cancels(tmp_path: Path, profile: Profile) -> None:
    """Die Sperre rechnet am Eiffelturm aus dem Korpus eine Viertelminute —
    Schnitt, Kanalfrage, Kanalraum — vor dem Start des Slicers. *Abbrechen*
    griff erst danach: ``write_assembly`` kannte keinen Abbruch. Jetzt erreicht
    er den Schnitt, und es entsteht keine Datei."""
    from app.core.errors import OperationCancelled

    class Stopped:
        is_cancelled = True

        def raise_if_cancelled(self) -> None:
            raise OperationCancelled

    entry = scene_object(mesh=tunnel_block())
    taken = print_settings.with_path(
        print_settings.with_path(print_settings.resolve(profile), "support.style", "grid"),
        "support.block_channels",
        True,
    )

    with pytest.raises(OperationCancelled):
        write_assembly(
            [entry],
            tmp_path,
            project_name="t",
            profile=profile,
            settings=taken,
            cancelled=Stopped(),
        )
    assert not list(tmp_path.glob("*.3mf")), "keine halbe Übergabe"


def test_a_saved_file_carries_no_blocker(tmp_path: Path, profile: Profile) -> None:
    """Eine gespeicherte 3MF ist das Projekt des Kunden und keine Übergabe:
    Sie trägt keine Sperre, die ein anderes Programm als Material lesen
    könnte."""
    entry = scene_object(mesh=tunnel_block())
    taken = print_settings.with_path(
        print_settings.with_path(print_settings.resolve(profile), "support.style", "grid"),
        "support.block_channels",
        True,
    )

    saved, _saved_findings = write_assembly(
        [entry],
        tmp_path / "datei",
        project_name="t",
        profile=profile,
        settings=taken,
        for_slicer=False,
    )
    assert [kind for kind, _first, _last in _blocker_ranges(saved)] == ["ModelPart"]


def test_cura_gets_every_part_and_the_blocker_as_meshes_of_their_own(
    tmp_path: Path, profile: Profile
) -> None:
    """Die Stützsperre reist zu CuraEngine als eigenes Netz (Prüfbericht Cura, B10).

    Bis zum 27.09.2026 bekam Cura alle Teile als ein STL, und die Sperre fiel
    weg — am Minigolf-Körper im Prüfbericht gemessen: mit der Sperre als
    eigenem Netz und ``anti_overhang_mesh`` 18 476 Stützbewegungen weniger,
    die Modellbahn gleich. Curas Fenster bekommt dieselben Netze als 3MF
    (:func:`test_curas_window_gets_the_blocker_and_the_values_of_each_part`),
    der Befund ist deshalb derselbe wie bei jedem Slicer.
    """
    entry = scene_object(mesh=tunnel_block())
    second = scene_object("obj_2", "Zweites")
    second = replace(second, mesh=apply(second.mesh, translation((60.0, 0.0, 0.0))))
    taken = print_settings.with_path(
        print_settings.with_path(print_settings.resolve(profile), "support.style", "grid"),
        "support.block_channels",
        True,
    )

    stl, findings = write_assembly(
        [entry, second], tmp_path, project_name="t", profile=profile, settings=taken, flavour="cura"
    )

    assert stl.suffix == ".stl", "das Fenster bekommt weiter ein STL mit allen Teilen"
    meshes = handover.cura_meshes(stl)
    assert [mesh.path.name for mesh in meshes] == [
        "t-part-1.stl",
        "t-blocker-1.stl",
        "t-part-2.stl",
    ]
    assert [dict(mesh.settings) for mesh in meshes] == [{}, {"anti_overhang_mesh": "true"}, {}]
    part = read_mesh(meshes[0].path.read_bytes(), ".stl")
    assert part.volume == pytest.approx(as_mesh_data(entry.mesh).raw.volume, rel=1e-6)
    blocker = read_mesh(meshes[1].path.read_bytes(), ".stl")
    assert blocker.volume > 0.0
    [said] = [finding for finding in findings if finding.code == "export.support_blocker"]
    assert "Cura-Fenster" not in str(said.message), "das Fenster bekommt die Sperre selbst"


def _ledge_tunnel() -> MeshData:
    """Der Tunnelblock mit einem Kragarm oben, 30 mm frei: Er braucht Stützen,
    und die Tunneldecke trägt sich selbst — Stützen an und Kanal gesperrt."""
    ledge = trimesh.creation.box(extents=(30.0, 40.0, 3.0))
    ledge.apply_translation((44.0, 0.0, 38.5))
    return MeshData.of(trimesh.boolean.union([tunnel_block().raw, ledge]))


def test_curas_window_gets_the_blocker_and_the_values_of_each_part(
    tmp_path: Path, profile: Profile
) -> None:
    """Curas Fenster bekommt, was die Kommandozeile bekommt (RM-257): je Teil
    ein Objekt mit seinen Werten, die Sperre als Netz mit ``anti_overhang_mesh``
    — als 3MF in Curas Schreibweise statt des zusammengelegten STL, das weder
    Sperre noch Werte je Teil trug.

    Die Sperre steht als Komponente neben ihrem Körper in einem Objekt: Cura
    setzt ein freistehendes Objekt aufs Bett, ein Kind einer Gruppe wandert
    mit ihr. Verschoben um den halben Bauraum, denn Cura misst eine 3MF von
    der Bettecke und ordnet sie beim Laden nicht an.
    """
    taken = print_settings.with_accepted(
        print_settings.with_accepted(print_settings.resolve(profile), "support.style", "grid"),
        "support.block_channels",
        True,
    )
    objects = [
        scene_object("obj_1", "Tunnel", mesh=_ledge_tunnel()),
        replace(
            scene_object("obj_2", "Klotz"),
            mesh=apply(scene_object().mesh, translation((70.0, 0.0, 0.0))),
        ),
    ]

    console, _console_findings = write_assembly(
        objects,
        tmp_path / "konsole",
        project_name="t",
        profile=profile,
        settings=taken,
        flavour="cura",
    )
    window, findings = write_assembly(
        objects,
        tmp_path / "fenster",
        project_name="t",
        profile=profile,
        settings=taken,
        flavour="cura",
        for_window=True,
    )

    assert window.suffix == ".3mf"
    archive = zipfile.ZipFile(window)
    assert sorted(archive.namelist()) == ["3D/3dmodel.model", "[Content_Types].xml", "_rels/.rels"]
    model = ET.fromstring(archive.read("3D/3dmodel.model"))
    core = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
    objects_by_id = {node.get("id"): node for node in model.iter(f"{core}object")}

    def values(node: ET.Element) -> dict[str, str]:
        return {
            meta.get("name", ""): meta.text or ""
            for meta in node.iter(f"{core}metadata")
            if meta.get("name", "").startswith("cura:")
        }

    items = list(model.iter(f"{core}item"))
    width, depth, _height = profile.printer.build_volume
    assert {item.get("transform") for item in items} == {
        f"1 0 0 0 1 0 0 0 1 {width / 2:g} {depth / 2:g} 0"
    }
    tunnel, block = (objects_by_id[item.get("objectid")] for item in items)
    body, shield = (
        objects_by_id[component.get("objectid")] for component in tunnel.iter(f"{core}component")
    )
    assert values(body) == {"cura:support_enable": "True"}
    assert values(shield) == {"cura:anti_overhang_mesh": "True"}
    assert values(block) == {"cura:support_enable": "False"}
    assert [dict(mesh.settings) for mesh in handover.cura_meshes(console)] == [
        {"support_enable": "true"},
        {"anti_overhang_mesh": "true"},
        {"support_enable": "false"},
    ], "dieselben Werte wie in der Kommandozeile, dort in ihrer Schreibweise"
    assert "export.support_blocker" in {finding.code for finding in findings}


def test_curas_window_centres_the_job_on_the_bed_cura_has_active(
    tmp_path: Path, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Curas Leser zieht beim Öffnen die halbe Bettgröße *seiner* aktiven
    Maschine ab (``ThreeMFReader._read``, Cura 5.13) und ordnet nicht an.

    Auf das Bett des Druckers in Solidon gerechnet, lag ein Auftrag an einer
    anderen Maschine um die halbe Differenz aus der Mitte: am Ender-3 V3 SE
    (220 mm) mit dem Centauri Carbon 2 (256 mm) um 18 mm nach hinten rechts
    (B5, Durchsicht 0.5.1) — ein Auftrag, der auf Curas Bett passte, konnte so
    über dessen Rand ragen.
    """
    from app.core.export import slicer_profiles

    monkeypatch.setattr(
        slicer_profiles,
        "cura_active_machine",
        lambda _executable: slicer_profiles.CuraActiveMachine(
            name="Ender-3 V3 SE",
            definition=Path("creality_ender3v3se.def.json"),
            bed=(220.0, 200.0),
        ),
    )
    assert profile.printer.build_volume[:2] != (220.0, 200.0), "sonst prüft der Test nichts"

    window, _findings = write_assembly(
        [scene_object("obj_1", "Klotz")],
        tmp_path,
        project_name="t",
        profile=profile,
        settings=print_settings.resolve(profile),
        flavour="cura",
        setup=handover.SlicerSetup(executable=Path("CuraEngine.exe"), flavour="cura"),
        for_window=True,
    )

    model = ET.fromstring(zipfile.ZipFile(window).read("3D/3dmodel.model"))
    core = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
    assert [item.get("transform") for item in model.iter(f"{core}item")] == [
        "1 0 0 0 1 0 0 0 1 110 100 0"
    ]


def test_cura_window_names_both_printers_and_keeps_solidon_settings(
    tmp_path: Path, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.export import slicer_profiles

    active = slicer_profiles.CuraActiveMachine(
        name="Ender-3 V3 SE",
        definition=Path("creality_ender3v3se.def.json"),
        bed=(220.0, 200.0),
    )
    actual_active_machine = slicer_profiles.cura_active_machine
    monkeypatch.setattr(slicer_profiles, "cura_active_machine", lambda _executable: active)
    monkeypatch.setattr(slicer_profiles, "chosen_printer", lambda *_args, **_kwargs: "")
    settings = print_settings.resolve(profile)
    settings = replace(
        settings,
        temperature=replace(settings.temperature, nozzle=223),
        speed=replace(settings.speed, outer_wall=37.5),
    )
    settings = print_settings.with_choice(settings, "temperature.nozzle", 223)
    settings = print_settings.with_choice(settings, "speed.outer_wall", 37.5)

    window, findings = write_assembly(
        [scene_object("obj_1", "Klotz")],
        tmp_path,
        project_name="t",
        profile=profile,
        settings=settings,
        flavour="cura",
        setup=handover.SlicerSetup(executable=Path("CuraEngine.exe"), flavour="cura"),
        for_window=True,
    )

    [finding] = [entry for entry in findings if entry.code == "slicer.machine_mismatch"]
    message = str(finding.message)
    assert "Ender-3 V3 SE" in message
    assert str(profile.printer.title) in message
    assert (
        "Temperaturen und Druckgeschwindigkeiten stammen weiter aus Solidons Druckerprofil."
        in message
    )
    assert "open_print_settings" in {action.id for action in finding.suggestions}
    with zipfile.ZipFile(window) as archive:
        model = ET.fromstring(archive.read(threemf.MODEL_PATH))
    core = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
    assert {item.get("transform") for item in model.iter(f"{core}item")} == {
        "1 0 0 0 1 0 0 0 1 110 100 0"
    }

    engine = _cura_install(tmp_path)
    _cura_active(tmp_path, monkeypatch)
    monkeypatch.setattr(slicer_profiles, "cura_active_machine", actual_active_machine)
    setup = handover.SlicerSetup(executable=engine, flavour="cura")
    handover.cura_profile_beside(window, settings, profile, setup)
    values = _cura_containers(window.with_suffix(".curaprofile"))["solidon"]["values"]
    assert values["material_print_temperature"] == str(settings.temperature.nozzle)
    assert values["speed_wall_0"] == str(settings.speed.outer_wall)


def test_cura_window_without_print_settings_still_reports_the_active_printer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.export import slicer_profiles

    engine = _cura_install(tmp_path)
    _cura_active(tmp_path, monkeypatch)
    monkeypatch.setattr(
        slicer_profiles,
        "cura_active_machine",
        lambda _executable: slicer_profiles.CuraActiveMachine(
            name="K1 Max in der Werkstatt",
            definition=Path("creality_k1max.def.json"),
            bed=(300.0, 300.0),
        ),
    )
    monkeypatch.setattr(slicer_profiles, "chosen_printer", lambda *_args, **_kwargs: "")

    window, findings = write_assembly(
        [scene_object("obj_1", "Klotz")],
        tmp_path,
        project_name="t",
        profile=profiles.make_profile("centauri-carbon-2", "pla"),
        settings=None,
        flavour="cura",
        setup=handover.SlicerSetup(executable=engine, flavour="cura"),
        for_window=True,
    )

    assert window.is_file()
    [finding] = [entry for entry in findings if entry.code == "slicer.machine_mismatch"]
    message = str(finding.message)
    assert "K1 Max in der Werkstatt" in message
    assert "Druckwerte werden nicht mitgegeben" in message
    assert (
        "Temperaturen und Druckgeschwindigkeiten stammen weiter aus Solidons Druckerprofil."
        not in message
    )
    assert "slicer.cura_printer_unknown" not in {entry.code for entry in findings}


@pytest.mark.parametrize(
    ("solidon_printer", "cura_bed_width", "warns"),
    [
        ("creality-k1-max", None, False),
        ("centauri-carbon-2", None, True),
        ("creality-k1-max", 350.0, True),
    ],
    ids=["gleicher-drucker", "anderer-drucker", "gleiche-definition-anderes-bett"],
)
def test_cura_names_the_active_printer_only_when_it_is_a_different_one(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    solidon_printer: str,
    cura_bed_width: float | None,
    warns: bool,
) -> None:
    """RM-417: Curas aktive Instanz „Creality K1 Max“ auf ``creality_k1max`` und
    Solidons eingebauter K1 Max sind derselbe Drucker. Die Warnung kam trotzdem
    bei jedem *Im Slicer öffnen*, weil ``chosen_printer`` eine nicht
    übernommene Instanz keinem Solidon-Drucker zuordnet."""
    engine = _cura_install(tmp_path)
    definitions = engine.parent / "share" / "cura" / "resources" / "definitions"
    (definitions / "creality_k1max.def.json").write_text(
        json.dumps(
            {
                "version": 2,
                "name": "Creality K1 Max",
                "inherits": "fdmprinter",
                "metadata": {"visible": True},
                "overrides": {
                    "machine_width": {"default_value": 300},
                    "machine_depth": {"default_value": 300},
                    "machine_height": {"default_value": 300},
                },
            }
        ),
        encoding="utf-8",
    )
    _cura_active(tmp_path, monkeypatch, name="Creality K1 Max", definition="creality_k1max")
    if cura_bed_width is not None:
        changes = tmp_path / "config" / "cura" / "5.13" / "definition_changes"
        changes.mkdir()
        (changes / "Creality+K1+Max_settings.inst.cfg").write_text(
            f"[general]\nversion = 4\n\n[values]\nmachine_width = {cura_bed_width}\n",
            encoding="utf-8",
        )
        stack = changes.parent / "machine_instances/Creality+K1+Max.global.cfg"
        stack.write_text(
            stack.read_text(encoding="utf-8").replace(
                "6 = empty_definition_changes", "6 = Creality K1 Max_settings"
            ),
            encoding="utf-8",
        )
    profile = profiles.make_profile(solidon_printer, "pla")
    setup = handover.SlicerSetup(engine, "cura")

    finding = handover.cura_active_printer_mismatch(setup, profile)

    assert (finding is not None) is warns
    if finding is not None:
        assert finding.values["cura_printer"] == "Creality K1 Max"
        assert finding.values["solidon_printer"] == profile.printer.title


def test_cura_gets_parts_without_a_blocker_when_none_is_taken(
    tmp_path: Path, profile: Profile
) -> None:
    """Ohne übernommene Sperre: je Teil ein Netz, keines mit Werten."""
    stl, findings = write_assembly(
        [scene_object(mesh=tunnel_block())],
        tmp_path,
        project_name="t",
        profile=profile,
        settings=print_settings.resolve(profile),
        flavour="cura",
    )

    assert [(mesh.path.name, dict(mesh.settings)) for mesh in handover.cura_meshes(stl)] == [
        ("t-part-1.stl", {})
    ]
    assert "export.support_blocker" not in {finding.code for finding in findings}
