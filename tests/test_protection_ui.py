"""Die Sichtflächen-Sperre von der Geste bis zur Naht (§22.3, RM-080).

„Diese Fläche soll schön bleiben" — die eine Kundengeste der Trennen-Serie
(T8). Geprüft wird der ganze Weg, weil er bis zum 14.09.2026 an zwei Enden
offen war: Der Kern kannte ``protect``, der Viewport die Markierung, und kein
Aufrufer reichte das eine an das andere; und die Markierung lebte nur in der
Ansicht, also war sie nach dem Schließen weg.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
from PySide6.QtWidgets import QApplication, QCheckBox

from app.core.errors import AppError
from app.core.geom.autosplit import SplitOutcome
from app.core.geom.mesh import as_mesh_data
from app.core.split import SplitPlan
from app.core.types import Finding
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def window(qt_app: QApplication) -> MainWindow:
    # Aufgeräumt wird zentral: ``tests/conftest.py`` wartet nach jedem Test
    # auf die Arbeiter jedes offenen Fensters.
    return MainWindow(Session(), UiSettings())


def a_plate_with_a_face(window: MainWindow) -> tuple[str, str]:
    """Die Platte mit Bohrungen geöffnet, ihre erste Fläche gewählt."""
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    face = next(key for key, feature in entry.features.items() if feature.kind == "face")
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, face)
    return object_id, face


def the_toggle(window: MainWindow) -> QCheckBox:
    toggle = window.feature_panel.protection_toggle()
    assert toggle is not None, "an einer Fläche steht der Umschalter"
    return toggle


def test_the_toggle_writes_the_document_and_the_picture_follows(
    window: MainWindow, tmp_path: Path
) -> None:
    """Ein Haken, drei Folgen: Dokument, Bild, Statuszeile.

    Das Dokument ist die Wahrheit (die Sperre wird gespeichert), das Bild
    folgt ihm über ``projectChanged``, und die Statuszeile nennt sie beim
    Namen — die zweite Kodierung neben der Schraffur (Regel 18).
    """
    object_id, face = a_plate_with_a_face(window)
    # Gespeichert, damit „geändert" danach nur die Sperre meinen kann und
    # nicht den Import davor.
    window.session.save_project(tmp_path / "platte.p3d")
    toggle = the_toggle(window)
    assert toggle.isEnabled() and not toggle.isChecked()
    assert not window.session.modified

    toggle.setChecked(True)

    assert window.session.project.document.protected == {object_id: (face,)}
    assert window.session.modified, "sonst geht die Sperre beim Schließen verloren"
    assert window.viewport.protected_features(object_id) == (face,)
    assert window.selection_label().endswith("geschützt")

    toggle.setChecked(False)

    assert window.session.project.document.protected == {}
    assert window.viewport.protected_features(object_id) == ()
    assert not window.selection_label().endswith("geschützt")


def test_a_reopened_project_shows_its_protection(window: MainWindow, tmp_path: Path) -> None:
    """Speichern, schließen, öffnen — die Sperre steht noch, im Dokument und im Bild.

    Das war der Fall, an dem der Kunde seine Arbeit verlor: Als
    Ansichtszustand war die Markierung nach dem Schließen weg, und er erfuhr
    es an dem Schnitt, der durch die Fläche ging, die er schützen wollte.
    """
    object_id, face = a_plate_with_a_face(window)
    the_toggle(window).setChecked(True)
    window.session.save_project(tmp_path / "platte.p3d")

    window.session.open_project(tmp_path / "platte.p3d")
    window.session.wait_for_idle()
    window.session.evaluate_now()
    QApplication.processEvents()

    assert window.session.project.document.protected == {object_id: (face,)}
    assert window.viewport.protected_features(object_id) == (face,)
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, face)
    assert the_toggle(window).isChecked(), "der Haken zeigt den gespeicherten Stand"


def test_the_search_receives_the_protected_points(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der fehlende Draht: ``split_async`` reicht die Wolken an ``plan_split``.

    Aufgezeichnet wird, was die Suche bekommt — nicht, was das Bild zeigt.
    Die Wolke der Oberseite liegt ganz oben, und daran ist sie zu erkennen.
    """
    from app.ui import session as session_module

    object_id, face = a_plate_with_a_face(window)
    the_toggle(window).setChecked(True)
    result = window.session.last_result
    assert result is not None
    entry = result.scene.objects[object_id]
    top = max(float(z) for z in as_mesh_data(entry.mesh).raw.vertices[:, 2])

    seen: list[Any] = []

    def record(mesh: Any, _object_id: str, _profile: Any, **kwargs: Any) -> SplitPlan:
        seen.append(tuple(kwargs.get("protect", ())))
        return SplitPlan(drafts=(), outcome=SplitOutcome(parts=[mesh]))

    monkeypatch.setattr(session_module, "plan_split", record)

    window.action_auto_split(object_id)
    window.session.wait_for_idle()

    assert len(seen) == 1, "die Suche lief genau einmal"
    assert len(seen[0]) == 1, "eine gesperrte Fläche, eine Wolke"
    face_feature = entry.features[face]
    assert len(seen[0][0]) == 3 * len(face_feature.face_indices)
    assert all(abs(float(point[2]) - top) < 1e-6 for point in seen[0][0]) or all(
        abs(float(point[2]) - top) > 1e-6 for point in seen[0][0]
    ), "die Wolke ist die einer ebenen Fläche"


def test_releasing_the_protection_from_the_report_splits_again(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """*Sperren aufheben und erneut teilen* am Befund — mit dem Körper aus dem Befund.

    Aufgehoben werden alle Sperren des Körpers, dann startet die Suche neu.
    Der Handler liest den Körper aus dem Fehler, nie aus der Auswahl.
    """
    from app.ui import session as session_module

    object_id, _face = a_plate_with_a_face(window)
    the_toggle(window).setChecked(True)

    seen: list[Any] = []

    def record(mesh: Any, _object_id: str, _profile: Any, **kwargs: Any) -> SplitPlan:
        seen.append(tuple(kwargs.get("protect", ())))
        return SplitPlan(drafts=(), outcome=SplitOutcome(parts=[mesh]))

    monkeypatch.setattr(session_module, "plan_split", record)
    finding = Finding(
        code="split.blocked_by_protection",
        severity="warning",
        message="Neben den geschützten Flächen bleibt für dieses Teil keine Trennebene übrig.",
        object_id=object_id,
        values={"blocked_planes": 33},
    )
    error = AppError(str(finding.message), object_id=finding.object_id)

    window.error_handlers()["release_protection"](error)
    window.session.wait_for_idle()

    assert window.session.project.document.protected == {}
    assert window.viewport.protected_features(object_id) == ()
    assert seen == [()], "die Suche lief ohne Sperre erneut"


def test_the_report_offers_release_first_on_a_blocked_split() -> None:
    """Der Befund trägt seinen Ausweg vorn: aufheben, dann die Linie."""
    from app.ui.panels import FINDING_ACTIONS

    offered = [action.id for action in FINDING_ACTIONS["split.blocked_by_protection"]]
    assert offered[0] == "release_protection"
    assert "split_along_line" in offered
