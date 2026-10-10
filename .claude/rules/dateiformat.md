---
description: "Projektdatei, Import, Export und Slicer-Übergabe — Migration ist Pflicht, was nicht in die Datei gehört, die Eingangsstufe, was welcher Slicer bekommt und das Herstellerprofil"
paths:
  - "app/core/ingest/**/*.py"
  - "app/core/export/**/*.py"
  - "app/core/scene/project*.py"
  - "app/core/scene/serialise.py"
  - "app/core/geom/repair.py"
---

# Regeln für Projektdatei, Import und Export

Das Warum steht unter denselben Überschriften in
`konzepte/begruendungen/regel-dateiformat.md`.

## Migration ist Pflicht, nicht Kür

Eine Projektdatei ist Fehlerbericht und Archiv. Jede Formatänderung folgt der
Checkliste „Dateiformat ändern" in `AGENTS.md`; der Test belegt, dass die
alte Datei **korrekt** rechnet, nicht nur fehlerfrei öffnet.

**Ändert sich, was ein gespeicherter Wert meint, rechnet die Migration ihn
um, statt es zu melden** — braucht es die Auswertung, über einen Haken im
Schritt (`measured_frame`, Format 39).

## Was nicht in die Datei gehört

Keine absoluten Pfade, kein ausführbarer Code, keine eigenen Bausteine — sie
werden beim Namen genannt; fehlt einer, hält die Auswertung an und sagt
welcher (§24.5, §32).

- **Eigene Drucker und Materialien reisen als Daten** (Format 30,
  `Document.carried_profiles`): Name, Bauraum, Düse, Verfahren, Schichtwerte,
  nur für nicht mitgelieferte Kennungen. Der zweite Rechner rechnet damit und
  bietet die Übernahme an; einen unbekannten Drucker ersetzt er durch den
  allgemeinen desselben Verfahrens und sagt es. Passungen aus *An Ebene teilen* und
  *Deckel* stehen auf `auto:` und folgen dem Material ihrer Körper (Migration
  29 → 30, `material_fits_v29.p3d`).
- **Ein ausgeschalteter Schritt steht in der Datei, mit dem, was er traf**
  (Format 32, `Operation.suppressed`): `chosen` (gewählt oder mitruhend),
  `expects` (Schlüssel, Merkmal, Art, Erzeuger, Abdruck jedes Verweises),
  `fits` (mitruhende Passungen); Umbau-Transaktionen tragen `revision`
  (`insert`, `move`, `suppress`, `reactivate`). 31 → 32 schreibt nichts um;
  `project._validate_suppression_schema` weist Beschädigtes und unbekannte
  Umbauarten ab.
- **Gleich heißt inhaltsgleich, nicht bytegleich**: Verglichen wird
  `project.content_digest`, nie der Dateihash (Deflate-Bytes unterscheiden
  sich je Plattform, der ZIP-Kopf nennt kein System: `CONTAINER_SYSTEM`).
  Eingecheckte Beispiel- und Belegdateien werden nicht neu geschrieben — ihr
  Hash ist ihr Beleg.
