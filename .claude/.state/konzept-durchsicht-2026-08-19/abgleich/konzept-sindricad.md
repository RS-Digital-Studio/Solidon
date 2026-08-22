# Abgleich: konzept-sindricad.md gegen den Stand vom 19.08.2026

Geprüft wurden die 15 intern prüfbaren Behauptungen der Sondierung, dazu die
Stellen des Dokuments um sie herum. Die 20 externen Behauptungen (SindriCAD,
Marktumfeld, Presse) sind hier nicht Gegenstand — sie lassen sich im
Repository nicht belegen.

Das Dokument misst sich selbst auf den **4. August 2026**. Zwischen diesem
Datum und heute liegen **568 Commits** (`git rev-list --count --since="2026-08-04" HEAD`).

**Zählung:** stimmt 5 · überholt 8 · falsch 1 · unprüfbar 1
(dazu ein Widerspruch innerhalb des Dokuments, siehe W1).

---

## 1 — Umfang: 178 Python-Dateien, 51.565 Zeilen; Tests 95/25.678; 35 Oberflächenmodule

**Urteil: überholt.**

Beleg (Repository-Wurzel):

```
find app   -name "*.py" | wc -l        ->  208
find app   -name "*.py" -exec cat {} + | wc -l ->  80743
find tests -name "*.py" | wc -l        ->  134   (davon 131 test_*.py)
find tests -name "*.py" -exec cat {} + | wc -l ->  51815
find app/ui -name "*.py" | wc -l       ->   50
```

`mypy` bestätigt die Größenordnung von der anderen Seite: „Success: no issues
found in **209** source files".

Sätze, die stattdessen dastehen müssten: „Anwendung 208 Python-Dateien,
80.743 Zeilen · Tests 134 Dateien, 51.815 Zeilen · 50 Oberflächenmodule
(Stand 19.08.2026)."

