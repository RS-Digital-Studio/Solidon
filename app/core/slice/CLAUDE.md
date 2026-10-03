# `app/core/slice/` — Schichtanalyse

Kennzahlen und Konturen aus dem Modell — **Analyse, kein G-Code-Slicer**
(§22): Die Datei für den Drucker kommt vom externen Slicer, G-Code wird hier
nur gelesen. Einzuhalten ist `.claude/rules/schichtanalyse.md`; Messwerte und
Anlässe dieser Karte stehen in `konzepte/begruendungen/karte-app-core-slice.md`.

```
analysis.py  ──> geschätzt   (aus der Geometrie, sofort)
gcode.py     ──> geplant     (aus dem G-Code des Slicers, nach dem Lauf)
```

Beide Herkünfte verschmelzen nie (Regel 14); erst eine Feststellung am
gedruckten Werkstück ist eine Messung des Verbrauchs.

## Die Karte

| Datei | Rolle |
|---|---|
| `analysis.py` | Der Analyse-Schneider: Konturen, Überhänge, Inseln, Brücken, Stützvolumen (§22); `model_support` merkt seine Antwort je Messung (Identität des Schichttupels) |
| `_chain.pyx` · `_chain.pyi` | Übersetzter Ebenenschnitt und Konturverkettung (`tools/build_slice_core.py`, Budget §31); ohne ihn gerichtete Verkettung über NumPy |
| `advise.py` | Einstellungen aus Geometrie, Material und Maschine (§22.2, §29): Stützort über `analysis.model_support` (außen, Kanal, Insel), Kanalsperre als Vorschlag, Leerfahrt aus dem Drucker, Brim auch für viele kleine Füße, ruhige Wände und Beschleunigung für schlanke Körper auf kleinem Fuß (`_calm_walls`), langsame erste Schicht über schmalen Stegen (`analysis.narrow_share`), Schrägnaht an runden Außenwänden (`analysis.smooth_outline_height`), Volumenstrom über `knowledge.print_settings.flow_speed_limit` (sein Deckel ist an `limits_flow` zu erkennen); `combine` vereint den Ausgabeumfang, ohne benötigte Stützen zu verlieren; Bremsen auf Tempo und Beschleunigung lockern keine frühere Regel (`_merged`, `_BRAKING_PATHS`); `for_part` gibt mit Profil den Rat je Körper für `PART_PATHS`, `SLICED_PATHS` sagt, welche davon den Schnitt des Körpers brauchen (danach schneidet der Export), `plate_paths` die plattenweiten Gründe, `connector_diameters` die Verbinder eines Körpers |
| `gcode.py` | G-Code zurücklesen (§28.1, §28.2) in einem Durchlauf, auch die erste Schicht mit Bauteillüfter (`fan_start`) |
| `estimate.py` | Kostenschätzung sowie eingefrorene Plattengegenprobe aus tatsächlich exportierten Netzen und Teilwerten (`plate_comparison`); vollständige gemeinsame Stützanalyse, belegte Modelllagen, beide Herkünfte je Platte (`plates_findings`) |
| `findings.py` | Die Schichtanalyse im Prüfbericht (§17.3, §22.2, §22.3): Inseln mit Ort, größter frei hängender Überhang außerhalb der Kanäle (`model_support(..., only=)` nur über der Meldeschwelle), lange Brücke und schmalste Stelle mit Ort (`advise.located_warnings`), gesparte Stütze einer anderen Lage; gemerkt im Netzcache, gerufen von `ui/print_findings_flow.py`. `remembered_analysis` gibt die Messung heraus, ohne zu rechnen — Druckdialog (`_AdviceWorker`) und Stützsperre (`export.writer._support_blocker`) fragen dort zuerst |
| `orientation.py` | Die Suche nach einer Druckorientierung (§28.2); dazu eine kleine Grundflächen-Vorauswahl für Auto Split mit demselben Stützvolumen und derselben Fünf-Prozent-Grenze (§22.3) |

## Die Orientierungssuche

- **Kandidaten** kommen deterministisch aus den flächengeordneten Normalen der
  konvexen Hülle (Stichprobe `HULL_SAMPLE`), den Achsen und großen
  Körperflächen; der Druckbereich wird vor der Schichtanalyse geprüft.
