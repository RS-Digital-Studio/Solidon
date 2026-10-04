---
description: "Schichtanalyse, Druckberatung, Slicer-Übergabe und Merkmalserkennung — kein G-Code-Slicer, Kennzahlen mit Herkunft, Vorschläge mit Grund, Merkmale nur mit Beleg"
paths:
  - "app/core/slice/**/*.py"
  - "app/core/perceive/**/*.py"
---

# Regeln für Schichtanalyse und Wahrnehmung

Messwerte, Modellreihen und Anlässe stehen unter denselben Überschriften in
`konzepte/begruendungen/regel-schichtanalyse.md`.

## Die Abgrenzung, die nicht verhandelbar ist

Solidon analysiert Geometrie und schreibt keinen G-Code (§22.5). Jede Kennzahl
nennt ihre Herkunft; Schätzung und G-Code-Wert verschmelzen nie. Die Oberfläche
nennt sie „Schichtanalyse“.

## Zwei Wege durch den Schnitt, und beide müssen dasselbe rechnen

Ab elf Ebenen dichte Körper mit Volumenerhalt: `Manifold.slice`; sonst gerichtete
Segmente über Cython oder NumPy/GEOS, Material über `CrossSection(Positive)`.
Netzknoten trennen berührende Schalen. Ohne eindeutige Richtung gilt der
Reparaturweg. Beide Segmentwege runden gleich auf sechs Stellen;
`test_slice_core.py` erzwingt beide. Jeder Weg bleibt abbrechbar.

## Die Einstellungen bleiben trotzdem hier

Der Slicer führt aus, er entscheidet nicht: `PrintSettings` (§29) hält alles,
was gedruckt wird, `export/handover.py` schreibt es ihm vor und liest den
G-Code zurück.

- **Aufgelöst wird aus Stufe, Material, Drucker**, in dieser Reihenfolge: Die
  Düse skaliert die Schichthöhe, Maschinengrenzen deckeln die Temperatur, ein
  offener Bauraum bekommt keine Kammertemperatur.
- **Leerfahrt und Tempo kommen vom Drucker**: `PrinterProfile.travel_speed`
  aus dem Standardprozess des Herstellers; `speed_*`, `acceleration`,
  `outer_wall_acceleration` gelten für „Standard“, andere Stufen behalten ihr
  Verhältnis (`print_settings._paced`), `flow_factor` hebt den Volumenstrom
  des Materials aufs Hotend. Ältere Projekte bekommen die Leerfahrt als
  Vorschlag.
- **Kein Tempo fördert mehr, als das Filament fließt**
  (`print_settings.flow_speed_limit`, Rechnung der Volumenstromregel) — die
  Herstellertempi gelten seinem schnellsten Filament. Ältere Projekte behalten
  ihre Tempi; schneller wird nie vorgeschlagen.
- **Was Solidon meint, wird geschrieben, auch das Muster**: „Gitter“ als
  `rectilinear-grid` (Orca, PrusaSlicer) bzw. `grid` (Cura, Linienabstand mal
  zwei); Bäume behalten das Muster des Herstellers (`slicer_keys._only`).
- **Das Maschinenprofil wird nicht erfunden**: Bettform, Anfahrwege, Start-
  und Endcode kommen aus dem Bestand des Slicers, bei der Orca-Familie auch
  das Prozessprofil: Solidon liest das benannte Systemprofil und legt seine
  Werte darüber — sonst „process not compatible with printer“.
- **Ein neuer Slicer kostet eine Tabelle** (`slicer_keys.py`), keinen Eingriff
  in den Ablauf (`handover.py`).
- **`CuraEngine` bekommt jeden Wert global und auf dem Extruder-Zug**: Nur
  global überschreibt ihn die Definition, nur am Zug fehlt er der
  Zeitrechnung.
- **Der Kopf einer Cura-Datei ist keine Messung** (`Filament used`, `MINX`,
  `TIME` stehen vor dem Rechnen): Gelesen werden E-Achse und letzte
  `TIME_ELAPSED`; ein Kopfwert gilt weiter, wo er einen Vorgang trägt, den
  keine Bahn zeigt.

**Der Bauraum wird an den Bahnen nachgemessen** (`gcode.analyze(...).extent`,
`handover.off_the_bed`), denn CuraEngine prüft ihn nicht. `G2`/`G3` zählen
mit; die Stelle wird über alle Bewegungen nachgeführt. Geprüft wird in
Maschinenkoordinaten, Ursprung wie die Maschine, getrennt von der Verschiebung
der Eingabe (CuraEngine verschiebt selbst, Prusa- und Orca-Projekte enthalten
sie); eine Bettkontur in der Druckdatei geht dem Druckerprofil vor. Gemeldet,
nicht gesperrt (§29) — unter einer Bahnbreite gar nicht, die Bahn liegt
ohnehin halb neben der gemessenen Mitte.

