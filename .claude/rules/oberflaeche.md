---
description: "Die Oberfläche allgemein — das Versprechen, eine Quelle je Auskunft, Texte über tr() und Texte für Kunden, Zahlen, gestufte Tiefe, Felder mit Namen, Fokus und Rahmen, Barrierefreiheit, Anzeigeeinheit, Tests am Fenster; Fenster, Grenzen, Ansicht, Wartezeit und Zeichenfläche stehen in eigenen Dateien"
paths:
  - "app/ui/**/*.py"
---

# Regeln für die Oberfläche

PySide6. Die Oberfläche benutzt `core`, nie umgekehrt; sie rechnet und ändert
keine Geometrie, sie ruft Ops auf (Regel 1, 2). Weitere Regeln laden mit ihren
Dateien: `fenster.md` (Fenster, Dialoge, Rückfragen, Verlauf, Prüfbericht,
Merkmalfenster), `grenzen.md` (Grenzen, was wo steht, Dialogvorderseite,
Zwillinge, Kürzel), `ansicht.md`, `griffe.md`, `kamera.md`, `wartezeit.md`,
`zeichenflaeche.md`, `uebersetzung.md`. Warum:
`konzepte/begruendungen/regel-oberflaeche.md`.

**Die Grenzen gelten für jeden**, auch wo `grenzen.md` nicht lädt: neun Menüs,
zwölf Zeilen je Menü, acht Umschalter, vier Felder vorn, ein Menüeintrag je
Operation. Wer eine Zahl erhöht, begründet es im Commit
(`tests/test_interface_limits.py`).

## Das Versprechen

**Nichts ist endgültig.** Jede Handlung ist eine Op, jede Op rücknehmbar, jeder
Wert nachträglich änderbar — keine Bestätigungsdialoge vor rücknehmbaren
Handlungen, kein „Möchten Sie wirklich“, keine Sackgassen (Regel 19). Die
gewollten Ausnahmen stehen in `fenster.md` unter „Rückfragen“. Wer nur
hinsieht, wird nie gefragt.

## Eine Auskunft, eine Quelle

Was Register oder Kern wissen — ob eine Handlung geht und warum nicht, welche
Felder sie hat, wann ein Feld wirkt —, liest die Oberfläche dort: Eine zweite
Aufzählung weiß beim nächsten Zuwachs die Hälfte, eine zweite Formulierung
läuft auseinander. Eine Fähigkeit (`requires_kind`, `applies_to`,
`depends_on`) steht im Register, alle Zugänge zu einer Auskunft fragen
dieselbe Funktion, und eine Sichtbarkeit oder Sperre setzt **eine** Stelle —
zwei Stellen gewinnen abwechselnd.

## Texte

Keine feste Zeichenkette — alles über `tr()`, deutsche Quelle, jeder Katalog
aus `app/i18n/locales/` zieht nach (Regel 20).

**Beschriftung und Doppelpunkt gehören in denselben Übersetzungsrahmen.**
Feste Titel stehen im vollständigen `tr()`-Satz; dynamische Namen und Werte
werden als Platzhalter übergeben (`tr("{name}: {value}", ...)`). So bestimmt
der Katalog auch die Abstände vor Satzzeichen, ohne Namen, Pfade oder Zahlen
zu verändern. `tests/test_translations.py` prüft direkte Zusammensetzungen
im Quelltext und die Ausgaben gemeinsamer Beschriftungshelfer.

**Auswahlwerte sind Schlüssel, keine Beschriftungen:** Der Name von `raised`,
`flat`, `linear` steht in `_CHOICE_NAMES` (`app/ui/labels.py`);
`tests/test_translations.py` lässt nur Selbstnamen durch (M4, 6x3, mm, x,
DejaVu Sans). Es gibt **eine** Namenstabelle — der Test prüft auch
`knowledge.print_fields.FIELDS` gegen sie, und eine dritte Liste von
Auswahlwerten wird dort eingehängt.

