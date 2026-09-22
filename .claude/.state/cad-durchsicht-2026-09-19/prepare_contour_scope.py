"""Staget vier geprüfte Fachpakete mit privaten Zwischenblobs und ausdrücklichen Pfaden."""

from __future__ import annotations

import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path("F:/3D Druck")
folder = Path(__file__).parent
scope = sys.argv[1]
paths = sorted(json.loads((folder / f"{scope}-paths.json").read_text(encoding="utf-8")))
assert paths and len(paths) == len(set(paths))
assert all(not path.startswith("website/") for path in paths)
environment = dict(os.environ, SOLIDON_KEIN_PUSH="1", PYTHONUTF8="1")
environment.pop("GIT_INDEX_FILE", None)


def git(*args: str, env=environment, data: bytes | None = None) -> bytes:
    return subprocess.run(["git", *args], cwd=ROOT, env=env, input=data,
                          capture_output=True, check=True).stdout


def old(path: str) -> str:
    return git("show", f"{head}:{path}").decode("utf-8")


def current(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def without(text: str, first: str, next_: str) -> str:
    assert text.count(first) == 1 and text.count(next_) == 1
    start, end = text.index(first), text.index(next_)
    assert end > start
    return text[:start] + text[end:]


def function_range(text: str, name: str) -> tuple[int, int]:
    nodes = [node for node in ast.parse(text).body if isinstance(node, ast.FunctionDef) and node.name == name]
    assert len(nodes) == 1
    node = nodes[0]
    lines = text.splitlines(keepends=True)
    return sum(map(len, lines[:node.lineno - 1])), sum(map(len, lines[:node.end_lineno]))


assert not git("diff", "--cached", "--name-only").strip()
head = git("rev-parse", "HEAD").decode().strip()
main_index = Path(git("rev-parse", "--path-format=absolute", "--git-path", "index").decode().strip())
main_hash = hashlib.sha256(main_index.read_bytes()).hexdigest()
index = folder / f"{scope}.index"
private = dict(environment, GIT_INDEX_FILE=str(index))
git("read-tree", head, env=private)
git("add", "--", *paths, env=private)

overrides: dict[str, str] = {}
if scope == "surfaces":
    path = "app/core/perceive/features.py"
    text, complete = old(path), current(path)
    for name in ("fit_torus", "detect_curved_faces"):
        first, last = function_range(text, name)
        a, b = function_range(complete, name)
        replacement = complete[a:b]
        text = text[:first] + replacement + text[last:]
    _first, last = function_range(text, "fit_torus")
    a, b = function_range(complete, "fit_torus_samples")
    text = text[:last] + "\n\n" + complete[a:b] + text[last:]
    marker = "detect_curved_faces(mesh, found)"
    assert text.count(marker) == 1
    text = text.replace(marker, "detect_curved_faces(mesh, found, check_cancelled=check_cancelled)")
    ast.parse(text)
    overrides[path] = text
    path = "app/core/brep/features.py"
    text = current(path)
    call = ("fit_cylinder(\n"
            "                mesh.raw, patch, check_cancelled=cancelled.raise_if_cancelled if cancelled else None\n"
            "            )")
    assert text.count(call) == 1
    overrides[path] = text.replace(call, "fit_cylinder(mesh.raw, patch)")

if scope == "contours":
    path = "app/core/scene/CLAUDE.md"
    overrides[path] = without(current(path), "Die Platzierungsbezüge sind vergänglich", "`placement.original_surface_hit`")
    path = "app/core/geom/CLAUDE.md"
    overrides[path] = without(current(path), "`assign_slot`, `paint_slot` und `clear_filament` ändern Attribute", "`paint_slot.replace_filament`")

if scope == "surfaces":
    path = "app/core/brep/CLAUDE.md"
    overrides[path] = without(current(path), "Filamentzuweisungen liegen unveränderlich", "`canonical.describe`")

if scope in {"contours", "surfaces"}:
    version = 15 if scope == "surfaces" else 16
    path = "app/core/scene/cache.py"
    text = current(path)
    assert text.count("CACHE_FORMAT_VERSION: Final = 17") == 1
    text = text.replace("CACHE_FORMAT_VERSION: Final = 17", f"CACHE_FORMAT_VERSION: Final = {version}")
    paragraph = ("#: Konturmaße, native Ringmerkmale und native Filamentflächen brauchen ihre\n"
                 "#: vollständigen Mess- und Attributdaten auch nach dem Wiederöffnen.\n")
    assert text.count(paragraph) == 1
    explanation = ("#: Erkannte Kreise tragen Konturfehler und tatsächliche radiale Netzgrenzen.\n"
                   if scope == "contours" else
                   "#: Native Ring- und Restflächen werden zusätzlich vollständig erkannt.\n")
    overrides[path] = text.replace(paragraph, explanation)
    path = "tests/test_cache.py"
    text = current(path)
    suffix = ", 15, 16])" if scope == "surfaces" else ", 16])"
    assert text.count(suffix) == 2
    overrides[path] = text.replace(suffix, "])" )

catalog_keys = {
    "contours": {
        "Die Netzmaße dieser Passung sind nicht vollständig bestimmt. Die Merkmale erneut erkennen oder eine genauer aufgelöste Datei verwenden.",
        "Die geschätzten Kreismaße passen, die tatsächlichen Netzflächen belegen das Spiel aber nicht. Die Verbindung in Einbaulage prüfen oder eine genauer aufgelöste Datei verwenden.",
        "Untere Grenze des Spiels (mm)", "Obere Grenze des Spiels (mm)",
    },
    "filaments": {
        "Diese Änderung würde unterschiedlich zugewiesene Filamentflächen zusammenfassen. Behalten Sie ihre Teilungsgrenze oder weisen Sie ihnen zuerst dasselbe Filament zu.",
    },
}
if scope in catalog_keys:
    keys = catalog_keys[scope]
    for path in paths:
        if path.startswith("app/i18n/locales/"):
            original, complete = json.loads(old(path)), json.loads(current(path))
            assert keys.isdisjoint(original) and keys <= complete.keys()
            original.update({key: complete[key] for key in keys})
            overrides[path] = json.dumps(dict(sorted(original.items())), ensure_ascii=False, indent=2) + "\n"

for path, content in overrides.items():
    blob = content.encode("utf-8")
    if path.endswith(".py"):
        formatted = subprocess.run(
            [str(ROOT / ".venv/Scripts/python.exe"), "-m", "ruff", "format", "--stdin-filename", path],
            cwd=ROOT, input=blob, capture_output=True, check=True,
        )
        blob = formatted.stdout
        subprocess.run(
            [str(ROOT / ".venv/Scripts/python.exe"), "-m", "ruff", "check", "--stdin-filename", path],
            cwd=ROOT, input=blob, capture_output=True, check=True,
        )
    saved = folder / f"{scope}-blobs" / path
    saved.parent.mkdir(parents=True, exist_ok=True)
    saved.write_bytes(blob)
    if path.endswith(".py"):
        # Auch der private Zwischenstand muss syntaktisch vollständig sein.
        ast.parse(blob, filename=path)
    oid = git("hash-object", "-w", "--stdin", data=blob).decode().strip()
    git("update-index", "--cacheinfo", f"100644,{oid},{path}", env=private)

staged = git("diff", "--cached", "--name-only", env=private).decode().splitlines()
assert staged == paths, (staged, paths)
git("diff", "--cached", "--check", env=private)
(folder / f"{scope}-stage.diff").write_bytes(git("diff", "--cached", env=private))
assert head == git("rev-parse", "HEAD").decode().strip()
assert main_hash == hashlib.sha256(main_index.read_bytes()).hexdigest()
report = {"head": head, "index": str(index), "main_index_sha256": main_hash, "paths": paths}
(folder / f"{scope}-stage.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps({"scope": scope, "paths": len(paths), "head": head}))
