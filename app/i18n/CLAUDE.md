# `app/i18n/` — Übersetzung

Ohne Qt. Der Kern darf `tr()` benutzen, ohne PySide6 zu holen — das ist der
Grund, warum hier nicht `QTranslator` steht.

Die Regeln stehen in `.claude/rules/uebersetzung.md`.

## Die Karte

| Datei | Rolle |
|---|---|
| `__init__.py` | `tr()`, `TranslatableText`, Sprachumschaltung, `format_decimal()`, `Figure` (Zahl mit Punkt, die als Platzhalterwert das Dezimalzeichen der Sprache nimmt), Anzeigeeinheit (`display_unit()`), `sort_key()` |
| `keys.py` | `native_keys(text, platform, names)`: Kürzel im Satz auf dem Mac als ⌘/⇧/⌥, Entf als ⌫, Pos1 als ↖; `translate` wendet es mit `key_platform()` an, das erst `app.ui.app` auf `sys.platform` stellt, und mit den Tastennamen der Sprache, in der der Satz steht (`key_names`, Katalogkontext „Taste“; Dateitexte über `native_text`) |
| `catalog.py` | Kataloge laden: `available_languages()`, `read_catalog()`, `install_language()` |
| `extract.py` | Übersetzbare Texte aus den Quellen einsammeln (§37.2) |
| `locales/` | Ein JSON je Sprache: `en` `es` `fr` `it` `pt` |

Der Einsammler liest außerdem die Generatorquellen aus
`extract.EXTRA_SOURCES` (Beispiele, Abbildungen, Changelog, Handbuch und
`site_nav.py`). Für `make_manual.py` und `site_nav.py` heißt das:
Titel, Navigation, Sprunglinks und PDF-Ränder sind Teil derselben Sprache wie
der Handbuchinhalt. Eine Katalogdatei reicht deshalb auch für den vollständigen
Webrahmen einer neuen Sprache; feste Sprachtabellen im Generator sind kein
zulässiger zweiter Katalog.

Der Übersetzungskontext ist sowohl als zweites Argument als auch über
`context=` zulässig. Nur `msgid` ist positionsgebunden, damit derselbe Name
auch als Platzhalterwert verwendbar bleibt. Der Einsammler und der Laufzeitweg
verwenden denselben Kontextschlüssel; `context` ist kein Formatierungswert.

**Deutsch hat keine Datei** — es ist die Quellsprache, der deutsche Text steht
im Code. Was für die Kataloge gilt (der Schlüssel ist der deutsche Satz, eine
neue Sprache ist eine Datei, nachgezogen über `extract`), steht in
`locales/CLAUDE.md`.

## Eine Falle, gemessen

**Sprachwechsel braucht zwei Schritte.** `install_language()` lädt,
`set_language()` aktiviert. Wer eines vergisst, misst seinen eigenen Aufbau
und hält ihn für einen Fehler.
