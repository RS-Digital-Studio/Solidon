# `app/core/ingest/` — die Eingangsstufe

Jede geladene Datei geht dieselben sechs Schritte (§17.1); was danach in der
Szene liegt, ist normalisiert, und der Rest der Anwendung muss nicht wissen,
woher es kam. **Auch Laden ist eine Operation** und steht im Stapel — sonst
wäre die Auswertung keine reine Funktion, und ein Projekt ließe sich nicht
gegen eine geänderte Quelle neu rechnen. Einzuhalten ist
`.claude/rules/dateiformat.md` („Eingangsstufe“, „Formate“) mit `kern.md`;
Anlässe und Zahlen: `konzepte/begruendungen/karte-app-core-ingest.md`.

## Die Karte

| Datei | Rolle |
|---|---|
| `loader.py` | Die sechs Schritte (`normalise`); `read_model` liest eine Datei aus dem Speicher als einen Körper (3MF verschweißt), `READABLE_SUFFIXES` ist **die** Liste dessen, was sich öffnen lässt; GLTF-Begleitdateien aus demselben Ordner werden eingebettet, Verweise hinaus bleiben gesperrt; gleich benannte ZIP-Einträge prüft `check_unpacked` |
| `threemf.py` | 3MF **lesen** — Objekte, Farbgruppen, Einheit, Baugruppe mit Production-Erweiterung (§17.1, §20); `_reading_trees` hält die eingefrorene GC-Generation bis zum Ende des letzten parallelen Lesers. Die Konstanten des Containers stehen hier, `export/threemf.py` holt sie, auch das Plattenraster der Orca-Familie (`plate_origin`), mit dem `_plate_layout` eine Datei mit mehreren Platten auf ihre Platten legt — nur mit dem Ladeparameter `plates`, den der Plan für neue 3MF setzt |
| `ops.py` | Die `load`-Operation |
| `step_ops.py` | `load_step`: eine STEP-Baugruppe als unabhängige exakte Körper mit Weltlage, Namen und Filamentslots aus den Flächenfarben; liest mit `brep.step` und wohnt hier, weil nur `ingest → brep` erlaubt ist |
| `plan.py` | Welche Operation eine Datei einliest, für Fenster und Kommandozeile: freie Namen (`names_in_use`, `copy_name`), `is_only_imported` (trägt ein Dokument nur Eingelesenes?), STEP als Baugruppe (`BodyChoice`, `with_selection`), gemeinsames Aufsetzen (`imported_group`, `imported_group_for_bed`) |
| `fetch.py` | Eine Modelldatei aus dem Netz (§16.3, §32), immer über `_open_download` und die gemeinsame HTTP-Grenze; eine Adresse von Printables, Thingiverse, MakerWorld, Cults3D, MyMiniFactory oder Thangs ohne Dateiendung ist eine Seite und wird ohne Netzzugriff mit dem Weg über deren Herunterladen-Knopf beantwortet (`model_page_host`) |
| `archive.py` | Ein ZIP **vor** dem Einbetten auflösen: nur das Modell kommt ins Projekt, bei mehreren wird gefragt, Grenzen wie beim 3MF, Pfadtricks übergangen, GLTF-Begleitdateien aus demselben Archiv. `IMPORT_SUFFIXES` gilt Dateidialog, Ablage, Netz und Kommandozeile, `plan.MODEL_SUFFIXES` den Operationen |
| `outline.py` | SVG/DXF-Profile mit Innenringen lesen, prüfen, auswählen, extrudieren; DXF liest trimesh |
| `svg_drawing.py` | SVG-Elemente über `xml.etree` zu `Path2D`-Argumenten, ohne lxml: Transformationen nach SVG 1.1 (auch `rotate` in Grad, `skewX`/`skewY`), Ellipsen, abgerundete Rechtecke und Bögen unter verzerrender Abbildung als Punktfolge in `MAX_FACET_SAG`, `use` mit Schleifen- und Mengengrenze; nicht Gezeichnetes (`defs`, `clipPath`, `display:none` …) fehlt |

## Was die Stufe entscheidet

- **Druckvorprüfung einer 3MF**: `read_objects(printable_only=True)` lässt
  Build-Instanzen mit `printable="0"` oder `"false"` aus. Der normale Import
  behält diese editierbaren Teile; die Filterung gilt nur dem Druckauftrag.

