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
- Stand: offen RM-741; der Fix (`f333e5ba7`, welle4 `b86381559`) ersetzt das Wort nur an der Maßgruppe — der finale Lauf zeigt „Materialtoleranz“ weiter im doc von *Bohrung setzen* (037, V1 Fund), in der Zusammenfassung von *Bohrung verschließen* (037) und in der Detailmeldung (043); Stufe B V1 offen (D4, D8).

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
- Stand: offen RM-737; Fix `aa1bae3ba` (in welle4 `6238bf7fd`): Rechts ist die Handlung im Bild scharf, *Merkmal verschieben* steht im finalen Lauf nur noch als zugeklappter Kopf (007). Offen bleibt nach Stufe B (`resize_hole`, Prüfpunkt 1), dass mit der Maßgruppe die Verschiebepfeile des Merkmals an derselben Bohrung scharf im Bild stehen (02, 016, 019).

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
- Stand: offen RM-737; der Hinweis nennt im finalen Lauf zuerst „Abbrechen“ (001 Fehlfall; Fix `c75ece14b`, welle4 `f807415569`, Rottest 6 rot), doch der angebotene Weg Abbrechen → *Merkmal entfernen* ist im Lauf nicht durchgeklickt; P7 und V5 beider Prüfer offen (D4).

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
- Stand: offen RM-741; die Listenreserve ist im finalen Lauf weg (037–042 Liste eine Zeile, `group_pattern` und `hollow_object` ohne Reserve; Fix `2e4752521`, welle4 `27a18b48c`, Rottest rot), doch an `pattern_feature` bleibt in DE, EN, FR und IT ein Leerstreifen von etwa 40 px über den Knöpfen, den Stufe B unter FD-45 führt (D4).

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
- Stand: offen RM-741; Fix `2e4752521` (welle4 `27a18b48c`), aber der finale Lauf fährt keine große Inhaltsschrift — die Lage ist ungemessen (Stufe B `group_pattern` P9).

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
- Stand: offen RM-737; Fix `6d5734da5` (welle4 `433da64bc`, Rottest 4 rot), aber im finalen Lauf erreichen 043–048 das Ziel ohne Radschritt — der korrigierte Radweg ist ungemessen.

### FD-57 Auswahlkarte und XYZ-Zeile geraten nach spanischem Schriftwechsel in eine Größenschleife

- Art: Gestaltung
- Schwere: mittel
- Funktion: move_feature
- Prüfpunkt: 9, 19
- Beleg: fix-panelbreite-codex.md vom Autor bild_d10; F:/tmp-suche/fix-panelbreite-codex/native-trace-es/native.json und timeout.png. Nach echter Segoe-UI-Änderung 9→14 pt bleiben bei 19,6–20,0 s und busy=false die Rechtecke in Bewegung: cardColumn-Breite 470 bis 483 logische Pixel, _CoordinateRow-Höhe 41↔131; Rollbalken erscheinen und verschwinden. Prozess Exit 1, Quellen vor/nach 2300 Pins gleich am Korrekturmanifest eef17728e9ebb3bf387776a5a207468dd92cf370d82f609b765683b9af0e19c4. Frühere sechs native Prozesse Exit 0; ein 1×1-Pixel-Bild ist kein Sichtbeleg, Ersatz-/Diagnosenachlauf bleibt rot.
- Ursache: Echte Produkt-Geometrieänderung im Auswahlkartenlayout, während die Sitzung nicht rechnet; keine bloß wechselnde Python-Wrapperidentität wie FD55. Der Autorenbericht lokalisiert die Rückkopplung an der von augenblicklicher Sichtbarkeit abhängigen Rollbalkenreserve in der natürlichen Breitenmessung. Ein kleiner roter Höhenwechsel-Fall nimmt XYZ allein durch einen erscheinenden Balken zwölf Punkte zugesagte Breite. Die neue enge Korrektur verwendet das vorhandene Stilmaß möglicher Rollbalken unabhängig von ihrer aktuellen Sichtbarkeit; ein abschließender nativer Nachherbeleg fehlt noch.
- Vorschlag: Im bestehenden Kartenmessweg die Rollbalkenreserve und den natürlichen Querbedarf so bestimmen, dass der sichtbare aktuelle Zustand keine endlose gegenseitige Größenänderung erzeugt. Roten konkreten Schriftwechsel-Gegenfall sichern, anschließend tatsächlichen ES14-Nachlauf mit stabiler Geometrie sowie Sprach-/Rückkehrgegenfälle belegen. Nicht nur die Wartefrist verlängern, eine breite Fixbreite erzwingen oder den roten Nachlauf durch frühere grüne Fälle ersetzen.
- Wirkung beim Kunden: Die Auswahlkarte verändert nach dem Schriftwechsel fortlaufend ihre Breite, und XYZ springt zwischen Querzeile und gestapelten Feldern. Die Bedienelemente bleiben dadurch nicht ruhig; eine verlässliche Größeneinstellung und Zielwahl ist in diesem Zustand nicht belegt.
- Stand: offen RM-747; Fix `11f44ba88` (welle4 `e68ca22cb`), aber der finale Lauf fährt keinen Schriftwechsel 9 → 14 pt; 039 zeigt nur die ruhige Ausgangsschrift.

