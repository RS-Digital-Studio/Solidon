"""Die Zonen liegen über der Ansicht, nicht neben ihr (Bauplan §2.5).

Der Umbau hat eine Behauptung, und die ist prüfbar: die Ansicht bekommt das
ganze Fenster, und die drei Zonen nehmen ihr nichts weg. Vorher teilte ein
Splitter die Breite — ein Objektbaum mit einer Zeile besetzte zweihundertachtzig
Pixel über die volle Höhe.

Geprüft wird die Geometrie und nicht das Aussehen: wie eine Karte gerahmt ist,
entscheidet das Thema, aber *wo* sie liegt, entscheidet diese Datei.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QRect
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from app.ui import overlay
from app.ui.main_window import MainWindow
from app.ui.overlay import LEFT_WIDTH, MARGIN, RIGHT_WIDTH, OverlayHost, card_stylesheet
from app.ui.session import Session
from app.ui.settings import UiSettings


@pytest.fixture(autouse=True)
def _without_movement(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ohne Bewegung messen.

    Die Karten gleiten an ihren Platz (``MOVE_MS``). Ein Test, der die
    Geometrie prüft, während eine Animation läuft, misst einen Zwischenstand
    und wird sporadisch rot — die schlechteste Sorte Test. Die Bewegung selbst
    prüft ``test_a_card_glides_when_the_user_caused_it``.
    """
    monkeypatch.setattr(overlay, "MOVE_MS", 0)


@pytest.fixture
def window(qt_app: QApplication) -> Iterator[MainWindow]:
    """Ein gezeigtes Fenster.

    Gezeigt, weil Qt ein Resize-Ereignis an ein verstecktes Widget erst beim
    Anzeigen zustellt — und die Geometrie der Zonen entsteht genau dort. Ein
    Test auf einem nie gezeigten Fenster misst die Vorgabegröße 640 × 480 und
    nichts von dem, was diese Datei behauptet. Offscreen kostet das nichts.
    """
    window = MainWindow(Session(), UiSettings())
    window.show()
    window.resize(1200, 900)
    # Und der Startbildschirm muss weg: solange er im Stapel oben liegt, hat
    # der Träger darunter keine Größe, und alle Zonen lägen auf 100 Pixeln.
    window._show_start_screen(False)
    qt_app.processEvents()
    yield window
    # Aufräumen ist hier Pflicht und nicht Höflichkeit: ein gezeigtes Fenster,
    # das stehen bleibt, bekommt weiter Ereignisse — und riss siebzehn Tests
    # *nach* dieser Datei mit ``AttributeError`` aus dem Ereignisfilter.
    window.close()
    window.deleteLater()
    qt_app.processEvents()


def test_the_view_gets_the_whole_window(window: MainWindow) -> None:
    """Die Ansicht füllt den Träger — das ist der ganze Punkt des Umbaus."""
    host = window.overlay
    assert host.view.geometry().width() == host.width()
    assert host.view.geometry().height() == host.height()


