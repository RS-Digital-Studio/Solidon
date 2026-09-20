# Prüfkörper der P2.7-Sonden

Je Fall: Baustein, Parameter (alles Weitere Vorgabe des Schemas), Träger,
unabhängiger Sollwert und die Sonde, die ihn misst. Die Sollwerte sind
Analytik aus den Normteilmaßen (`app/core/knowledge/data/standards.toml`)
und den Bausteinformeln — nicht aus dem Prüfling. Wer einen Fall in eine
Regression übernimmt, nimmt Parameter und Sollwert von hier und den Bauweg
aus `_probe.py`.

Konstanten, die in Sollwerten stehen: `BOOLEAN_OVERLAP` = 0,01 mm,
`INSERT_LEAD_IN` = 0,5 mm, `shapes.SEGMENTS` = 48, `polygon_ratio(48)` =
0,997147, `MAX_FACET_SAG` = 0,05 mm, `_SEAL_SAG` = 0,00625 mm.

## Träger

| Träger | Aufbau | Sonde |
|---|---|---|
| exakte Platte | `create_brep_box` 40 x 30 x 10, `drill_brep_hole` Ø5 bei z = 10 (am PETG-Profil kompensiert auf Ø5,2, durchgehend); V = 11787,628337 | S1, S8 |
| geneigte Platte | dieselbe, `rotate_object` Achse x, 30° | S8 3d |
| zwei Bohrungen | dieselbe, zweite Bohrung Ø5 bei x = 12 | S8 3e |
| Kundenweg §5.1 | dieselbe, `fillet_edges` R3, `shell_exact` Wand 2 (V = 4761,0477, 12 face, 8 fillet, 1 hole, 1 pin) | S8 4 |
| Block für Innengewinde | `edit.box` 20 x 20 x 8 unter der Mündung | S3 |

## Verbindungen (S3)

| Baustein | Parameter | Sollwert |
|---|---|---|
| `screw_hole` | M4, depth 10, countersink, head_room 2 | V = π·2,25²·10,01 + (Kegel 2,25→4,0 h 1,75 − π·2,25²·1,75) + (π·4² − π·2,25²)·2,01 = 255,527983; Ø(z=−8) = 4,5; Ø(z=−1) = 8,0; Ø(Senkmitte) = 6,25; zmax = 0,01 |
| `heatset_m4` | M4, lead_in, extra_depth 0,5 | Tiefe 8,6; Ø unten = 5,6; Mündung = 6,6 − Fase; zmax = 0,01 |
| `nut_trap` | M4, side, slide 12, play 0,2, screw_hole | Schlüsselweite 7,2 (in X), Umkreis 8,3138 (in Y); Höhe 3,3; bottom: um 90° um X gedreht |
| `printed_thread` außen | M6, length 12 | `threaded_rod`: Gang-Ø 6,000 (±1e-4), Kern 4,773; Netzprofil exakt: Kern 4,92, Gang 6,000; Netz V = 285,138 |
| `printed_thread` innen | M6, length 8, play 0,2 | Werkzeug-Gang-Ø 6,2; z −8..0 |
| `printed_screw` | M5, length 12, Sechskant | zmax = 5,0 (Kopfhöhe), zmin = −11,99 |
| `printed_screw` | M5, length 12, Senkkopf | Kopfhöhe (10 − 5)/2 = 2,5; zmin = −14,49; Compound 2 Solids |
| `host_cut` Senkung | M5 | Kegel 5,5→10 h 2,25 unter der Mündung; V = 109,121257 |
| `printed_nut` | M5, play 0,2 | Höhe 4,7; Achse frei |

## Mechanik (S4)

| Baustein | Parameter | Sollwert |
|---|---|---|
| `barrel_hinge` | pin 4, width 24, reach 12, wall 2,5, play 0,3 | 2 Solids; gap 0,3; outer = 4 + 2·(0,3 + 2,5) = 9,6; zmax = 4,8 + 2 + 0,3 + 2,5 |
| `bearing_seat` | 608, fest, grip 0,1 | Sitz-Ø = 22 − 0,1 = 21,9, Tiefe 7; Netz/exakt = 0,997147 ± 1e-6 |
| `dowel` pin | Ø6, length 8, chamfer 0,6, rund/hex/dovetail | Bounds ≤ Ø; oben min(Apothem, 3 − 0,6) |
| `dowel` bore | Ø6, length 8, chamfer 0,6, play 0,2 | Ø 6,2 unter der Mündung; Fase weitet auf 7,4 |
| `hinge_eye` | pin 3, width 8, reach 8, wall 2, play 0,2 | Wand hinter der Bohrung exakt 2,000; Netz 2,0043 |
| `latch` | width 6, depth 1, height 3, play 0,2 (negative: +0,2) | V = 9,0 bzw. 12,288; Punktproben Netz = exakt |
| `living_hinge` | 30, leaf 15, thickness 2, film 0,4, gap 1,5 | V = 30·31,5·2 − 30·1,5·1,6 = 1818 |
| `snap_connector` | Ø6, length 9, play 0,2, pin/bore | thickness = min(0,9, (room − 0,2)/3); Rastkante zwischen Mündung und −catch |
| `snap_fit` | 8, 16, 1,6, 1,2, 35° | V = 8·(1,6·16 + 1,2·h/2), h = 1,2/tan 35° |

