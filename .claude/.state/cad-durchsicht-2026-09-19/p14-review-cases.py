"""Konkrete Zuordnungsgegenfälle ohne Leistungsmessung oder Produktänderung."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import patch

import numpy as np

spec = importlib.util.spec_from_file_location("review_probe", Path(__file__).with_name("p14-review-probe.py"))
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
matching = probe.matching
Feature = probe.Feature


def features(prefix, points):
    return {
        f"{prefix}_{index}": Feature(
            f"{prefix}_{index}", "hole", "detected",
            {"centre": (point, 0.0, 0.0), "axis": (0.0, 0.0, 1.0), "diameter": 6.0},
        )
        for index, point in enumerate(points)
    }


def actual(name, old_points, new_points):
    old, new = features("old", old_points), features("new", new_points)
    print(name)
    print("raw_costs:", matching._cost_matrix(list(old.values()), list(new.values()), (0, 0, 0), (0, 0, 0), 1.0).tolist())
    print("global:", matching.match(old, new, (0.0, 0.0, 0.0), 1.0))
    with patch.object(matching, "linear_sum_assignment", probe.local_assignment):
        print("local:", matching.match(old, new, (0.0, 0.0, 0.0), 1.0))


actual("real-feature-tie", [0.0, 1.0, 1.0, 1.0], [0.0, 0.0, 1.0])
actual("greedy-is-not-assignment", [0.032, -0.04], [0.0, 0.096])

penalty = matching.KIND_PENALTY
for delta in (0.0, 1e-8, 1e-10, 1e-11, 1e-12, 1e-13, 1e-14):
    matrix = np.asarray([
        [0.0, 0.0, penalty],
        [penalty, penalty, 0.2 + delta],
        [penalty, penalty, 0.2],
        [penalty, penalty, 0.2 + 2 * delta],
    ])
    global_result, local_result = probe.result_for(matrix, local=False), probe.result_for(matrix, local=True)
    if global_result.mapping != local_result.mapping:
        probe.show(f"near-tie-delta={delta}", matrix)
    matrix[1, 2], matrix[2, 2] = matrix[2, 2], matrix[1, 2]
    global_result, local_result = probe.result_for(matrix, local=False), probe.result_for(matrix, local=True)
    if delta > 0.0 and global_result.mapping != local_result.mapping:
        probe.show(f"unique-real-optimum-with-penalty-rounding-delta={delta}", matrix)

probe.show("rejected-edge-is-not-rival", np.asarray([[0.9, 1.01]]))
probe.show("global-selected-cost-is-rival-reference", np.asarray([[0.4, 0.8], [0.5, 1.7]]))
probe.show("grade-one-orphan-order", np.asarray([
    [0.0, penalty, penalty],
    [penalty, penalty, penalty],
    [penalty, penalty, penalty],
    [penalty, penalty, penalty],
]))
probe.show("only-ambiguous-choice-order", np.asarray([
    [0.0, penalty, penalty],
    [0.0, penalty, penalty],
    [penalty, 0.0, 0.0],
]))

# Numerische Kugelanfrage und bisherige Positionsformel sind nicht dieselbe
# Gleitkommaberechnung. Ein Kandidat am Rand darf nicht vor cost verloren gehen.
from scipy.spatial import cKDTree
from fractions import Fraction
import math

radius = matching.POSITION_TOLERANCE * matching.MATCH_THRESHOLD
unit_roundoff = Fraction(1, 2**53)
reserve = Fraction(matching.POSITION_TOLERANCE) * Fraction(matching.MATCH_THRESHOLD) / (1 - unit_roundoff)**5
safe_radius = float(reserve)
if Fraction(safe_radius) < reserve:
    safe_radius = math.nextafter(safe_radius, math.inf)
print("certified-cube-radius:", safe_radius)
directions = [(1.0, 0.0, 0.0), (0.6, 0.8, 0.0), (1.0, 1.0, 1.0), (2.0, 3.0, 7.0)]
for direction in directions:
    point = np.asarray(direction) * (radius / np.linalg.norm(direction))
    for axis in range(3):
        candidate = point.copy()
        for steps in range(-4, 5):
            candidate[axis] = point[axis]
            destination = np.inf if steps > 0 else -np.inf
            for _ in range(abs(steps)):
                candidate[axis] = np.nextafter(candidate[axis], destination)
            raw = float(np.linalg.norm(candidate[None, :], axis=1)[0] / matching.POSITION_TOLERANCE)
            query = cKDTree(np.asarray([candidate])).query_ball_point(np.zeros(3), radius)
            conservative = cKDTree(np.asarray([candidate])).query_ball_point(np.zeros(3), safe_radius, p=np.inf)
            assert raw > matching.MATCH_THRESHOLD or conservative == [0]
            if raw <= matching.MATCH_THRESHOLD and not query:
                print("query-boundary-miss:", candidate.tolist(), "cost:", raw, "radius:", radius)
                break

random = np.random.default_rng(14142026)
for direction in random.normal(size=(128, 3)):
    candidate = direction * (radius / np.linalg.norm(direction))
    batch = float(np.linalg.norm(candidate[None, :], axis=1)[0] / matching.POSITION_TOLERANCE)
    scalar = float(np.linalg.norm(candidate) / matching.POSITION_TOLERANCE)
    if (batch <= 1.0) != (scalar <= 1.0):
        print("scalar-batch-threshold-difference:", candidate.tolist(), "batch:", batch, "scalar:", scalar)
        break
