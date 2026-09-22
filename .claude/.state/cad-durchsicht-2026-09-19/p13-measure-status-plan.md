# P1.3 – Herkunft und Kennzeichnung von Maßen

Lesender Anschlussplan zum eingefrorenen Entwicklungsstand vom 20.09.2026.
Grundlage: Konzept §4.2 und §13.2/P1.3, Bauplan §§21–23, Regeln 6, 18, 20
und 21. Diese Notiz plant ausschließlich die Maßauskunft. Kollisionsrechnung
und deren Anschluss an Passungen, Auswertung und Export liegen bei Root.
Keine Produktdatei geändert, keine Tests ausgeführt.

## Entscheidung

Die gemeinsame Auskunft gehört an das vorhandene `Feature` in
`app/core/types.py`, unmittelbar neben `kind_of` und `is_a_cavity`.
Sie beschreibt die Quelle **des konkreten Parameterwerts**, nicht die
Herkunft des Merkmals. Eine reine Abfrage liest diese Auskunft für Baum,
Viewport, Maßeditor, Bohrhinweis und Steckbrief. Sie berechnet keinen Fit,
keine Fläche, keine Toleranz und keinen zweiten Zahlenwert.

Vorgeschlagener kleiner Vertrag: `Feature.measure_sources` als standardmäßig
leere Zuordnung von Parameternamen zu `native`, `facets`, `fit` oder
`parameter`; eine gemeinsame `measure_status(feature, name)`-Abfrage liefert
`exact`, `estimated` oder `unknown` einschließlich der Quelle für die
Erklärung. Die Werte bleiben ausschließlich in `Feature.params`. Eine
fehlende Quelle wird nicht aus `provenance`, ID, `recognised`, `created_by`
oder fehlendem `residual` ergänzt. Es entsteht weder eine zweite Maßklasse
mit eigenen Zahlen noch ein neues Modul.

| Belegte Quelle | Auskunft | Bedeutung für die Anzeige |
|---|---|---|
| `native` | exakt innerhalb des bestehenden Kernvertrags | Maß der analytischen Trägerfläche oder Integral der tatsächlich verwendeten nativen Fläche |
| `facets` | exakt am vorhandenen Dreiecksmodell | Beispielsweise die tatsächlich aufsummierte Fläche; kein analytischer Kreisdurchmesser und kein ursprüngliches Konstruktionsmaß |
| `fit` | geschätzt | Analytische Form aus dem Netz bestimmt; auch ein sehr kleiner Fitfehler belegt keinen ursprünglichen Nennwert |
| `parameter` | belegter Vorgabewert | Eindeutig aus Erzeuger-/Schrittparametern; im Kundenhaupttext „Vorgabemaß“, keine Zusage über das aktuelle Netz oder den Druck |
| keine/ungültige Quelle oder kein gültiger Wert | unbestimmt | „Maß nicht bestimmt“ bzw. „Maßherkunft nicht bestimmt“, niemals ersatzweise null |

`parameter` ist nur als Vorgabewert exakt. Der gemeinsame Rückgabevertrag muss
die Quelle erhalten, damit kein Leser daraus eine exakte aktuelle Oberfläche
behauptet. Zahl und Quelle werden auf vorhandenen fachlichen Grenzen geprüft;
etwa sind fehlender Durchmesser, NaN oder bool kein bestimmtes Durchmessermaß.
Eine gültige Nullposition bleibt dagegen null. Historische Tiefe 0 bedeutet
weiter „durchgehend“ und ist kein fehlendes Maß.

## Warum vorhandene Herkunftsfelder nicht genügen

- `types.py:268–325`: `kind_of(entry.mesh)` beantwortet die Körperart;
  `provenance`/`created_by` beantworten Erzeugung und Rückweg. `recognised`
  sagt, ob der Erkenner ein benanntes Merkmal wiederfindet. Keines dieser
  Felder beantwortet die Genauigkeit eines einzelnen Maßes.
- `brep/features.py:139–146` veröffentlicht native Merkmale mit
  `provenance="detected"`. Die Dreiecksnummern sind deren Auswahl im Viewport,
  kein Beleg einer Messung an Dreiecken.
- `brep/features.py:161–210` ist bewusst gemischt: Offene Langlöcher lesen
  den gemeinsamen Meshfit. Bei Restflächen ersetzen nur vollständige native
  Flächen die Meshfläche und deren Schwerpunkt durch native Integrale.
  Ein Körperetikett „B-Rep“ kann diese einzelnen Quellen nicht ersetzen.
