"""Lokale Suche bleibt lesend; Auswahl, Vorschau und Übernehmen teilen den Auftrag."""

from __future__ import annotations

import copy
import importlib
import threading

import numpy as np
import pytest
import trimesh
from PySide6.QtWidgets import QDialog

from app.core.bootstrap import load_operations
from app.core.geom.mesh import MeshData
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.cache import ResultCache
from app.core.scene.project import ProjectSources, new_project
from app.core.types import Finding, Parameter, Source
from tests.helpers import blind_cylinder, bore_seed
from tests.ui_helpers import wait_until


@pytest.mark.parametrize("entry", ["arm", "begin"])
def test_local_recognition_entry_keeps_the_pending_measure_owner(entry):
    """Menü und direkter Rechtsklick nehmen einem Maßentwurf keine Eingabe weg."""
    from types import SimpleNamespace

    from app.ui.local_recognition_flow import LocalRecognitionFlow
    from app.ui.main_window import MainWindow

    notices = []
    host = SimpleNamespace(begun=True, committing=False)
    view = SimpleNamespace(_quiet_host=host)
    view._quiet_selection_allowed = lambda: MainWindow._quiet_selection_allowed(view)
    view._say_the_change_comes_first = lambda: notices.append("finish-draft")
    view._quiet_command_allowed = lambda: MainWindow._quiet_command_allowed(view)
    flow = SimpleNamespace(view=view)
    hit = ("obj_1", (0.0, 0.0, 0.0), 0, None)

    getattr(LocalRecognitionFlow, entry)(flow, *(() if entry == "arm" else (hit,)))

    assert view._quiet_host is host
    assert notices == ["finish-draft"]


def test_local_recognition_replaces_passive_measures_before_taking_the_pointer():
    """Der erlaubte Wechsel räumt den alten Besitzer vor dem neuen Zeiger ab."""
    from types import SimpleNamespace

    from app.ui.local_recognition_flow import LocalRecognitionFlow

    calls = []
    view = SimpleNamespace(
        _quiet_command_allowed=lambda: True,
        _quiet_host=object(),
        _op_dialog=None,
        session=SimpleNamespace(busy=False, last_result=object()),
        end_quiet_placement=lambda: calls.append("end-measures"),
        viewport=SimpleNamespace(
            set_placement_pointer=lambda pointer: calls.append(pointer),
            set_surface_picker=lambda _callback: None,
        ),
        announce=lambda text: calls.append("notice"),
    )
    flow = SimpleNamespace(
        view=view,
        invalidate=lambda: calls.append("invalidate"),
        pointer="local-pointer",
        _pick_surface="local-surface",
    )

    LocalRecognitionFlow.arm(flow)

    assert calls == ["invalidate", "end-measures", "local-pointer", "notice"]
    assert flow.armed


@pytest.mark.parametrize(
    ("constraint", "ways"),
    [
        ("local_seed", ["pick_elsewhere"]),
        ("local_ambiguous_seed", ["pick_elsewhere"]),
        ("local_topology", ["repair_mesh", "pick_elsewhere"]),
        ("local_boundary", ["enlarge_radius", "pick_elsewhere"]),
        ("local_no_feature", ["pick_elsewhere", "enlarge_radius"]),
        ("local_budget", ["shrink_radius", "decimate_mesh"]),
        ("minimum", ["correct_input"]),
    ],
)
def test_local_error_offers_the_ways_its_sentence_names(constraint, ways):
    """Je Grund die Wege, die sein Satz nennt — und jeder hat einen Knopf (E6).

    Bis zum 24.09.2026 trug jeder Grund einen Knopf für zwei genannte Wege;
    bei den Bereichsgründen führte er nur in das Suchradiusfeld. Der erste Weg
    ist der Hauptknopf, und jede Handlung hat im Dialog ihren Empfänger.
    """
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.core.errors import CORRECT_INPUT, ValidationError
    from app.ui.local_recognition import LocalRecognitionDialog

    errors = []
    dialog = Mock(
        _closed=False,
        _revision=4,
        state=SimpleNamespace(
            set_error=lambda problem, handlers: errors.append((problem, handlers))
        ),
    )
    problem = ValidationError(constraint=constraint, suggestions=[CORRECT_INPUT])

    LocalRecognitionDialog._failed(dialog, 4, problem)

    offered, handlers = errors[0]
    assert [action.id for action in offered.suggestions] == ways
    assert [action.primary for action in offered.suggestions] == [True] + [False] * (len(ways) - 1)
    assert set(ways) <= set(handlers), "jeder angebotene Weg hat einen Empfänger"
    dialog.save_button.setEnabled.assert_called_once_with(False)
    dialog.edit_button.setEnabled.assert_called_once_with(False)


@pytest.mark.parametrize(
    ("way", "expected"),
    [
        ("pick_elsewhere", ["point"]),
        ("enlarge_radius", ["radius 15"]),
        ("shrink_radius", ["radius 6.667"]),
        ("decimate_mesh", ["operation decimate_mesh obj_1"]),
        ("repair_mesh", ["operation repair obj_1"]),
    ],
)
def test_each_local_way_does_what_its_button_says(way, expected):
    """Ein Klick statt Fokus, Tippen, Warten: Der Suchradius ändert sich gleich."""
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.core.errors import ValidationError
    from app.core.perceive.ops import DetectRegionParams
    from app.ui.local_recognition import LocalRecognitionDialog

    done = []
    constraint = {
        "pick_elsewhere": "local_seed",
        "enlarge_radius": "local_boundary",
        "shrink_radius": "local_budget",
        "decimate_mesh": "local_budget",
        "repair_mesh": "local_topology",
    }[way]
    errors = []
    radius = Mock()
    radius.value.return_value = 10.0
    radius.set_value.side_effect = lambda value: done.append(f"radius {round(value, 3):g}")
    radius.setFocus.side_effect = lambda: done.append("focus")
    dialog = Mock(
        _closed=False,
        _revision=4,
        _object_id="obj_1",
        _radius_spec=next(e for e in DetectRegionParams.spec() if e.name == "radius"),
        radius=radius,
        state=SimpleNamespace(
            set_error=lambda problem, handlers: errors.append((problem, handlers))
        ),
        pickRequested=SimpleNamespace(emit=lambda: done.append("point")),
        operationRequested=SimpleNamespace(
            emit=lambda name, body: done.append(f"operation {name} {body}")
        ),
    )
    problem = ValidationError(constraint=constraint)

    LocalRecognitionDialog._failed(dialog, 4, problem)
    errors[0][1][way](problem)

    assert done == expected


def test_an_expression_in_the_search_radius_keeps_its_binding():
    """Ein Ausdruck wird nicht still zur Zahl; das Feld bekommt den Fokus."""
    from unittest.mock import Mock

    from app.core.perceive.ops import DetectRegionParams
    from app.ui.local_recognition import LocalRecognitionDialog

    done = []
    radius = Mock()
    radius.value.return_value = "=@suchweite"
    radius.set_value.side_effect = done.append
    radius.setFocus.side_effect = lambda: done.append("focus")
    dialog = Mock(
        _radius_spec=next(e for e in DetectRegionParams.spec() if e.name == "radius"),
        radius=radius,
    )
    LocalRecognitionDialog._scale_radius(dialog, 1.5)
    assert done == ["focus"]


def test_local_worker_preserves_the_error_cause_for_the_dialog(monkeypatch):
    """Der Umweg über den Auswertungsbefund verliert die Ursache nicht."""
    from types import SimpleNamespace
    from unittest.mock import Mock

    import app.ui.local_recognition as local

    finding = Finding(
        "op.detect_region.ValidationError",
        "error",
        "Die gewählte Stelle ist ungültig.",
        values={"constraint": "local_seed"},
    )
    result = SimpleNamespace(
        complete=False, scene=SimpleNamespace(report=SimpleNamespace(findings=[finding]))
    )
    monkeypatch.setattr(local, "History", lambda _document: Mock())
    monkeypatch.setattr(local, "evaluate", lambda *_args, **_kwargs: result)
    worker = Mock(document={}, original_ray=None, revision=7)

    local._RecognitionWorker.work(worker)

    revision, problem = worker.failed.emit.call_args.args
    assert revision == 7
    assert problem.values == {"constraint": "local_seed"}
    worker.ready.emit.assert_not_called()


