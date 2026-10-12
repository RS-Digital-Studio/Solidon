# drache3 — Kinn und Bein am dritten Drachendruck (RM-704)

Fortlaufend. Matrix und Werkzeuge: `F:\3D Druck\output\drache-2026-10-10\matrix\`
(`lauf.sh` schneidet Übergabe 3 mit Änderungen über `schnitt.py`, `messung.py` misst Unterseite
und Glieder, `mess.sh` fährt dazu `kontakt_bereich.py` von gestern für Kinn und Stacheln).
ElegooSlicer 1.5.3.5, Konsole, Kerne FFFFF0FF.

## Gegenprobe V0

Übergabe 3 unverändert: 8 h 31 min 25 s, 168,25 g — die gedruckte Datei hieß `…_0.2_8h31m.gcode`.
Lage wie Übergabe 2 (Bauelement `128 128 0`), Bereiche aus `rueckstaende\bericht.md` gelten.

## Lage

- Kinn: x 106–137, y 92–118, z 84–99 (G-Code). Unterkiefer beginnt bei z ≈ 94–96 als Inseln
  zwischen den Baumspitzen (`matrix\kinn_v0.png`).
- Vorderbeine: links x 108–131, rechts x 131–160, y 97–126, z 2–42; ab z ≈ 40 gehen sie in die
  Brust über (`matrix\beine_v0.png`, `beine_hoch_v0.png`). Vor Beinen und Brust stehen die
  Stämme der Kinnstütze (y 80–108).

## Messweg

`messung.py` rastert Bahnen mit Breite auf 0,05 mm, Modell und Stütze mit gefüllten Löchern
(Rahmen x 95–165, y 85–150, damit Kopf und Hals geschlossen sind — sonst zählt Elegoos
wechselnde Füllrichtung als Überhang; erster Lauf war deshalb falsch und ist verworfen).
Kinnunterseite: Überhang je Ebene = Modell mehr als 0,2 mm neben der Ebene darunter, getrennt in
Inseln (Bartstachel-Anfänge), flach (> 0,6 mm neben dem Modell darunter) und Rand (schräge
Streifen). Getragen = Stütze/Trennschicht höchstens 0,6 mm unter der Unterkante; Tr = davon
Trennschicht. Beine: Anteil des Umfangs mit Stütze in 1 mm, Anteil Füllung am Querschnitt.
Kinn-/Stachelkontakt mit `kontakt_bereich.py` von gestern (Fläche mit Luft 0 und 0,2 mm, diagonal).
Druck 2 zum Vergleich: `rueckstaende\v-basis` (Nachbau S1 von gestern).

## Matrix (ElegooSlicer, Übergabe 3 + Änderung)

| Variante | Zeit | g | Kinn flach getragen / Tr | Kinn Rand getragen / Tr, Luft 0,2 / 0,4 mm² | Kinnkontakt Luft 0 (Punkte) / 0,2 mm² | Stacheln Luft 0 / 0,2 mm² / diag. | Bein Füllung l/r |
|---|---|---|---|---|---|---|---|
| Druck 2 (S1) | 9:05 | 172,2 | 54 % / 0 | 34 % / 0, 34,9 / 8,6 | 0,93 (15) / 59,4 | 0,63 / 92,4 / 1,66 | 17,7 / 18,2 % |
| V0 = Druck 3 | 8:31:25 | 168,25 | 22 % / 5 % | 26 % / 2 %, 2,5 / 28,3 | 0,32 (6) / 7,0 | 0 / 3,2 / 0,94 | 26,8 / 29,2 % |
| V1 Astabstand 1 | 8:33:11 | 168,66 | 25 % / 6 % | 26 % / 2 % | 0,42 (7) / 7,3 | 0 / 3,4 | – |
| V2 + Winkel 40 | 8:29:48 | 167,58 | 22 % / 5 % | 26 % / 1 % | 0,60 (8) / 6,8 | 0 / 3,3 | – |
| V3 V1 + XY 0,5 + Wände 3 | 9:07:05 | 180,50 | 23 % / 6 % | 26 % / 2 % | 0,27 (6) / 6,6 | 0 / 3,5 | 20,8 / 21,2 % (alter Rahmen) |
| V4 V3 + oben 0,2 | 9:07:09 | 181,03 | 40 % / 0 | 33 % / 0, 33,4 / 8,7 | 1,69 (15) / 57,3 | 0,29 / 95,1 | – |
| V5 nur oben 0,2 | 8:37:43 | 172,04 | 41 % / 0 | 33 % / 0, 34,0 / 8,5 | 1,16 (10) / 59,3 | 0,26 / 94,2 | – |
| V6 Spitze 1,2 | 8:36:14 | 168,56 | 27 % / 25 % | 25 % / 25 % | 0,28 (5) / 4,5 | 0 / 1,7 / 0,57 | – |
| V7 Spitze 1,2 + Astabstand 1 | bahngleich mit V6 | | | | | | |
| V8 Trennschicht 3 Lagen, Abstand 0,2 | 8:31:21 | 168,04 | 22 % / 4 % | 26 % / 1 % | 0,32 (5) / 6,7 | 0 / 3,4 | – |
| V9 Schwelle 40° | 9:35:29 | 186,23 | 26 % / 5 % | 30 % / 2 % | 0,50 (7) / 8,4 | 0,01 / 8,3 | – |
| V10 unten 0,2 | 8:32:06 | 168,68 | 19 % / 5 % | 27 % / 2 % | 0,26 (5) / 6,9 | 0 / 4,0 | – |
| V11 Wände 3 | 9:05:31 | 180,46 | wie V0 | wie V0 | wie V0 | wie V0 | – |
| **V12 Spitze 1,2 + Wände 3** | **9:12:39** | **181,82** | **27 % / 25 %** | **25 % / 25 %, 1,7 / 24,7** | **0,28 (5) / 4,5** | **0 / 1,7 / 0,60** | **22,7 / 24,7 %** |
| V13 V12 + Trennschichtabstand 0,2 | 9:14:20 | 181,74 | 29 % / 27 % | 26 % / 26 % | 0,27 (5) / 4,5 | 0 / 2,0 | wie V12 |
| V14 V12 + 3 Trennlagen | 9:11:36 | 180,95 | 25 % / 25 % | 25 % / 24 % | 0,11 (2) / 3,7 | 0 / 2,0 | wie V12 |
| V15 V12 + XY 0,5 | 9:12:12 | 180,54 | 28 % / 26 % | 25 % / 25 % | 0,18 (5) / 4,5 | 0 / 2,0 | wie V12 |
| V16 Spitze 1,4 + Wände 3 | 9:11:34 | 181,53 | 24 % / 23 % | 23 % / 23 % | 0,19 (4) / 3,7 | 0 / 2,0 | wie V12 |
| V17 V12 + Abstand 0,2 + 3 Lagen | 9:14:49 | 181,79 | 25 % / 25 % | 26 % / 26 % | 0,11 (2) / 4,2 | 0 / 2,0 | wie V12 |
| V18 V12 + oben 0,2 | 9:19:43 | 185,76 | 36 % / 36 % | 30 % / 30 %, 24,0 / 11,8 | 0,35 (12) / 39,1 (Tr 38,5) | 0 / 79,9 / 1,3 | wie V12 |

Beine: Stütze am Umfang in 1 mm in allen Varianten 1,7–3 % (Druck 2: 3,4 / 5,2 %), keine Stütze
setzt auf den Beinen auf. Die Stütze an den Beinen ist in Druck 3 nicht mehr geworden.

## Ursache

- **Kinn.** Druck 3 trägt die Kieferunterseite schlechter als Druck 2: flache Teile 22 % statt
  54 % getragen, schräge Ränder 26 % statt 34 %, und was trägt, steht 0,4 mm statt 0,2 mm darunter
  — auf nackten Baumspitzen ohne Trennschicht (2–5 %). Ursache ist der Abstand oben 0,4 (V5 stellt
  Druck 2 wieder her), nicht Astabstand, Winkel, XY oder Wände (V1–V3, V11 ohne Wirkung am Kinn).
  Mit 0,4 enden die Spitzen zwei Schichten tiefer und stoßen an der schrägen Kieferseite früher
  an; ohne Trennschicht hängt die erste Modellschicht 0,4 mm über einzelnen Spitzen.
- **Bein.** Nicht mehr Stütze am Bein, aber ein schwächeres Bein: 2 statt 3 Wände (Elegoo-Grundlage
  statt Solidons Wert in Druck 2), Füllung 27–29 % des Querschnitts statt 18 %. Der Bruch auf halber
  Höhe mit sichtbarer Füllung passt dazu. Mechanisch messen lässt sich der Bruch nicht.
- **Hebel.** Eine Spitze ≥ 1,2 mm erzwingt die Trennschicht an jeder Spitze
  (π·0,6² = 1,13 mm² > `minimum_roof_area` 1 mm², `TreeSupport3D.cpp:1286`). Bei 0,4 oben trägt dann
  ein Viertel der Kieferunterseite eine Trennschicht statt 2–5 %, und an Kinn und Stacheln sinkt
  der Kontakt weiter (Kinn 7,0 → 4,5 mm², Stacheln 3,2 → 1,7 mm², diagonal 0,94 → 0,60).

## Druckdatei 4 (geliefert)

V12: Übergabe 3 + `tree_support_tip_diameter` 1,2 + `wall_loops` 3 (Objekt bleibt oben/unten 0,4).
9 h 12 min 39 s, 181,82 g (+41 min, +13,6 g gegen Druck 3; Wände allein +34 min).
- `F:\3D Druck\output\drache-2026-10-10\Drache-druck4.3mf` — Format der Übergabe 3 (CC2-Grundlage,
  Drucker „Elegoo Centauri Carbon 2 0.4 nozzle“, Filament „Solidon PLA Schwarz“), öffnet im
  ElegooSlicer wie Übergabe 3, deren Fensterzeit der Konsolenlauf auf die Minute traf.
  Ein Projekt im Orca-Format über `--export-3mf` stürzt in der Konsole zweimal ab (Exit 139).
- `F:\3D Druck\output\drache-2026-10-10\Drache-druck4.gcode` — md5 gleich `v-V12\plate_1.gcode`.
- Gedruckte Werte gegen V0 (`einstellungen.py`): Temperaturen, Lüfter, Tempo, Beschleunigung gleich;
  nur `wall_loops` im Konfigurationsblock anders.
- Alternative V18 (zusätzlich oben 0,2): Kiefer besser getragen (36 % / 30 %, alles mit
  Trennschicht), aber Stachelkontakt mit 0,2 mm Luft wieder 79,9 mm² wie in Druck 2 — die Reste an
  den Kopfstacheln kämen zurück. Nicht gewählt.

## Nachtrag A

- Stütze auf dem Modell (`gcode_auflage.py`): V0 8,5 mm² / 31 Füße, V12 12,9 / 49, Druck 2 19,2 / 42.
- Spitze 1,13 mm (V19 mit Wänden 3: 9:11:11, 181,44 g; V20 ohne: 8:36:19, 168,28 g) wirkt wie 1,2.
- Laufwerk C: lief gegen 05:50 voll; betroffen waren nur Testläufe und die ersten Kundenweg-Läufe,
  alle nachgefahren. Die Matrix lag auf F:.
- `SendMessage` gab es in dieser Sitzung nicht; die Zwischenantwort stand hier.

## Teil B — Solidon (Zweig `einstellungen/drache-druck3`, Worktree `F:\sl-drache3`)

**Befund → Rat:** Wo der Abstand über Baumspitzen gilt (RM-584, 0,4 mm), Trennschichten gedruckt
werden und die Orca-Familie schneidet, schlägt der Rat `support.tip_diameter` =
`ROOF_TIP_DIAMETER` vor: kleinste Spitze auf Hundertstel, deren Querschnitt `TIP_ROOF_AREA`
(`minimum_roof_area`, 1 mm²) übersteigt, also 1,13 mm. Neues Feld *Baumspitze*
(`tree_support_tip_diameter`), aus dem Herstellerprofil gelesen, unter Gitter inaktiv.
Bambu Studio kennt den Schlüssel nicht, Creality Print 7.2 liest ihn ohne Wirkung (gemessen,
`NOT_TAKEN_BY_PROGRAM`); PrusaSlicer und Cura nicht geschnitten (`NOT_TAKEN_BY`).

**Commits:** `053141305` (Rat, Feld, Tabellen, Kataloge, Changelog 0.6.0, Regel, Begründung,
Register RM-704, Tests), `121697bcb` (Archiv RM-704 Teil), `917b49bbe` (Merge welle3 `c7a6f853d`).
Gepusht.

**Tests (Test zuerst, Gegenprobe):** `test_the_roof_tip_is_the_smallest_with_a_roof`,
`test_tips_with_air_above_carry_a_roof` (orca ja; prusa, cura, wenige Inseln, keine
Trennschicht, schon breite Spitze nein) — am alten Stand rot (kein `ROOF_TIP_DIAMETER`, kein
Pfad). Slicertest `test_a_roof_tip_puts_an_interface_on_every_tip` (Kegelspitzen unter einer
Platte, Trennschicht unter z 19): OrcaSlicer, ElegooSlicer, Anycubic mehr, Bambu und Creality
gleich, 5 passed. Stifte von 0,6 mm zeigten den Unterschied nicht (Elegoo legte auch bei 0,8
eine Trennschicht), deshalb Kegel; Sonde: Kegel 0 → 3607, Schuppen 0 → 5714 Trennschichtbahnen.
Nach dem Merge: 2760 passed, 8 skipped (print_settings, slice_findings, manufacturer,
text_length, changelog, roadmap, directory_docs, wording, language_rules, translations,
slicer_profiles, cache, interface_limits, calibration, cli; ohne Fenster), Exit 0; vorher
`test_print_settings_ui.py` mit Fenster 327 passed. ruff, format, mypy Exit 0.
`test_text_length` war am Ausgangsstand rot (Kanalbefund, fremd, mit welle3 `a97c63add` behoben);
mein Grund ist auf 55 Zeichen gekürzt.

**Slicerbeleg Kundenweg** (`tools/matrix_unit.py`, elegoo:centauri-carbon-2, Drache, alter
Stand origin/welle3 gegen Zweig, `output/drache-2026-10-10/beleg/`): Der Rat schlägt 1,13 mm vor,
die Druckdatei trägt `tree_support_tip_diameter = 1.13`. Mit allen Vorschlägen alt 8:05:17 /
149,24 g, neu 8:10:10 / 149,27 g. Kinn: flach getragen 22 → 25 %, Trennschicht 5 → 25 %, Rand
Trennschicht 2 → 24 %; Kinnkontakt 0,2 mm Luft 6,95 → 3,95 mm²; Stacheln 3,16 → 1,87 mm², Luft 0
an beiden 0. Herstellerprofil allein: 104,1 g (ohne Stützen), unverändert. Sonst gleiche
Vorschläge.

**Nicht gebaut — Wände an dünnen Gliedern (neuer Punkt, nach welle4):** Ohne die breite Spitze setzt keine
Stütze auf den Beinen auf (mit 1,13 mm drei sehr kleine Füße, 0,19 mm² auf etwa 21 mm; Review M2), der Umfang mit Stütze in 1 mm ist
2–3 % (Druck 2: 3–5 %). Der Unterschied zu Druck 2 ist allein die Wandzahl (2 statt 3, Füllung
27–29 % statt 18 % des Querschnitts). Eine hergeleitete Wandregel ohne Kraftannahme gibt es
nicht (die Kernregel `solid_core` ergäbe 5 Wände für ein 7-mm-Bein), und ein Bruch ist die
einzige Messung. Druckdatei 4 druckt mit 3 Wänden; hält das Bein, ist das der Beleg für einen
Korpuslauf über Figuren mit Beinen. Bleibt im Register unter RM-704 offen (Text dort), mit Prusa
und Cura für die Spitze.

## Zusammenfassung

A: `output\drache-2026-10-10\Drache-druck4.3mf` / `.gcode` = Übergabe 3 + Spitze 1,2 + Wände 3,
9:12:39, 181,82 g. B: Rat „Baumspitze 1,13 mm“ in der Orca-Familie, Commits `053141305`,
`121697bcb`, Merge `917b49bbe`, gepusht; Wandregel als eigener Punkt.

## Fixes nach Review (`reviews-2026-10-10/review_rm704.md`)

Commit `ddea0dd43`, Merge welle3 `083dab2f6` als `076965bfe` (Konflikt nur im Archivverzeichnis
und am Dateiende, beide Seiten behalten), gepusht.
- M1: Changelog (sechs Sprachen, 181–199 Zeichen) und Feldhinweis nennen die gemessene Wirkung;
  `test_the_tip_field_names_the_roof_tip` hält 1,13 in Quelle und Katalogen gegen
  `ROOF_TIP_DIAMETER`. Register: Kinn an Druck 4 prüfen, sonst bleibt V18.
- M2: Begründung, Archiv, Register nennen 49 statt 31 Füße (14,3 statt 8,5 mm²), Kopf 105–112 mm,
  Vorderbeine ~21 mm; Satz zum Bein hier und in der Begründung berichtigt.
- M3: Slicertest `test_a_roof_tip_puts_an_interface_under_every_cone`: Art aus `TYPE|FEATURE`,
  Stütze unter den Kegeln verlangt, Trennschicht unter jedem der sechs Kegel (Mitte aus den
  Plattenbahnen, 2 mm), sonst gleiche Trennschicht. Bambu: zwei Läufe mit 0,8 sind gleich, 1,13
  weicht an 38 Stützpunkten ab; laut Nachprüfung legt Bambu die Platte von Lauf zu Lauf an 19 und 19 Punkten anders an, auch zweimal mit 0,8 mm;
  der Test sichert deshalb die Meldung zu, nicht gleiche Äste. 5 passed (gepinnt, nach dem Merge).
- L1: `test_proposed_roofs_bring_the_roof_tip_along` (flache Decke, Stil behalten, 0 Lagen →
  3 Lagen und Spitze; ohne `roofs = layers` rot), Spitze in `test_the_tree_walls_rest_under_a_grid`,
  `test_the_tip_is_read_back`, `test_a_tip_of_nothing_stays_foreign`.
- L3: Regel (Spitze plattenweit), `slicer_keys`-Kommentar, `types.py` („der meisten“).
- Nach dem Merge: 2098 passed, 8 skipped (text_length, translations, changelog, directory_docs,
  roadmap, wording, slice_findings, manufacturer, print_settings, language_rules,
  interface_limits), ruff, format, mypy Exit 0.

## Nachprüfung (`review_rm704_nach.md`)

Commit `801e0078c` (N1 Changelog auf Unterseiten, Grund „Mit Trennschicht löst sich jede
Baumspitze leichter.“, N2 Bambu-Kommentar, N3 Bein ohne Auflage im dritten Druck, N4 keine
Trennschicht unter 0,8 mm im Ja-Zweig), Merge welle3 `b8cf40a0d` als `1c0bf19e3`, gepusht.
Slicertest gepinnt 5 passed; text_length, changelog, translations, shared_constants,
language_rules, registry_consistency, directory_docs, slice_findings, roadmap 2366 passed,
4 skipped; ruff, format, mypy Exit 0.
