"""FD46: Die Auswahlkarte misst Inhalt statt freier Bildschirmfläche."""

from collections.abc import Callable, Iterator

import pytest
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QAbstractButton,
    QAbstractSpinBox,
    QApplication,
    QLabel,
    QLineEdit,
    QVBoxLayout,
    QWidget,
)

from app.ui import overlay
from app.ui.overlay import CurrentPageTabs, OverlayHost
from app.ui.theme import apply_theme
from tests import qt_roots
from tests.bundled_fonts import bundled_font

roots = qt_roots.roots


@pytest.mark.parametrize("language", ("de", "en", "es", "fr", "it", "pt"))
@pytest.mark.parametrize("font_size", (9, 14))
def test_a_spanning_quick_action_wraps_to_its_whole_row(
    qt_app: QApplication,
    roots: Callable[[QWidget], QWidget],
    language: str,
    font_size: int,
) -> None:
    """FD58: Der dritte Hauptknopf nutzt seine ganze Zeile auch für den Text."""
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY
    from app.i18n import set_language
    from app.i18n.catalog import install_language
    from app.ui.card_width import button_width
    from app.ui.selection_operations import SelectionOperationsPanel
    from app.ui.style import apply_style

    install_language(language)
    set_language(language)
    load_operations()
    qt_app.setFont(QFont("DejaVu Sans", font_size))
    apply_style(qt_app, "light")
    panel = SelectionOperationsPanel(REGISTRY.all())
    roots(panel)
    panel.set_context(1, lambda _name: (True, ""), feature_kind="hole")
    panel.show()
    button = panel._quick_buttons["pattern_feature"]
    original_height = None
    for width in (600, 450, 600):
        panel.resize(width, 600)
        for _ in range(12):
            qt_app.processEvents()
        position = panel._quick.getItemPosition(panel._quick.indexOf(button))
        assert isinstance(position, tuple)
        assert position[3] == panel._quick_columns
        assert button.font().pointSizeF() == font_size
        assert button_width(button) <= button.width(), "Der vollständige Titel hat Platz"
        print(language, font_size, width, button.size().toTuple(), repr(button.text()))
        assert "\n" not in button.text(), "Die halbe Nachbarzeile ist keine Textgrenze"
        if original_height is None:
            original_height = button.height()
        else:
            assert button.height() == original_height


@pytest.fixture(autouse=True)
def _readable_font(qt_app: QApplication) -> Iterator[None]:
    """Die Betriebsschrift steht vor dem Stil; synthetische Metriken reichen nicht.

    Offscreen hat Qt unter Windows keine Schrift, auch nicht DejaVu Sans; die
    gebündelte Datei gibt jeder Plattform dieselbe Metrik wie der Linux-CI.
    Schrift und Thema gibt ``conftest.py`` zurück.
    """
    from app.ui.style import apply_style

    with bundled_font(qt_app, 9):
        apply_theme(qt_app, "light")
        apply_style(qt_app, "light")
        yield


