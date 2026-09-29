# Review: Paket „Gesamtprüfung und RM-281“ (Zweig `uebergabe-gesamtpruefung`, Stand `3018613e6`)

Stand: 28.09.2026, nur lesend. Geprüft wird
`git diff 9f19b44d6...dd95985e5` (43 Dateien, +3267/−510, 17 Commits und
der Merge von `main`) und auf Wunsch der Koordination der letzte Commit
`3018613e6` („Solidon schlägt keine längere Mindestzeit je Schicht vor, wo
das Profil eine trägt“, `git diff dd95985e5 3018613e6`, 5 Dateien). Das
Urteil gilt für `3018613e6`. Gelesen am Commit selbst (`git show` und eine
Arbeitskopie per `git archive` im Scratchpad), nicht am Arbeitsbaum
`F:\3D Druck.gesamtfix`. Zeilennummern gelten für `3018613e6`.

Maßstab: `AGENTS.md` (22 Regeln), `.claude/rules/dateiformat.md`,
`schichtanalyse.md`, `oberflaeche.md`, `fenster.md`, `wartezeit.md`,
`tests.md`, `zwillinge.md`, die Karten der berührten Verzeichnisse und
`konzepte/konzept-herstellerprofil-als-grundlage-2026-09.md`
(Entscheidungen A–L, besonders G und K).

Drei Stufen: **blockiert den Merge**, **vor dem Tag** (nach dem Merge,
aber vor dem Tag 0.5.1 zu beheben), **Register nach 0.5.1** (Rest).

> **Stand `211789878` (zweiter Nachtrag am Ende):** N1, N2, N5 und B5 sind
> behoben. Offen und blockierend bleibt N6: Der Dateiexport aus dem
> Hauptfenster schreibt die gewählten Körper ohne `job`, und ein übernommener
> Vorschlag für den Pilz landet dort an jedem gewählten Teil — N1 auf dem
> zweiten Weg. **Mergebar nein**, bis N6 behoben ist (eine Zeile).
>
> **Stand `bc7e3e2da` (erster Nachtrag):** B1–B4 behoben, N1 blockierte.
> Das Urteil darunter gilt dem früheren Stand `3018613e6`.

## Urteil

**Mergebar: ja.** Kein Befund blockiert den Merge — keiner schreibt in
Projektdateien oder zerstört Daten, und `main` wird durch den Merge nicht
schlechter, als es vor Stufe E war. **Vor dem Tag** müssen fünf Punkte
behoben bzw. nachgewiesen sein (B1–B5); acht gehen ins Register (B6–B13).

## Übersicht

| Nr. | Stufe | Kurz | Ort |
|---|---|---|---|
| — | blockiert den Merge | keiner | — |
| B1 | vor dem Tag | Rat je Teil schreibt die ganze Einstellungsgruppe ans Objekt; gemessen: Füllung innen am Passungsteil schneller als Bambus Profil | `handover.py:763-772`, `writer.py:1250` |
| B2 | vor dem Tag | übernommener Vorschlag über eigener Wahl verschwindet still | `handover.py:882-897`, `print_settings.py:569-574` |
| B3 | vor dem Tag | Prusa-Drucker: nie ein Brim-Vorschlag, auch nicht je Teil | `advise.py:653`, `manufacturer.py:1095-1110` |
| B4 | vor dem Tag | Prüfbericht nennt weder Teil noch Einstellung, Tooltip mit Punktpfad und `True` | `writer.py:1327-1368` |
| B5 | vor dem Tag | Curas Fenster (3MF statt STL) nie im Fenster geöffnet | `writer.py:1630-1640`, RM-257 |
| B6 | Register | Dialog zeigt nach dem Übernehmen Werte je Teil als Plattenwert | `print_settings_dialog.py:5931-5966` |
| B7 | Register | `plate_paths`/`for_part` fragen Volumenstromdeckel, die der Dialog für Orca/Prusa verwirft | `advise.py:1377-1386` |
| B8 | Register | `fit_kinds_for` zählt ausgeschaltete Passungsschritte | `fits.py:312-348` |
| B9 | Register | doppelter Schnitt je Körper, `result` nie übergeben, Dateiexport ohne Abbruch | `writer.py:1387-1420`, `1668`, `1869` |
| B10 | Register | *Fertig* blockiert den Oberflächen-Thread bis 10 s | `first_run.py:754-773` |
| B11 | Register | Bindung der gemerkten Maschine an zwei Stellen hergeleitet | `print_settings_dialog.py:4256-4262`, `1125-1138` |
| B12 | Register | `SCARF_MIN_LOOP` als abgeschriebene Ableitung | `advise.py:210` |
| B13 | Register | Test und Docstring für `flavour=None`, den kein Aufrufer übergibt | `test_print_settings.py`, `print_settings_dialog.py:6441` |

## Blockiert den Merge

Keiner.

## Vor dem Tag

### B1 — Ein Rat je Teil schreibt die ganze Einstellungsgruppe als Objektwert, auch schneller als das Herstellerprofil

`app/core/export/handover.py:763-772` (`object_keys`), gerufen seit diesem
Paket aus `app/core/export/writer.py:1250` (`_part_values`, Orca-Familie und
PrusaSlicer) für jeden Pfad aus `advise.PART_PATHS`. Cura ist nicht
betroffen: Dort filtert `writer.py:1276-1279` auf `CURA_PER_MESH`, und die
Platte trägt ohnehin Solidons vollen Satz.

```python
groups = {entry.path.partition(".")[0] for entry in advice}
keys = {entry.key for entry in slicer_keys.TABLES[flavour] if entry.path.partition(".")[0] in groups}
...
written = {key: value for key, value in changed.items() if key in keys or before.get(key) != value}
```

Die Gruppenlogik war für die Haftung gebaut („wer Brim wählt, braucht die
Breite“). Seit Stufe E laufen auch `speed.*`, `shell.*`, `support.*`,
`infill.*` und `layers.*` hindurch, und dann schreibt **ein** Rat die ganze
Gruppe mit den Werten der Platte an das Objekt.

Was in der Datei steht (Sonde `bambu_fit_part.py`, installiertes Bambu
Studio, P1S, *Bambu PLA Basic*, Passungsrat übernommen → `split_for_parts`
→ `for_part` → `object_keys`, wie `_part_values` es tut): Das Teil mit
Passung bekommt 21 Objektwerte statt der vier übernommenen Pfade, darunter
`internal_solid_infill_speed: 270` (Bambu: 250), `gap_infill_speed: 300`
(Bambu: 250), `initial_layer_speed: 105` (Bambu: 50), `travel_speed`,
`default_acceleration`, `wall_loops`, `top_shell_layers`,
`seam_slope_type`. PrusaSlicer genauso (`prusa_followers.py`, MK4S-Bündel:
zwölf Tempo-Schlüssel für einen Rat, `gap_fill_speed: 170` statt 120,
`first_layer_speed: 100` statt 40); ElegooSlicer ebenso
(`elegoo_followers.py`). Ein Rat auf `shell.scarf_seam` oder
`shell.precise_outer_wall` schreibt 9 bis 13 Schalenschlüssel, einer auf
`infill.density` auch `sparse_infill_pattern` und `infill_direction`, einer
auf `support.style` auch Schwelle, Abstände und Schnittstelle
(`object_keys_probe.py`, `object_keys_probe2.py`).

Was der Slicer daraus druckt — gemessen in echten Läufen (Deckel mit
Passung neben einem Klotz ohne, Sonden `test_zz_review_probe3/4/5.py`,
Tempo je Objekt und Bahnart aus der Druckdatei):

| Slicer | Füllung innen (voll) Deckel / Klotz | Außenwand Deckel / Klotz | Wände Schicht 1 Deckel / Klotz |
|---|---|---|---|
| Bambu Studio, P1S | **270 / 250** | 30 / 200 | 50 / 50 |
| ElegooSlicer, CC2 | **200 / 250** | 30 / 160 | 50 / 50 |
| PrusaSlicer, MK4S | gleich (Objektwert = Kette, beide vom Volumenstrom gedeckelt) | 30 / 30 (siehe B7) | 40 / 40 |

Die Regionswerte am Objekt wirken also: Am Bambu druckt das Passungsteil
seine volle Füllung 8 % schneller als das Profil des Herstellers, am Elegoo
20 % langsamer, beides ohne Grund am Modell. Die erste Schicht dagegen
bleibt unberührt — die Objektwerte `initial_layer_speed` und
`first_layer_speed` übergehen alle drei Slicer. (Eine erste Fassung dieses
Berichts nahm hier die doppelte Wandgeschwindigkeit in Schicht 1 an; die
Messung widerlegt das.) Dazu steht das Teil im Objektfenster des Slicers
mit 21 eigenen Einstellungen da, wo vier gemeint sind.

Warum es zählt:
- `dateiformat.md`: „Ein mitbedienter Schlüssel wird nie schneller als beim
  Hersteller (`_followers_not_faster`)“ und „Ein übernommener Vorschlag
  bremst, er beschleunigt nicht“ — am Objekt greift keine der beiden Regeln,
  gemessen am Bambu.
