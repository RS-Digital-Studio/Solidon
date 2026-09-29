# Paket kanten — Schlussbericht

Arbeitsbaum `F:\3D Druck.review-051\wt-kanten`, Zweig `rm-279-kanten`, von
`main` `1163c30d7`. Commits: `6e8d0bedc` (RM-279, Weg B, Format 37),
`4e145c801` ((i) Ringrundung am Netz), `53ad8b785` (zwei Testfehler aus dem Tor),
`81b797456` ((ii) Gruppe lässt aus, was nicht trägt). Der laufende Bericht mit
allen Zahlen: `reports\kanten.md`.

## 1. Registerpunkte

### RM-279 — „Alle waagerechten Kanten“ nimmt die Ränder einer Querbohrung mit

**Gebaut (Weg B, Entscheidung Koordinator):** `edges.choose` nimmt gerade
Kanten nach ihrer Richtung und einen runden Rand nur, wenn er waagerecht liegt
(`edge_lie_of`, dieselbe Quelle wie die Beschriftung); ein Rand in einer
Seitenwand gehört zu keiner Gruppe, „senkrecht“ rechnet wie bisher. Beide
Kerne (der exakte ruft dieselbe Funktion). Alte Projekte: Parameter
`rings_by_plane` an *Verrunden*, *Fase*, *Wulst* (Rückseite, nur bei
waagerecht/oben/unten aktiv), Format 36 → 37 mit
`_keep_edge_groups_as_they_were` (auch `edited_ops` hinter Strg+Z),
`edge_groups_v36.p3d` vom Stand davor, `example_v37.p3d`. Commit `6e8d0bedc`.

**Messung:** Quader 40 × 30 × 20 mit Querbohrung Ø 6, „waagerecht“: vorher 10
Kanten (2 Ringe), nachher 8, beide Kerne. Pegboard-STEP (zehn Querbohrungen):
exakt 141 → 131, Netz 81 → 71, keine Mündung mehr; „senkrecht“ 52/28
unverändert. Eine Mündung heißt „Senkrecht · 18,85 mm · x 50,00, y 2,50“.

**Abnahme: ja.**
- Querbohrung → „waagerecht“ ohne Ringe, beide Kerne:
  `test_mesh_edges.py::test_a_group_takes_a_rim_only_when_it_lies_flat[mesh|brep]`
  (am alten Stand rot, `10 == 8`).
- Altes Projekt mit *Verrunden* an „waagerecht“ rechnet wie gespeichert:
  `test_project.py::test_v36_rounding_at_horizontal_keeps_the_mouths_of_a_cross_bore`
  (eingecheckte Datei; exakt auf die Stelle gleich, am Netz innerhalb des
  Sehnenzugs, weil (i) die Ringrundung selbst berichtigt) und
  `test_v36_edge_groups_on_both_undo_sides_keep_counting_rings_as_flat`.
- Echtes Modell: `F:\3D Dateien\pegboard-goot-ceramic-screwdrivers-v3.step`
  (`laeufe\kanten-echt-vorher.txt` / `-nachher.txt`).
- Vor dem Umbau gemessen, ob „senkrecht“ die Mündungen tragen kann
  (`reports\kanten.md`, Abschnitt „Halt“) — daraus die Entscheidung B.

### (i) Ringverrundung am Netz zu flach

**Gebaut:** `edges._swept_tool` — ein gebogener Zug bekommt sein Werkzeug als
einen Körper durch Querschnitte an den Knoten (Ring: Schlauch), auch mit
Radiusverlauf; vorher Prismen je Stück mit klaffendem Keil außen an der
Biegung. `cache_version` Verrunden 11, Fase 12. Commit `4e145c801`.

**Messung** (Quader, Bohrung Ø 6, beide Mündungen, quer und stehend gleich;
Abstand zum Torus analytisch):

| Maß | Netz vorher | Netz nachher | exakt = Pappus | Abstand zum Torus |
|---|---|---|---|---|
| R 2 | 35,160 (−5,4 %) | 38,746 (+4,2 %) | 37,180 | 0,713 → 0,017 mm |
| R 5 | 220,589 (−20,5 %) | 290,274 (+4,6 %) | 277,554 | 1,953 → 0,043 mm |
| Fase 2 | 78,899 (−14,4 %) | 91,890 (−0,3 %) | 92,153 | — |
| Verlauf 2→4→2 | 0,874 × exakt | 1,045 × exakt | 47,825 | — |

Die +4 % sind der Sehnenzug des Bogens (sechs Sehnen je Viertelkreis), dieselbe
Grenze wie an jeder Rundung; jeder Punkt liegt unter `MAX_FACET_SAG`.
gs-100, pegboard-goot, pb3041 (Mündungen einzeln, R ≤ 0,5, mehr lehnen beide
Kerne ab): Netz/exakt 1,039 → 1,052 bzw. Fase 0,994 → 0,996 — dort war der
Keil klein. Zapfen und Rundquader ohne Rückschritt.