Anmerkung: Die Tabelle in 2.1 ist als Momentaufnahme gekennzeichnet („Gemessen
am 4. August 2026"). Sie ist deshalb nicht *falsch*, aber sie wird beim Lesen
als heutiger Stand genommen, weil das ganze Dokument als „Kontrolle: der Stand
von Solidon" auftritt. Ein Datumszusatz direkt an der Tabelle wäre der
billigste Fix.

---

## 2 — 61 registrierte Operationen

**Urteil: überholt.**

Beleg:

```
.venv/Scripts/python.exe -c "from app.core.bootstrap import load_operations; \
from app.core.registry import REGISTRY; load_operations(); print(len(REGISTRY.all()))"
-> 85
```

Die 61 war schon damals eine Zahl mit Haken: `ROADMAP.md` (Abschnitt „Gegen
das Wettbewerbsfeld gehalten (11.08.2026)", „Was der Durchgang durch das
laufende Fenster gefunden hat") hält fest, dass ein Zähllauf über
`walk_packages` auf 61 kam, „weil die sechzehn `insert_*`-Operationen der
Bausteine erst mit `load_operations()` entstehen" — beworben und richtig waren
dort 77.

Stattdessen: „**85** registrierte Operationen (Register nach
`load_operations()`, 19.08.2026)."

---

## 3 — 16 registrierte Bausteine

**Urteil: überholt.**

Beleg: `grep -rn "@register_part" app/core/knowledge/parts/ | wc -l` -> **17**;
dieselbe Zahl von der Op-Seite: 17 Operationen mit Präfix `insert_`
(`insert_cable_gland`, `insert_dowel`, `insert_fit_ladder`, `insert_heatset_m4`,
`insert_keyhole`, `insert_latch`, `insert_living_hinge`, `insert_magnet_pocket`,
`insert_nut_trap`, `insert_overhang_fan`, `insert_printed_thread`, `insert_rib`,
`insert_screw_hole`, `insert_snap_connector`, `insert_snap_fit`,
`insert_wall_ladder`, `insert_wall_mount`).

Stattdessen: „**17** registrierte Bausteine."

---

## 4 — 8 Texturmuster: rib, wave, knurl_straight, knurl_diamond, hexagon, dimple, voronoi, noise

**Urteil: stimmt.**

Beleg: `app/core/geom/texture_ops.py:40-49`, `PATTERNS` führt genau diese acht
in dieser Reihenfolge. Die Aussage „doppelt so viele wie SindriCAD" bleibt
damit tragfähig, soweit die externe Zahl 4 stimmt.

---

## 5 — Phasen P0 bis P15, Arbeitsliste bis auf einen Punkt abgetragen

**Urteil: überholt, in beiden Hälften.**

Beleg: `ROADMAP.md:4908` — `## P16 — Organische Modellierung`. Die höchste
Phase ist heute **P16**, nicht P15.

Offene Punkte: `grep -c "^- \[ \]" ROADMAP.md` -> **12** (gegen 444 erledigte).
Die zwölf stehen auf den Zeilen 4435, 4437, 4450, 4516, 4570, 4652, 4655,
4659, 4840, 4901, 5793, 5913 — darunter Sichtbarkeit, macOS-Auslieferung,
G-Code senden, DMARC, Auslieferungsschritte der Demo und zwei Einträge zum
sporadischen Testabsturz.

Stattdessen: „Phasen P0 bis P16; zwölf offene Punkte, überwiegend
Auslieferung und Vermarktung, dazu ein sporadischer Absturz in der
Oberflächen-Suite."

---

## 6 — Tor grün: ruff format 326 Dateien, mypy 178 Quelldateien, ruff check grün, pytest 2598 grün in 3:35 min

**Urteil: überholt.**

Belege, heute gefahren:

| Prüfung | Ausgabe |
|---|---|
| `.venv/Scripts/python.exe -m ruff format --check .` | `428 files already formatted` |
| `.venv/Scripts/python.exe -m ruff check .` | `All checks passed!` |
| `.venv/Scripts/python.exe -m mypy` | `Success: no issues found in 209 source files` |
| `.venv/Scripts/python.exe -m pytest -q --collect-only` | `4246 tests collected` |

Drei der vier Tore sind grün. Die Testzahl hat sich von 2598 auf **4246**
bewegt. Die vierte Zeile („2598 grün in 3:35 min") ist heute zusätzlich in der
*Aussage* nicht mehr haltbar: `ROADMAP.md:5793` und `:5913` führen als offene
Punkte, dass die Suite **in einem Prozess** etwa einmal in acht Läufen mit
einem nativen Abbruch stirbt (`free(): invalid pointer` bzw. „Windows fatal
exception: access violation"); je Datei ein eigener Prozess
(`tools/run_suite_isolated.py`) läuft dagegen sauber durch — „130 Testdateien
einzeln gefahren: 4164 Tests, **kein einziger Absturz**, in zwölf statt
siebzehn Minuten".

Stattdessen: „`ruff format --check` 428 Dateien · `ruff check` grün · `mypy`
ohne Beanstandung in 209 Quelldateien · `pytest` 4246 Tests; in einem Prozess
bricht der Lauf sporadisch nativ ab, isoliert je Datei nicht (ROADMAP,
'ein dritter Absturz')."

---

## 7 — Der rote Übersetzungstest ist behoben in app/ui/palette.py, Commit 1dcd855

**Urteil: stimmt.**

Beleg: `git show --stat 1dcd855` — „Drei Beschriftungen galten als aufgegeben,
weil niemand sie beim Namen nannte", 04.08.2026, geändert allein
`app/ui/palette.py` (+20/−10). Die Commit-Meldung beschreibt genau den im
Konzept geschilderten Hergang.

---

## 8 — Der native Absturz Python/VTK ist selten, aber nicht beseitigt; ein Absturzprotokoll steht in der Roadmap noch offen

**Urteil: erste Hälfte stimmt, zweite Hälfte teilweise überholt — und die
Zuordnung zur Ursache ist inzwischen widerlegt.**

Belege:

* Der Abbruch besteht: `ROADMAP.md:5793` („`test_operation_ui.py` bricht
  weiter ab, etwa einmal in acht Läufen") und `:5913`, mit einem Messpunkt
  vom **19.08.2026** — also von heute.
* Es ist aber **nicht mehr** die Referenzschleife Python/VTK aus
  `konzept-bedienung.md` 5.5. Die Roadmap schließt den Speicherbereiniger
  ausdrücklich aus („Mit `gc.disable()` fielen 5 von 24 Läufen, ohne ihn 1 von
  8: dieselbe Größenordnung") und benennt das Bild als doppeltes Freigeben.
  Eine *zweite*, davon verschiedene Ursache — ein `window`-Fixture, das sein
  Fenster dem Speicherbereiniger überließ — ist gefunden und behoben
  (`ROADMAP.md`, „Der Segmentierungsfehler auf dem Ubuntu-Runner").
* „Absturzprotokoll": im Anwendungscode gibt es keines
  (`grep -rn -i "crash\|excepthook" app/ --include=*.py` -> keine Treffer),
  `faulthandler` steht allein in `tools/run_ui_audit.py:32,535`.
  `konzept-bedienung.md:925` sagt weiterhin „ein Absturzprotokoll gibt es
  weiterhin nicht". Als *eigene Zeile in der Roadmap* steht es allerdings
  nicht mehr offen — die offenen Zeilen 5793/5913 handeln von der Ursache,
  nicht vom Protokoll.

Stattdessen: „Der sporadische Abbruch besteht weiter (etwa 1 von 8 Läufen in
einem Prozess), ist aber seit dem 14.08. anders zugeordnet: nicht die
Referenzschleife zu VTK, sondern ein doppeltes Freigeben, das je Datei
isoliert verschwindet. Ein Absturzprotokoll gibt es nach wie vor nicht."

---

## 9 — Solidon importiert zusätzlich PLY, OFF, GLTF, SVG, DXF; writer.py schreibt nur stl, 3mf, obj, step — GLB kommt herein, geht nicht hinaus

**Urteil: überholt — und das ist der wichtigste Fund dieses Abgleichs.**

Beleg: `app/core/export/writer.py:54`

```python
ExportFormat = Literal["stl", "3mf", "obj", "ply", "glb", "step"]
```

Dazu `FORMAT_SUFFIX` mit `"glb": ".glb"` (Zeile 68) und `_glb_bytes()`
(Zeile 665, `scene.export(file_type="glb")`). Der Kommentar über dem Eintrag
zitiert den Befund wörtlich: „Gelesen wurde es längst (`READABLE_SUFFIXES`) —
hinaus ging es nicht."

Der Commit dazu: `d4dea28` „GLB kam herein und ging nicht hinaus"
(`git log -S"glb" -- app/core/export/writer.py`).
`ROADMAP.md:4383` führt ihn als erledigt, ausdrücklich als „**B4 aus dem
SindriCAD-Konzept**", samt Farbgruppen je Materialslot.

Die Importseite stimmt: `app/core/geom/mesh.py:31` führt
`.stl .obj .ply .off .glb .gltf .3mf`, `app/core/ingest/fetch.py:56` ergänzt
`.step .stp .svg .dxf`.

Stattdessen: **Befund B4 und Baustein D sind zu streichen bzw. als erledigt zu
kennzeichnen** — „GLB wird seit `d4dea28` auch geschrieben, mit Namen und je
Materialslot einem eigenen Teilnetz." Zusätzlich schreibt der Export heute
`ply`, was das Dokument nirgends nennt.

---

## 10 — Drei Slicer angebunden (Prusa, Orca, Cura) mit Rückprüfung der geschriebenen Werte

**Urteil: stimmt.**

Beleg:

```
.venv/Scripts/python.exe -c "from app.core.export.handover import SlicerFlavour; \
import typing; print(typing.get_args(SlicerFlavour))"
-> ('prusa', 'orca', 'cura')
```

Die Rückprüfung steckt in `app/core/export/handover.py` (`_cura_dependants`,
`_only_chosen_adhesion`, `_orca_process`).

---

## 11 — shortcut_schemes.py bietet eine Fusion-Belegung, aber nur fürs Modellieren, nicht für die Skizze

**Urteil: als Aussage über die Datei stimmt sie; als Aussage über das
Programm ist sie überholt.**

Beleg: `app/ui/shortcut_schemes.py` (57 Zeilen) führt weiterhin nur elf
Modellier-Operationen (`sketch_extrude` E, `push_face` Q, `fillet_edges` F,
`chamfer_edges` C, `translate_object` M, `rotate_object` R, `drill_hole` H,
`duplicate_object` Ctrl+D, `mirror_object` Ctrl+M, `pattern` P,
`shell_exact` S).

Aber der Skizzeneditor führt seine Kürzel inzwischen selbst:
`app/ui/sketch_editor.py:1968` `TOOL_KEYS`, `:1979` `ACTION_KEYS`
(`rectangle` R, `distance` D, `offset` O, `construction` X), `:1990`
`VIEW_KEYS` (`fit` Home) und `PLANE_KEYS` (Ziffern 1/2/3 für die drei
Grundebenen), angemeldet als `QShortcut` in `:2404-2441`. Der Kommentar dort
nennt genau den im Konzept beschriebenen Konflikt und seine Auflösung: die
Zeichenkürzel gelten nur im Skizzenmodus.

Stattdessen: „Die Fusion-Belegung in `shortcut_schemes.py` deckt das
Modellieren; die Zeichenkürzel liegen getrennt im Skizzeneditor und gelten
kontextabhängig nur dort — der Konflikt R/C ist damit aufgelöst."

---

## 12 — Die Skizze ist rechnerisch fertig und bedienerisch halb — neun offene Punkte laut konzept-bedienung.md Teil 4

**Urteil: überholt. Zweitwichtigster Fund.**

Belege:

* `konzept-bedienung.md`, Abschnitt „Stand (5. August 2026, zweiter Eintrag)":
  „**Die fünf Zeichenpunkte 15 bis 19 sind ebenfalls durch.** Der
  Skizzeneditor hat Ursprung, Achsen und Maßstab; die Kürzel liegen wie in
  Fusion und gelten nur im Skizzenmodus; Trimmen, Verlängern, Versetzen und
  Spiegeln gibt es; Projizieren holt die Kanten des Körpers herein, und
  Hilfsgeometrie trägt Bedingungen, ohne ein Profil zu bilden; ein Maß lässt
  sich beim Zeichnen eintippen, und die Bedingungsliste zeigt beim Überfahren,
  wovon sie spricht." Dazu die beiden letzten Punkte aus Teil 4.
* `ROADMAP.md:4461`: `- [x] **Skizze bedienerisch fertig** (B1). Die
  Ändern-Gruppe stand schon; die übrigen Punkte aus `konzept-bedienung.md`
  Teil 4 sind seither nachgekommen — die Stand-Notiz dort führt alle neun als
  durch, im Code nachgeprüft am 13.08.`
* Im Code nachvollziehbar: `app/ui/sketch_editor.py` mit `ACTION_KEYS`
  (offset, construction), `Surroundings` (Docstring nennt *Projizieren*
  ausdrücklich) und den Ebenen-Ziffern.

Stattdessen: **Befund B1 und Baustein A sind erledigt.** „Die neun Punkte aus
`konzept-bedienung.md` Teil 4 sind seit dem 13.08.2026 umgesetzt; die Skizze
ist auch bedienerisch fertig."

Damit ist auch Teil 7 (Reihenfolge) hinfällig: Plätze 1, 2, 3 und 4 sind
gebaut, allein Platz 5 (Baustein C) steht noch aus.

---

## 13 — Sieben Touren; eine achte zur Textur sowie ein Musterkatalog mit gerenderten Kacheln fehlen

**Urteil: überholt in der Zahl und im Musterkatalog; die Textur-Tour und das
Beispielprojekt fehlen weiterhin.**

Belege:

* Touren: `.venv/Scripts/python.exe -c "from app.core.tour import TOURS; print(len(TOURS))"`
  -> **9**. Die `example_id` in `app/core/tour.py`: `weg1-halterung-anpassen`,
  `weg2-halter-konstruieren`, `weg3-generiert-aufbereiten`,
  `weg4-figur-formen`, `gehaeuse-mit-bausteinen`, `schild-zweifarbig`,
  `drucker-kalibrieren`, `aushoehlen-und-teilen`, `dose-mit-deckel`.
* Musterkatalog: `app/core/figures.py:470` `texture_tile()` und `:514`
  `_textures()` rendern alle acht aus
  `app.core.geom.texture_ops.pattern_shapes`; registriert als Abbildungen
  `texture` (`:993`) und `textures` (`:1003`), Namen in `TEXTURE_NAMES`
  (`:552`).
* Handbuchseite: `app/core/manual.py:863ff`, Seite `surfaces` „Oberflächen und
  Füllungen" — „Acht Muster stehen zur Wahl", mit `![](figure:textures)` und
  dem Satz, dass es echte Geometrie ist: „Was der Slicer bekommt, ist das, was
  Sie sehen."
* `ROADMAP.md:4394`: `- [x] **Texturmuster sichtbar** (B2). Bild und Name je
  Zeile in der Auswahl, gezeichnet aus `pattern_shapes`. Dazu eine
  Handbuchabbildung mit allen achten und ein Abschnitt auf der Startseite.`
* **Nicht** gebaut: eine Tour zur Textur (`grep -n -i "muster\|rändel\|wabe"
  app/core/tour.py` -> kein Treffer) und ein Beispielprojekt mit Textur
  (`grep -n -i "textur\|muster" app/core/examples.py` -> kein Treffer).

Stattdessen: „Neun Touren. Baustein B ist zu drei Vierteln eingelöst:
Musterkatalog mit gerenderten Kacheln, Handbuchseite und Vorschau in der
Auswahl stehen; offen bleiben die Tour zur Textur und das Beispielprojekt mit
Textur auf dem Startbildschirm."

---

## 14 — Der Bauplan kennt das Senden von G-Code nicht — §28 meint Rücklesen, §29 endet beim Slicer-Aufruf

**Urteil: stimmt.**

Beleg: `3d-agent-bauplan.md:1313` „## 28. Rückkopplung aus Slicer und
Drucker" mit den Unterabschnitten 28.1 „G-Code zurücklesen", 28.2 „Was das
ändert", 28.3 „Selbstkalibrierung" — **kein 28.4**. `:1349` „## 29. Export und
Slicer-Übergabe" endet bei „Übergabe an den Slicer: direkt per Kommandozeile
aufrufen oder die exportierte Datei öffnen".

Auch im Code ist nichts gebaut: `grep -rn "Moonraker\|OctoPrint" app/
--include=*.py` -> kein Treffer. `ROADMAP.md:4450` führt es unverändert als
offen: „- [ ] **G-Code an die Maschine senden** (B3)".

Baustein C ist damit der einzige der vier, der noch vollständig aussteht.

---

## 15 — LICENSE: Copyright (c) 2026 RS Digital, alle Rechte vorbehalten, mit zwei MIT-Ausnahmen

**Urteil: stimmt.**

Beleg: `LICENSE`, Zeile 4 „Copyright (c) 2026 RS Digital. Alle Rechte
vorbehalten." und der Abschnitt „Ausnahmen": „die Bausteinbibliothek in
`app/core/knowledge/parts/`" und „der Referenzkorpus in `tests/data/`", beide
mit eigener `LICENSE`-Datei (vorhanden:
`app/core/knowledge/parts/LICENSE`). Teil 8 bleibt damit unverändert gültig,
einschließlich der offenen Frage.

`ROADMAP.md:4435` bestätigt auch die Fortdauer von B5: „- [ ] **Sichtbarkeit.**
Solidon ist fertiger als das, worüber geschrieben wird, und unbekannt. Keine
Entwicklungsaufgabe."

---

## Zusatzbefunde beim Lesen der Umgebung

### W1 — Widerspruch im Dokument: „beide erledigt"

Die Überschrift von 2.3 lautet **„Zwei Befunde aus der Kontrolle — beide
erledigt"**. Der zweite Befund darunter sagt aber im Fettdruck das Gegenteil:
„**Das heißt: der Absturz ist selten, nicht weg.**" Überschrift und Absatz
widersprechen sich unmittelbar; wer nur die Überschrift liest, hält einen
weiterhin offenen Punkt für abgehakt — und die Roadmap führt ihn heute noch
(`:5793`, `:5913`, Messpunkt vom 19.08.2026).

Fix: Überschrift auf „einer erledigt, einer offen" ändern.

### Z1 — 3.1, Zeile „Import STEP/BREP/STL/3MF/OBJ/GLB | dieselben plus …"

**Urteil: falsch, schon am 4. August.** Solidon liest **kein** `.brep`:
`app/core/geom/mesh.py:31` führt `.stl .obj .ply .off .glb .gltf .3mf`,
`app/core/ingest/fetch.py:56` ergänzt `.step .stp .svg .dxf`. Ein
`.brep`-Lesepfad existiert nicht (`app/core/brep/` liest über
`app/core/brep/step.py` nur STEP). „Dieselben" ist an dieser einen Endung
unzutreffend.

Fix: „Import STL/3MF/OBJ/GLB/GLTF/PLY/OFF/STEP/SVG/DXF — BREP nicht."

### Z2 — 3.1, Zeile „Export STL/STEP/3MF | dieselben plus OBJ"

**Urteil: überholt.** Heute plus OBJ, **PLY und GLB**
(`app/core/export/writer.py:54`).

### Z3 — 3.1, Zeile „Zwangsbedingungen | 9 Bedingungen"

**Urteil: stimmt.** `app/core/types.py:1049` führt zehn Literale, aber
`app/core/sketch/solver.py:65` markiert `"reference"` als
`_MEASURING_ONLY` — bleiben neun bindende. Bauplan §30.1 zählt dieselben neun
auf. Kein Änderungsbedarf; die abweichende Zahl „zehn" in
`konzept-bedienung.md` Teil 4 zählt das Referenzmaß mit.

### Z4 — 1.4 „die KI-gesteuerte CAD-Bedienung ist kein Alleinstellungsmerkmal mehr"

**Urteil: unprüfbar im Repository** (Aussage über den Markt). Der interne Teil
der Aussage — Solidons MCP-Server im Fenster, jeder Fernaufruf durch
`History.apply` — steht in `app/ui/remote_server.py` und ist unverändert
tragfähig.

---

## Empfehlung in einem Satz

Vier der fünf Befunde des Dokuments sind eingeholt: **B1 (Skizze) und B4/D
(GLB) sind gebaut, B2 (Texturen) zu drei Vierteln**; allein **B3/Baustein C
(G-Code an die Maschine)** und **B5 (Sichtbarkeit)** stehen noch offen. Wer
das Dokument heute als Arbeitsgrundlage nimmt, baut dreimal etwas nach, das
schon dasteht — und Teil 7 (Reihenfolge) führt ihn dabei in genau dieser
Reihenfolge an vier erledigten Punkten vorbei.
