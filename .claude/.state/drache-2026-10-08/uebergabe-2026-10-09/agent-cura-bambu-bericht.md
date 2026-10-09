# RM-583: Abweichungen bei Cura und Bambu Studio in der Sonde kontakt_je_teil

Stand: Worktree F:\sl-stuetzen (einstellungen/stuetzabstand, 936def3fc plus ungesicherte Änderungen), nur gelesen.
Quelltexte: CuraEngine Tag 5.13.0 (`src/support.cpp`), BambuStudio master
(`Support/SupportParameters.hpp`, `Support/SupportCommon.cpp`, `Support/SupportMaterial.cpp`,
`Slicing.cpp`, `PrintConfig.cpp`). Alles liegt unter `scratchpad\cura_bambu\`.

Kurz gesagt: Beide Slicer drucken, was Solidon geschrieben hat. Die Abweichungen kommen aus
`gcode_kontakt.py`. Solidon muss für die beiden Fragen nichts ändern. Dazu kommen ein Unterschied
in der Bedeutung des Werts bei Bambu (unten werden n+1 Lagen gedruckt) und ein Nebenbefund zum
Reinigungsturm.

## 1. Cura: Ziel 0,6 mm und 3 Lagen statt 0,4 und 5, Bezug 0,4 statt 0,2

### Was geschrieben wurde (ergebnis.json → commands)

Bei Cura trägt die globale Ebene die übernommenen Werte. Die Teile ohne Rat bekommen je Netz die
Grundlage zurück (`handover.py:1564`, `PartSplit(settings, …, revert=True)`). Deshalb steht in
`plate` dasselbe wie in `controls`.

| Ebene | support_z/top/bottom_distance | support_roof_height / interface_height | support_bottom_enable / _height |
|---|---|---|---|
| global und -e0 | 0,4 | 1,0 (5 Lagen) | false / 0 |
| `-l model-0.stl` (Ziel, links) | nur support_z_distance=0,4, der Rest kommt aus der globalen Ebene | – | – |
| `-l model-1.stl` (Bezug, rechts) | 0,2 | 0,4 (2 Lagen) | true / 0,4 (2 Lagen), Abstand 0,2 |

`support_roof_line_distance` = `support_bottom_line_distance` = 1,62 gilt global (Lücke 1,2 plus
0,42 Bahn). Die Lücke kann Cura nicht je Netz annehmen (`unavailable`), sie gilt also auch für
den Bezug.

### Was CuraEngine daraus macht (G-Code, Schichtoberkanten, `schichten.py`)

```
Ziel links : SUPPORT-INTERFACE 11.85 12.05 12.25 12.45 12.65 | leer 12.85 13.05 | SKIN 13.25
Bezug rechts: SUPPORT-INTERFACE 12.65 12.85                 | leer 13.05       | SKIN 13.25
unten Ziel : Platte bis 3.05 | leer 3.25 3.45 (innen) | SUPPORT ab 3.65, keine Trennschicht
unten Bezug: Platte bis 3.05 | leer 3.25 (innen)      | SUPPORT-INTERFACE 3.45 3.65 | SUPPORT ab 3.85
```

Am Ziel liegen 5 Lagen bei 0,4 mm Abstand, unten 0 Lagen bei 0,4 mm. Am Bezug sind es 2 Lagen bei
0,2 mm, unten 2 Lagen bei 0,2 mm. Das ist genau das Geschriebene.
(Die 145- bzw. 238-mm-Bahnen bei 3,25 sind der Stützring außerhalb der Platte, der bis aufs Bett geht.)

### Ursache: die Messung

`gcode_kontakt.py:27` legt ein Raster von 0,5 mm (`CELL`) und markiert eine Zelle nur, wenn ein
Abtastpunkt der Bahnmitte hineinfällt. Die Trennschicht liegt diagonal (45°/135° im Wechsel) mit
1,62 mm Abstand. Dadurch fehlt vielen Zellen die oberste Trennlage. Die Messung findet dann die
nächsttiefere Lage, also +0,2 mm Abstand, und zählt weniger Lagen (`:169`, `:183-187`). Die
Verteilung zeigt das: Ziel oben `0.40: 923, 0.60: 853`, Median 0,6. Im natürlichen Lauf liegt die
Lücke bei 0,2, die Bahnen liegen dicht, und deshalb stimmt dort alles.

Gegenprobe mit gröberem Raster, dieselbe Datei (`nachmessen_cura.txt`):

| Zelle | Ziel oben | Ziel unten | Bezug oben | Bezug unten |
|---|---|---|---|---|
| 0,5 mm | 0,6 / 3 | 0,4 / 0 | 0,4 / 2 | 0,4 / 2 |
| 2,0 mm | **0,4 / 5** | **0,4 / 0** | **0,2 / 2** | **0,2 / 2** |

### Quelltext CuraEngine 5.13.0 (`support.cpp`), Abstand und Dach je Netz

- `:1010-1011`: Die Stützfläche je Netz nimmt `support_top_distance` aus den Netzwerten
  (`roof_settings` = `mesh.settings`). `layer_z_distance_top = (z / layer) + 1` in ganzen µm.
- `:1118-1119`: unten `round_up_divide(support_bottom_distance, layer)`.
- `:1729-1735`: Dach je Netz: `round_divide(support_roof_height, layer)` Lagen,
  Abstand `round_up_divide(support_top_distance, layer)`.
- `:1698-1703`: Boden je Netz entsprechend, mit `support_bottom_enable` je Netz (`:701-703`).

Bei einem Abstand, der ein ganzes Vielfaches der Schichthöhe ist, stimmen beide Rechnungen überein.
`support_gap_target` liefert für Cura genau das (`advise.py:943-951`), `_for_supports` schreibt die
Höhen als Lagen × Schicht mit `:g` (`handover.py:1912-1917`, aus 3 × 0,1 wird „0.3“).

### Feine Schichten, ein Konsolenlauf zur Bestätigung (`cura_fein.py`, 0,7 s)

Derselbe Aufruf mit 0,08er Schichten. Links Abstand 0,16, Dach 0,24 und Boden 0,16. Rechts Abstand
0,08, Dach 0,16 und Boden 0,16:

```
links : INTERFACE 12.65 12.73 12.81 | leer 12.89 12.97 | SKIN 13.05  → 0,16 mm, 3 Lagen
rechts: INTERFACE 12.81 12.89       | leer 12.97       | SKIN 13.05  → 0,08 mm, 2 Lagen
unten links : Platte bis 2.97 | leer 3.05 3.13 | INTERFACE 3.21 3.29   → 0,16 mm, 2 Lagen
unten rechts: Platte bis 2.97 | leer 3.05      | INTERFACE 3.13 3.21   → 0,08 mm, 2 Lagen
```

**Betroffen sind Kunden mit echtem Rat nicht.** PLA 0,08 → Rat 0,16 (2 Schichten) und PETG 0,1 → 0,2
werden genau gedruckt, je Netz. Abweichen könnte nur ein Abstand, der kein Vielfaches der
Schichthöhe ist. Den erzeugt der Rat für Cura nicht.

Randnotiz: `generateVaryingXYDisallowedArea` (`:823-824`) liest Ober- und Unterabstand aus der
globalen Ebene, also mit den übernommenen Werten. Das wirkt nur auf den XY-Abstand an Schrägen
(`support_xy_overrides_z`) und ist kein Kontaktfehler.

## 2. Bambu Studio: Ziel unten 5 Lagen und 0,18 mm, Bezug unten 2 Lagen und 0,15 mm

### Was geschrieben wurde

`model_settings.config` (Ziel, Objekt 2): `support_top_z_distance 0.4`, `support_bottom_z_distance 0.4`,
`support_interface_top_layers 5`, `support_interface_bottom_layers 0`, `support_interface_spacing 1.2`.
Für den Bezug steht nichts, er nimmt also den Prozess: 0,2 / 2 / 2 / 0,5. Im Kopf des G-Codes steht
`independent_support_layer_height = 1`.

### Was Bambu druckt (G-Code)

```
Ziel oben  : Support transition 11.236 | interface 11.509 11.782 12.055 12.327 12.600 | Modell ab 13.0 → 0,4 / 5
Bezug oben : Support transition 12.247 | interface 12.524 12.800                       | Modell ab 13.0 → 0,2 / 2
Ziel unten : Platte bis 3.0 | Kontaktlage 3.600, Höhe 0.2 (Unterkante 3.4) → 0,4 mm, Bahnabstand 2,88 mm = Stützmuster
Bezug unten: Platte bis 3.0 | Kontakt 3.400, Höhe 0.2 (Unterkante 3.2), dann 3.676 3.953 → 0,2 mm, Bahnabstand 0,88 mm, 3 Lagen
```

Belege: G-Code-Zeile 11909ff. (`; FEATURE: Support interface`, `; LAYER_HEIGHT: 0.2`,
`G1 X84.738 … X87.615 … X90.492`, Abstand 2,877) und Zeile 11394ff. (`X136.459 … X137.336 …
X138.213`, Abstand 0,877). Die Länge passt dazu: 497 mm am Ziel gegen 1456 mm je Lage am Bezug.

### Was Bambu mit den unteren Werten tut (Quelltext)

- **0 heißt 0, nicht „wie oben“.** Nur ein negativer Wert übernimmt die obere Zahl:
  `SupportParameters.hpp:73-74` (`support_interface_bottom_layers < 0 ? num_top : …`). Beim
  *Abstand* dagegen heißt ≤ 0 „wie oben“ (`Slicing.cpp:115-117`). Solidon schreibt unten denselben
  Abstand wie oben (`slicer_keys.py:480-481`), deshalb trifft das hier nicht.
- **Werte je Objekt kommen an.** Der Abstand kommt aus `object_config.support_bottom_z_distance`
  (`Slicing.cpp:115`). Die Kontaktlage liegt bei `layer.print_z + height + gap_object_support`
  (`SupportMaterial.cpp:2434ff.`): 3,0 + 0,2 + 0,4 = 3,6 am Ziel, 3,0 + 0,2 + 0,2 = 3,4 am Bezug.
- **Mit 0 Lagen** wird die Kontaktlage als Stütze gedruckt: `SupportCommon.cpp:1781`
  (`bottom_interfaces = top_interfaces && support_interface_bottom_layers != 0`) →
  `InterfaceAsBase`, mit Stützbahn, Stützdichte und Stützwinkel. Als Rolle steht trotzdem
  `erSupportMaterialInterface` (`:1761`), im G-Code also „Support interface“. Gedruckt wird keine
  Trennschicht. Das ist richtig so.
- **Mit n ≥ 1 Lagen druckt Bambu unten n+1 Lagen**: die Kontaktlage und darüber n weitere
  (`SupportCommon.cpp:201-218`, `bottom_z = intermediate[idx − n + 1]`). Eine Verringerung um 1, wie
  PrusaSlicer sie hat, fehlt, obwohl der Kommentar in `SupportParameters.hpp:296` „without counting
  the contact layer“ sagt. Oben sind es n Lagen, bei Bambu kommt eine Übergangslage dazu
  (`num_top_base_interface_layers = 1`, Rolle `erSupportTransition`, `:1805`). Der natürliche Lauf
  zeigt dasselbe: unten 3,4 / 3,6 / 3,8 bei geschriebenen 2. OrcaSlicer main zählt ebenso ohne die
  Verringerung (`SupportParameters.hpp:48`), hat aber bei einem Filament keine Übergangslage.

### Ursache der Messwerte: die Messung

1. `gcode_kontakt.py:30` kennt „Support transition“ nicht. `kind_of` (`:63-71`) macht daraus
   „model“. Unter jedem oberen Trennschichtstapel sieht die Messung deshalb einen Fuß auf dem Modell.
   Ziel: Übergang 11,236 → Trennschicht 11,509, Höhe aus der nächsten Stützebene der *ganzen Platte*
   (11,418 rechts) = 0,091 → 11,509 − 0,091 − 11,236 = **0,182**, und 5 Lagen darüber. Das sind die
   gemeldeten 0,18 und 5. Beim Bezug kommen die 0,15 auf demselben Weg zustande.
2. `:157-158` rechnet die Schichthöhe als Abstand zur vorigen Stützebene auf der ganzen Platte. Mit
   eigener Stützschichthöhe liegen die Ebenen beider Körper verschränkt, die Höhe wird zu klein und
   der Abstand zu groß (Bezug echt 0,2, gemessen 0,338).
3. Die Kontaktlage bei 0 Lagen heißt „Support interface“ und wird als eine Trennschicht gezählt.

Gegenprobe mit „support transition“ als Stütze und Höhen nur aus dem eigenen Bereich
(`gcode_kontakt_fix.py`, `nachmessen_fix.txt`, Zelle 2 mm):
Ziel oben 0,4 / 5, unten 0,338 / 1. Die 1 ist die Kontaktlage im Stützmuster. Der echte Abstand ist
0,4: Höhe 0,2 laut `; LAYER_HEIGHT`, Unterkante 3,4.
Bezug oben 0,2 / 2, unten **0,2 / 3**.

### Betrifft das Kunden mit echtem Rat?

Der Rat schlägt unten nie 0 vor. Er schlägt 2 vor, wenn die Stütze auf dem Modell steht und die
Grundlage darunter liegt (`advise.py:989-996`). Sonst schweigt er, und es gilt der Herstellerwert.
Bambu führt selbst 2, der Rat schreibt dort also nichts. Der Kunde bekommt unten 3 Lagen, wie mit
dem Herstellerprofil allein. Eine 0, die der Kunde selbst wählt oder die ein Profil führt, wird
richtig ohne Trennschicht gedruckt. Der Abstand unten gilt je Objekt genau, solange die Stütze eine
eigene Schichthöhe hat.

Abweichend vom Geschriebenen ist nur die Zählung unten: geschrieben n, gedruckt n+1. Das gilt auch
für Orca-Familie-Profile mit Grundlage 0 oder 1, bei denen der Rat 2 schreibt: Dort werden es 3.
Schaden entsteht dadurch nicht, unter dem Fuß liegt nur eine dichte Lage mehr.

### Nebenbefund Reinigungsturm (natürlicher Lauf, zwei Filamente)

Mit Turm liegt die Stütze auf den Schichten des Modells, obwohl im Kopf
`independent_support_layer_height = 1` steht (Tooltip `PrintConfig.cpp:6000-6001`: „invalid when
the prime tower is enabled“). Bambu rundet dann auf die nächste Schicht
(`SupportMaterial.cpp:1698-1718`). Am Bezug (PETG) wurde aus den geschriebenen 0,28 deshalb **0,2**:
Trennschicht bis 12,8, Modell ab 13,0. Den Fall kennt der Arbeitsstand schon
(`writer.py:2763-2785`, `export.support_gap_rounded`, noch nicht eingecheckt, jünger als der Lauf).
Der Befund sagt es dem Kunden. Der geschriebene Wert bleibt aber krumm, und Bambu rundet dann
selbst, auch unter die Materialgrenze. Beispiel PLA mit 0,08er Schichten: Der Rat ist 0,10 (Minimum).
Bambu rundet 1,25 Schichten auf 1, also 0,08, und das liegt unter `support_gap_min` 0,10. Rechnet
Solidon in diesem Fall in ganzen Schichten wie bei Cura, ergibt `support_gap_target` 0,16.

## Fix-Vorschläge

**Solidon (app/):** für Punkt 1 und 2 nichts nötig.
- Zählung unten bei Bambu und Orca festhalten, damit niemand „2 geschrieben, 3 gedruckt“ für einen
  Fehler hält: Kommentar an `slicer_keys.py:484` und eine Zeile in `.claude/rules/druckrat.md`.
  Eine Ausgleichsrechnung (n−1 schreiben) würde ich nicht einbauen. Die Grundlage aus dem
  Herstellerprofil meint dieselbe Zählung, und mit 1 lässt sich bei Bambu keine einzelne Lage
  erreichen (1 ergibt 2).
- Nebenbefund Turm: Wenn `tower_cause(...)` nicht `None` ist, den Abstand wie bei Cura in ganzen
  Schichten bestimmen. Das heißt `support_gap_in_whole_layers` (`slicer_keys.py:1569`) bzw.
  `support_gap_target` (`advise.py:925ff.`) bekommen den Turm als Eingang, und der Rat
  wird mit diesem Wissen gefragt. Der Befund `export.support_gap_rounded` bleibt.

**Sonde (`gcode_kontakt.py`, `kontakt_je_teil.py`):**
1. `SUPPORT` um `"support transition"` ergänzen (`:30`).
2. Trennschicht je Zelle mit Nachbarschaft prüfen: eine Zelle zählt als „Trennschicht auf Ebene z“,
   wenn eine Trennbahn im Umkreis von mindestens einem halben Bahnabstand liegt. Ersatzweise
   Zellen ≥ Bahnabstand (2 mm), siehe Tabelle oben. So bleiben lockere Trennschichten (Lücke 1,2)
   messbar.
3. Schichthöhe aus dem eigenen Bereich, bei der Orca-Familie besser aus dem `; LAYER_HEIGHT:`
   direkt nach `; FEATURE:` (die Höhe der Bahn, nicht der Abstand zur vorigen Ebene der Platte).
4. Kontaktlage bei 0 unteren Lagen erkennen: „Support interface“ mit Bahnabstand ≈
   `support_base_pattern_spacing` zählt als Stütze.
5. Sollwerte je Programm: Bambu und Orca unten n+1 (für n ≥ 1), oben n, Bambu dazu eine
   Übergangslage.
6. `areas()` fand bei Bambu keine Namen und nahm „links (Cura)“ an. Das stimmte hier, weil das Ziel
   bei x = −26 liegt, ist aber Zufall. Robuster wäre die Zuordnung über die Kennung in
   `; start printing object, unique label id:` und die 3MF.

## Dateien

- `schichten.py`: Bahnarten je Schicht und Seite
- `nachmessen.py`, `nachmessen_fix.py`, `gcode_kontakt_fix.py`: Gegenproben der Messung
- `nachmessen_cura.txt`, `nachmessen_bambu.txt`, `nachmessen_fix.txt`: Ausgaben
- `cura_fein.py`, `cura_fein/fein.gcode`, `cura_fein/engine.log`: Konsolenlauf 0,08 mm
- `support_5.13.0.cpp`, `bambu_*.cpp/hpp`, `orca_SupportParameters.hpp`: Quelltexte
