# Nachprüfung RM-571 (`F:/solidon-claude-a`, `claude/lauf-a`, `ea03ab0cc`) — solidon3d-review, 09.10.2026

Gelesen habe ich `git show ea03ab0cc` vollständig, also `analysis.py`, `test_slice_findings.py`,
`druckrat.md`, `slice/CLAUDE.md`, Begründung, Register und Archiv. Dazu `_channel_space`,
`_narrow`, `_model_support` und das erste Review. Der Baum ist sauber und steht auf `ea03ab0cc`.
Der Stand vor dem Fix, `b01a96f46`, ist byte-gleich mit `rm571fix/analysis_alt.py`, gegen den der
Beheber gemessen hat.

Im Baum ausgeführt, jeweils mit Exit 0:

- die 24 Kanal-, Becher- und Himmelstests aus `test_slice_findings.py`;
- 32 Sperrraumtests aus `test_export`, `test_estimate`, `test_advise` und `test_print_findings`;
- `test_roadmap` und `test_directory_docs`: 31 grün, 3 übersprungen;
- `ruff check` und `ruff format --check` auf beiden Dateien und `mypy` auf `analysis.py`, alle ohne
  Befund.

Dazu kommen Mutanten über ein Plugin, Sonden und Messungen in CPU-Zeit, einfädig, Median im Wechsel.
Ein volles Tor habe ich nicht gefahren. Außerhalb des Prüfbaums habe ich einmal `git fetch` im
Hauptklon ausgeführt. Das hat nur die Fernzweige aktualisiert, am Arbeitsbaum hat sich nichts
geändert.

## Die Punkte des ersten Reviews

**M1 behoben.** Gemessen habe ich den Becher mit Deckel (`probe_schacht.txt`). Die Tabelle nennt den
Anteil des Simses, der unter ihm im Sperrraum liegt. Mit geschlossenem Deckel sind es 64 %, im
offenen Becher 4 %:

| Öffnung im Deckel neben dem Sims | Sims gesperrt |
|---|---|
| Schlitz 2 / 10 / 20 / 25 / 28 / 29 / 29,5 / 29,9 / 30 mm | 64 % |
| Schlitz 30,1 / 30,5 / 31 / 32 mm | 4 % |
| Gitter aus Schlitzen 2, 4 oder 8 mm mit Stegen von 1 mm, zusammen 40 mm breit | 64 % |
| Loch Ø 28 mm / Ø 31 und 32 mm | 64 % / 4 % |
| weite Öffnung, Kante 0,3 mm / 0,5, 1 oder 5 mm neben dem Sims | 4 % / 64 % |

Die letzte Zeile zeigt den Saum von zwei Bahnbreiten. Er wirkt wie vor dem Fix (siehe „Außerhalb“).

Die Kammer aus dem Schlitz-Test bleibt bei Schlitzen von 0,3 bis 2 mm zu 100 % gesperrt
(`probe_slit_nach.txt`).

An der Grenze antworten `_narrow` und `_open_above` gleich (`probe_grenze.txt`, synthetisch). Bis
einschließlich 30,00 mm gilt der Raum als eng und als nicht erreichbar, ab 30,01 mm als keins von
beiden. Ein Schacht von genau `CHANNEL_WIDTH` ist damit Kanal, wie es der Docstring von
`CHANNEL_WIDTH` sagt („bis zu dieser Weite“).

Gegenproben:

- Am Stand `b01a96f46` sind die drei Schlitztests und der Nasentest rot, 4 von 23.
- Die Mutante „Fenster halb so weit“ macht 3 Tests rot, „Abbruchgrenze vierfach“ 2.
- Was keine Mutante sieht, steht unter N2.

**M2 behoben.** `_seam` puffert rund (`analysis.py:1887`). Mit Gehrung oder Fase statt rund wird der
Nasentest rot (`mut/M2_gehrung.txt`, `mut/M2_fase.txt`). Die Fase reicht an der 11°-Spitze nur
0,08 mm hinaus, daran scheitert die Gegenprobe bei 0,2 mm.

In echter Geometrie lässt sich M2 nach M1 nicht mehr zeigen. Zwischen Nasenspitze und Becherwand
bleiben 20 mm, und das ist kein Schacht. Der Test fragt `_open_above` deshalb zu Recht direkt.

**L1 behoben.** Der Abschnitt steht am Ende des Archivs, der Verweis zeigt auf
`regel-druckrat.md`, und „am alten Stand rot“ ist jetzt genau. Die neuen Deckel- und Nasentests sind
am Stand `b01` rot, „weiter offen“ bleibt grün (nachgefahren).

