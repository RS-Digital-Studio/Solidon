# Nachprüfung `konzept`-Agent zum Konzept Funktionsdurchgang (11.10., Fassung 20:07)

Urteil: nach N1–N7 abgabefähig, ohne neue Runde. S1, S3, S4, E/V, M2–M6, M8, L1–L5, H1, H3–H7,
M1–M5, M7, M8, G1, G2 behoben; S2, M1 (bedienlogik), M7, H2, M6, G3, G4 teilweise.

- **N1 (mittel)** Kategorie-Wächter widersprüchlich: `sculpt_strokes`, `pose_armature` haben
  `category="mesh"` (`sculpt.py:2064`, `pose.py:942`); `scene` und `surface` ohne Paket → Zuordnung je
  Operation aus dem Register (`import`, `export` → D1; `primitive`, `parts`, `variants` → D2;
  `boolean`, `transform`, `shaping`, `surface` → D3; `holes` → D4; `repair`, `mesh` → D5;
  Gestenparameter `strokes`, `armature` → D6; `sketch` → D7; `scene`, `prepare` → D8; `colour`,
  `label`, `fits`, `parameters` → D10); Wächter: jede Operation genau einem Paket.
- **N2 (mittel)** 50 Bausteine (83 = `catalogue_operations()`), 190 Operationen; 90 Aktionen = 190 − 8
  Zwillinge − 9 Variantenmitglieder − 83 Katalogoperationen.
- **N3 (mittel)** W1-Satz in §9 ohne Regel-6-Zusatz.
- **N4 (leicht)** Verweise auf künftige Ablagepfade; §2 und §9 einheitlich mit heutigen Pfaden.
- **N5 (mittel)** Fensterbefehle nicht ohne Fenster zählbar (`_build_menus`) → Prüfstand zählt sie am
  Fenster; Tor hält Operationen und Dialogklassen; Fensterbefehlsliste `rendered`-Test beim Release.
- **N6 (mittel)** G1 gegen `fenster.md` „Der Hauptknopf“ (`no_primary`, Ruhezustand nur
  *Bausteinkatalog …*) → Schwelle „wie `fenster.md` und `test_resting_state`“.
- **N7 (mittel)** G9 ist Bauauftrag → G9-Fund höchstens leicht; neuer Griff eigener Registerpunkt mit
  Hauptweg nach `grenzen.md`.
- **N8 (leicht)** RM-734 bis 749 und Ort der Funddatei (`.claude/.state/funktionsdurchgang-2026-10/funde.md`).
- **N9 (mittel)** `file_acceptance` eigene Abkürzungen: `window.action_undo()`/`action_redo()`
  (Z. 972–984), `feature_panel._apply` (Z. 968), `select_feature`, gesetzte Zahl → auf
  Eingabeereignisse umstellen.
- **N10 (leicht)** Ziele `tree.row:<objekt>[.<merkmal>]`, `history.row:<n>`,
  `feature.field:<op>.<feld>`, `measure.field:<feld>`.
- **N11 (leicht)** Zwei Ausnahmen zu „Fenster lokal nur beim Release“ → ein gemeinsamer Satz in
  `AGENTS.md`; §11 ergänzen.
- Klein: Startweg von `file_acceptance`/`window_bench.py` statt Erinnerung; G2 über
  `layout.spacing()`/`contentsMargins()`; Merkmalfenster-Handlungen erzeugt aus
  `perceive.actions`/`selection_operations`.
- Stichproben stimmen (file_acceptance, area_for/_op_actions, make_guides-Abkürzungen, Termine,
  Kartenplatz, Gestaltungswerte). §13.1 belegt nur über KOORDINATION 20:06 — ist aber Roberts
  Antwort im Gespräch („1 ja, 2 ja“, 11.10.).
