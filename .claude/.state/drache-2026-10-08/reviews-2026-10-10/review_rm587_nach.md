# Nachprüfung RM-587 „Lange Brücken bekommen ihre Stütze, und was frei druckt, hält“ (rv587n)

Gegenstand: Worktree `F:/sl-bruecken`, Zweig `einstellungen/bruecken-rm587`, Stand `641fb064a`
(welle3 `997ce9fcd` enthalten). Erstreview `review_rm587.md` (M1–M4, L1–L3), Behebungen
`ec2f54560`, `83db31e28`, Merges `222baf312`, `12cb93d4f`, `641fb064a`, Bericht `rm587b.md`.
Nur gelesen und gemessen, im Worktree nichts geändert (`git status` vor und nach allen Läufen
leer). Scratch: `scratchpad/rv587n/` (Archivabzüge `neu` = `641fb064a`, `w3` = `997ce9fcd`,
`fix` = `83db31e28`, je mit der übersetzten Kernbibliothek des Hauptbaums, `_chain.pyx` gleich;
`mut` = Kopie von `neu` für Quelltextmutanten). Slicer und Rechnungen gepinnt (`FFFFF0FF`).

## Verlauf

- 12:58 Auftrag, Erstreview, Bericht des Bauagenten gelesen.
- 13:05 Diffs `ec2f54560`, `83db31e28` und die Anpassung im Merge `222baf312` (`advise.py`,
  `span_beside` statt `quiet_layers`) vollständig gelesen; Interdiff eigener Diff alt
  (`aff70cb91..31788ce82`) gegen neu (`997ce9fcd..641fb064a`) durchgesehen.
- 13:08 Ratsonde des Erstprüfers nachgebaut (`probe_rat2.py`: ohne `quiet_layers`, Spannen ohne
  Ränder bzw. ohne Kanal und Ränder, `steep_reach`; neu: Decke auf drei und auf zwei Seiten,
  geneigte Zylinder, Trichter 44/45/46 Grad 60 mm hoch, Rundung 10 mm, mini-pot, Side kit rest,
  Besenhalter, Schraubendreherhalter) → `rat_neu.out`, EXIT 0.
- 13:10 Bandsonde nachgebaut (`probe_steil2.py`, protokolliert jeden Lauf von `steep_reach`,
  K1 Max / Kobra 2 / MK4S, ABS) → `steil_neu.out`, EXIT 0.
- 13:12 PrusaSlicer 2.9.6 an Kasten, U-Decke, L-Decke, Pilz, Auskragung je mit und ohne
  `extra_perimeters_on_overhangs` (`deckel2.py`, nach `rv587/deckel_prusa.py`) → `deckel2.out`,
  10 × Exit 0.
- 13:18 Tore im Worktree (`gates_wt.sh`) → `gates_wt.out`, alle EXIT 0.
- 13:15 Kanaldecke am echten Slicer (`kanal_slicer.py`, OrcaSlicer, K1 Max, PLA,
  Herstellerprofil, echter Rat des Teils) → `kanal_minipot.out`, EXIT 0; Stütze je Höhe im
  Deckenbereich (`kanal_z.py`) → `kanal_z.out`, EXIT 0.
- (Abbruch am Nutzungslimit, fortgesetzt 16:41.)
- 16:42 `git merge-tree` gegen welle3; Fenstertest, echte Slicer (gepinnt) und gezielte
  Quelltextmutanten (`mut_gezielt.sh`, Mutante in der Datei statt zur Laufzeit, weil
  `test_advise.py` `advise` neu lädt) → `fenster.out`, `slicer.out`, `mut_gezielt.out`, je EXIT 0
  bzw. wie erwartet rot. SuperSlicer `--help-fff` → `ss_help.out`.

## Befunde

### N1 (mittel) Eine Decke auf drei Seiten zählt weiter als einseitig und bekommt Zusatzwände ohne Wirkung

`app/core/slice/analysis.py:3415–3431` (`cantilevers`: Ringausnahme `:3426`, Zählung
`:3428–3430`), Rat `app/core/slice/advise.py:2326–2336` über `_free_flat_overhang` `:2393`.

