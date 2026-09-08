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
        SimpleNamespace(),
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
    harness._spool_change = lambda entry: main_window.MainWindow._spool_change(harness, entry)
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
