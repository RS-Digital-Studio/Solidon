# Sondierung: .claude/konzept-slicer-uebergabe.md

**Titel:** Konzept — Druckeinstellungen automatisch setzen, bevor der Slicer sie bekommt
**Stand laut Dokument:** (kein Stand-Datum im Dokument genannt; letzte Git-Änderung 2026-08-07)
**Zweck:** Bestandsaufnahme und Fünf-Stufen-Plan, wie Solidon Druckeinstellungen selbst ermittelt und so an den Slicer (Orca-Familie/ElegooSlicer) übergibt, dass sie dort tatsächlich ankommen — abgeleitet aus dem von Hand eingerichteten Gewürzset-Projekt.

**Alterung:** 4/5 — Das Dokument hängt an zwei beweglichen Dingen zugleich: am Profilbestand und der Kommandozeile eines fremden Slicers (Schlüsselnamen, Profilzuordnung, Herstellerwerte für Elegoo-PETG, Profilzahlen 5962/3887 — alles ändert sich mit jeder Slicer- und Profilfassung) und am eigenen Umsetzungsstand, den es selbst als 'umgesetzt' abhakt. Die Fünf-Stufen-Gliederung ist Arbeitsstand, kein zeitloser Entwurf; sobald die offenen Reste (arrange_bed-Haftungsrand, Lochkorrektur, Ironing-Regel aus Fit) erledigt sind, beschreibt der Text einen vergangenen Zustand. Ein fehlendes Stand-Datum verschärft das.

## Gliederung

- Konzept — Druckeinstellungen automatisch setzen, bevor der Slicer sie bekommt (Titel)
- 1. Was Solidon heute schon kann
- 2. Drei Lücken, gemessen
- 3. Was im Modell fehlt
- 4. Wo die Grenze zwischen „automatisch" und „vorgeschlagen" liegt
- 5. Vorschlag in fünf Stufen
- 6. Was nicht gebaut wird
- 6a. Die Probe — das Gewürzset aus Solidon heraus
- 7. Abnahme

## Extern prüfbare Behauptungen (17)

- **[hoch/funktionsumfang] OrcaSlicer / ElegooSlicer (Profilaufbau)** — Die Orca-Familie verteilt ihre Einstellungen auf drei Profiltypen (machine, process, filament); 14 der genannten Schlüssel führt Elegoo im FILAMENT-Profil, 4 im MACHINE-Profil  
  _Ort:_ §2.1
- **[hoch/api] OrcaSlicer Kommandozeile** — Der Slicer wird mit --load-settings machine;process aufgerufen; für Filamente gibt es den eigenen Schalter --load-filaments  
  _Ort:_ §2.1, §5 Stufe 1
- **[hoch/api] OrcaSlicer Einstellungsschlüssel (retraction_length etc.)** — Orca sieht filament_*-Entsprechungen für den Rückzug vor, sodass kein Maschinenprofil geschrieben werden muss  
  _Ort:_ §5 Stufe 1
- **[hoch/funktionsumfang] Elegoo PETG Translucent (Herstellerprofil)** — Elegoo PETG Translucent: Düse 255/255 °C, Bett 70/70 °C, Volumenstrom 10 mm³/s, Pressure Advance 0,052  
  _Ort:_ §2.3 Tabelle
- **[hoch/funktionsumfang] Elegoo PETG PRO (Herstellerprofil)** — Elegoo PETG PRO: Düse 240/240 °C, Bett 70/70 °C, Volumenstrom 5 mm³/s, Pressure Advance 0,1  
  _Ort:_ §2.3 Tabelle
- **[mittel/funktionsumfang] ElegooSlicer Filamentprofile** — Pressure Advance steht in jedem Elegoo-Filamentprofil  
  _Ort:_ §3
- **[mittel/funktionsumfang] ElegooSlicer Profil-Erbkette** — Beim transluzenten Elegoo-PETG löst die Erbkette fünfundfünfzig Werte aus vier Dateien auf, wo die oberste nur drei nennt  
  _Ort:_ §5 Stufe 2
- **[mittel/funktionsumfang] ElegooSlicer Profilbestand** — Profilbestand des installierten Slicers: 5962 Profile mit Filamenten gegen 3887 ohne  
  _Ort:_ §5 Stufe 2
- **[mittel/funktionsumfang] CuraEngine / Ultimaker Cura** — CuraEngine hat keinen umschaltbaren Wandgenerator  
  _Ort:_ §5 Stufe 3
- **[mittel/funktionsumfang] PrusaSlicer** — PrusaSlicer kennt keine gesonderte genaue Außenwand; beide (Cura, Prusa) rechnen mit variabler Bahnbreite  
  _Ort:_ §5 Stufe 3
- **[hoch/api] OrcaSlicer 3MF-Format / model_settings.config** — Die Orca-Familie schreibt das name-Attribut des 3MF-Standards selbst nie und liest Objektnamen aus model_settings.config  
  _Ort:_ §5 Stufe 4
- **[mittel/api] 3MF / OrcaSlicer model_settings.config** — model_settings.config nimmt Metadaten je Objekt auf  
  _Ort:_ §3
- **[mittel/api] OrcaSlicer/ElegooSlicer Profilsyntax** — 'nil' in einem Filamentprofil bedeutet 'keine Angabe' — der Wert bleibt beim Drucker  
  _Ort:_ §6a Fund 2
