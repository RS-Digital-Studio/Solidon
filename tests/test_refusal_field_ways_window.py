"""Ein Feldweg in einer Absage steht nur, wo er landet, und verbreitert nichts (FD-182).

*Objekt umbenennen* bot auf eine Ebenenabsage „Eine andere Ebene wählen“ als
Knopf an, obwohl der Dialog kein Ebenenfeld hat: Der Knopf tat nichts und
drückte den Dialog bei 18 Punkt auf 602 Bildpunkte, mit Rollbalken. Geprüft
wird hier der Wächter über jeden Operationsdialog, der echte Weg über
``ErrorNotice`` und der Knopf, der umbricht statt zu verbreitern.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QPushButton, QWidget

from app.core.bootstrap import load_operations
from app.core.errors import CORRECT_INPUT, FIELD_WAYS, PICK_PLANE, ValidationError
from app.core.registry import REGISTRY
from app.core.sketch.planes import frame_for_sketch
from app.i18n import set_language
from app.i18n.catalog import install_language
from app.ui.op_dialog import _SEAL_PATH_COMPANIONS, OperationDialog
from app.ui.refusal_details import QUIET_WITHOUT_FIELD, field_ways, silent_ways
from app.ui.style import apply_style
from app.ui.theme import apply_theme
from app.ui.wrapping_button import WrappingButton
from tests.bundled_fonts import bundled_font
from tests.plane_refusals import sketch_plane_refusal

#: Ein Feldname, den kein Dialog führt.
NO_SUCH_FIELD = "no_such_field"


def _settle(application: QApplication) -> None:
    for _ in range(16):
        application.processEvents()


def _plane_error() -> ValidationError:
    """Die echte Ebenenabsage aus dem Fund, keine Attrappe."""
    with pytest.raises(ValidationError) as caught:
        frame_for_sketch("through:0,0,20;10,0,20;20,0,20")
    return caught.value


def _sketch_error() -> ValidationError:
    """Dieselbe Absage, wie eine Skizzenoperation sie wirft."""
    return sketch_plane_refusal("through:0,0,20;10,0,20;20,0,20")


def _way_buttons(dialog: OperationDialog) -> list[QPushButton]:
    labels = {str(CORRECT_INPUT.label), str(PICK_PLANE.label)}
    return [
        button
        for button in dialog._refusal.findChildren(QPushButton)
        if button.text() in labels and not button.isHidden()
    ]


@pytest.fixture
def german(qt_app: QApplication) -> Iterator[QApplication]:
    load_operations()
    install_language("de")
    set_language("de")
    apply_theme(qt_app, "light")
    previous = QFont(qt_app.font())
    yield qt_app
    qt_app.setFont(previous)
    apply_style(qt_app, "light")


def _inside(widget: QWidget | None, editor: QWidget) -> bool:
    while widget is not None:
        if widget is editor:
            return True
        widget = widget.parentWidget()
    return False


def test_every_field_way_of_every_dialog_lands_in_its_field(german: QApplication) -> None:
    """Je Operationsdialog und je Feldname: Knopf und Sprung, oder kein Knopf.

    Ohne Feld fällt *Eingabe korrigieren* weg (die Eingabe steht darüber),
    *Eine andere Ebene wählen* bleibt als Rat im Text.

    Gefragt wird jedes Feld des Schemas, dazu ``plane`` (der Name der echten
    Ebenenabsage) und ein Name, den kein Dialog führt.
    """
    dead: list[str] = []
    for spec in REGISTRY.all():
        dialog = OperationDialog(spec, {})
        try:
            dialog.show()
            names = [entry.name for entry in spec.params.spec()] + ["plane", NO_SUCH_FIELD]
            for field in dict.fromkeys(names):
                error = ValidationError(field, "Absage", suggestions=[CORRECT_INPUT, PICK_PLANE])
                ways = field_ways(error, dialog)
                silent = silent_ways(error, dialog)
                if not ways:
                    if silent != QUIET_WITHOUT_FIELD:
                        dead.append(f"{spec.name}.{field}: Satz ohne Feld")
                    continue
                if set(ways) != FIELD_WAYS or silent:
                    dead.append(f"{spec.name}.{field}: {sorted(ways)} / {sorted(silent)}")
                    continue
                before = dialog.focusWidget()
                if before is not None:
                    before.clearFocus()
                ways[CORRECT_INPUT.id](error)
                target = (
                    "path_sketch"
                    if spec.name == "create_seal" and field in _SEAL_PATH_COMPANIONS
                    else field
                )
                editor = dialog._editors.get(target)
                if editor is None or not _inside(dialog.focusWidget(), editor):
                    dead.append(f"{spec.name}.{field}: Knopf ohne Sprung")
        finally:
            dialog.close()
            dialog.deleteLater()
    assert not dead, "\n".join(dead)


def test_rename_offers_no_plane_button_and_the_sketch_dialog_does(german: QApplication) -> None:
    """Der Fund am echten Weg: die Ebenenabsage im Umbenennen und am Skizzenschritt."""
    error = _plane_error()
    assert error.values.get("field") == "plane"
    drawn = _sketch_error()
    rename = OperationDialog(REGISTRY.get("rename_object"), {"body": "Körper"})
    sketch = OperationDialog(REGISTRY.get("sketch_pocket"), {"body": "Körper"})
    try:
        for dialog, refusal in ((rename, error), (sketch, drawn)):
            dialog.show()
            _settle(german)
            dialog.show_refusal(refusal)
            _settle(german)
        assert _way_buttons(rename) == []
        # Kein Knopf ins Leere, aber der Rat bleibt (Regel 17).
        assert str(PICK_PLANE.label) in rename._refusal.text().splitlines()
        assert str(CORRECT_INPUT.label) not in rename._refusal.text()
        offered = _way_buttons(sketch)
        assert [button.text() for button in offered] == [str(PICK_PLANE.label)]
        offered[0].click()
        _settle(german)
        assert _inside(sketch.focusWidget(), sketch._editors["sketch"])
    finally:
        for dialog in (rename, sketch):
            dialog.close()
            dialog.deleteLater()


def test_a_long_way_wraps_instead_of_widening_the_dialog(german: QApplication) -> None:
    """Wird die Schrift im gezogenen *Objekt umbenennen* groß, bricht ein langer Feldweg um.

    Der Ablauf des Funds: bei 11 Punkt geöffnet und gezogen, die Absage kommt,
    dann 18 Punkt. Der Weg führt hier ins Namensfeld, damit der Dialog ihn
    anbietet; die Beschriftung ist die lange aus dem Fund.

    Gemessen mit der Prüfschrift, und ab 18 Punkt so weit größer, bis der Knopf in einer
    Zeile nicht mehr passt: Mit DejaVu Sans passte er bei 18 Punkt noch (Linux-Läufer,
    Fensterauswahl 39035816730), und die Voraussetzung hing an der Schrift der Plattform.
    """
    with bundled_font(german, 11) as font:
        apply_style(german, "light")
        dialog = OperationDialog(REGISTRY.get("rename_object"), {"body": "Körper"})
        try:
            _wrap_the_long_way(german, font, dialog)
        finally:
            dialog.close()
            dialog.deleteLater()


def _wrap_the_long_way(german: QApplication, font: QFont, dialog: OperationDialog) -> None:
    """Der Ablauf von :func:`test_a_long_way_wraps_instead_of_widening_the_dialog`."""
    dialog.show()
    _settle(german)
    dialog.resize(dialog.width(), dialog.height() + 20)
    _settle(german)
    chosen = dialog.width()
    dialog.show_refusal(ValidationError("name", "Absage", suggestions=[PICK_PLANE]))
    _settle(german)
    for points in range(18, 41, 2):
        font.setPointSize(points)
        german.setFont(font)
        apply_style(german, "light")
        _settle(german)
        (offered,) = _way_buttons(dialog)
        one_line = offered.sizeHint().width()
        if chosen < one_line:
            break
    assert chosen < one_line, "Voraussetzung: einzeilig passt der Knopf nicht"
    assert dialog.width() == chosen, "die Absage verbreitert den Dialog nicht"
    assert offered.width() < one_line, "die Beschriftung bricht um"
    assert offered.height() >= offered.heightForWidth(offered.width()), "jede Zeile steht da"
    assert offered.height() > offered.sizeHint().height()
    assert dialog._scroll.horizontalScrollBar().maximum() == 0


def test_the_button_is_as_narrow_as_its_longest_word(german: QApplication) -> None:
    """Mindestbreite ist das längste Wort; die Höhe folgt der Breite, ``text()`` bleibt ganz."""
    button = WrappingButton("Eine andere Ebene wählen")
    try:
        whole = button.sizeHint()
        least = button.minimumSizeHint()
        assert button.text() == "Eine andere Ebene wählen"
        assert least.width() < whole.width()
        assert button.heightForWidth(whole.width()) == whole.height()
        assert button.heightForWidth(least.width()) > whole.height()
        assert least.height() == button.heightForWidth(least.width())
        button.resize(least)
        button.show()
        _settle(german)
        assert not button.grab().isNull()
    finally:
        button.close()
        button.deleteLater()
