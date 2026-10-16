"""Was der Prüfstand an einer Fläche aufnimmt, ist, was der Kunde dort hat (Paket F8, RM-737).

Offscreen an echten Widgets, ohne den ganzen Fall: Felder, die der Besitzer
selbst versteckt, zählen nicht (FD-102); eine Zeile in Liste oder Baum, die
die Ansicht mit „…“ kürzt, ist abgeschnitten (FD-110); der Grund eines grauen
Knopfs steht als eigenes Bild da (FD-149); ein Glied der Tab-Kette ohne
eigenen Namen heißt nicht nach seiner Klasse (FD-141).
"""

from __future__ import annotations

from typing import Any

from tools import function_capture as capture

# --- FD-102: ein selbst verstecktes Feld ist keines der Fläche --------------------------


def test_a_field_its_owner_hides_is_not_counted_but_one_behind_a_flap_is(qt_app: Any) -> None:
    """Der Haken „Auf alle … anwenden“ steht leer und versteckt im Merkmalfenster.

    Er erscheint erst bei mehreren gleichartigen Merkmalen, dann mit Text und
    Kurzhilfe (``feature_editing.configure_scope``). Versteckt zählte ihn V3 als
    Feld ohne Titel und Satz (FD-102, Lauf 037–042). Ein Feld hinter einer
    zugeklappten Klappe bleibt dagegen ein Feld der Fläche, nur nicht vorn.
    """
    from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QFormLayout, QVBoxLayout, QWidget

    root = QWidget()
    layout = QVBoxLayout(root)
    front = QWidget(root)
    form = QFormLayout(front)
    width = QDoubleSpinBox(front)
    width.setAccessibleName("Breite")
    width.setToolTip("Wie breit das Teil wird.")
    form.addRow("Breite", width)
    layout.addWidget(front)
    flap = QWidget(root)
    behind = QFormLayout(flap)
    depth = QDoubleSpinBox(flap)
    depth.setAccessibleName("Tiefe")
    depth.setToolTip("Wie tief es reicht.")
    behind.addRow("Tiefe", depth)
    layout.addWidget(flap)
    flap.setVisible(False)
    every = QCheckBox("", root)
    every.setVisible(False)
    layout.addWidget(every)
    root.show()
    try:
        entries = capture.field_entries(root)
        assert [(entry["label"], entry["front"]) for entry in entries] == [
            ("Breite", True),
            ("Tiefe", False),
        ]
    finally:
        root.close()


def test_the_feature_window_names_every_field_it_counts(qt_app: Any) -> None:
    """Am echten Merkmalfenster einer Bohrung: kein gezähltes Feld ohne Namen (FD-102)."""
    from PySide6.QtWidgets import QVBoxLayout, QWidget

    from app.core.bootstrap import load_operations
    from app.core.types import Feature
    from app.ui.panels import FeaturePanel

    load_operations()
    host = QWidget()
    body = QVBoxLayout(host)
    panel = FeaturePanel()
    body.addWidget(panel)
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
    host.resize(420, 1400)
    host.show()
    try:
        for op in ("move_feature", "duplicate_feature"):
            row = next(row for row in panel._shown_rows.values() if row.op == op)
            row.toggle.click()
            qt_app.processEvents()
            surface = row.toggle.parentWidget()
            # Die Knopfzeile wohnt seit FD-136 im Merkmalfenster unter der offenen Handlung.
            entries = [*capture.field_entries(surface), *capture.field_entries(panel._footer)]
            assert entries, op
            unnamed = [e for e in entries if not e["label"] and not e["accessible_name"]]
            assert unnamed == [], (op, unnamed)
            row.toggle.click()
            qt_app.processEvents()
    finally:
        host.close()


# --- FD-110: eine umbrochene Zeile, die nicht in ihre Zelle passt ----------------------


LONG = "Ein Objekt steckt unter dem Druckbett. · cube_clean · Überstand: 10,00 mm"


