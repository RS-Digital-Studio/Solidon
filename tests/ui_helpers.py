"""Gemeinsame Fenster-Fixtures und Exporthilfen; der Qt-Abbau bleibt in conftest."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import (
    QApplication,
    QMessageBox,
)

from app.i18n import tr
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def session(qt_app: QApplication) -> Session:
    return Session()


@pytest.fixture
def window(qt_app: QApplication, session: Session) -> MainWindow:
    # Aufgeräumt wird zentral: ``tests/conftest.py`` wartet nach jedem Test
    # auf die Arbeiter jedes offenen Fensters.
    return MainWindow(session, UiSettings())


def shown_window(qt_app: QApplication) -> Iterator[MainWindow]:
    """Ein gezeigtes Fenster ohne Startbildschirm, für eine Fixture mit ``yield from``.

    Gezeigt, weil Qt ein Resize-Ereignis an ein verstecktes Widget erst beim
    Anzeigen zustellt — und die Geometrie der Zonen entsteht genau dort. Ein
    Test auf einem nie gezeigten Fenster misst die Vorgabegröße 640 × 480.
    Offscreen kostet das nichts.
    """
    window = MainWindow(Session(), UiSettings())
    window.show()
    window.resize(1200, 900)
    # Und der Startbildschirm muss weg: solange er im Stapel oben liegt, hat
    # der Träger darunter keine Größe, und alle Zonen lägen auf 100 Pixeln.
    window._show_start_screen(False)
    qt_app.processEvents()
    yield window
    # Aufräumen ist hier Pflicht und nicht Höflichkeit: ein gezeigtes Fenster,
    # das stehen bleibt, bekommt weiter Ereignisse — und riss siebzehn Tests
    # *nach* ``test_overlay.py`` mit ``AttributeError`` aus dem Ereignisfilter.
    window.close()
    window.deleteLater()
    qt_app.processEvents()


def with_a_body(window: MainWindow) -> str:
    """Die saubere Figur aus dem Korpus, ausgewählt wie nach einem Klick — die Vorlage für
    Form- und Skelettsitzung; ihre mittlere Kantenlänge von 2,8 mm macht nebenbei den
    Auflösungshinweis prüfbar.
    """
    window.open_path(MESHES / "clean_figure.stl")
    window.session.wait_for_idle()
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    item.setSelected(True)
    object_id = window.object_tree.selected()
    assert object_id
    return str(object_id)


def wait_for_export(window: MainWindow) -> None:
    """§2.8: Exportiert wird im Arbeiter, der Test wartet also wie das Fenster.

    Nach dem Warten einmal zustellen — ``done`` ist eine Warteschlangen-
    Verbindung, und ohne ``processEvents`` kämen weder Meldung noch Befunde je
    an.

    **Zwei Runden, seit der Export erst prüft und dann schreibt** (§29,
    RM-140): Der erste Lauf endet an der Prüfung, wenn sie etwas findet; die
    Antwort darauf startet den zweiten. Wo nichts gefragt wird, ist die zweite
    Runde ein ``processEvents`` ohne Arbeiter und kostet nichts.
    """
    for _ in range(2):
        worker = window._export_worker
        if worker is not None:
            worker.wait(20_000)
        QApplication.processEvents()


def export_anyway(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Frage vor dem Schreiben bejahen (§29, RM-140).

    Zwei Körper genau übereinander sind ein Befund, und seit RM-140 fragt der
    Export danach, bevor er schreibt. Ein Test, dessen Szene eine Warnung
    trägt, beantwortet sie — sonst stünde die Suite offscreen an einem modalen
    Dialog, und zwar ohne rot zu werden (siehe ``.claude/rules/oberflaeche.md``).
    """

    def trotzdem(box: QMessageBox) -> int:
        next(entry for entry in box.buttons() if entry.text() == tr("Trotzdem exportieren")).click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", trotzdem)


def expire_trial(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import activation

    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=0))
