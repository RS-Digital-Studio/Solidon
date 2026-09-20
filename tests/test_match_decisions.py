"""Eine ganze Zuordnungswahl gilt unabhängig von Namen und Körpernachbarn."""

from copy import deepcopy
from dataclasses import replace

import pytest

from app.core.errors import AmbiguityError, OperationCancelled
from app.core.perceive.match_decisions import (
    conflict_groups,
    group_fingerprint,
    mapping_with_decisions,
    resolve_group,
)
from app.core.perceive.match_records import group_key
from app.core.perceive.matching import MatchResult
from app.core.scene import CancelSignal
from app.core.types import Feature


def candidates():
    """Zwei unterscheidbare Nachfolger um dieselbe bisherige Mittellage."""
    return {
        name: Feature(
            name,
            "hole",
            "detected",
            {
                "centre": (x, 0.0, 0.0),
                "axis": (0.0, 0.0, 1.0),
                "diameter": 4.0,
            },
        )
        for name, x in (("candidate_A", -0.25), ("candidate_B", 0.25))
    }


def saved_choice():
    found = candidates()
    claims = {"before_1": tuple(found), "before_2": tuple(found)}
    decisions = {"before_1": "candidate_B", "before_2": None}
    record = group_fingerprint("body", claims, decisions, found, (0, 0, 0), 10.0)
    return found, claims, decisions, record


def test_transitive_claims_form_one_group_without_changing_the_match():
    result = MatchResult(
        mapping={"fixed": "fixed_now"},
        ambiguous={"third": ("y", "z"), "first": ("x",), "second": ("x", "y"), "other": ("w",)},
    )
    before = deepcopy(result)
    assert conflict_groups(result) == (
        {"first": ("x",), "second": ("x", "y"), "third": ("y", "z")},
        {"other": ("w",)},
    )
    assert result == before


def test_a_partial_claim_graph_cannot_release_one_competing_owner():
    """Eine vollständige Entscheidung über unvollständige Ansprüche genügt nicht."""
    result = MatchResult(ambiguous={"a": ("x",), "b": ("x",)})
    before = deepcopy(result)
    with pytest.raises(AmbiguityError):
        mapping_with_decisions(result, {"a": ("x",)}, {"a": "x"})
    assert result == before


def test_an_unselected_group_target_cannot_belong_to_an_outside_owner():
    found, claims, _decisions, saved = saved_choice()
    assert (
        resolve_group(
            saved, "body", claims, found, (0, 0, 0), 10.0, reserved_targets={"candidate_A"}
        )
        is None
    )


def test_an_unselected_claim_cannot_overlap_the_fixed_mapping():
    found, claims, decisions, _saved = saved_choice()
    result = MatchResult(mapping={"fixed": next(iter(found))}, ambiguous=dict(claims))
    before = deepcopy(result)
    with pytest.raises(AmbiguityError):
        mapping_with_decisions(result, claims, decisions)
    assert result == before


def test_whole_choice_survives_new_numbers_and_preserves_noncontinuation():
    found, claims, decisions, saved = saved_choice()
    before = deepcopy(saved)
    renamed = {
        "now_9": replace(found["candidate_B"], id="now_9"),
        "now_3": replace(found["candidate_A"], id="now_3"),
    }
    renamed_claims = {name: tuple(renamed) for name in claims}
    assert resolve_group(saved, "body", renamed_claims, renamed, (0, 0, 0), 10.0) == {
        "before_1": "now_9",
        "before_2": None,
    }
    assert saved == before
    assert saved["candidates"][0]["fingerprint"]["diameter"] == pytest.approx(4.0)
    assert mapping_with_decisions(MatchResult(ambiguous=dict(claims)), claims, decisions) == {
        "before_1": "candidate_B"
    }


@pytest.mark.parametrize(
    "change", ["object", "old_member", "candidate", "claim", "occupied", "duplicate_choice"]
)
def test_any_changed_group_context_reopens_the_whole_choice(change):
    found, claims, _decisions, saved = saved_choice()
    object_id, reserved = "body", frozenset()
    if change == "object":
        object_id = "different_body"
    elif change == "old_member":
        claims["before_3"] = tuple(found)
    elif change == "candidate":
        found["extra"] = replace(
            found["candidate_B"],
            id="extra",
            params={**found["candidate_B"].params, "centre": (0.75, 0.0, 0.0)},
        )
        claims["before_1"] = tuple(found)
    elif change == "claim":
        claims["before_2"] = ("candidate_A",)
    elif change == "occupied":
        reserved = frozenset({"candidate_B"})
    else:
        saved["decisions"]["before_2"] = dict(saved["decisions"]["before_1"])
    assert resolve_group(saved, object_id, claims, found, (0, 0, 0), 10.0, reserved) is None


def test_indistinguishable_new_geometry_is_not_restored_by_table_order():
    found, claims, _decisions, saved = saved_choice()
    found["candidate_A"] = replace(found["candidate_B"], id="candidate_A")
    assert resolve_group(saved, "body", claims, found, (0, 0, 0), 10.0) is None


def test_an_explicit_choice_to_carry_nothing_is_still_a_complete_answer():
    found, claims, _decisions, _saved = saved_choice()
    choices = dict.fromkeys(claims)
    saved = group_fingerprint("body", claims, choices, found, (0, 0, 0), 10.0)
    assert resolve_group(saved, "body", claims, found, (0, 0, 0), 10.0) == choices


@pytest.mark.parametrize("choices", [{"a": "x", "b": "x"}, {"a": "x"}, {"a": "unknown", "b": None}])
def test_invalid_decisions_never_partly_modify_the_existing_mapping(choices):
    result = MatchResult(mapping={"fixed": "fixed_now"}, ambiguous={"a": ("x",), "b": ("x",)})
    before = deepcopy(result)
    with pytest.raises(AmbiguityError):
        mapping_with_decisions(result, result.ambiguous, choices)
    assert result == before


def test_a_new_decision_cannot_claim_an_already_fixed_target():
    result = MatchResult(mapping={"fixed": "x"}, ambiguous={"a": ("x",)})
    with pytest.raises(AmbiguityError):
        mapping_with_decisions(result, result.ambiguous, {"a": "x"})
    assert result.mapping == {"fixed": "x"}


def test_cancelling_restore_leaves_saved_answers_and_features_untouched():
    found, claims, _decisions, saved = saved_choice()
    before = deepcopy((found, claims, saved))
    signal = CancelSignal()
    checks = []

    def cancel():
        checks.append(None)
        if len(checks) == 5:
            signal.cancel()
        signal.raise_if_cancelled()

    with pytest.raises(OperationCancelled):
        resolve_group(saved, "body", claims, found, (0, 0, 0), 10.0, check_cancelled=cancel)
    assert len(checks) == 5
    assert (found, claims, saved) == before


def test_object_qualification_and_escaped_names_prevent_group_collisions():
    assert group_key('body",["a', ["b"]) != group_key("body", ['a",["b'])
    assert group_key("body_1", ["hole_1"]) != group_key("body_2", ["hole_1"])
    assert group_key("body", ["b", "a"]) == group_key("body", ["a", "b"])
