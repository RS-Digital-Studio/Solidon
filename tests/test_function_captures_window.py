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
    """F-4: Ohne ``level`` steht die wirksame Schrift im Protokoll — die Grundschrift.

    Die Stufe verlangt eine gemessene Familie. Offscreen hat Qt unter Windows
    keine Schrift; die gebündelte DejaVu Sans gibt jeder Plattform eine.
    """
    from pathlib import Path

    from PySide6.QtGui import QFont, QFontDatabase, QFontInfo
    from PySide6.QtWidgets import QApplication, QLabel, QVBoxLayout, QWidget

    from tools.function_judges import _effective_level

    path = Path(__file__).parents[1] / "app/core/geom/data/fonts/DejaVuSans.ttf"
    font_id = QFontDatabase.addApplicationFont(str(path))
    assert font_id >= 0, "Die gebündelte Prüfschrift wurde nicht geladen"
    before = QFont(qt_app.font())
    qt_app.setFont(QFont("DejaVu Sans", 9))
    holder = QWidget()
    label = QLabel("Durchmesser", holder)
    QVBoxLayout(holder).addWidget(label)
    holder.show()
    _settle(qt_app)
    try:
        assert QFontInfo(label.font()).family() == "DejaVu Sans"
        (entry,) = capture.font_entries(holder)
        points = round(label.font().pointSizeF(), 2)
    finally:
        holder.close()
        holder.deleteLater()
        _settle(qt_app)
        qt_app.setFont(before)
        QFontDatabase.removeApplicationFont(font_id)
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


def _watched(qt_app: Any, dialog: Any) -> Any:
    """Die Wache über einem offenen modalen Dialog, wie der Prüfstand sie fährt."""
    watch = capture.ModalWatch(0.0)
    dialog.open()
    _settle(qt_app)
    try:
        watch.poll()
    finally:
        dialog.close()
        dialog.deleteLater()
        _settle(qt_app)
    return watch


def _judged(watch: Any, criterion: str) -> list[str]:
    protocol = sample_protocol()
    protocol["modals"] = watch.modal_entries()
    protocol["raw_windows"] = watch.raw_entries()
    outcome = CRITERION_JUDGES[criterion](protocol, sample_context())
    return [issue.text for issue in outcome.issues]


def test_only_the_questions_of_the_concept_are_modal_without_a_finding(qt_app: Any) -> None:
    """Z2 wie im Konzept (welle4 ``7aaa0b163``): Rückfragen aus ``fenster.md`` und ``ctx.ask``.

    Eine Rückfrage über ``ctx.ask`` ist an ihrer Herkunft ausgenommen: Das
    Hauptfenster zeigt sie aus ``_on_ask`` mit ``exec()``, und die Wache, die in
    dieser Schleife läuft, sieht den Rahmen. Gegenprobe: Derselbe ``AskDialog``
    ohne diese Herkunft — eine Frage der Oberfläche selbst — ist rot (Z2 und E6).
    """
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.ui.dialogs import AskDialog
    from app.ui.main_window import MainWindow
    from app.ui.session import AskRequest, Session
    from app.ui.settings import UiSettings

    other = _watched(qt_app, AskDialog("Welche Fläche ist gemeint?", ["Oben", "Unten"]))
    assert other.modal_entries()[0]["allowed"] is False
    assert _judged(other, "Z2") and _judged(other, "E6")

    window = MainWindow(Session(), UiSettings())
    asked = capture.ModalWatch(0.0)
    seen: list[str] = []

    def look() -> None:
        # In der Schleife des ``exec()`` von ``_on_ask``, wie die Wache des Prüfstands.
        asked.poll()
        question = QApplication.activeModalWidget()
        seen.append(type(question).__name__)
        if question is not None:
            question.reject()

    QTimer.singleShot(200, look)
    try:
        window._on_ask(AskRequest("Welche Fläche ist gemeint?", ["Oben", "Unten"]))
        _settle(qt_app)
    finally:
        window.close()
        window.deleteLater()
        _settle(qt_app)
    assert seen == ["AskDialog"], seen
    assert asked.modal_entries()[0]["allowed"] is True
    assert _judged(asked, "Z2") == [] and _judged(asked, "E6") == []


