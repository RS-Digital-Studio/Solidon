"""Prüft erhaltene Fälle, Marker, Fixture-Auflösung und Testkörper gegen den Snapshot."""

from __future__ import annotations

import ast
from collections import Counter
import json
from pathlib import Path
import re

STATE = Path(__file__).resolve().parent
ROOT = STATE.parents[2]
before = json.loads((STATE / "ui-collection-before.json").read_text(encoding="utf-8"))
after = json.loads((STATE / "ui-collection-final.json").read_text(encoding="utf-8"))
optimized = set(json.loads((STATE / "empty-window-cases.json").read_text(encoding="utf-8")))


def indexed(entries: list[dict]) -> dict[str, dict]:
    result = {}
    for entry in entries:
        key = entry["name"]
        assert key not in result, f"Doppelte Sammlung: {key}"
        # Die Adresse einer Marker-ID-Funktion ist pro Prozess verschieden.
        result[key] = json.loads(
            re.sub(r" at 0x[0-9A-Fa-f]+", "", json.dumps(entry, ensure_ascii=False))
        )
    return result


old, new = indexed(before), indexed(after)
assert not old.keys() - new.keys(), "Ursprüngliche Testfälle fehlen."
for name, entry in old.items():
    current = new[name]
    assert entry["markers"] == current["markers"], name
    if name not in optimized:
        assert entry["fixtures"] == current["fixtures"], name
        assert entry["fixture_details"] == current["fixture_details"], name
    else:
        expected = (set(entry["fixtures"]) - {"window"}) | {"empty_window", "session"}
        assert set(current["fixtures"]) == expected, name
        assert current["fixture_details"]["empty_window"] == new[
            "test_an_unreadable_gcode_file_says_so"
        ]["fixture_details"]["window"], name
        for fixture in set(entry["fixture_details"]) - {"window"}:
            assert entry["fixture_details"][fixture] == current["fixture_details"][fixture], name


def functions(path: Path) -> dict[str, ast.FunctionDef]:
    return {
        node.name: node
        for node in ast.parse(path.read_text(encoding="utf-8")).body
        if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
    }


old_ui = functions(STATE / "test_ui.before.py")
current_ui = functions(ROOT / "tests/test_ui.py")
for suffix in ("dialogs", "export", "licensing", "remote"):
    extra = functions(ROOT / f"tests/test_ui_{suffix}.py")
    assert not current_ui.keys() & extra.keys(), "Ein Test wurde kopiert statt verschoben."
    current_ui.update(extra)
for name, node in old_ui.items():
    assert ast.dump(node) == ast.dump(current_ui[name]), name


class OriginalFixtureName(ast.NodeTransformer):
    def visit_Name(self, node: ast.Name) -> ast.Name:
        if node.id == "empty_window":
            node.id = "window"
        return node

    def visit_arg(self, node: ast.arg) -> ast.arg:
        if node.arg == "empty_window":
            node.arg = "window"
        return node


old_operations = functions(STATE / "test_operation_ui.before.py")
current_operations = functions(ROOT / "tests/test_operation_ui.py")
assert old_operations.keys() == current_operations.keys()
for name, node in old_operations.items():
    current = current_operations[name]
    if name in optimized:
        current = OriginalFixtureName().visit(current)
    assert ast.dump(node) == ast.dump(current), name

report = {
    "original_cases": len(old),
    "current_cases": len(new),
    "lost_cases": [],
    "duplicate_cases": [],
    "concurrent_additions": sorted(new.keys() - old.keys()),
    "original_case_metadata_unchanged_except_expected_fixture_swap": True,
    "ui_test_ast_unchanged": len(old_ui),
    "operation_test_ast_unchanged_except_fixture_alias": len(old_operations),
    "reduced_import_fixtures": sorted(optimized),
    "cases_per_file": dict(Counter(entry["nodeid"].split("::")[0] for entry in after)),
}
(STATE / "ui-split-comparison.json").write_text(
    json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
)
print(json.dumps(report, indent=2, ensure_ascii=False))
