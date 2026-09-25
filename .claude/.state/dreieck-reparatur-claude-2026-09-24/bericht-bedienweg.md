# Bedienweg „kaputtes Dreiecksmodell → druckbar und bearbeitbar"

Durchsicht: Claude (bedienlogik), 24.09.2026, nur lesend. Stand: HEAD 8ed5d6299
plus unkommittierte Änderungen aus `.claude/.state/triangle-repair-review-2026-09-24/staged.patch`.
Sonden (ohne Fenster) unter `sonden/`, Ausgaben daneben als `*.txt`.

Status: abgeschlossen (24.09.2026).

## Messgrundlage

Sonde `sonden/befunde_weg.py` geht den Weg der Sitzung ohne Fenster
(`ingest.plan.import_plan` → `History.apply` → `evaluate`), danach einmal
*Reparieren* mit Vorgabe und einmal mit „Selbstdurchdringungen auflösen“, und
listet je Befund Text, Schwere und die Knöpfe, die
`panels.actions_for_document` wirklich anbietet. Ausgaben:
`sonden/befunde_weg_1.txt` (Korpus `tests/data/meshes` sowie `F:/3D Dateien/mushroom.stl`
und `peg.stl`), `befunde_weg_2.txt` und `befunde_weg_3.txt` (künstliche Fehlerbilder aus
`sonden/kaputte_netze.py`, `kaputte_netze_2.py`), `dense_1m.txt` (1,31 Mio. Dreiecke),
`geometrie_nach_import.txt` (was nach dem Import tatsächlich vorliegt).

Wichtigster Messbefund vorweg: **Der Import schließt jedes Netz topologisch** —
auch eine einzelne Fläche aus zwei Dreiecken und eine zufällige Dreieckssuppe
(„112 von 112 offenen Kanten geschlossen; 0 bleiben offen“). `ingest.not_watertight`
war in keinem der 22 Fälle erreichbar. Was bleibt, sind Körper ohne Volumen,
Körper mit selbst erzeugten Durchdringungen und ein Volumenverlust ohne Warnung
— und der Bericht sieht dabei fast grün aus.

## Weg A — Import einer kaputten STL

**Klickfolge Ist:** Datei ziehen (1) → der Bericht springt auf, weil eine
Warnung entsteht → der Kunde liest 2 bis 5 Zeilen. Knöpfe gibt es nur an
„mehrere Teile“ und „sehr kleine Einzelteile“. Kein Klick führt zur „großen Öffnung“.

Gemessen, was der Kunde nach dem Import sieht (Auszug):

| Datei | Zeilen | davon mit Knopf | Was tatsächlich vorliegt |
|---|---|---|---|
| `broken_open.stl`, `partially_open.stl`, `kugel_ohne_kappe.stl` | 2 | 0 | geschlossen, Öffnung mit neuer Fläche |
| `rohr_ohne_deckel.stl` | 2 | 0 | zwei Deckel erfunden |
| `offene_flaeche.stl` (2 Dreiecke) | 2 | 0 | „geschlossen“, **Volumen 0**, 4 sich durchdringende Dreiecke |
| `flosse.stl` (Würfel + Dreieck an einer Kante) | 3 | 0 | **7000 statt 8000 mm³** — ein Würfeldreieck entfernt, die Flosse behalten |
| `loch_und_kruemel.stl` | 3 | 2 | geschlossen, aber **7 durchdringende Dreiecke in der eigenen Lochfüllung** |
| `durchdringung.stl` (zwei ineinandergeschobene Würfel) | 1 | 1 | Durchdringung wird nicht gemeldet; Knopf „In Einzelteile zerlegen“ |
| `suppe.stl` | 5 | 1 | 37 „geschlossene“ Schalen aus Zufallsdreiecken |
| `gedrehte_flaechen.stl`, `umgestuelpt.stl`, `t_stoss.stl`, `degenerate.stl` | 1 | 0 | richtig repariert |

### A1 — Die „große Öffnung“ hat keinen Knopf und keinen Rückweg (hoch)

- **Ist:** `repair.wide_hole_filled` (`app/core/geom/repair.py:1424-1440`),
  Warnung: „Eine große Öffnung wurde geschlossen — prüfen Sie, ob dort wirklich
  eine Fläche hingehört.“ Keine Handlung (`FINDING_ACTIONS` kennt den Code nicht,
  `app/ui/panels.py:361-569`), kein Ort am Befund (Werte nur `walls`).
- **Kundensicht:** Er soll prüfen, weiß aber nicht wo — die Netzfehlerkarte zeigt
  die neue Fläche nicht (sie ist kein Defekt mehr). Und wenn die Fläche nicht
  hingehört, gibt es keinen Weg: Die Ladeoperation hat keinen Schalter für das
  Lochfüllen (`LoadParams`, `app/core/ingest/ops.py:74-141`; `normalise(mend=…)`
  wird nie gesetzt, `ops.py:307-326`). Strg+Z nimmt den ganzen Import. Sackgasse
  und Regel 17. Dazu bleibt die Warnung für immer im Bericht, und der Bericht
  springt bei jedem solchen Import nach vorn.
- **Soll:**
  1. Der Befund trägt den Ort (Mitte des geschlossenen Rings, `values["at"]`) —
     dann fliegt der Klick auf die Zeile hin, und die Marke steht dort (vorhandener
     Mechanismus, `oberflaeche.md`, „Ein Klick auf einen Befund bleibt nie folgenlos“).
  2. Ladeparameter `mend` („Offene Stellen schließen“, hinten, Vorgabe an) und
     am Befund zwei Knöpfe: **„Stelle zeigen“** und **„Offen lassen“** (setzt
     `mend=False` am Ladeschritt über `History.change_params`; Strg+Z nimmt es zurück).
  3. Text kürzer: „Eine große Öffnung wurde mit einer neuen Fläche geschlossen.“
     (Mehrzahl: „{walls} große Öffnungen …“). Der Rat steckt im Knopf.
- **Dateien:** `app/core/geom/repair.py` (Ort mitgeben), `app/core/ingest/ops.py`
  (`LoadParams.mend`, an `normalise` durchreichen), `app/ui/panels.py`
  (`FINDING_ACTIONS`), `app/ui/main_window.py` (Handler „Offen lassen“), alle
  Kataloge. Ein neuer Parameter mit Vorgabe „an“ ändert alte Projekte nicht;
  die Formatfrage prüft der Kern.

