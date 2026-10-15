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
| Funktion | Kennung der Zeile aus der Funktionsliste |
| Prüfpunkt | 1–19 oder Kriterium (E1 … I6) |
| Beleg | Bild, Kennzahl, Schrittfolge |
| Ursache | Satz |
| Vorschlag | Satz |
| Wirkung beim Kunden | Satz |
| Stand | offen RM-…, behoben `<commit>`, gut nach Fix `<lauf>` |

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
- Stand: offen RM-741; der beobachtete Begriff ist im gemeinsamen Paket FD7/16/63/64 durch eine Wirkungserklärung zur Druckkorrektur ersetzt, mit vier neuen Textschlüsseln in allen fünf Katalogen. Geliefert als f333e5ba7d0248646ef7e4c16f0434573366e604, integriert als b863815593f2e8ec43e73db7957e6828b77ea60c. 44 enge Fälle, 30 bestehende Anschlüsse und 2.861 Kernfälle grün; gemeinsamer 71-Fall-Anschluss und anschließende 126-Fall-Integration mit FD66 grün. Die echte Sechssprachenfolge auf bc2d5e20c376e5d9003c1c1d8058033a93ca427f (native-runner-v3/runs/run-20261013T210714907Z) ist abgeschlossen: jeweils regulär Exit 0 und 62/62 Bedingungen, insgesamt 372. Alle 192 Originalbilder wurden einzeln gelesen; sämtliche 51 eigenen Prozessidentitäten beendet. Die ab Bild021 abgeschnittene Statuszeile bleibt im Original dokumentiert und wurde getrennt unter FD75 kausal behoben. Keine nachträgliche Umwertung der alten Bilder. Gemeinsamer endgültiger D0-Lauf und Tor bleiben offen.

### FD-8 Der Kalibrierstand heißt „Startwert“

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `Bearbeiten/Material kalibrieren …`
- Kriterium: V1
- Beleg: Überschrift „PETG — Startwert“; Fall 034, `flaeche-sprachen-dialog.png`
- Ursache: `app/ui/calibration_dialog.py:73` (`tr("Startwert", context="Kalibrierstand")`).
- Vorschlag: „noch nicht kalibriert“ oder „Werkswerte“.
- Wirkung beim Kunden: Das Wort sagt nicht, dass noch nicht gemessen wurde.
- Stand: offen RM-747

### FD-9 Die Beschreibung von Schriftzug anlegen ist zu lang

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `create_label`
- Kriterium: V2
- Beleg: steht im eingefrorenen Bestand zu langer Texte; Fall 034, `surfaces/create_label-*.json`
- Ursache: `app/core/geom/label_ops.py` (doc).
- Vorschlag: ein Satz, etwa „Legt einen Schriftzug als eigenes Objekt an — zum Aufkleben oder für zwei Farben.“; Eintrag in `tests/data/text_lengths/` streichen.
- Wirkung beim Kunden: Ein zu langer Satz über dem ersten Feld wird übersprungen.
- Stand: offen RM-747

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
- Stand: offen RM-747

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
- Stand: offen RM-741; FeatureEditPriority gibt dem angebotenen Merkmalauftrag Vorrang, auch bei vorübergehender Sperre, und stellt die Katalogpriorität nach Ende wieder her. Gemeinsam mit FD7/63/64 als f333e5ba7d0248646ef7e4c16f0434573366e604 geliefert und als b863815593f2e8ec43e73db7957e6828b77ea60c integriert. 44 enge Fälle sowie gemeinsame Anschlüsse mit 71 und 126 Fällen grün. Abbrechen, Einzel-/Sammelübernahme und Undo am echten Fenster in allen sechs Sprachen belegt. Die echte Sechssprachenfolge auf bc2d5e20c376e5d9003c1c1d8058033a93ca427f (native-runner-v3/runs/run-20261013T210714907Z) ist abgeschlossen: jeweils regulär Exit 0 und 62/62 Bedingungen, insgesamt 372. Alle 192 Originalbilder wurden einzeln gelesen; sämtliche 51 eigenen Prozessidentitäten beendet. Die ab Bild021 abgeschnittene Statuszeile bleibt im Original dokumentiert und wurde getrennt unter FD75 kausal behoben. Keine nachträgliche Umwertung der alten Bilder. Gemeinsamer endgültiger D0-Lauf und Tor bleiben offen.

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
- Stand: offen RM-747

### FD-20 Die Maßspalte im Objektbaum schneidet krumme Maße ab

- Art: Gestaltung
- Schwere: leicht
- Funktion: `finding.action:scale_to_fit`
- Prüfpunkt: 9
- Beleg: „253,44 × 190,08 × 12,67 mm“ in 117 px bei 152 px Bedarf; Fall 046
- Ursache: `app/ui/panels.py` (`_size_columns`, Spalte auf `MEASURE_SHARE` gedeckelt).
- Vorschlag: Spalte nach dem Inhalt der sichtbaren Zeilen statt nach festem Anteil.
- Wirkung beim Kunden: Ein eingelesenes Modell mit krummen Maßen zeigt das Maß abgeschnitten.
- Stand: offen RM-748

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
- Stand: offen RM-737

### FD-32 Der Sperrgrund steht im Reiter Auswahl zweimal

- Art: Gestaltung
- Schwere: leicht
- Funktion: `resize_hole`
- Kriterium: E5
- Beleg: ohne Freischaltung unter dem Suchfeld und im Merkmalfenster derselbe Satz (Fix FD-26 bis FD-30)
- Ursache: FD-5 setzte den Satz an beiden Flächen.
- Vorschlag: die Zeile unter dem Suchfeld gilt für den Reiter; das Merkmalfenster trägt den Grund nur an seinen grauen Elementen.
- Wirkung beim Kunden: Derselbe Satz zweimal lenkt vom Weg ab.
- Stand: offen RM-737

### FD-33 Jede Aktualisierung der Fensterbefehle fragt nach dem exakten Kern

- Art: Leistung
- Schwere: leicht
- Funktion: `resize_hole`
- Prüfpunkt: 6
- Beleg: im Profil 3,5 von 9,3 ms je `_update_actions` in `importlib.find_spec` über `exact_kernel_present()` (Fix FD-26 bis FD-30)
- Ursache: Die Anwesenheit des Kerns wird bei jedem Aufruf neu gesucht, obwohl sie sich im Prozess nicht ändert.
- Vorschlag: je Prozess einmal ermitteln, an der Quelle; Messung vorher und nachher.
- Wirkung beim Kunden: Jede Auswahl und jede Handlung kostet unnötig Zeit im Hauptfaden.
- Stand: offen RM-737

### FD-34 Eine erkannte Bohrung holt Bohrung ändern ins Bild, rechts bleibt Merkmal verschieben scharf

- Art: Fehler
- Schwere: mittel
- Funktion: `resize_hole`
- Prüfpunkt: 1
- Beleg: am echten Fenster nach der Auswahl einer erkannten Bohrung (`fix-zeile-bohrung.md`, neuer Punkt 1)
- Ursache: `request_in_view` holt die Maßgruppe ins Bild, ohne ihre Handlung scharf zu machen, wie es der Knopf *Im Bild einstellen* tut.
- Vorschlag: ein Weg für Auswahl und Knopf; die Handlung im Bild ist auch rechts die scharfe.
- Wirkung beim Kunden: Rechts steht offen eine andere Handlung als die, deren Maße er im Bild sieht.
- Stand: offen RM-737

## D0: Entwurf neuer Belege FD-35 bis FD-59

Nur Dokumentationsentwurf, keine Änderung der aktuellen Funddatei. Originalurteile und Originalfunde bleiben erhalten. Nummern vom Koordinator vergeben. 25 Ergänzungen; FD36 ist integriert, ein gemeinsamer neuer D0-Nachweis steht aus.

### FD-35 Bettaktion beschreibt Anheben als Senken

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: finding.action:place_on_bed
- Prüfpunkt: 8
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/002/02-flaeche.png rechts unter Auf das Bett setzen: „Senkt den Körper bis auf das Bett“ bei 10 mm Unterstand; 03-uebernommen.png und function.json#result.metrics: Unterseite z=0. V4-Fall002 sagt vor dem Klick ausdrücklich 10 mm Anheben voraus.
- Ursache: app/core/action_effects.py:133, SIDE_EFFECTS[place_on_bed], setzt mit Senkt und den fünf entsprechenden Katalogwerten eine Bewegung nach unten voraus; tatsächlich hängt die Richtung von der Ausgangslage ab.
- Vorschlag: Richtungsneutraler Satz „Setzt den Körper auf das Bett; seitlich bleibt er, wo er ist.“ und fünf Katalogwerte gemäß textfix-fd35-fd43-entwurf.md; oberhalb/unterhalb/auf dem Bett prüfen. Kein Geometriefix.
- Wirkung beim Kunden: Der Kunde liest eine falsche Bewegungsrichtung; das belegte geometrische Ergebnis selbst stimmt.
- Stand: offen RM-745; Texteinheit 2ad0206ed5c9c2064f1fabe5504f9a116e4a8030 geliefert und als ac28ecbb22da16e210eb1f0c653c9b8d8129407b auf welle4/origin integriert. Alle 16 Paketpfade bytegleich; Paketwahl 27388 bestanden/172 übersprungen/4646 abgewählt, gemeinsamer Anschluss 348 bestanden/1 übersprungen/8 abgewählt und Statik grün. AT-01 korrigiert. Gemeinsamer frischer V4-/Sprachbeleg und volles Endtor stehen aus; ursprüngliches rotes Urteil bleibt erhalten.

### FD-36 Entfernen-Hinweis überspringt das notwendige Abbrechen

- Art: Verständlichkeit
- Schwere: mittel
- Funktion: resize_hole
- Prüfpunkt: 7, E7, V5
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/001/04-fehlfall.png: 0,10 mm unter 0,20-mm-Grenze; Maßgruppe bietet Abbrechen, „Merkmal entfernen“ rechts grau. function.json#messages/#steps. Fix-Einzelfall F:/tmp-suche/fix-probe-feedback-codex/native-pinned/cases/001/04-fehlfall.png; process.json Exit0.
- Ursache: FeaturePanel._removal_way nennt die Entfernen-Zeile auch während eines begonnenen Maßentwurfs, obwohl _settle_lock sie dann sperrt. Ohne begonnenen Entwurf ist der direkte Weg richtig.
- Vorschlag: Begonnenen Entwurf unterscheiden; zuerst Abbrechen und danach den tatsächlichen Entfernen-Titel nennen. Fixbericht fix-probe-feedback-codex.md: vier Produktzeilen, sechs Kataloge, 6 vorher rot/18 Gegenfälle grün, danach 24 grün; echte DE-Aufnahme bestätigt den Text.
- Wirkung beim Kunden: Wer dem bisherigen Hinweis folgt, erreicht einen gesperrten Knopf; der erforderliche erste Schritt fehlt.
- Stand: offen RM-737 für den gemeinsamen neuen D0-Nachweis; Paket c75ece14b351c2694bc264d552385c794a3b0723 wurde als f807415569f636113c9e006b6ada3dee8f7c38ee auf welle4 integriert, konfliktfrei und mit identischem Baum 53c371a2740f86b44152b46e918806c46a32a4ba. 24 Regressionen, 72 Gegenfälle und echter Fensterfall belegt; 18604 bestandene Auswahlfälle mit zwei danach behobenen Changelog-Längen, 318 Textnachprüfungen grün. Endtor und gemeinsamer neuer Bildnachweis bleiben offen; keine rückwirkende Änderung der Originalurteile.

### FD-37 Flächenaufnahme einer Sofortaktion entsteht erst nach ihrer Wirkung

- Art: Fehler
- Schwere: mittel
- Funktion: finding.action:place_on_bed
- Prüfpunkt: 9, 19
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/005/flaeche-zoll.png, 010/flaeche-skalierung.png, 017/flaeche-dunkel.png, 020/flaeche-bewegung.png: Verlaufsschritt2 und leerer Bericht; jeweiliges function.json#steps enthält die wirksame Befundaktion in phase=weg.
- Ursache: Prüfstand: phase_surface führte sämtliche path_steps einschließlich des finalen wirksamen Zielklicks vor der Flächenmessung aus.
- Vorschlag: Walk nur für diesen Flächenzweck nach allen Wegklicks und geprüfter Trefferidentität vor dem Zielklick halten. Normale Aktionswege bleiben wirksam. Kopflose Rot/Grün- und Zieltreffer-Gegenproben im Prüfstandfixbericht; nativer Vollnachweis offen.
- Wirkung beim Kunden: Die beabsichtigte Kundenfläche wird nicht beurteilt; der Bericht könnte eine ungemessene Variante freigeben. Kein belegter Produktfehler der Bettkorrektur.
- Stand: offen RM-737; Die zweite und letzte Durchsicht schließt RPF-M1: Soforthandlungen werden davor gemessen, Dialogöffner danach tatsächlich geklickt und als eigene Fläche aufgenommen. Paket 6d5734da599c73c0d4f7de43812a596499946b9e als 433da64bc31eb57943ad92b776c05a9174d36b91 auf welle4/origin integriert; alle 24 Pins bytegleich, keine Merge-Auflösung. Der FD56-Breitlauf bleibt mit 1 fehlgeschlagen/11178 bestanden/47 übersprungen/1635 abgewählt, Exit 1 historisch rot. Enger endgültiger Wächter-/Qt-Anschluss 96 grün; gemeinsamer Anschluss 755 bestanden/61 abgewählt plus 20 Radfälle, Statik und Prozessausgänge Exit 0. Die Commitmeldung unterzählt die tatsächlichen 20 Radfälle als 15. Gemeinsamer frischer D0-Nachweis und Endtor stehen aus; keine dritte C-Durchsicht und kein Gesamtgrün für D8/P18.

### FD-38 E7 verwirft einen ausdrücklich gemessenen Rechenausweg

- Art: Fehler
- Schwere: mittel
- Funktion: finding.action:place_on_bed
- Prüfpunkt: 2, E7
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/002/function.json#messages: kind=sperrgrund, way_out=true, „… wieder frei, sobald die Berechnung fertig ist.“; 04-fehlfall.png zeigt Wird neu berechnet/Voriger Stand/grauen Knopf. Automatik nennt Meldung ohne Handlung.
- Ursache: Prüfstand: E7 verlangt pauschal actions; der bei V5 erlaubte und als way_out gemessene Rechenausweg wurde dort nicht berücksichtigt.
- Vorschlag: Nur explizit belegte Auswege an Sperrgrund/Grenzablehnung akzeptieren. Echte Meldungen ohne Handlungen bleiben auch bei beliebigem way_out=true rot; entsprechende Gegenproben erhalten.
- Wirkung beim Kunden: Falscher schwerer Sackgassenbefund in der Abnahme; die gezeigte Berechnungssperre erklärt bereits ihren Rückweg.
- Stand: offen RM-737; Ausdrücklich gemessene Rechenauswege werden als E7-Ausweg anerkannt; handlungslose Fehlermeldungen erhalten dadurch keine Freigabe. Paket 6d5734da599c73c0d4f7de43812a596499946b9e als 433da64bc31eb57943ad92b776c05a9174d36b91 auf welle4/origin integriert; alle 24 Pins bytegleich, keine Merge-Auflösung. Der FD56-Breitlauf bleibt mit 1 fehlgeschlagen/11178 bestanden/47 übersprungen/1635 abgewählt, Exit 1 historisch rot. Enger endgültiger Wächter-/Qt-Anschluss 96 grün; gemeinsamer Anschluss 755 bestanden/61 abgewählt plus 20 Radfälle, Statik und Prozessausgänge Exit 0. Die Commitmeldung unterzählt die tatsächlichen 20 Radfälle als 15. Gemeinsamer frischer D0-Nachweis und Endtor stehen aus; keine dritte C-Durchsicht und kein Gesamtgrün für D8/P18.

### FD-39 Fehlfallbild wird erst nach Escape aufgenommen

- Art: Fehler
- Schwere: mittel
- Funktion: Bearbeiten/Parameter anlegen …
- Prüfpunkt: 7, E7, V5
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/003/04-fehlfall.png zeigt nur das Hauptfenster; function.json#messages enthält die Ablehnung von „breite außen“, closed_by_escape: phase=fehlfall, times=1; kein 04-fehlfall-dialog.png.
- Ursache: Prüfstand: run_steps las die Meldung, schloss anschließend den modalen Parameterdialog mit Escape und erstellte erst danach die Fehlfallaufnahme.
- Vorschlag: Bild im selben Leseschritt wie den Meldungstext vor Escape erfassen; den tatsächlichen Meldungs-/Korrekturweg anschließend unabhängig bewerten. Aufnahmefix allein schließt den automatischen E7/V5-Produktverdacht nicht.
- Wirkung beim Kunden: Der sichtbare Fehlerzustand und sein Ausweg bleiben im Bericht unbewiesen.
- Stand: offen RM-737; Der Fehlerdialog wird vor Escape gesichert; sein früherer echter E7/V5-Meldungsbefund und die alten Urteile bleiben erhalten. Paket 6d5734da599c73c0d4f7de43812a596499946b9e als 433da64bc31eb57943ad92b776c05a9174d36b91 auf welle4/origin integriert; alle 24 Pins bytegleich, keine Merge-Auflösung. Der FD56-Breitlauf bleibt mit 1 fehlgeschlagen/11178 bestanden/47 übersprungen/1635 abgewählt, Exit 1 historisch rot. Enger endgültiger Wächter-/Qt-Anschluss 96 grün; gemeinsamer Anschluss 755 bestanden/61 abgewählt plus 20 Radfälle, Statik und Prozessausgänge Exit 0. Die Commitmeldung unterzählt die tatsächlichen 20 Radfälle als 15. Gemeinsamer frischer D0-Nachweis und Endtor stehen aus; keine dritte C-Durchsicht und kein Gesamtgrün für D8/P18.

### FD-40 Fremder Generierungsdialog verunreinigt spätere Sprachflächen

- Art: Fehler
- Schwere: mittel
- Funktion: finding.action:place_on_bed
- Prüfpunkt: 9, 19
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/043/flaeche-de-finding.action_place_on_bed-53db7bc0-dialog.png zeigt Beschreibung/Bild/ComfyUI und fremden Projektkontext; entsprechendes Hauptbild zeigt korrekt den Würfel am Bett. D8-Ledger:38 solche Zusatzpfade,25 unterschiedliche Inhalte. Weitere tool:analysis/tool:layers/command:edit.auto_split bestätigt der Zweitprüfer.
- Ursache: Prüfstand: LanguageFlow wechselte nach phase_surface die Startszene; StepMachine räumte nur laufende modale Aufrufe ab. Der nichtmodale Generierungsdialog blieb geöffnet. windows_to_picture fotografierte die tatsächlich sichtbaren Fenster korrekt.
- Vorschlag: Nach jeder Sprachfläche echten Escape-Rückweg an sichtbaren Nebenfenstern durchführen; bei verbleibendem Fenster Teilfläche mit bench.surface_cleanup_failed rot beenden, bevor das nächste Projekt öffnet. Keine Fremdbilder filtern und keine direkten reject-Abkürzungen.
- Wirkung beim Kunden: Spätere Dialogbilder gehören nicht zur benannten Handlung; ihre Texte und Maße dürfen deren Beurteilung nicht tragen. Kein nachgewiesener falscher Produktaufruf.
- Stand: offen RM-737; Der nichtmodale Generator wird tatsächlich geöffnet, aufgenommen und über Escape geschlossen; Generator-/Folgeflächenbeleg liegt vor. Die später aufgedeckte Auto-Split-Radstörung ist über FD56 separat belegt und korrigiert. Paket 6d5734da599c73c0d4f7de43812a596499946b9e als 433da64bc31eb57943ad92b776c05a9174d36b91 auf welle4/origin integriert; alle 24 Pins bytegleich, keine Merge-Auflösung. Der FD56-Breitlauf bleibt mit 1 fehlgeschlagen/11178 bestanden/47 übersprungen/1635 abgewählt, Exit 1 historisch rot. Enger endgültiger Wächter-/Qt-Anschluss 96 grün; gemeinsamer Anschluss 755 bestanden/61 abgewählt plus 20 Radfälle, Statik und Prozessausgänge Exit 0. Die Commitmeldung unterzählt die tatsächlichen 20 Radfälle als 15. Gemeinsamer frischer D0-Nachweis und Endtor stehen aus; keine dritte C-Durchsicht und kein Gesamtgrün für D8/P18.

### FD-41 Native Sprachmessung bricht bei der Kontrastaufnahme ab

- Art: Stabilität
- Schwere: schwer
- Funktion: Bearbeiten/Parameter anlegen …
- Prüfpunkt: 9, G6
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/032/process.json,034/process.json,041/process.json: Exit3221225477, kein Timeout;14/2/7 gespeicherte Sprachteilflächen. Startmarken filament.section/create_label/pin_for_bore. Stacks bemerken Fehler in Qt-Arbeiter/QCompleter; Originalabbildungen und Teilprotokolle bleiben unverändert.
- Ursache: Prüfstandverdacht inzwischen an Kontrastcapture eingegrenzt: top.grab() berührt das gesamte Fenster mit nativer 3D-Fläche. Weglassen verhindert bisher den Abbruch; Ersatz durch screen.grabWindow liefert laut Fixagent inzwischen drei Originalsequenzen plus einen zweiten vollständigen Lauf mit Exit0. Ursprüngliche Stackorte beweisen keine frühere Beschädigungsursache; keine Hardwarebehauptung.
- Vorschlag: Echte Schirmaufnahme für unveränderte Farbproben verwenden; reproduzierende Gegenprobe, wiederholte native Sprachfolgen, auswertbare Kontrastwerte, Abschlussauswahl und Commit dokumentieren. Ursachenbehebung erst nach dem kompletten Nachweissatz freigeben.
- Wirkung beim Kunden: Sprachprüfung endet vorzeitig; ihre Vollständigkeit und Kontrastabnahme fehlen. Schwere bezieht sich hier auf den blockierenden Prüfstand, nicht auf einen nachgewiesenen Kundenabsturz.
- Stand: offen RM-737; Native Bildschirmaufnahme ersetzt das gefährliche QWidget-Neuzeichnen; RPF-S1 geschlossen. Fehlende Pixel bleiben ungemessen, schlechte gemessene Kontraste rot. Frühere AccessViolations werden nicht umgedeutet. Paket 6d5734da599c73c0d4f7de43812a596499946b9e als 433da64bc31eb57943ad92b776c05a9174d36b91 auf welle4/origin integriert; alle 24 Pins bytegleich, keine Merge-Auflösung. Der FD56-Breitlauf bleibt mit 1 fehlgeschlagen/11178 bestanden/47 übersprungen/1635 abgewählt, Exit 1 historisch rot. Enger endgültiger Wächter-/Qt-Anschluss 96 grün; gemeinsamer Anschluss 755 bestanden/61 abgewählt plus 20 Radfälle, Statik und Prozessausgänge Exit 0. Die Commitmeldung unterzählt die tatsächlichen 20 Radfälle als 15. Gemeinsamer frischer D0-Nachweis und Endtor stehen aus; keine dritte C-Durchsicht und kein Gesamtgrün für D8/P18.

### FD-42 Gegenstücke setzen zeigt sechs unabhängige Vorderseitenfelder

- Art: Einfachheit
- Schwere: mittel
- Funktion: Erzeugen/Bausteine/Gegenstücke setzen …
- Prüfpunkt: E5
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/031/flaeche-de-Erzeugen_Bausteine_Gegenstücke_setzen-5b902f72-dialog.png und surfaces/Erzeugen_Bausteine_Gegenstücke_setzen-5b902f72.json#fields: Paar,Durchmesser,Länge,Form,Spiel,Fase jeweils front=true; auch ES/IT/PT. Keine Vektorkomponenten.
- Ursache: counterpart_dialog baut sämtliche Pair.shared-Felder in das vordere Formular und ignoriert vorhandenes ParamSpec.placement. Form, Spiel und Fase sind im Schema bereits advanced.
- Vorschlag: Vorn Paar und gewöhnliche Maße; vorhandene advanced-Felder unter Weitere Einstellungen mit aktueller Zusammenfassung. ContentHeight/expanded_width und natürlich bemessene Breite verwenden, alle Werte/Paare/Tastaturwege in sechs Sprachen erhalten.
- Wirkung beim Kunden: Für die einfache Gegenstückaufgabe muss der Kunde sechs fachliche Werte gleichzeitig überblicken; E5 erlaubt höchstens vier.
- Stand: offen RM-747; Gegenstücke-Paket d06fb300be9c0042fb840aa10f03c74c541f1991 geliefert und als 9b3e44120881b78d54eb72cd1eb05ebe55e82ede auf welle4/origin integriert. KF-M1 und KF-L1 korrigiert; sechs native Sprachwege sowie Größe, Klappen, Abbruch, Übernahme und Undo im Autorenbericht belegt. Root prüfte alle fünf vereinigten Kataloge schlüsselweise und den Semikolonbestand 326; gemeinsamer Anschluss 507 bestanden/2 übersprungen/83 abgewählt plus Statik Exit 0. Alter breiter Lauf mit zwei später eng reparierten Regelverstößen bleibt rot dokumentiert. Gemeinsamer neuer D0-Lauf und Endtor noch offen, kein nachträgliches Angleichen der Originalurteile.

