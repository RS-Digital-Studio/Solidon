"""Lagerzuweisung und Buchungsangebote sind an tatsächliche Ausgaben angeschlossen."""

from dataclasses import replace
from types import SimpleNamespace

import pytest
import trimesh

from app.core.errors import FileWriteError, OperationCancelled
from app.core.export import handover
from app.core.filament_usage import with_spool
from app.core.geom.mesh import MeshData
from app.core.knowledge import filaments, print_settings, profiles
from app.core.slice.gcode import GcodeMetrics
from app.core.types import MaterialSlot, SceneObject
from app.ui import main_window
from app.ui import print_settings_dialog as printing
from app.ui.filament_picker import spool_slot
from app.ui.settings import UiSettings


def body(identifier: str = "body", plate: int = 0) -> SceneObject:
    return SceneObject(
        id=identifier,
        name=identifier,
        plate=plate,
        mesh=MeshData.of(trimesh.creation.box(extents=(20, 20, 20))),
        material_slots=[MaterialSlot(0, "PLA Rot", (1.0, 0.0, 0.0), None, "PLA")],
    )


@pytest.fixture
def inventory(tmp_path, monkeypatch):
    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    return filaments.save(
        filaments.CatalogueFilament(
            "PLA Rot",
            "#ff0000",
            "PLA",
            remaining_grams=100.0,
            spool_grams=1000.0,
        )
    )


@pytest.mark.parametrize("success", [True, False])
@pytest.mark.parametrize("format_name", ["3mf", "stl"])
def test_export_offers_only_successful_3mf(qt_app, tmp_path, monkeypatch, success, format_name):
    profile = profiles.make_profile()
    worker = main_window._ExportWorker(
        [body()],
        tmp_path / f"model.{format_name}",
        format_name,
        profile=profile,
        sources={},
        settings=None,
        ui_settings=UiSettings(),
        material=profile.material.id,
        inventory_settings=print_settings.resolve(profile),
        project_name="Probe",
    )

    def write():
        if not success:
            raise FileWriteError("model", detail="locked")
        return [tmp_path / "model"], []

    monkeypatch.setattr(worker, "_assembly", write)
    monkeypatch.setattr(worker, "_files", write)
    offered = []
    worker.usageReady.connect(offered.append)
    worker.work()
    assert len(offered) == int(success and format_name == "3mf")
    if offered:
        assert offered[0].project_name == "Probe"


@pytest.mark.parametrize("mode", ["open", "slice"])
@pytest.mark.parametrize("failure", ["none", "cancel", "second"])
def test_plate_outputs_offer_only_completed_plates(qt_app, tmp_path, monkeypatch, mode, failure):
    profile = profiles.make_profile()
    objects = (body("first", 0), body("second", 1))
    job = printing._PlateJob(
        objects,
        (0, 1),
        tmp_path,
        "Projekt",
        handover.SlicerSetup(tmp_path / "orca-slicer.exe", "orca"),
        print_settings.resolve(profile),
        profile,
        {},
    )
    monkeypatch.setattr(
        printing,
        "_prepare_plate",
        lambda _job, plate: printing.PlateRun(
            plate,
            tmp_path / f"{plate}.3mf",
            tuple(objects[plate].material_slots),
        ),
    )

    def output(path, *_args, **_kwargs):
        target = path[0] if isinstance(path, list) else path
        if failure == "cancel" or (failure == "second" and target.stem == "1"):
            if mode == "slice":
                raise OperationCancelled()
            raise FileWriteError(str(target), detail="locked")
        return handover.SliceOutcome(target, GcodeMetrics(filament_grams_by_tool=(42.0,)))

    monkeypatch.setattr(handover, "open_in_slicer", output)
    monkeypatch.setattr(handover, "slice_model", output)
    worker = (
        printing._OpenInSlicerWorker(job)
        if mode == "open"
        else printing._PrepareAndSliceWorker(job)
    )
    offered = []
    worker.usageReady.connect(offered.append)
    worker.work()
    assert [one.plate for one in offered] == {"none": [0, 1], "cancel": [], "second": [0]}[failure]
    if mode == "slice" and offered:
        assert offered[0].lines[0].grams == pytest.approx(42.0)