### A2 — Eine offene Fläche wird zu einem Körper ohne Volumen; danach ist „Offene Fläche schließen“ gesperrt (hoch)

- **Ist:** `offene_flaeche.stl` (zwei Dreiecke) kommt als „geschlossen“ an —
  Volumen 0, alle vier Dreiecke durchdringen sich (`geometrie_nach_import.txt`).
  Bericht: „große Öffnung“ und „4 von 4 offenen Kanten geschlossen; 0 bleiben
  offen.“ *Offene Fläche schließen* (`app/core/geom/mesh_ops.py:1628`) ist danach
  gesperrt mit `ALREADY_CLOSED` (`mesh_ops.py:1619-1623`): „Dieser Körper ist
  schon geschlossen — …“. *Reparieren* meldet „Flächen durchdringen sich …“, und
  mit dem Haken „Die Durchdringungsreparatur braucht einen geschlossenen Körper …“
  (`repair.py:1482-1493`) — über einem Körper, den der Bericht gerade „geschlossen“
  genannt hat.
- **Kundensicht:** Ein Relief, ein Lithophan-Rohling, eine einzelne Fläche aus
  einem CAD-Export: Der eine Weg, der hilft (Dicke geben), ist gesperrt, und jeder
  andere widerspricht sich. Ring ohne Ausgang.
- **Soll (zwei Varianten; Entscheidung Robert nötig, weil sie „alles beim Import
  beheben“ vom 22.09.2026 berührt):**
  - **V1** Der Import schließt nicht, wenn das Ergebnis kein Volumen hätte: Er
    lässt die Fläche offen und meldet „Das Modell ist eine Fläche ohne Dicke.“
    mit dem Knopf **„Dicke geben“** (*Offene Fläche schließen*, vorbelegt mit der
    Mindestwand des Profils).
  - **V2** Der Import schließt wie heute, aber `labels.body_facts` zählt einen
    Körper ohne Volumen als offen; *Offene Fläche schließen* bleibt bedienbar,
    und die Öffnungswarnung trägt „Dicke geben“.
  - Empfehlung V1: Eine erfundene Doppelfläche ist nie, was der Kunde wollte.
- **Dateien:** `app/core/ingest/loader.py:1133-1158`, `app/core/geom/repair.py`
  (Volumen vor dem Füllen fragen), `app/ui/labels.py` (`body_facts`), `app/ui/panels.py`.

### A3 — Die Import-Reparatur verändert das Teil, und keine Zeile sagt es (hoch, Kern)

- **Ist:** `flosse.stl`: `resolve_branching_edges` entfernt „die kleinste“ Fläche
  an der Verzweigung — hier ein Würfeldreieck (200 mm²) statt der Flosse (212 mm²);
  danach wird die Lücke mit der Flosse geschlossen. Ergebnis 7000 statt 8000 mm³.
  Text dazu: „An einer Kante lagen Flächen übereinander — die überzählige wurde
  entfernt.“ (`repair.py:1377-1390`). `loch_und_kruemel.stl`: Die eigene
  Lochfüllung erzeugt 7 sich durchdringende Dreiecke; erst *Reparieren* meldet
  danach „Flächen durchdringen sich“, als hätte die Datei sie mitgebracht.
- **Kundensicht:** „Übereinander“ stimmt nicht (die Flosse ragt heraus), und dass
  ein Achtel des Volumens fehlt, erfährt er im Slicer. Dass Solidon die
  Durchdringung selbst gebaut hat, sieht er nie.
- **Soll:** Geometrie gehört in den Reparaturkern-Bericht (`bericht-reparaturkern.md`).
  Für die Bedienung: Ändert die Importreparatur das Volumen um mehr als
  `Profile.smallest_printable_volume`, gehört das als Warnung mit Zahl in den
  Bericht („Beim Schließen hat sich das Volumen um 12 % geändert.“, Knöpfe
  „Stelle zeigen“, „Offen lassen“). Text der Verzweigung: „An {edges} Kanten
  stießen mehr als zwei Flächen zusammen; die überzähligen wurden entfernt.“ —
  „übereinander“ nur, wo die Flächen wirklich deckungsgleich waren.

### A4 — Zu viele Infozeilen für eine erledigte Sache (mittel)

- **Ist:** Ein Loch erzeugt zwei Zeilen (`wide_hole_filled` und `holes_filled`),
  eine Flosse drei. Texte: „4 von 4 offenen Kanten geschlossen; 0 bleiben offen.“
  (`repair.py:1447-1453`), „Kanten mit einem Punkt darauf wurden vernäht.“
  (`repair.py:1404`), „Entartete Dreiecke wurden entfernt.“ (`loader.py:1088`,
  `repair.py:1350`), „Deckungsgleiche Dreiecke wurden paarweise entfernt.“
  (`repair.py:1322`), „Doppelte Punkte blieben stehen — sie zu verschweißen hätte
  das Netz weiter aufgerissen.“ mit dem Wert `tolerance: '0.00 mm'` (Punkt statt
  Komma, und 0,00 ist keine Auskunft; `repair.py:1285-1294`).
- **Kundensicht:** Fachwörter (Kante, entartet, verschweißt, vernäht), keine
  Handlung, und „0 bleiben offen“ ist Füllstoff. Robert will kurze Texte.
- **Soll:** Je Ladeschritt **eine** Zeile für alles Erledigte:
  „Beim Einlesen repariert: 1 Loch geschlossen, 3 fehlerhafte Dreiecke entfernt,
  Außenseiten angeglichen.“ — Einzelheiten im Tooltip. Nur was offen bleibt oder
  das Teil verändert, steht als eigene Warnung. Mindestens die Einzeltexte:
  - `holes_filled`: „{closed} Löcher geschlossen.“ (Zahl der Ringe statt Kanten;
    der Rest nur, wenn er größer als null ist: „{remaining} offene Stellen bleiben.“)
  - `t_junctions`: „Lücken an Nähten wurden geschlossen.“
  - `degenerate_removed`: „Leere Dreiecke wurden entfernt.“
  - `doubled_removed`: „Doppelte Dreiecke wurden entfernt.“
  - `weld_skipped` (beide Stellen): Zeile entfällt — es ist nichts passiert, und
    der Kunde kann nichts tun. `tolerance` höchstens als Zahl, die `labels.length`
    formatiert, nicht als fertiger Text aus dem Kern.
