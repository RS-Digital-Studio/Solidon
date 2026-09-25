# Review „Dreieckserkennung und Reparatur" (Claude, 24.09.2026)

Nur lesend. Umfang laut Auftrag (repair.py, intersections.py, mesh.triple_products/enclosed_volume/signed_volume,
boolean/difference, ops.RepairParams, loader Schritte 2/4/4b/5, ingest/ops mend, maps Netzfehlerkarte,
features.detect_curved_faces, migrations 34→35, evaluate SETTLED_BY/CLOSED_STATE_CODES/ONE_PIECE_CODES/_without_outdated,
cache 28, errors, main_window/dialogs/panels/labels, Kataloge, Tests, Doku).

Format je Befund: Schwere, Datei:Zeile, was falsch ist, Fall, Vorschlag.

Stand: `repair.py` sha1 `38c6de81`, `loader.py` `c064f6a5` (25.09.2026, 00:06). Die Hauptsitzung hat während
der Durchsicht weiter geändert; Zeilenangaben können um ein, zwei Zeilen wandern. Die Sonden
`review-schalen`, `review-import` und `review-flach` sind am Schluss am genannten Stand wiederholt und
unverändert (`*-nachlauf.txt`). Zeiten sind unter Last gemessen (paralleles Tor) und damit Obergrenzen.

## Befunde (fortlaufend, Reihenfolge des Findens; Sortierung nach Schwere am Ende)

### R1 — niedrig — Befundwert `reason` steht als englischer Code im Tooltip (Regel 20)

- Ort: `app/core/geom/repair.py:3119` (`values={"reason": blocked}` an `repair.self_intersections_skipped`)
  und `:3134` (`values={"reason": blocked or "kernel"}` an `repair.self_intersections_unresolved`);
  angezeigt über `app/ui/panels.py:5102` (`value_line` je Wert), `labels.choice_label` kennt die Codes nicht.
- Fall (Sonde `sonden/review-labels.py` → `review-labels.txt`): `value_line("reason", …)` ergibt
  „Grund: open", „Grund: winding", „Grund: self", „Grund: cavity", „Grund: kernel" (nur „flat" wird
  zufällig über einen fremden `_CHOICE_NAMES`-Eintrag zu „Flach"). Tooltip und Bildschirmleser des Befunds
  zeigen damit Bezeichner statt Kundensprache — in allen sechs Sprachen englisch.
