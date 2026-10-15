"""Ein Feld, dessen einzige Eingabe ein Knopf ist, bedient der Kunde über diesen Knopf (FD-101).

``QtPorts.aim`` lenkt einen Klick auf ein Feld in sein Eingabefeld — Zahlenfeld,
Auswahlliste, Textfeld. Das Feld *Dichtweg* (``field:path_sketch``) trägt nur
einen dehnbaren Satz und den Knopf *Dichtweg wählen …*: Der Klick fiel in die
Mitte, auf den Satz, und der Dichtwegdialog öffnete nie. Allgemein: Ist ein
Knopf die einzige Eingabe des Felds, gilt der Klick ihm; hat das Feld ein
Eingabefeld oder eine Liste, bleibt alles wie zuvor.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from tools.function_walk import QtPorts


def _field(qt_app: Any, *extras: str) -> tuple[Any, dict[str, Any]]:
    from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QListWidget, QPushButton, QWidget

    from app.core import guides

    holder = QWidget()
    holder.setProperty(guides.TARGET_PROPERTY, "field:probe")
    row = QHBoxLayout(holder)
    parts: dict[str, Any] = {"label": QLabel("Noch kein Dichtweg gewählt", holder)}
    row.addWidget(parts["label"], 1)
    if "line" in extras:
        parts["line"] = QLineEdit(holder)
        row.addWidget(parts["line"])
    if "list" in extras:
        parts["list"] = QListWidget(holder)
        row.addWidget(parts["list"])
    parts["button"] = QPushButton("Dichtweg wählen …", holder)
    row.addWidget(parts["button"])
    holder.resize(600, 80)
    holder.show()
    for _ in range(20):
        qt_app.processEvents()
    return holder, parts


def _aim(holder: Any) -> Any:
    ports = QtPorts(holder, 0.0)
    centre = holder.mapToGlobal(holder.rect().center())
    return ports.aim(SimpleNamespace(target="field:probe", why="ziel"), centre), centre


@pytest.mark.parametrize(
    ("extras", "expected"),
    [((), "button"), (("line",), "line"), (("list",), None)],
    ids=["nur-knopf", "mit-textfeld", "mit-liste"],
)
def test_a_field_whose_only_input_is_a_button_is_clicked_on_it(
    qt_app: Any, extras: tuple[str, ...], expected: str | None
) -> None:
    from PySide6.QtCore import QPoint, QRect

    holder, parts = _field(qt_app, *extras)
    try:
        aimed, centre = _aim(holder)
        if expected is None:
            # Eine Liste ist eine Eingabe: kein Umlenken auf einen Knopf daneben.
            assert aimed == centre
        else:
            widget = parts[expected]
            assert QRect(widget.mapToGlobal(QPoint(0, 0)), widget.size()).contains(aimed), aimed
    finally:
        holder.hide()
        holder.deleteLater()
        qt_app.processEvents()
