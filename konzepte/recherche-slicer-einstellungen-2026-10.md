# Slicer-Einstellungen nach Modell — Recherche und Abgleich mit Solidon

> **Stand 08.10.2026, datierte Ausgangsbefunde.** Daraus gebaut sind RM-580
> (Mindesttempo für Spitzen), RM-581 (Bäume, wo kleine Überhänge auf dem Modell
> ansetzen) und RM-582 (Ränder ohne Stütze); die übrigen Lücken stehen als
> RM-583 bis RM-589 im Register von `ROADMAP.md` und verweisen auf die Nummern
> unten. Die Spalte „Solidon“ beschreibt den Code vor diesen drei Punkten.

Auftrag: Welche Slicerwerte verlangt die Geometrie anders, als der
Hersteller sie vorgibt, und welche davon schreibt Solidon heute? Schwerpunkt Stützen
(keine Spuren, keine unerreichbaren Stellen).

**Quellenlage.** Netzquellen: Prusa Knowledge Base, OrcaSlicer-Wiki und Quelltext,
UltiMaker-Support, Teaching Tech, Foren von Bambu Lab, Prusa, Creality und UltiMaker,
dazu All3DP, Sovol, Wevolver, Polymaker. **Reddit war nicht abrufbar** (Domäne für den
Abrufdienst gesperrt), das **Bambu-Lab-Wiki** ebenso nicht (HTTP 402); Bambu-Aussagen
stammen deshalb aus dem Bambu-Forum und aus Bambus Konfigurationsblock. Standardwerte
sind, wo möglich, **gemessen statt zitiert**:

- PrusaSlicer 2.9.6: `prusa-slicer-console --help-fff` (Programmvorgabe) und
  `resources/profiles/PrusaResearch.ini` (Herstellerbündel, ausgezählt).
- UltiMaker Cura 5.13: `share/cura/resources/definitions/fdmprinter.def.json`.
- OrcaSlicer: `src/libslic3r/PrintConfig.cpp` auf GitHub (Programmvorgabe).
- Herstellerprofile der Orca-Familie: Konfigurationsblock der Prüfläufe „standard“ in
  diesem Ordner — ElegooSlicer 1.5.3.5 (Centauri Carbon 2, Elegoo PLA), Bambu Studio
  (Kopfzeile 02.08.02.61, P1S, Bambu PLA Basic), Creality Print 7.3.0 (K1, Hyper PLA),
  OrcaSlicer 2.4.2 (Anycubic Kobra 2, Generic PLA), dazu PrusaSlicer 2.9.6 (MK4S
  0.20mm SPEED) und SuperSlicer 2.5.59.13 (MINI).

**Legende „Solidon“** (Zweig `einstellungen/nach-modell` vor RM-580 bis RM-582):

| Kürzel | Bedeutung |
|---|---|
| **Rat** | Zuordnung in `export/slicer_keys.py` **und** Regel in `slice/advise.py`; geschrieben, sobald der Kunde den Vorschlag übernimmt (`PrintSettings.accepted`) |
| **Feld** | Zuordnung vorhanden, der Kunde kann den Wert im Druckdialog setzen (`PrintSettings.chosen`), aber keine Regel schlägt ihn aus der Geometrie vor |
| **abgeleitet** | Solidon schreibt den Schlüssel als Folgewert eines anderen (Cura-Formeln in `handover._for_supports`, Stützbahnbreite mit der Dichte, Baumspitze auf Gültigkeit) |
| **Hersteller** | keine Zuordnung — es gilt das Herstellerprofil bzw. die Programmvorgabe |

Grundregel heute (`types.PrintSettings`, Konzept Herstellerprofil): Über ein
Herstellerprofil geht nur, was in `chosen` oder `accepted` steht. Bei Cura ohne
Herstellerkette (Prüflauf Sovol SV06) ging Solidons ganzer Satz hinaus.

---

## 1. Kurzfassung — die 15 wichtigsten Lücken

Werte, die Solidon heute beim Hersteller lässt (oder nur als Feld ohne Regel führt),
obwohl die Geometrie einen anderen verlangt. Reihenfolge nach Wirkung auf Roberts Ziel:
erst Spuren und Erreichbarkeit der Stützen, dann Oberfläche und Maß.

| # | Problem | Geometrie-Auslöser | Einstellung: Orca-Familie · PrusaSlicer · Cura | Empfohlener Wert | Solidon heute | Beleg |
|---|---|---|---|---|---|---|
| 1 | Stütznarben bzw. verschweißte Stützen an Sichtflächen | Stützen nötig und Schichthöhe ≠ 0,2 mm (Stufe fein/Entwurf, variable Schicht); Material PETG | `support_top_z_distance` (mit `independent_support_layer_height = 1`) · `support_material_contact_distance` · `support_top_distance` über `support_z_distance` | PLA ≈ 1 × Schichthöhe, nie unter 0,1, Deckel 0,25 mm (Prusa-Bündel: 0,17 bei 0,10–0,15; 0,2 bei 0,2; 0,25 ab 0,25). PETG 1,25–1,5 × Schicht (0,25–0,3 bei 0,2). Cura nur ganze Schichten | Feld `support.z_gap`, kein Rat (nur Warnung unter einer Schicht) | [P1], [L1], [F3], [F9], [F10], [U1] |
| 2 | Fußabdrücke, wo Stützen auf dem Modell stehen | `on_model` aus `advise._from_geometry` (Insel, Feld oder lange Brücke über dem Modell) | `support_bottom_z_distance`, `support_interface_bottom_layers` · `support_material_bottom_contact_distance`, `support_material_bottom_interface_layers` · `support_bottom_distance`, `support_bottom_enable`/`support_bottom_height` | unterer Abstand = oberer; 2 untere Kontaktlagen (MK4S-Profil hat 0) | Hersteller (Prusa: Abstand folgt oben bei 0; Cura: aus `z_gap` gespiegelt) | [O2], [P1] |
| 3 | Unter großen flachen Decken hängen die ersten Bahnen durch — an kleinen, gewölbten Flächen sitzt die Kontaktschicht zu fest | größtes Überhangstück (`SupportNeed.patch`) groß und flach gegenüber klein/gekrümmt | `support_interface_spacing` (+ `support_interface_top_layers`) · `support_material_interface_spacing` · `support_roof_density` bzw. `support_roof_line_distance` | flache Decke: 0,1–0,2 mm Lücke, 3 Lagen; kleine/gewölbte Flächen: 0,4–0,5 mm, 2 Lagen | Hersteller (Orca-Familie 0,5, Prusa 0,2); Cura fest 3 × Bahnbreite (≈ 33 %) | [P1], [F6], [O2] |
| 4 | Stützart passt nicht zur Fläche: Bäume unter flachen Decken (raue Unterseite), Gitter auf Figuren (Narben) | großes flaches Stück über dem Bett gegenüber vielen Inseln/Figur | `support_style` (`tree_hybrid`, `organic`, `snug`) · `support_material_style` (`snug`, `organic`) · `support_structure` | flache Decke: Orca `tree_hybrid` oder normal/`snug`; Figur, verstreute Inseln: `organic`; Prusa `snug` statt `grid` | Rat nur `tree`/`grid`/`auto`; der Stil bleibt beim Hersteller | [O3], [P1], [U1] |
| 5 | Bäume kippen oder brechen ab | hohe Stützen (Unterseite weit über dem Bett), wenig Fuß, schwere Überhänge | `tree_support_wall_count`, `tree_support_branch_diameter(_organic)`, `tree_support_branch_diameter_double_wall`, `tree_support_brim_width`/`tree_support_auto_brim` · `support_tree_branch_diameter`, `support_tree_branch_diameter_double_wall`, `support_tree_angle` · `support_tree_bp_diameter`, `support_tree_branch_diameter` | ab ~100 mm Stützhöhe 2 Wände; Doppelwand ab 3 mm Astquerschnitt (Prusa-Vorgabe; MK4S-Profil 8); Ast 3 statt 2 mm; Baum-Brim 3–5 mm; Astwinkel ≤ 40° | Hersteller | [P2], [F6], [F7], [F8] |
| 6 | Punkte und Fasern an feinen Details unter Baumspitzen | feine Überhänge (Schuppen, Kinn, Krallen) mit schmaler Kontaktfläche | `tree_support_tip_diameter`, `tree_support_top_rate`, `tree_support_branch_distance_organic` · `support_tree_tip_diameter`, `support_tree_top_rate`, `support_tree_branch_distance` · `support_tree_tip_diameter`, `support_tree_top_rate`, `support_tree_min_height_to_model` | Spitze klein, aber ≥ Stützbahnbreite (Vorgabe 0,8; Prusa-Bündel 0,5–1,6 je Düse); Kontaktdichte über Kontaktlagen statt über `top_rate` erhöhen; Cura-Mindesthöhe zum Modell ≥ 3 mm | Hersteller (Orca: Spitze nur auf Gültigkeit gehoben) | [O1], [P2], [U1] |
| 7 | Kontaktschicht verschweißt mit dem Teil, vor allem PETG | Stützen an Sichtflächen, `on_model`, PETG | `support_material_interface_fan_speed` · — (nur SuperSlicer) · `support_fan_enable` + `support_supported_skin_fan_speed` | 100 % während der Kontaktschicht bzw. der Haut darüber | Hersteller (alle vier Orca-Profile −1 = aus) | [O4], [L2] |
| 8 | Spitzen kühlen trotz Mindestschichtzeit nicht ab | kleine Querschnitte oben (Drache: obere 12 mm, 0,1–1,3 s je Schicht) | `small_perimeter_threshold` + `small_perimeter_speed` · `small_perimeter_speed` · `cool_lift_head`, `cool_min_temperature`, `small_hole_max_size` | Orca-Schwelle 6,5 mm Radius bei 50 % (alle vier Profile: 0 = aus); Prusa 15–25 mm/s (MK4S SPEED: 170); Cura Kopf anheben, Kleinschicht-Temperatur 5–10 °C tiefer | Rat `cooling.minimum_speed` und `minimum_layer_time`; Rest Hersteller | [O7], [L1], [F12], [G1] |
| 9 | Treppenstufen auf flachen Kuppeln, verlorene Feinheiten | flache Schrägen nahe der Waagerechten; feine Details nur in Teilhöhen | Orca-Familie: `Metadata/layer_heights_profile.txt` bzw. `layer_config_ranges.xml` in der 3MF · `Metadata/Slic3r_PE_layer_heights_profile.txt` · `adaptive_layer_height_enabled` (+ `_variation`, `_threshold`) | innerhalb der Maschinengrenzen (Orca-Profile 0,04–0,08 bis 0,28–0,32 mm), geglättet | schreibt nichts | [P3], [O8], [L3], [L2] |
| 10 | Kissen oder Löcher in Deckflächen | feine Stufe (0,12 mm) mal Lagenzahl < 0,8 mm; flache Oberseiten über dünner Füllung | `top_shell_thickness` · `top_solid_min_thickness` · `top_thickness` | Mindestdicke 0,8–1,0 mm | nur Lagenzahl `shell.top_layers` | [O9], [L1], [F14] |
| 11 | Lange Brücken hängen durch | Brücke ≥ 15 mm (`advise._from_spans`, Befund `slice.long_bridge`) | `thick_bridges`, `bridge_flow`, `bridge_density`, `enable_extra_bridge_layer` · `thick_bridges`, `bridge_flow_ratio` · `bridge_skin_material_flow`, `bridge_enable_more_layers` | dicke Außenbrücke an, Fluss 0,85–0,95, zweite Brückenlage „external_bridge_only“ | nur `speed.bridge` und Brückenlüfter | [O10], [L1] |
| 12 | Steile ungestützte Überhänge rollen sich auf | Flächen zwischen ~45° und Stützgrenze bleiben ohne Stütze; ABS/ASA/TPU | `extra_perimeters_on_overhangs`, `overhang_reverse` (+ `_threshold`) · `extra_perimeters_on_overhangs` · — | an, wo solche Flächen vorkommen; Umkehr bei schrumpfenden und weichen Materialien | Hersteller (in allen gemessenen Profilen aus) | [O5], [L1] |
| 13 | Bohrungen und Stifte passen nicht | Passungen, Bohrungen unter ~10 mm, Passflächen am Bett | `xy_hole_compensation`, `xy_contour_compensation`, `hole_to_polyhole`, `elefant_foot_compensation` · `xy_size_compensation`, `elefant_foot_compensation` · `hole_xy_offset` (+ `_max_diameter`), `xy_offset_layer_0` | nur nach Kalibrierung, abgestimmt mit dem Spiel aus dem Materialprofil (kein doppeltes Spiel); Polyholes für kleine Bohrungen; Elefantenfuß 0,1–0,2 | Rat nur Außenwand (genau, langsam, zuerst); Kompensation Hersteller | [O6], [P4], [F15] |
| 14 | Naht als senkrechte Linie auf der Schauseite einer Figur | Figur mit Vorderseite, Außenwand ohne Kanten | `seam_position = back` · `seam_position = rear` · `z_seam_type = back` | hinten; bei glatten Rundungen zusätzlich Schrägnaht (Regel vorhanden) | Feld `shell.seam_position`, kein Rat | [O11], [P5] |
| 15 | Sichtbare Bahnen auf flachen Sichtoberseiten | große, zur Platte parallele Oberseite ohne Passung (Schild, Deckel, Box) | `ironing_type = topmost` · `ironing_type = topmost` · `ironing_enabled` + `ironing_only_highest_layer` | oberste Fläche bügeln, Abstand 0,1 mm | Rat nur bei bündiger Passung (`_from_fits`) | [P6] |

