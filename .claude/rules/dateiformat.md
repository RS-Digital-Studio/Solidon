---
paths:
  - "app/core/ingest/**/*.py"
  - "app/core/export/**/*.py"
  - "app/core/scene/project*.py"
---

# Regeln für Projektdatei, Import und Export

## Migration ist Pflicht, nicht Kür

Eine Projektdatei ist zugleich Fehlerbericht und Archiv. Ändert sich das
Format:

1. `format_version` erhöhen
2. Migrationsfunktion `vN → vN+1` schreiben
3. Beispieldatei der alten Version einchecken
4. Test: die alte Datei öffnet und rechnet **korrekt**, nicht nur fehlerfrei
5. Ältere Migrationen bleiben bestehen und werden nie zusammengefasst

## Was nicht in die Datei gehört

Keine absoluten Pfade. Kein ausführbarer Code. Keine eigenen Bausteine — ein
Projekt verweist auf sie namentlich, und fehlt einer, hält die Auswertung an
und sagt welcher (§24.5, §32).

## Eingangsstufe

Jede geladene Datei durchläuft dieselbe Kette, und das Ergebnis steht in
`sources`: Einheit bestimmen (bei Verdacht **nachfragen**, nicht annehmen),
Vertices verschweißen, entartete Dreiecke entfernen, Normalen vereinheitlichen,
Komponenten zählen (Kleinstteile **melden** statt still löschen), Lage
ermitteln und Aufsetzen anbieten — nicht erzwingen.

Die Eingangsstufe ist die Op `load`, damit ihre Parameter im Stack sichtbar
und änderbar bleiben.

## Formate

3MF ist eine **Baugruppe**, keine einzelne Datei: mehrere Objekte, Stückzahlen,
Materialgruppen je Dreieck, Transformationen. Wer es als ein Mesh liest,
verliert genau das. STL kennt keine Einheiten und keine Farbe. STEP bringt
echte Flächen, aber keine Farbe.

Dreieckszahl und Dateigröße sind beim Import gedeckelt — mit klarer Meldung
statt Speicherüberlauf.
