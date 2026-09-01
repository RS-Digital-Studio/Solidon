# `app/i18n/` — Übersetzung

Ohne Qt. Der Kern darf `tr()` benutzen, ohne PySide6 zu holen — das ist der
Grund, warum hier nicht `QTranslator` steht.

Die Regeln stehen in `.claude/rules/uebersetzung.md`.

## Die Karte

| Datei | Rolle |
|---|---|
| `__init__.py` | `tr()`, `TranslatableText`, Sprachumschaltung, `format_decimal()`, `sort_key()` |
| `catalog.py` | Kataloge laden: `available_languages()`, `read_catalog()`, `install_language()` |
| `extract.py` | Übersetzbare Texte aus den Quellen einsammeln (§37.2) |
| `locales/` | Ein JSON je Sprache: `en` `es` `fr` `it` `pt` |

Der Einsammler liest außerdem die vier Generatorquellen aus
`extract.EXTRA_SOURCES`. Dazu gehören `make_manual.py` und `site_nav.py`:
Titel, Navigation, Sprunglinks und PDF-Ränder sind Teil derselben Sprache wie
der Handbuchinhalt. Eine Katalogdatei reicht deshalb auch für den vollständigen
Webrahmen einer neuen Sprache; feste Sprachtabellen im Generator sind kein
zulässiger zweiter Katalog.

**Deutsch hat keine Datei.** Es ist die Quellsprache — der deutsche Text steht
im Code, die Kataloge übersetzen ihn weg.

## Eine weitere Sprache ist eine Datei und sonst nichts

Sprachauswahl, Einsammler, Handbuch, Abbildungen und Prüfung lesen alle
`available_languages()`, also das Verzeichnis. Wer `locales/nl.json`
einscheckt, hat Niederländisch hinzugefügt — an keiner zweiten Stelle steht
eine Liste, die nachgezogen werden müsste.

**Unvollständig eingecheckt wird keine.** `tests/test_translations.py` prüft
jede gefundene Datei, nicht nur die englische.

## Zwei Fallen, beide gemessen

- **Sprachwechsel braucht zwei Schritte.** `install_language()` lädt,
  `set_language()` aktiviert. Wer eines vergisst, misst seinen eigenen Aufbau
  und hält ihn für einen Fehler.
- **Katalogschlüssel sind Wörter, keine IDs.** Der Schlüssel *ist* der
  deutsche Quelltext. Ein neu formuliertes Label kapert deshalb still den
  Eintrag eines anderen, wenn beide denselben Satz ergeben — das Minus im
  Katalog-Diff ist der Alarm, der Test sieht es nicht.

## Werkzeug

Nach neuen Texten die Kataloge nachziehen — der Lauf meldet je Sprache,
wie viele Texte offen sind:

```bash
.venv/Scripts/python.exe -m app.i18n.extract
```
