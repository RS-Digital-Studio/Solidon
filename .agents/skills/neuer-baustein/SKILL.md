---
name: neuer-baustein
description: >
  Führt durch das Anlegen oder Ändern eines Bausteins in der Bibliothek:
  register_part, Geometrie für Netz- und exakten Kern, benannte Features,
  to_scad, Vorschaubild, Bereichsnachweis, Normteilmaße aus der Tabelle und
  die Bibliotheksversion bei Maßänderungen. Anleitung für die Sitzung selbst;
  abgeschlossen delegieren: Agent solidon3d-baustein.
argument-hint: "[welcher Baustein]"
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---

# Neuer Baustein: Angaben aus der aktuellen Anfrage

Der Agent in der Anwendung setzt **geprüfte** Bausteine zusammen, statt
Geometrie zu erfinden (§24) — was hier entsteht, wird später blind benutzt.
Die Checkliste „neuer Baustein“ aus `AGENTS.md` gilt vollständig, die Regeln in
`.claude/rules/bausteine.md` ebenso; die Karte ist
`app/core/knowledge/parts/CLAUDE.md`. Hier steht, was je Schritt dazugehört.

## Vorher

- Die Bibliothek unter `app/core/knowledge/parts/` durchsehen: Gibt es ihn
  schon, oder deckt ein vorhandener den Fall mit einem Parameter mehr ab?
- Maße in `app/core/knowledge/standards.py` beziehungsweise
  `app/core/knowledge/data/standards.toml` nachschlagen. Fehlt ein Normteil
  dort, wird **zuerst die Tabelle ergänzt**, mit Quelle im Kommentar.
- Zwei bestehende Bausteine derselben Gruppe lesen (`fasteners.py`,
  `mechanics.py`, `mounting.py`, `structure.py`, …).

## Je Schritt

1. **`register_part`:** die aktuelle Signatur in
   `app/core/knowledge/parts/registry.py` lesen — Name, Titel, Gruppe,
   Parameterschema, Features, Dokumentation; dazu Körperzahl, Wand- und
   Feature-Anforderungen und zulässige Kombinationen deklarieren. Ein
   `preview`-Argument gibt es nicht.
2. **Geometrie** als Formbeschreibung über `shapes` und `build`, gerechnet am
   Netz gegen `manifold3d` und am exakten Träger über `exact.py`; wer ein Netz
   direkt anfasst, sagt es (`shapes.mesh_only`).
3. **Benannte Features** zurückgeben — die Provenienz-IDs, an denen Ops und
   Passungen ansetzen.
4. **`to_scad()`** ergänzen; es schreibt eine Datei und führt nichts aus.
5. **Bereichsnachweis** für den neuen oder geänderten Baustein:
   `python tools/check_part_ranges.py <name>` prüft mit dem Bezugsprofil
   Wasserdichtheit, Mindestwandstärke, Selbstdurchdringung an den Grenzen und
   die Namen der Features und schreibt `data/part_ranges.toml`. An den Rändern
   bricht Geometrie, nicht in der Mitte: Jedes Längenmaß braucht beide
   Grenzen, sonst fährt der Lauf nur die untere. Gültige, ausgeschlossene,
   abgebrochene und fehlerhafte Fälle im `RangeReport` auseinanderhalten; eine
   endliche Grenzprüfung beweist nicht jeden Wert eines Bereichs. Die Suite
   fährt den Bereich nicht, sie vergleicht nur den Nachweis mit dem Stand.
6. **Normteilmaße** aus der Tabelle, nie hart im Baustein.
7. **Vorschaubild** über `app/core/knowledge/parts/preview.py` rendern lassen,
   nicht von Hand pflegen.
8. **Maßänderung an einem bestehenden Baustein:** `LIBRARY_VERSION` in
   `parts/registry.py` erhöhen — sie reist als `parts_version` in jede
   Projektdatei — und am Baustein einen `PartChange` in `changes=` ergänzen
   (Version, Datum, Grund, Auswirkung auf die Maße); der letzte Eintrag setzt
   die Version des Bausteins, ein zweites Feld dafür gibt es nicht. Eine
   gemeinsame Ursache mehrerer Bausteine ist ein gemeinsamer `PartChange`.
   Danach `tools/make_examples.py`: Die Beispielprojekte tragen die
   Bibliotheksversion, und `tests/test_examples.py` hält sie dort fest.

## Spiel und Passung

Spiel kommt als Parameter aus dem Materialprofil, nicht als versteckte feste
Zugabe. Ein Paar wird in Einbaulage geprüft: Schnittvolumen und Mindestabstand
für Spielpassungen, beabsichtigte Überdeckung für Press- und
Schnappverbindungen, dazu der Montageweg; ein Gewindepaar über den ganzen
Eingriffsweg (`bausteine.md`). Zwei einzeln gültige Körper und eine Boolesche
Differenz belegen noch keine passende Verbindung.

Legt ein **aufgesetzter** Baustein sein Spiel in eine Bohrung, ein
Innengewinde oder eine Aufnahme, steht `play_inside=True` und das Loch ist ein
benanntes Innenmerkmal mit Achse und Tiefe: Der Druckrat stellt dann den
Lochausgleich des Slicers für das Teil auf null, wenn die Achse auf der Platte
steht (`scene.fits.allowances_for`, RM-589). Ohne die Angabe gleicht der Slicer
das Spiel ein zweites Mal aus; `test_parts.py` prüft es am gebauten Baustein.

## Abschluss

`.agents/skills/pruefen/SKILL.md` mit den betroffenen Dateien, insbesondere `tests/test_parts.py` und
`tests/test_parts_catalog.py`, dazu ruff, format, mypy; das Entwicklungstor vor
jedem Stand, der nach main geht. Melden:
Name, Parameter mit Grenzen, Features, Bereichslauf mit Profil und Ergebnis,
ob die Bibliotheksversion steigen musste, und ob der Katalogeintrag mit
Vorschaubild steht.