def test_stock_warning_has_no_stock_side_effect(qt_app, inventory):
    profile = profiles.make_profile()
    settings = with_spool(
        print_settings.resolve(profile), spool_slot(inventory), inventory.identifier
    )
    filaments.set_remaining(inventory.identifier, 0.5)
    worker = printing._StockWorker([body()], settings, profile)
    notes = []
    worker.done.connect(notes.append)
    worker.work()
    assert "0,5 g" in notes[0]
    assert filaments.get(inventory.identifier).remaining_grams == pytest.approx(0.5)
    assert not filaments.bookings()


def test_first_inventory_binding_keeps_the_selected_print_quality(qt_app):
    """Eine erstmals angelegte Lagerkennung bewahrt die bisher wirksame Feinheit."""
    from app.ui.session import Session

    session = Session()
    harness = SimpleNamespace(session=session, settings=UiSettings(print_quality="fine"))
    harness.effective_print_settings = lambda: main_window.MainWindow.effective_print_settings(
        harness
    )
    configured = main_window.MainWindow._inventory_settings(harness)
    assert configured.inventory_project_id
    assert configured.quality == "fine"
    assert configured.layers == print_settings.resolve(session.profile, "fine").layers
    assert session.project.document.print_settings == configured


def test_inventory_navigation_preserves_open_project(qt_app, inventory):
    from app.ui.session import Session

    window = main_window.MainWindow(Session(), UiSettings())
    document = window.session.project.document
    before = window.stack.currentWidget()
    window.start_screen.inventoryRequested.emit()
    assert window.stack.currentWidget() is window._inventory_view
    assert window.session.project.document is document
    window._inventory_view.backRequested.emit()
    assert window.stack.currentWidget() is before
    assert window.session.project.document is document


def test_quick_assignment_is_one_transaction_and_keeps_the_spool(qt_app, inventory, monkeypatch):
    from app.core.scene.history import OperationDraft
    from app.ui.session import Session

    session = Session()
    assert session.apply("Körper", [OperationDraft("create_box", params={})])
    session.evaluate_now()
    selected = tuple(session.last_result.scene.objects)
    harness = SimpleNamespace(
        session=session,
        settings=UiSettings(),
        announce=lambda _text: None,
        object_tree=SimpleNamespace(
            selected_objects=lambda: selected, selected_features=lambda: ()
        ),
    )
    harness._inventory_settings = lambda: main_window.MainWindow._inventory_settings(harness)
    harness.effective_print_settings = lambda: main_window.MainWindow.effective_print_settings(
        harness
    )
    harness._spool_change = lambda entry: main_window.MainWindow._spool_change(harness, entry)
    harness._current_inventory_spool = lambda entry: (
        main_window.MainWindow._current_inventory_spool(harness, entry)
    )
    main_window.MainWindow._assign_inventory_spool(harness, inventory)
    result = session.evaluate_now()
    assert len(session.project.document.transactions[-1].ops) == 1
    assert all(
        one.material_slots[0].name == inventory.name for one in result.scene.objects.values()
    )
    assert (
        session.project.document.print_settings.spool_bindings[0].spool_identifier
        == inventory.identifier
    )
    assert filaments.get(inventory.identifier).remaining_grams == pytest.approx(100.0)
    second = filaments.save(replace(inventory, identifier="", revision=0))
    main_window.MainWindow._assign_inventory_spool(harness, second)
    session.undo()
    assert (
        session.project.document.print_settings.spool_bindings[0].spool_identifier
        == inventory.identifier
    )
    session.undo()
    result = session.evaluate_now()
    assert all(not one.material_slots for one in result.scene.objects.values())
    assert not session.project.document.print_settings.spool_bindings