Nicht in der Liste, weil Solidon es schon abdeckt: Stützen an/aus und Art, „nur vom
Bett“ gegen „überall“, Kanalsperre, Stützwinkel aus der Maschine, Schrägnaht an runden
Wänden, Arachne bei dünnen Stellen, Bahnbreite an schmalen Stellen, langsame erste
Schicht an Stegen, Brim und ruhige Wände an schlanken Teilen, Mindesttempo an Spitzen.
Überhangtempo und Überhanglüfter bremsen alle Herstellerprofile bereits (Arbeitsliste).

---

## 2. Stützen im Detail

### 2.1 Was die Quellen übereinstimmend sagen

- Der **obere Z-Abstand** entscheidet am meisten über Ablösen und Narben; zu klein
  verschweißt, zu groß sackt der erste Überhang durch oder löst sich während des
  Drucks ([P1], [F9], [G2]).
- **Mehr oder dichtere Kontaktlagen** geben eine glattere Unterseite, binden aber fester
  ([P1], [O2]). Prusa und Orca raten, die Kontaktdichte über Kontaktlagen zu erhöhen
  statt über die Astdichte der Bäume ([O1], [P2]).
- **Bäume** setzen mit wenigen Füßen auf und hinterlassen weniger Spuren; **normale
  Stützen** tragen große flache Decken besser ([U1], [O3]). Solidons eigene Messung am
  Drachen: Gitterstützen der Hersteller setzten mit 212 bis 324 mm² auf dem Modell auf,
  Bäume mit 4 bis 66 mm² (`advise.py`, Kommentar am Baum-Rat).
- **Stützsperren wirken nur an den Flächen, die sie berühren**, nicht als Sperrraum
  ([F4]); Bemalen des Hohlraumbodens hält keine Stütze ab, nur die Überhangfläche selbst.
- **„Nur vom Bett“** hält Hohlräume frei, lässt aber Überhänge über dem Modell
  ungestützt ([P1], [F5]).

### 2.2 Schwer zu entfernen, Narben, Rückstände

**Ursache:** oberer Z-Abstand zu klein oder nicht zur Schichthöhe passend, zu dichte
Kontaktlage, zu viele Kontaktlagen, PETG haftet an sich selbst stärker als PLA, zu
warme Kontaktschicht.

**Wo es auftritt:** Sichtflächen auf der Unterseite von Figuren, kleine Kontaktflächen
(die Stütze reißt Material mit), Stützen neben senkrechten Wänden (XY-Abstand), feine
Schichthöhen mit festem Abstand von 0,2 mm (relativ zu groß) oder grobe Schichten mit
0,2 mm (relativ zu klein).

**Abhilfe und Werte — oberer Z-Abstand:**

| Schichthöhe | PLA (Vorschlag) | PETG (Vorschlag) | Was die Herstellerprofile tun |
|---|---|---|---|
| 0,05–0,08 | 0,10 | 0,12–0,15 | Prusa 0,07–0,11 (0,07 ist bei Prusa auch der Wert der löslichen Variante) |
| 0,10–0,12 | 0,12–0,17 | 0,17–0,20 | Prusa 0,17 (13×) bzw. 0,11–0,12 bei 0,12 |
| 0,15–0,16 | 0,17 | 0,20–0,22 | Prusa 0,17 (25×), 0,2 (19×), 0,22 (11×) |
| 0,20 | 0,20 (0,22 für leichteres Lösen) | 0,25–0,30 | Prusa 0,2 (70×), 0,22 (24×); Orca-Familie 0,2 |
| 0,25–0,28 | 0,25 | 0,30 | Prusa 0,25 / 0,28 |
| ≥ 0,30 | 0,25 | 0,30 | Prusa 0,25 (Deckel) |

- Herkunft: Prusa-Bündel ausgezählt (`PrusaResearch.ini`, Paare Schichthöhe/Abstand nach
  Vererbung, [L1]); Prusa-KB nennt 50–75 % der Schichthöhe als brauchbar ([P1]) — die
  eigenen Profile liegen eher bei 100 %; UltiMaker empfiehlt für Stützen aus Baumaterial
  zwei Schichthöhen ([U1]); Creality-Forum: Schichthöhe + 0,025 mm ([F6]);
  MakerWorld-Testmodell: bei 0,2 beginnen, in 0,02-Schritten erhöhen ([F11]);
  Prusa-Forum: PLA mindestens 0,2, PETG mehr, viele nehmen 0,25 ([F9]); Sovol: PETG
  ≈ 1,5 × Schicht, unter 0,10 verschweißt, über 0,35 sackt es ([F10]).
- **PETG-Werte sind Forenwissen, nicht Herstellerwert** — kein gemessenes Orca-Profil
  ändert den Abstand mit dem Material.
- **Cura** rechnet Stützabstände in ganzen Schichten; ein Wert zwischen zwei Vielfachen
  wird gerundet ([G3]). Solidon spiegelt `support_z_distance` auf oben und unten und
  sollte ihn deshalb auf ein Vielfaches der Schicht legen.
- **Orca-Familie:** Ohne `independent_support_layer_height` folgt die Stütze den
  Objektschichten, und ein Z-Abstand unter bzw. zwischen Schichtvielfachen wird nicht
  frei eingehalten (Bambu-Forum, [F2]; genaues Rundungsverhalten je Version am G-Code
  prüfen). Elegoo CC2 führt den Schalter auf 0, Bambu, Creality und Orca auf 1. Mit
  Prime Tower ist er gesperrt.
- **Bambu-Stolperfalle:** Beim Wechsel auf Baum-Hybrid bietet Bambu Studio an, Z-Abstand
  und Kontaktlagen anzupassen; ein Nutzer bekam danach 0 Abstand und 0 Kontaktlagen
  ([F2]). Solidon schreibt beides ausdrücklich, das schützt davor.