**L2 behoben.** Für jede der fünf Lagen steht ein Volumen da, in der richtigen Folge. Die Werte
gleichen den Messungen des Behebers (`zeit-c.txt`, `zeit-vol.txt`), und der falsche Satz zu den
„zwei Übergriffen“ ist ersetzt.

**L3 und L4 behoben.** `slice_contour` steht an allen drei Stellen (`:1150`, `:1215`, `:1252`), und
`covered` sichert `len(covered) > 5` zu.

**L5 entschieden und tragfähig, aber ohne Wächter (N5).** Ausgespart wird die ganze Säule. Meine
L-förmige Säule reicht aus dem offenen Becher bis in den Tunnel (`probe_l5.txt`). Im Tunnel ist sie
zu 0 % gesperrt; mit der Alternative aus dem Review („nur, was nicht in `_narrow` liegt“) wären es
100 %.

Als Abwägung trägt das. Am Wedge-Lock kostete eine Sperre über einer Säule die ganze Stütze, und
seit dem Fix liegt das offene Ende wirklich an einem Schacht. Den Streifen aus dem Review erreicht
kein Schacht mehr (100 % gesperrt, `probe_strip-neu.txt` des Behebers), der Satz in der Begründung
stimmt also.

**Der Nebenbefund steht als RM-626 im Register.** Inhaltlich ist der Eintrag korrekt, die Abnahme
aber unvollständig (N1).

## Kosten

Gemessen habe ich am abgelegten Schnitt `becher60.pkl` des Behebers (300 Schichten), mit
ungemerktem `_channel_space` (`zeit_vorschlag.txt`, `zeit_teile.txt`):

- Vor dem Fix kostet der Sperrraum 0,28 s, jetzt 0,63 s.
- Fast alles davon ist der Himmel: 0,03 s vorher, 0,34 s jetzt, für 276 Schichten über einem
  Fenster von 4 880 mm² statt über dem Saum.
- Die Schachtfrage kostet für alle 11 Scheiben zusammen 0,02 s. Eine Vorprüfung oder ein Schacht nur
  nahe der Naht spart deshalb nichts (gemessen).

Bei diesen Körpern fragt keine Säule nach dem Himmel (0 Aufrufe), und die CPU-Zeit bleibt gleich
(`zeit_teile*.txt`, vorher/nachher):

| Körper | vorher | nachher |
|---|---|---|
| Schüssel, Drucklage 50° | 6,08 s | 5,94 s |
| Schüssel, Drucklage 60° | 5,26 s | 5,07 s |
| Schüssel, Dateilage 55° | 9,09 s | 9,02 s |
| Drache 130 % | 6,84 s | 6,82 s |
| Eiffelturm | 12,65 s | 12,21 s |
| grenuttags (Korpus) | 0,42 s | 0,45 s |
| Side kit rest (Korpus) | 0,55 s | 0,56 s |
| kumiko (Korpus) | 0,94 s | 0,95 s |
| Gövde79 (Korpus) | 1,50 s | 1,50 s |

Im Korpuslauf des Behebers sprang die Wandzeit von grenuttags von 3,1 auf 24,5 s. Das war Fremdlast,
nicht der Fix.

Der Aufwand ist gerechtfertigt, weil das Fenster 30 mm über den Saum reichen muss. Vermeidbar ist er
trotzdem, siehe N4: Der Becher kommt damit auf den Stand vor dem Fix zurück, bei gleichen Scheiben.

## Neue Befunde

Mittlere oder schwere Befunde gibt es keine. Die leichten:

**N1 — Die Abnahme von RM-626 ließe einen Fix durch, der einer Insel die Stütze nimmt.**
`ROADMAP.md:1010–1025`, Zeile im Register `:75`.

Korrekt ist der Eintrag: `landed.get(owner, (index - 1, 0.0))` (`analysis.py:4172`) merkt die
höchste Auflage, und die Zahlen stimmen nachgestellt (`probe_rm626.txt`). Mit Insel reicht die
Kanalsäule von 22,75 bis 28,25 mm, das sind 6 Scheiben von 22,5 bis 29,5 mm. Ohne Insel reicht sie
von 7,75 bis 28,25 mm, 20 Scheiben.

Es fehlen vier Dinge:

- **(a) Die Insel.** Beide Wege der Abnahme sperren die Säule unter der Insel zu 100 %, wo es heute
  0 % sind: „bis zur untersten Auflage“ ebenso wie „eine Höhe je Auflage“. Die Insel braucht selbst
  Stütze, ist im Umschlossenen aber nicht erreichbar, also spart `channel_space` sie nicht aus
  (`:4610`). Die Abnahme fragt nur nach Stütze im Kanal und ließe so einen Fix durch, nach dem die
  Insel in die Luft druckt.
- **(b) Die Schätzung.** Ob sie dort Stütze zählt, steht als offen im Eintrag, aber nicht in der
  Abnahme. Dabei ist es ohne Slicer messbar, denn `estimate` fragt `channel_space`
  (`estimate.py:496`, `:562`).
- **(c) Der Ausgang ohne Stütze im Kanal.** Stellt kein Slicer Stütze hinein, fehlt die Anweisung,
  den Punkt mit Beleg zu schließen.
- **(d) Die Nachstellbarkeit.** „Sonde `probe_real_debug.py`“ liegt im Scratchpad einer Sitzung, und
  Lage und Höhe der Insel fehlen (x 2–6, y −2–2, z 20–23 mm).

Das zählt, weil der Registereintrag der Auftrag der nächsten Sitzung ist (`CLAUDE.md`). Fix: (a) bis
(d) in den Eintrag aufnehmen und als Bedingung schreiben, dass die Insel ihre Stütze behält, oder
entscheiden, was eine Insel im Umschlossenen bekommt (siehe „Außerhalb“, das gilt schon heute).

**N2 — Die Weite des Schachts und den Schnitt mit dem Schacht hält kein Test.**
`tests/test_slice_findings.py:1159–1177`, `analysis.py:1962–1973`.

Bei drei Mutanten bleiben alle 23 Becher-, Deckel- und Himmelstests grün: Radius 5 statt
`CHANNEL_WIDTH / 2`, Radius 12, und `reach ∩ sky` statt `reach ∩ shaft`
(`mut/M1_radius_5.txt`, `mut/M1_radius_12.txt`, `mut/M1_himmel_statt_schacht.txt`).

Die Schlitztests mit 0,5, 1 und 2 mm entscheidet die Abbruchgrenze in `_sky_above` (`:1926`), nicht
der Kreis. Beim Schlitz von 2 mm hat der Himmel über dem Sims 607 mm² und damit weniger als
π · 15² = 707 mm² (`probe_schacht.txt`). Die Gegenprobe öffnet 34 mm.

Dass die dritte Mutante übersteht, hat einen Grund: Jeder Kreis, der ins Fenster passt, reicht ohnehin
bis an die Naht. Der Schnitt mit dem Schacht entscheidet nur, wenn draußen hinter einer dünnen Wand
weiter Himmel liegt und drinnen ein schmaler.

Das zählt nach `tests.md`, „An der Aussage vorbei“: Der Docstring sagt „Schacht so weit wie ein
Kanal“, geprüft wird „Schlitz kleiner als die Abbruchfläche“.

Fix, beide Fälle nachgemessen:

- **(a)** Ein Deckel mit Schlitz 25 mm, der Sims bleibt gesperrt. Der Baum liefert 64 %, mit Radius 5
  oder 12 sind es 4 % (`probe_radius.txt`). Dazu gern 32 mm als offen.
- **(b)** Die dünnwandige Kammer aus `…[thin wall]` mit einem Schlitz von 1 mm in der Decke über der
  Säule. Der Baum sperrt sie zu 100 %, mit „Himmel statt Schacht“ zu 0 %
  (`probe_wand_schlitz.txt`).

**N3 — Ein schräger Schacht zählt nur mit seiner senkrechten Durchsicht, und das steht nirgends.**
Docstring `analysis.py:1938–1958`, `regel-druckrat.md:346–368`, `druckrat.md:64`.

Gemessen am Becher mit einem 20 mm dicken Deckel und einem Loch Ø 34 mm, dessen Unterkante direkt
neben dem Sims endet (`probe_schraeg.txt`):

| Neigung des Lochs | senkrecht durchschaubar | jetzt | vor dem Fix |
|---|---|---|---|
| 0° | 34,0 mm | 4 % | 4 % |
| 10° | 31,0 mm | 4 % | 4 % |
| 20° | 28,9 mm | 64 % | 4 % |
| 30° | 27,7 mm | 64 % | 4 % |
| 30° vom Sims weg | — | 64 % | 64 % |

