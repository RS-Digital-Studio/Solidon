---
name: regelcheck
description: >
  Prüft die aktuellen Änderungen gegen die 22 harten Regeln aus AGENTS.md —
  Aufbau, Zahlen, Sicherheit, Bedienung, Haltung — und nennt je Verstoß die
  Regelnummer, die Stelle und den Fix. Benutzen vor dem Commit oder wenn unklar
  ist, ob eine Änderung regelkonform ist.
argument-hint: "[optional: Datei oder Modul]"
allowed-tools: Bash, Read, Grep, Glob
---

# Regelcheck

Jede Regel aus `AGENTS.md` hat einen Test. Dieser Durchgang findet, was der
Test erst später fände — oder was er gar nicht sieht.

## Umfang

Ohne Argument: `git diff` und `git diff --cached`, dazu unversionierte Dateien.
Mit Argument: die genannte Datei oder das genannte Modul vollständig.

## Durchgang

Geh die Regeln in dieser Reihenfolge durch und prüfe jede ausdrücklich am
geänderten Code. Regeln, die das geänderte Gebiet nicht berühren, überspringst
du stillschweigend — behaupte nicht, sie geprüft zu haben.

**Aufbau (1–5)** — Qt unterhalb `ui/`? Gespeicherte Geometrie ohne registrierte
Op? Schreiben auf `ctx.scene`? Op ohne vollständigen Registervertrag,
Wirkungstest oder Texte? Geometrieändernde Op ohne Geometrietest?
Schattenvertrag neben der kanonischen Definition aus Bauplan §9? Persistenter
Vertrag ohne Migration, alte Beispieldatei und Rundreisetest?

**Zahlen (6–9)** — Rundung aus der Anzeige im Kern? Geometrische Gleichheit
oder Gültigkeit mit exaktem Fließkommavergleich? Fertigungstoleranz als Zahl
statt Profilwert? Lokale Rechentoleranz statt `EPS_GEOM`, `EPS_DISPLAY` oder
`EPS_MATCH`? Hauptmaß oder wiederverwendeter Nutzerwert als Streuzahl statt
Projektparameter? Zufall ohne `ctx.seed` oder ohne `deterministic=False`?

**Sicherheit (10–15)** — `eval`? Fremder Quelltext an `eval`, `exec`,
Importlader oder Unterprozess? Absoluter Pfad in einer Projektdatei? Eigener
`.py`-Baustein, der mitreisen könnte, oder eine Datei, die das Register
erweitert? Kennzahlen aus Schichtanalyse und G-Code vermischt? Neue
Abhängigkeit ohne Lizenzeintrag oder mit GPL?

**Bedienung (16–20)** — Agentenvorschlag mit mehr als einer Transaktion?
Nutzersichtbarer `AppError` ohne passende Handlung? Bedeutung allein über Farbe?
Bestätigungsdialog vor einer rücknehmbaren Handlung? Feste Zeichenkette statt
`tr()`?

**Haltung (21–22)** — Wurde geraten, wo in einer Op `ctx.ask`, im Agenten
`ask_user` oder in einem anderen Kernweg eine strukturierte Mehrdeutigkeit
hingehört? Öffnet der Kern einen Dialog? Neue Abhängigkeit ohne Eintrag in der
Lizenzliste?

Dazu, ohne Regelnummer, aber genauso ein Fund: deutscher Bezeichner oder
Docstring in `app/`, fehlende Übersetzung, fehlender Test zu neuem Verhalten.

## Ergebnis

Je Verstoß: Regelnummer, Datei:Zeile, was dagegen verstößt, der Fix. Am Ende
ein Satz, ob die Änderung regelkonform ist. Kein Verstoß ist ein gültiges
Ergebnis — dann sag es kurz und ohne Füllwerk.
