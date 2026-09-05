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
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from app.ui import overlay
from app.ui.main_window import MainWindow
from app.ui.overlay import (
    CARD_PADDING,
    LEFT_MAX,
    LEFT_WIDTH,
    MARGIN,
    RIGHT_MAX,
    RIGHT_WIDTH,
    OverlayHost,
    card_stylesheet,
    card_width,
)
from app.ui.session import Session
from app.ui.settings import UiSettings
from app.ui.style import ROOMY
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


def test_a_half_torn_down_child_is_stepped_over(qt_app: QApplication) -> None:
    """Die Python-Hülle überlebt die C++-Seite — und die erste Frage an sie
    ist der Absturz.

    Im Belegslauf vom 23.08.2026 riss `test_ui.py` in zwei von vier
    Durchgängen genau hier, jedes Mal im Teardown und jedes Mal **nach** 257
    bestandenen Tests:

        RuntimeError: Error calling Python override of QWidget::eventFilter():
        libshiboken: Internal C++ object (ObjectTree) already deleted.

    Der `eventFilter` läuft, während die Ereignisschleife ein letztes Mal
    angehalten wird, und geht über Kinder, die der Abbau schon halb weggeräumt
    hat. Beim Kunden passiert dasselbe im `closeEvent`; dort landet die
    Ausnahme auf stderr, wo sie niemand liest.

    Nachgestellt wird der Zustand so, wie Qt ihn erzeugt: Das C++-Objekt wird
    zerstört (`shiboken6.delete`), die Python-Referenz bleibt. Genau die Lage,
    in der `findChildren` etwas zurückgibt, das nur noch eine Hülle ist.
    """
    from shiboken6 import delete, isValid

    from app.ui.overlay import living

    zone = QWidget()
    lebt = QLabel("bleibt", zone)
    stirbt = QLabel("geht", zone)

    assert len(living(zone, QLabel)) == 2, "vorher sind beide da"

    delete(stirbt)
    assert not isValid(stirbt), "das C++-Objekt ist weg, die Hülle steht noch"

    uebrig = living(zone, QLabel)

    assert len(uebrig) == 1, f"das tote Kind gehört übersprungen: {len(uebrig)}"
    assert uebrig[0] is lebt

    # **Und der Beleg, warum das Überspringen zählt**: Am toten Kind wirft
    # schon die erste Frage — genau die, die `_extra_height` und der
    # `eventFilter` stellen. Ohne den Filter stünde sie in der Schleife.
    with pytest.raises(RuntimeError):
        stirbt.isVisibleTo(zone)

    zone.deleteLater()


def test_the_view_gets_the_whole_window(window: MainWindow) -> None:
    """Die Ansicht füllt den Träger — das ist der ganze Punkt des Umbaus."""
    host = window.overlay
    assert host.view.geometry().width() == host.width()
    assert host.view.geometry().height() == host.height()


def test_the_axis_marker_does_not_hide_behind_a_card(window: MainWindow) -> None:
    """Die einzige Orientierungsanzeige der Anwendung muss zu sehen sein.

    Sie stand auf ``(0.0, 0.0, 0.16, 0.24)`` — Anteile des Fensters, mit der
    Begründung, unten links liege keine Karte. Dort liegt die linke Spalte:
    Objekte, Parameter und Verlauf. Bei 1180 auf 760 war die Anzeige 189 auf
    158 Punkte groß und lag fast vollständig dahinter; zu sehen blieb allein
    die Spitze des roten X-Pfeils, die unter der Karte hervorschaute. Auf jedem
    Bildschirmfoto, in jeder Sprache — und sie sieht aus wie ein Grafikfehler.

    Ein fester Anteil kann das nicht lösen: Die Karte hält ihren Abstand in
    Bildpunkten, der Anteil daran ändert sich mit jeder Fenstergröße. Geprüft
    wird deshalb bei mehreren Größen.
    """
    from app.ui.viewport import orientation_corner

    host = window.overlay
    for size in ((1180, 760), (1600, 1000), (900, 640)):
        window.resize(*size)
        QApplication.processEvents()

        view = host.view
        left, bottom, right, top = orientation_corner(view.width(), view.height())
        # VTK zählt von unten, Qt von oben.
        marker = QRect(
            round(left * view.width()),
            round((1.0 - top) * view.height()),
            round((right - left) * view.width()),
            round((top - bottom) * view.height()),
        )

        # Gemessen wird gegen den Platz, den eine Karte einnehmen **kann**,
        # nicht gegen den, den sie gerade einnimmt: Auf der leeren Szene ist
        # die linke Spalte kurz, und genau dort fällt der Fehler nicht auf. Im
        # Fenster mit geladenem Projekt reicht sie bis an diese Kante.
        room = max(view.height() - 2 * MARGIN - host._bottom_room(), 0)
        lowest_card_edge = MARGIN + room

        assert marker.top() >= lowest_card_edge, (
            f"{size}: Die Achsenanzeige beginnt bei {marker.top()} und damit "
            f"{lowest_card_edge - marker.top()} Punkte über der Unterkante, bis zu der "
            "eine Karte wächst — eine gefüllte linke Spalte deckt sie zu."
        )

        # Die Gegenprobe. Ohne sie stünde hier eine Formel, die immer aufgeht.
        old_top = round((1.0 - 0.24) * view.height())
        assert old_top < lowest_card_edge, (
            "Der alte Wert (0.0, 0.0, 0.16, 0.24) lag hinter der linken Spalte. "
            "Tut er das nicht mehr, hat sich das Layout geändert und dieser Test "
            "braucht neue Zahlen."
        )


