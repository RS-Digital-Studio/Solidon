"""Every exception carries at least one suggested action (Bauplan §33.1, §2.7).

An error that ends with "failed" is unfinished. The check walks the whole
hierarchy, so a new exception class cannot slip through without one.
"""

from __future__ import annotations

import pytest

from app.core import errors
from app.core.errors import (
    AmbiguityError,
    AppError,
    BooleanFailedError,
    GeometryError,
    InternalError,
    UnitUnknownError,
    UserError,
    ValidationError,
)


def all_error_classes() -> list[type[AppError]]:
    found: list[type[AppError]] = []
    stack = [AppError]
    while stack:
        current = stack.pop()
        found.append(current)
        stack.extend(current.__subclasses__())
    return found


@pytest.mark.parametrize("error_class", all_error_classes(), ids=lambda cls: cls.__name__)
def test_every_error_can_be_raised_bare(error_class: type[AppError]) -> None:
    error = error_class()
    assert str(error.title), "an error needs a title saying what did not work"
    assert error.suggestions, "an error without a suggestion is unfinished"


@pytest.mark.parametrize("error_class", all_error_classes(), ids=lambda cls: cls.__name__)
def test_every_error_serialises(error_class: type[AppError]) -> None:
    data = error_class().as_dict()
    assert data["type"] == error_class.__name__
    assert data["suggestions"]


def test_hierarchy_matches_the_plan() -> None:
    assert issubclass(UserError, AppError)
    assert issubclass(ValidationError, UserError)
    assert issubclass(AmbiguityError, UserError)
    assert issubclass(UnitUnknownError, UserError)
    assert issubclass(GeometryError, AppError)
    assert issubclass(errors.NotManifoldError, GeometryError)
    assert issubclass(BooleanFailedError, GeometryError)
    assert issubclass(errors.OutOfBuildVolume, GeometryError)
    assert issubclass(errors.ExternalToolError, AppError)
    assert issubclass(InternalError, AppError)


def test_a_programming_error_is_not_a_user_error() -> None:
    assert not issubclass(InternalError, UserError)
    assert not issubclass(ValidationError, InternalError)


def test_ambiguity_offers_the_candidates() -> None:
    error = AmbiguityError(candidates=("hole_3", "hole_4"))
    ids = [action.id for action in error.suggestions]
    assert "choose:hole_3" in ids
    assert "choose:hole_4" in ids


def test_unit_question_offers_the_units() -> None:
    error = UnitUnknownError()
    ids = [action.id for action in error.suggestions]
    assert ids[:3] == ["unit:mm", "unit:cm", "unit:in"]


def test_boolean_failure_keeps_stages_and_seed() -> None:
    error = BooleanFailedError(attempted=("direct", "welded"), seed=20260727)
    assert error.attempted == ("direct", "welded")
    assert error.as_dict()["values"]["seed"] == 20260727


def test_cancelling_is_not_an_error() -> None:
    assert not issubclass(errors.OperationCancelled, AppError)
