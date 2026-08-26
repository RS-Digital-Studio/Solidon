# Gebietsbericht: Schichtanalyse und Auto Split (`app/core/slice/`, `app/core/split.py`)

Gegen analytische Körper und den Korpus gemessen; `_chain` nicht gebaut → GEOS-Weg gemessen. Skripte unter `review-slice\`.

## Hoch

### 1 [hoch] Die Orientierungssuche stellt flache Teile hochkant — VERIFIZIERT
`analysis.py:145` (`heights = np.arange(low + layer_height/2, high, layer_height)`), Wirkung `orientation.py:141,166,200` — ist ein Körper niedriger als die halbe Suchschichthöhe (`SEARCH_LAYER_HEIGHT=1.0`, also unter 0,5 mm), ist `heights` leer → 0 Schichten, `first_layer_area=0`, `stands()` verwirft die liegende Lage; jede hochkant stehende Lage gewinnt. Gemessen (Karte 85×54): 0,4 mm dick → Richtung (0,1,0), 54 mm hochkant, `orient.searched` meldet „0,0 mm³ gespart". Trifft jede Schablone/dünne Karte/0,4-mm-Blech. **Fix:** in `slice_body` mindestens eine Schicht erzwingen, wenn `high-low > EPS_GEOM` aber `arange` leer (`[(low+high)/2]`).

### 2 [hoch] Auto Split lässt Passungen im Dokument, die es gerade als entfallen meldet — VERIFIZIERT
`split.py:173-206` — `_fits_without` sortiert die Passungen des verbrauchten Stücks aus `kept` aus, die lokale Liste `fits` behält sie und schreibt sie in `change_for(document, fits=[*kept, *fits])` zurück. Für `apply_line_split` (ein Schnitt) gebaut, greift bei mehreren Schnitten nicht (Zwilling). Gemessen (Balken 600 mm, 2 Schnitte): Befunde `split.fit_dropped`, aber `stift_1/2` bleiben im Dokument (→ `obj_3` existiert nicht mehr) → Prüfbericht `fit.missing_feature` (Fehler). **Fix:** in der Schleife `fits[:] = [e for e in fits if e not in gone]`; Test mit zwei Schnitten.

### 3 [hoch] Auto Split liefert ein Stück, das nicht auf das Bett passt — VERIFIZIERT
`split.py:91-104`, Wirkung `geom/autosplit.py:50` (`MARGIN=2.0`), `geom/pins.py:239` (`length=reach*2`) — die Suche reizt die Bauraumgrenze aus, der Stift ragt mit `plan.length/2` (7,2 mm) über die Schnittfläche; beides zusammen wird nicht geprüft. Gemessen (600-mm-Balken, Bett 220, Grenze 216): Quader A geplant 216 → angewandt 223,2 → passt nicht; Prüfbericht `arrange.out_of_build_volume`. Zusage „teilt, bis jedes Stück passt" gebrochen. **Fix:** Stiftüberstand in die Grenze einrechnen oder nach der Suche gegenprüfen und einen Schnitt mehr planen.

## Mittel
- **4** „Alle Überhänge erreichen das Bett" auch bei Säule auf dem Modell (`advise.py:480-491`, Bedingung `needs_support and not islands`; „keine Insel" ≠ „reicht bis zur Platte"). Gemessen (Hohlraum über Material): placement `everywhere→build_plate` schaltet Stützen dort aus, wo sie gebraucht werden. `_support_volume` weiß es (`_above_material`). Fix: „Säule endet an Material" mitführen und den Vorschlag daran hängen.
- **5** `minimum_width` misst die dickste Stelle einer Schicht, nicht die dünnste (`analysis.py:757-799`, größter einbeschriebener Kreis). Gemessen: Klotz+Rippe 0,4 → 8,03; Streuscheibe mit 1,1-mm-Armen → Arachne-Vorschlag und Bahnbreitenwarnung fallen aus (genau der Fall aus `advise.py:98`). Fix: je zusammenhängendem Teil, dünnste Stelle suchen; Test „dünn neben dick".
- **6** Auslaufschichten kippen die Bahnbreitenempfehlung (`analysis.py:923`, `advise.py:576-589`); oberste Fasenschicht 0,047 mm bei ~0 Fläche → Vorschlag `line_width 0.42→0.34` (unter Düse 0,4). Gemessen an `plate_chamfer_and_taper.stl`. Fix: nur Schichten mit Mindestfläche werten.
- **7** „Nichts an diesem Teil schwebt" neben „sonst hilft nur eine Stütze" (`advise.py:467-478` vs `:898-934`, `needs_support` kennt die Brückenweite nicht). Gemessen (Becher, Schulter über Öffnung): `support.style grid→none` und zugleich `slice.long_bridge`. Fix: `needs_support` um Brückenweite erweitern, „none" unterdrücken solange `long_bridge` vorliegt.
- **8** Zwei Winkel für dieselbe Frage: Analyse 45°, Slicer 50° (`analysis.py:54-61` vs `types.py:574`, `slicer_keys.py:219,316,430`). Im Streifen 45–50° meldet die Analyse Fläche und empfiehlt Stützen, der Slicer setzt keine. PLAUSIBEL (kein Slicer-Lauf). Fix: eine Zahl, ein Ort.
- **9** Der Prüfbericht rechnet das G-Code-Gewicht mit fester Dichte 1,24 (`gcode.py:73-81,656`, `grams()` ohne Argument); CuraEngine schreibt kein Gewicht. Gemessen: ABS +19,2 %, ASA +15,9 %; `_compare_totals` rechnet daneben mit `settings.filament.density` → zwei Gramm-Zahlen im selben Bericht, Gegenprobe (15 %) reißt allein dadurch. Fix: `findings_for(metrics, density)`.

## Gering
- **10** Keine Untergrenze für die Inselfläche (`analysis.py:730-754`, `needs_support = bool(islands)`); 0,04-mm²-Insel schaltet Stützen fürs ganze Teil ein. Fix: `island_area > line_width²`.
- **11** `FILAMENT_AREA` fest auf 1,75 mm (`gcode.py:36-38`); bei 2,85 mm sind `material_cm3`/`support_mm3` Faktor 2,65 falsch. PLAUSIBEL. Durchmesser durchreichen.
- **12** Auto Split braucht so viele Undos wie Schnitte (`split.py:1-14` Modulkopf vs `:173-206`, eine Transaktion je Schnitt). VERIFIZIERT (2 Schnitte → 3 Transaktionen). Alle Schnitte in eine Transaktion oder Zusage streichen.
- **13** Ein Absatz genau auf Schnitthöhe verliert die untere Fläche (`analysis.py:431-434`, `above = height_above > 0`). Überhang/Inseln/Stützvolumen bleiben korrekt, nur Flächenkennzahlen. `>= -EPS_GEOM`.
- **14** Fehlbegründung „Das Teil läuft nach oben spitz zu" (`advise.py:591-602`, `_has_thin_layers` prüft „obere Hälfte < 120 mm²"); Maßnahme richtig, Grund falsch. Text auf die Tatsache bringen.
- **15** Die Brückenwarnung schickt die Kamera in den Ursprung (`advise.py:932`, `location=(0,0,z)`); nach Plattenbelegung leer. Schwerpunkt statt (0,0).

## Geprüft und in Ordnung
Stützvolumen als Säule, schichthöhenunabhängig (Pilz 29 987 gegen 30 000, T-Träger, Hohlraum; `_above_material` stimmt); Querschnitte (Zylinder 314,03, Würfel 100 Schichten); Brückenweite misst die schmale Seite (Kabelkanal 7,81 statt 30); G-Code-Leser (absolut/relativ/`G92`, Stützanteil, `TIME_ELAPSED`, nie G-Code geschrieben §22); Regel 14 (Herkunft überall); Regel 9 (`orient_for_print` deterministic=False mit Seed); Regel 1/3/10/12; alle 18 Einstellungspfade aus `advise.py` existieren und werden übersetzt; kein „Sollwert aus dem Prüfling" in `test_slice.py`.

**Kann das so rein: nein** — drei hohe Befunde (flaches Teil hochkant, tote Passungen nach Auto Split, Stück über der Bettgrenze) an sichtbaren Wegen; die mittleren Beratungsbefunde machen Vorschläge unglaubwürdig, die der Kunde annehmen soll.