**Findet der Kunde die Sache im Slicer unter dem englischen Begriff, bleibt
er:** `skirt`, `brim`, `raft` mit „Skirt-Runden“, „Brim-Breite“,
„Raft-Schichten“, dazu Algorithmennamen (`gyroid`, `arachne`) — ein Wert, der
anders heißt als sein Feld, ist eine Fährte ins Nichts.

**Jedes Feld sagt, was es tut — und zwar alle**, sonst lernt niemand, dass es
hier Sätze gibt: die Druckeinstellungen über `note`, jeder Parameter jeder
Operation über seinen `doc`-Satz. Der Satz sagt, was der Wert bewirkt, nicht
den Titel noch einmal, und hängt an **beiden** Hälften der Zeile — man zeigt
auf das unverständliche Wort (`_editor` und `_label`; im Operationsdialog
`_explain` über `QFormLayout.labelForField`). Ist eine Zeile gesperrt, tragen
beide Hälften den *Grund* statt des Satzes. Dazu `accessibleDescription`
(Regel 18); ein eigener Tooltip bleibt, der Satz kommt dahinter. **Einen
`statusTip` tragen nur Menüaktionen** (Entscheidung Robert, RM-509): An Feldern
und Knöpfen wiederholte er den Tooltip; `test_status_tips_stand_only_at_menu_actions`.

**Auswahlwerte tragen je einen Satz** aus `_CHOICE_NOTES` — was der Wert
bewirkt und kostet. `explain_choices(box)` hängt ihn als ToolTipRole **und**
AccessibleDescriptionRole an, gelesen am rohen Schlüssel im `itemData`; nach
jeder Neubefüllung erneut aufrufen, `clear()` nimmt die Rollen mit. Ein
Schlüssel bedeutet überall dasselbe (`grid`: Füllung und Stützmuster);
`test_every_named_choice_also_says_what_it_does` hält Namen und Sätze
deckungsgleich, Selbstnamen stehen in keiner der beiden Tabellen. Die offene
Combo-Liste zeigt ToolTipRole von sich aus — anders als `QMenu` braucht sie
keinen Schalter.

**Ein Bild statt eines Worts, wo ein Wort nichts zeigt:** Texturmuster tragen
ihre Kachel aus `figures.texture_tile`, erkannt an den Werten des Feldes.

**Ein Fehler endet nie mit „fehlgeschlagen“** (Regel 17, §2.7): was nicht
ging, warum, was jetzt möglich ist — als anklickbare Handlungen. Kein
Stapelabzug, keine Adresse aus dem Code: `spoken_values` lässt `field` und
`constraint` einer `ValidationError` weg, ihre Übersetzung ist der Cursor im
Feld (`NewFilamentDialog.focus_field`). Titel und Detail in zwei Zeilen
(`problem_text`), nie „Titel.: Detail“. Wer im Satz eine Handlung nennt,
bietet genau sie an („Laden Sie den Stand neu“ → `RELOAD`), und jeder
Vorschlag ist ausführbar.

**Kein Wort, das nur ein Konstrukteur kennt, wo ein Neuling liest** — das Wort
aus seinem Slicer: Richtung (nicht Normale), Außenseiten angleichen, geschlossen
(nicht wasserdicht), auf einem Raster (nicht Voxelstufe), Vereinigen oder
Abziehen (nicht boolesch), jede Kante sichtbar (nicht Facetten), ohne Zufall
(nicht deterministisch). Begründet bleiben *Slot* im 3MF-Weg und *Rasterweite* hinter der Klappe.
*Bahnbreite* heißt dieselbe Druckgröße in Einstellungen, Befunden,
Wandstärkenleiter und Handbuch; die Übersetzungen verwenden den Namen des
Feldes (englisch *Line width*).
`test_wording::test_no_customer_text_uses_a_designer_word` hält die Wortliste
für Quelle und Englisch, `test_a_quoted_control_is_named_as_the_control_says`,
dass ein zitierter Knopf in jeder Sprache so heißt wie der Knopf.
Eine Druckeinstellung in einem Befund heißt, wie das Feld des Druckdialogs,
mit dem Wert, wie er dort steht (`print_settings_dialog.setting_title`,
`shown_value`) — nie Punktpfad oder `True`; ein Befund je Teil trägt dessen
`object_id`, damit der Klick es wählt (`writer.PART_SETTING_CODES`).