## Vorschlag oder Befund

`slice/advise.py`: Was ein Wert behebt, wird ein **Vorschlag**
(`SettingAdvice` mit Pfad, altem und neuem Wert und **Begründung** — ohne Grund
keiner); was kein Wert behebt, ein **Befund** (`Finding`), etwa ASA auf
offenem Drucker. Übernommen wird auf Klick, nie von allein.

- **Ein Vorschlag je Einstellung**, `was` ist der Ausgangswert; Regeln auf
  denselben Wert werden zusammengeführt, die spätere gewinnt. Der Volumenstrom
  läuft zuletzt, weil er an Schichthöhe, Bahnbreite und Tempo hängt.
- **Volumenstrom** (Schichthöhe × Bahnbreite × Tempo gegen `max_flow`): ein
  Tempo je Bahnart, die erste Schicht mit eigenen Maßen; keine pauschale
  Temperaturanhebung (keine Kurve hinterlegt), und eine kleine Standfläche
  begründet Haftung, keine Filamenttemperatur. Reicht auch das kleinste Tempo
  nicht, hält die Beratung mit einem Vorschlag zu Schichthöhe, Bahnbreite oder
  gemessenem Profilwert an — eine leere Liste wäre keine Entwarnung.
- **„Viel auf einmal“ heißt an einem Stück** (`largest_overhang_patch`), nicht
  je Schicht — kleine Stegunterseiten tragen sich selbst. Ein Ergebnis ohne
  Stücke gilt schichtweise als eines; lange Stege fängt die Brückenregel.
- **Den Stützwinkel sagt, womit der Slicer stützt** (Konzept Herstellerprofil,
  Entscheidung L): gemessen auf dem Raster der Probe, sonst die Schwelle des
  gewählten Herstellerprozesses, sonst `overhang_limit` aus `printers.toml`,
  sonst die Startregel (`Profile.overhang_limit_degrees`). Auswertung,
  Druckdialog-Rat und Kanalsperre rechnen mit den wirksamen Einstellungen
  (`Session.evaluation_profile`, `profiles.for_process(..., effective=True)`);
  aus einem gespeicherten Satz gilt die Schwelle nur als eigene Wahl.
  **Wer einen Winkel einführt, reicht ihn bis in jede Vorauswahl durch.**
- **Ein Überhangwinkel wird an der Normalen mit dem Sinus verglichen**
  (z < −sin(Grenze)) und an einem Winkel ungleich 45 geprüft, wo sich Sinus
  und Kosinus unterscheiden
  (`test_orient.py::test_the_preselection_counts_overhangs_against_the_printers_limit`).
- **Eine Decke im Kanal verlangt keine Stütze auf dem Modell**
  (`analysis.model_support`): Fasst der freie Raum unmittelbar **unter** ihr
  keinen Kreis von `CHANNEL_WIDTH` um das Stück, schließt sie sich als Brücke
  oder Gewölbe und fällt aus dem Stützbedarf. Außen auf dem Modell zählt nur
  ein Stück über `OVERHANG_LAYER_WORTH_SUPPORT` oder die Summe über
  `OVERHANG_WORTH_SUPPORT`. Wer die Grenze anfasst, misst die Gegenfälle an der
  Konstante nach und fährt die Waschschüssel im Slicer.
- **Eine Insel ist nie eine Kanaldecke**: Auf dem Modell heißt es „überall“,
  gleich wie klein (`ModelSupport.island_on_model`); über dem Bett verhindert
  sie „nur vom Bett“ nicht.
- **`support.block_channels`**, weil „nur vom Bett“ nicht in jedem Slicer den
  Kanal freihält: eine Stützsperre aus `analysis.channel_space` — freie Fläche
  um die Kanalsäulen **innerhalb der konvexen Hülle** der Schicht, jede Scheibe
  eine Scheibenhöhe in die Decke, weil der Slicer an der Überhangfläche
  fragt. Je Familie: `dateiformat.md`, „Was welcher Slicer bekommt“.
  **Vorschlag, nicht Automatik** (Entscheidung Robert).
- **Die kleine Standfläche wird auch je Fuß gefragt** (`advise._on_small_feet`):
  Erreicht keine von mehreren Inseln `SMALL_FOOTPRINT`, heißt es Brim — nur
  als Vorschlag. `for_part` fragt mit Profil jede Regel für `PART_PATHS`;
  seine Brim-Regeln aus dem Schnitt behalten das letzte Wort.
- **Eine runde Außenwand bekommt die Schrägnaht vorgeschlagen**: glatte
  Umrisse (kein Knick über `analysis.SMOOTH_TURN_DEGREES`, gemessen über Arme
  der Düsenbreite wie im Slicer, ab `advise.SCARF_MIN_LOOP` Umfang) über
  `SCARF_MIN_HEIGHT`.