- Konzept B / `dateiformat.md`: „Was sich nicht übersetzen lässt, wird nicht
  umgedeutet (`Foundation.foreign`)“ — am Objekt wird Solidons Rückfallwert
  geschrieben (etwa ein Füllmuster, das Solidon nicht kennt), während der
  Dialog am Feld zusagt „Hersteller: … Gedruckt wird er, solange Sie das
  Feld nicht ändern“ (`print_settings_dialog.py:5972-5986`).
- Der vorhandene Test
  `test_print_settings.py::test_an_object_override_carries_the_measures_of_its_group`
  sagt die Absicht selbst: „Nur die betroffene Gruppe — die Wandzahl des
  Teils ist die der Platte.“ Innerhalb von `speed` und `shell` gilt dasselbe.
- Konzept §2 und Changelog-Satz „ändert nur, was Ihr Modell verlangt“.

Fix: `object_keys` auf die Pfade der Ratschläge und ihre Partner aus
`COUPLED_PATHS` beschränken — dieselbe Regel, die `as_mapping(paths=…)` über
`_with_partners` schon hat (der Haftungstest oben bleibt grün, er prüft nur
Partner) —, abgeleitete Schlüssel weiter über den Vergleich
`before != changed` (Stützdichte als Abstand). Test: ein Teil mit
Passungsrat an einer Grundlage, in der `internal_solid_infill_speed` und
`sparse_infill_speed` verschieden sind (eigene Prozessdatei im Test) — am
Objekt stehen nur die vier Passungsschlüssel; Gegenprobe gegen den heutigen
Stand rot.

### B2 — Ein übernommener Vorschlag über einer eigenen Wahl verschwindet still aus der Datei

`app/core/export/handover.py:882-897` (`split_for_parts`) setzt jeden
übernommenen Pfad aus `PART_PATHS` auf der Platte auf die **Grundlage des
Herstellers** zurück; `app/core/knowledge/print_settings.py:569-574`
(`with_accepted`) hat die eigene Wahl auf demselben Pfad beim Übernehmen
gelöscht („höchstens eine Menge“). Der Rat je Teil wird danach an dieser
Grundlage gefragt (`writer.py:1222-1246`). Liefert er dort nichts, landet
der Wert nirgends.

Gemessen (Sonde `test_zz_review_probe2.py`, ElegooSlicer-Installation,
Centauri Carbon 2, PLA, `write_assembly` mit `setup`): Grundlage `auto`
(Elegoos Auto-Brim). Der Kunde wählt im Dialog „Skirt“ (`with_choice`), der
Rat bietet dem schlanken Turm „Brim“ an (Skirt hält nicht), der Kunde
übernimmt:

```
chosen: ['adhesion.skirt_loops'] accepted: ['adhesion.kind']
split per_part: ['adhesion.kind'] Platte: auto
Platte brim_type: None        (Elegoos auto_brim gilt)
Objekt Turm brim_type: None   (kein Brim am Turm)
Befunde: []
```

Im Dialog steht „Haftung: Brim“ als übernommener Vorschlag; gedruckt wird
Elegoos Auto-Brim auf allen Teilen plus die Skirt-Runden der früheren Wahl,
ohne Befund. Das verletzt `schichtanalyse.md` („Ein Vorschlag ist ein
Knopf, kein Hinweis. Was er trägt, landet auf Klick in der Datei für den
Slicer“), Konzept G („Eine eigene Wahl im Dialog gilt weiter der ganzen
Platte“) und H („Der Druckdialog zeigt, was gedruckt wird“), und es ist
still (Regel 21 im Geist). Derselbe Mechanismus greift, wenn Dialog und
Export den Rat je Teil verschieden beantworten (Dialog: Anzeige-Netz,
`split_for_parts` über *alle* Vorschläge angenommen; Export:
`mesh_for_export`, nur die tatsächlich übernommenen).

Fix, klein und ohne Formatsprung: In `split_for_parts`/`_part_values` einen
Pfad, dessen Rat je Teil für **kein** Teil den übernommenen Wert liefert,
auf der Platte behalten statt auf die Grundlage zu setzen — „ein
übernommener Vorschlag verschwindet nie still“. Test: der Ablauf oben,
danach `brim_type` der Platte `outer_only`, Gegenprobe rot. Die vollständige
Lösung (Plattenwert der eigenen Wahl neben dem übernommenen Wert je Teil)
braucht ein Feld im Format und gehört ins Register.

### B3 — Bei PrusaSlicer mit Prusa-Drucker schlägt Solidon nie einen Brim vor, auch nicht je Teil

`app/core/slice/advise.py:653` `UNANCHORED = frozenset({"skirt", "auto"})`,
gelesen von `_unanchored` (`advise.py:663-676`), das dieses Paket für alle
drei Brim-Regeln in `_from_geometry` und `for_part` einführt. Die Grundlage
am Prusa-Bündel liest `adhesion.kind = "none"` (`manufacturer.py:1095-1110`,
`_prusa_adhesion`: Prusas Drucker haben `skirts = 0` und `brim_width = 0`,
weil der Startcode eine Spüllinie zieht). „Keine Haftung“ gilt damit als
gehalten.

Gemessen (Sonde `prusa_brim.py`, installierter PrusaSlicer, MK4S 0.4,
`0.20mm SPEED @MK4S 0.4`, `Prusament PLA @MK4S`):

```
Haftung der Grundlage: none brim_width 0.0 skirts 0
Rat je Teil (schlank, 16 mm² Fuß): [('speed.outer_wall', 166.0)]
```

Ein Turm 4 × 4 × 80 mm auf 16 mm² bekommt keinen Brim — weder für die
Platte noch je Teil. In 0.5.0 lag unter Prusa Solidons Tabelle mit „Skirt“,
dort kam der Vorschlag. `ROADMAP-ARCHIV.md` (RM-250: „bei PrusaSlicer und
CuraEngine, die keinen haben, bleibt der Vorschlag je Teil“) und
`tests/test_print_settings.py::test_the_orca_auto_brim_already_holds_a_part`
behaupten das Gegenteil; der Test setzt für Prusa `adhesion.kind = "auto"`,
das `_prusa_adhesion` nie liefert (raft/brim/skirt/none). Die Lücke
entstand mit Stufe C auf `main`; dieses Paket baut Stufe E für Prusa darauf
und belegt sie an einem Zustand, den es dort nicht gibt. Die neue Regel aus
`3018613e6` („Kein Vorschlag überstimmt, was das Profil für denselben Zweck
trägt“) deckt das nicht: Prusas „keine“ ist keine Haftungsart, die kleine
Füße hält.

Fix: `"none"` in `UNANCHORED`; Test mit der Grundlage, die
`_prusa_adhesion` für `skirts = 0, brim_width = 0` liest, statt mit
`"auto"`. Die Zahl der Vorschläge an Prusa-Druckern steigt dadurch — der
Korpuslauf sollte das einmal sehen.

### B4 — Der Prüfbericht nennt weder Teil noch Einstellung, und der Tooltip spricht Punktpfad und `True`

Nach dem Export steht je Pfad und Grund „Für einzelne Teile gilt eine
andere Einstellung als für die Platte — die Geometrie verlangt es.“
(`writer.py:1327-1368`). Die Zeile trägt keinen Wert aus `_LINE_VALUES`
(`panels.py:1039`), der Tooltip zeigt `Einstellung: support.style` bzw.
`shell.scarf_seam` und `Wert: True` (`labels.value_text` → `choice_label`
kennt weder Punktpfade noch `True`) und nur die Zahl der Teile, nicht ihre
Namen; ohne `object_id` wählt ein Klick nichts. Bei einem Deckel mit vier
übernommenen Passungswerten entstehen vier gleich lautende Befunde, die der
Bericht zu einer Zeile „(4) Für einzelne Teile gilt …“ bündelt — was die
vier sind, steht nur im Tooltip, und dort als Pfad. Der Befund ist älter,
seine Reichweite ist mit Stufe E von „Brim“ auf alle 14 Pfade gewachsen,
und er ist nach dem Übernehmen die einzige bleibende Auskunft, welches Teil
was bekommt. Regel: `oberflaeche.md` „Kein Wort, das nur ein Konstrukteur
kennt“; die Frage des Auftrags „Muss er raten?“ ist hier ja.

Fix: Der Befund nennt Feldtitel (`print_settings_dialog.FIELDS` oder eine
Kerntabelle der Titel), den Wert über die Namenstabelle und die Teile —
etwa „Stützen: Automatisch für Pilz. Die übrigen Teile drucken wie die
Platte.“ —, `object_id` je Teil bzw. die Körper der Sammelzeile für den
Klick; Texte in allen fünf Katalogen. Test: Zeile und Tooltip enthalten den
Teilenamen und keinen Punktpfad.

### B5 — Curas Fenster bekommt einen neuen Weg (3MF statt STL), der im Fenster selbst nie geöffnet wurde