**Ein Text, der eine Grenze beschreibt, altert mit der Grenze.** Wer eine
Fähigkeit hinzufügt, sucht vorher die Sätze, die ihre Abwesenheit versprechen —
in Code, Katalogen, Website und Vertragstext, mit der Verneinung („nichts“,
„nie“, „kein“, „ohne“) als Suchbegriff.

**Beim Tauschen eines Katalogtexts muss der alte Schlüssel hinaus**
(`test_every_text_is_translated` prüft beide Richtungen, „no longer used“).

## Texte, die der Kunde liest

Oberfläche, Handbuch, Website, Changelog, Update-Fenster, Mails. Übersetzen:
`uebersetzung.md`.

- **Kurz und trotzdem verständlich** (Entscheidung Robert): ein, zwei Sätze —
  was ist, was zu tun ist, der Rückweg, wo es einen gibt (Strg+Z, „Diesen
  Schritt ändern“). Keine Nebensatzketten, keine doppelten Vorschläge; im
  Prüfbericht verdrängt jede lange Zeile die nächste. Jeder angefasste Text
  wird gekürzt, alle Kataloge ziehen mit — den Bestand nicht in einem Zug.
- **Die Länge hängt am Ort** (RM-509, `test_text_length.py`, Art nach
  Aufrufort): Befund 20 Wörter und zwei Sätze, Fehlerdetail 25/2,
  Bausteinänderung 20/1, Vorbehalt 20/2, erster Satz einer `doc` 15,
  Parameter-`doc` und Kurzhilfe 25/2, Ansage, Leertext und Tourschritt 20,
  Druckrat-Grund 60 Zeichen. Menü, Statuszeile, Palette und Dialogkopf zeigen
  nur den ersten Satz; geschnitten wird überall mit `surfaces.sentences`.
- **Nicht nach einem Sprachmodell klingen** (Entscheidung Robert; Kunden
  schreiben Robert persönlich). Die sieben Merkmale: nummerierte Listen, wo
  Fließtext reicht; Rückspiegeln dessen, was der andere schrieb; Dreierfiguren
  und Parallelismen („nicht X, sondern Y“); jeder Absatz endet auf einer
  Pointe; Bewertungsvokabeln („hochspannend“, „extrem wertvoll“);
  Gedankenstriche im Übermaß; der zusammenfassende Schlusssatz. Dagegen:
  kürzer, ruhig ein unfertiger Gedanke oder umgangssprachlicher Einwurf, ein
  Absatz ungerundet. Gilt auch im Gespräch mit Robert. Semikolon, die Formel
  „Nur …:“ und Fachwörter der Datenhaltung hält `test_wording` mit
  eingefrorenem Bestand (`tests/data/text_patterns.json`, RM-509).
- **Nach außen heißt es „Version“, nicht „Fassung“** (Entscheidung Robert) —
  ein zweites Wort lässt den Kunden einen Unterschied suchen. Intern (Commits,
  Roadmap, Konzepte, Regeln) darf „Fassung“ bleiben; sinngemäß für jedes zweite
  Wort neben einem eingeführten.
