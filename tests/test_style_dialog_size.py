"""Dialoggröße: Anfangsmaß, Wachsen mit nachgereichtem Inhalt, Größe des Kunden.

Die Fälle prüfen ``_content_size_for_intent``, ``ContentHeight`` und
``form_natural_width`` aus ``app/ui/style.py`` an Attrappen, ohne Anwendung und
ohne Fenster. Eigene Datei, weil ``test_style.py`` in der Sperrklinke steht
(Konzept Codestruktur 3.4): Neue Fälle zur Dialoggröße kommen hierher.
"""

from __future__ import annotations

import pytest


def test_dialog_size_decision_follows_the_change_intent() -> None:
    from PySide6.QtCore import QSize

    from app.ui.style import _content_size_for_intent

    current = QSize(700, 420)
    natural = QSize(920, 680)
    assert _content_size_for_intent(
        current, natural, "initial", grow_width=True, natural_width=960
    ) == QSize(960, 680)
    assert _content_size_for_intent(current, natural, "explicit", available_height=250) == QSize(
        700, 250
    )
    # Passiv wächst nur die Höhe, bis zum Bildschirmrand, und nichts schrumpft:
    # nachgereichter Inhalt bekommt Platz, ein kürzerer Status lässt den Rahmen stehen.
    assert _content_size_for_intent(current, natural, "passive") == QSize(700, 680)
    assert _content_size_for_intent(current, natural, "passive", available_height=500) == QSize(
        700, 500
    )
    assert _content_size_for_intent(current, natural, "passive", available_height=400) is None
    assert _content_size_for_intent(current, QSize(920, 300), "passive") is None


def test_screen_fit_does_not_consume_the_initial_content_fit() -> None:
    from PySide6.QtCore import QSize, Qt

    from app.ui.style import ContentHeight

    class Layout:
        def invalidate(self) -> None:
            pass

        def activate(self) -> None:
            pass

    class Scroll:
        def updateGeometry(self) -> None:  # noqa: N802 — Qt-Name
            pass

        def verticalScrollBarPolicy(self) -> Qt.ScrollBarPolicy:  # noqa: N802 — Qt-Name
            return Qt.ScrollBarPolicy.ScrollBarAsNeeded

        def setVerticalScrollBarPolicy(self, _policy: Qt.ScrollBarPolicy) -> None:  # noqa: N802
            pass

        def widget(self) -> None:
            return None

    class Geometry:
        def __init__(self) -> None:
            self._size = QSize(680, 420)

        def isVisible(self) -> bool:  # noqa: N802 — Qt-Name
            return True

        def size(self) -> QSize:
            return QSize(self._size)

        def width(self) -> int:
            return self._size.width()

        def height(self) -> int:
            return self._size.height()

        def sizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
            return QSize(720, 500)

        def screen(self) -> None:
            return None

        def layout(self) -> Layout:
            return Layout()

        def resize(self, width: int, height: int) -> None:
            self._size = QSize(width, height)

    dialog = Geometry()
    scroll = Scroll()
    height = ContentHeight()

    # Frühe passive Messung und der Bildschirmfit setzen fitted, aber noch
    # nicht die natürliche Anfangsmessung.
    height.fit(dialog, scroll, intent="passive")  # type: ignore[arg-type]
    height.fit_to_screen(dialog)  # type: ignore[arg-type]
    assert not height.initial_fit_done
    assert height.fitted == QSize(680, 420)

    height.fit(
        dialog,  # type: ignore[arg-type]
        scroll,  # type: ignore[arg-type]
        grow_width=True,
        intent="initial",
        natural_width=980,
    )
    assert dialog.size() == QSize(980, 500)
    assert height.initial_fit_done

    # Der umgekehrte Ablauf verhindert, dass ein späterer Callback erneut passt.
    height.fit(dialog, scroll, intent="initial")  # type: ignore[arg-type]
    assert dialog.size() == QSize(980, 500)


