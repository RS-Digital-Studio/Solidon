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

**Aufbau (1–5)** — Qt unterhalb `ui/`? Geometrieänderung außerhalb einer Op?
Schreiben auf `ctx.scene`? Op ohne Registereintrag, Schema, Test, Texte?
Signatur abweichend von Bauplan §9?

**Zahlen (6–9)** — Rundung im Kern? `==` auf Fließkomma? Toleranz als
Zahlenkonstante statt `auto:<material>`? Streuzahl statt Projektparameter?
Zufall ohne `ctx.seed` oder ohne `deterministic=False`?

**Sicherheit (10–15)** — `eval`? Operation, die ein fremdes Programm startet
(→ `foreign.SCRIPTED_OPS`)? Absoluter Pfad in einer Projektdatei? Eigener
Baustein, der mitreisen könnte? Kennzahlen aus Schichtanalyse und G-Code
vermischt? Abhängigkeit unter GPL?

**Bedienung (16–20)** — Agentenvorschlag mit mehr als einer Transaktion?
Ausnahme ohne Handlungsvorschlag? Bedeutung allein über Farbe?
Bestätigungsdialog vor einer rücknehmbaren Handlung? Feste Zeichenkette statt
`tr()`?

**Haltung (21–22)** — Wurde geraten, wo `ctx.ask` hingehört? Neue Abhängigkeit
ohne Eintrag in der Lizenzliste?

Dazu, ohne Regelnummer, aber genauso ein Fund: deutscher Bezeichner in
`app/`, fehlende Übersetzung, fehlender Test zu neuem Verhalten.

## Ergebnis

Je Verstoß: Regelnummer, Datei:Zeile, was dagegen verstößt, der Fix. Am Ende
ein Satz, ob die Änderung regelkonform ist. Kein Verstoß ist ein gültiges
Ergebnis — dann sag es kurz und ohne Füllwerk.