@pytest.mark.parametrize("caller", ["local", "panel"])
@pytest.mark.parametrize("phase", ["contact", "containment", "remember"])
def test_feature_workers_cancel_the_separate_body_proof_without_remembering_it(
    profile, monkeypatch, caller, phase
):
    """Der echte Arbeiteraufruf reicht seinen Schalter bis in beide Sicherheitsbelege.

    In einer Ø6-Bohrung steht ein freier Ø5-Stift zwischen z=2 und z=8 mm.
    Seine Hülle liegt im Hüllquader der Platte: Neben der Kontaktprüfung
    wird deshalb wirklich die Einschließungsfrage gestellt. Abbruch darf
    weder eine fertige Fensterauskunft noch den gemeinsamen Kernmerker setzen.
    """
    from dataclasses import replace
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.core.geom import prepare_ops, repair
    from app.core.geom.prepare_ops import hole_is_clear
    from app.core.perceive.features import forget_cache
    from app.ui import local_recognition as local
    from app.ui.main_window import MainWindow
    from tests.helpers import bore_plate

    load_operations()
    plate = bore_plate("mesh", [(0, -1), (3, -1), (3, 11), (0, 11), (0, -1)])
    feature = next(value for value in plate.features.values() if value.kind == "hole")
    pin = trimesh.creation.cylinder(radius=2.5, height=6.0, sections=48)
    pin.apply_translation((0.0, 0.0, 5.0))
    mesh = MeshData.of(trimesh.util.concatenate((plate.mesh.raw, pin)))
    entry = replace(plate, mesh=mesh, features={feature.id: feature})
    assert mesh.component_count == 2 and not hole_is_clear(mesh, feature)
    forget_cache()
    result = SimpleNamespace(
        complete=True,
        answers={},
        scene=SimpleNamespace(objects={entry.id: entry}, parameters={}),
    )
    answers = []
    aborted = []
    failed = []
    if caller == "local":
        monkeypatch.setattr(
            local,
            "History",
            lambda _document: Mock(apply=Mock(return_value=SimpleNamespace(ops=("op_1",)))),
        )
        monkeypatch.setattr(local, "evaluate", lambda *_args, **_kwargs: result)
        monkeypatch.setattr(local, "features_in_region", lambda *_args, **_kwargs: (feature.id,))
        worker = local._RecognitionWorker(
            new_project().document,
            OperationDraft("detect_region", inputs=(entry.id,), params={"radius": 8.0}),
            profile,
            7,
            None,
            None,
        )
        worker.ready.connect(lambda _revision, reply: answers.append(reply.actions[feature.id]))
        worker.aborted.connect(aborted.append)
        worker.failed.connect(lambda *_args: failed.append(_args))
    else:
        # Der Fensteraufruf baut den echten Arbeiter samt Kopie und Rückkanal;
        # nur Fenster und Threadstart bleiben Attrappen. work() läuft direkt.
        view = Mock(_answers_worker=None)
        view.session.last_result = result
        view.object_tree.selected.return_value = entry.id
        view.object_tree.selected_feature.return_value = feature.id
        view.feature_panel.remember_answers.side_effect = (
            lambda _id, _feature, _features, _mesh, reply: answers.append(reply.actions)
        )
        MainWindow._answer_in_worker(view, feature.id, entry, result)
        worker = view._leash.start.call_args.args[0]
        worker.crashed.connect(failed.append)

    module, name = {
        "contact": (repair, "parts_that_cross"),
        "containment": (repair._Shells, "inside"),
        "remember": (prepare_ops, "_hole_has_separate_contents_read"),
    }[phase]
    original = getattr(module, name)
    calls = 0

    def stop_inside_the_proof(*args, **kwargs):
        nonlocal calls
        calls += 1
        received = args[0]._cancelled if phase == "containment" else kwargs.get("cancelled")
        assert received is not None, "Der Abbruchschalter ging auf dem UI-Aufrufweg verloren."
        assert received is worker.cancelled
        if phase == "contact":
            assert kwargs["max_pairs"] is None
            assert kwargs["require_complete"] is True
            assert kwargs["include_face_contacts"] is True
        if phase == "remember":
            answer = original(*args, **kwargs)
            if calls == 1:
                worker.cancelled.cancel()
            return answer
        if calls == 1:
            worker.cancelled.cancel()
        return original(*args, **kwargs)

    monkeypatch.setattr(module, name, stop_inside_the_proof)
    worker.work()
    assert calls == 1 and not answers and not failed
    if caller == "local":
        assert aborted == [7]
    worker.cancelled.reset()
    worker.work()
    assert calls == 2, "Ein abgebrochener Sicherheitsbeleg darf nicht im Merker stehen."
    assert len(answers) == 1 and not failed
    assert [row.op for row in answers[0] if row.op] == ["slot_hole"]
    worker.cancelled.cancel()
    worker.work()
    assert calls == 2 and len(answers) == 1 and not failed


@pytest.mark.parametrize("ending", ["replace", "close"])
def test_an_obsolete_feature_answers_worker_receives_the_cancel_request(ending):
    """Neuer Merkmalklick und Fensterende schalten den vorhandenen Arbeiter ab."""
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.core.perceive.features import detect
    from app.ui.main_window import MainWindow

    mesh = blind_cylinder()
    features = detect(mesh)
    feature_id = next(key for key, value in features.items() if value.kind == "hole")
    entry = SimpleNamespace(id="obj_1", mesh=mesh, features=features)
    view = Mock(_answers_worker=None, _inventory_view=None)
    view.findChildren.return_value = []
    view._leash.pending.return_value = ()
    MainWindow._answer_in_worker(view, feature_id, entry, None)
    worker = view._answers_worker

    if ending == "replace":
        MainWindow._answer_in_worker(view, feature_id, entry, None)
        view._retire.assert_called_once_with(worker)
    else:
        MainWindow.wait_for_workers(view, 0)
        assert view._answers_worker is None
    assert worker.cancelled.is_cancelled


def make_dialog(
    profile,
    monkeypatch,
    *,
    raw=None,
    hit=None,
    full_detection=False,
    radius=8,
    parameters=(),
    **kwargs,
):
    """Ein eigener kleiner Körper nimmt den gleichen Pfad wie das große Original."""
    from app.ui.local_recognition import LocalRecognitionDialog

    load_operations()
    evaluation = importlib.import_module("app.core.scene.evaluate")
    if not full_detection:
        monkeypatch.setattr(evaluation, "FEATURE_LIMIT_TRIANGLES", 1)
        monkeypatch.setattr(evaluation, "CONFIRMED_FEATURE_LIMIT_TRIANGLES", 1)
    project = new_project()
    project.document.parameters = {parameter.name: parameter for parameter in parameters}
    project.sources["src_1"] = (blind_cylinder().raw if raw is None else raw).export(
        file_type="stl"
    )
    project.document.sources["src_1"] = Source("src_1", "import", "sources/own.stl", "")
    History(project.document).apply(
        "Laden",
        [
            OperationDraft(
                "load", params={"source": "src_1", "unit": "mm", "coordinates": "legacy_raw"}
            )
        ],
    )
    cache, sources = ResultCache(), ProjectSources(project)
    before = evaluate(project.document, profile, cache=cache, sources=sources)
    assert before.complete
    entry = before.scene.objects["obj_1"]
    assert bool(entry.features) is full_detection
    seed, point, normal = bore_seed(entry.mesh) if hit is None else hit
    dialog = LocalRecognitionDialog(
        project.document,
        before.scene,
        "obj_1",
        profile,
        point=point,
        normal=normal,
        seed_face=seed,
        radius=radius,
        sources=sources,
        cache=cache,
        **kwargs,
    )
    return dialog, project, before


