"""Kundenwege im Filamentlager ohne Geometrie und ohne 3D-Kontext."""

from __future__ import annotations

from dataclasses import replace
from functools import partial
from pathlib import Path
from threading import Event
from time import monotonic

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QMenu

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


def _stock_conflict(view: InventoryView):
    """Zwei Vorgänge der ersten Spule liegen vor einer jüngeren Bestandsfeststellung."""
    first = filaments.save(filaments.CatalogueFilament("Erste", "#123456", remaining_grams=200))
    second = filaments.save(filaments.CatalogueFilament("Zweite", "#654321", remaining_grams=300))
    for identifier, entry in (("first", first), ("second", first), ("other", second)):
        filaments.book(identifier, identifier, [filaments.BookingPosition(entry.identifier, 20)])
    filaments.set_remaining(first.identifier, 150)
    view.show_spool(first.identifier)
    view.history.setCurrentRow(0)
    return first, second


@pytest.mark.parametrize("change", ["spool", "shelf", "filter", "history"])
def test_stock_conflict_exception_does_not_follow_selection(inventory, change):
    """Die bewahrende Rücknahme darf nie über einen anderen Vorgang ausgelöst werden."""
    _first, second = _stock_conflict(inventory)
    inventory.reverse_button.click()
    _wait_for_action(inventory)
    assert not inventory.keep_count_button.isHidden()
    assert inventory.message.text()
    if change == "spool":
        inventory.show_spool(second.identifier)
        inventory.history.setCurrentRow(0)
    elif change == "shelf":
        inventory.show_shelf()
    elif change == "filter":
        inventory.search.setText("Erste")
    else:
        inventory.history.setCurrentRow(1)
    assert inventory.keep_count_button.isHidden()
    assert not inventory.message.text()
    inventory._reverse_preserving_counts()
    assert all(not booking.reversed_at for booking in filaments.bookings())


def test_stock_conflict_exception_keeps_its_exact_operation(inventory):
    """Der zweite bewusste Klick behält den gezählten Bestand und nimmt nur den Anlass zurück."""
    first, _second = _stock_conflict(inventory)
    identifier = inventory.history.currentItem().data(Qt.ItemDataRole.UserRole)
    inventory.reverse_button.click()
    _wait_for_action(inventory)
    inventory.keep_count_button.click()
    _wait_for_action(inventory)
    reversed_ids = {booking.operation_id for booking in filaments.bookings() if booking.reversed_at}
    assert reversed_ids == {identifier}
    assert filaments.get(first.identifier).remaining_grams == pytest.approx(150)


def test_late_stock_conflict_does_not_reopen_exception_on_another_spool(inventory, monkeypatch):
    """Ein noch arbeitender alter Klick liefert keine Ausnahme in das inzwischen neue Detail."""
    _first, second = _stock_conflict(inventory)
    entered, released = Event(), Event()
    original = filaments.reverse_booking

    def delayed(*args, **kwargs):
        entered.set()
        assert released.wait(3)
        return original(*args, **kwargs)

    monkeypatch.setattr(filaments, "reverse_booking", delayed)
    inventory.reverse_button.click()
    try:
        assert entered.wait(1)
        inventory.show_spool(second.identifier)
        inventory.history.setCurrentRow(0)
    finally:
        released.set()
        _wait_for_action(inventory)
    assert inventory.keep_count_button.isHidden()
    # Die Absage geht nicht verloren (B6), sie nennt nur ihre Spule — das
    # Angebot „mit aktuellem Bestand" bleibt an der Ansicht gebunden.
    assert inventory.message.text().startswith("Erste: ")
    assert "neu festgestellt" in inventory.message.text()
    assert all(not booking.reversed_at for booking in filaments.bookings())


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