### FD-58 Vollzeilenknopf erhält halbe Umbruchbreite und behält einen ungültigen Rasterzustand

- Art: Gestaltung
- Schwere: mittel
- Funktion: pattern_feature
- Prüfpunkt: 9, 19
- Beleg: fix-panelbreite-codex.md und KOORDINATION.md: tatsächlicher MSI-Nachlauf native-fd57-msi zeigte am vollständig überspannenden Hauptknopf unnötigen Umbruch. Reale Segoe-14-Folge 504×44→435×64→504×44; erste 12-Fälle-Gegenprobe FR/IT/PT rot (3 rot/9 grün). Isolierter 600→450→600-Fix reichte nicht: native-fd58-trace/de/07-tall-14.png zeigt Merkmal vervielfachen trotz natürlichem Textbedarf 242 in 474×64 auf zwei Zeilen. Neue echte schmal/9→groß/14→schmal/9-Folge im Original rot (ES: 1 rot/5 grün), endgültig 66 bestanden/88,00 s, Exit 0. Finales Manifest 4a03df4877f1d4ae8197950c7e61a113bad8fe659d6f0952267b6481a13b3d18; native-fd58-final sechs MSI-Sprachen/24 vom Autor tatsächlich gelesene Bilder, alle Exit 0. Pixelurteil ee045d065c8bc4e9749af8a94d5f82e54537e3f068f290f14b8590325fd27743; Root las DE/ES zusätzlich.
- Ursache: Produktfehler in app/ui/selection_operations.py, vorhandener _wrap_labels-Weg: Der dritte Hauptknopf überspannt die ganze Rasterzeile, die Textmessung teilte die Breite trotzdem wie bei den beiden Nachbarknöpfen. Während Qt die Knöpfe umhängt, wird derselbe Weg vor dem erneuten Eintragen aufgerufen; indexOf(button) ist dann -1, getItemPosition liefert keinen gültigen Spaltenumfang. Die Gegenprobe sah den ungültigen Wert 32761. Der Messcache behielt diesen Zwischenstand, weil sein Schlüssel den gültigen tatsächlichen Span nicht hinreichend unterschied.
- Vorschlag: Im vorhandenen Umbruchweg den tatsächlichen gültigen Raster-/Spaltenumfang verwenden, einen noch nicht eingetragenen Knopf abwarten und den gültigen Span im bestehenden Messschlüssel berücksichtigen. Keine zusätzliche feste Kartenbreite, zweite Layoutdefinition oder neue Timerkette. Den echten Start- und Rückweg mit tatsächlicher Schrift 9/14 und sechs Sprachen prüfen, einschließlich XYZ-Querzeile, Höhe 1200→700→1200 und unterster sichtbarer Handlung.
- Wirkung beim Kunden: Eine eigentlich ausreichend breite Hauptaktion wird unnötig zweizeilig und hoch. Beim echten Wechsel von schmaler Ansicht mit kleiner Schrift zur großen Ansicht mit großer Schrift kann dieser überhöhte Zustand trotz genügend Platz erhalten bleiben; die Karte und ihr Rollbedarf zeigen dadurch vermeidbare zusätzliche Höhe.
- Stand: offen RM-747; Fix `11f44ba88` (welle4 `e68ca22cb`), aber die Folge schmal/9 pt → groß/14 pt → schmal/9 pt ist im finalen Lauf nicht gefahren.

