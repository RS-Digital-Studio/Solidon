"""Katalogeinträge der lokalen KI in allen fünf Sprachen setzen.

Neue Schlüssel dürfen noch nicht dastehen (sonst würde eine gewählte
Übersetzung still ersetzt — ``katalogschreiber-ueberschreibt-still``), alte
müssen dastehen. Geschrieben wird wie der Bestand: sortiert, zwei Leerzeichen,
Umlaute unmaskiert, LF, Schlusszeilenumbruch.

    python catalogs.py entries.json
"""

import json
import sys
from pathlib import Path

LOCALES = Path(r"F:\3D Druck\app\i18n\locales")
LANGUAGES = ("en", "es", "fr", "it", "pt")


def main() -> int:
    spec = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    add: dict[str, dict[str, str]] = spec.get("add", {})
    remove: list[str] = spec.get("remove", [])
    for source, texts in add.items():
        missing = [lang for lang in LANGUAGES if not texts.get(lang)]
        assert not missing, f"{source[:50]}: fehlt {missing}"
    for lang in LANGUAGES:
        path = LOCALES / f"{lang}.json"
        raw = path.read_bytes().decode("utf-8")
        catalogue = json.loads(raw)
        present = [source for source in add if source in catalogue and catalogue[source] != add[source][lang]]
        assert not present, f"{lang}: stünde schon anders da — {[s[:40] for s in present]}"
        absent = [source for source in remove if source not in catalogue]
        assert not absent, f"{lang}: alter Schlüssel fehlt — {[s[:40] for s in absent]}"
        for source in remove:
            del catalogue[source]
        for source, texts in add.items():
            catalogue[source] = texts[lang]
        text = json.dumps(catalogue, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        path.write_bytes(text.encode("utf-8"))
        print(lang, "+", len(add), "-", len(remove))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