def test_delete_button_removes_selected_spool_and_keeps_its_history(inventory):
    """Der sichtbare Mülleimer räumt das Regal auf und bewahrt den Rückweg."""
    entry = filaments.save(
        filaments.CatalogueFilament("Eigene Mischung", "#123456", remaining_grams=100)
    )
    filaments.book("print", "geometry", [filaments.BookingPosition(entry.identifier, 20)])
    inventory.refresh()
    inventory.cards[0].click()
    assert not inventory.add_button.icon().isNull()
    assert not inventory.delete_button.icon().isNull()
    inventory.delete_button.click()
    _wait_for_action(inventory)
    assert inventory.pages.currentIndex() == 0
    assert inventory.cards == []
    assert filaments.get(entry.identifier).archived
    assert len(filaments.bookings(entry.identifier)) == 1
    inventory.archived.setChecked(True)
    inventory.cards[0].click()
    inventory.delete_button.click()
    _wait_for_action(inventory)
    assert filaments.catalogue()[0].identifier == entry.identifier


def test_card_context_delete_targets_clicked_spool(inventory, monkeypatch):
    """Gleiche Etiketten und ein anderes offenes Detail dürfen das Löschziel nicht ändern."""
    from app.ui import filament_inventory

    first = filaments.save(filaments.CatalogueFilament("Eigene Spule", "#123456"))
    second = filaments.duplicate(first.identifier)
    inventory.refresh()
    inventory.show_spool(first.identifier)

    class ChoosingMenu(QMenu):
        def exec(self, _position):
            assert self.toolTipsVisible()
            action = next(
                action for action in self.actions() if action.text() == "Filament löschen"
            )
            assert not action.icon().isNull()
            action.trigger()

    monkeypatch.setattr(filament_inventory, "QMenu", ChoosingMenu)
    card = next(card for card in inventory.cards if card.entry.identifier == second.identifier)
    card.customContextMenuRequested.emit(QPoint(5, 5))
    _wait_for_action(inventory)
    assert filaments.get(second.identifier).archived
    assert not filaments.get(first.identifier).archived
    assert inventory._selected_id == first.identifier


def test_failed_delete_keeps_the_spool_visible(inventory, monkeypatch):
    """Ein Schreibfehler darf weder die Spule noch den Wiederholungsweg ausblenden."""
    from app.core.errors import FileWriteError

    entry = filaments.save(filaments.CatalogueFilament("Eigene Spule", "#123456"))
    inventory.refresh()
    inventory.cards[0].click()

    def reject(_identifier):
        raise FileWriteError(detail="Datei gesperrt")

    monkeypatch.setattr(filaments, "archive", reject)
    inventory.delete_button.click()
    _wait_for_action(inventory)
    assert not filaments.get(entry.identifier).archived
    assert inventory._selected_id == entry.identifier
    assert inventory.message.text()
    assert inventory.delete_button.isEnabled()


def test_delete_preserves_error_if_refresh_cannot_read_inventory(inventory, monkeypatch):
    """Ein Fehler nach dem Speichern darf nicht hinter dem Rückweghinweis verschwinden."""
    entry = filaments.save(filaments.CatalogueFilament("Spule", "#123456"))
    inventory.show_spool(entry.identifier)

    def unreadable(**_kwargs):
        raise ValidationError(field="inventory", detail="Lagerdatei gesperrt")

    monkeypatch.setattr(filaments, "catalogue", unreadable)
    inventory.delete_button.click()
    _wait_for_action(inventory)
    assert filaments.get(entry.identifier).archived
    assert "Lagerdatei gesperrt" in inventory.message.text()
    assert not inventory.retry_button.isHidden()


def test_inventory_summary_distinguishes_zero_one_and_many(inventory):
    """Die tatsächliche Spulenzahl bestimmt Leerzustand, Einzahl und Mehrzahl."""
    assert inventory.summary.text() == "Noch keine Spule eingetragen"
    for count in (1, 2):
        filaments.save(filaments.CatalogueFilament(f"Spule {count}", "#123456"))
        inventory.refresh()
        assert inventory.summary.text() == (
            "Eine Spule im Lager" if count == 1 else "2 Spulen im Lager"
        )


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


def test_the_hatching_means_unknown_and_nothing_else() -> None:
    """Bekannter Rest ohne Nennfüllung: kein Schraffur-„unbekannt" neben „300 g übrig" (R3)."""
    from app.ui.filament_inventory import coil_fill

    assert coil_fill(filaments.CatalogueFilament("A", "#111111")) == (False, 0.7)
    assert coil_fill(filaments.CatalogueFilament("A", "#111111", remaining_grams=300)) == (
        True,
        0.7,
    )
    known, ratio = coil_fill(
        filaments.CatalogueFilament("A", "#111111", remaining_grams=250, spool_grams=1000)
    )
    assert known and ratio == pytest.approx(0.25)
    assert coil_fill(filaments.CatalogueFilament("A", "#111111", remaining_grams=0)) == (True, 0.0)