### FD-59 Innere Fallfrist des Dateiprüfstands lässt untergeordnete Prozesse zurück

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: file_acceptance.run
- Prüfpunkt: 9, 19
- Beleg: probelauf-zwei-pruefstand-fix-codex.md, delivery-fd59.json und F:/tmp-suche/koord-codex/merge-fd59/evidence.md: vier echte Windows-Ketten aus Launcher, Interpreter und Helfer, Modi normal/nonzero/timeout/exception. fd59-red: 4 rot, Exit 1; Timeout ließ Helfer PID 73148 zurück, Ausnahme PID 64760. Normalende und Exit 7 waren bereits korrekt, ihre roten Assertions betrafen fehlende explizite Startoptionen. fd59-green: 4 grün, Exit 0; fehlende Restprozesse per Betriebssystem geprüft. Endgültiger Paket- und Integrationsanschluss jeweils 142 bestanden/5 Fensterfälle abgewählt, Exit 0, Statik Exit 0. Vorhandener count_new_windows auf vier echten Ketten: 4 grün, Befehl und Zähler Exit 0, 0 neue sichtbare Fenster/0 Konsolenfenster. Prozess-/Profilmarken in fd59-process-records.json; eigene Restprozesse bei Lieferung leer.
- Ursache: Prüfstandfehler in tools/file_acceptance.py, run(): Die innere Fallfrist beendete nur den direkt gestarteten Launcher. Auf Windows blieb dessen untergeordnete Interpreter-/Helferkette bei Timeout und Ausnahme im Warten bestehen. Die öffentliche Prozessgruppe war an dieser inneren Grenze noch nicht angeschlossen. Der neue Import von app.core.process benötigt zudem den eigenen ROOT unbedingt zuerst in sys.path, auch wenn dort vorher ein fremder Eintrag stand.
- Vorschlag: Vorhandene process_group_options(no_window=True), no_error_dialogs und terminate_process_tree im bestehenden run-Rumpf verwenden. Den zugehörigen Baum bei Timeout oder Ausnahme beenden, solange seine Kante besteht; keine zweite Prozessverwaltung. ROOT vor dem neuen Kernimport unbedingt vorn eintragen. Tatsächliche Exitwerte, Ausnahme, Timeoutstatus, Falldateien, Wiederaufnahme und sechs weitergegebene Profile unverändert erhalten. Normale Rückkehr und Exit 7 als Gegenfälle belassen.
- Wirkung beim Kunden: Ein abgebrochener Prüffall endet nur scheinbar vollständig. Zurückgebliebene Interpreter oder Helfer können nachfolgende Fälle und Prozessnachweise verunreinigen. Das ist ein Prüfstandfehler; hieraus wird kein Fehler des Produkt-Exportwegs oder der eigentlichen Anwendung abgeleitet.
- Stand: offen RM-737; Fix `bc376abc0` (welle4 `c9505aac2`, Rottest 4 rot), aber der finale Lauf hatte weder Zeitüberschreitung noch Ausnahme und nutzt den Einzelfallweg statt `file_acceptance.run` — die innere Frist ist ungemessen.

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
- Stand: offen RM-741; Fix `f6b0f53f2` (welle4 `4521cf8ff`), aber der finale Lauf klappt „Weitere Werte“ der Maßgruppe nie auf (001, Schritte 0–104) — ungemessen.

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
- Stand: offen RM-741; trotz Fix (`48adcd982`, `1e37ebc10`, welle4 `d4e7305f3`) decken im finalen Lauf Griffkörper und Achspfeile die gewählte Bohrung (001, 016, 019), Stufe B G9 offen beider Prüfer (D4).

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
- Stand: offen RM-741; Fix `a408a0620` (welle4 `26b66508e`), aber der finale Lauf zieht keinen Langlochgriff, die freistehende Maßzahl erscheint nicht — ungemessen.

### FD-74 Prüfstand prüft den Knopftreffer vor der nötigen Mausbewegung

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Funktionsprüfstand, Bereitschaft vor einem Knopfklick
- Prüfpunkt: 8
- Beleg: fix-massgruppe-front-codex.md, native-runner-v3/runs/run-20261013T203830058Z. Die echte DE-Folge erfüllt 22 Bedingungen einschließlich gehaltener Maßkartenzüge und dreier Feldhilfen. Danach liegt ein tatsächliches qtooltip_label über dem künftigen Abbrechen-Ziel. click_button fragt widget_under vor QtPorts.press und dessen öffentlicher Mausbewegung ab und lehnt ab. Kein Abbrechen-Press, kein Nachbedingungsfehler und kein Timeout. Cursorort und Entstehungstakt dieses späteren Tooltips wurden am Abbruch nicht gemessen; keine solche Behauptung.
- Ursache: Die bisherige Bereitschaft prüft den zukünftigen Treffpunkt, ohne zuvor den tatsächlichen Mausort dorthin zu bewegen und Qt den natürlichen Zustellungs-/Tooltipabbau zu erlauben. Ein verschachteltes processEvents in click_button würde den bereits vorgemerkten StepMachine-Folgeschritt vor dem aktuellen Klick ausführen können.
- Vorschlag: Im bestehenden Walk.stable zuerst öffentlich zum aktuellen Ziel bewegen und im nächsten regulären Takt Ziel, Sichtbarkeit, Aktivierung, Geometrie und Treffer frisch prüfen. Bei geändertem Ziel erneut bewegen. Benannte und per Getter aufgelöste Knöpfe benutzen denselben Weg; click_button bleibt abschließender synchroner Zustands-/Trefferwächter. Vorhandene Fristen unverändert, keine gezielte Tooltipunterdrückung.
- Wirkung beim Kunden: Die Abnahme kann einen normal bedienbaren Kundenweg vor dessen Klick abbrechen. Ein kaputter Abbrechen-Knopf der Anwendung ist damit nicht belegt.
- Stand: offen RM-737; Fix `f749bdc61` (welle4 `bc2d5e20c`, Rottest 1 rot), aber die Lage — eine Kurzhilfe über dem Klickziel nach Feldhilfen — kommt im finalen Lauf nicht vor.