- **Dateien:** `app/core/ingest/loader.py`, `app/core/geom/repair.py`; die
  Zusammenfassung am besten in `app/core/ingest/ops.py` nach `normalise`; alle Kataloge.

### A5 — Durchdringungen kommen beim Import nicht vor; der Knopf empfiehlt das Falsche (mittel)

- **Ist:** Zwei ineinandergeschobene Würfel: einzige Zeile „Das Modell besteht aus
  mehreren Teilen.“ mit „In Einzelteile zerlegen“ (`loader.py:1320-1327`,
  `panels.py:494`). Die Suche nach Durchdringungen läuft beim Import bewusst nicht
  (Codex-Änderung, Docstring `repair.py:1265-1271`).
- **Kundensicht:** „Zerlegen“ macht aus einem Teil zwei überlappende Teile — das
  Gegenteil dessen, was ein Druck braucht. Dass die Teile ineinanderstecken,
  erfährt er erst, wenn er selbst *Reparieren* findet.
- **Soll:** Beim Import die billige Vorfrage „überlappen sich die Hüllquader
  zweier Schalen?“ — dann „Das Modell besteht aus {components} Teilen, die
  ineinanderstecken.“ und die Knöpfe **„Zu einem Körper verschmelzen“** (Reparieren
  mit `self_intersections=True`) vor „In Einzelteile zerlegen“. Liegen die Teile
  getrennt, bleibt der heutige Satz.

### A6 — `perceive.voids_unreadable` nennt eine Handlung ohne Knopf (mittel)

- **Ist:** `suppe.stl`: „Dieses Modell besteht aus mehreren Schalen, und ob eine
  davon ein Lufteinschluss ist, ließ sich nicht sicher lesen. Reparieren Sie das
  Netz, oder prüfen Sie es im Slicer auf eingeschlossene Luft.“ — Warnung, kein
  Knopf, 30 Wörter. Nach *Reparieren* steht sie unverändert da.
- **Soll:** „Ob das Modell Lufteinschlüsse hat, ließ sich nicht sicher lesen.“
  Knopf „Stellen zeigen“; „Reparieren“ nur, wenn eine Reparatur ihn wirklich
  auflösen kann, sonst ist der Rat ein Ring. Regel aus `oberflaeche.md`: Wer eine
  Handlung im Satz nennt, bietet genau sie als Knopf an.

## Weg B — „Stellen zeigen“ und die Netzfehlerkarte

**Klickfolge Ist:** Befundzeile (vorgewählt) → **Stellen zeigen** (1) →
`MainWindow._show_error_location` (`app/ui/main_window.py:19749-19766`) wählt den
Körper, schaltet das Werkzeug *Analyse* ein und die Karte *Netzfehler*. Die Karte
(`app/core/perceive/maps.py:872-932`) färbt je Dreieck vier Stufen
(`DEFECT_LEVELS`, `maps.py:110-118`) auf der Viridis-Rampe (`palette.map_colour`):
„in Ordnung“ dunkelviolett, „offene Kante“ blau, „verzweigte Kante“ grün,
„Durchdringung“ gelb. Rot oder Orange gibt es dort nicht. Die Legende
(`app/ui/analysis_bar.py:138-160`) schreibt den Namen auf das Farbfeld — damit
trägt jede Farbe ein Wort (Regel 18 in der Legende erfüllt); auf dem Modell selbst
trägt nur die Helligkeit die zweite Kodierung.

### B1 — Von der Karte führt kein Weg zur Reparatur (hoch)

- **Ist:** Die Analyseleiste hat keine Handlung. Wer die gelben Stellen sieht,
  muss zurück in den Bericht (*Eingabe korrigieren*) oder in der Auswahlkarte die
  Gruppe *Reparatur* suchen. Strg+Umschalt+R kennt kein Kunde.
- **Soll:** Zeigt die Netzfehlerkarte einen Fehler, steht in der Analyseleiste
  rechts neben der Legende ein Knopf, der zur Stufe passt:
  **„Löcher schließen“** (Stufe 1 oder 2 vorhanden → *Reparieren* mit Vorgabe) oder
  **„Überschneidungen auflösen“** (nur Stufe 3 → *Reparieren* mit
  `self_intersections=True`). Ohne Fehler steht dort der Satz
  „Keine Netzfehler gefunden.“ — heute zeigt die Karte dann ein einfarbig
  violettes Modell ohne Aussage.
- **Dateien:** `app/ui/analysis_bar.py` (Knopf, Signal), `app/ui/main_window.py`
  (`_analysis_map`-Abschluss: Stufen zählen, Knopf setzen).

### B2 — Legende und Kartensatz sprechen Fachsprache und passen nicht zusammen (mittel)

- **Ist:** Stufen „offene Kante“, „verzweigte Kante“, „Durchdringung“. Der Satz am
  Kartennamen (`analysis_bar.py:329`): „Zeigt Löcher, doppelte Flächen und Stellen,
  an denen das Netz nicht dicht ist.“ — „doppelte Flächen“ ist keine Stufe, die
  Durchdringung fehlt im Satz, „Netz“ ist Konstrukteurswort.
- **Soll:** Stufen **„in Ordnung“, „Loch“, „überzählige Fläche“, „Überschneidung“** —
  dieselben Wörter wie in den Reparaturtexten (siehe C3). Satz: „Zeigt Löcher,
  überzählige Flächen und Stellen, an denen sich das Modell selbst schneidet.“
- **Dateien:** `app/core/perceive/maps.py:110-118`, `app/ui/analysis_bar.py:325-331`,
  alle Kataloge.

### B3 — „in Ordnung“ färbt das ganze Modell (niedrig)

- **Ist:** Stufe 0 bekommt die dunkelste Rampenfarbe; das Modell wird violett, die
  wenigen Fehlerdreiecke sind hell. Kleine Fehler (ein Dreieck an einer
  Durchdringung) sind auf einem großen Modell kaum zu finden.
- **Soll:** Stufe 0 in der normalen Körperfarbe, Fehler in der Rampe, und die
  Kamera fliegt beim Öffnen über „Stellen zeigen“ zur größten Fehlergruppe
  (dieselbe Marke wie beim Befundklick). Entscheidung der Ansicht, nicht nur der
  Bedienung — `ansicht.md` prüfen.

## Weg C — „Reparieren“ und der Weg zu den Überschneidungen

