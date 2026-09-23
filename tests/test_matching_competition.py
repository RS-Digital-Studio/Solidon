"""Konkurrierende alte Identitäten bleiben auch bei globalen Alternativen offen."""

from __future__ import annotations

from dataclasses import replace
from fractions import Fraction
from itertools import permutations

import numpy as np
import pytest

from app.core.errors import AppError, OperationCancelled
from app.core.perceive import matching
from app.core.scene import CancelSignal
from app.core.types import Feature


def holes(positions, prefix):
    return {
        f"{prefix}_{index}": Feature(
            f"{prefix}_{index}",
            "hole",
            "detected",
            {"centre": (position, 0.0, 0.0), "axis": (0.0, 0.0, 1.0), "diameter": 4.0},
        )
        for index, position in enumerate(positions)
    }


@pytest.mark.parametrize("placement", ["only_candidate", "invalid_first", "invalid_last"])
@pytest.mark.parametrize(
    "change",
    [
        {"centre": (float("nan"), 0.0, 0.0)},
        {"centre": (float("inf"), 0.0, 0.0)},
        {"centre": 0.0},
        {"centre": (0.0, 0.0)},
        {"centre": None},
        {"axis": (0.0, float("nan"), 1.0)},
        {"axis": (0.0, float("inf"), 1.0)},
        {"axis": (0.0, 1.0)},
        {"diameter": float("nan")},
        {"diameter": float("inf")},
        {"centre": (1e200, 0.0, 0.0)},
    ],
    ids=[
        "nan_position",
        "inf_position",
        "scalar_position",
        "short_position",
        "missing_position",
        "nan_axis",
        "inf_axis",
        "short_axis",
        "nan_size",
        "inf_size",
        "overflowing_cost",
    ],
)
def test_saved_answer_never_ignores_an_incomparable_current_candidate(change, placement):
    """Auch ein ungültiger Nichtgewinner kann die nötige Eindeutigkeit nicht belegen."""
    other = placement != "only_candidate"
    detected = holes([0.0, 0.5] if other else [0.0], "new")
    broken_id = "new_1" if other else "new_0"
    params = {**detected[broken_id].params, **change}
    if params["centre"] is None:
        del params["centre"]
    detected[broken_id] = replace(detected[broken_id], params=params)
    if placement == "invalid_first":
        detected = dict(reversed(detected.items()))
    saved = {
        "kind": "hole",
        "relative": [0.0, 0.0, 0.0],
        "axis": [0.0, 0.0, 1.0],
        "diameter": 4.0,
        "directional": False,
    }
    with np.errstate(over="ignore", invalid="ignore"):
        assert matching.resolve(saved, tuple(detected), detected, (0, 0, 0), 1.0) is None


@pytest.mark.parametrize(
    "centre,diagonal",
    [
        ((float("nan"), 0, 0), 1.0),
        ((float("inf"), 0, 0), 1.0),
        ((0, 0, 0), float("inf")),
        ((0, 0, 0), float("nan")),
        (0.0, 1.0),
        ((0, 0), 1.0),
    ],
)
def test_saved_answer_requires_a_finite_three_dimensional_current_frame(centre, diagonal):
    """Ohne endlichen Bezugsrahmen des heutigen Körpers gibt es keine gespeicherte Antwort."""
    detected = holes([0.0], "new")
    saved = {"kind": "hole", "relative": [0, 0, 0], "axis": [0, 0, 1], "diameter": 4.0}
    with np.errstate(over="ignore", invalid="ignore"):
        assert matching.resolve(saved, tuple(detected), detected, centre, diagonal) is None


@pytest.mark.parametrize(
    "change",
    [
        {"relative": [float("nan"), 0, 0]},
        {"relative": [float("inf"), 0, 0]},
        {"relative": [0, 0]},
        {"relative": None},
        {"axis": [0, 0]},
        {"axis": [float("nan"), 0, 1]},
        {"diameter": float("nan")},
    ],
)
def test_saved_answer_requires_its_actual_finite_reference(change):
    """Eine gespeicherte Antwort mit unvollständigem oder unendlichem Bezug löst nichts auf."""
    detected = holes([0.0], "new")
    saved = {"kind": "hole", "relative": [0, 0, 0], "axis": [0, 0, 1], "diameter": 4.0, **change}
    if saved["relative"] is None:
        del saved["relative"]
    with np.errstate(over="ignore", invalid="ignore"):
        assert matching.resolve(saved, tuple(detected), detected, (0, 0, 0), 1.0) is None