M1 ist für den geschlossenen Ring behoben, die Ursache nicht: Eine einzige zusammenhängende
Berührung gilt weiter als „hängt an einer Seite“. Ein Kasten mit Deckel, vorn offen (Gehäuse mit
Öffnung, Fach), liegt links, hinten und rechts auf — die Berührung ist ein U, also eine Linie.

Beleg: `rat_neu.out` B7 „Decke auf drei Seiten“: breit 1, einseitig 1, und
`shell.overhang_walls=True «Zusatzwände halten den Überhang ohne Stütze.»` in **allen sechs**
Varianten, auch K1 PLA mit Vorgabe (Stützen nicht nötig). PrusaSlicer 2.9.6 (`deckel2.out`,
Deckenschichten z 12–14): U-Decke mit und ohne Zusatzwände gleich (Brückenbahn 3 588,7 mm,
Förderung 16 839,07; Überhangwand 51,2 mm in beiden). Gegenproben wirken: L-Decke (zwei
Nachbarseiten) Brücke 3 590,6 → 1 795,3 mm, Überhangwand 109,5 → 1 928,9 mm; Pilz Brücke
3 451,5 → 1 795,3, Überhangwand 233,0 → 1 886,0; Auskragung 3 mm Überhangwand 95,4 → 367,8.
Kasten mit Deckel bleibt gleich (3 575,0), M1 hält. Orca nicht nachgefahren (Zeit); dort steckt
derselbe aus PrusaSlicer übernommene Algorithmus, und die Begründung des Zweigs misst ebenfalls in
PrusaSlicer.

Warum es zählt: derselbe Schaden wie M1 — ein Rat, der eine Wirkung verspricht, die es nicht gibt
(`_free_flat_overhang` sagt selbst: „Eine an beiden Enden gelagerte Brücke legt der Slicer mit und
ohne Zusatzwände gleich“), an einer Alltagsform. Zwilling der Ringausnahme
(`.claude/rules/zwillinge.md`).

Fix: In `cantilevers` einseitig nur, wenn keine Bahn über das Stück an zwei Berührungen ankert —
etwa die Brückenweite des Stücks mit der Berührung als Anker messen (`_bridge_width(…,
touching=…)`, wie `span_beside` es tut) und ab einer Bahnbreite beidseitig nennen; der Ring wird
damit ein Sonderfall derselben Regel. Test in `test_advise.py`: U-Decke ohne Zusatzwände (mit und
ohne Stützen), L-Decke, Pilz und 3-mm-Auskragung weiter mit; Gegenprobe `deckel2.py`.

### N2 (leicht) Steil wird eine Wand schon durch ihre Höhe: 46 Grad bekommt die Umkehr, die Orca dort nicht ausführt

`analysis.py:3355–3366` (Summe der Bandbreiten je Lauf), Rat `advise.py:2341`.

Beleg `steil_neu.out` (alle drei Drucker): Trichter 46 Grad, 60 mm hoch: 2,110 mm über 299
Schichten (je Schicht höchstens 0,012 mm) → Umkehr; 45 Grad 0,022, 44 Grad 0,002 → still. Die
Grenze „eine Bahnbreite“ entspricht Höhe · (tan θ − 1) > 0,42: 46 Grad ab 11,8 mm Höhe, 47 Grad ab
5,9 mm. Orca kehrt aber nur dort um, wo die Außenbahn über die Schicht darunter hinausragt:
`overhang_reverse_threshold` steht im K1-Max-Prozess (`fdm_process_creality_common.json`) auf 50 %
der Bahnbreite, also erst ab h · tan θ > 0,5 · w, bei 0,2/0,42 ab 46,4 Grad. An einer hohen Wand
zwischen 45 und 46,4 Grad bleibt der vorgeschlagene Schalter ohne Wirkung (aus Orcas Schwelle
abgeleitet, nicht im G-Code gemessen). Zur Herleitung (Regel 7/8): Die Grenze ist ein Projektwert
und für die Frage „Kante oder Wand“ schlüssig (Rundung 2/5/10 mm bleibt mit 0,046/0,181/0,358 mm
still, Besenhalter und Schraubendreherhalter siehe unten); für die Steilheit fehlt die Schwelle je
Schicht.

