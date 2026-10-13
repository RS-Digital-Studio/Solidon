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
- Stand: offen RM-741

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
- Stand: offen RM-741

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

