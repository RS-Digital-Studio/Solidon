# Nachprüfung RM-629: Fixrunde zu „Schräger Schacht, Schicht für Schicht“ (rv629n)

Gegenstand: Worktree `F:\sl-schacht`, Zweig `einstellungen/schacht-rm629`, Spitze `0463b5046`
(Merge welle4 `ac244486b`, welle4 auf origin unverändert). Fix-Diff `a675390e6..8bbb07ca3`
(`dc102c0d0` F1, `297e872da` F6, `a1af92f21` F2, `5ae6de331` Rücknahme, `008d64ed4` F4,
`8bbb07ca3` F3/F5). Erstreview `review_rm629.md`, Fixbericht `berichte-2026-10-10\rm629b.md`.
Scratch: `%TEMP%\claude\F--3D-Druck\b00d64ab-ed49-460e-9651-1d89ea000640\scratchpad\rv629n\`.
Nichts im Worktree geändert. Sonden laufen aus ausgepackten Bäumen (`git archive`, dazu der
übersetzte Kern `_chain` aus dem Hauptbaum, `.pyx` gleich): `fin` = `0463b5046` (mit Unterlagen
und Website-Texten), `f1` = `dc102c0d0` (a675390e6 + F1), `base` = `a675390e6`, `w4` = welle4.
`app.__file__` geprüft, in pytest über `pfad_plugin.py` auch in jedem xdist-Arbeiter. Läufe
gepinnt `FFFFF0FF`.

Stand: 11.10. 00:37, abgeschlossen. Alle Läufe fertig, Exit 0 bis auf die erwarteten Roten
(Mutanten, Umgebungsrot im Scratchbaum, abgebrochener Drache-130-Vergleich, siehe Verlauf).

## Urteil (11.10. 00:37)

**Kann landen mit Fix A, ohne ihn nicht.** F1, F2, F4 sind behoben und belegt, F6 für den
einzelnen Schlitz, der quer zu seiner schmalen Seite geneigt ist (45° 22, 40° 24, 30° 27 zu; 31
offen; Ø 34 um 40° offen; drehende Schlitze, Knick in die Senkrechte, senkrecht-dann-schräg ohne
falsche Öffnung); schräg dazu geneigt bleibt ein Band von rund 2 mm (Fund B).
Druckgleich zum F1-Stand in allen übrigen Fällen bis auf zwei sichere Schließungen, die die
Unterlagen als Grenze nennen; echte Modelle unverändert (keine Schachtfrage), Tests, ruff,
format, mypy grün, Merge mit welle4 sauber, Slicer bestätigt Sims und Schlitz wie Solidon sagt.
Offen bleibt eine Klasse falscher Öffnungen, die die Fixrunde nicht schließt und die Unterlagen
ausschließen: Fund A (mittel), ein Weg über zwei verschieden wandernde Löcher (Y, Fischgrät) — im
Slicer 21 m Stütze mehr unter dem Sims eines geschlossenen Gefäßes. Der Fix liegt gegengeprüft
vor (nur die falschen Fälle ändern sich, Tests grün, Leistung gleich); wortgleich übernommen
mit Test, braucht er keine weitere Prüfung. B (leicht) übernehmen oder als Grenze benennen, C
ist eine Zeile im Bauplan. Ohne A nur, wenn Robert die Grenze ausdrücklich hinnimmt und
Docstring, Regel, Begründung und Archiv sie nennen.

## Zu den Fragen des Auftrags

1. **Je Fund:** F1 behoben (Kriechen zeilengleich mit 1b, Test rot am alten Stand laut
   Fixbericht, Mutante „voller Schritt“ 2 rot). F6 für den quer geneigten Schlitz behoben, nicht
   für zwei verschieden wandernde Löcher eines Wegs (Fund A) und nicht ganz für schräg dazu
   geneigte Schlitze (Fund B). F2 behoben und verdrahtet (einziger Leser `_channel_space`, kein
   Cache und keine Serialisierung betroffen, `cache_version` nicht berührt, Merker hängen am
   Winkel bzw. am Schichttupel), Bauplan §9 fehlt (Fund C). F3/F5: Zahlen stimmen, die
   Allaussagen „nie neu offen“/„gleich wie geneigt“ nicht (Fund A/B). F4 gemessen.
2. **Druckgleich:** Endstand gegen F1-Stand in 212 Becherfällen und 190 synthetischen Fällen
   gleich bis auf die gewollten Schließungen und zwei benannte sichere (Wendel r 8, Kegel
   40 → 31 bei 0,2 mm); echte Modelle 0 mm² Abweichung, keine Schachtfrage.
3. **Leistung:** Zickzack +0,41 s (0,5 mm) / +0,94 s (0,2 mm), Deckel 20° +0,08 / +0,13 s CPU;
   keine druckgleiche Beschleunigung gefunden, kein §31-Ziel berührt (Abschnitt unten).
4. **Slicer:** Cura und ElegooSlicer bestätigen Sims (schräg 20°) und Schlitz 45° 22 mm wie
   Solidon sagt; Elegoo-Tunnel 1,08 m kommt aus welle4 (RM-584), nicht aus RM-629.
5. **Merge und Tests:** Merge sauber (je Datei dieselben Änderungen wie auf dem Zweig, die Karte
   mit beiden Zeilen), 5639 Tests grün (eine Umgebungsrot, im Worktree geprüft grün), ruff,
   format, mypy grün, Budgets der Regeln und Karten grün.

## Funde

### A. mittel — Ein verzweigter Schacht und gegenläufige Schlitze öffnen den geschlossenen Becher (Fund 6 nur für einen Schlitz behoben)

`app/core/slice/analysis.py:2245–2255` (`_shaft_step`) mit `_hole_middle` (`:2321–2335`): Die
Mitte des Lochs ist der Schwerpunkt **aller** freien Teile im Fenster, die die Mitten des Wegs
berühren. Liegen die Mitten eines Wegs in zwei Löchern, die verschieden wandern — ein Schacht,
der sich in zwei Äste teilt (Y), zwei Schlitze, gegenläufig geneigt (Fischgrät) —, wandert ihr
gemeinsamer Schwerpunkt kaum. Weil θ die *flachere* der beiden Schätzungen ist
(`rise = min(rise, …)`, `:2253`), wird die Ellipse nie gerechnet (`back <= WIDTH_SIMPLIFY`), und
jeder Ast zählt wieder mit seiner waagerechten Weite `w / cos θ` — genau Fund 6.

Beleg, synthetisch (`probe_ellipse.py`, Platte 20 mm, Säule wie in den Tests, Stützwinkel 45°;
`ellipse_fin_0.5.txt`, `ellipse_fin_0.2.txt`): Y aus einer Öffnung, Äste um ±45°, 22 / 25 / 28 mm
quer zur Achse: **Schacht offen** bei 0,5 und 0,2 mm (senkrecht zu, Soll zu); dasselbe für zwei
Schlitze 32 mm lang nebeneinander, gegenläufig. 31 mm offen (richtig). Ein Schlitz allein:
22–29,5 zu, 30,5/31 offen (richtig). Ursache gemessen (`diag_y.txt`): Wandern der Mitte je
Schicht 0,00, keine einzige Ellipse gerechnet; beim einzelnen Schlitz (`diag_slit.txt`) 1,00 und
zu ab z = 12,75.

Am Becher durch den ganzen Weg (`probe_faelle_n.py`, Anteil des Simses im Sperrraum, großer
Becher Ø 160 mit Sims 30 × 30, weil der Ring der Startkreise am kleinen Becher für zwei Äste zu
schmal ist; `faelle_fin_0.5.txt`, `faelle_fin_0.2.txt`):

| Deckel 20 mm, 45° | 0,5 mm | 0,2 mm | Soll |
|---|---|---|---|
| ohne Deckel | 1 % | 0 % | offen |
| ein Schlitz 22 mm | 29 % | 30 % | zu |
| ein Schlitz 31 mm | 1 % | 0 % | offen |
| **Y in y, Äste 22 / 25 / 28 mm** | **1 / 1 / 1 %** | **0 / 0 / 0 %** | zu |
| Fischgrät 22 mm | 29 % | 30 % | zu |
| **Fischgrät 25 / 28 mm** | **1 / 1 %** | **0 / 0 %** | zu |

Vor RM-629 war jeder dieser Fälle zu (senkrecht gefragt), am Stand F1 ebenso offen wie jetzt.
Regel, Begründung, Archiv und Docstring sagen das Gegenteil: „So zählt ein Schlitz ab 30 mm quer
zur Achse, gleich wie geneigt“ (`analysis.py:2075`), „Grenzen, alle wie vor RM-629 zu, nie neu
offen“ (`regel-druckrat.md:408`), „beide sind wieder zu“ (`ROADMAP-ARCHIV.md:47520`). Beim
Kunden: Stütze unter dem
Sims eines geschlossenen Gefäßes, die durch keinen Ast herauskommt (Slicerbeleg unten).

Fix, im Scratchbaum `fixa` gegengeprüft (`fix_a.diff`, rund 30 Zeilen): je Loch ein Weg.
Zerfallen die Mitten eines Wegs nach dem Schritt in Teile, die in verschiedenen freien Teilen der
Schicht liegen (im Zuschnitt `shade`, Mitten ± R), wird er geteilt — Verlauf `pushes`/`middles`
kopiert, `starts` je Teil. Eine Scheibe ist offen, wenn einer ihrer Wege durchkommt; das hält die
Schlussschleife ohnehin (`True` zuletzt). In `_shafts_pass` statt des Zusammenlegens:

```
for piece in _split_by_hole(way, shade):
    for joined in ways:
        if _same_centres(joined.centres, piece.centres): ...
