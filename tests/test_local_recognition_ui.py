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
from tests.test_local_detection import blind_cylinder, bore_seed
from tests.test_outline_dialog import _until


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
        _until(qt_app, dialog.save_button.isEnabled)
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
        _until(qt_app, dialog.save_button.isEnabled)
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
        _until(qt_app, dialog.save_button.isEnabled)
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
        _until(qt_app, later.save_button.isEnabled)
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
    from tests.test_bore_mouth_resize import _sloping_bore

    mesh, _, hole = _sloping_bore()
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
        _until(qt_app, dialog.save_button.isEnabled)
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
        _until(qt_app, dialog.save_button.isEnabled)
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
        _until(qt_app, dialog.save_button.isEnabled)
        choose_action(dialog, "resize_hole")
        assert dialog.editor is not None
        _until(qt_app, lambda: bool(previews))
        assert [draft.op for draft in previews[-1]] == ["detect_region", "resize_hole"]
        assert previews[-1][1].params["at_feature"] == dialog.features.currentItem().data(256)
        dialog.editor._editors["diameter"].set_value(8)
        _until(qt_app, lambda: previews[-1][1].params["diameter"] == 8)
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
        _until(qt_app, dialog.save_button.isEnabled)
        previous, revision = dialog.inspection, dialog._revision
        dialog.radius.set_value(0.5)
        assert dialog.inspection is None
        assert not dialog.save_button.isEnabled() and not dialog.edit_button.isEnabled()
        assert dialog.features.currentItem() is None
        dialog._ready(revision, previous)
        assert dialog.inspection is None and cleared
        _until(qt_app, lambda: dialog._worker is None and not dialog._pending)
        assert not dialog.save_button.isEnabled()
        assert "Suchradius" in dialog.state.text()
    finally:
        dispose(dialog, qt_app)


def test_old_preview_cannot_unlock_new_values(qt_app, profile, monkeypatch):
    dialog, _project, _before = make_dialog(profile, monkeypatch)
    try:
        _until(qt_app, dialog.save_button.isEnabled)
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
        _until(qt_app, dialog.save_button.isEnabled)
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
        _until(qt_app, dialog.save_button.isEnabled)
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
        _until(qt_app, entered.is_set)
        dialog.radius.set_value(0.5)
        dialog.radius.set_value(8.5)
        _until(qt_app, dialog.save_button.isEnabled)
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
        _until(qt_app, lambda: dialog._question is not None)
        assert dialog._question.list.count() == 2
        if accept:
            dialog._question.list.setCurrentRow(1)
            dialog._question.accept()
            _until(qt_app, dialog.save_button.isEnabled)
            assert dialog.inspection.detect_draft.params["seed_face"] >= 0
        else:
            dialog._question.reject()
            _until(qt_app, lambda: dialog._worker is None)
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
        _until(qt_app, lambda: dialog._question is not None)
        worker = dialog._worker
        dialog.invalidate()
        _until(qt_app, lambda: not worker.isRunning())
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
        _until(qt_app, dialog.save_button.isEnabled)
        draft = dialog.inspection.detect_draft
        assert len(threads) == 1 and threads[0] != threading.get_ident()
        assert draft.params["x"] == pytest.approx(3)
        assert draft.params["z"] == pytest.approx(17.5)
        seed = draft.params["seed_face"]
        assert seed != 0
        expected = before.scene.objects["obj_1"].mesh.raw.face_normals[seed]
        assert np.allclose([draft.params[key] for key in ("nx", "ny", "nz")], expected)
        dialog.radius.set_value(8.5)
        _until(qt_app, dialog.save_button.isEnabled)
        assert len(threads) == 1
    finally:
        dispose(dialog, qt_app)


def test_ray_with_no_original_hit_never_uses_the_lod_placeholder(qt_app, profile, monkeypatch):
    dialog, _project, _before = make_dialog(
        profile, monkeypatch, original_ray=((200, 0, 17.5), (1, 0, 0))
    )
    try:
        _until(qt_app, lambda: dialog._worker is None and not dialog._pending)
        assert dialog.inspection is None
        assert not dialog.save_button.isEnabled()
        assert "Stelle" in dialog.state.text()
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
        _until(qt_app, lambda: dialog._worker is None and not dialog._pending)
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
        _until(qt_app, lambda: dialog._worker is None and not dialog._pending)
        assert dialog.inspection is None and not dialog.save_button.isEnabled()
        assert dialog.state.text()
        assert not dialog.progress.isVisible()
    finally:
        dispose(dialog, qt_app)