Fix: Je Schicht nur Band zählen, das breiter ist als 0,5 · Bahnbreite − Schichthöhe (die Schwelle,
ab der das Programm umkehrt), sonst beginnt der Lauf neu. Test: Trichter 46 Grad 60 mm ohne,
47 und 50 Grad mit Umkehr.

### N3 (leicht) Eine steile Wand, die irgendwo jenseits der Grenze überhängt, zählt gar nicht

`analysis.py:3343` (`kept = ~shapely.intersects(parts, ceilings[owner])` nimmt das ganze
zusammenhängende Bandstück heraus, nicht den Streifen am Überhang).

Beleg `steil_neu.out`: Zylinder 55 Grad geneigt 4,293 mm → Umkehr; derselbe 65 Grad geneigt —
Flanken zwischen 45 und 60 Grad über 17 mm Höhe, nur die Unterseite jenseits der Grenze —
0,185 mm, herausgenommen 76,9 mm² → keine Umkehr. Am MK4S (Grenze 55 Grad) verliert auch der
55-Grad-Zylinder die Umkehr (0,081 mm). Die Flanken drucken auch mit Stützen frei; an organischen
Teilen (Bäuche, Kinne) ist das die Regel. Der Erstreview hatte genau das vorgeschlagen: nur den
Streifen am Überhang herausnehmen.

Fix: Statt ganzer Bandstücke die Überhangstücke, um Schichthöhe · (tan Grenze − 1) und
`OVERHANG_MARGIN` erweitert, vom Band abziehen. Test: Zylinder 65 Grad geneigt mit Umkehr, Kasten
und Becher weiter ohne.

### N4 (leicht) Die Kanaldecke gilt als frei, auch wenn nichts sie freihält

`advise.py:2283–2288`, `:2307`; `DECIDING_PATHS` `:1037`; Vorschlag der Sperre `:1473–1486`.

Beleg `kanal_minipot.out`, `kanal_z.out` (OrcaSlicer, K1 Max, PLA, Herstellerprofil; Rat des
mini-pot: Stütze automatisch, „nur vom Bett“, freie Ränder, dicke Bahnen; Fluss steht im Profil
schon auf 0,9; die Kanalsperre schlägt der Rat hier nicht vor). Mit übernommenem Rat (`voll`)
endet die Stütze im Bereich der Kanaldecke (136,8 mm²) bei z 27,8 (1,6 mm Trennschicht am Rand),
die Decke z 28,8–29,2 druckt frei als Überhangwand (44,0 + 213,9 mm) und Brücke (187,5 mm). Die
Verhaltensänderung aus welle3 ist auf diesem Weg also richtig, siehe unten. Wählt der Kunde aber
„nur vom Bett“ ab (`ueberall`), stützt Orca die Decke (Trennschicht 198,5 / 192,1 / 173,9 / 144,7 /
76,7 mm in z 27,8–28,6 direkt darunter), und die dicken Bahnen bleiben (Teilwert
`thick_bridges = 1`, Bahnen wie in `voll`). Der Rat fragt `need.model.channels`, nicht, ob Ort oder
Sperre den Kanal wirklich freihalten; beide fehlen in `DECIDING_PATHS`, die Abwahl fragt nicht
neu. Der eigene Docstring sagt: „Über einer Stütze trägt die dünne Brücke und sieht besser aus.“
Folge: optisch, keine Fehlstelle — deshalb leicht. Dasselbe Muster galt vor dem Merge für
Schichten aus lauter Kanalstücken; jetzt trifft es mehr Teile.

Fix: Wie `_free_flat_overhang` mit `support.spare_ledges`: Kanaldecken nur frei, wenn
`support.placement == "build_plate"` oder `support.block_channels` gesetzt oder vorgeschlagen und
nicht abgewählt ist; beide in `DECIDING_PATHS`. Test: Tunnel unter Stützen mit „überall“ ohne
Sperre → keine dicken Bahnen; mit „nur vom Bett“ → dicke Bahnen (der L1-Test bleibt).

