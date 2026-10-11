# Nachprüfung RM-670 (`F:/solidon-claude-e`, Zweig `claude/lauf-e`, HEAD `c3bb26628`) — solidon3d-review, 09.10.2026

Geprüft: die Behebungen `5ea13ea0f` (13 Dateien, +152/−26) und `c3bb26628` (Testnachzug) gegen das erste
Review (`review_rm670.md`, 3 mittel, 9 leicht). Worktree sauber, keine fremden Änderungen. Dazu gelesen:
`_held`, `_holding_signature`, `_all_files`, `_settled`, `stock_signature`, `forget_holdings`, `_prusa_store`,
`_prusa_signature`, `_prusa_files`, `_PrusaStore.read`, `_prusa_printer_models`, `_program_folders`,
`_orca_profiles`, `_kind_of`, `_names_in`, `_chain`, `_json_files`, `_cura_profiles`, `_cura_machine_instances`,
`profile_roots`, `user_roots`, `find_profiles` mit allen Aufrufern; im Hauptfenster `_ChosenSetup`,
`_FoundationWorker`, `_ExportWorker`, `_warm_the_slicer`, `_warm_slicer`, `_on_busy`, `_print_foundation`,
`_foundation_key`, `_chosen_setup_now`, `_start_foundation`, `_foundation_found`, `_export_worker_done`; im
Druckdialog `remembered_setup`, `recheck_slicer`, `_show_slicer_state`, `_slicer_chosen`; `discover`
(`_from_path`, `find_program(s)`, `remember`, `forget_cache`), `tools.slicer_program(s)`; Regeln druckerwahl
und zwillinge, Skill regelcheck; Register und Archiv zu RM-670; Changelog in sechs Sprachen.

Ausgeführt — am Worktree nichts geändert (pytest mit `-p no:cacheprovider` und `PYTHONDONTWRITEBYTECODE=1`,
ruff mit `--no-cache`, mypy mit einer Kopie des Caches im Scratchpad; alle Läufe im Vordergrund beendet):
- Tests, jeweils Exit 0: die neuen und berührten Tests (12 passed); `test_slicer_profiles.py` 297 passed; am
  HEAD `c3bb26628` `test_export_background.py`, der nachgezogene
  `test_the_file_export_of_a_selection_asks_the_whole_job`, `test_discover.py`, `test_export.py`,
  `test_changelog.py`: 416 passed, 1 skipped; `test_ui_export.py` ohne Fenster- und Rendermarken 5 passed
  (48 abgewählt). `ruff check`, `ruff format --check` (8 Dateien) und mypy über die vier App-Module grün.
- Gegenproben als Laufzeitmutation (Plugin `mutants.py` im Scratchpad ändert die Quelle im Speicher; die
  Kontrollmutation an `_assembly_in_one_read` macht `test_the_export_writes_with_the_chosen_setup_without_deriving_it`
  rot, der Mechanismus greift also auch an Methoden):

  | Mutation | Ergebnis |
  |---|---|
  | M1: Artfilter weg (`_all_files(root)`) | rot, `test_slicer_profiles.py:5253` „Telemetrie ist kein Profil“ |
  | M3: Verdrängung weg | rot, `:5269` (6 statt 4) |
  | M3: Treffer stellt nicht nach hinten (`pop` → `get`) | **grün** |
  | M2: `and self._chosen.current()` im Export weg | **grün** (5 Tests) |
  | M2: Signatur im Grundlagenarbeiter `None` | **grün** (5 Tests) |
  | L2: `asked_at` weg | **grün** (20 Tests) |
  | L6: `forget_holdings()` in `recheck_slicer` weg | **grün** (4 Tests) |

- Sonden im Scratchpad, CPU-Zeit (die Maschine stand unter Fremdlast): `probe_rm670_nach.py` (Roberts
  ElegooSlicer: Signatur mit und ohne Filter, Vorwahl kalt und warm), `probe_m2_none.py` (echter
  `_FoundationWorker` an `cc2_stock`, APPDATA umgebogen), `probe_cura_signature.py` (Cura 5.13),
  `probe_filter_cost.py`, `kind_case_scan.py`, `changed_methods.py` (Frage des Koordinators). Dazu gelesen:
  `%APPDATA%\ElegooSlicer\user`, `%APPDATA%\cura\5.13`, `%APPDATA%\PrusaSlicer`, Curas `cura/AutoSave.py` und
  `UM/Qt/QtApplication.py`.
- Nicht gefahren: Tor, Fenster- und Rendertests (Vorgabe).

**Ergebnis: 0 schwer, 3 mittel, 6 leicht; L3, L4 und L7 weiter offen.**

