# Zweite Nachprüfung RM-585 — Bögen und gefasste Kragarme drucken ohne Stütze

Prüfling: Worktree `F:\sl-boegen`, Zweig `einstellungen/boegen-rm585`, Spitze `c8e42e34a`
(welle4 `a72079433` enthalten, Merge-Basis). Fixrunde: `acec53d55` (N1–N3, N5–N7),
`cbb854fc8`/`ba5efe054` (N4). Vorgänger: `review_rm585_nach.md` (N1–N7), Fixbericht
`berichte-2026-10-10\rm585b.md`. Reviewer: solidon3d-review (rv585n2).

Stand: **abgeschlossen** (03:45). Urteil:
**nicht landen** in dieser Form — Z1 schwer, Z2 und Z3 leicht (Begründung unter „Urteil“).
**Nachtrag 11.10. 07:15:** Gezielte Nachprüfung (Z1–Z3) am Ende dieses Berichts, Spitze
`249dbfe57` — Urteil dort: **kann landen**.
„S1“ meint in diesem Bericht immer den Befund des Erstreviews (fast flache Decken).

## Vorgehen

- Prüfling vollständig gelesen: `git diff a72079433 c8e42e34a` (15 Dateien, +1621/−93),
  dazu `_Ceilings` ganz, `_model_support`, `_channel_space`, `_bridges_and_overhangs`,
  `_from_spans`.