def test_saved_answer_keeps_legacy_optional_fields_and_scalar_cost_semantics():
    """Eine historische Antwort ohne Richtungs-/Maßfelder bleibt bei passender Geometrie lesbar."""
    feature = Feature("new", "void", "detected", {"centre": (0.0, 0.0, 0.0)})
    assert (
        matching.resolve(
            {"kind": "void", "relative": [0, 0, 0]}, ("new",), {"new": feature}, (0, 0, 0), 1.0
        )
        == "new"
    )


def test_three_equal_ancestors_do_not_publish_an_arbitrary_owner():
    """Drei alte Bohrungen an derselben Stelle und eine neue: keine bekommt den Namen.

    Die Zuordnung veröffentlicht keine Wahl, die sie nur getroffen hat, weil eine
    Reihenfolge sie zuerst nannte; alle drei bleiben mehrdeutig, und der Kunde
    entscheidet.
    """
    old = holes([0.0, 1.0, 1.0, 1.0], "old")
    new = holes([0.0, 0.0, 1.0], "new")
    result = matching.match(old, new, (0.0, 0.0, 0.0), 1.0)

    assert not result.mapping
    assert not result.orphaned
    assert {name: set(candidates) for name, candidates in result.ambiguous.items()} == {
        "old_0": {"new_0", "new_1"},
        "old_1": {"new_2"},
        "old_2": {"new_2"},
        "old_3": {"new_2"},
    }
    assert set(result.fresh) == set(new)


@pytest.mark.parametrize(
    "before,after,expected",
    [
        ([0.25, -0.25, 1.75], [0.0, 1.0], [{0, 1}, {0}, {1}]),
        ([0.125, 1.25, -0.5], [0.0, 0.5], [{0, 1}, {1}, {0}]),
        ([0.0, -0.5], [0.0, 0.5], [{0, 1}, {0, 1}]),
        ([0.0, 0.03125], [0.0, 0.03125], [{0, 1}, {0, 1}]),
    ],
    ids=["opened_owner", "alternating_without_seed", "isolated_minimum", "existing_floor"],
)
def test_exact_binary_counterexamples_keep_the_whole_competition(
    monkeypatch, before, after, expected
):
    """Einheitsmaßstab hält die analytischen Tabellen exakt binär darstellbar.

    Im zweiten Fall bleibt c→y mit Kosten 1 ausgeschlossen: Die globale
    y-Grenze ist 0,75, die lokale Besitzergrenze 0,9875. Offen sind trotzdem
    alle drei alten Ansprüche, denn c→x ermöglicht den alternierenden Weg.
    """
    monkeypatch.setattr(matching, "POSITION_TOLERANCE", 1.0)
    old = holes(before, "old")
    new = holes(after, "new")
    for old_order in permutations(old):
        for new_order in permutations(new):
            result = matching.match(
                {name: old[name] for name in old_order},
                {name: new[name] for name in new_order},
                (0.0, 0.0, 0.0),
                1.0,
            )
            assert not result.mapping
            assert not result.orphaned
            assert {name: set(candidates) for name, candidates in result.ambiguous.items()} == {
                f"old_{index}": {f"new_{target}" for target in targets}
                for index, targets in enumerate(expected)
            }


@pytest.mark.parametrize("function", [matching.inherit_originators, matching.apply_mapping])
def test_duplicate_targets_cannot_mix_one_ancestors_name_with_anothers_origin(function):
    """Zwei alte Merkmale auf ein neues gemappt ist ein Widerspruch, kein Erbe.

    Weder Name noch Herkunft dürfen dabei aus verschiedenen Vorfahren zusammengesetzt
    werden; beide Anwender der Zuordnung lehnen mit Vorschlag ab und lassen das neue
    Merkmal unberührt.
    """
    old = holes([0.0, 0.0], "old")
    old = {
        name: replace(feature, created_by=index + 1)
        for index, (name, feature) in enumerate(old.items())
    }
    new = holes([0.0], "new")
    result = matching.MatchResult(mapping={"old_0": "new_0", "old_1": "new_0"})

    with pytest.raises(AppError) as caught:
        function(new, result, previous=old)
    assert caught.value.suggestions
    assert new["new_0"].created_by is None
    assert new["new_0"].id == "new_0"


