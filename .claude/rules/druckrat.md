---
description: "Druckrat — Vorschläge aus Geometrie, Material und Maschine: ein Vorschlag je Einstellung mit Grund, Stützbedarf, Kanäle, Ränder, Bäume, Stützkontakt je Material, Kühlung, Haftung; kein Vorschlag überstimmt das Profil für denselben Zweck"
paths:
  - "app/core/slice/**/*.py"
---

# Regeln für den Druckrat

Messwerte, Modellreihen und Anlässe stehen unter denselben Überschriften in
`konzepte/begruendungen/regel-druckrat.md`. Schnitt, Übergabe und Erkennung:
`schichtanalyse.md`.

## Vorschlag oder Befund

`slice/advise.py`: Was ein Wert behebt, wird ein **Vorschlag**
(`SettingAdvice` mit Pfad, altem und neuem Wert und **Begründung** — ohne Grund
keiner); was kein Wert behebt, ein **Befund** (`Finding`), etwa ASA auf
offenem Drucker. Übernommen wird auf Klick, nie von allein.

- **Ein Vorschlag je Einstellung**, `was` ist der Ausgangswert; Regeln auf
  denselben Wert werden zusammengeführt, die spätere gewinnt. Der Volumenstrom
  läuft zuletzt, weil er an Schichthöhe, Bahnbreite und Tempo hängt.
- **Volumenstrom** (Schichthöhe × Bahnbreite × Tempo gegen `max_flow`): ein
  Tempo je Bahnart, die erste Schicht mit eigenen Maßen; keine pauschale
  Temperaturanhebung (keine Kurve hinterlegt), und eine kleine Standfläche
  begründet Haftung, keine Filamenttemperatur. Reicht auch das kleinste Tempo
  nicht, hält die Beratung mit einem Vorschlag zu Schichthöhe, Bahnbreite oder
  gemessenem Profilwert an — eine leere Liste wäre keine Entwarnung.
- **„Viel auf einmal“ heißt an einem Stück** (`largest_overhang_patch`), nicht
  je Schicht — kleine Stegunterseiten tragen sich selbst; eine schräge
  Unterseite zählt als Feld ihrer Decke (`largest_sloped_patch`). Ein Ergebnis
  ohne Stücke gilt schichtweise als eines; lange Stege fängt die Brückenregel.
- **Den Stützwinkel sagt, womit der Slicer stützt** (Konzept Herstellerprofil,
  Entscheidung L): gemessen auf dem Raster der Probe, sonst die Schwelle des
  gewählten Herstellerprozesses, sonst `overhang_limit` aus `printers.toml`,
  sonst die Startregel (`Profile.overhang_limit_degrees`). Auswertung,
  Druckdialog-Rat und Kanalsperre rechnen mit den wirksamen Einstellungen
  (`Session.evaluation_profile`, `profiles.for_process(..., effective=True)`);
  aus einem gespeicherten Satz gilt die Schwelle nur als eigene Wahl.
  **Wer einen Winkel einführt, reicht ihn bis in jede Vorauswahl durch.**
- **Ein Überhangwinkel wird an der Normalen mit dem Sinus verglichen**
  (z < −sin(Grenze)) und an einem Winkel ungleich 45 geprüft (`test_orient.py`).
- **Eine Decke im Kanal verlangt keine Stütze auf dem Modell**
  (`analysis.model_support`): Fasst der Raum **unter** ihr keinen Kreis von
  `CHANNEL_WIDTH` und liegt ihr Grundriss zwischen seinen Auflagen, gehalten
  nur von Material daneben (`_Ceilings.closes`), schließt sie sich selbst.
  Gefragt wird die ganze Decke (Flächenmehrheit). Außen auf dem Modell zählt
  `worth_support`, auch als `open_field`. Wer das anfasst, misst Schüssel und
  Drache.
- **Eine Insel ist nie eine Kanaldecke**: Auf dem Modell heißt es „überall“,
  gleich wie klein (`ModelSupport.island_on_model`), ebenso für eine lange
  Brücke, die selbst dort hängt (`open_bridge_width`); über dem Bett bleibt
  „nur vom Bett“.
- **Bäume, wo kleine Überhänge auf dem Modell ansetzen** (`branching`): Ein
  Baum setzt mit wenigen Füßen auf, ein Gitter mit jeder Säule. Nicht unter
  einem flachen Stück über `OVERHANG_LAYER_WORTH_SUPPORT` — dort bleibt die
  Art des Herstellers.
