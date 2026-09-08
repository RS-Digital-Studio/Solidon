"""Der Kundenweg von einer erfolgreichen Ausgabe zur bestätigten Lagerbuchung."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from pathlib import Path
from threading import Barrier, Event
from time import monotonic

import pytest
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from app.core.filament_usage import UsageLine, UsageRequest
from app.core.knowledge import filaments
from app.core.types import MaterialSlot
from app.i18n import set_language
from app.ui import filament_usage as usage_ui
from app.ui.filament_usage import UsageDialog, UsageNotice, _line_key
from app.ui.settings import UiSettings


@pytest.fixture(autouse=True)
def own_inventory(qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Jeder Fensterfall läuft ohne fremdes Lager und ohne 3D-Kontext."""
    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")


def _wait(widget: UsageDialog | UsageNotice) -> None:
    """Das Fachsignal samt Freigabe muss zugestellt sein, nicht nur der Thread fertig."""
    until = monotonic() + 5
    while widget._tasks.worker is not None and monotonic() < until:
        QTest.qWait(10)
    assert widget._tasks.worker is None
    QTest.qWait(10)


def _spool(grams: float | None = 500, **metadata: object) -> filaments.CatalogueFilament:
    return filaments.save(
        filaments.CatalogueFilament(
            "PETG Weiß",
            "#ffffff",
            "PETG",
            remaining_grams=grams,
            **metadata,
        )
    )


def _request(
    entry: filaments.CatalogueFilament | None,
    grams: float | None = 42,
    source: filaments.BookingSource = "internal",
) -> UsageRequest:
    return UsageRequest(
        "geometry",
        "Halter",
        0,
        (
            UsageLine(
                MaterialSlot(0, "PETG Weiß", (1.0, 1.0, 1.0), material_type="PETG"),
                grams,
                entry.identifier if entry else "",
                source,
            ),
        ),
    )


def _dialog(request: UsageRequest) -> UsageDialog:
    dialog = UsageDialog(request)
    _wait(dialog)
    return dialog


def _remaining(entry: filaments.CatalogueFilament) -> float | None:
    current = filaments.get(entry.identifier)
    assert current is not None
    return current.remaining_grams


def test_offer_never_books_in_the_default_mode() -> None:
    entry = _spool()
    notice = UsageNotice(UiSettings())
    notice.offer(_request(entry))
    assert not notice.isHidden()
    assert notice.choice.count() == 1
    assert _remaining(entry) == pytest.approx(500)
    assert filaments.bookings() == ()


def test_concurrent_automatic_offers_book_the_same_result_only_once(monkeypatch) -> None:
    """Zwei Fenster sehen gleichzeitig noch keinen Vorgang; die Schreibkennung bleibt gleich."""
    entry = _spool()
    request = _request(entry)
    barrier = Barrier(2)
    original = usage_ui._previous

    def simultaneous_snapshot(value):
        previous = original(value)
        assert not previous
        barrier.wait(timeout=3)
        return previous

    monkeypatch.setattr(usage_ui, "_previous", simultaneous_snapshot)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(usage_ui._auto_book, request)
        second = pool.submit(usage_ui._auto_book, request)
        assert first.result(timeout=5) == second.result(timeout=5)
    assert len(filaments.bookings()) == 1
    assert _remaining(entry) == pytest.approx(458)


@pytest.mark.parametrize(
    "changed", [{"material_type": "PLA"}, {"colour": "#ff0000"}, {"slicer_profile": "Other"}]
)
def test_changed_spool_properties_require_review_even_with_existing_binding(changed) -> None:
    entry = _spool()
    request = _request(entry)
    filaments.save(replace(entry, **changed))
    notice = UsageNotice(UiSettings(inventory_booking_mode="auto"))
    notice.offer(request)
    _wait(notice)
    assert filaments.bookings() == ()
    assert _remaining(entry) == pytest.approx(500)
    assert notice.requests[request.fingerprint] == request