### FD-75 Erneute Fensterplatzierung trennt gemessene Clientfläche und Aufnahme

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Funktionsprüfstand, wiederholter Aufbau auf demselben Bildschirm
- Prüfpunkt: 9, 19
- Beleg: fix-massgruppe-front-codex.md und native-runner-v3/runs/run-20261013T210714907Z auf bc2d5e20c376e5d9003c1c1d8058033a93ca427f. Alle sechs Sprachen laufen funktional regulär durch. Bis Bild020 stimmen QWidget-Client/contentsRect und grabWindow mit 2560 × 1369 überein; ab dem nächsten FunctionFlow.prepare melden Client und contentsRect 2560 × 1392, die PNGs bleiben 2560 × 1369. Die letzten 23 Pixel einschließlich Statuszeile fehlen sichtbar, unabhängig von D4, D8 und Root gelesen. Kein bloßer Unterschied zwischen Fensterrahmen und Client und kein bewiesenes Abschneiden am physischen Monitorrand.
- Ursache: place_window ruft bei jeder Vorbereitung erneut setGeometry(availableGeometry) und showMaximized auf, auch wenn das Fenster bereits auf demselben Schirm maximiert ist. Der zweite Aufbau überschreibt damit den gespeicherten QWidget-Clientumfang. Die native Gegenprobe bestätigt einen unveränderten Win32-Rahmen und tatsächlichen Client von 2560 × 1369; ausschließlich QWidget und contentsRect springen beim zweiten Originalaufbau auf 2560 × 1392. Kein physischer Monitorbeschnitt.
- Vorschlag: Wiederholte Maximierung am bereits gewählten Schirm idempotent behandeln; beim ersten Aufbau, Monitorwechsel oder Wechsel zur ausdrücklichen Größe den nötigen Normalzustand herstellen und den bisherigen Platzierungsvertrag erhalten. Aufnahme und tatsächliche Clientfläche gegenprüfen, einschließlich vollständiger Statuszeile. Kein Zuschneiden, keine erfundenen Sollpixel und keine Änderung der Bildschirm-/DPI-Untergrenzen.
- Wirkung beim Kunden: Prüfstandsmessung und sichtbarer Bildbeleg beschreiben unterschiedliche Flächen. Die bereits innerhalb des Bilds belegten Kartenaktionen bleiben gültig, eine vollständige Fensterabnahme kann daraus nicht entstehen. Kein Fehler am eigentlichen Kunden-Statusinhalt belegt.
- Stand: offen RM-737; Fix `a0d5ae491` (welle4 `9dc38e79f`, Rottest 5 rot), aber im finalen Lauf platziert jeder Prozess das Fenster nur einmal — der wiederholte Aufbau ist ungemessen.

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
- Stand: offen RM-745; kein Fix, der finale Lauf zeigt den Fund weiter (043–048 V3 Fund an allen sechs Zeilen, Stufe B offen, D8).

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
- Stand: behoben `377f1b552`, Testbau `cbc883304`, Nachzug `c5b25728f`, Themenleck zentral über `bf3c6d5e8`; in welle4 `b4e515c7b`, gezielt 580 grün am gemergten Stand. Schlussreview D0: Grifffall im Kundenthema `dabd95e26` (ohne `marked.append(grip)` rot), Changelog 0.6.1 `37801525b`, der letzte Rückfall der Notanordnung legt ein Feld eher über ein anderes als auf die Karte `ccb9bd87f`.

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
- Funktion: `statusbar`
- Prüfpunkt: 6
- Beleg: `F:\tmp-suche\urteile-d04-claude\crops\status.png`: Szene `merkmal.hole.exakt` ohne Änderung erst 11 g · 20 min (037–042 countersink_hole), später 8,9 g · 14 min mit „−2,2 g seit dem letzten Schritt“ (detect_region, alle Sprachen), ohne dass ein Schritt dazukam; dieselbe Ausgangsszene 18 g · 32 min in 004, 007, 016, 019 gegen 14 g · 23 min in 001 (d04 Nr. 3 b, c).
- Ursache: am Code belegt, dass die Zahl nicht nur nach einem Schritt neu entsteht: `_update_facts` läuft nach jeder Auswertung und noch einmal, wenn die Druckgrundlage des gewählten Prozesses eintrifft (`main_window.py:26382`), dann mit anderen wirksamen Einstellungen; `PrintFacts.show_estimate` vergleicht jede neue Schätzung mit der vorigen und nennt die Differenz „seit dem letzten Schritt“ (`facts.py:125–149`). Dass im Lauf genau die Grundlage die Zahl verschob, ist naheliegend, nicht gemessen.
- Vorschlag: Die Differenz nur zwischen zwei Dokumentständen mit derselben Rechengrundlage bilden; ändern sich die Einstellungen, wird der Vergleichswert still neu gesetzt. Die Zahl erst zeigen, wenn die wirksamen Einstellungen feststehen, oder als vorläufig kennzeichnen.
- Wirkung beim Kunden: Die Zeile meldet eine Ersparnis durch einen Schritt, den es nicht gab, und dieselbe Szene zeigt je nach Zeitpunkt andere Gramm und Minuten.
- Stand: offen RM-737

### FD-90 Die Zahlenzeile der Statusleiste wird abgeschnitten

- Art: Gestaltung
- Schwere: leicht
- Funktion: `statusbar`
- Prüfpunkt: 9
- Beleg: Lauf 001/01-vorher.png „14 g ·“; detect_region 037–042: Summe links abgeschnitten („· 14 min“), die deutsche Differenz endet in „Schrit…“ (`F:\tmp-suche\urteile-d04-claude\crops\status.png`, d04 Nr. 3 a).
- Ursache: offen; Statusmeldung und Zahlenzeile teilen sich die Statusleiste, und die Breite der Zahlenzeile folgt ihrem Text nicht verlässlich.
- Vorschlag: Mindestbreite aus beiden Texten der Zeile; gekürzt wird zuerst die Statusmeldung.
- Wirkung beim Kunden: Material und Dauer sind nur zum Teil lesbar.
- Stand: offen RM-749

### FD-91 Die Kopfzeile kürzt den Druckernamen trotz freier Fläche