- **Lösliches oder anderes Kontaktmaterial** (Bambu „Support for PLA“, PLA unter PETG):
  Abstand 0 und Kontaktlücke 0 ([F2], Herstellerangabe zum Filament). Braucht zwei
  Materialien — für Solidon nur als Hinweis relevant.

**Kontaktlagen:** 2 sind der häufigste Mittelweg ([G2], [F11]); Prusa-Bündel 3 (37×)
oder 4 (24×); Orca-Vorgabe 3, Elegoo/Bambu/Creality 2, Anycubic 3. **Lücke der
Kontaktlinien:** Prusa 0,2 (Vorgabe 0 = geschlossen), Orca-Familie 0,5, Anycubic 0,2;
Creality-Forum 0,1 bzw. 0 bei großen flachen Flächen ([F6]); ein Leitfaden nennt 60–80 %
Dichte, 100 % binde zu fest, 40 % lasse durchhängen ([G2]). Muster: Orca `auto` =
Linien; Prusa Linien; Cura-Vorgabe konzentrisch und voll — Solidon schreibt dort Linien
zu einem Drittel.

**XY-Abstand:** Orca-Familie 0,35 mm, Prusa 50 % (Vorgabe) bzw. 80 % der Außenbahn
(MK4S), Cura 0,7 mm mit „Z vor XY“ und 0,2 mm Mindestabstand unter Überhängen. Bei PETG
0,5 mm ([F3]); an steilen Wänden 0,38–0,4 mm ([F2]); Creality-Forum bis ≥ 1 mm, wenn
Stützen Details berühren ([F6]). Geometrischer Auslöser: Stütze steht dicht neben einer
senkrechten Wand oder einem Relief — dann größer; Überhang direkt an der Wand — dann
braucht es „Z vor XY“ (Cura; bei Bambu nicht einstellbar, [F2]; Creality Print führt
`support_xy_overrides_z`).

**Untere Kontaktlagen** (Stütze steht auf dem Modell): Orca-Wiki — untere Lagen sitzen
dort, wo die Stütze auf dem Modell aufsetzt ([O2]). Gemessen: Elegoo/Bambu/Creality 2,
Anycubic −1 (= wie oben), Orca-Vorgabe 0, Prusa MK4S 0. Ohne untere Lage steht der rohe
Stützfuß auf der Modelloberfläche und zeichnet sie.

### 2.3 Stützen an unerreichbaren Stellen

- **Hohlräume und Kanäle:** Solidon legt eine Stützsperre als Volumen in den Kanal
  (`support.block_channels`, Orca-Teilart `support_blocker`, Prusa `SupportBlocker`,
  Cura `anti_overhang_mesh`) und schlägt „nur vom Bett“ vor, wo nichts über dem Modell
  hängt. Das entspricht dem, was die Foren als einzig verlässlichen Weg beschreiben
  ([F4], [F5]).
- **Was die Sperre nicht abdeckt:** Kontaktlagen, die breiter sind als die gestützte
  Fläche, können in eine Röhre ragen, und die Sperre wirkt dort nicht ([F5]). Orca hat
  `support_expansion` (negativ = schmaler) und `support_interface_not_for_body`; Cura
  `support_interface_offset`. Kein Rat in Solidon.
- **Cura-Bäume:** `support_tree_rest_preference` (Solidon: `buildplate` bei „nur vom
  Bett“, sonst `graceful`) und `support_tree_min_height_to_model` (3 mm) verhindern
  kleine Stützklumpen auf dem Modell ([U1]).
- **Schwellwinkel:** zu flach eingestellt stützt Dinge, die keine Stütze brauchen, auch in
  Hohlräumen. Solidon schreibt den Winkel aus `Profile.overhang_limit_degrees` (Rat aus
  `_from_machine`). Orca-Vorgabe 30° gegen die Waagerechte; Prusa-Bündel 35° (24×);
  Cura 50° gegen die Senkrechte. Daneben: Orca `support_remove_small_overhang` (überall 1)
  und `support_critical_regions_only` (Bäume, nur Spitzen und Kragarme).
- **Brücken nicht stützen:** Orca `bridge_no_support` / `max_bridge_length` (Vorgabe
  10 mm, Bambu-Profil 0 = jede Brücke stützen), Prusa `dont_support_bridges`. Geometrie:
  kurze Brücken über Hohlräumen ohne Stütze lassen, lange stützen — Solidon misst Brücken
  (`open_bridge_width`, `_from_spans`) und könnte `max_bridge_length` aus der längsten
  druckbaren Spanne setzen.

### 2.4 Zu wenig oder falsch gestützte Überhänge

- **„Nur vom Bett“ über dem Modell:** Solidon schaltet in diesem Fall auf „überall“
  (Regel `on_model`, Wedge-Lock und Kinn des Drachen als Belege im Code).
- **Bäume unter großen flachen Decken:** raue, durchhängende Unterseite, „Spaghetti“
  ([O3], Bambu-Forum). Abhilfe: Orca `support_style = tree_hybrid` (normale Stütze unter
  großen flachen Überhängen, Bäume sonst, [O3]) oder normal/`snug` (Prusa: `snug` folgt
  der Überhangform und hält Abstand von den Wänden, [P1]). Solidons Rat schaltet heute bei
  `on_model` immer auf Baum, ohne nach der Größe des flachen Stücks zu fragen.
- **Hybrid und Bambu:** Hybrid gibt kleinen Flächen weiter Bäume; ein steiler, aber großer
  Überhang (≈ 5° geneigt) bekam ebenfalls Bäume — die Zuordnung ist automatisch und nicht
  bemalbar ([F1]).
- **Stützen reichen nicht an den Überhang:** Kontaktlücke und XY-Abstand prüfen ([F2]);
  bei Bäumen hilft ein größerer Astwinkel (mehr Reichweite, weniger Stabilität, [P2]).
- **Erste Schicht über der Stütze sackt:** Kontaktlücke zu groß oder zu wenig Kühlung;
  MakerWorld-Testmodell: Temperatur etwas senken oder Kühlung erhöhen ([F11]).

### 2.5 Bäume: Einstellungen und Werte

| Größe | Orca-Familie | PrusaSlicer | Cura | Wirkung und Empfehlung |
|---|---|---|---|---|
| Astwinkel max. | `tree_support_branch_angle(_organic)`: Vorgabe 40; Elegoo/Bambu/Creality 45 | `support_tree_angle` 40 | `support_tree_angle` = `support_angle` begrenzt 20–85 (Solidon schreibt den Stützwinkel hinein) | flacher = stabiler, steiler = mehr Reichweite ([P2], [O1]); UltiMaker nennt 40° zuverlässig ([U1]). Hohe Stützen 35–40°, Reichweite um das Modell herum 45–50° |
| bevorzugter Winkel | `tree_support_angle_slow` 25 (Elegoo 30) | `support_tree_angle_slow` 25 | `support_tree_angle_slow` = 2/3 Astwinkel | kleiner = senkrechter und stabiler ([P2]) |
| Astdurchmesser | `tree_support_branch_diameter` 5 (Profile 2), `_organic` 2 | 2 | `support_tree_branch_diameter` 5 | dicker = stabiler, schwerer zu entfernen ([P2], [U1]); schwere Überhänge 3 mm |
| Verdickung | `tree_support_branch_diameter_angle` 5 | 5 | `support_tree_branch_diameter_angle` 7 | 0 = gleich dick; etwas Winkel = stabiler ([P2]) |
| Doppelwand ab | `tree_support_branch_diameter_double_wall` (Creality 3) | 3 (MK4S-Profil 8) | — | 0 = nie; niedriger = haltbarer ([P2], [F7]) |
| Spitze | `tree_support_tip_diameter` 0,8 (organisch) | 0,8 (Bündel 0,5–1,6 je Düse) | `support_tree_tip_diameter` = 2 × Stützbahn | Orca lehnt Spitzen schmaler als die Stützbahn ab (Solidon hebt sie, `handover.organic_tree_fitted`) |
| Astabstand | `tree_support_branch_distance` 5; `_organic` 1 (Elegoo 2) | 1 | — | kleiner = mehr Kontaktpunkte, bessere Unterseite, schwerer lösbar ([O1], [P2]) |
| Astdichte | `tree_support_top_rate` 30 % | `support_tree_top_rate` 15 % (Bündel 30 %) | `support_tree_top_rate` 30 mit Dach, sonst 10 | höher = bessere Überhänge, schwerer lösbar; lieber Kontaktlagen ([O1], [P2]) |
| Wände | `tree_support_wall_count` 0 = automatisch (Bambu −1) | — | `support_wall_count` 1 beim Baum | 2 Wände ab ~100 mm Stützhöhe ([F6]) |
| Fuß | `tree_support_auto_brim` 1, `tree_support_brim_width` 3; `raft_first_layer_expansion` | `raft_first_layer_expansion` 3 | `support_tree_bp_diameter` 7,5, `support_brim_*` | breiterer Fuß bei hohen Bäumen; Creality-Forum 2–8 mm Erweiterung ([F6]) |
| Füllung im Stamm | Bambu früher `tree_support_with_infill` | — | `support_tree_max_diameter` 25 | Bambu-Wiki (zitiert im Forum): Füllung macht Bäume sehr stabil, für schwache Materialien wie Silk-PLA empfohlen; die Option ist laut Nutzer seit Studio 1.4 verschwunden ([F8]) |
| Ruheplatz | — | — | `support_tree_rest_preference`, `support_tree_min_height_to_model` 3 | Bett bevorzugen ([U1]) |
| Stilwahl | `support_style`: `organic` (Vorgabe bei Baum), `tree_slim`, `tree_strong`, `tree_hybrid` | `support_material_style = organic` | `support_structure = tree` | Hybrid für große flache Decken, Strong für schwere Überhänge, Organic für Figuren ([O3]) |

