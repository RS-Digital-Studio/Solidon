"""Gemeinsame Fenster-Fixtures und Exporthilfen; der Qt-Abbau bleibt in conftest."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

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
