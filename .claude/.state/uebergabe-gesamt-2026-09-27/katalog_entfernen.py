"""Entfernt einen Quelltext aus allen Sprachkatalogen, Zeile für Zeile.

Aufruf: python katalog_entfernen.py <baum> <quelltext-anfang>
Die Datei bleibt sonst Byte für Byte, wie sie ist.
"""

import json
import sys
from pathlib import Path

root = Path(sys.argv[1]) / "app" / "i18n" / "locales"
start = sys.argv[2]
for catalog in sorted(root.glob("*.json")):
    raw = catalog.read_bytes()
    lines = raw.decode("utf-8").split("\n")
    kept = [line for line in lines if not line.startswith('  "' + start)]
    removed = len(lines) - len(kept)
    if removed:
        text = "\n".join(kept)
        json.loads(text)
        catalog.write_bytes(text.encode("utf-8"))
    print(catalog.name, removed)
