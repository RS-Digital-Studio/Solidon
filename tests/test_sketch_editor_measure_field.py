"""Das Maßfeld der Zeichnung am Ort: Sein Beispiel ist ein gültiger Ausdruck (A-M3, B-L6).

Ohne Fenster: Der Satz wird aus ``app/ui/sketch_editor.py`` gelesen, das
Beispiel darin in jeder Sprache ausgewertet.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from app.core.expressions import evaluate
from app.i18n import SOURCE_LANGUAGE
from app.i18n.catalog import available_languages, read_catalog

EDITOR = Path(__file__).resolve().parents[1] / "app" / "ui" / "sketch_editor.py"


def _measure_field_note() -> str:
    """Der Satz unter dem Maßfeld am Ort (``target="message:constraint_value"``)."""
    for call in ast.walk(ast.parse(EDITOR.read_text(encoding="utf-8"))):
        if not (isinstance(call, ast.Call) and getattr(call.func, "id", "") == "edit_value"):
            continue
        words = {word.arg: word.value for word in call.keywords}
        target = words.get("target")
        if not (isinstance(target, ast.Constant) and target.value == "message:constraint_value"):
            continue
        note = words["note"]
        while isinstance(note, ast.Call) and note.args:
            note = note.args[0]
        assert isinstance(note, ast.Constant), ast.unparse(words["note"])
        return str(note.value)
    raise AssertionError("das Maßfeld der Zeichnung trägt keinen Satz mehr")


def test_the_example_in_the_measure_field_evaluates_in_every_language() -> None:
    """Das Beispiel unter dem Maßfeld wertet mit einem gleichnamigen Parameter aus (A-M3).

    „etwa breite/2“ brach ab: Parameter werden mit ``@`` geschrieben. Und der
    Name ist in jeder Sprache derselbe wie im Beispiel der Parameterfelder
    („zum Beispiel =@breite/2“ → ``=@width/2``), statt deutsch zu bleiben (B-L6).
    """
    note = _measure_field_note()
    sibling = "zum Beispiel =@breite/2"
    for language in available_languages():
        source = language == SOURCE_LANGUAGE
        catalog = {} if source else read_catalog(language)
        said = note if source else catalog[note]
        example = said.rstrip(".").split()[-1]
        named = re.fullmatch(r"@(\w+)/2", example)
        assert named is not None, f"{language}: {said!r}"
        assert evaluate(example, {named.group(1): 70.0}) == pytest.approx(35.0), language
        expected = sibling if source else catalog[sibling]
        assert f"@{named.group(1)}/2" in expected, f"{language}: {said!r} gegen {expected!r}"
