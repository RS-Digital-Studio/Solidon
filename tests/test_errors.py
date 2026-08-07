"""Jede Ausnahme trägt mindestens einen Handlungsvorschlag (Bauplan §33.1,
§2.7).

Ein Fehler, der mit „fehlgeschlagen" endet, ist unfertig. Die Prüfung läuft die
ganze Hierarchie ab — eine neue Ausnahmeklasse kann also nicht ohne einen
durchrutschen.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

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


def core_sources() -> list[Path]:
    return sorted((Path(__file__).resolve().parent.parent / "app" / "core").rglob("*.py"))


@pytest.mark.parametrize("path", core_sources(), ids=lambda entry: entry.name)
def test_no_error_text_carries_a_placeholder_nobody_fills(path: Path) -> None:
    """Ein ``{platzhalter}`` in einem Fehlertext bleibt wörtlich stehen.

    Anderswo ist er richtig: die Oberfläche setzt ihre Texte mit ``.format``
    zusammen, und ``tr("{grams} g").format(...)`` ist der übliche Weg. Einen
    Fehler formatiert dagegen niemand nach — ``show_details`` zeigt
    ``str(error.detail)``, wie es ist, und hängt die ``values`` als eigene
    Zeilen darunter. Wer den Wert in den Satz schreibt, zeigt dem Nutzer
    geschweifte Klammern.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    placeholder = re.compile(r"\{[a-z_]+\}")
    offenders: list[str] = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg not in ("detail", "title"):
                continue
            for text in ast.walk(keyword.value):
                if (
                    isinstance(text, ast.Constant)
                    and isinstance(text.value, str)
                    and placeholder.search(text.value)
                ):
                    offenders.append(f"{path.name}:{text.lineno} {text.value[:60]}")

    assert not offenders, "Fehlertexte mit unersetztem Platzhalter:\n" + "\n".join(offenders)


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