def test_renamed_spool_still_uses_its_explicit_automatic_binding() -> None:
    entry = _spool()
    request = _request(entry)
    filaments.save(replace(entry, name="Werkstattspule"))
    notice = UsageNotice(UiSettings(inventory_booking_mode="auto"))
    notice.offer(request)
    _wait(notice)
    assert len(filaments.bookings()) == 1
    assert _remaining(entry) == pytest.approx(458)


def test_dismissed_dialog_keeps_stock_unchanged() -> None:
    entry = _spool()
    dialog = _dialog(_request(entry))
    dialog.reject()
    assert filaments.bookings() == ()
    assert _remaining(entry) == pytest.approx(500)


def test_explicit_book_is_idempotent_and_uses_language_independent_journal_values() -> None:
    entry = _spool()
    request = _request(entry)
    dialog = _dialog(request)
    assert dialog.book_button.isEnabled()
    dialog.book_button.click()
    _wait(dialog)
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert _remaining(entry) == pytest.approx(458)
    (booked,) = filaments.bookings()
    assert booked.positions[0].note == "without_supports_and_adhesion"
    set_language("en")
    reopened = _dialog(request)
    assert not reopened.book_button.isEnabled()
    assert len(filaments.bookings()) == 1


def test_missing_amount_requires_explicit_entry_and_keeps_manual_source() -> None:
    entry = _spool()
    dialog = _dialog(_request(entry, None, "gcode"))
    assert not dialog.book_button.isEnabled()
    assert "Einzelmenge" in dialog.state.text()
    dialog.amounts[0].setValue(25)
    assert dialog.book_button.isEnabled()
    dialog.book_button.click()
    _wait(dialog)
    (booked,) = filaments.bookings()
    assert booked.positions[0].source == "manual"
    assert booked.positions[0].grams == pytest.approx(25)


def test_unknown_stock_requires_confirmation_but_the_full_amount_remains_documented() -> None:
    entry = _spool(None)
    dialog = _dialog(_request(entry))
    assert not dialog.book_button.isEnabled()
    dialog.allow_unverified.setChecked(True)
    assert dialog.book_button.isEnabled()
    dialog.book_button.click()
    _wait(dialog)
    assert _remaining(entry) is None
    assert filaments.bookings()[0].positions[0].grams == pytest.approx(42)


def test_bound_spool_wins_and_missing_binding_is_never_silently_replaced() -> None:
    bound, better = _spool(500), _spool(50)
    dialog = _dialog(_request(bound))
    assert dialog.choices[0].currentData() == bound.identifier
    missing = replace(_request(bound).lines[0], spool_identifier="missing")
    unresolved = _dialog(replace(_request(bound), lines=(missing,)))
    assert unresolved.choices[0].currentData() == ""
    assert not unresolved.book_button.isEnabled()
    assert "fehlt" in unresolved.suggestions[0].text()
    assert better.identifier in unresolved._entries


def test_unbound_suggestion_is_visible_and_prefers_the_smallest_sufficient_stock() -> None:
    _spool(500)
    _spool(20)
    suitable = _spool(60)
    dialog = _dialog(_request(None))
    assert dialog.choices[0].currentData() == suitable.identifier
    assert "Vorschlag" in dialog.suggestions[0].text()
    assert filaments.bookings() == ()


def test_unknown_material_is_not_a_matching_spool_suggestion() -> None:
    filaments.save(filaments.CatalogueFilament("Unbekannt", "#ffffff"))
    line = replace(_request(None).lines[0], slot=MaterialSlot(0, "Unbekannt", (1.0, 1.0, 1.0)))
    dialog = _dialog(replace(_request(None), lines=(line,)))
    assert dialog.choices[0].currentData() == ""
    assert not dialog.book_button.isEnabled()


def test_gcode_corrects_only_the_difference_and_repeat_is_explicit() -> None:
    entry = _spool()
    first = _dialog(_request(entry))
    first.book_button.click()
    _wait(first)
    corrected = _dialog(_request(entry, 47, "gcode"))
    assert corrected.book_button.isEnabled()
    corrected.book_button.click()
    _wait(corrected)
    assert _remaining(entry) == pytest.approx(453)
    assert len(filaments.bookings()) == 1
    repeat = _dialog(_request(entry, 47, "gcode"))
    assert not repeat.book_button.isEnabled()
    repeat.repeat_button.click()
    assert repeat.book_button.isEnabled()
    repeat.book_button.click()
    _wait(repeat)
    assert _remaining(entry) == pytest.approx(406)
    assert len(filaments.bookings()) == 2