- **Eine Zahl trägt nur, wenn sie an der Sache des Kunden gemessen ist:** ein
  Messwert an seinem Modell („296 von 1130 Merkmalen“), eine Nebenwirkung, die
  er bemerkt („die Setup-Datei ist 23 Megabyte größer“), eine Zusage, die er
  prüfen kann. Keine Zählung behobener eigener Fehler, kein Umfang unserer
  Arbeit („31 von 37 Dialogen geprüft“), keine Zahl der Stellen, an denen eine
  Zusage neu eingelöst wurde: Der Kunde liest daraus, was bis gestern fehlte,
  und die Zahl veraltet mit dem nächsten Fund — das Verhalten zu beschreiben
  ist der bessere Satz. In `ROADMAP.md`, Commits und Karten bleibt die
  Fehlerzählung richtig.
- **Gewonnene Druckzeit als Anteil** (Entscheidung Robert): „rund 40 Prozent
  kürzer“ — „rund“, wenn an einem Modell gemessen —, nicht die Stunden eines
  fremden Modells. Rechenzeiten bleiben in Sekunden.
- **Die Neuerungen-Seite ist das Gestaltungsvorbild der Website** und wird
  nicht umgebaut, nur mitgeprüft (Entscheidung Robert;
  `tools/make_changelog.py`). Neue Abschnitte messen sich an ihr: Karten einer
  Reihe gleich hoch, Akzentrand für die Karte, die handeln lässt, keine halbe
  letzte Reihe, ein Gedanke je Karte, jeder Gedanke einmal.

## Zahlen

**Eine Zahl, eine Schreibweise — in beiden Richtungen.**

*Hinaus:* Der Kern schreibt mit Punkt; wer **anzeigt**, schickt die Zahl durch
`localised` (`app/ui/labels.py`) und setzt kein Komma fest ein. `localised`
tauscht **jeden** Punkt — um Pfade, Adressen und Versionsnummern nimmt man
`localised_value`. Zwei Wächter von zwei Seiten:
`test_no_number_reaches_the_user_past_the_localisation` liest den Quelltext
(f-Strings mit Formatangabe; `"%.2f" %`, `.format()` und ein nacktes
`f"{wert}"` sieht er nicht), `test_no_visible_text_writes_a_decimal_point` jeden
sichtbaren Text und Tooltip des gebauten deutschen Fensters (Pfade, Adressen und
Versionsnummern lässt er durch).

**Die Einheit gehört in den Wert**, nicht in Satz, Beschriftung oder
Katalogtext: Länge, Volumen und Fläche folgen der Umschaltung (§19.3) über
`labels.length`, `labels.volume`, `labels.area`, ein Befundwert über
`value_text` (`_VALUE_UNITS`) statt `value_label` — selbst angeschrieben kann
eine Zeile nicht in Zoll sprechen.

*Herein:* Ein Zahlenfeld ist eine `NumberSpin` (oder `LengthSpin`), **kein
nacktes `QDoubleSpinBox`** — Qt liest den Punkt in deutscher Anzeigesprache als
Tausendertrennung, aus „12.5“ wird still 125. Leseregel: **das letzte
Trennzeichen ist das Dezimaltrennzeichen**, alle davor trennen Tausender; nur
„1.000“ ohne Nachkomma bleibt zweideutig (eins), und was gelesen wurde, steht
danach im Feld. **Der getippte Text bleibt unangetastet:** `validate` prüft
beide Lesarten und gibt ihn unverändert zurück, gelesen wird in
`valueFromText`. Als Typprüfung bleibt `QDoubleSpinBox` richtig.