**Organisch gegen hybrid:** Organisch spart Material und lässt sich leicht lösen, Prusa
nennt es spurenarm ([P1]); Hybrid legt unter große flache Überhänge normale Stütze
([O3]).

### 2.6 Bäume, die umfallen oder das Modell treffen

- **Zwei Bauarten:** Fuß löst sich vom Bett (Vibration, zu kleine Haftfläche) oder Stamm
  bricht/wird umgestoßen ([F7]).
- **Fuß:** Baum-Brim bzw. Fußerweiterung; ein Prusa-Nutzer stellte fest, dass der
  normale Brim den Fuß organischer Stützen nicht vergrößert ([F12b]); Raft als schwere
  Lösung; Bettreinigung.
- **Stamm:** Astdurchmesser etwas größer, Verdickungswinkel, Doppelwandschwelle senken,
  Astwinkel senken; Bambu „Tree Strong“ statt Auto, oder Z-Abstand 0,25 und 3 Kontaktlagen
  ([F7]).
- **Tempo:** langsamer drucken, wenn der Kopf das Modell in schnellen Richtungswechseln
  durchschüttelt ([F7]). Der Stützentakt selbst ist hoch (Elegoo/Bambu/Creality 150 mm/s,
  Kontaktlage 80 mm/s; Prusa MK4S 120 mm/s, Kontaktlage 50 %) — bei hohen, dünnen
  Bäumen ist das die zweite Stellschraube neben der Geometrie des Baums.
- **Auslöser für Solidon:** Höhe der Stützsäulen (Abstand Unterseite–Bett bzw.
  Unterseite–Modell) und Verhältnis zur Fußfläche; Solidon kennt Inseln und Überhanghöhen
  aus der Schichtanalyse.

### 2.7 Stützsperren und -verstärker

- **PrusaSlicer:** Bemalte Sperren brauchen „überall“ oder „nur vom Bett“ mit
  automatischen Stützen; Verstärker funktionieren auch mit „nur für Verstärker“ ([P7]).
  Sehr kleine bemalte Flächen werden nicht genau eingehalten, weil der Generator auf einem
  Raster arbeitet — kleinerer Musterabstand erhöht die Auflösung ([P7]). Organische
  Stützen gehorchen der Bemalung ([P7]).
- **Solidons Prusa-Weg** schaltet mit Stützen auch `support_material_auto = 1` ein
  (`handover._with_automatic_prusa_support`) — sonst stützt MK4S nur Verstärker.
- **Sperrvolumen:** wirken nur an berührten Flächen ([F4]); Solidons Kanalsperre sperrt
  Raum, in dem die Überhangflächen der Kanaldecke liegen — passt.
- **Verstärker für hohe schlanke Teile:** Bambu-Forum: kleine bemalte Stützpunkte an
  senkrechten Flächen, die das Teil nicht berühren, halten wackelnde Türme ([F13]).
  `support_material_enforce_layers` (Prusa) bzw. `enforce_support_layers` (Orca) stützt
  die ersten n Schichten für Teile mit kleinem Fuß ([P1]).

### 2.8 Kühlung und Material der Kontaktschicht

- **Orca `support_material_interface_fan_speed`:** höhere Drehzahl schwächt die Bindung
  zwischen Stütze und Teil ([O4]); alle gemessenen Profile −1 (aus).
- **Cura `support_fan_enable` / `support_supported_skin_fan_speed`:** Lüfter für die
  Haut, die auf der Stütze liegt (Vorgabe aus, 100 % wenn an, [L2]).
- **Forenrat:** Lüfter während des Stützdrucks nicht abschalten, schlechte Kühlung macht
  die gestützte Unterseite rau ([G2]).
- **Bügeln der Kontaktschicht:** Orca `support_ironing`, Bambu `enable_support_ironing`
  (überall 0). Creality-Forum: kostet Zeit bei ähnlichem Ergebnis ([F6]).

---

## 3. Übrige Einstellungen im Detail

Herstellerwerte in dieser Spalte sind gemessen (Elegoo CC2 · Bambu P1S · Creality K1 ·
Kobra 2 in Orca; Prusa MK4S bzw. Prusa-Bündel). „Solidon“ bezieht sich auf
`types.PrintSettings` und `slicer_keys.py`.

### 3.1 Kühlung kleiner Schichten

- **Auslöser:** kleine Schichtflächen oben (Spitzen, Hörner, Turmspitzen), Teile allein
  auf der Platte.
- **Einstellungen:** Mindestschichtzeit (`slow_down_layer_time` · `slowdown_below_layer_time`
  · `cool_min_layer_time`), Mindesttempo (`slow_down_min_speed` · `min_print_speed` ·
  `cool_min_speed`), Lüfterkurve (`fan_cooling_layer_time` · `fan_below_layer_time` ·
  `cool_min_layer_time_fan_speed_max`), Cura zusätzlich `cool_lift_head` und
  `cool_min_temperature`, Prusa 2.9 `cooling_slowdown_logic` (`consistent_surface` in 11
  Bündelprofilen).
- **Herstellerwerte:** Mindestschichtzeit 4 · 4 · 8 · 8 s; Prusa-Bündel meist 10–20 s;
  Cura-Definition 5 s. Mindesttempo 20 · 20 · 20 · 10 mm/s; Prusa meist 15, Vorgabe 10;
  Cura 10. Lüfterschwelle 80 · 100 · 100 · 100 s.
- **Grenze:** Ist das Mindesttempo erreicht, bremst kein Slicer weiter; die Schicht
  bleibt zu kurz, der Lüfter läuft voll ([O4], Orca-Issue [G1] — Wunsch nach Warten statt
  Kriechen, abgelehnt). Prusa warnt: zu langsam über lange Zeit bringt Hitzestau ([P8]).
- **Abhilfen:** Mindesttempo senken (Solidon: 5 mm/s, Rat), kleine Umfänge langsamer
  (Lücke 8), Cura Kopf anheben, Kleinschicht-Temperatur ([F12]); zweites Teil oder
  Kühlturm daneben drucken ([F12]); Düse so kühl wie möglich, Lüfter 100 % ([F12]).
- **Solidon:** `cooling.minimum_layer_time` (Rat nur, wo keine gilt), `cooling.minimum_speed`
  (Rat), Lüfterkurve als Felder.

### 3.2 Überhänge und Überhangtempo

- **Auslöser:** Wandüberhang in Bahnbreitenanteilen; steile Flächen knapp unter dem
  Stützwinkel; gerundete Unterseiten.
- **Einstellungen:** Orca `enable_overhang_speed`, `overhang_1_4…4_4_speed`,
  `overhang_fan_speed`, `overhang_fan_threshold`, `extra_perimeters_on_overhangs`,
  `overhang_reverse`, `make_overhang_printable`; Prusa `enable_dynamic_overhang_speeds`,
  `overhang_speed_0…3`, `extra_perimeters_on_overhangs`; Cura `wall_overhang_angle`,
  `wall_overhang_speed_factors`, `cool_min_layer_time_overhang`.
- **Herstellerwerte:** Orca-Familie 0/50/30/10 mm/s (Anycubic 0/20/15/10), Lüfter 100 %
  ab 50 % Überhang; Prusa-Vorgabe 15/15/20/25 mm/s. Zusatzwände und Umkehr überall aus.
- **Empfehlung:** Tempo beim Hersteller lassen (Arbeitsliste). Zusatzwände auf
  Überhängen und „Umkehr auf geraden Schichten“ dort, wo steile Flächen ohne Stütze
  bleiben; Umkehr hilft bei ABS/ASA und TPU, kann außen Textur geben — dann nur innen
  (`overhang_reverse_internal_only`) ([O5]). `make_overhang_printable` ändert die
  Geometrie (Kegel statt Überhang, 45–60° laut Wiki) — für Solidon kein Slicerwert,
  sondern eine Op-Frage (Regel 2).
- **Solidon:** Cura-Stufen werden aus Bahnbreite/Schichthöhe nachgerechnet
  (`handover._for_overhangs`); sonst Hersteller.
- **Nachgemessen (RM-587):** Zusatzwände ändern zwischen 45 Grad und der
  Stützgrenze nichts (PrusaSlicer und OrcaSlicer bitgleich), sie wirken unter
  einseitig hängenden flachen Überhängen ohne Stütze. Im Band wirkt die Umkehr.
  Messwerte: `konzepte/begruendungen/regel-druckrat.md`.

### 3.3 Brücken

- **Auslöser:** freie Spannweite (Solidon meldet ab 15 mm), Brücken über Hohlräumen,
  innere Brücken über dünner Füllung.
- **Einstellungen:** Orca `bridge_flow`, `bridge_density`, `thick_bridges`,
  `thick_internal_bridges`, `enable_extra_bridge_layer`, `bridge_speed`,
  `internal_bridge_*`; Prusa `bridge_flow_ratio`, `thick_bridges`, `bridge_speed`; Cura
  `bridge_settings_enabled`, `bridge_wall_material_flow` 50 %, `bridge_skin_material_flow`
  60 %, `bridge_enable_more_layers`.
- **Herstellerwerte:** Fluss 1 · 1 · 0,9 · 0,85; dicke Außenbrücken überall aus, dicke
  innere an; zweite Brückenlage aus. Prusa-Bündel: `thick_bridges` 10 × an, 9 × aus;
  Fluss meist 1 oder 0,95.
- **Empfehlung:** lange Außenbrücken: dicke Brücke an (trägt weiter, sieht rauer aus);
  Fluss leicht unter 1 gegen Durchhängen; zweite Brückenlage mindestens „nur außen“;
  Dichte über 100 % glättet, bis etwa 120 % ([O10]). Lüfter 100 % (Teaching Tech-Basis,
  [T1]).
