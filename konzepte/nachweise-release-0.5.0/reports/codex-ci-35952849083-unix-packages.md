# Unix-Pakete aus CI-Lauf 35952849083

Quellstand: `71113912dbecd2b77f1ed9511b4c8e53af95d8b9`, manueller Vollbau
`build.yml` auf `main`. Stand dieser Akte: 24.09.2026, beide Versuche vollständig
mit demselben Mac-Abbruch beendet. **Keine Paketfreigabe, keine Artefakte
heruntergeladen.** Der geforderte Gesamterfolg ist durch den unten genannten
Workerabbruch nicht gegeben. Die Quellen wurden nicht geändert und kein
Wiederholungslauf gestartet.

## Tatsächliche Ergebnisse

| Job | Kennung | Ergebnis und Beleg |
|---|---:|---|
| Neueste Versionen | 107485122526 | Erfolgreich, 27:59 gesamt. Kern: 17.061 bestanden, 33 übersprungen, 1 xfail, 1 xpass; 1.530,20 s. |
| Suite Ubuntu | 107485122706 | Erfolgreich, 29:33 gesamt. Kern: 17.061 bestanden, 33 übersprungen, 1 xfail, 1 xpass; 1.548,16 s. Fensterverträge: 210 bestanden, 16 abgewählt; 67,20 s. Renderer: 1 bestanden, 8 abgewählt, 2 xpass; 9,72 s. |
| Suite macOS | 107485122874 | **Fehlgeschlagen**, 38:41 gesamt. Kern: 1 fehlgeschlagen, 16.904 bestanden, 186 übersprungen, 4 xfail, 1 xpass; 2.210,75 s, Exit 1. |
| Suite Windows | 107485122867 | Erfolgreich, 1:19:29 gesamt. Kern: 17.062 bestanden, 33 übersprungen, 1 xfail; 2.030,58 s. Fensterverträge: 210 bestanden, 16 abgewählt; 73,42 s. Alle Fensterdateien erfolgreich. |

Die vier abgeschlossenen vollständigen Jobprotokolle wurden mit
`gh api repos/RS-Digital-Studio/Solidon/actions/jobs/<id>/logs --allow-escape-sequences`
gesichert, jeweils direkter Exit 0:

- `tore/codex-ci-35952849083-latest.txt`
- `tore/codex-ci-35952849083-ubuntu.txt`
- `tore/codex-ci-35952849083-macos.txt`
- `tore/codex-ci-35952849083-windows.txt`

Der Monitor `tore/codex-ci-35952849083-watch.txt` stammt aus
`gh run watch 35952849083 --repo RS-Digital-Studio/Solidon --exit-status --interval 60`.

## Mac-Abbruch

Bei `tests/test_orientation_search.py::test_the_pool_holder_does_not_stand_on_a_knife_edge`
ging Worker `gw0` verloren. Der erste Nachweis steht im Maclog Zeile 609:
`04:08:58.852509Z`, `Not properly terminated`, bei 48 Prozent. Die eindeutige
Testzuordnung steht in Zeilen 736–739; der Kern endet um `04:26:24Z` und der
Schritt um `04:26:25Z` mit Exit 1.

Der Log enthält **keinen** Signalcode, nativen Stapel, Faulthandler-Auszug
oder Speichermangelbeleg. Ein OOM, GEOS-Problem oder bestimmter Aufruf ist
damit nicht bewiesen. Der Test erstellt den Poolhalter und ruft
`search(holder, count=200, profile=profile)` auf (`tests/test_orientation_search.py:856`).
Das ist die einzugrenzende Testlast, noch keine ermittelte Absturzstelle.

## Grenzen der drei angefragten Registerbelege

- **RM-186:** Der Ubuntu-Kern ist vollständig grün. Der am Quellstand
  vorhandene `test_thread_features.py::test_the_end_face_of_a_thread_bolt_belongs_to_its_step`
  ist ein unbedingter Kerntest ohne Fensterfixture, Skip oder Xfail. Er prüft
  ausdrücklich genau `face` und `thread` aus dem Gewindeschritt sowie die
  unabhängig aus dem Netz gelesene Stirnfläche. Der Nachweis besteht aus
  dieser Quellenzuordnung plus dem vollständigen grünen Kern; der
  `pytest -q -n auto`-Log druckt keine grüne Einzeltest-ID.
- **RM-113:** `test_licence_admin.py::test_a_private_regular_token_file_is_read`
  besitzt weiterhin den bedingten CI-Skip bei abgelehntem Dateibesitz. Ein
  grüner Gesamtjob mit Skipanzahl allein belegt deshalb weder diesen Test
  ohne Skip noch die konkreten SID-/ACL-Werte. Der fertige Windowslog wurde
  danach durchsucht: Er enthält weder die Einzeltest-ID noch Besitzer-/Nutzer-SID
  oder ACL-Diagnose. RM-113 bleibt damit offen. Die Diagnose darf
  keine breite Besitzfreigabe oder erneuten Testlauf ersetzen.
- **RM-234:** „Neueste Versionen“ fährt heute ausdrücklich ausschließlich
  `not performance and not rendered and not windowed`; es gibt dort keinen
  Fensterschritt. Belegt sind die neuesten installierten Versionen
  (`manifold3d 3.5.3`, `NumPy 2.5.3`, `PyInstaller 6.22.3`, `Shapely 2.1.2`)
  und ihr grüner Kern. Der jetzige Macfehler liegt ausschließlich beim
  Poolhalter-Worker, nicht beim unbedingten Kerntest
  `test_prepare.py::test_a_widened_countersink_over_the_edge_says_so`.
  Wegen des roten Mac-Kerns wird trotzdem kein vollständig grüner
  Mac-Lauf behauptet. Die frühere Zusage, „Neueste Versionen“ müsse einen
  Fensterschritt erreichen, passt nicht zum aktuellen Workflowumfang.

