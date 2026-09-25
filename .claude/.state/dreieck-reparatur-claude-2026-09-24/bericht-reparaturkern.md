# Bericht Reparaturkern — Netzfehler-Erkennung und -Reparatur

Prüfer: Claude (nur lesend, keine Änderung im Baum), 24.09.2026.
Ausgang: HEAD `8ed5d6299` plus Codex' unkommittierte Änderungen
(`.claude/.state/triangle-repair-review-2026-09-24/staged.patch`), danach die
laufenden Umsetzungen der Hauptsitzung.
Sonden: `.claude/.state/dreieck-reparatur-claude-2026-09-24/sonden/`.
Interpreter: `.venv/Scripts/python.exe` (CPython 3.14.7), Windows, 32 logische
Kerne. **Zeiten sind unter Last gemessen** (parallel liefen das
Entwicklungstor mit `-n 8` und weitere Sitzungen) und damit Obergrenzen.

Kennzeichnung: **belegt** = gemessen mit Sonde oder Test; **vermutet** = aus
dem Code gelesen, nicht gemessen.

## Stand, gegen den dieser Bericht gilt

| Datei | sha1 (8) | geändert |
|---|---|---|
| `app/core/geom/repair.py` | `a6f6289f` | 18:40 |
| `app/core/ingest/loader.py` | `d5053dc2` | 18:40 |
| `app/core/scene/evaluate.py` | `4d646477` | 18:24 |
| `app/core/geom/ops.py` | `5786e5c1` | 18:33 |
| `app/core/perceive/maps.py` | `9ce825e1` | 16:56 (Codex) |
| `app/core/geom/intersections.py` | `396c920e` | unverändert seit HEAD |
| `app/core/geom/mesh.py` | `68e18272` | 18:30 |

`repair.py` durchlief während der Prüfung die Stände `37eac24e` (18:04),
`e0a6f656` (18:14), `1af26c21` (18:28), `02c5a9f7` (18:32), `a6f6289f`
(18:40). Kopien: `sonden/repair_stand_1804.py`, `repair_stand_1814.py`,
`repair_stand_neu.py` (18:28), HEAD als `repair_head.py`. Jeder Befund nennt,
an welchem Stand er gemessen ist; die Statusspalte gilt am Stand oben
(Nachmessung `sonden/s20_nachpruefung.py` → `s20b.txt`, 18:40).

Bestandstests (`test_repair.py test_repair_features.py test_maps.py
test_self_intersections.py test_ingest.py`, `-m "not windowed and not
performance"`): 18:04 — 246 bestanden (`tests-bestand.txt`); `02c5a9f7` — 252
(`tests-aktuell.txt`); **`a6f6289f` — 262 bestanden, Exit 0**
(`tests-final.txt`). Keine Fenster- oder Leistungstests gefahren.

## Kurzfazit