- **Einheiten**: STL trägt keine; erkannt wird aus der Größe, bei
  Mehrdeutigkeit **gefragt** (`ctx.ask`, Regel 21). Mehrdeutig ist auch eine
  einzige Lesart unter 300 mm, solange eine zweite innerhalb `plausible_reach`
  liegt — nur Millimeter entscheiden dann allein (`detect_unit`). GLB/GLTF: Meter sind eine
  Vorschrift des Formats, keine Aussage der Datei (`_a_format_convention`) —
  unplausibel (`PLAUSIBLE_MIN_MM` bis `plausible_reach`) fragt `_unit_for`
  mit Meter zuerst. `load` dreht die schon angewandten Knoten von Y-oben nach
  Z-oben; `legacy_raw` erhält alte Quellen, eine erzeugte GLB
  (`generate.into_project`) speichert `gltf` mit `mm`, die Größe bleibt
  eigener Schritt: `fit_to_size` auf die Arbeitsgröße vor der Reparatur, ein
  zweiter mit `free_spot` dahinter setzt Kundenmaß und Lage (RM-676).
- **Offene Stellen werden geschlossen** (Regel: `dateiformat.md`): `normalise`
  ruft `geom.repair.repair` ohne die schon gefahrenen Schritte, sobald das
  verschweißte Netz nicht dicht ist. Der Ladeschritt trägt `mend` (*Offene
  Stellen schließen*) und `wide_holes` (*Große Öffnungen schließen*, hängt an
  `mend`); ob die Teile ineinanderstecken, fragt `_count_components` über
  `geom.repair.parts_that_cross`.
- **Außen fragt der Import wie die Reparatur**: Schritt 4 macht die Wicklung
  einheitlich (`wind_consistently`) und richtet jede freie Schale nach außen
  (`turn_shells_outward`); eine Schale ganz in einer anderen meldet
  `repair.part_inside` mit Ort — außer Schritt 4b hat es schon gesagt. 4b
  folgt *Außenseiten angleichen* und dem Abbruch (`normalise(cancelled=)`);
  Befundorte wandern beim Aufsetzen mit, auch in Baugruppen
  (`moved_findings`). Als verschweißt zählt nur, was zusammengelegt wurde
  (`used_vertex_count`); verschweißt wird über `geom.repair.weld` — die
  Regeln dazu stehen in `dateiformat.md` („Eingangsstufe“).
- **Dieselbe Schale zweimal** (`loader._without_doubled_shell`): An einem
  dichten Netz aus mehr als einem Teil — gezählt nach Eckennummern
  (`_index_parts`; `face_components` verbindet auch bloß Anliegendes) — wird
  eine Kopie über alles verschweißt; bleibt von Deckungsgleichem das erste
  und ist das Netz dicht, war es eine Kopie (`ingest.doubled_shell_removed`).
  Sonst bleibt der Eingang, wie er ist.
- **Dichtheit wird einmal gefragt**, wenn die Antwort gebraucht wird: am
  verschweißten Netz über `repair.is_closed` (die Kantenzählung
  `mesh.edge_table` bleibt für Reparatur und Teilezahl liegen;
  `tests/test_ingest_figures.py` zählt). **Dichtheit und Umlaufsinn reisen als
  Paar**: `normalise` bewahrt beide vor Aufsetzen oder Zentrieren und legt sie
  gemeinsam zurück.
- **`loader._too_fine` spricht nur über die Grenze der Analysekarten**
  (`ingest.very_large`, *Dreiecke verringern*). Ob die Erkennung ausgelassen
  wurde, meldet `perceive.too_large` am Körper; die Frage gehört in
  `scene.evaluate`, und der Loader lädt unabhängig davon unverändert.
- **3MF und STEP sind Baugruppen.** STEP liest der Plan über
  `brep.step.read_assembly`, schreibt die Kennungen in `load_step.bodies` und
  legt sie als `ImportPlan.choices` daneben; die Zahl der Ausgänge steht vor
  der Operation fest (§11). Geht die Baugruppe nicht auf, wählt der Plan `*`.
- **Die Lage schreibt der Plan in den Ladeschritt** (§17.1, Schritt 6;
  `plan._placement`): das erste Modell `place_on_bed` und `centre`, jedes
  weitere `place_on_bed` und `free_spot`, ohne Angabe nichts.
  `ops._to_a_free_spot` legt alle Körper der Datei als Block an die erste
  freie Stelle (`geom.prepare.placed_at_free_spot`, gelesen aus `ctx.scene`)
  und gibt Mitte und Platte als Antwort zurück (`spot_*`, §15.7); danach liest
  der Schritt die Szene nicht mehr. Eine Datei mit mehreren Platten rückt
  hinter die letzte belegte, auch über zwölf. Einzelne weitere Modelle nutzen
  zuerst passende freie Stellen und Lücken. `load_step` fragt denselben Helfer. Netz- und
  STEP-Import reichen ihre Filamente vor der Platzierung weiter; gespeicherte
  `spot_*`-Antworten haben Vorrang vor später geänderten Düsen oder Filamenten.
