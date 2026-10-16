# Funde des Funktionsdurchgangs (RM-736)

Konzept: `konzepte/konzept-funktionsdurchgang-2026-10.md` §7. Je Fund eine
Überschrift `### FD-<n> <Kurztitel>`; Nummern werden nie wiederverwendet.
`tools/function_report.py` liest und prüft diese Datei. Am Programmende zieht
sie mit den Abhaklisten nach `konzepte/`.

Felder je Fund, in dieser Reihenfolge:

| Feld | Werte |
|---|---|
| Art | Leistung, Stabilität, Fehler, Zwillinge, Aufräumen, Einfachheit, Verständlichkeit, Gestaltung |
| Schwere | schwer, mittel, leicht, Vorschlag (I ohne Bauplanzusage, der Chatweg zu I6 gehört an Prüfpunkt 17; G9 höchstens leicht) |
| Funktion | Kennungen der Zeilen aus der Funktionsliste, durch Komma, Semikolon oder „und“ getrennt; ein Fund, der keine Zeile betrifft (Prüfstand, Werkzeug), beginnt mit „keine Zeile:“ |
| Prüfpunkt | 1–19 oder Kriterium (E1 … I6) |
| Beleg | Bild, Kennzahl, Schrittfolge |
| Ursache | Satz |
| Vorschlag | Satz |
| Wirkung beim Kunden | Satz |
| Stand | offen RM-…, behoben `<commit>`, gut nach Fix `<lauf>`; nennt ein offener Stand einen Commit im Laufkopf, sagt er mit „Rest: …“, was offen bleibt, sonst hält `report` den Lauf an (FD-153) |

Schwer heißt falsches Ergebnis, Datenverlust, Sackgasse oder nicht auffindbar;
mittel heißt Regelverstoß, Umweg oder Fehlerweg ohne Handlung; leicht heißt
Text oder Darstellung (Konzept §4, „Urteil und Schwere“).

## D0 (RM-737)

### FD-1 Text aufbringen löscht am exakten Körper alle Merkmale

- Art: Fehler
- Schwere: schwer
- Funktion: `label_text`
- Prüfpunkt: 4
- Beleg: exakter Quader 40 × 30 × 20, *Text aufbringen* „OS“ 12 mm auf der Deckfläche, durch Verlauf und Auswertung: 6 Merkmale vorher, 0 danach, kein Befund; `features_of` am selben Körper findet 15 (`output/konsolidierung-2026-10-12/fix-schrift-merkmale.md`, Reproduktion)
- Ursache: Der exakte Zweig gab seinen Körper mit leerem `features` aus (`label_ops.py`, seit v0.5.0), und der exakte Zweig der Auswertung meldet keinen Verlust.
- Vorschlag: Ausgang über `_exact_features_after` benennen, Gewinde nur mit `threads_to_read`; Wächter über die Falltabelle in `tests/test_exact_body_parity.py`. Berührte und geteilte Flächen der übrigen exakten Neubauten führt RM-787.
- Wirkung beim Kunden: Nach einer Beschriftung findet ein folgender Schritt seine Fläche, Bohrung oder sein Gewinde nicht mehr, und niemand sagt warum.
- Stand: behoben `e871f6062`

### FD-2 Schrift einlegen löscht am exakten Körper alle Merkmale

- Art: Fehler
- Schwere: schwer
- Funktion: `inlay_text`
- Prüfpunkt: 4
- Beleg: Zwillingssuche zu FD-1, statisch und über jede exakte Variante der Falltabelle; Träger und Einlage ohne Merkmale (`fix-schrift-merkmale.md`)
- Ursache: derselbe leere Ausgang wie FD-1, seit v0.5.2.
- Vorschlag: wie FD-1, für Träger und Einlage.
- Wirkung beim Kunden: wie FD-1, an Träger und Einlage.
- Stand: behoben `e871f6062`

### FD-3 Gegenform einlassen löscht am exakten Körper alle Merkmale

- Art: Fehler
- Schwere: schwer
- Funktion: `cut_counter_form`
- Prüfpunkt: 4
- Beleg: Zwillingssuche zu FD-1, statisch und über jede exakte Variante der Falltabelle; Ausgang ohne Merkmale (`fix-schrift-merkmale.md`)
- Ursache: derselbe leere Ausgang wie FD-1, seit v0.5.2.
- Vorschlag: wie FD-1.
- Wirkung beim Kunden: wie FD-1, am Körper mit der Aussparung.
- Stand: behoben `e871f6062`

### Probelauf am echten Fenster

Aus dem Probelauf am echten Fenster (51 Fälle, Lauf `F:\tmp-suche\probelauf-d0`,
Auswertung `output/konsolidierung-2026-10-12/auswertung-probelauf-d0.md`). Leichte
Funde einer Zeile behebt ihr Paket; mittlere und die systemischen leichten behebt D0.

### FD-4 Strg+Z nimmt nach einer Befundhandlung nichts zurück

- Art: Fehler
- Schwere: mittel
- Funktion: `finding.action:place_on_bed`
- Prüfpunkt: 5
- Beleg: Nach *Auf das Bett setzen* liegt der Fokus im Suchfeld der Auswahlkarte; Strg+Z am Fokuswidget nimmt den Schritt nicht zurück, ans Fenster geschickt wirkt es; am echten Fenster nachgestellt (`fix-befundhandlung-ui.md`)
- Ursache: Die nach jeder Auswertung wiederhergestellte Auswahl holte den Reiter *Auswahl* ohne `held()` nach vorn (seit v0.3.1), und jedes Textfeld beanspruchte Strg+Z, auch leer.
- Vorschlag: Wiederherstellung unter `held()`; ein Feld ohne Rücknehmbares gibt Strg+Z und Strg+Y ans Fenster; Fokus bleibt im Bericht.
- Wirkung beim Kunden: Strg+Z nach einer angebotenen Lösung tut nichts, Bauplan §19.2 sagt Undo überall.
- Stand: behoben `da0bae89f`

### FD-5 Ohne Freischaltung scheitert eine angebotene Handlung erst nach dem Klick

- Art: Fehler
- Schwere: mittel
- Funktion: `finding.action:place_on_bed`
- Prüfpunkt: 18
- Beleg: In `sale_without_trial` und `needs_activation` ist *Auf das Bett setzen* offen, der Klick endet im Meldungsfenster mit „… noch nicht aktiviert.: Aktivieren …“; Lauf, Fälle 028 und 029
- Ursache: Prüfbericht, Merkmalfenster, Kontextmenüs, Filament-Schnellwähler und Operationsdialog fragten den Freischaltzustand nicht (seit v0.2.2); `AppError` fügte Titel und Ursache mit „: “ auch hinter einem Satzende.
- Vorschlag: eine Quelle `change_lock` für alle Zugänge, lesende Handlungen bleiben offen; `errors.title_and_detail` für den Satzschluss.
- Wirkung beim Kunden: In der Demo klickt er eine angebotene Lösung und bekommt eine Absage, statt vorher am grauen Knopf den Grund zu lesen.
- Stand: behoben `da0bae89f`

### FD-6 Gröber rechnen änderte nirgends etwas

- Art: Fehler
- Schwere: mittel
- Funktion: `finding.action:use_voxel_stage`
- Prüfpunkt: 7
- Beleg: Für den Vorschlag ließ sich keine Startszene bauen. Im Fenster rechnet eine gekürzte Kette nach ihrer Absage sofort voll, eine volle hat die Voxelstufe schon hinter sich, und festgelegte Stufen (Musterentfernung, Textur) rechnen fein nicht anders. Der Behälterbau setzte seine Kette selbst und lief deshalb nie voll nach (`paket-d0-l.md`, Abschnitt FD-6).
- Ursache: `BooleanFailedError` bot *Gröber rechnen* unabhängig davon an, ob es etwas ändern konnte; `container_ops` kürzte an `boolean` vorbei.
- Vorschlag: Vorschlag, Handler und Texte entfernen; `boolean` kürzt auch für den Behälterbau, die Auswertung rechnet voll nach.
- Wirkung beim Kunden: Ein Knopf in der Absage, der nach dem Klick dasselbe Ergebnis brachte.
- Stand: behoben `6e9b419ac`

### FD-7 Materialtoleranz ist ein Fachwort

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `drill_hole`
- Kriterium: V1
- Beleg: „Materialtoleranz“ im doc von *Bohrung setzen* und im Feld „Materialtoleranz berücksichtigen“, ebenso an `plug_hole`; Lauf, Fall 040, `surfaces/drill_hole-*.json`
- Ursache: `app/core/geom/prepare_ops.py` (doc und Feldtitel), `field_ops.py`; das Wort steht im eingefrorenen Bestand von `tests/data/customer_vocabulary.json`.
- Vorschlag: Slicer-Wort, etwa „Spiel des Materials einrechnen“, in allen Sprachen neu übersetzt; Bestand schrumpft.
- Wirkung beim Kunden: Wer aus dem Slicer kommt, versteht nicht, warum die Bohrung größer wird als getippt.
- Stand: behoben `9ef1b33a0`, `970e8a458`; `tests/test_hole_compensation_words.py` am Stand davor rot (fünf Operationen mit „Materialtoleranz berücksichtigen“ in sechs Sprachen, dazu der alte Titel in `scene/fits.py`), danach heißt der Haken überall „Druckabweichung ausgleichen“ mit dem Satz zur Lochkorrektur aus dem Materialprofil, auch im Befund und im Handbuch; die erzeugten Handbuchseiten zieht das Release nach.

### FD-8 Der Kalibrierstand heißt „Startwert“

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `Bearbeiten/Material kalibrieren …`
- Kriterium: V1
- Beleg: Überschrift „PETG — Startwert“; Fall 034, `flaeche-sprachen-dialog.png`
- Ursache: `app/ui/calibration_dialog.py:73` (`tr("Startwert", context="Kalibrierstand")`).
- Vorschlag: „noch nicht kalibriert“ oder „Werkswerte“.
- Wirkung beim Kunden: Das Wort sagt nicht, dass noch nicht gemessen wurde.
- Stand: behoben `eda0f8407`; Dialog und Kommandozeile sagen „noch nicht kalibriert“, beide Tests am Stand davor rot („PETG — Startwert“); der Agentenauszug folgt dem Wort aus Bauplan §23.

### FD-9 Die Beschreibung von Schriftzug anlegen ist zu lang

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `create_label`
- Kriterium: V2
- Beleg: steht im eingefrorenen Bestand zu langer Texte; Fall 034, `surfaces/create_label-*.json`
- Ursache: `app/core/geom/label_ops.py` (doc).
- Vorschlag: ein Satz, etwa „Legt einen Schriftzug als eigenes Objekt an — zum Aufkleben oder für zwei Farben.“; Eintrag in `tests/data/text_lengths/` streichen.
- Wirkung beim Kunden: Ein zu langer Satz über dem ersten Feld wird übersprungen.
- Stand: behoben `5c8ba4e60`; `test_text_length.py` nach Streichen des Bestandseintrags am Stand davor rot („op_doc zu lang“), mit dem neuen Satz in sechs Sprachen grün.

### FD-10 Die Messfelder der Kalibrierung erklären sich nicht

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `Bearbeiten/Material kalibrieren …`
- Kriterium: V3
- Beleg: fünf Messfelder ohne Kurzhilfe und Beschreibung; Fall 034, `surfaces/Bearbeiten_Material_kalibrieren-*.json`
- Ursache: `app/ui/dialogs.py` (Messfelder ohne `setToolTip`/`setAccessibleDescription`).
- Vorschlag: je Feld ein Satz, wo am Prüfkörper gemessen wird und was die Zahl bewirkt.
- Wirkung beim Kunden: Er weiß nicht, welche Zahl vom Prüfkörper in welches Feld gehört.
- Stand: behoben `74c183721`

### FD-11 Die Felder von Parameter anlegen erklären sich nicht

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `Bearbeiten/Parameter anlegen …`
- Kriterium: V3
- Beleg: Name, Einheit, Unter- und Obergrenze ohne Kurzhilfe und Beschreibung; Fall 003, `02-flaeche-dialog.png`
- Ursache: `app/ui/dialogs.py` (`ParameterDialog`, Felder ohne Satz).
- Vorschlag: je Feld ein Satz, etwa „So heißt das Maß in Ausdrücken, etwa @breite.“
- Wirkung beim Kunden: Wofür Ober- und Untergrenze gut sind, muss er raten.
- Stand: behoben `3a1e6fdf1`; `test_parameter_dialog.py::test_every_field_says_what_it_does_on_both_halves` am Stand davor rot („Name: ohne Satz“), danach trägt jedes Feld einen Satz an Feld, Beschriftung und Beschreibung.

### FD-12 Am Drehfeld eines Zahlenfelds fehlt die Beschreibung für Hilfsmittel

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `drill_hole`
- Kriterium: V3
- Beleg: in jedem Operationsdialog fehlen dem fokussierbaren Drehfeld und dem Haken „Ganzer Körper“ Name und Beschreibung, mit der Maus ist der Satz da; Fall 040, 13 Drehfelder
- Ursache: `app/ui/op_dialog.py` (`_explain` an den Behälter, nicht an `ValueField.spin` und `FeatureSetField.whole`).
- Vorschlag: `_explain` gibt den Satz auch an das innere Feld.
- Wirkung beim Kunden: Ein Bildschirmleser liest am fokussierten Zahlenfeld keine Erklärung.
- Stand: behoben `3a4dd788e`

### FD-13 Material kalibrieren zeigt vorn neun Felder und zwei Absätze

- Art: Einfachheit
- Schwere: mittel
- Funktion: `Bearbeiten/Material kalibrieren …`
- Kriterium: E5
- Beleg: 9 Felder vorn (erlaubt 4), 41 Wörter über dem ersten Feld (erlaubt 25), übersetzt 49–61 (erlaubt 35); Fall 034
- Ursache: `app/ui/dialogs.py` (Überschrift, zwei Absätze, fünf Messwerte, zwei Haken alle vorn).
- Vorschlag: ein Satz, vorn nur, was der Prüfkörper liefert; der Rest unter *Weitere Einstellungen*.
- Wirkung beim Kunden: Wer nur sein Spiel nachtragen will, liest drei Absätze und sieht neun Felder.
- Stand: behoben `74c183721`

### FD-14 Zahlen stehen linksbündig

- Art: Gestaltung
- Schwere: leicht
- Funktion: `Bearbeiten/Material kalibrieren …`
- Kriterium: G3
- Beleg: kein Zahlenfeld der Anwendung ist rechtsbündig; Fall 034
- Ursache: Drehfeldklassen in `app/ui/labels.py` und `NumberSpin` ohne `setAlignment`.
- Vorschlag: rechtsbündig zentral in den Drehfeldklassen.
- Wirkung beim Kunden: Zahlen untereinander stehen nicht Stelle unter Stelle.
- Stand: behoben `746e2eb12`

### FD-15 Operationsdialoge halten das 4er-Raster nicht

- Art: Gestaltung
- Schwere: leicht
- Funktion: `drill_hole`
- Kriterium: G2
- Beleg: Abstand 6 px im Inhalt und in beiden Formularen jedes Operationsdialogs; Fall 040, `surfaces/drill_hole-*.json`
- Ursache: `app/ui/op_dialog.py` (Formulare und Inhalt ohne gesetzten Abstand, Qt-Vorgabe 6).
- Vorschlag: `NORMAL` setzen wie im Kalibrierdialog.
- Wirkung beim Kunden: Der meistbenutzte Dialog wirkt minimal unruhig.
- Stand: behoben `4cc120f79`

### FD-16 Zwei Hauptknöpfe in der Auswahlkarte bei gewähltem Merkmal

- Art: Gestaltung
- Schwere: leicht
- Funktion: `feature.apply`
- Kriterium: G1
- Beleg: „Passende Bausteine …“ und „Übernehmen“ beide in Akzentfarbe; Fall 040, `flaeche-sprachen.png`
- Ursache: `app/ui/selection_operations.py` (`make_primary` am Katalogknopf) neben `panels.py` (*Übernehmen*).
- Vorschlag: Katalogknopf gewöhnlich, solange das Merkmalfenster *Übernehmen* zeigt.
- Wirkung beim Kunden: Er muss lesen, welcher Knopf seine Änderung übernimmt.
- Stand: behoben `f333e5ba7`; der 43er-Satz war am Original 38 rot, darunter die gleichzeitigen Hauptaktionen. Finaler Lauf 037–042: rechte Karte an `move_feature`, `duplicate_feature`, `rotate_feature` und `resize_feature` mit genau einem Akzentknopf, G1 erfüllt, Stufe B G1 `gut_nach_fix` (D4); die Zeile `feature.apply` selbst erreichte der Prüfstand nicht. In welle4 `b86381559`.

### FD-17 Die Suche findet Auf das Bett setzen und Parameter anlegen mit Kundenwörtern nicht vorn

- Art: Verständlichkeit
- Schwere: mittel
- Funktion: `finding.action:place_on_bed`
- Prüfpunkt: 1
- Beleg: „Druckbett“ bringt *Auf das Bett setzen* auf Rang 7; „Variable“ und „Benutzerparameter“ finden *Parameter anlegen* nicht; Fälle 002 und 003, `function.json#search`
- Ursache: `app/core/registry/search.py` (Treffer in der Beschreibung gleich gewertet; Kundenwörter fehlen).
- Vorschlag: Kundenwörter „Druckbett“, „aufs Bett“, „Grundebene“ an `place_on_bed`, „Variable“, „Benutzerparameter“ an *Parameter anlegen*; Rang mit Gegenprobe.
- Wirkung beim Kunden: Wer „Druckbett“ tippt, bekommt Grundkörper statt der Handlung.
- Stand: behoben `8f2c5c4d6`

### FD-18 Fragen in eigenen Worten führen zu Mausbelegungen

- Art: Gestaltung
- Schwere: Vorschlag
- Funktion: `finding.action:place_on_bed`
- Kriterium: I6
- Beleg: „Wie setze ich das Teil auf die Druckplatte?“ bringt die Handlung auf Rang 7, vorn fünf Mausschemata; „Wie lege ich ein Maß an, das ich mehrfach verwende?“ Rang 9
- Ursache: `app/core/registry/search.py` (`request_terms` behält Fragewörter).
- Vorschlag: Frage- und Füllwörter je Sprache aus der Anfrage nehmen.
- Wirkung beim Kunden: Eine Frage führt zu Mausbelegungen statt zur Handlung.
- Stand: behoben `8f2c5c4d6`

### FD-19 Filament und Druck liegt zugeklappt am Ende der Auswahlkarte

- Art: Gestaltung
- Schwere: leicht
- Funktion: `filament.picker`
- Kriterium: Z3
- Beleg: bei gewähltem Körper unter rund 40 Handlungen, erst nach Rollen und Aufklappen; Fälle 040 und 046
- Ursache: `app/ui/selection_operations.py` (`collapsible(..., open_now=False)`).
- Vorschlag: Zuweisung oben als Zeile mit Farbe, oder offen, solange kein Filament zugewiesen ist.
- Wirkung beim Kunden: Mehrfarbdruck ist ein häufiges Ziel, seine Zuweisung liegt am Ende der längsten Liste.
- Stand: behoben `55c856d12`; `test_print_section_place.py` am Stand davor rot, danach steht die Klappe *Filament und Druck* direkt unter den Hauptaktionen mit dem Farbfeld der Zuweisung; Bild hell und dunkel.

### FD-20 Die Maßspalte im Objektbaum schneidet krumme Maße ab

- Art: Gestaltung
- Schwere: leicht
- Funktion: `finding.action:scale_to_fit`
- Prüfpunkt: 9
- Beleg: „253,44 × 190,08 × 12,67 mm“ in 117 px bei 152 px Bedarf; Fall 046
- Ursache: `app/ui/panels.py` (`_size_columns`, Spalte auf `MEASURE_SHARE` gedeckelt).
- Vorschlag: Spalte nach dem Inhalt der sichtbaren Zeilen statt nach festem Anteil.
- Wirkung beim Kunden: Ein eingelesenes Modell mit krummen Maßen zeigt das Maß abgeschnitten.
- Stand: behoben `6209cb930`, `9b6232ff7`, `51a9d0c75`; `test_object_tree_columns.py` am Stand davor rot, danach nimmt die Maßspalte, was die Namen übrig lassen, und die linke Karte wird bis `LEFT_MAX` breiter; Wächter `test_left_card_width_window.py` (`26f33fc8e`) gegen die Mutation rot; nativer Nachweis des Falls „253,44 × …“ im Schlusslauf (Plan Punkt 34).

### FD-21 Jede Fehlermeldung ist ein rohes Systemfenster

- Art: Gestaltung
- Schwere: mittel
- Funktion: `finding.action:place_on_bed`
- Kriterium: Z5
- Beleg: Meldungen eines `AppError` erscheinen als `QMessageBox` mit Windows-Warnsymbol und Titel „Das hat so nicht funktioniert“; Fälle 028, 029, 046–051
- Ursache: `app/ui/dialogs.py` (`show_error` baut `QMessageBox` mit `setIcon(Warning)`).
- Vorschlag: eigener Meldungsdialog im Hausstil — Titel, Ursache, Handlungen als Knöpfe, Symbol aus dem eigenen Satz. Zu Z2 (E-17): Eine Fehlermeldung mit Handlung, die auf eine Kundenhandlung antwortet, darf modal bleiben (Ausnahme in Konzept §4, Entscheidung Koordinator); eine ohne Handlung bleibt ein Fund.
- Wirkung beim Kunden: Ein Systemfenster mit Warndreieck bricht den Stil; Z5 erlaubt im Kundenweg keines.
- Stand: behoben `4dee5f9bc`

### FD-22 Eingabe- und Farbfragen sind rohe Systemfenster

- Art: Gestaltung
- Schwere: mittel
- Funktion: `meldung:_pick_colour`
- Kriterium: Z5
- Beleg: acht Aufrufe von `QInputDialog.getText`/`getItem` und `QColorDialog.getColor` im Kundenweg: Filamentfarbe und -platz (`filament_picker.py`), Druckfarbe (`print_settings_dialog.py`), Dienstadresse (`install_dialog.py`), Modell-Adresse, Gegenstück und Lagerspule (`main_window.py`), Maßwert einer Bedingung (`sketch_editor.py`); gemeldet beim Fix von FD-21
- Ursache: Für Eingabe und Farbwahl gibt es keinen eigenen Dialog im Hausstil; FD-21 deckte nur Meldungen ab.
- Vorschlag: Eingabe am Ort, wo es geht, sonst ein Eingabedialog im Hausstil auf der Grundlage von `message_dialog`; Farbwahl über den eigenen Farbwähler des Filamentlagers.
- Wirkung beim Kunden: Mitten im Ablauf ein Systemfenster in anderem Stil, bei der Farbe der Windows-Farbdialog.
- Stand: behoben `54464f2be`

### FD-23 Die Karten halten das 4er-Raster nicht

- Art: Gestaltung
- Schwere: leicht
- Funktion: `finding.action:place_on_bed`
- Kriterium: G2
- Beleg: zehn Kartenlayouts in `panels.py` mit Qts Abstand 6; der Wächter aus FD-15 nimmt sie aus, weil `OverlayHost` ihre Höhen teilt
- Ursache: `app/ui/panels.py` (Layouts der Karten ohne gesetzten Abstand).
- Vorschlag: Raster setzen und die Höhenrechnung von `OverlayHost` und `natural_height` mitziehen; Ausnahme im Wächter streichen.
- Wirkung beim Kunden: Die Karten wirken neben den Dialogen minimal unruhiger.
- Stand: behoben `26d8aefb8`

### FD-24 Erfolgsmeldungen der Freischaltung sind modal

- Art: Gestaltung
- Schwere: mittel
- Funktion: `meldung:_online_completed`
- Kriterium: Z2
- Beleg: Nach erfolgreicher Freischaltung und Abmeldung erscheint ein modales Meldungsfenster; Z2: „Erfolg und Hinweis erscheinen nie als Meldungsfenster“; gemeldet beim Fix von FD-21
- Ursache: `app/ui/dialogs.py` (Erfolgsmeldungen der Freischaltung über `inform`, modal).
- Vorschlag: Erfolg nicht-modal am Ort oder in der Statusleiste, im Hausstil; was der Kunde danach tun kann, als Handlung dabei.
- Wirkung beim Kunden: Ein Erfolg hält das Fenster an, bis er weggeklickt ist.
- Stand: behoben `54464f2be`

### FD-25 Der Objektbaum verlangt mit einem Körper mehr Mindesthöhe, als er braucht

- Art: Gestaltung
- Schwere: leicht
- Funktion: `finding.action:place_on_bed`
- Prüfpunkt: 9
- Beleg: am echten Fenster mit einem Körper Mindesthöhe 183 gegen Wunschhöhe 81 Punkte; die Karte zeigt Leere unter dem Körper; gemeldet beim Fix von FD-23 (`fix-karten-raster.md`)
- Ursache: Die Mindestzeilenzahl des Objektbaums gilt auch, wenn weniger Zeilen da sind; `fenster.md` verlangt, dass die Mindesthöhe einer Karte ihre Wunschhöhe nie übersteigt.
- Vorschlag: Mindesthöhe aus den vorhandenen Zeilen, höchstens die Wunschhöhe; Test an einem und an vielen Körpern.
- Wirkung beim Kunden: Leere Fläche im Objektbaum, die der Ansicht Platz nimmt.
- Stand: behoben `96a4638b3`

### FD-26 Parameter anlegen bleibt ohne Freischaltung offen

- Art: Fehler
- Schwere: mittel
- Funktion: `Bearbeiten/Parameter anlegen …`
- Prüfpunkt: 18
- Beleg: in `sale_without_trial` und `needs_activation` offen, der Klick endet in einer Absage; Nachmessung D0-P2, Fälle `nach-lizenz` 007 und 008, Bild `n3/008-MessageDialog.png`
- Ursache: `main_window.py` behält die Aktion nicht, `_update_actions` kann sie nicht sperren; `action_add_parameter` fragt `change_lock` nicht. FD-5 erfasste diesen Fensterbefehl nicht.
- Vorschlag: Fensterbefehle, die ändern, fragen dieselbe Quelle `change_lock`; ein Wächter über alle ändernden Fensterbefehle.
- Wirkung beim Kunden: Ein Menübefehl, der in der Demo erst nach dem Klick absagt.
- Stand: behoben `660501d8f`

### FD-27 Eine graue Befundhandlung beschreibt sich mit ihrer Nebenwirkung statt mit dem Sperrgrund

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `finding.action:place_on_bed`
- Kriterium: V3
- Beleg: während der Rechnung grau, die zugängliche Beschreibung trägt den Nebenwirkungstext; `probe_fault_lock.json` (D0-P2)
- Ursache: `panels.py` setzt bei der Sperre nur die Kurzhilfe, nicht die Beschreibung.
- Vorschlag: Sperrgrund als Kurzhilfe und Beschreibung, solange gesperrt.
- Wirkung beim Kunden: Ein Bildschirmleser liest, was der Knopf täte, nicht warum er nicht geht.
- Stand: behoben `660501d8f`

### FD-28 Die Maßgruppe nimmt ohne Freischaltung Eingaben an

- Art: Fehler
- Schwere: mittel
- Funktion: `resize_hole`
- Prüfpunkt: 18
- Beleg: in beiden gesperrten Zuständen bleibt das Feld der Maßgruppe offen, erst *Übernehmen* ist grau; bei `needs_activation` nennt der Satz keinen Menüweg (D0-P2, Bild `q8-nach-uebernehmen.png`)
- Ursache: `placement_flow.py` sperrt nur *Übernehmen*, nicht den Eingang.
- Vorschlag: Eingang und Übernehmen sperren mit Grund und Ausweg aus `change_lock`.
- Wirkung beim Kunden: Er tippt ein Maß, das nicht übernommen werden kann.
- Stand: behoben `660501d8f`

### FD-29 Am echten Fenster fehlen an einer gesetzten Bohrung Bohrung ändern und Zum Langloch ziehen

- Art: Fehler
- Schwere: leicht
- Funktion: `resize_hole`
- Prüfpunkt: 1
- Beleg: am echten Fenster verborgen, ohne Fenster sichtbar (`n5-echt.out`, `n5-offscreen.out`, D0-P2); am echten Fenster nachgestellt und zugeordnet in `output/konsolidierung-2026-10-12/fix-bohrung-sichtbar.md`
- Ursache: gewollt nach RM-199 (`FeaturePanel.set_measuring`): Die Maßgruppe der Handlung steht im Bild, rechts ist ihr Kopf deshalb verborgen; die Zeile startete an einer gesetzten Bohrung, und der Prüfstand fand die Handlung nur rechts.
- Vorschlag: die Zeile an einer erkannten Bohrung beginnen lassen (`erkannte_bohrung.netz`); der Prüfstand fragt die Maßgruppe im Bild nach ihrer Handlung.
- Wirkung beim Kunden: Keine Sackgasse: Die Maße der Bohrung stehen nach dem Klick im Bild, *Bohrung ändern* findet die Suche der Karte.
- Stand: behoben `67058d32d`, Prüfstand `0b1e61346`

### FD-30 Zwei Sperrgründe nennen keinen Ausweg

- Art: Verständlichkeit
- Schwere: mittel
- Funktion: `finding.action:place_on_bed`
- Kriterium: V5
- Beleg: „Aktivieren Sie diesen Rechner einmal online …“ und „Erst nach der Berechnung …“ nennen keine bedienbare Menüzeile und keinen offenen Knopf (D0-P2)
- Ursache: Sätze der Sperre ohne Weg.
- Vorschlag: den Weg nennen, etwa die Menüzeile der Freischaltung; in allen Sprachen neu übersetzt.
- Wirkung beim Kunden: Er liest, dass es nicht geht, aber nicht, was er tun kann.
- Stand: behoben `660501d8f`

### FD-31 Übernehmen der Maßgruppe ist vor der ersten Eingabe grau ohne Grund

- Art: Einfachheit
- Schwere: mittel
- Funktion: `resize_hole`
- Kriterium: E7
- Beleg: freigeschaltet, nach der Auswahl einer Bohrung; *Übernehmen* grau, ohne Kurzhilfe und Beschreibung (Fix FD-26 bis FD-30, `fix-sperre-vollstaendig.md`)
- Ursache: Der Knopf wartet auf eine Änderung und sagt es nicht.
- Vorschlag: ein Satz, der das erste Feld als Weg nennt; der Prüfstand zählt einen offenen Feldtitel derselben Fläche als Ausweg (Entscheidung Koordinator).
- Wirkung beim Kunden: Ein grauer Knopf ohne Satz sieht aus wie gesperrt.
- Stand: behoben `827d559cc`, `3ecee68ce` (Maßgruppe), `ce8390478` (Merkmalfenster und Flächenkarte), `38ab43c4f` (Operationsdialog); `test_measure_card_first_change.py`, `test_feature_first_change.py` und `test_operation_dialog_change.py` je am Stand davor rot, danach grün: *Übernehmen* ist bis zur ersten Änderung grau mit „Erst „{Feld}“ ändern, dann übernehmen.“ aus einer Quelle (`app/ui/first_change.py`).

### FD-32 Der Sperrgrund steht im Reiter Auswahl zweimal

- Art: Gestaltung
- Schwere: leicht
- Funktion: `resize_hole`
- Kriterium: E5
- Beleg: ohne Freischaltung unter dem Suchfeld und im Merkmalfenster derselbe Satz (Fix FD-26 bis FD-30)
- Ursache: FD-5 setzte den Satz an beiden Flächen.
- Vorschlag: die Zeile unter dem Suchfeld gilt für den Reiter; das Merkmalfenster trägt den Grund nur an seinen grauen Elementen.
- Wirkung beim Kunden: Derselbe Satz zweimal lenkt vom Weg ab.
- Stand: behoben `4170f587b`, `e5a172a4a`; Nachweis `6c413f383` (`test_lock_reason_once.py`, am Stand vor `4170f587b` rot mit zwei Zeilen, danach genau eine).

### FD-33 Jede Aktualisierung der Fensterbefehle fragt nach dem exakten Kern

- Art: Leistung
- Schwere: leicht
- Funktion: `resize_hole`
- Prüfpunkt: 6
- Beleg: im Profil 3,5 von 9,3 ms je `_update_actions` in `importlib.find_spec` über `exact_kernel_present()` (Fix FD-26 bis FD-30)
- Ursache: Die Anwesenheit des Kerns wird bei jedem Aufruf neu gesucht, obwohl sie sich im Prozess nicht ändert.
- Vorschlag: je Prozess einmal ermitteln, an der Quelle; Messung vorher und nachher.
- Wirkung beim Kunden: Jede Auswahl und jede Handlung kostet unnötig Zeit im Hauptfaden.
- Stand: behoben `ca9f933a7`; nachgemessen mit CPU-Zeit im Wechsel: die Frage rund 1 000 µs → unter der Auflösung, `_update_actions` 2,97–3,44 → 2,08–2,60 ms; Wächter `test_kernel_switch.py::test_the_kernel_is_looked_up_once_per_process`.

### FD-34 Eine erkannte Bohrung holt Bohrung ändern ins Bild, rechts bleibt Merkmal verschieben scharf

- Art: Fehler
- Schwere: mittel
- Funktion: `resize_hole`
- Prüfpunkt: 1
- Beleg: am echten Fenster nach der Auswahl einer erkannten Bohrung (`fix-zeile-bohrung.md`, neuer Punkt 1)
- Ursache: `request_in_view` holt die Maßgruppe ins Bild, ohne ihre Handlung scharf zu machen, wie es der Knopf *Im Bild einstellen* tut.
- Vorschlag: ein Weg für Auswahl und Knopf; die Handlung im Bild ist auch rechts die scharfe.
- Wirkung beim Kunden: Rechts steht offen eine andere Handlung als die, deren Maße er im Bild sieht.
- Stand: offen RM-737; Hauptteil behoben `aa1bae3ba` (rechts ist die Handlung im Bild scharf, *Merkmal verschieben* nur noch zugeklappt); F5 `90600562c` lässt die Pfeile des Griffs erst ab der Knopfreichweite beginnen. Rest: Die Verschiebepfeile des Merkmals stehen neben der Maßgruppe scharf an derselben Bohrung (Stufe B, 02, 016, 019); dafür hat kein Paket einen Fix gebaut, ob `90600562c` ihn trägt, urteilt der Schlusslauf (Plan Punkt 26).

## D0: Entwurf neuer Belege und Funde aus den Fixen (FD-35 bis FD-85)

Nummern vom Koordinator vergeben; Originalurteile und Originalfunde bleiben erhalten. Nachweis für den Stand ist der finale 48-Fall-Lauf auf `2ec37b23b` (Fortsetzung 03) mit den Stufe-B-Urteilen beider Prüfer.

### FD-35 Bettaktion beschreibt Anheben als Senken

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: finding.action:place_on_bed
- Prüfpunkt: 8
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/002/02-flaeche.png rechts unter Auf das Bett setzen: „Senkt den Körper bis auf das Bett“ bei 10 mm Unterstand; 03-uebernommen.png und function.json#result.metrics: Unterseite z=0. V4-Fall002 sagt vor dem Klick ausdrücklich 10 mm Anheben voraus.
- Ursache: app/core/action_effects.py:133, SIDE_EFFECTS[place_on_bed], setzt mit Senkt und den fünf entsprechenden Katalogwerten eine Bewegung nach unten voraus; tatsächlich hängt die Richtung von der Ausgangslage ab.
- Vorschlag: Richtungsneutraler Satz „Setzt den Körper auf das Bett; seitlich bleibt er, wo er ist.“ und fünf Katalogwerte gemäß textfix-fd35-fd43-entwurf.md; oberhalb/unterhalb/auf dem Bett prüfen. Kein Geometriefix.
- Wirkung beim Kunden: Der Kunde liest eine falsche Bewegungsrichtung; das belegte geometrische Ergebnis selbst stimmt.
- Stand: behoben `2ad0206ed`; `tests/test_action_texts.py` war am Original 16 rot. Finaler Lauf 002, 005 und 043–048 zeigen „Setzt den Körper auf das Bett. Seitlich bleibt er, wo er ist.“, Stufe B V4 `gut_nach_fix` (D8). In welle4 `ac28ecbb2`.

### FD-36 Entfernen-Hinweis überspringt das notwendige Abbrechen

- Art: Verständlichkeit
- Schwere: mittel
- Funktion: resize_hole
- Prüfpunkt: 7, E7, V5
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/001/04-fehlfall.png: 0,10 mm unter 0,20-mm-Grenze; Maßgruppe bietet Abbrechen, „Merkmal entfernen“ rechts grau. function.json#messages/#steps. Fix-Einzelfall F:/tmp-suche/fix-probe-feedback-codex/native-pinned/cases/001/04-fehlfall.png; process.json Exit0.
- Ursache: FeaturePanel._removal_way nennt die Entfernen-Zeile auch während eines begonnenen Maßentwurfs, obwohl _settle_lock sie dann sperrt. Ohne begonnenen Entwurf ist der direkte Weg richtig.
- Vorschlag: Begonnenen Entwurf unterscheiden; zuerst Abbrechen und danach den tatsächlichen Entfernen-Titel nennen. Fixbericht fix-probe-feedback-codex.md: vier Produktzeilen, sechs Kataloge, 6 vorher rot/18 Gegenfälle grün, danach 24 grün; echte DE-Aufnahme bestätigt den Text.
- Wirkung beim Kunden: Wer dem bisherigen Hinweis folgt, erreicht einen gesperrten Knopf; der erforderliche erste Schritt fehlt.
- Stand: behoben `c75ece14b`; der Hinweis nennt zuerst *Abbrechen*, Rottest am Stand davor rot (6); den zweiten Schritt des Wegs (*Merkmal entfernen* nach *Abbrechen*) geht der Prüfstand seit `3a70b3806` mit (`tools/function_way.py`); nativer Nachweis im Schlusslauf (Plan Punkt 19).

### FD-37 Flächenaufnahme einer Sofortaktion entsteht erst nach ihrer Wirkung

- Art: Fehler
- Schwere: mittel
- Funktion: finding.action:place_on_bed
- Prüfpunkt: 9, 19
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/005/flaeche-zoll.png, 010/flaeche-skalierung.png, 017/flaeche-dunkel.png, 020/flaeche-bewegung.png: Verlaufsschritt2 und leerer Bericht; jeweiliges function.json#steps enthält die wirksame Befundaktion in phase=weg.
- Ursache: Prüfstand: phase_surface führte sämtliche path_steps einschließlich des finalen wirksamen Zielklicks vor der Flächenmessung aus.
- Vorschlag: Walk nur für diesen Flächenzweck nach allen Wegklicks und geprüfter Trefferidentität vor dem Zielklick halten. Normale Aktionswege bleiben wirksam. Kopflose Rot/Grün- und Zieltreffer-Gegenproben im Prüfstandfixbericht; nativer Vollnachweis offen.
- Wirkung beim Kunden: Die beabsichtigte Kundenfläche wird nicht beurteilt; der Bericht könnte eine ungemessene Variante freigeben. Kein belegter Produktfehler der Bettkorrektur.
- Stand: behoben `6d5734da5`; `tests/test_function_surface_timing.py` war am Original 4 rot. Finaler Lauf 005, 010, 017, 020 und 043–048: Aufnahme vor dem Zielklick, Körper noch unter dem Bett, Befund und Knopf im Bild, Verlauf ein Schritt; Stufe B Zweitprüfer P9 `gut_nach_fix` (D8). Dieselbe Aufnahmelage an `report.action` führt FD-115. In welle4 `433da64bc`.

### FD-38 E7 verwirft einen ausdrücklich gemessenen Rechenausweg

- Art: Fehler
- Schwere: mittel
- Funktion: finding.action:place_on_bed
- Prüfpunkt: 2, E7
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/002/function.json#messages: kind=sperrgrund, way_out=true, „… wieder frei, sobald die Berechnung fertig ist.“; 04-fehlfall.png zeigt Wird neu berechnet/Voriger Stand/grauen Knopf. Automatik nennt Meldung ohne Handlung.
- Ursache: Prüfstand: E7 verlangt pauschal actions; der bei V5 erlaubte und als way_out gemessene Rechenausweg wurde dort nicht berücksichtigt.
- Vorschlag: Nur explizit belegte Auswege an Sperrgrund/Grenzablehnung akzeptieren. Echte Meldungen ohne Handlungen bleiben auch bei beliebigem way_out=true rot; entsprechende Gegenproben erhalten.
- Wirkung beim Kunden: Falscher schwerer Sackgassenbefund in der Abnahme; die gezeigte Berechnungssperre erklärt bereits ihren Rückweg.
- Stand: behoben `6d5734da5`; `tests/test_function_surface_timing.py` (darin `test_dead_ends_respect_a_measured_way_out`) war am Original rot. Finaler Lauf 002: E7 erfüllt, der gemessene Rechenausweg zählt, Stufe B E7 `gut_nach_fix` beider Prüfer (D8). In welle4 `433da64bc`.

### FD-39 Fehlfallbild wird erst nach Escape aufgenommen

- Art: Fehler
- Schwere: mittel
- Funktion: Bearbeiten/Parameter anlegen …
- Prüfpunkt: 7, E7, V5
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/003/04-fehlfall.png zeigt nur das Hauptfenster; function.json#messages enthält die Ablehnung von „breite außen“, closed_by_escape: phase=fehlfall, times=1; kein 04-fehlfall-dialog.png.
- Ursache: Prüfstand: run_steps las die Meldung, schloss anschließend den modalen Parameterdialog mit Escape und erstellte erst danach die Fehlfallaufnahme.
- Vorschlag: Bild im selben Leseschritt wie den Meldungstext vor Escape erfassen; den tatsächlichen Meldungs-/Korrekturweg anschließend unabhängig bewerten. Aufnahmefix allein schließt den automatischen E7/V5-Produktverdacht nicht.
- Wirkung beim Kunden: Der sichtbare Fehlerzustand und sein Ausweg bleiben im Bericht unbewiesen.
- Stand: behoben `6d5734da5`; `tests/test_function_surface_timing.py` war am Original rot. Finaler Lauf 003: `04-fehlfall-dialog.png` zeigt den offenen Parameterdialog mit der Ablehnung vor Escape, beide Prüfer bestätigen (D10). Dass die Meldung selbst keine Handlung trägt (P7, E7, V5 offen), ist ein Produktbefund, den FD-39 nicht umfasst. In welle4 `433da64bc`.

### FD-40 Fremder Generierungsdialog verunreinigt spätere Sprachflächen

- Art: Fehler
- Schwere: mittel
- Funktion: finding.action:place_on_bed
- Prüfpunkt: 9, 19
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/043/flaeche-de-finding.action_place_on_bed-53db7bc0-dialog.png zeigt Beschreibung/Bild/ComfyUI und fremden Projektkontext; entsprechendes Hauptbild zeigt korrekt den Würfel am Bett. D8-Ledger:38 solche Zusatzpfade,25 unterschiedliche Inhalte. Weitere tool:analysis/tool:layers/command:edit.auto_split bestätigt der Zweitprüfer.
- Ursache: Prüfstand: LanguageFlow wechselte nach phase_surface die Startszene; StepMachine räumte nur laufende modale Aufrufe ab. Der nichtmodale Generierungsdialog blieb geöffnet. windows_to_picture fotografierte die tatsächlich sichtbaren Fenster korrekt.
- Vorschlag: Nach jeder Sprachfläche echten Escape-Rückweg an sichtbaren Nebenfenstern durchführen; bei verbleibendem Fenster Teilfläche mit bench.surface_cleanup_failed rot beenden, bevor das nächste Projekt öffnet. Keine Fremdbilder filtern und keine direkten reject-Abkürzungen.
- Wirkung beim Kunden: Spätere Dialogbilder gehören nicht zur benannten Handlung; ihre Texte und Maße dürfen deren Beurteilung nicht tragen. Kein nachgewiesener falscher Produktaufruf.
- Stand: behoben `6d5734da5`; `cleanup-baseline-red` war am Original 2 rot. Finaler Lauf 043–048: an `place_on_bed` kein fremdes Nebenfenster, Dialogbilder nur an Zeilen, die einen Dialog öffnen; Stufe B Zweitprüfer P9 `gut_nach_fix` (D8). In welle4 `433da64bc`.

### FD-41 Native Sprachmessung bricht bei der Kontrastaufnahme ab

- Art: Stabilität
- Schwere: schwer
- Funktion: Bearbeiten/Parameter anlegen …
- Prüfpunkt: 9, G6
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/032/process.json,034/process.json,041/process.json: Exit3221225477, kein Timeout;14/2/7 gespeicherte Sprachteilflächen. Startmarken filament.section/create_label/pin_for_bore. Stacks bemerken Fehler in Qt-Arbeiter/QCompleter; Originalabbildungen und Teilprotokolle bleiben unverändert.
- Ursache: Prüfstandverdacht inzwischen an Kontrastcapture eingegrenzt: top.grab() berührt das gesamte Fenster mit nativer 3D-Fläche. Weglassen verhindert bisher den Abbruch; Ersatz durch screen.grabWindow liefert laut Fixagent inzwischen drei Originalsequenzen plus einen zweiten vollständigen Lauf mit Exit0. Ursprüngliche Stackorte beweisen keine frühere Beschädigungsursache; keine Hardwarebehauptung.
- Vorschlag: Echte Schirmaufnahme für unveränderte Farbproben verwenden; reproduzierende Gegenprobe, wiederholte native Sprachfolgen, auswertbare Kontrastwerte, Abschlussauswahl und Commit dokumentieren. Ursachenbehebung erst nach dem kompletten Nachweissatz freigeben.
- Wirkung beim Kunden: Sprachprüfung endet vorzeitig; ihre Vollständigkeit und Kontrastabnahme fehlen. Schwere bezieht sich hier auf den blockierenden Prüfstand, nicht auf einen nachgewiesenen Kundenabsturz.
- Stand: behoben `6d5734da5`; am Original nativ reproduziert (D10/en Exit 3221225477, im Ursprungslauf 032, 034 und 041), ein kopfloser Rottest ist für den nativen Abbruch nicht möglich. Finaler Lauf: alle Sprachfälle 031–048 Exit 0 samt Kontrastaufnahme, darunter die alten Abbruchfälle 032, 034 und 041; Stufe B G6 `gut` (D10). In welle4 `433da64bc`.

### FD-42 Gegenstücke setzen zeigt sechs unabhängige Vorderseitenfelder

- Art: Einfachheit
- Schwere: mittel
- Funktion: Erzeugen/Bausteine/Gegenstücke setzen …
- Prüfpunkt: E5
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/031/flaeche-de-Erzeugen_Bausteine_Gegenstücke_setzen-5b902f72-dialog.png und surfaces/Erzeugen_Bausteine_Gegenstücke_setzen-5b902f72.json#fields: Paar,Durchmesser,Länge,Form,Spiel,Fase jeweils front=true; auch ES/IT/PT. Keine Vektorkomponenten.
- Ursache: counterpart_dialog baut sämtliche Pair.shared-Felder in das vordere Formular und ignoriert vorhandenes ParamSpec.placement. Form, Spiel und Fase sind im Schema bereits advanced.
- Vorschlag: Vorn Paar und gewöhnliche Maße; vorhandene advanced-Felder unter Weitere Einstellungen mit aktueller Zusammenfassung. ContentHeight/expanded_width und natürlich bemessene Breite verwenden, alle Werte/Paare/Tastaturwege in sechs Sprachen erhalten.
- Wirkung beim Kunden: Für die einfache Gegenstückaufgabe muss der Kunde sechs fachliche Werte gleichzeitig überblicken; E5 erlaubt höchstens vier.
- Stand: behoben `d06fb300b`; `tests/test_counterpart_front.py` war am Original 31 rot. Finaler Lauf 031–036: drei Felder vorn, E5 erfüllt, Stufe B E5 `gut_nach_fix` (D10). In welle4 `9b3e44120`.

### FD-43 Übersetzte Handlungsaufzählungen enthalten deutsches und

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: paint_slot
- Prüfpunkt: 9, V1
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/033/flaeche-es-paint_slot-9865a109.png und036/flaeche-pt-paint_slot-9865a109.png rechts; „Duplicar característica und …“. Weitere drill_hole-Bilder039/es,040/fr,041/it,042/pt sowie clear_filament034/fr,036/pt. Ein gemeinsamer Textfund.
- Ursache: app/ui/panels.py:_and_then (8144) verknüpft die von _folded bereits übersetzten Titel mit vier fest eingebauten deutschen Trennern in8157–8160. Vorhandenes Muster main_window.py:2903 und Schlüssel tr(und mit Leerzeichen) sind bereits in allen Katalogen vorhanden.
- Vorschlag: Einmal connector=tr(" und ") innerhalb _and_then bestimmen, Suche/rpartition und beide Ergebniswege damit bilden. Bestehende Präfixkürzung erhalten. Zwei und drei Titel in allen sechs Sprachen samt Laufzeitwechsel prüfen. Kein neuer FD43-Katalogschlüssel, enger Entwurf textfix-fd35-fd43-entwurf.md.
- Wirkung beim Kunden: Die sichtbare Auswahlkarte mischt Sprachen; kein benannter Projektinhalt.
- Stand: behoben `2ad0206ed`; `tests/test_action_texts.py` war am Original rot (gefaltete Handlungen in fünf Übersetzungen). Finaler Lauf 031–036: die Aufzählung endet auf „and/y/et/e/e“, Stufe B Zweitprüfer V1 `gut_nach_fix`, der Erstprüfer bestätigt (D10). In welle4 `ac28ecbb2`.

### FD-44 Skizzenfehler zeigt Ursachencode und verdeckt den Korrekturweg

- Art: Verständlichkeit
- Schwere: mittel
- Funktion: finding.action:sketch.pick_plane
- Prüfpunkt: 7, 8, 19, V5
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/043/flaeche-de-finding.action_sketch.pick_plane-ad8b805d-dialog.png:380×268px, Grund:points_are_on_one_line; Korrekturzeilen aus surfaces/finding.action_sketch.pick_plane-ad8b805d.json#texts nicht sichtbar. Szene ebene_durch_linie.netz.p3d:Quader40×30×20; Tasche2; Ebene through:0,0,20;10,0,20;20,0,20. Zwei getroffene Klicks Befund→Eine andere Ebene wählen. -dialog-2.png ist fremd und zählt nicht.
- Ursache: Die absichtlich kollinearen Ebenenpunkte sind korrekt ungültig. spoken_values/value_line gibt den internen reason roh aus; nachgereichter ErrorNotice wird in show_refusal sichtbar, aber die Dialoghöhe nicht passend nachgeführt. Verständlicher Satz für denselben Grund existiert im Skizzeneditor.
- Vorschlag: Vorhandene verständliche Erklärung zentral wiederverwenden/eng zuordnen; Fehlerbereich und vorhandene Korrekturtexte mit bestehendem ContentHeight-/Refitweg vollständig sichtbar machen, manuelle Größe und erreichbaren Scrollweg erhalten.
- Wirkung beim Kunden: Die Ursache wird technisch statt handlungsnah erklärt, und der angebotene vorhandene Korrekturweg ist im aufgenommenen Fensterzustand unsichtbar. Kein Geometriefehler und keine Behauptung, die Anwendung hätte grundsätzlich keine Korrekturhandlung.
- Stand: behoben `2e4752521`; die Regression war am Original 18 rot. Finaler Lauf 043–048: verständlicher Grund statt `points_are_on_one_line`, die Korrekturzeilen stehen ganz im Dialog (043 gelesen), Stufe B „FD-44 sichtbar verbessert“ (D8); Wege nur als Satz führt FD-95. In welle4 `27a18b48c`.

### FD-45 Merkmalslisten reservieren Höhe für nicht vorhandene Einträge

- Art: Gestaltung
- Schwere: leicht
- Funktion: pattern_feature
- Prüfpunkt: 9, 19, Z6
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/037/flaeche-de-pattern_feature-2d8cbcf5-dialog.png:380×503px, eine Zeile in≈287×224px Liste,≈200px leer. group_pattern-5f312f3f-dialog.png:380×358px,sechs Zeilen≈96px in≈191px Liste. Alle sechs Sprachbilder bestätigen denselben Listenleerraum; Fehlerzusatztexte getrennt.
- Ursache: Gemeinsames FeatureSetField-QListWidget orientiert seine Höhe nicht an der tatsächlichen Zeilenzahl; Mindest-/Maximalhöhe und Qt-Größenhinweis reservieren zu viel Listenraum.
- Vorschlag: Listenhöhe aus vorhandenen Zeilen, Zeilenhöhen, Rahmen und Innenabständen; bei vielen Einträgen begrenzen und rollen. Nach Einfügen/Schrift-/DPI-Wechsel nachziehen, keine feste deutsche Pixelhöhe. Ziel im DE-Einzelfall etwa40–48px statt224px.
- Wirkung beim Kunden: Unnötige Leere macht den Dialog länger und verschiebt weitere Felder/Knöpfe nach unten; keine exakt verdeckte Modellfläche aus getrenntem Dialogbild behauptet.
- Stand: behoben `2e4752521` (Listenreserve), `43113904f` (Anfangsmessung in der endgültigen Breite), `6462013cd` (Klappe ohne vorläufigen Rollbalken); `test_operation_dialog_height.py` und `test_operation_dialog_flap_height.py` je am Stand davor rot (bis 28 Punkte leer über den Knöpfen), danach hat kein Operationsdialog in sechs Sprachen einen Streifen; nativer Nachweis mit Systemschrift im Schlusslauf (Plan Punkt 12).

### FD-46 Rechte Kartenbreite wächst allein mit dem Fensteranteil

- Art: Gestaltung
- Schwere: leicht
- Funktion: resize_hole
- Prüfpunkt: 9, 19, Z6
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/037/flaeche-de-duplicate_feature-66547dd4.png:rechte Karte≈539px; cases/007/flaeche-skalierung.png≈479×752px. Größter gemessener Knopftext im Sechssprachenvergleich154px. Koordinator bestätigt Quellformel25%Fenster,Maximum540:bei2560px tatsächlich540. D8 nach Bettsetzen nur540×122px, darunter freie Ansicht.
- Ursache: Anfangsbreite wird aus Fensterquote bis540px abgeleitet, statt aus Inhalt/Schrift. Laut Koordinator ist keine gespeicherte Benutzerbreite vorhanden, nur CardPlace-Lage. Die Reserve einzelner Texte allein bestimmt noch nicht das Minimum aller Felder.
- Vorschlag: Natürlichen Vorderseiten-/Feld-/Schriftbedarf und vorhandene Mindestbedarfe verwenden; Bildschirmgrenzen und bewusst gewählte Nutzergröße bewahren. Rund400px Standardschrift nur als Vergleichskandidat, nicht universelle harte Breite; sechs Sprachen,Zoll/große Werte/Großschrift prüfen.
- Wirkung beim Kunden: Kurze Inhalte können unnötig 3D-Fläche überlagern; im kleinen D4-Beispiel könnte ein nachgewiesen passender400px-Kandidat≈59.400px² freigeben. Keine Behauptung einer vollständig verlorenen rechten Spalte in D8.
- Stand: behoben `11f44ba88`; `tests/test_card_content_width.py` war am Original rot. Finaler Lauf 001 (2560) und 007 (1920): rechte Karte je etwa 358 px statt 540 und 479 px, Stufe B Zweitprüfer P9 `gut` mit gleicher Breite (D4). In welle4 `e68ca22cb`.

### FD-47 Messfläche trifft Nachbarkarte statt aktive Maßgruppe

- Art: Fehler
- Schwere: mittel
- Funktion: resize_hole
- Prüfpunkt: 2, 8, E5, V3
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/001/function.json#texts/#fields/#layout:ab Zeilen2558/2760/3082 _SelectionPage; Bild02-flaeche.png zeigt aktive Maßgruppe mit vier Feldern. Sprachprotokolle u.a.move_feature/duplicate_feature/resize_feature melden fremde Maßgruppen.
- Ursache: Vom Fixagenten bestätigt: tools/function_surface.py:surface_for ignorierte feature:-Zielart und fiel auf die Auswahlseite zurück. Dadurch stammen Einleitung/Feld-/Layoutzahlen nicht ausschließlich von der bedienten Fläche.
- Vorschlag: Nur bei passender öffentlicher feature_panel.measure_op und sichtbarem measure.apply deren eigene Elternkarte wählen; sonst tatsächlichen Zielkopf und eigene Elternzeile. Eine fremde Maßgruppe ausdrücklich ausschließen.
- Wirkung beim Kunden: Falsche Wörter-/Feldzählung und falsche Zielflächen können Funktionen unberechtigt rot oder grün erklären; Produktbeurteilung der Maßgruppe bleibt ohne neue Aufnahme offen.
- Stand: behoben `6d5734da5`; `feature-red` war am Original 5 rot. Finaler Lauf 001, 004, 007, 016, 019 und 037–042 messen die eigene `_MeasureCard` (8 von 8 Feldern, vorn 3), Stufe B E5 und V3 `gut_nach_fix` beider Prüfer, der Zweitprüfer sieht keine Fremdflächenmessung mehr (D4). In welle4 `433da64bc`.

### FD-48 Änderungsprobe liest noch das alte Importergebnis

- Art: Fehler
- Schwere: mittel
- Funktion: resize_hole
- Prüfpunkt: 12
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/001/function.json#revise (Zeilen3935–3972):menue und doppelklick mit ursprünglichen params src1/unit/place_on_bed/centre statt resize_hole; history_before1,history_after2. Automatik meldet Verlauf gewachsen beim Ändern. Neuer eigener Autorenbeleg F:/tmp-suche/probelauf-zwei-pruefstand-fix-codex/fd48-native-reviewfix/cases/001/function.json#revise/#steps und review-native-reading.log: beide Wege tippen tatsächlich 8,8; typed_values und params_after tragen diameter8.8, Verlauf jeweils2→2.
- Ursache: Vom Fixagenten bestätigt: phase_revise wartete nur auf idle, obwohl last_result noch zum vorherigen Import gehörte. Die Werte- und Verlaufsbasis wurden vor dem fertigen neuen Ergebnis gelesen.
- Vorschlag: Nach Vorschau und erfolgreichem run_steps ein wirklich neues last_result sowie die erwartete Verlaufslänge abwarten, erst danach Werte vergleichen. Verweigerte Übernahme als roten Gegenfall erhalten.
- Wirkung beim Kunden: Falscher schwerer Änderungsfund im Prüfbericht; aus diesen alten Parametern folgt kein belegter Kundenfehler des nachträglichen Änderns.
- Stand: behoben `6d5734da5`; `feature-red` war am Original rot. Finaler Lauf 001: P12 erfüllt, beide Wege tippen 8,8 mm, Verlauf 2 → 2, Stufe B P12 `gut_nach_fix` beider Prüfer (D4). In welle4 `433da64bc`.

### FD-49 G7 zählt beschriftete Aufklapppfeile als namenlose Symbolknöpfe

- Art: Fehler
- Schwere: leicht
- Funktion: resize_hole
- Prüfpunkt: 19, G7
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/001/function.json#icons und 02-flaeche.png: Merkmal verschieben, Zum Langloch ziehen, Merkmal drehen und Merkmal verdoppeln sind sichtbare beschriftete Zeilenköpfe; G7 fordert dennoch eigenes Symbol und Tooltip. Bestätigung im Prüfstandfixbericht, Abschnitt FD47/FD48/FD49.
- Ursache: Prüfstand: Ein checkable QToolButton mit Pfeil wurde trotz unmittelbar benachbartem sichtbarem gleichnamigem Label als Bedienelement ohne Text klassifiziert.
- Vorschlag: Nur diese unmittelbar und gleichnamig beschrifteten Aufklappköpfe als Textbedienelement behandeln. Verborgene, leere und anders benannte Labels entlasten nicht. headings-red: 1 failed/12 passed, danach grün laut Fixbericht; echte namenlose Symbolknöpfe bleiben Negativfälle.
- Wirkung beim Kunden: Die Abnahme erzeugt einen falschen Symbolbefund und könnte zu überflüssigen Symbolen oder Textdoppelung führen; kein belegtes namenloses Bedienelement an dieser Bildstelle.
- Stand: behoben `6d5734da5`; `headings-red` war am Original 1 rot. Finaler Lauf: G7 in allen 693 gemessenen Protokollen erfüllt, an 001 „0 Symbole“, Stufe B G7 `gut` (D4). In welle4 `433da64bc`.

### FD-50 Paar im Gegenstücke-Dialog hat keine eigene zugängliche Feldhilfe

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: Erzeugen/Bausteine/Gegenstücke setzen …
- Prüfpunkt: 8, V3
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/031/surfaces/Erzeugen_Bausteine_Gegenstücke_setzen-5b902f72.json#fields: fünf von sechs Feldern mit eigenem Satz, Paar ohne Tooltip/AccessibleDescription; F:/tmp-suche/probelauf-d0-zwei-codex/cases/031/flaeche-de-Erzeugen_Bausteine_Gegenstücke_setzen-5b902f72-dialog.png. Stufe-B-D10-Bericht und fix-counterpart-front-codex.md Abschnitt FD-50.
- Ursache: Der bereits übersetzte erklärende Satz pair.doc erscheint im Dialog, ist aber nicht dem Paarfeld als Kurzhilfe und AccessibleDescription zugeordnet.
- Vorschlag: Gemeinsamen Pair.doc beim Paarwechsel an Tooltip und AccessibleDescription von Feld und Beschriftung binden. KF-L1 verlangt dabei die inhaltstreue Kürzung der beiden zentralen Quellen für Schraube/Mutter und Buchse/Loch von 30/29 auf höchstens25 deutsche Wörter samt je fünf Katalogwerten. Die frühere Aussage keine neuen Katalogtexte ist damit überholt. Eine Quelle für sichtbaren Hinweis und Hilfe erhalten; drei Paare/sechs Sprachen und tatsächliche Wort-/Satzgrenze prüfen. Von FD42 getrennt nachweisen.
- Wirkung beim Kunden: Direkt am obersten Auswahlfeld fehlt der erklärende Satz für Kurzhilfe und Hilfstechnik.
- Stand: behoben `d06fb300b`; `tests/test_counterpart_front.py` war am Original rot. Finaler Lauf 031–036: V3 6 von 6 Feldern samt Paar, Stufe B V3 `gut_nach_fix` (D10). In welle4 `9b3e44120`.

### FD-51 Kurzer Dialoginhalt behält eine unnötige Mindesthöhe von 88 Pixeln

- Art: Gestaltung
- Schwere: leicht
- Funktion: rename_object
- Prüfpunkt: 19, Z6
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/043/flaeche-de-rename_object-03af2449-dialog.png: Dialog380×154, leerer Bereich x16–363/y68–110=348×43=14964 Pixel. Gegenbild duplicate_object380×157 hat unter zwei Feldern nur8 Pixel Abstand. D8-Größennachtrag; KOORDINATION reserviert FD51 nach 13 roten Gegenproben.
- Ursache: Die gemeinsame DialogScrollArea hält auch bei kurzem Inhalt eine pauschale Mindesthöhe von88 Pixeln vor und vergrößert dadurch den leeren Rumpf.
- Vorschlag: Im bestehenden style.py-Rumpf die natürliche Inhaltshöhe als Untergrenze berücksichtigen. Ziel für die gezeigte DE-Fläche etwa32 Pixel weniger Höhe, kein fester122-Pixel-Dialog. Lange Inhalte, sechs Sprachen, größere Schrift, manuelle Nutzergröße und Rollweg erhalten.
- Wirkung beim Kunden: Ein Dialog mit nur einem kurzen Namensfeld verdeckt mehr3D-Fläche als sein tatsächlicher Inhalt benötigt.
- Stand: behoben `2e4752521`; die Regression war am Original 13 rot. Finaler Lauf 043–048: *Umbenennen* 380 × 118 statt 380 × 154, Stufe B P19 „FD-51 im Bild behoben“ (D8). In welle4 `27a18b48c`.

### FD-52 Vorschauband bleibt nach ausgeblendeter Legende zu schmal

- Art: Gestaltung
- Schwere: leicht
- Funktion: Erzeugen/Bausteine/Gegenstücke setzen …
- Prüfpunkt: 9, 19
- Beleg: Original PT/Fall036 und IT/Fall035 bleiben erhalten. Bestätigte stabile PT-Vorgeschichte: F:/tmp-suche/preview-band-diagnose-codex/history-24-f80741556/run-f80741556/cases/036/band-00-vor-originalmessung.png und band-stabil-2.png; pt-analysis.json. Band382×106 statt sizeHint557×106, Legende und Notiz abgeschnitten; sieben native Aufnahmen bytegleich, SHA256 da3a2108f2242110cf4c20fb021a39b11a154dfc8809abface23d12aaa25a8bf. Diagnosebericht vorschauband-diagnose-vorgeschichte-codex.md. IT-Vollfolge ohne abgeschlossenen neuen Zielnachweis.
- Ursache: Vorherige Vorschauabsage mit changes=False versteckt die Legende. _refresh_preview_banner ruft show_preview/place/adjustSize vor dem Wiedereinblenden auf; endgültige Legendensichtbarkeit fehlt bei der Messung. PT:557−163−12=382px. Fertige Vorschau und weitere Ereignisse heben den Zustand nicht auf; kein Beleg für eine bloß zu frühe Aufnahme oder FD46-Kartenbreite.
- Vorschlag: Endgültige Legendensichtbarkeit vor den vorhandenen show_preview/place-Aufruf setzen. Keine zweite Größenrechnung oder neue Mindestbreite. Originalvorgeschichte, kurze/lange Hinweise, echte sechs Kataloge und Inhaltsschriften prüfen; native PT-/IT-Gegenprobe erst mit freigegebenem korrigiertem C-Prüfstand.
- Wirkung beim Kunden: Die Legende zur Vorschau endet mitten im Wort; der umgebrochene Notiztext wird ebenfalls abgeschnitten. Der Kunde kann die angezeigte Vorschaufolge nicht vollständig lesen.
- Stand: behoben `ac6c686f1`; der Widgettest war am Original rot. Finaler Lauf 036 (PT, gleiche Vorgeschichte): Vorschauband mit Legende und Notiz ganz, Stufe B P9 „nicht mehr zu sehen“ (D10). In welle4 `64ec1b690`.

### FD-53 Gemischte Exportprobe übernimmt die Auswahl der vorherigen Szene

- Art: Fehler
- Schwere: mittel
- Funktion: finding.action:export_as_mesh
- Prüfpunkt: 9, 19
- Beleg: F:/tmp-suche/probelauf-zwei-pruefstand-fix-codex/export-native-context/cases/043/lifecycle.jsonl: Originalteilfolge decimate_mesh→export_gemischt behält selection[obj_1]; neue Szene obj_1=brep/obj_2=mesh. t314485.7226815: QFileDialog „Exportieren: 1 von 2 Körpern“; t314486.0832581: ui.handoff_receipt. Tatsächliches Ergebnis: export-native-context/cases/043/ausloeser/szene.step. Gegenbeleg export-native-diagnosis/cases/043/lifecycle.jsonl t314393.4609132: leere Auswahl, beide Körper, QMessageBox „Vor dem Export gefunden“ mit export.needs_solid; isolierter Lauf Exit0/19,25s laut C-Bericht.
- Ursache: Prüfstandfehler: Die Szenenvorbereitung übernimmt die zuvor ausgewählte ID obj_1. In export_gemischt bezeichnet dieselbe ID den exakten Quader; der Netzkörper obj_2 gehört nicht zur Auswahl. Die Produktfunktion exportiert folgerichtig nur diesen einen geeigneten Körper. Der Prüfstand wartet dagegen bis180s auf die Rückfrage für einen nicht zum Exportumfang gehörenden Netzkörper.
- Vorschlag: Fix C stellt vor dieser Exportvorbereitung über die bestehende Kundeneingabe eine leere Auswahl her und prüft den öffentlichen Zustand beziehungsweise vollständigen Exportumfang. Danach ursprüngliche decimate_mesh→export_gemischt-Folge sowie isolierten Gegenfall neu belegen. Keine Änderung am Produkt-Export, keine bloße Unterdrückung der Wartefrist oder nachträgliche Umwertung.
- Wirkung beim Kunden: Die Abnahme meldet fälschlich eine fehlende Export-Rückfrage und erreicht den beauftragten gemischten Exportfall nicht. Das beobachtete Produktverhalten ist korrekt; daraus folgt kein Kundenfehler des STEP-Exports.
- Stand: behoben `6d5734da5`; `tests/test_function_export_preparation.py` war am Original 8 rot. Finaler Lauf 043–048: Escape leert die geerbte Auswahl, `export.needs_solid` erscheint, der Dateidialog öffnet und wird gemessen; Stufe B urteilt an dieser gemischten Exportfläche (D8). In welle4 `433da64bc`.

### FD-54 Große Inhaltsschrift schneidet Einleitung und Hauptknopf im Operationsdialog ab

- Art: Gestaltung
- Schwere: mittel
- Funktion: group_pattern
- Prüfpunkt: 9, 19
- Beleg: F:/tmp-suche/fix-dialoggroessen-codex/native-review-fix/01-dynamic-03.png und .json: Als Muster zusammenfassen, automatische Breite 380 px, tatsächliche Inhaltsschrift 18 pt, DPR 1,0; erster Einleitungssatz und Hauptknopf abgeschnitten. Bildurteil und 23 gelesene native Aufnahmen aus fix-dialoggroessen-codex.md vom Autor bild_d4; keine neue eigene Bildprüfung in diesem Dokumentationsnachtrag. fd54-before-realfont.log: Einleitung 96 px hoch, benötigt 128; Hauptknopf 202 px breit, benötigt 329, Textbreite 303. Basisgegenprobe fd54-base-realfont.log reproduziert den Fehler auch auf dca24076f.
- Ursache: Bei tatsächlicher großer Inhaltsschrift decken vorhandene automatische Dialogbreite, Umbruchhöhe der Einleitung und einzeilige Knopfleiste den Platzbedarf nicht. Der erste Satz endet vollständig mit „oder ändern lässt.“; der zweite Satz gehört gemäß lead_sentence bewusst in die Kurzhilfe. Der Befund ist eine Abschneidung vorhandener Texte, kein Auftrag zur Kürzung. Die Größenursache ist im Autorenbericht dokumentiert; Basis und eigener Zwischenstand betroffen.
- Vorschlag: Einleitung über den vorhandenen Umbruchträger korrekt bemessen und automatische Breite anhand des tatsächlichen Inhalts bis zur Bildschirmgrenze nachführen. Bei gewählter Nutzergröße vollständige Knöpfe und Rollweg erhalten, bei Bedarf Knöpfe untereinander beziehungsweise mit Textumbruch; Originaltexte, Rollen, Tastatur und zugängliche Namen bewahren. Sechs Sprachen sowie automatische/manuelle Größe und echte Inhaltsschrift am endgültigen Stand belegen.
- Wirkung beim Kunden: Der Kunde kann bei großer Schrift den vollständigen Hinweis und den Namen der Hauptaktion nicht lesen, obwohl beide Texte vorhanden sind. Der kürzere englische Cancel-Knopf in der alten Sonde ist eine getrennte fehlende Qt-Übersetzerinitialisierung der Sonde und kein Produktsprachfund.
- Stand: behoben `2e4752521`; die große Inhaltsschrift fährt der Schlusslauf mit dem Satz `schrift` (14 und 18 pt je Sprache, `996503fed`, `f7a4f0675`); nativer Nachweis im Schlusslauf (Plan Punkt 20).

### FD-55 Wechselnde Python-Wrapperidentität verwirft einen ruhigen C++-Dateidialog

- Art: Fehler
- Schwere: mittel
- Funktion: finding.action:export_as_mesh
- Prüfpunkt: 9, 19
- Beleg: review-probelauf-fixes-nachpruefung-codex.md, FD55/RPF2-M1: tools/function_bench.py:144 id(root), Anschluss still_step:330–338 und geöffnete Befundfläche:1920–1922; HEAD 341588a5d, gebundener Stand mit 22 Pfaden, Autorenmanifest 20ac20317a86b1e7bc8d75224a2ca638d2f9743ee99c64179b105523a3005299. F:/tmp-suche/review-probelauf-fixes-nachpruefung-codex/stillness-static-dialog.json: 24 Abfragen, 18 Python-IDs, ein C++-Zeiger und eine vollständige Geometriesignatur; echter still_step verwirft die ruhige Fläche nach 0,817 s bei auf 0,8 s verkürzter Prüffrist. Derselbe Dialog mit gehaltener Hülle ist nach 0,335 s still, Sonde Exit 0.
- Ursache: Prüfstandfehler: surface_signature bindet die Flächenidentität an id(root). Für denselben von QFileDialog.getSaveFileName in C++ erzeugten Dialog liefert PySide nach Freigabe der vorigen Hülle neue kurzlebige Python-Hüllen. Die Identität ändert sich bei konstantem C++-Dialog und unveränderter sichtbarer Geometrie; der Stillstandsmerker beginnt deshalb immer wieder neu. Die unabhängige Offscreen-Sonde belegt diesen Mechanismus. Der native export-native-context-fixed-Lauf enthält keine Zeiger-/Signaturmessungen und beweist nicht nachträglich dieselbe Ursache für jeden Takt.
- Vorschlag: Die Identität lebender Qt-Flächen während der Messphase stabil halten, etwa durch Referenzen auf die aktuellen Wurzelwidgets. Echte Geometrieänderung und Flächenwechsel müssen weiter neu beginnen. C++-erzeugten Dialog ohne vom Test dauerhaft gehaltene Python-Hülle sowie echte Bewegung und Flächenwechsel gezielt gegenprüfen; Stillstandsfrist und Pflicht zur vollständigen Messung nicht lockern.
- Wirkung beim Kunden: Die Abnahme kann die wirklich geöffnete Dateidialogfläche trotz ruhiger Rechtecke als ungemessen verlieren. Dadurch bleibt der Exportfall unbegründet unvollständig. Kein Produktfehler und kein falsches Grün; vorhandene fehlende Messungen werden nicht nachträglich gutgesetzt.
- Stand: behoben `6d5734da5`; `fd55-red-2` war am Original 1 rot. Finaler Lauf 043–048: der Speicherdialog ist vollständig gemessen (`unmeasured` leer), Stufe B P9 und P19 urteilen an ihm (D8). In welle4 `433da64bc`.

### FD-56 Synthetisches Radereignis erreicht nach Ablehnung den äußeren Rollbereich nicht

- Art: Fehler
- Schwere: mittel
- Funktion: command:edit.auto_split
- Prüfpunkt: 1, 2, 9, 19
- Beleg: auto-split-messluecke-codex-nativ.md und F:/tmp-suche/auto-split-messluecke-codex/run-probe-accepted-original/cases/043/observer.jsonl: acht Zustellungen an QToolButton Formgebung bei [5696,775], accepted_after=false, kein äußerer Empfänger, Rollwert 0 bei Maximum 274. Betriebssystem-Gegenprobe am identischen Punkt erreicht äußeren Scrollbar, 0→80, Auto Split wird sichtbar und erreichbar. fix-radweiterleitung-codex.md: Original 4 rot/10 grün, Kandidat 14 grün; beim C-Anschluss einschließlich Werkzeugvorbedingung 15 grün. F:/tmp-suche/probelauf-zwei-pruefstand-fix-codex/fd56-native-final: Originalfolge mit einem wheel_down und getroffenem Ziel, Exit 0/17,47 s, keine Fehler oder fehlenden Messungen, keine Restprozesse.
- Ursache: Prüfstandfehler in tools/function_walk.py, QtPorts.press, ursprünglicher Radzweig: QApplication.sendEvent stellt QWheelEvent unmittelbar dem getroffenen Kindwidget zu und verlässt den Zweig. Dessen ausdrückliche Ablehnung löst dabei nicht die normale Fenster-Weiterleitung zum äußeren Rollbereich aus. sendEvent-Rückgabe true ist keine Annahme. Ein vorhandener Hinweis verlagert das Ziel um 45 Pixel und macht den funktionierenden Kunden-Rollweg erforderlich. Das Produkt bewältigt diesen Zustand über die Betriebssystem-Eingabe korrekt.
- Vorschlag: Vorhandenen Qt-Fensterdispatcher QTest.wheelEvent mit korrekt aus dem globalen Punkt abgeleiteten QWindow-Koordinaten und unveränderten Zusatztasten benutzen. Keine eigene Elternschleife, kein direktes Setzen von Scrollwerten. Die Werkzeugvoraussetzung Qt ab 6.8 ausdrücklich prüfen; bei fehlender API Handlungshinweis auf die gepinnte Prüfumgebung 6.12, keine Änderung am allgemeinen App-Minimum. Annahme/Ablehnung, verschachtelte rollbare Bereiche, Bewegung beider Richtungen, Modifier und echten ursprünglichen Zielweg sichern.
- Wirkung beim Kunden: Die Abnahme meldet Auto Split fälschlich als nicht auffindbar, obwohl der normale Kundenweg mit einem Radschritt funktioniert. Kein Produktfehler und keine Aussage über die Teilungsrechnung; der verwendete passende Quader prüft Zugang und Schon-passend-Rückmeldung.
- Stand: behoben `6d5734da5`; Rottest am Stand davor rot (4), danach grün; Lage im Test erzwungen, nativ nicht erzwingbar (Plan Schlusslauf §6 Nr. 6, Punkt 21).

### FD-57 Auswahlkarte und XYZ-Zeile geraten nach spanischem Schriftwechsel in eine Größenschleife

- Art: Gestaltung
- Schwere: mittel
- Funktion: move_feature
- Prüfpunkt: 9, 19
- Beleg: fix-panelbreite-codex.md vom Autor bild_d10; F:/tmp-suche/fix-panelbreite-codex/native-trace-es/native.json und timeout.png. Nach echter Segoe-UI-Änderung 9→14 pt bleiben bei 19,6–20,0 s und busy=false die Rechtecke in Bewegung: cardColumn-Breite 470 bis 483 logische Pixel, _CoordinateRow-Höhe 41↔131; Rollbalken erscheinen und verschwinden. Prozess Exit 1, Quellen vor/nach 2300 Pins gleich am Korrekturmanifest eef17728e9ebb3bf387776a5a207468dd92cf370d82f609b765683b9af0e19c4. Frühere sechs native Prozesse Exit 0; ein 1×1-Pixel-Bild ist kein Sichtbeleg, Ersatz-/Diagnosenachlauf bleibt rot.
- Ursache: Echte Produkt-Geometrieänderung im Auswahlkartenlayout, während die Sitzung nicht rechnet; keine bloß wechselnde Python-Wrapperidentität wie FD55. Der Autorenbericht lokalisiert die Rückkopplung an der von augenblicklicher Sichtbarkeit abhängigen Rollbalkenreserve in der natürlichen Breitenmessung. Ein kleiner roter Höhenwechsel-Fall nimmt XYZ allein durch einen erscheinenden Balken zwölf Punkte zugesagte Breite. Die neue enge Korrektur verwendet das vorhandene Stilmaß möglicher Rollbalken unabhängig von ihrer aktuellen Sichtbarkeit; ein abschließender nativer Nachherbeleg fehlt noch.
- Vorschlag: Im bestehenden Kartenmessweg die Rollbalkenreserve und den natürlichen Querbedarf so bestimmen, dass der sichtbare aktuelle Zustand keine endlose gegenseitige Größenänderung erzeugt. Roten konkreten Schriftwechsel-Gegenfall sichern, anschließend tatsächlichen ES14-Nachlauf mit stabiler Geometrie sowie Sprach-/Rückkehrgegenfälle belegen. Nicht nur die Wartefrist verlängern, eine breite Fixbreite erzwingen oder den roten Nachlauf durch frühere grüne Fälle ersetzen.
- Wirkung beim Kunden: Die Auswahlkarte verändert nach dem Schriftwechsel fortlaufend ihre Breite, und XYZ springt zwischen Querzeile und gestapelten Feldern. Die Bedienelemente bleiben dadurch nicht ruhig; eine verlässliche Größeneinstellung und Zielwahl ist in diesem Zustand nicht belegt.
- Stand: behoben `11f44ba88`; den Schriftwechsel 9 → 14 pt zur Laufzeit fährt der Schlusslauf mit dem Satz `schriftwechsel` (`996503fed`); seit FD-194 (`a9a3233a7`) folgt die Anwendung dem Wechsel ohne Neustart; nativer Nachweis im Schlusslauf (Plan Punkt 22).

### FD-58 Vollzeilenknopf erhält halbe Umbruchbreite und behält einen ungültigen Rasterzustand

- Art: Gestaltung
- Schwere: mittel
- Funktion: pattern_feature
- Prüfpunkt: 9, 19
- Beleg: fix-panelbreite-codex.md und KOORDINATION.md: tatsächlicher MSI-Nachlauf native-fd57-msi zeigte am vollständig überspannenden Hauptknopf unnötigen Umbruch. Reale Segoe-14-Folge 504×44→435×64→504×44; erste 12-Fälle-Gegenprobe FR/IT/PT rot (3 rot/9 grün). Isolierter 600→450→600-Fix reichte nicht: native-fd58-trace/de/07-tall-14.png zeigt Merkmal vervielfachen trotz natürlichem Textbedarf 242 in 474×64 auf zwei Zeilen. Neue echte schmal/9→groß/14→schmal/9-Folge im Original rot (ES: 1 rot/5 grün), endgültig 66 bestanden/88,00 s, Exit 0. Finales Manifest 4a03df4877f1d4ae8197950c7e61a113bad8fe659d6f0952267b6481a13b3d18; native-fd58-final sechs MSI-Sprachen/24 vom Autor tatsächlich gelesene Bilder, alle Exit 0. Pixelurteil ee045d065c8bc4e9749af8a94d5f82e54537e3f068f290f14b8590325fd27743; Root las DE/ES zusätzlich.
- Ursache: Produktfehler in app/ui/selection_operations.py, vorhandener _wrap_labels-Weg: Der dritte Hauptknopf überspannt die ganze Rasterzeile, die Textmessung teilte die Breite trotzdem wie bei den beiden Nachbarknöpfen. Während Qt die Knöpfe umhängt, wird derselbe Weg vor dem erneuten Eintragen aufgerufen; indexOf(button) ist dann -1, getItemPosition liefert keinen gültigen Spaltenumfang. Die Gegenprobe sah den ungültigen Wert 32761. Der Messcache behielt diesen Zwischenstand, weil sein Schlüssel den gültigen tatsächlichen Span nicht hinreichend unterschied.
- Vorschlag: Im vorhandenen Umbruchweg den tatsächlichen gültigen Raster-/Spaltenumfang verwenden, einen noch nicht eingetragenen Knopf abwarten und den gültigen Span im bestehenden Messschlüssel berücksichtigen. Keine zusätzliche feste Kartenbreite, zweite Layoutdefinition oder neue Timerkette. Den echten Start- und Rückweg mit tatsächlicher Schrift 9/14 und sechs Sprachen prüfen, einschließlich XYZ-Querzeile, Höhe 1200→700→1200 und unterster sichtbarer Handlung.
- Wirkung beim Kunden: Eine eigentlich ausreichend breite Hauptaktion wird unnötig zweizeilig und hoch. Beim echten Wechsel von schmaler Ansicht mit kleiner Schrift zur großen Ansicht mit großer Schrift kann dieser überhöhte Zustand trotz genügend Platz erhalten bleiben; die Karte und ihr Rollbedarf zeigen dadurch vermeidbare zusätzliche Höhe.
- Stand: behoben `11f44ba88`; die Folge schmal/9 pt → groß/14 pt → schmal/9 pt fährt der Schlusslauf mit dem Satz `schriftwechsel` (`996503fed`); nativer Nachweis im Schlusslauf (Plan Punkt 23).

### FD-59 Innere Fallfrist des Dateiprüfstands lässt untergeordnete Prozesse zurück

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: file_acceptance.run
- Prüfpunkt: 9, 19
- Beleg: probelauf-zwei-pruefstand-fix-codex.md, delivery-fd59.json und F:/tmp-suche/koord-codex/merge-fd59/evidence.md: vier echte Windows-Ketten aus Launcher, Interpreter und Helfer, Modi normal/nonzero/timeout/exception. fd59-red: 4 rot, Exit 1; Timeout ließ Helfer PID 73148 zurück, Ausnahme PID 64760. Normalende und Exit 7 waren bereits korrekt, ihre roten Assertions betrafen fehlende explizite Startoptionen. fd59-green: 4 grün, Exit 0; fehlende Restprozesse per Betriebssystem geprüft. Endgültiger Paket- und Integrationsanschluss jeweils 142 bestanden/5 Fensterfälle abgewählt, Exit 0, Statik Exit 0. Vorhandener count_new_windows auf vier echten Ketten: 4 grün, Befehl und Zähler Exit 0, 0 neue sichtbare Fenster/0 Konsolenfenster. Prozess-/Profilmarken in fd59-process-records.json; eigene Restprozesse bei Lieferung leer.
- Ursache: Prüfstandfehler in tools/file_acceptance.py, run(): Die innere Fallfrist beendete nur den direkt gestarteten Launcher. Auf Windows blieb dessen untergeordnete Interpreter-/Helferkette bei Timeout und Ausnahme im Warten bestehen. Die öffentliche Prozessgruppe war an dieser inneren Grenze noch nicht angeschlossen. Der neue Import von app.core.process benötigt zudem den eigenen ROOT unbedingt zuerst in sys.path, auch wenn dort vorher ein fremder Eintrag stand.
- Vorschlag: Vorhandene process_group_options(no_window=True), no_error_dialogs und terminate_process_tree im bestehenden run-Rumpf verwenden. Den zugehörigen Baum bei Timeout oder Ausnahme beenden, solange seine Kante besteht; keine zweite Prozessverwaltung. ROOT vor dem neuen Kernimport unbedingt vorn eintragen. Tatsächliche Exitwerte, Ausnahme, Timeoutstatus, Falldateien, Wiederaufnahme und sechs weitergegebene Profile unverändert erhalten. Normale Rückkehr und Exit 7 als Gegenfälle belassen.
- Wirkung beim Kunden: Ein abgebrochener Prüffall endet nur scheinbar vollständig. Zurückgebliebene Interpreter oder Helfer können nachfolgende Fälle und Prozessnachweise verunreinigen. Das ist ein Prüfstandfehler; hieraus wird kein Fehler des Produkt-Exportwegs oder der eigentlichen Anwendung abgeleitet.
- Stand: behoben `bc376abc0`; Rottest am Stand davor rot (4), danach grün; seit CS-35 (`27c56448c`) endet jeder Prozessbaum über ein Jobobjekt; im Tor hält `tests/test_file_acceptance_process_tree.py` die innere Frist, nativ optional im Schlusslauf (Plan Punkt 24, L6).

### FD-60 Native Zugriffsverletzungen brechen den frischen Fensterlauf ab

- Art: Stabilität
- Schwere: schwer
- Funktion: resize_hole, place_on_bed und die zugehörigen Sprachflächen
- Prüfpunkt: 9, 16
- Beleg: F:/tmp-suche/probelauf-d0-frisch-codex auf 6d063ef064: 48 Fälle, 41 Prozesse Exit 0, sieben Zugriffsverletzungen in 001, 002, 032, 038, 039, 042 und 047. Originaldaten und alle drei Stufe-A-Berichte unverändert erhalten. fix-projektwechsel-crash-codex.md und fd60-binding-codex.md binden die nachfolgenden einzelnen CDB-Sonden und die unabhängige Quellenlesung.
- Ursache: Die begrenzten CDB-Sonden zeigen den NULL-Zugriff in PySide::SignalManager::retrieveMetaObject und einen falschen Nicht-QObject-Wrapper vom Typ QWidgetItem. Der native Widgetabbau in weiterlebenden FeaturePanel-Layouts ließ dessen gehaltene Python-Hülle gültig. Die beiden betroffenen Abbauwege clear und keep_measure_group lösen das Widget jetzt vorher öffentlich aus dem tatsächlichen Layout, auch bei verschachteltem Layout oder externem Host. removeWidget entwertet die Itemhülle; Elternschaft und wiederverwendete Widgets bleiben erhalten. Kein Hardwareurteil.
- Vorschlag: Den belegten Einzelabbau über layout_lifetime.detach_from_layout vor hide/deleteLater führen; keine globale Invalidierung, zusätzliche Lebenszeitreferenz oder unterdrückte Ausnahme. Die ursprünglichen sieben Absturzfälle auf der gemeinsamen Fassung erneut prüfen.
- Wirkung beim Kunden: Der echte Anwendungsprozess endet ohne nutzbaren Rückweg. Die fehlenden Folgeaufnahmen und Urteile sind kein bestandenes Ergebnis; der Gesamtlauf kann nicht abgenommen werden.
- Stand: behoben `f507043f9`; `tests/test_feature_layout_lifetime.py` war am Original 9 rot. Finaler Lauf: alle 48 Fälle Exit 0 mit regulärem Abbau, darunter die alten Absturzfälle 001, 002, 032, 038, 039, 042 und 047. In welle4 `fda4f687c`.

### FD-61 Lagebefund zeigt Millimeter trotz gewählter Zollanzeige

- Art: Fehler
- Schwere: mittel
- Funktion: place_on_bed
- Prüfpunkt: 9
- Beleg: F:/tmp-suche/probelauf-d0-frisch-codex/cases/005/flaeche-zoll.png und function.json: Kopf, Objektbaum und Status in Zoll; ausgewählter Befund zeigt Überstand 10,00 mm. fix-befund-einheiten-codex.md bindet die Diagnose, ursprüngliche 48 roten Umrechnungsfälle und weitere 30 rote Auswahl-/Previous-Gegenfälle aus dem Reviewfund BE-01.
- Ursache: Kanonische geometrische Werte excess/gap/needed wurden bereits im Kern als vollständiger mm-Text geliefert und später nicht als Anzeigegröße formatiert. Bei synthetischen Gruppen wechselte die Identität mit den formatierten Mitgliedstexten. Der echte Einstellungsweg setzte außerdem den gelesenen Reiter und offene Körperknoten zurück; frühere künstliche Tabproben bildeten diesen Kundenweg nicht ab.
- Vorschlag: Ausschließlich vollständige kanonische geometrische mm-Werte über den bestehenden Längenformatter anzeigen; beim Einheitenwechsel den Bericht über seinen öffentlichen Pfad erneuern. Auswahl, Details und Voriger-Stand-Zuordnung an rohe vollständige Mitgliedsidentitäten einschließlich Duplikaten binden. Freitext, Versionszahlen und Slicerwerte unverändert behandeln.
- Wirkung beim Kunden: Der Bericht widerspricht der gewählten Maßeinheit. Ein unvollständiger Fix würde zusätzlich die ausgewählte Sammelzeile und ihren Bearbeitungszustand verlieren.
- Stand: behoben `5d11646c6`; die Einheitenregression war am Original 48 rot, der Reiter- und Baumweg 24 rot. Finaler Lauf 005: „Überstand: 0,3937 in“, Stufe B Zweitprüfer P9 `gut_nach_fix`, der Erstprüfer bestätigt (D8). In welle4 `c6789f91c`.

### FD-62 Kontrastmessung liest am Hauptknopf die falsche Textfarbe

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Prüfstand für Hauptaktionen
- Prüfpunkt: G6
- Beleg: fix-farbmessung-codex.md und review-farbmessung-codex.md; gleiche 13 Kontrastgegenfälle am Ausgang 9 rot / 4 grün, am Fix 13 grün. Die ursprünglichen Aufnahmen und Urteile des frischen D0-Laufs bleiben unverändert.
- Ursache: Die generische Farbrolle des Widgets entspricht bei einem über den Qt-Stil gezeichneten Hauptknopf nicht zwingend der tatsächlich verwendeten Beschriftungsfarbe und ihrem aktuellen Zustand.
- Vorschlag: Die tatsächliche zustandsabhängige Qt-Beschriftung messen; nur eindeutig deckende Textpixel übernehmen. Fehlende oder mehrdeutige Messung offen lassen. Den Hintergrund weiterhin am echten Bildschirm lesen, keine gute Themenfarbe als Ersatz für eine schlechte Eigenfarbe einsetzen.
- Wirkung beim Kunden: Die Abnahme kann ausreichenden Kontrast falsch beanstanden oder einen tatsächlichen Kontrastfehler verdecken. Der Produktstil und die Kontrastschwelle dürfen durch die Messkorrektur nicht verändert werden.
- Stand: behoben `599526b10`; die Kontrastgegenfälle waren am Original 9 rot. Finaler Lauf: G6 in 669 Protokollen erfüllt, kein Fund, Hauptknopf #1c2026 auf #f0a54a gemessen, Stufe B G6 `gut` (D10). In welle4 `f08927d63`.

### FD-63 Maßgruppe zeigt fünf eigenständige Vorderseitenfelder

- Art: Einfachheit
- Schwere: mittel
- Funktion: resize_hole
- Prüfpunkt: 2, E5
- Beleg: F:/tmp-suche/probelauf-d0-frisch-codex/cases/001/02-flaeche.png sowie Fälle 004 und 007 mit Zoll und Skalierung. Jeweils Durchmesser, Änderungsumfang, Tiefe, Materialtoleranz und separater Sammelhaken vorne. Originalbilder und Feldlisten in fix-massgruppe-front-codex.md gebunden.
- Ursache: Der Adapter der Merkmalsfelder verliert die Vorder-/Rückseitenzuordnung des Operationsschemas. Die Maßgruppe stellt außer Koordinaten alle Felder nach vorn und zählt den zusätzlichen Sammelhaken nicht gegen das Feldbudget.
- Vorschlag: Schemametadaten durch die gemeinsame Feldauskunft transportieren und rechts wie im Bild verwenden. Gewöhnliche Bohrung mit Durchmesser, Tiefe und gegebenenfalls Sammelhaken; Druckkorrektur und gewöhnlicher Änderungsumfang hinten. Fachlich vorbelegtes Mitnehmen des Einlaufs bleibt als bewusste vierte Eingabe sichtbar. Werte, Bedingungen, Wiederverwendung und Undo erhalten.
- Wirkung beim Kunden: Fünf gleichrangige Eingaben überladen die Maßgruppe und verletzen die Vorderseitengrenze. Ein pauschales Verstecken könnte dagegen eine wirksame Vorbelegung oder die Reichweite der Sammeländerung verschleiern.
- Stand: behoben `f333e5ba7`; der 43er-Satz war am Original 38 rot. Finaler Lauf 001, 004, 007, 016, 019 und 037–042: vorn drei Felder, E5 erfüllt, Stufe B E5 `gut_nach_fix` beider Prüfer (D4). In welle4 `b86381559`.

### FD-64 Maßgruppenfelder verlieren die Wirkungshilfe ihres Schemas

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: resize_hole
- Prüfpunkt: 8, V3
- Beleg: Dieselben frischen Maßgruppenbilder und Feldprotokolle wie FD63; Änderungsumfang und Materialtoleranz ohne Tooltip und zugängliche Beschreibung, Sammelhaken ohne Tooltip, Durchmesser/Tiefe nur mit Maßherkunft. Diagnose und genaue Adapterstellen in fix-massgruppe-front-codex.md.
- Ursache: ActionField transportiert die Schemahilfe nicht. Der gemeinsame Feldkonfigurator ersetzt die Feldhilfe durch Herkunft; Beschriftungen übernehmen diesen unvollständigen Stand. Erklärung einzelner Auswahlwerte ersetzt keinen Wirkungssatz des Feldes.
- Vorschlag: Die gemeinsame Schemahilfe durchreichen und bei Wiederverwendung an Beschriftung, Editor und fokussierte Innenfelder binden; Herkunft ergänzend erhalten. Beide Sammelhaken bekommen dieselbe übersetzte Wirkungshilfe. Die unklare Materialbezeichnung bleibt dem bereits bestehenden FD7 zugeordnet.
- Wirkung beim Kunden: Direkt am Eingabefeld fehlen die Erklärung der Änderung und entsprechende Auskünfte für Hilfstechnik. Der Nutzer sieht teilweise nur, woher das Maß stammt, nicht was seine Änderung bewirkt.
- Stand: behoben `f333e5ba7`; der 43er-Satz war am Original rot. Finaler Lauf: V3 8 von 8 Feldern mit Wirkungssatz in sechs Sprachen, Stufe B V3 `gut_nach_fix` beider Prüfer (D4). In welle4 `b86381559`.

### FD-65 Schriftprüfung lehnt die vertragliche Primärschrift ab

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Prüfstand für Hauptaktionen
- Prüfpunkt: G4
- Beleg: fix-farbmessung-codex.md und die neue test_function_primary_fonts.py: gleiche 31 Schrift-/Schemafälle am Ursprung 26 rot / 5 grün, am Fix 31 grün; bestehender Schriftaufnahmeanschluss zusätzlich grün. Tatsächliche gebündelte Fontfamilien und Metriken sind zugesichert.
- Ursache: Die Prüfung unterschied die ausdrücklich erlaubte halbfette Grundschrift des tatsächlichen Hauptknopfs nicht hinreichend von beliebigen Schriftabweichungen. Die Primärrolle und reale Anwendungsfamilie fehlten als typgeprüfte Messwerte.
- Vorschlag: Optionale boolesche Primärrolle und reale Schriftfamilien kompatibel erfassen. Nur nachgewiesene Primärbeschriftung in der tatsächlichen Grundfamilie und vereinbarten Größe/Gewichtung entlasten; gewöhnliche Knöpfe, fremde Familien und falsche Größen bleiben Gegenfälle. Alte Protokolle weiter lesen.
- Wirkung beim Kunden: Die Abnahme fordert eine Änderung an einer bereits vertraglichen Hervorhebung oder verdeckt echte Schriftabweichungen durch eine zu breite Ausnahme.
- Stand: behoben `599526b10`; die Schriftfälle waren am Original 26 rot. Finaler Lauf: Hauptknöpfe als halbfette Primärrolle erfasst, kein G4-Fund an einem Hauptknopf, Stufe B G4 `gut` an sieben D4-Zeilen. In welle4 `f08927d63`.

### FD-66 Gegenstückdialog behält unnötige Anfangshöhe

- Art: Gestaltung
- Schwere: leicht
- Funktion: Erzeugen/Bausteine/Gegenstücke setzen …
- Prüfpunkt: 19, Z6
- Beleg: Frische FR-/IT-Sprachflächen und fd66-diagnose-codex.md. Native FR-Originalfolge bei gleichem Inhalt und gleicher Breite: anfangs 341 × 353, nach einmal Auf-/Zuklappen 341 × 322; user durchgehend None und keine notwendige Rollleiste. Root hat beide tatsächlichen Bildschirmbilder gelesen; Sichtbeleg root-viewed-fd66-original.json unter F:/tmp-suche/koord-codex.
- Ursache: Die Anfangsmessung las eine durch vorübergehende AsNeeded-Rollleisten noch auf 297 statt 309 Pixel reduzierte Viewportbreite und erzeugte zusätzliche Textzeilen. Beim passiven Nachmessen wurde außerdem der Platz einer Querleiste ohne echten Rollweg als verdeckter Inhalt gezählt. sizeHint und _hidden_height berücksichtigen jetzt den tatsächlich verfügbaren maximalen Ausschnitt; nötige oder dauerhaft gesetzte Leisten bleiben erhalten. Keine irrtümliche Erkennung einer Nutzergröße.
- Vorschlag: Im bestehenden natürlichen Größenwunsch die nach Abbau vorübergehender Rollleisten tatsächlich verfügbare Breite zugrunde legen; keine feste 31-Pixel-Korrektur. Gleichen geschlossenen Inhalt vor und nach Klappzyklus vergleichen, manuelle Größe, echte große Schrift und tatsächlich nötige Rollleisten erhalten.
- Wirkung beim Kunden: Der Dialog verdeckt mehr Modellfläche als sein vorhandener Inhalt benötigt. Die zusätzliche echte Herkunftszeile in FR ist notwendiger Inhalt und bleibt erhalten.
- Stand: behoben `e7ca1cc95`; der Größenvertrag war am Original 15 rot. Finaler Lauf 034 und 035: Gegenstückdialog FR 341 × 322, IT 306 × 322 (vorher FR 341 × 353), Stufe B P19 ohne Anfangshöhe (D10). In welle4 `a100dd99f`.

### FD-67 Aufgeklappte Maßgruppenfelder im Bild verschwinden unter der Knopfzeile

- Art: Fehler
- Schwere: mittel
- Funktion: `resize_hole`
- Prüfpunkt: 19, Z6
- Beleg: F:/tmp-suche/fix-massgruppe-front-codex/native-runner-v3/runs/run-20261013T173601513Z/de/003-resize-rueckseite-vor-hover.png auf ece8988f2bdc60436a7bc327ee1b77e8e794a4b7, von Autor und Root tatsächlich gelesen. Nach Öffnen bleibt die Maßgruppe 304 × 232, der Scrollviewport 286 × 156; der Inhalt wächst auf 272 × 330. entrance_mode liegt unter dem Viewport, der Hit-Test trifft placement_measure_accept. Kein sichtbarer Rollbalken trotz abgeschnittenem Änderungsumfang und freiem Bildraum.
- Ursache: Der vorhandene PlacementFlow-Gruppenfilter verarbeitet den geänderten Größenbedarf nach LayoutRequest nicht. Die feste Höhe und ScrollBarAlwaysOff bleiben vom geschlossenen Zustand erhalten, auch nach weiteren Qt-Ereignisrunden.
- Vorschlag: Größenbedarfsänderungen über den bestehenden Gruppenfilter nach dem Qt-Layoutschritt an die vorhandene Größenrechnung anschließen; selbst ausgelöste Layoutschleifen, Gruppentausch und Abbau berücksichtigen. Aufklappen und Zuklappen gegenprüfen, bei echtem Platzmangel erreichbar rollen und Fußaktionen sichtbar halten.
- Wirkung beim Kunden: Die Rückseite lässt sich öffnen, ihre Werte sind aber verdeckt und mit dem Zeiger nicht erreichbar. Eine Vergrößerung auf pauschale Maße würde unnötig Modellfläche verdecken.
- Stand: behoben `f6b0f53f2`; nativer Nachweis im Schlusslauf: Maßkartenfolge mit aufgeklappten *Weiteren Werten* in sechs Sprachen (Plan Punkt 25, L1).

### FD-68 Druckbett-Raster verschwindet im hellen Thema

- Art: Gestaltung
- Schwere: mittel
- Funktion: keine Zeile: Druckbett in der 3D-Ansicht
- Prüfpunkt: 19
- Beleg: Nutzerhinweis und tatsächliche Vorheraufnahme F:/tmp-suche/fix-bettraster-hell-codex/native-before-v3/01-hell.png auf 4521cf8ff0d4f623c070feda6b67cb937b0cb7a7. Root und Autor haben das Bild gelesen: beleuchtete Bettfläche #B8C0C9 gegen Rasterpixel #BBC3CE, Linien kaum erkennbar. Identische Szene, Kamera, Fenster und Skalierung im Nachherordner native-after-v3; Haupt- und Nebenlinien deutlich sichtbar. Keine behauptete Textkontrast-Normverletzung.
- Ursache: Raster und Bettkante nutzten dieselbe sehr helle Farbrolle; 0,35 Deckkraft nähert die Linienfarbe zusätzlich an die beleuchtete Bettfläche an. Themenweitergabe und Tiefenabstand sind vorhanden; kein belegter Tiefenfehler. Die Linien hatten keine getrennte Gewichtung zur Orientierung.
- Vorschlag: Bestehende Rasterlinien mit eigener bed_grid-Farbrolle und disjunkten Haupt-/Nebenlinien alle fünf Abstände zeichnen. Positionen, Zeichenraster, Bauraum und Treffverhalten erhalten; Hell/Dunkel/Hell am echten Fenster vergleichen.
- Wirkung beim Kunden: Auf dem hellen Druckbett fehlt eine verlässlich erkennbare räumliche Orientierung. Die Korrektur lässt das Raster erkennen und hält den Körper visuell im Vordergrund.
- Stand: behoben `bc4fe912a`; `tests/test_bed_grid_visibility.py` war am Original 6 rot. Finaler Lauf 001, 005 und alle hellen Fälle: Haupt- und Nebenlinien des Bettrasters sichtbar (eigene Bildlesung); das Bett ist keine Zeile der Funktionsliste und hat keine eigene Stufe-B-Zelle. In welle4 `438efade2`.

### FD-69 Bettmaßzahlen bleiben im hellen Thema äußerst blass

- Art: Gestaltung
- Schwere: leicht
- Funktion: keine Zeile: Maßbeschriftung des Druckbetts
- Prüfpunkt: 19
- Beleg: F:/tmp-suche/fix-bettraster-hell-codex/native-after-v3/01-hell.png. Root und unabhängiger Bildprüfer sehen 100 bei etwa 1049/158, 50 bei 769/232 und 0 bei 429/324 nur äußerst schwach auf dem hellen Grund. Das neue Raster behebt die Zahlenfarbe nicht. Die genaue Kontrastquote wurde hier nicht gemessen.
- Ursache: Viewport._draw_one_bed verwendet für LabelStyle.text_colour weiterhin _bed_colour, also die Farbe der Bettkante (#bfcad8 im hellen Thema). Der bestehende Labelrenderer passt den Kontrast nicht automatisch an. Im dunklen Thema läuft derselbe Pfad mit #5a6472.
- Vorschlag: Ausschließlich die Maßzahlen über eine geeignete vorhandene Textrolle zeichnen und im Themenwechsel erneuern; Bauraumfarbe, Texte, Geometrie und Positionen erhalten. Hell und Dunkel am selben nativen Zustand nachlesen.
- Wirkung beim Kunden: Die Orientierungslinien sind sichtbar, die zugehörigen Maßzahlen bleiben aber schwer lesbar.
- Stand: behoben `1e37ebc10`; `labels-original-red` war am Original 2 rot. Finaler Lauf 001 (hell) und 016 (dunkel): Bettzahlen 0 und 100 lesbar (eigene Bildlesung), Stufe B liest sie an `resize_hole` P9 (die fehlende Einheit führt FD-92). In welle4 `d4e7305f3`.

### FD-70 Griff- und Vorschauflächen verdecken die gewählte Bohrung im Bild

- Art: Gestaltung
- Schwere: leicht
- Funktion: `resize_hole`
- Prüfpunkt: 19, G9
- Beleg: design-d0-oberflaeche-codex.md, tatsächliches helles Bild F:/tmp-suche/fix-massgruppe-front-codex/native-runner-v3/runs/run-20261013T173601513Z/de/003-resize-rueckseite-vor-hover.png und dunkler Originalfall016. Orange Griffkörper, flächige Markierung und Achspfeile überdecken die gewählte Öffnung stärker als die übrigen Bohrungen; Bildurteil mit begründeter Sichtprüfung, kein gemessener Kontrastwert.
- Ursache: Zwei gefüllte pickbare SlotHandle-Zylinder mit Deckkraft 1,0, zusätzliche nicht pickbare face-handle-Scheibe mit 0,6 und Merkmalsfüllung mit 0,45 liegen in der gewählten Öffnung übereinander. outlined bezeichnet die Schnittkontur und entfernt die Griffkörper nicht. Die vorhandene Größenbegrenzung der Zylinder verhindert diese perspektivische Überdeckung nicht.
- Vorschlag: Ruhende Füllungen gezielt zurücknehmen, überfahrene/gehaltene Griffe und wirkliche laufende oder wartende Entwürfe klar erhalten. Bestehende Netze, Bezugspunkte und positive Deckkraft im Pickpfad bewahren. Direkten take_press ohne Hover, wiederverwendeten Vorschauaktor, Abbruch und Wiederaufbau prüfen; keine kleineren Trefferflächen als Gestaltungstrick.
- Wirkung beim Kunden: Gerade die zu bearbeitende Öffnung lässt sich schlechter erkennen als die ungewählten. Die Gestaltung soll Lochrand und Änderung zugleich sichtbar halten, bei unverändert gut treffbaren Griffen.
- Stand: behoben `90600562c` (nach `48adcd982`, `1e37ebc10`); `test_hole_grip_clearance.py` am Stand davor 7 von 8 rot, danach grün: Knöpfe außen am Scheitel, Pfeile ab der Knopfreichweite, Wandtönung 0,28, hell und dunkel offscreen gelesen; nativer Nachweis G9 im Schlusslauf (Plan Punkt 26).

### FD-71 Maßkartenzüge halten den impliziten Qt-Mausempfänger fest

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Maßkarte am Titel oder freien Hintergrund verschieben
- Prüfpunkt: 8, 19
- Beleg: fix-measure-card-drag-codex.md und fix-massgruppe-front-codex.md; echte QWindow→QWidget-Transportgegenfälle für Titel und freie Fläche. Beide erreichen das richtige Dragziel, danach erhält am Original trotzdem das alte QLabel beziehungsweise Karten-QWidget den buttonlosen Move statt QComboBox. Zwei Fälle vor dem Fix rot, endgültige Helferdatei mit 36 Fällen grün. Native Folge run-20261013T201120471Z belegt passende Cursorziele, aber ToolTip/MouseMove weiter an der Maßkarte; ein Einzelhover ohne vorherigen Zug erreichte dagegen Feld und sichtbare Hilfe.
- Ursache: Der globale Ereignisfilter konsumierte auch den QWindow-Release. Dadurch erreichte die Freigabe den Qt-Transport nicht, der den impliziten button_down-Empfänger löscht. Ein ausdrückliches grabMouse verwendet der Helfer nicht.
- Vorschlag: Den aktiven Zug erst bei QWidget-Empfängern verarbeiten. QWindow-Transport unverändert passieren lassen; nach dem Loslassen muss die echte folgende Mausbewegung den neuen Empfänger erreichen. Eingabefelder, Außenrelease, Abbau und aktueller Vorfahrenvertrag bleiben erhalten.
- Wirkung beim Kunden: Nach dem Verschieben reagieren Feldhilfen und Hoverzustände nicht mehr am tatsächlich überfahrenen Eingabefeld. Die schwebende Karte lässt sich bewegen, stört danach aber die normale Mauszustellung.
- Stand: behoben `c902aed13`; in welle4 `8831b33e9`; native DE-Maßkartenfolge am echten Fenster auf welle4 `7d978c4ee` 62/62 Bedingungen (Titel- und Freiflächenzug mit vollständiger QWindow-/QWidget-Folge, echte Feldhilfen nach dem Zug; `output/konsolidierung-2026-10-12/native-d0-claude.md`, Nachweis 2).

### FD-72 Vordergrundkanten übernehmen den Zeichenvertrag ihrer Fläche nicht

- Art: Fehler
- Schwere: leicht
- Funktion: keine Zeile: 3D-Renderer, Fläche mit Vordergrundkanten
- Prüfpunkt: 19
- Beleg: review-grifflesbarkeit-codex.md und test_front_overlay_alpha.py; tatsächlicher öffentlicher add_surface-Aufruf mit SurfaceStyle(keep_in_front=True, show_edges=True), echten pygfx-Materialien und gesperrten Grafikadapteranforderungen. Vollständige Flächen-/Rückseiten-/Kantenprüfung vor Korrektur acht fachliche Fehler und acht Positivkontrollen, danach dieselben 16 Fälle grün. Kein bestehender Kundenaufrufer mit genau beiden Schaltern und keine native Ansicht mit verdeckten Kanten in dieser engen Prüfung nachgewiesen.
- Ursache: Das eigene show_edges-Material übernimmt weder den abgeschalteten Tiefentest noch die festgelegte Vordergrundqueue der zugehörigen Fläche. Die Lücke bestand bereits vor der Alphakorrektur von FD70.
- Vorschlag: Ausschließlich die zwei vorhandenen Materialargumente aus keep_in_front ableiten; Raumkanten behalten Tiefentest und automatische Queue. Deckkraftwechsel, force_opaque, Rückseitenanteile sowie erhaltene Geometrie und Pickflags gegenprüfen.
- Wirkung beim Kunden: Der öffentliche Renderer-Vertrag erlaubt, dass Kanten einer ausdrücklich im Vordergrund gezeichneten Fläche verdeckt werden. Eine solche konkrete Kundenansicht ist hier nicht belegt; kein Abbruch und keine Modelländerung behauptet.
- Stand: behoben `1e37ebc10`; in welle4 `d4e7305f3`, Renderertest am Original 8 rot. Keine Kundenansicht nutzt beide Schalter, Stufe A hat dafür keine Zeile; der Renderertest ist deshalb der Nachweis (Entscheidung Koordinator, 15.10.).

### FD-73 Freistehende Griffmaße verschwinden auf hellen Modellflächen

- Art: Gestaltung
- Schwere: leicht
- Funktion: `slot_hole`
- Prüfpunkt: 19, G9
- Beleg: Original F:/tmp-suche/fix-bettraster-hell-codex/grips-after-front-final/dark-05-gehaltener-zug.png auf 1e37ebc101cd18e42ed628d4d1310e17d786724d, von Autor, Root und unabhängigem Prüfer einzeln gelesen. Das freistehende Maß „16,03 mm“ liegt sehr blass auf dem hellblauen Hoverkörper; im hellen Bild ebenfalls grau. Keine gemessene Kontrastquote. FD70s aktive Griffe und Umrisse sind auf demselben Bild bereits kräftig; getrennter Textfund.
- Ursache: Viewport._label_gizmo hängt _slot_length_text an den gemeinsamen gizmo_labels-Aktor für X/Y/Z/L und wählt _object_colour als Textfarbe, im dunklen Thema #b9c4d0, im hellen #78828e. 13 Pixel, fett, immer sichtbar, ohne Hintergrund oder Umriss. Der vorhandene Textmaterialweg nutzt volle Deckkraft, keinen Tiefentest und seine Vordergrundqueue; keine belegte erneute OIT- oder Griffdeckkraftursache.
- Vorschlag: Vorhandenes kontrastierendes Text-/Fensterfarbpaar mit deckendem LabelStyle-Hintergrund verwenden. Die gemeinsame Wirkung auf Achsen-/L-Buchstaben ausdrücklich mitprüfen, bei Themenwechsel erneuern und am echten gehaltenen Zustand in beiden Themen nachlesen. Keine neue Farbrolle, API, Geometrie oder Definition im großen Viewport.
- Wirkung beim Kunden: Die aktuelle Länge steht zwar im Eingabefeld, lässt sich direkt am Griff aber nur schwer ablesen. Die Lesbarkeit darf nicht von der zufälligen Farbe der Fläche darunter abhängen.
- Stand: behoben `a408a0620`; das Bild im gehaltenen Langlochzug nimmt der Prüfstand seit `2835d5847` auf (`05-zug-gehalten`, `slot_hole` mit `drag = "handle:slot.end"`); nativer Nachweis hell und dunkel im Schlusslauf (Plan Punkt 27).

### FD-74 Prüfstand prüft den Knopftreffer vor der nötigen Mausbewegung

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Funktionsprüfstand, Bereitschaft vor einem Knopfklick
- Prüfpunkt: 8
- Beleg: fix-massgruppe-front-codex.md, native-runner-v3/runs/run-20261013T203830058Z. Die echte DE-Folge erfüllt 22 Bedingungen einschließlich gehaltener Maßkartenzüge und dreier Feldhilfen. Danach liegt ein tatsächliches qtooltip_label über dem künftigen Abbrechen-Ziel. click_button fragt widget_under vor QtPorts.press und dessen öffentlicher Mausbewegung ab und lehnt ab. Kein Abbrechen-Press, kein Nachbedingungsfehler und kein Timeout. Cursorort und Entstehungstakt dieses späteren Tooltips wurden am Abbruch nicht gemessen; keine solche Behauptung.
- Ursache: Die bisherige Bereitschaft prüft den zukünftigen Treffpunkt, ohne zuvor den tatsächlichen Mausort dorthin zu bewegen und Qt den natürlichen Zustellungs-/Tooltipabbau zu erlauben. Ein verschachteltes processEvents in click_button würde den bereits vorgemerkten StepMachine-Folgeschritt vor dem aktuellen Klick ausführen können.
- Vorschlag: Im bestehenden Walk.stable zuerst öffentlich zum aktuellen Ziel bewegen und im nächsten regulären Takt Ziel, Sichtbarkeit, Aktivierung, Geometrie und Treffer frisch prüfen. Bei geändertem Ziel erneut bewegen. Benannte und per Getter aufgelöste Knöpfe benutzen denselben Weg; click_button bleibt abschließender synchroner Zustands-/Trefferwächter. Vorhandene Fristen unverändert, keine gezielte Tooltipunterdrückung.
- Wirkung beim Kunden: Die Abnahme kann einen normal bedienbaren Kundenweg vor dessen Klick abbrechen. Ein kaputter Abbrechen-Knopf der Anwendung ist damit nicht belegt.
- Stand: behoben `f749bdc61`; Rottest am Stand davor rot (1), danach grün; Lage im Test erzwungen, nativ nicht erzwingbar (Plan Schlusslauf §6 Nr. 6, Punkt 28).

### FD-75 Erneute Fensterplatzierung trennt gemessene Clientfläche und Aufnahme

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Funktionsprüfstand, wiederholter Aufbau auf demselben Bildschirm
- Prüfpunkt: 9, 19
- Beleg: fix-massgruppe-front-codex.md und native-runner-v3/runs/run-20261013T210714907Z auf bc2d5e20c376e5d9003c1c1d8058033a93ca427f. Alle sechs Sprachen laufen funktional regulär durch. Bis Bild020 stimmen QWidget-Client/contentsRect und grabWindow mit 2560 × 1369 überein; ab dem nächsten FunctionFlow.prepare melden Client und contentsRect 2560 × 1392, die PNGs bleiben 2560 × 1369. Die letzten 23 Pixel einschließlich Statuszeile fehlen sichtbar, unabhängig von D4, D8 und Root gelesen. Kein bloßer Unterschied zwischen Fensterrahmen und Client und kein bewiesenes Abschneiden am physischen Monitorrand.
- Ursache: place_window ruft bei jeder Vorbereitung erneut setGeometry(availableGeometry) und showMaximized auf, auch wenn das Fenster bereits auf demselben Schirm maximiert ist. Der zweite Aufbau überschreibt damit den gespeicherten QWidget-Clientumfang. Die native Gegenprobe bestätigt einen unveränderten Win32-Rahmen und tatsächlichen Client von 2560 × 1369; ausschließlich QWidget und contentsRect springen beim zweiten Originalaufbau auf 2560 × 1392. Kein physischer Monitorbeschnitt.
- Vorschlag: Wiederholte Maximierung am bereits gewählten Schirm idempotent behandeln; beim ersten Aufbau, Monitorwechsel oder Wechsel zur ausdrücklichen Größe den nötigen Normalzustand herstellen und den bisherigen Platzierungsvertrag erhalten. Aufnahme und tatsächliche Clientfläche gegenprüfen, einschließlich vollständiger Statuszeile. Kein Zuschneiden, keine erfundenen Sollpixel und keine Änderung der Bildschirm-/DPI-Untergrenzen.
- Wirkung beim Kunden: Prüfstandsmessung und sichtbarer Bildbeleg beschreiben unterschiedliche Flächen. Die bereits innerhalb des Bilds belegten Kartenaktionen bleiben gültig, eine vollständige Fensterabnahme kann daraus nicht entstehen. Kein Fehler am eigentlichen Kunden-Statusinhalt belegt.
- Stand: behoben `a0d5ae491`; Rottest am Stand davor rot (5); nativer Nachweis im Schlusslauf: vier Aufbauten in einem Prozess, Bildpixel gleich Clientgröße (Plan Punkt 29, L1).

### FD-76 Textmessung beschädigt HTML-Entities und literale Ampersands

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Funktionsprüfstand, Textnormalisierung vor der Breitenmessung
- Prüfpunkt: 9
- Beleg: review-v4-textnormalisierung-codex.md; frisches V4-ready.json von Fall001 auf 2ec37b23bbc18bd76fc604c794ecd0c7231adaec. Die tatsächlich vollständig sichtbare Vorschaulegende wird als „nbsp;+ Hinzugefügtnbsp;nbsp;nbsp;nbsp;- Entferntnbsp;“ mit Bedarf301/Breite145 und cut=true vermessen. Sie ist in diesem Fall nur im Zusatzartefakt enthalten, nicht im öffentlichen function.json; kein bereits erzeugtes falsches P9-Urteil dieses Falls behauptet.
- Ursache: _text_of entfernt jedes & vor der HTML-Normalisierung durch QTextDocument. Dadurch verliert &nbsp; seinen Entity-Anfang; auch Qt-Mnemonics und escaped && werden undifferenziert behandelt.
- Vorschlag: Vorhandenen Textweg trägergerecht normalisieren; RichText unbeschädigt parsen, Mnemonic-Marker nur bei geeigneten Trägern entfernen und literale Ampersands erhalten. Echte Label-/Knopfgegenfälle und weiterhin roter P9-Kontrollfall bei zu geringer Breite.
- Wirkung beim Kunden: Die Abnahme kann eine vollständig sichtbare Beschriftung fälschlich als abgeschnitten einstufen. Der Text der Anwendung selbst ist in diesem Beispiel korrekt.
- Stand: behoben `f4c9bd26c`; Originalrot 14 Fälle, am Fix 16 grün; Text-/Aufnahmeanschlüsse grün; in welle4 `7eebc67dd`.

### FD-77 Navigationsabschluss akzeptiert ein halb abgeschnittenes Eingabefeld

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Gemeinsame Anleitungsnavigation und Funktionsaufnahme, Filamentwähler
- Prüfpunkt: 9, 19
- Beleg: filament-picker-sichtbarkeit-codex.md; frischer Fall032/EN auf 2ec37b23bbc18bd76fc604c794ecd0c7231adaec. Original flaeche-en-filament.picker-0afd58ad.png von Root, D10 und B einzeln gelesen. „No filament assigned yet“ am unteren Rand der Rollkarte abgeschnitten, Hauptfensterstatus vollständig. Ziel1339..1367 gegenüber zuvor protokolliertem Rollrand1354; Mitte1352 treffbar. Keine nachträglich erfundene vollständige Clipkettenmessung.
- Ursache: guide_targets._scroll_needed prüft ausschließlich die Mitte gegen alle Scrollsichtflächen. Walk bestätigt den stabilen Mittelpunkt und Treffer; der nachfolgende Stillstand prüft keine Vollsicht. So wird die teilweise abgeschnittene Fläche regulär aufgenommen.
- Vorschlag: Passend große Felder im vorhandenen gemeinsamen Navigationsweg bis zu ihren vertikalen Kanten freilegen, innere und äußere Scrollbereiche berücksichtigen. Vollsichtkontrolle mit halb abgeschnittenem Original, oberem Rand, verschachtelten Bereichen, vollständig sichtbarem Feld, übergroßem Container und Scrollanschlag. Keine privaten Scrollbaränderungen im Kundenweg oder verlängerten Fristen.
- Wirkung beim Kunden: Eine technisch erreichbare Feldmitte wird als brauchbare Endansicht behandelt. Eine unbedienbare Produktliste ist damit nicht belegt; kein erneuter FD75-Statusbeschnitt.
- Stand: behoben `46c628ef9`; gegen die alten Module 20 rot (16 fachlich, 4 Vertrag), gezielt 92/92 grün; betroffene Auswahl 14 783 grün, Exit 0; in welle4 `64e389936`. Native EN-Nachheraufnahme von Fall 032 auf `7d978c4ee`: Lauf regulär, der Wähler aber „nicht auffindbar“ — die Anleitungsnavigation verwirft den Rollschritt unter einer verschachtelten Liste (FD-159); der Nachweis folgt mit dessen Fix.

### FD-78 Fachfelder in Druckvorbereitungswegen haben unvollständige Hilfen

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: tool:analysis, tool:split, finding.action:sketch.pick_plane, finding.action:generate_again, finding.action:choose_printer, finding.action:open_print_settings
- Prüfpunkt: 8, V3
- Beleg: bild-final-d8-codex.md und F:/tmp-suche/bild-final-d8-codex/2ec37b23b/FD78-hilfen-entwurf.md; frische italienische und deutsche Fälle 047/043 auf 2ec37b23. Flächenprotokolle und einzeln gelesene Originalbilder sind mit vollständigen Hashes gebunden. AnalysisBar/Analysewahl, SplitBar/Anzahl/Form/Vorbereitung und OperationDialog/Typ sind die ursprünglichen fünf Felder. Hinzu kommen „Beschreibung“ im tatsächlich geöffneten Generator und „Werte mitgeben“ im vorgeschalteten Herstellerprofilhinweis. Letzterer erscheint über zwei Inventarzeilen, ist aber derselbe Träger und zählt einmal. Alle tatsächlichen Inventarzeilen gehören D8.
- Ursache: Die Rohaufnahme zeigt an sieben unterschiedlichen Feldern eine leere zugängliche Beschreibung; Analyseauswahl, Generatorbeschreibung und Werte-Haken haben zusätzlich keine Kurzhilfe. An den vier übrigen Feldern ist ein erklärender Tooltip vorhanden. Im Slicerhinweis ist der erklärende Satz sichtbar; seine technische Zuordnung an die Hilfekanäle fehlt. Der konkrete Quellenanschluss ist noch nicht diagnostiziert; keine globale Ursache behauptet.
- Vorschlag: Vorhandene übersetzte Wirkungssätze an die zugängliche Beschreibung der tatsächlichen Eingabefelder binden. Für die drei Felder ohne Tooltip den passenden vorhandenen Wirkungssatz ermitteln und beide Hilfekanäle anbinden. Gleiche Träger, sechs Sprachen, Titelwortüberschneidung und tatsächliche Feldhilfe prüfen. Sichtbare Erklärung erhalten; nachgelagerte Drucker-/Einstellungsdialoge sind durch diese Aufnahmen nicht nachgewiesen.
- Wirkung beim Kunden: Die Erklärung der Feldwirkung fehlt in einem erforderlichen Hilfekanal, bei drei Feldern auch beim Überfahren. Eine Bildschirmleser-Ausführung wurde hier nicht durchgeführt; kein fehlender Erklärungstext im gesamten Slicerhinweis behauptet.
- Stand: behoben `ed4a7d77f` (Analyse- und Teilenleiste), `b30b74d97` (Generator, Druckhinweis, Variantenwahl); `test_bar_field_sentences.py` und `test_field_help_rest.py` je am Stand davor rot, danach grün.

### FD-79 Maßkartenzug umgeht den gemeinsamen Ereignisverteiler

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Maßkarte am Titel oder freien Hintergrund verschieben
- Prüfpunkt: 8, 19
- Beleg: review-v4-textnormalisierung-codex.md; affected-01, regulär Exit 1 mit genau drei Wächterfehlern bei 11.320 bestandenen Fällen. test_no_module_hangs_its_own_filter_on_the_application beanstandet measure_card_drag.py:205. Quellen und Wächter sind bytegleich zum Integrationskopf 2ec37b23; Bindung affected-failure-binding.json SHA a35fb03fa78f12d6b88459b35e34494e5d9f0493f5c5733a7d179c936409b6bb.
- Ursache: Die Geste installiert einen eigenen Anwendungsfilter, obwohl app.ui.app_events einen gemeinsamen, nach Ereignisarten gefilterten Verteiler bereitstellt.
- Vorschlag: Nur während der Geste die benötigten Ereignisarten über listen anmelden und über forget abmelden. Lokale Kartenfilter, QWidget-Schranke aus FD71, einmalige Verarbeitung und vollständigen Abbau erhalten.
- Wirkung beim Kunden: Zusätzliche globale Zustellung umgeht den bestehenden Architekturvertrag. Eine konkrete Verlangsamung wurde in diesem Lauf nicht gemessen; keine neue Leistungszahl behauptet.
- Stand: behoben `8f4e89fd0`; Wächter am alten Stand rot, am Fix grün; 16 neue Verhaltensfälle gegen die Originalklasse rot, am Fix grün; in welle4 `7eebc67dd`; native DE-Maßkartenfolge am echten Fenster auf welle4 `7d978c4ee` 62/62 Bedingungen.

### FD-80 Maßkartenzug sichert seinen globalen Mauszeiger nicht gegen jeden Ausgang

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Maßkarte am Titel oder freien Hintergrund verschieben
- Prüfpunkt: 8, 19
- Beleg: Derselbe gebundene Lauf; test_a_state_that_is_set_is_taken_back_on_every_path beanstandet measure_card_drag.py:181. setOverrideCursor steht vor der Bewegungsarbeit ohne finally-/with-Absicherung.
- Ursache: Ein asynchroner Zug verändert den globalen Cursorstapel und nimmt ihn nur über den gewöhnlichen _finish-Weg zurück. Der Ausnahmeweg nach dem Setzen ist nicht abgesichert; eine fremde spätere Stapelposition hat keine eigene Zuordnung.
- Vorschlag: Das vorhandene Pattern für widgetgebundene asynchrone Cursor verwenden, falls der echte gehaltene Zug außerhalb der Karte dadurch vollständig erhalten bleibt. Vorherigen eigenen oder geerbten Zustand wiederherstellen; fremde globale Overrides, Release, Escape, Fokusverlust, Reset und Lebensdauerenden gegenprüfen. Fehlerwege müssen tatsächlich aufräumen.
- Wirkung beim Kunden: Der Cursorzustand ist nicht für jeden Ausgang abgesichert. Ein konkret beim Kunden stehengebliebener Cursor wurde hier nicht beobachtet; der statische Regelverstoß ist bestätigt.
- Stand: behoben `8f4e89fd0`; Zeiger am Druckempfänger statt Override, Rückgabe auf jedem Ausgang (Escape, Hide, Fokus-/Fensterverlust, Reset, Empfängertod, Ausnahme) gegen die Originalklasse rot, am Fix grün; in welle4 `7eebc67dd`; am echten Fenster auf `7d978c4ee` trägt der Druckempfänger während des Haltens den Verschiebezeiger ohne globalen Override, nach dem Loslassen ist der alte Zeiger zurück (`native-d0-claude.md`, 2b).

### FD-81 Maßkartenprüfungen importieren private Helfer aus anderen Testmodulen

- Art: Fehler
- Schwere: leicht
- Funktion: keine Zeile: Prüfanschlüsse der Maßkarte und Platzierung
- Prüfpunkt: 8, 19
- Beleg: Derselbe gebundene Lauf; test_test_files_do_not_import_private_names_from_each_other findet in test_measure_card_placement.py fünf private Querimporte aus drei test_*-Modulen.
- Ursache: _begin, _drop, _heading, _rounds und _layout dienen mehreren Tests, liegen aber bei einzelnen Testverbrauchern statt im vorhandenen gemeinsamen tests/ui_helpers.py.
- Vorschlag: Diese Helfer samt benötigtem internem Maushelfer einmalig in das bestehende Hilfsmodul verschieben und alle Verbraucher auf sprechende öffentliche Namen umstellen. Keine Duplikate, kein neues Modul und keine Abschwächung des Wächters.
- Wirkung beim Kunden: Kein unmittelbarer sichtbarer Produktfehler belegt; die Prüfstruktur koppelt Testmodule über private Implementierung und verletzt ihren bestehenden Vertrag.
- Stand: behoben `8f4e89fd0`; Wächter der privaten Querimporte am alten Stand rot, am Fix grün; in welle4 `7eebc67dd`.

### FD-82 Testdoubles der Flächenplatzierung kennen den Maßkartenzug nicht

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Prüfanschlüsse der Flächenplatzierung
- Prüfpunkt: 19
- Beleg: Betroffener Lauf am Fixbaum von FD-79–81 (`F:\tmp-suche\fpf-liefern-claude\affected-20261014-050245.txt`): 88 rot, alle in `tests/test_surface_placement.py`, `AttributeError: 'types.SimpleNamespace' object has no attribute '_measure_drag'` an `placement_flow.py:5560`; am unveränderten `welle4` `d5b2c51df` gleich rot.
- Ursache: `0036e21ea` führte `_measure_drag.update_room` in `PlacementFlow.redraw` ein; die zwei Doubles der Datei wurden nicht nachgezogen.
- Vorschlag: Beide Doubles tragen einen stummen Zug wie ihre übrigen Maßhelfer.
- Wirkung beim Kunden: Kein Produktfehler; 88 Prüfungen der Werkzeugausrichtung an der Fläche erreichten ihre Zusicherung nicht, das Entwicklungstor wäre rot.
- Stand: behoben `0df73f13d`; `tests/test_surface_placement.py` vorher 88 von 381 rot (`AttributeError _measure_drag`), nachher 381/381 grün, gepinnt.

### FD-83 Tooltipfall des Prüfstands hängt von der Reihenfolge ab

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 19
- Beleg: `tests/test_function_bench_window.py::test_button_probe_moves_away_from_a_real_tooltip_before_testing_coverage[wortschatz|knopf]` ist allein grün und nach `test_a_double_click_reaches_a_list_as_a_double_click` im selben Prozess rot (`verdeckt: feature:resize_hole … qtooltip_label`), am unveränderten `2ec37b23b` genauso (`F:\tmp-suche\fpf-liefern-claude\order-b.txt`, `order-c.txt`).
- Ursache: `QtPorts.press(…, "double")` schickte nach `mouseClick` und `mouseDClick` kein Loslassen; bis zum nächsten Klick galt die linke Taste als gedrückt, jede Bewegung bis dahin war ein Zug ohne Enter und Leave, und der Tooltip des vorigen Ziels blieb über dem nächsten stehen.
- Vorschlag: Ursache am Ablauf belegen und an der Wurzel beheben, Gegenprobe in derselben Datei in beiden Reihenfolgen.
- Wirkung beim Kunden: Kein Produktfehler; ein Fenstertest wird im Release-Tor reihenfolgeabhängig rot. Die Urteile des 48-Fall-Laufs verfälscht es nicht: In `phase_revise` folgt dem Doppelklick der Klick ins erste Dialogfeld, jede weitere Phase beginnt mit Klicks.
- Stand: behoben `001effdcd`; Tooltipfall nach dem Doppelklickfall am alten Stand rot, am Fix in beiden Reihenfolgen grün, neue Zusicherung ohne gedrückte Taste; in welle4 `fe8f5bcd7`. Rückfallzweig (Widget im Doppelklick abgebaut) mit Fall `5c138af29`, Kommentar und Docstring `0f93ad296` (Review RD-2/RD-3).

### FD-84 Maßfelder fallen bei Platzmangel unter den Bildrand und über den Bewegungsgriff

- Art: Fehler
- Schwere: mittel
- Funktion: `resize_hole`
- Prüfpunkt: 7
- Beleg: Elf Fenstertests offscreen rot an welle4 `7eebc67dd` und schon an `0036e21ea` (`tests/test_measure_card_placement.py`, `test_placement_dimensions.py::test_the_dimension_fields_leave_the_movement_handle_alone` nach dunklem Thema); neuer Fall `test_a_tall_card_leaves_as_many_rows_as_the_fields_need` am Original 4 failed, fünftes Feld bei `QRect(12, 1072, 471, 12)` in einer 1920 × 1080 großen Ansicht, deren Raum bei 1067 endet; am 900 × 600-Fall Mittenbeschriftung bei (12, 78) über dem Griff (234, 84, 433, 433). Belege in `output/konsolidierung-2026-10-12/fd84-claude.md`.
- Ursache: Die Maßkarte hielt fest eine Feldzeile frei, gleich wie viele Felder hineinmussten; die Notreihen brachen ohne Prüfung der Unterkante um und wichen nur dem Setzpunkt aus, nicht dem Bewegungsgriff. Offscreen ausgelöst durch breitere Schrift mit Stylesheet, dazu zwei Testbauannahmen über Schriftbreiten und ein stehen gebliebenes dunkles Thema aus `customer_theme`.
- Vorschlag: Freihaltung nach den Zeilen, die die Felder brauchen (`measure_field_places.rows_height`), Notanordnung je Feld am ersten freien Platz im Bild mit Stufen vom Abstand bis zum Überdecken (`emergency_places`); Testziele aus dem freien Raum statt fester Punkte; Aussehen nach jedem Fall zurückgeben.
- Wirkung beim Kunden: Bei schmalem Bildraum, kleinem Bildschirm oder langer Sprache stand ein Maßfeld außerhalb der Ansicht oder über dem Bewegungsgriff, dessen Pfeile und Ringe dann nicht mehr auf den Zeiger reagierten.
- Stand: behoben `377f1b552`, Testbau `cbc883304`, Nachzug `c5b25728f`, Themenleck zentral über `bf3c6d5e8`; in welle4 `b4e515c7b`, gezielt 580 grün am gemergten Stand. Schlussreview D0: Grifffall mit echter Schrift `c87e0b166` — ohne `marked.append(grip)` rot unter Windows offscreen und mit DejaVu Sans wie in der Linux-CI; der Fall aus `dabd95e26` war das nur in Windows' schriftloser Offscreen-Lage (Review 2, RF-15). Changelog 0.6.1 `37801525b`; der letzte Rückfall der Notanordnung legt ein Feld neben der Karte versetzt über die anderen und deckt keines ganz (`ccb9bd87f`, `ed2ba4504`).

### FD-85 Abhakliste lässt einen offenen Fund hinter einem älteren behobenen verschwinden

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 19
- Beleg: Erster Validatorlauf der D4-Urteile (`F:\tmp-suche\urteile-d04-claude\validate-1.log`): `resize_hole` Prüfpunkt 1 zeigte FD-29 als behoben, obwohl FD-34 zum selben Punkt offen ist; neuer Fall in `tests/test_function_report.py` am alten Code rot (FD-1 statt FD-2).
- Ursache: `function_report._finding_for` nahm je Zeile und Prüfpunkt den Fund mit der kleinsten Nummer, unabhängig vom Stand.
- Vorschlag: Ein offener Fund geht jedem behobenen vor; sonst bleibt der älteste.
- Wirkung beim Kunden: Kein Produktfehler; eine Zelle der Abhakliste galt als erledigt, obwohl ein offener Fund sie offen halten muss.
- Stand: behoben `b5363624b`; in welle4 `c68df3f95`, test_function_report 260/260.

## Stufe-B-Urteilsrunde am finalen Lauf und Folgefunde (FD-86 bis FD-142)

Lauf `F:\tmp-suche\probelauf-d0-final-2ec37b23b-fortsetzung-03` auf
`2ec37b23b` (kurz „Lauf“, Bilder unter `cases/`), Urteilsberichte
`output/konsolidierung-2026-10-12/urteile-d04-claude.md`, `urteile-d08-claude.md`,
`urteile-d10-claude.md`, `urteile-zweit-claude.md`; Zuordnung in `funde-neu-claude.md`.
Mittlere und systemische leichte Funde trägt D0 (RM-737), leichte einer Zeile ihr Paket.

### FD-86 Tab verlässt die Maßgruppe vor Sammelhaken, Übernehmen und Abbrechen

- Art: Fehler
- Schwere: mittel
- Funktion: `resize_hole`
- Prüfpunkt: 10
- Beleg: Lauf 001/function.json#tab_chain: Durchmesser → Tiefe → Weitere Werte → Griff der Objektkarte (außerhalb); der vorn sichtbare Sammelhaken, Übernehmen und Abbrechen kommen in der Kette nicht vor; Bild 001/02-flaeche.png (d04 Nr. 1, zweit Nr. 3).
- Ursache: am Code naheliegend, am Lauf nicht belegt: `PlacementFlow` legt Übernehmen, Abbrechen und den Sammelbereich beim Aufbau an (`placement_flow.py:2746–2763`), die Felder entstehen später im Rollbereich; Qt reiht sie in der Fokuskette hinter die Knöpfe, und nach dem letzten Feld folgt ein später entstandenes Widget außerhalb der Karte.
- Vorschlag: Nach jedem Aufbau der Maßgruppe die Tab-Folge Felder → Weitere Werte → Sammelhaken → Übernehmen → Abbrechen setzen (`QWidget.setTabOrder`) und an der Karte schließen; Test über Tab-Druck und `focusWidget()`.
- Wirkung beim Kunden: Mit der Tastatur erreicht er Übernehmen und Abbrechen der Maßgruppe nicht und landet in einer anderen Karte.
- Stand: behoben `b7bdc571c`; `tests/test_measure_card_keys.py` am Stand davor rot (nach „Weitere Werte“ der Kartengriff „Objekte“, Haken unter den Knöpfen), danach Felder → Weitere Werte → Sammelhaken → Übernehmen → Abbrechen → erstes Feld; nativer Nachweis der Fokusrahmen und des Sammelhakens in langen Sprachen im Schlusslauf (Plan Punkt 37).

### FD-87 Die Maßgruppe springt im Fehlfall an den Plattenrand

- Art: Gestaltung
- Schwere: leicht
- Funktion: `resize_hole`
- Prüfpunkt: 7, G8
- Beleg: Lauf 001/03-uebernommen.png gegen 001/04-fehlfall.png bei gleicher Kamera; Ausschnitte `F:\tmp-suche\urteile-d04-claude\crops\001-03-ueberblick.png` und `001-04-ueberblick.png` (d04 Nr. 2).
- Ursache: offen; fest steht, dass die Karte mit der Ablehnung höher wird und danach ohne Übergang an anderer Stelle steht.
- Vorschlag: Bei wachsender Karte die gewählte Lage halten und nur so weit verschieben, wie der Platz verlangt; der Wechsel mit Übergang aus `motion`.
- Wirkung beim Kunden: Das Feld, das er gerade korrigiert, springt an eine andere Stelle des Bilds.
- Stand: behoben `b58241193`, `fc82ee4be`; `tests/test_measure_card_growth.py` am Stand davor rot (die gewachsene Karte sprang 125 bzw. 281 Punkte), danach bleibt die Ecke, und die Karte gleitet (`grown_place`, `motion.glide`); nativer Nachweis der Gleitbewegung im Schlusslauf (Plan Punkt 37).

### FD-88 Die Ablehnung der Maßgruppe steht dreimal da

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `resize_hole`
- Prüfpunkt: 7, E5
- Beleg: Lauf 001/04-fehlfall.png: derselbe Satz unter dem Feld, über der Knopfzeile der Maßgruppe und in der Statusleiste (d04 Nr. 2).
- Ursache: offen; Feldablehnung, Hinweis der Maßgruppe und Statuszeile setzen je denselben Satz. Verwandt mit FD-32 (Sperrgrund zweimal), andere Stelle.
- Vorschlag: Der Satz steht am Feld; Maßgruppe und Statusleiste wiederholen ihn nicht.
- Wirkung beim Kunden: Derselbe Satz dreimal lenkt vom Feld ab, das er ändern muss.
- Stand: behoben `47b58a2da` (Karte), `08dea68c3` (Statusleiste); `test_measure_card_note.py` und `test_measure_refusal_status.py` je am Stand davor rot (Satz im Hinweis und in der Statusleiste, obwohl er unter dem Feld steht), danach grün.

### FD-89 „seit dem letzten Schritt“ meldet auch eine geänderte Rechengrundlage

- Art: Fehler
- Schwere: mittel
- Funktion: `statusbar`
- Prüfpunkt: 6
- Beleg: `F:\tmp-suche\urteile-d04-claude\crops\status.png`: Szene `merkmal.hole.exakt` ohne Änderung erst 11 g · 20 min (037–042 countersink_hole), später 8,9 g · 14 min mit „−2,2 g seit dem letzten Schritt“ (detect_region, alle Sprachen), ohne dass ein Schritt dazukam; dieselbe Ausgangsszene 18 g · 32 min in 004, 007, 016, 019 gegen 14 g · 23 min in 001 (d04 Nr. 3 b, c).
- Ursache: am Code belegt, dass die Zahl nicht nur nach einem Schritt neu entsteht: `_update_facts` läuft nach jeder Auswertung und noch einmal, wenn die Druckgrundlage des gewählten Prozesses eintrifft (`main_window.py:26382`), dann mit anderen wirksamen Einstellungen; `PrintFacts.show_estimate` vergleicht jede neue Schätzung mit der vorigen und nennt die Differenz „seit dem letzten Schritt“ (`facts.py:125–149`). Dass im Lauf genau die Grundlage die Zahl verschob, ist naheliegend, nicht gemessen.
- Vorschlag: Die Differenz nur zwischen zwei Dokumentständen mit derselben Rechengrundlage bilden; ändern sich die Einstellungen, wird der Vergleichswert still neu gesetzt. Die Zahl erst zeigen, wenn die wirksamen Einstellungen feststehen, oder als vorläufig kennzeichnen.
- Wirkung beim Kunden: Die Zeile meldet eine Ersparnis durch einen Schritt, den es nicht gab, und dieselbe Szene zeigt je nach Zeitpunkt andere Gramm und Minuten.
- Stand: behoben `877a11ce2`, `e9831a8e0`; `test_facts_basis.py` am Stand davor rot (5 von 5, „+836 g seit dem letzten Schritt“ ohne Schritt) und `test_foundation_crash_window.py` am Stand davor rot (nach einem Absturz des Grundlagenarbeiters gilt Solidons Tabelle), danach grün.

### FD-90 Die Zahlenzeile der Statusleiste wird abgeschnitten

- Art: Gestaltung
- Schwere: leicht
- Funktion: `statusbar`
- Prüfpunkt: 9
- Beleg: Lauf 001/01-vorher.png „14 g ·“; detect_region 037–042: Summe links abgeschnitten („· 14 min“), die deutsche Differenz endet in „Schrit…“ (`F:\tmp-suche\urteile-d04-claude\crops\status.png`, d04 Nr. 3 a).
- Ursache: offen; Statusmeldung und Zahlenzeile teilen sich die Statusleiste, und die Breite der Zahlenzeile folgt ihrem Text nicht verlässlich.
- Vorschlag: Mindestbreite aus beiden Texten der Zeile; gekürzt wird zuerst die Statusmeldung.
- Wirkung beim Kunden: Material und Dauer sind nur zum Teil lesbar.
- Stand: behoben `916990010`; `test_status_line_room.py` am Stand davor rot (Differenz 239 von 372 px), danach grün; nativer Nachweis mit Windows-Schrift im Schlusslauf (Plan Punkt 38).

### FD-91 Die Kopfzeile kürzt den Druckernamen trotz freier Fläche

- Art: Gestaltung
- Schwere: leicht
- Funktion: `header`
- Prüfpunkt: 9, Z6
- Beleg: Lauf 007/flaeche-skalierung.png (`F:\tmp-suche\urteile-d04-claude\crops\007-kopf-rechts.png`) und 013/flaeche-skalierung.png bei 1920 × 1009: „Elegoo …rbon 2 · FDM“, links davon breite freie Fläche (d04 Nr. 4, d10 Nr. 2).
- Ursache: offen.
- Vorschlag: Das Profilfeld der Kopfzeile nach seinem Inhalt bemessen und erst kürzen, wenn die Zeile voll ist; der volle Name im Tooltip.
- Wirkung beim Kunden: Auf der kleinsten Arbeitsfläche ist der gewählte Drucker nicht lesbar.
- Stand: behoben `7aa4f4b85`; `test_header_room.py` am Stand davor rot („…· FDM“ bei 1128 px), danach grün; nach einem Schriftwechsel misst die Kopfzeile neu (`40c9a5840`, `885998851`); nativer Nachweis mit Windows-Schrift im Schlusslauf (Plan Punkt 38).

### FD-92 Die Bettmaßzahlen folgen der Anzeigeeinheit nicht

- Art: Verständlichkeit
- Schwere: mittel
- Funktion: keine Zeile: Druckbett in der 3D-Ansicht
- Prüfpunkt: 9
- Beleg: Lauf 004/flaeche-zoll.png (`F:\tmp-suche\urteile-d04-claude\crops\004-bett.png`): „0“, „100“ ohne Einheit bei Zollanzeige; 006/flaeche-zoll.png: „50“ (`F:\tmp-suche\urteile-d10-claude\crops\006-bett50.png`); Kopf und Baum zeigen Zoll (d04 Nr. 5, d10 Nr. 1).
- Ursache: belegt: `bed_scale` schreibt `f"{value:.0f}"` in Millimetern, ohne Anzeigeeinheit und ohne Einheitenzeichen (`viewport.py:2808–2812`). Zwilling zu FD-69 (Farbe derselben Zahlen), andere Ursache.
- Vorschlag: Die Zahlen über den Längenformatter der Anzeige setzen, Schrittweite passend zur Einheit, das Einheitenzeichen einmal an der Skala; beim Einheitenwechsel neu zeichnen.
- Wirkung beim Kunden: In Zoll liest er Millimeterzahlen ohne Hinweis und schätzt Größe und Lage falsch ein.
- Stand: behoben `3d29abed1`; `test_bed_scale_unit.py` am Stand davor rot (der Einheitenwechsel baute die Bettzahlen nicht neu), danach Zahlen in Zoll mit Einheit einmal an der Vorderkante, hell und dunkel offscreen gelesen; Schwere mittel wie FD-61 und FD-125 (Review RD-6); nativer Nachweis im Zollfall des Schlusslaufs (Plan Punkt 9).

### FD-93 Die Auswahlkarte hält am Katalogknopf Leerraum

- Art: Gestaltung
- Schwere: leicht
- Funktion: `resize_feature`, `countersink_hole`
- Prüfpunkt: 19, Z6
- Beleg: Lauf 037–042 resize_feature: am Zapfen rund 75 px leer zwischen „Prüfstück erzeugen“ und „Filament und Druck“, in allen Sprachen (`F:\tmp-suche\urteile-d04-claude\crops\037-resize_feature-karte.png`); an der Bohrung PT rund 35 px, IT rund 8 px vor „Blocos adequados …“ (`042-countersink-karte.png`) (d04 Nr. 6).
- Ursache: offen; Verdacht: Der Platz des Katalogknopfs „Passende Bausteine …“ (`selection_operations.py`) bleibt reserviert, wenn der Knopf fehlt, und ist bei umbrochenem Text höher als nötig.
- Vorschlag: Ursache am Layout belegen; die Höhe aus dem sichtbaren Inhalt.
- Wirkung beim Kunden: Leere Fläche schiebt „Filament und Druck“ nach unten, auf kleinen Schirmen unter den Rand.
- Stand: behoben `b1df5efb3`; `test_selection_card_room.py` am Stand davor rot (77 Punkte), danach grün; Bild hell und dunkel.

### FD-94 Eingabefelder tragen keinen zugänglichen Namen

- Art: Fehler
- Schwere: mittel
- Funktion: `pin_for_bore`, `plug_hole`, `drill_hole`, `pattern_feature`, `Bearbeiten/Parameter anlegen …`
- Prüfpunkt: 10
- Beleg: `F:\tmp-suche\urteile-d04-claude\felder-je-sprache.txt`: leerer `accessible_name` an der Auswahl „Bohrung“ (Stift, Verschließen), am Langloch-Haken (Bohren) und an „Art“ (Muster); die Listen „Zellen“ und „Merkmale“ heißen zugänglich „Ganzer Körper“. Lauf 003/function.json#names: Namens- und Wertfeld des Parameterdialogs heißen nach ihrem Inhalt „breite“ und „40,00“ (d04 Nr. 7, zweit Nr. 2).
- Ursache: belegt: `_explain` gibt Namen nur an innere Felder eines Behälters (`op_dialog.py:1389–1397`); ein Auswahlfeld oder Haken, der selbst der Editor ist, bleibt ohne Namen, und der Flächenwähler reicht den Namen seines Hakens weiter. Im `ParameterDialog` tragen Name, Wert, Ausdruck und Grenzen keinen Namen, nur die Einheit (`dialogs.py`). Der Prüfstand fällt dann auf den Text zurück.
- Vorschlag: Ein Weg für alle Formulare: Jedes Eingabefeld bekommt den Text seiner Beschriftung als `accessibleName`, auch der Editor selbst und die Liste im Flächenwähler; Wächter über alle Operationsdialoge und den Parameterdialog.
- Wirkung beim Kunden: Ein Bildschirmleser nennt das Feld nicht oder liest nur seinen Inhalt vor.
- Stand: behoben `1524e1ddb` (Formulare), `73e1ba16c` (Operationsdialog), `22f55de98` (Partner nach Variantenwechsel); `test_form_fields.py` und `test_operation_dialog_names.py` je am Stand davor rot (183 von 190 Dialogen mit einem Feld ohne oder mit doppeltem Namen), danach grün.

### FD-95 Die Absage im Operationsdialog wiederholt ihren Titel als „Art:“ und nennt Wege nur als Satz

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `group_pattern`, `create_label`, `split_bodies`, `finding.action:correct_input`, `finding.action:sketch.pick_plane`
- Prüfpunkt: 7, V1, V5
- Beleg: Lauf 037–042 group_pattern-dialog: „Art: Die Eingabe war so nicht verwendbar.“, „Eingabe korrigieren“ als Text, dazu „Details anzeigen“; 031/flaeche-de-create_label-1c3131b4-dialog.png ebenso in allen Sprachen; 043/flaeche-de-split_bodies-e45b38ac-dialog.png: „Art: Ein Wert liegt außerhalb des zulässigen Bereichs“; 043/flaeche-geoeffnet-de-finding.action_correct_input-9a5b98d1-dialog.png und …sketch.pick_plane-ad8b805d-dialog.png: „Eingabe korrigieren“ und „Eine andere Ebene wählen“ als bloßer Text (d04 Nr. 8, d10 Nr. 12, d08 N4, N11).
- Ursache: belegt: `problem_text` setzt die Werte des Fehlers über `spoken_values` darunter, und `kind` ist bei einem Schrittfehler dessen Titel (`_finding_from`); nur der Haltweg nimmt ihn heraus (`session.py:2772–2779`, KUNDE-12), der Dialog nicht (`dialogs.py:3274–3337`). Vorschläge ohne Handler setzt `unhandled_advice` als Satz, auch „Eingabe korrigieren“ in dem Dialog, der selbst die Eingabe ist. FD-44 deckte nur den Ursachencode.
- Vorschlag: `kind` bei `op.*`-Fehlern zentral in `spoken_values` auslassen, eine Quelle für Halt und Dialog; `show_refusal` löst „Eingabe korrigieren“ als Sprung ins Feld aus `values["field"]` ein und lässt es sonst weg; „Eine andere Ebene wählen“ als Handler des Ebenendialogs.
- Wirkung beim Kunden: Eine Fachzeile doppelt den Titel, und der Weg aus der Absage steht als Text da, den man nicht klicken kann.
- Stand: behoben `1c9b1d9cc`, `72cbf7705`; `test_refusal_details.py` und KUNDE-12 (`test_evaluation.py::test_the_halt_refusal_does_not_repeat_its_sentence`) je am Stand davor rot, danach ohne Titelwiederholung, *Eingabe korrigieren* springt ins Feld; beide Wege hält `test_field_ways_both_paths_window.py`.

### FD-96 Der i-Knopf der Merkmalzeilen ist ein Buchstabe statt eines Symbols

- Art: Gestaltung
- Schwere: leicht
- Funktion: `move_feature`, `duplicate_feature`, `rotate_feature`, `resize_feature`
- Prüfpunkt: 19, G4, G7
- Beleg: Stufe-A-Rohfund G4/G7 an den vier Zeilen in allen Sprachen (Schrift 9 pt, Gewicht 600), Lauf 037–042 (d04 Nr. 9).
- Ursache: belegt: `FeaturePanel` setzt `dot.setText(tr("i"))` an einem flachen `QToolButton` (`panels.py:11303–11309`).
- Vorschlag: Symbol aus dem eigenen Satz (`icons`); Tooltip, zugänglicher Name und Sprung ins Handbuch bleiben.
- Wirkung beim Kunden: Der Knopf wirkt wie ein Schriftzeichen und fällt neben den Symbolen aus dem Stil.
- Stand: behoben `a94e9307d`; `test_info_dot.py` am Stand davor rot, danach Symbol statt Buchstabe; Bild hell und dunkel.

### FD-97 Abkürzungen verhindern Satzenden an Wortenden

- Art: Fehler
- Schwere: leicht
- Funktion: `pin_for_bore`, `finding.action:orient_for_print`
- Prüfpunkt: 9, E5
- Beleg: Lauf 039 und 042 pin_for_bore-dialog: ES und PT zeigen zwei Einleitungssätze, DE/EN/FR/IT einen; 045/flaeche-geoeffnet-es-finding.action_orient_for_print-a1ca663b-dialog.png: ES mit zweitem Satz (d04 Nr. 10, d08 N19).
- Ursache: belegt: `sentences` maskiert die Abkürzungen per Teilzeichenkette (`surfaces.py:935–971`); „ca.“ trifft das Wortende von „rosca.“ (ES/PT, Stift) und „placa.“ (ES, Druckoptimal), der Satz endet dort nicht, und `lead_sentence` nimmt zwei. Dieselbe Funktion schneidet Menü, Statuszeile, Suche und den Längenwächter.
- Vorschlag: Abkürzungen nur als ganzes Wort maskieren (Wortgrenze davor); Test mit „rosca. Es“ und „placa. Cada“.
- Wirkung beim Kunden: Über dem ersten Feld steht in zwei Sprachen ein Satz mehr, und Menü- und Suchtexte schneiden dort anders als in den übrigen Sprachen.
- Stand: behoben `5aafd2b56`; `test_text_length.py::test_sentences_are_counted_as_a_reader_counts_them` mit „rosca. Es“ und „placa. Cada“ am Stand davor rot, danach grün.

### FD-98 Der Zapfen heißt in fünf Sprachen klein

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `resize_feature`
- Prüfpunkt: 9
- Beleg: Lauf 038–042 resize_feature, Kartenkopf und Baum: „peg · Ø6,00 mm“, „espiga“, „tenon“, „perno“, „pino“ (d04 Nr. 11).
- Ursache: belegt: Der Katalogeintrag „Zapfen“ ist in en, es, fr, it und pt klein übersetzt; die übrigen Merkmalsarten aus `registry.py:540–575` sind groß.
- Vorschlag: Die fünf Katalogwerte groß; braucht ein Satz das Wort klein, ein zweiter Schlüssel mit Kontext.
- Wirkung beim Kunden: Der Kopf der Karte beginnt klein und sieht wie ein Fehler aus.
- Stand: behoben `8718ddd59`; `test_catalog_terms.py::test_every_feature_kind_starts_with_a_capital_letter` am Stand davor in fünf Sprachen rot, danach grün.

### FD-99 Übernehmen vor der ersten Änderung ist je Fläche anders, im Änderungsweg grau ohne Grund

- Art: Zwillinge
- Schwere: mittel
- Funktion: `resize_hole`, `resize_feature`, `finding.action:change_creating_step`
- Prüfpunkt: E7
- Beleg: Lauf 037/flaeche-de-countersink_hole-4a325b8d.png: „Bohrung im ursprünglichen Schritt ändern“ rechts offen mit orangem Übernehmen ohne Änderung, ebenso „Merkmal ändern“ am Zapfen (`F:\tmp-suche\urteile-d04-claude\crops\037-resize_feature-karte.png`) und „Fläche versetzen“ bei 0 mm; die Maßgruppe im Bild (037/flaeche-de-remove_feature-29cd30d1.png) grau ohne Satz (FD-31); 043/flaeche-geoeffnet-de-finding.action_change_creating_step-87b7204a-dialog.png: Gewindedialog im Änderungsweg, Hauptknopf „Einsetzen“, grau ohne Grund, alle Sprachen (d04 Nr. 13, d08 N9).
- Ursache: Zwilling zu FD-31: Maßgruppe und Änderungsdialog warten auf eine Änderung und sagen es nicht, Merkmalfenster und Flächenkarte bieten Übernehmen ohne Änderung an. Der Änderungsweg öffnet über `edit_operation` (`main_window.py:27826–27838`) den Dialog des Bausteins, dessen Hauptknopf `accept_text` „Einsetzen“ nennt (`op_dialog.py:249–251`), auch wenn ein bestehender Schritt geändert wird.
- Vorschlag: Mit FD-31 eine Regel für alle Flächen: vor der ersten Änderung grau mit dem Satz, der das erste Feld nennt; im Änderungsweg heißt der Knopf „Übernehmen“.
- Wirkung beim Kunden: Einmal geht Übernehmen ohne Änderung, einmal ist es grau ohne Satz, und im Änderungsweg sagt der Knopf „Einsetzen“.
- Stand: behoben `38ab43c4f`, `04c528bef`, `6dfa1d7f5` (Operationsdialog), `ce8390478` (Merkmalfenster, Flächenkarte), `66e6d75df` (Anschluss `edit_operation`); `test_operation_dialog_change.py`, `test_feature_first_change.py`, `test_offered_unchanged.py` und `test_change_step_window.py` je am Stand davor rot („Einsetzen“ statt „Übernehmen“), danach im Änderungsweg *Übernehmen*, grau bis zur ersten Änderung; das Bild der Kurzhilfe nimmt der Prüfstand seit `3a70b3806` auf; nativer Nachweis im Schlusslauf (Plan Punkt 8).

### FD-100 Die Auswahlmatrix fragt das Ziel ohne den Weg der Zeile ab

- Art: Fehler
- Schwere: mittel
- Funktion: `resize_hole`, `finding.action:place_on_bed`
- Prüfpunkt: 13
- Beleg: Lauf 001/function.json#matrix: an ein_merkmal „QToolButton steht nicht da“, an den übrigen Stufen „fehlt“, obwohl die Maßgruppe *Bohrung ändern* im Bild steht (001/02-flaeche.png); 002/function.json#matrix: an allen Stufen „kein Bedienelement trägt dieses Kennzeichen“ (d04 Nr. 15, zweit Nr. 1).
- Ursache: belegt: `phase_matrix` klickt nur die Auswahl und fragt dann `offer_state(target)` (`function_bench.py:1516–1594`), ohne die Vorbereitungsklicks aus `Row.route` (Reiter, Klappe, Befund) und ohne die Zuordnung der Maßgruppe im Bild, die der Prüfstandsfix zu FD-29 (`0b1e61346`) nur für den Ort einführte.
- Vorschlag: Die Matrix geht denselben Weg wie die Hauptphase: Route bis vor das Ziel, die Maßgruppe im Bild als Ort der Handlung; der Gegenfall „fehlt“ bleibt.
- Wirkung beim Kunden: Prüfpunkt 13 ist an zwei von drei Hauptzeilen unmessbar; ein Kundenfehler ist daraus nicht belegt.
- Stand: behoben `dd20ed8f2`; `test_function_matrix_way.py` am Stand davor rot, danach geht die Auswahlmatrix nach jeder Stufe den Weg der Zeile.

### FD-101 Zeilen ohne Weg oder passende Startszene

- Art: Fehler
- Schwere: mittel
- Funktion: `slot_hole`, `feature.apply`, `feature.in_view`, `feature.every`, `dialog:local_recognition_dialog`, `group_pattern`, `arrange_bed`, `check_collisions`, `orient_for_print`, `finding.action:install`, `finding.action:keep_saved_parts`, `finding.action:recognize_fully`, `dialog:body_choice_dialog`, `dialog:seal_path_dialog`, `dialog:step_values_dialog`, `dialog:binding_dialog`, `dialog:calibration_dialog`, `dialog:counterpart_dialog`, `dialog:parameter_dialog`, `dialog:recipe_dialog`, `dialog:slicer_filament_dialog`, `meldung:_pick_colour`, `meldung:_replacement_slot`, `meldung:action_counterpart`, `menu:parameters.edit`
- Prüfpunkt: 1, 2
- Beleg: D4-Stufe A (`F:\tmp-suche\urteile-d04-claude\stufe-a-dump.txt`): „… steht nicht da, und kein Weg führt hin“ an feature:slot_hole, feature.apply, feature.in_view, feature.every; group_pattern an `quader.exakt` ohne gleiche Einzelmerkmale; D8: neun Zeilen ohne Fläche (Lauf 043/surfaces/<zeile>.json#steps); D10: zehn Zeilen ohne Weg zu ihrem Fenster, menu:parameters.edit mit leerer Route (d04 Nr. 8, Nr. 15, d08 N22, d10 Nr. 10).
- Ursache: Funktionsliste und Szenenkatalog (`tests/data/function_rows/`, `tools/function_scenes.py`): leere Route, eine Route, die einen Körper wählt, an dem die Handlung nicht gilt, oder eine Startszene ohne den Befund oder die Merkmale. Die Fußknöpfe des Merkmalfensters gibt es nur bei offener Zeile; *Zum Langloch ziehen* fehlt rechts, solange der Bohrschritt im Bild steht (gewollt, `panels.py` `set_measuring`).
- Vorschlag: Je Zeile Route und Szene so ergänzen, dass die Fläche entsteht (offene Merkmalzeile vor den Fußknöpfen, Rechtsklick für `menu:`, Szene mit Befund oder gleichen Merkmalen); Wächter: keine Zeile der Liste ohne erreichte Fläche.
- Wirkung beim Kunden: Diese Zeilen bleiben ungemessen; ein Kundenfehler ist daraus nicht belegt.
- Stand: behoben `7ddca9f81`, `aa1e8399b`, `22e33f61a`, `308721dcd`, `5979d993e`, `afd9b7756`, `88dcda6e3`, `f61bfc4a8`; jede Zeile von D4, D8 und D10 hat Startszene und Weg zu ihrer Fläche, Wächter `test_function_rows_reach.py` am Stand davor rot, offscreen erreicht der Sprachfall jede dieser Flächen; die übrigen Pakete trägt FD-175; Bilder am echten Fenster im Schlusslauf (Plan Punkt 32).

### FD-102 Ein verborgenes Feld ohne Namen macht V3 rot

- Art: Fehler
- Schwere: leicht
- Funktion: `move_feature`, `duplicate_feature`, `resize_feature`
- Prüfpunkt: V3
- Beleg: Stufe A an den drei Zeilen, Lauf 037–042: je ein Feld ohne Titel, Kurzhilfe und Beschreibung, das im Bild nicht zu sehen ist (d04 Nr. 15).
- Ursache: offen; fest steht, dass das gezählte Feld im Bild nicht sichtbar ist.
- Vorschlag: Ursache am Flächenprotokoll belegen: Zählt der Prüfstand verborgene Felder, zählen nur sichtbare; ist es ein sichtbares Feld ohne Fläche, wird es entfernt.
- Wirkung beim Kunden: Falscher V3-Fund an drei Zeilen; kein Kundenfehler belegt.
- Stand: behoben `40c38dfb0`; kein Produktfehler; `test_function_capture_reach.py` (ein verborgener Haken zählt nicht, einer hinter der Klappe schon) am Stand davor rot, danach grün.

### FD-103 Ein Behälter der Maßgruppe hält Qts Abstand 6

- Art: Aufräumen
- Schwere: leicht
- Funktion: `resize_hole`
- Prüfpunkt: G2
- Beleg: Stufe A, Lauf 001: QWidget#5 der Maßgruppe mit `spacing` 6 bei einem Element (d04 Nr. 16).
- Ursache: am Code naheliegend: `_measure_scope_layout` setzt Ränder, aber keinen Abstand (`placement_flow.py:2760–2762`); Zwilling zu FD-23, das die Karten in `panels.py` auf das Raster brachte.
- Vorschlag: Abstand aus dem Raster setzen; der G2-Wächter schließt die Maßgruppe ein.
- Wirkung beim Kunden: Keine sichtbare; das Raster ist nicht überall gesetzt.
- Stand: behoben `c678ff6df`; `test_style.py::test_every_layout_of_a_dialog_keeps_the_grid` liest jetzt `placement_flow.py` und war am Stand davor rot (drei Layouts mit Qts 6), danach grün.

### FD-104 Befundhandlungen hinter einer angehaltenen Kette werden angeboten und scheitern

- Art: Fehler
- Schwere: mittel
- Funktion: `finding.action:mesh_to_exact`, `finding.action:orient_for_print`, `finding.action:resolve_intersections`, `finding.action:split_bodies`
- Prüfpunkt: 7, 15, E7, V5
- Beleg: Lauf 043/flaeche-geoeffnet-de-finding.action_mesh_to_exact-ef335aaf-dialog.png und …orient_for_print-a1ca663b-dialog.png: Hauptknopf grau ohne Grund im Dialog; …resolve_intersections-6c1a6470-dialog.png und …split_bodies-b73ef166-dialog.png: Absage erst nach dem Klick über den Haltdialog; alle Sprachen (d08 N1).
- Ursache: offen; fest steht: Die Handlungen hängen einen Schritt hinten an, und erst der Haltweg der Sitzung sagt ab („Die Kette hält an — ein neuer Schritt dahinter würde nicht gerechnet.“, `session.py:2781`). Der Bericht fragt den Halt vor dem Anbieten nicht — das Muster von FD-5.
- Vorschlag: Vor dem Anbieten fragen, ob die Handlung hinter dem Halt landen würde; dann vor dem Halt einfügen wie *Reparieren und erneut versuchen*, oder grau mit dem Halt als Grund und dem Weg dorthin.
- Wirkung beim Kunden: Er klickt die angebotene Lösung und bekommt eine Absage oder einen grauen Knopf ohne Satz.
- Stand: behoben `dced53d01` (Fenster), `5e233623f` (Bericht und Kontextmenü), `c6eaf7d58` (die Wege des haltenden Befunds); `test_halt_refusal_window.py`, `test_halted_report_offers.py` und `test_halt_ways_window.py` je am Stand davor rot, danach grau mit Grund vor dem Dialog.

### FD-105 Rohdaten im Kundentext

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `finding.action:show_details`, `finding.action:show_step_values`, `finding.action:calibrate_material`
- Prüfpunkt: V1
- Beleg: Lauf 043/flaeche-geoeffnet-de-finding.action_show_details-6ec9f9d7-dialog.png: Koordinaten „1.3325671035519837e-16“ ohne Einheit und „obj_1“; …show_step_values-6402e83f-dialog.png: Operationsname „paint_slot“ und Rohschlüssel; 043/flaeche-de-finding.action_calibrate_material-8295cd40.png: Berichtszeile „— Quader · obj_1 · obj_2“; alle Sprachen (d08 N2).
- Ursache: offen; die drei Ausgaben setzen Werte und Kennungen ohne `value_line` und Anzeigenamen.
- Vorschlag: Werte über `value_line` mit Einheit und Rundung der Anzeige, Körper mit Namen, Operationen mit Titel.
- Wirkung beim Kunden: Interne Kennungen und Fließkommazahlen statt verständlicher Angaben.
- Stand: behoben `4df8bd536` (Passungsbefunde), `321a33b6f` (Einzelheiten, Schrittwerte), `662283167` (Berichtszeile), `fec33ba89` (Kopieren); die Tests je am Stand davor rot, danach nennen Bericht und Dialoge Körper, Schritt und Stelle in Fensterwörtern.

### FD-106 „Passt bereits auf das Bett“ steht auch neben einem Teil, das nicht passt

- Art: Fehler
- Schwere: mittel
- Funktion: `finding.action:release_protection`, `finding.action:split_along_line`
- Prüfpunkt: 6, V5
- Beleg: Lauf 043/flaeche-de-finding.action_release_protection-34d13d85.png und …split_along_line-0458b46f.png: Statuszeile „Dieses Objekt passt bereits auf das Bett.“ neben der Warnung „über den Bauraum hinaus … 172,00 mm“ (d08 N3).
- Ursache: belegt: `_split_done` setzt den Satz, sobald die Teilung keine Transaktion liefert (`main_window.py:9089–9091`), gleich aus welchem Grund, auch wenn kein Schnitt möglich war.
- Vorschlag: Den Satz nur, wenn das Teil wirklich passt; sonst der Grund aus den Befunden der Teilung mit ihrer Handlung.
- Wirkung beim Kunden: Die Statuszeile sagt, alles passe, während der Bericht das Gegenteil meldet.
- Stand: behoben `138ac0b67`; `test_split_done_status.py` am Stand davor rot, danach sagt die Statuszeile mit einem Befund „Nicht geteilt.“ und seinen ersten Satz.

### FD-107 Zwei Akzentknöpfe in Bericht und Analyseleiste

- Art: Gestaltung
- Schwere: leicht
- Funktion: `finding.action:decimate_mesh`, `finding.action:repair_and_retry`, `finding.action:resolve_intersections`
- Prüfpunkt: G1
- Beleg: Lauf 043/flaeche-de-finding.action_decimate_mesh-84b04288.png, …repair_and_retry-4ee0b670.png, …resolve_intersections-6c1a6470.png (d08 N5).
- Ursache: offen; Hauptknopf des Berichts und Knopf der Analyseleiste tragen beide den Akzent.
- Vorschlag: Solange der Bericht eine Hauptaktion zeigt, ist der Knopf der Leiste gewöhnlich.
- Wirkung beim Kunden: Er muss lesen, welcher Knopf gemeint ist.
- Stand: behoben `794191fef`; `test_analysis_offer_accent.py` am Stand davor rot, danach grün; Bild hell und dunkel.

### FD-108 Die Halt-Quittung erscheint am Zeiger über dem Bericht

- Art: Gestaltung
- Schwere: leicht
- Funktion: `finding.action:check_updates`, `finding.action:suppress_step`, `finding.action:resolve_intersections`, `finding.action:decimate_and_retry`, `finding.action:use_reachable`, `finding.action:remesh_and_retry`, `finding.action:show_support_need`
- Prüfpunkt: 9, E4
- Beleg: Lauf 043/flaeche-de-finding.action_check_updates-3c670373.png, …suppress_step-03bf451d.png; Blätter `F:\tmp-suche\urteile-d08-claude\blatt-finding_action_check_updates.png` und `…suppress_step.png`: „Die Kette hält an — siehe Prüfbericht.“ liegt über Hauptknopf, Zielknopf, Befundzeilen, Details und Exportieren (d08 N6).
- Ursache: belegt: `announce` setzt jede Quittung als `_ActionNotice` an den Mauszeiger und hebt sie über die Karten, für mindestens acht Sekunden (`main_window.py:943–966`, `26548–26554`); nach dem Klick steht der Zeiger im Bericht.
- Vorschlag: Die Quittung neben die auslösende Karte in die freie Ansicht setzen, nie über eine Karte.
- Wirkung beim Kunden: Acht Sekunden lang verdeckt der Satz die Knöpfe, die der Bericht als nächsten Schritt anbietet.
- Stand: behoben `c5b2387a9`; `test_action_notice_window.py` am Stand davor rot (Quittung über dem Bericht), danach steht sie an der freien Stelle nächst dem Ort der Handlung; nativer Nachweis neben echten Karten im Schlusslauf (Plan Punkt 38).

### FD-109 Befundzeilen kürzen ihre Maßangabe

- Art: Gestaltung
- Schwere: leicht
- Funktion: `finding.action:place_on_bed`, `finding.action:remove_small_parts`, `finding.action:show_layers`
- Prüfpunkt: 9
- Beleg: Lauf 048/flaeche-pt-finding.action_remove_small_parts-c7433173.png „Ressalto: 10,00 …“; 046/flaeche-fr-finding.action_show_layers-ebbd45da.png „Dépassement : 10,00 …“; 002/04-fehlfall.png „Überstand: 10,00 …“; Gruppenzeilen in EN und FR (d08 N7).
- Ursache: offen; die Zeilen des Berichts werden am rechten Rand elidiert.
- Vorschlag: Maß und Einheit gehören sichtbar zur Zeile; umbrechen oder den Titel vor dem Maß kürzen.
- Wirkung beim Kunden: Die Zahl, um die es geht, fehlt.
- Stand: behoben `e0b6de3b8`; `test_report_rows.py` am Stand davor rot, danach grün; nativer Nachweis bei 125 % im Schlusslauf (Skalierung 1,25 seit `e7f9c9569`, Plan Punkt 11).

### FD-110 Die Textmessung erkennt elidierte Berichtszeilen nicht

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Funktionsprüfstand, Textmessung
- Prüfpunkt: 9
- Beleg: dieselben Bilder wie FD-109; Stufe A meldet dort `cut=false` (d08 N7).
- Ursache: offen; die Messung prüft Zeilen in Listen und Bäumen nicht gegen ihre gezeichnete Breite.
- Vorschlag: Elision in Listen und Bäumen messen (Text gegen Spaltenbreite der Ansicht), mit kurzer Zeile als Gegenfall.
- Wirkung beim Kunden: P9 meldet vollständige Texte, wo der Kunde „…“ liest.
- Stand: behoben `f81515384`; `test_function_capture_reach.py::test_a_wrapped_row_too_low_for_its_lines_is_cut` am Stand davor rot, danach `axis = hoehe`, `cut = true`.

### FD-111 Nach der Befundauswahl ist die Stelle nicht zu sehen

- Art: Einfachheit
- Schwere: mittel
- Funktion: `finding.action:scale_to_fit`, `finding.action:split_model`, `finding.action:repair_before_and_retry`, `finding.action:recognize_local`, `finding.action:remesh_and_retry`
- Prüfpunkt: E4
- Beleg: Lauf 043/flaeche-de-finding.action_scale_to_fit-87964424.png, …split_model-d08d0a7a.png, …repair_before_and_retry-34a5b021.png, …recognize_local-8238ff17.png, …remesh_and_retry-c1243162.png: die Ansicht zeigt nur Körperfläche (Kamera auf oder im Körper) oder einen winzigen Körper (d08 N8).
- Ursache: offen (Kamerafahrt der Befundauswahl oder Größe der Szene).
- Vorschlag: Ursache an einem der fünf Fälle belegen; die Befundauswahl rahmt Körper und Stelle.
- Wirkung beim Kunden: Er wählt einen Befund und sieht nicht, wo er liegt.
- Stand: behoben `2178041c4` (Ansicht), `7e1fb79c5` (Fenster); `test_finding_frame.py` und `test_finding_frame_window.py` je am Stand davor rot, danach rahmt ein Befund ohne Ort den Körper, und ein geöffnetes Projekt steht ganz im Bild.

### FD-112 Dieselbe Handlung heißt im Bericht „Dicke geben“ und im Dialog „Offene Fläche schließen“

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `finding.action:give_thickness`
- Prüfpunkt: V1
- Beleg: Lauf 043/flaeche-geoeffnet-de-finding.action_give_thickness-0921d5a7-dialog.png; alle Sprachen (d08 N10).
- Ursache: belegt: *Dicke geben* öffnet gewollt *Offene Fläche schließen* (`main_window.py:28068`, `errors.py:114–116`); der Dialog nennt nur den Operationstitel.
- Vorschlag: Der Dialog sagt in seiner ersten Zeile, dass er der Fläche eine Dicke gibt, oder der Knopf heißt wie die Operation.
- Wirkung beim Kunden: Er klickt „Dicke geben“ und landet in einem Dialog mit anderem Namen.
- Stand: behoben `3e7cf5408`; der erste Satz hinter *Dicke geben* sagt „Dicke“ in jeder Sprache, der Test je Sprache am Stand davor rot.

### FD-113 „In Einzelteile aufteilen“ nennt ein mehrteiliges Netz ein Stück

- Art: Fehler
- Schwere: mittel
- Funktion: `split_bodies`
- Prüfpunkt: 7, E7, V5
- Beleg: Lauf 043/flaeche-de-split_bodies-e45b38ac.png und -dialog.png an `mehrteilig.netz`: Vorschau und Absage „Der Körper besteht aus einem Stück“, obwohl der Bericht mehrere Teile meldet; „Splitter behalten“ wird nicht angeboten (d08 N11).
- Ursache: belegt: `split_bodies` zählt ohne Splitter, solange `keep_tiny` aus ist (`prepare_ops.py:21759–21801`); bleibt ein Teil, sagt `ONE_PIECE` „aus einem Stück“, und die Vorschläge sind nur *Eingabe korrigieren* und *Abbrechen*. Die Zeile „Art: …“ ist FD-95.
- Vorschlag: Weggelassene Splitter nennen („… und N Splitter unter der Druckgrenze“) und *Splitter behalten* als Handlung anbieten.
- Wirkung beim Kunden: Die Absage widerspricht dem Bericht und verschweigt den einen Schalter, der weiterhilft.
- Stand: behoben `abf1b103d`; `test_split_splinters.py` an `two_components.stl` am Stand davor rot, danach nennt die Absage den Splitter, bietet *Splitter behalten*, und mit dem Schalter entstehen zwei Objekte.

### FD-114 Umbenennen zeigt den aktuellen Namen nicht

- Art: Einfachheit
- Schwere: leicht
- Funktion: `rename_object`
- Prüfpunkt: E2
- Beleg: Lauf 043/flaeche-de-rename_object-03af2449-dialog.png: Feld „Name“ leer; alle Sprachen (d08 N12).
- Ursache: offen.
- Vorschlag: Der aktuelle Name als Vorgabe, markiert.
- Wirkung beim Kunden: Für eine kleine Änderung tippt er den ganzen Namen neu.
- Stand: behoben `5ae49d564` (Vorgabe in `run_operation`), `ace879f65` (Markierung beim ersten Fokus), `a1cc7a720`, `7426b1693` (*Übernehmen* wartet auf einen neuen Namen, ein mitgebrachter gibt frei); `test_rename_dialog.py` und `test_operation_dialog_first_focus.py` je am Stand davor rot, danach grün.

### FD-115 Flächen von Berichtshandlung und Löschen entstehen nach ihrer Wirkung

- Art: Fehler
- Schwere: mittel
- Funktion: `report.action`, `delete_object`
- Prüfpunkt: 9, 19, V4
- Beleg: Lauf 043/flaeche-de-report.action-e5ae30a0.png und 043/flaeche-de-delete_object-df54ecae.png (d08 N13).
- Ursache: belegt: Der Fix von FD-37 hält den Weg nur bei Zielen `finding.action:` und `feature:` vor dem letzten Klick an (`function_bench.py:1906–1912`); andere Soforthandlungen klicken vor der Aufnahme. Rest zu FD-37.
- Vorschlag: „Vor der Wirkung messen“ an der Art der Handlung entscheiden (wirkt sofort), nicht am Präfix des Ziels; Gegenprobe an beiden Zeilen.
- Wirkung beim Kunden: Gemessen wird der Stand danach; kein Kundenfehler belegt.
- Stand: behoben `8188f8725`; `test_function_surface_at_once.py` am Stand davor rot, danach wird eine Handlung, die mit dem Klick wirkt, davor gemessen.

### FD-116 Das Vorschauband zeigt die Legende ohne Volumenänderung

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `rename_object`, `set_material`
- Prüfpunkt: 3, V1
- Beleg: Lauf 043/flaeche-de-rename_object-03af2449.png und …set_material-323cd6b1.png: Legende Hinzugefügt/Entfernt ohne Geometrieänderung (d08 N14).
- Ursache: offen; verwandt mit FD-52 (Sichtbarkeit der Legende), hier umgekehrt.
- Vorschlag: Die Legende nur, wenn die Vorschau hinzugefügtes oder entferntes Material zeigt.
- Wirkung beim Kunden: „Hinzugefügt/Entfernt“ bei einer Handlung, die nichts hinzufügt oder entfernt.
- Stand: behoben `3ea182a86`; `test_preview_legend.py` am Stand davor rot (2), danach steht die Legende nur über einer Differenz mit Volumen- oder Körperänderung; nativer Nachweis im Schlusslauf (Plan Punkt 10).

### FD-117 „Neu erzeugen“ öffnet den Generator leer

- Art: Einfachheit
- Schwere: leicht
- Funktion: `finding.action:generate_again`
- Prüfpunkt: E2, Z6
- Beleg: Lauf 043/flaeche-geoeffnet-de-finding.action_generate_again-c04c15ad-dialog.png: ohne Einleitungssatz, frühere Beschreibung nicht vorbelegt; Blatt `F:\tmp-suche\urteile-d08-claude\blatt-finding_action_generate_again.png`: ES/IT/PT 282 statt 266 px hoch (d08 N15). Die Feldhilfen sind FD-78.
- Ursache: für die Vorbelegung belegt: Der Handler ruft `_generate(None)` (`main_window.py:27550`) und gibt keine frühere Beschreibung mit; Einleitung und Höhe offen.
- Vorschlag: Die Beschreibung des erzeugten Modells vorbelegen, wenn sie vorliegt; ein Satz über dem Feld.
- Wirkung beim Kunden: Für einen neuen Versuch tippt er die Beschreibung noch einmal.
- Stand: behoben `dd98a37d2`; `test_generate_again_window.py` am Stand davor rot (Feld leer), danach mit Beschreibung, nächstem Startwert und Satz.

### FD-118 Das Wertefenster ist für sechs Zeilen viel zu groß

- Art: Gestaltung
- Schwere: leicht
- Funktion: `finding.action:show_step_values`
- Prüfpunkt: Z6
- Beleg: Lauf 043/flaeche-geoeffnet-de-finding.action_show_step_values-6402e83f-dialog.png: 520 × 360, rund zwei Drittel des Textfelds leer; alle Sprachen (d08 N16).
- Ursache: offen.
- Vorschlag: Höhe aus dem Inhalt, wie bei FD-51.
- Wirkung beim Kunden: Das Fenster verdeckt mehr Modell als nötig.
- Stand: behoben `321a33b6f`; `test_the_step_values_window_is_as_tall_as_its_lines` am Stand davor rot (134 px leer), danach so hoch wie die Zeilen (520 × 360 → 464 × 273).

### FD-119 Der Prüfstück-Dialog hat zweimal „Stelle“

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `test_piece`
- Prüfpunkt: V1, G3
- Beleg: Lauf 043/flaeche-de-test_piece-c2812758-dialog.png: Anzeige „Stelle“ und Auswahl „Genannter Punkt“ unter demselben Wort; alle Sprachen (d08 N17).
- Ursache: offen.
- Vorschlag: Zwei unterscheidbare Beschriftungen.
- Wirkung beim Kunden: Unklar, welches Feld die Stelle festlegt.
- Stand: behoben `b785e5c4f`; `test_dialog_texts.py::test_no_field_is_named_like_the_place_line_in_front` am Stand davor rot, danach heißt die Wahl „Lage des Würfels“.

### FD-120 „Stifte“ klebt am Haken davor

- Art: Gestaltung
- Schwere: leicht
- Funktion: `tool:split`
- Prüfpunkt: G3
- Beleg: Blatt `F:\tmp-suche\urteile-d08-claude\blatt-tool_split.png`, Lauf 043/flaeche-de-tool_split-ed52c275.png: „Zum Zusammenstecken vorbereiten“ und „Stifte“ lesen sich als ein Satz; alle Sprachen (d08 N18).
- Ursache: offen (Abstand in der Teilenleiste).
- Vorschlag: Abstand oder Trenner zwischen Haken und Feldbeschriftung.
- Wirkung beim Kunden: Haken und Feld lesen sich wie ein Satz.
- Stand: behoben `1f2df32dd`; `test_split_bar_spacing.py` am Stand davor rot, danach grün; Bild hell und dunkel.

### FD-121 Der einmalige Druckhinweis verdeckt die Zielfläche im Prüfstand

- Art: Fehler
- Schwere: mittel
- Funktion: `finding.action:choose_printer`, `finding.action:open_print_settings`
- Prüfpunkt: 1, E5
- Beleg: Lauf 043/flaeche-geoeffnet-de-finding.action_choose_printer-2c1a8d33-dialog.png und …open_print_settings-970cbb07-dialog.png: gemessen wird der Druckhinweis (258 px, 27 Wörter), die Zielfläche wird nie erreicht (d08 N20).
- Ursache: Das Prüfprofil quittiert den einmaligen Hinweis (`app/ui/print_disclosure.py`) nicht; Stufe A misst E5 am Hinweis.
- Vorschlag: Den Hinweis im Profil der Fälle als gesehen eintragen (`tools/function_setup.py`, `profile_settings`) und ihn als eigene Zeile messen.
- Wirkung beim Kunden: E5-Fund an der falschen Fläche, die Zielfläche bleibt ungemessen; kein Kundenfehler belegt.
- Stand: behoben `040898baa`, `07b1edf6c`; `test_function_print_hint.py` am Stand davor rot: das Prüfprofil hat den Hinweis gesehen, die eigene Zeile läuft mit `druckhinweis = "offen"`; nativer Nachweis des Falls `D12@druckhinweis=offen` im Schlusslauf (Plan Punkt 30).

### FD-122 Der Prüfstand misst an Dateidialogen den erzwungenen Qt-Dialog

- Art: Fehler
- Schwere: leicht
- Funktion: `finding.action:choose_another_file`, `finding.action:export_as_mesh`
- Prüfpunkt: 19
- Beleg: Lauf 043/flaeche-geoeffnet-de-finding.action_choose_another_file-3b6379cf-dialog.png und …export_as_mesh-b040c130-dialog.png: englische Teile, gekürzte Spalten, Startordner `F:\sl-welle4`; Stufe-A-Funde Abstände 6/11 und Rollleiste (d08 N21).
- Ursache: belegt: Der Fallprozess setzt `AA_DontUseNativeDialogs` (`tools/file_acceptance.py:1197`); der Kunde sieht den Systemdialog.
- Vorschlag: Dateidialoge als Systemfläche kennzeichnen (Z5-Ausnahme, Stufe C) und nicht nach G2 und Z6 messen.
- Wirkung beim Kunden: Falsche Gestaltungsfunde; kein Kundenfehler.
- Stand: behoben `25cce747a`; `test_function_system_surface.py` am Stand davor rot, danach zählt ein `QFileDialog` als Systemfläche (Stufe C).

### FD-123 Der Kantenfehler bietet „Andere Objekte wählen“ an

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `finding.action:change_selection`
- Prüfpunkt: V1
- Beleg: Lauf 043/flaeche-de-finding.action_change_selection-9fd7dccb.png (d08 N23).
- Ursache: offen; der Vorschlag nennt Objekte, wo Kanten gemeint sind.
- Vorschlag: „Andere Kanten wählen“ an Kantenfehlern, in allen Sprachen.
- Wirkung beim Kunden: Er wählt einen anderen Körper statt einer anderen Kante.
- Stand: behoben `f8d54b2ae`, nach Review `36cdd9fe2` (Handlung nach dem auslösenden Schritt); `test_edge_refusal_ways.py` am Stand davor rot, danach bieten die Kantenabsagen beider Kerne *Andere Kanten wählen*.

### FD-124 Große Zahlen ohne Tausendertrennung

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `finding.action:decimate_mesh`
- Prüfpunkt: 9
- Beleg: Lauf 043/flaeche-de-finding.action_decimate_mesh-84b04288.png und -dialog.png: „2103472 Dreiecke, möglich sind 900000“, Feld „1051736“; alle Sprachen (d08 N24).
- Ursache: offen.
- Vorschlag: Ganzzahlen mit Gruppentrennung der Anzeigesprache, auch im Feld.
- Wirkung beim Kunden: Siebenstellige Zahlen sind schwer zu lesen.
- Stand: behoben `8ebd989d4` (Satz der Analyseleiste), `afa2a9427` (Zahlenfeld des Operationsdialogs), `3e515ef4f`, `8af6a2d09` (alle Ganzzahlfelder, FD-184); `test_map_limit_text.py` und `test_grouped_count_field.py` je am Stand davor rot, danach Dreiergruppen wie `count_text`; nativer Nachweis der Breite mit Systemschrift im Schlusslauf (Plan Punkt 14).

### FD-125 Parameter anlegen kennt keine Zolleinheit

- Art: Fehler
- Schwere: mittel
- Funktion: `Bearbeiten/Parameter anlegen …`
- Prüfpunkt: 9
- Beleg: Lauf 006/flaeche-zoll-dialog.png: bei Zollanzeige nur „mm — Länge“, der Wert ohne Zoll; Kopf und Baum zeigen Zoll (d10 Nr. 1).
- Ursache: belegt: `PARAMETER_UNITS` kennt nur mm, Grad und ohne Einheit (`labels.py:112–116`); auch der Rezeptdialog nutzt die Liste (`recipe_dialog.py:253`).
- Vorschlag: Längenparameter in der Anzeigeeinheit zeigen und annehmen (Längenfeld wie in den Operationsdialogen), gespeichert in mm (Regel 6).
- Wirkung beim Kunden: Wer in Zoll arbeitet, rechnet für einen Parameter in Millimeter um.
- Stand: behoben `91e966a51` (Parameter- und Bausteindialog), `d3cd8f2e0` (Parameterleiste), `6168cacae`, `f49c624d9`, `209bbe08c` (Review RA-1, RA-2, RA-5); `test_parameter_units.py`, `test_parameter_panel_units.py` und `test_parameter_unit_switch_window.py` je am Stand davor rot, danach Zoll gezeigt und angenommen, Millimeter gespeichert, ein Maß ohne Einheit bleibt eine Zahl.

### FD-126 Im ersten Bild liegt „Parameter anlegen …“ über dem Erklärungstext

- Art: Gestaltung
- Schwere: leicht
- Funktion: `Bearbeiten/Parameter anlegen …`, `parameters`
- Prüfpunkt: 19
- Beleg: Lauf 003/01-vorher.png, Ausschnitt `F:\tmp-suche\urteile-d10-claude\crops\003-01-parameter.png`; alle späteren Bilder sauber (d10 Nr. 3).
- Ursache: offen (ein Bild); Verdacht: Höhe des umbrochenen Texts vor der endgültigen Breite gemessen.
- Vorschlag: Am Startweg nachstellen, dann beheben.
- Wirkung beim Kunden: Kurz nach dem Laden verdeckt der Knopf eine Textzeile.
- Stand: behoben `9f8e67c08`, `d3cd8f2e0`, `546b0e891` (misst nach einem Schriftwechsel); `test_parameter_empty_note.py` am Stand davor rot, danach grün; nativer Nachweis am Startweg im Schlusslauf (Plan Punkt 35).

### FD-127 Prüfpunkt 12 zählt nur Operationen

- Art: Fehler
- Schwere: leicht
- Funktion: `Bearbeiten/Parameter anlegen …`
- Prüfpunkt: 12
- Beleg: Lauf 003/03-uebernommen.png zeigt den Verlaufseintrag „Parameter breite“, Stufe A meldet „die Zeile legt keinen Schritt im Verlauf an“ (d10 Nr. 4).
- Ursache: belegt: `phase_revise` vergleicht die Zahl der `ops` (`function_revision.py:38–40`); eine Parameteränderung ist ein Verlaufseintrag ohne Operation.
- Vorschlag: Die Verlaufslänge aus den Einträgen des Verlaufs lesen und den Parameterweg (Doppelklick, *Ändern …*) messen.
- Wirkung beim Kunden: P12 bleibt an Parameterzeilen ungemessen; kein Kundenfehler belegt.
- Stand: behoben `f50bf25a8`, `13b09c7a0`, `7af8a78f3`, `2b0fcc820`; `test_function_revision_parameters.py` geht beide Wege des Parameters über den echten Wortschatz, ohne die Ziele „nicht gemessen“.

### FD-128 Prüfpunkte 5 und 16 verlangen Zustände, die die Zeile nicht hat

- Art: Fehler
- Schwere: leicht
- Funktion: `finding.action:place_on_bed`, `Bearbeiten/Parameter anlegen …`
- Prüfpunkt: 5, 16
- Beleg: Lauf 002/function.json#states: before, applied, undo und redo vorhanden, Rückgängig stellt den Körperabdruck her, P5 meldet trotzdem alle fünf Zustände fehlend; 003/02-flaeche.png: P16 verlangt Vorschau- und Rechnungsphase an einer Zeile ohne beides (zweit Nr. 4, d10 Nr. 5).
- Ursache: belegt: `_point_5` verlangt `states.escape` an jeder Zeile (`function_points.py:337–345`), `_point_16` alle `SWITCH_PHASES` (`function_points.py:829–846`), gleich ob die Zeile Entwurf, Vorschau oder Rechnung hat.
- Vorschlag: Escape nur an Zeilen mit Entwurf oder Dialog verlangen, Wechselphasen nur die, die die Zeile hat; sonst *entfällt* mit Grund aus der geschlossenen Liste.
- Wirkung beim Kunden: Der Rückweg nach FD-4 und der Wechsel bleiben ungewertet; kein Kundenfehler.
- Stand: behoben `8c48fc7d6`; `test_function_judgement_scope.py` (Rückweg ohne Entwurf, Zeile ohne Wechsellage) am Stand davor rot; am finalen Lauf neu ausgewertet 002 P5 erfüllt, P16 entfällt, 003 P16 erfüllt.

### FD-129 Fensterbefehle mit Agentenwerkzeug nennen keinen Ort, und Prüfpunkt 17 sieht sie nicht

- Art: Fehler
- Schwere: mittel
- Funktion: `Bearbeiten/Parameter anlegen …`, `dialog:parameter_dialog`
- Prüfpunkt: 17
- Beleg: Lauf 003/02-flaeche.png, Stufe A „ohne Agentenwerkzeug“; das Werkzeug `add_parameter` legt genau diesen Parameter an (d10 Nr. 6).
- Ursache: belegt: `_point_17` sucht den Agentenweg nur für Zeilen der Art `operation` (`function_points.py:851–856`); `add_parameter` beschreibt keinen Ort im Fenster (`app/core/agent/tools.py:644–667`), anders als die Operationswerkzeuge über `menu_path`.
- Vorschlag: Werkzeuge außerhalb des Registers (`add_parameter`, `set_parameter`, `add_fit` und weitere) nennen ihren Fensterort aus derselben Quelle wie das Menü; P17 ordnet sie ihren Zeilen zu.
- Wirkung beim Kunden: Der Agent kann nicht sagen, wo der Kunde einen Parameter selbst anlegt, und die Prüfung hält den Punkt für nicht zutreffend.
- Stand: behoben `133594b30` (Werkzeugort), `2a8329f54` (Prüfpunkt 17); `test_agent_tool_places.py` und `test_function_judgement_scope.py::test_the_agent_place_of_a_window_command_is_compared` je am Stand davor rot, am finalen Lauf 003 P17 erfüllt.

### FD-130 Die Flächenmessung nimmt für andere Ziele die Auswahlkarte

- Art: Fehler
- Schwere: mittel
- Funktion: `parameters`, `parameters.first`
- Prüfpunkt: 8, E5, V1, V2, V3
- Beleg: Lauf 031/flaeche-de-parameters.first-b5c45dda.png; Flächenprotokolle beider Zeilen: Texte und Felder aus der rechten Auswahlkarte („Nichts gewählt …“), Wertfeld, Einheit und „…“ der Parameterzeile fehlen (d10 Nr. 7).
- Ursache: belegt: `surface_for` kennt Dialog, Bericht, Werkzeugleiste und Merkmal und fällt sonst auf `selection` zurück (`function_surface.py:116`); der Fix von FD-47 schloss nur `feature:`. Rest zu FD-47.
- Vorschlag: Die Fläche aus dem Ziel selbst ableiten (nächster Kartenvorfahre des Ziels); die Auswahlkarte nur, wenn das Ziel dort liegt.
- Wirkung beim Kunden: E5, V1 und V2 grün und V3 rot an der falschen Karte; kein Kundenfehler belegt.
- Stand: behoben `98c3d4215`; `test_function_surface_place.py` am Stand davor rot, danach ist die Fläche einer Zeile die Seite oder der Abschnitt, in dem ihr Ziel steht.

### FD-131 Die Navigation klickt ein Ziel unterhalb aller Sichtflächen an

- Art: Fehler
- Schwere: mittel
- Funktion: `assign_slot`
- Prüfpunkt: 2
- Beleg: Lauf 031/surfaces/assign_slot-bd965763.json#steps: Klick „klappe“ auf `filament.picker` bei y = 1572–1605, das Fenster endet bei 1470, kein Rollen, `widget_at` leer, „verdeckt“; in allen sechs Sprachen (d10 Nr. 8).
- Ursache: teilweise belegt: Am Stand `2ec37b23b` lässt `_scroll_needed` das Ziel stehen, wenn kein Rollbereich weiter rollen kann (`guide_targets.py:1648–1676`), und der Klick geht ins Leere. Der Fix zu FD-77 (`46c628ef9`, auf welle4 seit `64e389936`) macht daraus `MissingTargetError`. Warum kein Bereich das Ziel heranrollt, ist offen: Prüfstand oder eine Karte, die über den Fensterrand reicht.
- Vorschlag: Am Stand mit FD-77 nachstellen; reicht die Karte über den Fensterrand, ist es ein Produktfund und wird neu bewertet.
- Wirkung beim Kunden: Der Kundenweg zu *Filament zuweisen* lief in keiner Sprache.
- Stand: behoben `9301605b6`; kein Produktfund; `test_guide_obstacle_scroll.py` und `test_function_walk_rolling.py` am Stand davor rot, danach rollt die Navigation eine Klappe heran; nativer Nachweis im Schlusslauf (Plan Punkt 2).

### FD-132 Der Zustand einer Sprachfläche wandert in die nächste

- Art: Fehler
- Schwere: mittel
- Funktion: `paint_slot`, `filament.section`
- Prüfpunkt: Z3
- Beleg: Lauf 031/flaeche-de-paint_slot-9865a109.png: Z3 misst 0 Wegklicks, weil die vorige Fläche im selben Prozess den Abschnitt aufgeklappt beziehungsweise die Karte ans Ende gerollt hatte; im Ausgangszustand ist er zu (FD-19) (d10 Nr. 9).
- Ursache: Zwilling zu FD-40: Der Sprachdurchgang wechselt die Startszene, stellt aber Klappzustand und Rolllage der Karten nicht zurück (`tools/function_language.py`).
- Vorschlag: Vor jeder Sprachfläche den Ausgangszustand der Karten herstellen, oder messen und rot beenden, wenn er abweicht.
- Wirkung beim Kunden: Ein rotes Z3 wird grün; der Weg zum Filamentabschnitt erscheint kürzer, als er ist.
- Stand: behoben `d2c4351fd`; `test_function_language_ground.py` am Stand davor rot, danach beginnt jede Sprachfläche im Ausgangszustand eines frischen Starts.

### FD-133 Im portugiesischen Maßblock der Gegenstücke stehen zwei Leerzeilen

- Art: Gestaltung
- Schwere: leicht
- Funktion: `Erzeugen/Bausteine/Gegenstücke setzen …`
- Prüfpunkt: 9, Z6
- Beleg: Lauf 036/flaeche-pt-Erzeugen_Bausteine_Gegenstücke_setzen-5b902f72.png: rund 32 px Leerraum im Maßblock der rechten Karte, andere Sprachen ohne (d10 Nr. 11).
- Ursache: offen; möglicherweise dieselbe Umbruchhöhe wie FD-93.
- Vorschlag: Am Layout belegen; die Höhe aus dem sichtbaren Inhalt.
- Wirkung beim Kunden: Leere Zeilen in der Karte.
- Stand: behoben `5068fc6d9`, `6affeeb97`; Ursache war `panels.fit_wrapped`, das umbrochene Sätze an der Grundbreite der linken Spalte maß; `test_wrapped_height.py` am Stand davor 14 von 15 rot, `test_left_card_empty_sentences_window.py` am Stand davor 5 von 6 rot, danach grün; Bild hell und dunkel in sechs Sprachen; nativer Nachweis im Schlusslauf (Plan Punkt 17).

### FD-134 Schriftzug anlegen meldet vor der ersten Eingabe einen Fehler

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `create_label`
- Prüfpunkt: V5
- Beleg: Lauf 031/flaeche-de-create_label-1c3131b4-dialog.png: schon beim Öffnen „Ohne Text gibt es nichts anzulegen.“ mit Fehlerblock und „Details anzeigen“, alle Sprachen; `inlay_text` und `label_text` zeigen denselben Zustand nur im Vorschauband (d10 Nr. 12).
- Ursache: offen; fest steht, dass die erste Vorschau mit leerem Text als Absage im Dialog endet, bei den Geschwistern nicht. Die Form des Blocks ist FD-95.
- Vorschlag: Ein leerer Pflichttext ist ein Hinweis am Feld wie bei den Geschwistern, kein Fehler.
- Wirkung beim Kunden: Bevor er etwas getan hat, steht da ein Fehler.
- Stand: behoben `25ff4aa1a`; `test_required_text_field.py` am Stand davor rot (Absage beim Öffnen), danach keine Vorschau, Hinweis im Feld, Knopf grau mit „Erst „Text“ ausfüllen, dann übernehmen.“

### FD-135 Textur in Filamente umrechnen wird ohne Textur angeboten

- Art: Fehler
- Schwere: mittel
- Funktion: `slots_from_texture`
- Prüfpunkt: 13, E7
- Beleg: Lauf 031/flaeche-de-slots_from_texture-1cd8021e.png: am Quader ohne Textur angeboten, erst die Vorschau sagt „Dieses Objekt trägt keine Farbinformation.“ (d10 Nr. 13).
- Ursache: belegt: Der Registereintrag trägt kein `requires_body` (`colour_ops.py:314–330`); `grenzen.md` verlangt, dass am Menüeintrag steht, was am gewählten Körper nie etwas tun kann.
- Vorschlag: Die Bedingung „trägt Farbinformation“ als `requires_body` mit demselben Satz; der Eintrag steht grau mit Grund.
- Wirkung beim Kunden: Er öffnet eine Handlung, die an seinem Teil nie etwas tun kann.
- Stand: behoben `a1a9306fd` (Kern vorbereitet `7938175dc`, `cac627d7e`); vier Tests in `test_texture.py` und `test_operation_ui.py` am Stand davor rot (Eintrag frei, kein Satz), danach grün: *Textur in Filamente umrechnen* steht an einem Körper ohne Farbe grau mit dem Satz des Befunds (`colour.no_texture`), frei an einem farbigen, beide Kerne; Startszene `farbig.netz` mit Korpus `painted_cube.ply`; Changelog 0.6.1 in sechs Sprachen.

### FD-136 Der Übernehmen-Fuß steht weit unter seinem Feld

- Art: Gestaltung
- Schwere: leicht
- Funktion: `clear_filament`, `paint_slot`, `resize_feature`
- Prüfpunkt: 19
- Beleg: Lauf 031/flaeche-de-clear_filament-a6b075a9.png: oranges „Übernehmen“ mit „Fläche versetzen“ unter dem Filamentabschnitt, das Feld ganz oben; ebenso „Merkmal ändern“ am Zapfen (`F:\tmp-suche\urteile-d04-claude\crops\037-resize_feature-karte.png`) (d10 Nr. 14). Gestaltungsurteil.
- Ursache: Der Fuß steht außerhalb der rollenden Zeilen am Kartenende (so beschrieben in `function_surface.surface_parts`).
- Vorschlag: Den Fuß unmittelbar unter der offenen Zeile zeigen; E1–E7 an derselben Zeile vorher und nachher messen.
- Wirkung beim Kunden: Feld oben, Knopf unten — der Blick springt über die ganze Karte.
- Stand: behoben `976b60ade` (Panel), `a2cf5c2f7` (Fenster, `_Follower`), Wächter `26f33fc8e`, `78d2158f6`; `test_feature_footer_window.py`, `test_footer_in_sight.py` und `test_feature_footer_low_window.py` je am Stand davor rot, danach steht die Knopfzeile unter der Handlung im Sichtfeld; nativer Nachweis mit Öffnungsbewegung im Schlusslauf (Plan Punkt 6).

### FD-137 Zwei Dialogeinleitungen sind wörtlich oder doppeldeutig übersetzt

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `Bearbeiten/Parameter anlegen …`, `inlay_text`
- Prüfpunkt: 8, V1
- Beleg: Lauf 034/flaeche-fr-Bearbeiten_Parameter_anlegen-ffe8f785-dialog.png: EN „turning the number rebuilds the model“, FR „tourner le chiffre …“, IT „girare il numero …“ (Quelle `app/ui/dialogs.py`); 036/flaeche-pt-inlay_text-96981be8-dialog.png: PT „Incrusta texto à face numa face.“ (d10 Nr. 15, Nr. 16).
- Ursache: belegt: die Katalogwerte in en, fr und it beziehungsweise pt.
- Vorschlag: Die vier Katalogwerte neu übersetzen.
- Wirkung beim Kunden: Die Einleitung ist in vier Sprachen holprig oder missverständlich.
- Stand: behoben `6b2b6c555`; `test_catalog_terms.py::test_two_dialog_intros_say_what_the_german_means` am Stand davor in en, fr, it und pt rot, danach grün.

### FD-138 Die gefaltete Sperrzeile liest sich als gewöhnlicher Absatz

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `clear_filament`, `paint_slot`, `resize_feature`
- Prüfpunkt: V1
- Beleg: Lauf 031/flaeche-de-clear_filament-a6b075a9.png: „Merkmal ändern, Zum Langloch ziehen, drehen, verdoppeln und entfernen — Eine Fläche ist …“, Großschreibung mitten im Satz, in allen Sprachen gleich gebaut; am Zapfen „Zum Langloch ziehen — Gezogen wird ein Loch, …“ (`F:\tmp-suche\urteile-d04-claude\crops\037-resize_feature-karte.png`) (d10 Nr. 17).
- Ursache: Die Gründe aus `NOT_APPLICABLE` (`app/core/perceive/actions.py`) werden in `panels.py` hinter die Titel gefaltet, ohne zu sagen, dass die genannten Handlungen hier nicht gehen. Der Verbinder aus FD-43 ist behoben und nicht betroffen.
- Vorschlag: Ein Satzbau, der die Absage trägt („Hier nicht: …, weil …“), mit kleinem Anschluss nach dem Gedankenstrich, in allen Sprachen.
- Wirkung beim Kunden: Er liest eine Aufzählung von Handlungen und erfährt nicht, dass sie hier fehlen.
- Stand: behoben `014590964`; `test_refusal_line.py` am Stand davor in sechs Sprachen rot, danach „Hier nicht möglich: {actions}. {reason}“; Bild hell und dunkel.

### FD-139 Rollbereiche sind eigene Tab-Halte mit Klassennamen

- Art: Fehler
- Schwere: mittel
- Funktion: `Bearbeiten/Parameter anlegen …`, `finding.action:place_on_bed`
- Prüfpunkt: 10
- Beleg: Lauf 003/function.json#tab_chain: Die Kette beginnt und endet an „DialogScrollArea“; 002/function.json#tab_chain: erstes Glied „FittedScroller“ (zweit Nr. 2, Nr. 3).
- Ursache: belegt am Code: `DialogScrollArea` (`style.py:233`) und `overlay.FittedScroller` (`overlay.py:1046`) setzen keine Fokuspolitik und behalten Qts Vorgabe für Rollbereiche (`StrongFocus`); einen zugänglichen Namen tragen sie nicht.
- Vorschlag: Reine Rollbehälter auf `NoFocus` (Rad und Tastatur rollen über das fokussierte Kind), sonst mit Name und Beschreibung.
- Wirkung beim Kunden: Am Anfang und Ende jedes Dialogs ein Tab-Halt ohne Namen.
- Stand: behoben `7464c5ae3`, `5fb7d7537` (Maßgruppe); `test_scroll_areas.py` und `test_report_tab_chain.py` am Stand davor rot, danach ist kein Rollbereich ein namenloser Tab-Halt.

### FD-140 Tab erreicht „Auf das Bett setzen“ im Prüfbericht nicht

- Art: Fehler
- Schwere: mittel
- Funktion: `finding.action:place_on_bed`
- Prüfpunkt: 10
- Beleg: Lauf 002/function.json#tab_chain: FittedScroller → SignalTabBar (außerhalb), die Handlung fehlt; Bild 002/02-flaeche.png (zweit Nr. 3).
- Ursache: offen; fest steht, dass die Kette den Bericht nach dem Rollbereich verlässt. Ob seine Knöpfe fokussierbar sind, sagt das Protokoll nicht.
- Vorschlag: Die Tab-Folge des Berichts belegen (Befundliste → Handlungen) und setzen; Test über Tab und `focusWidget()`.
- Wirkung beim Kunden: Mit der Tastatur bleibt die angebotene Lösung unerreichbar.
- Stand: behoben `7464c5ae3`; `test_report_tab_chain.py::test_tab_reaches_the_offered_action_from_every_stop_before_it` am Stand davor rot („FittedScroller → SignalTabBar“), danach grün.

### FD-141 Prüfpunkt 10 fragt weder nach der Zielhandlung noch nach technischen Namen

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Funktionsprüfstand, Tastatur und Zugänglichkeit
- Prüfpunkt: 10
- Beleg: Lauf 001 und 002: Ketten ohne Zielhandlung, Glieder „FittedScroller“ und „DialogScrollArea“; Stufe A „2 Tab-Schritte, erfüllt“ beziehungsweise „erfüllt“ (zweit Nr. 3).
- Ursache: belegt: `_point_10` prüft nur Rücksprünge innerhalb der Fläche, leere und doppelte Namen (`function_points.py:615–655`); `name_of` fällt auf den Klassennamen zurück (`function_capture.py:474–477`), der als Name zählt, und Glieder außerhalb werden nur weggefiltert.
- Vorschlag: P10 verlangt, dass die Kette die Zielhandlung der Zeile erreicht, bevor sie die Fläche verlässt; ein Klassenname zählt als fehlender Name.
- Wirkung beim Kunden: Ein unbedienbarer Tastaturweg wird als erfüllt abgehakt.
- Stand: behoben `0526611ec`; `test_function_capture_reach.py::test_the_chain_names_what_a_screen_reader_reads_and_finds_the_target` am Stand davor rot, am finalen Lauf 002 P10 Fund statt erfüllt.

### FD-142 Weitere Doppelklicks in Tests und Werkzeugen lassen die Maustaste gedrückt

- Art: Zwillinge
- Schwere: leicht
- Funktion: keine Zeile: Prüfanschlüsse und Videowerkzeug
- Prüfpunkt: 19
- Beleg: Neben dem in FD-83 behobenen `QtPorts.press` rufen `tests/test_start_screen.py:461`, `:957`, `:966` und `tools/make_workshop_videos.py:2462` `QTest.mouseDClick` ohne anschließendes Loslassen auf; in `make_workshop_videos.py` fehlt zusätzlich der Klick davor (`F:\3D Druck\output\konsolidierung-2026-10-12\fd83-claude.md`).
- Ursache: `mouseDClick` schickt nur das Doppelklickereignis; Qt hält die linke Taste danach bis zum nächsten Klick im selben Prozess für gedrückt.
- Vorschlag: Dieselbe Folge wie der Kunde (Klick, Doppelklick, Loslassen) an allen Stellen; als Wächter eine Fixture, die nach jedem `qt_app`-Fall `QGuiApplication.mouseButtons() == NoButton` zusichert.
- Wirkung beim Kunden: Kein Produktfehler; im selben Prozess sehen Bewegungen bis zum nächsten Klick wie ein Zug aus, in Tests wie in den Werkstattvideos.
- Stand: behoben `701f20cca`; ein Helfer `tools/qt_clicks.double_click` an allen Stellen in `tests/` und `tools/`, der Wächter in `tests/conftest.py` am Stand davor rot an zwei Fällen von `test_start_screen.py` und an einer gepflanzten Stelle, danach grün.

## Einordnung der Prüferabweichungen (FD-143 bis FD-153)

Einordnung aller 37 Abweichungen zwischen Primär- und Zweitprüfer am finalen
Lauf: `output/konsolidierung-2026-10-12/abweichungen-claude.md` (Klassen,
Diffs, Nachurteilsliste `F:\tmp-suche\abweichungen-claude\nachurteil.toml`).
Entscheidung Koordinator zu FD-145: Die Übereinstimmung ≥ 90 % gilt je
Prüfpunkt gepoolt über alle Pakete einer Urteilsrunde; die Werte je Paket sind
Auskunft.

### FD-143 Funde mit mehreren Zeilen erreichen keine Zelle der Abhakliste

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 19
- Beleg: `F:\tmp-suche\abweichungen-claude\mehrzeilig.txt`: 43 Funde nennen mehrere Zeilen in „Funktion“ (FD-94, FD-100, FD-101, FD-109, FD-128, FD-129, FD-132 …) und erreichen keine Zelle; neuer Fall `test_a_finding_of_several_rows_holds_each_of_them_open` am alten Code dreimal rot (`_finding_for` liefert `None`).
- Ursache: `_finding_for` und die Fundspalte der Abhakliste verglichen das ganze Feld „Funktion“ mit der Zeilenkennung.
- Vorschlag: Die Zeilen aus „Funktion“ trennen wie die Prüfpunkte (Komma, Semikolon, „und“); ein Fund gehört jeder genannten Zeile.
- Wirkung beim Kunden: Kein Produktfehler; Zellen der Abhakliste galten als erledigt, obwohl ein offener Fund sie offen halten muss.
- Stand: behoben `3ea60bd0e`; Abhaklisten danach neu erzeugt.

### FD-144 Die Übereinstimmung lässt Zellen ohne Gegenurteil still weg

- Art: Fehler
- Schwere: leicht
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 19
- Beleg: Gegenprobe an einer Kopie (`F:\tmp-suche\abweichungen-claude\gegenprobe.txt`): an den 13 Zeilen des Zweitprüfers 77 Zellen nur primär, 5 nur zweit; G1–G8, Z1, Z2, Z5 und Z6 haben keinen einzigen Übereinstimmungswert.
- Ursache: `function_report.agreement` zählt nur Paare und meldet ungepaarte Zellen nicht.
- Vorschlag: `agreement` gibt die ungepaarten Zellen aus, die Abhakliste führt sie als „ohne Gegenurteil“; jeder Prüfpunkt braucht Paare, sonst ist er nicht gemessen.
- Wirkung beim Kunden: Kein Produktfehler; die Abnahme „≥ 90 % je Prüfpunkt“ war für zwölf Kriterien nicht prüfbar.
- Stand: behoben `3d3cd6efd`; `test_function_verdict_round.py::test_cells_without_a_counter_verdict_are_counted_not_dropped` hält die Zellen ohne Gegenurteil in der Abhakliste (am finalen Lauf 77 nur primär, 5 nur zweit).

### FD-145 Ob die Übereinstimmung gepoolt oder je Paket gilt, war nicht festgelegt

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 19
- Beleg: Konzept §4 (Urteil und Schwere) gegen §10 (Abnahme); die Abhaklisten markieren je Paket 7, 14 und 7 Punkte, gepoolt sind es 11 (`F:\tmp-suche\koord-claude-1014\ue.txt`); bei zwei bis drei Zeilen je Paket heißt 90 % „keine Abweichung“.
- Ursache: Konzept und Prüfstand nennen die Grundmenge der Quote nicht.
- Vorschlag: Entschieden (Koordinator, 15.10.): gepoolt je Prüfpunkt über alle Pakete einer Urteilsrunde ist bindend, je Paket Auskunft; Konzept §4 und `report` erhalten den Rundenwert.
- Wirkung beim Kunden: Kein Produktfehler; die Abnahme maß bei kleinen Paketen nichts.
- Stand: behoben `3d3cd6efd`; die 90 % gelten je Prüfpunkt gepoolt über die Runde (`test_the_round_pools_the_packages_and_binds` am Stand davor rot), die Paketwerte sind Auskunft; Konzept §4 sagt es so.

### FD-146 E1 bis E3 gelten als erfüllt an Wegen, die vor dem Beispielziel enden

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: E1, E2, E3
- Beleg: Alle Sprachflächenzeilen haben keine Zeilenspezifikation (`F:\tmp-suche\abweichungen-claude\zeilen.txt`); Stufe A meldet trotzdem „0 Eingaben, erfüllt“ (`stufe-a-paare.txt`, Abweichungen 01, 07–09, 11–15); neun Abweichungen gehen darauf zurück.
- Ursache: `_e1`, `_e2`, `_e3` (`tools/function_judges.py`) prüfen weder Spezifikation noch Übernahmeschritt; der E2-Paketanteil zählt diese Zeilen mit.
- Vorschlag: E1–E3 nur an einem Weg, der das Beispielziel erreicht hat; sonst nicht gemessen, *offen* mit Paket-RM; Gegenprobe Sprachflächenprotokoll ohne Spezifikation.
- Wirkung beim Kunden: Kein Produktfehler; Schrittzahlen galten als gemessen, die es nicht waren.
- Stand: behoben `bd7a043be`; `test_function_judgement_scope.py::test_steps_count_only_on_a_way_that_reached_the_example_goal` am Stand davor 12-mal rot, danach E1–E3 ohne Beispielziel „nicht gemessen“.

### FD-147 Englisch übersetzt „Überstand“ und „Überhang“ beide mit „Overhang“

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `finding.action:place_on_bed`
- Prüfpunkt: V1
- Beleg: `app/i18n/locales/en.json` Befund „An object sits below the build plate … Overhang: 10.00 mm“ (Fall 044, Ausschnitt `F:\tmp-suche\abweichungen-claude\crops2\pob-6spr.png`); dazu „overhang“ für Überstand an Haken, Rastnase und Widerhaken.
- Ursache: Zwei deutsche Begriffe teilen im englischen Katalog ein Slicer-Wort mit anderer Bedeutung.
- Vorschlag: Den Überstand unter dem Bett neu übersetzen (etwa „Below plate“), die Bausteintexte auf „protrusion“; alle Kataloge auf dieselbe Verwechslung prüfen.
- Wirkung beim Kunden: Ein englischsprachiger Kunde liest einen Überhang, wo ein Teil unter dem Bett steckt.
- Stand: behoben `40a44bcf8`; `test_catalog_terms.py::test_a_protrusion_is_never_called_an_overhang` am Stand davor in en und pt rot, danach in allen Sprachen grün.

### FD-148 V4 nimmt jede geschriebene Vorhersage an, auch eine nachträgliche

- Art: Fehler
- Schwere: leicht
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: V4
- Beleg: `tools/function_report.py` prüft an V4 nur, dass `prediction` nicht leer ist; die Fälle 29, 36 und 37 wurden so als *gut* angenommen.
- Ursache: Die Vorhersage ist nicht an den Zeitpunkt vor dem Klick gebunden.
- Vorschlag: Feld `prediction_bound` (Pfad und SHA256 der vor dem Klick freigegebenen Vorhersage); ohne Bindung ist V4 *offen*; Vorhersagetor im Fallprozess auch im Sprachdurchgang.
- Wirkung beim Kunden: Kein Produktfehler; V4 konnte ohne echte Vorhersage gelten.
- Stand: behoben `2cfa39669`; `test_function_verdict_round.py::test_a_good_v4_without_a_bound_prediction_is_rejected` am Stand davor rot; das Vorhersagetor im Fallprozess bindet die Vorhersage seit FD-168 (`d73df33ce`), und `report` prüft die Siegeldatei selbst (`d41312515`, `71856a491`).

### FD-149 Der Sperrgrund des grauen Knopfs im Fehlfall steht nicht im Bild

- Art: Fehler
- Schwere: leicht
- Funktion: `finding.action:place_on_bed`
- Prüfpunkt: 7
- Beleg: `cases/002/04-fehlfall.png` (Ausschnitt `F:\tmp-suche\abweichungen-claude\crops2\002-04-karte.png`): unter „Auf das Bett setzen“ nur der Wirkungssatz; der Sperrgrund steht nur in `function.json#messages`, beide Prüfer stützen Punkt 7 darauf.
- Ursache: Der Prüfstand nimmt Tooltip und Sperrgrund eines grauen Elements nicht als Bild auf.
- Vorschlag: Sperrgrund bzw. Tooltip des grauen Elements als eigenes Bild aufnehmen; eine JSON-Eigenschaft ersetzt kein angezeigtes Bild.
- Wirkung beim Kunden: Kein Produktfehler; Punkt 7 wurde an einer nicht gezeigten Zeile geurteilt.
- Stand: behoben `b8a329034` (Aufnahme), `2b0fcc820` (Aufruf im Fehlfall), `2ee321fd6` (nur eine echte Kurzhilfe); `test_function_surface_timing.py::test_the_reason_of_a_grey_target_is_pictured_in_the_fault_phase` am Stand davor rot, danach grün.

### FD-150 Prüfpunkt 11 findet außerhalb des Registers und an Bildtexten keine Fundstelle

- Art: Fehler
- Schwere: leicht
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 11
- Beleg: `tools/function_report.py` sucht Fundstellen nur über Registernamen und entfernt `alt` aus dem Websitetext; `resize_hole` hat `website: []` trotz `website/funktionen.html` (Abschnitt Bohrungen).
- Ursache: Website- und Handbuchstellen hängen am Registernamen; Zeilen ohne Op und Bildtexte fallen heraus.
- Vorschlag: Zeilenspezifikation um `manual` und `website` je Zeile; `_point_11` misst damit auch Nicht-Operationen; `alt` und `title` zählen zum Websitetext.
- Wirkung beim Kunden: Kein Produktfehler; Versprechen ohne Fundstelle blieben ungeprüft.
- Stand: behoben `50a5e4eaa`, `2f3220fc1`, `2b0fcc820`; Bildtexte zählen, Zeilen außerhalb des Registers finden ihre Stellen über die Spezifikation; `test_every_place_a_row_spec_names_exists` hält die Werte der drei Zeilen.

### FD-151 auto_split hat kein Beispielziel, und die Szene erlaubt kein Teilen

- Art: Fehler
- Schwere: leicht
- Funktion: `command:edit.auto_split`
- Prüfpunkt: G9
- Beleg: Fall 043 (Ausschnitt `F:\tmp-suche\abweichungen-claude\crops2\043-autosplit.png`): „Dieses Objekt passt bereits auf das Bett“; die Spezifikation fehlt. Zwilling zu FD-101.
- Ursache: Szenenkatalog und Zeilenspezifikation decken nur den Fall „passt bereits“.
- Vorschlag: Spezifikation mit Beispielziel („passt bereits“ als Rückmeldung) und ein zweiter Fall mit zu großem Körper für Vorschlag und G9.
- Wirkung beim Kunden: Kein Produktfehler; G9 und E1–E3 an auto_split waren nicht messbar.
- Stand: behoben `7ddca9f81`; `auto_split` hat an `zu_gross.netz` ein Beispielziel und den Fehlfall „passt bereits“; Wächter `test_function_rows_reach.py` am Stand davor rot.

### FD-152 I1 „jede Art“ ist aus dem Protokoll nicht prüfbar

- Art: Fehler
- Schwere: leicht
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: I1
- Beleg: `cases/002/function.json`: `hover_labels` hat einen Eintrag, ein Feld der erkannten Arten fehlt.
- Ursache: Das Protokoll hält nicht fest, welche Merkmalsarten die Erkennung an der Szene liefert.
- Vorschlag: Protokollfeld `recognized_kinds` neben `hover_labels`; `_i1` vergleicht beide.
- Wirkung beim Kunden: Kein Produktfehler; die Bauplanzusage zu I1 war nicht prüfbar.
- Stand: behoben `3d549d12e`, `634d6117b`; `test_function_judgement_scope.py::test_every_recognized_kind_must_be_hovered` verlangt jede Art aus `recognized_kinds`, ohne Liste „nicht gemessen“.

### FD-153 Funde mit integriertem Fix stehen in der Funddatei weiter offen

- Art: Aufräumen
- Schwere: leicht
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 19
- Beleg: FD-35, FD-37, FD-38, FD-43, FD-61 und FD-64 standen beim gemeinsamen Lauf auf „offen RM-…; … integriert“, obwohl ihre Fixe Vorfahren von `2ec37b23b` waren; die Abweichungen 16, 18 und 24 hängen daran. Nachgezogen hat sie `a00233340`, vor dem Eintrag dieses Funds.
- Ursache: Der Stand wurde nach dem gemeinsamen Lauf nicht nachgezogen.
- Vorschlag: Vor jeder Urteilsrunde den Stand der Funde nachziehen, deren Fix im Laufkopf liegt, mit Nachweis an ihrer Zeile.
- Wirkung beim Kunden: Kein Produktfehler; *gut nach Fix* war eine Lesart statt einer Folge der Funddatei.
- Stand: behoben `3b8b7ba28`; `report` hält einen Lauf an (Ausgang 1), solange ein offener Fund einen Commit nennt, der im Laufkopf liegt, ohne mit „Rest:“ zu sagen, was offen bleibt (`function_verdict_rules.stale_findings`); `test_function_findings.py::test_the_report_refuses_an_open_finding_whose_fix_lies_in_the_run_head` (gepflanzter offener Fund mit dem Kopf als Fix) am Stand davor rot, danach grün; die sechs Einzelfälle sind nachgezogen (`a00233340`), alle Stände vor dem Schlusslauf in `fix/w5-funde`.

## Folgefunde aus Fixen, Durchsichten und nativen Nachweisen (ab FD-154)

### FD-154 Fallprozess stirbt nach dem Abbau an einem noch laufenden Arbeiter

- Art: Stabilität
- Schwere: mittel
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 19
- Beleg: Fall 001 `resize_hole` offscreen, Exit 0xC0000409 nach `shutdown_complete: true`, `QtFatalMsg QThread: Destroyed while thread '' is still running` (`F:\tmp-suche\review-d0rest-claude\r2\qthread-beleg\`, Review RD-10); dieselbe Signatur in zwei nativen Fällen aus `fd83-claude.md`. Nachgestellt deterministisch mit einem 3-s-Arbeiter am echten Fenster über `shutdown_window` (0xC0000409 nach 2,04 s) und an einer Minimalsonde; Kundenwege Beenden, Dialog schließen, Projektwechsel und `quit` am Original Exit 0 (`output/konsolidierung-2026-10-12/fd154-claude.md`).
- Ursache: PySides `atexit`-Haken zerstört jedes Python-eigene QObject; `shutdown_window` gab `MainWindow.release` 2 s für alle Arbeiter, wer länger rechnete, lief beim Prozessende noch, und kein Weg im Prozess wartete vorher auf alle Fäden.
- Vorschlag: ein Abbauweg in der Leine: ein `atexit`-Haken vor dem von PySide wartet über `finish_before_exit` bis `EXIT_WAIT_MS` und beendet sonst benannt mit `STRAGGLER_EXIT_CODE`; `shutdown_window` wartet dort vor Renderer und Fenster.
- Wirkung beim Kunden: keine belegte, das Hauptfenster schließt erst nach dem letzten Arbeiter; in der Abnahme falsche rote Fälle, deren Ursache weit vom Fall entfernt steht.
- Stand: behoben `a177d903d`; `tests/test_leash.py::test_a_process_that_ends_while_a_worker_runs_waits_for_it` war am Original mit genau der Signatur rot; Prüfstandsweg mit 3-s-Arbeiter 3/3 Exit 0, Fall 001 zehnmal Exit 0; in welle4 `81a63d962`.

### FD-155 Parameter anlegen lehnt einen Namen ohne Handlung und abseits des Felds ab

- Art: Verständlichkeit
- Schwere: mittel
- Funktion: `Bearbeiten/Parameter anlegen …`
- Prüfpunkt: 7, E7, V5
- Beleg: Fall 003 `04-fehlfall-dialog.png` und `function.json#messages` im finalen Lauf: „Der Name muss sich in einem Ausdruck als @name schreiben lassen — Buchstaben, Ziffern und Unterstriche.“ steht unter „Weitere Einstellungen“, das Feld ist nicht markiert, eine Handlung fehlt (`output/konsolidierung-2026-10-12/funde-stand-claude.md`, neuer Punkt). Die D10-Urteile führten das bisher unter FD-39, das nur die Aufnahme betraf.
- Ursache: offen; die Ablehnung des Namens wird als allgemeiner Hinweis des Dialogs gesetzt, nicht am Feld.
- Vorschlag: Die Ablehnung steht am Namensfeld, das Feld wird markiert und bekommt den Fokus; der Satz nennt den Weg (etwa einen gültigen Vorschlag aus dem eingegebenen Text).
- Wirkung beim Kunden: Der Kunde sucht, welches Feld falsch ist, und findet den Satz an anderer Stelle.
- Stand: behoben `77ea99596`, `f84328243`; `test_a_refused_name_stands_at_the_name_field_with_its_way` am Stand davor rot, danach steht die Ablehnung markiert am Namensfeld mit einem freien Namen als Knopf; Bild hell und dunkel.

### FD-156 Sechs Fenstertests hielten an der Bohrung und in der Suche das Verhalten vor drei Fixes fest

- Art: Fehler
- Schwere: mittel
- Funktion: `search`, `tool:section`, `tool:measure`
- Prüfpunkt: 19
- Beleg: Sechs Fälle in `tests/test_ui.py` auf main grün, auf welle4 rot, auch allein (`output/konsolidierung-2026-10-12/d0-testfix-claude.md`, N1; Bisektion auf `6238bf7fd`, `b86381559`, `3d6a080c8`); je Fall Ursache, Gegenprobe und Lauf in `output/konsolidierung-2026-10-12/fd156-claude.md`.
- Ursache: Fünf Fälle prüften das Verhalten vor FD-34, FD-63 und FD-16 (offene *Merkmal verschieben* neben der Maßgruppe, Stelle vorn, Katalog als zweiter Hauptknopf; die Höhe ohne Fokus getippt). Der sechste traf zusätzlich einen Produktfehler: `ToolStrip.set_shortcut` schrieb beim Bau des Fensters Titel und Kürzel über den Grund eines grauen Werkzeugs, und die Suche nannte seit FD-26 diesen Namen als Grund.
- Vorschlag: Fälle auf die gewollte Wirkung stellen, je mit Gegenprobe gegen den alten Stand; `set_shortcut` schreibt über `_hint_of`, die eine Stelle für den Hinweis.
- Wirkung beim Kunden: Auf einer leeren Szene stand an einem grauen Werkzeug seit v0.1.1 nur sein Name statt des Grundes, in der Suche auf welle4 auch als Grund; die übrigen fünf Fälle waren kein Produktfehler, hätten aber die Fensterprüfung nach dem Push nach main rot gemacht.
- Stand: behoben `bbd2c2c59`, `fae59424c`, `bbff466e0`; in welle4 `b156f8f4d`, test_ui 802 offscreen grün.

### FD-157 Der Wortschatzfall las die Verlaufszeile, während die Seitenkarte noch glitt

- Art: Fehler
- Schwere: leicht
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 19
- Beleg: `tests/test_guide_targets.py::test_every_new_kind_resolves_on_a_prepared_window` verlangte nach dem Aufklappen der Verlaufsgruppe sofort `ziel`; im dunklen Thema am Stand `d1f4fd3f2` 3 von 3 Läufen `rollen` (`output/konsolidierung-2026-10-12/d0-testfix-claude.md`, N2; `fd156-claude.md`, Abschnitt 4). Schlussreview D0 (RF-1): In der langen Dateireihenfolge von Lauf B/B2 waren dieser Fall und `test_next_click_names_each_step_in_order_and_reveals_nothing` rot (`('ziel', 0)`, `MissingTargetError` an `tree.row:obj_1.hole_1`), nachgestellt am Stand `3d9ede08f` mit 2 failed, 629 passed; die Sonde `ruhe_sonde.py` zeigt fast jede Antwort von `next_click` während einer laufenden Kartenbewegung, nach dem Gleiten heißt es sofort `ziel` (`output/konsolidierung-2026-10-12/review-d0-final-claude.md`, `d0-final-fix-claude.md`).
- Ursache: `prepared_window` und die Fälle lasen nach 20 Ereignisrunden, während die Seitenkarte noch `overlay.MOVE_MS` zu ihrem Platz glitt. Wie weit sie kam, hing an der Rechnerlast: Eine halb gewachsene Karte zeigte die Zeile halb (`rollen`) oder gar nicht (`MissingTargetError`). Das Kundenthema allein erzwingt kein Rollen.
- Vorschlag: Fenster und Fälle warten nach dem Aufbau und nach jedem Aufklappen, bis keine Karte mehr gleitet und kein Setzen vorgemerkt ist (`tests/guide_window.py`, `at_rest`); danach verlangt der Fall ohne Rollen `ziel` und die ganz sichtbare Zeile.
- Wirkung beim Kunden: Kein Produktfehler; nach dem Gleiten der Karte steht die Zeile ganz da. Der Fall war uhrabhängig und hätte bis zu drei Rollschritte zugelassen, die der Kunde nicht braucht.
- Stand: behoben `88ae173a2` (zuvor `99d057c12`); Gegenprobe ohne Warten rot (`'rollen' == 'ziel'`), die Reihenfolge von Lauf B2 grün (630 passed), die Datei allein 50 passed.

### FD-158 Vorschaurückrufe greifen nach dem Abbau auf den Objektbaum zu

- Art: Stabilität
- Schwere: leicht
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 19
- Beleg: Fällt `test_panel_dimensions_and_placement_position_are_adopted_together[normal]` mitten im Fluss rot aus, greifen danach laufende Vorschaurückrufe auf den abgebauten Objektbaum zu (`_ObjectTreeView already deleted`); am Stand `0659b226d` endete der Prozess dann mit 0xC0000409, seit FD-154 mit Exit 1 (`output/konsolidierung-2026-10-12/fd156-claude.md`, Offen N1).
- Ursache: offen; der Rückruf hält das Fenster stark und prüft nicht, ob seine Widgets noch leben.
- Vorschlag: Rückrufe halten das Fenster nur schwach oder prüfen es mit `shiboken6.isValid`, an der einen Stelle, die Vorschaurückrufe anmeldet; Test, der das Fenster vor dem Rückruf abbaut.
- Wirkung beim Kunden: keine belegte; beim Schließen während einer laufenden Vorschau könnte ein Rückruf ins Leere greifen.
- Stand: behoben `1e83dcc92`; `test_preview_teardown_window.py` baut das Fenster zwischen Anfrage und Antwort ab: am Stand davor rot (RuntimeError), danach grün.

### FD-159 Die Anleitungsnavigation verwirft erreichbare Ziele unter einer verschachtelten Liste

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Gemeinsame Anleitungsnavigation und Funktionsaufnahme
- Prüfpunkt: 1
- Beleg: Nativer Lauf am echten Fenster auf welle4 `7d978c4ee`, Fall 032 EN: `filament.picker` und `filament.section` enden „nicht auffindbar: Rollanschlag oder kein geeigneter Radschritt“, obwohl der Rollbalken 170 px Restweg hat und 132 px fehlen; zwei lesende Diagnoseläufe (`output/konsolidierung-2026-10-12/native-d0-claude.md`, Nachweis 1).
- Ursache: Die Trefferprobe in `guide_targets._scroll_needed` trifft in der Mitte der Sichtfläche eine verschachtelte Liste (`_ListScroller`) statt des äußeren Rollbereichs und verwirft jeden Rollschritt; Regression aus FD-77.
- Vorschlag: Den Rollschritt an den Rollbereich geben, der das Ziel enthält und weiter rollen kann, nicht an das Widget unter der Mitte; Gegenprobe mit verschachtelter Liste.
- Wirkung beim Kunden: Kein Produktfehler; `next_click` rufen nur die Prüfstandsmodule, Tour und Bildanleitungen gehen über `area_for`. Der Prüfstand erreicht den Filamentwähler nicht (032 EN), seine Zeilen bleiben dort ungemessen.
- Stand: behoben `827f9d1ae`; die Gegenprobe mit verschachtelter Liste in `test_guide_obstacle_scroll.py` am Stand davor rot, offscreen erreicht der Sprachfall die Filamentzeilen; nativer Nachweis an 032 EN im Schlusslauf (Plan Punkt 1 und 2).

### FD-160 Nach „Abbrechen“ der Maßgruppe steht der Fokus auf dem Kartengriff „Objekte“

- Art: Einfachheit
- Schwere: leicht
- Funktion: `resize_hole`
- Prüfpunkt: 10
- Beleg: Native DE-Maßkartenfolge auf `7d978c4ee` (`native-d0-claude.md`, neuer Punkt 2): nach *Abbrechen* Fokus auf dem Kartengriff „Objekte“, nach *Übernehmen* und Undo dagegen in der 3D-Ansicht.
- Ursache: offen; Abbrechen gibt den Fokus nicht an die Ansicht zurück, aus der die Maßgruppe kam.
- Vorschlag: Alle drei Ausgänge der Maßgruppe geben den Fokus an dieselbe Stelle zurück (die Ansicht).
- Wirkung beim Kunden: Wer nach Abbrechen eine Taste drückt, bedient die Objektkarte statt der Ansicht.
- Stand: behoben `9e7076c0e`; `tests/test_measure_card_exits.py` am Stand davor rot (Fokus auf `CardGrip`), danach enden alle vier Ausgänge in der Ansicht; nativer Nachweis im Schlusslauf (Plan Punkt 36).

### FD-161 Eine geänderte Bohrung springt im Objektbaum ans Listenende

- Art: Einfachheit
- Schwere: leicht
- Funktion: `resize_hole`
- Prüfpunkt: 3
- Beleg: Native DE-Maßkartenfolge auf `7d978c4ee` (`native-d0-claude.md`, neuer Punkt 3); am Stand vor D0 genauso.
- Ursache: offen; der Baum ordnet ein geändertes Merkmal neu ein statt an seiner Stelle.
- Vorschlag: Ein geändertes Merkmal behält seinen Platz im Baum.
- Wirkung beim Kunden: Nach jeder Änderung sucht der Kunde die Bohrung neu.
- Stand: behoben `78f130336`; `test_feature_order.py::test_a_resized_hole_keeps_its_place_among_the_features` am Stand davor rot, danach grün; nativer Nachweis im Schlusslauf (Plan Punkt 36).

### FD-162 Die Undo-Blase verdeckt die Sammelzeile, und die Statuszeile meldet danach weiter „zurückgenommen“

- Art: Gestaltung
- Schwere: leicht
- Funktion: `resize_hole`
- Prüfpunkt: 9
- Beleg: Native DE-Maßkartenfolge auf `7d978c4ee` (`native-d0-claude.md`, neuer Punkt 4): Die Blase steht 6,7 s über Wiederwahl, Aufklappen und Tippen und verdeckt die Zeile des Sammelhakens; nach der nächsten Übernahme meldet die Statuszeile weiter „zurückgenommen“. Zwilling zu FD-108 (Quittung am Zeiger über dem Bericht).
- Ursache: offen; die Quittung kennt weder die Lage der Karten noch den nächsten Schritt.
- Vorschlag: Mit FD-108 eine Regel für Quittungen: nie über einer Karte, weg mit dem nächsten Schritt; die Statuszeile folgt dem letzten Schritt.
- Wirkung beim Kunden: Die Blase deckt die nächste Bedienung zu, und die Statuszeile widerspricht dem Stand.
- Stand: behoben `c5b2387a9` (Wurzel mit FD-108); `test_action_notice_window.py` (der nächste Schritt nimmt die Quittung mit, eine Karte schiebt sie beiseite) am Stand davor rot, danach grün; nativer Nachweis im Schlusslauf (Plan Punkt 36).

### FD-163 Prozesse des Prüfstands schreiben kein Dateiprotokoll

- Art: Fehler
- Schwere: leicht
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 19
- Beleg: Native Läufe auf `7d978c4ee` (`native-d0-claude.md`, Nachweis 3 und neuer Punkt 5): Die Zeile, mit der FD-154 auf einen Arbeiter wartet, steht in keinem Protokoll des Falls, weil nur `main()` das Dateiprotokoll einrichtet; die Zusage in `fd154-claude.md` trifft so nicht zu.
- Ursache: Der Fallprozess richtet das Protokoll der Anwendung nicht ein.
- Vorschlag: Der Fallprozess richtet dasselbe Dateiprotokoll ein wie `main()`, im isolierten Profil des Falls.
- Wirkung beim Kunden: Kein Produktfehler; Ursachen in Fallprozessen bleiben ohne Protokoll.
- Stand: behoben `e01effdab`; ein Fallprozess schreibt `app.log` in sein Profil, `test_file_acceptance_log.py` am Stand davor rot.

### FD-164 Die nativen Läufer liegen außerhalb des Repositorys und starten ohne Siegelprüfung

- Art: Stabilität
- Schwere: mittel
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 19
- Beleg: Die DE-Maßkartenfolge läuft über `F:\tmp-suche\fix-massgruppe-front-codex\native-runner-v3\Run-Language.ps1`, der Fall 032 über `F:\tmp-suche\fix-projektwechsel-crash-codex\final_d0_cli.py`, beide außerhalb des Baums; im Läuferordner lag eine spätere, ungesiegelte Ergänzung, die `Run-Language.ps1` ohne Prüfung gefahren hätte, und ihre Cursorlesung zielt auf das Hauptfenster statt auf das eigene Fenster der Maßkarte (`native-d0-claude.md`, Nachweis 2b und neuer Punkt 6).
- Ursache: Die nativen Anschlüsse entstanden als Sitzungswerkzeuge und wurden nie ins Repository übernommen.
- Vorschlag: Die nativen Läufer (Fallbrücke, Maßkartenfolge, Bindung und Siegel) nach `tools/` übernehmen, mit Siegelprüfung vor dem Start, als Schritt in `/erzeugen` (Konzept §8, §10); die Cursorlesung am Fenster des Druckempfängers.
- Wirkung beim Kunden: Kein Produktfehler; der Wiederholungslauf beim Release wäre auf keinem frischen Stand reproduzierbar.
- Stand: behoben `fb4c91507`, `3dfe19ba1`, `f188d9ca7`; Fallbrücke und Maßkartenläufer stehen als `tools/native_runs.py`, `tools/native_binding.py` und `tools/native_measure_card.py` im Repository, mit Siegel vor dem Start, im Kind vor Qt und danach; `tests/test_native_runs.py` belegt die Verweigerung bei geänderter Läuferdatei; nativer Nachweis der Maßkartenfolge im Schlusslauf (Plan Punkt 3, L1).

### FD-165 Formschräge und Fläche versetzen bieten „Andere Objekte wählen“ an

- Art: Zwillinge
- Schwere: leicht
- Funktion: `draft_faces`, `push_face`
- Prüfpunkt: 7, V5
- Beleg: Neuer Punkt in `output/konsolidierung-2026-10-12/fix-f6-claude.md`: `brep/profiles.py` `draft_faces` (6 Stellen), `geom/faces.py` (11 Stellen, Formschräge und *Fläche versetzen*) und `face_ops._no_face` boten `CHANGE_SELECTION`; `tests/test_face_refusal_ways.py` am Stand davor 8 rot, jede Meldung „['…', 'Andere Objekte wählen', 'Abbrechen']“ (`fix-rest-b-claude.md`). Zwilling von FD-123.
- Ursache: Die Flächenabsagen beider Kerne trugen `CHANGE_SELECTION`; dessen Handler gibt dem Schritt die im Baum markierten Körper.
- Vorschlag: `errors.CHANGE_FACES` („Andere Flächen wählen“, `change_step`) an allen Flächenabsagen beider Kerne, nach dem Schritt, der die Absage auslöst.
- Wirkung beim Kunden: Wer der Absage folgt, tauscht die Körper des Schritts statt der Flächen und kommt nicht weiter.
- Stand: behoben `b353f58d9`, nach Review `36cdd9fe2` (Handlung nach dem auslösenden Schritt); `test_face_refusal_ways.py` am Stand davor 8 rot, danach grün, beide Kerne und *Fläche versetzen*.

### FD-166 Doppelklick auf einen Parametereintrag im Verlauf bleibt stumm

- Art: Fehler
- Schwere: mittel
- Funktion: `history`, `Bearbeiten/Parameter anlegen …`
- Prüfpunkt: 12
- Beleg: `output/konsolidierung-2026-10-12/fix-f8-claude.md` (FD-127): *Parameter anlegen* legt eine Transaktion ohne Operation an, ihre Verlaufszeile trug weder `UserRole` noch `OPS_ROLE`; `test_history_parameter_rows.py` am Stand davor rot (`[] == ['hoehe']`), `test_history_parameter_window.py` ohne Verdrahtung rot (`[] == ['breite']`) (`fix-f4-claude.md`, `fix-rest-a-claude.md`); Review RA-6: auch die Zeilen für Drucker, Material und Passung blieben stumm.
- Ursache: `HistoryPanel._on_activated` kannte nur Zeilen mit Schritt; eine Maßänderung, eine Drucker- oder Materialwahl und eine Passung hatten keinen Weg.
- Vorschlag: Die Zeile trägt das Maß (`PARAMETER_ROLE`), Doppelklick öffnet *Ändern …* des Maßes; Drucker und Material öffnen die Druckeinstellungen, eine Passung sagt ihren Weg.
- Wirkung beim Kunden: Ein Doppelklick auf eine Verlaufszeile tat nichts, obwohl er an jeder anderen Zeile den Schritt öffnet (§2.1).
- Stand: behoben `3f7011cd1`, `91ff3d3b4`, `94f620bec`, `18ebb9a2d`; `test_history_parameter_window.py` ohne Verdrahtung rot, `test_history_change_rows.py` am Stand davor rot (alle drei Zeilen stumm), danach öffnet der Doppelklick das Maß oder die Druckeinstellungen, an einer Passung steht ein Satz mit dem Weg.

### FD-167 Ein Körperabschied mitten in einer Schleife über die Erkennungsmerker bricht sie ab

- Art: Stabilität
- Schwere: mittel
- Funktion: keine Zeile: Erkennungsarbeiter der Merkmalserkennung
- Prüfpunkt: 6
- Beleg: `tests/test_features.py::test_a_face_keeps_its_area_unrounded` einmal mit `RuntimeError: dictionary changed size during iteration` an `features.py:1305` (`output/konsolidierung-2026-10-12/fix-f10-claude.md`, neuer Punkt 1); ohne Eingriff nachgestellt (`fd167-claude.md`): je Runde ein toter Körper mit Merker im Zyklus, gehaltene Listen, dann `forget_cache` — am Original 2 von 8 000 Runden rot, zweimal bei denselben Runden; Zwilling in `answered_ahead` (`OrderedDict mutated during iteration`) und in `app_events.listening`.
- Ursache: `_forget_body` läuft als `weakref.finalize` aus der Speicherbereinigung an jedem Prüfpunkt einer Schleife, auch unter dem wiedereintrittsfähigen `_MEMORY_LOCK`, und nimmt aus `_MEMORIES` und `_BY_GEOMETRY`; zwei Schleifen liefen unmittelbar über diese Merker, `app_events.listening` über die Arten, aus denen der Rückruf eines sterbenden Zuhörers nimmt.
- Vorschlag: Die Schleifen über Schnappschüsse (`tuple(...)`), Wächter über jede Schleife an den sechs Merkern, Regel in `kern.md`.
- Wirkung beim Kunden: Bei Modellen ab 50 000 Dreiecken konnte ein Erkennungsarbeiter seinen Teil verlieren oder enden; der Hauptprozess rechnete ihn selbst, mit demselben Ergebnis, nur langsamer.
- Stand: behoben `ff0a27705`; neue Fälle am Original rot, am Fix grün; druckgleich an 12 Beispielprojekten und 6 Modellen; in welle4 `5abf5f5b0`.

### FD-168 Der Fallprozess hält vor dem Klick nicht für die Vorhersage an

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Fallprozess des Prüfstands (V4)
- Prüfpunkt: V4
- Beleg: Neuer Punkt in `output/konsolidierung-2026-10-12/fix-f8-claude.md`: FD-148 verlangt `prediction_bound`, aber kein Fallprozess hielt vor dem Klick an; die Vorlage `v4_observer.py` hängte sich als Sitzungswerkzeug per Monkeypatch nur in drei Basisfälle; `test_fd168_rot.py` am Stand davor rot („unbekannte Angaben in der Variante: predict“) (`fix-rest-c-claude.md`).
- Ursache: Der Prüfstand hatte kein Tor zwischen „vor dem Übernehmen“ und dem Klick.
- Vorschlag: `tools/function_prediction.PredictionGate`: vor dem Klick Bild und `ready.json`, die Vorhersage des Prüfers binden und versiegeln, `prediction.bound` ins Protokoll; `report` prüft die Bindung.
- Wirkung beim Kunden: Kein Produktfehler; ohne Tor blieb jedes V4 bis zur Nachurteilsrunde abgewiesen.
- Stand: behoben `d73df33ce`, `b3c72a8db`, `d41312515`, `71856a491`; ein Fall mit dem Variantensatz `vorhersage` hält vor dem Handlungsklick an, bindet und versiegelt die Vorhersage, `report` rechnet Siegel und Vorhersage selbst nach; `test_function_prediction_seal.py` am Stand davor rot (5 von 6 Verfälschungen angenommen), offscreen 51 Tore gebunden; nativer Nachweis mit Schreiber im Schlusslauf (Plan Punkt 33, L5).

### FD-169 E4 ist an Handlungen am ganzen Körper nicht gemessen

- Art: Fehler
- Schwere: leicht
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands (E4)
- Prüfpunkt: E4
- Beleg: Neuer Punkt M-E4 in `output/konsolidierung-2026-10-12/fix-f8-claude.md`: sechs E4-Abweisungen an `finding.action:*`; `FunctionFlow.spot` misst nur an gewähltem Merkmal oder gewählter Kante und liefert sonst `None`; zwei Gegenproben in `function_samples.BROKEN_SAMPLES` blieben am Stand davor grün (`fix-rest-c-claude.md`).
- Ursache: `_e4` verlangte `spot` nur an Zeilen mit Auswahlbezug; an *Auf das Bett setzen* blieb E4 ohne Stellenmessung.
- Vorschlag: den Rahmen der geänderten Körper im Ergebnisbild messen (`tools/function_spot.py`); E4 meldet „Stelle nach dem Ergebnis außerhalb des Bildes“.
- Wirkung beim Kunden: Kein Produktfehler; E4 galt an Ganzkörperhandlungen ohne Messung.
- Stand: behoben `554c70de7`, `9f59786e0`; die Gegenproben am Stand davor grün geblieben, danach rot; nativer Nachweis des Rahmens im Schlusslauf (Plan Punkt 31).

### FD-170 Die Hauptlinien des Bettrasters liegen nicht an den Maßzahlen

- Art: Gestaltung
- Schwere: leicht
- Funktion: keine Zeile: Druckbett in der 3D-Ansicht
- Prüfpunkt: 9, 19
- Beleg: Neuer Punkt in `output/konsolidierung-2026-10-12/fix-f5-claude.md`: `shapes.grid_lines` teilte 256 mm ab der Ecke in 26 Felder zu 9,85 mm, Hauptlinien bei −128, −78,8, −29,5, 19,7 …, die Zahlen stehen bei 0, ±50, ±100; Bild `bilder-fix-f5/fd92-nachher-hell-mm.png` („0“ zwischen zwei Hauptlinien); `test_bed_grid_visibility.py` am Stand davor 4 rot (`fix-rest-b-claude.md`).
- Ursache: Raster und Skala rechneten von verschiedenen Nullpunkten — das Raster ab der Ecke der Platte, die Skala ab der Mitte.
- Vorschlag: Hauptlinien auf den Lagen der Skala, Nebenlinien 10 mm, 1 cm bzw. ½ in, der Rand als Nebenlinie (Entscheidung Koordinator: Linien an die Zahlen, FD-68-Test entsprechend).
- Wirkung beim Kunden: Das „10-mm“-Raster ist keines, und die Null steht zwischen zwei Hauptlinien — Lagen lassen sich am Raster nicht abzählen.
- Stand: behoben `46215f53a`; `test_bed_grid_visibility.py` (umgestellter FD-68-Test) am Stand davor 4 rot, dazu `test_bed_grid_at_scale.py`, danach Hauptlinien an den Zahlen in mm und Zoll, hell und dunkel offscreen gesehen; nativer Nachweis im Schlusslauf (Plan Punkt 9).

### FD-171 Prüfpunkt 15 meldete „nicht auffindbar“ gegen die Anwendung

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 15
- Beleg: Neuer Punkt 1 in `output/konsolidierung-2026-10-12/fix-f7-claude.md`: Die Einfügemarke stand vor dem letzten Schritt der Startszene; entstand dort, worüber der Weg führt, gab es ihn am Stand davor nicht (Läufe 001 und 002 im Probelauf und im finalen Lauf: `tree.row:obj_1.hole_1`, `finding:arrange.below_bed`); jede Absage hieß „ergebnis“; `test_function_insertion.py` am Stand davor rot (2).
- Ursache: Die Phase setzte die Marke ohne Blick auf die Wegziele und las die Antwort gegen den Endstand.
- Vorschlag: Fehlt ein Wegziel aus der Szene, wendet der Fall die Zeile einmal an und setzt die Marke vor diesen Schritt; die Antwort gilt gegen den Stand davor.
- Wirkung beim Kunden: Kein Produktfehler; Prüfpunkt 15 meldete an jeder Zeile einen Fund, den die Anwendung nicht hatte.
- Stand: behoben `f137c9c81`; `test_function_insertion.py` am Stand davor rot, danach zweimal grün.

### FD-172 Ein Fenster aus dem Ereignisdurchlauf hielt den Prüfstand bis zur Frist an

- Art: Stabilität
- Schwere: mittel
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 19
- Beleg: Neuer Punkt 2 in `output/konsolidierung-2026-10-12/fix-f7-claude.md`: Fragt ein Arbeiter (*Alle Merkmale erkennen*) oder kommt eine Absage als Meldung, geht das modale Fenster in `pump` auf; Stapel per faulthandler über fünf Minuten in `show_error`, `_on_ask`; `test_function_machine_outside.py` mit Gegenprobe.
- Ursache: Der Automat war fertig, `drive` stand in der Schleife des modalen Fensters, und niemand räumte die tiefere Ereignisschleife ab.
- Vorschlag: `StepMachine(nested=…)` räumt eine tiefere Ereignisschleife ab wie eine eigene.
- Wirkung beim Kunden: Kein Produktfehler; ein Fall hing bis zur Frist und lieferte kein Ergebnis.
- Stand: behoben `8a18eaa3c`; `test_function_machine_outside.py` am Stand davor rot, danach grün.

### FD-173 Ein Dateifall hängt an einem Fenster aus dem Ereignisdurchlauf

- Art: Zwillinge
- Schwere: mittel
- Funktion: keine Zeile: Dateifälle von `tools/file_acceptance.py`
- Prüfpunkt: 19
- Beleg: Zwilling von FD-172 (`output/konsolidierung-2026-10-12/fix-f7-claude.md`, neuer Punkt 2): `file_acceptance.WindowFlow.drive` baute `StepMachine` ohne `nested`; `tests/test_file_acceptance_modal.py` am Stand davor rot („der Wachhund musste das Fenster schließen — der Fall hing“) (`fix-rest-c-claude.md`).
- Ursache: dieselbe Bauart wie vor `8a18eaa3c`: Ein Fenster, das in `pump` per `exec()` aufgeht, ließ den fertigen Automaten ohne Takt.
- Vorschlag: `function_machine.nested_since_now()` als eine Quelle für Funktions- und Dateifall.
- Wirkung beim Kunden: Kein Produktfehler; ein Dateifall hätte bis zur Frist gehangen.
- Stand: behoben `e45cf2c30`; `test_file_acceptance_modal.py` am Stand davor rot, danach grün.

### FD-174 Rechtsklick auf das Wertfeld einer Parameterzeile öffnet Qts englisches Textfeldmenü

- Art: Fehler
- Schwere: mittel
- Funktion: `parameters.first`, `menu:parameters.edit`
- Prüfpunkt: 1, 9
- Beleg: Neuer Punkt 4 in `output/konsolidierung-2026-10-12/fix-f7-claude.md`: `probe_rechtsklick.py` (offscreen, Szene `parameter.netz`): Wertfeld → Menü des `QLineEdit` mit „&Undo, &Redo, Cu&t, &Copy, &Paste, Delete, &Select All, &Step up, Step &down“; Beschriftung → Menü der Leiste mit *Ändern …*; `test_parameter_row_menu.py` am Stand davor rot (`fix-f4-claude.md`).
- Ursache: Das Wertfeld brachte sein eigenes Kontextmenü mit, obwohl beide Hälften der Zeile dieselbe Zeile meinen (`panels._remember_row`).
- Vorschlag: Das Wertfeld hat kein eigenes Menü; der Rechtsklick geht an die Leiste (*Ändern …*).
- Wirkung beim Kunden: Rechts auf den Wert geklickt, sieht er ein englisches Textfeldmenü statt *Ändern …* (Regel 20).
- Stand: behoben `52a6a5c65`; `test_parameter_row_menu.py` am Stand davor rot, danach zeigt der Rechtsklick genau `parameters.edit`.

### FD-175 Zeilen der übrigen Pakete haben keinen Weg zu ihrer Fläche

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 1, 2
- Beleg: Neuer Punkt 5 in `output/konsolidierung-2026-10-12/fix-f7-claude.md`: 37 Zeilen in D9 und D12 ohne Weg zu ihrem Fenster (u. a. `dialog:print_settings_dialog`, `dialog:new_filament_dialog`, `dialog:settings_dialog`, `meldung:_assign_inventory_spool`); `fix-rest-c-claude.md`: zusammen 59 Zeilen (37 in D9/D12, 22 in D1, D2, D7, D11), der Wächter über alle Pakete am Stand des Merges rot.
- Ursache: Im Sprachfall erreicht der Prüfstand ein Fenster nur über eine `route` der Spezifikation; einige Zeilen brauchten Zustände, die kein Fallprozess herstellte, und die Startzeile lief nur auf Deutsch.
- Vorschlag: Wege und Szenen in allen Paketen, Nähte des Prüfstands für Zustände, die er nicht herstellen kann (`tools/function_seams.py`), Wächter `test_no_row_of_any_package_is_without_a_way` über alle Pakete.
- Wirkung beim Kunden: Kein Produktfehler; 59 Zeilen blieben ungemessen.
- Stand: behoben `9caab1f38`, `3010e5ac0`, `22f869c52`, `ccbcb5810`, `de8ef25ca`, `49a3fdba2`, `c12710342`, `4f01e4fbd`, `1c9bc2975`; jede der 59 Zeilen hat Route, Szene und wo nötig eine Naht und ist offscreen im Sprachfall erreicht, die Startzeile je Sprache im Startfall; der Wächter war am Stand des Merges rot; Bilder am echten Fenster im Schlusslauf (Plan Punkt 32).

### FD-176 *Material kalibrieren* folgt der Zollanzeige nicht

- Art: Fehler
- Schwere: leicht
- Funktion: `Bearbeiten/Material kalibrieren …`, `dialog:calibration_dialog`
- Prüfpunkt: 9
- Beleg: Neuer Punkt in `output/konsolidierung-2026-10-12/fix-f2b-claude.md`: Die Längenfelder (`clearance`, `press`, `hole_compensation`, `elephant_foot`, `minimum_wall`) sind `NumberSpin` mit festem „ mm“ (`calibration_dialog.py:137–146`); `tests/test_calibration_units.py` am Stand davor 3 von 3 rot, Bild `fd176-kalibrieren-zoll-*` „0,250 mm“ trotz Zoll (`fix-f2a-claude.md`).
- Ursache: Die Felder kannten die Anzeigeeinheit nicht; `LengthSpin` hätte die dritte Stelle dieser Feinmaße verloren.
- Vorschlag: ein feines Längenfeld mit einer Stelle mehr als die Einheit, gelesen in mm; die Druckbedingungen darunter über `labels.length`.
- Wirkung beim Kunden: In Zoll liest er Millimeterwerte und tippt sie falsch ein.
- Stand: behoben `3fdb20462`, `0be16540e` (eine Quelle der Feinheit, `fine_length_spin.finer`); `test_calibration_units.py` am Stand davor rot, danach Längen in der Anzeigeeinheit mit dritter Stelle, gespeichert in mm; nativer Nachweis im Schlusslauf (Plan Punkt 15).

### FD-177 Tab von der Reiterleiste springt an der Seite vorbei

- Art: Fehler
- Schwere: leicht
- Funktion: `report`, `selection`
- Prüfpunkt: 10
- Beleg: Neuer Punkt in `output/konsolidierung-2026-10-12/fix-f4-claude.md`: In der rechten Karte steht der Reiterbalken (`SignalTabBar`) in der Fokuskette hinter dem Inhalt seiner Seite; Tab vom Reiter *Prüfbericht* springt zu Kopfzeile und linker Karte (SignalTabBar → PrintFacts → … → Bericht); `test_card_tab_chain.py` am Stand davor 3 von 3 rot (`fix-rest-a-claude.md`).
- Ursache: Qt reiht Seiten nach der Entstehung ein, und `setTabOrder(tabBar, page)` greift an einem Behälter ohne Fokus nicht.
- Vorschlag: `SignalTabBar.focusNextPrevChild` legt die Halte der vorderen Seite in Layoutfolge hinter die Leiste (`tab_stops.chain_after`).
- Wirkung beim Kunden: Wer per Tastatur vom Reiter in den Bericht will, landet in Kopfzeile und linker Karte.
- Stand: behoben `1d9db4c0e`, `a7bc3312d`; `test_card_tab_chain.py` am Stand davor rot, danach geht Tab von der Reiterleiste in die vordere Seite; den Tastaturweg ab der Leiste geht der Prüfstand seit `3a70b3806`; nativer Nachweis im Schlusslauf (Plan Punkt 7).

### FD-178 Rundungsabsagen ohne zwei Ebenen bieten „Andere Objekte wählen“ an

- Art: Zwillinge
- Schwere: leicht
- Funktion: `fillet_edges`, `remove_feature`, `resize_feature`
- Prüfpunkt: 7, V5
- Beleg: `output/konsolidierung-2026-10-12/fix-rest-b-claude.md`: `edges.NOT_BETWEEN_TWO_PLANES` an vier Stellen (`geom/edges.py:3825, 3926`, `geom/prepare_ops.py:24081`, `brep/edit.py:4081`) und vier weitere Flächenabsagen (Aushöhlen, Befund ohne Hohlraum, Dichtnut, Muster bis zum Rand) boten `CHANGE_SELECTION`; `test_edge_refusal_ways.py` und `test_face_refusal_ways.py` am Stand `3ea182a86` 4 rot. Dritter Zwilling von FD-123 und FD-165.
- Ursache: Die Absagen trugen die Objektwahl, wo eine Kante oder Fläche gemeint ist; Review RB-1: die Rundungsabsagen kommen auch über *Merkmal entfernen* und *Merkmal ändern* ohne Kantenfeld.
- Vorschlag: Kantenabsagen `CHANGE_EDGES`, Flächenabsagen `CHANGE_FACES`, jeweils nach dem Schritt, der die Absage auslöst.
- Wirkung beim Kunden: Der angebotene Weg tauscht die Körper des Schritts und führt nicht zur Rundung oder Fläche.
- Stand: behoben `69e52b1ab`, nach Review `36cdd9fe2`; die beiden Tests am Stand davor 4 rot, danach grün; der Kantenwächter erfasst jede Kantenabsage beider Kerne (`2789be78c`).

### FD-179 Merkmalsabsagen bieten „Andere Objekte wählen“, wo ein anderes Merkmal gemeint ist

- Art: Zwillinge
- Schwere: leicht
- Funktion: `resize_chamber`, `resize_closure`, `pin_for_bore`, `pattern_feature`, `move_feature`, `resize_hole`
- Prüfpunkt: 7, V5
- Beleg: `output/konsolidierung-2026-10-12/fix-rest-b-claude.md`: 32 Absagen an Schritten mit `at_feature`/`at_features` (Bohrungskette, Gewinde, Kammer, Verschluss, Ring, Merkmalsoperationen, Muster) boten `CHANGE_SELECTION`; `test_feature_refusal_ways.py` am Stand `69e52b1ab` 12 rot. Vierter Zwilling von FD-123.
- Ursache: Die Objektwahl stand an Absagen, deren Schritt ein Merkmal wählt.
- Vorschlag: `errors.CHANGE_FEATURE` („Anderes Merkmal wählen“) an jeder Absage eines Schritts mit Merkmalsfeld; die Objektwahl bleibt, wo ein Körper gemeint ist.
- Wirkung beim Kunden: Der angebotene Weg wählte andere Körper statt eines anderen Merkmals.
- Stand: behoben `0b7f08da6`, nach Review `36cdd9fe2`; `test_feature_refusal_ways.py` am Stand davor 12 rot, danach grün; der Text in fünf Katalogen neu übersetzt.

### FD-180 *Solidon kaufen* ist im Freischaltdialog grau ohne Grund

- Art: Fehler
- Schwere: mittel
- Funktion: `dialog:activation_dialog`
- Prüfpunkt: 7, E7
- Beleg: Neuer Punkt in `output/konsolidierung-2026-10-12/fix-rest-c-claude.md`: `dialogs.ActivationDialog._follow_field` sperrte `buy_button` mit `not damaged and not locked_locally and not busy`, die Kurzhilfe trug nur den Grund der beschädigten Installation; dazu standen *Schlüssel prüfen*, *Online aktivieren* und *Offline aktivieren …* stumm grau; `test_ui_licensing.py::test_an_activated_computer_can_still_buy_and_says_why_the_rest_is_closed` am Stand davor rot.
- Ursache: Der Knopf öffnet nur die Produktseite, wurde aber auf einem freigeschalteten Rechner gesperrt, ohne Grund in Kurzhilfe oder Beschreibung (Regel 18, E7).
- Vorschlag: *Solidon kaufen* bleibt bedienbar und ist nur bei beschädigter Installation gesperrt, mit Grund; die übrigen Knöpfe nennen ihren Grund, *Schlüssel prüfen* auch den Ausweg *Diesen Rechner deaktivieren*.
- Wirkung beim Kunden: Wer für ein zweites Gerät kaufen will, steht vor einem grauen Knopf ohne Erklärung.
- Stand: behoben `5807a99e0`, `650b01c24`; der Test am Stand davor rot, danach grün; Dialoggröße unverändert, Bilder hell und dunkel.

### FD-181 Der Erste eines Monats heißt auf Französisch „1 décembre“

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `startup.expired_demo`
- Prüfpunkt: 9
- Beleg: Neuer Punkt in `output/konsolidierung-2026-10-12/fix-rest-c-claude.md`: Startfall fr (Text der abgelaufenen Demo) „1 décembre 2026“; `tests/test_calendar_date_ordinal.py` am Stand davor 2 von 7 rot.
- Ursache: `labels.calendar_date` setzt das Langformat von `QLocale` „d MMMM yyyy“, und Qt kennt keine Ordinalform.
- Vorschlag: eine Regel je Sprache (`_FIRST_OF_MONTH = {"fr": "er"}`) an dieser einen Stelle; die anderen Sprachen prüfen.
- Wirkung beim Kunden: Französische Kunden lesen ein Datum, wie es auf Französisch nicht geschrieben wird.
- Stand: behoben `3277b97eb`; `test_calendar_date_ordinal.py` am Stand davor rot, danach „1er décembre 2026“; die anderen fünf Sprachen geprüft und unverändert.

### FD-182 Der Feldweg „Eine andere Ebene wählen“ steht als toter Knopf in *Objekt umbenennen*

- Art: Fehler
- Schwere: leicht
- Funktion: `rename_object`, `finding.action:sketch.pick_plane`
- Prüfpunkt: 7, 9
- Beleg: Neuer Punkt in `output/konsolidierung-2026-10-12/fix-f2a-claude.md` (Nachzug F2b): `test_short_dialog_ui` (6 Fälle, 18 pt): `refusal_details.field_ways` bot in *Objekt umbenennen* den Knopf „Eine andere Ebene wählen“ ohne Ebenenfeld an, bei 18 pt 602 px breit, mit Querleiste; `fix-rest-a-claude.md`: Die Ebenenabsage der Skizzenoperationen nannte das Feld `plane`, das keine Skizzenoperation hat; `test_refusal_field_ways_window.py`, `test_plane_refusal_field.py` und `test_short_dialog_ui.py` am Stand davor rot.
- Ursache: `field_ways` machte jede Absage mit `values["field"]` zum Sprungknopf, ohne zu fragen, ob der Dialog das Feld führt; `sketch.ops._frame_of` nannte das falsche Feld; Knöpfe unter einer Absage brachen nicht um.
- Vorschlag: Ein Feldweg ist ein Knopf nur, wo der Dialog das Feld führt (`focus_field(…, check_only=True)`), sonst ein Rat; die Skizzenoperationen nennen `sketch`; Knöpfe unter einer Absage brechen um.
- Wirkung beim Kunden: Ein Knopf in der Absage tat nichts, und bei großer Schrift rollte der Dialog quer.
- Stand: behoben `c070cb122`; die drei Tests am Stand davor rot, danach grün; Bild hell und dunkel; nativer Nachweis des Umbruchs mit Systemschrift im Schlusslauf (Plan, Nachtrag review2-ra).

### FD-183 Eine umgebrochene Beschriftung der Rückseite verliert Zeilen

- Art: Gestaltung
- Schwere: leicht
- Funktion: `drill_hole`, `dialog:operation_dialog`
- Prüfpunkt: 9
- Beleg: `output/konsolidierung-2026-10-12/fix-f2a-claude.md`, Sonde `probe_labels.py`: *Bohrung setzen*, „Durchmesser der Aufweitung“ Breite 69, Höhe 32, Bedarf 48; offscreen 11 Beschriftungen in 11 Dialogen bei Grundschrift, 197 bei 16 pt; Bilder `bilder-fix-f2a/fd183-aufweitung-*`; Review R3: nach 16 → 9 pt hielt dieselbe Beschriftung 84 statt 48 Punkte.
- Ursache: `dialogs.align_to_the_front` hält die Breite einer Rückseitenbeschriftung fest, die Zeilenhöhe nahm das Formular aber aus `QLabel.sizeHint` für eine breitere Zeile.
- Vorschlag: Die Untergrenze der Höhe ist die Höhe des Textes in der festen Breite, neu gezählt nach Schrift-, Stil- und Breitenwechsel (`wrapped_caption.keep_whole_lines`).
- Wirkung beim Kunden: Die dritte Zeile einer Feldbeschriftung fehlt, das Feld ist nicht mehr eindeutig benannt.
- Stand: behoben `15f5a1b4f`, `22f55de98`; `tests/test_wrapped_captions.py` am Stand davor rot (4 von 9, zur Rücknahme nach R3 2 von 10), danach zeigt jede umgebrochene Rückseitenbeschriftung jede Zeile, in beide Schriftrichtungen; Bild hell und dunkel.

### FD-184 Ganzzahlfelder außerhalb des Operationsdialogs schreiben keine Dreiergruppen

- Art: Zwillinge
- Schwere: leicht
- Funktion: `dialog:print_settings_dialog`, `dialog:settings_dialog`, `dialog:operation_dialog`
- Prüfpunkt: 9
- Beleg: `output/konsolidierung-2026-10-12/fix-f2a-claude.md`: 14 Ganzzahlfelder ohne Gruppen (Einrichtung, Pinsel, Teilen, Varianten, Skizzeneditor, Druckeinstellungen, Merkmalfenster, Filamentlager); Felder mit `setDecimals(0)` lasen „2.103.472“ als 2103,472; Review R2: 13 Druckfelder mit null Nachkommastellen, *Leerfahrt* las „1.000“ als 1 mm/s; R5: Kennungen (Startwert, Port) nur über eine Namensausnahme; `tests/test_grouped_count_fields.py` je am Stand davor rot.
- Ursache: Die Gruppenschreibweise aus FD-124 galt nur im Ganzzahlfeld des Operationsdialogs; Druckfelder mit null Stellen und Kennungen hatten keine Regel.
- Vorschlag: jedes Ganzzahlfeld über `grouped_spin`, Druckfelder ohne Nachkomma als `GroupedSpin`, Kennungen über `param(identifier=True)` ohne Gruppen; ein Wächter über `app/ui`.
- Wirkung beim Kunden: Große Zahlen standen ohne Gruppen da, und „1.000“ in *Leerfahrt* wurde als 1 mm/s gelesen.
- Stand: behoben `3e515ef4f`, `8af6a2d09`, `112fbf80a`; `tests/test_grouped_count_fields.py` am Stand davor rot, danach entsteht jedes Ganzzahlfeld über `grouped_spin` und liest „1.000“ in jeder Sprache als tausend; nativer Nachweis der Breite mit Systemschrift im Schlusslauf (Plan Punkt 14).

### FD-185 Die Handlungsknöpfe im Prüfbericht sind bei großer Schrift gestaucht

- Art: Gestaltung
- Schwere: mittel
- Funktion: `report.action`
- Prüfpunkt: 9, 10
- Beleg: Review 2 Restpaket B, N1 (`output/konsolidierung-2026-10-12/review2-rest-b-claude.md`): Fenster bei 18 pt, Befund *Kammer ändern*: Knopf *Anderes Merkmal wählen* 26 px hoch bei `minimumSizeHint` 38 px; *Eingabe korrigieren* und *Andere Kanten wählen* oben und unten beschnitten; `tests/test_report_offer_height_window.py` am Stand davor rot (1920 × 700, 26 statt 38 px) (`fix-rest-a-claude.md`).
- Ursache: Das Stylesheet gibt `QPushButton` `min-height`, Qt setzt daraus eine ausdrückliche Mindesthöhe von 26 px, und die schlägt im engen Layout die Höhe der Schrift.
- Vorschlag: Die Mindesthöhe jedes Knopfs folgt seiner Beschriftung nach Stil- und Schriftwechsel (`button_floor`, ein Zuhörer mit FD-194).
- Wirkung beim Kunden: Bei großer Schrift ist jede Handlung einer Befundzeile angeschnitten (Barrierefreiheit).
- Stand: behoben `2b0eea69f`, `a9a3233a7`; `test_report_offer_height_window.py` am Stand davor rot, danach grün; Bild 11 und 18 pt hell und dunkel; nativer Nachweis bei großer Windows-Textskalierung im Schlusslauf (Plan Punkt 40, Nachtrag review2-ra).

### FD-186 Die Absage zum Gegenstück zeigt eine Kennung und Längen ohne Einheit

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `meldung:action_counterpart`
- Prüfpunkt: 9, V1
- Beleg: Review 2 Restpaket B, N2 (`output/konsolidierung-2026-10-12/review2-rest-b-claude.md`): Absagedialog in sechs Sprachen „Merkmal: thread_1“, „Durchmesser: 37,0“, „Steigung: 0,9“ (`blatt-gewinde-dialog-*.png`); `test_stepless_advice.py` am Stand davor 3 rot (`fix-rest-b-claude.md`).
- Ursache: `counterpart.py:620/644` legten `feature` als Kennung und Längen ohne `_mm` ab; `spoken_values` zeigt beides roh.
- Vorschlag: `diameter_mm` und `pitch_mm` ablegen, `feature` weglassen; jede Merkmalskennung in Meldungen als „Art Nummer“ (`registry.feature_title_of` in `labels.value_text`).
- Wirkung beim Kunden: Eine interne Kennung statt eines Namens, und in Zoll eine Millimeterzahl ohne Einheit.
- Stand: behoben `a2a3cafe3`; `test_stepless_advice.py` am Stand davor rot, danach steht die Absage ohne Kennung, Längen in der Anzeigeeinheit; offscreen hell und dunkel bei 11 und 18 pt in sechs Sprachen gesehen.

### FD-187 Ein Auswahlfeld zeigt einen Wert, den seine Liste nicht führt, als Kennung

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `resize_chamber`, `pattern_feature`, `dialog:operation_dialog`
- Prüfpunkt: V1
- Beleg: Review 2 Restpaket B, N3 (`output/konsolidierung-2026-10-12/review2-rest-b-claude.md`): nach *Anderes Merkmal wählen* steht im Feld *Kammer* „face_1“, nach *Andere Flächen wählen* im Feld *Fläche* „fillet_1“; `op_dialog.py:4167` (`combo.addItem(str(start), str(start))`), gleich gebaut an `:1245` und `:4217`; `tests/test_unlisted_choices.py` am Stand davor rot (`fix-f2a-claude.md`).
- Ursache: Sechs Stellen zeigten einen Wert außerhalb ihrer Liste roh: Merkmalsfeld, Merkmalsliste, Kantenliste, Bild- und Quellenwähler, Objekt- und Quellenauswahl.
- Vorschlag: eine Quelle `app/ui/unlisted_choice.py`: Art und Nummer mit „passt hier nicht“, der Wert bleibt.
- Wirkung beim Kunden: Der neue Weg führt genau auf dieses Feld, und dort steht der abgelehnte Wert als interne Kennung.
- Stand: behoben `82b2b110c`; `tests/test_unlisted_choices.py` am Stand davor rot („face_1“, „fillet_1“, Dateikennungen), danach „Fläche 1 · passt hier nicht“; Bild hell und dunkel.

### FD-188 Längen in Absagewerten stehen ohne Einheit

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `draft_faces`, `fillet_edges`, `pin_for_bore`, `create_profile_clamp_set`, `part:*`
- Prüfpunkt: 9, V5
- Beleg: Neuer Punkt in `output/konsolidierung-2026-10-12/fix-rest-b-claude.md`: gut zwanzig Absagen legen Längen unter Schlüsseln ohne `_mm` ab, die Anzeige zeigt sie ohne Einheit und in Zoll falsch (`brep/profiles.py:1407, 1474`, `geom/edges.py:1734`, `geom/lid_hinge.py:186, 204, 824, 974`, `geom/prepare_ops.py:12197, 17054, 17761, 19027`, `geom/profile_clamp_ops.py:419`, `knowledge/parts/fasteners.py:1872, 1883, 1906`, `parts/holders.py:804`, `parts/mounting.py:1086`, `parts/structure.py:716`); dazu „Erreichbar: 0,58“ im Rat des Operationsdialogs (`mesh_ops._too_fine`); andere legen fertigen Text mit fester Einheit ab (`format_length` in `geom/prepare.py`).
- Ursache: Die Absagen legen Längen unter Schlüsseln ohne `_mm` ab, `spoken_values` erkennt sie nicht als Länge; Leser im Code brauchen die Schlüssel (`main_window.py` liest `previous`/`diameter`, `bore_pin.py` `diameter`/`pitch`), deshalb blieben sie in FD-186 unverändert.
- Vorschlag: je Stelle `_mm`-Schlüssel und die Leser nachziehen; ein Wächter über `spoken_values` aller Absagen mit Zahl.
- Wirkung beim Kunden: In Zoll liest er eine Millimeterzahl ohne Einheit und hält sie für Zoll.
- Stand: offen RM-737; in Arbeit

### FD-189 *Einzelne Kanten* zeigt einen gespeicherten Kantenschlüssel roh

- Art: Zwillinge
- Schwere: leicht
- Funktion: `fillet_edges`, `chamfer_edges`
- Prüfpunkt: V1
- Beleg: Neuer Punkt in `output/konsolidierung-2026-10-12/fix-rest-b-claude.md`: Über *Andere Kanten wählen* an *Verrunden* mit `edges="named"` steht in der Liste die gewählte Kante als „e:-20.00,-15.00,10.00:0.000,0.000,1.000“ (`weg-benannt-CHANGE_EDGES.png`); `test_unlisted_choices.py` am Stand davor rot (`fix-f2a-claude.md`). Zwilling von FD-187.
- Ursache: `EdgeSetField` zeigt einen Schlüssel ohne Eintrag in `choices` wörtlich; `MainWindow._edge_names` liefert an einem Netz nur die markierten Kanten, die gespeicherte Wahl eines Schritts bekam keine Beschriftung.
- Vorschlag: gespeicherte Kanten aus Lage und Ort ihres Schlüssels beschriften, aus derselben Quelle wie die markierten.
- Wirkung beim Kunden: Statt einer Kante liest er eine Zahlenkette.
- Stand: behoben `82b2b110c`; `test_unlisted_choices.py` am Stand davor rot, danach heißt eine gespeicherte Kante nach Lage und Ort („Senkrecht · x -20,00, y -15,00“) wie eine markierte; Bild hell und dunkel.

### FD-190 Nach *Eine andere Ebene wählen* aus dem Bericht steht die Tastatur nicht in der Ebenenwahl

- Art: Einfachheit
- Schwere: leicht
- Funktion: `finding.action:sketch.pick_plane`
- Prüfpunkt: 10
- Beleg: Neuer Punkt in `output/konsolidierung-2026-10-12/fix-rest-a-claude.md` (Merge B und D): Nach *Eine andere Ebene wählen* aus dem Prüfbericht öffnet der Skizzenmodus mit der unlesbaren Ebene, die Tastatur steht aber auf dem Kartengriff (`CardGrip`) statt in der Ebenenwahl; `tests/test_sketch_way_focus_window.py` am Stand davor 2 von 2 rot (Fokus in der Befundliste).
- Ursache: `MainWindow.start_sketch` setzte keinen Fokus; der gedrückte Berichtsknopf verschwand, und der Bericht parkte den Fokus in seiner Liste (FD-4).
- Vorschlag: ohne auflösbare Ebene Fokus in *Zeichenebene*, sonst in die Ansicht (`app/ui/sketch_focus.py`, eine Zeile in `start_sketch`).
- Wirkung beim Kunden: Wer nach dem Weg tippt, bedient nicht die Ebenenwahl, die die Handlung nennt.
- Stand: behoben `3185c1a3a`; `tests/test_sketch_way_focus_window.py` am Stand davor rot, danach setzt *Eine andere Ebene wählen* die Tastatur in *Zeichenebene* und *Eingabe korrigieren* an einer kaputten Zeichnung in die Ansicht.

### FD-191 Offen gelassene Fenster machten einen späteren Testfall rot

- Art: Fehler
- Schwere: leicht
- Funktion: keine Zeile: Fenstertests der Suite
- Prüfpunkt: 19
- Beleg: Neuer Punkt in `output/konsolidierung-2026-10-12/fix-f2a-claude.md` (Testisolation): `test_function_feature_measurement` fiel im Umfeldlauf mit „Mehrere offene Bedienflächen ohne eindeutiges aktives Fenster“; `fix-rest-a-claude.md`: drei Fälle in `test_operation_ui.py` zeigten einen Operationsdialog und schlossen ihn nie, das Paar mit `test_function_feature_measurement.py` vorher 3 failed, danach 342 passed; der neue Wächter fand 24 Verursacher.
- Ursache: Fälle ließen sichtbare Fenster zurück, und `surface_for` liest die offenen Fenster der Anwendung.
- Vorschlag: ein Wächter `_no_window_outlives_its_test` in `tests/conftest.py`; die Verursacher schließen.
- Wirkung beim Kunden: Kein Produktfehler; ein späterer Fall wurde je nach Reihenfolge rot.
- Stand: behoben `6b11dcabb`; der Wächter macht jeden Fall rot, der ein sichtbares Fenster zurücklässt (der gepflanzte Fall am Stand davor grün, danach rot), alle 24 Verursacher sind geschlossen.

### FD-192 Eine angezeigte Textur rechnet eine Vorschau ohne Änderung

- Art: Leistung
- Schwere: leicht
- Funktion: `feature:texture.change`
- Prüfpunkt: 6
- Beleg: Neuer Punkt 1 in `output/konsolidierung-2026-10-12/fix-ci-main-claude.md`: `show_texture` (`app/ui/panels.py:10127`) meldet die unveränderten Werte des Schritts als Änderung, `_on_feature_values_changed` stellt die 300-ms-Uhr, danach rechnet eine Vorschau ohne Änderung und *Abbrechen* steht da (Spur `texslow.txt`); `test_waiting_click_rebuild.py` am Stand davor 3 rot.
- Ursache: Der Neuaufbau des Merkmalfensters meldete Werte wie eine Eingabe des Kunden; gleiche Wurzel wie der verfallende wartende Klick (Review CI, RCI-2).
- Vorschlag: `show_texture` meldet nichts; ein Neuaufbau ohne Eingabe hält die Freigabe mit wartendem Klick (`app/ui/waiting_click.py`).
- Wirkung beim Kunden: Nach dem Anwählen einer Textur rechnet Solidon ohne Grund und zeigt *Abbrechen*.
- Stand: behoben `6369e3b81`; `test_waiting_click_rebuild.py` am Stand davor rot, danach grün.

### FD-193 Die Ansicht hält einen abgelösten Renderer bis zum Fensterende

- Art: Leistung
- Schwere: leicht
- Funktion: `viewport`
- Prüfpunkt: 6
- Beleg: Neuer Punkt 2 in `output/konsolidierung-2026-10-12/fix-ci-main-claude.md`: `_Same(self.renderer)` in den Vergleichsschlüsseln der Ansicht (`viewport.py:12281`, `:12592`) hält den alten Renderer nach `release_renderer`, etwa nach einem Sprachwechsel (wgpu.log der Probe 38855455034); `test_viewport_release.py` am Stand davor rot (Halter tuple, Gizmo, SlotHandle, `_Same`).
- Ursache: Griffe und Vergleichsschlüssel hielten den Renderer stark.
- Vorschlag: `release_renderer` lässt Griffe und die Schlüssel mit `_Same(self.renderer)` und `_bed_built` fallen.
- Wirkung beim Kunden: Nach einem Sprachwechsel bleibt der Speicher des alten Renderers bis zum Schließen belegt.
- Stand: behoben `abcf79ee8`; `test_viewport_release.py` am Stand davor rot, danach grün; belegt mit einem Aufzeichnungsrenderer, am echten `GfxRenderer` nicht nachgestellt.

### FD-194 Solidon übernahm eine geänderte Systemschrift erst nach einem Neustart

- Art: Fehler
- Schwere: mittel
- Funktion: `dialog:main_window`, `dialog:operation_dialog`
- Prüfpunkt: 9, Z6
- Beleg: Frage aus Review 2 Restpaket C (RC2-4), am Code und offscreen belegt (`output/konsolidierung-2026-10-12/KOORDINATION.md`, 16.10.): kein Zuhörer auf `ApplicationFontChange`, `apply_style` nur beim Themenwechsel, Sonde 9 → 14 pt: das Stylesheet bleibt; `tests/test_font_follow_window.py` am Stand davor rot (Titel und Abschnitt 16/10 statt 24/16, Knöpfe und offener Dialog bei 9 pt) (`fix-rest-a-claude.md`).
- Ursache: Das Stylesheet trägt die Größen der Stufen fest und wurde nur beim Themenwechsel gesetzt.
- Vorschlag: ein Zuhörer auf `ApplicationFontChange` setzt den Stil neu, nur über Solidons eigenem Stylesheet (`app/ui/style_follow.py`).
- Wirkung beim Kunden: Wer die Windows-Textgröße ändert, sieht Solidon erst nach einem Neustart in der neuen Größe; offene Dialoge blieben klein.
- Stand: behoben `a9a3233a7`; `test_font_follow_window.py` am Stand davor rot, danach folgen Stufen, Knöpfe und offene Dialoge in beide Richtungen; Bild 9 → 14 → 9 pt hell und dunkel; nativer Nachweis mit der Windows-Textgröße im Schlusslauf (Plan, Nachtrag review2-ra).

### FD-195 Ein offener Dialog gab nach kleinerer Schrift seine Höhe nicht zurück

- Art: Gestaltung
- Schwere: leicht
- Funktion: `dialog:operation_dialog`
- Prüfpunkt: 9, Z6
- Beleg: Neuer Punkt in `output/konsolidierung-2026-10-12/fix-rest-a-claude.md` (FD-194): Zurück auf 9 pt behielt der offene Dialog *Quader anlegen* seine 347 px, unten blieb ein leerer Streifen (`fd194-nachher-dialog-c9-*`); `test_font_height_window.py` am Stand davor rot (296 statt 258).
- Ursache: `style.ContentHeight` lässt passive Änderungen nie verkleinern (RM-487), und ein Schriftwechsel zählte als passiv.
- Vorschlag: Ein Schriftwechsel misst offene Dialoge wie ein Aufklappen (Absicht `font`); eine Größe des Kunden bleibt.
- Wirkung beim Kunden: Nach kleinerer Schrift blieb in offenen Dialogen Leerraum über den Knöpfen.
- Stand: behoben `3b0c1a8f7`; `test_font_height_window.py` am Stand davor rot, danach grün.

### FD-196 Die Sammelzeile verlorener Formdetails liest ein Bildschirmleser 118-mal

- Art: Fehler
- Schwere: leicht
- Funktion: `report`
- Prüfpunkt: 10
- Beleg: Nachprüfung Restpaket A (`output/konsolidierung-2026-10-12/review2-rest-a-claude.md`): `app/ui/panels.py:7773–7792`, Sammelzeile mit 118 Waisen: Kurzhilfe und zugängliche Beschreibung je 20 179 Zeichen, jedes Mitglied wiederholt den ganzen Satz, dazu rohe Kennungen (L2, Sonde `test_zz_sonde_kennung_kurzhilfe.py`); seit v0.6.0.
- Ursache: Die Sammelzeile setzte für jedes Mitglied den ganzen Satz und die Kennung statt des Namens.
- Vorschlag: Mitglieder nur mit Merkmal und Körper, höchstens fünfzehn wie in der Zeile, danach „… (+N)“.
- Wirkung beim Kunden: Ein Bildschirmleser liest denselben Satz 118-mal.
- Stand: behoben `a04ba84fe`, `98a971a7a`; die Mutationen N05 (Kennung statt Name) und N06 (alle statt fünfzehn) sind rot, danach nennen Sammelzeilen Art, Nummer und Körper, höchstens fünfzehn Mitglieder.

### FD-197 *Fluss bei Brücken* zeigt 2 % und schreibt 1–2 % an den Slicer

- Art: Fehler
- Schwere: schwer
- Funktion: `dialog:print_settings_dialog`
- Prüfpunkt: 4, 9
- Beleg: Review 2 F2a und D, N1 (`output/konsolidierung-2026-10-12/review2-f2a-d-claude.md`): `print_fields.py:327–341` `shell.bridge_flow` mit `minimum=0.5, maximum=1.5, factor=100.0, decimals=0`; am echten Druckdialog „2 %“, „90“ → „90 % liegt über der Obergrenze 2 %.“, „1“ und Pfeil hoch → Modell 0,01 als eigene Wahl; am Tag `v0.6.0` ebenso (eingeführt mit `badc464f9`); `test_print_field_units.py` und `test_bridge_flow_dialog.py` am Stand davor 12 von 73 rot (`fix-fd197-claude.md`).
- Ursache: Das Feld zeigt Prozent (`factor=100`), seine Grenzen und sein Schritt standen als Anteil; Qt rundete sie bei null Stellen auf 1–2 %.
- Vorschlag: Grenzen und Schritt in Anzeigeeinheit, ein Wächter über alle Druckfelder; ein Formatschritt, der eine gespeicherte 0,01/0,02 aus 0.6.0 zurücknimmt und es sagt.
- Wirkung beim Kunden: Jeder Kunde sah einen falschen Wert; wer ihn änderte, schickte 1–2 % Brückenfluss an den Slicer — Brücken drucken ohne Material.
- Stand: behoben `5212ca45f`, `b736da48f`, `8b7a1b3aa`; Grenzen 50–200 %, Schritt 5, 90 % kommt als 0,9 in der Datei für Orca und Prusa und im G-Code von OrcaSlicer an; der Formatschritt 52 → 53 nimmt 1–2 % aus 0.6.0 zurück und sagt es im Prüfbericht (`project.bridge_flow_reset`); neue Tests am Stand davor 54 von 306 rot, danach grün; Beispielprojekte auf Format 53 (`1f8346073`).

### FD-198 *Parameter anlegen* behält nach dem Aufklappen Leerraum

- Art: Gestaltung
- Schwere: leicht
- Funktion: `Bearbeiten/Parameter anlegen …`, `dialog:parameter_dialog`, `dialog:settings_dialog`, `dialog:first_run_dialog`, `dialog:activation_dialog`
- Prüfpunkt: 9, Z6
- Beleg: Review 2 F2a und D, N2 (`output/konsolidierung-2026-10-12/review2-f2a-d-claude.md`): *Parameter anlegen* bei 9 pt nach dem Aufklappen 330 hoch, 16 leer, ohne senkrechten Balken 314, 0 leer (`sonde_andere.py`); die Zwillinge *Baustein speichern*, *Erste Schritte*, *Chat einrichten* und *Solidon freischalten* zugeklappt bis 326 Punkte leer, die *Einstellungen* bis 382 (Review 2 Restpaket A, P1); `test_content_height_dialogs.py` am Stand davor 22 rot (`fix-rest-a-claude.md`).
- Ursache: Die Klappe war nicht an die ausdrückliche Messung angeschlossen; die passive Messung lief mit vorläufigem Balken und gab zugeklappt nichts zurück.
- Vorschlag: `ContentHeight.fit` misst für Öffnen, Klappen und Schriftwechsel ohne vorläufigen Balken und ein zweites Mal nach den Layout-Anfragen; jede Klappe misst `explicit`.
- Wirkung beim Kunden: Über den Knöpfen blieben bis zu mehrere hundert Punkte leer.
- Stand: behoben `23c94be83`, `546b0e891`; `test_content_height_dialogs.py` am Stand davor 22 rot, danach 28 grün, mit den Einstellungen und dem Schriftwechsel 40 grün.

### FD-199 *Material kalibrieren* rollt bei großer Schrift quer

- Art: Gestaltung
- Schwere: leicht
- Funktion: `Bearbeiten/Material kalibrieren …`, `dialog:calibration_dialog`
- Prüfpunkt: 9, Z6
- Beleg: Review 2 F2a und D, N2 (`output/konsolidierung-2026-10-12/review2-f2a-d-claude.md`): *Material kalibrieren* rollt bei 16 pt 18 Punkte, obwohl unten Platz ist, auch ohne Balken; *Baustein speichern* rollte beim Öffnen 57 bis 214 Punkte quer (`fix-rest-a-claude.md`); die Fälle `kalibrieren-14/16` und `baustein-9/11/14` in `test_content_height_dialogs.py` am Stand davor rot.
- Ursache: Bei 14 und 16 pt deckelt der Bildschirm die Höhe nach dem Aufklappen, der bleibende Balken nimmt 12 Punkte Breite, und der Dialog maß seine Breite nie.
- Vorschlag: `fit` verbreitert nach dem Legen um die fehlende Mindestbreite samt bleibendem Balken, bis zum Bildschirmrand.
- Wirkung beim Kunden: Der Dialog rollt quer, obwohl daneben über 300 Punkte frei sind.
- Stand: behoben `23c94be83`; die Fälle am Stand davor rot, danach grün.

### FD-200 *Bohrung setzen* rollt bei großer Schrift quer, und der Test sah weg

- Art: Gestaltung
- Schwere: leicht
- Funktion: `drill_hole`
- Prüfpunkt: 9, Z6
- Beleg: Review 2 F2a und D, N3 (`output/konsolidierung-2026-10-12/review2-f2a-d-claude.md`): bei de 16 pt, 18 pt und auf 1366 × 728 nach dem Aufklappen *Bohrung setzen* (`drill_hole`, `drill_brep_hole`) mit Querleiste, Dialog 490 breit, Ausschnitt 446, Inhalt mindestens 454 (`sonde_querleiste.py`, `n3-bohrung-16pt-aufgeklappt-*.png`); der R1-Test übersprang jeden Dialog mit Querleiste mit falscher Begründung; `test_operation_dialog_flap_height.py` mit gebündelter Schrift, `de-16` am Stand davor rot (`fix-rest-a-claude.md`).
- Ursache: Die Anfangsbreite kam nicht aus der Mindestbreite der aufgeklappten Rückseite samt Balken.
- Vorschlag: derselbe Breitenschritt wie FD-199; der Test zählt Querleisten, außer der Schirm deckelt die Breite, und misst mit der gebündelten Schrift.
- Wirkung beim Kunden: Bei großer Schrift ist die Auswahl *Achse* rechts abgeschnitten.
- Stand: behoben `23c94be83`; `de-16` am Stand davor rot, danach alle acht Fälle grün (sechs Sprachen bei 9 pt, de bei 16 und 18 pt).

### FD-201 Zugriffsverletzung beim Bau des `QCompleter` im Operationsdialog

- Art: Stabilität
- Schwere: mittel
- Funktion: keine Zeile: Fensterlauf `tests/test_operation_ui.py`
- Prüfpunkt: 19
- Beleg: `output/konsolidierung-2026-10-12/fix-rest-a-claude.md`: dreimal dieselbe Zugriffsverletzung in `ExpressionField.__init__` beim Bau des `QCompleter` (`op_dialog.py:494` bzw. `:503` ← `_editor_for` ← `OperationDialog.__init__`) im Fall `test_every_operation_dialog_names_its_fields_and_keeps_the_grid`; die ganze Datei zehnmal gepinnt: 9 grün, 1 Abriss, mit abgeschaltetem Speicherbereiniger derselbe Ort; `fix-fd201-202-claude.md`: nativer Stapel unter `cdb.exe` — `PySide::SignalManager::retrieveMetaObject` mit Typdaten `nullptr` aus `QCompleterWrapper::metaObject()`. Zwilling von RM-790 (Abbruch am `QCompleter` in `ValueField.__init__`).
- Ursache: offen; am Stapel liefert der `BindingManager` während des Konstruktors die Hülle eines längst freigegebenen C++-Objekts an derselben Adresse, vermutlich eines Typs ohne `QObject`, den C++ löscht, während Python die Hülle noch hält.
- Vorschlag: den Typnamen der fremden Hülle im Abriss lesen und je Fall zählen, welche Hüllen ohne `QObject` über die Datei wachsen (`shiboken6.Shiboken.getAllValidWrappers()`); den Verursacher abbauen.
- Wirkung beim Kunden: keine belegte; im Kundenweg nicht beobachtet, in der Suite etwa jeder zehnte ganze Lauf der Datei.
- Stand: offen RM-737; in Arbeit

### FD-202 Der Maßkartenfall las gleitende Seitenkarten als Dauerschleife

- Art: Fehler
- Schwere: leicht
- Funktion: keine Zeile: Fenstertest `tests/test_measure_group_layout.py`
- Prüfpunkt: 19
- Beleg: `output/konsolidierung-2026-10-12/fix-rest-a-claude.md`: `test_measure_group_layout.py::test_fold_changes_card_height_and_settles` wechselnd rot (34 statt 30 Zeichnungen, je eine andere Sprache); `fix-fd201-202-claude.md`: mit 1 s Gleiten (`-p slowcards`) auf main, welle5 und Restpaket A rot, auch am Entstehungscommit `f6b0f53f2`.
- Ursache: Die Seitenkarten gleiten nach der Wahl einer Bohrung 160 ms nach der Wanduhr, `settle_measure_layout` zählte nur 20 Ereignisrunden, und jeder Schritt der Karten setzt die Maßkarte neu. Kein Produktfehler.
- Vorschlag: Das Einschwingen wartet wie in FD-157 auf ruhende Karten (`wait_for_resting_cards`, eine Quelle für `ui_helpers` und `guide_window`).
- Wirkung beim Kunden: Kein Produktfehler; die Maßkarte folgt den gleitenden Karten Bild für Bild und steht danach.
- Stand: offen RM-737; in Arbeit

### FD-203 Herstellerwerte außerhalb der Feldgrenzen stehen im Druckdialog gekürzt

- Art: Fehler
- Schwere: mittel
- Funktion: `dialog:print_settings_dialog`, `dialog:first_run_dialog`
- Prüfpunkt: 4, 9
- Beleg: Neuer Punkt in `output/konsolidierung-2026-10-12/review-fd197-claude.md`: `scan_vendor.py` über 9 169 Prozessdateien von fünf Slicern: `speed.acceleration` in 15 Dateien 32 000–100 000 (Feld bis 30 000), `speed.travel` in 13 (1 200–1 500, Feld bis 1 000), Schichthöhen und Bahnbreiten bis 4 und 9,5 mm, `shell.bottom_layers` 999; über `base_settings` bestätigt: Sovol Zero 40 000 → „30000 mm/s²“; `test_vendor_field_values.py` am Stand davor 45 rot (`fix-fd197-claude.md`).
- Ursache: Das Feld setzte seine Grenzen und klemmte jeden geladenen Wert darauf; Prüfbericht und Kommandozeile nannten den echten Wert, und der Slicer druckte ihn.
- Vorschlag: Kein Feld kürzt einen geladenen Wert still (`print_fields.shown_range`), die Grenzen decken jeden Herstellerwert, der ein Maß ist, ein Wächter gegen eine eingecheckte Liste der Herstellerwerte.
- Wirkung beim Kunden: Der Dialog zeigte einen anderen Wert als den, der gedruckt wird.
- Stand: behoben `b736da48f`, `8b7a1b3aa`; `test_vendor_field_values.py` am Stand davor rot, danach steht jedes Herstellerextrem aus 46 225 Profilen ungekürzt im Feld, sechs Merkzeichen sind benannt; die Düse geht bis 10 mm in Druckdialog und Ersteinrichtung.

## Funde nach dem Einfrieren (ab FD-204, nach 0.6.1, RM-812)

Robert, 16.10.2026, 15:50: Fertig gemacht wird, was bis FD-203 beauftragt ist;
neue Funde werden eingetragen und nach dem Release von 0.6.1 abgearbeitet
(`output/konsolidierung-2026-10-12/AUFTRAG-1016-claude.md`, „Umfang
eingefroren“). Ihr Registerpunkt ist RM-812.

### FD-204 Cura-Profile fehlen im Herstellerscan der Druckfeldgrenzen

- Art: Fehler
- Schwere: leicht
- Funktion: keine Zeile: Werkzeug `tools/scan_vendor_values.py`
- Prüfpunkt: 19
- Beleg: Neuer Punkt in `output/konsolidierung-2026-10-12/fix-fd197-claude.md`: Der Erzeuger liest die Orca-Familie und die PrusaSlicer-Bündel, nicht Curas Druckerdefinitionen und Qualitätsprofile (`share\cura\resources`); bestätigt in `review2-fd197-claude.md`.
- Ursache: `scan_vendor_values.py` hat keinen Leser für Cura.
- Vorschlag: einen Cura-Leser (`manufacturer`, Cura-Grundlage) in `scan_vendor_values.py` aufnehmen und `tests/data/vendor_print_values.json` neu schreiben.
- Wirkung beim Kunden: keine belegte; gekürzt wird ein Cura-Wert seit FD-203 nicht mehr (`shown_range`), nur benannt ist er nicht.
- Stand: offen RM-812

### FD-205 Ein geladenes Merkzeichen weitet die Eingabespanne des Felds

- Art: Fehler
- Schwere: leicht
- Funktion: `dialog:print_settings_dialog`
- Prüfpunkt: 7
- Beleg: Neuer Punkt in `output/konsolidierung-2026-10-12/fix-fd197-claude.md`: Nach dem Laden von 999 Bodenschichten (HueForge @LH Stinger) nimmt das Feld jede Eingabe bis 999 an, nicht nur bis 50.
- Ursache: `print_fields.shown_range` weitet die Spanne bis zum geladenen Wert, und dieselbe Spanne gilt für getippte Werte.
- Vorschlag: eine getrennte Annahmegrenze in `_BoundedBehavior`, die nur den geladenen Wert selbst zusätzlich zulässt.
- Wirkung beim Kunden: Ein Tippfehler bis zum Merkzeichen geht ohne Ablehnung durch.
- Stand: offen RM-812

### FD-206 Ein Hinweis beim Öffnen geht verloren, wenn die erste Auswertung abbricht

- Art: Fehler
- Schwere: leicht
- Funktion: `report`
- Prüfpunkt: 7
- Beleg: `output/konsolidierung-2026-10-12/review2-fd197-claude.md`, NP-1: `session.py:440–445` löscht `pending_foreign_check` vor `_evaluate`; `except OperationCancelled` und `except AppError` (`:496–499`) stellen ihn nicht wieder her, und `evaluate_async` bricht einen laufenden Arbeiter bei jeder neuen Anfrage ab; `probe_cancel.py`: erster Lauf abgebrochen, zweiter fertig ohne `project.bridge_flow_reset`. Derselbe Weg trägt die Hinweise zu §32 (`foreign.findings_for`) und §24.4 (`part_check`).
- Ursache: Der Merker wird gelöscht, bevor die erste Auswertung fertig ist.
- Vorschlag: den Merker erst nach `finishedWith` löschen oder bei Abbruch und Fehler zurücksetzen; Test mit abgebrochenem erstem Lauf.
- Wirkung beim Kunden: Wer gleich nach dem Öffnen etwas ändert, erfährt nicht, dass Solidon den Brückenfluss aus 0.6.0 zurückgenommen hat, dass Inhalt fremder Herkunft ist oder ein Baustein sich geändert hat.
- Stand: offen RM-812

### FD-207 Die Kommandozeile zeigt die Hinweise eines geöffneten Projekts nicht

- Art: Zwillinge
- Schwere: leicht
- Funktion: keine Zeile: Kommandozeile (`app/cli/main.py`)
- Prüfpunkt: 7
- Beleg: `output/konsolidierung-2026-10-12/review2-fd197-claude.md`, NP-2: `cli/main.py:171` (`open_project`) lädt und liest `project.notices` nicht, ebenso keine Hinweise zu §32; ein `export` eines 0.6.0-Projekts mit 1 % Brückenfluss übergibt still den Wert der Grundlage.
- Ursache: Der Weg der Hinweise endet in der Sitzung des Fensters; die Kommandozeile hat keinen.
- Vorschlag: `open_project` gibt `project.notices` über `print_findings` aus.
- Wirkung beim Kunden: Ein Export über die Kommandozeile nimmt still einen anderen Wert, als das Projekt trug.
- Stand: offen RM-812

### FD-208 Der Rückzug wird nicht gegen den Extruder geprüft

- Art: Fehler
- Schwere: leicht
- Funktion: `dialog:print_settings_dialog`
- Prüfpunkt: 7
- Beleg: `output/konsolidierung-2026-10-12/review2-fd197-claude.md`, NP-3: Ein Rückzug von 15 mm (für 1,5) lehnte die alte Grenze 10 ab, seit den gehobenen Grenzen aus FD-203 wird er angenommen; `advise.py` kennt keinen Rat zum Rückzug. Den Teil zur Bahnbreite behob `8b7a1b3aa` (`advise.WIDE_LINE_SHARE`).
- Ursache: Es gibt keine Prüfung des Rückzugs gegen die Art des Extruders.
- Vorschlag: einen Rat zum Rückzug gegen die Extruderart (Direktantrieb, Bowden) in `advise.py`, wie `WIDE_LINE_SHARE` an der Bahnbreite.
- Wirkung beim Kunden: Ein Tippfehler 15 statt 1,5 mm geht ohne Rat an den Slicer.
- Stand: offen RM-812

### FD-209 Die Kurzhilfe der Waisen-Sammelzeile nennt die Mitglieder zweimal

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `report`
- Prüfpunkt: 10
- Beleg: `output/konsolidierung-2026-10-12/review2-rest-a-claude.md`, P2: Die Kurzhilfe trägt den Wert „Merkmal: …“ (die fünfzehn Namen aus `names`) und danach dieselben fünfzehn noch einmal (`panels.py:7773–7793`), mit demselben Trenner „ · “ wie zwischen Merkmal und Körper: „Fläche 3 · Griff · Bohrung 2 · Deckel“ (Sonde `test_zz_sonde_kennung_kurzhilfe.py`).
- Ursache: Wertezeile und Mitgliederliste werden beide gesetzt, mit gleichem Trenner.
- Vorschlag: bei einem Schritt nur die Wertezeile, sonst die Mitglieder mit „; “ trennen.
- Wirkung beim Kunden: Ein Bildschirmleser liest die Liste doppelt, und Merkmal und Körper sind nicht zu trennen.
- Stand: offen RM-812

### FD-210 *Filament anlegen* öffnet bei 16 pt mit Leerraum über den Knöpfen

- Art: Gestaltung
- Schwere: leicht
- Funktion: `dialog:new_filament_dialog`
- Prüfpunkt: 9, Z6
- Beleg: `output/konsolidierung-2026-10-12/review2-rest-a-claude.md`, P5: 1920 × 1080, 16 pt, 25 Punkte leer über den Knöpfen, vor und nach dem Diff von Restpaket A gleich.
- Ursache: offen; der Dialog steht nicht in `test_content_height_dialogs.py`.
- Vorschlag: die Ursache wie bei FD-198 an `ContentHeight` prüfen und den Dialog in `test_content_height_dialogs.py` aufnehmen.
- Wirkung beim Kunden: Bei großer Schrift steht der Dialog mit einer Leerzeile über den Knöpfen da.
- Stand: offen RM-812

### FD-211 Das Schlüsselfeld in *Solidon freischalten* folgt keiner kleineren Schrift

- Art: Gestaltung
- Schwere: leicht
- Funktion: `dialog:activation_dialog`
- Prüfpunkt: 9, Z6
- Beleg: `output/konsolidierung-2026-10-12/review2-rest-a-claude.md`, P4, und `fix-rest-a-claude.md` (P4-Rest): Das Schlüsselfeld setzt seine Höhe nur bei Text und Anzeigen (`_fit_key_field`), nicht nach einem Schriftwechsel, und bleibt nach 14 → 9 pt 27 Punkte höher als nötig.
- Ursache: `_fit_key_field` läuft nicht nach einem Schriftwechsel.
- Vorschlag: Das Feld misst nach einem Schriftwechsel neu, wie `WrappedNote` seit `546b0e891`.
- Wirkung beim Kunden: Nach kleinerer Schrift bleibt das Schlüsselfeld zu hoch.
- Stand: offen RM-812

## Regressionen aus Fixen nach dem Einfrieren (ab FD-212)

Was ein Fix des eingefrorenen Umfangs kaputt macht, ist kein neuer Fund für
nach 0.6.1, sondern Teil dieses Fixes und wird vor 0.6.1 behoben
(`output/konsolidierung-2026-10-12/AUFTRAG-1016-claude.md`, „Umfang
eingefroren“).

### FD-212 Nach dem Formatschritt 52 → 53 bietet ein geänderter eigener Baustein seinen gespeicherten Stand nicht mehr an

- Art: Fehler
- Schwere: mittel
- Funktion: `finding.action:keep_saved_parts`
- Prüfpunkt: 7, V5
- Beleg: `tests/test_function_list.py::test_a_light_mesh_scene_keeps_its_promises[baustein_geaendert.netz]` und `::test_a_scene_leaves_nothing_behind` mit „Handlung keep_saved_parts fehlt an parts.own_changed, angeboten []“, gepinnt rot (EXIT=1) an welle5 `1f8346073`, `3f84a4c3c`, `780ea7dd7` und auf dem FD-197-Zweig an `b736da48f` und `5212ca45f`, grün (EXIT=0) an `364367294` (Elter von `5212ca45f`), `b8f8296a1` und `068ebf2b7` (`output/konsolidierung-2026-10-12/funde-w5-claude.md`). Regression aus FD-197 (Formatschritt 52 → 53).
- Ursache: Der Abdruck eines eigenen Rezept-Bausteins (`recipe.fingerprint`, zugleich `PartSpec.version`) hashte die Formatversion des Rezeptdokuments mit; beim Lesen wird das Rezept migriert, also passte nach jeder Formaterhöhung kein gespeicherter Abdruck mehr (Sonde an `own_part_v52.p3d`: gespeichert `1ac66d32c23d`, heute `fdf886e56582`, mit Format 52 nachgerechnet wieder `1ac66d32c23d`). In 0.6.0 traf es ebenso Projekte aus 0.5.3 (Format 46).
- Vorschlag: den Abdruck unabhängig von der Formatversion des Dokuments rechnen oder das mitgereiste Rezept in der Version vergleichen, in der es gespeichert wurde; Test mit einem Projekt der Vorversion und geändertem eigenem Baustein.
- Wirkung beim Kunden: Für jedes Projekt aus 0.6.0 mit geändertem eigenem Baustein sagt der Prüfbericht „ihr alter Stand liegt nicht mehr vor“, obwohl er mitgereist ist, und *Gespeicherten Stand verwenden* fehlt.
- Stand: behoben `f470cd0e5`: Der Abdruck eines eigenen Bausteins rechnet ohne Formatversion (`recipe.fingerprint`, gespeichert mit `c:`); ein Abdruck aus einer älteren Datei bekommt beim Öffnen deren Formatversion und wird mit ihr nachgerechnet (`check.mark_stamp_formats`, `check.stamp_means`); `tests/test_part_stamps.py` mit dem Prüfstandsfall am Stand davor 7 von 7 rot, nachher 8 von 8 grün, Gegenprobe einer späteren Formatversion dabei; Zwilling Buchungsabdruck mitbehoben, sein einmaliger Bruch steht im Archiv; Changelog 0.6.1 in sechs Sprachen.

## Nachgetragene Funde aus CI-Fix und Prüfstand (ab FD-213)

Behobene Funde aus `output/konsolidierung-2026-10-12/fix-ci-main-claude.md` und
`fix-rest-c-claude.md`, die ihre Nummer erst bei der Landung der Welle 5 bekamen.

### FD-213 Ein Klick an einer Textur während einer Berechnung ging verloren

- Art: Fehler
- Schwere: mittel
- Funktion: `feature:texture.change`
- Prüfpunkt: 6
- Beleg: `output/konsolidierung-2026-10-12/fix-ci-main-claude.md`, Punkt 17: `test_operation_ui.py::test_a_texture_panel_click_while_the_scene_evaluates_changes_the_step_after_it` auf macOS Intel rot (`0.6 == 0.9`); lokal nachgestellt mit verzögertem `_PreviewWorker.work`: Verzögerung 0 → 0,9, 0,5 s und 3 s → 0,6, auch nach 20 s (`texslow*.txt`).
- Ursache: Nach der Auswertung baut das Merkmalfenster die Textur neu auf, `show_texture` meldete die Werte des Schritts als Änderung und stellte die 300-ms-Entprellung; rechnete die Vorschau des getragenen Klicks länger, band die Uhr die alten Werte und ersetzte die Freigabe samt wartendem Klick — kein Schritt, kein Satz.
- Vorschlag: `_apply_carried_feature_order` verwirft Merkposten und Uhr des Neuaufbaus, bevor es bindet; beide Wege des getragenen Klicks (Merkmalfenster und Maßgruppe) gehen hierdurch.
- Wirkung beim Kunden: An größeren Modellen fiel ein *Übernehmen* an einer Textur während einer Berechnung still weg; seit 0.6.0.
- Stand: behoben `bfdad2d9a`; der Fall hält die Vorschau an und lässt die Uhr ablaufen, am Stand davor rot (`0.6 == 0.9`), danach grün, `test_operation_ui.py` ganz 328 passed; die Wurzel trägt seit `6369e3b81` `app/ui/waiting_click.py` (FD-192); Endprobe 38862811071 auf Linux, macOS ARM, macOS Intel und Windows grün.

### FD-214 Ohne Grafiktreiber hing das Prozessende in `wgpuSurfaceRelease`

- Art: Stabilität
- Schwere: mittel
- Funktion: `viewport`
- Prüfpunkt: 6
- Beleg: `output/konsolidierung-2026-10-12/fix-ci-main-claude.md`, Punkt 19: Windows-Runner ohne Grafikkarte (WARP), py-spy des Fallprozesses im Hauptfaden in `wgpuSurfaceRelease → wgpuTextureViewRelease → WaitForSingleObjectEx` aus `GPUCanvasContext.__del__` beim Prozessende; nach `release_renderer` lebten `GfxRenderer`, `WgpuRenderer`, `WgpuContextToScreen` und `GPUCanvasContext` weiter; A/B in Probe 38855455034: ohne Freigabe beim Schließen 6 von 6 hängend, mit 0 von 6.
- Ursache: Die Bildschirmfläche der Ansicht ging erst beim Abbau des Interpreters, nach Fenster und Anwendung; dort wartete wgpu ohne Gerät ewig.
- Vorschlag: `GfxRenderer.close()` gibt die Fläche frei, solange Fenster und Gerät leben.
- Wirkung beim Kunden: Ohne Grafiktreiber, etwa in einer virtuellen Maschine, lief Solidon nach dem Schließen unsichtbar weiter.
- Stand: behoben `973fc5128`; `test_render_gfx_regressions.py` (ein Zeuge zählt die Freigabe, die Mutation ohne Aufruf ist rot; ein Vertragsfall über die Interna von pygfx, rendercanvas und wgpu); Endprobe 38862811071: Windows-Prüfstandsfall zwölfmal ohne Hänger.

### FD-215 Die Sprachkarte der Website deckte die Fußverweise am Seitenende

- Art: Fehler
- Schwere: leicht
- Funktion: keine Zeile: Website, Karte mit dem Sprachhinweis
- Prüfpunkt: 9
- Beleg: `output/konsolidierung-2026-10-12/fix-ci-main-claude.md`, Punkt 18: `test_website_browser.py::test_the_fixed_card_keeps_its_space_free[telefon]` auf macOS rot; die Sonde zeigte `--language-hint-space` 162 px, der berechnete `padding-bottom` von `body` aber 0 px, am Seitenende lagen 12 Fußverweise unter der Karte; lokal nachgestellt mit QtWebEngine offscreen, 12-mal der Telefonfall: am Stand von main 4 von 12 mit verdeckten Verweisen.
- Ursache: Chromium rechnete den Stil von `body` nach dem Setzen des Polsters während des Ladens erst beim nächsten Bild nach (im Prüfstand ohne Bild dauerhaft); weder die Variable an `body` noch ein Inline-Stil hielten.
- Vorschlag: einen eigenen leeren Block in der Höhe der Karte am Ende von `body`, der den Platz sofort hält; die Variable nur noch für `scroll-padding-bottom`.
- Wirkung beim Kunden: Auf dem Telefon lagen die Fußverweise am Seitenende zeitweise unter der Sprachkarte und waren nicht zu erreichen.
- Stand: behoben `0da225deb`, `730e741f6`; lokal 12 von 12 ohne verdeckten Verweis, der Browserfall prüft die Höhe des Blocks gegen den Platzwert und nach dem Schließen 0 (Mutation ohne `spacer.remove()` rot); Endprobe 38862811071 auf vier Plattformen grün.

### FD-216 Ein wartender Klick zeigte alte Werte, und gleiches Tippen ließ ihn still fallen

- Art: Fehler
- Schwere: mittel
- Funktion: `resize_hole`, `feature:texture.change`
- Prüfpunkt: 6
- Beleg: Nachprüfung CI, R2-2 (`output/konsolidierung-2026-10-12/review2-ci-claude.md`, Sonde `test_zz_sonde_review2.py`): Während der gehaltene Klick an seiner Freigabe wartete, zeigte die Maßgruppe 5,20, der Klick wollte 5,70; den gewollten Wert erneut getippt, verwarf den Klick ohne Schritt und ohne Satz, ein anderer Wert ebenso; an der Textur dasselbe mit 0,6 gegen 0,9; neue Fälle in `test_waiting_click_rebuild.py` am Stand davor 8 rot (`fix-ci-main-claude.md`).
- Ursache: `_apply_carried_feature_order` und `show_values` der neuen Maßgruppe banden mit verschiedenen Eigentümern, ein gleicher Auftrag behielt die Freigabe nur beim selben; `_check_waiting_order` meldete nur den Klick nach der Auswertung, nicht den an der Freigabe wartenden.
- Vorschlag: Nach einem Neuaufbau zeigen Maßgruppe und Merkmalfenster die Werte des wartenden Auftrags; ein anderer Wert sagt, dass nicht übernommen wurde.
- Wirkung beim Kunden: Feld und Statuszeile widersprachen sich für die ganze Rechenzeit; wer dem Feld glaubte und seinen Wert noch einmal tippte, verlor die Änderung ohne Satz; seit 0.6.0.
- Stand: behoben `c14595ed8`; die neuen Fälle am Stand davor 8 rot, danach 9 grün; die Mutationen (Werte tragen, Satz im Merkmalfenster, Satz in der Maßgruppe, Wächter `_clear_preview`) sind rot.

### FD-217 Der Maßkartenläufer endete ohne `record_shutdown`

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: native Läufer des Prüfstands (`tools/native_measure_card.py`)
- Prüfpunkt: 19
- Beleg: `output/konsolidierung-2026-10-12/fix-rest-c-claude.md`, Fund unterwegs: `test_window_bench.py::test_every_process_end_names_its_stragglers_once` war am Zweig seit dem Merge von F10 rot (am Stand `94da19159` 1 failed).
- Ursache: `CardRoute.run` verwarf die Nachzügler von `shutdown_window` und setzte `shutdown_complete` selbst (RF-18), statt über `record_shutdown` zu gehen.
- Vorschlag: `record_shutdown` nach `leave()`, damit ein sofortiges Ende bei Nachzüglern die Siegelprüfung nicht überspringt.
- Wirkung beim Kunden: Kein Produktfehler; ein Nachzügler im nativen Lauf endete ohne Namen.
- Stand: behoben `d5530a736`; der Test am Stand davor rot, danach grün (`test_window_bench`, `test_native_measure_card_cursor`, `test_native_runs`, `test_function_guard` 132 passed); nativer Nachweis mit der Maßkartenfolge im Schlusslauf (Plan Punkt 3, L1).