Nachweis, kein Codefehler. `writer.py:1630-1640` schickt *Im Slicer
öffnen* bei Cura jetzt immer über `_cura_window` (3MF mit
`cura:`-Metadaten, Sperre als Komponente, Versatz um den halben Bauraum von
Solidons Drucker). Belegt ist der Weg an Curas Quelltext und an der
Struktur der Datei
(`test_curas_window_gets_the_blocker_and_the_values_of_each_part`);
`ROADMAP.md` (RM-257) führt „offen die Sichtprüfung im Cura-Fenster“. Das
STL, das bisher geöffnet wurde, war im Fenster erprobt. Offen ist, ob Cura
5.13 die Werte je Objekt als Einstellungen je Objekt zeigt, ob die Sperre
als Stützblocker erscheint und ob die Teile auf dem Bett liegen — auch
dann, wenn Curas aktive Maschine ein anderes Bett hat als Solidons Drucker
(der Versatz rechnet mit `profile.printer.build_volume`) oder Solidons
Anordnung nicht hält (`_cura_window` verschiebt immer, die Konsole nur bei
`place_on_bed`; der Docstring verspricht „an derselben Stelle wie in der
Kommandozeile“).

Fix: einmal im Fenster öffnen (Pilz + Klotz, Tunnelblock mit Sperre),
Ergebnis in RM-257 festhalten; bei Abweichung Rückfall auf das STL.

## Register nach 0.5.1

### B6 — Nach dem Übernehmen zeigt der Dialog einen Wert je Teil als Wert der Platte

Vor dem Übernehmen nennt die Zeile die Teile („Stützen · Pilz“,
`print_settings_dialog.py:2033-2091` `_with_parts`, `:6739-6760`
`_advice_title`), nach dem Klick die Statuszeile einmal (`_apply_advice`,
„Übernommen: …“). Danach steht im Feld „Stützen: Automatisch“ mit fetter
Beschriftung und dem Tooltip „Übernommener Vorschlag. Zurücksetzen auf …
aus …“ (`_mark_origins`, `print_settings_dialog.py:5931-5966`) — ohne ein
Wort, dass die Platte weiter ohne Stützen druckt und nur der Pilz sie
bekommt; beim nächsten Öffnen fehlt auch die Statuszeile. Konzept H: „Jedes
Feld zeigt den wirksamen Wert.“ Mit B4 steht die Auskunft wenigstens im
Bericht; ins Register, weil es eine Anzeige mehr am Feld braucht.

Fix: Ein übernommener Pfad aus `PART_PATHS` trägt neben dem Feld die Teile,
denen er gilt (Quelle `writer.part_advice`, wie die Zeile), der
Rücksetz-Tooltip sagt „gilt für: …; die übrigen Teile drucken mit … aus …“.

### B7 — `plate_paths` und `for_part` fragen Volumenstromdeckel, die der Dialog für Orca und Prusa verwirft

`app/core/slice/advise.py:1377-1386` (`plate_paths`) ruft `advise()` ohne
Slicerfamilie; `_from_flow` deckelt dort `speed.outer_wall`, obwohl der
Dialog diese Deckel für die Orca-Familie und PrusaSlicer weglässt
(`print_settings_dialog.py:6163-6176`, `slicer_keys.caps_volumetric_speed`,
`advise.limits_flow`). Gemessen (Sonde `bambu_plate_paths.py`, Bambu P1S):

```
Generic PLA            max_flow 12  plate_paths: [..., 'speed.outer_wall', ...]
                                      per_part: ['shell.precise_outer_wall'] Platte outer_wall: 30.0
Bambu PLA Basic @BBL   max_flow 21  per_part: [..., 'speed.outer_wall']        Platte outer_wall: 200.0
```

Im PrusaSlicer-Lauf aus B1 (Prusament PLA, 15 mm³/s) ebenso: Die
Außenwand des Klotzes ohne Passung fährt 30 mm/s
(`external_perimeter_speed = 30` im Kopf der Druckdatei). Das langsame
Tempo einer Passung geht an alle Teile, begründet mit einem Deckel, den der
Slicer selbst setzt und den der Kunde nie zu sehen bekam; `for_part` nimmt
dieselben Deckel in den Rat je Teil (B3: `speed.outer_wall 166`). Nur Zeit,
kein Druckfehler, aber gegen Entscheidung G.

Fix: `plate_paths(settings, profile, flavour)` und `for_part` lassen
`limits_flow`-Einträge weg, wo `caps_volumetric_speed(flavour)` gilt.

### B8 — `fit_kinds_for` zählt ausgeschaltete Passungsschritte mit

`app/core/scene/fits.py:312-348`: Rückwärtsgang über `document.ops` und die
Prüfung auf `FITTING_OPS` lesen `Operation.suppressed` nicht; nur
eingetragene Passungen ruhen über `active_fits`/`paused_fits`. Sonde
`fits_suppressed.py`: `insert_nut_trap` aktiv → `('clearance',)`,
ausgeschaltet → `('clearance',)`. Aus dem Dialog verschoben
(`_fits_in_play`), trifft jetzt auch den Export je Teil und den
Kalibrierhinweis. Fix: Schritte mit `suppressed is not None` überspringen;
Test mit ausgeschaltetem Schritt.

### B9 — Der Rat je Teil schneidet einen Körper, und die Stützsperre schneidet ihn noch einmal

`writer.py:1387-1420` hat einen Parameter `result` mit dem Kommentar „hat
der Rat je Teil den Körper schon geschnitten, gilt dessen Ergebnis“; kein
Aufrufer übergibt ihn (`writer.py:1668-1670`, `1869-1871`), `_PartValues`
hält das Ergebnis nicht fest. Mit übernommenen Stützen und Sperre schneidet
`_part_values` mit `detail="full"` (`writer.py:1222-1233`) und
`_support_blocker` danach mit `detail="support"`; `remembered_analysis`
trifft nur den Schnitt des Prüfberichts, bei einem exakten Körper
(`mesh_for_export` vernetzt neu) gar nicht. Am Eiffelturm kostete *ein*
solcher Schnitt den größten Teil von 17 s (DRUCK-14). Beim Dateiexport aus
dem Hauptfenster läuft der Schnitt ohne Abbruch (`main_window.py:1347`
übergibt kein `cancelled`). Fix: `result` durchreichen, Abbruch
durchreichen — oder den Kommentar streichen (`tests.md`, „Am erfundenen
Beleg vorbei“).

### B10 — *Fertig* in den Ersten Schritten hält den Oberflächen-Thread bis zu zehn Sekunden

`app/ui/first_run.py:754-773`: `survey.wait(10_000)` im Hauptthread, nur mit
Wartezeiger, danach `processEvents()`. Gemessen ist rund eine Sekunde
(ElegooSlicer, 1001 Profile); PrusaSlicers Bündel und ältere Rechner liegen
darüber. `wartezeit.md`: über 2 s „Fortschritt mit Abbrechen, Oberfläche
bedienbar“. Das `processEvents()` kann einen gepufferten zweiten Klick auf
*Fertig* zustellen. Fix: *Fertig* sperren, solange die Suche läuft, und
beim Eintreffen freigeben.

### B11 — Zwei Stellen entscheiden, ob eine gemerkte Maschine noch gilt

`print_settings_dialog.py:4256-4262` (neu) und `remembered_setup`
(`print_settings_dialog.py:1125-1138`) prüfen dieselbe Bindung an Drucker
und Slicer getrennt; der neue Kommentar sagt „dieselbe Regel wie beim
Export“ (`zwillinge.md`: „Ein Kommentar ‚dieselbe wie …‘ ist kein
Teilen“). Eine dritte Stelle (`:3881-3885`, Druckplatte) prüft nur den
Drucker. Fix: eine Funktion, von allen drei gefragt.

### B12 — `SCARF_MIN_LOOP` ist eine abgeschriebene Ableitung

`advise.py:210`: „zwei Rampen der Schrägnaht (``slicer_keys.SCARF_LENGTH``)“
steht als Literal `40.0` (`zwillinge.md`). Fix:
`SCARF_MIN_LOOP: Final = 2.0 * SCARF_LENGTH`; der Import aus
`export.slicer_keys` ist zyklenfrei (`slicer_keys` importiert nur
`app.i18n`, beide Paket-`__init__` sind leer).

### B13 — Ein Test hält einen Zustand fest, den die Anwendung nie herstellt

`tests/test_print_settings.py::test_without_a_known_slicer_automatic_adhesion_stays_unanchored`
prüft `for_part(..., flavour=None)`; der Dialog übergibt
`flavour or "orca"` (`print_settings_dialog.py:6441`), `write_assembly` hat
`flavour="orca"` als Vorgabe, und `_unanchored`s Docstring („Ohne bekannten
Slicer bleibt es bei der Vorsicht“) beschreibt einen Weg, den kein Aufrufer
geht. `AGENTS.md`, Testart „Anschluss“. Fix: Aussage entscheiden, Docstring
oder Aufrufer angleichen, Test über den Dialog-Arbeiter ohne Slicer.

## Commit `3018613e6` (Mindestzeit je Schicht)

Gelesen ganz (5 Dateien). `advise._from_geometry` schlägt die 15 s nur
noch vor, wo `is_zero(settings.cooling.minimum_layer_time)` gilt (Regel 6
eingehalten), der Grund des Vorschlags sagt genau das, die neue Regelzeile
in `schichtanalyse.md` trifft den Code, der neue Test
`test_a_minimum_layer_time_of_the_profile_stays` hält 4 s, 8 s und die
Gegenprobe 0 s. Die vier angepassten Tests setzen die Mindestzeit auf null,
damit sie weiter den Spulenweg prüfen; `> 0` statt `> 1` ist gegenüber dem
neuen Ausgangswert gleich streng. **Kein Befund.** Ausgeführt:
`test_advise.py` und der geänderte Test in `test_print_settings.py` am
Stand `3018613e6`, 44 bestanden, Exit 0; die zwei geänderten Fenstertests
nicht (Release).

