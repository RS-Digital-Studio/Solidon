# Das Herstellerprofil ist die Grundlage — Solidon schreibt nur, was davon abweichen soll

Stand: 27.09.2026. Auftrag Robert am 27.09.2026 nach dem gescheiterten
Minigolf-Druck am Centauri Carbon 2: „kontrolle dann über alle slicer und alle
modelle damit alles druckbar ist mit sinnvollen vorschlägen, außerdem bei allen
slicern alle Parameter und Einstellungsmöglichkeiten beachten für perfekte
druckergebnisse", dazu „alles optimieren du kannst alles machen und brauchst
nicht mein ok" und „lieber langsam, dafür richtig". Der laufende Umsetzungs-
und Abnahmestand gehört in `ROADMAP.md`; dieses Dokument trägt Entscheidungen
und Nachweise.

Die vier Prüfberichte, auf denen es steht, liegen unverändert unter
[`nachweise-herstellerprofil-2026-09/`](nachweise-herstellerprofil-2026-09/):
Orca-Familie, PrusaSlicer, CuraEngine und die Karte des Einstellungsweges im
Code. Zeilennummern darin gelten für ihren Stichtag.

**Bauplanänderung mit Ansage.** §29 sagt heute: „Prozesswerte und
Filamentzuordnungen werden aus den gespeicherten Druckeinstellungen des
Projekts aufgelöst." Das kehrt dieses Konzept um. Die Änderung am Bauplan
steht in Stufe A und wird im Bericht an Robert ausdrücklich genannt —
nach seiner Vorgabe vom 25.09.2026: Widerspricht die beste Lösung für
Kunde, Druck und Modell dem Bauplan, wird er mit Begründung nachgezogen.

---

## 1. Anlass: was Solidon heute über das Herstellerprofil legt

### 1.1 Der Minigolf-Druck

Robert druckte den Minigolf-Satz (`F:\3D Dateien\Mini+Golf+All+Set-P1S_stls`)
mit Solidons Übergabe im ElegooSlicer. Schicht 1 war ein treppenförmiger
Stützfuß, der Brim zerfiel in Stücke. Gemessen an denselben Körpern
(ElegooSlicer 1.5.3.4, Konsole):

| Lauf | Stütze gesamt | Brim-Ansätze in Schicht 1 |
|---|---|---|
| Solidons Übergabe (Gitter, nur vom Bett, Winkel 45) | 46,4 m | 298 |
| nur der Winkel auf Elegoos 30 | 2,9 m | 104 |
| Elegoos vollständiger Stützsatz (Baum, 30°, `auto_brim`) | 0 m | 63 |

Die feste 45°-Grenze ist mit Paket 1 behoben (`6254b4dff`, `cab9d6d30`: der
Winkel kommt je Drucker aus dem Herstellerprofil). Die Durchsicht aller drei
Slicerfamilien zeigte aber, dass der Winkel nur ein Fall einer Regel ist:
**Solidon schreibt seine Tabellenwerte über jedes Herstellerprofil**, gleich
ob der Wert vom Kunden, aus einem Vorschlag oder bloß aus Solidons
Qualitätsstufe kommt.

### 1.2 Orca-Familie (ElegooSlicer, OrcaSlicer, Bambu Studio, Creality Print)

`_orca_process` legt 45 Prozessschlüssel und `_orca_filament` 22
Filamentschlüssel über das aufgelöste Herstellerprofil. Abgeglichen an zwölf
Druckern (Standardprozess und Standard-PLA/-PETG des Herstellers):

- Stützart **Gitter statt Baum** bei Elegoo und Bambu, auch mit
  ausgeschalteten Stützen — wer im Slicerfenster Stützen einschaltet, bekommt
  Gitter.
- **Auto-Brim aus**, dafür zwei Skirt-Runden (`no_brim` statt der
  Programmvorgabe `auto_brim`, die kein Hersteller abschaltet).
- **Keine Druckplatte**: `curr_bed_type` schreibt Solidon nirgends, die Konsole
  nimmt dann „Cool Plate". `_with_every_plate` schreibt deshalb Solidons
  Betttemperatur auf alle Platten und hebt damit auch die Sperren auf, mit
  denen ein Hersteller eine Platte für ein Material ausschließt (0 °C).
