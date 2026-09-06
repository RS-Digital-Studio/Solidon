# Kegelfunde in `peg.stl`

## Ergebnis

Das wasserdichte Einteilnetz hat 504 Dreiecke und ist nur 4 mm dick. Der alte
Stand `final-source-v4` und der neue Normalenfilter veröffentlichen dieselben
sechs Kegel mit denselben Parametern. Die symmetrische Anzahl allein beweist
die Form noch nicht.

`cone_1`, `cone_2`, `cone_5` und `cone_6` sind berechtigte Teilkegel: zwei
Kreisbogengrößen auf beiden Breitseiten, jeweils etwa 90° Öffnungswinkel. Alle
Patchvertices liegen bis höchstens 0,0125 mm auf dem eingepassten Kegelmantel;
nach Berücksichtigung der Facettenauflösung bleibt kein Normalenausreißer. Die
Gegenpaare stimmen in Dreieckszahl und Durchmesser und ihre Achsen zeigen bis
auf höchstens 0,768° entgegengesetzt.

`cone_3` und `cone_4` sind Falschpositive. Das jeweilige Fasenband ist zwar
zusammenhängend, symmetrisch und hat nahezu konstante 45° Flächenneigung. Es
gehört aber nicht zu einem einzelnen Kreiskegel: Bei nur 0,5025 mm
Axialausdehnung variiert der Abstand zur behaupteten Achse um 4,2680 mm; ein
Patchvertex liegt 4,0698 mm neben dem eingepassten Kegelmantel. Der bisherige
Fit misst nur Dreiecksschwerpunkte und mittelt diesen Widerspruch auf einen
Rückstand von 0,0276. Die neue Normalenprüfung zieht bei groben Dreiecken deren
Winkelauflösung ab und kann diesen fehlenden gemeinsamen Mantel daher ebenfalls
nicht belegen.

## Konsequenz

Der Kegelfit braucht ergänzend den bereits verwendeten dimensionslosen
Punktabstandsvertrag an allen Patchvertices. Das ist keine neue Winkel- oder
Größenschwelle: Lage, Einheit und Maßstab fallen heraus, und echte grobe
Teilkegel besitzen dieselbe Spitze und erfüllen die Gleichung an ihren
Vertices. Der permanente Test verwendet eine selbst erzeugte nichtkreisförmige
45°-Profilfase als Negativfall und einen groben echten 90°-Teilbogen in beiden
Flächenrichtungen als Positivfall. Die Kundendatei bleibt nur lokaler
Abnahmebeleg.

## Beleg

- Original: `C:\Users\rober\Downloads\peg.stl`, SHA-256
  `758acc335b66003a805a238af9e4259c7a844535005e4c585d975c067c036b14`
- Alte UI-Auskunft:
  `final/gfx/file-09/result.json`
- Vollständige Messwerte:
  `peg-cone-profile-diagnosis.json`
