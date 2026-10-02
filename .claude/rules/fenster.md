---
description: "Fenster, Dialoge und Karten — Zonen, Quittung und Einladungen, Rückfragen vor Export und Übergabe, Verlauf umbauen, Kettenhalt, Prüfbericht, Merkmalfenster und Bausteinmerkmale, Hauptknopf, setParent(None), Sicherung, Kartenhöhen, Rückmeldung"
paths:
  - "app/ui/main_window.py"
  - "app/ui/app.py"
  - "app/ui/dialogs.py"
  - "app/ui/*dialog*.py"
  - "app/ui/style.py"
  - "app/ui/filament_picker.py"
  - "app/ui/start_screen.py"
  - "app/ui/first_run.py"
  - "app/ui/manual_window.py"
  - "app/ui/overlay.py"
  - "app/ui/panels.py"
---

# Regeln für Fenster und Dialoge

`oberflaeche.md` gilt und lädt zusätzlich; was wo im Menü und in der Karte der
Handlungen steht, sagt `grenzen.md`. Warum:
`konzepte/begruendungen/regel-fenster.md`.

## Fenster

**Höchstens drei sichtbare Zonen:** links Objektbaum, Parameter und Verlauf als
einklappbare Abschnitte, Mitte der Viewport, rechts **entweder** Chat **oder**
Prüfbericht, umschaltbar und ganz ausblendbar; eine neue Warnung schaltet zum
Bericht. Keine Betriebsarten (`AGENTS.md`) — es gibt einen Zustand, die Szene.

**Die Handlungen an der Auswahl stehen in einer zweiten Karte darunter**
(Entscheidung Robert): eigener Rand, derselbe Stil, `MARGIN` dazwischen, und
durch die Lücke ist das Modell zu sehen (die Maske von `overlay.CardColumn`
nimmt sie aus). Für F9, Warnungszähler und Höhenverteilung bleibt es **eine**
Zone; die zweite Karte folgt ihrem Inhalt.

**Eine Handlungsquittung steht zusätzlich dort, wo gehandelt wurde:**
`MainWindow.announce` behält die Statuszeile und zeigt eine passive Quittung im
vorhandenen Overlay — kein Fokus, keine Mausklicks, kein RichText, mindestens
acht Sekunden, längere Texte länger. Eine neue ersetzt die alte, Fortschritt
überschreibt sie nicht, Kontextwechsel und Fensterabbau beenden sie samt
Zeitgeber; keine neue Zone, kein zweites Live-Ereignis für Bildschirmleser.

**Eine Einladung steht über der Ansicht, nie unter einer Karte** (Entscheidung
Robert). `SurveyNotice` (nach 15 aktiven Minuten) und `SupportNotice` (nach dem
dritten erfolgreichen Export oder Slicer-Start einer Version) sind
`survey.ViewNotice`: nicht modal, ohne Fokus beim Erscheinen, weg erst auf
Klick.

- **Der Platz wird gesucht:** `spot` nimmt die oberste freie Stelle zwischen
  allem, was über `keep_clear_of` gemeldet ist (Zonen, Ansichtsleiste,
  Vorschauband, Ziehwert-Leiste) — zuerst oben zwischen den Karten, sonst unter
  der kürzeren. **Wer etwas Neues über die Ansicht legt, meldet es dort an.**
- **Ausgewichen wird in einer Richtung** — die Unterstützung weicht der
  Rückfrage; gegenseitiges Ausweichen schiebt im Kreis.
- **Angeboten wird nur, wo sie jemand sieht:** nicht hinter einem modalen
  Dialog (beim Druckdialog nach `exec`), nicht über dem Startbildschirm, sonst
  beim nächsten Ergebnis; „gesehen“ setzt erst das Zeigen.
- **Gezählt wird das Ergebnis, nicht der Versuch:** `_announce_written` und
  `PrintSettingsDialog.handedOver` kommen nur nach geschriebener Datei bzw.
  gelungenem Slicen oder Öffnen an — Abbruch, Fehler und die Rückfrage vor
  Fehlern nie.

**Wer auf dem Startbildschirm zu arbeiten beginnt, beginnt das leere Projekt:**
Kürzel und Befehlspalette sind dort erreichbar, und `run_operation` und
`start_sketch` gehen über `_begin_from_the_start_screen` — wie Einfügen und
Download ersetzt der Anfang das offene Projekt (mit der Frage aus
`_may_discard`, wenn etwas verloren ginge) und wechselt in den Arbeitsbereich,
damit die Vorschau nicht hinter dem Startbildschirm liegt; `start_empty` sagt,
ob es dazu kam.

