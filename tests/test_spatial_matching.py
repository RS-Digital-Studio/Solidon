"""Räumliche Vorauswahl erhält die vollständige Zuordnung und ihren Abbruch."""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from app.core.errors import OperationCancelled
from app.core.perceive import matching
from app.core.perceive.matching import MatchResult, cost, feature_vector, match
from app.core.scene import CancelSignal
from app.core.types import Feature


def hole(identifier, x=0.0):
    return Feature(
        identifier,
        "hole",
        "detected",
        {"centre": (x, 0.0, 0.0), "axis": (0.0, 0.0, 1.0), "diameter": 4.0},
    )


@pytest.mark.parametrize("old,new", [({}, {}), ({"old": hole("old")}, {"new": hole("new")})])
def test_cancelled_matching_stops_before_any_answer(old, new):
    signal = CancelSignal()
    signal.cancel()
    with pytest.raises(OperationCancelled):
        match(old, new, (0.0, 0.0, 0.0), 1.0, check_cancelled=signal.raise_if_cancelled)


def complete_reference(
    old, new, centre=(0.0, 0.0, 0.0), diagonal=1.0, old_centre=None, *, assignment_only=False
):
    """Eingefrorener Vollvergleich einschließlich Solver-Kontext und Ausgabeordnung."""
    if not old:
        return MatchResult(fresh=tuple(new))
    if not new:
        return MatchResult(orphaned=tuple(old))
    before = centre if old_centre is None else old_centre
    one = np.asarray([feature_vector(entry, before, diagonal) for entry in old.values()])
    two = np.asarray([feature_vector(entry, centre, diagonal) for entry in new.values()])
    # Bewusst unabhängige Testreferenz der bisherigen vollständigen Formel.
    matrix = np.linalg.norm(one[:, None, :3] - two[None, :, :3], axis=2) / 0.08
    axes = np.linalg.norm(one[:, None, 3:6] - two[None, :, 3:6], axis=2)
    signless = np.asarray(["axis" in feature.params for feature in old.values()])
    axes[signless] = np.minimum(
        axes[signless], np.linalg.norm(one[signless, None, 3:6] + two[None, :, 3:6], axis=2)
    )
    matrix += axes / 0.3
    size = np.maximum(np.abs(one[:, None, 6]), np.abs(two[None, :, 6]))
    np.maximum(size, matching.EPS_GEOM, out=size)
    matrix += (np.abs(one[:, None, 6] - two[None, :, 6]) / size) / 0.15
    old_kinds = np.asarray([entry.kind for entry in old.values()])
    new_kinds = np.asarray([entry.kind for entry in new.values()])
    matrix[old_kinds[:, None] != new_kinds[None, :]] = 1e6
    matrix = np.where(matrix > 1.0, 1e6, matrix)
    from scipy.optimize import linear_sum_assignment

    rows, columns = linear_sum_assignment(matrix)
    if assignment_only:
        return matrix, rows, columns
    result = MatchResult()
    old_ids, new_ids = list(old), list(new)
    for row, column in zip(rows, columns, strict=True):
        if matrix[row, column] > 1.0:
            result.orphaned = (*result.orphaned, old_ids[row])
            continue
        rivals = [
            new_ids[index]
            for index, value in enumerate(matrix[row])
            if index != column and value <= matrix[row, column] * 1.25 + 0.05
        ]
        if rivals:
            result.ambiguous[old_ids[row]] = (new_ids[column], *rivals)
        else:
            result.mapping[old_ids[row]] = new_ids[column]
    result.orphaned = (
        tuple(
            identifier
            for identifier in old
            if identifier not in result.mapping
            and identifier not in result.ambiguous
            and identifier not in result.orphaned
        )
        + result.orphaned
    )
    result.fresh = tuple(
        identifier for identifier in new if identifier not in result.mapping.values()
    )
    return result


def assert_original_assignment(old, new):
    """P1.4a-Kosten und Solverantwort unabhängig von der neuen Identitätsfreigabe prüfen."""
    matrix, rows, columns = complete_reference(old, new, assignment_only=True)
    assigned = matching._assignment(
        list(old.values()), list(new.values()), (0, 0, 0), (0, 0, 0), 1.0, None
    )
    np.testing.assert_array_equal(assigned.rows, rows)
    np.testing.assert_array_equal(assigned.columns, columns)
    np.testing.assert_array_equal(assigned.values, matrix[rows, columns])
    if assigned.matrix is not None:
        np.testing.assert_array_equal(assigned.matrix, matrix)
    # Auch der selektive Kostenweg liefert jedes angenommene Paar und nur diese.
    seen = np.full(matrix.shape, matching.KIND_PENALTY)
    for row, nearby, values in assigned.pairs():
        seen[row, nearby] = values
    np.testing.assert_array_equal(seen, matrix)