def test_local_list_excludes_the_complete_but_distant_outer_shell(qt_app, profile, monkeypatch):
    """Die komplette Szene behält ihre Merkmale; die lokale Liste zeigt nur den Suchraum."""
    dialog, project, before = make_dialog(profile, monkeypatch, full_detection=True)
    document = copy.deepcopy(project.document)
    try:
        wait_until(qt_app, dialog.save_button.isEnabled)
        inspection = dialog.inspection
        entry = inspection.evaluation.scene.objects["obj_1"]
        point = np.array([inspection.detect_draft.params[name] for name in ("x", "y", "z")])
        expected = {
            name
            for name, feature in before.scene.objects["obj_1"].features.items()
            if np.all(
                np.linalg.norm(
                    entry.mesh.raw.vertices[
                        entry.mesh.raw.faces[np.asarray(feature.face_indices, dtype=int)]
                    ]
                    - point,
                    axis=2,
                )
                < 8
            )
        }
        assert len(expected) == 2
        assert set(inspection.features) == expected
        assert entry.features.keys() == before.scene.objects["obj_1"].features.keys()
        assert inspection.selected in expected
        assert project.document == document
    finally:
        dispose(dialog, qt_app)


def test_local_radius_filter_resolves_the_saved_project_expression(qt_app, profile, monkeypatch):
    """Der Suchraum folgt dem ausgewerteten Projektmaß; gespeichert bleibt der Ausdruck."""
    dialog, _project, _before = make_dialog(
        profile,
        monkeypatch,
        full_detection=True,
        radius="=@search_radius",
        parameters=(Parameter("search_radius", 8),),
    )
    try:
        wait_until(qt_app, dialog.save_button.isEnabled)
        assert len(dialog.inspection.features) == 2
        assert dialog.inspection.detect_draft.params["radius"] == "=@search_radius"
    finally:
        dispose(dialog, qt_app)


def test_local_list_keeps_old_region_features_only_in_the_scene(qt_app, profile, monkeypatch):
    """Ein früherer lokaler Auftrag bleibt reproduzierbar, ohne die aktuelle Liste zu füllen."""
    from app.ui.local_recognition import LocalRecognitionDialog

    first = blind_cylinder().raw
    second = first.copy()
    second.apply_translation((250, 0, 0))
    dialog, project, _before = make_dialog(
        profile, monkeypatch, raw=trimesh.util.concatenate((first, second))
    )
    later = None
    try:
        wait_until(qt_app, dialog.save_button.isEnabled)
        inspection = dialog.inspection
        History(project.document).apply("Erste Stelle", (inspection.detect_draft,))
        old_features = inspection.evaluation.scene.objects["obj_1"].features
        _, point, normal = bore_seed(MeshData.of(first))
        place = np.asarray(point) + np.array((250, 0, 0))
        later = LocalRecognitionDialog(
            project.document,
            inspection.evaluation.scene,
            "obj_1",
            profile,
            point=tuple(place),
            normal=normal,
            radius=8,
            sources=ProjectSources(project),
            cache=dialog._cache,
            original_ray=(tuple(place + np.asarray(normal) * 0.5), tuple(-np.asarray(normal))),
        )
        wait_until(qt_app, later.save_button.isEnabled)
        entry = later.inspection.evaluation.scene.objects["obj_1"]
        assert old_features.keys() <= entry.features.keys()
        assert set(later.inspection.features).isdisjoint(old_features)
        assert len(later.inspection.features) == 2
        assert entry.features[later.inspection.selected].kind == "hole"
        assert all(entry.features[name] == feature for name, feature in old_features.items())
    finally:
        if later is not None:
            dispose(later, qt_app)
        dispose(dialog, qt_app)


def test_local_list_keeps_the_confirmed_bore_and_entrance(qt_app, profile, monkeypatch):
    """Eine vollständige Senkbohrung wird im Suchraum als gemeinsam bearbeitbare Kette angeboten."""
    from app.core.perceive.relations import cavity_chain_at
    from tests.helpers import sloping_bore

    mesh, _, hole = sloping_bore()
    face = hole.face_indices[0]
    point, normal = tuple(mesh.raw.triangles_center[face]), tuple(mesh.raw.face_normals[face])
    dialog, _project, before = make_dialog(
        profile,
        monkeypatch,
        raw=mesh.raw,
        hit=(-1, point, normal),
        radius=20,
        full_detection=True,
    )
    try:
        wait_until(qt_app, dialog.save_button.isEnabled)
        entry = dialog.inspection.evaluation.scene.objects["obj_1"]
        selected = next(
            feature
            for feature in entry.features.values()
            if feature.kind == "hole" and abs(feature.params["centre"][0]) < 1
        )
        chain = cavity_chain_at(selected, entry.features, entry.mesh)
        assert chain is not None
        assert {feature.kind for feature in chain} == {"hole", "cone"}
        assert {feature.id for feature in chain} <= set(dialog.inspection.features)
        resize = next(
            action
            for action in dialog.inspection.actions[selected.id]
            if action.op == "resize_hole"
        )
        assert (
            next(field.value for field in resize.fields if field.name == "entrance_mode")
            == "follow"
        )
        assert entry.features.keys() == before.scene.objects["obj_1"].features.keys()
    finally:
        dispose(dialog, qt_app)


def dispose(dialog, app):
    dialog.release()
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def choose_action(dialog, op):
    index = next(
        index
        for index in range(dialog.action_box.count())
        if dialog.action_box.itemData(index).op == op
    )
    dialog.action_box.setCurrentIndex(index)
    dialog.edit_button.click()


def test_search_and_actions_run_outside_qt_and_leave_the_source_unchanged(
    qt_app, profile, monkeypatch
):
    import app.ui.local_recognition as local

    threads = []
    original = local.actions_for

    def measured(*args, **kwargs):
        threads.append(threading.get_ident())
        return original(*args, **kwargs)

    monkeypatch.setattr(local, "actions_for", measured)
    dialog, project, before = make_dialog(profile, monkeypatch)
    document = copy.deepcopy(project.document)
    results, selected = [], []
    dialog.recognitionReady.connect(results.append)
    dialog.featureSelected.connect(selected.append)
    try:
        wait_until(qt_app, dialog.save_button.isEnabled)
        assert threads and all(value != threading.get_ident() for value in threads)
        assert project.document == document
        assert before.scene.objects["obj_1"].features == {}
        assert len(results) == 1 and results[0] is dialog.inspection
        chosen = dialog.features.currentItem().data(256)
        feature = dialog.inspection.evaluation.scene.objects["obj_1"].features[chosen]
        assert feature.kind == "hole"
        assert selected[-1] == chosen
        assert "Ausgewählt:" in dialog.selection.text()
        assert dialog.edit_button.isEnabled()
    finally:
        dispose(dialog, qt_app)


def test_edit_preview_and_acceptance_use_one_identical_transaction(qt_app, profile, monkeypatch):
    dialog, project, _before = make_dialog(profile, monkeypatch)
    previews, accepted = [], []
    dialog.previewRequested.connect(previews.append)
    dialog.draftsReady.connect(accepted.append)
    try:
        wait_until(qt_app, dialog.save_button.isEnabled)
        choose_action(dialog, "resize_hole")
        assert dialog.editor is not None
        wait_until(qt_app, lambda: bool(previews))
        assert [draft.op for draft in previews[-1]] == ["detect_region", "resize_hole"]
        assert previews[-1][1].params["at_feature"] == dialog.features.currentItem().data(256)
        dialog.editor._editors["diameter"].set_value(8)
        wait_until(qt_app, lambda: previews[-1][1].params["diameter"] == 8)
        revision = dialog.preview_revision
        dialog.preview_status("Korrigieren Sie das Maß.", revision=revision)
        dialog.editor.accept()
        assert not accepted and dialog.editor is not None
        assert "Korrigieren" in dialog.edit_notice.text()
        warning = Finding("own.warning", "warning", "Die Wand wird dünner.")
        dialog.preview_status(findings=(warning,), revision=revision)
        assert "Die Wand wird dünner" in dialog.edit_notice.text()
        dialog.editor.accept()
        assert accepted == [previews[-1]]
        History(project.document).apply("Hier erkennen und ändern", accepted[0])
        assert len(project.document.transactions[-1].ops) == 2
        history = History(project.document)
        assert history.undo() is not None
        assert len(project.document.ops) == 1
        assert dialog.result() == QDialog.DialogCode.Accepted
    finally:
        dispose(dialog, qt_app)