### N5 (leicht) Kein Test hält die Umkehrgrenze bei einer Bahnbreite

Mutante `schwelle_drei` (Grenze 3 × Bahnbreite in `advise.py:2341`): 16 passed, EXIT 0
(`mut_gezielt.out`). Die Ratstests prüfen den Trichter mit 50 Grad (3,8 mm) und Kanten unter
0,2 mm; dazwischen nichts, und `test_the_steep_reach_follows_one_wall_upwards` prüft nur die
Messung. `schwelle_null` dagegen ist rot (Rundung). Fix: Rattest mit dem geweiteten Pfosten
(55 Grad über 2 mm, Reichweite zwischen Bahnbreite und 0,86 mm) → Umkehr, zwei kurze Weitungen
→ keine.

## Erstbefunde — behoben?

- **M1 behoben** für den geschlossenen Ring: Kasten mit Deckel und umgedrehter Becher einseitig 0,
  keine Zusatzwände in allen Varianten (`rat_neu.out` B1, B2); Pilz und Auskragung weiter
  einseitig; PrusaSlicer am Kasten mit und ohne gleich. Mutante `ring` 2 rot. Rest: N1.
- **M2 behoben** in der gemeldeten Form: Kasten und Becher 0 (herausgenommen 655,4 / 514,3 mm²),
  Rundung 2 mm 0,046, Trichter 40 Grad 0, 50 Grad 3,798 mm (von Hand 19,8 · 0,192 = 3,80), an
  allen drei Druckern. **Besenhalter und Schraubendreherhalter verlieren die Umkehr zu Recht:**
  Ihr längster Lauf sind zwei Schichten (z 15,75–15,95 bzw. 51,75–51,95, 1,4 bzw. 5,1 mm²,
  0,123 / 0,107 mm) — Kanten, keine Wände. mini-pot (1,150, 23 Schichten), Side kit rest (0,603,
  16 Schichten), Okarina, Baum, Drache behalten sie. Mutanten `streifen` 7, `durchgehend` 1,
  `schwelle_null` 3 rot. Rest: N2, N3, N5.
- **M3 behoben:** echte Slicer gepinnt, `test_real_slicers.py -k bridge` 10 passed, EXIT 0 —
  darin SuperSlicer 2.5.59.13 (Datei ohne Programm und mit SuperSlicer öffnen, Brückenfluss je
  Teil wirkt), PrusaSlicer (stützt die lange Brücke, verdickt die freie), Orca- und Elegoo-Familie,
  Brückenfluss je Teil in PrusaSlicer, OrcaSlicer, ElegooSlicer, Creality Print, Anycubic Slicer
  Next, Bambu Studio. SuperSlicers eigener `bridge_type` ist „nozzle“ (`ss_help.out`), mit
  Solidons `thick_bridges = 0` also dünn — der Changelog-Satz stimmt. Mutanten `familie` 2,
  `standardwert` 1, `ss_fluss` 2 rot. Die programmlose Prusa-Datei verliert Schrägnaht und
  Zusatzwände; über die Oberfläche entsteht sie nicht (`main_window` nimmt ohne Programm `orca`,
  die Dialogwege tragen immer ein Programm) — kein Befund.
- **M4 behoben:** `DECIDING_PATHS` mit Brückenstütze und freien Rändern; Dialog fragt neu
  (Fenstertests in `test_print_settings_ui.py` grün), Export fragt ohne die nicht übernommenen
  (Mutante `abwahl_export` 1 rot). Die Zeile der Brückenstütze bleibt nach der Abwahl stehen
  (`_bridges_and_overhangs` hängt sie unabhängig von `declined` an) — der Kunde kann zurück.
- **L1 behoben:** `kanal_laut` 1, `fluss_max` 1 rot. **L2 behoben:** `umkehr_prusa` 1 rot.
  **L3 behoben:** `cura_satz` 1 rot, Cura-Satz in allen fünf Katalogen, Changelog in sechs
  Sprachen gleich gegliedert.

## Verhaltensänderung nach welle3 (Punkt 3)