- **Solidon:** `speed.bridge` (Rat: nicht schneller als die Außenwand), Brückenlüfter
  (Feld), Cura-Schalter `bridge_settings_enabled` (abgeleitet).

### 3.4 Fäden und Rückzug

- **Auslöser:** viele getrennte Inseln je Schicht (Spitzen, Gitter, mehrere Teile),
  Leerfahrten über offene Hohlräume.
- **Einstellungen:** Rückzuglänge/-tempo, Z-Sprung, Wischen, Mindestfahrweg, Wände nicht
  kreuzen, Temperatur.
- **Werte:** Prusa: Direktantrieb ≤ 2 mm, Bowden-MINI 3,2 mm; höheres Tempo hilft, bis
  der Motor Schritte verliert; Z-Sprung klein; Temperatur 5–10 °C tiefer testen ([P9]).
  Teaching Tech: Direktantrieb-PLA-Beispiel 0,4–0,6 mm bestes Ergebnis ([T1]). Orca-Wiki:
  Mindestfahrweg 2–4 mm, schnelle Leerfahrt ([O11]).
- **Herstellerwerte:** 0,8 mm (Bambu/Elegoo/Creality), 2 mm (Kobra 2), Z-Sprung 0,4 mm.
- **Solidon:** Länge, Tempo, Z-Sprung, Wischen, „Wände nicht kreuzen“ als Felder;
  Leerfahrttempo als Rat aus der Maschine. Geometrischer Rat fehlt: bei vielen Inseln
  je Schicht „Wände nicht kreuzen“ einschalten — die Orca-Profile führen es aus (0).

### 3.5 Naht

- **Auslöser:** runde Außenwände ohne Ecke (Solidon: Schrägnaht), Figuren mit
  Schauseite, Stifte in Bohrungen.
- **Einstellungen:** `seam_position` (`aligned`, `aligned_back`, `back`, `nearest`,
  `random`), `seam_gap`, `staggered_inner_seams`, Schrägnaht `seam_slope_*`;
  Prusa `seam_position`, `seam_gap_distance` (15 %), `staggered_inner_seams`,
  Nahtbemalung; Cura `z_seam_type`, `z_seam_corner`.
- **Werte:** Orca-Wiki: Aligned/Aligned Back/Back meist am besten; Aligned Back legt die
  Naht bei Figuren weg von vorn; Random verteilt und kann bei Stiften in Bohrungen die
  Festigkeit verbessern; Nahtlücke 0–15 %; Schräglänge um 20 mm, 10 Stufen ([O11]).
  Prusa: Nearest sucht zuerst eine konkave Ecke ([P5]).
- **Herstellerwerte:** überall `aligned`.
- **Solidon:** Feld `shell.seam_position` (inkl. `rear`), Rat `shell.scarf_seam`.

### 3.6 Erste Schicht und Elefantenfuß

- **Auslöser:** schmale Stege in der ersten Schicht (Solidon-Rat), Passflächen und
  Kanten am Bett, feine Schrift am Boden.
- **Werte Elefantenfuß:** Prusa-KB ≈ 0,2 mm bei 0,4er Düse, offizielle Profile haben
  ihn an; zu groß trennt den Brim vom Teil ([P4]); PrusaSlicer-Vorgabe 0. Orca-Familie
  0,1 · 0,15 · 0,15 · 0,1, über `elefant_foot_compensation_layers` auslaufend ([O6]).
- **Erste Schicht:** Elegoo und Bambu fahren die Füllung der ersten Schicht mit
  105 mm/s; Solidons Rat senkt auf 50 mm/s, wo Stege es verlangen.
- **Solidon:** erste Schicht als Feld/Rat; Elefantenfuß Hersteller. Geometrischer
  Auslöser für eine Abweichung: Passung oder Bohrung, die am Bett beginnt (Fuß macht
  sie eng) — dann den Herstellerwert behalten oder leicht erhöhen; feine Bodenschrift
  dagegen verliert Linien.

### 3.7 Warping

- **Auslöser:** große Grundfläche mit scharfen Ecken, schrumpfende Materialien (ABS, ASA,
  PC, auch PETG), offene Drucker, kleine Füße.
- **Abhilfen:** Brim, bei Ecken Mausohren; Prusa-KB: kleine Hilfsgeometrie nur an der
  Problemecke, Grundflächen rund statt eckig, mehrere Teile zusammen drucken, kein Zug,
  langsamer drucken; Lüfter prüfen, aber zu viel Lüfter hebt das Teil ([P10]).
- **Orca Auto-Brim:** rechnet aus Höhe/Grundfläche, Tempo und Materialfaktor (1; PETG/PCTG
  2; TPU 0,5), höchstens 20 mm ([O12]). Mausohren: `brim_type = brim_ears`,
  `brim_ears_max_angle` (gemessen 125°), `brim_ears_detection_length` ([O12]).
- **Solidon:** Brim/Raft/Skirt/Auto (Rat für ABS/ASA im offenen Drucker, kleine Füße,
  schlanke Teile), Kammertemperatur (Rat). **Lücke:** keine Mausohren für Ecken großer
  Flächen — weniger Nacharbeit als ein voller Brim; nur Orca-Familie.

### 3.8 Wände und Arachne

- **Auslöser:** Wände, die nicht auf ganze Bahnen aufgehen, Schrift, Keile.
- **Einstellungen:** `wall_generator` · `perimeter_generator` · (Cura immer variabel);
  `min_feature_size` 25 %, `min_bead_width` 85 %, `wall_transition_*`.
- **Werte:** Arachne ist seit PrusaSlicer 2.5 Vorgabe; erkennt dünne Wände selbst
  ([P11]). Orca-Familie: Elegoo, Bambu, Creality fahren **classic**, Anycubic in Orca
  Arachne.
- **Solidon:** Rat Arachne unter 3 Bahnen, Bahnbreite an schmalen Stellen, Außenwand
  zuerst bei Keilen. Feinwerte Hersteller — reicht.

### 3.9 Füllung

- **Auslöser:** Festigkeit (Wände wirken mehr als Füllung), Verbinder (Solidon-Rat),
  Deckflächen über dünner Füllung, hohe schlanke Teile.
- **Werte:** Unabhängige Tests: zusätzliche Wände bringen mehr Festigkeit je Gramm als
  zusätzliche Füllung ([G4]); Füllung trägt die Deckflächen ([F14]). Herstellerwerte
  15 % Gitter/Linien, Anycubic 10 % Crosshatch.
- **Solidon:** Dichte, Muster, Winkel als Felder; Rat für Verbinder (Wände bzw. Dichte).

### 3.10 Deckschichten und Pillowing

- **Auslöser:** feine Schichthöhe mit fester Lagenzahl, große flache Oberseiten über
  dünner Füllung, flache Schrägen.
- **Werte:** 0,8–1,0 mm Mindestdicke, 4–6 Lagen bei großen Decken, Füllung 15–20 %
  bzw. dichter unter breiten Decken ([F14]); Orca-Mindestdicke erhöht die Lagenzahl
  automatisch, 0 = aus ([O9]). Herstellerwerte `top_shell_thickness` 1 · 1 · 0,8 · 0,6;
  Prusa-Bündel `top_solid_min_thickness` 0,7 (8×); Cura `top_thickness` 0,8.
- **Solidon:** `shell.top_layers` als Lagenzahl (Feld). Lücke 10.

### 3.11 Schichthöhe und variable Schichthöhe

- **Auslöser:** flache Schrägen (Treppenstufen), feine Details nur in einem Höhenbereich,
  Gewindeflanken, große glatte Flächen, die mit grober Schicht schneller gehen.
- **Wie es übergeben wird:** PrusaSlicer liest eine Höhenkurve aus
  `Metadata/Slic3r_PE_layer_heights_profile.txt` und Höhenbereiche mit eigenen Werten aus
  `Metadata/Prusa_Slicer_layer_config_ranges.xml`; OrcaSlicer, Bambu Studio und
  ElegooSlicer tragen `Metadata/layer_heights_profile.txt` und
  `Metadata/layer_config_ranges.xml` in ihrer DLL ([L3], Quelltext-Nachweis [G5]); Cura
  kennt nur die Automatik `adaptive_layer_height_enabled` (Variation 0,1 mm, Schwelle 0,2,
  [L2]).
- **Werte:** Grenzen aus dem Maschinenprofil (Orca-Familie min 0,08/0,08/0,08/0,04,
  max 0,28/0,28/0,30/0,32; PrusaSlicer `min_layer_height` 0,07); Prusa rechnet die
  adaptive Kurve aus dem Querschnittsfehler an Schrägen und glättet sie ([P3]); Orca
  identisch mit Glättungsradius ([O8]).
- **Höhenbereiche** (`layer_config_ranges.xml`) erlauben je Z-Bereich eigene Prozesswerte
  — ein Weg, oberhalb einer Höhe (Spitzen) langsamer zu drucken, ohne die Platte zu
  bremsen.
- **Solidon:** schreibt keine Höhenkurve und keine Höhenbereiche; Schichthöhe nur global
  (Rat: höchstens 0,75 × Düse).

### 3.12 Bügeln

- **Auslöser:** flache, zur Platte parallele Sicht- oder Klebeflächen; nicht bei
  Figuren und gewölbten Formen ([P6]).
- **Werte:** „topmost“ bügelt nur die oberste Fläche, „top“ alle Oberseiten; Abstand
  0,1 mm (Prusa-Vorgabe), langsam; kostet Zeit, Kanten werden etwas weicher ([P6]).
- **Solidon:** Rat nur bei bündiger Passung; Orca-Zuordnung „top“. Lücke 15.