def _list(qt_app: Any, text: str, *, wrap: bool, lines: int, width: int = 220) -> Any:
    """Eine Liste mit einer Zeile so hoch wie ``lines`` Textzeilen — wie die Befundliste."""
    from PySide6.QtCore import QSize
    from PySide6.QtWidgets import QListWidget, QListWidgetItem, QVBoxLayout, QWidget

    host = QWidget()
    listing = QListWidget(host)
    QVBoxLayout(host).addWidget(listing)
    listing.setWordWrap(wrap)
    item = QListWidgetItem(text)
    item.setSizeHint(QSize(width, listing.fontMetrics().lineSpacing() * lines + 2))
    listing.addItem(item)
    listing.setFixedSize(width + 2 * listing.frameWidth(), 200)
    host.show()
    qt_app.processEvents()
    return host


def _cell(listing: Any) -> dict[str, Any]:
    (entry,) = [e for e in capture.text_entries(listing) if e["carrier"].endswith(".Zeile")]
    return entry


def test_a_wrapped_row_too_low_for_its_lines_is_cut(qt_app: Any) -> None:
    """Die Befundzeile „… Überstand: 10,00 …“ (FD-109) hieß an Stufe A ``cut=false``.

    Eine umbrechende Liste brauchte nur ihr längstes Wort (F-15); dass die
    Zeile dafür zu niedrig ist und die letzte Zeile gekürzt wird, sah die
    Messung nicht (FD-110, Lauf 002/04-fehlfall).
    """
    listing = _list(qt_app, LONG, wrap=True, lines=1)
    try:
        entry = _cell(listing)
        assert entry["cut"] is True, entry
        assert entry["axis"] == "hoehe" and entry["need_px"] > entry["width_px"], entry
    finally:
        listing.close()


def test_a_wrapped_row_tall_enough_and_a_short_row_are_not_cut(qt_app: Any) -> None:
    """Gegenfälle: genug Zeilen für den Umbruch, und eine kurze Zeile."""
    for text, lines in ((LONG, 8), ("Kurz", 1)):
        listing = _list(qt_app, text, wrap=True, lines=lines)
        try:
            entry = _cell(listing)
            assert entry["cut"] is False, entry
        finally:
            listing.close()


def test_a_row_without_wrapping_is_measured_across(qt_app: Any) -> None:
    """Ohne Umbruch zählt die Breite wie bisher — und eine kurze Zeile passt."""
    listing = _list(qt_app, LONG, wrap=False, lines=1)
    try:
        entry = _cell(listing)
        assert entry["cut"] is True and entry["axis"] == "breite", entry
    finally:
        listing.close()
    listing = _list(qt_app, "Kurz", wrap=False, lines=1)
    try:
        assert _cell(listing)["cut"] is False
    finally:
        listing.close()


# --- FD-141: Name wie ein Bildschirmleser ihn liest, Zielhandlung erkannt -------------


