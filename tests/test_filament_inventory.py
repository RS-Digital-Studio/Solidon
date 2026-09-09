"""Spulenidentität, Mengen und atomare Lagerbuchungen über Prozessgrenzen."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from app.core.errors import FileWriteError, ValidationError
from app.core.knowledge import filaments


@pytest.fixture(autouse=True)
def own_inventory(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Kein Test berührt die Spulen im Nutzerprofil."""
    monkeypatch.setattr(filaments, "user_config_dir", lambda: tmp_path)


def spool(grams: float | None = 500.0) -> filaments.CatalogueFilament:
    """Eine wirklich vorhandene Spule mit ausdrücklich bekanntem oder unbekanntem Rest."""
    return filaments.save(filaments.CatalogueFilament("PETG Rot", "#d02020", remaining_grams=grams))


def current(entry: filaments.CatalogueFilament) -> filaments.CatalogueFilament:
    """Liest den beständigen Datensatz nach einer Buchung neu."""
    found = filaments.get(entry.identifier)
    assert found is not None
    return found


def position(
    entry: filaments.CatalogueFilament,
    grams: float = 42.0,
    source: filaments.BookingSource = "internal",
    *,
    filament_key: str = "",
) -> filaments.BookingPosition:
    """Eine Ausgabezeile kennt Spule und Herkunft vor dem Schreiben."""
    return filaments.BookingPosition(entry.identifier, grams, source, filament_key=filament_key)


def test_same_labels_remain_independent_spools() -> None:
    first, second = spool(), spool()
    assert first.identifier != second.identifier
    changed = filaments.save(replace(first, name="Neue Bezeichnung", colour="#ffffff"))
    assert changed.identifier == first.identifier
    assert current(second) == second
    assert len(filaments.catalogue()) == 2


def test_legacy_migration_persists_unique_ids_without_inventing_amounts() -> None:
    legacy = Path(__file__).parent / "data" / "filament_catalogue_v0.json"
    filaments.catalogue_path().write_bytes(legacy.read_bytes())
    first = filaments.catalogue(strict=True)
    encoded = json.loads(filaments.catalogue_path().read_text(encoding="utf-8"))
    assert encoded["format_version"] == filaments.FORMAT_VERSION
    assert encoded["inventory_identifier"]
    assert len({entry.identifier for entry in first}) == 2
    assert filaments.catalogue(strict=True) == first
    for entry in first:
        assert entry.diameter_mm is entry.spool_grams is entry.remaining_grams is None
    assert filaments.inventory_identifier() == encoded["inventory_identifier"]