```

mit `_split_by_hole(way, shade)`: `parts = _areas_of(way.centres)`; bei mehr als einem Teil die
freien Teile von `box(way.centres.bounds ± R) - shade`, die Teile der Mitten je freiem Teil
gruppiert, ab zwei Gruppen je Gruppe ein `_ShaftWay` mit Kopie des Verlaufs. Gemessen:
Synthetik 0,5 und 0,2 mm je 89 von 95 Fällen gleich, die sechs anderen genau die falschen
Öffnungen, jetzt zu (`ellipse_fixa_*.txt`); Becher 0,5 und 0,2 mm je 101 von 106 gleich, die
fünf anderen die falschen Öffnungen am großen Becher, jetzt 29 bzw. 30 %
(`faelle_fixa_*.txt`); Kriechen
zeilengleich; `test_slice_findings.py` + `test_advise.py` 548 bestanden, Exit 0
(`tests_fixa.txt`). Test zum Fix, fertig im Muster der synthetischen Schachttests
(`test_vorschlag_y.py`: Platte z 10…30, zwei Äste `box(s, −30, s + W, 30)` und
`box(−s − W, −30, −s, 30)` mit s = z − 10, W = w / cos 45°, Säule `box(−2, −2, 2, 2)` in Schicht 4,
senkrecht zu): Äste 22 und 28 mm zu, 31 mm offen — am Endstand 22/28 rot, mit Fix A alle grün
(`test_vorschlag_y.txt`). Ohne Fix: Grenze in Docstring, Regel, Begründung und Archiv ehrlich
nennen (die Sätze oben streichen) und neuer Punkt.

### B. leicht — Ein diagonal geneigter Schlitz zählt bis rund 2 mm zu weit

`analysis.py:2249–2256`: Die Neigung kommt aus der flacheren Schätzung, die Richtung aber immer
aus dem Wandern der Mitte, sobald es zwei Mitten gibt. Ist ein Schlitz nicht quer zu seiner
schmalen Seite geneigt, sondern schräg dazu (Neigungsrichtung 45° gegen die schmale Achse),
schiebt die Wand nur mit ihrer Normalkomponente (gemessen 0,51–0,58, also ~30°), während die
Mitte entlang der Achse wandert (1,0, 45°). Die Ellipse liegt dann entlang der Achse mit 30°
und ist quer zur schiebenden Wand zu schmal (`diag_diag.txt`: Richtung (+1, 0), Neigung
26,8–30°).

Beleg: synthetisch Schlitz mit runden Enden, schmale Achse 45° gegen die Neigung, 45°:
29 mm offen bei 0,5 mm, 28 und 29 mm offen bei 0,2 mm (`ellipse_fin_*.txt`); am Becher
(`diagonal psi45`, eckig) 29 mm offen bei beiden Schichthöhen, 27 mm zu. Schmales Band unter
`CHANNEL_WIDTH`, unsichere Seite.

Fix: Richtung und Neigung aus derselben Schätzung — ist der Schub die flachere, die Richtung
der Schubsumme (`fix_b.diff`, sechs Zeilen). Gegen die schiebende Wand ist die Ellipse dann so
breit wie nötig (die Ebene mit Normale e₁ wandert je Höhe um tan θ_Schub, und
R / cos θ_Schub = R / |e₁ waagerecht|); Knick und Kegel bleiben, wie sie sind (dort ist die Mitte
die flachere). Gegengeprüft mit A (`fixab`): Synthetik 87 von 95 gleich, die acht anderen
Korrekturen (dazu „x und y 31 mm“ von falsch zu auf offen); Becher 0,2 mm 100 von 106 gleich,
alles Korrekturen; Becher 0,5 mm dazu eine sichere Schließung: Wendel r 5 Ganghöhe 40 Ø 31 offen →
zu (bei 0,2 mm schon am Endstand zu, Klasse „die Ellipse ist gerade“: die Schubsumme über 5 mm
hinkt der Wendel nach). Eine Variante „Mitte als Vektor, quer zur Wand auf den Schub begrenzt“
(`fixab2`) schloss runde Löcher Ø 30,2–34 und öffnete einen anderen Diagonalfall — verworfen.
Bei leichter Schwere genügt sonst: Grenze benennen (rund 2 mm unter `CHANNEL_WIDTH`, wenn die
Neigung schräg zur schmalen Seite liegt) und neuer Punkt.

### C. leicht — `SliceResult` hat ein neues Feld, der Kernvertrag in Bauplan §9 nicht (Regel 5)

`app/core/types.py:2839–2843` ergänzt `overhang_angle`; `3d-agent-bauplan.md:654–659` (§9
Kernverträge) führt `SliceResult` mit `bridge_from`, aber ohne das neue Feld. `bridge_from` steht
dort — das Muster, dem F2 folgt, ist auch im Vertrag nachgezogen worden. Fix: Zeile
`overhang_angle: float | None = None  # Stützwinkel des Schnitts, Grad von der Senkrechten` in
§9 (Bauplan mit Ansage).