- **Was zum Teil gehört, steht im Dokument, was zum Rechner gehört, in den
  Einstellungen**: Exportformat und Namensschema im Dokument
  (`Document.export_format`, `export_scheme`, Format 23), der Ordner in
  `UiSettings.export_dirs` je Projektpfad (§29: „je Projekt", nicht „in der
  Projektdatei"). Die Sichtflächensperre (`Document.protected`, Format 24)
  hält je Körper **Merkmalkennungen**, keine Dreiecke oder Punkte (nur
  Kennungen überleben eine Auswertung, §21); die Punktwolke rechnet
  `split.protected_patches` beim Start. Kein Verlaufsschritt; ein Rezept trägt
  keine Sperren (`part_file` weist sie ab).

## Transaktionstitel

Ein Titel aus dem Code trägt `title_translatable` (seit Format 6): `title` ist
die Message-ID, aufgelöst erst bei der Anzeige; ohne Markierung ist er wörtlich
(Nutzernamen werden nie übersetzt). Transaktionstitel über `_()`, nie `tr()` —
sonst friert die Sprache des Speicherzeitpunkts ein. Auch ein zusammengesetzter
Titel ist ein `_()` mit Platzhalter (`session._parameter_title`:
`_("Parameter {name}", name=title or name)`, der Titel selbst übersetzbar);
wörtlich bleibt nur, was der Nutzer benannt hat. Die Titel der
Beispiel-Bauer sammelt `EXTRA_SOURCES` in `app/i18n/extract.py` ein.

## Ein Platzhalterwert kann selbst übersetzbar sein

Ein Wert in einem `TranslatableText` kann selbst einer sein
(`perceive.actions._no_way`). Werte gehen deshalb durch
`translatable_values_to_data`/`translatable_values_from_data`
(`scene/serialise.py`), nie durch ein rohes `dict(text.values)` — an allen vier
Ablagestellen (Parametertitel, Transaktionstitel, Befundmeldung, Beschriftung
eines Auswegs) und in `cache._name_to_data`. **Abgelegt wird die Struktur,
nicht der Satz**: nicht `str(value)` (friert die Sprache ein), nicht
`source_text(value)` (Deutsch im fremden Satz); Zahlen bleiben Zahlen
(`{free:.1f}`). `TranslatableText.translate(sprache)` und `source_text()`
reichen die Sprache an ihre Werte weiter, nie über `__str__`.

## Eingangsstufe

Jede Datei durchläuft dieselbe Kette (Ergebnis in `sources`): Einheit
bestimmen, bei Verdacht **fragen**; verschweißen; entartete Dreiecke
entfernen; Normalen vereinheitlichen; Komponenten zählen, Kleinstteile
**melden**, nie still löschen; Lage ermitteln, Aufsetzen anbieten, nicht
erzwingen. Die Kette ist die Op `load` — ihre Parameter bleiben im Stapel
sichtbar und änderbar.

- **Die Lage steht im Ladeschritt** (§17.1): Die freie Stelle eines weiteren
  Modells wird einmal gerechnet und als Antwort festgehalten (`free_spot`,
  `spot_*`, Format 38, Entscheidung Robert).

- **Was zum Lesen eines Formats gehört, ist kein Befund**: STL verschweißt
  schweigend (`normalise(weld_is_reading=True)`, von `import_model` an der
  Endung gesetzt); OBJ, PLY und 3MF behalten den Befund. „Das Modell besteht
  aus mehreren Teilen." trägt die Handlung `SPLIT_BODIES`
  (`panels.FINDING_ACTIONS`) — Angebot, keine Ausführung.
- **Eine Kopie derselben Schale ist ein Duplikat, keine Baugruppe**: unter
  `remove_degenerate` abgeräumt, mit Befund, nur wenn das Netz danach
  geschlossen ist; flächig berührende Körper bleiben zwei.
- **Verschweißen schließt Ränder, es verbindet keine Blätter**: Import und
  Reparatur fragen `geom.repair.weld` (nur offene oder verzweigte Ränder und
  Kanten unter `EPS_GEOM`, getrennt nach Flächenblatt, nie zum Schlechteren);
  heile Form bleibt, auch eine Fase schmaler als die Schweißtoleranz. Jede
  weitere Stelle, die ein eingelesenes oder beschädigtes Netz verschweißt,
  nimmt dieselbe Funktion; `Trimesh.merge_vertices` bleibt nur, wo ein
  Erzeuger eigene Stücke fügt (Drehkörper, Werkzeuge), und in
  `boolean._tidied`.
- **Offenes wird beim Import geschlossen** (Entscheidung Robert):
  `geom.repair.repair` mit den Schritten der Operation, **nur** wenn es etwas
  zu tun gibt — ein geschlossener Körper ohne Messung, ein unverschweißtes
  Netz gar nicht (`weld=False`: nicht anfassen). Was geschlossen wurde, steht
  mit Zahl im Bericht (`repair.holes_filled`, `repair.branching_resolved`),
  eine Öffnung über `FILL_LOOP_SHARE` der Oberfläche zusätzlich als Warnung
  `repair.wide_hole_filled` (Test: `broken_open.stl`). Danach wird die
  Antwort auf „ist es dicht" im Netzcache neu gesetzt. Die Reparatur bleibt
  eine Operation: dieselben Befunde, Strg+Z am Ladeschritt.

Grenzen des Schließens (Entscheidung Robert):

- **Große Öffnung**: geschlossen, mit Ort, *Stelle zeigen* und *Offen lassen*.
  *Offen lassen* setzt am Ladeschritt nur `wide_holes=False` (*Große Öffnungen
  schließen*) — kleine Löcher, Nähte, überzählige Flächen gehen weiter zu —
  und meldet `repair.wide_hole_kept` mit *Dicke geben*. Der Schalter gilt
  allen Körpern der Datei; der Ort wandert beim Aufsetzen mit.
- **Lose offene Splitter** unter `SMALL_COMPONENT_SHARE` des größten Teils
  gehen mit `repair.splinters_removed`; *Offene Stellen schließen* aus lässt
  sie. Geschlossene Kleinstteile nur melden (`ingest.small_components`,
  §17.1 Schritt 5).
- **Ineinandersteckende Teile**: `ingest.multiple_components` fragt am
  geschlossenen Netz `repair.parts_that_cross` (Paare im Überlapp der
  Hüllquader, frühes Ende, eigenes Budget) und bietet *Überschneidungen
  auflösen* vor *In Einzelteile aufteilen*; Flächenberührung und Spiel wie
  beim Kettenglied zählen nicht.
- **Was ausblieb, ist keine Zeile**: Ein Verschweißen oder Entfernen, das das
  Netz aufgerissen hätte, geht ins Protokoll, nicht in den Bericht.
- **Eine Fläche ohne Dicke bleibt offen** (`repair.no_thickness`, *Dicke
  geben*).
- **Unentscheidbares wird gemeldet, nicht gerichtet**: Eine Schale ganz in
  einer anderen, nach außen gerichtet, ist `repair.part_inside` mit Ort, bei
  Import und Reparatur gleich.

Weitere Eingänge:

- **GLB/GLTF**: Neue Importe speichern am Ladeschritt `coordinates="gltf"`
  (Meter, Y oben); bestehende Projekte samt Undo-Fassungen, eingebetteten
  Generatorquellen und Rezeptdokumenten behalten `legacy_raw`. Eine erzeugte
  GLB speichert `gltf` mit `mm`; Maß per `fit_to_size`, alte Ketten bleiben.
  Eine ausdrückliche Einheit hat Vorrang; Rohleser und Zielgrößenskalierung
  behalten ihren Vertrag. **Unplausible Meter werden nicht geglaubt** (unter
  10 mm, über der doppelten Bauraumdiagonale): Einheitenfrage mit Meter zuerst
  (Regel 21). Eine 3MF-Einheit gilt ohne Frage.
- **ZIP-Dubletten nur bei bytegleichem Inhalt**: Alle Einträge zählen vorher zu
  Archivanzahl, Entpackgröße und Kompressionsverhältnis; gleiche CRC ist kein
  Beweis; Vergleich in begrenzten Blöcken; fehlerhafte oder widersprüchliche
  Kopien bleiben abgewiesen; keine Quelle wird dafür umgeschrieben.
- **Aus dem Netz derselbe Weg** (`core/ingest/fetch.py`): gemeinsame Stelle
  `Session.import_payload`, `import_model` liest nur die Platte. Herkunft in
  `Source.origin` (§16.3), nur `http`/`https`, Größengrenze **während** des
  Lesens (`Content-Length` ist eine Behauptung); HTML ist eine Modellseite —
  gemeldet, nicht ausgewertet.

## Formate

3MF ist eine **Baugruppe** (Objekte, Stückzahlen, Materialgruppen je Dreieck,
Transformationen), nie ein Netz am Stück; STL kennt keine Einheit und keine
Farbe. Dreieckszahl und Dateigröße sind beim Import gedeckelt, mit Meldung
statt Speicherüberlauf.

**Ein 3MF-Modell wird nie am Stück geparst**: den Baum über
`threemf._parse_model` innerhalb von `_reading_trees` — stückweise, je Stück
eingefroren (`gc.freeze`), am Ende in Scheiben freigegeben und aufgetaut;
nichts bleibt eingefroren (`gc.get_freeze_count() == 0`, Test). Wer nur
zählt, baut keine Geometrie (`_StructureOnly`). Ein Stück, ein Zahlenblock
und ein Freigabeblock halten den GIL je höchstens wenige Millisekunden
(`XML_CHUNK`, `NUMBER_BLOCK`). Objekte und Materialgruppen sucht
`_outside_meshes`, nie `findall(".//…")` über das Modell (Test).

**STEP ist eine Baugruppe** (Format 33): je Komponenteninstanz ein exakter
Körper mit Weltlage, Namen und Flächenfarben über XCAF
(`brep.step.read_assembly`, dort Vorrang von Name und Farbe).

- Die Quelle bleibt die STEP-Datei; im Dokument stehen Ladeschritt und
  Kennungen (`load_step.bodies`, JSON-Liste von Instanzpfaden), keine Formen,
  Farben oder Pfade (Regeln 12, 13). Fehlt eine Kennung, hält es an und sagt,
  wo man neu wählt.
- Ohne `bodies` liest der Schritt einen Körper (`step.read`); 32 → 33 schreibt
  nichts um (`step_assembly_v32.p3d`). `*` ist der gemeldete Rückfall, wenn
  XCAF scheitert — ein Körper, der Bericht sagt, dass Namen und Farben fehlen.
- Farben werden Filamentslots nur ab zwei Farben (wie bei 3MF); Flächen ohne
  Farbe am neutralen Slot null; mehr als acht je Körper sind ein Befund.
- Die Auswahl ändert sich nur, solange niemand auf ihr baut:
  `History.change_params` weist eine andere Zahl der Ausgänge
  (`produces_from`) **und** einen Austausch gleicher Zahl ab, sobald ein
  späterer Schritt die Körper benutzt (`members_in_use`).
- Hinaus: `step.write_bodies` — Name wörtlich, Filamentfarben je Fläche,
  Umlaute nach ISO 10303-21; die Rundreise ergibt dieselben Körper, Namen und
  Farben.

## Ein Druckerprofil wird gelesen, wie der Slicer es liest

Orca: je vier Punkte von `bed_exclude_area` ein Hüllrechteck
(`build_area.exclusion_boxes`, für Profil, Gegenprobe und Turm). PrusaSlicer
übergeht den Schlüssel; Punkte lesen beide wie ein `istringstream`
(`_stream_point`). Cura: konvexe Hülle, Form `elliptic` oder Rechteck, nur
Konstanten in Formelgestalt (`_cura_literal`).

## Was welcher Slicer bekommt

- **Die Schrägnaht braucht Art und Länge** (`shell.scarf_seam`). Geschrieben
  werden nur Außenwand und glatte Schleifen mit `slicer_keys.SCARF_LENGTH`;
  Bambu Studio bekommt dazu `override_filament_scarf_seam_setting`, sonst
  sticht die Schrägnaht seines Filaments. Cura: `scarf_joint_seam_length` je
  Netz. Die Grundlage liest „an“ nur mit einer Länge über null.
- **Stützdichte bei Prusa und Orca:** Lücke `s/d−s`, zurück `s/(Lücke+s)`;
  `s` aus der wirksamen Stützbahn. Ohne positive Dichte aktive Übergabe anhalten.
- **Eine Stützsperre gehört zu ihrem Objekt, und jede Familie schreibt sie
  anders** (`slicer_keys.helpers_as_parts`): Orca-Familie als eigenes Teil
  (`model_settings.config` nennt die zweite Komponente `support_blocker`),
  PrusaSlicer als Bereich (Dreiecke hinter denen des Körpers, `SupportBlocker`
  in der Beilage, Modell mit `slic3rpe:Version3mf`), CuraEngine als eigenes
  Netz mit `anti_overhang_mesh=true` (`slicer_keys.takes_mesh_settings`),
  Curas Fenster als Komponente neben ihrem Körper mit
  `cura:anti_overhang_mesh`. Jede Familie druckt die fremde Schreibweise als
  Kunststoff — geprüft wird an der **Modellbahn** mit und ohne Sperre, nicht
  an der Stütze. Geschrieben nur in die direkte Übergabe, nie in eine
  gespeicherte 3MF.
- **CuraEngine bekommt kein 3MF, Curas Fenster schon** (`cura`): Für die
  Kommandozeile gibt `write_assembly` ein STL aller Teile der Platte, daneben
  je Teil ein Netz und eine Netzliste (`-s` nach `-l` gilt nur diesem Netz).
  Eine Netzliste, die nicht hält (fremder Pfad, fehlende Datei, Wert mit
  Umbruch), hält die Übergabe an, statt still ohne Sperre zu rechnen. Das
  Fenster (`for_window`) bekommt dieselben Netze mit denselben Werten als 3MF
  in Curas Schreibweise (`cura:<schlüssel>` am Objekt, Wahrheitswerte `True`,
  `handover.for_the_cura_window`), mittig auf dem Bett der Maschine, die in Cura
  aktiv ist (`CuraActiveMachine.bed`, ohne sie das des Druckers).
- **Mehrere Platten in eine Datei, wo der Slicer Platten kennt**
  (`knows_plates`): Orca-Familie mit je einem `plate`-Block, Teile
  plattenweise im Raster — `ceil(sqrt(n))` Spalten, Zeilen nach unten, ein
  Fünftel Bett Luft (`plate_origin`, `SLICER_PLATE_GAP`),
  Blöcke nach Rang; *Im Slicer öffnen* gibt eine Datei. PrusaSlicer und Cura
  bekommen je Platte eine Datei, *Slicen* je Platte eine Druckdatei. Solidons Anordnung reist nur mit, wenn sie auf
  **jeder** gewählten Platte hält (`arrangement_holds`).
- **Bettkoordinaten für jede Familie** (`wants_bed_coordinates`): Teile um
  `build_area.machine_shift` verschoben **und** ein Bett um denselben
  Nullpunkt (`PrinterProfile.bed_origin`, sonst die Ecke), in derselben
  Übergabe — beides fragt dasselbe Prädikat. Eine Cura-Definition behält
  ihren Ursprung (`CuraMachine.shift`).
- **Ohne Familie STL um den Ursprung** (`other`): nichts übersetzt; der
  Konsolenweg sagt ab, das Öffnen läuft.
- **Was nur gedreht passt, dreht Solidon**, auch für die Orca-Familie
  (`writer.prepare_slicer_meshes`).
- **Ein exakter Körper geht so fein hinaus, wie der Drucker es braucht**:
  `writer.mesh_for_export` vernetzt neu, wenn `Profile.export_deflection` (ein
  Achtel des kleinsten Details, gedeckelt von der Zahl des Kerns) feiner
  verlangt als der Körper hat; Anzeige und Erkennung bleiben bei seiner
  Vernetzung. `export.tessellated` einmal je Export, nie je Körper.

## Auf dem Herstellerprofil wird nur die Abweichung geschrieben

Entscheidung Robert (Bauplan §29): Gedruckt wird mit dem Profil des
Herstellers, Solidon schreibt darüber nur die Abweichung.

- **Nur `chosen`, `accepted`, Gemessenes und Stufenwerte gehen über das
  Herstellerprofil.** Jeder Übergabepfad fragt `manufacturer.written_paths`;
  Werte ohne Herkunft kommen aus der Grundlage.
- **Die Stufe wählt den Herstellerprozess** (`manufacturer.for_stage`,
  Zuordnung `slicer_profiles.stage_process`): Jede Stelle, die eine
  Einrichtung aus `remembered_setup` baut, wendet sie an, und der Druckdialog
  zeigt den Stufenprozess im Prozessfeld. `UiSettings.slicer_base_process`
  trägt den Standardprozess der Maschine, solange das Feld der Stufe folgt,
  sonst die eigene Wahl — nie den abgeleiteten Stufenprozess, denn die Stufe
  gehört zum Projekt. Nur wo der Hersteller keinen nennt (Creality Print heißt
  jeden Prozess „Standard"), liegen `STAGE_PATHS` über dem Standardprozess;
  ein selbst gewählter Prozess ist die Stufe.
- **Was die Maschine setzt, bleibt beim Hersteller**: Curas Lüfterkurve unten
  und Schwelle (`manufacturer.cura_fan_curve`); Fuß- und Lochausgleich nur
  gewählt oder übernommen (`slicer_keys.MAKER_OWNED`), der Rat je Teil gilt
  als übernommen (`handover._applied`), in der Orca-Familie mit Brim-Abstand
  (`object_keys`).
- **Was ohne Partner nicht wirkt, geht mit ihm** (`handover.COUPLED_PATHS`):
  Haftungsart mit den Maßen aller Arten, Lüfter-Obergrenze mit dem unteren
  Ende; eine gewählte Haftungsart bringt ihr Maß mit, wenn es null ist
  (`print_settings._with_a_measure`). Neue Paare dort eintragen.
- **`with_path` setzt keine Herkunft**: Dialog `with_choice`, übernommener
  Vorschlag `with_accepted` (`advise.apply`), Zurücksetzen `without_choice`;
  eine Rücklesung aus einem Profil ist keine Wahl.
- **Das Gemessene gilt auf dem Raster seiner Probe**
  (`manufacturer.measured_on`): Wirksame Einstellungen entstehen über
  `manufacturer.effective`, im Druckdialog über sein Attribut `settings`. Eine
  andere Schichthöhe oder Bahnbreite setzt den gemessenen Überhangwinkel auf
  die Grundlage ohne Messung zurück (`Foundation.unmeasured`).
- **Was aus dem Körper folgt, steht am Teil** (`handover.split_for_parts`):
  Ein übernommener Pfad aus `advise.PART_PATHS` ohne plattenweiten Grund
  (`advise.plate_paths`) fällt auf der Platte auf die Grundlage zurück, und
  der Rat je Körper schreibt ihn als Objektwert (`writer._part_values`).
  Export und Dialog fragen diesen Rat an einer Stelle (`writer.part_advice`,
  je Spule `handover.slot_processes`), bis zum Fixpunkt mit den Übernahmen,
  die das Teil verlangt (`PartSplit.accepted_per_part`). CuraEngine nimmt nur
  `CURA_PER_MESH` je Netz: Die Platte behält die Übernahme, ein Teil ohne
  Bedarf bekommt je Netz die Grundlage zurück (`PartSplit.revert`). Was ein
  Slicer nicht je Teil annimmt, bleibt plattenweit; gefragt wird ohne die
  Übernahme (`PartSplit.base`), und wer sie nur mitbekommt, erfährt es
  (`export.part_setting_unavailable`). `write_assembly` und `slice_model`
  fragen dieselbe Trennung; Haftungsprüfung und Stützsperre fragen den Wert,
  den das Teil bekommt. Eine eigene Wahl gilt der Platte, auch unter einem
  Vorschlag je Teil (`PrintSettings.plate_choices`). Ein Objektwert
  trägt die Pfade seines Rats und deren Partner (`COUPLED_PATHS`), nie die
  ganze Gruppe (`handover.object_keys`). **Ein übernommener Vorschlag
  verschwindet nie still**: Verlangt ihn kein Teil, geht er als Objektwert an
  jedes (`writer._unserved`, `export.part_setting_all`); die Platte bleibt,
  damit `slice_model` dieselbe rechnet. „Kein Teil“ heißt keines des Auftrags
  (`job`: im Druckdialog die gewählten Platten, beim Dateiexport alle Körper).
- **Die Druckplatte ist eine Angabe, keine Vermutung**: die im Druckdialog
  gewählte (`SlicerSetup.plate`), sonst die Standardplatte der Maschine oder ihres
  Modells, sonst die des Programms (`manufacturer.PROGRAM_PLATE`). Nur ohne
  Plattenwahl (`support_multi_bed_types` fehlt) gilt die eine Temperatur
  `hot_plate_temp` (`manufacturer.SINGLE_PLATE`); mit Wahl und ohne
  Standardplatte keine geratene, sondern `slicer.plate_unknown`. Die
  Betttemperatur der Grundlage kommt nur aus dem Schlüssel der aufliegenden
  Platte; 0 °C beim Hersteller sperrt sie für das Filament — die Grundlage
  liest dort nichts, `slicer.plate_refuses_filament` führt in die
  Druckeinstellungen. Eine eigene Betttemperatur geht trotzdem dorthin.
- **Gedruckt wird, was der Slicer liest**: die Düsenart-Fassung der
  Maschinendüse, ein eigener Wert in jeder (`slicer_keys.NOZZLE_KIND_KEYS`);
  wo gestützt wird, keine Baumspitze unter der Stützbahn
  (`handover.organic_tree_fitted`); passt der genannte Standardprozess nicht,
  der seiner Schichthöhe, ohne Prozess `slicer.process_missing`; was die
  Konsole ablehnt, als Programmvorgabe (`slicer_keys.CONSOLE_LIMITS`); ein
  Stützabstand zwischen zwei Schichten mit eigener Stützschichthöhe, außer
  unter organischen Bäumen (`handover.support_gaps_by_style`).
- **Was sich nicht übersetzen lässt, wird nicht umgedeutet**
  (`Foundation.foreign`): `crosshatch` bleibt ungeschrieben, der Dialog zeigt
  „Hersteller: crosshatch".
- **Ein mitbedienter Schlüssel wird nie schneller als beim Hersteller**
  (`handover._followers_not_faster`): Innenwand schreibt auch die
  Lückenfüllung, Füllung auch die innere Vollfüllung (Solidons eigener Satz
  braucht dafür Werte); über dem Herstellerprozess dürfen sie langsamer
  werden, nicht schneller. Eine Rolle mit eigenem Herstellertempo
  (`_PRUSA_ROLES`, `_ORCA_ROLES`) folgt einem gebremsten Leittempo.
- **Ein übernommener Vorschlag bremst, er beschleunigt nicht**: Tempi, die nur
  ein Vorschlag setzt (`handover._suggested_speed_keys`), bleiben über dem
  Herstellerprozess nie schneller als dort; eine eigene Wahl darf beides.
- **Ein Vorschlag, der beim Slicer nichts ändert, wird nicht angeboten**:
  Tempodeckel nach Volumenstrom (`advise.limits_flow`) fallen weg, wo der
  Slicer selbst deckelt (`slicer_keys.caps_volumetric_speed`), und bleiben bei
  Cura.
- **PrusaSlicer bekommt die ganze Kette seines Bündels in einer Datei**:
  Drucker, Prozess und Filament aus seinem Bestand (`manufacturer.prusa_chain`),
  aufgelöst und ohne die Profilverwaltungsschlüssel (`PRUSA_MANAGING_KEYS`),
  vollständig in `solidon.ini` und der 3MF-Beilage (`handover.prusa_values`),
  darüber nur die Abweichung. Dazu technisch nötig: die drei `*_settings_id`,
  `support_material_auto = 1` bei eingeschalteten Stützen, der Rückzug auch
  als `filament_retract_*`, im Konsolenlauf `binary_gcode = 0` (die 3MF
  bleibt binär). Ohne Drucker des Bündels bleibt
  Solidons voller Satz samt Maschine, `filament_type` der ersten Spule und
  Zeitschätzung (`_prusa_time_estimate`, `marlin`, nie `ignore`), und
  `slicer.printer_unknown` sagt, dass Bettvermessung und Spüllinie fehlen. Was
  keine der drei Ketten nennt, liest die Grundlage aus PrusaSlicers
  eingebauten Vorgaben (`PRUSA_PROGRAM_DEFAULTS`).
- **Ein Prusa-Bündelabschnitt wird am Namen erkannt, nicht am Pfad**
  (`slicer_profiles.identity`) — Auswahlen über Profile nehmen diese
  Kennung. Den gelesenen Bestand hält `slicer_profiles._prusa_store`, geprüft
  an Größe und Zeitstempel jeder Datei.
- **Bei PrusaSlicer erst der Hersteller, dann Liste und Bedingung**
  (`slicer_profiles._prusa_fits`, wie PrusaSlicers
  `is_compatible_with_printer`): Ein Systemprofil passt nur zum Drucker
  desselben Bündels (`SlicerProfile.vendor`, der Dateistamm); Vorlagen
  (`templates_profile = 1`) und eigene Profile ohne Herstellerbasis gehen nach
  Bedingung, ein eigenes Profil gehört dem Hersteller seines Elternprofils
  (`_PrusaStore.vendor_of`).
- **Die Gegenprobe hält, was Solidon schreibt, plus eine Stichprobe der
  Grundlage** (`handover.FOUNDATION_SAMPLE`; PrusaSlicer
  `PRUSA_FOUNDATION_SAMPLE` und `PRUSA_IDENTITY`: Druckermodell, Profilname,
  Startcode). Bambu: Variante/ID je Profil (ohne Wahl Index 0, mehrdeutig:
  Tabelle); 3MF: nur Variantenschlüssel je Slot, gleiche Listenlänge zählt
  nicht. Unklare Spulen: Projektwerte; Befund zum Druckdialog.
- **Die Abnahme ist der Konfigurationsblock**: Ohne Vorschläge gleicht
  Solidons G-Code-Konfiguration der des Herstellerprofils allein, bis auf
  Namen, Objektmarken und `filament_self_index`.
- **Ältere Dateien ordnet die Migration gegen jede Auflösung ein, mit der eine
  Version schrieb** (`print_settings.legacy_choices`: heutige und 0.5.0,
  `resolve(..., legacy=True)`); wer die Auflösung ändert, prüft an einer von
  der alten Version gespeicherten Datei
  (`tests/data/projects/print_settings_v33.p3d`).

## Die drei Stufen der Übergabe

`values_for` ist die einzige Stelle, an der sie zusammenkommen, in dieser
Folge: **Zuordnung** (`as_mapping`: Tabellen aus `slicer_keys` und was sich
allein aus den Einstellungen umrechnen lässt), **Maschine** (`_machine_keys`:
Bauraum, Düse, was `CuraEngine` sonst nirgends findet), **Abgeleitetes**
(`_cura_dependants`: nur Cura, nur danach, rechnet auf beide; für Prusa und
Orca leer). Eine einzeln benutzte Stufe ist ein halber Satz. PrusaSlicer mit
einem Drucker seines Bündels bekommt `prusa_values` statt `values_for` — die
Maschine kommt aus der Kette, `_machine_keys` entfällt. Für Cura folgt die
Maschine (`_cura_machine` in `write_config`: Druckerdefinition hinter `-j`,
Start- und Endcode als eigene `-s`, die zwei Schalter für Curas
Temperaturbefehle), nicht in `values_for`.

## CuraEngine rechnet keine Formeln

In `fdmprinter.def.json` trägt jede abgeleitete Einstellung `value` und
`default_value`; CuraEngine nimmt den Vorgabewert, ein geschriebener Wert
erreicht die aus ihm gerechneten Schlüssel nicht. Die Erbkette (auch einer Druckerdefinition) löst CuraEngine
selbst auf und lädt Extruderzüge aus `machine_extruder_trains`, sofern `-d`
den Ordner `extruders` nennt (mit `os.pathsep`).

Eine neue Cura-Zuordnung prüft, was am Schlüssel hängt: Kopien in
`CURA_MIRRORED`, Faktoren in `CURA_SCALED`, Gerechnetes in `_cura_computed`
(**die Formel aus der Definition**, keine eigene Meinung), bewusst Ausgelassenes
mit Begründung in `CURA_UNTOUCHED`; `tests/test_print_settings.py` lässt
nichts dazwischen zu. **Wo Curas Werksprofile anders setzen als `fdmprinter`,
gilt das Werksprofil** — als Konstante mit Herkunft in `handover`, nie als
Meinung ohne Beleg.

## Der Startcode kommt vom Hersteller, die Platzhalter füllt Solidon

Kein eigener Startcode (Entscheidung Robert). Bei Cura kommt er aus der
Druckerdefinition (`PrinterProfile.cura_definition`); CuraEngine füllt keine
Platzhalter, deshalb `handover._filled`:

- `{name}` und `{name, n}` sind **Textersetzung** — der Wert, den Solidon
  schreibt, sonst der Vorgabewert der Kette; eine Formel der Kette füllt
  nichts.
- Eine **Rechnung** wie `{machine_depth - 5}` geht durch `app.core.expressions`
  (kein `eval`, Regel 10), nur über Zahlen, die Solidon kennt.
- **Unfüllbares hält die Übergabe an** (`_unfillable`, Regel 21): unbekannter
  Name, `{if …}`, Werte, die erst das Fenster nach dem Schneiden kennt
  (`{print_time}`).

Setzt der Startcode selbst eine Temperatur (Platzhalter auf
`material_bed_temperature…` oder eine Düsentemperatur, Kommentare
ausgenommen), stehen `material_bed_temp_prepend`/`material_print_temp_prepend`
auf `false`, wie Curas `StartSliceJob`. Ohne Definition: `fdmprinter` und der Befund
`slicer.cura_printer_unknown`, kein stiller Rückfall.

## Das Cura-Profil gehört dem Drucker, der in Cura aktiv ist

Curas Fenster nimmt Einstellungen nur als `.curaprofile`
(`handover.cura_profile_beside`) und setzt sie auf die **aktive Maschine** um.
Die Stufe kommt aus `slicer_profiles.cura_active_machine` und
`cura_quality_types(…, variant=…, material_type=…)`, nie aus `fdmprinter` für
eine Maschine mit eigenen Stufen. Passt kein eingerichteter Drucker, entsteht
**keine Datei**, sondern `handover.cura_profile_unbound`.

## Winkel zählen nicht überall gleich

`support.threshold_angle` misst **gegen die Senkrechte** (0° stützt jeden
Überhang, 90° keinen) wie Cura; PrusaSlicer und die Orca-Familie messen gegen
die **Horizontale** — für sie rechnet `_angle_from_horizontal` `90 − Wert`.

## Eine gelungene Übergabe ist noch kein vollständiger Druck

Exit 0 und eine Datei sagen nicht, dass der Auftrag darin steht: **Nach** dem
Lauf wird geprüft, was hineingehörte (`spools_left_out`). Jede neue Zusage an
den Slicer braucht ein Merkmal, das ihr Einlösen in der fertigen Datei zeigt. Gezählt werden **Flächen, nicht die Deklaration**.

## Ein Absturz ist keine Absage

`crashed()` trennt beide am Rückgabewert (POSIX: negatives Signal, hinter
Flatpak 128 + Absturzsignal; Windows: `NTSTATUS` ab `0xC0000000`) und steht
**vor** den Ausgabeprüfungen; eine Absage in `result.json` zählt vor dem
Prozess. Orca-Absagen kommen als DWORD oder Byte (`orca_refused`).

## Über Erfolg entscheidet die Druckdatei, nicht das Prozessende

Läufe der Orca-Familie bekommen `finished=handover._result_written(target)`, und `process.run_limited`
beendet den Baum `FINISHED_LINGER_SECONDS` nach dem gemeldeten Ergebnis.
Gezählt wird nur eine **neue**, lesbare `result.json` dieses Laufs. Ein
Slicer, der sein Ende sonst anzeigt, bekommt dieselbe Frage mit.

## Ein Wert gehört an einen Schlüssel, der dasselbe meint

Eine Zeile in `slicer_keys` schreibt einen Wert nur unter einen Namen, der
**dieselbe Sache** meint; zwei Enden einer Kurve sind zwei Einstellungen. Hat
der Slicer einen Gegenwert (Minimum zum Maximum, Schwelle zur Kurve, Schalter
zum Anteil), braucht Solidon ein eigenes Feld, eine Zeile je Familie, eine in
den Rücklesetabellen und einen Wert im Materialprofil. Ein Anteil, der nur mit
einem Schalter wirkt, schreibt den Schalter mit (`_positive_switch`, etwa
`reduce_fan_stop_start_freq`).

Kennt eine ältere Datei ein solches Feld nicht, ist es keine
Dataclass-Vorgabe, sondern eine Frage an dieselbe Stelle wie bei einem neuen
Projekt: Unteres Ende und Schwelle der Lüfterkurve kommen beim Öffnen aus dem
Material (`print_settings.fan_curve`); der alte eine Wert bleibt das obere
Ende, wie er im Dialog hieß. Kein Formatsprung, solange ein älteres Programm
neue Schlüssel still übergeht (`_group_from_data`) und die Datei dort druckt
wie vorher.

## Wie eine Zuordnung geprüft wird

Prusa und Orca schreiben
ihre Konfiguration in den G-Code — `verify()` vergleicht sie gegen das
Geschriebene. CuraEngine schreibt dort nichts; für es nennt
`fdmprinter.def.json` jeden gültigen Schlüssel der installierten Version:
`unknown_keys()` zur Laufzeit, `test_every_cura_key_exists_in_the_definition`
beim Bauen.

## Einstellungen reisen mit der exportierten Datei

| Slicer | Beilage | Format |
|---|---|---|
| Orca-Familie | `Metadata/project_settings.config` | JSON |
| PrusaSlicer | `Metadata/Slic3r_PE.config` | `; schlüssel = wert` je Zeile |

PrusaSlicers Beilage beginnt mit `PRUSA_CONFIG_HEADER`. Cura bekommt seine
Einstellungen über die Kommandozeile.
