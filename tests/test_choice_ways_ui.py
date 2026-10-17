"""Eine Auswahlhandlung öffnet den Schritt mit ihrem Feld sichtbar und im Fokus (RB-2).

*Anderes Merkmal wählen* an *Kammer ändern* ließ das Feld *Kammer* zugeklappt
und setzte den Cursor in die Breite; *Andere Kanten wählen* an *Verrunden*
setzte ihn in den Radius, genau wie *Eingabe korrigieren* daneben. Gemessen
am echten Fenster (offscreen): der Befund des angehaltenen Schritts als Fehler
(``panels.as_error``), die Handlung über die Handler des Fensters, gelesen am
offenen Operationsdialog. Die Anpassung an den Schritt selbst prüft
``test_choice_ways.py`` ohne Fenster.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication, QWidget


@pytest.fixture
def opened(qt_app: QApplication, tmp_path: Path) -> Iterator[Callable[[Any], Any]]:
    from app.core.scene.project import save
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    windows: list[Any] = []

    def open_one(project: Any) -> Any:
        path = tmp_path / f"auswahl{len(windows)}.p3d"
        save(project, path)
        window = MainWindow(Session(), UiSettings())
        window.resize(1920, 1080)
        window.show()
        window._show_start_screen(False)
        window.open_path(path)
        assert window.session.wait_for_idle(120_000)
        qt_app.processEvents()
        windows.append(window)
        return window

    yield open_one
    for window in windows:
        assert window.session.wait_for_idle(120_000)
        window.wait_for_workers()
        window.hide()
        window.deleteLater()
    qt_app.processEvents()


def _project(scene: str, extra: list[tuple[str, dict[str, Any]]]) -> Any:
    from app.core.scene import History, OperationDraft
    from tools import function_scenes

    project = function_scenes.build_scene(scene)
    history = History(project.document)
    for op, params in extra:
        history.apply(op, [OperationDraft(op=op, inputs=("obj_1",), params=params)])
    return project


def _halt_error(window: Any, op: str) -> Any:
    from app.ui.panels import as_error

    document = window.session.project.document
    op_id = next(entry.id for entry in document.ops if entry.op == op)
    result = window.session.last_result
    assert result is not None
    found = [entry for entry in result.scene.report.findings if entry.op_id == op_id]
    finding = next(entry for entry in found if entry.suggestions)
    return as_error(finding, document)


def _editor_of(dialog: Any, widget: QWidget | None) -> str | None:
    if widget is None:
        return None
    return next(
        (
            name
            for name, editor in dialog._editors.items()
            if widget is editor or editor.isAncestorOf(widget)
        ),
        None,
    )


def _opens(qt_app: QApplication, window: Any, op: str, action: Any, field: str) -> None:
    """Die Handlung steht als Knopf, öffnet den Schritt, das Feld ist sichtbar und im Fokus."""
    from app.ui.dialogs import offered_actions
    from app.ui.op_dialog import OperationDialog

    error = _halt_error(window, op)
    handlers = window.error_handlers()
    assert action in offered_actions(error, handlers), [str(a.label) for a in error.suggestions]
    before = {id(dialog) for dialog in window.findChildren(OperationDialog)}
    handlers[action.id](error)
    qt_app.processEvents()
    dialog = next(
        dialog
        for dialog in window.findChildren(OperationDialog)
        if dialog.isVisible() and id(dialog) not in before
    )
    try:
        assert window.session.wait_for_idle(120_000)
        qt_app.processEvents()
        assert dialog._editors[field].isVisible(), f"{field} liegt zugeklappt"
        # Offscreen wird der Dialog nicht aktiv; sein eigener Fokus zählt.
        assert _editor_of(dialog, dialog.focusWidget()) == field
    finally:
        dialog.reject()
        qt_app.processEvents()


def test_another_feature_opens_the_chamber_field(qt_app: QApplication, opened: Any) -> None:
    """*Kammer ändern* an einer Außenfläche: das Feld *Kammer* liegt hinten."""
    from app.core.errors import CHANGE_FEATURE

    window = opened(
        _project("quader.netz", [("resize_chamber", {"at_feature": "face_1", "width": 5.0})])
    )
    _opens(qt_app, window, "resize_chamber", CHANGE_FEATURE, "at_feature")


def test_other_edges_open_the_edges_not_the_radius(qt_app: QApplication, opened: Any) -> None:
    """*Verrunden* mit zu großem Radius: zwei Knöpfe, zwei Felder."""
    from app.core.errors import CHANGE_EDGES, CORRECT_INPUT
    from tools import function_scenes

    window = opened(function_scenes.build_scene("halt"))
    _opens(qt_app, window, "fillet_edges", CHANGE_EDGES, "edges")
    _opens(qt_app, window, "fillet_edges", CORRECT_INPUT, "radius")


def test_other_edges_at_named_edges_open_the_single_edges(
    qt_app: QApplication, opened: Any
) -> None:
    """*Verrunden* an einer einzeln gewählten Kante: die Liste hinten geht auf (RB2-3)."""
    from app.core.errors import CHANGE_EDGES
    from app.core.geom.edges import edge_key, edges_of
    from app.core.geom.mesh import as_mesh_data
    from app.core.scene import OperationDraft
    from tools import function_scenes

    window = opened(function_scenes.build_scene("quader.netz"))
    body = window.session.last_result.scene.objects["obj_1"]
    key = edge_key(edges_of(as_mesh_data(body.mesh))[0])
    window.session.apply(
        "Verrunden",
        [
            OperationDraft(
                op="fillet_edges",
                inputs=("obj_1",),
                params={"radius": 40.0, "edges": "named", "edge_keys": key},
            )
        ],
    )
    assert window.session.wait_for_idle(120_000)
    _opens(qt_app, window, "fillet_edges", CHANGE_EDGES, "edge_keys")


def test_other_faces_open_the_face_field(qt_app: QApplication, opened: Any) -> None:
    """*Fläche versetzen* an einer Rundung: keine ebene Fläche gewählt."""
    from app.core.errors import CHANGE_FACES

    window = opened(
        _project("merkmal.fillet.netz", [("push_face", {"face": "fillet_1", "distance": 1.0})])
    )
    _opens(qt_app, window, "push_face", CHANGE_FACES, "face")
