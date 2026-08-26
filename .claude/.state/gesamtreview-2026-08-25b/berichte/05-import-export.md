# Gebietsbericht: Import und Export (`app/core/ingest/`, `app/core/export/`, `units.py`)

Baseline grün (176 + 149 passed). Skripte unter `review-io\`.

## Hoch

### H1 [hoch] „Auf diese Breite skalieren" misst die falsche Zeichnung — VERIFIZIERT
`ingest/outline.py:147-149` — `path.bounds` umfasst alle Entitäten, der Körper entsteht nur aus geschlossenen Ringen; Mittellinie/Maßlinie/Rahmen/Hilfslinie geht in den Maßstab ein, ohne im Körper zu stehen (bei DXF der Normalfall). Gemessen: Quadrat 10 mm + offene Linie über 100, `width=50` → Körper 5×5 statt 50×50 (zehnfach falsch); `ingest.extruded` meldet `drawn_width=100` und bestätigt den Fehler. **Fix:** `actual` aus den Grenzen der `polygons` bilden, `OutlineResult.width` aus derselben Quelle.

### H2 [hoch] Zwei Objekte, ein Namensschema ohne `{index}`: eine Datei, zwei Erfolgsmeldungen — VERIFIZIERT
`export/writer.py:208-243` (`_entries_for`), `:583-590` — `plan_export(..., scheme=...)` bildet Namen ohne Kollisionsprüfung, `write_plan` überschreibt gleiche Namen und meldet beide als geschrieben. Gemessen (zwei Objekte „Halterung", `--scheme "{project}_{object}"`): eine Datei im Ordner, zweimal „Geschrieben", Exit 0, das kleine Teil weg. `safe_name` kann zwei Namen zusammenfallen lassen. Zweiter Kopf: `skipped` als Dateinamensliste (`:576-580`) lässt beim STEP-Export den exakten Körper mit herausfallen. **Fix:** in `_entries_for` auf Doppelte prüfen (`ValidationError` mit `{index}` oder durchnummerieren wie `threemf._numbered`); `skipped` auf `object_id`.

## Mittel
- **M2** Eine mehrfarbige Platte reist mit genau einem Filament (`writer.py:788`, `handover.py:724-817`); `project_settings(..., extruders)` nie übergeben, und `_orca_filament` macht jeden Wert schon zur Ein-Element-Liste → Bedingung `not isinstance(list)` immer falsch. Gemessen: 3 Farben in der Geometrie, 1 Filament + eine Slotfarbe in den Einstellungen. Die Slicen-Kette hat es behoben (`SlicerConfig.filaments`), die Export-Kette nicht. Test (`test_print_settings.py:1875`) prüft den einen Schlüssel, den die Bedingung nicht trifft (Sollwert aus dem Prüfling). Fix: Slots durchreichen, je Slot `_orca_filament(..., slot=...)`.
- **M3** Wer PrusaSlicer eingerichtet hat, exportiert eine 3MF ohne jede Einstellung (`writer.py:666-763`, `flavour` und `setup` unabhängig; `_assembly()` in `main_window.py:572-580` ohne `flavour=`). Gemessen: eingerichteter Slicer → nur `model_settings.config`; kein Slicer → auch `project_settings.config`. Wer einrichtet, bekommt die schlechtere Datei. Fix: `write_assembly` leitet `flavour` aus `setup.flavour` ab.
- **M4** Ein negativer Eckpunktindex in einer 3MF wird zu stiller Falschgeometrie (`threemf.py:730`, nur Obergrenze geprüft; numpy schlägt negativ um). Gemessen: Volumen −1000, offen, Hüllquader stimmt. Fix: `faces.min() < 0` mitprüfen.
- **M5** `count_objects` baut den ganzen Baum, im Hauptthread, und danach noch einmal (`threemf.py:485-494`, `plan.py:90`; `ET.fromstring` statt Streaming). Gemessen: 1 Mio Dreiecke → 6,9 s / 1,18 GB nur für die Zahl 1, unter `waiting()` ohne Abbrechen (§2.8). Fix: `ET.iterparse` mit `clear()`, `mesh`-Teilbäume überspringen.
- **M6** Die entpackte Grenze hält den Speicherüberlauf nicht auf (`ingest/loader.py:40,143-167`; Spitzenspeicher ≈ 12× entpackte XML). Gemessen: 97 MB entpackt → 1,18 GB; hochgerechnet auf die 512-MiB-Grenze ~6,5 GB; `MAX_TRIANGLES` greift erst nach dem Parsen. Prüfung selbst richtig gebaut (lügendes Zip → `BadZipFile`), nur die Höhe trägt nicht. Fix: kleinere Grenze aus dem Faktor oder Dreiecke beim Streamen zählen.
- **M7** Die Größengrenze steht nur für 3MF vor der Operation (`plan.py:88-89`, `check_limits`/`check_unpacked` im `.3mf`-Zweig). Gemessen: zu große STL/OBJ/STEP/SVG/PLY werden angenommen, scheitern erst bei der Auswertung, die Quelle wandert in die Projektdatei. Fix: `check_limits` aus dem Zweig herausziehen.
- **M8** Der Satz für die Modellseite erreicht nie den Fall, für den er geschrieben wurde (`fetch.py:156-157`; `_name_from` wirft vor `_reject_web_page`). Gemessen: Seitenadresse ohne Endung → `unknown_format` statt „Unter dieser Adresse steht eine Webseite …". Fix: `_reject_web_page` vor `_name_from`.

## Gering
- **G1** Verweis auf `_cura_rated`, das es nie gab (`handover.py:81`, `dateiformat.md:115`; heißt `_cura_computed`). Umbenennen.
- **G2** Ein einzeln exportierter Körper verliert seinen Namen (`threemf.py:1136-1140` vs `:1052-1062`; `_model_xml` setzt keinen Objektnamen). CLI-Weg → „Object 1"/„Körper 2". Zwilling in derselben Datei.
- **G3** Eine Cura-Ableitung ist nicht die Formel aus der Definition (`handover.py:435`; `meshfix_maximum_travel_resolution` ohne Geschwindigkeitsverhältnis). Gemessen: 0,5 statt 0,84. Von 224 Schlüsseln der einzige unbeabsichtigte. Formel ausschreiben.
- **G4** Ein asymmetrischer Umriss landet nicht mittig (`outline.py:159`, Volumenschwerpunkt statt Hüllquadermitte). L-Profil → `-13,72…26,28`. Fix: `bounds.mean(axis=0)`.
- **G5** Die Einheitenfrage zeigt Zahlen mit Punkt (`ingest/ops.py:393-397`, `dialogs.py:59`; `AskDialog` reicht den Text roh in `QLabel`). Fix: durch `labels.localised`.

## Geprüft und in Ordnung
Einheitenheuristik (genau eine Lesart gewinnt, jede Mehrdeutigkeit an `ctx.ask`, gemessene Einheit immer in der Auswahl); 3MF-Baugruppe Roundtrip verlustfrei (Slots, Farben, Namen, Transformationen); Zip-Sicherheit (Grenze vor dem Parsen, lügendes Zip → `BadZipFile`, XML-Bombe von expat abgefangen, kein Traversal, kein `extractall`); Exportgenauigkeit (6,3·10⁻⁶ mm über STL/3MF/OBJ/PLY); Dateinamen (Transliteration, CJK/Kyrillisch bleiben, Sonderzeichen weg); `slicer_keys` beidseitig (224 Cura-Schlüssel in `fdmprinter.def.json`, alle Aufzählungswerte gültig, 56/57 Orca im ElegooSlicer); `handover`-Fehlerpfade (jede Ausnahme mit Vorschlag, kein `shell=True`, feste Argumentliste); Regel 12 (keine absoluten Pfade); `units.py` (Nachkommastellen, `quantize`, Toleranzskalierung §11.2).

**Kann das so rein: nein** — H1 (zehnfach falsch skaliert) und H2 (stiller Dateiverlust); M2–M8 unmittelbar danach.
