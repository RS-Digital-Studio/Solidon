# Drache: Kanalsperre an Figuren (RM-566)

Roberts Drache (`F:\3D Dateien\Drache.p3d`, Quelle darin `sources/src_1/next.3mf`,
2,9 Mio. Dreiecke) druckte am Centauri Carbon 2 mit übernommenen Vorschlägen Kiefer,
Kinnstacheln und Flügelbögen in die Luft. Ursache war die Kanalsperre der Übergabe.
Das Warum steht in `konzepte/begruendungen/regel-schichtanalyse.md`, die Nachweise im
Archiveintrag RM-566.

Alle Sonden nehmen als erstes Argument die Code-Wurzel (Worktree), damit derselbe Lauf
gegen den alten und den neuen Stand geht. Aufruf immer mit `PYTHONUTF8=1` und dem
Interpreter des Hauptklons.

| Sonde | Was sie misst |
|---|---|
| `extract.py <übergabe.3mf>` | zieht Körper und Stützsperre einer Übergabe als STL heraus |
| `sonde_rat.py <wurzel> <modell>` | Stützbedarf, Kanalstücke, Vorschläge und Sperrvolumen wie Druckdialog und Export (CC2, PLA) |
| `sonde_decken.py <wurzel> <modell>` | je Kanaldecke Fläche, Lage, Höhe und ob sie sich selbst schließt |
| `schnittbild.py <wurzel> <modell> <x> <y> <halb> <z,…> <bild.png>` | Schichtschnitte mit Überhangstücken: rot Kanal, orange auf dem Modell, blau zum Bett |
| `coverage.py <körper.stl> <sperre.stl> [winkel]` | Anteil stützbedürftiger Dreiecksfläche innerhalb einer Sperre |
| `gcode_stuetzen.py <wurzel> <netz.stl> <aus.json> <gcode…>` | Anteil der Überhangfläche mit Stützbahn bis 1,2 mm darunter, je 10-mm-Band, dazu Inseln und die frei hängenden Stücke |
| `gcode_im_kanal.py <körper.stl> <bereich.stl> <gcode…>` | Stützbahn innerhalb eines Bereichs (der Sperrkörper der Übergabe) — Stütze im Kanal |
| `einstellungen.py <aus.json> <name=gcode…>` | was ein Slicer wirklich druckt: Temperaturen, Lüfter je Schicht, Tempo je Bahnart, Beschleunigung, Rückzug, Z-Hub, dazu die Konfiguration |
| `bericht_einstellungen.py <matrix-ordner> <einstellungen.json> <bericht.md>` | Tabelle je Slicer mit Herstellerprofil, gemessenen Werten, Abweichungen und Vorschlägen |
| `korpus_alle.py <wurzel> <aus.jsonl>` · `korpus_kanal.py` · `korpus_vergleich.py` | Kanalfrage und Vorschläge über `F:\3D Dateien`, alter gegen neuen Stand |
| `korpus_sperre.sh` (aus dem Prüfordner) | Korpusfälle, deren Sperre entfällt: alter und neuer Stand durch ElegooSlicer, Stützbahn im alten Sperrkörper |
| `sonde_kanalraum.py <wurzel> <netz.stl> <winkel>` | Kanalstücke, gesperrte Säulen und Sperrvolumen bei einem Stützwinkel, ohne Slicer (Cura 50°, Orca-Familie 60°, Prusa 55°) |
| `sonde_saeulen.py <wurzel> <netz.stl> <winkel>` | je gesperrte Säule Höhe, Landung, Fläche und Lage |
| `sonde_bild.py <wurzel> <netz.stl> <winkel> <x> <y> <halb> <z,…> <bild.png>` | Schichtbild mit Kanalfrage und Sperrraum bei einem Stützwinkel |
| `zeige_kanal.py <körper.stl> <bereich.stl> <gcode> <z,…> <bild.png>` | Körper, Sperrbereich und Stützbahnen einer Druckdatei übereinander |
| `gcode_auflage.py <aus.json> <gcode…>` | wo die Stütze aufsetzt: Fläche und Füße auf dem Modell (Narben, schwer lösbar) gegen das Bett |
| `matrix_organisch.py <wurzel> <modell> <ordner> <kombis> [<bambu-wert>]` | Matrix mit `support_style` für Bäume; belegte, dass Bambu Studio und Creality Print `default` ohnehin organisch lesen |
| `zeige_lauf.py <json…>` | Kurzausgabe von `gcode_stuetzen.py` je Lauf, Slicer und Variante, mit dem Anteil ohne Kanaldecken |
| `sonde_gewoelbe.py <wurzel> <netz.stl> <winkel> <x> <y> <z>` | ob die Decke über einem Punkt schließt, mit Grundriss |
| `sonde_kinn.py <wurzel> [<unterseite> …]` | Stützbedarf an einer schrägen Unterseite: Streifen, Decke, Streifenbreite (RM-570) |
| `sonde_zeit_bedarf.py <wurzel> <netz.stl>` | Zeit von `support_need` bei 0,2 und 1,0 mm |
| `messe_kandidat.sh <ordner>` · `messe_paar.sh <alt> <neu> <name>` | Endmessungen eines Matrixordners; Stütze im alten Sperrkörper alt gegen neu |

`gcode_stuetzen.py` meldet zwei Anteile: alle Überhangstücke und die außerhalb
der Kanaldecken (`open_share`, nach der Kanalfrage der Code-Wurzel). Verglichen
wird der zweite — die Stütze unter einer Kanaldecke soll fehlen.

Die Matrix über alle Slicer läuft mit `tools/matrix_unit.py <wurzel> <modell> <ordner> heim`
und `GESAMT_BEHALTEN=1`, sonst löscht das Werkzeug unauffällige G-Codes, die
`gcode_stuetzen.py` braucht. Das Netz für `gcode_stuetzen.py` ist der Körper aus der
Übergabe (`extract.py`); die Lage auf dem Bett liest die Sonde aus dem G-Code.