## Regelcheck (AGENTS.md, Regel für Regel am geänderten Code)

| Regel | Ergebnis |
|---|---|
| 1 Kein Qt unter `ui/` | eingehalten — kein Qt-Import in den geänderten Kernmodulen |
| 2 Keine Geometrie außerhalb einer Op | eingehalten — der Versatz in `_cura_window` gilt nur der Datei |
| 3 `OpContext.scene` nur lesend | nicht berührt |
| 4 Op mit Register | nicht berührt (keine neue Op) |
| 5 Verträge zuerst | kein neues Modul |
| 6 Millimeter, kein `==` auf Fließkomma | eingehalten (`is_close`, `is_zero`, Ungleichungen, `same_value`) |
| 7 Keine Toleranzkonstante | eingehalten — `NARROW_WEB_AREA`, `SCARF_*`, `SMOOTH_TURN_DEGREES` sind Ratschwellen mit Herkunft |
| 8–13 | nicht berührt |
| 14 Herkunft Schichtanalyse/G-Code | eingehalten — `cura_machine_differences` im Befund mit `source="gcode"` |
| 15 Keine GPL | nicht berührt |
| 16 Agentenvorschlag eine Transaktion | nicht berührt |
| 17 Ausnahme mit Handlungsvorschlag | keine neue Ausnahme; `export.part_setting*` begründet in `OHNE_KNOPF` |
| 18 Keine Bedeutung allein über Farbe | eingehalten — Teile als Text, Knopf mit Text |
| 19 Keine Bestätigung vor Rücknehmbarem | eingehalten |
| 20 Kein fester Text | eingehalten — neue Texte über `tr()`/`_()`, alle fünf Kataloge nachgezogen, der alte Cura-Fenster-Satz überall entfernt |
| 21 Nie still raten | **B2** (übernommener Wert verschwindet still) |
| 22 Keine neue Abhängigkeit | eingehalten |

Ohne Regelnummer: keine deutschen Bezeichner in `app/`; Karten (`export`,
`slice`, `scene`, `knowledge`, `tests`) und Regeln (`dateiformat.md`,
`schichtanalyse.md`, `tests.md`) sind nachgezogen und treffen den Code;
`ROADMAP.md`/`ROADMAP-ARCHIV.md` verschieben RM-250 korrekt (bis auf die
Prusa-Aussage, B3).

## Geprüft und in Ordnung

- **Messung auf dem Raster ihrer Probe** (`manufacturer.measured_on`,
  `_measured`, `_unmeasured`, `written_paths`, `print_settings.resolve` mit
  Stufen-Schichthöhe, Dialog-Setter): Grundlage, Analyse und Übergabe
  fragen dasselbe Raster; eine eigene Wahl der Schwelle bleibt. Die neuen
  Tests in `test_manufacturer.py` prüfen hin und zurück.
- **Schrägnaht**: `smooth_outline_height` über Arme der Düsenbreite,
  deterministisch; Tests mit Sollwerten aus der Konstruktion (Zwölfkant,
  128-Kant, Rundung 0,3/4 mm). Schlüssel je Familie mit Länge, Bambus
  Filament-Schalter; Rücklesung Orca/Prusa nur mit Länge über null. Die
  Begriffe stimmen mit OrcaSlicers Übersetzung (de „Schrägnaht“, fr
  „Couture en biseau“, it „Cucitura a sciarpa“).
- **Stegfläche** (`NARROW_WEB_AREA`): Die Geometrie des Tests ist
  nachrechenbar (vier Stege 2 × 60 mm = 480 mm², 8,9 % der ersten
  Schicht), die Gegenprobe steht daneben.
- **Cura je Netz**: Rücknahme über `PartSplit.revert` stimmt. Verdacht
  geprüft und **widerlegt**, dass `support.block_channels` bei Cura als
  „nicht je Teil annehmbar“ gemeldet würde, obwohl die Sperre je Netz
  geschrieben wird (Sonde `test_zz_review_probe.py`: Die Basis behält den
  Pfad, der Rat feuert nicht, kein Befund).
- **Werte je Teil kommen an**: Außenwand 30 mm/s nur am Passungsteil
  (Bambu, Elegoo, gemessen), `support_material_auto` am Prusa-Objekt,
  Konsole = Datei (`test_the_console_gets_the_same_plate_as_the_file`).
- **Cura-Gegenprobe**: Name und Startcode in Reihenfolge, gefüllte Codes,
  nur mit Druckerdefinition; keine Fehlalarme gefunden.
- **Haftungsprüfungen je Teil** und Stützsperre je Teil rechnen mit dem
  Wert, den das Teil bekommt.
- **Druckdialog**: Slicerwahl über dem Abschnitt, Druckerwahl als Vorgabe
  nur über `activated`, gemerkte Maschine gebunden, Knopf „… übernehmen“ mit
  Tooltip, Statuszeile und Beschreibung; `_with_parts` rechnet im Arbeiter,
  Passungen je Körper im Hauptthread.
- **Erste Schritte**: Suche beim Öffnen, späte Antworten über `sender()`
  abgewiesen, Leine hält die Arbeiter.
- **Kalibrierhinweis nur mit Passungen**: ein Aufrufer, Wert aus dem
  Hauptthread; der Satz spricht nur von Toleranzen.
- **PHP-Prüfserver**: alle drei Startwege tragen `opcache.enable=0`.
- **Randfälle**: leere Szene (Absage vor dem Split), ein Körper
  (Objektwerte, keine Teilnamen), Cura ohne Druckerdefinition (keine
  Gegenprobe), Prusa ohne Bündel (Tabellengrundlage, alles geschrieben),
  mehrere Platten (ein Split für die Datei, je Platte eine Datei bei
  Prusa/Cura), Mehrfarbe (`slot_processes` je benutzter Spule) — ohne
  weiteren Befund.

## Gelesen und ausgeführt

Gelesen: der vollständige Diff Datei für Datei plus `3018613e6`, dazu der
umgebende Code der berührten Funktionen, das Konzept, die genannten Regeln
und Karten.

Ausgeführt, nur in der Arbeitskopie im Scratchpad (nichts im Repository):
- Sonden gegen die installierten Bambu Studio, ElegooSlicer und PrusaSlicer:
  `object_keys_probe.py`, `object_keys_probe2.py`, `bambu_followers.py`,
  `elegoo_followers.py`, `prusa_followers.py`, `bambu_fit_part.py` (B1),
  `test_zz_review_probe3/4/5.py` (B1, echte Slicerläufe),
  `test_zz_review_probe2.py` (B2), `prusa_brim.py` (B3),
  `bambu_plate_paths.py` (B7), `fits_suppressed.py` (B8),
  `test_zz_review_probe.py` (Cura-Sperre, widerlegt).
- Die neuen Tests des Pakets ohne Fenster: 28 + 24 bestanden am Stand
  `dd95985e5`, 44 bestanden am Stand `3018613e6`, jeweils Exit 0.
- Nicht gefahren: das Entwicklungstor, die Fenstertests (Release), die
  Slicer-Abnahmen des Pakets.

## Urteil

**Mergebar: ja** (Stand `3018613e6`). Nichts blockiert den Merge. **Vor dem
Tag** zu beheben: B1 (Objektwerte nur für die übernommenen Pfade und ihre
Partner), B2 (kein stilles Verschwinden eines übernommenen Werts), B3
(`"none"` hält kein Teil), B4 (Befund mit Teil, Feldtitel und Kundenwort);
nachzuweisen: B5 (Curas Fenster einmal öffnen). B6–B13 gehen ins Register
nach 0.5.1.

## Nachtrag bc7e3e2da

Stand 28.09.2026. Geprüft: `git diff 3018613e6 bc7e3e2da` (sechs Commits,
25 Dateien, +641/−142), ganz gelesen. Sonden am Stand `bc7e3e2da` (Arbeitskopie
per `git archive` im Scratchpad) gegen die installierten Bambu Studio,
ElegooSlicer und PrusaSlicer; Vergleichsläufe am Stand `3018613e6`.
Zeilennummern gelten für `bc7e3e2da`.

### Urteil

**Mergebar: nein.** Blockierend ist ein einziger Rest: **N1** — die neue
Lösung zu B2 gibt einen übernommenen Vorschlag je Teil auf jeder Platte, auf
der kein Teil ihn verlangt, **allen** Teilen dieser Platte. Bei *Slicen* (alle
Familien, je Platte ein Lauf) und *Im Slicer öffnen* (PrusaSlicer, Cura)
bekommen damit auf jeder Platte, auf der kein Körper Stützen verlangt, alle
Körper Stützen — bei Roberts Minigolf-Satz auf drei Platten genau dann, wenn
die Körper, die Stützen brauchen, nicht auf jeder Platte liegen. Das ist der
Ausgangsfehler des Konzepts, auf den übrigen Platten zurück. Nach N1: vor dem
Tag N2 (Ausrichtung urteilt am ausgedünnten Netz) und weiterhin B5
(Sichtprüfung Cura-Fenster); N3–N5 ins Register.

