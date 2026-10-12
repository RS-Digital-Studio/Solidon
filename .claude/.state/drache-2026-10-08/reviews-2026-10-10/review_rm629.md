# Review RM-629: schräger Schacht, Schicht für Schicht

Gegenstand: Worktree `F:\sl-schacht`, Zweig `einstellungen/schacht-rm629`, Diff
`219360698..a675390e6` (Zwischenstand `a6654858b`, fertig `8b9844c7d`, `a675390e6`).
Bauagentenbericht: `berichte-2026-10-10\rm629.md`. Scratch:
`%TEMP%\claude\F--3D-Druck\b00d64ab-ed49-460e-9651-1d89ea000640\scratchpad\rv629\`.
Nichts im Worktree geändert. Sonden laufen aus ausgepackten Bäumen im Scratch (`neu` =
`a675390e6`, `alt` = `219360698`, `merged` = Probemerge mit welle3, je `git archive` von `app`,
`tests`, `tools`, `conftest.py`, `pyproject.toml`, dazu der übersetzte Kern aus dem Hauptbaum,
`_chain.pyx` gleich; `fix`, `fix1b`, `fix2`, `fix6` = Varianten zu den Fixvorschlägen), `app.__file__`
geprüft, auch in den xdist-Arbeitern. Läufe gepinnt `FFFFF0FF`.

Stand: 11:40, abgeschlossen. Alle Läufe fertig, alle Exit 0 außer den Mutanten und dem
verworfenen Prototyp `fix6` (wie genannt).

## Urteil (11:40)

**Nicht — kann so nicht landen, nach den Fixes heute aber schon.** Zwei neue falsche Öffnungen
gegenüber dem Stand davor: Kreise wandern an jeder leicht überhängenden Wand unter einem Dach
seitwärts (Fund 1), und ein schräger Schlitz zählt mit seiner waagerechten statt seiner Weite
quer zur Achse (Fund 6, bei 45° schon 22 mm offen). Für Fund 1 liegt ein kleiner,
gegengeprüfter Fix vor (Variante 1b, Tests grün). Fund 6 braucht eine Entscheidung Roberts
(waagerechte Weite vorerst hinnehmen, benennen, Registerpunkt) — einen Fix bis heute Abend
halte ich nicht für machbar. Fund 3 (scharfe Knicke bleiben gesperrt) ist keine Regression,
aber Regel, Begründung und Archiv versprechen mehr, als der Code hält. Funde 2, 4, 5 sind klein.
Der Merge in welle3 geht mit zwei mechanischen Konflikten in Unterlagen, der Probemerge ist
grün. Was trägt: schräg Ø 34 bis 44°, Zickzack, Wendel, Knick mit Rundung, Kegel — im Becher
richtig offen, im Slicer (Elegoo, Cura) mit Stütze unter dem Sims und freiem Tunnel; echte
Modelle unverändert, Becherzeit gehalten. **Nach den Fixes: Nachprüfung nötig** (Fund 1 ändert
die Modellregel; Fund 6 und 2 je nach Entscheidung).

## Funde

### 1. mittel — Ein Kreis, den eine Wand nur streift, wandert unter dem Dach seitwärts (neue falsche Öffnung)

`app/core/slice/analysis.py:2125–2128` (`_shafts_pass`): Wen Material trifft, dessen Mitten
werden um den vollen Schritt `drift` (Schichthöhe · `SHAFT_DRIFT`) **in jede Richtung**
aufgeweitet, auch wenn die Wand ihn nur um Tausendstel schiebt. Die Enden des getroffenen
Streifens wachsen dabei **entlang** der Wand je Schicht um bis zu einen Schritt. So wandern
Kreise an jeder Wand, die mehr als einige Zehntel Grad überhängt (0,11° noch nicht, 0,57°
schon), unter einem Dach mit bis zu 45° seitwärts — genau das, was der Docstring ausschließt („Ein Kreis, der frei nach oben steigen
kann, wandert nicht: Sonst schöbe er sich unter einem Dach schräg hervor“) und was die
RM-571-Entscheidung „offen über der Säule“ verlangt. Vor RM-629 war jeder dieser Fälle zu.

Beleg `rv629\probe_kriechen.py` → `kriechen.txt`, synthetisch über `_shafts_pass`: Kammer
z 2…30, darüber ein Dach z 30…33 mit einer weiten Öffnung, deren freie Mitten `gap` mm neben
den Startkreisen der Säule liegen; die Wand bei −y neigt sich nach innen und schiebt die Kreise
in +y, die Öffnung liegt in +x. Senkrecht gefragt (`_open_above`, also auch alt) ist jeder
Fall zu.

| gap | senkrecht | 0,11° | 0,57° | 2,9° | 10° | 30° |
|---|---|---|---|---|---|---|
| 0,3 mm | offen | offen | offen | offen | offen | offen |
| 0,6 mm | zu | zu | **offen** | **offen** | **offen** | **offen** |
| 2 mm | zu | zu | **offen** | **offen** | **offen** | **offen** |
| 5 mm | zu | zu | zu | **offen** | **offen** | **offen** |
| 10 mm | zu | zu | zu | **offen** | **offen** | **offen** |

Eine Wand mit 0,57° (0,005 mm je Schicht) lässt den Kreis 2 mm, eine mit 2,9° 10 mm seitwärts
unter das Dach wandern. Echte Netze — Formschrägen, organische Wände, Kugelzonen — haben solche
Wände fast überall. Am Korpus wird die Schachtfrage nie gestellt (siehe Leistung); die Lücke
öffnet aber die Klasse, die RM-571 geschlossen hat: eine Säule unter einem Dach im
umschlossenen Raum, etwa ein Kanal in einem Gefäß mit leicht überhängender Wand.

**Fix (Variante 1b, im Scratchbaum `fix1b` gegengeprüft):** getroffene Mitten nur so weit
aufweiten, wie die Wand sie schiebt, mit einem kleinen Zuschlag für Vieleck und Vereinfachung,
höchstens `step`:

```
corners = shapely.points(shapely.get_coordinates(fallen))
depth = float(np.max(shapely.distance(corners, blocked.boundary)))
push = min(step, 1.02 * depth + 2.0 * WIDTH_SIMPLIFY)
centres = centres.union(fallen.buffer(push, quad_segs=SHAFT_STEP_SEGMENTS))
```

Ergebnis `fix1b_kriechen.txt`: 0,11° und 0,57° bleiben ab `gap` 0,6 zu; 2,9° und 10° öffnen nur
noch 0,6 mm (ein Zuschlag), 30° bis 5 mm statt 10 (ein Kreis darf so steil ausweichen, wie die
Wand schiebt). Die 29 Schacht-, Deckel- und Bechertests bleiben grün (`fix1b_tests.txt`,
Exit 0), ebenso `test_slice_findings.py` und `test_advise.py` ganz (280 bestanden, Exit 0,
`fix1b_voll.txt`). Fälle (`fix1b_faelle05.txt`, `fix1b_faelle02.txt`) wie am Stand `a675390e6` bis auf drei
Grenzfälle derselben Klasse wie Fund 3, die nun zu sind: Lippe 33 bzw. 33,5 mm (0,5 bzw.
0,2 mm), Lippe 1 mm zur hinteren Wand (0,5 mm), scharfer Knick 30° Ø 34 → 34. Ohne Zuschlag
(Variante `fix`, `push = min(step, depth)`) fiel auch der schräge Schacht Ø 30,2 um 20° zu —
der Zuschlag ist nötig. Test zum Fix: dieselbe Kammer synthetisch, Wand 0,57° oder 2,9°, Öffnung
2 mm daneben → zu (am Stand `a675390e6` offen, also rot), Wand senkrecht zu, `gap` 0,3 offen.

### 6. mittel — Ein schräger Schlitz zählt mit seiner waagerechten Weite (neue falsche Öffnung, „Schacht zu eng“)

`_shafts_pass` misst je Schicht den waagerechten Schnitt. Der Docstring sagt es selbst („ein
Schlitz, quer zu seiner schmalen Seite geneigt, zählt deshalb mit w / cos θ — bis zur
Überhanggrenze höchstens das 1,4-Fache“), stellt den Absatz aber unter die Überschrift „Weit
wie ein Kanal quer zur Achse“, und Regel, Begründung und Archiv nennen es nicht. Nach `CHANNEL_WIDTH` holt
niemand eine Stütze durch einen engeren Spalt heraus (Review RM-571); quer zur Achse ist der
Schlitz aber nur `w` weit.

Beleg `probe_faelle.py`, Schlitz `w` × 60 mm durch einen Deckel von 20 mm, um θ geneigt
(`schlitz_neu05.txt`, `schlitz_neu02.txt`, `schlitz_alt05.txt`):

| Schlitz (quer zur Achse) | waagerecht | alt | neu 0,5 mm | neu 0,2 mm |
|---|---|---|---|---|
| 45°, 20 mm | 28,3 | zu | zu | zu |
| **45°, 22 mm** | 31,1 | zu | **offen** | **offen** |
| **40°, 24 mm** | 31,3 | zu | **offen** | **offen** |
| 30°, 25 mm | 28,9 | zu | zu | zu |
| **30°, 27 mm** | 31,2 | zu | **offen** | **offen** |
| senkrecht 29 / 31 mm | 29 / 31 | zu / offen | zu / offen | zu / offen |

Bei runden Löchern stimmt die Messung (die schmale Achse des waagerechten Schnitts ist der
Durchmesser), bei Schlitzen nicht. Fix: die geschobenen Mitten gegen eine elliptische
Aufweitung prüfen — Halbachse `R / cos θ` in Schubrichtung, `R` quer dazu, `tan θ` = Schub je
Schichthöhe (aus Fund 1 bekannt); freie Kreise steigen senkrecht und bleiben bei `R`.
Gegenproben: Schlitz 45° 22 mm zu, rundes Loch Ø 34 um 40° weiter offen. Ein schneller
Prototyp davon (Scratchbaum `fix6`: Richtung aus den Schwerpunkten von gefallenen und gelandeten
Mitten, Neigung aus der Schubtiefe) war zu streng — er sperrte jeden schrägen Schacht, 7 der 29
Tests rot (`fix6_tests.txt`) —, die Messung braucht also einen sorgfältigen Entwurf, keinen
Nachmittagsfix. Alternative für heute: Robert entscheidet, dass die waagerechte Weite zählt
(wie in `_narrow`); dann gehört die Grenze in Regel, Begründung und Archiv, mit einem Test, der
sie festhält, und einem Registerpunkt für die Weite quer zur Achse.

### 3. mittel — Scharfe Knicke und Engstellen abseits der hinteren Wand bleiben gesperrt (falsche Sperre, keine Regression); die Unterlagen nennen nur „zwei kleine Grenzen“

Weil nur getroffene Kreise ausweichen, liegen sie in einem schrägen Schacht bald an seiner
hinteren Wand (der Docstring sagt das selbst). Jede Fortsetzung, deren freie Mitten mehr als
einen Schritt von dieser Wand entfernt liegen, schließt dann den Schacht, obwohl ein Kreis
entlang der Achse durchpasst. Das ist nicht nur die Lippe aus dem Bericht, sondern eine Klasse —
und sie trifft den „geknickten Schacht“, den Regel `druckrat.md`, Begründung und Archiv
versprechen („Ein schräger oder geknickter Schacht zählt …“).

Beleg `probe_faelle.py` (Becher mit Deckel, Anteil des Simses im Sperrraum, 1–4 % = offen,
64/66 % = gesperrt; `faelle_neu.txt`, `faelle2_neu05.txt`, `faelle2_neu02.txt`):

| Fall | 0,5 mm | 0,2 mm | Kreis passt entlang der Achse |
|---|---|---|---|
| Knick mit Kugel 20/30/40° → senkrecht, Ø 34 und 32, auch Ø 34 → 31 | offen | offen | ja |
| scharfer Knick (zwei Deckelteile, waagerechte Fuge) 20° Ø 34 → 34 | offen | offen | ja |
| **scharfer Knick 20° und 30° Ø 34 → Ø 32 / Ø 31** | **zu** | **zu** | ja |
| **scharfer Knick 40° Ø 34 → Ø 34** | **zu** | **zu** | ja |
| Lippe mittig im 20°-Schacht 31 / 32 / 33 / 33,5 mm | zu / zu / offen / offen | zu / zu / **zu** / offen | ja |
| Lippe 32 mm, Öffnung 2 / 1 mm zur hinteren Wand | offen / offen | offen / zu | ja |
| Wendel r 5, Ganghöhe 40, Ø 31 | offen | **zu** | ja |

Alle diese Fälle waren auch vorher zu (alt 64 %); der Sims druckt dort weiter ohne Stütze.
Falsch sind die Unterlagen: Begründung (`regel-druckrat.md`) und Docstring nennen „zwei kleine
Grenzen“ mit Zahlen, die nur bei 0,5-mm-Schichten gelten, und rechtfertigen die Lippe mit „eine
Lippe ist ein flacher Überhang, also ein Dach“. Der Grund ist nicht das Dach — die Kreise, die
durch die Lippe passen, stehen nicht unter ihr —, sondern dass die Kreise an der hinteren Wand
kleben; dieselbe Ursache sperrt den scharfen Knick. Zur Frage im Auftrag: **ja, ein Fund, aber
als Grenze vertretbar**, wenn sie richtig benannt ist; beheben braucht ein anderes Modell.

Fix: Docstring, Regel, Begründung und Archiv ehrlich machen (Klasse: Knick oder Engstelle,
deren freie Mitten mehr als einen Schritt von der hinteren Wand liegen; Zahlen je Schichthöhe)
und einen neuen Registerpunkt vorschlagen. Richtung für diesen Punkt, im Scratchbaum `fix2`
gemessen: Der ganze Weg weicht so weit aus, wie die Wand schiebt (`centres.buffer(push)` statt
nur der getroffenen). Dann sind Lippen 31–33,9 und scharfe Knicke 20/30° bei 0,5 mm offen, die
Tests grün (`fix2_*.txt`) — aber der ganze Weg wandert mit jeder schiebenden Wand (30°-Wand:
bis 10 mm seitwärts, `fix2_kriechen.txt`), der scharfe 40°-Knick bleibt zu, Ø 30,2 um 20° fällt
zu. Das ist kein Fix für heute.

### 2. leicht bis mittel — Die Ausweichweite ist die Startregel, nicht die wirksame Überhanggrenze

`analysis.py:3590–3596` `SHAFT_DRIFT: Final = OVERHANG_ANGLE_FACTOR`. Der Docstring begründet
die Zahl mit „so weit, wie eine Wand ohne Stütze überhängt“ — das ist die Stützgrenze, und die
kommt nach `.claude/rules/druckrat.md` aus dem Profil („Den Stützwinkel sagt, womit der Slicer
stützt … Auswertung, Druckdialog-Rat und Kanalsperre rechnen mit den wirksamen Einstellungen …
Wer einen Winkel einführt, reicht ihn bis in jede Vorauswahl durch“).
`app/core/knowledge/rules.py:42–46` sagt an der Konstante selbst: „Die Frage stellt man
`Profile.overhang_limit_degrees`, nicht diese Zahl.“ Die Säulen, deren Erreichbarkeit gefragt
wird, entstehen schon mit dem wirksamen Winkel (`slice_body(..., overhang_angle=...)`), die
Ausweichweite nicht; der Docstring begründet das nur technisch („der Sperrraum hängt nur an den
Schichten“). Regel 7 (Toleranzen) ist nicht berührt, Regel 8 nicht im Wortlaut (kein
Projektparameter), wohl aber die Gebietsregel. Zur Frage im Auftrag: **nein, nicht aus dem
Profil hergeleitet.**

Fix: den Winkel wie `bridge_from` im `SliceResult` mitführen (`slice_body` setzt ihn) und in
`_channel_space` daraus `tan(radians(...))` reichen; Test an einem Winkel ungleich 45. Wenn 45°
als Zugangsgeometrie gewollt ist, statt dessen die Begründung umschreiben (keine Stützgrenze,
sondern eine Entscheidung mit Grund) und die Regel ergänzen.

### 4. leicht — Tests halten die 45°-Grenze, das Zusammenlegen der Wege und die Stufe nicht

Mutanten am fertigen Stand (`run_mutants_rv.py`, `mutanten.txt`, 29 Tests der Auswahl,
`mutant_plugin.py` des Bauagenten):

| Mutante | rot |
|---|---|
| keine | 0 (29 grün) |
| freie Kreise wandern (jeder Weg getroffen, alle Mitten gefallen) | 1: `test_open_sky_is_asked_at_each_slab` |
| `SHAFT_DRIFT` 2,0 (63°) | **0** |
| `SHAFT_DRIFT` 1,5 (56°) | **0** |
| alle Wege zusammenlegen (`_same_centres` immer wahr) | **0** |
| `_clipped` ohne Reparatur | 1: Zickzack 34 |
| Restfläche statt `WIDTH_SIMPLIFY²` nur leer | 0 (Zahlenschutz, hinnehmbar) |
| Treffer immer | 0 (nur Leistung, hinnehmbar) |
| Startscheibe über der obersten Schicht immer offen | 0 (Randfall) |
| Saum ohne Verbindung zur Säule | 2: dünne Wand |

Die Grenze „so steil, wie eine Wand ohne Stütze überhängt“ ist bis mindestens 63° nicht
bewacht, ein Fehler in `_same_centres` fiele keinem Test auf. `test_a_step_narrower_than_a_
channel_keeps_the_shaft_closed` ist auch bei 3 mm Versatz (31 mm Überlappung, ein Kreis passt
senkrecht durch beide Löcher) grün — dort sperrt nicht die Stufe, sondern der Streifen ≥ 15 mm
vor dem Sims, auf den dessen eigene Decke die Kreise zwingt (`Stufe 3.0` in `faelle_*.txt`, alt
wie neu zu); er fängt Drift 10 (Bauagent), nicht 1,5 oder 2 (gemessen) — geschätzt erst ab
einem Sprung von 4 mm je Schicht. Die Mutantentabelle in Bericht und Archiv stammt
vom Zwischenstand (`rm629\mutanten.txt` 22:38; Anker wie `if not shade.is_empty and
shapely.dwithin(` gibt es im fertigen Code nicht mehr); „freie Kreise wandern“ habe ich am
fertigen Stand nachgefahren, sie wird gefangen.

Fix: (a) ein langer Schacht über der Grenze bleibt zu — „lang 50° Ø34 H60“ (Deckel 60 mm) ist
bei 0,5 und 0,2 mm zu, „lang 44°“ offen; als Test bei 0,2 mm 44 offen / 46 zu, oder bei 0,5 mm
46 offen / 50 zu. (b) synthetisch zwei Scheiben, deren Wege sich unterscheiden (die untere wird
von einer schrägen Wand zur Seite geschoben, darüber eine Enge auf der anderen Seite:
`{unten: False, oben: True}`), rot mit „alle zusammenlegen“. (c) die Stufe synthetisch über
`_shafts_pass` mit Gegenprobe (Versatz, bei dem ein Kreis passt → offen), damit der Test die
Stufe misst und nicht den Sims.

### 5. leicht — Grenzzahlen in Docstring, Begründung und Archiv gelten nur bei 0,5 mm

„Dachkante 0,5 offen, 1 zu“ und „Lippe ab 33 offen“ stimmen nur bei 0,5-mm-Schichten; die
Druckanalyse rechnet im Druckraster (`druckrat.md`, „Die Druckanalyse benutzt das
Druckraster“). `faelle_neu.txt` (0,5 mm): weit versetzt 0,5/0,7/0,9 offen, 1,0 zu;
`faelle_neu02.txt` (0,2 mm): 0,5 offen, 0,7 zu. Fix: als Formel (ein Schritt = Schichthöhe ·
`SHAFT_DRIFT` je Dachkante; am Becher zwei: Sims und Deckel) oder je Schichthöhe.

## Fälle ohne Befund (Auftrag Punkt 1)

`faelle_neu.txt` gegen `faelle_alt.txt` (0,5 mm), `faelle_neu02.txt`/`faelle2_neu02.txt` (0,2 mm):

- Schräg Ø 34 um 10/20/30/40/44° offen (vorher 64 %), 60° zu; −30° offen (Test). Ø 29,8 um 20°
  zu, Ø 30,2/30,5/31 offen; um 40° Ø 30,5/31/32 offen. Grenze an `CHANNEL_WIDTH` für runde
  Löcher wie behauptet.
- 45°-Grenze an einem langen Schacht (Deckel 60 mm): 0,2 mm 44° offen / 46° zu; 0,5 mm 46° offen
  / 50° zu (ein Schritt Spiel an der Dachkante). Kurze Deckel (20 mm) öffnen auch bei 46/50°,
  weil die senkrechte Durchsicht dort 29,1 mm ist und ein kleiner Versatz genügt — richtig.
- Zickzack Ø 34 offen, zweite Strecke Ø 28 zu (beide Schichthöhen).
- Wendel r 5, Ganghöhe 40, Ø 34 offen; r 8 offen (innere Bahn steiler als 45°, richtig).
- Kegel 40 → 26 zu, 40 → 31 offen.
- Sackloch (Schacht endet 5 mm unter der Oberseite) senkrecht und 20° zu (20°: 93 % wie alt,
  weil das Sackloch selbst eine umschlossene Decke ist; CPU alt 1,77 / neu 2,16 s).
- Versetzte Löcher (Stufe) 3,0 bis 6,0 mm: alle zu, alt ebenso (siehe Fund 4).
- Dachkante: Fund 5; als benannte Grenze vertretbar (≤ 1 mm neben dem Saum).

## Slicer (Auftrag Punkt 2)

`tools/matrix_unit.py` aus dem Scratchbaum `neu`, ElegooSlicer Centauri Carbon 2 und Cura SV06,
Herstellerprofil, gepinnt; Messung `becher_messung.py` mit
`.claude/.state/drache-2026-10-08/gcode_im_kanal.py`, Bereiche neu gebaut (Säule unter dem Sims
x 0…14, y −7…7, z 4…15; Tunnel x 20…28, y −8…8, z 4…20). Stützbahn in m:

| Becher | Slicer | Vorschläge: unter dem Sims / Tunnel | ohne Sperre (Stützen an) |
|---|---|---|---|
| schräg 20° Ø 34 | Cura | 17,29 / 0,00 | 16,91 / 12,64 |
| schräg 20° Ø 34 | Elegoo | 7,49 / 0,00 | 6,33 / 4,72 |
| Wendel r 5 Ø 34 | Cura | 17,39 / 0,00 | 16,95 / 12,64 |
| Wendel r 5 Ø 34 | Elegoo | 8,25 / 0,00 | 6,90 / 4,97 |
| scharfer Knick 40° Ø 34 → 34 (Fund 3) | Cura | **7,70** / 0,00 | 16,89 / 12,64 |
| scharfer Knick 40° Ø 34 → 34 (Fund 3) | Elegoo | **3,14** / 0,00 | 6,09 / 4,10 |

Die Zahlen des Bauagenten für den 20°-Becher sind auf die Stelle genau nachgefahren
(`messung_schraeg20.txt`); die Wendel verhält sich gleich (`messung_wendel.txt`). Stütze unter
dem Sims, Tunnel frei. Der scharfe Knick zeigt, was Fund 3 beim Kunden heißt
(`messung_scharf40.txt`): Unter dem Sims steht nur gut die Hälfte der Stütze — dieselbe Lage wie
am 20°-Becher vor RM-629 (Cura 7,72, Elegoo 3,60 m im Bericht des Bauagenten).

## Kundensicht

Vorher druckte ein Sims unter einem schrägen Loch im Deckel mit übernommenen Vorschlägen nur
mit gut der Hälfte seiner Stütze (Cura 7,7 statt 17 m, Elegoo 3,6 statt 7,5 m); jetzt bekommt er
sie ganz, und der Tunnel bleibt frei. Kein neuer Text, nichts zu raten — die Sperre bleibt ein
Vorschlag mit Grund. Wo Fund 1 oder 6 greift, steht künftig Stütze in einem Raum, aus dem sie
nach der eigenen Regel nicht herauskommt (Säule unter dem Dach, schräger Schlitz unter 30 mm);
das sieht der Kunde erst am Druck. Wo Fund 3 greift, bleibt es wie vorher (halbe Stütze).

## Leistung (Auftrag Punkt 3)

`echte_modelle.py` (alt und neu im selben Prozess, im Wechsel, 5 Läufe, CPU-Median, einfädig,
ungemerkt), `echte.txt`, `echte2.txt`:

| Schnitt | Scheiben | größte Abweichung | `_open_above` / `_shafts_pass` | CPU alt / neu |
|---|---|---|---|---|
| Becher (becher60) | 16 = 16 | 0 mm² | 11 / 0 | 0,297 / 0,328 s |
| Becher gerade / Kegel | 16 = 16 | 0 | 11 / 0 | 0,328 / 0,328; 0,438 / 0,453 |
| Deckel Schlitz 25 / 30 | 16 = 16 | 0 | 11 / 1 | 0,203 / 0,281; 0,219 / 0,266 |
| Deckel schräg 20° | 16 = 16 | 117,9 (gewollt) | 11 / 1 | 0,250 / 0,359 |
| Side kit rest, Grenuttag, Kumiko, obj_30_G | gleich | 0 | 0 / 0 | im Rauschen |
| Schüssel Drucklage 50° / 55° | 43 / 44 gleich | 0 | 0 / 0 | 6,00 / 6,03; 5,59 / 5,63 |
| Schüssel Dateilage 55° / 60° | 30 / 13 gleich | 0 | 0 / 0 | 8,91 / 8,75; 2,70 / 2,69 |
| Drache 50 % | 16 = 16 | 0 | 0 / 0 | 2,31 / 2,22 |
| Eiffelturm | 3 = 3 | 0 | 0 / 0 | 12,44 / 11,97 |
| Drache 130 % | 22 = 22 | 0 | 0 / 0 | 6,81 / 6,70 |

Becherbezug gehalten (keine Schachtfrage, Werte im Rauschen). An keinem echten Modell wird
`_open_above` überhaupt gerufen — die ganze Frage „umschlossen, von oben erreichbar“ hängt am
Korpus nur an den synthetischen Bechern. Mehrkosten nur, wo die Schachtfrage läuft
(+0,06…0,11 s am Becherdeckel, Sackloch +0,4 s, Zickzack bei 0,2 mm 1,3 s). Gebündelt: die
Trefferfrage je Schicht über alle Wege (`shapely.dwithin` über ein Feld); die Schichtschleife ist
von Natur aus nacheinander, die Wege sind 1–3. In Ordnung. `ruff check`, `ruff format --check`
(zwei Dateien) und `mypy` (374 Dateien) am Scratchbaum `neu`: ohne Befund, je Exit 0.

## welle3 (Auftrag Punkt 4)

`git merge-tree --write-tree origin/welle3 a675390e6`, welle3 = `164d713a9` (zuerst `37ff5c9ca`,
dasselbe Ergebnis): Konflikte nur in Unterlagen.

- `ROADMAP-ARCHIV.md`: Index und Abschnitte — welle3 hat RM-754, -751, -750, -670 (10.10.) und
  weitere eingefügt, der Zweig RM-629. Beide behalten.
- `app/core/slice/CLAUDE.md`, Zeile `analysis.py`: welle3 ergänzte `keep_answers` (je Körper ein
  Schnitt, Verdrängung), `span_beside`/`span_spot`, `channel_pieces`; der Zweig den Satz „sonst
  ein schräger Schacht … über `_shafts_pass`“. Lösung: welle3-Zeile nehmen und den Satz nach
  „im Fenster `_sky_window`“ einsetzen.
- `analysis.py`, `test_slice_findings.py`, `druckrat.md`, `regel-druckrat.md` ohne Konflikt. Die
  welle3-Änderungen an `channel_space` (Merker `_recent`/`_keep_recent`) berühren
  `_channel_space` nicht.
- Probemerge (`fbf23c411`) im Scratch: `test_slice_findings`, `test_slice`, `test_advise`,
  `test_estimate`, `test_slice_core` mit `-n 4`: **631 bestanden, Exit 0** (`merged_tests.txt`).

## Unterlagen, Register, Changelog (Auftrag Punkt 5)

- Register: `ROADMAP.md` hat RM-629 auf keinem Stand (Zweig, welle3, main, Basis); der Punkt kam
  aus der Übergabe. Direkt ins Archiv ist in Ordnung. Bleibt aus Fund 3 (und je nach
  Entscheidung Fund 6) Arbeit offen, braucht sie einen neuen Registerpunkt.
- Changelog: keiner nötig. Die Sperre im umschlossenen Raum kam mit `43e111dc6` (`_enclosed`,
  08.10.) und `004973704` (`_open_above`, RM-571); `git tag --contains` ist für beide leer. Der
  0.6.0-Punkt „*Kanäle frei halten* sperrt nur noch Raum, aus dem keine Stütze mehr herauskäme“
  beschreibt die Eigenschaft schon.
- Karte `app/core/slice/CLAUDE.md` und Regel `druckrat.md` ziehen nach; Inhalt siehe Funde 1, 3,
  5, 6.

## Was vor dem Landen zu tun ist (Reihenfolge)

1. Fund 1: Variante 1b einbauen, Test „Kammer mit 0,57°- oder 2,9°-Wand, Öffnung 2 mm daneben →
   zu“ (am Stand `a675390e6` rot), Docstring „weicht so weit aus, wie die Wand schiebt“.
2. Fund 6: Robert fragen, ob die waagerechte Weite vorerst zählt. Ja → Grenze in Docstring,
   Regel, Begründung, Archiv, Test „Schlitz 45° 22 mm offen“ als festgehaltene Grenze und ein
   Registerpunkt; nein → Messung quer zur Achse entwerfen (nicht heute).
3. Funde 3 und 5: Unterlagen ehrlich machen (Klasse statt „Lippe ist ein Dach“, Zahlen je
   Schichthöhe), Registerpunkt für den achsentreuen Kreis.
4. Fund 4: Grenztest 45° (lang 50° zu bei 0,5 mm), Test für `_same_centres`, Stufe synthetisch
   mit Gegenprobe; die Mutantenangabe im Archiv am fertigen Stand neu fahren.
5. Fund 2: Winkel im `SliceResult` mitführen (Muster `bridge_from`) oder als Entscheidung
   begründen.
6. Merge in welle3: zwei Unterlagenkonflikte wie oben lösen.

Danach Nachprüfung: Fund 1 ändert die Modellregel, Fund 6 und 2 je nach Entscheidung. Mit 1b
bleiben die Fälle des Bauagenten gleich (Becher, Slicerbeleg 20°) bis auf die Lippe 33 mm bei
0,5 mm, die zu wird; dazu werden zwei weitere Grenzfälle der Klasse aus Fund 3 zu (Lippe 1 mm
zur hinteren Wand, scharfer Knick 30° Ø 34 → 34).

## Neue Punkte (Vorschlag, keine Nummer vergeben)

- **Schacht quer zur Achse messen** (Fund 6): geschobene Kreise gegen eine Ellipse `R / cos θ`
  in Schubrichtung prüfen; Fälle Schlitz 45° 22 mm (zu) und Ø 34 um 40° (offen).
- **Kreis folgt der Achse statt der hinteren Wand** (Fund 3): scharfe Knicke, Lippen, enge
  Wendeln; Variante `fix2` als Ausgangspunkt mit ihrer Kriechgrenze.
- Außerhalb RM-629, schon auf main: `pyproject.toml` verlangt `shapely>=2.0`, der Kern ruft
  `make_valid(..., method="structure", keep_collapsed=False)` (Docstring von shapely 2.2:
  „versionadded:: 2.1.0“) und `shapely.dwithin`; `constraints.txt` pinnt 2.2.0, die CI ist also
  sicher, eine Installation gegen shapely 2.0 nicht. Untergrenze auf 2.1 heben.

## Geprüft (Verlauf)

- 10:17 Diff gelesen (6 Dateien, +495/−41), jede Zeile von `_shafts_pass`, `_touching_centres`,
  `_same_centres`, `_seam_reach`, `_clipped`, `reachable_from`, `crossed_by`, Tests, Docstrings,
  Unterlagen. Sperren: `reachable_from` hält `sky_lock` über `_shafts_pass` (kein verschachteltes
  Sperren, `shade_at` nur unter der Sperre) — in Ordnung. Alle Startscheiben bekommen eine
  Antwort (auch über der obersten Schicht), `passages[number][start]` trifft immer.
- Regeln 1–22 am Diff: kein Qt, keine Op, keine Szene, keine Texte, keine Ausnahme ohne Rat,
  keine Abhängigkeit, Bezeichner englisch, Kommentare deutsch mit Umlauten, kein `==` auf
  Fließkomma (`pending[0] == index` sind Ganzzahlen). Regel 7/8 und Gebietsregel: Fund 2.
- Läufe (alle Exit 0 außer den Mutanten wie genannt und dem verworfenen Prototyp `fix6`, 7 rot,
  abgebrochen): `faelle_*.txt`, `faelle2_*.txt`,
  `schlitz_*.txt`, `kriechen*.txt`, `fix*_*.txt`, `mutanten.txt`, `echte*.txt`,
  `merged_tests.txt`, `messung_*.txt`, `mypy.txt`, `ruff.txt`.