- Exporte mit demselben übersetzten Kern (`_chain.pyx` unverändert): `w4` = `a72079433`,
  `neu` = `c8e42e34a`. **C: ist voll** (02:32: 861 MB frei, 475 GB belegt; ein erster
  Export brach mit „No space left on device“ ab und ist gelöscht). Exporte und große
  Ausgaben liegen deshalb unter `F:\rv585n2-scratch\` (nach dem Urteil löschbar), Skripte und
  Protokolle im Scratch `scratchpad\rv585n2\` (Sitzung 78c2d72e). Läufe gepinnt
  (`start /affinity FFFFF0FF`, `GESAMT_KERNE`), `TEMP`/`TMP` auf F:.

## Befunde

### Z1 (schwer) — Gekrümmte Streifen gelten als „zwischen zwei Auflagen“: eine flache Halbkuppel verliert ihre Stütze, im G-Code hängen Bahnen bis 2,5 mm neben der Schicht darunter

`app/core/slice/analysis.py:4913–4974` (`_Ceilings._held_twice`, besonders `:4960–4974`: der Teil
jenseits des Kragarms gilt als gehalten, wenn die Hülle seiner gehaltenen Randstücke ihn
deckt), mit `_spans` (`:5136–5166`) und `_runs_free` (`:4890–4911`, Lauflänge als lange
Seite des kleinsten Rechtecks).

Die zweite Tür aus N2 ist nur für gerade Streifen zu: Ein einseitig hängender gerader Streifen
hat als gehaltenen Rand eine Gerade, deren Hülle nichts deckt. Ein **gekrümmter** einseitiger
Streifen — ein Halbring unter einer Halbkuppel, ein Bogenstück einer gerundeten Nische — hat
als gehaltenen Rand einen Bogen, und dessen Hülle ist das Kreissegment, in dem der Streifen
liegt: „zwischen zwei Auflagen“, damit getragen, sobald kein Punkt weiter als 7,5 mm vom
Material liegt — gleich, wie weit er je Schicht kragt und wie lang seine freie Kante läuft.
`_runs_free` misst dazu bei einem Bogen die Sehne (2r), nicht den Lauf (πr).

Beleg (`kuppel2.py`, Nische mit Kugelkappe, vorn offen, Sehne und Stich wie ein Flachbogen;
`out/ku2.log`, alle Läufe Exit 0; Bahn 0,84):

| Körper | 0,2/45 welle4 → Zweig | 0,2/60 | 0,28/60 | gefasste Bogenstreifen (Zweig) |
|---|---|---|---|---|
| Halbkuppel R 10, Stich 1,7 | ja → **nein** | ja → **nein** | ja → ja | 4 / 3 / 3 |
| Halbkuppel R 12, Stich 2 | ja → ja | ja → **nein** | ja → ja | 7 / 6 / 6 |
| Halbkuppel R 8, Stich 1,3 | nein → nein | nein → nein | ja → **nein** | 1 / 1 / 2 |
| Halbkuppel R 15, Stich 2,5 | ja → ja | ja → ja | ja → ja | 9 / 9 / 8 |
| *gerader* Flachbogen 24/2 in 12 mm Wand | ja → ja | ja → ja | ja → ja | 0 |

Am Kundenweg (Matrix, CC2, 60°, `mxh.sh`, R 12/2): welle4 „Die Überhänge sind zu groß, um
sich selbst zu tragen.“, `support.style=auto`, `placement=build_plate`, 12,94 m Stütze; Zweig
`needed: false`, stattdessen dicke Brücken, Brückenfluss 0,9 und Zusatzwände, 0 m Stütze
(Überhang ohne Bögen 129,2 → 8,8 mm²). Im G-Code ohne Stütze (`luft.py` des Vorgängers,
`out/luft_halbkuppel.log`) liegen gefasste Bahnen bis **2,51 mm** neben der Schicht darunter
(6 Bahnbreiten; 1,78 mm über 11,8 mm, 1,38 mm über 11,5 mm) und Kragarme mit freiem Ende bis
**1,22 mm** (2,9 Bahnbreiten). Die Regel des Koordinators lässt einen Kragarm höchstens eine
Bahn neben der Schicht darunter zu und eine kurze Brücke bis Zugabe plus zwei Bahnen
(0,346 + 0,8 = 1,15 mm Kante, Bahnmitte 0,94 mm) — beides deutlich überschritten. Kein
Körper des Korpus zeigt es (CC2 und 45° wie im Fixbericht), die Form ist aber gewöhnlich:
Nische, Apsis, gerundeter Alkoven, Unterseite eines runden Vordachs.

**Fix:** Den Teil jenseits des Kragarms nur dann als „zwischen zwei Auflagen“ zählen, wenn
seine freie Kante nicht als ein Lauf länger als `SPAN_INTERESTING` frei läuft — dieselbe
Frage wie `_runs_free`, aber entlang der Kante gemessen (Länge der losen Randlinie, nicht das
Rechteck); `_runs_free` selbst ebenso. Die Eiffelturm-Streifen bleiben gefasst (Halt ringsum
an den Gitterstäben, lose Stücke kurz); die Prüfung gilt nur dem freien Teil — eine
Verschärfung am ganzen Streifen (`neu_fix3`) gab dem Turm bei 45° die Stütze zurück. Ein
Ring unter einer geschlossenen Kuppel bleibt eine bewusste Entscheidung (Docstring); wer sie
behält, nennt sie in Regel und Test. Tests: Halbkuppel R 10/1,7 bei 0,2/45 und 0,2/60,
R 12/2 bei 0,2/60 brauchen Stützen; Eiffelturm (45°/60°), R 20/R 30/R 35, Spitzbögen,
Arkade, Kumiko wie heute; Korpus bei CC2 und 45° noch einmal.

**Experiment** (nur in der Kopie `F:\rv585n2-scratch\fix1`, `patch_fix1.py`, sieben Zeilen:
in `_held_twice` je freiem Teil zusätzlich „keine lose Randlinie länger als
`SPAN_INTERESTING`“ über `_merged_lines`, in `_runs_free` dieselbe Linie vor dem Rechteck;
`fx.sh`, alle Läufe Exit 0): Halbkuppel R 10/1,7 und R 12/2 brauchen in allen drei
Einstellungen Stützen (wie welle4), R 15 ebenso; R 8/1,3 bei 0,28/60 bleibt frei (welle4
mit, Überhang 54,6 mm², Feld 15,9 mm² — knapp). Unverändert gegenüber dem Zweig: Rundbögen
R 20/R 30/R 35, Spitzbögen 40/24 und 40/40, Arkade ohne Stütze bei 0,2/45, 0,2/60 und
0,08/45; Flachbogen 40/3, Satteldecke 8,5°, Pultdecke 12° und Haut 15° in 20 mm Tiefe (0,2)
mit; Pultdecke 12° in 8 mm frei; **Eiffelturm generisch 45° ohne Stütze, Feld 0,0 mm²,
2 536 Bogenstreifen, CC2 ohne Stütze, 412 Bogenstreifen — wie im Zweig;** Kumiko-Schale bei
45° weiter mit Stütze (Feld 3 587 mm², `fxk.sh`). Der Weg ist also
gangbar, ohne einen Gegenfall zurückzugeben; Korpus und Tests stehen aus, ebenso, was `fix1`
an Ringen unter einer geschlossenen Kuppel ändert (ihre lose Innenkante ist länger als 15 mm,
sobald der Ring weiter als knapp 5 mm ist) — nicht gemessen.

### Z2 (leicht) — Unterlagen versprechen tiefen Decken und Bögen ihre Stütze ohne Schichthöhe

`.claude/rules/druckrat.md:140–142` („Pultdecke unter 12° und Haut unter 15° in 20 mm Tiefe
behalten ihre Stütze, ein Rundbogen in einer Wand über 15 mm Tiefe auch“),
`ROADMAP-ARCHIV.md:46805` („Rundbögen in Wänden über 15 mm Tiefe bekommen ihre Stütze zurück“),
`konzepte/begruendungen/regel-druckrat.md:614` (der Rundbogen im selben Satz ohne die 0,2 mm),
Changelog aller sechs Sprachen („Flache Decken und Bögen in sehr tiefen Mauern behalten
ihre.“); dazu `analysis.py:4084` und `regel-druckrat.md:625–626` („bei 0,2 mm und darüber
entscheidet die Bahnbreite“).

Beleg (`out/g2_tab.txt`): Bei 0,08/45 und 0,12/55 sind Pultdecke 12°, 15°, 20° und Rundbogen
R 20 in 20 mm Wand, Haut 12°/15°/20° und Hautdach 12°/15° im Zweig **ohne** Stütze (welle4
mit); ohne Profilbahn (1,0 mm) bei 0,2/60 auch Pultdecke 15°, Haut 15° und R 20 in 20 mm.
Und bei 0,2 mm entscheidet für die kurze Brücke nicht die Bahn, sondern `CANTILEVER_LAYERS`:
`min(2·0,42; 4·0,2) = 0,8` (`analysis.py:4886`) — die Pultdecke 12° in 8 mm Wand ist frei,
weil vier Schichthöhen es erlauben. Das Verhalten folgt der Regel des Koordinators (bei
0,12 mm liegt die Bahnmitte der 12°-Decke 0,355 mm neben der Schicht darunter, unter einer
Bahn); falsch ist nur der Satz ohne Schichthöhe. **Fix:** in Regel, Begründung, Archiv und
Docstring „ab 0,2 mm“ bzw. „bei feinen Schichten trägt sich eine Decke ab gut 11° Schicht für
Schicht als Kragarm“; die Aussage über 0,2 mm richtigstellen; im Changelog den Nebensatz über
tiefe Mauern streichen oder auf das zurücknehmen, was überall gilt (etwa „Fast flache Decken
behalten ihre.“). Der Probedruck aus `rm585b.md` („Grenze feiner Schichten“) sollte die
Pultdecke 12° in 20 mm Wand bei 0,12 mm mitnehmen.

### Z3 (leicht, Zwilling) — Der Teil jenseits des Kragarms wird dreimal hergeleitet

`analysis.py:4387–4401` (`_hangs_on`), `:4890–4901` (`_runs_free`), `:4955–4962`
(`_held_twice`): je Ausschnitt des Materials darunter, Puffer um die Reichweite, Differenz,
Vergleich mit `LEDGE_SPILL`. `_carries` ruft `_hangs_on` und `_runs_free` mit derselben
Reichweite (zwei gleiche Puffer), `_arch` danach `_held_twice` mit derselben noch einmal.
Heute stimmen alle drei überein; ändert jemand Fenster oder Rauschgrenze an einer Stelle,
sagt `_carries` „ragt hinaus“ und `_held_twice` (`free.area <= LEDGE_SPILL …: return True`)
„liegt ganz im Kragarm“ für denselben Streifen (`.claude/rules/zwillinge.md`, ungewollt).
**Fix:** eine Hilfe `_beyond(shape, below, reach)`, die den freien Teil (oder nichts unter
`LEDGE_SPILL`) liefert, für alle drei; spart je Streifen zwei Puffer.

## Punkt 1 — N1 bis N7 am Endstand

Prüfkörper (`grenze2.py` = `rv585n/grenze.py` mit wählbarer Bahnbreite, `g2.sh`,
`out/g2_tab.txt`; 23 Körper × 0,08/45, 0,12/55, 0,2/45, 0,2/60, 0,28/60; welle4 und Zweig mit
der Bahn des Centauri, 0,84 mm, Zweig zusätzlich ohne Profil, 1,0 mm; alle 15 Läufe Exit 0),
echte Modelle mit `kanal_diff.py` (Dateilage, Druckdialog-Schnitt; `ek.sh`, Exit 0):

| Fall | Ergebnis Zweig | Urteil |
|---|---|---|
| N1 Kumiko-Schale, generisch 45° | Stützen nötig, Feld 3 587 mm² | behoben |
| N2 Pultdecke 12°/15°, Haut 15° in 20 mm Tiefe, 0,2/45 und 0,2/60 (0,84) | alle mit Stütze; dazu Pult 12° und Haut 12° bei 0,28/60 | behoben, wie entschieden |
| Eiffelturm CC2 (60°) / generisch (45°) | ohne Stütze (Feld 38,3 / 0,0 mm², 412 / 2 536 Bogenstreifen) | gehalten |
| R 20, R 30, R 35, Spitzbögen 40/24 und 40/40, Arkade (8 mm) | in allen fünf Einstellungen ohne Stütze | gehalten |
| S1-Körper (Pult 4,3°, Decke 2°, Flachbogen 40/3 und 60/8, Korbbogen 60/12, Sattel 8,5°) | in allen fünf mit Stütze | gehalten |
| N3 Drache 45° (`drache45.py`, `out/d45_*.log`) | welle4 1 836 Kanalstücke / 70 Säulen / 8 227 mm³, Zweig 2 085 / 61 / 7 594 (CPU 482 → 489 s) | behoben, siehe unten |
| N4 Neigungsreihe | `test_a_steeper_ceiling_never_needs_more_support` grün; Wächter `5a33fc8ad` siehe unten | behoben |
| N5–N7 | Docstrings (`ModelSupport.tallest_column`, `span_beside`), `_anchored` für Schließfrage und Scheitel (`analysis.py:5046`, gerufen aus `_closes` und `_crown_spans_short`), `hanging` vor `arches` (`:4242–4243`) | behoben |

**N3 am Drachen (45°):** Die neun Säulen, die welle4 sperrt und der Zweig nicht, sind die
kragenden Scheitel **beider** Flügeltaschen: links fünf Streifen z 62,1–62,9 (61,9 mm²,
x −44,8…−8,4), rechts vier z 63,1–64,9 (47,7 mm², x 21,9…46,1); alle neun stehen jetzt als
offene Säulen da (`out/d45_vergleich.txt`). Beide Taschen behalten ihre Sperre (Scheiben
60,4–66,4 weiter 80–365 mm²); die Asymmetrie aus N3 ist weg. Was die Sperre verliert, liegt
dort, wo ihr Umkreis nur von diesen Scheitelsäulen kam (Scheiben 52,4–55,4: 64 → 22 mm²).
Dazu 52 kleine Stücke der rechten Tasche (0,0–2 mm², meist unter 1 mm²) und 19 Bettsäulen am
Flügelende als `crowned` ausgespart; Löcher, in die keine Bahn passt, verwirft
`_with_usable_holes`. Ob der Raum unter den Scheiteln umschlossen ist, habe ich am Netz
nachgesehen (`umschlossen.py`, Querschnitt alle 2 mm von Fuß bis Scheitel, `out/umschlossen_d45.txt`):
Für alle elf betroffenen Säulen liegt die Hülle zu 0 % in einem Loch des Querschnitts, zu
73–100 % im Freien. Eine Stütze dort kommt heraus; eine Tasche verliert ihre Sperre nicht zu
Unrecht. **Kein Befund.** Am CC2 siehe Punkt 3.

**N4-Wächter** (`5a33fc8ad`, vom Bauagenten während dieser Prüfung ergänzt): Gegenprobe am
Export mit den Tests dieses Stands (`mut.sh`, `out/mut.log`): unverändert 6 grün, Exit 0; mit
der doppelten Zugabe für jede Schicht (Fassung `cbb854fc8`) wird
`test_only_the_last_layer_of_a_ceiling_holds_across_two_allowances` rot (`closes` sagt ja),
Exit 1. Der Wächter hält, was er soll; der neue Punkt „Wächter für N4“ aus `rm585b.md` ist
damit erledigt.

**Bahnbreite und `CANTILEVER_LAYERS` (Entscheidung des Koordinators):** `CANTILEVER_LAYERS`
steht in `_cantilever` (`analysis.py:4858–4862`) und in der Grenze der kurzen Brücke
(`:4886`) jeweils in einem `min()`, macht die Bahnregel also nur enger; eine neue
Entwarnung gegenüber einer reinen Bahnregel kann es nicht öffnen. Gegenüber welle4 entwarnt
der Zweig bei feinen Schichten aber jede tiefe Decke ab gut 11°: bei 0,08/45 und 0,12/55 sind
Pultdecke 12°/15°/20° und Rundbogen R 20 in 20 mm Wand, Haut 12°/15°/20° und Hautdach
12°/15° ohne Stütze (welle4 mit; `out/g2_tab.txt`). Das folgt aus der Regel selbst: Bei
0,12 mm ragt die 12°-Decke je Schicht 0,565 mm (Kragarm bis 0,591), die Bahnmitte liegt
0,355 mm neben der Schicht darunter — weniger als eine Bahn (0,42), also Kragarm, ohne dass
die Lauflänge gefragt wird. Schlüssig im Sinn der Entscheidung, aber ungedruckt (siehe Z2).

## Punkt 2 — die zwei Korpusmodelle mit geschrumpfter Kanalsperre, im ElegooSlicer

`tools/matrix_unit.py` aus dem jeweiligen Export (Druckdialog-Weg, ElegooSlicer, Centauri
Carbon 2, PLA, Dateilage `GESAMT_AUSRICHTEN=0` wie der Korpuslauf; `mxk.sh`), Sperrkörper aus
der Übergabe-3MF (`extract.py`), Stützbahn im Sperrkörper des welle4-Stands
(`gcode_im_kanal.py`, `out/gk_g_w4region.log`, `out/gk_o.log`); Kanalfrage Stück für Stück
(`kanal_diff.py`, `vergleich.py`, `out/vg_*.txt`). Alle Läufe Exit 0.

**`grenuttags_hallare_modell_41x47_curved`** (Halter, Profil 47 × 63 mm, 20 mm tief):

| | welle4 | Zweig |
|---|---|---|
| Kanalfrage (Druckdialog-Schnitt, 60°): Kanalstücke / Sperrsäulen | 29 / 25 | 6 / 2 |
| Sperrkörper der Übergabe | 2 179 mm³, z 3,8–58,8 | 131 mm³, z 44–57,6 |
| Rat am Teil (Unterschied) | `thick_bridges`, `bridge_flow 0,9` | — |
| Stütze gesamt / im welle4-Sperrkörper | 86,9 m / 0,05 m | 89,7 m / 3,58 m |

Die 23 verlorenen Kanalstücke sind der Scheitel eines Flachbogens (z 56,35–58,75, Sehne gut
28 mm zwischen den Flanken bei y ±14, oberste Spanne 112 mm²); im Zweig ist er
`overhanging` und ausgespart, die 3,58 m Stütze stehen direkt unter ihm (z 56–58, x über die
ganze Tiefe). Der Raum darunter ist nicht abgeschlossen (`schnitte.py`): Das Profil ist ein
offenes C ohne Loch (Schnitt x = ±9,9 eine Fläche ohne Loch), bei z 30 steht nur die Wand
y 20,5–23,5, vorn und hinten (x ±10) ist der Raum offen. Die Stütze kommt also heraus, und
sie trägt einen Scheitel, der weiter kragt, als er sich trägt — welle4 ließ ihn mit dicken
Brücken frei drucken. **Kein Befund**; die Änderung ist die beabsichtigte.

**`obj_15_Assembly`** (Piratenschiff): Am Kundenweg ist der **Sperrkörper in beiden Ständen
derselbe** (8 324 mm³, gleiche Ecken- und Dreieckszahl, gleiche Hülle; `3D/3dmodel.model`
inhaltsgleich). Die 1 953 → 522 mm³ des Korpuslaufs stammen aus dessen eigenem Weg
(`_body_analysis(detail="full")` + `channel_space`), nicht aus der Übergabe. Stütze im
Sperrkörper: welle4 4,08 m, Zweig **0,87 m** (Vorschläge); „Stützen automatisch“ 16,50 /
16,46 m. Was sich ändert, ist der Rat (`out/ml_o_*.txt`, `einstellungen.py`): welle4 Hybrid
mit dichter Trennschicht und feinen Schichten (0,1 mm, „rund 56 % länger“), Zweig Baum ohne
beides — Überhang ohne Kanäle, Ränder und Bögen 1 193 → 239 mm², größtes Feld 136 → 29 mm²
(529 Bogenstreifen). Stütze 417,7 → 315,0 m, Druckzeit 537 → 338 min. Die feinen Schichten
fallen mit dem Baum weg (`_fine_layers` nicht unter organischen Bäumen) — Folge, kein
eigener Fehler. **Keine Stütze in einem Raum, aus dem sie nicht herauskommt.**

## Punkt 3 — übrige Korpusänderungen und Drache

Gleicher Weg (`mxb.sh`, `dr.sh`, Dateilage; Drache wie im Fixbericht als `obj3.stl` in
Drucklage), alle Läufe Exit 0.

- **Drache am CC2:** Übergabe-3MF in allen drei Varianten (Standard, Vorschläge, Stützen
  automatisch) gegen welle4 `a72079433` **inhaltsgleich**, 6 von 6 Einträgen
  (`zipvergleich.py`); G-Code gleich lang (69 074 862 Byte). Einzig die Kennzahl
  „Überhang“ des Stützbedarfs sinkt 346,9 → 332,8 mm² (Bogenstreifen zählen nicht).
- **Minigolf `obj_30_Gövde79`:** welle4 keine Stütze (dicke Brücken, Brückenfluss, Zusatzwände,
  feine Schichten 0,1 mm), Zweig Baum und Kanalsperre, 14,89 m Stütze, davon 0,64 m im eigenen
  Sperrkörper (z 50–54, unter dem Scheitel). Ursache (`scheitel.py`, `out/scheitel_m.txt`):
  ein Flachbogen von gut 25 mm Spannweite und 3,8 mm Stich in 16,5 mm tiefer Wand; die
  Streifen ab z 54,15 laufen 16,5 mm frei, der Scheitel (zwei Arme je 6 × 16,5 mm) trägt
  sich nicht und wird ausgespart. Das ist der S1-Fall des Erstreviews (Flachbogen behält seine
  Stütze); der Raum darunter ist ein offenes Fenster (`umschlossen.py`: 0 % Loch, 100 % frei
  von z 5,8 bis 53,9) — die Stütze kommt heraus. **Plausibel.** Nebenbefund ohne Folge: Die
  oberste Schicht dieser Decke ist ein Splitter von 0,0 mm² (Schicht 277), die eigentliche
  letzte Spanne (37,9 mm², z 55,15) zählt deshalb als gefasster Streifen; mit ihr in der
  Scheitelzone spannt der Scheitel ebenfalls nicht kurz (Diagonale 21,8 mm, keine Richtung
  mit Halt an beiden Enden) — die Antwort bleibt dieselbe. Die feinen Schichten fallen mit dem
  Baum weg (Druckzeit 564 → 369 min).
- **Waschschüssel (Dateilage):** Rat gleich (Objekteinstellungen identisch), Sperrkörper der
  Übergabe 30 356 → 28 331 mm³. Ausgespart werden vier Scheitelstücke (z 52,35–52,95,
  25–88 mm², Säulen bis z 11,4). Stütze im welle4-Sperrkörper 4,87 → **20,61 m** (z 11–18 und
  46–53). Der Raum dort ist aber das Innere des liegenden Beckens: im Querschnitt
  6 900–17 800 mm² frei, über 107–296 mm zur Seite y = 57,5 offen, die Stütze höchstens
  27,5 mm von der Öffnung (`kanalraum.py`, `out/kanalraum_b.txt`), kein Loch
  (`out/umschlossen_b.txt`). Sie kommt heraus. **Plausibel.** In **Drucklage** (wie der Kunde,
  `GESAMT_AUSRICHTEN=1`, `mxbd.sh`): Sperrkörper 87 464 → 87 060 mm³, Rat Baum-Hybrid statt
  normaler Stütze, Stütze gesamt 792,7 → 646,9 m, im welle4-Sperrkörper **0,0 / 0,0 m**
  (`out/gk_bd.log`) — nichts im Wasserkanal.

## Punkt 4 — Tests, Unterlagen, Budgets

- **Tests am Endstand** (Worktree, HEAD `5a33fc8ad` = `c8e42e34a` + N4-Wächter, `app` aus dem
  Worktree, ohne Bytecode und Cache; `tests.sh`): Pflichtliste der Baumleser samt
  Unterlagen (toolchain, finding_ways, finding_actions, hard_rules, errors, core_isolation,
  interface_limits, shared_constants, language_rules, registry_consistency, text_length,
  translations, wording, directory_docs, roadmap, changelog) **3 257 grün, 5 übersprungen,
  Exit 0**; gezielt 13 Dateien (slice_findings, advise, print_findings, slice, slice_core,
  estimate, export, geometry_findings, print_settings, delivery_matrix_review, real_models,
  prepare, gcode) **2 810 grün, 4 übersprungen, Exit 0**. `ruff check` und `ruff format
  --check` über die vier geänderten Python-Dateien Exit 0, `mypy` 375 Dateien Exit 0. Der
  Worktree blieb unverändert (`git status` leer).
- **Changelog:** ein Punkt unter `## 0.6.0` in allen sechs Sprachen an derselben Stelle,
  150/149/164/171/168/169 Zeichen, als Eigenschaft formuliert; der zweite Satz sagt zu viel:
  Bögen in tiefen Mauern nur ab 0,2 mm (Z2), „Flache Decken behalten ihre“ nicht für flache
  Halbkuppeln (Z1).
