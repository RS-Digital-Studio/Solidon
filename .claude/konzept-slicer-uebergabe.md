# Konzept — Druckeinstellungen automatisch setzen, bevor der Slicer sie bekommt

Anlass: das Gewürzset (Projekt 08 im Ordner `3D Drucker`) wurde von Hand für
den ElegooSlicer eingerichtet. Alles, was dabei per Hand nötig war, ist die
Prüfliste für diese Frage — kann Formwerk das, und soll es das von allein tun?

Bezug: Bauplan §29 (Export und Slicer-Übergabe), §28 (Rückkopplung), §22.5
(Herkunft der Kennzahlen), §2.7 (Fehler als Vorschlag).

---

## 1. Was Formwerk heute schon kann

Mehr als erwartet. Der Weg steht vollständig:

| Baustein | Datei | Stand |
|---|---|---|
| Einstellungen halten | `knowledge/print_settings.py` | Stufe + Material + Drucker zu einem `PrintSettings` |
| In die Sprache des Slicers | `export/slicer_keys.py` | 50 Zuordnungen für Orca, dazu Prusa und Cura |
| Profil schreiben, Slicer rufen | `export/handover.py` | Konsolenlauf, Zeitlimit, G-Code zurücklesen |
| Profile des Slicers finden | `export/slicer_profiles.py` | Maschine und Prozess, Erbkette der Verträglichkeit |
| Aus der Geometrie schließen | `slice/advise.py` | Stützen, Haftung, Linienbreite, Schichtzeit, Volumenstrom, Passungstempo |
| Gegenprobe | `handover.verify` | liest die Konfigurationskommentare der erzeugten Datei |
| Baugruppe schreiben | `export/threemf.py` | mehrere Körper, Materialslots über `merge_slots` |

`advise.py` ist dabei genau die richtige Idee: jeder Vorschlag trägt seinen
Grund, übernommen wird auf Klick. Das ist die Denkweise, die auch beim
Gewürzset getragen hat — Brim wegen kleiner Standfläche, langsame Außenwand
wegen der Passung, Mindestschichtzeit wegen der kleinen Deckelfläche.

## 2. Drei Lücken, gemessen

### 2.1 Achtzehn von fünfzig Werten landen im falschen Profil

Die Orca-Familie verteilt ihre Einstellungen auf drei Profiltypen. Formwerk
schreibt alles in **ein** Prozessprofil und lädt `--load-settings machine;process`.
Abgeglichen mit dem echten Profilbestand des installierten ElegooSlicer:

```
14 Schlüssel führt Elegoo im FILAMENT-Profil:
   nozzle_temperature, nozzle_temperature_initial_layer,
   hot_plate_temp, hot_plate_temp_initial_layer,
   fan_min_speed, fan_max_speed, overhang_fan_speed,
   close_fan_the_first_x_layers, slow_down_layer_time,
   filament_diameter, filament_density, filament_flow_ratio,
   filament_cost, filament_max_volumetric_speed

 4 Schlüssel führt Elegoo im MACHINE-Profil:
   retraction_length, retraction_speed, z_hop, wipe
```

Das heißt: **Temperatur, die gesamte Kühlung, der gesamte Rückzug und alle
Filamentwerte kommen beim Slicen nicht an.** Sie stehen in einer Datei, die
der Slicer für etwas anderes liest. Gedruckt wird mit dem, was im Slicer
zuletzt eingestellt war.

Die Spur davon steht schon im Code: `handover._RECOMPUTED` nimmt
`filament_colour`, `filament_density`, `filament_cost` und
`filament_max_volumetric_speed` von der Gegenprobe aus, mit der Begründung,
der Slicer rechne sie um. Er rechnet sie nicht um — er bekommt sie nie.

Die Gegenprobe (`verify`) würde den Rest melden. Sie läuft nur, wenn jemand
einen echten Lauf macht; in der Suite gibt es keinen.

### 2.2 Das Filamentprofil fehlt ganz

