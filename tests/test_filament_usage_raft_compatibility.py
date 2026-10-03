"""Raftwerte und alte Verbrauchsbuchungen ohne Fenster verbinden."""

from __future__ import annotations

from contextlib import nullcontext
from dataclasses import dataclass, replace
from types import SimpleNamespace

import pytest
import trimesh

from app.core import filament_usage as usage
from app.core.errors import AppError
from app.core.geom.mesh import MeshData
from app.core.knowledge import filaments, print_settings, profiles
from app.core.scene import serialise
from app.core.slice.gcode import GcodeMetrics
from app.core.types import AdhesionSettings, MaterialSlot, SceneObject
from app.ui import filament_usage as ui


@dataclass(frozen=True, slots=True)
class ExtendedAdhesion(AdhesionSettings):
    """Erlaubt dieselbe Gegenprobe auch vor der separaten Raftfeld-Ergänzung."""

    raft_gap: float | None = None


def _prepare(kind, gap, *, explicit=True, bodies=None):
    profile = profiles.make_profile("prusa-mini", "pla")
    settings = replace(print_settings.resolve(profile), inventory_project_id="existing-project")
    settings = replace(settings, adhesion=replace(settings.adhesion, kind=kind))
    if explicit:
        settings = print_settings.with_choice(settings, "adhesion.kind", kind)
    values = serialise.print_settings_to_data(settings)["adhesion"]
    values.pop("raft_gap", None)
    settings = replace(settings, adhesion=ExtendedAdhesion(**values, raft_gap=gap))
    objects = bodies or [
        SceneObject("one", "Part", MeshData.of(trimesh.creation.box((20, 20, 20))))
    ]
    return usage.prepare(objects, settings, profile, "Project")


def _old_request(monkeypatch, kind, gap, **kwargs):
    serializer = usage.print_settings_to_data

    def legacy(settings):
        data = serializer(settings)
        data["adhesion"].pop("raft_gap", None)
        return data

    with monkeypatch.context() as scoped:
        scoped.setattr(usage, "print_settings_to_data", legacy)
        return _prepare(kind, gap, **kwargs)


@pytest.mark.parametrize(
    "kind,gap,explicit",
    [
        ("raft", None, True),
        ("auto", None, True),
        ("none", None, False),
        ("none", 0.15, True),
        ("brim", 0.0, True),
        ("skirt", 0.20, True),
    ],
)
def test_unknown_or_disabled_raft_keeps_existing_fingerprint(monkeypatch, kind, gap, explicit):
    previous = _old_request(monkeypatch, kind, gap, explicit=explicit)[0]
    current = _prepare(kind, gap, explicit=explicit)[0]
    assert current.fingerprint == previous.fingerprint
    assert current.legacy_fingerprints == previous.legacy_fingerprints


@pytest.mark.parametrize("kind,explicit", [("raft", True), ("auto", True), ("none", False)])
def test_active_or_unproven_raft_retains_values_and_possible_old_key(monkeypatch, kind, explicit):
    requests = [_prepare(kind, gap, explicit=explicit)[0] for gap in (0.0, 0.15, 0.20)]
    previous = _old_request(monkeypatch, kind, 0.15, explicit=explicit)[0]
    assert len({request.fingerprint for request in requests}) == 3
    assert all(previous.fingerprint in request.legacy_fingerprints for request in requests)


def test_possible_identity_keeps_plate_geometry_and_gcode_identity(monkeypatch):
    raw = MeshData.of(trimesh.creation.box((20, 20, 20)))
    bodies = [SceneObject("one", "Part", raw), SceneObject("two", "Other", raw, plate=1)]
    current = _prepare("raft", 0.15, bodies=bodies)
    old = _old_request(monkeypatch, "raft", 0.15, bodies=bodies)
    assert len({request.fingerprint for request in current}) == 2
    assert all(
        previous.fingerprint in request.legacy_fingerprints
        for request, previous in zip(current, old, strict=True)
    )
    adjusted = usage.from_gcode(current[0], GcodeMetrics(filament_grams=47))
    assert adjusted.legacy_fingerprints == current[0].legacy_fingerprints
    assert adjusted.fingerprint == current[0].fingerprint


