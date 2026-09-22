# P1.6 – veröffentlichte Teilträger und ihre Originalhaut

## Umgesetzter Umfang

Eigener Produktstand eingefroren nach gezielter Prüfung. Keine Commits,
Veröffentlichung, Fensterdateien oder Leistungsprüfungen durch diesen Agenten.

Neue Dateien:

- `app/core/perceive/surfaces.py`
- `tests/test_surface_patches.py`

Bestehende Dateien dieses Anteils:

- `app/core/perceive/features.py`
- `app/core/perceive/slots.py`
- `app/core/perceive/local.py`
- `app/core/perceive/matching.py`
- `app/core/geom/transform.py`
- `app/core/perceive/CLAUDE.md`
- `app/core/geom/CLAUDE.md`

Datensatz, native Hersteller, Ergebnis-/Plattencache, Auswertung, weitere
Ebenenhersteller, Kartenrechnung und Oberfläche gehören den anderen Anteilen.

## Gemeinsame Auskünfte

`surfaces` prüft den vereinbarten Zahlenvertrag, Originalindizes und optional
ihre Zugehörigkeit. `planar_patch` prüft alle Originalecken gegen die bereits
gewählte Ebene mit `EPS_GEOM`; es gibt keine zusätzliche Einpassung.
`clipped_patches` beschränkt wirkliche Teilmengen; `reindexed_patches` folgt
der belegten Reihenfolge des Ausschnitts. NumPy-Indizes werden beim Erzeugen
in gewöhnliche speicherbare Ganzzahlen übernommen, ungültige Indizes nicht
zurechtgebogen. Alle öffentlichen Helfer nehmen `check_cancelled` an.

`transformed_patches` erhält Ebenen bei invertierbaren affinen Abbildungen,
alle Rundträger bei Ähnlichkeiten sowie Zylinder/Kegel bei belegter radialer
Gleichheit und orthogonaler Achse. Der bestehende Nachweis liegt gemeinsam in
`radial_scales`; keine neue Formerkennung. Ebenennormalen folgen der invers
transponierten Matrix, Kegelspitzen und gerichtete Nappen der tatsächlichen
Abbildung. `matching` bewegt die Träger genau einmal. Der native Objektweg
ordnet die ursprünglichen Faces vorab auf die neue Tessellierung ab.
Ein unbelegter Ausschnitt einer nativen Fläche wird als Träger verworfen.

Die Rundhersteller publizieren ausschließlich ihre endgültig akzeptierten
Fitwerte. Langlöcher behalten getrennte Bögen, nachgewiesene Flanken und
angehängte Kegelfasen. Der Stadionzweig zerlegt seinen vorhandenen Fit, der
offene Weg übernimmt während der Flutung tatsächlich geprüfte Bogenfacetten.
Innenräume übernehmen ihre Träger aus dem unveränderten Eingangsbestand,
damit eine frühere semantische Löschung keine spätere Kammer beraubt.
Die Erkennungskosten zählen zusätzlich alle gespeicherten Trägerindizes.

## Fachliche Grenzen, ausdrücklich geprüft

- Ein kurzer realer Stadionfit hat im Gegenfall R6,0052037159 und eine um
  etwa 2,335° gedrehte Richtung gegenüber dem konstruierten R6-Stadion. Diese
  tatsächliche Fitlösung bleibt erhalten. Nahtüberspannende Dreiecke werden
  nicht einem näheren Träger zugeschlagen. Der unabhängig richtig
  parametrisierte Stadiongegenfall deckt dagegen die ganze Mantelhaut.
- Im Zweibogenweg gehörten einzelne Übergangsdreiecke zu keinem akzeptierten
  Bogenfit. Nachgewiesene Flanken werden übernommen; übrige Dreiecke bleiben
  unbekannt. Zwei angenommene Radien von 6 und 6,024 bleiben getrennte Träger,
  während die unveränderte semantische Langlochbreite weiterhin 12 ist.
- Die lokale Suche passt nur die angeklickte Zusammenhangskomponente ein.
  Eine getrennte Kugelinsel wird als vollständige Luftgrenze erkannt, bekommt
  dadurch jedoch keinen ungeprüften Kugelträger. Global wird dieselbe Insel
  vollständig als Kugel belegt. Es wird kein Suchgebiet erweitert oder ein
  zweiter Fit gestartet.
- Kartenrechnung und Fertigungsaussage sind hier nicht implementiert. Ein
  Fitträger behauptet weder Ursprungsmaß noch Hautabweichung null.

## Nachweise

Protokollverzeichnis:
`C:/Users/rober/AppData/Local/Temp/solidon-p16-carriers-78d314dd030946bf97d00b00222cdd94`

- `helpers-before.txt`: 28 rote neue Vertragsfälle vor dem gemeinsamen Helfer.
- `publishers-before.txt`: 8 rote echte Veröffentlichungs-/Zusammensetzungsfälle,
  29 vorhandene Helferfälle grün.
- `two-voids-before.txt`: reproduzierbar verlorener kleiner Trägeranteil nach
  semantischer Löschung durch die erste Kammer. Gezielt vorwärts korrigiert.
- `carrier-consumers.txt`: **854 passed, Exit 0**, 503,27 s. Vor dem letzten
  Zwei-Kammer-Schritt, einschließlich ursprünglicher Erkennung, Bohrungsboden/
  Mündung, lokaler Suche, Langlochbearbeitung, Transform/Matching und Rundmaßen.
- `carrier-final-core.txt`: **90 passed, 375 deselected, Exit 0**, 14,09 s.
  Nach dem Zwei-Kammer-Schritt: alle damals 51 eigenen Trägerfälle und
  bestehende Mesh-/native/lokale Innenraumfälle.
- `carrier-final-own.txt`: **52 passed, Exit 0**, 1,59 s; endgültige eigene
  Datei einschließlich zusätzlicher schiefer Ebene unter Scherung/Spiegelung.
- `carrier-final-ruff.txt`: **Exit 0** für sechs Produktmodule und neue Testdatei.
- `carrier-final-format.txt`: **Exit 0**, sieben Dateien unverändert formatiert.
- `carrier-final-mypy.txt`: **Exit 0**, sechs Produktmodule im vollständigen Importgraphen.
- `carrier-final-diff-check.txt`: **Exit 0**.

Die Läufe gingen über `tools/affected_tests.py --run`. Die abhängigen ganzen
Fensterdateien `test_local_recognition_flow.py`, `test_local_recognition_ui.py`
und `test_ui.py` wurden ausdrücklich zurückgestellt und nicht ausgeführt.
Alle roten Zwischenprotokolle bleiben erhalten. Ein vollständiges
Entwicklungstor und die spätere Release-Abnahme bleiben beim Root.
