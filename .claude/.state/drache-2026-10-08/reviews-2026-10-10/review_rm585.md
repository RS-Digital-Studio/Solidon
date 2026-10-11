# Review RM-585 — Bögen, die sich zwischen ihren Beinen schließen

Prüfling: Worktree `F:\sl-boegen`, Zweig `einstellungen/boegen-rm585`, Commit `d176bc5ca` auf
`a9e4d3f64`. Reviewer: solidon3d-review (Sitzung „Einstellungen nach dem Modell“, 10.10.2026).
Sonden und Ausgaben: `scratchpad\rv585\` (`koerper.py`, `tabelle.py`, `zeit.py`, `luft.py`,
`streifenart.py`, `mutation.py`, `proto_patch.py`, Läufe unter `out\`).

Stand: abgeschlossen. Urteil: **nicht landen**, Nachprüfung nötig (S1 schwer, M1/M2 mittel,
L1–L3 leicht, zwei neue Punkte).

## Vorgehen

- Diff vollständig gelesen (15 Dateien, +393/−48), dazu `_Ceilings`, `_model_support`,
  `support_need`, `_may_need_support`, `_bridge_width`/`_supported_span`, `overhang_findings`,
  `orientation.stays`, Regel `druckrat.md`, Karte `app/core/slice/CLAUDE.md`, Archiveintrag.
- Neuer Stand: Worktree als erstes `sys.path`-Element (`app.__file__` geprüft). Alter Stand:
  `git archive a9e4d3f64` im Scratch (`alt_np`, ohne übersetzten Kern wie der Worktree). Für
  Zeitmessungen beide Stände als Export mit demselben `_chain.cp314-win_amd64.pyd`
  (`_chain.pyx` gleich in beiden Ständen und im Hauptbaum, `.pyd` danach gebaut).
- Alle Läufe gepinnt (`start /affinity FFFFF0FF`), Exit-Code im Skript geschrieben (Übersicht
  unter „Messungen“). Der Worktree blieb unverändert (`git status` leer, HEAD `d176bc5ca`).
- Slicer über `tools/matrix_unit.py` (Druckdialog-Weg) mit `GESAMT_AUSRICHTEN=0`
  (aufrecht, wie gebaut) und `GESAMT_BEHALTEN=1`: ElegooSlicer am Centauri Carbon 2 (Prozess
  „0.20mm Standard“, `enable_support = 0`, Schwelle 30°), PrusaSlicer am MK4S.

## Befunde

### S1 (schwer) — Fast flache Decken gelten als Bogen: falsche Entwarnung

`app/core/slice/analysis.py:3688–3702` (`_hangs_on`), `:3656–3685` (`_vault_strips`).

Ein Streifen gilt als selbsttragend, wenn er bis `LEDGE_REACH` = **3 mm** über das Material
seiner eigenen Schicht darunter ragt. Gemeint ist je Schicht, nicht je Decke: bei 0,2 mm
Schichthöhe eine Unterseite von 3,8° gegen die Waagerechte, bei 0,08 mm von 1,5°. Eine Grenze
der Spannweite zwischen den Beinen gibt es nicht. Jede schwach geneigte Decke zwischen zwei Wänden
„schließt sich zwischen ihren Auflagen“ — an ihrer letzten Schicht, an der hohen Wand — und
verliert ihre Fläche. Gedruckt wird ein Bogen aber Schicht für Schicht als zwei Kragarme, die erst
mit der letzten Schicht zusammenkommen; dass er sich schließt, hilft keiner Schicht davor. Was
`_hangs_on` je Streifen prüfen müsste, ist der Kragarm, und 3 mm sind keiner mehr.

**Analyse** (Sonde `koerper.py`, Wand 8 mm tief, Startregel 45°, alter → neuer Stand):

| Körper | Schicht | Stützen nötig | Reichweite je Streifen | Streifen > 2 mm |
|---|---|---|---|---|
| Pultdecke 40 mm, 3 mm Anstieg (4,3°) | 0,2 | ja → **nein** | 2,67 mm | 13 von 15 |
| Pultdecke 80 mm, 6 mm Anstieg (4,3°) | 0,2 | ja → **nein** | 2,67 mm | 28 von 30 |
| Flachbogen Sehne 80, Stich 10 | 0,2 | ja → **nein** | 3,01 mm | 4 |
| Flachbogen Sehne 60, Stich 8 | 0,2 | ja → **nein** | 2,54 mm | 2 |
| Flachbogen Sehne 40, Stich 3 | 0,2 | ja → **nein** | 2,70 mm | 2 |
| Korbbogen 60 × 12 | 0,2 | ja → **nein** | 2,80 mm | 2 |
| Satteldecke 40 mm, 3 mm Stich (8,5°) | 0,2 | ja → **nein** | 1,33 mm | 0 (28 > 1 mm) |
| Decke 30 mm, um 5° geneigt | 0,2 | ja → **nein** | 2,29 mm | 11 |
| Decke 30 mm, um **2°** geneigt | **0,08** | ja → **nein** | 2,29 mm | 12 |
| Decke 30 mm, waagerecht (Testfall `flache-decke`) | 0,08–0,28 | ja → ja | — | — |

Zwei Grad Neigung machen bei feinen Schichten aus einer Decke wie im Testfall `flache-decke`
(30 mm zwischen zwei Wänden, dort „braucht Stützen“) eine, die keine braucht. Ohne Stützen im
Profil (Elegoo-Standard) kommt kein Vorschlag mehr; mit Stützen im Profil rät Solidon
`support.style=none` „Nichts an diesem Teil braucht eine Stütze.“. Vorher lautete der Rat „Die Überhänge sind zu groß, um sich selbst zu tragen.“
(`support.style=auto`, `placement=build_plate`). Der Prüfbericht meldete an diesen Körpern in
keinem Stand etwas (kein Stück über 100 mm², keine Brücke über 15 mm) — der Druckrat war die
einzige Stelle, die Stützen verlangte. Bauplan §28.3: Der Überhangwinkel ist eine
Prozessmessung, „die wirksamen Grenzen gehen in … Schichtanalyse … ein“. In der Bogenfrage geht
er nicht ein: Ob 35° oder 60° kalibriert sind, jeder Streifen bis 3 mm gilt als getragen.

**Echte Slicer** (Druckdialog-Weg, Winkel der Programme: Elegoo 60°, Prusa 55°):

| Körper | Slicer | Stütze mit Solidons Vorschlägen alt → neu | „Stützen automatisch“ des Slicers |
|---|---|---|---|
| Pultdecke 40/3 | ElegooSlicer | 12,45 m → **0 m** | 12,45 m |
| Pultdecke 40/3 | PrusaSlicer | 12,96 m → **0 m** | 13,97 m |
| Flachbogen 60/8 | ElegooSlicer | 27,25 m → **0 m** | 27,25 m |
| Flachbogen 60/8 | PrusaSlicer | 25,81 m → **0 m** | 27,05 m |
| Rundbogen R 20 | ElegooSlicer | 0 → 0 (bei 60° schon alt ohne Stütze) | — |

Im G-Code ohne Stütze (`luft.py`: Modellbahnen gegen den Querschnitt in der Mitte der Schicht
darunter, frei ab einer halben Bahnbreite; „Kragarm“ = freier Lauf mit freiem Ende):

| Körper (neuer Stand, Solidons Vorschläge, 0 m Stütze) | Slicer | Kragarm-Bahn gesamt | weitester Kragarm | Läufe > 1 mm |
|---|---|---|---|---|
| Rundbogen R 20 (Gegenfall) | ElegooSlicer / PrusaSlicer | 13 / 13 mm | 0,41 / 0,47 mm | 0 / 0 |
| Pultdecke 40/3 | ElegooSlicer / PrusaSlicer | 391 / 368 mm | **1,73 / 1,68 mm** | 14 / 14 |
| Flachbogen 60/8 | ElegooSlicer / PrusaSlicer | 92 / 78 mm | **1,54 / 1,53 mm** | 2 / 2 |

Die Pultdecke lässt Schicht für Schicht Bahnen von bis zu 32,5 mm Länge mit freiem Ende 1,7 mm
neben der Kante hängen, viermal so weit wie am Rundbogen; am Flachbogen kommen im Scheitel gefasste
Bahnen bis 3,47 mm dazu. Mit Stützen an stellt derselbe Slicer genau dort 12,45 m (Pultdecke) und
27,25 m (Flachbogen) Stütze hin — dieselben Modellbahnen, darunter Stütze.

**Was den Eiffelturm von der Pultdecke trennt** (Sonde `streifenart.py`): Die weiten Streifen des
Turms sind keine Kragarme. Bei Reichweite 2,84 mm hat ihre freie Fläche einen Inkreis von 7,3–7,5 mm
(Verhältnis 2,6): Sie liegen zwischen zwei Auflagen wie eine Brücke von 7,5 mm. Die Streifen von
Pultdecke, Flach-, Korb- und Satteldecke und Rundbogen hängen an einer Seite (Verhältnis 0,84–0,92).
Einseitige Streifen über 1 mm Reichweite bilden am Turm keine Fläche (größtes zusammenhängendes
Stück 6,2 mm², 72 Streifen über das Gitter verstreut), an der Pultdecke 265,6 mm² an einem Stück,
an der Satteldecke 126,9, am Korbbogen 68,1, am Flachbogen 60/8 55,9 je Seite, am Rundbogen R 20
10,0 je Seite.

**Am echten Modell — Roberts Drache** (`output/drache-2026-10-08/obj3.stl`, Drucklage, 0,2 mm,
45°): 1 505 Stücke gelten als Bogenstreifen; das Bild `scratchpad\rv585\bilder\drache_boegen_z60-66.png`
zeigt sie an den Unterseiten beider **Flügelhäute** zwischen Rumpf und Flügelknochen und am linken
Flügelbogen (die Stellen, die im RM-566-Druck in die Luft gingen). 35 davon hängen einseitig weiter
als 1 mm, bis 2,25 mm je Schicht, zusammenhängend bis 98,6 mm². Der Rat ändert sich am Drachen
heute nicht (122 Inselschichten verlangen Stütze ohnehin, Bogenstreifen werden nicht gesperrt;
Vorschläge in allen drei Ausgangslagen gleich, `rat.py`), aber Überhang ohne Kanäle/Ränder fällt
von 696 auf 327 mm² und „auf dem Modell“ (`open_area`) von 300 auf 207 mm². Ein Teil mit solchen
Flügeln und ohne Inseln bekäme die Entwarnung.

Zur Einordnung der Belege des Autors: Auch am Eiffelturm hängen Bahnen mit freiem Ende weiter als
die genannten 0,51 mm — im eigenen ElegooSlicer-G-Code des Autors (`m_neu/…/eiffel/…/vorschlaege`)
bei z 26,8 acht Wandstücke von 4,7 mm Länge 2,13–2,14 mm über die Kante, im PrusaSlicer 1,72 mm
(L2). Das sind die einseitigen Scheitelstreifen der Turmbögen (rot im Bild
`bilder\eiffel_boegen_z14-30.png`), kurz und verstreut; ob sie sauber drucken, sagt nur ein Druck.

**Fix:** `_hangs_on` fragt den Kragarm, nicht die Reichweite. Ein Streifen, der an einer Seite
hängt (Inkreis seiner freien Fläche nicht größer als seine Reichweite), trägt sich nur bis zu einer
Weite, die an Schichthöhe und wirksamem Überhangwinkel hängt (§28.3; eine eigene, hergeleitete
Größe, nicht `LEDGE_REACH`, das die ganze Decke eines Rands meint). Was weiter kragt, zählt mit
seiner Fläche, zusammenhängend gemessen. Die Messung trennt die Fälle deutlich — größtes
zusammenhängendes Feld einseitiger Streifen über 1 mm Reichweite (0,2 mm, 45°):

| Körper | Feld | Körper | Feld |
|---|---|---|---|
| Eiffelturm | 6,2 mm² | Flachbogen 60/8 | 55,9 mm² |
| Spitzbogen 40/24 | 0 | Flachbogen 40/3 | 66,9 mm² |
| Rundbogen R 20 | 10,0 mm² | Korbbogen 60/12 | 68,1 mm² |
| Rundbogen R 30 | 20,9 mm² | Flachbogen 80/10 | 89,6 mm² |
| — | — | Satteldecke 40/3 | 126,9 mm² |
| — | — | Decke 30 mm um 5° | 207,8 mm² |
| — | — | Pultdecke 40/3, 40/5 | 265,6 / 268,8 mm² |

Mit `worth_support` allein (100 / 150 mm²) blieben Flach- und Korbbögen durch; die Grenze liegt
zwischen 21 und 56 mm² und braucht eine Herleitung (Druck oder Slicerbeleg). Ein Streifen zwischen
zwei Auflagen (Eiffelturm, Verhältnis 2,6) bleibt Bogen bis zu einer Brücke unter
`SPAN_INTERESTING`. Abnahme: die Körper der ersten Tabelle behalten Stützen (auch bei 0,08 und
0,28 mm, 45/55/60°), Rundbogen R 20 und Eiffelturm bleiben ohne, die Flügelhäute des Drachen sind
keine Bogenstreifen; Tests dazu (M1).

### M1 (mittel) — Die Grenze, die vor S1 schützen soll, prüft kein Test; drei weitere Stellen auch nicht

`tests/test_slice_findings.py:2739–2816` und die übrigen Tests des Gebiets.

Gegenproben per Mutation (`mutation.py`, je Mutation `test_slice_findings.py`,
`test_advise.py`, `test_print_findings.py`, 269 Fälle; Ausgangsstand 269 grün):

| Mutation | Ergebnis |
|---|---|
| `_hangs_on` gibt immer `True` (keine Reichweitengrenze je Streifen) | **269 grün** |
| `open_pieces` ohne Bogenstreifen (`bearing` statt `bridging`) | **269 grün** |
| `overhang_findings` ohne `vaults` (Änderung in `findings.py` zurück) | **269 grün** |
| `_model_support`: `edges = rims` (Bogenstreifen wieder „auf dem Modell“) | **269 grün** |
| `_hangs_on` mit 1 mm statt 3 mm | 1 rot: `…carries_itself[rundbogen]` |
| oberste Schicht zählt mit | 2 rot |
| ohne Filter `spanned` | 1 rot (Haube an der Tunnelmündung) |
| ohne Schließfrage | 12 rot |
| Bogenschichten ruhig für die Brückenregel | 1 rot (Steg auf Zwickeln bei 0,08 mm) |
| Stützbedarf ohne Bogenstreifen | 1 rot (Rundbogen) |

Die einzige Grenze, die einen Bogen von einer fast flachen Decke trennt, kann wegfallen, ohne
dass ein Test rot wird; die drei Stellen, an denen der Prüfling „auf dem Modell“, die Brückenfrage
auf dem Modell und den Prüfbericht ändert, ebenso. Dazu prüft
`assert arches == {name for name in pieces if name[0] < top}` (Zeile 2794) den Ist-Zustand, nicht die
Zusage: Jede Verschärfung der Grenze, die den Rundbogen weiter ohne Stütze lässt (1-mm-Mutation:
`needed` bleibt `False`), macht ihn rot, weil zwei Scheitelstreifen von 1,46 mm dann nicht mehr
in der Menge stehen. Alle neuen Fälle laufen bei 0,2 mm und 45°; der Kunde schneidet mit dem
Winkel seines Slicers (60/55/50°) und anderen Schichthöhen, an denen S1 kippt.

**Fix:** Mit S1 Fälle, die Stütze behalten müssen (Pultdecke 40/3 bei 0,2 mm, Decke 30 mm um 2°
bei 0,08 mm, Flachbogen 60/8 bei 60°), parametriert über Schichthöhe und Winkel; je ein Fall für
`open_pieces`/`open_area` eines Bogens über dem Modell und für den Prüfbericht (ein Körper, dessen
größtes Stück über 100 mm² ein Bogenstreifen ist — am Eiffelturm die vier gefassten Streifen von
110,7 mm² bei z = 21,5; ein Rundbogen in 80 mm tiefer Wand taugt nicht, dort bleibt die oberste
Schicht mit 287 mm² gemeldet, in beiden Ständen); die
Gleichheit in Zeile 2794 durch die Zusage ersetzen (kein Streifen der obersten Schicht, Stützbedarf
nein, Feld ohne Streifen klein). Jeder neue Test mit Gegenprobe.

### M2 (mittel, Regel „Gebündelt rechnen“) — Die Rand-/Bogenfrage kostet das Dreifache, und zwei Schleifen je Stück lassen sich bündeln

`app/core/slice/analysis.py:3680–3685` (Filter je Streifen in `_vault_strips`) und
`:4061–4079` (Halt je Stück in `_Ceilings._closes`, jetzt im heißen Pfad von `support_need`).

Gemessen an gesicherten Schnitten (0,2 mm, 45°), CPU-Zeit, je Frage ein frischer Prozess, im
Wechsel, beide Stände mit demselben übersetzten Kern (`zeit.py`, `t2.sh`):

| Frage | Körper | alt | neu | Prototyp gebündelt |
|---|---|---|---|---|
| `ledges(result)` (neu: Rand und Bogen in einem Durchgang) | Eiffelturm | 7,9 / 8,2 s | **24,1 / 23,8 s** | 12,9 / 12,2 s |
| dto. | Drache (`obj3.stl`, 2,9 Mio. Dreiecke) | 7,5 s | **14,0 s** | 12,0 s |
| `located_warnings` (Hinweise in Druckdialog und Prüfbericht) | Eiffelturm | 4,8 / 4,8 s | **19,7 / 19,5 s** | — |
| dto. | Drache | 2,7 / 2,7 s | **5,2 / 5,2 s** | — |
| `overhang_findings` (Prüfbericht) | Eiffelturm | 65,3 / 63,9 s, 2 Läufe `_ledges` | **83,1 / 86,2 s, 4 Läufe** | — |
| dto. | Drache | 0,08 / 0,06 s | 0,08 / 0,06 s (kein Stück über 100 mm²) | — |
| `support_need` | Eiffelturm | 170,6 / 179,5 s | 180,7 / 181,6 s | — |
| `support_need` | Drache | 471,8 / 463,3 s | 473,7 / 465,8 s | — |

Der Prüfbericht eines Eiffelturms kostet damit gut 35 s CPU mehr (Überhang- und Hinweisfrage),
bei gleichen Befunden. `located_warnings` wird am Eiffelturm viermal so teuer: `_from_spans`
fragt nur Ränder (`ledges(result, asked)`, `advise.py:2451`), und weil Rand- und Bogenfrage einen
Durchgang teilen (`_self_carried`), bezahlt sie die Bogenfrage samt Schließfrage des Turmbogens
mit, ohne das Ergebnis zu lesen. Mit `only` wird nichts gemerkt; der Prüfbericht
(`findings.body_findings`) stellt die Frage deshalb in `overhang_findings` zweimal (`ledges` und
`vaults`), in `model_support(only=…)` noch zweimal und in `located_warnings` ein fünftes Mal.

Im Profil (`profil.py`, Eiffelturm, neu) gehen 22,3 von 35,3 s in `_vault_strips`: 15,8 s
Schließfrage für 5 Decken, davon der größte Teil `difference` jedes Stücks gegen den **ganzen**
Grundriss `own` der Decke (6 344 Aufrufe, 13,6 s; der Turmbogen hat 2 244 Stücke), und 5,0 s für
den Filter, der jeden der 2 509 Streifen einzeln mit `between` schneidet. Am Drachen 8,0 von 17,3 s.

Der Prototyp (`proto_patch.py`, nur im Scratch) beschneidet `own` vor dem Abziehen auf dasselbe
Fenster wie das Material (`shapely.clip_by_rect(own, *window)`) und prüft die Streifen gegen das
vorbereitete `between` als Feld (`shapely.contains`, Schnittfläche nur für die übrigen, ein
Aufruf). Ergebnis gleich: Rand- und Bogenmengen am Eiffelturm und am Drachen hashgleich, alle
32 Prüfkörper mit identischen Antworten (Stützbedarf, Feld, Summe, Streifen, Rat, Bericht).
Die Rand-/Bogenfrage halbiert sich am Eiffelturm (24 → 12,6 s), der Drache spart 2 s.

Gemerkter Speicher ist dagegen kein Fund: `_CLOSINGS` hält am Eiffelturm 5 Decken mit 29 000
Koordinaten, am Drachen 19 Fragen, 10 Flächen, 43 715 Koordinaten (unter 1 MB).

**Fix:** beide Stellen wie im Prototyp bündeln, Gleichheit über Korpus und Beispielprojekte
belegen, Messung im Wechsel nennen. Wer nur Ränder fragt, rechnet keine Bögen (die Bogenfrage
erst auf Anfrage, oder `_self_carried` mit Schalter), und eine enge Antwort wird wenigstens für
`ledges`/`vaults` desselben Aufrufers nicht zweimal gerechnet (`overhang_findings` fragt beides
mit derselben Auswahl). Den Satz „Rand- und Bogenfrage gehen in einem Durchgang“ nur für die
volle Frage stehen lassen (siehe L2).

### L1 (leicht) — Ab 15 mm Wandtiefe bleibt jeder Bogen „Stützen nötig“, und das Netz darunter ist eine Diagonale

`app/core/slice/advise.py:914` (`resting` ohne Bogenstreifen) mit `analysis.py:2427–2428/2463`
(`_supported_span`: ohne beidseitig getragene Richtung die Diagonale).

Die Brückenregel, die der Prüfling als Netz unter den Bogenstreifen stehen lässt („die Streifen
einer schwach geneigten Decke zwischen zwei Beinen sind je eine Brücke“), misst an einem
einseitig hängenden Streifen keine Brücke, sondern seine Diagonale — praktisch die Wandtiefe.
Rundbogen R 20: Tiefe 8 und 12 mm ohne Stütze, 16 und 20 mm mit Stütze und Befund
`slice.long_bridge` „Hier spannt eine Decke frei, ihre Bahnen hängen durch.“ (16,1 / 20,1 mm), bei
denselben Streifen von 1,46 mm. Dasselbe Netz fängt die Pultdecke nur, wenn die Wand tiefer als
etwa 15 mm ist. Der Changelog verspricht „Solidon verlangt für sie keine Stützen mehr“; ein
Torbogen in einer 20 mm dicken Mauer bekommt sie weiter. **Fix:** Mit S1 die einseitigen
Streifen über das Kragarm-Maß beurteilen und aus der Diagonalen nehmen, die Brückenregel für
gefasste Streifen behalten; Changelog nach dem Fix an das tatsächliche Verhalten anpassen.

### L2 (leicht) — Belege und Unterlagen sagen mehr, als gemessen ist

- `ROADMAP-ARCHIV.md:46285–46286` und `konzepte/begruendungen/regel-druckrat.md:471–473`: „Bahnen mit
  freiem Ende ragen dort höchstens 0,51 mm über die Kante“. Die Sonde des Autors listete nur die
  *längsten* Läufe; seine eigenen G-Codes haben im Bogenband bei z 26,8 Kragarme von 2,13–2,14 mm
  (ElegooSlicer, `m_neu/…/eiffel/…/vorschlaege`, acht Wandstücke à 4,7 mm) und 1,72 mm
  (PrusaSlicer, `rm585/m_prusa/…/vorschlaege`), gemessen mit `luft.py`. Die Zahl ist falsch, und
  sie war der Beleg, dass der Turm nur kurze Bahnen ins Freie legt.
- Archiv und Commit: „Rand- und Bogenfrage gehen in einem Durchgang (`_self_carried`)“ — nur für
  die volle Frage (M2).
- Changelog in allen sechs Sprachen: „eine weit gespannte flache Decke behält ihre“ — eine um 2–5°
  geneigte nicht (S1); „Solidon verlangt für sie keine Stützen mehr“ — für tiefe Bögen nicht (L1).
- Archiv: CPU-Zeit `support_need` „neu 111,5 und 138,1 s, alt 131,4 und 141,0 s“; gemessen mit
  gleichem Kern im Wechsel: neu +3,5 % (Eiffelturm 175,1 → 181,2 s im Mittel), Drache +0,5 %.
- Regel `druckrat.md` und Begründung tragen die Prämisse „Ein Bogen trägt sich wie ein Gewölbe“
  — gedruckt wird er als zwei Kragarme (S1); nach dem Fix neu fassen.

### L3 (leicht) — Docstrings nennen die Bogenstreifen nicht

`advise.py:819–826` (`SupportNeed.overhang`, `.patch`, `.piece`: „ohne Kanaldecken und Ränder“),
`analysis.py:3112–3113` und `:3158–3159` (`without` von `total_overhang` und
`largest_overhang_patch`: „die Kanaldecken … und die Ränder“), `analysis.py:4024–4026` (`closes`:
„Rand-, Bogen- und Kanalfrage stellen sie“ — die Randfrage stellt sie nicht). **Fix:** Bogenstreifen
nennen, Randfrage streichen.

## Neue Punkte (außerhalb des Diffs, Vorschlag für das Register)

- **Kanaldecken mit derselben Prämisse.** Ein flacher Bogen (Sehne 36, Stich 3) auf einer
  auskragenden Platte: 19 Scheitelstücke gelten in **beiden** Ständen als Kanal, die Übergabe
  sperrt den Raum darunter (`channel_space`: x −0,4…24,4, z 34,8–37,8 mm,
  `support.block_channels=True`). `_Ceilings.closes` beantwortet für Kanal und Bogen dieselbe
  Frage „trägt sich, weil sie schließt“ (Zwilling); der Kragarm-Fix aus S1 gehört an beide Stellen.
  Sonde `kanal_bein.py`.
- **`support_need` dauert an großen Körpern Minuten** (gleich in beiden Ständen, 0,2 mm, 45°, CPU):
  Eiffelturm 171–182 s, Drache 463–474 s. Im Profil (`profil_bedarf.py`, Eiffelturm) gehen 175 von
  206 s Wand in `_model_support`, vor allem in den Säulenabstieg (`descend`, `_material_cross` je
  Stück, 17 099 Aufrufe, und `material_at`). Gebiet Kanalfrage, Python-Schleife je Stück im heißen
  Pfad (Regel „Gebündelt rechnen“).

## Geprüft ohne Befund

- **Spitzbogen** (Sehne 40, Halbmesser 40 und 24): in beiden Ständen ohne Stütze, Streifen höchstens
  0,34 / 0,88 mm, Scheitel steil — richtig.
- **Loch im Scheitel** (Rundbogen R 20 mit Schlitz 3 mm und 0,6 mm bis oben): zwei Konsolen,
  `closes` nein, kein Bogenstreifen; Feld 53,5 / 63,1 mm², in beiden Ständen ohne Stütze (Verhalten
  unverändert, nicht Teil des Prüflings).
- **Bein auf einem Überhang** (Wand mit Bogen auf einer Platte, die 64 mm frei auskragt): Stützbedarf
  bleibt (Platte 510 mm², Brücke 64,5 mm), die Bogenstreifen verdecken die Platte nicht, Rat gleich.
  Der flache Bogen darauf läuft in beiden Ständen über die Kanalfrage (neuer Punkt).
- **Gekippt**: Wand 20° und 35° nach vorn geneigt — in beiden Ständen ohne Stütze, unverändert;
  in der Ebene gedreht: Rundbogen 15° wie der Rundbogen, Korbbogen 20° kippt wie S1 (Streifen 2,49 mm).
- **Dünn**: Bogen in 0,6 mm Wand unverändert ohne Stütze; Rippe 1 mm × 8 mm wie der Rundbogen
  (Streifen 1,45 mm), Rippe 0,6 × 3 mm unverändert.
- **Nebeneinander**: drei Rundbögen R 8 — ja → nein, Streifen ≤ 0,91 mm, richtig; drei flache
  Segmente 20/1,5 bleiben „ja“, weil ihre drei obersten Schichten zusammen 167 mm² ergeben
  (`worth_support`-Summe, bestehende Regel).
- **Gegenfälle**: Rundbogen R 20 (8/12 mm Tiefe) und R 30 ohne Stütze, flache Decke mit Stütze; am
  Eiffelturm Stützbedarf nein statt ja, Feld 0,5 statt 360,3 mm², Summe 28,3 statt 388,6 mm²,
  2 504 Bogenstreifen — wie im Archiv.
- **Determinismus**: zwei unabhängige Läufe (`k2`, `k3`) über 27 Körper gleich; übersetzter Kern
  und NumPy-Weg gleich (Worktree gegen Export mit `.pyd`, 32 Körper).
- **Merker und Nebenläufigkeit**: `_closing_answers` hängt nur an den Schichten, beide Fragesteller
  nehmen `_material`; gleichzeitiges Füllen des geteilten Dicts rechnet höchstens doppelt.
- **Abbruch**: `_ledges` prüft je Decke wie zuvor; die Schließfrage selbst war schon in
  `_model_support` nicht abbrechbar.
- **Ausrichten**: Für die drei Wände schlägt der Prüfbericht in beiden Ständen vor, sie hinzulegen
  (`orient.saves_support`, 100 %); S1 trifft, wer aufrecht druckt — Turm, Haus, Brücke.
- **Unterlagen**: Karte 19,6 KB, Regel 10,7 KB (Budgets 25/30 KB); Register und Archiv nach Format;
  Changelog in sechs Sprachen, `test_changelog.py` grün.

## Regeldurchgang (`/regelcheck`)

Regel 1: kein Qt im Diff. 2–4: keine Op berührt. 5: `vaults` ist eine neue Kernfunktion ohne
§9-Vertrag. 6: kein `==` auf Fließkomma, Millimeter durchgehend. 7/8: keine neue Zahl — aber
`LEDGE_REACH` bekommt eine zweite Bedeutung (je Streifen statt je Decke) und ersetzt dort den
wirksamen Überhangwinkel (S1, Bauplan §28.3). 9–13: nicht berührt. 14: Analyse- und G-Code-Zahlen
im Archiv getrennt benannt. 15/22: keine Abhängigkeit. 16, 18, 19, 21: nicht berührt. 17: keine
neue Ausnahme. 20: kein Oberflächentext. Bezeichner englisch, Docstrings deutsch mit Umlauten.

## Messungen

Alle Skripte und Ausgaben unter `scratchpad\rv585\`; gepinnt, Exit-Code im Skript.

| Lauf | Inhalt | Exit |
|---|---|---|
| `k2.sh`, `k3.sh` | 32 Prüfkörper alt/neu bei 0,2 mm, 8 davon bei 0,08/0,12/0,28 mm | alle 0 |
| `k4.sh`, `k5` | Prototyp gegen neu (32 Körper gleich); Rundbogen in 80 mm Wand | 0 |
| `s1.sh` | Eiffelturm (864 Schichten, 41 s CPU) und Drache (650 Schichten, 60 s CPU) geschnitten | 0 / 0 |
| `t1.sh`, `t2.sh`, `t3.sh` | Zeiten `support_need`, `overhang_findings`, `ledges`, `located_warnings` im Wechsel | alle 0 |
| `p1`–`p3.sh` | Profile Rand-/Bogenfrage und Stützbedarf | 0 |
| `m1.sh` | 11 Mutationen × 269 Fälle (siehe M1) | 0 bei grünen, 1 bei roten Mutanten |
| `mx.sh` | `matrix_unit.py`: Pultdecke, Flachbogen, Rundbogen × Elegoo CC2 / Prusa MK4S, alt/neu | alle 0 |
| `l1`–`l3.sh` | `luft.py` an 12 G-Codes | alle 0 |
| `sa*.sh`, `b1.sh`, `r1.sh`, `a1.sh` | Streifenart, Bilder, Rat am Drachen, Ausrichten | alle 0 |
| `v1.sh` | am Worktree: `test_slice_findings`, `test_advise`, `test_print_findings`, `test_roadmap`, `test_changelog`, `test_directory_docs`, `test_wording` | 1: 369 passed, 4 skipped, 6 failed — alle 6 `rendered` (Handbuchseiten, `make_manual.py`), nicht vom Diff |
| `v1.sh` | `ruff check`, `ruff format --check` (geänderte Dateien), `mypy` (374 Dateien) | 0 / 0 / 0 |

## Urteil

**Nicht landen.** S1 ist eine falsche Entwarnung, belegt an der Analyse, an zwei echten Slicern
(12–27 m Stütze → 0 m bei Kragarmen bis 1,7 mm) und an den Flügelhäuten des Drachen. Dazu M1
(die schützende Grenze ist ungetestet) und M2 (Prüfbericht am Eiffelturm 35 s CPU teurer,
bündelbar ohne Ergebnisänderung). Nach den Fixes ist eine **Nachprüfung nötig** (ein schwerer, zwei
mittlere Befunde), Schwerpunkt: Kragarm-Grenze an den Körpern aus S1 und der Messreihe, Eiffelturm
und Drache, Tests mit Gegenprobe.