### 3.13 Kleine Details und Spitzen

- **Auslöser:** Umfänge unter ~40 mm (Radius ≤ 6,5 mm), Spitzen, Zähne, Stacheln.
- **Einstellungen:** Orca `small_perimeter_speed` (50 % der Außenwand) und
  `small_perimeter_threshold` (Radius; 0 = aus, [O7]); Prusa `small_perimeter_speed`
  (Vorgabe 15 mm/s, gilt für Radien bis 6,5 mm); Cura `small_hole_max_size` (0 = aus),
  `small_feature_speed_factor` 50 %; Orca `small_area_infill_flow_compensation`
  gegen Überextrusion auf kurzen Bahnen ([O13]).
- **Herstellerwerte:** Orca-Familie Schwelle 0 in allen vier Profilen — die Funktion ist
  aus. Prusa MK4S SPEED 170 mm/s, Bündel meist 25–45.
- **Solidon:** nichts davon. Lücke 8.

### 3.14 Hohe, schlanke Teile

- **Auslöser:** Höhe zu kleinster Grundkante groß (Solidon `SLENDER_RATIO`), kleine
  Standfläche.
- **Abhilfen:** Beschleunigung und Wandtempo senken (Obico: 60–80 mm/s), breiter Brim
  (5 → 10 mm und mehr), Orca-Auto-Brim nach Höhe/Fläche, Gyroid statt Gitter in hohen
  Beinen, Stützpunkte als Halt ([F13], [O12]).
- **Solidon:** Rat ruhige Wände (60 mm/s, 2000 mm/s²) und Brim ohne Abstand bei schlanken
  Teilen auf kleinem Fuß; Brim bei schlanken Teilen. Abgedeckt.

### 3.15 Dünne Wände

- **Auslöser:** dünnste Stelle < 3 Bahnen, Federarme, Schrift.
- **Einstellungen:** Arachne, Mindeststrukturgröße, Mindestbahnbreite; classic:
  `detect_thin_wall` (Orca, Anycubic 1, sonst 0), Prusa `thin_walls`; Cura
  `fill_outline_gaps`, `min_feature_size`.
- **Solidon:** Rat Arachne, Bahnbreite, Befund unter Düsenbreite. Abgedeckt.

### 3.16 Gewinde und Passungen

- **Auslöser:** Passungen, Gewinde, Bohrungen, Verbinder.
- **Werte:** Gewinde 0,1–0,2 mm radiales Spiel je Seite; Steigung unter 0,5 mm schwer
  druckbar, ab M3/M4 lieber Gewindeeinsätze ([F15], [G6]); Bohrungen drucken zu klein,
  Ausgleich über Bohrungskompensation oder Polyholes ([F15], [O6]); Orca-Wiki: Random-Naht
  für Stifte in Bohrungen ([O11]).
- **Herstellerwerte:** `xy_hole_compensation` 0 (Anycubic 0,02), `hole_to_polyhole` 0;
  Bambu rechnet Bohrungen über `hole_coef_*`/`hole_limit_*`.
- **Solidon:** Rat genaue Außenwand, Außenwand zuerst, langsam (30 mm/s, 2000 mm/s²),
  Bügeln bei bündiger Passung. Spiel kommt aus dem Materialprofil (Regel 7); eine
  Slicerkompensation käme dazu und muss mit ihm abgestimmt werden. Lücke 13.

---

## 4. Stütz-Schlüssel je Familie

### 4.1 Orca-Familie (OrcaSlicer, Bambu Studio, ElegooSlicer, Creality Print, Anycubic Slicer Next)

Spalte „Orca“ = Programmvorgabe aus `PrintConfig.cpp`; „E · B · C · A“ = gemessen bei
Elegoo CC2 · Bambu P1S · Creality K1 · Kobra 2 in OrcaSlicer („–“ = Schlüssel fehlt
im Block).

| Schlüssel | Orca | E · B · C · A | Solidon |
|---|---|---|---|
| `enable_support` | 0 | 0 · 0 · 0 · 0 | Rat `support.style` |
| `support_type` | normal(auto) | tree(auto) · tree(auto) · normal(auto) · normal(auto) | Rat `support.style` (`grid` → normal(auto), `tree` → tree(auto), `auto` schweigt) |
| `support_style` | default (Baum: organic) | default · default · default · grid | Hersteller |
| `support_threshold_angle` | 30 | 30 · 30 · 30 · 30 | Rat `support.threshold_angle` (90 − Solidon-Winkel) |
| `support_threshold_overlap` | 50 % | 50 % · – · – · 50 % | Hersteller |
| `support_on_build_plate_only` | 0 | 0 · 0 · 0 · 0 | Rat `support.placement` |
| `support_critical_regions_only` | 0 | 0 · 0 · 0 · 0 | Hersteller |
| `support_remove_small_overhang` | 1 | 1 · 1 · 1 · 1 | Hersteller |
| `support_top_z_distance` | 0,2 | 0,2 · 0,2 · 0,2 · 0,2 | Feld `support.z_gap` |
| `support_bottom_z_distance` | 0,2 | 0,2 · 0,2 · 0,2 · 0,2 | Hersteller |
| `support_interface_top_layers` | 3 | 2 · 2 · 2 · 3 | Feld `support.interface_layers` |
| `support_interface_bottom_layers` | 0 | 2 · 2 · 2 · −1 | Hersteller |
| `support_interface_spacing` | 0,5 | 0,5 · 0,5 · 0,5 · 0,2 | Hersteller |
| `support_bottom_interface_spacing` | 0,5 | 0,5 · 0,5 · 0,5 · 0,5 | Hersteller |
| `support_interface_pattern` | auto | auto · auto · auto · auto | Hersteller |
| `support_interface_loop_pattern` | – | 0 · 0 · 0 · 0 | Hersteller |
| `support_interface_not_for_body` | 1 | 1 · 1 · 1 · 1 | Hersteller |
| `support_base_pattern` | default | rectilinear · default · rectilinear · rectilinear | Rat nur `grid` → `rectilinear-grid` |
| `support_base_pattern_spacing` | 2,5 | 1 · 2,5 · 2,5 · 0,2 | Feld `support.density` (als Lücke umgerechnet) |
| `support_angle` (Musterwinkel) | – | 0 · 0 · 0 · 0 | Hersteller |
| `support_object_xy_distance` | 0,35 | 0,35 · 0,35 · 0,35 · 0,35 | Feld `support.xy_gap` |
| `support_object_first_layer_gap` | 0,2 | 0,2 · 0,2 · 0,2 · 0,2 | Hersteller |
| `support_expansion` | 0 | 0 · 0 · 0 · 0 | Hersteller |
| `support_line_width` | – | 0,42 · 0,42 · 0,42 · 0,4 | abgeleitet (mit der Dichte = Bahnbreite) |
| `support_speed` / `support_interface_speed` | – | 150/80 · 150/80 · 150/80 · 100/80 | Hersteller |
| `support_material_interface_fan_speed` | – | −1 · – · −1 · −1 | Hersteller |
| `independent_support_layer_height` | 1 | 0 · 1 · 1 · 1 | Hersteller |
| `bridge_no_support` | 0 | 0 · 0 · 0 · 1 | Hersteller |
| `max_bridge_length` | 10 | 10 · 0 · 10 · 10 | Hersteller |
| `enforce_support_layers` | 0 | 0 · 0 · 0 · 0 | Hersteller |
| `support_ironing` (Bambu `enable_support_ironing`) | 0 | 0 · 0 · 0 · 0 | Hersteller |
| `tree_support_branch_angle` | 40 | 45 · 45 · 45 · 40 | Hersteller |
| `tree_support_branch_angle_organic` | 40 | 45 · – · 40 · 40 | Hersteller |
| `tree_support_angle_slow` | 25 | 30 · – · 25 · 25 | Hersteller |
| `tree_support_branch_distance` | 5 | 5 · 5 · 5 · 5 | Hersteller |
| `tree_support_branch_distance_organic` | 1 | 2 · – · 1 · 1 | Hersteller |
| `tree_support_branch_diameter` | 5 | 2 · 2 · 2 · 5 | Hersteller |
| `tree_support_branch_diameter_organic` | 2 | 2 · – · 2 · 2 | abgeleitet nur auf Gültigkeit (≥ 2 Stützbahnen) |
| `tree_support_branch_diameter_angle` | 5 | 5 · 5 · 5 · 5 | Hersteller |
| `tree_support_branch_diameter_double_wall` | – | – · – · 3 · – | Hersteller |
| `tree_support_tip_diameter` | 0,8 | 0,8 · – · 0,8 · 0,8 | abgeleitet nur auf Gültigkeit (≥ Stützbahn) |
| `tree_support_top_rate` | 30 % | 30 % · – · 30 % · 30 % | Hersteller |
| `tree_support_wall_count` | 0 | 0 · −1 · 0 · 0 | Hersteller |
| `tree_support_auto_brim` / `tree_support_brim_width` | 1 / 3 | 1/3 · – · 1/3 · 1/3 | Hersteller |
| `tree_support_adaptive_layer_height` | – | – · – · 1 · – | Hersteller |
| `raft_layers` / `raft_contact_distance` | 0 / 0,1 | 0/0,1 überall | Feld `adhesion.raft_layers` / `adhesion.raft_gap` |
| `raft_first_layer_density` / `_expansion` | – | 90 %/2 · 90 %/−1 · 90 %/2 · 90 %/2 | Hersteller |
| Stützsperre (Teilart `support_blocker`) | — | — | Rat `support.block_channels` (Geometrie) |

### 4.2 PrusaSlicer und SuperSlicer

„Vorgabe“ = PrusaSlicer 2.9.6 `--help-fff`; „MK4S“ = gemessen im Lauf MK4S 0.20mm SPEED;
„Bündel“ = häufigster Wert in `PrusaResearch.ini`.

