"""Mauszeiger des Viewports (§19.3, Regel 18).

Ein Zeiger ist Beiwerk — er darf die Anwendung nie aufhalten und nie
verschwinden. Beides wird hier festgehalten, dazu die zwei Eigenschaften, die
man ihm nicht ansieht: der Saum, ohne den er über einem gewählten Körper
unsichtbar wäre, und der Griffpunkt, der beim Messen den Unterschied macht.
"""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QWidget

from app.ui import cursors
from app.ui.theme import THEMES


def test_every_role_yields_a_cursor(qt_app: QApplication) -> None:
    """Jede Rolle liefert einen Zeiger — keine leere Grafik, kein Fehler."""
    widget = QWidget()
    for role in cursors.known():
        found = cursors.cursor(role, widget)
        assert found is not None
        if role in cursors.SHAPES:
            assert not found.pixmap().isNull(), role


def test_an_unknown_role_falls_back_instead_of_failing(qt_app: QApplication) -> None:
    """Ein Zeiger hält die Anwendung nie an. Wer eine Rolle falsch schreibt,
    bekommt den gewöhnlichen Pfeil und keine Ausnahme."""
    widget = QWidget()
    assert cursors.cursor("gibtesnicht", widget).shape() == Qt.CursorShape.ArrowCursor


def test_drawn_shapes_carry_the_accent_and_a_dark_edge() -> None:
    """Der Akzent allein genügt nicht: über einem gewählten Körper liegt er auf
    sich selbst. Jede eigene Zeichnung führt deshalb beide Farben."""
    accent = THEMES["dark"]["highlight"]
    edge = THEMES["dark"]["highlight_text"]
    for role in cursors.SHAPES:
        source = cursors.svg_source(role)
        assert accent in source, role
        assert edge in source, role


def test_the_edge_is_drawn_wider_than_the_accent(qt_app: QApplication) -> None:
    """Der Saum entsteht dadurch, dass er *unter* dem Akzent liegt und breiter
    ist. Wäre er dünner, gäbe es ihn nur auf dem Papier."""
    source = cursors.svg_source("measure")
    edge_width = float(source.split('stroke-width="')[1].split('"')[0])
    accent_width = float(source.split('stroke-width="')[2].split('"')[0])
    assert edge_width > accent_width


def test_the_hotspot_sits_where_the_shape_points(qt_app: QApplication) -> None:
    """Beim Fadenkreuz ist der gemeinte Punkt die Mitte, beim Pfeil die Spitze
    oben links. Ein Zeiger, der danebenliegt, misst falsch."""
    widget = QWidget()
    measure = cursors.cursor("measure", widget)
    select = cursors.cursor("select", widget)

    size = measure.pixmap().deviceIndependentSize()
    middle = measure.hotSpot()
    assert abs(middle.x() - size.width() / 2) <= 1.5
    assert abs(middle.y() - size.height() / 2) <= 1.5

    tip = select.hotSpot()
    assert tip.x() < size.width() / 2
    assert tip.y() < size.height() / 2


def test_the_same_role_is_built_once(qt_app: QApplication) -> None:
    """Der Zeiger wird bei jeder Mausbewegung gesetzt. Ihn dabei neu zu rastern
    wäre die teuerste Zeile der Anwendung."""
    widget = QWidget()
    cursors.forget()
    first = cursors.cursor("rotate", widget)
    second = cursors.cursor("rotate", widget)
    assert first is second


def test_forget_lets_a_theme_change_through(qt_app: QApplication) -> None:
    widget = QWidget()
    before = cursors.cursor("zoom", widget)
    cursors.forget()
    assert cursors.cursor("zoom", widget) is not before


def test_system_shapes_stay_system_shapes(qt_app: QApplication) -> None:
    """Wo das System eine bekannte Form hat, wird sie benutzt: Sie folgt der
    eingestellten Zeigergröße, unsere täte das nicht."""
    widget = QWidget()
    assert cursors.cursor("panning", widget).shape() == Qt.CursorShape.ClosedHandCursor
    assert cursors.cursor("move", widget).shape() == Qt.CursorShape.SizeAllCursor
    for role in cursors.SYSTEM:
        assert role not in cursors.SHAPES, f"{role} wäre zweimal beschrieben"


# --- der Anschluss im Viewport ------------------------------------------------
#
# Offscreen gibt es keinen Plotter; ``_cursor_role`` wird trotzdem gepflegt.
# Das ist Absicht: Was der Zeiger sein *soll*, ist eine Frage des Zustands und
# nicht der Grafikkarte — und nur so lässt es sich ohne Bild prüfen.


def test_the_pointer_says_what_a_click_would_do(qt_app: QApplication) -> None:
    """Pinsel schlägt Messen schlägt Auswahl — dieselbe Reihenfolge, die
    ``_on_picked`` beim echten Klick geht. Wer sie hier anders sortiert, baut
    einen Zeiger, der bei zwei aktiven Werkzeugen das Falsche verspricht."""
    from app.ui.viewport import Viewport

    viewport = Viewport()
    assert viewport._resting_role() == "select"

    viewport.set_measure_mode("points")
    assert viewport._resting_role() == "measure"

    viewport.set_painting(True)
    assert viewport._resting_role() == "paint"


