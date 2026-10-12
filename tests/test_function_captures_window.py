"""Die Fehlalarme des Probelaufs D0, die nur am Fenster zu greifen sind (D0-P2, RM-737).

Die Aufnahmen des Prüfstands (``tools/function_capture.py``) lasen am Probelauf
vom 12.10.2026 Kontrast, Schrift, Abstände, Felder, Symbole, Übergänge und
Textbedarf falsch (F-1 bis F-16 in ``output/konsolidierung-2026-10-12/
auswertung-probelauf-d0.md``); dazu nahm ein Bild nur das modale Fenster auf
(F-31). Je Fehlalarm ein Fall an echten Widgets, offscreen wie
``tests/conftest.py`` es setzt — am Stand des Laufs rot. Was ohne Fenster geht,
steht in ``test_function_alarms.py``.
"""

from __future__ import annotations

from typing import Any

from tools import function_capture as capture
from tools.function_judges import CRITERION_JUDGES
from tools.function_samples import sample_context, sample_protocol


def _settle(qt_app: Any) -> None:
    for _ in range(10):
        qt_app.processEvents()


def test_contrast_reads_the_ground_the_customer_sees(qt_app: Any) -> None:
    """F-1, F-2, F-3: Der Grund ist, was hinter dem Träger zu sehen ist; Gesperrtes zählt nicht.

    Ein durchsichtiges Etikett und ein Symbolknopf ohne eigenen Grund auf einer
    weißen Fläche: Die Palette nannte Schwarz ohne Deckung, und ``.name()``
    machte daraus ``#000000`` — Kontrast 1,28. Ein gesperrter Knopf ist nach
    WCAG 1.4.3 ausgenommen.
    """
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import QLabel, QPushButton, QToolButton, QVBoxLayout, QWidget

    from app.ui.icons import ThemedIcon

    holder = QWidget()
    holder.setObjectName("weiss")
    holder.setStyleSheet("QWidget#weiss { background: #ffffff; }")
    column = QVBoxLayout(holder)
    label = QLabel("Weitere Einstellungen", holder)
    label.setStyleSheet("background: transparent; color: #1c2026;")
    column.addWidget(label)
    locked = QPushButton("Gesperrt", holder)
    locked.setEnabled(False)
    column.addWidget(locked)
    symbol = QToolButton(holder)
    symbol.setAutoRaise(True)
    symbol.setIcon(QIcon(ThemedIcon("about")))
    symbol.setStyleSheet("background: transparent; border: none;")
    column.addWidget(symbol)
    holder.resize(240, 160)
    holder.show()
    _settle(qt_app)
    try:
        found = {entry["widget"]: entry for entry in capture.contrast_entries(holder, "light")}
    finally:
        holder.close()
        holder.deleteLater()
        _settle(qt_app)
    assert found["Weitere Einstellungen"]["background"] == "#ffffff", found
    assert "Gesperrt" not in found
    symbols = [entry for entry in found.values() if entry["symbol"]]
    assert symbols and symbols[0]["background"] == "#ffffff", symbols


def test_fonts_carry_the_effective_font_of_their_carrier(qt_app: Any) -> None:
    """F-4: Ohne ``level`` steht die wirksame Schrift im Protokoll — die Grundschrift."""
    from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

    from tools.function_judges import _effective_level

    holder = QWidget()
    label = QLabel("Durchmesser", holder)
    QVBoxLayout(holder).addWidget(label)
    holder.show()
    _settle(qt_app)
    try:
        (entry,) = capture.font_entries(holder)
        points = round(label.font().pointSizeF(), 2)
    finally:
        holder.close()
        holder.deleteLater()
        _settle(qt_app)
    assert entry["level"] == ""
    assert entry["base_points"] == QApplication.font().pointSize()
    assert entry["points"] == points
    assert _effective_level(entry) == "body", entry