- **Regel, Begründung, Archiv:** N1–N7 nachgezogen, Register ohne RM-585, Archiv mit Befund,
  Nachprüfung und Nachweis; ehrlich bis auf Z2 und Z1 (die Regel nennt gekrümmte Streifen
  nicht). Der neue Punkt „Wächter für N4“ aus `rm585b.md` ist mit `5a33fc8ad` erledigt.
- **Budgets:** Karte `app/core/slice/CLAUDE.md` eine Zeile, `test_directory_docs` grün;
  `tests/CLAUDE.md` unberührt. CPU-Zeit des Stützbedarfs am Drachen (45°, gleichzeitig mit
  anderen Läufen) welle4 482,0 s, Zweig 488,9 s (+1,4 %); Eiffelturm siehe Fixbericht.
  Druckgleich: Kein Netz und keine Lage ändert sich; die Bündelung ist nicht Gegenstand dieser
  Runde.

## Regeldurchgang (`/regelcheck`)

1: kein Qt im Diff (`test_core_isolation` grün). 2–4: keine Op berührt. 5: `vaults`,
`hanging_vaults` öffentlich ohne §9-Vertrag wie `ledges` (aus der ersten Runde, kein neuer
Befund). 6: Millimeter, doppelte Genauigkeit, kein `==` auf Fließkomma (nur Schichtnummern).
7: `CANTILEVER_LAYERS` ist keine Passtoleranz. 8: `CANTILEVER_LAYERS` steht jetzt nur in
`min()` neben der Bahn aus `bridge_from` und ist mit einer Messreihe begründet; dass es bei
0,2 mm für die kurze Brücke entscheidet, sagen die Unterlagen falsch (Z2). 9–13: nicht
berührt. 14: Archiv trennt Analyse- und G-Code-Zahlen. 15/22: keine Abhängigkeit. 16–21:
nicht berührt; keine neue Ausnahme, kein Oberflächentext. Bezeichner englisch, Docstrings
deutsch mit Umlauten. Zwillinge: Z3.