def test_separated_features_do_not_allocate_or_solve_the_full_assignment(monkeypatch):
    old = {f"old_{index}": hole(f"old_{index}", float(index)) for index in range(1056)}
    new = {f"new_{index}": hole(f"new_{index}", index + 0.001) for index in reversed(range(1056))}

    def forbidden(*args, **kwargs):
        pytest.fail("isolated pairs must not need a quadratic assignment")

    monkeypatch.setattr(matching, "linear_sum_assignment", forbidden)
    monkeypatch.setattr(matching, "_cost_matrix", forbidden)
    result = match(old, new, (0.0, 0.0, 0.0), 1.0)
    assert result.mapping == {f"old_{index}": f"new_{index}" for index in range(1056)}
    assert result.settled and not result.fresh


def test_matching_can_cancel_during_actual_preparation():
    checks = []
    signal = CancelSignal()

    def check():
        checks.append(None)
        if len(checks) == 3:
            signal.cancel()
        signal.raise_if_cancelled()

    old = {f"old_{index}": hole(f"old_{index}", float(index)) for index in range(30)}
    new = {f"new_{index}": hole(f"new_{index}", float(index)) for index in range(30)}
    with pytest.raises(OperationCancelled):
        match(old, new, (0.0, 0.0, 0.0), 1.0, check_cancelled=check)
    assert len(checks) == 3


@pytest.mark.parametrize(
    "before,after,same_result",
    [
        ([0, 1, 1, 1], [0, 0, 1], False),
        ([0.032, -0.04], [0, 0.096], False),
        ([0, 1, 2], [0, 3], True),
        ([0, 1, 2], [3, 4], True),
        ([0, 1], [0, 1, 2], True),
        ([0, 0], [0, 0], True),
    ],
)
def test_global_solver_ties_and_rectangular_order_remain_identical(before, after, same_result):
    old = {f"old_{index}": hole(f"old_{index}", x) for index, x in enumerate(before)}
    new = {f"new_{index}": hole(f"new_{index}", x) for index, x in enumerate(after)}
    assert_original_assignment(old, new)
    if same_result:
        assert match(old, new, (0, 0, 0), 1.0) == complete_reference(old, new)


def test_spatial_boundary_keeps_a_pair_accepted_by_the_original_cost():
    first = hole("old")
    second = replace(
        hole("new"), params={**first.params, "centre": (0.04800000000000001, 0.064, 0.0)}
    )
    old, new = {first.id: first}, {second.id: second}
    assert complete_reference(old, new).mapping == {"old": "new"}
    assert match(old, new, (0.0, 0.0, 0.0), 1.0) == complete_reference(old, new)


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"centre": (0.08, 0.0, 0.0)}, 1.0),
        ({"diameter": 8.0}, 0.5 / 0.15),
        ({"axis": (0.0, 0.0, -1.0)}, 0.0),
    ],
)
def test_independent_analytic_cost_components(changes, expected):
    first = hole("old")
    second = replace(hole("new"), params={**first.params, **changes})
    assert cost(first, second, (0, 0, 0), (0, 0, 0), 1.0) == pytest.approx(expected)


def test_opposite_surface_normals_remain_directed():
    first = Feature("old", "face", "detected", {"normal": (0.0, 0.0, 1.0), "area": 4.0})
    second = replace(first, id="new", params={**first.params, "normal": (0.0, 0.0, -1.0)})
    assert cost(first, second, (0, 0, 0), (0, 0, 0), 1.0) == pytest.approx(2.0 / 0.3)


