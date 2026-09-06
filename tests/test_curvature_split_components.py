"""Vertrag der gebündelten Krümmungs-Komponentensuche."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.perceive import features as features_module


def _branched_components() -> tuple[Any, list[list[int]], np.ndarray]:
    """Mehrere Flecken mit Einzelknoten, Trennkanten und einer Verzweigung."""
    patches = [
        [8, 2, 5, 0],
        [11, 4],
        [7],
        [9, 1, 6, 3, 10],
    ]
    pairs = np.asarray(
        [
            [8, 2],
            [5, 0],
            [2, 5],
            [11, 4],
            [0, 11],
            [9, 1],
            [9, 6],
            [9, 3],
            [3, 10],
        ],
        dtype=np.int64,
    )
    angles = np.radians([5.0, 5.0, 45.0, 45.0, 5.0, 4.0, 4.0, 4.0, 4.0])
    jumps = np.asarray([0.0, 0.0, 0.0, 0.0, 0.0, 0.1, 0.1, 0.1, 1.0])
    body = SimpleNamespace(
        faces=np.zeros((12, 3), dtype=np.int64),
        face_adjacency=pairs,
        face_adjacency_angles=angles,
    )
    return body, patches, jumps


def _previous_result(
    body: Any, patches: list[list[int]], jumps: np.ndarray
) -> list[list[list[int]]]:
    """Der bisherige Einzellauf je Fleck als unabhängige Referenz."""
    pairs = np.asarray(body.face_adjacency)
    angles = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float))
    result: list[list[list[int]]] = []
    for patch in patches:
        wanted = set(patch)
        edges = [
            pair
            for pair, angle, jump in zip(pairs, angles, jumps, strict=True)
            if angle < features_module.CURVATURE_LIMIT
            and jump <= features_module.CURVATURE_JUMP
            and int(pair[0]) in wanted
            and int(pair[1]) in wanted
        ]
        if not edges:
            result.append([patch])
            continue
        groups = trimesh.graph.connected_components(
            np.asarray(edges), nodes=np.asarray(patch), engine="scipy"
        )
        result.append([[int(index) for index in group] for group in groups])
    return result


def test_all_active_patches_share_one_component_search(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Bündelung bewahrt Ergebnis und Reihenfolge ohne Graphaufbau je Fleck."""
    body, patches, jumps = _branched_components()
    expected = _previous_result(body, patches, jumps)
    original = trimesh.graph.connected_component_labels
    calls = 0

    def counted(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(trimesh.graph, "connected_component_labels", counted)

    actual = features_module._split_patches_by_curvature(body, patches, jumps)

    assert actual == expected
    assert calls == 1


def test_a_cancel_after_the_native_search_stops_before_results_are_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nach dem einen nativen Lauf wird ein inzwischen bestellter Abbruch gelesen."""

    class StopHereError(RuntimeError):
        pass

    body, patches, jumps = _branched_components()
    original = trimesh.graph.connected_component_labels
    search_finished = False

    def searched(*args: Any, **kwargs: Any) -> Any:
        nonlocal search_finished
        result = original(*args, **kwargs)
        search_finished = True
        return result

    def stop() -> None:
        if search_finished:
            raise StopHereError

    monkeypatch.setattr(trimesh.graph, "connected_component_labels", searched)

    with pytest.raises(StopHereError):
        features_module._split_patches_by_curvature(
            body,
            patches,
            jumps,
            check_cancelled=stop,
        )
