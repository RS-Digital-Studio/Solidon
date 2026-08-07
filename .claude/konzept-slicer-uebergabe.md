# Konzept — Druckeinstellungen automatisch setzen, bevor der Slicer sie bekommt

Anlass: das Gewürzset (Projekt 08 im Ordner `3D Drucker`) wurde von Hand für
den ElegooSlicer eingerichtet. Alles, was dabei per Hand nötig war, ist die
Prüfliste für diese Frage — kann Solidon das, und soll es das von allein tun?

Bezug: Bauplan §29 (Export und Slicer-Übergabe), §28 (Rückkopplung), §22.5
(Herkunft der Kennzahlen), §2.7 (Fehler als Vorschlag).

---

## 1. Was Solidon heute schon kann

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

Die Orca-Familie verteilt ihre Einstellungen auf drei Profiltypen. Solidon
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
Deckel. Solidon kann heute „PETG" sagen, nicht „`Elegoo PETG Translucent
@ECC2`".

### 2.3 Materialwerte werden doppelt gepflegt und weichen ab

`knowledge/data/print_settings.toml` führt eigene Materialwerte. Gegen den
Bestand des installierten Slicers:

| | Solidon `material.petg` | `Elegoo PETG Translucent` | `Elegoo PETG PRO` |
|---|---|---|---|
| Düse | 240 / 245 °C | **255 / 255 °C** | 240 / 240 °C |
| Bett | 80 / 80 °C | **70 / 70 °C** | 70 / 70 °C |
| Volumenstrom | 12 mm³/s | 10 mm³/s | **5 mm³/s** |
| Pressure Advance | kennt Solidon nicht | 0,052 | 0,1 |

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
was Solidon geändert hat — kein Dialog, der nach jedem Wert fragt (Regel 19:
das Slicen ist rücknehmbar, es entsteht nur eine Datei).

## 5. Vorschlag in fünf Stufen

### Stufe 1 — Werte dorthin schreiben, wo sie hingehören — **umgesetzt**
`slicer_keys.Entry` trägt die Profilart, `handover.write_config` schreibt für
die Orca-Familie Prozess- und Filamentprofil getrennt, `_command` lädt das
Filament über den eigenen Schalter `--load-filaments`.

Ein Maschinenprofil schreibt Solidon **nicht**: der Rückzug geht über die
`filament_*`-Entsprechungen, die Orca dafür vorsieht. Das erspart den Eingriff
in ein Profil, das die Kinematik trägt, und passt zur Herkunft — bei Solidon
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
Auswahl und merkt sie sich. `handover` legt die Solidon-Werte darauf, statt
ein Profil zu erfinden.

Zwei Dinge, die beim Bauen auffielen:

- **Der Index der Erbkette läuft über den Profilnamen, nicht den Dateinamen.**
  Bei Elegoo sind beide zufällig gleich; wo sie es nicht sind, bräche die Kette
  nach der ersten Datei ab, ohne dass etwas zu fehlen scheint. Ein Test mit
  abweichenden Dateinamen hat es gefunden.
- **Filamente werden nur auf Verlangen gelesen** (`kinds`). Sie vervielfachen
  den Bestand — 5962 gegen 3887 —, und der Dialog, der nur den Drucker sucht,
  soll sie nicht mitlesen.

`profile_differences` meldet, wo Solidons Tabelle und das Herstellerprofil
auseinandergehen. Übernommen wird nichts davon: die Einstellung ist die
Entscheidung des Nutzers, das Profil die Unterlage für alles, was Solidon
nicht setzt.

### Stufe 3 — die fehlenden Stellschrauben ins Modell — **umgesetzt**
Neu in `PrintSettings`: `shell.wall_generator`, `shell.precise_outer_wall`,
`shell.ironing`, `speed.bridge`, `speed.acceleration`,
`speed.outer_wall_acceleration` — mit Vorgaben je Qualitätsstufe und Zuordnung
in allen drei Tabellen, soweit ein Slicer die Sache kennt. Was er nicht kennt,
bekommt keinen Eintrag: CuraEngine hat keinen umschaltbaren Wandgenerator,
PrusaSlicer keine gesonderte genaue Außenwand, und beide rechnen ohnehin mit
variabler Bahnbreite. Eine Zuordnung auf das Nächstbeste wäre eine Einstellung,
die woanders landet.

Regeln in `advise.py`:

- schmalste Stelle unter drei Linienbreiten → Arachne (Warnung)
- Projekt hat Passungen → präzise Außenwand und Beschleunigung auf 2000 mm/s²
- Überhänge im Teil → Brückentempo höchstens Außenwandtempo

**Zwei Werte aus der Liste blieben bewusst draußen.** Beide hätte Solidon
doppelt gerechnet:

- **Elefantenfuß.** Dafür gibt es die Op `compensate_elephant_foot`, die in der
  Geometrie arbeitet und laut eigenem Docstring „genau das tut, was die
  Elefantenfuß-Kompensation eines Slicers tut". Den Wert zusätzlich zu
  übergeben hieße, zweimal einzuziehen.
- **Lochkorrektur.** `MaterialProfile.hole_compensation` ist ein kalibrierter
  Wert, der bisher nur in die Hashsumme eingeht — es gibt keine Op, die ihn
  anwendet. Ihn an den Slicer zu geben würde die Sache nicht klären, sondern
  die Frage verschieben, wer kompensiert. Das gehört erst entschieden.

Bügeln ist an/aus, ohne Feinwerte: **ob** gebügelt wird, ist die Entscheidung —
wie stark und mit welchem Abstand weiß der Slicer besser. Die Regel „Fläche,
auf der etwas gleiten soll" aus dem `Fit` abzuleiten steht noch aus; heute ist
es ein Schalter im Dialog.

### Stufe 4 — Einstellungen je Objekt — **umgesetzt**
`AssemblyPart.settings` trägt, was nur für ein Teil gilt; `write_assembly`
schreibt dafür `model_settings.config`. `advise.for_part` entscheidet die
Plattenhaftung je Teil, `handover.object_keys` übersetzt sie — und zwar die
ganze Gruppe, weil zur Haftungsart ihr Maß gehört und die Maße der anderen
Arten auf null müssen.

Dabei kam ein zweiter Fund heraus: **die Objektnamen kamen im Slicer nie an.**
Solidon schrieb sie ins `name`-Attribut des Standards, aber die Orca-Familie
schreibt das selbst nie und liest die Namen aus `model_settings.config`. Eine
Baugruppe erschien deshalb als „Object 1, Object 2", obwohl die Namen in der
Datei standen. Dieselbe Beilage löst beides.

Die Grundfläche kommt aus einem Schnitt 0,2 mm über dem Boden, nicht aus der
Bounding-Box: ein Teil auf drei schmalen Armen hat eine große Bounding-Box und
kaum Halt — genau der Fall, für den die Unterscheidung da ist.

Plattenweit bleiben Temperatur, Kühlung und Stützen: sie hängen am Material
oder an der Maschine, und je Teil verstellt wären sie ein Widerspruch, den der
Slicer auflösen müsste.

### Stufe 5 — Platten aus Materialgruppen — **umgesetzt**
Drei Stücke, alle drei aus dem Gewürzset abgeleitet:

- **`plates_by_material`** schlägt vor, welches Teil auf welche Platte gehört —
  ein Filament je Platte. Die Reihenfolge folgt dem ersten Auftreten, damit
  derselbe Entwurf zweimal dieselbe Zuordnung ergibt. Ein Objekt mit mehreren
  Slots bleibt zusammen: ein zweifarbiges Schild lässt sich nicht auf zwei
  Platten legen. Zurück kommt ein Vorschlag, keine Änderung — die Platte eines
  Objekts gehört ins Dokument und wird über eine Transaktion gesetzt.
- **`check_adhesion_clearance`** rechnet den Haftungsrand mit. Zwei Körper
  können reichlich Luft haben und der Druck trotzdem scheitern: Brim und Skirt
  stehen über den Körper hinaus, und zwischen zwei Nachbarn zählt der Rand
  zweimal. Genau daran war die erste Deckelplatte zu eng.
- **`check_filament_changes`** nennt den Preis, statt ihn zu verbieten: die
  Zahl der Schichten, in denen beide Filamente vorkommen, und die Wechsel
  daraus. Beim Gewürzset 110 Schichten und 220 Wechsel — der Behälter ist
  68 mm hoch, der Deckel 22.

Die Spülmenge in Gramm bleibt draußen. Sie steht im Profil des Slicers, nicht
in Solidon, und eine Zahl zu erfinden, die wie eine Messung aussieht, wäre
schlechter als die Wechselzahl, die sich exakt ergibt.

## 6. Was nicht gebaut wird

- **Kein eigener Slicer** (§22) — auch keine Nachbildung seiner Profillogik.
  Gelesen wird, was da ist; erfunden wird nichts.
- **Kein Überschreiben des Herstellerprofils.** Solidon legt seine Werte
  darüber, wie es §29 vorsieht. Was es nicht anfasst, bleibt stehen.
- **Keine Kalibrierung im Hintergrund.** Flussrate und Toleranzen kommen aus
  §28.3, gemessen am gedruckten Teil, nicht geschätzt.

## 6a. Die Probe — das Gewürzset aus Solidon heraus

Gebaut wie ein Nutzer es täte: `new`, viermal `import`, `assign_slot` je Teil,
`arrange_bed`, dann Platten, Einstellungen und Export über den Kern.

**Was auf Anhieb stimmte.** Der Plattenvorschlag trennt nach Filament —
Behälter transluzent auf die eine, Deckelteile und Regal auf die andere. Die
Profile werden gefunden und zugeordnet (`Elegoo Centauri Carbon 2 0.4 nozzle`,
`0.20mm Standard @Elegoo CC2 0.4 nozzle`, `Elegoo PETG @ECC2`), das
Prozessprofil trägt Arachne und das Brückentempo, das Filamentprofil Temperatur
und Pressure Advance des Herstellers.

**Was Solidon besser wusste als die Handarbeit.** Von Hand hatte die
Streuscheibe den Brim bekommen — Intuition wegen der drei 1,1-mm-Federarme,
ohne zu messen. Solidon gibt ihn der Deckelbasis. Nachgemessen:

| Teil | Standfläche | Höhe |
|---|---|---|
| Deckelbasis | **282 mm²** | 22,0 mm |
| Streuscheibe | 516 mm² | 5,4 mm |
| Behälter | 1256 mm² | 67,6 mm |

Die Basis steht auf dem 2,75 mm breiten Gewindering und ist viermal so hoch wie
die Scheibe, die auf einem 9,8 mm breiten Ring liegt. Die Automatik hatte
recht, die Handentscheidung war eine Vermutung.

**Was die Probe an Solidon fand.**

1. *Das Regal steht über den Bauraum.* Sein STL liegt nicht zentriert; der
   Slicer ordnet still an, Solidon sagt es. Behoben mit `arrange_bed`.
2. *`nil` wurde als Abweichung gemeldet.* In einem Filamentprofil heißt es
   „dazu sage ich nichts" — der Wert bleibt beim Drucker. Vier solche Zeilen
   standen neben den echten Unterschieden; behoben, 17 Meldungen wurden 13.
3. *Die Anordnung kennt den Haftungsrand nicht.* `arrange_bed` legt 5 mm
   zwischen zwei Körper, bei 3 mm Skirt-Abstand braucht es 6.
   `check_adhesion_clearance` meldet es mit der Zahl — aber die Anordnung
   selbst kann es nicht wissen: sie ist eine Operation und Teil des Dokuments,
   die Haftung eine Druckeinstellung, die zum Slicer reist. Zusammenbringen
   kann das nur die Oberfläche; das steht in der Roadmap.

**Was verschieden blieb und bleiben soll.** Solidon wählt die
Grundausführung `Elegoo PETG @ECC2`, von Hand stand dort Translucent und PRO —
das ist die dokumentierte Vorgabe aus Stufe 2, und wer eine besondere Spule
hat, wählt sie. Und Solidons Materialtabelle weicht in dreizehn Werten vom
Herstellerprofil ab, darunter 240 gegen 250 °C an der Düse und 80 gegen 70 °C
am Bett. Genau dafür ist `profile_differences` da.

## 7. Abnahme

1. Ein Lauf gegen ElegooSlicer, bei dem `handover.verify` **keine** Abweichung
   meldet — heute meldete er achtzehn, wenn jemand hinsähe.
2. Ein Testfall, der die Profilart jedes Eintrags in `slicer_keys` gegen den
   Bestand eines installierten Slicers prüft und rot wird, sobald ein Wert im
   falschen Profil landet. Ohne installierten Slicer übersprungen, nicht grün.
3. Das Gewürzset als Referenz: aus Solidon heraus dieselben drei Platten mit
   denselben Werten, die jetzt von Hand entstanden sind.

Punkt 3 ist der eigentliche Maßstab. Was ein Mensch für ein Projekt von Hand
einstellen musste, ist die Liste dessen, was die Anwendung können soll.
