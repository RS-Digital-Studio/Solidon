"""Zwei Funktionen nebeneinander: Körper ohne Docstring, Ähnlichkeit, Diff.

Aufruf: twin_diff.py datei:zeile datei:zeile [datei:zeile datei:zeile ...]
"""

from __future__ import annotations

import ast
import difflib
import sys
from pathlib import Path


def body_at(spec: str) -> tuple[str, str, int]:
    file, line = spec.rsplit(":", 1)
    tree = ast.parse(Path(file).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.lineno <= int(line) <= (node.end_lineno or 0):
            if node.lineno == int(line) or node.name:
                body = node.body
                if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
                    body = body[1:]
                text = "\n".join(ast.unparse(s) for s in body)
                return node.name, text, (node.end_lineno or node.lineno) - node.lineno + 1
    raise SystemExit(f"keine Funktion bei {spec}")


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    args = sys.argv[1:]
    for a, b in zip(args[::2], args[1::2]):
        na, ta, la = body_at(a)
        nb, tb, lb = body_at(b)
        ratio = difflib.SequenceMatcher(None, ta, tb).ratio()
        print(f"\n===== {na} ({a}, {la} Z) <-> {nb} ({b}, {lb} Z): Ähnlichkeit {ratio:.2f}, wortgleich={ta == tb}")
        if ta == tb:
            print(ta[:600])
            continue
        for line in difflib.unified_diff(ta.splitlines(), tb.splitlines(), lineterm="", n=1):
            print("  " + line[:160])


if __name__ == "__main__":
    main()
