"""Messung: doppelte Stellen und Zwillinge in app/.

Sieben Fragen, jede eine eigene Tabelle. Kein eval, nur ast.
"""

from __future__ import annotations

import ast
import hashlib
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("app")
FILES = sorted(p for p in ROOT.rglob("*.py") if "__pycache__" not in p.parts)

TRIVIAL_NUMBERS = {0, 1, 2, 3, 4, 5, 6, 8, 10, 12, 16, 20, 24, 32, 50, 60, 64, 90, 100, 128, 180, 200, 255, 256, 360, 500, 512, 1000, 1024, 0.5, 1.0, 0.0, 2.0, 0.1, 0.01, 0.001, -1}


def load() -> dict[Path, ast.Module]:
    trees = {}
    for path in FILES:
        try:
            trees[path] = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            print(f"!! Syntaxfehler {path}: {exc}", file=sys.stderr)
    return trees


def rel(path: Path) -> str:
    return path.as_posix()


# ---------- 1. Konstanten ----------

ARITH = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b, ast.FloorDiv: lambda a, b: a // b, ast.Pow: lambda a, b: a**b}


def value_of(node: ast.expr):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        pass
    if isinstance(node, ast.BinOp) and type(node.op) in ARITH:
        left, right = value_of(node.left), value_of(node.right)
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            try:
                return ARITH[type(node.op)](left, right)
            except (ZeroDivisionError, OverflowError):
                return None
    return None


def constants(trees):
    by_name: dict[str, list[tuple[str, int, object]]] = defaultdict(list)
    for path, tree in trees.items():
        for node in tree.body:
            targets = []
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]
            for name in targets:
                if not (name.isupper() and len(name) > 3) or node.value is None:
                    continue
                value = value_of(node.value)
                if isinstance(value, bool) or not isinstance(value, (int, float, str)):
                    continue
                by_name[name].append((rel(path), node.lineno, value))
    return by_name


def report_constants(trees):
    by_name = constants(trees)
    total = sum(len(v) for v in by_name.values())
    print(f"\n## 1. Konstanten auf Modulebene: {total} in {len(by_name)} Namen")

    same_name_same_value = {n: p for n, p in by_name.items() if len(p) > 1 and len({v for _, _, v in p}) == 1}
    same_name_diff_value = {n: p for n, p in by_name.items() if len(p) > 1 and len({v for _, _, v in p}) > 1}
    print(f"\n### 1a. Gleicher Name, gleicher Wert, mehrere Dateien: {len(same_name_same_value)}")
    for name, places in sorted(same_name_same_value.items()):
        print(f"  {name} = {places[0][2]!r}: " + ", ".join(f"{f}:{l}" for f, l, _ in places))
    print(f"\n### 1b. Gleicher Name, VERSCHIEDENER Wert: {len(same_name_diff_value)}")
    for name, places in sorted(same_name_diff_value.items()):
        print(f"  {name}: " + ", ".join(f"{f}:{l}={v!r}" for f, l, v in places))

    by_value: dict[object, list[tuple[str, str, int]]] = defaultdict(list)
    for name, places in by_name.items():
        for f, l, v in places:
            if isinstance(v, (int, float)) and v not in TRIVIAL_NUMBERS:
                by_value[v].append((name, f, l))
            elif isinstance(v, str) and len(v) > 3 and not v.isupper():
                by_value[v].append((name, f, l))
    multi = {v: p for v, p in by_value.items() if len({n for n, _, _ in p}) > 1}
    print(f"\n### 1c. Gleicher (nicht-trivialer) Wert unter verschiedenen Namen: {len(multi)}")
    for value, places in sorted(multi.items(), key=lambda kv: -len(kv[1])):
        print(f"  {value!r}: " + ", ".join(f"{n}@{f}:{l}" for n, f, l in places))


# ---------- 2./3. Funktions-Zwillinge ----------


class Normalise(ast.NodeTransformer):
    """Namen und Konstanten austauschen, Attribute und Aufrufziele behalten."""

    def visit_Name(self, node):
        return ast.copy_location(ast.Name(id="N", ctx=node.ctx), node)

    def visit_arg(self, node):
        node.arg = "a"
        node.annotation = None
        return node

    def visit_Constant(self, node):
        if isinstance(node.value, str):
            return ast.copy_location(ast.Constant(value="S"), node)
        if isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
            return ast.copy_location(ast.Constant(value=0), node)
        return node