def test_the_axis_marker_is_placed_over_the_renderer_contract(qt_app: QApplication) -> None:
    """Das Nachziehen des Achsenkreuzes geht über den Vertrag des Renderers.

    Bis zum 05.09.2026 suchte der Viewport das Widget in PyVistas Innereien —
    ``plotter.axes_widget`` gab es in 0.48 nicht mehr, ein ``getattr`` lieferte
    still ``None``, und die Anzeige blieb dort stehen, wo sie beim Aufbau
    landete: mitten im Bild, weil das Fenster da noch keine Größe hat.
    ``place_axes_marker`` ist eine Methode des Vertrags; fehlt sie, fällt der
    Aufruf, statt zu schweigen.
    """
    from app.ui.viewport import Viewport, orientation_corner
    from tests.render_fakes import RecordingRenderer

    viewport = Viewport()
    try:
        renderer = RecordingRenderer()
        viewport.renderer = renderer
        viewport.resize(800, 600)

        viewport._place_orientation_widget()

        assert renderer.marker_corners[-1] == orientation_corner(800, 600), (
            "das Achsenkreuz wird in seine Ecke gesetzt"
        )
        viewport.renderer = None
        viewport._place_orientation_widget()  # ohne Renderer darf nichts krachen
    finally:
        viewport.deleteLater()


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


def test_the_work_cards_use_full_hd_and_grow_with_large_screens() -> None:
    """Maße und Befunde bekommen Raum, ohne auf 4K zu Wänden zu werden."""
    widths = (640, 800, 1200, 1920, 2560, 3072, 3840)
    left = [card_width(LEFT_WIDTH, LEFT_MAX, width) for width in widths]
    right = [card_width(RIGHT_WIDTH, RIGHT_MAX, width) for width in widths]

    assert 295 <= left[3] <= 310, f"Full HD links: {left[3]} statt etwa 300"
    assert 315 <= right[3] <= 330, f"Full HD rechts: {right[3]} statt etwa 320"
    assert left == sorted(left) and right == sorted(right), "breiter darf keine Karte schrumpfen"
    assert left[-1] <= LEFT_MAX and right[-1] <= RIGHT_MAX

    for width, left_width, right_width in zip(widths, left, right, strict=True):
        assert left_width + right_width + 3 * MARGIN <= width, (
            f"{width}: linke und rechte Karte überlappen oder nehmen den letzten Sichtspalt"
        )


@pytest.mark.parametrize("width", (640, 800, 1200, 1920, 2560, 3072))
def test_the_overlay_matrix_keeps_every_zone_inside_and_the_viewport_whole(
    qt_app: QApplication, width: int
) -> None:
    """Die Layoutmatrix prüft die Wirkung, nicht nur die Breitenformel."""
    host = OverlayHost(QLabel("Ansicht"))
    left, right, bottom = QWidget(), QWidget(), QLabel("Werkzeuge")
    host.set_zones(left, right, bottom)
    host.resize(width, 900)
    host.show()
    qt_app.processEvents()

    assert host.view.geometry() == host.rect()
    assert left.geometry().left() == MARGIN
    assert right.geometry().right() == width - MARGIN - 1
    assert left.geometry().right() + MARGIN < right.geometry().left(), (
        f"{width}: zwischen den Arbeitskarten bleibt kein sichtbarer Viewport"
    )
    for zone in (left, right, bottom):
        assert host.rect().contains(zone.geometry()), f"{width}: {zone.geometry()} liegt außerhalb"

    host.deleteLater()


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


