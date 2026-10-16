"""Welche Wege ``values["field"]`` lesen, steht an einer Stelle (Merge Restpaket A/B).

Restpaket B führte ``choice_ways.VALUE_WAYS`` ein (die Auswertung lässt diesen
Wegen das Feld des Werts, RB-2), Restpaket A ``refusal_details.FIELD_WAYS``
(der offene Dialog springt mit ihnen ins Feld oder schweigt, FD-95/FD-182) —
zweimal dieselbe Menge, die auseinanderlaufen konnte. Jetzt gibt es
``errors.FIELD_WAYS``; beide Seiten lesen sie, und keine andere Datei schreibt
die Menge noch einmal hin.
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.core import errors
from app.core.errors import CORRECT_INPUT, PICK_PLANE
from app.core.scene import choice_ways

APP = Path(__file__).resolve().parents[1] / "app"

#: Wie die beiden Handlungen im Quelltext stehen können: als Kennung oder als
#: ``CORRECT_INPUT.id``/``PICK_PLANE.id``.
SPELLINGS = {
    "correct_input": CORRECT_INPUT.id,
    "sketch.pick_plane": PICK_PLANE.id,
    "CORRECT_INPUT": CORRECT_INPUT.id,
    "PICK_PLANE": PICK_PLANE.id,
}


def _members(node: ast.Set) -> set[str]:
    found: set[str] = set()
    for element in node.elts:
        if isinstance(element, ast.Constant) and isinstance(element.value, str):
            found.add(SPELLINGS.get(element.value, element.value))
        elif (
            isinstance(element, ast.Attribute)
            and element.attr == "id"
            and isinstance(element.value, ast.Name)
        ):
            found.add(SPELLINGS.get(element.value.id, element.value.id))
        else:
            found.add("<anderes>")
    return found


def _sets_of_field_ways(path: Path) -> list[int]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.Set) and _members(node) == errors.FIELD_WAYS
    ]


def test_the_field_ways_are_the_two_ways_that_read_the_field() -> None:
    assert {CORRECT_INPUT.id, PICK_PLANE.id} == errors.FIELD_WAYS


def test_core_and_window_read_the_one_set() -> None:
    from app.ui import refusal_details

    assert choice_ways.FIELD_WAYS is errors.FIELD_WAYS
    assert refusal_details.FIELD_WAYS is errors.FIELD_WAYS


def test_no_module_writes_the_set_a_second_time() -> None:
    sources = sorted(APP.rglob("*.py"))
    assert len(sources) > 100, f"nur {len(sources)} Dateien — der Wächter prüft nichts"
    own = APP / "core" / "errors.py"
    assert _sets_of_field_ways(own), "Voraussetzung: der Wächter erkennt die Menge in errors.py"
    copies = {
        str(path.relative_to(APP)): lines
        for path in sources
        if path != own and (lines := _sets_of_field_ways(path))
    }
    assert not copies, copies
