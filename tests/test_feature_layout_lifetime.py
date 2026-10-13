"""Merkmalabbau löst Layoutitems, bevor deren Widgets nativ verschwinden.

Eine gehaltene itemAt-Hülle entspricht dem Beobachter bei der Breitenmessung.
Geprüft wird vor DeferredDelete; auch ein roter Lauf kann dadurch seine noch
lebenden Widgets geordnet lösen, ohne jemals ein freigegebenes Item aufzurufen.
"""

from types import SimpleNamespace

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QLabel,
    QLayout,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import isValid

from app.core.bootstrap import load_operations
from app.core.geom.mesh import read_mesh
from app.core.perceive import features
from app.core.registry import REGISTRY
from app.ui.panels import FeaturePanel


@pytest.fixture
def panel(qt_app: QApplication):
    """Auch die rote Gegenprobe räumt ihre noch lebenden Layoutitems korrekt ab."""
    load_operations()
    current = FeaturePanel()
    owners = [current]
    yield current, owners
    for owner in owners:
        if not isValid(owner):
            continue
        for layout in owner.findChildren(QLayout):
            for child in owner.findChildren(QWidget):
                if isValid(child) and layout.indexOf(child) >= 0:
                    layout.removeWidget(child)
        owner.hide()
        owner.deleteLater()
        QCoreApplication.sendPostedEvents(owner, QEvent.Type.DeferredDelete)


def measured_features():
    """Der kleine vorhandene Bohrungskorpus liefert echte Kernangebote."""
    from pathlib import Path

    path = Path(__file__).parent / "data" / "meshes" / "plate_holes.stl"
    return features.detect(read_mesh(path.read_bytes(), ".stl"))


@pytest.mark.parametrize("rebuilding", [False, True])
@pytest.mark.parametrize("place", ["rows", "nested", "print_host", "nested_layout"])
def test_clear_releases_each_real_layout_before_deferred_widget_delete(
    panel, rebuilding: bool, place: str
) -> None:
    """Eigene Zeile, tiefer Schrittknopf und fremder Druckabschnitt gehen denselben Weg."""
    current, owners = panel
    if place == "rows":
        current.show_note("Diese Merkmalsauskunft gehört zum alten Stand.")
        widget = current._built[-1]
    elif place == "nested":
        current.show_part(
            SimpleNamespace(id=4, op="create_organizer", params={}),
            REGISTRY.get("create_organizer"),
        )
        widget = next(widget for widget in current._built if widget.parentWidget() is not current)
    else:
        host = QWidget()
        owners.append(host)
        outer = QVBoxLayout(host)
        rows = QVBoxLayout() if place == "nested_layout" else outer
        if rows is not outer:
            outer.addLayout(rows)
        current.set_print_host(rows)
        face = next(feature for feature in measured_features().values() if feature.kind == "face")
        current.show_feature(face.id, face)
        widget = current.protection_toggle()
        assert widget is not None and widget.parentWidget() is host
    parent = widget.parentWidget()
    assert parent is not None
    layout = rows if place in ("print_host", "nested_layout") else parent.layout()
    assert layout is not None and layout.indexOf(widget) >= 0
    item = layout.itemAt(layout.indexOf(widget))
    assert item is not None and isValid(item)
    neighbor = QLabel("Bleibende Zeile", parent)
    layout.addWidget(neighbor)
    neighbor_item = layout.itemAt(layout.indexOf(neighbor))
    assert neighbor_item is not None

    current.clear(rebuilding=rebuilding)

    assert not isValid(item), "Das Layoutitem muss vor dem nativen Widgetabbau entwertet sein."
    assert isValid(widget), "Das Widget selbst wartet weiterhin auf DeferredDelete."
    assert widget.parentWidget() is parent, "Kein elternloses Zwischenfenster."
    assert layout.indexOf(widget) == -1
    assert isValid(neighbor_item) and layout.indexOf(neighbor) >= 0
    QCoreApplication.sendPostedEvents(widget, QEvent.Type.DeferredDelete)
    assert not isValid(widget)
    assert isValid(layout)


def test_returning_measure_group_removes_only_borrowed_layout_items(panel) -> None:
    """Ein geliehener Flussschalter stirbt; die wiederverwendbaren Maßfelder bleiben."""
    current, owners = panel
    hole = next(feature for feature in measured_features().values() if feature.kind == "hole")
    current.show_feature(hole.id, hole)
    built = current.measure_fields("resize_hole", None, feature=hole)
    assert built is not None
    _, group, editors = built
    owners.append(group)
    layout = group.layout()
    assert isinstance(layout, QFormLayout)
    own_editor = editors["diameter"]
    own_item = layout.itemAt(layout.indexOf(own_editor))
    assert own_item is not None
    borrowed = QCheckBox("Auf alle anwenden", group)
    layout.addRow(borrowed)
    item = layout.itemAt(layout.indexOf(borrowed))
    assert item is not None

    assert current.keep_measure_group(group)

    assert not isValid(item), "Zurückgeben darf keine gültige Hülle eines gelöschten Items lassen."
    assert isValid(own_item) and isValid(own_editor)
    assert layout.indexOf(own_editor) >= 0
    assert borrowed.parentWidget() is group
    QCoreApplication.sendPostedEvents(borrowed, QEvent.Type.DeferredDelete)
    assert not isValid(borrowed)
    rebuilt = current.measure_fields("resize_hole", None, feature=hole)
    assert rebuilt is not None and rebuilt[1] is group
    assert rebuilt[2]["diameter"] is own_editor