def test_possible_identity_keeps_material_slots_and_assignment(monkeypatch):
    raw = trimesh.creation.box((20, 20, 20))
    slots = [
        MaterialSlot(0, "White", (1.0, 1.0, 1.0), material_type="PLA"),
        MaterialSlot(1, "Black", (0.0, 0.0, 0.0), material_type="PLA"),
    ]
    mesh = MeshData.of(raw, (0,) * 6 + (1,) * 6)
    body = SceneObject("one", "Part", mesh, material_slots=slots)
    current = _prepare("raft", 0.15, bodies=[body])[0]
    old = _old_request(monkeypatch, "raft", 0.15, bodies=[body])[0]
    assert len(current.lines) == 2
    assert old.fingerprint in current.legacy_fingerprints
    swapped = replace(body, mesh=MeshData.of(raw, (1,) * 6 + (0,) * 6))
    other = _prepare("raft", 0.15, bodies=[swapped])[0]
    assert other.fingerprint != current.fingerprint
    assert other.legacy_fingerprints != current.legacy_fingerprints
    assert body.mesh is mesh
    assert body.material_slots is slots


@pytest.fixture
def inventory(monkeypatch, tmp_path):
    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    entry = filaments.save(
        filaments.CatalogueFilament("PLA", "#ffffff", "PLA", remaining_grams=500)
    )
    slot = MaterialSlot(0, "PLA", (1.0, 1.0, 1.0), material_type="PLA")
    line = usage.UsageLine(slot, 42.0, entry.identifier)
    request = SimpleNamespace(
        fingerprint="new", legacy_fingerprints=("old",), project_name="Part", plate=0, lines=(line,)
    )
    position = filaments.BookingPosition(
        entry.identifier, 42.0, "internal", ui._note(line), filament_key=ui._line_key(line)
    )
    return SimpleNamespace(entry=entry, request=request, position=position)


def _old_booking(inventory, *, was_reversed=False):
    booking = filaments.book("old-operation", "old", [inventory.position])
    return filaments.reverse_booking(booking.operation_id) if was_reversed else booking


@pytest.mark.parametrize("was_reversed", [False, True])
def test_uncertain_old_booking_stops_automatic_debit(inventory, was_reversed):
    prior = _old_booking(inventory, was_reversed=was_reversed)
    before = filaments.get(inventory.entry.identifier).remaining_grams
    with pytest.raises(AppError) as raised:
        ui._auto_book(inventory.request)
    assert raised.value.values["constraint"] == "legacy_adhesion_gaps"
    assert [action.id for action in raised.value.suggestions] == ["correct_input"]
    assert "Brim und Raft" in str(raised.value.detail)
    assert ("zurückgenommen" in str(raised.value.detail)) is was_reversed
    assert filaments.get(inventory.entry.identifier).remaining_grams == before
    assert filaments.read_snapshot().bookings() == (prior,)


@pytest.mark.parametrize("was_reversed", [False, True])
def test_exact_new_history_has_priority_over_possible_legacy(inventory, was_reversed):
    old = _old_booking(inventory)
    exact = filaments.book("confirmed-new", "new", [inventory.position])
    if was_reversed:
        filaments.reverse_booking(exact.operation_id)
    result = ui._auto_book(inventory.request)
    assert result.fingerprint == "new"
    assert not result.reversed_at
    assert (result.operation_id != exact.operation_id) is was_reversed
    assert filaments.get(inventory.entry.identifier).remaining_grams == 416
    assert filaments.read_snapshot().journal[old.operation_id] == old


def test_exact_gcode_correction_changes_only_difference(inventory):
    _old_booking(inventory)
    filaments.book("confirmed-new", "new", [inventory.position])
    inventory.request.lines = (replace(inventory.request.lines[0], grams=47.0, source="gcode"),)
    result = ui._auto_book(inventory.request)
    assert result.operation_id == "confirmed-new"
    assert filaments.get(inventory.entry.identifier).remaining_grams == 411
    ui._auto_book(inventory.request)
    assert filaments.get(inventory.entry.identifier).remaining_grams == 411