- Erste Schicht 0,25 mm hoch, 0,449 mm breit, Düse +5 °C statt 0,2 / 0,5 /
  gleich.
- 3 statt 2 Wände, 4 statt 3 Bodenschichten, `arachne` statt `classic`,
  Füllmuster `grid` statt des Herstellermusters, alle Bahnbreiten 0,42.
- Tempi auf Solidons Volumenstrom gedeckelt: Bambu fährt alle Rollen mit
  142 mm/s (der `flow_factor` fehlt), der SV06 bekommt 8000 mm/s² über seiner
  Maschinengrenze.
- Rückzug und Z-Hop der Maschine überschrieben (CC2: Z-Hop 0,4 → 0,2).
- Eine lokale Spule gleichen Typs (Roberts „PLA Lavendal") bekommt Solidons
  Materialtabelle über Elegoos Filamentprofil.
- Stützen, Passungswerte und Verbinderwände gelten für die ganze Platte, auch
  wenn nur einer von fünf Körpern sie braucht.

`profile_differences` sagt es selbst: „Übergeben werden die Einstellungen."

### 1.3 PrusaSlicer

Die Übergabe ist eine `solidon.ini` mit 63 Schlüsseln, ohne Drucker-,
Prozess- oder Filamentprofil. **Von 347 wirksamen Schlüsseln sind 284
PrusaSlicers eingebaute Vorgaben**, nicht das Profil von Prusa. Im G-Code
fehlen deshalb Bettvermessung (`G29`), Spüllinie, Druckerprüfung (`M862`),
Pressure Advance (`M572`); die Firmware-Art ist `reprap` statt `marlin2`, die
erste Schicht fährt 4000 statt 500 mm/s², PETG geht als PLA hinaus. Der MINI
trägt Werte des abgelösten Profils ohne Input Shaper und den Rückzug eines
Direktantriebs (0,8 statt 2,5 mm am Bowden). Am Minigolf-Körper: 55,6 m Stütze
gegen 1,1 m beim Hersteller, 1 h 42 min gegen 1 h 09 min.

### 1.4 CuraEngine

Die Konsole liest aus einer Definition nur `default_value`, nie die
`value`-Formeln; Solidon schreibt deshalb einen vollständigen Satz (228
Werte) über `fdmprinter.def.json`. Es fehlt die Maschine: Start- und Endcode
sind die von `fdmprinter` (`G28`, `G1 Z15`, 3 mm Filament in der Luft, keine
Spüllinie, kein Bettnetz), die erste Schicht fährt mit der
Druckbeschleunigung (12 000 mm/s² am Ender-3 V3). Die Stützsperre und Stützen
je Teil gehen verloren, weil alle Teile als ein STL reisen, obwohl beides je
Netz ginge (gemessen). Überhänge zwischen alter und neuer Stützgrenze fahren
ohne Tempo-Rücknahme.

---

## 2. Grundsatz

> **Grundlage jeder Übergabe ist das Profil des Herstellers.** Solidon
> schreibt darüber nur, was davon abweichen soll: was der Kunde im Druckdialog
> selbst gesetzt hat, was ein übernommener Vorschlag mit einem Grund am Modell
> oder Material setzt, und was technisch nötig ist, damit das Herstellerprofil
> überhaupt richtig greift. Ohne Herstellerprofil — kein Slicer, ein Drucker,
> den sein Bestand nicht kennt, CuraEngine — bleiben Solidons Tabellen die
> Grundlage und werden vollständig geschrieben.

Das ist Roberts Maßstab vom 25.09.2026 an der Waschschüssel, als Solidons
Übergabe im ElegooSlicer schon in Schicht 1 scheiterte: Jede Abweichung vom
Herstellerprofil braucht einen Grund, der am Modell oder Material hängt. Das
alte Konzept versprach es schon (`konzept-slicer-uebergabe`, §6: „Kein
Überschreiben des Herstellerprofils") und löste es anders ein, als es klang:
„Solidon legt seine Werte darüber" hieß in der Praxis *alle* Werte.

**Was dabei nicht verloren geht.** Solidons Stärke ist die Geometrie: Stützen,
wo das Teil schwebt, Brim auf kleinen Füßen, langsame Außenwand an einer
Passung, mehr Wände an einem Verbinder. Das bleiben Vorschläge mit Grund, und
sie wirken genau dort, wo ihr Grund liegt — am Körper, nicht an der Platte.

---

## 3. Entscheidungen

### A — Jeder Wert weiß, woher er kommt

`PrintSettings` bekommt zwei Mengen von Punktpfaden (dieselben Pfade wie
`print_settings.with_path` und die Tabellen in `slicer_keys`):

| Feld | Bedeutung | Gesetzt von |
|---|---|---|
| `chosen` | der Kunde hat den Wert selbst gesetzt | Eingabe im Druckdialog; Übernahme beim Druckerwechsel; Einordnung einer älteren Datei (E) |
| `accepted` | der Wert kommt aus einem übernommenen Vorschlag | `advise.apply` |

Ein Pfad steht in höchstens einer Menge; eine Eingabe auf einem
angenommenen Pfad macht ihn zu einer eigenen Wahl. **Alle übrigen Werte sind
Grundlage** und werden bei jeder Verwendung neu bestimmt (B). Sie stehen
weiter vollständig in `PrintSettings` — jeder Leser (Schichtanalyse,
Schätzung, Plattenränder, Prüfbericht) bekommt einen ganzen Satz, nur eben
den, der gedruckt wird.

Warum zwei Mengen und nicht eine: Ein übernommener Vorschlag gilt dem Körper,
der ihn verlangt (G), eine eigene Wahl der ganzen Platte. Der Unterschied ist
genau der zwischen „dieses Teil braucht Stützen" und „ich will Stützen".

Warum Mengen und keine Abbildung Pfad → Herkunft: `PrintSettings` ist ein
eingefrorener, vergleichbarer und hashbarer Wert; zwei `frozenset` halten das.

### B — Die Grundlage kommt aus dem gewählten Herstellerprofil

`base_settings(profile, quality, setup)` im Exportpaket (neues Modul
`export/manufacturer.py`, kein Qt) baut die Grundlage:

1. `print_settings.resolve(profile, quality)` — Solidons Tabellen als Rückfall.
2. **Orca-Familie**: darüber die Rücklesung aus dem aufgelösten Prozess, dem
   aufgelösten Filament und aus der Maschine, was das Filament offen lässt
   (Rückzug, Z-Hop bei `nil`).
3. **PrusaSlicer**: darüber die Rücklesung aus Drucker, Prozess und Filament
   des Prusa-Bündels, aufgelöst mit dem vorhandenen `_PrusaStore`.
4. **CuraEngine und ohne Slicer**: nichts darüber (C).

Die Rücklesung ist die umgekehrte Übersetzungstabelle (`PROCESS_READBACK` je
Familie, Gegenstück zu `FILAMENT_READBACK`), mit den Umrechnungen der
Schreibseite rückwärts: Prozent zu Anteil, Winkel gegen die Waagerechte zu
gegen die Senkrechte (`support_threshold_angle 0` heißt beim Baum 30), Bahnbreiten
in Prozent der Düse, Plattentemperatur **der gewählten Platte** (F).

**Was das Profil nicht nennt, nimmt der Slicer aus seinen eingebauten
Vorgaben.** Für die übersetzten Schlüssel steht diese Vorgabe je Programm in
einer kleinen Tabelle (`precise_outer_wall` ist bei Orca an, bei Bambu Studio
aus; `brim_type` ist überall `auto_brim`) — gemessen am Konfigurationsblock
eines Laufs mit leerem Prozess, nicht aus der Erinnerung.

**Was sich nicht übersetzen lässt, wird nicht umgedeutet.** Ein Füllmuster wie
`crosshatch` oder eine Wandfolge `inner-outer-inner wall` hat in Solidon keinen
Namen. Die Grundlage behält dann Solidons Wert *für die eigene Rechnung*, der
Dialog zeigt den Herstellerwert mit seinem Namen, und geschrieben wird er
nicht — der Slicer druckt, was sein Profil sagt. Eine Rücklesung, die still
den nächsten Solidon-Wert annähme, schriebe ihn beim nächsten Speichern als
Abweichung zurück.

### C — CuraEngine bleibt bei Solidons Satz, bekommt aber seine Maschine

Die Formeln einer Cura-Definition zur Laufzeit auszuwerten ist ausgeschlossen:
Es wäre `eval` auf fremdem Text (Regel 10, altes Konzept §8). Die
mitgelieferten Cura-Druckerprofile sind zudem Gemeinschaftsbeiträge, nicht
Werksprofile; die Hersteller liefern heute Orca-Abkömmlinge, und aus denen
stammen Solidons Druckerwerte. **Für Cura bleibt Solidons vollständiger Satz
die Grundlage**, mit drei Änderungen:

- Die **Druckerdefinition** wird gewählt (`printers.toml`: `cura_definition`)
  und ihr Start- und Endcode übergeben — als eigene `-s`-Argumente, mit
  Platzhaltern, die Solidon durch reine Textersetzung aus seinen Werten füllt
  (kein Auswerter; ein unbekannter Platzhalter hält an, Regel 21), und
  `material_*_temp_prepend = false`, wo der Startcode die Temperaturen selbst
  setzt — wie das Cura-Fenster.
- Die Befunde B2 bis B11 des Cura-Berichts: eigene Beschleunigung der ersten
  Schicht, Stützen wie im Werksprofil, Überhangtempo, `infill_before_walls`,
  Leerfahrt und Bahnbreite der ersten Schicht, Fahrwege.
- Stützen je Teil und die Stützsperre als eigenes Netz (G).

Ein Drucker ohne Cura-Definition (Centauri Carbon 2, Prusa, Bambu, Ender-3 V3)
bekommt einen Befund statt stillem `fdmprinter`: „Cura kennt diesen Drucker
nicht — ohne Startcode des Herstellers: keine Spüllinie, kein Bettnetz."

### D — Die Übergabe schreibt Abweichungen

| Familie | Grundlage in der Datei | darüber | technisch nötig |
|---|---|---|---|
| Orca | Maschine, Prozess, Filament des Herstellers, vollständig aufgelöst (wie heute) | nur `chosen` und `accepted` | `curr_bed_type` (F); Objektmarken; Name und Verträglichkeit; Filamenttyp, Farbe, Name je Slot; Objektwerte (G); Stützsperre |
| PrusaSlicer | **neu:** Drucker, Prozess, Filament des Bündels, vollständig aufgelöst in `solidon.ini` und `Slic3r_PE.config` | nur `chosen` und `accepted` | `printer_settings_id`, `print_settings_id`, `filament_settings_id` in der Beilage (das Fenster nimmt dann das installierte Profil und zeigt „(geändert)"); im Konsolenlauf `binary_gcode = 0` (Solidon liest Text); Stützen an heißt `support_material = 1` **und** `support_material_auto = 1` (die Prusa-Vorgabe ist „nur Verstärker"); `filament_type` für ein Material ohne Bündelprofil; Objektwerte; Stützsperre |
| CuraEngine | Solidons Satz (C) | — | Druckerdefinition, Start-/Endcode, Netze je Teil |

Ohne Herstellerprofil unter der Übergabe schreibt Solidon wie heute alles.
`machine_limits_usage = ignore` für Prusa entfällt: sein Grund waren die
eingebauten Grenzen, die mit dem Druckerprofil verschwinden.

### E — Ältere Projekte: nur eigene Werte bleiben eigene Werte

Eine Datei vor Format 36 kennt keine Herkunft, und ihr voller Satz ist kein
Beleg für eine Entscheidung: Bis 0.5.1 schrieben `_plate_job`,
`MainWindow._inventory_settings` und `history.restore` den aufgelösten Satz
ungefragt ins Projekt. Alles als eigene Wahl zu lesen, hielte den Fehler für
jedes jemals geschnittene Projekt am Leben; alles zu verwerfen, nähme dem
Kunden seine bewussten Änderungen.

**Entscheidung:** Die Migration 35→36 ordnet ein. Als eigene Wahl gilt ein
gespeicherter Wert, der **weder** der heutigen Auflösung für Drucker, Material
und Stufe des Projekts **noch** der Vorgabe der Dataclass gleicht. Damit
fallen die alten Tabellenwerte heraus — auch die 40 mm/s von vor dem 25.09.
(RM-256), denn sie sind die Dataclass-Vorgabe —, und was jemand selbst
eingetragen hat, bleibt. Früher übernommene Vorschläge werden eigene Wahl; sie
galten schon bisher der ganzen Platte, es ändert sich für sie also nichts.

Das ruft wie `_bind_old_lid_fits` die **heutigen** Funktionen und ist darin
angreifbar; festgehalten wird es mit einer eingecheckten v35-Datei, deren
Einordnung ein Test prüft. Der Dialog zeigt die übernommenen eigenen Werte beim
ersten Öffnen als eigene Wahl mit Rücksetzknopf (H), sodass nichts still
verschwindet und nichts still bleibt.

### F — Die Druckplatte ist eine Angabe, keine Vermutung

Orca-Familie: `curr_bed_type` steht immer in der Übergabe, in der Beilage der
3MF **und** in der Prozessdatei des Konsolenlaufs (welcher der beiden Wege mit
`--load-settings` greift, ist nicht gemessen — sicher ist beides). Der Wert
ist die Wahl im Druckdialog, sonst die Standardplatte der Maschine
(`default_bed_type`). `_with_every_plate` entfällt: Die Grundlage liest die
Temperatur **der gewählten Platte**, geschrieben wird eine Betttemperatur nur
als eigene Wahl und nur für diese Platte.

`default_bed_type` steht meist als Name („Textured PEI Plate"), bei Elegoo als
Zahl. **Belegt ist „4" = Textured PEI Plate**: Alle 34 mit ElegooSlicer 1.5.x
gespeicherten Projekte in `F:\3D Dateien` für Centauri Carbon und Centauri
Carbon 2 tragen `curr_bed_type = Textured PEI Plate`, fünf davon zusammen mit
`default_bed_type = 4`; keines nennt eine andere Platte. Die Sonden dieses
Tages nahmen „4" als High Temp Plate — das war falsch und ist in ihnen
berichtigt.

Nennt der Hersteller für eine Platte und ein Filament 0 °C, ist die Platte für
dieses Filament gesperrt (`Print.cpp`: „does not support filament"). Solidon
überschreibt die Null nicht, sondern meldet es mit der Handlung „Andere Platte
wählen".

### G — Was aus dem Körper folgt, gilt dem Körper

Ein **übernommener** Vorschlag, dessen Grund an der Geometrie hängt, wird je
Teil geschrieben, nicht für die Platte: Stützen (Art, Ort, Sperre), Brim,
Passungswerte (genaue Außenwand, Außenwandtempo und -beschleunigung,
Bügeln), Verbinderwände und -füllung, schmale Stellen (Wandgenerator,
Bahnbreite). Die Übergabe fragt dafür je Körper `advise.for_part` und schreibt
dessen Werte für die angenommenen Pfade als Objektwerte:

- Orca: `Metadata/model_settings.config` je Objekt (`enable_support`,
  `support_type`, `support_on_build_plate_only`, `brim_type`, `brim_width`,
  `wall_loops`, `precise_outer_wall`, …).
- PrusaSlicer: `Metadata/Slic3r_PE_model.config` je Objekt.
- CuraEngine: je Teil ein Netz mit `-l teil.stl -s support_enable=…` und die
  Sperre als eigenes Netz mit `anti_overhang_mesh=true` (gemessen: 18 476
  Stützbewegungen → 0, Modell unverändert). Haftung ist dort nicht je Netz
  einstellbar; der Befund „unerfüllt" bleibt dafür richtig.

Eine **eigene Wahl** im Dialog gilt weiter der ganzen Platte. Material- und
Maschinenwerte (Temperatur, Kühlung, Rückzug, Volumenstrom) bleiben
plattenweit — sie hängen an der Spule, nicht am Teil.

Damit ist auch RM-250 entschieden: Der Brim je Teil kommt nicht mehr ohne
Klick, sondern mit der Übernahme des Vorschlags, und dann nur an den Teilen,
die ihn brauchen.

### H — Der Druckdialog zeigt, was gedruckt wird

- Jedes Feld zeigt den wirksamen Wert. Eine eigene Wahl oder ein übernommener
  Vorschlag trägt eine Marke und einen Knopf *Zurücksetzen*; der Tooltip nennt
  den Wert aus dem Profil. Ein Wert aus dem Profil trägt keine Marke.
- Unter der Kopfzeile steht die Grundlage in einem Satz: Prozess, Filament,
  Platte („Grundlage: 0.20mm Standard @Elegoo CC2 · Elegoo PLA @ECC2 ·
  Texturierte PEI-Platte").
- Die Druckplatte ist in der Orca-Familie wählbar (die Platten, die das
  Programm kennt; vorgewählt die Standardplatte der Maschine).
- PrusaSlicer bekommt dieselbe Profilwahl wie die Orca-Familie: Drucker samt
  Düsenvariante, Prozess, Filament.
- *Werte übernehmen* am Filament entfällt: Die Werte des Herstellerfilaments
  *sind* jetzt die Grundlage.
- Die Stufe wählt den Herstellerprozess (I).

### I — Die Stufe wählt den Prozess des Herstellers

Solidons vier Stufen stehen für vier Prozesse, die jeder Hersteller führt:
Standard → der Standardprozess der Maschine (`default_print_profile`), Fein →
der feinste mit „Fine"/„DETAIL"/„QUALITY" um 0,12 mm, Entwurf → „Draft"/
„DRAFT" um 0,24–0,28 mm, Belastbar → „Strength"/„STRUCTURAL" bei der
Standard-Schichthöhe. Ein Stufenwechsel stellt das Prozessfeld; eine Wahl im
Prozessfeld stellt die Stufe auf die nächstliegende oder auf „Eigene". Findet
sich kein passender Prozess, bleibt der gewählte, und die Schichthöhe der
Stufe wird eigene Wahl — der Kunde hat „Fein" gesagt.

### J — Stützen einschalten heißt nicht „Gitter"

`SupportStyle` bekommt `auto`: Stützen an, Art aus dem Profil des Slicers.
Der Vorschlag „Stützen nötig" setzt `auto`, außer ein Grund am Modell verlangt
eine Art (viele Inselschichten → Baum, `TREE_FROM_ISLANDS`). Übersetzt heißt
`auto` in der Orca-Familie `enable_support = 1` ohne `support_type`, bei
PrusaSlicer `support_material = 1` und `support_material_auto = 1` ohne Stil,
bei Cura `support_enable = true`. `none` schreibt nur noch den Schalter, nicht
mehr `support_type normal(auto)`. Das Kreuzmuster aus der Waschschüssel
(`rectilinear-grid`) bleibt an der ausdrücklichen Art „Gitter" und gilt nur
der Orca-Familie, wo es gemessen ist.

Ebenso bekommt `AdhesionType` `auto` (Orca `auto_brim`, bei den anderen die
Vorgabe des Profils), und das ist der Wert, den die Grundlage in der
Orca-Familie meist zurückliest.

### K — Die Gegenprobe prüft auch, was nicht geschrieben wurde

`verify_settings` vergleicht heute nur die geschriebenen Werte. Schreibt
Solidon weniger, prüfte es weniger. Dazu kommen:

- die **Grundlage**: eine Stichprobe von Schlüsseln, die Solidon nicht
  schreibt, gegen die Rücklesung (Schichthöhe, Wände, Düsentemperatur,
  Stützschwelle) — sie beweist, dass das Herstellerprofil wirklich darunter
  lag;
- die **Identität**: `printer_settings_id`/`printer_model` bei PrusaSlicer,
  `curr_bed_type` in der Orca-Familie;
- der **Startcode**: bei PrusaSlicer und Cura die Marken des Herstellers
  (`G29`, `M420 S1`, `START_PRINT`), wo seine Definition sie trägt.

### L — Die Analyse rechnet mit dem, was der Slicer tut

Die Stützgrenze der Schichtanalyse ist die wirksame Stützschwelle der
Übergabe — gemessen, sonst die des gewählten Prozesses, sonst die des
Druckers aus `printers.toml` (Paket 1), sonst 45°. Wählt der Kunde einen
anderen Prozess (Prusa „STRUCTURAL" stützt ab 50° statt 55° gegen die
Senkrechte), folgt die Analyse. `profiles.for_process` bekommt dafür die Schwelle aus den
Einstellungen. Die übrigen Vorschläge rechnen ebenfalls gegen die Grundlage:
Wandzahl, Bahnbreite, Volumenstrom des gewählten Filaments.

---

## 4. Stufen der Umsetzung

Jede Stufe endet grün (Entwicklungstor), mit ihrer Messung im echten Slicer
und mit einem eigenen Merge. Reihenfolge nach Wirkung und Abhängigkeit.

| Stufe | Inhalt | Abnahme |
|---|---|---|
| **A** Grundlage und Herkunft | `chosen`/`accepted`, `base_settings` mit Rücklesung Orca und Prusa samt Programmvorgaben, wirksame Einstellungen überall (Dialog, Prüfbericht, Statuszeile, Übergabe), Format 36 mit Einordnung (E), `advise.apply` und Dialogeingaben markieren, Bauplan §29 | Rücklesung CC2/Bambu/Prusa gegen die aufgelösten Profile Schlüssel für Schlüssel; v35-Beispieldatei ordnet ein; Tor grün |
| **B** Orca schreibt Abweichungen | Prozess/Filament nur `chosen`+`accepted`; `curr_bed_type` und Plattenwahl (F); `SupportStyle`/`AdhesionType` `auto` (J); `_with_every_plate` fällt; Gegenprobe (K) | **Ohne Vorschläge ist Solidons G-Code-Konfiguration gleich der des Herstellerprofils allein**, bis auf die technisch nötigen Schlüssel — an Minigolf-Platte, Waschschüssel und einem Passungsteil, ElegooSlicer und Bambu Studio |
| **C** PrusaSlicer auf dem Bündel | Profilsuche und -wahl im Dialog (Drucker mit Düsenvariante, Prozess, Filament); Bündel vollständig in INI und Beilage; `*_settings_id`; `binary_gcode`; `support_material_auto`; `filament_type`; Gegenprobe (K) | dieselbe Gleichheit mit dem Herstellerlauf an MK4S (HF0.4), MINI IS und XL IS; `G29`, `M862`, `M572` im G-Code |
| **D** Cura mit Maschine | `cura_definition`, Start-/Endcode mit Platzhaltern, Befunde B2–B11, `.curaprofile` an die aktive Maschine | Startcode des Druckers im G-Code (Ender-3 V3 SE `M420 S1`, K1 Max `START_PRINT`), kein `{`, genau ein `M190`; erste Schicht mit 500 mm/s² |
| **E** Je Teil | `for_part` für alle geometrischen Pfade (G); Objektwerte Orca/Prusa; Netze je Teil und Sperrnetz bei Cura | Minigolf-Satz mit einem gestützten Körper: Stütze nur an ihm, Brim der übrigen geschlossen |
| **F** Stufe wählt Prozess | Zuordnung Stufe ↔ Herstellerprozess (I) | vier Stufen an CC2, P1S, MK4S finden je einen Prozess; Umschalten hin und zurück ist verlustfrei |

Danach folgen Paket 3 (die Vorschlagsregeln selbst: Mindestschichtzeit,
Keilspitzen, Stützbedarf gegen das Urteil des Herstellers, Brückenregel) und
der Lauf „jedes Modell × jeder Slicer" als Gesamtabnahme.

---

## 5. Was nicht gebaut wird

- **Kein Auswerten von Cura-Formeln** (C, Regel 10).
- **Kein eigener Startcode.** Er kommt vom Hersteller oder er fehlt mit Befund
  (Entscheidung Robert, 26.08.2026: „Der Anfahrcode bleibt der des
  Herstellers").
- **Keine Werte „zur Sicherheit".** Was keinen Grund am Modell oder Material
  hat, wird nicht geschrieben — auch nicht, wenn Solidons Tabelle es anders
  kennt.
- **Keine Stützverstärker in dieser Runde.** Inseln und große freie Stücke als
  `SupportEnforcer` zu übergeben (Prusa-Bericht N2) ist besser als jede
  Schwelle, aber eine neue Fähigkeit; sie gehört in das Register, nicht in
  diesen Umbau.

---

## 6. Was der Kunde davon merkt (für den Changelog 0.5.1)

Ein Satz kommt nur in den Changelog, wenn 0.5.0 den Fehler schon hatte;
geprüft wird das je Satz mit `git tag --contains` an dem Commit, der das
Verhalten eingeführt hat, wenn die Stufe abgenommen ist. Die Sätze darunter
sind die Richtung, nicht der Wortlaut.

- Solidon druckt mit dem Profil Ihres Druckerherstellers und ändert nur, was
  Ihr Modell verlangt oder Sie selbst einstellen.
- PrusaSlicer bekommt Drucker, Prozess und Filament von Prusa: mit
  Bettvermessung, Spüllinie und Druckerprüfung.
- Cura bekommt den Startcode Ihres Druckers.
- Stützen und Brim gelten nur den Teilen, die sie brauchen.
- Die Druckplatte wird mitgegeben; die Temperatur stimmt zur Platte.