- Art: Gestaltung
- Schwere: leicht
- Funktion: `header`
- Prüfpunkt: 9, Z6
- Beleg: Lauf 007/flaeche-skalierung.png (`F:\tmp-suche\urteile-d04-claude\crops\007-kopf-rechts.png`) und 013/flaeche-skalierung.png bei 1920 × 1009: „Elegoo …rbon 2 · FDM“, links davon breite freie Fläche (d04 Nr. 4, d10 Nr. 2).
- Ursache: offen.
- Vorschlag: Das Profilfeld der Kopfzeile nach seinem Inhalt bemessen und erst kürzen, wenn die Zeile voll ist; der volle Name im Tooltip.
- Wirkung beim Kunden: Auf der kleinsten Arbeitsfläche ist der gewählte Drucker nicht lesbar.
- Stand: offen RM-749

### FD-92 Die Bettmaßzahlen folgen der Anzeigeeinheit nicht

- Art: Verständlichkeit
- Schwere: mittel
- Funktion: keine Zeile: Druckbett in der 3D-Ansicht
- Prüfpunkt: 9
- Beleg: Lauf 004/flaeche-zoll.png (`F:\tmp-suche\urteile-d04-claude\crops\004-bett.png`): „0“, „100“ ohne Einheit bei Zollanzeige; 006/flaeche-zoll.png: „50“ (`F:\tmp-suche\urteile-d10-claude\crops\006-bett50.png`); Kopf und Baum zeigen Zoll (d04 Nr. 5, d10 Nr. 1).
- Ursache: belegt: `bed_scale` schreibt `f"{value:.0f}"` in Millimetern, ohne Anzeigeeinheit und ohne Einheitenzeichen (`viewport.py:2808–2812`). Zwilling zu FD-69 (Farbe derselben Zahlen), andere Ursache.
- Vorschlag: Die Zahlen über den Längenformatter der Anzeige setzen, Schrittweite passend zur Einheit, das Einheitenzeichen einmal an der Skala; beim Einheitenwechsel neu zeichnen.
- Wirkung beim Kunden: In Zoll liest er Millimeterzahlen ohne Hinweis und schätzt Größe und Lage falsch ein.
- Stand: offen RM-737; Schwere von leicht auf mittel wie die Zwillinge FD-61 und FD-125, weil die Anzeigeeinheit zugesagt ist (Prüfpunkt 9; Review RD-6).

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
- Funktion: `slot_hole`, `feature.apply`, `feature.in_view`, `feature.every`, `dialog:local_recognition_dialog`, `group_pattern`, `arrange_bed`, `check_collisions`, `orient_for_print`, `finding.action:install`, `finding.action:keep_saved_parts`, `finding.action:recognize_fully`, `dialog:body_choice_dialog`, `dialog:seal_path_dialog`, `dialog:step_values_dialog`, `dialog:binding_dialog`, `dialog:calibration_dialog`, `dialog:counterpart_dialog`, `dialog:parameter_dialog`, `dialog:recipe_dialog`, `dialog:slicer_filament_dialog`, `meldung:_pick_colour`, `meldung:_replacement_slot`, `meldung:action_counterpart`, `menu:parameters.edit`
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
- Funktion: keine Zeile: Funktionsprüfstand, Textmessung
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
- Funktion: keine Zeile: Funktionsprüfstand, Tastatur und Zugänglichkeit
- Prüfpunkt: 10
- Beleg: Lauf 001 und 002: Ketten ohne Zielhandlung, Glieder „FittedScroller“ und „DialogScrollArea“; Stufe A „2 Tab-Schritte, erfüllt“ beziehungsweise „erfüllt“ (zweit Nr. 3).
- Ursache: belegt: `_point_10` prüft nur Rücksprünge innerhalb der Fläche, leere und doppelte Namen (`function_points.py:615–655`); `name_of` fällt auf den Klassennamen zurück (`function_capture.py:474–477`), der als Name zählt, und Glieder außerhalb werden nur weggefiltert.
- Vorschlag: P10 verlangt, dass die Kette die Zielhandlung der Zeile erreicht, bevor sie die Fläche verlässt; ein Klassenname zählt als fehlender Name.
- Wirkung beim Kunden: Ein unbedienbarer Tastaturweg wird als erfüllt abgehakt.
- Stand: offen RM-737

### FD-142 Weitere Doppelklicks in Tests und Werkzeugen lassen die Maustaste gedrückt

- Art: Zwillinge
- Schwere: leicht
- Funktion: keine Zeile: Prüfanschlüsse und Videowerkzeug
- Prüfpunkt: 19
- Beleg: Neben dem in FD-83 behobenen `QtPorts.press` rufen `tests/test_start_screen.py:461`, `:957`, `:966` und `tools/make_workshop_videos.py:2462` `QTest.mouseDClick` ohne anschließendes Loslassen auf; in `make_workshop_videos.py` fehlt zusätzlich der Klick davor (`F:\3D Druck\output\konsolidierung-2026-10-12\fd83-claude.md`).
- Ursache: `mouseDClick` schickt nur das Doppelklickereignis; Qt hält die linke Taste danach bis zum nächsten Klick im selben Prozess für gedrückt.
- Vorschlag: Dieselbe Folge wie der Kunde (Klick, Doppelklick, Loslassen) an allen Stellen; als Wächter eine Fixture, die nach jedem `qt_app`-Fall `QGuiApplication.mouseButtons() == NoButton` zusichert.
- Wirkung beim Kunden: Kein Produktfehler; im selben Prozess sehen Bewegungen bis zum nächsten Klick wie ein Zug aus, in Tests wie in den Werkstattvideos.
- Stand: offen RM-737

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
- Stand: offen RM-737