def test_dragging_the_camera_beats_every_other_role(qt_app: QApplication) -> None:
    """Wer dreht, will nicht wissen, was unter dem Zeiger liegt."""
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.set_painting(True)
    viewport.set_drag_cursor("rotate")
    assert viewport._cursor_role == "rotate"


def test_after_the_drag_the_tool_comes_back(qt_app: QApplication) -> None:
    """Der Zeiger nach dem Loslassen ist der des Werkzeugs, nicht der Pfeil.
    Ein Pfad, der pauschal auf „select" zurücksetzt, löscht den Pinsel."""
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport.set_measure_mode("points")
    viewport.set_drag_cursor("panning")
    viewport.set_drag_cursor(None)
    assert viewport._cursor_role == "measure"


def test_leaving_the_view_forgets_the_feature(qt_app: QApplication) -> None:
    """Sonst bliebe der Merkmalszeiger stehen, während die Maus längst im
    Objektbaum ist."""
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport._hover_feature = True
    viewport._update_cursor()
    assert viewport._cursor_role == "feature"

    viewport._forget_pointer()
    assert viewport._cursor_role == "select"


def test_the_hover_search_waits_for_the_mouse_to_stand_still(qt_app: QApplication) -> None:
    """Bei jeder Bewegung zu suchen hieße, den Tiefenpuffer hunderte Male in
    der Sekunde im Hauptthread zu lesen."""
    from app.ui.viewport import HOVER_DELAY_MS, Viewport

    viewport = Viewport()
    assert viewport._hover_timer.isSingleShot()
    assert viewport._hover_timer.interval() == HOVER_DELAY_MS


def test_a_drag_stops_the_hover_search(qt_app: QApplication) -> None:
    """Während eines Zugs ist die Suche nutzlos und teuer."""
    from app.ui.viewport import Viewport

    viewport = Viewport()
    viewport._hover_timer.start()
    viewport.set_drag_cursor("rotate")
    assert not viewport._hover_timer.isActive()


def test_the_cursor_actually_reaches_the_interactor(qt_app: QApplication) -> None:
    """Der Test, ohne den alle anderen nichts wert wären.

    Offscreen ist ``plotter`` None, und jeder Pfad, der den Zeiger setzt, steigt
    vorher aus — die Rollenlogik könnte also vollständig stimmen, während im
    Fenster nie ein Zeiger ankommt. Eine Attrappe mit genau der einen Methode,
    die benutzt wird, schließt die Lücke ohne OpenGL.
    """
    from app.ui.viewport import Viewport

    class FakeInteractor:
        def __init__(self) -> None:
            self.cursors: list[object] = []

        def setCursor(self, cursor: object) -> None:  # noqa: N802 — Qt-Name
            self.cursors.append(cursor)

        def height(self) -> int:
            return 480

    class FakePlotter:
        def __init__(self) -> None:
            self.interactor = FakeInteractor()

    viewport = Viewport()
    plotter = FakePlotter()
    viewport.plotter = plotter

    viewport.set_painting(True)
    assert plotter.interactor.cursors, "der Pinselzeiger kam nie am Fenster an"
    assert viewport._cursor_role == "paint"

    before = len(plotter.interactor.cursors)
    viewport.set_drag_cursor("rotate")
    assert len(plotter.interactor.cursors) == before + 1


def test_the_same_role_twice_does_not_set_it_twice(qt_app: QApplication) -> None:
    """Der Zeiger hängt an der Mausbewegung. Ihn bei jeder erneut zu setzen,
    lässt ihn auf langsamen Treibern flackern."""
    from app.ui.viewport import Viewport

    class FakeInteractor:
        def __init__(self) -> None:
            self.count = 0

        def setCursor(self, cursor: object) -> None:  # noqa: N802 — Qt-Name
            self.count += 1

        def height(self) -> int:
            return 480

    class FakePlotter:
        def __init__(self) -> None:
            self.interactor = FakeInteractor()

    viewport = Viewport()
    viewport.plotter = FakePlotter()

    viewport.set_drag_cursor("rotate")
    viewport.set_drag_cursor("rotate")
    viewport.set_drag_cursor("rotate")
    assert viewport.plotter.interactor.count == 1


def test_the_panels_get_the_same_pointer_as_the_view(qt_app: QApplication) -> None:
    """Sonst stehen zwei Handschriften in einem Fenster: der eigene Zeiger über
    dem Bild, der des Systems daneben."""
    from app.ui.cursors import apply_default_cursor

    window = QWidget()
    child = QWidget(window)
    apply_default_cursor(window)

    assert not window.cursor().pixmap().isNull()
    # Das Kind hat keinen eigenen gesetzt und erbt deshalb — genau darauf
    # beruht der Aufruf auf Fensterebene.
    assert child.cursor().pixmap().cacheKey() == window.cursor().pixmap().cacheKey()


def test_a_text_field_keeps_its_own_pointer(qt_app: QApplication) -> None:
    """Der Textbalken ist eine Auskunft, keine Zierde. Widgets, die ihren
    Zeiger selbst setzen, dürfen von der Vererbung nicht überfahren werden."""
    from PySide6.QtWidgets import QLineEdit

    from app.ui.cursors import apply_default_cursor

    window = QWidget()
    field = QLineEdit(window)
    apply_default_cursor(window)
    assert field.cursor().shape() == Qt.CursorShape.IBeamCursor