## Stand der Punkte aus dem ersten Review

| Punkt | Stand | Beleg |
|---|---|---|
| M1 Telemetrie verwirft den Merker | **Für die Orca-Familie behoben**, für Cura und Prusa nicht (N3) | Sonde: aus der Signatur fallen `user\telemetry_cache\runtime_state\96048.json` und sieben Herstellerindizes unter `system\`, die der Leser nicht öffnet; Mutation rot |
| M2 Vorwahl ohne Signatur | **Zur Hälfte**: Fall 1 offen (N1), das Fenster erneuert nichts (N2), kein Anschlusstest | Sonde `probe_m2_none.py`; zwei Mutationen grün |
| M3 Speicher | **Zur Hälfte**: Wachstum über Slicer gekappt, Doppelablage je Slicer bleibt (N4) | Mutation Verdrängung rot, LRU grün |
| L1 Format | behoben | `ruff format --check` grün |
| L2 Beruhigung am Zeitpunkt der Signatur | in `_held` richtig, ohne Test, Zwillinge offen (N5) | Mutation grün |
| L3 `_prusa_store` ohne `SETTLE_NS` | offen | unten |
| L4 paralleles Lesen beim Vorwärmen | offen | unten |
| L5 PATH-Nein bleibt | entschieden; tragfähig, Begründung unvollständig (N7) | unten |
| L6 *Erneut suchen* leert den Bestand | wirkt nur, solange kein Slicer gefunden ist (N6) | Mutation grün |
| L7 zwei schwache Tests | offen | unten |
| L8 Changelog | behoben | sechs Sprachen gleich, im Abschnitt 0.6.0, `test_changelog.py` grün |
| L9 Register lockert die Abnahme | **weder behoben noch erwähnt** (N9) | `ROADMAP.md:3256-3264` |

## Mittel

### N1 M2 Fall 1 bleibt offen: Ergab die Vorwahl `None`, trägt sie keine Signatur, und `current()` sagt für immer ja

Stellen: `app/ui/main_window.py:1480-1487` (`current()` ist ohne `setup` oder ohne Signatur immer `True`),
`:1556-1562` (Signatur nur bei `setup is not None`), `:1943-1956` (der Export nimmt `self._chosen.setup`, bei
`None` den nackten `handover.detect`). Der neue Test schreibt die Lücke fest: `tests/test_ui_export.py:1760-1762`
(„ohne Slicer gibt es nichts zu vergleichen“) — `None` heißt aber auch „Slicer da, sein Bestand kennt den
Drucker nicht“ (`print_settings_dialog.py:417-419`).

Beleg (Sonde mit dem echten `_FoundationWorker`): `cc2_stock` ohne die drei CC2-Maschinen, ein leerer
Kontoordner `ElegooSlicer\user\default\machine`. Vorwahl `None`, Signatur `None`. Der Kunde legt
„Elegoo Centauri Carbon 2 0.4 nozzle“ im Kontoordner an: `stock_signature` ändert sich, `chosen.current()` bleibt
`True`. Neu hergeleitet ergäben sich Maschine `Mein CC2.json`, Prozess `standard.json`, Filament `pla.json`.

Warum es zählt: Das ist der erste Fall aus M2 und genau der Weg, den Solidon dem Kunden weist, wenn der Slicer
den Drucker nicht kennt. Danach meldet der Export nichts mehr (`machine_missing` sieht den Drucker), die Datei
geht aber bis zum nächsten Schlüsselwechsel ohne Herstellerprozess und -filament hinaus (RM-623). Die
Commit-Meldung sagt „ein im Slicer angelegtes … Profil erreicht den nächsten Export“.

Fix: `_ChosenSetup` merkt, wessen Bestand gefragt wurde, auch bei leerer Wahl:

```python
    stock: tuple[Path, SlicerFlavour] | None = None
    """Wessen Bestand gefragt wurde — auch, wenn die Wahl ``None`` ergab."""

    def current(self) -> bool:
        if self.stock is None or self.signature is None:
            return True
        executable, flavour = self.stock
        return slicer_profiles.stock_signature(flavour, executable) == self.signature
