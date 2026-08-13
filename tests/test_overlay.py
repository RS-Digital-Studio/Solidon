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
from app.ui.theme import THEMES


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


def test_a_wrapped_finding_is_measured_at_its_real_height(window: MainWindow) -> None:
    """``sizeHintForRow`` kennt den Wortumbruch nicht — ``visualRect`` schon.

    Der Prüfbericht bricht seine Sätze um (§2.7 schreibt Sätze, keine
    Stichworte). Gerechnet wurde die Kartenhöhe trotzdem über
    ``sizeHintForRow``, und der meldet für jede Zeile dieselbe Zahl, ob dort
    ein Wort steht oder drei Zeilen. Bei den fünf Befunden, mit denen das
    Beispielprojekt öffnet, waren das 170 Pixel gegen 234 echte — und die
    Karte bekam die 170, also stand bei fünf Befunden ein Rollbalken in
    einer Spalte, neben der achthundert Pixel frei blieben.
    """
    from PySide6.QtWidgets import QListWidgetItem

    report = window.report
    window.right.setCurrentIndex(window.right.indexOf(report))
    report.list.clear()
    for number in range(4):
        report.list.addItem(
            QListWidgetItem(
                f"Befund {number}: ein Satz, der in einer schmalen Karte über "
                f"mehrere Zeilen läuft, so wie die echten es tun."
            )
        )
    QApplication.processEvents()

    naive = sum(report.list.sizeHintForRow(row) for row in range(report.list.count()))
    measured = overlay.rows_height(report.list)

    assert measured > naive, "der Umbruch muss in der Höhe ankommen"


def test_findings_that_arrive_later_make_the_card_grow(window: MainWindow) -> None:
    """Ein ``QListWidget`` meldet sein Wachstum nicht — es muss es sagen.

    Nach der Auswertung kommen Befunde nach: die G-Code-Gegenprobe (§28.2),
    die Kollisionsprüfung, die Exportprüfung. Die Karte blieb dabei auf der
    Höhe, die sie beim Auswerten bekommen hatte, weil die Wunschgröße eines
    ``QListWidget`` an seiner Größenrichtlinie hängt und nicht an seinem
    Inhalt — und weil die Karte in keinem Layout steckt, das ein
    ``LayoutRequest`` weiterreichen könnte.

    Aufgefallen ist es am Handbuchbild: acht Befunde im Kopf gezählt, zwei
    davon zu sehen, darunter vierhundert Pixel frei.
    """
    from app.core.types import Finding

    report = window.report
    window.right.setCurrentIndex(window.right.indexOf(report))
    report.list.clear()
    QApplication.processEvents()
    window.overlay.reflow()
    QApplication.processEvents()
    before = report.height()

    report.add_findings(
        [
            Finding(
                code=f"probe.{number}",
                severity="info",
                message=f"Ein nachgereichter Befund Nummer {number}, mit einem Satz, "
                f"der über mehrere Zeilen läuft.",
            )
            for number in range(8)
        ]
    )
    QApplication.processEvents()

    assert report.height() > before, (
        "die Karte muss wachsen, wenn Befunde nach der Auswertung dazukommen"
    )
    assert report.list.verticalScrollBar().maximum() == 0, (
        "acht Befunde passen in die Spalte — ein Rollbalken hier heißt, "
        "die Karte hat ihren Platz nicht genommen"
    )


def test_a_card_uses_the_room_a_tall_window_offers(window: MainWindow) -> None:
    """Der Deckel kommt aus der Fensterhöhe, nicht aus einer Konstante.

    ``MAX_ROWS`` stand auf zwölf, gesetzt über ``setFixedHeight``. Im
    Vollbild rollte der Objektbaum bei dreißig sichtbaren Zeilen, während
    unter der Karte dreihundert Pixel leer blieben. Wie viel Platz da ist,
    weiß nur die Überlagerung — sie teilt ihn zu.
    """
    from PySide6.QtWidgets import QTreeWidgetItem

    from app.ui.panels import MAX_ROWS

    tree = window.object_tree
    tree.tree.clear()
    for number in range(MAX_ROWS * 3):
        tree.tree.addTopLevelItem(QTreeWidgetItem([f"Körper {number}", "10 × 10 × 10 mm"]))
    tree._fit()
    QApplication.processEvents()

    window.resize(1200, 1400)
    QApplication.processEvents()
    window.overlay.reflow()
    QApplication.processEvents()

    row = tree.tree.sizeHintForRow(0)
    assert tree.tree.height() > MAX_ROWS * row, (
        "ein hohes Fenster muss dem Baum mehr als den Vorgabedeckel geben"
    )
    assert tree.tree.height() <= tree.wanted_height(), "aber nie mehr, als er braucht"