def test_new_radius_immediately_invalidates_selection_and_old_reply(qt_app, profile, monkeypatch):
    dialog, _project, _before = make_dialog(profile, monkeypatch)
    cleared = []
    dialog.previewCleared.connect(lambda: cleared.append(True))
    try:
        wait_until(qt_app, dialog.save_button.isEnabled)
        previous, revision = dialog.inspection, dialog._revision
        dialog.radius.set_value(0.5)
        assert dialog.inspection is None
        assert not dialog.save_button.isEnabled() and not dialog.edit_button.isEnabled()
        assert dialog.features.currentItem() is None
        dialog._ready(revision, previous)
        assert dialog.inspection is None and cleared
        wait_until(qt_app, lambda: dialog._worker is None and not dialog._pending)
        assert not dialog.save_button.isEnabled()
        assert "Suchradius" in dialog.state.text()
    finally:
        dispose(dialog, qt_app)


def test_old_preview_cannot_unlock_new_values(qt_app, profile, monkeypatch):
    dialog, _project, _before = make_dialog(profile, monkeypatch)
    try:
        wait_until(qt_app, dialog.save_button.isEnabled)
        choose_action(dialog, "resize_hole")
        old_revision = dialog.preview_revision
        dialog.editor._editors["diameter"].set_value(8)
        assert dialog.preview_revision > old_revision
        dialog.preview_status(revision=old_revision)
        assert dialog.editor._blocked_reason
        dialog.preview_status(revision=dialog.preview_revision)
        assert dialog.editor._blocked_reason is None
    finally:
        dispose(dialog, qt_app)


def test_detection_only_has_an_explicit_single_draft_button(qt_app, profile, monkeypatch):
    dialog, project, _before = make_dialog(profile, monkeypatch)
    accepted = []
    dialog.draftsReady.connect(accepted.append)
    try:
        wait_until(qt_app, dialog.save_button.isEnabled)
        assert "Merkmale übernehmen" in dialog.save_button.text()
        dialog.save_button.click()
        assert len(accepted) == 1 and len(accepted[0]) == 1
        assert accepted[0][0].op == "detect_region"
        assert len(project.document.ops) == 1
    finally:
        dispose(dialog, qt_app)


def test_invalidation_rejects_late_worker_and_edit_results(qt_app, profile, monkeypatch):
    dialog, project, _before = make_dialog(profile, monkeypatch)
    accepted, results = [], []
    dialog.draftsReady.connect(accepted.append)
    try:
        wait_until(qt_app, dialog.save_button.isEnabled)
        previous, revision = dialog.inspection, dialog._revision
        choose_action(dialog, "resize_hole")
        dialog.recognitionReady.connect(results.append)
        dialog.invalidate()
        dialog._ready(revision, previous)
        dialog.preview_status(revision=dialog.preview_revision)
        assert not accepted and not results and dialog.editor is None
        assert len(project.document.ops) == 1
    finally:
        dispose(dialog, qt_app)


def test_radius_queue_keeps_only_the_latest_request_and_cancels_the_running_one(
    qt_app, profile, monkeypatch
):
    import app.ui.local_recognition as local

    dialog, _project, _before = make_dialog(profile, monkeypatch)
    entered, unblock, calls = threading.Event(), threading.Event(), []
    original = local.evaluate

    def held(document, *args, **kwargs):
        calls.append(document.ops[-1].params["radius"])
        if len(calls) == 1:
            entered.set()
            while not unblock.wait(0.01):
                kwargs["cancelled"].raise_if_cancelled()
        return original(document, *args, **kwargs)

    monkeypatch.setattr(local, "evaluate", held)
    try:
        wait_until(qt_app, entered.is_set)
        dialog.radius.set_value(0.5)
        dialog.radius.set_value(8.5)
        wait_until(qt_app, dialog.save_button.isEnabled)
        assert calls == [8, 8.5]
        assert dialog.inspection.detect_draft.params["radius"] == 8.5
    finally:
        unblock.set()
        dispose(dialog, qt_app)


@pytest.mark.parametrize("accept", [True, False])
def test_real_surface_ambiguity_answers_or_cancels_without_a_waiting_worker(
    qt_app, profile, monkeypatch, accept
):
    first = trimesh.creation.box((5, 5, 5))
    second = first.copy()
    second.apply_translation((0.5, 0, 0))
    dialog, project, _before = make_dialog(
        profile,
        monkeypatch,
        raw=trimesh.util.concatenate((first, second)),
        hit=(-1, (0, 0, 2.5), (0, 0, 1)),
    )
    try:
        wait_until(qt_app, lambda: dialog._question is not None)
        assert dialog._question.list.count() == 2
        if accept:
            dialog._question.list.setCurrentRow(1)
            dialog._question.accept()
            wait_until(qt_app, dialog.save_button.isEnabled)
            assert dialog.inspection.detect_draft.params["seed_face"] >= 0
        else:
            dialog._question.reject()
            wait_until(qt_app, lambda: dialog._worker is None)
            assert not dialog.save_button.isEnabled()
            assert "abgebrochen" in dialog.state.text()
            assert not dialog.progress.isVisible()
        assert dialog._request is None and dialog._question is None
        assert len(project.document.ops) == 1
    finally:
        dispose(dialog, qt_app)


def test_closing_a_waiting_question_releases_the_worker(qt_app, profile, monkeypatch):
    first = trimesh.creation.box((5, 5, 5))
    second = first.copy()
    second.apply_translation((0.5, 0, 0))
    dialog, _project, _before = make_dialog(
        profile,
        monkeypatch,
        raw=trimesh.util.concatenate((first, second)),
        hit=(-1, (0, 0, 2.5), (0, 0, 1)),
    )
    try:
        wait_until(qt_app, lambda: dialog._question is not None)
        worker = dialog._worker
        dialog.invalidate()
        wait_until(qt_app, lambda: not worker.isRunning())
        assert dialog._request is None and dialog._question is None
    finally:
        dispose(dialog, qt_app)


def test_lod_ray_is_resolved_on_the_original_inside_the_worker(qt_app, profile, monkeypatch):
    import app.ui.local_recognition as local

    threads = []
    original = local.original_surface_hit

    def measured(*args, **kwargs):
        threads.append(threading.get_ident())
        return original(*args, **kwargs)

    monkeypatch.setattr(local, "original_surface_hit", measured)
    dialog, _project, before = make_dialog(
        profile,
        monkeypatch,
        hit=(0, (123, 234, 345), (0, 0, 1)),
        original_ray=((0, 0, 17.5), (1, 0, 0)),
    )
    try:
        wait_until(qt_app, dialog.save_button.isEnabled)
        draft = dialog.inspection.detect_draft
        assert len(threads) == 1 and threads[0] != threading.get_ident()
        assert draft.params["x"] == pytest.approx(3)
        assert draft.params["z"] == pytest.approx(17.5)
        seed = draft.params["seed_face"]
        assert seed != 0
        expected = before.scene.objects["obj_1"].mesh.raw.face_normals[seed]
        assert np.allclose([draft.params[key] for key in ("nx", "ny", "nz")], expected)
        dialog.radius.set_value(8.5)
        wait_until(qt_app, dialog.save_button.isEnabled)
        assert len(threads) == 1
    finally:
        dispose(dialog, qt_app)