Richtig auf dem Weg, den der Rat vorsieht: Am mini-pot druckt die Kanaldecke mit übernommenem
„nur vom Bett“ frei (siehe N4, `voll`), und `thick_bridges = 1` wirkt dort — Orca legt sie als
Überhangwand und Brücke, dicke Bahnen fördern 0,0461 statt 0,0287 (Überhangwand) bzw. 0,0262 mm je
mm (Brücke), die Brücke braucht 187,5 statt 250,6 mm Bahn. Dicke, runde Bahnen über 20 mm freier
Decke sind PrusaSlicers eigene Vorgabe; dass sie dort helfen, ist schlüssig. Die Lücke ist N4 (Ort
oder Sperre abgewählt). Side kit rest bekommt die Kanalsperre vorgeschlagen (`rat_neu.out` E2), am
Slicer nicht nachgefahren.

## Punkt 4: `installed_slicer` und das echte LOCALAPPDATA

- §38 hält: Im Fenster läuft nur das Original `discover.find_programs`; es liest die gemerkte Wahl
  unter APPDATA (bleibt umgebogen), PATH, Registry und die Installationsordner, darunter das echte
  `%LOCALAPPDATA%\Programs`. `user_data_dir`/`user_cache_dir` fragt es dort nicht; das `finally`
  stellt die Variable zurück und leert die Merker. Die Umstellung ist prozessweit — ein Faden eines
  früheren Tests sähe in diesem Augenblick das echte LOCALAPPDATA; theoretisch, kein Befund.
- CI-Auswahl unberührt: gesammelt wird auf ubuntu (`build.yml:385`), dort trägt der Test `skip`
  statt Marker und wird nie gewählt; `slicer-auswahl.yml` fährt nur ubuntu/macOS, dort ist
  `_REAL_LOCAL_APPDATA` leer. „Nur unter Windows“ ist richtig, solange es kein Rezept gibt (neuer
  Punkt 1 des Bauagenten).
- Wächter: `_unmarked_machine_searches` liest „mark.slicer“ im entparsten Dekorator, der bedingte
  Ausdruck zählt; die Umbenennung im Helfer `_advised_gcode` ist sachlich richtig (er sucht nicht
  selbst). `test_slicer_selection.py` grün.

## Merge-Vorschau welle3

`git merge-tree --write-tree --name-only 641fb064a b8f42046c` → nur Baum `9efa8db33`, kein
Konflikt; gegen den jetzigen Stand `fcac08701` (enthält `b8f42046c`) → `71558c4ba`, kein Konflikt.
welle3 berührt seit `997ce9fcd` keine der RM-587-Kerndateien (`advise.py`, `analysis.py`,
`slicer_keys.py`, `handover.py`, `writer.py`, `tests/conftest.py`).

## Tore

- `ruff check .` EXIT 0, `ruff format --check .` EXIT 0 (1206 Dateien), `mypy` EXIT 0
  (374 Dateien) — im Worktree ohne Cache.
- `test_text_length`, `test_shared_constants`, `test_language_rules`,
  `test_registry_consistency`, `test_slicer_selection`, dazu `test_translations`, `test_wording`,
  `test_directory_docs`, `test_roadmap`, `test_changelog`: 2185 passed, 4 skipped, 8 deselected,
  EXIT 0.
- Fenster `test_print_settings_ui.py`: 338 passed, 126 deselected, EXIT 0.
- Gepinnt `test_real_slicers.py -k bridge`: 10 passed, 65 deselected, EXIT 0.
- Gegenproben-Basis (32 gezielte Tests im Abzug): 32 passed, EXIT 0.

## Urteil

**Nicht** — ein mittlerer Befund (N1, Zusatzwände ohne Wirkung unter einer Decke auf drei
Seiten, der Rest von M1) und vier leichte (N2–N5). N1 ist eine Bedingung in `cantilevers` und ein
Test; danach kann der Zweig landen, eine weitere Nachprüfung braucht es für einen einzelnen
mittleren Befund nicht. N2–N5 nach der Hausregel ebenfalls beheben; sie halten den Merge nicht
auf.