def assignment_for(matrix):
    from scipy.optimize import linear_sum_assignment

    rows, columns = linear_sum_assignment(matrix)
    return matching._Assignment(
        rows, columns, matrix[rows, columns], matrix, lambda: matching._matrix_pairs(matrix, None)
    )


def test_penalty_sum_cannot_erase_a_real_binary_cost_difference():
    """Eine Strafe von der Größe P darf einen Unterschied von 2⁻⁶⁰ nicht verschlucken.

    Die Hüllgrenzen je Zeile werden aus exakten Binärzahlen gebildet; die Summe der
    Zuteilung minus die Zeilenminima ist genau null, nicht „ungefähr".
    """
    penalty = matching.KIND_PENALTY
    small = 2.0**-60
    matrix = np.array([[0.0, small, penalty], [0.0, penalty, penalty], [penalty] * 3])
    assigned = assignment_for(matrix)
    limits = matching._hull_limits(matrix, assigned, None)
    # Gewählt: a→y (2^-60), b→x (0), Strafpaar (P). Zeilenminima: 0, 0, P.
    np.testing.assert_array_equal(limits, [small, small, penalty])
    assert float(np.sum(assigned.values) - np.sum(np.min(matrix, axis=1))) == 0.0


def test_hull_rounds_each_exact_binary_bound_down():
    """Die Hüllgrenze einer Zeile ist die größte Gleitkommazahl unter der exakten Summe,
    nie darüber."""
    matrix = np.array([[0.1, 0.3], [0.0, 0.2]])
    # Eine zulässige obere Grenze genügt; die Paarung muss hierfür nicht optimal sein.
    assigned = matching._Assignment(
        np.array([0, 1]), np.array([0, 1]), np.array([0.1, 0.2]), matrix, lambda: iter(())
    )
    limits = matching._hull_limits(matrix, assigned, None)
    exact = Fraction(0.1) + Fraction(0.2)
    assert Fraction(float(limits[0])) <= exact
    assert Fraction(float(np.nextafter(limits[0], np.inf))) > exact
    assert limits[0] < float(exact)


@pytest.mark.parametrize(
    "values",
    [
        [[0.0, 0.5], [0.5, 1.0]],
        [[0.25, 0.75], [0.25, 1e6], [1e6, 0.75]],
        [[0.0, 0.0], [0.0, 0.0], [1e6, 1e6]],
        [[0.0, 0.5, 1e6], [1e6, 0.5, 1e6], [1e6, 1e6, 1e6]],
        [[0.0, 1e6, 1e6], [0.0, 1e6, 1e6], [1e6, 0.0, 1e6]],
    ],
)
@pytest.mark.parametrize("transpose", [False, True])
def test_alternating_graph_matches_exhaustive_maximum_cardinality_support(values, transpose):
    """Alle kleinen Komplettierungen aufzählen, unabhängig von Reichweite und SCC."""
    matrix = np.asarray(values, dtype=float)
    if transpose:
        matrix = matrix.T
    assigned = assignment_for(matrix)
    oriented = matrix.T if matrix.shape[0] > matrix.shape[1] else matrix
    minima = [min(Fraction(float(value)) for value in row) for row in oriented]
    gap = sum(Fraction(float(value)) for value in assigned.values) - sum(minima)
    allowed = {
        (row, column)
        for row in range(matrix.shape[0])
        for column in range(matrix.shape[1])
        if matrix[row, column] <= 1.0
        and Fraction(float(matrix[row, column]))
        <= minima[column if matrix.shape[0] > matrix.shape[1] else row] + gap
    }
    maximum = -1
    expected = set()
    for columns in permutations(range(oriented.shape[1]), oriented.shape[0]):
        pairs = {
            (column, row) if matrix.shape[0] > matrix.shape[1] else (row, column)
            for row, column in enumerate(columns)
        } & allowed
        if len(pairs) > maximum:
            maximum, expected = len(pairs), set(pairs)
        elif len(pairs) == maximum:
            expected.update(pairs)
    partners = np.full(len(matrix), -1, dtype=np.intp)
    accepted = assigned.values <= 1.0
    partners[assigned.rows[accepted]] = assigned.columns[accepted]
    actual = matching._global_support(assigned, partners, matrix.shape[1], None)
    assert {(row, column) for row, columns in enumerate(actual) for column in columns} == expected