- `scene/evaluate.py:1583–1614` hängt an deklarierte Bausteinmaße erkannte
  Dreiecksnummern. Das macht den ursprünglichen Vorgabewert nicht zum Fit.
  Umgekehrt übernimmt `evaluate.py:1915–1924` nach Neuerkennung die Herkunft
  `generated` für stabile Namen; die gerade gemessenen Werte bleiben Fits.
- `knowledge/parts/recipe.py:691–716` benennt vorhandene Ergebnisse um und
  setzt `generated`. Daraus darf keine neue Maßzusage entstehen. Ein im
  Rezept entstandenes natives Maß bleibt nativ, ein Meshfit bleibt geschätzt.

Die Quelle wird deshalb dort gesetzt, wo der konkrete Wert entsteht oder
nachgeführt wird. Vollständige native NURBS-Träger nutzen die bereits
bewiesene analytische Auskunft; die Anzeige führt keine neue NURBS-Probe aus.
Eine nur teilweise verwendete Restfläche wird nicht wegen ihres Trägerkörpers
als natives Integral ausgegeben. Offene P1.2-Maßfehler bleiben eigene
Korrekturen; eine Herkunftskennzeichnung ist kein Richtigkeitsnachweis.

## Verantwortungs- und Aufruferliste

| Ort | Kleinster nötiger Anschluss |
|---|---|
| `core/types.py:277` | Maßquellen am Feature und reine gemeinsame Statusabfrage. Nur vorhandene Werte lesen; unbekannte Herkunft bleibt unbekannt. |
| `core/perceive/features.py`, `slots.py`, `local.py` | Quellen beim Veröffentlichen der tatsächlich berechneten Werte setzen: Kreis-/Kegel-/Kugel-/Torusfit geschätzt, tatsächlich gemessene Facettenfläche gesondert. Lokale Nachmessung übernimmt ihre neue Quelle. |
| `core/brep/features.py:_describe`, `features_of` | Native Parameter und Integrale beim Lesen kennzeichnen; Mesh-Rückfälle einschließlich offener Langlöcher und unvollständiger Restflächen behalten deren Quelle. |
| `core/knowledge/parts/build.py` und tatsächliche spezielle Feature-Erzeuger | Nur ausdrücklich aus Eingabe-/Erzeugerwerten deklarierte Maße als Vorgabemaß kennzeichnen; Rezept-Umbenennung erhält die bestehende Quelle. |
| `core/perceive/matching.py:transformed_features`, `apply_mapping`; `core/scene/evaluate.py:_with_features`, `_carried_along` | Werte und Quellen zusammen führen. Bewiesene Ähnlichkeitstransformation erhält die Quelle; neue geometrische Messung ersetzt sie. Unbelegtes Maß nach nicht gleichförmiger Skalierung darf keine alte Quelle erben. ID-/Erzeugervererbung bleibt davon unabhängig. |
| `ui/labels.py:feature_measure`, `feature_label` | Eine gemeinsame Formatierung ergänzt geschätzte oder vorgegebene Werte; gleiche Maßauskunft liefert Tooltip, Statushinweis und zugänglichen Beschreibungstext. Mehrteilige Maße behandeln ihre einzelnen Quellen, statt ein unbekanntes Teilmaß mit einer Null zu füllen. |
| `ui/panels.py:ObjectTree`, `_feature_tip` | `SceneObject` liegt beim Aufbau bereits vor. Werte, Gruppierung, Tooltip beider Spalten, statusTip und AccessibleDescription benutzen dieselbe Auskunft. Die Körperart bleibt eine getrennte vorhandene Auskunft. |
| `ui/viewport.py:_redraw_features` | Nach `_shown_feature_body(entry)` das tatsächlich angezeigte Ergebnismerkmal beschriften. Kein Status aus dem ursprünglichen Objekt über einer geänderten Vorschau; keine neue Geometrie oder zusätzliche dauernde Überlagerung. |
| `ui/main_window.py:_show_feature_fields`, `_place_from_feature_panel`; `ui/panels.py:show_feature`, `measure_fields` | Maßquelle erhalten, bevor `as_mesh_data` den Träger für vorhandene Auswahl-/Beziehungsrechnung umwandelt. Die gemeinsame Feldfabrik schreibt einen Hinweis neben den gemessenen Ausgangswert, keine zweite Werteablage. |
| `core/perceive/actions.py:feature_value_source`, `bore_action`, `_saved_fields` | Vorhandene Feld→Feature-Maß-Zuordnung wiederverwenden. Ableitung oder Schemavorgabe wird dadurch noch kein gemessenes Zielmaß. Historische Bohr-/Bausteinfelder lesen weiterhin Originalwerte und nennen sie ausdrücklich. |
| `ui/placement_flow.py` | Vorbereitete Felder samt Auskunft anzeigen; Entwurf, interpretText, Vorschaupflicht, ✓/× und Begonnen-Zustand bleiben unverändert. Historischer Prefix und vollständiges Vorschauergebnis dürfen nicht dieselbe Messung vortäuschen. |
| `core/scene/placement.py:bore_advice` | Gemeinsamen Maßstatus als zusätzlichen fachlichen Eingang lesen. Geschätzte Maße begründen keine sichere Schraubengröße; vorhandene Normtabelle und Auswahlwege bleiben eine Quelle. Beide UI-Aufrufer in MainWindow und FeaturePanel reichen denselben Status durch. |
| `core/perceive/digest.py:_object_lines`, `_feature_line` | Dieselbe Kernabfrage, ohne UI-Import. Pro Maß „geschätzt“/„Vorgabemaß“; fehlende Werte nicht als Ø0 ausgeben. Vorhandene `fit.*`-Befunde im Steckbrief bleiben bestehen. |