def test_one_action_moves_a_card_once(window: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    """Eine Handlung, eine Bewegung — nicht neunhundertfünf.

    Die Zuteilung der Höhe las einmal die Höhen, die sie gerade selbst
    gesetzt hatte. Damit bekam sie beim nächsten Durchlauf andere Zahlen,
    setzte wieder, und weil ``_move`` eine laufende Animation abbrach und neu
    begann, sobald die Geometrie nicht schon am Ziel war, kam die Karte nie
    an: sie lief bei jeder Aktion auf und ab. Gemessen an einem einzigen
    Aufklappen waren es neunhundertfünf Geometriewechsel.
    """
    from PySide6.QtCore import QPropertyAnimation
    from PySide6.QtWidgets import QTreeWidgetItem

    monkeypatch.setattr(overlay, "MOVE_MS", 160)
    left = window.overlay.left
    started: list[int] = []

    original = QPropertyAnimation.start

    def counting(self: QPropertyAnimation, *args: object, **kwargs: object) -> None:
        if self.targetObject() is left:
            started.append(1)
        original(self, *args, **kwargs)

    monkeypatch.setattr(QPropertyAnimation, "start", counting)

    tree = window.object_tree
    for number in range(20):
        item = QTreeWidgetItem([f"Körper {number}", "10 × 10 × 10 mm"])
        item.addChild(QTreeWidgetItem([f"Bohrung {number}", "Ø4 mm"]))
        tree.tree.addTopLevelItem(item)
    tree._fit()
    QApplication.processEvents()

    started.clear()
    tree.tree.expandAll()
    QApplication.processEvents()

    # Eine Handvoll statt einer einzigen: Qt legt einen Baum mit zwanzig
    # Ästen in Etappen, und jede Etappe ist eine echte Änderung des Bedarfs.
    # Die Grenze hütet die Größenordnung — vor dem Fix waren es
    # neunhundertfünf, am laufenden Fenster ist es heute eine.
    assert len(started) <= 3, f"{len(started)} Bewegungen für ein Aufklappen"


def test_sharing_the_room_settles_on_one_answer(window: MainWindow) -> None:
    """Zweimal zuteilen ergibt dasselbe — sonst schaukelt es sich auf.

    Die Bedingung dafür ist, dass weder ``room`` noch ``wanted_height`` an der
    Höhe hängen, die gerade gesetzt wurde.
    """
    host = window.overlay
    room = host.height() - 2 * MARGIN - host._bottom_room()

    host._share_room(host.left, room)
    QApplication.processEvents()
    first = (window.object_tree.tree.height(), window.history_panel.list.height())

    host._share_room(host.left, room)
    QApplication.processEvents()
    second = (window.object_tree.tree.height(), window.history_panel.list.height())

    assert first == second


def test_a_list_pinned_below_qts_default_hint_does_not_shrink_its_zone(
    qt_app: QApplication,
) -> None:
    """Die linke Spalte rechnete sich um die Qt-Pauschale zu kurz.

    Ihre Listen stehen per ``fit_to_rows`` auf festen Höhen, meist weit unter
    Qts pauschaler Wunschhöhe von 192 Pixeln — das Layout rechnet mit der
    geklemmten Zahl, ``natural_height`` zog aber die Pauschale ab. Je Liste
    fehlten der Zone damit gut hundert Pixel: gemessen bekam sie 159 für 371
    Pixel Inhalt, und Parameter und Verlauf hingen unterhalb der Kartenkante —
    „zeigt die Hälfte". Sichtbar wurde das beim Einklappen, denn erst dann lag
    der Bedarf unter der Fensterhöhe und der Deckel ``room`` verdeckte den
    Fehler nicht mehr.
    """
    from PySide6.QtWidgets import QListWidget, QVBoxLayout

    zone = QWidget()
    layout = QVBoxLayout(zone)
    listing = QListWidget(zone)
    listing.addItem("eine Zeile")
    listing.setFixedHeight(60)
    layout.addWidget(QLabel("Überschrift", zone))
    layout.addWidget(listing)
    zone.adjustSize()

    assert overlay.natural_height(zone) >= zone.sizeHint().height(), (
        "die Zone muss mindestens bekommen, was ihr Layout braucht"
    )


def test_the_card_edge_carries_the_accent() -> None:
    """Ein grauer Rand über einem grauen Modell in einem grauen Raum ist die
    Kante, die man sucht statt sieht.

    Der Akzent steht damit an mehr als einer Stelle zugleich — das war eine
    bewusste Entscheidung und keine Nachlässigkeit. Der Test hält sie fest,
    damit sie nicht beim nächsten Aufräumen still zurückgedreht wird.
    """
    for theme in ("dark", "light"):
        sheet = card_stylesheet(theme)  # type: ignore[arg-type]
        accent = THEMES[theme]["accent_line"]  # type: ignore[index]
        assert f"border: 1px solid {accent}" in sheet, theme
        # Und nicht mehr die Trennfarbe: Die steht weiter zwischen Zeilen und
        # Feldern, nur nicht mehr an der Kante der Karte.
        assert f"border: 1px solid {THEMES[theme]['line']}" not in sheet  # type: ignore[index]
