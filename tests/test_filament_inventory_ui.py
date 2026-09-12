"""Kundenwege im Filamentlager ohne Geometrie und ohne 3D-Kontext."""

from __future__ import annotations

from pathlib import Path
from threading import Event
from time import monotonic

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from app.core.errors import ValidationError
from app.core.knowledge import filaments
from app.ui.filament_inventory import InventoryView, SlicerSpoolDialog, SpoolCard
from app.ui.filament_picker import NewFilamentDialog


def _wait_for_action(view: InventoryView) -> None:
    """Der echte Arbeiter muss einschließlich seiner Qt-Rückmeldung fertig werden."""
    end = monotonic() + 5
    while view._worker is not None and monotonic() < end:
        QTest.qWait(10)
    assert view._worker is None
    QTest.qWait(20)


@pytest.fixture
def inventory(qt_app: QApplication, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Jeder Kundenweg besitzt ein eigenes echtes Lager auf der Platte."""
    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    view = InventoryView()
    yield view
    view.close()
    view.deleteLater()
    qt_app.processEvents()


def test_empty_shelf_offers_both_entrances(inventory: InventoryView) -> None:
    """Das erste Regal besitzt keine erfundenen Spulen."""
    assert inventory.cards == []
    assert "leer" in inventory.empty.text()
    assert inventory.add_button.isEnabled()
    assert inventory.import_button.isEnabled()
    assert filaments.catalogue() == ()


def test_detail_reads_spool_and_journal_from_one_complete_snapshot(inventory, monkeypatch):
    """Ein Austausch zwischen Lesen und Zeichnen mischt keinen Rest mit einem jüngeren Journal."""
    entry = filaments.save(filaments.CatalogueFilament("Spule", "#112233", remaining_grams=500))
    original = filaments.read_snapshot
    observed = []

    def replace_after_read():
        snapshot = original()
        filaments.book("external", "geometry", [filaments.BookingPosition(entry.identifier, 100)])
        return snapshot

    original_fill = inventory._fill_history

    def remember(shown, bookings):
        observed.append((shown, bookings))
        original_fill(shown, bookings)

    monkeypatch.setattr(filaments, "read_snapshot", replace_after_read)
    monkeypatch.setattr(inventory, "_fill_history", remember)
    inventory.show_spool(entry.identifier)
    assert observed == [(entry, ())]
    assert "Noch keine Buchungen" in inventory.history.item(0).text()
    monkeypatch.setattr(filaments, "read_snapshot", original)
    inventory.show_spool(entry.identifier)
    assert observed[-1][0].remaining_grams == pytest.approx(400)
    assert observed[-1][1][0].operation_id == "external"


def test_damaged_inventory_between_detail_and_edit_keeps_explanation(inventory):
    """Auch ein späterer Detailklick lässt weder Ausnahme noch leeres Regal zurück."""
    entry = filaments.save(filaments.CatalogueFilament("Spule", "#112233"))
    inventory.show_spool(entry.identifier)
    old_history = inventory.history
    filaments.catalogue_path().write_text("{kaputt", encoding="utf-8")
    inventory.show_spool(entry.identifier)
    inventory._edit()
    inventory._archive()
    assert inventory.history is old_history
    assert "Sicherung" in inventory.message.text()
    assert not inventory.retry_button.isHidden()


def test_unknown_is_preserved_when_edit_dialog_opens(qt_app: QApplication) -> None:
    """Öffnen und unverändertes Speichern machen aus unbekannt weder leer noch voll."""
    entry = filaments.CatalogueFilament("Altspule", "#112233", identifier="old")
    dialog = NewFilamentDialog(entry=entry)
    assert dialog.entry().remaining_grams is None
    assert dialog.entry().spool_grams is None
    assert dialog.entry().diameter_mm is None
    assert not dialog.stock_slider.isEnabled()
    assert "unbekannt" in dialog.stock_hint.text()
    assert dialog.entry().identifier == "old"


def test_slider_and_grams_edit_the_same_value(qt_app: QApplication) -> None:
    """Der Schieber besitzt keine zweite, widersprüchliche Bestandszahl."""
    dialog = NewFilamentDialog(name="Spule")
    dialog.spool_weight.setValue(800)
    assert dialog.entry().remaining_grams is None
    dialog.stock_known.setChecked(True)
    dialog.stock_slider.setValue(250)
    assert dialog.entry().remaining_grams == pytest.approx(200)
    dialog.remaining.setValue(600)
    assert dialog.stock_slider.value() == 750
    dialog.stock_known.setChecked(False)
    assert dialog.entry().remaining_grams is None


def test_optional_price_keeps_currency_and_zero(qt_app: QApplication) -> None:
    """Kostenlose Spule und unbekannter Preis sind verschiedene Angaben."""
    dialog = NewFilamentDialog(name="Geschenk")
    assert dialog.entry().price is None
    dialog.price_known.setChecked(True)
    assert not dialog._ok_button.isEnabled()
    dialog.currency.setText("USD")
    assert dialog._ok_button.isEnabled()
    assert dialog.entry().price == pytest.approx(0)
    assert dialog.entry().currency == "USD"


def test_invalid_date_is_explained_before_saving(qt_app: QApplication) -> None:
    """Datumsfelder speichern weder erfundene Daten noch sprachabhängige Werte."""
    dialog = NewFilamentDialog(name="Spule")
    dialog.bought_on.setText("2026-02-30")
    assert not dialog._ok_button.isEnabled()
    assert "Datum" in dialog.validation.text()
    dialog.bought_on.setText("2026-02-28")
    assert dialog._ok_button.isEnabled()
    assert dialog.entry().bought_on == "2026-02-28"


def test_same_labels_remain_individually_selectable(inventory: InventoryView) -> None:
    """Zwei gleichfarbige Etiketten öffnen ihre jeweilige Kennung."""
    first = filaments.save(filaments.CatalogueFilament("PLA", "#ffffff", location="Links"))
    second = filaments.save(filaments.CatalogueFilament("PLA", "#ffffff", location="Rechts"))
    inventory.refresh()
    assert len(inventory.cards) == 2
    assert inventory.cards[0].accessibleName() != inventory.cards[1].accessibleName()
    next(card for card in inventory.cards if card.entry.identifier == second.identifier).click()
    assert inventory._selected_id == second.identifier
    assert inventory._selected_id != first.identifier


def test_search_and_grouping_use_stock_data(inventory: InventoryView) -> None:
    """Ein Kunde findet eine Spule über ihren Lagerort ebenso wie über Material."""
    filaments.save(filaments.CatalogueFilament("Rot", "#cc0000", "PETG", location="Schrank"))
    filaments.save(filaments.CatalogueFilament("Blau", "#0000cc", "PLA", location="Kiste"))
    inventory.refresh()
    inventory.search.setText("schrank")
    assert [card.entry.name for card in inventory.cards] == ["Rot"]
    inventory.grouping.setCurrentIndex(1)
    assert [card.entry.name for card in inventory.cards] == ["Rot"]
    inventory.search.clear()
    assert len(inventory.cards) == 2


def test_spool_drawing_exposes_unknown_stock_as_text(qt_app: QApplication) -> None:
    """Die Farbzeichnung ist keine Voraussetzung, den Bestand zu verstehen."""
    card = SpoolCard(filaments.CatalogueFilament("Unbekannt", "#ffffff"))
    assert "Bestand unbekannt" in card.accessibleName()
    card.resize(240, 250)
    assert not card.grab().isNull()


def test_card_keeps_room_for_location_identity_and_low_stock_after_polish(
    qt_app: QApplication,
) -> None:
    """Die Kartenhöhe bleibt nach dem globalen Knopf-Stylesheet beim gesamten Inhalt."""
    from PySide6.QtGui import QFontMetrics

    from app.ui.style import apply_style
    from app.ui.theme import apply_theme

    apply_theme(qt_app, "dark")
    apply_style(qt_app, "dark")
    card = SpoolCard(
        filaments.CatalogueFilament(
            "Spule",
            "#aabbcc",
            identifier="unique",
            location="Schrank",
            spool_grams=1000,
            remaining_grams=50,
        )
    )
    card.resize(250, 190)
    card.show()
    QApplication.processEvents()
    font = card.font()
    font.setBold(True)
    bottom = 128 + (QFontMetrics(font).height() + 3) * 6
    assert card.minimumHeight() > bottom
    assert card.height() > bottom
    card.close()


def test_journal_timestamp_uses_local_time_without_storage_precision(qt_app: QApplication) -> None:
    """UTC, Sekundenbruchteile und technische ISO-Trenner bleiben in der Datei."""
    from PySide6.QtCore import QDateTime, QLocale

    from app.i18n import get_language
    from app.ui.labels import local_timestamp

    source = "2026-09-08T12:30:18.123456+00:00"
    local = QDateTime.fromString(source, Qt.DateFormat.ISODateWithMs).toLocalTime()
    rendered = local_timestamp(source)
    assert rendered == QLocale(get_language()).toString(local, QLocale.FormatType.ShortFormat)
    assert "123456" not in rendered
    assert "T12:" not in rendered


def test_keyboard_opens_the_selected_spool(inventory: InventoryView) -> None:
    """Enter ist derselbe direkte Kundenweg wie ein Mausklick."""
    entry = filaments.save(filaments.CatalogueFilament("Spule", "#ffffff"))
    inventory.refresh()
    QTest.keyClick(inventory.cards[0], Qt.Key.Key_Return)
    assert inventory._selected_id == entry.identifier
    assert inventory.pages.currentIndex() == 1


def test_archive_and_restore_preserve_the_spool(inventory: InventoryView) -> None:
    """Aus dem aktiven Regal nehmen ist dauerhaft rücknehmbar."""
    entry = filaments.save(filaments.CatalogueFilament("Spule", "#ffffff", remaining_grams=125))
    filaments.archive(entry.identifier)
    inventory.refresh()
    assert not inventory.cards
    inventory.archived.setChecked(True)
    assert inventory.cards[0].entry.identifier == entry.identifier
    assert "Archiviert" in inventory.cards[0].accessibleName()
    filaments.restore(entry.identifier)
    inventory.refresh()
    assert inventory.cards[0].entry.remaining_grams == pytest.approx(125)


def test_duplicate_labels_show_identity_before_opening(inventory: InventoryView) -> None:
    """Eine kurze Kennung steht genau bei den sonst gleichen Etiketten im Regal."""
    filaments.save(filaments.CatalogueFilament("Gleich", "#ffffff"))
    filaments.save(filaments.CatalogueFilament("Gleich", "#ffffff"))
    filaments.save(filaments.CatalogueFilament("Andere", "#334455"))
    inventory.refresh()
    assert all(card.show_identifier for card in inventory.cards if card.entry.name == "Gleich")
    assert not next(card for card in inventory.cards if card.entry.name == "Andere").show_identifier


def test_detail_displays_note_as_plain_text(inventory: InventoryView) -> None:
    """Eine Spulennotiz ist vor dem Bearbeiten lesbar und führt keine HTML-Darstellung ein."""
    from PySide6.QtWidgets import QLabel

    entry = filaments.save(
        filaments.CatalogueFilament("Spule", "#123456", note="<b>Trocken lagern</b>")
    )
    inventory.show_spool(entry.identifier)
    note = next(
        label for label in inventory.detail.findChildren(QLabel) if label.text() == entry.note
    )
    assert note.textFormat() == Qt.TextFormat.PlainText


def test_multi_import_only_takes_checked_spools(qt_app: QApplication) -> None:
    """Der Slicer ist kein Besitznachweis: keine Spule ist vorausgewählt."""
    entries = (
        filaments.CatalogueFilament("PLA One", "#112233", "PLA"),
        filaments.CatalogueFilament("PETG Two", "#223344", "PETG"),
    )
    dialog = SlicerSpoolDialog(entries)
    assert not dialog._ok_button.isEnabled()
    dialog.list.item(0).setCheckState(Qt.CheckState.Checked)
    assert dialog._ok_button.isEnabled()
    assert dialog.chosen_spools() == [entries[0]]
    dialog.list.item(1).setCheckState(Qt.CheckState.Checked)
    assert dialog.chosen_spools() == list(entries)


def test_booking_preference_is_not_written_while_opening(inventory: InventoryView) -> None:
    """Anzeigen der gespeicherten Vorgabe ist keine neue Entscheidung."""
    seen: list[str] = []
    inventory.bookingModeChanged.connect(seen.append)
    inventory.set_booking_mode("never")
    assert not seen
    inventory.booking_mode.setCurrentIndex(inventory.booking_mode.findData("auto"))
    assert seen == ["auto"]


def test_start_card_opens_inventory_without_project(
    qt_app: QApplication, inventory: InventoryView
) -> None:
    """Die erste Spule lässt sich schon vor dem ersten Modell verwalten."""
    from app.ui.start_screen import StartScreen

    screen = StartScreen()
    seen: list[bool] = []
    screen.inventoryRequested.connect(lambda: seen.append(True))
    screen.inventory_button.click()
    assert seen == [True]
    assert screen.inventory_button.accessibleName() == "Filamentlager · 0 Spulen"
    filaments.save(filaments.CatalogueFilament("Spule", "#ffffff"))
    screen.refresh_inventory()
    assert screen.inventory_button.accessibleName() == "Filamentlager · 1 Spule"
    assert screen.inventory_button.caption.text() == "Filamentlager · 1 Spule"
    filaments.save(filaments.CatalogueFilament("Zweite Spule", "#112233"))
    screen.refresh_inventory()
    assert screen.inventory_button.accessibleName() == "Filamentlager · 2 Spulen"
    assert screen.inventory_button.caption.text() == "Filamentlager · 2 Spulen"


def test_edit_preserves_identifier_and_other_same_named_spool(
    inventory: InventoryView, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der alte Namensschlüssel darf weder die zweite Spule ändern noch den Rest verlieren."""
    from PySide6.QtWidgets import QDialog

    first = filaments.save(filaments.CatalogueFilament("Doppelt", "#123456", remaining_grams=250))
    other = filaments.save(filaments.CatalogueFilament("Doppelt", "#123456", remaining_grams=600))
    inventory.show_spool(first.identifier)

    def accept(dialog: NewFilamentDialog) -> int:
        dialog.name.setText("Umbenannt")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(NewFilamentDialog, "exec", accept)
    inventory._edit()
    _wait_for_action(inventory)
    assert filaments.get(first.identifier).name == "Umbenannt"
    assert filaments.get(first.identifier).remaining_grams == pytest.approx(250)
    assert filaments.get(other.identifier).remaining_grams == pytest.approx(600)


def test_duplicate_opens_new_unknown_spool(inventory: InventoryView) -> None:
    """Noch eine davon erzeugt ein eigenes Exemplar und kopiert keinen physischen Rest."""
    entry = filaments.save(filaments.CatalogueFilament("Spule", "#123456", remaining_grams=250))
    inventory.show_spool(entry.identifier)
    inventory._duplicate()
    _wait_for_action(inventory)
    assert inventory._selected_id != entry.identifier
    assert filaments.get(inventory._selected_id).remaining_grams is None
    assert filaments.bookings(inventory._selected_id) == ()


def test_journal_shows_source_correction_and_reverses_entire_operation(
    inventory: InventoryView,
) -> None:
    """Ein Klick nimmt beide Spulen zurück, einschließlich der späteren G-Code-Korrektur."""
    first = filaments.save(filaments.CatalogueFilament("Erste", "#123456", remaining_grams=200))
    second = filaments.save(filaments.CatalogueFilament("Zweite", "#654321", remaining_grams=300))
    filaments.book(
        "operation",
        "fingerprint",
        [
            filaments.BookingPosition(first.identifier, 20),
            filaments.BookingPosition(second.identifier, 30),
        ],
        project_name="Halter",
    )
    filaments.book(
        "operation",
        "fingerprint",
        [
            filaments.BookingPosition(first.identifier, 25, "gcode"),
            filaments.BookingPosition(second.identifier, 35, "gcode"),
        ],
        project_name="Halter",
    )
    inventory.show_spool(first.identifier)
    assert "G-Code geplant" in inventory.history.item(0).text()
    assert "Korrektur" in inventory.history.item(0).text()
    inventory.history.setCurrentRow(0)
    inventory.reverse_button.click()
    _wait_for_action(inventory)
    assert filaments.get(first.identifier).remaining_grams == pytest.approx(200)
    assert filaments.get(second.identifier).remaining_grams == pytest.approx(300)
    assert "Zurückgenommen" in inventory.history.item(0).text()
    inventory.history.setCurrentRow(0)
    assert not inventory.reverse_button.isEnabled()


def test_newer_stock_count_is_not_overwritten_by_reverse(inventory: InventoryView) -> None:
    """Eine jüngere Wägung bleibt stehen und der Konflikt wird im Regal erklärt."""
    entry = filaments.save(filaments.CatalogueFilament("Spule", "#123456", remaining_grams=200))
    filaments.book("operation", "fingerprint", [filaments.BookingPosition(entry.identifier, 20)])
    filaments.set_remaining(entry.identifier, 123)
    inventory.show_spool(entry.identifier)
    inventory.history.setCurrentRow(0)
    inventory.reverse_button.click()
    _wait_for_action(inventory)
    assert filaments.get(entry.identifier).remaining_grams == pytest.approx(123)
    assert inventory.message.text()
    assert not filaments.bookings(entry.identifier)[0].reversed_at
    assert not inventory.keep_count_button.isHidden()
    inventory.keep_count_button.click()
    _wait_for_action(inventory)
    assert filaments.get(entry.identifier).remaining_grams == pytest.approx(123)
    assert filaments.bookings(entry.identifier)[0].reversed_at
    assert "Bestandsfeststellung beibehalten" in inventory.history.item(0).text()


def test_low_stock_warning_has_text_and_respects_threshold(inventory: InventoryView) -> None:
    """Die Warnung ist beschriftet und ihre Schwelle verändert keine Menge."""
    entry = filaments.save(
        filaments.CatalogueFilament("Spule", "#123456", remaining_grams=150, spool_grams=1000)
    )
    inventory.refresh()
    assert "Wenig Filament" not in inventory.cards[0].accessibleName()
    inventory.set_low_stock_threshold(20)
    assert "Wenig Filament" in inventory.cards[0].accessibleName()
    assert filaments.get(entry.identifier).remaining_grams == pytest.approx(150)


def test_full_spool_is_only_set_by_explicit_action(qt_app: QApplication) -> None:
    """Nennfüllung einzutragen behauptet noch keine volle vorhandene Spule."""
    dialog = NewFilamentDialog(name="Neue Spule")
    dialog.spool_weight.setValue(750)
    assert dialog.entry().remaining_grams is None
    dialog.full_spool_button.click()
    assert dialog.entry().remaining_grams == pytest.approx(750)


def test_replaced_spool_details_hide_before_deferred_deletion(
    inventory: InventoryView, qt_app: QApplication
) -> None:
    """Der nächste Detailaufbau zeigt keine Knöpfe der vorigen Spule mehr."""
    first = filaments.save(filaments.CatalogueFilament("Erste", "#123456"))
    second = filaments.save(filaments.CatalogueFilament("Zweite", "#123456"))
    inventory.show_spool(first.identifier)
    inventory.show()
    qt_app.processEvents()
    old = [
        inventory.detail_layout.itemAt(index).widget()
        for index in range(inventory.detail_layout.count())
        if inventory.detail_layout.itemAt(index).widget() is not None
    ]
    assert old and all(widget.isVisible() for widget in old)
    inventory.show_spool(second.identifier)
    assert all(widget.isHidden() for widget in old)


@pytest.mark.parametrize("first_outcome", ["saved", "rejected", "crashed"])
def test_next_confirmed_spool_is_saved_after_the_current_action(
    inventory: InventoryView, monkeypatch: pytest.MonkeyPatch, first_outcome: str
) -> None:
    """Eine zweite bestätigte Eingabe überlebt Erfolg und Fehler des vorigen Auftrags."""
    started, finish = Event(), Event()
    original_save = filaments.save
    names = iter(("Erste Spule", "Zweite Spule"))

    def accept(dialog: NewFilamentDialog) -> int:
        dialog.name.setText(next(names))
        return QDialog.DialogCode.Accepted

    def save(entry: filaments.CatalogueFilament) -> filaments.CatalogueFilament:
        if entry.name == "Erste Spule":
            started.set()
            assert finish.wait(5)
            if first_outcome == "rejected":
                raise ValidationError("stock", "Bestand prüfen.")
            if first_outcome == "crashed":
                raise OSError("Lagerdatei nicht erreichbar")
        return original_save(entry)

    monkeypatch.setattr(NewFilamentDialog, "exec", accept)
    monkeypatch.setattr(filaments, "save", save)
    try:
        inventory.add_button.click()
        assert started.wait(2)
        inventory.add_button.click()
        assert not inventory.wait_for_workers(0)
    finally:
        finish.set()
        _wait_for_action(inventory)
    expected = {"Zweite Spule"}
    if first_outcome == "saved":
        expected.add("Erste Spule")
    assert {entry.name for entry in filaments.catalogue()} == expected
    assert filaments.get(inventory._selected_id).name == "Zweite Spule"


@pytest.mark.parametrize("search_outcome", ["found", "rejected", "crashed"])
def test_cancelled_search_cannot_finish_the_following_spool_write(
    inventory: InventoryView, monkeypatch: pytest.MonkeyPatch, search_outcome: str
) -> None:
    """Eine verspätete Suchantwort weder öffnet den Import noch beendet sie das Speichern."""
    from app.ui import filament_inventory

    search_started, finish_search = Event(), Event()
    save_started, finish_save = Event(), Event()
    original_save = filaments.save
    changed: list[bool] = []
    inventory.catalogueChanged.connect(lambda: changed.append(True))

    def search() -> tuple[filaments.CatalogueFilament, ...]:
        search_started.set()
        assert finish_search.wait(5)
        if search_outcome == "rejected":
            raise ValidationError("profile", "Profil prüfen.")
        if search_outcome == "crashed":
            raise OSError("Suchpfad nicht erreichbar")
        return ()

    def save(entry: filaments.CatalogueFilament) -> filaments.CatalogueFilament:
        save_started.set()
        assert finish_save.wait(5)
        return original_save(entry)

    def accept(dialog: NewFilamentDialog) -> int:
        dialog.name.setText("Neue Spule")
        return QDialog.DialogCode.Accepted

    monkeypatch.setattr(filament_inventory, "configured_spools", search)
    monkeypatch.setattr(filaments, "save", save)
    monkeypatch.setattr(NewFilamentDialog, "exec", accept)
    try:
        inventory.import_button.click()
        assert search_started.wait(2)
        search_worker = inventory._worker
        inventory._show_wait_progress()
        inventory.cancel_button.click()
        cancelled_message = inventory.message.text()
        inventory.add_button.click()
        assert save_started.wait(2)
        write_worker = inventory._worker
        assert write_worker is not search_worker
        finish_search.set()
        assert search_worker.wait(2000)
        QTest.qWait(20)
        assert inventory._worker is write_worker
        assert not inventory.wait_for_workers(0)
        assert inventory.message.text() == cancelled_message
        assert changed == []
    finally:
        finish_search.set()
        finish_save.set()
        _wait_for_action(inventory)
    assert [entry.name for entry in filaments.catalogue()] == ["Neue Spule"]
    assert changed == [True]


def test_unreadable_inventory_keeps_the_recovery_explanation(inventory: InventoryView) -> None:
    """Eine beschädigte Datei zeigt den vorhandenen Sicherungsweg und bewahrt die letzte Ansicht."""
    from app.core.errors import ValidationError

    entry = filaments.save(filaments.CatalogueFilament("Vorhanden", "#123456"))
    inventory.refresh()
    saved = inventory._entries
    filaments.catalogue_path().write_text('{"format_version": 1, "broken": true}', encoding="utf-8")
    with pytest.raises(ValidationError) as caught:
        filaments.catalogue()
    inventory.refresh()
    assert inventory.message.text() == str(caught.value)
    assert "Sicherung" in inventory.message.text()
    assert inventory._entries == saved and saved[0].identifier == entry.identifier
    assert not inventory.retry_button.isHidden()


def test_unexpected_inventory_read_error_is_reported_and_logged(
    inventory: InventoryView, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Ein Programmfehler beim Lesen wird weder verschwiegen noch zum Schreibfehler umgedeutet."""
    from app.core.errors import InternalError

    def broken(*args, **kwargs):
        raise RuntimeError("inventory-read-probe")

    monkeypatch.setattr(filaments, "catalogue", broken)
    inventory.refresh()
    assert inventory.message.text() == str(
        InternalError(detail="RuntimeError: inventory-read-probe")
    )
    assert "inventory-read-probe" in caplog.text
    assert not inventory.retry_button.isHidden()


def test_spool_cards_do_not_keep_the_inventory_alive(
    qt_app: QApplication,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unpinned_windows,
) -> None:
    """Die echten Spulenkarten halten ihr losgelassenes Lager nicht über den Klickpfad fest."""
    import gc
    import weakref

    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    filaments.save(filaments.CatalogueFilament("Spule", "#123456"))
    references = []
    for _ in range(3):
        view = InventoryView()
        assert view.cards
        view.cards[0].click()
        assert view._selected_id == view.cards[0].entry.identifier
        view.show_shelf()
        references.append(weakref.ref(view))
        view.release()
        del view
    qt_app.processEvents()
    gc.collect()
    try:
        assert all(reference() is None for reference in references)
    finally:
        for reference in references:
            remaining = reference()
            if remaining is not None:
                remaining.deleteLater()
        qt_app.processEvents()
