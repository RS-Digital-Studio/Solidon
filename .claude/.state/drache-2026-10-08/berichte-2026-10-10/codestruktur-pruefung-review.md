# Prüfbericht `solidon3d-review` zu `konzept-codestruktur.md` (11.10., Entwurf 13:20)

Urteil: nein in dieser Fassung; Messzahlen stimmen. Prüfstand welle5 `f850ef25c`, pytest 9.1.1,
PySide6 6.12.0, mypy 2.4.0 strict, Python 3.14.7. Skripte: `F:\tmp-agenten\struktur\pruef2\`
(scan_patches, ladelast, klassen, probe).

## Schwer
- **S1** Regel 3 (eifriges `__init__`) gegen `app/core/lazy.py:1-25` (Deadlock 5/5),
  `app/core/CLAUDE.md:180-192`; `test_core_isolation.py:186` nur einmaliger Wettlauf. Bootstrap nennt
  die Untermodule; Op-Blöcke zusammenhängend `prepare_ops.py:719`–`:23870`.
- **S2** Lebensdauer-Pin der Suite fällt still aus: `tests/conftest.py:318-319`, `:432-435` an
  `app.ui.main_window`/`app.ui.viewport` gebunden; `_pin_ui_widgets` (`:247-250`) holt
  `getattr(module, "MainWindow"/"Viewport", None)` und überspringt `None` stumm → nativer Abriss
  0xc0000374 (Docstring `:305-316`). Laut, aber im selben Commit: `:741` (`forget_remembered_steps`),
  `:895` (`panels.keep_sections_in`). Vorschlag: Zeile in 2.4 + Test, der `MainWindow._suite_pinned`
  und `Viewport._suite_pinned` verlangt (Marke `conftest.py:263`).
- **S3** Zehn Verbotstests lesen flach (`test_leash.py:477/950/1101`, `test_style.py:510/912/917/
  1200/1370`, `test_value_labels.py:756`, `test_native_keys.py:419`, `test_features.py:2999`);
  Gegenprobe `test_leash.py:1136-1151` verlangt nur ≥ 20 Dateien. W4: gemeinsamer rekursiver Helfer
  in `tests/helpers.py`; Gegenprobe verlangt die Definitionsmodule von MainWindow, Viewport, features.
- **S4** W2 blind für mehrere Leser nach Mixin-Teilung; Patches auf importierte Namen: main_window
  158/166 (`show_error` 45, `confirm_unsaved` 14, `check_before_export` 12), print_settings_dialog
  54/72, session 32/73, viewport 16/39; still bei verneinender Zusicherung (`test_ui_export.py:870`/
  `:879`). Heute 54 Kopfkopie-Paare (z. B. `features.detect` in `scene/evaluate.py:73`).
  Fehlalarme: 313 Patches wirken über andere Module (Attributzugriff `conftest.py:619` über
  `app/core/tools.py:109`; später Import `test_ui_audit_outcomes.py:49,61` über
  `tools/run_ui_audit.py:253`; `test_part_range_runner.py:75,142` über `tools/check_part_ranges.py:
  116,177`). Alias je Datei falsch für 32 Patches (`test_viewport_decisions.py:1121`) → Gültigkeit je
  Funktion. Text: wirksam, wenn M liest oder ein Modul in app/ oder tools/ `M.N`/getattr/späten Import
  nutzt; W2 meldet jede Kopfkopie; Mixin-Schritte: Fixture ersetzt importierte Namen in jedem Modul
  des Pakets; Verbotspatches mit Gegenprobe „erreicht“.

## Mittel
- **M1** mypy strict lehnt Selbsttyp ab (`erased type of self`, `@override` ohne Basis, `super()`
  Argument 2). Tragend: `# mypy: disable-error-code="misc"` je Mixin-Datei (Rumpf weiter gegen
  MainWindow geprüft) oder Protocol als Selbsttyp (alle Attribute deklarieren). Vorbild
  `_BoundedBehavior` (`app/ui/labels.py:540`) nutzt `self: Any`. Qt-Überschreibungen mit
  `@override`/`super()` im Rumpf: MainWindow 5, Viewport 9, PlacementFlow 1 (`placement_flow.py:525`).
- **M2** Merkschlüssel an Modulnamen: `scene/evaluate.py:4453-4462` `_STEP_WAY_MODULES`, `_step_ways`
  (`:4517-4524`) liest `vars(sys.modules.get(name))`, überspringt fehlende Module stumm;
  `perceive/matching.py:830` `globals()[name]` über `_MATCH_WAYS`. Zeile in 2.4 + Test „jeder Name löst
  auf und trägt mindestens eine Funktion bei“.
- **M3** `raising=False` 25×, davon `test_features.py:4203-4204`, Verbotspatch
  `writer._arrange_for_cli` (`test_slicer_placement_followups.py:117`); `create=True` 0.
- **M4** `test_registry_consistency.py:443-489` prüft nur Module mit Op (`inspect.getmodule(spec.fn)`)
  → `prepare_ops/shared.py` fiele heraus.
- **M5** Tabelle 2.4: `pyproject.toml:347-365` mypy-Ausnahmen je Modul (perceive.features,
  geom.repair, geom.prepare), Untermodule erben nicht; `main_window.py` ≥ 14 Stellen
  (`test_header.py:500`, `test_manual.py:1164`, `test_ui.py:9613/11477`, `test_translations.py:1433`,
  `test_action_effects.py:96-97/181` `Path(main_window.__file__).parent`, `test_interface_limits.py:
  2567/2623`, `test_style.py:2390`); Werkzeug muss Attributzugriffe über Modulaliasse umschreiben
  (`tools/matrix_unit.py:370/378/785`, in keiner Suite); Pfad als Text muss auf alle Dateien des Pakets
  zeigen (`test_shared_hosting_removed.py:81-95`).
- **M6** Ladelast-Abnahme durch Zählweise erfüllt (`docs_scan.py:181-194`).
- **M7** Heute wirkungslose Patches: `test_first_run.py:552/560` (`configured_spools`,
  `assert_not_called`; Aufrufer hält Kopie `app/ui/filament_inventory.py:62`, Aufruf `:1174`);
  `test_spatial_matching.py:122` verbietet `matching._cost_matrix` (`matching.py:180`), die niemand
  ruft (nur Zeichenkette in `_MATCH_WAYS`, `:942`).

## Leicht
- **L1** Luft 469 B (main_window, 164 395 B) / 964 B (placement_flow); rot erst ab 161 KB.
- **L2** Signal in Nicht-QObject-Basis funktioniert unter PySide6 6.12 (Probe); kein `@Slot`,
  `connectSlotsByName`, `invokeMethod`, `SLOT()` in den Großklassen (nur `support_dialog.py:1092/
  1102/1157`); Overrides und Verbindungen zu Mixin-Methoden laufen → `@Slot`-Probe entbehrlich.
- **L3** setattr: 4 761 Aufrufe (3 137 auf Module, 1 509 auf Objekte/Klassen, 115 als Text); 88
  Textziele auf `app.` stimmen.
- **L4** `.claude/agents/solidon3d-review.md:28` nennt `prepare_ops.py`.

## Ohne Befund
Loggernamen (`record.name` nirgends verglichen), Hooks, Skills, Workflows, Kernprozess
(`kernel_jobs.JOBS` über Auftragsnamen), Handbuch (`manual.py:2114-2141` Präfix, Titelsortierung),
`test_directory_docs` (prüft `paths:`-Ziele und §-Verweise, keine Modulnamen in Karten).