### FD-145 Ob die Übereinstimmung gepoolt oder je Paket gilt, war nicht festgelegt

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 19
- Beleg: Konzept §4 (Urteil und Schwere) gegen §10 (Abnahme); die Abhaklisten markieren je Paket 7, 14 und 7 Punkte, gepoolt sind es 11 (`F:\tmp-suche\koord-claude-1014\ue.txt`); bei zwei bis drei Zeilen je Paket heißt 90 % „keine Abweichung“.
- Ursache: Konzept und Prüfstand nennen die Grundmenge der Quote nicht.
- Vorschlag: Entschieden (Koordinator, 15.10.): gepoolt je Prüfpunkt über alle Pakete einer Urteilsrunde ist bindend, je Paket Auskunft; Konzept §4 und `report` erhalten den Rundenwert.
- Wirkung beim Kunden: Kein Produktfehler; die Abnahme maß bei kleinen Paketen nichts.
- Stand: offen RM-737

### FD-146 E1 bis E3 gelten als erfüllt an Wegen, die vor dem Beispielziel enden

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: E1, E2, E3
- Beleg: Alle Sprachflächenzeilen haben keine Zeilenspezifikation (`F:\tmp-suche\abweichungen-claude\zeilen.txt`); Stufe A meldet trotzdem „0 Eingaben, erfüllt“ (`stufe-a-paare.txt`, Abweichungen 01, 07–09, 11–15); neun Abweichungen gehen darauf zurück.
- Ursache: `_e1`, `_e2`, `_e3` (`tools/function_judges.py`) prüfen weder Spezifikation noch Übernahmeschritt; der E2-Paketanteil zählt diese Zeilen mit.
- Vorschlag: E1–E3 nur an einem Weg, der das Beispielziel erreicht hat; sonst nicht gemessen, *offen* mit Paket-RM; Gegenprobe Sprachflächenprotokoll ohne Spezifikation.
- Wirkung beim Kunden: Kein Produktfehler; Schrittzahlen galten als gemessen, die es nicht waren.
- Stand: offen RM-737

### FD-147 Englisch übersetzt „Überstand“ und „Überhang“ beide mit „Overhang“

- Art: Verständlichkeit
- Schwere: leicht
- Funktion: `finding.action:place_on_bed`
- Prüfpunkt: V1
- Beleg: `app/i18n/locales/en.json` Befund „An object sits below the build plate … Overhang: 10.00 mm“ (Fall 044, Ausschnitt `F:\tmp-suche\abweichungen-claude\crops2\pob-6spr.png`); dazu „overhang“ für Überstand an Haken, Rastnase und Widerhaken.
- Ursache: Zwei deutsche Begriffe teilen im englischen Katalog ein Slicer-Wort mit anderer Bedeutung.
- Vorschlag: Den Überstand unter dem Bett neu übersetzen (etwa „Below plate“), die Bausteintexte auf „protrusion“; alle Kataloge auf dieselbe Verwechslung prüfen.
- Wirkung beim Kunden: Ein englischsprachiger Kunde liest einen Überhang, wo ein Teil unter dem Bett steckt.
- Stand: offen RM-745

### FD-148 V4 nimmt jede geschriebene Vorhersage an, auch eine nachträgliche

- Art: Fehler
- Schwere: leicht
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: V4
- Beleg: `tools/function_report.py` prüft an V4 nur, dass `prediction` nicht leer ist; die Fälle 29, 36 und 37 wurden so als *gut* angenommen.
- Ursache: Die Vorhersage ist nicht an den Zeitpunkt vor dem Klick gebunden.
- Vorschlag: Feld `prediction_bound` (Pfad und SHA256 der vor dem Klick freigegebenen Vorhersage); ohne Bindung ist V4 *offen*; Vorhersagetor im Fallprozess auch im Sprachdurchgang.
- Wirkung beim Kunden: Kein Produktfehler; V4 konnte ohne echte Vorhersage gelten.
- Stand: offen RM-737

### FD-149 Der Sperrgrund des grauen Knopfs im Fehlfall steht nicht im Bild

- Art: Fehler
- Schwere: leicht
- Funktion: `finding.action:place_on_bed`
- Prüfpunkt: 7
- Beleg: `cases/002/04-fehlfall.png` (Ausschnitt `F:\tmp-suche\abweichungen-claude\crops2\002-04-karte.png`): unter „Auf das Bett setzen“ nur der Wirkungssatz; der Sperrgrund steht nur in `function.json#messages`, beide Prüfer stützen Punkt 7 darauf.
- Ursache: Der Prüfstand nimmt Tooltip und Sperrgrund eines grauen Elements nicht als Bild auf.
- Vorschlag: Sperrgrund bzw. Tooltip des grauen Elements als eigenes Bild aufnehmen; eine JSON-Eigenschaft ersetzt kein angezeigtes Bild.
- Wirkung beim Kunden: Kein Produktfehler; Punkt 7 wurde an einer nicht gezeigten Zeile geurteilt.
- Stand: offen RM-737

