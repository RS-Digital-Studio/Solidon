"""Auto Split und die Explosionsansicht aus dem Fenster (§25, §18.8)."""

from __future__ import annotations

from pathlib import Path

import pytest
import trimesh
from PySide6.QtWidgets import QApplication

from app.core.geom.mesh import MeshData
from app.core.scene import History, OperationDraft
from app.core.scene.project import new_project
from app.core.types import Source
from app.ui.explode_bar import ExplodeBar
from app.ui.session import Session

MESHES = Path(__file__).parent / "data" / "meshes"


def loaded(session: Session, name: str) -> None:
    payload = (MESHES / name).read_bytes()
    session.project = new_project("centauri-carbon-2", "petg")
    session.project.sources["src_1"] = payload
    session.project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/{name}", sha256=""
    )
    session.history = History(session.project.document)
    session.history.apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    session.evaluate_async()
    session.wait_for_idle()


def test_the_bar_says_when_there_is_something_to_pull_apart(
    qt_app: QApplication,
) -> None:
    """``show_for`` **antwortet**, es zeigt nicht.

    Sichtbar macht die Leiste allein die Werkzeugzeile, der sie gehört. Solange
    sie sich selbst zeigte, steuerten zwei Stellen dasselbe: die eine klappte
    auf, was die andere zugeklappt hielt, und die Leiste landete über den
    Umschaltern.
    """
    bar = ExplodeBar()

    assert bar.show_for(1) is False
    assert bar.show_for(3) is True
    assert not bar.isVisible(), "gezeigt wird sie erst auf Knopfdruck"


def test_folding_back_together_resets_the_slider(qt_app: QApplication) -> None:
    """Ein Schieber, der einen Wert behält, den niemand mehr sieht, ist eine
    Falle.
    """
    bar = ExplodeBar()
    bar.show_for(2)
    bar.slider.setValue(8)

    bar.show_for(1)

    assert bar.factor == 0.0


def test_the_slider_reports_a_factor(qt_app: QApplication) -> None:
    """Der Faktor kommt entprellt: jede Stufe baut die ganze Ansicht neu, und
    ein Zug über den Regler soll eine Rechnung auslösen statt zwanzig.

    Geprüft wird, **dass** der Zeitgeber läuft, nicht wie lange. Vorher stand
    hier ein ``processEvents`` zwischen den Reglerstufen und dem Auslösen von
    Hand: liefen dazwischen mehr als die hundertzwanzig Millisekunden der
    Entprellung — und unter der vollen Suite tun sie das —, feuerte er dort
    schon, und das Signal kam zweimal. Ein Test, der bei belasteter Maschine
    rot wird, misst die Maschine.
    """
    bar = ExplodeBar()
    seen: list[float] = []
    bar.factorChanged.connect(seen.append)

    bar.slider.setValue(4)
    bar.slider.setValue(10)
    assert seen == [], "während der Zeiger unterwegs ist, wird nicht gerechnet"
    assert bar._pending.isActive(), "aber es ist etwas angemeldet"

    bar._pending.stop()
    bar._settled()

    assert seen == [1.0]
    assert bar.factor == 1.0


def test_revealing_a_split_opens_a_gap_immediately(qt_app: QApplication) -> None:
    """Nach einer Teilung sollen Stifte und Löcher ohne einen gesuchten
    zweiten Handgriff sichtbar werden.

    ``reveal`` wartet nicht auf die Entprellung des Schiebers: Der Nutzer hat
    ihn nicht gezogen, die Anwendung zeigt ein fertiges Ergebnis.
    """
    bar = ExplodeBar()
    seen: list[float] = []
    bar.factorChanged.connect(seen.append)

    bar.reveal()

    assert bar.factor > 0.0
    assert seen == [bar.factor]
    assert not bar._pending.isActive()


def test_the_session_splits_an_oversized_part(qt_app: QApplication) -> None:
    session = Session()
    loaded(session, "oversized.stl")

    applied = session.auto_split("obj_1")
    session.wait_for_idle()

    assert len(applied.object_ids) == 2
    assert len(applied.fits) == 2
    assert session.last_result is not None
    assert set(session.last_result.scene.objects) == set(applied.object_ids)


def test_the_result_of_the_split_stays_readable(qt_app: QApplication) -> None:
    """„Geteilt: 2 · 2 Passungen" stand nie da (§2.8).

    ``_split_done`` schrieb die Zeile, und das ``busy``-Signal desselben
    Arbeiters leerte sie unmittelbar danach. Wie viele Teile und wie viele
    Passungen entstanden sind, sagt sonst nichts im Fenster — im Objektbaum
    stehen die Teile, die Passungen stehen nirgends.
    """
    from app.ui.main_window import MainWindow
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    loaded(window.session, "oversized.stl")
    QApplication.processEvents()

    window._split_done(window.session.auto_split("obj_1"))
    window.session.wait_for_idle()
    # Genau der Schlag, der die Meldung bisher löschte: das Ende des Laufs.
    window._on_busy(False)
    window._on_split_busy(False)
    QApplication.processEvents()

    assert "2" in window.status_message.text(), (
        f"die Meldung des Teilens ist weg: {window.status_message.text()!r}"
    )


def test_a_new_project_drops_the_old_message(qt_app: QApplication) -> None:
    """Eine Meldung überlebt ihren Lauf, aber nicht ihr Projekt."""
    from app.ui.main_window import MainWindow
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    window.announce("Exportiert: dose.3mf")

    window.start_empty()
    QApplication.processEvents()

    assert window.status_message.text() == ""


def test_a_part_that_fits_is_left_alone(qt_app: QApplication) -> None:
    session = Session()
    loaded(session, "cube_clean.stl")

    applied = session.auto_split("obj_1")

    assert applied.transaction is None
    assert applied.object_ids == ["obj_1"]


def test_the_explosion_never_reaches_the_geometry(qt_app: QApplication) -> None:
    """§18.8: sie ist eine Art, die Teile anzusehen, keine Art, sie zu bewegen."""
    from app.ui.viewport import Viewport

    session = Session()
    loaded(session, "oversized.stl")
    session.auto_split("obj_1")
    session.wait_for_idle()
    result = session.last_result
    assert result is not None
    before = {
        object_id: tuple(entry.mesh.bounds.centre)
        for object_id, entry in result.scene.objects.items()
    }

    viewport = Viewport()
    viewport.show_scene(result)
    viewport.set_explosion(1.5)

    after = {
        object_id: tuple(entry.mesh.bounds.centre)
        for object_id, entry in result.scene.objects.items()
    }
    assert after == before


def test_the_offset_points_away_from_the_middle(qt_app: QApplication) -> None:
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.viewport import Viewport

    left = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    right_body = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    right_body.apply_translation((40.0, 0.0, 0.0))
    result = EvaluationResult(
        scene=Scene(
            objects={
                "obj_1": SceneObject(id="obj_1", name="A", mesh=left),
                "obj_2": SceneObject(id="obj_2", name="B", mesh=MeshData.of(right_body)),
            }
        )
    )

    viewport = Viewport()
    viewport._explosion = 1.0
    offset = viewport._exploded(result.scene.objects["obj_2"], result)

    assert offset[0] == pytest.approx(20.0), "half the distance between the two centres"
    assert offset[1] == pytest.approx(0.0)