- **Schmale Stege bekommen eine langsame erste Schicht**: Liegt mindestens
  `advise.NARROW_WEB_SHARE` der ersten Schicht in Stegen unter
  `NARROW_WEB_LINES` Bahnen (`analysis.narrow_share`) oder mehr als
  `NARROW_WEB_AREA` mm² davon, und ist sie schneller als `NARROW_WEB_SPEED`,
  wird dieses Tempo vorgeschlagen. Über dem Herstellerprofil bremst er nur
  (`dateiformat.md`).
- **Kein Vorschlag überstimmt, was das Profil für denselben Zweck trägt**:
  Mindestzeit je Schicht nur ohne eine, kein Brim über Orcas Auto-Brim
  (`AUTO_BRIM_FLAVOURS`) — gebremst wird dort trotzdem: `_calm_walls` für
  schlanke Körper unter `SMALL_FOOTPRINT`, je Teil.
- **Mehrere Körper werden gemeinsam beurteilt** (`advise.combine`), auch
  passende — ein Würfel schaltet die Stützen eines anderen nicht ab.
  Filamentwerte werden je tatsächlichem Slot aufgelöst und nur darin
  zusammengeführt, Prozesswerte passen für alle gewählten Körper; Abgewähltes
  bleibt bei Neuberechnung abgewählt.
- **Die Druckanalyse benutzt das Druckraster**: `slice_body` bekommt normale
  und erste Schichthöhe aus den effektiven Einstellungen; der Dialog misst den
  Ausgabeumfang im Hintergrund und verwirft Ergebnisse veralteter Szene,
  Platte oder Raster. Fehlende oder abgebrochene Messung ist keine
  Entwarnung. Die Orientierungssuche behält ohne Erstschichthöhe ihr
  gleichmäßiges Raster.
- **Was in Geometrie gerechnet ist, wird nicht so gedruckt**: `solid_core`
  misst `Durchmesser − 2 × Wandzahl × Bahnbreite`. Gemeldet erst, wenn der
  Füllkern breiter ist als das Material darum; vorgeschlagen wird die Wandzahl
  genau bis dahin, nie bis vollmassiv, bei gefülltem Kern nichts — und über
  `MOST_WALLS_WORTH_SUGGESTING` keine, der Obergrenze des Dialogfelds, die der
  Kern selbst führt (Regel 1; `tests/test_print_settings_ui.py` hält beide
  gleich). Der Materialanteil belegt keine Festigkeit.

> **Ein Vorschlag ist ein Knopf, kein Hinweis.** Was er trägt, landet auf
> Klick in der Datei für den Slicer; ein Wert, den das Feld nicht darstellen
> kann, ist ein stiller Unterschied zwischen dem, was der Kunde sieht, und dem,
> was er druckt. Und was die Geometrie als Material führt, ist erst Material,
> wenn eine Bahn darin liegt.

## Das Maschinenprofil des Slicers

`export/slicer_profiles.py` liest den installierten Bestand: gesucht wird der
Ordnername irgendwo im Pfad (die Tiefe ist nicht einheitlich);
`compatible_printers` wird über `inherits` vererbt; eigene Profile tragen kein
`type`/`instantiation`, stehen unter `from: User` und gehören in die Liste.
Zugeordnet wird über `printer_model`, Düse und `default_print_profile` — ohne
Treffer bleibt die Auswahl leer. Ein Slicerwechsel leert sie
(`_clear_profile_choices`) am **Anfang** der Suche, weil
`_start_profile_search` für `prusa` und `cura` früh zurückkehrt; sonst bekommt
CuraEngine ein `-j` auf eine Orca-Datei. Wo nichts zu wählen ist, wird nichts
gemerkt.

## Was geschrieben wird, ist nicht alles, was im Modell steht

Skirt, Brim und Raft lesen die Slicer als Schalter: `_only_chosen_adhesion`
nullt die Maße der nicht gewählten Arten. Dasselbe gilt jeder Einstellung mit
Art und Maßen — der Fehler ist geräuschlos.

## Die Druckdatei gehört dem Nutzer

Der G-Code aus dem Arbeitsordner muss speicherbar sein (Vorschlag: Ordner und
Name des Projekts). Druckeinstellungen gehören ins Projekt (seit
`format_version` 4), Slicer-Pfad und Profilwahl zur Anwendung — das Teil
reist, der Rechner nicht.

## Die Einstellungen reisen in der Datei mit

