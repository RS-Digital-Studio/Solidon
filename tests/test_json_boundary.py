"""Strukturgrenzen für JSON aus fremden Vertrauensräumen."""

from __future__ import annotations

import pytest

from app.core.json_boundary import StrictJsonError, loads


@pytest.mark.parametrize("raw", [b"NaN", b"Infinity", b"-Infinity", b"1e400"])
def test_non_finite_numbers_are_refused(raw: bytes) -> None:
    with pytest.raises(StrictJsonError):
        loads(raw)


def test_the_depth_boundary_accepts_its_edge_and_refuses_the_next_level() -> None:
    accepted = "[" * 7 + "0" + "]" * 7
    refused = "[" * 8 + "0" + "]" * 8

    assert loads(accepted, max_depth=8)
    with pytest.raises(StrictJsonError):
        loads(refused, max_depth=8)


def test_the_node_boundary_counts_object_keys_and_values() -> None:
    assert loads('{"a":1}', max_nodes=3) == {"a": 1}
    with pytest.raises(StrictJsonError):
        loads('{"a":1}', max_nodes=2)


def test_duplicate_object_keys_are_refused() -> None:
    with pytest.raises(StrictJsonError):
        loads('{"ok":true,"ok":false}')


def test_lone_surrogates_are_refused_but_non_bmp_unicode_is_kept() -> None:
    with pytest.raises(StrictJsonError):
        loads('"\\ud800"')

    assert loads('"\U0001f30d"') == "\U0001f30d"


def test_the_byte_and_collection_boundaries_are_enforced() -> None:
    assert loads("[0,1]", max_bytes=5, max_collection_items=2) == [0, 1]
    with pytest.raises(StrictJsonError):
        loads("[0,1]", max_bytes=4)
    with pytest.raises(StrictJsonError):
        loads("[0,1,2]", max_collection_items=2)