@pytest.mark.parametrize("transpose", [False, True])
def test_connected_raster_with_distinct_minima_needs_no_global_matrix(monkeypatch, transpose):
    original = {f"old_{index}": hole(f"old_{index}", index * 0.03) for index in range(1056)}
    changed = {
        f"new_{index}": hole(f"new_{index}", index * 0.03) for index in reversed(range(1056))
    }
    changed["extra"] = hole("extra", 100.0)
    old, new = (changed, original) if transpose else (original, changed)
    expected = complete_reference(old, new)
    original_full = matching.np.full

    def bounded(shape, *args, **kwargs):
        assert shape != (len(old), len(new)), (
            "a certified raster must never allocate the global matrix"
        )
        return original_full(shape, *args, **kwargs)

    def forbidden(*args, **kwargs):
        pytest.fail("strict distinct minima do not need the global solver")

    monkeypatch.setattr(matching.np, "full", bounded)
    monkeypatch.setattr(matching, "linear_sum_assignment", forbidden)
    assert match(old, new, (0, 0, 0), 1.0) == expected


def test_unique_selected_partner_can_still_have_a_real_ambiguity(monkeypatch):
    old = {"old": hole("old")}
    new = {"nearest": hole("nearest"), "rival": hole("rival", 0.001)}
    expected = complete_reference(old, new)

    def forbidden(*args, **kwargs):
        pytest.fail("the assignment is certified, its rival is a separate result")

    monkeypatch.setattr(matching, "linear_sum_assignment", forbidden)
    assert match(old, new, (0, 0, 0), 1.0) == expected
    assert expected.ambiguous == {"old": ("nearest", "rival")}
    assert expected.fresh == ("nearest", "rival")


@pytest.mark.parametrize("transpose", [False, True])
def test_distant_global_context_is_retained_for_true_ties(monkeypatch, transpose):
    old = {f"old_{index}": hole(f"old_{index}", x) for index, x in enumerate([0, 1, 1, 1])}
    new = {f"new_{index}": hole(f"new_{index}", x) for index, x in enumerate([0, 0, 1])}
    if transpose:
        old, new = new, old
    expected_matrix, expected_rows, expected_columns = complete_reference(
        old, new, assignment_only=True
    )
    observed = []
    original = matching.linear_sum_assignment

    def captured(matrix):
        observed.append(matrix.shape)
        np.testing.assert_array_equal(matrix, expected_matrix)
        rows, columns = original(matrix)
        np.testing.assert_array_equal(rows, expected_rows)
        np.testing.assert_array_equal(columns, expected_columns)
        return rows, columns

    monkeypatch.setattr(matching, "linear_sum_assignment", captured)
    result = match(old, new, (0, 0, 0), 1.0)
    assert not result.mapping and not result.orphaned
    assert {name: set(candidates) for name, candidates in result.ambiguous.items()} == {
        name: {
            target
            for target, other in new.items()
            if feature.params["centre"] == other.params["centre"]
        }
        for name, feature in old.items()
    }
    assert observed == [(len(old), len(new))]


@pytest.mark.parametrize("seed", range(8))
def test_selective_pairs_preserve_independent_full_formula_and_solver(seed):
    random = np.random.default_rng(seed)
    old, new = {}, {}
    for target, prefix, count in ((old, "old", 19), (new, "new", 14 + seed)):
        for index in range(count):
            position = random.integers(-3, 4, size=3) * 0.015
            feature = hole(f"{prefix}_{index}")
            params = {
                **feature.params,
                "centre": tuple(position),
                "diameter": float(random.choice([4.0, 4.04, 4.1])),
                "axis": (0.0, 0.0, float(random.choice([-1.0, 1.0]))),
            }
            target[feature.id] = replace(feature, params=params)
    assert_original_assignment(old, new)


@pytest.mark.parametrize("axis", range(3))
def test_nextafter_boundary_and_translated_frames_keep_all_original_candidates(axis):
    first = hole("old")
    for direction in ((1.0, 0.0, 0.0), (0.6, 0.8, 0.0), (1.0, 1.0, 1.0), (2.0, 3.0, 7.0)):
        point = np.asarray(direction) * (0.08 / np.linalg.norm(direction))
        for steps in range(-4, 5):
            position = point.copy()
            for _ in range(abs(steps)):
                position[axis] = np.nextafter(position[axis], np.inf if steps > 0 else -np.inf)
            second = replace(hole("new"), params={**first.params, "centre": tuple(position)})
            old, new = {first.id: first}, {second.id: second}
            assert match(old, new, (0, 0, 0), 1.0) == complete_reference(old, new)
            moved = replace(
                second, params={**second.params, "centre": tuple(np.add(position, (17, -4, 9)))}
            )
            new = {moved.id: moved}
            assert match(old, new, (17, -4, 9), 1.0, old_centre=(0, 0, 0)) == complete_reference(
                old, new, (17, -4, 9), 1.0, old_centre=(0, 0, 0)
            )