## Messungen

Skripte und Protokolle unter `scratchpad\rv585n2\` (Sitzung 78c2d72e), Exporte, Übergaben und
G-Codes unter `F:\rv585n2-scratch\`; gepinnt (`start /affinity FFFFF0FF`, `GESAMT_KERNE`),
Exit-Code im Skript, `TEMP`/`TMP` auf F:.

| Lauf | Inhalt | Exit |
|---|---|---|
| `mxk.sh` | Matrix CC2, grenuttags und obj_15, welle4/Zweig | 0 (4×) |
| `kd.sh`, `kdo.sh`, `kdb.sh` | Kanalfrage Stück für Stück (grenuttags CC2/45°, obj_15, Schüssel, Minigolf) | 0 (w4-Lauf von grenuttags erst nach Korrektur der Sonde, `vaults` fehlt in welle4) |
| `gko.sh`, `gkb.sh`, Hand | `gcode_im_kanal.py` grenuttags, obj_15, Schüssel, Minigolf | 0 |
| `d45.sh` | Drache 45°, Säulen (`drache45.py`) | 0 / 0 |
| `dr.sh` | Drache Matrix CC2, welle4/Zweig | 0 / 0 |
| `mxb.sh` | Matrix CC2 Schüssel und Minigolf, Dateilage | 0 (4×) |
| `g2.sh` | 23 Prüfkörper × 5 Einstellungen, welle4 0,84 / Zweig 0,84 / Zweig 1,0 | 0 (15×) |
| `ek.sh` | Eiffelturm CC2 und 45°, Kumiko 45° am Endstand | 0 (3×) |
| `ku.sh`, `ku2.sh` | Kuppeln und Halbkuppeln, welle4/Zweig | 0 (10×) |
| `mxh.sh` | Halbkuppel R 12/2 Matrix CC2 und `luft.py` | 0 (3×) |
| `mxbd.sh`, `gkbd.sh` | Waschschüssel in Drucklage, Matrix CC2 welle4/Zweig, Stütze im Sperrkörper | welle4 0; Zweig nach „Vorschläge“ von mir per PID beendet (Variante „Stützen automatisch“ nicht gebraucht); `gkbd` 0 |
| `fx.sh`, `fxk.sh` | Experiment Z1 an der Kopie `fix1` | 0 (9×) |
| `mut.sh` | N4-Wächter unverändert / mutiert | 0 / 1 (erwartet) |
| `tests.sh` | Baumleser 3 257 grün, gezielt 2 810 grün | 0 / 0 |
| ruff, format, mypy | vier Dateien / 375 Dateien | 0 / 0 / 0 |

Zwei Ausrutscher meinerseits: zweimal ein Hilfsaufruf mit `python -` (02:40:38 und
03:23:48); beide Prozesspaare per PID beendet (Elternprozess je meine Shell), gerechnet
haben sie nichts.

**Für den Koordinator:** C: war um 02:32 voll (861 MB frei); fremde Exporte im Scratch des
Bauagenten (`rm585b\alt`, `mut`, `mut2`, `n4`, `n5`, `n6`, `neu`, `o4`, `w4`) liegen dort
weiter — nicht von mir angefasst. Meine Exporte und Übergaben unter `F:\rv585n2-scratch\` und
`F:\tmp-agenten\rv585n2\` sind nach dem Urteil löschbar.

## Urteil

**Nicht landen** in dieser Form. Die zweite Fixrunde hält, was sie zusagt: N1–N7 sind
behoben (Kumiko mit Stütze, Pultdecke und Haut in 20 mm Tiefe bei 0,2 mm mit, Eiffelturm,
Rund- und Spitzbögen, Arkade ohne; Drache bei 45° mit beiden Taschen gesperrt und nur ihren
Scheiteln ausgespart; Neigungsreihe monoton, ihr Wächter `5a33fc8ad` beißt). Die beiden
Korpusmodelle mit geschrumpfter Sperre bekommen im ElegooSlicer keine Stütze in einen Raum,
aus dem sie nicht herauskommt (grenuttags: Stütze unter dem Scheitel in einem offenen C,
obj_15: Sperrkörper am Kundenweg unverändert, weniger Stütze darin); Minigolf und Schüssel
sind plausibel, der Drache am CC2 inhaltsgleich zu welle4; Tests, ruff, format, mypy grün.

Es hält der neue schwere Befund **Z1** an: Die Tür „zwischen zwei Auflagen“ ist für gekrümmte
Streifen offen. Eine flache Halbkuppel (Nische 24 × 12 mm, Stich 2 mm) bekommt am Centauri
bei 0,2 mm statt 12,9 m Stütze keine, im G-Code hängen Bahnen bis 2,5 mm neben der Schicht
darunter — dieselbe Art Fehlentwarnung wie N2, nach der Regel des Koordinators eindeutig.
**Nicht ohne weitere Prüfung behebbar**, aber eng: Das Experiment `fix1` (sieben Zeilen,
lose Kante des freien Teils höchstens `SPAN_INTERESTING`) schließt R 10 und R 12 und lässt
Eiffelturm, Bögen und S1-Körper unverändert; danach Tests (Halbkuppeln), Korpus an CC2 und
45° und eine gezielte Nachprüfung von Z1. Z2 (Unterlagen und Changelog ohne Schichthöhe) und
Z3 (Zwilling) sind ohne weitere Prüfung behebbar und können mitgehen. Wer Z1 nicht vor dem
Schnitt beheben will, muss das Risiko ausdrücklich ins Register nehmen (gekrümmte flache
Decken ohne Stütze) — das wäre eine Entscheidung des Koordinators, keine Empfehlung von mir.

## Gezielte Nachprüfung (Z1–Z3)

Prüfer rv585z (solidon3d-review), 11.10.2026 07:00–07:15. Prüfling: Zweig
`einstellungen/boegen-rm585`, Spitze `249dbfe57` (welle4 `4c135723a` gemergt), Worktree
`F:\sl-boegen` nur gelesen (`git status` vor und nach den Läufen leer). Fixes: `f11790806` (Z3),
`db41b0b1f` + `b452c0cc5` (Z1), `04109401b` (Z2). Gelesen: `git diff 5a33fc8ad 04109401b`
(11 Dateien, +170/−56), dazu `_carries`, `_beyond`, `_runs_free`, `_held_twice`, `_runs_loose`,
`_hangs_on`, `_anchored_span`, `_merged_lines`, `_areas_of` am Endstand und der Exportweg der
Sperre (`writer.py:2851–2864`).

Weiterverwendet aus der abgebrochenen dritten Runde von rv585n2 (alle Exit 0): Exporte
`F:\rv585n2-scratch\neu2` (= `249dbfe57`, `analysis.py` mit `cmp` gegen den Worktree gleich) und
`w4b` (= `4c135723a`, `cmp` gegen `git show` gleich); `nk.sh` (Matrix ElegooSlicer, Centauri
Carbon 2, 0,2 mm, gepinnt, G-Codes behalten, 13 Läufe); `p2.sh` (23 Prüfkörper × 5
Einstellungen, Kuppeln und Halbkuppeln, Eiffelturm CC2/45°, Kumiko 45°, Drache 45°; 16 Läufe)
mit `out/p2_tab.txt` (welle4 / `c8e42e34a` / Zweig). Eigene Sonden und Ausgaben unter
`F:\tmp-agenten\rv585z\` (`out\`).

### Punkt 1 — Z1 behoben, keine neue Entwarnung durch `b452c0cc5`

- **Halbkuppel-Nische:** `test_a_flat_half_dome_keeps_its_supports` (R 10/1,7 bei 45° und 60°,
  R 12/2 bei 60°) grün; Gegenprobe an einer Kopie mit `_runs_loose` ≡ „nie lang“ (Stand vor Z1,
  `mut_z.py A`): **3 von 3 rot**, Exit 1 — der Wächter beißt. Sonde `kuppel2.py` am Zweig
  (`p2_tab.txt`): R 10 bei 0,2/45 und 0,2/60, R 12 bei 0,2/60 von „nein“ (`c8e`) auf „ja“;
  R 15, R 20, geschlossene Kuppel R 20 überall „ja“. Am Kundenweg (Matrix CC2, `nk.sh`): R 12/2
  und R 10/1,7 brauchen am Zweig Stütze, Rat `auto`/`build_plate` wie welle4, 12,94 m und
  9,44 m Stütze — **gleich welle4**.
- **`b452c0cc5` (Ausnahme mit `_anchored_span`):** Gegenprobe ohne die Ausnahme (`mut_z.py B`):
  4 Tests rot (`test_a_channel_ceiling_stays_a_channel_with_an_open_end[0.08|0.2]`,
  `test_a_strip_at_a_channel_mouth_does_not_borrow_the_channel_for_its_field`,
  `test_an_open_strip_at_a_channel_mouth_is_asked_without_the_channel`), Exit 1 — sie ist
  bewacht. Neue Entwarnung gegenüber `c8e`: **keine** — in `p2_tab.txt` geht jeder Wechsel
  `c8e` → Zweig nach „ja“. Rund-, Spitz-, Flach- und Korbbögen, Arkade (8 mm), Pult, Haut,
  Sattel wie `c8e`. Eiffelturm CC2 und 45° (`kanal_diff`): `needed` nein, Überhang, Feld,
  412 / 2 536 Bogenstreifen, Sperre 3 277,6 / 47 966,3 mm³ — **identisch zu `c8e`**. Kumiko 45°
  weiter mit Stütze (Feld 3 587 mm², 3 145 → 3 115 Bogenstreifen). Drache 45°: Kanalstücke,
  Säulen, Sperre identisch zu `c8e`; CPU 451,4 s (w4b) gegen 454,4 s (Zweig), +0,7 %.
- **Rest (leicht, kein neuer Befund, nicht blockierend) — kleine Halbkuppel bei 0,28 mm:**
  R 8/1,3 bei 0,28/60 welle4 „ja“, Zweig „nein“ (Feld 3,6 mm²; im Z1-Experiment `fix1` schon
  so, dort „knapp“ genannt; nicht im Auftrag der Fixrunde). Ursache dieselbe Tür wie Z1, nur
  unterhalb der Schwelle: Die lose Innenkante des obersten Rings ist ein Halbkreis von 9 bis
  15 mm, also nie länger als `SPAN_INTERESTING` (`analysis.py:4408–4413`, `:5017`), und die
  Hülle seines Bogens fasst ihn. Gerechnet (Kugelkappe R 25,3 mm) wächst der oberste Ring bei
  0,28 mm gut 1,3 bis 1,8 mm je Schicht, mehr als Zugabe plus zwei Bahnen (0,485 + 0,84 =
  1,33 mm). Nicht im G-Code gemessen: Die Matrix fährt das 0,2-mm-Profil, und dort braucht
  R 8 schon in welle4 keine Stütze. Vorschlag: neuer Punkt fürs Register („kleine Halbkuppel
  bei 0,28 mm ohne Stütze“) mit einem Druck- oder G-Code-Nachweis im Entwurfsprofil, bevor man
  die Tür für einseitige Bogenstücke ganz schließt.

### Punkt 2 — grenuttags und Waschschüssel im ElegooSlicer (CC2), welle4 gegen Zweig

Matrix aus `nk.sh` (Dateilage wie der Korpuslauf) und eigener Lauf in Drucklage (`mxd.sh`),
Sperrkörper je Stand aus der Übergabe-3MF (`gk_z.sh`, `extract.py`), Stützbahn im
**welle4**-Sperrkörper (`gcode_im_kanal.py`); je Bahn in diesem Körper zusätzlich, ob sie in
einem Loch des Querschnitts liegt (`eingeschlossen.py`) und ob ein gerader Strahl in ±x/±y aus
dem Körper führt (`raus.py`); den freien Raum an den Stellen misst `kanalraum.py` (Fläche,
Öffnung zur Hülle). Alle Läufe Exit 0 außer `gk_gd` (siehe Drucklage).

**`grenuttags_hallare_modell_41x47_curved`, Dateilage:**

| | welle4 `4c135723a` | Zweig `249dbfe57` |
|---|---|---|
| Rat (Matrix) | Baum, Kanalsperre, Ränder, dicke Brücken, Brückenfluss 0,9 | Baum, Ränder |
| Sperrkörper der Übergabe | 2 179 mm³, z 3,8–58,8 | 28 mm³ (nur Rand, z 44–48 am Rücken) |
| Stütze Vorschläge gesamt / im welle4-Sperrkörper | 86,93 m / 0,05 m | 93,24 m / 3,92 m |
| davon im Loch / ohne geraden Ausweg | 0 / 0 m | **0 / 0 m** |
| „Stützen automatisch“ im welle4-Sperrkörper | 3,96 m | 3,96 m |

Die 3,92 m stehen wie in Runde 2 unter dem Scheitel (z 56–58, x −10,5…10,6, y −12,8…13,4).
Das Profil ist ein Haken: Rücken y 20,5–23,5 vom Bett bis oben, Bogen über die ganze Breite,
vorn eine Lippe bis z 50 (`raum_g_z.txt`); der Schnitt x = ±9,9 ist eine Fläche ohne Loch. Der
freie Raum unter dem Bogen ist bei z 50–58,3 nach vorn und hinten (x = ±10) offen, 21–82 mm
Öffnung, 10 mm vom Stützpunkt (`raum_g_kanal00.txt`); die Säulenhülle liegt zu 100 % frei, 0 %
im Loch. **Die Feststellung aus Runde 2 gilt nach Z1 weiter: Die Stütze kommt heraus**, jede
Bahn auf geradem Weg nach vorn oder hinten. Der Slicer selbst stellt dort dieselben 3,96 m hin.
**Drucklage** (wie der Kunde, `GESAMT_AUSRICHTEN=1`): Das Teil liegt flach (20 mm hoch), in
beiden Ständen kein Stützbedarf, gleicher Rat (Erstschicht 50, Arachne), 0 m Stütze, keine
Sperre — darum hat `gk_gd` keinen Sperrkörper zu zählen (Exit 1 an der fehlenden Datei).

**Waschschüssel, Dateilage** (Schüssel liegt auf der Seite, Rand in der Ebene y = 57,5):

| | welle4 | Zweig |
|---|---|---|
| Rat | gleich (Hybrid, Kanalsperre, Ränder, dichte Trennschicht, feine Schichten 0,1 …) | gleich |
| Sperrkörper der Übergabe | 30 356 mm³ | 21 437 mm³ (gleiche Hülle) |
| Stütze Vorschläge gesamt / im welle4-Sperrkörper | 4 099,3 m / 4,88 m | 4 219,7 m / **41,42 m** |
| davon im Loch des Querschnitts | 0 m | **0 m** |
| davon gerader Ausweg zum Rand (+y) / in keiner Achsrichtung | 0,13 / 4,74 m | 31,98 / 9,44 m |
| „Stützen automatisch“ im welle4-Sperrkörper (ohne Achsausweg) | 44,78 m (12,74 m) | 44,78 m (12,74 m) |

Die Querschnitte z 12,5–52 haben **kein einziges Loch** (`raum_b_schnitte.txt`); die Säulenhüllen
der Zweigstütze (z 11–18,6 und 46–53) liegen zu 0 % im Loch. Die 9,44 m ohne geraden Ausweg
(z 11–18 bei x 74–82, y 0–8; z 46–53 bei x 60–91, y −10,5…17) stehen hinter der Innenwand,
aber im großen freien Raum des Beckens: 6 900–17 900 mm², zum Rand über 107–298 mm offen
(`raum_b_keiner.txt`, dieselbe Fläche wie an den Punkten mit geradem Ausweg); welle4 selbst
stellt 4,74 m an solche Stellen, der Slicer allein 12,74 m. **Keine Stütze in einem Raum, aus
dem sie nicht herauskommt.** Die Sperre schrumpft dort, wo Z1 weitere einseitige
Scheitelstücke aussparen lässt; das ist die beabsichtigte Folge.
**Drucklage:** Sperrkörper 87 464 → 87 060 mm³, Stütze Vorschläge 792,7 → 627,7 m (Rat Raster
→ Hybrid, wie in Runde 2), im welle4-Sperrkörper **0,0 / 0,0 m**; „Stützen automatisch“ 14,23 m
in beiden Ständen.

### Punkt 3 — Z2, Z3, Changelog

- **Z2:** Regel (`.claude/rules/druckrat.md:137–153`), Begründung
  (`regel-druckrat.md:610–638`), Archiv und Docstring `CANTILEVER_LAYERS`
  (`analysis.py:4081–4089`) nennen die Schichthöhe: ab 0,2 mm Stütze für tiefe Pultdecke,
  Haut und Rundbogen, bei 0,08/0,12 mm Kragarm ab gut 11°; die kurze Brücke deckeln bis gut
  0,2 mm die Schichthöhen (4 · 0,2 = 0,8 gegen 0,84). Deckt sich mit `p2_tab.txt`. Behoben.
- **Z3:** `_beyond` (`analysis.py:4900–4930`) liefert freien Teil, Fenster und Halt einmal, je
  Stück gemerkt; `_carries`, `_runs_free`, `_held_twice` nehmen ihn. Am Code nachgerechnet:
  Fenster, Puffer, Rauschgrenze und Halt (`reach + OVERHANG_MARGIN/2`) sind dieselben wie
  vorher, auch der Fall ohne Material im Fenster (vorher `_hangs_on` → nein, jetzt freier
  Teil = ganzes Stück → nein). Behoben, druckgleich (Eiffelturm, Drache identisch).
- **Changelog:** ein Punkt unter `## 0.6.0` in allen sechs Sprachen an derselben Stelle, zweiter
  Satz jetzt „Fast flache Decken behalten ihre.“ (en „Nearly flat ceilings keep theirs.“, es
  „techos casi planos“, fr „plafonds presque plats“, it „soffitti quasi piani“, pt „tetos
  quase planos“) — inhaltsgleich, als Eigenschaft, `test_changelog`/`test_text_length` grün.
  Einzige Unschärfe: die kleine Halbkuppel bei 0,28 mm aus Punkt 1 behält ihre nicht.