### FD-150 Prüfpunkt 11 findet außerhalb des Registers und an Bildtexten keine Fundstelle

- Art: Fehler
- Schwere: leicht
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 11
- Beleg: `tools/function_report.py` sucht Fundstellen nur über Registernamen und entfernt `alt` aus dem Websitetext; `resize_hole` hat `website: []` trotz `website/funktionen.html` (Abschnitt Bohrungen).
- Ursache: Website- und Handbuchstellen hängen am Registernamen; Zeilen ohne Op und Bildtexte fallen heraus.
- Vorschlag: Zeilenspezifikation um `manual` und `website` je Zeile; `_point_11` misst damit auch Nicht-Operationen; `alt` und `title` zählen zum Websitetext.
- Wirkung beim Kunden: Kein Produktfehler; Versprechen ohne Fundstelle blieben ungeprüft.
- Stand: offen RM-737

### FD-151 auto_split hat kein Beispielziel, und die Szene erlaubt kein Teilen

- Art: Fehler
- Schwere: leicht
- Funktion: `command:edit.auto_split`
- Prüfpunkt: G9
- Beleg: Fall 043 (Ausschnitt `F:\tmp-suche\abweichungen-claude\crops2\043-autosplit.png`): „Dieses Objekt passt bereits auf das Bett“; die Spezifikation fehlt. Zwilling zu FD-101.
- Ursache: Szenenkatalog und Zeilenspezifikation decken nur den Fall „passt bereits“.
- Vorschlag: Spezifikation mit Beispielziel („passt bereits“ als Rückmeldung) und ein zweiter Fall mit zu großem Körper für Vorschlag und G9.
- Wirkung beim Kunden: Kein Produktfehler; G9 und E1–E3 an auto_split waren nicht messbar.
- Stand: offen RM-737

### FD-152 I1 „jede Art“ ist aus dem Protokoll nicht prüfbar

- Art: Fehler
- Schwere: leicht
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: I1
- Beleg: `cases/002/function.json`: `hover_labels` hat einen Eintrag, ein Feld der erkannten Arten fehlt.
- Ursache: Das Protokoll hält nicht fest, welche Merkmalsarten die Erkennung an der Szene liefert.
- Vorschlag: Protokollfeld `recognized_kinds` neben `hover_labels`; `_i1` vergleicht beide.
- Wirkung beim Kunden: Kein Produktfehler; die Bauplanzusage zu I1 war nicht prüfbar.
- Stand: offen RM-737

### FD-153 Funde mit integriertem Fix stehen in der Funddatei weiter offen

- Art: Aufräumen
- Schwere: leicht
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 19
- Beleg: FD-35, FD-37, FD-38, FD-43, FD-61 und FD-64 standen beim gemeinsamen Lauf auf „offen RM-…; … integriert“, obwohl ihre Fixe Vorfahren von `2ec37b23b` waren; die Abweichungen 16, 18 und 24 hängen daran. Nachgezogen hat sie `a00233340`, vor dem Eintrag dieses Funds.
- Ursache: Der Stand wurde nach dem gemeinsamen Lauf nicht nachgezogen.
- Vorschlag: Vor jeder Urteilsrunde den Stand der Funde nachziehen, deren Fix im Laufkopf liegt, mit Nachweis an ihrer Zeile.
- Wirkung beim Kunden: Kein Produktfehler; *gut nach Fix* war eine Lesart statt einer Folge der Funddatei.
- Stand: offen RM-737; die sechs Einzelfälle sind nachgezogen (`a00233340`), offen ist der Prozessschritt vor jeder Urteilsrunde.

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
- Stand: offen RM-737

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
- Stand: offen RM-737

### FD-159 Die Anleitungsnavigation verwirft erreichbare Ziele unter einer verschachtelten Liste

- Art: Fehler
- Schwere: mittel
- Funktion: keine Zeile: Gemeinsame Anleitungsnavigation und Funktionsaufnahme
- Prüfpunkt: 1
- Beleg: Nativer Lauf am echten Fenster auf welle4 `7d978c4ee`, Fall 032 EN: `filament.picker` und `filament.section` enden „nicht auffindbar: Rollanschlag oder kein geeigneter Radschritt“, obwohl der Rollbalken 170 px Restweg hat und 132 px fehlen; zwei lesende Diagnoseläufe (`output/konsolidierung-2026-10-12/native-d0-claude.md`, Nachweis 1).
- Ursache: Die Trefferprobe in `guide_targets._scroll_needed` trifft in der Mitte der Sichtfläche eine verschachtelte Liste (`_ListScroller`) statt des äußeren Rollbereichs und verwirft jeden Rollschritt; Regression aus FD-77.
- Vorschlag: Den Rollschritt an den Rollbereich geben, der das Ziel enthält und weiter rollen kann, nicht an das Widget unter der Mitte; Gegenprobe mit verschachtelter Liste.
- Wirkung beim Kunden: Die Anleitung kommt am Filamentwähler nicht ans Ziel, obwohl der Kunde ihn selbst ins Bild rollen kann.
- Stand: offen RM-737