```

Im Grundlagenarbeiter (`:1556`) den Slicer über `tools.slicer_program()` (gemerkt, kostet nichts) und
`handover.detect` bestimmen und, wenn nicht `handover.only_opens`, Signatur und `stock` mitgeben — am besten in
einer Hilfsfunktion `_chosen_for(key, setup)`, die N2 mitbenutzt. Test in `test_print_settings_ui.py` neben
`:9953` nach dem Muster der Sonde: Maschinen aus `cc2_stock` entfernen, `user_roots` auf einen Kontoordner,
Maschine anlegen → `not chosen.current()`, danach `_ExportWorker(..., chosen=chosen)._assembly()` → die Datei
trägt den Herstellerprozess (`wall_loops` 2 statt Solidons 3, wie `:9997`). `test_ui_export.py:1760-1762`
umschreiben.

### N2 Rest von M2: Das Fenster übernimmt die neue Wahl nie — jeder weitere Export leitet neu her, Zahlenzeile und Datei gehen auseinander

Stellen: `main_window.py:1943-1952` (der Export leitet neu her und behält das Ergebnis für sich),
`:10464-10473` (`_export_worker_done` übernimmt nichts), `:25559-25566` und `:25592-25604` (`_chosen_setup` und
`_foundation_cache` ändern sich nur mit dem Schlüssel); Zusage im Docstring `:1465-1469` („Zahlenzeile und
Datei sicher mit derselben Wahl“).

Beleg:
- Sonde an Roberts ElegooSlicer ohne gemerkte Maschine: Vorwahl aus warmem Merker 0,52–0,69 s CPU je Aufruf
  (kalt 6,0 s). Nach jeder Profiländerung im Slicer sagt `current()` für den Rest der Sitzung nein; jeder
  Export zahlt diese Zeit wieder, bis sich Drucker, Material, Profilwahl oder Slicer ändern. Die Abnahme
  „zweiter 3MF-Export unter 0,5 s“ ist danach nicht mehr erreichbar — in Roberts Weg „Slicer daneben,
  nachbessern, wieder exportieren“.
- Ändert die Änderung die Wahl selbst (eigenes Profil unter dem Herstellernamen gespeichert; `_orca_profiles`
  setzt es an dieselbe Stelle, `slicer_profiles.py:3246-3267`), rechnen Zahlenzeile und Prüfbericht mit dem
  Herstellerprozess, die Datei mit dem eigenen. Vor dem Fix war beides alt, aber gleich.
- Kein Anschlusstest: Die Mutationen „`current()` im Export weg“ und „Signatur im Grundlagenarbeiter `None`“
  bleiben grün. Der neue Test (`test_ui_export.py:1741-1762`) prüft `current()` allein, mit gepatchter
  Signatur.

Fix: Der Export gibt die neue Wahl zurück, das Fenster übernimmt sie und rechnet die Grundlage nach.

```python
# _ExportWorker.__init__
        self.renewed: _ChosenSetup | None = None
# _ExportWorker._assembly_in_one_read
        chosen = self._chosen
        if chosen is not None and chosen.current():
            setup = chosen.setup
        else:
            setup = remembered_setup(
                self._ui_settings, self._material, self._profile.printer.id, cancelled=self.cancelled
            )
            if chosen is not None:
                self.renewed = _chosen_for(chosen.key, setup)
# MainWindow._export_worker_done, im Zweig des eigenen Arbeiters
            renewed = getattr(worker, "renewed", None)
            if (
                renewed is not None
                and self._chosen_setup is not None
                and renewed.key == self._chosen_setup.key
            ):
                self._chosen_setup = renewed
                quality = self.effective_print_settings().quality
                self._start_foundation(self._foundation_key(quality), quality)