def strip_docstring(body):
    if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
        return body[1:]
    return body


def functions(trees):
    out = []
    for path, tree in trees.items():
        parents = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parents[child] = parent
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                owner = parents.get(node)
                qual = node.name
                if isinstance(owner, ast.ClassDef):
                    qual = f"{owner.name}.{node.name}"
                body = strip_docstring(node.body)
                if not body:
                    continue
                lines = (node.end_lineno or node.lineno) - node.lineno + 1
                exact = "\n".join(ast.unparse(s) for s in body)
                mod = ast.Module(body=[ast.fix_missing_locations(Normalise().visit(ast.parse(ast.unparse(s)))) for s in body], type_ignores=[])
                norm = "\n".join(ast.unparse(m) for m in mod.body)
                out.append({"file": rel(path), "line": node.lineno, "qual": qual, "lines": lines, "stmts": len(body), "exact": exact, "norm": norm, "cls": isinstance(owner, ast.ClassDef)})
    return out


def report_exact_twins(funcs):
    print("\n## 2. Wortgleiche Funktionskörper (ohne Docstring), mind. 4 Anweisungen oder 8 Zeilen")
    groups = defaultdict(list)
    for f in funcs:
        if f["stmts"] >= 4 or f["lines"] >= 8:
            groups[hashlib.sha1(f["exact"].encode()).hexdigest()].append(f)
    twins = [g for g in groups.values() if len(g) > 1]
    print(f"Gruppen: {len(twins)}")
    for g in sorted(twins, key=lambda g: -g[0]["lines"]):
        print(f"  [{g[0]['lines']} Zeilen] " + " | ".join(f"{f['qual']} {f['file']}:{f['line']}" for f in g))


def report_renamed_twins(funcs):
    print("\n## 3. Strukturgleiche Funktionskörper (Namen/Zahlen normalisiert), mind. 6 Anweisungen oder 12 Zeilen")
    groups = defaultdict(list)
    for f in funcs:
        if f["stmts"] >= 6 or f["lines"] >= 12:
            groups[hashlib.sha1(f["norm"].encode()).hexdigest()].append(f)
    exact_hashes = set()
    twins = []
    for g in groups.values():
        if len(g) > 1 and len({f["exact"] for f in g}) > 1:
            twins.append(g)
    print(f"Gruppen (nicht schon unter 2. gemeldet): {len(twins)}")
    for g in sorted(twins, key=lambda g: -g[0]["lines"]):
        print(f"  [{g[0]['lines']} Zeilen] " + " | ".join(f"{f['qual']} {f['file']}:{f['line']}" for f in g))


def shingles(text: str, k: int = 6) -> set[int]:
    toks = re.findall(r"\w+|[^\w\s]", text)
    return {hash(tuple(toks[i : i + k])) for i in range(max(0, len(toks) - k + 1))}


def report_near_twins(funcs, min_lines=15, min_jaccard=0.55):
    print(f"\n## 4. Nahe Zwillinge (Jaccard über 6-Gramme der normalisierten Form >= {min_jaccard}, ab {min_lines} Zeilen)")
    cands = [f for f in funcs if f["lines"] >= min_lines]
    sets = [shingles(f["norm"]) for f in cands]
    index = defaultdict(list)
    for i, s in enumerate(sets):
        for h in s:
            index[h].append(i)
    shared = Counter()
    for members in index.values():
        if len(members) > 40:
            continue
        for a in range(len(members)):
            for b in range(a + 1, len(members)):
                shared[(members[a], members[b])] += 1
    pairs = []
    for (a, b), n in shared.items():
        if cands[a]["exact"] == cands[b]["exact"] or cands[a]["norm"] == cands[b]["norm"]:
            continue
        union = len(sets[a] | sets[b])
        if union and n / union >= min_jaccard:
            pairs.append((n / union, cands[a], cands[b]))
    print(f"Paare: {len(pairs)}")
    for j, a, b in sorted(pairs, key=lambda t: -t[0]):
        print(f"  {j:.2f} [{a['lines']}/{b['lines']} Z] {a['qual']} {a['file']}:{a['line']}  <->  {b['qual']} {b['file']}:{b['line']}")


# ---------- 5. Literalvergleiche ----------