### FD-160 Nach „Abbrechen“ der Maßgruppe steht der Fokus auf dem Kartengriff „Objekte“

- Art: Einfachheit
- Schwere: leicht
- Funktion: `resize_hole`
- Prüfpunkt: 10
- Beleg: Native DE-Maßkartenfolge auf `7d978c4ee` (`native-d0-claude.md`, neuer Punkt 2): nach *Abbrechen* Fokus auf dem Kartengriff „Objekte“, nach *Übernehmen* und Undo dagegen in der 3D-Ansicht.
- Ursache: offen; Abbrechen gibt den Fokus nicht an die Ansicht zurück, aus der die Maßgruppe kam.
- Vorschlag: Alle drei Ausgänge der Maßgruppe geben den Fokus an dieselbe Stelle zurück (die Ansicht).
- Wirkung beim Kunden: Wer nach Abbrechen eine Taste drückt, bedient die Objektkarte statt der Ansicht.
- Stand: offen RM-737

### FD-161 Eine geänderte Bohrung springt im Objektbaum ans Listenende

- Art: Einfachheit
- Schwere: leicht
- Funktion: `resize_hole`
- Prüfpunkt: 3
- Beleg: Native DE-Maßkartenfolge auf `7d978c4ee` (`native-d0-claude.md`, neuer Punkt 3); am Stand vor D0 genauso.
- Ursache: offen; der Baum ordnet ein geändertes Merkmal neu ein statt an seiner Stelle.
- Vorschlag: Ein geändertes Merkmal behält seinen Platz im Baum.
- Wirkung beim Kunden: Nach jeder Änderung sucht der Kunde die Bohrung neu.
- Stand: offen RM-737

### FD-162 Die Undo-Blase verdeckt die Sammelzeile, und die Statuszeile meldet danach weiter „zurückgenommen“

- Art: Gestaltung
- Schwere: leicht
- Funktion: `resize_hole`
- Prüfpunkt: 9
- Beleg: Native DE-Maßkartenfolge auf `7d978c4ee` (`native-d0-claude.md`, neuer Punkt 4): Die Blase steht 6,7 s über Wiederwahl, Aufklappen und Tippen und verdeckt die Zeile des Sammelhakens; nach der nächsten Übernahme meldet die Statuszeile weiter „zurückgenommen“. Zwilling zu FD-108 (Quittung am Zeiger über dem Bericht).
- Ursache: offen; die Quittung kennt weder die Lage der Karten noch den nächsten Schritt.
- Vorschlag: Mit FD-108 eine Regel für Quittungen: nie über einer Karte, weg mit dem nächsten Schritt; die Statuszeile folgt dem letzten Schritt.
- Wirkung beim Kunden: Die Blase deckt die nächste Bedienung zu, und die Statuszeile widerspricht dem Stand.
- Stand: offen RM-737

### FD-163 Prozesse des Prüfstands schreiben kein Dateiprotokoll

- Art: Fehler
- Schwere: leicht
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 19
- Beleg: Native Läufe auf `7d978c4ee` (`native-d0-claude.md`, Nachweis 3 und neuer Punkt 5): Die Zeile, mit der FD-154 auf einen Arbeiter wartet, steht in keinem Protokoll des Falls, weil nur `main()` das Dateiprotokoll einrichtet; die Zusage in `fd154-claude.md` trifft so nicht zu.
- Ursache: Der Fallprozess richtet das Protokoll der Anwendung nicht ein.
- Vorschlag: Der Fallprozess richtet dasselbe Dateiprotokoll ein wie `main()`, im isolierten Profil des Falls.
- Wirkung beim Kunden: Kein Produktfehler; Ursachen in Fallprozessen bleiben ohne Protokoll.
- Stand: offen RM-737

### FD-164 Die nativen Läufer liegen außerhalb des Repositorys und starten ohne Siegelprüfung

- Art: Stabilität
- Schwere: mittel
- Funktion: keine Zeile: Prüfanschlüsse des Prüfstands
- Prüfpunkt: 19
- Beleg: Die DE-Maßkartenfolge läuft über `F:\tmp-suche\fix-massgruppe-front-codex\native-runner-v3\Run-Language.ps1`, der Fall 032 über `F:\tmp-suche\fix-projektwechsel-crash-codex\final_d0_cli.py`, beide außerhalb des Baums; im Läuferordner lag eine spätere, ungesiegelte Ergänzung, die `Run-Language.ps1` ohne Prüfung gefahren hätte, und ihre Cursorlesung zielt auf das Hauptfenster statt auf das eigene Fenster der Maßkarte (`native-d0-claude.md`, Nachweis 2b und neuer Punkt 6).
- Ursache: Die nativen Anschlüsse entstanden als Sitzungswerkzeuge und wurden nie ins Repository übernommen.
- Vorschlag: Die nativen Läufer (Fallbrücke, Maßkartenfolge, Bindung und Siegel) nach `tools/` übernehmen, mit Siegelprüfung vor dem Start, als Schritt in `/erzeugen` (Konzept §8, §10); die Cursorlesung am Fenster des Druckempfängers.
- Wirkung beim Kunden: Kein Produktfehler; der Wiederholungslauf beim Release wäre auf keinem frischen Stand reproduzierbar.
- Stand: offen RM-737