**Ein Klick baut das Fenster einmal, auch wenn er mehrere Signale sendet:** Der
Objektbaum geht über `_on_tree_selection`, das die Menüeinträge dem
Merkmalsignal überlässt, und `_fields_this_round` merkt sich das Merkmal, das
`featureSelected` in derselben Runde gebaut hat (samt `FeaturePanel.serial`).
Wer ein weiteres Signal an dieselbe Geste hängt, zählt, wie oft der teure Teil
läuft.

**Die Tour ist ein Angebot, keine Sperre:** Solange ein Beispielprojekt offen
ist, trägt die rechte Spalte einen dritten Reiter (`app/ui/tour.py`, Schritte in
`app/core/tour.py`); er erkennt getane Schritte über `projectChanged`, „Weiter“
schaltet auch ohne Erkennung. Der Warnungssprung lässt der aktiven Tour den
Reiter, ein anderes Projekt räumt ihn weg. Die Erkennungswerte passen zu
`tools/make_examples.py` (`tests/test_tour.py`).

## Rückfragen

Die gewollten Ausnahmen von Regel 19, und was sie davon abhält, zur Blockade zu
werden:

- **Löschen im Verlauf:** Die Nachfrage nennt mitbetroffene Schritte beim
  Namen, mit Nummer und Titel wie im Verlauf (`history.named_steps`: bis vier
  alle, sonst drei und „und N weitere“), und den Rückweg über Strg+Z.
- **Die lange Merkmalserkennung wird angeboten** (§21.1): Oberhalb der
  automatischen Grenze nennt die Frage Dauer und Speicherbedarf; die
  Alternative — auch das Schließen — lädt mit begrenzter Erkennung. Das ist
  kein abgebrochener Import und keine Sackgasse: Der Befund `perceive.too_large`
  trägt *Alle Merkmale erkennen*, auch an jedem Folgeschritt des Körpers (die
  Wahl gehört dem Körper), aber nur, wo am Ladeschritt eine Wahl steht (`panels._recognition_reopenable` über
  `history.recognition_reopenable`; Kommandozeile: `recognize`). An einer
  Sammelzeile gilt er allen ihren Körpern, und die Frage kommt mit derselben
  Schätzung wieder; am Speicherfehler steht er zuletzt und nicht hervorgehoben —
  vorn steht, was der Satz nennt.
- **Export** (§29): Eine geschriebene Datei holt kein Undo zurück. Der Export
  prüft, zeigt die Befunde im Prüfbericht und fragt dann
  (`dialogs.confirm_export`) — nur ab `warning` (der Lizenzhinweis §16.3 ist
  `info`), Weitergehen ist die Vorgabe, und der Bericht steht daneben, nicht im
  Dialog: Der Prüfbericht bekommt die Befunde und rückt nach vorn, der Dialog
  zeigt die ersten Sätze und verweist dorthin.
- **Slicer-Übergabe:** `confirm_handover` fragt vor *Slicen* und *Im Slicer
  öffnen* nur bei **Fehlern** der gewählten Platten, nicht bei Warnungen — die
  Übergabe ist oft der Blick ins gewohnte Programm; Weitergehen ist die Vorgabe.
- **Danach weiß der Kunde, wo die Datei liegt:** *Ordner zeigen* steht neben der
  Ankündigung, solange sie steht (`announce` nimmt ihn mit der nächsten mit),
  und öffnet über `QDesktopServices` (Qt kennt die Plattform und im Flatpak das
  Portal).
- **Wer nur hinsieht, wird nicht gefragt:** Beim Schließen fragt das Fenster nur,
  wenn etwas verloren ginge, das nicht in den Dateien des Kunden steht
  (`ingest.plan.is_only_imported` über `Session.only_imported`).
  `Session.modified` bleibt, was es war — die Sicherung hängt daran —; nur das
  bewusste Schließen fragt nicht und räumt die Sicherung selbst weg. Ein
  eingelesenes Modell steht in „Zuletzt geöffnet“.

## Der Verlauf lässt sich umbauen — und sagt, was er nicht kann

Einfügen, Verschieben, Aus- und Einschalten fragen nicht (Regel 19); gefragt
wird nur, wenn Zurückgenommenes verworfen würde (§15.4,
`MainWindow._history_change_allowed`, `confirm_discard`).

- **Die Vorschau ist die Rechnung:** Die Sitzung rechnet den Vorschlag im
  Arbeiter (`_RevisionWorker`, `wartezeit.md`) und übernimmt nur ein gültiges
  Ergebnis, als eine Transaktion mit Satz und Strg+Z. Ein ungültiger Vorschlag
  ändert nichts und bringt seine Handlungen (*Schritt einschalten*, *Diesen
  Schritt mit ausschalten*, *Einfügen beenden*, *Abbrechen*; Regel 17).
- **Eine unmögliche Stelle sagt ihren Grund, bevor gerechnet wird**
  (`Session.move_targets`): kein Einfügestrich und ein Satz beim Ziehen, ein
  grauer Eintrag mit Kurzhilfe im Kontextmenü.
