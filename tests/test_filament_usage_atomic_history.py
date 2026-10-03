"""Nur beobachtete Druckzuordnungen dürfen automatisch einen neuen Vorgang anlegen."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from threading import Event, get_ident
from types import SimpleNamespace

import pytest

from app.core.errors import AppError
from app.core.filament_usage import UsageLine, UsageRequest
from app.core.knowledge import filaments
from app.core.types import MaterialSlot
from app.ui import filament_usage as ui


@pytest.fixture
def inventory(monkeypatch, tmp_path):
    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    spool = filaments.save(
        filaments.CatalogueFilament("PLA", "#ffffff", "PLA", remaining_grams=500)
    )
    slot = MaterialSlot(0, "PLA", (1.0, 1.0, 1.0), material_type="PLA")
    line = UsageLine(slot, 42.0, spool.identifier)
    request = UsageRequest("new-gap-key", "Part", 0, (line,), ("old-key",))
    position = filaments.BookingPosition(
        spool.identifier, 42.0, "internal", ui._note(line), filament_key=ui._line_key(line)
    )
    return spool, request, position


def interleaved(monkeypatch, request, other):
    """Der zweite Schreiber läuft nach dem Snapshot und vor dessen Buchungsaufruf."""
    original_read = filaments.read_snapshot
    owner = get_ident()
    captured = Event()
    resume = Event()
    first = True

    def paused_snapshot():
        nonlocal first
        snapshot = original_read()
        if get_ident() != owner and first:
            first = False
            captured.set()
            assert resume.wait(5), "Der zweite Bucher muss die Sonde freigeben."
        return snapshot

    monkeypatch.setattr(filaments, "read_snapshot", paused_snapshot)
    problem = result = None
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(ui._auto_book, request)
        try:
            assert captured.wait(5), "Die Automatik muss den alten Stand gelesen haben."
            other()
        finally:
            resume.set()
        try:
            result = future.result(timeout=5)
        except AppError as error:
            problem = error
    return result, problem, original_read()


@pytest.mark.parametrize("fingerprint", ["old-key", "new-gap-key"])
@pytest.mark.parametrize("was_reversed", [False, True])
def test_new_relevant_booking_or_its_reversal_stops_stale_automatic_request(
    monkeypatch, inventory, fingerprint, was_reversed
):
    spool, request, position = inventory

    def other():
        filaments.book("parallel", fingerprint, [position])
        if was_reversed:
            filaments.reverse_booking("parallel")

    result, problem, snapshot = interleaved(monkeypatch, request, other)
    assert snapshot.spools[spool.identifier].remaining_grams == (500 if was_reversed else 458)
    assert len(snapshot.bookings()) == 1
    assert result is None
    assert problem.values["constraint"] == "booking_history_changed"
    assert [action.id for action in problem.suggestions] == ["correct_input"]


def test_unrelated_parallel_booking_does_not_block(monkeypatch, inventory):
    spool, request, position = inventory
    result, problem, snapshot = interleaved(
        monkeypatch, request, lambda: filaments.book("unrelated", "different-print", [position])
    )
    assert problem is None
    assert result.fingerprint == request.fingerprint
    assert snapshot.spools[spool.identifier].remaining_grams == 416
    assert len(snapshot.bookings()) == 2


def test_the_addressed_exact_operation_remains_idempotent(monkeypatch, inventory):
    spool, request, position = inventory
    existing = filaments.book("existing-exact", request.fingerprint, [position])
    result, problem, snapshot = interleaved(
        monkeypatch, request, lambda: filaments.book("parallel-old", "old-key", [position])
    )
    assert problem is None
    assert result.operation_id == existing.operation_id
    assert snapshot.spools[spool.identifier].remaining_grams == 416
    assert len(snapshot.bookings()) == 2


def test_already_observed_exact_reversal_allows_existing_repeat_route(inventory):
    spool, request, position = inventory
    filaments.book("old", "old-key", [position])
    existing = filaments.book("previous-exact", request.fingerprint, [position])
    filaments.reverse_booking(existing.operation_id)
    result = ui._auto_book(request)
    assert result.operation_id != existing.operation_id
    assert not result.reversed_at
    assert filaments.get(spool.identifier).remaining_grams == 416


def test_reversal_after_observation_does_not_revive_addressed_operation(monkeypatch, inventory):
    spool, request, position = inventory
    existing = filaments.book("existing-exact", request.fingerprint, [position])
    result, problem, snapshot = interleaved(
        monkeypatch, request, lambda: filaments.reverse_booking(existing.operation_id)
    )
    assert problem is None
    assert result is None
    assert snapshot.spools[spool.identifier].remaining_grams == 500
    assert len(snapshot.bookings()) == 1
    assert snapshot.bookings()[0].reversed_at


def test_manually_confirmed_repeat_does_not_require_history_guard(inventory):
    spool, request, position = inventory
    old = filaments.book("old", "old-key", [position])
    new = filaments.book("manual-repeat", request.fingerprint, [position])
    assert filaments.get(spool.identifier).remaining_grams == 416
    assert {entry.operation_id for entry in filaments.read_snapshot().bookings()} == {
        new.operation_id,
        old.operation_id,
    }


def test_unchanged_exact_history_can_be_used_for_a_new_repeat(inventory):
    spool, request, position = inventory
    old = filaments.book("exact-then-reversed", request.fingerprint, [position])
    old = filaments.reverse_booking(old.operation_id)
    result = filaments.book(
        "next",
        request.fingerprint,
        [position],
        expected_history={request.fingerprint: (old,), request.legacy_fingerprints[0]: ()},
    )
    assert result.operation_id == "next"
    assert filaments.get(spool.identifier).remaining_grams == 458


def test_same_automatic_operation_is_safe_when_another_worker_committed_it(monkeypatch, inventory):
    spool, request, _position = inventory
    results = []
    result, problem, snapshot = interleaved(
        monkeypatch, request, lambda: results.append(ui._auto_book(request))
    )
    assert problem is None
    assert result.operation_id == results[0].operation_id
    assert snapshot.spools[spool.identifier].remaining_grams == 458
    assert len(snapshot.bookings()) == 1


def test_exact_correction_after_snapshot_still_changes_only_the_difference(monkeypatch, inventory):
    spool, request, position = inventory
    filaments.book("exact", request.fingerprint, [position])
    request = replace(request, lines=(replace(request.lines[0], grams=47, source="gcode"),))
    result, problem, snapshot = interleaved(
        monkeypatch, request, lambda: filaments.book("parallel-old", "old-key", [position])
    )
    assert problem is None
    assert result.operation_id == "exact"
    assert snapshot.spools[spool.identifier].remaining_grams == 411
    assert len(snapshot.bookings()) == 2


@pytest.mark.parametrize("change", ["reverse", "restore", "correct"])
def test_changed_observed_record_stops_a_new_operation(inventory, change):
    spool, request, position = inventory
    old = filaments.book("observed", request.fingerprint, [position])
    if change == "restore":
        old = filaments.reverse_booking(old.operation_id)
    observed = {request.fingerprint: (old,)}
    if change == "reverse":
        filaments.reverse_booking(old.operation_id)
    elif change == "restore":
        filaments.restore_booking(old.operation_id)
    else:
        filaments.book(
            old.operation_id, request.fingerprint, [replace(position, source="gcode", grams=47)]
        )
    before = filaments.read_snapshot()
    with pytest.raises(AppError) as raised:
        filaments.book("new-attempt", request.fingerprint, [position], expected_history=observed)
    assert raised.value.values["constraint"] == "booking_history_changed"
    assert filaments.read_snapshot() == before
    assert filaments.get(spool.identifier) == before.spools[spool.identifier]


def test_journal_order_does_not_change_observed_history(inventory):
    spool, request, position = inventory
    first = filaments.book("first", "old-key", [position])
    second = filaments.book("second", "old-key", [position])
    result = filaments.book(
        "new",
        request.fingerprint,
        [position],
        expected_history={request.fingerprint: (), "old-key": (second, first)},
    )
    assert result.operation_id == "new"
    assert filaments.get(spool.identifier).remaining_grams == 374


def test_history_conflict_opens_existing_review_with_fresh_old_warning(monkeypatch, inventory):
    _spool, request, position = inventory
    result, problem, snapshot = interleaved(
        monkeypatch, request, lambda: filaments.book("parallel", "old-key", [position])
    )
    assert result is None
    assert problem is not None
    assert str(problem.suggestions[0].label) == "Buchung prüfen …"
    opened = []
    handlers = {}
    inert = SimpleNamespace(
        setText=lambda text: None,
        setVisible=lambda shown: None,
        setToolTip=lambda text: None,
        setStatusTip=lambda text: None,
        setAccessibleDescription=lambda text: None,
        setEnabled=lambda enabled: None,
        set_actions_enabled=lambda enabled: None,
        set_error=lambda error, actions: handlers.update(actions),
    )
    host = SimpleNamespace(
        _tasks=SimpleNamespace(worker=None),
        _problems={request.fingerprint: problem},
        choice=SimpleNamespace(currentData=lambda: request.fingerprint),
        _declined=set(),
        _booked=set(),
        _pending={},
        requests={request.fingerprint: request},
        _dialogs=[],
        review=inert,
        state=inert,
        changed=SimpleNamespace(emit=lambda: None),
        _release_dialog=lambda dialog: None,
    )
    host._sync_review = lambda: ui.UsageNotice._sync_review(host)
    monkeypatch.setattr(ui, "weak_slot", lambda owner, action: lambda: action(owner))

    def review_dialog(chosen, parent):
        fresh = ui._snapshot(chosen)
        opened.append((chosen, parent, fresh))
        return SimpleNamespace(exec=lambda: ui.QDialog.DialogCode.Rejected, booking_declined=True)

    monkeypatch.setattr(ui, "UsageDialog", review_dialog)
    host._sync_review()
    handlers["correct_input"]()
    assert len(opened) == 1
    assert opened[0][:2] == (request, host)
    assert opened[0][2].legacy_bookings == snapshot.bookings()
    assert opened[0][2].bookings == ()
    assert host._declined == {request.fingerprint}
    assert not host._booked
    assert filaments.read_snapshot() == snapshot
