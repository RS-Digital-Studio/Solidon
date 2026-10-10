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
from PySide6.QtCore import QRect
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QLabel, QWidget

from app.ui import overlay
from app.ui.main_window import MainWindow
from app.ui.overlay import (
    CARD_PADDING,
    EDGE,
    LEFT_MAX,
    LEFT_WIDTH,
    MARGIN,
    RIGHT_MAX,
    RIGHT_SHARE,
    RIGHT_WIDTH,
    OverlayHost,
    card_stylesheet,
    card_width,
)
from app.ui.style import ROOMY
from app.ui.theme import THEMES
from tests.ui_helpers import shown_window


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
    """Ein gezeigtes Fenster — ohne Anzeige misst ein Test hier die Vorgabegröße."""
    yield from shown_window(qt_app)


def test_first_long_finding_fits_without_another_user_event(
    qt_app: QApplication, window: MainWindow
) -> None:
    """Der erste Importbefund braucht seine Umbruchhöhe ohne späteren Menüklick."""
    from app.core.scene import EvaluationResult
    from app.core.types import Finding, Report, Scene
    from tests.helpers import make_object

    finding = Finding(
        "geometry.deviation",
        "warning",
        "Die erkannte Form weicht an einer kleinen Stelle vom ursprünglichen Modell ab. "
        "Prüfen Sie diese Stelle vor der weiteren Bearbeitung. Die größte Abweichung beträgt "
        "0,03 mm.",
        object_id="tray",
    )
    window.report.show_result(
        EvaluationResult(
            Scene(objects={"tray": make_object("tray")}, report=Report(findings=[finding]))
        )
    )
    window.right.setCurrentWidget(window.report)
    for _ in range(6):
        qt_app.processEvents()
    view = window.report.list
    item = view.item(0)
    rect = view.visualItemRect(item)
    assert rect.height() > 2 * view.fontMetrics().height()
    assert rect.bottom() < view.viewport().height(), (rect, view.viewport().size())


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
        # ``orientation_corner`` zählt Anteile von unten links, Qt von oben.
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
        room = max(view.height() - EDGE - MARGIN - host._bottom_room(), 0)
        lowest_card_edge = EDGE + room

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

    def alternating(zone: object, width: int | None = None) -> int:
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

    # Bündig an Seite und Leiste (Robert, 05.10.2026).
    assert left.geometry().left() == EDGE == 0
    assert left.geometry().top() == EDGE
    assert left.geometry().width() == LEFT_WIDTH

    assert right.geometry().right() == width - EDGE - 1
    assert right.geometry().top() == EDGE
    # Der Anschluss nutzt dieselbe responsive Breite wie die Kartenplatzierung;
    # die unabhängigen Maßgrenzen prüft die anschließende Breitenmatrix.
    assert right.geometry().width() == card_width(RIGHT_WIDTH, RIGHT_MAX, width, RIGHT_SHARE)

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
    right = [card_width(RIGHT_WIDTH, RIGHT_MAX, width, RIGHT_SHARE) for width in widths]

    assert 295 <= left[3] <= 310, f"Full HD links: {left[3]} statt etwa 300"
    assert 470 <= right[3] <= 490, f"Full HD rechts: {right[3]} statt etwa 480"
    assert left == sorted(left) and right == sorted(right), "breiter darf keine Karte schrumpfen"
    assert left[-1] <= LEFT_MAX and right[-1] <= RIGHT_MAX

    for width, left_width, right_width in zip(widths, left, right, strict=True):
        assert left_width + right_width + 2 * EDGE + MARGIN <= width, (
            f"{width}: linke und rechte Karte überlappen oder nehmen den letzten Sichtspalt"
        )


@pytest.mark.parametrize("width", (640, 800, 1200, 1920, 2560, 3072, 3840))
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
    assert left.geometry().left() == EDGE
    assert right.geometry().right() == width - EDGE - 1
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

    window.right_column.setVisible(False)

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


