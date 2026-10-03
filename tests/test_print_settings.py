"""Druckeinstellungen, Empfehlung und Slicer-Übergabe (Bauplan §29, §28).

Drei Sachen, die zusammengehören: Solidon hält die Einstellungen, die
Geometrie ändert sie, und der Slicer bekommt sie in seiner eigenen Sprache
geschrieben. Getestet wird ohne installierten Slicer — was einen Fremdprozess
braucht, steht ausdrücklich dabei.
"""

from __future__ import annotations

import json
import re
import subprocess
import zipfile
from dataclasses import fields, replace
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Final, Literal, get_args, get_origin, get_type_hints
from xml.etree import ElementTree as ET

import pytest
import trimesh

from app.core import activation
from app.core.build_area import size_excess
from app.core.errors import AppError, ExternalToolError, OutOfBuildVolume, ValidationError
from app.core.export import handover, slicer_keys, slicer_profiles, threemf
from app.core.geom.mesh import MeshData
from app.core.knowledge import print_settings, profiles
from app.core.scene.project import PROJECT_ENTRY, load, new_project, save
from app.core.slice import advise, gcode
from app.core.types import (
    BoundingBox,
    LayerInfo,
    MaterialSlot,
    Polygon,
    Profile,
    SettingAdvice,
    SliceResult,
)

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.mark.parametrize("phase", ("before", "after_success", "after_refusal"))
def test_cancel_around_preflight_packing(monkeypatch: pytest.MonkeyPatch, phase: str) -> None:
    from app.core.errors import OperationCancelled
    from app.core.export import writer
    from app.core.geom import prepare
    from app.core.scene.cancel import CancelSignal

    profile = profiles.make_profile("prusa-mini", "pla")
    setup = handover.SlicerSetup(Path("prusa-slicer-console.exe"), "prusa")
    token = CancelSignal()
    called: list[bool] = []

    def arrangement(_meshes: Any, _profile: Any) -> bool:
        if phase == "before":
            token.cancel()
        return False

    def pack(_meshes: Any, _profile: Any) -> Any:
        called.append(True)
        token.cancel()
        findings = (
            [SimpleNamespace(code="arrange.needs_more_plates")] if phase == "after_refusal" else []
        )
        return SimpleNamespace(findings=findings)

    monkeypatch.setattr(writer, "arrangement_holds", arrangement)
    monkeypatch.setattr(prepare, "arrange_on_bed", pack)
    meshes = [_preflight_box((100.0, 100.0, 10.0)) for _index in range(2)]
    with pytest.raises(OperationCancelled):
        handover._check_plate(meshes, profile, setup, token)
    assert called == ([] if phase == "before" else [True])


def _old_spool_dialog_state():
    """Drei alte Profilplätze, davon zwei benutzt; echte Methoden ohne Fenster."""
    from app.core.export import threemf
    from app.core.types import Scene
    from app.ui.print_settings_dialog import PrintSettingsDialog

    red = MaterialSlot(0, "Rot", (1.0, 0.0, 0.0), material_type="PLA")
    blue = MaterialSlot(1, "Blau", (0.0, 0.0, 1.0), material_type="PLA")
    green = MaterialSlot(0, "Grün", (0.0, 1.0, 0.0), material_type="PLA")
    first = _standing_box("Blau", (10.0, 10.0, 10.0))
    first = replace(
        first,
        mesh=replace(first.mesh, slots=(1,) * first.mesh.triangle_count),
        material_slots=(red, blue),
        plate=0,
    )
    second = replace(_standing_box("Grün", (10.0, 10.0, 10.0)), material_slots=(green,), plate=1)
    scene = Scene(objects={first.id: first, second.id: second})
    project = new_project()
    settings = replace(
        print_settings.resolve(profiles.make_profile()),
        slot_profiles=("Rotes Altprofil", "Blaues Profil", "Grünes Profil"),
        slot_profile_bindings=None,
        inventory_project_id="old-spools",
    )
    project.document.print_settings = settings
    host = SimpleNamespace(
        settings=settings,
        session=SimpleNamespace(
            project=project,
            profile=profiles.make_profile(),
            last_result=SimpleNamespace(scene=scene, stopped_at=None),
            picture=None,
        ),
        _opened_with=settings,
        _handover_project_id="old-spools",
        _all_plates=lambda: (0, 1),
        _chosen_plates=lambda: (0, 1),
    )
    host._plate_slots = lambda **kwargs: PrintSettingsDialog._plate_slots(host, **kwargs)
    host._profiles_for = lambda slots: PrintSettingsDialog._profiles_for(host, slots)
    return host, (first, second), tuple(threemf.slot_identity(slot) for slot in (red, blue, green))


def test_old_spool_dialog_reads_profiles_before_active_slots_are_renumbered():
    """Auch nur Platte zwei bekommt ihr altes Profil, ohne die Einstellung zu ändern."""
    host, _objects, _keys = _old_spool_dialog_state()
    original = host.settings
    host._chosen_plates = lambda: (1,)
    shown = host._plate_slots()
    assert host._profiles_for(shown) == ("Grünes Profil",)
    host._chosen_plates = lambda: (0,)
    shown = host._plate_slots()
    assert host._profiles_for(shown) == ("Blaues Profil",)
    assert host.settings is original and original.slot_profile_bindings is None


def test_old_spool_choice_preserves_other_legacy_profile_bindings():
    """Eine neue blaue Profilwahl verschiebt keine fremde alte Bindung."""
    from app.ui.print_settings_dialog import PrintSettingsDialog

    host, _objects, (red, blue, green) = _old_spool_dialog_state()
    shown = host._plate_slots()
    position = next(index for index, slot in enumerate(shown) if str(slot.name) == "Blau")
    box = SimpleNamespace(currentData=lambda: "Neues blaues Profil")
    host.slot_rows = [(None, box)] * len(shown)
    host._profile_name = lambda value: value
    host._slot_names = [str(slot.name) for slot in shown]
    host._check_print_result = lambda: None
    host._refresh_advice = lambda: None
    host.state = SimpleNamespace(setText=lambda text: None)
    original = host.settings
    PrintSettingsDialog._slot_filament_chosen(host, position)
    chosen = {binding.key: binding.profile_name for binding in host.settings.slot_profile_bindings}
    assert chosen == {red: "Rotes Altprofil", blue: "Neues blaues Profil", green: "Grünes Profil"}
    assert original.slot_profile_bindings is None


def test_old_spool_choice_survives_save_reopen_delete_and_undo(tmp_path: Path):
    """Gebundene Wahlen schlagen die parallele Positionsliste auch nach dem Rundlauf."""
    from app.core.export import threemf
    from app.core.scene import History, OperationDraft, evaluate
    from app.ui.print_settings_dialog import PrintSettingsDialog

    host, _objects, (_red, blue, green) = _old_spool_dialog_state()
    project = host.session.project
    history = History(project.document)
    for name, colour in (("Blau", "#0000ff"), ("Grün", "#00ff00")):
        history.apply("Körper", [OperationDraft("create_box", params={"name": name})])
        identifier = project.document.ops[-1].outputs[0]
        history.apply(
            "Filament",
            [
                OperationDraft(
                    "assign_slot",
                    (identifier,),
                    {"slot": 0, "name": name, "colour": colour, "material_type": "PLA"},
                )
            ],
        )
    # Der letzte alte Szenenstand trägt noch die rote Deklaration. Beim
    # erneuten Auswerten bleiben nur die tatsächlich zugewiesenen Filamente.
    shown = host._plate_slots()
    position = next(index for index, slot in enumerate(shown) if str(slot.name) == "Blau")
    host.slot_rows = [(None, SimpleNamespace(currentData=lambda: "Neues blaues Profil"))] * len(
        shown
    )
    host._profile_name = lambda value: value
    host._slot_names = [str(slot.name) for slot in shown]
    host._check_print_result = host._refresh_advice = lambda: None
    host.state = SimpleNamespace(setText=lambda text: None)
    PrintSettingsDialog._slot_filament_chosen(host, position)
    project.document.print_settings = host.settings
    opened = load(save(project, tmp_path / "alte-spulen.p3d"))
    stored = opened.document.print_settings
    assert stored == host.settings
    result = evaluate(opened.document, host.session.profile)
    assert result.complete
    objects = tuple(result.scene.objects.values())
    assert handover.chosen_slot_profiles(objects, stored) == {
        blue: "Neues blaues Profil",
        green: "Grünes Profil",
    }
    history = History(opened.document)
    history.apply("Löschen", [OperationDraft("delete_object", (objects[0].id,))])
    remaining = tuple(evaluate(opened.document, host.session.profile).scene.objects.values())
    assert len(remaining) == 1
    slots = threemf.merge_slots(
        [threemf.AssemblyPart(remaining[0].mesh, slots=remaining[0].material_slots)]
    )
    assert slots[0].index == 0
    assert handover.chosen_slot_profiles(remaining, stored) == {green: "Grünes Profil"}
    assert stored.slot_profiles[0] == "Neues blaues Profil", (
        "die alte Position ist nicht maßgeblich"
    )
    reopened = load(save(opened, tmp_path / "after-delete.p3d"))
    assert handover.chosen_slot_profiles(
        tuple(evaluate(reopened.document, host.session.profile).scene.objects.values()),
        reopened.document.print_settings,
    ) == {green: "Grünes Profil"}
    assert history.undo()
    assert handover.chosen_slot_profiles(
        tuple(evaluate(opened.document, host.session.profile).scene.objects.values()), stored
    ) == {blue: "Neues blaues Profil", green: "Grünes Profil"}


@pytest.mark.parametrize("plates", [(0,), (1,), (0, 1)])
def test_old_spool_job_binds_before_local_profile_numbers(tmp_path: Path, plates):
    """Der normale Auftrag trägt die alte Identität vor jeder lokalen Werkzeugnummer."""
    from app.ui.print_settings_dialog import PrintSettingsDialog, _slots_with_profiles

    host, objects, (red, blue, green) = _old_spool_dialog_state()
    host._chosen_plates = lambda: plates
    setup = handover.SlicerSetup(tmp_path / "elegoo-slicer.exe", "orca")
    job = PrintSettingsDialog._plate_job(host, objects, plates, tmp_path, "Altspulen", setup)
    assert job.settings.slot_profile_bindings is not None
    assert {
        binding.key: binding.profile_name for binding in job.settings.slot_profile_bindings
    } == {red: "Rotes Altprofil", blue: "Blaues Profil", green: "Grünes Profil"}
    for entry, expected in zip(objects, ("Blaues Profil", "Grünes Profil"), strict=True):
        if entry.plate not in plates:
            continue
        slots, chosen = _slots_with_profiles(job, [entry])
        assert len(slots) == 1 and slots[0].index == 0
        assert chosen == (expected,)
    assert host.settings.slot_profile_bindings is None
    assert host.session.project.document.print_settings.slot_profile_bindings is None


def test_old_spool_session_binds_the_complete_previous_scene():
    """Vor einer neuen Szene werden auch unbemalte alte Plätze identitätsfest gebunden."""
    from app.ui.session import Session

    host, _objects, (red, blue, green) = _old_spool_dialog_state()
    original = host.settings
    Session._bind_filament_profiles(host.session)
    bound = host.session.project.document.print_settings
    assert {binding.key: binding.profile_name for binding in bound.slot_profile_bindings} == {
        red: "Rotes Altprofil",
        blue: "Blaues Profil",
        green: "Grünes Profil",
    }
    assert original.slot_profile_bindings is None
    Session._bind_filament_profiles(host.session)
    assert host.session.project.document.print_settings is bound


@pytest.mark.parametrize("way", ["console", "window", "export"])
@pytest.mark.parametrize("plates", [(0,), (1,), (0, 1)])
def test_old_spool_profiles_reach_the_written_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, way, plates
):
    """Alle drei Schreibwege behalten gewählte Profile und passende Werkzeugnummern."""
    from app.core.export import threemf, writer
    from app.ui.print_settings_dialog import PrintSettingsDialog, _prepare_plate, _prepare_plates

    host, objects, _keys = _old_spool_dialog_state()
    host._chosen_plates = lambda: plates
    available = []
    for name, temperature in (
        ("Rotes Altprofil", "260"),
        ("Blaues Profil", "210"),
        ("Grünes Profil", "235"),
    ):
        path = tmp_path / f"{name}.json"
        path.write_text(
            json.dumps({"name": name, "nozzle_temperature": [temperature]}), encoding="utf-8"
        )
        available.append(slicer_profiles.SlicerProfile(path=path, name=name, kind="filament"))
    monkeypatch.setattr(slicer_profiles, "find_profiles", lambda *_args, **_kwargs: available)
    setup = handover.SlicerSetup(tmp_path / "orca.exe", "orca")
    job = PrintSettingsDialog._plate_job(host, objects, plates, tmp_path, "Altspulen", setup)
    outputs = []
    if way == "console":
        for plate in plates:
            run = _prepare_plate(job, plate)
            assert run.used_tools == (0,)
            outputs.append((run.model, (plate,)))
    elif way == "window":
        outputs.append((_prepare_plates(replace(job, for_window=True)).model, plates))
    else:
        written, _findings = writer.write_assembly(
            list(objects),
            tmp_path,
            project_name="Altspulen",
            profile=host.session.profile,
            plate=plates[0] if len(plates) == 1 else None,
            settings=host.settings,
            setup=setup,
            flavour="orca",
        )
        outputs.append((written, plates))
    for written, included in outputs:
        with zipfile.ZipFile(written) as archive:
            embedded = json.loads(archive.read(threemf.PROJECT_SETTINGS_PATH))
            model = ET.fromstring(archive.read(threemf.MODEL_PATH))
        names = ["Solidon Blau", "Solidon Grün"]
        temperatures = ["210", "235"]
        if way == "export" and included == (1,):
            # Der globale Platz 0 gehört zur tatsächlich benutzten blauen Spule
            # der anderen Platte; nur dieser notwendige Platzhalter bleibt.
            assert embedded["filament_settings_id"][1] == names[1]
            assert embedded["nozzle_temperature"][1] == temperatures[1]
            expected_tools = {"1"}
        else:
            assert embedded["filament_settings_id"] == [names[p] for p in included]
            assert embedded["nozzle_temperature"] == [temperatures[p] for p in included]
            expected_tools = {str(index) for index in range(len(included))}
        assert {
            node.get("p1") for node in model.iter() if node.tag.endswith("}triangle")
        } == expected_tools
    assert host.settings.slot_profile_bindings is None


def test_a_replaced_support_suggestion_explains_the_support_actually_offered() -> None:
    advice = SettingAdvice("support.style", "tree", "normal", "Baumstützen sparen Material.")
    shown = slicer_keys.offered([advice], "superslicer")
    assert len(shown) == 1
    assert shown[0].value == "grid"
    assert shown[0].reason == slicer_keys.substitute("support.style", "tree", "superslicer").reason
    assert slicer_keys.offered([replace(advice, was="grid")], "superslicer") == []
    assert slicer_keys.offered([advice], "prusaslicer") == [advice]


@pytest.mark.parametrize(
    "program,flavour",
    [
        ("prusaslicer", "prusa"),
        ("superslicer", "prusa"),
        ("orcaslicer", "orca"),
        ("elegooslicer", "orca"),
        ("bambustudio", "orca"),
        ("crealityprint", "orca"),
        ("cura", "cura"),
    ],
)
def test_every_written_choice_belongs_to_the_measured_program(program, flavour) -> None:
    """RM-480/RM-461: Jede Aufzählungszeile gegen einen unabhängig erhobenen
    Bestand. Neue Aufzählungen ohne Messung machen den Wächter ebenfalls rot."""
    measured = json.loads((MESHES.parent / "slicer_values.json").read_text(encoding="utf-8"))
    known = measured["programs"][program]["values"]
    base = print_settings.resolve(profiles.make_profile("generic-220", "pla"))
    checked = 0
    for entry in slicer_keys.TABLES[flavour]:
        group, name = entry.path.split(".")
        hint = get_type_hints(type(getattr(base, group)))[name]
        choices = (
            (False, True) if hint is bool else get_args(hint) if get_origin(hint) is Literal else ()
        )
        for choice in choices:
            settings = print_settings.with_choice(base, entry.path, choice)
            written = handover.as_mapping(settings, flavour, program=program)
            written = slicer_keys.for_program(written, flavour, program)
            keys = slicer_keys.PROGRAM_ALIASES.get(program, {}).get(entry.key, (entry.key,))
            for key in keys:
                if key not in written:
                    continue
                value = written.get(key, "")
                if key in known:
                    assert value in known[key], (program, entry.path, choice, value)
                    checked += 1
                    continue
                if not value or value in {"true", "false"}:
                    continue
                try:
                    float(value)
                except ValueError:
                    assert key in known, (program, entry.path, key)
    assert checked >= 10, "Der Wächter muss echte Aufzählungswerte prüfen."


def _layers(
    *areas: float, overhang: float = 0.0, islands: bool = False, min_width: float = 5.0
) -> SliceResult:
    """Ein Schnittergebnis mit vorgegebenen Flächen — für die Vorschläge reicht
    das, sie lesen nur Kennzahlen."""
    square = ((0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0))
    layers = tuple(
        LayerInfo(
            z=float(index) * 0.2,
            contours=(Polygon(outline=square),),
            area=area,
            overhang_area=overhang,
            islands=(square,) if islands and index > 0 else (),
            min_width=min_width,
        )
        for index, area in enumerate(areas)
    )
    return SliceResult(
        layers=layers,
        support_volume=overhang * 0.2 * len(areas),
        first_layer_area=areas[0] if areas else 0.0,
        source="internal",
    )


def _elegoo_nozzle_profile(root: Path, nozzle: float) -> slicer_profiles.SlicerProfile:
    """Eine installierte Elegoo-Maschine mit Herstellerbeleg aus ihrem Pfad."""
    name = f"Elegoo Centauri Carbon 2 {nozzle:.1f} nozzle"
    filename = "Centauri.json" if nozzle == 0.4 else "Centauri02.json"
    path = root / "resources" / "profiles" / "Elegoo" / "machine" / "ECC2" / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "type": "machine",
                "name": name,
                "instantiation": "true",
                "printer_model": "Elegoo Centauri Carbon 2",
                "nozzle_diameter": [f"{nozzle:g}"],
                "printable_area": ["0x0", "256x0", "256x256", "0x256"],
                "printable_height": "256",
                "machine_start_gcode": f"G28 ; Elegoo {nozzle:.1f} nozzle",
            }
        ),
        encoding="utf-8",
    )
    profile = slicer_profiles._read(path, "machine", False)
    assert profile is not None
    return profile


# --- die drei Ebenen (§29) ----------------------------------------------------------


def test_the_stage_names_speak_the_language_of_the_window() -> None:
    """Regel 20: Die Stufennamen kamen als Titel aus ``print_settings.toml``,
    ohne ``_()``, und standen in der englischen Oberfläche als „Fein“ und
    „Belastbar“ da (Fund der Release-Sitzung, 27.09.2026). Mit ihnen der Name,
    unter dem der Slicer den Prozess zeigt."""
    from app.i18n import catalog, set_language

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    catalog.install_language("en")
    set_language("en")

    assert list(print_settings.quality_presets().values()) == [
        "Draft",
        "Standard",
        "Fine",
        "Strong",
    ]
    assert print_settings.resolve(profile, "fine").title == "Fine · PLA"


def test_the_quality_preset_decides_the_layer_height() -> None:
    profile = profiles.make_profile("prusa-mk4s", "pla")
    draft = print_settings.resolve(profile, "draft")
    fine = print_settings.resolve(profile, "fine")

    assert draft.layers.layer_height > fine.layers.layer_height
    assert fine.shell.top_layers > draft.shell.top_layers


def test_the_material_decides_the_temperature() -> None:
    printer = "prusa-mk4s"
    pla = print_settings.resolve(profiles.make_profile(printer, "pla"))
    petg = print_settings.resolve(profiles.make_profile(printer, "petg"))

    assert petg.temperature.nozzle > pla.temperature.nozzle
    assert petg.cooling.fan_speed < pla.cooling.fan_speed
    # Die Stufe ist dieselbe — die Schichthöhe darf sich am Material nicht
    # ändern, sonst wäre die Aufteilung der Ebenen sinnlos.
    assert petg.layers.layer_height == pla.layers.layer_height


def test_a_wider_nozzle_lays_thicker_layers() -> None:
    profile = profiles.make_profile("prusa-mk4s", "pla")
    wide = replace(profile, printer=replace(profile.printer, nozzle_diameter=0.6))

    narrow = print_settings.resolve(profile)
    thick = print_settings.resolve(wide)

    assert thick.layers.layer_height > narrow.layers.layer_height
    assert thick.layers.layer_height <= 0.6 * print_settings.MAX_LAYER_RATIO


def test_the_printer_caps_what_the_material_asks_for() -> None:
    """Ein Profil, das heißer will, als die Maschine kann, ist ein stiller
    Schaden — hier wird er laut."""
    profile = profiles.make_profile("anycubic-kobra-2", "asa")
    settings = print_settings.resolve(profile)

    assert settings.temperature.nozzle <= profile.printer.nozzle_temperature_max


def test_an_open_printer_gets_no_chamber_temperature() -> None:
    open_printer = print_settings.resolve(profiles.make_profile("prusa-mk4s", "abs"))
    closed = print_settings.resolve(profiles.make_profile("bambu-x1c", "abs"))

    assert open_printer.temperature.chamber == 0
    assert closed.temperature.chamber > 0


# --- Das Tempo gehört dem Drucker ------------------------------------------------


def test_the_printers_own_pace_is_the_standard_stage() -> None:
    """Der Centauri Carbon 2 fährt im Standardprozess seines Herstellers die
    Außenwand mit 160, Innenwand, Füllung und Deckel mit 200 mm/s und
    beschleunigt mit 10 000 mm/s² (Elegoo-Profil in OrcaSlicer, eingetragen in
    ``printers.toml``). Die allgemeine Stufe fährt 40 — die Waschschüssel ging
    so mit einem Viertel des Tempos hinaus, das der Drucker kann."""
    speed = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "pla")).speed

    assert (speed.outer_wall, speed.inner_wall, speed.infill, speed.top_surface) == (
        160.0,
        200.0,
        200.0,
        200.0,
    )
    assert (speed.first_layer, speed.bridge) == (50.0, 50.0)
    assert (speed.acceleration, speed.outer_wall_acceleration) == (10000.0, 5000.0)


def test_the_other_stages_keep_their_ratio_to_the_printers_pace() -> None:
    """„Fein" fährt bei Solidon die Außenwand ein Viertel langsamer als
    „Standard" — am Centauri dann 120 statt 160. Ein Drucker ohne eigenes
    Tempo behält die Zahlen der Stufe."""
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    fine = print_settings._quality_table("fine")
    standard = print_settings._quality_table("standard")

    speed = print_settings.resolve(profile, "fine").speed

    assert speed.outer_wall == pytest.approx(
        160.0 * fine["speed_outer_wall"] / standard["speed_outer_wall"]
    )
    assert speed.acceleration == pytest.approx(
        10000.0 * fine["acceleration"] / standard["acceleration"]
    )
    plain = print_settings.resolve(profiles.make_profile("generic-220", "pla"), "fine").speed
    assert plain.outer_wall == fine["speed_outer_wall"]
    assert plain.acceleration == fine["acceleration"]


def test_the_printers_hotend_raises_the_flow_of_the_material() -> None:
    """Der Materialwert gilt einem üblichen Hotend. Elegoos allgemeines PLA
    fördert am Centauri 21 mm³/s, Solidons PLA 12 — ``flow_factor`` 1,75."""
    pla = print_settings._material_table("pla")["max_flow"]

    fast = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "pla"))
    plain = print_settings.resolve(profiles.make_profile("generic-220", "pla"))

    assert fast.filament.max_flow == pytest.approx(pla * 1.75)
    assert plain.filament.max_flow == pytest.approx(pla)


@pytest.mark.parametrize("material_id", ["tpu-95a", "abs", "petg", "pa-cf-eigenbau"])
def test_the_hotend_factor_leaves_other_materials_alone(material_id: str) -> None:
    """Der Faktor ist am PLA des Herstellers gemessen. TPU bekam mit ihm am
    Centauri 6,1 mm³/s und fuhr 72 statt 41 mm/s; Elegoos allgemeines ABS und
    PETG-CF fördern dort 12, nicht 19,25 und 15,75. Ein eigenes Material ohne
    Tabelle bekommt ihn ebenso wenig — es könnte ein Elastikfilament sein."""
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    plain = print_settings.resolve(
        replace(profile, material=replace(profile.material, id=material_id))
    )

    expected = print_settings._material_table(material_id).get("max_flow", 12.0)
    assert plain.filament.max_flow == pytest.approx(expected)


@pytest.mark.parametrize("printer_id", sorted(profiles.printer_profiles()))
def test_no_stage_asks_for_more_than_the_filament_flows(printer_id: str) -> None:
    """Die Herstellertempi gelten dem schnellsten Filament des Herstellers.
    Der Bambu A1 fährt Innenwände mit 300 mm/s, das sind 25 mm³/s gegen 12 für
    allgemeines PLA; der Slicer bremst dann selbst. Die Auflösung bremst
    genauso — sonst stünden an jedem Teil vier Warnungen, ohne dass jemand
    etwas eingestellt hätte."""
    printer = profiles.printer(printer_id)
    if printer.is_resin:
        pytest.skip("ein Resin-Drucker fördert nicht")
    materials = [
        identifier
        for identifier, material in profiles.material_profiles().items()
        if material.technology == printer.technology
    ]
    assert materials
    for material_id in materials:
        profile = profiles.make_profile(printer_id, material_id)
        for quality in print_settings.quality_presets():
            settings = print_settings.resolve(profile, quality)  # type: ignore[arg-type]
            for name, first in print_settings.FLOW_BOUND_SPEEDS:
                flow = advise.flow_of(settings, getattr(settings.speed, name), first_layer=first)
                assert flow <= settings.filament.max_flow + 1e-9, (material_id, quality, name)
            assert advise._from_flow(settings) == [], (material_id, quality)


def test_the_flow_cap_is_the_highest_whole_speed_below_the_limit() -> None:
    """A1 mit PLA: 12 mm³/s durch 0,2 auf 0,42 mm sind 142,9 mm/s —
    abgerundet 142, damit der Wert die Grenze einhält, um die es geht."""
    settings = print_settings.resolve(profiles.make_profile("bambu-a1", "pla"))
    area = settings.layers.layer_height * settings.layers.line_width

    assert settings.speed.inner_wall == float(int(settings.filament.max_flow / area))
    assert settings.speed.first_layer == 50.0, "die erste Schicht liegt darunter"


@pytest.mark.parametrize(
    "printer_id",
    sorted(
        identifier
        for identifier, printer in profiles.printer_profiles().items()
        if not printer.is_resin and not identifier.startswith("generic-")
    ),
)
def test_every_named_printer_carries_its_makers_pace(printer_id: str) -> None:
    """Jeder benannte Drucker hat einen Standardprozess beim Hersteller, und
    „Standard" soll ihn fahren. Dem Ender-3 V3 fehlte er (Orca: „0.20mm Standard
    @Creality Ender-3 V3", 200/300/500 mm/s, Leerfahrt 500): Er druckte mit
    Solidons allgemeinen 40 mm/s, obwohl der Changelog das Gegenteil sagt."""
    printer = profiles.printer(printer_id)

    assert printer.travel_speed is not None
    assert printer.speed_outer_wall is not None


@pytest.mark.parametrize("printer_id", sorted(profiles.printer_profiles()))
def test_the_outer_wall_never_accelerates_harder_than_the_rest(printer_id: str) -> None:
    """Die Außenwand fährt sanfter als der Rest, bei jedem Hersteller. Stand nur
    die allgemeine Beschleunigung in der Tabelle, kam die der Außenwand aus der
    Stufe — am Kobra 2 5000 gegen 2500 mm/s² (Orca: 700), am MINI stand dazu
    10 000 statt der 1000 aus Prusas Profil."""
    printer = profiles.printer(printer_id)
    if printer.is_resin:
        pytest.skip("ein Resin-Drucker fährt keine Bahnen")
    speed = print_settings.resolve(profiles.make_profile(printer_id, "pla")).speed

    assert speed.outer_wall_acceleration <= speed.acceleration


def test_the_mini_accelerates_like_prusas_profile() -> None:
    """Prusas Standardprozess für den MINI mit Input Shaper, den PrusaSlicer
    2.9.6 vorwählt („0.20mm SPEED @MINIIS 0.4"): 2000 mm/s², die Außenwand
    ebenso. Bis zum 27.09.2026 standen hier die 1000 und 700 des abgelösten
    Prozesses ohne Input Shaper, und mit ihnen Außenwände von 40 statt 140 mm/s."""
    speed = print_settings.resolve(profiles.make_profile("prusa-mini", "pla")).speed

    assert (speed.acceleration, speed.outer_wall_acceleration) == (2000.0, 2000.0)
    assert speed.outer_wall == pytest.approx(140.0)


@pytest.mark.parametrize("field", ["speed_outer_wall", "acceleration", "flow_factor"])
def test_a_pace_that_does_not_move_is_refused(field: str) -> None:
    table = {"title": "Probe", "build_volume": [200.0, 200.0, 200.0], field: 0}

    with pytest.raises(ValidationError):
        profiles._printer_from_table("probe", table, Path("printers.toml"))


def test_an_unknown_material_still_yields_settings() -> None:
    """Ein eigenes Filament soll sich benutzen lassen, bevor jemand eine
    Tabelle dafür pflegt."""
    profile = profiles.make_profile("prusa-mk4s", "pla")
    strange = replace(profile, material=replace(profile.material, id="pa-cf-eigenbau"))

    settings = print_settings.resolve(strange)

    assert settings.temperature.nozzle > 0


def test_an_unknown_quality_is_refused_by_name() -> None:
    with pytest.raises(ValidationError):
        print_settings.resolve(profiles.make_profile(), "hochglanz")  # type: ignore[arg-type]


# --- Pfadzugriff --------------------------------------------------------------------


def test_a_value_can_be_read_and_set_through_its_path() -> None:
    settings = print_settings.resolve(profiles.make_profile())

    changed = print_settings.with_path(settings, "support.style", "tree")

    assert print_settings.read_path(changed, "support.style") == "tree"
    # Unveränderlich: der Vorschlag darf das Original nicht anfassen, sonst
    # ließe er sich nicht mehr verwerfen.
    assert settings.support.style == "none"


@pytest.mark.parametrize("path", ["", "support", "erfunden.wert", "support.gibtesnicht"])
def test_a_path_that_points_nowhere_is_refused(path: str) -> None:
    settings = print_settings.resolve(profiles.make_profile())
    with pytest.raises(ValidationError):
        print_settings.read_path(settings, path)


# --- Vorschläge aus der Geometrie (§29) ---------------------------------------------


def _paths(entries: list) -> set[str]:
    return {entry.path for entry in entries}


def test_islands_ask_for_supports() -> None:
    settings = print_settings.resolve(profiles.make_profile())
    result = _layers(500.0, 500.0, 500.0, islands=True)

    entries = advise.advise(settings, profiles.make_profile(), result)

    assert "support.style" in _paths(entries)
    chosen = next(entry for entry in entries if entry.path == "support.style")
    assert chosen.value != "none"
    assert chosen.reason, "ein Vorschlag ohne Grund ist keiner"


def test_a_part_that_floats_nowhere_gets_its_supports_taken_away() -> None:
    settings = print_settings.with_path(
        print_settings.resolve(profiles.make_profile()), "support.style", "grid"
    )
    result = _layers(500.0, 500.0, 500.0)

    entries = advise.advise(settings, profiles.make_profile(), result)

    chosen = next(entry for entry in entries if entry.path == "support.style")
    assert chosen.value == "none"


def test_a_wall_thinner_than_two_lines_asks_for_a_narrower_line() -> None:
    """Die Wandstärkenprüfung sitzt hier und nicht in jeder Operation (E1).

    Konzept P15 hatte sie für ``push_face`` vorgesehen — eine Wand, die der
    Zug unter das Materialminimum bringt, soll das sagen. Sie steht schon, und
    zwar besser: sie misst am **ganzen** Körper statt nur an der gezogenen
    Fläche, sie läuft dort, wo die Schichtanalyse ohnehin rechnet, und sie
    nennt die Linienbreite, mit der die Stelle doch entsteht.

    Sie in eine Operation zu kopieren hieße, je Zug eine Schichtanalyse zu
    fahren — Sekunden für eine Zahl, die der Bericht danach ohnehin nennt.

    Dieser Test hält die Zusage fest; ohne ihn stand die Prüfung ungeprüft im
    Code.
    """
    settings = print_settings.resolve(profiles.make_profile())
    two_lines = 2.0 * settings.layers.line_width
    # Knapp unter zwei Linien, aber über der doppelten schmalsten Bahn der Düse:
    # dort hilft eine schmalere Linie noch. Darunter ist es der Befund
    # ``settings.wall_below_nozzle`` (Durchsicht Schichtanalyse, 02.09.2026).
    result = _layers(500.0, 500.0, 500.0, min_width=two_lines * 0.95)

    entries = advise.advise(settings, profiles.make_profile(), result)

    chosen = next(entry for entry in entries if entry.path == "layers.line_width")
    assert chosen.value < settings.layers.line_width, "eine schmalere Linie erreicht die Stelle"
    assert chosen.severity == "warning"
    assert chosen.reason, "ein Vorschlag ohne Grund ist keiner"


def test_a_wall_wide_enough_says_nothing() -> None:
    """Eine Wand, die passt, bekommt keinen Vorschlag — sonst stünde an jedem
    Teil einer."""
    settings = print_settings.resolve(profiles.make_profile())
    result = _layers(500.0, 500.0, 500.0, min_width=5.0)

    entries = advise.advise(settings, profiles.make_profile(), result)

    assert "layers.line_width" not in _paths(entries)


def test_a_small_footprint_asks_for_a_brim() -> None:
    settings = print_settings.resolve(profiles.make_profile())
    result = _layers(80.0, 80.0, 80.0)

    entries = advise.advise(settings, profiles.make_profile(), result)

    brim = [entry for entry in entries if entry.path == "adhesion.kind"]
    assert brim and brim[0].value == "brim"


def _standing_on(*feet: float) -> SliceResult:
    """Ein Körper, dessen erste Schicht aus getrennten Quadraten der
    genannten Flächen besteht — darüber eine geschlossene Schicht."""
    contours = tuple(
        Polygon(
            outline=(
                (100.0 * index, 0.0),
                (100.0 * index + area**0.5, 0.0),
                (100.0 * index + area**0.5, area**0.5),
                (100.0 * index, area**0.5),
            )
        )
        for index, area in enumerate(feet)
    )
    first = LayerInfo(
        z=0.1,
        contours=contours,
        area=sum(feet),
        overhang_area=0.0,
        islands=(),
        min_width=5.0,
    )
    above = replace(
        first,
        z=0.3,
        contours=(Polygon(outline=((0.0, 0.0), (900.0, 0.0), (900.0, 50.0), (0.0, 50.0))),),
    )
    return SliceResult(
        layers=(first, above), support_volume=0.0, first_layer_area=sum(feet), source="internal"
    )


def test_a_part_on_many_small_feet_asks_for_a_brim() -> None:
    """Die Waschschüssel steht in Drucklage auf zwölf Füßen, zehn davon zu je
    108 mm², zusammen 1417 mm² (gemessen am Schnitt 0,1 mm über dem Bett).
    Die Summe liegt über :data:`advise.SMALL_FOOTPRINT`, und doch hält keiner
    der Füße für sich — Nutzer des Designerprofils melden, dass sich die
    hintere Ecke hebt."""
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.resolve(profile)
    bowl = _standing_on(242.8, 198.6, 2.8, *[108.1] * 9)
    assert bowl.first_layer_area > advise.SMALL_FOOTPRINT

    entries = advise.advise(settings, profile, bowl)

    brim = [entry for entry in entries if entry.path == "adhesion.kind"]
    assert [entry.value for entry in brim] == ["brim"]
    assert "Füßen" in str(brim[0].reason)


def test_one_foot_that_holds_on_its_own_needs_no_brim() -> None:
    """Steht einer der Füße auf genug Fläche für ein Teil, trägt er den Rest
    — und ein einzelner großer Fuß ist schlicht eine Standfläche."""
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.resolve(profile)

    for result in (
        _standing_on(advise.SMALL_FOOTPRINT + 1.0, 108.1, 108.1),
        _standing_on(1417.3),
    ):
        entries = advise.advise(settings, profile, result)
        assert "adhesion.kind" not in _paths(entries)


def test_a_tall_slim_part_asks_for_a_brim() -> None:
    settings = print_settings.resolve(profiles.make_profile())
    result = _layers(*[600.0] * 6)
    bounds = BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(20.0, 20.0, 200.0))

    entries = advise.advise(settings, profiles.make_profile(), result, bounds=bounds)

    assert "adhesion.kind" in _paths(entries)


@pytest.mark.parametrize(
    ("flavour", "kind", "asks"),
    [("orca", "auto", False), ("prusa", "none", True), ("cura", "auto", True)],
)
def test_the_orca_auto_brim_already_holds_a_part(flavour: str, kind: str, asks: bool) -> None:
    """Orcas Auto-Brim rechnet aus Höhe, Grundfläche und Tempo selbst und hielt
    mehr als Solidons Brim fester Breite: 1,9 statt 0,9 m Randbahn an den
    200 mm hohen Schäften der Minigolf-Platte, 0,93 statt 0,40 m an der
    Waschschüssel (ElegooSlicer, 27.09.2026). Über ihm schweigen die drei
    Brim-Regeln — kleine Standfläche, kleine Füße, hoch und schmal. Cura hat
    keinen; dort heißt „automatisch“ die Art aus der Tabelle, und die Regeln
    bleiben. PrusaSlicer auch nicht, und seine Grundlage liest an Prusas
    eigenen Druckern „keine“ (``_prusa_adhesion``), die ebenso wenig hält."""
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.with_path(print_settings.resolve(profile), "adhesion.kind", kind)
    slim = BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(20.0, 20.0, 200.0))
    cases = (
        advise.advise(settings, profile, _layers(80.0, 80.0, 80.0), flavour=flavour),
        advise.advise(
            settings, profile, _standing_on(242.8, 198.6, 2.8, *[108.1] * 9), flavour=flavour
        ),
        advise.advise(settings, profile, _layers(*[600.0] * 6), bounds=slim, flavour=flavour),
        advise.for_part(settings, slim, 400.0, flavour=flavour),
        advise.for_part(
            settings,
            BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(40.0, 40.0, 20.0)),
            60.0,
            flavour=flavour,
        ),
    )

    assert [("adhesion.kind" in _paths(entries)) for entries in cases] == [asks] * len(cases)


CALM_WALLS: Final = {
    "speed.outer_wall": advise.SLENDER_WALL_SPEED,
    "speed.inner_wall": advise.SLENDER_WALL_SPEED,
    "speed.outer_wall_acceleration": advise.CAREFUL_ACCELERATION,
    "speed.acceleration": advise.CAREFUL_ACCELERATION,
}


@pytest.mark.parametrize("flavour", ["orca", "prusa", "cura"])
def test_a_slender_part_on_a_small_foot_is_slowed_down_even_under_an_auto_brim(
    flavour: slicer_keys.SlicerFlavour,
) -> None:
    """Roberts Fahnenstangen (29.09.2026): Ø 7,7 × 122 mm auf 46,5 mm². Elegoos
    Auto-Brim lag fest, die Stangen rissen bei 200 mm/s und 5000 bis
    10 000 mm/s² samt erster Schicht aus ihm heraus. Der Brim hält den Fuß,
    nicht die Stange — also werden Wände und Beschleunigung gebremst, bei
    jedem Slicer und über dem Auto-Brim ebenso. Dieselben Pfade gehen je Teil
    (``PART_PATHS``), damit nur die Stange langsamer wird."""
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.with_path(print_settings.resolve(profile), "adhesion.kind", "auto")
    pole = BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(9.7, 9.7, 122.0))
    result = _layers(46.5, 46.5, 46.5)

    for entries in (
        advise.advise(settings, profile, result, bounds=pole, flavour=flavour),
        advise.for_part(settings, pole, 46.5, profile=profile, result=result, flavour=flavour),
    ):
        chosen = {entry.path: entry for entry in entries if entry.path in CALM_WALLS}
        assert {path: entry.value for path, entry in chosen.items()} == CALM_WALLS
        assert all(entry.severity == "warning" and entry.reason for entry in chosen.values())
    assert set(CALM_WALLS) <= advise.PART_PATHS


def test_a_slender_part_on_a_broad_foot_keeps_its_pace() -> None:
    """Die Schäfte derselben Minigolf-Platte (Ø 25,7 × 200 mm, 518 mm²) liefen
    am 27.09.2026 mit vollem Tempo sauber: schlank, aber mit genug Fuß. Sie
    zu bremsen kostete Stunden und brächte nichts; ebenso wenig die Stange,
    wenn die Einstellungen schon ruhig sind."""
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.resolve(profile)
    shaft = BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(25.7, 25.7, 200.0))
    calm = settings
    for path, value in CALM_WALLS.items():
        calm = print_settings.with_path(calm, path, value)
    pole = BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(9.7, 9.7, 122.0))

    cases = (
        advise.advise(settings, profile, _layers(518.0, 518.0), bounds=shaft, flavour="orca"),
        advise.advise(calm, profile, _layers(46.5, 46.5), bounds=pole, flavour="orca"),
    )

    assert [_paths(entries) & set(CALM_WALLS) for entries in cases] == [set(), set()]


def test_the_core_without_a_family_keeps_automatic_adhesion_conservative() -> None:
    """Die ungebundene Kernabfrage bleibt vorsichtig; sie beschreibt nicht
    den Druckdialog ohne Programmauswahl. Ein Skirt hält auch unter Orca nichts."""
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    table = print_settings.resolve(profile)
    automatic = print_settings.with_path(table, "adhesion.kind", "auto")
    skirt = print_settings.with_path(table, "adhesion.kind", "skirt")
    slim = BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(20.0, 20.0, 200.0))

    assert "adhesion.kind" in _paths(advise.for_part(automatic, slim, 400.0))
    assert "adhesion.kind" in _paths(advise.for_part(skirt, slim, 400.0, flavour="orca"))


def test_warping_material_on_an_open_printer_is_a_finding_not_a_change() -> None:
    """Die Materialtabelle setzt für ABS schon Brim und wenig Lüfter — es gibt
    nichts zu ändern. Gesagt werden muss es trotzdem."""
    profile = profiles.make_profile("prusa-mk4s", "abs")
    settings = print_settings.resolve(profile)

    assert settings.adhesion.kind == "brim"
    assert not [
        entry for entry in advise.advise(settings, profile) if entry.path == "adhesion.kind"
    ]

    findings = advise.warnings_for(settings, profile)
    codes = {finding.code for finding in findings}
    assert "settings.warping_material_open_printer" in codes
    assert all(finding.source == "internal" for finding in findings)


def test_the_same_material_in_a_closed_chamber_is_no_warning() -> None:
    profile = profiles.make_profile("bambu-x1c", "abs")
    settings = print_settings.resolve(profile)

    codes = {finding.code for finding in advise.warnings_for(settings, profile)}
    assert "settings.warping_material_open_printer" not in codes


def test_a_ceiling_spanning_free_air_is_reported() -> None:
    """Der Fall, der einen Satz Gewürzbehälter gekostet hat (§22.2).

    Eine waagerechte Ringschulter im Becher: der Slicer überspannte sie mit
    geraden Bahnen quer über die Öffnung, 27 mm frei. Keine Einstellung behebt
    das — also ein Befund, kein Vorschlag, und er nennt die Höhe, damit man
    hinsehen kann.
    """
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    spanning = _layers(100.0, 100.0, 100.0)
    spanning = SliceResult(
        layers=tuple(
            replace(layer, bridge_width=26.8 if index == 2 else 0.0)
            for index, layer in enumerate(spanning.layers)
        ),
        support_volume=spanning.support_volume,
        first_layer_area=spanning.first_layer_area,
    )

    findings = advise.warnings_for(settings, profile, spanning)
    spans = [finding for finding in findings if finding.code == "slice.long_bridge"]

    assert spans, "27 mm free air has to be said out loud"
    assert spans[0].values["span_mm"] == pytest.approx(26.8)
    assert spans[0].values["z_mm"] == pytest.approx(0.4)
    assert spans[0].severity == "warning"
    assert all(finding.source == "internal" for finding in findings)


def test_a_short_bridge_is_no_warning() -> None:
    """Zehn Millimeter überbrückt jeder Drucker — sonst warnte der Bericht bei
    jedem Schraubenloch."""
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    short = _layers(100.0, 100.0)
    short = SliceResult(
        layers=tuple(replace(layer, bridge_width=8.0) for layer in short.layers),
        support_volume=0.0,
        first_layer_area=100.0,
    )

    codes = {finding.code for finding in advise.warnings_for(settings, profile, short)}
    assert "slice.long_bridge" not in codes


def test_a_support_gap_under_one_layer_welds_itself_on() -> None:
    profile = profiles.make_profile()
    settings = print_settings.with_path(
        print_settings.with_path(print_settings.resolve(profile), "support.style", "grid"),
        "support.z_gap",
        0.05,
    )

    codes = {finding.code for finding in advise.warnings_for(settings, profile)}
    assert "settings.support_gap_too_small" in codes


def test_a_lax_setting_change_needs_a_reason_everywhere() -> None:
    """Regel: eine Zahl ohne Begründung ist schlechter als die Vorgabe."""
    profile = profiles.make_profile("prusa-mk4s", "tpu-95a")
    settings = print_settings.resolve(profile)
    entries = advise.advise(settings, profile, _layers(80.0, 80.0, islands=True))

    assert entries
    for entry in entries:
        assert entry.reason, f"{entry.path} kommt ohne Grund"
        assert entry.value != entry.was, f"{entry.path} schlägt vor, was schon gilt"


def test_flexible_material_caps_the_speed() -> None:
    profile = profiles.make_profile("prusa-mk4s", "tpu-95a")
    settings = print_settings.resolve(profile)

    entries = advise.advise(settings, profile)

    speeds = [entry for entry in entries if entry.path.startswith("speed.")]
    assert speeds
    assert all(float(entry.value) <= advise.FLEXIBLE_MAX_SPEED for entry in speeds)  # type: ignore[arg-type]


def test_too_much_flow_limits_speed_within_the_measured_profile() -> None:
    """Die Grenze, die kein Feld zeigt: Schichthöhe mal Bahnbreite mal Tempo
    ist der Volumenstrom, und darüber wird die Bahn dünner als gerechnet —
    ohne dass an den Einstellungen etwas falsch aussähe. Die Auflösung hält
    die Grenze selbst ein; das zu hohe Tempo setzt hier der Kunde von Hand."""
    profile = profiles.make_profile("prusa-mk4s", "pla")
    settings = print_settings.with_path(
        print_settings.resolve(profile, "draft"), "speed.infill", 300.0
    )
    assert advise.flow_of(settings, settings.speed.infill) > settings.filament.max_flow

    entries = advise.advise(settings, profile)

    changed = advise.apply(settings, entries)
    assert changed.temperature == settings.temperature
    assert advise.flow_of(changed, changed.speed.infill) <= changed.filament.max_flow


def test_a_calm_setting_needs_no_flow_advice() -> None:
    profile = profiles.make_profile("prusa-mk4s", "petg")
    settings = print_settings.resolve(profile, "fine")

    entries = advise.advise(settings, profile)

    assert not [entry for entry in entries if entry.path == "temperature.nozzle"]


def test_a_nozzle_at_its_limit_slows_down_instead() -> None:
    """Heißer geht nicht immer — dann ist der andere Weg der einzige, und ein
    Vorschlag über die Maschinengrenze hinaus wäre keiner."""
    profile = profiles.make_profile("anycubic-kobra-2", "pla")
    settings = print_settings.with_path(
        print_settings.with_path(print_settings.resolve(profile, "draft"), "speed.infill", 150.0),
        "temperature.nozzle",
        profile.printer.nozzle_temperature_max,
    )

    entries = advise.advise(settings, profile)

    slower = next(entry for entry in entries if entry.path == "speed.infill")
    assert float(slower.value) < settings.speed.infill  # type: ignore[arg-type]
    assert not [
        entry
        for entry in entries
        if entry.path == "temperature.nozzle"
        and int(entry.value) > profile.printer.nozzle_temperature_max  # type: ignore[call-overload]
    ]


def test_the_flow_rule_sees_what_the_others_changed() -> None:
    """Bei weichem Filament senkt die Materialregel das Tempo. Rechnete der
    Volumenstrom gegen das alte, empfähle er eine heißere Düse für ein Tempo,
    das nebenan schon gesenkt wurde. Die Auflösung bleibt schon unter der
    Grenze; das schnelle Tempo stammt hier aus einem Projekt von vorher."""
    profile = profiles.make_profile("prusa-mk4s", "tpu-95a")
    settings = print_settings.with_path(
        print_settings.resolve(profile, "draft"), "speed.infill", 120.0
    )

    entries = advise.advise(settings, profile)
    after = advise.apply(settings, entries)

    assert after.speed.infill <= advise.FLEXIBLE_MAX_SPEED
    assert advise.flow_of(after, after.speed.infill) < advise.flow_of(
        settings, settings.speed.infill
    )


def test_no_setting_gets_two_suggestions() -> None:
    """Zwei Zeilen für dieselbe Einstellung wären keine zwei Vorschläge,
    sondern eine Liste, die sich selbst widerspricht."""
    profile = profiles.make_profile("prusa-mk4s", "tpu-95a")
    settings = print_settings.resolve(profile, "draft")

    paths = [entry.path for entry in advise.advise(settings, profile, fit_kinds=("clearance",))]

    assert len(paths) == len(set(paths))


def test_a_flush_fit_asks_for_ironing() -> None:
    """Eine bündige Passung legt zwei Flächen aufeinander — die obere gleitet.

    Gebügelt sitzt sie auf einer geschlossenen Fläche statt auf den Kanten der
    Bahnen. Bisher war das ein Schalter im Dialog, den man kennen musste.
    """
    profile = profiles.make_profile()
    settings = print_settings.with_path(print_settings.resolve(profile), "shell.ironing", False)

    paths = [entry.path for entry in advise.advise(settings, profile, fit_kinds=("flush",))]

    assert "shell.ironing" in paths


def test_a_sliding_fit_does_not_ask_for_ironing() -> None:
    """Bei einem Schiebesitz oder einem Gewinde wäre Bügeln verlorene Zeit auf
    einer Fläche, die nichts berührt — die Art zählt, nicht nur das Ob.
    """
    profile = profiles.make_profile()
    settings = print_settings.with_path(print_settings.resolve(profile), "shell.ironing", False)

    for kind in ("clearance", "press", "thread"):
        paths = [entry.path for entry in advise.advise(settings, profile, fit_kinds=(kind,))]
        assert "shell.ironing" not in paths, kind
        assert "shell.precise_outer_wall" in paths, f"die anderen Regeln gelten weiter ({kind})"


def test_a_heated_chamber_gets_used_when_it_is_there() -> None:
    profile = profiles.make_profile("bambu-x1c", "abs")
    settings = print_settings.with_path(print_settings.resolve(profile), "temperature.chamber", 0)

    entries = advise.advise(settings, profile)

    chamber = next(entry for entry in entries if entry.path == "temperature.chamber")
    assert int(chamber.value) > 0  # type: ignore[call-overload]


def test_the_flow_limit_reaches_the_slicer() -> None:
    """Die Zahl gehört ins Filamentprofil — dort setzt der Slicer sie durch,
    auch für die Wege, die Solidon nicht einzeln einstellt."""
    settings = print_settings.resolve(profiles.make_profile("prusa-mk4s", "tpu-95a"))

    for flavour in ("prusa", "orca"):
        written = handover.as_mapping(settings, flavour)  # type: ignore[arg-type]
        assert written["filament_max_volumetric_speed"] == "3.5"


def test_fits_slow_the_outer_wall_down() -> None:
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)

    entries = advise.advise(settings, profile, fit_kinds=("clearance",))

    assert "speed.outer_wall" in _paths(entries)
    assert "shell.outer_wall_first" in _paths(entries)


def test_advice_without_a_slice_still_works() -> None:
    """Vor dem ersten Schnitt soll der Bericht nicht leer sein."""
    profile = profiles.make_profile("prusa-mk4s", "tpu-95a")
    entries = advise.advise(print_settings.resolve(profile), profile)
    assert entries


def test_applying_advice_changes_exactly_what_it_named() -> None:
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    entries = advise.advise(settings, profile, _layers(500.0, 500.0, islands=True))

    changed = advise.apply(settings, entries)

    for entry in entries:
        assert print_settings.read_path(changed, entry.path) == entry.value
    assert changed.layers.layer_height == settings.layers.layer_height


# --- Übergabe an den Slicer (§29) ---------------------------------------------------


@pytest.mark.parametrize("flavour", ["prusa", "orca", "cura"])
def test_every_setting_in_a_table_actually_exists(flavour: str) -> None:
    """Ein Tippfehler im Punktpfad wäre sonst erst beim Slicen zu sehen."""
    settings = print_settings.resolve(profiles.make_profile())
    for entry in slicer_keys.TABLES[flavour]:  # type: ignore[index]
        print_settings.read_path(settings, entry.path)
        assert entry.key, f"{entry.path} hat keinen Namen beim Slicer"


#: Einstellungen, die ein Slicer nicht kennt — mit dem Grund daneben.
#:
#: Der Test darunter prüft **alle** Einstellungen gegen alle drei Familien.
#: Wer eine neue anlegt und irgendwo nicht zuordnet, muss sich hier erklären;
#: eine Liste ohne Begründung wäre nur eine Liste von Ausreden.
UNREACHABLE: dict[str, dict[str, str]] = {
    "prusa": {
        "shell.precise_outer_wall": "PrusaSlicer kompensiert die Bahnbreite immer, ohne Schalter.",
        "adhesion.kind": "kennt keine Art, nur die Maße — ``ADHESION_KEYS`` nullt die anderen.",
        "support.block_channels": "reist als Stützsperre in der 3MF (``AS_GEOMETRY``).",
    },
    "orca": {
        "adhesion.kind": "in ``brim_type`` enthalten, das die Tabelle schreibt.",
        "support.block_channels": "reist als Stützsperre in der 3MF (``AS_GEOMETRY``).",
    },
    "cura": {
        "support.block_channels": "reist als eigenes Netz (``AS_GEOMETRY``).",
        "shell.wall_generator": "CuraEngine rechnet immer mit variabler Bahnbreite.",
        "shell.precise_outer_wall": "wie oben — es gibt keinen Schalter dafür.",
        "adhesion.kind": "in ``adhesion_type`` enthalten, das die Tabelle schreibt.",
        "retraction.wipe": "kennt kein Abstreifen beim Rückzug, nur das zwischen den Schichten.",
        "filament.density": "steht im Materialprofil des Fensters, nicht in der Rechenmaschine.",
        "filament.colour": "wie oben",
        "filament.cost_per_kg": "wie oben",
        "filament.max_flow": "CuraEngine liest den Volumenstrom nicht; Solidon deckelt die Tempi.",
    },
}


@pytest.mark.parametrize(
    ("flavour", "key"),
    [("orca", "brim_object_gap"), ("prusa", "brim_separation"), ("cura", "brim_gap")],
)
@pytest.mark.parametrize("gap", [0.0, 0.1, 0.25])
def test_a_chosen_brim_gap_reaches_the_actual_slicer_key(flavour, key, gap) -> None:
    profile = profiles.make_profile()
    settings = print_settings.with_choice(print_settings.resolve(profile), "adhesion.kind", "brim")
    settings = print_settings.with_choice(settings, "adhesion.brim_gap", gap)
    written = handover.values_for(settings, profile, flavour)
    assert float(written[key]) == pytest.approx(gap)
    assert settings.chosen >= {"adhesion.kind", "adhesion.brim_gap"}


@pytest.mark.parametrize("flavour", ["prusa", "orca", "cura"])
def test_every_setting_reaches_every_slicer(flavour: str) -> None:
    """Was der Dialog anbietet, muss überall ankommen — sonst stellt der
    Nutzer etwas ein, das für seinen Slicer folgenlos bleibt.

    Genau das war der Fall: ``support.placement`` erreichte PrusaSlicer nicht,
    obwohl es dort ``support_material_buildplate_only`` heißt, und die
    Stützdichte kam bei zwei von drei Familien nie an. Neun handverlesene
    Pfade zu prüfen hat das nicht gefunden — alle zu prüfen schon.
    """
    profile = profiles.make_profile()
    base = print_settings.resolve(profile)
    excused = UNREACHABLE[flavour]
    for path in _every_setting():
        if path in excused:
            continue
        # Ein Haftungsmaß gilt nur für seine Art — die anderen werden
        # ausdrücklich genullt (``_only_chosen_adhesion``). Also erst die Art
        # einstellen, sonst prüft der Test die Nullung statt die Zuordnung.
        settings = _with_context(base, path)
        # Gegen ``values_for`` und nicht gegen die Tabelle: was der Slicer
        # bekommt, ist die Frage — ob es aus der Zuordnung kommt oder aus der
        # Ableitungsstufe, ist seine Sache nicht.
        before = handover.values_for(settings, profile, flavour)  # type: ignore[arg-type]
        after = handover.values_for(
            print_settings.with_choice(settings, path, _other_value(settings, path)),
            profile,
            flavour,  # type: ignore[arg-type]
        )
        assert before != after, f"{flavour} bekommt {path} nicht, und nichts begründet das"


def _with_context(
    settings: print_settings.PrintSettings, path: str
) -> print_settings.PrintSettings:
    """Stellt ein, was der Pfad braucht, um überhaupt wirksam zu sein."""
    needed = {
        "adhesion.skirt_loops": "skirt",
        "adhesion.skirt_distance": "skirt",
        "adhesion.brim_width": "brim",
        "adhesion.brim_gap": "brim",
        "adhesion.raft_layers": "raft",
    }.get(path)
    if needed is not None:
        settings = print_settings.with_path(settings, "adhesion.kind", needed)
    if path.startswith("support.") and path != "support.style":
        settings = print_settings.with_path(settings, "support.style", "grid")
    return settings


def _every_setting() -> list[str]:
    """Jede Einstellung als Punktpfad, aus dem Modell gelesen."""
    settings = print_settings.resolve(profiles.make_profile())
    paths: list[str] = []
    for group in (
        "layers",
        "shell",
        "infill",
        "temperature",
        "cooling",
        "speed",
        "support",
        "adhesion",
        "retraction",
        "filament",
    ):
        paths += [f"{group}.{field.name}" for field in fields(getattr(settings, group))]
    return paths


def _other_value(settings: print_settings.PrintSettings, path: str) -> object:
    """Irgendein anderer Wert derselben Art — für die Frage, ob er ankommt."""
    current = print_settings.read_path(settings, path)
    if isinstance(current, bool):
        return not current
    if isinstance(current, int):
        return current + 3
    if isinstance(current, float):
        return current + 3.0
    choices = {
        "shell.seam_position": "rear",
        "shell.wall_generator": "classic",
        "infill.pattern": "gyroid",
        "support.style": "tree",
        "support.placement": "build_plate",
        "adhesion.kind": "raft",
        "filament.colour": "#123456",
    }
    return choices[path]


def test_the_support_angle_is_counted_from_the_right_side() -> None:
    """Derselbe Zahlenwert heißt in zwei Zählweisen das Gegenteil.

    Solidon misst gegen die Senkrechte — 0° stützt jeden Überhang, 90° keinen.
    Das ist Curas Zählweise; PrusaSlicer und die Orca-Familie messen gegen die
    Horizontale. Gemessen an einem Keil mit 30° Neigung: die beiden kippten
    zwischen 20 und 40, Cura zwischen 50 und 70 — an den Rändern wurde aus
    „stütze fast alles" ein „stütze fast nichts".
    """
    profile = profiles.make_profile()
    settings = print_settings.with_path(
        print_settings.resolve(profile), "support.threshold_angle", 50.0
    )

    assert handover.as_mapping(settings, "cura")["support_angle"] == "50"
    assert handover.as_mapping(settings, "prusa")["support_material_threshold"] == "40"
    assert handover.as_mapping(settings, "orca")["support_threshold_angle"] == "40"


def test_no_support_at_all_never_becomes_automatic() -> None:
    """Der Rand, an dem die Umrechnung kippen würde.

    Solidons 90° heißen „stütze nichts". Umgerechnet wäre das eine 0 — und
    die heißt bei PrusaSlicer „automatische Erkennung", bei Orca „nimm beim
    Baum 30". Aus der Absicht würde ihr Gegenteil.
    """
    profile = profiles.make_profile()
    settings = print_settings.with_path(
        print_settings.resolve(profile), "support.threshold_angle", 90.0
    )

    assert handover.as_mapping(settings, "prusa")["support_material_threshold"] == "1"
    assert handover.as_mapping(settings, "orca")["support_threshold_angle"] == "1"


def test_shares_are_written_as_percentages() -> None:
    """Solidon rechnet in 0…1, die Slicer in 0…100 — die Stelle, an der ein
    Fehler fünfzehn Prozent Füllung zu fünfzehn Hundertsteln macht."""
    settings = print_settings.resolve(profiles.make_profile())
    written = handover.as_mapping(settings, "prusa")

    assert written["fill_density"] == "15%"
    assert written["max_fan_speed"] == "100"


# --- die Lüfterkurve (Befund Robert, 23.09.2026) ---------------------------------

#: Wie jede Familie das obere Ende, das untere Ende und die Schwelle der
#: Lüfterkurve nennt. Alle drei regeln den Bauteillüfter nach der Schichtzeit:
#: bis zur Mindestzeit je Schicht voll, ab der Schwelle nur noch mit dem
#: unteren Wert, dazwischen linear.
_FAN_CURVE_KEYS: Final[dict[str, tuple[str, str, str]]] = {
    "orca": ("fan_max_speed", "fan_min_speed", "fan_cooling_layer_time"),
    "prusa": ("max_fan_speed", "min_fan_speed", "fan_below_layer_time"),
    "cura": ("cool_fan_speed_max", "cool_fan_speed_min", "cool_min_layer_time_fan_speed_max"),
}


@pytest.mark.parametrize("material", ["pla", "petg", "petg-cf", "asa", "abs", "tpu-95a"])
@pytest.mark.parametrize("flavour", ["orca", "prusa", "cura"])
def test_the_fan_curve_reaches_every_slicer_with_both_ends(flavour: str, material: str) -> None:
    """Befund Robert, 23.09.2026: „Beim Drucken ist unser Modelllüfter auch
    immer auf 100 % eingestellt.“

    Solidon kannte einen Lüfterwert und schrieb ihn an **beide** Enden der
    Kurve — ``fan_max_speed`` und ``fan_min_speed`` bei der Orca-Familie,
    ``max_fan_speed`` und ``min_fan_speed`` bei PrusaSlicer, über die Spiegelung
    ``cool_fan_speed_max`` und ``cool_fan_speed_min`` bei Cura. Gemessen am
    ElegooSlicer mit Centauri Carbon 2 und PLA: ``M106 S255`` in jeder der 135
    Schichten nach der ersten, obwohl Elegoos eigenes Profil 50 bis 100 %
    vorsieht.
    """
    profile = profiles.make_profile("centauri-carbon-2", material)
    settings = print_settings.resolve(profile)
    cooling = settings.cooling
    values = handover.values_for(settings, profile, flavour)  # type: ignore[arg-type]

    high, low, threshold = _FAN_CURVE_KEYS[flavour]
    assert values[high] == f"{cooling.fan_speed * 100.0:g}"
    assert values[low] == f"{cooling.minimum_fan_speed * 100.0:g}"
    assert values[threshold] == f"{cooling.fan_below_layer_time:g}"
    assert cooling.minimum_fan_speed <= cooling.fan_speed
    assert cooling.fan_below_layer_time > cooling.minimum_layer_time


def test_pla_does_not_run_the_part_fan_at_full_speed_on_every_layer() -> None:
    """Das Material des Befunds, ausdrücklich: Eine PLA-Schicht, die lange
    genug zum Abkühlen dauert, braucht nicht die volle Drehzahl — und der
    Lüfter geht dabei auch nicht ganz aus. Die zweite Hälfte ist der zweite
    Fund derselben Messung: Ohne Herstellerprofil stand
    ``reduce_fan_stop_start_freq`` auf dem Slicerstandard 0, und jede Schicht
    über 60 s lief ganz ohne Lüfter (``M106 S0``)."""
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.resolve(profile)
    orca = handover.values_for(settings, profile, "orca")
    prusa = handover.values_for(settings, profile, "prusa")
    cura = handover.values_for(settings, profile, "cura")

    assert float(orca["fan_min_speed"]) < float(orca["fan_max_speed"])
    assert float(prusa["min_fan_speed"]) < float(prusa["max_fan_speed"])
    assert float(cura["cool_fan_speed_min"]) < float(cura["cool_fan_speed_max"])
    assert float(orca["fan_min_speed"]) > 0
    assert orca["reduce_fan_stop_start_freq"] == "1"
    assert prusa["fan_always_on"] == "1"
    assert "fan_min_speed" in handover.by_section(settings, "orca")["filament"]
    assert "reduce_fan_stop_start_freq" in handover.by_section(settings, "orca")["filament"]


def test_the_lower_fan_end_never_rises_above_the_upper() -> None:
    """Ein unterer Wert über dem oberen hieße: Je länger die Schicht, desto
    stärker der Lüfter. Keiner der drei Slicer fängt das ab — Orca und
    PrusaSlicer rechnen die Gerade trotzdem, Curas ``cool_fan_speed_max``
    hat kein ``max()``. Die Übergabe deckelt deshalb auf den oberen Wert."""
    profile = profiles.make_profile("centauri-carbon-2", "asa")
    settings = print_settings.resolve(profile)
    settings = print_settings.with_path(settings, "cooling.minimum_fan_speed", 0.9)
    upper = f"{settings.cooling.fan_speed * 100.0:g}"

    for flavour, (high, low, _threshold) in _FAN_CURVE_KEYS.items():
        values = handover.values_for(settings, profile, flavour)  # type: ignore[arg-type]
        assert values[low] == upper == values[high], flavour


def test_the_manufacturers_fan_curve_survives_the_handover(tmp_path: Path) -> None:
    """Die Messung, die den Befund belegt hat, als Test: Elegoo PLA @ECC2
    nennt 50 bis 100 % mit der Schwelle bei 80 s. Eine Spule mit diesem Profil
    übernimmt die Werte des Herstellers (``settings_for_slot``) — gelesen
    wurde bisher nur das obere Ende, und geschrieben wurde es an beide."""
    vendor = _filament_profile(
        tmp_path,
        "Elegoo PLA @ECC2",
        filament_type=["PLA"],
        fan_min_speed=["50"],
        fan_max_speed=["100"],
        fan_cooling_layer_time=["80"],
        slow_down_layer_time=["4"],
    )
    slot = MaterialSlot(0, "PLA", material=str(vendor), material_type="PLA")
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(Path("elegoo-slicer.exe"), "orca")

    config = handover.write_config(settings, profile, setup, tmp_path, (slot,))
    emitted = json.loads(config.filaments[0].read_text(encoding="utf-8"))
    embedded = handover.project_settings(settings, profile, setup, slots=(slot,))

    for written in (emitted, embedded):
        assert written["fan_min_speed"] == ["50"]
        assert written["fan_max_speed"] == ["100"]
        assert written["fan_cooling_layer_time"] == ["80"]
        assert written["reduce_fan_stop_start_freq"] == ["1"]
    assert config.written["fan_min_speed"] == "50"


def _without_fan_curve(cooling: dict[str, object], fan_speed: float) -> None:
    """Ein Kühlblock, wie ihn Solidon vor dem 23.09.2026 speicherte: ein Wert."""
    cooling["fan_speed"] = fan_speed
    del cooling["minimum_fan_speed"]
    del cooling["fan_below_layer_time"]


@pytest.mark.parametrize(
    ("material", "stored", "upper", "lower", "below"),
    [
        # Der Befund: PLA stand auf 1.0 und lief damit fest voll.
        ("pla", 1.0, 1.0, 0.5, 80.0),
        # PETG bekommt seine Materialwerte, auch unter einem hohen alten Wert.
        ("petg", 1.0, 1.0, 0.2, 30.0),
        # Ein eigener alter Wert bleibt das obere Ende …
        ("pla", 0.6, 0.6, 0.5, 80.0),
        # … und das untere steht nie darüber.
        ("pla", 0.3, 0.3, 0.3, 80.0),
    ],
)
def test_an_older_settings_record_gets_the_fan_curve_of_its_material(
    material: str, stored: float, upper: float, lower: float, below: float
) -> None:
    """Entscheidung der Durchsicht vom 23.09.2026, im Sinne Roberts: Der eine
    gespeicherte Lüfterwert war immer das **obere** Ende — das Feld hieß
    „Lüfter", und dass die Übergabe ihn auch als unteres schrieb, war der
    Fehler, keine Wahl des Kunden. Unteres Ende und Schwelle kommen beim
    Öffnen aus derselben Materialzeile wie bei einem neuen Projekt, das untere
    höchstens so hoch wie das gespeicherte obere."""
    from app.core.scene import serialise

    settings = print_settings.resolve(profiles.make_profile("centauri-carbon-2", material))
    old = json.loads(json.dumps(serialise.print_settings_to_data(settings)))
    _without_fan_curve(old["cooling"], stored)

    cooling = serialise.print_settings_from_data(old, material).cooling

    assert cooling.fan_speed == pytest.approx(upper)
    assert cooling.minimum_fan_speed == pytest.approx(lower)
    assert cooling.fan_below_layer_time == pytest.approx(below)


def test_an_older_project_file_prints_pla_with_the_curve(tmp_path: Path) -> None:
    """Dasselbe durch eine echte Projektdatei: gespeichert, der Kühlblock auf
    den alten Stand zurückgeschrieben, wieder geöffnet — und übergeben. Eine
    Spule mit eigener Materialart ergänzt ihre Kurve aus ihrem Material, wie
    ``settings_for_slot`` es für sie auflöst. Ohne Materialangabe im Projekt
    gilt das Material, das die Sitzung annimmt (PLA am Centauri)."""
    from app.core.types import SlotOverride

    for material in ("pla", ""):
        profile = profiles.make_profile("centauri-carbon-2", "pla")
        settings = print_settings.resolve(profile)
        petg = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "petg"))
        settings = replace(
            settings,
            slot_overrides=(
                SlotOverride(
                    name="Grün",
                    colour=(0.0, 1.0, 0.0),
                    material_type="PETG",
                    cooling=petg.cooling,
                ),
            ),
        )
        project = new_project("centauri-carbon-2", material)
        project.document.print_settings = settings
        path = save(project, tmp_path / f"alt-{material or 'leer'}.p3d")
        with zipfile.ZipFile(path) as container:
            entries = {name: container.read(name) for name in container.namelist()}
        data = json.loads(entries[PROJECT_ENTRY])
        _without_fan_curve(data["print_settings"]["cooling"], 1.0)
        _without_fan_curve(data["print_settings"]["slot_overrides"][0]["cooling"], 0.5)
        entries[PROJECT_ENTRY] = json.dumps(data).encode("utf-8")
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as container:
            for name, payload in entries.items():
                container.writestr(name, payload)

        opened = load(path).document.print_settings
        assert opened is not None
        values = handover.values_for(opened, profile, "orca")
        assert (values["fan_max_speed"], values["fan_min_speed"]) == ("100", "50"), material
        assert values["fan_cooling_layer_time"] == "80"
        assert values["reduce_fan_stop_start_freq"] == "1"
        override = opened.slot_overrides[0]
        assert override is not None and override.cooling is not None
        assert override.cooling.minimum_fan_speed == pytest.approx(0.2)
        assert override.cooling.fan_below_layer_time == pytest.approx(30.0)


def test_a_current_settings_record_keeps_its_own_fan_curve() -> None:
    """Die Ergänzung gilt nur dem, was fehlt: Wer die Kurve selbst eingestellt
    hat, bekommt beim Öffnen nicht die des Materials zurück."""
    from app.core.scene import serialise

    settings = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "pla"))
    own = replace(
        settings,
        cooling=replace(settings.cooling, minimum_fan_speed=0.35, fan_below_layer_time=45.0),
    )
    stored = json.loads(json.dumps(serialise.print_settings_to_data(own)))

    assert serialise.print_settings_from_data(stored, "pla").cooling == own.cooling


def test_the_colour_reaches_the_slicer() -> None:
    profile = profiles.make_profile("prusa-mk4s", "petg")
    settings = print_settings.resolve(profile)

    for flavour in ("prusa", "orca"):
        written = handover.as_mapping(settings, flavour)  # type: ignore[arg-type]
        assert written["filament_colour"] == settings.filament.colour


def test_support_off_is_written_as_off_everywhere() -> None:
    settings = print_settings.resolve(profiles.make_profile())
    assert settings.support.style == "none"

    assert handover.as_mapping(settings, "prusa")["support_material"] == "0"
    assert handover.as_mapping(settings, "orca")["enable_support"] == "0"
    assert handover.as_mapping(settings, "cura")["support_enable"] == "false"


def test_support_on_actually_reaches_the_slicer() -> None:
    """Der Fehler, den erst ein echter Lauf zeigte: Orca schreibt Wahrheits-
    werte als ``0``/``1`` wie PrusaSlicer, nicht als ``true``/``false`` wie
    Cura. Ein ``true`` dort ist geräuschlos wirkungslos — der Slicer meldet
    nichts, er stützt bloß nicht, und die Stützenart daneben stimmt sogar.
    """
    settings = print_settings.with_path(
        print_settings.resolve(profiles.make_profile()), "support.style", "tree"
    )

    orca = handover.as_mapping(settings, "orca")
    assert orca["enable_support"] == "1"
    assert orca["support_type"] == "tree(auto)"
    assert handover.as_mapping(settings, "prusa")["support_material"] == "1"
    cura = handover.as_mapping(settings, "cura")
    assert cura["support_enable"] == "true"
    # Nicht nur das An/Aus: `support_structure` steht in der
    # fdmprinter-Definition — ohne den Schlüssel druckte Cura Gitterstützen,
    # wo Baumstützen eingestellt waren, und `verify()` sah nichts.
    assert cura["support_structure"] == "tree"


def test_grid_supports_reach_every_slicer_as_a_grid() -> None:
    """„Gitter" kam als Elegoos ``rectilinear`` an: Linien in einer Richtung,
    die ab Schicht 2 als freistehende Wände umkippten (Waschschüssel,
    25.09.2026). Bäume behalten das Muster des Herstellers.

    Cura nicht: Sein ``zigzag`` verbindet die Linien und kippt nicht, und alle
    Werksprofile in Cura fahren es (Stufe D, Prüfbericht Cura B4).
    """
    base = print_settings.resolve(profiles.make_profile())
    grid = print_settings.with_path(base, "support.style", "grid")
    tree = print_settings.with_path(base, "support.style", "tree")

    assert handover.as_mapping(grid, "orca")["support_base_pattern"] == "rectilinear-grid"
    assert handover.as_mapping(grid, "prusa")["support_material_pattern"] == "rectilinear-grid"
    assert "support_pattern" not in handover.as_mapping(grid, "cura")
    assert "support_base_pattern" not in handover.as_mapping(tree, "orca")
    assert "support_material_pattern" not in handover.as_mapping(tree, "prusa")
    assert "support_pattern" not in handover.as_mapping(tree, "cura")


def test_curas_zigzag_keeps_the_density_and_a_tree_carries_none() -> None:
    """Curas ``zigzag`` ist eine Linienschar: Linienabstand gleich Bahnbreite
    durch Dichte (fdmprinter-Definition, Faktor eins). Der Baum trägt nach
    Curas Formel keine Füllung, nur seine Wand — Solidon gab ihm 15 % dazu
    (Prüfbericht Cura, B4)."""
    profile = profiles.make_profile()
    base = print_settings.resolve(profile)
    grid = print_settings.with_path(base, "support.style", "grid")
    tree = print_settings.with_path(base, "support.style", "tree")

    lines = handover.values_for(grid, profile, "cura")
    assert float(lines["support_line_distance"]) == pytest.approx(
        grid.layers.line_width / grid.support.density
    )
    assert lines["support_wall_count"] == "0"
    branches = handover.values_for(tree, profile, "cura")
    assert branches["support_line_distance"] == "0"
    assert branches["support_wall_count"] == "1"


#: Wie PrusaSlicer und die Orca-Familie den Platz einer Bahn rechnen
#: (``Flow::rounded_rectangle_extrusion_spacing``): Breite - Höhe * (1 - pi/4).
def _flow_spacing(width: float, height: float) -> float:
    return width - height * (1.0 - 3.141592653589793 / 4.0)


@pytest.mark.parametrize(
    ("flavour", "key"),
    [("prusa", "support_material_spacing"), ("orca", "support_base_pattern_spacing")],
)
@pytest.mark.parametrize("density", [0.15, 0.5, 1.0])
def test_the_support_density_goes_to_prusa_and_orca_as_the_gap_between_lines(
    flavour: str, key: str, density: float
) -> None:
    """RM-475: PrusaSlicer und die Orca-Familie führen den Stützabstand als
    **Lücke** zwischen zwei Linien (``SupportParameters``: Teilung = Abstand +
    ``support_material_flow.spacing()``). Solidon schrieb die Teilung
    Bahnbreite / Dichte hinein; gedruckt wurde 15 % als 12 % und 50 % als 31 %
    (G-Code-Gegenprüfung 02.10.2026). Geprüft wird die Formel des Slicers,
    einschließlich seiner tatsächlich geschriebenen Stützbahnbreite."""
    profile = profiles.make_profile()
    settings = print_settings.with_path(
        print_settings.with_path(print_settings.resolve(profile), "support.style", "grid"),
        "support.density",
        density,
    )
    width, height = settings.layers.line_width, settings.layers.layer_height

    gap = float(handover.as_mapping(settings, flavour)[key])

    spacing = _flow_spacing(width, height)
    assert spacing / (gap + spacing) == pytest.approx(density, abs=1e-5)
    width_key = "support_material_extrusion_width" if flavour == "prusa" else "support_line_width"
    assert float(handover.as_mapping(settings, flavour)[width_key]) == pytest.approx(width)


def test_the_support_gap_reads_back_as_the_density_it_was_written_from() -> None:
    """Rücklesung und Übergabe rechnen dieselbe Formel in beide Richtungen
    (RM-475): Orcas Kobra-2-Profil mit 0,2 mm Lücke war als 100 % gelesen
    worden, Prusas Bündelwert 2,5 mm als 17 %."""
    from app.core.export import manufacturer

    width, height = 0.42, 0.2
    read = {"layers.line_width": width, "layers.layer_height": height}
    context = manufacturer._Context(nozzle=0.4)
    for density in (0.05, 0.15, 0.5, 0.9):
        gap = manufacturer.support_gap(density, width, height)
        back = manufacturer._support_density(
            {"support_base_pattern_spacing": f"{gap:g}"}, read, context
        )
        assert back == pytest.approx(density, rel=1e-4)
    kobra = manufacturer._support_density({"support_base_pattern_spacing": "0.2"}, read, context)
    assert kobra == pytest.approx(
        _flow_spacing(width, height) / (0.2 + _flow_spacing(width, height))
    )
    assert manufacturer._support_density(
        {"support_base_pattern_spacing": "0"}, read, context
    ) == pytest.approx(1.0), "Lücke null ist die dichteste Stütze, nicht keine"


def test_no_support_density_becomes_the_densest_support() -> None:
    """0 % ergab in PrusaSlicer und der Orca-Familie die dichteste Stütze
    (Lücke 0: am Pilz 28,9 cm³ statt 5,8 cm³). Das Prozentfeld beginnt bei 1.
    Gespeicherte Nullwerte bleiben erhalten und bekommen eine Absage mit
    Handlung, bevor daraus eine Druckdatei wird (RM-475)."""
    from app.core.errors import ValidationError
    from app.core.scene import serialise
    from app.ui.print_settings_dialog import FIELDS

    least = print_settings.LEAST_SUPPORT_DENSITY
    profile = profiles.make_profile()
    grid = print_settings.with_path(print_settings.resolve(profile), "support.style", "grid")
    nothing = print_settings.with_path(grid, "support.density", 0.0)
    for flavour in ("prusa", "orca"):
        with pytest.raises(ValidationError) as caught:
            handover.as_mapping(nothing, flavour)
        assert caught.value.suggestions

    field = next(one for one in FIELDS if one.path == "support.density")
    assert field.minimum == pytest.approx(least * field.factor)

    stored = serialise.print_settings_to_data(nothing)
    assert serialise.print_settings_from_data(stored, "pla").support.density == pytest.approx(0.0)
    assert least == pytest.approx(0.01), "kleinster positiver Wert im ganzzahligen Prozentfeld"


@pytest.mark.parametrize("prusa", [False, True])
@pytest.mark.parametrize("native_width", ["0.4", "100%", "0"])
def test_support_density_reads_the_native_support_width(prusa: bool, native_width: str) -> None:
    """Supportbreite und allgemeine Breite unterscheiden sich absichtlich;
    Prozent gilt bei Prusa der Schichthöhe, bei Orca der Düse."""
    from app.core.export import manufacturer

    values = (
        {"support_material_spacing": "0.2", "support_material_extrusion_width": native_width}
        if prusa
        else {"support_base_pattern_spacing": "0.2", "support_line_width": native_width}
    )
    read = {"layers.line_width": 0.45, "layers.layer_height": 0.2}
    width = 0.45 if native_width == "0" else 0.2 if native_width == "100%" and prusa else 0.4
    strand = _flow_spacing(width, 0.2)
    actual = manufacturer._support_density(
        values, read, manufacturer._Context(nozzle=0.4), prusa=prusa
    )
    assert actual == pytest.approx(strand / (0.2 + strand))


#: Was die Orca-Familie an diesen Stellen annimmt, abgelesen am ausgelieferten
#: Profilbestand von OrcaSlicer und seinen Ablegern. Ein Name daneben fällt
#: still auf die Vorgabe zurück — geprüft wird deshalb hier und nicht im Druck.
ORCA_VALUES = {
    "sparse_infill_pattern": {
        "grid",
        "gyroid",
        "cubic",
        "rectilinear",
        "alignedrectilinear",
        "triangles",
        "3dhoneycomb",
        "zig-zag",
        "crosshatch",
    },
    "seam_position": {"aligned", "nearest", "back", "aligned_back", "random"},
    "seam_slope_type": {"none", "external", "all"},
    "support_type": {"normal(auto)", "tree(auto)", "normal(manual)", "tree(manual)"},
    "brim_type": {"no_brim", "outer_only", "auto_brim", "inner_only", "outer_and_inner"},
    "wall_sequence": {"inner wall/outer wall", "outer wall/inner wall", "inner-outer-inner wall"},
}


@pytest.mark.parametrize("key", sorted(ORCA_VALUES))
def test_orca_gets_names_it_knows(key: str) -> None:
    """Über jeden Wert, den ein Feld annehmen kann — ein Muster, das der Slicer
    nicht kennt, druckt trotzdem, nur eben anders als eingestellt."""
    settings = print_settings.resolve(profiles.make_profile())
    path = next(entry[0] for entry in slicer_keys.ORCA if entry[1] == key)
    for choice in _possible(path):
        mapping = handover.as_mapping(print_settings.with_path(settings, path, choice), "orca")
        # Eine Wahl ohne Art — Stützen aus oder „wie das Profil" — nennt
        # keine (Konzept Herstellerprofil, Entscheidung J). Was sie nennt,
        # muss der Slicer kennen.
        written = mapping.get(key)
        if written is None:
            assert (path, choice) in {("support.style", "none"), ("support.style", "auto")}, (
                f"{path}={choice} schreibt {key} gar nicht"
            )
            continue
        assert written in ORCA_VALUES[key], f"{path}={choice} wird zu {written!r}"


def test_the_scarf_seam_reaches_every_slicer_with_its_length() -> None:
    """Die Schrägnaht braucht ihre Länge: Elegoos Basisprozess führt
    ``seam_slope_min_length = 0``, und mit der Art allein setzte ElegooSlicer am
    Minigolf-Schaft keine einzige Rampe (0 von 1000 Außenschleifen, mit 20 mm
    997). Jede Familie bekommt deshalb Art und Länge, nur für die Außenwand
    und, wo es geht, nur an glatten Schleifen."""
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    on = print_settings.with_path(print_settings.resolve(profile), "shell.scarf_seam", True)

    orca = handover.values_for(on, profile, "orca")
    prusa = handover.values_for(on, profile, "prusa")
    cura = handover.values_for(on, profile, "cura")

    assert {key: orca[key] for key in orca if key.startswith("seam_slope_")} == {
        "seam_slope_type": "external",
        "seam_slope_min_length": "20",
        "seam_slope_conditional": "1",
        "seam_slope_inner_walls": "0",
    }
    # Bambu Studio führt die Schrägnaht auch im Filament, und das sticht ohne
    # diesen Schalter: am P1S kein einziger Rampenanfang.
    assert orca["override_filament_scarf_seam_setting"] == "1"
    assert {key: prusa[key] for key in prusa if key.startswith("scarf_seam_")} == {
        "scarf_seam_placement": "contours",
        "scarf_seam_length": "20",
        "scarf_seam_only_on_smooth": "1",
        "scarf_seam_on_inner_perimeters": "0",
    }
    assert cura["scarf_joint_seam_length"] == "20"
    assert "scarf_joint_seam_length" in handover.CURA_PER_MESH, "Cura nimmt sie je Netz"


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        ({}, None),
        ({"seam_slope_type": "none", "seam_slope_min_length": "20"}, False),
        # Elegoos Basisprozess: Art gesetzt, Länge null — keine Rampe.
        ({"seam_slope_type": "external", "seam_slope_min_length": "0"}, False),
        ({"seam_slope_type": "external", "seam_slope_min_length": "20"}, True),
        # Ohne Länge in der Kette gilt die Vorgabe des Programms, größer null.
        ({"seam_slope_type": "all"}, True),
        (
            {
                "seam_slope_type": "external",
                "seam_slope_min_length": "0",
                "seam_slope_entire_loop": "1",
            },
            True,
        ),
    ],
)
def test_the_foundation_reads_a_scarf_seam_only_when_it_ramps(
    values: dict[str, str], expected: bool | None
) -> None:
    """Die Grundlage liest „an" nur, wo der Slicer wirklich eine Rampe setzt —
    sonst stünde im Dialog eine Schrägnaht, die nicht gedruckt wird."""
    from app.core.export import manufacturer

    assert manufacturer._scarf_seam(values) is expected
    prusa = {
        "seam_slope_type": "scarf_seam_placement",
        "seam_slope_min_length": "scarf_seam_length",
        "seam_slope_entire_loop": "scarf_seam_entire_loop",
    }
    placement = {"none": "nowhere", "external": "contours", "all": "everywhere"}
    translated = {
        prusa[key]: placement.get(value, value) if key == "seam_slope_type" else value
        for key, value in values.items()
    }
    assert manufacturer._prusa_scarf_seam(translated) is expected


def _possible(path: str) -> tuple[object, ...]:
    """Alle Werte, die eine Einstellung annehmen kann — aus ihrem Typ, nicht
    aus einer zweiten Liste, die veralten könnte."""
    group, _dot, name = path.partition(".")
    hints = get_type_hints(type(getattr(print_settings.resolve(profiles.make_profile()), group)))
    arguments = get_args(hints[name])
    return arguments or (True, False)


@pytest.mark.parametrize("flavour", ["prusa", "orca", "cura"])
@pytest.mark.parametrize("kind", ["skirt", "brim", "raft", "none"])
def test_only_the_chosen_adhesion_gets_measurements(flavour: str, kind: str) -> None:
    """Skirt, Brim und Raft sind Maße *ihrer* Art, keine unabhängigen
    Schalter — aber die Slicer lesen sie als solche.

    Alle drei zu schreiben hieße, alle drei zu bekommen: ein Raft unter einem
    Teil, für das „Skirt" eingestellt war. Das kostet Material, Zeit und die
    Unterseite, und es fällt erst auf der Platte auf.
    """
    settings = print_settings.with_path(
        print_settings.resolve(profiles.make_profile()), "adhesion.kind", kind
    )
    written = handover.as_mapping(settings, flavour)  # type: ignore[arg-type]

    for wanted, keys in slicer_keys.ADHESION_KEYS[flavour].items():  # type: ignore[index]
        for key in keys:
            if key not in written:
                continue
            value = float(written[key])
            if wanted == kind:
                assert value > 0.0, f"{kind}: {key} muss ein Maß haben"
            else:
                assert value == 0.0, f"{kind}: {key} gehört zu {wanted} und muss null sein"


# --- Gegenprobe: kam an, was geschrieben wurde? (§28.2) ----------------------------

ECHTER_GCODE = """
; generated by ElegooSlicer 1.5.2.2
G1 X10 Y10 E0.5
; layer_height = 0.2
; wall_loops = 3
; sparse_infill_density = 15%
; enable_support = 0
; nozzle_temperature = 240
"""


def test_the_check_stays_quiet_when_everything_arrived() -> None:
    assert handover.verify(ECHTER_GCODE, {"layer_height": "0.2", "wall_loops": "3"}) == []


def test_the_check_finds_what_the_slicer_ignored() -> None:
    """Das ist die Auskunft, die vom Slicer selbst kommt statt aus einer
    Dokumentation, die für die installierte Version gelten mag oder nicht.

    Damit prüft sich auch ein Slicer selbst, den beim Bauen der Tabelle
    niemand vorliegen hatte — und genau daran hing, dass PrusaSlicer und
    CuraEngine hier nie liefen.
    """
    findings = handover.verify(ECHTER_GCODE, {"layer_height": "0.3", "wall_loops": "99"})

    assert len(findings) == 1
    assert findings[0].severity == "warning"
    assert findings[0].source == "gcode", "gemessen, nicht geschätzt (Regel 14)"
    assert "layer_height" in str(findings[0].values["settings"])


def test_a_key_the_file_never_mentions_says_nothing() -> None:
    """Kein Slicer schreibt alles. Was nicht dasteht, ist keine Abweichung —
    sonst meldete die Gegenprobe bei jedem Lauf zwanzig Fehler und würde nach
    dem dritten Mal weggesehen."""
    assert handover.verify(ECHTER_GCODE, {"gibtesnichtimformat": "7"}) == []


@pytest.mark.parametrize(
    ("actual", "wanted"),
    [("0.20", "0.2"), ("15%", "15"), ('["0.4"]', "0.4"), ("  3  ", "3")],
)
def test_the_check_compares_leniently(actual: str, wanted: str) -> None:
    """``0.2`` und ``0.20`` meinen dasselbe. Eine Gegenprobe, die darüber
    stolpert, meldet Unterschiede, die keine sind."""
    text = f"; irgendein_wert = {actual}\n"
    assert handover.verify(text, {"irgendein_wert": wanted}) == []


def test_recomputed_keys_are_left_alone() -> None:
    """Manches rechnet der Slicer bewusst um — eine Farbe wird zur Liste, weil
    ein Drucker mehrere Filamente führt. Das ist keine Abweichung."""
    text = '; filament_colour = ["#FF0000";"#00FF00"]\n'
    assert handover.verify(text, {"filament_colour": "#FF0000"}) == []


@pytest.mark.parametrize("flavour", ["prusa", "orca"])
def test_the_prusa_family_writes_no_word_booleans(flavour: str) -> None:
    """Beide erben von Slic3r und lesen nur Zahlen. Ein ``true`` oder
    ``false`` in einem dieser Profile ist immer ein Fehler."""
    settings = print_settings.resolve(profiles.make_profile())
    written = handover.as_mapping(settings, flavour)  # type: ignore[arg-type]

    wrong = {key: value for key, value in written.items() if value in ("true", "false")}
    assert not wrong, f"{flavour} bekommt Wortwerte: {wrong}"


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("prusa-slicer-console.exe", "prusa"),
        ("PrusaSlicer", "prusa"),
        ("superslicer", "prusa"),
        ("orca-slicer.exe", "orca"),
        ("elegoo-slicer.exe", "orca"),
        ("BambuStudio.exe", "orca"),
        # Creality Print ab Version 6 ist ein Orca-Abkömmling. Gemessen an 7.2:
        # derselbe Profilbaum, 4234 lesbare Profile, dieselbe Übergabedatei.
        ("CrealityPrint.exe", "orca"),
        ("creality-print", "orca"),
        ("CuraEngine.exe", "cura"),
        ("notepad.exe", None),
    ],
)
def test_the_slicer_family_is_recognised_by_name(name: str, expected: str | None) -> None:
    assert slicer_keys.flavour_of(name) == expected


def test_an_unknown_program_only_opens_and_refuses_the_console_with_a_way_out(
    tmp_path: Path,
) -> None:
    """Ein Programm ohne Familie bekommt die Datei ins Fenster — und sonst nichts.

    Bis zum 22.09.2026 lehnte schon ``detect`` ab, und damit scheiterte auch
    das bloße Öffnen, das keine Übersetzung braucht: Ein Resin-Slicer kam nie
    an die Reihe (RM-071). Jetzt ist es die Familie ``other``; der
    Konsolenweg sagt an seiner Stelle ab, mit Vorschlag (Regel 17).
    """
    setup = handover.detect(Path("ChituBox.exe"))
    assert setup.flavour == "other"
    assert handover.only_opens(setup)
    assert handover.window_program(setup.executable) == setup.executable

    profile = profiles.make_profile("generic-resin-130", "resin")
    settings = print_settings.resolve(profile)
    with pytest.raises(ExternalToolError) as raised:
        handover.write_config(settings, profile, setup, tmp_path)
    assert raised.value.suggestions, "Regel 17: jede Ausnahme trägt einen Vorschlag"
    assert not list(tmp_path.iterdir()), "für other wird keine Konfiguration geschrieben"
    with pytest.raises(ExternalToolError) as raised:
        handover.slice_model(tmp_path / "teil.stl", settings, profile, setup)
    assert raised.value.suggestions
    # Und die Maschinenseite hat für dieses Programm keinen Befund: Es gibt
    # kein Profil, das fehlen könnte.
    assert handover.machine_missing(setup, profile) == []
    assert handover.setting_limitations("other") == []


def test_a_prusa_config_stands_on_its_own(tmp_path: Path) -> None:
    """PrusaSlicer lädt eine ``.ini`` ohne weiteres Profil — dann muss die
    Bettform darin stehen."""
    profile = profiles.make_profile("prusa-mk4s", "pla")
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(executable=Path("PrusaSlicer.exe"), flavour="prusa")

    written = handover.write_config(settings, profile, setup, tmp_path)
    text = written.process.read_text(encoding="utf-8")

    assert written.filament is None, "PrusaSlicer nimmt alles in einer Datei"
    assert "bed_shape" in text
    assert "nozzle_diameter" in text
    assert f"layer_height = {settings.layers.layer_height:g}" in text
    assert f"temperature = {settings.temperature.nozzle:d}" in text


def test_a_line_break_in_the_print_settings_is_refused_when_opening(tmp_path: Path) -> None:
    """Eine fremde Projektdatei bringt ihre Druckeinstellungen mit.

    ``print_settings`` war der einzige Block des Dokuments ohne Formprüfung:
    ``print_settings_from_data`` übernimmt die Werte mit ``klass(**…)``, und
    die ``Literal``-Typen gelten zur Laufzeit nicht. Ein Zeilenumbruch im
    Titel reiste damit bis in die ``.ini`` von PrusaSlicer, wo er die
    Einträge trennt.
    """
    path = save(new_project(), tmp_path / "umbruch.p3d")
    with zipfile.ZipFile(path) as container:
        entries = {name: container.read(name) for name in container.namelist()}
    data = json.loads(entries[PROJECT_ENTRY])
    # Ein neues Projekt legt noch keine Druckeinstellungen ab (``None``) — die
    # fremde Datei bringt den Block also vollständig selbst mit, und genau so
    # kommt er beim Kunden an.
    data["print_settings"] = {"title": "Standard\npost_process = beliebiger Befehl\n# "}
    entries[PROJECT_ENTRY] = json.dumps(data).encode("utf-8")
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as container:
        for name, payload in entries.items():
            container.writestr(name, payload)

    with pytest.raises(ValidationError) as caught:
        load(path)

    assert caught.value.constraint == "damaged"
    assert "print_settings.title" in str(caught.value.values.get("reason", ""))
    assert caught.value.suggestions, "Regel 17: jede Ausnahme trägt einen Vorschlag"


def test_a_line_break_in_the_title_never_becomes_an_ini_line(tmp_path: Path) -> None:
    """Die Gegenprobe an der Schreibstelle, unabhängig vom Weg dorthin.

    Der Titel steht als Kommentar in der ersten Zeile der ``.ini``. Trüge er
    einen Umbruch, stünde ab der zweiten Zeile eine Einstellung — und
    ``post_process`` schreibt Solidon nirgends selbst, es hätte also keine
    Konkurrenz.
    """
    profile = profiles.make_profile("prusa-mk4s", "pla")
    settings = replace(
        print_settings.resolve(profile),
        title="Standard\npost_process = beliebiger Befehl\n# ",
    )
    setup = handover.SlicerSetup(executable=Path("PrusaSlicer.exe"), flavour="prusa")

    written = handover.write_config(settings, profile, setup, tmp_path)
    lines = written.process.read_text(encoding="utf-8").splitlines()

    # Der Titel darf den Text tragen — er steht als Kommentar da. Was er nicht
    # darf, ist eine **Zeile** daraus machen: PrusaSlicer liest nur Zeilen als
    # Einstellungen, und keine beginnt mit ``post_process``.
    assert not any(line.startswith("post_process") for line in lines)
    assert lines[0].startswith("# "), "der Titel bleibt ein Kommentar"
    assert lines[0].count("post_process") == 1, "und zwar in einer einzigen Zeile"
    assert all(line.startswith("#") or " = " in line for line in lines if line), (
        "keine Zeile, die weder Kommentar noch Zuweisung ist"
    )


@pytest.mark.parametrize("destination", ["slicer", "export"])
def test_a_line_break_in_a_setting_value_is_refused(tmp_path: Path, destination: str) -> None:
    """Werte werden abgelehnt, nicht bereinigt (Regel 21).

    Einen Wert stillschweigend zu ändern hieße, eine Druckeinstellung zu
    verändern, ohne es zu sagen — und für einen Umbruch in einem Slicer-Wert
    ist nirgends zugesagt, wie man ihn maskiert. Dieselbe Entscheidung wie
    beim Semikolon im Profilpfad.
    """
    profile = profiles.make_profile("prusa-mk4s", "pla")
    base = print_settings.resolve(profile)
    settings = replace(base, filament=replace(base.filament, colour="rot\nmachine_start_gcode = x"))
    setup = handover.SlicerSetup(executable=Path("PrusaSlicer.exe"), flavour="prusa")

    with pytest.raises(ExternalToolError) as caught:
        if destination == "slicer":
            handover.write_config(settings, profile, setup, tmp_path)
        else:
            import trimesh

            from app.core.export import writer
            from app.core.geom.mesh import MeshData
            from app.core.types import SceneObject

            body = SceneObject("part", "Körper", MeshData.of(trimesh.creation.box((10, 10, 10))))
            writer.write_assembly(
                [body],
                tmp_path,
                project_name="Zeilengrenze",
                profile=profile,
                settings=settings,
                flavour="prusa",
                for_slicer=False,
                checked=[],
            )

    assert "filament_colour" in str(caught.value.values.get("setting", ""))
    assert caught.value.suggestions, "Regel 17: jede Ausnahme trägt einen Vorschlag"


def test_no_cura_key_passes_a_value_through_verbatim() -> None:
    """Keine Cura-Zuordnung leitet einen Wert unverändert durch.

    ``_mapped(table, "")`` fällt über ``fallback or str(value)`` auf den
    fremden Text zurück. ``adhesion_type`` war die einzige Stelle der
    Cura-Tabelle, an der ein Wert aus der Projektdatei so wörtlich in ein
    ``-s``-Argument gelangte; jetzt ist die Abbildung eine Positivliste.
    """
    fremd = "skirt\nmachine_start_gcode = beliebiger G-Code"
    durchgeleitet = []
    for row in slicer_keys.CURA:
        try:
            umgewandelt = row[2](fremd)
        except TypeError, ValueError:
            # Ein Zahlenwandler lehnt einen Text ohnehin ab — das ist die
            # strengere Antwort und genau die gewünschte.
            continue
        if umgewandelt == fremd:
            durchgeleitet.append(row[1])

    assert not durchgeleitet, (
        f"diese Cura-Schlüssel leiten einen fremden Wert wörtlich durch: {durchgeleitet}"
    )


def test_an_orca_process_keeps_what_the_base_profile_knew(tmp_path: Path) -> None:
    """Die Orca-Familie prüft Verträglichkeit gegen den Drucker. Was Solidon
    nicht anfasst, muss deshalb stehen bleiben."""
    base = tmp_path / "base.json"
    base.write_text(
        json.dumps(
            {
                "type": "process",
                "name": "0.20mm Standard",
                "compatible_printers": ["Irgendein Drucker 0.4 nozzle"],
                "wall_loops": "2",
            }
        ),
        encoding="utf-8",
    )
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(
        executable=Path("orca-slicer.exe"), flavour="orca", base_process=str(base)
    )

    written = handover.write_config(settings, profile, setup, tmp_path)
    document = json.loads(written.process.read_text(encoding="utf-8"))

    assert document["compatible_printers"] == ["Irgendein Drucker 0.4 nozzle"]
    # Solidons Stufe sagt drei Wände, der Hersteller zwei — und ohne eigene
    # Wahl gilt der Hersteller (Konzept Herstellerprofil, Entscheidung D).
    assert document["wall_loops"] == "2"
    chosen = print_settings.with_choice(settings, "shell.wall_count", 4)
    (tmp_path / "wahl").mkdir()
    again = handover.write_config(chosen, profile, setup, tmp_path / "wahl")
    assert json.loads(again.process.read_text(encoding="utf-8"))["wall_loops"] == "4"
    # Was ins Filamentprofil gehört, hat im Prozessprofil nichts verloren —
    # dort liest der Slicer es nicht.
    assert "nozzle_temperature" not in document
    assert "hot_plate_temp" not in document


def _two_plate_scene() -> object:
    """Eine Szene mit zwei Platten: rot allein, dann weiß und rot."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene.evaluate import EvaluationResult
    from app.core.types import MaterialSlot, Scene, SceneObject

    def body(name: str, plate: int, slots: tuple[MaterialSlot, ...]) -> SceneObject:
        mesh = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
        mesh.apply_translation((0.0, 0.0, 10.0))
        return SceneObject(
            id=name, name=name, mesh=MeshData.of(mesh), plate=plate, material_slots=slots
        )

    rot = MaterialSlot(index=0, name="Rot", colour=(1.0, 0.0, 0.0))
    weiss = MaterialSlot(index=0, name="Weiss", colour=(1.0, 1.0, 1.0))
    return EvaluationResult(
        scene=Scene(
            objects={
                "a": body("a", 0, (rot,)),
                "b": body("b", 1, (weiss,)),
                "c": body("c", 1, (rot,)),
            }
        )
    )


def test_the_plate_choice_appears_and_narrows_what_gets_sliced(qt_app: object) -> None:
    """Die Wahl erscheint nur, wenn es etwas zu wählen gibt — und sie wirkt.

    Beides in einem Test, und das ist eine Entscheidung gegen den üblichen
    Zuschnitt „ein Test, eine Zusage": Zwei Tests bauen zwei Dialoge, und der
    zweite riss die Datei in eine Zugriffsverletzung (Position 57, im Abbau
    von ``_no_worker_outlives_its_window``). Gemessen am 26.08.2026 — ohne
    einen der beiden lief die Datei grün, mit beiden dreimal von dreimal
    nicht, und ein trivialer 75. Test an derselben Stelle war folgenlos. Es
    ist also nicht die Zahl, sondern dieser Dialog ein zweites Mal.

    Das ist die bekannte Mine aus ``conftest.py`` — die Zerstörung eines
    Fensters mit Ansicht mitten in der Suite, gemessen unter VTK —, kein
    eigener Fehler und hier nicht zu beheben. Ihr wird ausgewichen, und das
    steht hier, damit
    der Nächste den Test trennen kann, sobald sie entschärft ist, statt sich
    über den Zuschnitt zu wundern.

    **Die Zusagen selbst:** Bei einer Platte bleibt die Zeile verborgen — eine
    Wahl ohne Alternative ist keine, und der Kunde liest sie doch. Ab der
    zweiten erscheint sie mit „Alle Platten" als Vorgabe, denn das ist der
    bisherige Weg. Und die Wahl wirkt auf beides: den Lauf und die Spulen, die
    er braucht. Solange ``_plate_slots`` fest die erste Platte nahm, ordnete
    der Kunde Filamente einer Platte zu, die er gar nicht slicte.
    """
    from app.ui.print_settings_dialog import PrintSettingsDialog
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    dialog = PrintSettingsDialog(Session(), UiSettings())
    assert dialog.plate_row.isHidden(), "leere Szene: keine Wahl"

    dialog.session.last_result = _two_plate_scene()  # type: ignore[assignment]
    dialog._refresh_plates()

    # ``isHidden`` und nicht ``isVisible``: Letzteres antwortet ``False``,
    # solange der Dialog nicht angezeigt wurde, und zwar für jedes Widget.
    assert not dialog.plate_row.isHidden(), "zwei Platten: jetzt gibt es etwas zu wählen"
    assert dialog.plate_choice.count() == 3, "die Sammelzeile und zwei einzelne"
    assert dialog.plate_choice.currentData() is None, "Vorgabe ist die Sammelzeile"
    assert dialog._chosen_plates() == [0, 1], "und die umfasst beide"

    # Platte 1 trägt nur Rot, Platte 2 trägt Weiß und Rot.
    dialog.plate_choice.setCurrentIndex(1)
    assert dialog._chosen_plates() == [0]
    assert [slot.name for slot in dialog._plate_slots()] == ["Rot"]

    dialog.plate_choice.setCurrentIndex(2)
    assert dialog._chosen_plates() == [1]
    assert sorted(slot.name for slot in dialog._plate_slots()) == ["Rot", "Weiss"]

    # Und zurück auf „Alle": beide Platten, alle Spulen.
    dialog.plate_choice.setCurrentIndex(0)
    assert dialog._chosen_plates() == [0, 1]
    assert sorted(slot.name for slot in dialog._plate_slots()) == ["Rot", "Weiss"]


def test_each_slot_can_carry_its_own_spool_settings(tmp_path: Path) -> None:
    """Vier Spulen sind nicht vier Farben desselben Materials (§20).

    Ein Schriftzug in PLA auf einem Gehäuse aus PETG fährt 210 Grad statt 250.
    Solange alle Slots die Werte des Projektmaterials bekamen, verkohlte
    entweder die Schrift oder das Gehäuse hielt nicht — und zu sehen war es
    erst am fertigen Druck.

    Geprüft wird an der Datei, die der Slicer lädt, nicht am Modell: Ein
    Übersteuerer, der die Übergabe nicht erreicht, ist folgenlos.
    """
    from dataclasses import replace

    from app.core.types import MaterialSlot, SlotOverride

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    assert settings.temperature.nozzle == 240, "das Projekt fährt PETG"

    schrift = replace(settings.temperature, nozzle=210, nozzle_first_layer=215, bed=60)
    settings = replace(
        settings,
        slot_overrides=(SlotOverride(name="Schrift", colour=(1.0, 1.0, 1.0), temperature=schrift),),
    )
    slots = (
        MaterialSlot(index=0, name="Gehäuse", colour=(0.1, 0.1, 0.1)),
        MaterialSlot(index=1, name="Schrift", colour=(1.0, 1.0, 1.0)),
    )
    setup = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")

    written = handover.write_config(settings, profile, setup, tmp_path, slots=slots)
    assert len(written.filaments) == 2, "je Slot eine Datei"

    gehaeuse = json.loads(written.filaments[0].read_text(encoding="utf-8"))
    schriftzug = json.loads(written.filaments[1].read_text(encoding="utf-8"))

    # Der Slot ohne eigene Werte bleibt beim Projekt …
    assert gehaeuse["nozzle_temperature"] == ["240"]
    assert gehaeuse["hot_plate_temp"] == ["80"]
    # … der mit eigenen fährt seine.
    assert schriftzug["nozzle_temperature"] == ["210"]
    assert schriftzug["nozzle_temperature_initial_layer"] == ["215"]
    assert schriftzug["hot_plate_temp"] == ["60"]


def test_a_spool_keeps_its_settings_when_the_order_changes(tmp_path: Path) -> None:
    """Die Werte gehören dem Filament, nicht dem Platz in einer Liste (§20).

    Der Dialog zeigt die Zusammenlegung der gewählten Platten; gedruckt wird
    Platte für Platte, und jede legt für sich zusammen. Bei Rot auf Platte 1
    und Weiß+Rot auf Platte 2 steht [Rot, Weiß] im Dialog und [Weiß, Rot] im
    Lauf der zweiten. Solange der Übersteuerer an der Position hing, bekam
    **Weiß die 210 Grad, die für Rot eingestellt waren** — gemessen am
    26.08.2026, und schwerer als derselbe Fehler bei den Filamentprofilen:
    Dort wandert die Temperatur mit dem Profil, hier *ist* sie der Wert. 210
    Grad auf ein PETG, das 240 braucht, geben einen Druck, der auseinanderfällt.
    """
    from dataclasses import replace

    from app.core.types import MaterialSlot, SlotOverride

    rot = MaterialSlot(index=0, name="Rot", colour=(1.0, 0.0, 0.0))
    weiss = MaterialSlot(index=1, name="Weiß", colour=(1.0, 1.0, 1.0))

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    kalt = replace(settings.temperature, nozzle=210)
    settings = replace(
        settings,
        slot_overrides=(SlotOverride(name="Rot", colour=(1.0, 0.0, 0.0), temperature=kalt),),
    )
    setup = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")

    # Die Reihenfolge des **Laufs**: Weiß zuerst, Rot danach — anders als im
    # Dialog, wo Rot oben stand.
    written = handover.write_config(settings, profile, setup, tmp_path, slots=(weiss, rot))

    erste = json.loads(written.filaments[0].read_text(encoding="utf-8"))
    zweite = json.loads(written.filaments[1].read_text(encoding="utf-8"))
    assert erste["nozzle_temperature"] == ["240"], "Weiß fährt das Projektmaterial"
    assert zweite["nozzle_temperature"] == ["210"], "Rot fährt seine eigenen Werte"


def test_a_slot_override_can_be_added_changed_and_removed() -> None:
    """Die Oberfläche braucht einen einzigen, identitätsfesten Schreibweg.

    Name und Farbe sind der Schlüssel. Würde der Wähler stattdessen an eine
    Listenposition schreiben, bekäme nach einer anderen Plattenauswahl wieder
    die falsche Spule die Temperatur.
    """
    from app.core.types import MaterialSlot, SlotOverride

    slot = MaterialSlot(index=3, name="PLA Weiß", colour=(1.0, 1.0, 1.0))
    settings = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "petg"))
    first = SlotOverride(name=slot.name, colour=slot.colour, temperature=settings.temperature)
    changed = SlotOverride(name=slot.name, colour=slot.colour, cooling=settings.cooling)

    settings = handover.with_slot_override(settings, slot, first)
    assert handover.override_for(settings, slot) == first

    settings = handover.with_slot_override(settings, slot, changed)
    assert settings.slot_overrides == (changed,), "ändern verdoppelt die Spule nicht"

    settings = handover.with_slot_override(settings, slot, None)
    assert handover.override_for(settings, slot) is None
    assert settings.slot_overrides == (), "Projektwerte brauchen keinen leeren Eintrag"


def test_the_slicers_that_cap_the_flow_themselves_take_the_limit() -> None:
    """Wer das Tempo selbst nach dem Volumenstrom deckelt, braucht den Wert:
    PrusaSlicer und die Orca-Familie bekommen ihn als
    ``filament_max_volumetric_speed``. Cura liest ihn nicht, dort bleibt der
    Deckel als Vorschlag der einzige (Gesamtprüfung, 27.09.2026)."""
    for flavour in ("orca", "prusa", "cura", "other"):
        caps = slicer_keys.caps_volumetric_speed(flavour)
        assert caps == (flavour in ("orca", "prusa")), flavour
        if caps:
            assert slicer_keys.takes(flavour, "filament.max_flow"), flavour


def test_a_slicer_that_takes_one_filament_says_so() -> None:
    """Was ein Slicer nicht entgegennimmt, wird gesagt — nicht verschwiegen.

    Nur die Orca-Familie lädt ein Filamentprofil je Slot. PrusaSlicer bekommt
    eine ``.ini`` und ``CuraEngine`` einen Satz Schlüssel; die Werte der
    zweiten Spule fallen dort weg. Still wäre das der schlechteste Fall: Der
    Kunde sieht seine Einstellung im Dialog stehen und bekommt einen Druck,
    der sie nicht verwendet.
    """
    from dataclasses import replace

    from app.core.types import SlotOverride

    settings = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "petg"))
    eigen = replace(settings.temperature, nozzle=210)
    mit = replace(settings, slot_overrides=(SlotOverride(name="Rot", temperature=eigen),))

    for flavour in ("prusa", "cura"):
        setup = handover.SlicerSetup(executable=Path("slicer.exe"), flavour=flavour)
        findings = handover.unreachable_overrides(mit, setup)
        assert len(findings) == 1, f"{flavour}: der Kunde erfährt es"
        assert findings[0].severity == "warning", "kein Fehler — der Slicer kann nicht mehr"
        # Regel 17: nie mit „fehlgeschlagen" enden, sondern mit einem Weg.
        assert "Orca" in str(findings[0].message), "und wo er es bekäme"

    # Die Orca-Familie nimmt sie an, also gibt es nichts zu melden.
    orca = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")
    assert handover.unreachable_overrides(mit, orca) == []

    # Und ohne eigene Werte schweigt auch Prusa — eine Warnung ohne Anlass
    # ist schlimmer als keine.
    prusa = handover.SlicerSetup(executable=Path("slicer.exe"), flavour="prusa")
    assert handover.unreachable_overrides(settings, prusa) == []
    leer = replace(settings, slot_overrides=(SlotOverride(name="Rot"),))
    assert handover.unreachable_overrides(leer, prusa) == []


@pytest.mark.parametrize("flavour", ["prusa", "cura"])
@pytest.mark.parametrize("different_colour", [False, True])
def test_two_filaments_with_equal_print_values_still_report_the_lost_spool(
    flavour: handover.SlicerFlavour, different_colour: bool
) -> None:
    """Zwei PLA-Spulen verschwinden auch bei gleichen Temperaturen nicht aus der Warnung."""
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.resolve(profile)
    first = MaterialSlot(0, "PLA Orange", (177 / 255, 99 / 255, 10 / 255), None, "PLA")
    second = replace(
        first,
        index=1,
        name="Zweite PLA-Spule",
        colour=(1.0, 1.0, 1.0) if different_colour else first.colour,
    )
    setup = handover.SlicerSetup(executable=Path("slicer.exe"), flavour=flavour)

    findings = handover.unreachable_overrides(settings, setup, (first, second), profile=profile)

    assert [finding.code for finding in findings] == ["slicer.overrides_unreachable"]
    assert findings[0].values["slots"] == 1
    assert not handover.unreachable_overrides(settings, setup, (second,), profile=profile)
    assert not handover.unreachable_overrides(
        settings, setup, (first, replace(first, index=1)), profile=profile
    ), "zwei Körper mit derselben Spule sind kein Mehrfilamentauftrag"


def test_a_single_profile_slicer_uses_the_first_filaments_values(tmp_path: Path) -> None:
    """Ein Satz heißt erster Extruder, nicht Projektwert trotz eigener Wahl.

    PrusaSlicer und CuraEngine können auf diesem Weg keine zwei Filamentprofile
    laden. Den ersten Satz können sie sehr wohl übernehmen; ihn ebenfalls zu
    verwerfen und zugleich nur zu warnen wäre unnötiger Datenverlust.
    """
    from app.core.types import MaterialSlot, SlotOverride

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    first = MaterialSlot(index=0, name="PLA Weiß", colour=(1.0, 1.0, 1.0))
    second = MaterialSlot(index=1, name="PETG Rot", colour=(1.0, 0.0, 0.0))
    pla = replace(settings.temperature, nozzle=210)
    petg = replace(settings.temperature, nozzle=245)
    settings = replace(
        settings,
        slot_overrides=(
            SlotOverride(name=first.name, colour=first.colour, temperature=pla),
            SlotOverride(name=second.name, colour=second.colour, temperature=petg),
        ),
    )
    setup = handover.SlicerSetup(executable=Path("prusa-slicer.exe"), flavour="prusa")

    written = handover.write_config(settings, profile, setup, tmp_path, slots=(first, second))
    text = written.process.read_text(encoding="utf-8")

    assert "temperature = 210" in text, "der erreichbare erste Satz kommt an"
    findings = handover.unreachable_overrides(settings, setup, (first, second))
    assert len(findings) == 1
    assert findings[0].values["slots"] == 1, "nur die zweite Spule ist unerreichbar"
    assert handover.unreachable_overrides(settings, setup, (first,)) == []


def test_a_slot_override_survives_the_project_file(tmp_path: Path) -> None:
    """Was der Kunde je Spule einstellt, steht beim nächsten Öffnen noch da.

    Ohne diesen Weg wäre die Übersteuerung eine Sitzungseinstellung: einmal
    gesetzt, beim Speichern verloren, und der zweite Druck desselben Projekts
    liefe wieder mit den Werten des Projektmaterials.
    """
    from dataclasses import replace

    from app.core.scene import serialise
    from app.core.types import SlotOverride

    settings = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "petg"))
    eigen = replace(settings.temperature, nozzle=210)
    settings = replace(
        settings,
        slot_overrides=(SlotOverride(name="Rot", colour=(1.0, 0.0, 0.0), temperature=eigen),),
    )

    # Durch JSON hindurch, nicht nur durch die beiden Funktionen: Ein Wert,
    # den ``json.dumps`` nicht schreiben kann, fiele sonst nicht auf.
    zurueck = serialise.print_settings_from_data(
        json.loads(json.dumps(serialise.print_settings_to_data(settings)))
    )
    assert zurueck.slot_overrides == settings.slot_overrides

    # Ein Slot ohne eigene Werte steht als ``null`` da und nicht als vier
    # leere Gruppen, die vortäuschen, jemand hätte etwas eingestellt.
    daten = serialise.print_settings_to_data(settings)
    # Die Identität reist mit — ohne sie fände der Übersteuerer sein Filament
    # beim nächsten Öffnen nicht wieder.
    assert daten["slot_overrides"][0]["name"] == "Rot"
    assert daten["slot_overrides"][0]["colour"] == [1.0, 0.0, 0.0]
    assert set(daten["slot_overrides"][0]) == {
        "name",
        "colour",
        "material",
        "material_type",
        "temperature",
    }

    # Und eine Datei ohne das Feld öffnet weiterhin — der Normalfall bei
    # jedem Projekt, das vor dieser Fassung entstanden ist.
    alt = serialise.print_settings_to_data(settings)
    del alt["slot_overrides"]
    assert serialise.print_settings_from_data(alt).slot_overrides == ()


def test_the_handover_kind_travels_with_the_project() -> None:
    """§29 wörtlich: Die Übergabeart wird je Projekt gemerkt — sie reist in
    den Druckeinstellungen. Eine ältere Datei ohne das Feld bleibt auf
    „slice", dem bisher einzigen Weg, und ein fremder Wert fällt dorthin
    zurück, statt bis in die Knopfleiste zu reisen."""
    from dataclasses import replace

    from app.core.scene import serialise

    settings = replace(print_settings.resolve(profiles.make_profile()), handover="open")

    zurueck = serialise.print_settings_from_data(
        json.loads(json.dumps(serialise.print_settings_to_data(settings)))
    )
    assert zurueck.handover == "open"

    alt = serialise.print_settings_to_data(settings)
    del alt["handover"]
    assert serialise.print_settings_from_data(alt).handover == "slice"
    assert serialise.print_settings_from_data({"handover": "quatsch"}).handover == "slice"


def test_the_orca_machine_profile_is_written_out_not_referenced(tmp_path: Path) -> None:
    """Solidon schreibt das Maschinenprofil aus, statt auf eines zu verweisen.

    Bisher bekam der Slicer den **Namen** eines Profils aus seinem Bestand
    und löste alles Weitere selbst auf. Gemessen am Elegoo-Bestand stehen in
    ``Elegoo Centauri 0.2 nozzle`` sechzehn Schlüssel und im Lauf
    dreiundachtzig — die übrigen siebenundsechzig kamen aus einer Erbkette,
    die dem Slicer gehört.

    Der Anfahrcode ist dabei der Prüfstein: Er steht nie in der obersten
    Datei, sondern immer eine Stufe tiefer. Kommt er hier an, ist die Kette
    aufgelöst; fehlt er, fährt der Drucker ohne Bettvermessung los.
    """
    wurzel = tmp_path / "fdm_machine_common.json"
    wurzel.write_text(
        json.dumps(
            {
                "type": "machine",
                "name": "fdm_machine_common",
                "machine_start_gcode": "G28 ;Startpunkt anfahren",
                "printable_height": "256",
                "retraction_length": ["0.8"],
            }
        ),
        encoding="utf-8",
    )
    oben = tmp_path / "Drucker 0.4 nozzle.json"
    oben.write_text(
        json.dumps(
            {
                "type": "machine",
                "name": "Drucker 0.4 nozzle",
                "inherits": "fdm_machine_common",
                "nozzle_diameter": ["0.4"],
            }
        ),
        encoding="utf-8",
    )
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(
        executable=Path("orca-slicer.exe"),
        flavour="orca",
        machine_profile=str(oben),
    )
    written = handover.write_config(settings, profile, setup, tmp_path)

    assert written.machine is not None, "die Übergabe trägt ein Maschinenprofil"
    document = json.loads(written.machine.read_text(encoding="utf-8"))
    # Der geerbte Anfahrcode — der Grund für die ganze Auflösung.
    assert document["machine_start_gcode"] == "G28 ;Startpunkt anfahren"
    assert document["retraction_length"] == ["0.8"], "auch der geerbte Rückzug"
    assert document["nozzle_diameter"] == ["0.4"], "und der eigene Wert der Stufe"
    # Nichts wird nachgeladen: Was in der Datei steht, gilt.
    assert "inherits" not in document, "ausgeschrieben, nicht verwiesen"
    assert document["from"] == "system", (
        "ElegooSlicer ordnet ein User-Maschinenprofil keinem Prozessprofil zu"
    )
    assert document["name"].startswith("Solidon"), "und es ist Solidons Datei"


def test_the_orca_process_names_the_machine_solidon_wrote(tmp_path: Path) -> None:
    """Prozess und Maschine tragen denselben Namen — sonst nimmt der Slicer nichts.

    Die Orca-Familie bricht mit „process not compatible with printer" ab,
    bevor sie das Modell ansieht. Solange die Bindung geerbt war, hielt sie
    ``inherits``; da die Werte jetzt ausgeschrieben sind, setzt Solidon sie
    selbst — und beide Namen kommen aus derselben Funktion.
    """
    maschine = tmp_path / "Drucker 0.4 nozzle.json"
    maschine.write_text(
        json.dumps({"type": "machine", "name": "Drucker 0.4 nozzle", "printable_height": "256"}),
        encoding="utf-8",
    )
    prozess = tmp_path / "0.20mm Standard.json"
    prozess.write_text(
        json.dumps(
            {
                "type": "process",
                "name": "0.20mm Standard",
                "compatible_printers": ["Ein ganz anderer Drucker"],
                "wall_loops": "2",
            }
        ),
        encoding="utf-8",
    )
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(
        executable=Path("orca-slicer.exe"),
        flavour="orca",
        machine_profile=str(maschine),
        base_process=str(prozess),
    )
    written = handover.write_config(settings, profile, setup, tmp_path)

    assert written.machine is not None
    maschinendatei = json.loads(written.machine.read_text(encoding="utf-8"))
    prozessdatei = json.loads(written.process.read_text(encoding="utf-8"))
    assert prozessdatei["compatible_printers"] == [maschinendatei["name"]], (
        "der Prozess nennt die Maschine, die daneben geschrieben wurde"
    )
    assert prozessdatei["from"] == maschinendatei["from"] == "system", (
        "nur dieselbe CLI-Kategorie nimmt die Bindung als verträglich an"
    )
    # Und nicht mehr die des Herstellers: Sie zeigte auf ein Profil aus
    # seinem Bestand, das hier gar nicht mitgeliefert wird.
    assert prozessdatei["compatible_printers"] != ["Ein ganz anderer Drucker"]


def test_the_orca_filament_profile_carries_what_hangs_on_the_filament(tmp_path: Path) -> None:
    """Temperatur, Kühlung und Rückzug gehören ins Filamentprofil.

    Standen sie im Prozessprofil, übernahm der Slicer sie nicht — geräuschlos,
    und gedruckt wurde mit dem, was zuletzt bei ihm eingestellt war.
    """
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")

    written = handover.write_config(settings, profile, setup, tmp_path)
    assert written.filament is not None
    document = json.loads(written.filament.read_text(encoding="utf-8"))

    assert document["type"] == "filament"
    assert document["filament_type"] == [slicer_keys.filament_type(profile.material.id)]
    # Werte stehen dort als Liste, ein Eintrag je Platz. Ein blanker String
    # wird nicht angenommen.
    assert document["nozzle_temperature"] == [str(settings.temperature.nozzle)]
    assert document["hot_plate_temp"] == [str(settings.temperature.bed)]
    assert document["filament_retraction_length"] == [f"{settings.retraction.length:g}"]
    meta = {"type", "name", "from", "instantiation"}
    assert all(isinstance(value, list) for key, value in document.items() if key not in meta)


def test_the_filament_profile_keeps_what_the_maker_knows(tmp_path: Path) -> None:
    """Solidon legt seine Werte auf das Profil des Herstellers, statt eines zu
    erfinden — und löst dessen Erbkette vorher auf.

    Der Unterschied ist keiner der Feinheit: ein Filamentprofil bei Elegoo
    setzt selbst drei Werte und erbt zweiundfünfzig. Ohne Auflösung stünde in
    der Übergabe ein Bruchstück, und der Slicer ergänzte den Rest aus dem, was
    zufällig eingestellt war.
    """
    root = tmp_path / "filament"
    root.mkdir()
    (root / "grund.json").write_text(
        json.dumps(
            {
                "type": "filament",
                "name": "Hersteller PETG @base",
                "filament_density": ["1.27"],
                "pressure_advance": ["0.04"],
                "nozzle_temperature": ["999"],
            }
        ),
        encoding="utf-8",
    )
    besonders = root / "besonders.json"
    besonders.write_text(
        json.dumps(
            {
                "type": "filament",
                "name": "Hersteller PETG Transluzent",
                "inherits": "Hersteller PETG @base",
                "instantiation": "true",
                "temperature_vitrification": ["70"],
            }
        ),
        encoding="utf-8",
    )
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(
        executable=Path("orca-slicer.exe"), flavour="orca", base_filament=str(besonders)
    )

    written = handover.write_config(settings, profile, setup, tmp_path)
    assert written.filament is not None
    document = json.loads(written.filament.read_text(encoding="utf-8"))

    assert document["pressure_advance"] == ["0.04"], "geerbt, und Solidon kennt es gar nicht"
    assert document["temperature_vitrification"] == ["70"], "eigener Wert des Profils"
    # Wo beide etwas sagen, gewinnt Solidon: die Einstellung ist die
    # Entscheidung des Nutzers, das Profil nur die Unterlage.
    assert document["nozzle_temperature"] == [str(settings.temperature.nozzle)]
    # Und der Name sagt, welche Spule gemeint ist. „Solidon Standard — PETG"
    # stand einmal über Werten von Elegoo PETG PRO — richtig gerechnet, falsch
    # beschriftet: wer die Druckdatei später liest, legt die falsche Rolle ein.
    assert document["name"] == "Solidon besonders", "der Name nennt das gewählte Profil"


def test_the_orca_call_loads_the_filament_profile(tmp_path: Path) -> None:
    """Ein eigener Schalter, nicht ``--load-settings``: dorthin gegeben würde
    das Filamentprofil nach seinem ``type`` aussortiert statt geladen."""
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")

    config = handover.write_config(settings, profile, setup, tmp_path)
    command = handover._command(setup, [tmp_path / "teil.stl"], config, tmp_path)

    assert "--load-filaments" in command
    assert command[command.index("--load-filaments") + 1] == str(config.filament)
    assert str(config.filament) not in command[command.index("--load-settings") + 1]


def _profile_keys(root: Path, kind: str) -> set[str]:
    """Alle Schlüssel, die der Bestand eines Slicers unter dieser Art führt."""
    found: set[str] = set()
    for path in (root / kind).rglob("*.json"):
        try:
            loaded = json.loads(path.read_text(encoding="utf-8"))
        except OSError, ValueError:
            continue
        if isinstance(loaded, dict):
            found |= set(loaded)
    return found


def _installed_orca_profiles() -> Path | None:
    """Der Profilbestand eines installierten Slicers der Orca-Familie."""
    for base in (Path("C:/Program Files"), Path("/usr/share"), Path("/opt")):
        if not base.is_dir():
            continue
        for folder in base.iterdir():
            root = folder / "resources" / "profiles"
            if not root.is_dir():
                continue
            for vendor in root.iterdir():
                if (vendor / "filament").is_dir() and (vendor / "process").is_dir():
                    return vendor
    return None


def test_every_orca_setting_sits_in_the_profile_it_claims() -> None:
    """Die Probe aufs Exempel: stimmt die Zuordnung gegen einen echten Bestand?

    Ein Wert im falschen Profil wird von der Orca-Familie stillschweigend
    übergangen. Genau das war lange der Fall — vierzehn Filamentwerte und der
    Rückzug standen im Prozessprofil und kamen nie an. Auffallen konnte es
    nicht, weil kein Test die Aufteilung kannte.
    """
    root = _installed_orca_profiles()
    if root is None:
        pytest.skip("kein Slicer der Orca-Familie installiert")

    known = {kind: _profile_keys(root, kind) for kind in ("process", "filament", "machine")}
    misplaced: list[str] = []
    for entry in slicer_keys.TABLES["orca"]:
        found = [kind for kind, keys in known.items() if entry.key in keys]
        if found and entry.section not in found:
            misplaced.append(f"{entry.key}: laut Tabelle {entry.section}, laut Slicer {found}")
    assert not misplaced, "Werte im falschen Profil:\n  " + "\n  ".join(misplaced)


def _cura_definitions() -> dict[str, dict[str, object]] | None:
    """Curas Einstellungsdefinition aus einer Installation, flach gelesen.

    Sie liegt neben jeder ``CuraEngine`` und nennt jeden gültigen Schlüssel,
    seine Einheit und seinen Vorgabewert. Das ist die einzige Auskunft
    darüber, ob eine Zuordnung trifft — und sie kommt vom Programm selbst,
    nicht aus einer Dokumentation, die für die installierte Version gelten mag
    oder nicht. Bei Prusa und Orca leistet das die Gegenprobe im G-Code; bei
    Cura kann sie es nicht, weil dort keine Einstellung in der Druckdatei
    steht.
    """
    flat: dict[str, dict[str, object]] = {}

    def walk(node: dict[str, object]) -> None:
        for key, value in node.items():
            if isinstance(value, dict):
                flat[key] = value
                children = value.get("children")
                if isinstance(children, dict):
                    walk(children)

    found = False
    for base in (Path("C:/Program Files"), Path("/usr/share"), Path("/opt")):
        if not base.is_dir():
            continue
        for folder in base.iterdir():
            for definitions in (
                folder / "share" / "cura" / "resources" / "definitions",
                folder / "resources" / "definitions",
            ):
                for name in ("fdmprinter.def.json", "fdmextruder.def.json"):
                    path = definitions / name
                    if not path.is_file():
                        continue
                    try:
                        loaded = json.loads(path.read_text(encoding="utf-8"))
                    except OSError, ValueError:
                        continue
                    settings = loaded.get("settings")
                    if isinstance(settings, dict):
                        walk(settings)
                        found = True
    return flat if found else None


def test_every_cura_key_exists_in_the_definition() -> None:
    """Ein Schlüssel, den Cura nicht kennt, wird stillschweigend verworfen.

    Genau das geschah mit ``outer_inset_first``: den Namen kennt Cura 5 nicht
    mehr, er heißt dort ``inset_direction``. Der Wert war geschrieben,
    gemessen wurde nichts davon — null von fünfzig Lagen begannen außen.
    Auffallen konnte es nicht, weil die Gegenprobe bei Cura nichts findet:
    ``CuraEngine`` schreibt seine Einstellungen nicht in die Druckdatei.
    """
    known = _cura_definitions()
    if known is None:
        pytest.skip("keine Cura-Installation, deren Definition sich lesen ließe")

    profile = profiles.make_profile()
    written = handover.values_for(print_settings.resolve(profile), profile, "cura")
    unknown = sorted(key for key in written if key not in known)
    assert not unknown, "Schlüssel, die Cura nicht kennt: " + ", ".join(unknown)


def test_nothing_cura_derives_is_left_to_its_default() -> None:
    """Die Gegenprobe zur Ableitungsstufe — und der Grund, warum es sie gibt.

    ``CuraEngine`` löst keine Vererbung auf: was Solidon schreibt, erreicht
    die abgeleiteten Schlüssel nicht, und die bleiben bei ihrem Vorgabewert.
    Gemessen an einem 20-mm-Würfel kostete das 1100 mm Filament statt 818.

    Geprüft wird beides: dass nichts offen bleibt, und dass keine Ausnahme in
    ``CURA_UNTOUCHED`` steht, die es nicht mehr braucht. Eine Liste, die nur
    wächst, erklärt am Ende nichts mehr.
    """
    known = _cura_definitions()
    if known is None:
        pytest.skip("keine Cura-Installation, deren Definition sich lesen ließe")

    # Die belegte Beschleunigung erreicht auch ihren abgeleiteten Prime-Tower-Wert.
    profile = profiles.make_profile("sovol-sv06", "pla")
    written = handover.values_for(print_settings.resolve(profile), profile, "cura")
    derived: set[str] = set()
    frontier, seen = set(written), set(written)
    while frontier:
        found = set()
        for key, spec in known.items():
            if key in seen:
                continue
            formula = spec.get("value")
            if not isinstance(formula, str):
                continue
            if any(re.search(rf"\b{re.escape(source)}\b", formula) for source in frontier):
                found.add(key)
                derived.add(key)
        seen |= found
        frontier = found

    open_ended = sorted(derived - set(slicer_keys.CURA_UNTOUCHED))
    assert not open_ended, "bleibt auf Curas Vorgabe stehen: " + ", ".join(open_ended)
    stale = sorted(set(slicer_keys.CURA_UNTOUCHED) - derived)
    assert not stale, "in CURA_UNTOUCHED, aber ohne Anlass: " + ", ".join(stale)


def test_a_key_cura_does_not_know_becomes_a_finding(tmp_path: Path) -> None:
    """Was der Gegenprobe bei Cura fehlt, holt die Definition nach.

    ``CuraEngine`` schreibt seine Einstellungen nicht in die Druckdatei —
    ``verify`` findet dort null von den geschriebenen Schlüsseln wieder. Ein
    Name, den diese Version nicht kennt, wird stillschweigend verworfen; die
    Definition daneben ist die einzige Stelle, an der es auffallen kann.
    """
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    engine = tmp_path / "CuraEngine.exe"
    engine.write_bytes(b"")
    setup = handover.SlicerSetup(executable=engine, flavour="cura")

    # Eine Definition, die alles kennt außer einem — so ist der Befund genau
    # der eine und nicht eine Liste von zweihundert.
    written = sorted(handover.values_for(settings, profile, "cura"))
    dropped = written[0]
    definitions = tmp_path / "share" / "cura" / "resources" / "definitions"
    definitions.mkdir(parents=True)
    (definitions / "fdmprinter.def.json").write_text(
        json.dumps(
            {"settings": {"alles": {"children": {key: {} for key in written[1:]}}}},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    findings = handover.unknown_keys(settings, profile, setup)

    assert findings and findings[0].code == "slicer.unknown_key"
    assert findings[0].values["count"] == 1
    assert findings[0].values["settings"] == dropped


def test_without_a_definition_nothing_is_claimed(tmp_path: Path) -> None:
    """Liegt keine Definition da, läuft der Slicer aus einem Paket, dessen
    Aufbau Solidon nicht kennt — dann wird auch nichts behauptet."""
    engine = tmp_path / "CuraEngine.exe"
    engine.write_bytes(b"")
    profile = profiles.make_profile()
    setup = handover.SlicerSetup(executable=engine, flavour="cura")

    assert not handover.unknown_keys(print_settings.resolve(profile), profile, setup)


def test_a_missing_model_says_so_before_starting_anything(tmp_path: Path) -> None:
    profile = profiles.make_profile()
    setup = handover.SlicerSetup(executable=Path("PrusaSlicer.exe"), flavour="prusa")

    with pytest.raises(ExternalToolError) as raised:
        handover.slice_model(
            tmp_path / "gibtesnicht.stl", print_settings.resolve(profile), profile, setup
        )
    assert raised.value.suggestions


def test_a_slicer_that_moved_away_points_at_the_extra_programs(tmp_path: Path) -> None:
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    profile = profiles.make_profile()
    setup = handover.SlicerSetup(executable=tmp_path / "weg.exe", flavour="prusa")

    with pytest.raises(ExternalToolError) as raised:
        handover.slice_model(model, print_settings.resolve(profile), profile, setup)
    assert any(action.id == "install" for action in raised.value.suggestions)


class _Finished:
    """Ein Slicerlauf, der zurückkam, ohne etwas zu schreiben."""

    def __init__(self, output: bytes) -> None:
        self.returncode = 0
        self.stdout = output
        self.stderr = b""


def _slicer_saying(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, output: bytes
) -> tuple[Path, handover.SlicerSetup]:
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    executable = tmp_path / "prusa-slicer.exe"
    executable.write_bytes(b"")
    monkeypatch.setattr(handover, "_run_slicer", lambda *args, **kwargs: _Finished(output))
    return model, handover.SlicerSetup(executable=executable, flavour="prusa")


@pytest.mark.parametrize("returncode", [0, 0xC0000409])
def test_a_plate_outside_the_volume_offers_arranging(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, returncode: int
) -> None:
    """Regel 17: Der Satz nennt die Ursache, und eine Handlung behebt sie.

    Gemessen an PrusaSlicer 2.9.6: Eine Platte in Bettkoordinaten — so kommt
    sie aus einer fremden 3MF — endet mit Rückgabewert 0 und dem Satz „All
    objects are outside of the print volume." Daraus wurde bisher „Der Slicer
    hat keine Druckdatei geschrieben", dazu drei Handlungen, von denen keine
    hilft. Was hilft, ist ein Klick auf *Auf dem Bett anordnen*.
    """
    profile = profiles.make_profile()
    model, setup = _slicer_saying(
        monkeypatch, tmp_path, b"All objects are outside of the print volume.\n"
    )
    monkeypatch.setattr(
        handover,
        "_run_slicer",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            args[0], returncode, b"All objects are outside of the print volume.\n", b""
        ),
    )

    with pytest.raises(ExternalToolError) as raised:
        handover.slice_model(model, print_settings.resolve(profile), profile, setup)

    assert "Bauraum" in str(raised.value), str(raised.value)
    assert any(action.id == "arrange_on_bed" for action in raised.value.suggestions)
    assert raised.value.values["output"], "die Ausgabe des Slicers bleibt lesbar"


@pytest.mark.parametrize("program", ["CrealityPrint.exe", "orca-slicer.exe"])
def test_an_empty_print_from_creality_says_what_the_family_says(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, program: str
) -> None:
    """Creality Print bekommt für „The print is empty" keine eigene Auskunft mehr.

    Bis 0.5.1 hieß es dort „Creality Print rechnet eine 3MF-Datei nur in
    seinem Fenster". Das stimmte nicht: Ohne ``extruder`` am Objekt ließ
    Creality Print 7.2 das Teil auf der Konsole ohne Werkzeug; mit ihm
    schneidet es Solidons 3MF samt Stützsperre und zwei Farben (RM-164,
    29.09.2026, ``test_every_object_names_its_tool_even_without_a_spool``).
    Sagt es den Satz trotzdem, gilt dieselbe Antwort wie für die Familie."""
    profile = profiles.make_profile()
    model = tmp_path / "platte.3mf"
    model.write_bytes(b"keine echte 3MF")
    executable = tmp_path / program
    executable.write_bytes(b"")
    finished = _Finished(
        b"The print is empty. The model is not printable with current print settings.\n"
    )
    finished.returncode = 0xFFFFFF9C
    monkeypatch.setattr(handover, "_run_slicer", lambda *args, **kwargs: finished)
    setup = handover.SlicerSetup(executable=executable, flavour="orca")

    with pytest.raises(ExternalToolError) as raised:
        handover.slice_model(model, print_settings.resolve(profile), profile, setup)

    assert "Im Slicer öffnen" not in str(raised.value), str(raised.value)
    assert str(raised.value.detail) == "Der Slicer hat keine Druckdatei geschrieben."
    assert raised.value.suggestions, "Regel 17"


def test_an_orca_refusal_for_parts_off_the_plate_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """KUNDE-09: Der Laptop-Ständer (205 × 272 mm) passt nicht auf den Centauri
    Carbon 2. Der ElegooSlicer lehnt mit -50 und „found error, exit" ab —
    gemessen auch halb und ganz neben der Platte und an einem zu langen
    Quader, jeweils mit ``--arrange 0``. Der Kunde las „Ein externes Programm
    hat nicht geantwortet" mit „Rückgabewert 4294967246". Jetzt: was los ist,
    und Teilen, Verkleinern, Anordnen als Knöpfe; die Zahl steht im
    Protokoll, nicht im Satz."""
    profile = profiles.make_profile()
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    executable = tmp_path / "elegoo-slicer.exe"
    executable.write_bytes(b"")
    finished = _Finished(b"Slic3r::CLI::run found error, exit\n")
    finished.returncode = 4294967246
    monkeypatch.setattr(handover, "_run_slicer", lambda *args, **kwargs: finished)
    setup = handover.SlicerSetup(executable=executable, flavour="orca")

    with pytest.raises(ExternalToolError) as raised:
        handover.slice_model(model, print_settings.resolve(profile), profile, setup)

    problem = raised.value
    assert "Druckplatte" in str(problem.detail)
    assert "nicht geantwortet" not in str(problem.title)
    assert {action.id for action in problem.suggestions} >= {"split_model", "scale_to_fit"}
    assert problem.values.get("exit_code") is None, "die Zahl gehört ins Protokoll"
    assert handover.signed_exit_code(4294967246) == -50


def test_bambus_refusal_in_its_result_file_reaches_the_slicer_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Bambu Studio sagt seine Absage nicht auf der Konsole, sondern in ``result.json``.

    Gemessen an Bambu Studio 2.3 (RM-163, Durchsicht 0.5.0): Ein Projekt für
    einen Drucker, den Bambu nicht kennt, endet mit Rückgabewert −17 und
    leerer Ausgabe; der Grund steht nur in der Datei neben der Druckdatei.
    Der Kunde las „Der Slicer hat keine Druckdatei geschrieben", und
    *Ausgabe des Slicers anzeigen* zeigte ein leeres Feld. Eine Datei aus
    einem früheren Lauf zählt nicht.
    """
    import os

    profile = profiles.make_profile()
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    executable = tmp_path / "bambu-studio.exe"
    executable.write_bytes(b"")
    reason = "The selected printer is not compatible with the process preset in the 3mf."
    output_dir = tmp_path / "ausgabe"
    output_dir.mkdir()
    stale = output_dir / "result.json"
    stale.write_text(json.dumps({"error_string": "alt", "return_code": -5}), encoding="utf-8")
    os.utime(stale, (1_000_000_000, 1_000_000_000))
    writes = {"reason": True}

    def run(command: list[str], *args: object, **kwargs: object) -> _Finished:
        target = Path(command[command.index("--outputdir") + 1])
        if writes["reason"]:
            (target / "result.json").write_text(
                json.dumps({"error_string": reason, "return_code": -17}), encoding="utf-8"
            )
        finished = _Finished(b"")
        finished.returncode = 0xFFFFFFEF
        return finished

    monkeypatch.setattr(handover, "_run_slicer", run)
    setup = handover.SlicerSetup(executable=executable, flavour="orca")

    with pytest.raises(ExternalToolError) as raised:
        handover.slice_model(
            model, print_settings.resolve(profile), profile, setup, output_dir=output_dir
        )
    assert reason in raised.value.values["output"]

    # Die Gegenprobe: Schreibt der Lauf nichts, bleibt die alte Datei stumm.
    os.utime(stale, (1_000_000_000, 1_000_000_000))
    stale.write_text(json.dumps({"error_string": "alt", "return_code": -5}), encoding="utf-8")
    os.utime(stale, (1_000_000_000, 1_000_000_000))
    writes["reason"] = False
    with pytest.raises(ExternalToolError) as raised:
        handover.slice_model(
            model, print_settings.resolve(profile), profile, setup, output_dir=output_dir
        )
    assert "alt" not in raised.value.values["output"]


def test_bambus_result_file_is_this_runs_or_none(tmp_path: Path) -> None:
    """Bambu Studio endet manchmal nicht nach seiner ``result.json`` — drei von
    rund hundert Läufen der Gesamtprüfung, auch auf gesunden Kernen
    (27.09.2026). Ob die Datei dieses Laufs da ist, zählt: nicht die eines
    älteren im selben Ordner, nicht eine halb geschriebene."""
    output_dir = tmp_path / "ausgabe"
    output_dir.mkdir()
    result = output_dir / "result.json"
    result.write_text(json.dumps({"return_code": 0}), encoding="utf-8")

    written = handover._result_written(output_dir)

    assert not written(), "die Datei eines älteren Laufs"
    result.write_text('{"return_code": ', encoding="utf-8")
    assert not written(), "halb geschrieben"
    result.write_text(json.dumps({"return_code": 0, "error_string": "Success."}), encoding="utf-8")
    assert written()
    assert not handover._result_written(tmp_path / "fehlt")()


def test_the_orca_family_is_asked_whether_its_result_is_there(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Anschluss: ``slice_model`` gibt dem Lauf der Orca-Familie die Frage
    nach ihrer ``result.json`` mit, und sie sagt erst ja, wenn der Lauf sie
    geschrieben hat (``process.run_limited`` beendet ihn dann nach einer
    Frist, statt bis zum Zeitlimit zu warten)."""
    profile = profiles.make_profile()
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    executable = tmp_path / "bambu-studio.exe"
    executable.write_bytes(b"")
    asked: list[bool] = []

    def run(command: list[str], *_args: object, **kwargs: object) -> _Finished:
        finished = kwargs.get("finished")
        assert callable(finished), "die Orca-Familie bekommt die Frage mit"
        asked.append(bool(finished()))
        target = Path(command[command.index("--outputdir") + 1])
        (target / "plate_1.gcode").write_text(_gcode_printing_at(-10.0, 10.0), encoding="utf-8")
        (target / "result.json").write_text(
            json.dumps({"return_code": 0, "error_string": "Success."}), encoding="utf-8"
        )
        asked.append(bool(finished()))
        return _Finished(b"")

    monkeypatch.setattr(handover, "_run_slicer", run)
    setup = handover.SlicerSetup(executable=executable, flavour="orca")

    outcome = handover.slice_model(
        model, print_settings.resolve(profile), profile, setup, output_dir=tmp_path / "out"
    )

    assert asked == [False, True]
    assert outcome.gcode_path.name == "plate_1.gcode"


def test_any_other_silence_keeps_the_old_answer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Gegenprobe. Die Orca-Familie verschluckt die Ursache — ihr CLI
    meldet nur „Slic3r::CLI::run found error, exit", und denselben Satz auch bei
    einem fehlenden Maschinenprofil. Daraus etwas über den Bauraum zu schließen
    wäre geraten.
    """
    profile = profiles.make_profile()
    model, setup = _slicer_saying(monkeypatch, tmp_path, b"Slic3r::CLI::run found error, exit\n")

    with pytest.raises(ExternalToolError) as raised:
        handover.slice_model(model, print_settings.resolve(profile), profile, setup)

    assert "Bauraum" not in str(raised.value), str(raised.value)
    assert not any(action.id == "arrange_on_bed" for action in raised.value.suggestions)
    assert any(action.id == "check_profile" for action in raised.value.suggestions)


def test_no_layers_points_at_the_model_instead_of_the_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """ElegooSlicer 1.5.3.4 benennt den Fall, und Solidon nutzt die Auskunft.

    Ein offener Würfel endete vorher bei „Maschinenprofil prüfen“. Das Profil
    hatte gerade einen gesunden Würfel geslicet; repariert werden muss das
    Modell, und die Ausgabe lässt offen, ob die Ursache eine Öffnung, ein zu
    dünner Körper oder eine falsche Einheit ist.
    """
    profile = profiles.make_profile()
    model, setup = _slicer_saying(
        monkeypatch,
        tmp_path,
        b"No layers were detected. You might want to repair your STL file(s).\n",
    )

    with pytest.raises(ExternalToolError) as raised:
        handover.slice_model(model, print_settings.resolve(profile), profile, setup)

    text = str(raised.value)
    assert "keine druckbaren Schichten" in text
    assert all(word in text for word in ("offene Stellen", "Einheit", "Wandstärke"))
    offered = {action.id for action in raised.value.suggestions}
    assert {"repair_and_retry", "show_locations"} <= offered
    assert "check_profile" not in offered, "der Slicer hat das Modell benannt, nicht das Profil"


def test_a_failed_run_offers_switching_the_slicer(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§2.1: Scheitert der eingestellte Slicer, ist der Wechsel der kürzeste
    Ausweg — auf dieser Maschine standen zwei arbeitende neben dem einen, der
    nicht wollte, und die Absage bot nur „Nur exportieren" an (30.08.2026).
    """
    profile = profiles.make_profile()
    model, setup = _slicer_saying(monkeypatch, tmp_path, b"Slic3r::CLI::run found error, exit\n")

    with pytest.raises(ExternalToolError) as raised:
        handover.slice_model(model, print_settings.resolve(profile), profile, setup)

    offered = [action.id for action in raised.value.suggestions]
    assert "choose_slicer" in offered
    assert offered.index("choose_slicer") == 0, "der Wechsel steht vorn, nicht hinter dem Export"


def test_window_program_finds_the_sibling_of_a_console(tmp_path: Path) -> None:
    """Die zweite Übergabeart (§29) braucht ein Fenster, und das liegt bei
    zwei Familien neben dem Konsolenprogramm — nur dort wird gesucht."""
    console = tmp_path / "prusa-slicer-console.exe"
    console.write_bytes(b"")
    window = tmp_path / "prusa-slicer.exe"
    window.write_bytes(b"")
    assert handover.window_program(console) == window

    engine = tmp_path / "CuraEngine.exe"
    engine.write_bytes(b"")
    cura = tmp_path / "Ultimaker-Cura.exe"
    cura.write_bytes(b"")
    assert handover.window_program(engine) == cura

    orca = tmp_path / "elegoo-slicer.exe"
    orca.write_bytes(b"")
    assert handover.window_program(orca) == orca, "die Orca-Familie ist ihr eigenes Fenster"


def test_open_in_slicer_without_a_window_offers_a_way_out(tmp_path: Path) -> None:
    """Eine CuraEngine ohne Cura daneben kann die Datei nicht zeigen — die
    Absage nennt den Wechsel und den Export, nicht nur das Scheitern."""
    engine = tmp_path / "CuraEngine.exe"
    engine.write_bytes(b"")
    model = tmp_path / "teil.3mf"
    model.write_bytes(b"x")
    setup = handover.SlicerSetup(executable=engine, flavour="cura")

    with pytest.raises(ExternalToolError) as raised:
        handover.open_in_slicer(model, setup)

    offered = {action.id for action in raised.value.suggestions}
    assert {"choose_slicer", "export_only"} <= offered


def test_open_in_slicer_starts_the_window_with_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Aufruf ist eine feste Argumentliste (§32): das Fenster, die Datei,
    sonst nichts — und gewartet wird nicht."""
    executable = tmp_path / "elegoo-slicer.exe"
    executable.write_bytes(b"")
    model = tmp_path / "teil.3mf"
    model.write_bytes(b"x")
    started: list[tuple[list[str], dict[str, object]]] = []

    class _Detached:
        def __init__(self, command: list[str], **kwargs: object) -> None:
            started.append((list(command), kwargs))

    monkeypatch.setattr(handover.subprocess, "Popen", _Detached)
    handover.open_in_slicer(model, handover.SlicerSetup(executable=executable, flavour="orca"))

    command, options = started[0]
    assert command == [str(executable.resolve()), str(model.resolve())]
    assert options["close_fds"] is True
    assert options["stdout"] == handover.subprocess.DEVNULL
    assert "OPENAI_API_KEY" not in options["env"]


def test_the_console_gets_the_same_plate_as_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Übernommene Stützen stehen an den Teilen, die sie brauchen, und die
    Platte bleibt auf der Grundlage (Konzept Herstellerprofil, Entscheidung
    G). ``slice_model`` fragt dafür dieselbe Trennung wie ``write_assembly``
    — sonst schriebe die Datei die Stützen je Teil, und der Prozess des
    Konsolenlaufs schaltete sie für alle ein."""
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    assert settings.support.style == "none", "die Vorbedingung des Tests"
    settings = print_settings.with_accepted(settings, "support.style", "auto")
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    executable = tmp_path / "elegoo-slicer.exe"
    executable.write_bytes(b"")
    processes: list[dict[str, object]] = []

    def run(command: list[str], *args: object, **kwargs: object) -> _Finished:
        path = Path(command[command.index("--load-settings") + 1].split(";")[-1])
        processes.append(json.loads(path.read_text(encoding="utf-8")))
        target = Path(command[command.index("--outputdir") + 1])
        (target / "plate_1.gcode").write_text(_gcode_printing_at(1.0, 5.0), encoding="utf-8")
        return _Finished(b"")

    monkeypatch.setattr(handover, "_run_slicer", run)
    handover.slice_model(
        model, settings, profile, handover.SlicerSetup(executable=executable, flavour="orca")
    )

    assert len(processes) == 1
    assert processes[0]["enable_support"] in ("0", ["0"])


def test_an_unknown_arrange_flag_falls_back_and_reports(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nur eine ausdrückliche Schalterabsage gilt für spätere Aufträge."""
    profile = profiles.make_profile()
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    executable = tmp_path / "elegoo-slicer.exe"
    executable.write_bytes(b"")
    setup = handover.SlicerSetup(executable=executable, flavour="orca")
    commands: list[list[str]] = []

    def fake_run(command: list[str], *args: object, **kwargs: object) -> _Finished:
        commands.append(list(command))
        if "--arrange" in command:
            failed = _Finished(b"Unknown option --arrange\n")
            failed.returncode = 127
            return failed
        target = Path(command[command.index("--outputdir") + 1])
        (target / "plate_1.gcode").write_text(_gcode_printing_at(1.0, 5.0), encoding="utf-8")
        return _Finished(b"")

    monkeypatch.setattr(handover, "_run_slicer", fake_run)
    outcome = handover.slice_model(
        model, print_settings.resolve(profile), profile, setup, keep_arrangement=True
    )

    assert len(commands) == 2, "erst mit Schalter, dann die Rückfallstufe ohne"
    assert "--arrange" in commands[0] and "--arrange" not in commands[1]
    assert any(entry.code == "slicer.arranged_itself" for entry in outcome.findings)

    # Gemerkt: derselbe Slicer bekommt den Schalter nicht noch einmal — und
    # der Befund bleibt, denn die Anordnung liegt weiter beim Slicer.
    again = handover.slice_model(
        model, print_settings.resolve(profile), profile, setup, keep_arrangement=True
    )
    assert len(commands) == 3, "die zweite Platte läuft in einem Zug"
    assert "--arrange" not in commands[2]
    assert any(entry.code == "slicer.arranged_itself" for entry in again.findings)


def test_creality_print_slices_on_its_console_before_and_after_7_3(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Creality Print 7.3 rechnet nur mit ``--cli``, 7.2 kennt den Schalter nicht.

    Gemessen am 29.09.2026: 7.3.0.6149 startet ohne ``--cli`` die Oberfläche,
    und der Lauf wartete bis zum Zeitlimit; mit ihm lehnt es ``--arrange`` ab
    („Invalid option --arrange"), hält die Lage einer 3MF selbst und schreibt
    ``plate_1.gcode`` nur mit ``--need-gcode-file``. Eine ältere Fassung, die
    ``--cli`` ablehnt, rechnet einmal mit dem alten Aufruf weiter, gemerkt je
    Programm. 7.3 rückt jede Platte selbst zur Mitte, auch eine haltende
    Anordnung (RM-414) — dort steht „selbst angeordnet"; 7.2 hält die Lage
    mit ``--arrange 0`` und meldet nichts.
    """
    profile = profiles.make_profile()
    model = tmp_path / "platte.3mf"
    model.write_bytes(b"keine echte 3MF")
    commands: list[list[str]] = []
    refuses_cli: set[Path] = set()

    def fake_run(command: list[str], *args: object, **kwargs: object) -> _Finished:
        commands.append(list(command))
        if Path(command[0]) in refuses_cli and "--cli" in command:
            failed = _Finished(b"Invalid option --cli\n")
            failed.returncode = 1
            return failed
        target = Path(command[command.index("--outputdir") + 1])
        (target / "plate_1.gcode").write_text(_gcode_printing_at(1.0, 5.0), encoding="utf-8")
        return _Finished(b"")

    monkeypatch.setattr(handover, "_run_slicer", fake_run)
    settings = print_settings.resolve(profile)

    new = tmp_path / "neu" / "CrealityPrint.exe"
    new.parent.mkdir()
    new.write_bytes(b"")
    outcome = handover.slice_model(
        model, settings, profile, handover.SlicerSetup(new, "orca"), keep_arrangement=True
    )
    assert len(commands) == 1, "7.3 rechnet im ersten Lauf"
    assert "--cli" in commands[0] and "--need-gcode-file" in commands[0]
    assert "--arrange" not in commands[0], "7.3 kennt den Schalter nicht"
    assert any(entry.code == "slicer.arranged_itself" for entry in outcome.findings), (
        "7.3 ordnet auch eine haltende Anordnung selbst an"
    )

    old = tmp_path / "alt" / "CrealityPrint.exe"
    old.parent.mkdir()
    old.write_bytes(b"")
    refuses_cli.add(old)
    for _ in range(2):
        outcome = handover.slice_model(
            model, settings, profile, handover.SlicerSetup(old, "orca"), keep_arrangement=True
        )
        assert not any(entry.code == "slicer.arranged_itself" for entry in outcome.findings)
    assert len(commands) == 4, "einmal mit --cli abgelehnt, dann zweimal der alte Aufruf"
    assert "--cli" in commands[1]
    for command in commands[2:]:
        assert "--cli" not in command and "--need-gcode-file" not in command
        assert command[command.index("--arrange") + 1] == "0", "7.2 hält die Lage so"


@pytest.mark.parametrize(
    ("program", "plate_count", "copied"),
    [
        ("CrealityPrint.exe", 1, True),
        ("creality-print", 1, True),
        ("CrealityPrint.exe", 0, False),
        ("CrealityPrint.exe", 2, False),
        ("bambu-studio.exe", 1, False),
        ("orca-slicer.exe", 1, False),
        ("elegoo-slicer.exe", 1, False),
        ("prusa-slicer-console.exe", 1, False),
    ],
)
def test_only_creality_cli_omits_a_proven_single_plate_without_losing_filaments(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    program: str,
    plate_count: int,
    copied: bool,
) -> None:
    """Der echte CLI-Eingang erhält alles außer Crealitys abstürzendem Plattenblock."""
    import trimesh

    from app.core.export import threemf
    from app.core.geom.mesh import MeshData

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    executable = tmp_path / program
    executable.write_bytes(b"")
    flavour = slicer_keys.flavour_of(program)
    assert flavour is not None
    setup = handover.SlicerSetup(executable=executable, flavour=flavour)
    parts = [
        threemf.AssemblyPart(
            MeshData.of(trimesh.creation.box((12.0, 12.0, 3.0))),
            name=name,
            slots=(MaterialSlot(index=0, name=name, colour=colour, material_type=kind),),
            plate=index if plate_count > 1 else 0,
        )
        for index, (name, colour, kind) in enumerate(
            [
                ("PLA Orange", (177 / 255, 99 / 255, 10 / 255), "PLA"),
                ("PETG Weiß", (1.0, 1.0, 1.0), "PETG"),
            ]
        )
    ]
    slots = threemf.merge_slots(parts)
    model = tmp_path / "Original.3mf"
    model.write_bytes(
        threemf.write_assembly(
            parts,
            project_settings=handover.project_settings(settings, profile, setup, slots=slots),
        )
    )
    with zipfile.ZipFile(model) as container:
        original = {entry.filename: container.read(entry) for entry in container.infolist()}
    if plate_count == 0:
        config = ET.fromstring(original[threemf.SETTINGS_PATH])
        for plate in config.findall("plate"):
            config.remove(plate)
        original[threemf.SETTINGS_PATH] = ET.tostring(config)
        with zipfile.ZipFile(model, "w") as container:
            for name, payload in original.items():
                container.writestr(name, payload)
    original_bytes = model.read_bytes()
    received: list[Path] = []

    def run(command: list[str], *args: object, **kwargs: object) -> _Finished:
        """Prüft die Datei an der Prozessgrenze, bevor der Arbeitsordner verschwindet."""
        incoming = next(Path(argument) for argument in command if argument.endswith(".3mf"))
        received.append(incoming)
        assert incoming != model
        assert str(incoming).isascii()
        with zipfile.ZipFile(incoming) as container:
            actual = {entry.filename: container.read(entry) for entry in container.infolist()}
        if copied:
            expected = ET.fromstring(original[threemf.SETTINGS_PATH])
            expected.remove(expected.findall("plate")[0])
            native = ET.fromstring(actual[threemf.SETTINGS_PATH])
            assert ET.tostring(native) == ET.tostring(expected)
            assert [
                obj.find("metadata[@key='extruder']").get("value")
                for obj in native.findall("object")
            ] == ["1", "2"]
            assert [
                obj.find("metadata[@key='name']").get("value") for obj in native.findall("object")
            ] == ["PLA Orange", "PETG Weiß"]
            actual[threemf.SETTINGS_PATH] = original[threemf.SETTINGS_PATH]
        assert actual == original, "Geometrie, Farben und übrige Beilagen bleiben vollständig"
        assert b"#B1630A" in actual[threemf.MODEL_PATH]
        assert b"#FFFFFF" in actual[threemf.MODEL_PATH]
        _slicer_output_path(command).write_text(_TWO_TOOLS, encoding="utf-8")
        return _Finished(b"")

    monkeypatch.setattr(handover, "_run_slicer", run)
    outcome = handover.slice_model(
        model, settings, profile, setup, output_dir=tmp_path, slots=slots, expected_tools=(0, 1)
    )
    assert len(received) == 1
    assert model.read_bytes() == original_bytes
    assert outcome.metrics.used_tools == (0, 1)


def _creality_tower_config(tmp_path: Path) -> handover.SlicerConfig:
    """Die für die Turmplatzierung maßgeblichen Werte des K1-CFS-Herstellerprofils."""
    machine = tmp_path / "machine.json"
    machine.write_text(
        json.dumps(
            {
                "name": "Creality K1_CFS-C 0.4 nozzle",
                "type": "machine",
                "printable_area": "0x0,220x0,220x220,0x220",
                "prime_tower_position_type": "Middle Upper",
            }
        ),
        encoding="utf-8",
    )
    process = tmp_path / "process.json"
    process.write_text(
        json.dumps(
            {
                "name": "Standard",
                "type": "process",
                "enable_prime_tower": "1",
                "prime_tower_width": "180",
                "wipe_tower_rotation_angle": "0",
            }
        ),
        encoding="utf-8",
    )
    return handover.SlicerConfig(process=process, machine=machine)


@pytest.mark.parametrize(
    "program", ["orca-slicer.exe", "elegoo-slicer.exe", "bambu-studio.exe", "CrealityPrint.exe"]
)
@pytest.mark.parametrize("bed", [180, 220])
@pytest.mark.parametrize("rotation", [0, 90])
@pytest.mark.parametrize("explicit_brim", [False, True])
def test_missing_tower_positions_start_inside_the_native_bed(
    tmp_path: Path, program: str, bed: int, rotation: int, explicit_brim: bool
) -> None:
    """RM-476: Ohne Fenstermodus blieb der Turm bei 15/220, selbst auf 180 mm."""
    config = _creality_tower_config(tmp_path)
    assert config.machine is not None
    config.machine.write_text(
        json.dumps({"printable_area": f"0x0,{bed}x0,{bed}x{bed},0x{bed}"}), encoding="utf-8"
    )
    process = {
        "enable_prime_tower": "1",
        "prime_tower_width": "35",
        "wipe_tower_rotation_angle": str(rotation),
    }
    if explicit_brim:
        process["prime_tower_brim_width"] = "3"
    config.process.write_text(json.dumps(process), encoding="utf-8")
    setup = handover.SlicerSetup(executable=Path(program), flavour="orca")

    positioned = handover._orca_cli_tower_position(config, setup, ())

    written = json.loads(config.process.read_text(encoding="utf-8"))
    assert float(written["wipe_tower_x"][0]) == pytest.approx(bed - 18 if rotation else 18)
    assert float(written["wipe_tower_y"][0]) == pytest.approx(18)
    assert {key: value for key, value in written.items() if key in process} == process
    assert positioned.written["wipe_tower_y"] == "18.0"


@pytest.mark.parametrize("rotation", [0, 90])
@pytest.mark.parametrize("brim", [0, 3, 25])
def test_automatic_tower_position_reserves_the_brim_on_a_shifted_bed(
    tmp_path: Path, rotation: int, brim: int
) -> None:
    """Der Rand kommt zur nativen Brimbreite hinzu; der Ursprung ist nicht stets null."""
    config = _creality_tower_config(tmp_path)
    assert config.machine is not None
    config.machine.write_text(
        json.dumps({"printable_area": ["10x20", "230x20", "230x260", "10x260"]}),
        encoding="utf-8",
    )
    config.process.write_text(
        json.dumps(
            {
                "enable_prime_tower": "1",
                "prime_tower_width": "35",
                "prime_tower_brim_width": str(brim),
                "wipe_tower_rotation_angle": str(rotation),
            }
        ),
        encoding="utf-8",
    )
    setup = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")

    positioned = handover._orca_cli_tower_position(config, setup, ())

    margin = 15 + brim
    assert float(positioned.written["wipe_tower_x"]) == pytest.approx(
        230 - margin if rotation else 10 + margin
    )
    assert float(positioned.written["wipe_tower_y"]) == pytest.approx(20 + margin)


@pytest.mark.parametrize(
    ("width", "brim", "initialized"),
    [(144, "3", True), (144.1, "3", False), (35, "nan", False), (35, "-1", False)],
)
def test_an_automatic_tower_does_not_hide_an_impossible_or_unknown_margin(
    tmp_path: Path, width: float, brim: str, initialized: bool
) -> None:
    """Ein zu großer Turm wird nicht durch geklemmte Koordinaten passend gerechnet."""
    config = _creality_tower_config(tmp_path)
    assert config.machine is not None
    config.machine.write_text(
        json.dumps({"printable_area": "0x0,180x0,180x180,0x180"}), encoding="utf-8"
    )
    config.process.write_text(
        json.dumps(
            {
                "enable_prime_tower": "1",
                "prime_tower_width": str(width),
                "prime_tower_brim_width": brim,
            }
        ),
        encoding="utf-8",
    )
    before = config.process.read_bytes()
    setup = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")

    positioned = handover._orca_cli_tower_position(config, setup, ())

    assert bool(positioned.written) is initialized
    if not initialized:
        assert config.process.read_bytes() == before


@pytest.mark.parametrize(
    ("mode", "unrotated", "rotated"),
    [
        ("Left Upper", (15, 185), (35, 25)),
        ("Left Center", (15, 110), (35, 110)),
        ("Left Below", (15, 15), (35, 15)),
        ("Middle Upper", (20, 185), (110, 25)),
        ("Middle Center", (20, 110), (110, 110)),
        ("Middle Below", (20, 15), (110, 15)),
        ("Right Upper", (25, 185), (205, 25)),
        ("Right Center", (25, 110), (205, 110)),
        ("Right Below", (25, 15), (205, 15)),
    ],
)
@pytest.mark.parametrize("rotation", [0, 90])
def test_creality_cli_uses_the_manufacturers_tower_modes(
    tmp_path: Path, mode: str, unrotated: tuple[int, int], rotated: tuple[int, int], rotation: int
) -> None:
    """Die neun Herstellerpositionen gelten auch ohne dessen Fensterinitialisierung."""
    config = _creality_tower_config(tmp_path)
    process = json.loads(config.process.read_text(encoding="utf-8"))
    process.update(prime_tower_position_type=mode, wipe_tower_rotation_angle=str(rotation))
    config.process.write_text(json.dumps(process), encoding="utf-8")
    setup = handover.SlicerSetup(executable=Path("CrealityPrint.exe"), flavour="orca")

    positioned = handover._orca_cli_tower_position(config, setup, ())

    written = json.loads(config.process.read_text(encoding="utf-8"))
    keys = ("wipe_tower_x", "wipe_tower_y")
    assert [float(written[key][0]) for key in keys] == pytest.approx(
        rotated if rotation else unrotated
    )
    assert {key: value for key, value in written.items() if key not in keys} == process
    assert all(key in positioned.written for key in keys), "die Gegenprobe kennt die Sollposition"
    assert handover.verify("; wipe_tower_x = 999\n", positioned.written)


@pytest.mark.parametrize("origin", ["machine", "process", "project"])
@pytest.mark.parametrize(
    "coordinates",
    [
        {"wipe_tower_x": ["27.25"]},
        {"wipe_tower_y": ["43.5"]},
        {"wipe_tower_x": ["27.25"], "wipe_tower_y": ["43.5"]},
    ],
)
def test_creality_cli_keeps_every_explicit_tower_coordinate(
    tmp_path: Path, origin: str, coordinates: dict[str, list[str]]
) -> None:
    """Auch eine teilweise oder eingebettet gespeicherte manuelle Position wird nie ersetzt."""
    from app.core.export.threemf import PROJECT_SETTINGS_PATH

    config = _creality_tower_config(tmp_path)
    models: tuple[Path, ...] = ()
    if origin == "project":
        model = tmp_path / "manual.3mf"
        with zipfile.ZipFile(model, "w") as container:
            container.writestr(PROJECT_SETTINGS_PATH, json.dumps(coordinates))
        models = (model,)
    else:
        path = config.machine if origin == "machine" else config.process
        assert path is not None
        values = json.loads(path.read_text(encoding="utf-8"))
        values.update(coordinates)
        path.write_text(json.dumps(values), encoding="utf-8")
    before = {path: path.read_bytes() for path in tmp_path.iterdir()}
    setup = handover.SlicerSetup(executable=Path("CrealityPrint.exe"), flavour="orca")

    assert handover._orca_cli_tower_position(config, setup, models) is config
    assert {path: path.read_bytes() for path in tmp_path.iterdir()} == before


@pytest.mark.parametrize(
    ("program", "values"),
    [
        ("bambu-studio.exe", {}),
        ("orca-slicer.exe", {}),
        ("elegoo-slicer.exe", {}),
        ("CrealityPrint.exe", {"prime_tower_position_type": "Custom"}),
        ("CrealityPrint.exe", {"enable_prime_tower": "0"}),
        ("CrealityPrint.exe", {"wipe_tower_rotation_angle": "45"}),
        ("CrealityPrint.exe", {"printable_area": "110x0,220x110,110x220,0x110"}),
    ],
)
def test_tower_initialization_leaves_unproven_cases_alone(
    tmp_path: Path, program: str, values: dict[str, str]
) -> None:
    """Fremde Platzierungsmodi und unbelegte Regeln lassen den Auftrag unverändert."""
    config = _creality_tower_config(tmp_path)
    process = json.loads(config.process.read_text(encoding="utf-8"))
    process.update(values)
    config.process.write_text(json.dumps(process), encoding="utf-8")
    before = config.process.read_bytes()
    setup = handover.SlicerSetup(executable=Path(program), flavour="orca")
    assert handover._orca_cli_tower_position(config, setup, ()) is config
    assert config.process.read_bytes() == before


def test_creality_tower_uses_the_actual_shifted_bed_bounds(tmp_path: Path) -> None:
    """Bettgröße und Ursprung stammen aus der Herstellerkontur, nie aus dem K1-Beispiel."""
    config = _creality_tower_config(tmp_path)
    assert config.machine is not None
    machine = json.loads(config.machine.read_text(encoding="utf-8"))
    machine["printable_area"] = ["10x20", "230x20", "230x260", "10x260"]
    config.machine.write_text(json.dumps(machine), encoding="utf-8")
    setup = handover.SlicerSetup(executable=Path("CrealityPrint.exe"), flavour="orca")
    positioned = handover._orca_cli_tower_position(config, setup, ())
    assert float(positioned.written["wipe_tower_x"]) == pytest.approx(30.0)
    assert float(positioned.written["wipe_tower_y"]) == pytest.approx(225.0)


@pytest.mark.parametrize(
    ("slot_count", "used_tools", "expected_tools"),
    [
        (1, (0,), (0,)),
        (1, (0,), ()),
        (2, (1,), (1,)),
        (2, (1,), ()),
        (2, (0, 1), (0, 1)),
        (2, (0, 1), ()),
    ],
)
@pytest.mark.parametrize("explicit", [False, True])
def test_creality_slice_initializes_the_tower_inside_the_manufacturers_bed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    slot_count: int,
    used_tools: tuple[int, ...],
    expected_tools: tuple[int, ...],
    explicit: bool,
) -> None:
    """Nur der aktive Turm muss abgeleitete Koordinaten bestätigen, ausdrückliche immer."""
    config = _creality_tower_config(tmp_path)
    executable = tmp_path / "CrealityPrint.exe"
    executable.write_bytes(b"")
    setup = handover.SlicerSetup(
        executable=executable,
        flavour="orca",
        machine_profile=str(config.machine),
        base_process=str(config.process),
    )
    profile = profiles.make_profile("creality-k1", "pla")
    settings = print_settings.resolve(profile)
    model = tmp_path / "probe.stl"
    model.write_text("solid x\nendsolid x\n")
    before = model.read_bytes()
    captured: list[dict[str, object]] = []
    expected: dict[str, str] = {}
    original_write = handover.write_config

    def write(*args: Any, **kwargs: Any) -> handover.SlicerConfig:
        """Eine ausdrückliche Koordinate ist schon vor der CLI-Ableitung ein Sollwert."""
        written = original_write(*args, **kwargs)
        expected.update(written.written)
        if not explicit:
            return written
        values = json.loads(written.process.read_text(encoding="utf-8"))
        coordinates = {"wipe_tower_x": "20.0", "wipe_tower_y": "185.0"}
        values.update({key: [value] for key, value in coordinates.items()})
        written.process.write_text(json.dumps(values), encoding="utf-8")
        return replace(written, written={**written.written, **coordinates})

    def run(command: list[str], *args: object, **kwargs: object) -> _Finished:
        """Prüft den Auftrag an der Prozessgrenze und schreibt einen kleinen Rücklauf."""
        path = Path(command[command.index("--load-settings") + 1].split(";")[-1])
        written = json.loads(path.read_text(encoding="utf-8"))
        captured.append(written)
        assert [float(value) for value in written["wipe_tower_x"]] == pytest.approx([20.0])
        assert [float(value) for value in written["wipe_tower_y"]] == pytest.approx([185.0])
        returned = "G90\nM82\n" + "".join(
            f"T{tool}\nG1 X10 Y0 E1\nG1 Z0.2\nG1 X20 Y0 E2\n" for tool in used_tools
        )
        # Creality nullt den inaktiven Einfilament-Turm. Beim aktiven Turm
        # oder einer ausdrücklichen Koordinate muss dieselbe Abweichung bleiben.
        returned += "".join(
            f"; {key} = {value}\n"
            for key, value in expected.items()
            if key not in {"wipe_tower_x", "wipe_tower_y"}
        )
        returned += "; wipe_tower_x = 0.000\n; wipe_tower_y = 0.000\n"
        _slicer_output_path(command).write_text(returned, encoding="utf-8")
        return _Finished(b"")

    monkeypatch.setattr(handover, "write_config", write)
    monkeypatch.setattr(handover, "_run_slicer", run)
    outcome = handover.slice_model(
        model,
        settings,
        profile,
        setup,
        output_dir=tmp_path,
        slots=_slots(slot_count),
        expected_tools=expected_tools,
    )
    assert len(captured) == 1
    assert model.read_bytes() == before
    assert outcome.metrics.used_tools == used_tools
    assert any(finding.code == "slicer.setting_ignored" for finding in outcome.findings) == (
        explicit or len(used_tools) > 1
    )
    embedded = handover.project_settings(settings, profile, setup)
    assert "wipe_tower_x" not in embedded and "wipe_tower_y" not in embedded


def test_a_print_file_shorter_than_the_model_is_an_error() -> None:
    """CuraEngine schneidet unter ``z = 0`` wortlos ab (gemessen 30.08.2026:
    50 Schichten statt 100 bei einem zentriert importierten Würfel, Exit 0).
    Keine andere Gegenprobe sieht das — die halbe Höhe liegt brav im Bauraum.
    """
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    half = "G90\nM82\n" + "".join(
        f"G1 Z{z / 10.0:g}\nG1 X{10 if z % 4 else 20} Y0 E{z / 10.0:g}\n" for z in range(2, 102, 2)
    )

    short = handover.too_short(half, 20.0, settings)
    assert short is not None, "10 mm Druck bei 20 mm Modell ist ein Befund"
    assert short.severity == "error"
    assert short.source == "gcode", "die Aussage kommt aus der Druckdatei (Regel 14)"

    assert handover.too_short(half, 10.0, settings) is None, "volle Höhe: kein Befund"
    assert handover.too_short(half, 10.3, settings) is None, (
        "zwei Schichthöhen Luft für Rundung und erste Schicht"
    )


#: Ein G-Code, der nur Werkzeug 0 benutzt — zwei Zeilen Förderung reichen,
#: denn geprüft wird die Werkzeugliste und nicht die Geometrie.
_ONE_TOOL = "G90\nM82\nT0\nG1 X10 Y0 E1\nG1 Z0.2\nG1 X20 Y0 E2\n"
#: Derselbe Druck mit beiden Werkzeugen.
_TWO_TOOLS = _ONE_TOOL + "T1\nG1 X30 Y0 E3\nG1 X40 Y0 E4\n"


def _slots(count: int) -> tuple[MaterialSlot, ...]:
    farben = ("Rot", "Blau", "Grün")
    return tuple(
        MaterialSlot(index, f"PLA {farben[index]}", None, None, "PLA") for index in range(count)
    )


def test_a_filament_missing_from_the_print_file_is_an_error() -> None:
    """Bambu Studio ließ ein zweifarbiges Teil halb weg und meldete Erfolg.

    Gemessen am 12.09.2026 mit Bambu Studio 2.3: derselbe Würfel einfarbig
    4,31 g, zweifarbig 2,82 g — ein Filament statt zwei, Exit 0, kein Wort in
    Ausgabe oder Protokoll. Höhe, Bauraum und geschriebene Werte stimmen alle;
    die drei bisherigen Gegenproben schweigen deshalb.
    """
    analysis = gcode.analyze(_ONE_TOOL)
    slots = _slots(2)

    left_out = handover.spools_left_out(analysis, (0, 1), slots, "orca")
    assert left_out is not None, "zwei Spulen übergeben, eine gedruckt — ein Befund"
    assert left_out.severity == "error"
    assert left_out.source == "gcode", "die Aussage kommt aus der Druckdatei (Regel 14)"
    assert "PLA Blau" in str(left_out.values["filament"]), (
        "der Kunde soll wissen, welche Spule fehlt, nicht nur dass eine fehlt"
    )

    assert handover.spools_left_out(gcode.analyze(_TWO_TOOLS), (0, 1), slots, "orca") is None, (
        "beide Werkzeuge im G-Code: kein Befund"
    )


@pytest.mark.parametrize("flavour", ["prusa", "cura"])
def test_slicers_without_filament_profiles_get_no_second_complaint(flavour: str) -> None:
    """Dass Prusa und Cura nur ein Filament fahren, sagt ``unreachable_overrides``
    schon vor dem Lauf. Ein zweiter Befund über dieselbe Sache macht den ersten
    schwächer, nicht den Bericht vollständiger."""
    assert (
        handover.spools_left_out(gcode.analyze(_ONE_TOOL), (0, 1), _slots(2), flavour)  # type: ignore[arg-type]
        is None
    )


def test_missing_spool_names_follow_the_report_language(monkeypatch: pytest.MonkeyPatch) -> None:
    """Gesammelte automatische Namen bleiben auch nach einem Sprachwechsel übersetzbar."""
    import app.i18n as i18n
    from app.i18n.catalog import read_catalog

    monkeypatch.setattr(i18n, "_language", "de")
    for language in ("en", "fr"):
        monkeypatch.setitem(i18n._catalogs, language, read_catalog(language))
    names = (i18n._("Quader"), i18n._("Zylinder"))
    slots = (
        MaterialSlot(index=0, name="PETG Weiß"),
        MaterialSlot(index=1, name=names[0]),
        MaterialSlot(index=2, name=names[1]),
    )
    finding = handover.spools_left_out(gcode.analyze(_ONE_TOOL), (0, 1, 2), slots, "orca")
    assert finding is not None
    value = finding.values["filament"]
    assert isinstance(value, i18n.TranslatableText)
    for language in ("en", "fr"):
        expected = ", ".join(name.translate(language) for name in names)
        assert value.translate(language) == expected
        assert expected != "Quader, Zylinder"


def test_a_single_spool_is_never_a_missing_one() -> None:
    """Mit einem Werkzeug gibt es nichts zu verwechseln — und ein G-Code ohne
    jeden Werkzeugbefehl ist dann der Normalfall, kein Verlust."""
    assert handover.spools_left_out(gcode.analyze(_ONE_TOOL), (0,), _slots(1), "orca") is None
    assert handover.spools_left_out(gcode.analyze(_ONE_TOOL), (), _slots(2), "orca") is None, (
        "ohne Angabe entfällt der Vergleich, geraten wird nichts (Regel 21)"
    )


def test_a_file_without_any_extrusion_gets_the_clearer_error() -> None:
    """Ohne eine einzige Förderbewegung bleibt die Werkzeugliste leer — und
    dann ist „eine Spule fehlt" die schwächere von zwei Aussagen. Der Lauf
    hält für diesen Fall schon vorher an, mit „keine einzige Materialbahn"."""
    leer = gcode.analyze("G90\nG1 X10 Y0\n")
    assert not leer.extrudes and not leer.metrics.used_tools
    assert handover.spools_left_out(leer, (0, 1), _slots(2), "orca") is None


def test_an_implicit_first_tool_still_shows_the_missing_second() -> None:
    """Der gemessene Bambu-Fall trug **keinen einzigen** Werkzeugbefehl: Der
    Slicer druckte alles mit dem Ausgangswerkzeug und ließ die zweite Farbe
    weg. Wer hier auf ein ausdrückliches ``T0`` wartet, sieht genau den Fall
    nicht, für den die Prüfung gebaut wurde."""
    implizit = gcode.analyze("G90\nM82\nG1 X10 Y0 E1\nG1 X20 Y0 E2\n")
    assert implizit.metrics.used_tools == (0,), "Werkzeug 0 gilt auch ungenannt"

    left_out = handover.spools_left_out(implizit, (0, 1), _slots(2), "orca")
    assert left_out is not None, "zwei Spulen übergeben, eine gedruckt"
    assert "PLA Blau" in str(left_out.values["filament"])


@pytest.mark.parametrize(
    ("code", "expected"),
    [
        # Windows meldet einen abgebrochenen Prozess als NTSTATUS. Gemessen an
        # Creality Print 7.2 am 12.09.2026, dreimal derselbe Aufruf.
        (0xC0000005, True),
        (0xC0000409, True),
        (0xE06D7363, True),
        # POSIX zählt anders: ein Signal kommt als negative Zahl zurück.
        (-11, True),
        (-6, True),
        # Und das hier sind gewöhnliche Fehlschläge, keine Abstürze: der
        # Slic3r-Zweig gibt -17 als unsigned, CuraEngine eine schlichte 1.
        (0, False),
        (1, False),
        (4294967279, False),
        (4294967196, False),
        (0xFFFFFFFF, False),
        (0xD0000005, False),
    ],
)
def test_a_crash_is_told_apart_from_a_refusal(code: int, expected: bool) -> None:
    """Beide enden ohne Druckdatei, aber sie verlangen verschiedene Antworten:
    „Prüfen Sie Ihr Profil" hilft bei einem Absturz niemandem."""
    assert handover.crashed(code) is expected


def test_a_crashed_slicer_says_so_instead_of_blaming_the_profile(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Kette bis zum Kunden, nicht nur das Prädikat.

    Gemessen an Creality Print 7.2 (12.09.2026): ``0xC0000005`` mitten im
    eigenen Start, keine Ausgabe. Ohne diese Unterscheidung bekam der Kunde
    „Der Slicer hat keine Druckdatei geschrieben" samt dem Rat, sein
    Slicer-Profil zu prüfen — dort ist nichts zu finden.
    """

    class _Crashed:
        returncode = 0xC0000005
        stdout = b"crealityprint_main start\n"
        stderr = b""

    model = tmp_path / "model.3mf"
    model.write_bytes(b"PK\x05\x06" + b"\x00" * 18)
    executable = tmp_path / "CrealityPrint.exe"
    executable.write_bytes(b"")
    monkeypatch.setattr(handover, "_run_slicer", lambda *args, **kwargs: _Crashed())
    profile = profiles.make_profile()
    setup = handover.SlicerSetup(executable=executable, flavour="orca")

    with pytest.raises(ExternalToolError) as raised:
        handover.slice_model(model, print_settings.resolve(profile), profile, setup)

    assert "abgestürzt" in str(raised.value.detail), str(raised.value.detail)
    assert raised.value.suggestions, "Regel 17: jede Ausnahme trägt einen Vorschlag"
    assert raised.value.suggestions[0].id == "choose_slicer", (
        "Der erste Ausweg hängt an keiner Vermutung: Gemessen ist der Absturz, nicht "
        "sein Grund — und auf einem Rechner mit mehreren Slicern ist der Wechsel der "
        "kürzeste Weg zur Druckdatei (Regel 21)"
    )
    assert [action.id for action in raised.value.suggestions].count("retry") == 1, (
        "das Wiederholen bleibt dabei — nach einem Start von Hand ist es der nächste Schritt"
    )


def test_a_left_out_spool_reaches_the_report(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Und auch diese Kette bis zum Ende: ``slice_model`` muss die erwarteten
    Werkzeuge annehmen und den Befund in seine Liste legen. Eine Prüfung, die
    nur als Funktion stimmt, hat der Kunde nie gesehen."""
    model, setup = _slicer_writing(monkeypatch, tmp_path, _ONE_TOOL, flavour="orca")
    profile = profiles.make_profile()
    slots = _slots(2)

    outcome = handover.slice_model(
        model,
        print_settings.resolve(profile),
        profile,
        setup,
        output_dir=tmp_path,
        slots=slots,
        expected_tools=(0, 1),
    )
    codes = [entry.code for entry in outcome.findings]
    assert "gcode.spool_left_out" in codes, codes
    # Regel 17: Eine fehlende Spule nennt den Weg zur vollständigen Druckdatei.
    left_out = next(entry for entry in outcome.findings if entry.code == "gcode.spool_left_out")
    assert [action.id for action in left_out.suggestions] == ["choose_slicer", "check_profile"]

    ohne = handover.slice_model(
        model,
        print_settings.resolve(profile),
        profile,
        setup,
        output_dir=tmp_path,
        slots=slots,
    )
    assert "gcode.spool_left_out" not in [entry.code for entry in ohne.findings], (
        "ohne Angabe entfällt der Vergleich — geraten wird nichts (Regel 21)"
    )


def test_open_in_slicer_reports_a_missing_file(tmp_path: Path) -> None:
    """Die Datei ist zwischen Export und Öffnen verschwunden — derselbe Satz
    und derselbe Ausweg wie beim Konsolenlauf."""
    executable = tmp_path / "elegoo-slicer.exe"
    executable.write_bytes(b"")
    setup = handover.SlicerSetup(executable=executable, flavour="orca")

    with pytest.raises(ExternalToolError) as raised:
        handover.open_in_slicer(tmp_path / "fehlt.3mf", setup)

    assert any(action.id == "retry" for action in raised.value.suggestions)


def _gcode_printing_at(*xs: float) -> str:
    """Eine kleinste Druckdatei, die genau an diesen X-Stellen Material legt."""
    lines = ["G90", "M82", "G1 Z0.2 F300"]
    lines += [f"G1 X{x:g} Y0 E{index / 10.0 + 0.1:g}" for index, x in enumerate(xs)]
    return "\n".join(lines) + "\n"


def _slicer_output_path(command: list[str]) -> Path:
    """Das Ziel aus der Kommandozeile, unabhängig vom gewählten Rückgabeordner."""
    if "--outputdir" in command:
        return Path(command[command.index("--outputdir") + 1]) / "plate_1.gcode"
    flag = "-o" if "-o" in command else "--output"
    return Path(command[command.index(flag) + 1])


def _slicer_writing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, payload: str, flavour: str = "cura"
) -> tuple[Path, handover.SlicerSetup]:
    """Ein Slicer, der durchläuft und genau diese Datei schreibt.

    Geschrieben wird an das tatsächliche CLI-Ziel, wie beim echten Slicer.
    """
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    executable = tmp_path / f"{flavour}.exe"
    executable.write_bytes(b"")

    def _writes(command: list[str], *_args: object, **_kwargs: object) -> _Finished:
        _slicer_output_path(command).write_text(payload, encoding="utf-8")
        return _Finished(b"")

    monkeypatch.setattr(handover, "_run_slicer", _writes)
    return model, handover.SlicerSetup(executable=executable, flavour=flavour)  # type: ignore[arg-type]


def test_slice_duration_uses_a_monotonic_clock(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Laufzeit darf nicht die Epoch-Zeit der Ergebnisdatei verwenden."""
    profile = profiles.make_profile()
    model, setup = _slicer_writing(
        monkeypatch, tmp_path, _gcode_printing_at(1.0, 5.0), flavour="orca"
    )
    elapsed_values = iter((12.0, 12.375))
    monkeypatch.setattr(
        handover,
        "time",
        SimpleNamespace(
            perf_counter=lambda: next(elapsed_values),
            time=lambda: 1_800_000_000.0,
        ),
    )

    outcome = handover.slice_model(
        model,
        print_settings.resolve(profile),
        profile,
        setup,
        output_dir=tmp_path,
    )

    assert outcome.seconds == pytest.approx(0.375)


def test_the_first_spools_value_is_verified_as_written(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Gegenprobe vergleicht mit dem Satz, den der Slicer wirklich bekam.

    Prusa und Cura nehmen einen Filamentsatz. Ist die erste Spule auf 210 °C
    gestellt und das Projekt auf 240 °C, ist 210 im G-Code ein Erfolg und kein
    angebliches Übergehen der Einstellung.
    """
    from app.core.types import SlotOverride

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    slot = MaterialSlot(index=0, name="PLA Weiß", colour=(1.0, 1.0, 1.0))
    own_temperature = replace(settings.temperature, nozzle=210)
    settings = replace(
        settings,
        slot_overrides=(
            SlotOverride(
                name=slot.name,
                colour=slot.colour,
                temperature=own_temperature,
            ),
        ),
    )
    payload = _gcode_printing_at(-10.0, 10.0) + "; temperature = 210\n"
    model, setup = _slicer_writing(monkeypatch, tmp_path, payload, flavour="prusa")
    written: dict[str, str] = {}
    original_write = handover.write_config

    def remember_config(*args: Any, **kwargs: Any) -> handover.SlicerConfig:
        config = original_write(*args, **kwargs)
        written.update(config.written)
        return config

    def complete_gcode(command: list[str], *_args: object, **_kwargs: object) -> _Finished:
        # Prusa bestätigt den ganzen Satz; nur die Temperatur kommt unabhängig
        # aus der gestellten Druckdatei, damit der Spulenvergleich aussagekräftig bleibt.
        rest = "".join(
            f"; {key} = {value}\n" for key, value in written.items() if key != "temperature"
        )
        _slicer_output_path(command).write_text(payload + rest, encoding="utf-8")
        return _Finished(b"")

    monkeypatch.setattr(handover, "write_config", remember_config)
    monkeypatch.setattr(handover, "_run_slicer", complete_gcode)

    outcome = handover.slice_model(
        model,
        settings,
        profile,
        setup,
        output_dir=tmp_path,
        slots=(slot,),
    )

    assert "slicer.setting_ignored" not in {finding.code for finding in outcome.findings}


def test_a_gcode_that_prints_beside_the_bed_becomes_a_finding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gemessen an CuraEngine 5.13.0: ein Würfel jenseits des Betts von
    220 mm — PrusaSlicer rückt ihn selbst in die Mitte, CuraEngine schreibt
    eine Datei, die dort druckt, wo kein Bett ist. Es prüft den Bauraum nicht,
    und sein Kopf sagt dazu ``MINX:2.14748e+06``, also nichts. Seit dem
    05.09.2026 misst jede Familie von der Ecke (CORE-17): Das Bett liegt bei
    0 bis 220, und ein Druck bei 230 bis 250 ist um 30 mm darüber hinaus.

    Gesperrt wird nichts (§29) — die Datei kommt zurück, der Befund steht
    daneben, und er trägt ``source="gcode"``, weil er an den Bahnen gemessen
    ist und nicht geschätzt (Regel 14).
    """
    profile = profiles.make_profile()
    model, setup = _slicer_writing(monkeypatch, tmp_path, _gcode_printing_at(230.0, 250.0))

    outcome = handover.slice_model(
        model, print_settings.resolve(profile), profile, setup, output_dir=tmp_path
    )

    beyond = [entry for entry in outcome.findings if entry.code == "gcode.off_the_bed"]
    assert beyond, [entry.code for entry in outcome.findings]
    assert beyond[0].severity == "error"
    assert beyond[0].source == "gcode"
    assert beyond[0].values["axis"] == "X"
    # 250 gedruckt, 220 erlaubt — das Bett von der Ecke aus.
    assert beyond[0].values["excess_mm"] == pytest.approx(30.0)
    assert outcome.gcode_path.is_file(), "die Datei bleibt trotzdem"


def test_a_gcode_that_stays_on_the_bed_says_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Gegenprobe: derselbe Weg, dieselbe Prüfung, ein Druck in der Mitte.

    Ohne sie prüfte der Test oben bloß, dass irgendein Befund entsteht.
    """
    profile = profiles.make_profile()
    model, setup = _slicer_writing(monkeypatch, tmp_path, _gcode_printing_at(80.0, 140.0))

    outcome = handover.slice_model(
        model, print_settings.resolve(profile), profile, setup, output_dir=tmp_path
    )

    assert not [entry for entry in outcome.findings if entry.code == "gcode.off_the_bed"]


def test_every_family_is_measured_from_the_corner() -> None:
    """Eine Welt, die des Druckers: Er misst von der Ecke, und die Gegenprobe
    misst genauso — für jede Familie.

    Bis zum 05.09.2026 waren es zwei Welten: Cura und PrusaSlicer bekamen von
    Solidon eine Maschine um den Ursprung, und ``bed_box`` maß gegen denselben
    erfundenen Ursprung — Bahnen bei ``-13,6`` galten damit als „auf dem
    Bett", obwohl es dort auf einem MK4S oder Centauri keines gibt
    (Gesamtreview, CORE-17). Unter Null liegt für keine Familie ein Bett.
    """
    profile = profiles.make_profile()
    unter_null = _gcode_printing_at(-30.0, 30.0)
    mitte = _gcode_printing_at(80.0, 140.0)

    for flavour in ("cura", "prusa", "orca"):
        assert handover.off_the_bed(unter_null, profile, flavour) is not None, (
            f"{flavour}: unter Null gibt es kein Bett"
        )
        assert handover.off_the_bed(mitte, profile, flavour) is None, flavour


def test_the_bed_in_the_file_beats_the_one_in_the_profile() -> None:
    """Wo der Slicer sein Bett selbst nennt, gilt seines.

    Die Orca-Familie und PrusaSlicer schreiben ihre Bettform in die Datei; ihr
    Maschinenprofil kommt aus dem Bestand des Slicers und nicht von Solidon
    (§29). Gemessen an einem Würfel in der Mitte eines 256er Betts, während im
    Dokument ein 220er Drucker steht — bei x 230 bis 250, also jenseits von
    220 und diesseits von 256. Ohne diese Vorfahrt stünde dort ein
    Befund über einen Druck, der genau dort liegt, wo er hingehört — und die
    Ursache wäre nicht der Druck, sondern zwei Profile, die verschiedene
    Maschinen meinen.
    """
    profile = profiles.make_profile()
    assert profile.printer.build_volume[0] == 220.0, "der Ausgangspunkt des Tests"
    weit_draussen = _gcode_printing_at(230.0, 250.0)
    mit_bett = "; printable_area = 0x0,256x0,256x256,0x256\n" + weit_draussen

    assert handover.off_the_bed(weit_draussen, profile, "orca") is not None
    assert handover.off_the_bed(mit_bett, profile, "orca") is None, "auf seinem Bett liegt es"


def test_a_file_without_a_single_path_is_not_judged() -> None:
    """Eine Datei ohne Materialbahn sagt nichts über den Bauraum — das Feld
    ``gcode.analyze(...).extrudes`` zeigt, ob sie Bahnen enthält."""
    profile = profiles.make_profile()

    assert handover.off_the_bed("G90\nG0 X400 Y400\nM104 S210\n", profile, "cura") is None


def test_the_newest_gcode_in_the_folder_wins(tmp_path: Path) -> None:
    """Orca hängt Plattennummern an; ein zweiter Lauf darf nicht die Zahlen des
    ersten melden."""
    import os
    import time

    old = tmp_path / "plate_1.gcode"
    old.write_text("; alt\n", encoding="utf-8")
    time.sleep(0.01)
    new = tmp_path / "plate_2.gcode"
    new.write_text("; neu\n", encoding="utf-8")
    os.utime(new, (time.time() + 5, time.time() + 5))

    assert handover._find_gcode(tmp_path) == new


def test_an_empty_folder_has_no_gcode(tmp_path: Path) -> None:
    assert handover._find_gcode(tmp_path) is None


def test_a_filament_profile_that_disagrees_is_reported(tmp_path: Path) -> None:
    """Beide Seiten haben recht: Solidons Tabelle sagt, was PETG im
    Allgemeinen verträgt, das Herstellerprofil, was diese Spule verträgt.

    Beim transluzenten Elegoo-PETG liegen dazwischen fünfzehn Grad an der Düse
    und zehn am Bett. Gemeldet wird es, übernommen nicht — die Einstellung ist
    die Entscheidung des Nutzers.
    """
    besonders = tmp_path / "besonders.json"
    besonders.write_text(
        json.dumps(
            {
                "type": "filament",
                "name": "Hersteller PETG Transluzent",
                "instantiation": "true",
                "nozzle_temperature": ["255"],
                "hot_plate_temp": ["70"],
            }
        ),
        encoding="utf-8",
    )
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    settings = print_settings.with_choice(settings, "temperature.nozzle", 240)
    settings = print_settings.with_choice(settings, "temperature.bed", 80)
    setup = handover.SlicerSetup(
        executable=Path("orca-slicer.exe"), flavour="orca", base_filament=str(besonders)
    )

    findings = handover.profile_differences(settings, setup)

    assert len(findings) == 1
    assert findings[0].code == "slicer.filament_differs"
    assert findings[0].source == "internal", "Regel 14: Herkunft ausweisen"
    named = findings[0].values["settings"]
    assert "nozzle_temperature: 240 statt 255" in named
    assert "hot_plate_temp: 80 statt 70" in named


def test_a_filament_profile_that_agrees_says_nothing(tmp_path: Path) -> None:
    """Ein Hinweis, der bei jedem Lauf erscheint, wird nach dem dritten Mal
    überlesen — also erscheint er nur, wenn wirklich etwas auseinandergeht."""
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    passend = tmp_path / "passend.json"
    passend.write_text(
        json.dumps(
            {
                "type": "filament",
                "name": "Hersteller PETG",
                "instantiation": "true",
                "nozzle_temperature": [str(settings.temperature.nozzle)],
            }
        ),
        encoding="utf-8",
    )
    setup = handover.SlicerSetup(
        executable=Path("orca-slicer.exe"), flavour="orca", base_filament=str(passend)
    )

    assert handover.profile_differences(settings, setup) == []
    # Ohne gewähltes Profil gibt es nichts zu vergleichen — und keine Meldung.
    ohne = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")
    assert handover.profile_differences(settings, ohne) == []


# --- Stellschrauben aus Stufe 3 -----------------------------------------------------


def test_a_narrow_wall_asks_for_the_variable_generator() -> None:
    """Ein Steg, der auf keine ganze Zahl von Bahnen aufgeht, ist der Fall, für
    den es den variablen Generator gibt.

    Der Anlass steht im Gewürzset: Federarme von 1,1 mm und eine Rastzunge von
    1,4 mm. Mit fester Linienbreite legt der Slicer zwei Bahnen à 0,42 und
    schließt den Rest mit Lückenfüllung — die trägt nicht, und die Feder bricht
    beim ersten Aufdrücken.
    """
    settings = print_settings.resolve(profiles.make_profile())
    settings = print_settings.with_path(settings, "shell.wall_generator", "classic")
    schmal = 2.5 * settings.layers.line_width
    result = _layers(500.0, 500.0, 500.0, min_width=schmal)

    entries = advise.advise(settings, profiles.make_profile(), result)

    chosen = next(entry for entry in entries if entry.path == "shell.wall_generator")
    assert chosen.value == "arachne"
    assert chosen.severity == "warning"


def test_a_wall_that_fits_whole_paths_keeps_the_generator() -> None:
    """Ein Vorschlag, der bei jedem Teil erscheint, ist keiner."""
    settings = print_settings.resolve(profiles.make_profile())
    settings = print_settings.with_path(settings, "shell.wall_generator", "classic")
    breit = 6.0 * settings.layers.line_width
    result = _layers(500.0, 500.0, 500.0, min_width=breit)

    entries = advise.advise(settings, profiles.make_profile(), result)

    assert "shell.wall_generator" not in _paths(entries)


def test_fits_ask_for_the_precise_wall_and_a_calmer_acceleration() -> None:
    """Beides zielt auf dasselbe: das Maß, auf das die Passung gerechnet ist."""
    settings = print_settings.resolve(profiles.make_profile())

    entries = advise.advise(settings, profiles.make_profile(), fit_kinds=("clearance",))

    precise = next(entry for entry in entries if entry.path == "shell.precise_outer_wall")
    assert precise.value is True
    calmer = next(entry for entry in entries if entry.path == "speed.outer_wall_acceleration")
    assert calmer.value == advise.CAREFUL_ACCELERATION
    assert calmer.value < settings.speed.outer_wall_acceleration


def test_without_fits_nothing_is_slowed_down() -> None:
    settings = print_settings.resolve(profiles.make_profile())

    entries = advise.advise(settings, profiles.make_profile())

    assert "shell.precise_outer_wall" not in _paths(entries)
    assert "speed.outer_wall_acceleration" not in _paths(entries)


def test_an_overhang_slows_the_bridge_down_to_the_outer_wall() -> None:
    """Über einer Lücke trägt nichts von unten."""
    settings = print_settings.resolve(profiles.make_profile())
    settings = print_settings.with_path(settings, "speed.bridge", 120.0)
    result = _layers(500.0, 500.0, 500.0, overhang=200.0)

    entries = advise.advise(settings, profiles.make_profile(), result)

    chosen = next(entry for entry in entries if entry.path == "speed.bridge")
    assert chosen.value == settings.speed.outer_wall


def test_the_new_settings_reach_the_slicers_that_know_them() -> None:
    """Was ein Slicer nicht kennt, bekommt keinen Eintrag — eine Zuordnung auf
    das Nächstbeste wäre eine Einstellung, die woanders landet.

    CuraEngine hat keinen umschaltbaren Wandgenerator, PrusaSlicer keine
    gesonderte genaue Außenwand. Beide rechnen ohnehin mit variabler
    Bahnbreite.
    """
    settings = print_settings.resolve(profiles.make_profile())

    orca = handover.as_mapping(settings, "orca")
    assert orca["wall_generator"] == settings.shell.wall_generator
    assert orca["bridge_speed"] == f"{settings.speed.bridge:g}"
    assert orca["outer_wall_acceleration"] == f"{settings.speed.outer_wall_acceleration:g}"
    assert orca["ironing_type"] == "no ironing"

    prusa = handover.as_mapping(settings, "prusa")
    assert prusa["perimeter_generator"] == settings.shell.wall_generator
    assert "precise_outer_wall" not in prusa

    cura = handover.as_mapping(settings, "cura")
    assert cura["bridge_wall_speed"] == f"{settings.speed.bridge:g}"
    assert "wall_generator" not in cura


def test_ironing_is_off_until_something_asks_for_it() -> None:
    """Bügeln kostet Zeit und nützt nur auf Flächen, die man sieht oder auf
    denen etwas gleitet."""
    settings = print_settings.resolve(profiles.make_profile())

    assert settings.shell.ironing is False
    assert handover.as_mapping(settings, "orca")["ironing_type"] == "no ironing"

    ironed = print_settings.with_path(settings, "shell.ironing", True)
    assert handover.as_mapping(ironed, "orca")["ironing_type"] == "top"


def test_a_part_on_little_ground_asks_for_a_brim_on_its_own() -> None:
    """Die Plattenhaftung ist die eine Einstellung, die je Teil zählt.

    Der Anlass ist das Gewürzset: zwölf Behälter auf Ø 40 und Streuscheiben,
    die auf drei 1,1-mm-Federarmen stehen. Ein Brim gehört unter die Scheiben
    und unter keinen Behälter — plattenweit gäbe es nur beides oder nichts.
    """
    settings = print_settings.resolve(profiles.make_profile())
    weit = BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(40.0, 40.0, 20.0))

    viel = advise.for_part(settings, weit, footprint=1200.0)
    wenig = advise.for_part(settings, weit, footprint=60.0)

    assert viel == []
    assert [entry.path for entry in wenig] == ["adhesion.kind"]
    assert wenig[0].value == "brim"


def test_a_tall_thin_part_asks_for_one_too() -> None:
    settings = print_settings.resolve(profiles.make_profile())
    schlank = BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(10.0, 10.0, 90.0))

    entries = advise.for_part(settings, schlank, footprint=900.0)

    assert [entry.path for entry in entries] == ["adhesion.kind"]


def test_a_part_keeps_quiet_when_the_plate_already_has_a_brim() -> None:
    """Ein Vorschlag, der das vorschlägt, was schon eingestellt ist, ist keiner."""
    settings = print_settings.resolve(profiles.make_profile())
    settings = print_settings.with_path(settings, "adhesion.kind", "brim")
    eng = BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(40.0, 40.0, 20.0))

    assert advise.for_part(settings, eng, footprint=60.0) == []


def test_an_object_override_carries_the_measures_of_its_group() -> None:
    """Wer die Haftungsart umstellt, braucht auch deren Maß — und die Maße der
    Arten, die nicht gewählt sind, müssen auf null.

    Sonst liefe unter dem einen Teil zusätzlich ein Raft mit, und das fällt
    erst auf der Platte auf.
    """
    settings = print_settings.resolve(profiles.make_profile())
    entries = advise.for_part(
        settings,
        BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=(40.0, 40.0, 20.0)),
        footprint=60.0,
    )

    keys = handover.object_keys(settings, entries, "orca")

    assert keys["brim_type"] == "outer_only"
    assert keys["brim_width"] == f"{settings.adhesion.brim_width:g}"
    assert keys["raft_layers"] == "0"
    assert keys["skirt_loops"] == "0"
    # Nur die betroffene Gruppe — die Wandzahl des Teils ist die der Platte.
    assert "wall_loops" not in keys


def test_an_object_override_carries_only_the_advised_paths() -> None:
    """Ein Rat je Teil schreibt seine Pfade, nicht deren ganze Gruppe (Durchsicht 0.5.1, B1).

    Über die Gruppe bekam ein Teil mit Passungsrat am Bambu P1S 21 Objektwerte
    statt vier, darunter die innere Vollfüllung mit 270 statt Bambus 250 mm/s,
    und der Slicer druckte sie so. Was der Rat nicht nennt, gehört der Platte.
    """
    settings = print_settings.resolve(profiles.make_profile())
    advice = [
        SettingAdvice("speed.outer_wall", 30.0, settings.speed.outer_wall, "Passung"),
        SettingAdvice("shell.wall_count", 4, settings.shell.wall_count, "Passung"),
        SettingAdvice("infill.density", 0.4, settings.infill.density, "Passung"),
    ]

    assert set(handover.object_keys(settings, advice, "orca")) == {
        "outer_wall_speed",
        "wall_loops",
        "sparse_infill_density",
    }
    assert set(handover.object_keys(settings, advice, "prusa")) == {
        "external_perimeter_speed",
        "perimeters",
        "fill_density",
    }


def test_without_advice_a_part_gets_no_override() -> None:
    settings = print_settings.resolve(profiles.make_profile())

    assert handover.object_keys(settings, [], "orca") == {}


def test_a_profile_that_says_nothing_is_no_disagreement(tmp_path: Path) -> None:
    """``nil`` heißt in einem Filamentprofil „dazu sage ich nichts" — der Wert
    bleibt beim Drucker.

    Das als Abweichung zu melden hieße, fünf Zeilen Rauschen neben die drei zu
    stellen, auf die es ankommt: beim Elegoo-PETG waren es der ganze Rückzug
    und das Wischen, alle vier auf ``nil``.
    """
    schweigend = tmp_path / "schweigend.json"
    schweigend.write_text(
        json.dumps(
            {
                "type": "filament",
                "name": "Hersteller PETG",
                "instantiation": "true",
                "filament_retraction_length": ["nil"],
                "filament_wipe": ["nil"],
                "nozzle_temperature": ["250"],
            }
        ),
        encoding="utf-8",
    )
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    settings = print_settings.with_choice(settings, "temperature.nozzle", 240)
    setup = handover.SlicerSetup(
        executable=Path("orca-slicer.exe"), flavour="orca", base_filament=str(schweigend)
    )

    findings = handover.profile_differences(settings, setup)

    assert len(findings) == 1
    named = findings[0].values["settings"]
    assert "nozzle_temperature" in named, "der echte Unterschied bleibt"
    assert "retraction" not in named, "nil ist keine Gegenaussage"
    assert "wipe" not in named


def test_a_profile_name_finds_its_file(tmp_path, monkeypatch) -> None:
    """Der Name gehört in die Projektdatei, die Datei braucht der Slicer.

    Beides muss gehen, und dazwischen fehlte die Auflösung: ``base_process``
    trug einen Namen, ``Path(name).is_file()`` sagte nein, und das
    geschriebene Prozessprofil hatte zweiundvierzig Schlüssel statt
    zweiundsechzig — ohne ``inherits``, ohne ``compatible_printers``. Genau an
    denen prüfte die Orca-Familie die Verträglichkeit, und der Lauf brach mit
    „can not find setting file" ab, bevor das Modell an die Reihe kam.

    Seit dem 26.08.2026 löst Solidon die Kette selbst auf, ``inherits``
    fällt weg — die Bindung bleibt, sie ist der Teil, der bleiben muss.
    """
    from pathlib import Path

    from app.core.export import slicer_profiles

    echte = tmp_path / "0.20mm Standard.json"
    echte.write_text(
        json.dumps(
            {
                "type": "process",
                "name": "0.20mm Standard",
                "inherits": "fdm_process_common",
                "compatible_printers": ["Elegoo Centauri Carbon 2 0.4 nozzle"],
                "layer_height": "0.2",
            }
        ),
        encoding="utf-8",
    )

    entry = slicer_profiles.SlicerProfile(echte, "0.20mm Standard", "process")

    gefragt: list[object] = []

    def suche(_executable, _flavour, kinds=None):
        gefragt.append(kinds)
        return [entry]

    monkeypatch.setattr(slicer_profiles, "find_profiles", suche)
    setup = handover.SlicerSetup(
        executable=Path("elegoo-slicer.exe"), flavour="orca", base_process="0.20mm Standard"
    )

    gefunden = handover.profile_file("0.20mm Standard", setup, "process")
    assert gefunden == echte, "der Name führt zur Datei"
    assert gefragt == [("process",)], "gefragt wird nach der gesuchten Art, nicht nach allen"

    # Ein Pfad geht weiterhin unverändert durch
    assert handover.profile_file(str(echte), setup, "process") == echte

    # Und was das Prozessprofil trägt, kommt aus dem Systemprofil
    settings = print_settings.resolve(
        profiles.make_profile("centauri-carbon-2", "petg"), "standard"
    )
    written = handover.write_config(
        settings, profiles.make_profile("centauri-carbon-2", "petg"), setup, tmp_path
    )
    daten = json.loads(written.process.read_text(encoding="utf-8"))
    # Keine Erbschaft mehr: Die Werte stehen seit dem 26.08.2026
    # ausgeschrieben in der Datei, und ein ``inherits`` daneben lüde
    # die Kette ein zweites Mal — aus einem Bestand, der sich ändern
    # kann, während die geschriebene Datei es nicht tut.
    assert "inherits" not in daten, "die Erbkette ist aufgelöst, nicht verwiesen"
    assert daten["layer_height"] == "0.2", "und ihr Wert steht in der Datei"
    # Die Bindung überlebt das Auflösen — hier die geerbte, weil dieser
    # Aufruf kein eigenes Maschinenprofil kennt (``machine_profile``
    # ist leer). Ohne sie bräche der Slicer mit „process not compatible
    # with printer" ab.
    assert daten["compatible_printers"] == ["Elegoo Centauri Carbon 2 0.4 nozzle"]
    assert daten["name"].startswith("Solidon"), "aber der Name ist Solidons eigener"


def test_a_filament_profile_is_found_by_name_too(tmp_path, monkeypatch) -> None:
    """Derselbe Weg für das Filament — und der war es nicht.

    ``find_profiles`` lässt Filamentprofile weg, wenn niemand nach ihnen
    fragt: sie vervielfachen den Bestand, und die Vorgabe kennt nur Maschinen
    und Prozesse. ``profile_file`` fragte aber nicht nach der Art, die es
    suchte — also lief die Schleife über Maschinen und Prozesse und fand nie
    ein Filament, egal wie es hieß.

    Das kostete mehr als einen Namen: ohne das Herstellerprofil fehlten die
    Temperaturen aller Druckplatten außer der einen, die Solidon selbst setzt.
    Der Slicer wählte „Cool Plate", fand dort seine eigenen 35 Grad, und ein
    PETG-Druck ging mit kaltem Bett hinaus.
    """
    from pathlib import Path

    from app.core.export import slicer_profiles

    datei = tmp_path / "Elegoo PETG PRO.json"
    datei.write_text(json.dumps({"name": "Elegoo PETG PRO"}), encoding="utf-8")

    entry = slicer_profiles.SlicerProfile(datei, "Elegoo PETG PRO", "filament")

    def suche(_executable, _flavour, kinds=None):
        # Genau wie im Bestand: ohne Nachfrage gibt es keine Filamentprofile.
        return [entry] if kinds and "filament" in kinds else []

    monkeypatch.setattr(slicer_profiles, "find_profiles", suche)
    setup = handover.SlicerSetup(
        executable=Path("elegoo-slicer.exe"), flavour="orca", base_filament="Elegoo PETG PRO"
    )

    assert handover.profile_file("Elegoo PETG PRO", setup, "filament") == datei


def test_a_project_file_carries_its_values_written_out(tmp_path, monkeypatch) -> None:
    """Eine Projektdatei kennt kein ``inherits`` — sie muss alles enthalten.

    Ein Profil darf sich auf seine Erbkette verlassen: der Slicer lädt es und
    löst selbst auf. Ein Projekt nicht. Was darin fehlt, füllt der Slicer aus
    dem Profil, das gerade eingestellt ist — und das ist nicht Solidons.

    Genau daran ging ein Druck vorbei: die 3MF trug 122 der 546 Schlüssel, in
    ihr standen drei Wände, gedruckt wurden zwei, und der Unterschied waren
    127 Gramm. Geprüft wird deshalb, dass die Erbkette **aufgelöst** wird und
    die eigene Wahl des Kunden trotzdem obenauf liegt — aber nur sie: Die
    Stufe ist keine Wahl (Konzept Herstellerprofil, Entscheidung D).
    """
    from pathlib import Path

    from app.core.export import slicer_profiles

    geerbt = tmp_path / "basis.json"
    geerbt.write_text(
        json.dumps({"name": "basis", "wall_loops": "2", "bridge_angle": "45"}),
        encoding="utf-8",
    )

    entry = slicer_profiles.SlicerProfile(geerbt, "basis", "process")

    monkeypatch.setattr(slicer_profiles, "find_profiles", lambda *_, **__: [entry])
    monkeypatch.setattr(
        slicer_profiles, "resolve_values", lambda _, **__: {"wall_loops": "2", "bridge_angle": "45"}
    )

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile, "standard")
    setup = handover.SlicerSetup(
        executable=Path("elegoo-slicer.exe"), flavour="orca", base_process="basis"
    )

    werte = handover.project_settings(settings, profile, setup)
    gewaehlt = handover.project_settings(
        print_settings.with_choice(settings, "shell.wall_count", 4), profile, setup
    )

    assert werte["bridge_angle"] == "45", "was nur geerbt ist, steht trotzdem in der Datei"
    assert werte["wall_loops"] == "2", "ohne eigene Wahl gilt der Hersteller"
    assert gewaehlt["wall_loops"] == "4", "die eigene Wahl liegt über dem geerbten"


def test_the_creality_window_says_which_printer_to_pick() -> None:
    """Creality Print fragt beim Öffnen einer fremden 3MF nach dem Drucker.

    Vorgewählt ist der, der dort gerade eingestellt ist — am 29.09.2026 ein
    CR-10 für eine Übergabe an den K1 (RM-164). Prozess und Filament nimmt das
    Fenster aus dessen Profilen, gemessen mit 7.2.2 und 7.3.0 an
    ``full_print_config.json``: Vier gewählte Wände und 37 % Füllung kamen nicht
    an. Der Befund nennt den Drucker der Übergabe und den Weg mit Solidons
    Einstellungen; andere Programme bekommen ihn nicht.
    """
    creality = handover.SlicerSetup(
        executable=Path("CrealityPrint.exe"),
        flavour="orca",
        machine_profile="C:/Creality/machine/Creality K1 0.4 nozzle.json",
    )
    befunde = handover.window_findings(creality)
    assert [befund.code for befund in befunde] == ["slicer.window_asks_for_the_printer"]
    assert "„Creality K1 0.4 nozzle“" in str(befunde[0].message)
    assert "eigenen Profilen" in str(befunde[0].message)
    assert "„Slicen“" in str(befunde[0].message)
    assert (
        handover.window_findings(
            handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")
        )
        == []
    )


def test_the_project_settings_ids_are_names_not_paths() -> None:
    """Regel 12: Der Pfad des eigenen Rechners reist nicht in einer Datei
    mit, die weitergegeben wird — und die Orca-Familie trifft mit einem Pfad
    ohnehin kein Preset. Prozess und Filament tragen den Solidon-Namen, unter
    dem `write_config` sie wirklich schreibt; unter dem Namen eines
    Systemprofils lüde der Slicer sein eigenes darunter."""
    from pathlib import Path

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile, "standard")
    root = "C:/Program Files/ElegooSlicer/resources/profiles/Elegoo"
    setup = handover.SlicerSetup(
        executable=Path("elegoo-slicer.exe"),
        flavour="orca",
        machine_profile=f"{root}/machine/ECC2/Elegoo Centauri Carbon 2 0.4 nozzle.json",
        base_process=f"{root}/process/ECC2/0.12mm Fine @Elegoo CC2 0.4 nozzle.json",
        base_filament=f"{root}/filament/ECC2/Elegoo PLA @ECC2.json",
    )

    werte = handover.project_settings(settings, profile, setup, extruders=2)

    assert werte["printer_settings_id"] == "Elegoo Centauri Carbon 2 0.4 nozzle"
    assert werte["print_settings_id"] == f"Solidon {settings.title}"
    assert werte["filament_settings_id"] == ["Solidon Elegoo PLA @ECC2"] * 2
    for key in ("printer_settings_id", "print_settings_id"):
        assert "/" not in str(werte[key]) and "\\" not in str(werte[key])


def test_a_profile_name_with_dots_is_not_truncated() -> None:
    """`.stem` auf „0.12mm Fine @…" schnitte mitten ins Maß — ein Name, der
    schon ein Name ist, bleibt unangetastet."""
    from pathlib import Path

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile, "standard")
    setup = handover.SlicerSetup(
        executable=Path("elegoo-slicer.exe"),
        flavour="orca",
        machine_profile="Elegoo Centauri Carbon 2 0.4 nozzle",
        base_process="0.12mm Fine @Elegoo CC2 0.4 nozzle",
    )

    werte = handover.project_settings(settings, profile, setup)

    assert werte["printer_settings_id"] == "Elegoo Centauri Carbon 2 0.4 nozzle"


def test_the_bed_temperature_reaches_every_plate(tmp_path) -> None:
    """Die Temperatur gehört dem Material, der Plattentyp der Maschine.

    Solidon weiß nicht, welche Platte aufliegt — also bekommt jede denselben
    Wert. Sonst steht die Betttemperatur auf genau einer Platte, der Slicer
    liest eine andere, und niemand hat über diesen Wert entschieden.
    """
    from pathlib import Path

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile, "standard")
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")

    werte = handover.project_settings(settings, profile, setup)

    erwartet = [str(settings.temperature.bed)]
    for platte in handover.PLATE_KINDS:
        assert werte[f"{platte}_plate_temp"] == erwartet, f"{platte} bekommt dieselbe Temperatur"


def test_cura_gets_its_values_on_the_extruder_too(tmp_path) -> None:
    """``CuraEngine`` liest das meiste vom Extruder-Zug, nicht global.

    Was nur global steht, wird nicht übernommen, sondern von der Vorgabe der
    Definition überschrieben. Gemessen an einem 20-mm-Würfel gegen PrusaSlicer
    mit denselben Einstellungen: 748 mm Filament statt 1410, weil Wandzahl,
    Bahnbreite und Füllung nie beim Extruder ankamen. Nur auf dem Zug ist
    ebenso falsch — dann fehlen der Zeitrechnung die Geschwindigkeiten (38,4
    Minuten statt 20,9).
    """
    from pathlib import Path

    setup = handover.SlicerSetup(executable=Path("CuraEngine.exe"), flavour="cura")
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    config = handover.write_config(print_settings.resolve(profile), profile, setup, tmp_path)

    command = handover._command(setup, [tmp_path / "cube.stl"], config, tmp_path)
    assert "-e0" in command, "ohne Extruder-Zug kommt kein Wert dort an"
    wall = [index for index, entry in enumerate(command) if entry.startswith("wall_line_count=")]
    assert len(wall) == 2, "einmal global, einmal auf dem Zug"
    assert wall[0] < command.index("-e0") < wall[1], "und in dieser Reihenfolge"


def test_cura_runs_without_its_verbose_log(tmp_path) -> None:
    """Mit ``-v`` schrieb CuraEngine am Eiffelturm aus dem Korpus 12,3 MB
    Protokoll, über Solidons Sammelgrenze von 8 MiB — der Lauf endete mit
    „mehr Ausgabe, als gesammelt wird" und ohne Druckdatei (RM-252). Ohne den
    Schalter waren es 50 kB."""
    from pathlib import Path

    setup = handover.SlicerSetup(executable=Path("CuraEngine.exe"), flavour="cura")
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    config = handover.write_config(print_settings.resolve(profile), profile, setup, tmp_path)

    command = handover._command(setup, [tmp_path / "cube.stl"], config, tmp_path)
    assert command[1] == "slice"
    assert "-v" not in command


def test_curas_first_line_width_is_a_share_not_a_size() -> None:
    """``initial_layer_line_width_factor`` will Prozent von ``line_width``.

    Solidon schrieb den Millimeterwert hinein: 0,449 wurde zu 0,449 Prozent,
    und die erste Schicht bekam ein Zweihundertstel der Breite, die sie haben
    sollte. Bei PrusaSlicer ist dasselbe Feld ein Maß — deshalb fiel es nur
    gegen einen echten Lauf auf.
    """
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.resolve(profile)
    written = handover.as_mapping(settings, "cura")

    share = float(written["initial_layer_line_width_factor"])
    expected = settings.layers.first_layer_line_width / settings.layers.line_width * 100.0
    # Geschrieben wird mit sechs geltenden Ziffern, wie jede andere Zahl auch.
    assert share == pytest.approx(expected, abs=1e-3)
    assert share > 50.0, "ein Anteil, kein Millimeterwert"


def test_cura_switches_acceleration_on_before_using_it(tmp_path) -> None:
    """Ohne den Schalter rechnet ``CuraEngine`` mit ``machine_acceleration``
    weiter und übergeht, was daneben steht."""
    from pathlib import Path

    setup = handover.SlicerSetup(executable=Path("CuraEngine.exe"), flavour="cura")
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    config = handover.write_config(print_settings.resolve(profile), profile, setup, tmp_path)
    lines = config.process.read_text(encoding="utf-8").splitlines()

    assert "acceleration_enabled=true" in lines
    assert any(line.startswith("acceleration_print=") for line in lines)


def test_an_unknown_profile_name_is_no_crash(tmp_path, monkeypatch) -> None:
    """Ein Name, den dieser Slicer nicht kennt, liefert nichts — und keinen
    Stapelabzug."""
    from pathlib import Path

    from app.core.export import slicer_profiles

    # Ausdrücklich gesetzt, nicht der Maschine überlassen: Ohne Namen fragt die
    # Maschinenart den Slicer, welcher Drucker dort eingestellt ist, und diese
    # Zusicherung gilt dem Fall, in dem auch das nichts ergibt.
    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_: "")

    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")
    assert handover.profile_file("gibt es nicht", setup, "process") is None
    assert handover.profile_file("", setup, "machine") is None


def test_without_a_chosen_printer_the_slicers_own_selection_counts(tmp_path, monkeypatch) -> None:
    """Ohne gewähltes Druckerprofil fragt die Übergabe den Slicer.

    **Der Fall kam vom Drucker.** Am 03.09.2026 lehnte ElegooSlicer eine
    übergebene Datei ab: „Relative Extruderadressierung erfordert das
    Zurücksetzen der Extruderposition bei jeder Schicht … Fügen Sie G92 E0 zu
    layer_gcode hinzu." Ohne Maschinenprofil schrieb Solidon die Maschinenseite
    gar nicht — kein Startcode, kein Schichtwechselcode —, und der Slicer
    füllte sie mit seinen eigenen Vorgaben, die nicht zusammenpassen. Das
    Herstellerprofil bringt das ``G92 E0`` selbst mit.
    """
    from pathlib import Path

    from app.core.export import slicer_profiles

    echte = tmp_path / "Elegoo Centauri Carbon 2 0.4 nozzle.json"
    echte.write_text("{}", encoding="utf-8")

    entry = slicer_profiles.SlicerProfile(echte, "Elegoo Centauri Carbon 2 0.4 nozzle", "machine")

    monkeypatch.setattr(
        slicer_profiles, "chosen_machine", lambda *_: "Elegoo Centauri Carbon 2 0.4 nozzle"
    )
    monkeypatch.setattr(slicer_profiles, "find_profiles", lambda *_, **__: [entry])
    monkeypatch.setattr(
        slicer_profiles,
        "resolve_values",
        lambda _, **__: {"before_layer_change_gcode": ";BEFORE_LAYER_CHANGE" + chr(10) + "G92 E0"},
    )

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")

    assert handover.machine_for(setup, profile) == "Elegoo Centauri Carbon 2 0.4 nozzle"

    werte = handover.project_settings(print_settings.resolve(profile, "standard"), profile, setup)

    assert "G92 E0" in str(werte["before_layer_change_gcode"]), (
        "ohne diese Zeile nimmt der Slicer die Datei nicht an"
    )


def test_the_same_printer_with_another_nozzle_hands_over_the_fitting_variant(
    monkeypatch, tmp_path
) -> None:
    """Derselbe Drucker, andere Düse — geschrieben wird die passende Herstellerseite.

    **Gemessen am 16.09.2026.** ElegooSlicer stand auf „Elegoo Centauri Carbon
    2 0.2 nozzle", das Projekt rechnete auf demselben Gerät mit 0,4. Der
    Druckervergleich sagte „passt" — der Name nennt den Drucker, und die Düse
    steht nur hinten dran —, also ging die Maschinenseite der 0,2er Düse
    hinaus, daneben ein Prozess mit ``line_width`` 0,42. Der Slicer nahm den
    widersprüchlichen Auftrag nicht an und fiel auf seine Vorgaben zurück:
    **jede** Linienbreite stand auf null, und er meldete „zu geringe
    Linienbreite". Von Solidons Werten kam kein einziger an.

    Die echten Herstellerdateien tragen kein eigenes ``vendor``-Feld. Ihre
    Herkunft aus ``resources/profiles/Elegoo/machine/ECC2`` belegt den Hersteller
    und muss bis in die ausgeschriebene Maschinenseite der 3MF erhalten bleiben.
    """
    from pathlib import Path

    bestand = [
        _elegoo_nozzle_profile(tmp_path, 0.2),
        _elegoo_nozzle_profile(tmp_path, 0.4),
    ]
    assert all(not entry.vendor for entry in bestand)
    assert all(slicer_profiles.machine_vendor(entry) == "Elegoo" for entry in bestand)
    monkeypatch.setattr(
        slicer_profiles, "chosen_machine", lambda *_: "Elegoo Centauri Carbon 2 0.2 nozzle"
    )
    monkeypatch.setattr(slicer_profiles, "find_profiles", lambda *_, **__: bestand)

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")
    assert profile.printer.nozzle_diameter == 0.4, "sonst prüft der Fall etwas anderes"

    selected = handover.machine_for(setup, profile)
    assert selected == str(bestand[1].path), (
        "die gewählte Variante bleibt über ihre Datei eindeutig"
    )

    machine_page = handover.project_settings(
        print_settings.resolve(profile, "standard"), profile, setup
    )
    assert machine_page["printer_settings_id"] == bestand[1].name
    assert machine_page["machine_start_gcode"] == "G28 ; Elegoo 0.4 nozzle"
    assert machine_page["nozzle_diameter"] == ["0.4"]
    machine_file = handover._orca_machine(replace(setup, machine_profile=selected))
    assert machine_file["name"] == f"Solidon {bestand[1].name}"
    assert machine_file["machine_start_gcode"] == "G28 ; Elegoo 0.4 nozzle"


def test_source_profile_name_resolves_a_prusa_bundle_reference(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Eine portable Prusa-Abschnittskennung liefert den echten Profilnamen."""
    path = tmp_path / "PrusaResearch.ini"
    path.write_text("[printer:Original Prusa MK4S HF0.4]\n", encoding="utf-8")
    profile = slicer_profiles.SlicerProfile(
        path=path,
        name="Original Prusa MK4S HF0.4",
        kind="machine",
        section="printer:Original Prusa MK4S HF0.4",
    )
    monkeypatch.setattr(slicer_profiles, "find_profiles", lambda *_args, **_kwargs: [profile])
    setup = handover.SlicerSetup(Path("prusa-slicer.exe"), "prusa")

    assert (
        handover._source_profile_name(slicer_profiles.identity(profile), setup, "machine")
        == profile.name
    )


def test_source_profile_name_resolves_a_cura_instance_reference(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Eine Cura-Instanzkennung bleibt intern und wird beim Schreiben lesbar."""
    path = tmp_path / "machine_instances" / "Centauri.def.json"
    path.parent.mkdir(parents=True)
    path.write_text("{}", encoding="utf-8")
    profile = slicer_profiles.SlicerProfile(
        path=path,
        name="Elegoo Centauri Carbon 2 Werkstatt",
        kind="machine",
        section="Werkstatt",
        cura_instance=tmp_path / "machine_instances" / "Centauri.global.cfg",
    )
    monkeypatch.setattr(slicer_profiles, "find_profiles", lambda *_args, **_kwargs: [profile])
    setup = handover.SlicerSetup(Path("cura.exe"), "cura")

    assert (
        handover._source_profile_name(slicer_profiles.identity(profile), setup, "machine")
        == profile.name
    )


def test_source_profile_name_does_not_guess_between_duplicate_profiles(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Mehrdeutige Namen bleiben Namen, keiner der gleichnamigen Pfade gewinnt."""
    profiles_with_same_name = []
    for relative in ("a/maschine.json", "b/maschine.json"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True)
        path.write_text(
            json.dumps({"type": "machine", "name": "Meine Maschine", "instantiation": "true"}),
            encoding="utf-8",
        )
        profiles_with_same_name.append(
            slicer_profiles.SlicerProfile(path, "Meine Maschine", "machine")
        )
    monkeypatch.setattr(
        slicer_profiles, "find_profiles", lambda *_args, **_kwargs: profiles_with_same_name
    )
    setup = handover.SlicerSetup(Path("orca.exe"), "orca")

    assert handover.profile_source("Meine Maschine", setup, "machine") is None
    assert handover._source_profile_name("Meine Maschine", setup, "machine") == "Meine Maschine"


def test_a_nozzle_that_no_variant_offers_hands_over_no_machine(monkeypatch, tmp_path) -> None:
    """Gibt es die Düse des Projekts nicht, bleibt die Maschinenseite leer.

    Die Gegenprobe zum Test darüber: Korrigiert wird nur **innerhalb**
    desselben Geräts. Ist dort keine passende Düse zu haben, wird nicht die
    nächstbeste genommen — das wäre wieder der widersprüchliche Auftrag, nur
    mit einer anderen Zahl (Regel 21).
    """
    from pathlib import Path

    nur_klein = [_elegoo_nozzle_profile(tmp_path, 0.2)]
    monkeypatch.setattr(
        slicer_profiles, "chosen_machine", lambda *_: "Elegoo Centauri Carbon 2 0.2 nozzle"
    )
    monkeypatch.setattr(slicer_profiles, "find_profiles", lambda *_, **__: nur_klein)

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")

    assert handover.machine_for(setup, profile) == ""


def test_a_printer_that_is_not_the_projects_is_left_alone(monkeypatch) -> None:
    """Der Slicer steht auf einem anderen Drucker — dann wird nichts übernommen.

    **Gemessen und keine Annahme:** Auf Roberts Rechner stand ElegooSlicer auf
    einem „Bambu Lab A1 0.2 nozzle", während das Projekt einem Centauri Carbon
    2 galt. Ein blind übernommenes Profil brächte den Startcode, den Bauraum
    und die Düse eines fremden Druckers in die Datei; ein Homing-Befehl der
    falschen Maschine fährt die Düse ins Bett. Lieber keine Maschinenseite als
    die falsche (Regel 21).
    """
    from pathlib import Path

    from app.core.export import slicer_profiles

    gefragt: list[str] = []

    def gemerkt(flavour, _executable) -> str:
        gefragt.append(flavour)
        return "Bambu Lab A1 0.2 nozzle"

    monkeypatch.setattr(slicer_profiles, "chosen_machine", gemerkt)

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")

    assert handover.machine_for(setup, profile) == ""
    assert gefragt == ["orca"], "gefragt wird einmal, übernommen wird nichts"


def test_the_customer_hears_that_the_slicer_stands_on_another_printer(monkeypatch) -> None:
    """Keine Maschinenseite ist richtig — und still ist sie falsch (Regel 21).

    **Genau Roberts Fall vom 03.09.2026.** ElegooSlicer stand auf einem
    „Bambu Lab A1 0.2 nozzle", das Projekt galt einem Centauri Carbon 2.
    ``machine_for`` weigert sich seitdem, das fremde Profil zu nehmen — richtig,
    denn ein Homing-Befehl der falschen Maschine fährt die Düse ins Bett. Es
    weigerte sich aber **schweigend**: Die Begründung ging in eine Protokollzeile,
    die niemand liest, und der Kunde bekam dieselbe abgelehnte Datei wie zuvor,
    nur ohne zu erfahren, warum.

    Gemessen: 73 Schlüssel ohne Maschinenseite, 160 mit ihr.
    """
    from pathlib import Path

    from app.core.export import slicer_profiles

    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_: "Bambu Lab A1 0.2 nozzle")
    # ElegooSlicer kennt den Centauri Carbon 2; der Kunde kann umstellen (RM-431).
    monkeypatch.setattr(slicer_profiles, "supports_printer", lambda *_: True)

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")

    findings = handover.machine_missing(setup, profile)

    assert [finding.code for finding in findings] == ["slicer.machine_mismatch"]
    assert findings[0].severity == "warning"
    assert findings[0].suggestions, "Regel 17: ein Befund endet nie mit „geht nicht"
    werte = findings[0].values
    assert "Bambu Lab A1 0.2 nozzle" in str(werte["machine"]), "der Kunde muss den Namen sehen"


def test_nothing_is_said_when_the_machine_side_is_there(monkeypatch) -> None:
    """Steht die Maschine, gibt es nichts zu melden — auch keine Beruhigung."""
    from pathlib import Path

    from app.core.export import slicer_profiles

    monkeypatch.setattr(
        slicer_profiles, "chosen_machine", lambda *_: "Elegoo Centauri Carbon 2 0.4 nozzle"
    )

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")

    assert handover.machine_missing(setup, profile) == []
    assert (
        handover.machine_missing(
            handover.SlicerSetup(
                executable=Path("elegoo-slicer.exe"), flavour="orca", machine_profile="Meine"
            ),
            profile,
        )
        == []
    ), "eine selbst getroffene Wahl steht, und über sie wird nicht geredet"


def test_a_slicer_that_names_no_machine_at_all_is_its_own_message(monkeypatch) -> None:
    """Frisch installiert und nie eingerichtet — dasselbe Ergebnis, ein anderer Rat.

    Zwei Fälle, zwei Sätze: Wer auf dem falschen Drucker steht, wechselt ihn im
    Slicer; wer noch gar keinen eingerichtet hat, kann das nicht — er wählt in
    Solidon ein Maschinenprofil oder richtet den Slicer erst ein. Ein Rat, der
    ins Leere zeigt, ist keiner.
    """
    from pathlib import Path

    from app.core.export import slicer_profiles

    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_: "")
    # Der Slicer **kennt** diesen Drucker, er steht nur auf keinem. Genau das
    # unterscheidet diesen Fall von dem darunter, und ohne die Angabe fiele
    # der Test in den anderen Zweig: eine leere Programmdatei hat keinen
    # Bestand, in dem etwas zu finden wäre.
    monkeypatch.setattr(slicer_profiles, "supports_printer", lambda *_: True)

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")

    findings = handover.machine_missing(setup, profile)

    assert [finding.code for finding in findings] == ["slicer.machine_unset"]
    assert findings[0].suggestions


def test_a_slicer_that_does_not_know_this_printer_says_so_instead(monkeypatch) -> None:
    """Ein Rat, der ins Leere zeigt, ist keiner — und genau das war er hier.

    „Wählen Sie das Maschinenprofil in den Druckeinstellungen" setzt voraus,
    dass es eines gibt. Bringt der Slicer für diesen Drucker gar keines mit,
    sucht der Kunde in einer leeren Liste. Der Unterschied ist messbar
    (08.09.2026): ElegooSlicer kennt 1001 Drucker und den Centauri Carbon 2
    darunter, PrusaSlicer kennt 261 und ihn nicht.
    """
    from pathlib import Path

    from app.core.export import slicer_profiles

    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_: "")
    monkeypatch.setattr(slicer_profiles, "supports_printer", lambda *_: False)

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")

    findings = handover.machine_missing(setup, profile)

    assert [finding.code for finding in findings] == ["slicer.printer_unknown"]
    assert findings[0].suggestions, "Regel 17: auch dieser Fall nennt den nächsten Schritt"


def test_a_slicer_set_to_another_printer_it_cannot_swap_for_ours_says_it_does_not_know_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RM-431: Allgemeiner Drucker mit PrusaSlicer, das zuletzt auf einem
    anderen Drucker stand. „Stellen Sie den Slicer auf denselben Drucker um“
    zeigte ins Leere — das Bündel kennt keinen allgemeinen Drucker."""
    from pathlib import Path

    from app.core.export import slicer_profiles

    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_: "Original Prusa MK4S")
    monkeypatch.setattr(slicer_profiles, "supports_printer", lambda *_: False)
    profile = profiles.make_profile("generic-220", "pla")
    setup = handover.SlicerSetup(executable=Path("prusa-slicer-console.exe"), flavour="prusa")

    findings = handover.machine_missing(setup, profile)

    assert [finding.code for finding in findings] == ["slicer.printer_unknown"]
    assert findings[0].values["printer"] == profile.printer.title


def test_a_chosen_printer_is_never_second_guessed(monkeypatch) -> None:
    """Wer selbst gewählt hat, wird nicht gefragt — auch nicht freundlich."""
    from pathlib import Path

    from app.core.export import slicer_profiles

    gefragt: list[str] = []
    monkeypatch.setattr(
        slicer_profiles, "chosen_machine", lambda flavour, _exe: gefragt.append(flavour) or ""
    )

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    setup = handover.SlicerSetup(
        executable=Path("elegoo-slicer.exe"), flavour="orca", machine_profile="Meine Maschine"
    )

    assert handover.machine_for(setup, profile) == "Meine Maschine"
    assert gefragt == [], "eine getroffene Wahl steht"


def test_a_spread_overhang_is_no_reason_for_supports() -> None:
    """Die Summe allein sprach ein Fehlurteil.

    Ein Becher verteilt seinen Überhang über dreihundert Schichten — keine
    trägt mehr als ein paar Quadratmillimeter, und jede Wand fängt das in sich
    auf. Gemessen am echten Teil: 239,8 mm² Summe, 3,7 mm² auf der schlimmsten
    Schicht. Er bekam trotzdem dieselbe Stützenwarnung wie ein Deckel, dessen
    Lochplatte mit 845,6 mm² auf einmal über einem Hohlraum beginnt.
    """
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile, "standard")
    assert settings.support.style == "none", "die Vorgabe kommt ohne Stützen"

    # Dreihundert Schichten à 0,8 mm² — Summe 240, keine einzelne kritisch.
    verteilt = _layers(*([200.0] * 300), overhang=0.8)
    # Zwei Schichten, davon eine mit 400 mm² auf einmal.
    geballt = _layers(200.0, 200.0, overhang=400.0)

    zu_verteilt = advise.advise(settings, profile, verteilt)
    zu_geballt = advise.advise(settings, profile, geballt)

    assert not [a for a in zu_verteilt if a.path == "support.style"], (
        "was sich über dreihundert Schichten verteilt, trägt sich selbst"
    )
    assert [a for a in zu_geballt if a.path == "support.style"], (
        "was auf einer Schicht anfängt, braucht Stützen"
    )


def test_the_worst_layer_is_reported_separately() -> None:
    """Summe und Spitze sind zwei Zahlen, und nur die zweite entscheidet."""
    from app.core.slice.analysis import total_overhang, worst_overhang

    result = _layers(200.0, 200.0, 200.0, overhang=50.0)

    assert total_overhang(result) == pytest.approx(150.0)
    assert worst_overhang(result) == pytest.approx(50.0)
    assert worst_overhang(_layers()) == 0.0, "ohne Schichten kein Überhang"


# --- mehrere Filamente auf einer Platte (§20, §29) ------------------------------


def _filament_profile(directory: Path, name: str, **werte: object) -> Path:
    datei = directory / f"{name}.json"
    datei.write_text(json.dumps({"name": name, **werte}), encoding="utf-8")
    return datei


def test_every_filament_profile_of_a_run_carries_the_same_keys(tmp_path: Path) -> None:
    """Befund Robert, 19.09.2026: „beim Öffnen im Slicer Fehler".

    Sein Regal aus einer Bambu-3MF trug neben der PLA-Spule aus dem Lager einen
    deklarierten PETG-Slot ohne eigenes Profil. Die PLA-Spule erbte das
    Herstellerprofil des Laufs mit seinen 65 Schlüsseln, die PETG-Spule kam
    mit Solidons 34 — und der ElegooSlicer brach mit 0xC0000409 ab, ohne ein
    Wort. Jedes Filamentprofil eines Laufs trägt jetzt dieselben Schlüssel;
    was Solidon selbst setzt, bleibt dabei je Spule das eigene.
    """
    from app.core.types import MaterialSlot

    house = _filament_profile(
        tmp_path,
        "Haus PLA",
        nozzle_temperature=["215"],
        filament_start_gcode=["; Haus PLA start"],
        pressure_advance=["0.03"],
        filament_vendor=["Haus"],
    )
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(
        executable=Path("elegoo-slicer.exe"), flavour="orca", base_filament=str(house)
    )
    foreign = MaterialSlot(index=0, name="SUNLU PETG @BBL A1", material_type="PETG")
    local = MaterialSlot(index=1, name="PLAOrange", material_type="PLA")

    config = handover.write_config(settings, profile, setup, tmp_path, [foreign, local])

    petg, pla = (json.loads(f.read_text(encoding="utf-8")) for f in config.filaments)
    assert set(petg) == set(pla), (
        f"ungleiche Schlüssel: nur PETG {sorted(set(petg) - set(pla))}, "
        f"nur PLA {sorted(set(pla) - set(petg))}"
    )
    assert petg["nozzle_temperature"] != pla["nozzle_temperature"], (
        "jede Spule fährt weiter ihre eigene Temperatur"
    )
    assert petg["filament_type"] == ["PETG"] and pla["filament_type"] == ["PLA"]
    assert pla["filament_start_gcode"] == ["; Haus PLA start"], "die PLA-Spule erbt den Hersteller"
    assert petg["filament_start_gcode"] == ["; Haus PLA start"], (
        "was Solidon nicht setzt, kommt aus dem Nachbarprofil statt zu fehlen"
    )


def test_a_filament_with_several_colours_reaches_the_orca_family_whole(tmp_path: Path) -> None:
    """Die Orca-Familie kennt mehrfarbiges Filament: ``filament_multi_colour``
    trägt alle Farben durch Leerzeichen getrennt, ``filament_colour_type``
    „1" die Abschnitte, ``filament_colour`` weiter die erste (§20).

    Geschrieben nur, wo es mehrere sind — und in der Projektdatei dann für
    jede Spule der Platte, denn dort ist es eine Liste je Extruder.
    """
    from app.core.types import MaterialSlot

    pla = _filament_profile(tmp_path, "Haus PLA", nozzle_temperature=["210"])
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")
    dual = MaterialSlot(
        index=0,
        name="Silk Dual",
        colour=(1.0, 0.0, 0.0),
        extra_colours=((0.0, 0.0, 1.0),),
        material=str(pla),
    )
    plain = MaterialSlot(index=1, name="Weiß", colour=(1.0, 1.0, 1.0), material=str(pla))

    config = handover.write_config(settings, profile, setup, tmp_path, [dual, plain])
    erste, zweite = (json.loads(f.read_text(encoding="utf-8")) for f in config.filaments)
    assert erste["filament_colour"] == ["#FF0000"], "die erste Farbe bleibt die Farbe"
    assert erste["filament_multi_colour"] == ["#FF0000 #0000FF"]
    assert erste["filament_colour_type"] == ["1"]
    # Im selben Lauf führt auch die einfarbige Spule die Schlüssel — mit ihrer
    # eigenen Farbe, denn alle Filamentprofile eines Laufs tragen dieselben
    # Schlüssel (``_with_equal_keys``); allein bleibt sie ohne.
    assert zweite["filament_multi_colour"] == ["#FFFFFF"]
    assert zweite["filament_colour_type"] == ["1"]
    (tmp_path / "allein").mkdir()
    alone = handover.write_config(settings, profile, setup, tmp_path / "allein", [plain])
    only = json.loads(alone.filaments[0].read_text(encoding="utf-8"))
    assert "filament_multi_colour" not in only, "einfarbig allein bekommt die Schlüssel nicht"

    document = handover.project_settings(settings, profile, setup, slots=[dual, plain])
    assert document["filament_colour"] == ["#FF0000", "#FFFFFF"]
    assert document["filament_multi_colour"] == ["#FF0000 #0000FF", "#FFFFFF"], (
        "in der Projektdatei führt jede Spule den Schlüssel — eine Liste je Extruder"
    )
    assert document["filament_colour_type"] == ["1", "1"]

    only_plain = handover.project_settings(settings, profile, setup, slots=[plain])
    assert "filament_multi_colour" not in only_plain

    prusa = handover.SlicerSetup(executable=Path("prusa-slicer-console.exe"), flavour="prusa")
    (tmp_path / "prusa").mkdir()
    written = handover.write_config(settings, profile, prusa, tmp_path / "prusa", [dual]).written
    assert "filament_multi_colour" not in written and "filament_colour_type" not in written, (
        "PrusaSlicer kennt eine Farbe je Filament — die Mehrfarbschlüssel gehen nur an Orca"
    )


def test_project_settings_keep_profile_wide_lists_flat(tmp_path: Path) -> None:
    """Profil-Metadaten und Vektoren sind keine zweite Extruderliste.

    Ein äußerer Eintrag je Spule um eine bereits vollständige Liste erzeugte
    ``[[], []]`` beziehungsweise ``[[a, b], [a, b]]``. Diese Form kennt das
    Slicerformat nicht; beschreibende Felder fallen weg, ein gemeinsamer
    Profilwert bleibt flach.
    """
    filament = _filament_profile(
        tmp_path,
        "Haus PLA",
        compatible_prints=[],
        filament_custom_curve=["a", "b"],
    )
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.resolve(profile)
    slots = (
        MaterialSlot(index=0, name="PLA Weiß", material=str(filament)),
        MaterialSlot(index=1, name="PLA Schwarz", material=str(filament)),
    )
    setup = handover.SlicerSetup(executable=Path("orca.exe"), flavour="orca")

    document = handover.project_settings(settings, profile, setup, slots=slots)

    assert "compatible_prints" not in document, "Profilbeschreibung ist kein Druckwert"
    assert document["filament_custom_curve"] == ["a", "b"], (
        "ein gemeinsamer Vektor bleibt eine flache Liste"
    )


def test_every_slot_gets_its_own_filament(tmp_path: Path) -> None:
    """Ein Slot ist ein Filament, kein Objektmerkmal (§20).

    Ein Schriftzug in Weiß auf einem Gehäuse in Schwarz sind zwei Spulen mit
    zwei Temperaturen. Solange die Übergabe eine Datei kannte, bekam jeder
    Slot dasselbe Filament — die zweite Farbe fuhr mit den Werten der ersten,
    und im G-Code stand nirgends, dass das so gemeint war.
    """
    from app.core.types import MaterialSlot

    petg = _filament_profile(
        tmp_path, "Haus PETG", nozzle_temperature=["240"], filament_max_volumetric_speed=["5"]
    )
    pla = _filament_profile(
        tmp_path, "Haus PLA", nozzle_temperature=["210"], filament_max_volumetric_speed=["21"]
    )
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")
    slots = [
        MaterialSlot(index=0, name="Gehäuse", colour=(0.0, 0.0, 0.0), material=str(petg)),
        MaterialSlot(
            index=1,
            name="Schrift",
            colour=(1.0, 1.0, 1.0),
            material=str(pla),
            material_type="PLA",
        ),
    ]

    config = handover.write_config(settings, profile, setup, tmp_path, slots)

    assert len(config.filaments) == 2, "je Slot ein Profil"
    erste, zweite = (json.loads(f.read_text(encoding="utf-8")) for f in config.filaments)
    assert erste["nozzle_temperature"] == ["240"], "der Hersteller des Slots gilt"
    assert zweite["nozzle_temperature"] == ["210"], "und für den zweiten ein anderer"
    assert zweite["filament_max_volumetric_speed"] == ["21"]
    assert zweite["filament_type"] == ["PLA"], "der Typ reist mit derselben Spule"
    assert erste["filament_colour"] == ["#000000"], "die Farbe kommt vom Slot"
    assert zweite["filament_colour"] == ["#FFFFFF"]
    assert zweite["name"] == "Solidon Schrift"

    befehl = handover._command(setup, [tmp_path / "platte.3mf"], config, tmp_path)
    stelle = befehl.index("--load-filaments")
    assert befehl[stelle + 1].count(";") == 1, "beide gehen an den Slicer, nicht nur eines"


def test_a_manual_slot_type_wins_over_the_projects_base_filament(tmp_path: Path) -> None:
    """Die sichtbare Spulenwahl steht über der allgemeinen Profilunterlage.

    Eine lokal angelegte PLA-Spule hat einen Typ, aber kein eigenes
    Herstellerprofil. Das globale PETG-Profil darf seinen Typ beim Auffüllen
    der übrigen Werte nicht wieder über die ausdrückliche Wahl schreiben.
    """
    petg = _filament_profile(
        tmp_path, "Haus PETG", filament_type=["PETG"], filament_start_gcode=["M104 S240"]
    )
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(
        executable=Path("orca-slicer.exe"),
        flavour="orca",
        base_filament=str(petg),
    )
    slot = MaterialSlot(index=0, name="PLA Lokal", material_type="PLA")

    config = handover.write_config(settings, profile, setup, tmp_path, (slot,))

    written = json.loads(config.filaments[0].read_text(encoding="utf-8"))
    assert written["filament_type"] == ["PLA"]
    expected = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "pla"))
    assert written["nozzle_temperature"] == [str(expected.temperature.nozzle)]
    assert written["hot_plate_temp"] == [str(expected.temperature.bed)]
    assert "filament_start_gcode" not in written
    embedded = handover.project_settings(settings, profile, setup, slots=(slot,))
    assert embedded["nozzle_temperature"] == written["nozzle_temperature"]


@pytest.mark.parametrize("shrink", [None, "99.5%"])
def test_every_filament_has_shrink_compensation_without_replacing_the_manufacturer(
    tmp_path: Path, shrink: str | None
) -> None:
    """Bambu indiziert die Schrumpfliste auch bei lokalen Spulen vollständig."""
    base = _filament_profile(
        tmp_path, "Haus PLA", **({"filament_shrink": [shrink]} if shrink else {})
    )
    profile = profiles.make_profile("bambu-a1", "pla")
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(
        executable=Path("bambu-studio.exe"), flavour="orca", base_filament=str(base)
    )
    slots = (
        MaterialSlot(index=0, name="PLA Orange", material_type="PLA"),
        MaterialSlot(index=1, name="PETG Weiß", material_type="PETG"),
    )

    config = handover.write_config(settings, profile, setup, tmp_path, slots)
    written = [json.loads(path.read_text(encoding="utf-8")) for path in config.filaments]

    assert [item["filament_shrink"] for item in written] == [[shrink or "100%"], ["100%"]]
    embedded = handover.project_settings(settings, profile, setup, slots=slots)
    assert embedded["filament_shrink"] == [shrink or "100%", "100%"]


def test_local_spool_defaults_keep_process_and_explicit_spool_values() -> None:
    """Materialwechsel bewahrt den Prozess und ausdrücklich gewählte Gruppen."""
    from app.core.types import SlotOverride

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    slot = MaterialSlot(index=1, name="PLA Weiß", material_type="PLA", colour=(1.0, 1.0, 1.0))
    settings = replace(settings, shell=replace(settings.shell, wall_count=7))
    override = SlotOverride(
        name=slot.name,
        colour=slot.colour,
        material_type=slot.material_type,
        temperature=replace(settings.temperature, nozzle=219),
    )
    settings = handover.with_slot_override(settings, slot, override)

    effective = handover.settings_for_slot(settings, profile, slot)

    expected = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "pla"))
    assert effective.shell is settings.shell
    assert effective.temperature is override.temperature
    assert effective.cooling == expected.cooling
    assert effective.retraction == expected.retraction
    assert effective.filament == expected.filament


@pytest.mark.parametrize("flavour", ["prusa", "cura"])
def test_a_local_spool_sets_the_material_values_of_a_shared_slicer(
    tmp_path: Path, flavour: handover.SlicerFlavour
) -> None:
    """Eine PLA-Spule fährt auch ohne Mehrfachprofile mit PLA-Werten."""
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(executable=Path("slicer"), flavour=flavour)
    slot = MaterialSlot(index=0, name="PLA Lokal", material_type="PLA")

    config = handover.write_config(settings, profile, setup, tmp_path, (slot,))

    written = config.process.read_text(encoding="utf-8")
    expected = print_settings.resolve(profiles.make_profile("centauri-carbon-2", "pla"))
    key = "temperature" if flavour == "prusa" else "material_print_temperature"
    separator = " = " if flavour == "prusa" else "="
    assert f"{key}{separator}{expected.temperature.nozzle}\n" in written


def test_a_slot_override_wins_over_its_selected_filament_profile(tmp_path: Path) -> None:
    """Die ausdrückliche Kundenwahl ist die oberste Schicht des Profils.

    Das Herstellerprofil liefert weiterhin alles, was nicht geändert wurde.
    Eine aktivierte Temperaturgruppe darf es aber nicht still wieder auf seine
    eigene Temperatur zurücksetzen.
    """
    from app.core.types import MaterialSlot, SlotOverride

    pla = _filament_profile(
        tmp_path,
        "Haus PLA",
        nozzle_temperature=["205"],
        filament_max_volumetric_speed=["21"],
    )
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    temperature = replace(settings.temperature, nozzle=215)
    slot = MaterialSlot(
        index=0,
        name="PLA Weiß",
        colour=(1.0, 1.0, 1.0),
        material=str(pla),
    )
    settings = replace(
        settings,
        slot_overrides=(
            SlotOverride(
                name=slot.name,
                colour=slot.colour,
                material=slot.material,
                material_type=slot.material_type,
                temperature=temperature,
            ),
        ),
    )
    setup = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")

    config = handover.write_config(settings, profile, setup, tmp_path, (slot,))

    written = json.loads(config.filaments[0].read_text(encoding="utf-8"))
    assert written["nozzle_temperature"] == ["215"], "die sichtbare Spulenwahl gewinnt"
    assert written["filament_max_volumetric_speed"] == ["21"], (
        "nicht geänderte Gruppen bleiben beim Herstellerprofil"
    )


def test_without_slots_it_stays_one_filament(tmp_path: Path) -> None:
    """Der einfarbige Druck ist der Sonderfall mit einem Eintrag, nicht ein
    anderer Weg — und dort gelten Solidons Werte, nicht die des Herstellers."""
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(executable=Path("orca-slicer.exe"), flavour="orca")

    config = handover.write_config(settings, profile, setup, tmp_path)

    assert len(config.filaments) == 1
    assert config.filament == config.filaments[0], (
        "das eine bleibt über die alte Auskunft erreichbar"
    )
    document = json.loads(config.filaments[0].read_text(encoding="utf-8"))
    assert document["nozzle_temperature"] == [str(settings.temperature.nozzle)]


# --- Verbinder, am Querschnitt gemessen (§25, §29) ----------------------------


def test_a_connector_made_mostly_of_infill_asks_for_more_walls() -> None:
    """Die Stiftplanung rechnet in Geometrie, gedruckt wird ein Ring mit Muster.

    Nachgemessen am Querschnitt: Ein Verbinder mit Ø 5,00 mm ist bei zwei
    Wänden à 0,42 mm innen 3,32 mm Füllung und außen 1,68 mm Material. Genau
    dort sitzt die Verbindung, die die beiden Hälften zusammenhalten soll —
    ein Gyroid mit fünfzehn Prozent trifft diesen Kern womöglich gar nicht.
    """
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    settings = replace(
        settings,
        shell=replace(settings.shell, wall_count=2),
        layers=replace(settings.layers, line_width=0.42),
    )

    assert advise.solid_core(5.0, settings) == pytest.approx(3.32)

    entries = [
        entry
        for entry in advise.advise(settings, profile, connectors=(5.0,))
        if entry.path == "shell.wall_count"
    ]

    assert entries, "der Verbinder besteht überwiegend aus Füllung"
    # 5,00 / (4 · 0,42) aufgerundet: die Schwelle, ab der das Material um den
    # Zapfen mindestens so breit ist wie sein Kern — nicht bis vollmassiv, das
    # wären zehn Wände auf dem ganzen Teil.
    assert entries[0].value == 3
    danach = replace(settings, shell=replace(settings.shell, wall_count=3))
    assert advise.solid_core(5.0, danach) <= 2.0 * 3 * 0.42


def test_a_connector_that_prints_solid_needs_no_advice() -> None:
    """Ein Zapfen mit ein paar Zehnteln Muster in der Mitte trägt — erst wenn
    der Füllkern breiter ist als das Material um ihn herum, ist es eine Sache.
    """
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    settings = replace(
        settings,
        shell=replace(settings.shell, wall_count=3),
        layers=replace(settings.layers, line_width=0.42),
    )

    # 3,00 minus 2 mal 3 mal 0,42 sind 0,48 mm Kern gegen 2,52 mm Material.
    assert advise.solid_core(3.0, settings) == pytest.approx(0.48)
    paths = {entry.path for entry in advise.advise(settings, profile, connectors=(3.0,))}

    assert "shell.wall_count" not in paths


def test_without_connectors_nothing_is_said() -> None:
    """Wer nicht geteilt hat, bekommt keinen Vorschlag über Verbinder."""
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)

    paths = {entry.path for entry in advise.advise(settings, profile)}

    assert "shell.wall_count" not in paths


# --- der Lauf selbst: Zeitgrenze, Abbruch, Start (§2.8, Regel 17) -----------------


def test_a_slicer_over_the_time_limit_is_an_answer_not_a_crash(tmp_path: Path) -> None:
    """``subprocess.run`` warf einen rohen
    ``TimeoutExpired`` aus dem Arbeits-Thread, der nur ``AppError`` fing —
    der Dialog stand dauerhaft auf „Der Slicer rechnet …"."""
    import sys

    setup = handover.SlicerSetup(executable=Path(sys.executable), flavour="orca")
    command = [sys.executable, "-c", "import time; time.sleep(30)"]

    with pytest.raises(ExternalToolError) as caught:
        handover._run_slicer(command, tmp_path, 0.5, setup, None)

    assert caught.value.suggestions, "eine Zeitgrenze ist eine Antwort, kein Absturz"


def test_a_cancelled_slicer_run_stops_the_child_quickly(tmp_path: Path) -> None:
    """Abbrechen beendet den Kindprozess, statt ihn auslaufen zu lassen —
    daran hängt, dass Schließen nicht mehr minutenlang einfriert."""
    import sys
    import time as clock

    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    signal = CancelSignal()
    signal.cancel()
    setup = handover.SlicerSetup(executable=Path(sys.executable), flavour="orca")
    command = [sys.executable, "-c", "import time; time.sleep(30)"]
    started = clock.perf_counter()

    with pytest.raises(OperationCancelled):
        handover._run_slicer(command, tmp_path, 60.0, setup, signal)

    assert clock.perf_counter() - started < 15.0, "der Kindprozess stirbt, nicht der Nutzer wartet"


def test_a_slicer_with_endless_output_is_stopped(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch ein redseliger Fehlerprozess bleibt innerhalb der Speichergrenze."""
    import sys

    monkeypatch.setattr(handover, "SLICER_OUTPUT_LIMIT", 1024)
    setup = handover.SlicerSetup(executable=Path(sys.executable), flavour="orca")
    command = [sys.executable, "-c", "import os, time; os.write(1, b'x' * 2048); time.sleep(5)"]

    with pytest.raises(ExternalToolError) as caught:
        handover._run_slicer(command, tmp_path, 4.0, setup, None)

    assert caught.value.suggestions


def test_the_slicer_runs_without_a_memory_limit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Slicer bekommt von Solidon keine Speichergrenze (Robert, 03.09.2026).

    Hier stand die Gegenprobe: dass der Lauf eine **eigene**, weitere Grenze
    trägt, weil die allgemeine von vier GiB für einen Slicer eine Absage war.
    Beide sind gefallen. Ein Slicer baut über einem feinen Netz Millionen von
    Segmenten auf; wie viel Speicher er dafür nimmt, entscheidet der Rechner
    des Kunden und nicht Solidon — bis 0.2.2 war es genauso. Zeitgrenze,
    Ausgabegrenze und das Beenden der Nachkommen bleiben; sie stehen in den
    Tests darüber.
    """
    import sys

    from app.core.errors import OperationCancelled
    from app.core.process import ProcessCancelled

    seen: dict[str, object] = {}

    def watching(command: list[str], **options: object) -> object:
        seen.update(options)
        raise ProcessCancelled

    monkeypatch.setattr(handover, "run_limited", watching)
    setup = handover.SlicerSetup(executable=Path(sys.executable), flavour="orca")

    with pytest.raises(OperationCancelled):
        handover._run_slicer([sys.executable], tmp_path, 5.0, setup, None)

    assert "memory_limit" not in seen, f"der Lauf trägt wieder eine Speichergrenze: {seen}"
    assert seen.get("timeout") and seen.get("output_limit"), (
        f"Zeit- und Ausgabegrenze müssen bleiben: {seen}"
    )
    assert not hasattr(handover, "SLICER_MEMORY_LIMIT"), "die eigene Slicer-Grenze ist wieder da"


def test_a_slicer_that_says_too_much_is_not_an_error_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zu viel Ausgabe ist etwas anderes als ein Fehlercode.

    Der Zweig meldete „Der Slicer ist mit einem Fehlercode zurückgekommen" —
    dabei ist gar keiner gekommen: Solidon hat den Lauf abgebrochen, weil die
    Ausgabe die Sammelgrenze überschritt. Wer den Satz liest, sucht den Fehler
    im Slicer statt in der Menge (§2.7).
    """
    import sys

    monkeypatch.setattr(handover, "SLICER_OUTPUT_LIMIT", 1024)
    setup = handover.SlicerSetup(executable=Path(sys.executable), flavour="orca")
    command = [sys.executable, "-c", "import os, time; os.write(1, b'x' * 2048); time.sleep(5)"]

    with pytest.raises(ExternalToolError) as caught:
        handover._run_slicer(command, tmp_path, 4.0, setup, None)

    said = str(caught.value.detail)
    assert "Fehlercode" not in said, f"der Satz spricht vom falschen Grund: {said}"
    assert "Ausgabe" in said, said
    assert {action.id for action in caught.value.suggestions} >= {
        "show_output",
        "choose_slicer",
        "export_only",
    }


def test_a_slicer_that_cannot_start_is_an_answer(tmp_path: Path) -> None:
    """Eine gewählte Datei kann ``flavour_of`` bestehen und trotzdem kein
    Programm sein — eine DLL zum Beispiel. Der ``OSError`` beim Start flog
    roh aus dem Thread."""
    fake = tmp_path / "elegoo-slicer.exe"
    fake.write_text("kein programm", encoding="utf-8")
    setup = handover.SlicerSetup(executable=fake, flavour="orca")

    with pytest.raises(ExternalToolError) as caught:
        handover._run_slicer([str(fake)], tmp_path, 5.0, setup, None)

    assert caught.value.suggestions


def test_slicing_without_a_model_offers_nothing_to_install(tmp_path: Path) -> None:
    """Regel 17 heißt nicht „irgendein Knopf".

    Beide Fehler erbten die Vorschläge von :class:`ExternalToolError`, und der
    erste davon heißt „Zusätzliche Programme …". Es fehlt hier aber kein
    Programm: Übergeben wurde nichts, beziehungsweise die Datei ist weg. Wer
    dem Knopf folgt, landet in einer Liste, die mit seinem Fehler nichts zu
    tun hat.
    """
    profile = profiles.make_profile()
    setup = handover.SlicerSetup(executable=tmp_path / "cura.exe", flavour="cura")

    with pytest.raises(ExternalToolError) as leer:
        handover.slice_model([], print_settings.resolve(profile), profile, setup)
    assert leer.value.suggestions
    assert "install" not in {action.id for action in leer.value.suggestions}
    assert "change_selection" in {action.id for action in leer.value.suggestions}

    with pytest.raises(ExternalToolError) as weg:
        handover.slice_model(
            tmp_path / "verschwunden.stl", print_settings.resolve(profile), profile, setup
        )
    assert "install" not in {action.id for action in weg.value.suggestions}
    assert "retry" in {action.id for action in weg.value.suggestions}


def test_a_semicolon_in_a_profile_path_is_refused_before_the_slicer_sees_it(
    tmp_path: Path,
) -> None:
    """``--load-settings`` trennt seine Profile mit Semikolon.

    Ein Semikolon im Pfad macht aus einem Profil zwei, und der Slicer
    antwortet mit „can not find setting file" auf einen Pfad, den es so nie
    gab. Ein Maskierungsweg ist für diesen Schalter nirgends zugesagt — also
    wird die Lage benannt, statt sie zu raten.
    """
    heikel = tmp_path / "ma;schine.json"
    heikel.write_text("{}", encoding="utf-8")
    setup = handover.SlicerSetup(
        executable=tmp_path / "orca.exe", flavour="orca", machine_profile=str(heikel)
    )
    config = handover.SlicerConfig(process=tmp_path / "prozess.json")

    with pytest.raises(ExternalToolError) as caught:
        handover._command(setup, [tmp_path / "platte.3mf"], config, tmp_path)

    assert ";" in str(caught.value.values.get("path", "")), "der Pfad, um den es geht"
    assert caught.value.suggestions, "Regel 17"

    harmlos = tmp_path / "maschine.json"
    harmlos.write_text("{}", encoding="utf-8")
    gut = handover.SlicerSetup(
        executable=tmp_path / "orca.exe", flavour="orca", machine_profile=str(harmlos)
    )
    assert "--load-settings" in handover._command(gut, [tmp_path / "p.3mf"], config, tmp_path)


def test_the_print_file_we_asked_for_beats_a_stranger_in_the_folder(tmp_path: Path) -> None:
    """§22.5: Kennzahlen sind nur etwas wert, wenn sie aus *dieser* Datei
    kommen.

    Prusa und Cura schreiben dorthin, wohin Solidon zeigt, und unter dem
    Namen, den Solidon nennt. Gesucht wurde trotzdem nur nach Endung, und die
    jüngste gewann — in einem Zielordner des Nutzers ist das die Datei eines
    fremden Programms, und ihre Zahlen standen dann im Prüfbericht.
    """
    import os

    unser = tmp_path / handover.OUTPUT_NAME
    unser.write_text("G1 X1 Y1 E1\n", encoding="utf-8")
    fremd = tmp_path / "irgendwas.gcode"
    fremd.write_text("G1 X2 Y2 E2\n", encoding="utf-8")
    spaeter = unser.stat().st_mtime + 60.0
    os.utime(fremd, (spaeter, spaeter))

    assert handover._find_gcode(tmp_path, handover.OUTPUT_NAME) == unser
    assert handover._find_gcode(tmp_path) == fremd, "wo der Slicer selbst benennt, die jüngste"

    unser.unlink()
    assert handover._find_gcode(tmp_path, handover.OUTPUT_NAME) == fremd, "Rückfall bleibt"


def test_the_slicer_run_reads_back_the_file_it_asked_for(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Und die Anschlussprüfung dazu: nicht „``_find_gcode`` kann es", sondern
    „der Lauf tut es"."""
    import os

    profile = profiles.make_profile()
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    executable = tmp_path / "cura.exe"
    executable.write_bytes(b"")

    def _writes(command: list[str], *_args: object, **_kwargs: object) -> _Finished:
        _slicer_output_path(command).write_text(_gcode_printing_at(-10.0, 10.0), encoding="utf-8")
        fremd = tmp_path / "fremd.gcode"
        fremd.write_text(_gcode_printing_at(400.0), encoding="utf-8")
        spaeter = fremd.stat().st_mtime + 60.0
        os.utime(fremd, (spaeter, spaeter))
        return _Finished(b"")

    monkeypatch.setattr(handover, "_run_slicer", _writes)
    setup = handover.SlicerSetup(executable=executable, flavour="cura")

    outcome = handover.slice_model(
        model, print_settings.resolve(profile), profile, setup, output_dir=tmp_path
    )

    assert outcome.gcode_path.name == handover.OUTPUT_NAME


def test_the_slicer_run_streams_the_print_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine große Druckdatei wird nicht als zweiter vollständiger String gehalten."""
    profile = profiles.make_profile()
    model, setup = _slicer_writing(
        monkeypatch, tmp_path, _gcode_printing_at(-10.0, 10.0), flavour="cura"
    )
    original_read_text = Path.read_text

    def guarded_read_text(path: Path, *args: object, **kwargs: object) -> str:
        if path.suffix.casefold() in handover.GCODE_SUFFIXES:
            raise AssertionError("Druckdateien müssen zeilenweise gelesen werden")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)

    outcome = handover.slice_model(
        model, print_settings.resolve(profile), profile, setup, output_dir=tmp_path
    )

    assert outcome.gcode_path.is_file()


def test_keeping_a_print_file_does_not_load_its_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch das Kopieren neben das Modell arbeitet mit begrenztem Speicher."""
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    work = tmp_path / "work"
    work.mkdir()
    produced = work / "print.gcode"
    produced.write_text(_gcode_printing_at(-10.0, 10.0), encoding="utf-8")

    def forbidden_read_bytes(_path: Path) -> bytes:
        raise AssertionError("Druckdateien müssen als Stream kopiert werden")

    monkeypatch.setattr(Path, "read_bytes", forbidden_read_bytes)

    kept = handover._kept_beside(model, produced)

    with kept.open("r", encoding="utf-8") as stream:
        assert "G1 X10" in stream.read()


def test_cancelling_the_copy_keeps_the_previous_print_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Abbruch hinterlässt weder eine Teildatei noch überschreibt er die alte."""
    from app.core.errors import OperationCancelled

    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    produced = tmp_path / "print.gcode"
    produced.write_bytes(b"abcdefghijklmnop")
    kept = model.with_suffix(".gcode")
    kept.write_bytes(b"vorher")

    class CancelDuringCopy:
        def __init__(self) -> None:
            self.calls = 0

        @property
        def is_cancelled(self) -> bool:
            return self.calls >= 3

        def raise_if_cancelled(self) -> None:
            self.calls += 1
            if self.is_cancelled:
                raise OperationCancelled

    monkeypatch.setattr(handover, "COPY_BLOCK_BYTES", 4)

    with pytest.raises(OperationCancelled):
        handover._kept_beside(model, produced, cancelled=CancelDuringCopy())

    assert kept.read_bytes() == b"vorher"
    assert not list(tmp_path.glob(f".{kept.name}.*.tmp")), "die angefangene Kopie bleibt liegen"


def test_the_slicer_run_passes_cancellation_into_readback(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Prozessabbruch endet nicht am Kindprozess, sondern gilt auch danach."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    profile = profiles.make_profile()
    model, setup = _slicer_writing(
        monkeypatch, tmp_path, _gcode_printing_at(-10.0, 10.0), flavour="cura"
    )
    signal = CancelSignal()
    original = handover.gcode.analyze_lines

    def cancelling_readback(lines: object, *, cancelled: object = None, **kwargs: object) -> object:
        assert cancelled is signal
        signal.cancel()
        return original(lines, cancelled=cancelled, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(handover.gcode, "analyze_lines", cancelling_readback)

    with pytest.raises(OperationCancelled):
        handover.slice_model(
            model,
            print_settings.resolve(profile),
            profile,
            setup,
            output_dir=tmp_path,
            cancelled=signal,
        )


def test_the_slicer_run_passes_cancellation_into_the_final_copy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch der Weg aus dem flüchtigen Arbeitsordner behält dasselbe Token."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    profile = profiles.make_profile()
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    executable = tmp_path / "cura.exe"
    executable.write_bytes(b"")
    setup = handover.SlicerSetup(executable=executable, flavour="cura")

    def writes(*args: object, **_kwargs: object) -> _Finished:
        workspace = args[1]
        assert isinstance(workspace, Path)
        (workspace / handover.OUTPUT_NAME).write_text(
            _gcode_printing_at(-10.0, 10.0), encoding="utf-8"
        )
        return _Finished(b"")

    signal = CancelSignal()
    original = handover._kept_beside

    def cancelling_copy(selected: Path, produced: Path, *, cancelled: object = None) -> Path:
        assert cancelled is signal
        signal.cancel()
        return original(selected, produced, cancelled=cancelled)  # type: ignore[arg-type]

    monkeypatch.setattr(handover, "_run_slicer", writes)
    monkeypatch.setattr(handover, "_kept_beside", cancelling_copy)

    with pytest.raises(OperationCancelled):
        handover.slice_model(
            model,
            print_settings.resolve(profile),
            profile,
            setup,
            cancelled=signal,
        )

    assert not model.with_suffix(".gcode").exists()


def test_a_print_file_that_cannot_be_kept_says_so(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne ``output_dir`` verschwindet der Arbeitsordner, und die Druckdatei
    wandert neben das Modell. Ging das nicht, flog ein roher ``OSError`` —
    aus einem Arbeits-Thread, der nur ``AppError`` fängt.
    """
    from app.core.errors import FileWriteError

    profile = profiles.make_profile()
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    (tmp_path / "model.gcode").mkdir()  # der Platz ist belegt, und zwar von einem Ordner
    executable = tmp_path / "cura.exe"
    executable.write_bytes(b"")

    def _writes(*args: object, **_kwargs: object) -> _Finished:
        workspace = args[1]
        assert isinstance(workspace, Path)
        (workspace / handover.OUTPUT_NAME).write_text(
            _gcode_printing_at(-10.0, 10.0), encoding="utf-8"
        )
        return _Finished(b"")

    monkeypatch.setattr(handover, "_run_slicer", _writes)
    setup = handover.SlicerSetup(executable=executable, flavour="cura")

    with pytest.raises(FileWriteError) as caught:
        handover.slice_model(model, print_settings.resolve(profile), profile, setup)

    assert caught.value.suggestions, "Regel 17"


def test_an_unknown_material_is_reported_not_silent() -> None:
    """Regel 21: `_material_table` fällt mit Absicht still auf die
    Modellvorgaben zurück — der Satz an den Nutzer fehlte: ein selbst
    angelegtes Material druckt sonst mit PLA-nahen Werten, ohne dass es
    irgendwo steht."""
    from dataclasses import replace as dc_replace

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    unknown = dc_replace(profile, material=dc_replace(profile.material, id="eigenes-filament"))
    settings = print_settings.resolve(unknown)

    codes = {entry.code for entry in advise.warnings_for(settings, unknown)}

    assert "settings.material_without_profile" in codes
    known_codes = {entry.code for entry in advise.warnings_for(settings, profile)}
    assert "settings.material_without_profile" not in known_codes


def test_without_a_slicer_the_dialog_offers_a_way_to_one(
    qt_app: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regel 17 an der Stelle, an der jemand gerade slicen wollte.

    „Kein Slicer eingerichtet — die Einstellungen lassen sich trotzdem
    pflegen." sagte, was fehlt, und bot nichts an. Der Satz bleibt (§27: das
    Backend meldet sich ab, es nörgelt nicht), der Weg kommt dazu.
    """
    from app.core import discover
    from app.ui.print_settings_dialog import PrintSettingsDialog
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    monkeypatch.setattr(discover, "find_program", lambda *_args: None)
    monkeypatch.setattr(discover, "find_programs", lambda *_args: ())
    dialog = PrintSettingsDialog(Session(), UiSettings())
    assert dialog.wait_for_slicers(), "die Slicersuche kam nicht zurück"

    assert not dialog.slice_button.isEnabled(), "ohne Slicer gibt es nichts zu starten"
    assert not dialog.setup_button.isHidden(), "aber einen Weg zu einem"
    assert "Kein Slicer" in dialog.state.text()

    asked: list[bool] = []
    dialog.setupRequested.connect(lambda: asked.append(True))
    dialog.setup_button.click()

    assert asked == [True]


def test_a_slot_profile_follows_its_slot_across_plates(qt_app: object, tmp_path: Path) -> None:
    """Das Profil gehört dem Filament, nicht der Zeilennummer (§20).

    Angezeigt wird die Zusammenlegung der gewählten Platten, gedruckt wird
    Platte für Platte, und jede legt für sich zusammen. Bei „Alle Platten"
    mit Rot auf Platte 1 und Weiß+Rot auf Platte 2 stand deshalb
    [Rot, Weiß] im Dialog und [Weiß, Rot] im Lauf der zweiten Platte —
    positionsweise zugeordnet bekam **Weiß das Rot-Profil**, und mit dem
    Profil wandert die Temperatur (Fund 26.08.2026, am Lauf gemessen).

    Die Gegenprobe steht im Test mit drin: Positionsweise wäre die
    Zuordnung vertauscht, und genau das darf sie nicht mehr sein.
    """
    from types import SimpleNamespace

    import trimesh

    from app.core.export import handover
    from app.core.geom.mesh import MeshData
    from app.core.types import MaterialSlot, Scene, SceneObject
    from app.ui.print_settings_dialog import PrintSettingsDialog
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    dialog = PrintSettingsDialog(Session(), UiSettings())
    assert dialog.wait_for_slicers(), "die Slicersuche kam nicht zurück"

    box = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    rot = MaterialSlot(index=0, name="Rot")
    weiss = MaterialSlot(index=0, name="Weiß")
    erste = SceneObject(id="A", name="A", mesh=box, material_slots=[rot], plate=0)
    zweite = SceneObject(id="B", name="B", mesh=box, material_slots=[weiss, rot], plate=1)
    # Eine **echte** Szene und keine Attrappe: Der Dialog reicht sie seit
    # RM-140 bis in die Exportprüfung durch, und die fragt nach Passungen und
    # Wandstärken. Ein ``SimpleNamespace`` hat beides nicht.
    dialog.session.last_result = SimpleNamespace(
        scene=Scene(objects={"A": erste, "B": zweite}, profile=dialog.session.profile),
        stopped_at=None,
    )
    # Was der Kunde bei „Alle Platten" sieht und zuordnet: Rot, dann Weiß.
    assert [str(slot.name) for slot in dialog._plate_slots()] == ["Rot", "Weiß"]
    dialog.settings = replace(dialog.settings, slot_profiles=("Rotes PLA", "Weißes PLA"))
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")

    run = dialog._plate_run([erste, zweite], 1, tmp_path, "satz", setup)

    gewählt = {str(slot.name): slot.material for slot in run.slots}
    assert gewählt == {"Weiß": "Weißes PLA", "Rot": "Rotes PLA"}
    assert [str(slot.name) for slot in run.slots] == ["Weiß", "Rot"], (
        "die Reihenfolge des Laufs ist eine andere — daran hing der Fehler"
    )


def test_a_slicer_that_arrived_is_picked_up_without_reopening(
    qt_app: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Wer einen Slicer gerade installiert hat, soll nicht schließen müssen.

    Gemessen mit einem PrusaSlicer, nicht mit der Orca-Familie: Die verlangt
    seit dem Profil-Wächter zu Recht erst eine Profilwahl, und ihr Knopf
    bliebe hier grau — dann prüfte dieser Test zwei Zusagen auf einmal und
    keine sauber. Das Aufgreifen misst sich an einem Slicer ohne
    Profilpflicht; den Wächter der Orca-Familie hält
    ``tests/test_print_settings_ui.py`` fest.

    Seit Stufe C sieht der Dialog auch bei PrusaSlicer den Profilbestand
    durch, und bis dahin ist der Knopf zu. Der Test wartet deshalb auch auf
    diese Suche. Findet sie nichts, druckt PrusaSlicer mit Solidons Werten,
    und der Hinweis darf nicht behaupten, er lehne den Auftrag ab.
    """
    from app.core import discover
    from app.ui.print_settings_dialog import PrintSettingsDialog
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    monkeypatch.setattr(discover, "find_program", lambda *_args: None)
    monkeypatch.setattr(discover, "find_programs", lambda *_args: ())
    dialog = PrintSettingsDialog(Session(), UiSettings())
    assert dialog.wait_for_slicers(), "die Slicersuche kam nicht zurück"
    assert not dialog.slice_button.isEnabled()

    program = tmp_path / "prusa-slicer.exe"
    program.write_text("")
    monkeypatch.setattr(discover, "find_program", lambda *_args: program)
    monkeypatch.setattr(discover, "find_programs", lambda *_args: (program,))

    dialog.recheck_slicer()
    assert dialog.wait_for_slicers(), "die Slicersuche kam nicht zurück"
    assert dialog.wait_for_profiles(), "die Profilsuche kam nicht zurück"

    assert dialog.slice_button.isEnabled(), "jetzt gibt es einen"
    assert dialog.setup_button.isHidden(), "und nichts mehr zu holen"
    assert "lehnt" not in dialog.profile_note.text(), dialog.profile_note.text()
    assert "Solidons eigene Werte" in dialog.profile_note.text()


def test_a_wall_below_one_nozzle_line_becomes_a_finding_not_a_suggestion() -> None:
    """Unter einer schmalsten Bahn der Düse behebt keine Einstellung mehr etwas.

    Die Bahnbreiten-Regel senkt höchstens bis ``NARROW_LINE_SHARE`` mal
    Düsendurchmesser — darunter blieb bisher ein Vorschlag stehen, der die
    Stelle weiter wegfallen ließ, und der eigentliche Ausweg (kleinere Düse
    oder breitere Wand) stand nirgends. Nach der Doktrin aus
    ``schichtanalyse.md`` gehört dorthin ein Befund: Was kein Wert behebt,
    wird ein Finding (Roberts Auftrag vom 26.08.2026, „Düse als Empfehlung").
    """
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    least = advise.NARROW_LINE_SHARE * profile.printer.nozzle_diameter
    result = _layers(500.0, 500.0, 500.0, min_width=least * 0.8)

    findings = advise.warnings_for(settings, profile, result)
    hits = [entry for entry in findings if entry.code == "settings.wall_below_nozzle"]

    assert hits, "eine Wand unter einer Bahnbreite gehört gesagt"
    assert hits[0].severity == "warning"
    assert hits[0].values["nozzle_mm"] == pytest.approx(profile.printer.nozzle_diameter)
    assert hits[0].values["width_mm"] == pytest.approx(least * 0.8)
    assert hits[0].values["least_mm"] == pytest.approx(least)
    assert hits[0].source == "internal"

    # Und der Vorschlag daneben verschwindet: Eine Bahnbreite, die die Stelle
    # trotzdem verliert, ist kein Vorschlag (dieselbe Doktrin, andere Hälfte).
    entries = advise.advise(settings, profile, result)
    assert not [entry for entry in entries if entry.path == "layers.line_width"], (
        "unter der Düsengrenze darf keine Bahnbreite mehr vorgeschlagen werden"
    )


def test_a_wall_the_nozzle_can_print_is_not_that_finding() -> None:
    """Die Gegenrichtung, sonst warnte der Bericht an jedem gesunden Teil."""
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    least = advise.NARROW_LINE_SHARE * profile.printer.nozzle_diameter
    # Eine einzelne variable Bahn ist druckbar; Festigkeit wird separat geprüft.
    result = _layers(500.0, 500.0, 500.0, min_width=least * 1.5)

    codes = {entry.code for entry in advise.warnings_for(settings, profile, result)}
    assert "settings.wall_below_nozzle" not in codes


def test_what_can_be_opened_can_also_be_found() -> None:
    """Der Öffnen-Dialog und die Suche im Ausgabeordner meinen dieselbe Menge.

    Die Endungen standen zweimal: im Kern (`handover`), der nach dem Lauf die
    erzeugte Druckdatei sucht, und in der Oberfläche, die den Dateifilter
    baut. Sie liefen auseinander — der Filter kannte `.nc`, die Suche nicht.
    Ein Slicer, der eine `.nc` schreibt, wäre damit unauffindbar gewesen, und
    der Kunde hätte „Der Slicer hat keine Druckdatei geschrieben." gelesen,
    während die Datei danebenlag (gefunden am 27.08.2026).

    Zwei Stellen, die dieselbe Frage beantworten, und nur eine wird gepflegt —
    dasselbe Muster wie bei `setdefault` gegen `merged_slots` und bei den
    beiden Parameterart-Tabellen. Der Test hält jetzt fest, dass es **eine**
    Menge ist, nicht zwei gleiche.
    """
    from app.ui.main_window import GCODE_SUFFIXES as AUS_DER_OBERFLAECHE

    assert AUS_DER_OBERFLAECHE is handover.GCODE_SUFFIXES, (
        "die Oberfläche holt die Endungen aus dem Kern, statt sie zu wiederholen"
    )
    assert ".nc" in handover.GCODE_SUFFIXES, "und die längere der beiden Listen gewinnt"


#: Feld/Slicer-Paare, bei denen eine Einstellung den Slicer **nicht** erreicht —
#: und der Grund, warum das richtig ist.
#:
#: Gemessen am 27.08.2026 auf Roberts Architekturauftrag zu den Zwillingen. Die
#: drei Slicer-Familien sind das teuerste Zwillingspaar des Projekts: 24
#: Verzweigungen über `flavour`, und die Übersetzung lebt an **zwei** Orten —
#: in `slicer_keys.TABLES` und in den Sonderfällen von `handover` (Haftung,
#: Stützabstand, Cura-Ableitungen). Eine Lücke in der Tabelle ist deshalb noch
#: kein Befund; erst die echte Ausgabe sagt es.
#:
#: Jeder Eintrag hier ist eine Zusage: *Dieses Feld erreicht diesen Slicer
#: nicht, und das ist in Ordnung.* Wer einen hinzufügt, schreibt den Grund
#: dazu — eine Ausnahmeliste ohne Gründe wird zur Halde.
UNREACHED: Final[dict[tuple[str, str], str]] = {
    ("shell.wall_generator", "cura"): (
        "CuraEngine wählt den Wandgenerator nicht über einen Schalter: Arachne "
        "ist seit 5.0 der einzige Weg, und die Klassik gibt es dort nicht mehr."
    ),
    ("shell.precise_outer_wall", "prusa"): (
        "Die genaue Außenwand ist eine Eigenheit der Orca-Familie; PrusaSlicer "
        "kennt keinen entsprechenden Schalter."
    ),
    ("shell.precise_outer_wall", "cura"): (
        "Dasselbe für CuraEngine — dort heißt der nächste Verwandte "
        "``outer_inset_first`` und meint die Reihenfolge, nicht das Maß."
    ),
    ("retraction.wipe", "cura"): (
        "CuraEngine wischt nicht auf Anweisung, sondern über das Einzugsmuster; "
        "ein eigener Schalter dafür existiert nicht."
    ),
    ("filament.density", "cura"): (
        "Dichte und Preis dienen der Verbrauchsschätzung, und die rechnet "
        "Solidon selbst aus dem G-Code (§22.5). CuraEngine nimmt sie nicht "
        "entgegen; sie zum Slicer zu tragen brächte niemandem etwas."
    ),
    ("filament.cost_per_kg", "cura"): "Wie die Dichte darüber — Solidon rechnet, nicht der Slicer.",
    ("filament.max_flow", "cura"): (
        "CuraEngine liest ``material_max_flowrate`` nicht (null Treffer in ``CuraEngine.exe`` "
        "5.13); den Volumenstrom hält Solidon über die Tempi (``print_settings._within_flow``)."
    ),
    ("support.block_channels", "prusa"): (
        "Reist als Stützsperre in der 3MF, nicht als Wert (``slicer_keys.AS_GEOMETRY``); "
        "``test_threemf_assembly`` prüft den Bereich."
    ),
    ("support.block_channels", "orca"): "Wie bei PrusaSlicer — dieselbe Beilage.",
    ("support.block_channels", "cura"): (
        "Reist als eigenes Netz mit ``anti_overhang_mesh`` neben den Teilen "
        "(``slicer_keys.takes_mesh_settings``); ``test_export`` prüft die Netzliste."
    ),
}


def _read_path(settings: object, path: str) -> object:
    obj: object = settings
    for part in path.split("."):
        obj = getattr(obj, part)
    return obj


def _with_value(settings: Any, path: str, value: object) -> Any:
    group, _, name = path.partition(".")
    return replace(settings, **{group: replace(getattr(settings, group), **{name: value})})


def _another_value(current: object, choices: tuple[str, ...]) -> object | None:
    """Ein anderer **gültiger** Wert — bei Auswahlfeldern aus ihren Werten.

    Der erste Anlauf setzte überall dieselbe Zeichenkette, auch in
    ``infill.pattern`` und ``support.placement``: Die Übersetzung fand den
    Wert nicht, schrieb nichts, und die Messung meldete zehn taube Felder,
    die keine waren. Ein Prüfstand, der ungültige Werte einsetzt, misst seine
    eigene Untauglichkeit.
    """
    if choices:
        other = [entry for entry in choices if entry != current]
        return other[0] if other else None
    if isinstance(current, bool):
        return not current
    if isinstance(current, (int, float)):
        return type(current)(current + 1) if current < 90 else type(current)(current - 1)
    return None


def test_every_setting_reaches_every_slicer_or_stands_in_the_list() -> None:
    """Ein Feld, das der Dialog anbietet, wirkt — oder es steht hier, warum nicht.

    Der Kunde stellt 56 Werte ein und kann keinem ansehen, ob sein Slicer ihn
    versteht. Bis heute fehlte die Zusicherung dazu ganz: ``support.density``
    stand nur in der Cura-Tabelle und erreichte PrusaSlicer und die
    Orca-Familie erst über eine Umrechnung, die jemand von Hand nachgetragen
    hat — bemerkt hat es niemand, weil nichts danach fragte.

    Gemessen wird an der **echten Ausgabe** (`values_for`), nicht an der
    Tabelle: Die Übersetzung lebt an zwei Orten, und wer nur die Tabelle liest,
    meldet sechs Lücken, die längst geschlossen sind. Geändert wird je Feld ein
    gültiger Wert; ändert sich daraufhin kein einziger Schlüssel dieses
    Slicers, kommt die Einstellung dort nicht an.
    """
    from app.ui.print_settings_dialog import FIELDS

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    base = print_settings.resolve(profile)
    unreached: list[tuple[str, str]] = []
    for field in FIELDS:
        current = _read_path(base, field.path)
        value = _another_value(current, field.choices)
        if value is None or value == current:
            continue
        # Haftungsabhängige Felder wirken nur unter ihrer Art — sonst misst
        # man die Bedingung statt des Feldes.
        start = base
        art = {
            "brim_width": "brim",
            "raft_layers": "raft",
            "skirt_loops": "skirt",
            "skirt_distance": "skirt",
        }.get(field.path.partition(".")[2] if field.path.startswith("adhesion.") else "")
        if art:
            start = _with_value(base, "adhesion.kind", art)
        changed = _with_value(start, field.path, value)
        for flavour in ("prusa", "orca", "cura"):
            if handover.values_for(start, profile, flavour) == handover.values_for(
                changed, profile, flavour
            ):
                unreached.append((field.path, flavour))

    assert unreached, "keine Messung gelaufen — die Grundmenge ist leer"
    neu = [pair for pair in unreached if pair not in UNREACHED]
    weg = [pair for pair in UNREACHED if pair not in unreached]
    assert not neu, "Einstellungen ohne Wirkung und ohne Begründung: " + str(sorted(neu))
    assert not weg, "steht als unerreichbar in der Liste, wirkt aber: " + str(sorted(weg))


def test_the_dialog_writes_time_and_mass_like_the_status_line() -> None:
    """Eine Sitzung, eine Schreibweise für dieselbe Größe.

    Gemessen am 27.08.2026: Die Statuszeile sagte „10 h 5 min" und „18 g", der
    Druckdialog für dieselben Werte „605 min" und „18,4 g". Zwei Stellen, die
    beide entschieden, wie eine Dauer und eine Masse aussehen — und `min` und
    `g` standen im Dialog als feste Zeichenketten, obwohl `facts.py` sie
    ausdrücklich durch `tr()` schickt (Regel 20).

    Geprüft wird die Quelle, nicht das Fenster: Was der Dialog daraus baut,
    ist eine Zeile mit Doppelpunkt davor, und die Zahl darin kommt seit dem
    Umbau aus derselben Funktion wie die der Statuszeile.
    """
    from app.ui.facts import duration, mass

    assert duration(605 * 60.0) == "10 h 5 min", "über einer Stunde in Stunden und Minuten"
    assert duration(90 * 60.0) == "1 h 30 min"
    # Über zehn Gramm ohne Nachkommastelle — bei einer Schätzung ist „18,4 g"
    # dieselbe Aussage wie „18 g", und die kürzere liest sich im Vorbeigehen.
    assert mass(18.44) == "18 g"
    assert mass(250.0) == "250 g"


def test_several_slicers_become_a_choice(
    qt_app: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Wer drei Slicer installiert hat, soll wählen können.

    Bis zum 30.08.2026 entschied die Suchreihenfolge: ``find_program`` hört
    beim ersten Treffer auf. Auf dieser Maschine fand sie ElegooSlicer und
    bot PrusaSlicer und Cura nicht an, obwohl beide danebenstanden — und als
    ElegooSlicers Kommandozeile nicht slicen wollte, war das eine Sackgasse
    statt einer Wahl (Robert: „auswahl bei mehreren slicern wäre auch
    sinnvoll").

    Geprüft wird beides: dass drei zu einer Auswahl werden **und** dass einer
    keine wird. Eine Zeile mit einem einzigen Eintrag ist eine Frage ohne
    Antwortmöglichkeit (§2.4) — ohne die zweite Hälfte wäre der Test auch
    grün, wenn das Feld immer erschiene.
    """
    from app.core import discover
    from app.ui.print_settings_dialog import PrintSettingsDialog
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    drei = tuple(
        tmp_path / name / f"{name}.exe" for name in ("ElegooSlicer", "PrusaSlicer", "Cura")
    )
    for entry in drei:
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_bytes(b"")

    monkeypatch.setattr(discover, "remembered_path", lambda _tool: "")
    monkeypatch.setattr(discover, "find_program", lambda *_args: drei[0])

    monkeypatch.setattr(discover, "find_programs", lambda *_args: drei)
    dialog = PrintSettingsDialog(Session(), UiSettings())
    assert dialog.wait_for_slicers(), "die Slicersuche kam nicht zurück"
    assert dialog.slicer_choice.count() == 3, "drei Slicer, drei Zeilen"
    assert [dialog.slicer_choice.itemText(i) for i in range(3)] == [
        "ElegooSlicer",
        "PrusaSlicer",
        "Cura",
    ], "benannt nach dem Installationsordner, nicht nach der Datei"
    assert dialog._slicer_path == drei[0]
    # Die Wahl steht über dem Abschnitt der Profile, nicht in ihm: zugeklappt
    # war sie nicht zu finden (Robert, 27.09.2026: „den slicer kann ich im
    # druckeinstellungen auch nicht einstellen").
    toggle = dialog.slicer_toggle
    assert toggle is not None
    toggle.setChecked(False)
    assert not dialog.slicer_inner.isVisibleTo(dialog), "der Abschnitt ist zu"
    assert dialog.slicer_choice.isVisibleTo(dialog), "und der Slicer bleibt wählbar"
    assert dialog.slicer_label.isVisibleTo(dialog)

    monkeypatch.setattr(discover, "find_programs", lambda *_args: drei[:1])
    einer = PrintSettingsDialog(Session(), UiSettings())
    assert einer.wait_for_slicers(), "die Slicersuche kam nicht zurück"
    assert einer.slicer_choice.count() == 1
    assert not einer.slicer_choice.isVisibleTo(einer), "bei einem gibt es nichts zu wählen"


def test_choosing_another_slicer_drops_the_profiles_of_the_old_one(
    qt_app: object, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ein Wechsel nimmt die Profile nicht mit.

    Maschinen- und Prozessprofil gehören dem Slicer, aus dessen Bestand sie
    stammen. Ein Elegoo-Druckerprofil an PrusaSlicer zu reichen wäre kein
    Fehler, den jemand sähe — der Slicer lehnte still ab oder rechnete mit
    etwas anderem, als im Feld steht.
    """
    from app.core import discover
    from app.ui.print_settings_dialog import PrintSettingsDialog
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    zwei = tuple(tmp_path / name / f"{name}.exe" for name in ("ElegooSlicer", "PrusaSlicer"))
    for entry in zwei:
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_bytes(b"")

    gemerkt: list[str] = []
    monkeypatch.setattr(discover, "remembered_path", lambda _tool: "")
    monkeypatch.setattr(discover, "find_program", lambda *_args: zwei[0])
    monkeypatch.setattr(discover, "find_programs", lambda *_args: zwei)
    monkeypatch.setattr(discover, "remember_path", lambda _tool, value: gemerkt.append(value))

    dialog = PrintSettingsDialog(Session(), UiSettings())
    assert dialog.wait_for_slicers(), "die Slicersuche kam nicht zurück"
    dialog.machine_choice.addItem("Elegoo Centauri Carbon 2 0.4 nozzle")
    dialog.process_choice.addItem("0.20mm Standard @Elegoo CC2 0.4 nozzle")

    dialog._slicer_chosen(1)

    assert dialog._slicer_path == zwei[1], "der gewählte gilt"
    assert gemerkt == [str(zwei[1])], "und er wird gemerkt"
    assert dialog.machine_choice.count() == 0, "das Druckerprofil des alten ist weg"
    assert dialog.process_choice.count() == 0, "das Prozessprofil auch"


def test_prusa_is_warned_only_since_it_prints_on_its_bundle() -> None:
    """Der Befund galt am 03.09.2026 weiter, als er gemeint war — und heute
    gilt er für PrusaSlicer mit Grund.

    ``machine_missing`` entstand für die Orca-Familie, die ihre Maschine als
    Profil aus dem eigenen Bestand lädt. Gemessen am 03.09.2026:

        orca   -> nichts
        cura   -> ['slicer.machine_unset']
        prusa  -> ['slicer.machine_unset']

    Damals schrieb Solidon für PrusaSlicer eine eigenständige ``.ini`` ohne
    Profil, und der Rat, einen Drucker einzurichten, stimmte nicht. Seit Stufe
    C des Konzepts Herstellerprofil (27.09.2026) druckt PrusaSlicer auf
    Drucker, Prozess und Filament seines Bündels; fehlt der Drucker dort,
    kommt der eingebaute Startcode ohne Bettvermessung und Spüllinie — das
    sagt der Befund jetzt. Den Weg mit Bündel prüft ``tests/test_manufacturer.py``.

    Cura stand bis zum 27.09.2026 mit hier, und dort war das Schweigen falsch:
    Ohne Druckerdefinition druckte CuraEngine mit dem Startcode von
    ``fdmprinter``. Was Cura jetzt gesagt bekommt, prüft
    ``tests/test_cura_machine.py``.
    """
    from pathlib import Path

    profile = profiles.make_profile("centauri-carbon-2", "pla")

    setup = handover.SlicerSetup(executable=Path("prusa.exe"), flavour="prusa")
    assert [f.code for f in handover.machine_missing(setup, profile)] == ["slicer.printer_unknown"]
    assert not handover.takes_a_machine_profile("prusa")
    assert not handover.takes_a_machine_profile("cura")
    assert handover.takes_a_machine_profile("orca")


def test_the_orca_family_is_still_warned(monkeypatch) -> None:
    """Die Gegenprobe: Der Fall, für den der Befund gebaut wurde, bleibt."""
    from pathlib import Path

    from app.core.export import slicer_profiles

    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_: "Bambu Lab A1 0.2 nozzle")
    # ElegooSlicer kennt den Centauri Carbon 2; der Kunde kann umstellen (RM-431).
    monkeypatch.setattr(slicer_profiles, "supports_printer", lambda *_: True)
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    setup = handover.SlicerSetup(executable=Path("elegoo-slicer.exe"), flavour="orca")

    assert [f.code for f in handover.machine_missing(setup, profile)] == ["slicer.machine_mismatch"]


def test_the_slicing_run_says_it_too_when_the_machine_side_is_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Anschluss: Der Befund darf nicht nur am Export hängen.

    ``machine_missing`` entstand für ``write_assembly``. Wer auf *Slicen*
    klickt, geht dort nicht vorbei — sein Lauf gelingt mit den Vorgaben des
    Slicers statt mit den Werten aus Solidon, oder er scheitert, und die
    Orca-Familie sagt dazu nur „Slic3r::CLI::run found error, exit".

    **Gemessen am 03.09.2026 gegen ElegooSlicer 1.5.3.4 auf dieser Maschine**,
    einmal mit Maschinenseite und einmal ohne, dieselbe Datei:

        mit    286 957 Bytes G-Code, 100 Schichten, 103 × ``G92 E0``, ein ``G28``
        ohne   Exit -17, „process not compatible with printer.", keine Datei

    Ohne den Befund erführe der Kunde in beiden Fällen nicht, woran es lag.
    """
    from app.core.export import slicer_profiles

    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_: "Bambu Lab A1 0.2 nozzle")
    # ElegooSlicer kennt den Centauri Carbon 2; der Kunde kann umstellen (RM-431).
    monkeypatch.setattr(slicer_profiles, "supports_printer", lambda *_: True)
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    model, setup = _slicer_writing(
        monkeypatch, tmp_path, _gcode_printing_at(-10.0, 10.0), flavour="orca"
    )

    outcome = handover.slice_model(model, settings, profile, setup, output_dir=tmp_path)

    codes = [finding.code for finding in outcome.findings]
    assert "slicer.machine_mismatch" in codes, codes


def test_a_matching_machine_leaves_the_slicing_run_quiet(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Gegenprobe: Passt die Maschine, wird nichts gesagt."""
    from app.core.export import slicer_profiles

    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_: "Meine Maschine")
    monkeypatch.setattr(slicer_profiles, "printer_for", lambda *_: "centauri-carbon-2")
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    model, setup = _slicer_writing(
        monkeypatch, tmp_path, _gcode_printing_at(-10.0, 10.0), flavour="orca"
    )

    outcome = handover.slice_model(
        model, print_settings.resolve(profile), profile, setup, output_dir=tmp_path
    )

    assert not [f for f in outcome.findings if f.code.startswith("slicer.machine_")]


def test_a_machine_profile_of_another_printer_is_not_handed_over(monkeypatch) -> None:
    """Eine gemerkte Wahl überlebt den Drucker nicht, zu dem sie gehört.

    **Gemessen am 03.09.2026, gemeldet von 3d-druck-c7.** Der Druckdialog merkt
    sich das zuletzt gewählte Maschinenprofil und reicht es unbesehen weiter.
    Wer den Drucker des Projekts wechselt, bekommt es trotzdem — vier Drucker,
    viermal dasselbe Profil. Die geschriebene Maschinendatei sah für ein
    Prusa-MK4S-Projekt so aus:

        printer_model    Elegoo Centauri Carbon 2
        Bauraum          256 x 256 x 256   (der Prusa hat 250 x 210 x 220)
        Startcode        ;===== CC2_START_GCODE

    Der Prusa hat 210 mm in Y; die Datei behauptet 256. Ein Teil, das Solidon
    als passend ausweist, ragt damit 46 mm über die Kante — und der Anfahrcode
    ist der einer fremden Maschine, wofür der Docstring von ``machine_for``
    seit gestern „ein Homing-Befehl der falschen Maschine fährt die Düse ins
    Bett" schreibt.

    **Die Sperre gab es, und ein Weg von zweien fragte sie.**
    ``settings_for_export`` vergleicht ``slicer_profile_printer`` und gibt
    nichts zurück, wenn die Drucker abweichen; ``_current_setup`` im Dialog
    liest die Auswahlfelder ungefiltert. Die Prüfung sitzt jetzt im Kern, wo
    beide Wege durchmüssen.

    **Was weiterhin gilt:** ein Profil, das Solidon keinem Drucker zuordnen
    kann. Ein selbst gebautes gehört seinem Besitzer, und es ihm wegzunehmen
    wäre schlimmer als es zu nehmen — geprüft wird gegen einen *anderen
    bekannten* Drucker, nicht gegen „nicht erkannt".
    """
    from pathlib import Path

    from app.core.export import slicer_profiles

    known = {
        "Elegoo Centauri Carbon 2 0.4 nozzle": "centauri-carbon-2",
        "Prusa MK4S 0.4 nozzle": "prusa-mk4s",
    }
    monkeypatch.setattr(slicer_profiles, "printer_for", lambda name, _table: known.get(name, ""))
    monkeypatch.setattr(slicer_profiles, "chosen_machine", lambda *_: "")
    setup = handover.SlicerSetup(
        executable=Path("elegoo-slicer.exe"),
        flavour="orca",
        machine_profile="Elegoo Centauri Carbon 2 0.4 nozzle",
    )

    eigener = profiles.make_profile("centauri-carbon-2", "pla")
    fremder = profiles.make_profile("prusa-mk4s", "pla")

    assert handover.machine_for(setup, eigener) == "Elegoo Centauri Carbon 2 0.4 nozzle"
    assert handover.machine_for(setup, fremder) == "", "das Profil gehört einer anderen Maschine"

    # Und der Kunde erfährt es, statt eine falsch adressierte Datei zu bekommen.
    codes = [finding.code for finding in handover.machine_missing(setup, fremder)]
    assert "slicer.machine_mismatch" in codes, codes


def test_a_profile_solidon_cannot_place_stays_the_customers(monkeypatch) -> None:
    """Ein selbst gebautes Profil gehört seinem Besitzer.

    ``printer_for`` ordnet nur zu, was es kennt. Ein Profil ohne Zuordnung als
    fremd zu behandeln nähme dem Kunden genau die Wahl weg, die er von Hand
    getroffen hat — und ein Slicer ohne Maschinenprofil lehnt den Auftrag ab.
    Geprüft wird deshalb gegen einen *anderen bekannten* Drucker.
    """
    from pathlib import Path

    from app.core.export import slicer_profiles

    monkeypatch.setattr(slicer_profiles, "printer_for", lambda *_: "")
    setup = handover.SlicerSetup(
        executable=Path("elegoo-slicer.exe"),
        flavour="orca",
        machine_profile="Meine eigene Maschine",
    )

    profile = profiles.make_profile("prusa-mk4s", "pla")

    assert handover.machine_for(setup, profile) == "Meine eigene Maschine"
    assert handover.machine_missing(setup, profile) == []


def test_prusa_and_cura_get_the_bed_of_the_machine_not_of_the_document(tmp_path: Path) -> None:
    """Gesamtreview 05.09.2026, CORE-17: PrusaSlicer bekam eine Bettform von
    ``-125`` bis ``125``, Cura ``machine_center_is_zero=true`` — Solidons Welt
    um den Ursprung, nicht die des Druckers, der von der Ecke misst. Der
    Slicer schrieb Bahnen bei ``-13,6``, die es auf der Maschine nicht gibt,
    und die eigene Gegenprobe maß gegen denselben erfundenen Ursprung. Beide
    bekommen jetzt das Bett, das der Drucker hat, und die Teile darin."""
    profile = profiles.make_profile("prusa-mk4s", "pla")
    width, depth, height = profile.printer.build_volume

    prusa = handover._machine_keys(profile, "prusa")
    assert prusa["bed_shape"] == f"0x0,{width:g}x0,{width:g}x{depth:g},0x{depth:g}"
    assert prusa["max_print_height"] == f"{height:g}"

    cura = handover._machine_keys(profile, "cura")
    assert cura["machine_center_is_zero"] == "false"
    assert cura["z_seam_x"] == f"{width / 2.0:g}", "hinten in der Mitte, in Bettkoordinaten"
    assert cura["z_seam_y"] == f"{depth:g}"
    assert "mesh_position_x" not in cura and "mesh_position_y" not in cura


def test_prusa_and_cura_get_a_bed_around_the_machines_own_origin() -> None:
    """RM-424: Ohne Druckerprofil des Bündels beschreibt Solidon die Maschine
    selbst — und schrieb jedem Drucker ein Bett ab der Ecke, auch dem BIBO
    (``bed_shape = -107x-93,…``) oder einem Delta. Die Teile kommen um dessen
    Nullpunkt (``build_area.machine_shift``), also muss die Bettform es auch."""
    base = profiles.make_profile("prusa-mk4s", "pla")
    bibo = replace(base.printer, build_volume=(214.0, 186.0, 160.0), bed_origin=(0.0, 0.0))
    centred = replace(base, printer=bibo)

    prusa = handover._machine_keys(centred, "prusa")
    assert prusa["bed_shape"] == "-107x-93,107x-93,107x93,-107x93"
    cura = handover._machine_keys(centred, "cura")
    assert cura["machine_center_is_zero"] == "true"
    assert (cura["z_seam_x"], cura["z_seam_y"]) == ("0", "93"), "hinten in der Mitte"
    assert "mesh_position_x" not in cura

    # Der Dremel 3D45: weder Ecke noch Mitte. Cura kennt dafür keinen
    # Schalter; ``mesh_position`` verschiebt jedes Netz um den Rest — von
    # CuraEngines halbem Bett (112,5 / 77,5) zurück auf (-15 / 0).
    dremel = replace(base.printer, build_volume=(225.0, 155.0, 170.0), bed_origin=(15.0, 0.0))
    offset = replace(base, printer=dremel)
    prusa = handover._machine_keys(offset, "prusa")
    assert prusa["bed_shape"] == "-127.5x-77.5,97.5x-77.5,97.5x77.5,-127.5x77.5"
    cura = handover._machine_keys(offset, "cura")
    assert cura["machine_center_is_zero"] == "false"
    assert (cura["mesh_position_x"], cura["mesh_position_y"]) == ("-127.5", "-77.5")
    assert (cura["z_seam_x"], cura["z_seam_y"]) == ("-15", "77.5")


def test_slot_advice_uses_inherited_values_and_the_adopted_group_reaches_both_outputs(
    tmp_path: Path,
) -> None:
    """Herstellerwerte beraten; die ausdrücklich angenommene Gruppe gewinnt danach."""
    from app.core.types import SlotOverride

    parent = _filament_profile(
        tmp_path, "Grundlage", slow_down_layer_time=["0"], filament_max_volumetric_speed=["3"]
    )
    own = _filament_profile(tmp_path, "Meine Spule", inherits=parent.stem)
    slot = MaterialSlot(0, "Meine Spule", material=str(own), material_type="PLA")
    profile = profiles.make_profile("prusa-mk4s", "pla")
    settings = print_settings.resolve(profile)
    setup = handover.SlicerSetup(Path("orca-slicer.exe"), "orca")

    effective = handover.settings_for_slot(settings, profile, slot, setup)
    assert effective.filament.max_flow == pytest.approx(3.0)
    recommendation = next(
        item
        for item in advise.advise(effective, profile, _layers(1.0, 1.0))
        if item.path == "cooling.minimum_layer_time"
    )
    adopted = advise.apply(effective, [recommendation])
    settings = handover.with_slot_override(settings, slot, SlotOverride(cooling=adopted.cooling))
    config = handover.write_config(settings, profile, setup, tmp_path, (slot,))
    emitted = json.loads(config.filaments[0].read_text(encoding="utf-8"))
    embedded = handover.project_settings(settings, profile, setup, slots=(slot,))
    assert emitted["slow_down_layer_time"] == ["15"]
    assert embedded["slow_down_layer_time"] == ["15"]
    assert emitted["filament_max_volumetric_speed"] == ["3"]


def test_written_slicer_values_include_the_resolved_temperature_of_every_tool(
    tmp_path: Path,
) -> None:
    """Der Sollwert ist die ausgegebene Datei; auch der zweite Extruder zählt."""
    from app.core.types import SlotOverride

    inherited = _filament_profile(tmp_path, "PLA", nozzle_temperature=["205"])
    first = MaterialSlot(0, "Erste", material=str(inherited), material_type="PLA")
    second = MaterialSlot(1, "Zweite", material_type="PLA")
    profile = profiles.make_profile("prusa-mk4s", "pla")
    settings = print_settings.resolve(profile)
    settings = handover.with_slot_override(
        settings, second, SlotOverride(temperature=replace(settings.temperature, nozzle=230))
    )
    setup = handover.SlicerSetup(Path("orca-slicer.exe"), "orca")
    config = handover.write_config(settings, profile, setup, tmp_path, (first, second))

    assert handover.verify_settings({"nozzle_temperature": "205,230"}, config.written) == []
    findings = handover.verify_settings({"nozzle_temperature": "205,210"}, config.written)
    assert [item.code for item in findings] == ["slicer.setting_ignored"]
    assert "230" in str(findings[0].values["settings"])


@pytest.mark.parametrize("flavour", ["prusa", "cura"])
def test_unreachable_material_defaults_are_reported_without_manual_overrides(flavour: str) -> None:
    """PLA und PETG unterscheiden sich bereits ohne eine bearbeitete Temperaturgruppe."""
    profile = profiles.make_profile("prusa-mk4s", "pla")
    settings = print_settings.resolve(profile)
    slots = (
        MaterialSlot(0, "PLA", material_type="PLA"),
        MaterialSlot(1, "PETG", material_type="PETG"),
    )
    setup = handover.SlicerSetup(Path("slicer"), flavour)
    findings = handover.unreachable_overrides(settings, setup, slots, profile=profile)
    assert "slicer.overrides_unreachable" in {entry.code for entry in findings}
    same = (slots[0], replace(slots[0], index=1))
    assert handover.unreachable_overrides(settings, setup, same, profile=profile) == []


@pytest.mark.parametrize("actual", ["205,230", "[205,230]", '["205";"230"]'])
def test_the_gcode_comparison_preserves_all_filament_values(actual: str) -> None:
    """Die beiden Kommentarformate sind gleichwertig; ein fehlender Wert nicht."""
    assert (
        handover.verify_settings({"nozzle_temperature": actual}, {"nozzle_temperature": "205,230"})
        == []
    )
    assert handover.verify_settings(
        {"nozzle_temperature": "205"}, {"nozzle_temperature": "205,230"}
    )


def test_the_gcode_comparison_unescapes_quotes_without_hiding_real_differences() -> None:
    """PrusaStartcode bleibt gleich, wenn der Slicer Anführungszeichen entmaskiert."""
    written = {"start_gcode": r"M862.3 P \"[printer_model]\""}

    assert handover.verify_settings({"start_gcode": 'M862.3 P "[printer_model]"'}, written) == []
    findings = handover.verify_settings({"start_gcode": 'M862.3 P "[different_printer]"'}, written)
    assert [item.code for item in findings] == ["slicer.setting_ignored"]


def test_the_gcode_comparison_does_not_unescape_other_setting_values() -> None:
    """Die G-Code-Normalisierung darf abweichende Nicht-G-Code-Werte nicht verdecken."""
    findings = handover.verify_settings(
        {"vendor_note": 'M862.3 P "[printer_model]"'},
        {"vendor_note": r"M862.3 P \"[printer_model]\""},
    )

    assert [item.code for item in findings] == ["slicer.setting_ignored"]


def test_filament_profile_comparison_uses_the_same_quote_normalization(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die zweite Nutzung von ``_same`` unterscheidet keine G-Code-Schreibweisen."""
    profile_path = tmp_path / "filament.json"
    profile_path.touch()
    settings = print_settings.resolve(profiles.make_profile())
    setup = handover.SlicerSetup(
        executable=Path("orca-slicer.exe"), flavour="orca", base_filament=str(profile_path)
    )
    monkeypatch.setattr(handover, "profile_file", lambda *_args: profile_path)
    monkeypatch.setattr(handover, "_profile_roots", lambda _setup: ())
    monkeypatch.setattr(
        handover.slicer_profiles,
        "resolve_values",
        lambda _base, *, roots: {"filament_start_gcode": ['M862.3 P \\"[printer_model]\\"']},
    )
    monkeypatch.setattr(
        handover,
        "by_section",
        lambda *_args: {"filament": {"filament_start_gcode": 'M862.3 P "[printer_model]"'}},
    )

    assert handover.profile_differences(settings, setup) == []


@pytest.mark.parametrize("initial_error", [b"outside printable area", b"found error, exit"])
def test_arrangement_fallback_does_not_disable_later_valid_layouts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, initial_error: bytes
) -> None:
    """Eine unzulässige erste Platte sagt nichts über die nächste Platte aus."""
    profile = profiles.make_profile()
    model = tmp_path / "model.stl"
    model.write_bytes(b"solid x\nendsolid x\n")
    setup = handover.SlicerSetup(tmp_path / "slicer.exe", "orca")
    setup.executable.write_bytes(b"")
    commands: list[list[str]] = []

    def run(command: list[str], *args: object, **kwargs: object) -> _Finished:
        commands.append(command)
        if len(commands) == 1:
            result = _Finished(initial_error)
            result.returncode = -64
            return result
        folder = Path(command[command.index("--outputdir") + 1])
        (folder / "plate_1.gcode").write_text(_gcode_printing_at(1, 5), encoding="utf-8")
        return _Finished(b"")

    monkeypatch.setattr(handover, "_run_slicer", run)
    settings = print_settings.resolve(profile)
    handover.slice_model(model, settings, profile, setup, keep_arrangement=True)
    handover.slice_model(model, settings, profile, setup, keep_arrangement=True)
    assert len(commands) == 3
    assert "--arrange" in commands[-1]


def test_cura_machine_enables_the_available_heated_bed() -> None:
    """Eine Bettzieltemperatur muss im Engine-Auftrag tatsächlich heizen können."""
    profile = profiles.make_profile()
    assert handover._machine_keys(profile, "cura")["machine_heated_bed"] == "true"
    cold = replace(profile, printer=replace(profile.printer, bed_temperature_max=0.0))
    assert handover._machine_keys(cold, "cura")["machine_heated_bed"] == "false"


def test_each_manual_orca_filament_declares_its_support_role(tmp_path: Path) -> None:
    """Mehrere manuelle Rollen brauchen gleich lange Pflichtfelder im Slicer."""
    profile = profiles.make_profile()
    setup = handover.SlicerSetup(tmp_path / "slicer.exe", "orca")
    for index, material in enumerate(("PLA", "PETG")):
        document = handover._orca_filament(
            {},
            print_settings.resolve(profile),
            profile,
            setup,
            MaterialSlot(index, material, material_type=material),
        )
        assert document["filament_is_support"] == ["0"]


@pytest.mark.parametrize("flavour", ["cura", "prusa"])
@pytest.mark.parametrize("with_header", [False, True])
def test_slicer_readback_uses_the_effective_filament_and_respects_file_headers(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, flavour, with_header
) -> None:
    """Fehlende Dateikennwerte werden vom wirklichen Filament ergänzt; Dateiangaben gewinnen."""
    import math

    from app.core.types import SlotOverride

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    slot = MaterialSlot(0, "Eigene Rolle", material_type="PLA")
    settings = handover.with_slot_override(
        settings,
        slot,
        SlotOverride(filament=replace(settings.filament, diameter=2.85, density=1.37)),
    )
    payload = _gcode_printing_at(10.0, 20.0)
    if with_header:
        payload += "; filament_diameter = 1.9\n; filament_density = 1.05\n"
    model, setup = _slicer_writing(monkeypatch, tmp_path, payload, flavour=flavour)
    outcome = handover.slice_model(
        model,
        settings,
        profile,
        setup,
        output_dir=tmp_path,
        slots=(slot,),
    )
    diameter, density = (1.9, 1.05) if with_header else (2.85, 1.37)
    assert outcome.metrics.filament_diameters == pytest.approx((diameter,))
    assert outcome.metrics.filament_densities == pytest.approx((density,))
    expected = outcome.metrics.filament_mm * math.pi * (diameter / 2) ** 2 * density / 1000
    assert outcome.metrics.grams(None, None) == pytest.approx(expected)


def test_orca_readback_keeps_every_tools_values_and_the_written_firmware(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Werkzeugwechsel werden mit geschriebenem Dialekt und individuellen Kennwerten gelesen."""
    from app.core.types import SlotOverride

    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    slots = (
        MaterialSlot(0, "Erste", material_type="PLA"),
        MaterialSlot(1, "Zweite", material_type="PLA"),
    )
    for slot, diameter, density in zip(slots, (1.75, 2.85), (1.1, 1.4), strict=True):
        settings = handover.with_slot_override(
            settings,
            slot,
            SlotOverride(filament=replace(settings.filament, diameter=diameter, density=density)),
        )
    payload = "G90\nM82\nG1 X0 Y0 Z0.2\nG1 X5 E1\nT1\nG1 X10 E2\n"
    model, setup = _slicer_writing(monkeypatch, tmp_path, payload, flavour="orca")
    machine = tmp_path / "machine.json"
    machine.write_text(
        json.dumps({"type": "machine", "name": "Testmaschine", "gcode_flavor": "marlin"}),
        encoding="utf-8",
    )
    setup = replace(setup, machine_profile=str(machine))
    outcome = handover.slice_model(
        model,
        settings,
        profile,
        setup,
        output_dir=tmp_path,
        slots=slots,
    )
    assert outcome.metrics.filament_diameters == pytest.approx((1.75, 2.85))
    assert outcome.metrics.filament_densities == pytest.approx((1.1, 1.4))
    assert outcome.metrics.filament_mm_by_tool == pytest.approx((1.0, 1.0))


def test_cura_reports_its_fan_ramp_instead_of_claiming_an_off_phase() -> None:
    """Kein Exaktwert darf als native Rampe verkauft werden — und keine exakte
    Übertragung als Verlust. Curas Hochlauf vom Anfangslüfter null bis
    ``cool_fan_full_layer`` ist für null und eine Schicht ohne Lüfter genau die
    Abschaltphase; erst ab zwei laufen die Schichten dazwischen an. Vorher
    warnte jede Cura-Übergabe, auch mit der Vorgabe von einer Schicht."""
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    for count, full in ((0, "1"), (1, "2"), (3, "4")):
        changed = print_settings.with_path(settings, "cooling.disable_first_layers", count)
        values = handover.values_for(changed, profile, "cura")
        assert values["cool_fan_full_layer"] == full
        assert values["cool_fan_speed_0"] == "0"
        warned = handover.setting_limitations("cura", changed)
        if count < 2:
            assert warned == [], f"{count} Schichten kommen genau an"
        else:
            assert [entry.values["path"] for entry in warned] == ["cooling.disable_first_layers"]
            assert warned[0].suggestions
            assert "4" in warned[0].message.translate("de")
        # Das Cura-Fenster bekommt nur diese Seite und rechnet die Schicht
        # mit seiner eigenen Formel aus der Höhe.
        page = handover.as_mapping(changed, "cura")
        assert page["cool_fan_speed_0"] == "0"
        assert "cool_fan_full_at_height" in page
        assert "cool_fan_full_layer" not in page
    assert slicer_keys.takes("cura", "cooling.disable_first_layers")
    assert handover.setting_limitations("cura") == [], "ohne Einstellungen kein Urteil"


@pytest.mark.parametrize("first", [0.1, 0.12, 0.2, 0.25, 0.28, 0.3, 0.32])
@pytest.mark.parametrize("layer", [0.08, 0.1, 0.12, 0.16, 0.2, 0.24, 0.28, 0.3])
def test_curas_fan_layer_formula_lands_on_the_layer_after_the_pause(
    first: float, layer: float
) -> None:
    """Cura rundet die Höhe ab (``fdmprinter.def.json``). Auf der Oberkante der
    Schicht entschiede der letzte Bitfehler — deshalb die Mitte, und hier jede
    Kombination aus dem Bereich der Stufen, mit null bis sechs Schichten."""
    profile = profiles.make_profile()
    settings = print_settings.resolve(profile)
    settings = print_settings.with_path(settings, "layers.layer_height", layer)
    settings = print_settings.with_path(settings, "layers.first_layer_height", first)
    for count in range(7):
        changed = print_settings.with_path(settings, "cooling.disable_first_layers", count)
        values = handover.values_for(changed, profile, "cura")
        assert float(values["cool_fan_full_at_height"]) >= 0.0, "Cura verlangt mindestens 0"
        assert values["cool_fan_full_layer"] == str(count + 1), (first, layer, count)


def test_cura_fan_in_the_off_layers_is_measured_in_the_print_file() -> None:
    """Curas Hochlauf trifft die Pause, aber kurze Schichten kühlt es auch dort.

    Gemessen am 26.09.2026 mit CuraEngine 5.13 und einer Schicht ohne Lüfter:
    am 20-mm-Würfel ``M106 S53.5`` in der ersten Schicht, am 120-mm-Würfel
    ``M107``. Vor dem Slicen kennt niemand die Schichtzeit; also spricht die
    Druckdatei, und nur dann, wenn der Lüfter wirklich zu früh läuft.
    """
    settings = print_settings.resolve(profiles.make_profile())
    assert settings.cooling.disable_first_layers == 1
    early = gcode.analyze(
        "M82\nM107\n;LAYER:0\nM106 S53.5\nG0 X0 Y0 Z0.2\nG1 X10 E1\n"
        ";LAYER:1\nM106 S255\nG1 X20 E2\n"
    )
    held = gcode.analyze(
        "M82\nM107\n;LAYER:0\nM107\nG0 X0 Y0 Z0.2\nG1 X10 E1\n;LAYER:1\nM106 S127.5\nG1 X20 E2\n"
    )

    found = handover.fan_in_off_layers(early, settings, "cura")

    assert found is not None
    assert found.source == "gcode" and found.severity == "warning"
    assert found.suggestions
    assert "Schicht 1 mit 21 %" in found.message.translate("de")
    assert handover.fan_in_off_layers(held, settings, "cura") is None
    for flavour in ("orca", "prusa"):
        assert handover.fan_in_off_layers(early, settings, flavour) is None, (
            f"{flavour} hält die Pause selbst"
        )
    longer = print_settings.with_path(settings, "cooling.disable_first_layers", 2)
    found = handover.fan_in_off_layers(held, longer, "cura")
    assert found is not None and "Schicht 2 mit 50 %" in found.message.translate("de")


def _standing_box(name: str, extents: tuple[float, float, float]) -> Any:
    """Ein Quader, der auf dem Bett steht, als Körper der Szene."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject

    mesh = trimesh.creation.box(extents=extents)
    mesh.apply_translation((0.0, 0.0, extents[2] / 2.0))
    return SceneObject(id=f"obj_{name}", name=name, mesh=MeshData.of(mesh))


def _advice_of(bodies: tuple[Any, ...], settings: Any, profile: Any, flavour: Any = "orca") -> list:
    """Der Rat des Druckdialogs für diese Körper, ohne Fenster gerechnet."""
    from app.ui.print_settings_dialog import _AdviceWorker

    worker = _AdviceWorker(bodies, settings, profile, None, {}, (), (), {}, flavour=flavour)
    got: list[list] = []
    worker.done.connect(lambda entries, _results: got.append(entries))
    worker.work()
    assert got, "der Arbeiter kam ohne Rat zurück"
    return got[0]


@pytest.mark.parametrize("kind", ["auto", "skirt"])
def test_without_a_slicer_the_dialog_advises_for_its_actual_export(
    tmp_path: Path, kind: str
) -> None:
    """B13: Der echte Arbeiterstart bindet den Rat an dieselbe Familie wie
    die anschließend geschriebene Datei. Eine ungebundene Kernprobe genügt nicht."""
    from types import SimpleNamespace

    from app.core.export.writer import write_assembly
    from app.ui.print_settings_dialog import PrintSettingsDialog

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.with_path(print_settings.resolve(profile), "adhesion.kind", kind)
    bodies = (_standing_box("Turm", (4.0, 4.0, 80.0)),)
    received: list[Any] = []
    started: list[Any] = []

    def quiet(*_args: Any) -> None:
        pass

    state = SimpleNamespace(
        _settling=False,
        _advice_pending=True,
        _plate_bodies=lambda: bodies,
        session=SimpleNamespace(profile=profile, busy=False),
        settings=settings,
        _advice_worker=None,
        _advice_request=(),
        _advice_context=lambda: (),
        _current_flavour=lambda: None,
        _slicer_path=None,
        _plate_slots=list,
        _profiles_for=lambda _slots: [],
        _analysis_context=lambda: (),
        _analysed_context=(),
        _body_analyses={},
        _fits_in_play=lambda: (),
        _connector_diameters=lambda: (),
        _part_fits=dict,
        _advice_ready=lambda _worker, _context, _analysis, entries, _results: received.extend(
            entries
        ),
        _advice_failed=quiet,
        _advice_progressed=quiet,
        _advice_finished=quiet,
        _leash=SimpleNamespace(start=started.append),
    )

    PrintSettingsDialog._start_advice(state)
    assert len(started) == 1
    worker = started[0]
    assert worker.setup is None and worker.flavour == "orca"
    worker.work()
    brim = [entry for entry in received if entry.path == "adhesion.kind"]
    assert [entry.value for entry in brim] == ([] if kind == "auto" else ["brim"])

    written, _findings = write_assembly(
        list(bodies),
        tmp_path,
        project_name="Satz",
        profile=profile,
        settings=advise.apply(settings, brim),
    )
    with zipfile.ZipFile(written) as archive:
        process = json.loads(archive.read("Metadata/project_settings.config"))
        parts = ET.fromstring(archive.read("Metadata/model_settings.config"))
    assert process["brim_type"] == ("auto_brim" if kind == "auto" else "no_brim")
    actual = [
        entry.get("value") for entry in parts.iter("metadata") if entry.get("key") == "brim_type"
    ]
    assert actual == ([] if kind == "auto" else ["outer_only"])


def test_the_advice_names_the_part_the_export_gives_it_to(tmp_path: Path) -> None:
    """Die Zeile im Druckdialog nennt das Teil, an das der Export den
    übernommenen Vorschlag schreibt (Konzept Herstellerprofil, Stufe E).

    Seit Entscheidung G gilt ein Vorschlag aus der Geometrie dem Körper, der
    ihn verlangt. Die Zeile sagte davon nichts: „Haftung: Skirt → Brim" las
    sich wie ein Rand um jedes Teil. Jetzt steht der Turm daran — und genau
    der Turm bekommt den Brim in der Datei, Platte und Klotz nicht.
    """
    from app.core.export.writer import write_assembly
    from app.ui.print_settings_dialog import _TargetedAdvice

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.resolve(profile, "standard")
    assert settings.adhesion.kind == "skirt", "die Vorbedingung des Tests"
    bodies = (
        _standing_box("Turm", (4.0, 4.0, 80.0)),
        _standing_box("Platte", (60.0, 60.0, 10.0)),
        _standing_box("Klotz", (30.0, 30.0, 10.0)),
    )

    entries = _advice_of(bodies, settings, profile)

    brim = [entry for entry in entries if entry.path == "adhesion.kind"]
    assert len(brim) == 1 and brim[0].value == "brim", entries
    assert isinstance(brim[0], _TargetedAdvice)
    assert brim[0].parts == ("Turm",)
    written, _findings = write_assembly(
        list(bodies),
        tmp_path,
        project_name="Satz",
        profile=profile,
        settings=advise.apply(settings, brim),
    )
    config = ET.fromstring(zipfile.ZipFile(written).read("Metadata/model_settings.config"))
    branded = {
        own.get("name", ""): own.get("brim_type")
        for node in config.iter("object")
        if (own := {meta.get("key"): meta.get("value") for meta in node.findall("metadata")})
    }
    assert branded == {"Turm": "outer_only", "Platte": None, "Klotz": None}


@pytest.mark.parametrize("case", ["one_body", "every_body", "plate_wide_slicer"])
def test_a_proposal_for_the_whole_plate_names_no_part(case: str) -> None:
    """Die Gegenproben: Ein Körper allein, ein Vorschlag, den jedes Teil
    verlangt, und ein Slicer, der keine Werte je Teil annimmt — dann gilt die
    Zeile der Platte, und sie nennt kein Teil."""
    from app.ui.print_settings_dialog import _TargetedAdvice

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.resolve(profile, "standard")
    tower = _standing_box("Turm", (4.0, 4.0, 80.0))
    bodies: tuple[Any, ...] = (tower,)
    flavour = "orca"
    if case == "every_body":
        bodies = (tower, _standing_box("Mast", (5.0, 5.0, 90.0)))
    elif case == "plate_wide_slicer":
        bodies = (tower, _standing_box("Platte", (60.0, 60.0, 10.0)))
        flavour = "other"

    entries = _advice_of(bodies, settings, profile, flavour)

    brim = [entry for entry in entries if entry.path == "adhesion.kind"]
    assert len(brim) == 1 and brim[0].value == "brim", entries
    assert not isinstance(brim[0], _TargetedAdvice) or not brim[0].parts


def test_a_long_list_of_parts_is_counted_in_the_line_and_named_in_full_beside_it() -> None:
    """Drei Teile stehen in der Zeile, ab vier die ersten zwei und die Zahl der
    übrigen; der Tooltip und der Bildschirmleser bekommen alle."""
    from types import SimpleNamespace

    from app.ui.print_settings_dialog import PrintSettingsDialog, _TargetedAdvice

    host = SimpleNamespace(_fields={"adhesion.kind": SimpleNamespace(title="Haftung")})

    def entry(*parts: str) -> _TargetedAdvice:
        return _TargetedAdvice(
            path="adhesion.kind", value="brim", was="skirt", reason="", parts=parts
        )

    few = entry("Turm", "Mast", "Fahne")
    many = entry("Scheibe 1", "Scheibe 2", "Scheibe 3", "Scheibe 4", "Scheibe 5")

    assert PrintSettingsDialog._advice_title(host, few) == "Haftung · Turm, Mast, Fahne"
    assert (
        PrintSettingsDialog._advice_title(host, many)
        == "Haftung · Scheibe 1, Scheibe 2 und 3 weitere"
    )
    assert PrintSettingsDialog._advice_parts(many) == (
        "Gilt für: Scheibe 1, Scheibe 2, Scheibe 3, Scheibe 4, Scheibe 5"
    )
    assert PrintSettingsDialog._advice_parts(entry()) == ""


def test_opening_curas_window_writes_the_3mf_the_console_writes_an_stl(tmp_path: Path) -> None:
    """*Im Slicer öffnen* verlangt die Datei fürs Fenster (RM-257): bei Cura die
    3MF mit Sperre und Werten je Teil. *Slicen* bleibt beim STL mit Netzliste,
    denn CuraEngine liest keine 3MF."""
    from app.ui.print_settings_dialog import _OpenInSlicerWorker, _PlateJob, _prepare_plate

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    job = _PlateJob(
        objects=(_standing_box("Klotz", (20.0, 20.0, 10.0)),),
        plates=(0,),
        folder=tmp_path,
        name="t",
        setup=handover.SlicerSetup(tmp_path / "CuraEngine.exe", "cura"),
        settings=print_settings.resolve(profile, "standard"),
        profile=profile,
        slot_profiles={},
    )

    window = _OpenInSlicerWorker(job)._job

    assert window.for_window and not job.for_window
    assert _prepare_plate(window, 0).model.suffix == ".3mf"
    assert _prepare_plate(job, 0).model.suffix == ".stl"


def _supported_parts(written: Path, flavour: str) -> set[str]:
    """Welche Teile der Datei als Objekt- oder Netzwert Stützen tragen."""
    if flavour == "cura":
        return {
            mesh.path.name
            for mesh in handover.cura_meshes(written)
            if dict(mesh.settings).get("support_enable") == "true"
        }
    member, key = {
        "orca": ("Metadata/model_settings.config", "enable_support"),
        "prusa": ("Metadata/Slic3r_PE_model.config", "support_material"),
    }[flavour]
    config = ET.fromstring(zipfile.ZipFile(written).read(member))
    supported: set[str] = set()
    for node in config.iter("object"):
        own = {meta.get("key", ""): meta.get("value", "") for meta in node.findall("metadata")}
        if own.get(key) == "1":
            supported.add(own.get("name", node.get("id", "")))
    return supported


@pytest.mark.parametrize(
    ("flavour", "program"),
    [
        ("orca", "elegoo-slicer.exe"),
        ("prusa", "prusa-slicer-console.exe"),
        ("cura", "CuraEngine.exe"),
    ],
)
def test_an_accepted_suggestion_is_asked_of_the_whole_job_not_one_plate(
    tmp_path: Path, flavour: str, program: str
) -> None:
    """Durchsicht 0.5.1, N1: *Slicen* schreibt je Platte eine Datei. Verlangt
    der Pilz auf Platte 1 die übernommenen Stützen, bekommt der Klotz auf
    Platte 2 keine. Bis dahin bekam er sie, weil auf seiner Platte kein Teil
    sie verlangte — der Ausgangsfehler von Entscheidung G, auf den übrigen
    Platten zurück.

    Die Gegenprobe steht am Ende: Ist der Klotz allein der ganze Auftrag,
    gilt der übernommene Vorschlag weiter jedem Teil (B2)."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject
    from app.ui.print_settings_dialog import _PlateJob, _prepare_plate

    stem = trimesh.creation.box(extents=(10.0, 10.0, 20.0))
    stem.apply_translation((0.0, 0.0, 10.0))
    cap = trimesh.creation.box(extents=(40.0, 40.0, 3.0))
    cap.apply_translation((0.0, 0.0, 21.5))
    mushroom = SceneObject(
        id="obj_1", name="Pilz", mesh=MeshData.of(trimesh.boolean.union([stem, cap])), plate=0
    )
    block = replace(_standing_box("Klotz", (30.0, 30.0, 10.0)), plate=1)
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.with_accepted(
        print_settings.resolve(profile, "standard"), "support.style", "auto"
    )
    job = _PlateJob(
        objects=(mushroom, block),
        plates=(0, 1),
        folder=tmp_path,
        name="t",
        setup=handover.SlicerSetup(tmp_path / program, flavour),
        settings=settings,
        profile=profile,
        slot_profiles={},
    )

    first, second = _prepare_plate(job, 0), _prepare_plate(job, 1)

    assert len(_supported_parts(first.model, flavour)) == 1, "der Pilz"
    assert _supported_parts(second.model, flavour) == set()
    assert "export.part_setting_all" not in {entry.code for entry in second.findings}

    alone = replace(job, objects=(block,), plates=(1,), folder=tmp_path / "allein")
    alone.folder.mkdir()
    run = _prepare_plate(alone, 1)
    assert len(_supported_parts(run.model, flavour)) == 1, "B2: kein Teil verlangt, alle tragen"
    assert "export.part_setting_all" in {entry.code for entry in run.findings}


def test_the_file_export_of_a_selection_asks_the_whole_job(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review des Nachtrags 0.5.1, N6: Der Dateiexport aus dem Hauptfenster
    schreibt nur die gewählten Körper, fragt übernommene Vorschläge aber am
    ganzen Auftrag. Mit nur dem Klotz gewählt trug seine 3MF die übernommenen
    Stützen des Pilzes, und der Bericht sagte, sie gälten allen Teilen — der
    Druckdialog hatte sie dem Pilz zugeschrieben. Der Exportarbeiter hielt den
    ganzen Auftrag schon (``_all_objects``) und gab ihn nicht weiter.

    Gerufen wird ``_ExportWorker._assembly`` selbst, ohne Faden und ohne
    Fenster; die Gegenprobe am Ende: Ist der Klotz der ganze Auftrag, gilt der
    Vorschlag weiter jedem Teil (B2)."""
    from types import SimpleNamespace

    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject
    from app.ui import main_window
    from app.ui.settings import UiSettings

    stem = trimesh.creation.box(extents=(10.0, 10.0, 20.0))
    stem.apply_translation((0.0, 0.0, 10.0))
    cap = trimesh.creation.box(extents=(40.0, 40.0, 3.0))
    cap.apply_translation((0.0, 0.0, 21.5))
    mushroom = SceneObject(
        id="obj_1", name="Pilz", mesh=MeshData.of(trimesh.boolean.union([stem, cap])), plate=0
    )
    block = replace(_standing_box("Klotz", (30.0, 30.0, 10.0)), plate=1)
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.with_accepted(
        print_settings.resolve(profile, "standard"), "support.style", "auto"
    )
    setup = handover.SlicerSetup(tmp_path / "elegoo-slicer.exe", "orca")
    monkeypatch.setattr(main_window, "remembered_setup", lambda *args: setup)

    def export(job: tuple[Any, ...]) -> tuple[set[str], set[str]]:
        folder = tmp_path / f"auftrag_{len(job)}"
        folder.mkdir()
        worker = SimpleNamespace(
            _objects=[block],
            _all_objects=job,
            _target=folder / "Klotz.3mf",
            _profile=profile,
            _sources={},
            _settings=settings,
            _ui_settings=UiSettings(),
            _material=profile.material.id,
            _scene=None,
            _document=None,
            _checked=None,
            cancelled=None,
            _begin_write=lambda: None,
        )
        (written,), findings = main_window._ExportWorker._assembly(worker)  # type: ignore[arg-type]
        return _supported_parts(written, "orca"), {entry.code for entry in findings}

    supported, codes = export((mushroom, block))
    assert supported == set(), "der Pilz verlangt die Stützen, nicht der Klotz"
    assert "export.part_setting_all" not in codes

    supported, codes = export((block,))
    assert len(supported) == 1, "B2: allein ist der Klotz der ganze Auftrag"
    assert "export.part_setting_all" in codes


@pytest.mark.parametrize(
    ("kind", "active"),
    [
        ("none", set()),
        ("skirt", {"adhesion.skirt_loops", "adhesion.skirt_distance"}),
        ("brim", {"adhesion.brim_width", "adhesion.brim_gap"}),
        ("auto", {"adhesion.brim_width", "adhesion.brim_gap"}),
        ("raft", {"adhesion.raft_layers"}),
    ],
)
def test_only_the_measures_of_the_chosen_bed_type_are_active(kind: str, active: set[str]) -> None:
    """Bei *Brim* standen Skirt- und Raft-Maße im Dialog und sperrten mit einem
    Grenzwert das Slicen, obwohl die Übergabe sie nullt (RM-341). Eine Stelle
    sagt jetzt für Sichtbarkeit, Sperre und Suche, was wirkt."""
    from app.core.knowledge import print_settings

    inactive = print_settings.inactive_paths("auto", kind)

    assert set(print_settings.ADHESION_DETAILS) - inactive == active
    assert not inactive & set(print_settings.SUPPORT_DETAILS), "Stützen sind an"
    assert set(print_settings.SUPPORT_DETAILS) <= print_settings.inactive_paths("none", kind)


@pytest.mark.parametrize(
    ("material_id", "flavour", "effective_kind", "active"),
    [
        ("pla", "orca", "auto", {"adhesion.brim_width", "adhesion.brim_gap"}),
        ("petg", "orca", "auto", {"adhesion.brim_width", "adhesion.brim_gap"}),
        ("pla", "prusa", "skirt", {"adhesion.skirt_loops", "adhesion.skirt_distance"}),
        ("petg", "prusa", "skirt", {"adhesion.skirt_loops", "adhesion.skirt_distance"}),
        ("pla", "cura", "skirt", {"adhesion.skirt_loops", "adhesion.skirt_distance"}),
        ("petg", "cura", "skirt", {"adhesion.skirt_loops", "adhesion.skirt_distance"}),
        ("pla", "other", "auto", {"adhesion.brim_width", "adhesion.brim_gap"}),
    ],
)
def test_auto_adhesion_uses_the_slicer_effective_type_for_active_measures(
    material_id: str,
    flavour: slicer_keys.SlicerFlavour,
    effective_kind: str,
    active: set[str],
) -> None:
    """RM-341: Auto-Brim und Materialrückfall zeigen nur wirksame Maße."""
    profile = profiles.make_profile("centauri-carbon-2", material_id)
    automatic = print_settings.with_path(print_settings.resolve(profile), "adhesion.kind", "auto")

    effective = handover.effective_adhesion(automatic, profile, flavour)
    inactive = print_settings.inactive_paths("auto", effective.adhesion.kind)

    assert effective.adhesion.kind == effective_kind
    assert set(print_settings.ADHESION_DETAILS) - inactive == active


@pytest.mark.parametrize(("flavour", "key"), [("prusa", "skirts"), ("cura", "skirt_line_count")])
def test_auto_adhesion_preserves_an_explicit_zero_measure(
    flavour: slicer_keys.SlicerFlavour, key: str
) -> None:
    """RM-341: Ein ausdrücklich gewählter Nullwert gilt auch bei Auto-Rückfall."""
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    automatic = print_settings.with_path(print_settings.resolve(profile), "adhesion.kind", "auto")
    chosen = print_settings.with_choice(automatic, "adhesion.skirt_loops", 0)

    effective = handover.effective_adhesion(chosen, profile, flavour)
    values = handover.values_for(chosen, profile, flavour)

    assert effective.adhesion.kind == "skirt"
    assert effective.adhesion.skirt_loops == 0
    assert values[key] == "0"


def _preflight_box(size: tuple[float, float, float], x: float = 0.0) -> MeshData:
    raw = trimesh.creation.box(extents=size)
    raw.apply_translation((x, 0.0, size[2] / 2.0))
    return MeshData.of(raw)


def _preflight_models(folder: Path, meshes: list[MeshData], transport: str) -> list[Path]:
    if transport == "3mf":
        model = folder / "model.3mf"
        model.write_bytes(threemf.write_assembly([threemf.AssemblyPart(mesh) for mesh in meshes]))
        return [model]
    paths = []
    for index, mesh in enumerate(meshes):
        path = folder / f"body_{index}.stl"
        path.write_bytes(trimesh.exchange.stl.export_stl(mesh.raw))
        paths.append(path)
    if transport == "cura":
        model = folder / "model.stl"
        model.write_bytes(
            trimesh.exchange.stl.export_stl(trimesh.util.concatenate([mesh.raw for mesh in meshes]))
        )
        blocker = folder / "support_blocker.stl"
        blocker.write_bytes(
            trimesh.exchange.stl.export_stl(_preflight_box((400.0, 400.0, 10.0)).raw)
        )
        # Ein riesiger Hilfskörper ist kein Druckteil und darf die Platte
        # nicht sperren. Die normale Netzliste bleibt vollständig beteiligt.
        handover.write_cura_meshes(
            model,
            [
                *(handover.CuraMesh(path) for path in paths),
                handover.CuraMesh(blocker, {"anti_overhang_mesh": "true"}),
            ],
        )
        return [model]
    return paths


@pytest.fixture
def preflight_probe(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    for variable in (
        "APPDATA",
        "LOCALAPPDATA",
        "XDG_DATA_HOME",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
    ):
        monkeypatch.setenv(variable, str(tmp_path / "user-data"))
    monkeypatch.setattr(activation, "require", lambda *_args, **_kwargs: None)
    profile = profiles.make_profile("prusa-mini", "pla")
    calls: list[list[str]] = []

    def crashed(
        command: list[str], *_args: object, **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        calls.append(list(command))
        return subprocess.CompletedProcess(command, 0xC0000409, b"", b"")

    monkeypatch.setattr(handover, "_run_slicer", crashed)

    def run(
        meshes: list[MeshData], transport: str, chosen: Profile | None = None
    ) -> tuple[list[list[str]], AppError]:
        current_profile = chosen or profile
        models = _preflight_models(tmp_path, meshes, transport)
        snapshot = tuple(meshes) if transport == "snapshot" else None
        if snapshot is not None:

            def unexpected_read(*_args: object, **_kwargs: object) -> None:
                pytest.fail("Der vorbereitete Netzsatz darf nicht aus Dateien ersetzt werden")

            monkeypatch.setattr(handover, "_meshes_from_files", unexpected_read)
        executable = tmp_path / ("CuraEngine.exe" if transport == "cura" else "SuperSlicer.exe")
        executable.write_bytes(b"")
        setup = handover.SlicerSetup(
            executable=executable, flavour="cura" if transport == "cura" else "prusa"
        )
        before = [mesh.raw.vertices.copy() for mesh in meshes]
        with pytest.raises(AppError) as raised:
            handover.slice_model(
                models,
                print_settings.resolve(current_profile),
                current_profile,
                setup,
                output_dir=tmp_path / "output",
                model_height=max(float(mesh.bounds.size[2]) for mesh in meshes),
                model_meshes=snapshot,
            )
        assert all(
            (old == mesh.raw.vertices).all() for old, mesh in zip(before, meshes, strict=True)
        ), "Vorprüfung verändert kein Eingabenetz"
        return calls, raised.value

    return run


@pytest.mark.parametrize("transport", ["stl", "3mf", "cura", "snapshot"])
@pytest.mark.parametrize("case", ["square", "height", "two_plates"])
def test_known_build_volume_problem_stops_before_the_slicer(
    preflight_probe: Any, transport: str, case: str
) -> None:
    if case == "square":
        meshes = [_preflight_box((231.0, 231.0, 10.0))]
    elif case == "height":
        meshes = [_preflight_box((20.0, 20.0, 181.0))]
    else:
        # Jedes 100-mm-Teil passt einzeln. Der bestehende Packweg braucht
        # dafür zwei Platten; das behauptet keine globale Packoptimalität.
        meshes = [_preflight_box((100.0, 100.0, 10.0)), _preflight_box((100.0, 100.0, 10.0))]
        printer = profiles.make_profile("prusa-mini", "pla").printer
        assert all(size_excess(mesh, printer) <= 0.0 for mesh in meshes)

    calls, problem = preflight_probe(meshes, transport)

    assert len(calls) == 0, (
        f"Bekannter Bauraumgrund muss vor dem Slicerstart anhalten; Starts={len(calls)}, "
        f"Meldung={problem}"
    )
    actions = {action.id for action in problem.suggestions}
    text = str(problem.detail).casefold()
    assert "abgestürzt" not in text
    assert "check_profile" not in actions
    if case == "two_plates":
        assert not isinstance(problem, OutOfBuildVolume), (
            "Einzelteile sind nicht übergroß; der Packweg benötigt mehr Platten"
        )
        assert "arrange_on_bed" in actions
        assert "platt" in text
        assert not any(
            word in text for word in ("unmöglich", "in keiner drehung", "zu groß", "größer als")
        )
    else:
        assert {"split_model", "scale_to_fit", "choose_printer"} <= actions


@pytest.mark.parametrize("transport", ["stl", "3mf", "cura", "snapshot"])
@pytest.mark.parametrize("case", ["shifted_cube", "diagonal_rod"])
def test_a_part_that_can_be_placed_or_turned_is_allowed_to_start(
    preflight_probe: Any, transport: str, case: str
) -> None:
    mesh = (
        _preflight_box((40.0, 40.0, 10.0), x=300.0)
        if case == "shifted_cube"
        else _preflight_box((200.0, 20.0, 10.0))
    )
    printer = profiles.make_profile("prusa-mini", "pla").printer
    assert size_excess(mesh, printer) <= 0.0

    calls, problem = preflight_probe([mesh], transport)

    assert len(calls) == 1, "Versatz oder eine passende Z-Drehung darf den Start nicht verhindern"
    assert isinstance(problem, ExternalToolError)
    assert "abgestürzt" in str(problem.detail), (
        "Die gestartete Attrappe meldet weiterhin ihren unbekannten Absturzgrund"
    )
    assert "choose_slicer" in {action.id for action in problem.suggestions}


@pytest.mark.parametrize("transport", ["stl", "snapshot"])
@pytest.mark.parametrize("case", ["half_degree", "half_turn_on_triangle"])
def test_preflight_does_not_turn_a_sampled_size_into_a_false_proof(
    preflight_probe: Any, transport: str, case: str
) -> None:
    """Ein passender gedrehter Zeuge widerlegt die heuristische Größenabsage."""
    import math

    import numpy as np

    from app.core.build_area import fits_on_bed

    profile = profiles.make_profile("prusa-mini", "pla")
    if case == "half_degree":
        witness = _preflight_box((179.0, 169.0, 10.0))
        raw = witness.raw.copy()
        raw.apply_transform(
            trimesh.transformations.rotation_matrix(math.radians(0.5), (0.0, 0.0, 1.0))
        )
    else:
        profile = replace(
            profile,
            printer=replace(
                profile.printer,
                printable_area=((-90.0, -90.0), (90.0, -90.0), (-90.0, 90.0)),
            ),
        )
        xy = ((-80.0, 80.0), (80.0, -80.0), (80.0, 80.0))
        raw = trimesh.convex.convex_hull(np.array([(x, y, z) for z in (0.0, 10.0) for x, y in xy]))
        turned = raw.copy()
        turned.apply_transform(trimesh.transformations.rotation_matrix(math.pi, (0.0, 0.0, 1.0)))
        witness = MeshData.of(turned)
    mesh = MeshData.of(raw)
    assert fits_on_bed(witness, profile.printer)
    assert size_excess(mesh, profile.printer) > 0.0

    calls, problem = preflight_probe([mesh], transport, profile)

    assert len(calls) == 1, "Eine passende Z-Drehung darf nicht als unmöglich abgewiesen werden"
    assert "abgestürzt" in str(problem.detail)


@pytest.mark.parametrize("disabled", ["0", "false"])
def test_preflight_ignores_disabled_3mf_build_instances(
    preflight_probe: Any, monkeypatch: pytest.MonkeyPatch, disabled: str
) -> None:
    """Der Import behält ausgeschaltete Teile, der Druckauftrag berücksichtigt sie nicht."""
    from io import BytesIO

    from app.core.ingest.threemf import read_objects

    original = _preflight_models

    def write_with_disabled_part(
        folder: Path, meshes: list[MeshData], transport: str
    ) -> list[Path]:
        paths = original(folder, meshes, transport)
        with zipfile.ZipFile(paths[0]) as archive:
            entries = {name: archive.read(name) for name in archive.namelist()}
        document = ET.fromstring(entries["3D/3dmodel.model"])
        document.findall("{*}build/{*}item")[-1].set("printable", disabled)
        entries["3D/3dmodel.model"] = ET.tostring(document)
        output = BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            for name, payload in entries.items():
                archive.writestr(name, payload)
        paths[0].write_bytes(output.getvalue())
        assert len(read_objects(output.getvalue())) == 2, "Der normale Import bleibt vollständig"
        return paths

    monkeypatch.setitem(globals(), "_preflight_models", write_with_disabled_part)
    calls, problem = preflight_probe(
        [_preflight_box((20.0, 20.0, 20.0)), _preflight_box((400.0, 400.0, 10.0))], "3mf"
    )

    assert len(calls) == 1, "Eine ausgeschaltete Instanz darf die druckbare Platte nicht sperren"
    assert "abgestürzt" in str(problem.detail)


@pytest.mark.parametrize("flavour", ["cura", "prusa", "orca"])
@pytest.mark.parametrize("explicit", [False, True])
@pytest.mark.parametrize("ending", ["success", "cancel", "replace_denied"])
def test_existing_output_and_sources_survive_the_return_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    flavour: str,
    explicit: bool,
    ending: str,
) -> None:
    """Erfolg, Abbruch und Schreibfehler erhalten Quellen und ersetzen nur ein fertiges Ergebnis."""
    from app.core.errors import FileWriteError, OperationCancelled
    from app.core.scene.cancel import CancelSignal

    payload = "G90\nM83\nG0 X10 Y10 Z0.2\nG1 X20 E1 F600\n"
    for variable in (
        "APPDATA",
        "LOCALAPPDATA",
        "XDG_DATA_HOME",
        "XDG_CONFIG_HOME",
        "XDG_CACHE_HOME",
    ):
        monkeypatch.setenv(variable, str(tmp_path / "user-data"))
    monkeypatch.setattr(activation, "require", lambda *_args, **_kwargs: None)
    source = tmp_path / "Bayrak Direği 打印.stl"
    source_bytes = (MESHES / "cube_clean.stl").read_bytes()
    source.write_bytes(source_bytes)
    executable = tmp_path / f"{flavour}.exe"
    executable.touch()
    directory = tmp_path / "Ausgabe 打印" if explicit else None
    native_name = "plate_1.gcode" if flavour == "orca" else handover.OUTPUT_NAME
    target = directory / native_name if directory else source.with_suffix(".gcode")
    target.parent.mkdir(exist_ok=True)
    target.write_bytes(b"existing print")
    captured: list[Path] = []
    token = CancelSignal()
    original_temporary = handover.tempfile.NamedTemporaryFile
    original_replace = Path.replace

    def run(command: list[str], workspace: Path, *_args: Any, **_kwargs: Any) -> Any:
        captured.append(workspace)
        assert target.read_bytes() == b"existing print"
        if flavour == "cura":
            output = Path(command[command.index("-o") + 1])
        elif flavour == "prusa":
            output = Path(command[command.index("--output") + 1])
        else:
            output = Path(command[command.index("--outputdir") + 1]) / native_name
        assert output.parent == workspace
        assert output != target
        output.write_text(payload, encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, b"", b"")

    def temporary(*args: Any, **kwargs: Any) -> Any:
        result = original_temporary(*args, **kwargs)
        if kwargs.get("dir") == target.parent and kwargs.get("prefix") == f".{target.name}.":
            assert target.read_bytes() == b"existing print"
            if ending == "cancel":
                token.cancel()
        return result

    def replace(path: Path, destination: Any) -> Path:
        if ending == "replace_denied" and Path(destination) == target:
            raise PermissionError("final replace denied")
        return original_replace(path, destination)

    monkeypatch.setattr(handover, "_run_slicer", run)
    monkeypatch.setattr(handover.tempfile, "NamedTemporaryFile", temporary)
    monkeypatch.setattr(Path, "replace", replace)
    profile = profiles.make_profile()

    def slice_once() -> handover.SliceOutcome:
        return handover.slice_model(
            source,
            print_settings.resolve(profile),
            profile,
            handover.SlicerSetup(executable, flavour),
            output_dir=directory,
            cancelled=token,
        )

    if ending == "success":
        result = slice_once()
        assert result.gcode_path == target
        assert target.read_text(encoding="utf-8") == payload
    elif ending == "cancel":
        with pytest.raises(OperationCancelled):
            slice_once()
        assert target.read_bytes() == b"existing print"
    else:
        with pytest.raises(FileWriteError) as caught:
            slice_once()
        assert caught.value.suggestions
        assert target.read_bytes() == b"existing print"
    assert source.read_bytes() == source_bytes
    assert len(captured) == 1
    assert not captured[0].exists()
    assert not list(target.parent.glob(f".{target.name}.*.tmp"))