def test_layouts_are_their_own_groups_and_qts_layouts_stay_out(qt_app: Any) -> None:
    """F-6, F-7, F-8: Je Layout eine Gruppe, Formulare mit zwei Abständen, Qts Layouts nicht.

    Vorher hieß jedes namenlose Widget „QWidget“ und war mit allen anderen eine
    Gruppe; ein Formular mit verschiedenen Abständen stand mit -1 da; Hauptfenster,
    Leiste und Statuszeile lieferten Qts eigene Werte 11, 6 und 1.
    """
    from PySide6.QtWidgets import (
        QFormLayout,
        QHBoxLayout,
        QLabel,
        QLineEdit,
        QMainWindow,
        QVBoxLayout,
        QWidget,
    )

    main = QMainWindow()
    centre = QWidget(main)
    column = QVBoxLayout(centre)
    column.setSpacing(8)
    column.setContentsMargins(12, 12, 12, 12)
    for spacing in (4, 8):
        row = QWidget(centre)
        line = QHBoxLayout(row)
        line.setContentsMargins(0, 0, 0, 0)
        line.setSpacing(spacing)
        line.addWidget(QLabel("a", row))
        line.addWidget(QLabel("b", row))
        column.addWidget(row)
    single = QWidget(centre)
    alone = QVBoxLayout(single)
    alone.setContentsMargins(0, 0, 0, 0)
    alone.addWidget(QLabel("allein", single))
    column.addWidget(single)
    form = QFormLayout()
    form.setContentsMargins(0, 0, 0, 0)
    form.setHorizontalSpacing(12)
    form.setVerticalSpacing(8)
    form.addRow("Breite", QLineEdit(centre))
    form.addRow("Tiefe", QLineEdit(centre))
    column.addLayout(form)
    main.setCentralWidget(centre)
    main.addToolBar("Leiste").addAction("Öffnen")
    main.statusBar().addWidget(QLabel("Bereit"))
    main.resize(500, 400)
    main.show()
    _settle(qt_app)
    try:
        entries = capture.layout_entries(main)
    finally:
        main.close()
        main.deleteLater()
        _settle(qt_app)
    spacing = [entry for entry in entries if entry["kind"] == "spacing"]
    groups = [entry["group"] for entry in spacing]
    assert len(groups) == len(set(groups)), groups
    assert all(entry["spacing"] != -1 for entry in spacing), spacing
    assert {(entry["spacing"], entry["horizontal"]) for entry in spacing} >= {(8, 12)}
    assert any(entry["items"] == 1 for entry in spacing), spacing
    assert len(spacing) == 5, spacing
    protocol = sample_protocol()
    protocol["layout"] = entries
    outcome = CRITERION_JUDGES["G2"](protocol, sample_context())
    assert outcome.verdict == "erfuellt", [issue.text for issue in outcome.issues]


def test_a_field_in_a_holder_reads_the_label_and_tooltip_of_its_row(qt_app: Any) -> None:
    """F-9: Das Drehfeld in einem Behälter trägt Beschriftung und Kurzhilfe seiner Formularzeile.

    So steht ``ValueField`` im Operationsdialog: Der Behälter steht im
    Formular und trägt den Satz, gefunden wird das Drehfeld darin. Die
    zugängliche Beschreibung bleibt die des Drehfelds (E-6 ist echt).
    """
    from PySide6.QtWidgets import QDoubleSpinBox, QFormLayout, QHBoxLayout, QWidget

    dialog = QWidget()
    form = QFormLayout(dialog)
    holder = QWidget(dialog)
    holder.setToolTip("Wie weit das Loch quer gemessen wird.")
    QHBoxLayout(holder).addWidget(QDoubleSpinBox(holder))
    form.addRow("Durchmesser", holder)
    dialog.show()
    _settle(qt_app)
    try:
        (entry,) = capture.field_entries(dialog)
    finally:
        dialog.close()
        dialog.deleteLater()
        _settle(qt_app)
    assert entry["label"] == "Durchmesser"
    assert entry["tooltip"] == "Wie weit das Loch quer gemessen wird."
    assert entry["description"] == ""


def test_only_buttons_with_a_symbol_are_symbol_buttons(qt_app: Any) -> None:
    """F-12: Ein Haken ohne Text und ein Knopf mit Beschriftungen darin sind keine Symbolknöpfe.

    Ein eigenes Symbol (``icons.ThemedIcon``) steht als eigenes da; vorher blieb
    ``own`` offen und galt als fehlend.
    """
    from PySide6.QtGui import QIcon
    from PySide6.QtWidgets import (
        QCheckBox,
        QHBoxLayout,
        QLabel,
        QPushButton,
        QToolButton,
        QVBoxLayout,
        QWidget,
    )

    from app.ui.icons import ThemedIcon

    holder = QWidget()
    column = QVBoxLayout(holder)
    column.addWidget(QCheckBox(holder))
    figures = QPushButton(holder)
    QHBoxLayout(figures).addWidget(QLabel("12 g · 1 h 40 min", figures))
    column.addWidget(figures)
    help_button = QToolButton(holder)
    help_button.setIcon(QIcon(ThemedIcon("about")))
    help_button.setToolTip("Hilfe (F1)")
    column.addWidget(help_button)
    holder.show()
    _settle(qt_app)
    try:
        entries = capture.icon_entries(holder)
    finally:
        holder.close()
        holder.deleteLater()
        _settle(qt_app)
    assert len(entries) == 1, entries
    assert entries[0]["own"] is True, entries