@pytest.mark.parametrize("stage", ["query", "pairs", "solver"])
def test_actual_search_pairwork_and_solver_propagate_cancellation(monkeypatch, stage):
    old = {"old": hole("old"), "other": hole("other")}
    new = {"new": hole("new"), "duplicate": hole("duplicate")}
    signal = CancelSignal()
    observed = []
    if stage == "query":
        original = matching.cKDTree

        class CancellingTree:
            def __init__(self, *args):
                self.tree = original(*args)

            def query_ball_point(self, *args, **kwargs):
                result = self.tree.query_ball_point(*args, **kwargs)
                observed.append(stage)
                signal.cancel()
                return result

        monkeypatch.setattr(matching, "cKDTree", CancellingTree)
    else:
        name = "_vector_costs" if stage == "pairs" else "linear_sum_assignment"
        original = getattr(matching, name)

        def cancelled(*args, **kwargs):
            result = original(*args, **kwargs)
            observed.append(stage)
            signal.cancel()
            return result

        monkeypatch.setattr(matching, name, cancelled)
    with pytest.raises(OperationCancelled):
        match(old, new, (0, 0, 0), 1.0, check_cancelled=signal.raise_if_cancelled)
    assert observed == [stage]


def test_saved_answer_can_cancel_during_real_candidate_comparison(monkeypatch):
    old = hole("old")
    new = {"first": hole("first"), "second": hole("second", 0.01)}
    saved = matching.fingerprint(old, (0, 0, 0), 1.0)
    signal = CancelSignal()
    original = matching._vector_costs
    observed = []

    def cancelled(*args, **kwargs):
        result = original(*args, **kwargs)
        observed.append(result)
        signal.cancel()
        return result

    monkeypatch.setattr(matching, "_vector_costs", cancelled)
    with pytest.raises(OperationCancelled):
        matching.resolve(
            saved, tuple(new), new, (0, 0, 0), 1.0, check_cancelled=signal.raise_if_cancelled
        )
    assert len(observed) == 1


def test_scalar_cost_keeps_its_original_norm_reduction():
    random = np.random.default_rng(1404)
    origin = hole("old")
    for _ in range(64):
        position = tuple(random.uniform(-0.08, 0.08, size=3))
        candidate = replace(hole("new"), params={**origin.params, "centre": position})
        expected = float(np.linalg.norm(np.asarray(position))) / 0.08
        np.testing.assert_array_equal(cost(origin, candidate, (0, 0, 0), (0, 0, 0), 1.0), expected)


@pytest.mark.parametrize("transpose", [False, True])
def test_strict_minima_are_combined_across_all_candidate_blocks(monkeypatch, transpose):
    old = {"left": hole("left"), "right": hole("right", 0.06)}
    new = {f"middle_{index}": hole(f"middle_{index}", 0.03) for index in range(300)}
    new.update({"left_new": hole("left_new"), "right_new": hole("right_new", 0.06)})
    if transpose:
        old, new = new, old
    expected = complete_reference(old, new)

    def forbidden(*args, **kwargs):
        pytest.fail("later strict minima must retain the certificate")

    monkeypatch.setattr(matching, "linear_sum_assignment", forbidden)
    assert match(old, new, (0, 0, 0), 1.0) == expected


def test_equal_best_candidates_across_blocks_keep_the_global_tie(monkeypatch):
    old = {"old": hole("old")}
    new = {"first": hole("first")}
    new.update({f"middle_{index}": hole(f"middle_{index}", 0.03) for index in range(300)})
    new["last"] = hole("last")
    expected = complete_reference(old, new)
    observed = []
    original = matching.linear_sum_assignment

    def captured(matrix):
        observed.append(matrix.shape)
        return original(matrix)

    monkeypatch.setattr(matching, "linear_sum_assignment", captured)
    assert match(old, new, (0, 0, 0), 1.0) == expected
    assert observed == [(1, 302)]


def test_nonfinite_normalised_position_keeps_the_original_failure():
    old = {"old": hole("old", float("nan"))}
    new = {"new": hole("new")}
    with pytest.raises(ValueError, match="invalid numeric"):
        match(old, new, (0, 0, 0), 1.0)
    with pytest.raises(ValueError, match="invalid numeric"):
        complete_reference(old, new)