def test_hull_neighbour_without_alternating_path_does_not_open_fixed_identity():
    """Eine Hall-Lücke an anderer Stelle öffnet keine feste Identität.

    Zwei zusätzliche alte Merkmale, die um dasselbe neue konkurrieren, vergrößern
    die Menge der offenen Ansprüche — aber nur ihre eigene; die feste Paarung
    ``0→0``, ``1→1`` ohne alternierenden Pfad dorthin bleibt fest.
    """
    matrix = np.array([[0.0, 0.5, 1e6], [1e6, 0.5, 1e6], [1e6, 1e6, 1e6]])
    # Eine gesonderte Hall-Lücke vergrößert U-L, ohne den festen Teil zu verbinden.
    combined = np.full((5, 5), 1e6)
    combined[:3, :3] = matrix
    combined[3:, 3] = 0.0
    assigned = assignment_for(combined)
    # Die konkrete globale Paarung kann einen anderen alten Hall-Besitzer wählen.
    partners = np.full(5, -1, dtype=np.intp)
    accepted = assigned.values <= 1.0
    partners[assigned.rows[accepted]] = assigned.columns[accepted]
    support = matching._global_support(assigned, partners, 5, None)
    assert support[0] == [0]
    assert support[1] == [1]
    _, claims = matching._open_claims(assigned, 5, 5, None)
    assert set(claims) == {3, 4}


def test_fast_certificate_still_checks_unassigned_nearby_old_claims():
    """Das schnelle Zertifikat übersieht keinen nahen alten Anspruch ohne Zuteilung.

    Zwei alte Bohrungen zwei Tausendstel auseinander und eine neue: keine Zuordnung
    wird veröffentlicht, beide bleiben mehrdeutig auf dasselbe Ziel.
    """
    old = holes([0.0, 0.002], "old")
    new = holes([0.0], "new")
    result = matching.match(old, new, (0, 0, 0), 1.0)
    assert not result.mapping and not result.orphaned
    assert result.ambiguous == {"old_0": ("new_0",), "old_1": ("new_0",)}


def test_existing_row_rival_opens_its_previously_fixed_owner():
    """Ein Zeilenrivale, der schon in der Zuteilung stand, öffnet auch den bisher festen Besitzer
    seines Ziels.
    """
    old = holes([0.032, -0.04], "old")
    new = holes([0.0, 0.096], "new")
    # Die globale Zuteilung gibt a→y und b→x. Der bisherige Zeilenrivale a→x
    # öffnet auch b; x darf kein zugleich freigegebenes Außenziel bleiben.
    result = matching.match(old, new, (0, 0, 0), 1.0)
    assert not result.mapping and not result.orphaned
    assert {name: set(candidates) for name, candidates in result.ambiguous.items()} == {
        "old_0": {"new_0", "new_1"},
        "old_1": {"new_0"},
    }


def test_a_fixed_free_partner_is_not_opened_by_column_proximity_alone(monkeypatch):
    """a→y passt zur hohen Besitzergrenze von b, aber a besitzt sicher sein eigenes x."""
    monkeypatch.setattr(matching, "POSITION_TOLERANCE", 1.0)
    old = holes([0.0, 1.0625], "old")
    new = holes([0.0, 0.25], "new")
    result = matching.match(old, new, (0, 0, 0), 1.0)
    assert result.mapping == {"old_0": "new_0", "old_1": "new_1"}
    assert result.settled


