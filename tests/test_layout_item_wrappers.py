"""Wer ein Layout liest, hält keine Hülle eines Elements fest, das Qt später löscht (FD-201).

``itemAt(index)`` hängt die Hülle an die des Layouts. Löscht Qt das Element,
bleibt sie im Hüllenverzeichnis von Shiboken unter freigegebener Adresse; ein
später dort gebauter ``QCompleter`` las sie in ``metaObject()`` und riss den
Prozess ab (Zugriffsverletzung in ``retrieveMetaObject``). Geprüft wird die
Zahl gültiger Elementhüllen, nicht der Abriss: Ob eine neue Allokation die
Adresse trifft, ist Zufall.
"""

from __future__ import annotations

import ast
import gc
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QObject, Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLayoutItem,
    QLineEdit,
    QSizePolicy,
    QSpacerItem,
    QVBoxLayout,
    QWidget,
)
from shiboken6 import Shiboken, isValid

from app.ui.dialog_footer import DialogFooter
from app.ui.layout_lifetime import borrowed_items, layout_parts
from app.ui.style import form_natural_width
from tools.function_capture import layout_entries

ROOT = Path(__file__).resolve().parent.parent


def _item_wrappers() -> int:
    """Gültige Hüllen von Layoutelementen, die keine QObjects sind."""
    gc.collect()
    return sum(
        1
        for wrapper in Shiboken.getAllValidWrappers()
        if isinstance(wrapper, QLayoutItem) and not isinstance(wrapper, QObject)
    )


@pytest.fixture
def host(qt_app: QApplication) -> Iterator[QWidget]:
    """Ein Fenster je Fall, das der Fall auch wieder schließt (FD-191)."""
    widget = QWidget()
    yield widget
    widget.close()
    widget.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def _form(host: QWidget) -> QFormLayout:
    form = QFormLayout(host)
    for index in range(4):
        form.addRow(QLabel(f"Zeile {index}"), QLineEdit())
    return form


@pytest.mark.parametrize(
    "read",
    [form_natural_width, layout_parts, lambda form: layout_entries(form.parentWidget())],
    ids=["form_natural_width", "layout_parts", "layout_entries"],
)
def test_a_removed_row_leaves_no_wrapper_of_its_items(
    qt_app: QApplication, host: QWidget, read: Callable[[QFormLayout], object]
) -> None:
    """Breite messen, dann ``removeRow`` — wie die Mitte der Drehung im Operationsdialog."""
    form = _form(host)
    host.show()
    qt_app.processEvents()
    before = _item_wrappers()
    read(form)
    while form.rowCount():
        form.removeRow(0)
    assert _item_wrappers() == before


def test_a_reflowing_footer_leaves_no_wrapper_of_its_old_buttons(
    qt_app: QApplication, host: QWidget
) -> None:
    """Der Weg aus FD-201: Prüfstand misst den Fuß, der Fuß bricht um und baut sein Layout neu."""
    column = QVBoxLayout(host)
    footer = DialogFooter(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, host
    )
    column.addWidget(footer)
    host.show()
    qt_app.processEvents()
    before = _item_wrappers()
    layout_entries(host)
    footer.setOrientation(Qt.Orientation.Vertical)
    footer.setOrientation(Qt.Orientation.Horizontal)
    assert _item_wrappers() == before


def test_borrowing_keeps_python_spacers_and_inner_layouts(host: QWidget) -> None:
    """Freigegeben wird nur, was beim Lesen entstand — nie ein eigenes Element oder ein Layout."""
    outer = QVBoxLayout(host)
    inner = QVBoxLayout()
    outer.addLayout(inner)
    spacer = QSpacerItem(0, 0, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
    outer.addItem(spacer)
    outer.addWidget(QLineEdit())
    with borrowed_items(outer) as items:
        kinds = [type(item).__name__ for _index, item in items]
    assert kinds == ["QVBoxLayout", "QSpacerItem", "QWidgetItem"]
    assert isValid(inner) and isValid(spacer), "Layout und eigenes Element bleiben gültig"
    spacer.changeSize(0, 12)
    assert [widget is not None for widget, _layout in layout_parts(outer)] == [False, False, True]


def _counted_reads(path: Path) -> list[str]:
    """``itemAt`` mit genau einem Argument, das kein Ort ist — also ein Index."""
    found = []
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if not (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "itemAt"
            and len(node.args) == 1
            and not node.keywords
        ):
            continue
        argument = ast.unparse(node.args[0])
        if any(word in argument for word in ("position", "pos", "Point", "mapFrom")):
            continue
        found.append(f"{path.relative_to(ROOT).as_posix()}:{node.lineno}: {ast.unparse(node)}")
    return found


def test_layouts_are_read_only_through_borrowed_items() -> None:
    """Kein Index-``itemAt`` außerhalb von ``layout_lifetime`` — dort wird die Hülle wieder frei."""
    allowed = ROOT / "app" / "ui" / "layout_lifetime.py"
    found = [
        line
        for folder in ("app", "tools")
        for path in sorted((ROOT / folder).rglob("*.py"))
        if path != allowed
        for line in _counted_reads(path)
    ]
    assert not found, "Layoutelemente über layout_lifetime.borrowed_items lesen:\n" + "\n".join(
        found
    )
    assert _counted_reads(allowed), "die Prüfung sieht die eine erlaubte Stelle"


def test_the_borrowed_reader_is_the_layout_api(host: QWidget) -> None:
    """Gegenprobe der Zählung: ein bloßes ``itemAt`` mit ``removeRow`` hinterlässt Hüllen."""
    form = _form(host)
    known = {id(wrapper) for wrapper in Shiboken.getAllValidWrappers()}
    held = [form.itemAt(index) for index in range(form.count())]
    del held
    while form.rowCount():
        form.removeRow(0)
    orphans = [
        wrapper
        for wrapper in Shiboken.getAllValidWrappers()
        if isinstance(wrapper, QLayoutItem)
        and not isinstance(wrapper, QObject)
        and id(wrapper) not in known
    ]
    try:
        assert orphans, "ohne Freigabe bleiben die Hüllen — sonst misst die Zählung nichts"
    finally:
        # Die Hüllen der eben gelöschten Elemente entwerten, bevor ein späterer
        # Fall an derselben Adresse etwas baut.
        for wrapper in orphans:
            Shiboken.invalidate(wrapper)
        del orphans