def test_late_content_grows_an_automatic_dialog_but_never_a_drawn_one() -> None:
    """Nachgereichter Inhalt vergrößert den Rahmen, solange der Kunde nicht zog (RM-487).

    Das Ergebnis einer Hintergrundprüfung kommt als passive Anpassung an. Sie
    blieb ganz im Rollbereich, und der Knopf, den die Prüfung einblendet, lag
    unter dem Rand. Jetzt wächst die Höhe — Breite und Lage bleiben —, ein
    kürzerer Inhalt danach gibt nichts zurück, und eine gezogene Größe bleibt.
    """
    from types import SimpleNamespace

    from PySide6.QtCore import QPoint, QRect, QSize, Qt

    from app.ui.style import ContentHeight

    class Layout:
        def invalidate(self) -> None:
            pass

        def activate(self) -> None:
            pass

    #: Was um den Rollbereich herum steht: Ränder und Knopfleiste.
    chrome = 100

    # Nicht ``Viewport``: Der Name ist ein Fensterbauer der Anwendung, und
    # ``test_the_workflow_finds_every_file_that_builds_a_window`` liest den Aufruf.
    class ScrollViewport:
        def __init__(self, dialog: Dialog) -> None:
            self.dialog = dialog

        def width(self) -> int:
            return self.dialog.size().width()

        def height(self) -> int:
            return self.dialog.size().height() - chrome

    class Content:
        def __init__(self, dialog: Dialog) -> None:
            self.dialog = dialog

        def layout(self) -> None:
            return None

        def width(self) -> int:
            return self.dialog.size().width()

        def sizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
            return self.dialog.natural - QSize(0, chrome)

        def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
            return QSize(0, 0)

    class Scroll:
        def __init__(self, dialog: Dialog) -> None:
            self._viewport = ScrollViewport(dialog)
            self._content = Content(dialog)

        def updateGeometry(self) -> None:  # noqa: N802 — Qt-Name
            pass

        def verticalScrollBarPolicy(self) -> Qt.ScrollBarPolicy:  # noqa: N802 — Qt-Name
            return Qt.ScrollBarPolicy.ScrollBarAsNeeded

        def setVerticalScrollBarPolicy(self, _policy: Qt.ScrollBarPolicy) -> None:  # noqa: N802
            pass

        def widget(self) -> Content:
            return self._content

        def viewport(self) -> ScrollViewport:
            return self._viewport

        def horizontalScrollBar(self) -> SimpleNamespace:  # noqa: N802 — Qt-Name
            return SimpleNamespace(minimum=lambda: 0, maximum=lambda: 0)

        def horizontalScrollBarPolicy(self) -> Qt.ScrollBarPolicy:  # noqa: N802 — Qt-Name
            return Qt.ScrollBarPolicy.ScrollBarAsNeeded

        def maximumViewportSize(self) -> QSize:  # noqa: N802 — Qt-Name
            return QSize(self._viewport.width(), self._viewport.height())

    class Dialog:
        def __init__(self) -> None:
            self._size = QSize(680, 420)
            self.natural = QSize(680, 420)
            self.moves: list[QPoint] = []

        def isVisible(self) -> bool:  # noqa: N802 — Qt-Name
            return True

        def size(self) -> QSize:
            return QSize(self._size)

        def width(self) -> int:
            return self._size.width()

        def height(self) -> int:
            return self._size.height()

        def sizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
            return QSize(self.natural)

        def frameGeometry(self) -> QRect:  # noqa: N802 — Qt-Name
            return QRect(QPoint(40, 30), self._size)

        def move(self, point: QPoint) -> None:
            self.moves.append(point)

        def screen(self) -> None:
            return None

        def layout(self) -> Layout:
            return Layout()

        def resize(self, width: int, height: int) -> None:
            self._size = QSize(width, height)

    dialog = Dialog()
    scroll = Scroll(dialog)
    height = ContentHeight()

    dialog.natural = QSize(720, 480)
    height.fit(dialog, scroll, intent="passive")  # type: ignore[arg-type]
    assert dialog.size() == QSize(680, 420), "vor der Anfangsmessung misst nur ``initial``"

    height.fit(dialog, scroll, grow_width=True, intent="initial")  # type: ignore[arg-type]
    assert dialog.size() == QSize(720, 480)

    dialog.natural = QSize(900, 536)
    height.fit(dialog, scroll, intent="passive")  # type: ignore[arg-type]
    assert dialog.size() == QSize(720, 536), "die Höhe wächst mit, die Breite bleibt"
    assert height.user is None, "das eigene Wachsen ist kein Zug des Kunden"

    dialog.natural = QSize(720, 300)
    height.fit(dialog, scroll, intent="passive")  # type: ignore[arg-type]
    assert dialog.size() == QSize(720, 536), "ein kürzerer Inhalt lässt den Rahmen stehen"

    dialog.resize(720, 400)  # der Kunde zieht
    dialog.natural = QSize(720, 700)
    height.fit(dialog, scroll, intent="passive")  # type: ignore[arg-type]
    assert dialog.size() == QSize(720, 400), "die gezogene Größe gehört dem Kunden"
    assert height.user == QSize(720, 400)
    assert dialog.moves == []