@pytest.mark.parametrize("transpose", [False, True])
def test_every_exact_global_optimum_stays_available_without_fixed_external_claims(
    monkeypatch, transpose
):
    """Über 25 zufällige Kostenmatrizen: Veröffentlicht wird nur, was in **jedem**
    globalen Optimum steht, und erreichbar bleibt alles, was in **irgendeinem** steht.

    Die Optima werden erschöpfend über alle Permutationen mit exakten Brüchen
    bestimmt, nicht über den Löser, dessen Antwort geprüft wird. Zuordnung,
    Mehrdeutigkeit und Verwaisung sind dabei disjunkt und decken alle alten
    Merkmale ab.
    """
    random = np.random.default_rng(1405)
    for _ in range(25):
        matrix = random.choice([0.0, 0.125, 0.375, 1.0, 1e6], size=(4, 3))
        if transpose:
            matrix = matrix.T
        oriented = matrix.T if matrix.shape[0] > matrix.shape[1] else matrix
        best = None
        optima = []
        for columns in permutations(range(oriented.shape[1]), oriented.shape[0]):
            total = sum(
                Fraction(float(oriented[row, column])) for row, column in enumerate(columns)
            )
            pairs = {
                (column, row) if matrix.shape[0] > matrix.shape[1] else (row, column)
                for row, column in enumerate(columns)
                if oriented[row, column] <= 1.0
            }
            if best is None or total < best:
                best, optima = total, [pairs]
            elif total == best:
                optima.append(pairs)
        assigned = assignment_for(matrix)
        monkeypatch.setattr(matching, "_assignment", lambda *args, answer=assigned: answer)
        old = holes(list(range(len(matrix))), "old")
        new = holes(list(range(matrix.shape[1])), "new")
        result = matching.match(old, new, (0, 0, 0), 1.0)
        published = {
            (int(name.removeprefix("old_")), int(target.removeprefix("new_")))
            for name, target in result.mapping.items()
        }
        available = published | {
            (int(name.removeprefix("old_")), int(target.removeprefix("new_")))
            for name, candidates in result.ambiguous.items()
            for target in candidates
        }
        assert published <= set.intersection(*optima)
        assert set.union(*optima) <= available
        assert set(result.mapping.values()).isdisjoint(
            target for candidates in result.ambiguous.values() for target in candidates
        )
        assert set(result.mapping).isdisjoint(result.ambiguous)
        assert set(result.orphaned).isdisjoint(set(result.mapping) | set(result.ambiguous))
        assert set(old) == set(result.mapping) | set(result.ambiguous) | set(result.orphaned)


def test_nonmaximal_solver_answer_does_not_certify_fixed_identities():
    """Eine Löserantwort, die nicht maximal ist, zertifiziert keine feste Identität — sie wird mit
    Vorschlag abgewiesen.
    """
    matrix = np.array([[0.0, 0.5], [0.0, 1e6]])
    assigned = matching._Assignment(
        np.array([0, 1]),
        np.array([0, 1]),
        np.array([0.0, 1e6]),
        matrix,
        lambda: matching._matrix_pairs(matrix, None),
    )
    with pytest.raises(AppError) as caught:
        matching._global_support(assigned, np.array([0, -1]), 2, None)
    assert caught.value.suggestions


@pytest.mark.parametrize(
    "stage", ["_hull_limits", "_reachable", "_strong_components", "_close_claims"]
)
def test_cancellation_inside_hull_graph_and_closure_reaches_the_original_caller(monkeypatch, stage):
    """Ein Abbruch mitten in jeder der vier Stufen der Hüllrechnung erreicht den Aufrufer als
    ``OperationCancelled``.
    """
    old = holes([0.0, 0.0, 0.0], "old")
    new = holes([0.0, 0.0], "new")
    signal = CancelSignal()
    original = getattr(matching, stage)
    entered = []

    def instrumented(*args):
        caller_check = args[-1]
        counts = 0

        def checked():
            nonlocal counts
            counts += 1
            if counts == (len(old) + 2 if stage == "_close_claims" else 2):
                entered.append(stage)
                signal.cancel()
            caller_check()

        return original(*args[:-1], checked)

    monkeypatch.setattr(matching, stage, instrumented)
    with pytest.raises(OperationCancelled):
        matching.match(old, new, (0, 0, 0), 1.0, check_cancelled=signal.raise_if_cancelled)
    assert entered == [stage]
    assert all(feature.created_by is None for feature in (*old.values(), *new.values()))