- **Der Zustand steht als Wort an der Zeile** („(aus)“, „(ruht)“), kursiv
  und gedämpft nur zusätzlich (Regel 18); die Kurzhilfe nennt, was ein Schritt braucht und
  wer ihn braucht.
- **Die Tastatur kann alles, was die Maus kann:** Einfg, Alt+Pfeil, Leertaste,
  Esc — am Verlauf und nur dort, wie Entf.
- **Mit Einfügemarke zeigt die ganze Oberfläche den Stand davor**
  (`Session.displayed_document`), und jede Operation über `Session.apply` landet
  dort. Abläufe mit eigener Buchführung (Teilen mit Stiften, Deckel, Gegenstück,
  Auto Split, Erzeugen, Agentenvorschlag) sagen ab, mit *Einfügen beenden* als
  Weg; Export und Druckeinstellungen beenden das Einfügen zuerst — hinaus geht
  das fertige Teil, nicht der Zwischenstand. Erzeugen fragt vor dem Start
  (`_generation_refusal`); sagt *Übernehmen* ab, bleibt der Dialog mit seinen
  Versuchen offen (`GenerateDialog.take`).

## Hinter einen Halt kommt kein Schritt

Hält die Kette an (§15.3), zeigt das Bild den letzten vollständig gerechneten
Stand, und dahinter wird nichts gerechnet. Zwei Stellen halten das, beide sind
nötig:

- **Die Sitzung nimmt keinen Schritt an** (`Session.halt_in_the_way` in `apply`
  mit Entwürfen, `split_async`, `auto_split`, `split_along`, `create_lid`,
  `add_generated`, `accept_proposal`). Die Absage trägt die Handlungen des Halts
  mit Schrittkennung, Werten und Körper, damit `error_handlers` sie ausführen
  kann. Weiter gehen Änderungen ohne Schritt (Parameter, Passung, Drucker — sie
  können den Halt lösen), Rückgängig, *Schritt löschen* und die Wege des
  Verlaufs (`change_params`, `repair_and_retry`, `split_and_retry`,
  `recount_and_retry`, `decimate_and_retry`, `remesh_and_retry`).
- **Die Oberfläche sagt es vorher** (`_halt_reason`, die erste Frage in
  `_reason_locked`): Aktion, Palette und Karte tragen den Grund mit
  Schrittnummer und Titel, ebenso Automatisch teilen, Einfügen, Erzeugen,
  Zeichnen, Formen, Skelett und der Filamentwähler — dieselbe Bauart wie Lizenz-
  und Gestensperre. Die Werkzeugzeile bleibt frei — Messen, Analyse, Schichten
  lesen nur. Das Merkmalfenster gehört dazu
  (`FeaturePanel.set_locked`): graue Knöpfe **und** der Grund als sichtbare
  Zeile, dazu in Kurzhilfe, Statuszeile und zugänglicher Beschreibung; die
  Sperre überlebt den Neuaufbau der Zeilen und fällt nach einem Undo
  (`test_a_halted_chain_takes_no_new_step_and_names_the_way_on`).

## Der Prüfbericht

- **Dasselbe Problem bietet dieselben Handlungen**, gleich wer es meldet:
  `FINDING_ACTIONS` (`panels.py`) hält die Zuordnung,
  `tests/test_value_labels.py` die **Familie** — Befunde mit demselben Namen
  hinter dem Punkt tragen alle eine Handlung, wenn einer sie trägt.
- **Die Kennung trifft den Fall:** „passt nicht“ und „liegt woanders“
  trennt, ob der Körper überhaupt hineinpasst (`prepare._fits_at_all`); einer
  3MF mit Bettkoordinaten (Bambu Studio, Orca, Elegoo) hilft *Auf dem Bett
  anordnen*, nicht *Modell teilen*.
- **Gleiche Meldungen sind eine Zeile, die Zahl davor in Klammern**
  (Entscheidung Robert): gebündelt ab zwei nach Satz, Kennung, Schwere, Schritt
  und Handlungen. Die Sammelzeile trägt alle Körper und wählt beim Klick alle,
  ihre Handlung fragt, für welche sie gilt, Ort und Merkmale trägt sie nur, wenn
  alle Mitglieder dieselben haben.
- **Die Handlungen stehen sichtbar da, nicht im Rechtsklick:** eine Knopfzeile
  unter der Liste über `actions_for(finding)`, dieselbe Quelle wie das
  Kontextmenü (§2.7).
- **Wer einen Befund baut, gibt ihm einen Weg** (`suggestions=`;
  `test_finding_ways.py`, sonst ein Grund in `OHNE_KNOPF`); was ohne Schritt
  oder Körper nichts täte, blendet der Bericht aus
  (`panels.actions_for_document`, `tests/test_finding_actions.py`).
