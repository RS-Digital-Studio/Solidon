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


def test_nonfinite_normalised_position_names_the_feature_and_offers_a_way_out():
    """Ein Merkmal ohne Zahl ist ein Programmfehler — mit Kennung und Vorschlag (Regel 17).

    Bis zum 21.09.2026 lief der Fall in den Vollvergleich, und scipy warf dort
    „matrix contains invalid numeric entries": ein Satz ohne Handlung.
    """
    from app.core.errors import InternalError

    old = {"old": hole("old", float("nan"))}
    new = {"new": hole("new")}
    with pytest.raises(InternalError) as caught:
        match(old, new, (0, 0, 0), 1.0)
    assert caught.value.suggestions, "jede Ausnahme trägt einen Handlungsvorschlag"
    assert caught.value.values["features"] == ["old"]
    with pytest.raises(InternalError) as caught:
        match(new, old, (0, 0, 0), 1.0)
    assert caught.value.values["features"] == ["old"], "auch auf der neuen Seite"


def _full_path_only(monkeypatch, old, new, centre=(0, 0, 0), diagonal=1.0, old_centre=None):
    """Dieselbe Frage ohne den Nahweg — der Vergleich für :func:`matching._near_assignment`."""
    with monkeypatch.context() as patched:
        patched.setattr(matching, "_near_assignment", lambda *args, **kwargs: None)
        matching.forget_matches()
        return match(old, new, centre, diagonal, old_centre)


def _near_cloud(random, count, spread, shift, flips, renamed, shuffled, twins):
    """Alte und neue Merkmale fast an derselben Stelle — mit Zwillingen und Nachbarn."""
    kinds = ("hole", "face", "sphere")
    # Jede Stelle des Rasters einmal: Zwillinge entstehen nur, wo sie gewollt sind.
    cells = random.choice(13**3, size=count, replace=False)
    old = {}
    for index in range(count):
        kind = kinds[index % 3]
        centre = (np.asarray(np.unravel_index(cells[index], (13, 13, 13))) - 6) * spread
        if twins and index % 7 == 0 and index:
            centre = np.asarray(old[f"old_{index - 1}"].params["centre"]) + random.choice(
                [0.0, 1e-9, 0.001, 0.0039, 0.004, 0.0041]
            )
        params = {"centre": tuple(float(value) for value in centre)}
        if kind == "hole":
            params |= {"axis": (0.0, 0.0, 1.0), "diameter": float(random.choice([4.0, 4.1]))}
        elif kind == "face":
            params |= {"normal": (0.0, 1.0, 0.0), "area": float(random.choice([9.0, 9.2]))}
        else:
            params |= {"diameter": 6.0}
        old[f"old_{index}"] = Feature(f"old_{index}", kind, "detected", params)
    new = {}
    for name, feature in old.items():
        moved = np.asarray(feature.params["centre"]) + shift * random.standard_normal(3)
        params = {**feature.params, "centre": tuple(float(value) for value in moved)}
        if flips and "axis" in params and random.random() < 0.5:
            params["axis"] = (0.0, 0.0, -1.0)
        target = f"new_{name}" if renamed else name
        new[target] = replace(feature, id=target, params=params)
    if shuffled:
        names = list(new)
        random.shuffle(names)
        new = {name: new[name] for name in names}
    return old, new


@pytest.mark.parametrize("seed", range(24))
def test_near_identical_sets_give_the_full_answer_bit_for_bit(monkeypatch, seed):
    """Der Nahweg antwortet wie der volle Weg — Zuordnung, Waisen, Mehrdeutige, Neue (RM-636).

    Gemischt: drei Arten, Zwillinge auf und knapp neben der Grenze der
    Mehrdeutigkeit, gekippte richtungslose Achsen, kleine Verschiebungen,
    neue Namen und vertauschte Reihenfolge.
    """
    random = np.random.default_rng(6362026 + seed)
    old, new = _near_cloud(
        random,
        count=int(random.integers(20, 160)),
        spread=float(random.choice([0.002, 0.01, 0.05])),
        shift=float(random.choice([0.0, 1e-15, 1e-6, 1e-4, 1e-3])),
        flips=bool(seed % 2),
        renamed=bool(seed % 3 == 0),
        shuffled=bool(seed % 4 == 1),
        twins=bool(seed % 5 != 0),
    )
    centre = (0.0, 0.0, 0.0) if seed % 2 else (3.0, -1.0, 2.0)
    engaged = []
    real = matching._near_assignment

    def watched(*args, **kwargs):
        answer = real(*args, **kwargs)
        engaged.append(answer is not None)
        return answer

    expected = _full_path_only(monkeypatch, old, new, centre, 1.0)
    monkeypatch.setattr(matching, "_near_assignment", watched)
    matching.forget_matches()
    found = match(old, new, centre, 1.0)
    assert found == expected
    assert found.mapping == expected.mapping and list(found.mapping) == list(expected.mapping)
    assert list(found.ambiguous.items()) == list(expected.ambiguous.items())
    assert found.orphaned == expected.orphaned and found.fresh == expected.fresh
    assert engaged, "Voraussetzung: der Zuordner fragt den Nahweg"
    if seed % 5 == 0:
        # Ohne Zwillinge trägt das Zertifikat: Der Nahweg antwortet selbst
        # (Review L3, M1) — nicht nur gefragt, auch genommen.
        assert any(engaged), "without twins the near way answers"


