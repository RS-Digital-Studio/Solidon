"""Gibt Katalogeinträge als nummerierte JSONL-Zeilen aus: {"i", "de", "en"}.

Aufruf: python dump_chunk.py START END
Liest base-en.json (Schlüssel = deutscher Quelltext, Wert = englische
Übersetzung als Referenz) — **nicht** den lebenden Katalog unter
app/i18n/locales/. Der wächst, während hier übersetzt wird, und jeder neue
Schlüssel verschiebt alle Indizes über seiner Einfügestelle. Die Teile in
diesem Ordner sind indexbasiert; sie brauchen eine unbewegte Basis.
"""

import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent / "base-en.json"

en = json.loads(BASE.read_text(encoding="utf-8"))
items = list(en.items())
start, end = int(sys.argv[1]), int(sys.argv[2])
for i in range(start, min(end, len(items))):
    key, value = items[i]
    print(json.dumps({"i": i, "de": key, "en": value}, ensure_ascii=False))