def test_ray_with_no_original_hit_never_uses_the_lod_placeholder(qt_app, profile, monkeypatch):
    dialog, _project, _before = make_dialog(
        profile, monkeypatch, original_ray=((200, 0, 17.5), (1, 0, 0))
    )
    try:
        wait_until(qt_app, lambda: dialog._worker is None and not dialog._pending)
        assert dialog.inspection is None
        assert not dialog.save_button.isEnabled()
        assert "Stelle" in dialog.state.text()
        requested = []
        dialog.pickRequested.connect(lambda: requested.append(True))
        button = next(
            button for button in dialog.state._buttons if button.text() == "Andere Stelle wählen"
        )
        button.click()
        assert requested == [True]
    finally:
        dispose(dialog, qt_app)


def test_original_ray_respects_the_current_section_planes(qt_app, profile, monkeypatch):
    from app.core.geom.section import SectionPlane

    dialog, _project, _before = make_dialog(
        profile,
        monkeypatch,
        original_ray=((0, 0, 17.5), (1, 0, 0)),
        clip_planes=(SectionPlane.along("z", 15),),
    )
    try:
        wait_until(qt_app, lambda: dialog._worker is None and not dialog._pending)
        assert dialog.inspection is None and not dialog.save_button.isEnabled()
    finally:
        dispose(dialog, qt_app)


def test_unexpected_worker_error_leaves_a_visible_recovery_state(qt_app, profile, monkeypatch):
    import app.ui.local_recognition as local

    dialog, _project, _before = make_dialog(profile, monkeypatch)

    def crash(*_args, **_kwargs):
        raise RuntimeError("own worker probe")

    monkeypatch.setattr(local, "actions_for", crash)
    try:
        wait_until(qt_app, lambda: dialog._worker is None and not dialog._pending)
        assert dialog.inspection is None and not dialog.save_button.isEnabled()
        assert dialog.state.text()
        assert not dialog.progress.isVisible()
    finally:
        dispose(dialog, qt_app)


def test_the_count_line_speaks_in_the_number_it_shows() -> None:
    """Keine „1 vollständige Merkmale", und bei keinem der Weg weiter.

    Die Zeile unter dem Radius sagte „1 vollständige Merkmale gefunden." und
    „0 vollständige Merkmale gefunden." — beim zweiten stand *Nur Merkmale
    übernehmen* grau daneben, und was jetzt hilft, stand nirgends.
    """
    from app.ui.local_recognition import _found_text

    assert _found_text(1) == "1 Merkmal gefunden."
    assert "Suchradius" in _found_text(0) and "0" not in _found_text(0)
    assert _found_text(3) == "3 Merkmale gefunden."


@pytest.mark.parametrize("code", ["perceive.too_large"])
@pytest.mark.parametrize(
    ("target", "kind", "expected"),
    [
        ("obj_1", "mesh", True),
        ("obj_1", "brep", False),
        ("obj_1", None, False),
        (None, "mesh", False),
    ],
)
def test_local_report_offer_requires_its_own_living_mesh(code, target, kind, expected):
    """Nur das tatsächlich vorhandene Netz des Befunds erhält den lokalen Einstieg."""
    from types import SimpleNamespace

    from app.core.errors import RECOGNIZE_LOCAL
    from app.ui.panels import actions_for_document

    finding = Finding(code, "info", "Großes Modell", object_id=target)
    objects = {"obj_1": SimpleNamespace(kind=kind)} if kind is not None else {}

    offered = actions_for_document(finding, None, live_objects=objects)

    assert (RECOGNIZE_LOCAL.id in {action.id for action in offered}) is expected


def test_the_mesh_warning_offers_no_local_recognition() -> None:
    """``ingest.very_large`` spricht nur über die Karten (24.09.2026).

    Bis 1,5 Millionen Dreiecke ist längst alles erkannt, und darüber trägt
    ``perceive.too_large`` am Körper die Wege der Erkennung — ein zweiter
    Knopf am Kartensatz bot etwas an, das sein Satz nicht erklärte.
    """
    from types import SimpleNamespace

    from app.core.errors import DECIMATE_MESH
    from app.ui.panels import actions_for_document

    finding = Finding("ingest.very_large", "warning", "Karten", object_id="obj_1")
    offered = actions_for_document(
        finding, None, live_objects={"obj_1": SimpleNamespace(kind="mesh")}
    )
    assert [action.id for action in offered] == [DECIMATE_MESH.id]


def _answered(object_id: str = "obj_1", allowed: bool = False) -> dict:
    """Die gespeicherte Erkennungswahl eines Ladeschritts, wie sie in der Datei steht."""
    from app.core.perceive.match_records import recognition_answer_key

    return {
        recognition_answer_key(object_id): {
            "object_id": object_id,
            "scope": "a" * 32,
            "allowed": allowed,
        }
    }


@pytest.mark.parametrize(
    ("op", "triangles", "answered", "alive", "expected"),
    [
        ("load", 2_330_374, True, True, True),
        ("load", 5_000_000, True, True, True),
        ("load", 5_000_001, True, True, False),
        ("repair", 2_330_374, True, True, False),
        # Unter der Grenze geladen, danach gewachsen: keine Wahl, kein Knopf (N3).
        ("load", 2_330_374, False, True, False),
        # Ein verbrauchter Körper behält ihn, wie der Satz ihn behält (B19).
        ("load", 2_330_374, True, False, True),
    ],
)
def test_the_full_recognition_is_offered_only_where_the_import_asks(
    op, triangles, answered, alive, expected
):
    """*Alle Merkmale erkennen* steht nur, wo am Ladeschritt eine Wahl steht (Review N3).

    Höchstens fünf Millionen Dreiecke und ein Ladeschritt, der eine
    Erkennungswahl für den Körper trägt; ohne sie gibt es nichts
    zurückzunehmen, und der Knopf rechnete neu, ohne dass eine Frage kam.
    Folgeschritte prüft
    ``test_the_way_back_stays_at_a_follow_up_step_of_the_loaded_body``.
    """
    from types import SimpleNamespace

    from app.core.errors import RECOGNIZE_FULLY
    from app.core.types import Document, Operation
    from app.ui.panels import actions_for_document

    document = Document(format_version=34, app_version="test")
    document.ops.append(
        Operation(id=1, op=op, outputs=("obj_1",), matches=_answered() if answered else {})
    )
    finding = Finding(
        "perceive.too_large",
        "info",
        "Großes Modell",
        object_id="obj_1",
        op_id=1,
        values={"triangles": triangles, "limit": 1_500_000},
    )
    objects = {"obj_1": SimpleNamespace(kind="mesh")} if alive else {}

    offered = actions_for_document(finding, document, live_objects=objects)

    assert (RECOGNIZE_FULLY.id in {action.id for action in offered}) is expected


@pytest.mark.parametrize("inputs", [("obj_1",), ("obj_1", "obj_2"), ()])
def test_local_report_offer_binds_only_an_unambiguous_step_input(inputs):
    """Ohne Körperkennung ist nur der eine Eingang des belegten Schritts eindeutig."""
    from types import SimpleNamespace

    from app.core.errors import RECOGNIZE_LOCAL
    from app.core.types import Document, Operation
    from app.ui.panels import actions_for_document, as_error

    document = Document(format_version=34, app_version="test")
    document.ops.append(Operation(id=7, op="repair", inputs=inputs, outputs=("obj_1",)))
    finding = Finding("perceive.too_large", "info", "Großes Modell", op_id=7)
    objects = {identifier: SimpleNamespace(kind="mesh") for identifier in inputs}

    offered = actions_for_document(finding, document, live_objects=objects)

    assert (RECOGNIZE_LOCAL.id in {action.id for action in offered}) is (len(inputs) == 1)
    assert as_error(finding, document).object_id == ("obj_1" if len(inputs) == 1 else None)