**Eine Grenze lehnt ab, sie kürzt nicht.** Die **Parameterleiste** und die Zahlenfelder des
**Operationsdialogs** (`op_dialog.ValueField`, auch die Stückzahl) tragen ein
`labels.BoundedSpin`: Eine Zahl jenseits der Grenzen bleibt markiert stehen,
`valueRefused` meldet sie, der Anzeigende nennt die Grenze des Schemas
(`limit_sentence`, `name_limits`) und, wo sie änderbar ist, den Weg dorthin;
der Dialog sperrt *Übernehmen* mit demselben Satz aus **einer** Quelle
(`OperationDialog._field_refusal`). Eine Nachkommastelle zu viel wird wie
überall gerundet, nicht abgelehnt; Pfeile und Rad klemmen. Das
**Merkmalfenster** nutzt denselben Validator für Zahlen, Anzahlen und Längen;
Längen behalten dabei die Umrechnung von `LengthSpin`. Die Ablehnung steht
direkt unter dem Feld, und der gemeinsame Knopf ist gesperrt, solange die
scharfgestellte Handlung eine sichtbare abgelehnte Zahl enthält. Maßgruppen im
Bild zeigen denselben Hinweis, bevor `read_fields` sie übernehmen kann; die
Sperre ist eigen (`QuietHost.refuse_fields`), kein Vorschauauftrag hebt sie. **Eine
gespeicherte Zahl jenseits der Grenze wird nicht geklemmt:** Die Leiste weitet
das Qt-Feld bis zu ihr (`ParameterPanel._set_limits`), nennt die wirksame
Grenze darunter und nimmt jede Korrektur an — sonst zeigt sie die Grenze, und
die Korrektur auf genau diese Zahl ist keine Änderung.
Felder und Fokus bleiben nur im selben Dokument (`show_document`); ein
anderes Projekt erbt keine abgelehnte Zahl.

**Auch die Druckeinstellungen lehnen ab statt zu kürzen.** Ihre Zahlenfelder
verwenden `BoundedSpin`, der Düsendurchmesser `BoundedLengthSpin`. Der Hinweis
steht am Feld. Solange ein wirksames Feld eine Zahl ablehnt, sind *Slicen* und
*Im Slicer öffnen* gesperrt und nennen dieselbe Grenze; ein ausgeblendetes Feld
einer ausgeschalteten Gruppe hält die Übergabe nicht an. Der Dialog zum
Überschreiben von Spulenwerten sperrt *Übernehmen* nur für eingeschaltete
Gruppen.

## Gestufte Tiefe

Jeder Dialog hat eine kurze Vorderseite und dahinter „Weitere Einstellungen“
(§2.4): vorn die zwei, drei Werte, die man ändert, hinten Toleranzen,
Auflösungen, Rückfallverhalten; die Vorgaben kommen aus Drucker- und
Materialprofil. **Eine gute Vorgabe ist mehr wert als eine gute
Einstellmöglichkeit.**

**Was gerade nichts tut, steht nicht da — ein Feld ohne Wirkung steht nicht
da** (Entscheidung Robert): Es verschwindet samt Beschriftung, solange seine
Bedingung nicht gilt, und kommt mit ihr wieder — im Operationsdialog, im
Merkmalfenster und überall, wo Felder einer Wahl folgen. Was vorn steht und wie
`depends_on` deklariert, gezeigt und geprüft wird: `vorderseite.md`.

Ein abgelehnter fx-Ausdruck in einem verborgenen bedingten Feld hält den
Operationsdialog an, weil `values()` ihn weiterhin an den Kern reicht. Eine
verborgene abgelehnte Zahl hält ihn nicht an: `ValueField.value()` liefert
weiter den letzten gültigen Wert. Der Hinweis führt über verborgene Steuerfelder
bis zur sichtbaren Wahl, ohne diese selbst zu ändern, und wird nach jeder
Änderung der Abhängigkeiten neu berechnet.

## Was eine Vorschau nicht zeigen kann, sagt sie

Ein leeres Bild ohne Satz sieht aus wie „nichts ändert sich“ — die eine
Rückmeldung, die nie stimmt. Das Vorschauband trägt den Grund aus dem Kern
(`Session.preview_async(explained=…)`), sagt bei leerer Differenz „am Volumen
ändert sich nichts“ und nach 0,2 s ohne Ergebnis „wird gerechnet …“ (§2.8).
Was nie etwas tun kann, sagt es schon am Menüeintrag (`grenzen.md`, „Der Satz
kommt vor den Dialog“).