def test_the_row_count_sees_every_open_level(qt_app: QApplication) -> None:
    """Die Höhe einer Karte folgt den sichtbaren Zeilen — über **alle** Ebenen.

    Der Test darüber baut lauter Körper ohne Kinder; er hätte den Fehler
    deshalb nie gesehen. Seit die Merkmale eines eingesetzten Bausteins unter
    dessen Knoten stehen, ist der Baum unter einem Körper zwei Ebenen tief,
    und dieser Knoten steht **immer** offen. Gezählt wurden die direkten
    Kinder: Ein Körper mit sechs Verrundungen unter einem Einhänger meldete
    zwei Zeilen und zeigte acht — die Karte bekam Höhe für zwei und dazu einen
    Rollbalken, den es an dieser Stelle nicht geben soll.

    Ohne Fenster, weil die Frage eine Rechnung über Baumknoten ist und ein
    Test, der dafür ein ``MainWindow`` baut, die Abrissquote der ganzen Datei
    hebt (gemessen am 24.08.2026).

    Ein ``QTreeWidget`` braucht es trotzdem, und zwar nicht als Zierat:
    ``setExpanded`` wirkt nur auf ein Item, das in einem Baum hängt — an einem
    freien meldet ``isExpanded()`` immer ``False``, und der Test wäre grün
    gegen eine Rechnung, die nie zählt. Gezeigt wird der Baum nicht.
    """
    from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem

    from app.ui.panels import _visible_rows

    tree = QTreeWidget()
    body = QTreeWidgetItem(["Körper"])
    group = QTreeWidgetItem(["Einhänger"])
    body.addChild(group)
    for number in range(6):
        group.addChild(QTreeWidgetItem([f"Verrundung {number}"]))
    tree.addTopLevelItem(body)

    body.setExpanded(True)
    group.setExpanded(True)
    assert _visible_rows(body) == 8, "der Körper, sein Bausteinknoten und sechs Merkmale"

    group.setExpanded(False)
    assert _visible_rows(body) == 2, "ein zugeklappter Baustein ist eine Zeile"

    body.setExpanded(False)
    assert _visible_rows(body) == 1, "und ein zugeklappter Körper ebenso"


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


def test_the_dodge_margin_covers_the_card_it_dodges(window: MainWindow) -> None:
    """Ausweichen, das die eigene Breite nicht kennt, weicht nicht aus.

    Der Skizzeneditor bekommt über ``set_zone_margins`` gesagt, wie weit er
    links und rechts wegbleiben soll. Gemeldet wurden die Grundbreiten
    (260 und 300) — und die gelten nur bis etwa 2000 Pixel Fensterbreite.
    Darüber wachsen die Karten mit: im Vollbild war die linke 332 Pixel breit,
    der Rand also 72 Pixel zu schmal. Genau dort, bei x = 284, lag die
    Ebenenwahl des Editors unter der Karte — zusammen mit der ersten
    Zwangsbedingung, dem Rückgängig-Knopf und der Überschrift der
    Bedingungsspalte.
    """
    seen: list[tuple[int, int, int]] = []

    class Dodger(QWidget):
        """Eine Ansicht, die ausweichen möchte, und mitschreibt, worum sie
        gebeten wird."""

        def set_zone_margins(self, left: int, right: int, bottom: int) -> None:
            seen.append((left, right, bottom))

    host = window.overlay
    host.view = Dodger(host)
    host.resize(2560, 1369)
    host._place()

    assert seen, "die Ansicht wurde überhaupt gefragt"
    left_margin, right_margin, bottom_margin = seen[-1]

    left = host.left
    right = host.right
    assert left is not None and right is not None
    assert left.geometry().width() > LEFT_WIDTH, "die Karte ist mitgewachsen"

    assert left_margin > left.geometry().right(), "der linke Rand deckt die linke Karte vollständig"
    assert right_margin > host.width() - right.geometry().left(), "und der rechte die rechte"
    assert bottom_margin == host._bottom_room(), "und unten gilt die echte Werkzeughöhe"


