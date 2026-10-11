# Nachprüfung RM-585 — Bögen, die sich zwischen ihren Beinen schließen

Prüfling: Worktree `F:\sl-boegen`, Zweig `einstellungen/boegen-rm585`, Stand `acc6283d5`
(welle3 `a97c63add` enthalten). Erstreview `review_rm585.md` (Stand `d176bc5ca`), Behebungen
`b271ffeaa`, `02d3d7db7`, `cfb3416bd`, `7aca67dda`, Merges `eb7b4edc5`, `acc6283d5`.
Reviewer: solidon3d-review. Scratch: `scratchpad\rv585n\`.

Stand: **abgeschlossen** (12:00). Urteil: **nicht landen** — N1 und N2 schwer, N3 mittel, N4–N7
leicht (Begründung unter „Urteil“).

## Vorgehen

- Diff gegen welle3 (`git diff a97c63add acc6283d5`, 15 Dateien, +1192/−70) vollständig
  gelesen, dazu `_Ceilings` (`closes`, `_spans`, `_gap`), `_carried`, `_model_support`
  (Kanalmehrheit), `_ledges`, `support_need`, `_from_spans`.
- Stände als Export mit demselben übersetzten Kern (`_chain.pyx` in allen Ständen gleich):
  `rv585n\alt` = `a97c63add` (welle3, Merge-Basis; `c4b6f3afa` ist Vorfahr), `rv585n\neu` =
  `acc6283d5`; Tests und Mutationen an einem eigenen Export `neu_t`. Der Worktree blieb
  unverändert (`git status` leer).
- Prüfkörper (`grenze.py`, gebaut wie `gate` im Test): 39 Körper × 0,08/45, 0,12/55, 0,2/45,
  0,2/60, 0,28/45, 0,28/60, alt gegen neu (`out/g1_*.jsonl`, Tabelle `out/tab_g1.txt`).
- Echter Slicer: `tools/matrix_unit.py` (Druckdialog-Weg, ElegooSlicer, Centauri Carbon 2,
  „0.20mm Standard“, Analysewinkel 60°, Wand 0,84 mm, aufrecht), freie Bahnen mit `luft.py`
  des Erstprüfers (Bahnmitte gegen den Querschnitt der Schicht darunter, frei ab halber
  Bahnbreite).
- Alle Läufe gepinnt (`start /affinity FFFFF0FF`), Exit-Code im Skript (alle 0, wo nicht
  anders genannt). Ein Hilfsaufruf mit `python -` und leerem Heredoc hing kurz (10:16); der
  eigene Prozess wurde per PID beendet, gerechnet hatte er nichts.

## Befunde

### N1 (schwer) — Ein „gefasster“ Streifen zählt nicht, auch wenn er 81 mm frei spannt: die Kumiko-Schale aus dem Korpus verliert ihre Stütze

`analysis.py:4610–4642` (`_Ceilings._held_twice`) mit `analysis.py:4565–4566` (`_arch`), dem Docstring `:4532–4536` und
`advise.py:967–968` (Brückenregel über `layer.bridge_width`).

Der Korpuslauf am generischen Drucker (Startregel 45°, `korpus45.sh`, `out/k45_*`) zeigt außer
dem Eiffelturm vier Modelle, denen der Prüfling die Stütze ganz nimmt. Eines ist eine Fehlentwarnung
in voller Größe: `kumiko_elongated-hexagon_shell_w150.stl` — welle3 „Stützen nötig“, Gitter mit
drei Trennlagen; Prüfling „Stützen nötig: nein“, kein Vorschlag. Ursache (`kumiko_stueck.py`,
Bild `bilder\kumiko_stueck.png`): Bei z 93,55 beginnt die Kumiko-Platte als **ein Stück von
3 587 mm²** (448 Löcher, x −40,6 … 40,8), das nur links und rechts auf den Seitenwänden aufliegt;
der fernste Punkt liegt **40,6 mm** vom Material darunter. Es ist nicht die oberste Schicht
seiner Decke (1 380 Stücke, z 86,75–94,95), `_held_twice` sagt „zwischen zwei Auflagen“ —
richtig —, und damit gilt es als Bogenstreifen, der sich trägt. Wie weit er spannt, soll laut
Docstring von `arch` die Brückenregel seiner Schicht fragen; die misst `bridge_width = 1,49 mm`,
denn frei sind nur die schmalen Gitterstäbe. Damit fehlen 3 587 mm² im Feld, und keine Regel
fängt eine 81 mm weite Gitterplatte in der Luft. Im ElegooSlicer ohne Stütze (Drucklage wie
im Korpus, `out/luft45_kumiko.log`, z 92,5–96) liegen dort 10,4 m Bahn frei, Läufe bis 82 mm
lang und bis 41,2 mm neben dem Material darunter, 597 Kragarme über 1 mm. Am CC2-Weg (60°)
bleibt die Stütze in beiden Ständen; betroffen sind der generische Drucker und jede Einstellung,
an der die Platte so gruppiert wird.

Die übrigen drei Modelle, die bei 45° die Stütze verlieren (`korpus_boegen.py`,
`out/kb45.jsonl`, G-Code ohne Stütze `out/luft45_*`): `obj_12_Gövde75` (Minigolf) — 28 Streifen
von zusammen 349,5 mm², die höchstens 0,13 mm über die Zugabe kragen, eine Fläche knapp unter
45°: zu Recht ohne Stütze. `garden-hose-holder` — 1 286 Bogenstreifen, 134 kragen mehr als eine
Bahnbreite über die Zugabe (bis 1,98 mm), keiner davon über 7,6 mm lang frei. `the-over-
engineered-backpack-wall-mount-v2` — 62 Streifen bei z 22,4–23,0 kragen 1,32 mm über die
Zugabe; im ElegooSlicer ohne Stütze liegen dort Wandbahnen 1,30 mm (3 Bahnbreiten) frei, je an
beiden Enden gefasst über bis 12,5 mm — kurze Brücken wie in N2.

**Fix:** `_held_twice` verlangt außer der Lage zwischen zwei Auflagen, dass kein Punkt des
Streifens weiter als eine halbe meldbare Brücke (`SPAN_INTERESTING / 2`) vom Material darunter
liegt — dieselbe Frage wie `_hangs_on`, nur mit dieser Weite. Im Experiment (`neu_fix8`, eine
Zeile in `_held_twice`, `out/f8.jsonl`, `out/kb45_f8.jsonl`): Kumiko-Schale bei 45° wieder
„Stützen nötig“ (Feld 3 587 mm²); Eiffelturm bei 0,2/45 unverändert (Feld 0,5 mm², dieselben
2 504 Bogenstreifen, 11 232 Kanalstücke) und bei 0,2/60 ohne Stütze; alle 14 Prüfkörper bei
0,2/45 und 0,2/60 wie der Prüfling, R 20 in 20 mm Wand ohne Stütze (L1 bleibt). Die strengere
Fassung über `_supported_span ≤ SPAN_INTERESTING` (`neu_fix7`) gibt dem Eiffelturm bei 45° die
Stütze zurück (seine gefassten Streifen von 110,7 mm²) und taugt nicht; `neu_fix6` aus N2 fängt
die Kumiko-Platte ebenfalls (`out/kb45f6_kumiko.log`: Stützen nötig, Feld 3 587 mm²).
Test: die Kumiko-Platte nachgebaut (Gitterplatte 80 mm zwischen zwei Wänden, darunter eine Decke,
die sie zur selben Decke macht) braucht Stützen; der Eiffelturm nicht.

### N2 (schwer) — Die neue Grenze entwarnt Decken zwischen 11,3° und gut 17°; in tiefen Wänden und Häuten laufen ihre Bahnen 20 mm frei

`app/core/slice/analysis.py:3869` (`CANTILEVER_LAYERS = 4.0`), `:4601–4608` (`_carries`),
mit `advise.py:967–968` und `:2611` (`hanging_vaults` ruhig für die Brückenregel).

Die S1-Körper des Erstreviews behalten ihre Stütze in allen sechs Einstellungen (Pultdecke
40/3 und 80/6, Flachbogen 40/3, 60/8, 80/10, Korbbogen 60/12, Satteldecke 40/3, Decke 2° und
5°) — S1, wie gemeldet, ist behoben. Die neue Grenze lässt aber jeden Streifen tragen, der je
Schicht bis Zugabe + 4 Schichthöhen kragt, also jede schließende Decke steiler als 11,3° (45°)
bzw. 9,9° (60°), gleich bei welcher Schichthöhe. Je Schicht sind das an der Grenze 1,0 mm
(0,2/45), 1,15 mm (0,2/60), 1,4 mm (0,28/45) und 1,6 mm (0,28/60) — die Außenbahn liegt dann
rechnerisch 1,9 bis 3,3 Bahnbreiten neben der Schicht darunter.

**Analyse** (alt → neu, Stützen nötig; `out/tab_g1.txt`): Pultdecke 40 mm unter 12°, 15°, 20°,
Satteldecke 12° und 20°, eine 1,5 mm dünne Haut zwischen zwei Knochen unter 15°/20° (ohne
Inseln) — welle3 verlangt bei 0,2/60 überall Stütze (Feld 116–420 mm², Pultdecke 12° in 20 mm Wand 495 mm²), der Prüfling bei keiner.
Am Kundenweg (Matrix, CC2) ebenso: `needed: false`, keine Vorschläge, 0 m Stütze.

**Echter Slicer ohne Stütze** (ElegooSlicer, 0,2 mm, Bahnbreite 0,42 mm, `out/luft_*.log`):

| Körper (neu: keine Stütze, welle3: Stütze) | freie Bahn je Schicht, größter Abstand | Länge des freien Laufs | freie Bahn gesamt |
|---|---|---|---|
| Pultdecke 12°, Wand 8 mm | **0,73 mm** (1,7 Bahnbreiten), „overhang wall“ | 8,5 mm, beidseitig gefasst | 0,65 m |
| Satteldecke 12°, Wand 8 mm | **0,73 mm** | 8,5 mm | 0,66 m |
| Pultdecke 15°, Wand 8 mm | **0,54 mm** (1,3) | 8,2 mm | 0,43 m |
| Pultdecke 12°, Wand **20 mm** | **0,73 mm** | **20,5 mm** | 1,67 m |
| Pultdecke 15°, Wand **20 mm** | **0,54 mm** | **20,2 mm** | 1,06 m |
| Haut 15° zwischen zwei Knochen, 20 mm tief | **0,54 mm** | **20,2 mm** | 1,06 m |
| Pultdecke 20°, Wand 8 mm / Haut 20° | 0,34 mm (0,8) | 7,8 / 19,8 mm | 0,56 / 1,42 m |
| *Gegenfall* Rundbogen R 20, Wand 8 mm (Erstreview) | Kragarm 0,41 mm; Scheitel gefasst 1,97 mm über 3,5 mm | | 0,26 m |
| *Gegenfall* Rundbogen R 20, Wand 20 mm | Kragarm 0,41 mm über 18,5 mm; Scheitel 1,98 / 3,5 mm | | 0,67 m |
| *Gegenfall* Rundbogen R 30, Wand 8 mm | Kragarm 0,83 mm über 13,1 mm (Scheitel, „bridge“); gefasst 2,42 / 4,4 mm | | 0,41 m |

Bei 0,28 mm (dieselbe Übergabe, nur `layer_height=0.28`, `elegoo_variante.py`; `out/luft028_*`)
wächst der Abstand mit der Schicht: Pultdecke 15° gefasst **0,84 mm** (2 Bahnbreiten) über
8,8 mm — der Prüfling verlangt bei 0,28/60 keine Stütze —, Pultdecke 12° in 20 mm Wand gefasst
**1,11 mm über 21,3 mm** (2,6 Bahnbreiten; bei 0,28/45 ohne Stütze, bei 0,28/60 wegen N4
zufällig mit). Die drei flachen Segmente 20/1,5 (bei 0,28/60 ohne Stütze) legen am Scheitel
einen Kragarm von 1,11 mm über 19,7 mm („bridge“) — dieselbe Art wie die 0,83 mm des R 30 bei
0,2 mm, die der Scheitel-Ausnahme zugutekommt.

Zwischen 11,3° und gut 17° liegt jede Außenwand-Bahn ganz neben der Schicht darunter (Abstand
größer als eine Bahnbreite, am Rundbogen R 20 sind es 0,41 mm) und hält nur an ihren Enden. In
einer 8 mm tiefen Wand ist das eine kurze Brücke; in einer 20 mm tiefen Wand oder Haut sind es
20 mm freie Bahn je Schicht — so weit, wie `SPAN_INTERESTING` (15 mm) eine Decke meldet. Die
Brückenregel schweigt trotzdem: Die Streifen hängen an einer Seite, gelten als
`hanging_vaults` und sind für sie ruhig (L1-Fix). Die Matrix zeigt es: Pultdecke 12° in 20 mm
Wand `bridges_over: 41, bridge_max: 20.0`, aber `needed: false`. Ob solche Decken sauber
drucken, sagt nur ein Druck; nach dem Maßstab dieses Auftrags (Kragarm je Bahn ≲ eine
Bahnbreite) tun sie es nicht, und welle3 verlangte für sie Stütze.

Mit Stützen im Profil (CC2, PLA, `style=auto`, `placement=everywhere`; `rat_an.py`,
`out/r1.log`) rät welle3 an Pultdecke 12° (8 und 20 mm Wand) und Haut 15° „Stützen nötig“,
`placement=build_plate`, an der 20-mm-Wand dazu `slice.long_bridge`; der Prüfling rät an allen
dreien `support.style=none` „Nichts an diesem Teil braucht eine Stütze.“ und meldet keine Brücke
mehr. Wer den Rat übernimmt, schaltet die Stütze des Slicers ab.

Am Drachen trifft dieselbe Lücke die rechte Flügelhaut (`bruecke_drache.py`, Bild
`bilder\drache_bruecke_z65.png`): welle3 meldet bei z 65,3 `slice.long_bridge` 16,3 mm; der
Streifen dort (17,9 mm², 20 mm lang, 1,07 mm je Schicht bei 0,2/45) ist jetzt ein hängender
Bogenstreifen, der Hinweis fällt weg. Am Drachen bleibt die Stütze trotzdem an (Inseln); ein
Teil mit solchen Flügeln ohne Inseln bekäme die Entwarnung.

**Die Herleitung trägt die Zahl nicht** (Regel 8): „zwei Bahnen an der Regelschicht, die halb so
hoch ist wie die Bahn breit“ rechnet eine Breite in Schichthöhen um. Die Bahnbreite kennt der
Schnitt (`result.bridge_from`, „am Drucker gemessen“); vier Schichthöhen sind bei 0,28 mm
1,12 mm statt 0,84 und bei 0,08 mm 0,32. Gewählt wurde die Einheit, damit eine flache Decke bei
feinen Schichten nicht durchgeht — die Grenze ist damit ein Neigungskriterium (11,3°/9,9°),
kein Kragarm-Kriterium, und für 12–17° bei 0,2 mm zu weit.

**Zweite Tür (`_held_twice`):** Ein Streifen, der an einer Seite hängt, gilt als „zwischen zwei
Auflagen“, wenn er schmaler als etwa (Zugabe + 0,1 mm)/0,75 ist — die gehaltene Kante samt der
Stummel von `OVERHANG_MARGIN` an beiden Enden, gepuffert um `closing`, deckt dann
`CEILING_SPANNED` (75 %). Heute liegt das innerhalb von `_carries`; wer die Grenze verschärft, merkt es
aber: Mit einer Kragarmgrenze von Zugabe + 1 Bahnbreite (Experiment `neu_fix2`) blieb die
Pultdecke 12° bei 0,2/60 „selbsttragend“ — 41 von 42 Streifen über `_held_twice`.

**Experimente** (nur Scratch, Kopien von `neu`; `out/f1_*`–`out/f6_*`; Bögen, Grenzkörper und
Eiffelturm bei 0,2/45, 0,2/60, 0,28/60, teils 0,08/45; Stütze nötig):

| Fassung | bleibt ohne Stütze | bekommt Stütze (wie welle3) | entwarnt weiter |
|---|---|---|---|
| Prüfling: Zugabe + 4 Schichthöhen | alle Bögen; Pult/Sattel/Haut 12–20° | S1-Körper | — |
| `neu_fix2`: Kragarm Zugabe + 1 Bahnbreite | R 20 (8 mm), Spitzbogen, Arkade, Eiffelturm (45° und 60°) | Pult/Sattel 12° bei 0,2/45; R 30, R 35 bei 0,2/45; R 20 in 20 mm Wand bei 0,2/45 und 0,28/60 | Pult/Sattel 12° bei 0,2/60 (41 von 42 Streifen über `_held_twice`) |
| `neu_fix3`/`neu_fix4`: dazu `_held_twice` mit zwei getrennten Randstücken bzw. ungepufferter Hülle | R 20 (8 mm), Spitzbogen, Arkade, Eiffelturm bei 60° | Pult/Sattel 12° (8 und 20 mm) bei 45° und 60°; R 30 bei 0,2/45, R 35 bei 60°, R 20 in 20 mm; **Eiffelturm bei 0,2/45** (Feld 191 mm², 152–156 kragende Scheitel) | Pult und Haut 15° bei 0,2/60 |
| `neu_fix6`: ein Streifen, dessen Teil jenseits Zugabe + 1 Bahnbreite länger als `SPAN_INTERESTING` läuft, gehört zum Scheitel | R 20 (8 mm), **R 30, R 35**, Spitzbogen, Arkade, Flachbogen 40/8, **Eiffelturm (45° und 60°)**; Pult/Sattel 12° in 8 mm Wand (8,5 mm kurze Läufe) | **Pult 12° in 20 mm Wand bei 45° und 60°**, Pult 15° in 20 mm und Haut 15° bei 0,2/45; R 20 in 20 mm Wand | Pult und Haut 15° bei 0,2/60 (0,40 mm über der Zugabe, im G-Code 0,54 mm) |

`_held_twice` ist tragend für den Eiffelturm bei 45° — jede einfache Verschärfung dort
(`neu_fix3`/`neu_fix4`) gibt ihm die Stütze zurück. Am nächsten an den Maßstab dieses Auftrags
kommt `neu_fix6`: Er hält alle verlangten Gegenfälle (R 20, R 30, Spitzbogen, Eiffelturm) und
schließt die 20-mm-Läufe der Pultdecke bei 45° und 60°; er kostet L1 (R 20 in tiefer Wand, wie
welle3) und lässt 15° bei 60° offen. Keine Fassung schließt das Band, ohne einen Gegenfall
zurückzugeben — die Grenze braucht einen Entwurf und einen Druck.

**Fix:** Ein Streifen trägt sich als Kragarm nur, solange seine Außenbahn höchstens eine
Bahnbreite (`bridge_from / 2`, am Rundbogen R 20 im G-Code 0,41 mm) neben der Schicht darunter
liegt; weiter Kragendes ist eine Brücke längs der freien Kante und gehört zum Scheitel, der quer
zwischen den Flanken gemessen wird (Richtung `neu_fix6`). Tests: Pultdecke 12° in 20 mm Wand bei
0,2/45 und 0,2/60 und Haut 15° behalten Stütze; Eiffelturm, R 20/R 30, Spitzbogen bleiben ohne.
Changelog und Regel danach am Ergebnis („schwach geneigte Decken behalten ihre“ stimmt heute für
12–17° nicht; „auch in einer tiefen Mauer“ gilt nach `neu_fix6` nicht mehr). Wer die heutige
Grenze behalten will, belegt sie vor dem Landen mit einem Druck (Pultdecke 12° und Haut 15° in
20 mm Tiefe, 0,2 mm, CC2), wie der Bericht des Bauagenten selbst vorschlägt.

### N3 (mittel) — Der Kanal-Zwilling entscheidet je Decke nach Mehrheit: am Drachen kippt bei 45° die linke Flügeltasche, die rechte behält ihren kragenden Scheitel unter der Sperre, und am generischen Drucker fällt die Sperre ganz weg

`analysis.py:5073–5085` (`_model_support`, `kragged` in der Flächenmehrheit).

Gemessen am gesicherten Schnitt (0,2 mm, 45° — der Winkel des generischen Druckers;
`kanal_lage.py`, `kanal_bild.py`, `out/kanal_*.json`, Bild `bilder\drache_kanal_verloren.png`):

| | welle3 | Prüfling |
|---|---|---|
| Kanalstücke / Fläche | 1 836 / 538,6 mm² | 1 795 / 413,9 mm² |
| gesperrte Säulen | 70 | 29 |
| Stützbedarf, offen auf dem Modell | ja, 300,4 mm² | ja, 219,9 mm² |

Alle 41 verlorenen Säulen (124,8 mm²) liegen in **einer** Decke: der Tasche unter der **linken**
Flügelhaut an der Flügelwurzel, z 59,5–65,7, Säulen bis 26,4 mm hoch (Auflage auf dem Modell
bei z 38,9–62,1). Sie kippt wegen zwei kragender Scheitelstreifen von zusammen 25,6 mm²
(z 62,1/62,9), beide Kanalstücke. Die Tasche unter der **rechten** Flügelhaut hat acht kragende
Scheitelstreifen (65,2 mm², z 62,9–64,7), davon einer im Kanal (8,4 mm², z 63,5): Sie bleibt
Kanal, und dieser Streifen bleibt gesperrt, obwohl er nach der eigenen Bogenfrage weiter kragt,
als er trägt. Links fällt die Sperre über 124,8 mm² Taschendecke wegen 25,6 mm² Scheitel, rechts
bleibt sie samt Scheitel. Die Mehrheit entscheidet über die ganze Decke, nicht über die Stücke,
die Stütze brauchen, und sie liegt knapp: Links trennten Kanal- und Außenfläche weniger als
51 mm². Kiefer und Kinnstacheln sind nicht betroffen (dort geht kein Kanalstück verloren).

**Am Kundenweg ändert sich am Drachen nichts** (Matrix, ElegooSlicer, CC2, Winkel 60°): Die
Übergabe-3MF ist in alt und neu **bytegleich**, der Sperrkörper ebenso (4 439 mm³); Stütze im
Sperrkörper 1,73 / 1,73 m, Stütze gesamt 514,7 / 515,0 m (Streuung des Slicers bei gleicher
Eingabe). Im Korpuslauf (CC2-Weg) dasselbe: Drache `next.3mf` 698 → 672 Kanalstücke, Sperrvolumen
und Rat gleich. Bei 50° (Prusa Mini/XL, Sovol SV06; `sonde_kanalraum.py`, `out/kr_*.log`) ist
alles gleich (1 384 Kanalstücke, 40 Säulen, 3 085 mm³), bei 55° (MK4S) 1 018 → 962 Kanalstücke,
in beiden Ständen keine Säule gesperrt. Der Schwund trifft den **generischen Drucker**
(Startregel 45°): mit den Werten der Übergabe am Drachen in Drucklage Sperrraum 8 227 → 4 819 mm³
(70 → 29 Säulen, `out/kr_*_45.log`), am Drachen, wie ihn der Korpus importiert (`next.3mf`),
8 589 → **0 mm³** — dort schlägt Solidon die Kanalsperre gar nicht mehr vor (`out/k45_vergleich.txt`).
An den Druckern der Liste ergibt sich weder Stütze, die nicht mehr herauskommt, noch fehlende
Stütze an Kiefer, Kinnstacheln und Flügelbögen; am generischen dürfen Bäume in Taschen, die
welle3 sperrte (im Slicer nicht gemessen — keiner schneidet mit 45°).

**Fix:** Die kragenden Scheitelstreifen nicht in die Mehrheit rechnen, sondern wie Stücke, die
selbst Stütze brauchen, aus der Sperre aussparen (`spared`/`open_columns`, „Ausgespart wird, was
selbst Stütze braucht“): Die Decke bleibt Kanal, wo sie es nach welle3 war, und nur die Scheitel
bekommen Stütze. Test: dieselbe Tasche gespiegelt — beide Seiten gleich; der flache Bogen auf der
Platte behält seine Stütze.

### N4 (leicht) — Ob eine Decke Bogen wird, kippt an der Schließfrage, nicht an der Neigung

`analysis.py:4735–4793` (`_Ceilings._closes`, aus welle3, jetzt Tor der Bogenfrage).

Dieselbe Decke wechselt mit Schichthöhe und Winkel zwischen „Stütze“ und „keine“, ohne
Ordnung in der Neigung (`out/tab_g1.txt`, Prüfling): Pultdecke 0,2/45 — 11° ja, 12° nein, 13°
nein, 15° nein, 20° nein, 30° ja; 0,2/60 — 12° nein, **13° ja**, 15° nein; 0,28/45 — 12° nein,
**15° ja**, 20° nein; 0,28/60 — **12° ja**, 13° nein, 15° nein, **20° ja**. Satteldecke 0,2/60 —
12° nein, **15° ja**, 20° nein; 0,28/45 — 12° nein, 15° ja, 20° ja. In allen untersuchten
Ja-Fällen ist die Ursache dieselbe (`warum.py`, `out/w1.log`): `closes` verneint (Pult 15° bei
0,28/45: 38 Stücke, „schließt False“; bei 0,28/60: „schließt True“, 37 von 37 tragen), oder die
Satteldecke zerfällt in zwei Decken, die je an einer Seite hängen. Die Richtung ist vorsichtig
(Stütze bleibt), aber der Kunde sieht den Rat mit der Schichthöhe springen. Fix: mit N2 Tests
über eine Neigungsreihe (z. B. 12/13/15/20° bei 0,2/45, 0,2/60, 0,28/45), die eine monotone
Antwort verlangen; die Schließfrage dort robust machen, wo ein Splitter an der hohen Wand
(`part.area > closing * closing`) den zweiten Halt verwirft.

### N5 (leicht) — Zwei Docstrings nennen die Bogenstreifen nicht (Rest von L3)

`ModelSupport.tallest_column` (`analysis.py:3515–3518`, „ohne Ränder und Kanaldecken“; gerechnet
wird im Hauptzweig ohne `rims | vaults`, `:5120`, `:5230`) und `span_beside`
(`analysis.py:3621–3622`, „Kanaldecken und Ränder“; die Aufrufer geben jetzt auch hängende
Bogenstreifen mit). Der Zweig ohne Auflage auf dem Modell (`:4989–4992`) rechnet den Stamm noch
ohne Bogenfrage; die Zahl ändert das nicht, weil die oberste Schicht jeder Bogendecke mitzählt
und höher liegt als ihre Streifen. Fix: Docstrings nachziehen.

### N6 (leicht, Zwilling) — Der Halt neben einem Scheitel wird ein zweites Mal hergeleitet

`analysis.py:4686–4720` (`_crown_spans_short`) wiederholt Zeile für Zeile die Halt-Rechnung aus
`_closes` (`analysis.py:4752–4779`: Fenster je Stück, eigenen Grundriss im Fenster abziehen,
Splitter unter `closing²` verwerfen, um die Reichweite aufweiten, vereinigen). Der M2-Fix musste
schon an beiden Stellen nachgezogen werden; ändert sich die Splittergrenze an der einen, rechnet
die andere weiter mit der alten (`.claude/rules/zwillinge.md`, Klasse „ungewollt“). Fix: eine
Hilfsfunktion `_anchored(members, own, closing)` für beide.

### N7 (leicht) — Zwischen zwei Zuweisungen kann ein Leser „keine hängenden Streifen“ sehen

`analysis.py:4022` (`_self_carried`): `known.arches, known.hanging = found, hanging` setzt
außerhalb des Schlosses erst `arches`, dann `hanging`. Ein zweiter Faden, der dazwischen
`hanging_vaults` fragt, sieht `arches` gesetzt, rechnet nicht, und bekommt aus
`known.hanging or frozenset()` eine leere Menge — Brückenregel und `open_pieces` dann ohne
Ausnahme (vorsichtige Richtung, ungemerkt falsch nur für diesen Aufruf). Fix: erst `hanging`,
dann `arches` zuweisen, oder beide unter `_ANSWERS_LOCK`.

## Befunde des Erstreviews (Punkt 3)

| Befund | Stand | Beleg |
|---|---|---|
| S1 fast flache Decken | **behoben** für die gemeldeten Körper; neue Grenze zu weit (N2) | `out/tab_g1.txt`: alle S1-Körper in sechs Einstellungen mit Stütze |
| M1 Grenze ungetestet | **behoben** | Mutationen unten |
| M2 dreifache Rechenzeit | **behoben**, gegen welle3 gleich oder schneller | Zeiten unten |
| L1 tiefe Wände | **behoben** (R 20 in 16/20 mm ohne Stütze und ohne Brückenbefund; Matrix R 20/20 mm `needed: false`, G-Code Kragarm 0,41 mm) — dieselbe Ausnahme schweigt aber auch bei 12–15° (N2) | `out/luft_rundbogen_r20_t20.log` |
| L2 Belege | **behoben** („0,51 mm“ ersetzt, „ein Durchgang“ nur für die volle Frage, CPU-Zahlen als Stand des Reviews gekennzeichnet); Regel, Docstring und Kommentar sagen weiter „Pult-, Sattel- und Flachbogendecken kragen weiter und bleiben ein Feld“ — für 12–20° falsch (N2) | `.claude/rules/druckrat.md:136`, `analysis.py:3926–3927`, `advise.py:929–931` |
| L3 Docstrings | **behoben** bis auf zwei (N5) | |

**Mutationen** (`mutation.py` am Export `neu_t`, nie am Worktree; Auswahl: die zwölf RM-585-Tests,
37 Fälle, unmutiert grün; `out/m1.jsonl`, `out/m2.jsonl`):

| Mutation | rot |
|---|---|
| `CANTILEVER_LAYERS` 3 | 2 (`r30-0.2-45`, `r30-0.28-45`) |
| `CANTILEVER_LAYERS` 5 / 8 | 3 / 9 |
| Bogenfrage bei jeder Randfrage | 1 (`test_asking_only_for_ledges_does_not_ask_for_arches`) |
| Kanalmehrheit wie welle3 (ohne `kragged`) | 1 (`test_a_flat_arch_over_the_model_is_no_channel`) |
| Brückenregel des Stützbedarfs ruhig auch für gefasste Streifen | 0 in der Auswahl; über `test_slice_findings`, `test_advise`, `test_print_findings` 1 (`test_a_bridge_is_no_channel_because_its_foot_touches_a_wall[0.08]`) |
| Auswahlfilter `asked` in `_vaults` weg | 0 — reine Abkürzung, gleiche Antwort; kein Fund |
| Testzeile `hanging_vaults(result)` im Abbruchtest weg | 1 (`[0]`), siehe Punkt 5 |

Die Grenze ist damit von beiden Seiten an Tests gebunden — an R 30 (enger) und Satteldecke 8,5°
(weiter); eine Decke zwischen 11° und 17° prüft kein Test (N2). Die drei ganzen Dateien liefen im
Export 358 grün, 1 rot (`test_the_stack_tells_which_body_carries_a_fit`: im Export fehlt das
Operationsregister, im Worktree grün — Umgebung, nicht der Prüfling).

**CPU-Zeit gegen welle3** (gesicherte Schnitte 0,2 mm/45°, je Frage ein Prozess, im Wechsel,
zwei Läufe, gleicher übersetzter Kern; `t1.sh`, `out/zeit.jsonl`):

| Frage | Eiffelturm alt → neu | Drache alt → neu |
|---|---|---|
| Hinweise (`located_warnings`) | 4,22 / 4,34 → 4,31 / 4,33 s | 19,6 / 19,6 → 5,6 / 5,5 s ¹ |
| Prüfbericht (`overhang_findings`) | 60,3 / 62,2 → 55,0 / 55,6 s | 0,08 → 0,05 s |
| volle Rand- und Bogenfrage | 6,1 / 7,5 → 11,6 / 11,1 s ² | 6,8 / 7,1 → 11,1 / 14,2 s ² |
| Stützbedarf (`support_need`) | 174,4 / 169,9 → 163,0 / 162,1 s | 461,9 → 468,1 s; gleichzeitig in `k1.sh`: 462,5 → 466,3 s (+1 %) |

¹ Kein Gewinn aus dem Bündeln: Der Hinweis `slice.long_bridge` (16,3 mm, z 65,3) fällt am
Drachen weg (N2), damit die Kanalfrage, die welle3 für ihn stellte.
² Die Bogenfrage ist neu und kommt zur Randfrage hinzu (Profil am Eiffelturm, `profil_bogen.py`:
4,7 s CPU, davon 4,0 s Schließfrage, die die Kanalfrage danach aus dem Merker liest, 0,8 s
`_carries` je Streifen); im Stützbedarf ist sie am Eiffelturm mehr als bezahlt, am Drachen kostet
sie 1 %.
Randmengen gleich: Ränder am Eiffelturm 13 588 (Hash `1f4670935208a54f`), am Drachen
3 783 (`5e3b617b91b74bfd`) in beiden Ständen.

## Korpus (Punkt 4)

`korpus_alle.py`/`korpus_kanal.py` über `F:\3D Dateien` (127 Dateien, 243 Körper, ohne
„3D Drucker“, Dubletten nach Prüfsumme), Centauri Carbon 2 und PLA (Analysewinkel 60°), alt
(welle3) gegen neu, zwei Körper nebeneinander, gepinnt; beide Läufe Exit 0, kein Körper mit
Fehler (`out/korpus_*.jsonl`, `out/korpus_vergleich.txt`).

| Ergebnis | Körper |
|---|---|
| gleich (Stützbedarf, Kanalstücke, Kanalfläche, Sperrvolumen, Rat) | 240 |
| Eiffelturm 18 cm und seine reparierte Fassung: Stützen nötig ja → nein, Rat ohne `support.*` (nur Brim) | 2 — gewollt |
| Drache `next.3mf`: Kanalstücke 698 → 672, Kanalfläche 166,5 → 115,6 mm²; Sperrvolumen und Rat gleich | 1 |

„Offen auf dem Modell“ (`open_area`) sinkt an 16 Körpern, weil Bogenstreifen dort nicht mehr
zählen (Waschschüssel 4 258,6 → 558,1 mm², `grenuttags_hallare_modell_41x47_curved` 108,3 →
0,3, Wedge-Lock 104,7 → 36,3, `parametric-laptop-riser` 5 247,6 → 5 107,9), ohne dass sich ein
Rat ändert. Am CC2-Weg liegt kein Körper des Korpus in den Lücken aus N1 und N2.

**Zweiter Lauf am generischen Drucker** (Startregel 45°, sonst gleich; `korpus45.sh`,
`k45\korpus_kanal.py` mit `KORPUS_DRUCKER=generic-220`; beide Exit 0, kein Fehler;
`out/k45_vergleich.txt`): 233 gleich, 10 verschieden.

| Körper | welle3 → Prüfling | Urteil |
|---|---|---|
| Eiffelturm, zweimal | Stützen nötig → keine | gewollt |
| `obj_12_Gövde75` | Baumstütze → keine | richtig: Fläche knapp unter 45°, Kragarm ≤ 0,13 mm über der Zugabe |
| `garden-hose-holder` | Stütze → keine | 134 Streifen über eine Bahnbreite, frei höchstens 7,6 mm lang; vertretbar |
| `the-over-engineered-backpack-wall-mount-v2` | Stütze → keine | 62 Streifen 1,32 mm über der Zugabe, im G-Code 1,30 mm frei über ≤ 12,5 mm (N2) |
| `kumiko_elongated-hexagon_shell_w150` | Gitterstütze → keine | **falsch: 81-mm-Gitterplatte in der Luft (N1)** |
| `countercleaner`, `chufang` (ein Körper), Marmorbahn (`meshy_ai_…`) | Stütze bleibt; Art wechselt (Baum → normal, Hybrid → Baum, Gitter → normal), Trennlagen fallen weg | Folge der kleineren Restfläche, nicht geprüft |
| Drache `next.3mf` | Kanalstücke 1 847 → 1 775, **Sperrvolumen 8 589 → 0 mm³**, `support.block_channels` fällt weg | N3 |

## Merge mit RM-584 Teil 2 / RM-627 (Punkt 5)

`git diff a97c63add acc6283d5` enthält nur RM-585 — keine welle3-Zeile ging im Merge verloren.
`test_the_report_stops_on_the_way_down_to_the_channel_floor` (`tests/test_slice_findings.py:3689`)
merkt jetzt vor dem Bericht auch `hanging_vaults(result)`. Die Absicht bleibt: Der Bericht soll
im Abstieg der Säulen abbrechen, nicht erst danach. Ohne die Zeile wird `[0]` rot — der Bericht
fragt dann zuerst die Bogenfrage, die je Decke abbricht (`_vaults`), und hält dort; `[1, 10, 40]`
bleiben grün. Die Zeile ist also nötig und folgt dem Muster der Randfrage davor. Dass der Bericht
auch in der Bogenfrage abbricht, prüft kein Test; die Prüfung je Decke steht im Code
(`analysis.py:4141–4142`). Kein Befund.

## Geprüft ohne Befund

- **Gegenfälle** (`out/tab_g1.txt`): Rundbogen R 20 (8 und 20 mm Wand), R 30, R 35, Spitzbogen
  40/24 und 40/40, Arkade 3 × R 8 in allen sechs Einstellungen ohne Stütze; Eiffelturm ohne Stütze
  bei 0,2/45 (Feld 0,5 mm², 2 504 Bogenstreifen) und am CC2-Weg (Korpus, 60°). G-Code ohne
  Stütze: R 20 Kragarm 0,41 mm (8 und 20 mm Wand), R 30 0,83 mm am Scheitel (13,1 mm „bridge“).
  Die letzte Spanne darüber druckt als Brücke (gefasst 1,97 bzw. 2,42 mm über 3,5–4,4 mm).
- **S1-Körper** behalten in allen sechs Einstellungen ihre Stütze (N2, erster Absatz). Die
  Slicer-Matrix des Bauagenten dazu (Pultdecke 40/3 und Flachbogen 60/8 mit derselben Stütze wie
  vor RM-585) habe ich nicht wiederholt.
- **Abbruch**: `_vaults` je Decke, Kanalfrage je Decke; abgebrochen bleibt `known.arches` leer
  und wird beim nächsten Mal gerechnet.
- **Merker**: `_closing_answers` an der Identität des Schichttupels, verdrängt über
  `_keep_recent`; Rand- und Bogenantwort derselben Auswahl einmal (`boegen_immer` rot).
- **Beide Kerne**: Die Bogenfrage rechnet nur mit shapely; RM-585-Tests im Worktree (ohne
  übersetzten Kern) und im Export (mit `.pyd`) grün.
- **Unterlagen**: Changelog 166/159/177/175/177/181 Zeichen, sechs Sprachen, gleiche Stelle;
  `test_changelog`, `test_roadmap`, `test_directory_docs`, `test_text_length` im Worktree 89
  grün, 4 übersprungen, Exit 0. Register: RM-585 aus `ROADMAP.md` ins Archiv verschoben.
- **Druckgleich der Bündelung** (M2): Ränder am Eiffelturm und Drachen in beiden Ständen
  hashgleich; Korpus 240 von 243 Körpern unverändert, die übrigen drei durch RM-585 selbst.

## Regeldurchgang (`/regelcheck`)

1: kein Qt im Diff. 2–4: keine Op berührt. 5: `vaults`/`hanging_vaults` sind neue öffentliche
Kernfunktionen ohne §9-Vertrag (wie `ledges`; kein eigener Befund). 6: Millimeter und
doppelte Genauigkeit, kein `==` auf Fließkomma. 7: `CANTILEVER_LAYERS` ist keine Passtoleranz.
**8: `CANTILEVER_LAYERS` rechnet „zwei Bahnen“ über eine angenommene Schichthöhe in
Schichthöhen um, obwohl der Schnitt die Bahnbreite trägt (`result.bridge_from`) — N2.** 9: kein
Zufall. 10–13: nicht berührt. 14: Archiv trennt Analyse- und G-Code-Zahlen. 15/22: keine
Abhängigkeit. 16–19: nicht berührt. 17: keine neue Ausnahme. 20: kein Oberflächentext; die
Changelog-Zeilen sind Unterlagen. 21: nicht berührt. Bezeichner englisch, Docstrings deutsch
mit Umlauten. Geprüft am gelesenen Diff; ausgeführt wurden Prüfkörper, Matrix, Korpus,
Mutationen und die genannten Testdateien, kein volles Tor.

## Messungen

Alle Skripte und Ausgaben unter `scratchpad\rv585n\`, gepinnt, Exit-Code im Skript.

| Lauf | Inhalt | Exit |
|---|---|---|
| `g1.sh` | 39 Prüfkörper × 6 Einstellungen, alt/neu (`out/g1_*.jsonl`, `out/tab_g1.txt`) | alle 0 |
| `mx.sh`, `e2.sh`, `e3.sh` | Matrix ElegooSlicer CC2 an Pult 12/15/20°, Sattel 12°, Haut 12/15/20°, R 30, Pult 12/15° in 20 mm, R 20 in 20 mm, drei flache Segmente; 0,28 mm über `elegoo_variante.py` | alle 0 |
| `l1.sh`, `e2.sh`, `e3.sh` | `luft.py` an 14 G-Codes ohne Stütze | alle 0 |
| `r1.sh` | Rat mit Stützen im Profil, alt/neu (`out/r1.log`) | alle 0 |
| `w1.sh` | Schließfrage je Decke (`out/w1.log`) | alle 0 |
| `f1.sh`–`f8.sh`, `p1.sh` | Experimente (`neu_fix`, `neu_fix2`–`neu_fix4`, `neu_fix6`–`neu_fix8`, nur Scratch); Profil der Bogenfrage | alle 0 |
| `kb45.sh`, `ks.sh`, `mx45.sh`, `mxk.sh` | Korpusmodelle mit verlorener Stütze bei 45°: Bogenstreifen, Kumiko-Stück, ElegooSlicer ohne Stütze, freie Bahnen | alle 0 |
| `m1.sh`, `m2.sh` | Mutationen am Export `neu_t` | 0 (Treiber); Testläufe wie oben |
| `t1.sh` | CPU-Zeiten alt/neu im Wechsel (`out/zeit.jsonl`) | alle 0 |
| `k1.sh`, `kb.sh`, `b1.sh`, `kr.sh` | Drache: Kanalstücke 45°, Bild, Brücke z 65,3, Sperrraum 50/55° | alle 0 |
| `d1.sh`, `gk.sh` | Drache durch ElegooSlicer alt/neu, Sperrkörper, Stütze im Sperrkörper | alle 0 |
| `korpus.sh` | Korpus CC2 alt/neu, 243 Körper (`out/korpus_vergleich.txt`) | 0 / 0 |
| `korpus45.sh`, `kr45.sh` | Korpus generischer Drucker 45°, 243 Körper (`out/k45_vergleich.txt`); Drache Sperrraum 45° | 0 / 0 |
| Worktree | `test_changelog`, `test_roadmap`, `test_directory_docs`, `test_text_length` | 0 (89 grün, 4 übersprungen) |

## Urteil

**Nicht landen** in dieser Form. S1 aus dem Erstreview ist für die gemeldeten Körper behoben,
M1, M2, L1–L3 sind behoben, der Korpus ändert am CC2-Weg nur den Eiffelturm (gewollt), und
Roberts Drache bekommt am CC2 dieselbe Übergabe wie in welle3 (bytegleich), an MK4S, Mini/XL und
SV06 dieselbe Kanalsperre. Zwei schwere Befunde halten das Landen an:

- **N1** — ein Stück „zwischen zwei Auflagen“ zählt ohne Grenze der Spannweite; die Kumiko-Schale
  aus dem Korpus verliert am generischen Drucker ihre Stütze, obwohl ihre Gitterplatte 81 mm frei
  spannt (G-Code: Läufe bis 82 mm, 41 mm neben dem Material darunter). Der Fix ist eine Zeile in
  `_held_twice` (`_hangs_on(…, SPAN_INTERESTING / 2)`); im Experiment ändert er weder Eiffelturm
  noch einen Prüfkörper.
- **N2** — die Kragarmgrenze ist für Decken zwischen 11,3° und gut 17° zu weit: Ihre Wandbahnen
  liegen 1,3 bis 1,7 Bahnbreiten (bei 0,28 mm bis 2,6) frei, in 20 mm tiefen Wänden und Häuten
  über 20 mm ohne Brückenbefund, und mit Stützen im Profil rät Solidon, sie abzuschalten — welle3
  verlangte Stütze. Keine gemessene engere Fassung hält alle Gegenfälle; am nächsten kommt
  `neu_fix6` (lange freie Streifen gehören zum Scheitel), der nur L1 (R 20 in tiefer Wand) an
  welle3 zurückgibt. Landen kann der Zweig mit N1-Fix und entweder dieser Fassung samt Tests oder
  einem Druck, der die heutige Grenze bestätigt (Pultdecke 12° und Haut 15° in 20 mm Tiefe).

N3 (mittel) gehört mit N2 entschieden — dieselbe Prämisse in der Kanalfrage; N4–N7 sind leicht und können mitgehen oder als Punkte ins Register.