def test_quick_removal_clears_mixed_scope_in_one_undo(qt_app, inventory):
    """Ein ganzer Körper und eine Fläche verlieren ihr Filament gemeinsam, der Rest bleibt."""
    from app.core.scene.history import OperationDraft
    from app.ui.session import Session

    session = Session()
    assert session.apply("Körper", [OperationDraft("create_box"), OperationDraft("create_box")])
    result = session.evaluate_now()
    selected = tuple(result.scene.objects)
    assert len(selected) == 2
    assert session.apply(
        "Filament",
        [
            OperationDraft(
                "assign_slot",
                inputs=(identifier,),
                params={
                    "slot": 0,
                    "name": inventory.name,
                    "colour": inventory.colour,
                    "material_type": inventory.material_type,
                },
            )
            for identifier in selected
        ],
    )
    result = session.evaluate_now()
    whole, partial = selected
    second = result.scene.objects[partial]
    feature = next(feature for feature in second.features.values() if feature.face_indices)
    before = result.scene
    transaction_count = len(session.project.document.transactions)
    harness = SimpleNamespace(
        session=session,
        announce=lambda text: pytest.fail(text),
        object_tree=SimpleNamespace(
            selected_objects=lambda: selected,
            selected_features=lambda: ((partial, feature.id),),
        ),
    )
    main_window.MainWindow._clear_selected_filament(harness)
    result = session.evaluate_now()
    assert len(session.project.document.transactions) == transaction_count + 1
    assert len(session.project.document.transactions[-1].ops) == 2
    assert not result.scene.objects[whole].material_slots
    second = result.scene.objects[partial]
    declared = {slot.index: slot for slot in second.material_slots}
    for index, slot in enumerate(second.mesh.slots):
        if index in feature.face_indices:
            assert slot not in declared
        else:
            assert declared[slot].name == inventory.name
    assert filaments.get(inventory.identifier).remaining_grams == pytest.approx(100)
    session.undo()
    restored = session.evaluate_now().scene
    assert all(
        restored.objects[key].material_slots == before.objects[key].material_slots
        for key in selected
    )
    assert all(
        restored.objects[key].mesh.slots == before.objects[key].mesh.slots for key in selected
    )


def test_quick_removal_rejects_invalid_face_before_applying_any_body(qt_app):
    """Ein veraltetes Merkmal lässt auch den gleichzeitig gewählten ganzen Körper stehen."""
    first, second = body("whole"), body("partial")
    calls, notices = [], []
    harness = SimpleNamespace(
        session=SimpleNamespace(
            last_result=SimpleNamespace(
                scene=SimpleNamespace(objects={"whole": first, "partial": second})
            ),
            apply=lambda *args, **kwargs: calls.append((args, kwargs)),
        ),
        announce=notices.append,
        object_tree=SimpleNamespace(
            selected_objects=lambda: ("whole", "partial"),
            selected_features=lambda: (("partial", "missing"),),
        ),
    )
    main_window.MainWindow._clear_selected_filament(harness)
    assert not calls
    assert notices


