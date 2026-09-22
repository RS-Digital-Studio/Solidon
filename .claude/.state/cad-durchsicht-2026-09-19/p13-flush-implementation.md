# P1.3 — bündiger Anschluss, eingefrorenes Umsetzungspaket

Basis: `5e31809c1`. Keine Commits oder Pushes durch diesen Bearbeiter.

## Geänderte Produkt- und Testpfade

- `app/core/scene/fits.py`: Ebenenbefund plus unabhängige gemeinsame
  Körperprobe; radiale Voraussetzungen bleiben auf radiale Passungen
  beschränkt. Bündige Lage heißt verschiedene Körper derselben Platte,
  ausdrücklich ohne erfundene Kontaktbedingung. Fehlende Ebenenmaße können
  neben einer tatsächlichen Körperkollision stehen; fehlende Referenzen
  bleiben Fehler. Sechs eigene bündige Texte, bestehende radiale Texte erhalten.
- `app/core/scene/CLAUDE.md`: ein zusammenhängender Absatz direkt nach dem
  vorhandenen P1.3-Körpervertrag.
- `tests/test_fit_geometry.py`: unabhängige Quaderfälle für Netz, nativ und
  beide gemischten Reihenfolgen, realer Kontakt und reale Überdeckung,
  Quellen-/Originalerhalt, Transformation, Fehler/Abbruch, Karte/Steckbrief/
  Agentenprüfung, Export eines Partners, Dokument/Cache/Wiederöffnung/Undo/Redo.
- `tests/test_digest_and_fits.py`: ausschließlich `two_faces` und sieben
  bestehende bündige Fälle. Echte angeordnete Würfel ersetzen überlagerte
  Platzhalter; Normalen-/Abstandserwartungen bleiben erhalten.

Geänderte bestehende Funktionen in `test_digest_and_fits.py`:
`two_faces`, `test_two_faces_in_one_plane_say_nothing` (jetzt
`test_two_faces_in_one_plane_report_only_the_body_probe`),
`test_a_lid_that_sits_proud_is_reported`,
`test_faces_at_an_angle_are_a_different_mistake`,
`test_scaled_normals_do_not_change_a_flush_result`,
`test_float32_noise_on_a_normal_is_still_flush`,
`test_a_tenth_of_a_degree_is_not_flush`,
`test_five_degrees_at_the_same_centre_is_not_flush`.

`measure.py`, `evaluate.py` und `writer.py` wurden nicht geändert. Die sechs
Quellen samt fünf Übersetzungsvorschlägen liegen in `p13-flush-texts.json`;
die Katalogübernahme gehört ausschließlich `policy_review`. Dieser Bearbeiter
hat keine Sprachkataloge geschrieben.

## Direkte Nachweise

Protokollverzeichnis:
`C:/Users/rober/AppData/Local/Temp/solidon-flush-bb142c00c0d74284ac0f96d08511211a`.

1. `red.txt`: vor Produktänderung **33 failed / 33 deselected**, Exit 1.
   Alle neu angelegten bündigen Fälle zeigen die fehlende Körperaussage.
2. `first-green.txt`: vollständige damalige Körperdatei **66 passed**, Exit 0.
3. `connections-first.txt`: Körperdatei und Digest-/Passungsdatei
   **201 passed in 3.15 s**, Exit 0.
4. `affected.txt`: `tools/affected_tests.py` mit expliziten Kerndateien
   `test_fit_geometry`, `test_digest_and_fits`, `test_maps`, `test_evaluation`,
   `test_export`, `test_language_rules`, `test_core_package_direction`:
   **1543 passed in 117.39 s**, Exit 0. `test_value_labels.py` wurde vom
   Einsammler ausdrücklich als Fensterdatei zurückgestellt.
5. Danach ausschließlich eine Ruff-Vereinfachung im Quellen-Dictionary der
   Testfixture sowie der genauere Same-body-Gegenfall mit zwei verschiedenen
   echten Flächendreiecken: `final-focused.txt`, **89 passed in 2.21 s**,
   Exit 0. Produktverhalten gegenüber Schritt 4 unverändert.
6. Ruff über alle drei eigenen Python-Dateien, deren Formatprüfung und
   `git diff --check` über alle vier Pfade: Exit 0.
   `mypy --follow-imports=silent app/core/scene/fits.py`: Exit 0.

Der unbeschränkte Mypy-Aufruf auf `fits.py` meldete im parallelen Zwischenstand
acht Fehler ausschließlich im neuen `perceive/surfaces.py`; globales Ruff
meldete 15 Fehler ausschließlich in parallel bearbeiteten P1.6-Dateien.
Diese beiden Zwischenstandläufe hatten Exit 1 und wurden dem Elternagenten
gemeldet. Sie sind kein grünes Gesamttor. Das gemeinsame Tor und die
vollständige Katalogstatik folgen im Gesamtpaket.

Kein Fensterdateitest, keine Leistungsprüfung, keine Website-Änderung.
Montageweg, Flächenkontakt und Druckverhalten werden durch die starre
Körperprobe weiterhin nicht nachgewiesen.
