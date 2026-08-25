# Gesamtreview Solidon — 25.08.2026

**Auftrag:** Gründlicher Review der gesamten Anwendung anhand des Ist-Codes und der
laufenden Oberfläche — nicht anhand der Dokumentation.

**Vorgehen:** Elf Review-Agenten, je Gebiet einer, strikt lesend, mit der Auflage,
Befunde auszuführen statt zu vermuten (VERIFIZIERT = ausgeführt oder nachgerechnet,
PLAUSIBEL = nur gelesen). Dazu eine eigene Oberflächen-Durchsicht am lebenden
Fenster (echte Qt-Plattform, bildschirmfüllend, Wachhund, Aufnahmen) — Skripte und
Bilder liegen neben diesem Bericht. Bekannte offene Punkte aus dem Register in
`ROADMAP.md` sind nicht erneut aufgeführt; das capture()-Einfrieren im Rezeptdialog
ist ausgelassen (Sitzung -ce arbeitet daran).

**Stand:** Begonnen auf b42278b1; während des Reviews sind Commits anderer
Sitzungen gelandet (u. a. 1b04b085 recipe_dialog, 48304e72 sketch_editor) — die
betroffenen Befunde sind gegen den neuen Stand geprüft bzw. als „möglicherweise
Baustelle" markiert. Der Arbeitsbaum trug ungestagte Stände dreier Nachbarsitzungen.

**Zählung:** rund 180 Befunde, davon ~30 mit Schweregrad hoch. Die Agenten haben
den weit überwiegenden Teil am ausgeführten Code belegt, oft mit Messwerten.

---

## Die schwersten Befunde auf einen Blick

Kunde bekommt falsche Geometrie oder verliert Daten:

1. **Projektdatei wird unlesbar**, sobald zwei eingebettete Quellen denselben
   Dateinamen tragen (`bracket.stl` aus zwei Ordnern) — beim Öffnen
   „Prüfsumme stimmt nicht", Arbeit weg. [Szene 1]
2. **„Gewinde in Bohrung schneiden" vereint statt abzuziehen** — aus der Bohrung
   wächst ein Bolzen (+286 mm³ gemessen). Gleicher Strukturfehler bei der
   Rastnasen-Gegenseite. [Wissen 1, 2]
3. **Senkung (`countersink_hole`)**: an drei der sechs Achsrichtungen wirkungslos
   (0,78 mm³ Kratzer, kein Befund), und die Vorbelegung aus einer angeklickten
   Bohrung senkt in die **Mitte** des Materials statt an die Mündung. [Geometrie 1, 2]
4. **Skizzen-Ops**: `loft` verliert gezeichnete Löcher stillschweigend;
   `sketch_pocket`/`sketch_sweep` ignorieren die gewählte Zeichenebene und
   schneiden immer von oben; Trimmen kann Linien **verlängern**. [Skizze 1, 2, 4]
5. **Agent-Rücknahme leert das Projekt**: `undo_transaction` auf eine alte
   Transaktion nimmt alle jüngeren mit, angekündigt ist eine. [Agent 1]
6. **Ein Rezept mit `create_from_scad` umgeht beide Quelltext-Sperren**
   (Fernzugriff-DENY und auto_acceptable). [Agent 2]
7. **`orient_for_print` meldet keine Transformationsmatrix** — Merkmalskennungen
   brechen, Passungen zeigen ins Leere. [Geometrie 5]
8. **Die Entlüftung beim Aushöhlen bohrt zusätzlich durch die Decke** — ein
   Ø4-Loch mitten in der Sichtfläche. [Geometrie 6]
9. **Schichtanalyse**: das „Stützvolumen" skaliert mit der Schichthöhe (Faktor 5
   zwischen zwei Anzeigen derselben Zahl); zwischen den zwei Überhang-Schwellen
   rät niemand Stützen an; die Brückenweite misst die längste statt der kürzesten
   Spannweite (Kabelkanal 8 mm wird als 30-mm-Brücke gemeldet). [Schicht 1–3]
10. **Viewport**: ein Klick wählt ausgeblendete Körper und Körper fremder Platten;
    der Fangradius im Skizzenmodus beträgt 6,7 mm statt 8 Bildpunkten (Klicks
    schnappen ungewollt auf Nachbarpunkte); Ziehen eines Punkts macht
    Hilfsgeometrie zur Profilkante; elf von dreizehn Zeichenkürzeln feuern im
    Viewport-Modus nie. [Viewport 1–4]
11. **Import/Export**: die Einheitenfrage bei kleinen mm-Teilen bietet „mm" nicht
    an (Import scheitert an einer korrekten Datei); eine 3MF wird vollständig
    entpackt, **bevor** die Zip-Bomben-Grenze prüft (1,9 MB → 660 MB im
    Hauptthread); die eigene zweifarbige Baugruppe verliert beim Wiederöffnen alle
    Farben. [Import/Export 1–3]
12. **Normteiltabelle**: Mutternhöhen nach zurückgezogener DIN 934 statt ISO 4032 —
    die M5-Mutternfalle ist 0,6 mm zu flach. [Wissen 7; der Senkkopf-Befund
    Wissen 8 wurde von b0 widerlegt — die Tabelle stimmt]

---

## A. Eigene Oberflächen-Durchsicht (lebendes Fenster)

Gefahren wurden: Erststart, Startbildschirm, leeres Projekt, Quader, Bohrung
(mit und ohne Auswahl), alle neun Menüs samt Untermenüs, Befehlspalette,
Werkzeugleiste (Messen/Analyse/Schichten/Bewegen), Bausteinkatalog, Chat,
Druckeinstellungen (inkl. Slicen ohne Profil), Skizzenmodus (Tasche schneiden),
Speichern/Wiederöffnen, Beispielprojekt mit Tour, sowie derselbe Rundgang auf
Portugiesisch. Aufnahmen unter `aufnahmen/`, Protokolle daneben.

### A1 · mittel · Objektbaum zeigt für die angebohrte Fläche die unbeschnittene Größe — VERIFIZIERT

Quader 40×30×10, Durchgangsbohrung Ø5 von oben (`through: True`). Der Baum zeigt
„Unterseite 1179 mm²" (korrekt beschnitten), aber „Oberseite 1200 mm²" —
die Fläche, in die der Kunde gebohrt hat. Headless nachgemessen: das
Provenienz-Merkmal `face_top` aus `create_box` behält `area=1200.0`, während die
neu erkannten Flächen (`face_1` …) nach der Booleschen Operation neu vermessen
werden. Die angezeigte Zahl der wichtigsten Fläche ist damit nach jeder Folge-Op
veraltet. Ort: Naht `create_box`-Provenienz ↔ `perceive`-Neuvermessung.

### A2 · mittel · „Speichern unter" erzwingt die Projektendung nicht — die App öffnet die eigene Datei danach nicht mehr als Projekt — VERIFIZIERT

`action_save_as` → `_save_to(Path(name))` → `session.save_project(path)`
schreibt jede Endung klaglos (live mit `.solidon` gespeichert, 556 Bytes).
`open_path` verzweigt strikt über `PROJECT_SUFFIX` (`.p3d`): dieselbe Datei wird
als Fremdmodell behandelt, eine scheiternde „Modell laden"-Op landet im Verlauf,
der Prüfbericht meldet „Dieses Dateiformat kann nicht gelesen werden", die Kette
hält an. Wer im Speichern-Dialog einen Namen mit fremder Endung tippt
(`halter.stl` ist der nahe Fehlgriff), baut sich diese Falle selbst. Fix:
Endung in `_save_to` erzwingen bzw. ergänzen.

### A3 · mittel · Der Bewegen-Modus lässt seine Fang-Markierungen im Viewport stehen — VERIFIZIERT (Bild)

Ablauf: Bewegen aktivieren (Gizmo + Fangmarken an Kantenmitten erscheinen),
Bewegen wieder deaktivieren, Katalog/Chat öffnen. Aufnahme `17-chat.png` zeigt
die Kantenmarken weiterhin, `12-messen.png` (vor Bewegen, gleiche Kamera) ist
sauber. Das Verlassen des Modus räumt seine Überlagerung nicht vollständig ab.

### A4 · mittel · Portugiesische Oberfläche: drei Auswahlwerte im Einstellungsdialog bleiben deutsch — VERIFIZIERT (Bild) — möglicherweise Baustelle (Sitzung b0, labels.choice_label)

`33-einstellungen-pt.png`: Tema = „Dunkel", Navegação = „Wie in Cura — links
wählt, rechts dreht", Vista de diferenças = „Blau und Orange (Vorgabe)". Die
Feldbeschriftungen sind übersetzt, die Werte nicht.

### A5 · gering · Der Titel des mitgelieferten Druckerprofils bleibt in jeder Sprache deutsch — VERIFIZIERT (Bild)

„Allgemeiner FDM-Drucker 220 mm" steht in der portugiesischen Oberfläche in der
Kopfzeile, im Einstellungsdialog und im Druckdialog. Es ist das Standardprofil
jedes Neustarts, kein Markenname — der Titel gehört übersetzbar gemacht.

### A6 · gering · „Fertig" im Skizzenmodus verlässt den Modus bei leerer Zeichnung wortlos — Code + Verhalten

Der Knopf ist immer aktiv; `finish_sketch(keep=True)` mit leerem Text räumt nur
auf (`if keep and text:` überspringt die Operation). Wer nichts gezeichnet hat
und Fertig drückt, bekommt weder Dialog noch Satz — die Leiste versprach „dann
fragt Solidon, was daraus wird".

### A7 · gering · Eine ganze Zeichnung lässt sich nicht verschieben — Code, bestätigt Vermutung von Sitzung -ce