def test_separate_inventories_never_derive_ids_from_the_same_label(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    legacy = '[{"name":"Weiß","colour":"#ffffff"}]'
    filaments.catalogue_path().write_text(legacy, encoding="utf-8")
    (first,) = filaments.catalogue()
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.setattr(filaments, "user_config_dir", lambda: other)
    filaments.catalogue_path().write_text(legacy, encoding="utf-8")
    (second,) = filaments.catalogue()
    assert first.identifier != second.identifier


def test_optional_metadata_roundtrips_without_changing_stock() -> None:
    saved = filaments.save(
        filaments.CatalogueFilament(
            "PLA",
            "#eeeeee",
            "PLA",
            "Generic PLA",
            diameter_mm=1.75,
            spool_grams=750,
            remaining_grams=None,
            location="Schrank 2",
            opened_on="2026-09-08",
            bought_on="2026-08-12",
            price=19.95,
            currency="eur",
            note="Trocken lagern",
        )
    )
    assert current(saved) == saved
    assert saved.currency == "EUR"
    assert saved.remaining_grams is None


@pytest.mark.parametrize(
    "field,value",
    [
        ("remaining_grams", -1.0),
        ("remaining_grams", float("nan")),
        ("remaining_grams", float("inf")),
        ("remaining_grams", True),
        ("spool_grams", 0.0),
        ("diameter_mm", 0.0),
        ("price", -1.0),
        ("price", 20.0),
        ("currency", "Euro"),
        ("opened_on", "2026-02-30"),
        ("bought_on", "08.09.2026"),
    ],
)
def test_invalid_metadata_never_writes(field: str, value: object) -> None:
    with pytest.raises(ValidationError) as raised:
        filaments.save(replace(filaments.CatalogueFilament("PLA", "#eeeeee"), **{field: value}))
    assert raised.value.suggestions
    assert filaments.catalogue() == ()


def test_duplicate_preserves_product_details_but_never_stock_or_history() -> None:
    first = spool()
    filaments.book("first-print", "geometry", [position(first)])
    copy = filaments.duplicate(first.identifier)
    assert copy.identifier != first.identifier
    assert copy.name == first.name
    assert copy.remaining_grams is None
    assert filaments.bookings(copy.identifier) == ()
    assert len(filaments.bookings(first.identifier)) == 1


def test_archive_keeps_history_and_can_be_restored() -> None:
    first = spool()
    filaments.book("first-print", "geometry", [position(first)])
    archived = filaments.archive(first.identifier)
    assert filaments.catalogue() == ()
    assert filaments.catalogue(include_archived=True) == (archived,)
    assert len(filaments.bookings(first.identifier)) == 1
    with pytest.raises(ValidationError):
        filaments.book("new-print", "geometry", [position(first)])
    filaments.reverse_booking("first-print")
    restored = filaments.restore(first.identifier)
    assert restored.identifier == first.identifier
    assert restored.remaining_grams == pytest.approx(500)


def test_stale_dialog_cannot_undo_a_newer_consumption() -> None:
    first = spool()
    filaments.book("first-print", "geometry", [position(first)])
    with pytest.raises(ValidationError) as raised:
        filaments.save(replace(first, name="Geänderter Name"))
    assert raised.value.constraint == "conflict"
    assert current(first).remaining_grams == pytest.approx(458)


def test_metadata_edit_preserves_the_consumption_baseline() -> None:
    first = spool()
    filaments.book("first-print", "geometry", [position(first)])
    filaments.save(replace(current(first), location="Andere Schublade"))
    filaments.reverse_booking("first-print")
    assert current(first).remaining_grams == pytest.approx(500)
    assert current(first).location == "Andere Schublade"


def test_synchronise_preserves_metadata_stock_and_identity() -> None:
    first = filaments.save(
        filaments.CatalogueFilament(
            "Generic PLA",
            "#ffffff",
            "PLA",
            "PLA @System",
            remaining_grams=250,
            spool_grams=1000,
            location="Schublade",
            note="Geprüft",
        )
    )
    supplied = filaments.CatalogueFilament("Generic PLA (#FFFFFF)", "#ffffff", "PLA", "PLA @System")
    filaments.synchronise([supplied])
    filaments.synchronise([supplied])
    actual = current(first)
    assert len(filaments.catalogue()) == 1
    assert actual.remaining_grams == pytest.approx(250)
    assert actual.spool_grams == pytest.approx(1000)
    assert actual.location == "Schublade"
    assert actual.note == "Geprüft"


def test_legacy_name_operations_reject_duplicate_labels() -> None:
    spool()
    spool()
    for action in (
        lambda: filaments.remember("PETG Rot", "#eeeeee"),
        lambda: filaments.forget("PETG Rot"),
        lambda: filaments.synchronise([filaments.CatalogueFilament("PETG Rot", "#eeeeee")]),
    ):
        with pytest.raises(ValidationError) as raised:
            action()
        assert raised.value.constraint == "ambiguous"
    assert len(filaments.catalogue()) == 2


def test_multi_spool_booking_is_one_atomic_journal_entry() -> None:
    first, second = spool(), spool(300)
    booking = filaments.book(
        "print", "geometry", [position(first), position(second, 17, "gcode")], project_name="Halter"
    )
    assert booking.project_name == "Halter"
    assert len(booking.positions) == 2
    assert current(first).remaining_grams == pytest.approx(458)
    assert current(second).remaining_grams == pytest.approx(283)
    assert filaments.bookings() == (booking,)
    assert filaments.bookings(second.identifier) == (booking,)


def test_insufficient_second_spool_never_leaves_a_partial_booking() -> None:
    first, second = spool(), spool(5)
    before = filaments.catalogue_path().read_bytes()
    with pytest.raises(ValidationError):
        filaments.book("print", "geometry", [position(first), position(second)])
    assert filaments.catalogue_path().read_bytes() == before
    assert filaments.bookings() == ()


@pytest.mark.parametrize("grams", [-1.0, float("inf"), float("nan")])
def test_invalid_consumption_is_rejected(grams: float) -> None:
    first = spool()
    with pytest.raises(ValidationError):
        filaments.book("print", "geometry", [position(first, grams)])
    assert current(first).remaining_grams == pytest.approx(500)


def test_unknown_is_not_empty_or_full_and_needs_explicit_confirmation() -> None:
    first = spool(None)
    with pytest.raises(ValidationError):
        filaments.book("print", "geometry", [position(first)])
    booked = filaments.book("print", "geometry", [position(first)], allow_unverified_stock=True)
    assert booked.positions[0].grams == pytest.approx(42)
    assert current(first).remaining_grams is None
    filaments.reverse_booking("print")
    assert current(first).remaining_grams is None


def test_confirmed_underflow_keeps_the_whole_quantity_and_reverses_cleanly() -> None:
    first = spool(10)
    booked = filaments.book("print", "geometry", [position(first, 42)], allow_unverified_stock=True)
    assert current(first).remaining_grams is None
    assert booked.positions[0].grams == pytest.approx(42)
    filaments.book("later", "other", [position(first, 2)], allow_unverified_stock=True)
    filaments.reverse_booking("print")
    assert current(first).remaining_grams == pytest.approx(8)


def test_exact_empty_and_zero_consumption_remain_known() -> None:
    first = spool(42)
    filaments.book("print", "geometry", [position(first, 42)])
    assert current(first).remaining_grams == pytest.approx(0)
    filaments.book("zero", "other", [position(first, 0)])
    assert current(first).remaining_grams == pytest.approx(0)


def test_decimal_consumptions_can_empty_a_spool_without_false_underflow() -> None:
    first = spool(3.3)
    filaments.book("first", "one", [position(first, 1.1)])
    filaments.book("second", "two", [position(first, 2.2)])
    assert current(first).remaining_grams == pytest.approx(0)


def test_previously_saved_roundoff_underflow_is_recovered_from_the_full_journal() -> None:
    first = spool(3.3)
    filaments.book("first", "one", [position(first, 1.1)])
    filaments.book("second", "two", [position(first, 2.2)])
    data = json.loads(filaments.catalogue_path().read_text(encoding="utf-8"))
    # Genau diesen Cachewert schrieb die ältere Fassung bei bestätigtem Abzug.
    data["spools"][0]["remaining_grams"] = None
    revision = data["spools"][0]["revision"]
    filaments.catalogue_path().write_text(json.dumps(data), encoding="utf-8")
    recovered = current(first)
    assert recovered.remaining_grams == pytest.approx(0)
    assert recovered.revision == revision + 1
    saved = json.loads(filaments.catalogue_path().read_text(encoding="utf-8"))
    assert saved["bookings"] == data["bookings"]
    assert saved["stock_counts"] == data["stock_counts"]


def test_a_real_decimal_underflow_is_not_rounded_to_empty() -> None:
    first = spool(3.3)
    with pytest.raises(ValidationError) as raised:
        filaments.book("print", "geometry", [position(first, 3.3001)])
    assert raised.value.constraint == "stock"
    assert current(first).remaining_grams == pytest.approx(3.3)


def test_overflowing_consumption_total_is_an_actionable_atomic_rejection() -> None:
    first = spool(1e308)
    before = filaments.catalogue_path().read_bytes()
    with pytest.raises(ValidationError) as raised:
        filaments.book(
            "print",
            "geometry",
            [position(first, 1e308, filament_key="a"), position(first, 1e308, filament_key="b")],
            allow_unverified_stock=True,
        )
    assert raised.value.suggestions
    assert filaments.catalogue_path().read_bytes() == before


def test_an_integer_outside_float_range_is_an_actionable_input_error() -> None:
    with pytest.raises(ValidationError) as raised:
        spool(10**400)
    assert raised.value.suggestions
    assert not filaments.catalogue_path().exists()


def test_out_of_range_number_in_file_is_rejected_without_overwriting() -> None:
    first = spool()
    data = json.loads(filaments.catalogue_path().read_text(encoding="utf-8"))
    data["stock_counts"][first.identifier] = 10**400
    broken = json.dumps(data)
    filaments.catalogue_path().write_text(broken, encoding="utf-8")
    assert filaments.catalogue() == ()
    with pytest.raises(ValidationError) as raised:
        filaments.catalogue(strict=True)
    assert raised.value.constraint == "unreadable"
    assert filaments.catalogue_path().read_text(encoding="utf-8") == broken


def test_repeated_delivery_is_idempotent_even_with_reordered_positions() -> None:
    first, second = spool(), spool()
    rows = [position(first), position(second, 3)]
    booking = filaments.book("print", "geometry", rows)
    before = filaments.catalogue_path().read_bytes()
    assert filaments.book("print", "geometry", list(reversed(rows))) == booking
    assert filaments.catalogue_path().read_bytes() == before


@pytest.mark.parametrize("fingerprint,grams", [("geometry", 43), ("changed", 42)])
def test_same_operation_with_other_payload_is_a_conflict(fingerprint: str, grams: float) -> None:
    first = spool()
    filaments.book("print", "geometry", [position(first)])
    with pytest.raises(ValidationError) as raised:
        filaments.book("print", fingerprint, [position(first, grams)])
    assert raised.value.constraint == "conflict"
    assert current(first).remaining_grams == pytest.approx(458)


@pytest.mark.parametrize("grams,expected", [(47, 453), (37, 463)])
def test_gcode_replaces_estimate_by_its_difference(grams: float, expected: float) -> None:
    first = spool()
    filaments.book("print", "geometry", [position(first)])
    corrected = filaments.book("print", "geometry", [position(first, grams, "gcode")])
    assert current(first).remaining_grams == pytest.approx(expected)
    assert corrected.positions[0].source == "gcode"
    assert len(corrected.corrections) == 1
    assert corrected.corrections[0].previous_positions[0].grams == pytest.approx(42)
    assert filaments.book("print", "geometry", [position(first)]) == corrected
    filaments.reverse_booking("print")
    assert current(first).remaining_grams == pytest.approx(500)


def test_same_spool_can_keep_separate_filament_sources() -> None:
    first = spool()
    rows = [position(first, 30, filament_key="a"), position(first, 12, filament_key="b")]
    filaments.book("print", "geometry", rows)
    corrected = filaments.book(
        "print", "geometry", [replace(rows[0], grams=35, source="gcode"), rows[1]]
    )
    assert current(first).remaining_grams == pytest.approx(453)
    assert [row.source for row in corrected.positions] == ["gcode", "internal"]
    assert [row.filament_key for row in corrected.positions] == ["a", "b"]


def test_manual_reallocation_requires_explicit_correction_and_keeps_history() -> None:
    first, second = spool(), spool()
    original = [position(first, 42, filament_key="a")]
    filaments.book("print", "geometry", original)
    allocated = [
        position(first, 20, "manual", filament_key="a"),
        position(second, 27, "manual", filament_key="a"),
    ]
    with pytest.raises(ValidationError):
        filaments.book("print", "geometry", allocated)
    corrected = filaments.book("print", "geometry", allocated, correct_manual_allocation=True)
    assert len(corrected.corrections) == 1
    assert current(first).remaining_grams == pytest.approx(480)
    assert current(second).remaining_grams == pytest.approx(473)
    assert len(filaments.bookings(first.identifier)) == 1
    filaments.reverse_booking("print")
    assert current(first).remaining_grams == pytest.approx(500)
    assert current(second).remaining_grams == pytest.approx(500)


def test_stale_manual_correction_cannot_rewind_a_newer_allocation() -> None:
    first, second = spool(), spool()
    original = filaments.book("print", "geometry", [position(first, filament_key="model")])
    allocation = [
        position(first, 20, "manual", filament_key="model"),
        position(second, 22, "manual", filament_key="model"),
    ]
    corrected = filaments.book(
        "print",
        "geometry",
        allocation,
        correct_manual_allocation=True,
        expected_booking_updated_at=original.updated_at,
    )
    assert (
        filaments.book(
            "print",
            "geometry",
            allocation,
            correct_manual_allocation=True,
            expected_booking_updated_at=original.updated_at,
        )
        == corrected
    )
    filaments.book(
        "print",
        "geometry",
        [position(second, 42, "manual", filament_key="model")],
        correct_manual_allocation=True,
        expected_booking_updated_at=corrected.updated_at,
    )
    before = filaments.catalogue_path().read_bytes()
    with pytest.raises(ValidationError) as raised:
        filaments.book(
            "print",
            "geometry",
            allocation,
            correct_manual_allocation=True,
            expected_booking_updated_at=original.updated_at,
        )
    assert raised.value.constraint == "conflict"
    assert filaments.catalogue_path().read_bytes() == before
    assert current(first).remaining_grams == pytest.approx(500)
    assert current(second).remaining_grams == pytest.approx(458)


@pytest.mark.parametrize("support_source", ["gcode", "manual"])
def test_gcode_can_add_a_previously_unknown_support_tool(support_source) -> None:
    first, second = spool(), spool()
    original_rows = [position(first, filament_key="model")]
    original = filaments.book("print", "geometry", original_rows)
    rows = [
        position(first, 47, "gcode", filament_key="model"),
        position(second, 6, support_source, filament_key="support"),
    ]
    corrected = filaments.book(
        "print", "geometry", rows, expected_booking_updated_at=original.updated_at
    )
    assert current(first).remaining_grams == pytest.approx(453)
    assert current(second).remaining_grams == pytest.approx(494)
    assert filaments.book("print", "geometry", original_rows) == corrected
    assert (
        filaments.book("print", "geometry", rows, expected_booking_updated_at=original.updated_at)
        == corrected
    )
    filaments.reverse_booking("print")
    assert current(first).remaining_grams == pytest.approx(500)
    assert current(second).remaining_grams == pytest.approx(500)


def test_additional_gcode_tool_requires_the_current_booking_revision() -> None:
    first, second = spool(), spool()
    original = filaments.book("print", "geometry", [position(first, filament_key="model")])
    changed = [position(first, 47, "gcode", filament_key="model")]
    filaments.book("print", "geometry", changed)
    before = filaments.catalogue_path().read_bytes()
    with pytest.raises(ValidationError) as raised:
        filaments.book(
            "print",
            "geometry",
            [*changed, position(second, 6, "gcode", filament_key="support")],
            expected_booking_updated_at=original.updated_at,
        )
    assert raised.value.constraint == "conflict"
    assert filaments.catalogue_path().read_bytes() == before


@pytest.mark.parametrize(
    "replacement", ["omit_model", "change_model_spool", "internal_support", "same_filament"]
)
def test_additional_tool_does_not_allow_replacing_existing_identities(replacement) -> None:
    first, second = spool(), spool()
    original = filaments.book("print", "geometry", [position(first, filament_key="model")])
    model = position(first, 47, "gcode", filament_key="model")
    support = position(second, 6, "gcode", filament_key="support")
    rows = [model, support]
    if replacement == "omit_model":
        rows = [support]
    elif replacement == "change_model_spool":
        rows[0] = replace(model, spool_identifier=second.identifier)
    elif replacement == "internal_support":
        rows[1] = replace(support, source="internal")
    else:
        rows[1] = replace(support, filament_key="model")
    before = filaments.catalogue_path().read_bytes()
    with pytest.raises(ValidationError):
        filaments.book("print", "geometry", rows, expected_booking_updated_at=original.updated_at)
    assert filaments.catalogue_path().read_bytes() == before


def test_manual_value_to_gcode_is_never_an_automatic_correction() -> None:
    first = spool()
    filaments.book("print", "geometry", [position(first, 42, "manual")])
    with pytest.raises(ValidationError):
        filaments.book("print", "geometry", [position(first, 47, "gcode")])
    filaments.book(
        "print", "geometry", [position(first, 47, "gcode")], correct_manual_allocation=True
    )
    assert current(first).remaining_grams == pytest.approx(453)


def test_repeat_print_is_a_new_operation_even_for_same_preparation() -> None:
    first = spool()
    filaments.book("print", "geometry", [position(first)])
    filaments.book("repeat", "geometry", [position(first)])
    assert current(first).remaining_grams == pytest.approx(416)
    assert len(filaments.bookings()) == 2


def test_reversal_returns_all_positions_once_and_keeps_other_prints() -> None:
    first, second = spool(), spool()
    filaments.book("print", "geometry", [position(first), position(second, 20)])
    filaments.book("later", "other", [position(first, 10)])
    reversed_booking = filaments.reverse_booking("print")
    assert reversed_booking.reversed_at
    assert filaments.reverse_booking("print") == reversed_booking
    assert current(first).remaining_grams == pytest.approx(490)
    assert current(second).remaining_grams == pytest.approx(500)
    assert (
        filaments.book("print", "geometry", [position(first), position(second, 20)])
        == reversed_booking
    )


@pytest.mark.parametrize("action", ["reverse", "correct"])
def test_a_newer_manual_count_blocks_the_entire_old_operation(action: str) -> None:
    first, second = spool(), spool()
    filaments.book("print", "geometry", [position(first), position(second)])
    filaments.save(replace(current(second), remaining_grams=200))
    before = filaments.catalogue_path().read_bytes()
    with pytest.raises(ValidationError) as raised:
        if action == "reverse":
            filaments.reverse_booking("print")
        else:
            filaments.book(
                "print", "geometry", [position(first, 47, "gcode"), position(second, 50, "gcode")]
            )
    assert raised.value.constraint == "stock_conflict"
    assert filaments.catalogue_path().read_bytes() == before


def test_explicit_reversal_preserves_new_counts_and_refunds_other_spools() -> None:
    first, second = spool(), spool()
    filaments.book("print", "geometry", [position(first), position(second)])
    filaments.save(replace(current(second), remaining_grams=200))
    reversed_booking = filaments.reverse_booking("print", preserve_newer_counts=True)
    assert reversed_booking.reversed_at
    assert len(reversed_booking.preserved_counts) == 1
    assert reversed_booking.preserved_counts[0].spool_identifier == second.identifier
    assert reversed_booking.preserved_counts[0].grams == pytest.approx(200)
    assert current(first).remaining_grams == pytest.approx(500)
    assert current(second).remaining_grams == pytest.approx(200)
    assert filaments.bookings() == (reversed_booking,)
    assert filaments.reverse_booking("print") == reversed_booking


def test_explicit_recount_of_the_same_quantity_also_protects_newer_knowledge() -> None:
    first = spool()
    filaments.book("print", "geometry", [position(first)])
    filaments.set_remaining(first.identifier, 458)
    with pytest.raises(ValidationError) as raised:
        filaments.reverse_booking("print")
    assert raised.value.constraint == "stock_conflict"


@pytest.mark.parametrize("broken", ["{", "null", '{"format_version":999}', '[{"name":"PLA"}]'])
def test_corrupt_and_future_catalogues_are_never_overwritten(broken: str) -> None:
    filaments.catalogue_path().write_text(broken, encoding="utf-8")
    assert filaments.catalogue() == ()
    with pytest.raises(ValidationError):
        filaments.catalogue(strict=True)
    with pytest.raises(ValidationError):
        spool()
    assert filaments.catalogue_path().read_text(encoding="utf-8") == broken


def test_a_damaged_journal_cannot_be_overwritten_by_metadata() -> None:
    first = spool()
    filaments.book("print", "geometry", [position(first)])
    data = json.loads(filaments.catalogue_path().read_text(encoding="utf-8"))
    data["bookings"][0]["positions"][0]["grams"] = -1
    broken = json.dumps(data)
    filaments.catalogue_path().write_text(broken, encoding="utf-8")
    with pytest.raises(ValidationError):
        filaments.save(replace(first, name="Anderer Name"))
    assert filaments.catalogue_path().read_text(encoding="utf-8") == broken


@pytest.mark.parametrize(
    "damage", ["history_spool", "history_revision", "history_chain", "timestamp", "preserved_count"]
)
def test_damaged_correction_history_blocks_metadata_writes(damage: str) -> None:
    first = spool()
    filaments.book("print", "geometry", [position(first)])
    filaments.book("print", "geometry", [position(first, 47, "gcode")])
    filaments.set_remaining(first.identifier, 200)
    filaments.reverse_booking("print", preserve_newer_counts=True)
    metadata = current(first)
    data = json.loads(filaments.catalogue_path().read_text(encoding="utf-8"))
    booking = data["bookings"][0]
    correction = booking["corrections"][0]
    if damage == "history_spool":
        correction["previous_positions"][0]["spool_identifier"] = "missing-spool"
    elif damage == "history_revision":
        correction["previous_positions"][0]["stock_revision"] = 1000
    elif damage == "history_chain":
        correction["positions"][0]["grams"] = 999
    elif damage == "timestamp":
        correction["created_at"] = {"not": "a timestamp"}
    else:
        booking["preserved_counts"][0]["spool_identifier"] = "missing-spool"
    broken = json.dumps(data)
    filaments.catalogue_path().write_text(broken, encoding="utf-8")
    with pytest.raises(ValidationError) as raised:
        filaments.save(replace(metadata, note="Neue Notiz"))
    assert raised.value.constraint == "unreadable"
    assert filaments.catalogue_path().read_text(encoding="utf-8") == broken


def test_failed_atomic_replace_keeps_stock_and_journal_together(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = spool()
    before = filaments.catalogue_path().read_bytes()

    def fail(source: Path, target: Path) -> Path:
        raise OSError("simulated full disk")

    monkeypatch.setattr(Path, "replace", fail)
    with pytest.raises(FileWriteError):
        filaments.book("print", "geometry", [position(first)])
    assert filaments.catalogue_path().read_bytes() == before
    assert not filaments.catalogue_path().with_name("filaments.json.tmp").exists()


def test_two_processes_keep_each_others_spools_and_book_once(tmp_path: Path) -> None:
    """Zwei echte Python-Prozesse liefern denselben Vorgang und verschiedene neue Spulen."""
    first = spool()
    script = """
import sys
from pathlib import Path
from app.core.knowledge import filaments
folder, identifier, prefix = sys.argv[1:]
filaments.user_config_dir = lambda: Path(folder)
for index in range(12):
    filaments.save(filaments.CatalogueFilament(prefix + str(index), '#eeeeee'))
    filaments.book('print', 'geometry', [filaments.BookingPosition(identifier, 42)])
"""
    processes = [
        subprocess.Popen(
            [sys.executable, "-c", script, str(tmp_path), first.identifier, prefix],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        for prefix in ("first-", "second-")
    ]
    try:
        for process in processes:
            _, stderr = process.communicate(timeout=30)
            assert process.returncode == 0, stderr.decode("utf-8", errors="replace")
    finally:
        for process in processes:
            if process.poll() is None:
                process.kill()
                process.communicate()
    assert len(filaments.catalogue()) == 25
    assert current(first).remaining_grams == pytest.approx(458)
    assert len(filaments.bookings()) == 1