- **Ein Fehler aus einer Operation ist ein Befund, kein Dialog**
  (`op.<operation>.<Ausnahme>`, die Kette hält an). Seine Handlung ist
  *Eingabe korrigieren*: `edit_operation(op_id, field)` öffnet den Schritt mit
  dem Cursor im genannten Feld und ersetzt ihn beim Übernehmen (§15.4). Was die
  Schrittkennung braucht, steht in `dialogs.NEEDS_OP`, was den lebenden Körper
  braucht, in `panels.NEEDS_LIVE_BODY`; wer einen Handler baut, der
  `_object_of`, `_entry_of` oder `error.object_id` liest, trägt ihn dort ein
  (`test_finding_actions`). Nur eine nackte Bindung (`=@breite`,
  `expressions.bound_name`) führt in die Parameterleiste.
- **Eine Befundzeile aus einer Operation steht nie ohne Knopf da:** Bleibt nach
  dem Abgleich mit `error_handlers` nichts, bietet `panels.handled_actions`
  *Eingabe korrigieren* an, mit dem Rat in dessen Kurzhilfe (der Fehlerdialog
  zeigt Räte als Sätze, `dialogs.unhandled_advice`). Knopfzeile, Kontextmenü
  und Vorwahl fragen dieselbe Funktion.
- **Lokale Formenerkennung aus einem Befund behält dessen Ziel:** Die nächste
  Oberflächenwahl bleibt an seine Körper gebunden, erst der Treffer bestimmt
  einen; die Baumauswahl ersetzt das Ziel nie, Maus und Tastatur führen über
  denselben Originaltreffer.
- **Ein Klick auf einen Befund bleibt nie folgenlos** (§2.7), gestuft: **Ort**
  → die Kamera fliegt hin, eine vergängliche Marke steht dort (`mark_finding`:
  Ring in der Befundfarbe `FINDING_COLOUR` vor dem Material, nie in der
  Auswahlfarbe, Radius aus dem Abstand, Titel auf eigenem Grund in
  Oben-Richtung der Kamera, bei `Finding.outline` dazu der Rand der Fläche —
  `ansicht.md`, „Was gefärbt wird“); **Körper** → er wird ausgewählt; **`op_id`** → der
  Verlauf zeigt den Schritt (`HistoryPanel.point_at`), auch ohne Körper.
  Fallen: Der Ort kommt aus der Szene und wird für die Ansicht verschoben
  (`view_point_of`); der Ort eines Kartenbefunds wird in `_map_ready`
  nachgeholt; eine Transaktion aus mehreren Schritten trägt nur `OPS_ROLE` am
  Gruppenknoten. Die Marke wird nicht nach vorn gezogen, die Beschriftung trägt
  `always_visible`.

## Das Merkmalfenster

- **Ohne jede Auswahl schweigt es** (`FeaturePanel.say_nothing_is_chosen`) —
  dann nennt die Karte den Weg zu den Bausteinen; mit gewähltem Körper kommt der
  Satz zurück.
- **Für alle heißt dasselbe Maß, nicht dieselbe Stelle:** „Auf alle N
  gleichartigen anwenden“ gibt jedem Mitglied seine eigene gemessene Mitte
  (`relations.params_for_members`); eine Verschiebung am gewählten Merkmal geht
  als **Versatz** mit, eine dort ungenannte Achse bleibt bei allen ungenannt.
  Das Fenster baut die Entwürfe (`MainWindow._apply_to_each_feature`), das Panel
  nennt nur Werte und Ziele.
- **Ein Nachweis gehört der Gruppe, nicht jeder Handlung:**
  `FeaturePanel._said_notes` merkt, welcher Absatz schon steht (geleert in
  `clear()`, mit dem `show_feature` beginnt). Weggelassen wird die Wiederholung,
  nicht die Auskunft — ab der zweiten Handlung trägt der Haken sie in Tooltip,
  Statuszeile und zugänglicher Beschreibung.
- **Ein zusammengelegter Grund spricht für alle, unter denen er steht:**
  `_folded` macht aus gleich begründeten Absagen eine Zeile („Verschieben,
  Ändern, Drehen, Verdoppeln und Entfernen — <Satz>“); der Satz verneint die
  **Voraussetzung**, nicht eine Handlung („trägt kein Maß, an dem sich Lage
  oder Größe ändern ließen“), und nennt den Weg, der bleibt. Maschinell
  prüfbar ist das nicht („ändern“ ist beides) —
  `test_no_feature_kind_falls_back_to_the_sentence_that_says_nothing` hält nur,
  dass keine Art auf `_UNKNOWN_KIND` zurückfällt.