Auswahl im Skizzeneditor: Einzelklick oder Strg-Klick je Element; kein
Alles-auswählen, kein Gummiband, nichts im Kontextmenü (nur „Koordinaten …",
„Löschen", Bedingungen). Eine Zeichnung mit zwanzig Elementen umzusetzen heißt
zwanzigmal Strg-klicken. (Das Ziehen der Mehrfachauswahl selbst funktioniert —
`_shift_selection` mit Schwelle ist sauber gebaut.)

### A8 · Beantwortete Vermutung: „Tasche schneiden" verlangt nach dem Zeichnen keine neue Auswahl

Fläche wählen → zeichnen → Fertig öffnet den Taschen-Dialog direkt, mit
x/y/z aus der Auswahl vorbelegt (live gefahren). Der Menüeintrag ist bei
Netz-Körpern ausgegraut (B-Rep-only), der Grund steht in Statusleiste/Tooltip,
und der erzwungene Weg endet in einem vorbildlichen Fehlersatz samt Vorschlag
(„… Exakte Körper kommen aus einer STEP-Datei oder aus den Grundformen mit
gesetztem Haken …"). Kein Befund.

### A9 · Beobachtungen ohne Befund

- Slicen ohne gewähltes Slicer-Profil: Knopf ist aktiv, der Klick liefert einen
  klaren Satz im Dialog („Dieser Slicer braucht ein Druckerprofil — bitte eines
  auswählen."). Vertretbar.
- `drill_hole` ohne Auswahl: Meldebox mit klarem Satz („Wählen Sie dafür ein
  Objekt aus …"). Undo/Redo, Speichern (556-Byte-Projekt), Beispielprojekt mit
  Tour (drei erklärte Info-Befunde), Befehlspalette mit Ausgrau-Begründungen —
  alles sauber.
- Portugiesisch ist ansonsten bemerkenswert vollständig (Menüs, Dialoge,
  Objektbaum, Prüfbericht, Statusleiste, Freischalt-Dialog).
- Menügrenzen: 9 Menüs, „Datei" mit genau 12 Einträgen, 8 Werkzeuge — alle an,
  keines über der Grenze.

---

## B. Szene, Verlauf, Parameter, Projektdatei (`app/core/scene`, `registry`, `expressions`, `types`, `units`, `split`, `lid_flow`, `tools`)

Keine Datei des Gebiets trug fremde ungestagte Änderungen.

1. **hoch · VERIFIZIERT · `project.py:168` + `:283`** — Zwei Quellen mit gleichem Dateinamen bekommen denselben Containerpfad (`sources/bracket.stl` zweimal); beim Wiederöffnen: „Eine Quelle stimmt nicht mit ihrer Prüfsumme überein." Die Datei ist heil geschrieben und trotzdem verloren. Fix: `source_id` in den Pfad, Zusicherung in `save()`.
2. **mittel · VERIFIZIERT · `serialise.py:64`** — Parametertitel werden als aufgelöste Zeichenkette eingefroren: das mitgelieferte Beispiel `dose-mit-deckel.p3d` zeigt einem englischen Kunden „Breite/Tiefe/Höhe/Wandstärke", obwohl die Übersetzungen existieren. `finding_to_data`/`transaction_to_data` im selben Modul machen es vor (`title_translatable` + Kontext).
3. **mittel · VERIFIZIERT · `serialise.py:143/97/361` (gefangen erst `project.py:394`)** — Strukturell kaputtes, syntaktisch gültiges JSON verlässt `load()` als rohe `KeyError`/`ValueError`/`TypeError` (fünf Wege gemessen), ohne Handlungsvorschlag (Regel 17). Fix: die drei Ausnahmearten im `load()`-Fang ergänzen.
4. **mittel · VERIFIZIERT · `serialise.py:100` + `fits.py:167` + `evaluate.py:435`** — Eine unbekannte Passungsart aus der Datei (`"type": "banane"`) reißt die Auswertung mit roher `KeyError` ab; `check_fits` steht außerhalb jedes `try`. Fix: in `fit_from_data` gegen `FIT_KINDS` prüfen.
5. **mittel · VERIFIZIERT · `history.py:750`** — Transaktionskennungen werden nach Undo wiedervergeben (Op-Kennungen nicht): ein Chat-Beitrag zeigt danach auf eine wildfremde Transaktion und gilt als lebendig; `_undo_named("t2")` träfe die falsche. Fix: `_next_transaction` wie `_highest_op_id` über alles je Vergebene bilden.
6. **mittel · VERIFIZIERT · `variants.py:181`** — `_place` schiebt jeden Körper einzeln auf den Versatz: bei „Dose mit Deckel" liegen je Variante Deckel und Rumpf ineinander, die gemeldete Breite ist die des breitesten Einzelkörpers. Fix: Gruppenversatz.
7. **mittel · VERIFIZIERT · `orphans.py:179`** — `_kind_of` kennt `cone/sphere/torus/fillet` nicht und führt das tote `slot`: für einen verschwundenen Kegel werden Flächen und Bohrungen als „plausible Nachfolger" angeboten. Fix: aus `get_args(FeatureKind)` ableiten.
8. **mittel · VERIFIZIERT · `types.py:935` + `evaluate.py:243`** — Regel 3 (`OpContext.scene` nur lesend) hat weder Schutz noch Test: eine schreibende Probe-Op ändert Parameter der Ergebnisszene. Einzige der 22 Regeln ohne Test.
9. **gering · VERIFIZIERT · `evaluate.py:305–347`** — deutsche Bezeichner `art_vorher`, `geworden`, `war`; Stämme fehlen in `GERMAN_STEMS`.
10. **gering · VERIFIZIERT · `ops.py:117–119`** — einziger englischer Docstring des Gebiets.
11. **gering · VERIFIZIERT · `ops.py:287/298`** — Bauraumprüfung von *Kopien in Reihe oder Kreis* nur im linearen Zweig; der Kranz meldet stattdessen acht Einzelwarnungen ohne die zwei Handlungsvorschläge.
12. **gering · VERIFIZIERT · `project.py:197`** — `_next_gathered` ist toter Code (es gibt nie `gathered_*`-Quellen); der Docstring behauptet eine Buchführung, die nicht existiert.
13. **gering · PLAUSIBEL · `project.py:353–359`** — mitgereiste Rezepte werden global registriert und nie wieder abgemeldet; der Fehlertext in `recipe.py:747` empfiehlt ein Mittel, das nichts bewirkt. (Grenzt an die aktive Rezept-Baustelle.)
14. **gering · VERIFIZIERT · `evaluate.py:494–506`** — derselbe zwölfzeilige Erklärblock steht dreimal in `SETTLED_BY`, zweimal ohne Eintrag dahinter.
15. **gering · VERIFIZIERT · `types.py:314` + `serialise.py:62`** — `Parameter.minimum/maximum` werden gelesen und serialisiert, aber von keiner Stelle der Anwendung je gesetzt (Spinbox-Grenzen damit immer ±100 000); Ausdrücke werden nie gegen die Grenzen geprüft (`max=60`, `=@a*10` → 600 ohne Meldung).

Zurückgenommen nach Gegenprüfung: Migration 6→7/drill_brep_hole; PaletteEntry.available; Feature.recognised im Cache; Rezept-§32-Warnung; FEATURE_TITLES.

**Testlücke der Naht:** kein Test mit zwei gleichnamigen Quellen; `variants._place` nur mit einem Körper geprüft; Regel 3 ohne Test.

---

## C. Geometrie-Kern (`app/core/geom`, ~12 700 Zeilen)

1. **hoch · VERIFIZIERT · `prepare.py:197–207` / `prepare_ops.py:299–325`** — `countersink` senkt je Achse in eine feste Richtung: an drei der sechs Flächen entstehen 0,78 mm³ statt 129,7 mm³ Abtrag, ohne Befund (Y verhält sich zusätzlich umgekehrt zu X/Z). Kein `into_the_body()`, kein `without_effect()`.
2. **hoch · VERIFIZIERT · `prepare_ops.py:309` + `placement.py:141–145`** — die Vorbelegung aus einer angeklickten Bohrung setzt die Senkung auf die **Mitte** der Bohrung: der Kegel sitzt unsichtbar im Material (61,3 mm³, Querschnitte gemessen). `drill` hat für genau diese Falle sein `anchor="mouth"` — `countersink` nicht.
3. **hoch · VERIFIZIERT · `paint.py:66–73`** — „Bemalen" misst gegen Dreiecks-Schwerpunkte: ein Klick mitten auf eine 60×40-Deckfläche meldet `colour.nothing_painted` (bis 200×200 gemessen). Die Lösung (`distance_to_triangles`) steht beschrieben in `mesh.py:312` und wird hier nicht benutzt; auch der Pinselumfang misst Schwerpunkte.
4. **hoch · VERIFIZIERT · `paint.py:197` + `attributes.py:150`** — `paint_slot` mit Slot 0 meldet immer Erfolg („12 Flächen"), auch bei Klick ins Leere bei x=500; die Facettenzahl im Befund ist generell die des Zielslots, nicht die des Pinsels.
5. **hoch · VERIFIZIERT · `prepare_ops.py:1003–1012`** — `orient_for_print` dreht ohne `transform` im `OpResult`: Merkmalskennungen wechseln (`hole_1` → `hole_2`), Passungen und Folge-Ops zeigen ins Leere, §21.3 hält an.
6. **hoch · VERIFIZIERT · `hollow.py:227/232`** — die Entlüftung spannt über die volle Körperhöhe plus 4 mm: zusätzlich zum Boden ein Ø4-Loch durch die Decke (Querschnitte bei z=19 gemessen), entgegen dem eigenen Docstring („nach unten durch den Boden").
7. **hoch · VERIFIZIERT · `repair.py:213` + `ops.py:420–432`** — `repair` füllt ein Loch (Dreieckszahl 1214→1215) und meldet gleichzeitig `repair.still_open` **und** `repair.nothing_to_do`; `changed` bedeutet „ist jetzt dicht" statt „hat sich geändert".
8. **mittel · VERIFIZIERT · `lattice.py:313–373`** — `hollow_object` (Vorgabe `vents=1`) → `lattice_fill` ist eine Sackgasse: die Entlüftung verbindet die Schalen, `_cavity_bounds` erkennt den Hohlraum nur an zwei getrennten Schalen; der Vorschlag lautet „Erst aushöhlen" — der Schritt, den der Nutzer gerade getan hat (Regel 17).
9. **mittel · VERIFIZIERT · `perceive/matching.py:398–404`** — `moved_features` wirft `created_by` und `recognised` weg: nach jedem Verschieben verschwindet „diesen Schritt ändern", Baustein-Merkmale verwaisen. Fix: `dataclasses.replace(feature, params=...)`.
10. **mittel · VERIFIZIERT · `hollow.py:39–42/163–166`** — die stehenbleibende Wand weicht bei 0,8 mm um 25 %, bei 0,5 mm um 40 % ab (Versprechen: ±1/6), und der Befund nennt den Sollwert statt des wirklich erodierten Betrags.
11. **mittel · VERIFIZIERT · `prepare.py:234`** — `plug_hole` zentriert den Stopfen auf `position`: an der Mündung eingetippt füllt er die halbe Bohrung (106 von 212 mm³), ohne Befund. Fix: `anchor`-Feld wie bei `drill`.
12. **mittel · VERIFIZIERT · `lid.py:390–410`** — `create_lid` meldet ein `lid_collar`-Merkmal auch bei `collar=0.0` („flacher Deckel ohne Kragen"); eine Passung misst dann eine Geometrie, die es nicht gibt.
13. **mittel · Codebeleg** — fünf Ops (hollow, create_lid, screw_lid, compensate_first_layer, split_pinned) laufen durch die Boolesche Rückfallkette, ohne die verwendete Stufe in `solver` zu melden (Zusage aus `boolean.py`).
14. **mittel · Codebeleg** — dieselben Ops reichen `ctx.quality` nicht durch bzw. verdrahten `quality="fine"` fest: die Entwurfsstufe existiert für sie nicht (Checkliste „neue Operation", Punkt 5).
15. **mittel · VERIFIZIERT** — `ctx.cancelled`/`ctx.progress` erreichen fast keine Op des Gebiets; `blend_union` mit `grid=0.5` läuft 9,2 s unabbrechbar und ohne Fortschritt (Schema erlaubt bis 0,05).
16. **mittel · VERIFIZIERT · `primitive_ops.py:278–288`** — Grundformen melden den Hüllquader als Deckflächen-Fläche: Zylinder 400 statt 314 mm², die Kugel behauptet eine ebene `face_top`, die es nicht gibt (und `plane_of` akzeptiert sie als Öffnungshöhe).
17. **gering** — englischer Docstring-Absatz `label_ops.py:14–15` (einziger im Gebiet, per AST gesucht).
18. **gering** — deutsche Bezeichner `passt` (`prepare.py:799`), `kein_volumen` (`repair.py:384`); Stämme in `GERMAN_STEMS` nachtragen.
19. **gering** — zwei Möller-Trumbore-Umsetzungen mit widersprüchlichen Epsilons (`mesh.py:264` 1e-12 vs. `measure.py:206` `EPS_GEOM` fürs Spatprodukt — dimensional falsch). Zusammenführen.
20. **gering** — `angle_between`, `bounding_box_of`, `volume_of` (§18.3) existieren und werden von niemandem außer den eigenen Tests gerufen — Anschluss-Lücke (Winkelmessen/Hüllquader/Volumen der Auswahl fehlen in der Anwendung).
21. **gering** — `difference.py:122` Spiegelkonstante `1e-6` statt `EPS_GEOM`.
22. **gering** — `ctx.profile` an vier Stellen als optional behandelt, obwohl der Vertrag es nicht ist; in `prepare_ops.py:800` verwirft der tote Zweig stillschweigend die Stiftplan-Befunde.
23. **gering · Baustelle** — `_ORIGINAL` in `enclosure.py:99–108` (ungestagter fremder Hunk) wird gesetzt und nie gelesen.

**Testlücken:** Die Geometrietests messen den einen Fall, für den der Code geschrieben wurde (Senken nur auf der Deckfläche mit Achse z; Malen nur mit Radius 1000 oder auf feiner Kugel; Gitter nur auf handgebautem Hohlkörper statt nach `hollow_object`). Es fehlen: alle sechs Achsrichtungen, die echte Vorbelegung aus `placement.values_for`, Ops in Handbuch-Reihenfolge, ein Test je Docstring-Zusage (Wandtoleranz, Entlüftungsrichtung, solver-Meldung), Widerspruchsfreiheit von Befunden.

---

## D. Skizzen und exakter Kern (`app/core/sketch`, `app/core/brep`)

Beide Pakete ohne fremde ungestagte Änderungen; die 195 Gebietstests grün — alle Befunde sind Lücken, keine Regressionen.

1. **hoch · VERIFIZIERT · `brep/profiles.py:307–308`** — `loft()` baut seine Querschnitte über `_wire` statt `_face`: gezeichnete Löcher verschwinden stillschweigend (Platte 40×40 mit 10×10-Loch: extrude 15000 mm³, loft 16000 mm³, null Befunde). Regel 21.
2. **hoch · VERIFIZIERT · `sketch/ops.py:394/599`** — `sketch_pocket` und `sketch_sweep` lesen die Skizzenebene nie: auf einer Seitenwand gezeichnet wird trotzdem von oben geschnitten (Hüllquader gemessen). `extrude`/`revolve`/`loft` wurden für genau diesen Fehler repariert, die zwei anderen vergessen. Der Weg ist über „Auf dieser Fläche zeichnen" + `SketchUseDialog` normal erreichbar.
3. **hoch · VERIFIZIERT · `brep/profiles.py:784–790`** — `_points()` übersieht Spline-Stützpunkte (`through` fehlt): `_leftmost`/`_rightmost` liefern falsche Werte, die Achsprüfung von `revolve` läuft ins Leere, und der Kunde bekommt für seine eigene Skizze „Im Programm ist ein unerwarteter Fehler aufgetreten" (StdFail_NotDone roh). `extrude`/`revolve` sind zudem die einzigen Builder ohne `_finished()`.
4. **hoch · VERIFIZIERT · `sketch/edit.py:122–141`** — `trim` akzeptiert Kreuzungen außerhalb der eigenen Strecke: aus einer Linie 0→10 mit Schnittkante bei x=30 wird eine Linie 30→10 — Trimmen **verlängert**, ohne Meldung. Fix: Parameterbereich der getrimmten Linie mitprüfen.
5. **mittel · VERIFIZIERT · `sketch/ops.py:770`** — `push_face` gibt `features={}` zurück: nach „Fläche versetzen" hat der Körper keine anklickbaren Flächen mehr (jede andere B-Rep-Op rechnet sie neu).
6. **mittel · VERIFIZIERT · `brep/profiles.py:886–887`** — `push_faces` prüft weder `IsDone()` noch das Ergebnis: `distance=-25` auf einen 20-mm-Quader → Volumen 0, null Befunde, der Körper ist wortlos weg.
7. **mittel · VERIFIZIERT · `sketch/profile.py:233–237`** — die dritte Verschachtelungsebene (Insel im Loch) fällt still weg — nicht „nicht gebohrt", sondern weggeworfen.
8. **mittel · VERIFIZIERT · `sketch/profile.py:139`** — eine sich selbst kreuzende Kette läuft bis in den Kern: `extrude` liefert einen nicht wasserdichten Körper (watertight False), der in STL-Export und Schichtanalyse geht — ohne Befund.
9. **mittel · VERIFIZIERT · `sketch/edit.py:399` + `ui/sketch_editor.py:735`** — `project()` bekommt seinen `frame` nie: auf einer Flächenebene projiziert die Hilfsgeometrie durch die globale XY-Ebene — die Grundfläche des Körpers landet als Hilfskontur auf der Seitenwand.
10. **mittel · VERIFIZIERT · `sketch/edit.py:122–133`** — `crossings_on` sieht Bögen und Splines nicht: eine Linie über einem Bogen trimmt an der falschen Stelle, sobald zusätzlich eine Linie kreuzt.
11. **mittel · Codebeleg · `brep/kernel.py:368`** — Fließkommavergleich von Knotenkoordinaten mit `==` (Regel 6); nach einer echten Transformation (STEP-Baugruppe) wandern degenerierte Dreiecke wieder in die STL.
12. **gering** — deutscher Bezeichner `ecken` (`brep/kernel.py:363`); Stamm `ecke` in `GERMAN_STEMS` nachtragen.
13. **gering · `sketch/planes.py:143`** — der Fehler zur Zielfläche nennt bei `up_to` das falsche Feld (`plane`) und einen unpassenden Vorschlag.
14. **gering · `sketch/profile.py:283` vs. `:414`** — zwei Schwellen für „Vollkreis" (1e-9 rad vs. EPS_GEOM): dazwischen zeichnet das Bild einen Kreis, der Kern rechnet einen Nullbogen. Familie: `sketch/ops.py:403`, `brep/profiles.py:869` (nackte 1e-9 statt `units.is_zero`).
15. **gering · `sketch/ops.py:171–175`** — dieselbe Zeichnung mit zwei getrennten Umrissen: `extrude`/`loft` rechnen, `pocket`/`sweep`/`revolve` lehnen ab — Inkonsistenz im `SketchUseDialog` (Meldung trägt Vorschläge, Regel 17 gewahrt).
16. **gering · PLAUSIBEL · `sketch/solver.py:518–536`** — `_redundant_pair` kann ein Referenzmaß als „legt dasselbe fest" benennen oder `(0,0)` liefern (zweimal dieselbe Bedingung).

**Sauber geprüft und in Ordnung:** Abmeldung ohne OpenCASCADE auf allen 16 Ops (mit blockiertem OCP gemessen); Löser-Korrektheit und -Determinismus (Restfehler ≤ 8,8e-11, bitgleiche Wiederholung); Ebenen-Transformationen invers und getestet.

**Testlücken:** Ebene nur an der Op geprüft, die sie liest; Loch-Volumen nur für `extrude`; Trimmen nie über die Strecke hinaus und nie gegen Bögen; `_leftmost`/`_rightmost` nur mit Grundformen ohne `through`. Ein Ergebnis-Check `is_closed ∧ solid_count ≥ 1 ∧ volume > EPS` über alle Skizzen-Ops hätte 1, 6 und 8 zusammen gefangen.

---

## E. Schichtanalyse und Wahrnehmung (`app/core/slice`, `app/core/perceive`)

1. **hoch · VERIFIZIERT · `analysis.py:145/166`** — `support_volume` ist das Volumen der überhängenden **Schale**, nicht der Stützsäule, und skaliert linear mit der Schichthöhe (Pilz: 79 mm³ bei lh 0,2, 385 mm³ bei lh 1,0; analytisch 7920). Folgen: die G-Code-Gegenprobe zum Stützvolumen feuert dauerhaft eine Falschwarnung (Abweichung > 90 % bei Schwelle 15 %), und der Chat nennt für denselben Körper Faktor-5-verschiedene „Stützvolumen".
2. **hoch · VERIFIZIERT · `advise.py:53/67/375`** — die Stützen-Bedingung reduziert sich auf `worst > 100 UND total > 150`: eine 138-mm²-Decke frei in der Luft bekommt keinerlei Hinweis (weder Stützen noch Brücke). Die Schichtschwelle muss allein tragen können.
3. **hoch · VERIFIZIERT · `analysis.py:731–734`** — `_bridge_width` misst die größte Ausdehnung des Hüllrechtecks statt der kürzesten freien Spannweite: ein 30×8-Kabelkanal wird als 30-mm-Brücke gemeldet — eine Zahl, die der Kunde am Teil widerlegen kann. `minimum_width` (Erosion) steht zwei Funktionen darüber.
4. **mittel · VERIFIZIERT · `ui/panels.py:296–313/1876` (Baustelle: fremde Umbenennungen in der Datei)** — die Befundzeile zeigt weder Zahlen (`minutes`, `grams`, `deviation`, `span_mm` …) noch die Herkunft; beides steht nur im Tooltip. Regel 14 („Herkunft immer ausweisen") ist in der Anzeige nicht eingelöst; `analysis_bar.py:125` löst es vor.
5. **mittel · VERIFIZIERT · `advise.py:202/226`** — der Flussvorschlag deckelt immer `speed.infill`, auch wenn `speed.inner_wall` die Grenze reißt: mit inner_wall=300/infill=20 lautet der Rat „infill 20 → 143" — er **erhöht** und der Fluss bleibt verletzt; die +10-°C-Empfehlung ändert `max_flow` nicht.
6. **mittel · VERIFIZIERT · `perceive/maps.py:75/78`** — sechs Legendentexte fest deutsch (`"in Ordnung"`, `"Non-Manifold"`, `"Passung verletzt"` …) ohne `_()` — Regel 20; `tests/test_analysis_ui.py:321` zementiert es.
7. **mittel · VERIFIZIERT · `gcode.py:373`** — die Filamentlänge wird aus der Größe geraten statt aus dem Muster (`[mm]`/`m` steht dort): 95 mm werden zu 95 m → 283 g für einen Kalibrierwürfel plus 100-%-Abweichungswarnung.
8. **mittel · VERIFIZIERT · `ui/main_window.py:5135/5256` (Baustelle)** — `_MapWorker` und `_SliceWorker` verbinden `crashed` nie: stirbt der Arbeiter, bleibt „Die Schichtanalyse läuft …" für immer stehen. (`test_leash.py` prüft je Datei statt je Startstelle — deckungsgleich mit Befund I-2.)
9. **gering · `analysis.py:804` + `advise.py:464`** — der 2,0-mm-Deckel von `narrowest()` wird als Messwert weiterverarbeitet: mit 0,8er-Düsenprofil bekommt ein massiver Klotz eine Bahnbreiten-Warnung.
10. **gering · `analysis.py:124`** — nackte englische `ValueError` („layer height has to be positive"), erreichbar über eigenes `printers.toml`; Regel 17.
11. **gering · `analysis.py:188–191`** — Docstring widerspricht dem (richtigen) Code zur Insel nach einer Lücke.
12. **gering · `advise.py:170`** — Fließkommavergleich mit `!=` (Regel 6).
13. **gering · PLAUSIBEL · `gcode.py:419`** — die absolute/relative-E-Heuristik (`";" not in text or "M83" not in text`) kippt bei M83 im Konfigurationskommentar bzw. bei kommentarlosen Dateien.
14. **gering · `perceive/features.py:1422`** — „durchgehend" ist wörtlich „irgendein Dreieck darüber": dieselbe Durchgangsbohrung gilt im U-Profil als Sackloch; für den Steckbrief-Leser unbenannt.
15. **gering · `perceive/features.py:1734–1755`** — alle offenen Kanten werden **ein** Merkmal am gemeinsamen Schwerpunkt (bei zwei Löchern liegt der im Leeren, die Kamera kann nicht hinfliegen).
16. **gering (mit Entwarnung) · `perceive/features.py:1696`** — `detect_faces` ohne Positions-Tiebreak; im Regelbetrieb rettet `match()` die Zuordnung (gemessen), Restrisiko nur für die Ersterkennung.
17. **gering · `gcode.py:502`** — `gcode.no_measurement` trägt als einzigen Zahlenwert die interne Schätzung unter `source="gcode"` (Regel 14 im Kleinen).

**Richtig befunden:** Wandstärkekarte (Median 3,00 bei Soll 3,0), Überhangwinkel auf 0,1° gegen analytische Kegel, Inselerkennung über Z-Lücke, `match()`-Umnummerierung, Regel 9 bei `orient_for_print`.

**Testlücken:** Stützvolumen nur gegen sich selbst geprüft (`> 100.0`) — ein Invarianztest gegen die Schichthöhe hätte Befund 1 am ersten Tag gefangen; Brücken nur am runden Fall; Einstellungsregeln nur auf „welcher Pfad", nie auf Wirkung.

---

## F. Import und Export (`app/core/ingest`, `app/core/export`)

1. **hoch · VERIFIZIERT · `ingest/loader.py:84–91`** — bei Teilen unter 10 mm Diagonale fällt `mm` aus den Antwort-Kandidaten: die M3-Unterlegscheibe in korrekten Millimetern lässt sich nur falsch (×10, ×25,4) importieren oder abbrechen. Die gemessene Einheit muss immer wählbar sein.
2. **hoch · VERIFIZIERT · `ingest/plan.py:75`** — `import_plan` parst das vollständige 3MF-XML **vor** jeder Grenzprüfung: eine 1,9-MB-Datei wird zu 660 MB im Hauptthread; `check_unpacked` (das genau dafür existiert und greifen würde) läuft erst später im Operationslauf.
3. **hoch · VERIFIZIERT · `export/threemf.py:720/356`** — die eigene zweifarbige Baugruppe verliert beim Zurücklesen alle Farben: `_groups_of` behandelt „ein Slot" als „keine Gruppe", auch wenn der Slot nicht 0 ist. Export → Neu → Öffnen = alles grau. (Dazu: fremde `pid`-Verweise fallen still auf default; Materialliste kann kürzer sein als die vergebenen Slots.)
4. **mittel · VERIFIZIERT · `export/writer.py:615/621/639`** — `write_assembly` (3MF) wandelt `OSError` nicht: schreibgeschütztes Ziel endet als „Fehler im Programm, bitte Bericht" statt als `FileWriteError` mit Vorschlag; `write_plan` daneben macht es richtig. Dasselbe in `handover.py:1571` und `discover.workspace_for`.
5. **mittel · VERIFIZIERT (gemessen) · `print_settings_dialog.py:2228` (Kern `writer.py:557`, `handover.py:714`)** — bis zu ~3 s je Platte synchron im Qt-Hauptthread vor dem ersten Balken (`find_profiles` über 9849 ElegooSlicer-Profile, `project_settings` 2,7 s); drei Platten ≈ 9 s eingefrorenes Fenster. Das Muster ist im Haus bekannt (`slicer_profiles.match_filament`).
6. **mittel · VERIFIZIERT · `export/threemf.py:438–476` + `ingest/ops.py:298`** — 3MF trägt seine Einheit im `unit`-Attribut; Solidon liest sie nicht und fragt den Nutzer (bei `micron`/`foot` ist keine der vier Antworten richtig).
7. **mittel · VERIFIZIERT · `export/writer.py:414–434` vs. `:499–522`** — STEP bei gemischter Auswahl: der Docstring verspricht „exakte schreiben, Netze auslassen und benennen", der Code bricht beim ersten Netz mitten im Schreiben ab — eine halbe Dateimenge bleibt liegen, ohne Auskunft.
8. **mittel · VERIFIZIERT · `export/writer.py:288–296`** — „Anordnung hält" prüft Z nur nach oben: ein eingesunkenes (z −15) oder schwebendes (z 50) Teil gilt als „hält", und Solidon setzt die Lage beim Slicer durch (`--arrange 0`) — abgeschnitten bzw. in die Luft gedruckt.
9. **mittel · VERIFIZIERT · `export/writer.py:177` + `cli/main.py:428`** — ein Tippfehler im Namensschema (`--scheme "{name}"`) endet als roher Traceback (KeyError/ValueError) statt als `ValidationError` mit den fünf erlaubten Platzhaltern.
10. **gering · `export/threemf.py:330/452`** — fremde ZIP-Verfahren (Deflate64, AES, verschlüsselt) fliegen als `NotImplementedError`/`RuntimeError` roh durch; das Ablegen der Datei tut sichtbar nichts, und die kaputte Quelle bleibt als Waise im Dokument.
11. **gering · `ingest/ops.py:158`** — „Auf das Bett setzen" tut bei einer Baugruppe nichts und sagt es nicht (kein Finding). Besser: die Gruppe gemeinsam absetzen.
12. **gering · `ingest/loader.py:46`** — `HEAVY_TRIANGLES=500 000` verspricht in seiner Warnung, was `MAP_LIMIT=120 000`/`FEATURE_LIMIT=200 000` längst tun — drei Schwellen, eine Frage; zwischen 200 k und 500 k schweigt die Eingangsstufe.
13. **gering · PLAUSIBEL · `handover.py:1726–1748`** — `_find_gcode` nimmt die jüngste Datei im Zielordner (latent: fremder Nutzerordner → Ergebnis des vorigen Laufs).
14. **gering · `handover.py:1466–1476`** — zwei Fehler erben Vorschläge, die nicht passen („Zusätzliche Programme …" für „Es wurde nichts übergeben").
15. **gering · PLAUSIBEL · `handover.py:1163`** — `--load-settings` trennt mit Semikolon; ein Semikolon im Profilpfad bricht mit irreführender Slicer-Meldung.

**Sauber:** Slicer-Aufruf als Argumentliste ohne Shell, Zeitlimit/Abbruch/Startfehler je mit `ExternalToolError`; `slicer_keys` über vier Bestandstests gedeckt; Regel 12 und 14 im Gebiet eingehalten.

**Testlücken:** Farb-Roundtrip (write **und** read mit Slot-Vergleich) fehlt; der Einheiten-Test prüft, was der Code tut, statt was er soll („mm in der Liste?" bliebe unbemerkt); für `write_assembly`/`slice_model` fehlt das Schreibfehler-Gegenstück.

---

## G. Wissensschicht und Bausteine (`app/core/knowledge` inkl. `parts/`, `standards.toml`, `print_settings`)

Achtung: `standards.toml`, `parts/fasteners|mechanics|mounting|ops|structure.py` tragen ungestagte Stände anderer Sitzungen — betroffene Befunde sind markiert.

1. **hoch · VERIFIZIERT · `parts/fasteners.py:385–421`** — „Gewinde in Bohrung schneiden" **vereint** sein Werkzeug statt abzuziehen (`internal` trägt kein `subtractive_on`): 30×30×20-Klotz 18000 → 18286 mm³ — aus der Bohrung wächst ein Bolzen. Der am 24.08. dokumentierte Fix reparierte nur die Übergabe, nicht die Wirkung.
2. **hoch · VERIFIZIERT · `parts/mechanics.py:148–177`** — dieselbe Struktur an der Rastnase: `negative=True` („zum Abziehen") vereint ebenfalls — das Gegenstück wird eine zweite, größere Rastnase.
3. **hoch · VERIFIZIERT · `parts/fasteners.py:125–127`** — `screw_hole.head_room` ist wirkungslos: der Freiraum-Zylinder wächst nach oben über die Trägerfläche hinaus (head_room 0 und 5 tragen identisch 101,827 mm³ ab).
4. **hoch · VERIFIZIERT · `parts/testbodies.py:339–354`** — die Strichmarkierung der Toleranzleiter ist mehrdeutig (`round(w*100)%10 or 10`): mit den Vorgaben tragen 0,10 und 0,20 dieselben 10 Striche — der Kalibrierdruck ist nach dem Drucken nicht ablesbar. Zudem behauptet der Docstring erhabene Schrift, gebaut wird vertieft.
5. **hoch · VERIFIZIERT · `parts/structure.py` + `parts/registry.py:393/417` — Baustelle** — `register_part` setzt `version = changes[-1].version`: der Rippen-Eintrag vom 25.08. senkt die Version von „4" auf „2", `changed_since_library("4")` sieht nichts — die Maßänderung erreicht kein bestehendes Projekt (§24.4, Checkliste Punkt 8). `gusset` startet mit „2" ohne je „1" gewesen zu sein.
6. **mittel · VERIFIZIERT · `parts/fasteners.py:329–360`** — `nut_trap` mit `direction="bottom"` dreht den Körper, nicht seine Merkmale: `pocket_1`/`bore_1` bleiben bei alter Lage/Achse — eine daran ausgerichtete Passung sitzt quer.
7. **mittel · VERIFIZIERT (Rechnung) · `standards.toml:106/131` — Baustelle** — Mutternhöhen nach zurückgezogener DIN 934 statt ISO 4032: M5-Tasche 4,10 mm für eine 4,70er Mutter — 0,6 mm zu flach, bei der verbreitetsten Größe; der `caveat` verspricht das Gegenteil.
8. **ZURÜCKGENOMMEN (widerlegt durch b0, 25.08.2026)** — Die Tabelle stimmt: ISO 10642 nennt dk = 2,00·d (M3–M12 nachgeschlagen); der Faktor 2,24 gehört zum theoretischen Kegelschnittpunkt, nicht zum Kopf. Eine „Korrektur" hätte die Senkung bei M8 um 1,9 mm zu weit gemacht.
9. **mittel · VERIFIZIERT · `standards.toml:170–191` + `fasteners.py:254`** — bei allen sechs Einpressbuchsen ist `outer == hole` (eingetragen ist der Bohrungs-, nicht der Rändeldurchmesser): die Einführfase degeneriert zu konstant 0,30 mm.
10. **mittel · VERIFIZIERT · `parts/mounting.py:99` — Baustelle** — die Haltelippe der Magnettasche hält bei keinem Material (fest −0,2 mm gegen +0,20…0,35 Spiel aus dem Profil); zusätzlich Regel 7 (Toleranzzahl im Baustein).
11. **mittel · VERIFIZIERT · `parts/recipe.py:467–474`** — `_default_profile()` nimmt per Titel-Sortierung **ABS** statt des deklarierten PLA: Vorschaubild und Bereichstest jedes Rezepts rechnen mit ABS-Toleranzen. `make_profile()` ohne Argumente täte das Richtige.
12. **mittel · VERIFIZIERT · `parts/mechanics.py:262–268`** — `living_hinge` liefert bei `film >= thickness` stumm eine massive Platte ohne Nut (beide Werte im deklarierten Bereich; der Bereichstest fährt die Kombination nicht, weil `corners()` zyklisch füllt). Regel 21.
13. **gering · VERIFIZIERT · `parts/fasteners.py:159–217`** — `size_for_insert`/`size_for_nut_trap`/`size_for_thread` hängen an der TOML-Dateireihenfolge statt an einer Sortierung (mit umgedrehter Reihenfolge gemessen falsch); dazu iteriert `size_for_nut_trap` über `screw_sizes()` statt `nut_sizes()`.
14. **gering · PLAUSIBEL · `parts/mounting.py:272/286`** — `keyhole` addiert 0,6 mm Kopfspiel fest und hat kein `play`-Feld: die Kalibrierung nach §28.3 erreicht diesen Baustein nie (der Test überspringt genau die Bausteine ohne `play`).
15. **gering · Baustelle · `parts/mounting.py:610–618`** — `foot/pocket` endet als einziger subtraktiver Baustein exakt auf z=0 statt um `OVERLAP` hinauszureichen; A/B-Gegenprobe zeigte keinen Schaden — Regelabweichung ohne gemessene Wirkung.
16. **gering · PLAUSIBEL · `calibration.py:88–101`** — `check()` prüft nur auf negativ: NaN und Unsinnswerte laufen durch und machen jede `auto:`-Passung zu NaN (der Dialog begrenzt, der Kern nicht).
17. **gering · PLAUSIBEL · `standards.py:161` + `rules.py:113`** — beide `load()` ohne `TOMLDecodeError`-Behandlung: eine beschädigte mitgelieferte Datei endet als roher Stapelabzug beim Start (die Nachbarn machen `ValidationError` daraus).
18. **gering · VERIFIZIERT · `parts/structure.py:55–57`** — Änderungstext „ab 1,2 mm ändert sich kein Maß"; die wahre Schwelle ist 1,2121 (bei 1,2 ändert sich 0,792→0,800).
19. **gering · VERIFIZIERT · `parts/mechanics.py`** — `snap_connector` führt zwei Änderungseinträge mit derselben Version „4" — für `changed_since_library` nicht unterscheidbar.

**Testlücken:** Bausteine werden als Geometrie gründlich, als **Wirkung im Dokument** kaum geprüft — niemand prüft, ob das Innengewinde-Werkzeug abgezogen wird (Anschluss-Testart); `by_direction()` zieht seine Erwartung aus derselben Funktion wie der Prüfling (Bausteine ohne `subtractive_on` fallen aus beiden Listen); der Bereichstest misst „Mindestwandstärke" am Hüllquader und füllt Ecken zyklisch statt kartesisch (lässt Befunde 4 und 12 durch); `spec.version == changes[-1].version` ist tautologisch.

---

## H. Agentenschicht und Backends (`app/core/agent`, `app/core/backends`, `generate.py`)

1. **hoch · VERIFIZIERT · `agent/apply.py:152–176` + `agent/session.py:319–335` + `ui/chat.py:560`** — der Rücknahme-Vorschlag nimmt **alle** jüngeren Transaktionen mit („bis einschließlich"), angekündigt ist eine: `undo_of=t1` bei vier Transaktionen leert das Projekt, ein einzelnes Redo bringt nur t1 zurück, und die nächste Anwendung verwirft t2–t4 endgültig. Regel 16 ist für diesen Vorschlagstyp nicht eingelöst.
2. **hoch · VERIFIZIERT · `agent/remote.py:70` + `agent/apply.py:55`** — beide `create_from_scad`-Sperren prüfen den Namen: ein Rezept mit einem `create_from_scad`-Schritt wird als `insert_<name>` registriert und ist über die Leitung erreichbar und auto-annehmbar — „kein ausführbarer Quelltext ohne Klick" fällt. (§32-Prüfung selbst greift weiter.) Fix: nach dem, was eine Op tut, fragen (`foreign.runs_foreign_code`), nicht nach ihrem Namen.
3. **hoch · VERIFIZIERT · `backends/llm.py:154–186/465–486/704–716`** — sechs Formen kaputter Modellantworten (HTML vom Proxy, JSON-Liste, content als str, arguments als JSON-Text …) enden als roher `InternalError` mit Fehlerbericht-Bitte statt als korrigierbare Meldung. Der arguments-als-String-Fall ist bei OpenAI-kompatiblen Servern real.
4. **mittel · VERIFIZIERT · `backends/comfy_setup.py:347–368`** — Frist und Abbruch werden nur je gelesener Zeile geprüft: ein schweigender Kindprozess (stilles pip/TLS) friert die Einrichtung ein, „Abbrechen" wirkt nicht (gemessen: nach 8 s bei 2-s-Frist noch am Leben).
5. **mittel · VERIFIZIERT · `backends/mesh.py:246–322`** — eine ComfyUI-Adresse ohne Schema (`127.0.0.1:8188`) ist dauerhaft „nicht erreichbar", und der eigens gebaute „keine Adresse"-Zweig ist für seinen eigenen Fall unerreichbar; `ollama_endpoint` nebenan löst es vor. 
6. **mittel · VERIFIZIERT · `backends/llm.py:1088`** — `ollama_speed` schickt an die rohe Adresse (drei Nachbarn nutzen `ollama_endpoint`): genau der Kunde, dem die Langsam-Warnung gilt, bekommt keine.
7. **mittel · VERIFIZIERT (Lesen) · `ui/main_window.py:5897–5900`** — die Fernsteuerung ignoriert das `transaction`-Argument von `undo_transaction` und nimmt das Letzte zurück — mit der Antwort „Zurückgenommen."
8. **mittel · VERIFIZIERT · `agent/context.py:72` + `perceive/digest.py:116/158`** — Objekt- und Dateinamen aus fremden Dateien reisen ungerahmt und ungekürzt als Nutzertext in den Prompt (Prompt-Injection-Fläche; für den Chat existiert die Rahmung `CARRIED_CHAT_NOTICE` bereits, für die Szene nicht).
9. **mittel · VERIFIZIERT (Lesen) · `backends/mesh.py:206–212/762–810`** — eine laufende Mesh-Erzeugung ist nicht abbrechbar (bis 3600 s); der Dialog lässt nach 50 ms los, der Arbeiter feuert später in einen geschlossenen Dialog.
10. **mittel · VERIFIZIERT · `backends/llm.py:480–486` + `agent/session.py:203–213`** — das Zugbudget zählt `cache_creation/read_input_tokens` nicht (beide Namen kommen im Repository nicht vor): Deckel und Kostenanzeige messen bei gesetztem `cache_control` die falsche Zahl.
11. **mittel · VERIFIZIERT (grep) · `llm.py:485/711` + `session.py:196–217`** — `stop_reason` wird gespeichert und nie ausgewertet: `max_tokens` (abgeschnittene Antwort gilt als vollständig) und `refusal` (leerer Vorschlag ohne Satz) verschwinden still.
12. **gering · `generate.py:248`** — `Generation.transactions` lässt `fit_to_size` aus (gemessen t1/t3 von t1–t3); der erste Aufrufer, der damit zurückrollt, lässt eine Transaktion stehen.
13. **gering · PLAUSIBEL · `comfy_setup.py:632/691`** — Zwischenordner unter festem Namen im gemeinsamen Temp (unter Linux vorbelegbar); gehört unter `app.core.paths`.
14. **gering · `agent/remote.py:184–206`** — `check_call` weist gesammelte Parameter (`GATHERED_KINDS`) nicht ab — die Chat-Sitzung tut es mit guter Begründung, die Leitung nicht.
15. **gering · `agent/session.py:319–335`** — ein zweiter `undo_transaction` überschreibt den ersten wortlos.
16. **gering · `agent/session.py:97–101`** — `tr()` statt `_()` im Kern-Fehlertext (Sprache wird beim Werfen statt beim Anzeigen aufgelöst).
17. **gering · `comfy_setup.py:860`** — `nodes_load` als einziger `_run`-Aufruf ohne Abbruchmerker.

**Sauber:** Regel 11 auf dem direkten Weg (check_source als erste Anweisung, Zeit-/Speichergrenze, gebundene Liste), harte Schrittgrenze, unbekannte Werkzeuge/IDs/Werte als korrigierbare Meldungen, Misch-Schranke doppelt, kein `eval`, Abschaltbarkeit ohne Schlüssel/Ollama gemessen sauber.

**Testlücken:** der Rücknahme-Fall „bekannte alte Kennung" fehlt; `run_remote` gegen das Werkzeugschema fehlt; fremde Antworten werden nur in selbst erzeugter Wohlform geprüft; `ollama_speed`, `comfy_setup._run` (Frist/Abbruch) und `Generation.transactions` haben gar keinen Test.

---

## I. Fenster, Sitzung, Panels (`app/ui/main_window`, `session`, `panels`, `overlay`, `analysis_bar`, `tool_strip`, `command_palette`, `start_screen`, `style`, `icons`)

`main_window.py` und `panels.py` trugen während des Reviews ungestagte fremde Änderungen; Commit 48304e72 einer Nachbarsitzung hat einen Teil der Sprachfunde bereits behoben.

1. **hoch · VERIFIZIERT · `session.py:1108–1113/1183–1187/1479–1484`** — „Abbrechen" hält nichts an, wenn ein Nachlauf eingereiht ist: `cancel()` löscht `_rerun_pending` nicht, die Statuszeile meldet „Abgebrochen", und im selben Atemzug startet der eingereihte Lauf — `busy` ist wieder wahr. Fix: ein Nutzer-Abbruch verwirft die eingereihte Anfrage.
2. **hoch · VERIFIZIERT · `main_window.py:3811/5135/5256/7124`** — vier Arbeiter ohne `crashed`-Empfänger (`_OllamaSizeWorker`, `_MapWorker`, `_SliceWorker`, `_UpdateWorker`): Legende bzw. „Die Schichtanalyse läuft …" bleiben für immer stehen, `_slice_waiters` leert sich nie, „Nach einer neuen Version sehen" wird zum toten Knopf. Der Test prüft „`crashed.connect` steht **in der Datei**" — in der Datei mit sechs Arbeitern blind. Fix: vier connects plus Test je Startstelle.
3. **mittel · VERIFIZIERT (Ende zu Ende) · `command_palette.py:405–412/322` + `main_window.py:4993–5003`** — Pfeiltaste + Enter führt einen gesperrten Paletteneintrag aus und öffnet die modale Sackgasse („Wählen Sie zuerst ein Objekt"), die der eigene Kommentar als beseitigt beschreibt (Regel 19).
4. **mittel · VERIFIZIERT · `main_window.py:5344`** — nach einem Agentenzug bleibt der Abbrechen-Knopf sichtbar stehen (`isVisible()` wird gelesen, bevor der Balken ausgeblendet ist); `_on_split_busy` daneben macht es richtig.
5. **mittel · VERIFIZIERT · `main_window.py:6582–6591/5372–5379/3063–3075`** — der Fortschrittsbalken hat vier Besitzer mit drei Freigabebedingungen, keine fragt Export/Download: endet eine Auswertung während eines laufenden Exports, verschwinden Balken und Statuszeile, während der Export weiterschreibt. Fix: eine gemeinsame Auskunft `_anything_running()`.
6. **mittel · VERIFIZIERT · `panels.py:1249–1256` + `main_window.py:5574–5580`** — Rechtsklick auf einen bereits ausgeblendeten Körper zeigt „Alles andere ausblenden", die Wirkung ist „alles einblenden": Beschriftung und Handler lesen dasselbe Feld mit verschiedener Frage.
7. **mittel · VERIFIZIERT (statisch) · `main_window.py:2993–3018` + `ingest/fetch.py:112`** — der Modell-Download hat weder Abbrechen-Knopf noch Abbruchweg — ein 300-MB-Modell an langsamer Leitung ist nur durch Beenden zu stoppen (§2.8).
8. **mittel · VERIFIZIERT · `main_window.py:5305–5310` vs. `6760–6765`** — ein Klick auf einen Befund im Prüfbericht färbt das Modell als Analysekarte um, ohne Werkzeug/Legende zu aktivieren: reine Farbe ohne zweite Kodierung (Regel 18, §18.4). Fix: `tools.activate("analysis")` wie in `_show_error_location`.
9. **mittel · VERIFIZIERT · `analysis_bar.py:79–96/233–238`** — `show_problem` lässt den Hinweistext außerhalb des Layouts zurück (Geometrie 100×30 für einen 576-Punkte-Satz): genau die zwei erklärenden Sätze („wird berechnet …", „zu groß") sind betroffen.
10. **mittel · PLAUSIBEL · `main_window.py:3112–3128` + `session.py:1027–1055/1445–1451`** — Auto Split ist gegen einen zweiten Start nicht gesperrt; nach dem 10-s-Aufgeben von `wait_for_idle` überschreibt der zweite Arbeiter den ersten, `_on_split_done` prüft den Absender nicht: `split_running` lügt, der verworfene Plan kann doch angewandt werden, ein Thread überlebt sein Fenster.
11. **gering · VERIFIZIERT** — acht modale Dialoge (`PartCatalog`, `AboutDialog`, `VariantsDialog`, `KeyDialog`, `ParameterDialog`, `CalibrationDialog`, `SupportDialog`, `GenerateDialog`) sammeln sich ohne Freigabe am Fenster (gemessen: 3 Runden → 6 lebende QDialog-Kinder); nur zwei Dialoge rufen `deleteLater`. Fix: `WA_DeleteOnClose` einheitlich.
12. **gering · VERIFIZIERT · `main_window.py:1743/1950/1986` über `_add_action:2277`** — `triggered(bool)` landet in Slots mit `str`-Signatur (`action_manual(False)` u. a.); heute durch Falschheits-Prüfungen gedeckt, für den nächsten Leser eine gestellte Falle. Fix: `_add_action` verwirft das Argument.
13. **gering · PLAUSIBEL · `main_window.py:5709/6985` + `history.py`** — die Nachfrage vor dem Verwerfen abgeschnittener Redo-Schritte steht vor zwei von ~zwölf Wegen; Import, Split, Deckel, Parameter, Passung, Katalog und Agent-Annahme verwerfen kommentarlos.
14. **gering · `panels.py:2008`** — Kontextmenü des Prüfberichts öffnet am falschen Bezugspunkt (`self.list` statt `viewport()`); die zwei Nachbarn machen es richtig.
15. **gering** — deutsche Bezeichner `vorhanden`, `nach_titel`, `lebende`, `versteckt` (`main_window.py:3959/3966`, `overlay.py:123`, `command_palette.py:352`) — nicht in `GERMAN_STEMS`, von 48304e72 nicht erfasst.
16. **gering · PLAUSIBEL · `main_window.py:5975–5978` + `remote_server.py:72–80`** — scheitert ein Fernaufruf in der Transaktion, öffnet der Hauptthread einen modalen Fehlerdialog und die Gegenstelle läuft in den Zeitablauf statt in den Grund.

**Testlücken:** `crashed`-Test greift je Datei statt je Startstelle; „Abbrechen während Nachlauf eingereiht" fährt niemand; Offscreen-Läufe ohne `show()` machen jede `isVisible()`-Zusage zur Prüfung über der leeren Menge (eigene Messung erst mit gezeigtem Fenster rot); keine `PaletteEntry` mit `available=False` im Test; Isolier-Beschriftung nie aus dem Zustand „schon ausgeblendet" geprüft.

---

## J. Viewport und Skizzeneditor (`app/ui/viewport.py`, `app/ui/sketch_editor.py`)

1. **hoch · VERIFIZIERT · `viewport.py:3623–3654`** — `_object_at` prüft weder `visible` noch `_hidden` noch `_plate`: ein Klick wählt ausgeblendete Körper und Körper fremder Platten (bei mehreren Treffern gewinnt der kleinste — also gerade das Unsichtbare). Gleiche Lücke in `_nearest_mesh` und `_bore_aim`. Die nächste Operation trifft das falsche Teil.
2. **hoch · VERIFIZIERT · `sketch_editor.py:1226–1234/1358/3131`** — der Fangradius hängt im Viewport-Modus am Maßstab des unsichtbaren Canvas: real 6,67 mm statt 8 Bildpunkte — ein Klick 5 mm neben einem Punkt schnappt auf ihn und erzeugt eine ungewollte Deckungsbedingung (gemessen).
3. **hoch · VERIFIZIERT · `sketch_editor.py:1156–1168`** — einen Punkt ziehen (oder „Koordinaten …") baut das Element neu und verliert `construction`: aus einer Mittellinie wird eine Profilkante — der Körper bekommt eine Trennung, ohne Meldung. Gleiche Familie in `sketch/edit.py:168–329` (trim/extend/offset).
4. **hoch · VERIFIZIERT · `sketch_editor.py:3176–3240` vs. `3131–3141`** — `use_viewport()` hängt nur die Ebenen-Kürzel um: elf von dreizehn Zeichenkürzeln (L, C, A, D, T, O, X, P, S, Strg+Z, Pos1) feuern im gefahrenen Modus nie; Strg+Z und Pos1 sind zusätzlich am Fenster gesperrt — es gibt keinen Tastaturweg, und der Einpassen-Tooltip verspricht Pos1. Zwei Tests decken es zu (`<= 1` Besitzer besteht mit null; ein Docstring behauptet den Zustand, den der Code nicht hat).
5. **hoch · VERIFIZIERT (Quelltext beider Seiten) · `viewport.py:3490–3514/5531–5571`** — Qt-Logikpunkte und VTK-Gerätepunkte werden vermischt (`_note_pointer` ohne `devicePixelRatio`): auf jedem HiDPI-Schirm stehen Fangkreuz/Vorschau woanders als der Klick; `pixels_per_mm` liefert Gerätepunkte und wird gegen Logikpunkt-Schwellen gehalten (Raster zu fein, Fang zu fein). Randfall derselben Sache: `main_window.py:5626` (Kontextmenü am falschen Ort).
6. **mittel · VERIFIZIERT (Quelltext) · `viewport.py:5627–5657`** — der Rechtsklick kennt den Skizzenmodus nicht: er ändert die Objektauswahl und öffnet das Objektbaum-Menü; das gebaute Skizzen-Kontextmenü (Koordinaten/Löschen/Bedingungen) ist im Viewport-Modus unerreichbar — zusammen mit Befund 4 gibt es keinen Weg zum Löschen außer der Werkzeugleiste.
7. **mittel · VERIFIZIERT · `sketch_editor.py:1515–1558`** — das Maß am Zeiger (E19) ist im Viewport-Modus unsichtbar (Kind des versteckten Canvas), und der Ziffern-Eingabeweg braucht dessen Fokus — den Normalweg des Bemaßens gibt es im gefahrenen Modus nicht.
8. **mittel · VERIFIZIERT (Quelltext) · `viewport.py:5173–5180`** — `view_from` (Strg+0–6, ViewBar) ruft `reset_camera()` auf alles Sichtbare: rahmt Bauraum-Kulisse statt Teil — exakt der Fehler, den `Viewport.reset_camera` in eigenen Worten beschreibt; im Skizzenmodus zerstört es zusätzlich die Ebenenansicht.
9. **mittel · VERIFIZIERT (Quelltext) · `viewport.py:3838–3866/4865–4886/4537–4551`** — Merkmalsbeschriftung, Griffscheibe und Differenzkörper folgen der Plattenverschiebung nicht (die Merkmalsfläche schon): dieselbe Bohrung, zwei Orte, eine Bettbreite auseinander.
10. **mittel · VERIFIZIERT (Quelltext) · `viewport.py:2856–2864`** — der Anzeige-Cache hält genau einen Eintrag: zwei große Körper verdrängen einander, und `show_scene` dezimiert bei jeder Auswahl beide neu im Hauptthread (§2.8-Blockade).
11. **mittel · VERIFIZIERT · `viewport.py:3672`** — die Maßbeschriftung im Bild ignoriert die Anzeigeeinheit (MeasureBar „2,3622 in", Viewport „60 mm") und enthält die feste deutsche Zeichenkette `grad` ohne `tr()` (Regel 20; toter Zweig); `refresh_labels` zieht bei Einheitenwechsel nicht nach.
12. **gering** — Themenwechsel lässt Druckplatte/Bauraum in alten Farben stehen, bis die Plattenzahl sich ändert (fast schwarzes Bett auf hellem Grund).
13. **gering · VERIFIZIERT** — Mausbewegungen über dem Wertfeld werden als Viewport-Koordinaten gelesen (`eventFilter` prüft `watched` bei MouseMove nicht): falscher Zeiger, Vorschausprung im Skizzenmodus.
14. **gering · VERIFIZIERT** — `ghost`-Parameter (§18.7) wird angenommen, gespeichert und nie gelesen — kein Geist im Bild.
15. **gering** — `viewport.py:2820–2826`: `away / length * length * explosion` — die behauptete Normierung findet nicht statt; wer die Zeile ändert, ändert das Verhalten unabsichtlich.
16. **gering · PLAUSIBEL** — `show_build_volume` befragt `_sketch_frame` nicht: ein während des Zeichnens neu gebautes Bett käme sichtbar zurück (heute schwer auslösbar; die Zusage hängt an der Aufruf-Reihenfolge statt am Zustand).
17. **gering** — `abs(… - 1.0) > 1e-4` zweimal als Streuzahl neben `EPS_DISPLAY` (Skalierzug beim Ziehen vs. Tippen).

**Testlücken:** kein Test mit Fokus außerhalb des Panels (der einzige reale Zustand des Modus) und keiner mit `devicePixelRatio ≠ 1` — beide hätten die Befundgruppen 4 und 5 in einem Lauf gefangen; kein Test klickt auf einen ausgeblendeten Körper oder eine fremde Platte; Offscreen sieht keine Aktoren, darum bleiben Überlagerungsversätze unbemerkt.

---

## K. Dialoge (`op_dialog`, `dialogs`, `print_settings_dialog`, `recipe_dialog`, `catalog`, `generate_dialog`, `install_dialog`, `support_dialog`, `first_run`, `chat`, `tour`, `survey`, `variants_dialog`, `manual_window`, `leash`, `loading`, `labels`)

`recipe_dialog.py` ist aktive Baustelle der Sitzung -ce (während des Reviews zweimal committet, weitere Arbeit angekündigt) — die Rezept-Befunde unten sind gegen ae6468b0 geprüft, können aber schon überholt sein.

1. **hoch · VERIFIZIERT · `generate_dialog.py:382–383/436`** — „Erzeugen" ist in drei von fünf Bereitschaftslagen freigegeben und tut beim Klick nichts (`_start` steigt still aus): kein Balken, kein Satz. Der Kommentar begründet das Freigeben, `_start` widerspricht ihm.
2. **hoch · VERIFIZIERT · `variants_dialog.py:110–112`** — „Erster Wert" folgt der Parameterauswahl nicht (keine Signalverbindung): wer *Spiel* wählt, bekommt eine Kalibrierreihe ab 60,0 mm Spiel — §28.3 im Kern getroffen.
3. **hoch · VERIFIZIERT · `op_dialog.py:1063–1069`** — ein `int`-Parameter mit gespeichertem Ausdruck (`plates = "=@anzahl"`) lässt den Dialog mit roher `ValueError` gar nicht aufgehen — der für `float` behobene Fehler steht beim Zwilling noch (27 int-Parameter im Register).
4. **hoch · VERIFIZIERT · `recipe_dialog.py:590/681–687`** — nach einem Arbeiter-Absturz steht `<built-in method title of str object …>` im Fenster (`getattr(error, "title")` auf einem str); alle zwölf Nachbarstellen verpacken `crashed` in `InternalError`.
5. **mittel · VERIFIZIERT · `op_dialog.py:1084–1085`** — ein unbekannter Auswahlwert aus dem Dokument wird stumm zum ersten Eintrag (Regel 21); die Nachbarzweige (object/feature/image) tragen Unbekanntes ausdrücklich ein.
6. **mittel · VERIFIZIERT · `op_dialog.py:1209–1227`** — `take_point` meldet Erfolg, obwohl ein fx-Feld den Klick verschluckt (`values()` liefert weiter den Ausdruck); gleiche Naht bei `_couple_sketch_measures`.
7. **mittel · VERIFIZIERT (Lesung) · `variants_dialog.py:243–260`** — die Warnung „Nicht jede Variante ließ sich rechnen — siehe Prüfbericht" wird sofort überschrieben und der Dialog geschlossen; die `variants.stopped`-Befunde erreichen den Prüfbericht nie.
8. **mittel · VERIFIZIERT · `print_settings_dialog.py:1932–1939`** — unbekannte Enum-Werte und Zahlen außerhalb der Feldgrenzen werden stumm umgeschrieben und beim ersten Feldwechsel zurückgespeichert (betrifft Projektdateien und fremde Slicer-Profile; der ausgelieferte Bestand ist sauber — gemessen).
9. **mittel · VERIFIZIERT · `first_run.py:184`** — eine unbekannte Sprache in den Einstellungen leert das Feld und schreibt `"None"` zurück; die geschützte Fassung steht 275 Zeilen tiefer in derselben Datei.
10. **mittel · VERIFIZIERT · `recipe_dialog.py:143–145` → `op_dialog.py:71`** — eine frei getippte Einheit („cm") schaltet die Umrechnung ab: Feld zeigt „[cm]", der Kern baut Millimeter; im Zollbetrieb spricht eine Zeile eine andere Einheit als ihre Nachbarn.
11. **mittel · VERIFIZIERT** — „Demo — noch 1 Tage" am letzten Tag, an fünf Fundstellen und in fünf Sprachen (`labels.py:1121`, `dialogs.py:1035/1048/1386/1390`); das Einzahl-Muster steht in `chat.costs` vor.
12. **mittel · VERIFIZIERT · `catalog.py:519`** — der vom Kunden getippte Bausteintitel geht unmaskiert in ein RichText-Label (`<b>{spec.title}</b>`): ein Titel mit spitzen Klammern verschluckt Text bzw. verschiebt die Formatierung. Fix: `html.escape`.
13. **gering** — `variants_dialog.py:103`: Schrittweite 0 erlaubt (Kern prüft sie auch nicht) → N identische Teile als „Kalibrierdruck".
14. **gering** — `recipe_dialog.py:225–232`: `ordered()` lässt `min == max` durch — der Bereichstest prüft dann eine Ecke und meldet bestanden.
15. **gering** — `recipe_dialog.py:669–679`: der Warnsatz zum gescheiterten Bereichstest wird gesetzt und sofort vom `accept()` unlesbar gemacht (durch `catalog._range_warning` entschärft — dann ist er toter Text).
16. **gering · VERIFIZIERT** — `op_dialog.py:323`: der Ausdruckshinweis schreibt den Punkt („= 17.5 mm") direkt unter ein Komma-Feld („17,50"); `labels.localised` existiert genau dafür.
17. **gering** — deutsche Bezeichner an sechs Stellen: `klappe` (op_dialog:1197), `beispiel`/`satz` (install_dialog:244), `erste` (print_settings_dialog:1657), `trenner`/`gezaehlt` (support_dialog:568); Stämme nachtragen.
18. **gering** — `support_dialog.py:699`: feste deutsche Zeichenkette `--- anhänge ---` im Bericht, den der Kunde weitergibt.
19. **gering** — `recipe_dialog.py:304–306`: Attribut-Docstring hängt am falschen Feld.
20. **gering** — `recipe_dialog.py:531–532`: der Speichern-Wächter kehrt beim laufenden Bereichstest wortlos zurück; `_update_enabled` sollte den Arbeiter mitprüfen (Muster in `support_dialog`).

**Testlücken:** Kein Test im Gebiet fährt einen freigegebenen Knopf wirklich durch und misst die Wirkung — `test_an_unknown_answer_does_not_lock_the_button` prüft `isEnabled()` und klickt nie (eine Zeile hätte Befund 1 gefangen). Es fehlt die Testart „fremder Wert" (Enum außerhalb `choices`, Ausdruck im int-Feld, Punktklick auf fx-Feld). `test_variants_ui` prüft Nebenläufigkeit, keine einzige Wertzusage.

---

## L. Querschnitt: Aktivierung, Update, Support, Handbuch, CLI, i18n

1. **mittel · VERIFIZIERT · `activation/store.py:16–20` vs. `:152–157`** — der versprochene Schutz gegen eine zurückgestellte Uhr existiert im ausgelieferten Demo-Zweig nicht: Uhr auf 2020 → 2495 Tage Demo, und es entsteht keine Marke (`last_seen` wird nur im Testlauf-Zweig geführt).
2. **mittel · VERIFIZIERT · `install.py:573–591`** — `TIMEOUT_SECONDS=900` greift nur, wenn der Installer etwas schreibt: ein stiller winget/brew hängt unbegrenzt, der Arbeiter-Thread überlebt sein Fenster.
3. **mittel · VERIFIZIERT · `manual.py:1572–1579`** — „Meldungen im Wortlaut" verspricht Vollständigkeit über eine handgepflegte Modulliste: `SendFailed` („Die Rückmeldung ließ sich nicht senden" — der wahrscheinlichste Fehler überhaupt) fehlt im ausgelieferten Handbuch; der Handbuchinhalt hängt an der Importreihenfolge.
4. **mittel · VERIFIZIERT · `cli/main.py:635–653`** — die Kommandozeile installiert nie eine Sprache: ein spanischer Kunde bekommt deutsche Hilfe- und Fehlertexte, obwohl die Übersetzungen in den Katalogen liegen.
5. **gering · VERIFIZIERT · `updates.py:23–24`** — „Die Prüfung beim Start ist aus, bis jemand sie einschaltet" ist seit 23.08. falsch (Vorgabe `True`, Alt-Dateien werden angehoben); die veröffentlichte Datenschutzerklärung stimmt, der Docstring nicht.
6. **gering · VERIFIZIERT · `updates.py:361–371`** — `check()` sendet `User-Agent: Python-urllib/3.13` (CDN-Sperren → Prüfung scheitert still; Datenschutztext verspricht „kein Kennzeichen"); `download()` macht es richtig.
7. **gering · VERIFIZIERT (Lesen) · `activation/integrity.py:46–47` vs. `:107–111`** — „was das Manifest darüber hinaus deckt, wird mitgeprüft" stimmt nicht: geprüft werden nur die vier `BOUNDARY_FILES`.
8. **gering · `i18n/catalog.py:47–53`** — einzige ungesicherte Dateilesung des Gebiets: eine beschädigte Katalogdatei beendet den Start mit rohem `JSONDecodeError` (alle Nachbarn fangen).
9. **gering · latent · `i18n/extract.py:36–49`** — der Einsammler kennt das Kontext-Argument von `_()`/`tr()` nicht; der erste `_("…", "Kontext")`-Aufruf bliebe in jeder Sprache deutsch, und der Übersetzungstest (gleiche Quelle) merkte nichts.
10. **gering · `figures.py:1272`** — stilles `except Exception: return None`: eine dauerhaft brechende Abbildung verschwindet aus Fenster, Handbuch und Website ohne Spur im Protokoll.
11. **gering · PLAUSIBEL · `cli/main.py:655–682`** — kein letztes Auffangnetz: ein unerwarteter Fehler erreicht den Nutzer als Stapelabzug (sechs naheliegende Fehlerpfade enden sauber — gemessen; die Lücke bleibt).
12. **gering · `support_dialog.py:391–394` + `core/support.py:9–10`** — „vorher sieht er, was mitgeht" gilt nicht für das vorangekreuzte Protokoll (nur Name+Größe in der Vorschau); `export/writer.py:528` und `report.py:133` protokollieren absolute Pfade samt Windows-Kontonamen.

**Sauber (ausdrücklich geprüft):** Ed25519 streng nach RFC 8032 samt Kleingruppen-Ablehnung; Update-Kette vollständig signiert, HTTPS+Host-Bindung, halber Download wird gelöscht; `report.write` hängt an genau einem Knopf; `markup` maskiert vor dem Auszeichnen; §38-Pfade; CLI-Fehlerpfade mit Titel, Grund, Zahlen, Vorschlägen.

**Testlücken:** Übersetzungstest prüft gegen denselben Einsammler, den er absichern soll; Handbuchtest läuft über eine andere Menge als die Erzeugung; `report.py` hat keine eigene Testdatei; `install._stream` keinen Zeitmaß-Test.

---

## M. Muster über allen Gebieten

Vier Muster tragen die Mehrzahl der hohen Befunde:

1. **Die Naht ist ungeprüft, nicht die Bausteine.** Loch-Volumen nur für extrude, Farb-Roundtrip nur schreibend, Gewinde-Werkzeug nur als Geometrie, `crashed` nur je Datei: Tests bauen eine Seite selbst und bekommen die andere als Attrappe. („Eine Kette endet am letzten Glied.")
2. **Die Erwartung kommt aus dem Prüfling.** `by_direction()` aus `cuts_by_parameter`, Übersetzungstest aus `message_ids()`, Handbuchtest aus `vars(errors)`, Stützvolumen `> 100` gegen sich selbst — der Test bestätigt, was der Code tut.
3. **Ein reparierter Fehler hat unreparierte Zwillinge.** drill hat `anchor`, countersink/plug nicht; extrude/loft lesen die Ebene, pocket/sweep nicht; ValueField für float, nicht für int; `_on_split_busy` richtig, `_on_agent_busy` falsch; `write_plan` fängt OSError, `write_assembly` nicht. Wer einen Fehler behebt, sollte seine Geschwister suchen.
4. **Zusagen in Docstrings misst niemand nach.** Wandtoleranz ±1/6, Entlüftung „nach unten", Uhr-Rückstellungsschutz, „eine Transaktion", „Abbrechbar mitten drin" — je ein Test pro Zusage hätte einen Großteil der hohen Befunde am Entstehungstag gefangen.

## N. Übergaben und Nebenwirkungen

- Sitzung **-ce** (recipe_dialog): Befunde K-4, K-10, K-14, K-15, K-19, K-20 übergeben; capture()-Einfrieren bewusst ausgelassen; F821 war ein Zwischenstand (behoben in ae6468b0) und ist kein Befund.
- Sitzung **b0** (SKADIS/standards/mounting/labels): Befunde G-7, G-8, G-9, G-10, G-14, G-15 und A-4 (deutsche Auswahlwerte in PT — vermutlich genau die choice_label-Baustelle) übergeben.
- Sitzung **61** (Kern+Werkzeuge): Befunde G-5 (Bausteinversion sinkt — im ungestagten Stand), G-11 (Rezept-Vorschauprofil ABS), B-13 (Rezept-Abmeldung), K-12 (catalog RichText) grenzen an ihr Gebiet.
- Der Rest ist unbesetzt und kann nach Priorität abgearbeitet werden; die Doppel-Befunde E-8 ↔ I-2 (fehlende crashed-Verbindungen) sind **derselbe** Fix.

Skripte, Protokolle und Aufnahmen dieser Durchsicht: `.claude/.state/gesamtreview-2026-08-25/`.


---

## O. Stand der Behebung — Paket dieser Sitzung (3d-druck-43, 25.08.2026)

Was diese Sitzung übernommen hatte, ist vollständig behoben und gepusht.
Die Zuordnung Befund → Commit, in Behebungsreihenfolge:

| Befunde | Commit | Kurzform |
|---|---|---|
| J-Paket, D-1…D-6, D-10…D-12, I-1…I-9, I-12, I-14, I-15, A-2, A-3 | e40751dd … 9c481105 | Viewport, Skizzeneditor, Skizzen-Kern erste Hälfte, Fenster/Panels, Bezeichner (elf Commits, siehe Log 15:29–17:09) |
| D-13, D-14, D-16 | b7a42644 | up_to-Feldfehler, eine Vollkreis-Schwelle, ehrliche Redundanz-Paare |
| D-8, D-15 | d36249fd | Selbstschnitt hält an der Zeichnung; Tasche nimmt alle Regionen |
| D-7, D-9 | 71d77d6b | Insel im Loch ist wieder Material; Projektion durch die gewählte Ebene |
| I-10 | ebc63c58 | Auto-Split-Doppelstartsperre samt Absender-Checks |
| L-1, L-5, L-6, L-7 | c4692409 | Demo-Uhr, Update-Absender, Docstring, Manifest deckt alles |
| L-2, L-4, L-9, L-11 | cb81529e | Installer-Uhr, CLI-Sprache, Kontext-Einsammler, CLI-Netz |
| L-3, L-8, L-10, L-12 | 2df8a734 | Handbuch vollständig, Katalog-Lesung, figures-Spur, Support-Vorschau |
| B-15 (Dialog-Hälfte) | 0ad075dd | Grenzen-Schreibseite; Ausdrucksprüfung als Befund bei 61 (ffca0868) |
| I-16-Nachbar (Bezeichner tools/) | 4d036fbd | nach_main → to_main |
| Neufund: 41 Lambda-Ringe aus cc40aaa4 | c1fcb9ea | weak_slot-Fix + absichtlicher Suite-Pin; Messreihe im Commit und im ROADMAP-Register (1ceacbf7) |
| H-1, F-10-Rest (Übergaben von 61) | 9ed9ddc5 | Rücknahme-Warnung klickbar; keine Waisen-Quelle |

Nicht von dieser Sitzung, mit Ort: A-1 (an 61 übergeben — Naht
create_box-Provenienz/perceive), A-4 und G-Paket (b0), K-Paket (ce),
B/C/E/F/H-Pakete (61, laut deren Meldungen komplett). I-11 (WA_DeleteOnClose)
und I-13 sind nach dem Suite-Pin neu zu bewerten und bleiben offen; die
Fensterriss-Mine steht im ROADMAP-Register mit Todesweg und Messwerten.
