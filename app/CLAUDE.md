# `app/` — die Anwendung

Vier Schichten, eine Richtung. Was hier liegt, reist zum Kunden; alles andere
im Repository tut das nicht.

## Die Schichten und die Importrichtung

```
app/cli/    ──┐
              ├──>  app/core/   (rechnet, kein Qt)
app/ui/     ──┘         │
                        └──>  app/i18n/   (tr(), Kataloge)
```

- **`core/`** rechnet und weiß nichts von Fenstern. Es ist ohne installiertes
  Qt importierbar, und `tests/test_core_isolation.py` erzwingt das.
- **`ui/`** und **`cli/`** sind zwei Oberflächen über demselben Kern. Beide
  lesen dasselbe Register (§10) — deshalb bekommt eine neue Operation Menü,
  Dialog und Kommandozeilenbefehl, ohne dass jemand sie dort einträgt.
- **`i18n/`** hängt an nichts. Der Kern darf es benutzen, ohne Qt zu holen.

**Die Gegenrichtung gibt es nicht.** `core` importiert nie aus `ui` oder
`cli` — nicht in einer Hilfsfunktion, nicht „nur für den Typ". Kommunikation
aus dem Kern nach außen läuft über den `OpContext` (`ctx.progress`,
`ctx.ask`, `ctx.cancelled`) und über nichts sonst. Alle vier Pfeile prüft
`tests/test_layer_direction.py` über den Quelltext — auch träge Importe in
Funktionen und solche unter `TYPE_CHECKING`. Der einzige Verstoß, den er beim
ersten Lauf fand, war `i18n`, das seinen Logger aus `core` holte; seither
nimmt es `logging` direkt.

## Was direkt hier liegt

| Datei | Rolle |
|---|---|
| `branding.py` | Produktidentität an genau einer Stelle (§37.1) — Name, Version, URLs. Wer den Namen tippt statt ihn hier zu holen, baut die nächste Umbenennung als Fehler ein. |

## Die übrigen Verzeichnisse

| Ordner | Inhalt |
|---|---|
| `core/` | Der kopflose Kern — eigene `CLAUDE.md`, dort geht die Pyramide weiter |
| `ui/` | PySide6-Oberfläche, 55 Module |
| `cli/` | Kommandozeile auf demselben Kern |
| `i18n/` | Übersetzung, `locales/` trägt die fünf Katalogdateien |
| `images/` | Bildschirmfotos fürs Handbuch, je Sprache ein Ordner — **erzeugt**, nicht von Hand gepflegt (`tools/make_figures.py`) |
| `examples/` | Beispielprojekte, ebenfalls erzeugt (`tools/make_examples.py`) |

## Grenzen

- **Nichts hier ist ein Hilfsprogramm.** Was nur beim Bauen oder Messen
  gebraucht wird, liegt in `tools/` und reist nicht mit.
- **Keine feste Zeichenkette in der Oberfläche** — alles über `tr()`.
  Das gilt für `ui/` und `cli/` gleichermaßen.
- **Bezeichner, Dateinamen und Modulnamen englisch**; Docstrings und
  Kommentare deutsch. `tests/test_language_rules.py` prüft `app/` und
  `tools/`, und seine Stammliste ist kuratiert — wer ein deutsches Wort in
  einem Bezeichner findet, trägt es dort ein.

Die verbindlichen Regeln stehen in `AGENTS.md` und in `.claude/rules/`; hier
steht die Karte, nicht das Gesetz.