- **Eine Anzahl ist keine Länge** (`count`, `steps`, `holes`):
  `perceive.actions._kind_of` nennt `int` `count`, das Fenster baut ein
  Ganzzahlfeld und gibt `int` zurück; eine neue Feldart in `ActionField.kind`
  wird an beiden Enden gebaut.

## Ein Merkmal aus einem Baustein meint den Baustein

Gefragt wird über `Feature.created_by` und die Kategorie `parts`, nicht über
den Operationsnamen (`drill_hole` erzeugt auch eine Bohrung mit Provenienz). Die
Ansichtsseite steht in `griffe.md`.

- **Drei Handlungen gelten dem Schritt** — Maße ändern, verschieben, entfernen;
  die Werte kommen aus dem Schritt, nicht aus der Messung, und jede Handlung
  schickt nur ihren Ausschnitt, gelegt über die Werte im Schritt
  (`_change_part_step`).
- **Der Organizer gehört dazu**, obwohl er unter `primitive` steht:
  `panels.SPEAKS_FOR_ITS_FEATURES` nennt ihn mit den Rollen, für die sein
  Schritt spricht (`divider`, gefragt über `part_step_of` und `organizer_role`);
  Fachböden und Innenboden behalten ihre Flächenhandlungen.
- **Jeder Zug an einem Bausteinmerkmal geht in den Schritt des Bausteins** —
  Griff, Körpergriff, Bewegen-Leiste (`MainWindow._move_the_part`), an **jedem**
  seiner Merkmale (`Viewport.moves_as_a_part`), auch an seinen Flächen (kein
  Press/Pull, die Statuszeile nennt den Baustein). Nur wenn der Schritt eine
  Lage kennt: `MainWindow._asks_for_the_part` verlangt `x/y/z` (Organizer,
  Deckel, Profil-Einlagen haben keine). Wer eine neue Geste an einem Merkmal
  baut, fragt zuerst, ob es aus einem Baustein kam.
- **Die Drehachse ist die des Bausteins:** am benannten Sitz (`at_feature`) aus
  dem Sitzmerkmal (`direction_of`), mit freier Richtung über
  `placement_transform` → `placement_values_of`, sonst nur um sein Feld
  *Achse* — jede andere Achse bekommt einen Satz mit dem Weg.
- **Eine gebundene Lage folgt dem Griff:** Der Zug wandert als Versatz in den
  Ausdruck (`expressions.shifted`: `=@staerke + 5`), eine Achse ohne Zug bleibt
  unangetastet; abgelehnt wird nur eine Drehung an einem gebundenen Wert. Eine
  Achse mit Ausdruck bekommt im Merkmalfenster das `ValueField` des
  Operationsdialogs (`FeaturePanel._part_fields`, §13).
- **Entf** nimmt an Dach oder Einzelmerkmal den Schritt des Bausteins
  (`MainWindow._delete_the_chosen_feature`), nie den Körper; ohne Baustein gilt
  `remove_feature`; greift auch das nicht (Fläche, Gewinde, Verrundung), fällt
  der Körper — mit Ansage und Strg+Z: Eine Fläche ist kein Ding, das man
  löscht, der Körper ist gemeint, und ein Teil, das Entf nicht löscht, ist eine
  Sackgasse (Regel 19). *Ausblenden* heißt am Merkmal *Körper ausblenden*.
- **Bei gewähltem Dach** fragt `_move_the_part` `_common_part_step`, und das
  Dach bekommt einen eigenen Griff (`_part_grip_anchor` →
  `Viewport.set_part_grip`; welches Merkmal ihn trägt, sagt das Fenster) statt
  des Körpergriffs mit Skalierwürfel. Die Bohrung eines Bausteins bekommt ihren
  Griff ohne *Im Bild einstellen*, aber ohne Langlochknöpfe.
- **Filament:** An einer Bausteinfläche färbt der Schnellwähler **alle** Flächen
  des Bausteins; Wähler, Zuweisen und Entfernen lesen dieselbe Menge
  (`_part_faces_of_selection`, `_filament_targets`), die Chips im Baum bleiben
  je Fläche.
- **Was kein Zahlenfeld werden kann, bekommt seinen Weg:** Ein Sammelparameter
  mit eigenem Editor (`perceive.actions.COLLECTED_KINDS`, dieselben Arten wie
  in `operationen.md` unter „Sammelparameter“) steht in
  `FeatureAction.elsewhere`, und ein Knopf öffnet den Dialog des Schritts. Ein
  neuer Sammelparameter trägt seine Art dort ein.
- **Ein Langloch aus einem Schritt gehört dazu:** Hat `slot_hole` es gezogen,
  ändert *Übernehmen* diesen Schritt (`_prepare_slot_change`,
  `_commit_slot_change`) und legt keinen zweiten obenauf. Wer eine Operation
  baut, die ein Merkmal aus ihrem früheren Schritt noch einmal anfasst, fragt
  zuerst `created_by`.