- Vorschlag: Den Grund nicht als Wert führen (der Satz sagt ihn schon: „erst an einem geschlossenen Modell",
  „solange Außenseiten gegeneinander zeigen") — oder als eigener Code-Zweig ohne `values`, wenn ein Test
  ihn lesen muss, über `Finding.code`/`details` statt `values`. Alternativ `_CHOICE_NAMES` um übersetzte
  Einträge ergänzen; dann aber „open" nicht global (Kollision mit anderen Auswahlwerten).

### R2 — niedrig — „Toleranz: 0,00 mm" am Befund `weld_skipped`

- Ort: `repair.py:2684` (`values={"tolerance_mm": weld_tolerance(...)}`), `loader.py:1009`
  (`values={"tolerance_mm": tolerance}`).
- Fall: Die Schweißtoleranz liegt um 10⁻⁴…10⁻⁶ mm; `value_line("tolerance_mm", 0.000123)` → „Toleranz:
  0,00 mm" (Sonde `review-labels.txt`). Der Wert sagt dem Kunden nichts und liest sich wie „keine Toleranz".
  Nicht neu (HEAD schrieb `format_length` mit demselben Ergebnis), aber die Stelle wurde umgebaut.
- Vorschlag: Wert weglassen oder mit einer eigenen Endung über `labels.length_bound` (behält zwei geltende
  Ziffern, `units.format_length_bound`) anzeigen.

### R3 — mittel — Globales Umstülpen dreht den richtigen Hohlraum eines anderen Teils mit

- Ort: `app/core/geom/repair.py:398–403` (`turn_shells_outward`: `inverted = fsum(volumes) < 0` → `body.invert()`
  über **alle** Schalen), danach `:409–417` richtet nur freie Schalen zurück.
- Fall (Sonde `sonden/review-schalen.py` A → `review-schalen.txt`): ein richtiger Hohlkörper (außen +8 000,
  Hohlraum −1 000) und daneben ein getrennter, umgestülpter Würfel 22³ (−10 648). Summe −3 648 → alles wird
  umgedreht, der freie Außenwürfel wieder zurück — der **Hohlraum bleibt +1 000**. Ergebnis: Schalen
  [1 000, 8 000, 10 648], Volumen 19 648 statt 17 648, dazu `repair.part_inside` „Ein Teil liegt ganz in einem
  anderen" über einer Stelle, die vorher richtig war. Derselbe Weg läuft beim Import (`loader.py` Schritt 4).
- Warum es zählt: Die Reparatur macht aus einem korrekten Modell ein mehrdeutiges und meldet danach ihre eigene
  Verschlechterung als Befund des Modells.
- Vorschlag: Die Gesamtumkehr durch eine Umkehr **je Verschachtelungsbaum** ersetzen: Für jede freie Schale
  mit negativem Volumen sie selbst und alle Schalen, die in ihr liegen (`_Shells.around` + `inside`), gemeinsam
  drehen; freie positive Schalen samt Inhalt unberührt lassen. Das deckt den bisherigen Fall „ganzer
  Hohlkörper verkehrt" (außen −, innen +) weiter ab. Test: der Fall A als Gegenprobe (heute rot).

### R4 — mittel — „Teil im Teil" meldet ein gefangenes Teil in einem Hohlraum

- Ort: `repair.py:423–444` (`parts_inside_parts`: fragt nur, ob die positive Schale in einer **positiven**
  Schale liegt, nicht, ob sie dort im Material liegt), gleicher Befund aus `loader.py` Schritt 5.
- Fall (Sonde B): Kugel r 20 mit Hohlraum r 15 und einer freien Kugel r 5 darin (Rassel, Kugel im Käfig,
  „print in place") — alle Schalen richtig gewickelt. `repair()` meldet `repair.part_inside` „Ein Teil liegt
  ganz in einem anderen. Slicer drucken es je nach Einstellung hohl oder voll." Das stimmt nicht: Nonzero
  und Even-Odd drucken die kleine Kugel beide voll und den Hohlraum beide leer (Umlaufzahl dort 0).
- Warum es zählt: Eine Warnung im Normalfall eines absichtlich gebauten Teils nimmt dem echten Befund die
  Wirkung (`operationen.md`, „Eine Warnung, die im Normalfall kommt, ist keine Warnung mehr").
- Vorschlag: Gemeldet wird nur, wenn der Stichpunkt der Schale **im Material** der übrigen liegt: Summe der
  Vorzeichen aller umschließenden Schalen (positiv +1, negativ −1) ≥ 1. Dieselbe Tiefenrechnung trägt den
  Fix von R3. Test: Kugel im Hohlraum ohne Befund, Würfel mit falsch gewickelter Innenschale mit Befund.

### R5 — mittel — Nach dem Entfernen der Splitter bleibt ihre Randbilanz stehen: falsche „Fläche ohne Dicke" und verdeckte offene Stellen

- Ort: `repair.py:2844` (`remove_open_splinters` **nach** dem Füllen) gegen `:2916–2935` (`sheet`,
  `open_edges - filled.flat_edges` aus `_filled_rounds`, gezählt **vor** dem Entfernen).
- Fall (Sonde C): Würfel 20 mm + 20 lose Einzeldreiecke zu 1,1 mm² (jedes unter 0,1 % des Würfels):
  Ergebnis ein geschlossener Würfel, Bericht trotzdem `repair.no_thickness` „Ein Teil des Modells ist eine
  Fläche ohne Dicke." mit *Dicke geben* — die Fläche gibt es nicht mehr; *Dicke geben* endet an
  `ALREADY_CLOSED`. Sonde C2: dazu ein Zylinder mit einem 240°-Fenster, das offen bleibt (allein: 87 offene
  Kanten) → `repair.still_open` meldet nur noch **27**; mit 30 Splittern (90 Kanten) fiele der Befund ganz weg
  (`max(0, 87 − 90)`), und der Bericht schwiege über ein offenes Modell.
- Doku gegen Code: `app/core/geom/CLAUDE.md` sagt „lose offene Splitter … fallen **vorher** weg
  (`remove_open_splinters`)" — im Code laufen sie **nach** `_filled_rounds`, und genau daraus entsteht der
  Fehler.
- Einschränkung (nachgelesen): Im Dokumentweg streicht `evaluate._without_outdated` den falschen
  `no_thickness` aus Fall C, weil der Körper am Ende dicht ist — dort bleibt der Fehler auf `repair()` direkt
  (Agent, Kommandozeile, Tests) beschränkt. Fall C2 (Körper bleibt offen) trifft auch den Prüfbericht: falsches
  „Fläche ohne Dicke" mit *Dicke geben* **und** zu kleine oder fehlende `still_open`-Zahl.
- Vorschlag: `flat_edges`/`flat_area` nach `remove_open_splinters` neu bestimmen — am einfachsten die flachen
  offenen Teile am Endstand zählen (offene Komponente mit |V| ≤ `EPS_GEOM`·A) statt die Füllbilanz
  weiterzutragen; oder `remove_open_splinters` gibt die entfernten Kanten/Flächen zurück und sie werden
  abgezogen. Test: Fall C ohne `no_thickness`, Fall C2 mit 87 offenen Kanten.

### R6 — mittel — *Dicke geben* an „Ein Teil des Modells ist eine Fläche ohne Dicke" verändert die geschlossenen Teile mit

- Ort: `repair.py:2918–2928` (`GIVE_THICKNESS` auch im Teil-Fall, `flat_area < 0.5 · total`),
  `app/ui/main_window.py:20048` (`_give_thickness_after_error` → `thicken` am ganzen Körper),
  `app/core/geom/mesh_ops.py:1687` (`_thickened` versetzt **alle** Ecken und legt **jede** Fläche als
  Innenhaut an).
- Fall (Sonde D): Würfel 20 mm + ein flaches Blatt 12 × 12 daneben → `repair.no_thickness` „Ein Teil …" mit
  *Dicke geben* (primär). `_thickened(…, 0,8)` ergibt Schalen [115,2, 6 941,9, 8 000]: Das Blatt bekommt
  seine Wand, der **Würfel eine zweite, positive Innenschale** (nach `fix_normals`) — Volumen 15 057 statt
  8 115; ein Even-Odd-Slicer druckt den Würfel damit als 0,46-mm-Hülle. Im Dialog und von außen ist davon
  nichts zu sehen.
- Warum es zählt: Der neue Knopf führt vom Befund eines kleinen Blatts in eine Operation, die das Hauptteil
  still verdoppelt. Rücknehmbar, aber niemand bemerkt es.
- Vorschlag: `thicken` nur auf die offenen Komponenten anwenden und geschlossene Teile unverändert
  übernehmen (die Zusage des Docstrings „Ein Körper, der schon einer ist, bekommt keine zweite Haut" gilt
  dann je Teil), oder `GIVE_THICKNESS` nur anbieten, wenn jedes Teil des Körpers flach ist. Test: Würfel +
  Blatt, nach *Dicke geben* behält der Würfel 8 000 mm³ und eine Schale.

### R7 — mittel — Baugruppen-Import: Der Ort der großen Öffnung wandert beim gemeinsamen Aufsetzen nicht mit

- Ort: `app/core/ingest/ops.py:483–519` (`_group_on_bed` verschiebt die Körper, nicht die `Finding.location`);
  der Ortsausgleich steht nur in `loader.normalise` Schritt 6 (`loader.py:1209–1225`), und der läuft bei einer
  Baugruppe mit `place_on_bed=False, centre=False` (`ops.py`, Aufruf von `normalise`).
- Fall (Sonde `sonden/review-import.py` E → `review-import.txt`): zwei Körper, einer ohne Oberseite, bei
  (100 | 100 | 50). Befund `repair.wide_hole_filled` mit Ort (100 | 100 | 60); nach `_group_on_bed(…,
  place_on_bed=True, centre=True)` liegt der Körper bei x −27,5…−7,5, der Ort bleibt (100 | 100 | 60). Der
  erste Import einer Datei setzt beides (`ingest/plan.py:316`, `:373`) — jede 3MF-Baugruppe mit einer großen
  Öffnung (oder einem `repair.part_inside`) zeigt damit ins Leere. `dateiformat.md` sagt „Ein Ort wandert
  beim Aufsetzen mit dem Körper" ohne diese Ausnahme.
- Vorschlag: In `_group_on_bed` die Orte aller Befunde um denselben `offset` verschieben — am besten über eine
  gemeinsame Hilfsfunktion `moved_findings(findings, offset)`, die Schritt 6 ebenfalls benutzt (sonst zwei
  Herleitungen derselben Regel, `zwillinge.md`). Test: Baugruppe mit offenem Körper, Ort liegt nach dem Import
  im Hüllquader des Körpers.

### R8 — niedrig — Schritt 4b richtet die Außenseiten auch mit „Außenseiten angleichen: aus"

- Ort: `app/core/ingest/loader.py:1152–1164` (`repair_mesh(..., normals=True)` unabhängig von `unify_normals`).
- Fall (Sonde F): offener, einheitlich verkehrt gewickelter Würfel, `normalise(..., unify_normals=False)` →
  Befunde `repair.wide_hole_filled`, `repair.holes_filled`, **`repair.normals_flipped`** („Die Außenseiten
  wurden angeglichen."), Volumen +8 000. Der Kunde hat genau das am Ladeschritt abgeschaltet.
- Vorschlag: `normals=unify_normals` übergeben; der Kommentar „die Außenseiten aber doch" gilt dann für den
  eingeschalteten Fall. Ebenso die Teil-im-Teil-Frage in `repair()` nur mit `normals` (ist dort schon so).

### R9 — hoch — `_fill_jobs` ist quadratisch in der Zahl der Ringe: 1 500 Dreieckslöcher kosten 78 s statt 0,06 s

- Ort: `app/core/geom/repair.py:1495–1516` (Bandpaarung: jedes Paar gleich langer, nicht zusammengelegter
  ebener Ringe ruft `_band_between`, und das rechnet je Aufruf `exact_centre` und `_ring_normal` beider Ringe
  neu, `:1310–1313`), dazu `:1454–1480` (`holes_of`: jeder ebene Ring gegen jeden, je Paar `cast` +
  `units.dot3` in Python).
- Fall (Sonde `sonden/review-fuellzeit.py` G1, Profil `review-fuellzeit-profil.py` → `*.txt`): Icosphäre
  (81 920 Dreiecke) ohne 1 500 einzelne, nicht benachbarte Dreiecke — jeder Ring hat drei Ecken, ist damit
  eben und gleich lang wie alle anderen. `_fill_jobs` **77,9 s**, `_fill_loops` 68 s; HEADs
  `fill_boundary_loops` am selben Netz **0,06 s**, gleiches Ergebnis (dicht, gleiches Volumen). Reihe:
  100 Ringe 0,33 s, 200 1,65 s, 400 7,26 s (79 800 Aufrufe `_band_between`, davon 10,1 s in `_ring_normal`);
  ohne Bandpaarung 0,02/0,07/0,22 s — der Rest ist die quadratische `holes_of`-Schleife.
- Warum es zählt: Derselbe Weg läuft beim **Import** (Schritt 4b) — ohne Abbruch (R10) und ohne
  Fortschritt zwischen 0,7 und 0,8. Ein heruntergeladenes Netz mit einigen hundert fehlenden Dreiecken
  (Exporter, die Splitter verwerfen; dezimierte Scans) hängt damit Sekunden bis Minuten, wo es vorher sofort
  geladen war. §31-Budget verletzt, ohne Leistungstest, der es fängt.
- Vorschlag: Mitte, Normale und Radien je Ring **einmal** berechnen (die Liste `shapes` hat Mitte und Normale
  schon) und an `_band_between` übergeben; Kandidaten vorher billig sieben — gleiche Eckenzahl **und**
  `|n_a × n_b| ≤ BAND_PARALLEL` **und** Mittenversatz entlang der Normale —, am besten über einen Schlüssel
  (gerundete Achsgerade je Ring, dann nur innerhalb eines Eimers paaren). Dieselbe Vorsortierung für
  `holes_of` (nur gegenläufige Normalen derselben Ebene, etwa nach gerundetem Ebenenabstand gruppiert).
  Leistungswächter (Release) an G1: 1 500 Dreieckslöcher unter 1 s.

### R10 — mittel — Das Schließen beim Import lässt sich nicht abbrechen; `_fill_jobs` fragt den Abbruch nie

- Ort: `app/core/ingest/loader.py:861` (`normalise` hat keinen `cancelled`-Parameter), `:1153`
  (`repair_mesh(...)` ohne `cancelled`/`progress`), `app/core/ingest/ops.py` (`load` reicht `ctx.cancelled`
  nicht weiter — `grep cancel` in beiden Dateien: kein Treffer); `app/core/geom/repair.py:1410`
  (`_fill_jobs` ohne Abbruchpunkt, auch wenn *Reparieren* das Token durchreicht — `_fill_loops` fragt erst
  **nach** `_fill_jobs` je Auftrag).
- Fall: G1 aus R9 — 78 s in `_fill_jobs`, im Import ohne Abbruch und ohne Fortschritt; *Abbrechen* greift
  erst danach. Bericht B13 (Reparaturkern) hatte `normalise(..., cancelled=)` bereits als Fix genannt; umgesetzt
  ist nur der Abbruch im Ohrenschneiden.
- Warum es zählt: Bauplan §15.6 „Eine laufende Berechnung ist jederzeit abbrechbar". Seit Schritt 4b die
  ganze Füllkette fährt, ist der Import der längste Weg ohne Abbruchpunkt.
- Vorschlag: `normalise(..., cancelled=)` und `load` reicht `ctx.cancelled` durch (§15.6); `repair_mesh(...,
  cancelled=cancelled, progress=…)` in Schritt 4b; in `_fill_jobs` je äußerem Ring (oder je 1 000 Paaren)
  `raise_if_cancelled()`. Test: ein Token, das ein Rückruf beim ersten Fortschritt setzt, bricht den Import
  eines Netzes mit vielen Löchern vor dem Ende ab.

### R11 — mittel — RM-187: Die neuen Füllwege rechnen mit `np.hypot`/`np.einsum` und stehen in keinem `_WAYS`-Weg

- Ort: `repair.py:1231–1239` (`_bridged_holes`: Brückenziel über `np.argsort(np.hypot(...))` — bei
  symmetrischen CAD-Ringen gibt es Gleichstände, und das Ziel entscheidet die Triangulierung),
  `:1338–1339` (`_band_between`: Radien über `np.hypot`, entscheidet ob ein Band entsteht);
  `app/core/perceive/features.py:8668` (`_point_inside_shell`: `np.einsum` in der Parallelprobe) — seit
  dieser Änderung entscheidet er in `turn_shells_outward`, ob eine Schale gedreht wird.
  `tests/test_platform_identity.py` führt `hypot` selbst unter `_NUMPY_TRANSCENDENTAL` (verrauscht) und
  `einsum` unter `_BLAS_LIKE`.
- Fall (Sonde `sonden/review-wege.py` → `review-wege.txt`): Der Weg `import_repair` ruft
  `_band_between` 4 032-mal **ohne** ein Band, `_bridged_holes` **nie**, `_point_inside_shell` **nie**;
  `repair_selfint` und `thicken` keinen davon. Die zwei Plattformwege sind grün (`review-plattform.txt`),
  beweisen für Band, Brücke und Schalenwendung aber nichts.
- Vorschlag: `np.hypot(a, b)` durch `np.sqrt(a * a + b * b)` ersetzen (Grundrechenarten und `sqrt` sind
  korrekt gerundet), `einsum` in `_point_inside_shell` elementweise; drei Wege in `_WAYS` aufnehmen —
  Lochplatte ohne Bohrungswand (Band), Lochplatte ohne Oberseite (Brücken), Hohlkörper mit umgestülpter
  Außenschale (Strahl in `turn_shells_outward`). Nebenbei belegt die Zahl 4 032 bei 131 Ringen R9 auch am
  Testnetz.

### R12 — mittel — *Reparieren* mit den heutigen Vorgaben kostet an großen Netzen 10–90 s, fast ganz in der Schnittsuche, meist ohne Wirkung

- Ort: `app/core/geom/ops.py:725` (`inspect_intersections=True` für jeden Reparaturschritt),
  `repair.py:3047` (`crossings_of` mit `intersection_budget` = max(2 Mio., 12 · Dreiecke)).
- Fall (Sonde `sonden/review-gross.py` → `review-gross.jsonl`/`.log`, Stand `repair.py` 38c6de81, **unter
  Last** — das Tor der Hauptsitzung lief parallel, Zahlen sind Obergrenzen):

  | Modell | Dreiecke | Import | *Reparieren* | davon Suche | Ergebnis |
  |---|---|---|---|---|---|
  | Besenhalter | 59 740 | 0,2 s | 9,7 s | 9,4 s | nur `self_intersections_incomplete` |
  | Gähnende Katze | 452 301 | 6,5 s | 14,0 s | 11,8 s | `skipped` (offen) + `still_open` |
  | Spiderman | 885 570 | 4,4 s | 27,3 s | 22,0 s | `self_crossing`, unverändert |
  | Piratenschiff obj_15 | 1 223 836 | 9,7 s | 39,2 s | 33,9 s | `self_crossing`, unverändert |
  | Mausoleum Dragon | 2 330 374 | 16,2 s | 89,2 s | 69,9 s | nichts zu tun |

  Die vergebliche Vereinigung aus B18 ist weg (Piratenschiff 77 → 39 s), die Suche bleibt. An der Katze sucht
  sie 12 s an einem **offenen** Netz, obwohl danach feststeht, dass nichts aufzulösen ist (`skipped`); am
  Besenhalter endet sie nach 9 s ohne Aussage.
- Warum es zählt: *Reparieren* ist der Weg aus vielen Fehlerdialogen („Reparieren und erneut versuchen") und
  läuft bei jeder Neuauswertung ohne Cache-Treffer erneut (neues Netz nach dem Füllen, Cache-Version 3 beim
  Öffnen alter Projekte). Die Suche ist abbrechbar und meldet Fortschritt — aber eine Minute für „nichts zu
  tun" ist keine Reparatur, die man gern anklickt.
- Vorschlag: (1) Am offenen oder verkehrt gewickelten Netz vor der Suche aussteigen, wenn aufgelöst werden
  soll — `_intersections_resolvable` braucht die Suche für „open"/„winding"/„flat" nicht; die Diagnose kann
  dort mit dem Kartenbudget (`DEFECT_MAP_PAIRS`) laufen. (2) Über `MAP_LIMIT_TRIANGLES` die Suche nur mit dem
  Kartenbudget und dem Befund „nicht vollständig geprüft" samt *Überschneidungen auflösen* als ausdrücklicher
  Handlung. (3) Leistungswächter (Release) an zwei Korpusnetzen. (4) Bleibt es in diesem Schritt, gehört der
  Rest von B18 ins Register von `ROADMAP.md` — dort steht er heute nicht (nur RM-239/RM-240 sind neu).

### R13 — niedrig — „Teil im Teil" bleibt ohne Handlung

- Ort: `repair.py:447–464` (`part_inside_finding` ohne `suggestions`), `app/ui/panels.py:363 ff.`
  (`FINDING_ACTIONS` ohne Eintrag `repair.part_inside`).
- Fall: Test `test_a_part_inside_a_part_is_named_and_left_as_it_is` — Warnung „Ein Teil liegt ganz in einem
  anderen. Slicer drucken es je nach Einstellung hohl oder voll." mit Ort, aber `actions_for` liefert `()`.
  Der Kunde erfährt eine Mehrdeutigkeit (Regel 21: fragen) und bekommt keinen Weg, sie aufzulösen.
- Vorschlag: Mindestens *In Einzelteile zerlegen* (`SPLIT_BODIES`, dann ist das innere Teil wähl- und
  löschbar); besser zwei Handlungen, die die Frage beantworten — „Als Hohlraum drehen" (innere Schale umdrehen,
  eine Operation) und „Inneres Teil entfernen". Der Ort allein ist keine Handlung.

### R14 — niedrig — Zwilling: Ob eine Schale ein Hohlraum ist, rechnet die Erkennung weiter am Ursprung und über `einsum`

- Ort: `app/core/perceive/features.py:8483–8503` (`_enclosed_volume`: `np.einsum(...).sum()`, ursprungsbezogen)
  für die Hohlraumerkennung (`:8872`) gegen `repair._shell_volumes` (`repair.py:312`, körpernah, elementweise).
  Beide beantworten „positiv oder negativ je Schale", und seit dieser Änderung teilen sie sich den Strahltest
  `_point_inside_shell`.
- Fall: Der Würfel von 1 mm bei 10⁸ mm aus `test_a_small_body_far_from_the_origin_stays_the_right_way_out` —
  die Reparatur rechnet ihn richtig, die Erkennung an derselben Stelle mit dem Volumen aus Rundung (Bericht
  Reparaturkern B16: −5,5·10⁷ mm³ bei 10⁸). Auf ARM kann `einsum` mit FMA das Vorzeichen einer dünnen Schale
  anders entscheiden (RM-187).
- Vorschlag: Eine Funktion für beide (`mesh.shell_volumes(body, labels)` aus `_shell_volumes`), die Erkennung
  ruft sie; sonst Registerpunkt nach `zwillinge.md`.

### R15 — mittel — Das Einlesen löscht offene Splitter; §17.1 sagt „Kleinstteile melden statt still zu löschen"

- Ort: `repair.py:2844` (`remove_open_splinters` in jedem `repair(holes=True)`) über `loader.py:1153`
  (Schritt 4b, `mend=True` als Vorgabe); `remove_small_components` sagt im Docstring selbst „nur auf
  Nachfrage, nie beim Hereinkommen (§17.1)".
- Fall: Ein offenes Netz mit einem losen Flächenstück unter 0,1 % der größten Komponente (etwa eine offene
  Augenfläche, ein Aufkleber) verliert es beim Import; der Bericht sagt „Ein loser Splitter wurde entfernt."
  (Hinweis). Das ist gemeldet, aber gelöscht — und §17.1 Schritt 5 unterscheidet genau das.
- Vorschlag: Entscheidung Robert einholen und Bauplan §17.1 nachziehen, oder beim Import nur melden
  (`ingest.small_components` mit *Kleinstteile entfernen*) und das Entfernen der ausdrücklichen Reparatur
  überlassen. Solange die Frage offen ist: Registerpunkt.

### R16 — niedrig — Nach einer Auflösung fehlt der Hinweis „Suche unvollständig"; die Zusage „vollständig geprüft" stimmt dann nicht

- Ort: `repair.py:3077–3092` (`return` nach `repair.self_intersections`, vor dem `if not complete:`-Zweig
  `:3138`); `evaluate.py` `SETTLED_BY["repair.self_intersections_incomplete"] = {"repair.self_intersections"}`
  mit dem Kommentar „Vollständig geprüft heißt die Auflösung auch: nichts mehr offen"; `geom/CLAUDE.md`
  „Nur eine vollständig geprüfte direkte Float64-Vereinigung gilt als behoben".
- Fall: Ein Netz über dem Paarbudget (Besenhalter-artig, 54 Paare je Dreieck) mit zwei überlappenden Schalen:
  Die Suche endet vorzeitig, findet Schnitte zwischen Schalen, die Vereinigung gelingt, `_still_crosses`
  prüft nur um die **gefundenen** Schnitte — Bericht „Überschneidungen wurden aufgelöst." ohne den Hinweis,
  dass die Suche nicht alles gesehen hat; eine Eigenkreuzung im ungeprüften Teil bleibt unerwähnt und löscht
  zusätzlich den früheren `incomplete`-Hinweis über `SETTLED_BY`.
- Vorschlag: Den `incomplete`-Hinweis auch nach Erfolg anhängen (oder `repair.self_intersections` nur bei
  vollständiger Suche melden), und den `SETTLED_BY`-Eintrag an „vollständig" binden.

### R17 — niedrig — *Offen lassen* öffnet alle Stellen, nicht nur die große Öffnung

- Ort: `app/ui/main_window.py:20033–20046` (`mend=False` am Ladeschritt, `fill_holes=False` am
  Reparaturschritt); `repair.py:2765` (unter `holes` hängen auch Verzweigungen und Nähte).
- Fall: Import mit einer großen Öffnung und zehn kleinen Löchern (dazu eine T-Naht): Befund „Eine große
  Öffnung wurde mit einer neuen Fläche geschlossen." → *Offen lassen* → der Ladeschritt rechnet ohne 4b, alle
  elf Stellen bleiben offen, Nähte und überzählige Flächen bleiben auch, danach steht
  `ingest.not_watertight` mit *Reparieren und erneut versuchen* — das die große Öffnung wieder schließt. Bei
  einer Baugruppe gilt `mend=False` für jeden Körper der Datei. Das ist die Entscheidung vom 24.09.2026
  („setzt am Ladeschritt `mend=False`"), aber derselbe Einwand, den die Hauptsitzung bei
  `_remove_small_parts` selbst formuliert: „ein Knopf, der mehr tut, als er sagt".
- Vorschlag: Mindestens der Knopf- oder Tooltiptext sagt „ohne Lochschließen neu einlesen"; besser ein
  Parameter, der nur Öffnungen über `FILL_LOOP_SHARE` offen lässt (die Warnschwelle gibt es schon), damit
  kleine Löcher, Nähte und Verzweigungen weiter behoben werden. Rückfrage an Robert.

### R18 — niedrig — „Kleinstteile entfernen" und die automatische Splitterentfernung heißen gleich

- Ort: `app/core/geom/ops.py:666–670` (`small_components`, Doc „Entfernt lose Splitter, die viel kleiner sind
  als das Hauptteil."), `repair.py:2851–2854` (`repair.splinters_removed` „Ein loser Splitter wurde entfernt."
  läuft **unabhängig** vom Haken bei jedem Lochschließen).
- Fall: Haken aus (Vorgabe), *Reparieren* an einem Netz mit einem offenen Einzeldreieck → Bericht „Ein loser
  Splitter wurde entfernt." — der Kunde liest am Feld darüber, dass genau das der ausgeschaltete Haken tut.
  Umgekehrt entfernt der Haken auch **geschlossene** kleine Teile, die keine „Splitter" sind.
- Vorschlag: Doc des Hakens „Entfernt lose Teile, die viel kleiner sind als das Hauptteil — auch
  geschlossene." und im Docstring/Handbuch sagen, dass offene Splitter beim Lochschließen ohnehin gehen.

### R19 — niedrig — „Außenseiten gegeneinander" fällt am Endstand nicht, wenn ein späterer Schritt die Wicklung heilt

- Ort: `app/core/scene/evaluate.py` `CLOSED_STATE_CODES`/`ONE_PIECE_CODES` und `_without_outdated`;
  `repair.normals_inconsistent` steht in keiner Menge und in keinem `SETTLED_BY`-Eintrag.
- Fall (aus dem Code): Import meldet „An 12 Kanten zeigen die Außenseiten gegeneinander." (Warnung, *Stellen
  zeigen*); ein späterer Schritt liefert einen einheitlich gewickelten Körper (Vereinigung über die Voxelstufe,
  erneutes *Reparieren* nach einer Änderung) — der Satz im Präsens bleibt als Warnung stehen, und *Stellen
  zeigen* findet auf der Karte keine vierte Stufe mehr. Dasselbe Muster, das `_without_outdated` für Dichtheit
  und Teilezahl gerade eingeführt hat.
- Vorschlag: Eine dritte Menge `CONSISTENT_STATE_CODES = {"repair.normals_inconsistent"}` gegen
  `mesh.raw.is_winding_consistent` am Endstand, in `operationen.md` beim Endstandfilter mit nennen.

### R20 — niedrig — `turn_shells_outward` baut an einem einzigen Körper den ganzen Schalenapparat

- Ort: `repair.py:331–352` (`_Shells.__init__`: `face_components`, Dreiecksfeld, `_shell_volumes`, je Schale
  eine Eckenkopie für den Hüllquader), aufgerufen aus `unify_normals` und `loader.normalise` Schritt 4 an jedem
  geschlossenen Netz.
- Fall (Sonde `sonden/review-einschale.py` → `review-einschale.txt`): Icosphäre mit 1 310 720 Dreiecken, eine
  richtige Schale — `turn_shells_outward` 0,83 s und **378 MB** Spitze (tracemalloc), um danach nichts zu tun;
  `signed_volume` beantwortet dieselbe Frage in 0,16 s. Hochgerechnet auf die bestätigte Importgrenze
  (5 Mio.) rund 3 s und 1,4 GB zusätzlich, im Import und in jedem *Reparieren*; am Drachen stand
  `unify_normals` bei 5,0 s (`review-gross.jsonl`, unter Last).
- Vorschlag: Vorab `face_components` zählen (liegt als `MeshData.component_count` oft schon im Cache); bei
  einer Komponente nur `signed_volume` fragen und ggf. `invert()`. Hüllquader je Schale über `np.minimum.at`
  auf die Ecken statt einer Kopie je Schale.

### R21 — mittel — Gefundene Überschneidungen verschwinden ohne Befund, wenn das Volumen nicht positiv ist — dann folgt „nichts zu reparieren"

- Ort: `repair.py:2480–2481` (`_intersections_resolvable`: jedes nicht positive Volumen heißt `"flat"`),
  `:3123` (`elif blocked != "flat":` — „Eine Fläche ohne Dicke hat ihren eigenen Befund"), dazu
  `app/core/geom/ops.py` `repair_object` (`repair.nothing_to_do`, wenn weder geändert noch ein Befund).
- Fall (Sonde `sonden/review-flach.py` → `review-flach.txt`): zwei überlappende Würfel, umgestülpt, 12
  Schnittdreiecke; `repair(normals=False, self_intersections=True)` → **keine einzige Zeile**, die Operation
  sagt danach „An diesem Netz war nichts zu reparieren." Mit `self_intersections=False` kommt „Teile des Modells
  überschneiden sich." Der Satz aus dem Kommentar stimmt nur für die offene Fläche, deren Füllung verworfen
  wurde (`_flat_fills`); eine geschlossene Tasche ohne Volumen (zwei verschieden vernetzte, gegenläufige Blätter,
  die `remove_doubled_faces` nicht als Paare sieht) oder ein umgestülpter Körper bei ausgeschaltetem
  Angleichen bekommen gar keinen.
- Vorschlag: `"flat"` nur für |V| ≤ `EPS_GEOM`·A (wie `_flat_fills`), negatives Volumen als eigener Grund
  (`"inverted"`, Satz „… solange das Modell innen und außen vertauscht"); und in `_intersection_findings` für
  jeden Grund ohne eigenen Befund wenigstens `repair.self_intersections_detected` mit *Stellen zeigen* setzen.
  Test: der Sondenfall mit beiden Einstellungen hat eine Zeile über die Überschneidungen.

### R22 — niedrig — Testlücken: Die Bandsperre `_band_crosses` hat keine Gegenprobe, die Migration keine Undo-Seite

- Ort: `repair.py:1384–1407` (`_band_crosses`), `app/core/scene/migrations.py:860–887`
  (`_keep_repairs_as_they_were`, Zweig über `transactions[*].changes.{before,after}.edited_ops`).
- Fall (Sonde `sonden/review-mutation.py` → `review-mutation-band.txt`): `_band_crosses` durch „kreuzt nie"
  ersetzt — alle zehn Band- und Fülltests (`bore_wall`, `countersink`, `rings_joined`, `quarter`,
  `face_with_holes`, `fold`, `cut_sphere`, `window_around`) bleiben grün. Die Gegenprobe mit `_folds`
  (`review-mutation-folds.txt`) wird dagegen rot (2 Tests) — dort trägt der Test die Zusage. Für die
  Migration prüft `test_v34_repair_steps_keep_leaving_crossings_alone` nur den Stapel; eine geänderte
  Fassung eines alten Reparaturschritts auf einer Undo-Seite ist ungeprüft (das Muster steht für
  `edited_ops` in `test_project.py:275 ff.` schon bereit).
- Vorschlag: Ein Fall, in dem das Band vorhandene Flächen durchstieße (zwei koaxiale Ringe gleicher Teilung,
  zwischen denen ein fremder Körper steht, dessen Nachbarn die Seitenprobe bestehen) → gedeckelt, nicht
  überbrückt; und `repair_v34.p3d` (oder eine Kopie im Test) mit einer `edited_ops`-Fassung des Reparaturschritts
  auf `before`/`after`, nach dem Öffnen `self_intersections=False` auf beiden Seiten. Dazu die Fälle aus R5
  (viele Splitter) und R9 (viele gleich lange Ringe, als Leistungswächter beim Release).

## Geprüft ohne Befund (mit Beleg)

- `_loop_triangles` (verkettete Liste, Reflexmenge): zufällige Sterne mit 12/40/200 Ecken, Kämme mit 10/60
  Zähnen, Rechteck mit kollinearen Punkten, in schräger Raumlage und beiden Umlaufrichtungen — immer n − 2
  Dreiecke, keine Überdeckung, richtige Richtung, wie HEAD (`sonden/review-ohren.txt`).
- `wind_consistently`: 1 310 720 Dreiecke, 30 % gedreht → einheitlich in 1,23 s; die Mehrheitsregel wirkt wie
  beschrieben (`review-wicklung.txt`). Ganze Zahlen, keine Plattformfrage.
- Vereinigung vieler Schalen: 100 bzw. 400 überlappende Kugeln → aufgelöst, dicht, 2,2 bzw. 13,3 s
  (`review-viele-schalen.txt`).
- Kataloge: Jeder `_()`/`tr()`-Text aus `repair.py`, `intersections.py`, `geom/ops.py`, `loader.py`,
  `ingest/ops.py`, `maps.py`, `errors.py`, `labels.py`, `panels.py` steht in allen fünf Katalogen, Platzhalter
  stimmen (`review-kataloge.txt`), auch beide Fassungen von `repair.part_inside`.
- `intersections._candidates`: Die Budgetkante ist richtig — alle Paare eines Eintrags entstehen im selben Block,
  ein Dreieck mit allen Einträgen vor dem Schnitt ist ganz geprüft; `checked` bildet über `surface.kept` richtig
  auf Eingangsnummern ab. Gezählt wird nach dem Achsenfilter, wie dokumentiert.
- `mesh.triple_products`/`enclosed_volume`/`signed_volume` und der Ersatz in `boolean.py`/`difference.py`:
  dieselbe Formel wie das alte `_signed_volume`, elementweise.
- `_band_between`: Beide Ränder werden in ihrer Ringrichtung überlaufen (Orientierung passt zu den Nachbarn),
  Seitenprobe wie beschrieben; `_fill_loops`-Slotwahl nimmt die eigene Randkante vor der Diagonale (B10 behoben).
- Migration 34 → 35 folgt dem Muster von `_keep_raw_import_coordinates`; `FORMAT_VERSION` 35,
  `CACHE_FORMAT_VERSION` 28 und `cache_version="3"` der Reparatur sind gesetzt.
- `SETTLED_BY`-Ergänzungen und `_without_outdated`: richtig für die genannten Codes; mildern R5 im Dokumentweg.
- `detect_curved_faces`: Die Facettenschließung läuft nur über nicht beanspruchte Dreiecke; ebene Flächenmerkmale
  bleiben beansprucht.
- `ruff check` auf den geprüften Kerndateien: sauber (`review-ruff.txt`). Gezielte Tests grün: Plattformwege
  `import_repair` und `repair_selfint`, `test_repair.py -k "sheet or splinter or part_inside or …"` (8), die
  Mutation `_folds` wird von zwei Tests gefangen.

**Erwogen und verworfen:** Ein Hohlkörper, dessen beide Schalen je für sich innen-außen stehen (außen −, innen −),
kommt nach der Gesamtumkehr als „Teil im Teil" heraus — das ist mehrdeutig und wird gemeldet, kein Fehler (anders
als R3, wo ein **richtiger** Hohlraum kippt). Gleichstände im Liepa-Verfahren an ebenen Ringen entscheidet
Rechenrauschen, aber alle gültigen ebenen Triangulierungen haben dieselbe Fläche, und die Rechnung ist aus
Grundrechenarten — plattformgleich.

**Außerhalb des Umfangs, nur zur Kenntnis:** `app/ui/main_window.py:3423–3424` („Ohne Merkmalserkennung laden",
Hunk der Großnetz-Erkennung) fehlt in allen fünf Katalogen (`review-kataloge.txt`); `check_new_texts.py` würde den
Commit daran anhalten.

## Nach Schwere sortiert

| Schwere | Befunde |
|---|---|
| hoch (1) | R9 `_fill_jobs` quadratisch — 1 500 Dreieckslöcher 78 s statt 0,06 s, im Import ohne Abbruch |
| mittel (10) | R3 globales Umstülpen kippt einen richtigen Hohlraum · R4 „Teil im Teil" am gefangenen Teil · R5 Splitterbilanz: falsche „Fläche ohne Dicke", verdeckte offene Stellen · R6 *Dicke geben* verdoppelt geschlossene Teile · R7 Ort der Befunde bei Baugruppen · R10 Import ohne Abbruch · R11 RM-187 `np.hypot`/`einsum`, Wege nicht in `_WAYS` · R12 *Reparieren* 10–90 s an großen Netzen · R15 Splitterlöschen beim Import gegen §17.1 · R21 gefundene Überschneidungen ohne Befund, „nichts zu reparieren" |
| niedrig (11) | R1 `reason` als Code im Tooltip · R2 „Toleranz: 0,00 mm" · R8 4b ignoriert „Außenseiten angleichen: aus" · R13 „Teil im Teil" ohne Handlung · R14 Zwilling Schalenvolumen in der Erkennung · R16 „unvollständig" fehlt nach Auflösung · R17 *Offen lassen* öffnet alles · R18 „Splitter" doppelt belegt · R19 „Außenseiten gegeneinander" ohne Endstandfilter · R20 Schalenapparat an einem Körper · R22 Testlücken (`_band_crosses`, Migration Undo-Seite) |

**Kann das so rein? Nein** — R9 macht den Import eines Netzes mit einigen hundert kleinen Löchern um
Größenordnungen langsamer und ist nicht abbrechbar; R3, R5, R6 und R21 liefern an plausiblen Eingaben falsche
Geometrie oder falsche Entwarnungen. Die übrigen Befunde können als Registerpunkte folgen.

Fertig