## Slicer (Auftrag Punkt 4)

`fin/tools/matrix_unit.py` am Endstand, Herstellerprofil, gepinnt; Messung `messung_n.py` mit
`.claude/.state/drache-2026-10-08/gcode_im_kanal.py`, Bereiche wie im Erstreview (Säule unter dem
Sims x 0…14, y −7…7, z 4…15; Tunnel x 20…28, y −8…8, z 4…20), großer Becher: Säule x 0…30,
y −15…15, z 4…15. Stützbahn in m, Variante „Vorschläge übernommen“ (in Klammern „Stützen an“
ohne Sperre); zum Vergleich derselbe Becher am Stand welle4 `ac244486b` ohne RM-629
(`matrix_w4`, nur ElegooSlicer):

| Becher | Slicer | Endstand: unter dem Sims / Tunnel | welle4 ohne RM-629 |
|---|---|---|---|
| schräg 20° Ø 34 | Cura SV06 | 17,29 / 0,00 (16,91 / 12,64) | — |
| schräg 20° Ø 34 | Elegoo CC2 | **23,36** / 1,08 (7,59 / 4,72) | **10,84** / 1,08 |
| Schlitz 45° 22 mm | Cura SV06 | 7,78 / 0,00 (17,05 / 12,64) | — |
| Schlitz 45° 22 mm | Elegoo CC2 | 10,52 / 1,08 (6,72 / 4,79) | 10,52 / 1,08 |
| groß, Y 22 mm (Fund A) | Elegoo CC2 | **68,86** / 1,09 (27,25 / 4,98) | 47,81 / 1,09 |