Codex' Kernänderung ist richtig und wichtig: Überlappende Schalen werden
jetzt vereinigt statt verrechnet, und Erfolg wird nur nach Nachprüfung
gemeldet (HEAD lieferte an zwei überlappenden Würfeln das XOR-Volumen und an
einer Kugel im Würfel einen Hohlraum, beides als „aufgelöst"). Die
Hauptsitzung hat während der Durchsicht acht meiner Befunde umgesetzt; ich
habe alle nachgemessen. Offen und am aktuellen Stand belegt sind vor allem
**Laufzeit** (Reparieren 30–80 s an großen Figuren mit der neuen Vorgabe
„Überschneidungen auflösen", Netzfehlerkarte 8–12 s) und **die neue
Faltprobe**, die große harmlose Löcher offen lässt, die vorher sauber
geschlossen wurden.

## Priorisierte Liste (offen am Stand `a6f6289f` / `d5053dc2`)

| Rang | Befund | Schwere | Ort (aktuelle Zeilen) | Kernmessung | Fix in einem Satz |
|---|---|---|---|---|---|
| 1 | **B18** *Reparieren* mit Vorgabe „Überschneidungen auflösen" dauert an großen Modellen 30–80 s, meist ohne Wirkung | hoch | `repair.py` 1997–2093 `_intersection_findings`, 1551–1611 `resolve_self_intersections`; `ops.py` 659–661 (Vorgabe `True`), 725 | Piratenschiff 1,22 Mio.: 77,1 s → `unresolved`; Spiderman 885 k: 28,6 s → `unresolved`; Mausoleum 2,33 Mio.: 52,1 s → nichts zu tun; Besenhalter 60 k: 9,6 s → nichts zu tun | Nur vereinigen, wo Schnittpaare zwischen verschiedenen Schalen oder koplanar liegen; Nachprüfung nur im alten Schnittbereich; Fortschritt melden |
| 2 | **B14** Die Faltprobe lässt große harmlose Löcher offen, die vorher schnittfrei geschlossen wurden | hoch | `repair.py` 1099 (`_folds` für Ohren **und** Fächer), 842 `_loop_triangles` (Kantenregel erst nach dem Ohrenschneiden, 1100 ff.) | Kugelschale mit gezacktem Rand: HEAD dicht, jetzt `still_open`; Katze (452 k): 4 Ringe à 4–6 Kanten bleiben offen | Kantenregel ins Ohrenschneiden ziehen — in der Sonde belegt: 92 Ohren, dicht, einheitlich, 0 Schnitte |
| 3 | **B3-Rest** Netzfehlerkarte seit dem größenabhängigen Budget 8–12 s; Budget zählt rohe Sweep-Paare | hoch | `maps.py` 872–931; `repair.py` 1459–1476; `intersections.py` 267 | Besenhalter 8,2 s, Spiderman 12,2 s (136 Funde) — §31 gibt Karten 3 s | Karte mit Zeitbudget und Teilgewissheit je Scheibe; Budget an gefilterten Paaren messen |
| 4 | **B6** `SETTLED_BY` streicht keinen Reparatur- und keinen Teilebefund | mittel | `evaluate.py` 1188–1214 | `ingest.multiple_components` bleibt bei 1 Endteil (`s07c`); `repair.still_open` des Imports bleibt, nachdem *Kleinstteile entfernen* den Körper geschlossen hat (`s07d`) | Zustandsbefunde am Endstand fragen (wie `check_placement`) oder Tabelle ergänzen |
| 5 | **B13** Lochfüllung quadratisch, Abbruch greift erst danach; Import ohne Abbruch | mittel | `repair.py` 842–910 `_loop_triangles`; Abbruch nur 1573, 1682, 1858; `loader.normalise` 861 ohne `cancelled` | gewellter Ring 8 000 Kanten 12,75 s; Abbruch nach 0,5 s angefordert, gegriffen nach 11,9 s | Ear-Clipping mit Reflexmenge, Abbruch je Ring; `load` reicht `ctx.cancelled` durch |
| 6 | **B12** `fix_winding` beim Import 13–23 s an einem großen, uneinheitlich gewickelten Netz | mittel | `loader.py` 1109 | Katze 452 k: 23,2 s (heute unter Last), 13,4 s früher; Import gesamt 28,9 s | eigene Paritätsausbreitung über die Kantentabelle statt trimeshs Breitensuche; Fortschritt/Abbruch |
| 7 | **B10** Füllflächen erben den Slot einer geerbten Diagonale statt ihrer eigenen Randkante | niedrig–mittel | `repair.py` 1043–1047, 1125–1139 | zweifarbiges Loch: 4 von 16 Fülldreiecken mit fremdem Slot (HEAD: 1 von 22) | Randkanten und geerbte Diagonalen getrennt führen, Randkante zuerst |
| 8 | **B19** `turn_shells_outward` prüft jeden Hohlraum einzeln gegen die ganze Außenschale | niedrig–mittel | `repair.py` 222–306; beim Import `loader.py` 1111 | 300 Hohlräume in 331 k Dreiecken: 7,2 s | Strahltests bündeln oder die Schalenhierarchie der Hohlraumerkennung nutzen |
| 9 | **B4-Rest** Eigenkreuzung einer einzigen Schale bekommt „Überschneidungen auflösen" angeboten und endet `unresolved`; Satz „Teile des Modells überschneiden sich" an einem Teil | niedrig–mittel | `repair.py` 2040–2050, 1522–1543 | Achterröhre (1 Schale): Angebot `resolve_intersections`, danach `unresolved` | Vorprüfung um „Paare zwischen verschiedenen Schalen oder koplanar" ergänzen (wie B18) |
| 10 | **B9-Rest** positive Schale in positiver Schale (falsch gewickelter Hohlraum oder Doppelteil) ohne jeden Befund | niedrig–mittel | `repair.py` 222–306 | Würfel mit falsch herum gewickelter Innenschale: kein Befund, Volumen 9 000 statt 7 000 | nicht raten (Regel 21), aber melden, mit *Stellen zeigen* |
| 11 | **B16/B17** Zwillinge und RM-187: Volumenvorzeichen am Ursprung, `np.einsum` in Entscheidungen, Weg fehlt in `_WAYS` | niedrig | `mesh.py` 570–582; `repair.py` 209–219, 1546–1548; `intersections.py` 297–428 | 1-mm-Würfel bei 10⁸ mm wird umgestülpt; unter Plattformrauschen an 5 Fällen bitgleich | ein körpernahes, elementweises Volumen für alle Entscheidungen; `repair_selfint` in `_WAYS` |
| 12 | **B15-Rest** doppelte Sätze Import/Reparatur | niedrig | `loader.py` 999, 1063; `repair.py` 1692, 1739 | am Korpus 41 × `weld_skipped` doppelt, 23 × `degenerate_kept` doppelt (Stand 18:04) | eine Familie, ein Code, `_without_repeats` greift |
| 13 | **B5-Rest** am nicht orientierbaren Netz „Außenseiten angeglichen" neben „zeigen gegeneinander" | niedrig | `repair.py` 1858–1886 | Röhre mit gespiegelter Naht: beide Befunde zugleich | `normals_flipped` nur, wenn das Ergebnis einheitlich ist |

**Behoben während der Durchsicht (nachgemessen, `s20b.txt`):** B1 (Codex),
B2 (Import stellt die Außenfrage am geschlossenen Netz: +8 000 statt −8 000),
B3-Hauptteil (Besteckkorb ohne Warnung, Bohrhalter wird aufgelöst), B5
(Naht dicht und einheitlich), B7 (keine Nullvolumen-Taschen mehr), B8 (Ort
und *Offen lassen* an der großen Öffnung), B9-Hauptteil (freistehend
umgestülpte Schale in Reparatur **und** Import), B11-Hauptteil
(`ingest.not_watertight` nur noch ohne gelaufene Reparatur), B15-Hauptteil
(Verben, „noch", Gründe, Schwere).

## Antworten auf die Prüffragen des Auftrags

- **`unify_normals` über die Eckenreihenfolge statt das Volumen** (Codex):
  richtig — eine gedrehte Fläche kann denselben Volumenbeitrag haben (Codex'
  Test belegt das). Die Außenfrage lief zunächst über `enclosed_volume`
  (Ursprung, `einsum`, B16/B17); heute über `turn_shells_outward` je Schale
  (B9 behoben, B19 Laufzeit, B16 Ursprung bleibt).
- **`enclosed_volume`**: dasselbe Integral wie trimesh, am Ursprung bezogen.
  Bis 10⁷ mm Abstand richtig, bei 3·10⁷ ein 1-mm-Würfel 0,979, bei 10⁸
  −5,5·10⁷ (`s15_fern.py`). Selten, aber es entscheidet über Umstülpen und
  Vereinigen (B16).
- **`resolve_self_intersections` mit `face_components`-Schalen**
  (`s01_durchdringung.py`): getrennte überlappende Außenschalen → richtig
  vereinigt (14 272 mm³). Hohlkörper mit Innenschale **und** überlappender
  Außenschale → unverändert, `unresolved` (die negative Schale hat kein
  positives Volumen, Absicht, Grund `cavity`). **Nur eine Schale** mit echter
  Selbstkreuzung (`[mesh, mesh]`) → unverändert, `unresolved`; mit
  koplanarer/deckungsgleicher Überlagerung → aufgelöst, Volumen bitgleich
  (Kofferschale B, 宠物便便器). **Invertierte Innenschale** → `_has_volume` je
  Schale falsch → unverändert.
- **`fill_boundary_loops`, `neighbour_of`/`added_from`/`setdefault`**: die
  Übernahme über `added_from` und `slots[added_from]` ist technisch richtig
  (Farben und Slots reisen), die **Wahl** des Nachbarn nicht (B10).
- **Abbruch**: `repair()` fragt an zwei Stellen (1682, 1858),
  `resolve_self_intersections` an einer (1573), die Durchdringungssuche je
  Block; Verschweißen, Taschen, Verzweigungen,
  Vernähen, Lochfüllung, `fix_winding`, `turn_shells_outward` und die native
  Vereinigung sind nicht unterbrechbar; der Import nimmt gar keinen Abbruch an
  (B13, B12).
- **Reihenfolge**: in `repair()` richtig (Verschweißen → Taschen → leere
  Dreiecke → Verzweigungen → Nähte → Löcher → Außenseiten → Überschneidungen).
  Im Import war sie falsch (Außenfrage vor dem Schließen, B2) — behoben.
- **Befundtexte / Regel 17**: Warnungen tragen heute Handlungen oder stehen in
  `panels.FINDING_ACTIONS`; offen ist B15-Rest und B5-Rest.
- **Doppelte oder widersprüchliche Befunde**: B6 (über Schritte), B15-Rest
  (Import/Reparatur), B5-Rest (im selben Lauf).
- **Plattformgleichheit (RM-187)**: *Reparieren* mit Auflösung an fünf Fällen
  unter `platform_noise` bitgleich (`s11_plattform.py`); Regelverstöße bleiben
  (B17).
- **Leistung an ~1 Mio. Dreiecken**: vollständige Durchdringungssuche 12,5 s
  (885 k), 17,9 s (1,22 Mio.), 27,0 s (2,33 Mio.) — `s12.jsonl`;
  *Reparieren* mit den heutigen Vorgaben 28,6 / 77,1 / 52,1 s — `s22.jsonl`;
  Netzfehlerkarte 12,2 s (885 k) — `s21_karte_zeit.py`.
- **Determinismus**: kein Zufall im Pfad; zwei Läufe gleich (in `s11` ruhig
  gegen verrauscht gleich).
- **Zwillinge**: B16.
- **`SETTLED_BY`**: B6 — die neuen Codes `repair.self_intersections_*`
  werden von keinem Folgeschritt gestrichen; mit der Vorgabe `True` entsteht
  `detected` nur noch an Altschritten (Migration 34→35 behält „aus").

## Korpus (`F:\3D Dateien`)

`sonden/s02_korpus.py` → `s02.jsonl`, 172 Dateien, 485 Körper, Import +
*Reparieren* (Stand 18:04; die Import- und Füllbefunde haben sich seither
geändert, die Durchdringungszahlen gelten für das alte Budget):

- Kein Absturz, kein Körper nach der Reparatur schlechter (offen +
  verzweigt), keine Teilezahländerung.
- Nach dem Import dicht, aber uneinheitlich: `Naht-zusammengesetzt.stl`,
  `Gaehnende-Katze` (beide inzwischen anders, B5/B14).
- Die Durchdringungssuche kostete 252 von 330 s Reparaturzeit; 120 Körper
  „unvollständig" (B3).
- Benannte Kundendateien (Stand 18:04): `mushroom.stl` (28 Dreiecke), `peg.stl`
  (504) — sauber, nichts zu tun. `pirate+ship+with+sails_stls`: Zylinder
  `obj_8/11/2/14` mit Durchdringungen, mit Auflösung gelöst (2 → 1 Teil,
  Volumen gleich); Segel und Baugruppen `incomplete`. `spiderman…obj_1`
  (885 570): `incomplete` (heute vollständig: 136 Funde, B3/B18).
  `HydroBowl … washing bowl v1.stl` (215 072): `incomplete`.
  `Mausoleum Dragon.3mf` (2 330 374): Import 9,9 s, Reparieren 11,2 s (heute
  52,1 s, B18). `image_00001_.glb` (325 244, TripoSG): `weld_skipped`,
  `degenerate_kept`, `incomplete`.

## Befunde im Einzelnen

### B1 — Mehrschalen-Vereinigung ist richtig (Codex-Änderung bestätigt)

- Status: **gilt** (`s20b`: 14 272). Schwere: — (positiv, belegt)
- Ort: `repair.py` 1551–1611 `resolve_self_intersections`
- Messung (`s01_durchdringung.py`, `s01.txt`, am Stand 18:14 wiederholt
  `s01_neu.txt`), Volumen körpernah integriert:

| Fall | vorher | NEU | HEAD |
|---|---|---|---|
| A zwei überlappende Würfel 20 mm, Versatz 8 (2 Schalen) | 16 000 | **14 272**, 0 Restschnitte | 12 544 (XOR), 20 Restschnitte, „aufgelöst" |
| D wie A + Innenschale | 15 992 | unverändert + `unresolved` | 12 536, „aufgelöst" |
| G Kugel r = 4 ganz im Würfel (2 positive Schalen, kein Schnitt) | 8 265,8 | unverändert, kein Befund | **7 735,1** — als Hohlraum ausgeschnitten, „aufgelöst" |
| B Achterröhre (1 Schale, echte Selbstkreuzung) | 821,7 | unverändert + `unresolved` | 788,0, 73 Restschnitte, „aufgelöst" |
| E Achterröhre mit innerer Röhre (Hohlkörper) | 730,4 | unverändert + `unresolved` | 704,8, 553 Restschnitte, „aufgelöst" |
| F zwei überlappende Würfel, einer umgestülpt | 0,0 | `skipped` | `skipped` |

- Kundensicht: Der alte Weg meldete Erfolg und lieferte falsches Volumen.
- Zurückgenommen: meine erste Vermutung „eine Einzelschale wird nie
  aufgelöst" — koplanare Überlagerungen einer Schale löst `[mesh, mesh]`
  (Kofferschale B, 宠物便便器 实体1, Volumen bitgleich). Und: Codex' Ersatz des
  Tests `test_the_step_runs_last_so_that_it_can_run_at_all` ist berechtigt —
  HEAD meldete an `generated_figure.stl` „aufgelöst", obwohl nach dem Füllen
  **null** Schnitte bestanden; die Vereinigung hatte nur eine Nullvolumen-Tasche
  geschluckt (`s01.txt` Fall C).

### B2 — Import schloss ein offenes Netz und ließ es umgestülpt

- Status: **behoben** am Stand `d5053dc2` (`loader.py` 1159 `normals=True` in
  Schritt 4b; `s20b`: STL-Suppe +8 000, offener umgestülpter Würfel +8 000).
- Schwere: hoch (belegt)
- Ursprünglicher Fall (`s04_umstuelpung_import.py`, `s04.txt`): unterteilter
  Würfel als STL-Dreieckssuppe, Dreieck 0 falsch gewickelt, ein Dreieck
  fehlt → Import dicht, einheitlich, Volumen **−8 000**, Befund „korrigiert".
  Ursache: `fix_winding` am offenen Netz nach falschem Bezugsdreieck,
  `fix_inversion` nur am vorher dichten Netz, Lochfüllung mit `normals=False`.
- Testidee (falls noch nicht angelegt): genau dieser Fall in `test_ingest.py`
  mit `MeshData.volume > 0`.

### B3 — Durchdringungsbudget: am Stand 18:04 Warnung im Normalfall, heute zu lange Karte

- Status: **Hauptteil behoben**, **Rest offen (hoch)**: Budget heute
  `max(2 Mio., 512 · Dreiecke)` Sweep-Paare (`repair.py` 1459–1476). Am
  aktuellen Stand: Besteckkorb Modul B (8 672) ohne Befund in 1,76 s,
  drill-holder Körper 1 wird aufgelöst (4 Teile, 5,1 s). **Kehrseite:** Die
  Netzfehlerkarte rechnet jetzt praktisch vollständig — Besenhalter (59 740)
  **8,2 s**, Spiderman (885 570) **12,2 s** mit 136 Funden (`s21_karte_zeit.py`,
  Stand `02c5a9f7`; `maps.py` seither unverändert, `repair.py` am Stand
  `a6f6289f` nicht erneut gemessen). §31 gibt der teuersten
  Karte drei Sekunden; die Stützkarte bricht dort ab
  (`SUPPORT_MAP_BUDGET_SECONDS`).
- Ort: `maps.py` 872–931 (`self_intersection_check` 906, `nan` 912);
  `intersections.py` 267 (gezählt werden **rohe** Sweep-Paare vor dem
  Achsenfilter).
- Messung am Stand 18:04 (`s05_suchbudget.py`, `s05.txt`; Korpus):
  `incomplete` an 120 von 485 Körpern, an allen 60 über 100 000 Dreiecken;
  82 davon ohne jeden Fund; 67 Körper hätten sonst „nichts zu reparieren"
  erhalten; die richtige Vereinigung des Bohrhalters (ohne Budget geprüft
  schnittfrei, `s06b_bohrhalter_voll.py`) wurde verworfen.
- Größenreihe (`s12_budget_groessen.py`, `s12.jsonl`):

| Körper | Dreiecke | Sweep-Paare | gefilterte Paare | je Dreieck | vollständig | Funde |
|---|---|---|---|---|---|---|
| Besteckkorb Modul B | 8 672 | 2,70 Mio. | 0,82 Mio. | 94 | 1,70 s | 0 |
| Besenhalter | 59 740 | 22,1 Mio. | 3,23 Mio. | 54 | 8,94 s | 0 |
| Baum ohne Schale | 166 400 | 8,43 Mio. | 1,31 Mio. | 7,9 | 3,10 s | 0 |
| Segel obj_5 | 277 460 | 6,93 Mio. | 1,81 Mio. | 6,5 | 3,64 s | 0 |
| Spiderman | 885 570 | 49,1 Mio. | 5,91 Mio. | 6,7 | 12,5 s | **136** |
| Piratenschiff obj_15 | 1 223 838 | 60,6 Mio. | 8,60 Mio. | 7,0 | 17,9 s | **15** |
| Mausoleum Dragon | 2 330 374 | 80,6 Mio. | 14,45 Mio. | 6,2 | 27,0 s | 0 |

  Kosten gleichbleibend 1,9–2,8 µs je gefiltertem Paar. Der Besenhalter
  (Splitterdreiecke) braucht mit 512 je Dreieck 22 von 30,6 Mio. Paaren und
  läuft damit ganz durch.
- Fix für den Rest: (1) Karte mit Zeitbudget (3 s) und Teilgewissheit — die
  Flächen, deren Paare vollständig durchlaufen sind (beim einfachen Sweep alle
  Einträge vor dem Abbruchindex, bei Scheibenplänen je Scheibe), gelten als
  geprüft statt alles `nan`. (2) Das Budget an den **gefilterten** Paaren
  messen; dann reichen `max(2 Mio., 12 · Dreiecke)` für jedes organische Netz
  der Tabelle, und CAD-Splitter kosten nicht das Fünfzigfache. (3) Karte und
  Reparatur fragen denselben Zähler — beide mitziehen.
- Testidee: Karte an einem Körper mit langen Splittern (Besteckkorb) unter
  3 s mit Teilgewissheit statt ganz „unbekannt" (Release-Leistung).

### B4 — Der Rat „Überschneidungen auflösen" führte oft in eine Sackgasse

- Status: **teilweise behoben** (`repair.py` 1522–1543
  `_intersections_resolvable`, 2040–2082): Rat nur ohne Hindernis, Gründe
  getrennt (`open`, `winding`, `flat`, `cavity`), neue Handlung
  `RESOLVE_INTERSECTIONS`. **Rest offen:** Die Eigenkreuzung einer einzigen
  Schale besteht die Vorprüfung, bekommt das Angebot und endet `unresolved`
  (`s20b`: Achterröhre). Mit der Vorgabe `True` betrifft das Angebot heute nur
  Altschritte; der unnütze Rechenweg bleibt (B18). Der Satz „Teile des
  Modells überschneiden sich" (2045) passt nicht zu einem Teil, das sich
  selbst kreuzt.
- Messung am Stand 18:04 (`s02.jsonl`): Von 70 Körpern mit `detected` endete
  das Befolgen bei 15 im Erfolg, bei 55 in `unresolved`/`skipped`.
- Fix: in der Vorprüfung verlangen, dass Schnittpaare zwischen
  **verschiedenen** Schalen liegen oder koplanar überlagern (dafür eine
  Paarauskunft aus `intersections.crossing_faces`); Satz für die
  Eigenkreuzung „Die Oberfläche kreuzt sich selbst".
- Testidee: Achterröhre (`s01_durchdringung.tube_along(figure_eight())`) —
  `repair()` bietet `resolve_intersections` nicht an und ruft `boolean` nicht.

### B5 — Die Verzweigungsauflösung erzeugte Wicklungskonflikte

- Status: **behoben** an der Naht (`_resolve_branching_once` 1224 ff. wählt
  jetzt die gegenläufige Partnerfläche; `s20b`: Import dicht, einheitlich,
  66 359,5 mm³). Neuer Befund `repair.normals_inconsistent` (1878) meldet
  verbleibende Konfliktkanten. **Rest (niedrig):** Am geschlossenen, nicht
  orientierbaren Netz (`s10_klein.py`, Röhre mit gespiegelter Naht) stehen
  `normals_flipped` („Die Außenseiten wurden angeglichen.") und
  `normals_inconsistent` („An 12 Kanten zeigen die Außenseiten
  gegeneinander.") nebeneinander, das Volumen springt −13 803 → 69,6 mm³.
- Ursprünglicher Fall (`s06_naht_bohrhalter.py`, `s06c_naht_roh.py`):
  `Naht-zusammengesetzt.stl` roh einheitlich, nach Import uneinheitlich,
  Reparieren meldete „korrigiert" und verlor 6,1 % Volumen.
- Fix für den Rest: `normals_flipped` nur, wenn das Ergebnis einheitlich ist;
  sonst allein `normals_inconsistent`. Die Netzfehlerkarte kennt
  gegeneinander zeigende Kanten weiter nicht (`maps.DEFECT_LEVELS`) — eine
  vierte Stufe wäre die Stelle, die *Stellen zeigen* dort sucht.

### B6 — `SETTLED_BY` streicht keinen Reparatur- und keinen Teilebefund

- Status: **offen (mittel)**, belegt am aktuellen Stand.
- Ort: `evaluate.py` 1188–1214 (`SETTLED_BY`), 1352 `_without_settled`.
- Messung (`s07c_aktuell.py`, `s07c.txt`; `s07d_kleinteile.py`), echte
  Dokumente über `History` + `evaluate`:
  - `broken_selfint.stl`: *Laden* → *Reparieren* → *Reparieren*: Endkörper
    **1** Teil, im Bericht weiter op1 `ingest.multiple_components` („Das
    Modell besteht aus mehreren Teilen", in der Oberfläche mit *In Einzelteile
    zerlegen*).
  - `generated_figure.stl`: *Laden* → *Reparieren* mit *Kleinstteile
    entfernen*: Endkörper dicht, 1 Teil — im Bericht bleibt op1
    `repair.still_open` als **Warnung** („Eine offene Stelle ließ sich nicht
    sicher schließen.").
  - Am Stand 18:04 zusätzlich: `repair.self_intersections_detected` neben
    `repair.self_intersections` (heute durch die Vorgabe seltener).
- Fix: Zustandsaussagen („mehrere Teile", „offen", „überschneidet sich") wie
  `check_placement` einmal am Endstand fragen (die Regel dazu steht in
  `operationen.md`, „was aus einem Verhältnis entsteht"); zumindest die
  Tabelle ergänzen: `repair.still_open`/`still_branching` ←
  `repair.holes_filled`, `repair.components_removed`,
  `repair.branching_resolved`; `repair.self_intersections_*` ←
  `repair.self_intersections`; `ingest.multiple_components` ← alles, was die
  Teilezahl auf 1 bringt (besser: Endstand).
- Testidee: beide Ketten oben in `test_evaluation.py`; Endbericht ohne
  `multiple_components` bzw. ohne `still_open`.

### B7 — Die Lochfüllung machte aus losen Einzeldreiecken Nullvolumen-Taschen

- Status: **behoben** (`repair.py` 975 `_flat_fills`, Befund
  `repair.no_thickness` 1906). `s20b`: `generated_figure.stl` bleibt an seinem
  losen Dreieck offen (3 Kanten), Volumen 5 033,19; keine Tasche mehr.
- Ursprünglicher Fall (`s03.txt` 3a): zweites Teil mit 2 Dreiecken und
  Volumen 0,0, vom Füller gebaut; im Bericht „sehr kleine Einzelteile".
- Folge am aktuellen Stand: siehe B6 (der offene Rest bleibt als Warnung
  stehen, auch nachdem er entfernt wurde).

### B8 — „Eine große Öffnung wurde geschlossen" ohne Ort und ohne Knopf

- Status: **behoben** (`repair.py` 1831–1840: `location` der größten
  Öffnung, `LEAVE_OPEN`; `loader.py` 1198–1212 verschiebt den Ort beim
  Aufsetzen mit). `s20b`: `broken_open.stl` → Ort (6, 2, −2),
  `leave_open`.

### B9 — Ein umgestülptes Teil oder eine falsch gewickelte Innenschale: „nichts zu reparieren"

- Status: **Hauptteil behoben** (`repair.py` 222–306 `turn_shells_outward`,
  im Import `loader.py` 1103–1111). `s20b`: zwei getrennte Würfel, einer
  umgestülpt → beide +8 000 (Reparatur und Import); richtiger Hohlkörper
  bleibt (8 000, −1 000). **Rest offen (niedrig–mittel):** positive Schale in
  positiver Schale (Würfel mit falsch herum gewickelter Innenschale) — kein
  Befund, Volumen 9 000 statt 7 000; die Funktion rät richtig nicht, sagt aber
  nichts (Regel 21 verlangt Fragen, nicht Schweigen).
- Grenzfälle richtig (`s23_schalen.py`): Hohlraum, der die Außenwand berührt,
  bleibt; umgestülptes Teil im Maul eines U wird gedreht.
- Fix für den Rest: Befund „Ein Teil liegt vollständig in einem anderen —
  Hohlraum falsch herum oder doppeltes Teil?" mit *Stellen zeigen*.

### B10 — Füllflächen erben den Slot einer geerbten Diagonale

- Status: **offen (niedrig–mittel)**, belegt am aktuellen Stand (`s20b`: 4
  von 16).
- Ort: `repair.py` 1043–1047 (`neighbour_of` aus Randkanten), 1125–1139
  (`next(...)` über die drei Kanten in Eckenreihenfolge, dann
  `setdefault` der neuen Diagonalen).
- Messung (`s09_farbe_am_loch.py`, `s09.txt`): dreifach unterteilter Würfel,
  Loch 8 × 8 mm oben, links Slot 1/rot, rechts Slot 2/blau → 4 Fülldreiecke
  tragen einen Slot, den keine ihrer eigenen Randkanten trägt (z. B. x = +2,50,
  einziger Randnachbar Slot 2 → Slot 1). HEAD an derselben Eingabe: 1 von 22.
- Ursache: Eine vom Vorgängerdreieck geerbte Diagonale steht vor der eigenen
  Randkante in der Reihenfolge und gewinnt.
- Kundensicht: Farbnaht quer durch den Deckel, im Druck ein Wechsel mitten in
  der Fläche.
- Fix: zwei Tabellen — Randkante (unveränderlich) vor geerbter Diagonale vor
  `fallback`; bei zwei verschiedenen Randnachbarn die längere Kante. Farben
  folgen `origins` mit.
- Testidee: der `s09`-Körper — kein Fülldreieck mit Randkante trägt einen
  Slot, den keine seiner Randkanten trägt.

### B11 — Befundschleife: Der Import empfahl die Reparatur, die er schon gefahren hatte

- Status: **Hauptteil behoben** (`loader.py` 1233: `ingest.not_watertight`
  nur, wenn Schritt 4b nicht lief — `mended_here`). **Rest** geht in B6 auf
  (Import-`still_open` bleibt nach späterer Heilung stehen).
- Ursprüngliche Schleife (`s07b_naht_bericht.py`, Stand 18:14): drei Sätze über
  dieselben Ränder im Ladeschritt, danach „Aktivieren Sie …", danach
  „braucht einen geschlossenen Körper …".
- Hinweis zum Rest: Ist der offene Rest nur ein loses Kleinstteil
  (`generated_figure.stl`, Flaschenhalter `Bottle-holder-v3 v5`), stehen
  `still_open` und `ingest.small_components` nebeneinander; der Weg ist
  *Kleinstteile entfernen* (`REMOVE_SMALL_PARTS`, in `s07d` belegt). Der Satz
  von `still_open` könnte das sagen, wenn alle offenen Ränder in Kleinstteilen
  liegen.

### B12 — `fix_winding` beim Import 13–23 s, ohne Fortschritt und Abbruch

- Status: **offen (mittel)**, belegt am aktuellen Stand.
- Ort: `loader.py` 1109 (`trimesh.repair.fix_winding` am offenen,
  verschweißten Netz); `repair.py` 201 (dasselbe in `unify_normals`, dort
  inzwischen billig, weil `fix_winding` an einem einheitlichen Netz sofort
  zurückkehrt).
- Messung: `Gaehnende-Katze_Figur_material.3mf` (452 316 Dreiecke):
  `fix_winding` **23,2 s** im Import (heute unter Last), 13,4 s früher;
  `is_winding_consistent` davor 0,15 s; Import gesamt 28,9 s; zweiter
  `fix_winding` in 4b 0,35 s.
- Fix: eine Paritätsausbreitung über `scipy.sparse.csgraph` auf der
  vorhandenen Kantentabelle (`_edge_table`) statt trimeshs Python-Breitensuche;
  mindestens `progress` davor und danach, damit der Balken nicht steht.
- Testidee: Release-Leistung an einem uneinheitlich gewickelten Netz mit
  400 k Dreiecken.

### B13 — Lochfüllung quadratisch, Abbruch greift erst danach; Import ohne Abbruch

- Status: **offen (mittel)**. `_loop_triangles` ist seit 18:14 wortgleich
  (Diff gegen `repair_stand_1814.py`), die Abbruchpunkte sind am aktuellen
  Stand gezählt; die Laufzeit ist am Stand 18:14 gemessen.
- Ort: `repair.py` 842–910 `_loop_triangles` (je Versuch eine Python-Liste
  über alle Ringecken und ein Feld über alle Ecken → O(n²)); `repair()` fragt
  den Abbruch nur bei 1682 und 1858; `loader.normalise` (861) kennt keinen
  Abbruch, `ingest/ops.load` reicht `ctx.cancelled` nicht weiter.
- Messung (`s08_grosse_loecher.py`, `s08.txt`), offener Zylinder, ein Ring:
  1 000 Kanten 0,20 s · 2 000 0,64 s · 4 000 2,45 s · 8 000 rund 0,14 s
  (Ohren scheitern, Fächer) · **8 000 gewellt 12,75 s**. Abbruch nach 0,5 s
  angefordert, gegriffen nach **11,9 s**.
- Kundensicht: Ein Scan mit offenem Boden blockiert Import und Reparieren ohne
  Rückmeldung; *Abbrechen* wirkt erst am Ende.
- Fix: Ear-Clipping über eine verkettete Liste mit Reflexmenge (Innenprobe
  nur gegen Reflexecken); Abbruch je Ring und je 1 000 Ohren; `normalise(...,
  cancelled=)` und `load` reicht das Token durch (§15.6).
- Testidee: Kerntest — ein Signal, das ein Rückruf während der Lochfüllung
  setzt, bricht vor dem nächsten Ring ab; Release-Leistung: gewellter Ring
  8 000 Kanten unter 1 s.

### B14 — Die Faltprobe lässt harmlose große Löcher offen

- Status: **offen (hoch)**, belegt am aktuellen Stand (`s20b`: Schale
  `still_open`).
- Ort: `repair.py` 1099 (`_folds(reachable[attempt], normal)` verwirft Ohren
  **und** Fächer), 842 `_loop_triangles` (wählt Ohren ohne Blick auf schon
  belegte Kanten; die Kantenregel prüft erst die fertige Füllung, 1100 ff.).
- Messung (`s13_nachfassen_falten.py`, `s13b_vergleich.py`, `s13c`, `s13d`):

| Loch | HEAD | Stand 18:04 | Stand 18:14 bis heute |
|---|---|---|---|
| Kugel r = 10 unter dem Äquator abgeschnitten (94 Kanten, z −2,39…−1,61) | dicht, 0 Schnitte | dicht, 0 Schnitte | **offen**, `still_open` |
| Halbkugel exakt am Äquator (96 Kanten) | dicht | dicht | dicht |
| Zylinderfenster über ~240° | dicht, aber Membran quer durchs Innere (Volumen 7 656 statt ≈ 9 425) | dasselbe | offen — **richtig** |
| Loch über eine Kante, über eine Ecke, Kugelkappe | dicht | dicht | dicht |
| T-Stöße mit mehreren Punkten auf einer Kante (`STITCH_ROUNDS`) | — | — | vernäht, 0 Nullflächen |

- Ursache (`s13c`): Die Ohren wären gültig (92, keines rückwärts), scheitern
  an 4 Diagonalen, die schon zwei Flächen tragen; der Fächer hat 4 rückwärts
  zeigende Dreiecke, `_folds` verwirft ihn.
- Am Korpus (`s16_import_neu.py`, `s24_ringe_offen.py`): `Gaehnende-Katze`
  kommt offen aus dem Import — 4 kleine Ringe (4–6 Kanten, 0,3–0,9 mm,
  Unebenheit ≤ 0,04 mm), Ohren an 2–4 belegten Kanten gescheitert, Fächer
  gefaltet. Am Stand 18:04 waren dieselben Ringe mit gefalteten Fächern
  geschlossen — und diese Falten machten das Netz uneinheitlich (B2, zweite
  Gestalt). Beides löst dieselbe Änderung.
- Kundensicht: Schalen, abgeschnittene Scans, Modelle mit offenem Boden kommen
  seit 18:14 offen heraus; das widerspricht „alles bei der Reparatur beheben"
  (22.09.).
- Fix (in `s13d_ohren_mit_sperre.py` belegt): ein Ohr, dessen neue Diagonale
  schon zwei Flächen trägt, wird übersprungen wie ein reflexes Ohr. Ergebnis
  an der Schale: 92 Ohren, dicht, einheitlich, **0 Schnitte**, 1 419,3 mm³
  (HEAD: 1 460,7 mit umgeklappten Splittern). `_folds` bleibt für den Fächer.
- Testidee: Icosphäre (Unterteilung 4) ohne alle Dreiecke mit Mitte z > −2 →
  dicht, `self_intersecting_faces == ()`; Gegenfall Zylinderfenster bleibt
  offen.

### B15 — Befundtexte

- Status: **Hauptteil behoben** (heute „Überschneidungen", „vorzeitig beendet;
  es kann welche geben" als Hinweis, Gründe getrennt, „Leere Dreiecke",
  „Lücken an Nähten", Kleinstteile als Hinweis). **Rest offen (niedrig):**
  Import und Reparatur sagen dieselbe Nicht-Handlung mit zwei Codes —
  `ingest.weld_skipped` (`loader.py` 999) und `repair.weld_skipped`
  (`repair.py` 1692), `ingest.degenerate_kept` (1063) und
  `repair.degenerate_kept` (1739). Am Korpus (Stand 18:04) standen beide an 41
  bzw. 23 Körpern im selben Bericht; `_without_repeats` greift bei
  verschiedenen Codes nicht.
- Fix: eine Befundfamilie mit gemeinsamem Code oder eine Familienregel in
  `_without_repeats` (`evaluate.py` 1380).

### B16 — Zwillinge: dieselbe Auskunft mehrfach hergeleitet

- Status: **teilweise zusammengelegt** (Import und Reparatur fragen die
  Außenseite heute beide über `turn_shells_outward`). **Offen (niedrig):**

| Auskunft | Stellen | Befund |
|---|---|---|
| „positives geschlossenes Volumen?" | `repair._has_volume` 1546 (`MeshData.volume` → `mesh.enclosed_volume` 570, Ursprung, `einsum`), `repair._shell_volumes` 209 (Ursprung, elementweise), `boolean._kernel`/`_plausible` (`_signed_volume`, körpernah, elementweise) | **ungewollt, gedriftet**: 1-mm-Würfel bei 10⁸ mm (`s15_fern.py`, am aktuellen Stand in `s20b` wiederholt) → `turn_shells_outward` stülpt einen richtigen Würfel um (lokal danach −1,0). Zusammenlegen: ein körpernahes Volumen für alle Entscheidungen. |
| „macht ein Schritt das Netz schlechter?" | `repair._tears_it_further` 1622 (Summe offen + verzweigt); `loader.normalise` Schritt 2/3 („war dicht und ist es nicht mehr") | **ungewollt, gedriftet**; `geom/CLAUDE.md` Z. 455–458 behauptet „entspricht `ingest.loader.normalise`" — stimmt nicht |
| „welche Kanten sind offen/verzweigt" | `repair._edge_table` 2111; `maps.defect_map` 892 (`group_rows` + Python-Schleife) | **ungewollt, klein**: 0,57 gegen 0,27 s bei 885 570 Dreiecken (`s14_karte_kanten.py`) |
| „kleines Teil?" | `loader._count_components` 1345, `repair.remove_small_components` 1425 | gehalten über `SMALL_COMPONENT_SHARE` — in Ordnung |

### B17 — RM-187: `np.einsum` in Entscheidungen, Weg fehlt in `_WAYS`

- Status: **offen (niedrig)**. Regelverstoß belegt am Code, Auswirkung nicht
  getroffen.
- Ort: `mesh.py` 581 (`enclosed_volume`, entscheidet über `_has_volume` und
  damit über das Vereinigen); `intersections.py` 297, 346–347, 370, 386, 390,
  428 (`crossing_pairs` entscheidet seit Codex, ob ein Vereinigungsergebnis
  angenommen wird). `kern.md`: „`np.einsum` nicht (FMA auf ARM)".
- Messung (`s11_plattform.py`, `tests.test_platform_identity.platform_noise`):
  *Reparieren* mit Auflösung an `broken_selfint`, Kofferschale B, drill-holder
  Körper 1, `generated_figure`, `partially_open` — ruhig und verrauscht
  bitgleich (Stand `e0a6f656`). Grenzfälle auf `EPS_GEOM` sind damit nicht
  ausgeschlossen.
- Fix: elementweise Summen statt `einsum`; den Weg „ausdrückliches Reparieren
  mit Überschneidungen" als `repair_selfint` in
  `tests/test_platform_identity._WAYS` aufnehmen (`kern.md` verlangt das).

### B18 — *Reparieren* mit der Vorgabe „Überschneidungen auflösen" dauert an großen Modellen 30–80 s, meist ohne Wirkung

- Status: **offen (hoch)**. Zeiten am Stand `02c5a9f7` gemessen; am Stand
  `a6f6289f` bestätigt `s20b` die Befunde (Achterröhre `unresolved`,
  Bohrhalter gelöst), die Zeiten der großen Modelle sind dort nicht erneut
  gemessen.
- Ort: `ops.py` 659–661 (Vorgabe `True`, Entscheidung Robert 24.09.2026),
  725; `repair.py` 1997–2093 (`_intersection_findings`: vollständige Suche bis
  `512 · Dreiecke`), 1551–1611 (`resolve_self_intersections`: bei einer
  Schale `[mesh, mesh]`, danach **zweite vollständige** Prüfung des
  Ergebnisses, 1598).
- Messung (`s22_reparieren_gross.py`, `s22.jsonl`), Operation mit ihren
  heutigen Vorgaben:

| Modell | Dreiecke | *Reparieren* | Suche (inkl. Nachprüfung) | Auflösen | Ergebnis |
|---|---|---|---|---|---|
| Besenhalter | 59 740 | 9,6 s | 9,4 s | — | nichts zu tun |
| Gähnende Katze | 452 311 | 6,7 s | 5,9 s | — | offen, `skipped` |
| Spiderman | 885 570 | 28,6 s | 24,1 s | 13,4 s | `unresolved`, unverändert |
| Piratenschiff obj_15 | 1 223 838 | **77,1 s** | 46,8 s | 49,0 s | `unresolved`, unverändert |
| Mausoleum Dragon | 2 330 374 | 52,1 s | 41,2 s | — | nichts zu tun |

  Am Stand 18:04 kosteten dieselben Modelle 1–11 s (Suche abgebrochen), vor
  Codex lief keine Suche.
- Kundensicht: Ein Klick auf *Reparieren* an einer gekauften Figur — über eine
  Minute ohne Fortschritt, danach „ließen sich nicht sicher auflösen". Die
  Suche ist je Block abbrechbar, die native Vereinigung nicht.
- Fix: (1) Nur vereinigen, wenn Schnittpaare zwischen **verschiedenen**
  Schalen liegen oder koplanar überlagern; die Eigenkreuzung einer Schale löst
  `[mesh, mesh]` am Korpus nicht (Achterröhre, Spiderman, Piratenschiff).
  (2) Nachprüfung nur an Ergebnisdreiecken, deren Hülle die Hüllen der alten
  Schnittflächen (plus Schweißtoleranz) berührt — der Rest stammt unverändert
  aus schnittfreien Eingängen. (3) `ctx.progress` durch Suche und
  Vereinigung. (4) Über der Kartengrenze (`MAP_LIMIT_TRIANGLES`) die Suche nur
  auf Nachfrage.
- Testidee: Kerntest — Achterröhre mit den Vorgaben der Operation ruft
  `boolean` nicht auf (Zähler per Monkeypatch); Release-Leistung:
  Piratenschiff obj_15 unter 20 s.

### B19 — `turn_shells_outward` prüft jeden Hohlraum einzeln gegen die ganze Außenschale

- Status: **offen (niedrig–mittel)**, neue Funktion (18:28), heute auch im
  Import.
- Ort: `repair.py` 222–306 (je negativer Schale ein `_point_inside_shell`
  gegen jede umhüllende positive Schale, ohne das Gitterzertifikat, das
  `perceive.features._shells_inside_the_material` hat); `loader.py` 1111.
- Messung (`s23_schalen.py`): richtig in allen Grenzfällen; `unify_normals`
  mit 50 Hohlräumen in 82 520 Dreiecken 0,34 s, 300 in 85 520 1,71 s, **300 in
  331 280 7,17 s** — linear in Hohlräume × Außendreiecke.
- Fix: alle Hohlraum-Stichpunkte in einem Feldaufruf gegen eine Außenschale
  prüfen oder die Schalenhierarchie der Hohlraumerkennung übernehmen (kein
  Zwilling); Schalenvolumen körpernah (B16).
- Testidee: 300 Hohlraumwürfel in einer Icosphäre (Unterteilung 7) —
  `unify_normals` unter 1 s (Release-Leistung).

## Zurückgenommene oder gegenstandslose Behauptungen

1. „Eine Einzelschale wird nie aufgelöst" — falsch; koplanare Überlagerungen
   löst `[mesh, mesh]` (B1).
2. „Codex hat den Test an `generated_figure.stl` ersetzt, weil der Fall nicht
   mehr geht" — nicht als Regression zu werten: HEAD meldete dort
   „aufgelöst" über null Schnitten (B1).
3. B6, ursprüngliche Vermutung „`ingest.not_watertight` bleibt, wenn eine
   spätere Reparatur ohne Lochfüllen schließt" — nie belegt und seit
   `mended_here` gegenstandslos.
4. B12 nannte zuerst `unify_normals` als Kosten der Reparatur; am aktuellen
   Stand liegt die Zeit im Import, die Reparatur braucht dort 0,2 s.
5. Der Docstring-Satz „Zwei Millionen Paare rechnet numpy in Bruchteilen einer
   Sekunde" war auf dieser Maschine falsch (1,3 s); der Satz ist heute
   umformuliert.

## Sondenverzeichnis

Alle unter `sonden/`, nur lesend, keine Datei in `app/` oder `tests/`
berührt.

| Sonde | Frage | Ausgabe |
|---|---|---|
| `common.py` | Helfer (Laden, Kennzahlen, HEAD-Modul) | — |
| `s01_durchdringung.py` | Vereinigung neu gegen HEAD an 7 gebauten Fällen | `s01.txt`, `s01_neu.txt` |
| `s02_korpus.py`, `s02_auswertung.py` | Import + Reparieren am ganzen Korpus | `s02.jsonl`, `s02_auswertung.txt` |
| `s03_einzelfaelle.py` | Umstülpung, Farbe am Loch, Teilschalen | `s03.txt`, `s03_neu.txt` |
| `s04_umstuelpung_import.py` | Import eines offenen, falsch gewickelten Netzes | `s04.txt`, `s04_neu.txt` |
| `s05_suchbudget.py` | Budget an 6 Korpuskörpern | `s05.txt` |
| `s06_naht_bohrhalter.py`, `s06b_bohrhalter_voll.py`, `s06c_naht_roh.py` | Naht und Bohrhalter | `s06*.txt` |
| `s07_befunde_ueber_schritte.py`, `s07b_naht_bericht.py`, `s07c_aktuell.py`, `s07d_kleinteile.py` | Befunde über mehrere Schritte im Dokumentweg | `s07*.txt` |
| `s08_grosse_loecher.py` | Lochfüllung an großen Ringen, Abbruch | `s08.txt` |
| `s09_farbe_am_loch.py` | Slotwahl der Füllflächen | `s09.txt` |
| `s10_klein.py` | nicht orientierbares geschlossenes Netz | (in `s20b.txt`) |
| `s11_plattform.py` | Reparieren unter Plattformrauschen | `s11.txt` |
| `s12_budget_groessen.py` | Kosten der Suche je Größe | `s12.jsonl`, `s12.log` |
| `s13_nachfassen_falten.py`, `s13b_vergleich.py`, `s13c_falten_ursache.py`, `s13d_ohren_mit_sperre.py` | Faltprobe, Nachfassen, belegter Fix | `s13.txt` |
| `s14_karte_kanten.py` | Kantenteil der Netzfehlerkarte | (Konsole) |
| `s15_fern.py` | Volumenvorzeichen fern vom Ursprung | (Konsole) |
| `s16_import_neu.py` | Korpuskörper mit Lochfüllung am neuen Stand | `s16.txt` |
| `s20_nachpruefung.py` | alle Befunde in einem Lauf | `s20.txt`, **`s20b.txt` (Stand dieses Berichts)** |
| `s21_karte_zeit.py` | Netzfehlerkarte mit neuem Budget | (Konsole) |
| `s22_reparieren_gross.py` | Reparieren mit heutigen Vorgaben an großen Modellen | `s22.jsonl`, `s22.log` |
| `s23_schalen.py` | `turn_shells_outward` Laufzeit und Grenzfälle | (Konsole) |
| `s24_ringe_offen.py` | warum Ringe am Korpus offen bleiben | (Konsole) |
