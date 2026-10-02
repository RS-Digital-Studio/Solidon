# Remote-Review 48106 — Geometrie und Dateiformat

Fester Prüfling: `4cf460e87f8d93e2d950602c9fe25ce34e6b5eb9` → `48106c57afadaa67c9e07d33a944a6c988c2bc70`. Beim ersten Lesen war origin/main bereits `f781e1e8956c5e3d8f5dbab11df839c88aa3c644`; dieser spätere Stand ist ausdrücklich nicht Teil dieser Prüfung.

**Ergebnis: drei neue P2-Befunde, keine Freigabe dieser Geometrieeinheit.** Die 15 zugewiesenen Pfade wurden vollständig im Diff gelesen, einschließlich bestehender Verträge, Tests und realer Verbraucher.

## S01 — P2: Der neue Auswahlentscheid zerstört die Spiegelsymmetrie im Überlappungsbereich

**Ort:** `app/core/geom/sculpt.py:279` (Anschlusszeilen: 207, 211, 218, 283, 289, 326).

_strongest_copy wählt bei gleichem Gewicht nach owner, also stets die ursprüngliche Kopie. An einem Eckpunkt auf der Symmetrieebene sind die Abstände beider Pinselzentren gleich. Enthält die Strichrichtung eine Komponente quer zur Ebene, wird diese Komponente deshalb nicht ausgeglichen: der Ebenenpunkt verlässt die Ebene.

**Auslöser:** Echter stroke_at-Aufruf auf einer symmetrischen Kugel R20 am Punkt (5,328094023; 0; 19,277225269), Richtung aus der wirklichen Eckpunktnormale (0,267993231; ungefähr 0; 0,963420795), draw, Symmetrie X, Radius 16 mm, Stärke 1 mm. Anschließend dieselbe serialisierte Strichliste über die registrierte sculpt_strokes-Operation auswerten.

**Nachweis:** Kugel mit 642 Eckpunkten/1.280 Dreiecken; mittlere Kantenlänge 3,01305 mm. Ausgangsnetz, alte Semantik und Front-only ohne den neuen Selektor haben 0 Spiegelabweichung. Aktuell: 0,341167593 mm Abweichung zu den spiegelbildlich zugeordneten Eckpunkten; Punkte der Ebene wandern um 0,170583797 mm seitlich. Wasserdicht; allein sculpt.applied, kein Grobnetz-Hinweis. Probe Exit 0.

**Vorher/Nachher:** Die Abweichung entsteht durch den neuen mirror_once-Selektor. Der Gegenlauf mit front_only=True und mirror_once=False bleibt symmetrisch; die neue Vorderseitenfilterung ist nicht die Ursache.

**Vertrag / Fix:** Symmetrieparameter und _mirrored spiegeln Punkt und Richtung; die Auswahl muss deren Geometriesymmetrie erhalten. RM378 verlangt eine begrenzte Stärke bei überlappenden Kopien für alle Achsen und Pinsel. Überlappende Wirkungen unter Erhalt der gespiegelten Richtungen auf die gewünschte Stärke begrenzen; Gleichstände an der Ebene dürfen keine willkürliche Seitenrichtung gewinnen. Gegenfall mit einem schrägen Zug neben der Ebene aufnehmen.

**Grenze:** Keine native Bedien- oder Exportprobe; verwendet wurden der echte stroke_at-Helfer der Oberfläche und die echte registrierte Kernoperation. Die erste Radius-6-Probe hatte zusätzlich sculpt.too_coarse und bleibt als Vorstufe erhalten; maßgeblich ist der gesonderte Radius-16-Nachlauf ohne diesen Hinweis.

Rohbeleg: `remote-48106-spiegel-probe.json#probes.S01`.

## B01 — P2: Der neue Entwurfshinweis verspricht eine feine Ausgabe, die der Exportweg nicht herstellt

**Ort:** `app/core/geom/blend.py:437` (Anschlusszeilen: 405, 433, 441).

blend.draft sagt, Export und Druckvorbereitung rechneten fein. MainWindow._start_export:7821–7870 übernimmt jedoch die Objekte aus session.last_result in _ExportWorker. check_before_export prüft sie; plan_export/_entries_for übernimmt mesh_for_export(entry.mesh). Der Schreiber gibt ein bereits vorhandenes Netz unverändert zurück (writer.py:1034–1035). Eine feine Stack-Auswertung ist in diesem Pfad nicht angeschlossen.

**Auslöser:** Zwei Quader 20×20×20 mm, zweiter um 5 mm entlang X versetzt; Weich verschmelzen mit Radius 2 mm und Rasterweite 0,4 mm in draft. Den daraus gebauten Körper über den vom Fenster verwendeten Kernpfad plan_export planen.

