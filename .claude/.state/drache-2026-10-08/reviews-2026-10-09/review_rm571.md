# Review RM-571 (`F:/solidon-claude-a`, `claude/lauf-a`: `004973704`, `98d9831af`, Merge `b01a96f46`) — solidon3d-review, 09.10.2026

Gelesen: beide Commits vollständig (`analysis.py`, Tests, `druckrat.md`, `slice/CLAUDE.md`,
Begründung), der Merge gegen beide Eltern (`analysis.py` ist die Vereinigung; `ModelSupport` mit
Docstring aus RM-571 und `SliceContour` aus welle2; Register und Archiv), die Aufrufer von
`channel_space`, der Beleg `output/konsolidierung-2026-10-07/codex-claude/belege/lauf-a.md`.

Ausgeführt am Merge-Stand: die 5 neuen und 4 Geschwistertests grün; 70 Sperrtests aus
`test_slice_findings`, `test_export` und `test_estimate` grün (Exit 0); `test_roadmap` und
`test_directory_docs` 31 grün, 3 übersprungen; ruff check und format, mypy auf `analysis.py` ohne
Befund. Mutanten über `_open_above`: „nie erreichbar“ (= Stand RM-566) macht Sims und „je Scheibe“
rot, „immer erreichbar“ überdachte Säule, „je Scheibe“, dünne Wand und Schlitz. Dazu Sonden,
Skripte im Scratchpad (unten).

## Mittel

- **M1 — „Eine Bahn breit“ macht jede Ritze zum offenen Himmel.** `analysis.py:1946–1949`
  (`_eroded(opening, line_width / 2.0)`) zählt eine Öffnung ab 0,42 mm.
  Beleg (`probe_lid.py`, echte Geometrie): der Becher aus dem Test mit Deckel. Ohne Öffnung liegt
  der Sims zu 64 % im Sperrraum, mit Schlitz 0,3 mm ebenso. Mit Schlitz 0,5, 1,0 oder 2,0 mm neben
  dem Sims sind es 4 % wie im offenen Becher. In der Kammer aus dem Schlitz-Test mit 0,5 statt
  0,3 mm ist die Säule zu 0 statt 100 % gesperrt (`probe_slit.py`).
  Warum es zählt: Eine Stütze unter 14 × 14 mm kommt durch 0,5 mm nicht heraus, und „Eine Stütze in
  einer Kammer holt niemand heraus“ (`regel-druckrat.md:335`) gilt mit Schlitz weiter. Das ist ein
  fachlicher Zwilling ohne Entscheidung (`zwillinge.md`): Ob man an einen Raum herankommt,
  beantwortet `_narrow` mit `CHANNEL_WIDTH` 30 mm („Eine Stütze darin bekäme man nicht mehr
  heraus“, `analysis.py:3285–3297`), `_open_above` dagegen mit 0,42 mm. Die Begründung belegt nur
  die Untergrenze, also dass unter einer Bahn nichts herauskommt, nicht, dass eine Bahn genügt.
  Becher (68 mm) und Schüssel (kein Himmel) trennt jede Weite dazwischen.
  Fix: Die Weite des Himmels an der Kanalfrage messen. Etwa den Himmel über dem Fenster Saum plus
  `CHANNEL_WIDTH` bauen und nur eine Öffnung zählen, deren Himmelsstück einen Kreis von
  `CHANNEL_WIDTH` fasst (`_eroded(part, CHANNEL_WIDTH / 2)`), oder eine andere, belegte Weite als
  Entscheidung festhalten. Test: Becher mit Deckel und Schlitz 0,5, 1 und 2 mm, der Sims bleibt
  gesperrt wie im geschlossenen Becher, der offene Becher bleibt frei. Becher, Schüssel, Korpus und
  Kosten neu messen, Begründung und `druckrat.md` nachziehen.