- **[mittel/fassung] ElegooSlicer Profilnamen (Centauri Carbon 2)** — Konkrete Profilnamen des installierten Slicers: 'Elegoo Centauri Carbon 2 0.4 nozzle', '0.20mm Standard @Elegoo CC2 0.4 nozzle', 'Elegoo PETG @ECC2', 'Elegoo PETG Translucent @ECC2'  
  _Ort:_ §2.2, §6a
- **[mittel/api] ElegooSlicer G-Code-Ausgabe** — Die erzeugte G-Code-Datei trägt Konfigurationskommentare, die sich zurücklesen lassen  
  _Ort:_ §1 Tabelle (handover.verify)
- **[niedrig/funktionsumfang] ElegooSlicer Prozessprofil Centauri Carbon 2** — Vorlagenprofil fuhr 10 000 mm/s² Beschleunigung  
  _Ort:_ §3
- **[niedrig/funktionsumfang] ElegooSlicer / Centauri Carbon 2 Spülvolumen** — Ein Filamentwechsel je Lage kostet 30–50 g Spülmaterial bei rund 220 Wechseln, gut anderthalb Stunden  
  _Ort:_ §3

## Intern prüfbare Behauptungen (15)

- **[hoch]** slicer_keys.py enthält 50 Zuordnungen für Orca, dazu Prusa und Cura  
  _Prüfen:_ app/core/export/slicer_keys.py: Einträge zählen  
  _Ort:_ §1 Tabelle
- **[hoch]** Achtzehn von fünfzig Werten landen im falschen Profil (14 filament, 4 machine) — Zustand vor Stufe 1  
  _Prüfen:_ Historischer Befund; heute prüft test_every_orca_setting_sits_in_the_profile_it_claims — pytest -q -k orca_setting  
  _Ort:_ §2.1, §7 Punkt 1
- **[mittel]** handover._RECOMPUTED nimmt filament_colour, filament_density, filament_cost, filament_max_volumetric_speed von der Gegenprobe aus  
  _Prüfen:_ grep _RECOMPUTED in app/core/export/handover.py  
  _Ort:_ §2.1
- **[hoch]** slicer_profiles.PROFILE_DIRS kennt nur machine und process, filament fehlt  
  _Prüfen:_ grep PROFILE_DIRS in app/core/export/slicer_profiles.py — laut Stufe 2 inzwischen behoben  
  _Ort:_ §2.2
- **[hoch]** Solidons material.petg: Düse 240/245 °C, Bett 80/80 °C, Volumenstrom 12 mm³/s, kein Pressure Advance  
  _Prüfen:_ app/core/knowledge/data/print_settings.toml, Abschnitt material.petg  
  _Ort:_ §2.3
- **[mittel]** Solidons Materialtabelle weicht in dreizehn Werten vom Herstellerprofil ab  
  _Prüfen:_ profile_differences gegen installierten ElegooSlicer laufen lassen  
  _Ort:_ §6a
- **[hoch]** Alle fünf Stufen sind als 'umgesetzt' markiert  
  _Prüfen:_ Vorhandensein von Entry.kind/write_config-Trennung, --load-filaments, resolve_values/match_filament, PrintSettings.shell.wall_generator etc., AssemblyPart.settings, plates_by_material, check_adhesion_clearance, check_filament_changes  
  _Ort:_ §5, Stufenüberschriften
- **[mittel]** MaterialProfile.hole_compensation geht bisher nur in die Hashsumme ein; es gibt keine Op, die ihn anwendet  
  _Prüfen:_ grep hole_compensation über app/  
  _Ort:_ §5 Stufe 3
- **[mittel]** Die Op compensate_elephant_foot existiert und tut, was die Slicer-Kompensation tut  
  _Prüfen:_ grep compensate_elephant_foot im Register app/core/registry/  
  _Ort:_ §5 Stufe 3
- **[mittel]** Die Regel 'Fläche, auf der etwas gleiten soll' aus dem Fit abzuleiten steht noch aus; Bügeln ist heute nur ein Schalter im Dialog  
  _Prüfen:_ app/core/slice/advise.py auf eine Ironing-Regel prüfen  
  _Ort:_ §5 Stufe 3
- **[hoch]** arrange_bed legt 5 mm zwischen zwei Körper, nötig wären bei 3 mm Skirt-Abstand 6 mm — offen, steht in der Roadmap  
  _Prüfen:_ Abstandskonstante in der arrange_bed-Op; ROADMAP.md nach Haftungsrand/arrange_bed durchsuchen  
  _Ort:_ §6a Fund 3
- **[mittel]** In der Suite gibt es keinen echten Slicer-Lauf; verify läuft nur bei einem echten Lauf  
  _Prüfen:_ tests/ nach handover.verify / skipif ohne installierten Slicer durchsuchen  
  _Ort:_ §2.1, §7
- **[niedrig]** Die Spülmenge in Gramm bleibt draußen  
  _Prüfen:_ check_filament_changes-Rückgabe prüfen: nur Schichten und Wechsel  
  _Ort:_ §5 Stufe 5
- **[mittel]** Gewürzset-Messwerte: Deckelbasis 282 mm²/22,0 mm, Streuscheibe 516 mm²/5,4 mm, Behälter 1256 mm²/67,6 mm; 110 gemeinsame Schichten, 220 Wechsel  
  _Prüfen:_ Probe aus §6a wiederholen: Import der vier STL aus '3D Drucker' Projekt 08, advise.for_part und check_filament_changes  
  _Ort:_ §3, §6a
- **[niedrig]** Der 'nil'-Fund wurde behoben: 17 Meldungen wurden 13  
  _Prüfen:_ profile_differences erneut gegen dasselbe Filamentprofil laufen lassen  
  _Ort:_ §6a Fund 2