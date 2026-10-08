"""Mehrfachimport am Fenster: Abbrechen, Einfügen, Rückfrage, Gestensperre (RM-131, NM 2–4).

Die Kernfälle (Dateilage, eine Transaktion, Lesefehler, späte Antworten)
stehen in ``test_ui.py``; hier steht, was der Kunde über Menü und Dialog
erlebt. Sollwerte kommen aus der Konstruktion im Test: drei Würfel 20 mm an
festen Mitten.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QFileDialog

from app.core.scene import OperationDraft
from tests.ui_helpers import MESHES
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window

CENTRES = ((15.0, 25.0, 35.0), (65.0, 25.0, 55.0), (-10.0, 45.0, 20.0))


def _cubes(folder: Path) -> list[Path]:
    import trimesh

    paths = []
    for index, centre in enumerate(CENTRES):
        mesh = trimesh.creation.box((20, 20, 20))
        mesh.apply_translation(centre)
        path = folder / f"teil-{index}.stl"
        path.write_bytes(mesh.export(file_type="stl"))
        paths.append(path)
    return paths


@pytest.mark.parametrize("place", ["start", "project"])
def test_cancelling_the_file_dialog_keeps_project_selection_and_star(window, monkeypatch, place):
    """NM 2: Abbrechen im Dateidialog ändert weder Projekt noch Auswahl noch Stern."""
    window.session.apply("Quader", [OperationDraft(op="create_box")])
    assert window.session.wait_for_idle()
    window._show_start_screen(place == "start")
    key = next(iter(window.session.last_result.scene.objects))
    window.object_tree.select_object(key)
    project = window.session.project
    steps = list(project.document.ops)
    title = window.windowTitle()
    titles = []

    def cancelled(_parent, caption, *_args, **_kwargs):
        titles.append(caption)
        return [], ""

    monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(cancelled))
    window.action_import()
    QApplication.processEvents()
    assert titles == ["Modell öffnen" if place == "start" else "Modell einfügen"]
    assert window.session.project is project
    assert project.document.ops == steps
    assert window.session.modified
    assert window.windowTitle() == title
    assert tuple(window.object_tree.selected_objects()) == (key,)


def test_declining_the_recognition_question_imports_every_file_once(session, monkeypatch, tmp_path):
    """NM 2: Wer die Frage zur Vollerkennung schließt, bekommt alle Dateien, gefragt einmal."""
    import importlib

    from app.ui import session as session_module

    evaluation = importlib.import_module("app.core.scene.evaluate")
    monkeypatch.setattr(evaluation, "FEATURE_LIMIT_TRIANGLES", 1)
    monkeypatch.setattr(session_module, "FEATURE_LIMIT_TRIANGLES", 1)
    asked = []

    def decline(request):
        asked.append(request)
        request.reply(None)

    session.askRequested.connect(decline)
    session.import_models_async(_cubes(tmp_path))
    assert session.wait_for_idle(60_000)
    assert len(asked) == 1, [request.question for request in asked]
    assert len(session.project.document.transactions) == 1
    assert len(session.last_result.scene.objects) == 3
    for body, centre in zip(session.last_result.scene.objects.values(), CENTRES, strict=True):
        assert body.mesh.bounds.centre == pytest.approx(centre)


def test_inserting_several_models_keeps_the_body_and_undoes_only_the_group(window, tmp_path):
    """NM 3: *Modell einfügen* in ein Projekt — vorhandener Körper bleibt, ein Undo je Gruppe."""
    from app.core.scene import evaluate
    from app.core.scene.project import ProjectSources, load

    window._show_start_screen(False)
    window.session.apply("Quader", [OperationDraft(op="create_box")])
    assert window.session.wait_for_idle()
    existing = dict(window.session.last_result.scene.objects)
    window.import_paths(_cubes(tmp_path))
    assert window.session.wait_for_idle(60_000)
    QApplication.processEvents()
    scene = window.session.last_result.scene.objects
    assert len(scene) == 4
    for key, body in existing.items():
        assert scene[key].mesh.bounds.centre == pytest.approx(body.mesh.bounds.centre)
    added = [body for key, body in scene.items() if key not in existing]
    offsets = [
        tuple(
            a - b for a, b in zip(body.mesh.bounds.centre, added[0].mesh.bounds.centre, strict=True)
        )
        for body in added
    ]
    expected = [tuple(a - b for a, b in zip(centre, CENTRES[0], strict=True)) for centre in CENTRES]
    assert offsets == [pytest.approx(offset) for offset in expected], "Lage zueinander bleibt"
    transactions = len(window.session.project.document.transactions)
    window.session.undo()
    assert window.session.wait_for_idle()
    assert set(window.session.last_result.scene.objects) == set(existing)
    window.session.redo()
    assert window.session.wait_for_idle()
    assert len(window.session.last_result.scene.objects) == 4
    assert len(window.session.project.document.transactions) == transactions
    saved = window.session.save_project(tmp_path / "eingefuegt.p3d")
    restored = load(saved)
    result = evaluate(
        restored.document,
        window.session.profile,
        sources=ProjectSources(restored),
        detect_features=False,
    )
    assert len(result.scene.objects) == 4
    assert len(restored.document.transactions) == transactions


@pytest.mark.parametrize("editor", ["sculpting", "setting_armature"])
def test_an_open_gesture_editor_refuses_a_batch_import_and_names_the_way_back(
    window, monkeypatch, editor
):
    """NM 4: Eine laufende Form- oder Skelettsitzung nimmt keinen Import an und sagt warum."""
    from app.ui.main_window import _the_change_comes_first

    window._show_start_screen(False)
    monkeypatch.setattr(window, editor, lambda: True)
    steps = list(window.session.project.document.ops)
    window.import_paths([MESHES / "cube_clean.stl", MESHES / "cube_clean.stl"])
    QApplication.processEvents()
    assert window.session.project.document.ops == steps
    assert not window.session.busy
    assert window._announcement == _the_change_comes_first()