### FD-43 Übersetzte Handlungsaufzählungen enthalten deutsches und

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: paint_slot
- Prüfpunkt: 9, V1
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/033/flaeche-es-paint_slot-9865a109.png und036/flaeche-pt-paint_slot-9865a109.png rechts; „Duplicar característica und …“. Weitere drill_hole-Bilder039/es,040/fr,041/it,042/pt sowie clear_filament034/fr,036/pt. Ein gemeinsamer Textfund.
- Ursache: app/ui/panels.py:_and_then (8144) verknüpft die von _folded bereits übersetzten Titel mit vier fest eingebauten deutschen Trennern in8157–8160. Vorhandenes Muster main_window.py:2903 und Schlüssel tr(und mit Leerzeichen) sind bereits in allen Katalogen vorhanden.
- Vorschlag: Einmal connector=tr(" und ") innerhalb _and_then bestimmen, Suche/rpartition und beide Ergebniswege damit bilden. Bestehende Präfixkürzung erhalten. Zwei und drei Titel in allen sechs Sprachen samt Laufzeitwechsel prüfen. Kein neuer FD43-Katalogschlüssel, enger Entwurf textfix-fd35-fd43-entwurf.md.
- Wirkung beim Kunden: Die sichtbare Auswahlkarte mischt Sprachen; kein benannter Projektinhalt.
- Stand: offen RM-745; Übersetzungsanschluss gemeinsam mit FD35 als 2ad0206ed5c9c2064f1fabe5504f9a116e4a8030 geliefert und als ac28ecbb22da16e210eb1f0c653c9b8d8129407b auf welle4/origin integriert. 27388 Paketfälle und 348 gemeinsame enge Prüfungen bestanden, Statik grün; alle 16 Paketpfade bytegleich. Bestehender übersetzter und-Verbinder bleibt gemeinsame Quelle, keine neue FD43-Katalogdefinition. Frische gemeinsame D4-/D10-Aufnahme und Endtor fehlen; alte Urteile bleiben unverändert.

### FD-44 Skizzenfehler zeigt Ursachencode und verdeckt den Korrekturweg

- Art: Verständlichkeit
- Schwere: mittel
- Funktion: finding.action:sketch.pick_plane
- Prüfpunkt: 7, 8, 19, V5
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/043/flaeche-de-finding.action_sketch.pick_plane-ad8b805d-dialog.png:380×268px, Grund:points_are_on_one_line; Korrekturzeilen aus surfaces/finding.action_sketch.pick_plane-ad8b805d.json#texts nicht sichtbar. Szene ebene_durch_linie.netz.p3d:Quader40×30×20; Tasche2; Ebene through:0,0,20;10,0,20;20,0,20. Zwei getroffene Klicks Befund→Eine andere Ebene wählen. -dialog-2.png ist fremd und zählt nicht.
- Ursache: Die absichtlich kollinearen Ebenenpunkte sind korrekt ungültig. spoken_values/value_line gibt den internen reason roh aus; nachgereichter ErrorNotice wird in show_refusal sichtbar, aber die Dialoghöhe nicht passend nachgeführt. Verständlicher Satz für denselben Grund existiert im Skizzeneditor.
- Vorschlag: Vorhandene verständliche Erklärung zentral wiederverwenden/eng zuordnen; Fehlerbereich und vorhandene Korrekturtexte mit bestehendem ContentHeight-/Refitweg vollständig sichtbar machen, manuelle Größe und erreichbaren Scrollweg erhalten.
- Wirkung beim Kunden: Die Ursache wird technisch statt handlungsnah erklärt, und der angebotene vorhandene Korrekturweg ist im aufgenommenen Fensterzustand unsichtbar. Kein Geometriefehler und keine Behauptung, die Anwendung hätte grundsätzlich keine Korrekturhandlung.
- Stand: offen RM-745; Endgültiges Größenpaket 2e475252186598db3c9967737b4594b716cabde0 als 27a18b48c14b8d84b006c2dffa0d671f20eb66b4 auf welle4/origin integriert; alle neun Pins bytegleich, keine Merge-Auflösung. Paket 16847 bestanden/74 übersprungen/4686 abgewählt, Exit 0; dazu 141 gezielte Fälle und sechs native Komponentenfolgen/27 vom Autor gelesene Bilder. Gemeinsamer Größenanschluss 193 Fälle, Textanschluss 266 Fälle/8 abgewählt, Statik Exit 0. Tatsächliche 11/18-pt-Inhaltsschrift, vollständige Einleitung/Aktionen, manuelle Breite und notwendiges Footerminimum belegt. Gemeinsamer frischer D0-Nachweis und Endtor fehlen; ursprüngliche rote Urteile bleiben erhalten.

### FD-45 Merkmalslisten reservieren Höhe für nicht vorhandene Einträge

- Art: Gestaltung
- Schwere: leicht
- Funktion: pattern_feature
- Prüfpunkt: 9, 19, Z6
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/037/flaeche-de-pattern_feature-2d8cbcf5-dialog.png:380×503px, eine Zeile in≈287×224px Liste,≈200px leer. group_pattern-5f312f3f-dialog.png:380×358px,sechs Zeilen≈96px in≈191px Liste. Alle sechs Sprachbilder bestätigen denselben Listenleerraum; Fehlerzusatztexte getrennt.
- Ursache: Gemeinsames FeatureSetField-QListWidget orientiert seine Höhe nicht an der tatsächlichen Zeilenzahl; Mindest-/Maximalhöhe und Qt-Größenhinweis reservieren zu viel Listenraum.
- Vorschlag: Listenhöhe aus vorhandenen Zeilen, Zeilenhöhen, Rahmen und Innenabständen; bei vielen Einträgen begrenzen und rollen. Nach Einfügen/Schrift-/DPI-Wechsel nachziehen, keine feste deutsche Pixelhöhe. Ziel im DE-Einzelfall etwa40–48px statt224px.
- Wirkung beim Kunden: Unnötige Leere macht den Dialog länger und verschiebt weitere Felder/Knöpfe nach unten; keine exakt verdeckte Modellfläche aus getrenntem Dialogbild behauptet.
- Stand: offen RM-741; Endgültiges Größenpaket 2e475252186598db3c9967737b4594b716cabde0 als 27a18b48c14b8d84b006c2dffa0d671f20eb66b4 auf welle4/origin integriert; alle neun Pins bytegleich, keine Merge-Auflösung. Paket 16847 bestanden/74 übersprungen/4686 abgewählt, Exit 0; dazu 141 gezielte Fälle und sechs native Komponentenfolgen/27 vom Autor gelesene Bilder. Gemeinsamer Größenanschluss 193 Fälle, Textanschluss 266 Fälle/8 abgewählt, Statik Exit 0. Tatsächliche 11/18-pt-Inhaltsschrift, vollständige Einleitung/Aktionen, manuelle Breite und notwendiges Footerminimum belegt. Gemeinsamer frischer D0-Nachweis und Endtor fehlen; ursprüngliche rote Urteile bleiben erhalten.

### FD-46 Rechte Kartenbreite wächst allein mit dem Fensteranteil

- Art: Gestaltung
- Schwere: leicht
- Funktion: resize_hole
- Prüfpunkt: 9, 19, Z6
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/037/flaeche-de-duplicate_feature-66547dd4.png:rechte Karte≈539px; cases/007/flaeche-skalierung.png≈479×752px. Größter gemessener Knopftext im Sechssprachenvergleich154px. Koordinator bestätigt Quellformel25%Fenster,Maximum540:bei2560px tatsächlich540. D8 nach Bettsetzen nur540×122px, darunter freie Ansicht.
- Ursache: Anfangsbreite wird aus Fensterquote bis540px abgeleitet, statt aus Inhalt/Schrift. Laut Koordinator ist keine gespeicherte Benutzerbreite vorhanden, nur CardPlace-Lage. Die Reserve einzelner Texte allein bestimmt noch nicht das Minimum aller Felder.
- Vorschlag: Natürlichen Vorderseiten-/Feld-/Schriftbedarf und vorhandene Mindestbedarfe verwenden; Bildschirmgrenzen und bewusst gewählte Nutzergröße bewahren. Rund400px Standardschrift nur als Vergleichskandidat, nicht universelle harte Breite; sechs Sprachen,Zoll/große Werte/Großschrift prüfen.
- Wirkung beim Kunden: Kurze Inhalte können unnötig 3D-Fläche überlagern; im kleinen D4-Beispiel könnte ein nachgewiesen passender400px-Kandidat≈59.400px² freigeben. Keine Behauptung einer vollständig verlorenen rechten Spalte in D8.
- Stand: offen RM-737; Beobachtete Auswahlfläche D4/RM-741; ursprünglicher PB-01- und FD46-Befund unverändert. FD57 jetzt auf dem vereinbarten MSI MAG271CQR in allen sechs Sprachen nativ belegt: sechs Exit 0 und 54 vom Autor gelesene Bilder; die frühere LG-Folge bleibt nur Zusatzbeleg. FD58 korrigiert den vollen Spaltenumfang beim Umbruch sowie den ungültigen Zwischenzustand indexOf=-1 und dessen Messcache. Echte Folge schmal/9 pt→groß/14 pt→schmal/9 pt vorher rot, endgültige 66 Fälle und Statik grün. Manifest 4a03df4877f1d4ae8197950c7e61a113bad8fe659d6f0952267b6481a13b3d18 bindet fünf eigene Quellen und 2300 Pins; finaler MSI-Anschluss sechs Sprachen/24 vom Autor gelesene Bilder, alle Exit 0, Root liest DE/ES zusätzlich. Finale breite Auswahl abgeschlossen: 14603 bestanden/57 übersprungen/4633 abgewählt, Exit 0, 2300 Pins unverändert. Paket 11f44ba88f6b1af704f15df45597aa7ea92ee23a auf origin/codex/d0-panel-breite geliefert, Worktree sauber; 66 gezielte Fälle und 24 finale MSI-Bilder gehören zum gebundenen Lieferstand. Integriert auf welle4/origin als e68ca22cbf84417e3b2dea2bff473627e647927f, Baum 746d0a056e6d692c8d231ad4c03939141fea5fc6; Hooks/Push Exit 0. Vier Paketpins bytegleich, panels.py bewahrt ausschließlich die disjunkten Altänderungen _and_then-Übersetzung und FD36. Root-Anschluss 17 bestanden/201 abgewählt und Statik Exit 0. Erster Fensteranschluss 212 bestanden/6 Schriftumgebungsfehler, Exit 1; nach tatsächlichem Laden von zwölf DejaVu-TTFs dieselbe unveränderte Kartendatei vollständig 66/66 grün, Exit 0. Der erste rote Lauf bleibt erhalten. Gemeinsame native Gesamtabnahme und Endtor stehen weiterhin aus. Keine Gesamtfreigabe, ursprüngliche Urteile und rote Zwischenstände bleiben erhalten.

### FD-47 Messfläche trifft Nachbarkarte statt aktive Maßgruppe

- Art: Fehler
- Schwere: mittel
- Funktion: resize_hole
- Prüfpunkt: 2, 8, E5, V3
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/001/function.json#texts/#fields/#layout:ab Zeilen2558/2760/3082 _SelectionPage; Bild02-flaeche.png zeigt aktive Maßgruppe mit vier Feldern. Sprachprotokolle u.a.move_feature/duplicate_feature/resize_feature melden fremde Maßgruppen.
- Ursache: Vom Fixagenten bestätigt: tools/function_surface.py:surface_for ignorierte feature:-Zielart und fiel auf die Auswahlseite zurück. Dadurch stammen Einleitung/Feld-/Layoutzahlen nicht ausschließlich von der bedienten Fläche.
- Vorschlag: Nur bei passender öffentlicher feature_panel.measure_op und sichtbarem measure.apply deren eigene Elternkarte wählen; sonst tatsächlichen Zielkopf und eigene Elternzeile. Eine fremde Maßgruppe ausdrücklich ausschließen.
- Wirkung beim Kunden: Falsche Wörter-/Feldzählung und falsche Zielflächen können Funktionen unberechtigt rot oder grün erklären; Produktbeurteilung der Maßgruppe bleibt ohne neue Aufnahme offen.
- Stand: offen RM-737; RPF-M2 geschlossen: eigene offene Featurezeile und sichtbarer eigener Footer werden erfasst; sechs italienische Flächen samt Footer nativ belegt. Fremde Maßgruppen bleiben ausdrücklich ungemessen. Paket 6d5734da599c73c0d4f7de43812a596499946b9e als 433da64bc31eb57943ad92b776c05a9174d36b91 auf welle4/origin integriert; alle 24 Pins bytegleich, keine Merge-Auflösung. Der FD56-Breitlauf bleibt mit 1 fehlgeschlagen/11178 bestanden/47 übersprungen/1635 abgewählt, Exit 1 historisch rot. Enger endgültiger Wächter-/Qt-Anschluss 96 grün; gemeinsamer Anschluss 755 bestanden/61 abgewählt plus 20 Radfälle, Statik und Prozessausgänge Exit 0. Die Commitmeldung unterzählt die tatsächlichen 20 Radfälle als 15. Gemeinsamer frischer D0-Nachweis und Endtor stehen aus; keine dritte C-Durchsicht und kein Gesamtgrün für D8/P18.

### FD-48 Änderungsprobe liest noch das alte Importergebnis

- Art: Fehler
- Schwere: mittel
- Funktion: resize_hole
- Prüfpunkt: 12
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/001/function.json#revise (Zeilen3935–3972):menue und doppelklick mit ursprünglichen params src1/unit/place_on_bed/centre statt resize_hole; history_before1,history_after2. Automatik meldet Verlauf gewachsen beim Ändern. Neuer eigener Autorenbeleg F:/tmp-suche/probelauf-zwei-pruefstand-fix-codex/fd48-native-reviewfix/cases/001/function.json#revise/#steps und review-native-reading.log: beide Wege tippen tatsächlich 8,8; typed_values und params_after tragen diameter8.8, Verlauf jeweils2→2.
- Ursache: Vom Fixagenten bestätigt: phase_revise wartete nur auf idle, obwohl last_result noch zum vorherigen Import gehörte. Die Werte- und Verlaufsbasis wurden vor dem fertigen neuen Ergebnis gelesen.
- Vorschlag: Nach Vorschau und erfolgreichem run_steps ein wirklich neues last_result sowie die erwartete Verlaufslänge abwarten, erst danach Werte vergleichen. Verweigerte Übernahme als roten Gegenfall erhalten.
- Wirkung beim Kunden: Falscher schwerer Änderungsfund im Prüfbericht; aus diesen alten Parametern folgt kein belegter Kundenfehler des nachträglichen Änderns.
- Stand: offen RM-737; Tatsächlich getippte 8,8 mm über Menü und Doppelklick sowie Verlauf 2→2 sind belegt; P12 lokal erfüllt. Die passende fertige Vorschau ersetzt das veraltete Importergebnis als Zeitbasis, alte Ø8-Teilbelege bleiben getrennt. Paket 6d5734da599c73c0d4f7de43812a596499946b9e als 433da64bc31eb57943ad92b776c05a9174d36b91 auf welle4/origin integriert; alle 24 Pins bytegleich, keine Merge-Auflösung. Der FD56-Breitlauf bleibt mit 1 fehlgeschlagen/11178 bestanden/47 übersprungen/1635 abgewählt, Exit 1 historisch rot. Enger endgültiger Wächter-/Qt-Anschluss 96 grün; gemeinsamer Anschluss 755 bestanden/61 abgewählt plus 20 Radfälle, Statik und Prozessausgänge Exit 0. Die Commitmeldung unterzählt die tatsächlichen 20 Radfälle als 15. Gemeinsamer frischer D0-Nachweis und Endtor stehen aus; keine dritte C-Durchsicht und kein Gesamtgrün für D8/P18.

### FD-49 G7 zählt beschriftete Aufklapppfeile als namenlose Symbolknöpfe

- Art: Fehler
- Schwere: leicht
- Funktion: resize_hole
- Prüfpunkt: 19, G7
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/001/function.json#icons und 02-flaeche.png: Merkmal verschieben, Zum Langloch ziehen, Merkmal drehen und Merkmal verdoppeln sind sichtbare beschriftete Zeilenköpfe; G7 fordert dennoch eigenes Symbol und Tooltip. Bestätigung im Prüfstandfixbericht, Abschnitt FD47/FD48/FD49.
- Ursache: Prüfstand: Ein checkable QToolButton mit Pfeil wurde trotz unmittelbar benachbartem sichtbarem gleichnamigem Label als Bedienelement ohne Text klassifiziert.
- Vorschlag: Nur diese unmittelbar und gleichnamig beschrifteten Aufklappköpfe als Textbedienelement behandeln. Verborgene, leere und anders benannte Labels entlasten nicht. headings-red: 1 failed/12 passed, danach grün laut Fixbericht; echte namenlose Symbolknöpfe bleiben Negativfälle.
- Wirkung beim Kunden: Die Abnahme erzeugt einen falschen Symbolbefund und könnte zu überflüssigen Symbolen oder Textdoppelung führen; kein belegtes namenloses Bedienelement an dieser Bildstelle.
- Stand: offen RM-737; G7 erkennt ausschließlich passend beschriftete Aufklapppfeile; leere, verdeckte oder anderslautende Beschriftungen bleiben Gegenfälle. Paket 6d5734da599c73c0d4f7de43812a596499946b9e als 433da64bc31eb57943ad92b776c05a9174d36b91 auf welle4/origin integriert; alle 24 Pins bytegleich, keine Merge-Auflösung. Der FD56-Breitlauf bleibt mit 1 fehlgeschlagen/11178 bestanden/47 übersprungen/1635 abgewählt, Exit 1 historisch rot. Enger endgültiger Wächter-/Qt-Anschluss 96 grün; gemeinsamer Anschluss 755 bestanden/61 abgewählt plus 20 Radfälle, Statik und Prozessausgänge Exit 0. Die Commitmeldung unterzählt die tatsächlichen 20 Radfälle als 15. Gemeinsamer frischer D0-Nachweis und Endtor stehen aus; keine dritte C-Durchsicht und kein Gesamtgrün für D8/P18.

### FD-50 Paar im Gegenstücke-Dialog hat keine eigene zugängliche Feldhilfe

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: Erzeugen/Bausteine/Gegenstücke setzen …
- Prüfpunkt: 8, V3
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/031/surfaces/Erzeugen_Bausteine_Gegenstücke_setzen-5b902f72.json#fields: fünf von sechs Feldern mit eigenem Satz, Paar ohne Tooltip/AccessibleDescription; F:/tmp-suche/probelauf-d0-zwei-codex/cases/031/flaeche-de-Erzeugen_Bausteine_Gegenstücke_setzen-5b902f72-dialog.png. Stufe-B-D10-Bericht und fix-counterpart-front-codex.md Abschnitt FD-50.
- Ursache: Der bereits übersetzte erklärende Satz pair.doc erscheint im Dialog, ist aber nicht dem Paarfeld als Kurzhilfe und AccessibleDescription zugeordnet.
- Vorschlag: Gemeinsamen Pair.doc beim Paarwechsel an Tooltip und AccessibleDescription von Feld und Beschriftung binden. KF-L1 verlangt dabei die inhaltstreue Kürzung der beiden zentralen Quellen für Schraube/Mutter und Buchse/Loch von 30/29 auf höchstens25 deutsche Wörter samt je fünf Katalogwerten. Die frühere Aussage keine neuen Katalogtexte ist damit überholt. Eine Quelle für sichtbaren Hinweis und Hilfe erhalten; drei Paare/sechs Sprachen und tatsächliche Wort-/Satzgrenze prüfen. Von FD42 getrennt nachweisen.
- Wirkung beim Kunden: Direkt am obersten Auswahlfeld fehlt der erklärende Satz für Kurzhilfe und Hilfstechnik.
- Stand: offen RM-747; beide zentralen Pair.doc samt ihren Katalogwerten auf 19–23 Wörter gekürzt, anschließend Schraubenhilfe ohne Semikolon nachgeführt. Paket d06fb300be9c0042fb840aa10f03c74c541f1991 geliefert und als 9b3e44120881b78d54eb72cd1eb05ebe55e82ede auf welle4/origin integriert. Root-Katalogaudit bestätigt die vereinigten Schlüsseländerungen ohne Verlust; kombinierter Semikolonbestand 326. Gemeinsamer Anschluss 507 bestanden/2 übersprungen/83 abgewählt und ganze Statik Exit 0. Alter breiter Lauf bleibt mit zwei anschließend gezielt behobenen Regelverstößen erhalten. Gemeinsamer frischer D0-/Feldhilfennachweis und Endtor stehen aus.

### FD-51 Kurzer Dialoginhalt behält eine unnötige Mindesthöhe von 88 Pixeln

- Art: Gestaltung
- Schwere: leicht
- Funktion: rename_object
- Prüfpunkt: 19, Z6
- Beleg: F:/tmp-suche/probelauf-d0-zwei-codex/cases/043/flaeche-de-rename_object-03af2449-dialog.png: Dialog380×154, leerer Bereich x16–363/y68–110=348×43=14964 Pixel. Gegenbild duplicate_object380×157 hat unter zwei Feldern nur8 Pixel Abstand. D8-Größennachtrag; KOORDINATION reserviert FD51 nach 13 roten Gegenproben.
- Ursache: Die gemeinsame DialogScrollArea hält auch bei kurzem Inhalt eine pauschale Mindesthöhe von88 Pixeln vor und vergrößert dadurch den leeren Rumpf.
- Vorschlag: Im bestehenden style.py-Rumpf die natürliche Inhaltshöhe als Untergrenze berücksichtigen. Ziel für die gezeigte DE-Fläche etwa32 Pixel weniger Höhe, kein fester122-Pixel-Dialog. Lange Inhalte, sechs Sprachen, größere Schrift, manuelle Nutzergröße und Rollweg erhalten.
- Wirkung beim Kunden: Ein Dialog mit nur einem kurzen Namensfeld verdeckt mehr3D-Fläche als sein tatsächlicher Inhalt benötigt.
- Stand: offen RM-737; Endgültiges Größenpaket 2e475252186598db3c9967737b4594b716cabde0 als 27a18b48c14b8d84b006c2dffa0d671f20eb66b4 auf welle4/origin integriert; alle neun Pins bytegleich, keine Merge-Auflösung. Paket 16847 bestanden/74 übersprungen/4686 abgewählt, Exit 0; dazu 141 gezielte Fälle und sechs native Komponentenfolgen/27 vom Autor gelesene Bilder. Gemeinsamer Größenanschluss 193 Fälle, Textanschluss 266 Fälle/8 abgewählt, Statik Exit 0. Tatsächliche 11/18-pt-Inhaltsschrift, vollständige Einleitung/Aktionen, manuelle Breite und notwendiges Footerminimum belegt. Gemeinsamer frischer D0-Nachweis und Endtor fehlen; ursprüngliche rote Urteile bleiben erhalten.

### FD-52 Vorschauband bleibt nach ausgeblendeter Legende zu schmal

- Art: Gestaltung
- Schwere: leicht
- Funktion: Erzeugen/Bausteine/Gegenstücke setzen …
- Prüfpunkt: 9, 19
- Beleg: Original PT/Fall036 und IT/Fall035 bleiben erhalten. Bestätigte stabile PT-Vorgeschichte: F:/tmp-suche/preview-band-diagnose-codex/history-24-f80741556/run-f80741556/cases/036/band-00-vor-originalmessung.png und band-stabil-2.png; pt-analysis.json. Band382×106 statt sizeHint557×106, Legende und Notiz abgeschnitten; sieben native Aufnahmen bytegleich, SHA256 da3a2108f2242110cf4c20fb021a39b11a154dfc8809abface23d12aaa25a8bf. Diagnosebericht vorschauband-diagnose-vorgeschichte-codex.md. IT-Vollfolge ohne abgeschlossenen neuen Zielnachweis.
- Ursache: Vorherige Vorschauabsage mit changes=False versteckt die Legende. _refresh_preview_banner ruft show_preview/place/adjustSize vor dem Wiedereinblenden auf; endgültige Legendensichtbarkeit fehlt bei der Messung. PT:557−163−12=382px. Fertige Vorschau und weitere Ereignisse heben den Zustand nicht auf; kein Beleg für eine bloß zu frühe Aufnahme oder FD46-Kartenbreite.
- Vorschlag: Endgültige Legendensichtbarkeit vor den vorhandenen show_preview/place-Aufruf setzen. Keine zweite Größenrechnung oder neue Mindestbreite. Originalvorgeschichte, kurze/lange Hinweise, echte sechs Kataloge und Inhaltsschriften prüfen; native PT-/IT-Gegenprobe erst mit freigegebenem korrigiertem C-Prüfstand.
- Wirkung beim Kunden: Die Legende zur Vorschau endet mitten im Wort; der umgebrochene Notiztext wird ebenfalls abgeschnitten. Der Kunde kann die angezeigte Vorschaufolge nicht vollständig lesen.
- Stand: offen RM-737; beobachtetes D10/RM-747, gemeinsame Vorschau D11/RM-748; Vorschauband-Paket ac6c686f14ea30a5e485012f1b14a66c537c0e3c geliefert und konfliktfrei als 64ec1b690a154ffc09374c0eac6bd481d8c03ba2 auf welle4/origin integriert. Korrigierter vollständig isolierter Lauf: 14573 bestanden/57 übersprungen/4613 abgewählt, Exit 0, alle 35 Pins unverändert. Unabhängige enge Durchsicht 24 grün, kein sperrender Produktfund. Gegen Paket nur STAND.md unterschiedlich. 28 fehlende Bash-Fälle bleiben übersprungen und sind im Endtor nachzuholen; erster unvollständig isolierter Lauf bleibt ungültig. Gemeinsame native Originalfolge und volles Endtor fehlen, kein pauschales neues D0-Urteil.