def test_the_chain_names_what_a_screen_reader_reads_and_finds_the_target(qt_app: Any) -> None:
    """Eine Zahl heißt nach ihrer Formularzeile, eine Rollfläche ohne Namen hat keinen.

    Vorher fiel der Name auf Kennzeichen und Klasse zurück: „FittedScroller“ und
    „DialogScrollArea“ standen als Namen in der Kette (FD-141, Lauf 001, 002).
    Der Hauptknopf ist die Zielhandlung, ein Wortschatzname nennt sie ebenfalls.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import (
        QApplication,
        QDoubleSpinBox,
        QFormLayout,
        QPushButton,
        QScrollArea,
        QVBoxLayout,
        QWidget,
    )

    from app.core.guides import TARGET_PROPERTY

    root = QWidget()
    layout = QVBoxLayout(root)
    form_holder = QWidget(root)
    form = QFormLayout(form_holder)
    width = QDoubleSpinBox(form_holder)
    form.addRow("Breite", width)
    layout.addWidget(form_holder)
    scroller = QScrollArea(root)
    scroller.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    layout.addWidget(scroller)
    accept = QPushButton("Übernehmen", root)
    accept.setDefault(True)
    accept.setProperty(TARGET_PROPERTY, "feature.apply")
    layout.addWidget(accept)
    root.show()
    try:
        width.setFocus()
        qt_app.processEvents()
        chain = capture.tab_chain(
            root, lambda: QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Tab)
        )
        links = {entry["class"]: entry for entry in chain}
        assert links["QDoubleSpinBox"]["name"] == "Breite", chain
        assert links["QScrollArea"]["name"] == "", chain
        assert links["QPushButton"]["name"] == "Übernehmen"
        assert links["QPushButton"]["primary"] is True
        assert links["QPushButton"]["mark"] == "feature.apply"
        assert links["QDoubleSpinBox"]["primary"] is False
    finally:
        root.close()


# --- FD-149: der Sperrgrund eines grauen Knopfs als eigenes Bild ----------------------


def test_the_reason_of_a_grey_button_becomes_its_own_picture(qt_app: Any, tmp_path: Any) -> None:
    """Lauf 002: Der Sperrgrund stand nur im Protokoll, nicht im Bild des Fehlfalls."""
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

    from tools import function_tooltips

    root = QWidget()
    layout = QVBoxLayout(root)
    grey = QPushButton("Auf das Bett setzen", root)
    grey.setToolTip("Erst nach der Berechnung — der Befund gehört zum vorigen Stand.")
    grey.setEnabled(False)
    silent = QPushButton("Ohne Grund", root)
    silent.setEnabled(False)
    open_ = QPushButton("Offen", root)
    open_.setToolTip("Ein offener Knopf hat keinen Sperrgrund.")
    for button in (grey, silent, open_):
        layout.addWidget(button)
    root.show()
    qt_app.processEvents()
    folder = tmp_path / "cases" / "002"
    folder.mkdir(parents=True)
    try:
        found = {"grau": grey, "stumm": silent, "offen": open_}
        images = function_tooltips.reason_pictures(
            found.get, ["grau", "stumm", "offen", "fehlt"], folder, tmp_path
        )
        assert images == ["cases/002/04-fehlfall-grund-1.png"]
        picture = QImage(str(tmp_path / images[0]))
        assert not picture.isNull() and picture.width() > 0
        assert function_tooltips._shown_tip() is None, "die Kurzhilfe ist danach wieder weg"
    finally:
        root.close()


def test_a_grey_button_without_a_tip_has_no_picture_of_one(qt_app: Any, tmp_path: Any) -> None:
    """RC-7: Die zugängliche Beschreibung zeigt Qt beim Überfahren nicht.

    Das Bild zeigte sie trotzdem als Kurzhilfe; Stufe B sähe einen Grund, den der
    Kunde nicht sieht. Ohne Kurzhilfe kein Bild, und ``silent`` nennt das Ziel.
    """
    from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

    from tools import function_tooltips

    root = QWidget()
    layout = QVBoxLayout(root)
    described = QPushButton("Schlüssel prüfen", root)
    described.setAccessibleDescription(
        "Der aktive Lizenzschlüssel kann nicht überschrieben werden."
    )
    described.setEnabled(False)
    layout.addWidget(described)
    root.show()
    qt_app.processEvents()
    folder = tmp_path / "cases" / "003"
    folder.mkdir(parents=True)
    silent: list[str] = []
    try:
        images = function_tooltips.reason_pictures(
            {"grau": described}.get, ["grau"], folder, tmp_path
        )
        assert images == []
        assert not (folder / "04-fehlfall-grund-1.png").exists()
        function_tooltips.reason_pictures(
            {"grau": described}.get, ["grau"], folder, tmp_path, silent=silent.append
        )
        assert silent == ["grau"]
    finally:
        root.close()