def test_the_near_way_carries_the_identity_and_the_small_moves():
    """Ohne Zwillinge nimmt der Nahweg gleiche und leicht verschobene Mengen ganz an."""
    random = np.random.default_rng(6360)
    taken = []
    real = matching._near_assignment
    for shift in (0.0, 1e-12, 1e-5):
        old, new = _near_cloud(random, 120, 0.05, shift, False, False, True, False)
        one = matching._vectors(list(old.values()), (0, 0, 0), 1.0, None)
        two = matching._vectors(list(new.values()), (0, 0, 0), 1.0, None)
        taken.append(real(list(old.values()), list(new.values()), one, two, None) is not None)
        assert match(old, new, (0, 0, 0), 1.0).mapping == {name: name for name in old}
    assert taken == [True, True, True]


@pytest.mark.parametrize("steps", range(-3, 4))
def test_a_rival_on_the_ambiguity_boundary_keeps_the_full_answer(monkeypatch, steps):
    """Ein Nachbar genau an der Grenze der Mehrdeutigkeit, ulp für ulp verschoben."""
    distance = 0.05 * 0.08
    for _ in range(abs(steps)):
        distance = float(np.nextafter(distance, np.inf if steps > 0 else -np.inf))
    old = {"a": hole("a"), "b": hole("b", distance), "c": hole("c", 0.5)}
    new = {"a": hole("a"), "b": hole("b", distance), "c": hole("c", 0.5)}
    expected = _full_path_only(monkeypatch, old, new)
    matching.forget_matches()
    assert match(old, new, (0, 0, 0), 1.0) == expected


def test_identical_twins_leave_the_near_way_for_the_full_one(monkeypatch):
    """Zwei deckungsgleiche Merkmale tragen kein Zertifikat — der volle Weg entscheidet."""
    old = {"a": hole("a"), "b": hole("b"), "c": hole("c", 0.3)}
    new = {"a": hole("a"), "b": hole("b"), "c": hole("c", 0.3)}
    one = matching._vectors(list(old.values()), (0, 0, 0), 1.0, None)
    two = matching._vectors(list(new.values()), (0, 0, 0), 1.0, None)
    assert matching._near_assignment(list(old.values()), list(new.values()), one, two, None) is None
    assert match(old, new, (0, 0, 0), 1.0) == _full_path_only(monkeypatch, old, new)


def _taken_and_answer(monkeypatch, old, new):
    """Die Antwort mit Nahweg und ob er sie gab."""
    taken = []
    real = matching._near_assignment

    def watched(*args, **kwargs):
        answer = real(*args, **kwargs)
        taken.append(answer is not None)
        return answer

    with monkeypatch.context() as patched:
        patched.setattr(matching, "_near_assignment", watched)
        matching.forget_matches()
        found = match(old, new, (0.0, 0.0, 0.0), 1.0)
    return any(taken), found


def test_the_near_search_keeps_its_rounding_reserve(monkeypatch):
    """Ein Rivale knapp über ``T·L``, der in Gleitkomma doch bis ``L`` kostet (Review L3, M1).

    Ohne die Reserve aus ``_query_radius`` fände die kleine Suche ihn nicht, und a, b würden
    still zugeordnet, wo der volle Weg fragt.
    """
    s = float.fromhex("0x1.693a61ba258d5p-9")
    d = float.fromhex("0x1.e7e95a4372182p-8")
    old = {"a": hole("a", 0.0), "b": hole("b", -d - s / 4.0)}
    new = {"a": hole("a", s), "b": hole("b", -d)}
    expected = _full_path_only(monkeypatch, old, new)
    taken, found = _taken_and_answer(monkeypatch, old, new)
    assert taken, "the near way answers this case"
    assert found == expected
    assert dict(found.ambiguous) == {"a": ("a", "b"), "b": ("b",)}
    assert not found.mapping


@pytest.mark.parametrize("spacing", [0.008, 0.01, 0.012])
def test_the_near_way_answers_with_the_partners_it_found(monkeypatch, spacing):
    """Vertauschte Kennungen in der Nähe: Partner sind die gefundenen, nicht die vorläufigen."""
    old = {"a": hole("a", 0.0), "b": hole("b", spacing), "c": hole("c", 0.3)}
    new = {"a": hole("a", spacing), "b": hole("b", 0.0), "c": hole("c", 0.3)}
    expected = _full_path_only(monkeypatch, old, new)
    taken, found = _taken_and_answer(monkeypatch, old, new)
    assert taken, "the near way answers this case"
    assert found == expected
    assert found.mapping == {"a": "b", "b": "a", "c": "c"}