def test_long_names_wrap_before_they_are_cut_in_the_middle(qt_app: QApplication) -> None:
    """Zwei Polymaker-Spulen verschiedener Farbe bleiben am Namen unterscheidbar (R4)."""
    from PySide6.QtGui import QFontMetrics

    from app.ui.filament_inventory import name_lines

    metrics = QFontMetrics(qt_app.font())
    width = metrics.horizontalAdvance("Polymaker PolyTerra PLA")
    assert name_lines("PLA Rot", metrics, width) == ["PLA Rot"]
    lines = name_lines("Polymaker PolyTerra PLA Matte Rot", metrics, width)
    assert len(lines) == 2 and lines[0].startswith("Polymaker") and lines[1].endswith("Rot")
    lines = name_lines("Polymaker PolyTerra PLA Matte Lavendel Himmelblau Metallic", metrics, width)
    assert len(lines) == 2 and lines[1].endswith("Metallic") and "…" in lines[1]
    (single,) = name_lines("EinWortOhneJedeLückeDasVielZuLangIst", metrics, width)
    assert "…" in single and single.endswith("Ist")


def test_detail_hides_the_outer_back_and_escape_walks_back(inventory: InventoryView) -> None:
    """Im Detail gibt es einen Zurück-Knopf, und Esc geht denselben Weg (B4, B9)."""
    entry = filaments.save(filaments.CatalogueFilament("Spule", "#123456"))
    inventory.show()
    left: list[bool] = []
    inventory.backRequested.connect(lambda: left.append(True))
    assert not inventory.back_button.isHidden()
    inventory.show_spool(entry.identifier)
    assert inventory.back_button.isHidden()
    assert inventory.add_button.isHidden()
    inventory._escape()
    assert inventory.pages.currentIndex() == 0
    assert not inventory.back_button.isHidden()
    assert left == []
    inventory._escape()
    assert left == [True]
    inventory.close()


def test_detail_names_stock_dates_and_price_as_facts(inventory: InventoryView) -> None:
    """Preis, Kauf- und Öffnungsdatum stehen auf der Detailseite, nicht nur im Dialog (B5)."""
    from PySide6.QtWidgets import QLabel

    entry = filaments.save(
        filaments.CatalogueFilament(
            "Spule",
            "#123456",
            remaining_grams=321.5,
            bought_on="2026-09-05",
            price=24.9,
            currency="EUR",
        )
    )
    inventory.show_spool(entry.identifier)
    texts = [label.text() for label in inventory.detail.findChildren(QLabel)]
    assert "Restmenge" in texts and "321,5 g übrig" in texts
    assert "Gekauft am" in texts and any("2026" in text and "September" in text for text in texts)
    assert "Geöffnet am" in texts and "Unbekannt" in texts
    assert "Spulenpreis" in texts and "24,90 EUR" in texts


def test_empty_shelf_puts_both_ways_in_the_middle_and_hides_the_filters(
    inventory: InventoryView,
) -> None:
    """Ohne eine Spule gibt es nichts zu suchen; die zwei Wege stehen beim Satz (B8)."""
    inventory.show()
    assert inventory.filters.isHidden()
    assert not inventory.empty_actions.isHidden()
    assert inventory.import_button.isHidden()
    assert inventory.empty_add_button.isEnabled() and inventory.empty_import_button.isEnabled()
    filaments.save(filaments.CatalogueFilament("Spule", "#123456"))
    inventory.refresh()
    assert not inventory.filters.isHidden()
    assert inventory.empty_panel.isHidden()
    assert not inventory.import_button.isHidden()
    inventory.search.setText("gibt es nicht")
    assert not inventory.empty_panel.isHidden()
    assert inventory.empty_actions.isHidden(), "eine Suche ohne Treffer behält die Suchleiste"
    assert not inventory.filters.isHidden()
    inventory.close()


