"""Ein Rollbereich ist kein namenloser Tab-Halt (FD-139).

Qts ``QScrollArea`` nimmt in der Vorgabe den Fokus selbst. Der
Funktionsdurchgang maß deshalb Ketten, die an „DialogScrollArea“ begannen und
endeten (*Parameter anlegen …*) oder an „FittedScroller“ (Prüfbericht) — ein
Halt, den ein Bildschirmleser mit dem Klassennamen ansagt. Ein reiner Behälter
ist jetzt kein Halt mehr, ein Lesebereich trägt Namen und Beschreibung
(``app/ui/scroll_areas.py``).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QScrollArea, QWidget

from app.ui.dialogs import ParameterDialog
from app.ui.overlay import ContentScroller, FittedScroller
from app.ui.panels import ColumnScroller, SelectionScroller
from app.ui.scroll_areas import PassingScrollArea, ReadingScrollArea
from app.ui.style import DialogScrollArea

UI = Path(__file__).resolve().parent.parent / "app" / "ui"

#: Das Modul, das als einziges ``QScrollArea`` selbst ableitet.
HOME = UI / "scroll_areas.py"

#: Dateien eines anderen Fixpakets, deren Wechsel dort ansteht. Der Eintrag
#: fällt, sobald die Datei keinen nackten Rollbereich mehr baut — der Test
#: verlangt es.
PENDING: dict[str, str] = {}


def _bare_scroll_areas(path: Path) -> list[str]:
    """Wo eine Datei ``QScrollArea`` selbst baut oder ableitet — Zeile und Art."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _names_scroll_area(node.func):
            found.append(f"{path.name}:{node.lineno} baut QScrollArea")
        if isinstance(node, ast.ClassDef) and any(_names_scroll_area(base) for base in node.bases):
            found.append(f"{path.name}:{node.lineno} leitet {node.name} von QScrollArea ab")
    return found


def _names_scroll_area(node: ast.expr) -> bool:
    return (isinstance(node, ast.Name) and node.id == "QScrollArea") or (
        isinstance(node, ast.Attribute) and node.attr == "QScrollArea"
    )


def test_no_file_of_the_interface_builds_a_bare_scroll_area() -> None:
    """Jeder Rollbereich ist einer der zwei aus ``scroll_areas`` — kein dritter mit Qts Vorgabe."""
    found = {
        path.name: places
        for path in sorted(UI.rglob("*.py"))
        if path != HOME and (places := _bare_scroll_areas(path))
    }
    waiting = {name: found.pop(name, []) for name in PENDING}
    assert not found, found
    # Steht der Wechsel an, muss er auch noch fehlen — sonst fällt der Eintrag.
    assert all(waiting.values()), f"erledigt, aus PENDING streichen: {waiting}"


def test_the_detector_sees_both_ways_of_building_one() -> None:
    """Gegenprobe: Bau und Ableitung, auch über das Modul, fallen auf."""
    tree = ast.parse(
        "import PySide6.QtWidgets as w\n"
        "class Area(w.QScrollArea):\n    pass\n"
        "area = QScrollArea(None)\n"
    )
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    assert any(_names_scroll_area(call.func) for call in calls)
    assert any(_names_scroll_area(base) for cls in classes for base in cls.bases)


@pytest.mark.parametrize(
    "kind", [DialogScrollArea, FittedScroller, ContentScroller, ColumnScroller, SelectionScroller]
)
def test_every_container_scroller_passes_the_focus_on(
    qt_app: QApplication, kind: type[QScrollArea]
) -> None:
    """Die Rollbehälter der Karten und Dialoge sind keine Halte."""
    assert issubclass(kind, PassingScrollArea)
    area = kind(QWidget()) if kind is FittedScroller else kind()
    assert area.focusPolicy() == Qt.FocusPolicy.NoFocus
    area.deleteLater()


def test_a_reading_area_stays_a_stop_and_says_what_it_holds(qt_app: QApplication) -> None:
    area = ReadingScrollArea("Neuerungen", "Mit Pfeil- und Bildtasten blättern.")
    assert area.focusPolicy() == Qt.FocusPolicy.StrongFocus
    assert area.accessibleName() == "Neuerungen"
    assert area.accessibleDescription()
    area.deleteLater()


def test_tab_in_a_dialog_never_stops_at_its_scroll_area(qt_app: QApplication) -> None:
    """*Parameter anlegen …*: Die Kette läuft durch die Felder, nicht über den Rollbereich."""
    dialog = ParameterDialog({})
    dialog.show()
    dialog.activateWindow()
    QApplication.processEvents()
    first = dialog.focusWidget() or dialog
    first.setFocus(Qt.FocusReason.TabFocusReason)
    QApplication.processEvents()
    chain: list[QWidget] = []
    for _press in range(30):
        focused = QApplication.focusWidget()
        if focused is None or focused in chain:
            break
        chain.append(focused)
        QTest.keyClick(focused, Qt.Key.Key_Tab)
        QApplication.processEvents()
    stops = [type(widget).__name__ for widget in chain if isinstance(widget, QScrollArea)]
    dialog.reject()
    dialog.deleteLater()
    assert len(chain) > 2, chain
    assert not stops, f"Rollbereich als Tab-Halt: {stops}"
