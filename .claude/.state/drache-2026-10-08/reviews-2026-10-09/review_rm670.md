# Review RM-670 (`F:/solidon-claude-e`, Zweig `claude/lauf-e`, HEAD `3ef1db065` gegen `origin/welle2` `a9e4d3f64`) — solidon3d-review, 09.10.2026

Umfang: `git -C F:/solidon-claude-e diff origin/welle2 HEAD` vollständig (24 Dateien, +1197/−50; Worktree
sauber, keine unversionierten Dateien). Geprüft: `slicer_profiles` (`_held`, `_holdings`,
`_holding_signature`, `_top_level`, `_all_files`, `SETTLE_NS`/`_settled`, `forget_holdings`,
`_prusa_printer_models`, `_program_folders`, Signatur im Lesedurchgang), `discover._from_path`, Hauptfenster
(`_FoundationWorker`, `_warm_the_slicer`, `_ExportWorker._assembly`, `_export_when_current`/`_write_when_current`,
`_cancel_export`, `_export_worker_done`, `_start_print_findings`, `_print_findings_after_export_ended`,
`_on_busy`, `start`, `_warm_slicer`), sechs Testdateien, `conftest.py`, Regeln druckerwahl und wartezeit, drei
Karten, zwei Begründungen, Register, Archiv, Changelog in sechs Sprachen. Dazu gelesen: `user_roots`,
`install_root`, `profile_roots`, `_orca_profiles`, `_cura_profiles`, `_prusa_store`/`_prusa_signature`,
`single_read`/`_json_files`, `_chain`/`_names_in`, `appimage.ImageCopies`, `handover.standard_choice`,
`machine_for`, `machine_missing`, `profile_source`, `remembered_setup`, `_ChosenSetup`/`_foundation_key`/
`_chosen_setup_now`, `PrintFindingsFlow`, `discover.find_program`/`refresh_path`/`forget_cache`; Belege W2-1 und
W4-2; Regeln zwillinge und tests; Skill regelcheck.

Ausgeführt, alles lesend (am Worktree nur `.ruff_cache` und `.mypy_cache` berührt):
- Sonde `probe_rm670.py` (Scratchpad dieser Sitzung) gegen Roberts ElegooSlicer 1.5.3.5 mit dem Code des
  Worktrees (`app.__file__` = `F:\solidon-claude-e\app` geprüft). Die Maschine stand unter starker Fremdlast
  (Wand das 15- bis 20-Fache der CPU); geurteilt wird über CPU-Zeit und tracemalloc.
- Dateisystem: `%APPDATA%\ElegooSlicer` (Dateizahlen, `user\telemetry_cache`), Startprotokoll
  `log\debug_Thu_Oct_08_18_57_07_96048.log.0`, Zeichenketten in `ElegooSlicer.dll`.
- `ruff format --check` und `ruff check` über die neun geänderten Python-Dateien, `mypy` über die drei
  geänderten App-Module (grün).
- Tests aus `F:/solidon-claude-e`, jeweils Exit 0: die 13 neuen und angepassten in `test_slicer_profiles.py`;
  `test_discover.py`, `test_export_background.py`, `test_export.py` (11 ausgewählt);
  `test_ui_export.py::test_the_3mf_export_reads_the_slicer_stock_in_one_pass`; `test_directory_docs.py` und
  `test_changelog.py` (61 passed, 4 skipped: keine lokalen Erinnerungen, keine Presseentwürfe);
  `test_roadmap.py` und `test_archive.py` (40); `test_discover.py`, `test_slicer_selection.py`,
  `test_install.py` und der Comfy-Fall aus `test_first_run.py` (196); `test_slicer_profiles.py` und
  `test_appimage_profiles.py` vollständig (366).
- AST-Suche über `tests/` nach „fragen, Dateien ändern, wieder fragen" am gemerkten Bestand: 25 Kandidaten,
  von Hand geprüft; die zwei zeitabhängigen hat der Zweig schon angepasst.
- Nicht gefahren: das Entwicklungstor (`suite-getrennt.sh`), `test_manufacturer.py`,
  `test_print_settings*.py`, `test_cura_machine.py`, der Rest von `test_ui_export.py`. Laut `68bb2fd81` lief
  auch beim Autor kein Abschlusslauf.

