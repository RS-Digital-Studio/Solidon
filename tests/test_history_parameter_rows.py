"""Ein Doppelklick auf eine Maßänderung im Verlauf öffnet das Maß (FD-166).

*Parameter anlegen …* legt eine Transaktion ohne Operation an. Ihre Zeile im
Verlauf trug weder ``UserRole`` noch ``OPS_ROLE``, und ``_on_activated`` blieb
stumm — obwohl die Liste „Doppelklick öffnet einen Schritt“ verspricht. Jetzt
geht der Doppelklick denselben Weg wie *Ändern …* an der Parameterzeile
(``ParameterPanel.limitsRequested`` → ``MainWindow.action_edit_parameter``);
ein Maß, das es nicht mehr gibt, sagt das statt zu schweigen.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from PySide6.QtWidgets import QListWidgetItem

from app.core.scene.history import History, change_for
from app.core.types import Document, DocumentChange, DocumentState, Parameter
from tests import qt_roots

roots = qt_roots.roots


def _document_with(*names: str) -> Document:
    """Ein Dokument, in dem je Name eine Transaktion *Parameter anlegen* steht."""
    document = Document(format_version=1, app_version="0.0.1")
    history = History(document)
    for name in names:
        history.apply(
            f"Parameter {name}",
            changes=change_for(document, parameters={name: Parameter(name=name, value=12.0)}),
        )
    return document


def _row_of(panel: Any, name: str) -> QListWidgetItem:
    rows = [panel.list.item(row) for row in range(panel.list.count())]
    found = [item for item in rows if name in item.text()]
    assert len(found) == 1, [item.text() for item in rows]
    return found[0]


def test_a_double_click_on_a_parameter_row_opens_that_parameter(
    qt_app: Any, roots: Callable[[Any], Any]
) -> None:
    from app.ui.panels import HistoryPanel

    panel = roots(HistoryPanel())
    panel.show_document(_document_with("breite", "hoehe"))
    opened: list[str] = []
    said: list[str] = []
    # Über ``getattr``: Am Original fehlt das Signal, und gemessen wird, dass
    # der Doppelklick dort gar nichts tut — nicht, dass ein Name fehlt.
    if (signal := getattr(panel, "parameterActivated", None)) is not None:
        signal.connect(opened.append)
    panel.noteRequested.connect(said.append)

    panel.list.itemDoubleClicked.emit(_row_of(panel, "hoehe"))

    assert opened == ["hoehe"], said


def test_a_parameter_that_is_gone_says_so_instead_of_staying_silent(
    qt_app: Any, roots: Callable[[Any], Any]
) -> None:
    from app.ui.panels import HistoryPanel

    document = _document_with("breite")
    History(document).apply(
        "Parameter breite entfernt",
        changes=DocumentChange(
            before=DocumentState(parameters={"breite": document.parameters["breite"]}),
            after=DocumentState(parameters={"breite": None}),
        ),
    )
    panel = roots(HistoryPanel())
    panel.show_document(document)
    opened: list[str] = []
    said: list[str] = []
    # Über ``getattr``: Am Original fehlt das Signal, und gemessen wird, dass
    # der Doppelklick dort gar nichts tut — nicht, dass ein Name fehlt.
    if (signal := getattr(panel, "parameterActivated", None)) is not None:
        signal.connect(opened.append)
    panel.noteRequested.connect(said.append)

    first = panel.list.item(0)
    panel.list.itemDoubleClicked.emit(first)

    assert not opened
    assert len(said) == 1 and "breite" in said[0], said
