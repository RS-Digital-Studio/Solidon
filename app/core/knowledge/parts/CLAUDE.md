# `app/core/knowledge/parts/` — die Bausteinbibliothek

Geprüfte, parametrische Teile, die der Agent und der Nutzer zusammensetzen
(§24).

Die Regeln stehen in `.claude/rules/bausteine.md`.

## Eigene Lizenz — MIT

**Dieses Verzeichnis steht unter MIT**, anders als der Rest der Anwendung;
die `LICENSE`-Datei liegt hier. Der Grund steht in §36: Die Geometrie, die
diese Bausteine erzeugen, landet in den **eigenen Modellen der Nutzer** —
nichts hier darf für sie eine Lizenzfrage aufwerfen.

Wer hier Code hinzufügt, prüft, dass er unter MIT stehen darf.

## Gebaut gegen `manifold3d`

Nicht gegen OpenSCAD. So hängt `insert_part` an keiner externen Installation
und bleibt testbar. Seit dem Ausbau von OpenSCAD (26.08.2026) gibt es die
Alternative ohnehin nicht mehr — `scad.py` **schreibt** eine Datei und führt
nichts aus; das Format bleibt, der Lauf ist weg.

## Die Karte

**Die Bausteine, nach Gruppen**

| Datei | Gruppe |
|---|---|
| `fasteners.py` | Verbindungen — Schrauben, Muttern, Senkungen |
| `mechanics.py` | Mechanik — was sich bewegt und verbindet: Scharniere, Gewinde |
| `mounting.py` | Halterungen — was etwas an etwas anderem hält |
| `structure.py` | Struktur — versteifen, hindurchführen, anbinden |
| `testbodies.py` | Prüfkörper für die Kalibrierung (§28.3) |

**Das Gerüst**

| Datei | Rolle |
|---|---|
| `registry.py` | `register_part`, `PARTS`, `LIBRARY_VERSION`, `changed_since()` |
| `builtin.py` | Lädt die fünf mitgelieferten Gruppen einmalig; `bootstrap.load_operations()` ruft `builtin.load()` vor der Op-Erzeugung, der Paketimport selbst registriert nichts |
| `ops.py` | **Jeder Baustein wird zusätzlich eine Operation** (§24.1, §10) |
| `build.py` | Gemeinsamer Boden für jeden Baustein |
| `shapes.py` | Kleine Formen, aus denen die Bausteine gebaut werden |
| `range_check.py` | Der Bereichstest in der Anwendung |
| `preview.py` | Vorschaubilder — **gerendert, nicht von Hand gepflegt** |
| `scad.py` | Export als OpenSCAD-Quelltext |
| `recipe.py` | Ein eigener Baustein als **Rezept**: Daten statt Programm (§24.5) |
| `user.py` | Eigene Bausteine aus dem Nutzerverzeichnis |
| `check.py` | Was gesagt werden muss, wenn ein Projekt geöffnet wird (§24.4) |

## Rezept gegen `.py` — der Unterschied ist die Sicherheit

Ein Rezept ist eine Liste registrierter Operationen mit Werten. Es **führt
nichts aus**, was eine Projektdatei nicht ohnehin auslöst — deshalb darf es
in einer Projektdatei mitreisen (Regel 13, Entscheidung Robert 24.08.2026).

Ein eigener Baustein als `.py` bleibt dagegen, wo er liegt: im
Nutzerverzeichnis. Ausführbarer Code reist nie mit.

## Ein neuer Baustein

1. `@register_part(...)` mit `params`, `features`, `preview`, `doc`
2. Umsetzung gegen `manifold3d`
3. **Benannte Features zurückgeben** — das sind die Provenienz-IDs, an denen
   später Ops und Passungen ansetzen
4. `to_scad()` für den Quelltext-Export
5. Test über den **gesamten** Parameterbereich: wasserdicht,
   Mindestwandstärke, keine Selbstdurchdringung an den Grenzen
6. Normteilmaße aus `standards.py`, **nie im Baustein hart eintragen**
7. Vorschaubild rendern lassen
8. Maß an einem bestehenden Baustein geändert? `LIBRARY_VERSION` erhöhen und
   den Änderungsverlauf ergänzen (§24.4) — alte Projekte melden es beim
   Öffnen

## Zwei Versionen, die leicht zu verwechseln sind

- **`LIBRARY_VERSION`** steht in `registry.py` und beschreibt **die
  Bibliothek**. Sie wird erhöht, wenn sich ein Maß ändert.
- **`parts_version`** ist ein Feld **im Dokument** und hält fest, gegen
  welchen Stand das Projekt gebaut wurde.

`check.py` vergleicht die beiden beim Öffnen — daher die Meldung „dieser
Baustein hat sich geändert". `AGENTS.md` sagt verkürzt „`parts_version`
erhöhen"; gemeint ist die Konstante der Bibliothek.