def test_every_card_keeps_a_pixel_for_its_border(window: MainWindow) -> None:
    """Die Randlinie ist die Kante, an der die Karte aufhört — sie muss stehen.

    Sie stand nicht: Objektbaum, Verlaufsliste und die Seite des Reiters
    tragen eigene Flächen und reichten bis an die Widgetkante. Am Bild
    nachgezählt fehlten links 300 von 588 Randzeilen und rechts 412 von 427 —
    die rechte Karte hatte den Rahmen nur noch um ihre Reiterzeile.

    Geprüft wird die Ursache: ein Layout ohne Rand legt seine Kinder auf die
    Linie. Ein ``padding`` im Stilblatt tut es nicht, Qt verkleinert damit die
    Fläche eines schlichten ``QWidget`` nicht.
    """
    for name in ("left", "bottom"):
        zone = getattr(window.overlay, name)
        assert zone is not None
        layout = zone.layout()
        assert layout is not None, f"{name} hat ein Layout"
        margins = layout.contentsMargins()
        assert min(margins.left(), margins.right()) >= CARD_PADDING, (
            f"{name}: die Kinder liegen auf der Randlinie"
        )


def test_the_drawn_card_really_shows_its_border(window: MainWindow) -> None:
    """Und die Wirkung, an der gerenderten Karte abgelesen.

    Die Ursache allein genügt nicht: eine zweite Stelle könnte die Linie
    trotzdem zumalen. Gemessen wird an der linken Spalte, weil sie die drei
    Listen trägt, an denen es aufgefallen ist.
    """
    from app.ui.theme import THEMES

    zone = window.overlay.left
    assert zone is not None
    picture = zone.grab().toImage()
    accent = QColor(THEMES["dark"]["accent_line"])

    # Ohne die Rundungen oben und unten: dort schneidet die Maske, und eine
    # Ecke ist keine Kante.
    rows = range(ROOMY, picture.height() - ROOMY)
    # Ein Bild, das kleiner ist als der abgeschnittene Rand, ergibt eine leere
    # Zeilenmenge — und damit einen Test, der jede Farbe durchgehen ließe.
    assert len(rows) > 10, f"nur {len(rows)} Bildzeilen bei Höhe {picture.height()}"
    for label, x in (("links", 0), ("rechts", picture.width() - 1)):
        wrong = [
            y
            for y in rows
            if abs(QColor(picture.pixel(x, y)).red() - accent.red()) > 30
            or abs(QColor(picture.pixel(x, y)).green() - accent.green()) > 30
        ]
        assert not wrong, f"{label}: {len(wrong)} von {len(rows)} Zeilen ohne Randlinie"


def test_the_tab_card_keeps_its_border_too(window: MainWindow) -> None:
    """Das Reiterfeld braucht seine eigene Zeile im Stilblatt.

    ``QTabWidget::pane`` ist ein Subcontrol und weiß vom Polster des
    Elternteils nichts — ohne die Regel malt es den Rahmen der rechten Karte
    über die ganze Höhe zu, und übrig bleibt der Bogen um die Reiterzeile.
    """
    sheet = card_stylesheet("dark")

    assert "QTabWidget#overlayCard::pane" in sheet
    assert f"margin: 0px {CARD_PADDING}px {CARD_PADDING}px {CARD_PADDING}px" in sheet