def test_summary_counts_archived_spools_separately(inventory: InventoryView) -> None:
    """„3 Spulen im Lager" zählte Archivierte mit (T4)."""
    for name in ("Eine", "Zwei", "Drei"):
        filaments.save(filaments.CatalogueFilament(name, "#123456"))
    filaments.archive(filaments.catalogue()[0].identifier)
    inventory.archived.setChecked(True)
    inventory.refresh()
    assert inventory.summary.text() == "2 Spulen im Lager, 1 archiviert"
    inventory.archived.setChecked(False)
    inventory.refresh()
    assert inventory.summary.text() == "2 Spulen im Lager"


def test_booking_mode_has_a_visible_label(inventory: InventoryView) -> None:
    """Die Combobox „Nachfragen" sagt, wonach (B1)."""
    from PySide6.QtWidgets import QLabel

    labels = [
        label for label in inventory.findChildren(QLabel) if label.buddy() is inventory.booking_mode
    ]
    assert [label.text() for label in labels] == ["Nach einer Ausgabe an den Slicer buchen"]


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


def test_editing_only_the_label_keeps_the_exact_stock_and_the_reversal(inventory) -> None:
    """Die Anzeige rundet auf eine Nachkommastelle; gespeichert wird nicht die Rundung.

    Befund 19.09.2026: Rest 49,34 g, „Angaben ändern" ohne Berührung des
    Bestands → der Dialog gab 49,3 zurück, der Kern zählte das als neue
    Bestandsfeststellung, und die Rücknahme der Buchung war gesperrt.
    """
    entry = filaments.save(filaments.CatalogueFilament("PETG Rot", "#d02020", remaining_grams=1000))
    filaments.book("op-1", "geometry", [filaments.BookingPosition(entry.identifier, 950.66)])
    stored = filaments.get(entry.identifier)
    assert stored is not None
    assert stored.remaining_grams == pytest.approx(49.34)
    dialog = NewFilamentDialog(entry=stored)
    dialog.location.setText("Regal 2")
    edited = dialog.entry()
    assert edited.remaining_grams == pytest.approx(49.34)
    saved = filaments.save(edited)
    assert saved.stock_revision == stored.stock_revision
    assert saved.location == "Regal 2"
    filaments.reverse_booking("op-1")
    restored = filaments.get(entry.identifier)
    assert restored is not None
    assert restored.remaining_grams == pytest.approx(1000)
    # Ein Griff an den Bestand zählt weiterhin als Feststellung.
    dialog = NewFilamentDialog(entry=restored)
    dialog.remaining.setValue(980)
    counted = filaments.save(dialog.entry())
    assert counted.stock_revision == restored.stock_revision + 1
    assert counted.remaining_grams == pytest.approx(980)


def test_full_spool_button_counts_even_when_the_number_stays(inventory) -> None:
    """„Als volle Spule eintragen" ist eine Bestandsfeststellung, auch bei gleicher Zahl."""
    entry = filaments.save(
        filaments.CatalogueFilament("PLA", "#111111", remaining_grams=1000, spool_grams=1000)
    )
    dialog = NewFilamentDialog(entry=entry)
    dialog.full_spool_button.click()
    assert dialog.entry().remaining_grams == pytest.approx(1000)
    assert dialog._stock_edited


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
    """Datumsfelder speichern weder erfundene Daten noch sprachabhängige Werte.

    Seit dem Kalenderfeld (B7, 19.09.2026) lässt sich ein erfundenes Datum
    gar nicht mehr eintragen: Es bleibt „Unbekannt", und gespeichert wird
    ISO — gleich, in welcher Sprache getippt wurde.
    """
    dialog = NewFilamentDialog(name="Spule")
    dialog.bought_on.setText("2026-02-30")
    assert dialog._ok_button.isEnabled()
    assert dialog.entry().bought_on == ""
    assert dialog.bought_on.editor.text() == "Unbekannt"
    dialog.bought_on.setText("2026-02-28")
    assert dialog._ok_button.isEnabled()
    assert dialog.entry().bought_on == "2026-02-28"
    assert dialog.bought_on.clear_button.isEnabled()
    dialog.bought_on.clear_button.click()
    assert dialog.entry().bought_on == ""