**Abnahme: ja.** `test_the_mouth_of_a_bore_is_rounded_as_deep_as_pappus_says`
(6 Fälle) und `test_a_radius_law_around_the_mouth_of_a_bore_is_not_too_flat`,
alle 7 am Stand ohne `_swept_tool` rot (`laeufe\kanten-pappus-rot.txt`).

### (ii) Eine Gruppe scheitert ganz, statt eine zu enge Kante auszulassen

**Gebaut (Lesart 2, Entscheidung Koordinator):** `edges.contact_band_limits` je
Kante; eine Gruppe bearbeitet, was das Maß trägt, `edges.too_narrow` nennt die
übrigen mit dem kleinsten passenden Maß, *Stelle zeigen* und *Eingabe
korrigieren*; trägt keine Kante, bleibt die Absage, benannte Kanten halten an.
Exakter Kern: dieselbe Frage an der Tessellierung (`edge_ops._group_that_fits`),
OpenCASCADE bekommt nur die tragenden Kanten; baut es sie nicht oder tesselliert
es sie offen, bleibt die Absage mit der größten Zahl. Commit `81b797456`.

**Messung** (vorher `laeufe\kanten-gruppe-vorher.txt`, nachher
`kanten-gruppe-nachher.txt`, Wand `kanten-wand.txt`; Tabelle in
`reports\kanten.md`): Wand 40 × 3 × 20 an beiden Kernen gleich (oben R 2:
2 gerundet, 2 ausgelassen; alle R 2: 4 / 8; Wand bleibt 20 mm). Netz:
Hohlkasten R 2 17/4, R 5 9/12; pegboard-goot R 0,5–5 und Fase 1 je 8/20;
gs-100 6/4 (Facettenkanten, Wirkung unter 0,2 mm³); pb3041 Absage (keine Kante
trägt). Exakt: pegboard-goot Fase 1 8/20 (+24 glatte übersprungen); sonst
Absage wie vorher — Hohlkasten (OpenCASCADE baut die 17 nicht), pegboard-goot
Verrunden (zwei Rundungen werden offen tesselliert), gs-100 und pb3041 (keine
exakte Kante liegt auf einem tragenden Zug).

**Abnahme: teilweise.** Netz ja, Vorschau ja (`laeufe\kanten-vorschau-ii.txt`:
Befund mit Zahl, Stelle und Handlungen vor dem Übernehmen), Befundtext in sechs
Sprachen ja, Tests umgeschrieben und am alten Stand rot (5, `kanten-ii-rot.txt`).
**Beide Kerne gleich: nur bei gleicher Frage** — der exakte Kern sagt dort weiter
ab, wo OpenCASCADE die verkleinerte Gruppe nicht baut; an den drei Pegboards und
am Hohlkasten ist das der Fall. Ein halbierendes Neubauen wurde gemessen und
verworfen (15–37 s je Vorschau, an pb3041 ein offener Körper).

## 2. Kundensicht

Vorher: *Verrunden* an „alle waagerechten Kanten“ rundete an einem Teil mit
Querbohrung auch die Mündungen mit; an einem Netz kam jede verrundete oder
gefaste Bohrungsmündung zu flach heraus, bei großem Radius als Sägezahn.
Nachher: „waagerecht“, „oben“, „unten“ nehmen einen runden Rand nur, wenn er
waagerecht liegt; ein Rand in der Seitenwand heißt weiter „Senkrecht“, gehört
zu keiner Gruppe und wird einzeln gewählt — das Feld *Kanten* sagt es.
Die Rundung einer Mündung ist am Netz so tief wie am exakten Körper. Alte
Projekte öffnen und runden dieselben Kanten wie gespeichert.

## 3. Geänderte Dateien und Tests

| Datei | Trägt |
|---|---|
| `app/core/geom/edges.py` | `choose`, `_swept_tool`, `_tube`, `_loft_along`, `rings_by_plane` durch `wanted`/`selected_or_wanted`/`round_edges`/`bevel_edges`/`bead_edges` — `test_mesh_edges.py` (drei neue Tests) |
| `app/core/brep/edit.py` | `rings_by_plane` durch `fillet`/`chamfer`/`choose` — `test_mesh_edges.py[brep]` |
| `app/core/geom/edge_ops.py` | Parameter, doc-Sätze, `cache_version` — `test_operation_ui.py::test_the_rim_switch_sits_at_the_back_and_follows_the_group` (Fenster, Release-Tor), Offscreen-Sonde `sonden\kanten\dialog.py` |
| `app/core/scene/migrations.py` | Format 37 — `test_project.py` (zwei neue Tests, `example_v37.p3d`) |
| `tests/data/projects/edge_groups_v36.p3d`, `example_v37.p3d` | Beispieldateien |
| `app/i18n/locales/*.json` | zwei Texte, fünf Kataloge — `test_translations.py` |
| `.claude/rules/operationen.md`, `oberflaeche.md`, `app/core/geom/CLAUDE.md`, `konzepte/begruendungen/regel-operationen.md` | Regel, Parameterzahl, Karte, Warum |