**Das Band nennt, was sich ändert** (RM-516, Vertrag RM-090): unter dem Titel
eine Zeile aus `print_contract.explain_difference` — Ziel, Körper und von
Außenmaß, Körperzahl und Material nur, was nicht bleibt, Längen über
`labels.length` —, dahinter der Stand der Druckprüfung. Neue und behobene
Befunde stehen in höchstens drei Zeilen darunter (`review_difference`).

**Eine Absage steht auch bei den Eingaben** (`OperationDialog.show_refusal`),
selbst wenn der Dialog keinen zusätzlichen Handlungsknopf ausführen kann.
Die nächste Vorschau räumt den alten Satz ab; das Vorschauband bleibt die
Rückmeldung im Bild.

Eine fehlgeschlagene oder unvollständige Rechnung sperrt auch ohne Bildpflicht
das Übernehmen und verwirft einen bereits wartenden Klick. Neue Werte brauchen
eine neue Freigabe. Nur eine ausdrücklich gemeldete Rückfrage darf ohne Ergebnis
zum Übernehmen weitergehen; eine erfolgreiche Rechnung mit ausgelassenem Bild
liefert eine leere `SceneDifference`, kein `None`.

## Ein Feld ohne Namen ist für einen Bildschirmleser ein leeres Kästchen

**Wo Felder stehen, tragen sie ihren Namen — und „wo“ heißt jede Stelle**, nicht
die zwei, die man gerade im Kopf hat. Ein `QFormLayout` verbindet Beschriftung
und Feld nicht: `label.setBuddy(editor)` **und** ein Name am Feld selbst
(`setBuddy` allein hängt nur das Tastenkürzel an).

- **Der Name trägt die Handlung mit** („Durchmesser“ allein sagt nicht,
  welcher), wiederholte Zeilen nennen, wozu sie gehören („· {Parameter}“);
  `tests/test_feature_panel.py`: kein leerer Name, keine zwei gleichen.
- **`setAccessibleName` überschreibt den sichtbaren Text** — der Name bleibt
  der sichtbare Text, der erklärende Satz geht in `setAccessibleDescription`.
- **Ein Zeichen als zweite Kodierung braucht ein Wort als Namen:** „+“, „-“,
  „?“ heißen „Vorhanden“, „Fehlt“, „Wird gesucht …“.

## Ein Haken in einer Formularzeile antwortet auf der ganzen Zeile

Ein `QCheckBox` ohne Text nimmt nur Klicks auf sein Kästchen an. In einer
Formularzeile ist ein Haken ein `labels.RowCheckBox`, die Beschriftung bekommt
`labels.caption_toggles` (der Haken selbst ist ihr Ereignisfilter; wer mit
gehaltener Taste hinausfährt, schaltet nichts), und die Zeile ist so hoch wie
ihre Nachbarn (`RowCheckBox.sizeHint` über `labels.input_field_height`, an
einem Drehfeld gemessen).
`tests/test_operation_ui.py` prüft Klickfläche und Bauart über alle
`bool`-Parameter; die Höhe zeigt nur die echte Plattform (Sonde mit
`WA_DontShowOnScreen` — offscreen fehlen Stylesheet und Schrift).

## PySide legt seine Qt-Typen an, bevor das erste Fenster entsteht

`PYSIDE6_OPTION_LAZY=0` muss stehen, bevor `PySide6` zum ersten Mal lädt —
sonst hängt die Entstehung der Typen an der Importreihenfolge, und darin lag
ein Riss beim Abbau (`0xc0000374` im `gc.collect`). `app/ui/__init__.py` setzt
sie, `app.py` lädt das Paket als **ersten** Import, `tests/conftest.py` vor
jeder Testdatei; `test_the_interface_loads_qt_types_before_the_first_window`
hält alle drei. **Bei einem Riss dieser Gestalt zuerst die Importe
verdächtigen, dann den Code** — die Reichweite ist der Prozess.