### FD-53 Gemischte Exportprobe übernimmt die Auswahl der vorherigen Szene

- Art: Fehler
- Schwere: mittel
- Funktion: finding.action:export_as_mesh
- Prüfpunkt: 9, 19
- Beleg: F:/tmp-suche/probelauf-zwei-pruefstand-fix-codex/export-native-context/cases/043/lifecycle.jsonl: Originalteilfolge decimate_mesh→export_gemischt behält selection[obj_1]; neue Szene obj_1=brep/obj_2=mesh. t314485.7226815: QFileDialog „Exportieren: 1 von 2 Körpern“; t314486.0832581: ui.handoff_receipt. Tatsächliches Ergebnis: export-native-context/cases/043/ausloeser/szene.step. Gegenbeleg export-native-diagnosis/cases/043/lifecycle.jsonl t314393.4609132: leere Auswahl, beide Körper, QMessageBox „Vor dem Export gefunden“ mit export.needs_solid; isolierter Lauf Exit0/19,25s laut C-Bericht.
- Ursache: Prüfstandfehler: Die Szenenvorbereitung übernimmt die zuvor ausgewählte ID obj_1. In export_gemischt bezeichnet dieselbe ID den exakten Quader; der Netzkörper obj_2 gehört nicht zur Auswahl. Die Produktfunktion exportiert folgerichtig nur diesen einen geeigneten Körper. Der Prüfstand wartet dagegen bis180s auf die Rückfrage für einen nicht zum Exportumfang gehörenden Netzkörper.
- Vorschlag: Fix C stellt vor dieser Exportvorbereitung über die bestehende Kundeneingabe eine leere Auswahl her und prüft den öffentlichen Zustand beziehungsweise vollständigen Exportumfang. Danach ursprüngliche decimate_mesh→export_gemischt-Folge sowie isolierten Gegenfall neu belegen. Keine Änderung am Produkt-Export, keine bloße Unterdrückung der Wartefrist oder nachträgliche Umwertung.
- Wirkung beim Kunden: Die Abnahme meldet fälschlich eine fehlende Export-Rückfrage und erreicht den beauftragten gemischten Exportfall nicht. Das beobachtete Produktverhalten ist korrekt; daraus folgt kein Kundenfehler des STEP-Exports.
- Stand: offen RM-737; Die echte Teilfolge decimate_mesh→export_gemischt leert geerbtes obj_1 per Escape und prüft den öffentlichen vollständigen Exportumfang. export.needs_solid erscheint für beide Körperarten; Produkt-Export war korrekt. FD55-Nachlauf misst den danach geöffneten Dateidialog vollständig. Paket 6d5734da599c73c0d4f7de43812a596499946b9e als 433da64bc31eb57943ad92b776c05a9174d36b91 auf welle4/origin integriert; alle 24 Pins bytegleich, keine Merge-Auflösung. Der FD56-Breitlauf bleibt mit 1 fehlgeschlagen/11178 bestanden/47 übersprungen/1635 abgewählt, Exit 1 historisch rot. Enger endgültiger Wächter-/Qt-Anschluss 96 grün; gemeinsamer Anschluss 755 bestanden/61 abgewählt plus 20 Radfälle, Statik und Prozessausgänge Exit 0. Die Commitmeldung unterzählt die tatsächlichen 20 Radfälle als 15. Gemeinsamer frischer D0-Nachweis und Endtor stehen aus; keine dritte C-Durchsicht und kein Gesamtgrün für D8/P18.

### FD-54 Große Inhaltsschrift schneidet Einleitung und Hauptknopf im Operationsdialog ab

- Art: Gestaltung
- Schwere: mittel
- Funktion: group_pattern
- Prüfpunkt: 9, 19
- Beleg: F:/tmp-suche/fix-dialoggroessen-codex/native-review-fix/01-dynamic-03.png und .json: Als Muster zusammenfassen, automatische Breite 380 px, tatsächliche Inhaltsschrift 18 pt, DPR 1,0; erster Einleitungssatz und Hauptknopf abgeschnitten. Bildurteil und 23 gelesene native Aufnahmen aus fix-dialoggroessen-codex.md vom Autor bild_d4; keine neue eigene Bildprüfung in diesem Dokumentationsnachtrag. fd54-before-realfont.log: Einleitung 96 px hoch, benötigt 128; Hauptknopf 202 px breit, benötigt 329, Textbreite 303. Basisgegenprobe fd54-base-realfont.log reproduziert den Fehler auch auf dca24076f.
- Ursache: Bei tatsächlicher großer Inhaltsschrift decken vorhandene automatische Dialogbreite, Umbruchhöhe der Einleitung und einzeilige Knopfleiste den Platzbedarf nicht. Der erste Satz endet vollständig mit „oder ändern lässt.“; der zweite Satz gehört gemäß lead_sentence bewusst in die Kurzhilfe. Der Befund ist eine Abschneidung vorhandener Texte, kein Auftrag zur Kürzung. Die Größenursache ist im Autorenbericht dokumentiert; Basis und eigener Zwischenstand betroffen.
- Vorschlag: Einleitung über den vorhandenen Umbruchträger korrekt bemessen und automatische Breite anhand des tatsächlichen Inhalts bis zur Bildschirmgrenze nachführen. Bei gewählter Nutzergröße vollständige Knöpfe und Rollweg erhalten, bei Bedarf Knöpfe untereinander beziehungsweise mit Textumbruch; Originaltexte, Rollen, Tastatur und zugängliche Namen bewahren. Sechs Sprachen sowie automatische/manuelle Größe und echte Inhaltsschrift am endgültigen Stand belegen.
- Wirkung beim Kunden: Der Kunde kann bei großer Schrift den vollständigen Hinweis und den Namen der Hauptaktion nicht lesen, obwohl beide Texte vorhanden sind. Der kürzere englische Cancel-Knopf in der alten Sonde ist eine getrennte fehlende Qt-Übersetzerinitialisierung der Sonde und kein Produktsprachfund.
- Stand: offen RM-741; Endgültiges Größenpaket 2e475252186598db3c9967737b4594b716cabde0 als 27a18b48c14b8d84b006c2dffa0d671f20eb66b4 auf welle4/origin integriert; alle neun Pins bytegleich, keine Merge-Auflösung. Paket 16847 bestanden/74 übersprungen/4686 abgewählt, Exit 0; dazu 141 gezielte Fälle und sechs native Komponentenfolgen/27 vom Autor gelesene Bilder. Gemeinsamer Größenanschluss 193 Fälle, Textanschluss 266 Fälle/8 abgewählt, Statik Exit 0. Tatsächliche 11/18-pt-Inhaltsschrift, vollständige Einleitung/Aktionen, manuelle Breite und notwendiges Footerminimum belegt. Gemeinsamer frischer D0-Nachweis und Endtor fehlen; ursprüngliche rote Urteile bleiben erhalten.

### FD-55 Wechselnde Python-Wrapperidentität verwirft einen ruhigen C++-Dateidialog

- Art: Fehler
- Schwere: mittel
- Funktion: finding.action:export_as_mesh
- Prüfpunkt: 9, 19
- Beleg: review-probelauf-fixes-nachpruefung-codex.md, FD55/RPF2-M1: tools/function_bench.py:144 id(root), Anschluss still_step:330–338 und geöffnete Befundfläche:1920–1922; HEAD 341588a5d, gebundener Stand mit 22 Pfaden, Autorenmanifest 20ac20317a86b1e7bc8d75224a2ca638d2f9743ee99c64179b105523a3005299. F:/tmp-suche/review-probelauf-fixes-nachpruefung-codex/stillness-static-dialog.json: 24 Abfragen, 18 Python-IDs, ein C++-Zeiger und eine vollständige Geometriesignatur; echter still_step verwirft die ruhige Fläche nach 0,817 s bei auf 0,8 s verkürzter Prüffrist. Derselbe Dialog mit gehaltener Hülle ist nach 0,335 s still, Sonde Exit 0.
- Ursache: Prüfstandfehler: surface_signature bindet die Flächenidentität an id(root). Für denselben von QFileDialog.getSaveFileName in C++ erzeugten Dialog liefert PySide nach Freigabe der vorigen Hülle neue kurzlebige Python-Hüllen. Die Identität ändert sich bei konstantem C++-Dialog und unveränderter sichtbarer Geometrie; der Stillstandsmerker beginnt deshalb immer wieder neu. Die unabhängige Offscreen-Sonde belegt diesen Mechanismus. Der native export-native-context-fixed-Lauf enthält keine Zeiger-/Signaturmessungen und beweist nicht nachträglich dieselbe Ursache für jeden Takt.
- Vorschlag: Die Identität lebender Qt-Flächen während der Messphase stabil halten, etwa durch Referenzen auf die aktuellen Wurzelwidgets. Echte Geometrieänderung und Flächenwechsel müssen weiter neu beginnen. C++-erzeugten Dialog ohne vom Test dauerhaft gehaltene Python-Hülle sowie echte Bewegung und Flächenwechsel gezielt gegenprüfen; Stillstandsfrist und Pflicht zur vollständigen Messung nicht lockern.
- Wirkung beim Kunden: Die Abnahme kann die wirklich geöffnete Dateidialogfläche trotz ruhiger Rechtecke als ungemessen verlieren. Dadurch bleibt der Exportfall unbegründet unvollständig. Kein Produktfehler und kein falsches Grün; vorhandene fehlende Messungen werden nicht nachträglich gutgesetzt.
- Stand: offen RM-737; Gezielte Korrektur mit 116 grünen Fällen und realem C++-Dialog, Bewegungs-/Flächenwechselgegenfällen. export-native-fd55-final Exit 0/28,01 s; 6 Layout-/5 Schrift-/9 Kontrast-/3 Feldmessungen ohne Fehler oder fehlende Messungen. Der frühere breite 11286/47/1962-Exit-0-Beleg gilt ausdrücklich für den Stand vor FD56. Paket 6d5734da599c73c0d4f7de43812a596499946b9e als 433da64bc31eb57943ad92b776c05a9174d36b91 auf welle4/origin integriert; alle 24 Pins bytegleich, keine Merge-Auflösung. Der FD56-Breitlauf bleibt mit 1 fehlgeschlagen/11178 bestanden/47 übersprungen/1635 abgewählt, Exit 1 historisch rot. Enger endgültiger Wächter-/Qt-Anschluss 96 grün; gemeinsamer Anschluss 755 bestanden/61 abgewählt plus 20 Radfälle, Statik und Prozessausgänge Exit 0. Die Commitmeldung unterzählt die tatsächlichen 20 Radfälle als 15. Gemeinsamer frischer D0-Nachweis und Endtor stehen aus; keine dritte C-Durchsicht und kein Gesamtgrün für D8/P18.

### FD-56 Synthetisches Radereignis erreicht nach Ablehnung den äußeren Rollbereich nicht

- Art: Fehler
- Schwere: mittel
- Funktion: command:edit.auto_split
- Prüfpunkt: 1, 2, 9, 19
- Beleg: auto-split-messluecke-codex-nativ.md und F:/tmp-suche/auto-split-messluecke-codex/run-probe-accepted-original/cases/043/observer.jsonl: acht Zustellungen an QToolButton Formgebung bei [5696,775], accepted_after=false, kein äußerer Empfänger, Rollwert 0 bei Maximum 274. Betriebssystem-Gegenprobe am identischen Punkt erreicht äußeren Scrollbar, 0→80, Auto Split wird sichtbar und erreichbar. fix-radweiterleitung-codex.md: Original 4 rot/10 grün, Kandidat 14 grün; beim C-Anschluss einschließlich Werkzeugvorbedingung 15 grün. F:/tmp-suche/probelauf-zwei-pruefstand-fix-codex/fd56-native-final: Originalfolge mit einem wheel_down und getroffenem Ziel, Exit 0/17,47 s, keine Fehler oder fehlenden Messungen, keine Restprozesse.
- Ursache: Prüfstandfehler in tools/function_walk.py, QtPorts.press, ursprünglicher Radzweig: QApplication.sendEvent stellt QWheelEvent unmittelbar dem getroffenen Kindwidget zu und verlässt den Zweig. Dessen ausdrückliche Ablehnung löst dabei nicht die normale Fenster-Weiterleitung zum äußeren Rollbereich aus. sendEvent-Rückgabe true ist keine Annahme. Ein vorhandener Hinweis verlagert das Ziel um 45 Pixel und macht den funktionierenden Kunden-Rollweg erforderlich. Das Produkt bewältigt diesen Zustand über die Betriebssystem-Eingabe korrekt.
- Vorschlag: Vorhandenen Qt-Fensterdispatcher QTest.wheelEvent mit korrekt aus dem globalen Punkt abgeleiteten QWindow-Koordinaten und unveränderten Zusatztasten benutzen. Keine eigene Elternschleife, kein direktes Setzen von Scrollwerten. Die Werkzeugvoraussetzung Qt ab 6.8 ausdrücklich prüfen; bei fehlender API Handlungshinweis auf die gepinnte Prüfumgebung 6.12, keine Änderung am allgemeinen App-Minimum. Annahme/Ablehnung, verschachtelte rollbare Bereiche, Bewegung beider Richtungen, Modifier und echten ursprünglichen Zielweg sichern.
- Wirkung beim Kunden: Die Abnahme meldet Auto Split fälschlich als nicht auffindbar, obwohl der normale Kundenweg mit einem Radschritt funktioniert. Kein Produktfehler und keine Aussage über die Teilungsrechnung; der verwendete passende Quader prüft Zugang und Schon-passend-Rückmeldung.
- Stand: offen RM-737; Original 4 rot/10 grün→14 grün, C-Anschluss samt Vorbedingung 15 grün. Nativer Originalweg erreicht mit einem Radereignis das Ziel, Exit 0/17,47 s. QTest.wheelEvent ist eng im bestehenden Wächter freigegeben; direkte Widget-Handler und dynamische Zustellwege bleiben rote Gegenfälle. Keine Teilungsrechnung behauptet. Paket 6d5734da599c73c0d4f7de43812a596499946b9e als 433da64bc31eb57943ad92b776c05a9174d36b91 auf welle4/origin integriert; alle 24 Pins bytegleich, keine Merge-Auflösung. Der FD56-Breitlauf bleibt mit 1 fehlgeschlagen/11178 bestanden/47 übersprungen/1635 abgewählt, Exit 1 historisch rot. Enger endgültiger Wächter-/Qt-Anschluss 96 grün; gemeinsamer Anschluss 755 bestanden/61 abgewählt plus 20 Radfälle, Statik und Prozessausgänge Exit 0. Die Commitmeldung unterzählt die tatsächlichen 20 Radfälle als 15. Gemeinsamer frischer D0-Nachweis und Endtor stehen aus; keine dritte C-Durchsicht und kein Gesamtgrün für D8/P18.

### FD-57 Auswahlkarte und XYZ-Zeile geraten nach spanischem Schriftwechsel in eine Größenschleife

- Art: Gestaltung
- Schwere: mittel
- Funktion: move_feature
- Prüfpunkt: 9, 19
- Beleg: fix-panelbreite-codex.md vom Autor bild_d10; F:/tmp-suche/fix-panelbreite-codex/native-trace-es/native.json und timeout.png. Nach echter Segoe-UI-Änderung 9→14 pt bleiben bei 19,6–20,0 s und busy=false die Rechtecke in Bewegung: cardColumn-Breite 470 bis 483 logische Pixel, _CoordinateRow-Höhe 41↔131; Rollbalken erscheinen und verschwinden. Prozess Exit 1, Quellen vor/nach 2300 Pins gleich am Korrekturmanifest eef17728e9ebb3bf387776a5a207468dd92cf370d82f609b765683b9af0e19c4. Frühere sechs native Prozesse Exit 0; ein 1×1-Pixel-Bild ist kein Sichtbeleg, Ersatz-/Diagnosenachlauf bleibt rot.
- Ursache: Echte Produkt-Geometrieänderung im Auswahlkartenlayout, während die Sitzung nicht rechnet; keine bloß wechselnde Python-Wrapperidentität wie FD55. Der Autorenbericht lokalisiert die Rückkopplung an der von augenblicklicher Sichtbarkeit abhängigen Rollbalkenreserve in der natürlichen Breitenmessung. Ein kleiner roter Höhenwechsel-Fall nimmt XYZ allein durch einen erscheinenden Balken zwölf Punkte zugesagte Breite. Die neue enge Korrektur verwendet das vorhandene Stilmaß möglicher Rollbalken unabhängig von ihrer aktuellen Sichtbarkeit; ein abschließender nativer Nachherbeleg fehlt noch.
- Vorschlag: Im bestehenden Kartenmessweg die Rollbalkenreserve und den natürlichen Querbedarf so bestimmen, dass der sichtbare aktuelle Zustand keine endlose gegenseitige Größenänderung erzeugt. Roten konkreten Schriftwechsel-Gegenfall sichern, anschließend tatsächlichen ES14-Nachlauf mit stabiler Geometrie sowie Sprach-/Rückkehrgegenfälle belegen. Nicht nur die Wartefrist verlängern, eine breite Fixbreite erzwingen oder den roten Nachlauf durch frühere grüne Fälle ersetzen.
- Wirkung beim Kunden: Die Auswahlkarte verändert nach dem Schriftwechsel fortlaufend ihre Breite, und XYZ springt zwischen Querzeile und gestapelten Feldern. Die Bedienelemente bleiben dadurch nicht ruhig; eine verlässliche Größeneinstellung und Zielwahl ist in diesem Zustand nicht belegt.
- Stand: offen RM-747; Ursprünglicher ES14-Rotbefund (Karte 470–483, XYZ 41↔131, busy=false) bleibt unverändert. FD57 jetzt auf dem vereinbarten MSI MAG271CQR in allen sechs Sprachen nativ belegt: sechs Exit 0 und 54 vom Autor gelesene Bilder; die frühere LG-Folge bleibt nur Zusatzbeleg. FD58 korrigiert den vollen Spaltenumfang beim Umbruch sowie den ungültigen Zwischenzustand indexOf=-1 und dessen Messcache. Echte Folge schmal/9 pt→groß/14 pt→schmal/9 pt vorher rot, endgültige 66 Fälle und Statik grün. Manifest 4a03df4877f1d4ae8197950c7e61a113bad8fe659d6f0952267b6481a13b3d18 bindet fünf eigene Quellen und 2300 Pins; finaler MSI-Anschluss sechs Sprachen/24 vom Autor gelesene Bilder, alle Exit 0, Root liest DE/ES zusätzlich. Finale breite Auswahl abgeschlossen: 14603 bestanden/57 übersprungen/4633 abgewählt, Exit 0, 2300 Pins unverändert. Paket 11f44ba88f6b1af704f15df45597aa7ea92ee23a auf origin/codex/d0-panel-breite geliefert, Worktree sauber; 66 gezielte Fälle und 24 finale MSI-Bilder gehören zum gebundenen Lieferstand. Integriert auf welle4/origin als e68ca22cbf84417e3b2dea2bff473627e647927f, Baum 746d0a056e6d692c8d231ad4c03939141fea5fc6; Hooks/Push Exit 0. Vier Paketpins bytegleich, panels.py bewahrt ausschließlich die disjunkten Altänderungen _and_then-Übersetzung und FD36. Root-Anschluss 17 bestanden/201 abgewählt und Statik Exit 0. Erster Fensteranschluss 212 bestanden/6 Schriftumgebungsfehler, Exit 1; nach tatsächlichem Laden von zwölf DejaVu-TTFs dieselbe unveränderte Kartendatei vollständig 66/66 grün, Exit 0. Der erste rote Lauf bleibt erhalten. Gemeinsame native Gesamtabnahme und Endtor stehen weiterhin aus. Keine Gesamtfreigabe, ursprüngliche Urteile und rote Zwischenstände bleiben erhalten.

### FD-58 Vollzeilenknopf erhält halbe Umbruchbreite und behält einen ungültigen Rasterzustand

- Art: Gestaltung
- Schwere: mittel
- Funktion: pattern_feature
- Prüfpunkt: 9, 19
- Beleg: fix-panelbreite-codex.md und KOORDINATION.md: tatsächlicher MSI-Nachlauf native-fd57-msi zeigte am vollständig überspannenden Hauptknopf unnötigen Umbruch. Reale Segoe-14-Folge 504×44→435×64→504×44; erste 12-Fälle-Gegenprobe FR/IT/PT rot (3 rot/9 grün). Isolierter 600→450→600-Fix reichte nicht: native-fd58-trace/de/07-tall-14.png zeigt Merkmal vervielfachen trotz natürlichem Textbedarf 242 in 474×64 auf zwei Zeilen. Neue echte schmal/9→groß/14→schmal/9-Folge im Original rot (ES: 1 rot/5 grün), endgültig 66 bestanden/88,00 s, Exit 0. Finales Manifest 4a03df4877f1d4ae8197950c7e61a113bad8fe659d6f0952267b6481a13b3d18; native-fd58-final sechs MSI-Sprachen/24 vom Autor tatsächlich gelesene Bilder, alle Exit 0. Pixelurteil ee045d065c8bc4e9749af8a94d5f82e54537e3f068f290f14b8590325fd27743; Root las DE/ES zusätzlich.
- Ursache: Produktfehler in app/ui/selection_operations.py, vorhandener _wrap_labels-Weg: Der dritte Hauptknopf überspannt die ganze Rasterzeile, die Textmessung teilte die Breite trotzdem wie bei den beiden Nachbarknöpfen. Während Qt die Knöpfe umhängt, wird derselbe Weg vor dem erneuten Eintragen aufgerufen; indexOf(button) ist dann -1, getItemPosition liefert keinen gültigen Spaltenumfang. Die Gegenprobe sah den ungültigen Wert 32761. Der Messcache behielt diesen Zwischenstand, weil sein Schlüssel den gültigen tatsächlichen Span nicht hinreichend unterschied.
- Vorschlag: Im vorhandenen Umbruchweg den tatsächlichen gültigen Raster-/Spaltenumfang verwenden, einen noch nicht eingetragenen Knopf abwarten und den gültigen Span im bestehenden Messschlüssel berücksichtigen. Keine zusätzliche feste Kartenbreite, zweite Layoutdefinition oder neue Timerkette. Den echten Start- und Rückweg mit tatsächlicher Schrift 9/14 und sechs Sprachen prüfen, einschließlich XYZ-Querzeile, Höhe 1200→700→1200 und unterster sichtbarer Handlung.
- Wirkung beim Kunden: Eine eigentlich ausreichend breite Hauptaktion wird unnötig zweizeilig und hoch. Beim echten Wechsel von schmaler Ansicht mit kleiner Schrift zur großen Ansicht mit großer Schrift kann dieser überhöhte Zustand trotz genügend Platz erhalten bleiben; die Karte und ihr Rollbedarf zeigen dadurch vermeidbare zusätzliche Höhe.
- Stand: offen RM-747; FD58 und mittlere Schwere vom Koordinator vergeben. FD57 jetzt auf dem vereinbarten MSI MAG271CQR in allen sechs Sprachen nativ belegt: sechs Exit 0 und 54 vom Autor gelesene Bilder; die frühere LG-Folge bleibt nur Zusatzbeleg. FD58 korrigiert den vollen Spaltenumfang beim Umbruch sowie den ungültigen Zwischenzustand indexOf=-1 und dessen Messcache. Echte Folge schmal/9 pt→groß/14 pt→schmal/9 pt vorher rot, endgültige 66 Fälle und Statik grün. Manifest 4a03df4877f1d4ae8197950c7e61a113bad8fe659d6f0952267b6481a13b3d18 bindet fünf eigene Quellen und 2300 Pins; finaler MSI-Anschluss sechs Sprachen/24 vom Autor gelesene Bilder, alle Exit 0, Root liest DE/ES zusätzlich. Finale breite Auswahl abgeschlossen: 14603 bestanden/57 übersprungen/4633 abgewählt, Exit 0, 2300 Pins unverändert. Paket 11f44ba88f6b1af704f15df45597aa7ea92ee23a auf origin/codex/d0-panel-breite geliefert, Worktree sauber; 66 gezielte Fälle und 24 finale MSI-Bilder gehören zum gebundenen Lieferstand. Integriert auf welle4/origin als e68ca22cbf84417e3b2dea2bff473627e647927f, Baum 746d0a056e6d692c8d231ad4c03939141fea5fc6; Hooks/Push Exit 0. Vier Paketpins bytegleich, panels.py bewahrt ausschließlich die disjunkten Altänderungen _and_then-Übersetzung und FD36. Root-Anschluss 17 bestanden/201 abgewählt und Statik Exit 0. Erster Fensteranschluss 212 bestanden/6 Schriftumgebungsfehler, Exit 1; nach tatsächlichem Laden von zwölf DejaVu-TTFs dieselbe unveränderte Kartendatei vollständig 66/66 grün, Exit 0. Der erste rote Lauf bleibt erhalten. Gemeinsame native Gesamtabnahme und Endtor stehen weiterhin aus. Keine Gesamtfreigabe, ursprüngliche Urteile und rote Zwischenstände bleiben erhalten.