**Nachweis:** Entwurfsraster 0,8 mm, 9.076 Dreiecke und blend.draft. Ein gesonderter echter fine-Lauf derselben Eingaben hat 36.684 Dreiecke. Der Exportplan enthält exakt dasselbe MeshData-Objekt und dieselben Eckpunkte wie der Entwurf, weiterhin 9.076 Dreiecke. Probe Exit 0; keine Datei geschrieben.

**Vorher/Nachher:** Die direkte Übernahme von session.last_result ist älter. Neu in dieser Einheit ist die unzutreffende Zusage, die gröbere Auflösung werde beim Export automatisch durch eine feine ersetzt. Daher kein neu eingeführter Geometriefehler des Schreibers behauptet.

**Vertrag / Fix:** Neuer blend.draft-Text sowie der gelesene RM379-Ablauf versprechen ausdrücklich den feinen Export. Der registrierte Feinweg selbst ist vorhanden und rechnet korrekt mit params.grid; der UI-Anschluss fehlt. Vor der Ausgabe denselben Dokumentstand vollständig in fine auswerten und die daraus stammenden Objekte verwenden, bevor die neue Zusage erscheint. Falls diese Anschlussarbeit getrennt bleibt, darf der neue Text die noch fehlende Neuberechnung nicht zusagen.

**Grenze:** Der echte Fensteraufrufer wurde vollständig als Quelle verfolgt, aber kein Fenster gestartet. Die Probe verwendet die reale Kernoperation und Exportplanung; checked=[] entspricht dem vorhandenen bereits-geprüften Planweg. Kein nativer Datei-/Slicer-Endlauf. Der Druckanalyseanschluss arbeitet ebenfalls am gelieferten result; der bestätigte Befund benötigt bereits den Exportweg allein.

Rohbeleg: `remote-48106-geometrie-proben.json#probes.B01`.

## B02 — P2: Das neue Entwurfsbudget greift vor der Eingangsprüfung auf ein leeres Netz zu

**Ort:** `app/core/geom/blend.py:260` (Anschlusszeilen: 274, 298, 405).

blend_union ruft im Entwurf jetzt draft_grid vor blend_bodies auf. _grid indiziert first.raw.bounds; bei einem Netz ohne Flächen ist bounds=None. So erreicht der Aufruf die vorhandene NotManifoldError-Prüfung nicht mehr.

**Auslöser:** Den registrierten blend_union-Aufruf mit einem leeren MeshData und einem gültigen 10-mm-Quader, Radius 2 mm und Raster 1 mm einmal in draft und einmal in fine aufrufen.

**Nachweis:** draft: TypeError mit NoneType is not subscriptable, ohne eigene Handlungsvorschläge. fine: NotManifoldError mit Reparaturhinweis und repair_and_retry/show_locations/cancel. Beide Ausgänge im Rohbeleg, Probeskript Exit 0. evaluate.py:884–913 würde den neuen TypeError als InternalError melden, statt den fachlichen Eingabefehler weiterzugeben.

**Vorher/Nachher:** Vor dem Diff berechnete blend_union die Rasterweite rein numerisch und rief danach blend_bodies auf; dessen erste Schleife lehnte dieses Netz fachlich ab. Erst der neue vorgezogene _grid-Aufruf überspringt diesen vorhandenen Fehlerweg.

**Vertrag / Fix:** Die bestehende blend_bodies-Eingangsprüfung und Regel 17 geben für Körper ohne Volumen einen Reparaturweg. Ein Budgetentscheid darf diese Fehlerklassifikation nicht umgehen. Die gemeinsame Körperprüfung vor der Bounds-/Budgetermittlung ausführen und ihren bestehenden fachlichen Fehler erhalten. Leere Eingänge in beiden Qualitätsstufen als Regression prüfen.

**Grenze:** Direkter registrierter Op-Aufruf mit gezielt ungültigem Eingang. Ein konkreter nativer Kundenweg, der dieses leere Szenenobjekt erzeugt, wurde nicht nachgewiesen. Es ist ein bestätigter neuer Kern-Fehlerpfad, keine Behauptung über einen häufigen Bedienfall.

Rohbeleg: `remote-48106-geometrie-proben.json#probes.B02`.

## Migration, Cache und bestehende Befunde

Format40→41 setzt front_only/mirror_once per setdefault auf False in ops und beiden edited_ops-Seiten. Alte Werte bleiben, neue Schritte verwenden True; verborgene Dialogfelder werden weiterhin eingesammelt. Projektcontainer enthalten nur Daten und relative Quellen. Eigene komplette Undo/Redo-/Save/Open-Kernprobe wurde nicht ausgeführt. Der neue Test prüft den alten Unterkantenwert −0,498 mm und den Wechsel auf 0 mm; die darin enthaltene Spiegelwirkung wird nicht separat numerisch nachgewiesen. Die v40-Datei hat keine edited_ops-Historie; beide Seiten sind hier quellengeprüft.