## Die Tabulatortaste geht denselben Weg wie das Auge

Die Fokuskette folgt der Reihenfolge, in der Widgets **entstanden** sind, nicht
dem Layout. Wer ein Element später umhängt, zieht sie mit
`QWidget.setTabOrder` von hinten nach (`FeaturePanel._settle_tab_order`;
unsichtbare und gesperrte übergeht Qt). Geprüft wird gegen das Layout, nicht
gegen Bildpunkte (`test_the_tab_key_goes_down_the_panel_like_the_eye`).

## Ein Rad über einem Feld ohne Fokus rollt die Seite

Jedes Dreh- und Auswahlfeld in einem Rollbereich ruft `labels.wheel_needs_focus`
(Entscheidung Robert: erst hineinklicken) — `StrongFocus`, und eine Raste ohne
Fokus geht an den Rollbereich.

## Eine Adresse im Browser öffnet `dialogs.open_link`

`QDesktopServices.openUrl` meldet `False`, wenn kein Programm die Adresse
nimmt; `open_link(address, parent)` legt sie dann in die Zwischenablage und
nennt sie (Regel 17). Wer `openUrl` direkt ruft, liest den Rückgabewert und
hat einen eigenen Rückweg. Eine Funktion direkt an `clicked` bekommt keinen
Parameter mit Vorgabe — PySide reicht `checked` hinein.

## Ein Zustand darf die Farbe wechseln, nicht die Rahmenbreite

Ruhe- und Fokusrahmen jedes Eingabefelds sind gleich breit (zwei Punkte); der
Fokus wechselt auf `accent_line` und wird gestrichelt (`style.py`), denn Regel
18 verlangt die zweite Kodierung. Grund: Qt rechnet die Höhe des
Aufklappmenüs aus dem Innenrechteck der Combobox, ein breiterer Fokusrahmen
schneidet einen halben Eintrag ab. `:on`, `outline` und ein Rahmen in den
`margin` sind gemessen untauglich. `tests/test_style.py`:
`test_an_open_combo_box_shows_every_entry_it_has` (am Fenster, mit Fokus, samt
Gegenprobe) und `test_the_focus_ring_never_changes_the_size_of_a_field`.

**Der Ruherahmen behält die volle Linienfarbe** — er ist die einzige Kante des
Feldes, gedämpft fiel er unter WCAG 1.4.11.
`test_a_field_keeps_the_edge_that_is_its_only_one` prüft gegen die Linienfarbe
des Themas; was die leistet, ist eine Frage an das Thema.

## Eine Auswahl fällt nie still auf etwas Größeres

Trägt der neue Stand ein gewähltes Merkmal nicht mehr, hebt
`ObjectTree.show_scene` die Wahl auf und meldet `featuresLost`; das Fenster
sagt es als Quittung (RM-537). Still auf den Körper zu fallen hieß, dass Entf
danach den ganzen Körper entfernte.

## Barrierefreiheit

- **Keine Bedeutung allein über Farbe** (Regel 18): immer eine zweite
  Kodierung — Muster, Schraffur, Symbol, Beschriftung.
- **Keine Bedeutung ohne Farbe, wo Farbe die Sache ist:** Ein Materialslot
  ohne eigene Farbe zeigt in der Ansicht eine Ersatzfarbe aus
  `theme.slot_colour` (Slot 0, das unbemalte Teil: `None`), nicht die
  Körperfarbe — im Dokument steht sie nicht. Die Ersatzpalette ist eine
  **Grauleiter**, von der Auswahlfarbe sicher zu unterscheiden
  (`test_no_fallback_colour_can_be_mistaken_for_the_selection`); echte Farben
  kommen vom Kunden (Farbwähler, Filamentkatalog). Die Pinselleiste zeigt
  Farbfeld **und** Name, „neu“ für einen fehlenden Slot.
