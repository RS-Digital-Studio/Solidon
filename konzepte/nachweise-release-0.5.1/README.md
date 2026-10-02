# Nachweise der Durchsicht und des Releases 0.5.1 (26. bis 29.09.2026)

Was offene Registerpunkte, Kommentare und Begründungen aus der Durchsicht v0.5.1
und dem Release 0.5.1 fortsetzen oder belegen: Berichte, Sonden, Patches, kurze
Ausgaben und das Resteinventar. Sie lagen im Review-Ordner der Release-Sitzung
und im Prüfordner der Gesamtprüfung, beide nur auf der Entwicklungsmaschine;
geholt mit [RM-294](../../ROADMAP-ARCHIV.md#rm-294). **Unverändert abgelegt** —
ein umgeschriebenes Messskript belegt seine Zahl nicht mehr; deshalb nimmt
`pyproject.toml` den Ordner von ruff aus. Geändert sind nur Nutzerpfade
(`%USERPROFILE%` statt des Kontonamens) und in `reports/fenster.md` ein
verschluckter Backslash (`F:\3D Dateien`).

Nicht hier liegen Modelle, Netze, G-Code, Profile, lange Protokolle und die
Schnappschüsse der Arbeitsbäume. Wo ein Punkt sie brauchte, steht im Register
eine Aussage über die Messung. Pfade **in** den Dateien nennen die Orte ihres
Tages (`F:\3D Druck.review-051\…`, `F:\3D Dateien\…`) und gelten nur auf der
Entwicklungsmaschine.

## Eine Sonde fahren

Mit dem Interpreter des Projekts, aus einem Arbeitsbaum am Stand, den der
zugehörige Bericht oder Registerpunkt nennt:

```
set PYTHONUTF8=1
set SONDE_TREE=F:\3D Druck.<arbeitsbaum>
F:\3D Druck\.venv\Scripts\python.exe konzepte\nachweise-release-0.5.1\sonden\<paket>\<sonde>.py
```

Den Baum lesen die Sonden auf drei Arten: über `SONDE_TREE` (`common.py` in
`3mf/`, `fenster/`, `bohrung/`, `rest-bohrung/`, `rest-muendung/`), über
`_baum.setup` (`bohren/`, `rest-lippe/`, `rest-merker/`, Vorgabe im Kopf der
Datei) oder als erstes Argument (`hilfsprozess/`, `kanten/`, `rest-kunde/probe.py`,
`rest-auswahl/probe.py`, `druck/besteck_absturz.py`). `rest-auswahl` und
`rest-kunde` fahren ihre `scenario_*.py` über `probe.py` am echten Fenster.
Modelle kommen aus Roberts Korpus `F:\3D Dateien` und sind nicht beigelegt;
die Sonde nennt die Datei. Ausgaben schreibt eine Sonde neben sich
(`*.txt`, `*.out`, `out/`). Die Shellskripte (`korpus.sh`, `reihe_ab*.sh`,
`fenster-vor.sh`, `langloch.sh`) tragen die Pfade der Durchsicht und sind vor
einem neuen Lauf anzupassen.

## Inhalt

| Datei | Wofür | Punkt |
|---|---|---|
| [`reports/rm384-spaetes-helferende-2026-10-02.md`](reports/rm384-spaetes-helferende-2026-10-02.md) | Späteres Helferende am öffentlichen Kernweg, erhaltene Startursache, Startkontingent, Generation und tatsächliche Gegenläufe | RM-384 |
| [`reports/rm320-baugruppen-2026-10-02.md`](reports/rm320-baugruppen-2026-10-02.md) | Begrenzter Langlochzug mit freien Stiften und Innenkammern, tatsächlicher Arbeiterabbruch sowie analytische und reale Modellbelege | RM-320 |
| [`reports/rm284-rundungsgruppen-2026-10-02.md`](reports/rm284-rundungsgruppen-2026-10-02.md) | Rundungsgruppen, belegte Merkmalsfortführung und ausdrückliche Neuwahl; analytische Gegenfälle, Kundenmodelle und Schlussreview | RM-284, notwendiger RM-218-Anschluss |
| [`reports/rm298-hilfsprozessmarken-2026-10-02.md`](reports/rm298-hilfsprozessmarken-2026-10-02.md) | Vorbereitete öffentliche Helfer-Messwege, unverfälschte Marken und Entwicklungskontrollen | RM-298(d) |
| [`reports/rm298-lifecycle-2026-10-02.md`](reports/rm298-lifecycle-2026-10-02.md) | Aktiver Windows-Elternabbruch, tatsächliche OS-Priorität und Gegenproben | RM-298(d) |
| [`reports/rm298-poolnachweise-2026-10-02.md`](reports/rm298-poolnachweise-2026-10-02.md) | Integrierte Besitzgrenze, vier lokale Fehleranschlüsse, echte Gegenläufe und Entwicklungstor | RM-298(a) |
| [`reports/rm285-textnachweise-2026-10-02.md`](reports/rm285-textnachweise-2026-10-02.md) | Integrierte UI-/CLI-/Bereichsprüfertexte, tatsächliche Tore und Abnahmegrenze | RM-285, RM-347 |
| [`reports/rm285-modelltexte-2026-10-02.md`](reports/rm285-modelltexte-2026-10-02.md) | Fortsetzbare Liste der 42 Modelltextausdrücke mit 43 Texttrennern, Wirkung und Quellenhashes | RM-285, RM-347 |
| [`reports/rm290-textnachweise-2026-10-02.md`](reports/rm290-textnachweise-2026-10-02.md) | Abschluss a–h, wirkliche Wächter/Altgegenproben und Commit-/Tor-Nachweis | RM-290, RM-347 |
| [`reports/rm312-slicer-matrix-2026-10-02.md`](reports/rm312-slicer-matrix-2026-10-02.md) | Unabhängig geprüfter Zwischenbericht: 52/125 Matrixläufe, Messmethoden, Profile und offene Grenzen | RM-312, RM-347 |
| [`RESTE-INVENTAR.md`](RESTE-INVENTAR.md) | Inventar der Reste der Durchsicht, Quelle jedes „Inventar 1.x“ im Register | RM-292 und die Punkte „Aus der Durchsicht v0.5.1 (Inventar …)“ |
| [`laeufe/kanten-dicht.txt`](laeufe/kanten-dicht.txt) | Messlauf des Pakets kanten (Ausgabe der gleichnamigen Sonde) | RM-284 |
| [`laeufe/kanten-gruppe-brep.txt`](laeufe/kanten-gruppe-brep.txt) | Messlauf des Pakets kanten (Ausgabe der gleichnamigen Sonde) | RM-284 |
| [`laeufe/kanten-gruppe-brep2.txt`](laeufe/kanten-gruppe-brep2.txt) | Messlauf des Pakets kanten (Ausgabe der gleichnamigen Sonde) | RM-284 |
| [`laeufe/kanten-gruppe-nachher.txt`](laeufe/kanten-gruppe-nachher.txt) | Messlauf des Pakets kanten (Ausgabe der gleichnamigen Sonde) | RM-284 |
| [`laeufe/kanten-gruppe-vorher.txt`](laeufe/kanten-gruppe-vorher.txt) | Messlauf des Pakets kanten (Ausgabe der gleichnamigen Sonde) | RM-284 |
| [`laeufe/kanten-wand.txt`](laeufe/kanten-wand.txt) | Messlauf des Pakets kanten (Ausgabe der gleichnamigen Sonde) | RM-284 |
| [`laeufe/kanten-zeit.txt`](laeufe/kanten-zeit.txt) | Messlauf des Pakets kanten (Ausgabe der gleichnamigen Sonde) | RM-284 |
| [`laeufe/rev-code-t11.txt`](laeufe/rev-code-t11.txt) | Beleg T-11 des Code-Reviews: Stücknummern nach gelöschtem Schnitt | RM-287 |
| [`laeufe/rev-code-u1.txt`](laeufe/rev-code-u1.txt) | Beleg U-1 des Code-Reviews: `op_dialog._switch` klemmt still | RM-286 |
| [`reports/3mf-schluss.md`](reports/3mf-schluss.md) | Schlussbericht Paket 3mf: Qt-Takt beim Import großer 3MF | RM-258 |
| [`reports/ast-flake.md`](reports/ast-flake.md) | Bericht zu den sporadischen Abrissen, Befund an der Maschine | RM-272 |
| [`reports/bohren-schluss.md`](reports/bohren-schluss.md) | Schlussbericht Paket bohren, §6–7 Vorschlag zu `_without_scars` | RM-187 |
| [`reports/fenster.md`](reports/fenster.md) | Bericht Paket fenster der Durchsicht, Empfehlung zum Fadenkreuz | RM-291 |
| [`reports/kanten-schluss.md`](reports/kanten-schluss.md) | Schlussbericht Paket kanten, §6–7 Registertext und Nicht behoben | RM-284 |
| [`reports/review-autosplit-lagen.md`](reports/review-autosplit-lagen.md) | Review des Fixes `autosplit-lagen-051` | RM-307 |
| [`reports/review-code-ui-texte.md`](reports/review-code-ui-texte.md) | Code-Review der Pakete texte und ui | RM-290 |
| [`reports/review-einfuegen.md`](reports/review-einfuegen.md) | Review von `einfuegen-freier-platz` (F11 bis F15, N8) | RM-303 bis RM-306 |
| [`reports/review-gesamt-dd95985e5.md`](reports/review-gesamt-dd95985e5.md) | Review des Gesamtprüfungspakets bis `3018613e6` (B1 bis B10) | RM-289 |
| [`reports/review-handbuch.md`](reports/review-handbuch.md) | Code-Review des Handbuchumbaus | RM-299, Handbuchkonzept |
| [`reports/review-hilfsprozess.md`](reports/review-hilfsprozess.md) | Review des Pakets hilfsprozess | RM-298 |
| [`reports/review-kopien.md`](reports/review-kopien.md) | Review von `merkmale-an-kopien` | RM-210, RM-302 |
| [`reports/review-speicher.md`](reports/review-speicher.md) | Review von `speicher-ohne-prozesswerte` (F2) | RM-300 |
| [`reports/review-sprache-changelog2.md`](reports/review-sprache-changelog2.md) | Sprachreview des zweiten Changelog-Durchgangs | RM-290 |
| [`reports/review-sprache-ui-texte.md`](reports/review-sprache-ui-texte.md) | Sprachreview der Pakete texte und ui | RM-290 |
| [`reports/review-stapel.md`](reports/review-stapel.md) | Review des Pakets stapel | RM-297 |
| [`reports/stapel-schluss.md`](reports/stapel-schluss.md) | Schlussbericht Paket stapel, Abschnitt „Nicht behoben“ | RM-132, RM-193, RM-209 |
| [`reports/strang-b-uebersetzung.md`](reports/strang-b-uebersetzung.md) | Durchsicht der Übersetzungen aus Strang B (42 Befunde, behoben) | Handbuchkonzept |
| [`reports/tor-rest-schraube/weg.txt`](reports/tor-rest-schraube/weg.txt) | Fingerabdrücke des Wegs `slanted_part` unter Rauschen | RM-187 |
| [`review/cura-paket-2026-09-27/bericht.md`](review/cura-paket-2026-09-27/bericht.md) | Bericht Paket D: CuraEngine bekommt die Maschine des Druckers | RM-281 |
| [`review/gesamt-2026-09-27/naht/ergebnis.json`](review/gesamt-2026-09-27/naht/ergebnis.json) | Abnahme Schrägnaht in fünf Slicern | RM-281 |
| [`review/gesamt-2026-09-27/naht/lauf.txt`](review/gesamt-2026-09-27/naht/lauf.txt) | Abnahme Schrägnaht in fünf Slicern | RM-281 |
| [`review/gesamt-2026-09-27/stufe-e-prusa.out`](review/gesamt-2026-09-27/stufe-e-prusa.out) | Abnahme Stufe E am Minigolf-Satz mit Pilz (Ergebnis und Ausgabe) | RM-281 |
| [`review/gesamt-2026-09-27/stufe-e-prusa/ergebnis.json`](review/gesamt-2026-09-27/stufe-e-prusa/ergebnis.json) | Abnahme Stufe E am Minigolf-Satz mit Pilz (Ergebnis und Ausgabe) | RM-281 |
| [`review/gesamt-2026-09-27/stufe-e.out`](review/gesamt-2026-09-27/stufe-e.out) | Abnahme Stufe E am Minigolf-Satz mit Pilz (Ergebnis und Ausgabe) | RM-281 |
| [`review/gesamt-2026-09-27/stufe-e/ergebnis.json`](review/gesamt-2026-09-27/stufe-e/ergebnis.json) | Abnahme Stufe E am Minigolf-Satz mit Pilz (Ergebnis und Ausgabe) | RM-281 |
| [`review/gesamt-2026-09-27/stufe-f/abnahme.json`](review/gesamt-2026-09-27/stufe-f/abnahme.json) | Abnahme Stufe F im Slicer (Prozess des Herstellers je Qualität) | RM-281 |
| [`review/gesamt-2026-09-27/stufe-f/lauf.txt`](review/gesamt-2026-09-27/stufe-f/lauf.txt) | Abnahme Stufe F im Slicer (Prozess des Herstellers je Qualität) | RM-281 |
| [`review/herstellerprofil-2026-09-27/review-a-b.md`](review/herstellerprofil-2026-09-27/review-a-b.md) | Unabhängiges Review von A und B vor dem Commit | RM-281 |
| [`review/merkmale-kopien-2026-09-28/bericht.md`](review/merkmale-kopien-2026-09-28/bericht.md) | Sonde am Minigolf-Satz: Erkennung an Kopien, CPU vorher und nachher | Begründung `karte-app-core-perceive`, RM-210 |
| [`review/merkmale-kopien-2026-09-28/im_wechsel.py`](review/merkmale-kopien-2026-09-28/im_wechsel.py) | Sonde am Minigolf-Satz: Erkennung an Kopien, CPU vorher und nachher | Begründung `karte-app-core-perceive`, RM-210 |
| [`review/merkmale-kopien-2026-09-28/nachher-1.log`](review/merkmale-kopien-2026-09-28/nachher-1.log) | Sonde am Minigolf-Satz: Erkennung an Kopien, CPU vorher und nachher | Begründung `karte-app-core-perceive`, RM-210 |
| [`review/merkmale-kopien-2026-09-28/nachher-2.log`](review/merkmale-kopien-2026-09-28/nachher-2.log) | Sonde am Minigolf-Satz: Erkennung an Kopien, CPU vorher und nachher | Begründung `karte-app-core-perceive`, RM-210 |
| [`review/merkmale-kopien-2026-09-28/sonde_minigolf.py`](review/merkmale-kopien-2026-09-28/sonde_minigolf.py) | Sonde am Minigolf-Satz: Erkennung an Kopien, CPU vorher und nachher | Begründung `karte-app-core-perceive`, RM-210 |
| [`review/merkmale-kopien-2026-09-28/vergleich_minigolf.py`](review/merkmale-kopien-2026-09-28/vergleich_minigolf.py) | Sonde am Minigolf-Satz: Erkennung an Kopien, CPU vorher und nachher | Begründung `karte-app-core-perceive`, RM-210 |
| [`review/merkmale-kopien-2026-09-28/vorher-1.log`](review/merkmale-kopien-2026-09-28/vorher-1.log) | Sonde am Minigolf-Satz: Erkennung an Kopien, CPU vorher und nachher | Begründung `karte-app-core-perceive`, RM-210 |
| [`review/merkmale-kopien-2026-09-28/vorher-2.log`](review/merkmale-kopien-2026-09-28/vorher-2.log) | Sonde am Minigolf-Satz: Erkennung an Kopien, CPU vorher und nachher | Begründung `karte-app-core-perceive`, RM-210 |
| [`review/rm252-meldung-2026-09-28/ERGEBNIS.md`](review/rm252-meldung-2026-09-28/ERGEBNIS.md) | Nachstellung am Originalprojekt des Besteckeinsatzes | RM-252 |
| [`review/rm252-meldung-2026-09-28/nachstellung.out`](review/rm252-meldung-2026-09-28/nachstellung.out) | Nachstellung am Originalprojekt des Besteckeinsatzes | RM-252 |
| [`review/rm252-meldung-2026-09-28/nachstellung.py`](review/rm252-meldung-2026-09-28/nachstellung.py) | Nachstellung am Originalprojekt des Besteckeinsatzes | RM-252 |
| [`sonden/3mf/auswerten.py`](sonden/3mf/auswerten.py) | Sonde des Pakets 3mf (Qt-Takt, GIL-Griffe, Blöcke, 3D-Maus) | RM-258; `threemf.py`, `leash.py`, `loading.py`, `spacemouse.py` |
| [`sonden/3mf/common.py`](sonden/3mf/common.py) | Sonde des Pakets 3mf (Qt-Takt, GIL-Griffe, Blöcke, 3D-Maus) | RM-258; `threemf.py`, `leash.py`, `loading.py`, `spacemouse.py` |
| [`sonden/3mf/out/ab_ab1.txt`](sonden/3mf/out/ab_ab1.txt) | Messreihe des Pakets 3mf (`reihe_ab*.sh`), Reihen `abt` und `ab4` tragen RM-258 | RM-258 |
| [`sonden/3mf/out/ab_ab2.txt`](sonden/3mf/out/ab_ab2.txt) | Messreihe des Pakets 3mf (`reihe_ab*.sh`), Reihen `abt` und `ab4` tragen RM-258 | RM-258 |
| [`sonden/3mf/out/ab_ab3prio.txt`](sonden/3mf/out/ab_ab3prio.txt) | Messreihe des Pakets 3mf (`reihe_ab*.sh`), Reihen `abt` und `ab4` tragen RM-258 | RM-258 |
| [`sonden/3mf/out/ab_ab4.txt`](sonden/3mf/out/ab_ab4.txt) | Messreihe des Pakets 3mf (`reihe_ab*.sh`), Reihen `abt` und `ab4` tragen RM-258 | RM-258 |
| [`sonden/3mf/out/ab_abc1.txt`](sonden/3mf/out/ab_abc1.txt) | Messreihe des Pakets 3mf (`reihe_ab*.sh`), Reihen `abt` und `ab4` tragen RM-258 | RM-258 |
| [`sonden/3mf/out/ab_abt.txt`](sonden/3mf/out/ab_abt.txt) | Messreihe des Pakets 3mf (`reihe_ab*.sh`), Reihen `abt` und `ab4` tragen RM-258 | RM-258 |
| [`sonden/3mf/out/ab_abz1.txt`](sonden/3mf/out/ab_abz1.txt) | Messreihe des Pakets 3mf (`reihe_ab*.sh`), Reihen `abt` und `ab4` tragen RM-258 | RM-258 |
| [`sonden/3mf/p01_nativ.py`](sonden/3mf/p01_nativ.py) | Sonde des Pakets 3mf (Qt-Takt, GIL-Griffe, Blöcke, 3D-Maus) | RM-258; `threemf.py`, `leash.py`, `loading.py`, `spacemouse.py` |
| [`sonden/3mf/p02_griffe.py`](sonden/3mf/p02_griffe.py) | Sonde des Pakets 3mf (Qt-Takt, GIL-Griffe, Blöcke, 3D-Maus) | RM-258; `threemf.py`, `leash.py`, `loading.py`, `spacemouse.py` |
| [`sonden/3mf/p03_umschalten.py`](sonden/3mf/p03_umschalten.py) | Sonde des Pakets 3mf (Qt-Takt, GIL-Griffe, Blöcke, 3D-Maus) | RM-258; `threemf.py`, `leash.py`, `loading.py`, `spacemouse.py` |
| [`sonden/3mf/p04_bloecke.py`](sonden/3mf/p04_bloecke.py) | Sonde des Pakets 3mf (Qt-Takt, GIL-Griffe, Blöcke, 3D-Maus) | RM-258; `threemf.py`, `leash.py`, `loading.py`, `spacemouse.py` |
| [`sonden/3mf/p05_waechter.py`](sonden/3mf/p05_waechter.py) | Sonde des Pakets 3mf (Qt-Takt, GIL-Griffe, Blöcke, 3D-Maus) | RM-258; `threemf.py`, `leash.py`, `loading.py`, `spacemouse.py` |
| [`sonden/3mf/p06_hid.py`](sonden/3mf/p06_hid.py) | Sonde des Pakets 3mf (Qt-Takt, GIL-Griffe, Blöcke, 3D-Maus) | RM-258; `threemf.py`, `leash.py`, `loading.py`, `spacemouse.py` |
| [`sonden/3mf/reihe_ab.sh`](sonden/3mf/reihe_ab.sh) | Sonde des Pakets 3mf (Qt-Takt, GIL-Griffe, Blöcke, 3D-Maus) | RM-258; `threemf.py`, `leash.py`, `loading.py`, `spacemouse.py` |
| [`sonden/3mf/reihe_abc.sh`](sonden/3mf/reihe_abc.sh) | Sonde des Pakets 3mf (Qt-Takt, GIL-Griffe, Blöcke, 3D-Maus) | RM-258; `threemf.py`, `leash.py`, `loading.py`, `spacemouse.py` |
| [`sonden/3mf/reihe_abz.sh`](sonden/3mf/reihe_abz.sh) | Sonde des Pakets 3mf (Qt-Takt, GIL-Griffe, Blöcke, 3D-Maus) | RM-258; `threemf.py`, `leash.py`, `loading.py`, `spacemouse.py` |
| [`sonden/3mf/reihe_abz2.sh`](sonden/3mf/reihe_abz2.sh) | Sonde des Pakets 3mf (Qt-Takt, GIL-Griffe, Blöcke, 3D-Maus) | RM-258; `threemf.py`, `leash.py`, `loading.py`, `spacemouse.py` |
| [`sonden/bohren/_abdruck.py`](sonden/bohren/_abdruck.py) | Sonde des Pakets bohren (Werkzeug in der Welt) | RM-274 im Archiv; `features.py`, `test_cut_in_world.py`, `test_mesh_edges.py`, `test_features.py` |
| [`sonden/bohren/_baum.py`](sonden/bohren/_baum.py) | Sonde des Pakets bohren (Werkzeug in der Welt) | RM-274 im Archiv; `features.py`, `test_cut_in_world.py`, `test_mesh_edges.py`, `test_features.py` |
| [`sonden/bohren/p12_kippe.py`](sonden/bohren/p12_kippe.py) | Sonde des Pakets bohren (Werkzeug in der Welt) | RM-274 im Archiv; `features.py`, `test_cut_in_world.py`, `test_mesh_edges.py`, `test_features.py` |
| [`sonden/bohren/p16_eckrahmen.py`](sonden/bohren/p16_eckrahmen.py) | Sonde des Pakets bohren (Werkzeug in der Welt) | RM-274 im Archiv; `features.py`, `test_cut_in_world.py`, `test_mesh_edges.py`, `test_features.py` |
| [`sonden/bohren/p4_koplanar.py`](sonden/bohren/p4_koplanar.py) | Sonde des Pakets bohren (Werkzeug in der Welt) | RM-274 im Archiv; `features.py`, `test_cut_in_world.py`, `test_mesh_edges.py`, `test_features.py` |
| [`sonden/bohren/p5_drill_platten.py`](sonden/bohren/p5_drill_platten.py) | Sonde des Pakets bohren (Werkzeug in der Welt) | RM-274 im Archiv; `features.py`, `test_cut_in_world.py`, `test_mesh_edges.py`, `test_features.py` |
| [`sonden/bohren/p6_merkmalwege.py`](sonden/bohren/p6_merkmalwege.py) | Sonde des Pakets bohren (Werkzeug in der Welt) | RM-274 im Archiv; `features.py`, `test_cut_in_world.py`, `test_mesh_edges.py`, `test_features.py` |
| [`sonden/bohrung/common.py`](sonden/bohrung/common.py) | Nachmessung am Laptop-Ständer | RM-253 |
| [`sonden/bohrung/rm253_focus.py`](sonden/bohrung/rm253_focus.py) | Nachmessung am Laptop-Ständer | RM-253 |
| [`sonden/bohrung/rm253_focus_out.txt`](sonden/bohrung/rm253_focus_out.txt) | Nachmessung am Laptop-Ständer | RM-253 |
| [`sonden/cifix/hilfsprozess_fenster.py`](sonden/cifix/hilfsprozess_fenster.py) | Sonde der CI-Fehlschläge 0.5.1 (Wächterfall der Verfeinerung) | `test_refine.py` |
| [`sonden/cifix/test_zz_cifix_env.py`](sonden/cifix/test_zz_cifix_env.py) | Sonde der CI-Fehlschläge 0.5.1 (Wächterfall der Verfeinerung) | `test_refine.py` |
| [`sonden/cifix/test_zz_cifix_grow.py`](sonden/cifix/test_zz_cifix_grow.py) | Sonde der CI-Fehlschläge 0.5.1 (Wächterfall der Verfeinerung) | `test_refine.py` |
| [`sonden/cifix/test_zz_cifix_refine.py`](sonden/cifix/test_zz_cifix_refine.py) | Sonde der CI-Fehlschläge 0.5.1 (Wächterfall der Verfeinerung) | `test_refine.py` |
| [`sonden/cifix/test_zz_cifix_twice.py`](sonden/cifix/test_zz_cifix_twice.py) | Sonde der CI-Fehlschläge 0.5.1 (Wächterfall der Verfeinerung) | `test_refine.py` |
| [`sonden/cifix2/test_zz_cifix2_alive.py`](sonden/cifix2/test_zz_cifix2_alive.py) | Sonde der CI-Fehlschläge 0.5.1 (49 Lagen um dieselbe Kante) | `test_refine.py` |
| [`sonden/cifix2/test_zz_cifix2_family.py`](sonden/cifix2/test_zz_cifix2_family.py) | Sonde der CI-Fehlschläge 0.5.1 (49 Lagen um dieselbe Kante) | `test_refine.py` |
| [`sonden/cifix2/test_zz_cifix2_gegenprobe.py`](sonden/cifix2/test_zz_cifix2_gegenprobe.py) | Sonde der CI-Fehlschläge 0.5.1 (49 Lagen um dieselbe Kante) | `test_refine.py` |
| [`sonden/cifix2/umbau_refine.py`](sonden/cifix2/umbau_refine.py) | Sonde der CI-Fehlschläge 0.5.1 (49 Lagen um dieselbe Kante) | `test_refine.py` |
| [`sonden/druck/besteck_absturz.out`](sonden/druck/besteck_absturz.out) | Besteckeinsatz: Absturz, Bisektion, Original und Netz | RM-252 |
| [`sonden/druck/besteck_absturz.py`](sonden/druck/besteck_absturz.py) | Besteckeinsatz: Absturz, Bisektion, Original und Netz | RM-252 |
| [`sonden/druck/besteck_absturz2.out`](sonden/druck/besteck_absturz2.out) | Besteckeinsatz: Absturz, Bisektion, Original und Netz | RM-252 |
| [`sonden/druck/besteck_absturz3.out`](sonden/druck/besteck_absturz3.out) | Besteckeinsatz: Absturz, Bisektion, Original und Netz | RM-252 |
| [`sonden/druck/besteck_bisekt.out`](sonden/druck/besteck_bisekt.out) | Besteckeinsatz: Absturz, Bisektion, Original und Netz | RM-252 |
| [`sonden/druck/besteck_bisekt.py`](sonden/druck/besteck_bisekt.py) | Besteckeinsatz: Absturz, Bisektion, Original und Netz | RM-252 |
| [`sonden/druck/besteck_netz.out`](sonden/druck/besteck_netz.out) | Besteckeinsatz: Absturz, Bisektion, Original und Netz | RM-252 |
| [`sonden/druck/besteck_original.out`](sonden/druck/besteck_original.out) | Besteckeinsatz: Absturz, Bisektion, Original und Netz | RM-252 |
| [`sonden/druck/besteck_original.py`](sonden/druck/besteck_original.py) | Besteckeinsatz: Absturz, Bisektion, Original und Netz | RM-252 |
| [`sonden/fenster/common.py`](sonden/fenster/common.py) | Sonde des Pakets fenster (Parsen, Sicherung, Projekt öffnen) | `threemf.py`, `session.py` |
| [`sonden/fenster/p06_xml_gil.py`](sonden/fenster/p06_xml_gil.py) | Sonde des Pakets fenster (Parsen, Sicherung, Projekt öffnen) | `threemf.py`, `session.py` |
| [`sonden/fenster/p08_sicherung.py`](sonden/fenster/p08_sicherung.py) | Sonde des Pakets fenster (Parsen, Sicherung, Projekt öffnen) | `threemf.py`, `session.py` |
| [`sonden/fenster/p22_projekt_oeffnen.py`](sonden/fenster/p22_projekt_oeffnen.py) | Sonde des Pakets fenster (Parsen, Sicherung, Projekt öffnen) | `threemf.py`, `session.py` |
| [`sonden/fenster/p31_xml_freeze.py`](sonden/fenster/p31_xml_freeze.py) | Sonde des Pakets fenster (Parsen, Sicherung, Projekt öffnen) | `threemf.py`, `session.py` |
| [`sonden/fenster/p31b_phasen.py`](sonden/fenster/p31b_phasen.py) | Sonde des Pakets fenster (Parsen, Sicherung, Projekt öffnen) | `threemf.py`, `session.py` |
| [`sonden/hilfsprozess/buchhaltung.py`](sonden/hilfsprozess/buchhaltung.py) | Sonde des Pakets hilfsprozess | `kernel_jobs.py`, `kernel_process.py`, `test_kernel_process.py`; Begründungen `regel-kern`, `regel-wartezeit` |
| [`sonden/hilfsprozess/eingefroren/einstieg.py`](sonden/hilfsprozess/eingefroren/einstieg.py) | Hilfsprozess im gefrorenen Paket (Einstieg, Spec, Treiber, Bericht; ohne Bauerzeugnisse) | Begründung `regel-kern` |
| [`sonden/hilfsprozess/eingefroren/kernelprobe.spec`](sonden/hilfsprozess/eingefroren/kernelprobe.spec) | Hilfsprozess im gefrorenen Paket (Einstieg, Spec, Treiber, Bericht; ohne Bauerzeugnisse) | Begründung `regel-kern` |
| [`sonden/hilfsprozess/eingefroren/voll-bericht.json`](sonden/hilfsprozess/eingefroren/voll-bericht.json) | Hilfsprozess im gefrorenen Paket (Einstieg, Spec, Treiber, Bericht; ohne Bauerzeugnisse) | Begründung `regel-kern` |
| [`sonden/hilfsprozess/eingefroren/voll_treiber.py`](sonden/hilfsprozess/eingefroren/voll_treiber.py) | Hilfsprozess im gefrorenen Paket (Einstieg, Spec, Treiber, Bericht; ohne Bauerzeugnisse) | Begründung `regel-kern` |
| [`sonden/hilfsprozess/gil_kern.py`](sonden/hilfsprozess/gil_kern.py) | Sonde des Pakets hilfsprozess | `kernel_jobs.py`, `kernel_process.py`, `test_kernel_process.py`; Begründungen `regel-kern`, `regel-wartezeit` |
| [`sonden/hilfsprozess/grob_stillstand.py`](sonden/hilfsprozess/grob_stillstand.py) | Sonde des Pakets hilfsprozess | `kernel_jobs.py`, `kernel_process.py`, `test_kernel_process.py`; Begründungen `regel-kern`, `regel-wartezeit` |
| [`sonden/hilfsprozess/privat.py`](sonden/hilfsprozess/privat.py) | Sonde des Pakets hilfsprozess | `kernel_jobs.py`, `kernel_process.py`, `test_kernel_process.py`; Begründungen `regel-kern`, `regel-wartezeit` |
| [`sonden/hilfsprozess/referenz.py`](sonden/hilfsprozess/referenz.py) | Sonde des Pakets hilfsprozess | `kernel_jobs.py`, `kernel_process.py`, `test_kernel_process.py`; Begründungen `regel-kern`, `regel-wartezeit` |
| [`sonden/hilfsprozess/sanft_enden.py`](sonden/hilfsprozess/sanft_enden.py) | Sonde des Pakets hilfsprozess | `kernel_jobs.py`, `kernel_process.py`, `test_kernel_process.py`; Begründungen `regel-kern`, `regel-wartezeit` |
| [`sonden/hilfsprozess/schwelle.py`](sonden/hilfsprozess/schwelle.py) | Sonde des Pakets hilfsprozess | `kernel_jobs.py`, `kernel_process.py`, `test_kernel_process.py`; Begründungen `regel-kern`, `regel-wartezeit` |
| [`sonden/hilfsprozess/senkplatte.py`](sonden/hilfsprozess/senkplatte.py) | Sonde des Pakets hilfsprozess | `kernel_jobs.py`, `kernel_process.py`, `test_kernel_process.py`; Begründungen `regel-kern`, `regel-wartezeit` |
| [`sonden/hilfsprozess/speicher.py`](sonden/hilfsprozess/speicher.py) | Sonde des Pakets hilfsprozess | `kernel_jobs.py`, `kernel_process.py`, `test_kernel_process.py`; Begründungen `regel-kern`, `regel-wartezeit` |
| [`sonden/hilfsprozess/zweimal_verfeinert.py`](sonden/hilfsprozess/zweimal_verfeinert.py) | Sonde des Pakets hilfsprozess | `kernel_jobs.py`, `kernel_process.py`, `test_kernel_process.py`; Begründungen `regel-kern`, `regel-wartezeit` |
| [`sonden/kanten/auswahl.py`](sonden/kanten/auswahl.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/beispiel_v36.py`](sonden/kanten/beispiel_v36.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/beispiel_v37.py`](sonden/kanten/beispiel_v37.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/dialog.py`](sonden/kanten/dialog.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/dicht.py`](sonden/kanten/dicht.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/echt.py`](sonden/kanten/echt.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/faedeln.py`](sonden/kanten/faedeln.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/faedeln_brep.py`](sonden/kanten/faedeln_brep.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/faedeln_ii.py`](sonden/kanten/faedeln_ii.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/faedeln_ii_bau.py`](sonden/kanten/faedeln_ii_bau.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/faedeln_ii_bau.txt`](sonden/kanten/faedeln_ii_bau.txt) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/faedeln_ii_brep.py`](sonden/kanten/faedeln_ii_brep.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/faedeln_ii_ops.py`](sonden/kanten/faedeln_ii_ops.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/faedeln_ops.py`](sonden/kanten/faedeln_ops.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/faedeln_verlauf.py`](sonden/kanten/faedeln_verlauf.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/fail-gezielt2.txt`](sonden/kanten/fail-gezielt2.txt) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/fail-head.txt`](sonden/kanten/fail-head.txt) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/grundlinie.py`](sonden/kanten/grundlinie.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/gruppe.py`](sonden/kanten/gruppe.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/gruppe_brep.py`](sonden/kanten/gruppe_brep.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/gruppe_brep2.py`](sonden/kanten/gruppe_brep2.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/muendung.py`](sonden/kanten/muendung.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/ringe_echt.py`](sonden/kanten/ringe_echt.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/ringe_suchen.py`](sonden/kanten/ringe_suchen.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/rot_ohne_i.py`](sonden/kanten/rot_ohne_i.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/swept_tool.txt`](sonden/kanten/swept_tool.txt) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/tests_ii.py`](sonden/kanten/tests_ii.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/uebersetzen.py`](sonden/kanten/uebersetzen.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/uebersetzen2.py`](sonden/kanten/uebersetzen2.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/uebersetzen3.py`](sonden/kanten/uebersetzen3.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/verlauf.py`](sonden/kanten/verlauf.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/verrunden.py`](sonden/kanten/verrunden.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/vorgabe.py`](sonden/kanten/vorgabe.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/vorschau.py`](sonden/kanten/vorschau.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/vorschau_ii.py`](sonden/kanten/vorschau_ii.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/wand.py`](sonden/kanten/wand.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/zapfen.py`](sonden/kanten/zapfen.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/kanten/zeit.py`](sonden/kanten/zeit.py) | Sonde des Pakets kanten | RM-284 |
| [`sonden/rest-auswahl/fenster-vor.sh`](sonden/rest-auswahl/fenster-vor.sh) | Sonde rest-auswahl (Fenster, Langloch, Wiederholung; läuft über `probe.py`) | RM-213, RM-278; `test_render_gizmo.py` |
| [`sonden/rest-auswahl/langloch.sh`](sonden/rest-auswahl/langloch.sh) | Sonde rest-auswahl (Fenster, Langloch, Wiederholung; läuft über `probe.py`) | RM-213, RM-278; `test_render_gizmo.py` |
| [`sonden/rest-auswahl/out/fenster-vor.txt`](sonden/rest-auswahl/out/fenster-vor.txt) | Fenstersonde am Stand davor: keine Maße nach dem Zug zum Langloch | RM-213 |
| [`sonden/rest-auswahl/out/langloch-head.txt`](sonden/rest-auswahl/out/langloch-head.txt) | Sonde rest-auswahl (Fenster, Langloch, Wiederholung; läuft über `probe.py`) | RM-213, RM-278; `test_render_gizmo.py` |
| [`sonden/rest-auswahl/out/langloch-neu.txt`](sonden/rest-auswahl/out/langloch-neu.txt) | Sonde rest-auswahl (Fenster, Langloch, Wiederholung; läuft über `probe.py`) | RM-213, RM-278; `test_render_gizmo.py` |
| [`sonden/rest-auswahl/out/repro-head1.txt`](sonden/rest-auswahl/out/repro-head1.txt) | Sonde rest-auswahl (Fenster, Langloch, Wiederholung; läuft über `probe.py`) | RM-213, RM-278; `test_render_gizmo.py` |
| [`sonden/rest-auswahl/out/repro-neu1.txt`](sonden/rest-auswahl/out/repro-neu1.txt) | Sonde rest-auswahl (Fenster, Langloch, Wiederholung; läuft über `probe.py`) | RM-213, RM-278; `test_render_gizmo.py` |
| [`sonden/rest-auswahl/probe.py`](sonden/rest-auswahl/probe.py) | Sonde rest-auswahl (Fenster, Langloch, Wiederholung; läuft über `probe.py`) | RM-213, RM-278; `test_render_gizmo.py` |
| [`sonden/rest-auswahl/scenario_langloch.py`](sonden/rest-auswahl/scenario_langloch.py) | Zug in der Öffnung einer Senkbohrung | RM-278 |
| [`sonden/rest-auswahl/scenario_repro.py`](sonden/rest-auswahl/scenario_repro.py) | Sonde rest-auswahl (Fenster, Langloch, Wiederholung; läuft über `probe.py`) | RM-213, RM-278; `test_render_gizmo.py` |
| [`sonden/rest-auswahl/scenario_zeit.py`](sonden/rest-auswahl/scenario_zeit.py) | Sonde rest-auswahl (Fenster, Langloch, Wiederholung; läuft über `probe.py`) | RM-213, RM-278; `test_render_gizmo.py` |
| [`sonden/rest-auswahl/screens.py`](sonden/rest-auswahl/screens.py) | Sonde rest-auswahl (Fenster, Langloch, Wiederholung; läuft über `probe.py`) | RM-213, RM-278; `test_render_gizmo.py` |
| [`sonden/rest-bohrung/common.py`](sonden/rest-bohrung/common.py) | Sonde rest-bohrung (`t1_verify`, `t11_rounded_mouth` je Radius) | RM-259 |
| [`sonden/rest-bohrung/t11_rounded_mouth.py`](sonden/rest-bohrung/t11_rounded_mouth.py) | Sonde rest-bohrung (`t1_verify`, `t11_rounded_mouth` je Radius) | RM-259 |
| [`sonden/rest-bohrung/t11_rounded_mouth_R13_r0.5.txt`](sonden/rest-bohrung/t11_rounded_mouth_R13_r0.5.txt) | Sonde rest-bohrung (`t1_verify`, `t11_rounded_mouth` je Radius) | RM-259 |
| [`sonden/rest-bohrung/t11_rounded_mouth_R13_r0.txt`](sonden/rest-bohrung/t11_rounded_mouth_R13_r0.txt) | Sonde rest-bohrung (`t1_verify`, `t11_rounded_mouth` je Radius) | RM-259 |
| [`sonden/rest-bohrung/t11_rounded_mouth_R13_r1.txt`](sonden/rest-bohrung/t11_rounded_mouth_R13_r1.txt) | Sonde rest-bohrung (`t1_verify`, `t11_rounded_mouth` je Radius) | RM-259 |
| [`sonden/rest-bohrung/t11_rounded_mouth_R13_r2.txt`](sonden/rest-bohrung/t11_rounded_mouth_R13_r2.txt) | Sonde rest-bohrung (`t1_verify`, `t11_rounded_mouth` je Radius) | RM-259 |
| [`sonden/rest-bohrung/t11_rounded_mouth_R20_r1.txt`](sonden/rest-bohrung/t11_rounded_mouth_R20_r1.txt) | Sonde rest-bohrung (`t1_verify`, `t11_rounded_mouth` je Radius) | RM-259 |
| [`sonden/rest-bohrung/t11_rounded_mouth_R20_r2.txt`](sonden/rest-bohrung/t11_rounded_mouth_R20_r2.txt) | Sonde rest-bohrung (`t1_verify`, `t11_rounded_mouth` je Radius) | RM-259 |
| [`sonden/rest-bohrung/t11_rounded_mouth_R40_r1.txt`](sonden/rest-bohrung/t11_rounded_mouth_R40_r1.txt) | Sonde rest-bohrung (`t1_verify`, `t11_rounded_mouth` je Radius) | RM-259 |
| [`sonden/rest-bohrung/t11_rounded_mouth_R40_r2.txt`](sonden/rest-bohrung/t11_rounded_mouth_R40_r2.txt) | Sonde rest-bohrung (`t1_verify`, `t11_rounded_mouth` je Radius) | RM-259 |
| [`sonden/rest-bohrung/t1_verify.py`](sonden/rest-bohrung/t1_verify.py) | Sonde rest-bohrung (`t1_verify`, `t11_rounded_mouth` je Radius) | RM-259 |
| [`sonden/rest-bohrung/t1_verify.txt`](sonden/rest-bohrung/t1_verify.txt) | Sonde rest-bohrung (`t1_verify`, `t11_rounded_mouth` je Radius) | RM-259 |
| [`sonden/rest-klick/weg2/weg2-code.diff`](sonden/rest-klick/weg2/weg2-code.diff) | Gemessener, nicht behaltener Weg 2: Bewegungsgriff versetzen | RM-232 |
| [`sonden/rest-klick/weg2/weg2-test.py`](sonden/rest-klick/weg2/weg2-test.py) | Gemessener, nicht behaltener Weg 2: Bewegungsgriff versetzen | RM-232 |
| [`sonden/rest-kunde/out/teilen-vorher-organizer.txt`](sonden/rest-kunde/out/teilen-vorher-organizer.txt) | Organizer vor dem Teilen: 52 % im Bild nach *Skalieren* | RM-280; `test_viewport_decisions.py` |
| [`sonden/rest-kunde/probe.py`](sonden/rest-kunde/probe.py) | Sonde rest-kunde (läuft über `probe.py`) | RM-280; `test_finding_actions.py`, `test_start_screen.py`, `test_viewport_decisions.py` |
| [`sonden/rest-kunde/s268_laptop.txt`](sonden/rest-kunde/s268_laptop.txt) | Sonde rest-kunde (läuft über `probe.py`) | RM-280; `test_finding_actions.py`, `test_start_screen.py`, `test_viewport_decisions.py` |
| [`sonden/rest-kunde/s268_verbraucht.py`](sonden/rest-kunde/s268_verbraucht.py) | Sonde rest-kunde (läuft über `probe.py`) | RM-280; `test_finding_actions.py`, `test_start_screen.py`, `test_viewport_decisions.py` |
| [`sonden/rest-kunde/s269_zuletzt.py`](sonden/rest-kunde/s269_zuletzt.py) | Sonde rest-kunde (läuft über `probe.py`) | RM-280; `test_finding_actions.py`, `test_start_screen.py`, `test_viewport_decisions.py` |
| [`sonden/rest-kunde/s269_zuletzt_vorher.txt`](sonden/rest-kunde/s269_zuletzt_vorher.txt) | Sonde rest-kunde (läuft über `probe.py`) | RM-280; `test_finding_actions.py`, `test_start_screen.py`, `test_viewport_decisions.py` |
| [`sonden/rest-kunde/scenario_teilen.py`](sonden/rest-kunde/scenario_teilen.py) | Sonde rest-kunde (läuft über `probe.py`) | RM-280; `test_finding_actions.py`, `test_start_screen.py`, `test_viewport_decisions.py` |
| [`sonden/rest-lippe/_baum.py`](sonden/rest-lippe/_baum.py) | Drehweg und Sonden der gekippten Haltelippe | RM-262 |
| [`sonden/rest-lippe/common.py`](sonden/rest-lippe/common.py) | Drehweg und Sonden der gekippten Haltelippe | RM-262 |
| [`sonden/rest-lippe/prepare_ops_mit_drehen.patch`](sonden/rest-lippe/prepare_ops_mit_drehen.patch) | Gebauter Drehweg für *Merkmal drehen* an der Magnettasche | RM-262 |
| [`sonden/rest-lippe/r5_nach_dem_kippen.py`](sonden/rest-lippe/r5_nach_dem_kippen.py) | Drehweg und Sonden der gekippten Haltelippe | RM-262 |
| [`sonden/rest-lippe/r5_nach_dem_kippen_wt1.txt`](sonden/rest-lippe/r5_nach_dem_kippen_wt1.txt) | Drehweg und Sonden der gekippten Haltelippe | RM-262 |
| [`sonden/rest-lippe/r6_lippe_messen.py`](sonden/rest-lippe/r6_lippe_messen.py) | Drehweg und Sonden der gekippten Haltelippe | RM-262 |
| [`sonden/rest-lippe/r6_lippe_messen_wt1.txt`](sonden/rest-lippe/r6_lippe_messen_wt1.txt) | Drehweg und Sonden der gekippten Haltelippe | RM-262 |
| [`sonden/rest-lippe/r7_erkennung_gekippt.py`](sonden/rest-lippe/r7_erkennung_gekippt.py) | Drehweg und Sonden der gekippten Haltelippe | RM-262 |
| [`sonden/rest-lippe/r7_erkennung_gekippt_wt1.txt`](sonden/rest-lippe/r7_erkennung_gekippt_wt1.txt) | Drehweg und Sonden der gekippten Haltelippe | RM-262 |
| [`sonden/rest-merker/_baum.py`](sonden/rest-merker/_baum.py) | Sonde der Schritte beim Übernehmen | RM-273 |
| [`sonden/rest-merker/p08_schritte.py`](sonden/rest-merker/p08_schritte.py) | Sonde der Schritte beim Übernehmen | RM-273 |
| [`sonden/rest-merker/p11_prof.txt`](sonden/rest-merker/p11_prof.txt) | Auszug des Profils von *Merkmal verschieben* (das Rohprofil ist nicht versioniert) | RM-273 |
| [`sonden/rest-muendung/common.py`](sonden/rest-muendung/common.py) | Sonde rest-muendung | RM-259, RM-262 |
| [`sonden/rest-muendung/m19_exakt_band.py`](sonden/rest-muendung/m19_exakt_band.py) | Exakter Prototyp: Stopfen und Werkzeug samt Band | RM-259 |
| [`sonden/rest-muendung/m19_exakt_band.txt`](sonden/rest-muendung/m19_exakt_band.txt) | Ausgabe des Prototyps (−2,97 / +0,29 / −4,56 mm³) | RM-259 |
| [`sonden/rest-muendung/m20_lippe_kippen.py`](sonden/rest-muendung/m20_lippe_kippen.py) | Sonde rest-muendung | RM-259, RM-262 |
| [`sonden/rest-muendung/m20_lippe_kippen.txt`](sonden/rest-muendung/m20_lippe_kippen.txt) | Sonde rest-muendung | RM-259, RM-262 |
| [`sonden/rest-muendung/nachbau.py`](sonden/rest-muendung/nachbau.py) | Sonde rest-muendung | RM-259, RM-262 |
| [`sonden/rest-muendung/prepare_ops_mit_drehen_heute.patch`](sonden/rest-muendung/prepare_ops_mit_drehen_heute.patch) | Drehweg auf dem Stand mit `2e496575b` und `202d5133a` (8 Hunks) | RM-262 |
| [`sonden/rest-teilen/korpus-liste.txt`](sonden/rest-teilen/korpus-liste.txt) | Korpus der Teilungen, HEAD und Arbeitsbaum je Modell | RM-187 |
| [`sonden/rest-teilen/korpus.sh`](sonden/rest-teilen/korpus.sh) | Korpus der Teilungen, HEAD und Arbeitsbaum je Modell | RM-187 |
| [`sonden/rest-teilen/teilen_zeit.py`](sonden/rest-teilen/teilen_zeit.py) | Korpus der Teilungen, HEAD und Arbeitsbaum je Modell | RM-187 |
| [`sonden/revstapel/probe_h.json`](sonden/revstapel/probe_h.json) | Sonde H des Stapel-Reviews, Quelle des Wächterfalls | `tests/data/refine_guard_case.json` |