- **M2 — Der Saum reicht an spitzen Ecken bis zehn Bahnbreiten.** `analysis.py:1883`:
  `column.buffer(2.0 * line_width, join_style="mitre")` mit Shapelys `mitre_limit=5`. An einer Ecke
  unter etwa 23° reicht der Saum 5 × 2 Bahnbreiten weit, bei der Vorgabe 4,2 mm, und mit der Düse
  wächst das. `probe_seam.py`: Quadrat 2,8 Bahnbreiten an der Ecke, 30°-Dreieck 7,7, 10°-Dreieck
  und Sichel 10,1.
  Beleg (`probe_tip.py`, echte Geometrie): Becher mit Deckel, die Öffnung im Deckel 3 mm vor der
  Spitze einer Nase am Sims, der Rest unter dem Deckel. Wie gebaut liegen 4 % im Sperrraum (frei wie
  im offenen Becher), mit rundem Saum von zwei Bahnbreiten 64 %. Eine eingesetzte Spitze im
  Tunnel 3 mm unter der Dachkante (`probe_cup.py`, b) liegt zu 0 % im Sperrraum, mit rundem Saum zu
  100 %, ein Rechteck an derselben Stelle zu 100 %.
  Warum es zählt: Der Vertrag in `_seam`, `_open_above`, `regel-druckrat.md:347` und im Archiv
  lautet „zwei Bahnbreiten um ihren Grundriss“. Das Urteil hängt so an der Form (eine Nase macht
  frei, das Quadrat nicht), und spitze Enden haben gerade die Sichelstücke schräger und runder
  Decken.
  Fix: `join_style="bevel"` (nie weiter als zwei Bahnbreiten, wenig Ecken) oder rund; Test mit der
  Nase.

## Leicht

- **L1 — Archiv (Merge).** `ROADMAP-ARCHIV.md:27324–27345`: Der Abschnitt RM-571 (09.10.2026)
  steht zwischen „Filamentlager … (08.09.2026)“ (`:27281`) und „RM-027 entfällt … (09.09.2026)“
  (`:27347`), die übrigen Abschnitte vom 09.10. stehen am Ende (RM-680 `:46240`). In `:43907–43908`,
  einer Zeile, die der Merge angefasst hat, zeigt „Warum, mit allen verworfenen Wegen“ auf
  `regel-schichtanalyse.md`. Der Weg von RM-566 und RM-571 steht aber in
  `regel-druckrat.md:256–380`, und der Eintrag RM-571 nennt seine Begründung gar nicht. In `:27343`
  steht „am alten Stand rot“, das gilt aber nur für Sims und „je Scheibe“; überdachte Säule, dünne
  Wand und Schlitz sind Gegenproben (nachgestellt). Fix: Abschnitt ans Ende verschieben, Verweis auf
  `regel-druckrat.md` setzen, den Satz genau fassen.
- **L2 — Begründung `regel-druckrat.md`.** In `:356–359` sind vier Lagen genannt (Drucklage 50°,
  55°, 60°, Dateilage 55°), aber nur drei Volumen in anderer Folge. Laut Beleg sind es
  186 704 / 177 017 / 169 243 / 53 009 mm³. Der Satz in `:352–353` „dieselbe Grenze wie ‚zwei
  Übergriffe breit‘“ stimmt nicht: Der Sperrraum verlangt mehr als zwei Bahnbreiten
  (`analysis.py:4544`, `_eroded(part, line_width)`), die Öffnung mehr als eine (`:1948`). Fix: je Lage
  ein Wert, den Satz berichtigen (mit M1 ohnehin neu).
- **L3 — Neue Tests nach dem Merge mit altem Konturtyp.** `tests/test_slice_findings.py:1127/1133`,
  `:1148/1154`, `:1174/1191` geben `app.core.types.Polygon` in `open_columns`. Seit welle2 ist das
  `tuple[SliceContour, …]` (`analysis.py:3401`), und die vier Geschwister in `:969–1060` hat der
  Merge auf `tests.helpers.slice_contour` umgestellt. Es läuft nur, weil `_channel_space` `outline`
  und `holes` per Duck-Typing liest; `piece_area` an diesen Stücken wirft (`_area` fehlt), und mypy
  prüft `tests/` nicht. Fix: `slice_contour(column)`.
- **L4 — Gegenprobe über eine womöglich leere Menge.** `tests/test_slice_findings.py:1137–1139`
  läuft über die Scheiben mit `high <= 18.0`, ohne zuzusichern, dass es welche gibt (`tests.md`, „Ein
  Verbotstest über eine leere Menge ist immer grün“, Rechenergebnis). Heute sind es 12. Fix: Liste
  bilden und `assert len(covered) > 5` wie im Sims-Test.
