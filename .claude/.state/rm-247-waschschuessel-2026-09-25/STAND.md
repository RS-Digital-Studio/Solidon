# RM-247 — Waschschüssel: Sonden und Messungen (25.09.2026)

Modell: `F:\3D Dateien\HydroBowl+–+Smart+Fruit+&+Veggie+Washer (1)\washing bowl v1.stl`,
aufrecht (Solidons *Druckoptimal ausrichten*), Centauri Carbon 2, PLA, ElegooSlicer.
Die Übergabe, an der alles gemessen ist, war
`%LOCALAPPDATA%\RS Digital\Solidon3D\cache\sandbox\open-in-slicer\solidon.3mf`.

## Varianten im ElegooSlicer (`variante.py`, je `variante-vN.txt`)

| Variante | Zeit | Stütze gesamt | Leerfahrten Schicht 2 | Stütze im Kanal |
|---|---|---|---|---|
| v0 Solidons Übergabe (Gitter, überall) | 25 h 46 | 967 m | 529 | 22,9 m |
| v1 Elegoo-Vorgaben + Stützen | 13 h 22 | 564 m | 556 | 3,1 m |
| v2 Solidon + Baum | 30 h 14 | 959 m | 911 | 10,5 m |
| v3 Solidon + Baum, nur Bett | 29 h 47 | 889 m | 957 | 6,2 m (Stämme durch die Wand) |
| v4 Solidon + Gitter, nur Bett | 25 h 30 | 876 m | 529 | 0,3 m |
| v5 Baum klassisch (`tree_strong`), nur Bett | 30 h 15 | 908 m | 6 670 | 0,7 m |
| v7 Gitter-Kreuzmuster, nur Bett, Leerfahrt 500 | 25 h 08 | 873 m | 572 | 0,3 m |
| v8 überall, Kreuzmuster, `bridge_no_support` | 25 h 48 | 964 m | 572 | 30,2 m |

„Kanal" ist hier grob die Kugel um den Rohrbogen unter dem Becher (`kammer.json`).
`bilder/` zeigt v0 und v3 (Stützen orange über dem Halbschnitt), was „nur Bett"
gegenüber „überall" verliert (nur der Kanalblock und Krümel im Turm) und das
Stützmuster in Schicht 2 und 3 mit und ohne Kreuzmuster.

## Sonden

- `sonde2.py <stl>` — Solidons Druckempfehlung am Modell wie im Druckdialog,
  dazu `model_support` mit Laufzeit.
- `offenheit.py bowl` — die zwei verworfenen und das gewählte Maß (Offenheit,
  lichte Weite) an der Schüssel und an sieben Probekörpern.
- `variante.py <name> key=wert …` — die Übergabe mit geänderten Werten
  schneiden und auswerten; `__elegoo=1` legt Elegoos CC2-Werte darüber
  (`elegoo_ref.json` erzeugt die Sonde in `sonde_empfehlung.py` nicht mehr mit;
  sie stammt aus den Systemprofilen unter `%APPDATA%\ElegooSlicer\system\Elegoo`).
- `stuetz3d.py`, `stuetz_schnitt.py`, `erste_schichten.py` — Bilder aus dem G-Code.

## Endprobe (`endprobe.py`)

Solidons eigene Übergabe mit angenommenen Vorschlägen (Leerfahrt 150 → 500, Stützen Gitter, nur vom Bett) über `handover.project_settings` in den ElegooSlicer: 25 h 08, 415 g, 873 m Stütze, Schicht 2 mit 572 Leerfahrten, 0,3 m im Kanal. `bilder/endprobe-solidon-uebergabe.jpg`: Wasserweg frei, Mittelturm und Unterseite vom Bett gestützt.