### FD-59 Innere Fallfrist des Dateiprüfstands lässt untergeordnete Prozesse zurück

- Art: Fehler
- Schwere: mittel
- Funktion: file_acceptance.run
- Prüfpunkt: 9, 19
- Beleg: probelauf-zwei-pruefstand-fix-codex.md, delivery-fd59.json und F:/tmp-suche/koord-codex/merge-fd59/evidence.md: vier echte Windows-Ketten aus Launcher, Interpreter und Helfer, Modi normal/nonzero/timeout/exception. fd59-red: 4 rot, Exit 1; Timeout ließ Helfer PID 73148 zurück, Ausnahme PID 64760. Normalende und Exit 7 waren bereits korrekt, ihre roten Assertions betrafen fehlende explizite Startoptionen. fd59-green: 4 grün, Exit 0; fehlende Restprozesse per Betriebssystem geprüft. Endgültiger Paket- und Integrationsanschluss jeweils 142 bestanden/5 Fensterfälle abgewählt, Exit 0, Statik Exit 0. Vorhandener count_new_windows auf vier echten Ketten: 4 grün, Befehl und Zähler Exit 0, 0 neue sichtbare Fenster/0 Konsolenfenster. Prozess-/Profilmarken in fd59-process-records.json; eigene Restprozesse bei Lieferung leer.
- Ursache: Prüfstandfehler in tools/file_acceptance.py, run(): Die innere Fallfrist beendete nur den direkt gestarteten Launcher. Auf Windows blieb dessen untergeordnete Interpreter-/Helferkette bei Timeout und Ausnahme im Warten bestehen. Die öffentliche Prozessgruppe war an dieser inneren Grenze noch nicht angeschlossen. Der neue Import von app.core.process benötigt zudem den eigenen ROOT unbedingt zuerst in sys.path, auch wenn dort vorher ein fremder Eintrag stand.
- Vorschlag: Vorhandene process_group_options(no_window=True), no_error_dialogs und terminate_process_tree im bestehenden run-Rumpf verwenden. Den zugehörigen Baum bei Timeout oder Ausnahme beenden, solange seine Kante besteht; keine zweite Prozessverwaltung. ROOT vor dem neuen Kernimport unbedingt vorn eintragen. Tatsächliche Exitwerte, Ausnahme, Timeoutstatus, Falldateien, Wiederaufnahme und sechs weitergegebene Profile unverändert erhalten. Normale Rückkehr und Exit 7 als Gegenfälle belassen.
- Wirkung beim Kunden: Ein abgebrochener Prüffall endet nur scheinbar vollständig. Zurückgebliebene Interpreter oder Helfer können nachfolgende Fälle und Prozessnachweise verunreinigen. Das ist ein Prüfstandfehler; hieraus wird kein Fehler des Produkt-Exportwegs oder der eigentlichen Anwendung abgeleitet.
- Stand: offen RM-737; FD59 und mittlere Schwere vom Koordinator vergeben. Eng korrigiert und geliefert als bc376abc0868141a10c1f5edad26798993f38f6d, integriert auf welle4/origin als c9505aac22bc4cb213a7ebe64980c1f41de0d59d. Beide Pins bytegleich zum Manifest bc6dbce3961d165b1a6fb4b420e210887d01d2f47a504432fbab532d02f53d47; keine Merge-Auflösung. Paket und Root jeweils 142 bestanden/5 Fensterfälle abgewählt, Statik und Ausgänge Exit 0. Vier echte Ketten/0 sichtbare Fenster/0 Konsole belegt, eigene Restprozesse leer. Die automatische 97-Dateien-Auswahl ist nur protokolliert; übrige unveränderte C-Nachweise werden ausdrücklich wiederverwendet. Kein neuer breiter Lauf und keine dritte C-Durchsicht. Gemeinsamer frischer D0-Nachweis und vollständiges Endtor bleiben offen; D10 inzwischen als 11f44ba88f6b1af704f15df45597aa7ea92ee23a geliefert, inzwischen als e68ca22cbf84417e3b2dea2bff473627e647927f auf welle4/origin integriert; gemeinsame native Gesamtabnahme und Endtor offen; keine vorgezogene Gesamtfreigabe.

### FD-60 Native Zugriffsverletzungen brechen den frischen Fensterlauf ab

- Art: Stabilität
- Schwere: schwer
- Funktion: resize_hole, place_on_bed und die zugehörigen Sprachflächen
- Prüfpunkt: 9, 16
- Beleg: F:/tmp-suche/probelauf-d0-frisch-codex auf 6d063ef064: 48 Fälle, 41 Prozesse Exit 0, sieben Zugriffsverletzungen in 001, 002, 032, 038, 039, 042 und 047. Originaldaten und alle drei Stufe-A-Berichte unverändert erhalten. fix-projektwechsel-crash-codex.md und fd60-binding-codex.md binden die nachfolgenden einzelnen CDB-Sonden und die unabhängige Quellenlesung.
- Ursache: Die begrenzten CDB-Sonden zeigen den NULL-Zugriff in PySide::SignalManager::retrieveMetaObject und einen falschen Nicht-QObject-Wrapper vom Typ QWidgetItem. Der native Widgetabbau in weiterlebenden FeaturePanel-Layouts ließ dessen gehaltene Python-Hülle gültig. Die beiden betroffenen Abbauwege clear und keep_measure_group lösen das Widget jetzt vorher öffentlich aus dem tatsächlichen Layout, auch bei verschachteltem Layout oder externem Host. removeWidget entwertet die Itemhülle; Elternschaft und wiederverwendete Widgets bleiben erhalten. Kein Hardwareurteil.
- Vorschlag: Den belegten Einzelabbau über layout_lifetime.detach_from_layout vor hide/deleteLater führen; keine globale Invalidierung, zusätzliche Lebenszeitreferenz oder unterdrückte Ausnahme. Die ursprünglichen sieben Absturzfälle auf der gemeinsamen Fassung erneut prüfen.
- Wirkung beim Kunden: Der echte Anwendungsprozess endet ohne nutzbaren Rückweg. Die fehlenden Folgeaufnahmen und Urteile sind kein bestandenes Ergebnis; der Gesamtlauf kann nicht abgenommen werden.
- Stand: offen RM-737; geliefert als f507043f9bab355ba781c88278811decd7977d6c und integriert als fda4f687cc367c16371961ab128ee0a59e542438. Neun reproduzierende Lebensdauerfälle und fünf Folgeaufbauten grün; 14.717 betroffene Kernfälle bestanden, 48 übersprungen, 4.658 abgewählt, Exit 0. Root hat die neun Fälle erneut bestanden; spätere gemeinsame 27-, 71- und 126-Fall-Anschlüsse grün. Unabhängige Durchsicht ohne offenen Fund. Original001 am echten Fenster grün; die anderen sechs alten Absturzfälle, vollständiger gemeinsamer Fensterlauf und Endtor bleiben offen. Alte Abstürze und abgebrochene Diagnosen bleiben unverändert erhalten.

### FD-61 Lagebefund zeigt Millimeter trotz gewählter Zollanzeige

- Art: Fehler
- Schwere: mittel
- Funktion: place_on_bed
- Prüfpunkt: 9
- Beleg: F:/tmp-suche/probelauf-d0-frisch-codex/cases/005/flaeche-zoll.png und function.json: Kopf, Objektbaum und Status in Zoll; ausgewählter Befund zeigt Überstand 10,00 mm. fix-befund-einheiten-codex.md bindet die Diagnose, ursprüngliche 48 roten Umrechnungsfälle und weitere 30 rote Auswahl-/Previous-Gegenfälle aus dem Reviewfund BE-01.
- Ursache: Kanonische geometrische Werte excess/gap/needed wurden bereits im Kern als vollständiger mm-Text geliefert und später nicht als Anzeigegröße formatiert. Bei synthetischen Gruppen wechselte die Identität mit den formatierten Mitgliedstexten. Der echte Einstellungsweg setzte außerdem den gelesenen Reiter und offene Körperknoten zurück; frühere künstliche Tabproben bildeten diesen Kundenweg nicht ab.
- Vorschlag: Ausschließlich vollständige kanonische geometrische mm-Werte über den bestehenden Längenformatter anzeigen; beim Einheitenwechsel den Bericht über seinen öffentlichen Pfad erneuern. Auswahl, Details und Voriger-Stand-Zuordnung an rohe vollständige Mitgliedsidentitäten einschließlich Duplikaten binden. Freitext, Versionszahlen und Slicerwerte unverändert behandeln.
- Wirkung beim Kunden: Der Bericht widerspricht der gewählten Maßeinheit. Ein unvollständiger Fix würde zusätzlich die ausgewählte Sammelzeile und ihren Bearbeitungszustand verlieren.
- Stand: offen RM-745; geliefert als 5d11646c6fac45e31d212eef78e206e4747d4b30, integriert als c6789f91c05fe3a46e6a62439e5a5e0e229e8ea5. 222 enge Fälle, sieben bestehende Qt-Anschlüsse und 23 neue Quellenleser grün; zuvor 1.627 gebundene kopflose Teilfälle. Der Reiter-/Baumfix hat 24 echte Rotfälle und sechs positive Kontrollen; nach einer formalen Test-Callbackkorrektur die betroffenen 18 erneut grün. Gemeinsame Anschlüsse mit 27, 71 und zuletzt 126 Fällen grün, Statik und enge Durchsicht ohne offenen Fund. Auf dem gemeinsamen Stand ece8988f2bdc60436a7bc327ee1b77e8e794a4b7 ist der echte sechssprachige mm/in/mm-Weg vollständig grün: sechs Prozesse Exit 0, zwölf Settingswechsel, alle 18 echten MSI-Aufnahmen gelesen. Bericht, Details, Auswahl und Körperklappzustand bleiben erhalten; Quellen und acht Nutzerprofildateien unverändert, alle eigenen Prozesse beendet. Gemeinsamer finaler D0-Nachweis bleibt offen.

### FD-62 Kontrastmessung liest am Hauptknopf die falsche Textfarbe

- Art: Fehler
- Schwere: mittel
- Funktion: Prüfstand für Hauptaktionen
- Prüfpunkt: G6
- Beleg: fix-farbmessung-codex.md und review-farbmessung-codex.md; gleiche 13 Kontrastgegenfälle am Ausgang 9 rot / 4 grün, am Fix 13 grün. Die ursprünglichen Aufnahmen und Urteile des frischen D0-Laufs bleiben unverändert.
- Ursache: Die generische Farbrolle des Widgets entspricht bei einem über den Qt-Stil gezeichneten Hauptknopf nicht zwingend der tatsächlich verwendeten Beschriftungsfarbe und ihrem aktuellen Zustand.
- Vorschlag: Die tatsächliche zustandsabhängige Qt-Beschriftung messen; nur eindeutig deckende Textpixel übernehmen. Fehlende oder mehrdeutige Messung offen lassen. Den Hintergrund weiterhin am echten Bildschirm lesen, keine gute Themenfarbe als Ersatz für eine schlechte Eigenfarbe einsetzen.
- Wirkung beim Kunden: Die Abnahme kann ausreichenden Kontrast falsch beanstanden oder einen tatsächlichen Kontrastfehler verdecken. Der Produktstil und die Kontrastschwelle dürfen durch die Messkorrektur nicht verändert werden.
- Stand: offen RM-737; geliefert als 599526b10e930381a17e734a00708c0c130f27db und konfliktfrei auf welle4/origin als f08927d636f88bca0d31517ec3722e28ef3869f6 integriert. Vollständiger Baum und fünf Quellpins stimmen mit der geprüften Lieferung überein. 1.831 Anschlussfälle bestanden, 2 übersprungen, 41 abgewählt; Ruff, Format, Projekt-Mypy und unabhängige Durchsicht grün. Zusätzlicher direkter Werkzeug-Mypy behält acht basisgleiche Altfehler. Gemeinsamer nativer Messnachweis und Endtor offen.

### FD-63 Maßgruppe zeigt fünf eigenständige Vorderseitenfelder

- Art: Einfachheit
- Schwere: mittel
- Funktion: resize_hole
- Prüfpunkt: 2, E5
- Beleg: F:/tmp-suche/probelauf-d0-frisch-codex/cases/001/02-flaeche.png sowie Fälle 004 und 007 mit Zoll und Skalierung. Jeweils Durchmesser, Änderungsumfang, Tiefe, Materialtoleranz und separater Sammelhaken vorne. Originalbilder und Feldlisten in fix-massgruppe-front-codex.md gebunden.
- Ursache: Der Adapter der Merkmalsfelder verliert die Vorder-/Rückseitenzuordnung des Operationsschemas. Die Maßgruppe stellt außer Koordinaten alle Felder nach vorn und zählt den zusätzlichen Sammelhaken nicht gegen das Feldbudget.
- Vorschlag: Schemametadaten durch die gemeinsame Feldauskunft transportieren und rechts wie im Bild verwenden. Gewöhnliche Bohrung mit Durchmesser, Tiefe und gegebenenfalls Sammelhaken; Druckkorrektur und gewöhnlicher Änderungsumfang hinten. Fachlich vorbelegtes Mitnehmen des Einlaufs bleibt als bewusste vierte Eingabe sichtbar. Werte, Bedingungen, Wiederverwendung und Undo erhalten.
- Wirkung beim Kunden: Fünf gleichrangige Eingaben überladen die Maßgruppe und verletzen die Vorderseitengrenze. Ein pauschales Verstecken könnte dagegen eine wirksame Vorbelegung oder die Reichweite der Sammeländerung verschleiern.
- Stand: offen RM-741; gemeinsames Paket FD7/16/63/64 als f333e5ba7d0248646ef7e4c16f0434573366e604 geliefert und als b863815593f2e8ec43e73db7957e6828b77ea60c integriert. Die ursprünglichen 43 Fälle waren 38 rot / 5 grün; nach Fix und reproduziertem Theme-Fixture-Gegenfall MG-M1 alle 44 grün. Dazu 30 bestehende Anschlüsse und 2.861 Kernfälle grün, 97 abgewählt. Gemeinsame Integrationen mit 71 und 126 Fällen grün; Statik und Nachprüfung ohne offenen Fund. Keine neue Definition in den vier großen Altdateien. Die echte Sechssprachenfolge auf bc2d5e20c376e5d9003c1c1d8058033a93ca427f (native-runner-v3/runs/run-20261013T210714907Z) ist abgeschlossen: jeweils regulär Exit 0 und 62/62 Bedingungen, insgesamt 372. Alle 192 Originalbilder wurden einzeln gelesen; sämtliche 51 eigenen Prozessidentitäten beendet. Die ab Bild021 abgeschnittene Statuszeile bleibt im Original dokumentiert und wurde getrennt unter FD75 kausal behoben. Keine nachträgliche Umwertung der alten Bilder. Gemeinsamer endgültiger D0-Lauf und Tor bleiben offen.

### FD-64 Maßgruppenfelder verlieren die Wirkungshilfe ihres Schemas

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: resize_hole
- Prüfpunkt: 8, V3
- Beleg: Dieselben frischen Maßgruppenbilder und Feldprotokolle wie FD63; Änderungsumfang und Materialtoleranz ohne Tooltip und zugängliche Beschreibung, Sammelhaken ohne Tooltip, Durchmesser/Tiefe nur mit Maßherkunft. Diagnose und genaue Adapterstellen in fix-massgruppe-front-codex.md.
- Ursache: ActionField transportiert die Schemahilfe nicht. Der gemeinsame Feldkonfigurator ersetzt die Feldhilfe durch Herkunft; Beschriftungen übernehmen diesen unvollständigen Stand. Erklärung einzelner Auswahlwerte ersetzt keinen Wirkungssatz des Feldes.
- Vorschlag: Die gemeinsame Schemahilfe durchreichen und bei Wiederverwendung an Beschriftung, Editor und fokussierte Innenfelder binden; Herkunft ergänzend erhalten. Beide Sammelhaken bekommen dieselbe übersetzte Wirkungshilfe. Die unklare Materialbezeichnung bleibt dem bereits bestehenden FD7 zugeordnet.
- Wirkung beim Kunden: Direkt am Eingabefeld fehlen die Erklärung der Änderung und entsprechende Auskünfte für Hilfstechnik. Der Nutzer sieht teilweise nur, woher das Maß stammt, nicht was seine Änderung bewirkt.
- Stand: offen RM-741; mit FD7/16/63 als f333e5ba7d0248646ef7e4c16f0434573366e604 geliefert und als b863815593f2e8ec43e73db7957e6828b77ea60c integriert. Vier neue Textschlüssel in allen fünf Katalogen; Wirkungshilfe auch an Beschriftung, fokussierten Innenfeldern, Ausdrücken und Radiusdarstellung. Dieselben 44 engen, 30 bestehenden, 2.861 Kern- und gemeinsamen 71-/126-Fall-Anschlüsse wie FD63 grün. Alle 18 echten Feldhilfen in sechs Sprachen nach gehaltenen Kartenzügen mit Inhalt und tatsächlichen Ereignisspuren belegt. Die echte Sechssprachenfolge auf bc2d5e20c376e5d9003c1c1d8058033a93ca427f (native-runner-v3/runs/run-20261013T210714907Z) ist abgeschlossen: jeweils regulär Exit 0 und 62/62 Bedingungen, insgesamt 372. Alle 192 Originalbilder wurden einzeln gelesen; sämtliche 51 eigenen Prozessidentitäten beendet. Die ab Bild021 abgeschnittene Statuszeile bleibt im Original dokumentiert und wurde getrennt unter FD75 kausal behoben. Keine nachträgliche Umwertung der alten Bilder. Gemeinsamer endgültiger D0-Lauf und Tor bleiben offen. Kein zusätzlicher Fund für den bereits unter FD7 erfassten Begriff.

### FD-65 Schriftprüfung lehnt die vertragliche Primärschrift ab

- Art: Fehler
- Schwere: mittel
- Funktion: Prüfstand für Hauptaktionen
- Prüfpunkt: G4
- Beleg: fix-farbmessung-codex.md und die neue test_function_primary_fonts.py: gleiche 31 Schrift-/Schemafälle am Ursprung 26 rot / 5 grün, am Fix 31 grün; bestehender Schriftaufnahmeanschluss zusätzlich grün. Tatsächliche gebündelte Fontfamilien und Metriken sind zugesichert.
- Ursache: Die Prüfung unterschied die ausdrücklich erlaubte halbfette Grundschrift des tatsächlichen Hauptknopfs nicht hinreichend von beliebigen Schriftabweichungen. Die Primärrolle und reale Anwendungsfamilie fehlten als typgeprüfte Messwerte.
- Vorschlag: Optionale boolesche Primärrolle und reale Schriftfamilien kompatibel erfassen. Nur nachgewiesene Primärbeschriftung in der tatsächlichen Grundfamilie und vereinbarten Größe/Gewichtung entlasten; gewöhnliche Knöpfe, fremde Familien und falsche Größen bleiben Gegenfälle. Alte Protokolle weiter lesen.
- Wirkung beim Kunden: Die Abnahme fordert eine Änderung an einer bereits vertraglichen Hervorhebung oder verdeckt echte Schriftabweichungen durch eine zu breite Ausnahme.
- Stand: offen RM-737; gemeinsam mit FD62 als 599526b10e930381a17e734a00708c0c130f27db geliefert und als f08927d636f88bca0d31517ec3722e28ef3869f6 integriert. Derselbe gebundene Anschluss, Statik und unabhängige Durchsicht. Gemeinsame native Messung und Endtor bleiben offen; keine nachträgliche Umwertung der versiegelten Alturteile.

### FD-66 Gegenstückdialog behält unnötige Anfangshöhe

- Art: Gestaltung
- Schwere: leicht
- Funktion: Erzeugen/Bausteine/Gegenstücke setzen …
- Prüfpunkt: 19, Z6
- Beleg: Frische FR-/IT-Sprachflächen und fd66-diagnose-codex.md. Native FR-Originalfolge bei gleichem Inhalt und gleicher Breite: anfangs 341 × 353, nach einmal Auf-/Zuklappen 341 × 322; user durchgehend None und keine notwendige Rollleiste. Root hat beide tatsächlichen Bildschirmbilder gelesen; Sichtbeleg root-viewed-fd66-original.json unter F:/tmp-suche/koord-codex.
- Ursache: Die Anfangsmessung las eine durch vorübergehende AsNeeded-Rollleisten noch auf 297 statt 309 Pixel reduzierte Viewportbreite und erzeugte zusätzliche Textzeilen. Beim passiven Nachmessen wurde außerdem der Platz einer Querleiste ohne echten Rollweg als verdeckter Inhalt gezählt. sizeHint und _hidden_height berücksichtigen jetzt den tatsächlich verfügbaren maximalen Ausschnitt; nötige oder dauerhaft gesetzte Leisten bleiben erhalten. Keine irrtümliche Erkennung einer Nutzergröße.
- Vorschlag: Im bestehenden natürlichen Größenwunsch die nach Abbau vorübergehender Rollleisten tatsächlich verfügbare Breite zugrunde legen; keine feste 31-Pixel-Korrektur. Gleichen geschlossenen Inhalt vor und nach Klappzyklus vergleichen, manuelle Größe, echte große Schrift und tatsächlich nötige Rollleisten erhalten.
- Wirkung beim Kunden: Der Dialog verdeckt mehr Modellfläche als sein vorhandener Inhalt benötigt. Die zusätzliche echte Herkunftszeile in FR ist notwendiger Inhalt und bleibt erhalten.
- Stand: offen RM-747; als e7ca1cc953ee0ccd2c543db07f7f4186297c9c1d geliefert, mit b863 als 34ec9526d5fafdda4acc8ddd40f8dedbadcb5cd2 zusammengeführt und auf welle4 als a100dd99f9d960b5164c12231459c788221207c3 integriert. Endgültiger gleicher Vertrag am Ursprung 15 rot / 39 grün, am Fix 54 grün; 142 bestehende Größenfälle sowie 126 gemeinsame Integrationsfälle grün. Breiter Lauf historisch Exit 1: 14.777 bestanden, 57 übersprungen, 4.703 abgewählt und genau ein fehlender API-Zugang im alten Scroll-Testdouble. Nach dessen minimaler Ergänzung derselbe Test mit allen acht unveränderten Zusicherungen grün; übrige Fälle unverändert übernommen. Statik und enge Durchsicht grün. Native FR-/IT-Folgen regulär grün, 14 tatsächliche Bilder gelesen: Anfang und Wiederzuklappen jeweils FR 341 × 322, IT 306 × 322; Nutzermaße, echter Rollweg und Fußaktionen erhalten, ursprüngliche Textflächen pixelgleich. Frühere rote Test-/Sondenläufe bleiben erhalten. Gemeinsamer finaler D0-Lauf und Endtor offen.

### FD-67 Aufgeklappte Maßgruppenfelder verschwinden unter der Knopfzeile

- Art: Fehler
- Schwere: mittel
- Funktion: resize_hole im Bild, Weitere Werte
- Prüfpunkt: 19, Z6
- Beleg: F:/tmp-suche/fix-massgruppe-front-codex/native-runner-v3/runs/run-20261013T173601513Z/de/003-resize-rueckseite-vor-hover.png auf ece8988f2bdc60436a7bc327ee1b77e8e794a4b7, von Autor und Root tatsächlich gelesen. Nach Öffnen bleibt die Maßgruppe 304 × 232, der Scrollviewport 286 × 156; der Inhalt wächst auf 272 × 330. entrance_mode liegt unter dem Viewport, der Hit-Test trifft placement_measure_accept. Kein sichtbarer Rollbalken trotz abgeschnittenem Änderungsumfang und freiem Bildraum.
- Ursache: Der vorhandene PlacementFlow-Gruppenfilter verarbeitet den geänderten Größenbedarf nach LayoutRequest nicht. Die feste Höhe und ScrollBarAlwaysOff bleiben vom geschlossenen Zustand erhalten, auch nach weiteren Qt-Ereignisrunden.
- Vorschlag: Größenbedarfsänderungen über den bestehenden Gruppenfilter nach dem Qt-Layoutschritt an die vorhandene Größenrechnung anschließen; selbst ausgelöste Layoutschleifen, Gruppentausch und Abbau berücksichtigen. Aufklappen und Zuklappen gegenprüfen, bei echtem Platzmangel erreichbar rollen und Fußaktionen sichtbar halten.
- Wirkung beim Kunden: Die Rückseite lässt sich öffnen, ihre Werte sind aber verdeckt und mit dem Zeiger nicht erreichbar. Eine Vergrößerung auf pauschale Maße würde unnötig Modellfläche verdecken.
- Stand: offen RM-741; Größenfix als f6b0f53f2e61b18d7436940e830604aa80ce0ca1 geliefert und als 4521cf8ff0d4f623c070feda6b67cb937b0cb7a7 auf welle4 integriert, vollständiger Baum identisch. Neun gehärtete Fälle in sechs vor Fensterbau eingestellten Sprachen einschließlich echter Klappen-/Fußtexte und Lebensdauer grün; Statik und enge Durchsicht ohne offenen Produktfund. Der bestehende hohe-Karten-Reihenfolgefall besteht auf Original und Fix allein und scheitert auf beiden nach demselben Dark-Vorgänger; keine neue Regression behauptet. Auf-/Zuklappen, Feldeingabe und erreichbare Fußaktionen in allen sechs Sprachen nativ belegt. Die echte Sechssprachenfolge auf bc2d5e20c376e5d9003c1c1d8058033a93ca427f (native-runner-v3/runs/run-20261013T210714907Z) ist abgeschlossen: jeweils regulär Exit 0 und 62/62 Bedingungen, insgesamt 372. Alle 192 Originalbilder wurden einzeln gelesen; sämtliche 51 eigenen Prozessidentitäten beendet. Die ab Bild021 abgeschnittene Statuszeile bleibt im Original dokumentiert und wurde getrennt unter FD75 kausal behoben. Keine nachträgliche Umwertung der alten Bilder. Gemeinsamer endgültiger D0-Lauf und Tor bleiben offen. Beide ursprünglichen roten Maßgruppenläufe bleiben erhalten; kein Umgehen der verdeckten Felder im Prüfablauf.