**Klickfolge Ist** (zwei ineinandergeschobene Teile, dem Befund folgend):

| # | Kunde sieht | tut |
|---|---|---|
| 1 | Auswahlkarte, Gruppe *Reparatur* (nicht in `QUICK_BODY`, `selection_operations.py:55`) | *Reparieren* |
| 2 | Dialog, vorn allein „Offene Stellen schließen“ (hat der Import schon getan) | *Übernehmen* (nach der Vorschau) |
| 3 | Bericht: „Flächen durchdringen sich. Aktivieren Sie unter „Weitere Einstellungen“ die Option „Selbstdurchdringungen auflösen“.“ | *Eingabe korrigieren* |
| 4 | derselbe Dialog, Klappe zu, Cursor nirgends | *Weitere Einstellungen* |
| 5 | fünf Haken | Haken „Selbstdurchdringungen auflösen“ |
| 6 | — | *Übernehmen* |

Ergebnis: „Selbstdurchdringungen wurden aufgelöst.“ und daneben „Formdetails sind
nach diesem Schritt nicht mehr automatisch wiederzuerkennen.“ **6 Klicks, zwei
Dialoge, eine Klappe, viermal wechselt der Blick** zwischen Karte, Dialog und Bericht.

### C1 — „Eingabe korrigieren“ führt nicht in das genannte Feld (hoch)

- **Ist:** Der Befund `repair.self_intersections_detected` (`repair.py:1511-1532`)
  trägt `suggestions=(CORRECT_INPUT, SHOW_LOCATIONS)`, aber **keine Werte** — gemessen
  `Werte: {}` (`befunde_weg_1.txt`). `_correct_after_error`
  (`main_window.py:20047-20054`) ruft `edit_operation(op_id, values.get("field", ""))`,
  also mit leerem Feld; `OperationDialog.focus_field` (`op_dialog.py:2822-2852`),
  das die Klappe öffnen würde, läuft gar nicht. Der Dialog geht zu, die Option
  bleibt hinter „Weitere Einstellungen“. Dazu die Regel aus `oberflaeche.md`: Wer
  eine Handlung im Satz nennt, bietet genau sie als Knopf an — hier steht ein
  Menüweg im Satz und ein allgemeiner Knopf daneben.
- **Soll, kürzester Weg (Empfehlung):** eine eigene Handlung
  **`RESOLVE_INTERSECTIONS` — „Überschneidungen auflösen“** (Hauptknopf). Der
  Handler schreibt `self_intersections=True` in genau diesen Schritt
  (`History.change_params`, derselbe Weg wie *Eingabe korrigieren* beim
  Übernehmen: Schritt ersetzt, kein zweiter im Verlauf), ohne Dialog —
  rücknehmbar, also keine Rückfrage (Regel 19). Text am Befund:
  „Teile des Modells schneiden sich.“ — Knöpfe **[Überschneidungen auflösen]**
  **[Stellen zeigen]**. Klicks ab dem Befund: **1 statt 4**, ohne Dialog.
- **Mindestens (falls keine neue Handlung):** `values={"field": "self_intersections"}`
  am Befund; dann klappt *Eingabe korrigieren* auf und setzt den Fokus — 3 statt 4
  Klicks, und der Menüweg fliegt aus dem Satz.
- **Dateien:** `app/core/errors.py` (neue `Action`), `app/core/geom/repair.py`
  (Befund), `app/ui/main_window.py` (Handler in `error_handlers`, `dialogs.NEEDS_OP`
  um die Kennung ergänzen, weil sie eine Schrittkennung braucht), alle Kataloge.

### C2 — Die Vorderseite des Dialogs zeigt das Falsche; die Vorgabe tut nach dem Import fast nie etwas (hoch, Entscheidung)

- **Ist:** `RepairParams` (`app/core/geom/ops.py:641-685`): vorn nur `fill_holes`;
  hinten `weld`, `degenerate`, `normals`, `small_components`, `self_intersections`.
  Der Import fährt Verschweißen, Bereinigen, Außenseiten und Lochfüllen schon selbst.
  Gemessen an 22 Dateien: *Reparieren* mit Vorgabe meldete danach **nur einmal** (Zufallssuppe) eine neue
  Reparatur, sonst „An diesem Netz war nichts zu reparieren.“ oder den Rat, den
  hinteren Haken zu setzen.
- **Kundensicht:** Der Knopf heißt *Reparieren* und repariert nicht; die zwei
  Schalter, die nach dem Import noch wirken, liegen hinter der Klappe.
- **Soll, Varianten:**
  - **V1** Vorn: „Überschneidungen auflösen“ und „Kleinstteile entfernen“; hinten
    der Rest. Vorgaben unverändert.
  - **V2** Wie V1, und „Überschneidungen auflösen“ steht auf **an**. Die Suche
    läuft ohnehin bei jedem Reparaturschritt (`inspect_intersections=True`,
    `ops.py:716`); an kostet nur die Vereinigung, und die bleibt bei Unsicherheit
    ohne Wirkung. *Reparieren* heißt dann wirklich reparieren: 2 Klicks.
  - Empfehlung V2 mit Robert abstimmen (eine Vereinigung legt Teile zusammen, die
    der Kunde vielleicht getrennt drucken wollte — dafür gibt es *In Einzelteile
    zerlegen*, und Strg+Z).

### C3 — Parametertexte (mittel)

| Feld | Ist | Soll |
|---|---|---|
| `self_intersections` Titel | „Selbstdurchdringungen auflösen“ | „Überschneidungen auflösen“ |
| `self_intersections` doc (`ops.py:681-684`) | „Vereinigt **sich** überlappende Teile. …“ — Grammatikfehler | „Verschmilzt Teile, die ineinanderstecken. Was nicht sicher geht, bleibt unverändert.“ |
| `small_components` Titel/doc (`ops.py:671-676`) | „Kleinstteile löschen“ / „Standardmäßig aus: gelöscht wird nur, was ausdrücklich gelöscht werden soll.“ — sagt nicht, was es tut | „Kleinstteile entfernen“ (wie der Knopf `REMOVE_SMALL_PARTS` „Kleine Teile entfernen“ — ein Wort für eine Sache) / „Entfernt lose Splitter, die viel kleiner sind als das Hauptteil.“ |
| `degenerate` Titel (`ops.py:659-663`, ebenso `LoadParams`) | „Entartete Dreiecke entfernen“ | „Leere Dreiecke entfernen“ |
| `fill_holes` doc (`ops.py:645-648`) | „Schließt offene Ränder. Bei großen Öffnungen weist der Prüfbericht auf die neu entstandenen Flächen hin.“ | „Schließt Löcher. Große Öffnungen nennt der Prüfbericht.“ |
| Operation doc (`ops.py:703`) | „Schließt Löcher, entfernt entartete Dreiecke und richtet die Flächen aus.“ | „Schließt Löcher, entfernt fehlerhafte Dreiecke, richtet die Außenseiten aus und löst auf Wunsch Überschneidungen.“ |