Wie Solidon sagt: Der schräge Schacht gibt dem Sims seine Stütze (Cura wie im Erstreview auf die
Stelle 17,29 m; Elegoo 23,36 statt 10,84 m am Stand ohne RM-629), der Schlitz 22 mm um 45° bleibt
zu und druckt exakt wie welle4 (10,52 / 1,08 m), in Cura mit gut der Hälfte der Stütze (7,78
statt 17,05 m) wie vorher. Das Y aus Fund A bekommt unter dem großen Sims die volle Stütze
(68,86 m, an welle4 ohne RM-629 47,81 m: 21 m mehr) — in einem Gefäß, aus dem sie durch keinen
Ast herauskommt.

**Neuer Punkt außerhalb RM-629:** In ElegooSlicer stehen mit übernommenen Vorschlägen 1,08 m
Stütze im Tunnel, am Endstand und ebenso an welle4 ohne RM-629; im Erstreview (Stand welle3,
`support.style` „auto“) 0,00 m. Der Vorschlag ist seit RM-584 „grid“ (`55236d39c` „Gitter statt
automatisch …“, Grund unverändert „Die Überhänge sind zu groß …“, `json_diff_schraeg20.txt`).
Cura bleibt bei 0,00 m. Ob die Sperre bei Gitterstützen in Elegoo/Orca den Tunnel ganz hält,
gehört zu RM-584, nicht hierher.