| Schlüssel | Vorgabe | MK4S · Bündel | Solidon |
|---|---|---|---|
| `support_material` | aus | 1 | Rat `support.style` |
| `support_material_auto` | an (Haken) | 0 (nur Verstärker) | abgeleitet: 1, sobald Stützen an |
| `support_material_style` | grid | snug · snug (39×) | Rat nur `grid`/`organic` (`tree` → organic) |
| `support_material_threshold` | 0 = automatisch | 35 · 35 (24×) | Rat `support.threshold_angle` |
| `support_material_buildplate_only` | aus | 0 | Rat `support.placement` |
| `support_material_contact_distance` | 0,2 | 0,2 · ≈ Schichthöhe, Deckel 0,25 | Feld `support.z_gap` |
| `support_material_bottom_contact_distance` | 0 (= wie oben) | 0 | Hersteller (folgt oben) |
| `support_material_interface_layers` | 3 | 3 · 3 (37×) | Feld `support.interface_layers` |
| `support_material_bottom_interface_layers` | −1 (= wie oben) | 0 | Hersteller |
| `support_material_interface_spacing` | 0 (geschlossen) | 0,2 · 0,2 | Hersteller |
| `support_material_interface_pattern` | rectilinear | auto | Hersteller |
| `support_material_interface_contact_loops` | aus | 0 | Hersteller |
| `support_material_pattern` | rectilinear | rectilinear | Rat nur `grid` → `rectilinear-grid` |
| `support_material_spacing` | 2,5 | 2 | Feld `support.density` (als Lücke) |
| `support_material_xy_spacing` | 50 % | 80 % · 80 % (27×) | Feld `support.xy_gap` (mm) |
| `support_material_closing_radius` | 2 | 2 | Hersteller |
| `support_material_with_sheath` | aus | 0 | Hersteller |
| `support_material_angle` | 0 | 0 | Hersteller |
| `support_material_enforce_layers` | 0 | 0 | Hersteller |
| `support_material_synchronize_layers` | aus | 0 | Hersteller |
| `support_material_speed` / `_interface_speed` | 60 / 100 % | 120 / 50 % | Hersteller |
| `support_material_extrusion_width` | 0 | 0,4 | abgeleitet (Bahnbreite, mit der Dichte) |
| `dont_support_bridges` | – | 0 | Hersteller |
| `support_tree_angle` | 40 | 40 | Hersteller |
| `support_tree_angle_slow` | 25 | 25 | Hersteller |
| `support_tree_branch_diameter` | 2 | 2 | Hersteller |
| `support_tree_branch_diameter_angle` | 5 | 5 | Hersteller |
| `support_tree_branch_diameter_double_wall` | 3 | 8 | Hersteller |
| `support_tree_branch_distance` | 1 | 1 | Hersteller |
| `support_tree_tip_diameter` | 0,8 | 0,8 · 0,5–1,6 je Düse | Hersteller |
| `support_tree_top_rate` | 15 % | 30 % | Hersteller |
| `raft_layers` / `raft_contact_distance` | 0 / 0,1 | 0 / 0,15 | Feld (`adhesion.*`) |
| `raft_expansion` / `raft_first_layer_expansion` / `_density` | 1,5 / 3 / 90 % | 1,5 / 3 / 90 % | Hersteller |
| Bereich `SupportBlocker` | — | — | Rat `support.block_channels` |

SuperSlicer 2.5.59.13 hat zusätzlich `support_material_contact_distance_type`,
`support_material_interface_angle`, `support_material_interface_fan_speed`,
`support_material_layer_height` und `support_material_bottom_contact_distance` als
eigenen Wert; Bäume kennt er nicht (Solidon ersetzt durch Gitter, RM-480).

### 4.3 Cura (CuraEngine 5.13)

„Vorgabe“ = `fdmprinter.def.json` (Wert bzw. Formel).

| Schlüssel | Vorgabe | Solidon |
|---|---|---|
| `support_enable` | False | Rat `support.style` |
| `support_structure` | normal | Rat (`tree` → tree, sonst normal) |
| `support_type` | everywhere | Rat `support.placement` |
| `support_angle` | 50° (gegen die Senkrechte) | Rat `support.threshold_angle` |
| `support_pattern` | zigzag | Definition (bewusst, kippt nicht) |
| `support_infill_rate` | 15 % (Baum 0) | Feld `support.density` |
| `support_line_distance` | aus Dichte | abgeleitet |
| `support_wall_count` | 1 beim Baum | abgeleitet (Baum 1, sonst 0) |
| `support_z_distance` | 0,1 | Feld `support.z_gap` |
| `support_top_distance` / `support_bottom_distance` | = Z-Abstand | abgeleitet (gespiegelt) |
| `support_xy_distance` | 0,7 | Feld `support.xy_gap` |
| `support_xy_overrides_z` | z_overrides_xy | Definition |
| `support_xy_distance_overhang` | Düse/2 | abgeleitet |
| `support_offset` | Bahn + 0,4 (normal) | abgeleitet |
| `support_interface_enable` / `support_roof_enable` / `support_bottom_enable` | False | abgeleitet (an bei Lagen > 0) |
| `support_interface_height` | 1 mm | abgeleitet (Lagen × Schichthöhe) |
| `support_interface_density` / `support_roof_line_distance` | 100 % | abgeleitet: Linienabstand 3 × Bahnbreite |
| `support_roof_pattern` / `support_bottom_pattern` | concentric | abgeleitet: lines |
| `support_bottom_stair_step_height` | 0,3 | abgeleitet |
| `minimum_support_area` | 0 | abgeleitet 2 mm² |
| `minimum_interface_area` | 1 mm² | Definition |
| `support_interface_offset` | 0 | Definition |
| `support_tree_angle` | = Stützwinkel, begrenzt 20–85 | abgeleitet aus `support.threshold_angle` |
| `support_tree_angle_slow` | 2/3 Astwinkel | abgeleitet |
| `support_tree_branch_diameter` | 5 | Definition |
| `support_tree_max_diameter` | 25 | Definition |
| `support_tree_branch_diameter_angle` | 7° | Definition |
| `support_tree_tip_diameter` | 2 × Stützbahn | abgeleitet |
| `support_tree_top_rate` | 30 mit Dach, sonst 10 | abgeleitet |
| `support_tree_rest_preference` | buildplate/graceful | abgeleitet aus `support.placement` |
| `support_tree_min_height_to_model` | 3 mm | Definition |
| `support_tree_bp_diameter` | 7,5 mm | Definition |
| `support_tree_limit_branch_reach` / `_branch_reach_limit` | True / 30 mm | Definition |
| `support_brim_enable` / `_width` / `_line_count` | True / 3 Bahnen | abgeleitet |
| `support_fan_enable` / `support_supported_skin_fan_speed` | False / 100 % | Definition |
| `support_z_seam_away_from_model` | True | Solidon `false` (Absturzschutz der Konsole) |
| `support_conical_enabled` | False | Definition |
| `conical_overhang_enabled` | False | Definition (ändert Geometrie) |
| `anti_overhang_mesh` | — | Rat `support.block_channels` (eigenes Netz) |

### 4.4 Was Solidon heute aus der Geometrie ableitet (`slice/advise.py`)

`_from_geometry`:

- Stützen nötig (Inseln, Überhangsumme oder größtes Stück, lange Brücke; Kanaldecken
  ausgenommen) → `support.style` = `auto`, oder `tree` bei ≥ 8 Inselschichten bzw.
  Stützen auf dem Modell; Gitter/auto mit Stützen auf dem Modell → `tree`; nichts nötig →
  `none`.
- Ort: auf dem Modell nötig → `everywhere`; sonst `build_plate`.
- Kanäle mit sperrbarem Raum → `support.block_channels`.
- Skirt nur, wo er Platz hat; Brim bei Standfläche < 400 mm², auf vielen kleinen Füßen und
  bei schlanken Teilen (nicht über Orcas Auto-Brim).
- Schlank und kleiner Fuß → ruhige Wände (60 mm/s, 2000 mm/s²) und Brimabstand 0.
- Schmale Stege in der ersten Schicht → `speed.first_layer` 50 mm/s.
- Dünnste Stelle < 3 Bahnen und classic → Arachne; < 2 Bahnen → `layers.line_width`
  senken (bis 0,85 × Düse).
- Überhang vorhanden und Brücke schneller als Außenwand → `speed.bridge`.
- Keile in der Wand (≥ 20 % der Schichten) ohne Stützbedarf → `shell.outer_wall_first`.
- Glatte runde Außenwand über ≥ 10 mm → `shell.scarf_seam`.
- Dünne Schichten oben ohne Mindestzeit → `cooling.minimum_layer_time` 15 s; Spitzen
  unter der Mindestzeit → `cooling.minimum_speed` 5 mm/s.

Daneben: `_from_machine` (Leerfahrt, Stützwinkel, Schichthöhe ≤ 0,75 × Düse,
Temperaturgrenzen, Bahnbreite ≥ 0,85 × Düse, Kammer), `_from_material` (ABS/ASA: Brim,
Lüfter 20 %, Kammer 50 °C; TPU: Tempo ≤ 30), `_from_fits` (Bügeln bei bündiger Passung,
genaue Außenwand, 2000 mm/s², 30 mm/s, Außenwand zuerst), `_from_connectors`
(Wandzahl bzw. Dichte um Verbinder), `_from_flow` (Volumenstrom, nur Cura). Warnungen:
Stützabstand unter einer Schicht, Brücken ≥ 15 mm, Wand unter Düse, Brim ohne Platz.

---

## 5. Quellen

**Hersteller- und Programmdokumentation**