def test_a_message_in_house_style_is_modal_but_neither_raw_nor_a_question(qt_app: Any) -> None:
    """FD-21: ``MessageDialog`` ist kein rohes Fenster (Z5), aber modal (Z2), keine Frage (E6).

    Mit Handlung und Ausgang hat er zwei Knöpfe; vorher hätte die Wache ihn
    deshalb als Nachfrage gezählt. Und der Klick, nach dem er aufgeht, macht ihn
    nicht zur Fläche der Zeile (``function_surface.own_surface``). Ein Hinweis
    erscheint nie als Meldungsfenster — auch mit Handlung bleibt er ein Z2-Fund;
    ausgenommen ist nur die Fehlermeldung mit Handlungsvorschlag (Fall darunter).
    """
    from app.ui.message_dialog import MessageDialog
    from tools import function_surface

    dialog = MessageDialog(None, title="Hinweis", headline="Das ging", kind="info")
    dialog.add_action("Rückgängig", "message.button:probe.undo", lead=True)
    dialog.add_exit("Schließen", "message.button:probe.close")
    assert not function_surface.own_surface({"target": "operation:drill_hole"}, dialog)
    assert function_surface.own_surface({"target": "message:probe"}, dialog)
    watch = _watched(qt_app, dialog)
    entry = watch.modal_entries()[0]
    assert (entry["class"], entry["allowed"], entry["question"]) == ("MessageDialog", False, False)
    assert watch.raw_entries() == []
    assert _judged(watch, "Z2") and _judged(watch, "Z5") == [] and _judged(watch, "E6") == []


