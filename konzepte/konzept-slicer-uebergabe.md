# Konzept — Druckeinstellungen automatisch setzen, bevor der Slicer sie bekommt

Stand 07.08.2026, nachrecherchiert am 19.08.2026.

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
| In die Sprache des Slicers | `export/slicer_keys.py` | 57 Zuordnungen für Orca, 58 für Prusa, 224 Werte für Cura (§8) |
| Profil schreiben, Slicer rufen | `export/handover.py` | Konsolenlauf, Zeitlimit, G-Code zurücklesen |
| Profile des Slicers finden | `export/slicer_profiles.py` | Maschine, Prozess und Filament, Erbkette der Verträglichkeit |
| Aus der Geometrie schließen | `slice/advise.py` | Stützen, Haftung, Linienbreite, Schichtzeit, Volumenstrom, Passungstempo |
| Gegenprobe | `handover.verify` | liest die Konfigurationskommentare der erzeugten Datei — bei Cura steht dort nichts, siehe §8 |
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

> **Die Spur ist beseitigt.** Mit `9c59e3a` (05.08.2026) fielen die drei
> Filamentwerte aus `_RECOMPUTED` heraus; heute stehen dort nur noch Werte,
> die der Slicer wirklich umformt — Farbe zur Liste, Düsendurchmesser,
> Bettform, erste Schichtgeschwindigkeit, Brim-Art, Wandreihenfolge, Stützart
> (`app/core/export/handover.py:1146–1156`).

Die Gegenprobe (`verify`) würde den Rest melden. Sie läuft nur, wenn jemand
einen echten Lauf macht; in der Suite gibt es keinen.

### 2.2 Das Filamentprofil fehlte ganz

> **Nachgetragen in Stufe 2 desselben Dokuments — und dieser Abschnitt
> widersprach §5 seit dem Tag, an dem es gebaut wurde.**
> `slicer_profiles.PROFILE_DIRS` kennt heute `machine`, `process` **und**
> `filament` (`app/core/export/slicer_profiles.py:45–49`); `DEFAULT_KINDS`
> (`:267`) lässt Filamente nur dann weg, wenn es ausdrücklich verlangt wird.
> `handover.py:831` übergibt `--load-filaments`, und `write_config`
> (`:415–428`) schreibt je Slot ein Filamentprofil. Auch die Tabelle in §1
> müsste dort „Maschine, Prozess und Filament" sagen.

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

> **Der Volumenstrom in Spalte 1 ist ein Zahlendreher, und zwar von Anfang
> an.** `print_settings.toml:144` führt für PETG `max_flow = 10.0` — 12,0 ist
> der Wert von PLA (`:126`). `git log -L 129,148` zeigt: 10.0 steht dort seit
> dem 01.08.2026 (`2989261`) und wurde nie geändert; die 12 war für PETG nie
> im Repository. Richtig heißt die Zeile: **10 · 10 · 5 mm³/s** — der
> Unterschied liegt allein beim PRO, und dort um das Doppelte. Derselbe
> Dreher steht im Docstring `handover.py:722–731`.

Das Bett liegt 10 °C daneben, der Volumenstrom beim PRO um mehr als das
Doppelte. Keine dieser Zahlen ist falsch geraten — sie sind für „PETG im
Allgemeinen" richtig und für *dieses Filament auf diesem Drucker* eben nicht.
Der Hersteller weiß es besser, und seine Angabe liegt auf der Platte.

## 3. Was im Modell fehlt

> **Diese Liste widerspricht Stufe 3 in §5, und Stufe 3 hat recht.** In
> `PrintSettings` stehen heute `wall_generator`, `precise_outer_wall` und
> `ironing` (`app/core/types.py:411–418`) sowie `bridge`, `acceleration` und
> `outer_wall_acceleration` (`app/core/knowledge/print_settings.py:206–208`).
> Offen aus der Liste sind nur noch **drei**: Pressure Advance,
> `brim_object_gap` und `bridge_flow`. Der Elefantenfuß und
> `xy_hole_compensation` stehen bewusst nicht darin — beide werden in der
> Geometrie eingezogen, siehe Stufe 3.

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

- **Elefantenfuß.** Dafür gibt es die Op `compensate_first_layer`, die über
  `compensate_elephant_foot` in der Geometrie arbeitet und laut deren
  Docstring „genau das tut, was die Elefantenfuß-Kompensation eines Slicers
  tut". Den Wert zusätzlich zu übergeben hieße, zweimal einzuziehen.
