"""Das Trennwerkzeug am laufenden Fenster (Bauplan §25, §2.4).

Bedient wird über dieselben Wege, die eine Maus nimmt: der Umschalter der
Werkzeugzeile, dann die Punkte, die der Viewport meldet. Geprüft wird, was ein
Nutzer sieht und was danach im Dokument steht — nicht, ob eine Methode
aufgerufen wurde.

Der Viewport hat offscreen keinen Plotter. Das ist hier kein Mangel: Er meldet
Punkte über ein Signal, und das Signal von Hand auszulösen ist genau der Weg,
den ein Klick nimmt.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core.geom.section import plane_through
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from app.ui.split_bar import POINTS_NEEDED, SplitBar, state_text

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def session(qt_app: QApplication) -> Session:
    return Session()


@pytest.fixture
def window(qt_app: QApplication, session: Session) -> MainWindow:
    return MainWindow(session, UiSettings())


def with_a_cube(window: MainWindow) -> str:
    """Ein 20er-Würfel um den Ursprung, ausgewertet und im Baum."""
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    return "obj_1"


# --- die Leiste allein --------------------------------------------------------------


def test_the_bar_says_what_the_next_click_does(qt_app: QApplication) -> None:
    """Drei Zustände, drei Sätze. Ein Werkzeug, dessen erster Schritt geraten
    werden muss, ist eines zu viel."""
    assert state_text(0) != state_text(1) != state_text(POINTS_NEEDED)
    assert state_text(0) != state_text(POINTS_NEEDED)


def test_the_button_waits_for_a_finished_line(qt_app: QApplication) -> None:
    """Ein Knopf, der nichts tun kann, ist aus — und wird an, sobald er kann."""
    bar = SplitBar()

    assert not bar.apply.isEnabled(), "ohne Linie gibt es nichts zu trennen"
    assert not bar.clear.isEnabled(), "und nichts zu löschen"

    bar.show_points(1)
    assert not bar.apply.isEnabled()
    assert bar.clear.isEnabled(), "ein halber Anfang lässt sich verwerfen"

    bar.show_points(POINTS_NEEDED)
    assert bar.apply.isEnabled()


def test_the_pin_count_goes_with_its_checkbox(qt_app: QApplication) -> None:
    """Eine Zahl ohne die Sache, zu der sie gehört, ist eine Frage ohne Anlass."""
    bar = SplitBar()
    bar.show()

    bar.connect_halves.setChecked(False)
    assert not bar.count.isVisible()
    assert bar.values() == {"pins": 0}

    bar.connect_halves.setChecked(True)
    assert bar.count.isVisible()
    assert bar.values()["pins"] == bar.count.value()


def test_the_connection_is_preselected(qt_app: QApplication) -> None:
    """Die Arbeit, die dieses Werkzeug abnimmt, ist das Ausrichten beim
    Kleben. Sie erst suchen zu müssen wäre ein Handgriff zu viel."""
    assert SplitBar().values()["pins"] > 0


class FakeInteractor:
    """Nur das, was der Zeigerpfad des Viewports wirklich ruft."""

    def setCursor(self, cursor: object) -> None:  # noqa: N802 — Qt-Name
        pass

    def height(self) -> int:
        return 480


# --- was im Bild ankommt --------------------------------------------------------------


def test_the_drawn_line_really_reaches_the_view(qt_app: QApplication) -> None:
    """Offscreen gibt es keinen Plotter, und ``show_split_line`` steigt vorher
    aus.

    Ein Test, der nur ``window._split_points`` prüft, wäre also auch dann grün,
    wenn im Fenster nie ein Strich erschiene. Eine Attrappe mit genau den drei
    Methoden, die benutzt werden, schließt die Lücke ohne OpenGL — dieselbe
    Bauart wie in ``tests/test_cursors.py``.
    """
    from app.ui.viewport import Viewport

    class FakePlotter:
        def __init__(self) -> None:
            self.points: list[object] = []
            self.lines: list[object] = []
            self.removed: list[object] = []
            # Der Zeiger hängt am selben Plotter; ohne ihn scheitert der Test
            # an einer Stelle, um die es nicht geht.
            self.interactor = FakeInteractor()

        def add_points(self, marks: object, **_values: object) -> str:
            self.points.append(marks)
            return f"points:{len(self.points)}"

        def add_lines(self, marks: object, **_values: object) -> str:
            self.lines.append(marks)
            return f"lines:{len(self.lines)}"

        def remove_actor(self, actor: object, **_values: object) -> None:
            self.removed.append(actor)

        def render(self) -> None:
            pass

    viewport = Viewport()
    plotter = FakePlotter()
    viewport.plotter = plotter

    viewport.show_split_line([(0.0, 0.0, 0.0)])
    assert len(plotter.points) == 1, "der erste Punkt bekommt ein Zeichen"
    assert not plotter.lines, "eine Linie ist er noch nicht"

    viewport.show_split_line([(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)])
    assert len(plotter.lines) == 1, "zwei Punkte sind eine Linie"

    # Gezählt wird der Zuwachs, nicht der Bestand: Das Neuzeichnen räumt selbst
    # auf, der erste Punkt ist also längst wieder heraus.
    before = len(plotter.removed)
    viewport.clear_split_line()
    assert len(plotter.removed) - before == 2, "Zeichen und Linie gehen wieder heraus"


def test_leaving_the_tool_takes_the_line_out_of_the_view(qt_app: QApplication) -> None:
    """Regel 2: Was das Fenster währenddessen zeigt, ist eine Vorschau."""
    from app.ui.viewport import Viewport

    class FakePlotter:
        def __init__(self) -> None:
            self.removed: list[object] = []
            self.interactor = FakeInteractor()

        def add_points(self, _marks: object, **_values: object) -> str:
            return "points"

        def add_lines(self, _marks: object, **_values: object) -> str:
            return "lines"

        def remove_actor(self, actor: object, **_values: object) -> None:
            self.removed.append(actor)

        def render(self) -> None:
            pass

    viewport = Viewport()
    plotter = FakePlotter()
    viewport.plotter = plotter
    viewport.set_splitting(True)
    viewport.show_split_line([(0.0, 0.0, 0.0), (10.0, 0.0, 0.0)])

    viewport.set_splitting(False)

    assert plotter.removed, "der Strich blieb stehen, nachdem das Werkzeug zu war"


# --- das Werkzeug im Fenster ----------------------------------------------------------


def test_the_strip_offers_the_tool(window: MainWindow) -> None:
    assert "split" in window.tools.tools()
    assert str(window.tools.tools()["split"].title)


def test_opening_the_tool_turns_clicks_into_line_ends(window: MainWindow) -> None:
    """Der Umschalter steuert den Viewport — an der Leiste vorbei gäbe es zwei
    Stellen für denselben Zustand."""
    window.tools.activate("split")
    assert window.viewport._splitting is True

    window.tools.activate(None)
    assert window.viewport._splitting is False


def test_two_clicks_make_a_line_and_a_third_starts_over(window: MainWindow) -> None:
    """Wer nach zwei Punkten noch einmal klickt, hat sich vertan — und soll
    dafür keinen Knopf suchen müssen."""
    with_a_cube(window)
    window.tools.activate("split")

    window.viewport.splitPointRequested.emit((-10.0, 0.0, 0.0))
    assert len(window._split_points) == 1
    window.viewport.splitPointRequested.emit((10.0, 0.0, 0.0))
    assert len(window._split_points) == POINTS_NEEDED
    assert window.split_bar.apply.isEnabled()

    window.viewport.splitPointRequested.emit((0.0, 5.0, 0.0))
    assert len(window._split_points) == 1, "der dritte Klick fängt von vorn an"


def test_a_click_beside_the_model_says_so_instead_of_starting_a_line(
    window: MainWindow,
) -> None:
    """Regel 17 im Kleinen: nicht stumm nichts tun, sondern sagen, was fehlt."""
    with_a_cube(window)
    window.tools.activate("split")

    window.viewport.splitPointRequested.emit((500.0, 500.0, 500.0))

    assert window._split_points == []
    assert window._split_target is None
    assert not window.split_bar.apply.isEnabled()


def test_a_click_beside_the_model_takes_the_old_line_with_it(window: MainWindow) -> None:
    """Sonst bleibt ein Strich stehen, dessen Knopf nichts mehr tut.

    Der dritte Klick fängt von vorn an — trifft er daneben, gibt es keinen
    neuen Anfang, und der alte darf nicht so aussehen, als gäbe es ihn noch.
    """
    with_a_cube(window)
    window.tools.activate("split")
    window.viewport.splitPointRequested.emit((-10.0, 0.0, 0.0))
    window.viewport.splitPointRequested.emit((10.0, 0.0, 0.0))
    assert window.split_bar.apply.isEnabled()

    window.viewport.splitPointRequested.emit((500.0, 500.0, 500.0))

    assert window._split_points == []
    assert not window.split_bar.apply.isEnabled()
    assert not window.split_bar.clear.isEnabled()


def test_closing_the_tool_forgets_the_line(window: MainWindow) -> None:
    """Die Linie ist eine Vorschau, kein Dokumentzustand (Regel 2)."""
    with_a_cube(window)
    window.tools.activate("split")
    window.viewport.splitPointRequested.emit((-10.0, 0.0, 0.0))

    window.tools.activate(None)

    assert window._split_points == []
    assert not window.split_bar.clear.isEnabled()


def test_clearing_the_line_needs_no_undo(window: MainWindow) -> None:
    """Nichts wurde geändert, also gibt es nichts zurückzunehmen — und keinen
    Bestätigungsdialog davor (Regel 19)."""
    with_a_cube(window)
    window.tools.activate("split")
    window.viewport.splitPointRequested.emit((-10.0, 0.0, 0.0))
    window.viewport.splitPointRequested.emit((10.0, 0.0, 0.0))

    window.split_bar.clearRequested.emit()

    assert window._split_points == []
    assert window.session.project.document.ops == [
        entry for entry in window.session.project.document.ops if entry.op == "load"
    ]


def test_a_changed_document_drops_the_line(window: MainWindow) -> None:
    """Zwei Punkte im Leeren sind schlimmer als keine.

    Die Linie liegt auf einem Körper. Ändert sich das Dokument — ein neues
    Projekt, ein Undo, eine Operation von woanders —, muss es diesen Körper
    nicht mehr geben, und die Kennung dahinter bezeichnet in einer anderen
    Datei etwas anderes.
    """
    with_a_cube(window)
    window.tools.activate("split")
    window.viewport.splitPointRequested.emit((-10.0, 0.0, 0.0))
    window.viewport.splitPointRequested.emit((10.0, 0.0, 0.0))
    assert window.split_bar.apply.isEnabled()

    window.session.undo()
    window.session.wait_for_idle()

    assert window._split_points == []
    assert not window.split_bar.apply.isEnabled()


# --- der ganze Weg -------------------------------------------------------------------


def test_drawing_a_line_and_pressing_split_makes_two_parts(window: MainWindow) -> None:
    """Der Hauptweg, Klick für Klick: Werkzeug auf, zweimal ins Bild, trennen."""
    with_a_cube(window)
    window.tools.activate("split")

    window.viewport.splitPointRequested.emit((-10.0, 0.0, 2.0))
    window.viewport.splitPointRequested.emit((10.0, 0.0, 2.0))
    window.split_bar.applyRequested.emit()
    window.session.wait_for_idle()

    document = window.session.project.document
    assert [entry.op for entry in document.ops] == ["load", "split_line"]
    assert len(document.ops[-1].outputs) == 2
    result = window.session.last_result
    assert result is not None
    for made in document.ops[-1].outputs:
        assert result.scene.objects[made].mesh.is_watertight


def test_the_seam_becomes_a_fit_pair(window: MainWindow) -> None:
    """§14: Stift und Bohrung sind eine Passung, und sie steht im Dokument —
    daran hängen im Slicer die Werte, die über sie entscheiden."""
    with_a_cube(window)
    window.tools.activate("split")

    window.viewport.splitPointRequested.emit((-10.0, 0.0, 2.0))
    window.viewport.splitPointRequested.emit((10.0, 0.0, 2.0))
    window.split_bar.applyRequested.emit()
    window.session.wait_for_idle()

    fits = window.session.project.document.fits
    assert len(fits) == window.split_bar.count.value()
    assert all(fit.tolerance.startswith("auto:") for fit in fits), "Regel 7"


def test_without_the_checkbox_it_only_cuts(window: MainWindow) -> None:
    with_a_cube(window)
    window.tools.activate("split")
    window.split_bar.connect_halves.setChecked(False)

    window.viewport.splitPointRequested.emit((-10.0, 0.0, 2.0))
    window.viewport.splitPointRequested.emit((10.0, 0.0, 2.0))
    window.split_bar.applyRequested.emit()
    window.session.wait_for_idle()

    assert window.session.project.document.ops[-1].params["pins"] == 0
    assert window.session.project.document.fits == []


def test_one_undo_takes_the_whole_split_back(window: MainWindow) -> None:
    """Regel 16 dem Sinn nach: ein Handgriff, ein Schritt im Verlauf."""
    with_a_cube(window)
    window.tools.activate("split")
    window.viewport.splitPointRequested.emit((-10.0, 0.0, 2.0))
    window.viewport.splitPointRequested.emit((10.0, 0.0, 2.0))
    window.split_bar.applyRequested.emit()
    window.session.wait_for_idle()

    window.session.undo()
    window.session.wait_for_idle()

    assert [entry.op for entry in window.session.project.document.ops] == ["load"]


def test_the_stored_plane_does_not_depend_on_the_camera(window: MainWindow) -> None:
    """§11.2: Was in den Stapel geht, sind Zahlen.

    Die Blickrichtung wird einmal beim Trennen gelesen. Stünde sie in der
    Operation, gäbe dieselbe Datei nach einem Kameraschwenk ein anderes Teil.
    """
    with_a_cube(window)
    window.tools.activate("split")
    window.viewport.splitPointRequested.emit((-10.0, 0.0, 2.0))
    window.viewport.splitPointRequested.emit((10.0, 0.0, 2.0))
    window.split_bar.applyRequested.emit()
    window.session.wait_for_idle()

    params = window.session.project.document.ops[-1].params
    expected = plane_through((-10.0, 0.0, 2.0), (10.0, 0.0, 2.0), window.viewport.view_direction())
    assert expected is not None
    assert params["normal_x"] == pytest.approx(expected.normal[0])
    assert params["normal_y"] == pytest.approx(expected.normal[1])
    assert params["normal_z"] == pytest.approx(expected.normal[2])
    assert set(params) & {"view_x", "camera", "view"} == set(), "keine Kamera im Stapel"