Die verbleibenden `feature_label`-Aufrufer im Hauptfenster umfassen Auswahl-
und Passungsnamen, Kontaktanzeige und Merkmalsauswahl. Die Kennzeichnung
gehört daher in den gemeinsamen Helfer, nicht ausschließlich in den Baum.

## Speicherung, Undo und Zwillinge

- `scene/cache.py:ResultCache` hält vollständige `CachedResult`-/
  `SceneObject`-/`Feature`-Objekte. Die unveränderliche Quellenauskunft muss
  beim Kopieren erhalten bleiben; keine nachträgliche Mutation eines
  bereits gespeicherten Features.
- `DiskCache` serialisiert Features ausdrücklich über
  `_feature_to_data`/`_feature_from_data` (`cache.py:280–313`). Beide Seiten
  müssen die neue Zuordnung schreiben/lesen. Fehlendes Feld bedeutet
  unbekannt; bestehende Cacheversionsentwertung wird gemeinsam angehoben,
  damit alte Auskünfte nicht als aktuelle Erkennung gelten.
- **`MeshData.features_map` existiert im geprüften Baum nicht.**
  `geom/mesh.py:MeshData` trägt `raw`, `slots`, `cavity`;
  `MeshCodec`/`to_bytes`/`from_bytes` speichern Geometrie. Die Features liegen
  am `SceneObject` und im Cache-Metadatensatz. Keine zweite Kopie an MeshData
  einführen. Der bestehende Plattencodec unterstützt nur Netze; native
  Körper werden nach Öffnen neu ausgewertet.
- `History` speichert Operationen und deren Änderungen. Die tatsächliche
  Merkmalsübernahme geschieht bei `evaluate`/`matching`, nicht durch eine
  eigene Feature-Liste in History. Undo/Redo müssen Quelle und Werte aus
  demselben Auswertungsstand zurückbringen.
- `scene/serialise.py` speichert Dokumentparameter, Operationen, Verweise,
  Quellen und Transaktionen, keine Ergebnis-Feature-Instanzen. Allein für
  diese abgeleitete Auskunft ist kein Projektformatwechsel erforderlich.
  Wiederöffnung muss sie aus denselben Erzeuger-/Messwegen neu erzeugen.
  Etwaige spätere Aufnahme in ein persistiertes Benutzerformat müsste die
  normale Formatmigration durchlaufen; das ist hier nicht vorgesehen.
- Exakter Zwilling und Mesh-Zwilling können dieselbe Zahl mit unterschiedlicher
  Quelle haben. Tessellierung für Anzeige/Flächenwahl entwertet kein natives
  Maß. Eine tatsächliche B-Rep→Mesh-Operation mit anschließender Neuerkennung
  veröffentlicht dagegen die neue Mesh-Maßquelle. Ein erzeugtes Bauteil wird
  weder pauschal als Meshfit noch pauschal als exakte Oberfläche bezeichnet.

## Kundenformulierungen

Hauptwerte bleiben kurz. Alle Quellen sind deutsche `tr()`-Texte mit
vollständigen Sätzen und Platzhaltern; neue Quellen werden beim Umsetzen
gemeinsam in alle vorhandenen Kataloge übernommen.

