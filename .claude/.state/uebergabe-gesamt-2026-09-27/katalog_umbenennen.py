"""Ersetzt in allen Sprachkatalogen einen Quelltext durch einen neuen.

Aufruf: python katalog_umbenennen.py <baum> <umbenennungen.json>
``umbenennungen.json``: [{"alt": "...", "neu": "...", "je_sprache": {"en": "...", ...}}]
Fehlt eine Sprache in ``je_sprache``, bleibt ihre alte Übersetzung stehen.
Geschrieben wie die Kataloge: sortiert, zwei Leerzeichen, Zeilenende.
"""

import json
import sys
from pathlib import Path

root = Path(sys.argv[1]) / "app" / "i18n" / "locales"
changes = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
for catalog in sorted(root.glob("*.json")):
    language = catalog.stem
    data = json.loads(catalog.read_text(encoding="utf-8"))
    for change in changes:
        old = data.pop(change["alt"], None)
        if old is None:
            print(language, "fehlt:", change["alt"][:60])
            continue
        data[change["neu"]] = change.get("je_sprache", {}).get(language, old)
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    catalog.write_bytes(text.encode("utf-8"))
    print(language, len(changes))