- **Ein Hauptknopf entsteht über `style.make_primary()`** (Akzentfarbe **und**
  halbfett), nie über `setDefault(True)`; ein verwerfender über
  `style.make_danger()`, ein Fenster ohne Handlung nimmt `style.no_primary()`,
  und ein Stylesheet geht an einen `objectName`, nie typlos (`fenster.md`, „Der
  Hauptknopf“).
- Differenzansicht Blau/Orange, nicht Rot/Grün; Analysekarten mit
  wahrnehmungsgleicher Palette (Viridis-Art), kein Regenbogen — der erzeugt
  Kanten, wo keine sind.
- Alles über die Befehlspalette erreichbar, Kürzel daneben; Undo und Redo
  überall, auch im Chat. HiDPI, skalierbare Schrift, Kontrast in hellem und
  dunklem Thema, Anzeigeeinheit Millimeter oder Zoll.

### Die Anzeigeeinheit ist ein Zustand, wie die Sprache einer ist

`labels.set_display_unit`, `display_unit()` (gehalten in `app.i18n`, auch für
den Kern) — nicht durch Konstruktoren gereicht, denn `labels.length` rufen
auch Funktionen ohne Widget; ein übergebenes Argument hat Vorrang.

- **Was in ein Eingabefeld geschrieben wird, bleibt in Millimetern**
  (`measured_expression`; umgerechnet wäre es ein Datenfehler), auch beim
  Umschalten in den Ausdrucksmodus (`_number()` ist die eine Quelle für Feld
  und Hinweis). Eingabefelder umzustellen heißt Wert **und** Grenzen in beide
  Richtungen umzurechnen, ohne einen Parameterausdruck anzufassen — ein eigener
  Schritt; nur das Suffix zu tauschen ist falsch.
- **`valueChanged` überspringt die Umrechnung** — `valueChangedMm` ist
  dieselbe Nachricht in Millimetern; `valueChanged` nur, wo man den Wert fallen
  lässt und `value_mm()` liest.
- **Ein Einheitenwechsel meldet nichts:** `refresh_unit` tauscht unter
  `blockSignals`.
- **Ein Satz trägt keine Einheit im Katalogtext:** Die Zahl kommt mit ihrer
  Einheit (`labels.length`, im Kern `format_length(…, display_unit())`) —
  sonst liest sich „misst {measure} mm“ in Zoll als „0.2047 mm“ (RM-516).
- **Gelesen wird über die Leiste, nicht an ihr vorbei** (`SculptBar.values()`,
  typisiert als `StrokeValues`, damit mypy das Auspacken prüft).
- **Geprüft wird an einer Handlung, nicht nur an Anzeigen:**
  `tests/test_sculpt_session.py` fährt einen Pinselzug in Zoll bis in den
  `Stroke`; `tests/conftest.py` setzt die Einheit nach jedem Test zurück.

## Tests

Oberflächentests laufen offscreen (`tests/conftest.py`); eine neue Ansicht ohne
Test in `tests/test_ui.py` oder einer spezielleren Datei ist unfertig. Ein
Widget im Test braucht `qt_app` (`tests.md`) — ohne endet der Lauf je nach
Reihenfolge mit 0xC0000409 ohne ein Wort.

**Ein modaler Dialog auf einem Startweg hält die ganze Suite an** —
`QDialog.exec()` wartet offscreen auf einen Klick, den es nie gibt, und die
Suite wird nicht rot, sie steht (`py-spy dump --native` nennt die Stelle). Wer
einen Dialog auf einen Weg setzt, den ein Test geht, fragt vorher
`QT_QPA_PLATFORM != "offscreen"` (wie `motion.animations_enabled`) und setzt den
Merker eines solchen Hinweises dann **nicht** — sonst sähe der Kunde ihn nie.
Auch der Absturzbericht: `_on_ask` macht aus jeder Ausnahme eines Fragedialogs
einen `InternalError`, und `report_error` schreibt offscreen ins Protokoll
(`_log.error`).