### C4 — Befundtexte der Überschneidungen (mittel)

| Code | Ist (`repair.py`) | Soll |
|---|---|---|
| `self_intersections` (1508) | „Selbstdurchdringungen wurden aufgelöst.“ | „Überschneidungen wurden aufgelöst.“ |
| `self_intersections_detected` (1525-1526) | siehe C1 | „Teile des Modells schneiden sich.“ |
| `self_intersections_unresolved` (1519-1521) | „Die sich durchdringenden Flächen konnten nicht sicher getrennt werden. Das Modell bleibt an diesen Stellen unverändert; prüfen Sie die markierten Stellen.“ | „Die Überschneidungen ließen sich nicht sicher auflösen; das Modell bleibt dort unverändert.“ + [Stellen zeigen] |
| `self_intersections_incomplete` (1539-1540) | „Die Prüfung … ist noch unvollständig. …“ — „noch“ verspricht ein Weiterlaufen, das es nicht gibt | „Die Suche nach Überschneidungen wurde vorzeitig beendet; es kann weitere geben.“ |
| `self_intersections_skipped` (1487-1489) | 25 Wörter, „korrekt ausgerichteten Außenseiten“, „Einstellungen zum Schließen und Ausrichten“ ohne Knopf; an einer Fläche ohne Dicke falsch (A2) | „Überschneidungen lassen sich nur an einem Körper mit Innenraum auflösen.“ + [Stellen zeigen]; bei Volumen 0 zusätzlich [Dicke geben] |

„markierte Stellen“ gibt es erst nach *Stellen zeigen* — der Satz setzt einen
Klick voraus, den er nicht nennt. Mit dem Knopf daneben entfällt er.

### C5 — Nach der Reparatur meldet der Bericht verlorene „Formdetails“ (mittel)

- **Ist:** `perceive.orphaned` nach jedem verändernden Reparaturschritt:
  „Formdetails sind nach diesem Schritt nicht mehr automatisch wiederzuerkennen.“
  (Werte `face_2, face_4, …`), Info ohne Knopf.
- **Kundensicht:** An einem heruntergeladenen Netz hat er diese Flächen nie
  benannt; die Zeile klingt, als sei etwas kaputtgegangen.
- **Soll:** Nur melden, wenn ein **späterer Schritt oder eine Passung** eines der
  verlorenen Merkmale benutzt — sonst schweigen. Dann mit dem Namen des
  Verbrauchers und [Diesen Schritt ändern].

## Weg D — Was nach der Reparatur stehen bleibt

`SETTLED_BY` (`app/core/scene/evaluate.py:1186-1212`) kennt vier Paare:
`ingest.not_watertight` ← `repair.holes_filled`, `ingest.small_components` ←
`repair.components_removed`, `perceive.too_large` und `ingest.very_large` ←
`mesh.deviation`. Für die neuen Überschneidungsbefunde steht dort nichts.

### D1 — Der Rat „Aktivieren Sie …“ bleibt neben „wurden aufgelöst“ stehen (hoch)

- **Ist:** Wer nicht über *Eingabe korrigieren* geht, sondern *Reparieren* ein
  zweites Mal mit dem Haken aufruft, liest danach untereinander
  „Flächen durchdringen sich. Aktivieren Sie … „Selbstdurchdringungen auflösen““ mit
  *Eingabe korrigieren* **und** „Selbstdurchdringungen wurden aufgelöst.“
  (`befunde_weg_1.txt`: `broken_selfint.stl`; `befunde_weg_2.txt`: `durchdringung.stl`,
  `loch_und_kruemel.stl`). Bei `flaeche_geteilt.stl` und `innere_wand.stl` stehen
  „Aktivieren Sie …“ und „konnten nicht sicher getrennt werden“ nebeneinander.
- **Soll:** `SETTLED_BY["repair.self_intersections_detected"] =
  {"repair.self_intersections", "repair.self_intersections_unresolved"}` und
  `SETTLED_BY["repair.self_intersections_incomplete"] = {"repair.self_intersections"}`
  — dieselbe Bedingung wie bisher (späterer Schritt, derselbe Körper). Der Rat ist
  befolgt, sobald ein späterer Schritt den Haken hatte, gleich mit welchem Ausgang.

### D2 — Nach „Kleine Teile entfernen“ heißt es weiter „mehrere Teile“ (hoch)

- **Ist:** `sonden/kleinteile_weg.txt`: Nach dem Knopf am Importbefund hat der
  Körper **ein** Teil; im Bericht stehen „Das Modell besteht aus mehreren Teilen.“
  mit dem Knopf *In Einzelteile zerlegen* (der jetzt an `prepare_ops.ONE_PIECE`
  scheitern würde) und „Kleinstteile wurden gelöscht.“ als **Warnung** ohne Knopf
  (`repair.py:1361-1364`).
- **Kundensicht:** Er hat genau das getan, was der Bericht vorschlug, und der
  Bericht wird dadurch gelb und widersprüchlich.
- **Soll:** `SETTLED_BY["ingest.multiple_components"] = {"repair.components_removed"}`
  nur, wenn danach ein Teil übrig ist — sauberer: die Teilezahl am Ende neu
  melden, wie `check_placement` es für Lagen tut (`operationen.md`, „Was aus einem
  Verhältnis entsteht“). `components_removed` als Hinweis: „{removed} Kleinstteile
  entfernt. Strg+Z holt sie zurück.“

### D3 — „Kleine Teile entfernen“ fördert eine Überschneidungswarnung zutage (mittel)

