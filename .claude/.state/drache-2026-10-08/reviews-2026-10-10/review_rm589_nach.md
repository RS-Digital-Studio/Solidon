# Nachprüfung RM-589 — „Bohrungen und Stifte passen ohne Nacharbeit“

Prüfling: Worktree `F:\sl-loecher`, Zweig `einstellungen/loecher-rm589`, HEAD
`74f87bdef`; Behebungen `e8c785abd..HEAD` (`b202dc682`, `77fb4183a`, `9eb925fd3`,
`74f87bdef`), ganzer Zweig `a9e4d3f64..HEAD` (47 Dateien, jede Zeile gelesen).
Erstreview `reviews-2026-10-09/review_rm589.md`, Bericht des Bauagenten
`berichte-2026-10-10/rm589.md`. Sonden, Kopien und Ausgaben:
`scratchpad\rv589n\` (Kopien `mut` = HEAD, `alt` = `e8c785abd` per `git archive`,
nach den Läufen entfernt; Skripte und Ausgaben bleiben).
Am Worktree nichts geändert, `git status` danach leer.

## Erstbefunde

| Fund | Stand | Beleg |
|---|---|---|
| S1 eigener Satz schreibt ungefragt | **behoben** | Kundenweg gepinnt: Cura-Konsole ohne Wahl kein Schlüssel in `-s` und je Netz; Cura-Fenster am echten Cura (aktive Maschine Ender-3 V3 SE): `.curaprofile` 62 Werte ohne Ausgleich, 3MF je Objekt ohne; OrcaSlicer ohne Prozess, PrusaSlicer/SuperSlicer ohne Bündeldrucker: keiner der Schlüssel, Konfigurationsblock 0/0. Mutation „Filter aus“: 5 Tests rot |
| M1 kalibriertes Material | **behoben für vollständig kalibrierte Materialien**, Lücke bei Teilkalibrierung (N3) | `advise.advise` mit `calibrated=True`: kein Rat in allen vier Programmen; `drucker-kalibrieren.p3d`: keiner der drei Körper trägt Modellausgleich, die Kalibrierschleife ist zu. Mutation: Test rot |
| M2 Schritte statt Löcher | **teilweise** — die 24 Fälle des Bauagenten stimmen, neue Fehlzählungen (N1, N2) | Sonden `bausteine.py`, `ops_spiel.py`, `luecken.py`, `beispiele.py` |
| M3 Dialogweg ohne Test | **behoben** | Mutationen `_part_allowances` leer und Arbeiter ohne Weitergabe: Fenstertest rot |
| L1 Programmvorgaben | behoben | OrcaSlicer ohne Prozess: `elefant_foot_compensation = 0`, `xy_hole_compensation = 0` im Block; Mutation rot |
| L2 Regel 6 | behoben | `handover.py:1362` `not is_zero(foot)` |
| L3 Feldtexte und Suche | **teilweise** (N5) | englische Wörter in allen Sprachen, deutsche Kurzwörter; die Wörter der übersetzten Slicer findet die Suche nicht |
| L4 Unterlagen | behoben, Rest in N9 | Recherche-Kopf, Archiv, Begründung, Regelumzug, Changelog |
| L5 SuperSlicer | behoben, am Programm belegt | `first_layer_size_compensation = -0.2` aus dem MINI-Bündel zurückgelesen als 0,2; `hole_size_compensation = -0.1` weitet B um 0,200 mm |
| L6 Prusa-Rücklesung | behoben | Testzeile MK4S 0,2; Mutation rot |
| neu: Vorzeichen ohne Programm | behoben, am Programm belegt | Prusa-3MF ohne Programm: SuperSlicer liest `elefant_foot_compensation = 0.15` als `first_layer_size_compensation = -0.15` und `hole_size_compensation = -0.1`; PrusaSlicer liest den Einzug und übergeht den Lochschlüssel; beide schneiden ohne Fehler |

## Neue Funde

### Schwer

**N1 Nach *Anordnen* bekommt jeder Körper den Ausgleich seiner Nachbarn — übernommen
druckt der Nachbar mit Elefantenfuß.**
`app/core/scene/fits.py:341-355` (`_producing`), genutzt von `allowances_for`
(`fits.py:398`). `arrange_bed` und `orient_for_print` führen alle Körper als Ein- und
Ausgang; der Rückwärtsgang nimmt bei jedem Schritt, der den Körper ausgibt, *alle*
Eingänge mit und damit die Herkunft jedes Nachbarn.

- Sonde `anordnen.py` (K1 Max, PETG): A mit *Elefantenfuß ausgleichen*, B ohne. Ohne
  Anordnen A `('foot',)`, B `()`. Nach `arrange_bed` oder `orient_for_print` auch B
  `('foot',)` mit dem Rat „Erste Schicht einziehen → 0“, Grund „Das Modell zieht den
  Fuß schon selbst ein.“
- Slicerbeleg `anordnen_slicer.py`, OrcaSlicer 2.4.2, Herstellerprozess (Einzug 0,15),
  Rat übernommen wie im Dialog: ohne Anordnen nennt die Zeile `['A']`, B behält den
  Einzug (Schicht 1 um 0,380 mm schmaler als die Mitte). Mit Anordnen nennt sie
  `['A', 'B']`, der Export schreibt beiden `elefant_foot_compensation = 0`, und B ist in
  Schicht 1 nur noch 0,080 mm schmaler: B druckt mit Elefantenfuß, obwohl sein Modell
  nichts ausgleicht.
- Dieselbe Ursache für „holes“ in ausgelieferten Beispielen (`beispiele.py`):
  `aushoehlen-und-teilen.p3d` — die Stifthälfte zählt, weil `arrange_bed` die
  Bohrungshälfte in ihre Herkunft holt; `dose-mit-deckel.p3d` — der Deckel ohne jede
  Bohrung zählt, weil er die `insert_cable_gland` des Gehäuses erbt (Bausteine werden am
  Schritt gezählt, nicht am Merkmal des Körpers).
- `fit_kinds_for` springt genauso, schon am alten Stand (`passung_anordnen.py`:
  Mutternfalle an A → nach `arrange_bed` auch B `('clearance',)`, an `e8c785abd` und
  HEAD gleich); RM-589 macht die gemeinsame Herkunftssuche druckwirksam.
- Kein Test enthält einen Anordnen-Schritt nach dem Ausgleich; alle 24 Mutationen
  fangen diesen Fall nicht.

**Fix:** In `_producing` die Linie je Kennung verfolgen: Gibt ein Schritt den Körper aus
und hat ihn auch als Eingang (Anordnen, Ausrichten, alles an Ort und Stelle), nur diese
Kennung weiterverfolgen; alle Eingänge nur bei Schritten, die den Körper neu erzeugen.
Bausteine am Merkmal des fertigen Körpers zählen (`feature.created_by` gibt es auch für
Bausteinbohrungen, etwa `cable_gland_bore_1`, `nut_trap_pocket_1`), wie schon die
gebohrten Löcher. Tests: A/B mit `arrange_bed` und `orient_for_print` → B `()` für Fuß und
Löcher; `dose-mit-deckel.p3d` Deckel `()`; `aushoehlen-und-teilen.p3d` Stifthälfte `()`;
`fit_kinds_for` ebenso (ein Fix mit Zwilling, `zwillinge.md`).

### Mittel

**N2 M2 ist nicht abgeschlossen: drei Zwillinge fehlen, waagerechte Bohrungen zählen.**
`app/core/scene/fits.py:362-375, 410-411, 457-475`.

- **Zu wenig** (Sonde `luecken.py`, am gerechneten Körper):
  - `split_line` (*An gezeichneter Linie teilen*, „derselbe Schnitt wie *Teilen und
    verstiften*“, `prepare_ops.py:21687`): Hälfte B mit `bore_1/bore_2` (Achse z, Spiel)
    → `()`; dasselbe mit `split_pinned` → `('holes',)`.
  - `create_container` (*Behälter mit Deckel*, Vorgabe Schraubdeckel, ruft intern
    `screw_lid`): Drehdeckel mit `lid_cap_thread` → `()`; `screw_lid` gibt derselben
    Kappe `('holes',)`.
  - `cut_counter_form` (*Gegenform einlassen*): Taschen um das halbe Materialspiel je
    Seite geweitet (`counter_form_ops.py:184-198`), Entnahme z → Einsatz `()`.
- **Zu viel — waagerechte Bohrungen** (Sonde `luecken.py`, `kundenweg.py` Lage
  `waagerecht`, `vergleich_h.py`): `drill_hole` Achse x → `('holes',)`,
  `insert_hinge_eye` oben → `('holes',)` (Bohrung Achse (1,0,0); `hinge_eye`: „die Achse
  liegt parallel zur Fläche“). OrcaSlicer, K1 Max: Körper H mit waagerechter Bohrung hat
  bei `xy_hole_compensation` 0 und 0,1 dieselben 6206 Bahnen, keine weicht ab; Körper V
  daneben (senkrecht) weicht in 6419 von 6658 Bahnen ab, Loch 6,619 → 6,820 mm. Der
  XY-Lochausgleich wirkt nur auf geschlossene Innenkonturen der Schicht. Betroffen sind
  die Scharnieraugen von *Deckel erzeugen* (`lid_hinge.py:396-418`, `axis=_X`), die
  Bausteine `hinge_eye`, `barrel_hinge`, `pipe_clamp` („das Rohr läuft parallel zu ihr“),
  `cable_clip` („Achse in Y“), `channel_joint` (offen nach oben) und jede seitlich
  gesetzte Bohrung. Der Rat „Löcher weiten 0“ ändert dort am Loch nichts und nimmt nur
  den anderen, unausgeglichenen Löchern des Teils den Herstellerausgleich (Kobra 2
  0,02, Ender-3 V3 KE 0,025 mm je Seite). `test_only_a_step_that_puts_play_into_a_hole_counts`
  und `test_a_step_with_two_results_counts_only_where_the_play_is_inside` schreiben
  diese Zählung für Scharnierauge, Bolzenscharnier und Steckstift-Deckel fest — Sollwert
  aus der Einteilung „Innenkontur“, nicht aus dem, worauf der Slicer wirkt.

**Fix:** Löcher zählen, wo eine geschlossene, senkrechte Innenkontur Spiel trägt: am
fertigen Körper die Merkmalsachse gegen z (Achsen drehen mit, Sonde `folgeops.py`: nach
`rotate_object` (0,−1,0)), bei `cut_counter_form` die Entnahmerichtung. `split_line`
wie `split_pinned`, `create_container` mit `lid="screw"` wie `screw_lid` in
`PLAY_HOLE_OPS`/`_play_outputs`, `cut_counter_form` dazu. Tests am gerechneten Körper,
Sollwerte für Scharniere auf `()`; Archiv und Begründung („Scharniere … zählen“)
nachziehen.

**N3 M1 unterdrückt den Rat auch für Werte, die nie gemessen wurden.**
`app/core/slice/advise.py:1674-1675` fragt `profile.material.calibrated`; das Kennzeichen
gilt dem ganzen Material. Der Kalibrierdialog reicht jedes nicht bearbeitete Feld mit
seinem bisherigen Wert durch (`app/ui/dialogs.py:567-584`, `_original_values`), und
`calibration.apply` setzt danach `calibrated = True` (`calibration.py:175`). Wer nur das
Spiel am Toleranz-Testkörper misst, behält beim Elefantenfuß den Startwert der Tabelle
— der laut eigener Begründung „den ganzen Fuß meint und den Vorschlag bekommt“
(`regel-druckrat.md`, Bericht rm589 „M1: die Wahl“). Ein Teil mit *Elefantenfuß
ausgleichen* gleicht dann im Modell den ganzen Fuß aus, der Slicer noch einmal, und
kein Rat erscheint. Gleiches für die Lochkorrektur.
**Fix:** je Feld festhalten, was gemessen ist (der Dialog kennt `_edited_fields`), und
den Rat für „foot“ nur bei gemessenem `elephant_foot`, für „holes“ nur bei gemessener
Lochkorrektur bzw. gemessenem Spiel unterdrücken. Test: Kalibrierung nur mit
`clearance` → Fußrat bleibt.

**N4 Das Format-Tor ist rot.** `ruff format --check .` → Exit 1:
`tests/test_manufacturer.py:446` (aus `9eb925fd3`) würde umformatiert. Der Bericht des
Bauagenten nennt „ruff check, ruff format --check, mypy: sauber, Exit 0“. Mit rotem Tor
scheitert die CI beim Push nach main.
**Fix:** `ruff format tests/test_manufacturer.py`.

### Leicht

**N5 Die Suche kennt die Wörter der übersetzten Slicer nicht** (L3 halb).
`app/core/knowledge/print_fields.py:155-159, 258-262`, Kataloge; `slicer_keys.keys_for`
(`slicer_keys.py:1017-1038`). Sonde `slicerwoerter.py` liest die Kataloge der
installierten Programme und fragt Solidons Suche: kein einziger Treffer. Deutsch:
„Elefantenfußkompensation“, „X-Y-Loch-Kompensation“ (OrcaSlicer, Bambu Studio,
ElegooSlicer, PrusaSlicer), Cura „Horizontale Erweiterung erste Schicht“,
„Horizontalloch-Erweiterung“; fr „Compensation de l'effet patte d'éléphant“ (Solidon:
„pied d'éléphant“), it „Compensazione zampa d'elefante“ (Solidon: „piede d'elefante“),
es „Compensación en X-Y de huecos“, pt „Compensação de furos XY“. Dazu fehlt SuperSlicers
`first_layer_size_compensation` in `keys_for` (nur Familientabellen, `PROGRAM_KEYS` nicht).
**Fix:** je Sprache das Wort, das die Slicer in dieser Sprache zeigen, in den Satz; die
Suche zusätzlich auf Wortteile (oder Begriff als Teilwort des Heuhaufens); `keys_for`
mit den Programmschlüsseln. Test mit diesen Bezeichnungen.

**N6 Docstrings sagen das Verhalten vor S1/M1.** `app/core/types.py:1237-1240`:
„in Solidons eigenem Satz der des Materialprofils“ — seit S1 null und ohne Wahl
ungeschrieben. `types.py:1269-1271` „gehört er auf null“ — nicht bei kalibriertem
Material. **Fix:** Text an `MAKER_OWNED` und M1 angleichen.

**N7 Dritte Kopie der ausgeglichenen Lochfeldformen** (`zwillinge.md`).
`fits.py:368` `_COMPENSATED_FIELD_SHAPES = {"circle", "slot"}` wiederholt
`field_ops.py:344` und `:401`. Kommt eine Form mit Ausgleich dazu, zählt `fits.py` falsch.
**Fix:** eine Konstante in `field_ops`, an allen drei Stellen benutzt.

**N8 `PartSpec.play_inside` ist ein neuer Vertrag ohne Karte und Wächter.**
`registry.py:503-508`. Die Bausteinkarte (`app/core/knowledge/parts/CLAUDE.md:118-120`,
nennt `grip_from_profile`) und `/neuer-baustein` erwähnen ihn nicht; kein Test leitet ihn
aus der Geometrie ab. Ein neuer Baustein mit Spiel in einer Bohrung bekommt still keinen
Rat. **Fix:** Kartenzeile und Wächter: Baustein mit `play` 0 und 0,4 bauen, wächst eine
senkrechte Bohrung mit, muss `play_inside` stehen.

**N9 Unterlagen.** `app/core/slice/CLAUDE.md:23` zählt die Regeln von `advise.py` auf, die
neue (`_from_allowances`) fehlt. `.claude/rules/dateiformat.md` verlor beim Kürzen „Eine
3MF soll man drucken können, nicht erst einrichten:“, ohne Umzug (die drei anderen Sätze
stehen in `regel-dateiformat.md`). Nach N1/N2 Archiv und Begründung nachziehen.

**N10 Changelog-Wort.** `changelog/*.md` Punkt 2: „mit einer Bohrung samt
Materialzugabe“ — der Haken heißt in der Oberfläche *Materialtoleranz berücksichtigen*
(en „Apply material tolerance“). **Fix:** in allen sechs Sprachen das Wort der
Oberfläche nehmen. Sonst stimmt der Changelog: zwölf Zeilen ≤ 200 Zeichen (längste fr
175), gleiche Stelle in allen Sprachen, Feld- und Op-Namen wie im Katalog, als
Eigenschaft, kein Wort der Testfamilie.

## Slicerbeleg, nachgefahren (gepinnt `FFFFF0FF`, eigene G-Code-Auswertung)

Dieselben Bohrplatten wie der Bauagent (A: Ø 6 mit Haken, *Elefantenfuß ausgleichen*;
B: Ø 6,2 ohne beides), Weg des Druckdialogs (`_prepare_plate`, `slice_model`), Breite der
Außenwand-Mittellinie in mm, in Klammern Schicht 1 gegen Mitte.

| Programm (Drucker) | Grundlage Einzug / Loch | ohne Klick: A / B | Rat: A / B | Wahl 0,15 / 0,1 + Rat | eigener Satz |
|---|---|---|---|---|---|
| OrcaSlicer 2.4.2 (K1 Max) | 0,15 / 0 | 38,800 (0,78) / 39,200 (0,38) — Rat liegt an | 39,100 / 39,200 | Loch B−A 0,197 | nichts geschrieben, Block 0 / 0 |
| PrusaSlicer (MK4S) | 0,2 / – | 38,700 (0,85) / 39,100 (0,45) | 39,100 / 39,100 | B 39,200 (0,35); kein Lochausgleich | nichts geschrieben, Block 0 |
| SuperSlicer 2.5.59.13 (MINI) | 0,2 / 0 (`-0.2`) | 38,780 (0,77) / 39,180 (0,37) | 39,180 / 39,180 (Objektwert `first_layer_size_compensation = 0`) | Loch B−A 0,200 (`-0.1` weitet), B 39,280 | nichts geschrieben, Block 0 / 0 |
| Cura 5.13 (Ender-3 V3 SE) | 0 / 0 | kein Schlüssel; 39,140 (0,44) / 39,539 (0,04) | kein Rat | `-s` 0/0, je Netz A 0/0, B −0,15/0,1; Loch B−A 0,201 | – |

Die Werte des Bauagenten sind damit für alle vier Programme bestätigt.

## Bestätigt

- **`MAKER_OWNED` an jedem Ausgang:** 3MF Orca-Familie und Prusa (nur Wahl, Übernahme
  oder Herstellerwert der Kette), Dateiexport ohne Slicer, Cura-Konsole, Cura-Fenster
  (Profil und 3MF je Objekt), Objektwerte über `_applied`. Rücklesung über
  `ORCA_PROCESS`, `PRUSA_PROCESS`, `_read_prusa` mit Vorzeichen.
- **`_play_outputs`:** Kappe ist Ausgang 1 (`lid.py:1984-1999`), Teilen am gerechneten
  Körper, Bolzenscharnier am Deckel (`lid_hinge.hinge_features`) — abgesehen von N1/N2.
- **Merkmale überstehen Folgeschritte:** `created_by` bleibt nach `move_feature`,
  `translate_object`, `rotate_object`, `fillet_edges`, `chamfer_edges`, `mirror_object`,
  `union_objects`, `duplicate_object`, `orient_for_print` (`folgeops.py`).
- **Hauptthread:** `allowances_for` über alle Körper je Projekt unter der Zeitauflösung
  (< 16 ms CPU) für 12 Beispiel- und 77 Korpusprojekte (`zeit_allowances.py`).
- **Testqualität:** 24 von 24 Mutationen rot; am alten Stand 54 von 56 neuen Fällen rot,
  grün nur Prusa-Rücklesung und Dialoganschluss (vorhandenes Verhalten, beide von ihrer
  Mutation gefangen). Stumpfe Zusicherungen nicht gefunden.
- **Regeln:** 1–5, 7–22 ohne Verstoß; 6 (`is_zero`) eingehalten. Druckgleich/gebündelt:
  keine Geometrie- oder Heißpfadänderung; die 36 Fingerabdrücke in `part_ranges.toml`
  folgen dem Quelltext der Module, `test_parts.py` grün.

## Gelaufen

| Lauf | Ergebnis |
|---|---|
| 21 Testdateien des Gebiets ohne Fenster, `-n 4`, gepinnt | 4015 bestanden, 10 übersprungen, EXIT=0 |
| Neue Fenstertests am HEAD (Kopie) | 9 bestanden, Exit 0 |
| Mutationen an HEAD (24) | 24 rot erkannt, Basis 56 bestanden, EXIT=0 |
| Neue Tests am alten Stand `e8c785abd` | 54 rot, 2 grün, Exit 1 (erwartet) |
| `ruff check --no-cache .` | sauber, Exit 0 |
| `ruff format --no-cache --check .` | **Exit 1**, `tests/test_manufacturer.py` |
| `mypy` (Cache im Scratch) | 374 Dateien, keine Fehler, EXIT=0 |
| Kundenweg OrcaSlicer, PrusaSlicer, SuperSlicer, Cura | je EXIT=0 |
| Cura-Fenster am echten Cura, Prusa-3MF ohne Programm, Anordnen am OrcaSlicer | je Exit 0 |

Nicht gelaufen: volles Tor, CI, die übrigen Fenstertests, Bambu Studio, ElegooSlicer,
Creality Print, Anycubic Slicer Next (Tabelle des Bauagenten).

## Urteil

**Nicht.** N1 lässt nach dem üblichen *Anordnen* jeden Nachbarn den Rat bekommen, und
übernommen druckt er mit Elefantenfuß; dazu N2–N4. Nach den Fixes reicht eine
Nachprüfung von `fits.py`, Kalibrierfrage und Tor.