### FD-68 Druckbett-Raster verschwindet im hellen Thema

- Art: Gestaltung
- Schwere: mittel
- Funktion: Druckbett in der 3D-Ansicht
- Prüfpunkt: 19
- Beleg: Nutzerhinweis und tatsächliche Vorheraufnahme F:/tmp-suche/fix-bettraster-hell-codex/native-before-v3/01-hell.png auf 4521cf8ff0d4f623c070feda6b67cb937b0cb7a7. Root und Autor haben das Bild gelesen: beleuchtete Bettfläche #B8C0C9 gegen Rasterpixel #BBC3CE, Linien kaum erkennbar. Identische Szene, Kamera, Fenster und Skalierung im Nachherordner native-after-v3; Haupt- und Nebenlinien deutlich sichtbar. Keine behauptete Textkontrast-Normverletzung.
- Ursache: Raster und Bettkante nutzten dieselbe sehr helle Farbrolle; 0,35 Deckkraft nähert die Linienfarbe zusätzlich an die beleuchtete Bettfläche an. Themenweitergabe und Tiefenabstand sind vorhanden; kein belegter Tiefenfehler. Die Linien hatten keine getrennte Gewichtung zur Orientierung.
- Vorschlag: Bestehende Rasterlinien mit eigener bed_grid-Farbrolle und disjunkten Haupt-/Nebenlinien alle fünf Abstände zeichnen. Positionen, Zeichenraster, Bauraum und Treffverhalten erhalten; Hell/Dunkel/Hell am echten Fenster vergleichen.
- Wirkung beim Kunden: Auf dem hellen Druckbett fehlt eine verlässlich erkennbare räumliche Orientierung. Die Korrektur lässt das Raster erkennen und hält den Körper visuell im Vordergrund.
- Stand: offen RM-737; fünf Pfade als bc4fe912a828cbe072f51011910d36dfd2ea5dec normal geliefert und als 438efade21e7e3ad42ca7da993a631118607cb66 auf welle4 integriert, vollständiger Baum identisch. Sieben gezielte Fälle, Ruff/Format/mypy und enge Durchsicht grün. Native V3-Vorher- und Nachherfolge jeweils regulär Exit 0, alle sechs Aufnahmen vom Autor, beide Hell-/Dunkelpaare zusätzlich vom Root gelesen; eigene Prozesse beendet. Sechs Profile vor Appimport umgebogen, kein separater Hashvergleich aller echten Nutzerprofile. Die zwei früheren roten Scratchfolgen bleiben erhalten. Automatische breite Auswahl von 261 Dateien nicht ausgeführt und bis zum gemeinsamen Entwicklungstor ausstehend; endgültiger D0-Nachweis offen.

### FD-69 Bettmaßzahlen bleiben im hellen Thema äußerst blass