| Nr. | Stufe | Kurz |
|---|---|---|
| B1 | behoben | Objektwerte nur die Pfade des Rats; am Bambu 250 mm/s innen an beiden Teilen |
| B2 | behoben, **aber N1** | Übernommenes verschwindet nicht mehr still — auf einer Platte |
| B3 | behoben | MK4S: Turm bekommt Brim-Vorschlag, im PrusaSlicer nur um den Turm |
| B4 | behoben | Befund je Teil mit Feldname und Wert, ohne Punktpfad und `True` |
| B5 | offen, vor dem Tag | Cura-Fenster unverändert nicht angesehen (RM-257) |
| N1 | **blockiert den Merge** | `_unserved` sieht nur die eigene Platte |
| N2 | vor dem Tag | `orientation.stays` fragt das Ersatznetz: 4 von 30 Minigolf-Körpern falsch beurteilt, Satz 2× CPU |
| N3 | Register | `writer._same_value` ist ein Zwilling von `print_settings.same_value` |
| N4 | Register | Kommandozeile bündelt Teilwerte ohne Teil und Einstellung |
| N5 | Register | Behaltene Lage meldet „Ausrichtung … gesucht“ statt des Grunds |

### 1. Sind B1–B4 behoben?

**B1 — ja** (`4f2f96adf`, `handover.py:769`: Pfade des Rats und ihre Partner
aus `COUPLED_PATHS`, dazu Abgeleitetes). Nachgemessen am echten Slicer
(Sonden `bambu_fit_part.py`, `test_zz_review_probe3/4/5.py`):

| | vorher (`dd95985e5`) | jetzt (`bc7e3e2da`) |
|---|---|---|
| Bambu P1S, Objektwerte des Passungsteils | 21 | 4: `outer_wall_acceleration 2000`, `outer_wall_speed 30`, `precise_outer_wall 1`, `wall_sequence` |
| Bambu Studio, innere Vollfüllung Deckel / Klotz | 270 / 250 mm/s | **250 / 250** |
| Bambu Studio, Außenwand Deckel / Klotz | 30 / 200 | 30 / 200 |
| ElegooSlicer, innere Vollfüllung Deckel / Klotz | 200 / 250 | **250 / 250** |
| PrusaSlicer, ein Rat `speed.outer_wall` | 12 Schlüssel | 1: `external_perimeter_speed` |

Gegenprobe des neuen Tests `test_an_object_override_carries_only_the_advised_paths`
am alten Code: 24 statt 3 Schlüssel, rot; am neuen grün.

**B3 — ja** (`a1926aa93`, `advise.py:656`: `"none"` in `UNANCHORED`). Sonde
`prusa_brim.py` am MK4S-Bündel (`0.20mm SPEED @MK4S 0.4`, `Prusament PLA
@MK4S`): Der Turm 4 × 4 × 80 mm bekommt je Teil `adhesion.kind → brim`
(vorher nichts). Ende zu Ende (`test_zz_review_probe6.py`, installierter
PrusaSlicer): Objektwert `brim_width 5` am Turm, Platte `brim_width 0`, in
Schicht 1 liegen Brim-Züge nur um den Turm (X 88,8–101,2, Y 98,8–111,2 bei
einem Turm um X 95). Der Test setzt jetzt die Grundlage, die
`_prusa_adhesion` wirklich liefert (`"none"`).

**B2 — für eine Platte ja** (`176d961c9`, `writer._unserved`,
`writer.py:1304-1341`, Aufruf `writer.py:1664`). Nachgestellt
(`test_zz_review_probe2.py`, ElegooSlicer, eigene Wahl „Skirt“, dann Brim
übernommen): Turm und Klotz tragen `brim_type outer_only`, die Platte behält
Elegoos Auto-Brim, der Bericht meldet `export.part_setting_all`. Über mehrere
Platten nicht: N1.

**B4 — ja** (`176d961c9`). Sonde `b4_lines.py` über `_line_for` und
`_value_lines`: „Nur für dieses Teil: Die Überhänge sind zu groß, … — Teil 1 ·
Stützen: Automatisch“; im Tooltip „Schrägnaht: an“, „Außenwand: 30,0 mm/s“,
„Fülldichte: 40 %“, „Linienbreite: 0,350 mm“, „Druckbetthaftung: Brim“ —
kein Punktpfad, kein `True`; `object_id` je Befund, der Klick wählt das Teil.
Der zugehörige Test (`test_value_labels.py`) ist ein Fenstertest und lief
hier nicht.

### 2. B2 anders gelöst — tut es, was der Kunde sieht?

**Auf einer Platte ja, auch in Cura.** Verlangt beim Export kein Teil den
übernommenen Wert, zeigt auch der Dialog die Zeile ohne Teile (dieselbe Frage
in `_with_parts`), das Feld zeigt den Wert, und in der Datei trägt ihn jedes
Teil — deckungsgleich mit H. Nennt der Dialog Teile und der Export findet
keines (Anzeige- gegen Exportnetz), bekommt jedes Teil den Wert: mehr als die
Zeile sagte, nie weniger, und der Befund sagt es. G kann dort nichts
zuordnen; „allen“ ist die Bedeutung der Platte aus 0.5.0 und passt zum Feld.
Cura: `test_cura_keeps_an_accepted_suggestion_no_part_asks_for` — jedes Netz
`support_enable=true`, keine Rücknahme; die Platte trägt die Übernahme dort
ohnehin. Ein veralteter übernommener Vorschlag (Modell seither geändert)
gilt damit wieder allen; der Dialog bietet dann den Gegenvorschlag an, der
Rückweg ist da.

**Überstimmt ein Objektwert an jedem Teil eine eigene Wahl der Platte?** Auf
einer Platte nein. Sonde `test_zz_review_probe7.py` (ElegooSlicer): Kunde
wählt Skirt mit 3 Runden und 8 mm Brimbreite, übernimmt dann Brim, kein Teil
verlangt ihn. An beiden Teilen `brim_type outer_only, brim_width 8,
skirt_loops 0, raft_layers 0` — die gewählte Brimbreite geht mit; im G-Code
Brim an beiden Teilen, kein Skirt. Den Skirt nimmt nicht `_unserved`, sondern
die bestehende Regel `_only_chosen_adhesion` (die Haftungsart ist ein
Schalter; mit Brim nullt Solidon Skirt und Raft, auf der Platte wie am
Objekt). Mit B1 trägt ein Objektwert nur Pfade des Rats und ihre Partner;
Stützort, Schwelle, Tempi einer eigenen Wahl bleiben unberührt. Über Platten
hinweg überstimmt er dagegen die Grundlage aller Teile, die ihn nicht
verlangen: N1.

### 3. Ausrichtung (`2611950c2`)

**„Steht“ ist richtig bestimmt**: `stays` fragt zuerst `stands(baseline,
floor)` — Schwerpunkt in der Hülle der Auflage am **Original** und die
Auflage um eine halbe Linienbreite nach innen versetzt über der kleinsten
Aufstandsfläche. Sonde `orient_probe.py`: Ein Quader auf seiner Kante hat
Fuß 0,0, steht nicht und wird auf eine Fläche gedreht.

**Was stehend Stützen braucht, wird weiter gedreht**: T auf dem Stiel (35 mm
Kragarm) liegt danach flach; ein liegender Rundstab steht zwar (188 mm²), braucht
aber Stützen und wird aufgestellt; Schaft mit schwebendem Stift (Insel) wird
gedreht; dazu der bestehende Schirm-Test.

**Mehrere Körper, Passungen**: Das Op sucht je Körper für sich
(`prepare_ops.py:17138-17171`), der frühe Abbruch gilt je Körper. Zwei
stehende Schäfte in einem Körper (zwei Schalen) bleiben stehen (vorher
hingelegt). Passungen fragen weder `search` noch `stays`; der Abbruch hängt
allein an Stand und Stützbedarf.

**Minigolf-Satz, 30 Körper**, alt (`3018613e6`) gegen neu, `orientation.search`
mit CC2/PLA (`minigolf_orient.py`, je ein Lauf unter Fremdlast — Wandzeiten
schwanken, das Muster je Körper deckt sich mit den Einzelmessungen): dieselbe
Lage für alle Körper außer den Schäften `obj_27_1` und `xobj_26_2`, die jetzt
stehen bleiben statt hingelegt zu werden — genau die Absicht.

**Die volle Suche entfällt nur bei `kept`** (`orientation.py:543-552`) — so
ist es gebaut. Der Preis ist aber nicht „ein Schnitt“ im Sinn der Suche,
sondern ein voller Schnitt im Druckraster (`detail="full"`, 0,2 mm) vor der
Suche, an jedem Körper, der steht: N2.

### 4. mypy und Regel 17

- `mypy --platform linux`, `--platform darwin`, `--platform win32` am Stand
  `bc7e3e2da`: je „Success: no issues found in 330 source files“, Exit 0.
