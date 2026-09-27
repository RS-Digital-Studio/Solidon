---
name: regelcheck
description: >
  Prüft die aktuellen Änderungen oder ein genanntes Modul Regel für Regel gegen
  die 22 harten Regeln aus AGENTS.md und nennt je Verstoß Regelnummer, Stelle
  und Fix. Schneller Durchgang in der Sitzung, vor dem Commit oder bei der
  Frage, ob eine Änderung regelkonform ist; das vollständige Review mit
  Korrektheit und Testqualität macht der Agent solidon3d-review.
argument-hint: "[optional: Datei oder Modul]"
allowed-tools: Bash, Read, Grep, Glob
---

# Regelcheck

Jede Regel aus `AGENTS.md` hat einen Test. Dieser Durchgang findet, was der
Test erst später fände — oder gar nicht sieht.

## Umfang

Ohne Argument: `git diff HEAD` samt unversionierter Dateien. Mit Argument: die
genannte Datei oder das Modul vollständig. Karten und Regeln der berührten
Verzeichnisse mitlesen. Eine Prüfanfrage liefert Befunde; geändert wird nur
im Rahmen eines Reparaturauftrags.

## Durchgang

Die 22 Regeln aus `AGENTS.md` in ihrer Reihenfolge, jede ausdrücklich am
geänderten Code. Regeln, die das Gebiet nicht berühren, überspringst du — und
behauptest nicht, sie geprüft zu haben. Was dabei am häufigsten übersehen
wird:

- **Aufbau (1–5):** Qt, das über einen Umweg unter `core` landet, auch nur für
  Typen; eine Vorschau im Editor, die Dokumentzustand schreibt statt einen
  Parameterwert zu sammeln; Schreiben auf `ctx.scene` über ein veränderliches
  Objekt der Szene.
- **Zahlen (6–9):** Rundung im Kern; `==` auf Fließkomma; Fertigungsspiel am
  Materialprofil vorbei; numerische Grenzen außerhalb ihrer zuständigen
  Quelle; Zufall ohne `ctx.seed` oder ohne `deterministic=False`.
- **Sicherheit (10–15):** Jeder Weg, der Quelltext annimmt, braucht eine
  Prüfung und einen Eintrag in `foreign.SCRIPTED_OPS`; externe Programme wie
  Slicer sind davon zu unterscheiden. Rezepte aus registrierten
  Ops dürfen mitreisen, ein Baustein als `.py` nie. Absolute Pfade in
  Projektdateien; Kennzahlen aus Schichtanalyse und G-Code ohne Herkunft;
  Abhängigkeit außerhalb der Lizenzfreigabe.
- **Bedienung (16–20):** ein Agentenvorschlag mit mehr als einer
  Transaktion; eine Ausnahme ohne Handlungsvorschlag; Farbe ohne zweite
  Kodierung; eine Nachfrage vor rücknehmbarer Handlung außerhalb der
  ausdrücklich erlaubten Ausnahmen; eine feste Zeichenkette statt `tr()`,
  auch in Auswahlwerten.
- **Haltung (21–22):** geraten, wo `ctx.ask` hingehört; neue Abhängigkeit
  ohne Eintrag in der Lizenzliste.

Dazu, ohne Regelnummer und genauso ein Fund: ein deutscher Bezeichner in
`app/` oder `tools/`, eine fehlende Übersetzung, ein fehlender Test oder
Nachweis, den eine Checkliste aus `AGENTS.md` verlangt.

## Ergebnis

Je Verstoß: Regelnummer, Datei:Zeile, was dagegen verstößt, der Fix. Am Ende
ein Satz über den geprüften Umfang und seine Grenzen. „Keine Verstöße im
geprüften Umfang“ ist ein gültiges Ergebnis, aber keine Zusage über
ungeprüfte Pfade. Gelesenes und tatsächlich Ausgeführtes getrennt ausweisen.
