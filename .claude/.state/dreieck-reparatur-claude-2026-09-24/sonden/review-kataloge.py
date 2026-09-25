"""Review-Sonde: Stehen alle `_()`/`tr()`-Texte der geprüften Dateien in allen Katalogen? (nur lesend)

Liest die Quelle über `ast` (auch zusammengesetzte Zeichenketten), prüft jeden Katalog
unter `app/i18n/locales/`. Zusätzlich: Platzhalter der Übersetzung gegen die Quelle,
und Übersetzungen, die wortgleich zur deutschen Quelle sind (Verdacht: nicht übersetzt).
"""

from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

ROOT = Path(r"F:\3D Druck")
FILES = [
    "app/core/geom/repair.py",
    "app/core/geom/intersections.py",
    "app/core/geom/ops.py",
    "app/core/ingest/loader.py",
    "app/core/ingest/ops.py",
    "app/core/perceive/maps.py",
    "app/core/errors.py",
    "app/ui/labels.py",
    "app/ui/panels.py",
    "app/ui/main_window.py",
]
PLACEHOLDER = re.compile(r"\{([a-z_]+)[^}]*\}")


def texts(path: Path) -> list[tuple[str, str | None, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        name = node.func.id if isinstance(node.func, ast.Name) else None
        if name not in ("_", "tr") or not node.args:
            continue
        first = node.args[0]
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            continue
        context = None
        for keyword in node.keywords:
            if keyword.arg == "context" and isinstance(keyword.value, ast.Constant):
                context = keyword.value.value
        found.append((first.value, context, node.lineno))
    return found


catalogs = {
    path.stem: json.loads(path.read_text(encoding="utf-8"))
    for path in sorted((ROOT / "app" / "i18n" / "locales").glob("*.json"))
}
missing = 0
placeholder_mismatch = 0
same = 0
for relative in FILES:
    for msgid, context, line in texts(ROOT / relative):
        key = f"{context}\x04{msgid}" if context else msgid
        wanted = set(PLACEHOLDER.findall(msgid))
        for language, catalog in catalogs.items():
            if key not in catalog:
                missing += 1
                print(f"FEHLT {language}: {relative}:{line}: {msgid!r}")
                continue
            translated = catalog[key]
            if set(PLACEHOLDER.findall(translated)) != wanted:
                placeholder_mismatch += 1
                print(f"PLATZHALTER {language}: {relative}:{line}: {msgid!r} -> {translated!r}")
print("fehlend:", missing, "Platzhalter:", placeholder_mismatch, file=sys.stderr)

# Die neuen Reparaturtexte einzeln ausgeben, damit man die Übersetzungen lesen kann.
for relative in ("app/core/geom/repair.py", "app/core/perceive/maps.py", "app/core/errors.py"):
    for msgid, context, line in texts(ROOT / relative):
        if relative.endswith("errors.py") and msgid not in (
            "Überschneidungen auflösen",
            "Offen lassen",
            "Dicke geben",
        ):
            continue
        row = {language: catalogs[language].get(msgid) for language in sorted(catalogs)}
        print("TEXT", relative, line, json.dumps({"de": msgid, **row}, ensure_ascii=False))