- `export.part_setting_all` ist `info`; `test_finding_ways` verlangt einen
  Weg nur für Warnungen und Fehler und ist grün. Regel 17 ist damit
  eingehalten. Ein Knopf *Druckeinstellungen* wäre der natürliche Weg
  zurück (Register, N5-Umfeld).
- `test_finding_ways`, `test_translations`, `test_language_rules`: 535
  bestanden, Exit 0; die fünf Kataloge tragen die drei neuen Texte, die
  alten sind überall entfernt.

### N1 — Die Lösung zu B2 sieht nur die eigene Platte (blockiert den Merge)

`writer.py:1326`: `served = {item.path for entry in values for item in
entry.applied}` — `values` sind die Teile **dieser** Datei. Bei *Slicen*
schreibt der Druckdialog je Platte eine Datei
(`print_settings_dialog.py:2294`, `_PrepareAndSliceWorker` →
`_prepare_plate`, das `write_assembly(on_plate, …)` ruft,
`print_settings_dialog.py:1783-1800`), ebenso *Im Slicer öffnen* für
PrusaSlicer und Cura (`print_settings_dialog.py:2356`). Liegt das Teil, das
den Vorschlag verlangt, auf Platte 1, gilt er auf Platte 2 als „von keinem
Teil verlangt“ und geht an **jedes** Teil dort.

Gemessen (`test_zz_review_probe8.py`: Pilz und Klotz auf Platte 1, Klotz 2
auf Platte 2, „Stützen: Automatisch“ übernommen, `write_assembly` je Platte
wie `_prepare_plate`):

| Familie | Platte 2 am Stand `3018613e6` | Platte 2 am Stand `bc7e3e2da` |
|---|---|---|
| Orca | Klotz 2 ohne Objektwert | `enable_support 1`, Befund `export.part_setting_all` |
| PrusaSlicer | Klotz 2 ohne Objektwert | `support_material 1`, Befund `export.part_setting_all` |
| Cura | Netz `support_enable false` | Netz `support_enable true`, Befund `export.part_setting_all` |

Der Dialog nennt dabei „Stützen · Pilz“ (`_with_parts` fragt alle Körper
aller gewählten Platten). Mit Stützen an stützt der Slicer jedes Teil der
anderen Platten nach seiner eigenen Schwelle — auch die kleinen Überhänge,
die Solidons Regel als selbsttragend wertet. Genau das war der Minigolf-Druck
(treppenförmiger Stützfuß), und Roberts Satz liegt auf drei Platten. Für
Brim, Schrägnaht und Passungswerte gilt dasselbe. Gegen G, H und die Zeile
im Dialog; ein Rückschritt gegenüber `3018613e6`, der dort auf den anderen
Platten richtig nichts schrieb.

Fix: „verlangt“ heißt verlangt von einem Teil **des ganzen Auftrags**. Wo
eine Platte einen ungedienten Pfad findet, fragt `write_assembly` den Rat je
Teil der übrigen Körper des Auftrags für genau diese Pfade (nur dann, und
über `remembered_analysis` meist ohne neuen Schnitt), oder der Auftrag
bringt die im Ganzen gedienten Pfade mit (`_PlateJob`). Kleinster sicherer
Zwischenschritt: `_unserved` nur anwenden, wenn die Datei den ganzen
Auftrag trägt — dann kehrt B2 nur für Platten-Läufe zurück, in denen
wirklich kein Teil des Auftrags den Wert verlangt. Test: der Aufbau der
Sonde, Platte 2 ohne Objektwert und ohne `export.part_setting_all`;
Gegenprobe am heutigen Stand rot.

### N2 — Die Ausrichtung beurteilt den Stützbedarf am ausgedünnten Netz (vor dem Tag)

`orientation.py:546`: `stays(proxy, …)` schneidet das Ersatznetz der Suche
(`search_proxy`, höchstens 20 000 Dreiecke) im Druckraster; der Prüfbericht
fragt dieselbe Regel am Original (`findings.py:149`). Sonde
`proxy_vs_original.py` über alle 30 Minigolf-Körper, CC2-Raster: 26 gleich,
**3 falsch positiv** (Ersatznetz „Stütze nötig“, Original nicht:
`obj_28_3`, `xobj_1_Mini Golf Son v17`, `xobj_2_Gövde59` — die Ausdünnung
erzeugt Inseln und Überhänge, am Rundschaft v17 eine Insel, 289 statt
12 mm² Überhang und 24,6 mm Brücke) und **1 falsch negativ**
(`obj_30_Gövde79`: Ersatznetz „keine Stütze“, Original „Stütze nötig“ — der
Körper wird behalten, ohne dass eine Lage verglichen wird; hier war die
volle Suche zum selben Ergebnis gekommen, im Allgemeinen verspricht der
Docstring von `stays` genau das Gegenteil: „Nur was so Stützen braucht oder
nicht steht, wird gedreht“).

Kosten, Minigolf-Satz (30 Körper): Summe Wand 82,5 → 96,4 s, CPU 97,6 →
191,1 s. Schneller wurden die behaltenen Körper (z. B. `obj_23_Dönen`
6,9 → 0,8 s), langsamer die falsch positiven (v17 1,3 → 18,3 s, `obj_28`
1,3 → 6,6 s, `Gövde59` 0,7 → 3,3 s; `stays` allein am v17 65,8 s CPU) und die
sechs Schrauben, die wirklich Stützen brauchen (je rund +1 s). Die
Leistungszeile `orient_200_200k` (§31): 5,4 → 6,0 s (+10 %), unter der
25-%-Schwelle. Die Commit-Meldung verspricht das Gegenteil („die Suche hört
dann sofort auf“, „kostet einen Schnitt“); an den zwei Schäften, um die es
ging, kostet der Abbruch hier so viel wie vorher die ganze Suche.

Fix: `stays` am Original urteilen wie der Prüfbericht, zuerst über dessen
gemerkte Schichten (`findings.remembered_analysis`), sonst mit eigenem
Schnitt; am v17 ist das Original sogar billiger (7,4 statt 16,6 s). Test:
`obj_30`-artiger Körper (Ersatznetz ohne, Original mit Stützbedarf) wird
gedreht bzw. verglichen; v17 wird ohne zweite Suche behalten.

### N3–N5 — Register nach 0.5.1

- **N3** `writer.py:1344-1352` `_same_value` ist ein zweites „dasselbe
  Einstellungswert“ neben `print_settings.same_value` — mit `EPS_DISPLAY`
  (0,01) statt `EPS_SETTING` und ohne dessen Bool-Abfrage (`True` gleich
  `1.0`). Heute unschädlich (ein Pfad hat einen Typ), `zwillinge.md`:
  zusammenlegen.
- **N4** `app/cli/main.py:219-230` (`print_findings`) bündelt nach Satz und zeigt nur den Satz:
  „(3) Nur für dieses Teil: …“ ohne Teil und Einstellung. Die Kommandozeile
  sagt damit weniger als vor B4.
- **N5** Behält *Druckoptimal ausrichten* die Lage, meldet es
  „Ausrichtung über die Schichtanalyse gesucht.“ mit einem Kandidaten
  (`orientation.py:648-662`) — der Kunde sieht nichts gedreht und keinen
  Grund. Besser: „Die Lage bleibt: Das Teil steht und braucht keine
  Stütze.“

Unverändert offen aus dem Hauptteil: **B5** (vor dem Tag, Sichtprüfung
Cura-Fenster; RM-257 führt sie weiter als offen) und B6–B13 (Register).

### Gelesen und ausgeführt (Nachtrag)

- Gelesen: alle sechs Commits ganz, dazu `orientation.search`, `stays`,
  `stands`, `judge`, `orient_for_print_op`, `_prepare_plate(s)`,
  `_unserved`, `_values_for`, `_part_setting_findings`, `panels._line_for`
  und `_value_lines`, `test_finding_ways`.
- Ausgeführt im Scratchpad: die Sonden oben (echte Slicerläufe Bambu Studio,
  ElegooSlicer, PrusaSlicer); Tests ohne Fenster am Stand `bc7e3e2da`: 65
  bestanden (Ausrichtung, Export, Druckeinstellungen, Hersteller) und 535
  (Befundwege, Übersetzungen, Sprachregeln), Exit 0; mypy auf drei
  Plattformen, Exit 0.
- Nicht gefahren: das Entwicklungstor, die vier geänderten Fenstertests aus
  `bc7e3e2da` und der Fenstertest zu B4 (Release), Leistungstests.

## Nachtrag 211789878

Stand 28.09.2026. Geprüft: `git diff bc7e3e2da 211789878` (fünf Commits,
21 Dateien, +752/−118), ganz gelesen. Läufe im eigenen Arbeitsbaum
`wt-revgesamt` (detached `211789878`, zum Vergleich kurz auf `3018613e6`),
gebunden über `skripte/lauf-wt.sh` (Affinität `FFFFF0FF`); für `origin/main`
(`6eacc1a63`) ein zweiter Baum `wt-revmain`. Beide sind danach entfernt.
Zeilennummern gelten für `211789878`.

### Urteil