`threemf.write_assembly` schreibt `Metadata/project_settings.config`
(`handover.project_settings`). Filamentschlüssel sind Listen je Extruder,
`from` und `name` nicht; welche es sind, sagt die Sektion der
Übersetzungstabelle, keine zweite Liste. **Die Betttemperatur gehört der
aufliegenden Platte**, `curr_bed_type` der Maschine: Ist die Platte unbekannt,
geht die Temperatur auf jede Platte (`handover._with_every_plate`), bekannt
nur auf deren Schlüssel (`dateiformat.md`). `profile_file` fragt
`find_profiles` mit der gesuchten Art — ohne sie findet es kein Filament.
Pfade zum Slicer sind absolut, weil `slice_model` sein eigenes
Arbeitsverzeichnis setzt.

## Eine Platte ist eine Datei

Was zusammen gedruckt wird, geht als **eine 3MF-Baugruppe** hinaus
(`threemf.write_assembly`; Cura und das Slicerfenster: `dateiformat.md`).
`merge_slots` legt Materialslots über alle Teile nach Name, Farbe,
Materialprofil und Materialart zusammen — dieselbe Farbe ist nicht dieselbe
Spule —, und ihre Reihenfolge ist die Extruderbelegung. **Jede Platte ist ein
eigener Lauf**, bei allen drei Familien: eigene Baugruppe, Slots,
Anordnungsprüfung und Druckdatei, der Name trägt die Plattennummer.
`gcode.combine` addiert Zeit und Material, nicht die Schichtzahl; fehlt ein
Wert, fehlt die Summe.

## Die Gegenprobe ersetzt die Dokumentation

`handover.verify` liest die Konfigurationskommentare der Druckdatei und
meldet nur, was **nachweislich** anders übernommen wurde — ein fehlender
Schlüssel sagt nichts, und eine Gegenprobe voller Fehlalarme wird übersehen.
Verglichen wird nachsichtig (`0.2`/`0.20`, `15%`/`15`, Liste aus einem
Element).

## Die Schätzung ist eine Näherung mit Herkunft, keine Rechnung

`slice/estimate.py` antwortet in Mikrosekunden, damit die Zahl beim Ziehen an
einem Parameter steht. Die Schale ist die Differenz zweier Körper (mittlere
Wanddicke `3V/A`, Kern als deren dritte Potenz), nie Fläche mal Dicke — das
zählt Kanten doppelt. Wer die Rechnung anfasst, prüft kompakte **und**
dünnwandige Körper (`tests/test_estimate.py`). Stützen, Rand, Fahrwege und
Nähte kennt sie nicht; sie trägt `source="internal"` (Regel 14).

## Was die Analyse liefert

- **Zwei Breiten, zwei Fragen**: `minimum_width` ist die kleinste Struktur
  (morphologische Öffnung — der einbeschriebene Kreis übersieht eine Rippe
  neben einer Platte), `spanning_width` die weiteste freie Stelle. Bei offenen
  Seiten müssen beide Enden jeder freien Bahn aufliegen, und eine kurze
  ungestützte Querrichtung verkürzt keinen Steg; ohne beidseitig getragene
  Richtung bleibt es eine konservative Schätzung.
- **Die Öffnung sagt Nein aus den Teilen und Ja aus der ganzen Form**: Der
  Verlust eines Teils belegt das Nein, aber sich berührende Öffnungen zählen
  doppelt — ein Ja kommt nur aus der ganzen Form (`WIDTH_SCAN_PARTS` deckelt
  den Teileweg). Änderungen prüfen beide Richtungen gegen `_opening_loss`.
- **Ab wann eine Fläche Brücke ist, sagt der Drucker** (Regel 7):
  `slice_body(bridge_from=…)` aus `Profile.minimum_wall_thickness` über
  `profiles.analysis_limits`. Die Schichtanalyse nimmt Zahlen, keine Profile;
  **wer sie zwischenspeichert, nimmt sie in den Schlüssel**.
- **Die Orientierungssuche misst Stützräume am Ersatznetz und den Stand am
  Original** (`judge(footing_mesh=…)`, auch in der Vorauswahl). **Die sechs
  Achsen werden immer geschnitten**, weil die Heuristik liegende Lagen vor
  stehende reiht; höchstens `FINALISTS` + sechs Achsen + Ausgangslage.
  **Was steht und nach `advise.support_need` keine Stütze braucht, bleibt,**
  **wenn der Gewinner Stütze braucht** (`orientation.stays`, am Original).
  **Auto Splits Vorauswahl hält der billigsten stehenden Lage einen Platz**
  (`ranked_orientations(standing=…)`).
- **Eine dünne Wand ist nicht allein deshalb undruckbar** (Arachne); unter der
  Mindestbahnbreite verlangt der Befund die Kontrolle im Slicer.
- **`taper_length` misst Außenkontur auf einem Keil** — einer Wand, deren
  Stärke stetig über mehrere Bahnen läuft (Band und Längen: `TAPER_*` in
  `slice/analysis.py`). Ab einem Fünftel der Schichten mit Keil, variablem
  Wandgenerator und ohne Stütze schlägt `advise.py` „Außenwand zuerst“ vor.
  Gemessen wird an jeder fünften Schicht (`TAPER_SAMPLE`); einen kürzeren Keil
  verfehlt die Stichprobe (`test_slice.py`), je Schicht fragt
  `taper_length(shape)`.

