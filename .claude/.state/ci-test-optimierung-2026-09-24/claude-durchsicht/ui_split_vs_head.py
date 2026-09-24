"""Vergleicht Codex' UI-Umzug gegen HEAD statt gegen eine Arbeitskopie.

Für jede Funktion/Klasse/Zuweisung auf Modulebene: Wo steht sie in HEAD, wo
jetzt, und ist ihr AST gleich? So trennt sich der reine Umzug von fremden
Änderungen, die im geteilten Baum in denselben Dateien liegen.
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"F:\3D Druck")
NEW = ["tests/test_ui_dialogs.py", "tests/test_ui_export.py", "tests/test_ui_licensing.py",
       "tests/test_ui_remote.py", "tests/ui_helpers.py"]


def head(path: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), "show", f"HEAD:{path}"], capture_output=True,
                          text=True, encoding="utf-8", check=True).stdout


def top_level(source: str) -> dict[str, str]:
    result = {}
    for node in ast.parse(source).body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            result[node.name] = ast.dump(node)
        elif isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name):
                    result[target.id] = ast.dump(node)
    return result


old = top_level(head("tests/test_ui.py"))
current = top_level((ROOT / "tests/test_ui.py").read_text(encoding="utf-8"))
moved: dict[str, str] = {}
for path in NEW:
    for name, dump in top_level((ROOT / path).read_text(encoding="utf-8")).items():
        moved.setdefault(name, dump)
        if name in moved and moved[name] != dump and path != NEW[-1]:
            pass

moved_names = {name for path in NEW[:-1] for name in top_level((ROOT / path).read_text(encoding="utf-8"))}
helper_names = set(top_level((ROOT / "tests/ui_helpers.py").read_text(encoding="utf-8")))

print("HEAD test_ui.py Namen:", len(old), " jetzt:", len(current))
changed_moved = [n for n in moved_names if n in old and moved[n] != old[n]]
new_moved = [n for n in moved_names if n not in old]
print("verschoben und gegenüber HEAD geändert:", sorted(changed_moved))
print("verschoben, aber nicht in HEAD:", sorted(new_moved))
helpers_changed = [n for n in helper_names if n in old and top_level((ROOT / 'tests/ui_helpers.py').read_text(encoding='utf-8'))[n] != old[n]]
print("Helfer gegenüber HEAD geändert:", sorted(helpers_changed))
print("Helfer nicht in HEAD test_ui.py:", sorted(helper_names - set(old)))
still_changed = [n for n in current if n in old and current[n] != old[n]]
print("in test_ui.py verblieben und geändert:", sorted(still_changed))
print("in test_ui.py neu:", sorted(set(current) - set(old)))
gone = set(old) - set(current) - moved_names - helper_names
print("aus test_ui.py verschwunden, nirgends wieder:", sorted(gone))
both = moved_names & set(current)
print("doppelt (verschoben und noch da):", sorted(both))
sys.exit(0)