## Kundensicht

Kein neuer Text, nichts zu raten; die Sperre bleibt ein Vorschlag mit Grund. Ein Sims unter einem
schrägen runden Loch oder einem schräg genug weiten Schlitz bekommt seine Stütze, ein schmaler
schräger Schlitz sperrt wie vor RM-629. Wo Fund A greift (Y, Fischgrät), steht nach RM-629
Stütze in einem Gefäß, aus dem sie nicht herauskommt — das sieht der Kunde erst am Druck. Kein
Changelogpunkt nötig (wie im Erstreview: die Eigenschaft steht schon im 0.6.0-Punkt).

## Leistung (Auftrag Punkt 3)

CPU-Median `_channel_space` im Wechsel, F1-Stand gegen Endstand (`perf_05.txt` neun Läufe,
`perf_02.txt` fünf): Zickzack 0,547 → 0,953 s bei 0,5 mm, 1,234 → 2,172 s bei 0,2 mm; Deckel 20°
0,359 → 0,438 bzw. 0,656 → 0,781 s; offener Becher, senkrechter Schacht, Becher60 gleich; echte
Modelle gleich (keine Schachtfrage). Wo die Zeit liegt (`prof_zz_fin.txt`, drei Läufe Zickzack):
`simplify` (topologieerhaltend) 0,24 s je Lauf, `difference` 0,15, `buffer` 0,13, `union_all`
0,10. Eine druckgleiche Beschleunigung, die ohne den vollen Fallvergleich trägt, habe ich nicht
gefunden: Das Vereinfachen des Materials für die Ellipse ließe sich nur mit dem für `blocked`
teilen, wenn dessen Zuschnitt um 2 · (R / cos θ − R) wächst (bei 45° 12,4 mm je Seite) — das
verteuert jede Schicht und ist nicht bitgleich (Zuschnitt vor/nach Vereinfachen); schon eine
erste Beschleunigung an derselben Stelle (`stay` als bloße Differenz) war nicht druckgleich und
ist mit `5ae6de331` zurückgenommen. Kein §31-Ziel betroffen:
Das Budget „Schichtanalyse 300 ms“ gilt `slice_body`, der Sperrraum läuft im Rat- und
Schneidefaden (`_AdviceWorker`, `_SliceWorker`), nicht im Hauptfaden, und ist je Schnitt gemerkt.
Der Vorschlag des Bauagenten (vereinfachtes Material weiterreichen) bleibt neuer Punkt, mit
Fallvergleich. Fix A kostet nichts (`perf_fixa_05.txt`: alle Fälle gleich, Zickzack 0,953 /
0,953 s).

## Was vor dem Landen zu tun ist

1. Fix A wie `fix_a.diff` übernehmen (Hilfsfunktion `_split_by_hole` mit Docstring statt
   Prototyp-Kommentar), Test wie `test_vorschlag_y.py` (Äste 22/28 mm zu, 31 mm offen; am
   Endstand rot, mit A grün) nach dem Muster von
   `test_a_shaft_is_open_where_every_layer_holds_a_channel_circle`. Wer den Fix anders baut,
   fährt danach `probe_ellipse.py` und `probe_faelle_n.py` je 0,5/0,2 mm gegen `fixa`.