## Der Hauptknopf

**Ein Hauptknopf entsteht über `style.make_primary()`, nie über
`setDefault(True)`:** Qt rechnet die Breite aus der normalen Schrift, gezeichnet
wird halbfett, und in einer engen Leiste wird die Beschriftung abgeschnitten.
`make_primary` setzt die Schrift am Widget; das Fett bleibt als zweite
Kodierung neben der Akzentfarbe (Regel 18). **Ein Knopf, der verwirft, entsteht
über `style.make_danger()`** — Fehlerrot (`ROLES["error"]`) als Fläche, Schrift
aus `readable_on`, das Wort als zweite Kodierung (*Abbrechen* unter
*Übernehmen*; Entscheidung Robert); `tests/test_style.py` misst die Fläche am
gezeichneten Knopf.

**Wo keiner gesetzt wird, setzt Qt selbst einen:** `QDialog` macht beim ersten
`show()` den ersten Knopf mit `autoDefault` zum Default — Akzentfarbe ohne
halbfette Schrift. Ein Fenster ohne Handlung nimmt `style.no_primary()`, eines
mit Handlung `make_primary`, auch wenn der Knopf gesperrt startet. Das zeigt nur
das angezeigte Fenster: `tests/test_style.py` hält beide Richtungen
(`test_every_default_button_of_the_surface_goes_through_make_primary`,
`test_no_window_wears_an_accent_it_never_asked_for`), misst gegen die
gezeichnete Schrift und verbietet `setDefault(True)` außerhalb von `style.py`.

**Der Fokus macht keinen Hauptknopf, Enter gehört trotzdem dem per Tastatur
gewählten Knopf:** Ein `QPushButton` mit `autoDefault` (im `QDialog` Vorgabe)
macht sich beim Fokus zum Default. Der Zuhörer `style._FocusTakesNoAccent`
(einmal je Anwendung, über `make_primary`/`no_primary`) nimmt jedem
Nebenknopf beim Fokus `autoDefault`; ohne das gäbe der Knopf Enter an den
Default weiter. Den per Tab/Umschalt+Tab erreichten Knopf klickt der Zuhörer
bei Enter deshalb selbst (`style.enter_belongs_to_focus`), der Akzent bleibt.
Maus, Fensterwechsel, `setFocus` und vom gesperrten oder verborgenen Knopf
vertriebener Fokus (Qt meldet ihn als Tab) lassen Enter beim Hauptknopf. Kein
Dialog tut dafür etwas selbst. Wächter: `tests/test_enter_key.py` und
`test_no_button_takes_the_accent_when_it_gets_the_focus` (Fokus zugestellt —
mit `WA_DontShowOnScreen` wird kein Fenster aktiv).

**Ein typloses Stylesheet am Vorfahren nimmt dem Hauptknopf seine Farben:** Eine
Regel ohne Selektor gilt für jeden Nachkommen (auch aus dem Stylesheet der
Großeltern) und **ersetzt** dort das Anwendungs-Stylesheet — für die
Eigenschaften, die sie setzt; gefährlich ist `background` (ein typloses
`border:` wie in `_flash` nimmt nichts). Stylesheets gehen deshalb an den
`objectName`; wo eine breite Regel bleiben muss, bekommt der Hauptknopf darin
seine Farben ausdrücklich (`#surveyNotice #surveyGive` in `app/ui/survey.py`);
`make_primary` bleibt in beiden Fällen. Ein grüner Klicktest sagt nichts über
das Bild eines Knopfes.

**Der Knopf heißt nicht wie sein Werkzeug:** Der Umschalter nennt das Werkzeug,
der Knopf die Handlung („Trennen“, „Jetzt trennen“;
`tests/test_interface_limits.py`).

## Ein Dialog, der höher ist als sein Inhalt

Von Hand gezogen oder beim Öffnen an den Inhalt angepasst — überschüssiger
Raum braucht **eine** Stelle, sonst verteilt Qt ihn als Lücken zwischen
Widgets fester Höhe (im KI-Hinweis stand die Überschrift allein über einer
leeren Fläche). Die Stelle ist ein `addStretch` dort, wo Leere nicht stört,
oder ein Widget, das den Platz nutzt (die Versuchsliste des Erzeugen-Dialogs
nach dem Lauf). Lange Statusmeldungen bleiben im Rollbereich erreichbar und
ändern den Außenrahmen nicht; `style.WrappedNote` misst dafür ohne die
gepinnte Höhe, denn `QLabel.heightForWidth` meldet nie weniger als die
Mindesthöhe.