## Die Öffnung zählt, was der Form fehlt

Die Flächenbilanz der gefasten Öffnung ist keine Antwort: Eine Nadel über die
Form hinaus gleicht Verlust aus. Ein **Nein** darf aus der Bilanz kommen, ein
**Ja** nur aus `_protrusion`; Erosionssplitter unter `WIDTH_SIMPLIFY` werden
nicht aufgeweitet; was vom Anfangspunkt eines Rings abhängt, bekommt
`_canonical`, sonst rechnen die zwei Wege verschieden. Wer das anfasst,
vergleicht an echten Modellen Schicht für Schicht gegen `Form − Öffnung` und
misst die Zeit vorher und nachher, auf einem und auf sechs Arbeitern.

## Die Befunde im Prüfbericht kommen nach der Auswertung

`slice/findings.py` meldet jeden Befund mit Ort, Handlung und
`source="internal"`, im Arbeiter **nach** der Auswertung
(`ui/print_findings_flow.py`), nie in ihr — die Auswertung läuft bei jedem
Klick, die Schichtanalyse kostet Sekunden. Gemerkt wird am Netz; der
Schlüssel nennt Raster, Winkel, Brückenbreite und Drucker.

## Stabile IDs

Provenienz-IDs überleben jede Neuberechnung — sonst zeigt der Op-Stack ins
Leere; mehrdeutige Zuordnung hält an und fragt.

- **Starr bewegt erbt die Erkennung** (`features.moved_from`); gespiegelt
  (das Gewinde wechselt die Hand) und skaliert wird neu erkannt.
- **Zwillinge entscheidet die Lage ihrer Oberfläche**
  (`matching.settled_by_surface`, vor `_divided_partners`): nur, wenn sie für
  beide Seiten mit Vorsprung die nächste ist; sonst bleibt es eine Frage.

- **Eine geteilte Fläche heißt am größten Stück weiter**
  (`evaluate._divided_partners`), gesucht in ihrer Ebene innerhalb ihrer alten
  Dreiecke — nur, wenn diese Dreiecke die Fläche sind (Normale, Ebene), nie
  über Nummern, die eine Operation an ihrem eigenen Ergebnis vergab, und nicht
  nach einer Bewegung. Gleich große Stücke sind eine Frage (Regel 21), sobald
  ein Verweis daran hängt. Wer eine querende Fläche teilt, gibt sie beiden
  Hälften mit (`prepare_ops._features_after_split`).
- **Ein Verlust ohne Verweis** wird einmal je Körper und Schritt gemeldet
  (`perceive.orphaned`/`perceive.mended`, alle Kennungen in den Werten); **mit
  Verweis** bleibt er je Merkmal eine Warnung (§21.3).

## Jede Schwelle der Erkennung wird an beiden Seiten gemessen

Wer eine Zahl oder Bedingung der Merkmalserkennung anfasst, fährt
Konstruiertes **und** Figuren, Scans, Schriftzüge und erzeugte Netze aus dem
Korpus `F:\3D Dateien` gegen den Vorstand und sieht sich jedes geänderte
Merkmal an. Eine Rückfallregel, die im Korpus nie ihren Fall trifft, zeigt
dort nur ihre Fehlgriffe. Im Zweifel bleibt ein Merkmal, was es war.

## Ein Löserlauf entfällt nur mit dem Nein des Stapels

Nur `refine.exhausted` lässt einen Kegel- oder Ringlauf aus, kein Sieb aus
Fleckmerkmalen. Seine Residuen folgen `_cone_from_plan`/`_torus_from_plan`
(`tests/test_refine.py`).

## Auf einer Freiform sind Kugel, Ring, Kegel und Verrundung keine Merkmale

`features.is_a_freeform` urteilt an der fertigen Liste
(`FREEFORM_ROUND_COUNT`, `FREEFORM_ROUND_SHARE`), `_shapes_on_a_freeform`
nimmt die vier Rundformen heraus; Bohrung, Zapfen, Fläche, Kantenzug und
Gewinde bleiben. **Nicht still**: `freeform_dropped` wird `perceive.freeform`
(Regel 17), und der Satz nennt die Messung (überwiegend gekrümmt), keine
Herkunft wie „Scan“. **Einen zweiten Zustand** („überwiegend rund“) **gibt es
nicht** — er bräuchte eine zweite Schwelle in einer schmalen Lücke.

### Die Haut wird nicht in Splitter zerlegt

Entscheidung Robert.