- Art: Gestaltung
- Schwere: leicht
- Funktion: Maßbeschriftung des Druckbetts
- Prüfpunkt: 19
- Beleg: F:/tmp-suche/fix-bettraster-hell-codex/native-after-v3/01-hell.png. Root und unabhängiger Bildprüfer sehen 100 bei etwa 1049/158, 50 bei 769/232 und 0 bei 429/324 nur äußerst schwach auf dem hellen Grund. Das neue Raster behebt die Zahlenfarbe nicht. Die genaue Kontrastquote wurde hier nicht gemessen.
- Ursache: Viewport._draw_one_bed verwendet für LabelStyle.text_colour weiterhin _bed_colour, also die Farbe der Bettkante (#bfcad8 im hellen Thema). Der bestehende Labelrenderer passt den Kontrast nicht automatisch an. Im dunklen Thema läuft derselbe Pfad mit #5a6472.
- Vorschlag: Ausschließlich die Maßzahlen über eine geeignete vorhandene Textrolle zeichnen und im Themenwechsel erneuern; Bauraumfarbe, Texte, Geometrie und Positionen erhalten. Hell und Dunkel am selben nativen Zustand nachlesen.
- Wirkung beim Kunden: Die Orientierungslinien sind sichtbar, die zugehörigen Maßzahlen bleiben aber schwer lesbar.
- Stand: offen RM-737; Bild- und Quellbefund bestätigt. Die vorhandene Textrolle _sketch_label_colour ersetzt ausschließlich die Bettzahlenfarbe. Original zwei falsche Textrollen rot/sechs Rasterkontrollen grün, nach Korrektur acht Fälle grün; Hell/Dunkel/Rückweg sowie unveränderte Positionen, Größe und Bauraumfarbe. Enge Erstlesung ohne Fund. Statik grün, normal geliefert als 1e37ebc101cd18e42ed628d4d1310e17d786724d und auf welle4 als d4e7305f3f9cb75e0b2ea019530c4c66f48f94a7 integriert. Native Endfolge grips-after-front-final regulär Exit 0, alle 17 Originalbilder einzeln gelesen, Bettzahlen in Hell und Dunkel lesbar. Gemeinsamer endgültiger D0-Nachweis und Tor bleiben offen. Keine behauptete numerische Normverletzung.

### FD-70 Griff- und Vorschauflächen verdecken die gewählte Bohrung

- Art: Gestaltung
- Schwere: leicht
- Funktion: resize_hole im Bild
- Prüfpunkt: 19, G9
- Beleg: design-d0-oberflaeche-codex.md, tatsächliches helles Bild F:/tmp-suche/fix-massgruppe-front-codex/native-runner-v3/runs/run-20261013T173601513Z/de/003-resize-rueckseite-vor-hover.png und dunkler Originalfall016. Orange Griffkörper, flächige Markierung und Achspfeile überdecken die gewählte Öffnung stärker als die übrigen Bohrungen; Bildurteil mit begründeter Sichtprüfung, kein gemessener Kontrastwert.
- Ursache: Zwei gefüllte pickbare SlotHandle-Zylinder mit Deckkraft 1,0, zusätzliche nicht pickbare face-handle-Scheibe mit 0,6 und Merkmalsfüllung mit 0,45 liegen in der gewählten Öffnung übereinander. outlined bezeichnet die Schnittkontur und entfernt die Griffkörper nicht. Die vorhandene Größenbegrenzung der Zylinder verhindert diese perspektivische Überdeckung nicht.
- Vorschlag: Ruhende Füllungen gezielt zurücknehmen, überfahrene/gehaltene Griffe und wirkliche laufende oder wartende Entwürfe klar erhalten. Bestehende Netze, Bezugspunkte und positive Deckkraft im Pickpfad bewahren. Direkten take_press ohne Hover, wiederverwendeten Vorschauaktor, Abbruch und Wiederaufbau prüfen; keine kleineren Trefferflächen als Gestaltungstrick.
- Wirkung beim Kunden: Gerade die zu bearbeitende Öffnung lässt sich schlechter erkennen als die ungewählten. Die Gestaltung soll Lochrand und Änderung zugleich sichtbar halten, bei unverändert gut treffbaren Griffen.
- Stand: offen RM-741; als 48adcd982f5f0f72b37da4d4f9fbdada76ad03d8 normal geliefert, drei eigene Pfade. Original zehn Fälle rot/eine Positivkontrolle grün; enge Erstlesung fand GL-01: Außenrelease hielt den Griff kräftig, der alte Test verdeckte es durch ein zweites Leave. Neue Außenfälle vorher zweimal rot, nach Korrektur der Zustandsübernahme am tatsächlichen Loslasspunkt fünfzehn Fälle grün, einschließlich Innenrelease, direktem Lochdruck, echten Gizmoschritten und Abbau. Ruff/Format/mypy grün; keine neue Definition im Viewport. Nach nativer Gegenprobe wurde zusätzlich die zweite OIT-Mischung des Vordergrundknopfs gezielt geschlossen; Vordergrundflächen verwenden reguläres blend; Raumtransparenz bleibt weighted_blend, die Deckkraft bleibt erhalten. Normaler Abschluss 1e37ebc101cd18e42ed628d4d1310e17d786724d auf welle4 als d4e7305f3f9cb75e0b2ea019530c4c66f48f94a7 integriert. Native Endfolge grips-after-front-final mit 17 einzeln gelesenen Originalbildern regulär Exit 0: aktive Griffe, Umrisse, Auswahl und Escape-Rückweg in Hell/Dunkel sichtbar. Die dabei aufgefallenen blassen Maße wurden separat unter FD73 behoben. Keine pauschale Abnahme aller Griffzustände; endgültiger gemeinsamer D0-Nachweis und Tor bleiben offen. Die Schwere folgt der ausdrücklichen G9-Grenze leicht; der erste rote Fundleser wegen mittel bleibt erhalten.

### FD-71 Maßkartenzüge halten den impliziten Qt-Mausempfänger fest

- Art: Fehler
- Schwere: mittel
- Funktion: Maßkarte am Titel oder freien Hintergrund verschieben
- Prüfpunkt: 8, 19
- Beleg: fix-measure-card-drag-codex.md und fix-massgruppe-front-codex.md; echte QWindow→QWidget-Transportgegenfälle für Titel und freie Fläche. Beide erreichen das richtige Dragziel, danach erhält am Original trotzdem das alte QLabel beziehungsweise Karten-QWidget den buttonlosen Move statt QComboBox. Zwei Fälle vor dem Fix rot, endgültige Helferdatei mit 36 Fällen grün. Native Folge run-20261013T201120471Z belegt passende Cursorziele, aber ToolTip/MouseMove weiter an der Maßkarte; ein Einzelhover ohne vorherigen Zug erreichte dagegen Feld und sichtbare Hilfe.
- Ursache: Der globale Ereignisfilter konsumierte auch den QWindow-Release. Dadurch erreichte die Freigabe den Qt-Transport nicht, der den impliziten button_down-Empfänger löscht. Ein ausdrückliches grabMouse verwendet der Helfer nicht.
- Vorschlag: Den aktiven Zug erst bei QWidget-Empfängern verarbeiten. QWindow-Transport unverändert passieren lassen; nach dem Loslassen muss die echte folgende Mausbewegung den neuen Empfänger erreichen. Eingabefelder, Außenrelease, Abbau und aktueller Vorfahrenvertrag bleiben erhalten.
- Wirkung beim Kunden: Nach dem Verschieben reagieren Feldhilfen und Hoverzustände nicht mehr am tatsächlich überfahrenen Eingabefeld. Die schwebende Karte lässt sich bewegen, stört danach aber die normale Mauszustellung.
- Stand: offen RM-741; als c902aed139c900ffcb5f577a6a01d26b302013d4 normal geliefert und als 8831b33e94c786667d229756ebfff7ca52d18e4d auf welle4 integriert. Vollständiger Integrationsbaum identisch zum Autorenbaum, keine manuelle Auflösung. 36 Fälle, Ruff/Format/mypy und enge unabhängige Durchsicht grün; normale Hooks/Autopush bestätigt. Vollständige echte Sechssprachenfolge run-20261013T210714907Z auf bc2d5e20c376e5d9003c1c1d8058033a93ca427f jeweils regulär Exit 0 und 62/62 Bedingungen, zusammen 372. Alle zwölf gehaltenen Titel-/Flächenzüge erreichen den freien Ort, je vier Movepunkte auf QWindow und QWidget mit gedrückter linker Taste und Release ohne gedrückte Taste; alle 18 Feldhilfen erreichen nach dem Zug das richtige Feld und zeigen den passenden echten Tooltip. Abbrechen, Einzel-/Sammelübernahme und Undo bestanden. 32 Produktpins unverändert, alle 51 eigenen Prozessidentitäten beendet. Getrennter Aufnahmefehler FD75 betrifft ab Bild021 den unteren Statusrand, nicht die dokumentierten Züge und Hilfen. Gemeinsamer frischer D0-Nachlauf und Endtor bleiben offen; frühere rote Läufe erhalten.

### FD-72 Vordergrundkanten übernehmen den Zeichenvertrag ihrer Fläche nicht

- Art: Fehler
- Schwere: leicht
- Funktion: 3D-Renderer, Fläche mit Vordergrundkanten
- Prüfpunkt: 19
- Beleg: review-grifflesbarkeit-codex.md und test_front_overlay_alpha.py; tatsächlicher öffentlicher add_surface-Aufruf mit SurfaceStyle(keep_in_front=True, show_edges=True), echten pygfx-Materialien und gesperrten Grafikadapteranforderungen. Vollständige Flächen-/Rückseiten-/Kantenprüfung vor Korrektur acht fachliche Fehler und acht Positivkontrollen, danach dieselben 16 Fälle grün. Kein bestehender Kundenaufrufer mit genau beiden Schaltern und keine native Ansicht mit verdeckten Kanten in dieser engen Prüfung nachgewiesen.
- Ursache: Das eigene show_edges-Material übernimmt weder den abgeschalteten Tiefentest noch die festgelegte Vordergrundqueue der zugehörigen Fläche. Die Lücke bestand bereits vor der Alphakorrektur von FD70.
- Vorschlag: Ausschließlich die zwei vorhandenen Materialargumente aus keep_in_front ableiten; Raumkanten behalten Tiefentest und automatische Queue. Deckkraftwechsel, force_opaque, Rückseitenanteile sowie erhaltene Geometrie und Pickflags gegenprüfen.
- Wirkung beim Kunden: Der öffentliche Renderer-Vertrag erlaubt, dass Kanten einer ausdrücklich im Vordergrund gezeichneten Fläche verdeckt werden. Eine solche konkrete Kundenansicht ist hier nicht belegt; kein Abbruch und keine Modelländerung behauptet.
- Stand: offen RM-737; minimaler Zweizeilenanschluss am vorhandenen Kantenmaterial mit 16 bestandenen CPU-Materialfällen, Ruff/Format/mypy und enger unabhängiger Rückprüfung. Rendererpin90dcf946605d3bb856eab4d85f69fedb96cd1e932dc75756b2777437970a4b23 und Testpin756007bb490aa5185a671df1148443d1747e96a82cb675943f8b467617e69bde. Keine neue Definition im großen Renderer. Regulär als 1e37ebc101cd18e42ed628d4d1310e17d786724d geliefert, auf welle4 d4e7305f3f9cb75e0b2ea019530c4c66f48f94a7 mit identischem Autorenbaum integriert; normale Hooks/Push bestätigt. Gemeinsame breite Abnahme steht aus. Der erste Testentwurf mit einer falschen starren Raumqueueannahme bleibt separat erhalten und ist kein Produktgegenbeleg.

### FD-73 Freistehende Griffmaße verschwinden auf hellen Modellflächen

- Art: Gestaltung
- Schwere: leicht
- Funktion: Zum Langloch ziehen, Maßzahl im Bild
- Prüfpunkt: 19, G9
- Beleg: Original F:/tmp-suche/fix-bettraster-hell-codex/grips-after-front-final/dark-05-gehaltener-zug.png auf 1e37ebc101cd18e42ed628d4d1310e17d786724d, von Autor, Root und unabhängigem Prüfer einzeln gelesen. Das freistehende Maß „16,03 mm“ liegt sehr blass auf dem hellblauen Hoverkörper; im hellen Bild ebenfalls grau. Keine gemessene Kontrastquote. FD70s aktive Griffe und Umrisse sind auf demselben Bild bereits kräftig; getrennter Textfund.
- Ursache: Viewport._label_gizmo hängt _slot_length_text an den gemeinsamen gizmo_labels-Aktor für X/Y/Z/L und wählt _object_colour als Textfarbe, im dunklen Thema #b9c4d0, im hellen #78828e. 13 Pixel, fett, immer sichtbar, ohne Hintergrund oder Umriss. Der vorhandene Textmaterialweg nutzt volle Deckkraft, keinen Tiefentest und seine Vordergrundqueue; keine belegte erneute OIT- oder Griffdeckkraftursache.
- Vorschlag: Vorhandenes kontrastierendes Text-/Fensterfarbpaar mit deckendem LabelStyle-Hintergrund verwenden. Die gemeinsame Wirkung auf Achsen-/L-Buchstaben ausdrücklich mitprüfen, bei Themenwechsel erneuern und am echten gehaltenen Zustand in beiden Themen nachlesen. Keine neue Farbrolle, API, Geometrie oder Definition im großen Viewport.
- Wirkung beim Kunden: Die aktuelle Länge steht zwar im Eingabefeld, lässt sich direkt am Griff aber nur schwer ablesen. Die Lesbarkeit darf nicht von der zufälligen Farbe der Fläche darunter abhängen.
- Stand: offen RM-741; vier ursprüngliche Stilgegenfälle rot, danach alle 20 Griffprüfungen grün. Der leichte Leerfeldfund ist im bestehenden GfxLabels.build mit tatsächlicher Textsichtbarkeit behoben; ein CPU-Gegenfall rot plus eine Positivkontrolle, danach alle 18 Material-/Labelprüfungen grün, einschließlich Nachbarn, Anker, Sichtbarkeit und adopt/build. Erste Lieferung 471291463eb6833f6e6dc92a6640716f47315b92 integriert als 425dfc1db347a8ff8c63d36894e06d0701154f91. Die anschließenden echten Bilder belegten noch L-Felder über kleinen Knöpfen. Gezielter Nachfix verwendet öffentliche Knopfhüllen und vorhandene Projektion/Layoutrechnung, hält endliche Ausgangsanker bei nicht platzierbaren Feldern und schützt den laufenden Gizmo-Zug vor dem Kameratimer. Acht Originalgegenfälle und ein gesonderter Bewegungsanschluss rot, endgültige bestehende Datei 29/29 grün, Statik und enger unabhängiger Abschluss ohne Fund. Normal geliefert als a408a0620524eb58946d947a8a98a4d2e7090f10 und auf welle4/origin als 26b66508e19aafa4ec5b9f9519e8f0a7f65aeacd integriert; vollständiger Baum autorengleich, keine Auflösung, normale Hooks/Push Exit 0. Native Folge grips-after-fd73-anchors-final auf diesem sauberen Autorenkopf regulär Exit 0/39,26 s; alle 19 Originalbilder einzeln gelesen, Root zusätzlich Hell04 und Dunkel05. L neben freien gelben Knöpfen, gehaltene/wartende Maßzahl, XYZ/S und Leerfeld-Rückweg in Hell/Dunkel lesbar. Zehn App-Pins unverändert, alle sechs eigenen Prozessidentitäten beendet. Keine echte zusätzliche Zoom-/DPR2-Folge oder allgemeine Überlappungsfreiheit behauptet. D0-Nachlauf und Tor bleiben offen.

### FD-74 Prüfstand prüft den Knopftreffer vor der nötigen Mausbewegung

- Art: Fehler
- Schwere: mittel
- Funktion: Funktionsprüfstand, Bereitschaft vor einem Knopfklick
- Prüfpunkt: 8
- Beleg: fix-massgruppe-front-codex.md, native-runner-v3/runs/run-20261013T203830058Z. Die echte DE-Folge erfüllt 22 Bedingungen einschließlich gehaltener Maßkartenzüge und dreier Feldhilfen. Danach liegt ein tatsächliches qtooltip_label über dem künftigen Abbrechen-Ziel. click_button fragt widget_under vor QtPorts.press und dessen öffentlicher Mausbewegung ab und lehnt ab. Kein Abbrechen-Press, kein Nachbedingungsfehler und kein Timeout. Cursorort und Entstehungstakt dieses späteren Tooltips wurden am Abbruch nicht gemessen; keine solche Behauptung.
- Ursache: Die bisherige Bereitschaft prüft den zukünftigen Treffpunkt, ohne zuvor den tatsächlichen Mausort dorthin zu bewegen und Qt den natürlichen Zustellungs-/Tooltipabbau zu erlauben. Ein verschachteltes processEvents in click_button würde den bereits vorgemerkten StepMachine-Folgeschritt vor dem aktuellen Klick ausführen können.
- Vorschlag: Im bestehenden Walk.stable zuerst öffentlich zum aktuellen Ziel bewegen und im nächsten regulären Takt Ziel, Sichtbarkeit, Aktivierung, Geometrie und Treffer frisch prüfen. Bei geändertem Ziel erneut bewegen. Benannte und per Getter aufgelöste Knöpfe benutzen denselben Weg; click_button bleibt abschließender synchroner Zustands-/Trefferwächter. Vorhandene Fristen unverändert, keine gezielte Tooltipunterdrückung.
- Wirkung beim Kunden: Die Abnahme kann einen normal bedienbaren Kundenweg vor dessen Klick abbrechen. Ein kaputter Abbrechen-Knopf der Anwendung ist damit nicht belegt.
- Stand: offen RM-737; drei Pfade als f749bdc61f386e2c4f7825432d17b00cc51e3b77 normal geliefert und mit identischem Autorenbaum als bc2d5e20c376e5d9003c1c1d8058033a93ca427f auf welle4 integriert, keine manuelle Auflösung. Ein echter ursprünglicher benannter Tooltipfall rot, danach elf neue Qt-Fälle und 25 bestehende Walk/FakePorts-Anschlüsse grün. Ruff/Format und reguläres mypy über 388 Quellen grün. Ein zusätzlicher Werkzeug-mypy-Aufruf meldet exakt dieselben fünf belegten Altfehler an Original und Fix, kein pauschales Werkzeug-mypy-Grün. Unabhängiger enger Review ohne neue Funde, finale drei Pins bestätigt. Ganze echte Sechssprachenfolge run-20261013T210714907Z regulär jeweils Exit 0, insgesamt 372/372 Bedingungen: nach drei Feldhilfen tatsächlicher Abbrechen-Press und Release, danach Einzel-/Sammelübernahme und Undo. 32 Produktpins unverändert, alle 51 eigenen Prozessidentitäten beendet. Aufnahmegrenze am späteren Statusrand separat FD75; keine Umwertung alter Bilder. Gemeinsamer D0-Nachlauf und Tor stehen aus. Direkte synchrone Prüfstandsaufrufer bleiben ausdrücklich einphasig.

### FD-75 Erneute Fensterplatzierung trennt gemessene Clientfläche und Aufnahme

- Art: Fehler
- Schwere: mittel
- Funktion: Funktionsprüfstand, wiederholter Aufbau auf demselben Bildschirm
- Prüfpunkt: 9, 19
- Beleg: fix-massgruppe-front-codex.md und native-runner-v3/runs/run-20261013T210714907Z auf bc2d5e20c376e5d9003c1c1d8058033a93ca427f. Alle sechs Sprachen laufen funktional regulär durch. Bis Bild020 stimmen QWidget-Client/contentsRect und grabWindow mit 2560 × 1369 überein; ab dem nächsten FunctionFlow.prepare melden Client und contentsRect 2560 × 1392, die PNGs bleiben 2560 × 1369. Die letzten 23 Pixel einschließlich Statuszeile fehlen sichtbar, unabhängig von D4, D8 und Root gelesen. Kein bloßer Unterschied zwischen Fensterrahmen und Client und kein bewiesenes Abschneiden am physischen Monitorrand.
- Ursache: place_window ruft bei jeder Vorbereitung erneut setGeometry(availableGeometry) und showMaximized auf, auch wenn das Fenster bereits auf demselben Schirm maximiert ist. Der zweite Aufbau überschreibt damit den gespeicherten QWidget-Clientumfang. Die native Gegenprobe bestätigt einen unveränderten Win32-Rahmen und tatsächlichen Client von 2560 × 1369; ausschließlich QWidget und contentsRect springen beim zweiten Originalaufbau auf 2560 × 1392. Kein physischer Monitorbeschnitt.
- Vorschlag: Wiederholte Maximierung am bereits gewählten Schirm idempotent behandeln; beim ersten Aufbau, Monitorwechsel oder Wechsel zur ausdrücklichen Größe den nötigen Normalzustand herstellen und den bisherigen Platzierungsvertrag erhalten. Aufnahme und tatsächliche Clientfläche gegenprüfen, einschließlich vollständiger Statuszeile. Kein Zuschneiden, keine erfundenen Sollpixel und keine Änderung der Bildschirm-/DPI-Untergrenzen.
- Wirkung beim Kunden: Prüfstandsmessung und sichtbarer Bildbeleg beschreiben unterschiedliche Flächen. Die bereits innerhalb des Bilds belegten Kartenaktionen bleiben gültig, eine vollständige Fensterabnahme kann daraus nicht entstehen. Kein Fehler am eigentlichen Kunden-Statusinhalt belegt.
- Stand: offen RM-737; enger Vorwärtsfix in function_setup.py und zwei vorhandenen Testdateien. Fünf kausale Originalgegenfälle rot, danach dieselben fünf grün; vollständiger bestehender Setup-Anschluss mit 28 Fällen grün. Die echte Offscreen-Qt-Grenze zeigt am Original QWidget 800 × 800 statt zuvor 796 × 796 sowie eine ausdrückliche Sollgröße ohne passenden QWindow-Client; am Fix stimmen QWidget, contentsRect und QWindow überein. Ruff, Format und reguläres mypy (388 Dateien) grün, unabhängige Durchsicht ohne Fund; automatische Auswahl 103 nur ermittelt. Normal geliefert als a0d5ae491f8e348a2a4c37fc2e57c348fe0922a9. Echte MSI-Gegenprobe auf Root bc2d: run-20261013T213709788Z regulär Exit 1 wegen genau der zweiten Clientabweichung, keine Aufbau-/Fristfehler. Fix auf a0d5: run-20261013T213806356Z regulär Exit 0; beide Aufbauten QWidget/contentsRect/QWindow/Win32-Client/PNG durchgehend 2560 × 1369, Statuszeile vollständig. Alle vier Originalbilder einzeln gelesen, Root beide zweiten Bilder; Rahmen gleich und sämtliche 32 Quellenpins pro Lauf unverändert. Alle 15 beziehungsweise 13 eigenen Prozessidentitäten beendet, Lease zurück. Native Vergleichsverdichtung SHA5406E4E6D98EE92A67CF0E4394D688587473A6711D174995ADBC667BE34E0B7D. Nach normalem Autorenmerge 37dcea59f023a3112769c7ed5fc22d35b98276fb auf welle4/origin als 9dc38e79f253a92efde6df55e1dec3c79d64a9f6 integriert; vollständiger Baum autorengleich, keine Auflösung, normale Hooks/Push Exit 0. Endgültiger D0-Lauf und Tor bleiben offen.

### FD-76 Textmessung beschädigt HTML-Entities und literale Ampersands

- Art: Fehler
- Schwere: mittel
- Funktion: Funktionsprüfstand, Textnormalisierung vor der Breitenmessung
- Prüfpunkt: 9
- Beleg: review-v4-textnormalisierung-codex.md; frisches V4-ready.json von Fall001 auf 2ec37b23bbc18bd76fc604c794ecd0c7231adaec. Die tatsächlich vollständig sichtbare Vorschaulegende wird als „nbsp;+ Hinzugefügtnbsp;nbsp;nbsp;nbsp;- Entferntnbsp;“ mit Bedarf301/Breite145 und cut=true vermessen. Sie ist in diesem Fall nur im Zusatzartefakt enthalten, nicht im öffentlichen function.json; kein bereits erzeugtes falsches P9-Urteil dieses Falls behauptet.
- Ursache: _text_of entfernt jedes & vor der HTML-Normalisierung durch QTextDocument. Dadurch verliert &nbsp; seinen Entity-Anfang; auch Qt-Mnemonics und escaped && werden undifferenziert behandelt.
- Vorschlag: Vorhandenen Textweg trägergerecht normalisieren; RichText unbeschädigt parsen, Mnemonic-Marker nur bei geeigneten Trägern entfernen und literale Ampersands erhalten. Echte Label-/Knopfgegenfälle und weiterhin roter P9-Kontrollfall bei zu geringer Breite.
- Wirkung beim Kunden: Die Abnahme kann eine vollständig sichtbare Beschriftung fälschlich als abgeschnitten einstufen. Der Text der Anwendung selbst ist in diesem Beispiel korrekt.
- Stand: behoben `f4c9bd26c`; Originalrot 14 Fälle, am Fix 16 grün; Text-/Aufnahmeanschlüsse grün; in welle4 `7eebc67dd`.

### FD-77 Navigationsabschluss akzeptiert ein halb abgeschnittenes Eingabefeld

- Art: Fehler
- Schwere: mittel
- Funktion: Gemeinsame Anleitungsnavigation und Funktionsaufnahme, Filamentwähler
- Prüfpunkt: 9, 19
- Beleg: filament-picker-sichtbarkeit-codex.md; frischer Fall032/EN auf 2ec37b23bbc18bd76fc604c794ecd0c7231adaec. Original flaeche-en-filament.picker-0afd58ad.png von Root, D10 und B einzeln gelesen. „No filament assigned yet“ am unteren Rand der Rollkarte abgeschnitten, Hauptfensterstatus vollständig. Ziel1339..1367 gegenüber zuvor protokolliertem Rollrand1354; Mitte1352 treffbar. Keine nachträglich erfundene vollständige Clipkettenmessung.
- Ursache: guide_targets._scroll_needed prüft ausschließlich die Mitte gegen alle Scrollsichtflächen. Walk bestätigt den stabilen Mittelpunkt und Treffer; der nachfolgende Stillstand prüft keine Vollsicht. So wird die teilweise abgeschnittene Fläche regulär aufgenommen.
- Vorschlag: Passend große Felder im vorhandenen gemeinsamen Navigationsweg bis zu ihren vertikalen Kanten freilegen, innere und äußere Scrollbereiche berücksichtigen. Vollsichtkontrolle mit halb abgeschnittenem Original, oberem Rand, verschachtelten Bereichen, vollständig sichtbarem Feld, übergroßem Container und Scrollanschlag. Keine privaten Scrollbaränderungen im Kundenweg oder verlängerten Fristen.
- Wirkung beim Kunden: Eine technisch erreichbare Feldmitte wird als brauchbare Endansicht behandelt. Eine unbedienbare Produktliste ist damit nicht belegt; kein erneuter FD75-Statusbeschnitt.
- Stand: behoben `46c628ef9`; gegen die alten Module 20 rot (16 fachlich, 4 Vertrag), gezielt 92/92 grün; betroffene Auswahl 14 783 grün, Exit 0; in welle4 `64e389936`. Native EN-Nachheraufnahme von Fall 032 offen RM-737.

### FD-78 Fachfelder in Druckvorbereitungswegen haben unvollständige Hilfen

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: tool:analysis, tool:split, finding.action:sketch.pick_plane, finding.action:generate_again, finding.action:choose_printer, finding.action:open_print_settings
- Prüfpunkt: 8, V3
- Beleg: bild-final-d8-codex.md und F:/tmp-suche/bild-final-d8-codex/2ec37b23b/FD78-hilfen-entwurf.md; frische italienische und deutsche Fälle 047/043 auf 2ec37b23. Flächenprotokolle und einzeln gelesene Originalbilder sind mit vollständigen Hashes gebunden. AnalysisBar/Analysewahl, SplitBar/Anzahl/Form/Vorbereitung und OperationDialog/Typ sind die ursprünglichen fünf Felder. Hinzu kommen „Beschreibung“ im tatsächlich geöffneten Generator und „Werte mitgeben“ im vorgeschalteten Herstellerprofilhinweis. Letzterer erscheint über zwei Inventarzeilen, ist aber derselbe Träger und zählt einmal. Alle tatsächlichen Inventarzeilen gehören D8.
- Ursache: Die Rohaufnahme zeigt an sieben unterschiedlichen Feldern eine leere zugängliche Beschreibung; Analyseauswahl, Generatorbeschreibung und Werte-Haken haben zusätzlich keine Kurzhilfe. An den vier übrigen Feldern ist ein erklärender Tooltip vorhanden. Im Slicerhinweis ist der erklärende Satz sichtbar; seine technische Zuordnung an die Hilfekanäle fehlt. Der konkrete Quellenanschluss ist noch nicht diagnostiziert; keine globale Ursache behauptet.
- Vorschlag: Vorhandene übersetzte Wirkungssätze an die zugängliche Beschreibung der tatsächlichen Eingabefelder binden. Für die drei Felder ohne Tooltip den passenden vorhandenen Wirkungssatz ermitteln und beide Hilfekanäle anbinden. Gleiche Träger, sechs Sprachen, Titelwortüberschneidung und tatsächliche Feldhilfe prüfen. Sichtbare Erklärung erhalten; nachgelagerte Drucker-/Einstellungsdialoge sind durch diese Aufnahmen nicht nachgewiesen.
- Wirkung beim Kunden: Die Erklärung der Feldwirkung fehlt in einem erforderlichen Hilfekanal, bei drei Feldern auch beim Überfahren. Eine Bildschirmleser-Ausführung wurde hier nicht durchgeführt; kein fehlender Erklärungstext im gesamten Slicerhinweis behauptet.
- Stand: offen RM-745; von FD10/11/12/50/64 und Systemdialogen, reinen Ausgaben sowie verdeckten Nachbarfeldern abgegrenzt. Eigenständiger leichter Fund für das bereits beauftragte Kundenpaket D8. Kein Quellfix und kein Nachherbeleg; der ursprüngliche Bild- und Rohbefund bleibt erhalten.

### FD-79 Maßkartenzug umgeht den gemeinsamen Ereignisverteiler

- Art: Fehler
- Schwere: mittel
- Funktion: Maßkarte am Titel oder freien Hintergrund verschieben
- Prüfpunkt: 8, 19
- Beleg: review-v4-textnormalisierung-codex.md; affected-01, regulär Exit 1 mit genau drei Wächterfehlern bei 11.320 bestandenen Fällen. test_no_module_hangs_its_own_filter_on_the_application beanstandet measure_card_drag.py:205. Quellen und Wächter sind bytegleich zum Integrationskopf 2ec37b23; Bindung affected-failure-binding.json SHA a35fb03fa78f12d6b88459b35e34494e5d9f0493f5c5733a7d179c936409b6bb.
- Ursache: Die Geste installiert einen eigenen Anwendungsfilter, obwohl app.ui.app_events einen gemeinsamen, nach Ereignisarten gefilterten Verteiler bereitstellt.
- Vorschlag: Nur während der Geste die benötigten Ereignisarten über listen anmelden und über forget abmelden. Lokale Kartenfilter, QWidget-Schranke aus FD71, einmalige Verarbeitung und vollständigen Abbau erhalten.
- Wirkung beim Kunden: Zusätzliche globale Zustellung umgeht den bestehenden Architekturvertrag. Eine konkrete Verlangsamung wurde in diesem Lauf nicht gemessen; keine neue Leistungszahl behauptet.
- Stand: behoben `8f4e89fd0`; Wächter am alten Stand rot, am Fix grün; 16 neue Verhaltensfälle gegen die Originalklasse rot, am Fix grün; in welle4 `7eebc67dd`.

### FD-80 Maßkartenzug sichert seinen globalen Mauszeiger nicht gegen jeden Ausgang

- Art: Fehler
- Schwere: mittel
- Funktion: Maßkarte am Titel oder freien Hintergrund verschieben
- Prüfpunkt: 8, 19
- Beleg: Derselbe gebundene Lauf; test_a_state_that_is_set_is_taken_back_on_every_path beanstandet measure_card_drag.py:181. setOverrideCursor steht vor der Bewegungsarbeit ohne finally-/with-Absicherung.
- Ursache: Ein asynchroner Zug verändert den globalen Cursorstapel und nimmt ihn nur über den gewöhnlichen _finish-Weg zurück. Der Ausnahmeweg nach dem Setzen ist nicht abgesichert; eine fremde spätere Stapelposition hat keine eigene Zuordnung.
- Vorschlag: Das vorhandene Pattern für widgetgebundene asynchrone Cursor verwenden, falls der echte gehaltene Zug außerhalb der Karte dadurch vollständig erhalten bleibt. Vorherigen eigenen oder geerbten Zustand wiederherstellen; fremde globale Overrides, Release, Escape, Fokusverlust, Reset und Lebensdauerenden gegenprüfen. Fehlerwege müssen tatsächlich aufräumen.
- Wirkung beim Kunden: Der Cursorzustand ist nicht für jeden Ausgang abgesichert. Ein konkret beim Kunden stehengebliebener Cursor wurde hier nicht beobachtet; der statische Regelverstoß ist bestätigt.
- Stand: behoben `8f4e89fd0`; Zeiger am Druckempfänger statt Override, Rückgabe auf jedem Ausgang (Escape, Hide, Fokus-/Fensterverlust, Reset, Empfängertod, Ausnahme) gegen die Originalklasse rot, am Fix grün; in welle4 `7eebc67dd`.

### FD-81 Maßkartenprüfungen importieren private Helfer aus anderen Testmodulen

- Art: Fehler
- Schwere: leicht
- Funktion: Prüfanschlüsse der Maßkarte und Platzierung
- Prüfpunkt: 8, 19
- Beleg: Derselbe gebundene Lauf; test_test_files_do_not_import_private_names_from_each_other findet in test_measure_card_placement.py fünf private Querimporte aus drei test_*-Modulen.
- Ursache: _begin, _drop, _heading, _rounds und _layout dienen mehreren Tests, liegen aber bei einzelnen Testverbrauchern statt im vorhandenen gemeinsamen tests/ui_helpers.py.
- Vorschlag: Diese Helfer samt benötigtem internem Maushelfer einmalig in das bestehende Hilfsmodul verschieben und alle Verbraucher auf sprechende öffentliche Namen umstellen. Keine Duplikate, kein neues Modul und keine Abschwächung des Wächters.
- Wirkung beim Kunden: Kein unmittelbarer sichtbarer Produktfehler belegt; die Prüfstruktur koppelt Testmodule über private Implementierung und verletzt ihren bestehenden Vertrag.
- Stand: behoben `8f4e89fd0`; Wächter der privaten Querimporte am alten Stand rot, am Fix grün; in welle4 `7eebc67dd`.

### FD-82 Testdoubles der Flächenplatzierung kennen den Maßkartenzug nicht

- Art: Fehler
- Schwere: mittel
- Funktion: Prüfanschlüsse der Flächenplatzierung
- Prüfpunkt: 19
- Beleg: Betroffener Lauf am Fixbaum von FD-79–81 (`F:\tmp-suche\fpf-liefern-claude\affected-20261014-050245.txt`): 88 rot, alle in `tests/test_surface_placement.py`, `AttributeError: 'types.SimpleNamespace' object has no attribute '_measure_drag'` an `placement_flow.py:5560`; am unveränderten `welle4` `d5b2c51df` gleich rot.
- Ursache: `0036e21ea` führte `_measure_drag.update_room` in `PlacementFlow.redraw` ein; die zwei Doubles der Datei wurden nicht nachgezogen.
- Vorschlag: Beide Doubles tragen einen stummen Zug wie ihre übrigen Maßhelfer.
- Wirkung beim Kunden: Kein Produktfehler; 88 Prüfungen der Werkzeugausrichtung an der Fläche erreichten ihre Zusicherung nicht, das Entwicklungstor wäre rot.
- Stand: behoben `0df73f13d`

### FD-83 Tooltipfall des Prüfstands hängt von der Reihenfolge ab

- Art: Fehler
- Schwere: mittel
- Funktion: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 19
- Beleg: `tests/test_function_bench_window.py::test_button_probe_moves_away_from_a_real_tooltip_before_testing_coverage[wortschatz|knopf]` ist allein grün und nach `test_a_double_click_reaches_a_list_as_a_double_click` im selben Prozess rot (`verdeckt: feature:resize_hole … qtooltip_label`), am unveränderten `2ec37b23b` genauso (`F:\tmp-suche\fpf-liefern-claude\order-b.txt`, `order-c.txt`).
- Ursache: offen; der Doppelklick hinterlässt Zustand, nach dem der Tooltip die Mausbewegung überdauert.
- Vorschlag: Ursache am Ablauf belegen und an der Wurzel beheben, Gegenprobe in derselben Datei in beiden Reihenfolgen.
- Wirkung beim Kunden: Kein Produktfehler belegt; ein Fenstertest wird im Release-Tor reihenfolgeabhängig rot.
- Stand: behoben `001effdcd`; Tooltipfall nach dem Doppelklickfall am alten Stand rot, am Fix in beiden Reihenfolgen grün, neue Zusicherung ohne gedrückte Taste; in welle4 `fe8f5bcd7`.

### FD-85 Abhakliste lässt einen offenen Fund hinter einem älteren behobenen verschwinden

- Art: Fehler
- Schwere: mittel
- Funktion: Prüfanschlüsse des Prüfstands
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
- Stand: offen RM-737

### FD-87 Die Maßgruppe springt im Fehlfall an den Plattenrand

- Art: Gestaltung
- Schwere: leicht
- Funktion: `resize_hole`
- Prüfpunkt: 7, G8
- Beleg: Lauf 001/03-uebernommen.png gegen 001/04-fehlfall.png bei gleicher Kamera; Ausschnitte `F:\tmp-suche\urteile-d04-claude\crops\001-03-ueberblick.png` und `001-04-ueberblick.png` (d04 Nr. 2).
- Ursache: offen; fest steht, dass die Karte mit der Ablehnung höher wird und danach ohne Übergang an anderer Stelle steht.
- Vorschlag: Bei wachsender Karte die gewählte Lage halten und nur so weit verschieben, wie der Platz verlangt; der Wechsel mit Übergang aus `motion`.
- Wirkung beim Kunden: Das Feld, das er gerade korrigiert, springt an eine andere Stelle des Bilds.
- Stand: offen RM-741

### FD-88 Die Ablehnung der Maßgruppe steht dreimal da

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `resize_hole`
- Prüfpunkt: 7, E5
- Beleg: Lauf 001/04-fehlfall.png: derselbe Satz unter dem Feld, über der Knopfzeile der Maßgruppe und in der Statusleiste (d04 Nr. 2).
- Ursache: offen; Feldablehnung, Hinweis der Maßgruppe und Statuszeile setzen je denselben Satz. Verwandt mit FD-32 (Sperrgrund zweimal), andere Stelle.
- Vorschlag: Der Satz steht am Feld; Maßgruppe und Statusleiste wiederholen ihn nicht.
- Wirkung beim Kunden: Derselbe Satz dreimal lenkt vom Feld ab, das er ändern muss.
- Stand: offen RM-741

### FD-89 „seit dem letzten Schritt“ meldet auch eine geänderte Rechengrundlage

- Art: Fehler
- Schwere: mittel
- Funktion: Statusleiste, Materialverbrauch und Druckdauer
- Prüfpunkt: 6
- Beleg: `F:\tmp-suche\urteile-d04-claude\crops\status.png`: Szene `merkmal.hole.exakt` ohne Änderung erst 11 g · 20 min (037–042 countersink_hole), später 8,9 g · 14 min mit „−2,2 g seit dem letzten Schritt“ (detect_region, alle Sprachen), ohne dass ein Schritt dazukam; dieselbe Ausgangsszene 18 g · 32 min in 004, 007, 016, 019 gegen 14 g · 23 min in 001 (d04 Nr. 3 b, c).
- Ursache: am Code belegt, dass die Zahl nicht nur nach einem Schritt neu entsteht: `_update_facts` läuft nach jeder Auswertung und noch einmal, wenn die Druckgrundlage des gewählten Prozesses eintrifft (`main_window.py:26382`), dann mit anderen wirksamen Einstellungen; `PrintFacts.show_estimate` vergleicht jede neue Schätzung mit der vorigen und nennt die Differenz „seit dem letzten Schritt“ (`facts.py:125–149`). Dass im Lauf genau die Grundlage die Zahl verschob, ist naheliegend, nicht gemessen.
- Vorschlag: Die Differenz nur zwischen zwei Dokumentständen mit derselben Rechengrundlage bilden; ändern sich die Einstellungen, wird der Vergleichswert still neu gesetzt. Die Zahl erst zeigen, wenn die wirksamen Einstellungen feststehen, oder als vorläufig kennzeichnen.
- Wirkung beim Kunden: Die Zeile meldet eine Ersparnis durch einen Schritt, den es nicht gab, und dieselbe Szene zeigt je nach Zeitpunkt andere Gramm und Minuten.
- Stand: offen RM-737

### FD-90 Die Zahlenzeile der Statusleiste wird abgeschnitten

- Art: Gestaltung
- Schwere: leicht
- Funktion: Statusleiste, Materialverbrauch und Druckdauer
- Prüfpunkt: 9
- Beleg: Lauf 001/01-vorher.png „14 g ·“; detect_region 037–042: Summe links abgeschnitten („· 14 min“), die deutsche Differenz endet in „Schrit…“ (`F:\tmp-suche\urteile-d04-claude\crops\status.png`, d04 Nr. 3 a).
- Ursache: offen; Statusmeldung und Zahlenzeile teilen sich die Statusleiste, und die Breite der Zahlenzeile folgt ihrem Text nicht verlässlich.
- Vorschlag: Mindestbreite aus beiden Texten der Zeile; gekürzt wird zuerst die Statusmeldung.
- Wirkung beim Kunden: Material und Dauer sind nur zum Teil lesbar.
- Stand: offen RM-749

### FD-91 Die Kopfzeile kürzt den Druckernamen trotz freier Fläche

- Art: Gestaltung
- Schwere: leicht
- Funktion: Kopfzeile, Druckerprofil
- Prüfpunkt: 9, Z6
- Beleg: Lauf 007/flaeche-skalierung.png (`F:\tmp-suche\urteile-d04-claude\crops\007-kopf-rechts.png`) und 013/flaeche-skalierung.png bei 1920 × 1009: „Elegoo …rbon 2 · FDM“, links davon breite freie Fläche (d04 Nr. 4, d10 Nr. 2).
- Ursache: offen.
- Vorschlag: Das Profilfeld der Kopfzeile nach seinem Inhalt bemessen und erst kürzen, wenn die Zeile voll ist; der volle Name im Tooltip.
- Wirkung beim Kunden: Auf der kleinsten Arbeitsfläche ist der gewählte Drucker nicht lesbar.
- Stand: offen RM-749

### FD-92 Die Bettmaßzahlen folgen der Anzeigeeinheit nicht

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: Druckbett in der 3D-Ansicht
- Prüfpunkt: 9
- Beleg: Lauf 004/flaeche-zoll.png (`F:\tmp-suche\urteile-d04-claude\crops\004-bett.png`): „0“, „100“ ohne Einheit bei Zollanzeige; 006/flaeche-zoll.png: „50“ (`F:\tmp-suche\urteile-d10-claude\crops\006-bett50.png`); Kopf und Baum zeigen Zoll (d04 Nr. 5, d10 Nr. 1).
- Ursache: belegt: `bed_scale` schreibt `f"{value:.0f}"` in Millimetern, ohne Anzeigeeinheit und ohne Einheitenzeichen (`viewport.py:2808–2812`). Zwilling zu FD-69 (Farbe derselben Zahlen), andere Ursache.
- Vorschlag: Die Zahlen über den Längenformatter der Anzeige setzen, Schrittweite passend zur Einheit, das Einheitenzeichen einmal an der Skala; beim Einheitenwechsel neu zeichnen.
- Wirkung beim Kunden: In Zoll liest er Millimeterzahlen ohne Hinweis und schätzt Größe und Lage falsch ein.
- Stand: offen RM-737

### FD-93 Die Auswahlkarte hält am Katalogknopf Leerraum

- Art: Gestaltung
- Schwere: leicht
- Funktion: `resize_feature`, `countersink_hole`
- Prüfpunkt: 19, Z6
- Beleg: Lauf 037–042 resize_feature: am Zapfen rund 75 px leer zwischen „Prüfstück erzeugen“ und „Filament und Druck“, in allen Sprachen (`F:\tmp-suche\urteile-d04-claude\crops\037-resize_feature-karte.png`); an der Bohrung PT rund 35 px, IT rund 8 px vor „Blocos adequados …“ (`042-countersink-karte.png`) (d04 Nr. 6).
- Ursache: offen; Verdacht: Der Platz des Katalogknopfs „Passende Bausteine …“ (`selection_operations.py`) bleibt reserviert, wenn der Knopf fehlt, und ist bei umbrochenem Text höher als nötig.
- Vorschlag: Ursache am Layout belegen; die Höhe aus dem sichtbaren Inhalt.
- Wirkung beim Kunden: Leere Fläche schiebt „Filament und Druck“ nach unten, auf kleinen Schirmen unter den Rand.
- Stand: offen RM-741

### FD-94 Eingabefelder tragen keinen zugänglichen Namen

- Art: Fehler
- Schwere: mittel
- Funktion: `pin_for_bore`, `plug_hole`, `drill_hole`, `pattern_feature`, `Bearbeiten/Parameter anlegen …`
- Prüfpunkt: 10
- Beleg: `F:\tmp-suche\urteile-d04-claude\felder-je-sprache.txt`: leerer `accessible_name` an der Auswahl „Bohrung“ (Stift, Verschließen), am Langloch-Haken (Bohren) und an „Art“ (Muster); die Listen „Zellen“ und „Merkmale“ heißen zugänglich „Ganzer Körper“. Lauf 003/function.json#names: Namens- und Wertfeld des Parameterdialogs heißen nach ihrem Inhalt „breite“ und „40,00“ (d04 Nr. 7, zweit Nr. 2).
- Ursache: belegt: `_explain` gibt Namen nur an innere Felder eines Behälters (`op_dialog.py:1389–1397`); ein Auswahlfeld oder Haken, der selbst der Editor ist, bleibt ohne Namen, und der Flächenwähler reicht den Namen seines Hakens weiter. Im `ParameterDialog` tragen Name, Wert, Ausdruck und Grenzen keinen Namen, nur die Einheit (`dialogs.py`). Der Prüfstand fällt dann auf den Text zurück.
- Vorschlag: Ein Weg für alle Formulare: Jedes Eingabefeld bekommt den Text seiner Beschriftung als `accessibleName`, auch der Editor selbst und die Liste im Flächenwähler; Wächter über alle Operationsdialoge und den Parameterdialog.
- Wirkung beim Kunden: Ein Bildschirmleser nennt das Feld nicht oder liest nur seinen Inhalt vor.
- Stand: offen RM-737

### FD-95 Die Absage im Operationsdialog wiederholt ihren Titel als „Art:“ und nennt Wege nur als Satz

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `group_pattern`, `create_label`, `split_bodies`, `finding.action:correct_input`, `finding.action:sketch.pick_plane`
- Prüfpunkt: 7, V1, V5
- Beleg: Lauf 037–042 group_pattern-dialog: „Art: Die Eingabe war so nicht verwendbar.“, „Eingabe korrigieren“ als Text, dazu „Details anzeigen“; 031/flaeche-de-create_label-1c3131b4-dialog.png ebenso in allen Sprachen; 043/flaeche-de-split_bodies-e45b38ac-dialog.png: „Art: Ein Wert liegt außerhalb des zulässigen Bereichs“; 043/flaeche-geoeffnet-de-finding.action_correct_input-9a5b98d1-dialog.png und …sketch.pick_plane-ad8b805d-dialog.png: „Eingabe korrigieren“ und „Eine andere Ebene wählen“ als bloßer Text (d04 Nr. 8, d10 Nr. 12, d08 N4, N11).
- Ursache: belegt: `problem_text` setzt die Werte des Fehlers über `spoken_values` darunter, und `kind` ist bei einem Schrittfehler dessen Titel (`_finding_from`); nur der Haltweg nimmt ihn heraus (`session.py:2772–2779`, KUNDE-12), der Dialog nicht (`dialogs.py:3274–3337`). Vorschläge ohne Handler setzt `unhandled_advice` als Satz, auch „Eingabe korrigieren“ in dem Dialog, der selbst die Eingabe ist. FD-44 deckte nur den Ursachencode.
- Vorschlag: `kind` bei `op.*`-Fehlern zentral in `spoken_values` auslassen, eine Quelle für Halt und Dialog; `show_refusal` löst „Eingabe korrigieren“ als Sprung ins Feld aus `values["field"]` ein und lässt es sonst weg; „Eine andere Ebene wählen“ als Handler des Ebenendialogs.
- Wirkung beim Kunden: Eine Fachzeile doppelt den Titel, und der Weg aus der Absage steht als Text da, den man nicht klicken kann.
- Stand: offen RM-737

### FD-96 Der i-Knopf der Merkmalzeilen ist ein Buchstabe statt eines Symbols

- Art: Gestaltung
- Schwere: leicht
- Funktion: `move_feature`, `duplicate_feature`, `rotate_feature`, `resize_feature`
- Prüfpunkt: 19, G4, G7
- Beleg: Stufe-A-Rohfund G4/G7 an den vier Zeilen in allen Sprachen (Schrift 9 pt, Gewicht 600), Lauf 037–042 (d04 Nr. 9).
- Ursache: belegt: `FeaturePanel` setzt `dot.setText(tr("i"))` an einem flachen `QToolButton` (`panels.py:11303–11309`).
- Vorschlag: Symbol aus dem eigenen Satz (`icons`); Tooltip, zugänglicher Name und Sprung ins Handbuch bleiben.
- Wirkung beim Kunden: Der Knopf wirkt wie ein Schriftzeichen und fällt neben den Symbolen aus dem Stil.
- Stand: offen RM-741

### FD-97 Abkürzungen verhindern Satzenden an Wortenden

- Art: Fehler
- Schwere: leicht
- Funktion: `pin_for_bore`, `finding.action:orient_for_print`
- Prüfpunkt: 9, E5
- Beleg: Lauf 039 und 042 pin_for_bore-dialog: ES und PT zeigen zwei Einleitungssätze, DE/EN/FR/IT einen; 045/flaeche-geoeffnet-es-finding.action_orient_for_print-a1ca663b-dialog.png: ES mit zweitem Satz (d04 Nr. 10, d08 N19).
- Ursache: belegt: `sentences` maskiert die Abkürzungen per Teilzeichenkette (`surfaces.py:935–971`); „ca.“ trifft das Wortende von „rosca.“ (ES/PT, Stift) und „placa.“ (ES, Druckoptimal), der Satz endet dort nicht, und `lead_sentence` nimmt zwei. Dieselbe Funktion schneidet Menü, Statuszeile, Suche und den Längenwächter.
- Vorschlag: Abkürzungen nur als ganzes Wort maskieren (Wortgrenze davor); Test mit „rosca. Es“ und „placa. Cada“.
- Wirkung beim Kunden: Über dem ersten Feld steht in zwei Sprachen ein Satz mehr, und Menü- und Suchtexte schneiden dort anders als in den übrigen Sprachen.
- Stand: offen RM-737

### FD-98 Der Zapfen heißt in fünf Sprachen klein

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `resize_feature`
- Prüfpunkt: 9
- Beleg: Lauf 038–042 resize_feature, Kartenkopf und Baum: „peg · Ø6,00 mm“, „espiga“, „tenon“, „perno“, „pino“ (d04 Nr. 11).
- Ursache: belegt: Der Katalogeintrag „Zapfen“ ist in en, es, fr, it und pt klein übersetzt; die übrigen Merkmalsarten aus `registry.py:540–575` sind groß.
- Vorschlag: Die fünf Katalogwerte groß; braucht ein Satz das Wort klein, ein zweiter Schlüssel mit Kontext.
- Wirkung beim Kunden: Der Kopf der Karte beginnt klein und sieht wie ein Fehler aus.
- Stand: offen RM-741

### FD-99 Übernehmen vor der ersten Änderung ist je Fläche anders, im Änderungsweg grau ohne Grund

- Art: Zwillinge
- Schwere: mittel
- Funktion: `resize_hole`, `resize_feature`, `finding.action:change_creating_step`
- Prüfpunkt: E7
- Beleg: Lauf 037/flaeche-de-countersink_hole-4a325b8d.png: „Bohrung im ursprünglichen Schritt ändern“ rechts offen mit orangem Übernehmen ohne Änderung, ebenso „Merkmal ändern“ am Zapfen (`F:\tmp-suche\urteile-d04-claude\crops\037-resize_feature-karte.png`) und „Fläche versetzen“ bei 0 mm; die Maßgruppe im Bild (037/flaeche-de-remove_feature-29cd30d1.png) grau ohne Satz (FD-31); 043/flaeche-geoeffnet-de-finding.action_change_creating_step-87b7204a-dialog.png: Gewindedialog im Änderungsweg, Hauptknopf „Einsetzen“, grau ohne Grund, alle Sprachen (d04 Nr. 13, d08 N9).
- Ursache: Zwilling zu FD-31: Maßgruppe und Änderungsdialog warten auf eine Änderung und sagen es nicht, Merkmalfenster und Flächenkarte bieten Übernehmen ohne Änderung an. Der Änderungsweg öffnet über `edit_operation` (`main_window.py:27826–27838`) den Dialog des Bausteins, dessen Hauptknopf `accept_text` „Einsetzen“ nennt (`op_dialog.py:249–251`), auch wenn ein bestehender Schritt geändert wird.
- Vorschlag: Mit FD-31 eine Regel für alle Flächen: vor der ersten Änderung grau mit dem Satz, der das erste Feld nennt; im Änderungsweg heißt der Knopf „Übernehmen“.
- Wirkung beim Kunden: Einmal geht Übernehmen ohne Änderung, einmal ist es grau ohne Satz, und im Änderungsweg sagt der Knopf „Einsetzen“.
- Stand: offen RM-737

### FD-100 Die Auswahlmatrix fragt das Ziel ohne den Weg der Zeile ab

- Art: Fehler
- Schwere: mittel
- Funktion: `resize_hole`, `finding.action:place_on_bed`
- Prüfpunkt: 13
- Beleg: Lauf 001/function.json#matrix: an ein_merkmal „QToolButton steht nicht da“, an den übrigen Stufen „fehlt“, obwohl die Maßgruppe *Bohrung ändern* im Bild steht (001/02-flaeche.png); 002/function.json#matrix: an allen Stufen „kein Bedienelement trägt dieses Kennzeichen“ (d04 Nr. 15, zweit Nr. 1).
- Ursache: belegt: `phase_matrix` klickt nur die Auswahl und fragt dann `offer_state(target)` (`function_bench.py:1516–1594`), ohne die Vorbereitungsklicks aus `Row.route` (Reiter, Klappe, Befund) und ohne die Zuordnung der Maßgruppe im Bild, die der Prüfstandsfix zu FD-29 (`0b1e61346`) nur für den Ort einführte.
- Vorschlag: Die Matrix geht denselben Weg wie die Hauptphase: Route bis vor das Ziel, die Maßgruppe im Bild als Ort der Handlung; der Gegenfall „fehlt“ bleibt.
- Wirkung beim Kunden: Prüfpunkt 13 ist an zwei von drei Hauptzeilen unmessbar; ein Kundenfehler ist daraus nicht belegt.
- Stand: offen RM-737

### FD-101 Zeilen ohne Weg oder passende Startszene

- Art: Fehler
- Schwere: mittel
- Funktion: `slot_hole`, `feature.apply`, `feature.in_view`, `feature.every`, `dialog:local_recognition_dialog`, `group_pattern`, `arrange_bed`, `check_collisions`, `orient_for_print`, `install`, `keep_saved_parts`, `recognize_fully`, drei `dialog:`-Zeilen in D8, `menu:parameters.edit` und die übrigen `dialog:`- und `meldung:`-Zeilen in D10
- Prüfpunkt: 1, 2
- Beleg: D4-Stufe A (`F:\tmp-suche\urteile-d04-claude\stufe-a-dump.txt`): „… steht nicht da, und kein Weg führt hin“ an feature:slot_hole, feature.apply, feature.in_view, feature.every; group_pattern an `quader.exakt` ohne gleiche Einzelmerkmale; D8: neun Zeilen ohne Fläche (Lauf 043/surfaces/<zeile>.json#steps); D10: zehn Zeilen ohne Weg zu ihrem Fenster, menu:parameters.edit mit leerer Route (d04 Nr. 8, Nr. 15, d08 N22, d10 Nr. 10).
- Ursache: Funktionsliste und Szenenkatalog (`tests/data/function_rows/`, `tools/function_scenes.py`): leere Route, eine Route, die einen Körper wählt, an dem die Handlung nicht gilt, oder eine Startszene ohne den Befund oder die Merkmale. Die Fußknöpfe des Merkmalfensters gibt es nur bei offener Zeile; *Zum Langloch ziehen* fehlt rechts, solange der Bohrschritt im Bild steht (gewollt, `panels.py` `set_measuring`).
- Vorschlag: Je Zeile Route und Szene so ergänzen, dass die Fläche entsteht (offene Merkmalzeile vor den Fußknöpfen, Rechtsklick für `menu:`, Szene mit Befund oder gleichen Merkmalen); Wächter: keine Zeile der Liste ohne erreichte Fläche.
- Wirkung beim Kunden: Diese Zeilen bleiben ungemessen; ein Kundenfehler ist daraus nicht belegt.
- Stand: offen RM-737

### FD-102 Ein verborgenes Feld ohne Namen macht V3 rot

- Art: Fehler
- Schwere: leicht
- Funktion: `move_feature`, `duplicate_feature`, `resize_feature`
- Prüfpunkt: V3
- Beleg: Stufe A an den drei Zeilen, Lauf 037–042: je ein Feld ohne Titel, Kurzhilfe und Beschreibung, das im Bild nicht zu sehen ist (d04 Nr. 15).
- Ursache: offen; fest steht, dass das gezählte Feld im Bild nicht sichtbar ist.
- Vorschlag: Ursache am Flächenprotokoll belegen: Zählt der Prüfstand verborgene Felder, zählen nur sichtbare; ist es ein sichtbares Feld ohne Fläche, wird es entfernt.
- Wirkung beim Kunden: Falscher V3-Fund an drei Zeilen; kein Kundenfehler belegt.
- Stand: offen RM-737

### FD-103 Ein Behälter der Maßgruppe hält Qts Abstand 6

- Art: Aufräumen
- Schwere: leicht
- Funktion: `resize_hole`
- Prüfpunkt: G2
- Beleg: Stufe A, Lauf 001: QWidget#5 der Maßgruppe mit `spacing` 6 bei einem Element (d04 Nr. 16).
- Ursache: am Code naheliegend: `_measure_scope_layout` setzt Ränder, aber keinen Abstand (`placement_flow.py:2760–2762`); Zwilling zu FD-23, das die Karten in `panels.py` auf das Raster brachte.
- Vorschlag: Abstand aus dem Raster setzen; der G2-Wächter schließt die Maßgruppe ein.
- Wirkung beim Kunden: Keine sichtbare; das Raster ist nicht überall gesetzt.
- Stand: offen RM-737

### FD-104 Befundhandlungen hinter einer angehaltenen Kette werden angeboten und scheitern

- Art: Fehler
- Schwere: mittel
- Funktion: `finding.action:mesh_to_exact`, `finding.action:orient_for_print`, `finding.action:resolve_intersections`, `finding.action:split_bodies`
- Prüfpunkt: 7, 15, E7, V5
- Beleg: Lauf 043/flaeche-geoeffnet-de-finding.action_mesh_to_exact-ef335aaf-dialog.png und …orient_for_print-a1ca663b-dialog.png: Hauptknopf grau ohne Grund im Dialog; …resolve_intersections-6c1a6470-dialog.png und …split_bodies-b73ef166-dialog.png: Absage erst nach dem Klick über den Haltdialog; alle Sprachen (d08 N1).
- Ursache: offen; fest steht: Die Handlungen hängen einen Schritt hinten an, und erst der Haltweg der Sitzung sagt ab („Die Kette hält an — ein neuer Schritt dahinter würde nicht gerechnet.“, `session.py:2781`). Der Bericht fragt den Halt vor dem Anbieten nicht — das Muster von FD-5.
- Vorschlag: Vor dem Anbieten fragen, ob die Handlung hinter dem Halt landen würde; dann vor dem Halt einfügen wie *Reparieren und erneut versuchen*, oder grau mit dem Halt als Grund und dem Weg dorthin.
- Wirkung beim Kunden: Er klickt die angebotene Lösung und bekommt eine Absage oder einen grauen Knopf ohne Satz.
- Stand: offen RM-737

### FD-105 Rohdaten im Kundentext

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `finding.action:show_details`, `finding.action:show_step_values`, `finding.action:calibrate_material`
- Prüfpunkt: V1
- Beleg: Lauf 043/flaeche-geoeffnet-de-finding.action_show_details-6ec9f9d7-dialog.png: Koordinaten „1.3325671035519837e-16“ ohne Einheit und „obj_1“; …show_step_values-6402e83f-dialog.png: Operationsname „paint_slot“ und Rohschlüssel; 043/flaeche-de-finding.action_calibrate_material-8295cd40.png: Berichtszeile „— Quader · obj_1 · obj_2“; alle Sprachen (d08 N2).
- Ursache: offen; die drei Ausgaben setzen Werte und Kennungen ohne `value_line` und Anzeigenamen.
- Vorschlag: Werte über `value_line` mit Einheit und Rundung der Anzeige, Körper mit Namen, Operationen mit Titel.
- Wirkung beim Kunden: Interne Kennungen und Fließkommazahlen statt verständlicher Angaben.
- Stand: offen RM-745

### FD-106 „Passt bereits auf das Bett“ steht auch neben einem Teil, das nicht passt

- Art: Fehler
- Schwere: mittel
- Funktion: `finding.action:release_protection`, `finding.action:split_along_line`
- Prüfpunkt: 6, V5
- Beleg: Lauf 043/flaeche-de-finding.action_release_protection-34d13d85.png und …split_along_line-0458b46f.png: Statuszeile „Dieses Objekt passt bereits auf das Bett.“ neben der Warnung „über den Bauraum hinaus … 172,00 mm“ (d08 N3).
- Ursache: belegt: `_split_done` setzt den Satz, sobald die Teilung keine Transaktion liefert (`main_window.py:9089–9091`), gleich aus welchem Grund, auch wenn kein Schnitt möglich war.
- Vorschlag: Den Satz nur, wenn das Teil wirklich passt; sonst der Grund aus den Befunden der Teilung mit ihrer Handlung.
- Wirkung beim Kunden: Die Statuszeile sagt, alles passe, während der Bericht das Gegenteil meldet.
- Stand: offen RM-737

### FD-107 Zwei Akzentknöpfe in Bericht und Analyseleiste

- Art: Gestaltung
- Schwere: leicht
- Funktion: `finding.action:decimate_mesh`, `finding.action:repair_and_retry`, `finding.action:resolve_intersections`
- Prüfpunkt: G1
- Beleg: Lauf 043/flaeche-de-finding.action_decimate_mesh-84b04288.png, …repair_and_retry-4ee0b670.png, …resolve_intersections-6c1a6470.png (d08 N5).
- Ursache: offen; Hauptknopf des Berichts und Knopf der Analyseleiste tragen beide den Akzent.
- Vorschlag: Solange der Bericht eine Hauptaktion zeigt, ist der Knopf der Leiste gewöhnlich.
- Wirkung beim Kunden: Er muss lesen, welcher Knopf gemeint ist.
- Stand: offen RM-745

### FD-108 Die Halt-Quittung erscheint am Zeiger über dem Bericht

- Art: Gestaltung
- Schwere: leicht
- Funktion: `finding.action:check_updates`, `finding.action:suppress_step`, `finding.action:resolve_intersections`, `finding.action:decimate_and_retry`, `finding.action:use_reachable`, `finding.action:remesh_and_retry`, `finding.action:show_support_need`
- Prüfpunkt: 9, E4
- Beleg: Lauf 043/flaeche-de-finding.action_check_updates-3c670373.png, …suppress_step-03bf451d.png; Blätter `F:\tmp-suche\urteile-d08-claude\blatt-finding_action_check_updates.png` und `…suppress_step.png`: „Die Kette hält an — siehe Prüfbericht.“ liegt über Hauptknopf, Zielknopf, Befundzeilen, Details und Exportieren (d08 N6).
- Ursache: belegt: `announce` setzt jede Quittung als `_ActionNotice` an den Mauszeiger und hebt sie über die Karten, für mindestens acht Sekunden (`main_window.py:943–966`, `26548–26554`); nach dem Klick steht der Zeiger im Bericht.
- Vorschlag: Die Quittung neben die auslösende Karte in die freie Ansicht setzen, nie über eine Karte.
- Wirkung beim Kunden: Acht Sekunden lang verdeckt der Satz die Knöpfe, die der Bericht als nächsten Schritt anbietet.
- Stand: offen RM-737

### FD-109 Befundzeilen kürzen ihre Maßangabe

- Art: Gestaltung
- Schwere: leicht
- Funktion: `finding.action:place_on_bed`, `finding.action:remove_small_parts`, `finding.action:show_layers`
- Prüfpunkt: 9
- Beleg: Lauf 048/flaeche-pt-finding.action_remove_small_parts-c7433173.png „Ressalto: 10,00 …“; 046/flaeche-fr-finding.action_show_layers-ebbd45da.png „Dépassement : 10,00 …“; 002/04-fehlfall.png „Überstand: 10,00 …“; Gruppenzeilen in EN und FR (d08 N7).
- Ursache: offen; die Zeilen des Berichts werden am rechten Rand elidiert.
- Vorschlag: Maß und Einheit gehören sichtbar zur Zeile; umbrechen oder den Titel vor dem Maß kürzen.
- Wirkung beim Kunden: Die Zahl, um die es geht, fehlt.
- Stand: offen RM-745

### FD-110 Die Textmessung erkennt elidierte Berichtszeilen nicht

- Art: Fehler
- Schwere: mittel
- Funktion: Funktionsprüfstand, Textmessung
- Prüfpunkt: 9
- Beleg: dieselben Bilder wie FD-109; Stufe A meldet dort `cut=false` (d08 N7).
- Ursache: offen; die Messung prüft Zeilen in Listen und Bäumen nicht gegen ihre gezeichnete Breite.
- Vorschlag: Elision in Listen und Bäumen messen (Text gegen Spaltenbreite der Ansicht), mit kurzer Zeile als Gegenfall.
- Wirkung beim Kunden: P9 meldet vollständige Texte, wo der Kunde „…“ liest.
- Stand: offen RM-737

### FD-111 Nach der Befundauswahl ist die Stelle nicht zu sehen

- Art: Einfachheit
- Schwere: mittel
- Funktion: `finding.action:scale_to_fit`, `finding.action:split_model`, `finding.action:repair_before_and_retry`, `finding.action:recognize_local`, `finding.action:remesh_and_retry`
- Prüfpunkt: E4
- Beleg: Lauf 043/flaeche-de-finding.action_scale_to_fit-87964424.png, …split_model-d08d0a7a.png, …repair_before_and_retry-34a5b021.png, …recognize_local-8238ff17.png, …remesh_and_retry-c1243162.png: die Ansicht zeigt nur Körperfläche (Kamera auf oder im Körper) oder einen winzigen Körper (d08 N8).
- Ursache: offen (Kamerafahrt der Befundauswahl oder Größe der Szene).
- Vorschlag: Ursache an einem der fünf Fälle belegen; die Befundauswahl rahmt Körper und Stelle.
- Wirkung beim Kunden: Er wählt einen Befund und sieht nicht, wo er liegt.
- Stand: offen RM-737

### FD-112 Dieselbe Handlung heißt im Bericht „Dicke geben“ und im Dialog „Offene Fläche schließen“

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `finding.action:give_thickness`
- Prüfpunkt: V1
- Beleg: Lauf 043/flaeche-geoeffnet-de-finding.action_give_thickness-0921d5a7-dialog.png; alle Sprachen (d08 N10).
- Ursache: belegt: *Dicke geben* öffnet gewollt *Offene Fläche schließen* (`main_window.py:28068`, `errors.py:114–116`); der Dialog nennt nur den Operationstitel.
- Vorschlag: Der Dialog sagt in seiner ersten Zeile, dass er der Fläche eine Dicke gibt, oder der Knopf heißt wie die Operation.
- Wirkung beim Kunden: Er klickt „Dicke geben“ und landet in einem Dialog mit anderem Namen.
- Stand: offen RM-745

### FD-113 „In Einzelteile aufteilen“ nennt ein mehrteiliges Netz ein Stück

- Art: Fehler
- Schwere: mittel
- Funktion: `split_bodies`
- Prüfpunkt: 7, E7, V5
- Beleg: Lauf 043/flaeche-de-split_bodies-e45b38ac.png und -dialog.png an `mehrteilig.netz`: Vorschau und Absage „Der Körper besteht aus einem Stück“, obwohl der Bericht mehrere Teile meldet; „Splitter behalten“ wird nicht angeboten (d08 N11).
- Ursache: belegt: `split_bodies` zählt ohne Splitter, solange `keep_tiny` aus ist (`prepare_ops.py:21759–21801`); bleibt ein Teil, sagt `ONE_PIECE` „aus einem Stück“, und die Vorschläge sind nur *Eingabe korrigieren* und *Abbrechen*. Die Zeile „Art: …“ ist FD-95.
- Vorschlag: Weggelassene Splitter nennen („… und N Splitter unter der Druckgrenze“) und *Splitter behalten* als Handlung anbieten.
- Wirkung beim Kunden: Die Absage widerspricht dem Bericht und verschweigt den einen Schalter, der weiterhilft.
- Stand: offen RM-737

### FD-114 Umbenennen zeigt den aktuellen Namen nicht

- Art: Einfachheit
- Schwere: leicht
- Funktion: `rename_object`
- Prüfpunkt: E2
- Beleg: Lauf 043/flaeche-de-rename_object-03af2449-dialog.png: Feld „Name“ leer; alle Sprachen (d08 N12).
- Ursache: offen.
- Vorschlag: Der aktuelle Name als Vorgabe, markiert.
- Wirkung beim Kunden: Für eine kleine Änderung tippt er den ganzen Namen neu.
- Stand: offen RM-745

### FD-115 Flächen von Berichtshandlung und Löschen entstehen nach ihrer Wirkung

- Art: Fehler
- Schwere: mittel
- Funktion: `report.action`, `delete_object`
- Prüfpunkt: 9, 19, V4
- Beleg: Lauf 043/flaeche-de-report.action-e5ae30a0.png und 043/flaeche-de-delete_object-df54ecae.png (d08 N13).
- Ursache: belegt: Der Fix von FD-37 hält den Weg nur bei Zielen `finding.action:` und `feature:` vor dem letzten Klick an (`function_bench.py:1906–1912`); andere Soforthandlungen klicken vor der Aufnahme. Rest zu FD-37.
- Vorschlag: „Vor der Wirkung messen“ an der Art der Handlung entscheiden (wirkt sofort), nicht am Präfix des Ziels; Gegenprobe an beiden Zeilen.
- Wirkung beim Kunden: Gemessen wird der Stand danach; kein Kundenfehler belegt.
- Stand: offen RM-737

### FD-116 Das Vorschauband zeigt die Legende ohne Volumenänderung

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `rename_object`, `set_material`
- Prüfpunkt: 3, V1
- Beleg: Lauf 043/flaeche-de-rename_object-03af2449.png und …set_material-323cd6b1.png: Legende Hinzugefügt/Entfernt ohne Geometrieänderung (d08 N14).
- Ursache: offen; verwandt mit FD-52 (Sichtbarkeit der Legende), hier umgekehrt.
- Vorschlag: Die Legende nur, wenn die Vorschau hinzugefügtes oder entferntes Material zeigt.
- Wirkung beim Kunden: „Hinzugefügt/Entfernt“ bei einer Handlung, die nichts hinzufügt oder entfernt.
- Stand: offen RM-737

### FD-117 „Neu erzeugen“ öffnet den Generator leer

- Art: Einfachheit
- Schwere: leicht
- Funktion: `finding.action:generate_again`
- Prüfpunkt: E2, Z6
- Beleg: Lauf 043/flaeche-geoeffnet-de-finding.action_generate_again-c04c15ad-dialog.png: ohne Einleitungssatz, frühere Beschreibung nicht vorbelegt; Blatt `F:\tmp-suche\urteile-d08-claude\blatt-finding_action_generate_again.png`: ES/IT/PT 282 statt 266 px hoch (d08 N15). Die Feldhilfen sind FD-78.
- Ursache: für die Vorbelegung belegt: Der Handler ruft `_generate(None)` (`main_window.py:27550`) und gibt keine frühere Beschreibung mit; Einleitung und Höhe offen.
- Vorschlag: Die Beschreibung des erzeugten Modells vorbelegen, wenn sie vorliegt; ein Satz über dem Feld.
- Wirkung beim Kunden: Für einen neuen Versuch tippt er die Beschreibung noch einmal.
- Stand: offen RM-745

### FD-118 Das Wertefenster ist für sechs Zeilen viel zu groß

- Art: Gestaltung
- Schwere: leicht
- Funktion: `finding.action:show_step_values`
- Prüfpunkt: Z6
- Beleg: Lauf 043/flaeche-geoeffnet-de-finding.action_show_step_values-6402e83f-dialog.png: 520 × 360, rund zwei Drittel des Textfelds leer; alle Sprachen (d08 N16).
- Ursache: offen.
- Vorschlag: Höhe aus dem Inhalt, wie bei FD-51.
- Wirkung beim Kunden: Das Fenster verdeckt mehr Modell als nötig.
- Stand: offen RM-745

### FD-119 Der Prüfstück-Dialog hat zweimal „Stelle“

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `test_piece`
- Prüfpunkt: V1, G3
- Beleg: Lauf 043/flaeche-de-test_piece-c2812758-dialog.png: Anzeige „Stelle“ und Auswahl „Genannter Punkt“ unter demselben Wort; alle Sprachen (d08 N17).
- Ursache: offen.
- Vorschlag: Zwei unterscheidbare Beschriftungen.
- Wirkung beim Kunden: Unklar, welches Feld die Stelle festlegt.
- Stand: offen RM-745

### FD-120 „Stifte“ klebt am Haken davor

- Art: Gestaltung
- Schwere: leicht
- Funktion: `tool:split`
- Prüfpunkt: G3
- Beleg: Blatt `F:\tmp-suche\urteile-d08-claude\blatt-tool_split.png`, Lauf 043/flaeche-de-tool_split-ed52c275.png: „Zum Zusammenstecken vorbereiten“ und „Stifte“ lesen sich als ein Satz; alle Sprachen (d08 N18).
- Ursache: offen (Abstand in der Teilenleiste).
- Vorschlag: Abstand oder Trenner zwischen Haken und Feldbeschriftung.
- Wirkung beim Kunden: Haken und Feld lesen sich wie ein Satz.
- Stand: offen RM-745

### FD-121 Der einmalige Druckhinweis verdeckt die Zielfläche im Prüfstand

- Art: Fehler
- Schwere: mittel
- Funktion: `finding.action:choose_printer`, `finding.action:open_print_settings`
- Prüfpunkt: 1, E5
- Beleg: Lauf 043/flaeche-geoeffnet-de-finding.action_choose_printer-2c1a8d33-dialog.png und …open_print_settings-970cbb07-dialog.png: gemessen wird der Druckhinweis (258 px, 27 Wörter), die Zielfläche wird nie erreicht (d08 N20).
- Ursache: Das Prüfprofil quittiert den einmaligen Hinweis (`app/ui/print_disclosure.py`) nicht; Stufe A misst E5 am Hinweis.
- Vorschlag: Den Hinweis im Profil der Fälle als gesehen eintragen (`tools/function_setup.py`, `profile_settings`) und ihn als eigene Zeile messen.
- Wirkung beim Kunden: E5-Fund an der falschen Fläche, die Zielfläche bleibt ungemessen; kein Kundenfehler belegt.
- Stand: offen RM-737

### FD-122 Der Prüfstand misst an Dateidialogen den erzwungenen Qt-Dialog

- Art: Fehler
- Schwere: leicht
- Funktion: `finding.action:choose_another_file`, `finding.action:export_as_mesh`
- Prüfpunkt: 19
- Beleg: Lauf 043/flaeche-geoeffnet-de-finding.action_choose_another_file-3b6379cf-dialog.png und …export_as_mesh-b040c130-dialog.png: englische Teile, gekürzte Spalten, Startordner `F:\sl-welle4`; Stufe-A-Funde Abstände 6/11 und Rollleiste (d08 N21).
- Ursache: belegt: Der Fallprozess setzt `AA_DontUseNativeDialogs` (`tools/file_acceptance.py:1197`); der Kunde sieht den Systemdialog.
- Vorschlag: Dateidialoge als Systemfläche kennzeichnen (Z5-Ausnahme, Stufe C) und nicht nach G2 und Z6 messen.
- Wirkung beim Kunden: Falsche Gestaltungsfunde; kein Kundenfehler.
- Stand: offen RM-737

### FD-123 Der Kantenfehler bietet „Andere Objekte wählen“ an

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `finding.action:change_selection`
- Prüfpunkt: V1
- Beleg: Lauf 043/flaeche-de-finding.action_change_selection-9fd7dccb.png (d08 N23).
- Ursache: offen; der Vorschlag nennt Objekte, wo Kanten gemeint sind.
- Vorschlag: „Andere Kanten wählen“ an Kantenfehlern, in allen Sprachen.
- Wirkung beim Kunden: Er wählt einen anderen Körper statt einer anderen Kante.
- Stand: offen RM-745

### FD-124 Große Zahlen ohne Tausendertrennung

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `finding.action:decimate_mesh`
- Prüfpunkt: 9
- Beleg: Lauf 043/flaeche-de-finding.action_decimate_mesh-84b04288.png und -dialog.png: „2103472 Dreiecke, möglich sind 900000“, Feld „1051736“; alle Sprachen (d08 N24).
- Ursache: offen.
- Vorschlag: Ganzzahlen mit Gruppentrennung der Anzeigesprache, auch im Feld.
- Wirkung beim Kunden: Siebenstellige Zahlen sind schwer zu lesen.
- Stand: offen RM-745

### FD-125 Parameter anlegen kennt keine Zolleinheit

- Art: Fehler
- Schwere: mittel
- Funktion: `Bearbeiten/Parameter anlegen …`
- Prüfpunkt: 9
- Beleg: Lauf 006/flaeche-zoll-dialog.png: bei Zollanzeige nur „mm — Länge“, der Wert ohne Zoll; Kopf und Baum zeigen Zoll (d10 Nr. 1).
- Ursache: belegt: `PARAMETER_UNITS` kennt nur mm, Grad und ohne Einheit (`labels.py:112–116`); auch der Rezeptdialog nutzt die Liste (`recipe_dialog.py:253`).
- Vorschlag: Längenparameter in der Anzeigeeinheit zeigen und annehmen (Längenfeld wie in den Operationsdialogen), gespeichert in mm (Regel 6).
- Wirkung beim Kunden: Wer in Zoll arbeitet, rechnet für einen Parameter in Millimeter um.
- Stand: offen RM-737

### FD-126 Im ersten Bild liegt „Parameter anlegen …“ über dem Erklärungstext

- Art: Gestaltung
- Schwere: leicht
- Funktion: `Bearbeiten/Parameter anlegen …`, `parameters`
- Prüfpunkt: 19
- Beleg: Lauf 003/01-vorher.png, Ausschnitt `F:\tmp-suche\urteile-d10-claude\crops\003-01-parameter.png`; alle späteren Bilder sauber (d10 Nr. 3).
- Ursache: offen (ein Bild); Verdacht: Höhe des umbrochenen Texts vor der endgültigen Breite gemessen.
- Vorschlag: Am Startweg nachstellen, dann beheben.
- Wirkung beim Kunden: Kurz nach dem Laden verdeckt der Knopf eine Textzeile.
- Stand: offen RM-747

### FD-127 Prüfpunkt 12 zählt nur Operationen

- Art: Fehler
- Schwere: leicht
- Funktion: `Bearbeiten/Parameter anlegen …`
- Prüfpunkt: 12
- Beleg: Lauf 003/03-uebernommen.png zeigt den Verlaufseintrag „Parameter breite“, Stufe A meldet „die Zeile legt keinen Schritt im Verlauf an“ (d10 Nr. 4).
- Ursache: belegt: `phase_revise` vergleicht die Zahl der `ops` (`function_revision.py:38–40`); eine Parameteränderung ist ein Verlaufseintrag ohne Operation.
- Vorschlag: Die Verlaufslänge aus den Einträgen des Verlaufs lesen und den Parameterweg (Doppelklick, *Ändern …*) messen.
- Wirkung beim Kunden: P12 bleibt an Parameterzeilen ungemessen; kein Kundenfehler belegt.
- Stand: offen RM-737

### FD-128 Prüfpunkte 5 und 16 verlangen Zustände, die die Zeile nicht hat

- Art: Fehler
- Schwere: leicht
- Funktion: `finding.action:place_on_bed`, `Bearbeiten/Parameter anlegen …`
- Prüfpunkt: 5, 16
- Beleg: Lauf 002/function.json#states: before, applied, undo und redo vorhanden, Rückgängig stellt den Körperabdruck her, P5 meldet trotzdem alle fünf Zustände fehlend; 003/02-flaeche.png: P16 verlangt Vorschau- und Rechnungsphase an einer Zeile ohne beides (zweit Nr. 4, d10 Nr. 5).
- Ursache: belegt: `_point_5` verlangt `states.escape` an jeder Zeile (`function_points.py:337–345`), `_point_16` alle `SWITCH_PHASES` (`function_points.py:829–846`), gleich ob die Zeile Entwurf, Vorschau oder Rechnung hat.
- Vorschlag: Escape nur an Zeilen mit Entwurf oder Dialog verlangen, Wechselphasen nur die, die die Zeile hat; sonst *entfällt* mit Grund aus der geschlossenen Liste.
- Wirkung beim Kunden: Der Rückweg nach FD-4 und der Wechsel bleiben ungewertet; kein Kundenfehler.
- Stand: offen RM-737

### FD-129 Fensterbefehle mit Agentenwerkzeug nennen keinen Ort, und Prüfpunkt 17 sieht sie nicht

- Art: Fehler
- Schwere: mittel
- Funktion: `Bearbeiten/Parameter anlegen …`, `dialog:parameter_dialog`
- Prüfpunkt: 17
- Beleg: Lauf 003/02-flaeche.png, Stufe A „ohne Agentenwerkzeug“; das Werkzeug `add_parameter` legt genau diesen Parameter an (d10 Nr. 6).
- Ursache: belegt: `_point_17` sucht den Agentenweg nur für Zeilen der Art `operation` (`function_points.py:851–856`); `add_parameter` beschreibt keinen Ort im Fenster (`app/core/agent/tools.py:644–667`), anders als die Operationswerkzeuge über `menu_path`.
- Vorschlag: Werkzeuge außerhalb des Registers (`add_parameter`, `set_parameter`, `add_fit` und weitere) nennen ihren Fensterort aus derselben Quelle wie das Menü; P17 ordnet sie ihren Zeilen zu.
- Wirkung beim Kunden: Der Agent kann nicht sagen, wo der Kunde einen Parameter selbst anlegt, und die Prüfung hält den Punkt für nicht zutreffend.
- Stand: offen RM-737

### FD-130 Die Flächenmessung nimmt für andere Ziele die Auswahlkarte

- Art: Fehler
- Schwere: mittel
- Funktion: `parameters`, `parameters.first`
- Prüfpunkt: 8, E5, V1, V2, V3
- Beleg: Lauf 031/flaeche-de-parameters.first-b5c45dda.png; Flächenprotokolle beider Zeilen: Texte und Felder aus der rechten Auswahlkarte („Nichts gewählt …“), Wertfeld, Einheit und „…“ der Parameterzeile fehlen (d10 Nr. 7).
- Ursache: belegt: `surface_for` kennt Dialog, Bericht, Werkzeugleiste und Merkmal und fällt sonst auf `selection` zurück (`function_surface.py:116`); der Fix von FD-47 schloss nur `feature:`. Rest zu FD-47.
- Vorschlag: Die Fläche aus dem Ziel selbst ableiten (nächster Kartenvorfahre des Ziels); die Auswahlkarte nur, wenn das Ziel dort liegt.
- Wirkung beim Kunden: E5, V1 und V2 grün und V3 rot an der falschen Karte; kein Kundenfehler belegt.
- Stand: offen RM-737

### FD-131 Die Navigation klickt ein Ziel unterhalb aller Sichtflächen an

- Art: Fehler
- Schwere: mittel
- Funktion: `assign_slot`
- Prüfpunkt: 2
- Beleg: Lauf 031/surfaces/assign_slot-bd965763.json#steps: Klick „klappe“ auf `filament.picker` bei y = 1572–1605, das Fenster endet bei 1470, kein Rollen, `widget_at` leer, „verdeckt“; in allen sechs Sprachen (d10 Nr. 8).
- Ursache: teilweise belegt: Am Stand `2ec37b23b` lässt `_scroll_needed` das Ziel stehen, wenn kein Rollbereich weiter rollen kann (`guide_targets.py:1648–1676`), und der Klick geht ins Leere. Der Fix zu FD-77 (`46c628ef9`, auf welle4 seit `64e389936`) macht daraus `MissingTargetError`. Warum kein Bereich das Ziel heranrollt, ist offen: Prüfstand oder eine Karte, die über den Fensterrand reicht.
- Vorschlag: Am Stand mit FD-77 nachstellen; reicht die Karte über den Fensterrand, ist es ein Produktfund und wird neu bewertet.
- Wirkung beim Kunden: Der Kundenweg zu *Filament zuweisen* lief in keiner Sprache.
- Stand: offen RM-737

### FD-132 Der Zustand einer Sprachfläche wandert in die nächste

- Art: Fehler
- Schwere: mittel
- Funktion: `paint_slot`, `filament.section`
- Prüfpunkt: Z3
- Beleg: Lauf 031/flaeche-de-paint_slot-9865a109.png: Z3 misst 0 Wegklicks, weil die vorige Fläche im selben Prozess den Abschnitt aufgeklappt beziehungsweise die Karte ans Ende gerollt hatte; im Ausgangszustand ist er zu (FD-19) (d10 Nr. 9).
- Ursache: Zwilling zu FD-40: Der Sprachdurchgang wechselt die Startszene, stellt aber Klappzustand und Rolllage der Karten nicht zurück (`tools/function_language.py`).
- Vorschlag: Vor jeder Sprachfläche den Ausgangszustand der Karten herstellen, oder messen und rot beenden, wenn er abweicht.
- Wirkung beim Kunden: Ein rotes Z3 wird grün; der Weg zum Filamentabschnitt erscheint kürzer, als er ist.
- Stand: offen RM-737

### FD-133 Im portugiesischen Maßblock der Gegenstücke stehen zwei Leerzeilen

- Art: Gestaltung
- Schwere: leicht
- Funktion: `Erzeugen/Bausteine/Gegenstücke setzen …`
- Prüfpunkt: 9, Z6
- Beleg: Lauf 036/flaeche-pt-Erzeugen_Bausteine_Gegenstücke_setzen-5b902f72.png: rund 32 px Leerraum im Maßblock der rechten Karte, andere Sprachen ohne (d10 Nr. 11).
- Ursache: offen; möglicherweise dieselbe Umbruchhöhe wie FD-93.
- Vorschlag: Am Layout belegen; die Höhe aus dem sichtbaren Inhalt.
- Wirkung beim Kunden: Leere Zeilen in der Karte.
- Stand: offen RM-747

### FD-134 Schriftzug anlegen meldet vor der ersten Eingabe einen Fehler

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `create_label`
- Prüfpunkt: V5
- Beleg: Lauf 031/flaeche-de-create_label-1c3131b4-dialog.png: schon beim Öffnen „Ohne Text gibt es nichts anzulegen.“ mit Fehlerblock und „Details anzeigen“, alle Sprachen; `inlay_text` und `label_text` zeigen denselben Zustand nur im Vorschauband (d10 Nr. 12).
- Ursache: offen; fest steht, dass die erste Vorschau mit leerem Text als Absage im Dialog endet, bei den Geschwistern nicht. Die Form des Blocks ist FD-95.
- Vorschlag: Ein leerer Pflichttext ist ein Hinweis am Feld wie bei den Geschwistern, kein Fehler.
- Wirkung beim Kunden: Bevor er etwas getan hat, steht da ein Fehler.
- Stand: offen RM-747

### FD-135 Textur in Filamente umrechnen wird ohne Textur angeboten

- Art: Fehler
- Schwere: mittel
- Funktion: `slots_from_texture`
- Prüfpunkt: 13, E7
- Beleg: Lauf 031/flaeche-de-slots_from_texture-1cd8021e.png: am Quader ohne Textur angeboten, erst die Vorschau sagt „Dieses Objekt trägt keine Farbinformation.“ (d10 Nr. 13).
- Ursache: belegt: Der Registereintrag trägt kein `requires_body` (`colour_ops.py:314–330`); `grenzen.md` verlangt, dass am Menüeintrag steht, was am gewählten Körper nie etwas tun kann.
- Vorschlag: Die Bedingung „trägt Farbinformation“ als `requires_body` mit demselben Satz; der Eintrag steht grau mit Grund.
- Wirkung beim Kunden: Er öffnet eine Handlung, die an seinem Teil nie etwas tun kann.
- Stand: offen RM-737

### FD-136 Der Übernehmen-Fuß steht weit unter seinem Feld

- Art: Gestaltung
- Schwere: leicht
- Funktion: `clear_filament`, `paint_slot`, `resize_feature`
- Prüfpunkt: 19
- Beleg: Lauf 031/flaeche-de-clear_filament-a6b075a9.png: oranges „Übernehmen“ mit „Fläche versetzen“ unter dem Filamentabschnitt, das Feld ganz oben; ebenso „Merkmal ändern“ am Zapfen (`F:\tmp-suche\urteile-d04-claude\crops\037-resize_feature-karte.png`) (d10 Nr. 14). Gestaltungsurteil.
- Ursache: Der Fuß steht außerhalb der rollenden Zeilen am Kartenende (so beschrieben in `function_surface.surface_parts`).
- Vorschlag: Den Fuß unmittelbar unter der offenen Zeile zeigen; E1–E7 an derselben Zeile vorher und nachher messen.
- Wirkung beim Kunden: Feld oben, Knopf unten — der Blick springt über die ganze Karte.
- Stand: offen RM-737

### FD-137 Zwei Dialogeinleitungen sind wörtlich oder doppeldeutig übersetzt

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `Bearbeiten/Parameter anlegen …`, `inlay_text`
- Prüfpunkt: 8, V1
- Beleg: Lauf 034/flaeche-fr-Bearbeiten_Parameter_anlegen-ffe8f785-dialog.png: EN „turning the number rebuilds the model“, FR „tourner le chiffre …“, IT „girare il numero …“ (Quelle `app/ui/dialogs.py`); 036/flaeche-pt-inlay_text-96981be8-dialog.png: PT „Incrusta texto à face numa face.“ (d10 Nr. 15, Nr. 16).
- Ursache: belegt: die Katalogwerte in en, fr und it beziehungsweise pt.
- Vorschlag: Die vier Katalogwerte neu übersetzen.
- Wirkung beim Kunden: Die Einleitung ist in vier Sprachen holprig oder missverständlich.
- Stand: offen RM-747

### FD-138 Die gefaltete Sperrzeile liest sich als gewöhnlicher Absatz

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `clear_filament`, `paint_slot`, `resize_feature`
- Prüfpunkt: V1
- Beleg: Lauf 031/flaeche-de-clear_filament-a6b075a9.png: „Merkmal ändern, Zum Langloch ziehen, drehen, verdoppeln und entfernen — Eine Fläche ist …“, Großschreibung mitten im Satz, in allen Sprachen gleich gebaut; am Zapfen „Zum Langloch ziehen — Gezogen wird ein Loch, …“ (`F:\tmp-suche\urteile-d04-claude\crops\037-resize_feature-karte.png`) (d10 Nr. 17).
- Ursache: Die Gründe aus `NOT_APPLICABLE` (`app/core/perceive/actions.py`) werden in `panels.py` hinter die Titel gefaltet, ohne zu sagen, dass die genannten Handlungen hier nicht gehen. Der Verbinder aus FD-43 ist behoben und nicht betroffen.
- Vorschlag: Ein Satzbau, der die Absage trägt („Hier nicht: …, weil …“), mit kleinem Anschluss nach dem Gedankenstrich, in allen Sprachen.
- Wirkung beim Kunden: Er liest eine Aufzählung von Handlungen und erfährt nicht, dass sie hier fehlen.
- Stand: offen RM-737

### FD-139 Rollbereiche sind eigene Tab-Halte mit Klassennamen

- Art: Fehler
- Schwere: mittel
- Funktion: `Bearbeiten/Parameter anlegen …`, `finding.action:place_on_bed`
- Prüfpunkt: 10
- Beleg: Lauf 003/function.json#tab_chain: Die Kette beginnt und endet an „DialogScrollArea“; 002/function.json#tab_chain: erstes Glied „FittedScroller“ (zweit Nr. 2, Nr. 3).
- Ursache: belegt am Code: `DialogScrollArea` (`style.py:233`) und `overlay.FittedScroller` (`overlay.py:1046`) setzen keine Fokuspolitik und behalten Qts Vorgabe für Rollbereiche (`StrongFocus`); einen zugänglichen Namen tragen sie nicht.
- Vorschlag: Reine Rollbehälter auf `NoFocus` (Rad und Tastatur rollen über das fokussierte Kind), sonst mit Name und Beschreibung.
- Wirkung beim Kunden: Am Anfang und Ende jedes Dialogs ein Tab-Halt ohne Namen.
- Stand: offen RM-737

### FD-140 Tab erreicht „Auf das Bett setzen“ im Prüfbericht nicht

- Art: Fehler
- Schwere: mittel
- Funktion: `finding.action:place_on_bed`
- Prüfpunkt: 10
- Beleg: Lauf 002/function.json#tab_chain: FittedScroller → SignalTabBar (außerhalb), die Handlung fehlt; Bild 002/02-flaeche.png (zweit Nr. 3).
- Ursache: offen; fest steht, dass die Kette den Bericht nach dem Rollbereich verlässt. Ob seine Knöpfe fokussierbar sind, sagt das Protokoll nicht.
- Vorschlag: Die Tab-Folge des Berichts belegen (Befundliste → Handlungen) und setzen; Test über Tab und `focusWidget()`.
- Wirkung beim Kunden: Mit der Tastatur bleibt die angebotene Lösung unerreichbar.
- Stand: offen RM-737

### FD-141 Prüfpunkt 10 fragt weder nach der Zielhandlung noch nach technischen Namen

- Art: Fehler
- Schwere: mittel
- Funktion: Funktionsprüfstand, Tastatur und Zugänglichkeit
- Prüfpunkt: 10
- Beleg: Lauf 001 und 002: Ketten ohne Zielhandlung, Glieder „FittedScroller“ und „DialogScrollArea“; Stufe A „2 Tab-Schritte, erfüllt“ beziehungsweise „erfüllt“ (zweit Nr. 3).
- Ursache: belegt: `_point_10` prüft nur Rücksprünge innerhalb der Fläche, leere und doppelte Namen (`function_points.py:615–655`); `name_of` fällt auf den Klassennamen zurück (`function_capture.py:474–477`), der als Name zählt, und Glieder außerhalb werden nur weggefiltert.
- Vorschlag: P10 verlangt, dass die Kette die Zielhandlung der Zeile erreicht, bevor sie die Fläche verlässt; ein Klassenname zählt als fehlender Name.
- Wirkung beim Kunden: Ein unbedienbarer Tastaturweg wird als erfüllt abgehakt.
- Stand: offen RM-737

### FD-142 Weitere Doppelklicks in Tests und Werkzeugen lassen die Maustaste gedrückt

- Art: Zwillinge
- Schwere: leicht
- Funktion: Prüfanschlüsse und Videowerkzeug
- Prüfpunkt: 19
- Beleg: Neben dem in FD-83 behobenen `QtPorts.press` rufen `tests/test_start_screen.py:461`, `:957`, `:966` und `tools/make_workshop_videos.py:2462` `QTest.mouseDClick` ohne anschließendes Loslassen auf; in `make_workshop_videos.py` fehlt zusätzlich der Klick davor (`F:\3D Druck\output\konsolidierung-2026-10-12\fd83-claude.md`).
- Ursache: `mouseDClick` schickt nur das Doppelklickereignis; Qt hält die linke Taste danach im ganzen Prozess für gedrückt.
- Vorschlag: Dieselbe Folge wie der Kunde (Klick, Doppelklick, Loslassen) an allen Stellen; als Wächter eine Fixture, die nach jedem `qt_app`-Fall `QGuiApplication.mouseButtons() == NoButton` zusichert.
- Wirkung beim Kunden: Kein Produktfehler; spätere Fälle im selben Prozess und Werkstattvideos sehen Bewegungen als Zug.
- Stand: offen RM-737
