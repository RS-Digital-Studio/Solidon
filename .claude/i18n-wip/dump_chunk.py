"""Gibt Katalogeinträge als nummerierte JSONL-Zeilen aus: {"i", "de", "en"}.

Aufruf: python dump_chunk.py START END
Liest app/i18n/locales/en.json (Schlüssel = deutscher Quelltext,
Wert = englische Übersetzung als Referenz).
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

en = json.loads((ROOT / "app/i18n/locales/en.json").read_text(encoding="utf-8"))
items = list(en.items())
start, end = int(sys.argv[1]), int(sys.argv[2])
for i in range(start, min(end, len(items))):
    key, value = items[i]
    print(json.dumps({"i": i, "de": key, "en": value}, ensure_ascii=False))