def test_placing_the_zones_never_runs_into_itself(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Durchlauf setzt jede sichtbare Zone genau einmal.

    ``_move`` weist die Geometrie sofort zu, sobald nicht animiert wird — und
    ``setGeometry`` stellt sein ``Resize`` sofort zu, nicht über die
    Warteschlange. Der Ereignisfilter fängt es und ruft ``_place`` erneut,
    mitten in den Aufruf, aus dem es stammt.

    Getragen hat das die Bremse in ``_move``: steht die Zone schon am Ziel,
    passiert nichts mehr. Sie hält nur, solange das Ziel dasselbe bleibt.
    ``natural_height`` misst die Listen in einer Zone über deren *aktuelle*
    Höhe — die das ``setGeometry`` gerade geändert hat. Zwei Werte, die sich
    abwechseln, genügen, und der Stapel läuft über. Die ganze Datei starb
    daran, beim ersten Test.

    Hier wird das Schwanken erzwungen, statt auf die Gelegenheit zu warten, bei
    der es von selbst auftritt.
    """
    seen: list[object] = []

    def alternating(zone: object) -> int:
        seen.append(zone)
        return 200 if len(seen) % 2 else 400

    monkeypatch.setattr(overlay, "natural_height", alternating)

    window.overlay._place(moving=True)

    assert len(seen) <= 2, f"{len(seen)} Messungen für zwei Zonen — der Aufruf lief in sich selbst"


def test_the_zones_sit_on_top_and_take_nothing_away(window: MainWindow) -> None:
    """Links oben, rechts oben, Werkzeuge unten mittig — und alle innerhalb."""
    width = window.overlay.width()
    height = window.overlay.height()

    left = window.overlay.left
    right = window.overlay.right
    bottom = window.overlay.bottom
    assert left is not None and right is not None and bottom is not None

    assert left.geometry().left() == MARGIN
    assert left.geometry().top() == MARGIN
    assert left.geometry().width() == LEFT_WIDTH

    assert right.geometry().right() == width - MARGIN - 1
    assert right.geometry().top() == MARGIN
    assert right.geometry().width() == RIGHT_WIDTH

    # Die Werkzeugzeile ist so breit, wie sie sein muss, und liegt mittig.
    assert bottom.geometry().bottom() <= height - MARGIN
    left_gap = bottom.geometry().left()
    right_gap = width - bottom.geometry().right()
    assert abs(left_gap - right_gap) <= 2, "mittig, nicht bündig"

    # Und keine Zone hängt aus dem Fenster.
    for zone in (left, right, bottom):
        assert zone.geometry().left() >= 0
        assert zone.geometry().right() <= width
        assert zone.geometry().bottom() <= height


def test_a_hidden_zone_gives_its_room_back(window: MainWindow) -> None:
    """F9 blendet den rechten Bereich aus — danach steht dort Modell.

    Vorher gab der Splitter die Breite an die Nachbarn weiter; jetzt ist die
    Fläche einfach wieder Ansicht. Geprüft wird deshalb, dass die Ansicht ihre
    Größe behält, statt sich an der Zone zu orientieren.
    """
    assert window.right is not None
    width = window.overlay.width()

    window.right.setVisible(False)

    assert window.overlay.view.geometry().width() == width, "die Ansicht bleibt ganz"


def test_a_card_covers_what_lies_behind_it() -> None:
    """Eine Karte ohne deckende Fläche wäre Text auf einem Modell.

    Beide Themen, denn genau hier fällt ein halb übernommenes Thema auf: eine
    durchsichtige Karte sieht im dunklen Thema nach Absicht aus und im hellen
    nach Fehler.
    """
    for theme in ("dark", "light"):
        sheet = card_stylesheet(theme)  # type: ignore[arg-type]
        assert "#overlayCard" in sheet
        assert "background:" in sheet
        assert "border:" in sheet

    assert card_stylesheet("dark") != card_stylesheet("light"), (  # type: ignore[arg-type]
        "beide Themen ergäben sonst dieselbe Karte"
    )


def test_the_host_survives_zones_that_arrive_late(qt_app: QApplication) -> None:
    """``setParent`` löst sofort ein Resize aus — vor den Zonen.

    Das ist kein erfundener Fall: der erste Entwurf setzte die drei Felder nach
    dem Umhängen der Ansicht, und das Fenster starb beim Bauen mit
    ``AttributeError`` aus ``resizeEvent``.
    """
    host = OverlayHost(QLabel("Ansicht"))
    host.show()
    host.resize(400, 300)
    qt_app.processEvents()
    assert host.view.geometry().width() == 400

    host.set_zones(QWidget(), QWidget(), QWidget())
    host.resize(500, 400)
    qt_app.processEvents()
    assert host.view.geometry().width() == 500


def test_a_card_glides_when_the_user_caused_it(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Klappt ein Abschnitt zu, springen die darunter an eine neue Stelle.

    Ohne Weg dazwischen muss man raten, welcher wohin gewandert ist — das ist
    der ganze Zweck der Bewegung, und deshalb ist sie kein Schmuck.
    """
    monkeypatch.setattr(overlay, "MOVE_MS", 200)

    host = OverlayHost(QLabel("Ansicht"))
    left, right, bottom = QWidget(), QWidget(), QWidget()
    host.set_zones(left, right, bottom)
    host.show()
    host.resize(800, 600)
    qt_app.processEvents()

    start = left.geometry()
    host._move(left, QRect(start.x(), start.y(), start.width(), start.height() + 120), moving=True)

    assert host._moves, "eine Bewegung läuft"
    assert left.geometry() != QRect(start.x(), start.y(), start.width(), start.height() + 120), (
        "und sie ist noch unterwegs"
    )


def test_dragging_the_window_lets_nothing_lag_behind(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wer am Fensterrand zieht, erwartet, dass alles folgt.

    Eine Karte, die dabei hinterherläuft, sieht nicht nach Sorgfalt aus,
    sondern nach einem langsamen Rechner.
    """
    monkeypatch.setattr(overlay, "MOVE_MS", 200)

    host = OverlayHost(QLabel("Ansicht"))
    left, right, bottom = QWidget(), QWidget(), QWidget()
    host.set_zones(left, right, bottom)
    host.show()
    host.resize(800, 600)
    qt_app.processEvents()

    host.resize(1000, 700)

    assert not host._moves, "ein Resize bewegt nichts, es setzt"
    assert right.geometry().right() == 1000 - MARGIN - 1, "und sitzt sofort richtig"