## Befestigung (S5)

| Baustein | Parameter | Sollwert |
|---|---|---|
| `foot` | Ø10, h 3, chamfer 0 → h/5 | Standende oben Ø 10 − 2·0,6 = 8,8 |
| `foot` pocket | Ø10, h 3, play 0,2 | Sitz Ø 10,2 unter der Mündung; Schräge `POCKET_LEAD` |
| `keyhole` | M4, drop 8, depth 4, head_room 2,5, play 0,2 | Einstieg Ø 7 + 0,8; Schlitz in −Y; über dem Kopfkanal nur Schaft Ø 4,5 frei |
| `magnet_pocket` | 8x3, play 0,2, grip 0,15 | Öffnung 7,85 < Tasche 8,2; Lippe `MAGNET_LIP_HEIGHT` |
| `wall_mount` | 30 x 25 x 3, M4, 2 Löcher, lip 12 | V = 2250 + 1080 − 2·π·2,25²·3 |
| `pegboard_hook` | skadis, 2, steps 1, latch, plate 0, play 0,2 | 2 Solids; Bounds = Netz ± 0,0056 (Sag) |
| `profile_clamp_shell` | Kreis Ø20,25, depth 40, wall 4, lower, M4, play 0,2 | Außen-Ø 28,25; Hälfte endet y = −0,5 |
| `profile_clamp_liner` | Kreis Ø20, thickness 2, flange 1,2/1,5, rear 2, grip 0,1 | Länge 39,5; Bund 0..1,5 breiter als Kern |

## Struktur und Kabel (S6)

| Baustein | Parameter | Sollwert |
|---|---|---|
| `cable_clip` | cable-5, width 8, wall 2, play 0,2 | Bügelwand seitlich exakt 2; Außenbreite 9,2 (Netz 9,2086) |
| `cable_gland` | cable-5, wall 3, play 0,2, relief | Klemmspalt 0,8·5 = 4; am 40 x 40 x 3-Träger V = 4800 + 11,2·19·5,2 − π·2,6²·3 − 4·13·5,2 − 0,01·(π·2,6² − Rechteck∩Kreis) |
| `gusset` | legs 12, wall 2 | V = t·72, t = max(2·RIB_SHARE, min(2, MIN_RIB)) |
| `rib` | 20 x 10, wall 2, fillet 2 | V = t·(200 + 4) |
| `profile_tongue` | 2020, length 20, lead_in 1,5, play 0,2 | Hals = slot − 0,2, Kopf = core − 0,2 |
| `organizer_tray` | 120 x 80 x 40, wall 3, floor 3, R8 | V = (9600 − (4−π)·64)·40 − (8436 − (4−π)·25)·37 = außen·40 − innen·37; 8 Zylinderflächen |
| `organizer_rim` | 120 x 80 x 3, thickness 3, R8 | V = (außen − innen)·3 |
| `organizer_foot` | Ø18 h 11, Zapfen Ø13 x 8 | V = π·81·11 + π·42,25·8; Netz/exakt = 0,997147 |
| `seal_groove` | Rechteck 20 x 12, width 3, depth 2 | V = ((23·15 − (4−π)·2,25) − 17·9)·2 = 380,137167 |
| `seal_gasket` rect | wie oben, 2,6 x 2,4 | Band 2,6 x 2,4 auf z 0..2,4 |
| `seal_gasket` round | wie oben, height 2,4 | V = 64·π·1,44 − 4·(4/3)·1,728 + 4·(π/3)·1,728 = 287,551408 |
| `seal_gasket` round, Kreisweg Ø20 | height 2,4 | Torus V = 2π²·10·1,44 = 284,244607; Netzabstand ≤ 0,05625 |

## Kalibrierung (S7)

| Baustein | Parameter | Sollwert |
|---|---|---|
| `fit_ladder` | Ø6, steps 4, first 0,1, step 0,05, height 8 | 2 Solids; Bohrungen 6,10 / 6,15 / 6,20 / 6,25 |
| `wall_ladder` | 0,42, steps 6, height 15, length 25 | V = width·25·2 + Σt·25·15 = 4630,5; dünnste Wand 0,42 |
| `overhang_fan` | 20°, step 10°, 6, width 8, length 15 | letzte Rampe 70°: Unterseite auf der Winkelgeraden |