- [P1] Prusa KB, Support material: https://help.prusa3d.com/article/support-material_1698
- [P2] Prusa KB, Organic supports: https://help.prusa3d.com/article/organic-supports_480131
- [P3] Prusa KB, Variable layer height: https://help.prusa3d.com/article/variable-layer-height-function_1750
- [P4] Prusa KB, Elephant foot compensation: https://help.prusa3d.com/article/elephant-foot-compensation_114487
- [P5] Prusa KB, Seam position: https://help.prusa3d.com/article/seam-position_151069
- [P6] Prusa KB, Ironing: https://help.prusa3d.com/article/ironing_177488
- [P7] Prusa KB, Paint-on supports: https://help.prusa3d.com/article/paint-on-supports_168584
- [P8] Prusa KB, Cooling: https://help.prusa3d.com/article/cooling_127569
- [P9] Prusa KB, Stringing and oozing: https://help.prusa3d.com/article/stringing-and-oozing_1805
- [P10] Prusa KB, Warping: https://help.prusa3d.com/article/warping_2011
- [P11] Prusa KB, Arachne perimeter generator: https://help.prusa3d.com/article/arachne-perimeter-generator_352769
- [P12] Prusa KB, Speed settings (dynamische Überhänge): https://help.prusa3d.com/article/speed-settings_480325
- [O1] OrcaSlicer-Wiki, Tree support: https://www.orcaslicer.com/wiki/print_settings/support/support_settings_tree
- [O2] OrcaSlicer-Wiki, Support advanced: https://www.orcaslicer.com/wiki/print_settings/support/support_settings_advanced
- [O3] OrcaSlicer-Wiki, Support (Typen und Stile): https://www.orcaslicer.com/wiki/print_settings/support/support_settings_support
- [O4] OrcaSlicer-Wiki, Material cooling: https://www.orcaslicer.com/wiki/material_settings/cooling/material_cooling
- [O5] OrcaSlicer-Wiki, Overhangs: https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_overhangs
- [O6] OrcaSlicer-Wiki, Precision: https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_precision
- [O7] OrcaSlicer-Wiki, Other layers speed (kleine Umfänge): https://www.orcaslicer.com/wiki/print_settings/speed/speed_settings_other_layers_speed
- [O8] OrcaSlicer-Wiki, Variable layer height: https://www.orcaslicer.com/wiki/print_prepare/prepare_variable_layer_height
- [O9] OrcaSlicer-Wiki, Top and bottom shells: https://www.orcaslicer.com/wiki/print_settings/strength/strength_settings_top_bottom_shells
- [O10] OrcaSlicer-Wiki, Bridging: https://github.com/OrcaSlicer/OrcaSlicer/wiki/quality_settings_bridging
- [O11] OrcaSlicer-Wiki, Seam: https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_seam
- [O12] OrcaSlicer-Wiki, Brim: https://www.orcaslicer.com/wiki/print_settings/others/others_settings_brim
- [O13] OrcaSlicer-Wiki, Wall and surfaces: https://www.orcaslicer.com/wiki/print_settings/quality/quality_settings_wall_and_surfaces
- [O14] OrcaSlicer-Wiki, Overhang speed: https://www.orcaslicer.com/wiki/print_settings/speed/speed_settings_overhang_speed
- [O15] OrcaSlicer-Quelltext, Programmvorgaben: https://raw.githubusercontent.com/OrcaSlicer/OrcaSlicer/main/src/libslic3r/PrintConfig.cpp
- [U1] UltiMaker Support, Support settings: https://support.ultimaker.com/articles/Knowledge/1667417606331
- [T1] Teaching Tech, Calibration: https://teachingtechyt.github.io/calibration.html

**Foren, Tests, Leitfäden**

- [F1] Bambu-Forum, Mixed tree/normal supports: https://forum.bambulab.com/t/mixed-tree-normal-supports-on-the-same-model-how-to-replicate/185530
- [F2] Bambu-Forum, Help for support Z top distance: https://forum.bambulab.com/t/help-for-support-z-top-distance/40562 — und Missing support layer height option: https://forum.bambulab.com/t/missing-support-layer-height-option/12324
- [F3] Bambu-Forum, PETG support sticks too much: https://forum.bambulab.com/t/petg-support-sticks-to-much-advice-on-settings/12033
- [F4] Prusa-Forum, Support blockers not blocking: https://forum.prusa3d.com/forum/prusaslicer/support-blockers-not-blocking/
- [F5] Bambu-Forum, Support exclusion on buildplate: https://forum.bambulab.com/t/support-exclusion-on-buildplate-and-error-fix-2-requests/158584
- [F6] Creality-Forum, Best support settings for clean removal: https://forum.creality.com/t/best-support-settings-for-clean-3d-print-removal/50079
- [F7] Bambu-Forum, Tree supports falling over: https://forum.bambulab.com/t/tree-supports-falling-over-on-2-x1c-printers/24826 — Creality-Forum: https://forum.creality.com/t/tree-supports-falling-over-when-not-on-build-plate/50280
- [F8] Bambu-Forum, Tree support with infill: https://forum.bambulab.com/t/tree-support-with-infill/3097
- [F9] Prusa-Forum, PrusaSlicer hard to remove supports: https://forum.prusaprinters.org/forum/prusaslicer/prusaslicer-hard-to-remove-supports/paged/6/
- [F10] Sovol, Support settings explained: https://www.sovol3d.com/blogs/news/3d-printing-support-settings-explained-how-to-get-cleaner-easier-to-remove-fdm-prints
- [F11] MakerWorld, Top-Z-Distance-Test: https://makerworld.com/models/2497727
- [F12] UltiMaker-Community, Converging last layers (Kopf anheben, Zweitteil): https://community.ultimaker.com/topic/4328-problem-of-printing-converging-last-layers/
- [F12b] Prusa-Forum, Larger brim for organic supports: https://forum.prusa3d.com/forum/prusaslicer/how-to-add-a-larger-brim-to-the-bottom-of-organic-supports
- [F13] Bambu-Forum, Layer wobble tall and skinny parts: https://forum.bambulab.com/t/how-to-fix-layer-wobble-for-tall-and-skinny-parts/56301
- [F14] Polymaker-Wiki, Pillowed top: https://wiki.polymaker.com/printing-tips/common-printing-issues/pillowed-pitted-top-of-print
- [F15] Bambu-Forum, Hole size issues: https://forum.bambulab.com/t/hole-size-issues/100439
- [G1] OrcaSlicer-Issue #4716, Mindestschichtzeit warten statt kriechen: https://github.com/SoftFever/OrcaSlicer/issues/4716
- [G2] Leitfaden Stützen 2026 (Kontaktdichte 60–80 %, Kühlung): https://blog.uavmodel.com/?p=3734
- [G3] Wevolver, Cura support settings (Z-Abstand in Schichtvielfachen): https://www.wevolver.com/article/cura-support-settings-from-angles-to-z-distance
- [G4] HackSpace, Experiments with strong 3D prints: https://hackspace.raspberrypi.com/articles/experiments-with-strong-3d-prints
- [G5] Quelltextspiegel OrcaSlicer/PrusaSlicer, 3MF-Dateinamen der Schichthöhen: https://git.trueserve.org/PublicCodeMirror/OrcaSlicer-bambulab/commit/4e0eb12ef6518e0a9e964612da626c86890d5e02
- [G6] Snapmaker, Guide to 3D printing threads: https://www.snapmaker.com/blog/3d-printing-threads
- All3DP (Überblick, nicht als Einzelbeleg): https://all3dp.com/2/prusaslicer-support-settings-explained/ und https://all3dp.com/2/bambu-studio-support-settings-simply-explained/

**Örtlich gemessen (dieser Rechner, 08.10.2026)**

- [L1] PrusaSlicer 2.9.6: `prusa-slicer-console --help-fff`;
  `C:\Program Files\Prusa3D\PrusaSlicer\resources\profiles\PrusaResearch.ini` (Werte
  ausgezählt, Schichthöhe/Abstand nach Vererbung gepaart).
- [L2] Cura 5.13: `C:\Program Files\UltiMaker Cura 5.13.0\share\cura\resources\definitions\fdmprinter.def.json`.
- [L3] Zeichenketten in `OrcaSlicer.dll`, `BambuStudio.dll`, `ElegooSlicer.dll`
  (`Metadata/layer_heights_profile.txt`, `Metadata/layer_config_ranges.xml`) und
  `PrusaSlicer.dll` (`Metadata/Prusa_Slicer_layer_config_ranges.xml`).
- [L4] Konfigurationsblöcke der Prüfläufe „standard“ in `F:\3D Druck\output\drache-2026-10-08`:
  `matrix-final/…/bambu__bambu-p1s`, `matrix-final/…/creality__creality-k1`,
  `drache130/…/elegoo__centauri-carbon-2`, `kandidat/schuessel/…/orca__anycubic-kobra-2`,
  `eiffel/matrix/…/prusa__prusa-mk4s`, `matrix-final/…/superslicer__prusa-mini`.
- Solidon: `F:/sl-modell/app/core/types.py` (Zeilen 1168–1583),
  `app/core/export/slicer_keys.py`, `app/core/export/handover.py` (`_for_supports`,
  `_support_spacing`, `organic_tree_fitted`), `app/core/slice/advise.py`.

**Nicht erreichbar:** reddit.com (r/3Dprinting, r/BambuLab, r/OrcaSlicer, r/prusa3d,
r/Cura — für den Abrufdienst gesperrt), wiki.bambulab.com (HTTP 402), Creality-Wiki
Tree Support (Seite ohne Inhalt geliefert). Eigene Videos und Artikel von CNC Kitchen
fanden sich nicht; die Aussagen zu Wänden gegenüber Füllung stammen aus HackSpace.