- **Ist:** Der Knopf ruft den ganzen Reparaturschritt
  (`_remove_small_parts`, `main_window.py:19866-19889`), und der sucht immer nach
  Überschneidungen (`inspect_intersections=True`, `ops.py:716`). Bei
  `loch_und_kruemel.stl` steht danach neu „Flächen durchdringen sich …“ — ausgelöst
  von der eigenen Lochfüllung des Imports (A3).
- **Kundensicht:** Ein Klick auf „Kleine Teile entfernen“ erzeugt eine Warnung zu
  etwas ganz anderem. An großen Netzen kostet die Suche zudem Sekunden, die der
  Knopf nicht ankündigt.
- **Soll:** Die Suche gehört dem Reparaturschritt, den der Kunde als *Reparieren*
  aufruft; der Knopf „Kleine Teile entfernen“ sucht nicht mit (eigener Parameter
  oder `inspect_intersections` nur bei `self_intersections`/Vorgabe). Ursache A3
  beheben, dann erscheint die Warnung auch sonst nicht.

### D4 — „Das Modell ist nicht geschlossen“ verspricht, was „Reparieren“ gerade nicht konnte (niedrig, heute kaum erreichbar)

- **Ist:** `ingest.not_watertight` (`loader.py:1196-1212`) erscheint nur, wenn die
  Importreparatur **schon gescheitert** ist, sagt aber „„Reparieren“ schließt die
  offenen Stellen.“ *Reparieren und erneut versuchen* hängt dann einen
  Reparaturschritt an (`_repair_after_error`, `main_window.py:19858-19864`); der
  schließt mit denselben Mitteln nichts, und `SETTLED_BY` streicht den Befund nur
  nach `holes_filled`. `_repair_was_attempted` (`panels.py:658-685`) sieht nur
  Reparaturen **derselben** Transaktion vor dem Schritt — der Knopf bleibt also
  nach dem Klick stehen: ein Ring. In 22 Sonden nicht erreicht, weil der Import
  alles topologisch schließt.
- **Soll:** Text „Das Modell hat {count} offene Stellen, die sich nicht sicher
  schließen ließen.“ mit [Stellen zeigen] und — bei fehlendem Volumen — [Dicke
  geben]; *Reparieren und erneut versuchen* nur anbieten, wenn der Import mit
  `weld=False` lief (dann kann die Reparatur mehr). Test mit einem Netz, das die
  Importreparatur nicht schließt, als Datei in `tests/data/`.

### D5 — Die Rest-Texte zählen Kanten und nennen sie Stellen (mittel)

- **Ist:** `repair.py:1565-1586`: „An {edges} Kanten liegen weiterhin Flächen
  übereinander, und an {open_edges} Stellen ist das Netz offen.“ — `open_edges`
  ist die Zahl der Randkanten (ein Rohrende: 48), nicht der Stellen.
  „… das ist kein Loch, sondern eine Verzweigung.“ — Fachwort, kein Rat.
- **Soll:** Ringe zählen („{holes} offene Stellen“) und kurz:
  - `still_open`: „{holes} offene Stellen ließen sich nicht sicher schließen.“
  - `still_branching`: „An {edges} Kanten stoßen mehr als zwei Flächen zusammen.“
  - beide mit [Stellen zeigen]; Tooltip nennt die Kantenzahl.

### D6 — Die Import-Warnung „große Öffnung“ bleibt für immer (niedrig)

- **Ist:** Auch nach jeder weiteren Reparatur steht sie als Warnung da; es gibt
  keinen Befund, der sie erledigt. Mit A1 („Offen lassen“) verschwindet sie auf
  dem einen Weg; auf dem anderen („ja, die Fläche gehört dahin“) fehlt ein
  „Passt so“. Vorschlag: Stufe **Hinweis** statt Warnung, sobald der Kunde die
  Stelle einmal gezeigt bekommen hat — oder gleich als Hinweis mit Knopf, denn die
  Fläche ist beim Drucken kein Fehler, nur eine Rückfrage.

## Weg E — Formenerkennung an großen Modellen

**Klickfolge Ist:** Befund „fein vernetzt“ ist vorgewählt (Warnung, oberste Zeile
mit Knopf, `panels.py:_preselect`) → **Merkmale an dieser Stelle erkennen** (1) →
Statuszeile „Wählen Sie eine Oberfläche: klicken oder mit Pfeiltasten zielen und
Enter drücken. Escape beendet die Auswahl.“ (`local_recognition_flow.py:74-79`) →
Klick aufs Modell (2) → Dialog „Merkmale an dieser Stelle“ mit Liste → Merkmal
wählen (3) → *Merkmal bearbeiten …* (4) → Wert, *Übernehmen* (5); oder
*Nur Merkmale übernehmen* (4). Fünf Klicks sind für den Weg angemessen. Tastatur:
Pfeiltasten + Enter im Auswahlzustand, Umschalt fein — vorhanden.

### E1 — Der Knopf „Merkmale an dieser Stelle erkennen“ steht auch dort, wo alles erkannt ist (hoch)

- **Ist:** `dense_1m.stl` (1 310 720 Dreiecke, `sonden/dense_1m.txt`): einziger
  Befund „Dieses Modell ist fein vernetzt. Die Analysekarten lehnen ab;
  „Dreiecke verringern“ hilft.“ mit den Knöpfen **Merkmale an dieser Stelle
  erkennen** und *Dreiecke verringern*. Die volle Erkennung ist gelaufen (Grenze
  1,5 Mio., `perceive/local.py:25`); nur die Karten lehnen ab (0,9 Mio.,
  `maps.py:80`). Ursache: `FINDING_ACTIONS["ingest.very_large"]` hängt am Code
  (`panels.py:522`), und alle vier Textvarianten von `_too_fine`
  (`loader.py:1252-1281`) teilen ihn — Codex hat `RECOGNIZE_LOCAL` am 24.09. davor
  gesetzt.
- **Kundensicht:** Ein Knopf, dessen Wirkung der Satz nicht erklärt, an einem
  Modell, das seine Merkmale längst hat.
- **Soll:** Die Handlungen kommen aus dem Kern je Variante (`Finding.suggestions`
  geht in `actions_for` vor der Tabelle, `panels.py:612-617`): nur Karten begrenzt →
  (*Dreiecke verringern*); Erkennung begrenzt → (*Merkmal an einer Stelle erkennen*,
  *Dreiecke verringern*). Oder zwei Codes. Der Eintrag in `FINDING_ACTIONS` fällt dann.

### E2 — Zwei Zeilen sagen dasselbe (mittel)

