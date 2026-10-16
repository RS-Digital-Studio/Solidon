"""Eine Absage an einem gewählten Merkmal bietet ein anderes Merkmal an (FD-179).

Bohrung, Gewinde, Kammer, Verschluss, Ring und jedes Merkmal, das *Merkmal
verschieben*, *ändern*, *entfernen*, *drehen*, *duplizieren* oder *Muster*
nehmen: Ihre Absagen boten „Andere Objekte wählen“ an. Der Knopf gibt dem
Schritt die im Objektbaum markierten Körper — gemeint war ein anderes Merkmal,
und das steht im Dialog des Schritts (``at_feature``, ``at_features``). Der
vierte Zwilling nach FD-123 (Kanten), FD-165 (Flächen) und FD-178.

**Bleibt bei „Andere Objekte wählen“**, wo ein Körper gemeint ist oder kein
Schritt mit Merkmalsfeld besteht (``ALLOWED``).
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.core.errors import CANCEL, CHANGE_FEATURE, CHANGE_SELECTION

ROOT = Path(__file__).resolve().parents[1]

#: Merkmalsabsagen ohne Merkmalsfeld im Schritt: *Gegenstück* ist ein Ablauf,
#: kein Schritt (``counterpart.thread_counterpart_draft``).
ALLOWED = {("app/core/counterpart.py", "thread_counterpart_draft")}

#: Die Absagen über Merkmale, die kein ``field=`` nennen (``GeometryError``
#: oder Sammelwege): Modul und Funktion.
WITHOUT_FIELD = (
    ("app/core/geom/bore_pin.py", "<module>"),
    ("app/core/geom/chamber_ops.py", "resize_chamber"),
    ("app/core/geom/chamber_ops.py", "not_a_chamber"),
    ("app/core/geom/chamber_ops.py", "_stretched_chamber"),
    ("app/core/geom/chamber_ops.py", "_trough"),
    ("app/core/geom/closure_ops.py", "resize_closure"),
    ("app/core/geom/closure_ops.py", "_no_outline"),
    ("app/core/geom/prepare_ops.py", "_refuse_like_the_card"),
    ("app/core/geom/prepare_ops.py", "split_ways"),
)


def _suggests(node: ast.Call) -> set[str]:
    """Die Namen in ``suggestions=…`` eines Aufrufs."""
    names: set[str] = set()
    for keyword in node.keywords:
        if keyword.arg == "suggestions":
            names |= {entry.id for entry in ast.walk(keyword.value) if isinstance(entry, ast.Name)}
    return names


def _feature_refusals() -> list[tuple[str, str, int, set[str]]]:
    """Jede Absage mit ``field="at_feature"`` oder ``"at_features"`` in ``app``."""
    found = []
    for path in sorted((ROOT / "app").rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for function in ast.walk(tree):
            if not isinstance(function, ast.FunctionDef):
                continue
            for node in ast.walk(function):
                if not isinstance(node, ast.Call):
                    continue
                field = next((k.value for k in node.keywords if k.arg == "field"), None)
                at_feature = isinstance(field, ast.Constant) and field.value in (
                    "at_feature",
                    "at_features",
                )
                if at_feature and any(k.arg == "suggestions" for k in node.keywords):
                    relative = path.relative_to(ROOT).as_posix()
                    found.append((relative, function.name, node.lineno, _suggests(node)))
    return found


def test_no_refusal_at_a_feature_offers_other_objects() -> None:
    """Jede Absage mit Merkmalsfeld: keine bietet einen anderen Körper an.

    Wo ein Wert die Absage löst, bleibt *Eingabe korrigieren*, wo der Verlauf
    hilft, *Verlauf zeigen* — das prüft dieser Wächter nicht. Sammelwege
    (``_WAYS``, ``split_ways``, ``ways``) prüft der Fall darunter.
    """
    refusals = [entry for entry in _feature_refusals() if entry[:2] not in ALLOWED]
    assert len(refusals) >= 30, "der Wächter findet die Absagen nicht mehr"
    wrong = [
        f"{path}:{line} {function}: {sorted(names)}"
        for path, function, line, names in refusals
        if "CHANGE_SELECTION" in names
    ]
    assert not wrong, "\n".join(wrong)
    offering = [names for *_rest, names in refusals if "CHANGE_FEATURE" in names]
    assert len(offering) >= 15, "die Merkmalsabsagen bieten ein anderes Merkmal an"


@pytest.mark.parametrize(("path", "function"), WITHOUT_FIELD)
def test_the_refusals_without_a_field_offer_another_feature(path: str, function: str) -> None:
    tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    scopes: list[ast.AST] = (
        [statement for statement in tree.body if isinstance(statement, ast.AnnAssign | ast.Assign)]
        if function == "<module>"
        else [
            next(
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.FunctionDef) and node.name == function
            )
        ]
    )
    names = {node.id for scope in scopes for node in ast.walk(scope) if isinstance(node, ast.Name)}
    assert "CHANGE_SELECTION" not in names
    assert "CHANGE_FEATURE" in names


def test_a_chamber_refusal_offers_another_feature() -> None:
    """Ein Merkmal, das zu keiner Kammer gehört."""
    from app.core.geom.chamber_ops import not_a_chamber

    assert not_a_chamber().suggestions == (CHANGE_FEATURE, CANCEL)


def test_a_pin_outside_the_body_offers_another_bore() -> None:
    from app.core.geom.bore_pin import _not_in_the_body

    error = _not_in_the_body("hole_1", "hole_1")
    assert CHANGE_SELECTION not in error.suggestions
    assert CHANGE_FEATURE in error.suggestions


def test_another_feature_opens_the_step_where_the_feature_is_chosen() -> None:
    """Der Knopf öffnet den Schritt wie *Andere Kanten wählen* (``change_step``)."""
    assert CHANGE_FEATURE.id == "change_step"
    assert str(CHANGE_FEATURE.label) == "Anderes Merkmal wählen"
    assert CHANGE_FEATURE.primary