### Punkt 4 — Tests

`tests_z.sh` (gepinnt, ohne Bytecode und Cache, `--basetemp` unter `F:\tmp-agenten\rv585z`,
`app` aus `F:\sl-boegen`): `test_slice_findings`, `test_advise` und die Baumleser
`test_toolchain`, `test_finding_ways`, `test_finding_actions`, `test_hard_rules`,
`test_errors`, `test_core_isolation`, `test_interface_limits`, `test_value_labels`,
`test_shared_constants`, `test_language_rules`, `test_registry_consistency`,
`test_text_length`, `test_changelog`, `test_roadmap`, `test_directory_docs` ohne Fenster:
**3 887 grün, 5 übersprungen, Exit 0**. `ruff check` und `ruff format --check` über
`analysis.py` und `test_slice_findings.py` Exit 0. `test_parts::…range_proof` nicht gefahren
(welle4-weit rot, kein Fund).

| Lauf | Inhalt | Exit |
|---|---|---|
| `tests_z.sh` | Hauptliste / mutA / mutB | 0 / 1 (3 rot, erwartet) / 1 (4 rot, erwartet) |
| `gk_z.sh` | 6 Sperrkörper, `gcode_im_kanal` grenuttags, Schüssel Datei- und Drucklage | 0 (9×) |
| `mxd.sh` | Matrix grenuttags Drucklage w4b/Zweig, Auszug | 0 (4×); `gk_gd` 1 (kein Sperrkörper) |
| `eg.sh`, `raus.sh` | Loch und gerader Ausweg, Schüssel und grenuttags | 0 (4×) |
| `raum_g.sh`, `raum_b.sh`, Hand | Profil, Querschnitte, freier Raum | 0 |
| ruff, format | zwei Dateien | 0 / 0 |

### Urteil der gezielten Nachprüfung

**Kann landen.** Z1 ist für die gemessenen Fälle behoben und bewacht (Halbkuppel R 10/R 12 am
Centauri wieder mit 12,94 / 9,44 m Stütze wie welle4, Test 3 von 3 rot ohne Fix);
`b452c0cc5` öffnet keine neue Entwarnung (Eiffelturm, Bögen, Arkade, Kumiko, Drache wie
vorher) und ist selbst bewacht (4 rot ohne). grenuttags und Waschschüssel bekommen im
ElegooSlicer keine Stütze in einen Raum, aus dem sie nicht herauskommt: grenuttags 3,92 m
unter dem Scheitel, jede Bahn mit geradem Weg nach vorn oder hinten; Schüssel 41,42 m im
alten Sperrkörper, 0 m in einem Loch, alles im offenen Becken; in Drucklage beide 0 m. Z2, Z3
und der Changelog stimmen; Tests, ruff, format grün. Offen bleibt nur der leichte Rest aus
Punkt 1 (kleine Halbkuppel R 8/1,3 bei 0,28 mm ohne Stütze) — als neuer Punkt fürs Register,
kein Grund, die Landung anzuhalten.
