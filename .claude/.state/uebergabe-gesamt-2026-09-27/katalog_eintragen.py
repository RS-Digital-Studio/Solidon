"""Trägt Übersetzungen in die Sprachkataloge ein, sortiert wie die Kataloge.

Aufruf: python katalog_eintragen.py <baum> <eintraege.json>
``eintraege.json``: {"en": {"Quelle": "Übersetzung", ...}, "es": {...}, ...}
Die Kataloge sind ``json.dumps(..., ensure_ascii=False, indent=2,
sort_keys=True)`` plus Zeilenende; so werden sie auch geschrieben.
"""

import json
import sys
from pathlib import Path

root = Path(sys.argv[1]) / "app" / "i18n" / "locales"
entries = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
for language, pairs in sorted(entries.items()):
    catalog = root / f"{language}.json"
    data = json.loads(catalog.read_text(encoding="utf-8"))
    for source, translation in pairs.items():
        if source in data and data[source] != translation:
            print(language, "ersetzt", source[:60])
        data[source] = translation
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    catalog.write_bytes(text.encode("utf-8"))
    print(language, len(pairs))