Quer zur Achse bleibt das Loch 34 mm weit, die Stütze käme also heraus. Der Docstring begründet die
Weite damit, dass niemand eine Stütze durch einen engeren Spalt holt. Schräg ist der Spalt aber nicht
enger. Der Fix macht hier aus „frei“ ein „gesperrt“, und der Sims druckt ohne Stütze.

Fix: die Grenze in Docstring, Regel und Begründung nennen, mit der senkrechten Durchsicht
2R / cos θ − H · tan θ und der Folge für den Kunden. Den Schacht entlang seiner Achse zu messen wäre
die größere Variante; nötig ist sie für diese seltene Form nicht.

**N4 — Die Mehrkosten am Becher sind vermeidbar.** `analysis.py:1916–1928`.

Vorschlag: In `_sky_above` die Schichten überspringen, die den Himmel nicht mehr schneiden. Hat die
letzte Differenz den Himmel nicht verändert, wird er einmal um ein Zehntel von `WIDTH_SIMPLIFY`
eingerückt und vorbereitet. Schneidet das Material einer Schicht diesen Kern nicht, entfällt sie.
Der Fehler ist höchstens 0,001 mm, zehnmal weniger als die Vereinfachung, die schon gilt.

```python
    inner = None
    stable = False
    for start in sorted(set(starts), reverse=True):
        while index >= start and not sky.is_empty:
            shade = shapely.clip_by_rect(shade_at(index), *sky.bounds)
            index -= 1
            if stable:
                if inner is None:
                    inner = sky.buffer(-WIDTH_SIMPLIFY / 10.0)
                    shapely.prepare(inner)
                if not shapely.intersects(inner, shade):
                    continue
                inner = None
            before = sky.area
            sky = sky.difference(shade).simplify(WIDTH_SIMPLIFY)
            stable = abs(sky.area - before) <= WIDTH_SIMPLIFY / 10.0 * sky.length
            if sky.area < smallest:
                sky = ShapelyPolygon()
        found[start] = sky
    return found
```

Gemessen mit `_channel_space` ungemerkt, CPU, Median aus 9 Läufen im Wechsel (`zeit_vorschlag.txt`):

| | vor dem Fix | jetzt | mit Vorschlag | mit Vorschlag und `preserve_topology=False` |
|---|---|---|---|---|
| becher60 | 0,28 s | 0,63 s | 0,31 s | 0,30 s |
| Becher als Kegelstumpf | 0,27 s | 0,42 s | 0,44 s | 0,34 s |

Beim Kegelstumpf schneidet die Wand jede Schicht neu. Dort spart das Überspringen nichts, kostet aber
auch nichts.

Die Scheiben sind gleich (größte Abweichung 0,00 mm²) an becher60, am geraden und am kegeligen Becher
und an acht Deckelfällen (`zeit_adaptiv.txt`, `zeit_deckel.txt`). Die 23 Tests sind mit beiden
Fassungen grün (`mut/Opt_adaptiv*.txt`).

Warum es zählt: Robert verlangt, dass jede gefundene Beschleunigung bei gleichem Ergebnis umgesetzt
wird. Fix: den Vorschlag übernehmen und den Faktor 10 als benannte Konstante mit Herkunft schreiben
(Regel 8). Den Kommentar mit 3 916 Ecken und Zeiten dabei nachziehen; meine Messung ohne
Vereinfachung ergab 3 812 Ecken und 0,92 s für den Himmel allein.

**N5 — Die Entscheidung L5 hält kein Test.** `analysis.py:1954–1958`, `:4611–4612`.

Die Mutante „nur, was nicht in `_narrow` liegt“ (`.difference(narrow)` in `:4612`) lässt alle 23
Tests grün (`mut/L5_nur_ausserhalb_der_Enge.txt`). Dabei ist die L-Säule im Tunnel dann zu 100 %
statt 0 % gesperrt. Eine Entscheidung, die drei Texte tragen, aber kein Test, kippt beim nächsten
Umbau still (`tests.md`).

Außerdem stehen im Docstring zwei Sätze, die niemand gemessen hat:

- „Eine zur Hälfte gesperrte Säule stützte der Slicer nur zur Hälfte.“ Am Wedge-Lock stützte Cura
  gar nicht: 0,0 statt 2,0 m.
- „Wer ihr offenes Ende greift, zieht auch den Rest heraus.“

