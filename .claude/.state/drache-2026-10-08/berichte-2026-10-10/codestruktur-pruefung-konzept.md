# Prüfbericht `konzept`-Agent zu `konzept-codestruktur.md` (11.10., Entwurf 13:20)

Urteil: in dieser Fassung nicht abgabefähig; nach S1–S4 abgabefähig. Prüfskripte und Ausgaben:
`F:\tmp-agenten\struktur\pruef\` (zaehlen, doppelt, mixin_probe, mixin_probe2).

## Schwer
- **S1** Paket-`__init__` lädt Teile — widerspricht `app/core/bootstrap.py:3-6` (Register an einer
  Stelle, nicht als Nebenwirkung eines Paketimports), `app/core/CLAUDE.md:180-190` Muster 1 (träge
  `__init__`), `app/core/lazy.py:1-15` (Deadlock); Wettlauftest `tests/test_core_isolation.py:186-273`.
  Vorschlag: `__init__` nur Docstring; Bootstrap-Liste nennt die Teilmodule in heutiger Reihenfolge, W3 belegt.
- **S2** W2 deckt den Fall „Name nach dem Schnitt in mehreren Modulen gelesen“ nicht
  (`"app.ui.main_window.show_error"` 14× als Text; Modulpatches: features 115, main_window 69,
  viewport 44); `raising=False` 22× (zwei auf features, `tests/test_features.py:4203-4204`).
  Vorschlag: W2 hält je Patch die Menge der lesenden Funktionen vorher/nachher gleich; Werkzeug
  schreibt Patch je lesendes Modul um; nicht auflösbare Ziele in schrumpfender Liste.
- **S3** Quelltextwächter lesen `app/ui/*.py` / `perceive/*.py` flach per `glob("*.py")` (~19 Stellen,
  8 Dateien: test_leash 477/950/1147, test_style 510/912/917/1200/1370, test_ui 15991/16869,
  test_value_labels 756, test_widget_lifetime 426/584, test_native_keys 419, test_features 2999),
  meist Verbotsprüfungen → nach dem Schnitt still grün. `tools/affected_tests.py:74` kennt `glob(`
  nicht als Baumleser. Leser über `Path(modul.__file__)` (test_finding_actions 363, test_first_run
  1903, test_action_effects 181, test_ui 10167, test_features 3149/3723, test_viewport_decisions
  7495, test_errors 721) lesen danach nur `__init__.py`. Wörtliche Pfade: main_window.py ≥ 15,
  viewport.py 11. Vorschlag W4: rekursiv lesen, flaches glob über app/ verboten (Ausnahme
  activation); `__file__`-Leser nennen das definierende Modul.
- **S4** `def f(self: MainWindow)` im Mixin lehnt mypy 2.4.0 strict ab (gemessen: „erased type of
  self … is not a supertype of its class“). Grün: Wirtsprotokoll unter TYPE_CHECKING als Basis.
  `@Slot` in keiner Großdatei (nur `support_dialog.py`, 2×). Mixins nirgends in app/; bestehendes
  Muster `PlacementFlow` + `PlacementHost(Protocol)` (`placement_flow.py:156`, `:1552`).
  Vorschlag: Mixin oder eigenes Objekt mit Wirtsprotokoll in der Probe entscheiden; Test hält
  Protokoll an der Klasse; geprüft super() (MainWindow 3, Viewport 10, PrintSettingsDialog 6,
  SketchCanvas 5), Property+Setter, Qt-Overrides.

## Mittel
- **M1** Ladelast-Gewinn ist Messartefakt (`docs_scan.py:181-194` zählt nur eigene Karte; Codex liest
  alle Karten der Kette). Abnahme mit allen Karten auf dem Weg; Gewinn aus Regel 7. Luft gemessen:
  main_window 469 B, placement_flow 964 B.
- **M2** Bereichsnachweis: `boolean`, `mesh` ausgenommen (`_NOT_SHAPE`, `range_proof.py:87-96`);
  im Abdruck `_SHARED` (`:71-81`: geom/intersections, brep/profiles, knowledge/standards, parts/*)
  und direkte geom-Importe (lathe, transform `shapes.py:29`, contours `section.py:27-29`,
  geom/prepare `fasteners.py:1228`); relativer Pfad im Hash (`:240`) → Teilen von geom/prepare.py
  kostet Neunachweis der Befestiger; „3,5 h“ unbelegt. Satz „kein gespeicherter Zustand“ zu weit
  (Bereichsnachweis, CI-Laufzeittabellen). Abnahme: Bereichsnachweis ohne `stale`.
- **M3** Sperrklinke im Betrieb: Zahl steigt nie; Neues in neues Modul, neue Tests in
  `test_<thema>_<bereich>.py`; Liste ändern nur Verschiebeschritte; sinkt eine Datei, darf die Zahl
  stehen bleiben (keine Konflikte).
- **M4** „Nur verschoben“ für 30 000 Zeilen: Werkzeug beweist per `ast.dump` je Definition;
  Unterstriche in eigenen Commit; `global`-Schreiber zusammenhalten (evaluate 5×, panels 1×).
- **M5** „Keine andere Sitzung ändert die Datei“ = Sperre, widerspricht Entscheidung Robert (kein
  Brett, kein Schloss). Stattdessen: Schnitt als Skript, auf jedem Stand neu erzeugbar; Werkzeug
  trägt Diffs eines Zweigs je Definition nach.
- **M6** Späte Importe in `tools/` prüft niemand (mypy nur `app`): make_figures 636, make_guides
  1828, make_video 2241 (privat `_feature_item`), make_workshop_videos 1694 → statischer
  Importwächter für `from app.… import N` in app/, tools/, tests/, auch in Funktionen.
- **M7** UI-Schritte landen ungeprüft auf main (Fenstertests nur Release/CI auf main) → Frage an
  Robert: für Schritte 4–6 vor dem Merge die von `tools/ci_selection.py` genannten Fenstertests lokal.

## Leicht
- **L1** Tabelle 2.4: Lazy-Exporte `scene/__init__.py:50-51` („evaluate“), `agent/__init__.py:35`;
  Testaufteilung hängt an `tests/data/ci_*_durations.json` (`tools/ci_shards.py:54-57`), nicht an
  `fenster-auswahl.yml`; `.claude/agents/solidon3d-schicht.md:62` nennt `export/handover.py`
  (→ sync_agents); Logger-Namen unkritisch bei gleichem Paketnamen (caplog placement_flow 3×,
  evaluate 8×); Bauplan §11.3 (Zeile 937) nennt `app/core/slice/analysis.py` → Bauplanänderung mit
  Ansage; `ui/panels` (Zeile 3504) fehlt.
- **L2** W3: alle Felder des Registereintrags außer `fn`.
- **L3** `tests.md` hat 28 B Luft; eine „Git-Regel“ unter `.claude/rules/` gibt es nicht.
- **L4** 4 519 Commits inkl. Merges (ohne 3 789); Zahlen je Datei ohne Merges — Basis einheitlich.
- **L5** Kosten fehlen: Startzeit §31 je UI-Schritt; eigene Bausteine (§24.5), die verschobene
  Module importieren → Changelog-Hinweis.
- **L6** Alternative „Herauslösen beim Anfassen“ fehlt in Abschnitt 5; Gesamtaufwand fehlt.
- **L7** Freigabeliste: `LGPL-3.0-only`, nicht `-or-later` (`licences.toml:157-159`) → „rope zulässig“ prüfen.

## Stichproben, die stimmen
Zeilen der 14 Dateien und Bereichstabelle; MainWindow 26 529/892, Viewport 13 975/445,
PlacementFlow 4 556/116; 23 register_op; Karten-/Regelgrößen; Ladelast 160/160/152/146/145/141;
BOUNDARY_FILES; module_collection_mode (`solidon3d.spec:283-287`); `_OPERATION_MODULES`;
monkeypatch (`_pytest/monkeypatch.py:241-246`); 131; 88 Text-Patches; 18 paths:-Nennungen.
