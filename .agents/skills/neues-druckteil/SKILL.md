---
name: neues-druckteil
description: >
  Legt ein neues Druckteil im Ordner „3D Drucker" an: Maße klären, parametrisches
  Skript mit trimesh/manifold3d, Netzprüfung, STL-Export, Bauteil-Spezifikation und
  Druckhinweise für den Elegoo Centauri Carbon 2.
argument-hint: "[was gebraucht wird]"
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# Neues Druckteil: $ARGUMENTS

Ein Teil, das gedruckt und benutzt wird. Material und Zeit sind echt.

## 1. Maße klären, bevor irgendetwas entsteht

Die wichtigste Phase. Für jedes maßgebliche Maß muss feststehen, **woher es
kommt**: gemessen, aus einer Herstellerangabe, aus einem Ersatzteil, oder
geschätzt. Geschätzte Maße werden als solche markiert — und ein geschätztes
Passmaß bedeutet: erst ein **Prüfstück**, das nur diese Passung enthält, dann
das ganze Teil.

Frag nach, was du nicht wissen kannst: Spaltmaße, Blechdicken, Rohrdurchmesser,
Gewindegrößen, Anflugrichtungen. Raten ist hier teurer als jede Rückfrage.

Prüfe zugleich: passt das Teil in **256 × 256 × 256 mm**? Wenn nicht, ist die
Antwort Teilung mit Verstiftung oder Verschraubung, nicht Verkleinerung.

## 2. Konstruieren

Ordner unter `3D Drucker/NN_Name/`, Skript in Python mit
`trimesh`/`manifold3d`. OpenSCAD ist auf dieser Maschine nicht installiert.

Aufbau nach dem Vorbild bestehender Skripte: benannte Maßkonstanten oben mit
Einheit und Quelle im Kommentar, `PART`-Schalter für Varianten und Prüfstücke,
Export am Ende. Spiel und Wandstärke sind **eigene Parameter**.

Die Konstruktionsrichtwerte für FDM stehen in
`references/fdm-konstruktion.md` — Überhänge, Wandstärken, Passungen,
Gewinde, Verschraubungen.

## 3. Prüfen

Vor dem Export, und das Ergebnis wird gezeigt, nicht behauptet:

- `is_watertight` — wasserdicht
- Anzahl Komponenten (eine, wenn es eine sein soll)
- Volumen und Bounding Box plausibel, passt auf die Platte
- keine Selbstdurchdringung, Normalen einheitlich
- dünnste Stelle über der Mindestwandstärke

## 4. Dokumentieren

`NN_Name/Name_Bauteil-Spezifikation.md`:

- Zweck und Einbausituation
- Maßtabelle **mit Quelle je Maß** und den offenen Messungen
- Materialwahl mit Begründung (Bestand: ASA, PETG Pro, PETG-CF, PETG
  transluzent, TPU 95A, PLA)
- Druckhinweise: Orientierung, Stützen ja/nein, Perimeter, Schichthöhe,
  Besonderheiten
- Was noch zu prüfen ist, bevor das ganze Teil gedruckt wird

Iterationen kommen in `Versuch N/`, der aktuelle Stand in den Projekt-Root.
Zum Schluss `3D Drucker/AGENTS.md` um den Projekteintrag ergänzen.

## Haltung

Betrifft das Teil Sicherheit — Last, Tor, Schloss, Wasser, Strom —, sag das
ausdrücklich, und die vorhandene Sicherung bleibt dran. Ein Druckteil ist eine
Hilfe, kein Sicherheitselement.
