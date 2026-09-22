"""Enger unabhängiger Abschluss gegen die vorhandene historische Testreferenz."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import sys
from unittest.mock import patch
import warnings

import numpy as np

root = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(root))
sys.path.insert(0, str(root / "tests"))

from test_spatial_matching import complete_reference, hole

from app.core.errors import OperationCancelled
from app.core.perceive import matching
from app.core.scene import CancelSignal


def rows(prefix, positions):
    return {f"{prefix}_{index}": hole(f"{prefix}_{index}", position) for index, position in enumerate(positions)}


def compare(name, old, new, *, solver):
    expected = complete_reference(old, new)
    old_before = [(key, dict(feature.params)) for key, feature in old.items()]
    new_before = [(key, dict(feature.params)) for key, feature in new.items()]
    calls = []
    original = matching.linear_sum_assignment

    def observed(matrix):
        calls.append(matrix.shape)
        return original(matrix)

    with patch.object(matching, "linear_sum_assignment", observed):
        result = matching.match(old, new, (0.0, 0.0, 0.0), 1.0)
    assert result == expected, (name, result, expected)
    assert calls == ([(len(old), len(new))] if solver else []), (name, calls)
    assert old_before == [(key, dict(feature.params)) for key, feature in old.items()]
    assert new_before == [(key, dict(feature.params)) for key, feature in new.items()]
    print(name, "OK", "solver:", calls)


compare("tie-keeps-global-old-id", rows("old", [0, 1, 1, 1]), rows("new", [0, 0, 1]), solver=True)
compare("grade-one-keeps-orphan-order", rows("old", [0, 1, 2, 3]), rows("new", [0, 10, 20]), solver=True)
compare("isolated-small-side-row-keeps-global-context", rows("old", [0, 5]), rows("new", [0.001, 0.01, 10]), solver=True)
compare("competition-is-not-greedy", rows("old", [0.032, -0.04]), rows("new", [0, 0.096]), solver=True)

old, new = rows("old", [0, 0.03, 0.06, 0.09]), rows("new", [0.091, 0.001, 0.061, 0.031, 5])
compare("nonzero-free-minima", old, new, solver=False)
compare("nonzero-free-minima-transposed", new, old, solver=False)

old, new = rows("old", [0]), rows("new", [0.01] * 260 + [0])
compare("later-block-is-cheapest", old, new, solver=False)
compare("later-block-is-cheapest-transposed", new, old, solver=False)
new["new_0"] = hole("new_0", 0)
compare("equal-minimum-in-later-block-is-a-real-tie", old, new, solver=True)

first = hole("old")
second = replace(hole("new"), params={**first.params, "centre": (0.04800000000000001, 0.064, 0.0)})
compare("original-batch-boundary-survives-query", {first.id: first}, {second.id: second}, solver=False)

for value, field in ((np.nan, "centre"), (np.nan, "axis"), (np.inf, "centre")):
    changed = replace(hole("new"), params={**first.params, field: (value, 0.0, 0.0)})
    old, new = {first.id: first}, {changed.id: changed}
    outcomes = []
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for call in (complete_reference, lambda a, b: matching.match(a, b, (0, 0, 0), 1.0)):
            try:
                outcomes.append(call(old, new))
            except ValueError as error:
                outcomes.append((type(error).__name__, str(error)))
    assert outcomes[0] == outcomes[1], (field, value, outcomes)
    print("nonfinite", field, value, "OK", outcomes[0])

for stage in ("_vector_costs", "linear_sum_assignment"):
    signal = CancelSignal()
    original = getattr(matching, stage)
    calls = []

    def stopped(*args, **kwargs):
        result = original(*args, **kwargs)
        calls.append(stage)
        signal.cancel()
        return result

    with patch.object(matching, stage, stopped):
        try:
            matching.match(rows("old", [0, 0]), rows("new", [0, 0]), (0, 0, 0), 1.0, check_cancelled=signal.raise_if_cancelled)
        except OperationCancelled:
            pass
        else:
            raise AssertionError("cancelled matching returned a result")
    assert calls == [stage]
    print("cancel", stage, "OK")

signal = CancelSignal()
original = matching._vector_costs
saved = matching.fingerprint(first, (0, 0, 0), 1.0)
new = rows("new", [0, 0.01])

def stop_resolve(*args, **kwargs):
    result = original(*args, **kwargs)
    signal.cancel()
    return result

with patch.object(matching, "_vector_costs", stop_resolve):
    try:
        matching.resolve(saved, tuple(new), new, (0, 0, 0), 1.0, check_cancelled=signal.raise_if_cancelled)
    except OperationCancelled:
        pass
    else:
        raise AssertionError("cancelled saved choice returned a result")
print("cancel stored-choice comparison OK")
print("review probes completed")