| Ort / Zustand | Haupttext | Tooltip beziehungsweise Beschreibung |
|---|---|---|
| Analytischer Fit | `Ø 8,02 mm · geschätzt` | `Aus der vorhandenen Oberfläche geschätzt. Das ursprüngliche Konstruktionsmaß ist nicht bekannt.` |
| Native Messung | `Ø 8,00 mm` | `An der exakten Modellfläche bestimmt. Druckabweichungen und Passungsspiel sind darin nicht enthalten.` |
| Fläche aus Dreiecken | `124,50 mm²` | `Fläche des vorhandenen Dreiecksmodells. Eine gerundete Ursprungsfläche kann davon abweichen.` |
| Deklariertes oder gespeichertes Maß | `Ø 8,00 mm · Vorgabemaß` | `Wert aus dem erzeugenden Schritt. Die vorhandene Oberfläche kann davon abweichen.` |
| Kein Maßwert | `Maß nicht bestimmt` | `Dieses Maß ist nicht zuverlässig bestimmt. Einen Zielwert eingeben oder einen geeigneten Bezug wählen.` |
| Wert ohne Herkunftsbeleg | `{measure} · Maßherkunft nicht bestimmt` | `Für diesen Wert ist nicht belegt, wie er bestimmt wurde. Er wird deshalb nicht als exaktes Maß ausgegeben.` |
| Maßeditor, aktueller Ausgangswert | `Aktuell: {measure} · geschätzt` | Derselbe Fit-Tooltip; der editierbare Zielwert erhält kein „geschätzt“. |
| Historischer Maßeditor | `Vorgabemaß` | Vorhandenen Satz weiterverwenden: `Zeigt die ursprünglichen Schrittwerte vor späteren Größen- und Lageänderungen. Tiefe 0 bohrt durch das ganze Teil.` |
| Fit ohne belegte Schraubengröße | `Diese Bohrung misst geschätzt {measure} mm. Eine passende Schraubengröße ist damit nicht sicher bestimmt.` | Vorhandene Größenwahl bzw. `Selbst eintragen`; kein neuer Bestätigungsdialog. |
| Bekannte Unsicherheit aus Facetten | `Das geschätzte Maß allein belegt die Passung nicht.` | `Die vorhandenen Flächen können enger liegen. Die Verbindung in Einbaulage prüfen oder eine genauer aufgelöste Datei verwenden.` |

Bei unbekannter Maßherkunft reicht keine bloße Zahl ohne Zusatz. Bei normalen
exakten Werten ist kein zusätzliches dauerhaftes Badge nötig. Der Text dient
zugleich als zweite Kodierung und als zugängliche Beschreibung; Farbe allein
trägt keine Aussage.

`fit_error` ist der gemessene Konturfehler, `radial_min`/`radial_max` sind das
tatsächliche Facettenband, `residual` ist dimensionslos. Keiner dieser Werte
ist eine Nennmaßunsicherheit oder eine Fertigungstoleranz. Deshalb kein
erfundenes „±… mm“, kein Prozentvertrauen und kein Runden auf eine Normgröße.
Details werden nur angezeigt, wenn der vorhandene Erzeuger sie tatsächlich
ermittelt hat. Die gemeinsame Quelle für eine Passungsbewertung bleibt
`fits.check`; der Tooltip führt keine zweite Freigaberechnung ein.

## Geplante Gegenfälle, jetzt nicht ausgeführt

Kernfälle in bestehenden `test_features.py`, `test_brep_surfaces.py`,
`test_matching.py`, `test_cache.py` und `test_digest_and_fits.py`:
native Bohrung mit `detected`; nativer NURBS-Zwilling; vollständige native
Restfläche versus Mesh-Teilfläche; offenes Langloch am Solid mit Fitmaß;
echtes deklariertes Bausteinmaß; später neu gemessenes `generated`-Merkmal;
Rezeptumbenennung; fehlender Wert/Quelle; starre und gleichförmige sowie
nicht gleichförmige Transformation; Qualitätswechsel; warmer und kalter
Cache, Undo/Redo und Projektwiederöffnung. Erwartete Zahlen bleiben
unabhängig vorgegeben, Status wird nicht aus dem Produktresultat hergeleitet.

Fensterfälle ausschließlich beim Release in bestehenden
`test_value_labels.py`, `test_feature_panel.py`, `test_feature_label_layout.py`,
`test_ui.py`, `test_surface_placement_ui.py` und
`test_viewport_decisions.py`: identische Texte in Baum/Tooltip/Viewport/Karte;
tatsächlicher Vorschaukörper; Panel geschlossen bei aktivem Maßentwurf;
historischer Bohrschritt mit späterer Größenänderung; gemessener Ausgangswert
neben bewusst eingegebenem Zielwert; Gruppen mit unterschiedlich belegten
Maßen; Einheitenwechsel und zugängliche Beschreibung. Keine Fenster- oder
Leistungsprüfung wurde für diese Planung gestartet.