@pytest.mark.parametrize(
    ("target", "group", "expected"),
    [
        ("obj_1", (), ("obj_1",)),
        ("obj_1", ("obj_2", "obj_1"), ("obj_2", "obj_1")),
        (None, ("obj_2", "obj_1"), ("obj_2", "obj_1")),
        (None, (), None),
    ],
)
def test_local_report_entry_keeps_bound_targets_instead_of_tree_selection(target, group, expected):
    """Ein Sammelbefund behält alle Ziele; ein unbelegter Befund erfindet keines."""
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.core.errors import AppError
    from app.ui.local_recognition_flow import LocalRecognitionFlow

    tree = Mock()
    flow = SimpleNamespace(arm=Mock(), view=SimpleNamespace(object_tree=tree))
    error = AppError(object_id=target, values={"local_objects": group})

    LocalRecognitionFlow.from_report(flow, error)

    if expected is None:
        flow.arm.assert_not_called()
    else:
        flow.arm.assert_called_once_with(object_ids=expected)
    assert not tree.mock_calls


def _local_report_flow_stub(*, allowed=True, busy=False, objects=None):
    """Nur die Anschlussgrenze ersetzen; Zustandswechsel laufen durch den echten Fluss."""
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.ui.local_recognition_flow import LocalRecognitionFlow

    view = SimpleNamespace(
        _quiet_command_allowed=lambda: allowed,
        _quiet_host=None,
        _op_dialog=None,
        end_quiet_placement=Mock(),
        object_tree=Mock(),
        viewport=Mock(),
        announce=Mock(),
        session=SimpleNamespace(
            busy=busy,
            last_result=SimpleNamespace(scene=SimpleNamespace(objects=objects or {})),
        ),
    )
    flow = SimpleNamespace(
        view=view, dialog=None, armed=False, _targets=(), pointer=object(), _pick_surface=object()
    )
    flow.invalidate = lambda: LocalRecognitionFlow.invalidate(flow)
    flow.arm = lambda **kwargs: LocalRecognitionFlow.arm(flow, **kwargs)
    flow._refusal = lambda entry: LocalRecognitionFlow._refusal(flow, entry)
    return flow


def test_local_report_arm_and_reselection_keep_the_whole_bound_group():
    """Markierung und erneute Stellenauswahl behalten die einmal gebundene Gruppe."""
    from types import SimpleNamespace

    from app.ui.local_recognition_flow import LocalRecognitionFlow

    targets = ("obj_2", "obj_1")
    flow = _local_report_flow_stub(
        objects={identifier: SimpleNamespace(kind="mesh") for identifier in targets}
    )

    flow.arm(object_ids=("obj_2", "obj_1", "obj_2"))

    assert flow.armed and flow._targets == targets
    flow.view.object_tree.select_objects.assert_called_once_with(targets)
    flow.view.viewport.set_placement_pointer.assert_called_once_with(flow.pointer)
    flow.view.viewport.set_surface_picker.assert_called_once_with(flow._pick_surface)
    flow.view.object_tree.reset_mock()

    LocalRecognitionFlow._pick_again(flow)

    assert flow.armed and flow._targets == targets
    flow.view.object_tree.select_objects.assert_called_once_with(targets)


@pytest.mark.parametrize("reason", ["pending", "busy", "missing", "brep", "no_result"])
def test_local_report_arm_rejects_unusable_targets_before_replacing_an_active_flow(reason):
    """Ein abgelehnter Berichtseinstieg zerstört weder Entwurf noch aktuelle Stellenauswahl."""
    from types import SimpleNamespace
    from unittest.mock import Mock

    objects = {"obj_1": SimpleNamespace(kind="brep" if reason == "brep" else "mesh")}
    flow = _local_report_flow_stub(
        allowed=reason != "pending", busy=reason == "busy", objects=objects
    )
    if reason == "no_result":
        flow.view.session.last_result = None
    flow.armed = True
    flow._targets = ("previous",)
    flow.dialog = Mock()
    flow.view._quiet_host = object()
    flow.view._op_dialog = Mock()

    flow.arm(object_ids=("missing" if reason == "missing" else "obj_1",))

    assert flow.armed and flow._targets == ("previous",)
    flow.dialog.invalidate.assert_not_called()
    flow.view.end_quiet_placement.assert_not_called()
    flow.view._op_dialog.reject.assert_not_called()
    assert not flow.view.object_tree.mock_calls
    assert not flow.view.viewport.mock_calls
    # Und abgelehnt wird mit Grund, nie stumm (E5) — außer die begonnene
    # Änderung hält den Einstieg, dann sagt ``_quiet_command_allowed`` es.
    said = {
        "pending": None,
        "busy": "wird noch gerechnet",
        "no_result": "wird noch gerechnet",
        "brep": "Flächenbearbeitung beenden",
        "missing": "Zielen Sie auf das Modell",
    }[reason]
    if said is None:
        flow.view.announce.assert_not_called()
    else:
        (sentence,), _ = flow.view.announce.call_args
        assert said in sentence


def test_local_report_begin_rejects_a_mesh_outside_its_bound_group():
    """Ein gültiger Originaltreffer am falschen Netz übernimmt nicht dessen Stelle."""
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.ui.local_recognition_flow import LocalRecognitionFlow

    flow = _local_report_flow_stub(objects={"other": SimpleNamespace(kind="mesh")})
    flow.armed = True
    flow._targets = ("obj_1", "obj_2")
    flow.dialog = Mock()
    flow.view._quiet_host = object()
    hit = ("other", (1.0, 2.0, 3.0), 7, ((1.0, 2.0, 10.0), (0.0, 0.0, -1.0)))

    LocalRecognitionFlow.begin(flow, hit)

    assert flow.armed and flow._targets == ("obj_1", "obj_2")
    flow.dialog.invalidate.assert_not_called()
    flow.view.end_quiet_placement.assert_not_called()
    flow.view.announce.assert_called_once()
    assert not flow.view.viewport.mock_calls
    assert not flow.view.object_tree.mock_calls


@pytest.mark.parametrize("bodies", [(), ("obj_2", "obj_1", "obj_3")])
def test_local_report_action_passes_the_complete_group_through_the_window_once(monkeypatch, bodies):
    """Bericht, Fensterhandler und Fluss transportieren eine Gruppe genau einmal."""
    from types import SimpleNamespace
    from unittest.mock import Mock

    from PySide6.QtCore import Qt

    from app.core.errors import RECOGNIZE_LOCAL
    from app.ui import panels
    from app.ui.local_recognition_flow import LocalRecognitionFlow
    from app.ui.main_window import MainWindow

    finding = Finding(
        "perceive.too_large", "info", "Großes Modell", object_id="obj_1", values={"triangles": 42}
    )
    item = SimpleNamespace(
        data=lambda role: {
            Qt.ItemDataRole.UserRole: finding,
            panels._BODIES_ROLE: bodies,
        }.get(role)
    )
    panel = SimpleNamespace(
        _document=None,
        _live_objects={
            identifier: SimpleNamespace(kind="mesh") for identifier in bodies or ("obj_1",)
        },
    )
    flow = SimpleNamespace(arm=Mock())
    flow.from_report = lambda error: LocalRecognitionFlow.from_report(flow, error)
    view = Mock()
    view.local_features.return_value = flow
    handlers = MainWindow.error_handlers(view)
    monkeypatch.setattr(panels, "handlers_of", lambda _panel: handlers)
    ask = Mock(side_effect=AssertionError("The surface pick chooses the group member"))
    monkeypatch.setattr(panels.BodyChoiceDialog, "ask", ask)

    panels.ReportPanel._run_action_for(panel, item, RECOGNIZE_LOCAL.id)

    flow.arm.assert_called_once_with(object_ids=bodies or ("obj_1",))
    view.local_features.assert_called_once_with()
    assert not view.object_tree.mock_calls
    ask.assert_not_called()
    assert finding.values == {"triangles": 42}