def test_qts_own_layout_animation_is_no_transition(qt_app: Any) -> None:
    """F-13: Die Geometrie, die Qts Hauptfenster am Mittelteil animiert, ist kein Übergang.

    Ein Übergang der Anwendung bleibt, mit Ziel und Eigenschaft.
    """
    from PySide6.QtCore import QPropertyAnimation
    from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel, QMainWindow, QWidget

    main = QMainWindow()
    centre = QWidget(main)
    main.setCentralWidget(centre)
    laid_out = QPropertyAnimation(centre, b"geometry", centre)
    laid_out.setDuration(0)
    note = QLabel("Hinweis", centre)
    effect = QGraphicsOpacityEffect(note)
    note.setGraphicsEffect(effect)
    fading = QPropertyAnimation(effect, b"opacity", note)
    fading.setDuration(150)
    main.show()
    _settle(qt_app)
    try:
        entries = capture.animation_entries(main)
    finally:
        main.close()
        main.deleteLater()
        _settle(qt_app)
    assert [(entry["duration_ms"], entry["property"]) for entry in entries] == [(150.0, "opacity")]


def test_hidden_tabs_wrapping_lists_and_check_boxes_have_their_room(qt_app: Any) -> None:
    """F-14, F-15, F-16: verborgene Reiter, umbrechende Listen und Haken sind nicht abgeschnitten.

    Ein verborgener Reiter hat die Breite 0; eine Liste, die umbricht, braucht
    nur ihr längstes Wort; ein Haken gibt seinem Text, was sein Stil ihm lässt
    — der Prüfstand rechnete 2 px mehr.
    """
    from PySide6.QtWidgets import QCheckBox, QListWidget, QTabBar, QVBoxLayout, QWidget

    from app.ui.style import apply_style
    from app.ui.theme import apply_theme

    application = qt_app
    before = application.styleSheet()
    apply_theme(application, "light")
    apply_style(application, "light")
    holder = QWidget()
    column = QVBoxLayout(holder)
    tabs = QTabBar(holder)
    tabs.addTab("Auswahl")
    tabs.addTab("Tour")
    tabs.setTabVisible(1, False)
    column.addWidget(tabs)
    listing = QListWidget(holder)
    listing.setWordWrap(True)
    listing.addItem("Ein Objekt steckt unter dem Druckbett und braucht einen Klick")
    listing.setFixedWidth(160)
    column.addWidget(listing)
    box = QCheckBox("Mindestwand übernehmen", holder)
    column.addWidget(box)
    holder.show()
    _settle(qt_app)
    try:
        box.adjustSize()
        _settle(qt_app)
        cut = [entry for entry in capture.text_entries(holder) if entry["cut"]]
    finally:
        holder.close()
        holder.deleteLater()
        application.setStyleSheet(before)
        _settle(qt_app)
    assert cut == [], cut


def test_a_picture_takes_every_open_window_also_a_modeless_dialog(qt_app: Any) -> None:
    """F-31: Der nichtmodale Operationsdialog kommt ins Bild; ein Menü nicht."""
    from PySide6.QtWidgets import QDialog, QMainWindow, QMenu

    from tools import function_surface

    main = QMainWindow()
    dialog = QDialog(main)
    dialog.setModal(False)
    menu = QMenu(main)
    menu.addAction("Eintrag")
    main.show()
    dialog.show()
    menu.popup(main.mapToGlobal(main.rect().center()))
    _settle(qt_app)
    try:
        assert menu.isVisible()
        shown = function_surface.windows_to_picture(main)
    finally:
        menu.close()
        dialog.close()
        main.close()
        main.deleteLater()
        _settle(qt_app)
    assert dialog in shown and main not in shown and menu not in shown


def test_a_grey_button_reports_the_reason_its_tooltip_shows(qt_app: Any) -> None:
    """F-34: Als Meldung zählt die Kurzhilfe des grauen Knopfs, nicht seine alte Beschreibung."""
    from PySide6.QtWidgets import QMainWindow, QPushButton

    main = QMainWindow()
    button = QPushButton("Auf das Bett setzen", main)
    main.setCentralWidget(button)
    button.setAccessibleDescription("Nebenfolge: Senkt den Körper bis auf das Bett.")
    button.setToolTip("Erst nach der Berechnung — der Befund gehört zum vorigen Stand.")
    button.setEnabled(False)
    main.show()
    _settle(qt_app)
    try:
        texts = [entry["text"] for entry in capture.message_entries(main)]
    finally:
        main.close()
        main.deleteLater()
        _settle(qt_app)
    assert texts == ["Erst nach der Berechnung — der Befund gehört zum vorigen Stand."], texts