def test_no_card_is_pushed_outside_its_section(window: MainWindow) -> None:
    """Zeilen lagen außerhalb der Karte — und waren damit unerreichbar.

    Die Zuteilung teilte ``room`` allein unter den Karten, obwohl in der Zone
    noch Abschnittsköpfe, die Parameterleiste und die Layoutabstände stehen: bei
    zwanzig aufgeklappten Körpern bekam der Objektbaum 500 Pixel in einem
    Abschnitt, der 121 hoch war. Die 379 dazwischen schnitt das Elternwidget
    weg, und weil der Baum von seiner eigenen Höhe ausging, meldete sein
    Rollbalken dazu nichts — abgeschnitten wäre schlimm, unerreichbar ist
    schlimmer.

    Zwei Ursachen, beide hier festgehalten: das nicht abgezogene Beiwerk
    (:func:`overlay.extra_height`) und die Böden der Karten, die die anteilige
    Verteilung nicht kannte (``RoomTaker.least_height``).

    Zweimal umgelegt, weil Qt die Kinder erst im nächsten Durchlauf legt — im
    laufenden Fenster ist das ein Bild.
    """
    from PySide6.QtWidgets import QTreeWidgetItem

    from app.ui.overlay import RoomTaker, extra_height

    tree = window.object_tree.tree
    for number in range(20):
        item = QTreeWidgetItem([f"Körper {number}", "10 x 10 x 10 mm"])
        item.addChild(QTreeWidgetItem([f"Bohrung {number}", "4 mm"]))
        tree.addTopLevelItem(item)
    tree.expandAll()
    window.object_tree._fit()
    for _ in range(2):
        window.overlay.reflow()
        QApplication.processEvents()

    zone = window.overlay.left
    layout = zone.layout()
    assert layout is not None
    assert extra_height(zone) > 0, "ohne Beiwerk prüft dieser Test nichts"
    checked = 0
    for index in range(layout.count()):
        item = layout.itemAt(index)
        section = item.widget() if item is not None else None
        if section is None:
            continue
        for taker in section.findChildren(QWidget):
            if not isinstance(taker, RoomTaker) or not taker.isVisibleTo(zone):
                continue
            checked += 1
            assert taker.height() <= section.height(), (
                f"{type(taker).__name__} ragt um {taker.height() - section.height()} "
                "Pixel aus seinem Abschnitt heraus"
            )
    assert checked >= 2, "beide Karten der linken Spalte gehören geprüft"

    # Und die letzte Zeile ist erreichbar: ganz nach unten gerollt steht sie im
    # Sichtfeld des Baums, nicht dahinter.
    bar = tree.verticalScrollBar()
    assert bar is not None and bar.maximum() > 0, "vierzig Zeilen in eine Karte, ohne zu rollen?"
    bar.setValue(bar.maximum())
    QApplication.processEvents()
    last = tree.topLevelItem(19)
    assert last is not None
    deepest = last.child(0)
    viewport = tree.viewport()
    assert viewport is not None
    assert tree.visualItemRect(deepest).bottom() <= viewport.height(), (
        "am Rollbalkenende bleibt die letzte Zeile außerhalb"
    )


def test_a_view_whose_model_turned_into_a_stranger_still_answers(
    qt_app: QApplication,
) -> None:
    """Ein fremder Wrapper unter recyceltem Zeiger darf die Karte nicht sprengen.

    **Der Fall, den das ``Destroy``-Abbestellen nicht deckt.** Zweimal am
    30.08.2026 in einem vollen Torlauf gefallen, beide Male dieselbe Zeile in
    ``rows_height``::

        AttributeError: 'QWidgetItem' object has no attribute 'rowCount'

    Erreicht über ``LayoutRequest`` → ``eventFilter`` → ``_place``, also über
    eine Zone, die **noch lebt**, hin zu einer Ansicht, die schon geht. Der
    Griff aus :func:`app.ui.leash.stop_watching_the_dying` stand zu beiden
    Zeitpunkten bereits in ``overlay.py`` und half nicht: Wer abbestellt, hört
    auf, ein sterbendes Objekt zu beobachten — wer über seine *Nachbarn*
    rechnet, muss zusätzlich fragen, was er da vor sich hat.

    ``isValid`` fragt das Falsche. Ein recycelter Zeiger trägt ein
    **lebendiges** Objekt, nur eines vom falschen Typ; dieselbe Beobachtung
    steht seit dem 25.08.2026 in ``shortcut_schemes.py``, wo ein ``QWidgetItem``
    als ``watched`` ankam.

    **Was dieser Test ist und was nicht.** Er ist eine Sonde: Er stellt den
    fremden Wrapper her, statt auf ihn zu warten. Der echte Absturz kommt nur
    unter Last und nur manchmal — reproduzieren lässt er sich nicht auf Zuruf.
    Was hier geprüft wird, ist deshalb nicht „der Absturz ist weg", sondern
    „diese Eingabe wirft nicht mehr". Das ist weniger, und es ist das, was ein
    Test an dieser Stelle leisten kann.
    """
    from PySide6.QtWidgets import QListWidget, QWidgetItem

    class ReturnsAStranger(QListWidget):
        """Eine Liste, deren Modell unter einem recycelten Zeiger fremd wurde."""

        def model(self) -> object:  # type: ignore[override]
            return QWidgetItem(QWidget())

    view = ReturnsAStranger()
    view.addItem("ein Befund")

    height = overlay.rows_height(view)  # type: ignore[arg-type]

    assert height > 0, (
        "eine Liste, deren Modell fremd geworden ist, muss eine Ersatzhöhe "
        f"bekommen statt null — sonst fällt die Karte zusammen (bekam {height})"
    )