def test_the_date_is_typed_in_the_language_of_the_app(qt_app: QApplication) -> None:
    """Ein deutscher Kunde tippt 05.09.2026 — und genau das nimmt das Feld (B7)."""
    from PySide6.QtTest import QTest

    from app.i18n import get_language, set_language

    before = get_language()
    set_language("de")
    try:
        dialog = NewFilamentDialog(name="Spule")
        dialog.show()
        assert dialog.focus_field("bought_on")
        assert dialog.bought_on.editor.displayFormat() == "dd.MM.yyyy"
        assert dialog.bought_on.editor.text() == "Unbekannt"
        # Lostippen ab „Unbekannt", mit oder ohne Punkte, auch einstellig.
        for typed, expected in (
            ("05092026", "2026-09-05"),
            ("31.12.2024", "2024-12-31"),
            ("7.3.2025", "2025-03-07"),
        ):
            dialog.bought_on.clear()
            QTest.keyClicks(dialog.bought_on.editor, typed)
            assert dialog.entry().bought_on == expected, typed
        dialog.close()
    finally:
        set_language(before)


@pytest.mark.parametrize("text", ["20260905", "2026-W36-5", "05.09.2026", "2026-2-3"])
def test_dialog_rejects_every_date_form_the_core_rejects(qt_app: QApplication, text: str) -> None:
    """Was der Dialog speichert, nimmt der Kern an — dieselbe Prüfung an beiden Stellen."""
    dialog = NewFilamentDialog(name="Spule")
    dialog.bought_on.setText(text)
    assert dialog.entry().bought_on == ""
    assert filaments.valid_date(dialog.entry().bought_on or "2026-09-05")
    assert not filaments.valid_date(text)
    with pytest.raises(ValidationError) as rejected:
        filaments.save(filaments.CatalogueFilament("Spule", "#112233", bought_on=text))
    assert rejected.value.field == "bought_on"


def test_rejected_spool_comes_back_into_the_dialog(inventory, monkeypatch) -> None:
    """Weist der Kern ein Feld ab, steht die Eingabe wieder da — nichts geht verloren.

    Befund 19.09.2026: Dialog zu, unten der Grund, das Regal leer, und Name,
    Lagerort und Bestand waren weg.
    """
    reopened: list[tuple[object, str]] = []

    def capture(self):
        reopened.append((self._entry, self.focusWidget() is self.bought_on.editor))
        return QDialog.DialogCode.Rejected

    monkeypatch.setattr(NewFilamentDialog, "exec", capture)
    candidate = filaments.CatalogueFilament(
        "PETG Rot", "#d02020", location="Regal 2", remaining_grams=750, bought_on="20260905"
    )
    inventory._run(partial(filaments.save, candidate), inventory._saved, retry_entry=candidate)
    _wait_for_action(inventory)
    assert reopened and reopened[0] == (candidate, True)
    assert "bought_on" in inventory.message.text() or "Datum" in inventory.message.text()
    assert filaments.catalogue() == ()


def test_focus_field_opens_the_details_for_a_date(qt_app: QApplication) -> None:
    dialog = NewFilamentDialog(name="Spule")
    dialog.show()
    assert not dialog.more.isVisible()
    assert dialog.focus_field("bought_on")
    assert dialog.more.isVisible()
    assert dialog.focusWidget() is dialog.bought_on.editor
    assert not dialog.focus_field("revision")
    dialog.close()


def test_revision_conflict_offers_to_reload(inventory) -> None:
    """Der Satz sagt „neu laden" — und genau das ist der Knopf (Regel 17)."""
    entry = filaments.save(filaments.CatalogueFilament("Spule", "#112233"))
    filaments.save(replace(entry, location="Kiste"))
    stale = replace(entry, location="Schrank")
    inventory._run(partial(filaments.save, stale), inventory._saved, retry_entry=stale)
    _wait_for_action(inventory)
    labels = [button.text() for button in inventory.message._buttons]
    assert "Aktuellen Stand neu laden" in labels
    assert "Eingabe korrigieren" not in inventory.message.text()
    current = filaments.get(entry.identifier)
    assert current is not None and current.location == "Kiste"


