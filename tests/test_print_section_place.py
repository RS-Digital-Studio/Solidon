"""„Filament und Druck“ steht oben in der Auswahlkarte, mit der Farbe der Zuweisung (FD-19).

Die Klappe lag zugeklappt am Ende der längsten Liste der Karte: Bei gewähltem
Körper unter rund vierzig Handlungen, erst nach Rollen und Aufklappen. Sie
steht jetzt als Zeile direkt unter den Hauptaktionen, vor Suche und Liste,
und trägt, wo ein Filament zugewiesen ist, sein Farbfeld vor dem Namen.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QToolButton

from app.core.knowledge import filaments
from app.core.registry import REGISTRY
from app.core.types import MaterialSlot, SceneObject
from app.ui.filament_assignment import QuickFilamentPicker
from app.ui.selection_operations import SelectionOperationsPanel


def _body(slots: list[MaterialSlot]) -> SceneObject:
    import trimesh

    from app.core.geom.mesh import MeshData

    return SceneObject(
        id="part",
        name="Teil",
        mesh=MeshData.of(trimesh.creation.box(), slots=((slots[0].index,) * 12) if slots else ()),
        material_slots=slots,
    )


@pytest.fixture
def panel(qt_app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    built = SelectionOperationsPanel(REGISTRY.all())
    picker = QuickFilamentPicker()
    picker.described.connect(built.describe_print)
    built.add_print_widget(picker)
    yield built, picker
    built.deleteLater()


def test_the_print_section_stands_above_search_and_list(panel) -> None:
    built, _picker = panel
    layout = built.layout()
    assert layout.indexOf(built.print_section) < layout.indexOf(built.search), (
        "„Filament und Druck“ steht hinter Suche und Liste"
    )
    assert layout.indexOf(built.print_section) < layout.indexOf(built.scroller)


def test_an_assigned_filament_shows_its_colour_in_the_heading(panel) -> None:
    built, picker = panel
    heading = built.print_section.findChild(QToolButton, "sectionHeading")
    assert heading is not None
    picker.set_context([_body([MaterialSlot(index=1, name="Rot", colour=(1.0, 0.0, 0.0))])])
    assert not heading.icon().isNull(), "die Zuweisung trägt ihr Farbfeld"
    picker.set_context([_body([])])
    assert heading.icon().isNull(), "ohne Zuweisung kein Farbfeld"