def test_quick_removal_groups_faces_before_resolving_the_eight_slot_limit(qt_app, profile):
    """Zwei gemeinsam abgewählte Nullflächen benötigen keinen neunten Filamentplatz."""
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import Feature, OpContext, Scene

    mesh = MeshData.of(trimesh.creation.box(), slots=(0, 0, 1, 2, 3, 4, 5, 6, 7, 1, 2, 3))
    original = SceneObject(
        id="part",
        name="Teil",
        mesh=mesh,
        material_slots=[MaterialSlot(index, f"Spule {index}") for index in range(8)],
        features={
            name: Feature(name, "face", "generated", {}, face_indices=(index,))
            for index, name in enumerate(("first", "second"))
        },
    )
    calls = []
    harness = SimpleNamespace(
        session=SimpleNamespace(
            last_result=SimpleNamespace(scene=Scene(objects={original.id: original})),
            apply=lambda title, drafts: calls.append(drafts),
        ),
        announce=lambda message: pytest.fail(message),
        object_tree=SimpleNamespace(
            selected_objects=lambda: (original.id,),
            selected_features=lambda: ((original.id, "first"), (original.id, "second")),
        ),
    )
    main_window.MainWindow._clear_selected_filament(harness)
    assert len(calls) == len(calls[0]) == 1
    draft = calls[0][0]
    assert draft.params["at_features"] == ["first", "second"]
    spec = REGISTRY.get(draft.op)
    output = spec.fn(
        OpContext(
            scene=Scene(objects={original.id: original}),
            inputs=[original],
            params=spec.params(**draft.params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda *_args: None,
            ask=lambda _question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    ).outputs[0]
    assert output.mesh.slots[:2] == (0, 0)
    assert output.mesh.slots[2:] == original.mesh.slots[2:]
    assert all(slot.index != 0 for slot in output.material_slots)


@pytest.mark.parametrize("change", ["fields", "archive", "rename", "stock"])
def test_dialog_confirmation_rechecks_the_selected_spool(qt_app, inventory, monkeypatch, change):
    """Zwischen Spulenwahl und Anwenden bleiben Werte und physische Bindung deckungsgleich."""
    from app.core.registry import REGISTRY
    from app.core.scene.history import OperationDraft
    from app.ui.filament_picker import _ID_ROLE, FilamentField
    from app.ui.session import Session

    session = Session()
    window = main_window.MainWindow(session, UiSettings())
    assert session.apply("Körper", [OperationDraft("create_box")])
    assert session.wait_for_idle()
    result = session.evaluate_now()
    window.object_tree.select_object(next(iter(result.scene.objects)))
    dialogs = []
    monkeypatch.setattr(
        window, "_open_operation_dialog", lambda dialog, run: dialogs.append((dialog, run))
    )
    window.run_operation(REGISTRY.get("assign_slot"), on_bodies=list(result.scene.objects))
    dialog, run = dialogs[0]
    field = dialog.findChild(FilamentField)
    row = field.findData(inventory.identifier, _ID_ROLE)
    field.setCurrentIndex(row)
    field._chosen(row)
    if change == "fields":
        dialog._editors["name"].setText("Eigener Projektname")
    elif change == "archive":
        filaments.archive(inventory.identifier)
    elif change == "rename":
        filaments.save(replace(inventory, name="Jetzt PETG", material_type="PETG"))
    else:
        filaments.set_remaining(inventory.identifier, 80)
    count = len(session.project.document.ops)
    run()
    assert session.wait_for_idle()
    document = session.project.document
    if change in {"archive", "rename"}:
        assert len(document.ops) == count
    else:
        assert len(document.ops) == count + 1
        bindings = document.print_settings.spool_bindings if document.print_settings else ()
        if change == "fields":
            assert not bindings
        else:
            assert bindings[0].spool_identifier == inventory.identifier
    dialog.close()
    monkeypatch.setattr(window, "_may_discard", lambda: True)
    window.close()


@pytest.mark.parametrize("bound", [False, True])
def test_selected_export_keeps_the_selected_filaments_project_profile(
    qt_app, tmp_path, monkeypatch, bound
):
    """Die zweite Projektspule wird beim Export allein nicht zur ersten Profilwahl."""
    import json
    import zipfile

    from app.core.filament_usage import prepare

    first, selected = body("first"), body("selected")
    first.material_slots = [MaterialSlot(0, "PETG Rot", (1.0, 0.0, 0.0), None, "PETG")]
    selected.material_slots = [MaterialSlot(0, "PETG Blau", (0.0, 0.0, 1.0), None, "PETG")]
    profile = profiles.make_profile()
    settings = replace(
        print_settings.resolve(profile),
        slot_profiles=("PETG Standard", "PETG Schnell"),
        inventory_project_id="selected-profile-test",
    )
    if bound:
        from app.core.export import threemf

        slots = threemf.merge_slots(
            [
                threemf.AssemblyPart(entry.mesh, slots=tuple(entry.material_slots))
                for entry in (first, selected)
            ]
        )
        settings = handover.bind_slot_profiles(settings, slots)
    monkeypatch.setattr(main_window, "remembered_setup", lambda *_args: None)
    profile_files = {}
    for name, speed in (("PETG Standard", "5"), ("PETG Schnell", "21")):
        path = tmp_path / f"{name}.json"
        path.write_text(
            json.dumps(
                {"name": name, "filament_type": ["PETG"], "filament_max_volumetric_speed": [speed]}
            ),
            encoding="utf-8",
        )
        profile_files[name] = path
    monkeypatch.setattr(handover, "profile_file", lambda name, *_args: profile_files.get(name))
    worker = main_window._ExportWorker(
        [selected],
        tmp_path / "selected.3mf",
        "3mf",
        profile=profile,
        sources={},
        settings=settings,
        ui_settings=UiSettings(),
        material=profile.material.id,
        inventory_settings=settings,
        project_name="Probe",
        all_objects=(first, selected),
    )
    offered = []
    worker.usageReady.connect(offered.append)
    worker.work()
    with zipfile.ZipFile(tmp_path / "selected.3mf") as archive:
        written = json.loads(archive.read("Metadata/project_settings.config"))
    assert written["filament_max_volumetric_speed"] == ["21"]
    assert offered[0].lines[0].slot.material == "PETG Schnell"
    expected = prepare(
        [selected], replace(settings, slot_profiles=("PETG Schnell",)), profile, "Probe"
    )[0]
    assert offered[0].fingerprint == expected.fingerprint
    assert first.material_slots[0].material_type == "PETG"


def test_clearing_a_face_keeps_profiles_with_their_filaments_and_undo(qt_app, monkeypatch):
    """Ein neutraler Platz darf die übrigen Herstellerprofile weder tauschen noch erben."""
    from app.core.export import threemf
    from app.core.scene.history import OperationDraft
    from app.ui.session import Session

    session = Session()
    assert session.apply("Körper", [OperationDraft("create_box")])
    assert session.wait_for_idle()
    original = next(iter(session.evaluate_now().scene.objects.values()))
    first_face, second_face = [
        feature.id for feature in original.features.values() if feature.face_indices
    ][:2]
    assert session.apply(
        "Filamente",
        [
            OperationDraft(
                "assign_slot",
                (original.id,),
                {"slot": 0, "name": "Rot", "material_type": "PETG", "colour": "#ff0000"},
            ),
            OperationDraft(
                "paint_slot",
                (original.id,),
                {
                    "slot": 1,
                    "name": "Blau",
                    "material_type": "PETG",
                    "colour": "#0000ff",
                    "at_feature": first_face,
                },
            ),
        ],
    )
    assert session.wait_for_idle()
    session.evaluate_now()
    session.set_print_settings(
        replace(
            print_settings.resolve(session.profile), slot_profiles=("Rot Standard", "Blau Schnell")
        )
    )
    before = session.project.document.print_settings.slot_profile_bindings
    assert before is not None
    assert session.apply(
        "Filament entfernen",
        [OperationDraft("clear_filament", (original.id,), {"at_feature": second_face})],
    )
    assert session.wait_for_idle()

    def assigned():
        result = session.evaluate_now()
        slots = threemf.merge_slots(
            [
                threemf.AssemblyPart(entry.mesh, slots=tuple(entry.material_slots))
                for entry in result.scene.objects.values()
            ]
        )
        return {
            str(slot.name): slot.material
            for slot in handover.configured_slots(slots, session.project.document.print_settings)
        }

    values = assigned()
    assert values["Rot"] == "Rot Standard"
    assert values["Blau"] == "Blau Schnell"
    assert sum(value is None for value in values.values()) == 1
    session.undo()
    assert session.wait_for_idle()
    assert assigned() == {"Rot": "Rot Standard", "Blau": "Blau Schnell"}
    assert session.project.document.print_settings.slot_profile_bindings == before
