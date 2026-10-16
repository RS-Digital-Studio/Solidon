"""Ein Wert als Literal für TOML und OpenSCAD — eine Funktion statt zweier (RA-11).

``knowledge/calibration._literal`` und ``knowledge/parts/scad._literal`` waren
wortgleiche Zwillinge (``zwillinge.md``, „Zwillinge, die noch stehen“); die
Kalibrierung kannte dazu Listen. Jetzt schreiben beide über
``parts/literal.literal``. Ohne Fenster.
"""

from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).parents[1] / "app" / "core" / "knowledge"


def test_one_literal_writes_both_formats() -> None:
    from app.core.knowledge.parts.literal import literal

    assert literal(True) == "true" and literal(False) == "false"
    assert literal(2.5) == "2.5" and literal(3) == "3"
    assert literal('PLA "matt"') == '"PLA \\"matt\\""', "ein Anführungszeichen bricht nichts"
    assert literal([1.0, "a", False]) == '[1.0, "a", false]'


def test_neither_module_keeps_its_own_copy() -> None:
    owners = []
    for path in (ROOT / "calibration.py", ROOT / "parts" / "scad.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        owners += [
            path.name
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "_literal"
        ]
    assert owners == [], owners
