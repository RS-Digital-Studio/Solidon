# Nachprüfung RM-624 (F:\sl-kontakt, tests/kontakt-slicertest, e5533f2ce)

Agent solidon3d-review, 10.10.2026. Nur gelesen und gemessen, im Worktree nichts geändert
(Läufe mit `-p no:cacheprovider`, `PYTHONDONTWRITEBYTECODE=1`, `--basetemp` und Caches im
Scratch; einmal `git fetch origin`, das nur Remote-Refs nachzieht). Scratch:
`scratchpad\rv624n\` (Sonden `probe_*.py`, `test_probe_*.py`, Ausgaben `*.txt`). Slicer gepinnt
(`/affinity FFFFF0FF`). Die Maschine war die ganze Zeit mit über zwanzig fremden
Rechenprozessen belegt — Zeiten sind Wanduhr, Verhältnisse im selben Lauf gemessen.

Gegenstand: `git diff a9e4d3f64..e5533f2ce` (c95d542ed erster Stand, e5533f2ce Fixes des
Erstreviews `reviews-2026-10-09/review_rm572_rm624.md`, Abschnitt RM-624). Jede Zeile von
`tests/gcode_contact.py`, des neuen Teils von `tests/test_real_slicers.py`, Karte, Regel,
Register und Archiveintrag gelesen; dazu `advise.rounds_to_whole_layers`,
`handover.organic_styles`/`ignored_under_trees`, `slicer_keys` (Tabellen, Kontaktlage,
`limitation`), `gcode._arc_center`/`_arc_sweep`, `slicer-auswahl.yml` (Zweig und welle3),
`ci_selection` und RM-628 in `F:\sl-cura` (`8c2c381e8`, nur gelesen).

## Urteil

**Nicht — noch nicht.** Alle neun Erstbefunde sind behoben und mit Gegenprobe belegt; der Test
misst in allen sechs Programmen exakt und wird am echten Slicer rot, wenn Abstand oder untere
Lagen nicht ankommen (24 Gegenproben). Offen: **M1** (mittel) — der Cura-Ausschluss hängt an
RM-628, das in keinem Register steht; **L1** (leicht) — drei Teile der Messung hält kein
synthetischer Fall, anders als Archiv und Commit sagen. Beide Fixe sind klein, L1 ist im Scratch
erprobt. **Nach den Fixen kann RM-624 ohne weitere Nachprüfung landen** (ein mittlerer Befund,
Fixe mechanisch). Eine zunächst notierte L2 (CI-Auslöser) habe ich zurückgenommen, siehe unten.

## Läufe

| Lauf | gesammelt / gelaufen | Ergebnis |
|---|---|---|
| Zwölf echte Slicerfälle `test_the_support_contact_arrives_as_solidon_says`, gepinnt | 12 / 12 | 12 passed, EXIT=0, 148,9 s |
| Synthetische Fälle (`-k contact_measure`) | 7 / 7 | 7 passed, Exit 0 |
| Gezielt ohne Slicer/Fenster: `test_supply_chain`, `test_directory_docs`, `test_roadmap`, `test_toolchain`, `test_slicer_selection`, `test_affected_tests`, `test_real_slicers` (zweimal) | 303 / 303 | 299 passed, 4 übersprungen (3× keine lokalen Erinnerungen im Worktree, 1× kein Paket unter `website/dl/`), Exit 0 |
| `ruff check`, `ruff format --check` über die geänderten Dateien | — | grün; mypy prüft laut `pyproject.toml` nur `app/`, der Diff berührt es nicht |
| Würfel, sieben Programme, gepinnt (Zeitmaßstab) | 7 / 7 | 7 passed, EXIT=0 |
| Würfel und Kontaktfälle Orca + Elegoo im selben Lauf, zweimal | 6 / 6 je Lauf | 6 passed, EXIT=0 (beide) |
| Gegenprobe „Abstand verloren“, sechs Programme × Gitter/Baum (`test_probe_kontakt.py`) | 12 / 12 | alle 12 rot nach den Zusicherungen des Tests; Lauf danach per PID beendet (EXIT=1 durch Abbruch, nicht durch Fehler) |
| Gegenprobe „untere Lagen verloren“ (`test_probe_lagen.py`) | 12 / 12 | 8 rot, 4 grün (siehe unten), EXIT=0 |
| Cura über den Weg des Tests (`test_probe_cura.py`) | 2 / 2 | EXIT=0, gemessen, siehe Cura-Frage |

Programme lokal: ElegooSlicer 1.5.3.5, OrcaSlicer 2.4.2, Bambu Studio 02.08.02.61, Creality
Print 7.3.0.6149, Anycubic Slicer Next 2.0.0.3, PrusaSlicer 2.9.6, Cura 5.13.0.

Messung an den zwölf G-Codes des Laufs (`probe_mess.txt`), Zellen oben·unten mit `inset=4`:

| Programm | Gitter: oben / unten / untere Lagen / Zellen | Baum: oben / unten / untere Lagen / Zellen |
|---|---|---|
| Elegoo | 0,28 / 0,28 / 4 / 199·200 | 0,4 / 0,4 / 3 / 200·60 |
| Orca | 0,28 / 0,28 / 4 / 179·179 | 0,4 / 0,4 / 3 / 179·71 |
| Bambu | 0,28 / 0,28 / 4 / 179·179 | 0,4 / 0,4 / 0 / 180·71 |
| Creality | 0,28 / 0,28 / 4 / 179·179 | 0,4 / 0,4 / 0 / 178·57 |
| Anycubic | 0,28 / 0,28 / 4 / 179·179 | 0,4 / 0,4 / 0 / 179·76 |
| Prusa | 0,28 / 0,28 / 3 / 201·200 | 0,4 / 0,4 / 0 / 200·93 |

Die Spalten (`probe_spalte.txt`) zeigen, warum die Unterseite die Bahnhöhe braucht: Unter
Gitter liegt die unterste Stützlage bei 3,48 mm mit eigener Höhe 0,2, darüber 0,28 (Elegoo,
Bambu) bzw. 0,298 (Orca, Prusa): 3,48 − 0,2 − 3,0 = 0,28. Die Einzelwerte je Zelle
(`probe_verteilung.txt`) sind mit `inset=4` fast rein; ohne ihn zählen Elegoo- und
Prusa-Gitter 35 bzw. 70 Randzellen mit −0,066 bzw. −0,116 mm — der Rand von 4 mm bleibt nötig,
der Kommentar `test_real_slicers.py:541–542` stimmt.

## Erstbefunde 1–9

| # | Stand | Beleg |
|---|---|---|
| 1 Linux/macOS | Durch Roberts Regel kein Befund. Der Test läuft dort: dieselbe Fixture wie der Würfel, der in Lauf 37936320906 auf Ubuntu, macOS ARM und Intel grün war; `ci_selection` wählt `tests/test_real_slicers.py -m slicer` mit allen sieben Programmen, `SOLIDON_REQUIRE_SLICERS` macht ein fehlendes rot. Auf welle3 ruft der Push nach main die Slicerauswahl selbst auf (`build.yml`, Job `slicer-selection`, `workflow_call`). Versionen wie lokal bis auf Anycubic unter Linux (Paket „2.0.06“, Datei v2.0.0.5) — unbelegt bis zum Lauf auf main; weicht es ab, wird der Fall dort rot, wie er soll. Laufzeit: ein Kontaktfall kostet 0,8–2,0 Würfel (zwei Läufe im selben Takt: Orca 0,78/1,28 und 1,41/1,99, Elegoo 1,13/1,89 und 1,23/1,11); die CI-Würfel der sechs Programme summieren sich auf 18 s (Linux), 26 s (Intel), 30 s (ARM) — der Kontakttest bringt je Job rund 1–2 min, bisher höchstens 77 von 120 min. | `ci/`, `lauf_verhaeltnis_*.txt` |
| 2 verlorener Abstand unter Bäumen | **Behoben**: Gitter 0,28, Bäume 0,44 → 0,4, ±0,02 (`test_real_slicers.py:503, 555–556`). Am echten Slicer mit dem Abstand des Herstellerprozesses: 12 von 12 rot (Tabelle unten). | `probe_kontakt.txt` |
| 3 leere Menge | **Behoben**: `top_cells > 20`, `bottom_cells > 20` vor den Werten (`:553–554`); gemessen 57–201 Zellen, auch ohne untere Trennschicht steht der Baum auf dem Sockel. | `probe_mess.txt` |
| 4 Unterseite unter Gitter | **Behoben**: Höhe der eigenen Stützbahn je Zelle und Ebene (`gcode_contact.py:208–210, 260–266`), Nachbarschaft ausgeschlossen (`:236–259`). Die alte Messung aus c95d542ed ist an denselben G-Codes in 8 von 12 Fällen rot (unten Elegoo 0,4, Orca 0,2, Bambu 0,4, Creality 0,2, Anycubic 0,4, Prusa 0,0 mit 0 Lagen; Elegoo-Baum 2 Lagen), die neue misst überall 0,28. Archivbegründung korrigiert. | `probe_mess.txt` |
| 5 Prusa `Skirt/Brim` | **Behoben** (`gcode_contact.py:30`). Der synthetische Fall wird mit der Verstümmelung rot, aber aus anderem Grund (L1c). Im echten Prusa-G-Code kommt kein `Skirt/Brim` vor (MK4S-Prozess ohne); nur Anycubic-Baum schreibt `Brim`. | `probe_synth.txt`, `probe_rand.txt` |
| 6 G2/G3 | **Behoben** (`gcode_contact.py:83–116`, `_MOVES`). Synthetisch rot ohne Bögen und als Sehne. An echten G-Codes ändert sich das Urteil nicht (Median), die Zellen sinken: Prusa-Baum unten 93 → 43, Bambu 71 → 40, Creality 57 → 34. | `probe_synth.txt`, `probe_mess.txt` |
| 7 Docstring Aufsicht | **Behoben**: `_inside` über die Zellen mit Modellbahn; Reichweite `ceil(inset/2 + 0,5) − 1` nachgerechnet (4 mm → 2 Zellen, nächste Außenkante 5 mm). | Code |
| 8 `helpers.py` | **Behoben**: `ci_selection.py tests/gcode_contact.py` → nur `tests/test_real_slicers.py -m slicer`, keine Fensterdatei; Regel `.claude/rules/tests.md:35–38`. | `ci_sel*.txt` |
| 9 Karte | **Behoben** (`tests/CLAUDE.md:44`, `:118`). | Code |

## Neue Befunde

### Mittel

**M1 — Der Cura-Ausschluss hängt an RM-628, und RM-628 steht in keinem Register.**
`tests/test_real_slicers.py:487–488`, `ROADMAP-ARCHIV.md:27367–27372`, `ROADMAP.md`.

- Beleg: Cura über den Weg des Tests auf derselben Platte (`probe_cura.txt`, gemessen mit
  `support_contact`): Gitter 0,28 → oben 0,28, unten 0,40; Baum 0,44 → oben und unten 0,60;
  untere Lagen je 3; 180·180 bzw. 180·112 Zellen. Der heutige Sollwert des Tests
  (`rounds_to_whole_layers("cura")` → nächste Schicht) wäre 0,20/0,20 bzw. 0,40/0,40 — alle vier
  Abstandszusicherungen rot. Das ist ein bekannter Produktfehler: Am Stand des Zweigs rät
  Solidon einem Cura-Kunden mit PETG unter Gitter 0,2 mm (`support_gap_target`; Orca-Familie
  0,28) und sagt am Feld „Cura rechnet „Abstand oben und unten“ in ganzen Schichten zu
  0,20 mm.“ (`app/core/export/slicer_keys.py:1661–1672`), während Cura oben genau 0,28 und unten
  0,40 druckt (`probe_cura_rat.txt`).
- RM-628 steht in keinem `ROADMAP.md`: nicht auf diesem Zweig, nicht auf origin/main
  (`a09d3a728`), welle3 (`e4cb7b3b3`) und nicht auf dem RM-628-Zweig selbst (dort nur ein
  Archiveintrag eines unfertigen Stands). Der Docstring nennt den richtigen Grund ohne Nummer,
  das Archiv einen falschen: „Cura und SuperSlicer fehlen: RM-622 hat sie nicht gemessen.“
  Regel: `CLAUDE.md`, „Offene Arbeit steht im Register von `ROADMAP.md` und nirgends sonst“.
  Landet RM-624 vor RM-628, steht auf main ein Test, der Cura bewusst auslässt, und ein falscher
  Kundensatz — beides nirgends als offen geführt.
- Fix: RM-628 ins Register (Titel wie im RM-628-Archiv; Abnahme: Cura in
  `test_the_support_contact_arrives_as_solidon_says`, siehe Cura-Frage); Docstring `:487–488`
  und Archiv `:27367` nennen RM-628 als Grund und Folgepunkt („Cura rundet auf und kommt mit
  RM-628 dazu“).

### Leicht

**L1 — Drei Teile der Messung hält kein synthetischer Fall, obwohl Archiv und Commit es sagen.**
`ROADMAP-ARCHIV.md:27363–27365`: „jede verstümmelte Fassung der Messung und die alte aus
`c95d542ed` werden dort rot“. Gegenprobe über die sieben synthetischen Fälle je Fassung
(`probe_synth.txt`): alte Messung 4 rot, ohne G92 1, ohne Bögen 1, Bogen als Sehne 1, ohne
untere Nachbarschaft 2, Skirt/Brim als Modell 1 — **ohne Bahnhöhe 0, ohne obere
Nachbarschaft 0**.

- a) `tests/test_real_slicers.py:385–417` (`bahnhoehe`): Der Stapel 1,16/1,44/1,72 hat den
  Schritt der Bahnhöhe, der Rückfall ohne `;HEIGHT:` misst dasselbe. An den echten G-Codes misst
  der Rückfall unter Gitter 0,2 (Elegoo, Bambu, Anycubic) bzw. 0,182 (Orca, Creality, Prusa)
  statt 0,28, weil die unterste Lage eigene Höhe hat. Das fängt nur der Slicertest (sechs
  Gitterfälle rot, `probe_mess.txt`).
- b) `tests/gcode_contact.py:242` (`and "model" not in under`): Ohne die Zeile bleiben alle 7
  synthetischen und alle 12 echten Fälle grün, obwohl Elegoo- und Prusa-Gitter dann 72 bzw. 76
  Scheinzellen mit 0,0 mm neben 200 richtigen zählen (`probe_oben.txt`); nur der Median hält.
- c) `tests/test_real_slicers.py:420–443`: Der Rand liegt unter den Trennschichtflecken.
  „Skirt/Brim als Modell“ wird rot über `top_cells == 0` (die Nachbarschaftsregel schließt die
  Flecken aus), nicht über die im Docstring genannte breitere Aufsicht. Mit einem Rand nur außen
  um das Dach — wie ihn PrusaSlicer tatsächlich legt — zählt die Verstümmelung mit `inset=4`
  zwei Flecken statt einem (`probe_rand.txt`).
- Fix, im Scratch erprobt (`probe_fixvorschlag.py`/`.txt`): im Fall mit Bahnhöhe die unterste
  Stützlage 0,2 hoch wie in den echten G-Codes (1,08 mit `;HEIGHT:0.2`, dann 1,36 und 1,64 mit
  `;HEIGHT:0.28`; ohne Bahnhöhe gleichförmig wie jetzt), die Nachbarzelle mit
  `Support interface` statt `Support` und `assert measured.top_cells == 0`. Am Zweig grün; rot
  ohne Bahnhöhe, ohne obere und ohne untere Nachbarschaft und mit der alten Messung. Rand-Fall:
  `Skirt/Brim` nur als Ring außen um das Dach. Danach stimmt der Archivsatz.

### Zurückgenommen

**CI-Auslöser im Archiv** (`ROADMAP-ARCHIV.md:27365–27367`, „nimmt die Slicerauswahl beim Push
auf main ab“): Auf dem Zweig kennt `slicer-auswahl.yml` nur `workflow_dispatch`, auf welle3 ruft
`build.yml` sie beim Push nach main aber selbst auf (Job `slicer-selection`, `workflow_call`).
RM-624 landet über welle3; zum Landezeitpunkt stimmt der Satz. Kein Befund.

## Cura-Frage

**Heute:** Cura steht nicht in `_CONTACT_PROGRAMS` (`tests/test_real_slicers.py:447–454`),
der Fall entsteht gar nicht (weder gelaufen noch übersprungen); Grund im Docstring `:487–488`.
**Das ist richtig, solange RM-628 fehlt:** Mit Solidons heutiger Tabelle wäre der Fall in allen
vier Abstandszusicherungen rot (M1), und `xfail(strict=True)` taugt nicht — der JUnit-Bericht
führt xfail als übersprungen, und die Slicerauswahl wertet jeden übersprungenen Fall als rot.
Was fehlt, ist der Registereintrag (M1).

**Wenn RM-628 landet** (`advise.gap_rounding`, `advise.printed_gap`, Stand `8c2c381e8`):

1. `tests/test_real_slicers.py:447–454`: `"cura"` in `_CONTACT_PROGRAMS`.
2. `:547–556`: statt `rounds`/`printed` getrennt oben und unten aus der einen Quelle:
   `top = advise.printed_gap(gap, layer, advise.gap_rounding(setup.flavour, style=style, organic=organic))`,
   `bottom = advise.printed_gap(gap, layer, advise.gap_rounding(setup.flavour, style=style, organic=organic, below=True))`,
   dann `assert measured.top_gap == pytest.approx(top, abs=0.02)` und ebenso `bottom`. Das
   ersetzt auch das eigene `round(gap / layer) * layer` — Pythons `round` rundet x,5 zur geraden
   Zahl (`round(0.5) == 0`), die Programme und `printed_gap` runden auf: Anycubics
   Herstellerwert 0,1 kam unter Bäumen als 0,2 an (`probe_kontakt.txt`). Bei 0,44 trifft es
   nicht, aber es wäre eine zweite Rundungsregel.
3. **Sollwerte Cura:** Gitter (0,28): oben **0,28**, unten **0,40**; Baum (0,44): oben **0,60**,
   unten **0,60**. Die sechs übrigen bleiben 0,28/0,28 und 0,40/0,40 (`exact` bzw. `nearest`).
   Gemessen am Weg des Tests mit `support_contact` (`probe_cura.txt`): genau diese Werte; RM-628
   maß dieselben mit eigener Messung.
4. `:557–566`: untere Lagen für Cura **3** (Zweig `else`, `bottom_layers`), gemessen unter Gitter
   und Baum — Cura druckt sie auch unter Bäumen; nichts zu ändern.
5. `:484–488`: Cura-Satz streichen, „Cura rundet auf (`round_up_divide`)“ ergänzen.
6. RM-628 bringt mit `_CuraGaps`, `_cura_support_gaps` und zwei Tests
   (`F:\sl-cura\tests\test_real_slicers.py:297–506`) eine zweite Messung desselben Kontakts —
   ein Zwilling von `gcode_contact.support_contact`, das Cura nachweislich misst. Beim Landen
   zusammenlegen: Cura im Kontakttest, RM-628 behält nur seine Zusicherung auf den Feldsatz
   (`slicer_keys.limitation`) als Zeile darin. Beide Zweige ändern Zeile 29 (Import
   `slicer_keys`) und hängen ans Dateiende an — Konflikt beim Merge erwartet.

## Gegenproben am Slicer

Weg und Zusicherungen wie im Test, nur je eine Wahl weggelassen — dann gilt der Wert des
Herstellerprozesses, als käme Solidons Wert nicht an. Sollwerte des Tests: Abstand 0,28 bzw.
0,40, untere Lagen 4 (Orca-Familie, Gitter), 3 (Prusa-Gitter, Elegoo/Orca-Baum), 0 (übrige
Bäume).

| Programm | Abstand verloren, Gitter | Abstand verloren, Baum | untere Lagen verloren, Gitter | untere Lagen verloren, Baum |
|---|---|---|---|---|
| Elegoo | rot: 0,2/0,2 (Hersteller 0,2) | rot: 0,2/0,2 | rot: 3 statt 4 (Hersteller 2) | rot: 2 statt 3 |
| Orca | rot: 0,2/0,2 (0,2) | rot: 0,2/0,2 | rot: 3 statt 4 (2) | rot: 2 statt 3 |
| Bambu | rot: 0,2/0,2 (0,2) | rot: 0,2/0,2 | rot: 3 statt 4 (2) | grün — druckt dort keine |
| Creality | rot: 0,2/0,2 (0,2) | rot: 0,2/0,2 | rot: 3 statt 4 (2) | grün — druckt dort keine |
| Anycubic | rot: 0,1/0,1 (0,1) | rot: 0,2/0,2 (0,1 aufgerundet) | rot: 3 statt 4 („wie oben“ −1 → 2) | grün — druckt dort keine |
| Prusa | rot: 0,2/0,2 (oben 0,2, unten 0 = wie oben) | rot: 0,2/0,2 | rot: 0 statt 3 (Hersteller 0) | grün — druckt dort keine |

Die vier grünen Baumfälle sind richtig: Diese Programme legen unter organischen Bäumen keine
untere Trennschicht, ein verlorener Wert ändert am Druck nichts. Die Herstellerwerte bestätigen
den Docstring (`:483–485`) und den Kommentar zur Kontaktlage (`:561–562`: Standard 2 → 3).

## Merge-Hinweis für welle3

`tests/CLAUDE.md:44` lautet auf welle3 schon „(`slicer`-Marker, beim Push nach main auf Linux
und macOS)“; RM-624 schreibt dieselbe Zeile mit „vor dem Merge …“ um. Beim Hereinmergen von
welle3 die Fassung von welle3 nehmen und RM-624s Zusatz (Kontaktfrage, „die Kontaktmessung dort
auch synthetisch“) daneben behalten. `.claude/rules/tests.md`: Der neue Absatz steht hinter
„Neues bringt seinen Test …“, das auf welle3 unverändert ist — dort kein Konflikt zu erwarten.

## Regel „Gebündelt rechnen, druckgleich statt bitgleich“ (vom Koordinator nachgereicht)

Angewandt auf das geprüfte Gebiet: `support_contact` ist eine Python-Schleife je G-Code-Zeile
und je Abtastpunkt. Gemessen (`probe_kosten.txt`, CPU-Zeit Median aus drei, Spitze mit
tracemalloc): 0,14–0,95 s je G-Code, zusammen 4,05 s über die zwölf Fälle, Spitze 7,5–18,5 MB;
daneben kostet jeder Slicerlauf Sekunden bis Minuten. Kein heißer Pfad, und der Leser ist eine
Zustandsmaschine über Zeilen (Art, Bahnhöhe, E-Modus, Lage), die sich nicht als Feldrechnung
bündeln lässt, ohne ihn umzubauen. **Kein Fund.** Druckgleich/bitgleich ist nicht berührt (nur
Tests, keine Geometrie).

## Regeldurchgang (`/regelcheck`)

Berührt sind nur Tests, Karte, Regel und Register. Geprüft: 1 (kein Qt in `gcode_contact.py`;
der Slicertest holt `_PlateJob`/`_prepare_plate` aus `app.ui` wie der Würfel), 6 (Abstände mit
`pytest.approx`; `bottom_interface_layers == layers` vergleicht einen Median ganzer Zahlen,
exakt darstellbar), 10 (kein `eval`), 11 (Slicer nur extern aufgerufen), 14 (nur G-Code
gemessen), 15 und 22 (keine neue Abhängigkeit, nur Standardbibliothek). Sprachregel in
`tests/`: Bezeichner englisch, Docstrings deutsch; die Kennungen `bahnhoehe`/`ohne-bahnhoehe`
folgen dem Bestand der Suite (`ohne-stuetze`, `vorwaerts` u. a.). Keine Verstöße. Die übrigen
Regeln berührt der Diff nicht. Changelog „nein (Test)“ ist richtig: nichts Kundenspürbares.

## Bestätigt

- Bahnarten je Programm vollständig: Orca-Familie `Support`/`Support interface`, Bambu dazu
  `Support transition`, Prusa `Support material`/`Support material interface`; `Brim`
  (Anycubic) und `Custom` fallen heraus.
- `;HEIGHT:` (Orca-Familie, Prusa) und `; LAYER_HEIGHT:` (Bambu) werden je Bahn geschrieben und
  gelesen; `MAX_Z_HEIGHT`/`Z_HEIGHT` treffen den Ausdruck nicht.
- Kontaktlage der Orca-Familie unter Gitter (`slicer_keys.py:483–485`): 3 geschrieben → 4
  gedruckt in allen fünf; mit dem Herstellerwert 2 → 3.
- Die Sollwerte kommen aus Solidons Tabellen (`rounds_to_whole_layers`, `ignored_under_trees`,
  `organic_styles`); der Test hält Tabelle und Programm in beide Richtungen gegeneinander. Die
  Wahl 0,28/0,44 unterscheidet rechnerisch auch eine vertauschte Stützart (Baum statt Gitter
  ergäbe 0,2 statt 0,28, Gitter statt Baum 0,44 statt 0,4 — beides außerhalb ±0,02; nicht am
  Slicer nachgefahren).
- Keine verwaisten Verweise auf `#rm-624` nach dem Umzug ins Archiv.