**Dialoggröße nach Auslöser:** `ContentHeight` misst die natürliche Geometrie
des aktuellen Inhalts einmal nach dem Anzeigen. Eine manuell gezogene Breite
oder Höhe bleibt für die Dialoglebensdauer maßgeblich; Mehrinhalt rollt im
äußeren Scrollbereich, Aktionsknöpfe bleiben außerhalb. Nur ausdrücklich
betätigtes Auf- und Zuklappen darf bei automatischer Größe die Höhe anpassen;
dabei bleibt der Fensteranker, Platz bis zum Bildschirmrand wird genutzt, der
Rest rollt. Reiter, Suche, Statusmeldungen und bedingte Zeilen lassen den
Außenrahmen stehen. `contentSizeChanged` meldet verzögerte Innenlayoutänderungen.
Beim Öffnen sowie nach Monitorwechseln, geänderter nutzbarer Fläche oder
logischer DPI stellt `DialogScrollArea` mit `fit_dialog_to_screen` die
Erreichbarkeit wieder her. `form_natural_width` berücksichtigt zugeklappte
Formularzeilen bei der einmaligen Anfangsbreite.

**Formulare: eine Zeilenform, eine Kante.** Keine Beschriftung über dem Feld
(`DontWrapRows`); das Fenster wird so breit wie seine breiteste Zeile, eine
zugeklappte Rückseite zählt mit. Eine Beschriftungsspalte je Dialog
(`panels.align_forms`, gerahmte Reiter über `apart`), gleich breite Felder
(`panels.even_fields`, `op_dialog.even_value_fields`); eine Zeile aus Feld und
Knöpfen endet mit `addStretch`. Beschriftungen ohne Doppelpunkt.

**Klappen:** überall die flache Überschrift (`panels.collapsible`,
`sectionHeading`). Werte, die sich ein- und ausschalten lassen, sind eine
Schalterzeile mit eingerückten Feldern, kein ankreuzbarer Rahmen. Bei
`ContentHeight`-Dialogen werden Anfangsgröße und ausdrücklich bedientes
Klappen getrennt gemessen; passive Änderungen bleiben im Rollbereich und
werden nicht als gezogene Nutzergröße gemerkt. Andere Dialoge behalten ihren
eigenen Größenweg. Ein Ausgang ist `RejectRole` — als `AcceptRole` macht ihn
die Knopfleiste beim Anzeigen zum Hauptknopf.

**Was eine Angabe bestimmt, steht vor ihr** (Entscheidung Robert,
29.09.2026): was eine Liste füllt, eine Vorgabe setzt oder sperrt, davor; ein
Schalter bei dem, was er schaltet; ein Zustandssatz bei seinem Gegenstand.
Druckeinstellungen: Slicer, Drucker, Düse, Platte, Filamente, Qualität,
Profile des Slicers, Grundlage, Werte; *Werte mitgeben* bei der Übergabe
(`test_the_print_dialog_asks_in_the_order_its_answers_depend_on`). Register:
`tests/test_dependency_order.py`.

**Slicer vor Drucker:** Einstellungen und Erstlauf verwenden dieselbe
asynchrone Druckererhebung; in den Einstellungen steht der Slicer unter
„Anwendung“ (er gilt jedem Projekt), direkt vor den Druckervorgaben. Beide
bieten vollständige Profile aus dem gewählten Slicer an; neue Druckerprofile bleiben bis zum Speichern im Entwurf, auch beim
Sprachwechsel. Die Einstellungen übernehmen dabei auch den Programmpfad erst
beim Speichern. Der Erstlauf bewahrt seine bisherige Sprachwechsel-Semantik:
Sprache, Slicerpfad und bereits gespeicherte Drucker gelten sofort; eine neue
Profil-ID reist getrennt im Entwurf. Verspätete Antworten einer früheren
Auswahl ändern weder den aktuellen Dialog noch gespeicherte Einstellungen.
Die Druckerliste hat eine feste Suchzeile oberhalb der Treffer. Sie filtert
live; erst eine ausdrückliche Auswahl übernimmt einen Drucker, Escape schließt
nur die Liste.

## `setParent(None)` macht ein Kind zum Fenster

Ein Widget ohne Elternteil **ist** ein Top-Level-Fenster — bis zum Löschen
steht es als eigenes Fenster auf dem Bildschirm, im selben Atemzug gelöscht
bringt es den Absturz, und Tastenkürzel lösen falsch auf. Weggeräumt wird mit
`hide()` und `deleteLater()`, nie über den Elternteil: `takeAt` nimmt es aus
dem Layout, `hide` aus dem Bild, der Elternteil trägt es bis zum Löschen.

## Die automatische Sicherung

Sie ist für den Absturz da (§38), nie dafür, eine Entscheidung zu überstimmen.

- **Verworfen heißt verworfen:** `_may_discard` räumt die Sicherung bei
  *Verwerfen*, `closeEvent` schreibt danach keine neue.