- **`support.block_channels`**, weil „nur vom Bett“ Kanäle nicht freihält:
  `analysis.channel_space` sperrt um Decken, die sonst Stütze bräuchten
  (`worth_support` je Stück, im Zweifel Stütze), nur unerreichbaren Raum (eng
  oder umschlossen), eine Bahnbreite Zuschlag **vor** dem Aussparen der Säulen
  der Überhänge, deren Decke ohne Kanalstücke als Feld Stütze braucht
  (`_field`), außer im umschlossenen Raum (RM-571). Ohne gesperrten Raum kein
  Vorschlag. Familien: `dateiformat.md`.
  **Vorschlag, nicht Automatik** (Entscheidung Robert).
- **Ränder tragen sich selbst** (`analysis.ledges`): Eine Decke, deren Teil
  jenseits `LEDGE_REACH` um ihre Wurzel höchstens `LEDGE_SPILL` des Felds ist
  und samt Ansatz für sich keine Stütze lohnt (`worth_support`, Eckspitzen
  ohne Ansatz), und die keine Öffnung über `SPAN_INTERESTING` überspannt
  (zwei Bahnen breit, von außen gefasst, Öffnung frei — geometrisch, denn der
  Stützschnitt misst keine Brücken), zählt nicht zum Stützbedarf, nicht zu
  „auf dem Modell“, nicht zum Überhang- und nicht zum Brückenbefund. Wer nur
  einige Stücke prüft, fragt mit `only`. `support.spare_ledges` sperrt ihre
  Überhangfläche (`ledge_space`) und spart aus, was Stütze braucht;
  vorgeschlagen nur mit Stützen.
- **Der Stützkontakt folgt dem Material der Spule** (`_support_contact`):
  Abstand aus Schichthöhe × `support_gap_factor`, begrenzt durch
  `support_gap_min`/`support_gap_max` des Materialprofils (Regel 7,
  `support_gap_target`; ohne Werte kein Rat), vorgeschlagen außerhalb
  `SUPPORT_GAP_BAND`; wo der Slicer in ganzen Schichten rechnet — Cura, die
  Orca-Familie neben einem Reinigungsturm (`writer.tower_plates`,
  `whole_layers`), jedes Programm unter organischen Bäumen mit der Art, mit
  der das Teil druckt (`printed_style`: der Vorschlag, außer der Kunde lehnt
  ihn ab, `declined` — im Dialog abgewählt, dann fragt er neu, im Export nicht
  übernommen; `handover.organic_styles`, ohne Programm die Familie; Rat,
  Feldsatz und Export fragen dieselbe Auskunft) —, das Vielfache innerhalb der
  Materialgrenzen, auch statt eines Werts in `SUPPORT_GAP_BAND`, der zwischen
  zwei Schichten liegt (`in_whole_layers`); einen eigenen solchen Wert nennt
  der Export gerundet (`export.support_gap_rounded`). **Über Baumspitzen ohne
  Trennschicht** (ab `TIP_ISLANDS` Inseln unter `TIP_ROOF_AREA`, `tip_islands`)
  gilt unter organischen und Curas Bäumen `support_tip_gap` des Materials in
  ganzen Schichten, mindestens `TIP_GAP_LAYERS`, auch über `support_gap_max`
  (`tip_gap`); ohne gemessenen Wert nicht. Unter einem flachen Stück über
  `OVERHANG_LAYER_WORTH_SUPPORT` eine dichte Trennschicht, sonst eine lockere;
  steht die Stütze auf dem Modell, auch unten (`BOTTOM_INTERFACE_LAYERS`) —
  nicht, wo das Programm sie unter Bäumen nicht druckt
  (`handover.ignored_under_trees`). Volle Kühlung an der Trennschicht,
  wo das Material sie verlangt (`support_interface_cooling`), je Spule.
  Abstand und Trennschichten gehen je Teil (`PART_PATHS`), gefragt mit dem
  Material der Spule. Der Druckdialog fragt sie wie der Export gegen die
  Grundlage, auch die Stützart, die je Teil geht
  (`handover.asked_for_contact`), führt erst je Körper über die
  Spulen zusammen und dann nur die verlangenden Körper (`combine` mit
  `separate`); gegen die Übernahme gefragt, kam jede Zeile mit ihrer
  Gegenzeile wieder. Die Zeile nennt nur Teile mit ihrem Wert. Übergabe:
  `dateiformat.md`.