@pytest.mark.parametrize("representative", ["removed", "exact", "mesh"])
def test_local_report_group_keeps_surviving_meshes_when_its_first_body_is_gone(
    monkeypatch, representative
):
    """Ein historisches Gruppenmitglied sperrt keine vorhandene Oberfläche des Befunds."""
    from types import SimpleNamespace
    from unittest.mock import Mock

    from PySide6.QtCore import Qt

    from app.core.errors import RECOGNIZE_LOCAL
    from app.ui import panels

    finding = Finding("perceive.too_large", "info", "Große Modelle", object_id=representative)
    objects = {"mesh": SimpleNamespace(kind="mesh"), "exact": SimpleNamespace(kind="brep")}
    bodies = ("removed", "exact", "mesh", "mesh")
    offered = panels.actions_for_document(finding, None, live_objects=objects, bodies=bodies)
    assert RECOGNIZE_LOCAL.id in {action.id for action in offered}

    item = SimpleNamespace(
        data=lambda role: {Qt.ItemDataRole.UserRole: finding, panels._BODIES_ROLE: bodies}.get(role)
    )
    panel = SimpleNamespace(_document=None, _live_objects=objects)
    handler = Mock()
    monkeypatch.setattr(panels, "handlers_of", lambda _panel: {RECOGNIZE_LOCAL.id: handler})

    panels.ReportPanel._run_action_for(panel, item, RECOGNIZE_LOCAL.id)

    handler.assert_called_once()
    assert handler.call_args.args[0].values["local_objects"] == ("mesh",)


def test_local_report_empty_group_never_invokes_the_handler(monkeypatch):
    """Ein veralteter Klick wählt bei fehlendem Netz keinen anderen Szenenkörper."""
    from types import SimpleNamespace
    from unittest.mock import Mock

    from PySide6.QtCore import Qt

    from app.core.errors import RECOGNIZE_LOCAL
    from app.ui import panels

    finding = Finding("perceive.too_large", "info", "Große Modelle", object_id="removed")
    objects = {"other": SimpleNamespace(kind="mesh"), "exact": SimpleNamespace(kind="brep")}
    bodies = ("removed", "exact")
    offered = panels.actions_for_document(finding, None, live_objects=objects, bodies=bodies)
    assert RECOGNIZE_LOCAL.id not in {action.id for action in offered}
    item = SimpleNamespace(
        data=lambda role: {Qt.ItemDataRole.UserRole: finding, panels._BODIES_ROLE: bodies}.get(role)
    )
    panel = SimpleNamespace(_document=None, _live_objects=objects)
    handler = Mock()
    monkeypatch.setattr(panels, "handlers_of", lambda _panel: {RECOGNIZE_LOCAL.id: handler})

    panels.ReportPanel._run_action_for(panel, item, RECOGNIZE_LOCAL.id)

    handler.assert_not_called()


@pytest.mark.parametrize("entry", ["_show_offers", "_on_menu", "_preselect"])
def test_local_report_action_availability_receives_the_group_at_every_entry(monkeypatch, entry):
    """Knopf, Kontextmenü und Vorauswahl prüfen dieselben Körper der Sammelzeile."""
    from types import SimpleNamespace
    from unittest.mock import Mock

    from PySide6.QtCore import Qt

    from app.ui import panels

    finding = Finding("perceive.too_large", "info", "Große Modelle", object_id="removed")
    bodies = ("removed", "mesh")
    objects = {"mesh": SimpleNamespace(kind="mesh")}
    item = SimpleNamespace(
        data=lambda role: {Qt.ItemDataRole.UserRole: finding, panels._BODIES_ROLE: bodies}.get(
            role
        ),
        isHidden=lambda: False,
    )
    panel = SimpleNamespace(
        _document=None,
        _stopped_at=None,
        _live_objects=objects,
        _offer_row=SimpleNamespace(count=lambda: 0),
        _offers=Mock(),
        _show_finding_context=lambda _item: None,
        _set_slicer_primary=lambda _primary: None,
        list=SimpleNamespace(
            selectedItems=lambda: [] if entry == "_preselect" else [item],
            itemAt=lambda _position: item,
            count=lambda: 1,
            item=lambda _row: item,
        ),
    )
    offered = Mock(return_value=())
    monkeypatch.setattr(panels, "actions_for_document", offered)
    monkeypatch.setattr(panels, "handlers_of", lambda _panel: {})

    getattr(panels.ReportPanel, entry)(panel, *((None,) if entry == "_on_menu" else ()))

    offered.assert_called_once_with(
        finding, None, stopped_at=None, live_objects=objects, bodies=bodies
    )


@pytest.mark.parametrize(
    ("busy", "kind", "expected"),
    [
        (True, "mesh", "wird noch gerechnet"),
        (False, "brep", "Flächenbearbeitung beenden"),
        (False, None, "Zielen Sie auf das Modell"),
    ],
)
def test_the_local_pick_says_why_it_cannot_start(busy, kind, expected):
    """Drei Gründe, drei Sätze — und keiner schweigt (E5, 24.09.2026).

    Bis dahin kehrte der Einstieg aus dem Bericht während einer Rechnung
    stumm zurück, und eine laufende Rechnung bekam denselben Satz wie ein
    exakter Körper, mit dem Wort „Dreiecksnetz" darin.
    """
    from types import SimpleNamespace

    from app.ui.local_recognition_flow import LocalRecognitionFlow

    flow = SimpleNamespace(
        view=SimpleNamespace(session=SimpleNamespace(busy=busy, last_result=object()))
    )
    entry = SimpleNamespace(kind=kind) if kind is not None else None

    sentence = LocalRecognitionFlow._refusal(flow, entry)

    assert expected in sentence
    assert "Dreiecksnetz" not in sentence


def test_a_radius_that_swings_between_both_limits_says_so_once():
    """Kein Pendel zwischen „vergrößern“ und „verkleinern“ (B5, Review B13).

    An einer Freiform des Drachen meldete ein kleiner Suchradius den Suchrand
    und der nächstgrößere das Budget; die zwei Hauptknöpfe schickten einander
    zurück. Liegen beide Gründe höchstens einen Schritt auseinander, stehen die
    zwei Wege, die dort noch helfen. Weiter auseinander gibt es dazwischen noch
    Radien, und die Aussage „kein Radius hilft“ wäre geraten.
    """
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.core.errors import ValidationError
    from app.ui.local_recognition import LocalRecognitionDialog

    errors = []
    dialog = Mock(
        _closed=False,
        _revision=4,
        _limits={},
        state=SimpleNamespace(
            set_error=lambda problem, handlers: errors.append((problem, handlers))
        ),
    )
    for radius, constraint in ((5.0, "local_boundary"), (20.0, "local_budget")):
        dialog._searched_radius = radius
        LocalRecognitionDialog._failed(dialog, 4, ValidationError(constraint=constraint))
    dialog._searched_radius = 7.5
    LocalRecognitionDialog._failed(dialog, 4, ValidationError(constraint="local_budget"))

    first, apart, (swung, handlers) = errors[0][0], errors[1][0], errors[2]
    assert [action.id for action in first.suggestions] == ["enlarge_radius", "pick_elsewhere"]
    assert [action.id for action in apart.suggestions] == ["shrink_radius", "decimate_mesh"]
    assert [action.id for action in swung.suggestions] == ["pick_elsewhere", "decimate_mesh"]
    assert "zu fein" in str(swung.title)
    assert {"pick_elsewhere", "decimate_mesh"} <= set(handlers)


def test_the_way_back_stays_at_a_follow_up_step_of_the_loaded_body():
    """*Alle Merkmale erkennen* hängt am Körper, nicht am Schritt des Befunds (Review B1)."""
    from types import SimpleNamespace

    from app.core.errors import RECOGNIZE_FULLY
    from app.core.types import Document, Operation
    from app.ui.panels import actions_for_document

    document = Document(format_version=34, app_version="test")
    document.ops.append(Operation(id=1, op="load", outputs=("obj_1",), matches=_answered()))
    document.ops.append(
        Operation(id=2, op="translate_object", inputs=("obj_1",), outputs=("obj_1",))
    )
    finding = Finding(
        "perceive.too_large",
        "info",
        "Großes Modell",
        object_id="obj_1",
        op_id=2,
        values={"triangles": 2_330_374, "limit": 1_500_000},
    )
    objects = {"obj_1": SimpleNamespace(kind="mesh")}

    offered = actions_for_document(finding, document, live_objects=objects)

    assert RECOGNIZE_FULLY.id in {action.id for action in offered}