`slicer_profiles.PROFILE_DIRS` kennt `machine` und `process`. Der Ordner
`filament` wird nicht durchsucht, und `handover._command` übergibt kein
Filamentprofil. Damit lässt sich nicht ausdrücken, was beim Gewürzset der
Kern der Sache war: **transluzentes** PETG für den Behälter, graues für den
Deckel. Formwerk kann heute „PETG" sagen, nicht „`Elegoo PETG Translucent
@ECC2`".

### 2.3 Materialwerte werden doppelt gepflegt und weichen ab

`knowledge/data/print_settings.toml` führt eigene Materialwerte. Gegen den
Bestand des installierten Slicers:

| | Formwerk `material.petg` | `Elegoo PETG Translucent` | `Elegoo PETG PRO` |
|---|---|---|---|
| Düse | 240 / 245 °C | **255 / 255 °C** | 240 / 240 °C |
| Bett | 80 / 80 °C | **70 / 70 °C** | 70 / 70 °C |
| Volumenstrom | 12 mm³/s | 10 mm³/s | **5 mm³/s** |
| Pressure Advance | kennt Formwerk nicht | 0,052 | 0,1 |

Das Bett liegt 10 °C daneben, der Volumenstrom beim PRO um mehr als das
Doppelte. Keine dieser Zahlen ist falsch geraten — sie sind für „PETG im
Allgemeinen" richtig und für *dieses Filament auf diesem Drucker* eben nicht.
Der Hersteller weiß es besser, und seine Angabe liegt auf der Platte.

## 3. Was im Modell fehlt

Beim Gewürzset gesetzt, in `PrintSettings` nicht vorhanden:

| Wert | wofür er dort gebraucht wurde |
|---|---|
| `wall_generator` (Arachne) | Federarme 1,1 mm und Rastzunge 1,4 mm — schmaler als drei feste Linienbreiten |
| `precise_outer_wall` | Gewinde- und Klipp-Passung |
| Pressure Advance | steht in jedem Elegoo-Filamentprofil, wirkt auf jede Ecke |
| Elefantenfuß-Korrektur | erste Schicht bei 70–80 °C Bett |
| `bridge_speed`, `bridge_flow` | Lochplatte überspannt Ø 34,9, Behälter 4,4 mm Ringschulter |
| Bügeln (`ironing_*`) | Gleitfläche zwischen Lochplatte und Streuscheibe |
| Beschleunigungen | Vorlage fuhr 10 000 mm/s² — Maßhaltigkeit |
| `xy_hole_compensation` | musste ausdrücklich auf 0 stehen, sonst verstellt sie gerechnete Passungen |
| `brim_object_gap` | Brim abziehbar halten |

Dazu zwei strukturelle Fähigkeiten:

- **Einstellungen je Objekt.** Beim Gewürzset brauchte die Streuscheibe Brim
  und die Deckelbasis Bügeln — nicht die anderen Teile. `PrintSettings` gilt
  heute für die ganze Platte. Die 3MF-Seite kann es bereits (`model_settings.config`
  nimmt Metadaten je Objekt), das Modell nicht.
- **Aufteilung nach Filament.** Behälter (transluzent, 68 mm) und Deckel (grau,
  22 mm) auf einer Platte hieße bis Schicht 110 ein Filamentwechsel je Lage:
  rund 220 Wechsel, 30–50 g Spülmaterial, gut anderthalb Stunden. Getrennt
  kostet es einen zweiten Lauf und kein Gramm. Das ist eine Rechnung, die die
  Anwendung führen kann — sie kennt Höhen, Materialslots und das Spülvolumen.

## 4. Wo die Grenze zwischen „automatisch" und „vorgeschlagen" liegt

Der Bauplan sagt in §2.7 und in `advise.py`: angewandt wird nichts von allein.
Das gilt weiter — aber es gilt nicht für alles gleichermaßen. Zwei Arten von
Werten sind zu unterscheiden:

**Zwingend, ohne Rückfrage.** Wo etwas nachweislich falsch ankommt, ist die
Korrektur keine Geschmacksfrage, sondern die Aufgabe:

- Jeder Wert in das Profil schreiben, in das er gehört
- Das Filamentprofil mitgeben, das zum gewählten Material gehört
- Werte, die der Hersteller für dieses Filament angibt, als Grundlage nehmen

Hier zu fragen wäre keine Höflichkeit, sondern eine Zumutung: Niemand kann
beantworten, ob `hot_plate_temp` ins Filament- oder Prozessprofil gehört —
das ist eine Tatsache über den Slicer, keine Entscheidung des Nutzers.

**Vorgeschlagen mit Begründung, vorbelegt angehakt.** Alles, was aus der
Geometrie folgt und wo es einen vertretbaren Gegengrund geben kann: Arachne,
Bügeln, Brim je Objekt, Bridging-Tempo, Plattenaufteilung. Genau der Weg, den
`advise.py` schon geht.

Für die Übergabe heißt das: **ein Blick vor dem Lauf**, der zeigt, was gilt und
was Formwerk geändert hat — kein Dialog, der nach jedem Wert fragt (Regel 19:
das Slicen ist rücknehmbar, es entsteht nur eine Datei).

## 5. Vorschlag in fünf Stufen

### Stufe 1 — Werte dorthin schreiben, wo sie hingehören — **umgesetzt**
`slicer_keys.Entry` trägt die Profilart, `handover.write_config` schreibt für
die Orca-Familie Prozess- und Filamentprofil getrennt, `_command` lädt das
Filament über den eigenen Schalter `--load-filaments`.

Ein Maschinenprofil schreibt Formwerk **nicht**: der Rückzug geht über die
`filament_*`-Entsprechungen, die Orca dafür vorsieht. Das erspart den Eingriff
in ein Profil, das die Kinematik trägt, und passt zur Herkunft — bei Formwerk
kommt der Rückzug aus dem Material.

Abgesichert durch `test_every_orca_setting_sits_in_the_profile_it_claims`: er
liest den Profilbestand eines installierten Slicers und vergleicht ihn mit der
Tabelle. Am alten Stand wäre er mit achtzehn Verstößen rot gewesen, jetzt sind
es null. Ohne installierten Slicer wird er übersprungen, nicht grün.

### Stufe 2 — Filamentprofile lesen und benennen — **umgesetzt**
`slicer_profiles` kennt jetzt auch `filament/` und löst mit `resolve_values`
die Erbkette auf — beim transluzenten Elegoo-PETG fünfundfünfzig Werte aus vier
Dateien, wo die oberste nur drei nennt. `match_filament` wählt die
Grundausführung des eingestellten Materials vor; der Dialog zeigt sie zur
Auswahl und merkt sie sich. `handover` legt die Formwerk-Werte darauf, statt
ein Profil zu erfinden.

Zwei Dinge, die beim Bauen auffielen:

- **Der Index der Erbkette läuft über den Profilnamen, nicht den Dateinamen.**
  Bei Elegoo sind beide zufällig gleich; wo sie es nicht sind, bräche die Kette
  nach der ersten Datei ab, ohne dass etwas zu fehlen scheint. Ein Test mit
  abweichenden Dateinamen hat es gefunden.
- **Filamente werden nur auf Verlangen gelesen** (`kinds`). Sie vervielfachen
  den Bestand — 5962 gegen 3887 —, und der Dialog, der nur den Drucker sucht,
  soll sie nicht mitlesen.

`profile_differences` meldet, wo Formwerks Tabelle und das Herstellerprofil
auseinandergehen. Übernommen wird nichts davon: die Einstellung ist die
Entscheidung des Nutzers, das Profil die Unterlage für alles, was Formwerk
nicht setzt.

### Stufe 3 — die fehlenden Stellschrauben ins Modell
Die Werte aus Abschnitt 3, jeweils mit Zuordnung in allen drei Tabellen. Dazu
die passenden Regeln in `advise.py`:

- schmalste Wand unter drei Linienbreiten → Arachne
- Projekt hat Passungen → präzise Außenwand, gebremste Beschleunigung
- Brückenweite über einem Schwellwert → Brückentempo und Lüfter
- Fläche, auf der etwas gleiten oder dichten soll → Bügeln

Die letzte Regel braucht Wissen, das die Schichtanalyse nicht hat. Sie kommt
aus der Passung: Wo ein `Fit` zwei Flächen aufeinander legt, ist die obere
eine Gleitfläche. Damit ist es eine Ableitung aus dem Dokument, keine Heuristik.

### Stufe 4 — Einstellungen je Objekt
`PrintSettings` bleibt die Platte, dazu ein Satz Abweichungen je Objekt. Der
3MF-Schreiber trägt sie als Metadaten ein, `handover` gibt sie mit. Damit
bekommt die Streuscheibe ihren Brim, ohne dass zwölf Behälter einen bekommen.

### Stufe 5 — Platten aus Materialgruppen
`merge_slots` kennt die Slots bereits. Der Schritt davor fehlt: Teile nach
Filament gruppieren, je Gruppe eine Platte, und wenn eine Gruppe nicht auf eine
Platte passt, mehrere. Die Anordnung rechnet den Haftungsrand mit — beim
Gewürzset war die erste Belegung zu eng, weil der Brim nicht mitgezählt wurde.
Wer zwei Filamente auf einer Platte will, bekommt die Rechnung genannt
(Wechselzahl, Spülmenge, Zeit) und entscheidet.

## 6. Was nicht gebaut wird

- **Kein eigener Slicer** (§22) — auch keine Nachbildung seiner Profillogik.
  Gelesen wird, was da ist; erfunden wird nichts.
- **Kein Überschreiben des Herstellerprofils.** Formwerk legt seine Werte
  darüber, wie es §29 vorsieht. Was es nicht anfasst, bleibt stehen.
- **Keine Kalibrierung im Hintergrund.** Flussrate und Toleranzen kommen aus
  §28.3, gemessen am gedruckten Teil, nicht geschätzt.

## 7. Abnahme

1. Ein Lauf gegen ElegooSlicer, bei dem `handover.verify` **keine** Abweichung
   meldet — heute meldete er achtzehn, wenn jemand hinsähe.
2. Ein Testfall, der die Profilart jedes Eintrags in `slicer_keys` gegen den
   Bestand eines installierten Slicers prüft und rot wird, sobald ein Wert im
   falschen Profil landet. Ohne installierten Slicer übersprungen, nicht grün.
3. Das Gewürzset als Referenz: aus Formwerk heraus dieselben drei Platten mit
   denselben Werten, die jetzt von Hand entstanden sind.

Punkt 3 ist der eigentliche Maßstab. Was ein Mensch für ein Projekt von Hand
einstellen musste, ist die Liste dessen, was die Anwendung können soll.