- **L5 — Erreichbar wird die ganze Säule, auch tief unter einem Dach.** `analysis.py:4585–4587`
  spart eine erreichbare Säule mit ihrem ganzen Grundriss aus. Beleg (`probe_strip.py`, eingesetzte
  Säule wie in den Tests): ein Streifen 2 × 28 mm vom offenen Becher 14 mm in den Tunnel (8 mm, nach
  `CHANNEL_WIDTH` ein Kanal). Unter dem Dach liegen 0 % im Sperrraum, auch tiefer als 6 mm; mit
  `_open_above` → False sind es 100 %. An der Schüssel berührt kein Stück den Himmel (Beleg); der Fall
  braucht ein Stück, das aus dem Offenen in einen Kanal reicht. Die Begründung nennt diese Folge
  nicht. Fix: entscheiden und festhalten, oder nur den Teil der Säule aussparen, der nicht in
  `_narrow` liegt; Test mit dem Streifen.

## Ohne Befund

- **Regeln 1–22:** Es gibt kein Qt und keine Geometrieänderung, gerechnet wird in Millimetern, und
  kein `==` steht auf Fließkomma (die Tests nehmen `approx`). Statt einer Zahl steht die Bahnbreite,
  die Faktoren sind in `_seam` und `_smallest_opening` benannt. Kein Zufall, keine neue Abhängigkeit,
  keine Oberfläche, englische Bezeichner.
- **Geometrie:** Der Himmel je Scheibe reicht von `chunk[-1] + 1` bis zur obersten Schicht, die
  Scheibe selbst geht über ihr `material` ein, also ist der Schacht von der Scheibe bis über das
  Teil frei. Die Startmenge in `sky_of` und `crossing` folgen derselben Bedingung, es gibt keinen
  KeyError. Früher Ausstieg und `intersects(grown)` wirken nicht aufs Ergebnis. `sky_lock` schützt
  `shades` und `skies`, und der Parallelweg läuft im Test mit (120 Schichten ≥ `PARALLEL_FROM`).
- **Zwillinge:** `writer._support_blocker` (`:1991`), `advise` (`:1314`) und `estimate` (`:496`,
  `:562`) fragen `channel_space`. `print_time` fragt die Sperre nicht, und `_enclosed` hat keine
  zweite Verwendung.
- **Kosten:** nicht neu gemessen (sparsam). Der Beleg (Median aus 8 Läufen im Wechsel) zeigt den
  Becher bei 0,08 → 0,17 s und den Eiffelturm bei 20,5 → 19,4 s, Schüssel und Drache werden
  schneller. §31 hat für die Sperre keine Zeile, und der Eiffelturm wird nicht langsamer. Den Fix zu
  M1 mitmessen (größeres Himmelsfenster).
- **Merge:** Register-Zeile und Abschnitt RM-571 sind weg, die Sprungmarken treffen.
- **Changelog „kein Punkt“:** richtig. `git tag --contains 43e111dc6` (die Ausnahme im
  Umschlossenen aus RM-566) nennt keinen Tag, und v0.5.3 sparte alle Säulen aus
  (`git show v0.5.3:app/core/slice/analysis.py`, Zeile 3619). Daran ändern M1 und M2 nichts.

## Außerhalb des Prüflings (vorbestehend, im Slicer ungeprüft)

- `_model_support` (`analysis.py:4147`) merkt je Stück nur die erste, höchste Auflage. Steht unter
  einer Kanaldecke irgendwo etwas Höheres, sperrt sie nur noch darüber. Kammer aus dem Schlitz-Test
  mit Schlitz 1 mm: ohne Insel sperrt sie 8,5–29,5 mm (20 Scheiben), mit einer Insel 4 × 4 mm darin
  nur 22,5–29,5 mm (6 Scheiben); mit 0,3 mm und Insel 22,5–28,5 mm (`probe_real_debug.py`). Ob ein Slicer dann Stützen in den Kanal
  stellt, ist nicht gemessen. Prüfen und ins Register.

Sonden: `%TEMP%\claude\F--3D-Druck\6d004019-0ef1-44d0-8062-699c55490a5e\scratchpad\`
(`probe_seam.py`, `probe_cup.py`, `probe_slit.py`, `probe_lid.py`, `probe_tip.py`, `probe_strip.py`,
`probe_real.py`, `probe_real_debug.py`, `mutant_rm571.py`, Ausgaben `*.txt`).

**Urteil:** Nein, so noch nicht. Den Sims im offenen Becher löst RM-571 richtig und belegt es, aber
M1 und M2 machen einen geschlossenen Becher mit Schlitz bzw. einen Sims mit spitzer Nase zum offenen
Becher. Vor dem Merge gehören beide mit Test und neuer Messung behoben, die leichten gleich mit.