- **Geschnitten** werden höchstens `FINALISTS` der Heuristik (Standfläche,
  Überhangfläche), die `SUPPORT_FINALISTS` mit dem kleinsten geschätzten
  Stützraum (`geom.orient.Orientation.support`: Überhangfläche in Projektion
  mal Höhe über dem Bett, spiegelgleiche Lagen einmal), die sechs Achsen und
  eine zulässige Ausgangslage; der Bericht trennt betrachtete, passende und
  geschnittene Lagen. Eine unzulässige Ausgangslage hat `baseline=None` —
  dafür wird keine Einsparung behauptet.
- **Stützräume am ausgedünnten Ersatznetz** (20 000 Dreiecke), **Standfläche
  und Stand am Original**, auch in der Vorauswahl.
- **Stehen heißt, die erste Schicht lässt sich drucken**: Schwerpunkt in der
  Hülle der Auflage; mit Druckerprofil misst `judge(…, line_width=)` die
  Auflage eine halbe Linienbreite nach innen (`Candidate.footing`) — eine
  Kante trägt keine Linie. Unter Stehenden entscheidet das Stützvolumen,
  innerhalb fünf Prozent die Auflagefläche.
- `standing_check` teilt diese Standprüfung zwischen Auto Splits Vorauswahl
  und der schnellen FDM-Ausrichtung: halbe erste Schichthöhe, Linienbreite,
  Mindestauflage und Schwerpunkt am Original, mit Abbruch vor und nach der
  Messung. Sie schneidet nur die Auflage, nicht alle Schichten.
- **Das Original wird nie kopiert**: `geom.orient.extreme_points` (im
  Netzcache) liefert die Hüllbox jeder Lage (`turned_extents`), `judge` dreht
  nur Schwerpunkt und die Dreiecke an der Aufstandsebene (`_contact`), die
  Vorauswahl rechnet je Netz in einem Zug (`evaluate_directions`), und die
  Suchen rufen `slice_body(..., with_layers=False)`.
- `SearchResult.transform` ist die ganze geprüfte Bewegung; `seed` bleibt
  lesbar und wirkt nicht auf die Auswahl.

## Der Schnitt

- **Material nach Umlaufrichtung**: Ab elf Ebenen gehen dichte, konsistente Netze zum Kernel-Job;
  `_solid_sections` prüft dort Volumenerhalt und schneidet mit `Manifold.slice`. Negative Komponenten
  nehmen den Segmentweg, der freie Schalen von Hohlräumen trennt. Sonst
  liefern Cython oder NumPy gerichtete Segmente; `_numpy_rings` ordnet
  Schalen nach Netzknoten wie Cython, auch an Rücklaufnähten. `CrossSection(Positive)`
  vereinigt ihre Materialflächen. `_cross_shape` ordnet Löcher über ihre
  ganze Fläche zu, auch bei Randberührung und Inseln im Loch.
  Freie inverse Schalen drehen samt eigenen Löchern; ihre Kanten-IDs fragen
  die Originaltopologie erst bei Bedarf. `_contact` reicht diese Herkunft
  und das Abbruchtoken intern weiter. Zweipunktzyklen entfallen in beiden Wegen.

- **`PLANE_SEGMENTS_API = 3`** verlangt der Ebenenschnitt vom übersetzten
  Teil: Material links am Segment, Abbruchrückruf und schreibbare Puffer;
  schreibgeschützte Ansichten werden vorher kopiert. Ein älterer Bau nimmt den
  NumPy-Weg, die nativen Vergleichstests nennen den nötigen Neubau.
- **Eine ungültige geschlossene Kontur** (eine Ebene durch die auslaufende Ecke
  eines Verbinders) bekommt `polygonize` mit den **ursprünglichen losen
  Segmenten**, nie über einen daraus gebauten `LinearRing` — dem fehlen die
  Knoten. Sich kreuzende Segmente werden vor `polygonize` an ihren
  Kreuzungen geteilt (`shapely.node`); sonst verschwindet ihre Fläche auch
  neben einem gültigen Nachbarring. Innenlöcher bleiben erhalten. Korpusfälle sind
  `dovetail_vertex_plane.ply` und `ambiguous_sphere_ribbon.stl` unter
  `tests/data/meshes/`; Schnitt- und Standtests halten beide Wege gleich.
