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
Auswertung `output/konsolidierung-2026-10-12/auswertung-probelauf-d0.md`; FD-4 bis
FD-6 folgen mit ihrem Fix). Leichte Funde einer Zeile behebt ihr Paket; mittlere und
die systemischen leichten behebt D0.

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
- Ursache: `app/ui/dialogs.py` (`tr("Startwert", context="Kalibrierstand")`).
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
- Stand: offen RM-747

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
- Vorschlag: eigener Meldungsdialog im Hausstil — Titel, Ursache, Handlungen als Knöpfe, Symbol aus dem eigenen Satz.
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
- Stand: offen RM-737

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
- Stand: offen RM-737

### FD-25 Der Objektbaum verlangt mit einem Körper mehr Mindesthöhe, als er braucht

- Art: Gestaltung
- Schwere: leicht
- Funktion: `finding.action:place_on_bed`
- Prüfpunkt: 9
- Beleg: am echten Fenster mit einem Körper Mindesthöhe 183 gegen Wunschhöhe 81 Punkte; die Karte zeigt Leere unter dem Körper; gemeldet beim Fix von FD-23 (`fix-karten-raster.md`)
- Ursache: Die Mindestzeilenzahl des Objektbaums gilt auch, wenn weniger Zeilen da sind; `fenster.md` verlangt, dass die Mindesthöhe einer Karte ihre Wunschhöhe nie übersteigt.
- Vorschlag: Mindesthöhe aus den vorhandenen Zeilen, höchstens die Wunschhöhe; Test an einem und an vielen Körpern.
- Wirkung beim Kunden: Leere Fläche im Objektbaum, die der Ansicht Platz nimmt.
- Stand: offen RM-737