def test_auto_correction_checks_the_difference_not_the_whole_new_quantity() -> None:
    entry = _spool(60)
    notice = UsageNotice(UiSettings(inventory_booking_mode="auto"))
    notice.offer(_request(entry))
    _wait(notice)
    assert _remaining(entry) == pytest.approx(18)
    notice.offer(_request(entry, 47, "gcode"))
    _wait(notice)
    assert _remaining(entry) == pytest.approx(13)
    assert len(filaments.bookings()) == 1


def test_zero_from_gcode_can_correct_a_positive_estimate() -> None:
    entry = _spool()
    notice = UsageNotice(UiSettings(inventory_booking_mode="auto"))
    notice.offer(_request(entry))
    _wait(notice)
    notice.offer(_request(entry, 0, "gcode"))
    _wait(notice)
    assert _remaining(entry) == pytest.approx(500)
    assert len(filaments.bookings()[0].corrections) == 1


def test_automatic_mode_never_overwrites_a_manually_entered_quantity() -> None:
    entry = _spool()
    request = _request(entry)
    filaments.book(
        "print",
        request.fingerprint,
        [
            filaments.BookingPosition(
                entry.identifier,
                40,
                "manual",
                filament_key=_line_key(request.lines[0]),
            )
        ],
    )
    notice = UsageNotice(UiSettings(inventory_booking_mode="auto"))
    notice.offer(_request(entry, 47, "gcode"))
    _wait(notice)
    assert _remaining(entry) == pytest.approx(460)
    dialog = _dialog(_request(entry, 47, "gcode"))
    assert dialog.correct_button.isEnabled()
    dialog.correct_button.click()
    _wait(dialog)
    assert _remaining(entry) == pytest.approx(453)


def test_rejection_during_a_confirmed_atomic_write_does_not_report_a_cancellation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    entry = _spool()
    dialog = _dialog(_request(entry))
    entered, released = Event(), Event()
    original = filaments.book

    def blocked(*args: object, **kwargs: object):
        entered.set()
        assert released.wait(3)
        return original(*args, **kwargs)

    monkeypatch.setattr(filaments, "book", blocked)
    dialog.book_button.click()
    try:
        assert entered.wait(1)
        dialog.reject()
        assert dialog._tasks.worker is not None
    finally:
        released.set()
        _wait(dialog)
    assert dialog.result() == QDialog.DialogCode.Accepted
    assert _remaining(entry) == pytest.approx(458)


def test_auto_never_guesses_a_missing_binding_or_accepts_unknown_stock() -> None:
    entry = _spool()
    notice = UsageNotice(UiSettings(inventory_booking_mode="auto"))
    notice.offer(_request(None))
    _wait(notice)
    assert filaments.bookings() == ()
    filaments.set_remaining(entry.identifier, None)
    notice.offer(_request(entry))
    _wait(notice)
    assert filaments.bookings() == ()
    assert not notice.isHidden()


def test_transferred_notice_does_not_trigger_a_second_automatic_booking() -> None:
    entry = _spool()
    notice = UsageNotice(UiSettings(inventory_booking_mode="auto"))
    notice.offer(_request(entry), auto_book=False)
    assert notice._tasks.worker is None
    assert filaments.bookings() == ()


def test_later_estimate_cannot_replace_a_gcode_offer_or_booking() -> None:
    entry = _spool()
    notice = UsageNotice(UiSettings(inventory_booking_mode="auto"))
    notice.offer(_request(entry, 47, "gcode"))
    _wait(notice)
    notice.offer(_request(entry, 42))
    _wait(notice)
    assert notice.requests["geometry"].lines[0].source == "gcode"
    assert notice.requests["geometry"].lines[0].grams == pytest.approx(47)
    assert _remaining(entry) == pytest.approx(453)
    dialog = _dialog(_request(entry, 42))
    assert dialog.amounts[0].value() == pytest.approx(47)
    assert "G-Code" in dialog.sources[0].text()
    assert not dialog.book_button.isEnabled()