- **`slice_body` und `cross_sections` nehmen optional einen `CancelToken`**:
  ohne ihn der native Weg ohne Python-Rückruf, mit ihm prüfen Cython-Kern,
  NumPy-Blöcke, Polygonaufbau, GEOS und Stützvolumen periodisch — bei
  gleicher Segmentfolge und gleichen Werten. Die Analysekarten reichen Abbruch
  und Budget über `solid_field` hinein; ein abgebrochenes Voxelfeld wird nicht
  veröffentlicht.
- **`slice_body(overhang_angle=…)`** bekommt den Winkel gegen die Senkrechte
  aus dem wirksamen Profil (`Profile.overhang_limit_degrees`: Probe, Drucker,
  Startregel), ohne Angabe die Startregel. Denselben Vertrag nutzen
  Analysekarten, Orientierungssuche samt Vorauswahl
  (`evaluate_directions(overhang_limit=)`), Agentenbericht und Übergabe;
  Messwerte fremder Düse oder fremden Rasters verwirft schon das Profil.
- **`slice_body(first_layer_height=…)`** setzt das Druckraster, ohne Angabe
  gilt das gleichmäßige Suchraster. Offene Brücken zählen nur zwischen
  beidseitigen Auflagern; ein seitlich ungestützter kurzer Querschnitt ist
  keine kürzere Brücke.

## Wo die Zeit hingeht

- **Gleiche Schicht, gleiche Zahlen**: `_measure_all` misst nur, was seiner
  Vorgängerin nicht gleicht (`_same_layer`: Fläche, Umfang, Hüllbox,
  kanonische Ecken); gleiche erben die Zahlen (`_repeated`).
- **Gestapelt statt je Schicht**: Arbeiter bekommen Blöcke von höchstens
  `BATCH_LAYERS`, `_measure_batch` stellt jede Frage als **einen**
  vektorisierten GEOS-Aufruf; die Einzelfunktionen (`_islands`,
  `minimum_width`, `_opening_loss`, `_survives_opening`) sind Blöcke aus einem
  Element. `_islands_many` baut den GEOS-Index der Vorgänger einmal.
  `FULL_WORKERS` steht bei sechs, die Messreihe an der Konstante.
- **Spannweiten ohne Overlay**: `_supported_span` bündelt gleiche Richtungen
  und schneidet als Abtastzeile in NumPy (`_cuts_along`, Paritätsregel).
- **Der Keil an jeder `TAPER_SAMPLE`. Schicht**, dazwischen fortgeschrieben;
  ein kürzerer Keil wird verfehlt oder fünffach gezählt (Test in
  `test_slice.py`).
- **Kleine Ringe** rechnet `largest_overhang_patch` mit `units.ring_area` in
  Python, ohne GEOS und NumPy; `_nested` bleibt für den Rückfall ohne
  widerspruchsfreie Richtung, gerichtete Ringe nutzen Clipper2.
- **Die Öffnung** (`_opening_loss`, `_protrusion`, `_minimum_widths`,
  `_halved`, `_width_outline`, `_canonical`) folgt der Regel „Die Öffnung
  zählt, was der Form fehlt“ in `schichtanalyse.md`.
- **Die Säulen**: `_support_volume` vereinigt Überhänge und zieht Material
  darunter als gerichtete `CrossSection` ab; jede Fläche wird einmal
  konvertiert, Zwischenkonturen bleiben in Clipper. Schichten und Summe
  laufen in fester Folge, mit Abbruchprüfung je Schicht. `_material_cross`
  orientiert vorhandene Außenringe und Löcher ohne Vereinfachung.
  `slice_body(support_volume=False)` lässt die Säulen aus (Druckvorschläge);
  der Druckdialog behält die Messung in der Sitzung
  (`Session.remember_analyses`).
- **Der Stützort auf Arbeitern** (`model_support`): Gruppen je Startschicht,
  eine Clipper-Säule je ursprünglichem Stück. Materialkonturen entstehen
  unter einem lokalen Schloss einmal je Schicht und werden unverändert
  geteilt; `findings._column_under` teilt sie innerhalb eines Befundlaufs.
  Standort, Inseln und Kanäle bleiben örtliche Fragen; deren GEOS-Öffnung
  (`_in_channels`) und der Kanalraum (`channel_space`) bleiben bestehen.