Aufgelöste Parameter und quality stehen im operation_hash. Vorige Build-/Releasegeneration wird durch results_cache_dir getrennt; fehlende lokale Cacheversion allein ist kein bestätigter Cachebefund. Neue Formvorschauen und neue Op-Aufträge teilen die True-Vorgaben; migrierte ältere Schritte rechnen über den registrierten Pfad mit ihren False-Markern.

- **G01:** Auswahl der 256 stärksten Abträge jetzt sculpt.py:961 unverändert. Front-only behebt diese Auswahlannahme nicht; keine erneute Messung des ursprünglichen Zwei-Zonen-Falls am neuen Stand.

- **G02:** Befundfilter und Code-Lebenszyklus unverändert. Front-only verändert die Wandgeometrie, daher gelten die alten Zahlen 0,74→2,960 mm und Faktor 4 nur für den alten Reproduktionsstand; nicht als neuer Heilnachweis übernommen.

- **G03:** Baustein-Randtest ist außerhalb des neuen Diffs; der alte zugeordnete Befund wird nicht doppelt gezählt.


## Grenzen und Performancequellen

Alle fünf neuen Schlüssel sind in en/es/fr/it/pt vorhanden; sie enthalten keine Platzhalter. Die neue Parameterzählung steigt passend um zwei interne Boolesche Felder. Die ZIP-Container wurden als Daten gelesen; die Format-41-Beispieldatei ist wie ihr Vorgänger eine Serialisierungsfixture, kein Geometrienachweis.

- Neuer Spiegelabgleich sortiert je Strich über bis zu acht Kopien (O(k log k), zusätzliche Index-/Gewichtsarrays). Auf dem direkten Netz-Vorschauweg geschieht apply_strokes im UI-Aufrufer; keine neue Zeitüberschreitung behauptet oder gemessen.

- Blend unter dem Punktbudget verwendet bis zu ungefähr achtmal so viele Rasterpunkte wie zuvor im Entwurf und eine feinere Oberflächenwolke. Der Grenzwert begrenzt Rasterpunkte, keine Eingangsnetzgröße. Abbruch des Feldlaufs bleibt blockweise vorhanden; neue Rasterberechnung selbst ist nur dreidimensional. Native Leistungsabnahme bleibt Release.


## Wirklich ausgeführt

Drei ausdrücklich erlaubte enge Diagnosefälle auf QA `48106c57a`, danach ausschließlich S01 mit ausreichend großem Pinsel nachgeschärft: **beide Skripte Exit 0**. Kein Pytest-Lauf und kein Entwicklungstor. Die fünf maßgeblichen Quellen waren vor und nach beiden Läufen bytegleich zum festen Commit und blieben unverändert. Der unabhängige IT-Katalogwert des QA wurde nicht berührt oder bewertet.

Probeskripte, vollständige JSON-Ausgänge, Logs und echte Exitcodes: `remote-48106-geometrie-proben.*` und `remote-48106-spiegel-probe.*`. Hashes, Regelabgleich und Metadaten stehen in `remote-48106-geometrie.json`; der Quellnachweis liegt unter `remote-48106-geometrie-quellen/manifest.json`. Nutzerprofile wurden isoliert, Bytecode-Schreiben war aus.

## Vollständig gelesene Änderungsauswahl

- `.claude/rules/oberflaeche.md`

- `app/core/geom/blend.py`

- `app/core/geom/sculpt.py`

- `app/core/scene/migrations.py`

- `tests/data/README.md`

- `tests/data/projects/example_v41.p3d`

- `tests/data/projects/sculpt_brush_v40.p3d`

- `tests/test_blend.py`

- `tests/test_sculpt.py`

- `tests/test_project.py`

- `app/i18n/locales/en.json`

- `app/i18n/locales/es.json`

- `app/i18n/locales/fr.json`

- `app/i18n/locales/it.json`

- `app/i18n/locales/pt.json`


Karten und Regeln wurden entlang Root → app/core/geom, scene, ui und tests mitgelesen; Regelcheck/Geometry-Review angewandt. Die anschließenden UI-, Export- und History-Verbraucher sind Kontext, keine Freigabe anderer geänderter Einheiten.

**Kann das so rein? Nein — S01 und B01 sind kundenwirksame Nachgänge; B02 ist ein zusätzlicher bestätigter Kern-Fehlerpfad.**
