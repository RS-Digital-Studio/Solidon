---
name: neuer-baustein
description: >
  Führt durch das Anlegen eines Bausteins in der Bibliothek: register_part gegen
  manifold3d, benannte Features, to_scad, Vorschaubild, Test über den gesamten
  Parameterbereich und Normteilmaße aus der Tabelle.
argument-hint: "[welcher Baustein]"
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# Neuer Baustein: $ARGUMENTS

Der Grundsatz aus §24: Der Agent setzt **geprüfte** Bausteine zusammen, statt
Geometrie zu erfinden. Was hier entsteht, wird später blind benutzt — also
stimmt es oder es existiert nicht.

## Vorher

- Register unter `app/core/knowledge/parts/` durchsehen: gibt es ihn schon,
  oder deckt ein vorhandener den Fall mit einem Parameter mehr ab?
- Maße in `standards.py` beziehungsweise `data/*.toml` nachschlagen. Fehlt ein
  Normteil dort, wird **zuerst die Tabelle ergänzt** — mit Quelle im Kommentar.
- Zwei bestehende Bausteine lesen (`fasteners.py`, `mechanics.py`,
  `mounting.py`, `structure.py`).

## Die acht Schritte

1. `@register_part(...)` mit `params`, `features`, `preview`, `doc`
2. Geometrie gegen **`manifold3d`** — nicht OpenSCAD
3. Benannte Features zurückgeben: die Provenienz-IDs, an denen Ops und
   Passungen ansetzen
4. `to_scad()` ergänzen
5. **Bereichstest von Hand** für den neuen Baustein — `check_part(spec,
   profile)`: wasserdicht, Mindestwandstärke, keine Selbstdurchdringung an den
   Grenzen, Features korrekt benannt. An den Rändern bricht Geometrie, nicht
   in der Mitte. Der Lauf über *alle* Bausteine ist am 03.09.2026 gefallen, weil
   er eine halbe Stunde je Torlauf kostete (`.claude/rules/bausteine.md`); für
   den einen, den du gerade baust, dauert er eine Minute.
6. Normteilmaße aus der Tabelle, nie hart im Baustein
7. Vorschaubild rendern lassen
8. Bei Maßänderung an einem bestehenden Baustein: `parts_version` erhöhen,
   Änderungsverlauf ergänzen (was, wann, warum, Auswirkung auf die Maße)

## Spiel und Passung

Spiel gehört ins Materialprofil, nicht in den Baustein. Ein Paar (Gewinde,
Stift und Bohrung, Schnappverbindung) wird nicht daran geprüft, dass beide
Teile für sich sauber sind, sondern daran, dass die **Differenz** über die
volle Länge Luft lässt.

## Abschluss

```
.venv\Scripts\python.exe -m pytest tests/test_parts.py tests/test_parts_catalog.py -q
```

dann `/pruefen`. Melden: Name, Parameter, Features, was der Bereichstest
abdeckt, ob `parts_version` steigen musste, und ob der Katalogeintrag mit
Vorschaubild vorhanden ist.