- **Ist:** Über 1,5 Mio. Dreiecken ohne Vollerkennung stehen `ingest.very_large`
  („Dieses Modell ist sehr fein vernetzt. Analysekarten und vollständige
  Merkmalserkennung sind begrenzt; einzelne Merkmale können Sie lokal erkennen.
  „Dreiecke verringern“ hilft.“) und `perceive.too_large` („Die vollständige
  Merkmalserkennung wurde für dieses große Modell ausgelassen. Einzelne Merkmale
  können Sie lokal erkennen; „Dreiecke verringern“ ermöglicht die automatische
  Erkennung.“, `evaluate.py:2488-2500`) untereinander, mit denselben zwei Knöpfen
  (`panels.py:513`, `522`). Aus dem Code gelesen, nicht gefahren.
- **Soll:** Eine Zeile je Körper: „Das Modell hat {triangles} Dreiecke. Merkmale
  erkennt Solidon hier nur an einer gewählten Stelle, Farbkarten gar nicht.“ —
  [Merkmal an einer Stelle erkennen] [Dreiecke verringern]. `ingest.very_large`
  schweigt, wenn `perceive.too_large` für denselben Körper steht (oder umgekehrt).

### E3 — Eine abgelehnte Vollerkennung lässt sich nicht nachholen (hoch)

- **Ist:** Zwischen 1,5 und 5 Mio. Dreiecken fragt der Import (§21.1). Wer „nein“
  sagt, liest danach „… die vollständige Merkmalserkennung ist beim Laden nach
  Bestätigung möglich.“ (`loader.py:1262-1264`) — das Laden ist vorbei, die Antwort
  liegt im Dokument (`evaluate._full_recognition_allowed`, Aufzeichnung
  `evaluate.py:2267-2268`). In `app/ui/` gibt es keinen Weg, sie zu ändern
  (Suche nach `recognition_answer`, `full_recognition`: kein Treffer). Sackgasse bis
  zum Neuladen.
- **Soll:** Knopf **„Alle Merkmale erkennen (etwa {seconds} s)“** am Befund:
  setzt die gespeicherte Antwort auf „erlaubt“ als rücknehmbare Transaktion (nicht über
  `History.record_answers` — das ist laut `kern.md` Lesen ohne Lizenzgrenze), die Auswertung läuft mit Balken und
  Abbrechen. Text: „Merkmale wurden nur an gewählten Stellen erkannt.“

### E4 — Texte am großen Modell (mittel)

| Ist | Soll |
|---|---|
| „Dieses Modell ist fein vernetzt. Die Analysekarten lehnen ab; „Dreiecke verringern“ hilft.“ | „Das Modell hat {triangles} Dreiecke — zu viele für Farbkarten wie Wandstärke.“ [Dreiecke verringern] |
| Varianten mit „sehr fein vernetzt … sind begrenzt; …“ | siehe E2 |
| Tooltipwert `comfortable` = „Bequem: 900000“ | „Grenze für Farbkarten: 900 000“ |
| Knopf im Bericht „Merkmale an dieser Stelle erkennen“ — es ist noch keine Stelle gewählt | „Merkmal an einer Stelle erkennen“ (im Kontextmenü an einem Klick bleibt „an dieser Stelle“ richtig) |

### E5 — Die lokale Auswahl schweigt oder nennt den falschen Grund (mittel)

- **Ist:** `LocalRecognitionFlow.arm` (`local_recognition_flow.py:50-79`) kehrt
  **stumm** zurück, solange gerechnet wird oder noch kein Ergebnis steht (Z. 55-56):
  Der Klick im Bericht tut nichts. `begin` meldet bei laufender Rechnung
  „Wählen Sie eine sichtbare Oberfläche eines Dreiecksnetzes.“ (Z. 111-113) —
  derselbe Satz wie für einen exakten Körper (Z. 61), und „Dreiecksnetz“ ist
  Konstrukteurswort.
- **Soll:** Drei Gründe, drei Sätze: gerechnet wird → „Einen Moment — das Modell
  wird noch gerechnet.“; exakter Körper → der Satz aus `oberflaeche.md`
  (*Flächenbearbeitung beenden*); Klick daneben → „Klicken Sie auf das Modell.“

### E6 — Fehlergründe der lokalen Erkennung nennen zwei Wege und bieten einen (mittel)

`local_error` (`app/core/perceive/local.py:75-121`) gibt jedem Grund
`(CORRECT_INPUT, CANCEL)`; der Dialog (`local_recognition.py:628-648`) benennt
*Eingabe korrigieren* nur für `seed`, `ambiguous_seed`, `topology` in „Andere Stelle
wählen“ um und fokussiert sonst das Radiusfeld.

| Grund | Satz nennt | Knopf heute | Soll |
|---|---|---|---|
| `boundary` | Suchradius vergrößern **oder** andere Stelle | „Eingabe korrigieren“ (Radius) | [Suchradius vergrößern] [Andere Stelle wählen] |
| `no_feature` | andere Stelle **oder** Suchradius | „Eingabe korrigieren“ (Radius) | [Andere Stelle wählen] [Suchradius vergrößern] |
| `budget` | kleinerer Bereich **oder** Dreiecke verringern | „Eingabe korrigieren“ (Radius) | [Suchradius verkleinern] [Dreiecke verringern] |
| `topology` | Netz reparieren **oder** andere Stelle | „Andere Stelle wählen“ | [Andere Stelle wählen]; „Reparieren Sie das Netz“ streichen oder [Reparieren] anbieten |
| `seed`, `ambiguous_seed` | Stelle erneut wählen | „Andere Stelle wählen“ | passt |

„Suchradius vergrößern“ darf den Wert gleich um die Hälfte erhöhen und neu suchen
— ein Klick statt Fokus, Tippen, Warten.

### E7 — „Radius“, „Suchradius“, „vollständige Merkmale“ (niedrig)

- Feld heißt „Suchradius“ (`perceive/ops.py:21`), Kopfsatz und Zustände sagen
  „Radius“ (`local_recognition.py:161`, `217`, `294`). Überall „Suchradius“.
- „Vollständige Merkmale“, „1 vollständiges Merkmal gefunden.“
  (`local_recognition.py:217-220`, `313`) — „vollständig“ ist eine Prüfgröße des
  Kerns. Kunde: „Gefundene Merkmale“, „1 Merkmal gefunden.“, und für den
  Radiusfall „Kein ganzes Merkmal im Suchradius. Vergrößern Sie ihn.“