- **Lochkorrektur.** `MaterialProfile.hole_compensation` ist ein kalibrierter
  Wert — und die Geometrie wendet ihn längst an: `bore_diameter`
  (`app/core/geom/prepare.py:68`) rechnet ihn auf den Nenndurchmesser, benutzt
  von der Op `drill_hole` über den Parameter `compensate`
  (`prepare_ops.py:182`, `:191`, `:214`, eingeführt mit `4c888f6` am
  28.07.2026); eine Gewindepassung löst ihre Toleranz ebenfalls daraus auf
  (`profiles.py:211`). Test: `tests/test_prepare.py:47–56`. Ihn *zusätzlich*
  an den Slicer zu geben hieße also, zweimal einzuziehen — dieselbe
  Begründung wie beim Elefantenfuß.

  > **Hier stand, es gebe keine Op, die ihn anwendet.** Das war schon beim
  > Schreiben falsch: `drill_hole` tut es seit dem 28.07.2026. Die
  > Schlussfolgerung des Absatzes kehrt sich dadurch um — aus „erst
  > entscheiden, wer kompensiert" wird „die Entscheidung ist gefallen, und
  > zwar zugunsten der Geometrie".

  > **Der Op-Name war ebenfalls falsch.** Registriert ist
  > `compensate_first_layer` (`app/core/geom/prepare_ops.py:499`, Titel
  > „Elefantenfuß ausgleichen"); `compensate_elephant_foot` ist die Funktion
  > dahinter (`prepare.py:323`). Oben berichtigt.

Bügeln ist an/aus, ohne Feinwerte: **ob** gebügelt wird, ist die Entscheidung —
wie stark und mit welchem Abstand weiß der Slicer besser. Die Regel „Fläche,
auf der etwas gleiten soll" aus dem `Fit` abzuleiten steht noch aus; heute ist
es ein Schalter im Dialog.

> **Sie steht nicht mehr aus.** `advise._from_fits`
> (`app/core/slice/advise.py:524–545`) schlägt `shell.ironing` vor, wenn eine
> **bündige** Passung im Spiel ist, und begründet es — bei Schiebesitz,
> Presssitz oder Gewinde nicht. Gebaut am 07.08.2026 (`a28bd00`, 10:13), also
> gut dreizehn Stunden vor der letzten Änderung an diesem Dokument
> (`9c420bf`, 23:44). `ROADMAP.md:417–419`.

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

   > **Erledigt, und zwar dort, wo es hingehörte.** Der Dialog des Anordnens
   > öffnet mit dem doppelten Haftungsrand als Abstand:
   > `_spacing_for` rechnet `needed = 2.0 * adhesion_margin(settings)` und
   > gibt `max(default, needed)` (`app/ui/main_window.py:4958–4982`);
   > `ROADMAP.md:410–413` führt den Punkt als erledigt. Die **Operation**
   > kennt die Druckeinstellung weiterhin nicht und soll es nicht — die
   > Vorgabe 5,0 steht unverändert in `prepare.py:404`.

**Was verschieden blieb und bleiben soll.** Solidon wählt die
Grundausführung `Elegoo PETG @ECC2`, von Hand stand dort Translucent und PRO —
das ist die dokumentierte Vorgabe aus Stufe 2, und wer eine besondere Spule
hat, wählt sie. Und Solidons Materialtabelle weicht in dreizehn Werten vom
Herstellerprofil ab, darunter 240 gegen 250 °C an der Düse und 80 gegen 70 °C
am Bett. Genau dafür ist `profile_differences` da.

> **Heute sind es zwölf** (nachgemessen am 19.08.2026 gegen den installierten
> ElegooSlicer, Profil `Elegoo PETG @ECC2`). Die genannten Beispiele stimmen
> weiter — 240 gegen 250 °C an der Düse, 80 gegen 70 °C am Bett, dazu
> `filament_max_volumetric_speed` 10 gegen 11. Die Zahl hängt am
> Profilbestand des jeweiligen Rechners; wer sie zitiert, nennt Datum und
> Profilnamen dazu.

## 7. Abnahme

> **Punkt 1 und 2 sind erfüllt.** Am 07.08.2026 gegen den installierten
> ElegooSlicer gemessen, vier Teile des Gewürzsets, **null Abweichungen**
> (`ROADMAP.md:3227–3240`). Der Testfall aus Punkt 2 heißt
> `test_every_orca_setting_sits_in_the_profile_it_claims`
> (`tests/test_print_settings.py:903`) und ist grün — nicht übersprungen, der
> Slicer ist installiert. Punkt 1 stand damit im Widerspruch zur eigenen
> Stufe 1, die sich schon als „umgesetzt" führt.

1. Ein Lauf gegen ElegooSlicer, bei dem `handover.verify` **keine** Abweichung
   meldet — heute meldete er achtzehn, wenn jemand hinsähe.
2. Ein Testfall, der die Profilart jedes Eintrags in `slicer_keys` gegen den
   Bestand eines installierten Slicers prüft und rot wird, sobald ein Wert im
   falschen Profil landet. Ohne installierten Slicer übersprungen, nicht grün.
3. Das Gewürzset als Referenz: aus Solidon heraus dieselben drei Platten mit
   denselben Werten, die jetzt von Hand entstanden sind.

Punkt 3 ist der eigentliche Maßstab. Was ein Mensch für ein Projekt von Hand
einstellen musste, ist die Liste dessen, was die Anwendung können soll.

---

## Nachrecherchiert am 19.08.2026

Fünfzehn Aussagen über den eigenen Code geprüft: **vier stimmen, acht sind
überholt, zwei waren falsch, eine ist nicht prüfbar.** Dazu drei Stellen, an
denen das Dokument sich selbst widerspricht — jedes Mal, weil §5 („was daraus
wurde") einen Stand meldet, den §1 bis §3 noch nicht kennen.

**Die beiden Fehler von Anfang an:**

- **`hole_compensation` wird längst angewandt.** Der Absatz sagte, es gebe
  keine Op dafür, und leitete daraus ab, die Frage „wer kompensiert" sei noch
  offen. Tatsächlich rechnet `bore_diameter` den Wert seit dem 28.07.2026 auf
  jede Bohrung von `drill_hole`, und eine Gewindepassung löst ihre Toleranz
  daraus auf. Die Entscheidung ist also gefallen — zugunsten der Geometrie,
  genau wie beim Elefantenfuß.
- **12 mm³/s für PETG hat es nie gegeben.** Der Wert ist 10; 12 ist PLA. Die
  Zahl steht seit dem 01.08.2026 unverändert im Repository, der Dreher auch im
  Docstring von `handover.py`.

Dazu ein falscher Op-Name: registriert ist `compensate_first_layer`, nicht
`compensate_elephant_foot` — das ist die Funktion dahinter.

**Was gebaut wurde, während das Dokument entstand:** Die Regel „Fläche, auf
der etwas gleiten soll" leitet `advise._from_fits` seit dem 07.08.2026, 10:13
Uhr aus dem Fit ab — gut dreizehn Stunden vor der letzten Änderung an diesem
Text. Der Haftungsrand steht im Dialog des Anordnens (nicht in der Operation,
und das ist richtig so). Das Filamentprofil wird geschrieben und geladen.
`_RECOMPUTED` führt die drei Filamentwerte nicht mehr.

**Die Abnahme ist erfüllt, Punkt 1 und 2.** Am 07.08.2026 gegen den
installierten ElegooSlicer gemessen: vier Teile, **null Abweichungen**. Der
Testfall heißt `test_every_orca_setting_sits_in_the_profile_it_claims` und ist
grün. Punkt 1 stand im Widerspruch zur eigenen Stufe 1, die sich längst als
umgesetzt führt.

**Was noch offen ist**, aus der Liste in §3: Pressure Advance,
`brim_object_gap` und `bridge_flow`. Die übrigen sechs Werte sind in
`PrintSettings` angekommen.

**Zahlen, die mitgewachsen sind:** 50 Zuordnungen für Orca sind heute 57 (37
Prozess, 20 Filament), dazu 54 für Prusa und 47 für Cura. Die dreizehn
Abweichungen zum Herstellerprofil sind zwölf — eine Zahl, die am Profilbestand
des jeweiligen Rechners hängt und deshalb nur mit Datum zitiert werden sollte.

**Nicht prüfbar und deshalb unverändert stehen geblieben:** die Messwerte des
Gewürzsets (Deckelbasis 282 mm², Streuscheibe 516 mm², Behälter 1256 mm², die
110 gemeinsamen Schichten und 220 Wechsel). Der Ordner `3D Drucker` liegt
nicht im Repository und nicht auf dieser Maschine; zwei der Zahlen sind über
`ROADMAP.md:392–401` gedeckt, die übrigen nicht.

**Zur Außenwelt** hat die Recherche vom 19.08.2026 nichts gefunden, was die
Grundannahmen dieses Dokuments umstößt: Die Orca-Familie verteilt ihre
Einstellungen weiterhin auf Maschine, Prozess und Filament, und der
ElegooSlicer bleibt ein OrcaSlicer-Abkömmling.
## 8. Nachtrag vom 20.08.2026 — was die Durchsicht gegen die echten Slicer ergab

Alle drei Familien wurden gegen die installierten Programme durchgemessen:
PrusaSlicer 2.9.6, ElegooSlicer 1.5.3.4, CuraEngine 5.13.0. Der ganze Befund
steht in `ROADMAP.md`; hier steht nur, was am **Konzept** nachzuziehen ist.

### Die Bestandstabelle in §1 stimmt so nicht mehr

Zwei Zeilen sind überholt:

- **„50 Zuordnungen für Orca, dazu Prusa und Cura"** — es sind 57 für Orca,
  58 für Prusa und 224 für Cura. Die Zahl bei Cura ist kein Fleiß, sondern
  eine Eigenheit der Rechenmaschine, siehe unten.
- **„Gegenprobe: liest die Konfigurationskommentare der erzeugten Datei"** —
  das trägt weit, aber nicht überall gleich weit. Gemessen: PrusaSlicer nennt
  53 von 53 geschriebenen Schlüsseln in der Druckdatei, ElegooSlicer 56 von
  56, **CuraEngine null von 47**. Es schreibt seine Einstellungen dort nicht.
  Der Mechanismus, der die Zuordnung selbst prüft, war genau dort blind, wo
  die meisten Fehler saßen. Für Cura leistet das jetzt `unknown_keys()` gegen
  `fdmprinter.def.json` der installierten Version.

### Die Grenze in §6 braucht einen Satz mehr

„Kein eigener Slicer — auch keine Nachbildung seiner Profillogik" bleibt
richtig, aber der Wortlaut deckt einen Fall nicht ab, den die Durchsicht
erzwungen hat.

`CuraEngine` ist nicht die Kommandozeile eines Slicers, sondern die
Rechenmaschine hinter dem Fenster. In `fdmprinter.def.json` trägt jede
abgeleitete Einstellung zweierlei: einen `value`-Ausdruck und einen
`default_value`. **Das Fenster wertet den Ausdruck aus, die Rechenmaschine
nimmt den Vorgabewert.** Ein geschriebener Wert bleibt damit an seinem
Schlüssel stehen: die Bahnbreite erreicht die zwölf Bahnbreiten nicht, die
Füllung ihren Linienabstand nicht. Gemessen an einem 20-mm-Würfel kostete das
**1100 mm Filament statt 818** — ein Drittel zu viel, weil die Füllung mit
2 mm Linienabstand rechnete statt mit 5,6.

Wer diese Rechnung nicht nachzieht, kann die Einstellung genauso gut
weglassen. Also wird sie nachgezogen, und die Grenze verläuft eine Stelle
weiter innen, als der Satz sie zog:

> **Nachgerechnet wird, was in der Definition des Slicers steht. Ausgedacht
> wird nichts.** Jede Zeile in `CURA_MIRRORED`, `CURA_SCALED` und
> `_cura_computed` ist die Formel aus `fdmprinter.def.json` — nicht eine
> Meinung darüber, was besser wäre. Was absichtlich wegbleibt, steht mit
> Begründung in `CURA_UNTOUCHED`, und ein Test lässt keine dritte
> Möglichkeit zu.

Der naheliegendere Weg — die Ausdrücke zur Laufzeit auswerten — ist
ausgeschlossen: das wäre `eval` auf fremdem Text (Regel 10). Eine Tabelle ist
Daten, prüfbar gegen die Definition, und genau das prüft
`test_nothing_cura_derives_is_left_to_its_default`.

Für PrusaSlicer und die Orca-Familie bleibt es beim alten Satz: beide lösen
ihre Erbketten selbst auf, und Solidon legt nur seine Werte darüber.

### Die Abnahme aus §7 ist erfüllt, Punkt 1 und 2

Punkt 1: Ein Lauf gegen ElegooSlicer, bei dem `verify` keine Abweichung
meldet — erreicht, und ebenso gegen PrusaSlicer. Punkt 2: Der Testfall gegen
den Profilbestand steht als `test_every_orca_setting_sits_in_the_profile_it_claims`,
und daneben stehen jetzt zwei für Cura. Punkt 3, das Gewürzset als Referenz,
bleibt offen.

### Was dazukam und im Konzept fehlte

**Winkel zählen nicht überall gleich.** Solidon misst den Stützwinkel gegen
die Senkrechte, PrusaSlicer und die Orca-Familie gegen die Horizontale. Ein
Zahlenwert, an alle drei geschickt, hieß an den Rändern das Gegenteil. Das ist
keine Umsetzungsfrage, sondern eine Eigenschaft der Zielprogramme, mit der
jede weitere Zuordnung rechnen muss.

**Die exportierte Datei trägt ihre Einstellungen für beide Familien.** Stufe 5
hatte das für die Orca-Familie gebaut; PrusaSlicer liest dasselbe aus
`Metadata/Slic3r_PE.config`, und dort stand nichts. Für Cura bleibt es beim
STL und der Kommandozeile — seine 3MF-Seite sitzt im Fenster, nicht in der
Rechenmaschine.

## 9. RM-465 — Material- und Zeitgegenprobe vom 03.10.2026

Diese Messung begründet den Stand des offenen Punkts in `ROADMAP.md`.
Die Materialkorrektur ist umgesetzt; die drei Zeitansätze sind diagnostische
Rechnungen und wurden nicht als Zeitkorrektur ins Produkt übernommen.
Die Akzeptanzgrenze bleibt 15 %. Der bisherige Zeitvergleich warnt weiterhin
bei sieben von acht einfarbigen Standardfällen.

### Modelle und Messweg

- Würfel: `tests/data/meshes/cube_clean.stl`, 20 mm Kantenlänge,
  8000 mm³ Volumen und 2400 mm² Oberfläche, SHA256
  `1fafb705288b1c45ea766ac863a57f12a1da338c46d9c54f43f9a944876d9d28`.
- Pilz: Roberts separat vorhandene `mushroom.stl`, SHA256
  `55e189bf2f516cdfbeedb2bd787db34dae7268025d1f2cd56405725bb4b23f45`.
  Die Originaldatei wurde nur gelesen und ist nicht Teil des Repositorys.
  Für eine exakte Wiederholung dieser Referenz ist dieselbe Datei erforderlich.
- Je Körper ein echter einfarbiger PLA-Lauf mit dem Standardprozess der
  genannten Maschine: Creality/K1, Elegoo/Centauri Carbon 2,
  PrusaSlicer/MK4S und SuperSlicer/MINI. Die Tabellen sind Momentaufnahmen
  der lokal installierten Slicer; neue Versionen und Profile gesondert ausweisen.
- Die interne Schätzung erhält Geometrie und aufgelöste Druckeinstellungen.
  Der Vergleichswert kommt aus der anschließend erzeugten Druckdatei.
  Kein gemessener Gesamtzeitwert fließt in die interne Schätzung ein.
- Abweichung der Zeit: `(Schätzung − G-Code-Gesamtzeit) / G-Code-Gesamtzeit`.
  Materialabweichung: absoluter Unterschied geteilt durch G-Code-Modellmasse.

### Umgesetzte Materialtrennung

Der Parser zählt bekannte Modellrollen, Stützen, Haftung, Spülung und
unbekannte Rollen getrennt je Werkzeug. Nur vollständig zuordenbares
Modellmaterial mit belegter Dichte dient dem Modellvergleich. Bedingte
Firmwarezweige, Cutter-Wiederförderung und fehlende Materialdaten bleiben
ausdrücklich unvollständig. Der bisherige Gesamtverbrauch und die Buchung
des Filamentverbrauchs ändern sich nicht.

| Slicer / Maschine | Körper | Schätzung Modell g | Druckdatei Modell g | Druckdatei gesamt g | Abweichung |
|---|---|---:|---:|---:|---:|
| Creality / K1 | Pilz | 5,5642 | 5,6404 | 5,6400 | 1,35 % |
| Creality / K1 | Würfel | 3,4394 | 3,4835 | 3,4800 | 1,27 % |
| Elegoo / CC2 | Pilz | 5,6090 | 5,7618 | 6,2900 | 2,65 % |
| Elegoo / CC2 | Würfel | 3,4671 | 3,4767 | 4,0100 | 0,28 % |
| Prusa / MK4S | Pilz | 5,7891 | 5,9916 | 6,0500 | 3,38 % |
| Prusa / MK4S | Würfel | 3,5659 | 3,7220 | 3,7800 | 4,19 % |
| SuperSlicer / MINI | Pilz | 5,7891 | 6,4186 | 6,4500 | 9,81 % |
| SuperSlicer / MINI | Würfel | 3,5659 | 3,6972 | 3,7500 | 3,55 % |

Sechs bereits vorhandene lesbare Farbdateien bestätigen die Trennung:
Bambu 8,57 %, Creality 5,94 %, Elegoo 9,56 %, Orca 9,90 %, Prusa 0,49 %
und SuperSlicer 2,86 % Modellmassenabweichung. Beispielsweise stehen bei
Bambu 6,9742 g Modellmaterial 48,02 g Gesamtverbrauch gegenüber; die
internen 6,3765 g werden ausschließlich mit dem Modell verglichen.
Bei Cura ohne belegten Filamentdurchmesser beziehungsweise Dichte bleibt
die Modellmasse unbekannt. Aus lesbaren Spülbewegungen allein wird keine
vollständige Spülmenge behauptet.

Die integrierte Gegenprobe über alle acht frischen Standarddateien und neun
vorhandene reale Farb-/Stützdateien bestätigt unveränderte Gesamtmassen,
Werkzeugbuchung, Stützmengen, Gesamt-Schichtzahlen und gemeldete Zeiten.
Die Parser- und Anschlussregressionen liegen in `tests/test_gcode.py`,
`tests/test_print_settings_ui.py` und `tests/test_ui.py`. Sie prüfen auch,
dass ein späterer vollständiger Vergleich einen früheren Unbekannt-Befund
im echten Berichtspfad ersetzt.

### Ergebnis

Die Mindestschichtzeit ist **keine garantierte Untergrenze** der tatsächlichen Schichtzeit. Ein Slicer bremst nur bis zum Mindestdrucktempo. Das ist am SuperSlicer-Pilz direkt belegt und erklärt den größten Fehler des schichtweisen Prototyps. Die Beschleunigungs- und Startanteile bleiben eine eigene Frage. Ein allgemeines, belegtes Zeitmodell innerhalb 15 % für alle acht Fälle wurde mit dieser Sonde nicht erreicht.

### Schätzung aus Geometrie und Einstellungen

Die diagnostische Rechnung verwendet die Flächenaufteilung des ersten Prototyps: Außenwand, innere Wände, volle Deck-/Bodenflächen und Füllung je Schicht. Der vorhandene angenommene Fahrweganteil von 25 % bleibt unverändert. Hinzu kommt eine obere Grenze der durch Bremsen erreichbaren Zeit:

`max(geschätzte Schichtzeit, min(Mindestschichtzeit, geschätzte Bahnlänge / Mindestdrucktempo / 0,75))`.

Die Mindesttempi wurden für diese diagnostische Sonde aus den Konfigurationskommentaren gelesen: `min_print_speed` = 15 mm/s bei SuperSlicer, 20 bei PrusaSlicer; `slow_down_min_speed` = 20 bei Elegoo und Creality. **Für produktive interne Schätzung müssen diese Werte aus dem gewählten Herstellerprofil kommen.** Der gemessene Zeitwert geht in keine Schätzung ein. `CoolingSettings` führt diesen Grenzwert derzeit nicht.

| Slicer / Maschine | Körper | Erster Prototyp s | Mit Tempogrenze s | G-Code gesamt s | Abweichung der neuen Schätzung |
|---|---|---:|---:|---:|---:|
| Creality / K1 | Pilz | 1132,7 | 990,5 | 1150,9 | −13,94 % |
| Creality / K1 | Würfel | 809,8 | 809,8 | 883,7 | −8,37 % |
| Elegoo / CC2 | Pilz | 700,7 | 700,7 | 979,0 | −28,43 % |
| Elegoo / CC2 | Würfel | 423,5 | 423,5 | 637,0 | −33,51 % |
| Prusa / MK4S | Pilz | 1054,6 | 1054,6 | 1082,0 | −2,53 % |
| Prusa / MK4S | Würfel | 637,8 | 637,8 | 755,0 | −15,52 % |
| SuperSlicer / MINI | Pilz | 3931,0 | 3094,3 | 2702,0 | +14,52 % |
| SuperSlicer / MINI | Würfel | 2229,5 | 2229,5 | 2275,0 | −2,00 % |

Analytischer Bezug des Pilzstiels im SuperSlicer-Raster: Querschnitt 10 × 10 = 100 mm², 0,15-mm-Schicht; abgeschätztes Material 6,4269 mm³. Bei 0,45-mm-Bahnbreite ergibt das 95,2133 mm Bahnlänge. 15 mm/s erlauben 6,3476 s Materialauftrag, mit dem vorhandenen Fahrweganteil 8,4634 s. Ein hartes Maximum mit 15 s verlangt damit eine Abbremsung unter das zulässige Tempo. Beispielschicht 80 liegt bei z = 12,125 mm.

### Unabhängige Lesung der vorhandenen Bahnen

Die unabhängige Bahnauswertung liest die vorhandenen G0/G1-Bahnen und summiert Weg / Solltempo. E-only-Bewegungen werden ebenfalls gezählt. Das ist **eine Messung des G-Codes**, keine interne Vorhersage. Beschleunigung, Aufheizen und Maschinenmakros fehlen. G2/G3 werden gezählt, aber nicht zeitlich aufgelöst; daher nur die CC2-Werte (ein einzelner Endcodebogen) und die SuperSlicer-Werte (keine Bögen) als vergleichbare Belege verwenden. Die anderen vier Läufe werden wegen nicht zeitlich aufgelöster Bögen hier nicht für diesen Vergleich herangezogen.

| Fall | Nominale Modellbahnzeit s | Gemeldete Gesamtzeit s | Mittlere Schicht Weg/F s |
|---|---:|---:|---:|
| CC2 Würfel | 427,4 | 637 | 4,09 |
| CC2 Pilz | 731,8 | 979 | 4,02 |
| SuperSlicer Würfel | 2097,4 | 2275 | 15,01 |
| SuperSlicer Pilz | 2314,3 | 2702 | 7,03 |

Der CC2-Prototyp trifft damit die nominale Modellbahnzeit bereits recht gut. Die fehlende Zeit steckt wesentlich außerhalb dieser Größe. Vor der ersten Modellschicht stehen im CC2-Würfel M73 P17 R8 und bei Gesamt637 s ungefähr110 s Startanteil; diese Quantisierung beweist keine exakte Startdauer. Auch nach dessen Abzug bleiben etwa100 s (Würfel) beziehungsweise137 s (Pilz) gegenüber Weg/F. Eine pauschale Erhöhung der Extrusionsmenge würde die bereits passende Materialbilanz verschlechtern.

Der CC2-G-Code enthält je Schicht mehrere Rückzüge, automatische spiralförmige Z-Anhebung, Z-Absenken, wechselnde Beschleunigungen und bei den inneren Bahnen weitere Richtungswechsel. Ihre Dauer ist aus einem Volumenstrom oder der Schichtzahl allein nicht bestimmbar. Ohne eine belegte zusätzliche Bewegungsannahme oder eine unabhängig gelernte Maschinenzeit ist ein erfundener fester Aufschlag kein sauberer Abschluss von RM-465.

### Weitere Grenze der verfügbaren Einstellungen

`manufacturer._first_layer_speed` und `_prusa_first_layer_speed` führen absichtlich das schnellere von Wand- und Fülltempo in Solidons einem Feld. CC2: Wände50/Füllung105, Feld105 mm/s. MK4S: Wände40/Füllung100, Feld100 mm/s. Für einen Dialogwert ist diese Entscheidung dokumentiert; als einheitliches Erstschichttempo unterschätzt sie die Wände. Ebenso kennt die schnelle Schätzung keine getrennten Brücken-/Innenbrückenschichten: Der Pilz enthält diese im G-Code sichtbar.

### Empfehlung für die Umsetzung

1. Mindestdrucktempo aus derselben aufgelösten Herstellerprofilkette wie die Mindestschichtzeit übernehmen. Ohne belegten Wert keine garantierte Mindestdauer behaupten.
2. Startzeit ausschließlich aus einem unabhängig belegten Startabschnitt einer früheren Druckdatei lernen; sie mit Herkunft und passender Maschinen-/Profilidentität getrennt halten.
3. Die Schnittauswertung von der Mikrosekunden-Schätzung aus Volumen/Oberfläche getrennt halten. Die Aufteilung von Wänden/Decklagen ist nur im bereits geschnittenen Druckweg bezahlbar.
4. Die verbleibende CC2-Lücke offen dokumentieren, solange Beschleunigungs- und Auto-Lift-Anteile keinen tragfähigen unabhängigen Ansatz haben. Keine Modell-/Slicerfaktoren und keine Änderung der 15-%-Schwelle.

### Letzter Ansatz: Beschleunigung an den bekannten Wandkonturen

Zusätzlich wurde jede aus dem Schnitt bekannte Wandmittellinie gebildet; gerade Fortsetzungen wurden vereinfacht. Es entstehen keine Füllbahnen und kein G-Code. Für jedes gerade Segment der Länge `L`, Tempo `v`, Beschleunigung `a` ist die maximale Bewegungszeit bei vollständigem Halt an beiden Enden:

- `L/v + v/a`, falls `L >= v²/a` (Trapezprofil),
- `2 sqrt(L/a)`, sonst (Dreiecksprofil).

Die Differenz zu `L/v` ist eine **Obergrenze des Verlusts an diesem Segment** im vereinfachten konstanten Beschleunigungsmodell. Die untere Grenze beträgt null; Eckgeschwindigkeit, Ruckbegrenzung und Abweichungstoleranz kennt `PrintSettings` nicht. Für scharfe Winkel wird in der Praxis gebremst, aber der tatsächlich erlaubte Eckdurchlauf lässt sich ohne diese Angaben nicht bestimmen. Erste Schichten wurden bei dieser Schranke ausgelassen, weil ihre Beschleunigung abweicht.

CC2-Profil: außen5000, innen10000 mm/s², außen160/innen200 mm/s vor Kühlung. Zwei Auswertungen: Profiltempo ergibt eine grobe obere Grenze; das um den zuvor berechneten Kühlfaktor verminderte Tempo ergibt eine engere, ihrerseits von der Kühlannahme abhängige Grenze.

| CC2 | Wandverlust obere Grenze mit Profiltempo | Mit geschätztem gekühltem Tempo | Zeit inkl.110s Start und gekühlter oberer Grenze | Abweichung |
|---|---:|---:|---:|---:|
| Würfel | 20,592s | 10,792s | 544,309s | −14,55 % |
| Pilz | 25,792s | 8,989s | 819,654s | −16,28 % |

Nähme man die gröbere ungekühlte Obergrenze als festen Zuschlag, ergäben sich554,109s (−13,01 %) und836,457s (−14,56 %). Dass damit die Abnahme gerade grün wäre, begründet diese Wahl **nicht**: Die G-Code-Bahnen laufen sichtbar gekühlt. Der Ansatz an den vorhandenen Konturen reicht als belastbarer Punktwert nicht. Bei SuperSlicer-Pilz beträgt die gekühlte Wandobergrenze25,996s; ihr schlichtes Addieren verschiebt den bisher knapp grünen Vergleich wieder über15 %.

Zusätzlich steckt Beschleunigung bereits im angenommenen25-%-Fahrweganteil. Ein separater Zuschlag kann ihn doppelt zählen. Die Wandrechnung ist deshalb nur als Fehlerschranke/Diagnose verwendbar, nicht ungeprüft als additiver Produktivfix.

**Ohne neue Profilfelder implementierbar:** geometrische Wand-Beschleunigungsintervalle aus `speed.acceleration`/`outer_wall_acceleration`; schon vorhandener Rückzugsweg und -tempo als Teilkosten, wenn die Rückzugsanzahl unabhängig bekannt ist. **Nicht aus den vorhandenen Feldern bestimmbar:** tatsächliche Eckgeschwindigkeit, Füllweg-Anzahl und Wendepunkte, Mindestdrucktempo, getrenntes Erstschichttempo, Z-Achsen-Tempo/-Beschleunigung und Auto-Lift-Bahn. Eine exakte Restzeit würde eine Bewegungsplanung erfordern; ein solcher eigener Slicer gehört ausdrücklich nicht in Solidon.

### Umsetzung vom 04.10.2026: Zeit aus der Schichtanalyse

Die Empfehlung oben ist umgesetzt, ohne Modell- oder Slicerfaktor und ohne
Änderung der 15-%-Schwelle:

1. **Mindestdrucktempo und getrennte Erstschichttempi** kommen aus derselben
   aufgelösten Herstellerkette wie die Mindestschichtzeit
   (`manufacturer.orca_motion`, `prusa_motion`, `cura_motion`;
   `Foundation.motion`). Dazu Beschleunigung je Bahnart, Maschinengrenzen,
   Junction-Deviation (Orca) bzw. Ruck (PrusaSlicer rechnet laut
   `GCodeProcessor.cpp` nur mit dem Ruck je Achse), Z- und Rückzugstempo.
   Ohne belegtes Mindestdrucktempo gibt es keine `Motion` und keine Zeit.
2. **Startanteil** ist eine Angabe des Slicers selbst: Fortschritt `M73 P`
   vor der ersten Schicht mal Gesamtzeit (`GcodeMetrics.start_seconds`, auf
   ein Prozent genau); verglichen wird ab der ersten Schicht
   (`printing_seconds`). Er wird aus der Datei gelesen, die verglichen wird,
   ist also immer an Drucker und Profil dieses Laufs gebunden.
3. **Die Schnittauswertung** steht getrennt von der Mikrosekunden-Schätzung
   in `slice/print_time.py` und rechnet aus den Schichten, die die
   Plattengegenprobe ohnehin schneidet: Wände als versetzte Kontur mit
   Ecktempo, Deck/Boden an den ganzen Nachbarschichten, Brücke und innere
   Brücke, Bahnzahl über die mittlere Sehne, Abbremsen über Weg/Tempo bis zum
   Mindesttempo und danach Beschleunigung, Leerfahrt, Rückzug und Z-Hub.

Dieselben acht Standardläufe, frisch geslicet am 04.10.2026 (Elegoo/CC2,
Creality/K1, Prusa/MK4S, SuperSlicer/MINI; Würfel `cube_clean.stl`, Pilz
`mushroom.stl` wie oben), am Produktweg (Grundlage → `plate_comparison` →
`gcode.compare`):

| Fall | vorher: Volumen/Fläche gegen Gesamtzeit | Schichtanalyse s | ab erster Schicht s | Abweichung |
|---|---:|---:|---:|---:|
| Creality / K1 Pilz | −75,6 % | 1056,5 | 1150,9 | −8,2 % |
| Creality / K1 Würfel | −80,6 % | 875,9 | 883,7 | −0,9 % |
| Elegoo / CC2 Pilz | −60,5 % | 818,3 | 871,3 (Start 107,7) | −6,1 % |
| Elegoo / CC2 Würfel | −62,9 % | 492,4 | 528,7 (Start 108,3) | −6,9 % |
| Prusa / MK4S Pilz | −72,2 % | 999,0 | 1082,0 | −7,7 % |
| Prusa / MK4S Würfel | −75,7 % | 712,1 | 747,5 (Start 7,5) | −4,7 % |
| SuperSlicer / MINI Pilz | −13,5 % | 2403,6 | 2702,0 | −11,0 % |
| SuperSlicer / MINI Würfel | −41,3 % | 2202,7 | 2252,2 (Start 22,8) | −2,2 % |

Kein `gcode.deviation` mehr (vorher sieben von acht). Außerhalb der Abnahme
nachgemessen und als Grenze festgehalten: die Okarina (hohle Doppelschale)
liegt bei PrusaSlicer +8,5 %, bei ElegooSlicer −21,1 % und bei CuraEngine
−23,3 %, der Cura-Würfel bei −13,8 %. Die Lücke der Okarina steckt in der
Zahl der Zugbeginne: ElegooSlicer fährt an ihren schrägen Schalen je Schicht
bis zu 58 Rückzüge mit Z-Hub, die Bahnzahl über die mittlere Sehne kennt
diese Stückelung nicht. Eine solche Datei meldet weiter eine Abweichung — als
Hinweis, dass die Schätzung diese Form nicht trägt, nicht als Fehler der
Übergabe. Die Rechnung kostet an der Okarina (309 Schichten) rund 2,7 s unter
Fremdlast im Arbeiter des Druckdialogs, an Würfel und Pilz 0,1 bis 0,2 s.