def test_first_run_initial_width_after_screen_fit_is_not_treated_as_user_size() -> None:
    from PySide6.QtCore import QSize, Qt

    from app.ui.first_run import FirstRunDialog
    from app.ui.style import ContentHeight

    class Layout:
        def invalidate(self) -> None:
            pass

        def activate(self) -> None:
            pass

    class Content:
        def layout(self) -> Layout:
            return Layout()

        def findChildren(self, _kind: type) -> list[object]:  # noqa: N802 — Qt-Name
            return []

    class Scroll:
        def updateGeometry(self) -> None:  # noqa: N802 — Qt-Name
            pass

        def verticalScrollBarPolicy(self) -> Qt.ScrollBarPolicy:  # noqa: N802 — Qt-Name
            return Qt.ScrollBarPolicy.ScrollBarAsNeeded

        def setVerticalScrollBarPolicy(self, _policy: Qt.ScrollBarPolicy) -> None:  # noqa: N802
            pass

        def widget(self) -> None:
            return None

    class PrinterForm:
        def layout(self) -> None:
            return None

        def parentWidget(self) -> None:  # noqa: N802 — Qt-Name
            return None

    class Dialog:
        def __init__(self) -> None:
            self._size = QSize(680, 400)
            self._height = ContentHeight()
            self._height.fitted = QSize(self._size)
            self._contents = Content()
            self._scroll = Scroll()
            self.custom_printer = PrinterForm()

        def isVisible(self) -> bool:  # noqa: N802 — Qt-Name
            return True

        def layout(self) -> Layout:
            return Layout()

        def sizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
            return QSize(980, 620)

        def minimumWidth(self) -> int:  # noqa: N802 — Qt-Name
            return 0

        def _natural_width(self) -> int:
            return FirstRunDialog._natural_width(self)  # type: ignore[arg-type]

        def width(self) -> int:
            return self._size.width()

        def height(self) -> int:
            return self._size.height()

        def resize(self, width: int, height: int) -> None:
            self._size = QSize(width, height)

        def screen(self) -> None:
            return None

        def size(self) -> QSize:
            return QSize(self._size)

    dialog = Dialog()

    FirstRunDialog._grow_to_content(dialog, "initial")  # type: ignore[arg-type]

    assert dialog.size() == QSize(980, 620)
    assert dialog._height.user is None
    assert dialog._height.initial_fit_done


def test_natural_form_width_counts_each_hidden_and_spanning_item_once() -> None:
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QFormLayout

    from app.ui.style import form_natural_width

    class Margins:
        def left(self) -> int:
            return 2

        def right(self) -> int:
            return 3

    class Widget:
        def __init__(self, width: int, minimum_width: int) -> None:
            self.width = width
            self.minimum_width = minimum_width

        def sizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
            return QSize(self.width, 1)

        def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
            return QSize(0, 1)

        def minimumSize(self) -> QSize:  # noqa: N802 — Qt-Name
            return QSize(self.minimum_width, 1)

    class Layout:
        def sizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
            return QSize(210, 1)

        def minimumSize(self) -> QSize:  # noqa: N802 — Qt-Name
            return QSize(230, 1)

    class Item:
        def __init__(
            self,
            width: int,
            widget: Widget | None = None,
            layout: Layout | None = None,
        ) -> None:
            self.width = width
            self._widget = widget
            self._layout = layout

        def sizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
            return QSize(self.width, 1)

        def minimumSize(self) -> QSize:  # noqa: N802 — Qt-Name
            return QSize(0, 1)

        def widget(self) -> Widget | None:
            return self._widget

        def layout(self) -> Layout | None:
            return self._layout

    class Form:
        def __init__(self) -> None:
            self.items = [
                (0, QFormLayout.ItemRole.LabelRole, Item(40)),
                (0, QFormLayout.ItemRole.FieldRole, Item(100)),
                # Verborgene Widget-Items melden leer, das Widget behält seine
                # natürliche und festgelegte Mindestbreite.
                (1, QFormLayout.ItemRole.FieldRole, Item(0, Widget(200, 220))),
                # Die SpanningRole-Zelle liegt im Feldspeicher; eine Abfrage
                # ihrer Zeile als FieldRole liefert deshalb dasselbe Element.
                (2, QFormLayout.ItemRole.SpanningRole, Item(0, layout=Layout())),
            ]

        def contentsMargins(self) -> Margins:  # noqa: N802 — Qt-Name
            return Margins()

        def count(self) -> int:
            return len(self.items)

        def itemAt(  # noqa: N802 — Qt-Name
            self, index: int, role: QFormLayout.ItemRole | None = None
        ) -> Item | None:
            if role is None:
                return self.items[index][2]
            for row, item_role, item in self.items:
                if row == index and (
                    item_role == role
                    or (
                        role == QFormLayout.ItemRole.FieldRole
                        and item_role == QFormLayout.ItemRole.SpanningRole
                    )
                ):
                    return item
            return None

        def getItemPosition(self, index: int) -> tuple[int, QFormLayout.ItemRole]:  # noqa: N802
            row, role, _item = self.items[index]
            return row, role

        def horizontalSpacing(self) -> int:  # noqa: N802 — Qt-Name
            return 8

        def spacing(self) -> int:
            return -1

    assert form_natural_width(Form()) == 273  # type: ignore[arg-type]


@pytest.mark.parametrize("chosen", [(630, 420), (700, 360)])
def test_dialog_keeps_a_manually_chosen_width_and_height(chosen: tuple[int, int]) -> None:
    from PySide6.QtCore import QSize

    from app.ui.style import ContentHeight

    class Geometry:
        def __init__(self) -> None:
            self.resize_calls = 0

        def isVisible(self) -> bool:  # noqa: N802 — Qt-Name
            return True

        def size(self) -> QSize:
            return QSize(*chosen)

        def resize(self, _width: int, _height: int) -> None:
            self.resize_calls += 1

    dialog = Geometry()
    height = ContentHeight()
    height.fitted = QSize(700, 420)

    assert height.floor(dialog) == chosen[1]
    height.settle(dialog, 940, 760, intent="explicit")

    assert height.user == QSize(*chosen)
    assert height.fitted == QSize(*chosen)
    assert dialog.resize_calls == 0