```

`_start_foundation` gibt die erneuerte Wahl mit, der Arbeiter leitet nichts neu her, `_foundation_found` zeigt
Zahlenzeile und Prüfbericht neu. `getattr` hält die Ersatzarbeiter in `test_export_background.py:115` und
`:134` lauffähig. Tests: Export mit `_ChosenSetup(key, alt, ("vorher",), stock)` und `stock_signature` auf
`("nachher",)` → `remembered_setup` wird gefragt, die Datei trägt die neue Wahl, `worker.renewed` die neue
Signatur (macht die erste Mutation rot); `_export_worker_done` an einem Ersatzfenster übernimmt und startet die
Grundlage; im Grundlagentest `test_print_settings_ui.py:9989` zusätzlich
`chosen.signature == slicer_profiles.stock_signature("orca", executable)` (macht die zweite rot).

### N3 M1 gilt nur für die Orca-Familie: Curas und PrusaSlicers Signatur zählen Programmeinstellungen

Stellen: `slicer_profiles.py:3120` (`_KIND_FOLDERS if flavour == "orca" else None`), `:3072-3079`
(`stock_signature` für jede Familie über `_holding_signature`), `:3012-3015` (Zusage: „Was daneben liegt —
Curas Protokoll … — darf den Merker nicht verwerfen“), `:3404-3415` und `:3626-3642` (`_prusa_files`,
`_prusa_signature`); was Cura liest: `:2380-2385` (`_CURA_DIRS`), `:1561-1592` (`_cura_machine_instances`).

Beleg:
- Cura 5.13 auf dieser Maschine: In der Signatur stehen `cura.cfg` und `plugins.json` von der obersten Ebene
  des Versionsordners; der Leser öffnet keine von beiden (er liest `definitions`, `extruders`, `variants`,
  `quality`, `intent`, `quality_changes`, `materials`, `machine_instances`, `definition_changes`, `user`).
  `plugins.json` trägt den Beginn, `cura.cfg` das Ende der letzten Cura-Sitzung (28.09., 08:10 und 08:33;
  `cura.log` 08:33). Dazu schreibt Curas AutoSave `cura.cfg` zehn Sekunden nach jeder Einstellungsänderung
  (`cura/AutoSave.py`: `preferenceChanged` → `saveSettings()`), und jede in Cura geöffnete Datei ändert
  `cura/recent_files` (`UM/Qt/QtApplication.py:368-383`). Die 643 Maschinen neu zu lesen kostet 1,03 s CPU,
  aus dem Merker 0,00 s.
- PrusaSlicer: `stock_signature("prusa")` — nur `_ChosenSetup` fragt sie — läuft rekursiv über den ganzen
  Konfigurationsordner, auch über `cache/` (die Update-Downloads, die `_prusa_files` ausdrücklich draußen
  lässt; hier 13 Dateien), `workflows.json` und `ArchiveRepositoryManifest.json`. Der Prusa-Bestand selbst
  erkennt sich an `_prusa_signature`. Vorbestehend, gleiche Art: `_prusa_files` nimmt auf der obersten Ebene
  jede `*.ini`, also `PrusaSlicer.ini` und `PrusaSlicerGcodeViewer.ini`, die PrusaSlicer beim Beenden
  schreibt; `_PrusaStore.read` findet darin keinen Profilabschnitt (`:3502-3508`), `_prusa_cache` verfällt
  trotzdem.

Warum es zählt: Für Cura verfällt der Merker mit jeder Cura-Sitzung und nach dem Öffnen einer neuen Datei in
Cura — der Weg aus M1, nur mit Cura. Für Cura und Prusa sagt `_ChosenSetup.current()` danach nein, und mit N2
leitet jeder weitere Export neu her. Die Abnahme nennt Cura und PrusaSlicer ausdrücklich. Dazu steht hinter dem
Filter `== "orca"` statt eines Prädikats (`zwillinge.md`, „Woher sie kommen“).

Fix: Eine Stelle sagt je Familie, was der Leser unter einer eigenen Wurzel ansieht, und Leser und Signatur
nehmen beide sie: die Orca-Familie die Artordner aus `PROFILE_DIRS` irgendwo im Pfad, Cura die Ordner der
ersten Ebene, die `_CURA_DIRS` und `_cura_machine_instances` lesen (eine Konstante, die beide Leser benutzen,
sonst entsteht der nächste Zwilling); `stock_signature` gibt für Prusa
`_prusa_signature(profile_roots("prusa", executable))` zurück. Ob `_prusa_files` die Programmeinstellungen auf
der obersten Ebene des Konfigurationsordners auslassen kann, an `_PrusaStore` und `_prusa_configured` prüfen.
Tests: `test_curas_store_ignores_its_log_and_sees_a_new_machine` (`tests/test_slicer_profiles.py:5139`) um
`cura.cfg` und `plugins.json` erweitern; für Prusa eine Datei unter `cache/` → `stock_signature` gleich, eine
unter `print/` → anders.

## Leicht

### N4 M3: Die Doppelablage je Slicer bleibt, Kommentar und Commit sagen anderes

Stellen: `slicer_profiles.py:3002-3006`, `:3044-3054`; Aufrufer mit verschiedenen Arten: `handover.py:577`
(`machine`), `:602` (`process`, `filament`), `print_settings_dialog.py:2314` (alle drei),
`filament_picker.py:589` (`filament`), `profile_by_name` `slicer_profiles.py:3772-3782` (je eine Art).

Beleg: Export und Grundlage, Druckdialog und Filamentauswahl fragen für einen Slicer genau vier
Kombinationen, und alle passen unter `_HOLDINGS_LIMIT = 4`. Am ElegooSlicer nach den Messungen des ersten
Reviews 3,4 + 20,1 + rund 22 + rund 14 MiB — weiter rund 60 statt rund 24 MiB. Die Grenze kappt nur das
Wachstum über mehrere Slicer (höchstens vier Einträge, bis rund 4 × 24 MiB). Kommentar und Commit („ohne Grenze
rund 60 MiB je Slicer“) lesen sich, als wäre die Doppelablage behoben. Dass ein Treffer den Eintrag nach hinten
stellt, prüft kein Test (Mutation grün); der Test gibt jedem Slicer genau einen Aufruf.

Fix: Eine Anfrage, deren Arten ein gehaltener Eintrag desselben Slicers mit gleicher Signatur umfasst, bekommt
dessen gefilterte Liste; wer eine Obermenge ablegt, entfernt die Teilmengen desselben Slicers. Der Ausschnitt
gleicht für Orca und Cura einem Lesen nur dieser Arten (Doppelte je Art und Name, Erbketten je Profil; nur die
Schranke `MAX_FILES` zählt über alle gelesenen Arten) — mit einem Test, der beides je Kombination vergleicht
(`cc2_stock`, Cura-Bestand). Sonst den Kommentar ehrlich machen. Im Grenztest vor dem fünften Slicer einmal den
ältesten fragen.

### N5 L2: richtig, aber ohne Test, und die zwei Zwillinge messen weiter nach dem Lesen

Stellen: behoben `slicer_profiles.py:3040-3050`; unverändert `:2063-2071` (`_prusa_printer_models`) und
`:444-453` (`_program_folders`).

Beleg: `asked_at` liegt vor dem Lesen, und das genügt auch im Lesedurchgang, in dem die Signatur älter sein
kann: Was nach `asked_at` geändert wird, bekommt bei `asked_at − jüngster Stempel ≥ SETTLE_NS` einen neuen
Stempel; was zwischen der älteren Signatur und dem Lesen geändert wurde, liest das Lesen mit, denn Auflistungen
entstehen im Durchgang erst nach der Signatur (`_json_files` hat nur `_orca_profiles` als Aufrufer). Der Einwand
des ersten Reviews zum Durchgang trägt also nicht. Aber die Mutation „`asked_at` weg“ bleibt grün, und die zwei
Zwillinge sind weder angepasst noch als anders entschieden (`zwillinge.md`); beide lesen kurz, die Gefahr dort
ist klein.

Fix: in beiden Zwillingen `asked_at = time.time_ns()` vor Stempel bzw. Signatur und `_settled(..., asked_at)`.
Test:

```python
def test_the_settle_time_is_taken_before_the_read(
    slicer: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    newest = max(entry[1] for entry in sp.stock_signature("orca", slicer))
    clock = {"now": newest + sp.SETTLE_NS - 1}
    monkeypatch.setattr(sp.time, "time_ns", lambda: clock["now"])
    original = sp._orca_profiles

    def slow(*args: Any) -> list[sp.SlicerProfile]:
        clock["now"] += sp.SETTLE_NS  # das Lesen dauert über die Schwelle
        return original(*args)

    monkeypatch.setattr(sp, "_orca_profiles", slow)
    sp.find_profiles(slicer, "orca", ("machine",))
    assert not sp._holdings, "gemessen am Zeitpunkt der Signatur, nicht nach dem Lesen"
```

### N6 L6: Der Weg zu `recheck_slicer` steht nur offen, solange kein Slicer gefunden ist

Stellen: `print_settings_dialog.py:7116-7120`; `:6523-6526` und `:6796-6799` (*Zusätzliche Programme …* nur
ohne gefundenen Slicer); `main_window.py:9025-9032` (einziger Aufrufer von `recheck_slicer`);
`slicer_profiles.py:3018-3019` (Docstring „für Tests“); `discover.py:494` („*Erneut suchen*“).

Beleg: Einen Knopf oder Text „Erneut suchen“ gibt es in `app/` nicht. `recheck_slicer` läuft nur nach dem
Umweg über *Zusätzliche Programme …*, und diesen Knopf zeigt der Dialog nur ohne gefundenen Slicer. Der Fall
aus L6 — ein Slicer ist da, seine Signatur übersieht eine Änderung unterhalb der obersten Ebene der
Installation — hat damit weiter nur den Neustart. *Programm wählen …* (`_slicer_chosen` →
`discover.remember_path` → `forget_cache`, `:7078-7091`) lässt den Merker stehen. `forget_holdings` leert
`_prusa_cache` nicht. Mutation grün.

Fix: wie im ersten Review vorgeschlagen `discover.cache_generation()` in die Schlüssel von `_holdings`,
`_prusa_models` und `_program_folders_seen` — dann leert jeder Weg, der `forget_cache` auslöst, auch die Merker.
Docstring von `forget_holdings` und den Kommentar in `discover.py:494` an die echten Wege anpassen. Test:
`discover.forget_cache()` → der nächste `find_profiles` liest neu.

### N7 L5: tragfähig, aber unter Linux zeigt der Druckdialog einen Slicer, den der Export nicht findet

Stellen: `discover.py:484-496` gegen `:528-531` (`find_programs` fragt den PATH jedes Mal) und `:459-469`
(`_cache` merkt das Nein der Ordnersuche schon vor RM-670); `tools.py:325-342`.

Beleg: Für Windows trägt die Entscheidung (0,4 s je Export; ein Installationsprogramm ändert den PATH des
laufenden Prozesses nicht; das Nein der Ordnersuche merkte `_cache` schon vorher). Unter Linux legt der
Paketverwalter den Slicer in einen Ordner, der schon im PATH steht: Der Schlüssel bleibt gleich,
`tools.slicer_program()` (Export, Grundlage) bleibt beim Nein, `tools.slicer_programs()` (Druckdialog) findet
ihn. Wählt der Dialog ihn als einzigen von selbst, merkt er nichts (`print_settings_dialog.py:6923-6925`), und
*Zusätzliche Programme …* ist verborgen: Der Dialog zeigt den Slicer, der Export schreibt ohne ihn — bis zum
Neustart oder bis der Kunde ihn ausdrücklich wählt. Für die Ordnersuche gilt dasselbe vorbestehend auf allen
Plattformen. Selten, aber ohne sichtbaren Ausweg. Der Kommentar begründet nur Windows und nennt „*Erneut
suchen*“.

Fix: `find_programs` korrigiert, was es besser weiß: Findet es Fassungen, wo `_on_path` (gleicher Schlüssel)
oder `_cache["slicer"]` ein Nein halten, ersetzt es das Nein. Wenige Zeilen, ein Test über
`unpatched_find_program(s)` mit einem PATH-Ordner, in den nach dem ersten Nein eine Programmdatei kommt. Den
Kommentar um den Linux-Fall und den echten Ausweg ergänzen.

### N8 `_KIND_FOLDERS` ist ein Zwilling von `PROFILE_DIRS` ohne `casefold` und zerlegt jeden Pfad

Stellen: `slicer_profiles.py:3161-3163`, `:3193-3198` gegen `:178-182` (`PROFILE_DIRS`) und `:2940-2943`
(`_kind_of` vergleicht mit `casefold`).

Beleg: dieselbe Liste ein zweites Mal; der Leser vergleicht ohne, die Signatur mit Groß- und Kleinschreibung.
Auf dieser Maschine kommt keine abweichende Schreibweise vor (11 Wurzeln, 176 Artordner in Orca und
ElegooSlicer) — heute ohne Wirkung. Die Zerlegung jedes Pfads kostet messbar: am `ElegooSlicer\system`
(4 746 Einträge, 15 Läufe im Wechsel) 75,0 ms CPU je Signatur gegen 65,6 ms mit einem Merkmal je Ordner und
63,5 ms ganz ohne Filter, bei gleichem Ergebnis.

Fix: die Art je Ordner entscheiden, aus `PROFILE_DIRS` (für Cura nach N3 nur die erste Ebene):

```python
    folders = [(os.fspath(root), kinds is None)]
    while folders:
        folder, counted = folders.pop()
        ...
                if entry.is_dir():
                    folders.append((entry.path, counted or entry.name.casefold() in kinds))
                elif counted and entry.name.endswith(_HOLDING_SUFFIXES):
                    ...
```

### N9 L9 und die offenen Punkte stehen nicht im Register

Stellen: `ROADMAP.md:3256-3264`.

Beleg: Gegen `a9e4d3f64` fehlen weiter „die Maschinenbefunde beim *Slicen* unverändert (Tests über den echten
Exportweg)“, „ein im Slicer neu angelegtes Druckerprofil kennt der nächste Export“ (nach N1 weiter nicht
erfüllt) und „Bauplan §29, §31“; „(nach dem Vorwärmen)“ steht ohne Vermerk. L9 erwähnen weder `5ea13ea0f` noch
der Auftrag. L3, L4, L7 stehen nur in der Commit-Meldung — „Offene Arbeit steht im Register von `ROADMAP.md`
und nirgends sonst“ (`CLAUDE.md`). Das Archiv (`ROADMAP-ARCHIV.md:27343-27346`) führt den schwachen Test aus
L7 weiter als Nachweis.

Fix: die drei Abnahmepunkte zurück, die Lockerung als Entscheidung kennzeichnen oder streichen; was nach dieser
Runde offen bleibt, als Teil von RM-670 ins Register (den RM-672-Teil von L4 unter RM-672).

## Offen gelassen: L3, L4, L7 — jetzt beheben?

**L3 — ja, klein.** `slicer_profiles.py:3645-3662`; die Regel (`druckerwahl.md:101-102`) sagt es für beide
Merker zu.

```python
    _check_cancelled(cancelled)
    asked_at = time.time_ns()
    signature = _prusa_signature(roots, extra_file)
    key = (tuple(roots), signature)
    ...  # Treffer wie bisher
    cache = _PrusaCache(key, _PrusaStore(roots, cancelled=cancelled))
    with _PRUSA_LOCK:
        _check_cancelled(cancelled)
        if _settled(max((entry[1] for entry in signature), default=0), asked_at):
            _prusa_cache = cache
    return cache
```

Test mit gepatchter Uhr am `prusa_mini`-Bestand: knapp vor `SETTLE_NS` zwei Aufrufe → zweimal `_PrusaStore`
gebaut, ab `SETTLE_NS` einmal. Die Suite leert `_prusa_cache` nicht je Test (`conftest.py:704-711`); nach N6
macht es `forget_holdings` mit.

**L4 — ja, begrenzt (rund 25 Zeilen, zwei Tests); der Teil „Vorwärmen neben einem Laden kurz nach dem Start“
gehört mit Fenstermessung zu RM-672.** In `_held` je Schlüssel ein laufendes Lesen vermerken; wer denselben
Schlüssel fragt, wartet und fragt danach erneut (Treffer oder selbst lesen):

```python
_reading: dict[tuple[str, SlicerFlavour, frozenset[ProfileKind]], tuple[int, threading.Event]] = {}

    while True:
        asked_at = time.time_ns()
        signature = _holding_signature(flavour, executable)
        with _HOLDINGS_LOCK:
            ...  # Treffer wie bisher
            running = _reading.get(key)
            if running is None or running[0] == threading.get_ident():
                done = threading.Event()
                _reading[key] = (threading.get_ident(), done)
                break
        running[1].wait()
    try:
        ...  # lesen und ablegen wie bisher
    finally:
        with _HOLDINGS_LOCK:
            _reading.pop(key, None)
        done.set()
```

Kein neues Hängerisiko: Ein Wartender wartet so lange, wie er selbst lesen würde. Tests: zwei Fäden mit einem
`read`, das auf ein Ereignis wartet → ein Lesen; ein `read`, das wirft → der Wartende liest selbst.

**L7 — ja, beide klein.**
- (a) `tests/test_slicer_profiles.py:5122-5136` von der Wanduhr lösen und gegen leer sichern:

```python
    reads = _counting(monkeypatch, "_read")
    newest = max(entry[1] for entry in sp.stock_signature("orca", slicer))
    monkeypatch.setattr(sp.time, "time_ns", lambda: newest + sp.SETTLE_NS - 1)
    sp.find_profiles(slicer, "orca", ("machine",))
    count = len(reads)
    assert count > 0, "der Bestand hat Maschinen"
    sp.find_profiles(slicer, "orca", ("machine",))
    assert len(reads) == 2 * count, "unberuhigt nicht gemerkt"
    monkeypatch.setattr(sp.time, "time_ns", lambda: newest + sp.SETTLE_NS)
    sp.find_profiles(slicer, "orca", ("machine",))
    sp.find_profiles(slicer, "orca", ("machine",))
    assert len(reads) == 3 * count, "beruhigt gemerkt"
```

- (b) `tests/test_ui_export.py:675-708`: mit `executable = cc2_stock(tmp_path)` und
  `monkeypatch.setattr(tools, "slicer_program", lambda: executable)` exportieren und echte Lesungen zählen
  (`_load` umhüllen, gezählt nur, wenn `_pass_documents(documents)` die Datei noch nicht hat);
  `assert loads and max(loads.values()) == 1`. Einmal ohne `single_read` gegenprüfen, dass er rot wird.

## Nachgebaute Arbeiter (Frage des Koordinators)

Gesucht über `tests/`: `_ExportWorker._…`, `_FoundationWorker.(work|_in_one_read)`, `._assembly(`,
`_assembly_in_one_read`, `_in_one_read`, AST-Nachbauten (`worker.body`, `ast.Module(`), `MethodType` und
`__get__`; dazu systematisch (`changed_methods.py`) jede Methode, die RM-670 in `main_window.py` und
`print_settings_dialog.py` geändert oder neu angelegt hat (17), gegen ungebundene Aufrufe `Klasse.methode(`.

- `_assembly` an einem Ersatzobjekt rufen nur `test_print_settings.py:8512-8532` (in `c3bb26628` nachgezogen)
  und der AST-Nachbau `test_export.py:285-358` (in `5ea13ea0f` um `_assembly_in_one_read` und `slicer_profiles`
  ergänzt). Beide setzen `_chosen=None`; `current()` wird dort nicht erreicht.
- `_FoundationWorker.work` oder `_in_one_read` baut kein Test nach. Der einzige Ersatz-Grundlagenarbeiter
  (`test_print_settings_ui.py:10031-10037`) ist eine Fabrik für `_start_foundation` und ruft `work` nie.
- Echte Arbeiter, unbedenklich: `test_print_settings_ui.py:8341`, `:9932`, `:10093`,
  `test_print_contract_ui.py:784`, `test_filament_workflow.py:59` und `:782`; `test_ui_export.py:788-789`
  ersetzt `_assembly` ganz. `_ChosenSetup` mit zwei Argumenten (`test_print_settings_ui.py:10029`, `:10070`,
  `:10102`) hat keine Signatur und verhält sich wie vorher.
- Die übrigen ungebundenen Aufrufe geänderter Methoden stehen alle in `test_export_background.py` (`_on_busy`,
  `start`, `_warm_slicer`, `_export_when_current`, `_export_worker_done`, `_cancel_export`,
  `_start_print_findings`, `_print_findings_after_export_ended`), mit RM-670 geschrieben — am HEAD grün.

Weitere Lücken dieser Art gibt es nicht. Wer N2 behebt, muss `_export_worker_done` mit
`getattr(worker, "renewed", None)` schreiben, sonst brechen die Ersatzarbeiter in `test_export_background.py`.

## Geprüft ohne Befund

- **Telemetrie in echter Lage:** Bei ElegooSlicer ist `user\telemetry_cache` eine eigene Wurzel neben
  `user\default`, kein Unterordner des Kontos wie im Test; der Filter greift in beiden Lagen (relativ zur
  Wurzel). `user` hat seinen Zeitstempel seit 14.07., die Wurzelmenge bleibt stabil. Die sieben Dateien unter
  `system\`, die mit dem Filter wegfallen, öffnet der Leser nicht (`_kind_of`, `_names_in`, `_family` gehen
  nur in Artordner).
- **Nebenläufigkeit des Merkers:** `pop` und Wiedereinfügen unter derselben Sperre; ein Fehlgriff entfernt den
  alten Eintrag, das Ablegen hängt hinten an, die Verdrängung nimmt vorn — nie den eben abgelegten.
  `forget_holdings` während eines Lesens: Der Leser legt danach einen Eintrag mit seiner eigenen Signatur ab,
  das ist stimmig. `_program_folders_seen` ohne Sperre, aber mit atomaren Dict-Zugriffen.
- **Fehlender Ordner:** `_all_files` und `_top_level` fangen `OSError` und liefern leer; eine verschwundene
  Programmdatei ergibt `(Pfad, 0, -1)` und damit eine andere Signatur — `current()` sagt nein, der Export
  leitet neu her.
- **`current()` im Hauptthread:** nein. Es läuft nur im Exportarbeiter, im Lesedurchgang, wo die Signatur mit
  `_held` geteilt wird (0,09–0,13 s CPU, einmal je Export); `_chosen_setup_now()` vergleicht nur Schlüssel.
  `stock_signature` im Grundlagenarbeiter liegt im selben Durchgang hinter dem Lesen, Wahl und Signatur passen
  zusammen.
- **Wettlauf aus L5** (`key in _on_path`, dann `_on_path[key]`): CPython 3.14.7 mit aktivem GIL; zwischen den
  beiden Zugriffen liegt kein Unterbrechungspunkt des Interpreters, und ein Schlüssel aus Zeichenketten ruft
  keinen Python-Code. Kein Befund, ebenso beim Zwilling `_cache`.
- **Regeln:** 1 (der Kern zieht nichts Neues), 6 (Nanosekunden als Ganzzahl), 7 und 8 (`_HOLDINGS_LIMIT` ist
  eine Speichergrenze, keine Toleranz und kein Projektparameter), 10–13, 17 (keine neue Ausnahme), 20 (kein
  neuer Oberflächentext), 22 (keine Abhängigkeit). Bezeichner englisch, Kommentare und Docstrings deutsch mit
  Umlauten. Übrige Regeln nicht berührt.
- **Changelog:** sechs Sprachen sagen dasselbe, kurz, im Abschnitt 0.6.0.

**Kann das so rein? Nein:** Der erste Fall aus M2 ist nachweislich offen (N1), das Fenster übernimmt eine neue
Wahl nie und zahlt sie danach bei jedem Export (N2), und M1 gilt nicht für Cura und PrusaSlicer (N3); die
Behebungen von M2, L2 und L6 haben keinen Test, der ohne sie rot wird, und L9 ist unberührt. Nach den Fixes, bei
drei mittleren Befunden, eine weitere Nachprüfung.