- **Native 3MF-Farben** — Werkzeugpaletten (Orca/Bambu-Metadaten,
  Prusa-Konfiguration), Objekt- und Part-Werkzeuge, bemalte Dreiecke — werden
  Materialslots; Prusa-Volumen behalten ihre Dreiecksbereiche.
  **Teilflächenbemalung wird gelesen, nicht vergröbert**: `_decode_paint`
  liest `TriangleSelector::serialize`, `_refine` teilt wie der Slicer
  (Mittelpunkte über beide Seiten einer Kante, T-Stöße geschlossen). Was sich
  nicht lesen lässt, hält den Import nicht an (Entscheidung Robert): einfarbig,
  mit `ingest.colours_dropped` je Körper bzw. `ingest.palette_dropped`; der Rat
  steht im Satz, nicht in `suggestions` — es gibt keine Handlung mit Handler.
  Tiefer als `MAX_PAINT_DEPTH` ist ein Befund, kein `RecursionError`.
- **Was der Slicer außer druckbaren Teilen ins Objekt legt**: `HELPER_KINDS`
  (Modifikator, Stützblocker, -verstärker) werden übersprungen
  (`ingest.helper_skipped`), `negative_part` von jedem druckbaren Teil
  abgezogen (`ingest.negative_carved`, Rückfallkette, Stufe am Befund und als
  `Part.solver`; `load` meldet die tiefste, §17.2), eine unbekannte Art ist ein
  Körper mit `ingest.unknown_part_kind`. Zähl- und Leseweg fragen dasselbe
  `_is_body` (§11). Das gilt für Bambu, Orca und Elegoo (`subtype`);
  PrusaSlicer führt dieselben Arten als `volume` (`PRUSA_VOLUME_KINDS`,
  `_helpers_left_out` nimmt ihre Dreiecke heraus und nummeriert neu), eine
  unbekannte Bereichsart kommt als Material mit `ingest.foreign_volume`. Bleibt
  kein druckbarer Körper, ist das die Absage `no_printable_part`, keine leere
  Liste. `model_settings.config` wird ohne Namensräume gelesen
  (`_slicer_config`).
- **Wie der Körper heißt, entscheidet der Plan**: Trägt der Stapel die Datei
  schon, bekommt der neue Ladeschritt eine Nummer (`copy`, „plate_holes (2)“,
  `plan.copy_name`) — im Schritt, nicht im Namen, für **jeden** Körper der
  Datei; ein Einzelteil ohne Namen heißt nach der Datei. Gefragt wird der
  **Stapel**, nicht die Szene (§15.1); ältere „Name 2“ zählen mit.
- **Gemeinsames Aufsetzen** (`plan.imported_group`) gilt nur den lebenden
  Ausgaben eines unveränderten mehrteiligen Imports, ohne Auswahl und frühere
  Objekte, und ist die eigene Operation `place_group_on_bed`.
  `imported_group_for_bed` prüft die aktuellen Grenzen: Liegt die Unterseite
  innerhalb `EPS_DISPLAY` auf dem Bett, bleibt die Einzelhandlung.
- **Herkunft** wird vermerkt (`scene/foreign.py`, §32); nichts aus einer
  geöffneten Datei wird ausgeführt (Regel 13).

## Grenzen

- **Die Konturauswahl ist ein Operationswert**: `read_profiles` liefert
  geometrisch stabile Kennungen samt Ringen, `load_outline.contours` speichert
  sie als JSON-Liste; leer oder unbekannt hält an, nur der historische leere
  Text übernimmt alle Profile. `profile_reason` prüft für die Vorschau
  denselben Weg; unbrauchbare Profile bleiben mit Grund sichtbar.
- **Vorschau und Operation teilen `extrude_profiles`**: Die Zielbreite
  skaliert die gewählten Profile zusammen in X/Y, die Höhe bleibt, Löcher
  bleiben beim Profil.
- **Modelldownloads laufen immer über `fetch._open_download`**: geprüfte
  Weiterleitungen, Gesamtfrist samt Headern, begrenzte Leseantwort; Tests
  ersetzen nur den Transport, einen Umgehungsparameter gibt es nicht.