## G-Code und Verbrauch

- **Modell und Spülung sind getrennte Rollen.** `model_grams` verlangt
  vollständige Modellrollen und Werkzeugdaten; unbekannte oder bedingte
  Modellförderung verhindert eine vollständige Menge. `combine` summiert
  belegte Modellmassen ohne Werkzeugnummern verschiedener Platten zu mischen.
  Spülabschnittssummen bleiben bei ungeklärter Bilanz ausdrücklich unvollständig
  belegt; Gesamtverbrauch und Buchung übernehmen sie nicht. Explizite Modellzeit
  ersetzt keine Gesamtzeit; deren Differenz ist nur ein Zusatzanteil.
- **Stützmenge braucht vollständige Rollen.** Bedingte Stützextrusion oder eine
  unbekannte bewegte Druckrolle macht `support_mm3` unbekannt; gelesene
  Rollenanteile und Gesamtverbrauch bleiben erhalten. Auch die Gegenprobe
  verwirft unvollständige Stützmengen.
- **Modelllagen zählen physische Höhen.** `G92` verschiebt den Ursprung, nicht
  den Druckkopf. Höhe, Ursprung und Achsmodus werden getrennt verfolgt;
  bedingte Befehle können die Lagenzahl unbekannt machen, ohne eine belegte
  Modellmenge zu verwerfen. Relative Fahrten brauchen keinen bekannten Ursprung,
  absolute Fahrten schon. Später belegte Höhen ersetzen keine früheren
  unbekannten Druckhöhen.
- Warnungen vergleichen **ungekürzte** Materialvorgaben mit den Grenzen des
  Druckers — ein gedeckelter Sollwert beweist keine zu niedrige Temperatur.
- **`filament_mm_by_tool`, `filament_grams_by_tool`**: Index ist die
  Werkzeugnummer der Platte, samt Werkzeug 0, Nullen und `None` für
  Unbekanntes. Nur vollständige Listen ergeben eine Summe; eine ausgewiesene
  Gesamtsumme geht gerundeten Einzelwerten vor und füllt keine Lücken.
  `combine` verbindet Werkzeugnummern verschiedener Platten nicht.
- **`used_tools`** hält Wechsel mit tatsächlicher Extrusion fest; eine
  kommentarlose Gesamtlänge gehört dann nicht dem einzigen Modellfilament, und
  Einzelwerte werden nicht geraten.
- **`grams_by_tool`** wandelt nur mit belegter Dichte und belegtem Durchmesser
  je Werkzeug; der Dateikopf geht mitgegebenen Daten vor, `M200` liefert
  Volumen. Die Bilanz zählt Förderung auch stationär und bei `G0`; Rückzug
  bleibt je Werkzeug offen, ein Endrückzug senkt nichts; ein Wechsel zwischen
  linearer und volumetrischer Extrusion ohne belegten Durchmesser ist
  unbekannt. Reinigung und Leerfahrt bleiben von Druckbahnen, Modellgrenzen
  und Stützvolumen getrennt; Mengenheader haben Vorrang, Grammangaben gelten
  auch bei null. Eigene Ausgaben tragen `resolved_filament_grams` aus dem
  eingefrorenen Bedarf; `grams` nutzt ihn, spätere Dialogwerte nicht.
- **Bambu `T255`, `T1000`, `T1100` wechseln kein Filament** — bei belegter
  Bambu-Herkunft oder ihren Maschinenbefehlen, fremde Firmware erbt das nicht;
  komprimierte Kopfwerte folgen den einsbasierten Kennungen in
  `filament:`; Werkzeugnummern und Kopfkennungen werden vor der Allokation
  begrenzt.
- **`handover.off_the_bed`** prüft erst die Hüllbox, dann abbrechbar Geraden
  und Bögen, ohne Bahnen zu sammeln; Dateiangaben gehen dem Druckerprofil vor,
  Reinigung vor der ersten Modellschicht ist keine Modellbahn.
- **G-Code-Wörter brauchen keinen Leerraum**: `E` gilt auch direkt hinter einer
  Koordinate, und wissenschaftliche Zahlenschreibweise darf kein
  Extrusionswort verschlucken.
