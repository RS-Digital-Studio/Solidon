"""Doppelklick auf Drucker-, Material- oder Passungsänderung im Verlauf (RA-6).

FD-166 gab der Maßänderung ein Ziel. Eine Transaktion ohne Schritt ändert aber
auch Drucker, Material oder Passungen (``DocumentState``), und dort tat der
Doppelklick nichts, obwohl ``_on_activated`` zusagt, nicht stumm zu bleiben.
Drucker und Material öffnen die Druckeinstellungen; eine Passung sagt, wo ihr
Zustand steht und wie sie zurückgeht.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.core.types import Document, DocumentChange, DocumentState, FeatureRef, Fit, Transaction
from tests import qt_roots

roots = qt_roots.roots


def _document() -> Document:
    document = Document(format_version=1, app_version="0.0.1")
    fit = Fit(
        name="Zapfen in Bohrung",
        a=FeatureRef("obj_1", "pin_1"),
        b=FeatureRef("obj_2", "hole_1"),
    )
    document.transactions.extend(
        [
            Transaction(
                id="t1",
                title="Drucker wechseln",
                ops=(),
                changes=DocumentChange(
                    before=DocumentState(printer="alt"), after=DocumentState(printer="neu")
                ),
            ),
            Transaction(
                id="t2",
                title="Material wechseln",
                ops=(),
                changes=DocumentChange(
                    before=DocumentState(material="pla"), after=DocumentState(material="petg")
                ),
            ),
            Transaction(
                id="t3",
                title="Passung anlegen",
                ops=(),
                changes=DocumentChange(
                    before=DocumentState(fits=()), after=DocumentState(fits=(fit,))
                ),
            ),
        ]
    )
    return document


def test_rows_without_a_step_lead_somewhere(qt_app: Any, roots: Callable[[Any], Any]) -> None:
    from app.ui.panels import HistoryPanel

    panel = roots(HistoryPanel())
    panel.show_document(_document())
    heard: list[tuple[str, Any]] = []
    panel.operationActivated.connect(lambda value: heard.append(("operation", value)))
    panel.parameterActivated.connect(lambda value: heard.append(("parameter", value)))
    panel.noteRequested.connect(lambda value: heard.append(("note", value)))
    if (signal := getattr(panel, "printSettingsActivated", None)) is not None:
        signal.connect(lambda: heard.append(("print", None)))
    rows = {panel.list.item(row).text(): panel.list.item(row) for row in range(panel.list.count())}

    result: dict[str, list[tuple[str, Any]]] = {}
    for text, item in rows.items():
        heard.clear()
        panel.list.itemDoubleClicked.emit(item)
        result[text] = list(heard)

    printer = next(said for text, said in result.items() if "Drucker" in text)
    material = next(said for text, said in result.items() if "Material" in text)
    fit = next(said for text, said in result.items() if "Passung" in text)
    assert printer == [("print", None)], result
    assert material == [("print", None)], result
    assert len(fit) == 1 and fit[0][0] == "note" and "Prüfbericht" in fit[0][1], result