def test_only_what_lies_over_the_view_gets_its_own_window(qt_app: QApplication) -> None:
    """Eine native Grafikfläche steckt ihre Geschwister nicht mehr an (RM-232).

    Ohne ``AA_DontCreateNativeWidgetSiblings`` machte Qt jede Ebene über der
    wgpu-Fläche nativ, samt allen ihren Geschwistern: am Wabenhalter 140 von
    854 Widgets, die ganze Andockleiste darunter, und ein Bohrungsklick legte
    30 Fenster an. Nativ bleibt jetzt nur, was über der Fläche liegt — die
    Karten des Trägers; ihr Inhalt und alles daneben malt ohne eigenes Fenster.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QHBoxLayout

    from app.ui.overlay import keep_widgets_alien

    keep_widgets_alien()
    native = Qt.WidgetAttribute.WA_NativeWindow
    top = QWidget()
    row = QHBoxLayout(top)
    view = QWidget()
    canvas = QWidget(view)
    canvas.setAttribute(native)
    host = OverlayHost(view)
    beside = QWidget()
    inside = QLabel("daneben", beside)
    row.addWidget(host)
    row.addWidget(beside)
    zones = (QWidget(), QWidget(), QWidget())
    contents = [QLabel("Karte", zone) for zone in zones]
    host.set_zones(*zones)
    later = QLabel("später dazu", host)
    top.show()
    top.resize(800, 500)
    qt_app.processEvents()
    try:
        assert canvas.testAttribute(native) and view.testAttribute(native)
        assert all(zone.testAttribute(native) for zone in zones), "die Karten liegen über ihr"
        assert later.testAttribute(native), "auch was später dazukommt"
        assert not any(label.testAttribute(native) for label in contents), "ihr Inhalt nicht"
        assert not beside.testAttribute(native) and not inside.testAttribute(native), (
            "und was daneben liegt, steckt sie nicht mehr an"
        )
    finally:
        top.close()
        top.deleteLater()
        qt_app.processEvents()


def test_the_window_keeps_native_windows_to_the_overlays(window: MainWindow) -> None:
    """Am echten Fenster: die Andockleiste ohne eigenes Fenster, die Leisten der Ansicht mit.

    Das Merkmalfenster entstand als Kind des Hauptfensters, wurde dort nativ
    und nahm es beim Umzug in die Andockleiste mit — mit ihm jede Zeile, die
    es je baute (RM-232). Die Leisten der Ansicht sind ihre direkten Kinder
    und liegen über der Grafikfläche; sie brauchen das Fenster.
    """
    from PySide6.QtCore import Qt

    native = Qt.WidgetAttribute.WA_NativeWindow
    panel = window.feature_panel
    assert not panel.testAttribute(native)
    assert not any(child.testAttribute(native) for child in panel.findChildren(QWidget))
    assert window.viewport.view_bar.testAttribute(native)
    assert window.viewport.banner.testAttribute(native)


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

    try:
        start = left.geometry()
        host._move(
            left, QRect(start.x(), start.y(), start.width(), start.height() + 120), moving=True
        )

        assert host._moves, "eine Bewegung läuft"
        assert left.geometry() != QRect(
            start.x(), start.y(), start.width(), start.height() + 120
        ), "und sie ist noch unterwegs"
    finally:
        # **Nicht dem Speicherbereiniger überlassen.** Ein verwaister Host mit
        # laufender Animation starb irgendwann später — zwei Tests weiter
        # brach ``sizeHintForRow`` mit „Aborted" ab. Derselbe Abbau wie im
        # Nachbartest über die Freigabe der Bewegungsobjekte.
        host.close()
        host.deleteLater()
        qt_app.processEvents()


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
    assert right.geometry().right() == 1000 - EDGE - 1, "und sitzt sofort richtig"


@pytest.mark.parametrize("interrupted", [False, True])
def test_finished_card_movements_release_their_qobjects(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, interrupted: bool
) -> None:
    """Abgeschlossene wie ersetzte Bewegungen hinterlassen keine Qt-Kinder."""
    from PySide6.QtCore import QCoreApplication, QEvent, QPropertyAnimation

    monkeypatch.setattr(overlay, "MOVE_MS", 200)
    host = OverlayHost(QLabel("Ansicht"))
    zone = QWidget(host)
    host.resize(800, 600)
    host.show()
    zone.show()
    qt_app.processEvents()
    try:
        for index in range(12):
            target = QRect(10 + index, 10, 100, 100)
            host._move(zone, target, moving=True)
            movement = host._moves[id(zone)]
            assert host.findChildren(QPropertyAnimation), "der geprüfte Lauf muss existieren"
            if interrupted:
                host._move(zone, QRect(40 + index, 20, 100, 100), moving=False)
            else:
                movement.setCurrentTime(movement.duration())
            QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            assert not host._moves
            assert not host.findChildren(QPropertyAnimation), "auch das Qt-Objekt wird freigegeben"
    finally:
        host.close()
        host.deleteLater()


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


@pytest.mark.parametrize("severity", ["info", "warning"])
def test_findings_that_arrive_later_make_the_card_grow(window: MainWindow, severity: str) -> None:
    """Ein ``QListWidget`` meldet sein Wachstum nicht — es muss es sagen.

    Nach der Auswertung kommen Befunde nach: die G-Code-Gegenprobe (§28.2),
    die Kollisionsprüfung, die Exportprüfung. Die Karte blieb dabei auf der
    Höhe, die sie beim Auswerten bekommen hatte, weil die Wunschgröße eines
    ``QListWidget`` an seiner Größenrichtlinie hängt und nicht an seinem
    Inhalt — und weil die Karte in keinem Layout steckt, das ein
    ``LayoutRequest`` weiterreichen könnte.

    Aufgefallen ist es am Handbuchbild: acht Befunde im Kopf gezählt, zwei
    davon zu sehen, darunter vierhundert Pixel frei.

    **Hinweise allein klappen zu** (RM-508): Der Zähler nennt sie, und wer ihn
    klickt, sieht alle acht. Eine Warnung öffnet die Liste von selbst.

    **Und die Karte wächst in einem Zug.** Zwischen Liste und Zone liegen seit
    RM-511 Reiter, Rollbereich und Karte, und Qt reicht den neuen Wunsch je
    Ereignisrunde eine Ebene weiter. Die Zone las beim Aufklappen deshalb
    zuerst den alten Wunsch: Fünf Runden lang rollte die Liste neben freiem
    Platz, dann glitt die Karte ein zweites Mal (``overlay.tell_the_zone``,
    Durchsicht 0.5.3).
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
                severity=severity,
                message=f"Ein nachgereichter Befund Nummer {number}, mit einem Satz, "
                f"der über mehrere Zeilen läuft.",
            )
            for number in range(8)
        ]
    )
    if severity == "info":
        for _ in range(4):
            QApplication.processEvents()
        assert not report.list.isVisibleTo(report), "Hinweise allein stehen zugeklappt"
        assert "8" in report.list_toggle.text(), "der Zähler nennt sie"
        report.list_toggle.click()
    # Der Träger setzt je Ereignisdurchlauf einmal (``_place_later``); gezählt
    # wird über mehr Runden, als der alte Weg bis zur Ruhe brauchte (fünf).
    heights = []
    for _ in range(8):
        QApplication.processEvents()
        heights.append(report.height())
    assert report.list.isVisibleTo(report)

    assert report.height() > before, (
        "die Karte muss wachsen, wenn Befunde nach der Auswertung dazukommen"
    )
    assert len(set(heights)) == 1, f"die Karte wächst in einem Zug, nicht in Stufen: {heights}"
    assert report.list.verticalScrollBar().maximum() == 0, (
        "acht Befunde passen in die Spalte — ein Rollbalken hier heißt, "
        f"die Karte hat ihren Platz nicht genommen: Karte {report.height()}, "
        f"Liste {report.list.height()}, Zeilen {overlay.rows_height(report.list)}, "
        f"Spalte {window.right_column.height()}, Fenster {window.height()}"
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

    from app.ui.overlay import rows_height

    tree = QTreeWidget()
    body = QTreeWidgetItem(["Körper"])
    group = QTreeWidgetItem(["Einhänger"])
    body.addChild(group)
    for number in range(6):
        group.addChild(QTreeWidgetItem([f"Verrundung {number}"]))
    tree.addTopLevelItem(body)

    body.setExpanded(False)
    closed = rows_height(tree)
    row = tree.rowHeight(tree.indexFromItem(body))
    assert row > 0

    body.setExpanded(True)
    group.setExpanded(True)
    assert rows_height(tree) - closed == 7 * row, (
        "der Körper, sein Bausteinknoten und sechs Merkmale"
    )

    group.setExpanded(False)
    assert rows_height(tree) - closed == row, "ein zugeklappter Baustein ist eine Zeile"


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
    room = host.height() - EDGE - MARGIN - host._bottom_room()

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


def test_the_card_edge_carries_the_line_colour_not_the_accent() -> None:
    """Die Kante einer Karte sagt, wo sie aufhört — und nicht „hier handeln“.

    Mit Bernsteinkante leuchteten im Ruhezustand drei Karten neben dem einen
    Hauptknopf (RM-512); ein Signal an vier Stellen ist keines mehr. Die
    Kante nimmt die Trennfarbe, die auch Felder und Listen umrandet.
    """
    for theme in ("dark", "light"):
        sheet = card_stylesheet(theme)  # type: ignore[arg-type]
        # Nur der Block der Karte selbst: Andere Teile des Stylesheets dürfen
        # den Akzent tragen, wo er etwas verlangt.
        edge = sheet.split(f"QWidget#{overlay.CARD}, QFrame#{overlay.MEASURE_CARD} {{", 1)[1].split(
            "}", 1
        )[0]
        assert f"border: 1px solid {THEMES[theme]['line']}" in edge, theme  # type: ignore[index]
        for accent in ("accent_line", "highlight"):
            assert THEMES[theme][accent] not in edge, f"{theme}: {accent}"  # type: ignore[index]


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
    edge = QColor(THEMES["dark"]["line"])

    # Ohne die Rundungen oben und unten: dort schneidet die Maske, und eine
    # Ecke ist keine Kante.
    rows = range(ROOMY, picture.height() - ROOMY)
    # Ein Bild, das kleiner ist als der abgeschnittene Rand, ergibt eine leere
    # Zeilenmenge — und damit einen Test, der jede Farbe durchgehen ließe.
    assert len(rows) > 10, f"nur {len(rows)} Bildzeilen bei Höhe {picture.height()}"

    def lined(x: int) -> list[int]:
        return [
            y
            for y in rows
            if abs(QColor(picture.pixel(x, y)).red() - edge.red()) <= 30
            and abs(QColor(picture.pixel(x, y)).green() - edge.green()) <= 30
        ]

    # Die Karte liegt links bündig am Fensterrand (Robert, 05.10.2026): Ihre
    # Linie steht innen, zur Ansicht hin, und am Fensterrand keine.
    inner = lined(picture.width() - 1)
    assert len(inner) == len(rows), f"innen: {len(rows) - len(inner)} Zeilen ohne Randlinie"
    assert not lined(0), "am Fensterrand steht keine Linie"


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

    from app.ui.overlay import extra_height, is_room_taker

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
            if not is_room_taker(taker) or not taker.isVisibleTo(zone):
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


def test_a_card_column_masks_only_its_visible_cards(qt_app: QApplication) -> None:
    """Zwei Karten in einer Zone, und die Lücke dazwischen gehört der Ansicht.

    Die rechte Spalte trägt seit dem 07.09.2026 Bericht und Chat oben und die
    Auswahlhandlungen in einer zweiten Karte darunter (Entscheidung Robert).
    Für den Host bleibt sie eine Zone mit einer Maske — und die muss aus den
    sichtbaren Karten gebaut sein, nicht aus dem Rechteck der Spalte: sonst
    stünde zwischen den Karten der schwarze Elternhintergrund, den
    ``_round_corners`` an den Ecken einer Karte beschreibt. Eine
    ausgeblendete Karte verschwindet auch aus der Maske.
    """
    from PySide6.QtCore import QPoint

    from app.ui.overlay import CARD, CardColumn

    column = CardColumn()
    upper, lower = QWidget(), QWidget()
    upper.setMinimumHeight(100)
    lower.setMinimumHeight(60)
    column.add_card(upper, 1)
    column.add_card(lower)
    assert upper.objectName() == CARD == lower.objectName()
    column.resize(200, 300)
    column.show()
    QApplication.processEvents()
    try:
        gap_top, gap_bottom = upper.geometry().bottom(), lower.geometry().top()
        assert gap_bottom - gap_top - 1 == MARGIN
        mask = column.mask()
        assert mask.contains(QPoint(100, upper.geometry().center().y()))
        assert mask.contains(QPoint(100, lower.geometry().center().y()))
        assert not mask.contains(QPoint(100, (gap_top + gap_bottom) // 2)), "die Lücke ist frei"
        assert not mask.contains(QPoint(0, 0)), "und die Ecken bleiben rund"

        lower.hide()
        QApplication.processEvents()
        assert column.mask().boundingRect().bottom() <= upper.geometry().bottom(), (
            "eine ausgeblendete Karte verschwindet aus der Maske"
        )
    finally:
        column.deleteLater()


def test_a_card_column_forgets_a_card_deleted_on_its_own(qt_app: QApplication) -> None:
    """Die überlebende Karte berechnet ihre Maske ohne die gelöschte Schwester."""
    from PySide6.QtCore import QCoreApplication, QEvent

    from app.ui.overlay import CardColumn

    column = CardColumn()
    upper, lower = QWidget(), QWidget()
    column.add_card(upper)
    column.add_card(lower)
    column.resize(200, 300)
    column.show()
    qt_app.processEvents()
    try:
        upper.deleteLater()
        QCoreApplication.sendPostedEvents(upper, QEvent.Type.DeferredDelete)
        assert column.card_rects() == [lower.geometry()]
        lower.hide()
        assert column.card_rects() == []
        lower.show()
        assert column.card_rects() == [lower.geometry()]
    finally:
        column.deleteLater()


# --- verschiebbare Karten (Entscheidung Robert, 06.10.2026) -------------------
#
# Fragebogen zu 0.5.3: „Bewegliche Menüs?“. Die Rechnung steht als reine
# Funktionen und läuft ohne Fenster; der Griff und das Fenster darunter.


def test_a_card_place_survives_the_settings_and_refuses_what_does_not_fit() -> None:
    """Was in den Einstellungen steht, kommt als Platz zurück — Unsinn als Stammplatz."""
    from app.ui.overlay import CardPlace

    for place in (CardPlace("left"), CardPlace("right"), CardPlace("", 0.25, 0.75)):
        assert CardPlace.read(place.text(), "left") == place
    for broken in ("", "oben", "float:", "float:1.5:0", "float:a:b", "float:0:0:0", None, 3):
        assert CardPlace.read(broken, "right") == CardPlace("right"), broken
    assert CardPlace.read("float:nan:0.5", "left") == CardPlace("left"), "NaN ist kein Anteil"


def test_a_card_at_its_home_stands_where_it_always_stood() -> None:
    """Die Stammlage ist pixelgleich mit der Zeit vor den verschiebbaren Karten."""
    from PySide6.QtCore import QSize

    from app.ui.overlay import CardPlace, card_rect, free_span

    width, room, size = 1920, 900, QSize(300, 500)
    left = card_rect(CardPlace("left"), width, room, size)
    right = card_rect(CardPlace("right"), width, room, QSize(480, 400))
    assert left == QRect(EDGE, EDGE, 300, 500)
    assert right == QRect(width - 480 - EDGE, EDGE, 480, 400)
    assert free_span(width, (left, right)) == (300 + EDGE + MARGIN, 480 + EDGE + MARGIN), (
        "die Ansicht weicht in der Stammlage wie früher aus"
    )
    assert free_span(width, ()) == (0, 0), "ohne Karten gehört ihr alles"
    assert card_rect(CardPlace("left"), width, room, QSize(300, 2000)).height() == room


def test_a_card_snaps_to_an_edge_and_floats_elsewhere() -> None:
    """Bis SNAP_TO_EDGE vor einem Rand rastet sie ein, sonst schwebt sie mit Abstand."""
    from PySide6.QtCore import QSize

    from app.ui.overlay import SNAP_TO_EDGE, CardPlace, card_rect, dropped_place

    width, room = 1600, 900
    size = QSize(300, 400)
    assert dropped_place(QRect(SNAP_TO_EDGE, 50, 300, 400), width, room) == CardPlace("left")
    assert dropped_place(QRect(SNAP_TO_EDGE + 1, 50, 300, 400), width, room).edge == ""
    near_right = width - 300 - SNAP_TO_EDGE
    assert dropped_place(QRect(near_right, 0, 300, 400), width, room) == CardPlace("right")
    assert dropped_place(QRect(near_right - 1, 0, 300, 400), width, room).edge == ""
    assert dropped_place(QRect(1, 0, 300, 400), width, room, snap=0).edge == "", (
        "die Tastatur kommt mit dem ersten Pfeil vom Rand los"
    )

    floating = dropped_place(QRect(640, 200, 300, 400), width, room)
    placed = card_rect(floating, width, room, size)
    assert abs(placed.left() - 640) <= 1 and abs(placed.top() - 200) <= 1, placed
    for across in (0.0, 1.0):
        for down in (0.0, 1.0):
            rect = card_rect(CardPlace("", across, down), width, room, size)
            assert rect.left() >= MARGIN and rect.left() + rect.width() <= width - MARGIN
            assert rect.top() >= MARGIN and rect.top() + rect.height() <= room, (
                "eine schwebende Karte bleibt im Fenster und über der Werkzeugzeile"
            )


def test_a_floating_card_keeps_its_top_when_its_height_changes() -> None:
    """Die Oberkante einer schwebenden Karte steht, auch wenn sie kürzer oder länger wird.

    ``down`` war ein Anteil am Spielraum unter der Karte, also wanderte die
    Oberkante mit jeder Höhe: Wer die Kopfzeile *Objekte* anklickte, um
    zuzuklappen, sah sie unter dem Zeiger weglaufen (bei ``down=0,5`` von
    y=201 nach 275), und der zweite Klick traf etwas anderes.
    """
    from PySide6.QtCore import QSize

    from app.ui.overlay import CardPlace, card_rect, dropped_place

    width, room = 1600, 900
    for down in (0.0, 0.3, 0.5):
        place = CardPlace("", 0.5, down)
        tall = card_rect(place, width, room, QSize(300, 400))
        short = card_rect(place, width, room, QSize(300, 200))
        assert tall.top() == short.top(), (down, tall, short)
        back = dropped_place(tall, width, room)
        assert card_rect(back, width, room, QSize(300, 200)).top() == tall.top(), (
            "Loslassen und Zurücklesen treffen dieselbe Oberkante"
        )
    # **Auch beim Aufklappen bis an die Unterkante** (Runde 2): Die Karte passte
    # gerade, eine Liste wächst — die Oberkante bleibt, die Höhe wird begrenzt.
    fitting = card_rect(CardPlace("", 0.5, 0.25), width, room, QSize(300, 600))
    assert fitting.top() + fitting.height() <= room
    grown = card_rect(CardPlace("", 0.5, 0.25), width, room, QSize(300, 900))
    assert grown.top() == fitting.top(), (fitting, grown)
    assert grown.top() + grown.height() == room, "unten begrenzt, der Inhalt rollt"
    low = card_rect(CardPlace("", 0.5, 1.0), width, room, QSize(300, 500))
    assert low.top() + low.height() <= room, "ganz unten bleibt Platz für ihren Kopf"
    assert low.height() >= 200 and low.top() >= MARGIN


def test_one_edge_holds_one_card_and_a_floating_card_moves_aside() -> None:
    """Tausch am Rand, Ausweichen beim Überdecken, Absage, wo nichts passt."""
    from PySide6.QtCore import QSize

    from app.ui.overlay import CardPlace, card_rect, settled_places

    width, room = 1600, 900
    sizes = {"left": QSize(300, 450), "right": QSize(400, 320)}
    home = {"left": CardPlace("left"), "right": CardPlace("right")}

    swapped = settled_places("right", CardPlace("left"), home, sizes, width, room)
    assert swapped == {"left": CardPlace("right"), "right": CardPlace("left")}, "Tausch"

    floating = {"left": CardPlace("", 0.5, 0.2), "right": CardPlace("right")}
    pushed = settled_places("right", CardPlace("left"), floating, sizes, width, room)
    assert pushed is not None and pushed["right"] == CardPlace("left")
    assert pushed["left"].edge == "", "eine schwebende Karte bleibt schweben"

    beside = settled_places("right", CardPlace("", 0.5, 0.2), floating, sizes, width, room)
    assert beside is not None
    assert beside["right"] == CardPlace("", 0.5, 0.2), "die gezogene bekommt den Platz"
    assert beside["left"].edge == "" and beside["left"].down == 0.2, "die andere rückt waagrecht"
    mine = card_rect(beside["right"], width, room, sizes["right"])
    theirs = card_rect(beside["left"], width, room, sizes["left"])
    assert not mine.intersects(theirs), "und steht neben ihr"

    docked = {"left": CardPlace("left"), "right": CardPlace("right")}
    over_the_edge = settled_places("right", CardPlace("", 0.0, 0.2), docked, sizes, width, room)
    assert over_the_edge is not None and over_the_edge["left"] == CardPlace("left"), (
        "eine Karte am Rand weicht nicht"
    )
    assert not card_rect(over_the_edge["right"], width, room, sizes["right"]).intersects(
        card_rect(CardPlace("left"), width, room, sizes["left"])
    ), "dann rückt die gezogene neben sie"

    narrow = {"left": QSize(700, 450), "right": QSize(700, 320)}
    assert (
        settled_places(
            "right",
            CardPlace("", 0.5, 0.0),
            {"left": CardPlace("", 0.5, 0.0), "right": CardPlace("right")},
            narrow,
            1000,
            room,
        )
        is None
    ), "wo neben der anderen kein Platz ist, bleibt alles, wie es war"

    alone = settled_places(
        "left", CardPlace("", 0.3, 0.3), home, {"left": sizes["left"]}, width, room
    )
    assert alone == {"left": CardPlace("", 0.3, 0.3), "right": CardPlace("right")}, (
        "eine ausgeblendete Karte überdeckt nichts"
    )


def test_the_free_span_is_the_widest_gap_between_the_cards() -> None:
    """Die Ansicht weicht dem breitesten freien Streifen aus, wo die Karten auch stehen."""
    from app.ui.overlay import free_span

    width = 1600
    swapped = (QRect(0, 0, 480, 400), QRect(1300, 0, 300, 400))
    assert free_span(width, swapped) == (480 + MARGIN, 300 + MARGIN)
    middle = (QRect(0, 0, 300, 400), QRect(650, 80, 300, 400))
    left, right = free_span(width, middle)
    assert (left, width - right) == (950 + MARGIN, width), (
        "rechts von der schwebenden ist mehr Platz"
    )


def _host_with_cards(qt_app: QApplication) -> tuple[OverlayHost, QWidget, QWidget]:
    """Ein Wirt mit zwei Karten, die eine echte Wunschhöhe haben (450 und 320).

    Eine nackte Zone mit ``setMinimumHeight`` hat keinen gültigen
    ``sizeHint``: ``natural_height`` gab 0, alle Ziele waren 0 Punkte hoch,
    und weil sich leere Rechtecke nie schneiden, prüfte der Test zum
    Überdecken eine Lage, die es nicht gibt.
    """
    from PySide6.QtWidgets import QVBoxLayout

    host = OverlayHost(QLabel("Ansicht"))
    left, right, bottom = QWidget(), QWidget(), QLabel("Werkzeuge")
    for zone, tall in ((left, 450), (right, 320)):
        layout = QVBoxLayout(zone)
        layout.setContentsMargins(0, 0, 0, 0)
        filler = QWidget(zone)
        filler.setObjectName("filler")
        filler.setFixedHeight(tall)
        layout.addWidget(filler)
    host.set_zones(left, right, bottom)
    host.resize(1600, 1000)
    host.show()
    qt_app.processEvents()
    return host, left, right


def test_a_dragged_card_shows_an_outline_and_lands_on_release(qt_app: QApplication) -> None:
    """Ziehen zeigt Umriss und Satz, Loslassen legt hin, Escape nicht.

    Bewegt wird während des Zugs nur der Umriss aus vier Linien — die Karte
    ist ein natives Fenster über der Grafikfläche und malte sonst bei jeder
    Mausbewegung. Der Satz in der Statuszeile sagt, was das Loslassen täte
    (Regel 18), und ist danach wieder leer.
    """
    from PySide6.QtCore import QPoint

    from app.i18n import tr
    from app.ui.overlay import OUTLINE, CardPlace

    host, left, right = _host_with_cards(qt_app)
    hints: list[str] = []
    saved: list[dict[str, str]] = []
    host.dragHint.connect(hints.append)
    host.placesChanged.connect(saved.append)
    try:
        grab = host.mapToGlobal(right.geometry().center())
        host.begin_drag("right", grab)
        host.drag_to(grab - QPoint(700, 0))
        lines = [child for child in host.findChildren(QWidget) if child.objectName() == OUTLINE]
        assert len(lines) == 8, "vier Linien für die gezogene, vier für die andere"
        assert all(line.isVisibleTo(host) for line in host._outline)
        assert not any(line.isVisibleTo(host) for line in host._other_outline), (
            "die andere bleibt, wo sie ist"
        )
        assert hints[-1] == tr("Loslassen lässt die Karte hier schweben.")
        assert right.geometry().left() == 1600 - right.width(), "die Karte selbst wartet"

        host.end_drag(commit=False)
        assert host.places["right"] == CardPlace("right"), "abgebrochen bleibt sie"
        assert not any(line.isVisibleTo(host) for line in lines) and hints[-1] == ""

        host.begin_drag("right", grab)
        host.drag_to(host.mapToGlobal(QPoint(5, 30)))
        assert hints[-1] == tr("Loslassen tauscht die beiden Karten."), "am Rand der anderen"
        assert all(line.isVisibleTo(host) for line in host._other_outline), "zweiter Umriss"
        host.end_drag(commit=True)
        qt_app.processEvents()
        assert host.places == {"left": CardPlace("right"), "right": CardPlace("left")}
        assert right.geometry().left() == EDGE and left.geometry().right() == 1600 - EDGE - 1
        assert right.property("dock") == "left" and left.property("dock") == "right"
        assert saved[-1] == {"left": "right", "right": "left"}, "für die Einstellungen gemeldet"
    finally:
        host.deleteLater()


def test_a_floating_card_that_grows_keeps_its_top_and_scrolls(qt_app: QApplication) -> None:
    """Wird der Inhalt einer schwebenden Karte höher, bleibt ihre Oberkante stehen.

    Gemessen in Runde 2: Die linke Karte lag gerade passend (Oberkante 200),
    *Filamente* aufgeklappt, und die Oberkante sprang auf 87 — die geklickte
    Kopfzeile lief 113 Punkte unter dem Zeiger weg. Jetzt endet die Karte an
    der Unterkante, und ihr Inhalt rollt.
    """
    from app.ui.overlay import CardPlace, dropped_place

    host, left, _right = _host_with_cards(qt_app)
    try:
        room = host.card_room()
        filler = left.findChild(QWidget, "filler")
        # So tief gelegt, dass die 450 Punkte hohe Karte unten gerade anschließt.
        # Ohne Einrasten: Zehn Punkte über der Unterkante zieht ``dropped_place``
        # sie sonst an den unteren Rand, und sie schwebte nicht mehr.
        spot = QRect(700, room - 460, left.width(), 450)
        host.set_places(
            {
                "left": dropped_place(spot, host.width(), room, snap=0),
                "right": CardPlace("right"),
            }
        )
        qt_app.processEvents()
        top = left.geometry().top()
        assert abs(top - spot.top()) <= 1, (top, spot)
        filler.setFixedHeight(800)
        for _ in range(4):
            qt_app.processEvents()
        assert left.geometry().top() == top, "die Oberkante steht"
        assert left.geometry().top() + left.height() <= room, "die Karte endet an der Unterkante"
        filler.setFixedHeight(450)
        for _ in range(4):
            qt_app.processEvents()
        assert left.geometry().top() == top and left.height() == 450
    finally:
        host.deleteLater()


def test_a_zone_without_a_valid_wish_is_as_tall_as_its_minimum(qt_app: QApplication) -> None:
    """Eine Zone ohne gültigen ``sizeHint`` bekommt ihre Mindesthöhe, nicht null Punkte.

    ``natural_height`` gab für sie 0, und ein leeres Rechteck schneidet nie:
    Zwei solche Karten übereinander galten als frei, und der Rückfall auf die
    Stammlage griff nicht.
    """
    from app.ui.overlay import CardPlace

    host = OverlayHost(QLabel("Ansicht"))
    left, right, bottom = QWidget(), QWidget(), QLabel("Werkzeuge")
    left.setMinimumHeight(450)
    right.setMinimumHeight(320)
    host.set_zones(left, right, bottom)
    host.resize(800, 1000)
    host.show()
    qt_app.processEvents()
    try:
        assert (left.height(), right.height()) == (450, 320)
        host.set_places({"left": CardPlace("", 0.5, 0.0), "right": CardPlace("right")})
        qt_app.processEvents()
        assert left.geometry().left() == EDGE, "sie überdecken sich, also gilt die Stammlage"
    finally:
        host.deleteLater()


def test_cards_that_no_longer_fit_side_by_side_go_home_for_a_while(qt_app: QApplication) -> None:
    """Ein kleineres Fenster stellt die Stammlage her — die eigene Anordnung bleibt gemerkt."""
    from app.ui.overlay import CardPlace

    host, left, right = _host_with_cards(qt_app)
    try:
        host.set_places({"left": CardPlace("", 0.5, 0.0), "right": CardPlace("right")})
        qt_app.processEvents()
        assert (left.height(), right.height()) == (450, 320), (
            "die Karten sind so hoch, wie sie wollen"
        )
        assert left.geometry().left() > EDGE, "breit genug: sie schwebt"
        assert not left.geometry().intersects(right.geometry()), "und beide stehen frei"
        host.resize(800, 700)
        qt_app.processEvents()
        assert left.geometry().left() == EDGE, "zu schmal: vorübergehend am Stammplatz"
        assert not left.geometry().intersects(right.geometry())
        assert host.places["left"] == CardPlace("", 0.5, 0.0), "gemerkt bleibt die eigene"
        host.resize(1600, 1000)
        qt_app.processEvents()
        assert left.geometry().left() > EDGE, "und sie kommt zurück"
    finally:
        host.deleteLater()


def _outline_rect(host: OverlayHost, lines: tuple[QWidget, ...]) -> QRect | None:
    """Das Rechteck, das vier Umrisslinien umschließen — oder nichts, wenn sie verborgen sind."""
    if not lines or not all(line.isVisibleTo(host) for line in lines):
        return None
    top, _bottom, left, _right = (line.geometry() for line in lines)
    return QRect(top.left(), top.top(), top.width(), left.height())


def test_the_outline_shows_where_the_card_lands_and_where_the_other_goes(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Umriss und Satz zeigen vor dem Loslassen das Ergebnis — mit zweitem Umriss für die andere.

    Die Lage aus der Sonde (Review RM-538, Abschnitt h): beide Karten
    schwebend, die rechte auf die linke gezogen. Der Umriss stand dort, wo der
    Zeiger war, der Satz sagte „schweben“, und die Karte landete 312 Punkte
    daneben. Nach dem Soll bekommt die gezogene den Platz, und die andere rückt
    — sichtbar, bevor man loslässt (Regel 18: Der Satz ist die zweite
    Kodierung, er muss stimmen). Gemessen werden die Größen einmal beim
    Greifen: ``_card_sizes`` teilt den Raum neu zu, und das je Mausbewegung
    wäre ein Neuaufbau der Karten.
    """
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest

    from app.i18n import tr
    from app.ui.overlay import CardPlace, card_rect

    host, left, right = _host_with_cards(qt_app)
    hints: list[str] = []
    host.dragHint.connect(hints.append)
    try:
        host.set_places({"left": CardPlace("", 0.3, 0.1), "right": CardPlace("", 0.8, 0.1)})
        QTest.qWait(300)
        qt_app.processEvents()
        target = left.geometry()
        grab = host.mapToGlobal(right.geometry().topLeft() + QPoint(10, 10))
        host.begin_drag("right", grab)
        lines, others = host._outline, host._other_outline
        assert len(lines) == len(others) == 4

        shared: list[int] = []
        measuring = host._share_room
        monkeypatch.setattr(
            host, "_share_room", lambda zone, room: shared.append(room) or measuring(zone, room)
        )
        shown: list[str] = []
        for line in (*lines, *others):
            monkeypatch.setattr(line, "show", lambda: shown.append("show"))
            monkeypatch.setattr(line, "raise_", lambda: shown.append("raise"))
        for step in (QPoint(30, 0), QPoint(10, 10)):
            host.drag_to(host.mapToGlobal(target.topLeft() + step))
        monkeypatch.undo()
        assert shared == [], "die Größen gelten ab dem Griff, kein Neuaufteilen je Bewegung"
        assert shown == [], "die Linien sind schon gezeigt und oben, je Bewegung nur Geometrie"

        drag = host._drag
        assert drag is not None and drag.settled is not None
        landing = card_rect(drag.settled["right"], host.width(), host.card_room(), right.size())
        assert _outline_rect(host, lines) == landing, "der Umriss steht, wo die Karte landet"
        assert drag.settled["right"] == drag.place, "die gezogene bekommt den Platz"
        moved_aside = card_rect(drag.settled["left"], host.width(), host.card_room(), left.size())
        assert moved_aside != target, "die andere wandert"
        assert _outline_rect(host, others) == moved_aside, "und ein zweiter Umriss zeigt wohin"
        assert hints[-1] == tr(
            "Loslassen lässt die Karte hier schweben, die andere rückt beiseite."
        )

        host.end_drag(commit=True)
        QTest.qWait(400)
        qt_app.processEvents()
        assert right.geometry() == landing and left.geometry() == moved_aside, (
            "gelandet ist, was der Umriss gezeigt hat"
        )
        assert _outline_rect(host, lines) is None and _outline_rect(host, others) is None

        host.reset_cards()
        QTest.qWait(400)
        qt_app.processEvents()
        # Über die linke Karte am Rand: Die weicht nicht, also rückt die
        # gezogene neben sie — und der Umriss steht schon dort.
        host.begin_drag("right", host.mapToGlobal(right.geometry().topLeft() + QPoint(5, 5)))
        host.drag_to(host.mapToGlobal(QPoint(45, 105)))
        drag = host._drag
        assert drag is not None and drag.settled is not None
        assert drag.settled["right"] != drag.place, "sie landet nicht unter dem Zeiger"
        beside = card_rect(drag.settled["right"], host.width(), host.card_room(), right.size())
        assert _outline_rect(host, lines) == beside and not beside.intersects(left.geometry())
        assert hints[-1] == tr("Loslassen legt die Karte neben die andere.")
        assert _outline_rect(host, others) is None, "die andere bleibt am Rand"
        host.end_drag(commit=False)

        host.begin_drag("right", host.mapToGlobal(right.geometry().center()))
        host.drag_to(host.mapToGlobal(QPoint(5, 30)))
        assert hints[-1] == tr("Loslassen tauscht die beiden Karten.")
        assert _outline_rect(host, others) == QRect(
            host.width() - left.width() - EDGE, EDGE, left.width(), left.height()
        ), "der zweite Umriss steht am Rand gegenüber"
        host.end_drag(commit=False)
        assert host.places == {"left": CardPlace("left"), "right": CardPlace("right")}
    finally:
        host.deleteLater()


def test_a_drag_without_room_beside_the_other_card_says_so_before_release(
    qt_app: QApplication,
) -> None:
    """Wo neben der anderen kein Platz ist, sagt es der Satz schon beim Ziehen.

    Die Lage ist eng gebaut: eine breite rechte Karte am Rand und die linke
    schwebend so dicht davor, dass die Abstände zu den Rändern für keine der
    beiden mehr reichen, sobald die rechte schweben soll.
    """
    from PySide6.QtCore import QPoint
    from PySide6.QtTest import QTest

    from app.i18n import tr
    from app.ui.overlay import CardPlace

    host, left, right = _host_with_cards(qt_app)
    hints: list[str] = []
    host.dragHint.connect(hints.append)
    try:
        filler = right.findChild(QWidget, "filler")
        filler.setMinimumWidth(750)
        host.resize(1100, 1000)
        host.set_places({"left": CardPlace("", 0.03, 0.0), "right": CardPlace("right")})
        QTest.qWait(300)
        qt_app.processEvents()
        assert right.width() == 750 and left.geometry().left() > EDGE
        assert not left.geometry().intersects(right.geometry()), "beide stehen frei"
        host.begin_drag("right", host.mapToGlobal(right.geometry().topLeft() + QPoint(5, 5)))
        host.drag_to(host.mapToGlobal(QPoint(105, 15)))
        assert hints[-1] == tr("Hier ist neben der anderen Karte kein Platz.")
        assert not any(line.isVisibleTo(host) for line in host._other_outline)
        host.end_drag(commit=True)
        assert host.places["right"] == CardPlace("right"), "und alles bleibt, wie es war"
    finally:
        host.deleteLater()


def test_a_floating_card_gets_the_room_it_is_drawn_with(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine schwebende Karte teilt ihren Listen den Raum zu, den sie bekommt: ``room - MARGIN``.

    Zugeteilt wurde ``room``, gezeigt ``room - MARGIN`` (:func:`card_rect`):
    unten fehlten zwölf Punkte, und genau dort stehen Filamente und Verlauf.
    """
    from app.ui.overlay import CardPlace

    host, left, right = _host_with_cards(qt_app)
    try:
        host.set_places({"left": CardPlace("", 0.5, 0.0), "right": CardPlace("right")})
        rooms: dict[int, int] = {}
        measuring = host._share_room
        monkeypatch.setattr(
            host,
            "_share_room",
            lambda zone, room: rooms.__setitem__(id(zone), room) or measuring(zone, room),
        )
        room = host.card_room()
        host._card_sizes(host.width(), room, host.places)
        assert rooms[id(left)] == room - MARGIN, "schwebend"
        assert rooms[id(right)] == room, "am Rand"
    finally:
        host.deleteLater()


def test_up_and_down_at_a_docked_card_move_it_or_say_nothing(qt_app: QApplication) -> None:
    """Ein senkrechter Pfeil an der Karte am Rand löst sie nach unten; nach oben geht nichts.

    Die Karte blieb am Rand, ihr linker Rand blieb 0, und die Ansage sagte
    trotzdem „Die Karte liegt wieder an ihrem Platz.“ — eine Bestätigung für
    nichts. Nach unten erwartet man, dass sie wandert; oben am Fenster kann
    sie nicht weiter, und dann sagt der Griff nichts.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.ui.overlay import CardGrip, CardPlace

    host, left, _right = _host_with_cards(qt_app)
    grip = CardGrip(host, "left", "Karte verschieben", left, corner=True)
    notices: list[str] = []
    host.cardNotice.connect(notices.append)
    try:
        QTest.keyClick(grip, Qt.Key.Key_Up)
        QTest.keyClick(grip, Qt.Key.Key_Left)
        assert host.places["left"] == CardPlace("left") and notices == [], (
            "nichts bewegt, nichts gesagt"
        )
        top = left.geometry().top()
        QTest.keyClick(grip, Qt.Key.Key_Down)
        QTest.qWait(300)
        qt_app.processEvents()
        assert host.places["left"].edge == "", "vom Rand gelöst"
        assert left.geometry().top() > top, "und nach unten gewandert"
        assert len(notices) == 1
    finally:
        host.deleteLater()


def test_the_grip_moves_its_card_by_keyboard_and_returns_it_by_double_click(
    qt_app: QApplication,
) -> None:
    """Pfeile schieben, die Eingabetaste nennt die Plätze, Doppelklick legt zurück.

    Escape gehört während eines Zugs dem Griff, nicht dem Kürzel des Fensters
    (``CardGrip.event``): Ohne das brach Escape nichts ab, und die Karte
    landete beim Loslassen trotzdem.
    """
    from PySide6.QtCore import QEvent, QPoint, Qt
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtTest import QTest

    from app.ui.overlay import NUDGE_FAR, CardGrip, CardPlace

    host, left, _right = _host_with_cards(qt_app)
    grip = CardGrip(host, "left", "Karte verschieben", left, corner=True)
    qt_app.processEvents()
    try:
        assert grip.accessibleName() and grip.accessibleDescription()
        assert left.rect().contains(grip.geometry()), "der Griff sitzt in seiner Karte"
        assert grip.geometry().right() >= left.width() - CARD_PADDING - 2, "oben rechts"

        QTest.keyClick(grip, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)
        qt_app.processEvents()
        assert host.places["left"].edge == "", "vom Rand los"
        assert left.geometry().left() == NUDGE_FAR
        before = grip.accessibleDescription()

        menu = grip.place_menu()
        # Beide Seitenränder, die zwei unteren Ecken, der untere Rand und der Rückweg.
        assert [action.text() for action in menu.actions()] == [
            "An den linken Rand",
            "An den rechten Rand",
            "Nach unten links",
            "Nach unten rechts",
            "An den unteren Rand",
            "An ihren Platz",
        ]
        menu.actions()[1].trigger()
        menu.deleteLater()
        assert host.places == {"left": CardPlace("right"), "right": CardPlace("left")}
        assert grip.accessibleDescription() != before, "der Bildschirmleser hört die neue Lage"

        QTest.mouseDClick(grip, Qt.MouseButton.LeftButton)
        qt_app.processEvents()
        assert host.places == {"left": CardPlace("left"), "right": CardPlace("right")}

        QTest.mousePress(
            grip, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier, grip.rect().center()
        )
        QTest.mouseMove(grip, grip.rect().center() + QPoint(300, 60))
        assert host.dragging() == "left"
        override = QKeyEvent(
            QEvent.Type.ShortcutOverride, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier
        )
        assert grip.event(override) and override.isAccepted(), "im Zug nimmt der Griff Escape"
        QTest.keyClick(grip, Qt.Key.Key_Escape)
        QTest.mouseRelease(grip, Qt.MouseButton.LeftButton)
        assert host.dragging() == "" and host.places["left"] == CardPlace("left"), "abgebrochen"
    finally:
        host.deleteLater()


def test_the_window_keeps_its_card_places_and_offers_the_way_back(window: MainWindow) -> None:
    """Fenster: Griffe an beiden Karten, Plätze in den Einstellungen, *Karten an ihren Platz*.

    Auch die Ansichtsleiste unten rechts weicht jeder Karte aus, die über ihr
    stünde — eine hohe rechte Karte reichte bisher über sie.
    """
    from PySide6.QtWidgets import QApplication as App

    from app.i18n import tr
    from app.ui.overlay import CardPlace

    left_grip, right_grip = window.card_grips
    assert window.right.cornerWidget() is right_grip
    assert left_grip.parentWidget() is window.overlay.left
    assert left_grip.accessibleName() != right_grip.accessibleName()

    window.overlay.put_card("right", CardPlace("left"))
    App.processEvents()
    assert window.settings.card_places == {"left": "right", "right": "left"}
    assert window.viewport._zone_margins[:2] == (
        window.overlay.right.width() + EDGE + MARGIN,
        window.overlay.left.width() + EDGE + MARGIN,
    ), "die Ansicht weicht den getauschten Karten aus"

    entries = [
        action
        for action in window._view_menu.actions()
        if action.text() == tr("Karten an ihren Platz")
    ]
    assert len(entries) == 1
    entries[0].trigger()
    App.processEvents()
    assert window.overlay.places == {"left": CardPlace("left"), "right": CardPlace("right")}
    assert window.settings.card_places == {"left": "left", "right": "right"}

    bar = window.viewport.view_bar
    for zone in (window.overlay.left, window.overlay.right):
        assert not bar.geometry().intersects(zone.geometry()), "die Ansichtsleiste liegt frei"


def test_the_view_bar_moves_aside_from_a_tall_card(window: MainWindow) -> None:
    """Eine rechte Karte bis kurz über den Boden: Die Ansichtsleiste rückt neben sie.

    Im Ausgangszustand ist die rechte Karte kurz, und die Leiste läge auch ohne
    Ausweichen frei — ein Test dort bliebe grün, wenn das Ausweichen fiele.
    Die Lage wird deshalb hergestellt, und die Gegenprobe ohne gemeldete
    Karten muss die Leiste unter ihr finden.
    """
    view = window.viewport
    bar = view.view_bar
    saved = view._card_rects
    tall = QRect(view.width() - 480, 0, 480, view.height() - 20)
    try:
        view.set_card_rects(())
        assert bar.geometry().intersects(tall), "ohne Ausweichen läge die Leiste unter der Karte"
        view.set_card_rects((tall,))
        assert not bar.geometry().intersects(tall), "sie rückt neben die hohe Karte"
        assert bar.geometry().right() < tall.left()
    finally:
        view.set_card_rects(saved)


def test_the_view_bar_never_hides_under_the_left_card_when_the_gap_is_narrow(
    window: MainWindow,
) -> None:
    """Zwei hohe Karten mit schmaler Lücke: unter die kürzere, sonst in die Lücke.

    Die Schleife rückte die Leiste bis x=0 und ließ sie dort unter der linken
    Karte liegen, wo kein Knopf von ihr zu sehen war.
    """
    view = window.viewport
    bar = view.view_bar
    saved = view._card_rects
    width, height = view.width(), view.height()
    gap = bar.width() // 2
    middle = width // 2
    try:
        left = QRect(0, 0, middle - gap // 2, height - 4)
        right = QRect(middle + gap // 2, 0, width - middle - gap // 2, height - 60)
        view.set_card_rects((left, right))
        spot = bar.geometry()
        assert not spot.intersects(left) and not spot.intersects(right), spot
        assert spot.top() > right.bottom(), "unter die kürzere Karte"

        right = QRect(middle + gap // 2, 0, width - middle - gap // 2, height - 4)
        view.set_card_rects((left, right))
        spot = bar.geometry()
        assert spot.left() > left.right(), "in die Lücke, nicht unter die linke Karte"
        assert spot.left() < right.left(), "der Anfang der Leiste bleibt zu sehen"
    finally:
        view.set_card_rects(saved)


def test_each_grip_comes_first_in_the_tab_order_of_its_card(
    qt_app: QApplication, window: MainWindow
) -> None:
    """Tab vom Element davor landet am Griff, das nächste Element ist schon seine Karte.

    Die Griffe entstanden nach dem Inhalt und standen zuletzt: links an
    Stelle 8 von 8, rechts 7 von 7. Wer nur die Tastatur hat, tabbte durch die
    ganze Karte, bevor er sie verschieben konnte (Soll-Ablauf §6).
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    window.activateWindow()
    for grip in window.card_grips:
        card = grip.parentWidget()
        assert card is not None
        grip.setFocus(Qt.FocusReason.TabFocusReason)
        qt_app.processEvents()
        assert window.focusWidget() is grip
        QTest.keyClick(grip, Qt.Key.Key_Tab)
        after = window.focusWidget()
        assert after is not grip and card.isAncestorOf(after), (
            f"{grip.key}: nach dem Griff kommt seine Karte, nicht {after}"
        )
        grip.setFocus(Qt.FocusReason.TabFocusReason)
        QTest.keyClick(grip, Qt.Key.Key_Backtab, Qt.KeyboardModifier.ShiftModifier)
        before = window.focusWidget()
        assert before is not grip and not card.isAncestorOf(before), (
            f"{grip.key}: vor dem Griff steht nichts aus seiner Karte, sondern {before}"
        )
        QTest.keyClick(before, Qt.Key.Key_Tab)
        assert window.focusWidget() is grip, f"{grip.key}: Tab vom Element davor landet am Griff"


def test_the_cards_survive_the_garbage_collector_after_building(qt_app: QApplication) -> None:
    """Nach dem Bau und einem Lauf des Bereinigers leben Merkmalfenster und Karte der Handlungen.

    Die erste Fassung der Tabfolge lief in Python über ``nextInFocusChain``.
    PySide hängt jedes so zurückgegebene Widget an seinen Vorgänger, und mit
    einer kurzlebigen Hülle nahm der Bereiniger den Träger des Reiters
    *Auswahl* mit: 536 statt 699 Widgets, jede Auswahl warf „Internal C++
    object already deleted“ (Review RM-538, Runde 2, N1). Gebaut wird wie in
    der Anwendung, ohne dass der Test Hüllen der Karten festhält.
    """
    import gc

    from shiboken6 import isValid

    from app.ui.session import Session
    from app.ui.settings import UiSettings

    built = MainWindow(Session(), UiSettings())
    try:
        gc.collect()
        qt_app.processEvents()
        gc.collect()
        assert isValid(built.selection_operations), "die Karte der Handlungen lebt"
        assert isValid(built.feature_panel), "das Merkmalfenster lebt"
        assert all(isValid(grip) for grip in built.card_grips)
        assert built.card_grips[1] is built.right.cornerWidget()
        assert built.card_grips[0].parentWidget() is built.overlay.left
    finally:
        built.close()
        built.deleteLater()
        qt_app.processEvents()


def test_nudging_a_card_writes_the_settings_once(
    qt_app: QApplication, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zehn Pfeildrücke am Griff schreiben die Einstellungsdatei einmal, nicht zehnmal.

    Gemessen waren zehn Schreibvorgänge, synchron im Hauptfaden und atomar
    über ``replace`` — eine gehaltene Taste schrieb Dutzende je Sekunde. Der
    Wert gilt sofort, die Datei folgt gebündelt; das Schließen holt nach.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.ui import main_window as main_window_module

    written: list[object] = []
    monkeypatch.setattr(main_window_module, "save_settings", lambda settings: written.append(1))
    grip = window.card_grips[0]
    for _ in range(10):
        QTest.keyClick(grip, Qt.Key.Key_Right)
    qt_app.processEvents()
    assert window.settings.card_places["left"].startswith("float:"), "der Wert gilt sofort"
    assert written == [], "noch nichts geschrieben"
    QTest.qWait(main_window_module.CARD_PLACES_SAVE_MS + 200)
    assert written == [1], "einmal nach dem letzten Druck"

    QTest.keyClick(grip, Qt.Key.Key_Right)
    assert window._card_places_save.isActive()
    window.close()
    qt_app.processEvents()
    assert len(written) == 2 and not window._card_places_save.isActive(), (
        "das Schließen holt den ausstehenden Schreibvorgang nach"
    )


def test_a_drag_at_the_grip_keeps_a_standing_status_message(window: MainWindow) -> None:
    """Nach dem Zug steht die Anleitung wieder da, die vorher in der Statuszeile stand.

    Im Zeichenmodus und am Skelett steht dort, was der nächste Klick tut, und
    die Karten bleiben auch dann beweglich. Ein abgebrochener Zug leerte die
    Zeile.
    """
    from PySide6.QtCore import QPoint

    standing = "Freies Zeichnen. Fertig übernimmt die Zeichnung."
    window.statusBar().showMessage(standing)
    host = window.overlay
    grab = host.mapToGlobal(host.right.geometry().center())
    host.begin_drag("right", grab)
    host.drag_to(grab - QPoint(200, 0))
    assert window.statusBar().currentMessage() != standing, "beim Ziehen steht der Satz zum Zug"
    host.end_drag(commit=False)
    assert window.statusBar().currentMessage() == standing
    window.statusBar().clearMessage()
    host.begin_drag("right", grab)
    host.end_drag(commit=False)
    assert window.statusBar().currentMessage() == "", "ohne Meldung davor bleibt die Zeile leer"


@pytest.mark.parametrize("language", ["de", "en", "es", "fr", "it", "pt"])
@pytest.mark.parametrize("width", [1280, 1024])
def test_the_tab_bar_beside_the_grip_needs_no_scroll_arrows(
    qt_app: QApplication, language: str, width: int
) -> None:
    """Die Reiter der rechten Karte passen neben den Griff, in jeder Sprache.

    In Spanisch, Französisch, Italienisch und Portugiesisch war der Reiter
    *Prüfbericht* doppelt so lang wie der deutsche („Informe de comprobación“),
    und die Leiste zeigte Rollpfeile — schon ohne Griff, mit ihm 24 Punkte
    mehr. Der Reiter trägt einen kurzen Namen (Kontext „Reiter“). Offscreen
    gemessen, wie die Sonde des Reviews; am echten Fenster prüft es das
    Release.
    """
    from app.i18n import set_language
    from app.i18n.catalog import install_language
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    install_language(language)
    set_language(language)
    try:
        built = MainWindow(Session(), UiSettings(language=language))
        built.show()
        built.resize(width, 720)
        built._show_start_screen(False)
        built.right.setCurrentWidget(built.feature_dock)
        for _ in range(6):
            qt_app.processEvents()
        bar = built.right.tabBar()
        shown = [bar.tabText(index) for index in range(bar.count()) if bar.isTabVisible(index)]
        assert len(shown) >= 3, shown
        assert bar.sizeHint().width() <= bar.width(), (
            f"{language} {width}: {shown} brauchen {bar.sizeHint().width()}, Platz {bar.width()}"
        )
        built.close()
        built.deleteLater()
        qt_app.processEvents()
    finally:
        set_language("de")


@pytest.mark.parametrize("width", [640, 800, 1200, 1920, 2560, 3840])
def test_every_arrangement_fits_the_window_at_every_width(qt_app: QApplication, width: int) -> None:
    """Abnahme 4: In jeder Breite und Anordnung keine Überdeckung, ganz im Fenster, über der Leiste.

    Was nicht passt, steht vorübergehend an der Stammlage; die gemerkte
    Anordnung bleibt.
    """
    from app.ui.overlay import CardPlace

    arrangements = (
        {"left": CardPlace("left"), "right": CardPlace("right")},
        {"left": CardPlace("right"), "right": CardPlace("left")},
        {"left": CardPlace("", 0.5, 0.2), "right": CardPlace("right")},
        {"left": CardPlace("left"), "right": CardPlace("", 0.0, 1.0)},
        {"left": CardPlace("", 1.0, 0.0), "right": CardPlace("", 0.0, 0.5)},
    )
    host, left, right = _host_with_cards(qt_app)
    try:
        host.resize(width, 900)
        for places in arrangements:
            host.set_places(places)
            qt_app.processEvents()
            room = host.card_room()
            shown = (left.geometry(), right.geometry())
            assert not shown[0].intersects(shown[1]), (width, places, shown)
            for rect in shown:
                assert rect.left() >= 0 and rect.left() + rect.width() <= width, (width, places)
                assert rect.top() >= 0 and rect.top() + rect.height() <= room, (width, places)
            assert host.places == places, "gemerkt bleibt die eigene Anordnung"
    finally:
        host.deleteLater()


def test_undo_leaves_the_card_places_alone(
    qt_app: QApplication, window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Abnahme 7: Strg+Z nimmt den Schritt zurück, nicht die Lage der Karten (§2.1)."""
    from app.ui.overlay import CardPlace
    from tests.ui_helpers import with_a_body

    # Das zurückgenommene Einlesen lässt ein geändertes Projekt zurück; die
    # Speicherfrage beim Schließen gehört nicht zu diesem Test.
    monkeypatch.setattr(window, "_may_discard", lambda *_args, **_kwargs: True)
    with_a_body(window)
    steps = len(window.session.project.document.ops)
    assert steps, "ohne Schritt gäbe es nichts zurückzunehmen"
    window.overlay.put_card("right", CardPlace("left"))
    moved = dict(window.overlay.places)
    window.undo_action.trigger()
    assert window.session.wait_for_idle()
    qt_app.processEvents()
    assert len(window.session.project.document.ops) == steps - 1, "der Schritt ist zurück"
    assert window.overlay.places == moved, "die Karten bleiben, wo sie liegen"
    assert window.settings.card_places == {"left": "right", "right": "left"}


def test_the_tour_frames_the_gap_between_swapped_cards(
    qt_app: QApplication, window: MainWindow
) -> None:
    """Abnahme 12: Bei getauschten Karten rahmt die Tour die Lücke dazwischen, nicht eine Karte."""
    from app.ui.guide_targets import area_for
    from app.ui.overlay import CardPlace

    window.overlay.put_card("right", CardPlace("left"))
    qt_app.processEvents()
    area = area_for(window, "viewport")
    for zone in (window.overlay.left, window.overlay.right):
        card = QRect(zone.mapToGlobal(zone.rect().topLeft()), zone.size())
        assert not area.intersects(card), (area, card)
    origin = window.overlay.mapToGlobal(window.overlay.rect().topLeft())
    assert area.left() > origin.x() + window.overlay.right.width(), "rechts neben der Auswahl"


@pytest.mark.parametrize("size", [(1366, 768), (1920, 1080)], ids=["1366x768", "1920x1080"])
def test_the_longest_step_of_every_tour_fits_its_card_or_rolls(
    qt_app: QApplication, window: MainWindow, size: tuple[int, int]
) -> None:
    """RM-553: Die Tour-Karte ist so hoch wie ihr Inhalt, und keine Sprechblase liegt darüber.

    Bei 2000 × 816 stand die Karte auf wenigen Zeilen: Der Rollbereich der
    Schritte hatte sich den Wunsch der leeren Liste gemerkt, der aufgeklappte
    Schritt rollte neben freiem Platz, und der Tooltip eines eingeklappten
    lief als lange Zeile quer über Ansicht und Kartentext. Geprüft wird je
    Tour der längste Schritt in jeder Sprache: ganz gelegt, im Bild oder
    erreichbar über den Balken, die Karte im Fenster, keine Zeile mit Tooltip.
    """
    from PySide6.QtCore import QPoint
    from PySide6.QtWidgets import QScrollArea

    from app.core import examples
    from app.core.tour import TOURS
    from app.i18n import set_language
    from app.i18n.catalog import available_languages, install_language

    window.resize(*size)
    qt_app.processEvents()
    tour_panel = window.tour
    window.right.setTabVisible(window.right.indexOf(tour_panel), True)
    window.right.setCurrentWidget(tour_panel)
    languages = available_languages()
    assert len(languages) >= 6
    for language in languages:
        install_language(language)
        set_language(language)
        for tour in TOURS:
            example = next(entry for entry in examples.EXAMPLES if entry.id == tour.example_id)
            # Wie beim Öffnen eines Beispiels: mit dem Satz zum Reiter vor einem
            # Berichtsschritt, und gemessen wird der längste Text, wie er dasteht.
            tour_panel.set_tab_names(window._tour_tab_names())
            tour_panel.start(example, tour)
            longest = max(
                range(len(tour.steps)), key=lambda at: len(tour_panel._rows[at][1].full_text())
            )
            window.right.setCurrentWidget(tour_panel)
            for _ in range(8):
                qt_app.processEvents()
            # Erst gelegt, dann weitergeschaltet — wie *Weiter*: Der Fehler
            # stand im Wachsen danach, nicht im ersten Bild.
            tour_panel._current = longest
            tour_panel._update_marks()
            # Ein Schritt über den Prüfbericht holt dessen Reiter nicht mehr nach
            # vorn (RM-573); die Tour bleibt, gemessen wird sie.
            assert window.right.currentWidget() is tour_panel
            for _ in range(8):
                qt_app.processEvents()
            where = f"{language}, {tour.example_id}, Schritt {longest + 1}"
            text = tour_panel._rows[longest][1]
            assert text.wordWrap(), where
            for label in (tour_panel.title, tour_panel.intro, text):
                assert label.height() >= label.heightForWidth(label.width()), (
                    f"{where}: „{label.text()[:40]}“ ist abgeschnitten"
                )
            scroll = tour_panel.findChild(QScrollArea)
            assert scroll is not None
            row = tour_panel._row_hosts[longest]
            top = row.mapTo(scroll.viewport(), QPoint(0, 0)).y()
            shown = top >= 0 and top + row.height() <= scroll.viewport().height()
            rolls = scroll.verticalScrollBar().maximum() > 0
            assert shown or (rolls and row.height() > scroll.viewport().height()), (
                f"{where}: Zeile bei {top}, {row.height()} hoch, Ausschnitt "
                f"{scroll.viewport().height()}"
            )
            card = window.right_column.geometry()
            room = window.overlay.card_room()
            assert card.y() + card.height() <= room, f"{where}: Karte über der Werkzeugzeile"
            # Gerollt wird erst, wenn die Karte nicht mehr wachsen kann.
            assert not rolls or card.y() + card.height() >= room - 2, (
                f"{where}: rollt bei {card.height()} Punkten Karte, Platz bis {room}"
            )
            if not rolls:
                assert scroll.height() >= scroll.widget().heightForWidth(
                    scroll.viewport().width()
                ), f"{where}: Rollbereich kürzer als die Schritte, ohne Balken"
            bubbles = [
                widget.objectName() or type(widget).__name__
                for widget in (tour_panel, *tour_panel.findChildren(QWidget))
                if widget.toolTip()
            ]
            assert not bubbles, f"{where}: Sprechblase über der Karte an {bubbles}"
    tour_panel.stop()