def test_title_and_button_agree_on_creating_and_editing(qt_app: QApplication) -> None:
    """Ein Neueintrag, der abgewiesen zurückkommt, bleibt ein Anlegen — Titel wie Knopf."""
    fresh = NewFilamentDialog(entry=filaments.CatalogueFilament("Neu", "#112233"))
    assert fresh.windowTitle() == "Neues Filament"
    assert fresh._ok_button.text() == "Spule anlegen"
    named = NewFilamentDialog(name="Vorbelegt")
    assert named.windowTitle() == "Neues Filament"
    assert named._ok_button.text() == "Spule anlegen"
    existing = NewFilamentDialog(
        entry=filaments.CatalogueFilament("Alt", "#112233", identifier="x")
    )
    assert existing.windowTitle() == "Filament ändern"
    assert existing._ok_button.text() == "Spule speichern"


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
    from app.ui.theme import apply_theme, current_theme

    previous_theme = current_theme()
    previous_palette = qt_app.palette()
    previous_sheet = qt_app.styleSheet()
    try:
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
    finally:
        apply_theme(qt_app, previous_theme)
        qt_app.setPalette(previous_palette)
        qt_app.setStyleSheet(previous_sheet)


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
    # Die Rücknahme ist rücknehmbar (B2): derselbe Knopf, anderer Satz.
    assert inventory.reverse_button.isEnabled()
    assert inventory.reverse_button.text() == "Rücknahme rückgängig machen"
    inventory.reverse_button.click()
    _wait_for_action(inventory)
    assert filaments.get(first.identifier).remaining_grams == pytest.approx(175)
    assert filaments.get(second.identifier).remaining_grams == pytest.approx(265)
    assert "Zurückgenommen" not in inventory.history.item(0).text()
    assert len(filaments.bookings()) == 1
    inventory.history.setCurrentRow(0)
    assert inventory.reverse_button.text() == "Gewählten Vorgang zurücknehmen"


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

    def search(*, cancelled=None) -> tuple[filaments.CatalogueFilament, ...]:
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
    """Eine beschädigte Datei zeigt den vorhandenen Sicherungsweg und bewahrt die letzte Ansicht.

    **Und die Handlung ist ausführbar.** Hier stand ``CORRECT_INPUT`` als
    Text — der Vorschlag einer ``ValidationError``, der einem Dialogfeld gilt
    und den keine der vier Lageransichten ausführen kann. Eine kaputte Datei
    hat kein Feld; was hilft, ist die Sicherung und danach *Erneut versuchen*.
    """
    from PySide6.QtWidgets import QPushButton

    from app.core.errors import RETRY, ValidationError

    entry = filaments.save(filaments.CatalogueFilament("Vorhanden", "#123456"))
    inventory.refresh()
    saved = inventory._entries
    filaments.catalogue_path().write_text('{"format_version": 1, "broken": true}', encoding="utf-8")
    with pytest.raises(ValidationError) as caught:
        filaments.catalogue()
    assert RETRY in caught.value.suggestions, "der Lesefehler trägt seine eigene Handlung"
    inventory.refresh()
    assert inventory.message.text().startswith(str(caught.value.title))
    # Feld und Bedingung sind Adressen für den Code, keine Angaben für den
    # Kunden — sie stehen nicht mehr unter dem Satz (T2, 19.09.2026).
    assert "Feld:" not in inventory.message.text()
    assert "Bedingung:" not in inventory.message.text()
    assert ".:" not in inventory.message.text()
    assert "Sicherung" in inventory.message.text()
    offered = [button.text() for button in inventory.message.findChildren(QPushButton)]
    assert str(RETRY.label) in offered, f"kein ausführbarer Rückweg, nur {offered}"
    assert inventory._entries == saved and saved[0].identifier == entry.identifier
    assert not inventory.retry_button.isHidden()