**Mergebar: nein.** Blockierend ist ein Rest: **N6** — die Lösung zu N1 gilt
nur dem Druckdialog. Der Dateiexport aus dem Hauptfenster schreibt die
**gewählten** Körper ohne `job`, und ein für den Pilz übernommener Vorschlag
landet an jedem gewählten Teil. Das ist N1 auf dem zweiten Weg, und gegenüber
`origin/main` ein Rückschritt. Die Behebung ist eine Zeile. Alles andere aus
dem Nachtrag hält; der rote Fenstertest kommt nicht aus ihm.

| Nr. | Stufe | Kurz |
|---|---|---|
| N1 | behoben | *Slicen* und *Im Slicer öffnen* je Platte fragen den ganzen Auftrag |
| N6 | **blockiert den Merge** | Dateiexport einer Auswahl ohne `job` (`main_window.py:1347-1360`) |
| N2 | behoben | `stays` am Original, nur gegen einen anderen Gewinner mit Stützraum |
| N5 | behoben | `orient.kept` in sechs Sprachen, ohne grobe Stützzahlen |
| B5 | behoben | Cura-Fenster mittig auf dem Bett der aktiven Maschine; Belegtafel gesehen |
| `04ca4e53d` | in Ordnung | Kopien teilen die Suche nur bei reiner Verschiebung |
| N7 | zurückgenommen | Verdacht „Gewinner nach grobem Stützraum“ — die Sonde widerlegt das Beispiel |
| N8 | Register | `_served_elsewhere` fragt im seltenen B2-Fall jede Platte gegen alle übrigen Teile |
| N9 | Register | `shape_key` rundet auf 1 nm, der Docstring sagt Mikrometer |
| — | Hinweis | Fenstertest rot nur auf dem Zweig (fehlt `1509d1db9` aus main); vier Textkonflikte beim Merge |

### N1 — behoben

`writer.py:1339-1378` (`_served_elsewhere`), `writer.py:1715-1731`, der
Dialog reicht die Teile aller gewählten Platten durch
(`print_settings_dialog.py:1809`). Der neue Test
`test_an_accepted_suggestion_is_asked_of_the_whole_job_not_one_plate` geht
den Weg des Dialogs (`_prepare_plate`) in Orca, Prusa und Cura und prüft
auch die Gegenseite (Klotz allein → B2 gilt weiter); am Stand `bc7e3e2da`
zeigte meine Sonde genau den roten Fall (Klotz 2 mit Stützen in allen drei
Familien). *Im Slicer öffnen* mit mehreren Platten in einem Slicer, der
Platten kennt (`knows_plates`), schreibt alle in eine Datei
(`_prepare_plates`, `print_settings_dialog.py:2407`) und braucht `job` nicht;
die übrigen Wege gehen über `_prepare_plate` (`print_settings_dialog.py:2301`,
`2363`, `7188`).

### N6 — Der Dateiexport einer Auswahl fragt nicht den ganzen Auftrag (blockiert den Merge)

`main_window.py:1347-1360`: `_ExportWorker._assembly` ruft
`write_assembly(self._objects, …)` ohne `job`. `self._objects` sind die
**gewählten** Körper (`MainWindow._start_export`, `main_window.py:7768-7773`:
`selected_objects()`, nur ohne Auswahl alle), und der Arbeiter hält den
ganzen Auftrag schon als `self._all_objects` (`main_window.py:1201`, gesetzt
aus `result.scene.objects` in Zeile 7808) — gebraucht wird er dort nur für
die Filamentprofile (`main_window.py:1310`).

Gemessen (Sonde `tests/test_zz_review_nachtrag.py`, nur im Arbeitsbaum;
Pilz und Klotz, „Stützen: Automatisch“ übernommen, `write_assembly` wie der
Exportarbeiter mit `for_slicer=False`):

```
ganze Szene:                       {'Pilz': '1', 'Klotz': None}  ['export.part_setting']
nur Klotz gewählt, ohne job:       {'Klotz': '1'}                ['export.part_setting_all']
nur Klotz gewählt, mit job:        {'Klotz': None}               []
```

Dieselbe Sonde auf `origin/main` (`6eacc1a63`, Arbeitsbaum `wt-revmain`,
ohne `job`, das es dort nicht gibt):

```
main ganze Szene:        {'Pilz': '1', 'Klotz': None}  ['export.part_setting']
main nur Klotz gewählt:  {'Klotz': None}               []
```

Wer im Baum nur den Klotz gewählt hat und *Exportieren* wählt, bekommt eine
3MF, in der der Klotz die Stützen des Pilzes trägt; der Bericht sagt „Gilt
für alle Teile: Beim Export brauchte kein Teil diesen übernommenen Vorschlag
für sich allein.“ Das stimmt für die Datei und nicht für den Auftrag, den der
Dialog mit „Stützen · Pilz“ gezeigt hatte. Gegen G („nur an den Teilen, die
ihn brauchen“) und ein Rückschritt gegenüber `origin/main`, das dort nichts
schreibt.

Abgegrenzt: Die Plattenwahl im Druckdialog („Platte 2“ allein) gibt `job`
ebenfalls nur die gewählten Platten, dort ist das aber stimmig. Der Dialog
fragt Vorschläge und Teilzeilen über dieselben Körper (`_plate_bodies`,
`_with_parts`), zeigt für Platte 2 das übernommene „Automatisch“ im Feld,
und die Datei trägt es (H). Der Dateiexport zeigt vorher nichts; sein
Auftrag ist die Szene, wie beim Dialog über alle Platten. Der Docstring von
`write_assembly` („Ohne Angabe ist die Datei der Auftrag“, `writer.py:1630-1634`)
lässt diese Wahl dem Aufrufer, und das Hauptfenster hat sie nicht getroffen.

Fix: `job=self._all_objects` im Aufruf; in `dateiformat.md` zur Regel „Ein
übernommener Vorschlag verschwindet nie still“ der Satz, dass jeder Aufruf
mit einem Teil des Auftrags `job` mitgibt (sonst entsteht der nächste
Aufrufer ohne). Test: `_ExportWorker` mit Auswahl „Klotz“ und dem ganzen
Auftrag in `all_objects`, `_assembly()` direkt gerufen — Klotz ohne
`enable_support`, kein `export.part_setting_all`; Gegenprobe am heutigen
Stand rot. Ohne `qt_app` bauen: Die bestehenden Tests des Arbeiters
(`test_filament_workflow.py:56`) nehmen `qt_app` und sind damit Fenstertests,
die erst beim Release laufen.

### N2 und N5 — behoben

`orientation.py:670-683`: Die Suche läuft immer ganz; `stays` fragt nur,
wenn der Gewinner eine andere Lage ist (`same_pose`, `orientation.py:219`:
keine Stelle um eine Schicht verschoben) und groben Stützraum hat, und dann
**am Original** (`stays(mesh, …)`), gemerkt im Netz-Cache
(`_STAYS_CACHE`, `orientation.py:459`). Der Cache prüft beim Lesen, ob sich
die Ecken geändert haben (`trimesh` `Cache.__getitem__` ruft `verify`), und
`transform._carry_cache` trägt nur eine feste Liste von Topologie- und
Maßeinträgen weiter — ein gedrehtes Netz erbt das Urteil nicht.

Minigolf-Satz, 30 STL, `orientation.search` mit CC2/PLA, gebunden und im
Wechsel alt (`3018613e6`) / neu / neu (Sonde `rg_minigolf.py`):

| | alt | neu 1 | neu 2 |
|---|---|---|---|
| Summe CPU / Wand | 57,3 / 44,7 s | 59,0 / 46,8 s | 60,8 / 48,7 s |
| Schaft `obj_27_1` | liegend, 17,6 mm hoch | stehend (200 mm), `orient.kept` | ebenso |
| Schaft `xobj_26_2` | liegend, 19,2 mm hoch | stehend (200 mm), `orient.kept` | ebenso |
| `stays` gerufen | — (gibt es dort nicht) | nur an den zwei Schäften, 2,5 und 2,2 s CPU | 3,1 und 2,0 s CPU |
| Wand je Schaft | 1,2 / 1,3 s | 2,9 / 2,6 s | 3,0 / 2,8 s |

Die übrigen 28 Körper liegen wie vorher (Richtung und Höhe je Körper
verglichen), ihre Zeiten streuen in beide Richtungen; die Mehrkosten sind
der Schnitt an den zwei Schäften. Die Platte auf der Kante liegt
wieder flach (`test_a_plate_on_its_edge_is_laid_flat_although_it_stands`).
N5: `orient.kept` „Die Lage bleibt: Das Teil steht und braucht keine
Stütze.“ mit Übersetzungen in allen fünf Katalogen, `info`, ohne Stützzahlen.

### B5 — behoben

`writer.py:2077-2078` legt die 3MF mittig auf das Bett der Maschine, die in
Cura aktiv ist; `slicer_profiles.py:649-674` (`_cura_bed`) liest die
Erbkette der Maschinendefinition, überschrieben von den
Maschineneinstellungen des Nutzers (`definition_changes`). Gegengelesen an
Curas Quelltext: `ThreeMFReader.py:300-308` (Cura 5.13) zieht bei jedem
globalen Stapel die halbe `machine_width`/`machine_depth` ab. Die Belegtafel
(`output/review/b5-cura-2026-09-28/b5-belegtafel.png`, angesehen) zeigt im
Fenster „Generate Support“ am Pilz an und am Klotz aus, je Objekt; die
Sperre als „Don't support overlaps“, mit ihr den Kanal frei, ohne sie
gestützt; den 210-mm-Auftrag vorher rechts über den Rand, jetzt mittig. RM-257 ist zu Recht im
Archiv.