- **Haut** sind Flecken ohne Grundform, die nach Krümmung in Splitter
  zerfallen (`FREEFORM_SPLINTERS`, `FREEFORM_PIECE_SHARE`), zusammen über
  `FREEFORM_SKIN_SHARE` der Oberfläche. Ihre Splitter werden nicht einzeln
  eingepasst, die Stücke von Gewicht schon.
- **Das Urteil fällt einmal je Körper zwischen den zwei Runden von `_fitted`**
  — nach `classify` über alle Flecken und `_split_patches_by_curvature` über
  die gescheiterten, vor dem ersten Splitstück — und zählt nur, was keine
  Grundform ergab: Eine Kugel als ganzes Modell zerfällt wie eine Figur, nur
  der Fit trennt sie. **Die Runden nicht wieder verschränken**, und keine
  Abkürzung „auf der Haut nur den Zylinder fragen“.
- `is_a_freeform` nimmt `Fitted.freeform_skin` vor die Zählung, die weiter die
  verrauschte Freiform ohne Haut trägt; `perceive.freeform` kommt auch mit null
  weggelassenen Formen (`recognised_as_freeform`) und behauptet keine Suche,
  die nicht stattfand.
- **Raue Tafeln sind ein eigener Auslöser** (`features._rough_facet_area`,
  `FREEFORM_ROUGH_SHARE`/`_MIX`/`_BEND`) — nicht in der Splittersumme und nicht
  über alle verrauschten Facetten; beides kostete Konstruiertes.

### Was an einer Bohrung hängt, bleibt

Eine Rundform an der Mündung einer bleibenden Bohrung übersteht den Filter
(`features.sits_at_the_mouth_of`). **Die Frage schärfen, nicht die Schwelle
nachziehen.** Den Filter an Freiformen belegen, nicht an den Senkungsplatten
des Korpus. Ein weggefiltertes Merkmal nimmt seine Nachbarschaft
mit (`relations.cavity_chain_at`).

## Ohne Wendel ist ein Gewinde eine Fläche, deren Gänge ineinanderlaufen

`features._without_thread_turns` verwirft Zylinder ohne Wendelbeleg nur an
**einem Teil**, mit **derselben Materialseite**, und wenn jeder weitere
Abschnitt in den Lauf **hineinläuft und mehr Neues bringt, als er teilt**
(`_one_run`) — alles aus der Wendel, keine neue Zahl. Gemessen wird an
gedruckten Gewinden ohne Wendelsuche und am Korpus je Stapel.

## Ein Bogen hat einen Radius und liegt auf seinem Kreis

- **Jede glatte Kurve ist kurz ein Kreis** und besteht `fit_cylinder`; als
  gezeichneter Bogen (`_exactly_an_arc`) gilt ein Stück erst mit gleichem
  Radius über das ganze Stück und genauen Ecken.
- `features._arcs_of_a_prism` trennt erst über dem Rauschen (`PRISM_ARC_JUMP`)
  und gar nicht, wo die Schätzung selbst Rauschen ist (`PRISM_QUIET_SHARE`).
- **Ein geteilter Streifen leiht seinen Radius nur nach innen**
  (`features._through_the_piece`): nur für Dreiecke ganz im Inneren der
  Facette, nur wo die Nähte sich auf einen Radius einigen. Wer das lockert,
  verlangt null geänderte ungeteilte Körper.

## Ein tangentialer Verbund wird an seinen Zylindern getrennt

Was keine Runde davor teilt, trennt die sechste an Zylinderstücken mit allen
Ecken bis zur Verschweißtoleranz auf dem Mantel (`_tangential_pieces`). Es
zählt nur, was für sich steht: Züge gleichen Radius als Ganzes
(`_drawn_chains`), kein Stück nur am unerklärten Rest (`_enclosed_rounds`).

## Ein Umriss mit wanderndem Radius ist eine gerundete Seite

`features._wandering_outline` entscheidet über die Stücke eines Flecks
**zusammen**; Kennzahlen eines einzelnen Stücks trennen Spline und Bogen nicht
(gemessen, nicht erneut messen).

- **Ein bestätigter Kreis ist ein Bogen** und hält die Folge an: ein zweites
  Stück wie in `_same_cylinder`, eines auf dem Kreis des anderen
  (`_lies_on_the_cylinder`), oder ein gezeichneter Bogen. Eine Richtung
  genügt (Preis: RM-254).
- **Zwei Wechsel in dieselbe Richtung sind ein Verlauf**: unbestätigte,
  tangential folgende Kreise (über Splitter und formlose Stücke hinweg) mit
  Schritten unter `CURVATURE_JUMP`, ein engerer und ein weiterer Nachbar. Eine
  Untergrenze für den Schritt trennt nicht.
- Im wandernden Fleck bleiben bestätigte und gezeichnete Kreise; zurückgezogen
  wird nach der Zusammenlegung nur, was ganz auf vorgemerkten Dreiecken liegt
  (`_off_the_outline`). `test_features.py` hält jede Bedingung einzeln — außer
  `CURVATURE_JUMP` und dem Durchlaufen formloser Stücke, die kein Test hält.