## Weiterhin gesperrte Paketübernahme

Erwartete finale Artefakte, durch den Workflow belegt:
`solidon3d-linux`, `solidon3d-macos-ARM64`, `solidon3d-macos-X64`.
Erst ein vollständig erfolgreicher Quelllauf erlaubt den Download und die
Hashprüfung. Die vier öffentlichen Dateien wären AppImage, Flatpak und
zwei PKG-Dateien; beigefügte macOS-App-ZIPs bleiben interne Belege.

Der vorgesehene Zielordner `F:/3D Druck/dist/release-35952849083` wurde von
diesem Auftrag nicht angelegt. Windowsartefakte bleiben vollständig beim
Hauptagenten. Eine erfolgreiche Signierung, Notarisierung oder Releaseakte
dieses Laufs liegt noch nicht vor.

## Vollständiger Erstabschluss und genau ein freigegebener Nachlauf

Attempt 1 ist `completed/failure`. Vor dem Nachlauf sind unverändert gesichert:
`tore/codex-ci-35952849083-attempt1-run.json`,
`tore/codex-ci-35952849083-attempt1-jobs.json` und alle vier Joblogs.
Die vollständige Jobliste enthält genau eine Niederlage (Mac 107485122874),
die drei vorausgesetzten Erfolge und ausschließlich ausgelassene Paketfolgejobs.
Der ursprüngliche Monitor endet mit direktem Exit 1.

Nach ausdrücklicher Freigabe durch den Hauptagenten wurde **einmal** gefahren:

```powershell
gh run rerun 35952849083 --repo RS-Digital-Studio/Solidon --failed --debug
```

Direkter Exit 0, Beleg `tore/codex-ci-35952849083-attempt2-request.txt`.
Die anschließende API bestätigt `run_attempt: 2`, `in_progress`, unveränderten
Quellcommit und Beginn `2026-09-24T05:09:19Z`.
Startakten: `codex-ci-35952849083-attempt2-run-start.json` und
`codex-ci-35952849083-attempt2-jobs-start.json` unter `tore/`.

Aktiver neuer Macjob: **107502384432**. GitHub führt die bereits erfolgreichen
Ergebnisse unter neuen Kennungen weiter: Windows 107502385202, Neueste
107502385646, Ubuntu 107502419077. Das sind übernommene Ergebnisse, keine
neuen von uns ausgelösten Testläufe. Der neue Monitor schreibt ausschließlich
`tore/codex-ci-35952849083-attempt2-watch.txt`; der Erstversuch wird nicht
umbenannt, überschrieben oder nachträglich als grün behandelt. Bei erneutem
Fehler gibt es aus diesem Auftrag **keine weitere Wiederholung**.

Die zuletzt korrigierten Windowsfälle sind jetzt ausdrücklich als `PASSED`
im CI-Log belegt: Kataloglöschung Zeile 1156; Ruhezustand dunkel/hell und
Gegenprobe Zeilen 2948–2950; Slicerknopf beide Themen und linke Spalte beide
Themen Zeilen 4267–4270. Die vollständige Fensterauswahl aus `test_ui.py`
besteht mit 659 Fällen, 28 bereits im Kern abgewählt, 628,50 s (Zeile 4673).

## Endergebnis des Debug-Nachlaufs

Attempt 2 ist ebenfalls **`completed/failure`**, unveränderter Quellcommit.
Die Mac-Suite 107502384432 endet nach 34:07. Erneut stirbt `gw0` beim exakt
gleichen Poolhaltertest, wieder bei 48 Prozent:

- `05:25:59.989292Z`: `Not properly terminated`, Debug-Maclog Zeile 2393.
- `05:43:28Z`: eindeutige Testzuordnung, Zeilen 2520–2522.
- 1 fehlgeschlagen, 16.904 bestanden, 186 übersprungen, 3 xfail, 2 xpass;
  1.934,73 s, Zeile 2523.
- `05:43:29Z`: direkter Schritt-Exit 1. Monitor ebenfalls Exit 1.

Gesicherte Endakten, Abrufe jeweils direkter Exit 0:
`tore/codex-ci-35952849083-attempt2-macos.txt`,
`tore/codex-ci-35952849083-attempt2-run-final.json`,
`tore/codex-ci-35952849083-attempt2-jobs-final.json`.

Auch der Debug-Joblog nennt keinen nativen Stapel, Signalcode oder OOM.
Das zusätzliche reine Logarchiv
`tore/codex-ci-35952849083-attempt2-logs.zip` wurde über den
Attempt-2-Logs-Endpunkt bytegetreu gesichert (Exit 0, 112.791 Byte). Es enthält
17 Einträge, darunter die verschachtelte Runnerdiagnose mit
`Worker_20260924-050928-utc.log` und `Runner_20260924-050926-utc.log`.
Die lesende Suche dort liefert nur den äußeren Bash-Prozess 5523 mit Exit 1,
keinen Grund für das Ende des Python-Workers. Die zusätzliche Runnerakte ist
daher ein gesicherter Diagnosebeleg, **kein** OOM- oder Signalnachweis.

Alle Paketfolgejobs sind erneut ausgelassen. **Null Kundenpakete geladen,
keine Signatur- oder Notarisierungsfreigabe, keine Veröffentlichung.** Es
gibt keinen dritten Wiederholungsaufruf aus diesem Auftrag. Beide Monitore
sind beendet und ihre tatsächlichen Exits abgeholt. Das maschinenlesbare
Ergebnis steht in `codex-ci-35952849083-unix-packages.json`.