def test_fresh_request_after_restart_still_warns_without_journal_migration(inventory):
    _old_booking(inventory)
    for _attempt in range(2):
        fresh = SimpleNamespace(**vars(inventory.request))
        with pytest.raises(AppError):
            ui._auto_book(fresh)
    assert len(filaments.read_snapshot().bookings()) == 1
    assert filaments.get(inventory.entry.identifier).remaining_grams == 458


class Value:
    def __init__(self, value=None):
        self.stored = value
        self.enabled = True
        self.visible = True
        self.text = ""

    def currentData(self):  # noqa: N802 — Qt gibt den Namen vor
        return self.stored

    def value(self):
        return self.stored

    def isChecked(self):  # noqa: N802 — Qt gibt den Namen vor
        return bool(self.stored)

    def setEnabled(self, value):  # noqa: N802 — Qt gibt den Namen vor
        self.enabled = value

    def isEnabled(self):  # noqa: N802 — Qt gibt den Namen vor
        return self.enabled

    def setVisible(self, value):  # noqa: N802 — Qt gibt den Namen vor
        self.visible = value

    def setText(self, value):  # noqa: N802 — Qt gibt den Namen vor
        self.text = str(value)

    def setToolTip(self, value):  # noqa: N802 — Qt gibt den Namen vor
        pass

    def setStatusTip(self, value):  # noqa: N802 — Qt gibt den Namen vor
        pass

    def setAccessibleDescription(self, value):  # noqa: N802 — Qt gibt den Namen vor
        pass


class Choice(Value):
    def __init__(self):
        super().__init__()
        self.items = []

    def clear(self):
        self.items = []
        self.stored = None

    def addItem(self, text, value):  # noqa: N802 — Qt gibt den Namen vor
        self.items.append((str(text), value))
        if len(self.items) == 1:
            self.stored = value

    def findData(self, value):  # noqa: N802 — Qt gibt den Namen vor
        return next((i for i, (_, one) in enumerate(self.items) if one == value), -1)

    def setCurrentIndex(self, index):  # noqa: N802 — Qt gibt den Namen vor
        self.stored = self.items[index][1]


def _dialog(inventory, monkeypatch):
    monkeypatch.setattr(ui, "QSignalBlocker", lambda _one: nullcontext())
    monkeypatch.setattr(ui, "make_primary", lambda _one: None)
    calls = []
    host = SimpleNamespace(
        request=inventory.request,
        _pending="load",
        _loaded=False,
        _tasks=SimpleNamespace(worker=None, run=calls.append),
        _bookings={},
        _legacy_bookings=(),
        _lines=list(inventory.request.lines),
        _created_identifier="",
        _new_operation_id="explicit-new-operation",
        choices=[],
        allocations=[],
        amounts=[Value(42.0)],
        split_checks=[Value(False)],
        operation=Choice(),
        _positions=lambda: (inventory.position,),
        _needs_manual_correction=lambda _positions: False,
        _update_costs=lambda _positions: None,
        _unchanged=ui.UsageDialog._unchanged,
        _operation_changed=lambda: None,
        booking_declined=False,
    )
    for name in (
        "content",
        "add_button",
        "reload_button",
        "book_button",
        "correct_button",
        "repeat_button",
        "state",
        "legacy_notice",
    ):
        setattr(host, name, Value())
    host.allow_unverified = Value(False)
    host._validate = lambda: ui.UsageDialog._validate(host)
    host.reject = lambda: calls.append("reject")
    ui.UsageDialog._completed(host, ui._snapshot(inventory.request))
    host._validate()
    return host, calls