def test_a_short_selection_does_not_expand_with_the_screen(
    qt_app: QApplication, roots: Callable[[QWidget], QWidget], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dasselbe kurze Formular braucht bei 2560 nicht mehr Platz als bei 1920."""
    apply_theme(qt_app, "light")
    monkeypatch.setattr(overlay, "MOVE_MS", 0)
    host = OverlayHost(QLabel("Ansicht"))
    roots(host)
    tabs = CurrentPageTabs()
    page = QWidget()
    page.setObjectName("selectionPage")
    layout = QVBoxLayout(page)
    label = QLabel("Gewählte Fläche")
    layout.addWidget(label)
    tabs.addTab(page, "Auswahl")
    host.set_zones(QWidget(), tabs, QLabel("Werkzeuge"))
    host.resize(1920, 1080)
    host.show()
    qt_app.processEvents()
    host.reflow()
    first = tabs.width()
    host.resize(2560, 1369)
    qt_app.processEvents()
    host.reflow()
    assert tabs.width() == first, "Leere im Fenster vergrößert die Auswahlkarte nicht"
    assert tabs.width() < 480, "Der kurze Inhalt rechtfertigt keinen Full-HD-Quotenwert"
    assert label.width() >= label.sizeHint().width(), "Der ganze Text bleibt sichtbar"


@pytest.mark.parametrize("language", ("de", "en", "es", "fr", "it", "pt"))
@pytest.mark.parametrize("font_size", (9, 14))
@pytest.mark.parametrize("window_size", ((1920, 1080), (2560, 1369)))
def test_the_face_keeps_its_lines_columns_and_footer_when_it_shrinks(
    qt_app: QApplication,
    roots: Callable[[QWidget], QWidget],
    monkeypatch: pytest.MonkeyPatch,
    language: str,
    font_size: int,
    window_size: tuple[int, int],
) -> None:
    """Echte Auswahlfelder/-handlungen: Schrumpfen darf keine zusätzliche Höhe erzeugen."""
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY
    from app.core.types import Feature
    from app.i18n import set_language
    from app.i18n.catalog import install_language
    from app.ui import card_width
    from app.ui.overlay import CardColumn
    from app.ui.panels import FeaturePanel, SelectionScroller
    from app.ui.selection_operations import SelectionOperationsPanel
    from app.ui.style import apply_style

    install_language(language)
    set_language(language)
    apply_theme(qt_app, "light")
    qt_app.setFont(QFont("DejaVu Sans", font_size))
    apply_style(qt_app, "light")
    load_operations()
    monkeypatch.setattr(overlay, "MOVE_MS", 0)
    host = OverlayHost(QLabel("Ansicht"))
    roots(host)
    tabs = CurrentPageTabs()
    page = QWidget()
    page.setObjectName("selectionPage")
    inside = QWidget()
    body = QVBoxLayout(inside)
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(0)
    feature_panel = FeaturePanel()
    operations = SelectionOperationsPanel(REGISTRY.all())
    body.addWidget(feature_panel)
    body.addWidget(operations, 1)
    face = Feature(
        id="top",
        kind="face",
        provenance="detected",
        params={"normal": (0.0, 0.0, 1.0), "centre": (0.0, 0.0, 5.0), "area": 1200.0},
    )
    feature_panel.show_feature(face.id, face)
    operations.set_context(1, lambda _name: (True, ""), feature_kind="face")
    scroller = SelectionScroller()
    scroller.setWidget(inside)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(scroller, 1)
    layout.addWidget(feature_panel.footer())
    tabs.addTab(page, "Auswahl")
    shell = QWidget()
    box = QVBoxLayout(shell)
    box.setContentsMargins(1, 1, 1, 1)
    box.addWidget(tabs)
    column = CardColumn()
    column.add_card(shell, 1)
    host.set_zones(QWidget(), column, QLabel("Werkzeuge"))
    host.resize(*window_size)
    with monkeypatch.context() as baseline:
        baseline.setattr(card_width, "selection_card_width", lambda _zone, _width: None)
        host.show()
        for _ in range(8):
            qt_app.processEvents()
            host.reflow()
        labels = [
            label
            for label in page.findChildren(QLabel)
            if label.isVisibleTo(page) and label.wordWrap()
        ]
        heights = {label: label.heightForWidth(label.width()) for label in labels}
        columns = {title: operations.columns_of(title) for title in operations._groups}
        before = (column.width(), column.height(), scroller.verticalScrollBar().maximum())
        quick_before = operations._quick_columns
    for _ in range(8):
        host.reflow()
        qt_app.processEvents()
    after = (column.width(), column.height(), scroller.verticalScrollBar().maximum())
    print(language, font_size, window_size, before, after)
    measured_fonts = {}
    for kind in (QLabel, QAbstractButton, QAbstractSpinBox, QLineEdit):
        visible = [widget for widget in page.findChildren(kind) if widget.isVisibleTo(page)]
        sizes = sorted({widget.font().pointSizeF() for widget in visible})
        measured_fonts[kind.__name__] = sizes
        assert float(font_size) in sizes, (kind.__name__, font_size, sizes)
    print("Tatsächliche Schriften", measured_fonts)
    # Die stabile Reserve darf höchstens die möglichen Balken zusätzlich
    # beanspruchen. Höhe, Umbruch und Handlungen bleiben streng wie zuvor.
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QScrollArea, QStyle

    reserve = sum(
        area.style().pixelMetric(QStyle.PixelMetric.PM_ScrollBarExtent, None, area)
        for area in page.findChildren(QScrollArea)
        if area.isVisibleTo(page)
        and area.verticalScrollBarPolicy() != Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    )
    assert after[0] <= before[0] + reserve
    assert after[1] <= before[1], "Die Karte darf dabei nicht höher werden"
    assert after[2] <= before[2], "Zusätzlicher Rollweg wäre versteckte Mehrhöhe"
    assert all(operations.columns_of(title) >= count for title, count in columns.items())
    # Die Hauptknöpfe bleiben, wie sie standen — außer die Karte ist innerhalb
    # der Reserve breiter geworden, und ihr Paar passt jetzt nebeneinander.
    # Wo diese Schwelle liegt, hängt an der Schriftrasterung: DejaVu unter
    # macOS (CoreText) maß 508 statt 498, und das Paar passte (CI-Lauf
    # 38781742486). Weniger Spalten oder ein Wechsel ohne Zuwachs bleiben rot.
    if operations._quick_columns != quick_before:
        assert operations._quick_columns > quick_before and after[0] > before[0], (
            quick_before,
            operations._quick_columns,
            before,
            after,
        )
    for label, height in heights.items():
        assert label.heightForWidth(label.width()) <= height, label.text()
    assert feature_panel.footer().geometry().bottom() <= page.height()
    assert scroller.horizontalScrollBar().maximum() == 0


def test_only_the_embedded_current_page_contributes_and_detached_size_stays(
    qt_app: QApplication,
    roots: Callable[[QWidget], QWidget],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein fremder breiter Reiter und ein eigenes Fenster sind keine Auswahlvorgabe."""
    from app.ui.card_width import selection_card_width

    monkeypatch.setattr(overlay, "MOVE_MS", 0)
    host = OverlayHost(QLabel("Ansicht"))
    roots(host)
    tabs = CurrentPageTabs()
    page = QWidget()
    page.setObjectName("selectionPage")
    layout = QVBoxLayout(page)
    layout.addWidget(QLabel("Fläche"))
    other = QLabel("Bericht")
    other.setMinimumWidth(800)
    tabs.addTab(page, "Auswahl")
    tabs.addTab(other, "Bericht")
    tabs.configure_pages({"selection": page, "report": other}, {})
    host.set_zones(QWidget(), tabs, QLabel("Werkzeuge"))
    host.resize(1920, 1080)
    host.show()
    qt_app.processEvents()
    measured = selection_card_width(tabs, 540)
    assert measured is not None and measured < 540, "Verborgener Bericht bestimmt nicht die Breite"
    tabs.setCurrentWidget(other)
    assert selection_card_width(tabs, 540) is None
    tabs.setCurrentWidget(page)
    tabs.detach_page(page)
    own_window = page.window()
    roots(own_window)
    own_window.resize(710, 420)
    qt_app.processEvents()
    before = own_window.size()
    saved = tabs.layout_state()
    assert selection_card_width(tabs, 540) is None, "Die Auswahl liegt außerhalb der Karte"
    for width in (1920, 2560):
        host.resize(width, 900)
        qt_app.processEvents()
        host.reflow()
    assert own_window.size() == before and tabs.layout_state() == saved
    tabs.return_page(page)
    tabs.configure_pages({"selection": page, "report": other}, saved)
    restored = page.window()
    roots(restored)
    qt_app.processEvents()
    host.resize(1280, 800)
    host.reflow()
    qt_app.processEvents()
    assert restored.size() == before, (
        "Auch die gespeicherte manuelle Größe bleibt beim Wiederöffnen"
    )


def test_coordinate_fields_keep_their_horizontal_space(
    qt_app: QApplication, roots: Callable[[QWidget], QWidget]
) -> None:
    """Das absichtlich schmale XYZ-Minimum darf nicht die Querzeile auflösen."""
    from app.ui.card_width import selection_card_width
    from app.ui.labels import LengthSpin
    from app.ui.panels import _CoordinateRow

    tabs = CurrentPageTabs()
    roots(tabs)
    page = QWidget()
    page.setObjectName("selectionPage")
    layout = QVBoxLayout(page)
    pairs = []
    for axis in ("X", "Y", "Z"):
        spin = LengthSpin()
        spin.setRange(-100_000, 100_000)
        spin.setValue(-999.99)
        pairs.append((QLabel(axis), spin))
    coordinates = _CoordinateRow(pairs, page)
    layout.addWidget(coordinates)
    tabs.addTab(page, "Auswahl")
    tabs.resize(540, 300)
    tabs.show()
    qt_app.processEvents()
    measured = selection_card_width(tabs, 540)
    assert measured is not None
    tabs.resize(measured, 300)
    qt_app.processEvents()
    assert coordinates.across()
    assert coordinates.width() >= coordinates._needed()
    for _label, spin in pairs:
        assert spin.width() >= spin.minimumWidth()


def test_coordinate_width_survives_temporary_vertical_overflow(
    qt_app: QApplication, roots: Callable[[QWidget], QWidget]
) -> None:
    """FD57: Eine Höhenänderung darf die angebotene XYZ-Breite nicht zurücknehmen."""
    from app.ui.card_width import selection_card_width
    from app.ui.labels import LengthSpin
    from app.ui.panels import SelectionScroller, _CoordinateRow

    tabs = CurrentPageTabs()
    roots(tabs)
    page = QWidget()
    page.setObjectName("selectionPage")
    layout = QVBoxLayout(page)
    inside = QWidget()
    body = QVBoxLayout(inside)
    pairs = []
    for axis in "XYZ":
        spin = LengthSpin()
        spin.setRange(-100_000, 100_000)
        pairs.append((QLabel(axis), spin))
    coordinates = _CoordinateRow(pairs, inside)
    body.addWidget(coordinates)
    remainder = QLabel("Weitere Felder")
    remainder.setMinimumHeight(200)
    body.addWidget(remainder)
    scroller = SelectionScroller()
    scroller.setWidget(inside)
    layout.addWidget(scroller)
    tabs.addTab(page, "Auswahl")
    tabs.resize(540, 500)
    tabs.show()
    qt_app.processEvents()
    measured = selection_card_width(tabs, 540)
    assert measured is not None
    for height in (500, 180, 500, 180):
        tabs.resize(measured, height)
        for _ in range(8):
            qt_app.processEvents()
        print("Höhenwechsel", height, measured, coordinates.width(), coordinates.height())
        assert coordinates.across(), "Ein Rollbalken darf die zugesagte Querzeile nicht umklappen"
        assert selection_card_width(tabs, 540) == measured, (
            "Der reine Höhenwechsel darf kein neues Breitenziel auslösen"
        )


@pytest.mark.parametrize("initial_width", (256, 1920))
def test_coordinates_recover_after_narrow_start_and_actual_font_changes(
    qt_app: QApplication,
    roots: Callable[[QWidget], QWidget],
    monkeypatch: pytest.MonkeyPatch,
    initial_width: int,
) -> None:
    """PB-01: Die vorige Rasterform darf den natürlichen Querbedarf nicht verkleinern."""
    from app.ui.labels import LengthSpin
    from app.ui.panels import _CoordinateRow
    from app.ui.style import apply_style

    monkeypatch.setattr(overlay, "MOVE_MS", 0)
    host = OverlayHost(QLabel("Ansicht"))
    roots(host)
    tabs = CurrentPageTabs()
    page = QWidget()
    page.setObjectName("selectionPage")
    layout = QVBoxLayout(page)
    pairs = []
    for axis in "XYZ":
        spin = LengthSpin()
        spin.setRange(-100_000, 100_000)
        spin.setValue(-999.99)
        pairs.append((QLabel(axis), spin))
    coordinates = _CoordinateRow(pairs, page)
    layout.addWidget(coordinates)
    tabs.addTab(page, "Auswahl")
    host.set_zones(QWidget(), tabs, QLabel("Werkzeuge"))
    host.resize(initial_width, 800)
    host.show()
    for _ in range(12):
        qt_app.processEvents()
        host.reflow()
    assert coordinates.across() is (initial_width > 256)
    for width, font_size in ((1920, 9), (2560, 9), (2560, 14), (2560, 18), (2560, 9)):
        qt_app.setFont(QFont("DejaVu Sans", font_size))
        apply_style(qt_app, "light")
        host.resize(width, 1080)
        for _ in range(12):
            qt_app.processEvents()
            host.reflow()
        print("XYZ-Rückkehr", initial_width, width, font_size, tabs.width(), coordinates._needed())
        assert all(spin.font().pointSizeF() == font_size for _label, spin in pairs)
        assert coordinates.across(), "Bei genügend Fensterfläche kehrt die Querzeile zurück"
        assert coordinates.width() >= coordinates._needed()


@pytest.mark.parametrize("language", ("de", "en", "es", "fr", "it", "pt"))
@pytest.mark.parametrize("animated", (False, True))
@pytest.mark.parametrize("initial_width", (1024, 2560))
def test_open_hole_coordinates_follow_actual_font_changes(
    qt_app: QApplication,
    roots: Callable[[QWidget], QWidget],
    monkeypatch: pytest.MonkeyPatch,
    language: str,
    animated: bool,
    initial_width: int,
) -> None:
    """PB-01 am echten Anschluss: Verschieben einer Bohrung bleibt eine XYZ-Zeile."""
    from PySide6.QtTest import QTest

    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY
    from app.core.types import Feature
    from app.i18n import set_language
    from app.i18n.catalog import install_language
    from app.ui.overlay import CardColumn
    from app.ui.panels import FeaturePanel, SelectionScroller
    from app.ui.selection_operations import SelectionOperationsPanel
    from app.ui.style import apply_style

    install_language(language)
    set_language(language)
    load_operations()
    if not animated:
        monkeypatch.setattr(overlay, "MOVE_MS", 0)
    host = OverlayHost(QLabel("Ansicht"))
    roots(host)
    tabs = CurrentPageTabs()
    page = QWidget()
    page.setObjectName("selectionPage")
    inside = QWidget()
    body = QVBoxLayout(inside)
    body.setContentsMargins(0, 0, 0, 0)
    body.setSpacing(0)
    panel = FeaturePanel()
    operations = SelectionOperationsPanel(REGISTRY.all())
    body.addWidget(panel)
    body.addWidget(operations, 1)
    hole = Feature(
        id="hole",
        kind="hole",
        provenance="detected",
        params={
            "centre": (0.0, 0.0, 5.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 5.2,
            "depth": 10.0,
            "through": True,
        },
    )
    panel.show_feature(hole.id, hole)
    operations.set_context(1, lambda _name: (True, ""), feature_kind="hole")
    scroller = SelectionScroller()
    scroller.setWidget(inside)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(0)
    layout.addWidget(scroller, 1)
    layout.addWidget(panel.footer())
    tabs.addTab(page, "Auswahl")
    shell = QWidget()
    box = QVBoxLayout(shell)
    box.setContentsMargins(1, 1, 1, 1)
    box.addWidget(tabs)
    column = CardColumn()
    column.add_card(shell, 1)
    host.set_zones(QWidget(), column, QLabel("Werkzeuge"))
    host.resize(initial_width, 820 if initial_width == 1024 else 1369)
    host.show()
    for _ in range(12):
        qt_app.processEvents()
        host.reflow()
    move = next(row for row in panel._shown_rows.values() if row.op == "move_feature")
    move.toggle.click()
    (coordinates,) = move.coordinates
    original_height = None
    original_card_height = None
    for font_size in (9, 14, 9):
        qt_app.setFont(QFont("DejaVu Sans", font_size))
        apply_style(qt_app, "light")
        if initial_width == 1024:
            host.resize(2560, 1200) if font_size == 14 else host.resize(1024, 820)
        if animated:
            frames = []
            for _ in range(45):
                QTest.qWait(30)
                frames.append(
                    (column.size().toTuple(), coordinates.size().toTuple(), coordinates.across())
                )
            assert len(set(frames[-10:])) == 1, "Das animierte Größenmaß kommt zur Ruhe"
        else:
            for _ in range(12):
                qt_app.processEvents()
                host.reflow()
        fields = coordinates.findChildren(QAbstractSpinBox)
        print(
            "Bohrung-Schriftwechsel",
            language,
            font_size,
            column.width(),
            column.height(),
            coordinates.width(),
            coordinates.height(),
            coordinates._needed(),
            scroller.verticalScrollBar().maximum(),
        )
        print(
            "Feldhöhen",
            [
                (field.minimumHeight(), field.sizeHint().height(), field.height())
                for field in fields
            ],
            coordinates.minimumHeight(),
            coordinates.minimumSizeHint().height(),
            coordinates.sizeHint().height(),
        )
        assert len(fields) == 3 and all(field.font().pointSizeF() == font_size for field in fields)
        assert coordinates.across(), (
            "Geöffnete XYZ-Felder bleiben bei vorhandenem Platz nebeneinander"
        )
        assert coordinates.width() >= coordinates._needed()
        assert panel.footer().geometry().bottom() <= page.height()
        assert scroller.horizontalScrollBar().maximum() == 0
        from app.ui.card_width import button_width

        button = operations._quick_buttons["pattern_feature"]
        assert button_width(button) <= button.width()
        assert "\n" not in button.text(), "Die ganzzeilige Handlung bleibt bei Schriftwechsel ganz"
        if font_size == 9:
            if original_height is None:
                original_height = coordinates.height()
                original_card_height = column.height()
            else:
                assert coordinates.height() == original_height, (
                    "Kleine Schrift gewinnt ihre Höhe zurück"
                )
                assert column.height() <= original_card_height
