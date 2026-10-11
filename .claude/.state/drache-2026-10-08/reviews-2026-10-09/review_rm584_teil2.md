# Review RM-584 Teil 2 (F:/sl-stil, Stand 92e3f89f5, danach 568fdd649) — solidon3d-review, 09.10.2026

**Kurzfassung:** 0 schwer, 6 mittel, 11 leicht. Kann so nicht rein; nach M1–M6 Nachprüfung.

## Mittel

**M1 — Gitter statt „automatisch“ gilt für jedes Programm, der Grund nur, wo „automatisch“ Bäume druckt**
`app/core/slice/advise.py:1261-1302`, auch 1267-1271. Unter PrusaSlicer (MK4S, snug) schlägt der Rat für den Pilz Gitter statt „automatisch“ vor, mit „Große flache Decken hängen zwischen Baumspitzen durch.“; in Cura geben auto, grid und hybrid dieselbe Übergabe. Fix: dem Rat „automatisch heißt Baum“ geben (`"auto" in organic`, dazu `support_type` tree für slim/strong wie bei `Motion.support_tree`); nur dort Gitter oder Hybrid über „auto“ vorschlagen und bei „Stützen nötig“ Gitter setzen, sonst „auto“ lassen; ohne Programm konservativ. Tests für Prusa-snug, Elegoo, Cura.

**M2 — Der Hybrid-Ersatz verdrängt den Grund des Vorschlags**
`app/core/export/slicer_keys.py:1532-1534`, `:1576`. „Aus → Hybrid“ mit Warnung „Ohne Stützen druckt dieses Teil in die Luft.“ wird unter PrusaSlicer und Cura zu „Gitter — Dieser Slicer kennt keine Hybridstütze und stützt mit Gitter.“ (61 Zeichen, en 76, es 73, fr 78). Fix: in `offered()` den Grund des Rats behalten, den Ersatzsatz nur bei eigener Wahl; Satz kürzen („Dieser Slicer kennt kein Hybrid und stützt mit Gitter.“, 54); `_reason_texts` um `Substitute`-Gründe erweitern.

**M3 — Aus Gitter und Baum wird Hybrid, das keine Datei bekommt**
`advise.py:434-437` mit `print_settings_dialog.py:1644-1646`, `:7377-7378`. Pilz (Gitter) und Figur (Baum) ergeben in `combine` Hybrid; `write_assembly` schreibt für Orca je Teil `normal(auto)` und `tree(auto)`, Platte none (`split_for_parts`); der Dialog zeigt „Aus → Hybrid“. Fix: nur dort zu Hybrid zusammenführen, wo die Stützart für die Platte gilt; Test Dialog bis Export für Orca und Cura; druckrat.md:60.

**M4 — Der Wandvorschlag fragt Solidons Stützart statt der gedruckten**
`advise.py:1404-1416`. Unter PrusaSlicer und Cura zeigt der Dialog Gitter (Ersatz), „Wände der Bäume 1 → 2“ bleibt; Cura schreibt die Wände nur beim Baum (`handover.py:2060`), Prusas Doppelwand gilt nur organischen Ästen. „auto“ wird nie gefragt. Fix: Ersatz aus `NOT_OFFERED_BY_PROGRAM` vor der Wandfrage anwenden; Filter, der `support.tree_walls` fallen lässt, wo die wirksame Art keine Baumart ist; „auto“ mitzählen, wo es Bäume heißt.

**M5 — Prusas Doppelwand ist keine Wandzahl**
`slicer_keys.py:105-109`, `:343`; `manufacturer.py:374-380`, `:1444`. Ohne Prusa-Bündel schreibt Solidon `support_tree_branch_diameter_double_wall = 0` (schaltet PrusaSlicers Vorgabe 3 ab); `PrusaResearch.ini` setzt ihn nur bei 0,6 (8) und 0,8 (0); `PRUSA_PROGRAM_DEFAULTS` fehlt er. Fix: PrusaSlicer nimmt `support.tree_walls` nicht (`NOT_TAKEN_BY`, Feldsatz), oder eigenes Feld; mindestens `_double_wall(1)` schweigt und „3“ gemessen in die Vorgaben.

**M6 — Kein Slicertest mit echtem Programm**
Übergabe (`support_style` je Objekt, `tree_support_wall_count`, Doppelwand, Curas `support_wall_count`) ohne `@pytest.mark.slicer`; Messung nur örtlich (`output/drache-2026-10-08/stil-rm584*`), Skript `F:/sl-stil/.claude/.state/drache-2026-10-08/stil_je_decke.py` ungesichert. Fix: Slicertest nach test_real_slicers.py.

## Leicht

- **L1** `analysis.py:4097-4105`: `tallest_column` misst nur bis zur ersten Berührung (Platte auf 150 mm über 120-mm-Turm: 30,5 mm); Ränder und Kanaldecken zählen mit.
- **L2** `test_slice_findings.py:1321`: nur Stil „tree“, 120/40 mm hält die Schwelle nur zwischen 35 und 115; Paar 95/105, Fälle Gitter und abgelehnt.
- **L3** `print_settings.py:720`: „Wände der Bäume“ unter Gitter aktiv; inaktiv schalten (Muster RM-341).
- **L4** Zwillinge: `support_hybrid=True` (`manufacturer.py:957`) neben der Ersatztabelle (`slicer_keys.py:1550-1554`); `TALL_TREE_WALLS` am Feldmaximum ohne Wächter.
- **L5** `slicer_keys.py:1193`: Bambu Studio ungemessen in `_NO_WALLS_UNDER_TREES`; messen, bis dahin herausnehmen.
- **L6** `advise.py:1293`: Gitter auch über gewähltem Hybrid mit Grund „Baumspitzen“; ungetestet.
- **L7** `advise.py:1264`, Tests 1361/1385: Kriterium `on_model` statt „kleine Stücke auf dem Modell“; Tisch ohne Detail bekommt „Bäume für Details …“.
- **L8** `slicer_keys.py:492` mit `manufacturer.py:1141-1143`: über `tree_hybrid`-Prozess liest die Grundlage Hybrid; wählt der Kunde Baum, schreibt Solidon keinen `support_style` (Entscheidung H).
- **L9** Unterlagen: druckrat.md:59 (`NOT_OFFERED_BY_PROGRAM`, SuperSlicer), druckrat.md:64f und `test_print_settings.py:9843-9847` („Export filtert“), Docstring `test_advise.py:832`, regel-druckrat.md:412 gegen Recherche Nr. 4.
- **L10** `advise.py:1838-1863`: `support.tree_walls` für die Platte statt je Teil ohne Begründung (Entscheidung G).
- **L11** Changelog: „Hohe Bäume bekommen zwei Wände.“ — Vorschlag „Für hohe Baumstützen schlägt Solidon zwei Wände vor.“; es: „Cuadrícula“ statt „rejilla“.

## Ohne Befund

Regel 7/8 (`TALL_TREE_HEIGHT`, `TALL_TREE_WALLS` belegte Rat-Konstanten), Regeln 1, 6, 14, 20, 22, Bezeichner; Kataloge vollständig; Changelog-Länge; Dateiformat ohne Sprung.

Sonden: `scratchpad/probe_rm584.py`, `probe_combine.py`, `probe_walls.py`, `probe_cura.py`.