Sondenwerte (ElegooSlicer, CPU): Signatur 0,05–0,06 s, 4 894 Einträge (`system` 4 753, oberste Ebene der
Installation 133, `user\default` 2, `user\telemetry_cache` 1). Lesen ohne Merker: 1 001 Maschinen 1,64 s,
8 848 Prozesse und Filamente 5,31 s; aus dem Merker 0,16 s und 0,13 s. Gehalten nach beiden: 23,5 MiB. Ein
Exportdurchgang (Vorwahl plus „kennt der Slicer den Drucker") mit warmem Merker: 0,80 s, 1 071 Dokumente,
Spitze 9,7 MiB. Die Vorwahl trifft „Elegoo Centauri Carbon 2 0.4 nozzle", „0.20mm Standard @Elegoo CC2 0.4
nozzle", „Elegoo PLA @ECC2".

Nichts geändert, nichts committet.

**Ergebnis: 0 schwer, 3 mittel, 9 leicht.**

## Mittel

### M1 Die Signatur zählt Dateien, die kein Profil sind — bei offenem ElegooSlicer verfällt der Merker

Stellen: `app/core/export/slicer_profiles.py:415-423` (`user_roots`: jeder Ordner unter `user/` gilt als
Konto), `:3091-3097` (eigene Wurzeln gehen über `_all_files` ein), `:3138-3163` (`_all_files`: jede `.json`,
rekursiv, folgt Verknüpfungen); der Leser nimmt dagegen nur Dateien unter `machine/`, `process/`, `filament/`
(`:3196-3198`, `_kind_of`).

Beleg:
- Sonde: `profile_roots` für ElegooSlicer sind Installation, `user\default`, `system` und
  **`user\telemetry_cache`**. Der jüngste Eintrag der Signatur ist
  `user\telemetry_cache\runtime_state\96048.json`.
- Die Datei schreibt ElegooSlicers `TelemetryReporter` („runtime state file", „recover cached events from dead
  process" in `ElegooSlicer.dll`), je Programmlauf unter neuer Prozessnummer, Inhalt
  `{"process_id":96048,"runtime_sec":205,…}`. Lauf vom 08.10.: Start 18:57:13 (Protokoll), Ordner
  `runtime_state` angelegt 18:57:43, letzte Schreibung 19:00:38 beim Beenden. Geschrieben wird also mindestens
  30 s nach dem Start und beim Beenden; der mitgezählte `runtime_sec` spricht für laufendes Nachschreiben.
- Folge: Jeder Start und jedes Ende des Slicers — bei laufendem Nachschreiben jeder Takt — ändert die Signatur.
  Der nächste 3MF-Export liest die 1 001 Maschinen neu (1,64 s CPU statt 0,16 s), eine neue Grundlage dazu die
  8 848 Prozesse und Filamente (5,31 s). Liegt die Schreibung keine 2 s zurück, wird gar nicht gemerkt.
- Kein Test sieht es: Die Cura-Gegenprobe prüft nur `cura.log`, das schon an der Endung scheitert; für die
  Orca-Familie gibt es keine Nicht-Profildatei in einer eigenen Wurzel.

Warum es zählt: Genau der Kundenweg „Solidon und Slicer nebeneinander, exportieren, im Slicer öffnen,
nachbessern, wieder exportieren" — Roberts eigener mit ElegooSlicer — bekommt die alte Wartezeit zurück; RM-670
und die offene Abnahme (zweiter Export unter 0,5 s) hängen daran. `druckerwahl.md:94-104` verspricht „Eigene
Profile … Datei für Datei", gezählt wird alles mit passender Endung.

Fix: Die Signatur sieht nur an, was der Leser liest — für die Orca-Familie nur Dateien in einem Ordner aus
`PROFILE_DIRS` unterhalb der Wurzel (wie `_kind_of`), und `entry.is_dir(follow_symlinks=False)` wie `rglob`.
`user_roots` selbst nicht filtern: `chosen_machine` liest die `.conf` über `root.parent.parent` jeder Wurzel.
Test: eine `.json` unter `user/<Konto>/telemetry_cache/…` umschreiben → Signatur gleich; `machine/x.json`
umschreiben → anders. Danach die Sonde mit offenem ElegooSlicer wiederholen (zwei Exporte im Abstand einer
Minute).

### M2 Zusammenspiel mit RM-623: `_ChosenSetup` hält die Vorwahl ohne Signatur — der nächste Fensterexport sieht ein angelegtes, umbenanntes oder gelöschtes Profil nicht

Stellen: `app/ui/main_window.py:1461-1478` (`_ChosenSetup`), `:1517` (Wiederverwendung im
Grundlagenarbeiter), `:1925-1934` (der Export nimmt `self._chosen.setup`), `:25523-25548` (`_foundation_key`,
`_chosen_setup_now`: kein Stand des Bestands), `:25584-25585` (einziger Setzer); `app/core/export/handover.py:299-312`
(`profile_source`); Regel `.claude/rules/druckerwahl.md:94-95`; Test `tests/test_export.py:154`.

Beleg:
- `_chosen_setup` wird nur in `_foundation_found` gesetzt. Der Schlüssel enthält Drucker, Material, gemerkte
  Wahl, Platte und `discover.cache_generation()`, nichts über den Bestand des Slicers. Jeder Fensterexport
  bekommt die Wahl (`chosen=self._chosen_setup_now()`) und überspringt `remembered_setup`.
- Ohne gemerkte Maschine (Roberts Fall) kommt sie aus `standard_choice`, mit Dateipfaden als Identität (Sonde:
  `machine_profile='C:\Program Files\ElegooSlicer\resources\profiles\Elegoo\machine\ECC2\Elegoo Centauri Carbon 2 0.4 nozzle.json'`).
- Legt der Kunde im Slicer den Drucker an, für den die Vorwahl vorher `None` ergab, erkennt `machine_missing`
  ihn dank `_held` sofort; die Datei bleibt aber ohne die Vorwahl aus dem Bestand — Herstellerprozess und
  -filament, die RM-623 gerade hineinbringt —, bis sich der Schlüssel ändert. Benennt er eine gewählte eigene
  Datei um oder löscht sie, geht der alte Pfad weiter; `profile_source` endet dann mit einer Protokollwarnung,
  und diese Seite fehlt in der Datei.
- Der neue Test fährt `write_assembly` mit festem Setup und sieht den Merker des Fensters nicht.

Warum es zählt: Die Zusagen dieses Zweigs — „Über Aufrufe hinweg hält nur, was vor jeder Antwort seine Signatur
prüft" (`druckerwahl.md:94-95`), „neues, umbenanntes und gelöschtes Profil" (Archiv), „ein im Slicer neu
angelegtes Druckerprofil kennt der nächste Export" (bisherige Abnahme) — gelten im zusammengeführten Stand für den
Befund, nicht für die Datei. Regel 21 bleibt gewahrt, aber die Datei geht still ohne Herstellerseite hinaus.

Fix: Den Stand des Bestands an die Wahl hängen und im Arbeiter prüfen, nicht im Hauptthread: `_ChosenSetup`
trägt die Signatur (oder einen Hash davon) aus dem Lesedurchgang des `_FoundationWorker`;
`_ExportWorker._assembly_in_one_read` vergleicht sie im eigenen Durchgang, wo sie ohnehin erhoben wird, und
leitet bei Abweichung über `remembered_setup` neu her; das Fenster erneuert danach seine Grundlage (etwa über
eine Generation von `_holdings` im Grundlagenschlüssel). Test über `_ExportWorker` mit `cc2_stock`: Wahl aus dem
alten Bestand, gewählte eigene Datei umbenennen, die nächste Datei nennt die neue. Sonst die Regel ehrlich
machen und `_ChosenSetup` mit Grund als Ausnahme nennen.

### M3 Speicher: ein Merkereintrag je Profilarten-Kombination und je Programm, ohne Verdrängung

Stellen: `app/core/export/slicer_profiles.py:2996-3000` (`_holdings`, Schlüssel `(Programm, Familie,
frozenset(Arten))`), `:3012-3017` (`forget_holdings` nur für Tests). Aufrufer mit verschiedenen Artenmengen:
`handover.py:577` `("machine",)`, `:602` `("process", "filament")`, `print_settings_dialog.py:2314` alle drei,
`filament_picker.py:589` `("filament",)`, `slicer_profiles.py:3738` je eine Art. Zwilling: `_prusa_cache`
(`:3570-3583`) hält genau einen Bestand.

Beleg (Sonde, tracemalloc): nach `("machine",)` 3,4 MiB (1 001 Profile), nach `("process","filament")`
zusammen 23,5 MiB (dazu 8 848 Profile); jeder Eintrag trägt seine eigene Signatur mit 4 894 Tupeln. Der
Druckdialog (alle drei Arten, 9 849 Profile) und die Filamentauswahl (5 962) legen dieselben Profile ein zweites
und drittes Mal ab — hochgerechnet aus 2,2 KiB je Profil rund 22 und 14 MiB, für einen Slicer der Orca-Familie
also rund 60 statt rund 23 MiB. Jeder im Druckdialog angewählte weitere Slicer bleibt bis zum Ende der Sitzung
dazu; vorher hielt nichts davon über einen Aufruf hinaus.

Warum es zählt: doppelt liegender Speicher und eine Menge, die mit der Zahl der Slicer wächst (Roberts Rechner
hat sieben); der Prusa-Zwilling ist bewusst auf einen Bestand begrenzt.

Fix: Je Programm ein Eintrag mit einer Liste je Art; eine Anfrage über mehrere Arten setzt sie zusammen (die
Aufrufer filtern ohnehin je Art über `machines`, `processes`, `filaments` — die Reihenfolge über Arten hinweg
vorher prüfen). Nur der zuletzt gefragte Slicer bleibt, wie bei `_prusa_cache`. Vorher und nachher mit der Sonde
messen.

## Leicht

### L1 Das Tor ist rot: `ruff format --check` an der Zusammenführung

`tests/test_slicer_profiles.py:5204-5205`: Zwischen `test_the_program_folder_is_listed_again_only_when_its_parent_changes`
und `test_a_single_read_walks_each_stock_folder_once` (aus welle2) fehlen die zwei Leerzeilen; `68bb2fd81`
brachte 263 Zeilen in die Datei, die Zusammenführung 261. `ruff format --check` meldet „1 file would be
reformatted", Exit 1. Fix: `ruff format tests/test_slicer_profiles.py`, danach das ganze Tor (`/pruefen`).

### L2 `SETTLE_NS` wird an der Uhr nach dem Lesen gemessen, nicht am Zeitpunkt der Signatur

`slicer_profiles.py:3034-3042` (`_held`), ebenso `:2063-2071` (`_prusa_printer_models`) und `:445-452`
(`_program_folders`). `_settled` vergleicht `time.time_ns()` nach `read()` mit der jüngsten Änderung der vorher
erhobenen Signatur; im Lesedurchgang ist die Signatur noch älter (`_SINGLE_READ.signatures`). Dauert das Lesen
lange (unter Last 25 s Wand für die Maschinen), wird gemerkt, obwohl die Signatur im selben Takt der
Dateisystemuhr wie die letzte Änderung entstand — eine gleich große Neuschreibung in diesem Takt, die das Lesen
verpasst hat, bliebe unsichtbar. Selten, aber genau der Fall, den der Docstring von `SETTLE_NS` ausschließt.
Fix: die Zeit vor der Signatur nehmen und mit ihr im Durchgang ablegen; Test mit gepatchtem `sp.time.time_ns`,
das während `read()` über die Schwelle springt.

### L3 Zwilling ohne Entscheidung: `_prusa_store` merkt ohne `SETTLE_NS`

`slicer_profiles.py:3605-3622` legt jeden Bestand sofort ab. `druckerwahl.md:94-104` nennt `_prusa_store` und
`_holdings` in einem Absatz und sagt „Gemerkt wird erst, was älter ist als `SETTLE_NS`". Dieselbe Gefahr besteht
dort; `zwillinge.md`: „Unentschieden dürfen sie nicht bleiben." Fix: `_prusa_store` legt nur ab, was `_settled`
besteht, oder die Regel nennt den Unterschied mit Grund.

### L4 Vorwärmen, Grundlage und Export lesen denselben Bestand nebeneinander

`slicer_profiles.py:3035-3043`: Fehlt der Eintrag, liest jeder Aufrufer selbst, auch wenn ein anderer Faden
gerade dasselbe liest. Mit einem beim Start geöffneten Modell starten nach der Auswertung der Grundlagenarbeiter
(mit dem Ergebnis) und `_warm_slicer` (`main_window.py:25921-25923`) fast gleichzeitig; ohne gemerkte Maschine
lesen beide die 1 001 Maschinen (je 1,64 s CPU), und ein wartender Export kommt im selben `_on_busy` dazu. Das
Vorwärmen liest nur `("machine",)` (`:1576-1577`); `("process","filament")` (5,31 s) liest erst der
Grundlagenarbeiter — ein Export gleich nach dem Öffnen trägt es noch selbst. `_warm_slicer` fragt
`session.busy` nur beim Start: Öffnet der Kunde 2,5 s nach dem Start ein Modell, teilt sich das Laden den Rechner
mit dem Vorauslesen — der Fall von RM-672. Fix: je Schlüssel ein Ereignis „wird gelesen", auf das ein zweiter
Aufrufer wartet und danach den abgelegten Eintrag nimmt; den RM-672-Fall mit und ohne Vorwärmen messen.

### L5 Die PATH-Antwort bleibt ein Nein bis zum Neustart; Prüfen-dann-Lesen gegen `forget_cache`

`app/core/discover.py:484-491`. Unter Linux ist der PATH laut Modulkopf „die richtige Antwort": Ein Slicer, den
der Kunde während der Sitzung über den Paketverwalter installiert, bleibt für Export und Grundlage unsichtbar,
bis *Erneut suchen* oder ein Neustart `forget_cache` auslöst — vorher fand ihn der nächste Export. Dazu
`if key in _on_path: known = _on_path[key]`: Leert ein anderer Faden dazwischen (`install.py:605`), fliegt
`KeyError` im Exportarbeiter, wie beim Zwilling `_cache` (`:459-460`). Fix: `_on_path.get(key, _UNASKED)`; die
Grenze in `druckerwahl.md` nennen oder ein Nein nur begrenzte Zeit merken.

### L6 *Erneut suchen* verwirft den gemerkten Bestand nicht

`print_settings_dialog.py:7116` (`recheck_slicer`) und `install.py:605` rufen `discover.forget_cache()`;
`_holdings`, `_prusa_models` und `_program_folders_seen` sehen davon nichts. Übersieht die Signatur eine Änderung
— bewusst unterhalb der obersten Ebene der Installation, `test_the_installation_is_read_again_with_a_new_version_only`
hält es fest —, hilft dem Kunden nur ein Neustart. Das Muster für „wer selbst merkt" steht in
`discover.py:335-337` (`cache_generation`), `appimage.ImageCopies._failed` folgt ihm. Fix:
`discover.cache_generation()` in die Schlüssel der drei Merker.

### L7 Zwei Tests prüfen weniger, als sie sagen

- `tests/test_slicer_profiles.py:5122` `test_a_store_that_just_changed_is_not_kept` hängt an der Wanduhr: Beide
  Aufrufe müssen binnen 2 s nach der letzten Schreibung der Fixture fertig sein, unter Last nicht sicher; bei
  `count == 0` wäre er leer grün. Fix: Zeitstempel und `sp.time.time_ns` festlegen, `count > 0` zusichern.
- `tests/test_ui_export.py:675` `test_the_3mf_export_reads_the_slicer_stock_in_one_pass`: Im Fenstertest findet
  `discover.find_program` keinen Slicer (Attrappe `conftest.py:598-599`), `setup` bleibt `None`, kein Profil wird
  gelesen. Er zeigt, dass `base_settings` in einem offenen Durchgang läuft, nicht dass Vorwahl, Stufe, Grundlage
  und Datei jede Datei einmal lesen — das Archiv führt ihn als Nachweis dafür. Fix: mit `cc2_stock` und
  gemerktem Slicer exportieren, `_load` je Pfad zählen (höchstens einmal); Gegenprobe ohne den äußeren Durchgang
  rot.

### L8 Der Changelog verspricht vor der Abnahme mehr, als belegt ist

`changelog/de.md:99` und die fünf Übersetzungen: „… ist ein 3MF-Export in Sekundenbruchteilen fertig, kaum
langsamer als ein STL-Export." Die Abnahme steht im Register offen; mit offenem ElegooSlicer gilt es nach M1
nicht, und „in Sekundenbruchteilen fertig" stimmt für ein großes Modell nie. Fix: nach Abnahme und M1 relativ
formulieren, etwa „Mit installiertem Slicer ist ein 3MF-Export kaum langsamer als ein STL-Export." in allen
sechs Sprachen.

### L9 Das Register lockert die Abnahme ohne Vermerk

`ROADMAP.md:3256-3264` gegen welle2: Weggefallen sind „die Maschinenbefunde beim *Slicen* unverändert (Tests
über den echten Exportweg)", „ein im Slicer neu angelegtes Druckerprofil kennt der nächste Export" (über das
Fenster nach M2 nicht erfüllt) und „Bauplan §29, §31"; dazugekommen ist „(nach dem Vorwärmen)" beim ersten
Export. Fix: die Punkte zurück in die offene Abnahme, die Lockerung als Entscheidung kennzeichnen oder streichen.

## Geprüft ohne Befund

- **Regeln (regelcheck):** 1 (der Kern zieht nur `time` dazu), 6 (Nanosekunden als Ganzzahl, kein Float-`==`),
  7 und 8 (`SETTLE_NS`, `SLICER_WARMUP_DELAY_MS` sind benannte Zeitkonstanten mit Grund, keine Toleranzen), 10
  bis 13 (nichts ausgeführt, keine Pfade in Projektdateien), 17 (keine neue Ausnahme), 20 (kein neuer
  Oberflächentext; der Protokollsatz ist englisch), 22 (keine Abhängigkeit). 2–5, 9, 14–16, 18, 19 nicht
  berührt. Bezeichner englisch, Docstrings deutsch mit Umlauten.
- **Installation in der Signatur:** Windows über die Programmdatei (`elegoo-slicer.exe` wird je Fassung neu
  gebaut) und die Herstellerbündel der obersten Ebene; AppImage über das Abbild (Pfad, Zeit, Größe) — die Kopie
  liegt unter dem Hash des Pfads, ihr Name allein ändert sich nicht; Flatpak über `realpath` durch
  `current/active`, das den Commit nennt, am Starter wie an `files`, auch aus Solidons Flatpak
  (`/var/lib/flatpak/app:ro` im Manifest). Eigene Profile liegen in allen drei Formen in einer eigenen Wurzel und
  gehen Datei für Datei ein. Im Slicer angelegte, umbenannte und gelöschte Profile erreichen den nächsten Aufruf
  von `find_profiles` (Tests mit Gegenprobe, alle grün).
- **Nebenläufigkeit:** Der Lesedurchgang ist je Faden (`threading.local`), verschachtelt gilt der äußere, `finally`
  räumt; `_HOLDINGS_LOCK` schützt nur den Zugriff, gelesen wird außerhalb, keine Verschachtelung mit
  `_PRUSA_LOCK`. Das Vorwärmen im Daemon-Faden fasst kein Qt an, fängt und protokolliert seine Fehler, startet
  nicht nach `_close_requested`; der Zeitgeber hängt am Fenster.
- **Druckbefunde nach dem Export:** Warten, Schreiben, Abbruch des wartenden Exports, Abbruch der Prüfung,
  Fehler, Absturz des Arbeiters, Bestätigungsfrage, neuer Stand während des Schreibens und Schließen enden
  jeweils in `_export_worker_done` oder `_cancel_export`; kein Weg lässt die Befunde liegen. §2.8: Neu im
  Hauptthread ist nur Zustandslogik.
- **Speicher des Durchgangs:** Der Exportdurchgang umfasst jetzt das Schreiben und hält dabei rund 1 000
  Dokumente (Spitze 9,7 MiB) — vertretbar.
- **Budgets:** `druckerwahl.md` 8 309, `wartezeit.md` 28 724 (Grenze 30 720); `app/core/export/CLAUDE.md`
  25 371, `app/ui/CLAUDE.md` 24 900, `tests/CLAUDE.md` 25 507 (Grenze 25 600, 93 Byte Luft);
  `test_directory_docs.py` grün. Verschoben, nicht gelöscht: die Reihenfolge von `match_filament` nach
  `karte-app-core-export.md`, der Grund zur Güte nach `regel-wartezeit.md`; der `grabWindow`-Satz steht weiter in
  `ansicht.md:515-526` und `regel-wartezeit.md:74-76`.
- **mypy und `ruff check`** grün; Changelog-Ton kurz und ohne Bewertungsvokabeln, `test_changelog.py` grün.

**Kann das so rein? Nein:** Das Tor ist rot (L1), und die Zusage des Zweigs hält in Roberts eigenem Weg nicht —
mit offenem ElegooSlicer verfällt der Merker (M1), und der Fensterexport sieht Bestandsänderungen über
`_ChosenSetup` nicht (M2); dazu M3. Nach den Fixes das Tor und, bei drei mittleren Befunden, eine Nachprüfung.