def test_after_running_out_of_memory_the_full_recognition_is_not_the_first_way():
    """Am Speicherfehler steht vorn, was der Satz nennt (Review B19)."""
    from types import SimpleNamespace

    from app.core.errors import RECOGNIZE_FULLY
    from app.core.types import Document, Operation
    from app.ui.panels import actions_for_document

    document = Document(format_version=34, app_version="test")
    document.ops.append(Operation(id=1, op="load", outputs=("obj_1",), matches=_answered()))
    finding = Finding(
        "perceive.too_large",
        "warning",
        "Speicher",
        object_id="obj_1",
        op_id=1,
        values={"triangles": 1_200_000, "limit": 1_500_000},
    )
    objects = {"obj_1": SimpleNamespace(kind="mesh")}

    offered = actions_for_document(finding, document, live_objects=objects)

    assert offered[-1].id == RECOGNIZE_FULLY.id
    assert not offered[-1].primary
    assert offered[0].id != RECOGNIZE_FULLY.id


def test_a_consumed_body_offers_no_decimation():
    """*Dreiecke verringern* gilt der Auswahl — am verbrauchten Körper träfe es
    einen anderen (Review R7)."""
    from types import SimpleNamespace

    from app.core.errors import DECIMATE_MESH, RECOGNIZE_FULLY
    from app.core.types import Document, Operation
    from app.ui.panels import actions_for_document

    document = Document(format_version=34, app_version="test")
    document.ops.append(Operation(id=1, op="load", outputs=("obj_2",), matches=_answered("obj_2")))
    finding = Finding(
        "perceive.too_large",
        "info",
        "Großes Modell",
        object_id="obj_2",
        op_id=1,
        values={"triangles": 2_330_374, "limit": 1_500_000},
    )
    living = {"obj_2": SimpleNamespace(kind="mesh")}

    alive = {action.id for action in actions_for_document(finding, document, live_objects=living)}
    gone = {
        action.id
        for action in actions_for_document(
            finding, document, live_objects={"obj_3": SimpleNamespace(kind="mesh")}
        )
    }

    assert DECIMATE_MESH.id in alive
    assert DECIMATE_MESH.id not in gone
    assert RECOGNIZE_FULLY.id in gone, "die Wahl steht weiter am Ladeschritt"


def test_a_collected_row_takes_back_the_choice_of_all_its_bodies(monkeypatch):
    """Eine Sammelzeile nimmt die Wahl aller ihrer Körper zurück (Review B9)."""
    from types import SimpleNamespace
    from unittest.mock import Mock

    from PySide6.QtCore import Qt

    from app.core.errors import RECOGNIZE_FULLY
    from app.ui import panels

    finding = Finding("perceive.too_large", "info", "Große Modelle", object_id="a")
    bodies = ("a", "b")
    item = SimpleNamespace(
        data=lambda role: {Qt.ItemDataRole.UserRole: finding, panels._BODIES_ROLE: bodies}.get(role)
    )
    panel = SimpleNamespace(_document=None, _live_objects={})
    handler = Mock()
    monkeypatch.setattr(panels, "handlers_of", lambda _panel: {RECOGNIZE_FULLY.id: handler})

    panels.ReportPanel._run_action_for(panel, item, RECOGNIZE_FULLY.id)

    handler.assert_called_once()
    assert handler.call_args.args[0].values["recognition_objects"] == ("a", "b")


def test_the_face_at_the_seed_is_listed_beyond_the_radius():
    """Die ebene Fläche am Treffer steht in der Liste, andere Merkmale nur im Suchraum
    (Review B4)."""
    from app.core.types import Feature
    from app.ui.local_recognition import _with_the_face_at_the_seed

    features = {
        "face_1": Feature("face_1", "face", "detected", {}, face_indices=(3, 4)),
        "hole_1": Feature("hole_1", "hole", "detected", {}, face_indices=(3, 9)),
        "face_2": Feature("face_2", "face", "detected", {}, face_indices=(7,)),
    }

    assert _with_the_face_at_the_seed(features, ("face_2",), 3) == ("face_1", "face_2")
    assert _with_the_face_at_the_seed(features, ("face_2",), -1) == ("face_2",)


def test_the_recognition_answer_is_kept_at_once_and_can_be_taken_back():
    """Die Sitzung hält die Antwort sofort fest; nach einem Abbruch lädt sie ohne
    Vollerkennung (Review B18)."""
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.core.perceive.match_records import recognition_answer_key
    from app.core.types import Document, Operation
    from app.ui.session import Session

    document = Document(format_version=34, app_version="test")
    document.ops.append(Operation(id=1, op="load", outputs=("obj_1",)))
    key = recognition_answer_key("obj_1")
    record = {"object_id": "obj_1", "scope": "a" * 32, "allowed": True}
    session = SimpleNamespace(
        history=History(document),
        project=SimpleNamespace(document=document),
        projectChanged=Mock(),
        _project_generation=3,
        _recognition_answers=[],
        _dirty=False,
        _changed=Mock(),
    )

    Session._record_recognition_answer(session, 2, 1, key, record)
    assert key not in document.ops[0].matches, "ein anderes Dokument"
    Session._record_recognition_answer(session, 3, 7, key, record)
    assert not session._recognition_answers, "ein Ladeschritt, den es nicht mehr gibt"
    Session._record_recognition_answer(session, 3, 1, key, record)
    assert document.ops[0].matches[key]["allowed"] is True
    # Der Stern im Titel kommt mit der Antwort (Review N4).
    session.projectChanged.emit.assert_called_once()
    assert Session.recognition_interrupted(session)

    assert Session.load_without_recognition(session)
    assert document.ops[0].matches[key]["allowed"] is False
    session._changed.assert_called_once()
    assert not Session.recognition_interrupted(session)

    # Folgt der Zustimmung die Absage aus einem Speicherfehler, ersetzt sie
    # die Zustimmung: Kein Knopf bietet danach an, sie zurückzunehmen, und
    # der Grund bleibt stehen (Review R3).
    Session._record_recognition_answer(session, 3, 1, key, record)
    declined = {**record, "allowed": False, "out_of_memory": True}
    Session._record_recognition_answer(session, 3, 1, key, declined)
    assert not Session.recognition_interrupted(session)
    assert not Session.load_without_recognition(session)
    assert document.ops[0].matches[key]["out_of_memory"] is True


def test_a_cancelled_recognition_offers_to_load_without_it():
    """Nach dem Abbruch der langen Erkennung steht ein Weg zum Modell da (Review B18)."""
    from types import SimpleNamespace
    from unittest.mock import Mock

    from app.i18n import tr
    from app.ui.main_window import MainWindow

    for interrupted in (True, False):
        window = SimpleNamespace(
            announce=Mock(),
            session=SimpleNamespace(
                recognition_interrupted=lambda value=interrupted: value, picture=None
            ),
            skip_recognition=Mock(),
        )
        MainWindow._on_evaluation_cancelled(window)
        if interrupted:
            window.skip_recognition.setVisible.assert_called_once_with(True)
        else:
            window.skip_recognition.setVisible.assert_not_called()

    # Mit dem Bild vor der Erkennung (KUNDE-14) steht das Modell schon da; der
    # Satz sagt das und nicht „der letzte vollständig gerechnete Stand“.
    window = SimpleNamespace(
        announce=Mock(),
        session=SimpleNamespace(recognition_interrupted=lambda: False, picture=object()),
        skip_recognition=Mock(),
    )
    MainWindow._on_evaluation_cancelled(window)
    window.announce.assert_called_once_with(
        tr(
            "Abgebrochen. Das Modell steht da, seine Merkmale sind nicht erkannt — "
            "die nächste Änderung erkennt sie."
        )
    )