def report_literal_compares(trees):
    print("\n## 5. Zeichenketten, gegen die an >= 3 Stellen verglichen wird (== / != / in)")
    hits = defaultdict(list)
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if isinstance(node, ast.Compare):
                for side in [node.left, *node.comparators]:
                    if isinstance(side, ast.Constant) and isinstance(side.value, str) and len(side.value) >= 2:
                        hits[side.value].append(f"{rel(path)}:{node.lineno}")
    multi = {k: v for k, v in hits.items() if len(v) >= 3 and len({p.split(':')[0] for p in v}) >= 2}
    print(f"Literale: {len(multi)}")
    for lit, places in sorted(multi.items(), key=lambda kv: -len(kv[1]))[:60]:
        files = Counter(p.rsplit(':', 1)[0] for p in places)
        print(f"  {lit!r} x{len(places)} in {len(files)} Dateien: " + ", ".join(f"{f}({n})" for f, n in files.most_common()))


# ---------- 6. Kommentare, die eine Kopie bekennen ----------

CONFESSION = re.compile(r"wie bei |wie in `|dieselbe (Zahl|Schwelle|Logik|Regel|Reihenfolge|Liste|Formel)|derselbe (Grund|Wert|Satz|Weg)|denselben (Grund|Wert|Weg)|genau wie |Kopie (von|aus|der|des)|identisch (mit|zu)|analog zu|gespiegelt|spiegelt |Gegenstück (zu|von|in)|Zwilling|zweite Stelle|an zwei Stellen|beide Stellen|siehe auch `|wie `\w+\.\w+`", re.IGNORECASE)


def report_confessions():
    print("\n## 6. Kommentare/Docstrings, die eine Kopie oder ein Gegenstück bekennen")
    hits = []
    for path in FILES:
        for i, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if CONFESSION.search(line):
                hits.append((rel(path), i, line.strip()[:140]))
    print(f"Zeilen: {len(hits)}")
    per_file = Counter(f for f, _, _ in hits)
    print("  je Datei (Top 15): " + ", ".join(f"{f}({n})" for f, n in per_file.most_common(15)))
    for f, i, text in hits:
        print(f"  {f}:{i}: {text}")


# ---------- 7. Gleichnamige Funktionen in verschiedenen Modulen ----------


def report_same_names(funcs):
    print("\n## 7. Gleichnamige Funktionen/Methoden (>= 8 Zeilen) in verschiedenen Dateien")
    by_name = defaultdict(list)
    for f in funcs:
        if f["lines"] >= 8:
            by_name[f["qual"].split(".")[-1]].append(f)
    skip = {"__init__", "__repr__", "__eq__", "__hash__", "__str__", "__enter__", "__exit__", "run", "main", "setup", "paintEvent", "eventFilter", "mousePressEvent", "mouseMoveEvent", "mouseReleaseEvent", "keyPressEvent", "resizeEvent", "showEvent", "closeEvent", "sizeHint", "wheelEvent", "hideEvent", "changeEvent", "focusOutEvent", "focusInEvent", "leaveEvent", "enterEvent", "contextMenuEvent", "dragEnterEvent", "dropEvent", "mouseDoubleClickEvent", "keyReleaseEvent", "timerEvent", "event", "accept", "reject", "apply", "reset", "clear", "update", "refresh", "retranslate", "retranslate_ui", "values", "value", "params", "retranslateUi", "minimumSizeHint", "dragMoveEvent", "moveEvent", "tabletEvent", "inputMethodEvent", "actionEvent"}
    multi = {n: fs for n, fs in by_name.items() if n not in skip and len({f["file"] for f in fs}) > 1}
    print(f"Namen: {len(multi)}")
    for name, fs in sorted(multi.items(), key=lambda kv: -len(kv[1])):
        if len(fs) > 12:
            print(f"  {name} x{len(fs)} in {len({f['file'] for f in fs})} Dateien (Qt-Muster, nicht gelistet)")
            continue
        print(f"  {name}: " + " | ".join(f"{f['file']}:{f['line']}({f['lines']}Z)" for f in fs))


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    trees = load()
    print(f"# Zwillingsmessung über {ROOT} — {len(trees)} Dateien, {sum(len(p.read_text(encoding='utf-8').splitlines()) for p in trees)} Zeilen")
    funcs = functions(trees)
    print(f"Funktionen/Methoden: {len(funcs)}")
    report_constants(trees)
    report_exact_twins(funcs)
    report_renamed_twins(funcs)
    report_near_twins(funcs)
    report_literal_compares(trees)
    report_confessions()
    report_same_names(funcs)
