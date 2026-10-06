---
description: "Funktionale Gruppen — eine Auskunft über Merkmale, kein Merkmal; gemeinsam ändern nur, wo Fenster und Operation dasselbe sagen"
paths:
  - "app/core/perceive/groups.py"
  - "app/core/geom/chamber_ops.py"
  - "app/core/geom/closure_ops.py"
---

# Regeln für funktionale Gruppen

Kammer, Nut, Kanal, Gewinde mit Einlauf, Bajonett und Rastung, Scharnier,
Steckaufnahme und Schrift (Dateiaudit §7, RM-184). Erkannt in
`perceive/groups.py`, gemeinsam geändert in `geom/chamber_ops.py` (Kammer,
Nut, Kanal) und `geom/closure_ops.py` (Spiel und Drehweg eines Verschlusses).
`schichtanalyse.md` gilt zusätzlich.

- **Eine Gruppe ist eine Auskunft, kein Merkmal**: Sie ändert weder Merkmale
  noch Kennungen (`test_groups_do_not_change_the_features`), und der Korpus
  bleibt ohne Verlust. Ein Merkmal steht in höchstens einer Gruppe,
  Bausteinmerkmale in keiner — sie stehen unter ihrem Schritt.
- **Belegt, nicht vermutet**: Eine Gruppenart braucht einen Nachweis aus
  Geometrie und Nachbarschaft, eine Gegenprobe, die ihr nur ähnlich sieht, und
  einen Fall aus dem Korpus (`tests/data/meshes/recognition_*`). Was nur ein
  Verdacht ist, heißt `suggested` und sagt es im Merkmalfenster.
- **Ob eine Gruppe sich als Ganzes ändern lässt, sagt ein Satz für beide**:
  `reason_against_group` sperrt die Zeile im Merkmalfenster und die
  Operation mit demselben Wortlaut — mit der Merkmalsliste, denn ob ein Kanal
  genau zwei ebene Wände hat (`trough_walls`), steht in den Merkmalen —, beim
  Verschluss je Feld `reason_against_play` und `reason_against_turn`, für
  Menü und Zeile zusammen `reason_against_closure_change`.
- **Eine Stellung ist ein Winkel mit verschieden gerichteten Flächen**: Ein
  Stück aus Flächen zählt nur, wenn der Kosinus zweier Normalen höchstens
  `STATION_FACES_APART` ist — zwei Facetten derselben Wand sind keine
  Nocke —, und runde Mulden übereinander am selben Winkel sind eine Stellung
  (`_notch_reach`). Sonst meldet der Korpus falsche Verschlüsse.
- **Gemerkt wird je Netz und Merkmalsliste** (`features.remembered`, geteilt):
  Baum, Merkmalfenster und Operation fragen dieselbe Antwort; gerechnet wird
  im Auswertungsarbeiter (`session._warm_metrics`).
- **Die Toleranz eines Verschlusses misst sich an seinem Rundkörper, nicht
  an der Platte** (`_closures`: `match_tolerance(2 · größter Radius)`): Auf
  einem Druckbett mit vielen Teilen fielen sonst Rastfedern nahe der Achse
  weg, und gestaffelte Klötze galten als ein Ring. Ein Teil auf der Platte
  bekommt dieselbe Gruppe wie allein
  (`test_a_print_plate_does_not_change_the_closures_of_its_parts`). Und er
  sitzt am Rundkörper: Was entlang der Achse weiter von ihm entfernt liegt
  als zwei Flächen einer Nocke voneinander (`_lumps`), gehört nicht dazu
  (`test_struts_far_along_the_axis_of_a_bore_are_no_closure`).
- **Je Körper einmal nachschlagen, je Boden nur den Bereich rechnen**
  (`groups._Lookup`): Eine Rechnung über alle Dreiecke je Kandidat kostete am
  Korpus Minuten. Eine Beschleunigung gibt dieselben Gruppen zurück wie vorher —
  verglichen an Korpusdateien, nicht behauptet.
- **Ein Verschluss ändert sich über Werkzeuge aus dem Umriss seiner Flanken,
  nicht über wandernde Ecken**: Ecken klappten am Filterkäfig ab einem halben
  Grad Drehweg Dreiecke um. Wo Material an eine Kante grenzt, gleitet die
  Ecke an dessen Fläche (`closure_ops._slides`), sonst schnitte das Werkzeug
  eine Kerbe in den Rundkörper unter einer Nocke; wo Luft dahinter liegt,
  reicht ein abziehendes hinaus; jedes beginnt um `BOOLEAN_OVERLAP` vor der
  Flanke. Spiel nur, wo jede Flanke ihr Gegenüber hat — sonst änderte es sich
  einseitig —, Drehweg nur an einem Anschlag (`closure_stops`); die Wirkung
  muss die Rechnung treffen (`VOLUME_SHARE`), sonst lief ein Werkzeug in eine
  Nachbarstellung.