def test_unreadable_inventory_offers_the_backup_as_a_button(inventory: InventoryView) -> None:
    """Die Sicherung, die die Anwendung selbst anlegt, ist ein Klick entfernt (R2)."""
    entry = filaments.save(filaments.CatalogueFilament("Vorhanden", "#123456"))
    filaments.save(replace(entry, location="Kiste"))
    filaments.catalogue_path().write_text("{kaputt", encoding="utf-8")
    inventory.refresh()
    buttons = {button.text(): button for button in inventory.message._buttons}
    assert "Letzten lesbaren Stand zurückholen" in buttons
    assert "Beschädigte Datei beiseitelegen" in buttons
    buttons["Letzten lesbaren Stand zurückholen"].click()
    _wait_for_action(inventory)
    assert not inventory.message.text()
    assert [card.entry.identifier for card in inventory.cards] == [entry.identifier]
    assert inventory.cards[0].entry.location == ""


def test_unreadable_inventory_can_be_set_aside_from_the_shelf(inventory: InventoryView) -> None:
    filaments.save(filaments.CatalogueFilament("Vorhanden", "#123456"))
    filaments.catalogue_path().write_text("{kaputt", encoding="utf-8")
    inventory.refresh()
    buttons = {button.text(): button for button in inventory.message._buttons}
    assert "Letzten lesbaren Stand zurückholen" not in buttons, "ohne Sicherung kein Knopf dafür"
    buttons["Beschädigte Datei beiseitelegen"].click()
    _wait_for_action(inventory)
    assert not inventory.message.text()
    assert inventory.cards == []
    assert "leer" in inventory.empty.text()
    assert list(filaments.catalogue_path().parent.glob("filaments.json.damaged-*"))


def test_unexpected_inventory_read_error_is_reported_and_logged(
    inventory: InventoryView, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Ein Programmfehler beim Lesen wird weder verschwiegen noch zum Schreibfehler umgedeutet."""
    from app.core.errors import REPORT_ERROR, SHOW_DETAILS, InternalError

    def broken(*args, **kwargs):
        raise RuntimeError("inventory-read-probe")

    monkeypatch.setattr(filaments, "catalogue", broken)
    inventory.refresh()
    shown = inventory.message.text().splitlines()
    assert shown[:2] == [
        str(InternalError.default_title),
        "RuntimeError: inventory-read-probe",
    ]
    assert str(REPORT_ERROR.label) in inventory.message.text()
    assert str(SHOW_DETAILS.label) in inventory.message.text()
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


def test_cancel_button_stops_the_actual_slicer_profile_walk(inventory, tmp_path, monkeypatch):
    """Der Kundenknopf erreicht die laufende Dateisuche statt nur ihre spätere Antwort."""
    import json
    from types import SimpleNamespace

    from app.core import tools
    from app.core.export import slicer_profiles

    executable = tmp_path / "orca-slicer.exe"
    executable.write_bytes(b"")
    root = tmp_path / "OrcaSlicer" / "user" / "default"
    root.mkdir(parents=True)
    (root.parent.parent / "OrcaSlicer.conf").write_text(
        json.dumps(
            {
                "presets": {"machine": "Printer"},
                "orca_presets": [
                    {"machine": "Printer", "filament": "Missing", "filament_colors": "#123456"}
                ],
            }
        ),
        encoding="utf-8",
    )
    for index in range(20):
        (root / f"{index:02}.json").write_text(json.dumps({"name": str(index)}), encoding="utf-8")
    monkeypatch.setattr(tools, "by_id", lambda _key: SimpleNamespace(path=lambda: executable))
    monkeypatch.setattr(slicer_profiles, "user_roots", lambda *args: (root,))
    monkeypatch.setattr(slicer_profiles, "install_root", lambda *_args: None)
    original = Path.rglob
    entered, released = Event(), Event()
    visited = []

    def delayed_walk(path, pattern):
        for entry in original(path, pattern):
            visited.append(entry)
            if len(visited) == 1:
                entered.set()
                assert released.wait(3)
            yield entry

    monkeypatch.setattr(Path, "rglob", delayed_walk)
    inventory.import_button.click()
    worker = inventory._worker
    try:
        assert entered.wait(1)
        inventory._show_wait_progress()
        inventory.cancel_button.click()
        assert inventory._worker is None
    finally:
        released.set()
        assert worker.wait(2000)
        QTest.qWait(30)
    assert len(visited) == 1
    assert inventory.wait_for_workers(0)
    assert "abgebrochen" in inventory.message.text()
    assert filaments.catalogue() == ()