2. Fund B: `fix_b.diff` übernehmen (Test Diagonalschlitz 29 mm zu; die Wendel r 5 Ø 31 bei
   0,5 mm wird dabei zu, in die Grenze „die Ellipse ist gerade“ aufnehmen) oder die Grenze
   benennen.
3. Fund C: §9 um `overhang_angle` ergänzen (Bauplan mit Ansage).
4. Docstring `_shafts_pass` („So zählt ein Schlitz ab 30 mm quer zur Achse, gleich wie
   geneigt“), Begründung („nie neu offen“), Archiv („beide sind wieder zu“) an das angleichen,
   was nach 1 und 2 gilt.

## Neue Punkte (Vorschlag, keine Nummer vergeben)

- Außerhalb RM-629: ElegooSlicer setzt mit dem Vorschlag „grid“ (RM-584) 1,08 m Stütze in den
  gesperrten Tunnel des Bechers (Endstand und welle4 gleich, vorher mit „auto“ 0,00 m).
- Aus dem Fixbericht bestätigt: Kreis folgt der Achse statt der hinteren Wand; Ellipse ist
  gerade (Wendel r 8 Ø 34 bei beiden Schichthöhen, Kegel 40 → 31 bei 0,2 mm, nach Fix B auch
  Wendel r 5 Ø 31 bei 0,5 mm); Ellipse kostet am Zickzack +0,4 s (0,5 mm) bzw. +0,9 s CPU
  (0,2 mm).
- Fund A oder B, falls nicht behoben.
- Beobachtung außerhalb RM-629, nicht in der Anwendung gemessen: `model_support` am gepickelten
  Drachen 130 % kostet einfädig (`PARALLEL_FROM` aus) 403 s CPU an `a675390e6` und 435 s am
  Endstand (`echte_drache130_base.txt`, `echte_drache130.txt`); ob der Druckdialog das mit
  seinem parallelen Weg spürt, wäre zu messen.

## Geprüft (Verlauf)

- 23:20 Auftrag, Erstreview, Fixbericht gelesen; Fix-Diff `analysis.py`/`types.py`/Tests/
  Unterlagen ganz gelesen.
- Tests am Endstand (`tests_fin.txt`, gezielte Auswahl: slice_findings, slice, advise,
  estimate, slice_core und alle 19 Testdateien mit `SliceResult`/`overhang_angle`, dazu
  shared_constants, language_rules, registry_consistency, text_length, directory_docs,
  roadmap, changelog, wording; `-n 6`): **5639 bestanden, 11 übersprungen, 1 rot, Exit 1** —
  rot nur `test_memories_stay_out_of_the_repository`, weil der Scratchbaum kein Git-Klon ist
  (`git ls-files` Exit 128); dieselbe Prüfung im Worktree: `git ls-files -- .claude/memory`
  leer, also grün.
- F1 Kriechen am Endstand (`kriechen_fin.txt`, Exit 0) zeilengleich mit Variante 1b des
  Erstreviews.
- F2: einziger Leser von `SliceResult.overhang_angle` ist `_channel_space`; `SliceResult` wird
  in `app/` nur in `slice_body` gebaut (alle drei Ausgänge setzen den Winkel, `None` wird dort
  zu 45°); kein Plattencache, kein Hilfsprozess mit Pickle für Schnitte; die Merker
  (`findings.analysed`, `writer._body_analysis`, `channel_space`) schlüsseln nach Winkel bzw.
  Identität des Schichttupels. Aufrufer reichen den wirksamen Winkel (`analysis_limits(...,
  effective=True)`, Schätzung `support.threshold_angle`). Test 44°/50° bei 40/45/55° grün.
  Alte Pickles ohne das Feld werfen `AttributeError` (Slots) — nur für Sonden relevant.
