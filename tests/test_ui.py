"""Die Oberfläche: Sitzung, Hauptfenster und Merkmalsauswahl (§2.5, §10).

Läuft auf der Offscreen-Qt-Plattform, funktioniert also ohne Bildschirm.
Geprüft wird hier die Verdrahtung, keine Pixel: baut sich das Fenster aus dem
Register, geht eine Änderung durch den Stapel, bleibt die Auswertung im
Arbeiter. Schema-Dialoge, Export, Lizenzierung und Fernsteuerung liegen in
den fachlichen ``test_ui_*.py``-Modulen; ihre Fenster-Fixtures in ``ui_helpers``.
"""

from __future__ import annotations

import dataclasses
import logging
import re
import threading
import time
from pathlib import Path
from typing import Any, cast

import pytest
from PySide6 import QtWidgets
from PySide6.QtCore import QEvent, QLocale, QPoint, Qt
from PySide6.QtGui import QAction, QCloseEvent, QContextMenuEvent, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QToolBar,
    QWidget,
)

from app.core import errors
from app.core.export import handover
from app.core.geom.measure import Measurement
from app.core.registry import REGISTRY, catalogue_operations
from app.core.scene import OperationDraft
from app.core.scene.project import load
from app.core.types import (
    Feature,
    Finding,
    MaterialSlot,
    Parameter,
    Profile,
    SceneObject,
    SlotOverride,
)
from app.i18n import tr
from app.ui import main_window as main_window_module
from app.ui.leash import Worker
from app.ui.main_window import MainWindow
from app.ui.op_dialog import OperationDialog
from app.ui.palette import DIFF_PALETTES
from app.ui.session import AskRequest, Session
from app.ui.settings import UiSettings
from tests.helpers import (
    SOURCE,
    clean_recipe_globals,
    recipe_document_seed,
    recipe_with_halter,
    two_bores,
)
from tests.ui_helpers import MESHES, wait_for_export, wait_until
from tests.ui_helpers import expire_trial as _expired
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window


@pytest.mark.parametrize("command", ["start_sketch", "start_sculpt", "start_armature"])
def test_gesture_editor_entry_keeps_an_unaccepted_measure_draft(command: str) -> None:
    """Auch die direkten Toolbar-Einstiege erhalten den begonnenen Maßentwurf."""
    from types import SimpleNamespace

    notices: list[str] = []
    host = SimpleNamespace(begun=True, committing=False, values={"diameter": 7.0})
    view = SimpleNamespace(_quiet_host=host, announce=notices.append)
    view._quiet_selection_allowed = lambda: MainWindow._quiet_selection_allowed(view)
    view._say_the_change_comes_first = lambda: MainWindow._say_the_change_comes_first(view)
    view._quiet_command_allowed = lambda: MainWindow._quiet_command_allowed(view)

    arguments = ("",) if command == "start_sketch" else ()
    getattr(MainWindow, command)(view, *arguments)

    assert view._quiet_host is host
    assert host.values == {"diameter": 7.0}
    assert notices == [tr("Die aktuelle Änderung zuerst übernehmen oder abbrechen.")]


@pytest.mark.parametrize("before", ["held", "other"])
def test_the_held_sentence_goes_with_the_draft(before: str) -> None:
    """„… zuerst übernehmen oder abbrechen" gilt, solange ein Entwurf hält.

    Am Wabenhalter stand der Satz nach Escape weiter in der Statuszeile — zu
    einer Änderung, die es nicht mehr gab (Durchsicht 0.5.1, rest-auswahl).
    Eine andere Ansage bleibt stehen: Das Ende des Entwurfs räumt nur seinen
    eigenen Satz ab.
    """
    from types import SimpleNamespace

    held = tr("Die aktuelle Änderung zuerst übernehmen oder abbrechen.")
    cleared: list[bool] = []
    view = SimpleNamespace(
        _ending_quiet_placement=False,
        _preview_approval=None,
        _quiet_placement=None,
        _quiet_host=None,
        _quiet_target=None,
        _quiet_order=None,
        _announcement=held if before == "held" else "Gespeichert.",
        feature_panel=SimpleNamespace(measuring=False),
        viewport=SimpleNamespace(set_feature_gizmo_blocked=lambda _blocked: None),
        _drop_feature_preview=lambda: None,
        _clear_the_status_line=lambda: cleared.append(True),
    )
    MainWindow.end_quiet_placement(view)  # type: ignore[arg-type]
    assert cleared == ([True] if before == "held" else [])


def test_the_repair_buttons_ask_for_exactly_what_they_say() -> None:
    """Die Knöpfe der Reparaturbefunde, ohne Fenster: je Knopf genau sein Schalter.

    *Kleine Teile entfernen* verschmilzt nichts, seit „Überschneidungen
    auflösen" in der Vorgabe an steht; *Überschneidungen auflösen* ändert einen
    vorhandenen Reparaturschritt statt einen zweiten anzulegen (§15.4), und
    ohne ihn legt es einen an (Durchsicht 24.09.2026).
    """
    from types import SimpleNamespace

    from app.core.bootstrap import load_operations
    from app.core.types import Operation

    load_operations()
    applied: list[tuple[OperationDraft, ...]] = []
    changed: list[tuple[int, dict[str, object]]] = []
    step: list[Operation | None] = [None]
    view = SimpleNamespace(
        _object_of=lambda _error: "obj_1",
        _step_of=lambda _error: step[0],
        session=SimpleNamespace(
            apply=lambda _title, drafts: applied.append(tuple(drafts)),
            change_params=lambda op_id, params: changed.append((op_id, dict(params))),
        ),
    )

    MainWindow._remove_small_parts(view, object())
    assert applied[-1][0].params == {"small_components": True, "self_intersections": False}

    MainWindow._resolve_intersections_after_error(view, object())
    assert applied[-1][0].op == "repair"
    assert applied[-1][0].params == {"self_intersections": True}

    step[0] = Operation(
        id=2, op="repair", inputs=("obj_1",), outputs=("obj_1",), params={"fill_holes": True}
    )
    MainWindow._resolve_intersections_after_error(view, object())
    assert changed == [(2, {"fill_holes": True, "self_intersections": True})]
    assert len(applied) == 2, "kein zweiter Reparaturschritt"


def test_repairing_before_a_step_retries_that_step() -> None:
    """RM-246: *Erst reparieren, dann neu rechnen* setzt die Reparatur vor den Schritt.

    Derselbe Zug wie am angehaltenen Schritt (``History.repair_and_retry``);
    ein Befund ohne Schritt hat nichts, wovor repariert werden könnte.
    """
    from types import SimpleNamespace

    retried: list[int] = []
    view = SimpleNamespace(session=SimpleNamespace(repair_and_retry=retried.append))

    MainWindow._repair_before_step(view, errors.AppError(title="gerundet", op_id=7))
    MainWindow._repair_before_step(view, errors.AppError(title="gerundet"))

    assert retried == [7]


@pytest.mark.parametrize("command", ["action_undo", "action_redo"])
@pytest.mark.parametrize("begun", [False, True])
def test_document_history_waits_only_for_a_begun_measure_draft(command: str, begun: bool) -> None:
    """Passive Maße erlauben Undo; ein offener Entwurf behält seine Bezugsgeometrie."""
    from types import SimpleNamespace

    calls: list[str] = []
    view = SimpleNamespace(
        _quiet_host=SimpleNamespace(begun=begun, committing=False),
        restore_discarded_sketch=lambda: False,
        undo_sculpt_stroke=lambda: False,
        undo_bone=lambda: False,
        session=SimpleNamespace(
            undo=lambda: calls.append("undo"), redo=lambda: calls.append("redo")
        ),
    )
    view._quiet_selection_allowed = lambda: MainWindow._quiet_selection_allowed(view)
    view._say_the_change_comes_first = lambda: calls.append("finish-draft")
    view._quiet_command_allowed = lambda: MainWindow._quiet_command_allowed(view)

    getattr(MainWindow, command)(view)

    assert calls == (["finish-draft"] if begun else [command.removeprefix("action_")])


def test_split_apply_cannot_replace_an_unaccepted_measure_draft() -> None:
    """Auch eine vorher gezeichnete Trennlinie bleibt hinter der Entwurfssperre."""
    from types import SimpleNamespace

    calls: list[str] = []
    view = SimpleNamespace(
        _quiet_host=SimpleNamespace(begun=True, committing=False),
        _split_points=[(0.0, 0.0, 0.0), (10.0, 10.0, 0.0)],
        _split_target="obj_1",
        _split_plane=object(),
    )
    view._quiet_selection_allowed = lambda: MainWindow._quiet_selection_allowed(view)
    view._say_the_change_comes_first = lambda: calls.append("finish-draft")
    view._quiet_command_allowed = lambda: MainWindow._quiet_command_allowed(view)

    MainWindow._apply_split_line(view)

    assert calls == ["finish-draft"]
    assert view._split_points == [(0.0, 0.0, 0.0), (10.0, 10.0, 0.0)]
    assert view._split_target == "obj_1"


@pytest.mark.parametrize("active", [None, "split", "measure", "transform"])
def test_editing_feature_fields_releases_only_the_split_pointer(active: str | None) -> None:
    """Eine Feldänderung übernimmt den Zeiger; andere Ansichtswerkzeuge bleiben offen."""
    from types import SimpleNamespace

    closed: list[str] = []
    view = SimpleNamespace(
        _quiet_placement=None,
        _quiet_host=None,
        _preview_approval=None,
        _end_changed_quiet_placement=lambda: None,
        _prepare_feature_order=lambda op, params: None,
        _follow_chamfer_sides=lambda op, params: None,
        _offer_feature_cancel=lambda: None,
        tools=SimpleNamespace(active=lambda: active, close_tool=lambda: closed.append("split")),
    )

    MainWindow._on_feature_values_changed(view, "resize_hole", {"diameter": 7.0})

    assert closed == (["split"] if active == "split" else [])
    assert view._feature_pending == ("resize_hole", {"diameter": 7.0})


def _answers_stand_in(monkeypatch: pytest.MonkeyPatch, *, known: bool) -> Any:
    """Ein Hauptfenster aus Stellvertretern für den Merkmalsweg mit großem Körper (RM-232)."""
    from types import SimpleNamespace

    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import placement as placement_module

    monkeypatch.setattr(main_window_module, "ANSWERS_IN_WORKER_FROM", 12)
    monkeypatch.setattr(main_window_module, "texture_steps_of", lambda *_a, **_k: ((), False))
    monkeypatch.setattr(placement_module, "bore_step_of", lambda *_a, **_k: None)
    feature = Feature(id="hole_1", kind="hole", provenance="detected", params={"diameter": 5.0})
    entry = SimpleNamespace(
        id="obj_1",
        features={"hole_1": feature},
        mesh=MeshData.of(trimesh.creation.box((10.0, 10.0, 10.0))),
    )
    result = SimpleNamespace(
        completed=(), scene=SimpleNamespace(objects={"obj_1": entry, "obj_2": object()})
    )
    calls: list[tuple[str, Any]] = []
    view = SimpleNamespace(
        calls=calls,
        entry=entry,
        result=result,
        session=SimpleNamespace(
            last_result=result,
            project=SimpleNamespace(document=object()),
            protected_features=lambda _object: (),
        ),
        feature_panel=SimpleNamespace(
            known_answers=lambda *_a: "gemerkt" if known else None,
            show_feature=lambda feature_id, *_a, **_k: calls.append(("show", feature_id)),
            remember_answers=lambda feature_id, *_a: calls.append(("remember", feature_id)),
            request_in_view=lambda: calls.append(("in_view", None)),
            clear=lambda: calls.append(("clear", None)),
        ),
        feature_dock=SimpleNamespace(reveal=lambda: None),
        object_tree=SimpleNamespace(selected=lambda: "obj_1", selected_feature=lambda: "hole_1"),
        part_step_of=lambda _feature: None,
        _answer_in_worker=lambda feature_id, *_a: calls.append(("worker", feature_id)),
        _op_dialog=None,
        _quiet_placement=None,
        _start_feature_preview=lambda: None,
        _parameter_values=dict,
        _on_error=lambda error: calls.append(("error", error)),
        _lay_out_now=lambda: calls.append(("layout", None)),
    )
    view._show_feature_fields = lambda feature_id, entry, result, **kwargs: calls.append(
        ("fields", kwargs.get("allow_worker", True))
    )
    return view


@pytest.mark.parametrize("known", [False, True])
def test_a_large_body_asks_its_feature_answers_in_the_worker_unless_they_are_known(
    known: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der erste Klick an einer Bohrung eines großen Körpers rechnet nicht im Hauptfaden (RM-232).

    Hohlraumkette, Handlungen und gleichartige Geschwister kosteten an der
    dichten Platte (204 000 Dreiecke) 130 ms im Hauptfaden. Kennt das
    Merkmalfenster die Antwort, baut es sofort; sonst holt sie der Arbeiter,
    und bis dahin wird nichts angeboten.
    """
    view = _answers_stand_in(monkeypatch, known=known)

    MainWindow._show_feature_fields(view, "hole_1", view.entry, view.result)

    if known:
        assert view.calls == [("show", "hole_1"), ("in_view", None), ("layout", None)]
    else:
        assert view.calls == [("worker", "hole_1"), ("layout", None)], "kein Aufbau davor"


def test_without_the_worker_the_feature_fields_build_directly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der zweite Aufbau nach der Antwort geht nicht noch einmal in den Arbeiter."""
    view = _answers_stand_in(monkeypatch, known=False)

    MainWindow._show_feature_fields(view, "hole_1", view.entry, view.result, allow_worker=False)

    assert view.calls == [("show", "hole_1"), ("in_view", None), ("layout", None)]


@pytest.mark.parametrize("case", ["current", "superseded", "elsewhere", "stale"])
def test_the_arriving_answer_is_kept_and_built_only_where_it_still_belongs(
    case: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Antwort des Arbeiters gilt ihrem Merkmal, gebaut wird nur, was noch gewählt ist.

    Auch ein abgelöster Arbeiter liefert eine richtige Antwort, solange die
    Auswertung dieselbe ist — der nächste Klick auf sein Merkmal braucht sie.
    Eine neue Auswertung dagegen hat andere Merkmale, und dann gilt nichts.
    """
    from types import SimpleNamespace

    view = _answers_stand_in(monkeypatch, known=False)
    worker, other = object(), object()
    view._answers_worker = other if case == "superseded" else worker
    if case == "elsewhere":
        view.object_tree = SimpleNamespace(
            selected=lambda: "obj_1", selected_feature=lambda: "hole_2"
        )
    if case == "stale":
        view.session.last_result = object()

    MainWindow._answers_arrived(view, ("obj_1", "hole_1", view.result), worker, "antwort")

    expected = {
        "current": [("remember", "hole_1"), ("fields", False)],
        "superseded": [("remember", "hole_1")],
        "elsewhere": [("remember", "hole_1")],
        "stale": [],
    }
    assert view.calls == expected[case]


@pytest.mark.parametrize("current", [True, False])
def test_a_crashed_answer_worker_reports_instead_of_waiting(
    current: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Programmfehler im Arbeiter ist einer: Bericht, kein ewiger Wartezustand."""
    view = _answers_stand_in(monkeypatch, known=False)
    worker = object()
    view._answers_worker = worker if current else object()

    MainWindow._answers_failed(view, worker, "Traceback …")

    if current:
        assert [name for name, _value in view.calls] == ["clear", "error"]
        assert isinstance(view.calls[1][1], errors.InternalError)
    else:
        assert view.calls == [], "ein abgelöster Arbeiter meldet nichts"


@pytest.mark.parametrize("active", [None, "split", "measure", "transform"])
def test_first_measure_edit_releases_split_but_passive_measures_do_not(
    active: str | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die echte Host-Verdrahtung gibt den Zeiger erst bei der ersten Eingabe weiter."""
    from types import SimpleNamespace

    from app.core.bootstrap import load_operations
    from app.ui import placement_flow

    load_operations()
    closed: list[str] = []
    measuring: list[dict[str, Any]] = []
    order: list[str] = []

    class View:
        """Schwache Referenz ohne ein Fenster für die tatsächliche Anschlussmethode."""

    view: Any = View()
    view.tools = SimpleNamespace(active=lambda: active, close_tool=lambda: closed.append("split"))
    view._quiet_command_allowed = lambda: True
    view._quiet_placement = None
    view._drop_feature_preview = lambda: None
    view.end_quiet_placement = lambda **_kwargs: None
    view._measuring_to_release = False
    view._release_measuring = lambda: MainWindow._release_measuring(view)
    view._place_measures = lambda *args, **kwargs: MainWindow._place_measures(view, *args, **kwargs)
    view.object_tree = SimpleNamespace(selected=lambda: "obj_1", selected_feature=lambda: "hole")
    action = SimpleNamespace(fixed={}, fields=[])
    view.feature_panel = SimpleNamespace(
        measure_fields=lambda *args, **kwargs: (action, object(), {}),
        measure_group=lambda op: None,
        set_measuring=lambda enabled, **kwargs: (measuring.append(kwargs), order.append("messen")),
        bind_measure_group=lambda group, release: None,
        keep_measure_group=lambda group: False,
    )
    view._lay_out_now = lambda: order.append("legen")
    view.session = SimpleNamespace(
        last_result=None, project=SimpleNamespace(document=object()), result_current=False
    )
    view.viewport = SimpleNamespace(set_feature_gizmo_blocked=lambda *args, **kwargs: None)
    monkeypatch.setattr(
        placement_flow,
        "PlacementFlow",
        lambda *args, **kwargs: SimpleNamespace(
            active=True,
            set_measure_fields=lambda *args, **kwargs: None,
            start=lambda: order.append("start"),
        ),
    )

    MainWindow._place_from_feature_panel(view, "resize_hole", {"at_feature": "hole"})
    assert closed == []
    assert measuring[-1]["begun"] is False
    # **Erst umstellen, dann starten** (RM-232): Der Start blendet Felder über
    # der Grafikfläche ein, und das malt sofort — samt Merkmalfenster.
    assert order == ["messen", "legen", "start"]

    view._quiet_host.begin_edit()

    assert closed == (["split"] if active == "split" else [])
    assert measuring[-1]["begun"] is True


@pytest.mark.parametrize("handled_by", ["sketch", "sculpt", "bone"])
def test_editor_undo_keeps_priority_over_document_history(handled_by: str) -> None:
    """Das eigene Gesten-Undo bleibt vor der Sperre für fremde Dokumentbefehle."""
    from types import SimpleNamespace

    calls: list[str] = []

    def undo(kind: str) -> bool:
        calls.append(kind)
        return handled_by == kind

    view = SimpleNamespace(
        restore_discarded_sketch=lambda: undo("sketch"),
        undo_sculpt_stroke=lambda: undo("sculpt"),
        undo_bone=lambda: undo("bone"),
    )
    MainWindow.action_undo(view)
    assert (
        calls == ["sketch", "sculpt", "bone"][: ["sketch", "sculpt", "bone"].index(handled_by) + 1]
    )


def test_a_blocked_sketch_restore_keeps_the_discarded_drawing() -> None:
    """Undo verliert keine aufgehobene Zeichnung, wenn ein Maßentwurf den Einstieg hält."""
    from types import SimpleNamespace

    calls: list[str] = []
    drawing = object()
    view = SimpleNamespace(
        _quiet_host=SimpleNamespace(begun=True, committing=False),
        _discarded_sketch=drawing,
    )
    view._quiet_selection_allowed = lambda: MainWindow._quiet_selection_allowed(view)
    view._say_the_change_comes_first = lambda: calls.append("finish-draft")
    view._quiet_command_allowed = lambda: MainWindow._quiet_command_allowed(view)

    assert MainWindow.restore_discarded_sketch(view)
    assert view._discarded_sketch is drawing
    assert calls == ["finish-draft"]


def _accept_after_preview(window: MainWindow, dialog: OperationDialog) -> None:
    """Übernehmen, sobald die Vorschau dargestellt ist — so wie der Kunde.

    Seit dem 20.09.2026 wartet Übernehmen auf die aktuelle **dargestellte**
    Vorschau: Ein Klick, bevor sie steht, tut nichts, und der Knopf ist bis
    dahin grau. Ein Test, der direkt nach dem Tippen ``accept()`` ruft,
    schließt den Dialog deshalb nicht mehr.
    """
    from time import monotonic, sleep

    assert window.session.wait_for_idle(30_000)
    deadline = monotonic() + 30
    while monotonic() < deadline:
        QApplication.processEvents()
        if dialog._accept_button.isEnabled() and dialog.can_accept():
            break
        sleep(0.01)
    assert dialog._accept_button.isEnabled(), "die Vorschau ist dargestellt, Übernehmen frei"
    dialog.accept()
    assert window._op_dialog is not dialog, "der Dialog hat übernommen und ist zu"


def _release_unstarted_worker(owner: object, field: str, worker: Worker) -> None:
    """Eine vom Test bewusst nicht gestartete QThread-Attrappe abbauen."""
    if getattr(owner, field, None) is worker:
        setattr(owner, field, None)
    worker.release_finished_references()
    worker.deleteLater()
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_legacy_paint_finding_opens_its_real_values_and_history(window, monkeypatch):
    """Die alte Farbdatei führt über die sichtbaren Befundknöpfe bis zu ihren erhaltenen Werten."""
    from PySide6.QtWidgets import QPushButton

    from app.ui.dialogs import StepValuesDialog

    window.session.open_project(Path(__file__).parent / "data" / "projects" / "painted_v13.p3d")
    assert window.session.wait_for_idle(30000)
    result = window.session.last_result
    assert result is not None and result.stopped_at == 2
    window._on_scene(result)
    listing = window.report.list
    row = next(
        index
        for index in range(listing.count())
        if listing.item(index).data(Qt.ItemDataRole.UserRole).code == "evaluate.legacy_point_paint"
    )
    listing.setCurrentRow(row)
    opened, visited = [], []

    def read_values(dialog):
        assert dialog.text.isReadOnly()
        opened.append(dialog.text.toPlainText())
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(StepValuesDialog, "exec", read_values)
    monkeypatch.setattr(window, "_flash_area", visited.append)
    buttons = {button.text(): button for button in window.report._offers.findChildren(QPushButton)}
    buttons["Werte ansehen"].click()
    assert len(opened) == 1
    assert "radius" in opened[0] and "12.0" in opened[0]
    assert all(name in opened[0] for name in ("x", "y", "z", "slot"))
    buttons["Verlauf zeigen"].click()
    assert visited == ["history"]
    assert window.session.project.document.ops[1].params["radius"] == pytest.approx(12.0)


def test_rebuilding_the_object_tree_preserves_click_order(window: MainWindow) -> None:
    """Einheiten- und Szenenwechsel vertauschen keine Booleschen Operanden."""
    assert window.session.apply(
        "Zwei Körper",
        [OperationDraft(op="create_box"), OperationDraft(op="create_box")],
    )
    assert window.session.wait_for_idle(30000)
    tree = window.object_tree
    tree.tree.clearSelection()
    tree.tree.topLevelItem(1).setSelected(True)
    tree.tree.topLevelItem(0).setSelected(True)
    assert tree.selected_objects() == ("obj_2", "obj_1")
    tree.set_unit("in")
    assert tree.selected_objects() == ("obj_2", "obj_1")
    tree.show_scene(window.session.last_result, window.session.project.document)
    assert tree.selected_objects() == ("obj_2", "obj_1")


def test_derived_parameter_labels_follow_the_evaluated_expression(window: MainWindow) -> None:
    """Die Anzeige folgt dem neu gerechneten Maß, nicht seinem Erfassungswert."""
    from PySide6.QtWidgets import QLabel

    from app.core.geom.mesh import as_mesh_data

    session = window.session
    assert session.add_parameter(Parameter(name="base", value=20.0))
    assert session.wait_for_idle(30000)
    assert session.add_parameter(Parameter(name="derived", value=10.0, expression="@base / 2"))
    assert session.wait_for_idle(30000)
    assert session.apply("Quader", [OperationDraft(op="create_box", params={"height": "@derived"})])
    assert session.wait_for_idle(30000)
    assert session.change_parameter("base", 40.0)
    assert session.wait_for_idle(30000)
    result = session.last_result
    assert result is not None and result.complete
    assert as_mesh_data(result.scene.objects["obj_1"].mesh).bounds.size[2] == pytest.approx(20.0)
    labels = [
        label.text()
        for label in window.parameters.findChildren(QLabel)
        if label.toolTip() == "@base / 2"
    ]
    assert labels == ["20,00"]


def test_unused_parameters_become_bound_only_after_a_step_reads_them(window: MainWindow) -> None:
    """Die Leiste benennt wirkungslose Maße und erneuert die Auskunft nach Undo/Redo."""
    from PySide6.QtWidgets import QLabel

    session = window.session
    assert session.add_parameter(Parameter(name="width", value=30.0))
    assert session.wait_for_idle()

    def labels() -> list[QLabel]:
        return [
            label
            for label in window.parameters.findChildren(QLabel)
            if label.text().startswith("width")
        ]

    assert len(labels()) == 1
    assert "Nicht verwendet" in labels()[0].text()
    assert "=@width" in labels()[0].accessibleDescription()
    assert session.apply("Quader", [OperationDraft(op="create_box", params={"width": "=@width"})])
    assert session.wait_for_idle()
    assert labels()[0].text() == "width"
    assert "Operation 1" in labels()[0].toolTip() and "Breite" in labels()[0].toolTip()
    session.undo()
    assert session.wait_for_idle()
    assert "Nicht verwendet" in labels()[0].text()
    session.redo()
    assert session.wait_for_idle()
    assert labels()[0].text() == "width"


@pytest.mark.parametrize(
    "change,fail", [("selection", False), ("project", False), ("project", True), ("cancel", False)]
)
def test_a_delayed_image_source_keeps_its_project_and_target(
    window: MainWindow,
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
    fail: bool,
) -> None:
    """Echte späte Dateiergebnisse verändern nur ihren ursprünglichen Kontext."""
    from PySide6.QtGui import QImage

    session = window.session
    assert session.apply(
        "Zwei Körper", [OperationDraft(op="create_box"), OperationDraft(op="create_box")]
    )
    assert session.wait_for_idle(30000)
    filename = tmp_path / "relief.png"
    picture = QImage(5, 5, QImage.Format.Format_RGB32)
    picture.fill(0xFF123456)
    assert picture.save(str(filename))
    entered, proceed = threading.Event(), threading.Event()
    real_work = main_window_module._SourceReadWorker.work

    def held_work(worker: Any) -> None:
        entered.set()
        assert proceed.wait(15)
        real_work(worker)

    monkeypatch.setattr(main_window_module._SourceReadWorker, "work", held_work)
    calls: list[dict[str, Any]] = []
    errors: list[Exception] = []
    monkeypatch.setattr(window, "run_operation", lambda spec, **kwargs: calls.append(kwargs))
    monkeypatch.setattr(main_window_module, "show_error", lambda error, *args: errors.append(error))
    window.object_tree.select_object("obj_1")
    window._drop_image(filename)
    worker = window._source_worker
    try:
        assert worker is not None and entered.wait(5)
        if change == "selection":
            window.object_tree.select_object("obj_2")
        else:
            session.start_new()
            assert session.wait_for_idle(30000)
            own = session._embed_source("generated", "own.bin", b"neues Projekt")
            assert own == "src_1"
        if fail:
            filename.unlink()
        if change == "cancel":
            worker.cancel.cancel()
            announcements = []
            monkeypatch.setattr(window, "announce", announcements.append)
        proceed.set()
        assert worker.wait(15000)
        qt_app.processEvents()
        assert not errors
        if change == "cancel":
            assert not announcements, "der Abbruch des vorigen Projekts meldet hier keinen Zustand"
        if change == "selection":
            assert len(calls) == 1
            assert calls[0].get("on_bodies") == ("obj_1",)
            assert calls[0]["given"]["source"] in session.project.document.sources
        else:
            assert calls == []
            assert list(session.project.document.sources) == ["src_1"]
            assert session.project.sources["src_1"] == b"neues Projekt"
            assert not session.project.document.ops
    finally:
        proceed.set()
        if worker is not None:
            worker.wait(15000)


def test_filaments_leave_the_modal_print_dialog_and_offer_a_way_back(
    window: MainWindow,
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Knopf muss die Filamentkarte tatsächlich bedienbar machen."""
    from PySide6.QtCore import QTimer

    from app.ui.print_settings_dialog import PrintSettingsDialog

    dialog = PrintSettingsDialog(window.session, window.settings, window)
    dialog.filamentsRequested.connect(lambda: window._show_filaments(dialog))
    blocked = []

    def choose_filaments():
        dialog.material_link.click()
        blocked.append(qt_app.activeModalWidget() is dialog)
        if blocked[-1]:
            dialog.reject()

    QTimer.singleShot(0, choose_filaments)
    dialog.exec()
    assert blocked == [False]
    assert not window.filaments.return_to_print_button.isHidden()
    requested = []

    class ReturnedDialog(PrintSettingsDialog):
        def exec(self):
            requested.append(self.settings)
            return QDialog.DialogCode.Rejected

    monkeypatch.setattr(main_window_module, "PrintSettingsDialog", ReturnedDialog)
    monkeypatch.setattr(main_window_module, "ensure_print_disclosure", lambda *args: None)
    window.filaments.return_to_print_button.click()
    assert len(requested) == 1
    assert window.filaments.return_to_print_button.isHidden()
    dialog.deleteLater()


def test_section_controls_follow_the_scene_when_its_worker_finishes(
    window: MainWindow, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Schnittleiste übernimmt neue Grenzen erst mit der tatsächlich gezeigten Szene."""
    from threading import Event

    from app.core.scene import OperationDraft
    from app.ui import viewport as module

    session = window.session
    session.history.apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 400.0, "depth": 200.0, "height": 300.0})],
    )
    result = session.run_evaluation()
    entered, release = Event(), Event()
    original = module._SceneMeshWorker.work

    def held(worker):
        entered.set()
        assert release.wait(10)
        original(worker)

    monkeypatch.setattr(module._SceneMeshWorker, "work", held)
    monkeypatch.setattr(
        window.viewport,
        "_scene_tasks",
        lambda scene: (
            [(key, entry.mesh, None) for key, entry in scene.scene.objects.items()],
            None,
            None,
        ),
    )
    worker = None
    try:
        window._show_scene(result)
        worker = window.viewport._scene_worker
        assert worker is not None and entered.wait(5)
        release.set()
        assert worker.wait(10000)
        qt_app.processEvents()
        assert window.section_bar._ranges == window.viewport.section_ranges()
        assert window.section_bar._ranges["x"] == pytest.approx((-200.0, 200.0))
        assert window.section_bar._ranges["z"] == pytest.approx((0.0, 300.0))
    finally:
        release.set()
        if worker is not None:
            worker.wait(10000)


def test_another_running_session_keeps_its_recovery(qt_app: QApplication) -> None:
    """Ein zweites Fenster darf die Sicherung des ersten weder anbieten noch verwerfen."""
    from app.core.scene.project import autosave_path, discard_recovery, unsaved_recoveries

    first, second = Session(), Session()
    try:
        first._dirty = True
        first.autosave()
        saved = autosave_path(None, first.recovery_token)
        assert saved.is_file()
        assert saved not in unsaved_recoveries(except_token=second.recovery_token)
        discard_recovery(saved)
        assert saved.is_file()
        first.release()
        assert saved in unsaved_recoveries(except_token=second.recovery_token)
        discard_recovery(saved)
        assert not saved.exists()
    finally:
        first.release()
        second.release()


def test_opening_repairs_the_reference_at_the_stopped_operation(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der echte Öffnungs-Worker ordnet den Verweis im vorbereiteten Zwischenstand neu zu."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Feature, Scene, SceneObject

    session.history.apply("Körper", [OperationDraft(op="create_box")])
    session.history.apply(
        "Bohrung",
        [
            OperationDraft(
                op="resize_hole",
                inputs=("obj_1",),
                params={"at_feature": "hole_999", "diameter": 6.0},
            )
        ],
    )
    stopped = session.project.document.ops[-1].id
    scene = Scene(
        objects={
            "obj_1": SceneObject(
                id="obj_1",
                name="Platte",
                mesh=MeshData(trimesh.creation.box()),
                features={
                    "hole_2": Feature(
                        id="hole_2", kind="hole", params={"diameter": 5.0}, provenance="detected"
                    )
                },
            )
        }
    )

    def evaluate(*_args):
        pending = session.project.document.ops[-1].params["at_feature"] == "hole_999"
        return EvaluationResult(
            scene=scene,
            completed=(1,) if pending else (1, stopped),
            stopped_at=stopped if pending else None,
        )

    monkeypatch.setattr(session, "run_evaluation", evaluate)
    path = session.save_project(tmp_path / "verloren.p3d")
    requests = []
    session.askRequested.connect(
        lambda request: (requests.append(request), request.reply("hole_2"))
    )
    try:
        session.open_project(path)
        assert session.wait_for_idle()
        assert requests, "die unvollständige Auswertung muss die Wiederzuordnung erreichen"
        assert requests[0].candidates == (("obj_1", "hole_2"),)
        assert requests[0].preview is not None and requests[0].preview.scene is scene
        assert session.project.document.ops[-1].params["at_feature"] == "hole_2"
        assert session.last_result.complete
        assert session.modified, "die neue Zuordnung muss beim Schließen gespeichert werden"
    finally:
        session.release()


def test_the_question_shows_its_intermediate_scene_before_the_choices(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Rückfrage markiert Kandidaten in genau dem mitgelieferten Zwischenstand."""
    from app.core.scene import EvaluationResult
    from app.core.types import Scene
    from app.ui import main_window as module

    preview = EvaluationResult(scene=Scene(objects={}), stopped_at=2)
    shown = []
    monkeypatch.setattr(window, "_on_scene", lambda result: shown.append(("scene", result)))
    monkeypatch.setattr(
        window.viewport, "show_candidates", lambda *args: shown.append(("candidates", args))
    )

    class Answer(module.AskDialog):
        def exec(self):
            shown.append(("dialog", None))
            return self.DialogCode.Accepted

        def chosen(self):
            return "hole_2"

    monkeypatch.setattr(module, "AskDialog", Answer)
    request = AskRequest(
        "Bohrung zuordnen", ["hole_2"], preview=preview, candidates=(("obj_1", "hole_2"),)
    )
    window._on_ask(request)
    assert shown[0] == ("scene", preview)
    assert [entry[0] for entry in shown].index("candidates") < [entry[0] for entry in shown].index(
        "dialog"
    )
    assert request.answer == "hole_2" and request.answered.is_set()


def test_matching_question_context_reaches_the_worker_request_and_is_cleared(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Auswertungsaufruf überträgt Vorschau und echte IDs, die nächste Frage nicht."""
    from app.core.scene import EvaluationResult
    from app.core.types import Scene
    from app.ui import session as module

    preview = EvaluationResult(scene=Scene(objects={}), stopped_at=2)
    candidates = (("part_a", "face_2"), ("part_b", "face_2"))
    requests: list[AskRequest] = []

    def answer(request: AskRequest) -> None:
        requests.append(request)
        request.reply(request.choices[0])

    def evaluate(_document, _profile, **kwargs):
        context = kwargs["question_context"]
        context(preview, candidates)
        try:
            assert kwargs["ask"]("Welcher Bezug bleibt?", ["face_2"]) == "face_2"
        finally:
            context(None, ())
        assert kwargs["ask"]("Welche Einheit?", ["mm"]) == "mm"
        return preview

    monkeypatch.setattr(module, "evaluate", evaluate)
    session.askRequested.connect(answer, Qt.ConnectionType.DirectConnection)
    worker = module._EvaluationWorker(session)
    session._worker = worker
    try:
        worker.work()
        assert len(requests) == 2
        first, second = requests
        assert first.preview is preview and first.candidates == candidates
        assert first.temporary_preview
        assert first.worker is worker
        assert first.project_generation == session._project_generation
        assert second.preview is None and second.candidates == ()
        assert not second.temporary_preview
        assert session._pending.preview is None and session._pending.worker is None
    finally:
        _release_unstarted_worker(session, "_worker", worker)


def test_an_evaluation_question_keeps_the_project_generation_from_its_creation(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein alter Arbeiter darf beim verspäteten Start keinen neuen Projektstempel erben."""
    from app.ui import session as module

    worker = module._EvaluationWorker(session)
    session._worker = worker
    requests: list[AskRequest] = []
    stopped: list[bool] = []
    session.askRequested.connect(requests.append)
    worker.cancelled.connect(lambda: stopped.append(True))
    monkeypatch.setattr(session, "run_evaluation", lambda: session.ask_from_worker("Alt", ["Ja"]))
    session._project_generation += 1
    try:
        worker.work()
        assert requests == [] and stopped == [True]
        assert session._pending.worker is None
    finally:
        _release_unstarted_worker(session, "_worker", worker)


def test_a_question_closed_without_a_choice_is_declined_not_cancelled(session: Session) -> None:
    """Das Schließen einer Frage sagt der Frage ab, nicht der Rechnung.

    ``QuestionDeclined`` lässt die Auswertung am fragenden Schritt mit einem Befund anhalten
    (RM-024: „Abbruch liefert einen Befund"). Bis zum 23.09.2026 kam hier
    ``OperationCancelled``: Die ganze Rechnung galt als abgebrochen, und weil
    ``_cancel_by_user`` nicht stand, sagte das Fenster nichts. Eine überholte Frage bleibt
    ein gewöhnlicher Abbruch — ihre Antwort gehört zu keinem aktuellen Stand.
    """
    from app.core.errors import OperationCancelled, QuestionDeclined

    def close(request: AskRequest) -> None:
        request.reply(None)

    session.askRequested.connect(close, Qt.ConnectionType.DirectConnection)
    try:
        with pytest.raises(QuestionDeclined):
            session.ask_from_worker("Welches Merkmal entspricht hole_1?", ["hole_2"])
    finally:
        session.askRequested.disconnect(close)

    def outdated(request: AskRequest) -> None:
        session._project_generation += 1
        request.reply(None)

    session.askRequested.connect(outdated, Qt.ConnectionType.DirectConnection)
    try:
        with pytest.raises(OperationCancelled) as stopped:
            session.ask_from_worker("Welches Merkmal entspricht hole_1?", ["hole_2"])
    finally:
        session.askRequested.disconnect(outdated)
    assert not isinstance(stopped.value, QuestionDeclined)


def _matching_question_scenes():
    """Zwei unterscheidbare Ansichten mit tatsächlichen, körpergebundenen Dreiecken."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene

    def result(offset: float, names: tuple[str, str]):
        raw = trimesh.creation.box(extents=(10.0, 8.0, 4.0))
        raw.apply_translation((offset, 0.0, 0.0))
        features = {
            name: Feature(
                id=name,
                kind="face",
                params={"area": 8.0 * 4.0},
                face_indices=indices,
                provenance="detected",
            )
            for name, indices in zip(names, ((0, 2), (10, 11)), strict=True)
        }
        body = SceneObject(id="part", name="Platte", mesh=MeshData(raw), features=features)
        return EvaluationResult(scene=Scene(objects={body.id: body}), stopped_at=2)

    return result(0.0, ("face_old_a", "face_old_b")), result(6.0, ("face_new_a", "face_new_b"))


@pytest.mark.parametrize("gesture", ["button", "enter", "double_click", "accept"])
def test_matching_choices_wait_for_the_actual_scene_and_restore_it_before_reply(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, gesture: str
) -> None:
    """Kein Übernahmeweg entscheidet über unsichtbare Kandidaten oder publiziert die Vorschau."""
    from PySide6.QtTest import QTest

    from app.ui.dialogs import AskDialog

    base, preview = _matching_question_scenes()
    session = window.session
    session.last_result = base
    window._on_scene(base)
    document = session.project.document
    generation, modified = session.result_generation, session.modified
    history_count = len(document.transactions)
    original_show = window.viewport.show_scene
    original_candidates = window.viewport.show_candidates
    seen = []
    finished = []
    candidates = (("part", "face_new_a"), ("part", "face_new_b"))

    def show(result):
        seen.append(("scene", result))
        if result is not preview:
            original_show(result)

    def mark(pairs=(), emphasis=None):
        if pairs:
            assert window.viewport.is_scene_applied(preview)
        seen.append(("candidates", (tuple(pairs), emphasis)))
        original_candidates(pairs, emphasis)

    def choose(dialog):
        if gesture == "button":
            dialog._accept.click()
        elif gesture == "enter":
            QTest.keyClick(dialog, Qt.Key.Key_Return)
        elif gesture == "double_click":
            dialog.list.itemDoubleClicked.emit(dialog.list.currentItem())
        else:
            dialog.accept()

    def interact(dialog):
        dialog.finished.connect(finished.append)
        dialog.show()
        QApplication.processEvents()
        assert not dialog.list.isEnabled() and not dialog._accept.isEnabled()
        buttons = dialog.findChild(QDialogButtonBox)
        assert buttons.button(QDialogButtonBox.StandardButton.Cancel).isEnabled()
        assert not request.answered.is_set()
        choose(dialog)
        assert finished == [], "no acceptance or accidental cancellation before the scene exists"
        original_show(preview)
        assert dialog.list.isEnabled() and dialog._accept.isEnabled()
        dialog.list.setCurrentRow(1)
        assert window._ask_candidates == candidates
        assert seen[-1] == ("candidates", (candidates, candidates[1]))
        choose(dialog)
        assert finished == [QDialog.DialogCode.Accepted]
        return dialog.result()

    class Request(AskRequest):
        def reply(self, answer):
            assert window.viewport.is_scene_applied(base)
            assert window._ask_candidates == ()
            seen.append(("reply", answer))
            super().reply(answer)

    monkeypatch.setattr(window.viewport, "show_scene", show)
    monkeypatch.setattr(window.viewport, "show_candidates", mark)
    monkeypatch.setattr(window, "_on_scene", lambda _result: pytest.fail("temporary final scene"))
    monkeypatch.setattr(AskDialog, "exec", interact)
    request = Request(
        "Welcher Bezug bleibt?",
        ["face_new_a", "face_new_b"],
        preview=preview,
        candidates=candidates,
        temporary_preview=True,
        project_generation=session._project_generation,
    )
    window._on_ask(request)
    assert request.answer == "face_new_b" and request.answered.is_set()
    assert seen[-2:] == [("scene", base), ("reply", "face_new_b")]
    assert session.last_result is base and session.project.document is document
    assert (session.result_generation, session.modified) == (generation, modified)
    assert len(document.transactions) == history_count


@pytest.mark.parametrize("ending", ["cancel", "project", "new_result", "close"])
def test_a_matching_preview_can_end_before_its_scene_is_ready(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, ending: str
) -> None:
    """Abbruch bleibt erreichbar; Projektwechsel und neue Ergebnisse bekommen keine alte Ansicht."""
    from app.core.scene.project import new_project
    from app.ui.dialogs import AskDialog

    base, preview = _matching_question_scenes()
    window.session.last_result = base
    shown, errors = [], []
    monkeypatch.setattr(window.viewport, "show_scene", shown.append)
    monkeypatch.setattr(window.viewport, "is_scene_applied", lambda _scene: False)
    monkeypatch.setattr(window, "_on_error", errors.append)
    request = AskRequest(
        "Welcher Bezug bleibt?",
        ["face_new_a"],
        preview=preview,
        candidates=(("part", "face_new_a"),),
        temporary_preview=True,
        project_generation=window.session._project_generation,
    )

    def interact(dialog):
        if ending == "cancel":
            buttons = dialog.findChild(QDialogButtonBox)
            buttons.button(QDialogButtonBox.StandardButton.Cancel).click()
        elif ending == "project":
            window.session.project = new_project()
            window.session._project_generation += 1
            window.session.projectChanged.emit()
        elif ending == "new_result":
            window.session.last_result = preview
            window.session.result_generation += 1
            window.session.sceneChanged.emit(preview)
        else:
            window._close_requested = True
            window._cancel_pending_question()
            assert request.answered.is_set(), "the closing window must not wait for its own dialog"
        assert not dialog._accept.isEnabled()
        return QDialog.DialogCode.Accepted  # Auch eine verspätete Annahme zählt nicht.

    monkeypatch.setattr(AskDialog, "exec", interact)
    window._on_ask(request)
    assert request.answered.is_set() and request.answer is None
    assert errors == [] and window._ask_candidates == ()
    if ending == "cancel":
        assert shown == [preview, base]
    elif ending in ("project", "close"):
        assert shown == [preview]
    else:
        assert all(result is not base for result in shown)


@pytest.mark.parametrize("stage", ["construction", "prepare", "scene", "dialog", "restore"])
def test_a_matching_preview_error_releases_the_worker_before_reporting_it(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, stage: str
) -> None:
    """Jeder Aufbau- und Rückwegfehler beantwortet die Frage sicher mit Abbruch."""
    from app.ui.dialogs import AskDialog

    base, preview = _matching_question_scenes()
    window.session.last_result = base
    failures = []
    request = AskRequest(
        "Welcher Bezug bleibt?",
        ["face_new_a"],
        preview=preview,
        candidates=(("part", "face_new_a"),),
        temporary_preview=True,
    )

    def report(error):
        assert request.answered.is_set()
        failures.append(error)

    def show(result):
        if (stage == "prepare" and result is preview) or (stage == "restore" and result is base):
            raise RuntimeError("prepared scene error")

    def interact(dialog):
        if stage == "scene":
            window.viewport.sceneFailed.emit("asynchronous scene error")
            return dialog.result()
        if stage == "dialog":
            raise RuntimeError("dialog error")
        return QDialog.DialogCode.Accepted

    def broken_dialog(*_args):
        raise RuntimeError("construction error")

    monkeypatch.setattr(window, "_on_error", report)
    monkeypatch.setattr(window.viewport, "show_scene", show)
    monkeypatch.setattr(window.viewport, "is_scene_applied", lambda _result: True)
    monkeypatch.setattr(AskDialog, "exec", interact)
    if stage == "construction":
        monkeypatch.setattr(main_window_module, "AskDialog", broken_dialog)
    window._on_ask(request)
    assert request.answered.is_set() and request.answer is None
    assert len(failures) == 1 and isinstance(failures[0], errors.InternalError)
    assert window._ask_dialog is None and window._ask_candidates == ()


@pytest.mark.parametrize("stale", ["project", "worker", "cancelled"])
def test_a_queued_stale_question_never_opens_a_dialog(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, stale: str
) -> None:
    """Der Auftrag behält seinen Arbeiter; eine neue Sitzung oder Abbruch entwertet ihn."""
    from app.ui import session as module

    worker = module._EvaluationWorker(window.session)
    window.session._worker = worker
    request = AskRequest(
        "Welcher Bezug bleibt?",
        ["face_new_a"],
        project_generation=window.session._project_generation,
        worker=worker,
    )
    if stale == "project":
        window.session._project_generation += 1
    elif stale == "worker":
        window.session._worker = None
    else:
        window.session.cancel_signal.cancel()
    monkeypatch.setattr(
        main_window_module, "AskDialog", lambda *_args: pytest.fail("stale question dialog")
    )
    try:
        window._on_ask(request)
        assert request.answered.is_set() and request.answer is None
        assert window._ask_dialog is None
    finally:
        window.session.cancel_signal.reset()
        _release_unstarted_worker(window.session, "_worker", worker)


@pytest.mark.parametrize("stop", ["cancel", "replace"])
@pytest.mark.parametrize("phase", ["construction", "scene", "dialog"])
def test_active_matching_questions_end_when_their_evaluation_is_invalidated(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, stop: str, phase: str
) -> None:
    """Abbruch und Nachlauf lösen auch vor dem Event-Warten jede alte Frage vollständig."""
    from app.ui import session as module
    from app.ui.dialogs import AskDialog

    session = window.session
    base, preview = _matching_question_scenes()
    session.last_result = base
    original_show = window.viewport.show_scene
    original_show(base)
    original_init = AskDialog.__init__
    original_ready = AskDialog.set_ready
    shown, requests, stopped, failures, readiness = [], [], [], [], []
    worker = module._EvaluationWorker(session)
    session._worker = worker
    monkeypatch.setattr(worker, "isRunning", lambda: True)
    worker.cancelled.connect(lambda: stopped.append(True))
    remember = requests.append
    session.askRequested.connect(remember, Qt.ConnectionType.DirectConnection)
    monkeypatch.setattr(window, "_on_error", failures.append)

    def invalidate():
        if stop == "cancel":
            session.cancel_evaluation()
        else:
            # Die Änderungsmeldung kommt im echten _changed vor evaluate_async.
            session.projectChanged.emit()
            session.evaluate_async()

    def initialise(dialog, *args, **kwargs):
        original_init(dialog, *args, **kwargs)
        if phase == "construction":
            invalidate()

    def show(result):
        shown.append(result)
        original_show(result)
        if result is preview and phase == "scene":
            invalidate()

    def ready(dialog, value):
        readiness.append(value)
        original_ready(dialog, value)

    def interact(dialog):
        assert phase == "dialog", "a request invalidated before exec must never start its loop"
        assert dialog._accept.isEnabled()
        invalidate()
        assert not dialog._accept.isEnabled()
        assert dialog.result() == QDialog.DialogCode.Rejected
        return dialog.result()

    def evaluate():
        session.announce_question(preview, (("part", "face_new_a"),))
        session.ask_from_worker("Welcher Bezug bleibt?", ["face_new_a"])
        pytest.fail("an invalidated evaluation cannot receive a matching answer")

    monkeypatch.setattr(AskDialog, "__init__", initialise)
    monkeypatch.setattr(AskDialog, "set_ready", ready)
    monkeypatch.setattr(AskDialog, "exec", interact)
    monkeypatch.setattr(window.viewport, "show_scene", show)
    monkeypatch.setattr(session, "run_evaluation", evaluate)
    try:
        # Direkte Zustellung beantwortet die Frage noch vor answered.wait().
        worker.work()
        assert stopped == [True] and failures == []
        assert len(requests) == 1 and requests[0].answered.is_set()
        assert requests[0].answer is None
        assert session.last_result is base and window.viewport.is_scene_applied(base)
        assert shown[-1] is base
        assert window._ask_dialog is None and window._ask_request is None
        assert window._ask_candidates == ()
        assert session._pending.preview is None and session._pending.candidates == ()
        previous_calls = len(readiness)
        session.questionInvalidated.emit()
        assert len(readiness) == previous_calls, "the completed dialog has no live signal binding"
    finally:
        session._rerun_pending = False
        session.cancel_signal.reset()
        session.askRequested.disconnect(remember)
        _release_unstarted_worker(session, "_worker", worker)


def _needs_the_exact_kernel() -> None:
    """Ein Test an einem exakten Körper braucht OpenCASCADE — und sagt es, statt rot zu werden.

    Die CI installiert das Extra ``brep``; ein Quellklon ohne es lief in diesen
    Tests früher in einen Importfehler statt in einen Skip (Review Tests-1 #4).
    """
    from tests.helpers import exact_kernel

    exact_kernel()


# --- session --------------------------------------------------------------------


def test_a_fresh_session_has_an_empty_project(session: Session) -> None:
    assert session.project.document.ops == []
    assert session.path is None
    assert not session.modified


def test_outline_import_waits_for_the_shown_contours(
    window: MainWindow, qt_app: QApplication, tmp_path: Path
) -> None:
    """Auswahl, Vorschau, Übernahme und Rücknahme benutzen dieselben Konturen."""
    from app.ui.outline_dialog import OutlineDialog

    path = tmp_path / "contours.svg"
    path.write_bytes(SOURCE)
    window.open_path(path)
    # Gelesen und geplant wird im Arbeiter (RM-224); die Konturwahl öffnet danach.
    assert window.session.wait_for_idle()
    dialog = window.findChild(OutlineDialog)
    assert dialog is not None
    assert not window.session.history.operations
    wait_until(qt_app, lambda: dialog.accept_button.isEnabled())
    dialog.profiles.item(1).setCheckState(Qt.CheckState.Unchecked)
    wait_until(qt_app, lambda: dialog.accept_button.isEnabled())
    expected = dialog.result_preview
    chosen = dialog.values()
    assert expected is not None and expected.contours == 1
    dialog.accept()
    assert window.session.wait_for_idle()
    operations = window.session.history.operations
    assert len(operations) == 1 and operations[0].op == "load_outline"
    assert operations[0].params["contours"] == chosen["contours"]
    result = window.session.last_result
    assert result is not None and result.stopped_at is None
    body = next(iter(result.scene.objects.values()))
    assert body.mesh.volume == pytest.approx(expected.mesh.volume)
    assert body.mesh.bounds.size == pytest.approx(expected.mesh.bounds.size)
    window.session.undo()
    assert window.session.wait_for_idle()
    assert not window.session.history.operations
    window.session.redo()
    assert window.session.wait_for_idle()
    assert window.session.history.operations[0].params["contours"] == chosen["contours"]


def test_cancelling_outline_import_drops_only_its_pending_source(
    window: MainWindow, qt_app: QApplication, tmp_path: Path
) -> None:
    """Abbrechen hinterlässt weder eine Operation noch eine eingebettete Dateiwaise."""
    from app.ui.outline_dialog import OutlineDialog
    from tests.helpers import SOURCE

    path = tmp_path / "cancel.svg"
    path.write_bytes(SOURCE)
    window.open_path(path)
    # Gelesen und geplant wird im Arbeiter (RM-224); die Konturwahl öffnet danach.
    assert window.session.wait_for_idle()
    dialog = window.findChild(OutlineDialog)
    assert dialog is not None
    assert window.session.project.document.sources
    dialog.reject()
    assert not window.session.history.operations
    assert not window.session.project.document.sources
    assert not window.session.project.sources
    assert not window.session._outline_imports
    assert window._pending_import is None


def test_stale_outline_answer_cannot_apply_to_another_project(session: Session) -> None:
    """Die gleiche Quellenkennung im neuen Projekt gehört nicht zur alten Antwort."""
    from app.core.knowledge.profiles import DEFAULT_MATERIAL, DEFAULT_PRINTER
    from tests.helpers import SOURCE

    session.choose_outline = True
    requests = []
    session.outlineImportRequested.connect(lambda *args: requests.append(args))
    session.import_payload_async("first.svg", SOURCE)
    _plan, source_id, generation = requests[-1]
    session.start_new(DEFAULT_PRINTER, DEFAULT_MATERIAL)
    session.import_payload_async("second.svg", SOURCE)
    source = session.project.document.sources[source_id]
    session.finish_outline_import(source_id, generation, None)
    assert session.project.document.sources[source_id] is source
    assert not session.history.operations
    session.finish_outline_import(requests[-1][1], requests[-1][2], None)


def test_editing_outline_contours_keeps_bound_dimensions(
    window: MainWindow, qt_app: QApplication
) -> None:
    """Der Auswahlknopf im echten Verlaufsdialog erhält die Ausdrücke seiner Maße."""
    from PySide6.QtTest import QTest

    from app.ui.outline_dialog import ContourField, OutlineDialog

    session = window.session
    assert session.add_parameter(Parameter(name="thickness", value=4.0))
    assert session.wait_for_idle()
    assert session.add_parameter(Parameter(name="span", value=80.0))
    assert session.wait_for_idle()
    assert session.import_payload("profile.svg", SOURCE)
    assert session.wait_for_idle()
    step = session.history.operations[-1]
    assert session.change_params(step.id, {"height": "=@thickness", "width": "=@span"})
    assert session.wait_for_idle()
    window.edit_operation(step.id)
    operation_dialog = window._op_dialog
    assert operation_dialog is not None
    field = operation_dialog._editors["contours"]
    assert isinstance(field, ContourField)
    QTest.mouseClick(field.button, Qt.MouseButton.LeftButton)
    picker = operation_dialog.findChild(OutlineDialog)
    assert picker is not None
    wait_until(qt_app, lambda: picker.accept_button.isEnabled())
    assert picker.values()["height"] == pytest.approx(4.0)
    assert picker.values()["width"] == pytest.approx(80.0)
    assert not picker._fields["height"].isEnabled()
    picker.profiles.item(1).setCheckState(Qt.CheckState.Unchecked)
    wait_until(qt_app, lambda: picker.accept_button.isEnabled())
    chosen = picker.values()["contours"]
    picker.accept()
    assert operation_dialog.values()["height"] == "=@thickness"
    assert operation_dialog.values()["width"] == "=@span"
    assert field.value() == chosen
    _accept_after_preview(window, operation_dialog)
    assert session.wait_for_idle()
    updated = session.history.operation(step.id)
    assert updated.params["height"] == "=@thickness"
    assert updated.params["width"] == "=@span"
    assert updated.params["contours"] == chosen


def test_organizer_layout_choice_keeps_bound_dimensions_and_reaches_history(
    window: MainWindow, qt_app: QApplication
) -> None:
    """Der angeschlossene Facheditor verändert das Layout und erhält die Maßbindungen."""
    from PySide6.QtTest import QTest

    from app.core.organizer.ops import OrganizerParams
    from app.core.organizer.serialize import layout_from_text
    from app.ui.organizer_dialog import OrganizerDialog, OrganizerLayoutField

    session = window.session
    assert session.add_parameter(Parameter(name="span", value=180.0))
    assert session.wait_for_idle()
    assert session.add_parameter(Parameter(name="rise", value=100.0))
    assert session.wait_for_idle()
    assert session.apply(
        "Organizer",
        [
            OperationDraft(
                op="create_organizer",
                params={**OrganizerParams().as_dict(), "width": "=@span", "height": "=@rise"},
            )
        ],
    )
    assert session.wait_for_idle()
    step = session.history.operations[-1]
    original_layout = step.params["layout"]
    window.edit_operation(step.id)
    parent = window._op_dialog
    assert parent is not None
    field = parent._editors["layout"]
    assert isinstance(field, OrganizerLayoutField)
    QTest.mouseClick(field.button, Qt.MouseButton.LeftButton)
    picker = parent.findChild(OrganizerDialog)
    assert picker is not None
    wait_until(qt_app, picker.accept_button.isEnabled)
    assert not picker._fields["width"].isEnabled()
    picker.tree.setCurrentItem(picker._tree_items["rows"])
    picker._edit_fields["count"].set_value(2)
    wait_until(qt_app, picker.accept_button.isEnabled)
    chosen = picker.values()["layout"]
    assert layout_from_text(chosen).root.count == 2
    assert len(picker._layout.cells) == 6
    picker.accept()
    assert parent.values()["width"] == "=@span"
    assert parent.values()["height"] == "=@rise"
    assert field.value() == chosen
    _accept_after_preview(window, parent)
    assert session.wait_for_idle()
    updated = session.history.operation(step.id)
    assert updated.params["width"] == "=@span"
    assert updated.params["height"] == "=@rise"
    assert updated.params["layout"] == chosen
    assert session.last_result.complete
    session.undo()
    assert session.wait_for_idle()
    assert session.history.operation(step.id).params["layout"] == original_layout
    session.redo()
    assert session.wait_for_idle()
    assert session.history.operation(step.id).params["layout"] == chosen


@pytest.mark.parametrize("new_project", [False, True])
def test_cancelled_or_stale_organizer_editor_cannot_change_the_document(
    window: MainWindow, qt_app: QApplication, new_project: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Abbrechen und Projektwechsel verwerfen auch bereits berechnete Fachaufteilungen."""
    from PySide6.QtTest import QTest

    from app.core.knowledge.profiles import DEFAULT_MATERIAL, DEFAULT_PRINTER
    from app.core.organizer.ops import OrganizerParams
    from app.ui.organizer_dialog import OrganizerDialog

    errors_seen = []
    monkeypatch.setattr(
        main_window_module, "show_error", lambda error, *a, **k: errors_seen.append(error)
    )
    session = window.session
    assert session.apply(
        "Organizer", [OperationDraft(op="create_organizer", params=OrganizerParams().as_dict())]
    )
    assert session.wait_for_idle()
    project = session.project
    step = session.history.operations[-1]
    layout = step.params["layout"]
    window.edit_operation(step.id)
    parent = window._op_dialog
    assert parent is not None
    QTest.mouseClick(parent._editors["layout"].button, Qt.MouseButton.LeftButton)
    picker = parent.findChild(OrganizerDialog)
    assert picker is not None
    wait_until(qt_app, picker.accept_button.isEnabled)
    picker._edit_fields["count"].set_value(2)
    wait_until(qt_app, picker.accept_button.isEnabled)
    if new_project:
        session.start_new(DEFAULT_PRINTER, DEFAULT_MATERIAL)
        assert session.wait_for_idle()
        assert session.project is not project
        assert not session.history.operations
    else:
        picker.reject()
        assert parent.values()["layout"] == layout
        parent.reject()
        assert session.history.operation(step.id).params["layout"] == layout
    assert project.document.ops[-1].params["layout"] == layout
    assert not errors_seen


def test_importing_a_model_goes_through_the_stack(session: Session) -> None:
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    assert [entry.op for entry in session.project.document.ops] == ["load"]
    assert session.modified
    result = session.evaluate_now()
    assert result.complete
    assert result.scene.objects["obj_1"].mesh.volume == pytest.approx(8000.0)


def test_filament_values_from_the_panel_reach_the_project(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die neue, kurze Bedienkette: Filamentpanel → Dialog → Projektdatei."""
    slot = MaterialSlot(index=1, name="PLA Weiß", colour=(1.0, 1.0, 1.0))
    released: list[MaterialSlot] = []

    class AcceptedFilamentDialog:
        def __init__(self, chosen, settings, _existing, _parent) -> None:
            self.chosen = chosen
            self.temperature = dataclasses.replace(settings.temperature, nozzle=205)

        def exec(self) -> int:
            return int(QDialog.DialogCode.Accepted)

        def override(self) -> SlotOverride:
            return SlotOverride(
                name=self.chosen.name,
                colour=self.chosen.colour,
                temperature=self.temperature,
            )

        def deleteLater(self) -> None:  # noqa: N802 - bildet die Qt-API nach
            released.append(self.chosen)

    monkeypatch.setattr(main_window_module, "FilamentOverrideDialog", AcceptedFilamentDialog)

    window.filaments.overrideRequested.emit(slot)

    settings = window.session.project.document.print_settings
    assert settings is not None
    override = handover.override_for(settings, slot)
    assert override is not None and override.temperature is not None
    assert override.temperature.nozzle == 205
    assert released == [slot], "der geschlossene Dialog bleibt nicht am Hauptfenster hängen"


def test_a_cancelled_filament_dialog_is_released(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch Abbrechen räumt den parent-eigenen Qt-Dialog vollständig ab."""
    slot = MaterialSlot(index=1, name="PLA Weiß", colour=(1.0, 1.0, 1.0))
    released: list[MaterialSlot] = []

    class RejectedFilamentDialog:
        def __init__(self, chosen, _settings, _existing, _parent) -> None:
            self.chosen = chosen

        def exec(self) -> int:
            return int(QDialog.DialogCode.Rejected)

        def deleteLater(self) -> None:  # noqa: N802 - bildet die Qt-API nach
            released.append(self.chosen)

    monkeypatch.setattr(main_window_module, "FilamentOverrideDialog", RejectedFilamentDialog)

    window.filaments.overrideRequested.emit(slot)

    assert released == [slot]
    assert window.session.project.document.print_settings is None


def test_undo_and_redo_reach_the_document(session: Session) -> None:
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    session.undo()
    session.wait_for_idle()
    assert session.project.document.ops == []

    session.redo()
    session.wait_for_idle()
    assert [entry.op for entry in session.project.document.ops] == ["load"]


def test_a_changed_parameter_is_a_transaction(session: Session) -> None:
    """§13 und §15.5: eine gedrehte Zahl ist rücknehmbar und zählt als Änderung.

    Vorher schrieb die Leiste geradewegs ins Dokument. Das kostete beides: ein
    Strg+Z nahm die letzte *Operation* zurück statt der Zahl, und weil das
    Projekt als ungeändert galt, sicherte das Schließen sie nicht.
    """
    document = session.project.document
    document.parameters["width"] = Parameter(name="width", value=84.0, unit="mm")

    session.change_parameter("width", 120.0)
    session.wait_for_idle()

    assert document.parameters["width"].value == 120.0
    assert session.modified, "sonst geht die Änderung beim Schließen verloren"
    assert session.history.can_undo

    session.undo()
    assert document.parameters["width"].value == 84.0

    session.redo()
    assert document.parameters["width"].value == 120.0


def test_a_parameter_change_is_named_as_the_panel_names_it() -> None:
    """Der Verlauf sagt „Parameter Breite“, nicht „Parameter breite“.

    Die Leiste beschriftet ein Maß mit seinem Titel (``parameter.title or
    name``); der Verlauf schrieb den Schlüssel (Handbuchbild *Ein Maß ändern*,
    3). Ohne Fenster: Titel der Transaktion und Kurzhilfe der Zeile.
    """
    from app.core.types import DocumentChange, DocumentState, Origin, Transaction
    from app.i18n import _, set_language
    from app.i18n.catalog import install_language
    from app.ui.panels import _changed_parameters
    from app.ui.session import _parameter_title

    breite = Parameter(name="breite", value=40.0, unit="mm", title=_("Breite"))
    assert str(_parameter_title(breite)) == "Parameter Breite"
    assert str(_parameter_title(Parameter(name="wand", value=2.0))) == "Parameter wand", (
        "ohne Titel bleibt der Name, wie in der Leiste"
    )
    install_language("en")
    set_language("en")
    try:
        assert str(_parameter_title(breite)) == "Parameter Width", "der Eintrag folgt der Sprache"
    finally:
        set_language("de")

    geaendert = Transaction(
        id="t2",
        title=_parameter_title(breite),
        ops=(),
        origin=Origin(by="user"),
        changes=DocumentChange(
            before=DocumentState(parameters={"breite": breite}),
            after=DocumentState(parameters={"breite": dataclasses.replace(breite, value=90.0)}),
        ),
    )
    tip = _changed_parameters(geaendert)
    assert tip.startswith("Breite: ") and "→" in tip, tip
    assert "40" in tip and "90" in tip, tip

    begrenzt = Parameter(
        name="breite", value=40.0, unit="mm", title=_("Breite"), minimum=0.0, maximum=100.0
    )
    grenze_geaendert = Transaction(
        id="t3",
        title=_parameter_title(begrenzt),
        ops=(),
        origin=Origin(by="user"),
        changes=DocumentChange(
            before=DocumentState(parameters={"breite": begrenzt}),
            after=DocumentState(
                parameters={"breite": dataclasses.replace(begrenzt, maximum=150.0)}
            ),
        ),
    )
    grenzhinweis = _changed_parameters(grenze_geaendert)
    assert "Obergrenze" in grenzhinweis and "100" in grenzhinweis and "150" in grenzhinweis
    assert "40" not in grenzhinweis, "der unveränderte Wert wird nicht als Änderung wiederholt"


def test_the_history_row_of_a_parameter_change_carries_its_caption(window: MainWindow) -> None:
    """Am Fenster: Zeile „Parameter Breite“, Kurzhilfe mit dem Wert davor und danach."""
    from app.i18n import _

    session = window.session
    assert session.add_parameter(Parameter(name="breite", value=40.0, unit="mm", title=_("Breite")))
    assert session.change_parameter("breite", 90.0)
    session.wait_for_idle()
    QApplication.processEvents()
    rows = [window.history_panel.list.item(row) for row in range(window.history_panel.list.count())]
    texts = [item.text() for item in rows]
    assert "Parameter Breite" in texts, texts
    assert not any("breite" in text for text in texts), texts
    changed = [item for item in rows if item.text() == "Parameter Breite"][-1]
    assert "→" in changed.toolTip() and "Schritte" not in changed.toolTip(), changed.toolTip()


def test_a_number_over_the_limit_of_a_parameter_is_refused_with_the_limit(
    window: MainWindow,
) -> None:
    """Obergrenze 100, getippt 150: kein stilles 15, sondern die Grenze und ein Weg zu ihr.

    Vorher verfiel die Null beim Tippen, die Eingabetaste übernahm 15, und im
    Modell stand 15 (Durchsicht 0.5.1). Jetzt bleibt der Parameter bei 40,
    unter dem Feld steht die Obergrenze, und *Parameter ändern …* führt dorthin.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QPushButton

    from app.i18n import _

    session = window.session
    assert session.add_parameter(
        Parameter(name="breite", value=40.0, unit="mm", title=_("Breite"), maximum=100.0)
    )
    session.wait_for_idle()
    QApplication.processEvents()
    editor = window.parameters._editors["breite"]
    editor.setFocus()
    editor.lineEdit().selectAll()
    QTest.keyClicks(editor.lineEdit(), "150")
    QTest.keyClick(editor.lineEdit(), Qt.Key.Key_Return)
    for _round in range(3):
        QApplication.processEvents()
    session.wait_for_idle()

    assert session.project.document.parameters["breite"].value == pytest.approx(40.0)
    said = window.parameters.refusal_text()
    assert "150" in said and "100" in said and "mm" in said, said
    assert editor.lineEdit().text() == "150", "die abgelehnte Zahl bleibt stehen"

    asked: list[str] = []
    window.parameters.limitsRequested.disconnect()
    window.parameters.limitsRequested.connect(asked.append)
    change = next(
        button
        for button in window.parameters._refusal.findChildren(QPushButton)
        if button.text() == tr("Parameter ändern …")
    )
    change.click()
    for _round in range(3):
        QApplication.processEvents()
    assert asked == ["breite"], "der Weg zur Grenze öffnet genau dieses Maß"


def test_the_same_value_again_changes_nothing(session: Session) -> None:
    """Eine Spinbox meldet auch, was sie schon anzeigte — daraus wird kein
    Verlaufseintrag."""
    document = session.project.document
    document.parameters["width"] = Parameter(name="width", value=84.0, unit="mm")

    session.change_parameter("width", 84.0)

    assert not session.history.can_undo
    assert not session.modified


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_parameter_is_reported_without_changing_the_document(
    session: Session, value: float
) -> None:
    """Eine ungültige Zahl bleibt im Dialogfehler, nie als Prozessabsturz."""
    document = session.project.document
    document.parameters["width"] = Parameter(name="width", value=84.0, unit="mm")
    errors_seen: list[errors.ValidationError] = []
    session.failed.connect(
        lambda error: (
            errors_seen.append(error) if isinstance(error, errors.ValidationError) else None
        )
    )

    assert not session.change_parameter("width", value)
    assert document.parameters["width"].value == 84.0
    assert not session.history.can_undo
    assert errors_seen and errors_seen[-1].constraint == "not_a_number"


def test_a_parameter_spinbox_can_rebuild_after_its_own_signal(window: MainWindow) -> None:
    """Die linke Parameterleiste darf ihren Sender erst nach dem Signal löschen."""
    document = window.session.project.document
    document.parameters["width"] = Parameter(name="width", value=84.0, unit="mm")
    window.parameters.show_document(document)
    editor = window.parameters._editors["width"]

    editor.setValue(120.0)
    QApplication.processEvents()
    window.session.wait_for_idle()

    assert document.parameters["width"].value == 120.0
    assert "width" in window.parameters._editors, "die Leiste wurde sicher neu aufgebaut"


def test_a_parameter_unit_is_a_safe_choice_in_the_left_panel(window: MainWindow) -> None:
    """Die Einheit ist eine feste, rücknehmbare Auswahl und kein Freitext."""
    from app.core.units import DEGREE_UNIT

    document = window.session.project.document
    document.parameters["angle"] = Parameter(name="angle", value=45.0, unit="mm")
    window.parameters.show_document(document)
    editor = window.parameters._unit_editors["angle"]

    assert not editor.isEditable()
    assert [editor.itemData(index) for index in range(editor.count())] == [
        "mm",
        DEGREE_UNIT,
        "",
    ]

    index = editor.findData(DEGREE_UNIT)
    editor.activated.emit(index)
    assert document.parameters["angle"].unit == "mm", "das Auswahlsignal löscht sich nicht selbst"
    QApplication.processEvents()
    window.session.wait_for_idle()

    assert document.parameters["angle"].unit == DEGREE_UNIT
    assert window.session.history.can_undo
    window.session.undo()
    assert document.parameters["angle"].unit == "mm"


def test_saving_and_reopening_keeps_the_stack(session: Session, tmp_path: Path) -> None:
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()
    path = session.save_project(tmp_path / "projekt.p3d")

    assert not session.modified
    assert [entry.op for entry in load(path).document.ops] == ["load"]


def test_an_ambiguous_unit_reaches_the_surface_as_a_question(session: Session) -> None:
    seen: list[AskRequest] = []
    session.askRequested.connect(lambda request: (seen.append(request), request.reply("in")))

    session.import_model(MESHES / "bracket_inch.stl")
    session.wait_for_idle()
    result = session.evaluate_now()

    assert seen, "the surface is asked instead of the core guessing"
    assert result.scene.objects["obj_1"].mesh.bounds.size == pytest.approx((101.6, 50.8, 6.35))


def test_the_title_marks_unsaved_changes(session: Session, tmp_path: Path) -> None:
    """Der Titel sagt, ob etwas ungesichert ist — nur nicht überall mit einem Stern.

    **Bis zum 23.08.2026 stand hier ``endswith("*")`` für beide Lagen.** Seit
    der Titel den abgeleiteten Namen trägt, sind es zwei verschiedene Aussagen:

        nie gespeichert   „cube_clean (ungespeichert)"   das Wort sagt es
        gespeichert       „projekt.p3d*"                 der Stern sagt es

    Der Stern bedeutet „seit dem letzten Speichern geändert" — wo nie
    gespeichert wurde, kann er gar nicht fehlen, und dann trüge der Titel
    dieselbe Aussage zweimal.
    """
    assert not session.title.endswith("*")
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()
    assert "ungespeichert" in session.title, f"ohne Datei sagt es das Wort: {session.title!r}"
    assert session.title.startswith("cube_clean"), "und es nennt, was offen ist"

    session.save_project(tmp_path / "projekt.p3d")
    assert session.title == "projekt.p3d"

    # Und ab da trägt der Stern die Aussage.
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()
    assert session.title == "projekt.p3d*", f"mit Datei sagt es der Stern: {session.title!r}"


@pytest.mark.parametrize("named", [False, True])
def test_forgetting_recording_changes_removes_only_its_recovery(
    session: Session, tmp_path: Path, named: bool
) -> None:
    """Bewusstes Verwerfen schreibt keine Quelle und lässt fremde Sicherungen bestehen."""
    from app.core.scene.project import autosave_path

    target = tmp_path / "quelle.p3d"
    if named:
        session.save_project(target)
    original = target.read_bytes() if named else None
    session.apply("Aufnahmekörper", [OperationDraft(op="create_box", inputs=(), params={})])
    assert session.wait_for_idle()
    session.autosave()
    own = autosave_path(session.path, session.recovery_token)
    other = autosave_path(None, "andere-aufnahme")
    other.parent.mkdir(parents=True, exist_ok=True)
    other.write_bytes(b"fremde Sicherung")
    assert own.exists() and session.modified
    changes = []
    session.projectChanged.connect(lambda: changes.append(True))

    session.forget_changes()

    assert not session.modified
    assert not own.exists()
    assert other.read_bytes() == b"fremde Sicherung"
    assert changes == [True]
    assert (target.read_bytes() if named else None) == original
    assert named or not target.exists()


# --- window ---------------------------------------------------------------------


def all_menu_actions(window: MainWindow) -> list[QAction]:
    """Jeder Menüeintrag, auch in Untermenüs.

    Seit die dreizehn Kategorien in fünf Gruppen liegen (§2.5), steht das
    meiste eine Ebene tiefer. Erreichbar muss es trotzdem sein — auf welcher
    Ebene, ist die Frage dieses Tests nicht.
    """
    # Gefragt wird das Fenster, nicht die Leiste: es hält seine Menüs, und
    # ein über ``QAction.menu()`` geholter Wrapper nimmt beim Verwerfen das
    # C++-Menü mitsamt seinen Einträgen mit. Dass die Menüs auch wirklich in
    # der Leiste hängen, prüft `test_the_menubar_stays_a_bar`.
    return [action for menu in window._menus for action in menu.actions() if action.menu() is None]


def test_the_menubar_stays_a_bar(window: MainWindow) -> None:
    """§2.5: siebzehn Menüs sind keine Leiste mehr, sondern eine Liste."""
    top = [entry for entry in window.menuBar().actions() if entry.menu() is not None]
    assert len(top) <= 10, [entry.text() for entry in top]


def test_the_menu_is_built_from_the_registry(window: MainWindow) -> None:
    """Jede Operation bleibt erreichbar — im Menü, oder zusammengelegt.

    **Zwei Arten von Zusammenlegung, und sie sind verschieden.** Ein
    ``MENU_TWINS``-Zwilling ist dieselbe Handlung im anderen Rechenkern; sein
    Weg ist der Umschalter im Dialog des Partners, und der Partner trägt den
    Eintrag mit seinem eigenen Titel. Eine ``VARIANT_GROUPS``-Variante ist
    eine von mehreren gleichrangigen Arten; ihr Weg ist die Auswahl in einem
    Eintrag, der **keiner** Operation gehört und deshalb auch keinen
    Operationstitel trägt.

    Beide Male gilt dasselbe Hausprinzip — „eine Operation je Handlung, nicht
    je Variante" — und beide Male dieselbe Auflage: erreichbar bleibt alles,
    notfalls über die Palette.
    """
    from app.core.registry import (
        MENU_TWINS,
        VARIANT_GROUPS,
        in_the_menu_bar,
        palette_entries,
        variant_members,
    )

    labels = {action.text() for action in all_menu_actions(window)}
    offered = {entry.name for entry in palette_entries()}
    gruppen = {str(group.title) for group in VARIANT_GROUPS}

    for spec in REGISTRY.all():
        if spec.name in MENU_TWINS:
            # Beide Zwillinge tragen absichtlich denselben verständlichen
            # Titel. Am Text lässt sich deshalb nicht erkennen, ob Qt zwei
            # Einträge gebaut hat; die Aktionszuordnung kann es eindeutig.
            assert spec.name not in window._op_actions, (
                f"{spec.name} soll kein eigener Eintrag sein"
            )
            assert spec.name in offered, f"{spec.name} muss über die Palette erreichbar bleiben"
            partner = REGISTRY.get(MENU_TWINS[spec.name])
            assert partner.name in window._op_actions, "der sichtbare Zwilling trägt den Eintrag"
            if in_the_menu_bar(partner.category):
                assert str(partner.title) in labels, "der sichtbare Zwilling trägt den Eintrag"
            else:
                # Der Partner steht rechts (11.09.2026) — dort trägt er den Knopf.
                assert partner.name in window.selection_operations._buttons, (
                    "der sichtbare Zwilling trägt den Knopf rechts"
                )
            continue
        if spec.name in variant_members():
            assert str(spec.title) not in labels, f"{spec.name} soll kein eigener Eintrag sein"
            assert spec.name in offered, f"{spec.name} muss über die Palette erreichbar bleiben"
            continue
        if spec.name in catalogue_operations():
            # **Dritter Fall neben Zwilling und Variante, seit dem 29.08.2026.**
            # Die Bausteine der Bibliothek haben keinen Menüort mehr: Ein
            # räumliches Teil als Textzeile zu führen ist die schlechtere
            # Darstellung (§2.6). Wie bei den anderen beiden wird beides
            # geprüft — kein Eintrag, und trotzdem vollständig erreichbar.
            #
            # **Gefragt wird nach der Kachel, nicht nach der Kategorie.** Hier
            # stand ``spec.category in WITHOUT_MENU``, und damit nahm die
            # Ausnahme zwei Operationen mit, die gar keine Kachel haben:
            # ``create_lid`` und ``screw_lid`` verschwanden aus der Leiste,
            # ohne im Katalog aufzutauchen. Eine Ausnahme, die zu weit gefasst
            # ist, macht einen Wächter genau dort blind, wo er greifen soll.
            assert spec.name not in window._op_actions, (
                f"{spec.name} gehört in den Katalog, nicht ins Menü"
            )
            assert spec.name in offered, f"{spec.name} muss über die Palette erreichbar bleiben"
            continue
        if not in_the_menu_bar(spec.category):
            # **Vierter Fall, seit dem 11.09.2026: die Karte rechts.** Was einer
            # Auswahl gilt, steht nicht in der Leiste — die Aktion gibt es
            # trotzdem (Kürzel, Palette), der Knopf steht rechts, und der Weg
            # des Chats nennt genau das.
            assert spec.name in window._op_actions, f"{spec.name}: ohne Aktion kein Kürzel"
            assert str(spec.title) not in labels, f"{spec.name} steht rechts und in der Leiste"
            assert spec.name in window.selection_operations._buttons, f"{spec.name} fehlt rechts"
            assert spec.name in offered, f"{spec.name} muss über die Palette erreichbar bleiben"
            continue
        assert str(spec.title) in labels, f"{spec.name} is missing from the menu"

    assert gruppen <= labels, f"diese Sammeleinträge fehlen: {gruppen - labels}"


def test_shortcuts_from_the_registry_are_installed(window: MainWindow) -> None:
    """Jedes Kürzel des Registers hängt an einer Aktion — im Menü oder am Fenster.

    Die Handlungen rechts haben seit dem 11.09.2026 keinen Menüeintrag mehr;
    ihre Aktionen hängen am Fenster (oder, bei nackten Tasten wie Entf, an
    Objektbaum und Ansicht), und dort muss das Kürzel stehen.
    """
    shortcuts = {
        action.shortcut().toString().lower()
        for action in (*all_menu_actions(window), *window._op_actions.values())
        if not action.shortcut().isEmpty()
    }
    for spec in REGISTRY.all():
        if spec.shortcut:
            assert spec.shortcut.lower() in shortcuts


def test_a_dialog_says_which_body_it_works_on(window: MainWindow) -> None:
    """Zwei Würfel gewählt, ein Loch — und kein Wort dazu, in welchem (Regel 21).

    Eine Operation nimmt so viele Körper, wie sie deklariert, und zwar in
    Klickreihenfolge (``inputs_for``). Bei zwei gewählten und *Bohrung setzen*
    bekam einer ein Loch und der andere nicht; im Dialog stand nichts davon,
    und der Fenstertitel ist beim Klicken nicht im Blick. Das ist kein Raten —
    die Regel stand nur nirgends, wo jemand sie liest.

    Und im Normalfall steht dort nichts: ein gewählter Körper braucht keine
    Erklärung, welcher gemeint ist.
    """
    from app.ui.main_window import inputs_for

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    first = next(iter(window.session.last_result.scene.objects))

    spec = REGISTRY.get("drill_hole")
    window.object_tree.select_object(first)
    QApplication.processEvents()
    window.run_operation(spec)
    dialog = window._op_dialog
    assert dialog is not None
    assert dialog._note.text() == "", "bei einem gewählten Körper gibt es nichts zu sagen"
    dialog.reject()
    QApplication.processEvents()

    window.session.apply(
        "Objekt duplizieren",
        [OperationDraft(op="duplicate_object", inputs=(first,), params={})],
    )
    window.session.wait_for_idle()
    window.object_tree.tree.selectAll()
    QApplication.processEvents()
    chosen = window.object_tree.selected_objects()
    assert len(chosen) == 2, chosen
    taken = inputs_for(spec, list(window.session.last_result.scene.objects), chosen)
    assert len(taken) == 1, "die Operation nimmt einen Körper"

    window.run_operation(spec)
    dialog = window._op_dialog
    assert dialog is not None
    try:
        note = dialog._note.text()
        name = window.session.last_result.scene.objects[taken[0]].name
        assert name in note, f"der Dialog nennt den Körper nicht: {note!r}"
        assert "2" in note, f"und nicht, wie viele gewählt sind: {note!r}"
        assert not dialog._note.isHidden(), "der Satz steht da, aber unsichtbar"
    finally:
        dialog.reject()


def test_no_two_shortcuts_in_the_window_collide(window: MainWindow) -> None:
    """Eine doppelt belegte Taste tut **nichts** (§19.2).

    Qt meldet in dem Fall „Ambiguous shortcut overload" und führt keine der
    beiden Aktionen aus — der Nutzer drückt, und es passiert gar nichts.
    Geprüft war das nur halb: ``tests/test_registry_consistency.py`` hält die
    Kürzel der **Operationen** auseinander, und das Fenster bringt dreiundvierzig
    weitere mit — Ansichten, Werkzeugzeile, Dateibefehle, Navigation.

    Gefunden hätte man die Dublette also erst beim Drücken. Der Test steht hier
    und nicht dort, weil erst das gebaute Fenster beide Seiten kennt.
    """
    from itertools import combinations

    from PySide6.QtGui import QAction, QShortcut
    from PySide6.QtWidgets import QWidget

    taken: dict[str, list[tuple[str, Qt.ShortcutContext, tuple[QWidget, ...]]]] = {}
    for action in window.findChildren(QAction):
        for sequence in action.shortcuts():
            widgets = tuple(
                owner for owner in action.associatedObjects() if isinstance(owner, QWidget)
            )
            taken.setdefault(sequence.toString(), []).append(
                (action.text() or "(ohne Text)", action.shortcutContext(), widgets)
            )
    for shortcut in window.findChildren(QShortcut):
        parent = shortcut.parent()
        widgets = (parent,) if isinstance(parent, QWidget) else ()
        taken.setdefault(shortcut.key().toString(), []).append(
            ("QShortcut", shortcut.context(), widgets)
        )

    def overlap(
        first: tuple[str, Qt.ShortcutContext, tuple[QWidget, ...]],
        second: tuple[str, Qt.ShortcutContext, tuple[QWidget, ...]],
    ) -> bool:
        """Nur getrennte Widget-Bereiche dürfen dieselbe nackte Taste tragen."""
        _first_name, first_context, first_widgets = first
        _second_name, second_context, second_widgets = second
        local = Qt.ShortcutContext.WidgetWithChildrenShortcut
        if first_context != local or second_context != local:
            return True
        return any(
            left is right or left.isAncestorOf(right) or right.isAncestorOf(left)
            for left in first_widgets
            for right in second_widgets
        )

    twice = {
        key: [
            (first[0], second[0])
            for first, second in combinations(bindings, 2)
            if overlap(first, second)
        ]
        for key, bindings in taken.items()
        if key
    }
    twice = {key: pairs for key, pairs in twice.items() if pairs}
    assert not twice, f"doppelt belegte Tasten führen keine der beiden Aktionen aus: {twice}"


def test_escape_ends_insertion_from_the_history_without_changing_the_stack(
    window: MainWindow,
) -> None:
    """Ein echtes Escape erreicht den Rückweg trotz Fokus im Verlauf (§19.2)."""
    from PySide6.QtTest import QTest

    from app.ui.panels import open_section

    window.show()
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(30_000)
    operations = tuple(window.session.project.document.ops)
    assert window.session.start_inserting(operations[0].id)
    assert window.session.wait_for_idle(30_000)
    open_section(window.history_panel)
    window.activateWindow()
    window.history_panel.list.setFocus()
    QApplication.processEvents()
    assert window.history_panel.list.hasFocus(), "der Verlauf empfängt die Taste"
    assert window.history_panel.stop_insert_action.isEnabled()

    QTest.keyClick(window.history_panel.list, Qt.Key.Key_Escape)
    assert window.session.wait_for_idle(30_000)

    assert window.session.inserting is None, "Escape beendet das Einfügen"
    assert tuple(window.session.project.document.ops) == operations, "kein Schritt wurde geändert"
    assert not window.history_panel.stop_insert_action.isEnabled()


def test_the_window_starts_on_the_start_screen(window: MainWindow) -> None:
    assert window.stack.currentWidget() is window.start_screen
    assert not window.toolbar.isVisibleTo(window)
    assert window.start_screen.new_button.isVisibleTo(window)
    assert window.start_screen.open_button.isVisibleTo(window)
    assert window.start_screen.import_button.isVisibleTo(window)


def test_the_start_screen_shows_only_menus_that_do_something_there(window: MainWindow) -> None:
    """Auf dem Startbildschirm stehen nur Menüs, die dort etwas tun (§2.6).

    Bearbeiten, die Operationsgruppen und Ansicht setzen eine offene Szene
    voraus — als Leiste voller ausgegrauter Einträge waren sie Kulisse, keine
    Auskunft. Datei und Hilfe bleiben: Öffnen, Beenden, Handbuch und
    Freischalten sind genau dort sinnvoll.

    **Und sie bleiben es auch nach ``_update_actions``.** Der erste Bau maß nur
    das frisch aufgebaute Fenster, und ``action_new`` ruft kein
    ``_update_actions`` — in der laufenden Anwendung tut das jedes Signal.
    ``_hide_dead_menus`` blendet dabei nicht nur aus, es blendet auch wieder
    ein, sobald ein Eintrag geht: Bearbeiten, Erzeugen, Bausteine und Ansicht
    standen so nach dem ersten Klick wieder in der Leiste, ohne dass ein
    Projekt offen war.
    """

    def shown() -> list[str]:
        return [
            entry.text()
            for entry in window.menuBar().actions()
            if entry.menu() is not None and entry.isVisible()
        ]

    assert window.stack.currentWidget() is window.start_screen
    assert not window.toolbar.isVisibleTo(window)
    for menu in window._workspace_menus:
        assert not menu.menuAction().isVisible(), menu.title()
    assert len(shown()) == 2, shown()
    window._update_actions()
    assert len(shown()) == 2, shown()
    assert not window.toolbar.isVisibleTo(window)

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    assert window.toolbar.isVisibleTo(window)
    for menu in window._workspace_menus:
        assert menu.menuAction().isVisible(), menu.title()

    window.session._dirty = False
    window.action_new()
    assert len(shown()) == 2, "zurück auf dem Startbildschirm gilt wieder die kurze Leiste"
    window._update_actions()
    assert len(shown()) == 2, "und auch, wenn danach ein Signal die Aktionen auffrischt"
    assert not window.toolbar.isVisibleTo(window)

    # Und über die dritte Seite des Stapels ebenso: Vom Startbildschirm führt
    # ein Knopf ins Lager, und dort frischt jeder Weg über das Hilfemenü die
    # Aktionen auf. Auch dort gehört die Leiste nicht `_hide_dead_menus` —
    # sonst stehen die vier Menüs beim Zurückkommen wieder da, und auf dem
    # Startbildschirm rechnet sie niemand mehr nach.
    from app.ui.filament_inventory import InventoryView

    window.start_screen.inventory_button.click()
    assert window.stack.currentWidget() is window._inventory_view
    window._update_actions()
    inventory = window._inventory_view
    assert isinstance(inventory, InventoryView)
    inventory.back_button.click()
    assert window.stack.currentWidget() is window.start_screen
    assert len(shown()) == 2, "der Umweg über das Lager bringt keine Menüs mit zurück"
    assert not window.toolbar.isVisibleTo(window)


def test_the_start_screen_opens_the_manual(window: MainWindow) -> None:
    """§2.3: das Handbuch dort, wo es gebraucht wird.

    Die fünfundzwanzig Seiten mit den ersten fünfzehn Minuten erreichte nur,
    wer das Hilfemenü des Hauptfensters schon kannte — also niemand, für den
    sie geschrieben wurden.
    """
    window.start_screen.manual_button.click()

    assert window._manual is not None
    assert window._manual.isVisible()


def test_new_leads_back_to_the_examples(window: MainWindow) -> None:
    """Nach dem ersten Start waren die sieben Beispiele unerreichbar.

    *Neu* legte sofort eine leere Szene an; der Startbildschirm ist aber der
    einzige Ort, an dem die Beispielprojekte samt ihren Touren stehen. Wer sie
    danach sehen wollte, brauchte *Öffnen* und Pfadkenntnis.

    Ein Klick mehr ist es nicht: „Neues Projekt" ist dort der Hauptknopf und
    liegt auf der Eingabetaste.
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    assert window.stack.currentWidget() is not window.start_screen
    assert window.toolbar.isVisibleTo(window)

    window.action_new()
    assert window.stack.currentWidget() is window.start_screen
    assert not window.toolbar.isVisibleTo(window)

    # Ohne das fragt der Knopf, ob das Geladene weg darf — zu Recht, aber
    # ein Dialog offscreen wartet auf niemanden.
    window.session._dirty = False
    window.start_screen.new_button.click()
    window.session.wait_for_idle()
    assert window.stack.currentWidget() is not window.start_screen
    assert not window.session.project.document.ops, "und das Projekt ist leer"
    assert window.toolbar.isVisibleTo(window), "auch ein leeres neues Projekt zeigt seine Werkzeuge"


def test_the_help_menu_leads_back_to_the_examples(window: MainWindow) -> None:
    """Die Beispiele standen an genau einer Stelle (§37.2, August-Durchsicht 2.2).

    Sie sind Dokumentation, Abnahmetest und Startbildschirm-Inhalt in einem —
    und wer den Startbildschirm einmal verlassen hatte, fand sie nur über
    *Öffnen* mit Pfadkenntnis wieder. Im Hilfemenü sieht man nach
    Lehrmaterial.

    Und ohne Verwerfen-Falle: Der Eintrag zeigt den Startbildschirm, mehr
    nicht — gefragt wird erst, wenn wirklich etwas verloren ginge (Regel 19).
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    assert window.stack.currentWidget() is not window.start_screen

    labels = [
        action.text().replace("&", "")
        for menu in window.menuBar().actions()
        if menu.menu() is not None and menu.text().replace("&", "") == "Hilfe"
        for action in menu.menu().actions()
    ]
    assert "Beispiele" in labels

    window.action_examples()

    assert window.stack.currentWidget() is window.start_screen
    assert window.session.project.document.ops, "das Projekt steht noch, es ist nur verdeckt"


def test_the_help_menu_offers_direct_support(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der freiwillige Förderweg steht dort, wo man Kontakt und Auskunft sucht."""
    from app.branding import APP_NAME
    from app.ui.dialogs import DonationDialog

    entries = [
        action
        for menu in window.menuBar().actions()
        if menu.menu() is not None and menu.text().replace("&", "") == "Hilfe"
        for action in menu.menu().actions()
    ]
    support = next(
        action
        for action in entries
        if action.text().replace("&", "") == f"{APP_NAME} unterstützen …"
    )
    shown: list[str] = []
    monkeypatch.setattr(
        DonationDialog, "exec", lambda dialog: shown.append(dialog.windowTitle()) or 0
    )

    support.trigger()

    assert shown == [f"{APP_NAME} unterstützen"]


@pytest.mark.parametrize("provider", ["paypal", "gofundme"])
def test_the_support_dialog_opens_the_chosen_provider_only_after_the_click(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    """Der Dialog bleibt lokal; erst sein eindeutiger Knopf fragt nach draußen."""
    from PySide6.QtCore import QUrl
    from PySide6.QtWidgets import QLabel

    from app.branding import DONATION_URL, GOFUNDME_URL
    from app.ui.dialogs import DonationDialog

    opened: list[str] = []

    def open_url(url: QUrl) -> bool:
        opened.append(url.toString())
        return True

    monkeypatch.setattr("app.ui.dialogs.QDesktopServices.openUrl", open_url)
    dialog = DonationDialog()

    assert not opened
    assert "Standardbrowser" in dialog.browser_note.text()
    assert dialog.support_button.text() == "PayPal im Browser öffnen"
    assert dialog.gofundme_button.text() == "GoFundMe im Browser öffnen"
    assert dialog.close_button.text() == "Schließen"
    # Die Grenze steht vollständig in **einer** Zeile (Entscheidung Robert,
    # 23.09.2026) — leiser gesetzt, aber mit jedem Glied aus Konzept §2.
    terms = dialog.browser_note.text()
    for part in (
        "Freiwillig",
        "ohne Gegenleistung",
        "keine Bestellung",
        "keine Freischaltung",
        "keine Anrechnung auf einen späteren Kauf",
        "keine Spendenbescheinigung",
        "Erst Ihr Klick öffnet",
        "Daten an den gewählten Anbieter",
    ):
        assert part in terms, f"die Grenze verliert „{part}“"
    assert dialog.browser_note.property("level") == "caption", "optisch zurückgenommen"
    text = "\n".join(label.text() for label in dialog.findChildren(QLabel))
    assert "€" not in text and "EUR" not in text, "keine Beträge — die nennt die Kampagne"

    button, url = (
        (dialog.support_button, DONATION_URL)
        if provider == "paypal"
        else (dialog.gofundme_button, GOFUNDME_URL)
    )
    button.click()

    assert opened == [url]
    dialog.reject()
    assert opened == [url]


def test_the_support_dialog_invites_before_it_explains(qt_app: QApplication) -> None:
    """Oben die Person, dann wofür das Geld ist, dann zwei gleichwertige Wege.

    Robert, 23.09.2026: einladend statt einer Wand aus Rechtstext. Drei knappe
    Punkte mit Symbol aus dem Satz der Oberfläche, darunter die zwei Anbieter
    ohne Rangordnung, die Grenze als eine leise Zeile und ein Weg ohne Geld.
    """
    from PySide6.QtWidgets import QLabel, QPushButton

    from app.ui import icons
    from app.ui.dialogs import DonationDialog

    dialog = DonationDialog()
    dialog.show()
    qt_app.processEvents()
    try:
        assert "Robert" in dialog.personal.text()
        assert "Bamberg" in dialog.personal.text()
        assert [point for point, _detail in dialog.purposes] == [
            "Zwei KI-Werkzeuge",
            "Laufende Kosten",
            "Schon selbst bezahlt",
        ]
        details = " ".join(detail for _point, detail in dialog.purposes)
        for named in ("Hosting", "Domain", "Apple", "Signaturzertifikat"):
            assert named in details
        for symbol in ("generate", "network", "done"):
            assert symbol in icons.known(), f"{symbol} fehlt im Symbolsatz"
        marks = [
            label
            for label in dialog.findChildren(QLabel)
            if label.pixmap() is not None and not label.pixmap().isNull()
        ]
        assert len(marks) == 3, "je Punkt ein Symbol"
        assert all(mark.accessibleName() for mark in marks), "das Symbol trägt sein Wort"

        # Gleichwertig: gleiche Größe, kein Akzent, keiner der beiden empfohlen.
        paypal, gofundme = dialog.support_button, dialog.gofundme_button
        assert paypal.sizeHint().height() == gofundme.sizeHint().height()
        assert abs(paypal.width() - gofundme.width()) <= 1
        assert not any(button.isDefault() for button in dialog.findChildren(QPushButton)), (
            "kein Knopf trägt einen Akzent, den niemand bestellt hat"
        )
        assert dialog.share_button.text() == "Link zur Website kopieren"
        assert dialog.feedback_button.text() == "Rückmeldung senden …"
    finally:
        dialog.close()


def test_helping_without_money_copies_the_site_and_opens_the_existing_feedback(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Weitersagen legt die Adresse ab, Rückmeldung öffnet den vorhandenen Dialog.

    Kein zweiter Weg hinaus: Der Knopf schließt den Unterstützen-Dialog, und das
    Fenster öffnet danach ``action_feedback`` — denselben Dialog mit demselben
    einen Sendeknopf wie aus dem Hilfemenü.
    """
    from app.branding import WEBSITE_URL
    from app.ui.dialogs import DonationDialog

    opened: list[object] = []
    monkeypatch.setattr("app.ui.dialogs.QDesktopServices.openUrl", opened.append)
    asked: list[str] = []
    monkeypatch.setattr(window, "action_feedback", lambda kind="idea": asked.append(kind))

    def press_both(dialog: DonationDialog) -> int:
        previous = QApplication.clipboard().text()
        try:
            dialog.share_button.click()
            assert QApplication.clipboard().text() == WEBSITE_URL
            assert dialog.share_button.text() == "Link kopiert", "der Klick sagt, dass er wirkte"
        finally:
            QApplication.clipboard().setText(previous)
        dialog.feedback_button.click()
        return int(dialog.result())

    monkeypatch.setattr(DonationDialog, "exec", press_both)

    window.action_donate()

    assert asked == ["idea"], "der vorhandene Rückmeldedialog geht auf, einmal"
    assert not opened, "weder Weitersagen noch Rückmeldung öffnen den Browser"


def test_the_about_dialog_points_to_the_support_dialog(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Über-Dialog nennt, wer dahintersteht — und daneben den Weg zur Unterstützung."""
    from app.branding import APP_NAME
    from app.ui.dialogs import AboutDialog, DonationDialog

    shown: list[str] = []
    monkeypatch.setattr(AboutDialog, "exec", lambda dialog: dialog.support_button.click() or 0)
    monkeypatch.setattr(
        DonationDialog, "exec", lambda dialog: shown.append(dialog.windowTitle()) or 0
    )

    window.action_about()

    assert shown == [f"{APP_NAME} unterstützen"], "nacheinander, nicht übereinander"


def test_the_help_menu_entry_for_support_carries_the_heart(window: MainWindow) -> None:
    """Sichtbarer im Menü: dasselbe Herz wie auf der Startfläche und ein Satz dazu."""
    from app.branding import APP_NAME

    entries = [
        action
        for menu in window.menuBar().actions()
        if menu.menu() is not None and menu.text().replace("&", "") == "Hilfe"
        for action in menu.menu().actions()
    ]
    support = next(
        action
        for action in entries
        if action.text().replace("&", "") == f"{APP_NAME} unterstützen …"
    )
    assert not support.icon().isNull()
    assert "freiwillig" in support.statusTip()


# --- Einladung zur Unterstützung am Weg der Anwendung (Robert, 23.09.2026) ---


@pytest.fixture
def own_feedback(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Ein eigenes Profil für ``feedback.json`` — die Suite teilt sonst eines."""
    from app.core import feedback

    folder = tmp_path / "profil"
    monkeypatch.setattr(feedback, "user_config_dir", lambda: folder)
    return folder


def _export_once(window: MainWindow, monkeypatch: pytest.MonkeyPatch, target: Path) -> None:
    """Ein Export über den Menüweg: Dateidialog, Arbeiter, Quittung."""
    from PySide6.QtWidgets import QFileDialog

    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "STL (*.stl)")),
    )
    window.action_export()
    wait_for_export(window)


def test_the_third_export_shows_the_support_line_once(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, own_feedback: Path
) -> None:
    """Gezählt wird am echten Export, und die Zeile kommt genau beim dritten.

    Sie nimmt keinen Fokus, sie öffnet nichts von selbst, und nach dem Kreuz
    kommt sie in dieser Version nicht wieder — auch nicht mit dem vierten.
    """
    from app.core import feedback

    window.show()
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(30_000)
    notice = window._support_notice
    for number in (1, 2, 3):
        assert not notice.isVisible(), f"vor dem {number}. Export steht nichts da"
        focused = QApplication.focusWidget()
        target = tmp_path / f"wuerfel-{number}.stl"
        _export_once(window, monkeypatch, target)
        assert target.is_file()
        assert feedback.read().deliveries == number
    assert notice.isVisibleTo(window.viewport), "nach dem dritten Export steht die Zeile da"
    assert QApplication.focusWidget() is focused, "sie nimmt niemandem den Fokus"
    assert feedback.read().support_invited, "gezeigt heißt gesehen"
    assert notice.text.text() == str(feedback.SUPPORT_LINE)

    notice.close_button.click()
    assert not notice.isVisible()
    _export_once(window, monkeypatch, tmp_path / "wuerfel-4.stl")
    assert not notice.isVisible(), "in dieser Version nie wieder"
    assert feedback.read().deliveries == feedback.SUPPORT_AFTER_DELIVERIES


def test_declined_and_failed_exports_do_not_count(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, own_feedback: Path
) -> None:
    """Abgebrochen am Dateidialog, abgelehnt nach der Prüfung, gescheitert beim Schreiben."""
    from PySide6.QtWidgets import QFileDialog

    from app.core import feedback

    window.show()
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(30_000)

    # Der Dateidialog wird geschlossen, ohne einen Namen zu wählen.
    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(lambda *a, **k: ("", "")))
    window.action_export()
    wait_for_export(window)
    assert feedback.read().deliveries == 0

    # Die Prüfung findet etwas, und der Kunde schreibt nicht.
    monkeypatch.setattr(
        main_window_module,
        "check_before_export",
        lambda *args, **kwargs: [Finding("fit.collision", "warning", "Überschneidung")],
    )
    monkeypatch.setattr(main_window_module, "confirm_export", lambda *args: False)
    _export_once(window, monkeypatch, tmp_path / "abgelehnt.stl")
    assert not (tmp_path / "abgelehnt.stl").exists()
    assert feedback.read().deliveries == 0

    # Das Schreiben scheitert.
    monkeypatch.setattr(main_window_module, "check_before_export", lambda *a, **k: [])
    shown: list[object] = []
    monkeypatch.setattr(main_window_module, "show_error", lambda *args: shown.append(args))

    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise errors.FileWriteError(str(tmp_path / "gescheitert.stl"), detail="gesperrt")

    monkeypatch.setattr(main_window_module, "write_plan", refuse)
    _export_once(window, monkeypatch, tmp_path / "gescheitert.stl")
    assert shown, "der Fehler kam an"
    assert feedback.read().deliveries == 0
    assert not window._support_notice.isVisible()


def test_a_slicer_start_counts_on_the_way_of_the_application(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, own_feedback: Path
) -> None:
    """Slicen im Druckdialog zählt — und die Zeile erscheint erst, wenn er zu ist.

    Zwei Exporte vorher, der Slicer-Start ist der dritte Erfolg. Hinter einem
    modalen Fenster stünde die Zeile ungesehen; angeboten wird sie danach.
    """
    import time

    from app.core import feedback
    from app.core.slice import gcode
    from app.ui import print_settings_dialog as dialog_module

    window.show()
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(30_000)
    _export_once(window, monkeypatch, tmp_path / "eins.stl")
    _export_once(window, monkeypatch, tmp_path / "zwei.stl")
    assert feedback.read().deliveries == 2

    executable = tmp_path / "prusa-slicer-console.exe"
    executable.write_bytes(b"")
    setup = handover.SlicerSetup(executable=executable, flavour="prusa")
    model = tmp_path / "platte.3mf"
    model.write_bytes(b"")
    output = tmp_path / "platte.gcode"
    output.write_text("G1 X1\n", encoding="utf-8")
    monkeypatch.setattr(
        dialog_module,
        "_prepare_plate",
        lambda _job, plate: dialog_module.PlateRun(
            plate=plate, model=model, slots=(MaterialSlot(0, ""),)
        ),
    )
    monkeypatch.setattr(
        dialog_module.handover,
        "slice_model",
        lambda *_args, **_kwargs: handover.SliceOutcome(
            gcode_path=output, metrics=gcode.GcodeMetrics()
        ),
    )
    seen_while_open: list[bool] = []

    class SlicingDialog(dialog_module.PrintSettingsDialog):
        """Wie ein Kunde, der auf *Slicen* drückt und nach dem Ergebnis schließt."""

        def exec(self) -> int:
            self.wait_for_slicers()
            monkeypatch.setattr(self, "_current_setup", lambda: setup)
            monkeypatch.setattr(self, "_chosen_plates", lambda: [0])
            monkeypatch.setattr(self, "_plate_slots", list)
            self._slice()
            worker = self._worker
            assert worker is not None and worker.wait(20_000)
            deadline = time.perf_counter() + 10.0
            while self._worker is not None and time.perf_counter() < deadline:
                QApplication.processEvents()
            seen_while_open.append(window._support_notice.isVisible())
            return 0

    monkeypatch.setattr(main_window_module, "PrintSettingsDialog", SlicingDialog)

    window.action_print_settings()

    assert feedback.read().deliveries == 3, "der Slicer-Start zählt am Weg der Anwendung"
    assert seen_while_open == [False], "nicht hinter dem modalen Dialog"
    assert window._support_notice.isVisibleTo(window.viewport), "danach steht sie da"


def test_the_support_line_stays_clear_of_banner_and_cards(
    window: MainWindow, own_feedback: Path
) -> None:
    """Die Einladung weicht den echten Karten aus und kehrt an ihren freien Platz zurück.

    Ist die Lücke oben zu schmal, darf sie unter die kürzere Karte. Geprüft
    werden ihre Überschneidungen, keine offscreen erfundene Schriftbreite.
    """
    from PySide6.QtCore import QRect

    from app.ui.survey import NOTICE_TOP

    window.resize(1400, 900)
    window.show()
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(30_000)
    for _ in range(3):
        QApplication.processEvents()
    viewport = window.viewport
    notice = window._support_notice
    banner = viewport.banner
    survey = window._survey_notice
    obstacles = (
        window.overlay.left,
        window.overlay.right,
        window.overlay.bottom,
        viewport.view_bar,
        viewport.drag_bar,
        banner,
        survey,
    )

    def assert_clear() -> None:
        """Die sichtbaren Bedienflächen unabhängig von der Platzsuche vergleichen."""
        assert viewport.rect().contains(notice.geometry())
        for obstacle in obstacles:
            if obstacle is None or not obstacle.isVisible():
                continue
            corner = viewport.mapFromGlobal(obstacle.mapToGlobal(QPoint(0, 0)))
            area = QRect(corner, obstacle.size())
            assert not area.intersects(notice.geometry()), (
                f"{obstacle.objectName()} bei {area} verdeckt {notice.geometry()}"
            )

    notice.offer()
    QApplication.processEvents()
    assert_clear()

    banner.show()
    banner.adjustSize()
    banner.move((viewport.width() - banner.width()) // 2, 12)
    QApplication.processEvents()
    assert_clear()
    survey.ask()
    QApplication.processEvents()
    assert_clear()

    banner.hide()
    survey.hide()
    QApplication.processEvents()
    assert_clear()
    # Erst ohne die Karten ist die Oberkante sicher frei. Deren Inhalt kann
    # während der Anzeige noch durch die Druckprüfung kürzer werden.
    for obstacle in obstacles:
        if obstacle is not None:
            obstacle.hide()
    QApplication.processEvents()
    assert_clear()
    assert notice.y() == NOTICE_TOP, "an der freien Oberkante rückt die Einladung nach"


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_both_invitations_follow_the_theme(window: MainWindow, theme: str) -> None:
    """Die Rückfragekarte blieb im hellen Thema dunkel — beide folgen jetzt dem Wechsel."""
    from app.ui.theme import THEMES

    window.action_theme(theme)
    try:
        for notice in (window._survey_notice, window._support_notice):
            assert THEMES[theme]["window"] in notice.styleSheet(), (
                f"{notice.objectName()} trägt nicht die Fläche des Themas {theme}"
            )
    finally:
        window.action_theme("dark")


@pytest.mark.parametrize("provider", ["paypal", "gofundme"])
def test_a_blocked_payment_page_offers_a_copyable_way_out(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, provider: str
) -> None:
    """Ein fehlender Browser lässt niemanden mit einer Adresse zum Abtippen stehen."""
    from app.branding import DONATION_URL, GOFUNDME_URL
    from app.ui.dialogs import DonationOpenErrorDialog, open_donation

    url = DONATION_URL if provider == "paypal" else GOFUNDME_URL
    shown: list[DonationOpenErrorDialog] = []
    monkeypatch.setattr("app.ui.dialogs.QDesktopServices.openUrl", lambda _url: False)
    monkeypatch.setattr(
        DonationOpenErrorDialog,
        "exec",
        lambda dialog: shown.append(dialog) or 0,
    )

    assert not open_donation(url=url)
    assert len(shown) == 1
    assert shown[0].copy_button.text() == "Zahlungslink kopieren"

    previous_text = qt_app.clipboard().text()
    try:
        shown[0].copy_button.click()
        assert qt_app.clipboard().text() == url
    finally:
        qt_app.clipboard().setText(previous_text)


def test_an_empty_scene_leaves_nothing_of_the_last_one(window: MainWindow) -> None:
    """Nach *Neu* blieben die orangen Merkmalsmarkierungen des vorigen Objekts
    im Bild stehen, während Objektbaum und Prüfbericht längst leer waren."""
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    viewport = window.viewport
    viewport.select("obj_1")
    viewport.set_feature_overlay(True)
    viewport.measurements.add(
        Measurement(kind="distance", value=10.0, points=((0.0, 0.0, 0.0), (10.0, 0.0, 0.0)))
    )

    viewport.show_scene(None)

    assert viewport._selected is None
    assert len(viewport.measurements) == 0
    assert viewport._feature_actors == []


def test_the_right_panel_folds_away(window: MainWindow) -> None:
    assert not window.right_column.isHidden()
    window.action_toggle_right()
    assert not window.settings.right_panel_visible
    assert window.right_column.isHidden()
    window.action_toggle_right()
    assert window.settings.right_panel_visible
    assert not window.right_column.isHidden()


def test_view_menu_and_settings_share_theme_and_navigation_names(window: MainWindow) -> None:
    """Menü und Einstellungsdialog pflegen keine zwei Vokabulare."""
    from app.ui.settings_dialog import NAVIGATION, THEMES

    themes = {str(action.data()): action.text() for action in window._theme_group.actions()}
    navigation = {
        str(action.data()): action.text() for action in window._navigation_group.actions()
    }

    assert themes == {key: str(label) for key, label in THEMES.items()}
    assert navigation == {key: str(label) for key, label in NAVIGATION.items()}


def test_measure_bar_offers_angles_and_shows_degrees(qt_app: QApplication) -> None:
    """Ein Winkel ist auswählbar und wird nicht als Länge beschriftet."""
    from app.ui.section_bar import MeasureBar

    bar = MeasureBar()
    modes = [bar.mode.itemData(index) for index in range(bar.mode.count())]
    assert "angle" in modes

    bar.show_measurement("angle", 90.0, 1)
    assert "90°" in bar.readout.text()
    assert "mm" not in bar.readout.text()


def test_angle_measurement_uses_two_detected_planes(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§18.3 meint erkannte Ebenen, nicht drei frei geklickte Punkte."""
    from types import SimpleNamespace

    from app.ui.viewport import Viewport

    viewport = Viewport()
    faces = {
        "one": SimpleNamespace(
            kind="face", params={"normal": (1.0, 0.0, 0.0), "centre": (0.0, 0.0, 0.0)}
        ),
        "two": SimpleNamespace(
            kind="face", params={"normal": (0.0, 1.0, 0.0), "centre": (5.0, 0.0, 0.0)}
        ),
    }
    entry = SimpleNamespace(features=faces)
    viewport._result = SimpleNamespace(scene=SimpleNamespace(objects={"obj_1": entry}))
    monkeypatch.setattr(viewport, "_object_at", lambda point: "obj_1")
    monkeypatch.setattr(viewport, "_feature_at", lambda point: "one" if point[0] == 0 else "two")

    statuses: list[str] = []
    viewport.measurementStatus.connect(statuses.append)
    viewport._measure_plane_angle((0.0, 0.0, 0.0))
    viewport._measure_plane_angle((5.0, 0.0, 0.0))

    assert statuses and "zweite Ebene" in statuses[-1]
    assert len(viewport.measurements) == 1
    assert viewport.measurements.entries[0].kind == "angle"
    assert viewport.measurements.entries[0].value == pytest.approx(90.0)


def test_measuring_never_ends_in_silence(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die drei stummen Ausgänge des Messens melden sich jetzt (§2.7).

    Der Winkel-Pfad machte es seit je vor; Distanz und Wandstärke hatten
    drei ``return`` ohne ein Wort — Klick ins Leere, Wand ohne Messwert,
    erster Punkt gesetzt. Wer am Messen war und danebenklickte, sah einfach
    nichts und hielt das Werkzeug für kaputt.
    """
    import trimesh as raw_trimesh

    from app.core.geom.mesh import MeshData
    from app.ui.viewport import Viewport

    viewport = Viewport()
    statuses: list[str] = []
    viewport.measurementStatus.connect(statuses.append)
    viewport._measure_mode = "distance"

    monkeypatch.setattr(viewport, "_nearest_mesh", lambda point: None)
    viewport._on_picked((0.0, 0.0, 0.0))
    assert statuses and "Körper anklicken" in statuses[-1], statuses

    box = MeshData.of(raw_trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    monkeypatch.setattr(viewport, "_nearest_mesh", lambda point: box)
    viewport._on_picked((5.0, 0.0, 0.0))
    assert "zweiten Punkt anklicken" in statuses[-1], statuses
    assert viewport._pending_point is not None

    viewport._measure_mode = "thickness"
    monkeypatch.setattr("app.ui.viewport.wall_thickness", lambda mesh, point: None)
    viewport._on_picked((5.0, 0.0, 0.0))
    assert "Wand" in statuses[-1], statuses
    assert len(viewport.measurements) == 0, "gemeldet heißt nicht gemessen"


def test_opening_a_model_leaves_the_start_screen(window: MainWindow) -> None:
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    assert window.stack.currentWidget() is window.overlay
    assert [entry.op for entry in window.session.project.document.ops] == ["load"]


def test_importing_from_the_start_screen_shows_the_workspace(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Von acht Wegen ins Dokument wechselte genau dieser nicht in den
    Arbeitsbereich — und auf ihn zeigt der Schlussknopf der
    Erstinbetriebnahme: Modell geladen, Startbildschirm stand (§2.3)."""
    from PySide6.QtWidgets import QFileDialog

    assert window.stack.currentWidget() is window.start_screen
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(MESHES / "cube_clean.stl"), "")),
    )

    assert not window.toolbar.isVisibleTo(window)
    window.start_screen.import_button.click()
    window.session.wait_for_idle()

    assert window.stack.currentWidget() is not window.start_screen
    assert window.toolbar.isVisibleTo(window)
    assert [entry.op for entry in window.session.project.document.ops] == ["load"]


def test_the_panels_follow_the_evaluation(window: MainWindow) -> None:
    window.open_path(MESHES / "two_components.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    window._on_scene(result)

    assert window.object_tree.tree.topLevelItemCount() == 1
    assert window.report.list.count() >= 1, "the findings of the input stage are shown"
    assert window.history_panel.list.count() == 1


def test_the_status_bar_describes_the_selection(window: MainWindow) -> None:
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window._on_scene(window.session.evaluate_now())
    window.object_tree.tree.setCurrentItem(window.object_tree.tree.topLevelItem(0))

    assert "20,00" in window.measurements.text()
    assert "cm³" in window.measurements.text()


# --- Auswahl und Merkmalsfenster ------------------------------------------------


def test_a_thread_dialog_uses_the_selected_face_or_bore(window: MainWindow) -> None:
    """Bohrung und ebene Außenfläche bekommen die Richtung ohne Raten."""
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    face = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "face"
    )
    spec = REGISTRY.get("insert_printed_thread")

    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)
    window.run_operation(spec)
    dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
    assert dialog.values()["at_feature"] == hole
    assert dialog.values()["internal"], "Bohrung heißt Innengewinde"
    internal_label = dialog._rows["internal"].labelForField(dialog._editors["internal"])
    assert internal_label is not None
    assert internal_label.text() == "Innengewinde (aus = Außengewinde)"
    assert "Gewindebolzen auf einer ebenen Außenfläche" in dialog._editors["internal"].toolTip()
    assert "Drehdeckel erzeugen" in dialog._editors["internal"].toolTip()
    dialog.reject()

    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, face)
    window.run_operation(spec)
    dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
    assert dialog.values()["at_feature"] == face
    assert not dialog.values()["internal"], "eine ebene Fläche heißt Gewindebolzen"
    dialog.reject()


def test_drawable_faces_keep_the_object_that_owns_them(window: MainWindow) -> None:
    """Die Ebenenliste bindet jede Fläche an ihren Körper, ohne NameError."""
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id = next(iter(result.scene.objects))

    faces = window._drawable_faces()

    assert faces, "ein Würfel bietet ebene Zeichenflächen an"
    assert all(identifier.startswith(f"{object_id}:") for identifier, _label, _normal in faces)


def test_a_tree_context_click_selects_the_feature_it_opens_for(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Rechtsklick auf eine Bohrung darf nicht die vorige Auswahl benutzen.

    **Und er muss die Zeile treffen, auf die gezeigt wird.** Dieser Test rief
    ``_on_context_menu`` bis zum 03.09.2026 selbst auf und rechnete seinen
    Punkt vorher mit ``viewport().mapTo(tree, …)`` in Baumkoordinaten um — also
    genau in die falsche Annahme hinein, die im Handler stand. Beide Fehler
    hoben sich auf, der Test war grün, und in der Anwendung sprang die Auswahl
    zwei Zeilen nach oben (Robert, 03.09.2026). Jetzt geht der Weg über das
    echte Ereignis an den Viewport, so wie Qt es zustellt.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    face = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "face"
    )

    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)
    target = next(
        item
        for item in window.object_tree.tree.selectedItems()
        if item.data(1, Qt.ItemDataRole.UserRole) == hole
    )
    assert target is not None
    window.show()
    window.object_tree.tree.expandAll()
    window.object_tree.tree.scrollToItem(target)
    QApplication.processEvents()
    tree = window.object_tree.tree
    point = tree.visualItemRect(target).center()
    assert point.y() >= 0, "die Bohrung hat eine sichtbare Baumzeile"
    window.object_tree.select_feature(object_id, face)
    monkeypatch.setattr(window.object_tree, "context_menu", lambda: None)

    QApplication.sendEvent(
        tree.viewport(),
        QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse, point, tree.viewport().mapToGlobal(point)
        ),
    )
    QApplication.processEvents()

    assert window.object_tree.selected_feature() == hole


def test_the_selection_window_starts_closed_and_opens_on_a_selection(
    window: MainWindow,
) -> None:
    """Ein Bereich, der beim Start nichts zeigt, ist Fläche ohne Auskunft.

    Gemessen an vier Videoaufnahmen (03.09.2026): Das Fenster stand offen und
    leer am rechten Rand und nahm der Ansicht 165 von 1280 Punkten für einen
    einzigen Satz ab. Wer eine Datei öffnet, hat noch nichts gewählt — es geht
    bei der **ersten** Auswahl auf, wo es eine gerade gestellte Frage
    beantwortet.

    **Seit dem 07.09.2026 zählt dazu auch ein gewählter Körper** (Konzept „Ein
    Ort für die Auswahl", A). Bis dahin galt „ein Körper ist kein Merkmal", und
    das stimmte: Das Fenster zeigte nur Maße. Jetzt trägt es die Handlungen zur
    Auswahl, und ein Kunde mit einem gewählten Halter stünde sonst vor einem
    Fenster, das seine Handlungen hat und sie nicht zeigt.
    """
    assert window.feature_dock.isHidden(), "beim Start zu"

    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    window.object_tree.select_object(object_id)
    QApplication.processEvents()
    assert not window.feature_dock.isHidden(), "beim gewählten Körper geht es auf"

    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    window.object_tree.select_feature(object_id, hole)
    QApplication.processEvents()
    assert not window.feature_dock.isHidden(), "und beim Merkmal darin bleibt es"


def _close_the_feature_window(window: MainWindow) -> None:
    """Das Merkmalfenster zumachen wie mit seinem Kreuz — am gezeigten Hauptfenster.

    Das Merkmalfenster ist seit ``9d8d33395`` ein natives Fenster, weil es über
    der Grafikfläche liegt (``overlay.hold_above_the_view``). Solange das
    Hauptfenster nie gezeigt wurde, ist sein ``QWindow`` oberste Ebene, und
    ``close()`` geht an ihm vorbei — kein Schließereignis, kein Verbergen, das
    Fenster bleibt offen. Im Betrieb steht das Hauptfenster; also hier auch.
    """
    window.show()
    QApplication.processEvents()
    handle = window.feature_dock.windowHandle()
    assert handle is None or not handle.isTopLevel(), "das Merkmalfenster hängt im Hauptfenster"
    window.feature_dock.close()
    QApplication.processEvents()


def test_a_closed_feature_window_stays_closed_for_this_selection(window: MainWindow) -> None:
    """Wer es zumacht, hat für **diese** Auswahl entschieden.

    Ein Fenster, das nach jedem Klick wieder aufspringt, ist keine Hilfe,
    sondern eine Wiederholung derselben Frage. Bis zum 07.09.2026 galt das
    Zumachen deshalb der ganzen Sitzung — danach öffnete nur noch der Schalter
    unter *Ansicht*.

    **Der Merker gehört jetzt der laufenden Auswahl** (Entscheidung Robert,
    07.09.2026, Konzept „Ein Ort für die Auswahl", D). Der Grund ist, was das
    Fenster künftig trägt: Mit den Handlungen zur Auswahl darin wäre ein
    Zumachen auf Dauer der Verlust aller Handlungen — ein Klick auf ein Kreuz,
    und der Kunde kommt bis zum Neustart nicht mehr an sie heran. Die Zusage
    von oben bleibt für den Fall, für den sie geschrieben wurde: bei diesem
    Merkmal springt nichts wieder auf. Die nächste Auswahl bringt es zurück.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    holes = [identifier for identifier, feature in entry.features.items() if feature.kind == "hole"]
    assert len(holes) >= 2
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, holes[0])
    QApplication.processEvents()
    assert not window.feature_dock.isHidden()

    _close_the_feature_window(window)
    assert window.feature_dock.dismissed, "das Zumachen ist gemerkt"

    # Dasselbe Merkmal noch einmal ist keine neue Auswahl — hier gilt die
    # Zusage, und das Fenster bleibt zu.
    window.object_tree.select_feature(object_id, holes[0])
    QApplication.processEvents()
    assert window.feature_dock.isHidden(), "bei derselben Auswahl springt nichts auf"

    window.object_tree.select_feature(object_id, holes[1])
    QApplication.processEvents()
    assert not window.feature_dock.isHidden(), (
        "die nächste Auswahl bringt es zurück — sonst wären die Handlungen dauerhaft weg"
    )


def test_reopening_the_feature_window_takes_the_decision_back(window: MainWindow) -> None:
    """Der Schalter unter *Ansicht* ist der Ausweg, und er hebt das Zumachen auf.

    Wer es zumacht, sagt „nicht jetzt"; wer es über den Schalter wieder
    aufmacht, sagt das Gegenteil. Danach geht es auch wieder von selbst auf —
    sonst müsste er es für jedes weitere Merkmal erneut aufmachen.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)
    QApplication.processEvents()
    _close_the_feature_window(window)
    assert window.feature_dock.dismissed

    window.feature_dock.toggleViewAction().trigger()
    QApplication.processEvents()
    assert not window.feature_dock.isHidden(), "der Schalter öffnet es"
    assert not window.feature_dock.dismissed, "und nimmt das Zumachen zurück"


def test_two_selected_features_show_their_distance(window: MainWindow) -> None:
    """Zwei Zeilen im Baum markieren und den Abstand lesen — ohne Messwerkzeug.

    Geprüft wird die Kette: Der Baum meldet die Mehrfachauswahl über ein
    eigenes Signal, weil ``featureSelected`` bei zwei Zeilen bewusst nichts
    trägt, und das Panel macht daraus eine Auskunft.
    """
    from PySide6.QtWidgets import QLabel

    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    holes = [identifier for identifier, feature in entry.features.items() if feature.kind == "hole"]
    assert len(holes) >= 2
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, holes[0])
    QApplication.processEvents()

    window.object_tree.featuresSelected.emit([(object_id, holes[0]), (object_id, holes[1])])
    QApplication.processEvents()

    assert window.viewport.highlighted_features() == (holes[0], holes[1])
    assert window.viewport.highlighted_object() is None, "der Körper bleibt grau"
    assert window.viewport.highlighted_faces(), "beide Bohrungen bleiben im Viewport markiert"
    texte = " ".join(
        widget.text()
        for row in window.feature_panel._built
        for widget in ([row] if isinstance(row, QLabel) else row.findChildren(QLabel))
    )
    assert tr("Abstand") in texte, texte
    assert tr("in X") in texte and tr("in Z") in texte


def test_three_selected_features_explain_the_pair_limit(window: MainWindow) -> None:
    """Bei drei Merkmalen wird keine Beziehung geraten; die Auskunft nennt die Grenze."""
    from PySide6.QtWidgets import QLabel

    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    holes = [identifier for identifier, feature in entry.features.items() if feature.kind == "hole"]
    assert len(holes) >= 3
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, holes[0])
    QApplication.processEvents()
    window.object_tree.featuresSelected.emit([(object_id, hole) for hole in holes[:3]])
    QApplication.processEvents()
    assert any("genau zwei" in label.text() for label in window.feature_panel.findChildren(QLabel))
    assert not window.session.project.document.fits


def _manual_face_pair(window: MainWindow) -> tuple[tuple[str, str], tuple[str, str]]:
    """Zwei echte Quader mit parallelen, um einen Millimeter versetzten Deckflächen."""
    assert window.session.apply(
        "Zwei Teile",
        [
            OperationDraft(op="create_box"),
            OperationDraft(op="create_box"),
            OperationDraft(op="translate_object", inputs=("obj_2",), params={"dz": 1.0}),
        ],
    )
    assert window.session.wait_for_idle(30000)
    result = window.session.last_result
    assert result is not None and result.complete
    references = []
    for identifier, entry in result.scene.objects.items():
        face = max(
            (feature for feature in entry.features.values() if feature.kind == "face"),
            key=lambda feature: feature.params["centre"][2],
        )
        references.append((identifier, face.id))
    assert len(references) == 2
    return references[0], references[1]


def test_manual_fit_from_two_tree_rows_is_one_saved_undoable_relationship(
    window: MainWindow, tmp_path: Path
) -> None:
    """Reale Baumwahl und Schaltfläche schreiben eine Passung ohne Geometrieoperation."""
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLabel

    from app.core.geom.mesh import as_mesh_data
    from app.core.types import FeatureRef
    from app.ui.panels import _feature_item

    a, b = _manual_face_pair(window)
    window.show()
    tree = window.object_tree.tree
    window.object_tree.select_features((a, b))
    QApplication.processEvents()
    # Tatsächlicher Mehrfachklick mit der auf dieser Plattform vorgesehenen Taste.
    tree.clearSelection()
    for index, (object_id, feature_id) in enumerate((a, b)):
        parent = next(
            tree.topLevelItem(i)
            for i in range(tree.topLevelItemCount())
            if tree.topLevelItem(i).data(0, Qt.ItemDataRole.UserRole) == object_id
        )
        item = _feature_item(parent, feature_id)
        assert item is not None
        parent.setExpanded(True)
        tree.scrollToItem(item)
        QApplication.processEvents()
        QTest.mouseClick(
            tree.viewport(),
            Qt.MouseButton.LeftButton,
            Qt.KeyboardModifier.ControlModifier if index else Qt.KeyboardModifier.NoModifier,
            tree.visualItemRect(item).center(),
        )
    QApplication.processEvents()
    assert set(window.object_tree.selected_features()) == {a, b}
    document = window.session.project.document
    operations = tuple(document.ops)
    transaction_count = len(document.transactions)
    result = window.session.last_result
    assert result is not None
    before = {
        key: as_mesh_data(entry.mesh).raw.vertices.copy()
        for key, entry in result.scene.objects.items()
    }
    assert document.fits == []
    button = window.feature_panel._fit_button
    assert button is not None and button.isEnabled()
    window.session.evaluate_async()
    assert not button.isEnabled(), "der bestehende Knopf wird beim Start sichtbar gesperrt"
    assert window.session.wait_for_idle(30000)
    QApplication.processEvents()
    button = window.feature_panel._fit_button
    assert button is not None and button.isEnabled(), (
        "dieselbe Auswahl wird nach der Auswertung wieder nutzbar"
    )
    button.setFocus()
    QTest.keyClick(button, Qt.Key.Key_Space)
    QApplication.processEvents()
    assert window.session.wait_for_idle(30000)
    QApplication.processEvents()
    assert len(document.fits) == 1 and len(document.transactions) == transaction_count + 1
    fit = document.fits[0]
    assert {fit.a, fit.b} == {FeatureRef(*a), FeatureRef(*b)}
    assert fit.kind == "flush" and fit.tolerance == "auto:"
    assert tuple(document.ops) == operations
    result = window.session.last_result
    assert result is not None
    for key, entry in result.scene.objects.items():
        assert as_mesh_data(entry.mesh).raw.vertices == pytest.approx(before[key])
    assert any(finding.code == "fit.violated" for finding in result.scene.report.findings)
    destination = tmp_path / "manuelle-passung.p3d"
    window.session.save_project(destination)
    assert load(destination).document.fits == [fit]
    window.object_tree.select_features((b, a))
    QApplication.processEvents()
    assert window.feature_panel._fit_button is None
    assert any(fit.name in label.text() for label in window.feature_panel.findChildren(QLabel))
    assert window.session.undo() is not None
    assert window.session.wait_for_idle(30000)
    assert document.fits == [] and tuple(document.ops) == operations
    window.session.redo()
    assert window.session.wait_for_idle(30000)
    assert document.fits == [fit]


def test_queued_manual_fit_does_not_write_after_the_selection_changes(window: MainWindow) -> None:
    """Die Auskunft gehört zur damaligen Auswahl, auch bei einem bereits eingereihten Klick."""
    a, b = _manual_face_pair(window)
    window.object_tree.select_features((a, b))
    QApplication.processEvents()
    button = window.feature_panel._fit_button
    assert button is not None and button.isEnabled()
    button.click()
    window.object_tree.select_feature(*a)
    QApplication.processEvents()
    assert window.session.project.document.fits == []


def test_one_handling_for_all_alike_features_is_one_transaction(window: MainWindow) -> None:
    """Sechs Bohrungen auf ein Maß zu bringen war sechsmal derselbe Weg.

    Geprüft wird beides: dass **jede** Bohrung wandert und dass es **eine**
    Transaktion bleibt — ein Strg+Z nimmt sie zusammen zurück, weil es eine
    Handlung war (Regel 16). Sechs einzelne Aufrufe wären sechs Undos für einen
    Handgriff.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    holes = [identifier for identifier, feature in entry.features.items() if feature.kind == "hole"]
    assert len(holes) >= 2, "die Platte hat mehrere Bohrungen"
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, holes[0])
    QApplication.processEvents()
    vorher = len(window.session.project.document.transactions)

    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.relations import alike_for_action

    group = alike_for_action("resize_hole", holes[0], entry.features, as_mesh_data(entry.mesh))
    targets = [member.target for member in group.members]
    assert len(targets) >= 2
    window.feature_panel.operationRequestedForEach.emit(
        "resize_hole",
        {"at_feature": holes[0], "diameter": 6.5, "compensate": False},
        [*targets, "hole_missing"],
    )
    assert len(window.session.project.document.transactions) == vorher
    assert not any(op.op == "resize_hole" for op in window.session.project.document.ops)
    window.feature_panel.operationRequestedForEach.emit(
        "resize_hole", {"at_feature": holes[0], "diameter": 6.5, "compensate": False}, targets
    )
    window.session.wait_for_idle()

    schritte = [step.op for step in window.session.project.document.ops]
    assert schritte.count("resize_hole") == len(targets), "je belegter Bohrung ein Schritt"
    assert len(window.session.project.document.transactions) == vorher + 1, "und eine Handlung"
    danach = window.session.evaluate_now().scene.objects[object_id]
    gemessen = [
        round(float(danach.features[hole].params["diameter"]), 1)
        for hole in targets
        if hole in danach.features
    ]
    assert gemessen and all(abs(wert - 6.5) < 0.2 for wert in gemessen), gemessen


def test_applying_to_all_alike_holes_leaves_each_hole_where_it_is(window: MainWindow) -> None:
    """Durchmesser ändern, „auf alle anwenden" — und alle lagen übereinander.

    Das Merkmalfenster trägt beim Ändern einer Bohrung auch ihre Stelle x, y, z
    mit, und das Fenster gab sie als denselben Ort an jede Geschwisterbohrung
    (Robert, 16.09.2026: „alle sind übereinander"). Mitreisen darf das Maß;
    die Stelle gehört jedem Merkmal selbst. Verglichen werden die Mitten als
    Menge, nicht über die Kennungen: Ob eine Bohrung nach dem Ändern noch so
    heißt, ist hier nicht die Frage — dass sie noch dort sitzt, schon.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    holes = [identifier for identifier, feature in entry.features.items() if feature.kind == "hole"]
    assert len(holes) >= 2, "die Platte hat mehrere Bohrungen"
    centres_before = [
        tuple(float(value) for value in entry.features[hole].params["centre"]) for hole in holes
    ]
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, holes[0])
    QApplication.processEvents()

    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.relations import alike_for_action

    group = alike_for_action("resize_hole", holes[0], entry.features, as_mesh_data(entry.mesh))
    targets = [member.target for member in group.members]
    assert len(targets) >= 2
    x, y, z = centres_before[0]
    window.feature_panel.operationRequestedForEach.emit(
        "resize_hole",
        {"at_feature": holes[0], "diameter": 6.5, "compensate": False, "x": x, "y": y, "z": z},
        targets,
    )
    window.session.wait_for_idle()

    danach = window.session.evaluate_now().scene.objects[object_id]
    holes_after = [feature for feature in danach.features.values() if feature.kind == "hole"]
    assert len(holes_after) == len(holes), "keine Bohrung ist in einer anderen verschwunden"
    for before in centres_before:
        nearby = [
            feature
            for feature in holes_after
            if all(
                abs(float(a) - b) < 0.2
                for a, b in zip(feature.params["centre"], before, strict=True)
            )
        ]
        assert len(nearby) == 1, (before, "genau eine Bohrung sitzt noch an dieser Stelle")
    assert all(abs(float(feature.params["diameter"]) - 6.5) < 0.2 for feature in holes_after), (
        "und alle tragen das neue Maß"
    )


def test_a_face_offers_the_catalogue_from_the_panel(window: MainWindow) -> None:
    """Der Katalog aus der Fläche heraus — derselbe wie aus dem Objektbaum.

    Ein zweiter Weg dorthin, kein zweiter Katalog: Beide Signale hängen am
    selben Empfänger.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    face = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "face"
    )
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, face)
    QApplication.processEvents()

    from PySide6.QtWidgets import QPushButton

    knoepfe = [
        widget.text() for widget in window.feature_panel._built if isinstance(widget, QPushButton)
    ]
    assert knoepfe, "an der Fläche steht ein Weg statt vier grauer Zeilen"
    assert tr("Baustein einsetzen …") in knoepfe


def test_a_changed_number_previews_before_it_changes_anything(window: MainWindow) -> None:
    """Robert am 03.09.2026: „eine live vorschau wäre noch gut."

    Geprüft wird die Kette und ihre **Grenze**: Die Änderung wird gerechnet und
    gezeigt, und im Verlauf steht nichts. Eine Vorschau, die einen Schritt
    schreibt, wäre keine (Regel 2).
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)
    QApplication.processEvents()
    vorher = len(window.session.project.document.ops)

    window.feature_panel.valuesChanged.emit(
        "resize_hole", {"at_feature": hole, "diameter": 9.0, "compensate": False}
    )

    assert window._feature_preview.isActive(), "die Vorschau wartet, statt sofort zu rechnen"
    assert len(window.session.project.document.ops) == vorher, "und ändert nichts"

    gezeigt: list[object] = []
    window._show_preview = lambda difference: gezeigt.append(difference)  # type: ignore[method-assign]
    window._feature_preview.stop()
    window._preview_feature_change()
    window.session.wait_for_idle()
    QApplication.processEvents()

    assert gezeigt, "gerechnet, aber nichts gezeigt"
    assert len(window.session.project.document.ops) == vorher, "auch danach kein Schritt"


def test_choosing_another_feature_drops_the_waiting_preview(window: MainWindow) -> None:
    """Eine Vorschau gehört zu dem Merkmal, an dem sie entstand.

    Ohne das Vergessen zeigte der nächste Klick eine Änderung an etwas, das
    nicht mehr gewählt ist — und der Kunde sieht ein Teil, das er nicht
    angefasst hat.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    holes = [identifier for identifier, feature in entry.features.items() if feature.kind == "hole"]
    assert len(holes) >= 2, "die Platte hat mehrere Bohrungen"
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, holes[0])
    QApplication.processEvents()
    window.feature_panel.valuesChanged.emit("resize_hole", {"at_feature": holes[0]})
    assert window._feature_preview.isActive()

    window.object_tree.select_feature(object_id, holes[1])
    QApplication.processEvents()

    assert not window._feature_preview.isActive(), "die wartende Vorschau ist weg"
    assert window._feature_pending is None, "und ihr Merkposten auch"


def test_cancel_in_the_feature_panel_drops_the_waiting_preview_and_restores_the_fields(
    window: MainWindow,
) -> None:
    """*Abbrechen* steht, solange eine Feldvorschau wartet — und nimmt sie zurück.

    Seit dem 20.09.2026 trägt die Maßgruppe im Bild Übernehmen und Abbrechen
    selbst, und der Knopf im Merkmalfenster hatte keinen Ort mehr: sichtbar
    nur beim Messen, beim Messen verborgen (gemessen am 21.09.2026). Wer eine
    Zahl getippt hatte und sie nicht wollte, kam nur über Escape aus der
    Auswahl heraus. Jetzt steht er neben Übernehmen, solange die Vorschau aus
    dem Panel wartet; ein Klick verwirft sie, und das Feld zeigt wieder, was
    der Schritt trägt — ohne Schritt im Verlauf und ohne Rückfrage (Regel 19).
    """
    from app.ui.labels import LengthSpin

    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(name for name, feature in entry.features.items() if feature.kind == "hole")
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)
    QApplication.processEvents()
    panel = window.feature_panel
    # ``isHidden`` statt ``isVisibleTo``: Die Knopfzeile wohnt beim Träger
    # unter dem Rollbereich (``footer``), nicht mehr im Panel selbst.
    assert panel._cancel.isHidden(), "ohne wartende Vorschau steht kein Abbrechen"
    before = len(window.session.project.document.ops)

    field = next(
        spin
        for spin in panel.findChildren(LengthSpin)
        if "Bohrung ändern" in spin.accessibleName() and "Durchmesser" in spin.accessibleName()
    )
    original = field.value_mm()
    field.set_value_mm(original + 1.0)
    QApplication.processEvents()
    assert window._feature_preview.isActive() or window._preview_approval is not None
    assert not panel._cancel.isHidden(), "eine wartende Vorschau bietet Abbrechen an"

    panel._cancel.click()
    QApplication.processEvents()
    assert window.session.wait_for_idle(30_000)
    # Die alten Zeilen gehen über ``deleteLater`` — erst zustellen, sonst
    # findet die Suche unten das getippte Feld von vorhin.
    QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()

    assert not window._feature_preview.isActive(), "die wartende Vorschau ist weg"
    assert window._feature_pending is None
    # Das neu gezeigte Merkmal bindet wieder den Auftrag seines Schritts —
    # angefordert ist davon nichts.
    assert window._preview_approval is None or not window._preview_approval.requested
    assert len(window.session.project.document.ops) == before, "verworfen heißt: kein Schritt"
    restored = next(
        spin
        for spin in panel.findChildren(LengthSpin)
        if "Bohrung ändern" in spin.accessibleName() and "Durchmesser" in spin.accessibleName()
    )
    assert restored.value_mm() == pytest.approx(original), "das Feld zeigt wieder den Schritt"
    assert panel._cancel.isHidden(), "und Abbrechen geht mit der Vorschau"


def test_applying_drops_the_waiting_preview_too(window: MainWindow) -> None:
    """Der Zwilling zu ``test_choosing_another_feature_drops_the_waiting_preview``.

    Das Abwählen räumte die wartende Vorschau ab, das **Anwenden** nicht: Der
    Zeitgeber lief nach dem Übernehmen weiter und rechnete eine Änderung, die
    schon im Verlauf stand. ``session.apply`` dreht die Vorschau-Generation
    ebenfalls nicht weiter, ein schon rechnender Arbeiter legt sein Ergebnis
    also über das fertige Teil.

    Beide Anwenden-Wege werden geprüft — der einzelne und der für alle
    gleichartigen. Ein Weg, der nur an einer von zwei Stellen abräumt, ist
    derselbe Fehler noch einmal (gemeldet von 3d-druck-85, 03.09.2026).
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    holes = [identifier for identifier, feature in entry.features.items() if feature.kind == "hole"]
    assert len(holes) >= 2, "die Platte hat mehrere Bohrungen"
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, holes[0])
    QApplication.processEvents()

    values = {"at_feature": holes[0], "diameter": 9.0, "compensate": False}
    window.feature_panel.valuesChanged.emit("resize_hole", values)
    assert window._feature_preview.isActive(), "Voraussetzung: die Vorschau wartet"

    # **Sie muss auch wirklich im Bild stehen.** Ein bloß scharfer Zeitgeber
    # zeichnet nichts, und eine Zusicherung über ein Bild, das es nie gab, ist
    # immer grün — gemessen am 03.09.2026, der erste Anlauf dieses Tests war
    # genau so leer.
    window._feature_preview.stop()
    window._preview_feature_change()
    window.session.wait_for_idle()
    QApplication.processEvents()
    assert window.viewport.difference is not None, "Voraussetzung: die Differenz liegt im Bild"
    assert window.viewport._comparing, "Voraussetzung: das Band steht, der Filter hängt"
    window.feature_panel.valuesChanged.emit("resize_hole", values)

    window._apply_from_feature_panel("resize_hole", values)
    window.session.wait_for_idle()
    QApplication.processEvents()

    assert not window._feature_preview.isActive(), "nach dem Übernehmen wartet nichts mehr"
    assert window._feature_pending is None, "und der Merkposten ist leer"
    # Eine abgebrochene Rechnung nimmt nicht weg, was schon gezeichnet ist.
    assert window.viewport.difference is None, (
        "der Differenzkörper der Vorschau liegt nicht mehr da"
    )
    assert not window.viewport._comparing, (
        "mit dem Band geht der anwendungsweite Filter — sonst blendet die Leertaste überall um"
    )

    window.object_tree.select_feature(object_id, holes[1])
    QApplication.processEvents()
    window.feature_panel.valuesChanged.emit("resize_hole", {**values, "at_feature": holes[1]})
    assert window._feature_preview.isActive(), "Voraussetzung für den zweiten Weg"

    # Denselben Weg wie die Merkmalsleiste: das gewählte Merkmal steht in
    # ``at_feature``, die Ziele sind die Gruppe, die das Fenster beim Anbieten
    # gebildet hat — sonst hält das Fenster die Gruppe für geändert und wendet
    # nichts an (Gesamtreview 05.09.2026).
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.relations import alike_for_action

    body = window.session.last_result.scene.objects[object_id]
    group = alike_for_action("resize_hole", holes[1], body.features, as_mesh_data(body.mesh))
    targets = [member.target for member in group.members]
    assert holes[1] in targets, "Voraussetzung: die gewählte Bohrung gehört zu ihrer Gruppe"
    window._apply_to_each_feature(
        "resize_hole",
        {"at_feature": holes[1], "diameter": 9.5, "compensate": False},
        targets,
    )
    window.session.wait_for_idle()
    QApplication.processEvents()

    assert not window._feature_preview.isActive(), "auch der Weg über alle gleichartigen räumt ab"
    assert window._feature_pending is None
    assert window.viewport.difference is None
    assert not window.viewport._comparing


def _a_drawn_preview(window: MainWindow) -> tuple[str, str]:
    """Eine Vorschau, die wirklich im Bild steht — Voraussetzung dreier Tests.

    Ein bloß scharfer Zeitgeber zeichnet nichts, und eine Zusicherung über ein
    Bild, das es nie gab, ist immer grün.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)
    QApplication.processEvents()

    values = {"at_feature": hole, "diameter": 12.0, "compensate": False}
    window.feature_panel.valuesChanged.emit("resize_hole", values)
    window._feature_preview.stop()
    window._preview_feature_change()
    window.session.wait_for_idle()
    QApplication.processEvents()
    assert window.viewport.difference is not None, "Voraussetzung: die Differenz liegt im Bild"
    assert window.viewport._comparing, "Voraussetzung: das Band steht, der Filter hängt"
    window.feature_panel.valuesChanged.emit("resize_hole", values)
    return object_id, hole


def test_closing_the_feature_window_takes_its_preview_along(window: MainWindow) -> None:
    """Wer das Fenster zumacht, hat keinen Ort mehr, die Änderung zu übernehmen.

    Gemessen am 03.09.2026: Nach dem Zumachen blieben **alle sechs** Zustände
    stehen — Zeitgeber, Merkposten, Differenzkörper, Band, Filter und die
    Zeilen. Der Differenzkörper lag über dem Teil, das Band sagte „noch nicht
    übernommen", und der anwendungsweite Filter bog die Leertaste um. Sichtbar
    war das Fenster, an dem man beides hätte auflösen können, gerade nicht
    mehr.
    """
    _a_drawn_preview(window)

    _close_the_feature_window(window)

    assert window.viewport.difference is None, "der Differenzkörper geht mit"
    assert not window.viewport._comparing, "und der anwendungsweite Filter auch"
    assert not window._feature_preview.isActive()
    assert window._feature_pending is None


def test_the_start_screen_cut_takes_the_preview_along(window: MainWindow) -> None:
    """*Datei → Neu* ist der härteste Schnitt, den die Anwendung hat.

    Eine Vorschau überlebt ihn nicht: Beim nächsten geöffneten Projekt läge sie
    über der neuen Szene, mit einem Band, das von einer Änderung spricht, die
    es dort nie gab. ``start_empty`` ist mitgedeckt — es hängt am Hauptknopf
    des Startbildschirms und ist nur von dort erreichbar.
    """
    _a_drawn_preview(window)

    window.action_new()
    QApplication.processEvents()

    assert window.viewport.difference is None
    assert not window.viewport._comparing
    assert window._feature_pending is None


def test_a_feature_the_new_scene_does_not_know_leaves_the_window(window: MainWindow) -> None:
    """Der übersehene Zwilling von ``self._hidden &= set(result.scene.objects)``.

    Zwei Zeilen darüber vergisst ``_show_scene`` ausgeblendete Objekte, die es
    nicht mehr gibt — „sonst blendet eine wiederhergestellte Nummer später
    etwas aus, das niemand versteckt hat". Für das Merkmalsfenster galt
    dasselbe und stand nicht da: Seine Knöpfe zeigten auf ein Merkmal, das die
    Szene nicht mehr enthält.

    Geprüft und nicht pauschal geleert — nach einem Übernehmen lebt dasselbe
    Merkmal weiter, und dann soll das Fenster stehenbleiben.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)
    QApplication.processEvents()
    assert window.feature_panel.feature_id == hole, "Voraussetzung: das Fenster zeigt die Bohrung"

    # **Über die Sitzung und nicht über ``start_empty``.** Der Knopf des
    # Startbildschirms fragt vorher, ob das geänderte Projekt weggeworfen
    # werden darf (Regel 19 erlaubt die Frage, weil kein Undo ein verworfenes
    # Dokument zurückholt) — und ein modaler Dialog wartet im Testlauf ewig.
    # Der Lauf blieb daran zweimal stehen, ohne eine Zeile Ausgabe.
    #
    # Geprüft wird der Zustandswechsel, und der ist derselbe: ``start_empty``
    # ruft genau das hier, sobald die Frage beantwortet ist.
    window.session.start_new(window.settings.printer, window.settings.material)
    window.session.wait_for_idle()
    QApplication.processEvents()

    assert window.feature_panel.feature_id is None, "das Merkmal gibt es dort nicht mehr"
    assert not window.feature_panel._built, "und seine Zeilen stehen nicht mehr da"


def test_saving_keeps_the_mark_on_the_step_that_stopped(window: MainWindow) -> None:
    """Strg+S löschte das Ausrufezeichen vor dem hängenden Schritt.

    ``_show_scene`` reicht ``result.stopped_at`` an den Verlauf weiter, der Weg
    über ``projectChanged`` nicht — und Speichern meldet einen Dokumentwechsel
    **ohne** nachfolgende Auswertung. Danach stand der Verlauf ohne Marke da,
    während Statuszeile und Prüfbericht weiter sagten, die Kette halte an
    (§15.3, gefunden von 3d-druck-85, 03.09.2026).

    **Geprüft wird die Weitergabe, nicht das Bild.** Der Verlauf bekommt seine
    Marke als Argument; fehlt sie dort, kann er sie nicht zeichnen. Ein Aufbau
    mit einer wirklich angehaltenen Kette wäre der schönere Test, aber er
    braucht eine Operation, die scheitert — und der Lauf dazu blieb in dieser
    Datei zweimal stehen, ohne dass die Ursache am Fenster lag. Ein Test, der
    nicht durchläuft, hält nichts fest.

    Der Weg selbst ist echt: ``projectChanged`` ist das Signal, das Speichern
    aussendet, und ``_on_project`` ist, was daran hängt.
    """
    seen: list[Any] = []
    window.history_panel.show_document = (  # type: ignore[method-assign]
        lambda document, stopped_at=None, undone=(): seen.append(stopped_at)
    )

    window.session.projectChanged.emit()
    QApplication.processEvents()
    assert seen == [None], f"ohne angehaltene Kette keine Marke — {seen}"

    result = window.session.evaluate_now()
    window.session.last_result = dataclasses.replace(result, stopped_at=7)
    seen.clear()
    window.session.projectChanged.emit()
    QApplication.processEvents()

    assert seen == [7], f"die Marke des angehaltenen Schritts kommt an — {seen}"


def test_every_selected_body_lights_up_not_just_the_first(window: MainWindow) -> None:
    """Das Bild zeigte einen, die Statuszeile sagte zwei, der Zug bewegte beide.

    ``_on_selection`` reichte ``object_tree.selected()`` an den Viewport — die
    Kennung des **ersten** Eintrags —, während die Zahlenzeile drei Zeilen
    weiter unten mit ``selected_objects()`` rechnet und
    ``inputs_for_transform`` dieselbe Menge zurückgibt. Von den drei Auskünften
    log genau eine, und es war die einzige, die der Kunde ansieht (gefunden von
    3d-druck-85, 03.09.2026).

    Dass alle bewegt werden, ist die Entscheidung und bleibt. Falsch war das
    Bild.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    QApplication.processEvents()
    bodies = list(window.session.last_result.scene.objects)
    assert len(bodies) >= 2, f"Voraussetzung: mehrere Körper — {bodies}"

    tree = window.object_tree.tree
    for row in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(row)
        assert item is not None
        item.setSelected(True)
    QApplication.processEvents()

    chosen = window.object_tree.selected_objects()
    assert len(chosen) >= 2, f"Voraussetzung: der Baum hat mehrere gewählt — {chosen}"
    assert set(window.viewport.highlighted_objects()) == set(chosen), (
        "das Bild zeigt genau die gewählten Körper, nicht nur den ersten"
    )


def test_delete_removes_the_feature_not_the_body(window: MainWindow) -> None:
    """Robert am 03.09.2026: „wenn wir ein merkmal auswählen und auf der
    tastatur entf drück löschen wir den ganzen körper statt das merkmal."

    Die Weiche sitzt in ``run_operation``, also an der **einen** Stelle, durch
    die Taste, Menüeintrag und Befehlspalette laufen. Gemessen wird beides:
    dass die Bohrung verschwindet **und** dass der Körper bleibt — nur zusammen
    sagen sie, dass die richtige Operation gelaufen ist.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)

    window.run_operation(REGISTRY.get("delete_object"))
    window.session.wait_for_idle()

    assert [step.op for step in window.session.project.document.ops] == ["load", "remove_feature"]
    scene = window.session.evaluate_now().scene.objects
    assert object_id in scene, "der Körper bleibt stehen"
    assert hole not in scene[object_id].features, "die Bohrung ist weg"


def test_delete_without_a_feature_still_takes_the_body(window: MainWindow) -> None:
    """Die Gegenprobe: Ohne gewähltes Merkmal bleibt Entf, was es war.

    Eine Weiche, die alles einfängt, wäre von einer, die richtig trennt, am
    Test darüber nicht zu unterscheiden.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id = next(iter(result.scene.objects))
    window.object_tree.select_object(object_id)

    assert window.feature_instead_of("delete_object") is None
    window.run_operation(REGISTRY.get("delete_object"))
    window.session.wait_for_idle()

    assert [step.op for step in window.session.project.document.ops] == ["load", "delete_object"]


def test_the_feature_panel_is_a_window_of_its_own(window: MainWindow) -> None:
    """Robert am 03.09.2026: „ein extra panel nicht die bestehenden erweitern."

    Es hing zuerst als Abschnitt in der linken Spalte. Jetzt ist es ein Dock:
    eigener Titel, abziehbar, mit einem Schalter im Ansichtsmenü — und die
    linke Spalte ist wieder die, die sie war.
    """
    from PySide6.QtWidgets import QDockWidget, QPushButton

    dock = window.feature_dock
    assert isinstance(dock, QDockWidget)
    assert dock.widget() is not None, "das Panel steckt darin"
    assert dock.features() & QDockWidget.DockWidgetFeature.DockWidgetFloatable, "abziehbar"
    assert window.feature_panel in dock.findChildren(type(window.feature_panel))

    beschriftungen = [
        knopf.text().replace("&", "")
        for knopf in window.findChildren(QPushButton)
        if knopf.parent() is not None
    ]
    assert tr("Merkmal") not in beschriftungen, "kein Abschnitt mehr in der linken Spalte"


def test_a_drag_on_a_feature_becomes_a_feature_step(window: MainWindow) -> None:
    """Der Zug am Griff trifft das Merkmal, nicht sein Teil (§18.11).

    Die Ansicht rechnet die Zielmitte selbst und schickt sie **absolut**; das
    Fenster macht daraus einen Schritt. Geprüft wird die Naht zwischen beiden —
    dass ein Signal einen Empfänger hat, fällt in keinem Test auf, der nur den
    Sender prüft.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    centre = entry.features[hole].params["centre"]
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)

    ziel = (float(centre[0]) + 4.0, float(centre[1]), float(centre[2]))
    window.viewport.featureMoved.emit(hole, ziel)
    window.session.wait_for_idle()

    assert [step.op for step in window.session.project.document.ops] == ["load", "move_feature"]
    letzter = window.session.project.document.ops[-1]
    assert letzter.params["at_feature"] == hole
    assert float(letzter.params["x"]) == pytest.approx(ziel[0]), "die Mitte kommt absolut an"


def test_a_turn_on_a_feature_keeps_the_settled_angle(window: MainWindow) -> None:
    """Der Winkel kommt **gerastet** aus der Ansicht — sie kennt den Fang, das
    Fenster nicht. Nachgerechnet wird hier nichts."""
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)

    window.viewport.featureTurned.emit(hole, "x", 45.0)
    window.session.wait_for_idle()

    steps = [step.op for step in window.session.project.document.ops]
    assert steps == ["load", "rotate_feature"]
    letzter = window.session.project.document.ops[-1]
    assert letzter.params["at_feature"] == hole
    assert letzter.params["axis"] == "x"
    assert float(letzter.params["angle"]) == pytest.approx(45.0), "unverändert weitergereicht"


def test_a_drag_on_the_slot_knobs_becomes_one_slot_step(window: MainWindow) -> None:
    """Die dritte Naht derselben Bauart: aus dem Zug wird *Zum Langloch ziehen*.

    Länge und Richtung kommen fertig aus der Ansicht — sie hat den Zug auf der
    Mündungsebene der Bohrung gerechnet und kennt deren Rahmen. Das Fenster
    rechnet nichts nach; es macht daraus **einen** Schritt, und ein Undo nimmt
    ihn ganz zurück (§15.5).
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)

    # Das vierte Argument ist die Stelle — ``None``, wenn das Loch bleibt, wo
    # es ist; ein Zug am Bewegungsgriff, der zusammen mit dem Langlochzug
    # wartet, gibt sie mit (11.09.2026).
    window.viewport.slotDragged.emit(hole, 18.0, 30.0, None)
    window.session.wait_for_idle()

    assert [step.op for step in window.session.project.document.ops] == ["load", "slot_hole"]
    letzter = window.session.project.document.ops[-1]
    assert letzter.params["at_feature"] == hole
    assert float(letzter.params["slot_length"]) == pytest.approx(18.0)
    assert float(letzter.params["slot_angle"]) == pytest.approx(30.0)
    assert all(float(letzter.params.get(axis) or 0.0) == 0.0 for axis in ("x", "y", "z")), (
        "ohne Stelle bleibt das Loch, wo es ist — drei Nullen heißen das"
    )


def test_the_panel_sends_a_feature_into_the_view_without_changing_it(window: MainWindow) -> None:
    """``inViewRequested`` zeigt — es legt keinen Schritt an (10.09.2026).

    ``operationRequested`` führt aus, dieses bringt die Flächenplatzierung
    mit ihren Maßlinien in die Szene. Wer beide Signale gleich behandelte,
    schriebe schon beim Zeigen in den Verlauf — deshalb sind es zwei.

    **Und seit dem 11.09.2026 ohne Dialog.** Getragen wird die Platzierung
    von einem ``QuietHost``: Er hält die Werte und zeigt nichts, weil sie
    rechts im Merkmalfenster schon stehen (Robert: „werte im dialog und in
    der rechten merkmalleiste doppelt"). Geprüft wird deshalb der Träger und
    nicht mehr ein Fenster — die Zusage „gezeigt, nicht getan" ist dieselbe.
    """
    # **Die Betriebslage, nicht der Nullzustand** (`.claude/rules/tests.md`):
    # Ohne Renderer sagt `PlacementFlow.can_place()` nein, und offscreen gibt
    # es nie einen. Die Attrappe stellt her, was der Kunde hat.
    from tests.render_fakes import RecordingRenderer

    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    centre = entry.features[hole].params["centre"]
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)

    durchmesser = float(entry.features[hole].params["diameter"])
    window.feature_panel.inViewRequested.emit(
        "resize_hole", {"at_feature": hole, "diameter": durchmesser}
    )
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()

    try:
        assert not window.findChildren(OperationDialog), "es geht kein Dialog mehr auf"
        host = window._quiet_host
        assert host is not None, "die Platzierung hat ihren Träger"
        assert [step.op for step in window.session.project.document.ops] == ["load"], (
            "gezeigt, nicht getan — im Verlauf steht nichts Neues"
        )
        assert host.values().get("at_feature") == hole, "und er weiß, welches Merkmal"

        # **Und das Verschieben geht denselben Weg**, mit demselben Merkmal:
        # Es stellt seine Stelle ebenfalls auf einer Fläche ein. Bis zum
        # 11.09.2026 verlor es dabei die Kennung — `surface_values` gab sie
        # nur für zwei Operationen zurück und leerte sie sonst, und ohne sie
        # fand `_source_feature` das Merkmal nicht mehr.
        window.feature_panel.inViewRequested.emit(
            "move_feature",
            {
                "at_feature": hole,
                "x": float(centre[0]),
                "y": float(centre[1]),
                "z": float(centre[2]),
            },
        )
        window.session.wait_for_idle()
        for _ in range(40):
            QApplication.processEvents()
        zweiter = window._quiet_host
        assert zweiter is not None and zweiter is not host, "eine frische Platzierung"
        assert zweiter.values().get("at_feature") == hole, "auch sie behält ihr Merkmal"
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()


@pytest.mark.parametrize(
    "selection", ["other_feature", "other_body", "same", "none", "project", "evaluation"]
)
def test_a_feature_placement_stays_with_its_selected_place(
    window: MainWindow, selection: str
) -> None:
    """Eine neue Auswahl übernimmt keine wartende Änderung der vorherigen Stelle."""
    from app.ui.labels import LengthSpin
    from tests.render_fakes import RecordingRenderer

    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    window.open_path(MESHES / "plate_holes.stl")
    assert window.session.wait_for_idle(30_000)
    if selection == "other_body":
        window.session.import_model(MESHES / "plate_holes.stl")
        assert window.session.wait_for_idle(30_000)
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    holes = [name for name, feature in entry.features.items() if feature.kind == "hole"]
    assert len(holes) >= 2
    window.object_tree.select_feature(object_id, holes[0])
    panel = window.feature_panel
    panel._in_view.click()
    assert window.session.wait_for_idle(30_000)
    for _ in range(40):
        QApplication.processEvents()
    flow, host = window._quiet_placement, window._quiet_host
    assert flow is not None and flow.active and flow._accept.isEnabled()
    assert host is not None
    before = len(window.session.project.document.ops)

    selected_object, selected_hole = object_id, holes[0]
    if selection == "other_feature":
        selected_hole = holes[1]
    elif selection == "other_body":
        selected_object = next(name for name in result.scene.objects if name != object_id)
        assert selected_hole in result.scene.objects[selected_object].features
    elif selection == "project":
        window.session.start_new()
        window.session.import_model(MESHES / "plate_holes.stl")
        assert window.session.wait_for_idle(30_000)
    elif selection == "evaluation":
        window.session.evaluate_now()
    if selection == "none":
        window.object_tree.select_object(None)
    else:
        window.object_tree.select_feature(selected_object, selected_hole)
    QApplication.processEvents()

    if selection == "same":
        assert window._quiet_placement is flow and flow.active
        assert window._quiet_host is host
        assert len(window.session.project.document.ops) == before
    else:
        assert not flow.active, "die Maßlinien der vorigen Stelle werden abgeräumt"
        host.accept()
        assert len(window.session.project.document.ops) == before, "der alte Rückruf ist ungültig"
        if selection in ("none", "project", "evaluation"):
            return
    # Die neue Auswahl zeigt ihre Maße von selbst im Bild, und dort trägt die
    # Maßgruppe das Übernehmen; geprüft wird hier der Weg über das Panel —
    # also die Maße beenden, dann tippen, Vorschau abwarten, übernehmen.
    window.end_quiet_placement()
    diameter = next(
        field
        for field in panel.findChildren(LengthSpin)
        if field.isVisibleTo(panel)
        and "Bohrung ändern" in field.accessibleName()
        and "Durchmesser" in field.accessibleName()
    )
    diameter.set_value_mm(diameter.value_mm() + 0.5)
    window._feature_preview.stop()
    window._preview_feature_change()
    assert window.session.wait_for_idle(30_000)
    for _ in range(40):
        QApplication.processEvents()
    panel._apply.click()
    assert window.session.wait_for_idle(30_000)
    step = window.session.project.document.ops[-1]
    assert len(window.session.project.document.ops) == before + 1
    assert step.op == "resize_hole"
    assert tuple(step.inputs) == (selected_object,)
    assert step.params["at_feature"] == selected_hole


def _hole_fields_in_placement(window: MainWindow) -> tuple[str, str, Any, dict[str, Any]]:
    """Eine Bohrung mit echten Maßfeldern und einer vorbereiteten Bildplatzierung."""
    from app.ui.labels import LengthSpin
    from tests.render_fakes import RecordingRenderer

    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    window.open_path(MESHES / "plate_holes.stl")
    assert window.session.wait_for_idle(30_000)
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(name for name, feature in entry.features.items() if feature.kind == "hole")
    window.object_tree.select_feature(object_id, hole)
    window.feature_panel._in_view.click()
    assert window.session.wait_for_idle(30_000)
    for _ in range(40):
        QApplication.processEvents()
    flow = window._quiet_placement
    assert flow is not None and flow.active and flow._accept.isEnabled()
    # Stehen die Maße im Bild, gehören Felder und Abschluss der Maßgruppe
    # (20.09.2026): Die Gegenstücke im Panel sind gesperrt, sein Übernehmen
    # verborgen — getippt und übernommen wird in der Gruppe.
    assert flow._measure_group is not None
    fields = {
        field.accessibleName().rsplit(" — ", 1)[-1]: field
        for field in flow._measure_group.findChildren(LengthSpin)
        if "Bohrung ändern" in field.accessibleName()
    }
    # Ein Entwurf beginnt mit einer Geste — Klick, Tab oder Taste im Feld —,
    # nicht mit seiner Anzeige; ``set_value_mm`` ist keine. Offscreen trägt
    # kein Fokus, ein Tastendruck kommt an: Ende im Feld ändert nichts und
    # ist die Geste, die der Kunde macht, bevor er tippt.
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    QTest.keyClick(next(iter(fields.values())).lineEdit(), Qt.Key.Key_End)
    QApplication.processEvents()
    return object_id, hole, flow, fields


def test_a_refused_measure_stays_blocked_after_focus_moves(window: MainWindow) -> None:
    """Ein zweites Maßfeld darf eine abgelehnte Zahl weder überschreiben noch übernehmen."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    _object_id, _hole, flow, fields = _hole_fields_in_placement(window)
    diameter = fields["Durchmesser"]
    _minimum, _maximum = diameter._bounds_mm
    limit = diameter.value_mm() + 1.0
    diameter.set_range_mm(_minimum, limit)
    line = diameter.lineEdit()
    line.setFocus()
    line.selectAll()
    QTest.keyClicks(line, diameter.textFromValue(limit + 5.0))
    refused_text = line.text()
    refusal = diameter.refusal()
    assert refusal and "Obergrenze" in refusal, refusal

    other = fields["X"]
    other.lineEdit().setFocus()
    QTest.keyClick(other.lineEdit(), Qt.Key.Key_End)
    QApplication.processEvents()
    assert not line.isModified(), (
        "Fokuswechsel stellt die ungültige Zahl ohne Änderungsmarke wieder her"
    )
    assert line.text() == refused_text, "der Wechsel zu einem zweiten Feld lässt den Text stehen"
    assert flow.dialog.blocked_reason == refusal
    assert not flow._measure_accept.isEnabled(), "der Grenzsatz sperrt Übernehmen sofort"

    before = len(window.session.project.document.ops)
    other.set_value_mm(other.value_mm() + 0.5)
    QApplication.processEvents()
    flow._measure_accept.click()
    assert line.text() == refused_text
    assert len(window.session.project.document.ops) == before, "die alte Zahl wird nicht übernommen"

    line.setFocus()
    line.selectAll()
    QTest.keyClicks(line, diameter.textFromValue(limit))
    QApplication.processEvents()
    assert diameter.refused_value() is None
    assert flow.dialog.blocked_reason is None


def test_a_refused_measure_expression_blocks_accept_and_survives_refresh(
    window: MainWindow,
) -> None:
    """Ein fx-Ausdruck in der Maßgruppe bleibt auch ohne Spinbox sichtbar gesperrt."""
    from types import SimpleNamespace

    from app.ui.labels import LengthSpin
    from app.ui.op_dialog import ValueField
    from tests.render_fakes import RecordingRenderer

    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    window.open_path(MESHES / "plate_holes.stl")
    assert window.session.wait_for_idle(30_000)
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(name for name, feature in entry.features.items() if feature.kind == "hole")
    window.object_tree.select_feature(object_id, hole)
    for _ in range(40):
        QApplication.processEvents()

    spec = REGISTRY.get("drill_hole")
    step = SimpleNamespace(id=17, op="drill_hole", params={"diameter": "=@bore"})
    window.feature_panel.offer_bore_step(step, spec, {"bore": 6.0})
    window._place_measures("drill_hole", {"diameter": "=@bore"}, editing=False)
    for _ in range(40):
        QApplication.processEvents()

    flow = window._quiet_placement
    assert flow is not None and flow.active and flow._measure_group is not None
    diameter = next(
        editor
        for editor in flow._measure_group.findChildren(ValueField)
        if editor._entry.name == "diameter"
    )
    other = next(
        editor
        for editor in flow._measure_group.findChildren(LengthSpin)
        if editor.accessibleName().endswith("Tiefe")
    )
    window.show()
    QApplication.processEvents()
    line = diameter.text
    line.setFocus()
    line.setText("=@bore*100")
    QApplication.processEvents()
    refused_text = line.text()
    refusal = diameter.refusal()
    assert refusal and "Obergrenze" in refusal, refusal
    assert flow.dialog.blocked_reason == refusal
    assert not flow._measure_accept.isEnabled()

    other.lineEdit().setFocus()
    QApplication.processEvents()
    assert not line.hasFocus()
    before = len(window.session.project.document.ops)
    flow.accept()
    QApplication.processEvents()
    assert line.hasFocus(), "Übernehmen führt zurück zum fx-Text, das die Grenze verletzt"
    assert flow.dialog.values()["diameter"] == "=@bore", "der Ausdruck gelangt nicht in den Träger"
    assert len(window.session.project.document.ops) == before

    other.lineEdit().setFocus()
    line.setModified(False)
    flow.dialog.take_placement({"depth": other.value_mm() + 0.5})
    QApplication.processEvents()
    assert line.text() == refused_text, (
        "ein Rückschreiben überschreibt den abgelehnten Ausdruck nicht"
    )
    assert flow.dialog.blocked_reason == refusal
    window.end_quiet_placement()


def test_the_measures_in_the_view_take_their_twins_out_of_the_panel(window: MainWindow) -> None:
    """Was im Bild steht, steht rechts nicht noch einmal (Robert, 21.09.2026, RM-199).

    „durchmesser ist ja im viewport, kann im merkmalpanel entfernt werden":
    Solange die Maßgruppe an der gewählten Bohrung steht, fielen Durchmesser,
    Umfang und Koordinaten von *Bohrung ändern* rechts bisher nur in die
    Sperre — zwei Stellen für dieselbe Zahl, von denen eine nichts annahm. Jetzt
    geht der Block mit dem Messen und kommt mit seinem Ende zurück; die übrigen
    Handlungen des Merkmals bleiben, wo sie waren.
    """
    from app.ui.labels import LengthSpin
    from tests.render_fakes import RecordingRenderer

    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    window.open_path(MESHES / "plate_holes.stl")
    assert window.session.wait_for_idle(30_000)
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(name for name, feature in entry.features.items() if feature.kind == "hole")
    window.object_tree.select_feature(object_id, hole)
    for _ in range(40):
        QApplication.processEvents()
    panel = window.feature_panel

    def shown() -> set[str]:
        return {
            field.accessibleName()
            for field in panel.findChildren(LengthSpin)
            if field.isVisibleTo(panel)
        }

    flow = window._quiet_placement
    assert flow is not None and flow.active and panel._measuring, "die Maße stehen im Bild"
    assert flow._measure_group is not None
    in_view = {
        field.accessibleName()
        for field in flow._measure_group.findChildren(LengthSpin)
        if "Bohrung ändern" in field.accessibleName()
    }
    assert "Bohrung ändern — Durchmesser" in in_view, "der Durchmesser steht im Bild"
    assert not any("Bohrung ändern" in name for name in shown()), (
        "rechts steht kein Zwilling davon: " + ", ".join(sorted(shown()))
    )
    assert any("Merkmal verschieben" in name for name in shown()), "die übrigen Handlungen bleiben"

    window.end_quiet_placement()
    for _ in range(10):
        QApplication.processEvents()

    assert not panel._measuring
    assert {"Bohrung ändern — Durchmesser", "Bohrung ändern — X"} <= shown(), (
        "mit dem Ende des Messens stehen die Felder wieder rechts"
    )


def test_the_next_hole_hides_its_twins_too_and_the_end_brings_them_back(
    window: MainWindow,
) -> None:
    """RM-199 mit der nächsten Bohrung und dem Ende der Maße.

    Die Abnahme aus dem Register: Bohrung wählen, rechts kein Durchmesser und
    keine Koordinaten; endet die Maßgruppe, stehen sie wieder. Seit das
    Merkmalfenster seine Zeilen von Bohrung zu Bohrung weiterverwendet
    (RM-204), wandert dabei eine Zeile, die gerade als Zwilling versteckt war
    — sie muss an der nächsten Bohrung wieder weichen und danach wieder
    dastehen. Bis zum 25.09.2026 war Escape dieser Ausgang; seither wählt es
    ab wie *Abbrechen* (Entscheidung Robert), und rechts steht nichts mehr.
    """
    from app.ui.labels import LengthSpin
    from tests.render_fakes import RecordingRenderer

    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    window.open_path(MESHES / "plate_holes.stl")
    assert window.session.wait_for_idle(30_000)
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    holes = [name for name, feature in entry.features.items() if feature.kind == "hole"]
    panel = window.feature_panel

    def shown() -> set[str]:
        return {
            field.accessibleName()
            for field in panel.findChildren(LengthSpin)
            if field.isVisibleTo(panel)
        }

    for hole in holes[:2]:
        window.object_tree.select_feature(object_id, hole)
        for _ in range(40):
            QApplication.processEvents()
        assert panel.feature_id == hole
        assert window._quiet_placement is not None and panel._measuring
        assert not any("Bohrung ändern" in name for name in shown()), sorted(shown())
        assert any("Merkmal verschieben" in name for name in shown())

    window.end_quiet_placement()
    for _ in range(10):
        QApplication.processEvents()

    assert window._quiet_placement is None and not panel._measuring
    assert {"Bohrung ändern — Durchmesser", "Bohrung ändern — X"} <= shown(), sorted(shown())

    window.object_tree.select_feature(object_id, holes[0])
    for _ in range(40):
        QApplication.processEvents()
    assert window._quiet_placement is not None
    window._escape()
    for _ in range(10):
        QApplication.processEvents()
    assert window._quiet_placement is None and window.object_tree.selected() is None, (
        "Escape nimmt zurück und wählt ab"
    )


def test_a_refused_measure_shows_the_reason_of_the_core_not_a_generic_sentence(
    window: MainWindow,
) -> None:
    """Hält die Kette an, steht ihr Befund über der Vorschau — nicht „konnte nicht
    berechnet werden" (Robert, 22.09.2026, am Halter mit Senkung).

    Der Arbeiter meldet erst ``explained`` mit dem Befund und dann ``done``
    ohne Bild; der zweite Ruf überschrieb den ersten mit dem allgemeinen Satz.
    """
    from PySide6.QtTest import QTest

    _object_id, _hole, flow, fields = _hole_fields_in_placement(window)
    fields["Durchmesser"].set_value_mm(5000.0)
    assert window.session.wait_for_idle(30_000)
    banner = window.viewport.banner
    for _ in range(300):
        QTest.qWait(50)
        window.session.wait_for_idle(1_000)
        if "Vielfaches" in banner.note.text() or "berechnet" in banner.note.text():
            break
    assert "übersteigt den Körper um ein Vielfaches" in banner.note.text(), banner.note.text()
    assert "konnte nicht berechnet werden" not in banner.note.text()
    assert window._preview_reason == banner.note.text().removeprefix(
        tr("Keine Vorschau: {reason}").format(reason="")
    ), "Band und gemerkter Grund sind derselbe Satz"
    assert flow.active, "die Maßgruppe bleibt stehen — der Wert lässt sich korrigieren"


@pytest.mark.parametrize("position_source", ["view", "panel", "normal"])
def test_panel_dimensions_and_placement_position_are_adopted_together(
    window: MainWindow, position_source: str
) -> None:
    """Bildposition und zuletzt getippte Maße werden gemeinsam ein rücknehmbarer Schritt."""
    object_id, hole, flow, fields = _hole_fields_in_placement(window)
    before = len(window.session.project.document.ops)
    wanted_position = [fields[axis].value_mm() for axis in ("X", "Y", "Z")]
    axis = 2 if position_source == "normal" else 0
    wanted_position[axis] += 1.0
    if position_source == "view":
        assert flow.move_to(tuple(wanted_position))
        assert fields["X"].value_mm() == pytest.approx(wanted_position[0])
    else:
        fields[("X", "Y", "Z")[axis]].set_value_mm(wanted_position[axis])
        QApplication.processEvents()
    if position_source == "normal":
        # Eine Koordinate senkrecht zur Fläche verlässt sie. Mitten im Tippen
        # entscheidet die Zahl noch nichts: Die Maßgruppe bleibt, Übernehmen
        # wartet und sagt warum (``5a90d4361``, ``refuse_typed_position``).
        # Erst die Eingabetaste gibt die Stelle frei — dann geht die
        # Maßgruppe, und es gilt die normale Feldvorschau mit den Feldern rechts.
        from PySide6.QtTest import QTest

        from app.ui.labels import LengthSpin

        assert flow.active and flow._typed_off_surface
        assert not flow._measure_accept.isEnabled()
        QTest.keyClick(fields["Z"].lineEdit(), Qt.Key.Key_Return)
        for _ in range(20):
            QApplication.processEvents()
        assert not flow.active
        fields = {
            field.accessibleName().rsplit(" — ", 1)[-1]: field
            for field in window.feature_panel.findChildren(LengthSpin)
            if field.isVisibleTo(window.feature_panel)
            and "Bohrung ändern" in field.accessibleName()
        }
        assert fields["Z"].value_mm() == pytest.approx(wanted_position[2])
    wanted_diameter = fields["Durchmesser"].value_mm() + 1.0
    fields["Durchmesser"].set_value_mm(wanted_diameter)
    assert window.session.wait_for_idle(30_000)
    if position_source != "normal":
        assert flow.active
        assert window._quiet_host.values()["diameter"] == pytest.approx(wanted_diameter)
        assert flow._tool_context is not None
        assert flow._tool_context.mesh.bounds.size[0] == pytest.approx(wanted_diameter)

    # Übernehmen wartet auf die dargestellte Vorschau (20.09.2026).
    window._feature_preview.stop()
    window._preview_feature_change()
    assert window.session.wait_for_idle(30_000)
    for _ in range(40):
        QApplication.processEvents()
    if position_source == "normal":
        window.feature_panel._apply.click()
    else:
        flow._measure_accept.click()
    assert window.session.wait_for_idle(30_000)

    assert len(window.session.project.document.ops) == before + 1
    step = window.session.project.document.ops[-1]
    assert step.op == "resize_hole" and step.params["at_feature"] == hole
    assert tuple(step.inputs) == (object_id,)
    assert step.params["diameter"] == pytest.approx(wanted_diameter)
    assert [step.params[axis] for axis in ("x", "y", "z")] == pytest.approx(wanted_position)
    window.session.undo()
    assert window.session.wait_for_idle(30_000)
    assert len(window.session.project.document.ops) == before


@pytest.mark.parametrize(
    "next_action", ["accept", "cancel", "selection", "project", "edit", "operation"]
)
def test_a_pending_feature_placement_accept_belongs_to_its_current_context(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, next_action: str
) -> None:
    """Ein Klick, während das Werkzeug rechnet, wartet; Kontextwechsel legen nichts ab.

    Vom 20.09.2026 an war der Knopf grau, solange gerechnet wurde. Ein Klick
    gleich nach dem Tippen fiel damit still auf einen grauen Knopf (Durchsicht
    0.5.1, Kunde Weg b, ``5a90d4361``): Warten ist keine Sperre. Der Klick
    wartet auf das Werkzeug und danach auf die dargestellte Vorschau
    (``requires_displayed_preview``); erst dann entsteht der Schritt. Jeder
    Kontextwechsel davor nimmt den wartenden Klick mit.
    """
    from app.core.scene import placement

    _, hole, flow, fields = _hole_fields_in_placement(window)
    before = len(window.session.project.document.ops)
    entered, proceed = threading.Event(), threading.Event()
    prepare = placement.prepare_tool

    def held_prepare(*args: Any, **kwargs: Any) -> Any:
        # Angehalten wird nur der Arbeiter der getippten Zahl. Den Start eines
        # neuen Flusses rechnet der kleine Körper im Hauptfaden
        # (``AT_ONCE_BELOW``); dort angehalten stünde die Ereignisschleife
        # bis zur Frist — nach *selection* und *cancel* 15 s je Fall.
        if threading.current_thread() is threading.main_thread():
            return prepare(*args, **kwargs)
        entered.set()
        assert proceed.wait(15)
        return prepare(*args, **kwargs)

    monkeypatch.setattr(placement, "prepare_tool", held_prepare)
    # Ob der Schritt erst nach dem Bild kommt, das der Kunde gesehen hat.
    shown_when_applied: list[bool] = []
    apply_placed = window._apply_placed_feature

    def applied(op: str, values: Any) -> Any:
        approval = window._preview_approval
        shown_when_applied.append(approval is not None and approval.displayed)
        return apply_placed(op, values)

    monkeypatch.setattr(window, "_apply_placed_feature", applied)
    wanted = fields["Durchmesser"].value_mm() + 1.0
    fields["Durchmesser"].set_value_mm(wanted)
    try:
        assert entered.wait(5), "das neue Werkzeug rechnet"
        assert flow._measure_accept.isEnabled(), "Warten ist keine Sperre"
        flow._measure_accept.click()
        assert flow._accept_pending, "der Klick wartet auf das Werkzeug"
        assert len(window.session.project.document.ops) == before
        if next_action == "cancel":
            window.feature_panel._cancel.click()
        elif next_action == "selection":
            result = window.session.last_result
            assert result is not None
            object_id, entry = next(iter(result.scene.objects.items()))
            other = next(
                name
                for name, feature in entry.features.items()
                if feature.kind == "hole" and name != hole
            )
            window.object_tree.select_feature(object_id, other)
        elif next_action == "project":
            window.session.start_new()
        elif next_action == "edit":
            fields["Durchmesser"].set_value_mm(wanted + 1.0)
        elif next_action == "operation":
            from PySide6.QtWidgets import QDoubleSpinBox

            angle = next(
                field
                for field in window.feature_panel.findChildren(QDoubleSpinBox)
                if field.isVisibleTo(window.feature_panel)
                and "Merkmal drehen" in field.accessibleName()
                and "Winkel" in field.accessibleName()
            )
            angle.setValue(angle.value() + 15.0)
        proceed.set()
        assert window.session.wait_for_idle(30_000)
        for _ in range(40):
            QApplication.processEvents()
        assert window.session.wait_for_idle(30_000)

        if next_action in ("accept", "operation"):
            # Der wartende Klick hängt nach dem Werkzeug an der dargestellten
            # Vorschau (20.09.2026) und wird dann ohne zweiten Klick ein
            # Schritt. Eine fremde Handlung, die die begonnene Änderung
            # abweist (``_quiet_command_allowed``), ist ohne Wirkung — auch
            # auf den wartenden Klick; sonst verfiele er wieder still.
            assert len(window.session.project.document.ops) == before + 1
            assert shown_when_applied == [True], "erst nach dem gezeigten Bild"
            step = window.session.project.document.ops[-1]
            assert step.op == "resize_hole" and step.params["at_feature"] == hole
            assert step.params["diameter"] == pytest.approx(wanted)
        else:
            assert len(window.session.project.document.ops) == (
                0 if next_action == "project" else before
            )
            assert flow.active == (next_action == "edit")
            assert not flow._accept_pending, "der Kontextwechsel nahm den Klick mit"
            assert not shown_when_applied
    finally:
        proceed.set()
        assert window.session.wait_for_idle(30_000)


def test_the_gizmo_sentence_reaches_the_status_line(window: MainWindow) -> None:
    """Was der Griff bewegen wird, sagt die Ansicht — und der Kunde liest es.

    Ein Satz, den niemand anzeigt, ist derselbe Fall wie ein Signal ohne
    Empfänger: im Sender geprüft, beim Kunden unsichtbar.
    """
    window.announce("Exportiert: dose.3mf")
    window.viewport.gizmoStatus.emit("Der Griff bewegt die Bohrung.")
    QApplication.processEvents()

    assert "Bohrung" in window.status_message.text()
    # **Ein Hinweis ist keine Quittung** (Review Fenster #9, 21.09.2026): Er
    # steht, solange er gilt, und wischt die letzte Ansage nicht — die kam
    # als Blase und stand acht Sekunden unter dem Zeiger, und ein leerer
    # Hinweis beim Verlassen des Griffs nahm die Quittung des Exports mit.
    assert window._announcement == "Exportiert: dose.3mf"
    assert window._action_notice.text() == "Exportiert: dose.3mf", "keine Blase für den Griff"
    window.viewport.gizmoStatus.emit("")
    assert window.status_message.text() == "Exportiert: dose.3mf", "die Quittung kommt zurück"


def test_selecting_a_feature_fills_the_panel_and_clearing_empties_it(
    window: MainWindow,
) -> None:
    """Das Merkmal-Panel folgt der Auswahl (Robert, 03.09.2026).

    Geprüft wird die Kette und nicht das Panel für sich: Ein Panel, das seine
    Zeilen bauen kann und nie eine Auswahl bekommt, ist beim Kunden leer.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    assert not window.feature_panel._built, "ohne Auswahl steht dort der Satz"

    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)
    QApplication.processEvents()
    assert window.feature_panel._built, "die Bohrung füllt das Panel"

    window.object_tree.select_object(object_id)
    QApplication.processEvents()
    assert not window.feature_panel._built, "ohne Merkmal ist es wieder leer"


def test_a_changed_number_in_the_panel_becomes_a_step(window: MainWindow) -> None:
    """„Eine geänderte Zahl ist die Operation." Gemessen bis in die Geometrie:
    Die Bohrung dreht sich, und der Schritt steht im Verlauf.

    **Gedreht und nicht aufgebohrt**, seit dem 10.09.2026: *Bohrung ändern*
    führt ins Bild statt sofort auszuführen (``LEADS_INTO_THE_VIEW``) — dort
    stehen die Maße, und übernommen wird in der Szene. Was diese Zusage prüft,
    ist der andere Fall: eine Handlung, deren Werte im Panel vollständig sind.
    """
    from PySide6.QtWidgets import QDoubleSpinBox, QLabel

    from app.ui.labels import LengthSpin

    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)
    QApplication.processEvents()

    # **Der Weg der Oberfläche, seit ein Knopf unten für alle steht** (10.09.2026):
    # In den Feldern der Handlung etwas ändern — das schaltet sie scharf — und
    # dann den einen Knopf drücken.
    panel = window.feature_panel
    for schluessel, eintrag in panel._runs.items():
        titel = eintrag.title
        if "drehen" not in titel:
            continue
        zeile = next(
            row
            for row in panel._built
            if any(label.text() == titel for label in row.findChildren(QLabel))
        )
        winkel = next(
            widget
            for widget in zeile.findChildren(QDoubleSpinBox)
            if not isinstance(widget, LengthSpin)
        )
        winkel.setValue(30.0)
        assert panel._armed == schluessel, "eine geänderte Zahl schaltet ihre Handlung scharf"
        panel._apply.click()
        break
    else:
        pytest.fail("das Panel bot keine Änderung an")
    window.session.wait_for_idle()

    assert [step.op for step in window.session.project.document.ops] == ["load", "rotate_feature"]
    letzter = window.session.project.document.ops[-1]
    assert float(letzter.params["angle"]) == pytest.approx(30.0)
    assert letzter.params["at_feature"] == hole, "und sie meint die angeklickte Bohrung"


def _a_chosen_hole(window: MainWindow) -> tuple[str, str]:
    """Eine eingelesene Platte mit gewählter Bohrung — der Ausgangspunkt von Weg 2."""
    window.open_path(MESHES / "plate_holes.stl")
    assert window.session.wait_for_idle(30_000)
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    window.object_tree.select_feature(object_id, hole)
    QApplication.processEvents()
    return object_id, hole


def test_the_apply_button_stays_in_sight_however_low_the_window_is(window: MainWindow) -> None:
    """Der Weg, einen Schritt abzuschließen, steht nicht unter dem Fensterrand.

    Gemessen am gebauten Fenster (13.09.2026, 1600 auf 1000 Punkten, gewählte
    Bohrung): Sichtfeld des Rollbereichs 877 Punkte, Inhalt 1579 — *Im Bild
    einstellen* lag bei y = 1015, *Übernehmen* bei y = 1062. Wer eine Zahl
    tippte, musste erst rollen, um sie zu übernehmen.

    Gemessen wird **gegen das Fenster rechts**, nicht in Bildschirmpunkten:
    Die Frage ist, ob die Zeile im sichtbaren Bereich des Docks liegt.

    **Und das Fenster wird dafür gezeigt.** Ungezeigt legt Qt seine Kinder
    nicht aus: Das Dock maß 100 auf 84 Punkte, und alle Halte lagen auf
    derselben Stelle — eine Messung, die auch mit der Knopfzeile im Rollinhalt
    grün blieb (gemessen an der Gegenprobe). Offscreen erscheint dabei nichts
    auf einem Bildschirm; ausgelegt wird trotzdem.

    Gemessen wird der **gewöhnliche** Zustand: Stehen die Maße im Bild, trägt
    seit dem 20.09.2026 die Maßgruppe Übernehmen und Abbrechen, und die Knöpfe
    hier unten gehen mit dem Messen (``set_measuring``). Unten stehen an einer
    Bohrung drei — *Im Bild einstellen*, der Haken für die Gruppe und
    *Übernehmen*.
    """
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtWidgets import QScrollArea

    window.resize(1600, 700)
    window.show()
    QApplication.processEvents()
    _a_chosen_hole(window)

    dock = window.feature_dock
    roller = dock.findChild(QScrollArea)
    assert roller is not None
    panel = window.feature_panel
    # **Zweimal, und die zweite Runde trägt die Messung.** Die Zeilen entstehen
    # in der ersten; ausgelegt werden sie erst danach, und vorher meldet das
    # Panel 272 Punkte statt 764 — eine Zahl, gegen die jede Höhenaussage
    # erfunden wäre.
    for _ in range(3):
        QApplication.processEvents()
    # **Die Voraussetzung des Funds, und sie ist schärfer als „der Inhalt
    # rollt".** Gerollt wird immer, sobald die Handlungsliste darunter steht;
    # der Knopf verschwindet erst, wenn die **Zeilen des Merkmals** allein
    # nicht mehr ins Sichtfeld passen. Gemessen: Panel 764 Punkte, Sichtfeld
    # 486 — bei 1600 auf 700. Ohne diese Zeile bliebe der Test auch dann grün,
    # wenn die Knopfzeile wieder mitrollte.
    assert panel.height() > roller.viewport().height(), (
        "passen die Zeilen ins Sichtfeld, prüft dieser Test nichts — "
        f"{panel.height()} in {roller.viewport().height()}"
    )
    unten = [panel._in_view, panel._every, panel._apply]
    stehen = [halt for halt in unten if halt.isVisibleTo(dock)]
    assert len(stehen) == len(unten), "an dieser Bohrung stehen alle drei"
    draussen = [
        f"{halt.accessibleName() or halt.text()} bei y={halt.mapTo(dock, QPoint(0, 0)).y()}"
        for halt in stehen
        if not dock.rect().contains(QRect(halt.mapTo(dock, QPoint(0, 0)), halt.size()))
    ]
    assert not draussen, f"unter dem Rand: {draussen} (Fenster {dock.height()} hoch)"

    # **Die strukturelle Hälfte derselben Zusage.** Was im Rollinhalt liegt,
    # kann hinausgerollt werden — gleich wie es in dieser Höhe gerade steht.
    inhalt = roller.widget()
    assert inhalt is not None and not inhalt.isAncestorOf(panel.footer()), (
        "die Knopfzeile rollt mit"
    )


def test_the_return_key_in_a_feature_field_writes_exactly_one_step(window: MainWindow) -> None:
    """Tippen, Enter, fertig — und genau ein Schritt im Verlauf.

    Gemessen am gebauten Fenster (13.09.2026): Durchmesser gesetzt, ``Return``
    im Feld, Verlauf 1 → 1. Der Knopf daneben tat es, und er stand an dieser
    Fensterhöhe unter dem Rand.
    """
    from PySide6.QtTest import QTest

    from app.ui.labels import LengthSpin

    object_id, hole = _a_chosen_hole(window)
    panel = window.feature_panel
    before = len(window.session.project.document.ops)
    feld = next(
        widget
        for widget in panel.findChildren(LengthSpin)
        if widget.isVisibleTo(panel)
        and "Merkmal verschieben" in widget.accessibleName()
        and widget.accessibleName().endswith("X")
    )
    feld.setFocus()
    feld.set_value_mm(feld.value_mm() + 2.0)
    QApplication.processEvents()

    QTest.keyClick(feld, Qt.Key.Key_Return)
    assert window.session.wait_for_idle(30_000)

    schritte = window.session.project.document.ops
    assert len(schritte) == before + 1, "genau ein Schritt, nicht keiner und nicht zwei"
    assert schritte[-1].op == "move_feature"
    assert schritte[-1].params["at_feature"] == hole
    assert tuple(schritte[-1].inputs) == (object_id,)


def test_a_halted_chain_locks_the_feature_panel_and_lets_go_after_undo(
    window: MainWindow,
) -> None:
    """Der Halt erreicht auch das Merkmalfenster — und verlässt es von selbst.

    Gemessen am gebauten Fenster (13.09.2026): Nach dem Halt waren
    *Übernehmen*, *Im Bild einstellen* und alle vierzehn Zahlenfelder aktiv,
    und der Versuch endete in einem modalen „Das hat so nicht funktioniert"
    (Regel 19). Menü, Werkzeugzeile und Befehlspalette trugen den Grund
    längst.

    Der Rückweg gilt ohne Neuauswahl: Nach Strg+Z rechnet die Kette wieder,
    und der Grund von vorhin ist keine Auskunft mehr.
    """
    from app.ui.labels import LengthSpin

    object_id, _ = _a_chosen_hole(window)
    panel = window.feature_panel
    felder = [
        widget
        for widget in panel.findChildren(LengthSpin)
        if widget.isVisibleTo(panel) and widget.property("handlingKey")
    ]
    assert felder, "ohne Felder prüft dieser Test nichts"
    assert panel._apply.isEnabled(), "Voraussetzung: ohne Halt nimmt das Fenster Zahlen an"

    window.session.apply(
        "Bohrung setzen",
        [
            OperationDraft(
                op="drill_hole",
                inputs=(object_id,),
                params={"diameter": 5000.0, "x": 0.0, "y": 0.0, "z": 4.0, "axis": "z"},
            )
        ],
    )
    assert window.session.wait_for_idle(30_000)
    QApplication.processEvents()
    assert window.session.last_result.stopped_at is not None, "der Wert hält die Kette an"

    grund = str(window._halt_reason() or "")
    assert grund, "der Halt hat einen Grund"
    assert not panel._apply.isEnabled(), "hinter einem Halt nimmt das Fenster nichts an"
    assert not panel._in_view.isEnabled()
    # Die Auswertung baut das Panel neu auf; die Felder von vorhin sind
    # gelöscht, gefragt wird nach denen, die jetzt dastehen.
    felder = [
        widget
        for widget in panel.findChildren(LengthSpin)
        if widget.isVisibleTo(panel) and widget.property("handlingKey")
    ]
    assert felder, "nach dem Halt steht das Merkmal weiter im Fenster"
    offen = [feld.accessibleName() for feld in felder if feld.isEnabled()]
    assert not offen, f"{len(offen)} Felder nehmen weiter Zahlen an: {offen}"
    assert panel._apply.toolTip() == grund, "der Grund steht am Knopf"
    # Regel 18: nicht nur grau, sondern als Satz — und zwar sichtbar, nicht
    # nur im Tooltip, den man erst suchen muss.
    assert panel._lock_note.text() == grund
    assert panel._lock_note.isVisibleTo(window.feature_dock)

    window.session.undo()
    assert window.session.wait_for_idle(30_000)
    QApplication.processEvents()

    assert window.session.last_result.stopped_at is None, "zurückgenommen rechnet sie wieder"
    assert panel._apply.isEnabled(), "und das Fenster gibt ohne Neuauswahl wieder frei"
    assert not panel._lock_note.isVisibleTo(window.feature_dock)
    frei = [
        widget
        for widget in panel.findChildren(LengthSpin)
        if widget.isVisibleTo(panel) and widget.property("handlingKey")
    ]
    assert frei and all(feld.isEnabled() for feld in frei)


def test_the_slot_that_was_pulled_stays_selected_after_apply(window: MainWindow) -> None:
    """Nach *Zum Langloch ziehen* → Übernehmen steht das Langloch im Fenster.

    Gemessen am gebauten Fenster (13.09.2026): Im Baum stand „Langloch 1",
    gewählt war der **Körper**, und das Merkmalfenster zeigte „Kein Merkmal
    gewählt …". Wer weiterarbeiten wollte, klickte es neu an — obwohl das
    Konzept (`konzept-merkmalbedienung-2026-09`, §4, Abnahme 1) das Gegenteil
    verspricht.

    Die Bohrung wechselt dabei ihren Namen (``hole_1`` wird ``slot_1``,
    zugesagt in ``SLOT_FEATURE_RENAMED``), und der Baum stellt nur eine
    Auswahl wieder her, deren Kennung es noch gibt. Gesucht wird deshalb an
    der Stelle, die der Schritt genannt hat.
    """
    object_id, hole = _a_chosen_hole(window)
    panel = window.feature_panel
    before = len(window.session.project.document.ops)
    assert panel.take_values("slot_hole", {"slot_length": 20.0, "slot_angle": 45.0}), (
        "an einer Bohrung steht *Zum Langloch ziehen*"
    )

    panel._apply.click()
    assert window.session.wait_for_idle(30_000)
    QApplication.processEvents()

    schritte = window.session.project.document.ops
    assert len(schritte) == before + 1 and schritte[-1].op == "slot_hole"
    entry = window.session.last_result.scene.objects[object_id]
    assert hole not in entry.features, "die Bohrung heißt jetzt anders — sonst prüft das nichts"
    gewaehlt = window.object_tree.selected_feature()
    assert gewaehlt is not None, "das entstandene Langloch bleibt gewählt"
    assert entry.features[gewaehlt].kind == "slot"
    assert panel.feature_id == gewaehlt, "und das Merkmalfenster zeigt es"


def test_a_double_click_on_a_feature_opens_what_changes_it(window: MainWindow) -> None:
    """Roberts Wunsch vom 03.09.2026: „bei Doppelklick würde ich auch gerne die
    Größen usw. ändern können über einen Dialog."

    Geprüft wird der Weg und nicht der Dialog: Der Baum nennt die Operation,
    das Fenster öffnet sie — dieselbe Kette, die das Kontextmenü seit je geht.
    An einer erkannten Bohrung ist das *Bohrung ändern*.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)
    target = next(
        item
        for item in window.object_tree.tree.selectedItems()
        if item.data(1, Qt.ItemDataRole.UserRole) == hole
    )

    angeboten: list[object] = []
    window.object_tree.operationRequested.connect(angeboten.append)
    window.object_tree._on_double_click(target, 0)

    assert angeboten, "der Doppelklick auf eine Bohrung blieb folgenlos"
    assert str(angeboten[0].name) in {spec.name for spec in REGISTRY.for_feature("hole")}


def test_a_double_click_on_a_body_keeps_unfolding_it(window: MainWindow) -> None:
    """Die Gegenprobe: Ein Körper und ein Dach über gleichartigen Merkmalen
    sind nichts, was man ändert — dort bleibt der Doppelklick das Aufklappen."""
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    window.session.evaluate_now()
    body = window.object_tree.tree.topLevelItem(0)
    assert body is not None and body.childCount() > 0, "der Körper hat Merkmale"

    angeboten: list[object] = []
    schritte: list[int] = []
    window.object_tree.operationRequested.connect(angeboten.append)
    window.object_tree.stepRequested.connect(schritte.append)
    window.object_tree._on_double_click(body, 0)

    assert not angeboten and not schritte, "ein Körper öffnet keinen Dialog"


def test_a_double_click_on_a_made_feature_opens_its_step(window: MainWindow) -> None:
    """Was aus einem Schritt kam, führt in diesen Schritt zurück — dort stehen
    seine Maße als Parameter, und genau die will der Kunde ändern (§21.2)."""
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)
    target = next(
        item
        for item in window.object_tree.tree.selectedItems()
        if item.data(1, Qt.ItemDataRole.UserRole) == hole
    )
    # Ein erkanntes Merkmal hat keinen Erzeuger; der Baum trägt die
    # Schrittnummer an der Zeile, und genau die liest der Doppelklick.
    from app.ui.panels import _STEP_ROLE

    target.setData(0, _STEP_ROLE, 1)

    schritte: list[int] = []
    window.object_tree.stepRequested.connect(schritte.append)
    window.object_tree._on_double_click(target, 0)

    assert schritte == [1], "der Schritt geht vor der Operation"


def test_a_context_click_hits_the_row_it_points_at(qt_app: QApplication) -> None:
    """Zwanzig Zeilen, zwanzig Rechtsklicks, zwanzig Treffer.

    Der Test darüber prüft **welches Merkmal** gewählt wird, dieser prüft
    **welche Zeile** — und nur der zweite fängt einen Versatz, der jede Zeile
    gleich weit verschiebt. Gemessen am Fehler vom 03.09.2026: Kopfzeile 17 px
    gegen Zeilenhöhe 12 px, fünf von sechs Klicks daneben, der erste ins Leere.

    Flache Zeilen statt einer Szene, weil die Frage keine Geometrie braucht:
    Es geht um die Zuordnung von Bildpunkt zu Zeile.
    """
    from PySide6.QtWidgets import QTreeWidgetItem

    from app.ui.panels import ObjectTree

    tree_panel = ObjectTree()
    tree_panel.resize(360, 700)
    tree_panel.show()
    QApplication.processEvents()
    tree = tree_panel.tree
    tree.clear()
    for number in range(20):
        tree.addTopLevelItem(QTreeWidgetItem([f"Zeile {number}", f"{number} mm"]))
    QApplication.processEvents()
    tree_panel.context_menu = lambda: None  # type: ignore[method-assign]

    assert tree.header().height() > 0, "ohne Kopfzeile prüft dieser Test den Versatz nicht"

    daneben: list[str] = []
    for number in range(20):
        item = tree.topLevelItem(number)
        middle = tree.visualItemRect(item).center()
        if middle.y() < 0 or middle.y() > tree.viewport().height():
            continue
        QApplication.sendEvent(
            tree.viewport(),
            QContextMenuEvent(
                QContextMenuEvent.Reason.Mouse, middle, tree.viewport().mapToGlobal(middle)
            ),
        )
        QApplication.processEvents()
        chosen = tree.selectedItems()
        got = chosen[0].text(0) if chosen else "nichts"
        if got != item.text(0):
            daneben.append(f"{item.text(0)} -> {got}")

    assert not daneben, "der Rechtsklick traf eine andere Zeile: " + ", ".join(daneben)


def test_a_tolerance_keeps_its_third_decimal(qt_app: QApplication) -> None:
    """Zwei Nachkommastellen machten aus 0,075 beim Öffnen eine 0,08 — eine
    stille Änderung an einer Zahl, die jemand gemessen hat (§11.2)."""
    from app.ui.op_dialog import _decimals_for

    fine = next(
        entry
        for spec in REGISTRY.all()
        for entry in spec.params.spec()
        if entry.kind == "float" and entry.maximum is not None and 0 < entry.maximum <= 1.0
    )
    assert _decimals_for(fine) == 3


def test_the_report_summary_counts_findings_from_both_directions(
    qt_app: QApplication,
) -> None:
    """Befunde kommen aus der Auswertung *und* über ``add_findings`` (§28.2).

    Die Zeile über der Liste zählte nur die erste Sorte und schrieb deshalb
    „Keine Befunde" über eine Liste voller Befunde — aufgefallen, als für das
    Handbuch ein Bild davon aufgenommen wurde.
    """
    from app.core.types import Finding
    from app.ui.panels import ReportPanel

    panel = ReportPanel()
    assert "Keine Befunde" in panel.summary.text()

    panel.add_findings(
        [
            Finding(code="a.b", severity="warning", message="offen"),
            Finding(code="c.d", severity="info", message="dünn"),
        ]
    )

    assert panel.list.count() == 2
    assert "Keine Befunde" not in panel.summary.text()
    assert "1" in panel.summary.text()


def test_a_report_without_findings_says_so(qt_app: QApplication) -> None:
    from app.ui.panels import ReportPanel

    panel = ReportPanel()
    panel.show_result(None)

    assert "Keine Befunde" in panel.summary.text()


def test_every_tool_bar_gets_the_room_it_needs(window: MainWindow) -> None:
    """Ein geöffnetes Werkzeug darf nicht über den Umschaltern liegen.

    Die untere Zone hängt in einer Überlagerung: sie bekommt ihre Geometrie
    gesetzt, statt sie von einem Layout rechnen zu lassen. Solange niemand
    meldete, dass eine Leiste dazugekommen ist, blieb sie auf der Höhe der
    Knopfreihe — einunddreißig Pixel für einen Bedarf von siebenundneunzig.
    Regler, Felder und Knöpfe lagen dann über den Umschaltern, und zwar bei
    **jedem** der sieben Werkzeuge. Gesehen wurde es an einem
    Bildschirmfoto fürs Handbuch.
    """
    window._show_start_screen(False)
    qt_app = QApplication.instance()
    assert qt_app is not None
    for _ in range(20):
        qt_app.processEvents()

    zone = window.overlay.bottom
    assert zone is not None

    too_small = []
    for key in ("section", "measure", "transform", "analysis", "layers", "explode", "paint"):
        window.tools.activate(key)
        for _ in range(10):
            qt_app.processEvents()
        if zone.height() < zone.sizeHint().height():
            too_small.append(f"{key}: {zone.height()} statt {zone.sizeHint().height()}")
        window.tools.activate(None)

    assert not too_small, "die untere Zone bleibt zu niedrig:\n" + "\n".join(too_small)


def test_a_bar_never_shows_itself_past_its_switch(window: MainWindow) -> None:
    """Die Sichtbarkeit einer Leiste gehört der Werkzeugzeile — nur ihr.

    Die Explosionsleiste machte sich in ``show_for`` selbst sichtbar, sobald
    eine Szene zwei Körper hatte. Zwei Stellen steuerten damit dasselbe: die
    eine klappte auf, was die andere zugeklappt hielt, und die Leiste lag über
    den Umschaltern. Sie sagt jetzt nur noch, ob sie etwas zu bieten hat —
    gezeigt wird sie, wenn jemand ihren Knopf drückt.
    """
    window._show_start_screen(False)
    qt_app = QApplication.instance()
    assert qt_app is not None

    assert window.explode_bar.show_for(3) is True, "drei Körper sind etwas zum Auseinanderziehen"
    assert window.explode_bar.show_for(1) is False
    for _ in range(10):
        qt_app.processEvents()

    # ``isVisibleTo`` und nicht ``isVisible``: das Fenster im Test ist selbst
    # nicht auf dem Bildschirm, und dann ist alles darin unsichtbar — auch
    # das, was aufgeklappt wäre.
    strip = window.tools
    assert not window.explode_bar.isVisibleTo(strip), "ohne Knopfdruck bleibt sie zu"

    window.tools.set_tool_usable("explode", True)
    window.tools.activate("explode")
    for _ in range(10):
        qt_app.processEvents()
    assert window.explode_bar.isVisibleTo(strip), "mit Knopfdruck geht sie auf"

    # Und wird das Werkzeug grau, geht sie mit — der Knopf bleibt stehen und
    # sagt, was ihm fehlt (bis zum 14.09.2026 verschwand er).
    reason = str(tr("Dafür braucht es zwei Körper in der Szene."))
    window.tools.set_tool_usable("explode", False, reason)
    for _ in range(10):
        qt_app.processEvents()
    assert not window.explode_bar.isVisibleTo(strip)
    assert window.tools.active() is None
    button = window.tools._buttons["explode"]
    assert not button.isHidden() and not button.isEnabled(), "grau, nicht weg"
    assert button.toolTip() == reason


def test_the_explosion_tool_stays_in_the_strip_and_says_it_needs_two_bodies(
    window: MainWindow,
) -> None:
    """Sieben Werkzeuge in der leeren Szene, sechs mit einem Körper, sieben mit
    zweien — die Zeile baute sich beim Laden einer Datei um (Bedienweg-
    Durchsicht 14.09.2026). Sachlich richtig, denn eine Explosionsansicht
    braucht zwei Körper; falsch war, es nicht zu sagen. Jetzt bleibt der
    Knopf und trägt den Grund, wie die sechs anderen ihren.
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    button = window.tools._buttons["explode"]
    assert not button.isHidden(), "der Knopf bleibt in der Zeile"
    assert not button.isEnabled(), "mit einem Körper gibt es nichts auseinanderzuziehen"
    assert button.toolTip() == str(tr("Dafür braucht es zwei Körper in der Szene."))

    assert window.session.apply(
        str(REGISTRY.get("duplicate_object").title),
        [OperationDraft(op="duplicate_object", inputs=("obj_1",))],
    )
    window.session.wait_for_idle()
    assert button.isEnabled(), "mit zwei Körpern geht die Explosionsansicht"
    assert button.toolTip() != str(tr("Dafür braucht es zwei Körper in der Szene."))


def test_the_report_puts_the_heavy_findings_first(qt_app: QApplication) -> None:
    """Die Zählzeile verspricht eine Rangfolge — die Liste muss sie halten.

    Vorher hängte sie an, wie es kam: bei zwei Warnungen und vier Hinweisen
    stand zuoberst ein Hinweis, und der Fehler an sechster Stelle. Sichtbar
    war das am Bildschirmfoto des Hauptfensters, wo über einer Liste mit zwei
    Hinweisen „2 Warnung" stand.
    """
    from PySide6.QtCore import Qt

    from app.core.types import Finding
    from app.ui.panels import ReportPanel

    panel = ReportPanel()
    panel.add_findings(
        [
            Finding(code="a.info", severity="info", message="zuerst entstanden"),
            Finding(code="b.error", severity="error", message="der Fehler"),
            Finding(code="c.info", severity="info", message="noch ein Hinweis"),
            Finding(code="d.warning", severity="warning", message="die Warnung"),
        ]
    )

    order = [
        panel.list.item(row).data(Qt.ItemDataRole.UserRole).severity
        for row in range(panel.list.count())
    ]
    assert order == ["error", "warning", "info", "info"]


@pytest.mark.parametrize("additional", [False, True])
def test_later_report_findings_keep_the_selected_action(
    window: MainWindow, additional: bool
) -> None:
    """Nachlaufende Analyse lässt die gewählte Befundzeile und ihre Handlung stehen."""
    from PySide6.QtWidgets import QPushButton

    from app.core.types import Finding

    panel = window.report
    chosen = Finding(code="agent.undo_sweeps", severity="warning", message="ältere Schritte")
    panel.add_findings([chosen])
    panel.list.setCurrentRow(0)
    before = [
        item.widget().text()
        for index in range(panel._offer_row.count())
        if (item := panel._offer_row.itemAt(index)) is not None
        and isinstance(item.widget(), QPushButton)
    ]
    assert before

    incoming = [Finding(code="analysis.new", severity="error", message="neuer Befund")]
    panel.add_findings(incoming if additional else [])

    selected = panel.list.currentItem()
    assert selected is not None
    assert selected.data(Qt.ItemDataRole.UserRole) == chosen
    current = [
        item.widget()
        for index in range(panel._offer_row.count())
        if (item := panel._offer_row.itemAt(index)) is not None
        and isinstance(item.widget(), QPushButton)
    ]
    assert [button.text() for button in current] == before
    assert all(not button.isHidden() for button in current)


def keep_the_files_place(window: MainWindow) -> None:
    """Der letzte Ladeschritt ohne Lageentscheidung: Die Datei behält ihre Koordinaten.

    Ein weiteres Modell kommt seit dem 28.09.2026 aufgesetzt an die erste freie
    Stelle (§17.1, Schritt 6). Unter der Platte liegt es nur noch, wenn die
    Haken am Ladeschritt aus sind — wie in jedem Schritt, der davor gespeichert
    wurde. Die Tests der Befunde „unter dem Bett" stellen genau das her.
    """
    step = window.session.history.operations[-1]
    assert step.op in ("load", "load_step"), step.op
    assert window.session.change_params(step.id, {"place_on_bed": False, "free_spot": False})
    assert window.session.wait_for_idle()


def test_a_finding_with_a_way_out_is_chosen_before_anyone_clicks(window: MainWindow) -> None:
    """Die Knopfzeile des Prüfberichts steht ohne einen Klick da (§2.7).

    Sie zeigt die Handlungen des **gewählten** Befunds — und gewählt war nach
    dem Öffnen keiner. Der Kunde sah eine Liste und darunter nichts; dass ein
    Klick auf eine Listenzeile Knöpfe freischaltet, muss man wissen. §2.7
    verspricht anklickbare Handlungen, nicht auffindbare.

    Gemessen an einem **zweiten** Modell mit ausgeschalteten Haken am
    Ladeschritt: Das erste Modell eines Projekts kommt aufgesetzt und mittig
    herein, jedes weitere aufgesetzt an eine freie Stelle (§17.1, Schritt 6).
    Die Dateilage hat nur, wer *Auf das Bett setzen* und *An eine freie Stelle
    legen* ausschaltet — ``block_with_rounded_edge.stl`` liegt dann von Z -10
    bis +10 —, der Bericht meldet ``arrange.below_bed``, und *Auf das Bett
    setzen* löst es mit einem Klick. Vorher standen dort **null** Knöpfe und
    ``currentRow()`` auf −1.

    Zwei Entscheidungen im Testaufbau, beide notwendig:

    * **Am gebauten Fenster**, nicht an einem freistehenden ``ReportPanel``.
      ``_preselect`` fragt ``handlers_of``, und ein Panel ohne Fenster darüber
      hat keine Handler — der Test wäre grün gegen eine Zeile, die beim Kunden
      nichts tut.
    * **Die Knöpfe werden gezählt, nicht auf ``isVisible`` geprüft.** In einem
      nie gezeigten Fenster antwortet Qt darauf falsch; die Knöpfe existieren
      dagegen nur, wenn ``_show_offers`` sie gebaut hat, und das tut es allein
      für einen gewählten Befund.
    """
    from PySide6.QtWidgets import QAbstractButton

    window.open_path(MESHES / "block_with_rounded_edge.stl")
    window.session.wait_for_idle()
    # Das zweite Modell ist das, das unter der Platte landet — mit den Haken
    # seines Ladeschritts aus, sonst läge es aufgesetzt an einer freien Stelle.
    window.open_path(MESHES / "block_with_rounded_edge.stl")
    window.session.wait_for_idle()
    keep_the_files_place(window)
    window._on_scene(window.session.evaluate_now())

    codes = [
        window.report.list.item(row).data(Qt.ItemDataRole.UserRole).code
        for row in range(window.report.list.count())
    ]
    assert "arrange.below_bed" in codes, "dieses Modell steckt unter dem Bett"

    assert window.report.list.currentRow() >= 0, "kein Befund ist vorgewählt"
    offered = [
        button.text().replace("&", "")
        for button in window.report._offers.findChildren(QAbstractButton)
    ]
    assert offered, "ohne einen Klick steht keine Handlung als Knopf da"

    chosen = window.report.list.currentItem().data(Qt.ItemDataRole.UserRole)
    assert chosen.code == "arrange.below_bed", (
        f"vorgewählt ist {chosen.code!r} — der Befund ohne Handlung nützt hier nichts"
    )


def test_the_split_and_retry_button_lays_the_pieces_on_the_plates(
    window: MainWindow, tmp_path: Path
) -> None:
    """Ein Klick im Prüfbericht: zerlegen, ausrichten, auf die Platten — und
    ein Undo nimmt alles zurück.

    **Roberts Fall** (11.09.2026: „das druckoptimal ausrichten klappt nicht, es
    werden nicht mehr platten angelegt"): Ein Schriftzug von 200 mm passt als
    Ganzes auf kein Bett, die Kette hielt an, und die zwei Knöpfe hießen
    Teilen und anderer Drucker. Hier steht der Weg von der Absage bis zu den
    Platten — am Fenster, nicht am Verlauf: Dass ``History.split_and_retry``
    die Teile einsetzt, prüft ``test_history.py``; dass der Kunde den Knopf
    bekommt und er bis ans Ende läuft, nur diese Zeile.

    Zwei lose Platten 80 x 80, ein halber Meter auseinander — der Schriftzug
    im Kleinen. Nach dem Klick: kein Halt, zwei Körper, beide im Bett, ein
    Zug im Verlauf; nach dem Undo wieder ein Körper und die Absage.
    """
    import trimesh

    from app.core.errors import SPLIT_AND_RETRY
    from app.ui.main_window import inputs_for
    from app.ui.panels import actions_for_document, as_error

    near = trimesh.creation.box(extents=(80.0, 80.0, 4.0))
    far = trimesh.creation.box(extents=(80.0, 80.0, 4.0))
    far.apply_translation((500.0, 0.0, 0.0))
    path = tmp_path / "inseln.stl"
    path.write_bytes(trimesh.util.concatenate([near, far]).export(file_type="stl"))
    window.open_path(path)
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    spec = REGISTRY.get("orient_for_print")
    window.session.apply(
        spec.title,
        [
            OperationDraft(
                op=spec.name,
                inputs=inputs_for(spec, list(result.scene.objects), []),
                params={"thorough": False},
            )
        ],
    )
    window.session.wait_for_idle()
    halted = window.session.evaluate_now()
    window._on_scene(halted)
    assert halted.stopped_at is not None, "der Körper passt — dann prüft der Test nichts"

    refusal = next(f for f in halted.scene.report.findings if f.severity == "error")
    handlers = window.error_handlers()
    offered = actions_for_document(
        refusal,
        window.session.project.document,
        stopped_at=halted.stopped_at,
        live_objects=set(halted.scene.objects),
    )
    assert next(a.id for a in offered if a.id in handlers) == SPLIT_AND_RETRY.id, (
        f"der erste Knopf ist die Zerlegung, nicht {[a.id for a in offered]}"
    )
    steps_before = len(window.session.history.transactions)

    handlers[SPLIT_AND_RETRY.id](as_error(refusal, window.session.project.document))
    window.session.wait_for_idle()

    after = window.session.last_result
    assert after is not None and after.stopped_at is None, (
        f"die Kette hält weiter an: {[str(f.message) for f in after.scene.report.findings]}"
    )
    assert len(after.scene.objects) == 2
    assert len(window.session.history.transactions) == steps_before + 1, "ein Zug, ein Undo"
    half = window.session.profile.printer.build_volume[0] / 2.0
    for name, entry in after.scene.objects.items():
        box = entry.mesh.bounds
        assert -half <= box.minimum[0] and box.maximum[0] <= half, f"{name} liegt neben dem Bett"

    window.session.undo()
    window.session.wait_for_idle()
    back = window.session.last_result
    assert back is not None and list(back.scene.objects) == ["obj_1"]
    assert back.stopped_at == halted.stopped_at, "nach dem Undo steht die Absage wieder da"


def _dense_plate_file(folder: Path) -> Path:
    """Die Lochplatte, dreimal gleichmäßig geviertelt — dichter, als ihre Form verlangt."""
    import trimesh

    plate = trimesh.load(MESHES / "plate_holes.stl", force="mesh")
    vertices, faces = plate.vertices, plate.faces
    for _pass in range(3):
        vertices, faces = trimesh.remesh.subdivide(vertices, faces)
    path = folder / "platte_dicht.stl"
    path.write_bytes(trimesh.Trimesh(vertices, faces, process=False).export(file_type="stl"))
    return path


def test_the_decimate_and_retry_button_thins_before_the_step_and_runs_through(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Klick im Prüfbericht: verringern, verfeinern, fertig — und Strg+Z nimmt alles zurück.

    **Der Rat stand seit 0.5.0 da und hatte keinen Draht** (Durchsicht 0.5.1,
    REPARATUR-09): *Kanten verfeinern* an einem Netz, das dichter ist als seine
    Form, hielt an, und „Vorher mit „Dreiecke verringern“ ausdünnen." kam im
    Prüfbericht gar nicht an. Dass ``History.decimate_and_retry`` den Schritt
    davor setzt, prüft ``test_missing_ops.py``; dass der Kunde den Knopf
    bekommt und er bis ans Ende läuft, nur diese Zeile. Die Decke ist klein
    gesetzt, damit der Weg in Sekunden läuft — der Draht ist derselbe.
    """
    from app.core.errors import DECIMATE_AND_RETRY
    from app.core.geom import mesh_ops
    from app.ui.panels import actions_for_document, as_error

    monkeypatch.setattr(mesh_ops, "MAX_REMESH_TRIANGLES", 200_000)
    window.open_path(_dense_plate_file(tmp_path))
    window.session.wait_for_idle()
    window.session.evaluate_now()
    spec = REGISTRY.get("remesh_mesh")
    window.session.apply(
        spec.title, [OperationDraft(op=spec.name, inputs=("obj_1",), params={"edge": 1.0})]
    )
    window.session.wait_for_idle()
    halted = window.session.evaluate_now()
    window._on_scene(halted)
    assert halted.stopped_at is not None, "das Teilen ging — dann prüft der Test nichts"

    refusal = next(f for f in halted.scene.report.findings if f.severity == "error")
    handlers = window.error_handlers()
    offered = [
        action.id
        for action in actions_for_document(
            refusal,
            window.session.project.document,
            stopped_at=halted.stopped_at,
            live_objects=halted.scene.objects,
        )
        if action.id in handlers
    ]
    assert offered == ["use_reachable", DECIMATE_AND_RETRY.id], offered
    ops_before = list(window.session.project.document.ops)
    steps_before = len(window.session.history.transactions)

    handlers[DECIMATE_AND_RETRY.id](as_error(refusal, window.session.project.document))
    window.session.wait_for_idle()

    after = window.session.last_result
    assert after is not None and after.stopped_at is None, (
        f"die Kette hält weiter an: {[str(f.message) for f in after.scene.report.findings]}"
    )
    assert [entry.op for entry in window.session.project.document.ops] == [
        "load",
        "decimate_mesh",
        "remesh_mesh",
    ]
    assert len(window.session.history.transactions) == steps_before + 1, "ein Zug, ein Undo"
    assert after.scene.objects["obj_1"].mesh.is_watertight

    window.session.undo()
    window.session.wait_for_idle()
    back = window.session.last_result
    assert list(window.session.project.document.ops) == ops_before
    assert back is not None and back.stopped_at == halted.stopped_at, (
        "nach dem Undo steht die Absage wieder da"
    )


def test_the_remesh_and_retry_button_refines_before_the_smoothing_and_runs_through(
    window: MainWindow, tmp_path: Path
) -> None:
    """*Glätten* stülpt eine dünne Schale um — ein Klick im Prüfbericht verfeinert davor.

    „Vorher neu vernetzen — feiner glättet sanfter." war bis zur Durchsicht
    0.5.1 ein Rat ohne Länge und ohne Knopf. Jetzt nennt der Kern die Länge,
    an der Verfeinern und Glätten durchlaufen, und der Knopf setzt *Kanten
    verfeinern* vor den Schritt — ein Zug, Strg+Z nimmt ihn zurück.
    """
    import trimesh

    from app.core.errors import REMESH_AND_RETRY
    from app.core.geom.hollow import hollow
    from app.core.geom.mesh import MeshData
    from app.ui.panels import actions_for_document, as_error

    box = trimesh.creation.box(extents=(40.0, 40.0, 30.0))
    box.apply_translation((0.0, 0.0, 15.0))
    path = tmp_path / "schale.stl"
    path.write_bytes(hollow(MeshData.of(box), 2.0, vents=1).mesh.raw.export(file_type="stl"))
    window.open_path(path)
    window.session.wait_for_idle()
    window.session.evaluate_now()
    spec = REGISTRY.get("smooth_mesh")
    window.session.apply(
        spec.title, [OperationDraft(op=spec.name, inputs=("obj_1",), params={"iterations": 5})]
    )
    window.session.wait_for_idle()
    halted = window.session.evaluate_now()
    window._on_scene(halted)
    assert halted.stopped_at is not None, "das Glätten ging — dann prüft der Test nichts"

    refusal = next(f for f in halted.scene.report.findings if f.severity == "error")
    handlers = window.error_handlers()
    offered = [
        action.id
        for action in actions_for_document(
            refusal,
            window.session.project.document,
            stopped_at=halted.stopped_at,
            live_objects=halted.scene.objects,
        )
        if action.id in handlers
    ]
    assert offered == [REMESH_AND_RETRY.id], offered
    ops_before = list(window.session.project.document.ops)

    handlers[REMESH_AND_RETRY.id](as_error(refusal, window.session.project.document))
    window.session.wait_for_idle()

    after = window.session.last_result
    assert after is not None and after.stopped_at is None
    assert [entry.op for entry in window.session.project.document.ops] == [
        "load",
        "remesh_mesh",
        "smooth_mesh",
    ]
    assert after.scene.objects["obj_1"].mesh.volume > 0.0
    window.session.undo()
    window.session.wait_for_idle()
    assert list(window.session.project.document.ops) == ops_before


def test_the_decimate_button_retries_only_the_halted_step_with_the_named_count() -> None:
    """*Dreiecke verringern und erneut versuchen* nimmt Schritt und Zahl aus dem Befund.

    Am angehaltenen Schritt setzt der Verlauf das Verringern davor; ohne Zahl
    tut der Knopf nichts — geraten wird sie nicht (Regel 21) —, und hält die
    Kette woanders, geht der Dialog der Operation für den Körper des Befunds
    auf, vorbelegt mit derselben Zahl und dem schnellen Weg.
    """
    from types import SimpleNamespace

    retried: list[tuple[int, int]] = []
    opened: list[tuple[str, dict[str, object], tuple[str, ...]]] = []
    view = SimpleNamespace(
        session=SimpleNamespace(
            last_result=SimpleNamespace(stopped_at=7),
            decimate_and_retry=lambda step, count: retried.append((step, count)),
        ),
        run_operation=lambda spec, given, on_bodies: opened.append(
            (spec.name, dict(given), tuple(on_bodies))
        ),
    )

    MainWindow._decimate_after_error(
        view, errors.AppError(title="zu fein", op_id=7, values={"decimate_to": 25_000})
    )
    MainWindow._decimate_after_error(view, errors.AppError(title="zu fein", op_id=7))
    MainWindow._decimate_after_error(
        view,
        errors.AppError(
            title="zu fein", op_id=3, object_id="obj_2", values={"decimate_to": "12000"}
        ),
    )

    assert retried == [(7, 25_000)]
    assert opened == [("decimate_mesh", {"triangles": 12_000, "method": "fast"}, ("obj_2",))]


def test_the_remesh_button_retries_only_the_halted_step_with_the_named_length() -> None:
    """*Kanten verfeinern und erneut versuchen* nimmt Schritt und Länge aus dem Befund.

    Das Gegenstück zum Verringern, für ein *Glätten*, das umschlug oder zu
    viel kostete: vor dem Schritt das Verfeinern, ohne Länge nichts
    (Regel 21), und steht der Schritt nicht mehr im Verlauf, geht *Kanten
    verfeinern* vorbelegt auf.
    """
    from types import SimpleNamespace

    retried: list[tuple[int, float]] = []
    opened: list[tuple[str, dict[str, object], tuple[str, ...]]] = []
    view = SimpleNamespace(
        session=SimpleNamespace(
            project=SimpleNamespace(
                document=SimpleNamespace(ops=[SimpleNamespace(id=6), SimpleNamespace(id=7)])
            ),
            remesh_and_retry=lambda step, edge: retried.append((step, edge)),
        ),
        run_operation=lambda spec, given, on_bodies: opened.append(
            (spec.name, dict(given), tuple(on_bodies))
        ),
    )

    MainWindow._remesh_after_error(
        view, errors.AppError(title="umgestülpt", op_id=7, values={"remesh_to_mm": 2.0})
    )
    MainWindow._remesh_after_error(view, errors.AppError(title="umgestülpt", op_id=7))
    MainWindow._remesh_after_error(
        view,
        errors.AppError(
            title="umgestülpt", op_id=3, object_id="obj_2", values={"remesh_to_mm": "5"}
        ),
    )

    MainWindow._remesh_after_error(
        view, errors.AppError(title="geschrumpft", op_id=6, values={"remesh_to_mm": 10.0})
    )

    assert retried == [(7, 2.0), (6, 10.0)]
    assert opened == [("remesh_mesh", {"edge": 5.0}, ("obj_2",))]


def test_a_refused_preview_offers_in_the_dialog_what_the_dialog_carries_out() -> None:
    """Die Absage der Vorschau trägt ihre Knöpfe in den Dialog — nur mit Zahl (RESTVERLAUF-04).

    *Die kleinste Kantenlänge nehmen, die noch geht.* schreibt die Zahl ins
    Feld; *Dreiecke verringern und erneut versuchen* setzt das Verringern vor
    den Schritt des Dialogs. Beides nur mit dem Wert aus der Absage, und das
    Verringern nur, wo es einen Schritt gibt, vor den es gehört.
    """
    from types import SimpleNamespace

    from app.core.errors import Action, ValidationError

    taken: list[tuple[str, float]] = []
    prepared: list[tuple[str, dict[str, object]]] = []
    view = SimpleNamespace(
        _prepared_from_dialog=lambda approval, op, params, title: prepared.append(
            (op, dict(params))
        )
    )
    owner = SimpleNamespace(take_value=lambda name, value: taken.append((name, value)))
    draft = OperationDraft(op="remesh_mesh", inputs=("obj_1",), params={"edge": 0.3})
    approval = SimpleNamespace(
        owner=owner, order=SimpleNamespace(change_op=None, drafts=(draft,), changes=None)
    )
    refusal = ValidationError(
        field="edge",
        detail="zu fein",
        values={"reachable": 0.8, "decimate_to": 12_000},
        suggestions=(
            Action("use_reachable", "Die kleinste Kantenlänge nehmen, die noch geht."),
            errors.DECIMATE_AND_RETRY,
        ),
    )

    handlers = MainWindow._refusal_handlers(view, approval, refusal)
    assert set(handlers) == {"use_reachable", "decimate_and_retry"}
    handlers["use_reachable"](refusal)
    handlers["decimate_and_retry"](refusal)
    assert taken == [("edge", 0.8)]
    assert prepared == [("decimate_mesh", {"triangles": 12_000, "method": "fast"})]

    bare = ValidationError(field="edge", detail="zu fein", suggestions=refusal.suggestions)
    assert MainWindow._refusal_handlers(view, approval, bare) == {}, "ohne Zahl kein Knopf"
    nothing_to_prepare = SimpleNamespace(
        owner=owner, order=SimpleNamespace(change_op=None, drafts=(), changes=None)
    )
    assert set(MainWindow._refusal_handlers(view, nothing_to_prepare, refusal)) == {"use_reachable"}


def test_a_step_prepared_from_the_dialog_is_one_move() -> None:
    """Vorbereitung und Schritt aus dem Dialog: eine Transaktion, der Dialog geht zu.

    Beim Anlegen stehen das Verringern je Eingang und der Schritt in einem
    ``Session.apply``; beim Ändern ersetzt der Verlauf den Schritt mit den
    getippten Werten (``History.decimate_and_retry``). Nie zwei Strg+Z für
    einen Klick (Regel 16).
    """
    from types import SimpleNamespace

    applied: list[tuple[object, list[OperationDraft], object]] = []
    retried: list[tuple[int, int, dict[str, object]]] = []
    closed: list[bool] = []
    view = SimpleNamespace(
        _preview_is_current=lambda approval: True,
        session=SimpleNamespace(
            apply=lambda title, drafts, changes=None: applied.append((title, drafts, changes)),
            decimate_and_retry=lambda step, count, values: retried.append(
                (step, count, dict(values))
            ),
        ),
    )
    owner = SimpleNamespace(reject=lambda: closed.append(True))
    draft = OperationDraft(op="remesh_mesh", inputs=("obj_1",), params={"edge": 0.3})
    fresh = SimpleNamespace(
        owner=owner, order=SimpleNamespace(change_op=None, drafts=(draft,), changes=None)
    )
    changed = SimpleNamespace(
        owner=owner,
        order=SimpleNamespace(change_op=5, drafts=(), changes=None, change_values={"edge": 0.3}),
    )

    MainWindow._prepared_from_dialog(
        view, fresh, "decimate_mesh", {"triangles": 12_000, "method": "fast"}, "Titel"
    )
    MainWindow._prepared_from_dialog(
        view, changed, "decimate_mesh", {"triangles": 12_000, "method": "fast"}, "Titel"
    )

    assert closed == [True, True]
    assert len(applied) == 1
    title, drafts, _changes = applied[0]
    assert title == "Titel"
    assert [(entry.op, entry.inputs) for entry in drafts] == [
        ("decimate_mesh", ("obj_1",)),
        ("remesh_mesh", ("obj_1",)),
    ]
    assert retried == [(5, 12_000, {"edge": 0.3})]


def test_the_band_says_how_many_triangles_a_retriangulating_step_leaves() -> None:
    """Gezählt heißt die genaue Zahl, vorab „geschätzt", am offenen Netz „höchstens"."""
    from app.ui.labels import count_text
    from app.ui.main_window import _count_note
    from app.ui.session import TriangleCounts

    assert count_text(6_081_000) == "6\u00a0081\u00a0000"
    assert count_text(6_081_000, rough=True) == "6\u00a0100\u00a0000"
    assert count_text(488) == "488"
    assert "geschätzt" in _count_note(TriangleCounts(250_488, 6_081_000, False, True))
    assert "höchstens" in _count_note(TriangleCounts(250_488, 6_081_000, True, True))
    counted = _count_note(TriangleCounts(1_280, 9_120))
    assert "geschätzt" not in counted and "9\u00a0120" in counted


def test_a_halted_step_whose_advice_nobody_carries_out_still_opens_the_step() -> None:
    """Regel 17 im Prüfbericht: Eine Absage ohne einlösbaren Rat bekommt *Eingabe korrigieren*.

    *Glätten* mit zu vielen Durchgängen hält mit „Weniger Durchgänge nehmen."
    und „Vorher neu vernetzen" an — zwei Räte, die nur der Kunde ausführen
    kann. Der Fehlerdialog zeigt sie als Sätze, der Prüfbericht zeigte nur
    Knöpfe und damit nichts (Durchsicht 0.5.1). Jetzt öffnet ein Knopf den
    Schritt; wo es einen einlösbaren Weg gibt, bleibt es bei ihm, und ein
    Befund, der nicht aus einer Operation stammt, bekommt keinen Schritt
    angeboten, den es nicht gibt.
    """
    from app.core.errors import Action
    from app.ui.panels import handled_actions

    def nothing(_error: object) -> None:
        return None

    advice = (
        Action("fewer_iterations", "Weniger Durchgänge nehmen."),
        Action("remesh_first", "Vorher neu vernetzen — feiner glättet sanfter."),
    )
    halted = Finding(
        code="op.smooth_mesh.ValidationError",
        severity="error",
        message="Der Körper hat sich beim Glätten umgestülpt.",
        op_id=4,
        values={"field": "iterations"},
        suggestions=advice,
    )
    handlers = {"correct_input": nothing}

    assert [action.id for action in handled_actions(halted, None, handlers)] == ["correct_input"]
    assert [
        action.id
        for action in handled_actions(halted, None, {**handlers, "fewer_iterations": nothing})
    ] == ["fewer_iterations"], "ein einlösbarer Weg geht vor"
    loose = dataclasses.replace(halted, code="ingest.colours_dropped", op_id=None)
    assert handled_actions(loose, None, handlers) == [], "ohne Schritt kein Schritt zum Öffnen"


def test_a_halted_chain_takes_no_new_step_and_names_the_way_on(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Hinter einen Halt kommt kein Schritt — und wer einen versucht, bekommt
    den Ausweg statt einer Zeile im Verlauf.

    **Roberts Fall** (11.09.2026: „da geht nichts mehr wenn ich die operation
    ausführe"): Schriftzug, in Einzelteile zerlegt, dann die Schrift gewechselt
    — Comfortaa hatte mit der damaligen Füllregel elf lose Teile, DejaVu
    Sans zehn, und die Zerlegung hielt an. Jede Operation danach ging durch
    ihren Dialog und stand dann als
    Schritt 4, 5, 6 hinter dem angehaltenen zweiten: nie gerechnet, im Bild
    nichts, im Verlauf eine Zeile mehr (§15.3: gerechnet wird bis zum Halt).

    Die korrigierte Füllregel liefert heute in beiden Schriften zehn Teile.
    Ein zusätzlicher Punkt liefert deshalb die unabhängige elfte Komponente;
    beim Ändern von Schrift und Text fällt sie weg und löst denselben Halt aus.

    Drei Zusagen, in der Reihenfolge, in der der Kunde sie trifft: Vor dem
    Klick ist jede Operation gesperrt und sagt warum — Aktion, Palette und
    Karte aus derselben Quelle (``_reason_locked``); Rückgängig und *Schritt
    löschen* bleiben frei, denn beides löst den Halt. Kommt trotzdem ein
    Schritt an (Kürzel, Fernsteuerung, Agent), schreibt die Sitzung ihn nicht
    und meldet die Handlungen des Halts selbst, mit Schrittkennung und Werten.
    Und die erste davon führt hinaus: ein Klick, zehn Teile, alles wieder frei.
    """
    from app.core.errors import RECOUNT_AND_RETRY

    document = window.session.project.document
    window.session.apply(
        "Schriftzug",
        [
            OperationDraft(
                op="create_label",
                inputs=(),
                params={"text": "Solidon3D.", "size": 200.0, "font": "Comfortaa"},
            )
        ],
    )
    assert window.session.wait_for_idle(30000)
    window.session.apply(
        "Zerlegen",
        [OperationDraft(op="split_bodies", inputs=("obj_1",), params={"count": 11})],
    )
    assert window.session.wait_for_idle(30000)
    initial = window.session.evaluate_now()
    assert initial.stopped_at is None, "elf Teile, elf verlangt — kein Halt"
    assert len(initial.scene.objects) == 11

    window.session.change_params(1, {"text": "Solidon3D", "size": 200.0, "font": "DejaVu Sans"})
    assert window.session.wait_for_idle(30000)
    halted = window.session.evaluate_now()
    window._on_scene(halted)
    split_step = document.ops[1].id
    assert halted.stopped_at == split_step, "der Schriftwechsel hält die Zerlegung an"

    # 1. Gesperrt, mit Grund — an jedem Eintrag derselbe Satz aus einer Quelle.
    window.object_tree._restore(["obj_1"], None)
    window._update_actions()
    action = window._op_actions["split_bodies"]
    reason = action.toolTip()
    assert not action.isEnabled()
    assert f"Schritt {split_step}" in reason and "Prüfbericht" in reason, reason
    assert window._palette_availability("create_box") == (False, reason), (
        "auch eine Operation ohne Eingang legte ihren Schritt hinter den Halt"
    )
    card = window.selection_operations._buttons["split_bodies"]
    assert not card.isEnabled() and card.toolTip() == reason
    for name, entry in (
        ("auto_split", window.auto_split_action),
        ("import", window.import_action),
        ("sketch", window._toolbar_sketch),
    ):
        assert not entry.isEnabled() and reason in entry.toolTip(), name
    assert window.undo_action.isEnabled(), "Rückgängig löst den Halt — es bleibt frei"
    assert window.history_panel.remove_action.isEnabled(), "Schritt löschen ebenso"

    # 2. Ein Schritt trotzdem: nicht geschrieben, und die Absage trägt den Ausweg
    # — als Dialog beim Kunden, nicht als Zeile auf stderr.
    refusals: list[errors.AppError] = []
    monkeypatch.setattr(
        main_window_module, "show_error", lambda error, *args, **kwargs: refusals.append(error)
    )
    steps_before = len(document.ops)
    accepted = window.session.apply(
        "Zerlegen",
        [OperationDraft(op="split_bodies", inputs=("obj_1",), params={"count": 2})],
    )
    assert not accepted and len(document.ops) == steps_before, "kein Schritt hinter dem Halt"
    window.session.split_async("obj_1", lambda _applied: None)
    assert not window.session.split_running, "auch der Ablauf legt keinen Schritt an"
    assert len(refusals) == 2
    refusal = refusals[0]
    assert refusal.op_id == split_step and refusal.values["found"] == "10"
    assert [entry.id for entry in refusal.suggestions] == [
        RECOUNT_AND_RETRY.id,
        "correct_input",
        "cancel",
    ], "die Absage bietet an, was der Prüfbericht am Halt anbietet"
    assert "Schritt" in str(refusal.detail) and "weniger Teile" in str(refusal.detail)

    # 3. Der erste Knopf führt hinaus, und danach ist alles wieder frei.
    window.error_handlers()[RECOUNT_AND_RETRY.id](refusal)
    assert window.session.wait_for_idle(30000)
    result = window.session.evaluate_now()
    window._on_scene(result)
    assert result.stopped_at is None and len(result.scene.objects) == 10
    assert window._palette_availability("create_box") == (True, "")
    assert window.import_action.isEnabled() and window._toolbar_sketch.isEnabled()
    assert reason not in window._toolbar_sketch.toolTip(), "der eigene Satz kommt zurück"


def test_the_small_parts_button_removes_them_and_not_merely_runs(window: MainWindow) -> None:
    """Der Knopf zu „sehr kleine Einzelteile" entfernt sie wirklich.

    Der Befund sagte „Gelöscht wurde nichts." und bot nichts an — gemessen am
    Korpus bei zwei von zwanzig Modellen. Die Anwendung **kann** es:
    ``repair`` trägt einen Schalter ``small_components``.

    **Der naheliegende Fix wäre ein Knopf ohne Wirkung gewesen.** Den Befund an
    das vorhandene ``REPAIR_AND_RETRY`` zu hängen, hätte zehn Sekunden
    gedauert: ``_repair_after_error`` ruft ``repair`` ohne Parameter, und der
    Schalter steht dort auf ``False`` (``geom/repair.py``). Der Knopf wäre
    durchgelaufen, hätte einen Schritt in den Verlauf gelegt und die Teile
    stehen gelassen.

    **Deshalb zählt dieser Test Komponenten und nicht Schritte.** Ein Test auf
    „die Operation lief" wäre gegen genau diesen Fehler blind — sie läuft ja.
    Die Zahl der Komponenten ist dabei die eine Größe, die der parameterlose
    Aufruf **nicht** bewegt: ``weld``, ``degenerate``, ``normals`` und
    ``holes`` stehen in der Vorgabe auf ``True`` und ändern Ecken, Dreiecke und
    Normalen — die Fragmente lassen sie stehen.
    """
    from app.core.geom.mesh import face_components
    from app.ui.panels import actions_for, as_error

    window.open_path(MESHES / "two_components.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    window._on_scene(result)

    findings = list(result.scene.report.findings)
    small = next((f for f in findings if f.code == "ingest.small_components"), None)
    assert small is not None, (
        "dieses Modell soll den Befund auslösen — sonst prüft der Test nichts: "
        f"{[f.code for f in findings]}"
    )

    body = next(iter(result.scene.objects.values()))
    assert body.mesh is not None
    before = len(face_components(body.mesh.raw))
    assert before > 1, "ohne mehrere Komponenten gibt es nichts zu entfernen"

    handlers = window.error_handlers()
    offered = [action for action in actions_for(small) if action.id in handlers]
    assert [action.id for action in offered] == ["remove_small_parts"], (
        f"der Befund bietet {[a.id for a in offered]} an"
    )
    handlers["remove_small_parts"](as_error(small))
    window.session.wait_for_idle()

    after_result = window.session.last_result
    assert after_result is not None
    after_body = next(iter(after_result.scene.objects.values()))
    assert after_body.mesh is not None
    after = len(face_components(after_body.mesh.raw))
    assert after < before, (
        f"{before} Komponenten vorher, {after} nachher — der Knopf lief, "
        "ohne die kleinen Teile zu entfernen"
    )


def test_leaving_the_wide_opening_open_changes_the_load_step(window: MainWindow) -> None:
    """*Offen lassen* nimmt dem Ladeschritt das Schließen der großen Öffnungen.

    Der Knopf entstand mit der Durchsicht vom 24.09.2026 (Entscheidung
    Robert); seit RM-241 schaltet er nur „Große Öffnungen schließen" ab, die
    kleinen Löcher gehen weiter zu. Gezählt wird die Wirkung — der Körper ist
    wieder offen — und dass kein zweiter Schritt entsteht.
    """
    from app.ui.panels import actions_for, as_error

    window.open_path(MESHES / "broken_open.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    window._on_scene(result)
    wide = next(f for f in result.scene.report.findings if f.code == "repair.wide_hole_filled")
    handlers = window.error_handlers()
    assert [action.id for action in actions_for(wide) if action.id in handlers] == [
        "show_location",
        "leave_open",
    ]
    steps = len(window.session.project.document.ops)

    handlers["leave_open"](as_error(wide, window.session.project.document))
    window.session.wait_for_idle()

    document = window.session.project.document
    assert len(document.ops) == steps, "geändert, nicht ergänzt"
    load = next(step for step in document.ops if step.op == "load")
    assert load.params["wide_holes"] is False
    assert load.params.get("mend", True) is True, "die kleinen Löcher gehen weiter zu"
    opened = window.session.evaluate_now()
    body = next(iter(opened.scene.objects.values()))
    assert body.mesh is not None and not body.mesh.is_watertight
    assert "give_thickness" in handlers, "der dritte Rückweg hat seinen Draht"


def test_resolving_intersections_changes_the_repair_step(window: MainWindow) -> None:
    """*Überschneidungen auflösen* rechnet denselben Reparaturschritt mit dem Haken.

    Der Befund steht an einem Schritt, der „aus" trägt — ein alter oder einer,
    an dem der Kunde den Haken genommen hat (Durchsicht 24.09.2026).
    """
    from app.ui.panels import actions_for, as_error

    window.open_path(MESHES / "broken_selfint.stl")
    window.session.wait_for_idle()
    first = next(iter(window.session.evaluate_now().scene.objects))
    handlers = window.error_handlers()
    window.session.apply(
        "Reparieren",
        [OperationDraft(op="repair", inputs=(first,), params={"self_intersections": False})],
    )
    window.session.wait_for_idle()
    crossing = window.session.evaluate_now()
    detected = next(
        f for f in crossing.scene.report.findings if f.code == "repair.self_intersections_detected"
    )
    assert "resolve_intersections" in [action.id for action in actions_for(detected)]
    steps = len(window.session.project.document.ops)

    handlers["resolve_intersections"](as_error(detected, window.session.project.document))
    window.session.wait_for_idle()

    document = window.session.project.document
    assert len(document.ops) == steps
    assert document.ops[-1].params["self_intersections"] is True
    resolved = window.session.evaluate_now()
    assert "repair.self_intersections" in {f.code for f in resolved.scene.report.findings}


def test_a_chosen_finding_survives_a_second_report(window: MainWindow) -> None:
    """Eine Wahl des Kunden überschreibt die Vorauswahl nicht (§2.4).

    Befunde kommen nach — die G-Code-Gegenprobe, die Kollisionsprüfung. Wer
    inzwischen selbst eine Zeile gewählt hat, behält sie; eine Vorauswahl, die
    sich über eine getroffene Wahl legt, wäre schlimmer als gar keine.

    Das Modell kommt zweimal: Das erste liegt seit dem 03.09.2026 aufgesetzt
    und mittig, und seit dem 14.09.2026 begrüßt eine STL ohne den Befund über
    das Verschweißen — der Bericht wäre leer, und eine Wahl gäbe es nicht.
    Das zweite landet mit ausgeschalteten Haken unter der Platte und bringt
    den Befund (sonst läge es seit dem 28.09.2026 an einer freien Stelle).
    """
    window.open_path(MESHES / "block_with_rounded_edge.stl")
    window.session.wait_for_idle()
    window.open_path(MESHES / "block_with_rounded_edge.stl")
    window.session.wait_for_idle()
    keep_the_files_place(window)
    window._on_scene(window.session.evaluate_now())
    assert window.report.list.count(), "ohne Befund prüft dieser Test nichts"

    window.report.list.setCurrentRow(0)
    standing = window.report.list.currentItem().data(Qt.ItemDataRole.UserRole).code

    window.report._preselect()

    kept = window.report.list.currentItem().data(Qt.ItemDataRole.UserRole).code
    assert kept == standing, "die Vorauswahl hat eine getroffene Wahl überschrieben"


def test_a_double_click_on_a_folded_step_says_where_the_single_ones_are(
    qt_app: QApplication,
) -> None:
    """Eine Geste, die sechs Touren lehren, darf nicht stumm bleiben (Regel 17).

    Ein Doppelklick im Verlauf öffnet den Schritt — außer der Schritt fasst
    mehrere Operationen zusammen: Dann trägt die Zeile keine ``UserRole``, denn
    welche der vier sollte sich öffnen. Der Tooltip der Liste verspricht die
    Geste trotzdem ohne Einschränkung, und sechs der neun Beispieltouren lehren
    sie als *den* Weg zum Ändern.

    Geprüft wird über das Signal der Liste und nicht über ``_on_activated``:
    Was ein Doppelklick auslöst, entscheidet die Verbindung, und die ist Teil
    der Zusage.
    """
    from app.core.types import Document, Transaction
    from app.ui.panels import HistoryPanel

    document = Document(format_version=7, app_version="0.0.1")
    document.transactions.append(Transaction(id=1, title="Bohrung setzen", ops=(1,)))
    document.transactions.append(Transaction(id=2, title="Teilung in vier", ops=(2, 3, 4, 5)))

    panel = HistoryPanel()
    panel.show_document(document)

    notes: list[str] = []
    opened: list[int] = []
    panel.noteRequested.connect(notes.append)
    panel.operationActivated.connect(opened.append)

    einzeln = panel.list.item(0)
    assert einzeln.text() == "1  Bohrung setzen"
    panel.list.itemDoubleClicked.emit(einzeln)
    assert opened == [1], "ein einzelner Schritt öffnet sich weiterhin"
    assert not notes

    gefaltet = panel.list.item(1)
    # Der Titel steht dran, und mehr sagt diese Zeile nicht zu: Seit die
    # Oberpunkte einklappen, trägt sie davor ein Dreieck (▸/▾). Ein
    # Gleichheitsvergleich hätte hier den Ist-Zustand festgeschrieben statt
    # der Zusage — und die lautet, dass ein Sammelschritt keine einzelne
    # Operation öffnet.
    assert "Teilung in vier" in gefaltet.text(), gefaltet.text()
    panel.list.itemDoubleClicked.emit(gefaltet)
    assert opened == [1], "ein Sammelschritt öffnet keine einzelne Operation"
    assert notes, "der Doppelklick blieb stumm — die Touren lehren ihn trotzdem"
    assert "einzeln" in notes[0], notes[0]


def test_a_group_starts_folded(qt_app: QApplication) -> None:
    """Ein Oberpunkt zeigt seine Teilschritte erst auf Wunsch.

    **Roberts Anweisung vom 30.08.2026:** „oberpunkte im verlauf auch noch
    einklappen, damit es nicht zu voll wird". Ein Verlauf, der jeden
    Teilschritt zeigt, ist nach zehn Handlungen eine Wand aus Zeilen, und die
    eine, die man sucht, steht irgendwo darin.

    Das Dreieck ist die zweite Kodierung neben der Einrückung (Regel 18): Ein
    Bildschirmleser liest keine Leerzeichen vor.
    """
    from app.core.types import Document, Transaction
    from app.ui.panels import HistoryPanel

    document = Document(format_version=7, app_version="0.0.1")
    document.transactions.append(Transaction(id=1, title="Teilung in vier", ops=(1, 2, 3, 4)))

    panel = HistoryPanel()
    panel.show_document(document)

    oben = panel.list.item(0)
    assert oben.text().startswith("▸"), f"kein Zeichen für den zugeklappten Punkt: {oben.text()!r}"
    versteckt = [panel.list.item(row).isHidden() for row in range(1, panel.list.count())]
    assert all(versteckt), f"Teilschritte stehen offen, obwohl zugeklappt: {versteckt}"


def test_a_click_unfolds_and_folds_again(qt_app: QApplication) -> None:
    """Ein Klick klappt auf, der nächste zu — ohne Rückfrage.

    Regel 19: Einklappen nimmt nichts weg, es zeigt nur weniger. Ein Dialog
    davor wäre eine Bestätigung für etwas, das der nächste Klick zurückholt.
    """
    from app.core.types import Document, Transaction
    from app.ui.panels import HistoryPanel

    document = Document(format_version=7, app_version="0.0.1")
    document.transactions.append(Transaction(id=1, title="Teilung in vier", ops=(1, 2, 3, 4)))

    panel = HistoryPanel()
    panel.show_document(document)
    oben = panel.list.item(0)

    panel.list.itemClicked.emit(oben)
    assert oben.text().startswith("▾"), f"das Zeichen ist nicht mitgegangen: {oben.text()!r}"
    assert not panel.list.item(1).isHidden(), "der Klick hat nicht aufgeklappt"

    panel.list.itemClicked.emit(oben)
    assert oben.text().startswith("▸")
    assert panel.list.item(1).isHidden(), "der zweite Klick hat nicht zugeklappt"


def test_a_finding_unfolds_the_group_it_points_into(qt_app: QApplication) -> None:
    """**Die Stelle, an der der Umbau am ehesten still bricht** (V6).

    Ein Klick auf einen Befund führt zu seinem Schritt (``point_at``). Liegt
    der in einem eingeklappten Oberpunkt, wäre die Auswahl unsichtbar — der
    Klick sähe folgenlos aus, und genau das war der Befund, den V6 behoben
    hat. Eine versteckte Zeile auszuwählen ist dasselbe wie gar nichts zu tun.
    """
    from app.core.types import Document, Transaction
    from app.ui.panels import HistoryPanel

    document = Document(format_version=7, app_version="0.0.1")
    document.transactions.append(Transaction(id=1, title="Teilung in vier", ops=(1, 2, 3, 4)))

    panel = HistoryPanel()
    panel.show_document(document)
    assert panel.list.item(2).isHidden(), "der Aufbau war schon offen — der Test misst dann nichts"

    assert panel.point_at(3), "der Schritt wurde nicht gefunden"

    gewaehlt = panel.list.currentItem()
    assert gewaehlt is not None
    assert not gewaehlt.isHidden(), (
        "der Befund zeigt auf eine versteckte Zeile — für den Kunden ist der Klick damit folgenlos"
    )


def test_an_open_group_stays_open_across_a_rebuild(qt_app: QApplication) -> None:
    """Was der Kunde aufgeklappt hat, bleibt offen.

    ``show_document`` läuft nach jeder Änderung. Ein Verlauf, der dabei
    zuklappt, nähme dem Kunden gerade das, was er sich eben aufgemacht hat —
    und zwar in dem Moment, in dem er arbeitet.
    """
    from app.core.types import Document, Transaction
    from app.ui.panels import HistoryPanel

    document = Document(format_version=7, app_version="0.0.1")
    document.transactions.append(Transaction(id=1, title="Teilung in vier", ops=(1, 2, 3, 4)))

    panel = HistoryPanel()
    panel.show_document(document)
    panel.list.itemClicked.emit(panel.list.item(0))
    assert not panel.list.item(1).isHidden()

    document.transactions.append(Transaction(id=2, title="Bohrung setzen", ops=(5,)))
    panel.show_document(document)

    assert not panel.list.item(1).isHidden(), (
        "der Neuaufbau hat den Punkt zugeklappt, den der Kunde geöffnet hatte"
    )


def test_the_history_names_only_what_differs(qt_app: QApplication) -> None:
    """§26.4: die Herkunft steht dran, wo sie vom Üblichen abweicht.

    „(Nutzer)" an jeder Zeile ist in einem Projekt ohne Agenten an jeder
    Zeile — und was überall steht, liest niemand. Der Agent wird genannt.
    """
    from app.core.types import Document, Origin, Transaction
    from app.ui.panels import HistoryPanel

    document = Document(format_version=7, app_version="0.0.1")
    document.transactions.append(Transaction(id=1, title="Bohrung setzen", ops=(1,)))
    document.transactions.append(
        Transaction(id=2, title="Deckel erzeugen", ops=(2,), origin=Origin(by="agent"))
    )

    panel = HistoryPanel()
    panel.show_document(document)

    lines = [panel.list.item(row).text() for row in range(panel.list.count())]
    # Die führende Zahl ist die Schrittnummer und keine Herkunftsangabe: Sie
    # steht an jeder Zeile, die genau eine Operation vertritt, damit der
    # Fehlerdialog („Operation: 4") und der Verlauf dieselbe Zahl nennen. Was
    # dieser Test zusichert, ist die Abwesenheit eines *Kommentars* — „(Agent)"
    # steht an der zweiten Zeile und an der ersten nicht.
    assert lines[0] == "1  Bohrung setzen", "der Regelfall bleibt unkommentiert"
    assert "Agent" not in lines[0]
    assert "Agent" in lines[1]


def test_the_history_keeps_the_title_of_a_deleted_child(qt_app: QApplication) -> None:
    """Auch ein gelöschter Teilschritt bleibt für Menschen verständlich benannt."""
    from app.core.types import (
        Document,
        DocumentChange,
        DocumentState,
        Operation,
        Transaction,
    )
    from app.ui.panels import HistoryPanel, _op_title

    removed = Operation(id=1, op="drill_hole")
    remaining = Operation(id=2, op="rename_object")
    document = Document(format_version=17, app_version="0.1.3", ops=[remaining])
    document.transactions.extend(
        [
            Transaction(id="t1", title="Zwei Änderungen", ops=(1, 2)),
            Transaction(
                id="t2",
                title="Schritt löschen",
                ops=(),
                changes=DocumentChange(
                    before=DocumentState(edited_ops={1: removed}),
                    after=DocumentState(edited_ops={1: None}),
                ),
            ),
        ]
    )

    panel = HistoryPanel()
    panel.show_document(document)

    deleted = next(
        panel.list.item(row).text()
        for row in range(panel.list.count())
        if tr("gelöscht") in panel.list.item(row).text() and "1" in panel.list.item(row).text()
    )
    assert _op_title(removed.op) in deleted, "die Zeile zeigte nur eine Nummer"


def test_history_context_delete_uses_the_visible_multiple_selection(
    qt_app: QApplication,
) -> None:
    """Rechtsklick löscht dieselbe Mehrfachauswahl wie die Entf-Taste."""
    from app.core.types import Document, Operation, Transaction
    from app.ui.panels import HistoryPanel

    document = Document(
        format_version=17,
        app_version="0.1.3",
        ops=[Operation(id=1, op="drill_hole"), Operation(id=2, op="rename_object")],
        transactions=[
            Transaction(id="t1", title="Bohrung", ops=(1,)),
            Transaction(id="t2", title="Name", ops=(2,)),
        ],
    )
    panel = HistoryPanel()
    panel.show_document(document)
    panel.show()
    QApplication.processEvents()
    first = panel.list.item(0)
    second = panel.list.item(1)
    first.setSelected(True)
    second.setSelected(True)

    assert panel._operations_for_context(first) == (1, 2)

    panel.list.clearSelection()
    first.setSelected(True)
    assert panel._operations_for_context(second) == (2,)
    assert panel.selected_operations() == (2,), "der Rechtsklick ließ eine fremde Auswahl stehen"


def test_report_findings_wrap_instead_of_scrolling(qt_app: QApplication) -> None:
    """§2.7: die Sätze des Prüfberichts müssen ganz lesbar sein.

    Im schmalen rechten Bereich endeten sie mitten im Wort („…um die
    Materialtoleranz v") hinter einer horizontalen Bildlaufleiste —
    aufgefallen am Bildschirmfoto des Hauptfensters fürs Handbuch.
    """
    from PySide6.QtCore import Qt

    from app.ui.panels import ReportPanel

    panel = ReportPanel()
    assert panel.list.wordWrap()
    assert panel.list.textElideMode() == Qt.TextElideMode.ElideNone
    assert panel.list.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


def test_the_tool_strip_starts_with_every_bar_closed(qt_app: QApplication) -> None:
    """§2.4: im Ruhezustand zwei Zeilen, nicht fünf."""
    window = MainWindow(Session(), UiSettings())

    assert window.tools.active() is None
    assert not window.section_bar.isVisibleTo(window.tools)
    assert not window.split_bar.isVisibleTo(window.tools)


def test_opening_a_tool_shows_exactly_its_bar(qt_app: QApplication) -> None:
    window = MainWindow(Session(), UiSettings())
    window.tools.toggle("section")

    assert window.tools.active() == "section"
    assert window.section_bar.isVisibleTo(window.tools)
    assert not window.analysis_bar.isVisibleTo(window.tools), (
        "zwei gleichzeitig wären der alte Zustand"
    )


def test_a_second_tool_closes_the_first(qt_app: QApplication) -> None:
    window = MainWindow(Session(), UiSettings())
    window.tools.toggle("section")

    window.tools.toggle("analysis")

    assert window.tools.active() == "analysis"
    assert not window.section_bar.isVisibleTo(window.tools)


def test_closing_a_tool_takes_its_view_change_back(qt_app: QApplication) -> None:
    """Das Schließen ist die Rücknahme — deshalb braucht es kein „Kein Schnitt“."""
    window = MainWindow(Session(), UiSettings())
    window.tools.toggle("section")
    window.section_bar.axis.setCurrentIndex(1)

    window.tools.toggle("section")

    assert window.tools.active() is None
    assert window.section_bar.axis.currentIndex() == 0


def test_a_typed_cut_height_moves_the_plane(qt_app: QApplication) -> None:
    """Ziehen **und** tippen, nicht eines von beiden (Konzept P15 §4, E2).

    Ein Zug durch den Körper ist eine Suche; „schneide bei 12,5" ist eine Zahl.
    Der Regler bleibt die Wahrheit über die Position — geprüft wird deshalb,
    dass die getippte Höhe wirklich in der Ebene ankommt und nicht nur im Feld
    steht.
    """
    window = MainWindow(Session(), UiSettings())
    bar = window.section_bar
    bar.set_ranges({"x": (-40.0, 40.0), "y": (-40.0, 40.0), "z": (-40.0, 40.0)})
    bar.axis.setCurrentIndex(1)

    bar.readout.setValue(12.5)

    plane = bar.plane()
    assert plane is not None
    assert plane.position == pytest.approx(12.5)

    # Und andersherum: der Regler führt das Feld nach.
    bar.position.setValue(-70)
    assert bar.readout.value() == pytest.approx(-7.0)


def test_the_cut_slider_runs_along_its_own_axis(qt_app: QApplication) -> None:
    """Ein flaches Brett schneidet man in Z über acht Millimeter, nicht über
    achtzig.

    Vorher galt eine Spanne für alle drei Achsen, gebildet aus dem kleinsten
    und größten Wert über sämtliche. Ein Zug in die Reglermitte landete damit
    weit über dem Teil — der Regler hatte sich bewegt, und es war kein Schnitt
    zu sehen.
    """
    window = MainWindow(Session(), UiSettings())
    bar = window.section_bar
    bar.set_ranges({"x": (-40.0, 40.0), "y": (-25.0, 25.0), "z": (0.0, 8.0)})

    bar.axis.setCurrentIndex(bar.axis.findData("z"))
    assert bar.readout.minimum() < 0.0 <= 8.0 < bar.readout.maximum()
    assert bar.readout.maximum() < 20.0, "der Z-Weg gehört zur Dicke, nicht zur Länge"

    bar.axis.setCurrentIndex(bar.axis.findData("x"))
    assert bar.readout.maximum() > 40.0, "und der X-Weg zur Länge"


def test_switching_the_axis_keeps_the_cut_on_the_body(qt_app: QApplication) -> None:
    """Eine Position außerhalb des neuen Weges wäre ein Schnitt neben dem Teil."""
    window = MainWindow(Session(), UiSettings())
    bar = window.section_bar
    bar.set_ranges({"x": (-40.0, 40.0), "y": (-25.0, 25.0), "z": (0.0, 8.0)})

    bar.axis.setCurrentIndex(bar.axis.findData("x"))
    bar.readout.setValue(35.0)

    bar.axis.setCurrentIndex(bar.axis.findData("z"))
    assert 0.0 <= bar.readout.value() <= 8.0, "in die Mitte des neuen Weges"


def test_every_tool_button_carries_a_label(qt_app: QApplication) -> None:
    """Regel 18: welches Werkzeug offen ist, hängt nicht allein an einer Farbe."""
    window = MainWindow(Session(), UiSettings())

    titles = window.tools.tool_titles()

    # **Jedes** Werkzeug trägt sein Wort — die Zahl selbst prüft
    # ``test_interface_limits`` als Obergrenze (höchstens acht). Hier stand
    # ``== 8``, und damit hätte der Ausbau des Punkt-Radius-Pinsels einen
    # Test über *Beschriftungen* rot gemacht: Die Zusage ist „keines ohne
    # Wort", nicht „genau acht Stück".
    assert titles, "ohne Werkzeuge prüft dieser Test nichts"
    for key, title in titles.items():
        assert title.strip(), key


def test_the_language_picker_shows_names_not_codes(qt_app: QApplication) -> None:
    """„de" war die allererste Angabe, die ein neuer Benutzer zu sehen bekam."""
    from app.ui.first_run import FirstRunDialog

    dialog = FirstRunDialog(UiSettings())
    shown = [dialog.language.itemText(row) for row in range(dialog.language.count())]

    assert "Deutsch" in shown
    assert "English" in shown
    assert "de" not in shown


def test_the_chat_hint_offers_a_way_out(qt_app: QApplication) -> None:
    """§2.7: ein Hinweis, der nur feststellt, lässt den Benutzer stehen."""
    from app.ui.chat import ChatPanel

    panel = ChatPanel()

    panel.set_available(False)
    assert panel.setup.isVisibleTo(panel), "ohne Zugang führt ein Knopf dorthin"

    panel.set_available(True, backend="ollama")
    assert not panel.setup.isVisibleTo(panel), "mit Zugang gibt es nichts einzurichten"


def test_every_tool_has_a_symbol_and_keeps_its_label(qt_app: QApplication) -> None:
    """Regel 18: das Zeichen kommt neben den Text, nicht an seine Stelle."""
    from app.ui import icons

    window = MainWindow(Session(), UiSettings())

    for key, title in window.tools.tool_titles().items():
        button = window.tools._buttons[key]
        assert title.strip(), key
        assert not button.icon().isNull(), f"{key} hat kein Symbol"
        assert button.text().strip(), f"{key} hat seine Beschriftung verloren"
    assert len(icons.known()) >= len(window.tools.tool_titles())


def test_symbols_render_and_follow_the_text_colour(qt_app: QApplication) -> None:
    """Ein Satz Zeichen für beide Themen — sonst ist einer davon unsichtbar."""
    from app.ui import icons

    for name in icons.known():
        source = icons.svg_source(name, "#ff0000")
        assert source.startswith("<svg"), name
        assert "currentColor" not in source, f"{name} hängt an einer festen Farbe"
        assert "#ff0000" in source, name


def test_the_application_icon_carries_every_size(qt_app: QApplication) -> None:
    """Das Fenster-Symbol kommt aus der SVG-Quelle — leer hieße: Windows zeigt
    sein Standardbild, und niemand merkt es vor dem ersten Screenshot.
    """
    from app.ui import icons

    symbol = icons.application_icon()

    assert not symbol.isNull()
    assert len(symbol.availableSizes()) == len(icons.APPLICATION_ICON_SIZES)


def test_findings_carry_their_severity_as_a_shape(qt_app: QApplication) -> None:
    """Regel 18: die Form trägt den Schweregrad, die Farbe verstärkt ihn nur.

    Vorher stand ein „!" oder ein „·" im Text der Zeile. Das erfüllte die Regel,
    sah aber nach Behelf aus — und Warndreieck, Info-Kreis und Fehler-Achteck
    sind Zeichen, die niemand lernen muss.
    """
    from app.core.types import Finding
    from app.ui.panels import ReportPanel

    panel = ReportPanel()
    panel.add_findings(
        [
            Finding(code="a.b", severity="error", message="kaputt"),
            Finding(code="c.d", severity="warning", message="offen"),
            Finding(code="e.f", severity="info", message="dünn"),
        ]
    )

    assert panel.list.count() == 3
    for row in range(panel.list.count()):
        item = panel.list.item(row)
        assert not item.icon().isNull(), item.text()
        assert not item.text().startswith(("!", "·", "X")), "der Marker steckt jetzt im Zeichen"


def test_the_first_run_describes_every_tool_state_in_words(qt_app: QApplication) -> None:
    """„+" und „−" waren die kryptischste Stelle im allerersten Dialog.

    Das Wort ist geblieben, das Zeichen steht jetzt daneben — nicht statt
    seiner (Regel 18). Und der Installationspfad, der beim ersten Start keine
    Frage beantwortet, steht im Hinweis statt in der Zeile.
    """
    from PySide6.QtWidgets import QLabel

    from app.core import tools
    from app.ui.first_run import ToolRow

    states = tools.survey()
    assert states, "ohne Programme prüft dieser Test nichts"

    for state in states:
        row = ToolRow(state)
        words = [child.text() for child in row.findChildren(QLabel) if child.text()]
        assert any(
            word in ("gefunden", "bereit", "installiert", "nicht eingerichtet") for word in words
        ), words
        assert row.toolTip(), "wo es liegt, steht im Hinweis"
        assert not any(word.startswith(("+ ", "- ")) for word in words)


# --- Objektbaum (§18.8) ---------------------------------------------------------


def _with_two_objects(window: MainWindow) -> None:
    """Zwei Körper in der Szene, ausgewertet und im Baum.

    Zweimal laden statt einmal duplizieren: die Duplizierung verbraucht ihr
    Original und vergibt neue Nummern, und dann heißen die beiden nicht mehr
    obj_1 und obj_2.
    """
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window._on_scene(window.session.evaluate_now())


def test_hiding_takes_a_body_out_of_the_view_but_not_the_scene(window: MainWindow) -> None:
    """§18.8: ein Filter auf dem Bild, keiner auf der Szene."""
    _with_two_objects(window)

    window._on_visibility(("obj_1",), False)

    assert window.viewport.hidden == frozenset({"obj_1"})
    assert "obj_1" in window.session.last_result.scene.objects, "gerechnet wird er weiter"

    window._on_visibility(("obj_1",), True)
    assert window.viewport.hidden == frozenset()


def test_a_hidden_body_says_so_in_words(window: MainWindow) -> None:
    """Regel 18: eine ausgegraute Zeile allein wäre Farbe als einzige
    Kodierung."""
    _with_two_objects(window)
    window._on_visibility(("obj_1",), False)

    labels = [
        window.object_tree.tree.topLevelItem(index).text(0)
        for index in range(window.object_tree.tree.topLevelItemCount())
    ]
    hidden = [text for text in labels if "ausgeblendet" in text]
    assert len(hidden) == 1, labels


def test_isolating_hides_the_rest_and_the_same_entry_brings_it_back(
    window: MainWindow,
) -> None:
    _with_two_objects(window)

    window._on_isolate(("obj_1",))
    assert window.viewport.hidden == frozenset({"obj_2"})

    window._on_isolate(("obj_1",))
    assert window.viewport.hidden == frozenset()


def test_isolating_a_hidden_body_isolates_instead_of_revealing(
    window: MainWindow,
) -> None:
    """Beschriftung und Wirkung teilen sich jetzt eine Antwort (§18.8).

    Rechtsklick auf einen bereits **ausgeblendeten** Körper bot „Alles andere
    ausblenden" — und die Wirkung war „alles einblenden": Beide Seiten lasen
    dasselbe Feld mit verschiedener Frage (Gesamtreview 25.08.2026, I-6).
    """
    _with_two_objects(window)
    window._apply_hidden(frozenset({"obj_2"}))

    window._on_isolate(("obj_2",))
    assert window.viewport.hidden == frozenset({"obj_1"}), (
        "wer ein verstecktes Teil isoliert, will es sehen — nicht alles"
    )

    window._on_isolate(("obj_2",))
    assert window.viewport.hidden == frozenset(), "derselbe Eintrag holt alles zurück"


def test_the_palette_refuses_a_locked_choice_with_the_reason(window: MainWindow) -> None:
    """Gesperrt bleibt gesperrt, auch über die Pfeiltasten (Regel 19).

    Die Liste sperrt ihre Zeilen, aber die Tastatur sprang auf eine gesperrte,
    und Enter führte sie aus — „Gitter füllen" auf leerer Szene öffnete die
    modale Sackgasse (Gesamtreview 25.08.2026, I-3). Der Grund geht jetzt in
    die Statuszeile, gestartet wird nichts.
    """
    launched: list[str] = []
    window.launch_operation = lambda spec: launched.append(spec.name)  # type: ignore[method-assign]

    available, reason = window._palette_availability("lattice_fill")
    assert not available and reason, "auf leerer Szene ist die Wahl gesperrt, mit Grund"

    window._run_palette_choice("lattice_fill")
    assert launched == [], "eine gesperrte Wahl startet nichts"
    assert window.status_message.text() == reason, "der Grund steht in der Zeile"

    window._run_palette_choice("create_box")
    assert launched == ["create_box"], "eine freie Wahl startet wie bisher"


def test_an_operation_without_a_menu_entry_is_not_simply_allowed(window: MainWindow) -> None:
    """Keine Menü-Action zu haben heißt nicht, dass alles geht.

    ``_palette_availability`` las die Sperre aus der Action, die auch das Menü
    ausgraut — richtig, solange jede Operation eine hat. ``action is None``
    ergab „erlaubt", und das ist eine Annahme über den Bestand, keine über die
    Sache: Die zusammengelegten Zwillinge haben schon heute keinen eigenen
    Eintrag, und sobald eigene Bausteine in den Katalog wandern statt in die
    Menüleiste, hat **keiner** von ihnen einen. Dann bekäme jeder auf leerer
    Szene ein „erlaubt" und der Kunde die modale Sackgasse, gegen die der Test
    darüber gebaut wurde.

    Nachgestellt, indem der Eintrag entfernt wird — dieselbe Lage, die der
    Katalogumbau für die eigenen Bausteine dauerhaft herstellt.
    """
    launched: list[str] = []
    window.launch_operation = lambda spec: launched.append(spec.name)  # type: ignore[method-assign]

    removed = window._op_actions.pop("lattice_fill", None)
    assert removed is not None, (
        "ohne Eintrag im Register prüft dieser Test nur seinen eigenen Aufbau"
    )

    available, reason = window._palette_availability("lattice_fill")
    assert not available, "auf leerer Szene geht „Gitter füllen“ auch ohne Menüeintrag nicht"
    assert reason, "und der Grund steht dabei — sonst sucht der Kunde ihn bei sich"

    window._run_palette_choice("lattice_fill")
    assert launched == [], "gestartet wird nichts"


def test_a_locked_window_command_is_refused_with_the_reason(window: MainWindow) -> None:
    """Regel 19, der Nachbarzweig: auch ein Fensterbefehl bleibt gesperrt.

    ``_run_palette_choice`` bekam die Wache mit cc40aaa4; der Zweig für
    Fensterbefehle rief seinen Rückruf weiter direkt — die Tastatur sprang
    auf eine gesperrte Zeile, und Enter führte aus (Update-Review 25.08.,
    ce-Befund). ``palette_rows`` sperrte die Zeile längst richtig; nur der
    Vollzug fragte nie nach.
    """
    commands = window.window_commands()
    name = next(key for key in commands if window._palette_actions.get(key) is not None)
    action = window._palette_actions[name]
    ran: list[str] = []
    guarded = dict(commands)
    guarded[name] = (*commands[name][:2], lambda: ran.append(name))
    was_enabled = action.isEnabled()
    try:
        action.setEnabled(False)
        window._run_window_command(name, guarded)
        assert ran == [], "ein gesperrter Fensterbefehl startet nichts"
        assert window.status_message.text(), "der Grund steht in der Zeile"

        action.setEnabled(True)
        window._run_window_command(name, guarded)
        assert ran == [name], "frei heißt weiterhin: er läuft"
    finally:
        action.setEnabled(was_enabled)


def test_a_running_export_keeps_the_bar_when_the_evaluation_ends(window: MainWindow) -> None:
    """§2.8: Der Balken gehört dem Export, solange die Datei geschrieben wird.

    ``_anything_running`` fragte die Flagge seit je — gesetzt hatte sie nie
    jemand: Endete eine Auswertung während eines Exports, verschwand der
    Balken, und der Kunde hielt das Schreiben für beendet und schloss das
    Fenster (Update-Review, Fund 30).
    """
    window._exporting = True
    try:
        # **Wie der Export es tut, nicht wie der Test es könnte.** ``_export``
        # schaltet den Balken selbst an, bevor es die Flagge setzt; wer nur die
        # Flagge setzt, stellt eine Lage her, die im Betrieb nicht vorkommt.
        # Die Zusage lautet „bleibt", nicht „erscheint" — und seit die Anzeige
        # gestuft ist (§2.8), sind das zwei verschiedene Sätze: Ein Balken, den
        # noch niemand angeschaltet hat, kann nicht bleiben.
        window._set_progress_state(
            "export",
            active=True,
            text=tr("Exportiert wird … {name}").format(name="teil.3mf"),
        )
        window._on_busy(False)
        assert window.progress.isVisibleTo(window), "der Export trägt den Balken weiter"
        assert not window.cancel_button.isVisibleTo(window), (
            "und Abbrechen gibt es beim Export bewusst nicht (sein Docstring sagt warum)"
        )
    finally:
        window._exporting = False
        window._set_progress_state("export", active=False)
    window._on_busy(False)
    assert not window.progress.isVisibleTo(window), "ohne Export endet der Balken"


def test_a_pure_download_offers_its_cancel_button(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    """Der Abbruch eines Downloads braucht einen sichtbaren Knopf (§2.8).

    ``_on_busy`` zeigt ihn nur bei Auswertungen; ein reiner Download lief mit
    Balken und ohne erreichbares Abbrechen — ``_cancel_download`` hing an
    einem unsichtbaren Knopf, und kein Test fasste ihn an (Update-Review,
    Fund 30). Der Arbeiter wird nicht gestartet: geprüft wird die Anzeige,
    nicht das Netz.
    """
    started: list[Worker] = []
    monkeypatch.setattr(window._leash, "start", started.append)

    window.download_model("https://beispiel.invalid/halter.stl")
    assert started, "ohne angenommenen Arbeiter prüft der Test nur check_url"
    worker = started[-1]
    request.addfinalizer(lambda: _release_unstarted_worker(window, "_download_worker", worker))

    assert window._downloading
    assert window.cancel_button.isVisibleTo(window), "der Weg zum Abbruch ist sichtbar"

    window._download_stopped()
    assert not window._downloading
    assert not window.cancel_button.isVisibleTo(window), "mit dem Download geht der Knopf"


def test_a_flashed_area_gets_opened_before_it_lights_up(window: MainWindow) -> None:
    """Ein zugeklappter Abschnitt blinkt an einer Stelle, an der nichts steht.

    „Sehen Sie links in den Verlauf" nennt einen Bereich, und ein Rahmen für
    eine Sekunde beantwortet die Frage, ohne sie zu stellen — solange der
    Bereich sichtbar ist. Die drei Karten der linken Spalte sitzen aber in
    einklappbaren Abschnitten (§2.5), und zugeklappt leuchtete der Rahmen um
    eine Kopfzeile auf, unter der nichts zu sehen ist. Für den Prüfbericht war
    das längst bedacht — er wird über seinen Reiter nach vorn geholt —, für
    die andere Bauart nicht.

    Dieselbe Frage stellt der Agent: Seine Rücknahme-Warnung zeigt über
    ``show_history`` in den Verlauf (H-1).

    Gefragt wird mit ``isVisibleTo``: ``isVisible()`` meldet in einem nie
    gezeigten Fenster immer ``False`` und beantwortet damit eine andere Frage
    als die gestellte.
    """
    from PySide6.QtWidgets import QToolButton

    wrapper = window.history_panel.parentWidget()
    assert wrapper is not None, (
        "der Verlauf steckt in einem Abschnitt — sonst prüft das hier nichts"
    )
    heading = next(
        child
        for child in wrapper.children()
        if isinstance(child, QToolButton) and child.objectName() == "sectionHeading"
    )

    heading.setChecked(False)
    assert not window.history_panel.isVisibleTo(wrapper), "zugeklappt ist zugeklappt"

    window._flash_area("history")

    assert heading.isChecked(), "der Abschnitt geht auf, bevor der Rahmen leuchtet"
    assert window.history_panel.isVisibleTo(wrapper), "und der Verlauf steht wirklich da"


def test_a_tour_can_point_at_both_toolbars(window: MainWindow) -> None:
    """Formen und Explosion werden dort hervorgehoben, wo ihre Knöpfe stehen."""
    window._flash_area("toolbar")
    assert "border" in window.toolbar.styleSheet()

    window._flash_area("tools")
    assert "border" in window.tools.styleSheet()


def test_a_typed_name_gets_the_project_suffix(window: MainWindow) -> None:
    """„Speichern unter" erzwingt die Projektendung (Gesamtreview A2).

    ``save_project`` schrieb jede Endung klaglos, und ``open_path`` verzweigt
    strikt über sie: Eine als ``halter.stl`` gespeicherte Projektdatei wurde
    beim Öffnen als Fremdmodell gelesen — „Dieses Dateiformat kann nicht
    gelesen werden", über der eigenen Datei. Angehängt und nicht ersetzt.
    """
    from app.ui.main_window import _as_project_path

    assert _as_project_path("halter").name == "halter.p3d"
    assert _as_project_path("halter.stl").name == "halter.stl.p3d"
    assert _as_project_path("halter.p3d").name == "halter.p3d"
    assert _as_project_path("Halter 2.5").name == "Halter 2.5.p3d"
    assert _as_project_path("HALTER.P3D").name == "HALTER.P3D", "Großschreibung bleibt"


def test_the_tree_names_the_step_a_body_came_from(window: MainWindow) -> None:
    """§18.8: Herkunft aus Operation und Transaktion."""
    _with_two_objects(window)

    tip = window.object_tree.tree.topLevelItem(0).toolTip(0)
    assert "aus Operation" in tip
    assert "Modell laden" in tip, tip


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_the_tree_explains_editability_without_cad_vocabulary(
    window: MainWindow, kind: str
) -> None:
    """Die Körperart nennt die Folge, nicht den Namen des Rechenkerns."""
    _needs_the_exact_kernel()
    window.session.apply(
        "Werkstück",
        [
            OperationDraft(
                op="create_brep_box" if kind == "brep" else "create_box",
                params={"name": "Werkstück"},
            )
        ],
    )
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    assert result.scene.objects["obj_1"].kind == kind
    window.object_tree.show_scene(result, window.session.project.document)

    item = window.object_tree.tree.topLevelItem(0)
    assert item.text(0) == "Werkstück"
    assert "Flächen und Kanten bearbeitbar" in item.toolTip(0)
    assert ("echte Kurven" if kind == "brep" else "geraden Teilstücken") in item.toolTip(0)
    customer_text = f"{item.text(0)} {item.toolTip(0)}".casefold()
    assert "b-rep" not in customer_text
    assert "exakt" not in customer_text
    assert "normal" not in customer_text


def test_removing_an_object_and_taking_it_back(window: MainWindow) -> None:
    """Entf ist eine Operation, also holt ein Undo den Körper zurück."""
    _with_two_objects(window)
    window.session.apply("Entfernen", [OperationDraft(op="delete_object", inputs=("obj_2",))])
    window.session.wait_for_idle()
    assert set(window.session.evaluate_now().scene.objects) == {"obj_1"}

    window.session.undo()
    window.session.wait_for_idle()
    assert set(window.session.evaluate_now().scene.objects) == {"obj_1", "obj_2"}


@pytest.mark.parametrize(
    ("name", "chosen"),
    [
        ("union_objects", ("obj_1", "obj_2")),
        ("subtract_objects", ("obj_1", "obj_2")),
        ("place_on_bed", ("obj_1",)),
        ("delete_object", ("obj_1",)),
    ],
)
def test_a_fieldless_operation_on_exact_bodies_runs_without_a_dialog(
    window: MainWindow, name: str, chosen: tuple[str, ...]
) -> None:
    """Regel 19: Ein Dialog mit null Feldern vor einer rücknehmbaren Handlung ist keiner.

    Gemessen am 21.09.2026 an zwei exakten Quadern: *Vereinigen*, *Abziehen*,
    *Auf das Bett setzen* und Entf öffneten einen Dialog ohne ein einziges
    Feld, mit einer Vorschau, die 2,2 s brauchte, um dasselbe zu zeigen — weil
    ein exakter Eingang allein als Grund galt. Der Grund ist die mögliche
    Umwandlung, und die gibt es hier nicht: Alle vier bleiben an exakten
    Körpern exakt (``test_exact_body_parity``: KEEP).
    """
    from tests.helpers import exact_kernel

    exact_kernel()
    window.session.start_new()
    window.session.apply(
        "Zwei Quader",
        [
            OperationDraft(op="create_brep_box", params={"width": 40.0, "height": 10.0}),
            OperationDraft(op="create_brep_box", params={"width": 20.0, "height": 30.0}),
        ],
    )
    assert window.session.wait_for_idle(60_000)
    window._on_scene(window.session.evaluate_now())
    assert all(entry.kind == "brep" for entry in window.session.last_result.scene.objects.values())
    window.object_tree.select_objects(chosen)
    QApplication.processEvents()
    before = len(window.session.project.document.ops)

    window.run_operation(REGISTRY.get(name))

    assert window._op_dialog is None, "kein Dialog: die Handlung hat nichts zu fragen"
    assert window.session.wait_for_idle(60_000)
    assert [step.op for step in window.session.project.document.ops][before:] == [name]
    if name != "delete_object":
        assert all(
            entry.kind == "brep" for entry in window.session.evaluate_now().scene.objects.values()
        ), "und der Körper ist danach noch exakt"


def test_a_fieldless_operation_that_mixes_body_kinds_still_shows_its_preview(
    window: MainWindow,
) -> None:
    """Die Gegenprobe: gemischte Eingänge gehen den Netzweg, und das wird gezeigt.

    *Vereinigen* an einem exakten und einem Netzkörper macht aus dem exakten
    ein Dreiecksmodell (``evaluate.exact_became_mesh``). Das ist die
    Umwandlung, vor der die Vorschau stehen muss — und der einzige Grund, aus
    dem eine feldlose Operation einen Dialog bekommt.
    """
    from tests.helpers import exact_kernel

    exact_kernel()
    window.session.start_new()
    window.session.apply(
        "Gemischt",
        [
            OperationDraft(op="create_brep_box", params={"width": 40.0, "height": 10.0}),
            OperationDraft(op="create_box", params={"width": 20.0, "height": 30.0}),
        ],
    )
    assert window.session.wait_for_idle(60_000)
    window._on_scene(window.session.evaluate_now())
    window.object_tree.select_objects(("obj_1", "obj_2"))
    QApplication.processEvents()
    before = len(window.session.project.document.ops)

    window.run_operation(REGISTRY.get("union_objects"))

    dialog = window._op_dialog
    assert dialog is not None, "gemischte Eingänge: die Umwandlung wird vorher gezeigt"
    assert len(window.session.project.document.ops) == before
    dialog.reject()
    window.session.wait_for_idle()
    assert window._op_dialog is None


def test_an_operation_dialog_does_not_lock_the_window(window: MainWindow) -> None:
    """§18.7: eine Vorschau, die man nicht umdrehen kann, ist eine halbe.

    ``exec()`` sperrte jede Kameraführung, solange der Dialog offen war — wer
    sehen wollte, ob die Bohrung auf der Rückseite austritt, musste abbrechen,
    drehen und von vorn anfangen. Der Beweis ist ein Lauf ohne Blockade: ein
    modaler Dialog ließe diesen Test hängen.
    """
    _with_two_objects(window)
    window.object_tree.tree.topLevelItem(0).setSelected(True)
    before = len(window.session.project.document.transactions)

    window.run_operation(REGISTRY.get("drill_hole"))

    dialog = window._op_dialog
    assert dialog is not None, "der Dialog steht offen und hat die Kontrolle zurückgegeben"
    assert dialog.isVisible()
    assert len(window.session.project.document.transactions) == before, (
        "solange nichts übernommen ist, bleibt der Stapel unberührt"
    )

    dialog.accept()
    window.session.wait_for_idle()

    assert window._op_dialog is None, "nach dem Schließen hält das Fenster keinen Dialog mehr"
    assert len(window.session.project.document.transactions) == before + 1


def test_a_rejected_dialog_changes_nothing(window: MainWindow) -> None:
    """Abbrechen heißt abbrechen — auch ohne Sperre."""
    _with_two_objects(window)
    window.object_tree.tree.topLevelItem(0).setSelected(True)
    before = len(window.session.project.document.transactions)

    window.run_operation(REGISTRY.get("drill_hole"))
    assert window._op_dialog is not None
    window._op_dialog.reject()
    window.session.wait_for_idle()

    assert window._op_dialog is None
    assert len(window.session.project.document.transactions) == before


def test_a_second_dialog_closes_the_first(window: MainWindow) -> None:
    """Zwei Vorschauen um denselben Viewport wären eine Frage ohne Antwort.

    Das verhinderte bisher die Sperre; ohne sie muss es die Stelle tun, die
    den Dialog öffnet.
    """
    _with_two_objects(window)
    window.object_tree.tree.topLevelItem(0).setSelected(True)

    window.run_operation(REGISTRY.get("drill_hole"))
    first = window._op_dialog
    assert first is not None

    window.run_operation(REGISTRY.get("drill_hole"))
    second = window._op_dialog

    assert second is not None
    assert second is not first, "der zweite Dialog ist ein anderer"
    assert not first.isVisible(), "und der erste ist zu"


def test_a_click_in_the_view_reaches_the_open_dialog(window: MainWindow) -> None:
    """Der ganze Weg: Dialog offen, ins Bild geklickt, Feld gefüllt.

    Drei Änderungen greifen hier ineinander — der Dialog sperrt nicht mehr, der
    Klick kommt an, und der Dialog nimmt entgegen. Einzeln geprüft sind sie
    schon; hier zählt, dass sie zusammen den Weg ergeben, den §18.5 meint.
    """
    _with_two_objects(window)
    window.object_tree.tree.topLevelItem(0).setSelected(True)
    window.run_operation(REGISTRY.get("drill_hole"))
    dialog = window._op_dialog
    assert dialog is not None

    window.viewport.pointPicked.emit((8.0, 3.0, 1.5))

    values = dialog.values()
    assert values["x"] == pytest.approx(8.0)
    assert values["y"] == pytest.approx(3.0)
    assert values["z"] == pytest.approx(1.5)
    dialog.reject()


def test_a_click_without_a_dialog_changes_no_values(window: MainWindow) -> None:
    """Ohne offenen Dialog ist ein Klick eine Auswahl und sonst nichts."""
    _with_two_objects(window)
    assert window._op_dialog is None

    window.viewport.pointPicked.emit((8.0, 3.0, 1.5))  # darf nichts auslösen

    assert window._op_dialog is None


def test_a_filament_colour_is_named_not_numbered(qt_app: QApplication) -> None:
    """§29: über dem Filamentfeld stand „#4A90D9".

    Das ist der genaue Wert und beschreibt für niemanden eine Spule im Regal.
    Grob mit Absicht: Filamentfarben sind Regalfarben, und „Kornblumenblau"
    wäre genauer und trotzdem nicht die Spule, die dasteht.
    """
    from app.ui.labels import colour_name

    assert colour_name("#4A90D9") == "Blau"
    assert colour_name("#000000") == "Schwarz"
    assert colour_name("#ffffff") == "Weiß"
    assert colour_name("#808080") == "Grau"
    assert colour_name("#d02020") == "Rot"
    assert colour_name("#8b5a2b") == "Braun", "dunkles Orange heißt Braun"
    assert colour_name("#ff9500") == "Orange"
    assert colour_name("kein-farbwert") == "kein-farbwert"


def test_a_standard_part_is_offered_by_its_name(qt_app: QApplication) -> None:
    """§24: „cable-5" erkennt niemand ohne die Normteiltabelle daneben.

    Der Schlüssel ist englisch und kurz, weil er ein Schlüssel ist. Im Dialog
    stand er als Beschriftung — und wer eine Kabeldurchführung setzen will,
    sucht „Rundkabel Ø5 mm".
    """
    from PySide6.QtWidgets import QComboBox

    from app.core.knowledge.parts.ops import op_name as part_op_name

    dialog = OperationDialog(REGISTRY.get(part_op_name("cable_gland")), ["obj_1"])
    try:
        editor = dialog._editors["size"]
        assert isinstance(editor, QComboBox)

        labels = [editor.itemText(index) for index in range(editor.count())]
        assert any("Rundkabel" in text for text in labels), "der Name steht da"
        assert "cable-5" not in labels, "und der Schlüssel nicht"

        # Der Wert bleibt der Schlüssel — sonst fände die Tabelle ihn nicht.
        values = [editor.itemData(index) for index in range(editor.count())]
        assert "cable-5" in values
    finally:
        dialog.deleteLater()


def test_a_choice_that_is_already_a_name_stays_as_it_is(qt_app: QApplication) -> None:
    """„M4", „PLA", „z" sind selbst schon der Name — daran gibt es nichts zu
    übersetzen."""
    from app.ui.labels import choice_label

    assert choice_label("M4") == "M4"
    assert choice_label("z") == "z"
    assert choice_label("gibt-es-nicht") == "gibt-es-nicht"


def test_technical_part_codes_are_explained_in_the_choice(qt_app: QApplication) -> None:
    """Buchsenvariante und Lagernummer reichen ohne Tabellenwissen nicht."""
    from app.ui.labels import choice_label

    short_insert = choice_label("M4S")
    bearing = choice_label("608")

    assert "M4" in short_insert and "mm" in short_insert and short_insert != "M4S"
    assert "608" in bearing and "8" in bearing and "22" in bearing and "mm" in bearing


def test_numbers_are_written_the_way_the_input_fields_write_them(
    qt_app: QApplication,
) -> None:
    """§19.3: zwei Schreibweisen derselben Zahl im selben Blick.

    Im Objektbaum standen die Maße mit Punkt, vierzig Pixel neben einem
    Eingabefeld mit Komma. Der Kern hat recht, wenn er mit Punkt rechnet — dort
    ist eine Zahl ein Wert. Nur kam sie so auch beim Nutzer an.

    Gefragt wird ``QLocale``, weil die Eingabefelder es ebenso tun: eine
    Quelle, oder das Problem kommt an der nächsten Stelle wieder.
    """
    from PySide6.QtCore import QLocale
    from PySide6.QtWidgets import QDoubleSpinBox

    from app.ui.labels import length, localised

    before = QLocale()
    try:
        QLocale.setDefault(QLocale("de"))
        spin = QDoubleSpinBox()
        spin.setDecimals(2)
        spin.setValue(60.0)

        assert "," in spin.text(), "das Eingabefeld schreibt deutsch"
        assert length(80.0) == "80,00 mm", "und der Text daneben auch"
        assert localised("1.5 · 2.25") == "1,5 · 2,25"

        QLocale.setDefault(QLocale("en"))
        assert length(80.0) == "80.00 mm", "auf Englisch bleibt der Punkt"
        spin.deleteLater()
    finally:
        QLocale.setDefault(before)


def test_the_history_shows_titles_not_registry_names(qt_app: QApplication) -> None:
    """§4.1: der Verlauf spricht deutsch, auch bei mehreren Ops je Schritt.

    Zwischen „Grundkörper" und „Versteifung" stand ``insert_screw_hole``.
    Beides sind dieselben Schritte — nur kam der eine Text aus der Transaktion
    und der andere aus dem Code.
    """
    from app.ui.panels import _op_title

    assert _op_title("drill_hole") == str(REGISTRY.get("drill_hole").title)
    assert "_" not in _op_title("drill_hole"), "kein Registername"
    # Eine Projektdatei aus einer neueren Version ist kein Grund für eine
    # leere Zeile.
    assert _op_title("gibt_es_nicht") == "gibt_es_nicht"


def test_a_history_row_names_its_steps_and_why_it_is_marked(session: Session) -> None:
    """Die Kurzhilfe einer Verlaufszeile sagt „Schritt 1", nicht „Ops 1".

    Und die Zeile mit dem Ausrufezeichen sagt, was es heißt: Hier hält die
    Kette an. Bis zum 22.09.2026 stand dort „t1 · Ops 1" — ein Wort aus dem
    Code, und das Zeichen davor blieb unerklärt (RM-084, Regel 18).
    """
    from app.ui.panels import HistoryPanel

    session.history.apply("Quader", [OperationDraft(op="create_box", params={"width": 20.0})])
    panel = HistoryPanel()
    document = session.project.document
    panel.show_document(document, stopped_at=document.ops[0].id)

    tip = panel.list.item(0).toolTip()
    assert "Ops" not in tip and "Schritt 1" in tip, tip
    assert panel.list.item(0).text().startswith("!")
    assert "hält die Kette an" in tip, tip


def test_delete_only_bites_where_a_selection_is_visible(window: MainWindow) -> None:
    """§2.6: „Entf" folgt dem Bereich, in dem die Auswahl sichtbar ist.

    Wer im Verlauf einen Schritt markierte und die Taste drückte, verlor den
    ausgewählten **Körper**. Jetzt hat der Verlauf seine eigene, gleich
    begrenzte Handlung; dieselbe Taste meint dort den gewählten Schritt.

    Geprüft wird der Geltungsbereich, nicht das Drücken: Keine der beiden
    Handlungen darf in den Bereich der anderen reichen.
    """
    deletes = [
        action
        for action in window.findChildren(QAction)
        if action.shortcut() == QKeySequence("Del")
    ]
    object_delete = next(action for action in deletes if action in window.object_tree.actions())
    history_delete = next(
        action for action in deletes if action in window.history_panel.list.actions()
    )

    assert object_delete.shortcutContext() == Qt.ShortcutContext.WidgetWithChildrenShortcut
    assert object_delete in window.viewport.actions(), "die Objektlöschung gilt auch in der Ansicht"
    assert object_delete not in window.history_panel.list.actions(), "aber nicht im Verlauf"
    assert history_delete.shortcutContext() == Qt.ShortcutContext.WidgetWithChildrenShortcut
    assert history_delete not in window.object_tree.actions(), (
        "die Schrittlöschung gilt nicht im Baum"
    )


def test_removing_a_history_step_asks_and_can_be_undone(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Roberts ausdrückliche Ausnahme: Vor dem Löschen steht eine Bestätigung.

    Der Dialog nennt zugleich den Ausweg. Nach dem bestätigten Löschen stellt
    Strg+Z denselben Schritt wieder her; ein Abbruch ließe das Dokument
    unangetastet.
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    op_id = window.session.project.document.ops[0].id
    shown: list[str] = []

    def reject(box: QMessageBox) -> int:
        shown.append(box.text())
        button = next(entry for entry in box.buttons() if entry.text() == tr("Abbrechen"))
        button.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", reject)

    window.remove_history_operations((op_id,))

    assert [entry.id for entry in window.session.project.document.ops] == [op_id]

    def accept(box: QMessageBox) -> int:
        shown.append(box.text())
        button = next(entry for entry in box.buttons() if entry.text() == tr("Löschen"))
        button.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", accept)

    window.remove_history_operations((op_id,))
    window.session.wait_for_idle()

    assert shown and "Strg+Z" in shown[0], "der Dialog nennt die Rücknahme"
    assert window.session.project.document.ops == []
    removed_rows = [
        window.history_panel.list.item(row)
        for row in range(window.history_panel.list.count())
        if tr("gelöscht") in window.history_panel.list.item(row).text()
    ]
    assert removed_rows and removed_rows[0].font().strikeOut(), (
        "die Ursprungszeile bleibt als gelöschte Geschichte sichtbar"
    )

    window.session.undo()
    window.session.wait_for_idle()
    assert [entry.id for entry in window.session.project.document.ops] == [op_id]


def test_history_deletion_warns_before_discarding_redo(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der eine Löschdialog nennt auch den abgeschnittenen Redo-Zweig."""
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    active_id = window.session.project.document.ops[0].id
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window.session.undo()
    window.session.wait_for_idle()
    assert window.session.history.can_redo
    undone_title = window._discarded_names()[0]
    shown: list[str] = []

    def reject(box: QMessageBox) -> int:
        shown.append(box.text())
        cancel = next(entry for entry in box.buttons() if entry.text() == tr("Abbrechen"))
        assert box.icon() == QMessageBox.Icon.Warning
        assert box.defaultButton() is cancel, "Abbrechen ist nicht die sichere Vorgabe"
        assert box.escapeButton() is cancel, "Escape muss den Vorgang abbrechen"
        cancel.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", reject)
    window.remove_history_operations((active_id,))

    assert window.session.history.can_redo, "Abbrechen verwarf den Redo-Zweig"
    assert undone_title in shown[0]
    assert "nicht mehr wiederholt werden" in shown[0]

    def accept(box: QMessageBox) -> int:
        remove = next(entry for entry in box.buttons() if entry.text() == tr("Löschen"))
        remove.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", accept)
    window.remove_history_operations((active_id,))
    window.session.wait_for_idle()

    assert not window.session.history.can_redo
    assert window.session.project.document.ops == []


def test_history_deletion_names_the_dependent_step(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regel 19: Wer „Quader anlegen“ löscht, liest, dass „Bohrung setzen“ mitgeht.

    Die Nachfrage sagte vorher nur „spätere abhängige Schritte“ (Handbuchbild
    *Einen Schritt zurücknehmen*, 3).
    """
    from app.core.scene.history import OperationDraft

    session = window.session
    session.apply(tr("Quader anlegen"), [OperationDraft(op="create_box", inputs=(), params={})])
    session.wait_for_idle()
    body = session.project.document.ops[0].outputs[0]
    session.apply(
        tr("Bohrung setzen"),
        [OperationDraft(op="drill_hole", inputs=(body,), params={"x": 0.0, "y": 0.0, "z": 10.0})],
    )
    session.wait_for_idle()
    first, second = (entry.id for entry in session.project.document.ops)
    shown: list[str] = []

    def reject(box: QMessageBox) -> int:
        shown.append(box.text())
        next(entry for entry in box.buttons() if entry.text() == tr("Abbrechen")).click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", reject)
    window.remove_history_operations((first,))

    assert shown, "die Nachfrage muss kommen"
    assert f"{second} {REGISTRY.get('drill_hole').title}" in shown[0], shown[0]
    assert "Strg+Z" in shown[0], "und der Rückweg"
    assert [entry.id for entry in session.project.document.ops] == [first, second]


def test_shortcuts_with_a_modifier_stay_window_wide(window: MainWindow) -> None:
    """Strg+B ist eindeutig gemeint, egal worauf der Fokus steht."""
    drill = next(
        action
        for action in window.findChildren(QAction)
        if action.shortcut() == QKeySequence("Ctrl+B")
    )

    assert drill.shortcutContext() == Qt.ShortcutContext.WindowShortcut


def test_an_operation_without_parameters_asks_nothing(window: MainWindow) -> None:
    """Regel 19: ein Fenster mit nur „OK" wäre die Bestätigung vor einer
    rücknehmbaren Handlung.

    Der Beweis, dass kein Dialog aufgeht, ist ein Lauf ohne Blockade: ein
    modales Fenster würde diesen Test hängen lassen.
    """
    _with_two_objects(window)
    window.object_tree.tree.topLevelItem(1).setSelected(True)
    before = len(window.session.project.document.transactions)

    window.run_operation(REGISTRY.get("delete_object"))
    window.session.wait_for_idle()

    assert len(window.session.project.document.transactions) == before + 1


def test_the_source_picker_offers_sources_and_not_bodies(qt_app: QApplication) -> None:
    """Eine Quelle ist kein Objekt.

    Beide standen hier in derselben Liste: wer „Modell laden" im Verlauf
    wieder öffnete, bekam eine Auswahl aus Körpern angeboten, wo eine Datei
    gemeint war. Gezeigt wird der Dateiname, übergeben die Kennung.
    """
    dialog = OperationDialog(
        REGISTRY.get("load"),
        {"obj_1": "Gehäuse"},
        values={"source": "src_1"},
        sources={"src_1": "halterung.stl", "src_2": "deckel.stl"},
    )
    combo = dialog._editors["source"]
    assert isinstance(combo, QComboBox)

    assert [combo.itemText(index) for index in range(combo.count())] == [
        "halterung.stl",
        "deckel.stl",
    ]
    assert not combo.isEditable(), "eine getippte Kennung war ein Weg, sich zu vertippen"
    assert dialog.values()["source"] == "src_1", "der gespeicherte Wert bleibt stehen"


def test_an_unknown_stored_value_is_kept_not_replaced(qt_app: QApplication) -> None:
    """Stillschweigend eine andere Datei einzusetzen wäre schlimmer, als eine
    unbekannte anzuzeigen."""
    dialog = OperationDialog(
        REGISTRY.get("load"),
        {},
        values={"source": "src_9"},
        sources={"src_1": "halterung.stl"},
    )
    assert dialog.values()["source"] == "src_9"


# --- Der Zustand, den die Oberfläche liest (§2.6, Regel 17) ---------------------


def test_operations_are_greyed_out_until_they_could_run(window: MainWindow) -> None:
    """Ein Menü, in dem alles anklickbar ist und die Hälfte mit „Bitte zuerst
    etwas auswählen" antwortet, lässt den Nutzer die Regeln erraten.
    """
    from app.core.registry import MENU_TWINS

    drilling = window._op_actions["drill_hole"]
    joining = window._op_actions["union_objects"]
    # Welcher Quader im Menü steht, sagt seit P2.8 die Maschine (der exakte,
    # wo der Kern da ist); der andere Zwilling hat keinen eigenen Eintrag.
    creating = window._op_actions[MENU_TWINS.get("create_box", "create_box")]

    assert not drilling.isEnabled(), "leere Szene, kein Körper zum Bohren"
    assert creating.isEnabled(), "anlegen geht immer"

    _with_two_objects(window)
    window.object_tree.tree.topLevelItem(0).setSelected(True)
    assert drilling.isEnabled()
    assert not joining.isEnabled(), "eine Vereinigung braucht zwei"

    window.object_tree.tree.topLevelItem(1).setSelected(True)
    assert joining.isEnabled()


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_selected_bodies_reveal_their_operations_in_the_window_on_the_right(
    window: MainWindow,
    theme: str,
) -> None:
    """Der kurze Weg zur Auswahl folgt Auswahl und Menüfreigabe gemeinsam.

    **Und er steht im Fenster rechts, bei den Maßen des Gewählten** (Konzept
    „Ein Ort für die Auswahl", A, 07.09.2026). Bis dahin lag er in einer
    eigenen Karte unter Bericht und Chat und beantwortete dieselbe Frage ein
    zweites Mal — an einer gewählten Senkung standen dieselben drei Handlungen
    dort als Knöpfe und hier als Felder.

    Was der Umzug nebenbei erledigt: Die Spalte teilt ihre Höhe mit nichts
    mehr, und die zweite Rechnung, die den Formatverlust der Berichtskarte
    verursachte, gibt es nicht mehr.
    """
    from app.ui.overlay import CARD
    from app.ui.panels import FILTER_FROM
    from app.ui.style import TARGET_SIZE

    window.action_theme(theme)
    panel = window.selection_operations
    # **Die Karte steht auch ohne Auswahl, aber leer bis auf die Bausteine**
    # (Entscheidung Robert, 18.09.2026). Sie verschwand bis dahin ganz, und
    # damit der einzige sichtbare Zugang zum Katalog; drei der
    # siebenundzwanzig Bausteine stehen frei und brauchen keinen Körper.
    assert not panel.isHidden()
    # ``isHidden`` und nicht ``isVisible``: Die Fixture zeigt das Fenster nie,
    # und offscreen meldet ``isVisible`` dann für **jedes** Widget False — die
    # zwei Zeilen waren bis zum 18.09.2026 trivial wahr (Regel, gemessen in
    # der zweiten Durchsicht).
    assert panel.search.isHidden(), "ohne Auswahl gibt es nichts zu durchsuchen"
    # ``isVisibleTo(panel)`` und nicht ``isHidden()``: Die Knöpfe stecken in
    # ihren Abschnitten, und versteckt ist der **Abschnitt** — das Widget
    # selbst meldet ``isHidden() == False``. Gefragt ist „würde es erscheinen,
    # wenn die Karte erschiene".
    assert not any(button.isVisibleTo(panel) for button in panel._buttons.values())
    # **Und der Filament-Schnellwähler steht dort nicht.** Sein leerer
    # Zustand („Das Filamentlager ist auch ohne Auswahl erreichbar.") war nie
    # zu sehen, solange die Karte ganz verschwand; seit sie bleibt, stünden
    # drei Blöcke über demselben Zustand — die Kopfzeile, sein Satz und der
    # Satz, der die Antwort trägt. Das Lager steht in der Kopfzeile und im
    # Menü.
    assert window.quick_filament.isHidden(), "ohne Auswahl gibt es nichts zu färben"
    # **Und das Merkmalfenster darüber schweigt.** Sein leerer Satz („Kein
    # Merkmal gewählt. Klicken Sie …") sagt dasselbe wie die zwei Zeilen der
    # Karte, nur ohne den Weg zu den Bausteinen — drei Sätze über einen
    # Zustand (gemessen am gebauten Fenster, 18.09.2026).
    assert window.feature_panel._empty.isHidden(), "die Karte darunter sagt es schon"
    assert window.feature_dock.isAncestorOf(panel), "die Handlungen wohnen im Fenster rechts"
    assert window.feature_dock.isAncestorOf(window.feature_panel), "und die Maße darüber"
    assert window.right.parentWidget() is window.right_card
    assert window.right_card.objectName() == CARD
    assert window.right_column.objectName() != CARD, "die Spalte selbst ist keine Karte"

    _with_two_objects(window)
    # **Die Filterzeile steht erst ab ``FILTER_FROM`` Befunden** — und eine
    # saubere STL trägt seit dem 14.09.2026 keinen mehr: Das Verschweißen
    # doppelter Punkte beim Lesen ist kein Befund (B16). Bis dahin brachten
    # die zwei cube_clean.stl drei Befunde mit, und die Zahl 260 weiter unten
    # maß dieses Bild statt der Regel. Die Befunde kommen jetzt aus einem
    # Netz, das welche hat; die Regel steht an den Rechtecken.
    window.session.import_model(MESHES / "broken_open.stl")
    window.session.wait_for_idle()
    window._on_scene(window.session.evaluate_now())
    first = window.object_tree.tree.topLevelItem(0)
    second = window.object_tree.tree.topLevelItem(1)
    first.setSelected(True)
    assert not panel.isHidden()
    assert not window.feature_dock.isHidden(), "das Fenster folgt der Auswahl"
    assert not panel._buttons["union_objects"].isEnabled()

    second.setSelected(True)
    assert panel._buttons["union_objects"].isEnabled()
    assert (
        panel._buttons["union_objects"].isEnabled()
        == window._op_actions["union_objects"].isEnabled()
    )
    assert window.overlay.right is window.right_column

    report = window.report
    assert report.list.count() >= FILTER_FROM, "ohne Filterzeile prüft dieser Test nichts"
    window.resize(1024, 720)
    window.show()
    QApplication.processEvents()
    for above, below in ((report.to_slicer, report.search), (report.search, report.list)):
        assert above.geometry().bottom() < below.geometry().top(), (
            "Bericht und Filter dürfen nicht übereinanderliegen: "
            f"Spalte={window.right_column.height()}, Bericht={window.right.height()}"
        )
    assert report.list.geometry().bottom() <= report.height(), "die Liste bleibt in der Karte"
    assert report.search.height() >= 32
    assert report.severity.height() >= 32
    assert report.to_slicer.height() >= TARGET_SIZE
    assert panel.catalog_button.isVisibleTo(window.feature_dock)

    # **Eine Karte, und die Maske lässt nichts daneben stehen.** Mit zwei
    # Karten nahm sie die Lücke dazwischen aus, damit dort das Modell zu sehen
    # war; jetzt gibt es keine Lücke mehr.
    assert len(window.right_column.card_rects()) == 1


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_the_left_column_shares_its_height_with_all_four(window: MainWindow, theme: str) -> None:
    """Der Abnahmenachweis zu P4: alle vier Abschnitte teilen, keiner nimmt.

    Vorher teilten nur drei. ``ObjectTree``, ``HistoryPanel`` und
    ``FilamentPanel`` beantworten den Raumvertrag aus ``overlay.py`` seit
    Langem, ``ParameterPanel`` nicht — und ``_share_room`` fragt nur, wer ihn
    hat; wer ihn nicht hat, „behält seine eigene Höhe". Genau das tat die
    Parameterkarte: Bei zehn Maßen stand sie auf 378 Bildpunkten und damit
    höher als Baum, Verlauf und Filamente zusammen (148, 58, 126 — gemessen am
    gebauten Fenster).

    Geprüft wird an Roberts vier Vorgaben vom 07.09.2026: Jeder bekommt
    wenigstens seinen Boden, keiner mehr als seinen Wunsch. Unterhalb der
    Mindesthöhe bleibt die Zuteilung am Boden; zusätzlicher freier Platz
    wird geteilt, bis alle ihren Wunsch bekommen.
    """
    from PySide6.QtTest import QTest

    from app.ui.overlay import MARGIN, extra_height
    from app.ui.panels import open_section

    window.action_theme(theme)
    _with_two_objects(window)
    for nummer in range(10):
        window.session.project.document.parameters[f"mass_{nummer}"] = Parameter(
            name=f"mass_{nummer}", value=float(nummer + 1), unit="mm"
        )
    window.parameters.show_document(window.session.project.document)
    # Der Filamentabschnitt steht zugeklappt in der Spalte; zugeklappt zählt er
    # in der Verteilung nicht mit (``_share_room`` fragt ``isVisibleTo``), und
    # Roberts Vorgabe „Filamente ist heute kaum zu sehen" gilt dem
    # aufgeklappten.
    open_section(window.filaments)
    window.show()

    karten = {
        "Objekte": window.object_tree,
        "Parameter": window.parameters,
        "Verlauf": window.history_panel,
        "Filamente": window.filaments,
    }
    zuteilung: dict[str, list[int]] = {name: [] for name in karten}
    knapp = geteilt = voll = False
    for height in (600, 900, 1100, 1400):
        window.resize(1024, height)
        QTest.qWait(20)
        host = window.overlay
        budget = host.height() - 2 * MARGIN - host._bottom_room() - extra_height(host.left)
        boeden = sum(karte.least_height() for karte in karten.values())
        wuensche = sum(
            max(karte.least_height(), karte.wanted_height()) for karte in karten.values()
        )
        for name, karte in karten.items():
            lage = f"{name} bei Fensterhöhe {height}"
            # **Gemessen wird die Zuteilung, nicht die gelegte Höhe.** Sie ist
            # der Gegenstand des Pakets: ``_share_room`` verteilt, und was eine
            # Karte daraus macht, ist ihre eigene Rechnung. Den Höhenvertrag
            # der Filamentkarte einschließlich Hinweis und Nachbarkarten
            # prüft ``test_filament_picker`` bei knappen und freien Höhen.
            raum = karte._room
            assert raum is not None, f"{lage}: keine Zuteilung, die Karte teilt nicht mit"
            boden, wunsch = karte.least_height(), karte.wanted_height()
            assert raum >= boden, f"{lage}: {raum} zugeteilt, Boden ist {boden}"
            assert raum <= max(boden, wunsch), (
                f"{lage}: {raum} zugeteilt, mehr als Boden {boden} und Wunsch {wunsch}"
            )
            if budget <= boeden:
                knapp = True
                assert raum == boden, f"{lage}: ohne freien Platz gilt der Boden"
            elif budget >= wuensche:
                voll = True
                assert raum == max(boden, wunsch), f"{lage}: der volle Wunsch passt"
            elif name == "Parameter":
                geteilt = True
                assert boden < raum < wunsch, f"{lage}: freier Platz muss geteilt werden"
            zuteilung[name].append(raum)

    # Und die Parameterkarte, die den Fall veranlasst hat, wächst mit dem
    # Fenster, statt bei jeder Höhe dasselbe zu nehmen. Vor dem Paket nahm sie
    # umgekehrt bei jeder Höhe dasselbe — ihre volle Inhaltshöhe.
    assert knapp and geteilt and voll, "die Probe muss alle drei Budgetlagen tatsächlich erreichen"
    hoehen = zuteilung["Parameter"]
    assert hoehen == sorted(hoehen), f"mehr Platz verkleinert die Parameterkarte: {hoehen}"
    assert hoehen[0] < hoehen[-1], f"die Parameterkarte folgt dem Platz nicht: {hoehen}"
    assert hoehen[-1] == window.parameters.wanted_height(), (
        "und bei genug Platz bekommt sie ihren vollen Wunsch"
    )


def test_the_report_tabs_stay_at_the_top_of_their_card(window: MainWindow) -> None:
    """Der Abnahmenachweis zu P1: Inhalt und Karte sind gleich hoch.

    Der Fehler, der das Paket veranlasst hat, war nicht zu wenig Platz,
    sondern zu viel: Der Deckel lag auf ``self.right``, dessen senkrechte
    Größenpolitik ``Ignored`` ist. Die Karte behielt ihre gestreckte Höhe, das
    einzige Kind durfte sie nicht füllen, und ein ``QVBoxLayout`` zentriert
    dann — die Reiter saßen mitten in einer hohen, leeren Karte. Eine
    Höhenzahl allein sieht das nicht: ``self.right.height() >= 260`` galt
    dabei die ganze Zeit.

    **Der Deckel ist mit dem Umzug ganz weggefallen** (Konzept A): Die Spalte
    trägt nur noch eine Karte und teilt ihre Höhe mit nichts mehr. Der Test
    bleibt trotzdem stehen, und zwar als Zusage statt als Fehlerprobe — er
    hält fest, dass es bei einer Karte bleibt und die Reiter oben stehen. Ein
    zweiter Bewohner der Spalte brächte die zweite Rechnung zurück, die den
    Fehler gemacht hat.
    """
    from PySide6.QtTest import QTest

    from app.ui.overlay import CARD_PADDING

    assert not hasattr(window, "selection_card"), "die Spalte trägt nur noch Bericht, Chat und Tour"

    _with_two_objects(window)
    window.show()

    for height in (600, 900, 1400):
        window.resize(1024, height)
        # **Gewartet, nicht nur Ereignisse verarbeitet.** Die frei gesetzte
        # Overlay-Geometrie steht erst nach Qts Layout-Ereignis endgültig;
        # ``processEvents`` allein ließ die Spalte über sechs Runden auf 22
        # Bildpunkten stehen, und der Test hätte Qts Zeitpunkt geprüft statt
        # der Höhe.
        QTest.qWait(10)
        for chosen in (False, True):
            window.object_tree.tree.topLevelItem(0).setSelected(chosen)
            QTest.qWait(10)
            lage = f"Fensterhöhe {height}, Auswahl {chosen}"
            top = window.right.mapTo(window.right_card, window.right.rect().topLeft()).y()
            assert top == CARD_PADDING, f"die Reiter stehen nicht oben — {lage}, Abstand {top}"
            rest = window.right_card.height() - window.right.height() - 2 * CARD_PADDING
            assert rest == 0, (
                f"die Karte ist höher als ihr Inhalt — {lage}, "
                f"Karte={window.right_card.height()}, Inhalt={window.right.height()}, "
                f"übrig={rest}"
            )
            unten = window.right_card.geometry().bottom()
            assert unten <= window.right_column.rect().bottom(), (
                f"die Karte steht über die Spalte hinaus — {lage}"
            )


def test_a_modifier_click_in_the_view_adds_a_body(window: MainWindow) -> None:
    """Testart „Anschluss": Kann das Panel es, oder **tut** es das Fenster?

    Dass die Ansicht die Taste meldet, steht in ``test_selection.py``, dass
    der Navigator sie liefert, in ``test_navigator.py``. Ob am Ende zwei Körper
    gewählt sind, hängt an einer dritten Stelle — ``_on_object_picked`` musste
    dafür vom Ersetzen auf Dazunehmen umgestellt werden, und genau das prüft
    dieser Test. Er ist der Grund, aus dem Roberts Befund entstand: Im Bild ging
    Mehrfachauswahl nicht, im Baum längst.
    """
    _with_two_objects(window)

    window._on_object_picked("obj_1")
    assert window.object_tree.selected_objects() == ("obj_1",)

    window._on_object_picked("obj_2", True)
    assert window.object_tree.selected_objects() == ("obj_1", "obj_2"), (
        "die Taste nimmt dazu, statt zu ersetzen"
    )

    # Und ein zweites Mal auf denselben nimmt ihn wieder heraus — wie im Baum,
    # wo ``ExtendedSelection`` das seit jeher tut.
    window._on_object_picked("obj_2", True)
    assert window.object_tree.selected_objects() == ("obj_1",)

    # Ohne Taste bleibt es beim Ersetzen.
    window._on_object_picked("obj_2")
    assert window.object_tree.selected_objects() == ("obj_2",)


def test_a_chosen_hole_puts_its_own_actions_in_front(window: MainWindow) -> None:
    """Die Anwendung reicht die Merkmalsart wirklich durch (Testart „Anschluss").

    Dass das Panel es kann, steht in ``test_selection_operations.py``. Ob das
    Fenster es *tut*, hängt an zwei Stellen: ``selected_feature_kind()`` im
    Aufruf von ``set_context`` und daran, dass die Merkmalsauswahl überhaupt
    die Freigaben nachführt (``_on_feature_selected`` ruft
    ``_update_actions``). Ohne diesen Test wäre die Zusage genau dort
    eingelöst, wo sie niemand sieht.
    """
    from app.ui.selection_operations import QUICK_BODY

    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(name for name, feature in entry.features.items() if feature.kind == "hole")
    panel = window.selection_operations

    def vorn() -> set[str]:
        return {name for name, button in panel._quick_buttons.items() if not button.isHidden()}

    window.object_tree.select_object(object_id)
    QApplication.processEvents()
    assert vorn() == set(QUICK_BODY), "ein Körper allein: bohren, aushöhlen, teilen"

    window.object_tree.select_feature(object_id, hole)
    QApplication.processEvents()
    # **Ausgeschrieben, nicht aus der Tabelle gelesen.** ``QUICK_FEATURES["hole"]``
    # nennt auch *Bohrung ändern*; die steht seit dem 09.09.2026 im
    # Merkmalsfenster darüber als Feld mit ihrem gemessenen Wert und bekommt
    # hier keinen zweiten Knopf. Eine Erwartung aus derselben Tabelle ginge mit
    # jeder künftigen Änderung mit und prüfte nichts mehr.
    # `slot_hole` steht seit dem 10.09.2026 **nicht** dabei: Es ist eine Zeile
    # mit Feldern im Merkmalsfenster darüber (`ACTION_ORDER`) und bekommt hier
    # deshalb keinen zweiten Knopf — dieselbe Regel wie bei *Bohrung ändern*.
    an_der_bohrung = {"countersink_hole", "plug_hole", "pattern_feature"}
    assert vorn() == an_der_bohrung, "die Bohrung bringt ihre eigenen mit"
    assert all(panel._buttons[name].isEnabled() for name in an_der_bohrung), (
        "und sie sind ausführbar, nicht nur graue Knöpfe"
    )

    window.object_tree.select_object(object_id)
    QApplication.processEvents()
    assert vorn() == set(QUICK_BODY), "ohne Merkmal zählt wieder die Menge"


def test_a_divider_of_an_organizer_answers_as_the_organizer(window: MainWindow) -> None:
    """Wer eine Trennwand anfasst, hat den Organizer gemeint — im ganzen Fenster.

    **Befund Robert, 18.09.2026:** „Baustein verschieben bei Trennwand
    organizer keine Wirkung." Ein Organizer bringt je Fach und je Trennwand
    Merkmale mit; an einer Trennwandfläche standen die Handlungen einer
    Fläche, und ein Zug am Griff wurde ein ``move_feature`` auf sie.

    Drei Stellen lösen das zusammen ein, und keine davon war durchs Fenster
    geprüft (Funde 1 und 2 der zweiten Durchsicht):

    * Das Merkmalfenster zeigt die Handlungen des **Schritts**
      (``part_step_of`` mit dem Merkmal, damit die Rollenregel greift), und
      die Karte darunter bleibt leer.
    * Der Weg zur Fachaufteilung steht als eigener Knopf dabei — sie ist ein
      Sammelparameter und kann kein Zahlenfeld werden.
    * Der **Griff** bleibt der der Fläche: ``_asks_for_the_part`` verlangt
      ``x/y/z`` am Schritt, und ein Organizer hat sie nicht. Ohne diese Frage
      hielte die Auswertung nach dem ersten Zug an.
    """
    from app.core.scene import OperationDraft

    window.session.apply("Organizer", [OperationDraft(op="create_organizer", params={})])
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    window._on_scene(result)

    body = next(iter(result.scene.objects.values()))
    divider = next(
        (
            name
            for name, entry in body.features.items()
            if entry.params.get("organizer_role") == "divider"
        ),
        None,
    )
    assert divider is not None, "die Voraussetzung: der Organizer hat Trennwände"

    # **Über den Baum, wie der Kunde klickt.** ``Viewport.select_feature``
    # ist die Anzeige; die Karte hängt an der Baumauswahl, und genau die Kette
    # soll hier ankommen.
    window.object_tree.select_feature(body.id, divider)
    QApplication.processEvents()

    # **Das Merkmalfenster spricht für den Schritt, die Karte schweigt.**
    assert window.selection_operations.isHidden(), (
        "an einer Trennwand gelten die Handlungen des Bausteins, nicht die der Fläche"
    )
    titles = {
        button.property("operationTitle") or button.text()
        for button in window.feature_panel.findChildren(QtWidgets.QPushButton)
        if not button.isHidden()
    }
    assert any("Fachaufteilung" in str(title) for title in titles), (
        f"der Weg zum Fächereditor fehlt: {sorted(str(title) for title in titles)}"
    )

    # **Und der Griff bleibt der der Fläche.** Ein Organizer kennt keine Lage;
    # wer ihm den Bausteingriff gäbe, ließe den Zug in einem angehaltenen
    # Schritt enden.
    feature = body.features[divider]
    assert not window.viewport.moves_as_a_part(feature), (
        "der Schritt kennt kein x/y/z — der Zug hätte kein Ziel"
    )
    assert window.session.last_result is not None
    assert window.session.last_result.complete, "und die Auswertung steht"


def test_a_chosen_edge_reaches_the_panel_as_its_own_level(window: MainWindow) -> None:
    """Der Kantenklick muss beim Panel als eigene Stufe ankommen (Testart „Anschluss").

    Dass die Karte an einer Kante leer bleibt, steht in
    ``test_selection_operations.py`` — der Test setzt ``feature_kind="edge"``
    aber selbst und umgeht damit die Kette, um die es geht. Die hängt an
    ``MainWindow.selected_feature_kind``: Der Kantenklick setzt die
    Baumauswahl auf den **Körper** zurück, und ohne die Frage nach
    ``Viewport.has_a_chosen_edge`` meldet sie „kein Merkmal" — an der Kante
    stünden dann wieder die zweiundvierzig Körperknöpfe.

    Gemessen über eine Mutationsprobe am 18.09.2026: Ohne diesen Test bleibt
    genau diese Zeile ungeprüft.
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id = next(iter(result.scene.objects))
    panel = window.selection_operations

    window.object_tree.select_object(object_id)
    QApplication.processEvents()
    assert window.selected_feature_kind() is None, "am Körper gibt es keine Art"
    # ``isHidden`` und nicht ``isVisible``: Qt lügt vor dem Anzeigen, und
    # offscreen wird nie etwas angezeigt (Regel).
    assert any(not button.isHidden() for button in panel._buttons.values()), (
        "die Voraussetzung: am Körper steht etwas"
    )

    # Eine echte Kante dieses Körpers — derselbe Schlüssel, den der Klick im
    # Bild liefert und den ``fillet_edges`` unter ``edges="named"`` liest.
    from app.core.geom import edges as mesh_edges
    from app.core.geom.mesh import as_mesh_data

    body = result.scene.objects[object_id]
    key = mesh_edges.edge_key(next(iter(mesh_edges.edges_of(as_mesh_data(body.mesh)))))
    # **Derselbe Zweischritt wie `Viewport._edge_click`: erst setzen, dann
    # melden — und nicht `_update_actions` von Hand.** Die erste Fassung
    # dieses Tests rief die Auffrischung selbst und umging damit genau das
    # Glied, um das es geht: `_on_edge_picked` rief sie nicht, und im Fenster
    # blieb die Karte auf ihrem letzten Stand (gemessen am gebauten Fenster).
    window.viewport.select_edge(object_id, key)
    window.viewport.edgePicked.emit(object_id, key)
    QApplication.processEvents()

    assert window.selected_feature_kind() == "edge", "die Kante ist eine Stufe für sich"
    assert all(button.isHidden() for button in panel._buttons.values()), (
        "und an ihr steht keine Körperoperation"
    )
    # **Auch der Filament-Schnellwähler nicht.** Er sitzt in derselben Karte,
    # und seine Bedingung fragt nach Merkmalen und Flächen — eine Kante steht
    # in keiner Baumzeile, also stand er unter dem Satz „Was sich hier tun
    # lässt, steht oben bei den Maßen" und bot eine Zuweisung an, die dem
    # ganzen Körper gilt (Fund der zweiten Durchsicht, 18.09.2026).
    assert window.quick_filament.isHidden(), "an einer Kante gibt es nichts zu färben"


def test_the_chamfer_marks_follow_the_panel_and_a_click_on_one_swaps_the_sides(
    window: MainWindow,
) -> None:
    """Welche Fläche welches Maß der Fase trägt, steht im Bild — und tauscht per Klick (P6.2).

    Der Weg der Kundin, Ende zu Ende am Fenster: Kante anklicken, bei *Fase
    anbringen* „Zwei Abstände" wählen. Im Bild steht je Fläche eine Maßlinie
    bis zur Berührlinie, beschriftet „1 · …" auf der Bezugsfläche (hier die
    Oberseite) und „2 · …" auf der Wand — die Ziffer ist die zweite Kodierung
    neben Farbe und Strichstärke, und die Statuszeile nennt beide Flächen in
    Worten. Ein Klick auf eine Marke schaltet *Seiten tauschen* im
    Merkmalfenster, und die Marken folgen. Übernommen wird **ein** Schritt mit
    den Werten aus dem Fenster; ein Strg+Z nimmt ihn zurück. Gleiche Breite
    nimmt die Marken weg, samt dem Satz in der Statuszeile.
    """
    from app.core.geom import edges as mesh_edges
    from app.core.geom.mesh import as_mesh_data
    from app.core.registry import REGISTRY
    from app.ui.viewport import FEATURE_EDGE_WIDTH, SELECTED_EDGE_WIDTH, chamfer_mark_texts
    from tests.render_fakes import RecordingRenderer

    renderer = RecordingRenderer(size=(900, 600))
    window.viewport.renderer = renderer
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    assert REGISTRY.has("chamfer_edges"), "ohne Fase im Register gibt es keine Marken"
    object_id, body = next(iter(result.scene.objects.items()))
    before = len(window.session.project.document.ops)
    kanten = mesh_edges.edges_of(as_mesh_data(body.mesh))
    oben_rechts = max(kanten, key=lambda kante: (kante.middle[2], kante.middle[0]))
    key = mesh_edges.edge_key(oben_rechts)
    top, right = float(oben_rechts.middle[2]), float(oben_rechts.middle[0])

    window.object_tree.select_object(object_id)
    QApplication.processEvents()
    window.viewport.select_edge(object_id, key)
    window.viewport.edgePicked.emit(object_id, key)
    QApplication.processEvents()
    assert window.viewport.chamfer_marks() is None, "an der Kante ist zuerst Verrunden scharf"

    title = str(REGISTRY.get("chamfer_edges").title)
    schema = {entry.name: entry for entry in REGISTRY.get("chamfer_edges").params.spec()}

    def feld(name: str) -> Any:
        wanted = f"{title} — {schema[name].title}"
        return next(
            widget
            for widget in window.feature_panel.findChildren(QWidget)
            if widget.accessibleName() == wanted
        )

    art, breite, tauschen = feld("mode"), feld("distance"), feld("flip_sides")
    breite.set_value(2.0)
    art.setCurrentIndex(art.findData("two_distances"))
    QApplication.processEvents()

    marks = window.viewport.chamfer_marks()
    assert marks is not None, "zwei Abstände: die Marken stehen"
    assert marks[0].reference and marks[0].reach == pytest.approx(2.0)
    assert marks[0].end[2] == pytest.approx(top), "die Breite liegt auf der Oberseite"
    assert marks[0].end[0] == pytest.approx(right - 2.0)
    assert marks[1].end[2] == pytest.approx(top - 1.0), "der zweite Abstand die Wand hinunter"
    assert renderer.item_of("chamfer-side:1").line_width == pytest.approx(SELECTED_EDGE_WIDTH)
    assert renderer.item_of("chamfer-side:2").line_width == pytest.approx(2.0 * FEATURE_EDGE_WIDTH)
    texts = chamfer_mark_texts(marks, {"mode": "two_distances"})
    assert renderer.labelled[-1] == texts
    assert texts[0].startswith("1 · ") and texts[1].startswith("2 · ")
    assert window.status_message.text() == "Fase: Fläche 1 oben, Fläche 2 rechts"

    # Ein Klick auf die äußere Hälfte der ersten Marke tauscht die Seiten.
    entry = window.session.last_result.scene.objects[object_id]
    offset = window.viewport._shown_offset(entry, window.session.last_result)
    end = tuple(float(marks[0].end[axis]) + float(offset[axis]) for axis in range(3))
    x, y, _depth = renderer.world_to_display(end)
    window.viewport._on_left_click(round(x), round(y))
    QApplication.processEvents()

    assert tauschen.isChecked(), "der Klick schaltet den Haken im Merkmalfenster"
    swapped = window.viewport.chamfer_marks()
    assert swapped is not None
    assert swapped[0].end[2] == pytest.approx(top - 2.0), "jetzt trägt die Wand die Breite"
    assert swapped[1].end[0] == pytest.approx(right - 1.0)
    assert window.status_message.text() == "Fase: Fläche 1 rechts, Fläche 2 oben"
    assert window.viewport.highlighted_edge() == (object_id, key), "die Kante bleibt gewählt"

    # Übernehmen wartet auf die dargestellte Vorschau, dann ein Schritt.
    window._feature_preview.stop()
    window._preview_feature_change()
    assert window.session.wait_for_idle(30_000)
    for _ in range(40):
        QApplication.processEvents()
    window.feature_panel._apply.click()
    assert window.session.wait_for_idle(30_000)
    assert len(window.session.project.document.ops) == before + 1
    step = window.session.project.document.ops[-1]
    assert step.op == "chamfer_edges"
    assert step.params["edges"] == "named" and step.params["edge_keys"] == key
    assert step.params["mode"] == "two_distances" and step.params["flip_sides"] is True
    assert float(step.params["distance"]) == pytest.approx(2.0)
    window.session.undo()
    assert window.session.wait_for_idle(30_000)
    assert len(window.session.project.document.ops) == before

    # Gleiche Breite: keine Bezugsfläche, keine Marken, kein Satz.
    window.viewport.select_edge(object_id, key)
    window.viewport.edgePicked.emit(object_id, key)
    QApplication.processEvents()
    art = feld("mode")
    art.setCurrentIndex(art.findData("two_distances"))
    assert window.viewport.chamfer_marks() is not None
    shown = list(window.viewport._chamfer_items)
    art.setCurrentIndex(art.findData("equal_distances"))
    QApplication.processEvents()
    assert window.viewport.chamfer_marks() is None
    assert all(item in renderer.removed for item in shown), "die Marken sind aus dem Bild"
    assert not window.status_message.text().startswith("Fase:")


def test_the_window_hands_the_panel_its_level_and_its_name(window: MainWindow) -> None:
    """Testart „Anschluss" zu P5: Stufe und Name kommen wirklich an.

    Dass das Panel nach der Stufe ein- und ausblendet, steht in
    ``test_selection_operations.py``; dass es die Zeile setzt, ebenso. Ob das
    **Fenster** beides liefert, hängt an ``selection_label()`` und daran, dass
    ``_update_actions`` sie mitgibt — genau die Stelle, an der die Zusage
    sonst unbemerkt ausbliebe.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(name for name, feature in entry.features.items() if feature.kind == "hole")
    panel = window.selection_operations

    window.object_tree.select_object(object_id)
    QApplication.processEvents()
    assert panel.summary.text() == entry.name, "am Körper steht sein Name, nicht seine Zahl"
    # **Und mit Auswahl kommt der Satz zurück.** Dort trägt die Karte
    # Handlungen, und er ist die richtige Auskunft: wie man an die Maße kommt.
    assert not window.feature_panel._empty.isHidden(), (
        "am Körper sagt er, wie man zu einem Merkmal kommt"
    )
    assert panel.chosen_level() == "", "und die Stufe ist die des Körpers"
    # Eine Handlung für alle Körper steht ohne Auswahl, nicht am gewählten
    # Körper (Robert, 27.09.2026).
    assert panel._buttons["arrange_bed"].isHidden(), "am Körper steht nichts für alle"

    window.object_tree.select_feature(object_id, hole)
    QApplication.processEvents()
    assert panel.chosen_level() == "hole", "die Merkmalsart kommt durch"
    assert panel.summary.text().startswith(f"{entry.name} · "), (
        f"an der Bohrung steht Körper und Merkmal: {panel.summary.text()!r}"
    )
    assert panel._buttons["arrange_bed"].isHidden(), (
        "und *Auf dem Bett anordnen* verschwindet, statt bedienbar dazustehen"
    )

    window.object_tree.select_object(None)
    QApplication.processEvents()
    assert panel.chosen_level() == "scene", "ohne Auswahl die Stufe der ganzen Szene"
    assert not panel._buttons["arrange_bed"].isHidden(), "und dort steht die Handlung für alle"


def test_the_selection_panel_uses_the_shared_launch_path() -> None:
    """Gestenoperationen dürfen vom neuen Weg nicht am Editor vorbei starten."""
    source = (Path(__file__).parent.parent / "app" / "ui" / "main_window.py").read_text("utf-8")
    build = source.split("def _build_central(", 1)[1].split("def ", 1)[0]
    assert "operationRequested.connect(self.launch_operation)" in build


def test_undo_and_redo_follow_the_stack(window: MainWindow) -> None:
    assert not window.undo_action.isEnabled()
    assert not window.redo_action.isEnabled()

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    assert window.undo_action.isEnabled()

    window.session.undo()
    window.session.wait_for_idle()
    assert window.redo_action.isEnabled()


def test_the_undo_sweep_warning_offers_the_history(window: MainWindow) -> None:
    """Die Rücknahme-Warnung des Agenten ist anklickbar (Gesamtreview H-1).

    ``agent.undo_sweeps`` existierte als Befund im Kern, aber die Oberfläche
    kannte ihn nicht: kein Eintrag in FINDING_ACTIONS, keine Handlung — der
    Kunde las „nimmt auch alle jüngeren mit" und konnte nirgends nachsehen,
    welche das sind.
    """
    from app.core.types import Finding
    from app.ui.panels import actions_for

    finding = Finding(code="agent.undo_sweeps", severity="warning", message="x")
    offered = actions_for(finding)
    assert offered, "die Warnung trägt eine Handlung"
    known = window.error_handlers()
    for action in offered:
        assert action.id in known, f"{action.id} hat keinen Handler"


def test_the_too_large_map_offers_the_operation_that_helps(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Hauptvorschlag zu „Modell zu groß" löst die Operation wirklich aus.

    Geprüft wird der **Klickweg**, nicht die Funktion: Der Handler wird über
    ``error_handlers()`` geholt und mit dem echten Fehler gerufen — so, wie
    der Dialog es tut. Ein Test, der ``run_operation`` direkt aufriefe, bliebe
    grün, wenn der Draht dazwischen fehlt, und genau der fehlte hier.

    ``decimate_mesh`` stand bis zum 30.08.2026 nur als Satz da, obwohl die
    Operation gleichen Namens im Register liegt — ein verschenkter Klickweg
    beim häufigsten Rat dieser Meldung.
    """
    from app.core.perceive.maps import MapTooLarge

    gerufen: list[str] = []
    monkeypatch.setattr(
        type(window), "run_operation", lambda self, spec, given=None: gerufen.append(spec.name)
    )

    fehler = MapTooLarge(triangles=9_000_000)
    angeboten = [action.id for action in fehler.suggestions]
    assert "decimate_mesh" in angeboten, "der Fehler bietet den Rat überhaupt an"

    handler = window.error_handlers()
    assert "decimate_mesh" in handler, "und die Oberfläche kennt ihn"
    handler["decimate_mesh"](fehler)

    assert gerufen == ["decimate_mesh"], f"die Operation wurde nicht ausgelöst: {gerufen}"


def test_an_auto_split_finding_opens_the_drawn_split_tool(
    window: MainWindow,
) -> None:
    """Der Berichtsknopf führt in die sichtbare manuelle Trennung (§2.7)."""
    from PySide6.QtWidgets import QPushButton

    from app.core.types import Finding

    window.report.add_findings(
        [
            Finding(
                code="split.no_plane",
                severity="warning",
                message="Keine belastbare Trennebene gefunden.",
            )
        ]
    )
    window.report.list.setCurrentRow(0)

    buttons = {
        button.text().replace("&", ""): button
        for button in window.report._offers.findChildren(QPushButton)
    }
    label = tr("An gezeichneter Linie trennen")
    assert label in buttons, f"angeboten wurden nur: {sorted(buttons)}"
    buttons[label].click()

    assert window.tools.active() == "split"
    assert window.split_bar.isVisibleTo(window.tools), "die Handlung öffnet ihre bedienbare Leiste"
    assert window.viewport._splitting, "Klicks im Viewport werden jetzt als Trennlinie gelesen"


def test_an_unreachable_address_opens_that_address_not_the_product_page(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Browser-Knopf öffnet die Adresse aus dem Fehler.

    **Und ausdrücklich nicht die Produktseite.** ``open_website`` liegt
    daneben und wäre die bequeme Verwechslung: Der Kunde wollte zu *seiner*
    Datei, deren Adresse er selbst eingegeben hat und die in ``values["url"]``
    mitreist.

    Geprüft am Klickweg über ``error_handlers()``, mit gemocktem
    ``QDesktopServices`` — die Zusage ist „diese Adresse geht auf", nicht
    „irgendetwas geht auf".
    """
    from PySide6.QtGui import QDesktopServices

    geoeffnet: list[str] = []

    def open_url(url) -> bool:
        geoeffnet.append(url.toString())
        return True

    monkeypatch.setattr(QDesktopServices, "openUrl", staticmethod(open_url))

    adresse = "https://beispiel.test/teil.stl"
    fehler = errors.ValidationError(
        "url",
        "Diese Adresse führt auf eine Webseite, nicht auf eine Datei.",
        value=adresse,
        constraint="web_page",
        values={"url": adresse, "name": "teil.stl", "type": "text/html"},
        suggestions=[errors.OPEN_IN_BROWSER],
    )

    handler = window.error_handlers()
    assert "open_in_browser" in handler, "die Oberfläche kennt den Rat"
    handler["open_in_browser"](fehler)

    assert geoeffnet == [adresse], f"geöffnet wurde: {geoeffnet}"


def test_every_offered_error_action_does_something(window: MainWindow) -> None:
    """Regel 17 hat zwei Hälften, und die zweite fehlte.

    Die Vorschläge standen als Knöpfe da, und kein einziger Aufrufer las
    aus, welcher gedrückt wurde — jeder schloss ein Fenster und tat sonst
    nichts. Was hier zählt: für jede Handlung, die ein Fehler vorschlägt,
    gibt es entweder einen Handler oder einen benannten Grund.

    **Die Liste der Ausnahmen ist auf drei geschrumpft**, und jede trägt ihren
    Grund: ``cancel`` ist das Schließen und kein Vorschlag; ``choose`` fragt der
    Kern über ``ctx.ask``, bevor er wirft; ``use_voxel_stage`` ist eine Stufe
    der Rückfallkette und kein Parameter, den ein Dialog setzen könnte (§17.2).
    ``correct_input`` und ``choose_printer`` standen hier, bis ihr Weg gebaut
    war — der erste öffnet den Schritt, der zweite führt in die
    Druckeinstellungen. ``retry`` und ``save_elsewhere`` sind verdrahtet, stehen
    aber weiter hier: Sie gelten einem **bestimmten** gescheiterten Schreiben
    und erscheinen nur, solange es eines gibt.
    """
    known = window.error_handlers()
    # ``retry`` und ``save_elsewhere`` hängen an einem gescheiterten Schreiben
    # und stehen darum nicht immer in ``known`` — angeboten werden sie genau
    # dann, wenn sie wirken können (``_WriteFailure``).
    postponed = {
        "use_voxel_stage",
        "choose",
        "cancel",
        "retry",
        "save_elsewhere",
        # Nur ein Importfehler mit den gelesenen Dateibytes kann diesen Namen
        # anwenden; der Katalog verdrahtet ihn deshalb am konkreten Fehler.
        "use_suggested_name",
        # Der externe Slicer muss Teilflächen auflösen bzw. sein natives
        # 32-Filament-Format auf mehrere Dateien verteilen. Solidon hat dafür
        # keine Operation; unhandled_advice zeigt beide Schritte als Text.
        "split_by_filament",
        "split_filament_files",
        # Die drei gelten dem Filamentlager und hängen an dessen Fehlerkarten:
        # ``reload`` am Revisionskonflikt (`InventoryView._rejected`),
        # ``restore_backup`` und ``set_aside_file`` an der unlesbaren Datei
        # (`InventoryView._read_handlers`, `FilamentPanel._read_handlers`).
        # Wie ``retry`` sind sie verdrahtet, wo der Fehler entsteht — das
        # Hauptfenster hat weder die Datei noch den Dialog dazu.
        "reload",
        "restore_backup",
        "set_aside_file",
        # Die Wege der lokalen Merkmalserkennung hängen am Dialog der Suche
        # (`LocalRecognitionDialog._failed`): Suchradius und Stelle kennt nur
        # er. ``decimate_mesh`` aus derselben Reihe führt das Fenster aus.
        "pick_elsewhere",
        "enlarge_radius",
        "shrink_radius",
        "repair_mesh",
    }

    for name, value in vars(errors).items():
        if not isinstance(value, errors.Action):
            continue
        assert value.id in known or value.id in postponed, (
            f"{name} wird angeboten, aber nichts führt sie aus"
        )


def test_the_saved_part_state_button_switches_every_step_at_once(
    window: MainWindow, tmp_path: Path
) -> None:
    """RM-138, Anschluss: Der Knopf am Befund rechnet wieder mit dem gespeicherten Stand.

    Der Kern kann es (``tests/test_recipes.py``); geprüft wird hier, dass die
    Anwendung es tut — der Befund beim Öffnen, sein Knopf, ein Schritt im
    Verlauf für beide Einsätze und ein Strg+Z zurück.
    """
    from app.core.errors import AppError
    from app.core.knowledge import profiles
    from app.core.knowledge.parts import check as part_check
    from app.core.knowledge.parts import recipe
    from app.core.scene.project import Project, save
    from app.core.types import Operation

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    try:
        recipe.register(recipe_with_halter(30.0, profile))
        document = recipe_document_seed()
        halter = Operation(
            id=2,
            op="insert_probe_halter",
            inputs=("obj_1",),
            outputs=("obj_1",),
            params={"z": 8.0},
        )
        document.ops.extend(
            [halter, dataclasses.replace(halter, id=3, params={"z": 8.0, "x": 5.0})]
        )
        saved = tmp_path / "halter.p3d"
        save(Project(document=document), saved)
        clean_recipe_globals("probe_halter")
        recipe.register(recipe_with_halter(50.0, profile))

        window.session.open_project(saved)
        finding = next(
            entry
            for entry in part_check.check(window.session.project.document)
            if entry.code == "parts.own_changed"
        )
        (action,) = finding.suggestions
        window.error_handlers()[action.id](AppError(title=finding.message))

        steps = [entry.op for entry in window.session.project.document.ops[1:]]
        assert steps == ["insert_probe_halter_travelled"] * 2
        assert window.session.modified
        window.session.undo()
        steps = [entry.op for entry in window.session.project.document.ops[1:]]
        assert steps == ["insert_probe_halter"] * 2
    finally:
        clean_recipe_globals("probe_halter", "probe_halter_travelled")


#: Kennungen, die absichtlich neben ``errors.py`` entstehen — sie gehören einem
#: Fenster, das seine Knöpfe selbst baut (der Support-Dialog), oder einem Rat,
#: den ``unhandled_advice`` als Satz zeigt. Wer hier etwas einträgt, sagt damit:
#: Diese Kennung braucht keine Konstante und keinen Handler.
#:
#: **Die Frage, die vor jedem neuen Eintrag steht** — und ohne sie wird diese
#: Menge zur Müllhalde, in die der nächste ``cancel_evaluation``-Fall bequem
#: hineinrutscht:
#:
#:     Gibt es irgendwo eine Handlung, die diese Kennung einlösen könnte?
#:     Wenn ja: Konstante und Verdrahtung, nicht diese Menge.
#:
#: Genau daran ist der Gründungsfall des Wächters gescheitert.
#: ``cancel_evaluation`` bot an, die laufende Teilung abzubrechen — und
#: ``Session.cancel_split`` gab es die ganze Zeit. Der Fehler war nicht
#: „kein Handler", sondern **dass niemand gefragt hat**.
#:
#: **Und diese Menge ist selbst schon einmal daran vorbeigelaufen.** Als sie
#: am 30.08.2026 von vier auf 32 Einträge wuchs, wurde sie **pauschal**
#: befüllt — die Regel darüber stand im selben Commit und wurde auf keinen
#: einzigen Namen angewandt. Der Release-Durchgang eine Stunde später fand
#: zwei, für die es sehr wohl eine Einlösung gab: ``decimate_mesh`` (die
#: Operation liegt im Register) und ``open_in_browser`` (die Adresse reist im
#: Fehler mit). Beide sind jetzt Konstanten mit Handler.
#:
#: Wer diese Menge erweitert, prüft **jeden** Namen einzeln. Eine Liste, die
#: in einem Zug entsteht, entsteht ungeprüft.
#:
#: Die zweite Gruppe darunter ist gemessen und nicht geraten: 32 Kennungen an
#: 44 Fundstellen, von denen 26 in ``suggestions=`` eines geworfenen Fehlers
#: stehen und **keine einzige** einen Handler hat. Das ist kein Befund, sondern
#: die Bauart: ``dialogs.unhandled_advice`` zeigt einen Vorschlag ohne Handler
#: als **Satz** — „ein Knopf ohne Wirkung ist schlimmer als keiner". Die
#: Handlung führt in all diesen Fällen der Nutzer selbst aus: eine Fläche
#: anklicken, einen Wert kleiner wählen, vorher aufräumen.
#:
#: ``primary=True`` trennt die beiden Gruppen **nicht** — nachgemessen tragen
#: ``sketch.use_all_regions``, ``sketch.pick_face`` und
#: ``texture.pick_cylinder`` es und sind trotzdem Selbstausführer. Das Feld
#: sagt „der naheliegendste Weg", nicht „das tut die Oberfläche für dich".
ACTIONS_WITHOUT_A_CONSTANT = {
    # Ein Fenster, das seine Knöpfe selbst baut (Support-Dialog).
    "retry_send",
    "save_report",
    "send_by_mail",
    # Räte, die der Nutzer selbst ausführt — als Satz gezeigt, nicht als Knopf.
    "check_input",
    "coarser_pitch",
    "fewer_iterations",
    "fix_parent",
    "open_sketch",
    "pick_face",
    "pick_feature",
    "pick_image",
    "pick_in_tree",
    "remesh_first",
    "repack_file",
    "sketch.check_position",
    "sketch.clear_axis_feature",
    "sketch.clear_up_to",
    "sketch.enter_height",
    "sketch.flip_plane",
    "sketch.pick_face",
    "sketch.pick_plane",
    "sketch.pick_round_feature",
    "sketch.use_all_regions",
    "sketch.use_global_plane",
    "smaller_bodies",
    "smaller_diameter",
    "texture.pick_cylinder",
    "texture.wrap_flat",
    "use_parts",
    "use_planar",
    "use_texture",
    "write_target",
    # Inline gebaut, weil der Satz die Zahl des Aufrufers meint („die feinste
    # Rasterweite", „die doppelte Kantenlänge") — aber verdrahtet: Der Handler
    # setzt ``values["reachable"]`` in den Schritt (Durchsicht 0.5.1).
    "use_reachable",
}


def test_no_error_action_is_invented_at_the_call_site() -> None:
    """Eine Kennung, die nur an ihrer Aufrufstelle steht, entgeht jeder Prüfung.

    Der Test darüber liest die **Konstanten** aus ``errors.py`` — gründlich,
    aber er sieht nur, was dort steht. ``session.split_bodies`` erzeugte seinen
    Vorschlag von Hand:

        Action("cancel_evaluation", _("Die laufende Teilung abbrechen"))

    Zwei Fehler in einer Zeile, und beide blieben jahrelang unsichtbar. Die
    Kennung hieß nach der **Auswertung** und meinte die Teilung — zwei Dinge,
    die beide abbrechbar sind. Und verdrahtet war sie nirgends, also wurde aus
    dem einzigen Vorschlag dieses Fehlers ein Satz zum Lesen: Der Kunde bekam
    den Rat, die Teilung abzubrechen, und keinen Weg, es zu tun. Dabei gibt es
    die Handlung (``Session.cancel_split``).

    Gefunden hat das kein Test, sondern eine Kontrolle von Hand am Ende eines
    Tages. Diese Prüfung ist die Antwort darauf: Sie liest den **Quelltext**,
    nicht das Modul — dieselbe Bauart wie der Wächter in ``test_leash.py``, der
    jeden Arbeiter findet, der an der Leine vorbei startet.
    """
    import ast

    constants = {value.id for value in vars(errors).values() if isinstance(value, errors.Action)}
    assert len(constants) > 15, "die Konstanten wurden nicht gelesen — der Test prüft nichts"

    invented: dict[str, str] = {}
    files = [path for path in Path("app").rglob("*.py") if path.name != "errors.py"]
    assert len(files) > 100, "die Quelldateien wurden nicht gefunden"
    for path in files:
        text = path.read_text(encoding="utf-8")
        if "Action(" not in text:
            continue
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, ast.Call):
                continue
            if not (isinstance(node.func, ast.Name) and node.func.id == "Action"):
                continue
            # **Beide Aufrufformen.** Hier stand ``or not node.args`` als
            # erste Bedingung, und damit übersprang der Wächter jeden Aufruf
            # ohne positionales Argument — also jedes ``Action(id="…", …)``.
            # Gemessen am 30.08.2026: Von 32 inline gebauten Kennungen sah er
            # **vier**; die übrigen 28 lebten außerhalb jeder Prüfung, darunter
            # die drei des Slicer-Wegs, deren Knöpfe nichts taten.
            #
            # Der Zusatz liest sich wie eine Vorsichtsmaßnahme („ohne
            # Argumente gibt es nichts zu prüfen") und war eine Ausnahme für
            # die halbe Aufrufform. **Ein Wächter ist so scharf wie seine
            # weiteste Ausnahme** — und die stand hier in einer Zeile, die
            # niemand als Ausnahme gelesen hat.
            named: ast.expr | None = node.args[0] if node.args else None
            for keyword in node.keywords:
                if keyword.arg == "id":
                    named = keyword.value
            if (
                isinstance(named, ast.Constant)
                and isinstance(named.value, str)
                and named.value not in constants
                and named.value not in ACTIONS_WITHOUT_A_CONSTANT
            ):
                invented[named.value] = f"{path}:{node.lineno}"

    assert not invented, (
        "Aktionskennung ohne Konstante in errors.py — sie entgeht damit der Prüfung "
        f"darüber: {invented}"
    )


#: Die Handlungen am Prüfbericht, die die **Lage** eines Körpers ändern, mit der
#: Verschiebung, die den Befund erzeugt. Eine Zeile je Knopf und nicht je
#: Befund: ``arrange.above_bed`` bietet zwei an, und beide müssen wirken.
LAGE_HANDLUNGEN = [
    ((0.0, 0.0, -15.0), "arrange.below_bed", errors.PLACE_ON_BED),
    ((0.0, 0.0, 150.0), "arrange.above_bed", errors.PLACE_ON_BED),
    ((0.0, 0.0, 150.0), "arrange.above_bed", errors.ARRANGE_ON_BED),
    ((400.0, 0.0, 0.0), "arrange.off_the_plate", errors.ARRANGE_ON_BED),
]


@pytest.mark.parametrize(
    ("offset", "code", "action"),
    LAGE_HANDLUNGEN,
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_every_placement_button_really_moves_the_bodies(
    window: MainWindow,
    offset: tuple[float, float, float],
    code: str,
    action: errors.Action,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die dritte Hälfte von Regel 17: der Handler muss auch *wirken*.

    ``test_every_offered_error_action_does_something`` prüft, dass jede
    angebotene Handlung einen Handler **hat** — und genau das war bei *Auf dem
    Bett anordnen* erfüllt, während der Knopf nichts tat. Er trug die Operation
    ohne Eingaben in den Stapel, und eine Operation mit variabler Objektzahl
    ohne Eingaben plant keine Ausgänge (``History._outputs_for``): Der Schritt
    stand im Verlauf, kein Körper bewegte sich, keine Meldung erschien. Robert
    hat es gemeldet, der Test blieb grün.

    Getroffen hat es den häufigsten Importfall überhaupt — eine 3MF aus Bambu
    Studio, Orca oder Elegoo führt Bettkoordinaten, ihre Körper liegen neben
    dem Bett, und dieser Knopf ist die Handlung, die dort hilft.

    Gedrückt wird der **echte Knopf** unter der Befundliste, nicht der Handler
    von Hand: Zwischen beiden liegen ``actions_for``, ``as_error`` und die
    Verdrahtung in ``_show_offers``, und die gehören zur Zusage.

    Über alle vier Lage-Handlungen und nicht nur über die eine, die einmal
    kaputt war: Sie hängen an denselben zwei Handlern, und ein
    Registername steht darin als Zeichenkette (siehe den Wächter darunter).
    Wer eine der Operationen auflöst, bricht hier zwei Knöpfe auf einmal.

    **Seit dem 11.09.2026 klagen die zwei Würfel in einer Zeile** — der
    Bericht bündelt gleiche Meldungen über Körper hinweg, und der Knopf an
    einer Sammelzeile fragt, für welche Körper er gelten soll. Der Dialog
    antwortet hier mit allen; geprüft bleibt, dass die Handlung wirkt.
    """
    from PySide6.QtWidgets import QPushButton

    from app.ui import panels

    monkeypatch.setattr(
        panels.BodyChoiceDialog, "ask", lambda parent, title, ids, names: tuple(ids)
    )
    _with_two_objects(window)
    window.session.apply(
        "Verschieben",
        [
            OperationDraft(
                op="translate_object",
                inputs=("obj_1",),
                params={"dx": offset[0], "dy": offset[1], "dz": offset[2]},
            )
        ],
    )
    window.session.wait_for_idle()
    result = window.session.last_result
    window.report.show_result(result, window.session.project.document)

    def where() -> dict[str, tuple[float, ...]]:
        scene = window.session.last_result.scene
        return {
            object_id: tuple(entry.mesh.bounds.minimum)
            for object_id, entry in scene.objects.items()
        }

    def klagen() -> set[str]:
        """Die Körper, für die dieser Befund gerade steht.

        Objektbezogen und nicht als bloße Kennung: ``_with_two_objects`` lädt
        zwei Würfel, und ein aus der Datei geladener Würfel steckt zur Hälfte
        unter der Platte — bei ``below_bed`` klagen also beide. *Auf das Bett
        setzen* behebt genau seinen eigenen (``consumes=1``), und das ist
        richtig; eine Zusicherung „der Befund ist weg" wäre hier eine über eine
        Operation, die es nicht gibt.
        """
        return {
            finding.object_id
            for finding in window.session.last_result.scene.report.findings
            if finding.code == code and finding.object_id is not None
        }

    assert "obj_1" in klagen(), (
        "der Befund muss für den verschobenen Körper dastehen, sonst prüft das nichts: "
        f"{[f.code for f in result.scene.report.findings]}"
    )

    for row in range(window.report.list.count()):
        item = window.report.list.item(row)
        finding = item.data(Qt.ItemDataRole.UserRole)
        # Die Zeile, die für obj_1 steht — allein oder als Sammelzeile mit
        # obj_2 (``_BODIES_ROLE``), je nachdem, ob beide klagen.
        bodies = item.data(panels._BODIES_ROLE) or (finding.object_id,)
        if finding.code == code and "obj_1" in bodies:
            window.report.list.setCurrentRow(row)
            break
    QApplication.processEvents()

    offered = {button.text(): button for button in window.report._offers.findChildren(QPushButton)}
    assert str(action.label) in offered, f"kein Knopf {str(action.label)!r}: {list(offered)}"

    before = where()
    offered[str(action.label)].click()
    window.session.wait_for_idle()

    assert where() != before, f"der Knopf {str(action.label)!r} hat nichts bewegt"
    assert "obj_1" not in klagen(), (
        f"und der Körper, gegen den {str(action.label)!r} angeboten wurde, klagt nicht mehr"
    )


def test_no_error_handler_names_an_operation_that_is_gone(window: MainWindow) -> None:
    """Der schnelle Wächter neben dem Wirkungstest darüber (§2.7, Regel 17).

    Die Handler der Fehlerhandlungen holen ihre Operation über
    ``REGISTRY.get("…")`` — als **Zeichenkette**, mitten in einer Methode.
    Verschwindet der Registereintrag, wirft ``get`` einen ``InternalError``,
    und der Kunde bekommt am Prüfbericht-Knopf „Im Programm ist ein
    unerwarteter Fehler aufgetreten" samt Fehlerbericht-Ordner. Das ist genau
    die Falle beim Zusammenlegen von Varianten: ``MENU_TWINS`` schützt nicht
    davor — ein Zwilling behält seinen Eintrag und wird nur im Menü versteckt,
    wer eine Operation **auflöst**, nimmt ihren Namen mit.

    Gelesen wird der Quelltext und nicht das Verhalten, aus demselben Grund wie
    bei ``tests/test_leash.py``: Ein Handler, dessen Operation es nicht mehr
    gibt, sieht völlig normal aus, bis jemand den Knopf drückt. Und es ist der
    **schnelle** Wächter, nicht der verlässliche — dass ein Name im Register
    steht, heißt nicht, dass der Handler wirkt; genau das war der Fehler, den
    der Test darüber fängt.
    """
    import ast

    quelle = Path(main_window_module.__file__).read_text(encoding="utf-8")
    baum = ast.parse(quelle)
    handler = set(window.error_handlers())

    genannt: dict[str, set[str]] = {}
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.FunctionDef) or not knoten.name.endswith("_after_error"):
            continue
        for innen in ast.walk(knoten):
            if (
                isinstance(innen, ast.Call)
                and isinstance(innen.func, ast.Attribute)
                and innen.func.attr == "get"
                and isinstance(innen.func.value, ast.Name)
                and innen.func.value.id == "REGISTRY"
                and innen.args
                and isinstance(innen.args[0], ast.Constant)
                and isinstance(innen.args[0].value, str)
            ):
                genannt.setdefault(knoten.name, set()).add(innen.args[0].value)

    assert genannt, "kein Handler nennt eine Operation — dann prüft dieser Test nichts"
    fehlen = {
        f"{methode} → {name}"
        for methode, namen in genannt.items()
        for name in namen
        if not REGISTRY.has(name)
    }
    assert not fehlen, (
        "Ein Handler einer Fehlerhandlung nennt eine Operation, die es nicht "
        f"mehr gibt — der Knopf endet im InternalError: {sorted(fehlen)}. "
        f"Angebotene Handlungen: {sorted(handler)}"
    )


def test_the_report_shows_what_helps_without_a_right_click(window: MainWindow) -> None:
    """§2.7 verspricht anklickbare Handlungen, nicht welche zum Suchen.

    Gebaut waren sie längst — nur hingen sie an einem Rechtsklick auf eine
    Listenzeile, und den probiert dort niemand aus. Der Fehlerdialog hat für
    dieselbe Sache seit je Knöpfe; der Prüfbericht, in dem die häufigeren
    Fälle landen (ein Modell unter der Platte, ein Schritt mit einem
    unmöglichen Wert), hatte keine.

    Und die Zeile bleibt leer, wo nichts zu tun ist: „Doppelte Punkte wurden
    verschweißt" braucht keinen Knopf.

    **Der erste Zustand hat sich seither verschoben — in dieselbe Richtung.**
    Dieser Test hat die Knopfzeile durchgesetzt: Vorher hingen die Handlungen
    an einem Rechtsklick, den dort niemand probiert, danach standen sie
    sichtbar unter der Liste. Nur begann die Zeile **leer** und füllte sich
    erst, wenn jemand eine Listenzeile anklickte — und dass ein Klick dort
    Knöpfe freischaltet, muss man genauso wissen wie den Rechtsklick davor.
    Hier stand deshalb „ohne gewählten Befund steht dort nichts": Das beschrieb
    den Zwischenstand, nicht das Ziel.

    ``ReportPanel._preselect`` wählt jetzt den obersten Befund vor, der eine
    Handlung anbietet — Rechtsklick, Knopfzeile, Vorauswahl sind drei Schritte
    **einer** Bewegung, und §2.7 ist am Ende von ihr eingelöst. Was dieser Test
    darunter prüft — welcher Befund welchen Knopf bekommt und welcher keinen —
    ist davon unberührt und die eigentliche Zusage.
    """
    from PySide6.QtWidgets import QPushButton

    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    # Zwei Modelle, weil das erste seit dem 03.09.2026 mittig auf dem Bett
    # landet und der Fall „unter der Platte" erst mit dem zweiten entsteht —
    # mit ausgeschalteten Haken, sonst läge es an einer freien Stelle.
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    keep_the_files_place(window)
    report = window.report
    report.show_result(window.session.last_result, window.session.project.document)

    def offered() -> list[str]:
        # ``isHidden`` und nicht ``isVisible``: offscreen wird das Fenster nie
        # gezeigt, und dann meldet jedes Kind sich als unsichtbar — dieselbe
        # Unterscheidung, die der Test des Vorschaubandes trifft.
        #
        # **Und je Knopf noch einmal.** Ein ausgetauschter Knopf wird seit dem
        # 12.09.2026 verborgen und zur Löschung vorgemerkt, statt elternlos
        # gemacht zu werden (RM-101); bis die Ereignisschleife den Auftrag
        # zustellt, hängt er weiter als Kind darunter — ``processEvents``
        # liefert ``DeferredDelete`` nicht aus. Gezählt wird deshalb, was zu
        # sehen wäre, und nicht, was noch am Elternteil hängt: Ohne den Filter
        # stand hier nach zwei Befundwechseln dreimal „Auf das Bett setzen".
        QApplication.processEvents()
        row = report._offers
        if row.isHidden():
            return []
        return [b.text() for b in row.findChildren(QPushButton) if not b.isHidden()]

    assert offered() == [str(errors.PLACE_ON_BED.label)], (
        "die Vorauswahl zeigt die Handlung, bevor jemand klickt"
    )

    def choose(code: str) -> None:
        for row in range(report.list.count()):
            finding = report.list.item(row).data(Qt.ItemDataRole.UserRole)
            if finding.code == code:
                report.list.setCurrentRow(row)
                return
        raise AssertionError(f"kein Befund {code!r} im Bericht")

    choose("arrange.below_bed")
    assert offered() == [str(errors.PLACE_ON_BED.label)]

    # Ein Hinweis ohne Handlung — seit dem 14.09.2026 nicht mehr aus dem
    # STL-Import (das Verschweißen einer STL ist Lesen, kein Befund), also
    # ausdrücklich hinzugelegt: Geprüft wird die Knopfzeile, nicht der Import.
    report.add_findings(
        [Finding(code="ingest.welded", severity="info", message="Doppelte Punkte verschweißt.")]
    )
    choose("ingest.welded")
    assert offered() == [], "ein Hinweis ohne Handlung bekommt keinen Knopf"


def test_a_stopped_step_is_one_click_from_its_own_dialog(window: MainWindow) -> None:
    """Der häufigste Fehler des Programms hatte keinen Weg zurück (§2.7, §2.1).

    Eine Operation, deren Werte nicht gehen, wirft **keinen** Fehlerdialog: Der
    Kern macht daraus einen Befund und hält die Kette an (§15.3). Im Bericht
    stand dann „Der Wert liegt über dem zulässigen Höchstwert", und der Weg zu
    diesem Wert war, den Schritt im Verlauf zu suchen und doppelzuklicken.
    *Eingabe korrigieren* stand daneben — als Satz, denn es war die häufigste
    Handlung des Kerns und die einzige ohne Handler.

    Geprüft wird die ganze Kette: dass der Befund aus der Operation kommt, dass
    er seine Schrittkennung trägt, dass die Handlung angeboten wird, und dass
    sie den Schritt öffnet, der wirklich gescheitert ist.
    """
    from app.ui.panels import actions_for, as_error

    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    object_id = next(iter(window.session.last_result.scene.objects))

    window.session.apply(
        "Bohrung setzen",
        [
            OperationDraft(
                op="drill_hole",
                inputs=(object_id,),
                params={"diameter": 5000.0, "x": 0.0, "y": 0.0, "z": 4.0, "axis": "z"},
            )
        ],
    )
    window.session.wait_for_idle()

    result = window.session.last_result
    assert not result.complete, "ein unmöglicher Wert hält die Kette an"
    stopped = [f for f in result.scene.report.findings if f.code.startswith("op.")]
    assert stopped, "der Fehler der Operation steht als Befund im Bericht"
    finding = stopped[0]
    assert finding.op_id == result.stopped_at, "und er nennt den Schritt, der hängt"

    offers = actions_for(finding)
    handlers = window.error_handlers()
    assert [action.id for action in offers] == ["correct_input"]
    assert offers[0].id in handlers, "angeboten, aber nichts führt es aus"

    opened: list[int] = []
    # Mit ``field``: der Handler gibt das Feld mit, in das der Cursor gehört.
    window.edit_operation = lambda op_id, field="": opened.append(op_id)  # type: ignore[method-assign]
    handlers["correct_input"](as_error(finding))

    assert opened == [result.stopped_at], "geöffnet wird der Schritt, der gescheitert ist"


def test_a_geometry_failure_offers_repair_and_locations() -> None:
    """Ein kaputtes Netz bekommt seine sachlichen Auswege statt eines Felds.

    ``correct_input`` war der pauschale Rückfall für jeden ``op.*``-Befund.
    Bei einem Geometriefehler liegt es aber nicht an einem Zahlenfeld; der
    Kunde braucht die Reparatur und die markierten Stellen, die die Ausnahme
    bereits nennt.
    """
    from app.core.errors import GeometryError
    from app.core.scene.evaluate import _finding_from
    from app.core.types import Operation
    from app.ui.panels import actions_for

    operation = Operation(id=4, op="difference", inputs=("obj_1",), outputs=("obj_1",), params={})
    finding = _finding_from(GeometryError(), operation)

    assert [action.id for action in actions_for(finding)] == [
        "repair_and_retry",
        "show_locations",
    ]


def test_a_partial_repair_shows_closed_total_and_remaining_edges() -> None:
    """Der Anteil steht in der Zeile — nicht als zwei rohe Zahlen im Tooltip."""
    from app.core.types import Finding
    from app.ui.panels import _line_for

    filled = Finding(
        code="repair.holes_filled",
        severity="info",
        message="3 von 19 offenen Kanten geschlossen; 16 bleiben offen.",
        object_id="obj_1",
        values={"before": 19, "after": 16},
    )
    remaining = Finding(
        code="repair.still_open",
        severity="warning",
        message="Die Reparatur schließt kleine Löcher, kann fehlende Wände aber nicht ersetzen.",
        object_id="obj_1",
        values={"open_edges": 16},
    )

    filled_line = _line_for(filled, {"obj_1": "Halb offen"})
    remaining_line = _line_for(remaining, {"obj_1": "Halb offen"})

    assert "3 von 19 offenen Kanten geschlossen; 16 bleiben offen" in filled_line
    assert "Halb offen" in filled_line
    assert "Offene Kanten: 16" in remaining_line
    assert "Halb offen" in remaining_line


def test_repair_remainders_show_locations_only_for_a_known_body() -> None:
    """Der Ausweg führt zur Defektkarte, aber nie über eine geratene Auswahl."""
    from app.core.types import Finding
    from app.ui.panels import actions_for

    for code in ("repair.still_open", "repair.self_intersections_skipped"):
        located = Finding(code=code, severity="warning", message="x", object_id="obj_1")
        unlocated = Finding(code=code, severity="warning", message="x")
        assert [action.id for action in actions_for(located)] == ["show_locations"]
        assert actions_for(unlocated) == ()


@pytest.mark.parametrize(
    "code",
    [
        "repair.self_intersections_detected",
        "repair.self_intersections_unresolved",
        "repair.self_intersections_incomplete",
    ],
)
def test_intersection_repair_advice_never_targets_an_unrelated_selection(code: str) -> None:
    """Auch mit ausdrücklichem Vorschlag bleibt der Befund an seinen Körper gebunden."""
    from app.core.errors import SHOW_LOCATIONS
    from app.core.types import Finding
    from app.ui.panels import actions_for

    finding = Finding(code, "warning", "x", suggestions=(SHOW_LOCATIONS,))
    assert actions_for(finding) == ()
    located = dataclasses.replace(finding, object_id="obj_1")
    assert actions_for(located) == (SHOW_LOCATIONS,)


def test_an_attempted_repair_is_not_offered_twice_regardless_of_its_finding() -> None:
    """Auch „nichts zu reparieren“ öffnet denselben Reparaturring nicht erneut.

    Die Sperre liest bewusst keinen Befundtext: Ob die Reparatur teilweise
    half oder ``repair.nothing_to_do`` meldete, steht im Bericht; belegt ist
    der Versuch durch den aktiven Zug im Verlauf.
    """
    from app.core.types import Document, Finding, Operation, Transaction
    from app.ui.panels import actions_for_document

    document = Document(format_version=18, app_version="test")
    document.ops.extend(
        [
            Operation(id=4, op="repair", inputs=("obj_1",), outputs=("obj_1",)),
            Operation(id=5, op="remesh_uniform", inputs=("obj_1",), outputs=("obj_1",)),
        ]
    )
    document.transactions.append(Transaction(id="t3", title="Reparieren", ops=(4, 5)))
    finding = Finding(
        code="op.remesh_uniform.NotManifoldError",
        severity="error",
        message="offen",
        op_id=5,
        suggestions=(errors.REPAIR_AND_RETRY, errors.SHOW_LOCATIONS),
    )

    assert [action.id for action in actions_for_document(finding, document, stopped_at=5)] == [
        "show_locations"
    ]

    # Eine fremde Reparatur in einer anderen Transaktion oder am anderen
    # Körper ist kein Versuch für diesen Schritt und darf ihn nicht sperren.
    document.transactions[:] = [
        Transaction(id="t2", title="Fremde Reparatur", ops=(4,)),
        Transaction(id="t3", title="Fehler", ops=(5,)),
    ]
    assert [action.id for action in actions_for_document(finding, document, stopped_at=5)] == [
        "repair_and_retry",
        "show_locations",
    ]


def test_two_inputs_are_only_considered_repaired_when_both_are_covered() -> None:
    """Zwei Eingänge werden weder zusammengeworfen noch über die Auswahl ergänzt."""
    from app.core.types import Document, Finding, Operation, Transaction
    from app.ui.panels import actions_for_document

    document = Document(format_version=18, app_version="test")
    document.ops.extend(
        [
            Operation(id=7, op="repair", inputs=("obj_1",), outputs=("obj_1",)),
            Operation(id=8, op="repair", inputs=("obj_2",), outputs=("obj_2",)),
            Operation(
                id=9,
                op="subtract_objects",
                inputs=("obj_1", "obj_2"),
                outputs=("obj_3",),
            ),
        ]
    )
    document.transactions.append(Transaction(id="t4", title="Reparieren", ops=(7, 8, 9)))
    finding = Finding(
        code="op.subtract_objects.BooleanFailedError",
        severity="error",
        message="geht nicht",
        op_id=9,
        suggestions=(errors.REPAIR_AND_RETRY, errors.SHOW_LOCATIONS),
    )

    assert actions_for_document(finding, document, stopped_at=9) == (), (
        "beide Reparaturen wurden versucht; für zwei Körper gibt es keinen eindeutigen Kartenort"
    )

    document.transactions[-1] = Transaction(id="t4", title="Reparieren", ops=(7, 9))
    assert [action.id for action in actions_for_document(finding, document, stopped_at=9)] == [
        "repair_and_retry"
    ]


def test_repair_is_not_offered_for_a_stopped_step_without_an_input() -> None:
    """Ein Knopf ohne ausführbares Modell erscheint gar nicht erst."""
    from app.core.types import Document, Finding, Operation
    from app.ui.panels import actions_for_document

    document = Document(format_version=18, app_version="test")
    document.ops.append(Operation(id=3, op="create_box", inputs=(), outputs=("obj_1",)))
    finding = Finding(
        code="op.create_box.GeometryError",
        severity="error",
        message="geht nicht",
        op_id=3,
        suggestions=(errors.REPAIR_AND_RETRY, errors.SHOW_LOCATIONS),
    )

    offered = actions_for_document(finding, document, stopped_at=3)

    assert offered == ()


def test_the_grid_finding_repairs_before_its_step_and_only_once() -> None:
    """RM-246: Am gelungenen Rasterschritt gehört die Reparatur vor den Schritt.

    Die Ausgabe ist dicht, nur gerundet — *Reparieren und erneut versuchen*
    reparierte sie und ließ die Rundung stehen. Angeboten wird der Weg, der
    die Eingänge vor dem Schritt repariert, und nur, solange derselbe Zug das
    nicht schon getan hat.
    """
    from app.core.types import Document, Finding, Operation, Transaction
    from app.ui.panels import actions_for_document

    document = Document(format_version=18, app_version="test")
    document.ops.extend(
        [
            Operation(id=1, op="load", outputs=("obj_1",)),
            Operation(id=2, op="create_box", outputs=("obj_2",)),
            Operation(id=3, op="subtract_objects", inputs=("obj_1", "obj_2"), outputs=("obj_3",)),
        ]
    )
    document.transactions.extend(
        [
            Transaction(id="t1", title="Laden", ops=(1,)),
            Transaction(id="t2", title="Quader", ops=(2,)),
            Transaction(id="t3", title="Abziehen", ops=(3,)),
        ]
    )
    finding = Finding(
        code="boolean.voxel",
        severity="warning",
        message="gerundet",
        op_id=3,
        object_id="obj_3",
    )
    living = frozenset({"obj_3"})

    assert [
        action.id for action in actions_for_document(finding, document, live_objects=living)
    ] == ["repair_before_and_retry"]

    document.ops[2:] = [
        Operation(id=4, op="repair", inputs=("obj_1",), outputs=("obj_1",)),
        Operation(id=5, op="repair", inputs=("obj_2",), outputs=("obj_2",)),
        Operation(id=6, op="subtract_objects", inputs=("obj_1", "obj_2"), outputs=("obj_3",)),
    ]
    document.transactions[2] = Transaction(id="t3", title="Reparieren", ops=(4, 5, 6))
    repaired = dataclasses.replace(finding, op_id=6)

    assert actions_for_document(repaired, document, live_objects=living) == ()


def test_a_planned_but_not_evaluated_object_is_not_an_executable_target() -> None:
    """Der Stapel kann Ausgänge nennen, die hinter dem Stopp nie entstanden."""
    from app.core.types import Document, Finding, Operation
    from app.ui.panels import actions_for_document

    document = Document(format_version=18, app_version="test")
    document.ops.append(Operation(id=3, op="create_box", outputs=("obj_1",)))
    finding = Finding(
        code="mesh.open",
        severity="error",
        message="geht nicht",
        object_id="obj_1",
        suggestions=(errors.REPAIR_AND_RETRY, errors.SHOW_LOCATIONS),
    )

    offered = actions_for_document(finding, document, live_objects=frozenset())

    assert offered == ()


def test_repair_is_not_offered_before_retrying_an_exact_shell() -> None:
    """Die Oberfläche bewahrt Aushöhlen vor einer sicher schädlichen Reparatur."""
    from app.core.types import Document, Finding, Operation
    from app.ui.panels import actions_for_document

    document = Document(format_version=18, app_version="test")
    document.ops.extend(
        [
            Operation(id=4, op="create_brep_box", outputs=("obj_1",)),
            Operation(id=5, op="shell_exact", inputs=("obj_1",), outputs=("obj_1",)),
        ]
    )
    finding = Finding(
        code="op.shell_exact.GeometryError",
        severity="error",
        message="geht nicht",
        op_id=5,
        suggestions=(errors.REPAIR_AND_RETRY, errors.SHOW_LOCATIONS),
    )

    offered = actions_for_document(finding, document, stopped_at=5)

    assert [action.id for action in offered] == ["show_locations"]


def test_an_objectless_direct_error_has_no_repair_button(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch der modale Fehlerweg verspricht keine Reparatur ohne Ziel."""
    from app.ui import main_window

    shown: list[errors.AppError] = []
    monkeypatch.setattr(main_window, "show_error", lambda error, _parent: shown.append(error))

    window._on_error(errors.NotManifoldError(open_edges=3))

    assert len(shown) == 1
    assert "repair_and_retry" not in {action.id for action in shown[0].suggestions}


def test_partial_repair_runs_from_the_report_and_undoes(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Datei → Berichtsknopf → Restkarte → Oberflächen-Undo, ohne Kernabkürzung.

    Seit dem 22.09.2026 schließt der Import das offene Netz selbst, und die
    Reparatur füllt jede Öffnung, die eine Fläche tragen kann (``ed233f2c``).
    Der Teilerfolg, um den es hier geht, bleibt dort, wo Ränder sich nicht
    füllen lassen; die Testnetze haben keine solchen, also stellen die zwei
    Schalter aus ``tests/helpers.py`` den Fall nach — der Weg durch die
    Oberfläche ist derselbe.
    """
    from PySide6.QtWidgets import QPushButton

    from app.core.geom.repair import open_edge_count
    from tests.helpers import fill_only_small_holes, keep_imports_open

    keep_imports_open(monkeypatch, window.session)
    fill_only_small_holes(monkeypatch)
    window.open_path(MESHES / "partially_open.stl")
    window.session.wait_for_idle()
    object_id = next(iter(window.session.last_result.scene.objects))
    assert open_edge_count(window.session.last_result.scene.objects[object_id].mesh) == 19

    def choose(code: str) -> None:
        for row in range(window.report.list.count()):
            item = window.report.list.item(row)
            finding = item.data(Qt.ItemDataRole.UserRole)
            if finding.code == code:
                window.report.list.setCurrentRow(row)
                QApplication.processEvents()
                return
        raise AssertionError(f"kein Befund {code!r} im sichtbaren Bericht")

    def button(label: object) -> QPushButton | None:
        # Ausgebaute Qt-Kinder warten noch auf deleteLater; maßgeblich ist
        # ausschließlich die aktuelle Knopfzeile.
        row = window.report._offer_row
        buttons = [row.itemAt(index).widget() for index in range(row.count())]
        return next((entry for entry in buttons if entry.text() == str(label)), None)

    choose("ingest.not_watertight")
    repair_button = button(errors.REPAIR_AND_RETRY.label)
    assert repair_button is not None and not repair_button.isHidden()
    repair_button.click()
    window.session.wait_for_idle()

    repaired = window.session.last_result.scene.objects[object_id].mesh
    assert open_edge_count(repaired) == 16
    # Die Bilanz steht seit ``2b83f72a5`` in zwei Befunden statt in dem einen
    # Satz „3 von 19 offenen Kanten geschlossen; 16 bleiben offen“: Was
    # geschlossen wurde (mit Kanten davor und danach), und was offen bleibt.
    shown = [
        window.report.list.item(row).data(Qt.ItemDataRole.UserRole)
        for row in range(window.report.list.count())
    ]
    codes = [finding.code for finding in shown]
    filled = next((finding for finding in shown if finding.code == "repair.holes_filled"), None)
    assert filled is not None, codes
    assert (filled.values["before"], filled.values["after"]) == (19, 16)
    still = next((finding for finding in shown if finding.code == "repair.still_open"), None)
    assert still is not None, codes
    assert still.values["open_edges"] == 16

    choose("repair.still_open")
    location_button = button(errors.SHOW_LOCATIONS.label)
    assert location_button is not None and not location_button.isHidden()
    location_button.click()
    QApplication.processEvents()
    assert window.tools.active() == "analysis"
    assert window.analysis_bar.chosen() == "defects"
    assert window.object_tree.selected_objects() == (object_id,)

    window.undo_action.trigger()
    window.session.wait_for_idle()
    restored = window.session.last_result.scene.objects[object_id].mesh
    assert open_edge_count(restored) == 19


def test_failed_operation_is_repaired_before_retry_without_a_loop(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Echter Fehler → Reparatur davor → Retry → Stellen zeigen → ein Undo.

    Dieselben zwei Schalter wie im Test darüber, aus demselben Grund
    (22.09.2026, ``ed233f2c``): Ohne sie ist der Körper nach dem Import dicht,
    das Vernetzen gelingt, und es gibt keinen Fehler, dessen Reparatur zu
    prüfen wäre.
    """
    from PySide6.QtWidgets import QPushButton, QVBoxLayout

    from tests.helpers import fill_only_small_holes, keep_imports_open

    keep_imports_open(monkeypatch, window.session)
    fill_only_small_holes(monkeypatch)
    window.resize(1500, 950)
    window.show()
    QApplication.processEvents()
    window.open_path(MESHES / "partially_open.stl")
    window.session.wait_for_idle()
    object_id = next(iter(window.session.last_result.scene.objects))
    window.session.apply(
        REGISTRY.get("remesh_uniform").title,
        [OperationDraft(op="remesh_uniform", inputs=(object_id,))],
    )
    window.session.wait_for_idle()

    first_result = window.session.last_result
    failed_id = first_result.stopped_at
    assert failed_id is not None
    original_ops = tuple(window.session.project.document.ops)
    old_transaction = window.session.history.transaction_of(failed_id)
    assert old_transaction is not None

    def choose(code: str) -> None:
        for row in range(window.report.list.count()):
            item = window.report.list.item(row)
            finding = item.data(Qt.ItemDataRole.UserRole)
            if finding.code == code:
                window.report.list.setCurrentRow(row)
                QApplication.processEvents()
                return
        raise AssertionError(f"kein Befund {code!r} im sichtbaren Bericht")

    def button(label: object) -> QPushButton | None:
        row = window.report._offer_row
        return next(
            (
                entry
                for index in range(row.count())
                if isinstance(entry := row.itemAt(index).widget(), QPushButton)
                and entry.text() == str(label)
            ),
            None,
        )

    failed_code = "op.remesh_uniform.NotManifoldError"
    choose(failed_code)
    first_repair = button(errors.REPAIR_AND_RETRY.label)
    assert first_repair is not None and not first_repair.isHidden()
    offered_buttons = [
        entry for entry in window.report._offers.findChildren(QPushButton) if not entry.isHidden()
    ]
    assert isinstance(window.report._offer_row, QVBoxLayout)
    assert all(window.report._offers.rect().contains(entry.geometry()) for entry in offered_buttons)
    assert len({entry.x() for entry in offered_buttons}) == 1
    assert len({entry.width() for entry in offered_buttons}) == 1
    transaction_count = len(window.session.history.transactions)
    first_repair.click()
    first_repair.click()
    window.session.wait_for_idle()

    assert len(window.session.history.transactions) == transaction_count + 1
    retry = window.session.history.transactions[-1]
    retry_ops = [entry for entry in window.session.project.document.ops if entry.id in retry.ops]
    assert [entry.op for entry in retry_ops] == ["repair", "remesh_uniform"]
    assert retry.changes is not None
    assert failed_id in (retry.changes.after.edited_ops or {})
    assert window.session.last_result.stopped_at == retry_ops[-1].id

    rows = [window.history_panel.list.item(row) for row in range(window.history_panel.list.count())]
    old_row = next(item for item in rows if old_transaction.id in item.toolTip())
    assert tr("gelöscht") in old_row.text() and old_row.font().strikeOut()
    assert any(str(errors.REPAIR_AND_RETRY.label) in item.text() for item in rows)

    choose(failed_code)
    assert button(errors.REPAIR_AND_RETRY.label) is None, "derselbe Reparaturweg bildet keinen Ring"
    location = button(errors.SHOW_LOCATIONS.label)
    assert location is not None and not location.isHidden()

    window.undo_action.trigger()
    window.session.wait_for_idle()
    assert tuple(window.session.project.document.ops) == original_ops
    assert window.session.last_result.stopped_at == failed_id

    choose(failed_code)
    restored = button(errors.REPAIR_AND_RETRY.label)
    assert restored is not None and not restored.isHidden(), (
        "nach dem Undo ist der Reparaturversuch nicht mehr aktiv"
    )


def test_correcting_puts_the_cursor_in_the_field_that_failed(window: MainWindow) -> None:
    """Der Befund spricht über **einen** Wert — der Dialog soll ihn zeigen.

    ``ValidationError`` nennt das Feld, und der Befund trägt es weiter. Ohne
    den Sprung dorthin geht ein Dialog mit acht Zeilen auf, und der Kunde
    sucht, welche gemeint war. Geprüft wird an der ganzen Kette: Bericht,
    Knopf, Dialog, Fokus.
    """
    from PySide6.QtWidgets import QDoubleSpinBox

    from app.ui.panels import as_error

    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    object_id = next(iter(window.session.last_result.scene.objects))
    window.session.apply(
        "Bohrung setzen",
        [
            OperationDraft(
                op="drill_hole",
                inputs=(object_id,),
                params={"diameter": 5000.0, "x": 0.0, "y": 0.0, "z": 4.0, "axis": "z"},
            )
        ],
    )
    window.session.wait_for_idle()

    finding = next(
        f for f in window.session.last_result.scene.report.findings if f.code.startswith("op.")
    )
    assert finding.values.get("field") == "diameter", "der Kern nennt das Feld nicht mehr"

    window.error_handlers()["correct_input"](as_error(finding))
    QApplication.processEvents()

    dialog = window._op_dialog
    assert dialog is not None, "der Dialog ging nicht auf"
    try:
        editor = dialog._editors["diameter"]
        inner = editor.findChild(QDoubleSpinBox)
        assert inner is not None
        assert inner.hasFocus(), "der Cursor steht nicht im Feld, um das es geht"
    finally:
        dialog.reject()


def test_a_boolean_that_failed_in_draft_can_go_the_full_chain(window: MainWindow) -> None:
    """Der Rat zeigte ins Leere, und zwar an der häufigsten Stelle (§17.2, §31).

    Im Fenster läuft die kurze Rückfallkette; *Voxelstufe erzwingen* ist damit
    der richtige nächste Schritt — und war ein Satz ohne Knopf. Jetzt rechnet
    er einmal mit der vollen Kette, und danach ist die Sitzung wieder so
    schnell wie vorher.
    """
    from app.ui.dialogs import offered_actions

    handlers = window.error_handlers()
    entwurf = errors.BooleanFailedError(attempted=("direct", "welded"))
    assert "use_voxel_stage" in {a.id for a in offered_actions(entwurf, handlers)}

    handlers["use_voxel_stage"](entwurf)
    assert window.session._quality_once == "fine", "der Lauf bleibt im Entwurf"
    window.session.wait_for_idle()
    assert window.session._quality_once is None, "und der nächste ist wieder Entwurf"


def test_correcting_is_not_offered_where_there_is_no_step(window: MainWindow) -> None:
    """Ein Knopf, der nichts tun kann, wird nicht gezeigt.

    *Eingabe korrigieren* öffnet einen Schritt. Ein Fehler beim Lesen oder
    Schreiben einer Datei hat keinen — dort bliebe der Knopf stumm, und das ist
    der Grund, aus dem das Projekt Vorschläge ohne Handler gar nicht erst
    anbietet.
    """
    from app.ui.dialogs import offered_actions

    handlers = window.error_handlers()
    assert "correct_input" in handlers

    without = errors.ValidationError(field="diameter", detail="zu groß", constraint="maximum")
    assert "correct_input" not in {a.id for a in offered_actions(without, handlers)}

    with_step = errors.ValidationError(
        field="diameter", detail="zu groß", constraint="maximum", op_id=2
    )
    assert "correct_input" in {a.id for a in offered_actions(with_step, handlers)}


def test_a_bundle_row_acting_on_each_body_is_one_undo_step(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """RM-372: Eine Sammelzeile führt eine Handlung je Körper aus — und jeder
    Körper war ein eigener Rückgängig-Schritt.

    Zwei Leisten aus einer 3MF ragen über den Bauraum; die Zeile „steht über
    den Bauraum hinaus“ trägt beide. *Auf den Bauraum verkleinern* lief für
    jede einzeln durch ``error_handlers``, und ein Strg+Z nahm nur die zweite
    zurück. Jetzt ist der Klick eine Transaktion mit beiden Schritten, und ein
    Strg+Z stellt beide wieder her.
    """
    import trimesh
    from PySide6.QtWidgets import QPushButton

    from app.core.export import threemf
    from app.core.geom.mesh import MeshData
    from app.ui import panels

    monkeypatch.setattr(
        panels.BodyChoiceDialog, "ask", lambda parent, title, ids, names: tuple(ids)
    )
    parts = []
    for index in range(2):
        mesh = trimesh.creation.box((300.0, 20.0, 20.0))
        mesh.apply_translation((0.0, 40.0 * index, 10.0))
        parts.append(threemf.AssemblyPart(mesh=MeshData.of(mesh), name=f"Leiste {index + 1}"))
    assert window.session.import_payload("leisten.3mf", threemf.write_assembly(parts))
    assert window.session.wait_for_idle()
    document = window.session.project.document
    bodies = document.ops[-1].outputs
    assert len(bodies) == 2
    window.report.show_result(window.session.last_result, document)

    listing = window.report.list
    item = next(
        (
            listing.item(row)
            for row in range(listing.count())
            if listing.item(row).data(Qt.ItemDataRole.UserRole).code
            == "arrange.out_of_build_volume"
        ),
        None,
    )
    assert item is not None, [
        listing.item(row).data(Qt.ItemDataRole.UserRole).code for row in range(listing.count())
    ]
    assert set(item.data(panels._BODIES_ROLE) or ()) == set(bodies), "eine Zeile für beide"
    listing.setCurrentItem(item)
    QApplication.processEvents()
    button = next(
        child
        for child in window.report._offers.findChildren(QPushButton)
        if child.text() == str(errors.SCALE_TO_FIT.label)
    )

    def longest() -> list[float]:
        objects = window.session.last_result.scene.objects
        return [max(objects[key].mesh.bounds.size) for key in bodies]

    assert longest() == pytest.approx([300.0, 300.0])
    transactions = len(document.transactions)
    button.click()
    assert window.session.wait_for_idle()

    assert len(document.transactions) == transactions + 1, "ein Klick, ein Rückgängig-Schritt"
    by_id = {entry.id: entry for entry in document.ops}
    made = [by_id[op_id] for op_id in document.transactions[-1].ops]
    assert sorted(entry.inputs[0] for entry in made) == sorted(bodies)
    assert all(size < 300.0 for size in longest()), longest()

    window.action_undo()
    assert window.session.wait_for_idle()
    assert longest() == pytest.approx([300.0, 300.0]), "ein Strg+Z stellt beide wieder her"


@pytest.mark.parametrize("count", [2, 8])
@pytest.mark.parametrize("changed", [False, True])
def test_import_bed_action_keeps_the_import_group_and_ignores_selection(
    window: MainWindow, count: int, changed: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch eine Sammelzeile setzt den Import gemeinsam auf, ohne Körperauswahldialog."""
    import trimesh
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QPushButton

    from app.core.export import threemf
    from app.core.geom.mesh import MeshData
    from app.ui.panels import BodyChoiceDialog, as_error

    window.session.apply("Vorhanden", [OperationDraft(op="create_box")])
    window.session.wait_for_idle()
    old = window.session.last_result.scene.objects["obj_1"].mesh.bounds
    parts = []
    for index in range(count):
        mesh = trimesh.creation.box((10.0, 10.0, 10.0))
        mesh.apply_translation((30.0 + 10.0 * index, 0.0, -95.0 + 2.0 * index))
        parts.append(threemf.AssemblyPart(mesh=MeshData.of(mesh), name=f"Teil {index + 1}"))
    assert window.session.import_payload("gruppe.3mf", threemf.write_assembly(parts))
    window.session.wait_for_idle()
    keep_the_files_place(window)
    targets = window.session.project.document.ops[-1].outputs
    before = window.session.last_result
    assert [before.scene.objects[key].mesh.bounds.minimum[2] for key in targets] == pytest.approx(
        [-100.0 + 2.0 * index for index in range(count)]
    )
    window.object_tree.select_object("obj_1")
    listing = window.report.list
    item = next(
        listing.item(row)
        for row in range(listing.count())
        if listing.item(row).data(Qt.ItemDataRole.UserRole).code == "arrange.below_bed"
    )
    listing.setCurrentItem(item)
    QApplication.processEvents()
    stale = as_error(
        item.data(Qt.ItemDataRole.UserRole),
        window.session.project.document,
        import_group=targets,
    )

    def no_choice(*_args, **_kwargs):
        raise AssertionError("the import already fixes the complete target group")

    monkeypatch.setattr(BodyChoiceDialog, "ask", no_choice)
    button = next(
        child
        for child in window.report._offers.findChildren(QPushButton)
        if child.text() == tr("Gemeinsam auf das Bett setzen")
    )
    if changed:
        # Die alte Zeile bleibt absichtlich sichtbar: Ein nach dem Aufbau
        # mutiertes Dokument darf ihren Auftrag nicht auf ein Einzelteil ändern.
        window.session.history.apply(
            "Inzwischen geändert",
            [OperationDraft(op="rename_object", inputs=(targets[-1],), params={"name": "Neu"})],
        )
        total = len(window.session.project.document.ops)
        QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        assert len(window.session.project.document.ops) == total
        assert window.session.project.document.ops[-1].op == "rename_object"
        return
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    window.session.wait_for_idle()
    operation = window.session.project.document.ops[-1]
    assert operation.op == "place_group_on_bed"
    assert operation.inputs == targets
    after = window.session.last_result
    assert [after.scene.objects[key].mesh.bounds.minimum[2] for key in targets] == pytest.approx(
        [2.0 * index for index in range(count)]
    )
    assert after.scene.objects["obj_1"].mesh.bounds == old
    total = len(window.session.project.document.ops)
    window._place_on_bed_after_error(stale)
    assert len(window.session.project.document.ops) == total
    window.action_undo()
    window.session.wait_for_idle()
    restored = window.session.last_result.scene.objects
    assert [restored[key].mesh.bounds.minimum[2] for key in targets] == pytest.approx(
        [-100.0 + 2.0 * index for index in range(count)]
    )
    # Zweimal zurück: erst das Ausschalten der Haken (``keep_the_files_place``
    # ist ein eigener Schritt), dann der Import selbst.
    window.action_undo()
    window.session.wait_for_idle()
    window.action_undo()
    window.session.wait_for_idle()
    assert set(window.session.last_result.scene.objects) == {"obj_1"}


def test_grounded_import_keeps_the_single_bed_action_for_its_floating_body(window):
    """Der Berichtsklick senkt nur den schwebenden Körper; gemeinsam wäre es eine Nullwirkung."""
    import trimesh
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QPushButton

    from app.core.export import threemf
    from app.core.geom.mesh import MeshData

    window.session.apply("Vorhanden", [OperationDraft(op="create_box")])
    window.session.wait_for_idle()
    parts = []
    for index, centre in enumerate(((40.0, 0.0, 5.0), (70.0, 0.0, 15.0))):
        mesh = trimesh.creation.box((10.0, 10.0, 10.0))
        mesh.apply_translation(centre)
        parts.append(threemf.AssemblyPart(mesh=MeshData(mesh), name=f"Teil {index + 1}"))
    assert window.session.import_payload("aufgesetzt.3mf", threemf.write_assembly(parts))
    window.session.wait_for_idle()
    keep_the_files_place(window)
    targets = window.session.project.document.ops[-1].outputs
    before = window.session.last_result
    assert [before.scene.objects[key].mesh.bounds.minimum[2] for key in targets] == [0.0, 10.0]
    window.object_tree.select_object("obj_1")
    listing = window.report.list
    item = next(
        listing.item(row)
        for row in range(listing.count())
        if listing.item(row).data(Qt.ItemDataRole.UserRole).code == "arrange.above_bed"
        and listing.item(row).data(Qt.ItemDataRole.UserRole).object_id == targets[1]
    )
    listing.setCurrentItem(item)
    buttons = window.report._offers.findChildren(QPushButton)
    assert not any(button.text() == tr("Gemeinsam auf das Bett setzen") for button in buttons)
    button = next(button for button in buttons if button.text() == str(errors.PLACE_ON_BED.label))
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    window.session.wait_for_idle()
    operation = window.session.project.document.ops[-1]
    assert operation.op == "place_on_bed" and operation.inputs == (targets[1],)
    after = window.session.last_result
    assert (
        after.scene.objects[targets[0]].mesh.bounds == before.scene.objects[targets[0]].mesh.bounds
    )
    assert after.scene.objects["obj_1"].mesh.bounds == before.scene.objects["obj_1"].mesh.bounds
    assert after.scene.objects[targets[1]].mesh.bounds.minimum[2] == pytest.approx(0.0)
    assert not any(
        finding.code == "arrange.above_bed" and finding.object_id == targets[1]
        for finding in after.scene.report.findings
    )
    window.action_undo()
    window.session.wait_for_idle()
    assert window.session.last_result.scene.objects[targets[1]].mesh.bounds.minimum[
        2
    ] == pytest.approx(10.0)


def test_import_bed_offer_does_not_invent_a_group_from_historical_outputs(
    window: MainWindow,
) -> None:
    """Ein unvollständiges Ergebnis bietet keinen anschließend stillen Gruppenauftrag."""
    from app.core.scene.history import History
    from app.core.scene.project import new_project
    from app.ui.panels import actions_for_document, as_error

    document = new_project("centauri-carbon-2", "petg").document
    History(document).apply(
        "Import", [OperationDraft(op="load", params={"source": "src_1"}, produces=2)]
    )
    finding = Finding(
        code="arrange.below_bed", severity="warning", message="Unter dem Bett", object_id="obj_1"
    )
    actions = actions_for_document(finding, document, live_objects=("obj_1",))
    action = next(action for action in actions if action.id == "place_on_bed")
    assert action.label == errors.PLACE_ON_BED.label
    assert "import_group" not in as_error(finding, document).values


def test_the_finding_below_the_bed_is_one_click_from_being_fixed(window: MainWindow) -> None:
    """§2.7 zu Ende: der Klick am Befund tut, was der Satz nahelegt.

    Ein geladenes Modell sitzt mittig auf z = 0 und steckt damit zur Hälfte
    unter der Platte — der häufigste Befund von Weg 1. Die Eingangsstufe setzt
    es bewusst nicht von selbst auf (§17.1: anbieten, nicht erzwingen), und
    angeboten war es nirgends: Der Bericht nannte den Fall und bot *Modell
    teilen* und *Auf den Bauraum verkleinern* an.

    **Gemessen wird am zweiten Modell mit ausgeschalteten Haken.** Das erste
    eines Projekts kommt aufgesetzt und mittig herein, jedes weitere aufgesetzt
    an eine freie Stelle (§17.1, Schritt 6). Die Dateilage behält ein
    Ladeschritt, an dem *Auf das Bett setzen* und *An eine freie Stelle legen*
    aus sind — so wie jeder, der vor dem 28.09.2026 gespeichert wurde. Der
    Befund und sein Knopf haben damit denselben Anlass wie vorher.

    Geprüft wird die ganze Kette — Kennung, Handlung, Handler, Geometrie — und
    dass ein Undo sie zurücknimmt (Regel 19, §2.1).
    """
    from app.ui.panels import FINDING_ACTIONS, as_error

    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    keep_the_files_place(window)

    result = window.session.last_result
    sunk = [f for f in result.scene.report.findings if f.code == "arrange.below_bed"]
    assert sunk, "ohne die Haken behält es seine Lage und steckt unter der Platte"
    # Das zweite Objekt ist das gesunkene; das erste liegt auf dem Bett.
    gesunken = list(result.scene.objects.values())[1]
    before = gesunken.mesh.bounds.minimum[2]
    assert before < 0.0

    offers = FINDING_ACTIONS[sunk[0].code]
    handlers = window.error_handlers()
    assert [action.id for action in offers] == ["place_on_bed"]
    assert offers[0].id in handlers, "angeboten, aber nichts führt es aus"

    handlers[offers[0].id](as_error(sunk[0]))
    window.session.wait_for_idle()

    after = window.session.last_result
    assert list(after.scene.objects.values())[1].mesh.bounds.minimum[2] == pytest.approx(0.0)
    assert not [f for f in after.scene.report.findings if f.code == "arrange.below_bed"], (
        "der Befund bleibt stehen, obwohl er behoben ist"
    )

    window.action_undo()
    window.session.wait_for_idle()
    zurueck = window.session.last_result
    assert list(zurueck.scene.objects.values())[1].mesh.bounds.minimum[2] == pytest.approx(
        before
    ), "ein Undo nimmt die Handlung nicht zurück"


def test_scaling_to_the_build_volume_keeps_the_part_on_the_bed(window: MainWindow) -> None:
    """*Auf den Bauraum verkleinern* lässt das Teil auf dem Bett stehen (KUNDE-09).

    Verkleinert wurde um die Mitte; die Unterseite hob sich, und der Bericht
    meldete danach „Ein Objekt schwebt über dem Druckbett“ (Durchsicht 0.5.1,
    am Laptopständer aus dem Druckdialog).
    """
    from app.ui.panels import as_error

    window.open_path(MESHES / "oversized.stl")
    assert window.session.wait_for_idle()
    result = window.session.last_result
    over = [f for f in result.scene.report.findings if f.code == "arrange.out_of_build_volume"]
    assert over, "das Testmodell steht über den Bauraum hinaus"
    window.error_handlers()["scale_to_fit"](as_error(over[0]))
    assert window.session.wait_for_idle()
    after = window.session.last_result
    body = next(iter(after.scene.objects.values()))
    assert body.mesh.bounds.minimum[2] == pytest.approx(0.0, abs=1e-6)
    codes = {f.code for f in after.scene.report.findings}
    assert "arrange.above_bed" not in codes and "arrange.out_of_build_volume" not in codes


def test_only_actions_with_a_handler_are_offered(window: MainWindow) -> None:
    """Lieber ein Knopf weniger als einer, der nichts tut."""
    from app.ui.dialogs import offered_actions

    error = errors.NotManifoldError(open_edges=3)
    offered = {action.id for action in offered_actions(error, window.error_handlers())}

    assert "repair_and_retry" in offered
    assert "show_locations" in offered
    assert "cancel" not in offered, "das Schließen ist kein Vorschlag, es steht ohnehin da"


def test_missing_software_gets_a_button_into_the_install_list(window: MainWindow) -> None:
    """Der Vorschlag war da, der Handler nicht — also stand er als grauer Satz.

    Jede Meldung über fehlende Software schlägt ``install`` vor. Verdrahtet war
    unter dieser Kennung nichts; die Liste der zusätzlichen Programme hing
    unter ``open_settings``, also unter einem Namen, den kein Knopf trug.
    Ergebnis: „… installieren" als Text zum Lesen, während der Dialog, der es
    holt, zwei Menüs entfernt stand.

    Gefunden wurde es an ``ScadUnavailable``, und die Klasse ist mit dem
    OpenSCAD-Ausbau am 26.08.2026 entfallen. Geprüft wird seither an den zwei
    übrigen Wegen, auf denen fehlende Software gemeldet wird — die Zusage
    gilt der **Verdrahtung**, nicht dem Programm, das gerade fehlt.
    """
    from app.core.brep.kernel import BRepUnavailable
    from app.core.errors import ExternalToolError
    from app.ui.dialogs import offered_actions

    for problem in (ExternalToolError(detail="PrusaSlicer"), BRepUnavailable()):
        offered = {action.id for action in offered_actions(problem, window.error_handlers())}
        assert "install" in offered, f"{type(problem).__name__}: kein Weg zur Installation"
        assert "report_error" not in offered, "fehlende Software ist kein Fehlerbericht"


def test_closing_is_no_advice_either(window: MainWindow) -> None:
    """Derselbe Satz gilt für den Text, und dort galt er nicht.

    Jede Ausnahme in ``errors.py`` führt ``CANCEL`` unter ihren Vorschlägen, und
    für keine gibt es einen Handler — ``unhandled_advice`` schrieb „Abbrechen"
    also in **jeden** Fehlerdialog, als Rat, direkt über dem Abbrechen-Knopf.
    Der Grundsatz stand längst daneben, bei den Knöpfen; nur der Textpfad hatte
    ihn nicht übernommen.
    """
    from app.core.errors import CANCEL
    from app.ui.dialogs import unhandled_advice

    known = window.error_handlers()
    for name, value in vars(errors).items():
        if not isinstance(value, type) or not issubclass(value, errors.AppError):
            continue
        suggestions = getattr(value, "default_suggestions", ())
        if CANCEL not in suggestions:
            continue
        error = errors.AppError.__new__(value)
        object.__setattr__(error, "suggestions", list(suggestions))
        assert str(CANCEL.label) not in unhandled_advice(error, known), (
            f"{name} schreibt das Abbrechen als Ratschlag in den Text"
        )


def test_an_error_without_a_handler_still_offers_a_way_out(window: MainWindow) -> None:
    """Ein Dialog mit nur „Abbrechen" ist „fehlgeschlagen" mit mehr Worten.

    **Der Ausweg muss nicht immer ein Knopf sein.** Diese Prüfung verlangte
    früher ``report_error``, und das war die halbe Antwort: Von 48 Kennungen,
    die der Kern in ``Action(...)`` vergibt, sind zehn verdrahtet — die
    übrigen wurden verworfen, und an ihrer Stelle stand der Fehlerbericht als
    Hauptknopf. Auf einen reinen Bedienfehler ist das die falsche lauteste
    Antwort; er gehört laut ``errors.py`` dem ``InternalError``. Der hilfreiche
    Satz des Kernautors steckte derweil im weggeworfenen Knopf.

    Geprüft wird deshalb die Regel und nicht ihre eine Umsetzung: Es bleibt
    **entweder** eine Handlung mit Wirkung **oder** ein Rat zum Lesen. Nur
    beides zugleich leer wäre „fehlgeschlagen" mit mehr Worten.
    """
    from app.ui.dialogs import offered_actions, unhandled_advice

    known = window.error_handlers()
    error = errors.AmbiguityError("Welche Fläche ist gemeint?", ("oben", "unten"))
    offered = [action.id for action in offered_actions(error, known)]
    spoken = unhandled_advice(error, known)

    assert offered or spoken, "weder Knopf noch Rat — genau das darf nicht passieren"
    assert spoken, "die Vorschläge des Kerns dürfen nicht stillschweigend verschwinden"
    assert "report_error" not in offered, (
        "Der Fehlerbericht ist dem InternalError vorbehalten, nicht einer offenen Frage."
    )


def test_every_worker_field_is_waited_for_when_the_window_closes() -> None:
    """Ein Thread, der sein Fenster überlebt, nimmt den Prozess mit.

    ``wait_for_workers`` zählt die Arbeiter von Hand auf, und der Download
    fehlte darin. Er folgt dem Muster mit ``_retire`` und ``_hold_until_done``
    sauber — aber in ``_retired`` landet er erst, wenn er fertig ist. Solange er
    lief, hielt ihn allein sein Feld, und wer währenddessen schloss, bekam
    genau den Absturz, gegen den die Liste geschrieben wurde: einen ohne Zeile,
    weil niemand mehr da war, sie zu schreiben.

    Geprüft wird am Quelltext und nicht am laufenden Fenster: Ein Test, der
    dafür jeden Arbeiter wirklich startet, bräuchte ein Netz, einen Slicer und
    ein Sprachmodell. Was hier zählt, ist die Vollständigkeit der Aufzählung —
    wer ein neues Feld anlegt und es dort vergisst, wird rot.
    """
    import re

    source = (Path(__file__).parent.parent / "app" / "ui" / "main_window.py").read_text(
        encoding="utf-8"
    )
    fields = set(re.findall(r"self\.(_\w*worker\w*)\s*:\s*Any\s*=\s*None", source))
    assert fields, "keine Arbeiterfelder gefunden — dieser Test misst nichts mehr"

    body = source[source.index("def wait_for_workers") :]
    body = body[: body.index("\n    def ", 1)]

    forgotten = sorted(name for name in fields if name not in body)
    assert not forgotten, (
        f"Diese Arbeiter werden beim Schließen nicht abgewartet: {forgotten}. "
        "Solange einer läuft, hält ihn allein sein Feld — `_retired` bekommt ihn "
        "erst, wenn er fertig ist."
    )


def test_closing_keeps_the_window_alive_while_a_worker_is_running(
    window: MainWindow,
) -> None:
    """Ein noch laufender QThread darf sein Fenster nicht überleben."""

    class _RunningWorker:
        def cancel(self) -> bool:
            """Eine schon begonnene Ausgabe läuft vollständig aus."""
            return False

        def isRunning(self) -> bool:  # noqa: N802 — bildet die Qt-API nach
            return True

        def wait(self, _timeout_ms: int) -> bool:
            return False

    window._export_worker = _RunningWorker()
    event = QCloseEvent()

    window.closeEvent(event)

    assert not event.isAccepted()
    assert window._close_retry.isActive()
    assert not window.isEnabled(), "nach der Verwerfentscheidung darf keine neue Änderung entstehen"

    window._close_retry.stop()
    window._close_requested = False
    window._export_worker = None
    window.setEnabled(True)


def test_closing_waits_for_an_installation_dialog_owned_by_the_window(
    window: MainWindow,
) -> None:
    """Eine laufende Installation überlebt weder Fenster noch Hauptprozess."""
    from app.ui.install_dialog import InstallDialog

    class _PendingInstallDialog(InstallDialog):
        def __init__(self, parent: MainWindow) -> None:
            QDialog.__init__(self, parent)
            self.idle = False
            self.waits: list[int] = []

        def wait_for_workers(self, timeout_ms: int = 2000) -> bool:
            self.waits.append(timeout_ms)
            return self.idle

        def release(self, _timeout_ms: int = 2000) -> None:
            """Die Attrappe hält keine eigenen Arbeiter."""

    dialog = _PendingInstallDialog(window)
    first = QCloseEvent()

    window.closeEvent(first)

    assert not first.isAccepted()
    assert window._close_retry.isActive()
    assert dialog.waits == [0]

    dialog.idle = True
    second = QCloseEvent()
    window.closeEvent(second)

    assert second.isAccepted()
    assert dialog.waits == [0, 0]


def test_a_settings_write_error_is_visible_without_breaking_cleanup(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine gesperrte Einstellungsdatei wird gemeldet und nicht hochgeworfen."""
    monkeypatch.setattr("app.ui.main_window.save_settings", lambda _settings: None)

    assert window._store_settings() is False
    assert "Schreibrechte" in window.status_message.text()


def test_the_handlers_are_found_through_the_parent_window(window: MainWindow) -> None:
    """Ein Dialog im Fenster zeigt dieselben Handlungen wie das Fenster."""
    from app.ui.dialogs import handlers_of

    dialog = QDialog(window)
    assert set(handlers_of(dialog)) == set(window.error_handlers())


def test_closing_with_unsaved_changes_asks(window: MainWindow, monkeypatch) -> None:
    """Der Menühinweis versprach das seit jeher; gefragt wurde nie.

    **Gearbeitet wird hier ausdrücklich**, seit ein reines Einlesen nicht mehr
    fragt (RM-130): Der Quader ist die Änderung, die verloren ginge.
    """
    import app.ui.main_window as module

    asked: list[str] = []
    monkeypatch.setattr(
        module, "confirm_unsaved", lambda title, parent: asked.append(title) or "cancel"
    )

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    assert window.session.apply("Quader", [OperationDraft(op="create_box")])
    window.session.wait_for_idle()
    assert window.session.modified

    assert not window._may_discard(), "Abbrechen hält das Schließen an"
    assert asked, "gefragt wurde"


def test_a_model_that_was_only_looked_at_closes_without_a_question(
    window: MainWindow, monkeypatch
) -> None:
    """Wer nur hinsieht, wird nicht gefragt (RM-130).

    Eine STL öffnen, drehen, schließen — dabei ist nichts entstanden, was es
    nicht schon gäbe. Die Frage „Speichern / Verwerfen / Abbrechen" war
    technisch richtig (der Import ist eine Operation) und aus Kundensicht eine
    Frage nach etwas, das er nicht getan hat; Regel 19 verlangt sie nur dort,
    wo etwas unwiederbringlich weg wäre. Gemeldet von Robert am 04.09.2026 an
    allen neunzehn Kundendateien.
    """
    import app.ui.main_window as module

    def niemals(title: str, parent: object) -> str:
        raise AssertionError("ein reines Einlesen darf nicht fragen")

    monkeypatch.setattr(module, "confirm_unsaved", niemals)

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()

    assert window.session.modified, "gesichert wird weiterhin — der Absturz kennt keine Nachfrage"
    assert window.session.only_imported
    assert window._may_discard()


def test_a_model_that_was_only_looked_at_lands_in_the_recent_list(window: MainWindow) -> None:
    """Und der Weg zurück ist ein Klick (RM-130).

    Ohne die Frage beim Schließen ist „Zuletzt geöffnet" der einzige Weg
    zurück zu einer Datei, die man sich gerade angesehen hat — vorher stand
    dort nur, was als Projekt geöffnet wurde. Die Überschrift heißt „Zuletzt
    geöffnet" und nicht „Projekte"; sie stimmt also weiter.
    """
    window.settings.recent = []

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()

    assert window.settings.recent == [str(MESHES / "cube_clean.stl")]


def test_a_saved_project_closes_without_a_question(window: MainWindow, tmp_path: Path) -> None:
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window.session.save_project(tmp_path / "projekt.p3d")

    assert window._may_discard(), "nichts Ungesichertes, nichts zu fragen"


def test_cancelling_the_question_keeps_the_window_open(window: MainWindow, monkeypatch) -> None:
    """Abbrechen heißt abbrechen, nicht „gleich trotzdem".

    Geprüft war bisher nur, dass ``_may_discard`` bei *Abbrechen* nein sagt.
    Ob der ``closeEvent`` diese Antwort auch befolgt, stand nirgends — und
    genau das ist die Frage, die jemand stellt, der vor dem Dialog steht.
    Deshalb geht dieser Test über ``close()`` und sieht dem Fenster danach an,
    dass es noch da ist.

    Der Quader ist die Arbeit, um die es geht: Ein bloßes Einlesen fragt seit
    RM-130 nicht mehr, und ein Test ohne Frage prüfte hier gar nichts.
    """
    from time import monotonic

    from PySide6.QtTest import QTest

    import app.ui.main_window as module

    answers = ["cancel"]
    monkeypatch.setattr(module, "confirm_unsaved", lambda title, parent: answers[0])

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    assert window.session.apply("Quader", [OperationDraft(op="create_box")])
    window.session.wait_for_idle()
    window.show()
    assert window.session.modified

    assert not window.close(), "der Schließversuch wird abgelehnt"
    assert window.isVisible(), "das Fenster steht noch"
    assert window.session.modified, "und die Arbeit ist unberührt"
    assert not window._close_requested, "Abbrechen merkt kein späteres Schließen vor"
    assert window.isEnabled(), "nach Abbrechen bleibt die Arbeit bedienbar"

    answers[0] = "discard"
    window.close()
    assert window._close_requested, "mit Verwerfen ist das Schließen entschieden"
    # Laufende Arbeiter dürfen noch enden; der echte Wiederholungszeitgeber
    # schließt danach ohne einen weiteren Nutzerklick.
    deadline = monotonic() + 30.0
    while window.isVisible() and monotonic() < deadline:
        QTest.qWait(10)
    assert not window.isVisible(), "nach Verwerfen und Arbeiterende schließt das Fenster"


def test_dropping_a_model_on_the_start_screen_asks_before_replacing(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """*Datei → Neu* verwirft bewusst nichts — das Einfügen danach tat es.

    Der Startbildschirm über einem geänderten Projekt ist eine Ansicht, kein
    Verwerfen: Das Projekt bleibt offen. Ein Modell zu ziehen oder
    einzufügen rief dann ``start_new`` ohne jede Frage — Dokument samt
    Verlauf ersetzt, Undo holte nichts zurück (Gesamtreview-b, Bericht 08,
    Fund 1). Jetzt kommt dieselbe Frage wie beim Öffnen einer ``.p3d``.

    Gearbeitet wird dafür ausdrücklich — der Quader neben dem eingelesenen
    Würfel. Ein reines Einlesen wird seit RM-130 nicht mehr gefragt, und der
    Fund von damals betraf das Verwerfen von **Arbeit**.
    """
    import app.ui.main_window as module

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    assert window.session.apply("Quader", [OperationDraft(op="create_box")])
    window.session.wait_for_idle()
    assert window.session.modified
    window.action_new()
    ops_before = [entry.op for entry in window.session.project.document.ops]

    monkeypatch.setattr(module, "confirm_unsaved", lambda title, parent: "cancel")
    window.open_path(MESHES / "plate_holes.stl")

    assert [entry.op for entry in window.session.project.document.ops] == ops_before, (
        "Abbrechen lässt das Projekt, wie es war"
    )

    monkeypatch.setattr(module, "confirm_unsaved", lambda title, parent: "discard")
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    assert [entry.op for entry in window.session.project.document.ops] == ["load"], (
        "Verwerfen beginnt das neue Projekt"
    )


@pytest.mark.parametrize("entry", ["operation", "sketch"])
def test_a_creation_from_the_start_screen_begins_the_empty_project(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, entry: str
) -> None:
    """Palette und Kürzel gelten auch über dem Startbildschirm — und dort begann nichts.

    *Quader anlegen* über Strg+Umschalt+P öffnete seinen Dialog über dem
    Startbildschirm, in einer Sitzung, die nie ausgewertet worden war. Seit
    Übernehmen auf die aktuelle dargestellte Vorschau wartet (20.09.2026),
    gibt es die nur zu einem ausgewerteten Stand: Der Knopf war frei und tat
    nichts (gemessen am 21.09.2026). Jetzt gilt derselbe Weg wie beim Einfügen
    von dort: das leere Projekt beginnt, der Arbeitsbereich kommt, die Vorschau
    liegt im Bild — und ein geändertes Projekt dahinter wird gefragt.
    """
    import app.ui.main_window as module

    assert window.stack.currentWidget() is window.start_screen
    assert not window.session.result_current

    if entry == "sketch":
        window.start_sketch("")
        assert window.sketching()
        assert window.stack.currentWidget() is not window.start_screen
        assert window.session.wait_for_idle(30_000)
        assert window.session.result_current, "das leere Projekt ist ausgewertet"
        window.finish_sketch(keep=False)
        return

    window._run_palette_choice("create_box")
    dialog = window._op_dialog
    assert dialog is not None
    assert window.stack.currentWidget() is not window.start_screen, "die Vorschau liegt im Bild"
    _accept_after_preview(window, dialog)
    assert window.session.wait_for_idle(30_000)
    assert [entry.op for entry in window.session.project.document.ops] == ["create_box"]

    # Über einem geänderten Projekt fragt der Anfang — wie beim Einfügen.
    window.action_new()
    assert window.stack.currentWidget() is window.start_screen
    monkeypatch.setattr(module, "confirm_unsaved", lambda title, parent: "cancel")
    window._run_palette_choice("create_box")
    assert window._op_dialog is None, "Abbrechen lässt das Projekt, wie es war"
    assert [entry.op for entry in window.session.project.document.ops] == ["create_box"]
    monkeypatch.setattr(module, "confirm_unsaved", lambda title, parent: "discard")
    window._run_palette_choice("create_box")
    dialog = window._op_dialog
    assert dialog is not None
    assert window.session.project.document.ops == [], "Verwerfen beginnt das neue Projekt"
    dialog.reject()


# --- Einstellungen an einem Ort (§19.3, §38) ------------------------------------


def test_the_display_unit_reaches_everything_that_shows_a_length(window: MainWindow) -> None:
    """§19.3: die Einstellung gab es seit P0 und niemanden, der sie las.

    **Der Name war eine Zusage, und der Test prüfte zwei Stellen.** Erreicht
    wurden drei — Statusleiste, Objektbaum, Kopfzeile —, und die übrigen elf
    Längenausgaben standen weiter auf der Vorgabe „mm": der ganze
    Skizzeneditor, die Analyseleiste, die Schnittleiste und die
    Merkmalsbeschriftungen. Wer auf Zoll stellte, las im selben Fenster beides.

    Geprüft wird deshalb jetzt auch die freie Ausgabe — ``labels.length`` ohne
    durchgereichte Einheit ist der Weg, den jene elf nehmen — und die
    Kopfzeile, die als Einzige die Einstellung selbst las und trotzdem
    hinterherhing: Sie wurde nur bei Profil- oder Auswertungswechsel neu
    geschrieben.
    """
    from app.ui.labels import display_unit, length

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window._on_scene(window.session.evaluate_now())
    window.object_tree.tree.setCurrentItem(window.object_tree.tree.topLevelItem(0))

    assert "20,00" in window.measurements.text()
    assert "cm³" in window.measurements.text()
    assert "20" in window.header.bounds.full_text(), "die Kopfzeile kennt das Außenmaß"
    assert display_unit() == "mm", "die Vorgabe ist Millimeter"

    window.set_display_unit("in")

    # Die Einheit wechselt, die Schreibweise der Zahl folgt weiter der Sprache
    # — ein Zoll auf einer deutschen Oberfläche schreibt sich mit Komma.
    assert "0,7874" in window.measurements.text(), "20 mm sind 0,7874 Zoll"
    assert "in³" in window.measurements.text()
    assert "in" in window.object_tree.tree.topLevelItem(0).text(1)

    # Die Kopfzeile hing einen Schritt nach: sie liest die Einstellung selbst,
    # wurde aber nur bei Profil- oder Auswertungswechsel neu geschrieben.
    assert "in" in window.header.bounds.full_text(), "die Kopfzeile folgt sofort"
    assert "20,00" not in window.header.bounds.full_text(), "sonst steht dort noch Millimeter"

    # Und der Weg der elf: eine Länge ohne durchgereichte Einheit.
    assert display_unit() == "in"
    assert length(20.0) == "0,7874 in", length(20.0)


def test_the_settings_dialog_writes_every_value_back(qt_app: QApplication) -> None:
    from app.ui.settings_dialog import SettingsDialog

    settings = UiSettings()
    dialog = SettingsDialog(settings)
    dialog.unit.setCurrentIndex(dialog.unit.findData("in"))
    dialog.diff_palette.setCurrentIndex(dialog.diff_palette.findData("red_green"))
    dialog.updates.setChecked(True)

    dialog.apply_to(settings)

    assert (settings.display_unit, settings.diff_palette) == ("in", "red_green")
    assert settings.check_for_updates


def test_the_settings_dialog_offers_only_the_materials_of_the_chosen_technology(
    qt_app: QApplication,
) -> None:
    """RM-071: Ein Harzdrucker bietet Harze an, ein Filamentdrucker Filamente —
    und die Vorgabe folgt dem Wechsel, statt PLA in ein Harzbad zu stellen."""
    from app.core.knowledge import profiles
    from app.ui.settings_dialog import SettingsDialog

    settings = UiSettings()
    dialog = SettingsDialog(settings)
    offered = {str(dialog.material.itemData(i)) for i in range(dialog.material.count())}
    assert "pla" in offered and "resin" not in offered

    dialog.printer.setCurrentIndex(dialog.printer.findData(profiles.DEFAULT_RESIN_PRINTER))
    offered = {str(dialog.material.itemData(i)) for i in range(dialog.material.count())}
    assert offered == {"resin"}
    dialog.apply_to(settings)
    assert (settings.printer, settings.material) == (profiles.DEFAULT_RESIN_PRINTER, "resin")

    dialog.printer.setCurrentIndex(dialog.printer.findData("prusa-mk4s"))
    assert str(dialog.material.currentData()) == "pla"


def test_a_language_change_requests_a_new_settings_dialog(qt_app: QApplication) -> None:
    """Die gewählte Sprache fordert denselben Neuaufbau wie die ersten Schritte an."""
    from app.ui.first_run import LANGUAGE_CHANGED
    from app.ui.settings_dialog import SettingsDialog

    dialog = SettingsDialog(UiSettings())

    other = next(
        index
        for index in range(dialog.language.count())
        if dialog.language.itemData(index) != UiSettings().language
    )
    dialog.language.setCurrentIndex(other)
    assert dialog.result() == LANGUAGE_CHANGED


@pytest.mark.parametrize("accept", [False, True])
def test_two_settings_language_changes_preserve_edits_and_honour_cancel(
    qt_app: QApplication, window: MainWindow, monkeypatch: pytest.MonkeyPatch, accept: bool
) -> None:
    """Zwei echte Dialog-Neuaufbauten bewahren Antworten; nur Speichern ändert die Vorgaben."""
    from copy import deepcopy

    from app.i18n import get_language, set_language
    from app.i18n.catalog import install_language
    from app.ui.app import install_qt_translations
    from app.ui.settings_dialog import SettingsDialog

    window.settings.ai_disclosure_version = "previously shown"
    original = deepcopy(window.settings)
    previous_language = get_language()
    shown: list[str] = []
    stored: list[object] = []
    changed: list[bool] = []
    window.languageChanged.connect(lambda: changed.append(True))
    monkeypatch.setattr(window, "_store_settings", lambda: stored.append(deepcopy(window.settings)))
    monkeypatch.setattr(window, "_apply_settings", lambda: None)
    monkeypatch.setattr(window, "_apply_remote", lambda: None)

    def answer(dialog: SettingsDialog) -> int:
        shown.append(get_language())
        if len(shown) == 1:
            dialog.unit.setCurrentIndex(dialog.unit.findData("in"))
            dialog.theme.setCurrentIndex(dialog.theme.findData("light"))
            dialog.navigation.setCurrentIndex(dialog.navigation.findData("orbit"))
            dialog.updates.setChecked(not original.check_for_updates)
            dialog.remote_port.setValue(9888)
            dialog.ai_disclosure_reset.click()
            dialog.language.setCurrentIndex(dialog.language.findData("en"))
        else:
            assert dialog.windowTitle() == tr("Einstellungen")
            assert dialog.unit.currentData() == "in"
            assert dialog.theme.currentData() == "light"
            assert dialog.navigation.currentData() == "orbit"
            assert dialog.updates.isChecked() is not original.check_for_updates
            assert dialog.remote_port.value() == 9888
            assert dialog._reset_ai_disclosure
            assert not dialog.ai_disclosure_reset.isEnabled()
            assert window.settings == original, "der Entwurf wurde vor dem Speichern übernommen"
            if len(shown) == 2:
                dialog.language.setCurrentIndex(dialog.language.findData("fr"))
            elif accept:
                dialog.accept()
            else:
                dialog.reject()
        return int(dialog.result())

    monkeypatch.setattr(SettingsDialog, "exec", answer)
    try:
        window.action_settings()
        assert shown == [original.language, "en", "fr"]
        if accept:
            assert window.settings.language == "fr"
            assert window.settings.display_unit == "in"
            assert window.settings.theme == "light"
            assert window.settings.remote_port == 9888
            assert not window.settings.ai_disclosure_version
            assert get_language() == "fr"
            assert stored == [window.settings]
            assert changed == [True]
        else:
            assert window.settings == original
            assert get_language() == original.language
            assert not stored
            assert not changed
    finally:
        install_language(previous_language)
        set_language(previous_language)
        install_qt_translations(qt_app, previous_language)


def test_the_printer_of_an_open_project_can_change(session: Session) -> None:
    """§12: er wurde einmal beim Anlegen gesetzt und danach nie wieder — wer
    eine fremde Datei öffnete, arbeitete für immer gegen deren Bauraum.
    """
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()
    before = session.project.document.printer

    session.change_scene_profile("prusa-mk4s", "petg")
    session.wait_for_idle()

    assert session.project.document.printer == "prusa-mk4s"
    assert session.profile.printer.id == "prusa-mk4s", "das Profil folgt, nicht nur die Kennung"

    session.undo()
    assert session.project.document.printer == before, "eine Transaktion, also rücknehmbar"


# --- Entdeckbarkeit (§2.6, §19.2) -----------------------------------------------


def test_the_palette_reaches_more_than_the_registry(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§2.6: die Palette ist der Universalzugang — sie kannte nur Operationen.

    Speichern, das Handbuch und die sieben Ansichtswerkzeuge stehen nicht im
    Register. `ToolStrip.tool_titles()` und `strip_title()` wurden dafür
    geschrieben und hatten außer Tests keinen Aufrufer.
    """
    opened: list[bool] = []
    monkeypatch.setattr(window, "_open_catalog", lambda: opened.append(True))
    commands = window.window_commands()

    assert "file.save" in commands
    assert "help.manual" in commands
    assert commands["file.part_adopt"][0] == "Baustein aus Datei hinzufügen …"
    assert commands["file.part_share"][0] == "Baustein als Datei weitergeben …"
    commands["file.part_share"][2]()
    assert opened == [True], "die Weitergabe öffnet den Katalog zur Auswahl"
    for key in window.tools.tool_titles():
        assert f"tool.{key}" in commands, f"{key} fehlt in der Palette"

    for _title, _shortcut, slot in commands.values():
        assert callable(slot)


def test_part_file_commands_do_not_add_a_file_menu_row(window: MainWindow) -> None:
    """Beide Dateihandlungen leben in der Palette; das volle Menü bleibt an der Grenze."""
    from app.core.registry.surfaces import MAX_MENU_ROWS

    file_menu = next(
        action.menu()
        for action in window.menuBar().actions()
        if action.menu() is not None and action.text().replace("&", "") == "Datei"
    )
    assert file_menu is not None
    rows = [action for action in file_menu.actions() if not action.isSeparator()]
    titles = {action.text().replace("&", "") for action in rows}

    assert "Baustein aus Datei hinzufügen …" not in titles
    assert "Baustein als Datei weitergeben …" not in titles
    assert len(rows) <= MAX_MENU_ROWS


def test_escape_closes_the_open_tool(window: MainWindow) -> None:
    """`close_tool` gab es seit jeher und niemanden, der es rief."""
    window.tools.toggle("section")
    assert window.tools.active() == "section"

    window.tools.close_tool()
    assert window.tools.active() is None


def test_the_view_menu_can_fit(window: MainWindow) -> None:
    """Ohne diesen Eintrag musste man wissen, dass Strg+0 nebenbei einpasst."""
    labels = {action.text() for action in all_menu_actions(window)}
    assert "Einpassen" in labels


def test_the_first_body_gets_the_camera(window: MainWindow) -> None:
    """Sonst bleibt die Kamera, wo sie war, und das Teil liegt außerhalb des
    Bildes — die Anwendung sieht aus, als hätte sie nichts geladen."""
    assert not window._seen_objects

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window._on_scene(window.session.evaluate_now())

    assert window._seen_objects


def test_the_toolbar_buttons_carry_a_symbol_and_show_their_words(
    window: MainWindow,
) -> None:
    """Die wichtigsten Wege stehen als Zeichen und Wort in derselben Zeile."""
    from app.ui import icons

    for name in ("new", "open", "save", "import"):
        assert name in icons.known(), f"{name} fehlt im Symbolkatalog"

    from PySide6.QtWidgets import QWidgetAction

    toolbar = window.findChildren(QToolBar)[0]
    assert toolbar.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    for action in toolbar.actions():
        # Eingehängte Widgets sind keine Knöpfe: sie tragen ihre Beschriftung
        # selbst, und ein leerer ``text()`` ist bei ihnen kein Befund.
        if isinstance(action, QWidgetAction) or action.isSeparator():
            continue
        assert action.text(), "das Wort bleibt"
        assert not action.icon().isNull(), f"{action.text()} ohne Zeichen"
        assert action.toolTip(), f"{action.text()} ohne Hinweis am Zeiger"
        assert action.statusTip(), f"{action.text()} ohne Hinweis in der Statuszeile"

    labels = {action.text() for action in toolbar.actions()}
    assert {"Neues Projekt", "Modell einfügen", "Zeichnen", "Formen", "Skelett"} <= labels


def test_a_labelled_button_keeps_the_reason_short(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der sichtbare Name muss in einem Sperrhinweis nicht wiederholt werden.

    Beide Helfer, die einen Hinweis überschreiben, sind vertreten: die Sperre
    nach abgelaufenem Testzeitraum (``_lock_hint``) und die fehlende Auswahl
    (``_pick_hint``). Das Wort steht am Knopf; der Hinweis nennt nur den Grund.
    """
    _expired(monkeypatch)
    window = MainWindow(Session(), UiSettings())

    assert "Lizenzschlüssel" in window._toolbar_import.toolTip()
    assert not window._toolbar_import.toolTip().startswith("Modell einfügen")

    from app.core import activation

    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=99))
    window._update_actions()

    assert "ausgewählten Körper" in window._toolbar_sculpt.toolTip()
    assert not window._toolbar_sculpt.toolTip().startswith("Formen")
    # Und im Menü, wo der Name danebensteht, bleibt der Grund allein.
    assert not window.import_action.toolTip().startswith("Modell einfügen …")


def test_a_labelled_button_still_teaches_what_it_does_and_which_key(
    qt_app: QApplication,
) -> None:
    """Der sichtbare Kurzname ersetzt weder Zweck noch Tastenkürzel.

    Der Satz wird nicht abgeschrieben, sondern von der Menü-Action geholt;
    zwei Versionen desselben Satzes würden sonst auseinanderlaufen.
    """
    window = MainWindow(Session(), UiSettings())

    tip = window._toolbar_import.toolTip()
    assert window.import_action.statusTip() in tip, "der Satz kommt aus dem Menüeintrag"
    assert "Ctrl+I" in tip or "Strg+I" in tip, "und das Kürzel steht dabei"

    # Die drei ohne Menüpendant tragen ihren eigenen Satz — leer wäre keiner.
    assert len(window._toolbar_sketch.toolTip()) > len("Zeichnen")


# --- Die Aufräumrunde -----------------------------------------------------------


def test_the_keyboard_reaches_zoom_and_the_next_body(window: MainWindow) -> None:
    """§19.2: der Viewport ist mit der Tastatur navigierbar.

    Die Achsansichten waren es, Zoom und Durchblättern nicht — wer ohne
    Zeigegerät arbeitet, sah jedes Modell aus derselben Entfernung.
    """
    _with_two_objects(window)
    window.object_tree.tree.topLevelItem(0).setSelected(True)
    assert window.object_tree.selected_objects() == ("obj_1",)

    window.object_tree.step_selection(True)
    assert window.object_tree.selected_objects() == ("obj_2",)

    # Reihum: hinter dem letzten kommt wieder der erste.
    window.object_tree.step_selection(True)
    assert window.object_tree.selected_objects() == ("obj_1",)

    window.object_tree.step_selection(False)
    assert window.object_tree.selected_objects() == ("obj_2",)

    shortcuts = {entry.key().toString() for entry in window.findChildren(QShortcut)}
    assert "Ctrl+Tab" in shortcuts
    assert any("+" in text for text in shortcuts), "der Zoom hat ein Kürzel"


def test_the_default_navigation_is_solidons_own() -> None:
    """Die Vorgabe ist die eigene Steuerung, nicht mehr die von Cura (§2.9).

    Bis zum 03.09.2026 sicherte dieser Test das Gegenteil zu: „die Vorgabe
    folgt weiter §2.9" hieß damals ``slicer``. Robert hat sie an diesem Tag
    umgelegt, und der Bauplan ist mitgezogen — eine Zusicherung, die einer
    Entscheidung widerspricht, ist kein Schutz, sondern ein Hindernis.

    Was bleibt, ist die Aussage darunter: Die vier Nachbildungen sind alle
    noch da. Eine neue Vorgabe darf keine Wahl kosten, die jemand schon
    getroffen hat.
    """
    from app.ui.settings_dialog import NAVIGATION

    assert UiSettings().navigation == "solidon", "die Vorgabe ist die eigene"
    for nachbildung in ("slicer", "orbit", "cad", "blender"):
        assert nachbildung in NAVIGATION, f"{nachbildung} ist verschwunden"


def test_the_report_can_be_filtered(window: MainWindow) -> None:
    """Ein Bericht mit hundert Hinweisen und zwei Fehlern versteckt die zwei.

    Die Liste steht nach Schwere: der Fehler ist die erste Zeile, der Hinweis
    die zweite — auch wenn der Hinweis zuerst gemeldet wurde.
    """
    from app.core.types import Finding

    window.report.add_findings(
        [
            Finding(code="a", severity="info", message="Wandstärke knapp"),
            Finding(code="b", severity="error", message="Netz ist offen"),
        ]
    )
    assert window.report.list.count() == 2

    window.report.severity.setCurrentIndex(window.report.severity.findData("error"))
    hidden = [window.report.list.item(row).isHidden() for row in range(window.report.list.count())]
    assert hidden == [False, True]

    window.report.severity.setCurrentIndex(0)
    window.report.search.setText("wandstärke")
    hidden = [window.report.list.item(row).isHidden() for row in range(window.report.list.count())]
    assert hidden == [True, False], "der Text filtert unabhängig vom Schweregrad"

    assert "1 × Fehler" in window.report.summary.text(), "gezählt wird der ganze Bericht"


def test_the_history_shows_what_a_redo_would_bring_back(window: MainWindow) -> None:
    """Zurückgenommene Schritte verschwanden hier spurlos."""
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window._on_project()
    before = window.history_panel.list.count()

    window.session.undo()
    window.session.wait_for_idle()
    window._on_project()

    labels = [
        window.history_panel.list.item(row).text()
        for row in range(window.history_panel.list.count())
    ]
    assert any("zurückgenommen" in text for text in labels), labels
    assert window.history_panel.list.count() == before, "nichts verschwindet, es wechselt die Seite"


def test_a_recent_entry_can_be_forgotten(window: MainWindow, tmp_path: Path) -> None:
    """Was einmal in der Liste stand, blieb bis es hinausrutschte."""
    path = tmp_path / "versuch.p3d"
    window.settings.recent = [str(path)]

    window._forget_recent(path)

    assert window.settings.recent == []


# --- Parameter ohne Agent anlegen (§13, §2.3) ------------------------------------


def test_a_parameter_can_be_added_without_the_agent(session: Session) -> None:
    """§2.3 verspricht: ohne KI funktioniert alles außer dem Chat. Das
    Anlegen eines Parameters war aber ein reines Agentenwerkzeug — und ein
    Undo muss den neuen Parameter entfernen, nicht auf Null setzen (§15.5)."""
    session.add_parameter(Parameter(name="width", value=40.0))

    assert "width" in session.project.document.parameters
    assert session.modified

    session.undo()
    assert "width" not in session.project.document.parameters


def test_adding_a_taken_parameter_name_fails(session: Session) -> None:
    """Ein zweiter Parameter gleichen Namens überschriebe den ersten still —
    stattdessen kommt ein Fehler mit Vorschlag (§2.7)."""
    caught: list[object] = []
    session.failed.connect(caught.append)
    session.add_parameter(Parameter(name="width", value=40.0))

    session.add_parameter(Parameter(name="width", value=50.0))

    assert caught, "der zweite Versuch meldet sich"
    assert session.project.document.parameters["width"].value == pytest.approx(40.0)


def test_a_parameter_expression_may_not_cycle(session: Session) -> None:
    """Die Zyklusprüfung aus §13 gilt auch für den Weg über die Leiste."""
    caught: list[object] = []
    session.failed.connect(caught.append)
    session.add_parameter(Parameter(name="width", value=40.0))

    session.add_parameter(Parameter(name="height", value=0.0, expression="=@missing + 1"))

    assert caught, "ein Ausdruck auf einen unbekannten Parameter wird abgelehnt"
    assert "height" not in session.project.document.parameters


def test_the_parameter_dialog_validates_inline(qt_app: QApplication) -> None:
    """Der Dialog lehnt inline ab, statt ein Fenster auf ein Fenster zu
    stellen: leerer Name, vergebener Name, kaputter Ausdruck."""
    from app.ui.dialogs import ParameterDialog

    taken = {"width": Parameter(name="width", value=40.0)}
    dialog = ParameterDialog(taken)

    assert dialog.validation_problem() is not None, "ohne Namen geht es nicht"

    dialog.name_field.setText("width")
    assert dialog.validation_problem() is not None, "der Name ist vergeben"

    dialog.name_field.setText("height")
    dialog.expression_field.setText("=@width / 2")
    assert dialog.validation_problem() is None
    made = dialog.parameter()
    assert made.expression == "=@width / 2"
    assert made.value == pytest.approx(20.0), "der Startwert kommt aus dem Ausdruck"

    dialog.expression_field.setText("import os")
    assert dialog.validation_problem() is not None, "alles außerhalb der Grammatik fällt durch"

    # Ohne ``=`` und ``@`` getippt, wie auf der Website (Durchsicht 0.5.0):
    # angenommen, und gespeichert in der Form mit beidem.
    dialog.expression_field.setText("width / 4")
    assert dialog.validation_problem() is None
    assert dialog.parameter().expression == "=@width / 4"


def test_the_parameter_dialog_offers_fx_and_parameter_choices(qt_app: QApplication) -> None:
    """Formeln beginnen über sichtbare Werkzeuge, nicht über auswendig gelernte Syntax."""
    from app.ui.dialogs import ParameterDialog

    parameters = {
        "width": Parameter(name="width", value=40.0, title="Breite"),
        "depth": Parameter(name="depth", value=30.0, title="Tiefe"),
    }
    dialog = ParameterDialog(parameters)
    dialog.name_field.setText("height")
    dialog.show()
    QApplication.processEvents()

    assert not dialog.fx_button.isChecked()
    assert not dialog.expression_field.isVisibleTo(dialog)
    dialog.fx_button.click()
    assert dialog.fx_button.isChecked()
    assert dialog.expression_field.isVisibleTo(dialog)
    assert not dialog.value_field.isEnabled(), (
        "die Formel und die Zahl dürfen nicht zugleich gelten"
    )

    menu = dialog.parameter_button.menu()
    assert menu is not None
    choices = {action.data(): action for action in menu.actions()}
    assert set(choices) == {"width", "depth"}
    choices["width"].trigger()

    assert dialog.expression_field.text() == "=@width"
    assert dialog.validation_problem() is None
    assert dialog.parameter().expression == "=@width"

    choices["depth"].trigger()

    assert dialog.expression_field.text() == "=@depth", (
        "eine korrigierte Auswahl ersetzt den alten Verweis statt ihn anzuhängen"
    )
    assert dialog.validation_problem() is None


def test_the_parameter_dialog_uses_fixed_units_and_honest_decimals(
    qt_app: QApplication,
) -> None:
    """Einheiten sind auswählbar; ganze Werte zeigen mindestens zwei Stellen."""
    from app.core.units import DEGREE_UNIT
    from app.ui.dialogs import ParameterDialog

    dialog = ParameterDialog({})
    dialog.name_field.setText("angle")

    assert isinstance(dialog.unit_field, QComboBox)
    assert not dialog.unit_field.isEditable()
    assert [dialog.unit_field.itemData(index) for index in range(dialog.unit_field.count())] == [
        "mm",
        DEGREE_UNIT,
        "",
    ]
    dialog.unit_field.setCurrentIndex(dialog.unit_field.findData(DEGREE_UNIT))
    assert dialog.parameter().unit == DEGREE_UNIT

    separator = QLocale().decimalPoint()
    dialog.value_field.setValue(12.0)
    assert dialog.value_field.text() == f"12{separator}00"
    dialog.value_field.setValue(0.075)
    assert dialog.value_field.text() == f"0{separator}075", "Feinmaße bleiben sichtbar"

    unknown = Parameter(name="legacy", value=10.0, unit="cm")
    old_dialog = ParameterDialog({"legacy": unknown}, existing=unknown)
    assert old_dialog.unit_field.currentData() == "cm", "alte Dateien werden nicht umgedeutet"
    assert not old_dialog.unit_field.isEditable()


def test_the_parameter_dialog_offers_bounds(qt_app: QApplication) -> None:
    """Die Schreibseite der Grenzen (Gesamtreview B-15).

    Die Leiste liest minimum/maximum seit je und fiel immer auf ±100 000
    zurück, weil keine Stelle der Anwendung die Felder je setzte. Der Dialog
    bietet sie jetzt an — leer heißt weiter: keine Grenze.
    """
    from app.ui.dialogs import ParameterDialog

    dialog = ParameterDialog({})
    dialog.name_field.setText("depth")
    dialog.value_field.setValue(50.0)
    assert dialog.validation_problem() is None, "ohne Grenzen wie bisher"

    dialog.minimum_field.setText("0")
    dialog.maximum_field.setText("60")
    assert dialog.validation_problem() is None
    made = dialog.parameter()
    assert made.minimum == 0.0
    assert made.maximum == 60.0

    dialog.maximum_field.setText("40")
    assert dialog.validation_problem() is not None, "der Wert liegt über der Obergrenze"

    dialog.maximum_field.setText("-10")
    assert dialog.validation_problem() is not None, "Untergrenze über Obergrenze"

    dialog.maximum_field.setText("abc")
    assert dialog.validation_problem() is not None, "keine Zahl ist keine Grenze"


def test_a_limit_that_is_set_can_be_changed_again(session: Session) -> None:
    """Grenzen waren anlegbar und nie änderbar (§2.1: keine Sackgassen).

    Die Parameterleiste liest ``minimum``/``maximum`` nur als Spinbox-Grenzen
    und bietet nichts zum Bearbeiten; der einzige Dialog dazu weist einen
    vorhandenen Namen ab. Wer eine Obergrenze auf 100 gesetzt hatte und später
    150 brauchte, fand ein Feld, das ohne ein Wort klemmt, und keinen dritten
    Weg.

    Rücknehmbar muss es sein, weil es eine Dokumentänderung ist (§15.5) — ein
    Undo stellt die alte Grenze her und nicht bloß den alten Wert.
    """
    session.add_parameter(Parameter(name="breite", value=40.0, maximum=100.0, title="Breite"))

    weiter = dataclasses.replace(session.project.document.parameters["breite"], maximum=150.0)
    assert session.edit_parameter("breite", weiter)

    stand = session.project.document.parameters["breite"]
    assert stand.maximum == pytest.approx(150.0)
    assert stand.value == pytest.approx(40.0), "die Zahl bleibt, die Grenze wandert"
    assert stand.title == "Breite", "der Titel überlebt die Änderung"

    session.undo()
    assert session.project.document.parameters["breite"].maximum == pytest.approx(100.0)


def test_changing_a_limit_to_the_same_value_writes_no_transaction(session: Session) -> None:
    """Ein Undo, das nichts zurücknimmt, ist ein Undo, das der Kunde verliert.

    Wer den Dialog öffnet und mit *Übernehmen* schließt, ohne etwas zu ändern,
    darf keine Zeile im Verlauf erzeugen — sonst kostet ihn der nächste
    Strg+Z einen Schritt, den er nicht gemacht hat.
    """
    session.add_parameter(Parameter(name="breite", value=40.0, maximum=100.0))
    vorher = len(session.history.transactions)

    gleich = dataclasses.replace(session.project.document.parameters["breite"])

    assert not session.edit_parameter("breite", gleich)
    assert len(session.history.transactions) == vorher


def test_the_parameter_dialog_edits_what_is_there(qt_app: QApplication) -> None:
    """Derselbe Dialog ändert, was er angelegt hat — vorbelegt und ohne Absage.

    Zwei Dinge, die beide fehlten: Die Felder standen leer da (ein
    Änderungsdialog, der nichts zeigt, verlangt vom Kunden, sich zu erinnern),
    und der eigene Name fiel unter „Diesen Namen gibt es schon".

    Der Name selbst bleibt stehen: Er ist der Schlüssel, unter dem jeder
    Ausdruck das Maß nennt (``@breite``), und ihn hier umzuschreiben hieße,
    alle diese Verweise mitzuziehen.
    """
    from app.ui.dialogs import ParameterDialog

    bestand = {"breite": Parameter(name="breite", value=40.0, unit="mm", maximum=100.0)}
    dialog = ParameterDialog(bestand, existing=bestand["breite"])

    assert dialog.name_field.text() == "breite"
    assert dialog.name_field.isReadOnly(), "der Schlüssel wechselt hier nicht"
    assert dialog.name_field.toolTip(), "und sagt warum"
    assert dialog.value_field.value() == pytest.approx(40.0)
    assert dialog.maximum_field.text() == "100"
    assert dialog.minimum_field.text() == "", "keine Grenze bleibt keine Grenze"
    assert dialog.validation_problem() is None, "der eigene Name ist kein vergebener"

    dialog.maximum_field.setText("150")
    assert dialog.parameter().maximum == pytest.approx(150.0)


def test_the_parameter_bar_offers_the_way_to_the_limits(qt_app: QApplication) -> None:
    """Der Weg dorthin: Rechtsklick auf die Zeile, ein Eintrag.

    Geprüft am gebauten Menü und über das Auslösen des Eintrags, nicht am
    Aufruf dahinter: Ohne die Verbindung wäre der Eintrag ein Knopf, der
    nichts tut. ``exec`` bliebe stehen — deshalb gibt ``context_menu`` das
    Menü heraus, wie es der Objektbaum daneben tut.
    """
    from app.core.types import Document
    from app.ui.panels import ParameterPanel

    panel = ParameterPanel()
    document = Document(format_version=1, app_version="0.0.1")
    document.parameters["breite"] = Parameter(name="breite", value=40.0, maximum=100.0)
    panel.show_document(document)
    panel.resize(320, 200)
    panel.layout().activate()

    editor = panel._editors["breite"]
    assert panel.parameter_at(editor.geometry().center()) == "breite"

    gerufen: list[str] = []
    panel.limitsRequested.connect(gerufen.append)
    menu = panel.context_menu(editor.geometry().center())
    assert menu is not None
    aktionen = menu.actions()
    assert len(aktionen) == 1, [a.text() for a in aktionen]
    aktionen[0].trigger()
    assert gerufen == ["breite"], "der Eintrag nennt seine Zeile"

    assert panel.context_menu(QPoint(-5, -5)) is None, "kein Menü, wo keine Zeile steht"


def test_the_catalog_button_says_what_it_does(qt_app: QApplication) -> None:
    """„OK" sagte nicht, was es tut — im Katalog blieb der Standardknopf
    stehen, während jeder Operationsdialog längst nach seiner Operation
    heißt."""
    from PySide6.QtWidgets import QDialogButtonBox

    from app.ui.catalog import PartCatalog

    catalog = PartCatalog()
    box = catalog.findChild(QDialogButtonBox)
    assert box is not None
    ok = box.button(QDialogButtonBox.StandardButton.Ok)
    assert ok is not None
    assert ok.text().replace("&", "") == "Einfügen"


def test_the_catalog_says_in_words_what_takes_material_away(qt_app: QApplication) -> None:
    """Regel 18: was subtraktiv ist, trug allein die Farbe des Vorschaubilds.

    Orange nimmt weg, grau setzt hinzu — ohne Legende, und für jeden, der die
    beiden Farben nicht unterscheidet, gar nicht.
    """
    from app.core.knowledge.parts import PARTS
    from app.ui.catalog import SUBTRACTIVE_MARKER, describe

    subtractive = [spec for spec in PARTS.all() if spec.subtractive]
    additive = [spec for spec in PARTS.all() if not spec.subtractive]
    assert subtractive and additive, "sonst prüft dieser Test nichts"

    for spec in subtractive:
        assert SUBTRACTIVE_MARKER in describe(spec)
        assert tr("nimmt Material weg") in describe(spec)
    for spec in additive:
        assert tr("nimmt Material weg") not in describe(spec)


def test_the_detail_column_explains_the_chosen_part(qt_app: QApplication) -> None:
    """Eine Kachel trägt so viel, wie auf eine Kachel passt.

    Alles Weitere stand in einem Tooltip, den man erst findet, wenn man weiß,
    dass er da ist.
    """
    from app.core.knowledge.parts import PARTS
    from app.ui.catalog import PartCatalog, detail

    assert tr("Wählen Sie") in detail(None), "ohne Auswahl sagt sie, was zu tun ist"

    spec = next(entry for entry in PARTS.all() if entry.subtractive)
    text = detail(spec)
    assert str(spec.title) in text
    assert str(spec.doc) in text
    assert tr("nimmt Material weg") in text
    for entry in spec.params.spec():
        assert str(entry.title) in text, "alle Parameter, nicht nur die zwei der Kachel"

    catalog = PartCatalog()
    assert catalog.detail.text() == detail(None), "beim Öffnen ist nichts gewählt"


def test_the_catalog_grid_never_scrolls_sideways(qt_app: QApplication) -> None:
    """Das Raster bricht um — eine Leiste darunter hieße, dass es das nicht
    tut."""
    from PySide6.QtCore import Qt

    from app.ui.catalog import PartCatalog

    catalog = PartCatalog()
    assert catalog.list.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


# --- Auto Split abseits des Hauptthreads (§2.8) ----------------------------------


def test_a_fitting_body_gets_the_same_passive_reply_at_the_action_and_in_status(window):
    """Der echte Menüweg bleibt ohne neue Operation und quittiert im Blickfeld."""
    assert window.session.apply("Quader", [OperationDraft(op="create_box")])
    window.session.wait_for_idle()
    count = len(window.session.project.document.ops)
    window.action_auto_split("obj_1")
    window.session.wait_for_idle()
    expected = tr("Dieses Objekt passt bereits auf das Bett.")
    notice = window._action_notice
    assert window._announcement == expected
    assert window.status_message.text() == expected
    assert notice.text() == expected and not notice.isHidden()
    assert notice.parentWidget() is window.overlay
    assert notice.testAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
    assert notice.focusPolicy() == Qt.FocusPolicy.NoFocus
    assert notice._expiry.isActive() and notice._expiry.interval() >= 8000
    assert len(window.session.project.document.ops) == count


def test_evaluation_cancellation_replaces_the_action_reply_and_its_timer(window):
    """Das echte Sitzungssignal ersetzt eine alte Quittung an beiden sichtbaren Orten."""
    window.announce("Vorherige Meldung")
    notice = window._action_notice
    # Ein alter Ablauf darf der neuen, längeren Meldung keine Restzeit leihen.
    notice._expiry.start(1000)
    window.session.evaluationCancelled.emit()
    expected = tr(
        "Abgebrochen. Zu sehen ist der letzte vollständig gerechnete Stand — "
        "eine Änderung am Stapel rechnet weiter."
    )
    assert window._announcement == expected
    assert window.status_message.text() == expected
    assert notice.text() == expected and not notice.isHidden()
    assert notice._expiry.isActive()
    assert notice._expiry.interval() == max(8000, len(expected) * 60)
    window._on_busy(False)
    assert notice.text() == expected and window.status_message.text() == expected


def test_action_reply_survives_progress_and_replaces_its_previous_text(window):
    """Auslaufender Fortschritt überschreibt weder Karte noch Ergebnisquittung."""
    window.announce("Erster Hinweis")
    notice = window._action_notice
    second = "<b>Lesbarer Klartext</b> " + "Längerer verständlicher Hinweis. " * 10
    window.announce(second)
    assert notice.textFormat() == Qt.TextFormat.PlainText
    assert notice.wordWrap() and notice.text() == second
    assert notice._expiry.interval() >= len(second) * 60
    window._on_progress(0.5, "Wird berechnet")
    window._on_progress(1.0, "")
    window._on_busy(False)
    assert notice.text() == second and not notice.isHidden()
    assert window.status_message.text() == second
    notice._expiry.timeout.emit()
    assert notice.isHidden() and not notice._expiry.isActive()
    assert window._announcement == second and window.status_message.text() == second


@pytest.mark.parametrize("theme", ["dark", "light"])
def test_action_reply_wraps_inside_the_overlay_after_resize_and_font_growth(window, theme):
    """Längere Texte folgen Schrift und Fenster, ohne einen Eingabefänger zu schaffen."""
    from PySide6.QtGui import QFont

    notice = window._action_notice
    notice.set_theme(theme)
    font = QFont(notice.font())
    font.setPointSizeF(max(16.0, font.pointSizeF() * 1.5))
    notice.setFont(font)
    window.overlay.resize(700, 600)
    notice.show_message("Ein längerer Hinweis zum gewählten Körper. " * 4, QPoint(690, 590))
    assert window.overlay.rect().contains(notice.geometry())
    assert notice.height() > notice.fontMetrics().height()
    window.overlay.resize(420, 600)
    notice.place()
    assert window.overlay.rect().contains(notice.geometry())
    assert window.overlay.childAt(notice.geometry().center()) is not notice


def test_action_reply_uses_keyboard_focus_and_disappears_on_project_change(window, monkeypatch):
    """Tastaturzugang braucht keinen Mauszeiger; alte Quittungen reisen nicht mit."""
    window.setAttribute(Qt.WidgetAttribute.WA_KeyboardFocusChange, True)
    monkeypatch.setattr(QApplication, "focusWidget", staticmethod(lambda: window.status_message))
    expected = window.overlay.mapFromGlobal(
        window.status_message.mapToGlobal(window.status_message.rect().center())
    )
    window.announce("Gespeichert")
    assert window._action_notice._anchor == expected
    window.session.start_new("centauri-carbon-2", "petg")
    window.session.wait_for_idle()
    assert window._action_notice.isHidden()
    assert not window._action_notice._expiry.isActive()
    assert window._announcement == "" and window.status_message.text() == ""
    window.announce("Weitere Meldung")
    window.release()
    assert window._action_notice.isHidden()
    assert not window._action_notice._expiry.isActive()


def test_the_split_worker_forwards_the_core_progress(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Arbeiter reicht den echten Kernfortschritt bis zu seinem Signal."""
    from app.ui import session as session_module

    def planned(*_args: object, progress=None, **_kwargs: object) -> object:
        assert progress is not None, "der Kern bekam keinen Fortschrittskanal"
        progress(0.25, "Grobsuche")
        progress(0.75, "Stützbewertung")
        progress(1.0, "")
        return object()

    monkeypatch.setattr(session_module, "plan_split", planned)
    worker = session_module._SplitWorker(object(), "obj_1", session.profile, {})
    seen: list[tuple[float, str]] = []
    worker.progressed.connect(lambda fraction, text: seen.append((fraction, text)))

    worker.work()

    assert seen == [(0.25, "Grobsuche"), (0.75, "Stützbewertung"), (1.0, "")]


def test_only_the_current_split_worker_can_report_progress(session: Session) -> None:
    """Nachzügler und verworfene Suchen überschreiben keine neue Anzeige."""
    current = object()
    session._split = current
    seen: list[tuple[float, str]] = []
    cancelled: list[bool] = []
    session.splitProgressChanged.connect(lambda value, text: seen.append((value, text)))
    session.splitCancelled.connect(lambda: cancelled.append(True))
    try:
        session._split_progress(object(), 0.2, "alt")
        session._split_progress(current, 0.3, "aktuell")
        session._split_cancelled(object())
        assert not cancelled, "ein veralteter Arbeiter bestätigte den Abbruch"
        session._split_cancelled(current)
        session._split_discarded = True
        session._split_progress(current, 0.8, "verworfen")
    finally:
        session._split = None
        session._split_discarded = False

    assert seen == [(0.3, "aktuell")]
    assert cancelled == [True]


def _progress_snapshot(window: MainWindow) -> tuple[object, ...]:
    """Der vollständige sichtbare Vertrag des gemeinsamen Fortschrittsbereichs."""

    return (
        window.status_message.text(),
        window.progress.minimum(),
        window.progress.maximum(),
        window.progress.value(),
        window.progress.accessibleName(),
        window.progress.accessibleDescription(),
        window.progress.isVisibleTo(window),
        window.cancel_button.isVisibleTo(window),
        window.cancel_button.isEnabled(),
        window.cancel_button.accessibleDescription(),
    )


class _RunningSplit:
    """Der minimale laufende Arbeiter für die Signalkette des Fensters."""

    def __init__(self) -> None:
        from app.core.scene.cancel import CancelSignal

        self.cancel = CancelSignal()

    def isRunning(self) -> bool:  # noqa: N802 — bildet die Qt-API nach
        return True


def _show_split_progress(window: MainWindow) -> None:
    window.session._split = _RunningSplit()
    window.session.splitBusyChanged.emit(True)
    window.session.splitProgressChanged.emit(0.65, tr("Ausrichtung suchen"))
    window._split_patience.timeout.emit()
    window._split_bar_delay.timeout.emit()


def _finish_split_progress(window: MainWindow) -> None:
    window.session._split = None
    window.session._split_discarded = False
    window.session.splitBusyChanged.emit(False)


def test_split_restores_the_complete_agent_progress(window: MainWindow) -> None:
    """Split überdeckt den Agenten, ohne dessen Anzeige oder Abbruch zu verlieren."""

    window.session.busyChanged.emit(True)
    window._on_agent_busy(True)
    window._on_agent_progress(3, "boolesche Operation")
    expected = _progress_snapshot(window)

    _show_split_progress(window)
    assert window._progress_owner == "split"
    split_worker = window.session._split
    assert split_worker is not None
    window.cancel_button.click()
    assert split_worker.cancel.is_cancelled
    assert not window.session.agent_cancel.is_cancelled
    assert not window.session.cancel_signal.is_cancelled
    _finish_split_progress(window)

    assert window._progress_owner == "agent"
    assert _progress_snapshot(window) == expected
    window.cancel_button.click()
    assert window.session.agent_cancel.is_cancelled, "der wieder sichtbare Knopf gilt dem Agenten"
    assert not window.session.cancel_signal.is_cancelled, "die verdeckte Auswertung läuft weiter"
    window._on_agent_busy(False)
    assert window._progress_owner == "evaluation"
    window.cancel_button.click()
    assert window.session.cancel_signal.is_cancelled, (
        "nach Agentenende gilt der Knopf der Auswertung"
    )
    window.session.busyChanged.emit(False)


def test_split_restores_the_complete_download_progress(
    window: MainWindow,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
) -> None:
    """Nach Split stehen Downloadtext, Anteil, Hilfetext und Abbruch wieder da."""

    monkeypatch.setattr(window._leash, "start", lambda _worker: None)
    window.session.busyChanged.emit(True)
    window._on_agent_busy(True)
    window.download_model("https://beispiel.invalid/halter.stl")
    worker = window._download_worker
    assert worker is not None
    request.addfinalizer(lambda: _release_unstarted_worker(window, "_download_worker", worker))
    window._on_download_progress(0.42, tr("Modell herunterladen …"))
    expected = _progress_snapshot(window)

    _show_split_progress(window)
    assert window._progress_owner == "split"
    split_worker = window.session._split
    assert split_worker is not None
    window.cancel_button.click()
    assert split_worker.cancel.is_cancelled
    assert not window.session.agent_cancel.is_cancelled
    assert not window.session.cancel_signal.is_cancelled
    _finish_split_progress(window)

    assert window._progress_owner == "download"
    assert _progress_snapshot(window) == expected
    window.cancel_button.click()
    assert worker.cancel.is_cancelled, "der wieder sichtbare Knopf gilt dem Download"
    assert not window.session.agent_cancel.is_cancelled
    assert not window.session.cancel_signal.is_cancelled
    window._download_stopped()
    window._download_worker = None
    assert window._progress_owner == "agent"
    window._on_agent_busy(False)
    window.session.busyChanged.emit(False)


@pytest.mark.parametrize("writing", [False, True])
def test_split_restores_the_complete_export_progress(
    window: MainWindow,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    request: pytest.FixtureRequest,
    writing: bool,
) -> None:
    """Prüfung und Schreiben erhalten nach Split genau ihren eigenen Abbruchzustand zurück."""

    monkeypatch.setattr(window._leash, "start", lambda _worker: None)
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window._start_export(tmp_path / "halter.stl", "stl")
    worker = window._export_worker
    assert worker is not None
    request.addfinalizer(lambda: _release_unstarted_worker(window, "_export_worker", worker))
    if writing:
        window._export_writing(worker)
    expected = _progress_snapshot(window)
    try:
        _show_split_progress(window)
        assert window._progress_owner == "split"
        _finish_split_progress(window)

        assert window._progress_owner == "export"
        assert _progress_snapshot(window) == expected
        assert window.cancel_button.isVisibleTo(window) is not writing
    finally:
        window._exporting = False
        window._export_worker = None
        window._set_progress_state("export", active=False)


def test_split_uses_its_own_real_status_and_bar_timers(window: MainWindow) -> None:
    """Ein sichtbarer Agent schenkt dem neuen Split keine seiner Wartezeit."""
    from PySide6.QtTest import QTest

    window._on_agent_busy(True)
    window._on_agent_progress(2, "Netz prüfen")
    agent = _progress_snapshot(window)
    window.session._split = _RunningSplit()
    try:
        window.session.splitBusyChanged.emit(True)
        window.session.splitProgressChanged.emit(0.65, tr("Ausrichtung suchen"))

        QTest.qWait(main_window_module.DELAY_MS // 2)
        assert _progress_snapshot(window) == agent, (
            "vor 0,2 s bleibt der Agent vollständig sichtbar"
        )

        QTest.qWait(main_window_module.DELAY_MS)
        between = _progress_snapshot(window)
        assert between[0].startswith(tr("Ausrichtung suchen"))
        assert between[1:] == agent[1:], "vor zwei Sekunden bleiben Balken und Abbruch beim Agenten"

        QTest.qWait(main_window_module.BAR_AFTER_MS - 2 * main_window_module.DELAY_MS)
        before_bar = _progress_snapshot(window)
        assert before_bar[0].startswith(tr("Ausrichtung suchen"))
        assert before_bar[1:] == agent[1:], "auch kurz vor zwei Sekunden bleibt der Agent"

        QTest.qWait(main_window_module.DELAY_MS)
        assert window._progress_owner == "split"
        assert window.progress.accessibleName() == tr("Fortschritt: Automatisch teilen")
        assert window.cancel_button.accessibleDescription() == tr(
            "Bricht die automatische Teilung ab. Modell und Verlauf bleiben unverändert."
        )
    finally:
        _finish_split_progress(window)
        window._on_agent_busy(False)


def test_auto_split_uses_delayed_accessible_and_monotonic_progress(
    window: MainWindow,
) -> None:
    """Grobsuche bleibt unbestimmt; erst die Stützbewertung trägt Prozent."""

    class Running:
        def isRunning(self) -> bool:  # noqa: N802 — bildet die Qt-API nach
            return True

    window.session._split = Running()
    window.announce("Vorherige Meldung")
    try:
        window.session.splitBusyChanged.emit(True)
        window.session.splitProgressChanged.emit(0.25, tr("Die Trennebenen werden gesucht …"))

        assert window.status_message.text() == "Vorherige Meldung"
        assert not window.progress.isVisibleTo(window), "der Balken kam vor zwei Sekunden"
        assert not window.cancel_button.isVisibleTo(window)
        assert window.progress.minimum() == 0
        assert window.progress.maximum() == 100, "vor der Freigabe bleibt der Ruhewert stehen"
        assert not window.veil.isVisibleTo(window), "der Viewport darf nicht verdeckt werden"

        window._patience.timeout.emit()
        window._split_patience.timeout.emit()
        assert window.cursor().shape() == Qt.CursorShape.BusyCursor
        assert window.status_message.text() == tr("Die Trennebenen werden gesucht …")
        assert not window.progress.isVisibleTo(window)

        window._split_bar_delay.timeout.emit()
        assert window.progress.isVisibleTo(window)
        assert window.cancel_button.isVisibleTo(window)
        assert window.progress.accessibleName() == tr("Fortschritt: Automatisch teilen")
        assert tr("Die Trennebenen werden gesucht …") in window.progress.accessibleDescription()
        assert tr("Abbrechen ist verfügbar.") in window.progress.accessibleDescription()
        assert window.cancel_button.accessibleName() == tr("Abbrechen")
        assert window.cancel_button.accessibleDescription() == tr(
            "Bricht die automatische Teilung ab. Modell und Verlauf bleiben unverändert."
        )

        window._split_started = main_window_module.time.monotonic() - 11.0
        window.session.splitProgressChanged.emit(0.7, tr("Ausrichtung suchen"))
        assert window.progress.maximum() == 100
        assert window.progress.value() == 70
        assert "70 %" in window.status_message.text()
        assert tr("gleich fertig") in window.status_message.text()

        window.session.splitProgressChanged.emit(0.5, tr("Ausrichtung suchen"))
        assert window.progress.value() == 70, "bestimmter Fortschritt lief rückwärts"

        window.session.splitProgressChanged.emit(1.0, "")
        assert window.progress.value() == 100, "der leere Abschlusswert ging verloren"
        assert window.status_message.text().startswith(tr("Ausrichtung suchen"))
        assert "100 %" in window.status_message.text()
        assert tr("Ausrichtung suchen") in window.progress.accessibleDescription()
        assert "100 %" in window.progress.accessibleDescription()
        assert tr("Abbrechen ist verfügbar.") in window.progress.accessibleDescription()
    finally:
        window.session._split = None
        window.session.splitBusyChanged.emit(False)
    assert window.progress.accessibleName() == tr("Fortschritt")
    assert window.progress.accessibleDescription() == tr(
        "Zeigt den Fortschritt der laufenden Aufgabe."
    )
    assert window.cancel_button.accessibleDescription() == tr("Bricht die laufende Aufgabe ab.")


def test_undo_replaces_the_auto_split_result_with_the_current_state(
    window: MainWindow,
) -> None:
    """Nach Rückgängig darf die Statuszeile keine entfernte Teilung behaupten."""
    from app.core.split import SplitApplied

    title = tr("Teilen und verstiften")
    assert window.session.apply(
        title,
        [
            OperationDraft(
                op="create_box",
                params={"width": 20.0, "depth": 20.0, "height": 20.0},
            )
        ],
    )
    window.session.wait_for_idle()
    transaction = window.session.project.document.transactions[-1]
    object_id = next(iter(window.session.last_result.scene.objects))
    window._split_done(SplitApplied(object_ids=[object_id], transaction=transaction.id))
    assert window._announcement.startswith(tr("Geteilt"))

    window.action_undo()
    window.session.wait_for_idle()

    assert window._announcement == tr("{name} zurückgenommen.").format(name=title)


def test_the_auto_split_cancel_button_disables_itself_immediately(window: MainWindow) -> None:
    """Ein Klick verwirft genau einmal und lässt die Rückmeldung stehen."""
    from app.core.scene.cancel import CancelSignal

    class Running:
        def __init__(self) -> None:
            self.cancel = CancelSignal()

        def isRunning(self) -> bool:  # noqa: N802 — bildet die Qt-API nach
            return True

    worker = Running()
    window.session._split = worker
    try:
        window.session.splitBusyChanged.emit(True)
        window._split_bar_delay.timeout.emit()
        window.cancel_button.click()

        assert worker.cancel.is_cancelled
        assert not window.cancel_button.isEnabled()
        requested = tr("Teilung wird abgebrochen …")
        assert window.status_message.text() == requested
        assert window._announcement == requested

        window.session._split_cancelled(worker)
        finished = tr("Teilung abgebrochen. Modell und Verlauf sind unverändert.")
        assert window.status_message.text() == finished
        assert window._announcement == finished
    finally:
        window.session._split = None
        window.session._split_discarded = False
        window.session.splitBusyChanged.emit(False)


def test_escape_cancels_auto_split_before_touching_the_selection(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Escape verwirft die Suche sofort; Dokument und Auswahl bleiben stehen."""
    from app.core.scene.cancel import CancelSignal

    class Running:
        def __init__(self) -> None:
            self.cancel = CancelSignal()

        def isRunning(self) -> bool:  # noqa: N802 — bildet die Qt-API nach
            return True

    worker = Running()
    window.session._split = worker
    selection_touched: list[bool] = []
    monkeypatch.setattr(window, "_step_selection_out", lambda: selection_touched.append(True))
    try:
        window.session.splitBusyChanged.emit(True)
        window._split_bar_delay.timeout.emit()
        window._escape()

        message = tr("Teilung wird abgebrochen …")
        assert worker.cancel.is_cancelled
        assert not selection_touched, "Escape baute die Auswahl statt der Suche ab"
        assert not window.cancel_button.isEnabled(), "der Abbruchknopf blieb mehrfach klickbar"
        assert window.status_message.text() == message
        assert window._announcement == message, "die Rückmeldung überlebt den auslaufenden Arbeiter"
    finally:
        window.session._split = None
        window.session._split_discarded = False
        window.session.splitBusyChanged.emit(False)


def test_auto_split_runs_in_a_worker(session: Session) -> None:
    """Die Trennebenensuche lief mit Wartezeiger im Hauptthread — jetzt
    meldet sie sich über ``splitBusyChanged`` und liefert ihr Ergebnis an
    einen Rückruf, während das Fenster bedienbar bleibt."""
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    states: list[bool] = []
    session.splitBusyChanged.connect(states.append)
    results: list[object] = []

    session.split_async("obj_1", results.append)
    session.wait_for_idle()

    assert results, "der Rückruf bekommt das Ergebnis"
    applied = results[0]
    assert applied.transaction is None, "ein 20-mm-Würfel passt aufs Bett"
    assert states and states[0] is True and states[-1] is False


def test_auto_split_uses_the_objects_material_for_search_and_fits(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Projektmaterial und Körpermaterial dürfen beim Teilen nicht zusammenfallen."""
    from app.ui import session as session_module

    session.project.document.printer = "centauri-carbon-2"
    session.project.document.material = "petg"
    session.history.apply(
        "Anlegen",
        [
            OperationDraft(
                op="create_box",
                params={"width": 400.0, "depth": 60.0, "height": 40.0},
            )
        ],
    )
    session.evaluate_async()
    session.wait_for_idle()
    assert session.last_result is not None
    entry = session.last_result.scene.objects["obj_1"]
    entry.material = "pla"

    chosen: list[Profile] = []
    searched: list[Profile] = []
    real_for_object = session_module.profiles.for_object
    real_apply_split = session_module.apply_split

    def choose(base: Profile, body: SceneObject | None) -> Profile:
        profile = real_for_object(base, body)
        chosen.append(profile)
        return profile

    def apply(*args: Any, **values: Any) -> Any:
        searched.append(args[3])
        return real_apply_split(*args, **values)

    monkeypatch.setattr(session_module.profiles, "for_object", choose)
    monkeypatch.setattr(session_module, "apply_split", apply)
    monkeypatch.setattr(session, "evaluate_async", lambda: None)

    applied = session.auto_split("obj_1")

    assert len(chosen) == 1, "das Objektprofil wird genau einmal bestimmt"
    assert searched == chosen and searched[0].material.id == "pla"
    # Die Passungen nennen kein Material: Sie folgen dem der Körper, wenn sie
    # geprüft werden (``scene.fits._wanted``), statt es beim Teilen
    # festzuschreiben (Durchsicht 0.5.0).
    assert {fit.tolerance for fit in applied.fits} == {"auto:"}


def test_drawn_split_uses_the_spool_material_for_its_fits(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch der gezeichnete Schnitt prüft seine Passungen im Material von Spule null (§12).

    Bis zur Durchsicht 0.5.0 bestimmte die Sitzung dafür das Spulenprofil und
    schrieb es in die Passung (``auto:pla``). Seitdem nennt die Passung kein
    Material und folgt den Körpern, wenn sie geprüft wird — gemessen hier an
    einem Projekt in TPU, dessen Körper auf einer PLA-Spule liegt: Die Stifte
    rechnen ihr Spiel in PLA, und die Passung prüft in PLA, nicht in TPU.
    """
    from app.core.geom.section import SectionPlane

    session.project.document.printer = "centauri-carbon-2"
    session.project.document.material = "tpu-95a"
    session.history.apply(
        "Anlegen",
        [
            OperationDraft(
                op="create_box",
                params={"width": 400.0, "depth": 60.0, "height": 40.0},
            )
        ],
    )
    session.history.apply(
        "Spule",
        [
            OperationDraft(
                op="assign_slot",
                inputs=("obj_1",),
                params={"slot": 0, "name": "PLA", "colour": "#ffffff", "material_type": "PLA"},
            )
        ],
    )
    session.evaluate_async()
    session.wait_for_idle()
    assert session.last_result is not None

    applied = session.split_along("obj_1", SectionPlane((1.0, 0.0, 0.0), 0.0), pins=2)
    session.evaluate_async()
    session.wait_for_idle()

    assert applied.fits and {fit.tolerance for fit in applied.fits} == {"auto:"}
    result = session.last_result
    assert result is not None and result.complete, result
    codes = [finding.code for finding in result.scene.report.findings]
    assert "fit.violated" not in codes, codes


def test_async_split_keeps_one_object_profile_from_search_through_apply(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine Profiländerung während der Suche darf deren Plan nicht umdeuten.

    Seit der Durchsicht 0.5.0 bekommt das Anwenden gar kein Profil mehr: Die
    Nahtpassungen nennen kein Material (``auto:``), und was der Plan
    festlegt, entschied die Suche. Geprüft bleibt, dass genau ihr Plan ankommt.
    """
    from app.core.split import SplitApplied
    from app.ui import session as session_module

    session.project.document.printer = "centauri-carbon-2"
    session.project.document.material = "petg"
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()
    assert session.last_result is not None
    entry = session.last_result.scene.objects["obj_1"]
    entry.material_slots = [MaterialSlot(index=0, name="PLA", material_type="PLA")]

    started = threading.Event()
    release = threading.Event()
    chosen: list[Profile] = []
    searched: list[Profile] = []
    applied_with: list[object] = []
    real_for_object = session_module.profiles.for_object
    plan = object()

    def choose(base: Profile, body: SceneObject | None) -> Profile:
        profile = real_for_object(base, body)
        chosen.append(profile)
        return profile

    def search(_mesh: object, _object_id: str, profile: Profile, **_values: object) -> object:
        searched.append(profile)
        started.set()
        assert release.wait(2.0), "die blockierte Suche wurde nicht freigegeben"
        return plan

    def apply(_document: object, received: object, object_id: str) -> SplitApplied:
        applied_with.append(received)
        return SplitApplied(object_ids=[object_id])

    monkeypatch.setattr(session_module.profiles, "for_object", choose)
    monkeypatch.setattr(session_module, "plan_split", search)
    monkeypatch.setattr(session_module, "apply_planned", apply)

    results: list[object] = []
    session.split_async("obj_1", results.append)
    assert started.wait(2.0), "der Split-Arbeiter ist nicht angelaufen"
    session.project.document.material = "tpu-95a"
    release.set()
    session.wait_for_idle()

    assert len(chosen) == 1, "das Objektprofil wird genau einmal bestimmt"
    assert searched == chosen and searched[0].material.id == "pla"
    assert applied_with == [plan], "angewandt wird der Plan der Suche, kein neuer"
    assert len(results) == 1


def test_a_failed_import_plan_leaves_no_orphan_source(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scheitert der Einleseplan, bleibt keine Waisen-Quelle zurück (F-10).

    Eingebettet wurde vor dem Planen — wies der Plan die Datei ab (zu groß,
    Zip-Bombe), stand die kaputte Quelle trotzdem im Dokument und wanderte
    mit dem nächsten Speichern in die Projektdatei. Die Kommandozeile war nie
    betroffen: sie speichert nur nach vollständiger Auswertung.
    """
    from app.ui import session as session_module

    def refusing(*_args: object, **_kwargs: object) -> object:
        raise errors.ValidationError("file", "diese Datei nimmt der Plan nicht")

    monkeypatch.setattr(session_module, "import_plan", refusing)
    with pytest.raises(errors.AppError):
        session.import_payload("kaputt.3mf", b"x")
    assert not session.project.document.sources, "die Quelle wurde wieder ausgetragen"
    assert not session.project.sources, "auch ihr Inhalt"


def test_a_rejected_import_can_be_surfaced_without_an_orphan_source(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein synchroner Oberflächenweg bekommt die Abweisung selbst zurück.

    So kann er zuerst seine Warteanzeige beenden; Quelle und Inhalt dürfen
    trotzdem nicht im Projekt zurückbleiben.
    """

    def refusing(*_args: object, **_kwargs: object) -> object:
        raise errors.UserError(detail="der Schritt wurde abgewiesen")

    monkeypatch.setattr(session.history, "apply", refusing)

    with pytest.raises(errors.UserError):
        session.import_model(MESHES / "cube_clean.stl", raise_on_error=True)

    assert not session.project.document.sources, "die abgewiesene Quelle blieb im Dokument"
    assert not session.project.sources, "der Inhalt der abgewiesenen Quelle blieb im Projekt"
    assert not session.project.document.ops, "eine abgewiesene Operation darf nicht erscheinen"


def test_a_second_split_start_is_refused_while_one_runs(session: Session) -> None:
    """Zwei Suchen zugleich gab es nie absichtlich — die zweite wird abgewiesen.

    Vorher überschrieb der zweite Start den ersten Arbeiter: dessen Plan kam
    trotzdem an, ``split_running`` log nach dem ersten Ende, und ein Thread
    überlebte sein Fenster.
    """
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    class Running:
        """Nur was die Wache fragt: läuft er noch — wie ``QThread.isRunning``."""

        def isRunning(self) -> bool:  # noqa: N802 — der Name gehört Qt
            return True

    stub = Running()
    session._split = stub
    refused: list[object] = []
    session.failed.connect(refused.append)
    called: list[object] = []
    try:
        session.split_async("obj_1", called.append)
        assert refused, "die zweite Suche wird als Satz abgewiesen"
        assert refused[0].suggestions
        assert session._split is stub, "der laufende Arbeiter bleibt der Arbeiter"
        assert not called
    finally:
        session._split = None


def test_the_split_end_reports_when_the_thread_is_truly_gone(session: Session) -> None:
    """Das endgültige Ende der Trennsuche meldet im finished-Pfad (§2.8).

    ``_split_cancelled`` bestätigt den Abbruch früher, aber dort läuft der
    Thread noch: ``_on_split_busy`` fragt ``_anything_running()``, liest
    ``split_running`` als True und ließ Balken und Abbrechen für immer
    stehen — nach dem Auslaufen kam nie wieder ein False (Update-Review,
    Fund 30). Doppelt gemeldet ist folgenlos, die Anzeige stellt nur einen
    Zustand her.
    """

    class Done:
        """Nur was Leine und Wache fragen: läuft er noch — nein."""

        def isRunning(self) -> bool:  # noqa: N802 — der Name gehört Qt
            return False

        def wait(self, _timeout_ms: int) -> bool:
            """Die fertige Thread-Attrappe hat auch ihren Abbau abgeschlossen."""
            return True

    worker = Done()
    session._split = worker
    busy: list[bool] = []
    session.splitBusyChanged.connect(busy.append)

    session._on_split_done(worker)

    assert busy == [False], "genau eine Nachmeldung, nach dem Auslaufen"
    assert session._split is None, "und das Feld ist geräumt"


def test_cancelling_an_already_finished_split_is_confirmed_once(session: Session) -> None:
    """Die Lücke zwischen fachlichem Ende und ``finished`` bleibt nicht hängen."""
    from app.core.scene.cancel import CancelSignal

    class Done:
        def __init__(self) -> None:
            self.cancel = CancelSignal()

        def isRunning(self) -> bool:  # noqa: N802 — bildet die Qt-API nach
            return False

        def wait(self, _timeout_ms: int) -> bool:
            """Die fertige Thread-Attrappe hat auch ihren Abbau abgeschlossen."""
            return True

    worker = Done()
    session._split = worker
    requested: list[bool] = []
    confirmed: list[bool] = []
    session.splitCancelRequested.connect(lambda: requested.append(True))
    session.splitCancelled.connect(lambda: confirmed.append(True))

    session.cancel_split()
    assert requested == [True]
    assert not confirmed, "vor dem endgültigen Thread-Signal ist noch nichts bestätigt"

    session._split_cancelled(worker)
    assert confirmed == [True], "das fachliche Ende bestätigt den Abbruch"
    session._on_split_done(worker)

    assert confirmed == [True], "das endgültige Ende bestätigt genau einmal"
    assert session._split is None


def test_a_stale_split_worker_cannot_deliver(session: Session) -> None:
    """Was ein überlebender Arbeiter noch meldet, wird nicht mehr angewandt.

    Jeder Empfänger prüft den Absender: Plan, Fehler und das Auslaufen zählen
    nur, wenn sie vom aktuellen Arbeiter kommen.
    """
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    stale = object()
    busy: list[bool] = []
    session.splitBusyChanged.connect(busy.append)
    called: list[object] = []
    reported: list[object] = []
    session.failed.connect(reported.append)

    session._split_planned(stale, object(), "obj_1", called.append)
    assert not called and not busy, "ein fremder Plan wird nicht angewandt"

    session._split_failed(stale, errors.InternalError(detail="stale"))
    assert not reported, "ein fremder Fehler wird nicht gemeldet"

    keeper = object()
    session._split = keeper
    try:
        session._on_split_done(stale)
        assert session._split is keeper, "das Auslaufen eines Fremden räumt das Feld nicht"
    finally:
        session._split = None


# --- Live-Vorschau im Operationsdialog (§18.7) -----------------------------------


def test_a_preview_delivers_a_difference(session: Session) -> None:
    """Der Dialog zeigt, was er täte: dieselbe Differenzansicht wie beim
    Agentenvorschlag, gerechnet auf einer Kopie, ohne den Stapel anzufassen."""
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()
    stack_before = list(session.project.document.ops)

    collected: list[object] = []
    session.preview_async(
        collected.append,
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 4.0, "x": 0.0, "y": 0.0, "z": 0.0, "axis": "z"},
            )
        ],
    )
    session.wait_for_idle()

    assert collected, "die Vorschau liefert"
    difference = collected[0]
    assert difference is not None and difference.changed, "eine Bohrung ändert Volumen"
    assert list(session.project.document.ops) == stack_before, "der Stapel bleibt unberührt"


def test_a_preview_computes_the_stand_it_was_asked_about(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Vorschau rechnet auf dem Stand beim Fragen, nicht auf dem beim Rechnen.

    Bis zum 22.09.2026 kopierte der **Arbeiter** das lebende Dokument — erst
    wenn er dran war. Kam dazwischen eine Änderung im Hauptfaden an (ein
    Übernehmen, ein Import), rechnete die Vorschau einen Stand, den der
    Dialog nie gezeigt hatte, und ein Wörterbuch, das sich beim Kopieren
    änderte, riss den Arbeiter ab. Nachgestellt: Der Arbeiter wartet vor dem
    Rechnen, im Hauptfaden kommt ein zweiter Körper hinzu — die Vorschau
    kennt ihn nicht, denn sie wurde vorher gefragt.
    """
    import threading

    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()
    gate = threading.Event()
    original = Session._preview_outcome

    def held(self: Session, *args: object, **kwargs: object) -> object:
        assert gate.wait(30.0), "der Test hat die Vorschau nie freigegeben"
        return original(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Session, "_preview_outcome", held)
    collected: list[object] = []
    session.preview_async(
        collected.append,
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 4.0, "x": 0.0, "y": 0.0, "z": 0.0, "axis": "z"},
            )
        ],
    )
    session.history.apply(
        "Dazwischen", [OperationDraft(op="create_box", params={"width": 5.0, "x": 80.0})]
    )
    gate.set()
    assert session.wait_for_idle(30_000)

    assert collected and collected[-1] is not None
    difference = collected[-1]
    assert difference.changed, "die Bohrung ist in der Vorschau"
    assert not difference.created, "der Körper von danach gehört nicht in die Vorschau von davor"


def test_a_cancelled_preview_stays_silent(session: Session) -> None:
    """Der Dialog ist zu, bevor die Rechnung fertig ist — das Ergebnis wird
    verworfen statt gezeigt (§18.7)."""
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    collected: list[object] = []
    session.preview_async(
        collected.append,
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 4.0, "x": 0.0, "y": 0.0, "z": 0.0, "axis": "z"},
            )
        ],
    )
    session.cancel_preview()
    session.wait_for_idle()

    assert not collected, "eine verworfene Vorschau meldet sich nicht mehr"


def test_a_cancelled_preview_actually_stops_computing(session: Session) -> None:
    """Verwerfen ist nicht abbrechen.

    ``cancel_preview`` erhoehte nur die Generation: Das Ergebnis wurde
    weggeworfen, angehalten wurde nichts. Wer einen Dialog ueber einem grossen
    Koerper schloss, liess eine Rechnung hinter sich, die niemand mehr sehen
    wollte und die trotzdem bis zum Ende lief — und beim schnellen Tippen
    stapelten sich diese Rechnungen.

    Geprueft wird deshalb das Token, nicht die Stille: Jeder Arbeiter fuehrt
    ein **eigenes**, denn ein geteiltes mit ``reset()`` vor dem Start waere ein
    Wettlauf — der alte Lauf saehe den gesetzten Zustand womoeglich nie.
    """
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    def bohrung() -> list[OperationDraft]:
        return [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 4.0, "x": 0.0, "y": 0.0, "z": 0.0, "axis": "z"},
            )
        ]

    session.preview_async(lambda _difference: None, bohrung())
    erster = session._previews[-1]
    session.preview_async(lambda _difference: None, bohrung())
    zweiter = session._previews[-1]

    assert erster is not zweiter, "zwei Anfragen, zwei Arbeiter"
    assert erster.cancel is not zweiter.cancel, (
        "ein geteiltes Token waere ein Wettlauf zwischen altem und neuem Lauf"
    )
    assert erster.cancel.is_cancelled, "die neuere Anfrage laesst die aeltere weiterrechnen"
    assert not zweiter.cancel.is_cancelled, "die neueste darf rechnen"

    session.cancel_preview()
    assert zweiter.cancel.is_cancelled, "der geschlossene Dialog haelt seine Rechnung an"

    session.wait_for_idle()


def test_a_broken_preview_shows_nothing_instead_of_failing(session: Session) -> None:
    """Beim Tippen entstehen ungültige Zwischenstände — die Vorschau zeigt
    dann nichts; der echte Fehler kommt beim Anwenden als Vorschlag (§2.7)."""
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    collected: list[object] = []
    session.preview_async(
        collected.append,
        [OperationDraft(op="drill_hole", inputs=("obj_1",), params={"diameter": -1.0})],
    )
    session.wait_for_idle()

    assert collected == [None], "kein Fehlerdialog, nur keine Vorschau"


def test_the_wired_dialog_previews_into_the_viewport(window: MainWindow) -> None:
    """Die Verdrahtung Ende zu Ende: Dialog auf, erste Vorschau läuft von
    selbst, die Differenz steht im Viewport — und mit dem Schließen geht sie."""
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()

    spec = REGISTRY.get("drill_hole")
    dialog = OperationDialog(spec, window._object_names(), window)
    window._wire_preview(
        dialog,
        lambda entered: [OperationDraft(op=spec.name, inputs=("obj_1",), params=entered)],
    )
    window.session.wait_for_idle()

    assert window.viewport.difference is not None, "die Vorgaben sind schon eine Aussage"

    window._clear_preview()
    assert window.viewport.difference is None


def test_the_window_reads_metrics_the_worker_has_already_computed(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Volumen, Oberfläche, Wasserdichtheit und Teilezahl rechnet der Arbeiter.

    Sie sind gemerkte Eigenschaften der Körper, und der erste Zugriff rechnet.
    Der kam aus dem Hauptthread — ``describe_selection`` beim Wiederherstellen
    der Auswahl, ``_measure_up`` über dem Bericht —: 1,5 s an einer Million
    Dreiecken, 15 s an einem STEP-Gewinde (Review Leistung B1/B2, 21.09.2026).
    Gemessen wird, **in welchem Faden** die vier zum ersten Mal gerechnet
    werden: nie im Hauptthread.
    """
    from app.core.geom.mesh import MeshData

    first_thread: dict[str, str] = {}
    for name in ("volume", "area", "is_watertight", "component_count"):
        original = getattr(MeshData, name)

        def spy(self: Any, _name: str = name, _original: Any = original) -> Any:
            first_thread.setdefault(_name, threading.current_thread().name)
            return _original.fget(self)

        monkeypatch.setattr(MeshData, name, property(spy))

    session.import_model(MESHES / "cube_clean.stl")
    assert session.wait_for_idle(30_000)
    entry = next(iter(session.last_result.scene.objects.values()))
    # Der Hauptthread liest — und trifft dabei auf gemerkte Werte.
    assert entry.mesh.volume > 0.0 and entry.mesh.is_watertight
    assert set(first_thread) == {"volume", "area", "is_watertight", "component_count"}
    assert all(thread != "MainThread" for thread in first_thread.values()), first_thread


def test_rapid_previews_never_orphan_a_worker(session: Session) -> None:
    """Wer schnell tippt, startet Vorschau auf Vorschau. Jeder laufende
    Arbeiter bleibt referenziert, bis er ausgelaufen ist — ein QThread ohne
    Referenz wird sonst vom Speicherbereiniger mitsamt laufendem C++-Objekt
    zerstört: der Absturz ohne Zeile, der die Suite sporadisch riss."""
    import gc

    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    collected: list[object] = []
    for diameter in (2.0, 3.0, 4.0, 5.0, 6.0):
        session.preview_async(
            collected.append,
            [
                OperationDraft(
                    op="drill_hole",
                    inputs=("obj_1",),
                    params={"diameter": diameter, "x": 0.0, "y": 0.0, "z": 0.0, "axis": "z"},
                )
            ],
        )
    gc.collect()
    session.wait_for_idle()
    gc.collect()

    assert len(collected) == 1, "nur die jüngste Vorschau wird geliefert"
    assert not session._previews, "kein Arbeiter bleibt zurück"


def test_a_preview_that_cannot_be_says_why(session: Session) -> None:
    """Ein leeres Bild ohne Satz sah aus wie „nichts ändert sich".

    Gemessen am 13.09.2026 über alle Operationsdialoge: Elf öffneten mit
    leerem Bild und dem Band „Vorschau — noch nicht übernommen", und der Grund
    — „Diese Ebene teilt das Objekt nicht", „Der Körper ist auf dieser Höhe
    massiv" — kam erst beim Übernehmen. Der Satz gehört an die Stelle, an der
    man die Zahl noch ändern kann (§2.7).

    Beide Wege: Die Kette hält an einem Befund an (Teilen auf der
    Unterseite), oder die Operation wirft (Bohrung mit negativem Durchmesser).
    """
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    reasons: list[str] = []
    shown: list[object] = []
    session.preview_async(
        shown.append,
        [OperationDraft(op="split_pinned", inputs=("obj_1",), params={"position": 0.0})],
        explained=reasons.append,
    )
    session.wait_for_idle()
    assert shown == [None], "eine angehaltene Kette ist keine Vorschau"
    assert reasons == [tr("Diese Ebene teilt das Objekt nicht.")], "der Befund des Halts"

    reasons.clear()
    session.preview_async(
        shown.append,
        [OperationDraft(op="drill_hole", inputs=("obj_1",), params={"diameter": -1.0})],
        explained=reasons.append,
    )
    session.wait_for_idle()
    assert len(reasons) == 1 and reasons[0], "auch ein geworfener Fehler nennt seinen Satz"

    reasons.clear()
    session.preview_async(
        shown.append,
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 4.0, "x": 0.0, "y": 0.0, "z": 0.0, "axis": "z"},
            )
        ],
        explained=reasons.append,
    )
    session.wait_for_idle()
    assert not reasons, "eine Vorschau, die kommt, braucht keinen Grund"

    # Und eine leere Vorschau mit einer Warnung sagt die Warnung: *Textur in
    # Filamente* an einem Körper ohne Farbinformation läuft durch, ändert
    # nichts und meldet als Befund, warum.
    reasons.clear()
    session.preview_async(
        shown.append,
        [OperationDraft(op="slots_from_texture", inputs=("obj_1",), params={})],
        explained=reasons.append,
    )
    session.wait_for_idle()
    assert reasons == [tr("Dieses Objekt trägt keine Farbinformation.")]


def test_a_preview_that_stops_at_a_question_says_so(session: Session) -> None:
    """*Merkmal entfernen* an einer gesenkten Bohrung fragt, ob die Senkung
    mitgeht. Die stille Vorschau fragt nicht — und sagte bis zum 14.09.2026
    „am Volumen ändert sich nichts". Nichts hatte sich geändert; es war
    noch nichts entschieden."""
    session.import_model(MESHES / "plate_countersunk.stl")
    session.wait_for_idle()
    result = session.evaluate_now()
    entry = result.scene.objects["obj_1"]
    hole = next(identifier for identifier, f in entry.features.items() if f.kind == "hole")

    reasons: list[str] = []
    shown: list[object] = []
    asked: list[object] = []
    session.preview_async(
        shown.append,
        [OperationDraft(op="remove_feature", inputs=("obj_1",), params={"at_feature": hole})],
        explained=reasons.append,
        asked=asked.append,
    )
    session.wait_for_idle()
    assert shown == [None]
    assert reasons == [tr("Eine Rückfrage steht an — sie kommt beim Übernehmen.")]
    # Und es eigens gesagt, damit das Fenster den Satz nicht als Absage liest
    # und *Übernehmen* sperrt (RM-389).
    assert asked == [None]


def test_the_banner_names_the_reason_and_the_empty_difference(window: MainWindow) -> None:
    """Drei Zustände, drei Sätze — und nicht derselbe über allen.

    Vor dem 13.09.2026 stand „Vorschau — noch nicht übernommen" über einer
    Bohrung, über einem Verschieben um null und über einem Teilen, das nichts
    teilt. Nur der erste Satz war wahr.
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    banner = window.viewport.banner

    window._preview_explained("Diese Ebene teilt das Objekt nicht.")
    assert "Diese Ebene teilt das Objekt nicht." in banner.note.text()
    assert banner.note.text().startswith(tr("Keine Vorschau: {reason}").format(reason=""))
    assert window.viewport.difference is None
    assert not window.viewport._comparing, "ohne Differenz gehört die Leertaste nicht dem Band"
    # Das ``None`` des Arbeiters kommt nach dem Grund und lässt ihn stehen.
    window._show_preview(None)
    assert "Diese Ebene teilt das Objekt nicht." in banner.note.text()

    window._show_preview(dataclasses.make_dataclass("Leer", [("changed", bool)])(False))
    assert banner.note.text() == tr("Vorschau — am Volumen ändert sich nichts")
    assert banner.hint.text() == "", "ohne Unterschied gibt es kein Vorher zu halten"

    # RM-169: Wo die Zahl „nichts" sagt und das Bild etwas zeigt, sagt das
    # Band, was — und das Vorher lohnt sich wieder.
    quiet = dataclasses.make_dataclass(
        "Netz", [("changed", bool), ("reshaped", bool), ("recoloured", bool)]
    )
    window._show_preview(quiet(False, True, False))
    assert banner.note.text() == tr("Vorschau — das Netz ändert sich, das Volumen nicht")
    assert banner.hint.text() == tr("Leertaste halten: vorher")
    window._show_preview(quiet(False, False, True))
    assert banner.note.text() == tr("Vorschau — nur die Farbe ändert sich")

    window._show_preview(dataclasses.make_dataclass("Voll", [("changed", bool)])(True))
    assert banner.note.text() == tr("Vorschau — noch nicht übernommen")

    window._clear_preview()
    assert banner.isHidden()


def test_a_slow_preview_says_it_is_computing(window: MainWindow) -> None:
    """Nach 0,2 s ohne Ergebnis sagt das Band, dass gerechnet wird (§2.8).

    Ein Aushöhlen über einem großen Netz braucht Sekunden; solange stand das
    alte Bild unter dem alten Band, und ein Haken, dessen Wirkung erst nach
    drei Sekunden kommt, sah aus wie einer, der nicht reagiert.
    """
    from PySide6.QtTest import QTest

    banner = window.viewport.banner
    window._preview_busy.start()
    QTest.qWait(300)
    assert banner.note.text() == tr("Vorschau wird gerechnet …")

    # Das Ergebnis löst die Ansage ab — und ein Ergebnis vor Ablauf der
    # Frist verhindert sie ganz.
    window._show_preview(dataclasses.make_dataclass("Voll", [("changed", bool)])(True))
    assert banner.note.text() == tr("Vorschau — noch nicht übernommen")
    window._preview_busy.start()
    window._show_preview(dataclasses.make_dataclass("Voll", [("changed", bool)])(True))
    QTest.qWait(300)
    assert banner.note.text() == tr("Vorschau — noch nicht übernommen")
    window._clear_preview()


def test_splitting_starts_in_the_middle_of_the_body(window: MainWindow) -> None:
    """*Teilen* öffnete mit ``position=0`` — auf der Unterseite eines Körpers,
    der auf dem Bett steht. Die Ebene teilte nichts, und der Dialog sagte
    nichts. Jetzt beginnt sie in der Mitte; die Zahl bleibt änderbar."""
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window.object_tree.select_object("obj_1")

    window.run_operation(REGISTRY.get("split_pinned"))
    dialog = window._op_dialog
    assert dialog is not None
    try:
        assert dialog.values()["position"] == pytest.approx(10.0), "Mitte von 0 bis 20"
    finally:
        dialog.reject()


def test_aligning_is_grey_until_a_second_body_carries_a_feature(window: MainWindow) -> None:
    """Am einzigen Körper stand *An Merkmal ausrichten* bedienbar da — mit
    leerem Ziel und einem Band, das den Formatfehler des Kerns zeigte
    (Bedienweg-Durchsicht 14.09.2026). Ein Ziel gibt es erst, wenn ein zweiter
    Körper ein Merkmal trägt; bis dahin sagt der Knopf das.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.last_result
    assert result is not None
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(fid for fid, feature in entry.features.items() if feature.kind == "hole")
    spec = REGISTRY.get("align_to_feature")
    wanted = str(tr("Dafür braucht es ein Merkmal an einem zweiten Körper."))

    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)
    kinds = window.object_tree.kinds_of_selection()
    assert window._reason_locked(spec, kinds, 1, 1) == wanted

    assert window.session.apply(
        str(REGISTRY.get("duplicate_object").title),
        [OperationDraft(op="duplicate_object", inputs=(object_id,))],
    )
    window.session.wait_for_idle()
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)
    kinds = window.object_tree.kinds_of_selection()
    assert window._reason_locked(spec, kinds, 2, 1) is None, "mit einem zweiten Körper geht es"


def test_a_lid_is_offered_only_at_an_opening_that_faces_up(window: MainWindow) -> None:
    """*Deckel erzeugen* und *Drehdeckel erzeugen* standen an jeder Fläche einer
    massiven Platte bedienbar da und konnten nur scheitern — „auf dieser
    Höhe massiv" an der Oberseite, „zeigt nicht nach oben" an der Seite (seit
    RM-087 auch dort „massiv": Ein Deckel darf seitlich liegen, dahinter ist
    aber nichts offen) —,
    während *Offene Fläche schließen* daneben seit RM-168 grau war
    (Bedienweg-Durchsicht 14.09.2026). Die Karte kennt die Fläche, wenn sie
    den Knopf zeigt; sie fragt ``lid.reason_against`` und trägt denselben
    Satz. An der Öffnung einer ausgehöhlten Dose bleibt der Knopf frei.
    """
    from app.core.scene.placement import faces_up

    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.last_result
    assert result is not None
    plate, entry = next(iter(result.scene.objects.items()))
    top = next(
        fid
        for fid, feature in entry.features.items()
        if feature.kind == "face" and faces_up(feature)
    )
    side = next(
        fid
        for fid, feature in entry.features.items()
        if feature.kind == "face" and not faces_up(feature)
    )

    def reason_at(object_id: str, face: str, objects: int, name: str) -> str | None:
        window.object_tree.select_object(object_id)
        window.object_tree.select_feature(object_id, face)
        return window._reason_locked(
            REGISTRY.get(name), window.object_tree.kinds_of_selection(), objects, 1
        )

    for name in ("create_lid", "screw_lid"):
        assert "massiv" in (reason_at(plate, top, 1, name) or ""), name
        # Seit RM-087 darf ein Deckel auch an einer Seite liegen — an einer
        # massiven Platte ist die Seite darum aus demselben Grund grau wie
        # die Oberseite: Dahinter ist nichts offen.
        assert "massiv" in (reason_at(plate, side, 1, name) or ""), name

    assert window.session.apply(
        "Quader",
        [OperationDraft(op="create_box", params={"width": 60.0, "depth": 40.0, "height": 30.0})],
    )
    window.session.wait_for_idle()
    box = window.session.project.document.ops[-1].outputs[0]
    assert window.session.apply(
        "Aushöhlen",
        [OperationDraft(op="hollow_object", inputs=(box,), params={"wall": 3.0, "open_top": True})],
    )
    window.session.wait_for_idle()
    hollow = window.session.project.document.ops[-1].outputs[0]
    result = window.session.last_result
    assert result is not None
    # Zwei Flächen zeigen nach oben: der Rand und der Boden des Hohlraums.
    # Am Rand liegt die Öffnung, unter dem Boden ist die Dose massiv — und
    # genau das sagt die Karte an beiden.
    upward = sorted(
        (
            (float(feature.params.get("centre", (0.0, 0.0, 0.0))[2]), fid)
            for fid, feature in result.scene.objects[hollow].features.items()
            if feature.kind == "face" and faces_up(feature)
        ),
        reverse=True,
    )
    assert len(upward) == 2, upward
    rim, floor = upward[0][1], upward[1][1]
    for name in ("create_lid", "screw_lid"):
        assert reason_at(hollow, rim, 2, name) is None, f"{name} an der Öffnung bleibt frei"
        # Seit RM-087 nennt der Boden die Ursache statt des Symptoms: Er liegt
        # innen — vorher hieß es „massiv", weil der Schnitt darunter Wand traf.
        assert "Inneren" in (reason_at(hollow, floor, 2, name) or ""), f"{name} am Boden"


def test_decimating_and_remeshing_start_from_the_body(window: MainWindow) -> None:
    """Die Vorgabe trifft den Körper, nicht den Ursprung — auch bei Dreiecken.

    *Dreiecke verringern* stand auf 50 000: An einer Platte mit wenigen
    hundert Dreiecken sagte das Band „am Volumen ändert sich nichts", und der
    Knopf, den der Prüfbericht bei zu feinen Netzen anbietet, tat an einem
    normalen Modell nichts. *Dreiecke angleichen* stand auf 1,0 mm, gleich
    wie groß das Teil (Bedienweg-Durchsicht 14.09.2026). Gemessen an
    ``post_with_fillet.stl``: 2704 Dreiecke, 60 mm lang.
    """
    from app.core.geom.mesh_ops import DECIMATE_FLOOR
    from app.ui.main_window import EDGE_SHARE

    window.open_path(MESHES / "post_with_fillet.stl")
    window.session.wait_for_idle()
    window.object_tree.select_object("obj_1")
    result = window.session.last_result
    assert result is not None
    body = result.scene.objects["obj_1"].mesh
    count = body.triangle_count
    assert count > 2 * DECIMATE_FLOOR, "sonst deckt die Untergrenze die Hälfte zu"
    longest = max(
        float(high - low)
        for low, high in zip(body.bounds.minimum, body.bounds.maximum, strict=True)
    )

    window.run_operation(REGISTRY.get("decimate_mesh"))
    dialog = window._op_dialog
    assert dialog is not None
    try:
        assert dialog.values()["triangles"] == count // 2, "die Hälfte der gemessenen"
    finally:
        dialog.reject()

    window.run_operation(REGISTRY.get("remesh_uniform"))
    dialog = window._op_dialog
    assert dialog is not None
    try:
        assert dialog.values()["edge"] == pytest.approx(longest / EDGE_SHARE)
    finally:
        dialog.reject()


def test_a_model_of_several_parts_offers_to_split_it(window: MainWindow) -> None:
    """„Das Modell besteht aus mehreren Teilen." bot nichts an, während die
    Nachbarzeile „sehr kleine Einzelteile" ihren Knopf trug — und *In
    Einzelteile zerlegen* stand in der Karte unter 24 Handlungen
    (Bedienweg-Durchsicht 14.09.2026). Ein Angebot, keine Ausführung: Der
    Klick ist ein Schritt im Verlauf, und Strg+Z nimmt ihn zurück.
    """
    from app.ui.panels import actions_for, as_error

    window.open_path(MESHES / "two_components.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    window._on_scene(result)
    several = next(
        (f for f in result.scene.report.findings if f.code == "ingest.multiple_components"), None
    )
    assert several is not None, "dieses Modell soll den Befund auslösen"

    handlers = window.error_handlers()
    offered = [action.id for action in actions_for(several) if action.id in handlers]
    assert offered == ["split_bodies"], f"der Befund bietet {offered} an"
    before = len(result.scene.objects)
    handlers["split_bodies"](as_error(several))
    window.session.wait_for_idle()
    after = window.session.last_result
    assert after is not None
    assert len(after.scene.objects) > before, "der Knopf zerlegt wirklich"


def test_an_stl_import_greets_without_a_finding_about_reading_it(window: MainWindow) -> None:
    """Der Prüfbericht eines sauberen Modells begann mit „Doppelte Punkte wurden
    verschweißt." — bei jedem STL-Import, ohne Handlung, das Erste, was ein
    Neuling liest (Bedienweg-Durchsicht 14.09.2026). Das Verschweißen einer
    STL ist Lesen; gemeldet wird es nicht mehr, getan weiterhin.
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.last_result
    assert result is not None
    codes = [finding.code for finding in result.scene.report.findings]
    assert "ingest.welded" not in codes, codes
    body = next(iter(result.scene.objects.values()))
    assert body.mesh.vertex_count == 8, "verschweißt wird weiter"


def test_the_export_offers_its_folder(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nach dem Export stand „Exportiert: dose.3mf" in der Statuszeile und sonst
    nichts; alle vier Wege enden hier, und kein Knopf führte zum Ordner
    (Bedienweg-Durchsicht 14.09.2026). *Ordner zeigen* steht neben der
    Meldung, solange sie steht, und öffnet den Ordner über Qt — dieselbe
    Stelle auf allen drei Plattformen.
    """
    from app.ui import dialogs

    opened: list[str] = []
    monkeypatch.setattr(
        dialogs.QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()) or True
    )
    worker = object()
    window._export_worker = worker
    try:
        window._export_done(worker, [tmp_path / "dose.3mf"], [])
    finally:
        window._export_worker = None
    assert not window.reveal_export.isHidden(), "der Knopf steht neben der Meldung"
    assert window.reveal_export.toolTip() == str(tmp_path)
    window.reveal_export.click()
    assert [Path(entry) for entry in opened] == [tmp_path]

    window.announce("etwas anderes")
    assert window.reveal_export.isHidden(), "eine neue Ankündigung nimmt ihn mit"


# --- die Tour durch ein Beispiel (§37.2) ------------------------------------------


def _tour_tab_visible(window: MainWindow) -> bool:
    """Ob der Tour-Reiter gerade angeboten wird — er existiert immer, sichtbar
    ist er nur mit offenem Beispiel."""
    return window.right.isTabVisible(window.right.indexOf(window.tour))


def test_opening_an_example_starts_its_tour(window: MainWindow, session: Session) -> None:
    """§37.2: ein Beispiel öffnet sich mit seiner Tour, und die Erkennung
    schaltet an den echten Signalen der Sitzung weiter — Doppelklick-Änderung,
    Undo und Redo, wie ein Nutzer sie auslöst.

    Die Wartezeiten sind großzügig: das Beispiel rechnet eine echte Reparatur,
    und läuft die auf einer belasteten Maschine über die 10-Sekunden-Vorgabe
    von ``wait_for_idle`` hinaus, endet der Test mit laufendem Arbeiter — den
    zerstört der Speicherbereiniger später mitsamt C++-Objekt, und die Suite
    reißt ohne Zeile am Ende ab.
    """
    from app.core import examples

    window.open_path(examples.directory() / "weg1-halterung-anpassen.p3d")
    session.wait_for_idle(120_000)

    assert _tour_tab_visible(window)
    assert window.right.currentWidget() is window.tour, "auch eine Warnung stiehlt den Reiter nicht"
    assert window.tour.active
    assert window.tour.current_index == 0, "der Leseschritt wartet auf „Weiter“"

    window.tour.advance()
    assert window.tour.current_index == 1

    # Die Handlung aus Schritt 2: der Durchmesser der Bohrung ändert sich.
    drill = next(entry for entry in session.project.document.ops if entry.op == "drill_hole")
    session.change_params(drill.id, {"diameter": 6.0})
    assert window.tour.current_index == 2

    session.undo()
    assert window.tour.current_index == 3

    session.redo()
    assert window.tour.current_index == 4

    window.tour.advance()
    assert window.tour.current_index == 5
    assert not window.tour.closing.isHidden(), "der Abschluss steht da"
    assert window.tour.next_button.isHidden(), "hinter dem letzten Schritt gibt es kein Weiter"

    window.tour.stop_button.click()
    assert not _tour_tab_visible(window)
    session.wait_for_idle(120_000)
    assert not session.busy, "kein Arbeiter überlebt den Test"


def test_a_plain_project_carries_no_tour(
    window: MainWindow, session: Session, tmp_path: Path
) -> None:
    """Die Tour gehört den Beispielen: ein gewöhnliches Projekt räumt den
    Reiter wieder weg, statt eine fremde Anleitung weiterlaufen zu lassen."""
    from app.core import examples
    from app.core.scene.project import new_project, save

    window.open_path(examples.directory() / "weg1-halterung-anpassen.p3d")
    session.wait_for_idle(120_000)
    assert _tour_tab_visible(window)

    path = save(new_project("centauri-carbon-2", "petg"), tmp_path / "plain.p3d")
    window.open_path(path)
    session.wait_for_idle(120_000)

    assert not _tour_tab_visible(window)
    assert not window.tour.active
    assert not session.busy, "kein Arbeiter überlebt den Test"


# --- Zeichnen und Operationsmenüs -----------------------------------------------


def test_the_toolbar_has_a_drawing_entry_for_way_two(window: MainWindow) -> None:
    """§2.2: Weg 2 (neu konstruieren) nennt die Werkzeugzeile als Ort — der
    Platz war nie belegt, und das Zeichnen lag drei Ebenen tief im Menü. Der
    Knopf startet den Skizzenmodus ohne festgelegte Operation; die
    Erzeugungsart kommt bei „Fertig".
    """
    from PySide6.QtWidgets import QToolBar

    toolbar = window.findChild(QToolBar)
    assert toolbar is not None
    labels = [action.text() for action in toolbar.actions() if action.text()]
    assert "Zeichnen" in labels
    assert labels.index("Modell einfügen") < labels.index("Zeichnen")

    window.action_sketch_free()
    try:
        assert window.sketching()
        assert window._sketch_target == ""
    finally:
        window.finish_sketch(keep=False)


def test_the_toolbar_has_the_two_entries_for_way_four(window: MainWindow) -> None:
    """§2.2: Weg 4 (organisch formen) nennt die Werkzeugzeile als Ort.

    *Formen* und *Skelett* lagen unter *Ändern → Netz* zwischen
    Reparaturwerkzeugen — an derselben Stelle wie „Löcher schließen", ohne
    Kürzel und ohne Zusammenhang mit dem Weg, für den sie gebaut sind. Die
    untere Werkzeugzeile ist mit acht Umschaltern voll; die obere hat den
    Platz, und dort steht Weg 2 bereits.

    Der Menüeintrag bleibt: Befehlspalette und Verlauf führen über ihn.
    """
    from PySide6.QtWidgets import QToolBar

    toolbar = window.findChild(QToolBar)
    assert toolbar is not None
    labels = [action.text() for action in toolbar.actions() if action.text()]
    assert "Formen" in labels
    assert "Skelett" in labels
    assert labels.index("Zeichnen") < labels.index("Formen") < labels.index("Skelett")

    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    item.setSelected(True)

    window.action_sculpt_free()
    try:
        assert window.sculpting()
    finally:
        window.finish_sculpt()

    window.action_armature_free()
    try:
        assert window.setting_armature()
    finally:
        window.finish_armature()


def test_way_four_says_what_it_needs_before_the_click(window: MainWindow) -> None:
    """Ein Knopf, der einen gewählten Körper braucht, sagt das vorher (§2.6).

    Bis hierher fing das erst die Sitzung ab: Klick, dann „Bitte zuerst ein
    Objekt auswählen." in der Statusleiste — eine Sackgasse, die der Knopf
    selbst beantworten kann (Regel 19).
    """
    window._update_actions()
    assert not window._toolbar_sculpt.isEnabled()
    assert not window._toolbar_armature.isEnabled()
    assert "ausgewählten Körper" in window._toolbar_sculpt.toolTip()

    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    item.setSelected(True)
    window._update_actions()

    assert window._toolbar_sculpt.isEnabled()
    assert window._toolbar_armature.isEnabled()
    assert "ausgewählten Körper" not in window._toolbar_sculpt.toolTip()
    assert window._toolbar_sculpt.toolTip(), "und der eigene Satz steht wieder da"


def test_the_sketch_bar_says_what_finishing_does(window: MainWindow) -> None:
    """Der Hinweis über „Fertig" zeigte auf eine Operation, die es beim
    freien Zeichnen noch nicht gibt.

    Beide Wege enden auf demselben Knopf, aber nicht am selben Ort: mit
    festgelegter Op öffnet sie sich auf der Skizze, ohne fragt erst der
    Dialog. Wer „die Operation" liest und keine gewählt hat, sucht nach
    etwas, das nirgends steht.
    """
    window.action_sketch_free()
    try:
        assert "Operation" not in window._sketch_hint.text()
        assert "Freies Zeichnen" in window.statusBar().currentMessage()
    finally:
        window.finish_sketch(keep=False)

    window.start_sketch("sketch_extrude")
    try:
        # Seit dem 16.09.2026 sagt die Zeile nur, was sonst nirgends steht —
        # auf der Hauptebene nichts; die Operation nennt die Statusleiste.
        assert not window._sketch_hint.text()
        assert str(REGISTRY.get("sketch_extrude").title) in window.statusBar().currentMessage()
    finally:
        window.finish_sketch(keep=False)


def test_undo_in_the_sketch_mode_means_the_last_stroke(window: MainWindow) -> None:
    """Strg+Z gehört im Skizzenmodus dem Blatt, nicht dem Verlauf.

    Das Kürzel hing am Dialog um das Panel — und den Dialog gibt es nur auf
    einem der beiden Wege. Im Skizzenmodus des Fensters lag Strg+Z damit beim
    Verlauf und nahm die letzte **Operation** zurück, während vor dem Nutzer
    eine Zeichenfläche stand. Aufgefallen beim Beschreiben des Kapitels, nicht
    beim Bedienen: der Editor hat einen Rückgängig-Knopf, und wer den nimmt,
    merkt nie etwas.

    Zwei Hälften, beide nötig: das Panel bringt das Kürzel mit, und das
    Fenster graut seine zwei Einträge im Modus aus. Ohne die zweite Hälfte
    feuert **keine** von beiden Belegungen — Qt lässt bei zweien derselben
    Taste keine gelten, dieselbe Falle wie bei R und C.
    """
    from PySide6.QtGui import QKeySequence, QShortcut

    from app.ui.sketch_editor import SketchPanel

    panel_keys = [
        entry.key().toString() for entry in SketchPanel("", parent=window).findChildren(QShortcut)
    ]
    assert QKeySequence(QKeySequence.StandardKey.Undo).toString() in panel_keys

    window.run_operation(REGISTRY.get("create_box"))
    dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
    _accept_after_preview(window, dialog)
    window.session.wait_for_idle()
    assert window.session.history.can_undo, "sonst prüft das Folgende nichts"
    assert window.undo_action.isEnabled()

    window.action_sketch_free()
    try:
        assert not window.undo_action.isEnabled(), "im Modus gehört Strg+Z dem Blatt"
        assert not window.redo_action.isEnabled()
    finally:
        window.finish_sketch(keep=False)

    assert window.undo_action.isEnabled(), "und danach wieder dem Verlauf"


def test_the_sketch_field_knows_as_much_as_the_sketch_mode(window: MainWindow) -> None:
    """Beide Wege zum Editor bringen die Szene mit — sonst ist einer ärmer.

    Der Docstring von ``SketchPanel`` sagt seit je, dass keiner der beiden Wege
    ein Werkzeug bekommt, das der andere nicht hat. Er stimmte nicht: der
    Skizzenmodus reichte Bauraum, Flächen und Netze herein, das Skizzenfeld im
    Operationsdialog nichts davon. Wer aus dem Verlauf eine Skizze wieder
    öffnete, hatte keinen Bauraumrand, keine Fläche des Körpers in der
    Ebenenwahl — und *Projizieren* antwortete „kein Körper" an einem Modell,
    das im Fenster stand.
    """
    from app.ui.sketch_editor import SketchEditorDialog, SketchField

    _with_two_objects(window)
    surroundings = window._sketch_surroundings()
    assert surroundings.bed is not None, "der Bauraum kommt aus dem Profil"
    assert len(surroundings.bodies) == 2, "beide Körper sind Vorlage für die Projektion"

    field = SketchField("", {}, window, surroundings)
    dialog = SketchEditorDialog("", {}, field, field._surroundings)
    try:
        canvas = dialog.canvas
        assert canvas._bed == surroundings.bed
        assert len(canvas._bodies) == 2
        # Die drei Grundebenen stehen immer; die Flächen der Körper kommen
        # dazu, sobald einer da ist. Gezählt werden die Flächen selbst: Das
        # Feld trägt seit je mehr als die drei Grundebenen (die freie Ansicht,
        # seit dem 22.09.2026 auch „Neue Ebene …"), und „mehr als drei" wäre
        # ohne eine einzige Fläche wahr gewesen.
        choice = dialog.panel.plane_choice
        faces = [
            choice.itemData(index)
            for index in range(choice.count())
            if str(choice.itemData(index)).startswith("feature:")
        ]
        assert faces, "die Flächen der Körper stehen zur Wahl"
    finally:
        dialog.reject()


def test_the_history_offers_the_other_kernel_at_a_primitive_step(window: MainWindow) -> None:
    """Der Kernwechsel steht am Schritt im Verlauf, und nur an einem Grundkörper (P2.8).

    Der Haken im Dialog ist gefallen; was blieb, ist ein Eintrag im
    Kontextmenü des Verlaufs mit dem Satz, der den Nutzen nennt. Ein
    Bohrungsschritt bekommt keinen: Bohren fragt den Körper selbst, und ein
    Wechsel dort liefe ins Leere. Ohne den exakten Kern gibt es den Eintrag
    in diese Richtung nicht — statt einer Absage nach dem Klick (Regel 19).
    """
    from app.core.registry import exact_kernel_present
    from app.core.scene.history import OperationDraft

    window.session.start_new("centauri-carbon-2", "petg")
    window.session.history.apply(
        "Quader mit Bohrung",
        [
            OperationDraft(op="create_box", params={"width": 40.0, "depth": 30.0, "height": 20.0}),
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"x": 0.0, "y": 0.0, "z": 20.0, "diameter": 6.0, "depth": 10.0},
            ),
        ],
    )
    window.session.evaluate_now()
    window.session.wait_for_idle()
    box_step, hole_step = (entry.id for entry in window.session.project.document.ops)
    offered = window.history_panel._switchable
    assert hole_step not in offered, "Bohren entscheidet der Körper, nicht der Verlauf"
    if not exact_kernel_present():
        assert box_step not in offered, "ohne Kern kein Weg dorthin"
        return
    assert offered[box_step] == "Mit echten Flächen und Kanten rechnen"

    window.switch_kernel(box_step)
    window.session.wait_for_idle()
    ops = window.session.project.document.ops
    assert ops[0].op == "create_brep_box"
    assert window.history_panel._switchable[box_step] == "Als Dreiecksmodell rechnen"
    result = window.session.last_result
    assert result is not None
    assert result.scene.objects["obj_1"].kind == "brep", "die Bohrung blieb am exakten Körper"

    window.session.undo()
    window.session.wait_for_idle()
    assert window.session.project.document.ops[0].op == "create_box"


def test_the_menu_path_matches_the_built_menu_for_every_operation(window: MainWindow) -> None:
    """§2.6: der Menüort in den Werkzeugbeschreibungen kommt aus
    ``menu_path`` — dieser Test hält ihn an der wirklich gebauten Leiste
    fest, Ebene für Ebene. Ohne die Kopplung nannte der Chat für 72 von 77
    Operationen einen Ort ohne die Untermenüs, die die Leiste einzieht.
    """
    from PySide6.QtWidgets import QMenu

    from app.core.registry import REGISTRY, menu_path

    def paths_of(menu: QMenu, trail: tuple[str, ...]) -> dict[QAction, str]:
        found: dict[QAction, str] = {}
        for action in menu.actions():
            submenu = action.menu()
            if submenu is not None:
                found.update(paths_of(submenu, (*trail, submenu.title())))
            else:
                found[action] = " → ".join((*trail, action.text()))
        return found

    built: dict[QAction, str] = {}
    for group in window._workspace_menus:
        built.update(paths_of(group, (group.title(),)))

    from app.core.registry import in_the_menu_bar

    checked = 0
    for name, action in window._op_actions.items():
        if action not in built:
            continue
        checked += 1
        assert built[action] == menu_path(REGISTRY.get(name)), name
    # **Kein Schwellenwert, sondern die Zusage** (8b, 29.08.2026). Hier stand
    # „mindestens 70", und mit den Bausteinen im Katalog wären 50 daraus
    # geworden — eine Zahl, die beim nächsten Umbau wieder jemand senkt.
    # Geprüft wird stattdessen, dass die Kopplung **jede** Menüaktion erreicht:
    # Was einen Eintrag hat, hat auch einen genannten Weg, und der stimmt.
    # **Und was rechts steht, nennt rechts** (11.09.2026): Diese Aktionen
    # haben keinen Eintrag in der Leiste, und ihr Weg beginnt bei der Karte.
    assert checked, "keine einzige Kopplung gefunden — dann prüft dieser Test nichts"
    ohne_weg = sorted(
        name
        for name, action in window._op_actions.items()
        if action not in built and in_the_menu_bar(REGISTRY.get(name).category)
    )
    assert not ohne_weg, f"diese Menüaktionen haben keinen genannten Weg: {ohne_weg}"
    rechts = [
        name
        for name, action in window._op_actions.items()
        if action not in built and not in_the_menu_bar(REGISTRY.get(name).category)
    ]
    assert rechts, "keine Handlung rechts — dann prüft dieser Test den zweiten Ort nicht"
    for name in rechts:
        assert menu_path(REGISTRY.get(name)).startswith("Handlungen rechts"), name


def test_dragging_a_face_reaches_the_document(window: MainWindow) -> None:
    """Ein Signal ohne Empfänger fällt in keinem Review auf.

    Der Viewport sendete `faceDragged`, seit es den Griff an der Fläche gibt,
    und niemand hörte zu: der Griff ließ sich ziehen, das Modell blieb, wie es
    war. Ein Test, der nur den Sender prüft, hätte das nicht gefunden — dieser
    prüft, was im Dokument ankommt.

    **Und seit dem 10.09.2026 kommt dort die Fläche an, nicht ihre Normale.**
    Der Schritt trug ``nx/ny/nz``, und die Operation bewegte damit jede Fläche,
    die dorthin zeigt — an einer Treppe beide Stufen zugleich, während der
    Kunde eine einzelne angefasst hatte.
    """
    window.run_remote("create_box", {"width": 20.0, "depth": 20.0, "height": 20.0})
    window.object_tree.tree.setCurrentItem(window.object_tree.tree.topLevelItem(0))
    window.session.wait_for_idle(60_000)
    body = next(iter(window.session.last_result.scene.objects.values()))
    top = next(
        entry
        for entry in body.features.values()
        if entry.kind == "face" and entry.params["normal"][2] > 0.9
    )

    window.viewport.faceDragged.emit(top.id, 3.0)
    window.session.wait_for_idle(60_000)

    assert [entry.op for entry in window.session.project.document.ops] == [
        "create_box",
        "push_face",
    ]
    moved = window.session.project.document.ops[-1]
    assert moved.params["distance"] == pytest.approx(3.0)
    assert moved.params["face"] == top.id, "der Schritt nennt die Fläche, die gezogen wurde"
    assert "nz" not in moved.params or moved.params["nz"] == pytest.approx(1.0)


@pytest.mark.parametrize("cancel", [False, True])
def test_import_from_start_keeps_progress_until_the_plan_finishes(
    window: MainWindow,
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    cancel: bool,
) -> None:
    """Die leere Startauswertung beendet weder Planfortschritt noch Abbrechen."""
    from app.ui import session as module

    entered, proceed = threading.Event(), threading.Event()
    real_work = module._PlanWorker.work

    def held_work(worker: Any) -> None:
        entered.set()
        assert proceed.wait(30)
        real_work(worker)

    monkeypatch.setattr(module, "PLAN_IN_WORKER_ABOVE", 0)
    monkeypatch.setattr(module._PlanWorker, "work", held_work)
    seen: list[bool] = []
    window.session.busyChanged.connect(seen.append)
    window._show_start_screen(True)
    window.open_path(MESHES / "cube_clean.stl")
    try:
        # Seit RM-224 liest zuerst ein Arbeiter die Datei; der Plan beginnt
        # erst, wenn dessen Antwort zugestellt ist — also mit laufender
        # Ereignisschleife, nicht in einem blockierenden Warten.
        for _turn in range(500):
            if entered.is_set():
                break
            qt_app.processEvents()
            entered.wait(0.01)
        assert entered.is_set()
        planner = window.session._plan
        assert isinstance(planner, module._PlanWorker)
        if window.session._worker is not None:
            assert window.session._worker.wait(5000)
        qt_app.processEvents()
        qt_app.processEvents()
        assert planner.isRunning()
        assert window.session._worker is None, "the initial evaluation must have finished"
        assert window.session.busy
        assert False not in seen, "progress must not end before the import plan"
        assert window._progress_states["evaluation"].active
        window._show_progress_bar()
        assert window.cancel_button.isVisibleTo(window)
        assert window.cancel_button.isEnabled()
        if cancel:
            window.cancel_button.click()
    finally:
        proceed.set()
        assert window.session.wait_for_idle(30_000)

    assert not window.session.busy
    assert not window._progress_states["evaluation"].active
    assert not window.cancel_button.isVisibleTo(window)
    assert seen[-1] is False
    assert bool(window.session.project.document.ops) is not cancel
    assert bool(window.session.project.sources) is not cancel


def test_an_import_failure_does_not_end_another_evaluation(
    session: Session, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch der frühere Fehler des Plans lässt die laufende Auswertung sichtbar."""
    from app.ui import session as module

    entered, proceed = threading.Event(), threading.Event()
    real_evaluation = session.run_evaluation

    def held_evaluation(quality: Any = None) -> Any:
        entered.set()
        assert proceed.wait(30)
        return real_evaluation(quality)

    monkeypatch.setattr(module, "PLAN_IN_WORKER_ABOVE", 0)
    monkeypatch.setattr(session, "run_evaluation", held_evaluation)
    seen: list[bool] = []
    failed: list[object] = []
    session.busyChanged.connect(seen.append)
    session.importFailed.connect(failed.append)
    session.evaluate_async()
    try:
        assert entered.wait(5)
        session.import_payload_async("broken.stl", b"broken")
        planner = session._plan
        assert planner is not None and planner.wait(5000)
        qt_app.processEvents()
        qt_app.processEvents()
        assert failed, "the import must have reported its failure"
        assert session._plan is None
        assert session.busy
        assert False not in seen, "the failed plan must not end the evaluation's progress"
    finally:
        proceed.set()
        assert session.wait_for_idle(30_000)

    assert not session.busy
    assert seen[-1] is False


def test_a_late_worker_does_not_switch_off_its_successor(session: Session) -> None:
    """Der Nachzügler meldete „fertig" mitten in den Lauf seines Nachfolgers.

    Ein Arbeiter ist fertig, bevor Qt sein ``finished`` zugestellt hat; in
    dieser Lücke startet der nächste Lauf. Der Nachzügler kam dann in
    ``_on_thread_done`` an, schrieb ``None`` in ``_worker`` — das Feld gehörte
    da längst dem Nachfolger — und meldete ``busyChanged(False)``.

    **Zu sehen war das an der Stelle, an der jeder anfängt.** Eine Datei auf
    den Startbildschirm ziehen legt zwei Läufe hintereinander: den leeren des
    neuen Projekts und den des Imports. Bei einem Modell mit 1,3 Millionen
    Dreiecken verschwanden Balken und Abbrechen nach einer Zehntelsekunde, und
    die Anwendung rechnete die restlichen vier Sekunden ohne ein Zeichen von
    sich — genau das, was §2.8 ab zwei Sekunden verlangt. Unsichtbar, aber
    schwerer: ``busy`` log danach, ``wait_for_idle`` wartete nicht, und der
    nächste ``evaluate_async`` hätte einen zweiten Lauf **parallel** gestartet
    statt ihn einzureihen (§15.6).
    """
    from app.ui.session import _EvaluationWorker

    session.import_model(MESHES / "cube_clean.stl")
    running = session._worker
    assert running is not None, "der Import hat keinen Lauf gestartet"

    seen: list[bool] = []
    session.busyChanged.connect(seen.append)
    # Ein Vorgänger, dessen Signal jetzt erst ankommt. Gestartet wird er nie —
    # zugestellt wird sein Ende, und darum geht es.
    session._on_thread_done(_EvaluationWorker(session))

    assert seen == [], "ein alter Lauf meldet das Ende eines fremden"
    assert session._worker is running, "die Referenz auf den laufenden Lauf ging verloren"
    assert session.busy, "und damit log auch busy"

    session.wait_for_idle()


def test_a_replaced_run_keeps_the_progress_standing(session: Session) -> None:
    """Ein Ersetzen ist kein Aufhören (§15.6, §2.8).

    ``_rerun_pending`` heißt: dieser Lauf ist überholt, der nächste startet
    sofort. Dazwischen ``busyChanged(False)`` zu melden nähme Balken und
    Abbrechen für eine Zehntelsekunde mit — beim Ziehen an einem Schieber im
    Sekundentakt. Dieselbe Begründung, aus der ``evaluationCancelled`` einen
    ersetzten Lauf nicht meldet.
    """
    session.import_model(MESHES / "cube_clean.stl")
    running = session._worker
    assert running is not None

    seen: list[bool] = []
    session.busyChanged.connect(seen.append)
    session._rerun_pending = True
    session._on_thread_done(running)

    assert False not in seen, "der Balken fällt zwischen zwei Läufen aus"
    assert seen == [True], "und der nächste Lauf meldet sich als laufend"

    session.wait_for_idle()


def test_cancelling_discards_the_queued_rerun(session: Session) -> None:
    """Abbrechen heißt aufhören — auch mit dem, was eingereiht wartet.

    ``cancel()`` ließ ``_rerun_pending`` stehen: Die Statuszeile schrieb
    „Abgebrochen", und ``_on_thread_done`` startete im selben Atemzug den
    eingereihten Nachlauf — die Maschine rechnete weiter, das Wort stand
    daneben (Gesamtreview 25.08.2026, I-1). Ein **Ersetzen** behält den
    Nachlauf weiter, das prüft der Test darüber; ein **Nutzer-Abbruch**
    verwirft ihn.
    """
    session.import_model(MESHES / "cube_clean.stl")
    running = session._worker
    assert running is not None
    session._rerun_pending = True

    session.cancel()

    assert not session._rerun_pending, "der Abbruch verwirft die eingereihte Anfrage"
    session.wait_for_idle()
    assert session._worker is None or not session._worker.isRunning()


def test_a_late_result_does_not_overwrite_the_current_scene(session: Session) -> None:
    """§15.3: stehen bleibt der letzte **gültige** Stand.

    Das Ergebnis eines überholten Laufs gehört zu einem Dokument, das es nicht
    mehr gibt. Eingeblendet wurde es trotzdem — beim Ablegen einer Datei war
    das die leere Szene des neuen Projekts, über das Modell gelegt, das gerade
    geladen wurde. Sichtbar als Aufblitzen, und es nahm den Ladeschleier mit,
    der genau daran hängt, ob ein Körper dasteht.
    """
    from app.ui.session import _EvaluationWorker

    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()
    current = session.last_result
    assert current is not None and current.scene.objects

    session.import_model(MESHES / "two_components.stl")
    stale = dataclasses.replace(current, scene=dataclasses.replace(current.scene, objects={}))
    session._on_finished(stale, finished=_EvaluationWorker(session))

    assert session.last_result is current, "eine alte Szene hat die aktuelle ersetzt"

    session.wait_for_idle()


def test_every_worker_survives_the_delivery_of_its_own_signal(session: Session) -> None:
    """Die Regel gilt für alle drei Arbeiter, nicht nur den, bei dem es knallte.

    ``_on_thread_done``, ``_on_agent_done`` und ``_on_split_done`` laufen als
    Slots des ``finished``-Signals ihres eigenen Arbeiters. Wer die Referenz
    dort loslässt, gibt den PySide-Wrapper mitsamt C++-QThread frei, während
    Qt die Zustellung noch auf dem Stapel hat — der Absturz ohne Traceback, der
    die Suite sporadisch riss.

    Beim Auswerter wurde das behoben, weil dort jemand hämmerte. Agent und
    Teilungssuche trugen denselben Fehler weiter; die Teilungssuche sogar in
    einem Lambda, das ``None`` in genau das Feld schrieb, dessen Objekt es
    gerade zustellte.

    Geprüft am Slot statt am Absturz: einen Absturz zuverlässig auszulösen
    braucht Last und Glück, die Regel dahinter ist eine Zeile.

    **Und geprüft an der Regel statt an drei Feldnamen.** Die Sitzung hielt je
    Arbeiterart genau einen ausgelaufenen — ``_finished_worker``,
    ``_finished_agent``, ``_finished_split``. Ein Feld hält aber nur einen, und
    ``_on_thread_done`` startet bei ``_rerun_pending`` sofort den nächsten
    Lauf: Wird der schnell fertig, überschreibt er das Feld, während Qt den
    Vorgänger noch abräumt. Genau diese Kette stand im Stapelabzug eines
    Absturzes, den das Repository lange nur als „Segfault in test_chat_ui.py"
    kannte. Gehalten wird jetzt in einer Liste (:mod:`app.ui.leash`), und
    dieser Test liest, dass die drei Slots sie benutzen.
    """
    import re

    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    assert session._worker is None, "nach dem Warten läuft keiner mehr"
    assert hasattr(session, "_leash"), "die Sitzung hat keine Halteleine"

    quelle = (Path(__file__).parent.parent / "app" / "ui" / "session.py").read_text(
        encoding="utf-8"
    )
    for slot in ("_on_thread_done", "_on_agent_done", "_on_split_done"):
        koerper = quelle[quelle.index(f"def {slot}(") :]
        koerper = koerper[: koerper.index(chr(10) + "    def ", 1)]
        assert "_leash.hold_until_done" in koerper, (
            f"{slot} übergibt seinen Arbeiter nicht an die Halteleine — wer die "
            "Referenz im eigenen finished-Slot loslässt, gibt den Wrapper frei, "
            "während Qt die Zustellung noch auf dem Stapel hat."
        )
        assert not re.search(r"self\._(worker|agent|split)\s*=\s*None", koerper), (
            f"{slot} schreibt None in sein Feld, statt den Arbeiter erst zu sichern."
        )


# --- die Vorschau sagt, dass sie eine ist (Konzept Teil 10, 9b) ------------------


def test_a_running_preview_says_it_is_one(window: MainWindow) -> None:
    """Ein verändertes Bild sieht aus wie ein Ergebnis.

    Die Live-Vorschau gab es lange, bevor jemand sie sah; seit der Dialog neben
    dem Bild steht, sieht man sie — und damit wird die stillere Hälfte des
    Problems sichtbar: nichts sagte, dass das Gezeigte noch nicht übernommen
    ist.
    """
    banner = window.viewport.banner
    assert banner.isHidden(), "ohne Vorschau kein Band"

    window._show_preview(object())
    assert not banner.isHidden()
    assert "noch nicht übernommen" in banner.note.text()

    window._clear_preview()
    assert banner.isHidden(), "Dialog zu, Band weg"


def test_the_legend_names_the_colours_it_explains(window: MainWindow) -> None:
    """Regel 18: Farbe trägt nie allein. Das Band führt Zeichen und Namen."""
    window._show_preview(object())
    text = window.viewport.banner.legend.text()

    for encoding in (DIFF_PALETTES["blue_orange"].added, DIFF_PALETTES["blue_orange"].removed):
        assert encoding.symbol in text
        assert tr(encoding.label_key) in text


def test_switching_the_palette_relabels_the_legend(window: MainWindow) -> None:
    """Die Legende erklärt Farben — wechseln die, muss sie mitgehen."""
    window._show_preview(object())
    window.viewport.set_difference_palette("greyscale")

    assert not window.viewport.banner.isHidden()
    assert tr(DIFF_PALETTES["greyscale"].added.label_key) in window.viewport.banner.legend.text()


def test_holding_space_shows_the_state_before(window: MainWindow) -> None:
    """Einen Unterschied sieht man nur, wenn man beides kennt.

    Das Modell unter der Vorschau *ist* der Stand vor der Operation — die
    Differenz liegt nur darüber. Sie wegzunehmen ist deshalb schon der ganze
    Vergleich, und er kostet keine zweite Rechnung.
    """
    from PySide6.QtGui import QKeyEvent

    window._show_preview(object())
    viewport = window.viewport
    assert not viewport.difference_held

    hold = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
    let_go = QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)

    assert viewport._compare.eventFilter(window, hold), "die Leertaste gehört hier der Vorschau"
    assert viewport.difference_held

    assert viewport._compare.eventFilter(window, let_go)
    assert not viewport.difference_held


def test_a_space_in_a_text_field_stays_a_space(window: MainWindow) -> None:
    """Sonst könnte man keinen Namen mit Leerzeichen tippen, solange eine
    Vorschau läuft — und eine Vorschau läuft, sobald ein Dialog offen ist."""
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QLineEdit

    window._show_preview(object())
    field = QLineEdit(window)
    field.setFocus()

    hold = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
    assert not window.viewport._compare.eventFilter(field, hold)
    assert not window.viewport.difference_held


def test_the_survey_takes_spaces_while_a_preview_runs(window: MainWindow) -> None:
    """Im Rückmeldebogen ließ sich kein Leerzeichen tippen (RM-437).

    Der Bogen ist nicht modal und erscheint auch, während ein
    Operationsdialog seine Vorschau zeigt. Der Vergleich an der Anwendung
    hielt seine Felder nicht für Textfelder, weil ``QPlainTextEdit`` nicht von
    ``QTextEdit`` erbt, und nahm jedes Leerzeichen für sich. Geprüft wird mit
    echten Tasten über den Filter der Anwendung: an jedem mehrzeiligen Feld
    des Dialogs und an jeder Art Texteingabe, die die Oberfläche benutzt.
    """
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLineEdit, QPlainTextEdit, QTextEdit

    window._show_preview(object())
    window._open_survey()
    dialog = window._survey_dialog
    assert dialog is not None
    try:
        plain = dialog.findChildren(QPlainTextEdit)
        assert len(plain) >= 3, "zwei Fragen des Bogens und das Nachrichtenfeld"
        rich = QTextEdit(dialog)
        line = QLineEdit(dialog)
        combo = QComboBox(dialog)
        combo.setEditable(True)
        inner = combo.lineEdit()
        assert inner is not None
        fields: list[tuple[QWidget, Any]] = [
            *((field, field.toPlainText) for field in plain),
            (rich, rich.toPlainText),
            (line, line.text),
            (inner, combo.currentText),
        ]
        for field, read in fields:
            field.setFocus()
            QTest.keyClicks(field, "fehlt nichts")
            assert read().endswith("fehlt nichts"), type(field).__name__
        assert not window.viewport.difference_held, "der Vergleich blieb aus"
    finally:
        dialog.close()
        dialog.deleteLater()


def test_a_held_key_is_not_a_flicker(window: MainWindow) -> None:
    """Eine gehaltene Taste schickt eine Folge aus Press und Release, nicht
    einen langen Druck. Ohne diese Prüfung flackerte die Vorschau im Takt der
    Tastenwiederholung."""
    from PySide6.QtGui import QKeyEvent

    window._show_preview(object())
    window.viewport._compare.eventFilter(
        window, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
    )

    repeat = QKeyEvent(
        QEvent.Type.KeyRelease,
        Qt.Key.Key_Space,
        Qt.KeyboardModifier.NoModifier,
        autorep=True,
    )
    assert not window.viewport._compare.eventFilter(window, repeat)
    assert window.viewport.difference_held, "die Wiederholung ändert nichts"


# --- Einrichtung: was gewählt wurde, muss auch gelten (Konzept Teil 8) -----------


def test_the_first_run_reaches_the_project_that_is_open(window: MainWindow) -> None:
    """Gewählt war Centauri Carbon 2 und PETG — in den Druckeinstellungen stand
    danach „Allgemeiner FDM-Drucker" und PLA.

    Die Einstellungen sagen zu Recht, dass die Werte „für das nächste neue
    Projekt" gelten. Beim ersten Start ist das offene Projekt aber genau das,
    mit dem weitergearbeitet wird.
    """
    window.settings.printer = "centauri-carbon-2"
    window.settings.material = "petg"

    window._adopt_defaults()
    window.session.wait_for_idle()

    assert window.session.profile.printer.id == "centauri-carbon-2"
    assert window.session.profile.material.id == "petg"


def test_a_project_with_content_keeps_its_profile(window: MainWindow) -> None:
    """In ein Projekt mit Inhalt greift eine Einstellung nicht hinein — das
    wäre eine Geometrieänderung ohne Operation."""
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    before = window.session.profile.printer.id
    window.settings.printer = "centauri-carbon-2"

    window._adopt_defaults()

    assert window.session.profile.printer.id == before


def test_the_discard_question_names_what_it_throws_away(window: MainWindow) -> None:
    """„Diese Änderung verwirft 2 zurückgenommene Schritte" sagt, wie viel weg
    ist, nicht was — und genau das entscheidet, ob man Ja sagt."""
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    assert not window._discarded_names(), "nichts zurückgenommen, nichts zu nennen"

    window.action_undo()
    window.session.wait_for_idle()

    names = window._discarded_names()
    assert len(names) == window.session.history.discardable
    assert all(name.strip() for name in names), "und jeder Name sagt etwas"


def test_the_question_button_carries_the_answer(qt_app: QApplication) -> None:
    """Auf „Welchen soll ich abziehen?" ist „OK" keine Antwort.

    Es ist die Aufforderung, sie sich aus der Liste danebenzudenken. Der Knopf
    sagt, was er tut — derselbe Grundsatz wie im Dialog *Ungesicherte
    Änderungen*, den das Konzept als Vorlage nennt.
    """
    from app.ui.dialogs import AskDialog

    dialog = AskDialog("Welchen soll ich abziehen?", ["Klotz A", "Klotz B", "Keinen"])

    assert dialog._accept.text() == "Klotz A", "die Vorauswahl steht auf dem Knopf"

    dialog.list.setCurrentRow(2)
    assert dialog._accept.text() == "Keinen", "und sie folgt der Auswahl"
    assert dialog.chosen() == "Keinen"

    # **Und er trägt das Wort, das der Kunde liest, nicht den Wert dahinter.**
    # Die Einheitenfrage zeigt „Zoll (in)" in der Liste; auf dem Knopf stand
    # „in" — im deutschen Fenster kein Wort (Durchsicht 14.09.2026).
    units = AskDialog("In welcher Einheit ist das Modell?", ["mm", "cm", "in"])
    units.list.setCurrentRow(2)
    assert units._accept.text() == "Zoll (in)", "der Knopf sagt, was die Zeile sagt"
    assert units.chosen() == "in", "der Kern bekommt weiter das Kürzel"


def test_the_generator_dialog_puts_the_seed_out_of_the_way(qt_app: QApplication) -> None:
    """§2.4: vorn die zwei Werte, die man ändert.

    Der Startwert stand an dritter Stelle über allem, was jemand hier tun
    will — er entscheidet nichts, solange man ihn nicht wiederholen will.
    """
    from app.ui.generate_dialog import GenerateDialog

    dialog = GenerateDialog(None)

    assert not dialog.seed.isVisible(), "zugeklappt, nicht entfernt"
    assert dialog.advanced.isVisibleTo(dialog), "die Klappe selbst steht da"


def test_a_measure_drops_zeros_it_never_measured(qt_app: QApplication) -> None:
    """„60,00" trägt genau so viel Auskunft wie „60" und braucht mehr Platz.

    Die Nullen stehen dort, weil die Formatierung eine feste Stellenzahl hat,
    nicht weil jemand sie gemessen hätte. Ein krummes Maß behält seine Stellen
    — genau diesen Unterschied darf eine Abkürzung nicht verschlucken.
    """
    from app.ui.labels import compact_length

    assert compact_length(60.0) == "60"
    assert compact_length(11.0) == "11"
    assert compact_length(0.0) == "0"
    assert compact_length(60.25) == "60,25"
    assert compact_length(0.5) == "0,5"


def test_the_object_tree_fits_its_measures_in_the_card(qt_app: QApplication) -> None:
    """Die linke Zone ist so breit wie ``LEFT_WIDTH``, seit sie über der
    Ansicht liegt.

    Mit fester Stellenzahl brauchten Name und Maße dreihundertdreiundvierzig
    Pixel und bekamen zweihundertsechzig — die Spalte wurde abgeschnitten, und
    zwar bei jedem Projekt, nicht nur bei langen Namen.

    **Gefragt wird die Karte, nicht Qt.** Der Test rief hier
    ``resizeColumnToContents`` für beide Spalten und maß dann deren Summe — also
    genau das, was die Karte gerade *nicht* tut: Sie teilt die Breite
    (``_size_columns``), weil der Inhalt beider Spalten zusammen nun einmal
    breiter sein kann als die Karte. Solange die Namensspalte auf ``Stretch``
    stand, ging der Aufruf für sie ins Leere und die Summe stimmte zufällig; als
    die Maßspalte ihren Deckel bekam, tat er es nicht mehr. Ein Test, der die
    Einstellung überschreibt, die er prüfen soll, prüft sie nicht.
    """
    from PySide6.QtWidgets import QTreeWidgetItem

    from app.ui.overlay import LEFT_WIDTH
    from app.ui.panels import ObjectTree

    tree = ObjectTree()
    tree.resize(LEFT_WIDTH, 200)
    QTreeWidgetItem(tree.tree, ["Halter", "60 × 40 × 11 mm"])
    tree._size_columns()

    header = tree.tree.header()
    needed = header.sectionSize(0) + header.sectionSize(1)
    assert needed <= LEFT_WIDTH, f"{needed} Pixel bei {LEFT_WIDTH} verfügbaren"
    assert header.sectionSize(0) > header.sectionSize(1), (
        "der Name ist die Auskunft, das Maß die Beigabe"
    )


def test_the_object_tree_grows_with_its_content(qt_app: QApplication) -> None:
    """§2.5: die Karten der linken Spalte sind so hoch wie ihr Inhalt.

    Gemeint war das seit je, umgesetzt war es nicht. Qt gab jeder Ansicht ihre
    eigene Mindesthöhe von etwa zwei Zeilen und ließ es dabei — der Objektbaum
    scrollte ab dem zweiten Körper, während unter der Spalte sechshundert Pixel
    leer blieben. Der zweite Körper ist genau das, was nach einer Teilung
    entsteht.
    """
    from PySide6.QtWidgets import QTreeWidgetItem

    from app.ui.panels import ObjectTree

    tree = ObjectTree()
    for name in ("Teil A", "Teil B", "Teil C", "Teil D", "Teil E", "Teil F"):
        QTreeWidgetItem(tree.tree, [name, "20 × 20 × 20 mm"])
    tree._fit()

    row = tree.tree.sizeHintForRow(0)
    assert row > 0
    assert tree.tree.height() >= 6 * row, (
        f"sechs Zeilen brauchen {6 * row} px, die Ansicht ist {tree.tree.height()} px hoch"
    )


def test_the_history_grows_with_its_content(qt_app: QApplication) -> None:
    """Dasselbe für den Verlauf — bei vier Schritten waren zwei zu sehen."""
    from app.core.types import Document, Operation, Transaction
    from app.ui.panels import HistoryPanel

    document = Document(format_version=1, app_version="0.0.1")
    for number in range(1, 5):
        document.ops.append(Operation(id=number, op="drill_hole", inputs=(), params={}))
        document.transactions.append(
            Transaction(id=f"t{number}", title=f"Schritt {number}", ops=(number,))
        )

    panel = HistoryPanel()
    panel.show_document(document)

    row = panel.list.sizeHintForRow(0)
    assert row > 0
    assert panel.list.height() >= 4 * row, (
        f"vier Schritte brauchen {4 * row} px, die Liste ist {panel.list.height()} px hoch"
    )


def test_the_empty_parameter_note_is_readable(qt_app: QApplication) -> None:
    """Der Satz im leeren Zustand war nach anderthalb Zeilen abgeschnitten.

    Ein Label mit Umbruch meldet seine Höhe über ``heightForWidth``, und diese
    Kette reißt in einem Layout ohne Streckfaktor: siebzehn Pixel für vier
    Zeilen Text.
    """
    from app.core.types import Document
    from app.ui.panels import ParameterPanel

    panel = ParameterPanel()
    panel.show_document(Document(format_version=1, app_version="0.0.1"))

    label = panel._empty
    line = label.fontMetrics().height()
    assert label.minimumHeight() >= 2 * line, (
        f"{label.minimumHeight()} px für einen Satz von {label.text()!r}"
    )


def test_the_parameter_card_survives_getting_parameters(qt_app: QApplication) -> None:
    """Der leere Zustand hinterlässt eine tote Referenz, wenn man ihn misst.

    ``show_document`` räumt die Zeilen des Formulars weg; danach ist das
    C++-Objekt des Labels fort, während die Python-Referenz noch steht. Wer es
    danach vermäße, stürbe an genau dem — beim ersten Projekt mit Parametern,
    also bei jedem Weg 2.
    """
    from app.core.types import Document, Parameter
    from app.ui.panels import ParameterPanel

    panel = ParameterPanel()
    panel.show_document(Document(format_version=1, app_version="0.0.1"))

    document = Document(format_version=1, app_version="0.0.1")
    document.parameters["breite"] = Parameter(name="breite", value=60.0)
    panel.show_document(document)

    assert "breite" in panel._editors


def test_parameter_rows_recalculate_the_card_height(qt_app: QApplication) -> None:
    """Neue Zeilen dürfen nicht in der Höhe des leeren Zustands landen.

    Die schwebende linke Karte besitzt kein übergeordnetes Layout, das eine
    verspätete Wunschhöhe automatisch übernimmt. Nach dem Wechsel vom leeren
    Hinweis zu drei Parametern blieb deshalb die alte Mindesthöhe stehen und
    Qt presste Zahlen- und Einheitenfelder bis auf wenige Pixel zusammen.
    """
    from app.core.types import Document, Parameter
    from app.ui.panels import ParameterPanel

    panel = ParameterPanel()
    panel.resize(260, panel.minimumHeight())
    panel.show_document(Document(format_version=1, app_version="0.0.1"))
    panel.show()
    QApplication.processEvents()

    document = Document(format_version=1, app_version="0.0.1")
    for name, title, value in (
        ("breite", "Breite", 60.0),
        ("tiefe", "Tiefe", 40.0),
        ("staerke", "Stärke", 10.99),
    ):
        document.parameters[name] = Parameter(name=name, title=title, value=value)
    panel.show_document(document)
    QApplication.processEvents()

    assert panel.minimumHeight() >= panel.sizeHint().height(), (
        f"Mindesthöhe {panel.minimumHeight()} px, Inhalt {panel.sizeHint().height()} px"
    )
    for name, editor in panel._editors.items():
        assert editor.height() >= editor.minimumSizeHint().height(), (
            f"{name}: Feld {editor.height()} px, benötigt {editor.minimumSizeHint().height()} px"
        )
        unit = panel._unit_editors[name]
        assert unit.height() >= unit.minimumSizeHint().height(), (
            f"{name}: Einheit {unit.height()} px, benötigt {unit.minimumSizeHint().height()} px"
        )


def test_a_very_long_list_stops_growing(qt_app: QApplication) -> None:
    """Sonst schöbe ein Baum mit fünfzig Teilen den Verlauf aus dem Fenster."""
    from PySide6.QtWidgets import QTreeWidgetItem

    from app.ui.panels import MAX_ROWS, ObjectTree

    tree = ObjectTree()
    for number in range(50):
        QTreeWidgetItem(tree.tree, [f"Teil {number}", "10 × 10 × 10 mm"])
    tree._fit()

    row = tree.tree.sizeHintForRow(0)
    header = tree.tree.header().height() + 2 * tree.tree.frameWidth() + 2
    assert tree.tree.height() <= header + MAX_ROWS * row, (
        f"{tree.tree.height()} px bei fünfzig Zeilen à {row} px"
    )
    assert tree.tree.height() < 50 * row, "die Deckelung greift nicht"


def test_a_finding_says_which_body_it_means(qt_app: QApplication) -> None:
    """Zwei ausgehöhlte Körper meldeten zweimal denselben Satz.

    Im Bericht standen zwei Zeilen, Wort für Wort gleich — das sieht aus wie
    ein Fehler in der Anwendung und nicht wie zwei Befunde. Die Kennung stand
    im Befund, nur nie in der Zeile.
    """
    from app.core.types import Finding
    from app.ui.panels import _line_for

    finding = Finding(
        code="hollow.done",
        severity="info",
        message="Ausgehöhlt.",
        object_id="obj_2",
        values={"wall_mm": 2.0, "removed_cm3": 14.3},
    )

    plain = _line_for(finding)
    assert "obj_2" in plain, "ohne Namensliste bleibt die Kennung stehen"

    named = _line_for(finding, {"obj_2": "Klotz B"})
    assert "Klotz B" in named, "mit Namensliste der Name"
    assert "obj_2" not in named


def test_a_finding_writes_its_numbers_with_their_unit(qt_app: QApplication) -> None:
    """„Die Wandstärke stimmt im Rahmen des Rasters" nannte die Wandstärke
    nicht.

    Und wie viel Material gespart wurde — die Frage, für die man die Operation
    aufruft — stand ausschließlich im Tooltip.
    """
    from app.core.types import Finding
    from app.ui import labels
    from app.ui.panels import _line_for

    values = {"wall_mm": 2.0, "removed_cm3": 14.3}
    line = _line_for(
        Finding(code="hollow.done", severity="info", message="Ausgehöhlt.", values=values)
    )

    # **Gegen ``value_text`` und nicht gegen eine ausgeschriebene Stellenzahl.**
    # Hier stand „2,0 mm" — die Zusage ist aber, dass die Zahl ihre Einheit
    # trägt, und wie viele Nachkommastellen sie dabei hat, ist der Ist-Zustand.
    # Der Test fiel deshalb bei `3deb8910`, das Zeile und Tooltip auf dieselbe
    # Quelle stellte: Die Zeile schreibt seither „2,00 mm", wie der Tooltip es
    # immer schon tat. Gebrochen war nicht die Zusage, sondern eine Angabe
    # daneben — und ein Test, der die mitnagelt, blockiert genau die
    # Vereinheitlichung, für die er zeugen sollte.
    for key, value in values.items():
        assert labels.value_text(key, value) in line, f"{key}: {line}"


def test_the_arrangement_spacing_knows_the_plate_adhesion(window: MainWindow) -> None:
    """§25, §29: die Operation kennt die Druckeinstellung nicht, das Fenster
    beide.

    Zwei Körper mit fünf Millimetern Luft und je fünf Millimetern Brim stehen
    einander im Weg — der Haftungsrand zählt zwischen Nachbarn zweimal, und es
    fällt erst auf der Platte auf. Beim Gewürzset war das die erste
    Deckelplatte. Der Dialog öffnet deshalb mit dem Abstand, den die Haftung
    verlangt; ändern lässt er sich weiterhin.
    """

    from app.core.knowledge import print_settings as settings_table

    _with_two_objects(window)
    settings = settings_table.resolve(window.session.profile)
    # Als eigene Wahl: Was nicht gewählt ist, kommt aus der Grundlage (Skirt).
    settings = settings_table.with_choice(settings, "adhesion.kind", "brim")
    settings = settings_table.with_choice(settings, "adhesion.brim_width", 5.0)
    window.session.set_print_settings(settings)

    window.run_operation(REGISTRY.get("arrange_bed"))

    dialog = window._op_dialog
    assert dialog is not None
    assert dialog.values()["spacing"] == pytest.approx(10.0), "zweimal fünf Millimeter Brim"
    dialog.reject()
    window.session.wait_for_idle()


def test_without_plate_adhesion_the_spacing_stays_the_default(window: MainWindow) -> None:
    """Ohne Rand kein Aufschlag — die Vorgabe der Operation bleibt stehen."""

    from app.core.knowledge import print_settings as settings_table

    _with_two_objects(window)
    settings = settings_table.resolve(window.session.profile)
    settings = settings_table.with_choice(settings, "adhesion.kind", "none")
    window.session.set_print_settings(settings)

    window.run_operation(REGISTRY.get("arrange_bed"))

    dialog = window._op_dialog
    assert dialog is not None
    assert dialog.values()["spacing"] == pytest.approx(5.0)
    dialog.reject()
    window.session.wait_for_idle()


def test_the_cards_make_room_for_the_sketch_bar(window: MainWindow) -> None:
    """§2.5: die Karten liegen über der Ansicht — und weichen der Leiste aus.

    **Diese Zusage hat der Umbau umgedreht, und sie ist dabei besser
    geworden.** Solange der Skizzenmodus die Ansicht *ersetzte*, lag er unter
    den schwebenden Karten: die ersten Werkzeuge unter der linken, die
    Bedingungsliste unter der rechten. Die Antwort darauf war
    ``set_zone_margins`` — die Ansicht wich den Karten aus.

    Seit dem Schnitt (§30.1, P4) sitzt der Skizzenmodus in der unteren Karte,
    und für die gilt die Regel schon: ``_bottom_room`` zieht ihre Höhe von der
    Fläche ab, die den seitlichen Zonen bleibt. Jetzt weichen also **die
    Karten der Leiste aus** statt die Ansicht den Karten — eine Stelle
    weniger, an der zwei Rechnungen übereinstimmen müssen.

    Geprüft wird die Wirkung und nicht der Mechanismus: Die Leiste braucht
    mehr Höhe, sobald der Skizzenmodus läuft, und den seitlichen Zonen bleibt
    um denselben Betrag weniger.

    **Gerechnet und nicht an den Karten gemessen.** In einem nie gezeigten
    Fenster ist ``height()`` null — bei beiden Karten, vorher wie nachher, und
    ein Vergleich zweier Nullen ist grün ohne Aussage
    (`.claude/rules/wartezeit.md`, „isVisible lügt in einem nie gezeigten
    Fenster"). ``_bottom_room`` dagegen fragt den ``sizeHint``, und den gibt
    es auch ungezeigt.
    """
    window.resize(1400, 900)
    window.overlay._place()
    schmal = window.overlay._bottom_room()

    window.start_sketch("sketch_extrude", "")
    assert window._sketch_panel is not None
    window.overlay._place()
    breit = window.overlay._bottom_room()

    assert breit > schmal, "die Leiste trägt jetzt den Skizzenmodus"
    # Dieselbe Rechnung, die ``_lay_out`` für die Zonen anstellt.
    assert (900 - breit) < (900 - schmal), "und den Zonen daneben bleibt weniger"

    window.finish_sketch(keep=False)
    window.overlay._place()
    assert window.overlay._bottom_room() == schmal, "danach ist sie wieder, was sie war"


def _report_codes(window: MainWindow) -> list[str]:
    """Die Codes der Befunde, die im Bericht stehen."""
    from PySide6.QtCore import Qt as _Qt

    listing = window.report.list
    return [
        listing.item(row).data(_Qt.ItemDataRole.UserRole).code for row in range(listing.count())
    ]


def test_time_and_material_are_cross_checked_too(window: MainWindow) -> None:
    """§28.2 meint beide Zahlen, nicht nur das Stützvolumen.

    Beim Gewürzhalter standen 12 g gegen 10 g und 46 min gegen 37 min — 17 und
    20 Prozent auseinander —, und der Prüfbericht meldete vier Hinweise und
    keine Warnung. ``gcode.compare`` kennt die Schwelle von fünfzehn Prozent
    seit je; gerufen wurde sie nur für die Stützen.
    """
    from app.core.knowledge import print_settings as settings_table
    from app.core.slice import gcode
    from app.core.slice.estimate import total as estimate_total

    _with_two_objects(window)
    window.report.show_result(None)

    # Was der Slicer geschrieben hat: gut ein Fünftel unter der Schätzung.
    result = window.session.last_result
    settings = settings_table.resolve(window.session.profile)
    bodies = [(entry.mesh.volume, entry.mesh.area) for entry in result.scene.objects.values()]
    estimate = estimate_total(bodies, settings)
    measured = gcode.GcodeMetrics(
        filament_grams=estimate.grams * 0.8,
        print_seconds=estimate.seconds * 0.8,
    )

    window._compare_totals(measured)

    # Zwei Befunde mit demselben Satz sind seit dem 11.09.2026 **eine** Zeile
    # „(2) …" (Robert: „gleiche Meldungen zusammenfassen"); was jeder für
    # sich sagt — Material, Zeit, die Zahlen —, steht im Tooltip.
    from app.ui.panels import _BUNDLE_ROLE

    listing = window.report.list
    rows = [
        listing.item(row)
        for row in range(listing.count())
        if listing.item(row).data(Qt.ItemDataRole.UserRole).code == "gcode.deviation"
    ]
    assert len(rows) == 1 and rows[0].data(_BUNDLE_ROLE) == 2, "Material und Zeit, beide"
    assert rows[0].text().startswith("(2) ")
    assert "Material" in rows[0].toolTip() and "Zeit" in rows[0].toolTip(), rows[0].toolTip()


def test_a_close_estimate_stays_quiet(window: MainWindow) -> None:
    """Fünf Prozent daneben ist keine Meldung wert — sonst stünde die Warnung
    nach jedem Lauf da und wäre nach dem dritten unsichtbar."""
    from app.core.knowledge import print_settings as settings_table
    from app.core.slice import gcode
    from app.core.slice.estimate import total as estimate_total

    _with_two_objects(window)
    window.report.show_result(None)

    result = window.session.last_result
    settings = settings_table.resolve(window.session.profile)
    bodies = [(entry.mesh.volume, entry.mesh.area) for entry in result.scene.objects.values()]
    estimate = estimate_total(bodies, settings)

    window._compare_totals(
        gcode.GcodeMetrics(filament_grams=estimate.grams * 0.95, print_seconds=estimate.seconds)
    )

    assert "gcode.deviation" not in _report_codes(window)


def test_no_worker_hands_its_field_to_a_blind_lambda() -> None:
    """Kein ``finished``-Signal räumt eine Arbeiter-Referenz per ``setattr``.

    Das Muster war fünfmal richtig und zweimal falsch, und niemand konnte es
    sehen: die drei Slots der Sitzung und die Update-Abfrage tragen sogar den
    Kommentar, warum ein Lambda hier nicht geht — der Schnitt-Arbeiter und die
    Ollama-Abfrage benutzten trotzdem eines.

    ``lambda: setattr(self, "_worker", None)`` schreibt in das *Feld*, nicht
    zum *Arbeiter*: Wird ein Vorgänger fertig, nachdem sein Nachfolger im Feld
    steht, verliert der laufende Nachfolger seine einzige Referenz. Dazu kommt
    ``finished`` ohnehin zu früh — Qt räumt den Thread danach noch ab.

    Ein Test über den Quelltext und nicht über das Verhalten, weil der Absturz
    am Timing hängt und sich nicht verlässlich herbeiführen lässt. Eine
    Konvention, die nirgends geprüft wird, ist keine.
    """
    import re

    ui = Path(__file__).parent.parent / "app" / "ui"
    pattern = re.compile(r"finished\.connect\(\s*lambda[^)]*setattr", re.MULTILINE)

    culprits = [
        path.relative_to(ui.parent.parent)
        for path in sorted(ui.glob("*.py"))
        if pattern.search(path.read_text(encoding="utf-8"))
    ]

    assert not culprits, (
        f"{culprits}: ein benannter Slot prüft die Identität seines Arbeiters, "
        "ein Lambda trifft blind das Feld — siehe .claude/rules/wartezeit.md"
    )


def test_the_splash_screen_prints_the_mark_along_the_real_progress(qt_app: object) -> None:
    """Der Ladebildschirm zeigt den gemessenen Fortschritt, nicht eine Uhr.

    Geprüft wird die Zusicherung aus dem Modul: ``step`` setzt das Ziel, und
    die gezeigte Höhe nähert sich ihm an, statt zu springen. Ein Balken, der
    unabhängig vom Laden läuft, wäre eine Behauptung — dieser hier ist eine
    Anzeige.
    """
    from app.ui.splash import SplashScreen

    splash = SplashScreen()
    try:
        assert splash._shown == 0.0, "vor dem ersten Schritt ist nichts gedruckt"

        splash.step("Operationen werden geladen …", 0.5)
        assert splash._target == 0.5
        assert splash._message == "Operationen werden geladen …"
        # Angenähert, nicht gesprungen: nach einem Schritt liegt die Anzeige
        # zwischen Start und Ziel.
        assert 0.0 <= splash._shown < 0.5

        # Ausreißer nach oben und unten werden auf den gültigen Bereich
        # geklemmt — ein Aufrufer, der sich verzählt, verzerrt das Bild nicht.
        splash.step("zu weit", 1.8)
        assert splash._target == 1.0
        splash.step("zu wenig", -0.3)
        assert splash._target == 0.0
    finally:
        splash.finish()


def test_the_splash_screen_survives_a_missing_icon_source(
    qt_app: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne SVG-Quelle zeichnet er nichts, statt den Start zu verlieren.

    Das Startbild ist Zierde; ein Start scheitert nie daran. Dieselbe Haltung
    hat ``application_icon`` — fehlt die Datei, gibt es ein leeres Symbol.
    """
    from app.ui import splash as splash_module

    monkeypatch.setattr(splash_module, "application_icon_source", lambda: "")
    splash = splash_module.SplashScreen()
    try:
        splash.step("ohne Bild", 0.4)
        assert not splash._renderer.isValid()
        splash.repaint()  # darf nicht werfen
    finally:
        splash.finish()


# --- die Wartezeit beim Öffnen (§2.8) --------------------------------------------


def test_the_veil_covers_the_view_only_while_it_shows_nothing(window: MainWindow) -> None:
    """§2.8: die letzte gültige Darstellung bleibt stehen.

    Der Balken unten rechts war beim Öffnen eines Projekts die einzige
    Auskunft, und er steht dort, wo beim Warten niemand hinsieht. Über die
    leere Ansicht gehört eine Anzeige — über ein Modell nicht: was man gerade
    ansieht, wird nicht verdeckt, nur weil dahinter gerechnet wird.
    """
    window._on_busy(True)
    assert window.veil.showing, "die leere Ansicht bekommt die Anzeige"

    window._on_busy(False)
    assert not window.veil.showing, "und gibt sie nach dem Lauf wieder her"

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window._on_scene(window.session.evaluate_now())

    window._on_busy(True)
    assert not window.veil.showing, "über einem Körper bleibt die Ansicht die Ansicht"


def test_the_veil_hides_the_native_view_while_it_stands(window: MainWindow) -> None:
    """Verborgen, nicht nur verdeckt (§2.8).

    Die Ansicht ist ein natives Fenster (die Grafikfläche des Renderers): auf
    dem Bildschirm liegt es über jedem gemalten Geschwister, egal was die
    Qt-Stapelung sagt — und
    solange es nie gerendert hat, zeigt es alte Pixel. Beim Öffnen von Weg 1
    stand deshalb sechs Sekunden der Startbildschirm bzw. Schwarz, während
    der Schleier unsichtbar darunter lag; Robert hielt es zweimal für einen
    Absturz. Der ``childAt``-Test daneben sah davon nichts: er fragt die
    Stapelung, nicht den Bildschirm.
    """
    # ``isHidden`` und nicht ``isVisibleTo``: gefragt ist die ausdrückliche
    # Verbergung — der Stapel zeigt im frischen Fenster den Startbildschirm,
    # und dahinter ist jede Sichtbarkeitskette folgenlos False.
    window._on_busy(True)
    assert window.veil.showing
    assert window.middle_stack.isHidden(), (
        "die native Ansicht muss weg sein, solange der Schleier steht"
    )

    window._on_busy(False)
    assert not window.veil.showing
    assert not window.middle_stack.isHidden(), "mit dem Ende des Schleiers kommt die Ansicht zurück"


def test_reading_a_file_says_so_while_the_window_stays_free(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§2.8: Das Lesen eines Modells hat eine Auskunft und belegt das Fenster nicht.

    Bis RM-224 las die Sitzung die Datei synchron unter dem Wartezeiger; die
    Ladeanzeige deckt das Lesen nicht, und dazwischen lag ein Fenster ohne
    jede Auskunft. Seither liest ein Arbeiter (``Session._ReadWorker``): Die
    Statuszeile nennt den Vorgang, die Sitzung meldet sich beschäftigt, und
    ein Wartezeiger steht nirgends — das Fenster ist dabei bedienbar.
    """
    seen: list[tuple[Any, str]] = []
    real = window.session.import_model_async

    def watched(path: Path, *args: Any, **kwargs: Any) -> Any:
        seen.append((QApplication.overrideCursor(), window.status_message.text()))
        return real(path, *args, **kwargs)

    monkeypatch.setattr(window.session, "import_model_async", watched)

    window.open_path(MESHES / "cube_clean.stl")
    reading = window.session.busy
    held = QApplication.overrideCursor()
    window.session.wait_for_idle()

    assert seen, "gelesen wurde nichts — der Test misst am falschen Ort"
    cursor, status = seen[0]
    assert status == tr("Modell einfügen …"), "die Statuszeile erklärt den Vorgang nicht"
    assert cursor is None and held is None, "ein Wartezeiger stünde über einem freien Fenster"
    assert reading, "gelesen wird im Arbeiter, und die Sitzung sagt es"
    assert [entry.op for entry in window.session.project.document.ops] == ["load"]


def test_cancelling_frees_the_window_while_the_drive_still_reads(
    window: MainWindow, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """*Abbrechen* gilt sofort, auch wenn das Laufwerk nicht antwortet.

    Ein ``stat`` oder ``read`` lässt sich nicht unterbrechen; bis zur
    Durchsicht 0.5.1 galt der Klick erst, wenn das System aufgab — gemessen
    mit einem um 8 s verzögerten Lesen: frei nach 6,1 s. Gelesen wird seither
    in einem Daemon-Faden, und der Arbeiter endet auf den Klick.
    """
    from app.ui import session as session_module

    release = threading.Event()
    real = session_module.read_local_payload

    def hanging(path: Path) -> bytes:
        release.wait(30)
        return real(path)

    monkeypatch.setattr(session_module, "read_local_payload", hanging)
    finished: list[bool] = []
    window.session.importFinished.connect(finished.append)
    try:
        window.open_path(MESHES / "cube_clean.stl")
        assert window.session.busy, "gelesen wird im Arbeiter"
        window.session.cancel_evaluation()
        started = time.monotonic()
        while window.session.busy and time.monotonic() - started < 5:
            qt_app.processEvents()
            time.sleep(0.01)
        freed = time.monotonic() - started
        assert not window.session.busy, "der Klick wartete auf das Laufwerk"
        assert freed < 2.0, f"frei erst nach {freed:.1f} s"
        assert finished == [False], "der abgebrochene Import meldet sich als nicht angenommen"
        assert not window.session.project.document.ops, "eingebettet wurde nichts"
    finally:
        release.set()
    # Die späte Antwort des Laufwerks verfällt, und ein neuer Import geht durch.
    qt_app.processEvents()
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle()
    assert [entry.op for entry in window.session.project.document.ops] == ["load"]


def test_a_project_on_a_slow_drive_does_not_stop_the_window(
    window: MainWindow, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Das Fenster malt weiter, während eine Projektdatei von einem langsamen Laufwerk kommt.

    ``load`` lief im Hauptfaden: Um 5 s verzögertes Lesen hielt das Fenster
    5,1 s an (Durchsicht 0.5.1). Gelesen wird daneben; Zeitgeber laufen
    weiter, Eingaben nicht — das Öffnen bleibt ein Schritt.
    """
    from PySide6.QtCore import QTimer

    from app.core.scene.project import save
    from app.ui import session as session_module

    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle()
    target = save(window.session.project, tmp_path / "langsam.p3d")
    real = session_module.load

    def slow(path: Path) -> Any:
        time.sleep(0.4)
        return real(path)

    monkeypatch.setattr(session_module, "load", slow)
    ticks: list[int] = []
    QTimer.singleShot(100, lambda: ticks.append(1))
    window.session.open_project(target)
    assert ticks, "während des Lesens lief kein Zeitgeber — der Hauptfaden stand"
    assert window.session.path == target


def test_a_moved_project_leads_to_open_and_a_moved_model_to_insert(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """*Andere Datei wählen* nimmt den Weg, der scheiterte (Durchsicht 0.5.1).

    Ein Projekt sucht man unter *Öffnen*, ein Modell unter *Einfügen*; bis
    dahin führte jede Absage zu *Einfügen*.
    """
    from app.core.errors import UserError

    called: list[str] = []
    monkeypatch.setattr(window, "action_open", lambda: called.append("open"))
    monkeypatch.setattr(window, "action_import", lambda: called.append("import"))
    handler = window.error_handlers()["choose_another_file"]
    handler(UserError("x", values={"path": "werkstatt.p3d"}))
    handler(UserError("x", values={"path": "halter.stl"}))
    handler(UserError("x"))
    assert called == ["open", "import", "import"]


def test_the_autosave_writes_beside_the_window_and_says_when_it_cannot(
    window: MainWindow, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die automatische Sicherung hält das Fenster nicht an und schweigt nicht (RM-233).

    Sie schrieb im Zeitgeber des Hauptfadens — am Mausoleum-Drachen 0,8 bis
    1,0 s Stillstand alle zwei Minuten —, und ein Schreibfehler warf in diesem
    Slot, wo ihn niemand sah (Durchsicht 0.5.1).
    """
    from app.core.errors import FileWriteError
    from app.ui import session as session_module

    threads: list[bool] = []
    real = session_module.write_autosave

    def watched(project: Any, path: Any, token: Any = None) -> Any:
        threads.append(threading.current_thread() is threading.main_thread())
        return real(project, path, token)

    monkeypatch.setattr(session_module, "write_autosave", watched)
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle()
    assert window.session.modified
    window._autosave.timeout.emit()
    assert window.session.wait_for_idle()
    qt_app.processEvents()
    assert threads == [False], "geschrieben wird im Arbeiter"

    def refusing(project: Any, path: Any, token: Any = None) -> Any:
        raise FileWriteError(target="x.autosave", detail="Kein Platz")

    monkeypatch.setattr(session_module, "write_autosave", refusing)
    for _round in range(2):
        window._autosave.timeout.emit()
        assert window.session.wait_for_idle()
        qt_app.processEvents()
    said = tr(
        "Die automatische Sicherung ließ sich nicht schreiben — prüfen Sie den "
        "freien Speicherplatz und speichern Sie das Projekt selbst."
    )
    assert window._announcement == said, "der Fehler kam nicht beim Kunden an"
    window.announce("")
    window._autosave.timeout.emit()
    assert window.session.wait_for_idle()
    qt_app.processEvents()
    assert window._announcement == "", "einmal je Sitzung, nicht alle zwei Minuten"


def test_a_backup_that_finishes_after_saving_is_cleared(
    window: MainWindow, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Eine Sicherung, die nach dem Speichern fertig wird, böte sich sonst beim Start an."""
    from app.core.scene.project import autosave_path
    from app.ui import session as session_module

    release = threading.Event()
    real = session_module.write_autosave

    def slow(project: Any, path: Any, token: Any = None) -> Any:
        release.wait(10)
        return real(project, path, token)

    monkeypatch.setattr(session_module, "write_autosave", slow)
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle()
    target = tmp_path / "gespeichert.p3d"
    token = window.session.recovery_token
    window.session.autosave_async()
    window.session.save_project(target)
    release.set()
    assert window.session.wait_for_idle()
    qt_app.processEvents()
    assert not autosave_path(None, token).exists(), "die späte Sicherung blieb liegen"
    assert not autosave_path(target).exists()


def test_a_recent_file_that_vanished_leaves_the_list_after_the_attempt(
    window: MainWindow, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ein Eintrag, dessen Datei seit dem Start verschwand, bleibt nicht stehen.

    „Zuletzt geöffnet“ prüft beim Aufbau; wer danach verschob und klickte, bekam
    den Hinweis — und denselben toten Eintrag wieder angeboten (Durchsicht 0.5.1).
    """
    monkeypatch.setattr(main_window_module, "show_error", lambda *args, **kwargs: None)
    moved = tmp_path / "verschoben.stl"
    moved.write_bytes((MESHES / "cube_clean.stl").read_bytes())
    window.settings.recent = [str(moved)]
    window._show_recent()
    qt_app.processEvents()
    assert window.start_screen.recent_list.count() == 1
    moved.unlink()
    window.open_path(moved)
    assert window.session.wait_for_idle()
    for _round in range(20):
        qt_app.processEvents()
        if window.start_screen.recent_list.count() == 0:
            break
        time.sleep(0.02)
    assert window.start_screen.recent_list.count() == 0, "der tote Eintrag steht weiter da"


def test_a_file_without_a_model_leaves_no_step_and_no_recent_entry(
    window: MainWindow, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Eine Datei, die am Ladeschritt scheitert, wird kein Schritt 1 (KUNDE-12).

    Vorher: leerer Arbeitsbereich, „Die Kette hält an“, jede weitere Datei mit
    einem Dialog abgewiesen, und die kaputte stand in „Zuletzt geöffnet“.
    """
    shown: list[Any] = []
    monkeypatch.setattr(
        main_window_module, "show_error", lambda error, *a, **k: shown.append(error)
    )
    broken = tmp_path / "kaputt.stl"
    broken.write_bytes(b"solid x\n facet normal 0 0 1\n  outer loop\n   vertex 0 0 nope\n" * 3)
    window.open_path(broken)
    for _round in range(200):
        assert window.session.wait_for_idle()
        qt_app.processEvents()
        if shown and not window.session.busy:
            break
    assert [str(error.title) for error in shown] == [tr("Diese Datei ließ sich nicht lesen.")]
    assert "choose_another_file" in [action.id for action in shown[0].suggestions]
    assert not window.session.project.document.ops
    assert window.stack.currentWidget() is window.start_screen
    assert str(broken) not in window.settings.recent

    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle()
    qt_app.processEvents()
    assert len(shown) == 1, "die nächste Datei wird angenommen"
    assert len(window.session.last_result.scene.objects) == 1
    assert str(MESHES / "cube_clean.stl") in window.settings.recent


def test_a_resize_before_the_toolbar_exists_does_not_end_the_start(qt_app: QApplication) -> None:
    """Eine Größenänderung mitten im Aufbau beendet den Start nicht (RM-238).

    Der Renderer fragt beim Bau der Ansicht nach seinem nativen Fenster, und
    bei doppelter Skalierung auf einem 1440er Schirm kam dabei ein
    ``resizeEvent`` ans Hauptfenster, bevor es eine Werkzeugleiste hatte —
    ``AttributeError``, kein Fenster (Durchsicht 0.5.1, ``QT_SCALE_FACTOR=2``).
    """
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QResizeEvent

    class HalfBuilt(MainWindow):
        def __init__(self) -> None:
            # Nur der Qt-Teil, wie mitten im Aufbau.
            QtWidgets.QMainWindow.__init__(self)

    early = HalfBuilt()
    try:
        early.resizeEvent(QResizeEvent(QSize(800, 600), QSize(640, 480)))
    finally:
        # Gleich löschen, nicht erst im Abbau der Suite: Der fragt jedes
        # Hauptfenster nach ``release``, und ein halb gebautes hat nichts zum
        # Loslassen — es endete dort mit ``AttributeError`` (``_ask_dialog``).
        early.deleteLater()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def test_the_window_title_names_the_model_once_it_is_read(window: MainWindow) -> None:
    """Die Titelleiste sagt denselben Namen wie Kopfzeile und Baum.

    ``session.title`` leitet ihn aus dem Ergebnis ab; gesetzt wurde die
    Titelleiste nur beim Dokumentwechsel, also vor der Auswertung — nach dem
    Einlesen stand oben „Unbenannt“ (Durchsicht 0.5.1).
    """
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle()
    QApplication.processEvents()
    assert window.windowTitle().startswith("cube_clean"), window.windowTitle()


@pytest.mark.parametrize("starting_fresh", [False, True])
def test_import_dialog_keeps_its_reading_status_after_starting_the_project(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, starting_fresh: bool
) -> None:
    """Auch der Dateidialog bewahrt den Ladehinweis über den Projektanfang."""
    from PySide6.QtWidgets import QFileDialog

    window._show_start_screen(starting_fresh)
    window.announce("Bereit")
    seen: list[tuple[Any, str, str]] = []
    real = window.session.import_model_async

    def watched(path: Path, *args: Any, **kwargs: Any) -> Any:
        seen.append(
            (
                QApplication.overrideCursor(),
                window.status_message.text(),
                window._announcement,
            )
        )
        return real(path, *args, **kwargs)

    monkeypatch.setattr(window.session, "import_model_async", watched)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(MESHES / "cube_clean.stl"), "")),
    )

    window.action_import()
    window.session.wait_for_idle()

    assert seen, "gelesen wurde nichts — der Test misst am falschen Ort"
    cursor, status, announcement = seen[0]
    # Gelesen wird seit RM-224 im Arbeiter; ein Wartezeiger stünde über einem
    # freien Fenster (``test_reading_a_file_says_so_while_the_window_stays_free``).
    assert cursor is None
    assert status == tr("Modell einfügen …"), "der Projektanfang löschte den Ladehinweis"
    expected = "" if starting_fresh else "Bereit"
    assert announcement == expected, "nur ein neues Dokument verwirft die vorige Quittung"
    assert window._announcement == expected
    assert QApplication.overrideCursor() is None, "der Wartezeiger blieb stehen"


def test_a_broken_file_takes_the_wait_cursor_with_it(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Wartezeiger, der nach einem Fehler stehen bleibt, sieht aus wie ein
    hängendes Programm — und der Fehlerdialog darunter wie ein Fenster, das
    zugleich fragt und bittet zu warten."""

    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise errors.UserError(title="Diese Datei ließ sich nicht lesen.")

    shown: list[Any] = []
    # **Der Fehler entsteht jetzt dort, wo er hingehört.** Gepatcht wird
    # der Planer, nicht die Sitzungsmethode: So läuft der echte Weg samt
    # ``importFailed``, und der Test prüft, was der Kunde bekommt, statt
    # was eine ersetzte Methode geworfen hätte.
    monkeypatch.setattr("app.ui.session.import_plan", refuse)
    monkeypatch.setattr(
        "app.ui.main_window.show_error", lambda error, *args, **kwargs: shown.append(error)
    )

    window.open_path(MESHES / "cube_clean.stl")
    # Gelesen und geplant wird im Arbeiter (RM-224); der Fehler kommt danach.
    window.session.wait_for_idle()

    assert shown, "der Fehler kam nirgends an"
    assert QApplication.overrideCursor() is None, "der Wartezeiger überlebte den Fehler"


def test_a_rejected_file_restores_status_before_showing_the_error(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine Abweisung aus ``History.apply`` darf nicht als ewiges Laden enden."""
    window._show_start_screen(False)
    window.announce("Bereit")

    def refusing(*_args: object, **_kwargs: object) -> object:
        raise errors.UserError(detail="der Schritt wurde abgewiesen")

    shown: list[tuple[Any, Any, str]] = []
    monkeypatch.setattr(window.session.history, "apply", refusing)
    monkeypatch.setattr(
        "app.ui.main_window.show_error",
        lambda error, *_args, **_kwargs: shown.append(
            (error, QApplication.overrideCursor(), window.status_message.text())
        ),
    )

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()

    assert shown, "die Abweisung kam nirgends an"
    _error, cursor, status = shown[0]
    assert cursor is None, "der Fehler erschien noch unter dem Wartezeiger"
    assert status == "Bereit", "der Ladehinweis blieb hinter dem Fehler stehen"
    assert window.status_message.text() == "Bereit"
    assert not window.session.project.document.sources


def test_the_veil_shows_the_measured_progress(window: MainWindow) -> None:
    """Bauhöhe, Linie und Zahl sagen dasselbe — die Zahl das Gemessene.

    Regel 18 gilt auch für eine Wartezeit: die Höhe des gedruckten Symbols
    ist die eine Kodierung, die Länge der Linie die zweite, die Prozentzahl
    die dritte. Angenähert wird nur die Anzeige, nie die Auskunft.
    """
    window._on_busy(True)
    window._on_progress(0.5, "Bohrung")

    assert window.veil._target == 0.5
    assert window.veil._detail == "Bohrung"
    # Offscreen wird nicht animiert, sonst prüfte der Test die Uhr.
    assert window.veil._shown == 0.5

    window._on_progress(1.8, "verzählt")
    assert window.veil._target == 1.0, "ein Ausreißer verzerrt das Bild nicht"


def test_the_veil_leaves_the_toolbar_reachable(window: MainWindow) -> None:
    """Verdeckt wird die Ansicht, nicht die Bedienung.

    Über den Karten wäre der Schleier ein Vorhang ohne Ausgang: die
    Werkzeugzeile läge darunter, und wer den Lauf abbrechen oder das Fenster
    weiterbedienen will, käme nicht hin. Gemessen wird das wie beim Umbau auf
    schwebende Karten — mit ``childAt`` an der Stelle, an der die Zeile steht.
    """
    from app.ui.overlay import MARGIN

    window.overlay.setGeometry(0, 0, 1200, 800)
    window.overlay._place()
    window._on_busy(True)
    assert window.veil.showing

    bottom = window.overlay.bottom
    assert bottom is not None
    on_the_bar = bottom.geometry().center()
    assert window.overlay.childAt(on_the_bar) is not window.veil

    # Und dort, wo nur die Ansicht liegt, steht er.
    empty = QPoint(600, 800 - MARGIN - bottom.height() - 40)
    assert window.overlay.childAt(empty) is window.veil

    window._on_busy(False)


def test_the_veil_says_whether_a_model_or_a_project_is_coming(window: MainWindow) -> None:
    """Die Überschrift über der leeren Ansicht sagt, worauf gewartet wird.

    Wer eine STL einfügt, wartet nicht auf ein Projekt. Gemessen am
    13.09.2026: einundzwanzig Sekunden „Projekt wird geladen …" quer über das
    Fenster, während die Statuszeile daneben „Modell einfügen" meldete. Der
    Merker überlebt dabei das Ende des Einlesens — ausgewertet und erkannt
    wird danach noch, und die Anzeige steht so lange.
    """
    window._on_busy(True)
    assert window.veil._headline == str(tr("Projekt wird geladen …"))
    window._on_busy(False)

    window._loading_model = True
    window._on_busy(True)
    assert window.veil._headline == str(tr("Modell wird gelesen"))

    window._on_busy(False)
    assert not window._loading_model, "das Ende der Anzeige räumt den Merker"

    # Vom Startbildschirm aus steht schon das leere Ergebnis des neuen
    # Projekts da; das Modell gewinnt trotzdem (Durchsicht 0.5.1 — sonst stand
    # „Wird berechnet …“ über dem Import, „Modell einfügen“ in der Zeile).
    window.session.evaluate_now()
    assert window.session.last_result is not None
    window._loading_model = True
    window._on_busy(True)
    assert window.veil._headline == str(tr("Modell wird gelesen"))
    window._on_busy(False)


def test_the_veil_can_be_cancelled(window: MainWindow) -> None:
    """Der Schleier gehört der Auswertung und hält keine parallele Aufgabe an."""
    split_worker = _RunningSplit()
    window.session._split = split_worker
    window._on_busy(True)
    window.veil.cancel.click()

    assert window.session.cancel_signal.is_cancelled
    assert not window.session.agent_cancel.is_cancelled
    assert not split_worker.cancel.is_cancelled
    window.session._split = None
    window._on_busy(False)


def test_a_cancelled_run_says_that_it_was_cancelled(window: MainWindow) -> None:
    """Ein abgebrochener Lauf sah aus wie ein fertiger.

    Balken weg, Knopf weg, dieselbe Ansicht wie vorher — das erfuhr bisher nur
    die Logdatei. Wer nicht mitgezaehlt hat, konnte nicht wissen, ob sein Klick
    etwas bewirkt hat und ob das Bild vor ihm das Ergebnis ist oder ein alter
    Stand. Der Satz nennt deshalb beides (§2.8).
    """
    window.session.cancel()
    window.session._on_cancelled()

    assert "Abgebrochen" in window.status_message.text()
    assert "letzte" in window.status_message.text(), "der Stand gehoert dazu, nicht nur das Ende"

    # Und er ueberlebt das naechste Ereignis: ``_on_busy`` schreibt die Ansage
    # zurueck, und eine Meldung, die dabei verschwindet, war fuer den, der
    # gerade woanders hinsah, nie da.
    window._on_busy(False)
    assert "Abgebrochen" in window.status_message.text()


def test_replacing_a_run_is_not_an_interruption(window: MainWindow) -> None:
    """Eine neuere Anfrage bricht die laufende ab — das ist Ersetzen, kein
    Aufhoeren.

    Es zu melden hiesse, beim Ziehen an einem Schieber im Sekundentakt
    „abgebrochen" in die Statuszeile zu schreiben. Unterschieden wird an der
    Herkunft: ``cancel()`` kommt von einem Menschen, ``evaluate_async`` von
    der naechsten Zahl.
    """
    vorher = window.status_message.text()
    window.session.cancel_signal.cancel()  # wie es ``evaluate_async`` tut
    window.session._on_cancelled()

    assert window.status_message.text() == vorher, "ein Ersetzen sagt nichts"


def test_saving_shows_that_it_is_working(window: MainWindow, tmp_path) -> None:
    """Speichern ist keine Handlung ohne Dauer.

    Gemessen: 903 ms fuer ein Projekt mit einem 62-MiB-Netz, und das ohne
    jedes Zeichen — nach §2.8 die mittlere Stufe, Mauszeiger und Statusleiste,
    und beide fehlten. Wer *Speichern* drueckte, sah ein Fenster, das nicht
    reagiert.

    Geprueft wird der Zeiger waehrend des Schreibens, nicht danach: Ein Test,
    der erst hinterher hinsieht, findet immer einen aufgeraeumten Zustand und
    haette auch ohne die Aenderung bestanden.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    gesehen: list[object] = []
    echtes_speichern = window.session.save_project

    def merken(path):
        zeiger = QApplication.overrideCursor()
        gesehen.append(zeiger.shape() if zeiger is not None else None)
        gesehen.append(window.status_message.text())
        return echtes_speichern(path)

    window.session.save_project = merken  # type: ignore[method-assign]
    window._save_to(tmp_path / "projekt.solidon")

    assert gesehen[0] == Qt.CursorShape.WaitCursor, "waehrend des Schreibens fehlt der Wartezeiger"
    assert "gespeichert" in str(gesehen[1]), f"die Zeile sagt nichts: {gesehen[1]!r}"
    assert QApplication.overrideCursor() is None, "und danach ist er wieder weg"
    assert "Gespeichert" in window.status_message.text()


def test_motion_is_off_where_nobody_watches(qt_app: object) -> None:
    """Offscreen wird nicht animiert — sonst prüft ein Test die Uhr.

    Die Suite läuft unter ``QT_QPA_PLATFORM=offscreen`` (conftest, §38). Dort
    darf keine Animation starten: ein Widget, das erst nach 140 ms sichtbar
    ist, macht aus jeder Zusicherung eine Wette auf das Timing.
    """
    from app.ui import motion

    assert not motion.animations_enabled()


def test_switching_a_stack_arrives_immediately(qt_app: object) -> None:
    """Der Wechsel gilt sofort, animiert wird nur das Auftauchen.

    Das ist die Zusicherung, auf der alle Aufrufer stehen: Wer direkt nach
    ``switch`` auf ``currentWidget`` sieht, bekommt die neue Seite — nicht die
    alte, weil eine Blende noch läuft.
    """
    from PySide6.QtWidgets import QStackedWidget, QWidget

    from app.ui.motion import switch

    stack = QStackedWidget()
    first, second = QWidget(), QWidget()
    stack.addWidget(first)
    stack.addWidget(second)
    stack.setCurrentWidget(first)

    switch(stack, second)
    assert stack.currentWidget() is second

    # Zweimal dasselbe Ziel ist kein Wechsel und löst auch keine Blende aus.
    switch(stack, second)
    assert stack.currentWidget() is second


def test_fading_leaves_no_effect_behind(qt_app: object) -> None:
    """Nach der Blende hängt kein Deckkraft-Effekt mehr am Widget.

    Ein ``QGraphicsOpacityEffect`` kostet bei jedem Zeichnen eine eigene
    Zwischenfläche. Bliebe er stehen, zahlte der Viewport ihn für den Rest der
    Sitzung — und zwei übereinander machen das Widget dauerhaft blasser.
    """
    from PySide6.QtWidgets import QWidget

    from app.ui.motion import fade_in, fade_out

    widget = QWidget()
    fade_in(widget)
    assert widget.isVisible() or widget.isHidden() is False
    assert widget.graphicsEffect() is None

    fade_out(widget)
    assert not widget.isVisible()
    assert widget.graphicsEffect() is None


def test_the_application_icon_uses_the_small_source_where_it_matters(qt_app: object) -> None:
    """Bis 32 Pixel kommt die vereinfachte Version, darüber die ausgearbeitete.

    Das ist die Größe von Titelleiste, Taskleiste, Alt-Tab — und dieselbe in
    jedem Dialog, weil das Symbol einmal auf der ``QApplication`` steht und
    jedes Fenster es erbt. Die ausgearbeitete Version trägt dort Schichtlinien
    von 0,3 Pixeln Breite und kommt als grauer Schleier an.

    Die beiden Versionen sind **dieselbe Form** — gleiche Punkte, gleiche
    Farben. Der einzige Unterschied sind die Schichtlinien, und genau darauf
    prüft dieser Test: Wer die kleine Version neu gestaltet statt sie zu
    vereinfachen, bekommt zwei Symbole für ein Produkt.
    """
    from PySide6.QtCore import QSize

    from app.ui.icons import ICON_SOURCE, ICON_SOURCE_SMALL, SMALL_ICON_LIMIT, application_icon

    assert ICON_SOURCE.exists(), "die ausgearbeitete Quelle fehlt"
    assert ICON_SOURCE_SMALL.exists(), "die vereinfachte Quelle fehlt"

    icon = application_icon()
    assert not icon.isNull()
    assert not icon.pixmap(QSize(16, 16)).isNull()
    assert SMALL_ICON_LIMIT == 32

    large = ICON_SOURCE.read_text(encoding="utf-8")
    small = ICON_SOURCE_SMALL.read_text(encoding="utf-8")

    # Die Schichtlinien sind das Einzige, was fehlen darf — sie stehen als
    # <path> da, alles andere als <polygon> oder <ellipse>.
    assert "<path" in large, "die große Version hat ihre Schichtlinien verloren"
    assert "<path" not in small, "die kleine Version trägt Linien, die bei 16 px zu Schleier werden"

    # Dieselben Flächen, dieselben Farben: Was hier auseinanderläuft, sieht der
    # Nutzer als zwei verschiedene Symbole.
    for shape in ('points="64,18 104,41 64,64 24,41"', 'fill="#e08b4e"', 'fill="#7c3a10"'):
        assert shape in large and shape in small, f"{shape} steht nicht in beiden Versionen"


def test_no_window_overrides_the_application_icon() -> None:
    """Das Fenstersymbol wird einmal gesetzt, und alle erben es.

    Setzte ein Dialog ein eigenes, hätte er in seiner Titelleiste ein anderes
    Bild als das Hauptfenster — und die Korrektur an der einen Stelle ginge an
    ihm vorbei. Ein Test über den Quelltext, weil sich das Erben nicht
    offscreen nachstellen lässt.
    """
    import re

    ui = Path(__file__).parent.parent / "app" / "ui"
    pattern = re.compile(r"^\s*(?!application\b)\w+\.setWindowIcon\(", re.MULTILINE)

    culprits = [
        path.relative_to(ui.parent.parent)
        for path in sorted(ui.glob("*.py"))
        if pattern.search(path.read_text(encoding="utf-8"))
    ]

    assert not culprits, (
        f"{culprits}: das Fenstersymbol gehört einmal auf die QApplication "
        "(app/ui/app.py), nicht an einzelne Fenster"
    )


# --- Modell aus dem Netz (§16.3) ------------------------------------------------


class _Drag:
    """Ein Ablegen-Ereignis mit Adressen, wie es ein Browser schickt.

    Als eigene Klasse und nicht als echtes ``QDropEvent``: Qt übernimmt die
    ``QMimeData`` nicht, und ohne eine Referenz auf der Python-Seite gibt der
    Speicherbereiniger sie frei, während das Ereignis noch darauf zeigt —
    ``mimeData()`` liefert dann ein blankes ``QObject``. Derselbe Fake steht
    aus demselben Grund in ``test_chat_ui.py``.
    """

    def __init__(self, urls: list[str]) -> None:
        from PySide6.QtCore import QMimeData, QUrl

        self._data = QMimeData()
        self._data.setUrls([QUrl(entry) for entry in urls])
        self.accepted = False

    def mimeData(self) -> object:  # noqa: N802 — Qt gibt den Namen
        return self._data

    def acceptProposedAction(self) -> None:  # noqa: N802 — bildet die Qt-API nach
        self.accepted = True


def _drag(urls: list[str]) -> Any:
    return _Drag(urls)


def test_a_dropped_link_is_taken_like_a_dropped_file(tmp_path: Path) -> None:
    """§2.3: Ziehen und Ablegen gilt auch für einen Verweis aus dem Browser.

    **Auch der Verweis auf eine Modellseite** (22.09.2026): Er bekam beim
    Ziehen ein Verbotszeichen und keinen Satz. Angenommen wird jede
    Web-Adresse; was dahinter liegt, sagt der Kern — für eine Modellseite der
    Weg über ihren Herunterladen-Knopf.
    """
    from app.ui.start_screen import accepted_path, accepted_url

    assert accepted_url(_drag(["https://example.invalid/halter.stl"])) is not None
    assert accepted_url(_drag(["https://www.printables.com/model/3161-3d-benchy"])) is not None
    assert accepted_url(_drag(["https://example.invalid/modelle/17"])) is not None
    assert accepted_url(_drag(["file:///C:/teil.stl"])) is None, "das ist der Weg für Dateien"
    assert accepted_url(_drag(["ftp://example.invalid/teil.stl"])) is None
    assert accepted_path(_drag([(tmp_path / "teile.zip").as_uri()])) is not None, (
        "ein ZIP von der Modellseite geht wie eine Datei"
    )


def test_a_dropped_model_page_says_where_the_file_is(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Satz statt des Verbotszeichens — und ohne Anfrage ins Netz."""
    shown: list[errors.AppError] = []
    monkeypatch.setattr("app.ui.main_window.show_error", lambda error, _parent: shown.append(error))
    drop = _drag(["https://www.thingiverse.com/thing:763622"])

    window.dropEvent(drop)  # type: ignore[arg-type]

    assert drop.accepted
    assert window._download_worker is None, "keine Anfrage an eine Seite hinter einer Bot-Prüfung"
    assert shown and shown[0].values["constraint"] == "web_page"
    assert "Herunterladen" in str(shown[0].detail)


def test_a_zip_with_several_models_asks_and_imports_the_chosen_one(
    session: Session, qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Archiv wird vor dem Einbetten aufgelöst; die Wahl geht über den Frageweg."""
    import io
    import zipfile

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as container:
        container.writestr("teile/boden.stl", (MESHES / "cube_clean.stl").read_bytes())
        container.writestr("teile/deckel.stl", (MESHES / "cube_clean.stl").read_bytes())
        container.writestr("foto.jpg", b"JFIF")
    asked: list[list[str]] = []

    def answer(_question: str, choices: list[str]) -> str:
        asked.append(choices)
        return "teile/deckel.stl"

    monkeypatch.setattr(session, "ask_from_worker", answer)
    finished: list[bool] = []
    session.importFinished.connect(finished.append)

    session.import_payload_async("teile.zip", buffer.getvalue(), unit="mm")
    worker = session._plan
    assert worker is not None and worker.wait(10_000)
    for _round in range(5):
        qt_app.processEvents()
    assert session.wait_for_idle(30_000)

    assert asked == [["teile/boden.stl", "teile/deckel.stl"]]
    sources = session.project.document.sources
    assert any(source.path.endswith("deckel.stl") for source in sources.values()), sources
    assert not any(source.path.endswith(".zip") for source in sources.values())
    assert session.history.operations and session.history.operations[-1].op == "load"


def test_a_part_file_drop_reaches_open_path_but_json_does_not(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das ganze Fenster teilt den exakten lokalen Dateivertrag der Startfläche."""
    opened: list[Path] = []
    monkeypatch.setattr(window, "open_path", opened.append)
    part = tmp_path / "halter.solidon-part"
    generic = tmp_path / "halter.json"

    part_drop = _drag([part.as_uri()])
    window.dropEvent(part_drop)  # type: ignore[arg-type]
    generic_drop = _drag([generic.as_uri()])
    window.dropEvent(generic_drop)  # type: ignore[arg-type]

    assert opened == [part]
    assert part_drop.accepted
    assert not generic_drop.accepted


def test_a_bad_address_says_so_before_a_worker_starts(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§32: Eine ``file:``-Adresse wandert gar nicht erst in einen Thread."""
    seen: list[object] = []
    monkeypatch.setattr("app.ui.main_window.show_error", lambda error, _parent: seen.append(error))

    window.download_model("file:///C:/Windows/win.ini")

    assert seen, "ohne Meldung bliebe der Klick wirkungslos"
    assert window._download_worker is None


def test_a_downloaded_model_keeps_where_it_came_from(window: MainWindow) -> None:
    """§16.3: Die Herkunft steht in der Quelle, nicht in einem Gedächtnis."""
    from app.core.ingest.fetch import FetchedModel

    payload = (MESHES / "cube_clean.stl").read_bytes()
    assert window.stack.currentWidget() is window.start_screen, "sonst prüft der Test unten nichts"
    window._downloaded(
        FetchedModel(
            name="halter.stl",
            payload=payload,
            url="https://example.invalid/halter.stl",
            retrieved="2026-08-11T10:00:00+00:00",
        )
    )
    window.session.wait_for_idle()

    sources = list(window.session.project.document.sources.values())
    assert len(sources) == 1
    assert sources[0].origin is not None
    assert sources[0].origin.url == "https://example.invalid/halter.stl"
    assert sources[0].origin.retrieved.startswith("2026-08-11")
    assert window.session.last_result is not None
    assert window.session.last_result.scene.objects, "das Modell steht danach in der Szene"
    assert window.stack.currentWidget() is not window.start_screen, (
        "geladen laut Statusleiste, unsichtbar im Bild: der Startbildschirm blieb stehen"
    )


def test_a_rejected_download_never_claims_success(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nach einer Abweisung bleibt der Start sichtbar und „Geladen“ aus."""
    from app.core.ingest.fetch import FetchedModel

    shown: list[object] = []
    received: list[dict[str, object]] = []

    def refusing(*_args: object, **kwargs: object) -> bool:
        received.append(kwargs)
        raise errors.UserError(detail="der Schritt wurde abgewiesen")

    # Wie beim Lesen von der Platte: gepatcht wird der Planer, damit der
    # echte Weg läuft und die Abweisung über ``importFailed`` ankommt.
    monkeypatch.setattr("app.ui.session.import_plan", refusing)
    monkeypatch.setattr(
        "app.ui.main_window.show_error", lambda error, *_args, **_kwargs: shown.append(error)
    )

    window._downloaded(
        FetchedModel(
            name="halter.stl",
            payload=b"solid",
            url="https://example.invalid/halter.stl",
            retrieved="2026-08-29T10:00:00+00:00",
        )
    )

    assert shown, "die Abweisung kam nirgends an"
    assert received, "der Planer wurde nicht gefragt"
    assert window.stack.currentWidget() is window.start_screen
    assert not window._announcement.startswith(tr("Geladen"))


def test_the_cards_grow_with_a_wide_window() -> None:
    """§19.3: Feste Breiten sind für 1920 gebaut.

    Auf 3413 Pixeln wurde die linke Karte zum Zwölftel des Fensters — die
    Maßspalte brach mitten in der Zahl ab, während daneben zwei Meter Leere
    standen. Gewachsen wird anteilig und mit Deckel; unter etwa 2000 Pixeln
    bleibt alles, wie es war.
    """
    from app.ui.overlay import LEFT_MAX, LEFT_WIDTH, card_width

    assert card_width(LEFT_WIDTH, LEFT_MAX, 1280) == LEFT_WIDTH
    assert card_width(LEFT_WIDTH, LEFT_MAX, 1920) == LEFT_WIDTH
    assert card_width(LEFT_WIDTH, LEFT_MAX, 2560) > LEFT_WIDTH
    assert card_width(LEFT_WIDTH, LEFT_MAX, 5120) == LEFT_MAX


def test_the_report_tab_counts_what_needs_attention(window: MainWindow) -> None:
    """Eine Warnung muss zu sehen sein, auch wenn etwas anderes vorn steht.

    Ein eingelesenes Netz mit offenen Stellen meldete sich im Prüfbericht —
    und im Fenster sah man einen Reiter, der aussah wie vorher. Wer die Tour
    oder den Chat offen hatte, erfuhr von der Warnung nichts.

    Gezählt werden Fehler und Warnungen, keine Hinweise: „Doppelte Punkte
    wurden verschweißt" ist eine Auskunft und keine Aufforderung.
    """
    from app.core.types import Finding

    index = window.right.indexOf(window.report)
    plain = window.right.tabText(index)
    assert "·" not in plain, "ohne Befunde steht dort nur der Name"

    window.report.add_findings(
        [
            Finding(code="ingest.not_watertight", severity="warning", message="offen"),
            Finding(code="slice.thin_wall", severity="info", message="dünn"),
        ]
    )

    assert window.report.alerts() == 1, "eine Warnung, der Hinweis zählt nicht"
    assert window.right.tabText(index) == f"{plain} · 1"


def test_a_stopped_chain_opens_the_report_even_during_a_tour(window: MainWindow) -> None:
    """Die Meldung sagt „siehe Prüfbericht" — dann muss er auch aufgehen.

    Der Vorrang der Tour ist richtig, solange es um eine Warnung im Ablauf
    geht. Hält die Kette an, verweist die Statusleiste ausdrücklich auf den
    Bericht; ein Verweis auf ein Fenster, das die Anwendung selbst zuhält,
    ist keiner.
    """
    from app.core import examples
    from app.core.tour import tour_for

    example = next(entry for entry in examples.EXAMPLES if tour_for(entry.id))
    window.tour.start(example, tour_for(example.id))
    # Gezeigt und mit sichtbarem Arbeitsbereich, weil ``_focus_report`` auf
    # einer unsichtbaren Spalte nichts tut — richtig so: ein Reiterwechsel
    # hinter dem Startbildschirm wäre keiner. Hält die Kette an, ist ohnehin
    # ein Projekt offen.
    window.show()
    window._show_start_screen(False)
    switch_to = window.right.indexOf(window.tour)
    window.right.setTabVisible(switch_to, True)
    window.right.setCurrentIndex(switch_to)
    assert window.tour.active, "die Anleitung läuft"

    window._focus_report()
    assert window.right.currentWidget() is window.tour, "eine Warnung lässt die Anleitung stehen"

    window._focus_report(force=True)
    assert window.right.currentWidget() is window.report, "ein Abbruch holt den Bericht nach vorn"


def test_the_object_tree_offers_the_keyboard_a_starting_point(window: MainWindow) -> None:
    """Wer per Tabulator in den Baum kommt, muss sich bewegen können.

    Nach dem Öffnen stand ``currentItem()`` auf nichts, obwohl eine Zeile da
    war — eine Pfeiltaste bewegte daraufhin gar nichts, und die
    Tastaturnavigation begann im Leeren.

    Gewählt ist damit weiterhin nichts: die Marke sagt „hier steht der
    Zeiger", nicht „das ist ausgewählt". Der Unterschied zählt, denn an der
    Auswahl hängen die Menüs.
    """
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()

    assert window.object_tree.tree.topLevelItemCount() >= 1
    assert window.object_tree.tree.currentItem() is not None, "die Tastatur hat einen Anfang"
    assert not window.object_tree.selected_objects(), "gewählt ist trotzdem nichts"


def test_every_locked_menu_entry_says_why(window: MainWindow) -> None:
    """Ausgrauen allein ist die halbe Antwort.

    Auf der leeren Szene sind fast alle Operationszeilen gesperrt, und bei
    allen stand als Hinweis ihr Beschreibungssatz — was sie täte, wenn sie
    könnte. Die Werkzeugzeile daneben sagte es im selben Augenblick richtig:
    „Dafür braucht es einen Körper in der Szene." Der Grund fehlte, weil
    ``_kind_hint`` sofort ausstieg, sobald eine Operation kein
    ``requires_kind`` trägt — und das haben sieben von 84.

    Geprüft wird gegen den Beschreibungssatz: Ein Hinweis, der ihm gleicht,
    ist keiner.
    """
    from app.core.registry import REGISTRY

    window._update_actions()

    stumm = []
    for name, action in window._op_actions.items():
        if action.isEnabled():
            continue
        spec = REGISTRY.get(name)
        if action.toolTip().strip() == str(spec.doc).strip():
            stumm.append(name)

    assert not stumm, (
        f"{len(stumm)} gesperrte Einträge nennen ihren Grund nicht, "
        f"darunter {stumm[:5]}. Der Nutzer sucht ihn dann bei sich."
    )


def test_a_menu_entry_gets_its_description_back_when_it_works_again(window: MainWindow) -> None:
    """Der Grund verschwindet, sobald es keinen mehr gibt.

    Sonst bleibt „Wählen Sie dafür ein Objekt aus" an einem Eintrag stehen,
    der längst geht — und der Beschreibungssatz, den er eigentlich trägt, wäre
    für immer weg.
    """
    from app.core.registry import REGISTRY

    window._update_actions()
    name = next(
        entry
        for entry, action in window._op_actions.items()
        if not action.isEnabled() and REGISTRY.get(entry).consumes == 1
    )
    spec = REGISTRY.get(name)
    action = window._op_actions[name]
    assert action.toolTip() != str(spec.doc), "der gesperrte Eintrag nennt keinen Grund"

    # Derselbe Eintrag, aber jetzt liegt genug vor: ein Objekt in der Szene und
    # eines ausgewählt. Geprüft wird die Rückstellung und nicht der Szenenaufbau
    # — dafür genügt der Zustand, aus dem der Hinweis entsteht.
    #
    # **Über beide Glieder der Kette**, seit ``_kind_hint`` den Grund
    # entgegennimmt statt ihn selbst zu holen: Die Freigabe des Eintrags folgt
    # demselben Grund, und ihn zweimal je Eintrag zu rechnen war nicht nur
    # doppelte Arbeit. Die Zeile prüft damit beides — dass ``_reason_locked``
    # hier keinen Grund mehr findet und dass ``_kind_hint`` daraufhin den
    # Beschreibungssatz zurückgibt.
    window._kind_hint(action, window._reason_locked(spec, [], 1, spec.consumes), False)

    assert action.toolTip().strip() == str(spec.doc).strip(), (
        "Der Grund blieb stehen, obwohl der Eintrag wieder geht — dann ist der "
        "Beschreibungssatz für immer weg."
    )


def test_the_chat_setup_button_leads_where_its_name_says(window: MainWindow) -> None:
    """Derselbe Name, derselbe Dialog.

    Der Knopf am gesperrten Chat hieß „Zugang einrichten …" und führte in die
    „Zusätzlichen Programme" — dorthin, wo man ein lokales Modell installiert,
    aber seinen Schlüssel nicht einträgt. Der Dialog mit dem Schlüsselfeld
    heißt „Chat einrichten", steht im Menü unter genau diesem Namen und war
    vom Chat aus nicht erreichbar. Wer keinen Zugang hatte, bekam damit einen
    der zwei Wege aus §27 angeboten und fand den anderen nicht.
    """
    from app.i18n import tr

    assert window.chat.setup.text() == str(tr("Chat einrichten …")), (
        "Knopf und Menüeintrag müssen denselben Text tragen — sonst sind es für "
        "den Nutzer zwei verschiedene Dinge."
    )

    treffer = [
        action
        for action in window.findChildren(QAction)
        if action.text() == str(tr("Chat einrichten …"))
    ]
    assert treffer, "der Menüeintrag heißt nicht mehr so"


def test_a_warning_still_reaches_someone_with_the_right_column_hidden(
    window: MainWindow,
) -> None:
    """§2.5 nennt „Warnungen" für die Statusleiste, und dort standen sie nie.

    Solange die rechte Spalte offen ist, trägt ihr Reiter die Zahl. Ist sie zu,
    erreichte eine neue Warnung niemanden mehr: ``_focus_report`` steigt bei
    unsichtbarer Spalte zu Recht aus, und danach kam nichts. Der Zähler in der
    Statusleiste erscheint genau dann — und holt beides zurück.
    """
    # Ohne das liegt der Startbildschirm oben, und die rechte Spalte ist auch
    # dann unsichtbar, wenn niemand sie ausgeblendet hat.
    window._show_start_screen(False)
    window.right_column.setVisible(True)
    window._mark_status_alerts(3)
    # ``isHidden`` und nicht ``isVisible``: Das Fenster selbst wird hier nie
    # gezeigt, und dann ist jedes Kind unsichtbar — die Frage ist, ob der Knopf
    # ausgeblendet wurde.
    assert window.alert_button.isHidden(), (
        "Bei offener Spalte trägt der Reiter die Zahl — zwei Zähler sind einer zu viel."
    )

    window.right_column.setVisible(False)
    window._mark_status_alerts(3)
    assert not window.alert_button.isHidden(), "die Warnung erreicht niemanden mehr"
    assert "3" in window.alert_button.text()

    window._show_alerts()
    assert window.right_column.isVisibleTo(window), "der Klick holt die Spalte nicht zurück"
    assert window.right.currentWidget() is window.report
    assert window.alert_button.isHidden(), "er bleibt stehen, obwohl die Spalte offen ist"


def test_the_status_counter_stays_away_when_nothing_is_wrong(window: MainWindow) -> None:
    """Ein Zähler, der immer dasteht, wird Tapete — dieselbe Begründung wie am
    Reiter."""
    window._show_start_screen(False)
    window.right_column.setVisible(False)
    window._mark_status_alerts(0)

    assert window.alert_button.isHidden()


def test_what_a_screen_reader_can_name(window: MainWindow) -> None:
    """Ein Feld ohne Namen wird als seine Art angesagt — „Eingabe", „Auswahl".

    Wer nicht sieht, welches Label danebensteht, bedient damit ein Formular aus
    lauter „Eingabe". Gemessen waren es 44 von 102 fokussierbaren Elementen:
    die neun Beispielkacheln des Startbildschirms, die Wähler aller Leisten,
    die Suchfelder, der Schichtenregler, jede Liste.

    Was hier durchgeht, sind Qts eigene Unterwidgets: die Aufklappliste eines
    Auswahlfelds trägt den Namen ihres Feldes, ein Rollbereich den seines
    Inhalts. Sie zu benennen hieße, dieselbe Auskunft zweimal vorzulesen.
    """
    from PySide6.QtWidgets import (
        QAbstractScrollArea,
        QComboBox,
        QLabel,
        QTabBar,
        QTabWidget,
        QWidget,
    )

    def name_of(widget: QWidget) -> str:
        if widget.accessibleName().strip():
            return widget.accessibleName().strip()
        text = getattr(widget, "text", None)
        if callable(text):
            try:
                if str(text()).strip():
                    return str(text()).strip()
            except Exception:  # pragma: no cover - Qt-Signaturen streuen
                pass
        parent = widget.parentWidget()
        if parent is not None:
            for label in parent.findChildren(QLabel):
                if label.buddy() is widget and label.text().strip():
                    return label.text().strip()
        return ""

    def qt_internal(widget: QWidget) -> bool:
        if widget.objectName().startswith("qt_"):
            return True
        # Die Popup-Liste eines Auswahlfelds und der Rollbereich um einen
        # Inhalt: beide gehören einem Element, das selbst einen Namen trägt.
        parent = widget.parentWidget()
        while parent is not None:
            if isinstance(parent, QComboBox):
                return True
            parent = parent.parentWidget()
        # Ein Reiterfeld wird über seine Reiter angesagt, und die tragen Text.
        return (
            isinstance(widget, QAbstractScrollArea | QTabBar | QTabWidget)
            and not widget.accessibleName()
        )

    window._show_start_screen(False)
    nameless = [
        f"{type(child).__name__}({child.objectName() or '-'})"
        for child in window.findChildren(QWidget)
        if child.focusPolicy() != Qt.FocusPolicy.NoFocus
        # Ausgeblendetes liest niemand vor. ``isHidden`` und nicht
        # ``isVisible``: Das Fenster selbst wird hier nie gezeigt, und dann
        # wäre jedes Kind unsichtbar.
        and not child.isHidden()
        and not qt_internal(child)
        and not name_of(child)
    ]

    assert not nameless, (
        f"{len(nameless)} bedienbare Elemente haben für einen Bildschirmleser keinen "
        f"Namen: {nameless}. setAccessibleName() oder ein Label mit setBuddy()."
    )


def test_the_open_tool_keeps_its_symbol_readable(qt_app: QApplication) -> None:
    """Auf dem gedrückten Knopf widersprachen sich Symbol und Beschriftung.

    Er trug Bernstein, und das Stylesheet gab der Beschriftung dort die dunkle
    Schrift der Auswahl. Das **Symbol** kam weiter aus dem Thema, also hell:
    1,58 Kontrast auf der Fläche, gemessen. Zwei Zeichen derselben Aussage in
    entgegengesetzten Farben — und das hellere war das unlesbare. Eine eigene
    Umfärbung hielt die beiden zusammen.

    **Seit der Akzenthaushalt gilt, gibt es die Umfärbung nicht mehr, und die
    Zusage kehrt sich um.** Das aktive Werkzeug trägt eine gedämpfte Fläche und
    behält die Schrift des Themas; dieselbe Farbe ist damit in beiden Zuständen
    die richtige, und ein Symbol, das beim Einschalten die Farbe wechselte,
    wäre jetzt das falsche. Was gleich bleibt, ist der Grund, aus dem dieser
    Test steht: Das Zeichen muss auf seiner Fläche zu lesen sein — nur ist die
    Fläche eine andere geworden, und darum wird gegen sie gemessen und nicht
    mehr gegen die Auswahlfarbe.

    Gemessen wird am ``QIcon`` und nicht am gerenderten Knopf: die Beschriftung
    daneben streut Subpixel-Farben in jede Bildpunktzählung, und die sahen dem
    Symbol zum Verwechseln ähnlich.
    """
    from PySide6.QtCore import QSize

    from app.ui.style import active_fill, apply_style
    from app.ui.theme import apply_theme, contrast_ratio

    # **Die Betriebslage herstellen, sonst misst der Test Windows.** ``icon()``
    # holt seine Farbe aus der Palette des Widgets, und ohne angewandtes Thema
    # ist das die des Systems: Das Symbol kam schwarz heraus. Der Test war
    # trotzdem grün, weil er gegen ``palette().highlight()`` maß — ebenfalls
    # eine Systemfarbe. Zwei Farben, die es in der Anwendung nicht gibt, und
    # ihr Verhältnis passte zufällig.
    before = QApplication.instance().styleSheet()
    apply_theme(QApplication.instance(), "dark")
    apply_style(QApplication.instance(), "dark")
    window = MainWindow(Session(), UiSettings())
    button = window.tools._buttons["analysis"]

    def dominant(icon: object) -> str:
        image = icon.pixmap(QSize(24, 24)).toImage()  # type: ignore[attr-defined]
        tally: dict[str, int] = {}
        for y in range(image.height()):
            for x in range(image.width()):
                colour = image.pixelColor(x, y)
                if colour.alpha() > 180:
                    tally[colour.name()] = tally.get(colour.name(), 0) + 1
        assert tally, "das Symbol zeichnet nichts"
        return max(tally, key=lambda name: tally[name])

    try:
        resting = dominant(button.icon())
        window.tools.activate("analysis")
        active = dominant(button.icon())
    finally:
        QApplication.instance().setStyleSheet(before)
    fill = active_fill("dark")

    ratio = contrast_ratio(active, fill)
    assert ratio >= 4.5, f"Symbol {active} auf {fill}: {ratio:.2f} — auf seiner Fläche unlesbar"
    assert active == resting, (
        "das Symbol wechselt beim Einschalten die Farbe — die Beschriftung daneben tut es "
        "nicht mehr, und zwei Zeichen derselben Aussage in zwei Farben waren der Anlass "
        "dieses Tests"
    )

    # Und zurück, damit ein späterer Wechsel der Fläche hier auffällt und nicht
    # erst dort, wo jemand den Knopf ansieht.
    window.tools.activate(None)
    assert dominant(button.icon()) == resting


def test_the_view_bar_stays_out_of_the_way(window: MainWindow) -> None:
    """Die Leiste liegt **über** dem Modell, also ist ihre Breite eine Zusage.

    Mit Beschriftung an jedem Knopf wären es 1039 Bildpunkte gewesen — bei
    einem 1024er Fenster mehr als ein Drittel der Ansicht, und damit genau die
    Fläche, für die §2.5 die Karten überhaupt schweben lässt. Mit Symbolen sind
    es gut zweihundert.

    Die Grenze steht hier und nicht im Docstring, weil ein Zusatz sie sonst
    lautlos zurücknimmt: Wer einen achten Knopf oder eine Beschriftung
    hinzufügt, bekommt einen roten Lauf und entscheidet dann bewusst.
    """
    bar = window.viewport.view_bar
    bar.adjustSize()
    assert bar.width() <= 260, f"{bar.width()} px — die Leiste frisst den Viewport"
    assert bar.height() <= 48, f"{bar.height()} px hoch"


# --- Die Wiederherstellung fragt zweimal dasselbe (§38) -------------------------


def test_both_recovery_questions_name_their_action_and_the_age(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Beide Fälle gehen über denselben Aufbau — und der nennt Handlung und Alter.

    Der namenlose Fall stand auf „Ja"/„Nein" und ohne jede Angabe, während sein
    Zwilling daneben beides längst hatte. Geprüft wird deshalb nicht der Dialog
    (der hängt modal), sondern **womit** die beiden Aufrufer ihn bestellen:
    Wer hier einen zweiten Aufbau daneben stellt, bekommt einen roten Lauf.

    Gemessen wird **im** Aufruf. Danach ginge es nicht mehr: Ein Projekt zu
    speichern räumt die namenlose Sicherung weg, und die Prüfung liefe gegen
    eine Datei, die es zu Recht nicht mehr gibt.
    """
    from app.core.scene.project import write_autosave

    bestellt: list[dict[str, Any]] = []

    def merken(
        self: MainWindow, candidate: Path, saved: Path | None, question: str, decline: str
    ) -> bool:
        bestellt.append(
            {
                "vorhanden": candidate.is_file(),
                "alter": MainWindow._when(candidate),
                "saved": saved,
                "question": question,
                "decline": decline,
            }
        )
        return False

    monkeypatch.setattr(MainWindow, "_ask_recovery", merken)

    # Der namenlose Fall: die Sicherung liegt im Nutzerverzeichnis, das
    # conftest in einen Temp-Ordner umbiegt (§38).
    write_autosave(window.session.project, None)
    window._offer_unsaved_recovery()

    # Und der benannte daneben.
    named = tmp_path / "projekt.p3d"
    window.session.save_project(named)
    write_autosave(window.session.project, named)
    window._offer_recovery(named)

    assert len(bestellt) == 2, "beide Fälle müssen über _ask_recovery gehen"
    for eintrag in bestellt:
        assert eintrag["vorhanden"], "gefragt wird nur zu einer Sicherung, die es gibt"
        assert eintrag["question"].strip(), "die Frage sagt, worum es geht"
        # Das Alter steht im Dialog — ohne es entscheidet niemand zwischen
        # „vor fünf Minuten" und „vor drei Wochen".
        assert eintrag["alter"].strip()
        assert eintrag["alter"] != tr("unbekannt")
        # Der Knopf heißt nach seiner Handlung. „Ja" verlangt, die Frage im
        # Kopf zu behalten — dieselbe Begründung wie bei confirm_discard.
        decline = eintrag["decline"]
        assert decline not in {"Ja", "Nein", "Yes", "No"}, decline
        assert len(decline.split()) >= 2, f"{decline!r} benennt keine Handlung"

    # Nur der benannte Fall hat einen gespeicherten Stand zum Vergleichen; der
    # namenlose hat die Sicherung und sonst nichts.
    assert [eintrag["saved"] is None for eintrag in bestellt] == [True, False]


def test_a_declined_backup_is_not_offered_again(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wer die Sicherung ablehnt, hat entschieden — auch beim nächsten Öffnen.

    Sie blieb liegen und war weiter neuer als die Datei, also fragte jedes
    Öffnen erneut. Gemessen an der laufenden Oberfläche: sechs Öffnungen,
    sechs Fragen. Das ist keine Rückfrage mehr, das ist Nörgeln.
    """
    from app.core.scene.project import write_autosave

    gefragt: list[Path] = []

    def ablehnen(
        self: MainWindow, candidate: Path, saved: Path | None, question: str, decline: str
    ) -> bool:
        gefragt.append(candidate)
        return False

    monkeypatch.setattr(MainWindow, "_ask_recovery", ablehnen)

    named = tmp_path / "projekt.p3d"
    window.session.save_project(named)
    write_autosave(window.session.project, named)

    window._offer_recovery(named)
    window._offer_recovery(named)
    window._offer_recovery(named)

    assert len(gefragt) == 1, f"{len(gefragt)} Fragen für eine abgelehnte Sicherung"


def test_discarding_at_the_end_really_discards(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """*Verwerfen* am Schließen darf keine Sicherung hinterlassen.

    Das Fenster fragte, der Nutzer verwarf — und danach schrieb ``closeEvent``
    genau diesen Stand als automatische Sicherung weg. Beim nächsten Öffnen
    bot die Anwendung ihm an, was er weggeworfen hatte.
    """
    from PySide6.QtGui import QCloseEvent

    from app.core.scene.project import autosave_path, find_recovery, write_autosave

    named = tmp_path / "projekt.p3d"
    window.session.save_project(named)

    # So sieht es aus, wenn der Zeitgeber im Lauf gesichert hat und danach
    # weitergearbeitet wurde: eine Sicherung liegt da, das Dokument ist
    # geändert. Genau in diesem Zustand wird geschlossen.
    write_autosave(window.session.project, named)
    window.session._dirty = True
    monkeypatch.setattr("app.ui.main_window.confirm_unsaved", lambda *args, **kwargs: "discard")

    window.closeEvent(QCloseEvent())

    assert not autosave_path(named).is_file(), "die verworfene Sicherung liegt noch da"
    assert find_recovery(named) is None


def test_a_recovered_project_saves_into_the_users_file(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Sicherung wird geöffnet, aber sie wird nicht zur Datei des Nutzers.

    ``open_project`` machte sie dazu: ein „Speichern" danach schrieb in
    ``projekt.p3d.autosave``, und die eigentliche Datei blieb unberührt — die
    wiederhergestellte Arbeit war beim nächsten Öffnen wieder fort.
    """
    from app.core.scene.project import write_autosave

    named = tmp_path / "projekt.p3d"
    window.session.save_project(named)
    write_autosave(window.session.project, named)
    monkeypatch.setattr(MainWindow, "_ask_recovery", lambda *args, **kwargs: True)

    window._offer_recovery(named)

    assert window.session.path == named, f"gespeichert würde nach {window.session.path}"
    assert window.session.modified, "der Stand weicht von der Datei ab — genau darum ging es"


def test_no_question_box_asks_yes_or_no(window: MainWindow) -> None:
    """Bauart-Prüfung: „Ja"/„Nein" ist in dieser Oberfläche keine Frage.

    Der letzte Ja/Nein-Dialog war der namenlose Wiederherstellungsfall. Diese
    Zeile hält es dabei — sonst ist der nächste in einem halben Jahr wieder da,
    und er liest sich beim Schreiben jedes Mal harmlos.
    """
    import app.ui

    quellen = sorted(Path(app.ui.__file__).parent.glob("*.py"))
    assert quellen, "keine Oberflächenquellen gefunden"
    for path in quellen:
        text = path.read_text(encoding="utf-8")
        assert "QMessageBox.question" not in text, f"{path.name}: Ja/Nein-Frage"
        assert "StandardButton.Yes" not in text, f"{path.name}: Ja-Knopf"


def test_the_theme_stands_before_anything_is_shown(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Ladebildschirm stand knapp drei Sekunden im Systemgrau.

    Gesetzt hat das Thema erst ``build_application`` — und davor liegen der
    Ladebildschirm und ``load_operations()``. Gemessen: die Palette steht
    solange auf #efefef, danach auf #343a45. Der erste Eindruck der Anwendung
    war ein hellgrauer Kasten, der mitten im Laden die Farbe wechselt.

    Geprüft am kürzesten Weg durch ``main``: eine abgelaufene Demo kehrt mit 1
    zurück, bevor irgendein Fenster gebaut wird. Ist die Palette dann schon
    gefärbt, steht das Thema früh genug — und der Abschiedsdialog, das einzige
    Fenster dieses Starts, ist mit gedeckt.
    """
    import datetime

    from app.core.activation import Activation
    from app.ui import app as app_module
    from app.ui.theme import THEMES, apply_theme, current_theme

    themed = THEMES["dark"]["window"]
    # Die Palette gehört der ganzen Anwendung: wer sie in einem Test umstellt,
    # stellt sie für jeden folgenden um. Dieselbe Sorgfalt wie bei der
    # Anzeigeeinheit (siehe ``tests/conftest.py``) — nur hier lokal, weil kein
    # zweiter Test das braucht.
    before = qt_app.palette()
    before_style = qt_app.styleSheet()
    before_theme = current_theme()
    # Ein frischer Prozess trägt noch kein Stylesheet. Nur die Palette zu
    # leeren ließ den Themenmerker eines früheren Tests stehen: main erkannte
    # dann ein bereits gesetztes Thema und durfte dessen Aufbau überspringen.
    qt_app.setStyleSheet("")
    qt_app.setPalette(QApplication.style().standardPalette())
    assert qt_app.palette().window().color().name() != themed, (
        "ohne Thema ist die Palette die des Systems — sonst prüft der Test nichts"
    )

    # Eine Demo, deren Stichtag herum ist: ``main`` kehrt mit 1 zurück, bevor
    # ein Fenster gebaut wird. Was bis dahin gesetzt ist, ist früh genug.
    gone = Activation(licence=None, days_left=0, deadline=datetime.date(2000, 1, 1))
    assert gone.over, "sonst läuft der Test durch den ganzen Start"
    monkeypatch.setattr(app_module.activation, "state", lambda: gone)
    monkeypatch.setattr(app_module, "load_settings", lambda: UiSettings(theme="dark"))
    # Wie ``test_cli.py``: ``main`` läuft hier im Prozess der Suite, und der
    # Prozessschutz bög sonst ``sys.excepthook`` und ``faulthandler`` von
    # pytest um (Review Rest #5).
    monkeypatch.setattr(app_module, "install_crash_logging", lambda: None)

    shown: list[bool] = []
    monkeypatch.setattr("app.ui.dialogs.show_expired_demo", lambda state: shown.append(True))

    try:
        assert app_module.main([]) == 1, "eine abgelaufene Demo startet nicht"
        assert shown == [True], "und sagt es"
        assert qt_app.palette().window().color().name() == themed, (
            "die Palette steht noch auf dem Systemgrau"
        )
    finally:
        qt_app.setStyleSheet("")
        apply_theme(qt_app, before_theme)
        qt_app.setPalette(before)
        qt_app.setStyleSheet(before_style)


def test_the_program_start_configures_https_before_reading_the_licence(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der mitgelieferte CA-Satz muss vor jedem möglichen Netzkontakt gelten."""
    import datetime

    from app.core.activation import Activation
    from app.ui import app as app_module

    order: list[str] = []
    gone = Activation(licence=None, days_left=0, deadline=datetime.date(2000, 1, 1))
    monkeypatch.setattr(
        app_module.network,
        "configure_certificates",
        lambda: order.append("certificates") or True,
    )
    monkeypatch.setattr(
        app_module.activation,
        "state",
        lambda: order.append("licence") or gone,
    )
    monkeypatch.setattr("app.ui.dialogs.show_expired_demo", lambda _state: None)
    monkeypatch.setattr(app_module, "install_crash_logging", lambda: None)

    assert app_module.main([]) == 1
    assert order[:2] == ["certificates", "licence"]


def test_the_marketing_video_follows_demo_trial_and_sale_configuration(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die nächste Aufnahme darf nie das Angebot des vorigen Baus versprechen."""
    import datetime

    from tools import make_video

    monkeypatch.setattr(make_video.activation_store, "DEMO_UNTIL", None)
    monkeypatch.setattr(make_video.activation_store, "TRIAL_FROM", None)
    sale = " ".join(make_video.offer_copy("de"))
    assert "14" not in sale and "Demo" not in sale

    monkeypatch.setattr(make_video.activation_store, "TRIAL_FROM", datetime.date(2027, 2, 1))
    trial = " ".join(make_video.offer_copy("de"))
    assert f"{make_video.activation_store.TRIAL_DAYS} Tage" in trial

    monkeypatch.setattr(make_video.activation_store, "DEMO_UNTIL", datetime.date(2026, 10, 30))
    demo = " ".join(make_video.offer_copy("en"))
    assert "30 October 2026" in demo and "days" not in demo


# --- Die Projektdatei als Argument (Dateizuordnung) -----------------------------


def test_a_project_given_on_the_command_line_is_found(tmp_path: Path) -> None:
    """Was per Doppelklick mitkommt, findet die Anwendung im Aufruf.

    Unter Windows und Linux ist das der ganze Mechanismus hinter einer
    Dateizuordnung — der Explorer startet die Anwendung mit dem Pfad als
    Argument. Bis dahin wurde er an ``QApplication`` weitergereicht und dort
    verworfen, und die Zuordnung, die der Linux-Menüeintrag längst versprach,
    ging ins Leere.
    """
    from app.ui.app import requested_file

    project = tmp_path / "dose.p3d"
    project.write_bytes(b"PK\x03\x04")

    assert requested_file(["Solidon3D.exe", str(project)]) == project


def test_options_and_missing_files_are_stepped_over(tmp_path: Path) -> None:
    """Eine Qt-Option ist kein Dateiname, und ein Tippfehler ist keine Datei.

    Beides würde sonst als Projekt geöffnet und endete in einer Fehlermeldung
    vor dem ersten Blick auf das Programm.
    """
    from app.ui.app import requested_file

    project = tmp_path / "halter.p3d"
    project.write_bytes(b"PK\x03\x04")

    assert requested_file(["Solidon3D.exe"]) is None
    assert requested_file(["Solidon3D.exe", "-style", "fusion"]) is None
    assert requested_file(["Solidon3D.exe", str(tmp_path / "gibtsnicht.p3d")]) is None
    assert requested_file(["Solidon3D.exe", "--platform", str(project)]) == project


def test_a_directory_is_not_reported_as_missing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Ein Verzeichnis ist keine Datei — aber es fehlt auch nicht.

    Beides lief in dieselbe Zeile: „file … does not exist". Wer im Protokoll
    sucht, warum sein Doppelklick nichts tat, liest genau diese und sucht
    danach an der falschen Stelle weiter.
    """
    from app.ui.app import requested_file

    ordner = tmp_path / "projekte"
    ordner.mkdir()

    with caplog.at_level(logging.WARNING):
        assert requested_file(["Solidon3D.exe", str(ordner)]) is None

    assert "does not exist" not in caplog.text, "das Verzeichnis gibt es"
    assert "not a file" in caplog.text


def test_the_finder_event_opens_what_it_names(tmp_path: Path, qt_app: QApplication) -> None:
    """Auf dem Mac kommt die Datei als Ereignis, nicht als Argument.

    Ohne diesen Filter wäre der Dokumenttyp im Bundle ein Eintrag ohne Wirkung:
    Der Finder startet die Anwendung und schickt ihr den Pfad, und niemand hört
    zu. Geprüft wird über das echte Ereignis und nicht über einen direkten
    Aufruf von ``open_path`` — die Verbindung dazwischen ist die Sache.
    """
    from PySide6.QtGui import QFileOpenEvent

    from app.ui.app import FileOpenListener

    project = tmp_path / "deckel.p3d"
    project.write_bytes(b"PK\x03\x04")

    opened: list[Path] = []

    class Recorder:
        def open_path(self, path: Path) -> None:
            opened.append(path)

    listener = FileOpenListener(cast(Any, Recorder()))
    handled = listener.eventFilter(qt_app, QFileOpenEvent(str(project)))

    assert handled, "das Ereignis wurde durchgereicht statt beantwortet"
    assert opened == [project]


def test_a_step_can_be_made_exact_afterwards(window: MainWindow) -> None:
    """Der Weg, den es nicht gab: erst bauen, dann exakt brauchen.

    Ein Quader aus einem alten Projekt, vor P2.8 ohne Haken angelegt, war
    endgültig ein Netz: Sieben Operationen blieben ihm gesperrt, und der
    einzige Weg dorthin war, den Schritt zu löschen und alles darüber neu zu
    bauen. Seit P2.8 steht der Wechsel am Schritt im Verlauf
    (``MainWindow.switch_kernel``); der Dialog trägt keinen Haken mehr.
    """
    from tests.helpers import exact_kernel

    exact_kernel()
    window.session.start_new()
    window.session.history.apply(
        "Quader", [OperationDraft(op="create_box", params={"width": 30.0})]
    )
    window.session.evaluate_now()
    window.session.wait_for_idle()
    assert [entry.op for entry in window.session.project.document.ops] == ["create_box"]

    op_id = window.session.project.document.ops[0].id
    window.switch_kernel(op_id)
    window.session.wait_for_idle()

    assert [entry.op for entry in window.session.project.document.ops] == ["create_brep_box"]
    body = next(iter(window.session.last_result.scene.objects.values()))
    assert body.kind == "brep", "der Körper ist jetzt wirklich exakt"


def test_a_locked_tool_names_the_step_that_spoiled_the_exact_body(window: MainWindow) -> None:
    """Der Hinweis sprach vom Haken beim Anlegen — auch dann, wenn der Körper
    längst exakt angelegt war und ein späterer Schritt ihn zum Netz gemacht hat.

    In dem Fall hilft kein Haken. Die Auswertung weiß, welcher Schritt es war
    (``evaluate.exact_became_mesh``), und der Satz nennt ihn.

    **Gemessen wird das an ``brep_to_mesh``** — die dritte Umstellung dieser
    Art an einem Tag. Erst stand hier ``sketch_pocket``, bis die Tasche am
    30.08.2026 auch in Netze schneiden lernte; dann ``fillet_edges``, dann
    ``draft_faces``, bis beide am 10.09.2026 dasselbe lernten. Die Umwandlung
    ist die einzige, die es nie anders geben kann: „ein exakter Körper wird
    ein Netz" braucht einen exakten Körper.
    """
    window.session.start_new()
    window.session.apply(
        "Quader", [OperationDraft(op="create_brep_box", inputs=[], params={"width": 40.0})]
    )
    window.session.wait_for_idle()
    body = next(iter(window.session.last_result.scene.objects))
    # Seit P2.8 bohrt *Bohrung setzen* am exakten Körper exakt; was ihn zum
    # Netz macht, ist ein Aushöhlen mit Entlüftung (Konzept §10.1).
    window.session.apply(
        "Aushöhlen",
        [
            OperationDraft(
                op="hollow_object",
                inputs=[body],
                params={"wall": 2.0, "open_top": True, "vents": 2},
            )
        ],
    )
    window.session.wait_for_idle()

    window.object_tree.select_object(next(iter(window.session.last_result.scene.objects)))
    window._update_actions()
    hint = window._op_actions["brep_to_mesh"].toolTip()

    assert str(REGISTRY.get("hollow_object").title) in hint, hint
    assert "Nehmen Sie die Schritte ab dort zurück" in hint, (
        "der Satz nennt eine Handlung, die es gibt"
    )


def test_a_finding_names_a_body_a_later_step_has_replaced(qt_app: QApplication) -> None:
    """Der Fall aus dem Handbuchbild, in allen sechs Sprachen zu sehen.

    Das Aushöhlen meldet etwas über die Dose. Danach macht ``create_lid`` aus
    ihr zwei Körper — die Kennung `obj_1` gibt es nicht mehr, die zwei Befunde
    zeigen aber weiter darauf. Im Bericht stand deshalb „obj_1" statt eines
    Namens: aufgelöst wurde nur gegen die Endszene, und dort fehlt er.

    Der Name, den der Körper trug, ist die Antwort auf „welcher denn". Er ist
    nicht mehr aktuell — aber er war es, als der Befund entstand, und das ist
    genau die Auskunft, die der Leser braucht.
    """
    from app.core.knowledge import profiles
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.ui.panels import ReportPanel

    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    history = History(document)
    history.apply(
        "Dose",
        [
            OperationDraft(
                op="create_box",
                params={"width": 60.0, "depth": 40.0, "height": 30.0, "name": "Dose"},
            )
        ],
    )
    history.apply(
        "Aushöhlen",
        [
            OperationDraft(
                op="hollow_object",
                inputs=(document.ops[-1].outputs[0],),
                params={"wall": 3.0, "open_top": True},
            )
        ],
    )
    # Ein Werkzeug, das die Dose im Abziehen verbraucht. Der Deckel taugt dafür
    # seit ``keeps_inputs`` nicht mehr: Er setzt die Dose fort und legt den
    # Deckel daneben — die Kennung bleibt, und der Fall wäre verfehlt.
    history.apply(
        "Werkzeug",
        [OperationDraft(op="create_cylinder", params={"diameter": 20.0, "name": "Werkzeug"})],
    )
    tool = document.ops[-1].outputs[0]
    history.apply(
        "Abziehen",
        [OperationDraft(op="subtract_objects", inputs=(tool, "obj_1"), params={})],
    )

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    result = evaluate(document, profile, sources=ProjectSources(project))

    stale = [f for f in result.scene.report.findings if f.object_id == "obj_1"]
    assert stale, "kein Befund zeigt mehr auf den verbrauchten Körper — Fall verfehlt"
    assert "obj_1" not in result.scene.objects, "obj_1 lebt noch — das Abziehen hat ihn verbraucht"

    panel = ReportPanel()
    try:
        panel.show_result(result, document)
        lines = [panel.list.item(row).text() for row in range(panel.list.count())]
    finally:
        panel.deleteLater()

    about_stale = [line for line in lines if any(str(f.message) in line for f in stale)]
    assert about_stale, f"die Befunde stehen nicht in der Liste: {lines}"
    assert not any("obj_1" in line for line in about_stale), (
        f"der Bericht nennt die Kennung statt des Namens: {about_stale}"
    )
    assert any("Dose" in line for line in about_stale), (
        f"der Bericht nennt den Namen nicht, den der Körper trug: {about_stale}"
    )


def test_the_face_jump_names_the_area_in_the_chosen_unit(window: MainWindow) -> None:
    """Und die Beschriftung des Flächensprungs trug die Einheit **im Satz** —
    „Fläche an {object} — {area} mm², {side}". Ein Satz mit eingebauter Einheit
    kann nicht in Zoll sprechen; die Einheit gehört in den Wert."""
    from app.ui.labels import set_display_unit

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()

    try:
        set_display_unit("in")
        faces = window._drawable_faces()
        assert faces, "der Testkörper hat Flächen"
        for _feature_id, label, _normal in faces:
            assert "mm²" not in label, label
        assert any("in²" in label for _f, label, _n in faces)
    finally:
        set_display_unit("mm")


#: Eine Kommazahl mit Punkt — aber kein Pfad, keine Versionsnummer, keine Endung.
#:
#: Die Wächter links und rechts sind der Unterschied: „sources/1_cube.stl" und
#: „0.1.2" sind keine Zahlen, und eine Prüfung, die sie mitzählt, wird
#: abgeschaltet statt gelesen.
_DECIMAL_POINT = re.compile(r"(?<![\w./\\-])\d+\.\d+(?![\w./\\-])")


def _visible_texts(root: object, mark: str) -> list[tuple[str, str]]:
    """Jeden Text, den dieser Baum zeigt — Beschriftung, Knopf, Liste, Tooltip."""
    from PySide6.QtWidgets import QAbstractButton, QGroupBox, QLabel, QListWidget, QTreeWidget

    found: list[tuple[str, str]] = []
    for widget in [*root.findChildren(QLabel), *root.findChildren(QAbstractButton)]:
        text = widget.text() if hasattr(widget, "text") else ""
        if text:
            found.append((f"{mark}/{type(widget).__name__}", text))
        if widget.toolTip():
            found.append((f"{mark}/tooltip", widget.toolTip()))
    for box in root.findChildren(QGroupBox):
        if box.title():
            found.append((f"{mark}/QGroupBox", box.title()))
    for listing in root.findChildren(QListWidget):
        for index in range(listing.count()):
            found.append((f"{mark}/QListWidgetItem", listing.item(index).text()))
    for tree in root.findChildren(QTreeWidget):
        for index in range(tree.topLevelItemCount()):
            entry = tree.topLevelItem(index)
            for column in range(tree.columnCount()):
                if entry.text(column):
                    found.append((f"{mark}/QTreeWidgetItem", entry.text(column)))
    return found


def test_no_visible_text_writes_a_decimal_point(window: MainWindow) -> None:
    """Die Gegenprobe zur Regelprüfung — von der anderen Seite.

    `test_no_number_reaches_the_user_past_the_localisation` liest den Quelltext
    und sieht f-Strings mit Formatangabe. Sie sieht **nicht**, was über
    `"%.2f" %`, über `.format()`, über `str(round(…))` oder über ein nacktes
    `f"{wert}"` auf einer Fließkommazahl hereinkäme. Heute gibt es davon keine
    Stelle; morgen schreibt jemand die erste, und die Regel schweigt.

    Diese Prüfung schaut deshalb auf das Ergebnis: Sie baut die zahlenreichen
    Flächen auf — Fenster mit geladenem Modell, Druckeinstellungen, fünf
    Operationsdialoge — und liest jeden Text, den sie zeigen, samt Tooltips.
    Im deutschen Fenster darf dort keine Zahl mit Punkt stehen. Gemessen sind
    das über vierhundert Texte.
    """
    from PySide6.QtCore import QLocale

    from app.ui.print_settings_dialog import PrintSettingsDialog

    before = QLocale()
    try:
        QLocale.setDefault(QLocale("de"))
        window.open_path(MESHES / "plate_holes.stl")
        window.session.wait_for_idle()
        QApplication.processEvents()

        texts = _visible_texts(window, "Fenster")

        settings = PrintSettingsDialog(window.session, window.settings, window)
        settings.show()
        QApplication.processEvents()
        texts += _visible_texts(settings, "Druckeinstellungen")
        settings.reject()

        for name in ("drill_hole", "apply_texture", "insert_nut_trap", "label_text", "hollow"):
            if not REGISTRY.has(name):
                continue
            dialog = OperationDialog(REGISTRY.get(name), {}, window)
            dialog.show()
            QApplication.processEvents()
            texts += _visible_texts(dialog, name)
            dialog.reject()

        assert len(texts) > 300, f"nur {len(texts)} Texte — die Flächen sind nicht aufgebaut"
        offenders = [
            f"{where}: {text[:90]!r}" for where, text in texts if _DECIMAL_POINT.search(text)
        ]
        assert not offenders, "Zahl mit Punkt im deutschen Fenster:\n" + "\n".join(offenders[:15])
    finally:
        QLocale.setDefault(before)


def test_the_decimal_point_check_would_catch_a_violation() -> None:
    """Ein Wächter für die Prüfung darüber: ein grüner Lauf soll etwas heißen."""
    assert _DECIMAL_POINT.search("Übermaß: 12.40 mm")
    assert _DECIMAL_POINT.search("+1.25 cm³")
    assert not _DECIMAL_POINT.search("Übermaß: 12,40 mm")
    assert not _DECIMAL_POINT.search("Pfad: sources/1_cube.stl"), "ein Pfad ist keine Zahl"
    assert not _DECIMAL_POINT.search("Version 0.1.2"), "eine Versionsnummer auch nicht"
    assert not _DECIMAL_POINT.search("https://example.com/x.stl")


# --- Auf einer Fläche zeichnen (§30.1, P3) -----------------------------------


def _face_menu(window: MainWindow) -> tuple[str, object]:
    """Ein Modell laden, seine erste Fläche wählen, ihr Kontextmenü bauen."""
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    face = next(fid for fid, feature in entry.features.items() if feature.kind == "face")

    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, face)
    return face, window.object_tree.context_menu()


def test_a_face_offers_to_be_drawn_on(window: MainWindow) -> None:
    """§30.1 nennt die angeklickte Fläche als Ort einer Skizzenebene, und
    ``planes.py`` nennt sie „die interessantere".

    Erreichbar war sie nur über ein Klappfeld mit Zeilen wie „Fläche an
    Gehäuse — 2 400 mm², oben" — über das Wiedererkennen in einer Liste statt
    über das Zeigen auf sie.
    """
    _face, menu = _face_menu(window)

    assert menu is not None
    labels = [action.text() for action in menu.actions()]  # type: ignore[attr-defined]
    assert "Auf dieser Fläche zeichnen" in labels, f"Eintrag fehlt: {labels}"


def test_choosing_that_entry_really_starts_a_sketch_on_that_face(window: MainWindow) -> None:
    """Der Anschluss, nicht das Angebot.

    Ein Menüeintrag mit einem Handler ist kein eingelöstes Versprechen —
    ``.claude/rules/tests.md`` führt genau diese Bauform unter „Die
    Gegenprobe", „Am Weg vorbei": ein Knopf, dessen Verbindung nie geprüft
    war. Geprüft wird deshalb, dass der Skizzenmodus läuft **und** auf
    welcher Ebene er steht.
    """
    face, menu = _face_menu(window)
    assert menu is not None

    draw = next(
        action
        for action in menu.actions()  # type: ignore[attr-defined]
        if action.text() == "Auf dieser Fläche zeichnen"
    )
    draw.trigger()

    assert window.sketching(), "der Skizzenmodus läuft"
    panel = window._sketch_panel
    assert panel is not None
    object_id = window.object_tree.selected()
    expected = f"feature:{object_id}:{face}"
    assert panel.canvas.sketch.plane == expected, "und zwar auf der geklickten Fläche"
    assert panel.plane_choice.currentData() == expected, "die Wahl steht mit"

    window.finish_sketch(keep=False)


def test_without_a_chosen_face_nothing_offers_to_be_drawn_on(window: MainWindow) -> None:
    """Am Körper selbst gibt es keine Ebene, auf die man zeigen könnte.

    Die Gegenprobe zum Test oben: Ohne sie wäre auch ein Eintrag grün, der
    immer erscheint — und der führte am Körper in eine Skizze auf einer
    Fläche, die niemand gewählt hat.
    """
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id = next(iter(result.scene.objects))

    window.object_tree.select_object(object_id)
    menu = window.object_tree.context_menu()

    assert menu is not None
    labels = [action.text() for action in menu.actions()]  # type: ignore[attr-defined]
    assert "Auf dieser Fläche zeichnen" not in labels, f"steht am Körper: {labels}"


def test_a_hole_does_not_offer_to_be_drawn_on(window: MainWindow) -> None:
    """Auf einer Bohrung gibt es keine Ebene zu zeichnen.

    **Und dieser Test war der Grund, den vorigen nicht für ausreichend zu
    halten.** Die Gegenprobe „kein Merkmal gewählt" lief auch ohne die
    Artprüfung grün: Dort greift schon die zweite Wache (keine Kennung), und
    der ``kind != "face"``-Zweig war damit ungeprüft. Erst ein Merkmal, das
    eine Kennung hat und **keine Fläche ist**, misst ihn — dafür braucht es
    ein Modell mit Bohrung.
    """
    window.session.import_model(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(fid for fid, feature in entry.features.items() if feature.kind == "hole")

    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)
    menu = window.object_tree.context_menu()

    assert menu is not None
    labels = [action.text() for action in menu.actions()]  # type: ignore[attr-defined]
    assert "Auf dieser Fläche zeichnen" not in labels, f"steht an einer Bohrung: {labels}"


def test_the_three_slicer_handles_stand_where_a_body_is_chosen(window: MainWindow) -> None:
    """Verschieben, Drehen, Skalieren stehen direkt da — nicht zwei Klicks tief.

    **Der Maßstab ist der Slicer, nicht ein CAD-Programm.** Wer Solidon öffnet,
    kommt von Cura oder PrusaSlicer, und dort liegen diese drei auf der
    Werkzeugleiste. Hier lagen sie einmal unter „Ändern" zwischen dreißig
    anderen Einträgen (§2.6, §18.5).

    **Seit dem 11.09.2026 trägt das Kontextmenü keine Operationen mehr**; die
    drei stehen dort, wo ein gewählter Körper seine Handlungen hat: rechts in
    der Karte, als eigene Knöpfe, und dazu als Werkzeug *Bewegen* in der
    Werkzeugzeile mit dem Griff im Bild. Gezählt wird an den gebauten Knöpfen,
    nicht an ``operations_for_object()``.

    **Seit dem 14.09.2026 beginnt ihre Gruppe zugeklappt**: *Ändern* zählt am
    Körper mehr Einträge, als ein Menü zeigen darf, und ``OPEN_UP_TO`` klappt
    eine solche Gruppe zu (``test_interface_limits.
    test_the_selection_card_keeps_the_menu_limit_on_its_open_groups``). Die
    drei stehen deshalb einen Klick auf die Kopfzeile entfernt — nicht zwei
    Klicks tief in einem Menü, und der Griff im Bild bleibt ohnehin.
    """
    window.session.import_model(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id = next(iter(result.scene.objects))

    window.object_tree.select_object(object_id)
    QApplication.processEvents()

    panel = window.selection_operations
    for name in ("translate_object", "rotate_object", "scale_object"):
        button = panel._buttons[name]
        _section, toggle, _buttons = next(
            group for group in panel._groups.values() if button in group[2]
        )
        assert not button.isHidden(), f"{name} steht am gewählten Körper nicht rechts"
        if not toggle.isChecked():
            toggle.click()
            QApplication.processEvents()
        assert button.isVisibleTo(panel), f"{name} steht auch offen nicht in der Karte"
        assert button.isEnabled(), f"{name} ist am gewählten Körper gesperrt"
    assert any(str(tool.title) == tr("Bewegen") for tool in window.tools.tools().values()), (
        "und das Werkzeug *Bewegen* steht in der Werkzeugzeile"
    )


def test_the_sketch_mode_leaves_the_view_standing(window: MainWindow) -> None:
    """**Der Schnitt (§30.1, P4).** Robert am 24.08.2026: „am viewport ändert
    sich nichts, bei draufsicht, seitenansicht usw sieht man auch keinen
    unterschied".

    Der Grund war ein Tausch im Stapel: Die Ansicht lag unter einem Blatt,
    also änderte eine Kameravorgabe etwas, das niemand sah. Jetzt bleibt sie
    stehen, das Modell tritt durchscheinend zurück, und die Zeichnung liegt
    darin.
    """
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window.session.evaluate_now()
    vorher = window.viewport.display_mode

    window.start_sketch("sketch_extrude", "")

    assert window.middle_stack.currentWidget() is window.viewport, "die Ansicht bleibt im Bild"
    assert window.viewport.display_mode == "transparent", "das Modell tritt zurück"
    assert window.sketching(), "und gezeichnet wird trotzdem"

    window.finish_sketch(keep=False)

    assert window.viewport.display_mode == vorher, "danach steht die Darstellung wie zuvor"
    assert not window.sketching()


def test_the_camera_swings_onto_the_plane_that_is_drawn_on(window: MainWindow) -> None:
    """Beim Betreten schwenkt sie, danach nie wieder von selbst.

    Ohne den Schwenk läge die Zeichenebene schräg im Bild, und die erste
    Linie ginge irgendwohin. Mit ihm sieht man auf sie — und wer danach
    dreht, bleibt gedreht: Ein Bild, das nach jedem Strich zurückspringt,
    wäre schlimmer als eines, das nie schwenkt.
    """
    window.start_sketch("sketch_extrude", "")
    panel = window._sketch_panel
    assert panel is not None

    frame = window._sketch_frame()
    assert frame is not None, "die Grundebene hat einen Rahmen"
    assert frame.normal == pytest.approx((0.0, 0.0, 1.0)), "XY ist die Vorgabe"

    # Offscreen gibt es keinen Renderer, der Schwenk selbst ist also nicht
    # messbar (Entscheidung G). Prüfbar ist, dass er mit der richtigen Ebene
    # gerufen würde — und dass das Zeichnen ohne Renderer nicht scheitert.
    panel.canvas.set_tool("line")
    panel.canvas.place_on_plane((0.0, 0.0))
    panel.canvas.place_on_plane((20.0, 0.0))

    assert len(panel.canvas.sketch.elements) == 1, "gezeichnet wird auch ohne Bild"
    window.finish_sketch(keep=False)


def test_a_click_in_the_view_draws_on_the_plane(window: MainWindow) -> None:
    """Der Anschluss (§30.1, P4): Klick in der Ansicht, Punkt in der Skizze.

    Offscreen gibt es keinen Renderer, der Sichtstrahl selbst ist also nicht
    messbar (Entscheidung G). Prüfbar ist die Kette dahinter — und genau die
    war der Punkt: ``_sketch_hit`` rechnet den Strahl gegen die Ebene, das
    Signal trägt zwei Zahlen in Millimetern, und die Zeichenfläche macht
    damit dasselbe wie mit einem Klick auf sich selbst.

    **Was dieser Test ausdrücklich nicht prüft**, und das ist gemessen: Dass
    ``_on_left_click`` den Skizzenmodus vor der Auswahlkette abfragt. Entfernt
    man diesen Zweig, bleibt der Test grün — er sendet das Signal selbst,
    statt einen Klick auszulösen, und einen echten Klick gibt es ohne Renderer
    nicht (``_pick_ray`` gibt dort ``None``). Diese eine Zeile gehört zur
    Bild-Hälfte und wird im Prüfstand mit echtem Fenster gemessen, nicht hier.
    """
    window.start_sketch("sketch_extrude", "")
    panel = window._sketch_panel
    assert panel is not None
    panel.canvas.set_tool("line")

    window.viewport.sketchPointPicked.emit((0.0, 0.0))
    window.viewport.sketchPointPicked.emit((20.0, 0.0))

    assert len(panel.canvas.sketch.elements) == 1, "zwei Klicks, eine Linie"
    start, end = panel.canvas.sketch.elements[0].points
    assert start == pytest.approx((0.0, 0.0))
    assert end == pytest.approx((20.0, 0.0))

    window.finish_sketch(keep=False)


def test_the_view_stops_aiming_at_the_plane_when_the_sketch_ends(window: MainWindow) -> None:
    """Sonst zeichnete ein Klick weiter auf eine Ebene, die niemand meint.

    ``set_sketching(None)`` ist die Rücknahme, und ohne sie bliebe der
    Viewport in einem Modus, in dem er keine Körper mehr auswählt — die
    Auswahlkette liegt hinter der Skizzenfrage.
    """
    window.start_sketch("sketch_extrude", "")
    assert window.viewport._sketch_frame is not None, "im Modus zielt er auf die Ebene"

    window.finish_sketch(keep=False)
    assert window.viewport._sketch_frame is None, "danach wieder auf die Szene"


def test_changing_the_plane_swings_the_camera_along(window: MainWindow) -> None:
    """Wer die Ebene wechselt, sieht woanders hin — und will das auch sehen.

    Das ist die eine Stelle, an der nach dem Betreten noch geschwenkt wird.
    Beim Zeichnen selbst bleibt die Ansicht, wie der Nutzer sie gedreht hat.
    """
    window.start_sketch("sketch_extrude", "")
    panel = window._sketch_panel
    assert panel is not None

    vorher = window.viewport._sketch_frame
    assert vorher is not None and vorher.normal == pytest.approx((0.0, 0.0, 1.0))

    panel.choose_plane("plane:xz")

    nachher = window.viewport._sketch_frame
    assert nachher is not None
    assert nachher.normal == pytest.approx((0.0, 1.0, 0.0)), "die Ansicht zielt auf die neue Ebene"

    window.finish_sketch(keep=False)


def test_the_picture_for_the_support_asks_the_viewport_for_its_own(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das Bild einer Fehlermeldung muss das Modell zeigen, nicht ein Loch.

    **Warum das ein eigener Test ist und kein Bildvergleich.** ``QWidget.grab``
    malt Qts Puffer ab; der Viewport zeichnet in eine native pygfx-Renderfläche und
    steht dort nicht drin. Am 24.08.2026 kam so ein Bogen bei Robert an: alles
    darauf zu sehen — Menüs, Objektbaum, Parameter, Prüfbericht — nur in der
    Mitte, wo das Teil liegt, war es schwarz. Gemessen war der Viewport-Bereich
    danach **eine einzige Farbe** auf 100 % der Fläche; nach der Änderung sind
    es 530.

    Prüfen lässt sich das hier nicht am Bild: ``tests/conftest.py`` setzt
    ``QT_QPA_PLATFORM=offscreen``, dort gibt es keine Renderfläche, und
    :meth:`Viewport.snapshot` gibt folgerichtig ``None`` zurück. Ein Test über
    Bildpunkte wäre grün über einer leeren Menge — dieselbe Falle, die im
    Register unter „Offscreen prüft nichts, was am Aktor hängt" steht.

    Geprüft wird deshalb die **Kette**: dass ``window_shot`` überhaupt jemanden
    fragt. Wer den Aufruf entfernt, bekommt einen roten Lauf statt eines
    schwarzen Lochs im nächsten Kundenbogen.

    **Ohne Fenster-Fixture, und das ist gemessen.** Ein zweiter Test daneben
    hat über ``window`` ein ganzes ``MainWindow`` gebaut, nur um zu sehen, dass
    ``snapshot`` ohne Renderer ``None`` gibt. Er hob die Abrissquote dieser Datei
    von 1 aus 3 auf 2 aus 3 — die Suite baut in einem Prozess hunderte
    Fenster mit Ansicht, und zwei weitere kippten sie. Ein nacktes ``QWidget`` genügt
    hier, denn die Frage ist der Aufruf und nicht das Bild.
    """
    from app.ui import support_dialog

    asked: list[object] = []
    monkeypatch.setattr(
        support_dialog, "_paint_viewports", lambda picture, widget: asked.append(widget)
    )
    from PySide6.QtWidgets import QWidget

    widget = QWidget()
    widget.resize(320, 240)
    try:
        data = support_dialog.window_shot(widget)
    finally:
        widget.deleteLater()

    assert data.startswith(b"\x89PNG"), "ohne PNG hat der Bogen kein Bild"
    assert asked == [widget], (
        "window_shot muss die Ansichten nachmalen lassen — sonst bleibt die "
        "Bildmitte leer, und genau dort liegt das Teil des Kunden"
    )


def test_drawing_starts_on_the_selected_face_not_under_it(window: MainWindow) -> None:
    """Fläche gewählt, „Zeichnen" gedrückt — gezeichnet wird auf der Fläche.

    Roberts Fall vom 24.08.2026: Deckfläche ausgewählt, Draufsicht, Zeichnen —
    und die Striche landeten **unter** dem Körper auf z=0. Der Knopf der
    Werkzeugzeile rief ``start_sketch("")`` ohne Ebene, und ohne Ebene hieß
    Grundebene, gleich was gewählt war. Wer eine Fläche wählt und dann
    zeichnet, meint diese Fläche.

    Geprüft wird bis in die Zahl: Der Rahmen der Zeichenebene muss auf der
    Höhe der Deckfläche liegen, nicht auf null — der Ebenenname allein bewiese
    nur die halbe Kette. Die Höhe wird aus dem Körper gelesen und nicht
    hingeschrieben: Sie stand hier als 10.0, weil der 20-mm-Würfel um den
    Ursprung lag; seit das erste Modell eines Projekts mittig auf dem Bett
    landet (03.09.2026), sind es 20.0. Eine abgelesene Zahl altert still, eine
    gemessene nicht.
    """
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    top = next(
        fid
        for fid, feature in entry.features.items()
        if feature.kind == "face" and feature.params.get("normal", (0, 0, 0))[2] > 0.9
    )
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, top)

    window.action_sketch_free()
    try:
        panel = window._sketch_panel
        assert panel is not None
        assert panel.canvas.sketch.plane == f"feature:{object_id}:{top}", (
            "die gewählte Fläche muss die Zeichenebene sein, nicht die Grundebene"
        )
        frame = window._sketch_frame()
        assert frame is not None
        deckflaeche = entry.mesh.bounds.maximum[2]
        assert deckflaeche > 0.0, "sonst prüft die Zeile darunter gegen null"
        assert frame.origin[2] == pytest.approx(deckflaeche), (
            "gezeichnet wird auf der Deckfläche, nicht darunter auf z=0"
        )
    finally:
        window.finish_sketch(keep=False)


def test_duplicate_face_ids_keep_the_selected_body_and_its_label(window: MainWindow) -> None:
    """``face_1`` gilt je Körper und darf deshalb nicht den ersten gewinnen lassen.

    Zwei importierte Körper tragen gleichnamige erkannte Flächen. Gewählt wird
    bewusst der zweite: Ebenenreferenz und verständlicher Hinweis müssen bei
    ihm bleiben, unabhängig von Flächengröße und Szenenreihenfolge.
    """
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    first, second = list(result.scene.objects.items())[-2:]
    _first_id, first_entry = first
    second_id, second_entry = second
    first_entry.name = "Erster Körper"
    second_entry.name = "Gewählter Körper"
    duplicate = next(
        feature_id
        for feature_id, feature in second_entry.features.items()
        if feature.kind == "face"
        and feature_id in first_entry.features
        and first_entry.features[feature_id].kind == "face"
    )
    assert str(first_entry.name) != str(second_entry.name), "die Namen müssen unterscheidbar sein"

    window.object_tree.select_object(second_id)
    window.object_tree.select_feature(second_id, duplicate)
    window.action_sketch_free()
    try:
        panel = window._sketch_panel
        assert panel is not None
        assert panel.canvas.sketch.plane == f"feature:{second_id}:{duplicate}"
        assert str(second_entry.name) in window._sketch_hint.text(), (
            "der Hinweis muss den tatsächlich gewählten Körper nennen"
        )
        assert str(first_entry.name) not in window._sketch_hint.text()
    finally:
        window.finish_sketch(keep=False)


def test_drawing_without_a_selection_still_starts_on_the_base_plane(window: MainWindow) -> None:
    """Ohne Auswahl bleibt die Grundebene die Vorgabe — der Fix darf den
    leeren Start nicht mitreißen."""
    window.action_sketch_free()
    try:
        panel = window._sketch_panel
        assert panel is not None
        assert panel.canvas.sketch.plane.startswith("plane:"), panel.canvas.sketch.plane
    finally:
        window.finish_sketch(keep=False)


def test_the_snap_marker_follows_the_canvas_not_a_second_calculation(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Fangmarke zeigt den Ort, den der Canvas gefangen hat — und stirbt
    mit dem Modus.

    Roberts „die Klicks sind woanders als ich klick" (24.08.2026) war der
    Rasterfang ohne sichtbare Marke: bis zu ein halber Rasterschritt zwischen
    Zeiger und Punkt, elf Bildpunkte bei 2 mm Raster. Der Ort kommt vom
    Canvas (``pointer_target``), denn nur er kennt Raster **und** „vorhandener
    Punkt schlägt Raster" — im Viewport nachgerechnet wäre es die zweite Zahl
    für dieselbe Sache (d6335c1).

    Offscreen gibt es keine Renderfläche und damit keine Marke zum Ansehen;
    geprüft wird die **Verbindung** — dieselbe Haltung wie beim Bild des
    Fehlerbogens: Wer den Draht kappt, bekommt einen roten Lauf, keinen
    Zeiger, der wieder lügt.
    """
    shown: list[object] = []
    monkeypatch.setattr(
        type(window.viewport), "show_sketch_cursor", lambda self, point: shown.append(point)
    )
    window.action_sketch_free()
    try:
        panel = window._sketch_panel
        assert panel is not None
        panel.pointerMoved.emit(4.0, -6.0)
        assert shown[-1] == (4.0, -6.0), "die gefangene Stelle muss die Marke stellen"
    finally:
        window.finish_sketch(keep=False)
    before = len(shown)
    panel.pointerMoved.emit(1.0, 1.0)
    assert len(shown) == before, "nach dem Modus darf der Draht nicht mehr tragen"


def test_the_sketch_hint_names_the_plane_being_drawn_on(window: MainWindow) -> None:
    """Der Hinweis sagt, worauf gezeichnet wird — und zieht beim Wechsel nach.

    Die andere Hälfte der Fangmarke: Das Kreuz sagt, wohin der Klick fällt,
    dieser Satz sagt, worauf. Robert hat am 24.08.2026 auf z=0 gezeichnet und
    es erst am Ergebnis gemerkt — mit dem Satz hätte die Leiste „Draufsicht
    (XY)" gesagt, während er auf die Deckfläche sah.
    """
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    top = next(
        fid
        for fid, feature in entry.features.items()
        if feature.kind == "face" and feature.params.get("normal", (0, 0, 0))[2] > 0.9
    )
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, top)

    window.action_sketch_free()
    try:
        panel = window._sketch_panel
        assert panel is not None
        assert "Fläche an" in window._sketch_hint.text(), (
            "auf einer Fläche gestartet muss der Hinweis die Fläche nennen"
        )
        assert panel.choose_plane("plane:xy")
        # Auf einer Hauptebene führt das Auswahlfeld die Ebene vollständig —
        # die Zeile schweigt (16.09.2026: „weniger ist manchmal mehr").
        assert "Draufsicht" in panel.plane_choice.currentText()
        assert not window._sketch_hint.text(), (
            "auf der Hauptebene wiederholt die Zeile das Auswahlfeld nicht"
        )
    finally:
        window.finish_sketch(keep=False)


def test_saving_a_part_takes_the_whole_stack_by_id_not_by_position(window: MainWindow) -> None:
    """Der Rezeptdialog bekommt die IDs der Schritte — nicht ihre Plätze.

    ``capture`` filtert nach ``Operation.id`` (zählt ab eins), ``enumerate``
    zählt ab null: Mit Indizes fiel der **letzte** Schritt jedes Stapels
    still aus dem Rezept, und niemand sah es — drei Schritte ergeben auch
    einen Körper, der Bereichstest blieb grün. Gefunden am 25.08.2026 bei der
    Verifikation im echten Fenster: Der Weg-2-Halter verlor seine
    Versteifung.

    Geprüft wird die Übergabe an den Dialog — dieselbe Stelle, an der der
    Fehler saß —, nicht der Dialog selbst: Der gehört seinen eigenen Tests.
    Und in derselben Übergabe steckte der zweite Fund desselben Tages: Das
    ``saved``-Signal trägt den **Namen** des Rezepts, und direkt an
    ``show_parts`` verbunden wurde er zum Suchtext — der Katalog zeigte nach
    dem Speichern nur noch den neuen Baustein, bei leerem Suchfeld. Verbunden
    gehört ``refresh``, das keinen Parameter nimmt.
    """
    from unittest import mock

    from app.core import examples

    window.session.open_project(examples.directory() / "weg2-halter-konstruieren.p3d")
    window.session.wait_for_idle()
    window.session.evaluate_now()
    document = window.session.project.document
    assert len(document.ops) >= 2, "der Fall braucht einen Stapel mit mehreren Schritten"

    captured: dict[str, object] = {}

    class Attrappe:
        def __init__(self, _doc, _payloads, op_ids, _features, _profile, parent=None, origin=None):
            captured["op_ids"] = tuple(op_ids)
            captured["origin"] = origin
            captured["dialog"] = self
            self.saved = mock.Mock()

        def exec(self):
            return 0

        def release(self):
            return None

        def deleteLater(self):  # noqa: N802 - Qt-Namen gehoeren Qt
            return None

    katalog = mock.Mock()
    with mock.patch("app.ui.main_window.RecipeDialog", Attrappe):
        window._save_as_part(katalog)

    assert captured["op_ids"] == tuple(op.id for op in document.ops), (
        "jeder Schritt des Stapels muss das Rezept erreichen — auch der letzte"
    )
    assert captured["origin"] is None, (
        "ein gewöhnliches Projekt kommt aus keinem Baustein — der Dialog legt nichts vor (E6)"
    )
    dialog = captured["dialog"]
    assert isinstance(dialog, Attrappe)
    verbunden = [aufruf.args[0] for aufruf in dialog.saved.connect.call_args_list]
    assert katalog.refresh in verbunden, (
        "nach dem Speichern wird der Katalog aufgefrischt, mit stehender Suche"
    )
    assert katalog.show_parts not in verbunden, (
        "der Rezeptname darf nie als Suchtext im Katalog landen"
    )


def test_no_dialog_asks_for_the_kernel_any_more(window: MainWindow) -> None:
    """P2.8: Der Haken „Flächen und Kanten später bearbeiten“ ist aus jedem Dialog verschwunden.

    Ein Quader entsteht exakt, wo der Kern da ist — der Menüeintrag *Quader
    anlegen* ruft den exakten Erzeuger, und sein Dialog trägt keinen Haken
    zwischen den Rechenkernen mehr. Geprüft am gebauten Dialog, nicht am
    Register (Konzept §10.1, Entscheidung 4).
    """
    from PySide6.QtWidgets import QCheckBox

    from app.core.registry import MENU_TWINS
    from tests.helpers import exact_kernel

    exact_kernel()
    assert "create_brep_box" in window._op_actions, "das Menü ruft den exakten Quader"
    assert "create_box" not in window._op_actions, "der Netz-Quader ist der versteckte Zwilling"
    assert MENU_TWINS["create_box"] == "create_brep_box"
    # Bohren und Aushöhlen brauchen einen gewählten Körper — sonst fragt
    # ``run_operation`` mit einem Hinweisfenster nach einer Markierung. Über
    # die Sitzung, nicht am Verlauf vorbei: Erst ihr Dokumentwechsel verlässt
    # den Startbildschirm, und von dort begänne ``run_operation`` das leere
    # Projekt (21.09.2026) — ohne Körper, mit demselben Hinweisfenster.
    from app.core.scene import OperationDraft

    assert window.session.apply("Quader", [OperationDraft(op="create_brep_box", params={})])
    assert window.session.wait_for_idle(30_000)
    result = window.session.last_result
    assert result is not None
    window.object_tree.select_object(next(iter(result.scene.objects)))
    QApplication.processEvents()
    for name in ("create_brep_box", "drill_hole", "hollow_object"):
        window.run_operation(REGISTRY.get(name))
        dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
        try:
            boxes = [box.text() for box in dialog.findChildren(QCheckBox)]
            assert not any("Flächen und Kanten" in text for text in boxes), (name, boxes)
        finally:
            dialog.reject()
            dialog.deleteLater()
            QApplication.processEvents()


def test_the_dialog_names_both_bodies_a_boolean_will_take() -> None:
    """Bei zwei Eingängen nennt der Satz sie beim Namen.

    Der Hinweis gab es seit je — er sagte aber nur „die 2 zuerst gewählten von
    3", und damit musste der Kunde seine eigene Klickreihenfolge erinnern.
    Ausgerechnet dort zählt sie am meisten: Die Booleschen sagen zu, dass „das
    zuerst angeklickte mit seinem Namen und Material bleibt" — welches das ist,
    ließ der Satz offen.

    Gegen die Funktion und nicht gegen ein gebautes Fenster, weil hier die
    Formulierung geprüft wird und nicht der Weg dorthin; den prüft
    ``test_a_dialog_says_which_body_it_works_on`` eine Ebene höher.
    """
    from app.ui.main_window import _works_on

    two_of_three = _works_on(["Klotz", "Stift", "Deckel"], 3, 2)

    assert "Klotz" in two_of_three and "Stift" in two_of_three
    assert "Deckel" not in two_of_three, "der dritte wird nicht verrechnet und nicht genannt"

    # Die Gegenprobe: Wer genau so viel wählt, wie die Operation nimmt, braucht
    # keine Erklärung — sonst stünde der Satz bei jeder zweiten Operation.
    assert _works_on(["Klotz", "Stift"], 2, 2) == ""


def test_the_halt_message_goes_when_the_chain_runs_again(window: MainWindow) -> None:
    """„Die Kette hält an" ist ein Zustand, keine Auskunft über eine Handlung.

    Eine Meldung überlebt hier absichtlich jeden Lauf (``announce``) — richtig
    für „Exportiert: dose.3mf", das ein Ergebnis festhält, und falsch für
    einen Stopp: Der gilt, solange die Kette steht, und nicht länger. Robert
    sah den Satz am 29.08.2026 über einem Prüfbericht mit null Fehlern und
    null Warnungen, lange nachdem er den Schritt zurückgenommen hatte — die
    Statuszeile behauptete einen Zustand, den es nicht mehr gab.

    Gemerkt wird die **Herkunft** der Meldung und nicht ihr Text: Ein
    Vergleich auf den Satz bräche beim ersten Sprachwechsel.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    object_id = next(iter(window.session.last_result.scene.objects))

    window.session.apply(
        "Bohrung setzen",
        [
            OperationDraft(
                op="drill_hole",
                inputs=(object_id,),
                params={"diameter": 5000.0, "x": 0.0, "y": 0.0, "z": 4.0, "axis": "z"},
            )
        ],
    )
    window.session.wait_for_idle()

    assert window.session.last_result.stopped_at is not None, "der Wert hält die Kette an"
    assert "hält an" in window._announcement, "und die Statuszeile sagt es"

    window.session.undo()
    window.session.wait_for_idle()

    assert window.session.last_result.stopped_at is None, "zurückgenommen rechnet sie wieder"
    assert window._announcement == "", (
        "und der Satz über den Stopp steht nicht mehr da — er gilt nicht mehr"
    )


def test_a_chosen_part_reaches_the_catalogue_in_one_click(window: MainWindow) -> None:
    """Die Bausteine haben keinen Menüort mehr — dafür einen am gewählten Teil.

    Neunundzwanzig Bausteine standen in sechs Untermenüs, siebenundzwanzig
    davon drei Klicks tief, und jede Zeile nannte eine Vokabel statt einer
    Form: „Filmscharnier", „Schnappverbinder für eine Naht". Wer nicht weiß,
    wie ein Filmscharnier aussieht, findet es dort nicht. Der Katalog mit
    Bildern gab es die ganze Zeit — nur in *Datei*, also dort, wo niemand
    hinsieht, der gerade auf eine Fläche zeigt (§2.6).

    **Roberts Bedingung zu dieser Änderung** war genau dieser Weg: „solange
    man einfach zum Katalog kommt, wenn man das Teil gewählt hat". Geprüft
    wird deshalb beides — dass der Weg am gewählten Teil steht, und dass er
    wirklich den Katalog ruft. Durchgereicht ist nicht gerufen.

    **Der Weg ist seit dem 11.09.2026 der Hauptknopf rechts**, nicht mehr eine
    Zeile im Kontextmenü: Das trägt keine Operationen mehr, und der Knopf
    *Bausteine* steht in Akzentfarbe unter der Karte der Handlungen — an
    Körper und Fläche, ein Klick.
    """
    from PySide6.QtWidgets import QMenu

    face, menu = _face_menu(window)
    assert face
    assert isinstance(menu, QMenu)
    titles = [action.text().replace("&", "") for action in menu.actions()]
    assert "Baustein einsetzen …" not in titles, "im Kontextmenü steht der Katalog nicht mehr"

    knopf = window.selection_operations.catalog_button
    assert knopf.isVisibleTo(window.selection_operations), "der Knopf steht an der Fläche"
    assert knopf.isDefault(), "und zwar als Hauptknopf"

    gerufen: list[bool] = []
    window.action_catalog = lambda: gerufen.append(True)  # type: ignore[method-assign]
    window.selection_operations.catalogRequested.connect(window.action_catalog)
    knopf.click()
    assert gerufen, "der Knopf steht da, öffnet den Katalog aber nicht"

    # Und die andere Hälfte: In der Menüleiste steht keiner mehr — gefragt
    # nach der **Kachel**, nicht nach der Kategorie. Hier stand
    # ``category == "parts"``, und das verlangte dasselbe von ``create_lid``
    # und ``screw_lid``, die gar keine Kachel haben: Sie verschwanden aus der
    # Leiste, ohne im Katalog aufzutauchen.
    in_bar = [name for name in window._op_actions if name in catalogue_operations()]
    assert catalogue_operations(), "es gibt keine Bausteine — dann prüft dieser Test nichts"
    assert not in_bar, f"Bausteine gehören in den Katalog, nicht ins Menü: {sorted(in_bar)}"


def test_a_parameter_field_shows_its_whole_value(window: MainWindow) -> None:
    """„die eingabefelder sind jetzt manchmal zu klein" (Robert, 30.08.2026).

    Die Wertfelder der Parameterkarte tragen `SizePolicy.Ignored`, und das mit
    gutem Grund: Ihr Wertebereich geht bis ±100 000, und danach bemessen wäre
    jedes Feld 156 Punkte breit, auch für eine 40. Ohne Boden schrumpfen sie
    aber unter das Maß, das ihren **aktuellen** Wert zeigt — gemessen 92 Punkte
    für ein Feld, dessen Zahl mit Auf- und Ab-Knopf 118 braucht. Auf dem
    Bildschirm stand „2,4" statt „2,40" und „1234" statt „1234,56", ohne dass
    etwas rot wird: Qt schneidet stumm.

    Der Boden ist deshalb der aktuelle Wert, nicht der Wertebereich.
    """
    from PySide6.QtWidgets import QAbstractSpinBox, QStyle, QStyleOptionSpinBox

    from app.core.types import Parameter

    document = window.session.project.document
    for name, value in (("breite", 1234.56), ("wandstaerke", 2.4)):
        document.parameters[name] = Parameter(name=name, value=value, unit="mm")
    window.parameters.show_document(document)
    window.parameters.grab()  # erzwingt das Legen der Zeilen
    QApplication.processEvents()

    def textraum(spin: QAbstractSpinBox) -> int:
        opt = QStyleOptionSpinBox()
        opt.initFrom(spin)
        return (
            spin.style()
            .subControlRect(
                QStyle.ComplexControl.CC_SpinBox, opt, QStyle.SubControl.SC_SpinBoxEditField, spin
            )
            .width()
        )

    felder = [
        spin
        for spin in window.parameters.findChildren(QAbstractSpinBox)
        if spin.isVisibleTo(window.parameters)
    ]
    assert felder, "ohne Felder prüft das hier nichts"

    eng = [
        f"{spin.text()!r}: {spin.fontMetrics().horizontalAdvance(spin.text())} nötig, "
        f"{textraum(spin)} da"
        for spin in felder
        if textraum(spin) < spin.fontMetrics().horizontalAdvance(spin.text())
    ]
    assert not eng, f"abgeschnittene Werte in der Parameterkarte: {eng}"


def test_every_menu_indents_its_text_the_same(window: MainWindow) -> None:
    """Die Textspalte darf beim Wandern von Menü zu Menü nicht springen.

    Qt reserviert die Symbolspalte **je Menü**, sobald ein einziger Eintrag ein
    Zeichen trägt. Drei der neun Menüs der Leiste hatten keines — Bearbeiten,
    Ansicht und Hilfe —, und darum stand ihr Text bei 16 Bildpunkten, während
    er in den übrigen sechs bei 36 stand. Der Grund war nicht Gestaltung,
    sondern Herkunft: Einträge aus dem Register bringen ihr Symbol mit
    (``icon_name_for``), von Hand geschriebene nicht. Für den Kunden sah es aus
    wie ein Fehler, und es war einer.

    Behoben wird es nicht dadurch, dass jeder Eintrag ein Bild bekommt — für
    „Parameter anlegen" gibt es keines, auf das die Welt sich geeinigt hätte —,
    sondern dadurch, dass jedes Menü **mindestens einen** Eintrag hat, dessen
    Bild zweifelsfrei ist: Rückgängig und Wiederholen, Alles einpassen,
    Handbuch und Über.

    Geprüft wird die Wirkung und nicht die Ursache: nicht „jedes Menü hat ein
    Symbol", sondern „alle fangen an derselben Stelle an". Gemessen am
    **gezeigten** Menü, weil Qt die Geometrie seiner Einträge vorher nicht
    kennt.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QMenu

    from app.ui.style import apply_style

    # **Drei Vorbereitungen, und ohne jede einzelne misst der Test nichts.**
    # Qt legt die Geometrie eines Menüs erst fest, wenn sein Fenster gezeigt
    # wurde. Und die Suite fährt **ohne Stylesheet** — Qt zeichnet dann sein
    # eigenes Menü, schwarz auf weiß, mit anderen Abständen als die Anwendung
    # sie hat. Ein Test, der eine Einrückung misst, muss die Betriebslage
    # herstellen; sonst prüft er eine Lage, die kein Kunde je sieht.
    vorher = QApplication.instance().styleSheet()
    apply_style(QApplication.instance(), "dark")
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.show()
    QApplication.processEvents()

    def text_starts_at(menu: QMenu) -> int | None:
        """Die erste Spalte eines symbollosen Eintrags, in der etwas steht."""
        without = [
            entry
            for entry in menu.actions()
            if not entry.isSeparator() and entry.text() and entry.icon().isNull()
        ]
        if not without:
            return None
        menu.popup(window.pos())
        QApplication.processEvents()
        image = menu.grab(menu.actionGeometry(without[0])).toImage()
        ground = image.pixelColor(image.width() - 3, image.height() // 2)
        found = None
        # Ab zwei, nicht ab null: ``actionGeometry`` ist relativ zum **Menü**,
        # und dessen Rahmen liegt in der ersten Spalte. Er weicht vom Grund ab
        # wie jeder Text, und die Suche fand deshalb in jedem Menü dieselbe 0.
        for x in range(2, image.width()):
            for y in range(image.height()):
                here = image.pixelColor(x, y)
                if (
                    abs(here.red() - ground.red())
                    + abs(here.green() - ground.green())
                    + abs(here.blue() - ground.blue())
                    > 60
                ):
                    found = x
                    break
            if found is not None:
                break
        menu.hide()
        QApplication.processEvents()
        return found

    starts: dict[str, int] = {}
    try:
        for action in window.menuBar().actions():
            menu = action.menu()
            if not isinstance(menu, QMenu):
                continue
            start = text_starts_at(menu)
            if start is not None:
                starts[action.text()] = start
    finally:
        QApplication.instance().setStyleSheet(vorher)

    # Ohne diese Zeile prüfte der Vergleich unten eine leere Menge — und die
    # ist immer einig mit sich selbst. Sechs der neun Menüs bestehen nur aus
    # Registeroperationen und tragen deshalb überhaupt keinen symbollosen
    # Eintrag; vier ist der Bestand, drei die Grenze, unter der die Messung
    # nichts mehr über einen *Sprung* sagen könnte.
    assert len(starts) >= 3, f"zu wenige Menüs gemessen: {starts}"
    # Und die zweite Hälfte derselben Zusicherung: Ein Text fängt nie bei null
    # an, dort liegt der Rahmen. Eine Null heißt, dass die Messung nicht
    # gemessen hat — und vier Nullen sind sich einig wie vier richtige Werte.
    assert all(start > 0 for start in starts.values()), f"die Messung hat nichts gefunden: {starts}"
    assert len(set(starts.values())) == 1, (
        f"die Textspalte springt zwischen den Menüs: {starts} — "
        "ein Menü ohne jedes Symbol reserviert die Spalte nicht"
    )


def test_a_short_calculation_shows_nothing_at_all(window: MainWindow) -> None:
    """Was aufblitzt, sagt nichts — es macht nur unruhig (§2.8).

    Von 28 gemessenen Rechnungen liegen **elf unter zwei Zehntelsekunden**,
    und es sind die häufigsten Gesten überhaupt: einen Wert im Dialog ändern
    (7 ms), am Schichtregler ziehen (0,01 ms), einen Pinselstrich setzen
    (0,2 ms). Bei jeder davon zuckte der Fortschrittsbalken auf und sofort
    wieder weg, weil ``_on_busy`` ihn ohne jeden Zeitgeber sichtbar machte.

    Geprüft wird über das **Signal** der Sitzung und nicht über den Slot: Was
    beim Rechnen erscheint, entscheidet die Verbindung, und die ist Teil der
    Zusage.
    """
    window.session.busyChanged.emit(True)
    # ``isVisibleTo`` überall: ``isVisible`` meldet in einem nie gezeigten
    # Fenster immer False, und ein Test, der Abwesenheit prüft, wäre dann
    # grün gegen eine Lüge — genau die Tarnung, vor der ``wartezeit.md`` warnt.
    assert not window.progress.isVisibleTo(window), "der Balken kam sofort"
    assert not window.cancel_button.isVisibleTo(window), "der Abbrechen-Knopf kam sofort"
    assert window.cursor().shape() != Qt.CursorShape.BusyCursor, "der Wartezeiger kam sofort"

    window.session.busyChanged.emit(False)
    assert not window.progress.isVisibleTo(window)
    assert window.cursor().shape() != Qt.CursorShape.BusyCursor, "ein Zeiger blieb stehen"


def test_the_waiting_grows_in_the_three_steps_the_plan_names(window: MainWindow) -> None:
    """Zeiger, dann Balken — und beides erst, wenn es etwas zu sagen gibt.

    §2.8 kennt drei Stufen über der Schwelle: bis zwei Zehntelsekunden nichts,
    bis zwei Sekunden Mauszeiger und Statusleiste, darüber Fortschritt mit
    Abbrechen. Zwölf der 28 gemessenen Marken liegen in der mittleren Stufe —
    Netz vergröbern, Fläche unterteilen, ein Beispielprojekt öffnen.

    Die Zeitgeber werden hier von Hand ausgelöst statt abgewartet: Zwei
    Sekunden Wartezeit in einem Test sind zwei Sekunden in jedem Lauf. Das
    Signal geht dabei durch dieselbe Verbindung, die auch im Betrieb feuert.
    """
    try:
        window.session.busyChanged.emit(True)
        assert window._patience.isActive(), "die Uhr für den Zeiger läuft nicht"
        assert window._bar_delay.isActive(), "die Uhr für den Balken läuft nicht"

        window._patience.timeout.emit()
        # Am **Fenster** gefragt und nicht an der Anwendung: Der Zeiger ist eine
        # Eigenschaft dieses Fensters, damit er den Override der synchronen
        # Rechnung nicht vom Stapel nimmt (der Grund steht bei
        # ``_show_wait_cursor``).
        cursor = window.cursor()
        assert cursor.shape() == Qt.CursorShape.BusyCursor, (
            "der reine Wartezeiger behauptet eine gesperrte Oberfläche — sie ist bedienbar"
        )
        assert not window.progress.isVisibleTo(window), "der Balken kam schon in der zweiten Stufe"

        window._bar_delay.timeout.emit()
        assert window.progress.isVisibleTo(window), "nach zwei Sekunden fehlt der Balken"
        assert window.cancel_button.isVisibleTo(window), "ein Balken ohne Abbrechen (§2.8)"
    finally:
        window.session.busyChanged.emit(False)

    assert not window.progress.isVisibleTo(window)
    assert window.cursor().shape() != Qt.CursorShape.BusyCursor, (
        "der Zeiger blieb stehen — das sieht aus wie ein hängendes Programm"
    )


def test_no_wait_cursor_survives_a_second_run(window: MainWindow) -> None:
    """Qt stapelt Zeiger, und ein Stapel wird nie ganz abgeräumt.

    ``setOverrideCursor`` zweimal und ``restoreOverrideCursor`` einmal lässt
    einen stehen. Bei einer Kette von Läufen — und beim Ziehen an einem
    Schieber ist jede Bewegung einer — wäre nach kurzer Zeit ein Wartezeiger
    da, den nichts mehr wegnimmt.
    """
    for _ in range(3):
        window.session.busyChanged.emit(True)
        window._patience.timeout.emit()
        window._patience.timeout.emit()  # ein zweiter Anlauf derselben Stufe
        window.session.busyChanged.emit(False)
    assert window.cursor().shape() != Qt.CursorShape.BusyCursor, (
        "nach drei Läufen steht ein Zeiger im Weg"
    )


def test_the_status_bar_leads_where_its_numbers_come_from(window: MainWindow) -> None:
    """Eine Auskunft, die eine Frage aufwirft, kennt den Weg zu ihrer Antwort.

    Zwei Zeilen der Statusleiste taten das nicht. „51 g · 3 h 30 min" ist
    geschätzt, und wer sie ändern oder nachrechnen will, braucht die
    Druckeinstellungen — der Weg dorthin stand nur im Menü, und im Menü sucht
    ihn niemand, der gerade auf die Zahl sieht. Die Lizenzzeile war der
    deutlichere Fall: Sie **nannte** ihren Weg, „Hilfe → Solidon freischalten
    …", und ließ den Kunden ihn zu Fuß gehen.

    Geprüft wird über das Signal beziehungsweise den Klick und nicht über die
    Methode dahinter: Was ein Klick auslöst, entscheidet die Verbindung.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    # **Erst fragen, ob die Verbindung steht — sie ist die Zusage.** Danach
    # wird sie gelöst und durch eine Attrappe ersetzt: Der echte Empfänger
    # öffnet einen modalen Dialog, und ein Test, der ihn aufgehen lässt, wartet
    # bis zum Zeitablauf. Beides in dieser Reihenfolge, sonst prüft der Klick
    # nur noch die Attrappe, die der Test selbst angehängt hat.
    try:
        window.facts.clicked.disconnect()
    except (RuntimeError, TypeError) as nothing_there:  # pragma: no cover — die Zusage
        raise AssertionError("ein Klick auf den Verbrauch bleibt folgenlos") from nothing_there
    opened: list[str] = []
    window.facts.clicked.connect(lambda: opened.append("settings"))

    # Geklickt und nicht ``mousePressEvent`` gerufen: Wer die Methode direkt
    # aufruft, prüft die Methode und nicht den Klick — und genau dazwischen lag
    # der Fehler, den dieser Test festhält.
    QTest.mouseClick(window.facts, Qt.MouseButton.LeftButton)
    assert opened == ["settings"], "der Klick erreicht das Signal nicht"

    # Und der Zeiger sagt es, bevor jemand klickt: Eine Zeile, die auf Klicks
    # reagiert und wie Text aussieht, ist eine versteckte Funktion.
    assert window.facts.cursor().shape() == Qt.CursorShape.PointingHandCursor
    assert window.facts.accessibleDescription(), "kein Satz für den, der nichts sieht"

    assert window.trial_line.cursor().shape() == Qt.CursorShape.PointingHandCursor
    # Die Lizenzzeile hängt an ihrer eigenen Handlung, nicht an einem Menüweg
    # im Text. Geprüft am Empfänger des Signals, denn genau die Verbindung war
    # das, was fehlte.
    try:
        window.trial_line.clicked.disconnect()
    except (RuntimeError, TypeError) as nothing_there:  # pragma: no cover — die Zusage
        raise AssertionError(
            "die Lizenzzeile beschreibt weiter einen Weg, statt einer zu sein"
        ) from nothing_there


def test_the_header_gives_its_information_room_in_every_supported_width(
    window: MainWindow,
    qt_app: QApplication,
    request: pytest.FixtureRequest,
) -> None:
    """Die Kopfzeile kürzt lesbar, statt ihre langen Angaben zu verschlucken.

    **Was gemessen war.** Die Kopfzeile lebt als Widget in der
    Werkzeugleiste, und Qt gibt einem Widget dort entweder seine
    ``sizeHint``-Breite oder gar keinen Platz. Mit **offenem** Projekt wollte
    sie 968 Pixel (Name 273, Maße 275, Drucker 330), die Leiste damit 2283 —
    und auf einem **1920er Bildschirm war die ganze Zeile weg**: Projektname,
    Maße, Druckplatte, Drucker und Material zusammen, hinter einem
    unbeschrifteten Pfeil.

    **Mit leerem Projekt passiert das nicht** (dort will sie 103 px), und
    genau deshalb fällt es beim Ausprobieren nicht auf. Der Test öffnet
    deshalb ein Beispiel, statt das leere Fenster zu messen — sonst prüfte er
    die Lage, in der der Fehler nie auftrat.

    Der erste Fix hielt nur das äußere Widget in der Leiste. Sein innerer
    Leerraum bekam die ganze Restbreite, während Projektname, Maße und Drucker
    selbst auf 1920 Pixeln je **null** Pixel breit waren. Deshalb prüft dieser
    Test die sichtbaren Kinder, nicht nur ihren Elternkasten.

    Zwei Zusagen: Die drei Angaben bekommen in jeder unterstützten Breite
    wirklich Raum, und die Kürzung bewahrt die Enden mit Bedeutung — Stern,
    Einheit und Druckermodell. Der ganze Wortlaut bleibt für Tooltip und
    Hilfstechnik erhalten.
    """
    from PySide6.QtWidgets import QStyle, QStyleOptionComboBox

    from app.ui.style import apply_style

    # Auch die Innenabstände sind Produktzustand. Ohne Stylesheet misst der
    # Test die Plattform und kann auf einem anderen Schreibtisch zufällig grün
    # werden.
    previous_style = qt_app.styleSheet()
    request.addfinalizer(lambda: qt_app.setStyleSheet(previous_style))
    apply_style(qt_app, "dark")

    # **Angezeigt werden muss es.** Ohne ``show()`` verteilt Qt keine Breite,
    # und genau ein Test ohne Layout hatte den Null-Pixel-Zustand übersehen.
    window.show()
    QApplication.processEvents()

    beispiele = sorted((Path(__file__).parent.parent / "app" / "examples").glob("*.p3d"))
    assert beispiele, "ohne Beispielprojekt misst dieser Test die leere Lage"
    window.session.open_project(beispiele[0])
    window.session.wait_for_idle()
    window._on_project()
    window.set_display_unit("in")
    window.header.title.setText("Ein sehr langes Beispielprojekt für den schmalen Bildschirm*")
    window.header.printer.setText("Allgemeiner FDM-Drucker 220 mm")
    window.header.show_plates(3)

    labels = (window.header.title, window.header.bounds, window.header.printer)
    full = tuple(label.full_text() for label in labels)
    assert all(full), "Projektname, Außenmaß und Drucker tragen je eine Auskunft"

    for breite, hoehe in ((1920, 1080), (1040, 760), (800, 600), (640, 720)):
        window.resize(breite, hoehe)
        window.header.updateGeometry()
        window.toolbar.updateGeometry()
        QApplication.processEvents()

        assert window.header.isVisibleTo(window.toolbar), (
            f"bei {breite} px ist die Kopfzeile im Überlaufmenü — "
            "Projektname, Drucker und Platte sind für den Kunden weg"
        )
        assert window.header.plates.isVisibleTo(window.toolbar)
        assert window.header.plates.width() > 0
        assert window.header.plates.accessibleName() == str(tr("Druckplatte"))
        assert window.header.plates.currentText() == str(tr("Alle Platten"))
        plate_option = QStyleOptionComboBox()
        plate_option.initFrom(window.header.plates)
        plate_option.currentText = window.header.plates.currentText()
        plate_field = window.header.plates.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            plate_option,
            QStyle.SubControl.SC_ComboBoxEditField,
            window.header.plates,
        )
        assert plate_field.width() >= window.header.plates.fontMetrics().horizontalAdvance(
            window.header.plates.currentText()
        ), "das sichtbare Feld muss Zweck und aktiven Plattenfilter vollständig zeigen"
        # Kein Filament mehr in der Kopfzeile — es gilt dem Körper und nicht
        # dem Projekt. An seiner Stelle muss der Druckerknopf lesbar sein:
        # als Symbol allein hat ihn niemand gefunden.
        button = window.header.printer_button
        assert button.isVisibleTo(window.toolbar) and button.width() > 0
        assert button.text(), "der Knopf trägt seine Beschriftung"
        for label, expected in zip(labels, full, strict=True):
            assert label.isVisibleTo(window.toolbar)
            assert label.width() > 0, f"{expected!r} bekommt bei {breite} px keinen Raum"
            assert label.full_text() == expected
            assert label.toolTip() == expected
            assert label.accessibleName() == expected
            assert label.focusPolicy() == Qt.FocusPolicy.NoFocus
            if label.fontMetrics().horizontalAdvance(expected) > label.width():
                assert label.text() != expected, (
                    "Qt darf keinen ungekürzten Text rechts abschneiden"
                )
                assert "…" in label.text(), "die sichtbare Kürzung muss als solche erkennbar sein"
        assert window.header.title.text().endswith("*"), "ungespeichert bleibt sichtbar"
        assert window.header.bounds.text().endswith("in"), "die Anzeigeeinheit bleibt sichtbar"
        assert window.header.printer.text().endswith("220 mm"), "das Druckermodell bleibt sichtbar"


def test_a_header_label_keeps_its_text_for_tooltip_and_assistance(
    qt_app: QApplication,
) -> None:
    """Die Kürzung bewahrt das wichtige Ende und den ganzen zugänglichen Text.

    Rechts gekürzt wurde aus „… 220 mm" ein Anfang ohne Modellende. Mittig
    gekürzt bleiben Einheit, Stern und unterscheidender Namenszusatz stehen.
    Der sichtbare Rest ersetzt den Volltext nicht: Tooltip und Accessible Name
    tragen ihn weiter.
    """
    from app.ui.header import _EphemeralLabel

    label = _EphemeralLabel("Allgemeiner FDM-Drucker 220 mm", tail_words=2)
    label.show()
    label.resize(label.minimumWidth() + 10, 20)
    QApplication.processEvents()
    assert label.full_text() == "Allgemeiner FDM-Drucker 220 mm", "der ganze Text bleibt bekannt"
    assert label.toolTip() == label.full_text(), "und er steht im Tooltip"
    assert label.accessibleName() == label.full_text(), "und Hilfstechnik liest nicht die Kürzung"
    assert label.focusPolicy() == Qt.FocusPolicy.NoFocus, (
        "die Auskunft erzeugt keinen Tastaturstopp"
    )
    assert label.text().endswith("220 mm"), "das unterscheidende Ende bleibt vollständig sichtbar"
    assert "…" in label.text()

    # **Beide Wege, nicht nur einer.** Der Text kommt im Betrieb über
    # ``setText`` und nur im Test aus dem Konstruktor; eine Probe, die den
    # zweiten prüft und den ersten nicht, ließ die Mutation „Tooltip aus
    # setText entfernen" grün durchgehen.
    label.setText("Ein anderer, ebenfalls sehr langer Druckername")
    assert label.full_text() == "Ein anderer, ebenfalls sehr langer Druckername"
    assert label.toolTip() == label.full_text(), "auch der gesetzte Text steht im Tooltip"
    assert label.accessibleName() == label.full_text()

    title = _EphemeralLabel(
        "Ein sehr langes Beispielprojekt für einen schmalen Bildschirm*",
        protected_end="*",
    )
    title.show()
    title.resize(max(30, title.minimumWidth()), 20)
    QApplication.processEvents()
    assert title.text() != title.full_text(), "der Volltext darf nicht nur unsichtbar überstehen"
    assert "…" in title.text()
    assert title.text().endswith("*"), "die Ungespeichert-Markierung bleibt gezeichnet"


def test_a_clean_part_offers_the_way_to_the_slicer(window: MainWindow) -> None:
    """Der letzte Meter: „Keine Befunde." ohne nächsten Schritt war eine Sackgasse.

    Leere Szene: kein Knopf, weil nichts zu übergeben ist. Ein Körper ohne
    Befund: der Bericht sagt „druckbereit" und bietet den Slicer an; der Knopf
    öffnet denselben Dialog wie *Datei → Druckeinstellungen …*
    (Review 02.09.2026).

    Vom 20. bis zum 21.09.2026 stand an jedem Körper mit belegten Flächen ein
    Hinweis auf die Analysekarte „Formabweichung", und kein Quader erreichte
    mehr „druckbereit". Seither ist die Formabweichung ein Befund mit Maß, der
    nur steht, wo belegte Punkte neben der Form liegen
    (``evaluate.check_form_deviation``) — an einem Quader liegt keiner.
    """
    report = window.report
    assert not report.to_slicer.isVisibleTo(report)
    assert report.summary.text() == "Keine Befunde."

    window.session.apply(
        "Kasten",
        [
            OperationDraft(
                op="create_box",
                inputs=(),
                params={"width": 20.0, "depth": 20.0, "height": 10.0},
            )
        ],
    )
    window.session.wait_for_idle()
    QApplication.processEvents()

    assert report.to_slicer.isVisibleTo(report)
    assert report.summary.text() == "Keine Befunde. Das Teil ist druckbereit."
    assert report.list.count() == 0
    opened: list[str] = []
    window.action_print_settings = lambda: opened.append("dialog")  # type: ignore[method-assign]
    report.slicerRequested.disconnect()
    report.slicerRequested.connect(window.action_print_settings)
    report.to_slicer.click()
    assert opened == ["dialog"]


def test_palette_twins_do_not_look_alike(window: MainWindow) -> None:
    """Vier Paare tragen denselben Titel; die Palette zeigt beide mit ihrem Satz.

    Wer „quader" tippte, sah zweimal „Quader anlegen", und der Unterschied
    stand nur im Tooltip (Review 02.09.2026).
    """
    from app.core.registry import MENU_TWINS
    from app.ui.command_palette import CommandPalette

    palette = CommandPalette(parent=window)
    for hidden, visible in MENU_TWINS.items():
        palette._refilter(str(window._op_actions[visible].text()).replace("&", ""))
        rows = [palette.list.item(row).text() for row in range(palette.list.count())]
        both = [
            row
            for row in rows
            if row.split(chr(10))[0].split(chr(9))[0]
            in {str(spec.title) for spec in (REGISTRY.get(hidden), REGISTRY.get(visible))}
        ]
        assert len(both) >= 2, (hidden, visible, rows[:6])
        assert len(set(both)) == len(both), both
        assert all(chr(10) in row for row in both), both


def test_command_palette_shows_explanations_without_repeating_window_titles(
    window: MainWindow,
) -> None:
    from app.ui.command_palette import CommandPalette, first_sentence

    entries = window.palette_rows()
    commands = window.window_commands()
    palette = CommandPalette(entries, parent=window)
    entry = next(
        candidate
        for candidate in entries
        if candidate.available
        and candidate.name not in commands
        and str(candidate.doc).strip()
        and first_sentence(str(candidate.doc)).strip() != str(candidate.title).strip()
    )
    palette._refilter(str(entry.title))
    row = next(
        palette.list.item(index)
        for index in range(palette.list.count())
        if palette.list.item(index).data(Qt.ItemDataRole.UserRole) == str(entry.name)
    )

    assert row.text().splitlines()[1] == first_sentence(str(entry.doc)).strip()

    for key, tool in window.tools.tools().items():
        tool_entry = next(candidate for candidate in entries if candidate.name == f"tool.{key}")
        assert tool_entry.doc == str(tool.hint), key
        assert tool_entry.doc.strip() and tool_entry.doc != tool_entry.title, key

    for name in ("file.part_adopt", "file.part_share"):
        part_entry = next(candidate for candidate in entries if candidate.name == name)
        assert part_entry.doc.strip() and part_entry.doc != part_entry.title, name

    window_entry = next(candidate for candidate in entries if candidate.name == "view.bed")
    action = window._palette_actions[window_entry.name]
    assert window_entry.doc == action.statusTip()
    assert window_entry.doc != window_entry.title
    palette._refilter(str(window_entry.title))
    window_row = next(
        palette.list.item(index)
        for index in range(palette.list.count())
        if palette.list.item(index).data(Qt.ItemDataRole.UserRole) == str(window_entry.name)
    )
    assert window_row.text().splitlines()[1] == first_sentence(str(window_entry.doc)).strip()
    tooltip_lines = window_row.toolTip().splitlines()
    assert tooltip_lines == [str(window_entry.title), str(window_entry.doc)]


def test_a_question_of_several_words_still_finds_something(window: MainWindow) -> None:
    """„ecke abrunden" gab eine leere Liste, obwohl „abrunden" das *Verrunden*
    findet — die Suche verlangte alle Wörter, und die Leerantwort bot keinen
    Weg (Bedienweg-Durchsicht 14.09.2026: sieben von 71 Kundenwörtern leer).
    Erst wenn nichts auf alle passt, genügt eines; die Zeile darüber sagt es,
    und wer ein Wort tippt, das ganz passt, sieht sie nicht.

    „ecke abrunden" selbst passt seit den Kundenwörtern je Sprache ganz
    (Durchsicht 0.5.1: „Ecken rund" am *Verrunden*); die dritte Runde prüft
    deshalb ein Wort, das nirgends steht, neben einem, das trifft.
    """
    from app.ui.command_palette import CommandPalette

    heading = str(tr("Kein Befehl passt auf alle Wörter — das Folgende passt auf einzelne."))
    palette = CommandPalette(parent=window)

    palette._refilter("ecke abrunden")
    assert palette.list.item(0).data(Qt.ItemDataRole.UserRole) == "fillet_edges"

    palette._refilter("zacken abrunden")
    rows = [palette.list.item(row) for row in range(palette.list.count())]
    assert rows and rows[0].text() == heading, [row.text() for row in rows[:3]]
    assert not rows[0].flags() & Qt.ItemFlag.ItemIsSelectable, "die Überschrift ist kein Befehl"
    names = [row.data(Qt.ItemDataRole.UserRole) for row in rows[1:]]
    assert "fillet_edges" in names, names
    assert palette.list.currentRow() >= 1, "vorausgewählt ist ein Befehl, nicht die Überschrift"

    palette._refilter("abrunden")
    assert palette.list.item(0).text() != heading, "ein Wort, das ganz passt, braucht keine"
    assert palette.list.item(0).data(Qt.ItemDataRole.UserRole) == "fillet_edges"


def test_the_build_plate_hides_in_one_step(window: MainWindow) -> None:
    """Robert, 02.09.2026: „eine Option, wo man schnell hinkommt, um die Druckplatte auszublenden".

    Ein Haken im Ansichtsmenü mit Kürzel, in der Palette gelistet, und der
    Zustand bleibt in den Einstellungen — gleich, ob Menü, Palette oder Taste
    ihn umlegen.
    """
    assert window.viewport.bed_visible
    assert window.settings.bed_visible
    assert window._bed_action.isChecked()

    window.action_toggle_bed()

    assert not window.viewport.bed_visible
    assert not window.settings.bed_visible
    assert not window._bed_action.isChecked()
    assert window.window_commands()["view.bed"][1] == "Ctrl+Shift+D"

    window._bed_action.trigger()

    assert window.viewport.bed_visible
    assert window.settings.bed_visible
    assert window._bed_action.isChecked()


def test_closing_the_measure_tool_takes_the_dimensions_with_it(window: MainWindow) -> None:
    """Ein Maß überlebt sein Werkzeug nicht (Robert, 03.09.2026).

    Vorher schaltete das Schließen nur den Modus ab: Die Linien blieben im
    Bild stehen, und der einzige Knopf, mit dem man sie loswird, war mit der
    Leiste verschwunden. Ein Maß ist eine Auskunft über das Teil und kein
    Dokumentzustand (Regel 2) — dieselbe Entscheidung wie bei der Trennlinie.
    """
    from app.core.geom.measure import Measurement

    window.tools.toggle("measure")
    window.viewport.measurements.add(
        Measurement(kind="distance", value=12.0, points=((0.0, 0.0, 0.0), (12.0, 0.0, 0.0)))
    )
    assert len(window.viewport.measurements.entries) == 1

    window.tools.toggle("measure")

    assert window.viewport.measurements.entries == [], "das Schließen räumt die Maße weg"
    assert window.measure_bar.mode.currentData() == "off", "und schaltet das Messen ab"


def test_measuring_switches_the_view_to_parallel_and_back(window: MainWindow) -> None:
    """§18.1 sagt es ohne Vorbehalt: orthografisch ist beim Messen Pflicht (RM-142).

    Der Werkzeugweg setzte nur den Messmodus; die vorhandene Umschaltung
    gehörte dem Skizzeneditor. Wer perspektivisch arbeitete und zu messen
    anfing, setzte seine Punkte in einem Bild, in dem zwei gleich lange
    Strecken verschieden lang aussehen — die Maße stimmten, das Zielen nicht.
    """
    window.action_projection("perspective")

    window.tools.toggle("measure")

    assert window.viewport.projection == "orthographic"
    assert [
        action.data() for action in window._projection_group.actions() if action.isChecked()
    ] == ["orthographic"], "das Menü sagt, was gilt"

    window.tools.toggle("measure")

    assert window.viewport.projection == "perspective", "und danach steht die Ansicht wie vorher"


def test_the_measuring_detour_leaves_the_stored_setting_alone(window: MainWindow) -> None:
    """Messen stellt vorübergehend um, es entscheidet nichts (RM-142).

    ``settings.projection`` ist die Wahl des Nutzers. Sie zu überschreiben
    hieße, aus einem Werkzeug eine Einstellung zu machen — dieselbe Trennung
    wie beim Skizzeneditor.
    """
    window.action_projection("perspective")

    window.tools.toggle("measure")

    assert window.settings.projection == "perspective"


def test_changing_the_kind_of_measurement_keeps_the_way_back(window: MainWindow) -> None:
    """Von *Abstand* auf *Wandstärke* ist kein Verlassen (RM-142).

    Ein zweites Merken überschriebe die Projektion, zu der der Nutzer
    zurückwill — er wäre nach dem Messen orthografisch, ohne es je gewählt zu
    haben.
    """
    window.action_projection("perspective")
    window.tools.toggle("measure")

    window.measure_bar.mode.setCurrentIndex(2)
    assert window.measure_bar.mode.currentData() == "thickness", "sonst prüft der Test nichts"
    window.tools.toggle("measure")

    assert window.viewport.projection == "perspective"


def test_choosing_a_projection_while_measuring_wins(window: MainWindow) -> None:
    """Die Pflicht gilt dem Werkzeug, nicht gegen den Nutzer (RM-142).

    Wer während des Messens ausdrücklich umschaltet, meint es — und bekäme
    beim Schließen des Werkzeugs sonst einen Zustand zurück, den er eine
    Minute vorher verworfen hat.
    """
    window.action_projection("orthographic")
    window.tools.toggle("measure")

    window.action_projection("perspective")
    window.tools.toggle("measure")

    assert window.viewport.projection == "perspective", "die spätere Wahl ist das Rückkehrziel"


def test_the_view_settings_are_still_there_after_a_restart(qt_app: QApplication) -> None:
    """Darstellung, Schattierung und Projektion überleben das Schließen.

    **Der Befund (Robert, 03.09.2026):** „sollte leicht durchsichtig sein seit
    dem letzten update". Der Modus *war* eingestellt gewesen — und beim
    nächsten Start stand wieder *Massiv* da. `UiSettings` führte Navigation,
    Thema, Sprache, Einheit und ein Dutzend Slicer-Profile; diese drei nicht.
    Das ist die Sorte Fehler, die man für die eigene Erinnerung hält.

    Geprüft wird die ganze Kette: Der Menüweg schreibt in die Einstellungen,
    ein **neu gebautes** Fenster mit denselben Einstellungen wendet sie an,
    und die Häkchen zeigen, was gilt.
    """
    window = MainWindow(Session(), UiSettings())
    assert window.settings.display_mode == "solid", "die Vorgabe"

    window.action_display_mode("transparent")
    window.action_shading("smooth")
    window.action_projection("orthographic")

    assert window.settings.display_mode == "transparent"
    assert window.settings.shading == "smooth"
    assert window.settings.projection == "orthographic"
    assert window.viewport.display_mode == "transparent", "und die Ansicht folgt sofort"

    gemerkt = UiSettings(
        display_mode=window.settings.display_mode,
        shading=window.settings.shading,
        projection=window.settings.projection,
    )
    zweites = MainWindow(Session(), gemerkt)
    # Denselben Weg wie ``app.py``: Der Bau stellt das Fenster hin, und
    # ``_apply_settings`` gibt ihm, was gemerkt wurde. Ein Test, der das
    # ausließe, prüfte einen Start, den es nicht gibt.
    zweites._apply_settings()
    assert zweites.viewport.display_mode == "transparent", (
        "der neue Start nimmt den gemerkten Modus"
    )
    angehakt = [action.data() for action in zweites._mode_group.actions() if action.isChecked()]
    assert angehakt == ["transparent"], f"und das Menü zeigt ihn: {angehakt}"
    assert [a.data() for a in zweites._shading_group.actions() if a.isChecked()] == ["smooth"]
    assert [a.data() for a in zweites._projection_group.actions() if a.isChecked()] == [
        "orthographic"
    ]


def test_the_candidates_are_lit_while_the_question_stands(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§21.3 wörtlich: die Kandidaten stehen hervorgehoben da.

    Bis zum 03.09.2026 fehlte genau das. Wer eine Projektdatei öffnete, deren
    Merkmalsverweis mehrdeutig geworden war, bekam ``hole_1``, ``hole_2``,
    ``hole_3`` zur Wahl und sollte zwischen Bohrungen entscheiden, die er
    nicht sieht. Die Auskunft lag im Kern bereit und wurde nie abgerufen.
    """
    from app.ui.dialogs import AskDialog
    from app.ui.session import AskRequest

    gezeigt: list[tuple[tuple[tuple[str, str], ...], object]] = []
    monkeypatch.setattr(
        window.viewport,
        "show_candidates",
        lambda candidates=(), emphasis=None: gezeigt.append((tuple(candidates), emphasis)),
    )
    monkeypatch.setattr(AskDialog, "exec", lambda self: AskDialog.DialogCode.Accepted)

    request = AskRequest(
        question="Welches Merkmal ist gemeint?",
        choices=["hole_1", "hole_2"],
        candidates=(("obj_1", "hole_1"), ("obj_1", "hole_2")),
    )
    window._on_ask(request)

    assert gezeigt, "während der Frage leuchtet etwas"
    erste = gezeigt[0][0]
    assert erste == (("obj_1", "hole_1"), ("obj_1", "hole_2"))
    assert gezeigt[-1] == ((), None), "und nach der Antwort ist es weg"
    assert request.answer == "hole_1"


def test_nothing_is_lit_for_a_question_without_candidates(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Einheitenfrage beim Einlesen hat keine Kandidaten — und leuchtet nicht."""
    from app.ui.dialogs import AskDialog
    from app.ui.session import AskRequest

    gezeigt: list[object] = []
    monkeypatch.setattr(
        window.viewport,
        "show_candidates",
        lambda candidates=(), emphasis=None: gezeigt.append(candidates),
    )
    monkeypatch.setattr(AskDialog, "exec", lambda self: AskDialog.DialogCode.Rejected)

    window._on_ask(AskRequest(question="Millimeter oder Zoll?", choices=["mm", "in"]))

    assert gezeigt == [], "ohne Kandidaten wird die Ansicht nicht angefasst"


def test_the_marked_row_is_the_emphasised_candidate(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Was gleich die Antwort wäre, leuchtet deckender als die übrigen.

    Und wo dieselbe Kennung an mehreren Körpern steht — die Skizzenebene, die
    auf jeder planaren Fläche zu Hause sein darf —, wird keine betont: Die
    Frage entscheidet dort über die Kennung, nicht über den Fundort.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidgetItem

    gezeigt: list[object] = []
    monkeypatch.setattr(
        window.viewport,
        "show_candidates",
        lambda candidates=(), emphasis=None: gezeigt.append(emphasis),
    )

    window._ask_candidates = (("obj_1", "face_1"), ("obj_2", "face_1"), ("obj_1", "face_2"))

    eindeutig = QListWidgetItem("face_2")
    eindeutig.setData(Qt.ItemDataRole.UserRole, "face_2")
    window._emphasise_candidate(eindeutig, None)
    assert gezeigt[-1] == ("obj_1", "face_2")

    mehrdeutig = QListWidgetItem("face_1")
    mehrdeutig.setData(Qt.ItemDataRole.UserRole, "face_1")
    window._emphasise_candidate(mehrdeutig, None)
    assert gezeigt[-1] is None, "zwei Fundorte, eine Frage — keiner wird betont"


@pytest.mark.parametrize("standalone", [3, 4])
def test_feature_roof_counts_only_its_own_cavity_children(qt_app, monkeypatch, standalone):
    """Gleich große freie Senkungen zählen eine untergeordnete Senkung nicht mit."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.perceive.features import detect
    from app.core.perceive.relations import cavity_chains
    from app.core.scene import EvaluationResult
    from app.core.types import Scene
    from app.ui.labels import feature_measure, feature_name
    from app.ui.panels import BUNDLE_FROM, ObjectTree

    bodies = []
    for index in range(standalone + 1):
        profile = (
            [[12, 0], [12, 8.5], [5.5, 8.5], [3, 6], [3, 0], [12, 0]]
            if index == standalone
            else [[12, 0], [12, 2.5], [5.5, 2.5], [3, 0], [12, 0]]
        )
        body = trimesh.creation.revolve(profile, sections=48)
        body.apply_translation([index * 30, 0, 0])
        bodies.append(body)
    mesh = MeshData.of(trimesh.util.concatenate(bodies))
    features = detect(mesh)
    cones = [feature for feature in features.values() if feature.kind == "cone"]
    assert len(cones) == standalone + 1
    assert len({(feature_name(one.id, one), feature_measure(one)) for one in cones}) == 1
    chains = cavity_chains(features, mesh)
    assert len(chains) == 1 and chains[0][-1].kind == "cone"
    nested = chains[0][-1].id
    tree = ObjectTree()
    monkeypatch.setattr(tree, "_want_preview", lambda *_args: None)
    obj = SceneObject(id="part", name="Teil", mesh=mesh, features=features)
    tree.show_scene(EvaluationResult(Scene(objects={obj.id: obj})))
    top = tree.tree.topLevelItem(0)
    bore = chains[0][0]
    bore_row = next(
        top.child(index)
        for index in range(top.childCount())
        if top.child(index).data(1, Qt.ItemDataRole.UserRole) == bore.id
    )
    assert bore_row.text(0) == f"{feature_name(bore.id, bore)} mit Senkung"
    assert bore_row.child(0).data(1, Qt.ItemDataRole.UserRole) == nested
    assert "mit Senkung" in bore_row.data(0, Qt.ItemDataRole.AccessibleDescriptionRole)
    roofs = [
        top.child(index)
        for index in range(top.childCount())
        if top.child(index).text(0).startswith("Senkung (")
    ]
    if standalone < BUNDLE_FROM:
        assert roofs == []
    else:
        assert len(roofs) == 1
        assert roofs[0].text(0) == f"Senkung ({standalone})"
        assert roofs[0].childCount() == standalone
        assert all(
            roofs[0].child(index).data(1, Qt.ItemDataRole.UserRole) != nested
            for index in range(roofs[0].childCount())
        )


def test_many_features_of_one_kind_stand_under_one_roof(window: MainWindow) -> None:
    """Eine STEP-Datei bringt Dutzende gleichnamige Verrundungen mit.

    Gemessen an ``build_tray_v3.step`` (03.09.2026): 234 erkannte Merkmale,
    davon rund fünfzig sichtbare Zeilen „Hohlkehle R13,98 mm" untereinander.
    Der Prüfbericht daneben bündelt dieselbe Menge längst zu einer Zeile; der
    Objektbaum tat es nur für Merkmale aus einem Baustein.

    Gebaut wird die Merkmalsmenge hier von Hand: Geprüft wird die **Anzeige**,
    nicht die Erkennung — und kein Modell des Korpus hat vier gleichnamige.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))

    fillets = {
        f"fillet_{index}": Feature(
            id=f"fillet_{index}",
            kind="fillet",
            params={"radius": 13.98, "recess": True},
            provenance="detected",
        )
        for index in range(6)
    }
    einzeln = next(iter(entry.features.values()))
    entry = dataclasses.replace(entry, features={**fillets, einzeln.id: einzeln})
    result = dataclasses.replace(
        result, scene=dataclasses.replace(result.scene, objects={object_id: entry})
    )

    tree = window.object_tree
    tree.show_scene(result, window.session.project.document)
    top = tree.tree.topLevelItem(0)
    assert top is not None
    top.setExpanded(True)
    kinder = [top.child(index) for index in range(top.childCount())]
    beschriftungen = [kind.text(0) for kind in kinder if kind is not None]

    dach = next((kind for kind in kinder if kind is not None and "(6)" in kind.text(0)), None)
    assert dach is not None, f"sechs gleichnamige Merkmale, kein Dach darüber: {beschriftungen}"
    assert dach.childCount() == 6, "unter dem Dach stehen alle sechs"
    assert not dach.isExpanded(), "zugeklappt — sonst wäre nichts gewonnen"
    assert len(beschriftungen) == 2, (
        f"ein Dach und das einzelne Merkmal, sonst nichts: {beschriftungen}"
    )
    assert dach.toolTip(0) and dach.data(0, Qt.ItemDataRole.AccessibleDescriptionRole), (
        "Regel 18: der Hinweis steht auch für den Bildschirmleser da"
    )

    tree.select_feature(object_id, "fillet_3")
    assert dach.isExpanded(), "wer ein Merkmal darin wählt, sieht es"


def test_every_bundle_in_the_tree_selects_what_it_bundles(window: MainWindow) -> None:
    """Der Abnahmenachweis zu P6: jede der drei Bündelungen wählt ihre Glieder.

    Robert am 07.09.2026, auf die Rückfrage: „nicht nur bei Schraubenloch mit
    Senkung ist es so, bei allen Dach einträgen." Der Baum bündelt an drei
    Stellen, und keine davon wählte etwas — die zwei Dächer tragen ihre
    Merkmalskennung leer, und bei einer Bohrung mit Senkung als Kind wählte
    der Klick nur die Bohrung.

    Geprüft wird ``selected_features``, weil dort die Menge entsteht, aus der
    Panel, Bild und Handlungen sie beziehen (``featuresSelected`` →
    ``select_feature_refs``). Das Baustein-Dach steht in
    ``test_analysis_ui.py``: Es braucht einen echten Bausteinlauf, und der hat
    seinen Platz dort, wo ``_insert_a_thread`` schon steht.
    """
    from PySide6.QtWidgets import QTreeWidgetItem

    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    tree = window.object_tree

    # --- Gleichart-Dach: sechs Hohlkehlen unter einer Zeile ------------------
    fillets = {
        f"fillet_{index}": Feature(
            id=f"fillet_{index}",
            kind="fillet",
            params={"radius": 13.98, "recess": True},
            provenance="detected",
        )
        for index in range(6)
    }
    einzeln = next(iter(entry.features.values()))
    gefuellt = dataclasses.replace(entry, features={**fillets, einzeln.id: einzeln})
    tree.show_scene(
        dataclasses.replace(
            result, scene=dataclasses.replace(result.scene, objects={object_id: gefuellt})
        ),
        window.session.project.document,
    )
    top = tree.tree.topLevelItem(0)
    assert top is not None
    top.setExpanded(True)
    dach = next(
        kind
        for index in range(top.childCount())
        if (kind := top.child(index)) is not None and "(6)" in kind.text(0)
    )
    tree.tree.clearSelection()
    dach.setSelected(True)
    assert set(tree.selected_features()) == {(object_id, name) for name in fillets}, (
        "das Gleichart-Dach wählt alle sechs"
    )
    assert tree.selected_feature() is None, "es selbst ist keines — die Dachzeile bleibt eine"

    # --- Bohrung mit ihrer Senkung als Kind ---------------------------------
    # Von Hand zusammengehängt: Ob ``cavity_chains`` die Senkung unter ihre
    # Bohrung stellt, ist anderswo geprüft; hier geht es um die Auswahl an
    # einer Zeile, die ein Kind hat. ``plate_holes.stl`` hat keine solche —
    # ein Test, der das stillschweigend überspringt, prüft nichts.
    bohrung = next(
        kind
        for index in range(top.childCount())
        if (kind := top.child(index)) is not None
        and str(kind.data(1, Qt.ItemDataRole.UserRole) or "").startswith("hole_")
    )
    senkung = QTreeWidgetItem(["Senkung", ""])
    senkung.setData(0, Qt.ItemDataRole.UserRole, object_id)
    senkung.setData(1, Qt.ItemDataRole.UserRole, "recess_1")
    bohrung.addChild(senkung)
    fuehrend = (object_id, str(bohrung.data(1, Qt.ItemDataRole.UserRole)))
    tree.tree.clearSelection()
    bohrung.setSelected(True)
    assert tree.selected_features() == (fuehrend, (object_id, "recess_1")), (
        "die Kette wählt beide Glieder, das führende vorn"
    )
    assert tree.selected_feature() == fuehrend[1], (
        "und die Felder zeigen die Maße des führenden Glieds"
    )

    # --- und eine Körperzeile bleibt eine Körperzeile ------------------------
    tree.tree.clearSelection()
    top.setSelected(True)
    assert tree.selected_features() == (), (
        "wer einen Halter markiert, hat nicht seine achtzig Bohrungen gewählt"
    )


def test_one_line_stands_for_many_bodies_and_asks_which(window: MainWindow) -> None:
    """Sechs Körper, ein Satz — und die Wahl bleibt erhalten.

    Gemessen an ``Wizard+Tower+Staunton+Elegoo.3mf`` (03.09.2026): 15 Befunde,
    davon zwölf aus zwei Kennungen über dieselben sechs Körper. Sechsmal
    derselbe Satz mit anderem Namen dahinter — was der Kunde liest, ist eine
    Wand. Gebündelt wird über die Körpergrenze — erst für zwei Kennungen
    (``ACROSS_BODIES``), seit dem 11.09.2026 für jede (Robert: „gleiche
    Meldungen zusammenfassen und anzahl dann davor in Klammer anzeigen") —,
    und die Zeile führt die Körper mit, damit die Handlung fragen kann, für
    welche sie gelten soll (Entscheidung Robert).
    """
    report = window.report
    report.show_result(None)
    report.add_findings(
        [
            Finding(
                code="perceive.too_large",
                severity="info",
                message="Für die Merkmalserkennung ist dieses Modell zu groß.",
                object_id=f"obj_{index}",
                values={"triangles": 200000 + index, "limit": 200000},
            )
            for index in range(1, 7)
        ]
    )

    from app.ui.panels import _BODIES_ROLE

    zeilen = [report.list.item(row) for row in range(report.list.count())]
    assert len(zeilen) == 1, f"sechs Befunde, eine Zeile — gezählt: {len(zeilen)}"
    zeile = zeilen[0]
    assert zeile is not None
    assert zeile.text().startswith("(6) "), zeile.text()
    assert "obj_1" not in zeile.text(), (
        "eine Zeile für sechs Körper nennt keinen einzelnen — sonst verschweigt sie fünf"
    )
    assert zeile.data(_BODIES_ROLE) == tuple(f"obj_{index}" for index in range(1, 7))


def test_the_same_operation_on_many_bodies_is_one_transaction(window: MainWindow) -> None:
    """Regel 16: Ein Undo nimmt die ganze Handlung zurück, nicht ein Sechstel.

    ``decimate_mesh`` verbraucht einen Körper; die Handlung der Sammelzeile
    meint mehrere. ``run_operation(..., on_bodies=...)`` baut deshalb einen
    Schritt je Körper und wendet sie in **einer** Transaktion an — der Dialog
    fragt seine Werte dabei einmal für alle.
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    bodies = tuple(result.scene.objects)
    assert len(bodies) >= 2, f"zwei Körper für den Fall, gefunden: {len(bodies)}"
    transactions_before = len(window.session.project.document.transactions)
    steps_before = len(window.session.project.document.ops)

    window.run_operation(REGISTRY.get("decimate_mesh"), on_bodies=bodies[:2])
    dialog = window._op_dialog
    assert dialog is not None, "der Dialog fragt die Werte — einmal für beide"
    dialog.accept()
    window.session.wait_for_idle()

    document = window.session.project.document
    assert len(document.ops) == steps_before + 2, "ein Schritt je Körper"
    assert len(document.transactions) == transactions_before + 1, (
        "und alle in einer Transaktion — sonst nimmt Strg+Z nur den letzten zurück"
    )
    assert [tuple(step.inputs) for step in document.ops[-2:]] == [
        (bodies[0],),
        (bodies[1],),
    ], "jeder Schritt trifft genau seinen Körper"


def test_two_asking_threads_do_not_steal_each_others_candidates(session: Session) -> None:
    """Die Ansage gehört dem Faden, der sie gemacht hat — nicht der Sitzung.

    ``announce_candidates`` merkt sich, was die **nächste** Frage zur Wahl
    stellt, und ``ask_from_worker`` holt es ab. Der Weg dazwischen ist
    ``ctx.ask``, und die trägt nur Frage und Antworten (Regel 21) — deshalb
    steht es nicht an der Frage, sondern daneben.

    **Solange nur die Auswertung fragte, genügte ein Platz.** Er liegt auf der
    Sitzung, und mit einem zweiten fragenden Faden — 3d-druck-85 stellt am
    03.09.2026 das Einlesen auf einen Arbeiter um — reicht das nicht mehr: Die
    Einheitenfrage des Einlesens („Millimeter oder Zoll?") holte sich die
    Kandidaten der Verweisfrage ab, und die Verweisfrage bekäme dann keine.
    Beides ist falsche Auskunft: einmal leuchten Bohrungen zu einer Frage, die
    von Einheiten handelt, einmal leuchtet zu einer Frage über Bohrungen nichts.

    Ein Platz **je Faden** löst es an der Wurzel, ohne die Ask-Schnittstelle
    anzufassen: Wer ansagt und wer fragt, ist im selben Vorgang derselbe Faden
    (``orphans.check`` ruft beides unmittelbar nacheinander), und zwei Vorgänge
    kommen sich nicht mehr in die Quere.
    """
    import threading

    gestellt: dict[str, tuple[tuple[str, str], ...]] = {}
    bereit = threading.Event()

    def antworten(request: AskRequest) -> None:
        gestellt[request.question] = request.candidates
        request.reply(request.choices[0])

    # **Direkt verbunden**, damit der Slot im *fragenden* Faden läuft. Über die
    # Warteschlange bräuchte er die Ereignisschleife des Hauptfadens, und die
    # steht hier still — ``ask_from_worker`` wartete dann bis zum Zeitlimit.
    session.askRequested.connect(antworten, Qt.ConnectionType.DirectConnection)

    def fremder_faden() -> None:
        bereit.wait(timeout=5.0)
        session.ask_from_worker("Millimeter oder Zoll?", ["mm", "in"])

    zweiter = threading.Thread(target=fremder_faden)
    zweiter.start()
    try:
        session.announce_candidates((("obj_1", "hole_1"), ("obj_1", "hole_2")))
        bereit.set()
        zweiter.join(timeout=5.0)
        session.ask_from_worker("Welches Merkmal ist gemeint?", ["hole_1", "hole_2"])
    finally:
        bereit.set()
        zweiter.join(timeout=5.0)

    assert gestellt["Millimeter oder Zoll?"] == (), "die fremde Frage hebt nichts hervor"
    assert gestellt["Welches Merkmal ist gemeint?"] == (
        ("obj_1", "hole_1"),
        ("obj_1", "hole_2"),
    ), "und die eigene bekommt, was für sie angesagt war"


def test_a_failed_save_keeps_the_last_recovery(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gesamtreview 05.09.2026, UI-06: ``save_project`` räumte die Sicherung,
    bevor ``save`` zurückgekommen war. Ein volles oder gesperrtes Laufwerk
    ließ die Projektdatei auf dem alten Stand, die Sicherung war weg, und die
    neuen Änderungen lebten nur noch im Speicher."""
    from app.core.errors import AppError, FileWriteError
    from app.core.scene.project import find_recovery, write_autosave
    from app.ui import session as session_module

    named = tmp_path / "projekt.p3d"
    window.session.save_project(named)
    write_autosave(window.session.project, named)
    window.session._dirty = True

    def refuse(_project, target):
        raise FileWriteError(target=target.name, detail="das Laufwerk ist voll")

    monkeypatch.setattr(session_module, "save", refuse)
    with pytest.raises(AppError):
        window.session.save_project(named)

    assert find_recovery(named) is not None, "die letzte Sicherung bleibt, bis die Datei steht"
    assert window.session._dirty, "und das Dokument gilt weiter als geändert"


def test_the_parameter_dialog_refuses_bounds_that_are_not_finite(qt_app: QApplication) -> None:
    """Gesamtreview 05.09.2026, UI-26: ``float("inf")`` und ``float("nan")``
    gingen als Grenze durch; der Parameter kam ins Dokument, und Speichern
    scheiterte ohne Meldung."""
    from app.ui.dialogs import ParameterDialog

    dialog = ParameterDialog({})
    dialog.name_field.setText("hoehe")
    assert dialog.validation_problem() is None

    for text in ("inf", "-inf", "nan", "NaN"):
        dialog.maximum_field.setText(text)
        assert dialog.validation_problem() is not None, f"{text!r} ist keine Grenze"
    dialog.maximum_field.setText("120")
    assert dialog.validation_problem() is None


def test_a_discarded_sketch_makes_undo_available_even_in_an_empty_project(
    window: MainWindow,
) -> None:
    """Gesamtreview 05.09.2026, UI-10: Die Statuszeile versprach Strg+Z, aber
    die Aktion hing allein an ``history.can_undo`` — in einem frischen Projekt
    blieb sie grau, und ihr Auslösen holte nichts zurück."""
    from app.core.sketch import shapes

    assert not window.session.history.can_undo, "der Verlauf ist leer — das ist der Fall"
    window.start_sketch("sketch_extrude")
    panel = window._sketch_panel
    assert panel is not None
    panel.canvas.insert_shape(shapes.rectangle(40.0, 20.0))
    drawn = panel.sketch_text()
    assert drawn

    window.finish_sketch(keep=False)

    assert window._discarded_sketch is not None
    assert window.undo_action.isEnabled(), "der versprochene Rückweg ist bedienbar"
    window.action_undo()
    assert window._sketch_panel is not None, "Strg+Z holt die Zeichnung zurück"
    assert window._sketch_panel.sketch_text() == drawn
    window.finish_sketch(keep=False)


def test_a_finding_becomes_an_error_with_its_cause() -> None:
    """Der Fehlerbericht aus dem Prüfbericht nennt die Ursache, nicht nur den Titel.

    ``report_error`` schreibt ``str(error)`` in den Bericht, und der ist ohne
    ``detail`` allein der Titel. Der Kundenbericht S-20260906-9ca141 (0.3.4)
    stand deshalb zweimal bei „Im Programm ist ein unerwarteter Fehler
    aufgetreten", während die Ausnahmeart im Befund lag. ``as_error`` nimmt
    sie jetzt mit — und nur, wo es eine gibt.
    """
    from app.ui.panels import as_error

    crashed = Finding(
        code="op.load.InternalError",
        severity="error",
        message=tr("Im Programm ist ein unerwarteter Fehler aufgetreten."),
        op_id=1,
        values={"detail": "TypeError: bounds of an empty mesh", "operation": "load"},
    )
    error = as_error(crashed)
    assert error.detail == "TypeError: bounds of an empty mesh"
    assert "TypeError: bounds of an empty mesh" in str(error)

    plain = Finding(code="ingest.very_large", severity="warning", message=tr("Fein vernetzt."))
    assert as_error(plain).detail is None


def test_a_relief_for_a_vanished_body_is_announced_instead_of_started(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zwischen Ablegen und Lesen kann ein Undo den Zielkörper entfernt haben (UI-04).

    Dann öffnet sich kein Dialog auf ein Objekt, das es nicht gibt; die
    Statuszeile sagt, was zu tun ist. Ein lebender Körper bekommt sein Relief.
    """
    calls: list[dict[str, Any]] = []
    announcements: list[str] = []
    monkeypatch.setattr(window, "run_operation", lambda spec, **kwargs: calls.append(kwargs))
    monkeypatch.setattr(window, "announce", announcements.append)

    window._dropped_image_ready("obj_999", ("src_1", "image"))
    assert calls == []
    assert announcements and "Relief" in announcements[0]

    session = window.session
    assert session.apply("Ein Körper", [OperationDraft(op="create_box")])
    assert session.wait_for_idle(30000)
    result = session.last_result
    assert result is not None and "obj_1" in result.scene.objects
    window._dropped_image_ready("obj_1", ("src_1", "image"))
    assert calls and calls[0]["on_bodies"] == ("obj_1",)
    assert len(announcements) == 1


def test_the_object_tree_offers_the_filament_where_the_body_stands(
    window: MainWindow,
) -> None:
    """Das Filament steht im Baum und ist dort ein Klick — kein Menüweg.

    Der Weg dorthin führte über *Vorbereiten → Filament zuweisen*, also über
    ein Menü, in dem niemand ein Material sucht: Robert hat ihn am 07.09.2026
    nicht gefunden, auch nachdem die Operationen ihren richtigen Namen trugen.
    Gemessen wird deshalb nicht, dass es die Operation gibt, sondern dass die
    Zeile sie anbietet — Feld, Text und der Klick, der sie auslöst.
    """
    from app.ui.panels import FILAMENT_COLUMN

    assert window.session.apply("Ein Körper", [OperationDraft(op="create_box")])
    assert window.session.wait_for_idle(30000)
    window.object_tree.show_scene(window.session.last_result, window.session.project.document)
    tree = window.object_tree.tree

    assert tree.columnCount() == 3
    assert tree.headerItem().text(FILAMENT_COLUMN) == str(tr("Filament"))
    assert tree.columnWidth(FILAMENT_COLUMN) > 0, "eine Spalte ohne Breite zeigt nichts"

    row = tree.topLevelItem(0)
    assert row is not None
    assert not row.icon(FILAMENT_COLUMN).isNull(), "jede Körperzeile trägt ihr Farbfeld"
    # Regel 18: Die Farbe allein trägt die Bedeutung nicht — der Name steht
    # für Tooltip und Bildschirmleser daneben.
    hint = row.toolTip(FILAMENT_COLUMN)
    assert hint
    assert row.data(FILAMENT_COLUMN, Qt.ItemDataRole.AccessibleDescriptionRole) == hint

    asked: list[tuple[object, object]] = []
    window.object_tree.filamentRequested.connect(lambda obj, feat: asked.append((obj, feat)))
    window.object_tree._on_cell_clicked(tree.indexFromItem(row, FILAMENT_COLUMN))
    assert asked == [("obj_1", None)], "der Klick fragt nach dem Filament des Körpers"

    asked.clear()
    window.object_tree._on_cell_clicked(tree.indexFromItem(row, 0))
    assert asked == [], "ein Klick auf den Namen wählt aus und weist nichts zu"


def test_a_clicked_edge_reaches_the_selection_window(
    window: MainWindow, qt_app: QApplication
) -> None:
    """Der Klick auf eine Kante endet im Auswahlfenster, nicht im Signal.

    Der Anschluss ist die Zusage: ``Viewport.edgePicked`` gibt es, das Panel
    kann Kanten zeigen, und dazwischen liegt eine Zeile in ``__init__``. Ohne
    sie wären beide Hälften einzeln geprüft und grün, und im Fenster
    passierte beim Anklicken einer Kante nichts.

    Gefahren wird deshalb das **Signal der Ansicht** und nicht die Methode
    dahinter — dieselbe Regel wie überall: Wer eine Oberfläche prüft,
    drückt, tippt und wählt.
    """
    from app.core.brep.features import features_of
    from app.core.scene.evaluate import EvaluationResult
    from app.core.types import Scene, SceneObject
    from tests.helpers import exact_kernel

    brep_edit = exact_kernel()
    solid = brep_edit.box(40.0, 30.0, 20.0)
    entry = SceneObject(
        id="block", name="Block", mesh=solid, kind="brep", features=features_of(solid)
    )
    ergebnis = EvaluationResult(scene=Scene(objects={"block": entry}))
    window.session.last_result = ergebnis
    # **Die Ansicht kennt die Szene, sonst kennt sie die Kanten nicht.** Im
    # Betrieb ist das immer so; ohne diese Zeile prüfte der Test eine Lage,
    # die es nicht gibt — und bekäme „diese Kante gibt es nicht mehr".
    window.viewport.show_scene(ergebnis)
    # Und der Baum ebenso — er ist der Eigentümer der Auswahl (§18.5), und
    # ohne die Szene darin wählt `select_object` nichts.
    window.object_tree.show_scene(ergebnis, window.session.project.document)
    kante = next(info for info in brep_edit.edges_of(solid) if info.upright)
    schluessel = brep_edit.edge_key(kante)

    # Der Körper ist gewählt, wenn eine Kante drankommt — sie ist die zweite
    # Stufe, und die erste ist er (§18.5).
    window.object_tree.select_object("block")
    qt_app.processEvents()

    # Beides, wie ``_edge_click`` es tut: erst hervorheben, dann melden.
    window.viewport.select_edge("block", schluessel)
    window.viewport.edgePicked.emit("block", schluessel)

    # Angeboten wird über ``_runs``: Seit dem 10.09.2026 steht kein Knopf mehr
    # in jeder Zeile, sondern einer unten für die Handlung, an der zuletzt
    # jemand etwas angefasst hat.
    knoepfe = [entry.title for entry in window.feature_panel._runs.values()]
    assert str(REGISTRY.get("fillet_edges").title) in knoepfe, (
        "die angeklickte Kante bietet ihre Handlungen an"
    )

    # **Und der Körper bleibt gewählt.** Daran hängt alles, was die Kante
    # anbietet: ``_apply_from_feature_panel`` holt ihren Körper aus dem Baum,
    # und ``selection_depth`` entscheidet, was Escape tut.
    assert window.object_tree.selected() == "block"
    assert window.viewport.selection_depth() == 2

    # **Derselbe Weg, nachdem vorher ein Merkmal gewählt war.** Das ist der
    # gewöhnliche Fall — Körper wählen, Bohrung anklicken, dann eine Kante —
    # und er nimmt im Fenster einen eigenen Zweig: Die Merkmalszeile im Baum
    # muss weichen, ohne die Körperzeile mitzunehmen. Der erste Anlauf räumte
    # über ``select_features([])`` und leerte damit die ganze Auswahl: Die
    # beiden Kantenhandlungen fanden keinen Körper mehr und taten nichts,
    # die Tiefe stand auf 0, und Escape nahm nichts zurück.
    window.object_tree.select_feature("block", "face_1")
    qt_app.processEvents()
    assert window.object_tree.selected_features(), "sonst fährt der Test den Zweig nicht"

    window.viewport.select_edge("block", schluessel)
    window.viewport.edgePicked.emit("block", schluessel)
    qt_app.processEvents()

    assert window.object_tree.selected() == "block", "die Körperzeile bleibt"
    assert window.viewport._selected == "block"
    assert window.viewport.selection_depth() == 2, "sonst ist Escape tot"
    assert not window.object_tree.selected_features(), "die Merkmalszeile weicht"

    # **Und das Fenster überlebt die Kante nicht.** Eine Kante trägt keine
    # Merkmalskennung; die Prüfung, die ein verschwundenes Merkmal räumt,
    # griff bei ihr nie. Nach einer Auswertung, die sie wegnimmt, stünden
    # sonst zwei Knöpfe auf einen Schlüssel, den es nicht mehr gibt — und der
    # nächste Klick endete in einer Absage für etwas, das eben noch dastand.
    verrundet = brep_edit.fillet(solid, 2.0, "vertical")
    danach = EvaluationResult(
        scene=Scene(
            objects={
                "block": SceneObject(
                    id="block",
                    name="Block",
                    mesh=verrundet,
                    kind="brep",
                    features=features_of(verrundet),
                )
            }
        )
    )
    window.session.last_result = danach
    window.viewport.show_scene(danach)
    window._show_scene(danach)
    qt_app.processEvents()
    assert window.viewport.highlighted_edge() is None, "die Ansicht lässt die Kante fallen"
    uebrig = [
        eintrag.title for eintrag in window.feature_panel._runs.values() if eintrag.title in knoepfe
    ]
    assert not uebrig, "und das Fenster überlebt sie nicht"
    # ``isVisibleTo`` und nicht ``isVisible``: Offscreen wird kein Fenster je
    # gezeigt, und die zweite Frage beantwortet Qt deshalb immer mit „nein" —
    # eine Zusicherung, die nicht rot werden kann.
    assert not window.feature_panel._apply.isVisibleTo(window.feature_panel), (
        "der Knopf unten meint nichts mehr"
    )


def test_the_age_of_a_backup_follows_the_application_language(tmp_path: Path) -> None:
    """Das Datum einer alten Sicherung wandert mit der Sprache.

    Die relativen Angaben im Wiederherstellungsdialog — „vor einer Stunde" —
    gingen seit je über ``tr()``. Der Rückfall darüber hinaus nicht: Dort stand
    ein festes ``%d.%m.%Y %H:%M``, also deutsche Reihenfolge in einem
    spanischen Fenster, direkt neben Angaben, die längst übersetzt waren.

    Geprüft wird die **Sprachbindung** und nicht ein Wortlaut: Zwei Sprachen
    müssen zwei verschiedene Schreibweisen ergeben. Ein Vergleich gegen eine
    erwartete Zeichenkette prüfte dagegen nur, was ``QLocale`` in dieser
    Qt-Fassung gerade tut.
    """
    import os
    from datetime import datetime

    from app.i18n import get_language, set_language

    alt = tmp_path / "sicherung.p3d"
    alt.write_bytes(b"x")
    os.utime(alt, (0, datetime(2026, 3, 5, 14, 30).timestamp()))

    vorher = get_language()
    try:
        set_language("de")
        deutsch = MainWindow._when(alt)
        set_language("en")
        englisch = MainWindow._when(alt)
    finally:
        set_language(vorher)

    assert "2026" in deutsch and "2026" in englisch, f"kein Datum: {deutsch!r} / {englisch!r}"
    assert deutsch != englisch, (
        f"beide Sprachen schreiben {deutsch!r} — das Datum hängt nicht an der Sprache"
    )


# --- die Schicht gehört ihrem Körper, auch auf Platte zwei (RM-119) ---------------


def _two_plates(window: MainWindow) -> Any:
    """Zwei Bretter 200 auf 200 — mehr als ein Bett fasst, also zwei Platten."""
    for _ in range(2):
        window.session.apply(
            "Anlegen",
            [
                OperationDraft(
                    op="create_box", params={"width": 200.0, "depth": 200.0, "height": 20.0}
                )
            ],
        )
        window.session.wait_for_idle()
    result = window.session.last_result
    assert result is not None
    window.session.apply(
        "Anordnen",
        [
            OperationDraft(
                op="arrange_bed", inputs=tuple(result.scene.objects), params={"plates": 2}
            )
        ],
    )
    window.session.wait_for_idle()
    result = window.session.last_result
    assert result is not None
    assert {entry.plate for entry in result.scene.objects.values()} == {0, 1}, "zwei Platten"
    window.viewport.show_scene(result)
    window.viewport.wait_for_workers(5000)
    return result


def _layer_lines(window: MainWindow) -> Any:
    """Die x-Spanne der gezeichneten Schichtkonturen."""
    import numpy as np

    points = [
        np.asarray(entry["item"].points, dtype=float)
        for kind, entry in window.viewport.renderer.drawn
        if kind == "lines" and entry["name"] == "layer"
    ]
    assert points, "ohne gezeichnete Kontur sagt der Test nichts"
    stacked = np.vstack(points)
    return float(stacked[:, 0].min()), float(stacked[:, 0].max())


def test_the_layer_outline_follows_its_body_to_the_second_plate(window: MainWindow) -> None:
    """Die Schichtlinien lagen quer über dem falschen Teil (RM-119).

    Gemessen am 12.09.2026: Der Körper auf Platte 2 steht im Bild bei x 160
    bis 360 — eine Bettbreite plus Abstand weiter —, seine Schichtkonturen
    wurden bei x -100 bis 100 gezeichnet, also auf dem Teil daneben. Die
    Konturen entstehen in Szenenkoordinaten, und dort liegen beide Platten
    übereinander; was sie nicht bekamen, war der Ansichtsversatz, den jede
    andere Zeichenstelle über ``_view_offset`` längst nimmt.
    """
    from app.core.slice.analysis import slice_body
    from tests.render_fakes import RecordingRenderer

    result = _two_plates(window)
    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    second = next(key for key, entry in result.scene.objects.items() if entry.plate == 1)
    box = result.scene.objects[second].mesh.bounds

    layers = slice_body(result.scene.objects[second].mesh, 2.0)
    window.viewport.set_layer(layers.layers[3], second)

    low, high = _layer_lines(window)
    shift = float(window.viewport._view_offset(result.scene.objects[second], result)[0])
    assert shift > 100.0, "ohne Versatz prüft der Test nichts"
    assert low == pytest.approx(box.minimum[0] + shift, abs=1.0)
    assert high == pytest.approx(box.maximum[0] + shift, abs=1.0)


def test_looking_at_one_plate_puts_the_outline_back(window: MainWindow) -> None:
    """Und beim Blick auf eine einzelne Platte steht sie wieder am Szenenort.

    Dann zeichnet die Ansicht ein Bett, und darauf gehört das, was darauf
    liegt — ``_plate_offset`` ist null, und die Konturen dürfen nicht auf
    einem festen Versatz kleben bleiben.
    """
    from app.core.slice.analysis import slice_body
    from tests.render_fakes import RecordingRenderer

    result = _two_plates(window)
    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    second = next(key for key, entry in result.scene.objects.items() if entry.plate == 1)
    box = result.scene.objects[second].mesh.bounds

    window.viewport.set_plate(1)
    layers = slice_body(result.scene.objects[second].mesh, 2.0)
    window.viewport.set_layer(layers.layers[3], second)

    low, high = _layer_lines(window)
    assert low == pytest.approx(box.minimum[0], abs=1.0)
    assert high == pytest.approx(box.maximum[0], abs=1.0)


def test_the_section_plane_cuts_every_plate_at_its_own_place(window: MainWindow) -> None:
    """Und die Entscheidung daneben: Der Schnitt ist eine Szenenebene (RM-119).

    Bei zwei Platten liegen die Körper in der Szene übereinander und im Bild
    nebeneinander. Eine Ebene bei x = 0 schneidet deshalb **beide** Teile in
    ihrer Mitte — im Bild sieht man zwei aufgeschnittene Bretter, und genau
    das ist die Frage, für die ein Schnitt da ist (Wandstärke, Innenraum).

    Eine Bildebene wäre die schlechtere Antwort: Sie träfe immer nur eine
    Platte, und der Schieberweg müsste mit jeder weiteren um eine Bettbreite
    wachsen — er kommt aus den Körpergrenzen (`section_ranges`), also aus der
    Szene. Schnitt und Bedienung stimmen so überein.
    """
    import numpy as np

    from app.core.geom.section import SectionPlane

    result = _two_plates(window)
    window.viewport.set_section(SectionPlane.along("x", 0.0))

    cut_widths = []
    for entry in result.scene.objects.values():
        raw = getattr(window.viewport._sectioned(entry.mesh), "raw", None)
        assert raw is not None and len(raw.faces), "jedes Teil bleibt sichtbar"
        points = np.asarray(raw.vertices, dtype=float)
        cut_widths.append(float(points[:, 0].max() - points[:, 0].min()))

    assert len(cut_widths) == 2
    whole = 200.0
    for width in cut_widths:
        assert width == pytest.approx(whole / 2.0, abs=1.0), (
            f"jedes Teil wird an seiner eigenen Mitte geschnitten: {cut_widths}"
        )


# --- es geht kein zweites Fenster auf (RM-101) ------------------------------------


def _top_level_names() -> set[str]:
    """Jedes elternlose Widget dieser Anwendung, mit Typ und Titel."""
    return {
        f"{type(widget).__name__}({widget.windowTitle() or widget.objectName() or '-'})"
        for widget in QApplication.topLevelWidgets()
        if widget.parent() is None
    }


def test_no_second_window_appears_along_the_way(window: MainWindow) -> None:
    """Die Beobachtung, die den Punkt getragen hat — am aktuellen Fenster gemessen.

    Jemand hat ein fremdes Fenster gesehen; der Verdacht (ein elternlos
    gebauter Befundknopf) war am 10.09.2026 am Code widerlegt, die
    Beobachtung blieb offen. Hier steht der Weg, auf dem sie auftreten müsste:
    aufbauen, zeigen, ein Modell öffnen, die fünf Werkzeuge auf- und zumachen,
    den Prüfbericht füllen. Gemessen am 12.09.2026 bleibt es bei **einem**
    Fenster, und das Hauptfenster behält den Fokus.

    Gezählt wird der Zuwachs und nicht der Bestand: Die Suite hält Fenster
    früherer Tests absichtlich am Leben (`_pin_ui_widgets`), und ein
    absoluter Vergleich prüfte deren Aufräumen statt dieses Fensters.
    """
    from PySide6.QtWidgets import QPushButton

    before = _top_level_names()
    window.show()
    QApplication.processEvents()

    assert QApplication.activeWindow() is window, "das Hauptfenster ist das aktive"

    # Zweimal dasselbe Modell: Das zweite landet unter der Platte und gibt
    # einen Befund **mit Handlung** — nur dafür baut ``_show_offers`` Knöpfe,
    # und genau die standen unter Verdacht. Unter der Platte liegt es seit der
    # freien Stelle (0.5.1) nur mit ausgeschalteten Haken am Ladeschritt.
    for _ in range(2):
        window.open_path(MESHES / "block_with_rounded_edge.stl")
        window.session.wait_for_idle()
    keep_the_files_place(window)
    window._on_scene(window.session.evaluate_now())
    QApplication.processEvents()
    assert window.report._offers.findChildren(QPushButton), (
        "ohne einen Befundknopf prüft dieser Test den Verdacht nicht"
    )

    for tool in ("measure", "section", "layers", "explode", "split"):
        window.tools.toggle(tool)
        QApplication.processEvents()
        window.tools.toggle(tool)
        QApplication.processEvents()

    # **Und die Merkmalleiste**, die ihre Felder auf demselben Weg wegräumt:
    # ein Merkmal wählen füllt sie, die Auswahl aufheben leert sie.
    result = window.session.last_result
    assert result is not None
    object_id, entry = next(iter(result.scene.objects.items()))
    if entry.features:
        window.object_tree.select_object(object_id)
        window.object_tree.select_feature(object_id, next(iter(entry.features)))
        QApplication.processEvents()
        window.object_tree.tree.clearSelection()
        QApplication.processEvents()

    grown = {name for name in _top_level_names() - before if not name.startswith("MainWindow(")}
    assert not grown, f"es ist ein fremdes Fenster aufgegangen: {sorted(grown)}"
    assert QApplication.activeWindow() is window, "und der Fokus liegt weiter beim Hauptfenster"


# --- die grobe Vorschaustufe (§2.8) -----------------------------------------------


def test_a_drawn_split_line_starts_in_the_middle_of_the_body(window: MainWindow) -> None:
    """*An gezeichneter Linie trennen* öffnete auf der Ebene z = 0.

    Derselbe Fehler wie bei *Teilen*, nur in der anderen Schreibweise: Die
    Operation beschreibt ihre Ebene über ``normal_x/y/z`` statt über ``axis``,
    und ``_plane_through`` fragte nach ``axis``. Gemessen am 14.09.2026 über
    alle 110 Dialoge stand über ihr „Keine Vorschau: Diese Ebene teilt das
    Objekt nicht" — der Körper steht auf dem Bett, die Vorgabeebene liegt
    unter ihm.
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window.object_tree.select_object("obj_1")

    window.run_operation(REGISTRY.get("split_line"))
    dialog = window._op_dialog
    assert dialog is not None
    try:
        assert dialog.values()["position"] == pytest.approx(10.0), "Mitte von 0 bis 20"
    finally:
        dialog.reject()


def test_a_coarse_preview_says_so_before_it_says_nothing_changed(window: MainWindow) -> None:
    """Das Band nennt die grobe Stufe — und zwar vor der leeren Differenz.

    Auf einem vergröberten Netz ist „am Volumen ändert sich nichts" keine
    Zusage: Was dort fehlt, kann an der Vergröberung liegen.
    """
    leer = dataclasses.make_dataclass("Leer", [("changed", bool)])(False)
    banner = window.viewport.banner

    window._preview_coarse(400_000)
    assert window._preview_coarse_at == 400_000
    window._show_preview(leer)
    assert banner.note.text() == tr("Grobe Vorschau — beim Übernehmen wird genau gerechnet")

    # Und der Merker gilt genau einer Vorschau, nicht der nächsten.
    window._show_preview(leer)
    assert banner.note.text() == tr("Vorschau — am Volumen ändert sich nichts")

    # Ein Grund aus dem Kern räumt ihn ebenfalls weg.
    window._preview_coarse(400_000)
    window._preview_explained("Diese Ebene teilt das Objekt nicht.")
    assert window._preview_coarse_at == 0
    window._clear_preview()


def test_an_incomplete_coarse_preview_is_called_incomplete(window: MainWindow) -> None:
    """„Grob" darf „unvollständig" nicht verdecken.

    Eine Differenz, in der nur eine Richtung gerechnet werden konnte, trägt
    ``difference.incomplete``; dieser Vorbehalt steht über dem der groben
    Stufe, weil er über dasselbe Bild mehr sagt.
    """
    finding = dataclasses.make_dataclass("Befund", [("code", str)])("difference.incomplete")
    entry = dataclasses.make_dataclass("Eintrag", [("findings", list)])([finding])
    halb = dataclasses.make_dataclass("Halb", [("changed", bool), ("entries", dict)])(
        True, {"obj_1": entry}
    )

    window._preview_coarse(400_000)
    window._show_preview(halb)
    assert window.viewport.banner.note.text() == tr(
        "Vorschau unvollständig — beim Übernehmen wird genau gerechnet"
    )
    window._clear_preview()


def test_only_a_big_body_is_reduced_for_the_preview(session: Session) -> None:
    """Die Schranke ist eine Dreieckszahl, und unter ihr geschieht nichts.

    Gemessen (14.09.2026, Kugel, Bohrung Ø 5, Entwurfsqualität): 20 480
    Dreiecke 0,16 s, 81 920 0,63 s, 327 680 2,16 s. Die Sekunde aus §2.8
    fällt bei rund 150 000 — dort steht ``COARSE_PREVIEW_ABOVE``.
    """
    from app.ui.session import COARSE_PREVIEW_ABOVE, COARSE_PREVIEW_TARGET, _coarse_drafts

    session.import_model(MESHES / "cube_clean.stl")
    result = session.evaluate_now()
    assert _coarse_drafts(result.scene) == [], "ein Quader wird nicht vergröbert"

    class Grob:
        triangle_count = COARSE_PREVIEW_ABOVE + 1

    class Fein:
        triangle_count = COARSE_PREVIEW_ABOVE

    holder = dataclasses.make_dataclass("Traeger", [("mesh", object)])
    scene = dataclasses.make_dataclass("Szene", [("objects", dict)])(
        {"obj_1": holder(Grob()), "obj_2": holder(Fein())}
    )
    drafts = _coarse_drafts(scene)
    assert [draft.inputs for draft in drafts] == [("obj_1",)], "genau einer liegt darüber"
    assert drafts[0].op == "decimate_mesh"
    # Der Anzeigeweg (RM-208): Kern nach Sehnenfehler, dann Raster, ohne Messung.
    assert drafts[0].params == {"triangles": COARSE_PREVIEW_TARGET, "method": "fast"}


def test_a_coarse_preview_measures_the_same_change_as_the_exact_one(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die grobe Stufe rechnet beide Seiten auf demselben groben Netz.

    Getrennt verkleinert liefen ``davor`` und ``danach`` überall um
    Bruchteile eines Millimeters auseinander, und die Differenz war dieser
    Unterschied statt der Änderung — gemessen an einer Kugel aus 81 920
    Dreiecken 16,7 mm³ Material, das niemand angefasst hat, und zehn bis
    fünfzig Sekunden Rechnung dafür.

    Die Schranke wird für den Test heruntergesetzt: Ein Netz von 150 000
    Dreiecken in die Suite zu legen hieße, Sekunden je Lauf für eine Zahl
    auszugeben, die auch an einem Ellipsoid aus 1 280 Dreiecken stimmt — und
    krumm muss er sein, denn an einer ebenen Fläche ist das Verkleinern
    verlustfrei und die Frage gar nicht gestellt.
    """
    from app.core.geom.mesh_ops import DECIMATE_FLOOR
    from app.ui import session as session_module

    session.import_model(MESHES / "near_sphere_ellipsoid.stl", unit="mm")
    session.evaluate_now()
    body = next(iter(session.last_result.scene.objects))
    draft = OperationDraft(
        op="drill_hole",
        params={"diameter": 5.0, "x": 0.0, "y": 0.0, "z": 20.0, "depth": 0.0},
        inputs=(body,),
    )

    _scene, exact, _reason = session._preview_outcome([draft])
    assert exact is not None and exact.removed_volume > 0.0

    monkeypatch.setattr(session_module, "COARSE_PREVIEW_ABOVE", DECIMATE_FLOOR)
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_TARGET", DECIMATE_FLOOR)
    seen: list[int] = []
    _scene, coarse, _reason = session._preview_outcome([draft], coarsened=seen.append)
    assert seen and seen[0] > 0, "gemeldet wird die Dreieckszahl davor"
    assert coarse is not None
    assert coarse.removed_volume == pytest.approx(exact.removed_volume, rel=0.05)
    assert coarse.added_volume <= exact.removed_volume * 0.05, (
        "aus zwei getrennt verkleinerten Netzen käme hier Material, das niemand angefasst hat"
    )


def test_a_step_that_names_a_feature_is_previewed_on_the_exact_body(
    session: Session, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Wer ein Merkmal beim Namen nennt, bekommt keine vergröberte Vorschau.

    Die grobe Stufe verkleinert den Eingang und erkennt ihn neu; ein Schritt
    mit ``at_feature`` fand sein Merkmal danach nicht mehr. An der Senkplatte
    mit 311 296 Dreiecken (``plate_countersunk.stl``, fünfmal unterteilt)
    stand beim Maßeditor im Bild statt einer Vorschau „Dieses Merkmal gibt
    es an diesem Objekt nicht.", und Übernehmen blieb gesperrt (22.09.2026).
    Hier dieselbe Platte einmal unterteilt und die Schranke heruntergesetzt —
    am HEAD derselbe Satz.
    """
    import trimesh

    from app.core.geom.mesh_ops import DECIMATE_FLOOR
    from app.ui import session as session_module

    raw = trimesh.load(MESHES / "plate_countersunk.stl", force="mesh")
    vertices, faces = trimesh.remesh.subdivide(raw.vertices, raw.faces)
    finer = tmp_path / "plate_countersunk_x1.stl"
    trimesh.Trimesh(vertices, faces, process=False).export(finer)
    session.import_model(finer)
    result = session.evaluate_now()
    body, entry = next(iter(result.scene.objects.items()))
    hole = next(key for key, feature in entry.features.items() if feature.kind == "hole")
    draft = OperationDraft(
        op="resize_hole", params={"at_feature": hole, "diameter": 6.0}, inputs=(body,)
    )

    monkeypatch.setattr(session_module, "COARSE_PREVIEW_ABOVE", DECIMATE_FLOOR)
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_TARGET", DECIMATE_FLOOR)
    seen: list[int] = []
    _scene, difference, reason = session._preview_outcome([draft], coarsened=seen.append)
    assert reason == "" and difference is not None, reason
    assert seen == [], "genau gerechnet, nicht vergröbert"


def test_a_preview_without_the_coarse_callback_stays_exact(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wer die grobe Stufe nicht anfordert, bekommt die genaue Rechnung.

    Der Agentenvorschlag geht diesen Weg (``preview_scene``): Er antwortet
    ohnehin nicht in Millisekunden, und sein Bild steht, bis jemand es
    annimmt oder verwirft.
    """
    from app.ui import session as session_module

    session.import_model(MESHES / "near_sphere_ellipsoid.stl", unit="mm")
    session.evaluate_now()
    body = next(iter(session.last_result.scene.objects))
    draft = OperationDraft(
        op="drill_hole",
        params={"diameter": 5.0, "x": 0.0, "y": 0.0, "z": 20.0, "depth": 0.0},
        inputs=(body,),
    )
    asked: list[object] = []
    original = session_module._coarse_drafts

    def watched(scene: object) -> list[OperationDraft]:
        asked.append(scene)
        return original(scene)

    monkeypatch.setattr(session_module, "_coarse_drafts", watched)
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_ABOVE", 500)
    session.preview_scene([draft])
    assert asked == [], "ohne Rückruf wird nicht einmal gefragt"


def test_a_check_says_where_its_result_is_instead_of_naming_the_volume(
    window: MainWindow,
) -> None:
    """„Am Volumen ändert sich nichts" ist über einer Prüfung ein Füllsatz.

    *Überschneidungen prüfen* und *Fügeweg prüfen* ändern **nie** etwas; ihr
    Ergebnis sind die Befunde. Wer den allgemeinen Satz liest, sucht danach im
    Bild nach einem Ergebnis, das im Prüfbericht steht. *Objekt umbenennen*
    ändert dagegen sehr wohl etwas — nur nicht die Form.

    Welche Lage gilt, sagt das Register und keine Namensliste im Fenster
    (``OperationSpec.unchanged_effect``); das Fenster übersetzt sie in einen
    Satz.
    """
    leer = dataclasses.make_dataclass("Leer", [("changed", bool)])(False)
    banner = window.viewport.banner

    window._preview_effect = REGISTRY.get("check_collisions").unchanged_effect
    window._show_preview(leer)
    assert banner.note.text() == tr("Prüfung — das Ergebnis steht im Prüfbericht, nicht im Bild")

    # Der Merker gilt genau einer Vorschau — die nächste bekommt den
    # allgemeinen Satz zurück.
    window._show_preview(leer)
    assert banner.note.text() == tr("Vorschau — am Volumen ändert sich nichts")

    window._preview_effect = REGISTRY.get("rename_object").unchanged_effect
    window._show_preview(leer)
    assert banner.note.text() == tr("Vorschau — der Name ändert sich, die Form nicht")

    # Und ein Grund aus dem Kern räumt ihn ebenfalls weg.
    window._preview_effect = REGISTRY.get("check_join_path").unchanged_effect
    window._preview_explained("Diese Ebene teilt das Objekt nicht.")
    assert window._preview_effect == ""
    window._clear_preview()


def test_every_operation_without_a_geometry_outcome_is_declared_in_the_register() -> None:
    """Die Tabelle nennt Operationen, also müssen es welche sein.

    Ein Tippfehler darin wäre still: Das Band fiele auf den allgemeinen Satz
    zurück, und niemand bemerkte es.
    """
    from app.core.registry.registry import UNCHANGED_EFFECT

    unknown = sorted(name for name in UNCHANGED_EFFECT if not REGISTRY.has(name))
    assert unknown == [], f"keine Operationen: {unknown}"
    assert {name for name, lage in UNCHANGED_EFFECT.items() if lage == "report"} == {
        "check_collisions",
        "check_join_path",
    }, "die beiden Prüfwerkzeuge geben ihre Eingänge unverändert zurück"


def test_an_empty_preview_repeats_what_the_step_itself_reported() -> None:
    """Über einer leeren Differenz ist jeder Befund besser als der Füllsatz.

    *Dreiecke verringern* mit einem Ziel über der vorhandenen Zahl tut nichts
    und meldet ``mesh.already_below_target`` — Stufe ``info``, und die kam bis
    zum 14.09.2026 nicht ins Band: Dort stand „am Volumen ändert sich nichts",
    also die Beobachtung statt des Grundes. Dieselben Geschwister:
    ``repair.nothing_to_do``, ``mesh.not_simplified``, ``sculpt.empty``.

    Warnung und Fehler behalten den Vortritt — ein Schritt kann beides melden.
    """
    from app.ui.session import _warning_of

    def result_with(*findings: Finding) -> Any:
        report = dataclasses.make_dataclass("Bericht", [("findings", list)])(list(findings))
        scene = dataclasses.make_dataclass("Szene", [("report", object)])(report)
        return dataclasses.make_dataclass("Ergebnis", [("scene", object)])(scene)

    hinweis = Finding(
        code="mesh.already_below_target",
        severity="info",
        message="Der Körper hat schon weniger Dreiecke als das Ziel.",
        op_id=2,
    )
    warnung = Finding(
        code="mesh.not_simplified",
        severity="warning",
        message="Das Netz ließ sich nicht weiter vereinfachen.",
        op_id=2,
    )
    fremd = Finding(code="ingest.not_watertight", severity="warning", message="Offen.", op_id=1)

    assert _warning_of(result_with(hinweis), (2,)) == str(hinweis.message)
    assert _warning_of(result_with(hinweis, warnung), (2,)) == str(warnung.message)
    assert _warning_of(result_with(fremd, hinweis), (2,)) == str(hinweis.message), (
        "ein Befund eines fremden Schritts gehört nicht in dieses Band"
    )
    assert _warning_of(result_with(fremd), (2,)) == ""


def test_the_band_of_an_empty_preview_carries_that_sentence(window: MainWindow) -> None:
    """Und der Satz kommt im Fenster an, nicht nur in der Sitzung.

    *Reparieren* an einem heilen Quader ändert nichts und sagt, warum.
    """
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle()
    result = window.session.last_result
    assert result is not None
    body = next(iter(result.scene.objects))

    _scene, difference, reason = window.session._preview_outcome(
        [OperationDraft(op="repair", params={}, inputs=(body,))]
    )
    assert difference is not None and not difference.changed, "ein heiles Netz ändert sich nicht"
    assert reason, "der Schritt meldet, warum nichts geschah"

    window._preview_explained(reason)
    assert window.viewport.banner.note.text() == tr("Keine Vorschau: {reason}").format(
        reason=reason
    )
    assert window.viewport.banner.note.text() != tr("Vorschau — am Volumen ändert sich nichts")
    window._clear_preview()


def test_a_changed_preview_keeps_its_warning_and_its_result(
    window: MainWindow, tmp_path: Path
) -> None:
    """Eine geöffnete Nachbarbohrung wird vor dem Übernehmen sichtbar benannt."""
    mesh, _features, _hole = two_bores(7.5)
    source = tmp_path / "neighbour.stl"
    mesh.raw.export(source)
    window.open_path(source)
    assert window.session.wait_for_idle()
    before = window.session.last_result
    assert before is not None
    body = next(iter(before.scene.objects.values()))
    hole = min(
        (feature for feature in body.features.values() if feature.kind == "hole"),
        key=lambda feature: feature.params["centre"][0],
    )
    _scene, difference, reason = window.session._preview_outcome(
        [
            OperationDraft(
                op="resize_hole",
                params={"at_feature": hole.id, "diameter": 10.0, "compensate": False},
                inputs=(body.id,),
            )
        ]
    )
    assert difference is not None and difference.changed
    assert reason == "", "ein geändertes Ergebnis darf nicht als ausgebliebenes Bild gelten"
    warnings = [finding for finding in difference.findings if finding.severity == "warning"]
    conflict = next(finding for finding in warnings if finding.code == "bore.neighbour_opened")
    assert all(finding.op_id != 1 for finding in difference.findings)
    window._show_preview(difference)
    assert str(conflict.message) in window.viewport.banner.note.text()
    assert window.viewport.banner.hint.text() == tr("Leertaste halten: vorher")
    assert window.viewport._difference is difference
    assert window.session.last_result is before
    window._clear_preview()


def test_the_preview_reads_the_advice_the_core_already_carries() -> None:
    """Die Kennung kommt aus den Vorschlägen der Ausnahme, nicht aus dem Satz.

    Zwei Wege führen zum Band, und beide müssen sie tragen: die Ausnahme, die
    aus der Rechnung fliegt (:func:`_advice_of`), und der Befund, an dem die
    Kette anhält (:func:`_stop_advice`). *Abbrechen* ist kein Rat und trägt
    ``primary`` nicht — eine Ausnahme ohne empfohlene Handlung nennt keine.
    """
    from app.core.errors import CANCEL, GeometryError, NotManifoldError
    from app.i18n import TranslatableText
    from app.ui.session import _advice_of

    nicht_dicht = NotManifoldError(
        detail=TranslatableText("Erst reparieren."),
        open_edges=3,
    )
    assert _advice_of(nicht_dicht) == "repair_and_retry"
    ging_nicht = GeometryError(TranslatableText("Ging nicht."), suggestions=(CANCEL,))
    assert _advice_of(ging_nicht) == "", "Abbrechen ist kein Rat"


class _DialogWithHook:
    """Ein Dialogdoppel, das ``block_apply`` trägt — wie der echte."""

    def __init__(self) -> None:
        self.blocked: list[str | None] = []

    def block_apply(self, reason: str | None) -> None:
        self.blocked.append(reason)


class _DialogWithoutHook:
    """Und eines ohne ihn: Die Sperre darf daran nicht scheitern."""


def test_a_reason_that_asks_for_a_repair_first_greys_out_apply(window: MainWindow) -> None:
    """Das Band sagte „Erst reparieren, dann aushöhlen" — und *Übernehmen*
    blieb anklickbar.

    Drei Klicks später stand derselbe Satz im Prüfbericht, dazu ein
    angehaltener Schritt im Verlauf (Regel 19). Trägt der Grund eine Handlung,
    die vor das Übernehmen gehört, sperrt das Fenster den Knopf mit genau
    diesem Satz.
    """
    doppel = _DialogWithHook()
    window._op_dialog = cast(Any, doppel)
    satz = "Der Körper ist nicht geschlossen — erst reparieren, dann aushöhlen."

    window._preview_advised("repair_and_retry")
    window._preview_explained(satz)
    assert doppel.blocked == [satz]
    assert window._preview_action == "", "die Handlung gilt genau einem Grund"

    # Und das nächste Bild gibt ihn wieder frei.
    gezeigt = dataclasses.make_dataclass("Gezeigt", [("changed", bool), ("entries", dict)])(
        True, {}
    )
    window._show_preview(gezeigt)
    assert doppel.blocked[-1] is None

    # Eine Handlung, die im offenen Dialog stattfindet, sperrt nichts: Beim
    # Tippen entstehen ungültige Zwischenstände.
    window._preview_advised("correct_input")
    window._preview_explained("Ein Wert liegt außerhalb des zulässigen Bereichs.")
    assert doppel.blocked[-1] is None

    # Ein Dialog ohne den Haken und gar kein Dialog laufen unverändert weiter.
    window._op_dialog = cast(Any, _DialogWithoutHook())
    window._preview_advised("repair_and_retry")
    window._preview_explained(satz)
    window._op_dialog = None
    window._preview_advised("repair_and_retry")
    window._preview_explained(satz)


def test_naming_the_dimensions_makes_them_project_parameters(window: MainWindow) -> None:
    """Weg 2: *Maße als Parameter anlegen* legt Breite, Tiefe und Höhe als Projektparameter
    an, der Schritt verweist darauf, und der Quader folgt der Leiste (§13).

    Bis zum 14.09.2026 gab es diesen Weg nur für den Agenten; der Kunde
    musste den Parameter in der Leiste anlegen und dann ``=@breite`` in das
    Feld tippen. Geprüft wird die ganze Kette: die Parameter mit Einheit und
    übersetzbarem Titel, der Verweis im Schritt, die Ausdehnung des Körpers
    nach einer gedrehten Zahl, ein zweiter Quader mit eigenen Namen — und
    dass ein Strg+Z Schritt und Maße zusammen zurücknimmt, als eine
    Transaktion.
    """
    from app.ui.op_dialog import ValueField

    spec = REGISTRY.get("create_box")

    def make_box(width: float, depth: float, height: float) -> None:
        window.run_operation(spec)
        dialog = window._op_dialog
        assert dialog is not None
        assert dialog._naming is not None, "ein Grundkörper bietet den Haken an"
        assert dialog.names_dimensions(), "beim ersten Start steht er an (RM-369)"
        for name, value in (("width", width), ("depth", depth), ("height", height)):
            editor = dialog._editors[name]
            assert isinstance(editor, ValueField)
            editor.set_value(value)
        dialog._naming.setChecked(True)
        _accept_after_preview(window, dialog)
        QApplication.processEvents()
        window.session.wait_for_idle()

    make_box(60.0, 40.0, 20.0)
    document = window.session.project.document
    assert {name: entry.value for name, entry in document.parameters.items()} == {
        "breite": 60.0,
        "tiefe": 40.0,
        "hoehe": 20.0,
    }
    assert document.parameters["breite"].unit == "mm"
    assert str(document.parameters["hoehe"].title) == str(tr("Höhe")), (
        "der Titel bleibt übersetzbar"
    )
    first = document.ops[-1]
    assert first.op == "create_box"
    assert {key: first.params[key] for key in ("width", "depth", "height")} == {
        "width": "=@breite",
        "depth": "=@tiefe",
        "height": "=@hoehe",
    }
    body = window.session.last_result.scene.objects[first.outputs[0]]
    assert body.mesh.bounds.size == pytest.approx((60.0, 40.0, 20.0))

    # Die Leiste dreht das Maß, nicht der Schritt.
    assert window.session.change_parameter("breite", 90.0)
    window.session.wait_for_idle()
    body = window.session.last_result.scene.objects[first.outputs[0]]
    assert body.mesh.bounds.size == pytest.approx((90.0, 40.0, 20.0))

    # Ein zweiter Quader bekommt eigene Namen, statt die ersten zu überschreiben.
    make_box(10.0, 10.0, 10.0)
    document = window.session.project.document
    assert set(document.parameters) == {
        "breite",
        "tiefe",
        "hoehe",
        "breite_2",
        "tiefe_2",
        "hoehe_2",
    }
    assert document.ops[-1].params["width"] == "=@breite_2"
    assert document.parameters["breite"].value == pytest.approx(90.0), "das erste Maß bleibt"

    # Strg+Z nimmt Schritt und Maße zusammen zurück — eine Transaktion, wie
    # beim Agentenvorschlag (Regel 16).
    assert window.session.undo() is not None
    window.session.wait_for_idle()
    document = window.session.project.document
    assert set(document.parameters) == {"breite", "tiefe", "hoehe"}
    assert len(document.ops) == 1
    assert window.session.undo() is not None
    assert document.parameters["breite"].value == pytest.approx(60.0), "die gedrehte Zahl"
    assert window.session.undo() is not None
    window.session.wait_for_idle()
    document = window.session.project.document
    assert document.ops == []
    assert document.parameters == {}, "der Quader nimmt seine Maße mit"


@pytest.mark.parametrize("name", ["create_box", "create_cylinder", "create_holder_u"])
def test_the_naming_box_remembers_the_last_choice(window: MainWindow, name: str) -> None:
    """*Maße als Parameter anlegen* übernimmt die letzte Wahl (RM-369, §13, §2.4).

    Beim ersten Start steht der Haken an; wer ihn abwählt und übernimmt, findet
    ihn beim nächsten Dialog aus, auch nach einem Neustart. Ein Abbrechen
    entscheidet nichts. Geprüft an zwei Grundkörpern und einem Vorlagenbaustein,
    weil die Zusage für jeden Dialog mit dem Haken gilt (Vorgabe Robert).
    """
    from app.ui.settings import load_settings

    spec = REGISTRY.get(name)

    def open_dialog() -> OperationDialog:
        window.run_operation(spec)
        dialog = window._op_dialog
        assert dialog is not None
        assert dialog.offers_naming(), f"{name} bietet den Haken an"
        return dialog

    first = open_dialog()
    assert first.names_dimensions(), "beim ersten Start an"
    first._naming.setChecked(False)
    _accept_after_preview(window, first)
    QApplication.processEvents()
    window.session.wait_for_idle()
    assert window.session.project.document.parameters == {}, "abgewählt legt nichts an"
    assert load_settings().name_dimensions is False, "die Wahl überlebt einen Neustart"

    second = open_dialog()
    assert not second.names_dimensions(), "der nächste Dialog übernimmt die letzte Wahl"
    second._naming.setChecked(True)
    second.reject()
    QApplication.processEvents()
    assert window.settings.name_dimensions is False, "Abbrechen entscheidet nichts"

    third = open_dialog()
    assert not third.names_dimensions()
    third._naming.setChecked(True)
    _accept_after_preview(window, third)
    QApplication.processEvents()
    window.session.wait_for_idle()
    assert window.session.project.document.parameters, "angehakt legt die Maße an"
    assert load_settings().name_dimensions is True


def test_finish_lists_the_sketch_operations_in_the_window(window: MainWindow) -> None:
    """Die zehn Skizzenoperationen hängen unter *Mehr* — der Dialog
    „Was soll daraus werden?" ist am 16.09.2026 gefallen (Robert: „weniger
    ist manchmal mehr"), und an *Fertig* hängen sie seit dem 23.09.2026 nicht
    mehr (Bedienabnahme Zeichnen, E2). Hochziehen steht vorn."""
    window.action_sketch_free()
    try:
        names = list(window._finish_actions)
        assert names[0] == "sketch_extrude", "der Normalfall steht an erster Stelle"
        assert set(names) == {
            "sketch_extrude",
            "sketch_join",
            "sketch_pocket",
            "sketch_revolve",
            "sketch_loft",
            "sketch_sweep",
            "sketch_revolve_cut",
            "sketch_loft_cut",
            "sketch_sweep_cut",
            "field_cut",
        }
        assert window.sketch_more_button.menu() is window._finish_menu
        assert window.sketch_finish_button.menu() is None
        for action in window._finish_actions.values():
            assert action.toolTip(), "jeder Eintrag sagt, was er tut oder warum nicht"
    finally:
        window.finish_sketch(keep=False)


def test_delete_on_a_face_takes_the_body_and_says_so(window: MainWindow) -> None:
    """Eine Fläche ist nichts, was man löscht — Entf an ihr nimmt den Körper und sagt es.

    Zweimal am 16.09.2026 in Gegenrichtung. Morgens (Bausteindach): „wenn ich
    etwas im objektbaum oder viewport auswähle und entf drücke … wird der
    ganze körper gelöscht" — dafür fällt am Baustein sein Schritt
    (``test_delete_at_a_part_takes_its_step_and_never_the_body``). Danach
    löschte Entf an einer Fläche gar nichts mehr und verwies auf Escape, und
    abends am eingelesenen Tray: „warum kann ich kein körper mehr löschen".
    Im Bild trifft ein Klick immer eine Fläche; ein Teil, das sich mit Entf
    nicht löschen lässt, ist eine Sackgasse. Rücknehmbar, mit Ansage (Regel 19).
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    face = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "face"
    )
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, face)

    window.run_operation(REGISTRY.get("delete_object"))
    window.session.wait_for_idle()

    assert [step.op for step in window.session.project.document.ops] == ["load", "delete_object"]
    assert object_id not in window.session.evaluate_now().scene.objects, "der Körper fällt"
    said = window.status_message.text()
    assert "Strg+Z" in said, said

    window.session.undo()
    window.session.wait_for_idle()
    assert object_id in window.session.evaluate_now().scene.objects, "und Strg+Z holt ihn zurück"
    # Das Undo stellt die Flächenauswahl wieder her, und ein Fenster, das mit
    # gewählter Fläche in den Abbau der Suite geht, reißt dort (Exit 127, am
    # unveränderten HEAD nachgemessen, RM-021); der echte Schließweg der
    # Anwendung ist mit derselben Auswahl sauber. Der Test prüft Entf, nicht
    # den Abbau — die Auswahl geht deshalb vorher weg.
    window.object_tree.select_object(None)
    QApplication.processEvents()


def test_hiding_from_a_feature_row_names_the_body(window: MainWindow) -> None:
    """„Ausblenden" an einer Bohrung las sich als Zusage über die Bohrung — und
    der Körper verschwand (Robert, 16.09.2026). Der Eintrag sagt jetzt, was er
    trifft; am Körper selbst heißt er weiter wie bisher."""
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)
    menu = window.object_tree.context_menu()
    assert menu is not None
    texts = [action.text() for action in menu.actions()]
    menu.deleteLater()
    assert tr("Körper ausblenden") in texts and tr("Ausblenden") not in texts, texts

    window.object_tree.select_object(object_id)
    menu = window.object_tree.context_menu()
    assert menu is not None
    texts = [action.text() for action in menu.actions()]
    menu.deleteLater()
    assert tr("Ausblenden") in texts, texts
    # Dieselbe Aufräumfamilie wie einen Test darüber (RM-021): Ein Fenster,
    # das mit dieser Auswahl in den Abbau der Suite geht, reißt dort mit
    # Exit 127 nach grünen Zusicherungen — dreimal von drei, am unveränderten
    # HEAD genauso (19.09.2026, Teil 10 von test_ui.py). Der Test prüft den
    # Menütext, nicht den Abbau; die Auswahl geht deshalb vorher weg.
    window.object_tree.select_object(None)
    QApplication.processEvents()


@pytest.mark.parametrize("operation", ["brep_to_mesh", "union_objects"])
def test_exact_conversion_is_shown_before_apply_even_without_volume_change(window, operation):
    """Das Band nennt die wirkliche Bauartänderung, während das Dokument unverändert bleibt."""
    _needs_the_exact_kernel()
    window.session.apply(
        "Zwei Körper",
        [
            OperationDraft(op="create_box", params={"name": "Netz", "width": 40.0}),
            OperationDraft(op="create_brep_box", params={"name": "Werkzeug", "x": 10.0}),
        ],
    )
    assert window.session.wait_for_idle()
    before = window.session.last_result
    inputs = ("obj_2",) if operation == "brep_to_mesh" else ("obj_1", "obj_2")
    _scene, difference, reason = window.session._preview_outcome(
        [OperationDraft(op=operation, inputs=inputs)]
    )
    assert difference is not None
    assert not reason
    window._show_preview(difference)
    text = window.viewport.banner.note.text()
    assert str(REGISTRY.get(operation).title) in text
    assert "Werkzeug" in text
    assert "macht aus" in text and "Dreiecksmodell" in text
    assert "bleiben bearbeitbar" in text
    assert "Rückgängig" in text
    assert text.count("Dreiecksmodell") == 1
    assert window.session.last_result is before
    assert window.session.last_result.scene.objects["obj_2"].kind == "brep"
    assert len(window.session.project.document.ops) == 2
    window._clear_preview()


def test_an_exact_body_keeps_its_kind_when_the_preview_triangle_limit_is_low(session, monkeypatch):
    """Viele Anzeigedreiecke machen den exakten Eingabekörper nicht zum groben Netz."""
    _needs_the_exact_kernel()
    from app.ui import session as session_module

    session.apply("Rundkörper", [OperationDraft(op="create_brep_cylinder")])
    assert session.wait_for_idle()
    before = session.last_result
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_ABOVE", 1)
    assert session_module._coarse_drafts(before.scene) == []
    coarse = []
    scene, difference, reason = session._preview_outcome(
        [OperationDraft(op="scale_object", inputs=("obj_1",), params={"factor": 2.0})],
        coarsened=coarse.append,
    )
    assert scene.objects["obj_1"].kind == "brep"
    assert difference is not None
    assert not reason
    assert coarse == []
    assert session.last_result is before
    assert not any(f.converts_exact_body for f in difference.findings)


def test_editing_a_step_includes_conversion_information_from_its_suffix(session):
    """Die spätere Umwandlung gehört zum Ergebnis der geänderten früheren Operation."""
    _needs_the_exact_kernel()
    session.apply(
        "Körper und Folgeänderung",
        [
            OperationDraft(op="create_brep_box"),
            OperationDraft(op="translate_object", inputs=("obj_1",), params={"dx": 5.0}),
            OperationDraft(op="brep_to_mesh", inputs=("obj_1",)),
        ],
    )
    assert session.wait_for_idle()
    before = session.last_result
    scene, difference, reason = session._preview_outcome(
        [], change_op=2, change_values={"dx": 10.0}
    )
    assert difference is not None
    assert not reason
    assert scene.objects["obj_1"].kind == "mesh"
    converted = [f for f in difference.findings if f.code == "evaluate.exact_became_mesh"]
    assert len(converted) == 1
    assert converted[0].op_id == 3
    assert converted[0].values["input_object"] == "obj_1"
    assert session.last_result is before


@pytest.mark.parametrize(
    "original,target,kind",
    [("create_brep_box", "create_box", "mesh"), ("create_box", "create_brep_box", "brep")],
)
def test_a_history_preview_uses_the_chosen_twin_without_changing_the_document(
    session, original, target, kind
):
    """Synchroner und asynchroner Vorschauweg rechnen den gewählten Zwilling samt Folgeschritt."""
    import copy

    values = {"width": 40.0, "depth": 30.0, "height": 20.0, "name": "Grundkörper"}
    session.apply(
        "Körper mit Folgebewegung",
        [
            OperationDraft(op=original, params=values),
            OperationDraft(op="translate_object", inputs=("obj_1",), params={"dx": 10.0}),
        ],
    )
    assert session.wait_for_idle()
    document_before = copy.deepcopy(session.project.document)
    result_before = session.last_result
    selected_values = {**values, "width": 50.0}
    scene, difference, reason = session._preview_outcome(
        [], change_op=1, change_name=target, change_values=selected_values
    )
    assert not reason
    assert difference is not None
    assert scene.objects["obj_1"].kind == kind
    assert scene.objects["obj_1"].mesh.volume == pytest.approx(30000.0)
    assert scene.objects["obj_1"].mesh.bounds.size == pytest.approx((50.0, 30.0, 20.0))
    assert scene.objects["obj_1"].mesh.bounds.centre[0] == pytest.approx(10.0)
    converted = [f for f in difference.findings if f.converts_exact_body]
    assert len(converted) == (1 if kind == "mesh" else 0)
    if converted:
        assert converted[0].values["op"] == target
        assert converted[0].values["input_name"] == "Grundkörper"
        assert converted[0].op_id == 1

    shown, reasons, failures = [], [], []
    session.preview_async(
        shown.append,
        change_op=1,
        change_name=target,
        change_values=selected_values,
        explained=reasons.append,
        failed=failures.append,
    )
    assert session.wait_for_idle()
    assert not failures and not reasons
    assert len(shown) == 1 and shown[0] is not None
    assert shown[0].added_volume == pytest.approx(6000.0, abs=1e-4)
    assert sum(f.converts_exact_body for f in shown[0].findings) == len(converted)
    assert session.project.document == document_before
    assert session.last_result is result_before
    assert session.project.document.ops[0].op == original


def test_an_agent_preview_uses_new_parameters_and_the_proposed_print_target(session):
    """Neue Maße und Druckwerte gelten schon in derselben Vorschau wie die Operation."""
    _needs_the_exact_kernel()
    import copy

    from app.core.backends.llm import Reply, ToolCall
    from tests.scripted_backend import ScriptedBackend

    session.apply(
        "Grundkörper",
        [
            OperationDraft(
                op="create_brep_box", params={"width": 20.0, "depth": 10.0, "height": 8.0}
            )
        ],
    )
    assert session.wait_for_idle()
    before = copy.deepcopy(session.project.document)
    result_before = session.last_result
    material = "petg" if before.material != "petg" else "pla"
    backend = ScriptedBackend(
        answers=[
            Reply(
                tool_calls=(
                    ToolCall(
                        id="1",
                        name="add_parameter",
                        arguments={
                            "name": "factor",
                            "value": 2.0,
                            "unit": "",
                        },
                    ),
                )
            ),
            Reply(
                tool_calls=(
                    ToolCall(
                        id="2",
                        name="set_print_target",
                        arguments={
                            "printer": "centauri-carbon-2",
                            "material": material,
                        },
                    ),
                )
            ),
            Reply(
                tool_calls=(
                    ToolCall(
                        id="3",
                        name="scale_object",
                        arguments={
                            "objects": ["obj_1"],
                            "factor": "=@factor",
                        },
                    ),
                )
            ),
            Reply(text="Der Körper ist doppelt so groß."),
        ]
    )

    preview = session.run_proposal("Verdopple den Körper mit einem Hauptmaß.", backend)

    assert preview.proposal.invalid_calls == 0
    assert preview.difference is not None
    assert preview.scene.objects["obj_1"].kind == "brep"
    assert preview.scene.objects["obj_1"].mesh.bounds.size == pytest.approx((40.0, 20.0, 16.0))
    assert preview.scene.parameters["factor"].value == pytest.approx(2.0)
    assert preview.scene.profile.material.id == material
    assert session.project.document == before
    assert session.last_result is result_before

    transaction = session.accept_proposal(preview)
    assert transaction is not None
    assert session.wait_for_idle()
    assert len(session.project.document.transactions) == len(before.transactions) + 1
    assert session.project.document.material == material
    assert session.last_result.scene.objects["obj_1"].mesh.bounds.size == pytest.approx(
        preview.scene.objects["obj_1"].mesh.bounds.size
    )
    assert session.undo() is not None
    assert session.wait_for_idle()
    assert session.project.document.parameters == before.parameters
    assert session.project.document.material == before.material
    assert session.project.document.ops == before.ops


def test_an_agent_parameter_change_has_a_preview_without_new_operations(session):
    """Ein geändertes Hauptmaß bewegt vorhandene Geometrie auch ohne neuen Operationsschritt."""
    _needs_the_exact_kernel()
    from app.core.backends.llm import Reply, ToolCall
    from tests.scripted_backend import ScriptedBackend

    assert session.add_parameter(Parameter(name="width", value=20.0))
    session.apply(
        "Grundkörper", [OperationDraft(op="create_brep_box", params={"width": "=@width"})]
    )
    assert session.wait_for_idle()
    result_before = session.last_result
    backend = ScriptedBackend(
        answers=[
            Reply(
                tool_calls=(
                    ToolCall(
                        id="1",
                        name="set_parameter",
                        arguments={
                            "name": "width",
                            "value": 30.0,
                        },
                    ),
                )
            ),
            Reply(text="Die Breite beträgt 30 mm."),
        ]
    )

    preview = session.run_proposal("Ändere das Hauptmaß auf 30 mm.", backend)

    assert preview.proposal.invalid_calls == 0
    assert not preview.proposal.drafts
    assert preview.difference is not None
    assert preview.scene.objects["obj_1"].mesh.bounds.size[0] == pytest.approx(30.0)
    assert session.project.document.parameters["width"].value == pytest.approx(20.0)
    assert session.last_result is result_before


def test_an_edge_question_shows_the_edge_line_in_the_dialog_and_emphasises_by_token(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine Kollisionsfrage (P1.4c) bietet Token an; der Kunde liest die Kantenzeile.

    Das Token ist eine Kennung für diese eine Frage und keine Beschriftung.
    Der Dialog zeigt je Token dieselbe Zeile wie die Kantenliste (``edge_label``),
    der Kern bekommt das Token zurück, und die markierte Zeile betont die Kante
    in der Ansicht — gefunden über das Token, nicht über eine Kennung.
    """
    from app.core.scene import EdgeTarget, EvaluationResult
    from app.core.types import Scene
    from app.ui import main_window as module
    from app.ui.labels import edge_label

    left = EdgeTarget(
        token="e:0.00,15.00,10.00:0.000,0.000,1.000#1",
        object_id="obj_1",
        points=((0.0, 15.0, 0.0), (0.0, 15.0, 20.0)),
        middle=(0.0, 15.0, 10.0),
        length=20.0,
        upright=True,
        flat=False,
    )
    right = EdgeTarget(
        token="e:0.00,15.00,10.00:0.000,0.000,1.000#2",
        object_id="obj_1",
        points=((0.004, 15.0, 0.0), (0.004, 15.0, 20.0)),
        middle=(0.004, 15.0, 10.0),
        length=20.0,
        upright=True,
        flat=False,
    )
    preview = EvaluationResult(scene=Scene(objects={}), stopped_at=2)
    shown: list[tuple[str, Any]] = []
    built: list[dict[str, str]] = []
    monkeypatch.setattr(window, "_on_scene", lambda result: shown.append(("scene", result)))
    monkeypatch.setattr(
        window.viewport, "show_candidates", lambda *args: shown.append(("candidates", args))
    )

    class Answer(module.AskDialog):
        # ``as_buttons`` seit ``c2ebc0fe0``: Kanten brauchen die Liste, weil die
        # markierte Zeile im Bild leuchtet — Knöpfe gibt es hier nie. ``**rest``
        # nimmt jedes weitere Schlüsselwort mit; ohne es endete ``_on_ask`` am
        # Ersatzdialog mit einem ``TypeError`` statt mit der Frage.
        def __init__(
            self, question, choices, parent=None, *, labels=None, as_buttons=False, **rest
        ):
            assert not as_buttons, "Kandidaten stehen in der Liste"
            built.append(dict(labels or {}))
            super().__init__(
                question, choices, parent, labels=labels, as_buttons=as_buttons, **rest
            )

        def exec(self):
            shown.append(("dialog", None))
            self.list.setCurrentRow(1)
            return self.DialogCode.Accepted

    monkeypatch.setattr(module, "AskDialog", Answer)
    request = AskRequest(
        "Welche Kante?", [left.token, right.token], preview=preview, candidates=(left, right)
    )
    window._on_ask(request)

    assert built == [{left.token: edge_label(left), right.token: edge_label(right)}]
    assert request.answer == right.token and request.answered.is_set()
    emphasised = [args for kind, args in shown if kind == "candidates" and len(args) == 2]
    assert emphasised and emphasised[-1] == ((left, right), right), (
        "die markierte Zeile betont die Kante über ihr Token"
    )
    assert shown[-1] == ("candidates", ()), "nach der Antwort ist die Frage aus dem Bild"


def test_a_feature_question_names_its_candidates_like_the_tree(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Zuordnungs- und die Verweisfrage zeigen „Bohrung 2 · Ø4,40“ statt ``hole_2``.

    Nach *Dreiecke verringern* am Halter mit Wabenmuster fragte die Zuordnung
    „Welches Merkmal entspricht cone_3?“ und bot Kennungen an, die sonst
    nirgends in der Oberfläche stehen. Die Antwort bleibt die Kennung; die
    Zeile ist die Beschriftung des Objektbaums.
    """
    from app.core.scene import EvaluationResult
    from app.core.types import Feature, Scene, SceneObject
    from app.ui import main_window as module
    from app.ui.labels import feature_label

    hole = Feature(
        "hole_2",
        "hole",
        "detected",
        {"diameter": 4.4, "centre": (0.0, 0.0, 0.0), "axis": (0.0, 0.0, 1.0)},
        measure_sources={"diameter": "fit"},
    )
    import trimesh

    from app.core.geom.mesh import MeshData

    plate = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 5.0)))
    body = SceneObject(id="obj_1", name="Halter", mesh=plate, features={"hole_2": hole})
    preview = EvaluationResult(scene=Scene(objects={"obj_1": body}), stopped_at=2)
    built: list[dict[str, str]] = []
    monkeypatch.setattr(window, "_on_scene", lambda result: None)
    monkeypatch.setattr(window.viewport, "show_candidates", lambda *args: None)

    class Answer(module.AskDialog):
        # ``as_buttons`` seit ``c2ebc0fe0``: Merkmale brauchen die Liste, weil die
        # markierte Zeile im Bild leuchtet — Knöpfe gibt es hier nie. ``**rest``
        # nimmt jedes weitere Schlüsselwort mit; ohne es endete ``_on_ask`` am
        # Ersatzdialog mit einem ``TypeError`` statt mit der Frage.
        def __init__(
            self, question, choices, parent=None, *, labels=None, as_buttons=False, **rest
        ):
            assert not as_buttons, "Kandidaten stehen in der Liste"
            built.append(dict(labels or {}))
            super().__init__(
                question, choices, parent, labels=labels, as_buttons=as_buttons, **rest
            )

        def exec(self):
            self.list.setCurrentRow(0)
            return self.DialogCode.Accepted

    monkeypatch.setattr(module, "AskDialog", Answer)
    request = AskRequest(
        "Welches Merkmal entspricht hole_1?",
        ["hole_2", "Nicht weiterführen"],
        preview=preview,
        candidates=(("obj_1", "hole_2"),),
    )
    window._on_ask(request)

    assert built and built[0]["hole_2"] == feature_label("hole_2", hole)
    assert "Nicht weiterführen" not in built[0], "eine Antwort ohne Merkmal bleibt, wie sie ist"
    assert request.answer == "hole_2", "der Kern bekommt die Kennung, nicht die Beschriftung"


def test_the_ask_dialog_shows_a_label_per_token_and_returns_the_token(
    qt_app: Any,
) -> None:
    from app.core.units import UNIT_NAMES
    from app.ui.dialogs import AskDialog

    dialog = AskDialog(
        "Welche?", ["a#1", "a#2", "mm"], labels={"a#1": "Senkrecht · 20 mm", "a#2": "Waagerecht"}
    )
    try:
        assert [dialog.list.item(row).text() for row in range(3)] == [
            "Senkrecht · 20 mm",
            "Waagerecht",
            str(UNIT_NAMES["mm"]),
        ]
        dialog.list.setCurrentRow(1)
        assert dialog.chosen() == "a#2"
    finally:
        dialog.deleteLater()


def test_a_countersunk_bore_builds_the_selection_window_once(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Klick auf eine gesenkte Bohrung baut das Merkmalfenster **einmal**.

    Der Baum meldet dieselbe Wahl zweimal — erst als Merkmal, dann als
    Bohrung mit Senkung —, und bis zum 22.09.2026 bauten beide Meldungen
    Panel, Handlungen und Maßgruppe vollständig auf. Gemessen am Besenhalter
    aus dem Kundenbestand (60 000 Dreiecke): 0,55 s Stillstand je Klick, die
    Hälfte davon doppelt.
    """
    window.open_path(MESHES / "plate_countersunk.stl")
    assert window.session.wait_for_idle()
    entry = window.session.last_result.scene.objects["obj_1"]
    hole = next(identifier for identifier, f in entry.features.items() if f.kind == "hole")
    window.object_tree.select_object("obj_1")
    QApplication.processEvents()

    built: list[str] = []
    original = window.feature_panel.show_feature

    def counted(feature_id: str, *args: Any, **kwargs: Any) -> None:
        built.append(feature_id)
        original(feature_id, *args, **kwargs)

    monkeypatch.setattr(window.feature_panel, "show_feature", counted)
    window.object_tree.select_feature("obj_1", hole)
    QApplication.processEvents()

    assert len(window.object_tree.selected_features()) == 2, (
        "die Bohrung kommt mit ihrer Senkung — sonst gibt es die zweite Meldung nicht"
    )
    assert built == [hole], "dieselbe Wahl, ein Aufbau"
    assert window.feature_panel.feature_id == hole


def test_a_countersunk_bore_stays_one_chosen_feature_after_a_new_evaluation(
    window: MainWindow,
) -> None:
    """Nach einer Auswertung bleibt eine gewählte Bohrung mit Senkung eine Zeile.

    ``selected_features`` meldet sie als zwei Merkmale, und die Wiederherstellung
    im Baum markierte daraus zwei Zeilen — ``selected_feature`` hieß danach
    „keines“, und die Maßgruppe nach *Übernehmen* hing an keinem Merkmal
    (Durchsicht 0.5.1, Wabenhalter).
    """
    window.open_path(MESHES / "plate_countersunk.stl")
    assert window.session.wait_for_idle()
    entry = window.session.last_result.scene.objects["obj_1"]
    hole = next(identifier for identifier, f in entry.features.items() if f.kind == "hole")
    window.object_tree.select_object("obj_1")
    window.object_tree.select_feature("obj_1", hole)
    QApplication.processEvents()
    assert len(window.object_tree.selected_features()) == 2, "sonst gibt es den Fall nicht"

    window.object_tree.show_scene(window.session.last_result, window.session.project.document)
    QApplication.processEvents()

    assert window.object_tree.selected_feature() == hole
    assert len(window.object_tree.tree.selectedItems()) == 1, "eine Zeile, nicht zwei"
    assert len(window.object_tree.selected_features()) == 2, "und sie bündelt weiter beide"


def test_a_click_in_the_tree_settles_the_menu_entries_once_per_signal_pair(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Merkmalsklick stellt die Einträge genau einmal vollständig ein.

    Der Baum unterdrückt beim Leeren die Zwischenmeldung und meldet nur die
    fertige Auswahl. Deren Signalpaar selectionChanged/featureSelected darf
    die Hauptaktionen ebenfalls nur einmal aktualisieren.
    """
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle()
    entry = window.session.last_result.scene.objects["obj_1"]
    face = next(identifier for identifier, f in entry.features.items() if f.kind == "face")
    window.object_tree.select_object("obj_1")
    QApplication.processEvents()

    runs: list[int] = []
    original = window._update_actions

    def counted() -> None:
        runs.append(1)
        original()

    monkeypatch.setattr(window, "_update_actions", counted)
    window.object_tree.select_feature("obj_1", face)

    assert len(runs) == 1, f"{len(runs)} Läufe für einen Klick"
    assert window.selected_feature_kind() == "face"
    settled = {name: action.isEnabled() for name, action in window._op_actions.items()}
    original()
    again = {name: action.isEnabled() for name, action in window._op_actions.items()}
    assert settled == again, "was der Klick stellt, ist der Stand der vollständigen Auswahl"


def test_a_sleeping_network_drive_does_not_hold_the_recent_list(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ein Projekt auf dem ausgeschalteten NAS hielt den Start 21 s an.

    „Zuletzt geöffnet" fragte beim Fensteraufbau im Hauptthread jede Datei
    nach ihrer Existenz, und Windows antwortet für eine nicht erreichbare
    Netzadresse erst nach seinem Zeitlimit — gemessen am 22.09.2026 21 s
    (Review Fenster 0.5.0). Jetzt fragt ein eigener Thread; die Liste steht
    sofort und dünnt sich aus, wenn die Antwort da ist.
    """
    import time

    from app.ui import settings as settings_module

    here = tmp_path / "hier.p3d"
    here.write_text("{}", encoding="utf-8")
    gone = tmp_path / "nas" / "weg.p3d"
    answer = threading.Event()

    def asleep(entries: list[str]) -> list[Path]:
        answer.wait(10)
        return [Path(entry) for entry in entries if Path(entry).is_file()]

    monkeypatch.setattr(settings_module, "existing_paths", asleep)
    window.settings.recent = [str(here), str(gone)]

    started = time.perf_counter()
    window._show_recent()
    assert time.perf_counter() - started < 1.0, "the window waited for the file system"
    assert window.start_screen.recent_list.count() == 2, "the remembered list stands at once"

    answer.set()
    deadline = time.monotonic() + 5.0
    while window.start_screen.recent_list.count() != 1 and time.monotonic() < deadline:
        QApplication.processEvents()
        time.sleep(0.01)
    assert window.start_screen.recent_list.count() == 1, "the missing entry must go"


def test_a_local_recent_list_is_checked_before_it_is_shown(
    window: MainWindow, tmp_path: Path
) -> None:
    """Auf einer lokalen Platte gibt es kein Zwischenbild mit toten Einträgen."""
    here = tmp_path / "hier.p3d"
    here.write_text("{}", encoding="utf-8")
    window.settings.recent = [str(here), str(tmp_path / "geloescht.p3d")]

    window._show_recent()

    assert window.start_screen.recent_list.count() == 1
    assert not window._recent_poll.isActive()


def test_an_unreadable_plane_opens_its_step_at_the_plane(window: MainWindow) -> None:
    """„Eine andere Ebene wählen" führt in den Schritt, und zwar ans Ebenenfeld.

    Die Handlung stand bis zum 22.09.2026 als Kennung nur an ihrer
    Aufrufstelle (``planes._unreadable``) — ohne Konstante und ohne Handler
    im Fenster, also als Satz ohne Knopf beim häufigsten Rat eines
    Skizzenfehlers (Review Fenster 0.5.0). Geprüft am Klickweg über
    ``error_handlers()``, mit dem Fehler, den der Kern wirklich wirft.
    """
    from app.core.errors import PICK_PLANE
    from app.core.sketch import planes

    error = planes._unreadable("plane", "quer", "unknown_plane")
    assert PICK_PLANE in error.suggestions, "premise: the core offers the action"
    error.op_id = 7

    opened: list[tuple[int, str]] = []
    window.edit_operation = lambda op_id, field="": opened.append((op_id, field))  # type: ignore[method-assign]
    window.error_handlers()[PICK_PLANE.id](error)

    assert opened == [(7, "plane")]


def test_a_missing_selection_is_said_not_put_in_a_box(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """„Diese Operation braucht zwei Objekte" kam als modaler Kasten.

    Eine Auskunft ohne Entscheidung hielt das Fenster an, bis jemand *OK*
    klickte — auch auf Wegen, die aus einer Fehlerhandlung oder einer Karte
    kommen. Jetzt steht der Satz in der Ansage, wie beim Formen (Review
    Fenster 0.5.0, 22.09.2026).
    """

    def no_box(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("no modal box for a missing selection")

    monkeypatch.setattr(QMessageBox, "information", no_box)
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window.object_tree.tree.clearSelection()

    window.run_operation(REGISTRY.get("blend_union"))
    assert "zwei Objekte" in window.status_message.text()

    window.action_auto_split()
    assert window.status_message.text() == str(main_window_module._NEEDS_SELECTION)


def test_several_dropped_files_do_not_vanish_silently(window: MainWindow) -> None:
    """Von mehreren gezogenen Dateien kam eine — und kein Wort zu den übrigen.

    Mehrfachimport ist zurückgestellt (RM-131); die Abnahme dort verlangt aber
    „ohne still verworfene Dateien", und bis dahin fielen sie genau so weg
    (Review Fenster 0.5.0, 22.09.2026). Geprüft an beiden Ablageorten: am
    Fenster und an der Fläche des Startbildschirms.
    """
    from PySide6.QtCore import QMimeData, QUrl

    class _Drop:
        def __init__(self, data: QMimeData) -> None:
            self._data = data

        def mimeData(self) -> QMimeData:  # noqa: N802 - Qt gibt den Namen
            return self._data

        def acceptProposedAction(self) -> None:  # noqa: N802 - Qt gibt den Namen
            pass

    data = QMimeData()
    data.setUrls(
        [
            QUrl.fromLocalFile(str(MESHES / "cube_clean.stl")),
            QUrl.fromLocalFile(str(MESHES / "plate_holes.stl")),
            QUrl.fromLocalFile(str(MESHES / "plate_countersunk.stl")),
        ]
    )
    opened: list[Path] = []
    window.open_path = opened.append  # type: ignore[method-assign,assignment]

    window.dropEvent(_Drop(data))  # type: ignore[arg-type]

    assert opened == [MESHES / "cube_clean.stl"]
    assert window.status_message.text().startswith("2 weitere Dateien nicht geöffnet")

    window.status_message.setText("")
    from app.ui.start_screen import DropArea

    area = window.start_screen.findChild(DropArea)
    assert area is not None
    area.dropEvent(_Drop(data))  # type: ignore[arg-type]
    assert window.status_message.text().startswith("2 weitere Dateien nicht geöffnet")


def test_a_link_without_a_browser_lands_on_the_clipboard(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne Browser geschah auf den Klick nichts.

    ``QDesktopServices.openUrl`` sagt mit ``False``, dass kein Programm die
    Adresse annimmt; der Rückgabewert wurde nicht angesehen (Befund aus dem
    Paket „dialoge", Review 0.5.0). Beide Wege des Fensters — die Adresse aus
    einem Importfehler und *Ordner zeigen* nach dem Export — legen jetzt das
    Ziel in die Zwischenablage und sagen es.
    """
    import app.ui.dialogs as dialogs
    from app.core.errors import AppError

    monkeypatch.setattr(dialogs.QDesktopServices, "openUrl", lambda _url: False)
    clipboard = QApplication.clipboard()
    assert clipboard is not None

    error = AppError(detail="x", values={"url": "https://example.org/teil.stl"})
    window.error_handlers()["open_in_browser"](error)
    assert clipboard.text() == "https://example.org/teil.stl"
    assert "Zwischenablage" in window.status_message.text()

    window._export_folder = tmp_path
    window._reveal_export_folder()
    assert clipboard.text() == str(tmp_path)
    assert "Zwischenablage" in window.status_message.text()


def test_a_failed_import_hands_no_name_to_the_next_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein gescheiterter Import vererbt seinen Namen nicht an den nächsten gelungenen.

    ``_on_import_finished`` nimmt Datei und Download aus zwei Merkern, die der
    Anfang eines Imports setzt; der Fehlerweg räumte sie nicht ab. Ein
    Download nach einer unlesbaren Datei setzte diese in „Zuletzt geöffnet",
    eine Datei nach einem abgewiesenen Download meldete „Geladen:" mit dessen
    Namen. Stellvertreter statt Fenster: Gefragt ist der Weg über die zwei
    Slots, nicht ein Dialog.
    """
    from types import SimpleNamespace

    shown: list[Any] = []
    remembered: list[Any] = []
    said: list[str] = []
    monkeypatch.setattr(
        main_window_module, "show_error", lambda error, *_a, **_k: shown.append(error)
    )
    monkeypatch.setattr(
        main_window_module,
        "QApplication",
        SimpleNamespace(overrideCursor=lambda: None, restoreOverrideCursor=lambda: None),
    )
    view = SimpleNamespace(
        _pending_import=Path("verschoben.stl"),
        _pending_download="abgewiesen.3mf",
        _announcement="Bereit",
        status_message=SimpleNamespace(setText=lambda _text: None),
        settings=SimpleNamespace(remember=remembered.append),
        _store_settings=lambda: None,
        _show_recent=lambda: None,
        _show_start_screen=lambda _shown: None,
        announce=said.append,
    )

    MainWindow._on_import_failed(view, errors.UserError(title="Diese Datei ließ sich nicht lesen."))
    MainWindow._on_import_finished(view, True)

    assert shown, "der Fehler kam nicht an"
    assert remembered == [], "die unlesbare Datei landete in „Zuletzt geöffnet“"
    assert not any("abgewiesen.3mf" in text for text in said), said


def test_show_the_place_flies_and_marks_like_the_report_click() -> None:
    """*Stelle zeigen* am Befund fliegt und markiert wie der Klick auf seine Zeile.

    Beide Wege rechneten Abstand und Marke je für sich; ein Nachbessern am
    einen hätte den anderen nicht erreicht (Zwilling, ``zwillinge.md``). Der
    Knopf geht jetzt über ``_show_finding_at``, und hier stehen beide
    nebeneinander: derselbe Ansichtspunkt, derselbe Abstand, dieselbe Marke am
    selben Körper — nur der Titel ist der des Fehlers.
    """
    from types import SimpleNamespace

    calls: list[tuple[str, Any]] = []
    entry = SimpleNamespace(id="obj_1", mesh=SimpleNamespace(bounds=SimpleNamespace(diagonal=50.0)))
    viewport = SimpleNamespace(
        view_point_of=lambda point, object_id: (point[0] + 100.0, point[1], point[2]),
        fly_to=lambda point, reach: calls.append(("fly", (point, reach))),
        mark_finding=lambda point, title, object_id, outline=(): calls.append(
            ("mark", (point, title, object_id, outline))
        ),
        clear_finding_mark=lambda: calls.append(("clear", None)),
    )
    selected = {"id": ""}
    view = SimpleNamespace(
        viewport=viewport,
        object_tree=SimpleNamespace(
            select_object=lambda object_id: selected.update(id=object_id),
            selected=lambda: selected["id"],
        ),
        _quiet_command_allowed=lambda: True,
        _entry_of=lambda _error: entry,
        _finding_awaiting_map=object(),
    )
    view._show_finding_at = lambda *args: MainWindow._show_finding_at(view, *args)  # type: ignore[arg-type]
    place = (1.0, 2.0, 3.0)

    MainWindow._show_error_place(view, errors.AppError(title="Offen", values={"location": place}))  # type: ignore[arg-type]
    by_button = [call for call in calls if call[0] != "clear"]
    calls.clear()
    MainWindow._show_finding_at(view, "Offen", entry, place)  # type: ignore[arg-type]

    assert by_button == calls
    assert calls == [("fly", ((101.0, 2.0, 3.0), 70.0)), ("mark", (place, "Offen", "obj_1", ()))]
    assert view._finding_awaiting_map is None

    # **Mit Rand**: Die geschlossene Öffnung reist als Randkanten im Befund
    # (``Finding.outline``) und kommt bei der Marke an — die Ansicht umrandet
    # damit die neue Fläche (Handbuchbild *Ein Modell reparieren*, 3).
    rim = (((0.0, 0.0, 3.0), (4.0, 0.0, 3.0)), ((4.0, 0.0, 3.0), (0.0, 0.0, 3.0)))
    calls.clear()
    MainWindow._show_error_place(  # type: ignore[arg-type]
        view, errors.AppError(title="Offen", values={"location": place, "outline": rim})
    )
    marks = [call for call in calls if call[0] == "mark"]
    assert marks == [("mark", (place, "Offen", "obj_1", rim))], marks

    # Auch eine abgesagte Kantengruppe trägt alle getrennten Stellen durch
    # den echten Bericht und seine Handlung bis zum gemeinsamen Ansichtsweg.
    from app.core.scene.evaluate import _finding_from
    from app.core.types import Operation
    from app.ui.panels import actions_for_document, as_error

    omitted = (
        ((0.0, 0.0, 0.0), (2.0, 0.0, 0.0)),
        ((10.0, 0.0, 0.0), (12.0, 0.0, 0.0)),
        ((20.0, 0.0, 0.0), (22.0, 0.0, 0.0)),
    )
    target = (1.0, 0.0, 0.0)
    failure = errors.GeometryError(
        title="Nicht verrundet",
        values={"location": target, "outline": omitted, "skipped": 3},
        object_id="obj_1",
        suggestions=(errors.SHOW_LOCATION, errors.CORRECT_INPUT),
    )
    operation = Operation(id=9, op="fillet_edges", inputs=("obj_1",), outputs=("obj_1",), params={})
    finding = _finding_from(failure, operation)
    calls.clear()
    MainWindow._show_error_place(view, as_error(finding))  # type: ignore[arg-type]

    assert calls == [
        ("clear", None),
        ("fly", ((101.0, 0.0, 0.0), 70.0)),
        ("mark", (target, "Nicht verrundet", "obj_1", omitted)),
    ], "Fehler und Abschlussbericht müssen alle ausgelassenen Stellen bis zur Marke tragen"
    assert errors.SHOW_LOCATION in actions_for_document(finding, None)
    assert finding.object_id == "obj_1" and finding.op_id == 9
    assert "location" not in finding.values and "outline" not in finding.values
    assert failure.values["location"] == target and failure.values["outline"] == omitted


def test_a_closing_window_takes_no_late_feature_answer(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Kernauskünfte eines Merkmalklicks verfallen, wenn das Fenster zugeht (RM-232).

    Ihre Antwort kommt über ``_answers_arrived`` und ``_answers_failed`` an,
    und beide fragten anders als die Karten nicht nach dem Schließen: Ein
    schließendes Fenster baute das Merkmalfenster auf, begann eine Platzierung
    samt Arbeiter und meldete einen Fehler, den niemand mehr liest.
    ``wait_for_workers`` lässt den Arbeiter los wie die Karte ihren Auftrag.
    """
    from app.ui.main_window import _FeatureAnswersWorker

    reported: list[object] = []
    monkeypatch.setattr(window, "_on_error", reported.append)
    late = _FeatureAnswersWorker(lambda: None)  # nie gestartet: gefragt ist nur die Kennung
    window._answers_worker = late

    window.wait_for_workers(0)
    window._answers_failed(late, "Traceback …")

    assert window._answers_worker is None
    assert reported == [], "das schließende Fenster meldete einen Fehler, den niemand liest"


@pytest.mark.parametrize("closing", [False, True])
def test_a_late_manufacturer_foundation_starts_no_run_in_a_closing_window(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch, closing: bool
) -> None:
    """Kommt die Herstellergrundlage nach ``release``, wird nicht mehr ausgewertet.

    Seit ``e0e3cf982`` (Entscheidung L) wertet das Fenster ein zweites Mal
    aus, wenn die Grundlage eine andere Stützschwelle bringt als die Tabelle,
    mit der der erste Lauf rechnete. ``_start_foundation`` fragte nach dem
    Schließen, ``_foundation_found`` nicht: Im Abbau der Suite startete eine
    späte Grundlage einen Auswertungsarbeiter, dessen Frage niemand mehr
    beantwortete, und der Prozess endete danach mit 0xC0000409 — jeder Lauf von
    ``test_active_matching_questions_end_when_their_evaluation_is_invalidated``
    in den Varianten mit neuem Lauf. Die Gegenprobe ohne Schließen wertet aus.
    """
    from app.core.export import manufacturer
    from app.core.scene import EvaluationResult
    from app.core.types import Scene

    runs: list[bool] = []
    key = ("grundlage",)
    window.session.last_result = EvaluationResult(scene=Scene(objects={}))
    monkeypatch.setattr(window, "_foundation_key", lambda _quality: key)
    monkeypatch.setattr(window.session, "evaluation_follows", lambda _settings: False)
    monkeypatch.setattr(window.session, "evaluate_async", lambda: runs.append(True))
    foundation = manufacturer.Foundation(settings=window.effective_print_settings())
    if closing:
        window.release()

    window._foundation_found(key, foundation)

    assert runs == ([] if closing else [True])


def test_changing_a_migrated_slot_angle_returns_it_to_the_current_frame() -> None:
    """Ein Griffwinkel ist heute gemessen; eine reine Längenänderung bleibt alt."""
    from types import SimpleNamespace

    from app.core.sketch.planes import frame_of

    axis = (0.001, 0.0, 1.0)
    previous = frame_of(axis, (0.0, 0.0, 0.0))
    feature = SimpleNamespace(
        kind="slot",
        created_by=17,
        params={
            "axis": axis,
            "direction": previous.x_axis,
            "centre": (0.0, 0.0, 0.0),
            "length": 20.0,
            "diameter": 6.0,
        },
    )
    step = SimpleNamespace(
        id=17, op="slot_hole", params={"slot_angle": 0.0, "measured_frame": True}
    )
    result = SimpleNamespace(
        scene=SimpleNamespace(objects={"obj_1": SimpleNamespace(features={"slot_1": feature})})
    )
    window = SimpleNamespace(
        object_tree=SimpleNamespace(selected=lambda: "obj_1"),
        session=SimpleNamespace(
            last_result=result,
            project=SimpleNamespace(document=SimpleNamespace(ops=[step])),
        ),
    )
    values = {
        "slot_angle": 0.0,
        "slot_length": 20.0,
        "x": 0.0,
        "y": 0.0,
        "z": 0.0,
    }

    changed_angle = MainWindow._prepare_slot_change(window, "slot_1", values)
    changed_length = MainWindow._prepare_slot_change(
        window, "slot_1", {**values, "slot_angle": 90.0, "slot_length": 25.0}
    )

    assert changed_angle is not None
    assert changed_angle.change_values == {"slot_angle": 0.0, "measured_frame": False}
    assert changed_length is not None
    assert changed_length.change_values == {"slot_length": 25.0}


def test_three_arrow_steps_in_the_parameter_bar_turn_the_number_by_three(
    window: MainWindow,
) -> None:
    """Dreimal ↑ in *Breite* sind drei Millimeter, und der Fokus bleibt im Feld (RM-355).

    Die Leiste baute nach jeder Änderung alle Zeilen neu, und das bediente
    Feld ging unter: Nach dem ersten ↑ war der Fokus weg, ein zweites traf
    nichts mehr — 61 statt 62. Jetzt bleibt das Feld dasselbe Widget.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.i18n import _

    session = window.session
    window.show()
    window.open_path(MESHES / "cube_clean.stl")
    assert session.wait_for_idle(30_000)
    assert session.add_parameter(Parameter(name="breite", value=60.0, unit="mm", title=_("Breite")))
    session.wait_for_idle()
    QApplication.processEvents()
    editor = window.parameters._editors["breite"]
    editor.setSingleStep(1.0)
    window.activateWindow()
    editor.setFocus()
    QApplication.processEvents()
    assert editor.hasFocus(), "das Feld empfängt die Taste"

    for _step in range(3):
        focused = QApplication.focusWidget()
        assert focused is not None, "der Fokus ist noch da"
        QTest.keyClick(focused, Qt.Key.Key_Up)
        for _round in range(3):
            QApplication.processEvents()
        session.wait_for_idle()
        QApplication.processEvents()

    assert session.project.document.parameters["breite"].value == pytest.approx(63.0)
    assert window.parameters._editors["breite"] is editor, "dieselbe Zeile, kein Neubau"
    focus = QApplication.focusWidget()
    assert focus is editor or editor.isAncestorOf(focus), "der Fokus bleibt in Breite"


def _bound_width_project(session: Session) -> float:
    """Ein Quader, dessen Breite das Maß *breite* liest — zurück kommt die Obergrenze des Felds."""
    from app.core.registry import REGISTRY
    from app.core.scene import OperationDraft
    from app.i18n import _

    assert session.add_parameter(Parameter(name="breite", value=60.0, unit="mm", title=_("Breite")))
    session.apply("Quader", [OperationDraft(op="create_box", params={"width": "=@breite"})])
    assert session.wait_for_idle(30_000)
    entry = {item.name: item for item in REGISTRY.get("create_box").params.spec()}["width"]
    assert entry.maximum is not None
    return float(entry.maximum)


def test_a_parameter_beyond_its_field_is_refused_and_the_body_stays(session: Session) -> None:
    """Breite 5000 lief durch, die Kette hielt am Quader an, und die Szene war leer (RM-354).

    Jetzt sagt ``change_parameter`` die Grenze des Felds samt Schritt, das
    Dokument bleibt, und der Körper steht weiter da.
    """
    high = _bound_width_project(session)
    refused: list[errors.AppError] = []
    session.failed.connect(refused.append)

    assert not session.change_parameter("breite", high + 4000.0)
    session.wait_for_idle()

    assert session.project.document.parameters["breite"].value == pytest.approx(60.0)
    assert refused and isinstance(refused[-1], errors.ValidationError)
    assert refused[-1].constraint == "maximum"
    assert refused[-1].values["maximum"] == pytest.approx(high)
    assert session.last_result is not None and "obj_1" in session.last_result.scene.objects
    assert session.change_parameter("breite", high), "die Grenze selbst geht"


def test_the_parameter_bar_knows_the_limit_of_the_field_it_feeds(window: MainWindow) -> None:
    """Die Zeile *Breite* nimmt die Grenze des Quaderfelds und lehnt 5000 mit ihr ab (RM-354)."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    window.show()
    high = _bound_width_project(window.session)
    QApplication.processEvents()
    editor = window.parameters._editors["breite"]
    assert editor.maximum() == pytest.approx(high)

    window.activateWindow()
    editor.setFocus()
    editor.lineEdit().selectAll()
    QTest.keyClicks(editor.lineEdit(), str(int(high + 4000.0)))
    QTest.keyClick(editor.lineEdit(), Qt.Key.Key_Return)
    for _round in range(3):
        QApplication.processEvents()
    window.session.wait_for_idle()

    assert window.session.project.document.parameters["breite"].value == pytest.approx(60.0)
    said = window.parameters.refusal_text()
    assert str(int(high)) in said.replace(".", "").replace(",", ""), said


def test_correcting_a_field_that_reads_a_parameter_goes_to_the_parameter_bar(
    window: MainWindow,
) -> None:
    """*Eingabe korrigieren* an „=@breite“ führt in die Zeile der Leiste (RM-354).

    Im Schrittdialog stand „=@breite“, und wer dort eine Zahl tippte, trennte
    still die Bindung. Der Halt wird hier am Dokument erzwungen, an Leiste
    und Sitzung vorbei — so, wie eine ältere Datei ihn mitbringt.
    """
    import dataclasses

    window.show()
    high = _bound_width_project(window.session)
    document = window.session.project.document
    document.parameters["breite"] = dataclasses.replace(
        document.parameters["breite"], value=high + 4000.0
    )
    result = window.session.evaluate_now()
    assert result.stopped_at == 1
    QApplication.processEvents()
    window.activateWindow()

    error = errors.ValidationError(
        field="width", detail="zu breit", constraint="maximum", values={"maximum": high}
    )
    error.op_id = 1
    window._correct_after_error(error)
    QApplication.processEvents()

    editor = window.parameters._editors["breite"]
    assert editor.hasFocus(), "der Fokus steht in der Zeile des Maßes"
    assert window._op_dialog is None, "kein Schrittdialog mit „=@breite“"


def test_a_new_expression_beyond_its_field_is_refused_too(session: Session) -> None:
    """*Parameter ändern …* mit einem Ausdruck über der Feldgrenze: dieselbe Absage (RM-354)."""
    import dataclasses

    high = _bound_width_project(session)
    refused: list[errors.AppError] = []
    session.failed.connect(refused.append)
    existing = session.project.document.parameters["breite"]

    assert not session.edit_parameter(
        "breite", dataclasses.replace(existing, expression=f"={high + 4000.0:g}")
    )

    assert session.project.document.parameters["breite"] == existing
    assert refused and getattr(refused[-1], "constraint", None) == "maximum"


def test_a_halt_at_the_first_step_keeps_the_last_picture(window: MainWindow) -> None:
    """§15.3: nie ein leeres Fenster — auch nicht, wenn schon der erste Schritt anhält (RM-354).

    Ein Halt weiter hinten zeigt den Stand davor; am ersten Schritt ist der
    leer, und die Ansicht stand ohne Körper da. Erzwungen wird der Halt am
    Dokument, an Leiste und Sitzung vorbei.
    """
    import dataclasses

    window.show()
    high = _bound_width_project(window.session)
    QApplication.processEvents()
    document = window.session.project.document
    document.parameters["breite"] = dataclasses.replace(
        document.parameters["breite"], value=high + 4000.0
    )
    halted = window.session.evaluate_now()
    assert halted.stopped_at == 1 and not halted.scene.objects

    window._on_scene(halted)
    QApplication.processEvents()

    shown = window.viewport._requested_result
    assert shown is not None and "obj_1" in shown.scene.objects, "der Körper bleibt im Bild"
    assert window._halted, "und die Statuszeile sagt, dass die Kette anhält"


def _a_stored_width_beyond_its_field(window: MainWindow) -> float:
    """*Breite* jenseits der Feldgrenze, wie eine Datei sie mitbringt — zurück die Grenze."""
    import dataclasses

    window.show()
    high = _bound_width_project(window.session)
    document = window.session.project.document
    document.parameters["breite"] = dataclasses.replace(
        document.parameters["breite"], value=high + 4000.0
    )
    window._on_scene(window.session.evaluate_now())
    window._refresh_parameters()
    QApplication.processEvents()
    return high


def _type_into(window: MainWindow, name: str, number: float) -> None:
    """Eine Zahl in die Zeile der Leiste tippen und mit der Eingabetaste übernehmen."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    editor = window.parameters._editors[name]
    window.activateWindow()
    editor.setFocus()
    editor.lineEdit().selectAll()
    QTest.keyClicks(editor.lineEdit(), str(int(number)))
    QTest.keyClick(editor.lineEdit(), Qt.Key.Key_Return)
    for _round in range(3):
        QApplication.processEvents()
    window.session.wait_for_idle()
    QApplication.processEvents()


def test_a_stored_number_beyond_its_field_shows_and_takes_the_correction(
    window: MainWindow,
) -> None:
    """Die Leiste zeigt die Zahl aus der Datei und nimmt die Korrektur an (RM-447).

    Qt klemmte 5000 auf die Feldgrenze 1000: Die Leiste zeigte 1000, 1000 +
    Enter war keine Änderung, und der Halt blieb — obwohl *Eingabe
    korrigieren* genau in dieses Feld führt. In 0.5.1 stand dort 5000.
    """
    high = _a_stored_width_beyond_its_field(window)
    editor = window.parameters._editors["breite"]
    assert editor.value() == pytest.approx(high + 4000.0), "die gespeicherte Zahl steht da"
    said = window.parameters.refusal_text()
    assert str(int(high)) in said.replace(".", "").replace(",", ""), said

    _type_into(window, "breite", high)

    document = window.session.project.document
    assert document.parameters["breite"].value == pytest.approx(high)
    result = window.session.last_result
    assert result is not None and result.stopped_at is None, "der Halt ist gelöst"
    assert window.parameters.refusal_text() == "", "und der Satz zur Grenze geht"


def test_a_refused_derived_change_shows_the_valid_number_again(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lehnt die Sitzung eine Zahl ab, zeigt die Leiste wieder, was gilt (RM-447).

    *Breite* hat keine eigene Grenze, das Feld liest sie verdoppelt. 600 nimmt
    das Feld an, die Sitzung lehnt ab — die Leiste zeigte weiter 600.
    """
    from app.core.scene import OperationDraft

    shown: list[errors.AppError] = []
    monkeypatch.setattr(main_window_module, "show_error", lambda error, *_args: shown.append(error))
    window.show()
    session = window.session
    assert session.add_parameter(Parameter(name="breite", value=100.0, unit="mm"))
    assert session.add_parameter(
        Parameter(name="doppelt", value=200.0, unit="mm", expression="=@breite*2")
    )
    session.apply("Quader", [OperationDraft(op="create_box", params={"width": "=@doppelt"})])
    assert session.wait_for_idle(30_000)
    QApplication.processEvents()

    _type_into(window, "breite", 600.0)

    assert shown and getattr(shown[-1], "constraint", None) == "maximum", "die Sitzung lehnt ab"
    assert session.project.document.parameters["breite"].value == pytest.approx(100.0)
    assert window.parameters._editors["breite"].value() == pytest.approx(100.0)


def test_remote_parameters_name_the_limit_and_keep_title_and_bounds(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Fernsteuerung sagt die Grenze und behält Titel und Grenzen (RM-447).

    ``set_parameter`` über der Grenze antwortete „Der Wert ist schon so
    eingestellt.“, und ``add_parameter`` verlor ``minimum``, ``maximum`` und
    ``title``, obwohl das Werkzeugschema sie anbietet.
    """
    monkeypatch.setattr(main_window_module, "show_error", lambda *_args: None)
    high = _bound_width_project(window.session)

    said = window._remote_parameter("set_parameter", {"name": "breite", "value": high + 4000.0})
    assert str(int(high)) in said.replace(".", "").replace(",", ""), said
    assert window.session.project.document.parameters["breite"].value == pytest.approx(60.0)
    same = window._remote_parameter("set_parameter", {"name": "breite", "value": 60.0})
    assert same == tr("Der Wert ist schon so eingestellt.")

    window._remote_parameter(
        "add_parameter",
        {"name": "hoehe", "value": 30.0, "minimum": 10.0, "maximum": 50.0, "title": "Höhe"},
    )
    made = window.session.project.document.parameters["hoehe"]
    assert (made.minimum, made.maximum, str(made.title)) == (10.0, 50.0, "Höhe")


def _width_bound_box(session: Session) -> None:
    """Ein Quader, dessen Breite das Maß *breite* (80 mm) liest."""
    from app.core.scene import OperationDraft
    from app.i18n import _

    assert session.add_parameter(Parameter(name="breite", value=80.0, unit="mm", title=_("Breite")))
    session.apply("Quader", [OperationDraft(op="create_box", params={"width": "=@breite"})])
    assert session.wait_for_idle(30_000)


def test_an_export_during_the_recalculation_writes_the_new_state(
    window: MainWindow, tmp_path: Path
) -> None:
    """Breite 80 → 100, sofort exportieren: Die Datei ist 100 mm breit (RM-352).

    Geschrieben wurde das vorige Ergebnis mit dem neuen Dokument — Bild und
    Verlauf zeigten 100 mm, die Datei 80 mm, und die Quittung meldete Erfolg.
    Jetzt wartet der Export auf das Ergebnis, das zum Dokument gehört.
    """
    import trimesh

    _width_bound_box(window.session)
    QApplication.processEvents()
    assert window.session.change_parameter("breite", 100.0)
    target = tmp_path / "quader.stl"

    window._start_export(target, "stl")
    assert window._export_waiting is not None or window._export_worker is not None
    assert window.session.wait_for_idle(30_000)
    QApplication.processEvents()
    wait_for_export(window)

    assert target.exists(), "die Datei entsteht, sobald das Ergebnis steht"
    extents = trimesh.load(target, force="mesh").extents
    assert max(extents) == pytest.approx(100.0, abs=1e-3), extents


def test_a_waiting_export_writes_nothing_when_the_chain_halts(
    window: MainWindow, tmp_path: Path
) -> None:
    """Hält die Kette an, entsteht keine Datei — sie zeigte den Stand davor (RM-352)."""
    import dataclasses

    _width_bound_box(window.session)
    QApplication.processEvents()
    document = window.session.project.document
    document.parameters["breite"] = dataclasses.replace(
        document.parameters["breite"], value=1_000_000.0
    )
    window.session.result_current = False
    target = tmp_path / "quader.stl"

    window._start_export(target, "stl")
    assert window._export_waiting is not None, "der Export wartet"
    window._on_scene(window.session.evaluate_now())
    QApplication.processEvents()
    wait_for_export(window)

    assert window._export_waiting is None
    assert not target.exists(), "aus einem angehaltenen Stand wird keine Datei"


def _a_cone_in_draft(window: MainWindow) -> None:
    """Ein Kegel, der im Entwurf mit halb so vielen Dreiecken steht wie fein."""
    assert window.session.apply(
        "Kegel",
        [
            OperationDraft(
                op="create_cone",
                params={
                    "bottom_diameter": 30.0,
                    "top_diameter": 10.0,
                    "height": 20.0,
                    "segments": 64,
                },
            )
        ],
    )
    assert window.session.wait_for_idle(30_000)
    QApplication.processEvents()
    assert window.session.last_quality == "draft", "Voraussetzung: das Fenster rechnet im Entwurf"


def _fine_triangles(window: MainWindow) -> int:
    """Die Dreiecke der feinen Rechnung desselben Dokuments, unabhängig vom Fenster."""
    from app.core.geom.mesh import as_mesh_data
    from app.core.scene import evaluate
    from app.core.scene.project import ProjectSources

    session = window.session
    fine = evaluate(
        session.project.document,
        session.profile,
        sources=ProjectSources(session.project),
        quality="fine",
    )
    return sum(as_mesh_data(entry.mesh).triangle_count for entry in fine.scene.objects.values())


def test_the_export_writes_the_fine_calculation(window: MainWindow, tmp_path: Path) -> None:
    """Die Datei trägt die feine Rechnung, nicht den Entwurf des Fensters (RM-426).

    Das Fenster rechnet im Entwurf (§31). Geschrieben wurde dieser Entwurf —
    ein Kegel mit der Hälfte seiner Dreiecke, ein verschmolzenes Teil mit
    einem Viertel —, während der Befund ``blend.draft`` versprach, der
    Export rechne fein.
    """
    import trimesh

    from app.core.geom.mesh import as_mesh_data

    _a_cone_in_draft(window)
    result = window.session.last_result
    assert result is not None
    draft = sum(as_mesh_data(entry.mesh).triangle_count for entry in result.scene.objects.values())
    fine = _fine_triangles(window)
    assert fine > draft, "Voraussetzung: fein und Entwurf unterscheiden sich"
    target = tmp_path / "kegel.stl"

    window._start_export(target, "stl")
    assert window.session.wait_for_idle(30_000)
    QApplication.processEvents()
    wait_for_export(window)

    written = sum(len(trimesh.load(path, force="mesh").faces) for path in tmp_path.glob("*.stl"))
    assert written == fine, (written, fine, draft)
    assert window.session.last_quality == "fine"


def test_slicing_waits_for_the_fine_calculation(window: MainWindow) -> None:
    """Ein Klick auf *Slicen* bindet sich an die feine Rechnung (RM-426).

    Warten ist keine Sperre: Der Auftrag merkt sich den Klick, bestellt die
    feine Rechnung und läuft, sobald sie steht — den Entwurf bekommt der
    Slicer nicht.
    """
    from app.ui.print_settings_dialog import PrintSettingsDialog

    _a_cone_in_draft(window)
    dialog = PrintSettingsDialog(window.session, window.settings, window)
    ran: list[str] = []

    assert dialog._wait_for_fine(lambda: ran.append(window.session.last_quality))
    assert dialog.state.text() == tr("Wartet auf die feine Berechnung des Modells …")
    assert not ran, "der Klick wartet"
    assert window.session.wait_for_idle(30_000)
    QApplication.processEvents()

    assert ran == ["fine"], "der Klick läuft einmal, auf der feinen Rechnung"
    assert not dialog._wait_for_fine(lambda: ran.append("zweimal")), "fein steht schon"
    dialog.close()


def test_an_empty_scene_invites_to_start_and_steps_aside_for_the_first_body(
    window: MainWindow,
) -> None:
    """Die leere Szene lädt zum Anfangen ein — auf drei Wegen dorthin (RM-370).

    Nach *Neues Projekt* zeigte die Ansicht nur den Bauraum. Jetzt stehen dort
    die Einstiege, über die Tastatur erreichbar und mit Namen; sie gehen mit
    dem ersten Körper und kommen bei jeder leeren Szene wieder: neues
    Projekt, Strg+Z bis zum Anfang, alle Körper gelöscht.
    """
    from PySide6.QtCore import Qt as QtCore_Qt

    from app.core.scene import OperationDraft

    window.show()
    window.session._dirty = False
    window.start_screen.new_button.click()
    window.session.wait_for_idle()
    QApplication.processEvents()

    invitation = window.viewport.invitation
    assert invitation.isVisibleTo(window), "neues Projekt: die Einladung steht"
    shown = {key for key, button in invitation.buttons.items() if button.isVisibleTo(window)}
    assert {"create_box", "create_cylinder", "draw", "parts"} <= shown, shown
    for key in shown:
        button = invitation.buttons[key]
        assert button.accessibleName(), key
        assert button.focusPolicy() & QtCore_Qt.FocusPolicy.TabFocus, key

    invitation.buttons["create_box"].click()
    QApplication.processEvents()
    assert window._op_dialog is not None, "der Einstieg öffnet den Schritt wie das Menü"
    window._op_dialog.accept()
    window.session.wait_for_idle()
    QApplication.processEvents()
    assert window.session.last_result.scene.objects, "ein Quader steht"
    assert not invitation.isVisibleTo(window), "mit dem ersten Körper tritt sie zur Seite"

    window.action_undo()
    window.session.wait_for_idle()
    QApplication.processEvents()
    assert not window.session.last_result.scene.objects
    assert invitation.isVisibleTo(window), "Strg+Z bis zum Anfang: sie ist wieder da"

    window.session.apply("Quader", [OperationDraft(op="create_box", params={})])
    window.session.wait_for_idle()
    QApplication.processEvents()
    assert not invitation.isVisibleTo(window)
    (body,) = window.session.last_result.scene.objects
    window.session.apply("Löschen", [OperationDraft(op="delete_object", inputs=(body,))])
    window.session.wait_for_idle()
    QApplication.processEvents()
    assert invitation.isVisibleTo(window), "alles gelöscht: sie ist wieder da"