@pytest.mark.parametrize("was_reversed", [False, True])
def test_dialog_warns_and_offers_explicit_new_print_without_old_selection(
    inventory, monkeypatch, was_reversed
):
    old = _old_booking(inventory, was_reversed=was_reversed)
    host, calls = _dialog(inventory, monkeypatch)
    assert host.legacy_notice.visible
    assert "Brim und Raft" in host.legacy_notice.text
    assert ("zurückgenommen" in host.legacy_notice.text) is was_reversed
    assert host._bookings == {}
    assert host.operation.currentData() == ""
    assert host.book_button.text == "Weiteren Druck buchen"
    assert host.book_button.enabled
    ui.UsageDialog._book(host)
    assert len(calls) == 1
    booked = calls[0]()
    assert booked.operation_id == host._new_operation_id
    assert booked.fingerprint == "new"
    assert filaments.read_snapshot().journal[old.operation_id] == old
    assert filaments.get(inventory.entry.identifier).remaining_grams == (
        458 if was_reversed else 416
    )
    assert (
        ui._auto_book(SimpleNamespace(**vars(inventory.request))).operation_id
        == booked.operation_id
    )
    filaments.reverse_booking(booked.operation_id)
    assert filaments.get(inventory.entry.identifier).remaining_grams == (
        500 if was_reversed else 458
    )
    assert filaments.read_snapshot().journal[old.operation_id] == old


def test_dialog_decline_does_not_book_or_reassign_old_operation(inventory, monkeypatch):
    old = _old_booking(inventory)
    host, calls = _dialog(inventory, monkeypatch)
    ui.UsageDialog._decline_booking(host)
    assert host.booking_declined
    assert calls == ["reject"]
    assert filaments.read_snapshot().bookings() == (old,)
    assert filaments.get(inventory.entry.identifier).remaining_grams == 458


def test_old_candidates_never_appear_as_exact_previous(inventory):
    _old_booking(inventory)
    filaments.book("second-old-operation", "old", [inventory.position])
    snapshot = ui._snapshot(inventory.request)
    assert snapshot.bookings == ()
    assert len(snapshot.legacy_bookings) == 2
    assert ui._previous(inventory.request) == []


def test_fresh_dialog_uses_exact_confirmed_booking_without_warning(inventory, monkeypatch):
    _old_booking(inventory)
    exact = filaments.book("confirmed-new", "new", [inventory.position])
    host, calls = _dialog(inventory, monkeypatch)
    assert not host.legacy_notice.visible
    assert host.legacy_notice.text == ""
    assert host.operation.currentData() == exact.operation_id
    assert not host.book_button.enabled
    assert "bereits gebucht" in host.state.text
    assert calls == []


def test_visible_warning_action_opens_existing_review_and_decline_keeps_stock(
    inventory, monkeypatch
):
    old = _old_booking(inventory)
    with pytest.raises(AppError) as raised:
        ui._auto_book(inventory.request)
    host = SimpleNamespace(
        _tasks=SimpleNamespace(worker=None),
        _problems={"new": raised.value},
        choice=Value("new"),
        _declined=set(),
        _booked=set(),
        _pending={},
        requests={"new": inventory.request},
        _dialogs=[],
        review=Value(),
        state=Value(),
        changed=SimpleNamespace(emit=lambda: None),
    )
    opened = []
    host._release_dialog = lambda dialog: None
    host._sync_review = lambda: ui.UsageNotice._sync_review(host)
    host.state.set_error = lambda error, handlers: setattr(host.state, "handlers", handlers)
    host.state.set_actions_enabled = lambda enabled: None
    monkeypatch.setattr(ui, "weak_slot", lambda owner, action: lambda: action(owner))

    def dialog(request, parent):
        opened.append((request, parent))
        return SimpleNamespace(exec=lambda: ui.QDialog.DialogCode.Rejected, booking_declined=True)

    monkeypatch.setattr(ui, "UsageDialog", dialog)
    host._sync_review()
    assert str(raised.value.suggestions[0].label) == "Buchung prüfen …"
    host.state.handlers["correct_input"]()
    assert opened == [(inventory.request, host)]
    assert host._declined == {"new"}
    assert not host._booked
    assert filaments.read_snapshot().bookings() == (old,)


def test_request_without_raft_compatibility_information_keeps_old_callers(inventory):
    request = usage.UsageRequest("ordinary", "Part", 0, inventory.request.lines)
    assert request.legacy_fingerprints == ()
    first = ui._auto_book(request)
    second = ui._auto_book(request)
    assert first.operation_id == second.operation_id
    assert filaments.get(inventory.entry.identifier).remaining_grams == 458