- Echte Schnitte (`echte_n.txt`, Endstand gegen F1 im selben Prozess, je Winkel des Schnitts,
  40° und 55°, drei Läufe im Wechsel): Becher60, Becher gerade/Kegel, Deckel offen und mit
  senkrechtem Schlitz 2/25/30, Side kit rest, Grenuttag, Kumiko, obj_30_G, Schüssel Drucklage
  50°/55°, Dateilage 55°/60°, Drache 50 %, Eiffelturm: Scheiben und Grenzen gleich, größte
  Abweichung 0 mm², CPU gleich; an den echten Modellen keine Schacht- und keine Himmelsfrage.
  Drache 130 %: Vergleich nach 15 min abgebrochen (je Modul kostet `model_support` dort 435 s
  CPU einfädig), am Endstand allein (`echte_drache130.txt`) 22 Scheiben, keine Himmels- und
  keine Schachtfrage bei allen drei Winkeln, Sperrraum 6,3–6,4 s — der Fix ändert dort nichts.
- Becherfälle F1 gegen Endstand, 0,5 und 0,2 mm (`faelle_{fin,f1}_{0.5,0.2}.txt`, Sonde mit
  Verlängerung um den Durchmesser wie `shaft_lid`, 106 Fälle je Lauf): verschieden nur die
  Schlitze 45° 22/29, 40° 24, 30° 27 (gewollt zu), Diagonalschlitz 27 und großer Becher
  gleichläufig 28 (zu), bei 0,5 mm Fischgrät 22 (zu), dazu zwei sichere Schließungen, die die
  Unterlagen als Grenze nennen: Wendel r 8 Ganghöhe 40 Ø 34 (beide Schichthöhen) und Kegel 20°
  40 → 31 bei 0,2 mm (vorher offen, vor RM-629 zu). Alles Übrige zeilengleich: druckgleich zum
  F1-Stand; die Grenzzahlen der Begründung (Dachkante 0,9/1,0 bzw. 0,5/0,7 mm, Lippe ab 33,5
  bzw. 33,9 mm, scharfer Knick, Wendel r 5 Ø 31 und Kegel bei 0,2 mm) stimmen.
- Gegenbeispiele zur Ellipse (Auftrag Punkt 1, `probe_ellipse.py`): Schlitz quer zur schmalen
  Seite 20–29,5 zu, 30,5/31 offen; schräg zur schmalen Seite (Neigungsrichtung 30°/45°/60°
  gegen die schmale Achse, eckig und rund, auch 160 mm lang) zu bis auf Fund B; drehender
  Schlitz um seine Mitte richtig, um sein Ende (wandert auf einem Bogen steiler als 45°) zu;
  erst senkrecht Ø 34, dann 1–8 mm Schlitz um 45°: zu, wo senkrecht zu ist, keine falsche
  Öffnung durch das Anlaufen des Schubs; Y und Fischgrät: Fund A. Die Zeilen
  „Wendelschlitz“ in `ellipse_*.txt` tragen ein falsches Soll: Der Schlitz reicht dort über die
  Achse der Wendel, innen läuft ein Kreis auf einer engen, fast senkrechten Wendel hindurch
  (bei r 15/Ganghöhe 120 und 27 mm: 34,3 mm waagerecht, gebraucht 31) — offen ist richtig.
- Leistung 0,5 mm, neun Läufe im Wechsel, CPU-Median `_channel_space` (`perf_05.txt`): offen
  0,219/0,234, senkrecht 0,219/0,219, Becher60 0,297/0,312, schräg 20° 0,359/0,438,
  Schlitz 45° 22 0,312/0,281, Zickzack 0,547/0,953 s (F1/Ende). 0,2 mm, fünf Läufe
  (`perf_02.txt`): offen 0,328/0,328, senkrecht 0,281/0,312, schräg 20° 0,656/0,781, Schlitz
  0,500/0,469, Zickzack 1,234/2,172 s.
- ruff check (app, tests, tools) Exit 0, ruff format --check 961 Dateien Exit 0, mypy 374
  Dateien Exit 0 (`ruff.txt`, `format.txt`, `mypy.txt`).
- Mutanten am Endstand gegen die 52 Schachttests (`mutanten.py`, `mutanten.txt`): keine 0 rot;
  alle Wege zusammen 1 (`test_two_slabs_…`), ohne Ellipse 3 (die drei Schlitze), Startregel statt
  Winkel 2 (40°/55°), voller Schritt 2 (Kammer 0,57°/2,9°), nur Schub 1 (Knick in die
  Senkrechte) — die Angaben aus Fixbericht und Archiv stimmen.