def test_explicit_split_requires_each_share_and_books_every_spool_atomically() -> None:
    first, second = _spool(), _spool()
    dialog = _dialog(_request(first, 47, "gcode"))
    dialog.split_checks[0].setChecked(True)
    assert not dialog.book_button.isEnabled()
    left, right = dialog.allocations[0]
    right[0].setCurrentIndex(right[0].findData(second.identifier))
    left[1].setValue(20)
    right[1].setValue(25)
    assert not dialog.book_button.isEnabled()
    right[1].setValue(27)
    assert dialog.book_button.isEnabled()
    dialog.book_button.click()
    _wait(dialog)
    (booked,) = filaments.bookings()
    assert len(booked.positions) == 2
    assert {row.source for row in booked.positions} == {"manual"}
    assert _remaining(first) == pytest.approx(480)
    assert _remaining(second) == pytest.approx(473)


def test_manual_split_correction_requires_its_own_confirmation() -> None:
    first, second = _spool(), _spool()
    request = _request(first, 42)
    key = _line_key(request.lines[0])
    filaments.book(
        "print",
        request.fingerprint,
        [
            filaments.BookingPosition(
                first.identifier, 20, "manual", "manual_allocation", filament_key=key
            ),
            filaments.BookingPosition(
                second.identifier, 22, "manual", "manual_allocation", filament_key=key
            ),
        ],
    )
    dialog = _dialog(_request(first, 47, "gcode"))
    assert dialog.split_checks[0].isChecked()
    assert not dialog.correct_button.isEnabled()
    dialog.allocations[0][1][1].setValue(27)
    assert dialog.correct_button.isEnabled()
    assert dialog.book_button.isHidden()
    dialog.correct_button.click()
    _wait(dialog)
    assert _remaining(first) == pytest.approx(480)
    assert _remaining(second) == pytest.approx(473)
    assert len(filaments.bookings()) == 1
    assert len(filaments.bookings()[0].corrections) == 1


def test_material_cost_uses_saved_currency_and_never_guesses_missing_prices() -> None:
    known = _spool(spool_grams=1000, price=20, currency="USD")
    dialog = _dialog(_request(known, 50))
    assert "USD" in dialog.costs[0].text()
    assert "1,00" in dialog.costs[0].text() or "1.00" in dialog.costs[0].text()
    unknown = _spool()
    dialog.choices[0].setCurrentIndex(dialog.choices[0].findData(unknown.identifier))
    # Der neue Datensatz steht erst nach ausdrücklichem Neuladen in der Auswahl.
    dialog.reload_button.click()
    _wait(dialog)
    dialog.choices[0].setCurrentIndex(dialog.choices[0].findData(unknown.identifier))
    assert dialog.costs[0].text() == ""


def test_concurrent_stock_change_reports_error_without_partial_booking() -> None:
    entry = _spool()
    dialog = _dialog(_request(entry))
    filaments.set_remaining(entry.identifier, 1)
    dialog.book_button.click()
    _wait(dialog)
    assert dialog.result() != QDialog.DialogCode.Accepted
    assert "Bestand" in dialog.state.text()
    assert filaments.bookings() == ()
    assert _remaining(entry) == pytest.approx(1)


def test_file_wait_runs_outside_the_qt_thread(monkeypatch: pytest.MonkeyPatch) -> None:
    request = _request(None)
    entered, released = Event(), Event()
    original = filaments.catalogue

    def blocked(*args: object, **kwargs: object):
        entered.set()
        assert released.wait(3)
        return original(*args, **kwargs)

    monkeypatch.setattr(filaments, "catalogue", blocked)
    dialog = UsageDialog(request)
    try:
        assert entered.wait(1)
        assert dialog._tasks.worker is not None
        assert not dialog.book_button.isEnabled()
        QTest.qWait(20)
    finally:
        released.set()
        _wait(dialog)
