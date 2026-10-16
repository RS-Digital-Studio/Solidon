"""Eine Vorschauantwort nach dem Abbau des Fensters greift ins Leere nicht hinein (FD-158).

Die Vorschau rechnet im Arbeiter; ihre Rückrufe meldet das Fenster an einer
Stelle an (``MainWindow._request_order_preview``, ``still``). Kam eine Antwort
nach dem Abbau an, fragte ``_preview_is_current`` den Objektbaum, den es auf
der C++-Seite nicht mehr gab: ``RuntimeError: … _ObjectTreeView already
deleted`` (gesehen nach einem roten Fall in ``test_ui.py``). Hier wird das
Fenster zwischen Anfrage und Antwort abgebaut und jede Antwort zugestellt.
"""

from __future__ import annotations

from typing import Any

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QApplication
from shiboken6 import isValid

from app.core.scene import OperationDraft
from app.ui.main_window import MainWindow, _PreviewOrder
from app.ui.session import Session
from app.ui.settings import UiSettings


def test_a_preview_answer_after_the_teardown_touches_nothing(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    session = Session()
    session.history.apply("Quader", [OperationDraft(op="create_box")])
    session.evaluate_now()
    window = MainWindow(session, UiSettings())
    requests: list[tuple[Any, dict[str, Any]]] = []
    monkeypatch.setattr(
        window.session,
        "preview_async",
        lambda then, drafts=None, **kwargs: requests.append((then, kwargs)),
    )
    order = _PreviewOrder(drafts=(OperationDraft(op="create_box"),))
    approval = window._set_preview_order(window.feature_panel, order)
    window._request_order_preview(approval)
    assert requests, "die Vorschau wurde angefragt"
    shown, callbacks = requests[-1]

    window.release()
    window.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    QApplication.processEvents()
    assert not isValid(window), "das Fenster ist abgebaut"

    # Jede Antwort der Vorschau, wie der Arbeiter sie nach dem Abbau zustellt.
    shown(None)
    for name in ("explained", "failed", "refused", "asked", "pictured"):
        callbacks[name]("Nachzügler" if name == "explained" else None)
    session.release()