- **Abgelehnt heißt einmal gefragt:** Eine abgelehnte Sicherung wird gelöscht,
  und der Dialog sagt, was das kostet.
- **Angenommen speichert in die Datei des Nutzers:**
  `Session.recover(candidate, path)` behält den Pfad des Projekts — nie
  `open_project(candidate)`.
- **Namenlos heißt je Dokument eine Kennung, nicht je Rechner eine Datei:**
  `Session.recovery_token` aus `project.recovery_token()`, je Dokument neu
  (`_reset_for`), genommen von allen vier Sicherungsfunktionen. Beim Start wird
  die jüngste **fremde** Sicherung angeboten; abgelehnt wird genau sie geräumt
  (`discard_recovery`), angenommen wandert sie unter die eigene Kennung.

## Wie die Karten ihre Höhe teilen

`OverlayHost._share_room` verteilt die Höhe einer Zone auf ihre `RoomTaker`:

- **Gerechnet wird nie mit den Höhen, die gerade gesetzt wurden** — sonst läuft
  die Karte auf und ab; `natural_height` taugt darin nicht, `extra_height`
  rechnet strukturell (je Posten: Wunsch des Ganzen minus die Wünsche der
  Karten darin).
- **Was nicht den Karten gehört, wird abgezogen** (Abschnittsköpfe,
  Parameterleiste, Layoutabstände) — sonst schneidet das Elternwidget Zeilen
  weg, ohne dass ein Rollbalken es meldet.
- **Jede Karte nennt ihren Boden** (`RoomTaker.least_height`; aus `fit_to_rows`
  mit drei Mindestzeilen und aus dem leeren Zustand über `fit_wrapped`), nie
  höher als ihr Wunsch; verteilt wird nur, was darüber liegt.

`tests/test_overlay.py` hält alle drei („settles on one answer“, „moves a card
once“, „no card is pushed outside its section“). `fit_to_rows` rechnet mit
**einer** Zeilenhöhe — ungleiche Zeilen misst `overlay.rows_height`, und
`wanted_height` fragt dieselbe Quelle wie das Setzen. **Was unter der Liste
steht, gehört in beide Rechnungen**, sonst schiebt die Liste den einzigen Weg
der Karte hinaus.

**Gesetzt wird einmal je Ereignisdurchlauf, nicht je Ereignis:** `_place_later`
setzt über einen Nullzeitgeber — kein nachgereichtes Ereignis, denn die Listen
legen ihre Zeilen selbst über einen Nullzeitgeber, und `rows_height` misst an
`visualRect`; `resizeEvent` und `reflow` setzen sofort. Tests brauchen mehrere
Runden `processEvents` — eine Zusicherung nach einer Runde misst einen
Zwischenstand. `is_room_taker` antwortet je Widget-Typ einmal.

## Rückmeldung und Fehlerbericht

Ein Dialog für beides (`app/ui/support_dialog.py`): *Hilfe → Rückmeldung
senden* und `report_error` — dort mit `kind=crash`, eigenem Titel und „Das war
ein Programmfehler, nicht Ihre Schuld“ (§33.1).

- **Von allein geht nichts:** `support.send()` hat genau einen Aufrufer, den
  Knopf; `tests/test_support.py` zählt ihn — diese Zahl hält die Grenze zur
  verbotenen Telemetrie.
- **Nichts ungesehen:** Die Vorschau zeigt den ganzen Text samt Anhängen und
  Gesamtgröße.
- **Das Bildschirmfoto entsteht vor dem Dialog** (`window_shot(self)` im
  Fenster), aus vorhandenen Bildpunkten über `screen().grabWindow(winId())`
  ohne neues Rendern des womöglich defekten Modells; nur wenn das leer bleibt,
  `grab()`. Nur das Solidon-Fenster, nie der Bildschirm.
- **Der abgelegte Ordner ist ein Weg, kein Notausgang:** *Bericht ablegen* steht
  dauerhaft in der Knopfleiste (§37.2); *Selbst per E-Mail senden* erscheint
  erst, wenn ein Versand scheiterte.
- **Einmal erzeugt, identisch verwendet:** Die Sitzung wird einmal im Arbeiter
  gespeichert (Kopie von Dokument und Bericht, eigene Quellzuordnung;
  unveränderliche Datei-Bytes geteilt), ebenso die Protokollbytes — Vorschau,
  Versand und Ablage nehmen dieselben. Bis der Anhang fertig ist, zeigt der
  Dialog die Vorbereitung und sperrt den Versand; Abwahl und Schließen gehen,
  ein geschlossener Dialog verwirft späte Antworten. `report.log_tail()` liest
  rückwärts höchstens 1 MiB für die letzten 400 Zeilen.
