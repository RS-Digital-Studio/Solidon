"""Schreibt die Sätze des Börsenservers in allen Sprachen neben die PHP-Dateien.

**Der Server spricht sechs Sprachen und kann keine Kataloge lesen.** Die
Übersetzungen liegen in ``app/i18n/locales/`` und damit in der Anwendung; PHP
kommt nicht daran. Die deutschen Quelltexte stehen deshalb als eine Quelle in
``app/core/knowledge/parts/shared_texts.py``, und dieses Werkzeug zieht sie
durch jeden vorhandenen Katalog.

Dieselbe Bauart wie ``make_shared_rules.py``, und aus demselben Grund: Was
zwei Seiten in zwei Sprachen brauchen, wird **einmal** geschrieben und einmal
erzeugt. Eine von Hand gepflegte PHP-Tabelle wäre beim nächsten Satz falsch,
und zwar still — ein spanischer Kunde bekäme einen deutschen Satz, und
niemandem fiele es auf, der nicht Spanisch liest.

Aufruf::

    .venv\\Scripts\\python.exe tools/make_shared_texts.py

``tests/test_shared.py`` prüft, dass die eingecheckte Datei aktuell ist **und**
dass PHP genau die Schlüssel anfragt, die darin stehen — in beide Richtungen:
Ein fehlender Schlüssel ist eine leere Meldung beim Kunden, ein überzähliger
ist Arbeit für sechs Sprachen ohne Leser.

**Die Sprachliste wird nicht getippt.** ``available_languages()`` liest das
Katalogverzeichnis; wer eine siebte Sprache einlegt, bekommt sie hier ohne
Zutun. Eine feste Liste in PHP wäre die Stelle, an der sie hängen bliebe.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.i18n import SOURCE_LANGUAGE, install_catalog, set_language  # noqa: E402
from app.i18n.catalog import available_languages, read_catalog  # noqa: E402

#: Wohin die Sätze geschrieben werden — neben die PHP-Dateien, die sie lesen.
TARGET = ROOT / "website" / "api" / "shared-texts.json"


def texts() -> dict[str, dict[str, str]]:
    """Je Sprache eine Tabelle Schlüssel → Satz.

    **Der Katalog wird gewechselt und nicht nachgeschlagen.** Ein
    ``TranslatableText`` löst erst auf, wenn jemand ``str()`` darauf ruft, und
    zwar in der Sprache, die dann gerade eingestellt ist — deshalb wird hier
    umgeschaltet und ausgelesen, statt in einem rohen Katalogwörterbuch nach
    Schlüsseln zu suchen. Der Unterschied trägt: Ein Satz, den ein Katalog
    nicht kennt, fällt so auf die Quellsprache zurück, wie er es beim Kunden
    täte, statt hier zu fehlen.

    Zwei Schritte sind es dabei und nicht einer — ``install_language`` lädt den
    Katalog, ``set_language`` stellt ihn ein. Wer nur den ersten ruft, schreibt
    sechsmal Deutsch und merkt es nicht.
    """
    from app.core.knowledge.parts.shared_texts import all_texts

    source = all_texts()
    assert source, "das Quellmodul gibt keine Sätze heraus — dann schreibt dieses Werkzeug leer"

    collected: dict[str, dict[str, str]] = {}
    for language in available_languages():
        install_catalog(language, read_catalog(language))
        set_language(language)
        collected[language] = {key: str(text) for key, text in source.items()}
    set_language(SOURCE_LANGUAGE)
    return collected


def missing(collected: dict[str, dict[str, str]]) -> dict[str, list[str]]:
    """Was in einer Sprache leer geblieben ist — je Sprache die Schlüssel.

    **Ein leerer Katalogeintrag gibt einen leeren Satz, nicht den deutschen.**
    Das ist beim ersten Lauf keine Ausnahme, sondern der Normalfall: Der
    Einsammler legt einen neuen Schlüssel mit leerem Wert an, und bis jemand
    übersetzt, steht dort nichts. Gemessen am 30.08.2026, unmittelbar nachdem
    das Quellmodul entstand — 39 von 39 Sätzen kamen in fünf Sprachen als
    leere Zeichenkette heraus.

    Der Unterschied zur Anwendung ist entscheidend: Dort fängt
    ``test_translations`` das im Tor ab, und beim Kunden kommt es nie an. Diese
    Datei dagegen **verlässt** das Repository und wird auf einen Server gelegt,
    auf dem keine Prüfung mehr läuft. Ein leerer Satz stünde dort als leere
    Fehlermeldung — die schlechteste aller Antworten, weil der Kunde nicht
    einmal merkt, dass etwas schiefging.
    """
    return {
        language: sorted(key for key, sentence in sentences.items() if not sentence.strip())
        for language, sentences in collected.items()
        if any(not sentence.strip() for sentence in sentences.values())
    }


def written() -> str:
    """Die Datei als Text — sortiert und mit festem Einzug.

    Zweimal erzeugen ergibt zweimal dieselbe Datei; sonst meldet der Wächter
    einen Unterschied, den niemand gemacht hat.
    """
    return json.dumps(texts(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def main() -> int:
    collected = texts()
    open_ones = missing(collected)
    if open_ones:
        for language, key in sorted(open_ones.items()):
            print(f"{language}: {len(key)} Sätze ohne Übersetzung, z. B. {key[0][:60]}")
        print("Nichts geschrieben — eine leere Meldung beim Kunden ist schlimmer als keine Datei.")
        return 1

    text = written()
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    before = TARGET.read_text(encoding="utf-8") if TARGET.exists() else ""
    TARGET.write_text(text, encoding="utf-8", newline="\n")

    content = json.loads(text)
    languages = ", ".join(sorted(content))
    print(f"{TARGET.name}: {len(next(iter(content.values())))} Sätze in {len(content)} Sprachen")
    print(f"  {languages}")
    if before == text:
        print("  unverändert")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