Fix: ein Test mit der L-Säule aus `probe_l5.py` (Umriss von (−4, −16) bis (26, 0), Höhe 4 bis
12 mm), der zusichert, dass ihr Teil im Tunnel frei bleibt. Die beiden Sätze belegen oder als
Annahme kennzeichnen.

**N6 — Name und Docstring eines Tests nennen noch den alten Vertrag.**
`tests/test_slice_findings.py:1228–1234`.

`test_open_sky_must_be_beside_the_column_and_a_line_wide` sagt „nur eine Bahn breit … durch einen
Schlitz, schmaler als eine Bahn, holt niemand eine Stütze heraus“. Seit dem Fix ist auch ein Schlitz
bis 30 mm zu, und der Fall mit 0,3 mm besteht nur über die Abbruchgrenze. Prosa ist keine Prüfung,
und ein Text, der mit der Grenze altert, führt den Nächsten in die Irre.

Fix: Name und Docstring auf „Schacht so weit wie ein Kanal“ umstellen; der Fall aus N2 (b) gehört
hierher.

## Außerhalb des Prüflings (vorbestehend)

**Eine Insel im Umschlossenen verliert ihre Säule schon heute.** Gemessen an der Kammer aus dem
Schlitz-Test mit 1 mm Schlitz und einer Insel von 2 × 4 × 3 mm, die neben der Kanaldecke liegt statt
darunter (x 7,5–9,5, z 20–23). Die Kanalsäule setzt auf dem Boden auf, und die Säule der Insel liegt
zu 100 % im Sperrraum (`probe_insel.txt`, `island_on_model` ist wahr).

Der Grund: `channel_space` spart im Umschlossenen nur aus, was erreichbar ist (`:4601–4612`, Regel
aus RM-566), auch bei einer Insel. Eine Insel druckt aber ohne Stütze in die Luft, und `druckrat.md`
sagt „Eine Insel ist nie eine Kanaldecke … gleich wie klein“. Ob ein Slicer die Insel dann wirklich
ohne Stütze lässt, ist nicht gemessen.

RM-566 ist noch in keinem Tag. Vor 0.6.0 gehört das ins Register, zusammen mit N1 (a). Alternativ
behält eine Insel ihre Säule immer.

**Zur Kenntnis, kein Fund.** Eine weite Öffnung macht den Sims nur erreichbar, wenn ihre Kante
höchstens etwa eine Bahnbreite neben ihm liegt: bei 0,3 mm frei, bei 0,5 mm gesperrt. Das ist der
Saum, so gewollt („offen über der Säule“) und vom Fix unverändert. Ein Regal unter einem Deckel neben
einer Einfüllöffnung bleibt damit ohne Stütze.

## Sonden und Läufe

Ordner: `%TEMP%\claude\F--3D-Druck\6d004019-0ef1-44d0-8062-699c55490a5e\scratchpad\nach571\`

- Mutanten: `run_mutants.py` mit `mutant_plugin.py`, je Mutante `mut/<name>.txt`, Übersicht in
  `mut/uebersicht_alle.txt`.
- Sonden: `probe_schacht`, `probe_grenze`, `probe_radius`, `probe_wand_schlitz`, `probe_schraeg`,
  `probe_l5`, `probe_rm626`, `probe_insel`, je als `.py` mit `.txt`; dazu `probe_slit_nach.txt` und
  `probe_tip_nach.txt` aus den Sonden des ersten Reviews.
- Kosten: `zeit_teile.py` mit den Ausgaben `zeit_teile.txt`, `zeit_teile_gross.txt`, `zeit_dp.txt`,
  `zeit_adaptiv.txt`, `zeit_vorschlag.txt` und `zeit_deckel.txt`. Dazu `prof_sky.py` mit
  `prof_sky*.txt` und die Fassungen `make_variant.py` → `analysis_adaptiv*.py`.
- Schnitte: in `pkl/`; `becher60.pkl` und die Schüssel- und Drachenschnitte stammen aus
  `..\rm571fix\`.
- Testläufe: `t_basis.txt`, `t_geschwister.txt`, `t_docs.txt`, `mypy.txt`.

**Urteil: nicht, noch nicht.** M1 und M2 sind behoben und mit Gegenprobe belegt, mittlere oder
schwere Befunde gibt es nicht. Vor dem Merge gehören N1 bis N6 noch in den Zweig: Registertext, zwei
Testfälle, ein Testname mit Docstring, die genannte Grenze des schrägen Schachts, die Beschleunigung
und ein Wächter für L5. Danach kann es ohne weitere Nachprüfung rein.