## Eine Verengung ist keine Senkung

Ein hohler Kegel ist eine **Verengung** (Haltelippe;
`features.narrowings_marked`, beide Kerne), wenn das weite Ende mehrheitlich
auf seiner Bohrung sitzt, das enge auf keiner, das enge offen ist (dritte Ecke
der Nachbardreiecke außerhalb der Naht) und eine Öffnung statt einer Spitze
bildet. Im Zweifel bleibt der Kegel.

- Die Handlungen tragen die Lippe mit: Bohrungswerkzeuge über ihr eigenes
  Profil (`prepare_ops._narrowing_outline`), Versetzen, Verdoppeln,
  Vervielfachen und Entfernen der Kette über die eigenen Flächen der Tasche
  (exakt: `prepare_ops._exact_chain_own_cavity`, `_narrows_outward`). Was sie
  nicht anbieten, begründen `perceive.actions.cone_reason` und
  `not_offered_at`.
- **Was die Handlungen hinterlassen, muss die Erkennung wieder als Verengung
  lesen** — offene Mündung, ganze Facetten, keine Narben.
- **Gekippt liest keine Erkennung die Lippe**: *Merkmal drehen* kippt eine
  Kette mit Verengung nicht (`perceive.actions.narrowing_reason`,
  Registerpunkt RM-262), und schräg eingesetzte Magnettaschen erzeugen
  dieselbe Lage.

## Ein Hohlraum ohne Weg nach außen ist keine Bohrung

`detect_voids` gibt eingeschlossene Negativschalen, die `detect_holes` sonst
als Bohrungen ohne Öffnung läse, als Merkmalsart `void` aus;
`_voids_instead_of_phantom_bores` nimmt die Phantombohrungen darauf weg.

- **Vier Tore**: dicht, einheitlicher Umlaufsinn, mehr als eine Komponente,
  Schale im Material der **festen** Komponenten — nicht gegen „alles andere“,
  sonst fällt jeder Einschluss mit Nachbarn durch. Am offenen Netz wird nicht
  geraten (Regel 21).
- **Benannt, nicht verschwiegen** (Regel 17; Entscheidung Robert): im
  Objektbaum, kein `perceive.void`; ein zusätzlicher Befund gehört in die
  Bauart von `perceive.freeform` (`scene/evaluate.py`). Unlesbare
  Schalenpaare: keine Einschlüsse, dafür ihre Zahl über
  `features.unreadable_void_shells` in einen solchen Befund, nicht in ein
  Protokoll.
- **Enthaltensein per Strahl** nur mit Zertifikat über die Hüllquader, sonst
  native Differenz; ein Strahl auf einer Kante nimmt die nächste Richtung.
- `void` steht in `MOVABLE_KINDS` (belegt von
  `test_a_cavity_inside_the_body_moves_without_losing_material`), nicht in
  `DUPLICABLE_KINDS` (Robert); Größe und Drehung fehlen mangels Maß.

## Eine Formtoleranz wird an fremden Netzen gemessen, nicht nur an eigenen

- **Schweißtoleranz und Formtoleranz sind zwei Fragen**; die Formfrage (etwa
  in `radial_cylinder`) nimmt `features.ROUND_WALL_TOLERANCE` (ein Fünftel von
  `units.MAX_FACET_SAG`), belegt an importierten Dateien.
- **Ein Fit behauptet nichts unter seiner Auflösung**: Ein Stadion mit einem
  Weg unter `STADIUM_TOLERANCE · Radius` ist keines (`StadiumFit.good`); was
  der Zylinderfit ablehnt, nimmt kein weicherer Fit an.
- **Eine runde Wand heißt runde Wand** (`radial`, über 180 Grad, gehört zu
  keiner Kante; `actions.ROUND_WALL_HAS_NO_PLACE`); geht sie tangential in die
  Nachbarn über (`features.tangent_walls`), ist auch der Radius
  fest — Panel und Operation sagen `actions.WALL_BLENDS_INTO_ITS_NEIGHBOURS`.
- **Ein Kegel unter vollem Umlauf** geht im Langloch auf, an dessen Mantel er
  grenzt, oder bleibt Senkung der angeschnittenen Bohrung daneben; sonst ist er
  Kegelfläche (`partial`) ohne Körperhandlung (Panel und `_movable_feature`:
  `actions.CONE_PIECE_HAS_NO_BODY`; `features._partial_cones_folded`) und
  bleibt für die Freiformprobe im Bestand.
- **Ein Fleck auf der vorhandenen Wand gehört zu ihr**, wenn der gemeinsame
  Fit nicht schlechter streut als die Teile oder er im Vertrag von
  `CYLINDER_SPREAD` auf dem Zylinder liegt (`features._lies_on_the_cylinder`).
