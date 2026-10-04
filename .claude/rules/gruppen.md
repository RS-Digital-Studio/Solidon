---
description: "Funktionale Gruppen — eine Auskunft über Merkmale, kein Merkmal; gemeinsam ändern nur, wo Fenster und Operation dasselbe sagen"
paths:
  - "app/core/perceive/groups.py"
  - "app/core/geom/chamber_ops.py"
---

# Regeln für funktionale Gruppen

Kammer, Nut, Kanal, Gewinde mit Einlauf, Bajonett und Rastung, Scharnier,
Steckaufnahme und Schrift (Dateiaudit §7, RM-184). Erkannt in
`perceive/groups.py`, gemeinsam geändert in `geom/chamber_ops.py`.
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
  Operation mit demselben Wortlaut.
- **Gemerkt wird je Netz und Merkmalsliste** (`features.remembered`, geteilt):
  Baum, Merkmalfenster und Operation fragen dieselbe Antwort; gerechnet wird
  im Auswertungsarbeiter (`session._warm_metrics`).
- **Je Körper einmal nachschlagen, je Boden nur den Bereich rechnen**
  (`groups._Lookup`): Eine Rechnung über alle Dreiecke je Kandidat kostete am
  Korpus Minuten. Eine Beschleunigung gibt dieselben Gruppen zurück wie vorher —
  verglichen an Korpusdateien, nicht behauptet.
