# Paket stapel — Schlussbericht (RM-209, RM-132, RM-193)

Zweig `rm-209-stapel` (gepusht), Arbeitsbaum `wt-stapel`, Basis `aa82afdff`.
Commits: `53813ec61` (Stapel), `8e1afee29` (Nachbau des Lösers, Endcommit).
Tor am Endstand: `F:\3D Druck.review-051\laeufe\stapel-tor2.txt` — 17 921
bestanden, 59 übersprungen, Läufe mit Fehler 0, ruff/format/mypy Exit 0.
Ausführlich: `reports\stapel.md`; Sonden und Rohdaten `sonden\stapel\`.

## 1. Je Registerpunkt

**RM-209 (Rundform-Einpassung an Gittern).** Gebaut: `app/core/perceive/refine.py`.
`exhausted()` rechnet SciPys `trf_no_bounds` Zweig für Zweig für alle Kegel-
und Ringläufe einer Runde zugleich in NumPy und übernimmt nur das sichere
Nein; alles andere rechnet der echte Löser Zahl für Zahl. Eingebaut vor den
ganzen Flecken, den Stücken und dem Mantelnachweis (`features._screening`,
`_screened_fits`; Kegel- und Ringeinpassung getrennt in Plan und Löser).
`solve()` ist `least_squares` auf diesem Weg, bitgleich nachgebaut, ohne
SciPys Hülle (ein Fünftel der Löserzeit).
Sicherheitsabstand und Herkunft: Wegabweichung Stapel ↔ echter Lauf nach 100
Auswertungen höchstens 2,8e-11 relativ; an jedem bestätigten Lauf (Kumiko,
Drache, Meshy) dieselbe Schrittfolge und Newton-Schrittzahl, die Abweichung
nutzt höchstens 5,8e-4 des Abstands zur jeweiligen Schwelle
(`DECISION_MARGIN = 1e-6`, Reserve ≈ 1 700); Abbruchschwellen mindestens zwei
Zehnerpotenzen entfernt; Schattenlauf mit 1e-9 verschobenen Auswertungen muss
ebenso ausschöpfen und darf höchstens 1e-6 abweichen. Keine falsche Absage an
21 000 echten Läufen (Kumiko, Drache, Freiform, Meshy).
Messung (CPU, belastet, im Wechsel): Kumiko 37,6 → 24,9 s, Meshy 603 → 472 s.
Abnahme „§31 belegt oder begründet angepasst": **nein** (siehe 7).

**RM-132 (Freiform am Ein-Sekunden-Ziel).** Der Stapelumbau ist gebaut. An der
Freiform der Leistungstests bringt er nichts messbares (13,9 → 13,8 s CPU
belastet): Von 274 Läufen sind 65 vergeblich, 27–38 davon erkennt der Stapel,
und der Rest der Zeit liegt woanders. Abnahme: **nein**.

**RM-193 (glatte Generator-Freiform).** Drache 12,8 → 13,3 s CPU (belastet,
gleich im Rauschen); dort sind 12 von 98 Läufen vergeblich, in Gruppen zu
klein für den Stapel. Abnahme §31: **nein**.

Korpusvergleich (beide Commits): 553 Körper aus `F:\3D Dateien` (190 Dateien,
darunter Drache, Kumiko-Schale, Meshy-Murmelbrett, Piratenschiff,
BowlingGame mit den Bowlingkugeln, Gartenschlauchhalter, Elegoo,
Beckenreiniger) und `tests/data/meshes`, gegen Worktree auf `aa82afdff`:
**553 von 553 bitgleich** (Namen, Arten, Provenienz, jedes Maß als
`float.hex`, alle Dreiecksnummern, Freiformauskunft), kein Fehler.

## 2. Kundensicht

Vorher und nachher dieselben Merkmale mit denselben Namen und Maßen. An
Gittern und erzeugten Netzen endet die Merkmalserkennung früher (Kumiko-Schale
um ein Drittel, Meshy-Brett um ein Fünftel); an Figuren und Schiffskörpern
bleibt die Wartezeit gleich.

## 3. Dateien und Tests

| Datei | getragen von |
|---|---|
| `app/core/perceive/refine.py` (neu) | `tests/test_refine.py` (15 Fälle: Formeln = Einpassung, keine falsche Absage, Reihenfolge von Problemen, Punkten, Nachbarn, jeder Abstand allein, Abbruch, Nachbau bitgleich zu SciPy, Formen mit/ohne Stapel gleich an Prüfkörper und fünf Korpusnetzen) |
| `app/core/perceive/features.py` | `test_refine.py`, `test_fit_stability.py`, `test_round_surface_measurements.py`, `test_features.py`, Tor |
| `tests/test_round_surface_measurements.py` | Abbruchfall liest `refine.solve` |
| `app/core/perceive/CLAUDE.md`, `.claude/rules/schichtanalyse.md`, `konzepte/begruendungen/regel-schichtanalyse.md` | `test_directory_docs.py` |

Gegenproben rot: Stapel sagt zu allem nein (7 Fälle rot), Kegelformel um 1e-7
verbogen (Formelfall rot), Nachbau um ein ULP verschoben (Nachbaufall rot).

## 4. Oberflächentexte

Keine.

## 5. Changelog-Satz

„Die Merkmalserkennung ist an Gittermodellen und erzeugten Netzen deutlich
schneller, bei denselben Ergebnissen."

## 6. Registertext

RM-209, RM-132, RM-193 bleiben offen (`[~]`), jeweils mit dem Satz: „Stapelumbau
gebaut (`53813ec61`, `8e1afee29`): sicher vergebliche Kegel- und Ringläufe
entfallen, Löser ohne SciPy-Hülle, Merkmale am Korpus (553 Körper) bitgleich.
Kumiko-Schale −34 %, Meshy-Brett −22 % CPU (belastet); Drache, Freiform,
Schiff unverändert. §31 an keinem Modell erreicht — Rest und nächster Hebel
siehe Schlussbericht stapel." Die Zahl „1 127 Kegelläufe" in RM-209 ist
veraltet: heute 467, davon 442 vergeblich.

## 7. Nicht behoben

**§31 an keinem Modell.** Verbleibende Posten (cProfile am Endstand, belastet;
Ziel = 1 s je 200 000 Dreiecke):

- **Kumiko-Schale** (Ziel 0,47 s; 32,8 s unter cProfile): `fit_cylinder` 7,3 s
  (davon `_cylinder_contour` 4,9), Löser 7,0 s (1 200 Läufe, fast alle
  konvergierende Kugeln), `fit_sphere` 5,6 s (1 092 von 1 881 gut — echte
  Arbeit für die Freiformauskunft), `_finished_faces` 4,0 s (`_face_roles`
  2,7), `_surface_support` 3,6 s, `_merged_cylinders` 2,6 s. Nächster Hebel:
  die Zylinderkontur und der Kugellöser — beide antworten, Sparen geht nur über
  schnellere bitgleiche Rechnung, nicht über Auslassen.
- **Drache** (Ziel 1,6 s; 13,3 s): `_read_surface_support` 3,2 s an der Haut,
  `_large_facet_faces` 3,1 s (fragt ohne Hauturteil, RM-193), `fit_torus_samples`
  1,6 s (SVD über ganze Flecken), `_connected_patches` 1,3 s, `_fit_circle` 1,0 s,
  Löser 1,4 s. Nächster Hebel: `_large_facet_faces` das Hauturteil geben.
- **Freiform** (Ziel 1,0 s; 16,8 s): Löser 4,0 s (1 237 Läufe, median 31
  Auswertungen, die meisten liefern), `_surface_support` 2,7 s, `find_helices`
  2,0 s, `_connected_patches` 1,1 s, `_fit_circle` 1,1 s, `_rigid_key` 0,9 s.
  Nächster Hebel: Gewindesuche an Freiformen, danach der Löser selbst.
- **Schiff obj_3** (Ziel 2,1 s; 20,5 s): Löser 4,6 s (324 Läufe an großen
  Flecken), `_large_facet_faces` 4,3 s, `_surface_support` 3,5 s,
  `fit_torus_samples` 1,8 s, `curvature_jumps` 1,6 s.

**Vergebliche Läufe in kleinen Gruppen** bleiben: am Drachen 12, am Schiff 55,
an der Freiform 38 von 65. Gemessen: Der Stapel für jede Gruppengröße
(`MIN_BATCH = 1`) erkennt 11/40/38 davon, kostet aber mehr, als sie sparen
(Drache 12,4 → 13,2 s, Schiff 18,3 → 20,3 s CPU). An der Kumiko-Schale
laufen noch 22–48 vergebliche Läufe, die der Stapel nicht bestätigen kann.

**Zeiten nur unter Last**: Die Maschine lief durchgehend mit 100 % CPU und bis
zu 148 fremden Python-Prozessen (Gesamtprüfung). Die Leistungsprüfungen
(`-m performance`) fährt die Release-Sitzung auf ruhiger Maschine.