- **Die Langlochsuche rechnet je Bogen** (`slots._Reach`, die Maske einer
  Achse ist ihr Schlüssel); der Stadionfit drückt die Breite nie unter die
  Bögen.

## Das Panel bietet nur an, was die Operation hält

- `actions.fillet_blocked` fragt vorher, was die Bearbeitung fragt: Ohne genau
  zwei quer zur Achse angrenzende, tangential treffende Ebenen am Bogen
  (`features.replaces_an_edge`,
  gelesen von `geom/edges.py` in `sharp_corner`) stehen *Entfernen* und
  *Radius ändern* grau mit `edges.NOT_BETWEEN_TWO_PLANES`, und `sharp_corner`
  sagt dasselbe. Der Name bleibt Verrundung. Eine Ecke ohne Achse steht
  ebenso grau (`prepare_ops._refuse_a_corner`).
- `actions.no_own_body` fragt, was `prepare_ops._tool_for` fragt
  (`NO_OWN_BODY`; `NO_BODY_FROM_FACES` über `has_own_body`), an allen
  Körperhandlungen. Kundentexte: zwei Sätze, der Rückweg im zweiten.
- **Zerfällt ein Körper nach einer Merkmalsänderung, sagt es ein Satz:**
  `bore.splits_the_body` der Bohrung, sonst `feature.body_split`
  (`touches_features`, `evaluate._split_findings`; Urteil in
  `geom.boolean.body_split`; gewollt lose Teile: `bausteine.md`).
- **Ein konvexes Werkzeug aus den Flächen wurzelt in seiner Grundfläche und
  spart durchlaufende Hohlräume aus** (`prepare_ops._rooted`,
  `_without_cavities`, `_placing_tool`) — nur beim Setzen, nicht beim
  Abtragen. Das Abtragwerkzeug eines Zapfens umschreibt sein Vieleck
  (`_closed_at`).

## Viele gleiche Zellen sind ein Muster, und die Grenze zur Bohrung ist eine Entscheidung

**Erzeugte Texturen und ausdrücklich zusammengefasste Zellen**
(`group_pattern`) sind ab jeder Zellzahl ein `pattern` mit Schrittkennung
(`bound_to_its_surface`); `surface_triangles` belegt ihre Flächen,
Folgeschritte binden neu. Einzelzellen gehen darin auf, ihre Namen bleiben
reserviert, fremde Bohrungen frei. Ohne Wahl gelten die Schwellen unten; die
Zusammenfassung liest dieselben Zellen (`_read_cells`) ab zwei, Bohrungen
(`_a_bore`) sagen ab. Der exakte Körper fragt dieselbe Suche.

`perceive/patterns.py` faltet erst ab `MIN_CELLS` deckungsgleichen Zellen
(Streifen `MIN_STRIPS`, Streuung `MIN_SCATTER`, Rauschen `MIN_NOISE`). Runde
Zellen nur als Noppe — blind, höchstens `ROUND_DEPTH`-mal so tief wie breit,
ab `MIN_ROUND_CELLS`, nur im Wabengitter von `apply_texture`: Lochblech,
Magnettaschen und Quadratraster behalten ihre Bohrungshandlungen. Sechseckige
Löcher werden auch durchgehend zum Muster; in einem Gitter, das Solidon nicht
zeichnet, heißen sie `other` (entfernbar, nicht neu setzbar). Jeder Stil wird
nur in seinem Gitter neu gezeichnet (`_GENERATOR_LATTICE`).

- Gefaltet wird nach allen Einzelformen und **vor** dem Freiformfilter.
- Muster folgen zusammenhängenden Feldern und Streifenrichtungen; der
  Träger wird am Netz belegt, am Zylinder in der Abwicklung.
- **Unter gleichen Zellen wählt `patterns.SEAM_DIRECTION`** — Naht unter
  gleich großen Lücken (auch um Randstücke), Anker unter gleich nahen Zellen —,
  nie der Rundungsrest oder die erste Ebenenachse.
- Ein Stopfen liegt auf den Facetten, nicht auf dem Kreis; erst teilen, dann
  biegen; **geteilt wird konform** (`patterns._cut_at`), nicht mit
  `split_by_plane` und Vereinigung. Wer eine Auskunft genauer macht, sucht die
  Verbraucher, die an ihrem Rauschen hingen.
- Vertiefte Stopfen enden an `Frame.span`; die Aufweitung zum Boden einer
  Tasche mit parallelen Wänden gilt nur dem Umfang. Stopfen und neues Muster
  teilen den Mündungssaum (`_mouth_with_margin`) — ein gefüllter Streifen
  gehört zum neuen Feld. Am Stirnrand reicht nur das Schneidwerkzeug über die
  gemessene Stirnfläche, bezogen auf deren Ebene.
