# P1.4 – räumliche Zuordnung, Abbruch und große echte Projekte

Ausgang beim Fortsetzen: `69efc1cdf`, main und origin/main gleich.
Parallel fremd bearbeitet: `ROADMAP.md` (nur P2.7-Zeile),
`konzepte/README.md`, `konzepte/nachweise-cad-p2-7/README.md`.
Diese Änderungen bleiben in ihrer Sitzung. `website/` bleibt unangetastet.

## Zuständigkeiten

- `test_policy_runner`: matching.py, perceive/CLAUDE.md,
  test_spatial_matching.py und gegebenenfalls test_matching.py.
- `policy_review`: Abbruch an allen Aufrufern in evaluate.py, local.py,
  prepare_ops.py; scene/geom-Karten; test_matching_cancellation.py;
  erforderliche Signaturen vorhandener Doubles in test_evaluation.py.
- `exact_transform_kernel`: unabhängiger lesender Mathematik-/Vertragsreview.
- Root: test_matching_lifecycle.py, tests/CLAUDE.md, Gesamtintegration,
  Entwicklungstor, genauer Commitumfang und eigene P1.4-Statuspflege.

## Abgeleitete Bauart

Der ursprüngliche Vorschlag einer beliebigen Komponentenzerlegung ist
verworfen: gleiche optimale Kosten garantieren nicht dieselben IDs bei
konkurrierenden Altansprüchen. Vier alte Zentren [0,1,1,1] und drei neue
[0,0,1] liefern bereits ein echtes Gegenbeispiel. Der vollständige bisherige
Solverkontext bleibt für Konfliktfälle erhalten.

Der direkte Weg ist stärker als eine Beschränkung auf isolierte 1:1-Kanten:
Jede Zeile der tatsächlich kleineren globalen Solverseite benötigt ein
striktes akzeptiertes Minimum; dessen Partner müssen paarweise verschieden
sein. Dann findet jede Solverzeile sofort eine freie Minimalspalte. Der
zusammenhängende 1056er-Rasterfall ist dadurch ebenfalls gedeckt. Bei
fehlendem Zertifikat wird die gesamte globale Strafmatrix aufgebaut.

Die räumliche Abfrage darf keine akzeptablen Paare verwerfen. Die einfache
Kugelabfrage mit Radius 0,08 verlor gerundet akzeptierte Grenzpunkte, etwa
[0.04800000000000001,0.064,0]. Maximumsnorm und nach außen begrenzte
Rundungsreserve übernehmen nur die Vorauswahl; die Kosten entscheiden
weiterhin mit unveränderter fachlicher Schwelle.

## Root-Nachweise bis zum integrierten Algorithmus-Freeze

- Python 3.14.7; `tools/check_env.py` Exit 0, constraints stimmen.
- `twin_scan.py app` Exit 0, Protokoll p14-twins-app.txt. Tatsächlicher
  fachlicher Zwilling: cost/_cost_matrix/resolve; wird gemeinsam umgesetzt.
- Erster Lebenslaufentwurf: 1-mm-Würfel lief nativ grün, Netz ohne Merkmale;
  belegte bestehende MIN_FACE_AREA=4 mm². Testkörper vor weiteren Zusagen
  auf Kantenlänge 2 mm korrigiert, kein Produktionswert geändert.
- Zweiter Lauf überschnitt sich mit dem Anschluss der neuen API:
  evaluate schon mit check_cancelled, match noch ohne. 1 failed/1 passed;
  nur ein dokumentierter Arbeitszwischenstand, keine Produktregression.
- Nach API-Verfügbarkeit: `tools/affected_tests.py
  tests/test_matching_lifecycle.py --run`: 2 passed, 7,79 s, direkter Exit 0.
  p14-lifecycle-api-ready.txt. 176 echte Würfel ergeben 1056 Flächen,
  importiert als STL und STEP. ID/Lage/Normalen/Maße/Quellen/Träger,
  Originalquelle, Verschieben, Warmcache, Speichern/Wiederöffnung und
  Undo/Redo geprüft; am Netz tatsächlicher Matchaufruf über 1000 und echter
  Disk-Cachetreffer. Native Körper werden beim Wiederöffnen neu berechnet,
  ein nativer Disk-Treffer wird nicht behauptet.
- Die Merkmalsgrenze ist nur im Lifecycle-Test auf 1056 gesetzt. Produktion
  bleibt bei 1000 bis zum Release-Nachweis für Zuordnung, dichte Gegenfälle
  und weitere Verbraucher (insbesondere relations).

## Gemeinsames Entwicklungstor

Alle zwölf eigenen Dateien sind eingefroren. Matcher: 123 gezielte Fälle,
unabhängiger Review 16 Gegenproben, jeweils Exit 0. Aufrufer: 13 neue Fälle,
5 Auswertungsfälle und 197 Bestandsfälle, jeweils Exit 0; Statik grün.

`prepare_spatial_gate.py` hat 974 Dateien eingefroren. Laufordner:
`C:/Users/rober/AppData/Local/Temp/solidon-cad-spatial-final-2d2e3254de024c1488890d1dc42f9d0a`.
Root-Prozess 9397 ist beendet: Suite Exit 1, 1 failed, 12736 passed,
26 skipped in 531,43 s. Ein Testdouble in test_surface_placement nahm das
neue check_cancelled-Schlüsselwort nicht an; der fachliche Test blieb dabei
unerreicht. policy_review korrigiert ausschließlich diese Signatur und ihre
Weitergabe. Anschließend neuer Freeze und vollständiges Entwicklungstor.
Ruff/Format/mypy lieferten jeweils Exit 0. Währenddessen hat die
parallele Sitzung ihre drei Dokumente als `469ef4e92` committed und gepusht
(ls-remote bestätigt); alle 974 eingefrorenen Dateien bleiben bytegleich.

`stage_spatial_scope.py` und der bisherige private Commithelfer sind bereit.
Commit und eigener P1.4-ROADMAP-Eintrag folgen erst nach finalen Exitcodes.
Fenster und Leistung bleiben ausschließlich Release-Abnahme.

## Wichtig: P1.4 ist damit noch nicht vollständig abgenommen

Neben der ausstehenden Leistungsfreigabe der Zahlengrenze bleibt ein
belegter semantischer Fall: Im globalen Gegenfall [0,1,1,1] → [0,0,1]
erhält eine von drei gleich guten alten IDs den einzigen neuen Nachfolger
als eindeutiges `mapping`. Der räumliche Umbau erhält dieses Altverhalten
bewusst; es erfüllt noch nicht die vollständige Konzeptforderung nach
korrekter Mehrdeutigkeit bei symmetrischen Ansprüchen. Dieser Befund darf
nicht unter einer allein offenen Release-Abnahme verschwinden.

`test_policy_runner` prüft lesend eine separate Folgeeinheit P1.4b:
mehrere alte Ansprüche, gemeinsamer MatchResult/evaluate/resolve/ask-Vertrag,
keine doppelte Vergabe neuer IDs, gespeicherte Antworten und Cacheentwertung.
Notiz wird p14-competing-identities-plan.md. Noch keine Produktänderung
während des laufenden Gates. Diese Folgeeinheit geht vor P1.5.

P1.5-Einstieg liegt separat in p15-entry-plan.md; policy_review untersucht
lesend Verbraucher, exact_transform_kernel die ersten echten Sollkörper.
Beide führen während des Root-Gates keine Tests aus und ändern keinen Code.