**Tor:** `F:\3D Druck.review-051\laeufe\tor-kanten-3.txt` (auf `81b797456`):
17912 passed, 2 rot — zwei Zeitgrenzen unter Last
(`test_maps.py::test_a_body_on_the_plate_needs_nothing`, 3-s-Budget der
Stützkarte; `test_process.py::test_a_blocking_stream_callback_cannot_disable_the_total_timeout`,
3,8 statt 3 s), beide in der Wiederholung grün (`tor-kanten-3-wdh.txt`,
2 passed), ohne Bezug zu Kanten; ruff, format, mypy 0. Davor `tor-kanten-2.txt`
auf `53ad8b785` ganz grün.

(ii) zusätzlich: `app/core/geom/edges.py` (`contact_band_limits`, `_band_rows`,
`too_narrow_finding`, `skipped_finding`), `app/core/geom/edge_ops.py`
(`_group_that_fits`, Sicherung gegen offene Tessellierung), `tests/test_brep.py`,
`konzepte/begruendungen/karte-app-core-geom.md`.

## 4. Oberflächentexte (deutsch)

- neu `Runde Ränder nach ihrer Lage` (Titel des Parameters)
- neu `Ein runder Rand wie die Mündung einer Bohrung zählt nur zu waagerecht,
  oben oder unten, wenn er waagerecht liegt. In einer Seitenwand heißt er
  „Senkrecht“, gehört aber zu keiner Gruppe — wählen Sie ihn dann einzeln.
  Ohne Haken zählt jeder runde Rand als waagerecht, wie in Schritten aus
  älteren Versionen.`
- geändert (doc von *Kanten*): `… alle oder einzeln gewählte. Ein runder Rand
  gehört nur dazu, wenn er waagerecht liegt; eine Bohrung in einer Seitenwand
  wählen Sie einzeln.`

(ii) neu: drei Sätze `edges.too_narrow` — „Einige Kanten dieser Auswahl sind
nicht verrundet: Neben ihnen ist die Fläche zu schmal für diesen Radius. Dort
passt nur ein Radius unter {largest}. Die übrigen Kanten sind verrundet. Soll
die Rundung auch dort sitzen, wählen Sie einen kleineren Radius.“, dieselbe
Fassung für die Fase („Breite“) und für den Radiusverlauf („diese Radien“).

## 5. Changelog (Vorschlag)

„Alle waagerechten Kanten“ lässt die Mündungen einer seitlichen Bohrung
stehen, und eine verrundete oder gefaste Bohrungsmündung wird an einem
importierten Modell so tief wie gewünscht. Passt ein Radius nicht an jede
Kante einer Gruppe, rundet Solidon die übrigen und zeigt, wo es nicht passt.

## 6. Registertext

RM-279 schließt mit (i) und (ii). Neu ins Register gehört „Der exakte Kern baut
eine verkleinerte Kantengruppe nicht immer“: Hohlkasten 3 mm „alle“ R 2 (17
Kanten, jede einzeln baubar, zusammen nicht), pegboard-goot Verrunden (zwei
Rundungen, Kanten 212 und 221, tesselliert OpenCASCADE offen, bei jedem Radius
und auch einzeln), gs-100 und pb3041 (die Kanten der Tessellierung decken sich
nicht mit den exakten). Dort sagt der exakte Kern ab, wo das Netz auslässt.

## 7. Nicht behoben

- Exakter Kern bei (ii), siehe 6 — mit Messung; ein halbierendes Neubauen war zu
  langsam (15–37 s je Vorschau) und lieferte an pb3041 einen offenen Körper.
- pegboard-goot, Kanten 212 und 221: OpenCASCADE tesselliert ihre Rundung offen,
  auch einzeln gewählt (`sonden\kanten\dicht.py`, `laeufe\kanten-dicht.txt`) —
  vorbestehend, am benannten Weg weiter erreichbar.
- 42 Handbuchtests (`test_manual.py`, `test_wording.py::test_every_manual_paragraph_reaches_the_generated_page`)
  sind am unveränderten `1163c30d7` genauso rot (`laeufe\kanten-handbuch-head2.txt`);
  das eingecheckte Handbuch entsteht beim Release. Im Tor tauchen sie nicht auf,
  weil es sie als Erzeugnisvergleich zurückstellt.
- Der Grund an einer ausgegrauten Zeile nennt nur den ersten Wert einer Bedingung
  (`op_dialog._why_inactive`), nicht neu.
- `operationen.md` steht bei 30 714 von 30 720 Byte; die nächste Regel braucht
  vorher eine Verschiebung ins Warum.