def _shown_error(qt_app: Any, handlers: dict[str, Any]) -> Any:
    """``dialogs.show_error`` am Werk, die Wache in der Schleife seines ``exec()``."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication

    from app.core.errors import RETRY, AppError
    from app.ui.dialogs import show_error

    watch = capture.ModalWatch(0.0)
    rounds = {"left": 50}

    def look() -> None:
        dialog = QApplication.activeModalWidget()
        rounds["left"] -= 1
        if dialog is None and rounds["left"] > 0:
            QTimer.singleShot(100, look)
            return
        watch.poll()
        if dialog is not None:
            dialog.reject()

    QTimer.singleShot(100, look)
    show_error(AppError("Das ging nicht", suggestions=(RETRY,)), None, handlers)
    _settle(qt_app)
    return watch


def test_an_error_with_a_proposal_is_the_exception_to_z2(qt_app: Any) -> None:
    """Durchsicht welle4 D-M2, Entscheidung Koordinator: Die Fehlermeldung nach Regel 17
    mit mindestens einer Handlung antwortet auf eine Handlung des Kunden und darf modal sein.

    Gefahren wird ``dialogs.show_error`` selbst. Vorher war jeder Fehlfall mit
    ``AppError`` ein Z2-Fund, und „Z2 ohne offenen Fund“ war nicht erreichbar.
    Gegenprobe: Dieselbe Meldung ohne einlösbare Handlung — nur *Schließen* —
    bleibt ein Z2-Fund (und an ihrer Meldung E7/V5); der Hinweis darüber ebenso.
    """
    offered = _shown_error(qt_app, {"retry": lambda error: None})
    entry = offered.modal_entries()[0]
    assert (entry["class"], entry["allowed"]) == ("MessageDialog", True), entry
    assert _judged(offered, "Z2") == []
    bare = _shown_error(qt_app, {})
    assert bare.modal_entries()[0]["allowed"] is False, bare.modal_entries()
    assert _judged(bare, "Z2")


def test_a_message_in_house_style_is_read_with_its_actions(qt_app: Any) -> None:
    """V5 an FD-21: Die Meldung im Hausstil zählt mit Text und Handlung, ohne den Ausgang.

    ``message_entries`` las Hinweisrahmen im Hauptfenster und graue Knöpfe; eine
    Meldung als eigenes Fenster fehlte, und ihre Handlung hätte V5 nie geklickt.
    """
    from PySide6.QtWidgets import QMainWindow

    from app.ui.message_dialog import MessageDialog

    main = QMainWindow()
    dialog = MessageDialog(main, title="Fehler", headline="Das ging nicht", kind="error")
    dialog.add_action("Rückgängig", "message.button:probe.undo", lead=True)
    dialog.add_exit("Schließen", "message.button:probe.close")
    main.show()
    dialog.show()
    _settle(qt_app)
    try:
        entries = capture.message_entries(main)
    finally:
        dialog.close()
        main.close()
        main.deleteLater()
        _settle(qt_app)
    house = [entry for entry in entries if "Das ging nicht" in entry["text"]]
    assert len(house) == 1, entries
    assert [action["label"] for action in house[0]["actions"]] == ["Rückgängig"], house
    assert house[0]["actions"][0]["target"] == "message.button:probe.undo", house


def test_a_lock_reason_names_its_way_out_and_a_field_names_its_limit(qt_app: Any) -> None:
    """Prüfpunkt 7 und V5: Jede Absage trägt ihre Art; ein Sperrgrund sagt, ob er den Ausweg nennt.

    Ein grauer Knopf ist ein Sperrgrund — mit Ausweg, wenn der Satz eine
    bedienbare Menüzeile oder einen offenen Knopf nennt („Hilfe → Solidon
    freischalten …“), sonst ohne. Ein Zahlenfeld, das eine getippte Zahl
    ablehnt, ist eine Grenzablehnung (``BoundedSpin.refusal``).
    """
    from PySide6.QtWidgets import QMainWindow, QPushButton, QVBoxLayout, QWidget

    from app.ui.labels import BoundedSpin

    main = QMainWindow()
    body = QWidget()
    column = QVBoxLayout(body)
    unlock = QPushButton("Solidon freischalten …", body)
    named = QPushButton("Auf das Bett setzen", body)
    named.setToolTip(
        "Dafür braucht Solidon einen Lizenzschlüssel (Hilfe → Solidon freischalten …)."
    )
    named.setEnabled(False)
    bare = QPushButton("Exportieren", body)
    bare.setToolTip("Der Testzeitraum ist abgelaufen.")
    bare.setEnabled(False)
    spin = BoundedSpin(body)
    spin.setRange(0.5, 50.0)
    for widget in (unlock, named, bare, spin):
        column.addWidget(widget)
    main.setCentralWidget(body)
    main.show()
    _settle(qt_app)
    spin.lineEdit().setText("0,1")
    _settle(qt_app)
    try:
        entries = capture.message_entries(main)
    finally:
        main.close()
        main.deleteLater()
        _settle(qt_app)
    locks = {entry["text"]: entry["way_out"] for entry in entries if entry["kind"] == "sperrgrund"}
    assert locks == {
        "Dafür braucht Solidon einen Lizenzschlüssel (Hilfe → Solidon freischalten …).": True,
        "Der Testzeitraum ist abgelaufen.": False,
    }, entries
    limits = [entry for entry in entries if entry["kind"] == "grenzablehnung"]
    assert len(limits) == 1 and limits[0]["text"], entries


def test_a_lock_reason_may_name_an_open_field_of_its_own_surface(qt_app: Any) -> None:
    """FD-31, Entscheidung Koordinator: Ein Sperrgrund, der ein offenes Eingabefeld seiner
    Fläche beim Titel nennt („Erst „Durchmesser“ ändern, dann übernehmen.“), nennt den
    Ausweg — *Übernehmen* der Maßgruppe ist vor der ersten Eingabe grau.

    Gegenprobe im selben Fall: Derselbe Satz an einem grauen Feld oder an einem Feld
    einer anderen Fläche bleibt ein Sperrgrund ohne Ausweg.
    """
    from PySide6.QtWidgets import (
        QDoubleSpinBox,
        QFormLayout,
        QFrame,
        QMainWindow,
        QPushButton,
        QVBoxLayout,
        QWidget,
    )

    def card(parent: QWidget, title: str, reason: str, *, open_field: bool) -> QFrame:
        frame = QFrame(parent)
        frame.setAutoFillBackground(True)
        form = QFormLayout(frame)
        field = QDoubleSpinBox(frame)
        field.setEnabled(open_field)
        form.addRow(f"{title}:", field)
        accept = QPushButton("Übernehmen", frame)
        accept.setToolTip(reason)
        accept.setEnabled(False)
        form.addRow(accept)
        return frame

    main = QMainWindow()
    body = QWidget()
    column = QVBoxLayout(body)
    own = "Erst „Durchmesser“ ändern, dann übernehmen."
    grey = "Erst „Breite“ ändern, dann übernehmen."
    foreign = "Erst „Tiefe“ ändern, dann übernehmen."
    column.addWidget(card(body, "Durchmesser", own, open_field=True))
    column.addWidget(card(body, "Breite", grey, open_field=False))
    column.addWidget(card(body, "Tiefe", "Tiefe angeben.", open_field=True))
    column.addWidget(card(body, "Höhe", foreign, open_field=True))
    main.setCentralWidget(body)
    main.show()
    _settle(qt_app)
    try:
        entries = capture.message_entries(main)
    finally:
        main.close()
        main.deleteLater()
        _settle(qt_app)
    locks = {entry["text"]: entry["way_out"] for entry in entries if entry["kind"] == "sperrgrund"}
    assert locks[own] is True, locks
    assert locks[grey] is False and locks[foreign] is False, locks
