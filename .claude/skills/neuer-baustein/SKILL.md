---
name: neuer-baustein
description: >
  Führt durch das Anlegen eines Bausteins in der Bibliothek: register_part gegen
  manifold3d, benannte Features, to_scad, Vorschaubild, deklarationsbasierte
  Bereichsprüfung und Normteilmaße aus der Tabelle.
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
- Maße in `app/core/knowledge/standards.py` beziehungsweise
  `app/core/knowledge/data/standards.toml` nachschlagen. Fehlt ein
  Normteil dort, wird **zuerst die Tabelle ergänzt** — mit Quelle im Kommentar.
- Zwei bestehende Bausteine lesen (`fasteners.py`, `mechanics.py`,
  `mounting.py`, `structure.py`).

## Die acht Schritte

1. Aktuelle Signatur von `register_part` in
   `app/core/knowledge/parts/registry.py` lesen: Name, Titel, Gruppe,
   Parameterschema, Features und Dokumentation; Körperzahl,
   Wand- und Feature-Anforderungen sowie zulässige Kombinationen deklarieren.
2. Geometrie gegen **`manifold3d`** — nicht OpenSCAD
3. Benannte Features zurückgeben: die Provenienz-IDs, an denen Ops und
   Passungen ansetzen
4. `to_scad()` ergänzen
5. **Bereichstest mit Nachweis** für den neuen oder geänderten Baustein —
   `python tools/check_part_ranges.py <name>`: fährt `check_part(spec,
   profile)` mit dem Bezugsprofil (wasserdicht, Mindestwandstärke, keine
   Selbstdurchdringung an den Grenzen, Features korrekt benannt) und schreibt
   `data/part_ranges.toml`. An den Rändern bricht Geometrie, nicht in der
   Mitte. Jedes Längenmaß braucht beide Grenzen, sonst fährt der Test nur die
   untere. Gültige, ausgeschlossene, abgebrochene und fehlerhafte Fälle im
   `RangeReport` auseinanderhalten; eine endliche Grenzprüfung beweist nicht
   jeden Wert eines kontinuierlichen Bereichs. **Der Testlauf unten fährt
   den Bereich nicht**, er vergleicht nur den Nachweis mit dem Stand
   (`test_every_shipped_part_carries_a_current_range_proof`).
6. Normteilmaße aus der Tabelle, nie hart im Baustein
7. Vorschaubild über den vorhandenen Weg in
   `app/core/knowledge/parts/preview.py` rendern lassen; `preview` ist kein
   Argument der aktuellen `register_part`-Signatur.
8. Bei Maßänderung an einem bestehenden Baustein: `parts_version` erhöhen,
   Änderungsverlauf ergänzen (was, wann, warum, Auswirkung auf die Maße)

## Spiel und Passung

Spiel wird als Parameter aus dem Materialprofil abgeleitet, nicht als feste
Zugabe versteckt. Ein Paar in Einbaulage prüfen: Schnittvolumen und
Mindestabstand für Spielpassungen, beabsichtigte Überdeckung für Press- oder
Schnappverbindungen sowie den Montageweg. Zwei einzeln gültige Körper und
eine Boolesche Differenz allein belegen keine passende Verbindung — die
gedruckte Mutter bestand jeden Einzeltest und ließ bis zum 22.09.2026 keine
gedruckte Schraube durch.

## Abschluss

`/pruefen` mit den betroffenen Dateien, insbesondere `tests/test_parts.py`
und `tests/test_parts_catalog.py`, ausführen. Das Entwicklungstor ist vor
einem Commit nötig, kein zweiter Lauf nach jedem Schritt. Fensterdateien und
Leistungstests laufen ausschließlich beim Release. Melden: Name,
Parameter, Features, tatsächlicher Bereichslauf mit Profil und Ergebnis,
seine Abdeckung, ob `parts_version` steigen musste, und ob der Katalogeintrag mit
Vorschaubild vorhanden ist.