## Priorisierte Liste

| Rang | Befund | Schwere | Kern der Abhilfe |
|---|---|---|---|
| 1 | **C1** „Eingabe korrigieren“ führt nicht in das Feld; Menüweg im Satz | hoch | Eigene Handlung „Überschneidungen auflösen“ (1 Klick, ohne Dialog); mindestens `values["field"]` |
| 2 | **A2** Offene Fläche wird zu Körper ohne Volumen; „Offene Fläche schließen“ danach gesperrt | hoch | Import schließt nicht ohne Volumen, Knopf „Dicke geben“ (Entscheidung Robert) |
| 3 | **A1** „Große Öffnung“ ohne Ort, ohne Knopf, ohne Rückweg | hoch | Ort am Befund, `LoadParams.mend`, Knöpfe „Stelle zeigen“ / „Offen lassen“ |
| 4 | **D1** Rat „Aktivieren Sie …“ bleibt neben „aufgelöst“ | hoch | zwei Einträge in `SETTLED_BY` |
| 5 | **D2** „mehrere Teile“ + „Zerlegen“ nach „Kleine Teile entfernen“; Warnung nach eigener Handlung | hoch | Teilezahl am Ende neu melden; `components_removed` als Hinweis mit Strg+Z |
| 6 | **A3** Importreparatur verändert Volumen still (Flosse −12,5 %), erzeugt eigene Durchdringungen | hoch (Kern) | an Reparaturkern; Volumenwarnung mit Zahl |
| 7 | **E3** Abgelehnte Vollerkennung nicht nachholbar | hoch | Knopf „Alle Merkmale erkennen (etwa N s)“ |
| 8 | **E1** „Merkmale an dieser Stelle erkennen“ auch bei voller Erkennung | hoch | Handlungen je Textvariante aus dem Kern |
| 9 | **B1** Von der Netzfehlerkarte kein Weg zur Reparatur | hoch | Knopf in der Analyseleiste je Stufe |
| 10 | **C2** Dialog *Reparieren*: vorn das Überflüssige, Vorgabe wirkt nach Import fast nie | hoch (Entscheidung) | vorn Überschneidungen + Kleinstteile; ggf. Überschneidungen standardmäßig an |
| 11 | **A5** Ineinandersteckende Teile beim Import unerkannt, Knopf „Zerlegen“ | mittel | Hüllquader-Vorfrage, Knopf „Zu einem Körper verschmelzen“ |
| 12 | **A4** Zu viele Infozeilen, Fachwörter, „0.00 mm“ | mittel | eine Sammelzeile je Ladeschritt, Kundentexte |
| 13 | **C3/C4** Parameter- und Befundtexte, Grammatikfehler „Vereinigt sich überlappende Teile“ | mittel | Tabellen oben |
| 14 | **C5** „Formdetails nicht mehr wiederzuerkennen“ nach jeder Reparatur | mittel | nur melden, wenn ein Verbraucher betroffen ist |
| 15 | **E6** Lokale Fehlergründe: zwei Wege genannt, einer angeboten | mittel | zweiter Knopf, Beschriftung „Suchradius vergrößern“ |
| 16 | **E2** Zwei gleiche Zeilen am großen Modell | mittel | eine Zeile je Körper |
| 17 | **E5** Lokale Auswahl stumm bei laufender Rechnung, „Dreiecksnetz“ | mittel | drei Gründe, drei Sätze |
| 18 | **D3** „Kleine Teile entfernen“ fördert Überschneidungswarnung | mittel | Suche nur beim eigentlichen *Reparieren* |
| 19 | **D5** Rest-Texte zählen Kanten als Stellen | mittel | Ringe zählen, kurze Sätze |
| 20 | **A6** `voids_unreadable` nennt „Reparieren“ ohne Knopf | mittel | Knopf oder Satz streichen |
| 21 | **B2** Legende „offene/verzweigte Kante, Durchdringung“ | mittel | „Loch, überzählige Fläche, Überschneidung“ |
| 22 | **E4/E7** Texte am großen Modell, Radius/Suchradius | niedrig | Tabellen oben |
| 23 | **D4** `not_watertight`-Ring (heute unerreichbar) | niedrig | Text ehrlich, Knopf nur bei `weld=False`, Testdatei |
| 24 | **D6**, **B3** Dauerwarnung; violettes Modell auf der Karte | niedrig | Hinweisstufe; Stufe 0 in Körperfarbe |

## Fragen an Robert (Leitprinzip 6)

1. **A2:** Soll der Import eine Fläche ohne Dicke offen lassen und „Dicke geben“
   anbieten (V1), oder weiter schließen und nur die Sperre von *Offene Fläche
   schließen* lösen (V2)?
2. **C2:** Soll *Reparieren* Überschneidungen standardmäßig auflösen? Folge: ein
   Klick weniger an jedem durchdrungenen Modell; Teile, die sich überschneiden,
   werden zu einem Körper (Strg+Z und *In Einzelteile zerlegen* bleiben).
3. **A1:** Ladeparameter „Offene Stellen schließen“ (Vorgabe an) als Rückweg für
   eine ungewollt erfundene Fläche — einverstanden?

## Grenzen dieser Durchsicht

Nur gelesen und ohne Fenster gesondert gemessen; Fenster- und Leistungsprüfungen
laufen beim Release. Nicht gefahren: Vollerkennungsfrage zwischen 1,5 und 5 Mio.
Dreiecken (E2, E3 aus dem Code), Darstellung der Karte im gebauten Fenster (B3),
Tastaturweg durch den Reparaturdialog. Klickzahlen zählen Klicks des Kunden;
das Warten auf die Vorschau vor *Übernehmen* ist nicht mitgezählt.

**Hinweis zum Stand:** Während der Durchsicht hat eine parallele Sitzung
`app/core/scene/evaluate.py` geändert (neu `_recognition_choice`, Z. 2212; ruff meldet
dort F841 `choice` in Z. 2501). Die Zeilenangaben zu `evaluate.py` oben stammen vom
Beginn der Durchsicht und sind um bis zu rund 30 Zeilen verschoben
(`SETTLED_BY` jetzt Z. 1188, `perceive.too_large` Z. 2527). Ob die Änderung E3
berührt, vor dem Umsetzen am Code prüfen.
