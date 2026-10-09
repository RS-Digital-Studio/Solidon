## RM-583: Stützabstand und Trennschichten folgen dem Material der Spule, je Teil (09.10.2026)

<a id="rm-583-stützabstand-und-trennschichten-folgen-dem-material-der-spule-je-teil-09102026"></a>
<a id="rm-583"></a>

**Befund (Recherche 08.10.2026):** Solidon ließ Z-Abstand, Trennschichten, deren Lücke und
den Kontaktlüfter beim Hersteller; `support.z_gap` hatte ein Feld, aber keine Regel. Die
häufigsten Ursachen für Narben und verschweißte Stützen
(`konzepte/recherche-slicer-einstellungen-2026-10.md`, Nr. 1, 2, 3, 7): Abstand nicht auf
Schicht und Material abgestimmt (PLA etwa eine Schicht, PETG 1,25 bis 1,5), unten keine
Trennschicht, wo die Stütze auf dem Modell steht (MK4S-Profil 0), dichte Trennschichten
unter kleinen Flächen, Kontaktlüfter aus (alle Orca-Profile −1). Robert: „immer nach dem
verwendeten Material, kein Projektmaterial“ — PLA und PETG auf einer Platte brauchen
verschiedene Werte.

**Behoben:** Das Materialprofil führt `support_gap_factor`, `support_gap_min`,
`support_gap_max` und `support_interface_cooling` (Regel 7; PLA, ABS und ASA 1,0/0,10/0,25,
PETG und PETG-CF 1,4/0,12/0,30 mit voller Kühlung, TPU ohne Quelle und damit ohne Rat).
`advise._support_contact` schlägt den Abstand vor (`support_gap_target`; wo der Slicer in
ganzen Schichten rechnet, das Vielfache im Band), unten Trennschichten, wo die Stütze auf
dem Modell steht, unter flachen Decken dichte, sonst lockere Trennschichten, und volle
Kühlung an der Trennschicht. Neue Felder *Trennschichten unten*, *Lücke in der
Trennschicht* und *Volle Kühlung an der Stütze*, *Abstand nach oben* heißt *Abstand oben
und unten*; Übergabe und Rücklesen in allen Familien (Prusa −1 = wie oben, Orca-Lüfter als
Filamentwert, SuperSlicer mit unterem Abstand und Lüfter, PrusaSlicer und Bambu ohne Lüfter,
Cura `support_fan_enable` und eigene untere Höhe, Cura sagt einen Abstand zwischen zwei
Schichten an). Abstand und Trennschichten gehen je Teil (`PART_PATHS`, `SLICED_PATHS`,
Cura `CURA_DERIVED_PER_MESH`), gefragt mit dem Material der Spule; der Druckdialog führt
sie getrennt zusammen (`combine` mit `CONTACT_PATHS`). Die Orca-Familie rundet ohne eigene
Stützschichthöhe auf ganze Schichten (`Slicing.cpp`, Elegoos CC2-Prozess hat sie aus); an
den geschriebenen Abständen schaltet die Übergabe sie ein
(`handover.frees_support_layers`, Befund `slicer.support_layers_freed`), mit Reinigungsturm
(`handover.tower_cause` je Platte: mehrere Filamente außer „je Objekt“, glatter Zeitraffer,
Wicklungserkennung) sagt der Export nur die Rundung (`export.support_gap_rounded`). Der
Druckdialog fragt den Kontakt wie der Export gegen die Grundlage
(`handover.asked_for_contact`), führt erst je Körper über die Spulen und dann nur die
verlangenden Körper zusammen; die Zeile nennt nur Teile mit ihrem Wert. Die Cura-Grundlage
trägt den Abstand in ganzen Schichten, Curas Satz dazu kommt nur mit Stützen, nennt das
Feld und öffnet es. Ein vor 0.6.0 kalibriertes Material ergänzt fehlende Werte aus dem
mitgelieferten Eintrag. Die Spule druckt das Material ihres gewählten Filamentprofils
(`handover.slot_material_type`). Druckzeit und Stützmenge rechnen mit der geschriebenen
Lücke; die Matrix misst mit dem Filament des Materials.

**Nachweis (09.10.2026):** Kontaktsonde (`.claude/.state/drache-2026-10-08/kontakt_je_teil.py`,
zwei gestützte Stufenkörper, einer mit Objektwerten, Raster 2 mm) in allen acht
Programmen: Abstand oben wie geschrieben (0,4 gegen 0,2 mm; SuperSlicer bei 0,15er
Schichten 0,53 gegen 0,33), Trennschichten bei Prusa und Cura genau, die Orca-Familie oben
eine Übergangslage und unten die Kontaktlage mehr (`SupportCommon.cpp`), weite Lücke mit
deutlich weniger Bahn je Ebene (Orca 1044 gegen 1617 mm), bei Cura plattenweit. Eine
erste Messung mit 0,5-mm-Raster und Bambus Übergangslage als Modell hatte bei Cura 0,6
statt 0,4 und bei Bambu unten fünf Lagen gezeigt; beide druckten wie geschrieben. Echter Rat
auf einer Platte mit PLA und PETG: PrusaSlicer 0,2 und 0,28 mm; Orca, Elegoo, Creality und
Bambu mit Reinigungsturm beide 0,2. PETG allein: ElegooSlicer und Creality Print 0,28.
{DRACHE}
Tests in `test_slice_findings.py`, `test_print_settings.py`, `test_print_settings_ui.py`,
`test_print_time.py`, `test_manufacturer.py`, `test_slicer_part_settings.py` und
`test_export.py`. Review `solidon3d-review` mit Nachprüfung; {TOR}