def test_a_hall_deficit_elsewhere_does_not_open_a_clear_pair():
    """Eine Hall-Lücke unter den Kegeln öffnet keine Bohrung, die eindeutig bleibt (RM-024).

    Nachgestellt nach dem Halter mit Wabenmuster
    (``large-screwdriver-holder-with-honeycomb-pattern.stl``, *Dreiecke verringern*
    auf 5 000, eine Passung auf zwei Bohrungen): Die Bohrungspaare liegen 18 mm
    auseinander, jede alte kostet zu ihrer neuen 0,0 und zur Nachbarin 0,893. Zwei
    alte Kegel beanspruchen denselben neuen — eine echte Lücke, die gefragt
    werden muss. Ihre Strafe P ging aber in die **eine** Kostenhülle aller
    Merkmale ein, die Hülle ließ damit auch den Bohrungstausch zu, und der Kunde
    bekam vier Fragen „Welches Merkmal entspricht hole_1? hole_1 / hole_2"
    zu Bohrungen, die sich nicht bewegt hatten. Die Hülle gilt je
    Zusammenhangskomponente der angenommenen Paare: Jedes Optimum zahlt in jeder
    Komponente genau deren Optimum, denn Strafpaare kosten überall dasselbe.
    """
    old = holes([0.0, 18.0], "old")
    new = holes([0.0, 18.0], "new")
    cone = {"axis": (0.0, 0.0, 1.0), "diameter": 8.0}
    old |= {
        "old_cone_1": Feature(
            "old_cone_1", "cone", "detected", {**cone, "centre": (100.0, 0.0, 0.0)}
        ),
        "old_cone_2": Feature(
            "old_cone_2", "cone", "detected", {**cone, "centre": (102.0, 0.0, 0.0)}
        ),
    }
    new |= {
        "new_cone": Feature("new_cone", "cone", "detected", {**cone, "centre": (101.0, 0.0, 0.0)})
    }
    # Wie nach dem Verringern: mehr neue Merkmale als alte — dann ist die alte
    # Seite die vollständig zugeteilte, und die Strafe des leer ausgehenden
    # Kegels steht in ihrer Summe.
    new |= {
        f"new_face_{index}": Feature(
            f"new_face_{index}",
            "face",
            "detected",
            {"centre": (0.0, 50.0 + index, 0.0), "normal": (0.0, 0.0, 1.0), "area": 10.0},
        )
        for index in range(3)
    }

    result = matching.match(old, new, (0.0, 0.0, 0.0), 252.0)

    assert result.mapping == {"old_0": "new_0", "old_1": "new_1"}, result.ambiguous
    assert set(result.ambiguous) == {"old_cone_1", "old_cone_2"}
    assert all(candidates == ("new_cone",) for candidates in result.ambiguous.values())


@pytest.mark.parametrize("transpose", [False, True])
def test_component_hulls_keep_every_optimum_available_across_blocks(monkeypatch, transpose):
    """Die Hülle je Komponente verliert kein Optimum — auch zwischen getrennten Blöcken.

    Blockmatrizen aus zwei bis drei Gruppen angenommener Paare, eine davon mit
    Hall-Lücke: Veröffentlicht wird nur, was in **jedem** exakten Optimum
    steht, und erreichbar bleibt alles, was in **irgendeinem** steht. Die Optima
    zählt der Test selbst über alle Zuteilungen mit Brüchen, nicht über den Löser.
    """
    random = np.random.default_rng(2209)
    for _ in range(30):
        matrix = np.full((4, 6), 1e6)
        blocks = [
            (slice(0, 2), slice(0, 2)),
            (slice(2, 4), slice(2, 3)),
            (slice(2, 4), slice(3, 6)),
        ]
        for rows, columns in blocks[: random.integers(2, 4)]:
            shape = (rows.stop - rows.start, columns.stop - columns.start)
            matrix[rows, columns] = random.choice([0.0, 0.125, 0.5, 0.875, 1e6], size=shape)
        if transpose:
            matrix = matrix.T
        oriented = matrix.T if matrix.shape[0] > matrix.shape[1] else matrix
        best = None
        optima = []
        for columns in permutations(range(oriented.shape[1]), oriented.shape[0]):
            total = sum(
                Fraction(float(oriented[row, column])) for row, column in enumerate(columns)
            )
            pairs = {
                (column, row) if matrix.shape[0] > matrix.shape[1] else (row, column)
                for row, column in enumerate(columns)
                if oriented[row, column] <= 1.0
            }
            if best is None or total < best:
                best, optima = total, [pairs]
            elif total == best:
                optima.append(pairs)
        assigned = assignment_for(matrix)
        monkeypatch.setattr(matching, "_assignment", lambda *args, answer=assigned: answer)
        old = holes(list(range(len(matrix))), "old")
        new = holes(list(range(matrix.shape[1])), "new")
        result = matching.match(old, new, (0, 0, 0), 1.0)
        published = {
            (int(name.removeprefix("old_")), int(target.removeprefix("new_")))
            for name, target in result.mapping.items()
        }
        available = published | {
            (int(name.removeprefix("old_")), int(target.removeprefix("new_")))
            for name, candidates in result.ambiguous.items()
            for target in candidates
        }
        assert published <= set.intersection(*optima)
        assert set.union(*optima) <= available