### `04ca4e53d` — Kopien teilen die Suche: keine falsche Übernahme gefunden

Schlüssel `(shape_key(mesh), angle)` (`prepare_ops.py:17142-17164`),
`shape_key` hasht die Ecken relativ zur kleinsten Ecke samt Dreiecken
(`orientation.py:766-782`). Sonde `rg_shape_key.py`:

```
verschoben (100, -50, 0)           gleicher Schlüssel: True
verschoben (0.1234567, 0, 0)       gleicher Schlüssel: True
gedreht 180° / 90° um Z            gleicher Schlüssel: False
gedreht 360° um Z                  gleicher Schlüssel: True
gespiegelt an YZ                   gleicher Schlüssel: False
skaliert 1,001                     gleicher Schlüssel: False
gleiche Form, andere Eckenfolge    gleicher Schlüssel: False   (nur ein verpasster Treffer)
```

- **Lage, Skalierung, Spiegelung:** getrennt. Eine anders gedrehte Kopie
  sucht selbst (auch im Test `test_copies_share_one_search`).
- **Material:** Die Suche hängt am Körper nur über den Überhangwinkel
  (`analysis_limits(ctx.profile, entry)[1]`, `prepare_ops.py:17147`), und der
  steht im Schlüssel. Wand, kleinste Aufstandsfläche und `stays` rechnen mit
  `ctx.profile`, das für alle Körper eines Schritts gleich ist. Der Winkel
  steht als Zahl im Schlüssel; er kommt für dasselbe Material aus derselben
  Tabelle und ist bitgleich — ein Fehlgriff kostete eine Suche, nie eine
  fremde Lage.
- **Profil:** Der Speicher `searched` ist lokal in `orient_for_print_op`
  und lebt nur während eines Schritts; über Profile hinweg teilt nichts.
- **Determinismus:** `search` wählt ohne Zufall (Docstring: `seed` nur noch
  für gespeicherte Aufrufer), und das Ersatznetz rastert ab der kleinsten
  Ecke (`mesh_ops._clustered_for_display`: `low = vertices.min(axis=0)`) —
  eine verschobene Kopie fände dieselbe Lage selbst. Die Kopie übernimmt die
  Richtung, ihren Platz auf dem Bett rechnet `turned_like` für sie
  (`fitting_transform`, `orientation.py:784-812`); passt die Lage dort nicht,
  sucht sie selbst. Ein verpasster Treffer an einer Rundungskante kostet nur
  eine Suche.
- **Zusammen mit `merkmale-an-kopien` (`b9252ee36`):** kein Widerspruch.
  Dort fragt die Auswertung einen Bewegungsvermerk aus `transform.apply`
  samt geometrischem Beleg (`moved_from`, `moved_twin`, absolute Abdrücke),
  hier fragt die Suche die Form bis auf Verschiebung — zwei Fragen, die nur
  im Wort „Kopie“ zusammenfallen. Die Cache-Einträge berühren sich nicht
  (`solidon.orientation.stays` gegen `solidon_moved_from`, und
  `_carry_cache` trägt keinen von beiden weiter). `git merge-tree` der
  beiden Zweige: ohne Konflikt. Wer eine Stelle später anfasst, prüft, ob
  „dieselbe Form“ an eine Stelle gehört (`zwillinge.md`, fachlicher
  Zwilling) — kein Befund.

### Fenstertest `test_value_labels::test_the_offer_button_click_reaches_the_handler`

Einzeln mit `-o faulthandler_timeout=120`: **rot** auf `211789878` und
ebenso auf der Merge-Basis `3018613e6` („0 == 1“), **grün** auf `origin/main`
`6eacc1a63`. Ursache: Der Zweig enthält `8615dc1e6` („An einem verbrauchten
Körper steht kein Knopf, der ihn braucht“, RM-268), aber nicht die
Testanpassung `1509d1db9` („Zwei Prüfberichtstests legen lebende Körper in
die Szene“), die nur auf `main` liegt; der Test baut eine Szene ohne den
Körper des Befunds. Nicht aus dem Nachtrag, verschwindet mit dem Merge. Der
Fenstertest zu B4 (`test_a_part_setting_names_the_part_the_field_and_the_value`)
ist einzeln grün.

### Beim Merge nach main

`git merge-tree --write-tree origin/main origin/uebergabe-gesamtpruefung`
(`origin/main` = `6eacc1a63`; der Hauptbaum steht noch auf dem älteren
`f1cfff619`, dort sind es drei ohne `fr.json`): vier Textkonflikte —
`.claude/rules/schichtanalyse.md`, `ROADMAP-ARCHIV.md`,
`app/i18n/locales/fr.json`, `it.json`. In den Katalogen sind es Nachbarn:
`main` hat „Nur für den Weg aus Text …“ (und in `it` „Nur mit passender
Sechskantmutter …“) neu übersetzt, der Zweig fügt daneben „Nur für dieses
Teil: {reason}“ ein. Auflösen: die Zeilen von `main` behalten, den neuen
Schlüssel dazu. `test_translations` danach.

### N7 — zurückgenommen

Verdacht aus dem Code: `orientation.py:679` misst „der Gewinner braucht
selbst Stütze“ am groben Stützraum der Suche, „die Ausgangslage braucht
keine“ an der Regel der Druckvorschläge. Eine hochkant gelieferte Platte, die
flach einen winzigen groben Stützraum hätte, bliebe dann stehen. Mein
Beispiel (Gravur unten) trägt nicht, die Suche wendet die Platte einfach.
Sonde `rg_kante.py` (100 × 60 × 4 mm, hochkant): scharfe Kanten, rundum
verrundet mit 1,5 mm und mit 0,6 mm — alle drei liegen danach flach
(`orient.searched`, Höhe 4,0 mm), grober Stützraum des Gewinners 0,
`stays` nicht gerufen. Einen Fall, in dem die ungleiche Frage wirkt, habe
ich nicht gefunden; wo der Gewinner groben Stützraum hat, hält `stays` die
gelieferte Lage, und das ist die Absicht des Commits. Kein Befund.

### N8, N9 — Register nach 0.5.1

- **N8** `writer.py:1339-1378`: Im echten B2-Fall (kein Teil des ganzen
  Auftrags verlangt den Wert) fragt jede Platte den Rat jedes Teils der
  übrigen Platten (`_part_values` → `_body_analysis`); bei n Platten wird
  jeder Körper n-mal befragt statt einmal. `remembered_analysis` fängt das
  meist ab, wo der Prüfbericht dasselbe Raster schon geschnitten hat; sonst
  (kein Bericht mit diesem Raster, oder ein exakter Körper, den der Export für
  ein feineres Verfahren neu vernetzt, `mesh_for_export`) ist es ein voller
  Schnitt je Frage, im Arbeiter vor dem Start des Slicers. Die Antwort je
  Körper einmal für den Auftrag merken.
- **N9** `orientation.py:766-775`: „auf einen Mikrometer gerundet“ —
  `np.round(…, 6)` in Millimetern sind Nanometer. Die Wirkung beschreibt der
  Docstring richtig (eine Rundungskante kostet eine Suche); die Zahl führt in
  die Irre, wer die Treffergrenze daran bemisst.

### Gelesen und ausgeführt (zweiter Nachtrag)

- Gelesen: alle fünf Commits ganz, dazu `_ExportWorker`,
  `_start_export`, die Aufrufer von `write_assembly` (Hauptfenster, zwei im
  Dialog), `_plate_bodies`, `_with_parts`, `_carry_cache`,
  `remembered_analysis`, `trimesh.caching.Cache.__getitem__`, Curas
  `ThreeMFReader.py`, der Zweig `merkmale-an-kopien` (`b9252ee36`,
  Bewegungsvermerk, `_carry_cache` dort) und die Testanpassung `1509d1db9`
  auf `main`.
- Ausgeführt, gebunden im Arbeitsbaum: Kerntests `test_orient`,
  `test_orientation_search`, `test_slicer_profiles`, `test_finding_ways`,
  `test_translations` (328 bestanden, 1 abgewählt) und `test_export`,
  `test_print_settings`, `test_manufacturer` (696 bestanden, 4 übersprungen),
  die vier neuen Tests einzeln (6 Fälle, einer über drei Slicer, bestanden),
  jeweils Exit 0; mypy `win32`, `linux`, `darwin`: je „Success: no issues
  found in 330 source files“; die zwei Fenstertests einzeln (auf `211789878`,
  `3018613e6` und `origin/main`); Sonden `rg_minigolf.py` (dreimal, im
  Wechsel), `rg_shape_key.py`, `rg_kante.py`, die Auswahl-Sonde auf
  `211789878` und auf `origin/main`. Laufausgaben unter
  `F:/3D Druck.review-051/laeufe/rg-*.txt`.
- Nicht gefahren: das Entwicklungstor, die übrigen Fenstertests,
  Leistungstests.
