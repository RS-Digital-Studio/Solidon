---
name: neuer-baustein
description: >
  Führt durch das Anlegen eines Bausteins in der Bibliothek: register_part gegen
  manifold3d, benannte Features, to_scad, Vorschaubild, deklarationsbasierte
  Bereichsprüfung und Normteilmaße aus der Tabelle.
argument-hint: "[welcher Baustein]"
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# Neuer Baustein: Angaben aus der aktuellen Anfrage

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
5. **Bereichstest von Hand** für den neuen Baustein — `check_part(spec,
   profile)`: wasserdicht, Mindestwandstärke, keine Selbstdurchdringung an
   den Grenzen, Features korrekt benannt. An den Rändern bricht Geometrie,
   nicht in der Mitte. Der Lauf über *alle* Bausteine ist am 03.09.2026
   gefallen (`.claude/rules/bausteine.md`). Laufzeit und Abdeckung für den
   konkreten Baustein messen; gültige, ausgeschlossene, abgebrochene und
   fehlerhafte Fälle im `RangeReport` auseinanderhalten. Eine endliche
   Grenzprüfung beweist nicht jeden Wert eines kontinuierlichen Bereichs.
   **Der Testlauf unten führt diesen Bereichslauf nicht aus.**
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
eine Boolesche Differenz allein belegen keine passende Verbindung.

## Abschluss

`.agents/skills/pruefen/SKILL.md` mit den betroffenen Dateien, insbesondere `tests/test_parts.py`
und `tests/test_parts_catalog.py`, ausführen. Das vollständige Tor ist vor
einem Commit nötig, kein zweiter Lauf nach jedem Schritt. Melden: Name,
Parameter, Features, tatsächlicher Bereichslauf mit Profil und Ergebnis,
seine Abdeckung, ob `parts_version` steigen musste, und ob der Katalogeintrag mit
Vorschaubild vorhanden ist.
