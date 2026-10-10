"""Additive Brim-/Raftfelder dürfen alte Drucke weder verlieren noch gleichsetzen."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass, replace
from threading import Event, get_ident

import pytest
import trimesh

from app.core import filament_usage as usage
from app.core.errors import AppError
from app.core.geom.mesh import MeshData
from app.core.knowledge import filaments, print_settings, profiles
from app.core.scene.hashing import digest
from app.core.slice.gcode import GcodeMetrics
from app.core.types import AdhesionSettings, MaterialSlot, SceneObject
from app.ui import filament_usage as ui


@dataclass(frozen=True, slots=True)
class BothGaps(AdhesionSettings):
    """Der additive Vertrag funktioniert auch vor dem getrennten Brim-Merge."""

    brim_gap: float = 0.0
    raft_gap: float | None = None


def job(*, brim=0.0, raft=None, kind="raft", explicit=True, bodies=None, native=False):
    profile = profiles.make_profile("prusa-mini", "pla")
    settings = replace(print_settings.resolve(profile), inventory_project_id="existing-project")
    adhesion = settings.adhesion if native else BothGaps()
    adhesion = replace(adhesion, kind=kind, raft_gap=raft)
    if hasattr(adhesion, "brim_gap"):
        adhesion = replace(adhesion, brim_gap=brim)
    settings = replace(settings, adhesion=adhesion)
    if explicit:
        settings = print_settings.with_choice(settings, "adhesion.kind", kind)
    bodies = bodies or [
        SceneObject(
            "one",
            "Part",
            MeshData.of(trimesh.creation.box((20, 20, 20))),
            material_slots=[MaterialSlot(0, "PLA", (1.0, 1.0, 1.0), material_type="PLA")],
        )
    ]
    return bodies, settings, profile


def prepare(value):
    return usage.prepare(*value, "Project")[0]


def candidates(request):
    """Die rote Gegenprobe muss am Verhalten scheitern, nicht am noch einzelnen Feld."""
    if hasattr(request, "legacy_fingerprints"):
        return request.legacy_fingerprints
    return (request.legacy_fingerprint,) if request.legacy_fingerprint else ()


def historical_key(monkeypatch, value, fields, *, plate=True):
    """Den echten gebundenen Hash-Eingang mit den damaligen additiven Feldern lesen.

    ``plate=False`` ist der Stand von 0.5.1: ohne die (leere) Wahl der Platte (RM-705).
    """
    captured = []

    def observe(*args):
        if len(args) == 5:
            captured.append(deepcopy(args))
        return digest(*args)

    with monkeypatch.context() as scoped:
        scoped.setattr(usage, "digest", observe)
        prepare(value)
    assert captured
    payload = list(captured[0])
    for _identity, values in payload[3]:
        for name in ("brim_gap", "raft_gap"):
            values["adhesion"].pop(name, None)
        for name in fields:
            values["adhesion"][name] = getattr(value[1].adhesion, name)
        if not plate and not values["plate_choices"]:
            del values["plate_choices"]
    payload[3] = sorted(payload[3], key=digest)
    return digest(*payload)


@pytest.fixture
def stock(monkeypatch, tmp_path):
    monkeypatch.setattr(filaments, "catalogue_path", lambda: tmp_path / "filaments.json")
    return filaments.save(filaments.CatalogueFilament("PLA", "#ffffff", "PLA", remaining_grams=500))


def with_stock(request, stock):
    return replace(
        request,
        lines=tuple(
            replace(line, grams=42.0, spool_identifier=stock.identifier) for line in request.lines
        ),
    )


def position(request):
    line = request.lines[0]
    return filaments.BookingPosition(
        line.spool_identifier,
        line.grams,
        "internal",
        ui._note(line),
        filament_key=ui._line_key(line),
    )


@pytest.mark.parametrize("raft", [None, 0.0, 0.15])
def test_default_brim_preserves_pre_brim_exact_identity(monkeypatch, raft):
    value = job(raft=raft)
    previous = historical_key(monkeypatch, value, () if raft is None else ("raft_gap",))
    assert prepare(value).fingerprint == previous


@pytest.mark.parametrize("brim", [0.0, 0.12])
def test_all_historical_addition_orders_remain_possible(monkeypatch, brim):
    value = job(brim=brim, raft=0.15)
    request = prepare(value)
    expected = {
        historical_key(monkeypatch, value, fields)
        for fields in ((), ("brim_gap",), ("raft_gap",), ("brim_gap", "raft_gap"))
    } | {historical_key(monkeypatch, value, (), plate=False)}
    expected -= {request.fingerprint}
    assert set(candidates(request)) == expected
    assert len(candidates(request)) == len(expected)
    assert request.fingerprint not in candidates(request)
    assert "" not in candidates(request)


@pytest.mark.parametrize("kind,explicit", [("raft", True), ("auto", True), ("none", False)])
def test_nondefault_brim_and_active_raft_remain_different_prints(kind, explicit):
    requests = [
        prepare(job(brim=brim, raft=raft, kind=kind, explicit=explicit))
        for brim in (0.0, 0.12)
        for raft in (0.0, 0.15)
    ]
    assert len({request.fingerprint for request in requests}) == 4


@pytest.mark.parametrize(
    "kind,raft", [("none", 0.15), ("skirt", 0.0), ("brim", 0.2), ("raft", None)]
)
def test_raft_normalization_applies_to_every_candidate(monkeypatch, kind, raft):
    value = job(brim=0.12, raft=raft, kind=kind)
    current = prepare(value)
    without_raft = job(brim=0.12, raft=None, kind=kind)
    reference = prepare(without_raft)
    assert current.fingerprint == reference.fingerprint
    assert candidates(current) == candidates(reference)
    assert set(candidates(current)) == {
        historical_key(monkeypatch, value, ()),
        historical_key(monkeypatch, value, (), plate=False),
    }


@pytest.mark.parametrize("native", [False, True])
def test_missing_brim_field_and_default_zero_have_same_primary(monkeypatch, native):
    value = job(raft=0.15, native=native)
    current = prepare(value)
    assert current.fingerprint == historical_key(monkeypatch, value, ("raft_gap",))
    assert historical_key(monkeypatch, value, ()) in candidates(current)


@pytest.mark.parametrize("fields", [(), ("brim_gap",), ("raft_gap",), ("brim_gap", "raft_gap")])
@pytest.mark.parametrize("was_reversed", [False, True])
def test_only_historical_match_requires_visible_review(monkeypatch, stock, fields, was_reversed):
    value = job(brim=0.0, raft=0.15)
    request = with_stock(prepare(value), stock)
    old_key = historical_key(monkeypatch, value, fields)
    booking = filaments.book("old", old_key, [position(request)])
    if was_reversed:
        filaments.reverse_booking(booking.operation_id)
    before = filaments.read_snapshot()
    if fields == ("raft_gap",):
        result = ui._auto_book(request)
        assert result.fingerprint == request.fingerprint
        assert filaments.get(stock.identifier).remaining_grams == 458
    else:
        with pytest.raises(AppError) as raised:
            ui._auto_book(request)
        assert raised.value.values["constraint"] == "legacy_adhesion_gaps"
        assert str(raised.value.suggestions[0].label) == "Buchung prüfen …"
        assert "Brim" in str(raised.value.detail) and "Raft" in str(raised.value.detail)
        assert not ui._previous(request)
        assert ui._snapshot(request).legacy_bookings == before.bookings()
        assert filaments.read_snapshot() == before


@pytest.mark.parametrize("fields", [(), ("brim_gap",), ("raft_gap",)])
@pytest.mark.parametrize("was_reversed", [False, True])
def test_nonzero_brim_never_silently_reuses_historical_booking(
    monkeypatch, stock, fields, was_reversed
):
    value = job(brim=0.12, raft=0.15)
    request = with_stock(prepare(value), stock)
    old_key = historical_key(monkeypatch, value, fields)
    assert old_key != request.fingerprint
    filaments.book("old", old_key, [position(request)])
    if was_reversed:
        filaments.reverse_booking("old")
    before = filaments.read_snapshot()
    with pytest.raises(AppError) as raised:
        ui._auto_book(request)
    assert raised.value.values["constraint"] == "legacy_adhesion_gaps"
    assert filaments.read_snapshot() == before


def interleaved(monkeypatch, request, other):
    original_read = filaments.read_snapshot
    owner = get_ident()
    captured, resume = Event(), Event()
    first = True

    def paused():
        nonlocal first
        snapshot = original_read()
        if get_ident() != owner and first:
            first = False
            captured.set()
            assert resume.wait(5)
        return snapshot

    monkeypatch.setattr(filaments, "read_snapshot", paused)
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(ui._auto_book, request)
        try:
            assert captured.wait(5)
            other()
        finally:
            resume.set()
        with pytest.raises(AppError) as raised:
            future.result(timeout=5)
    return raised.value, original_read()


@pytest.mark.parametrize("brim", [0.0, 0.12])
@pytest.mark.parametrize("fields", [(), ("brim_gap",), ("raft_gap",), ("brim_gap", "raft_gap")])
@pytest.mark.parametrize("was_reversed", [False, True])
def test_every_empty_historical_group_is_watched_atomically(
    monkeypatch, stock, fields, was_reversed, brim
):
    value = job(brim=brim, raft=0.15)
    request = with_stock(prepare(value), stock)
    old_key = historical_key(monkeypatch, value, fields)

    def other():
        filaments.book("parallel", old_key, [position(request)])
        if was_reversed:
            filaments.reverse_booking("parallel")

    problem, snapshot = interleaved(monkeypatch, request, other)
    assert problem.values["constraint"] == "booking_history_changed"
    assert snapshot.spools[stock.identifier].remaining_grams == (500 if was_reversed else 458)
    assert len(snapshot.bookings()) == 1
    if old_key == request.fingerprint:
        assert not ui._snapshot(request).legacy_bookings
    else:
        assert ui._snapshot(request).legacy_bookings == snapshot.bookings()


@pytest.mark.parametrize("was_reversed", [False, True])
def test_exact_primary_takes_priority_over_all_historical_groups(monkeypatch, stock, was_reversed):
    value = job(brim=0.12, raft=0.15)
    request = with_stock(prepare(value), stock)
    for number, fields in enumerate(((), ("brim_gap",), ("raft_gap",))):
        filaments.book(
            f"old-{number}", historical_key(monkeypatch, value, fields), [position(request)]
        )
    exact = filaments.book("exact", request.fingerprint, [position(request)])
    if was_reversed:
        filaments.reverse_booking(exact.operation_id)
    result = ui._auto_book(request)
    assert not result.reversed_at
    assert (result.operation_id != exact.operation_id) is was_reversed
    assert filaments.get(stock.identifier).remaining_grams == 332
    assert not ui._snapshot(request).legacy_bookings


def test_geometry_plate_and_material_assignment_are_shared_by_all_candidates():
    raw = trimesh.creation.box((20, 20, 20))
    slots = [
        MaterialSlot(0, "White", (1.0, 1.0, 1.0), material_type="PLA"),
        MaterialSlot(1, "Black", (0.0, 0.0, 0.0), material_type="PLA"),
    ]
    mesh = MeshData.of(raw, (0,) * 6 + (1,) * 6)
    body = SceneObject("one", "Part", mesh, material_slots=slots)
    variants = [
        body,
        replace(body, plate=1),
        replace(body, mesh=MeshData.of(raw, (1,) * 6 + (0,) * 6)),
    ]
    groups = []
    for one in variants:
        request = prepare(job(brim=0.12, raft=0.15, bodies=[one]))
        assert len(request.lines) == 2
        adjusted = usage.from_gcode(request, GcodeMetrics(filament_grams_by_tool=(20, 30)))
        assert adjusted.fingerprint == request.fingerprint
        assert candidates(adjusted) == candidates(request)
        groups.append({request.fingerprint, *candidates(request)})
    assert not groups[0] & groups[1]
    assert not groups[0] & groups[2]
    assert body.mesh is mesh and body.material_slots is slots