- **Was das Modell schon ausgleicht, gleicht der Slicer nicht noch einmal aus**
  (`_from_allowances`, RM-589): Legt ein Schritt des Körpers Spiel in eine
  Innenkontur (`scene.fits.allowances_for`, `"holes"`), heißt der Vorschlag
  *Löcher weiten* null; zieht *Elefantenfuß ausgleichen* seine ersten
  Schichten ein (`"foot"`), *Erste Schicht einziehen* null — je Teil, nur wo
  der Slicer ausgleicht. Gefragt wird am fertigen Körper, Herkunft je
  Körperkennung (`fits._producing`; über alle Eingänge erbte nach *Anordnen*
  jeder Körper den Ausgleich seiner Nachbarn): ein Innenmerkmal, das der
  Slicer in einer Schicht geschlossen sieht (`_closes_in_a_layer`,
  `L·cos θ > d·sin θ` — eine waagerechte Bohrung weitet er nicht), gemacht von
  einem Schritt mit Spiel oder Lochkorrektur (`_puts_allowance_into`); die
  Taschen von *Gegenform einlassen* über Entnahmerichtung und Rahmen. Eine nur
  eingetragene Passung ändert keine Geometrie und zählt nicht, ein Stift,
  Haken oder Bolzen auch nicht.
  **Ein gemessener Wert bekommt keinen Vorschlag**: Sein Prüfkörper ging
  durch den Slicer mit dessen Ausgleich, gemessen ist der Rest dahinter. Das
  gilt je Wert (`MaterialProfile.measured`, Fuß `elephant_foot`, Löcher erst
  mit `clearance` und `hole_compensation`); ein Startwert meint den ganzen
  Ausgleich und bekommt ihn. Der Kalibrierdialog schreibt nur eingetragene
  Felder als gemessen.
  Übergabe (eigener Satz nur auf Wahl, Brim am Fuß): `dateiformat.md`.
- **Die kleine Standfläche wird auch je Fuß gefragt** (`advise._on_small_feet`):
  Erreicht keine von mehreren Inseln `SMALL_FOOTPRINT`, heißt es Brim — nur
  als Vorschlag. `for_part` fragt mit Profil jede Regel für `PART_PATHS`;
  seine Brim-Regeln aus dem Schnitt behalten das letzte Wort.
- **Eine runde Außenwand bekommt die Schrägnaht vorgeschlagen**: glatte
  Umrisse (kein Knick über `analysis.SMOOTH_TURN_DEGREES`, gemessen über Arme
  der Düsenbreite wie im Slicer, ab `advise.SCARF_MIN_LOOP` Umfang) über
  `SCARF_MIN_HEIGHT`.
- **Schmale Stege bekommen eine langsame erste Schicht**: Liegt mindestens
  `advise.NARROW_WEB_SHARE` der ersten Schicht in Stegen unter
  `NARROW_WEB_LINES` Bahnen (`analysis.narrow_share`) oder mehr als
  `NARROW_WEB_AREA` mm² davon, und ist sie schneller als `NARROW_WEB_SPEED`,
  wird dieses Tempo vorgeschlagen. Über dem Herstellerprofil bremst er nur
  (`dateiformat.md`).
- **Kein Vorschlag überstimmt, was das Profil für denselben Zweck trägt**:
  Mindestzeit je Schicht nur ohne eine, kein Brim über Orcas Auto-Brim
  (`AUTO_BRIM_FLAVOURS`) — gebremst wird dort trotzdem: `_calm_walls` für
  schlanke Körper unter `SMALL_FOOTPRINT`, je Teil, und das Mindesttempo
  für Spitzen (`_tips_stay_too_short`, `TIP_SPEED`), damit die Mindestzeit
  des Herstellers überhaupt greift.
- **Mehrere Körper werden gemeinsam beurteilt** (`advise.combine`) — ein
  Würfel schaltet die Stützen eines anderen nicht ab. Filamentwerte je
  tatsächlichem Slot, Prozesswerte für alle gewählten Körper; Abgewähltes
  bleibt bei Neuberechnung abgewählt.
- **Die Druckanalyse benutzt das Druckraster**: `slice_body` bekommt normale
  und erste Schichthöhe aus den effektiven Einstellungen; der Dialog misst den
  Ausgabeumfang im Hintergrund und verwirft Ergebnisse veralteter Szene,
  Platte oder Raster. Fehlende oder abgebrochene Messung ist keine
  Entwarnung. Die Orientierungssuche behält ohne Erstschichthöhe ihr
  gleichmäßiges Raster.
- **Was in Geometrie gerechnet ist, wird nicht so gedruckt**: `solid_core`
  misst `Durchmesser − 2 × Wandzahl × Bahnbreite`. Gemeldet erst, wenn der
  Füllkern breiter ist als das Material darum; vorgeschlagen wird die Wandzahl
  genau bis dahin, nie bis vollmassiv, bei gefülltem Kern nichts — und über
  `MOST_WALLS_WORTH_SUGGESTING` keine, der Obergrenze des Dialogfelds, die der
  Kern selbst führt (Regel 1; `tests/test_print_settings_ui.py` hält beide
  gleich). Der Materialanteil belegt keine Festigkeit.
