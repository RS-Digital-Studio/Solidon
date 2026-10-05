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

- Offene Formen-/Skelett-/Zeichengesten gehören zur Speicherfrage.
  `_has_unsaved_gestures` vergleicht mit gespeicherten Parametern, auch nach
  Löschen aller Gesten. Speichern übernimmt erst den Editor; ein noch nötiger
  Operationsdialog sperrt den Projektwechsel bis Übernehmen. Verwerfen und
  eingehender Projektwechsel räumen Ziele, Karten, Vorschauen und
  Wiederherstellungsdaten gemeinsam ab.
- Gespeicherte Gesten öffnen auf ihrem Eingang:
  `Session.scene_before_step_async` im Vorschauarbeiter, Antwort gebunden an
  Dokumentidentität/Werkzeugnummer. Verfeinerung über `Session.insert_before`
  im Revisionsarbeiter ersetzt Schrittkennung und Eingangsbindung.
- Formen/Skelett haben denselben lokalen Undo-Weg für Menü und Strg+Z; leerer
  Editor nimmt keinen Dokument-Schritt zurück. Zeichnen hat eigene Kürzel
  und deaktiviert die globale Aktion.
- Drei Zonen: links Baum/Parameter/Verlauf, Mitte Viewport, rechts eine Karte
  mit den Reitern Auswahl, Prüfbericht, Chat (F9 blendet sie aus). Keine
  Betriebsarten. Die Karte misst die vordere Seite (`CurrentPageTabs`).
- Warnungen holen den Bericht nie nach vorn, sie nähmen der Auswahl die Felder:
  `SignalTabBar` zählt und blinkt bis zum Ansehen; `_focus_report` nur auf Bitte.
- Eine neue Auswahl holt den Reiter Auswahl; Verlassen gilt bis zum Wechsel.
- `MainWindow.announce` ergänzt die Statuszeile um eine passive Overlayquittung:
  kein Fokus, keine Klicks, kein RichText; mindestens acht Sekunden, lange
  Texte länger. Neue Quittung ersetzt alte, Fortschritt überschreibt sie nicht.
  Kontextwechsel/Abbau beendet den Timer. Keine neue Zone und kein zweites
  Live-Ereignis für Bildschirmleser.
- Einladungen stehen über der Ansicht, nie unter Karten: `survey.ViewNotice`
  für `SurveyNotice` nach 15 aktiven Minuten und `SupportNotice` nach dem
  dritten erfolgreichen Export/Slicerstart einer Version; nichtmodal,
  ohne Fokus beim Erscheinen, bis zum Klick sichtbar.
  `spot` sucht die oberste freie Stelle gegen `keep_clear_of` (Zonen,
  Ansichtsleiste, Vorschau-/Ziehwertband), zuerst zwischen, sonst unter der
  kürzeren Karte. Neue Overlays dort anmelden. Nur Unterstützung weicht der
  Rückfrage aus, nie gegenseitig. Nicht über Startseite/modalem Dialog zeigen
  (Druckdialog nach `exec`), sonst beim nächsten Ergebnis. Erst Zeigen zählt
  als gesehen; `_announce_written`/`handedOver` zählen nur erfolgreiche Datei,
  Slicen oder Öffnen, nie Versuch, Abbruch, Fehler oder Rückfrage.
- Arbeitsbeginn auf der Startseite ersetzt das leere/offene Projekt über
  `_begin_from_the_start_screen` mit `_may_discard`; `start_empty` meldet Erfolg.
  `run_operation`/`start_sketch` sowie Einfügen/Download wechseln so in den
  Arbeitsbereich; Kürzel/Palette bleiben erreichbar, Vorschau liegt nicht
  hinter der Startseite.
- Eine Geste baut das Fenster einmal: `_on_tree_selection` überlässt Menübau
  dem Merkmalsignal; `_fields_this_round` merkt Merkmal und `FeaturePanel.serial`
  derselben Runde. Bei neuen Signalen die teuren Aufrufe zählen.
- Tour ist ein Angebot: zusätzlicher rechter Reiter für Beispielprojekte
  (`ui/tour.py`, Schritte `core/tour.py`), Erkennung über `projectChanged`,
  Weiter auch ohne Erkennung. Warnung lässt aktive Tour stehen, Projektwechsel
  räumt sie ab. Erkennungswerte müssen zu `make_examples.py` passen
  (`test_tour.py`).

## Rückfragen

Die gewollten Ausnahmen von Regel 19, und was sie davon abhält, zur Blockade zu
werden:

- **Löschen im Verlauf:** Die Nachfrage nennt mitbetroffene Schritte beim
  Namen, mit Nummer und Titel wie im Verlauf (`history.named_steps`: bis vier
  alle, sonst drei und „und N weitere“), und den Rückweg über Strg+Z. Titel
  aus `history.step_titles`, derselben Quelle wie die Zeilen und der
  Löschtitel; ein gelöschter Schritt trägt keine Nummer mehr.
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
Stand, und dahinter wird nichts gerechnet. Gibt es keinen, sagen Leerkarte und
Baum den Schritt, mit *Schritt korrigieren*, nie die Einladung (RM-458). Zwei
Stellen halten das, beide sind nötig:

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

- Gleiche Probleme bieten dieselben Handlungen: `panels.FINDING_ACTIONS`;
  `test_value_labels.py` prüft die Kennungsfamilie hinter dem Punkt.
- „Passt nicht“ und „liegt woanders“ unterscheiden sich über `prepare._fits_at_all`.
  Einer 3MF mit Bettkoordinaten (Bambu/Orca/Elegoo) hilft *Auf dem Bett anordnen*,
  nicht *Modell teilen*.
- Gleiche Meldungen bündeln ab zwei nach Satz, Kennung, Schwere, Schritt und
  Handlungen; Anzahl davor in Klammern. Klick wählt alle Körper, Handlung fragt
  die Teilmenge. Gewählt wird beim Drücken (`_ReportList.leftPressed`). Nur
  gemeinsame Merkmale, aber alle Umrissorte eines Körpers werden mitgeführt.
- **Erst die Befunde** (RM-508): Kopf eine Zeile — Status, Zähler ohne Nullen
  (zugleich Klappe der Liste), *Prüfumfang* mit den Kennzahlen; ein Grund nur
  bei unvollständiger Bewertung. Hinweise allein klappen zu, Fehler oder
  Warnung öffnen. Zeilen zeigen `headline`, die gewählte ganz; die Liste gibt
  bis drei Zeilen nach (`LEAST_REPORT_ROWS`), dann rollt der Kopf. Darunter `finding_meta`
  („Hinweis · Dose · intern geschätzt“), ein Zeige-Knopf (`_SHOWING_ACTIONS`),
  ein Folgesatz nur beim Fehler, die Nebenfolge nur bei `effect_worth_showing`.
  Filter ab `FILTER_FROM` Zeilen; Übergabe und Export unter dem Rollbereich;
  der Nachbau steht in der Karte der Handlungen.
- `actions_for(finding)` speist sichtbare Knopfzeile und Kontextmenü (§2.7).
  Jeder Befund bekommt `suggestions` oder begründetes `OHNE_KNOPF`
  (`test_finding_ways.py`); `actions_for_document` entfernt Handlungen ohne
  notwendigen Schritt/Körper (`test_finding_actions.py`).
- Op-Fehler sind Befunde `op.<operation>.<Ausnahme>` mit Kettenhalt, kein Dialog.
  *Eingabe korrigieren* ruft `edit_operation(op_id, field)` auf und ersetzt den
  Schritt (§15.4). Handler mit `_entry_of` gehören in `dialogs.NEEDS_OP`,
  solche mit `_object_of`/`error.object_id` in `panels.NEEDS_LIVE_BODY`.
  Nur nackte `=@breite`-Bindungen (`expressions.bound_name`) führen in die
  Parameterleiste.
- Bleibt nach `error_handlers` kein Knopf, bietet `handled_actions` *Eingabe
  korrigieren* mit Rat als Tooltip; der Fehlerdialog zeigt Räte über
  `dialogs.unhandled_advice` als Sätze. Knopfzeile, Kontextmenü und Vorwahl
  benutzen denselben Abgleich.
- Lokale Erkennung behält die Zielkörper des Befunds; erst der Originaltreffer
  bestimmt einen. Baumauswahl ersetzt dieses Ziel nicht. Maus und Tastatur
  verwenden denselben Treffer.
- Befundklick (§2.7): Ort → Kameraflug und `mark_finding`; sonst Körper → Auswahl;
  sonst `op_id` → `HistoryPanel.point_at`. Ortsmarken verwenden `FINDING_COLOUR`
  vor Material, Abstand als Radius, Titelgrund in Kamera-Oben-Richtung und
  `Finding.outline` als Rand (`ansicht.md`, „Was gefärbt wird“). Marke nicht
  nach vorn ziehen; nur Beschriftung `always_visible`. Szenenorte gehen durch
  `view_point_of`, Kartenorte kommen in `_map_ready`. Mehrschritt-Transaktionen
  tragen am Gruppenknoten nur `OPS_ROLE`.

## Das Merkmalfenster

- **Offen ist genau eine Handlung, die scharfe** (RM-510): `_arm` klappt auf
  (`_open_only`), ein Kopf macht scharf, Zugeklapptes nennt seine Werte. Ohne
  Auswahl schweigt es; die Anleitung entfällt nach dem ersten Merkmalklick.
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
  oder Größe ändern ließen“), und nennt den Weg, der bleibt.
- **Die Spalte rollt nur senkrecht** (RM-488): `panels.ColumnScroller` nimmt
  die Mindestbreite des Inhalts; Auswahlfelder baut `column_choice`, sonst
  verlangt ihr längster Eintrag die Spalte.
- **Ein Feld einer Merkmalsart steht nur an ihr** (`perceive.actions._carried_by`):
  die Steigung am Gewinde, nicht an der Bohrung.
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

- Hauptaktionen entstehen über `style.make_primary`, nie direkt über
  `setDefault(True)`: Akzent und halbfette Schrift bilden zwei Kodierungen.
  Verwerfen verwendet `make_danger` (Fehlerrot, Schrift aus `readable_on`,
  Handlungswort; etwa *Abbrechen* unter *Übernehmen*). `test_style.py` prüft
  gezeichnete Fläche/Schrift und verbietet den direkten Default-Aufruf.
- Dialoge ohne Hauptaktion rufen `no_primary`, andere `make_primary` auch bei
  anfangs gesperrtem Knopf. Sonst macht Qt beim ersten Anzeigen den ersten
  `autoDefault`-Knopf selbst zum Hauptknopf. Nur ein gezeigtes Fenster belegt
  dieses Verhalten.
- Fokus verschiebt keinen Akzent. `style._FocusTakesNoAccent` wird einmal
  durch `make_primary`/`no_primary` angemeldet, nimmt Nebenknöpfen `autoDefault`
  und klickt den per Tab/Umschalt+Tab gewählten bei Enter selbst
  (`enter_belongs_to_focus`). Maus, `setFocus` und von gesperrten/verborgenen
  Knöpfen vertriebener Fokus (Qt meldet Tab) lassen Enter beim Hauptknopf.
  Fensterwechsel erhält die Wahl; kein Dialog baut eigene Logik dafür.
  `test_enter_key.py` und `test_style.py` prüfen zugestellten Fokus;
  `WA_DontShowOnScreen` aktiviert kein Fenster.
- Stylesheets ohne Selektor am Vorfahren ersetzen für gesetzte Eigenschaften
  die Anwendungsfarben aller Nachkommen: besonders `background`, nicht ein
  reines `border` wie `_flash`. Deshalb `objectName`-Selektoren; bei notwendiger
  breiter Regel Hauptknopffarben ausdrücklich setzen (`#surveyNotice #surveyGive`)
  und weiterhin `make_primary` verwenden. Klicktests belegen keine Knopffarbe.
- Umschalter nennen das Werkzeug, Knöpfe die Handlung (*Trennen*, *Jetzt
  trennen*); `test_interface_limits.py`.

## Ein Dialog, der höher ist als sein Inhalt

Von Hand gezogen oder beim Öffnen an den Inhalt angepasst — überschüssiger
Raum braucht **eine** Stelle, sonst verteilt Qt ihn als Lücken zwischen
Widgets fester Höhe. Die Stelle ist ein `addStretch` dort, wo Leere nicht
stört, oder ein Widget, das den Platz nutzt. `style.WrappedNote` misst
Statusmeldungen ohne die gepinnte Höhe, denn `QLabel.heightForWidth` meldet
nie weniger als die Mindesthöhe.

**Dialoggröße nach Auslöser:** `ContentHeight` misst die natürliche Geometrie
des aktuellen Inhalts einmal nach dem Anzeigen, die Höhe erst in der neuen
Breite (Umbruch). Eine manuell gezogene Breite
oder Höhe bleibt für die Dialoglebensdauer maßgeblich; Mehrinhalt rollt im
äußeren Scrollbereich, Aktionsknöpfe bleiben außerhalb. Nur ausdrücklich
betätigtes Auf- und Zuklappen darf bei automatischer Größe die Höhe anpassen;
dabei bleibt der Fensteranker, Platz bis zum Bildschirmrand wird genutzt, der
Rest rollt. Passives (nachgereichte Prüfung, Status, Suche, Reiter, bedingte
Zeilen) wächst nach der Anfangsmessung um den verdeckten Inhalt bis zur
Bildschirmhöhe, nach einem Klappen ab dem Anker, und schrumpft nie (RM-487).
`contentSizeChanged` meldet verzögerte Innenlayoutänderungen.
Beim Öffnen sowie nach Monitorwechseln, geänderter nutzbarer Fläche oder
logischer DPI stellt `DialogScrollArea` mit `fit_dialog_to_screen` die
Erreichbarkeit wieder her. Die Anfangsbreite samt zugeklappter Teile und
Rollbalken rechnet allein `style.expanded_width` (RM-342 D-N5).

**Formulare: eine Zeilenform, eine Kante.** Keine Beschriftung über dem Feld
(`DontWrapRows`); das Fenster wird so breit wie seine breiteste Zeile, eine
zugeklappte Rückseite zählt mit. Eine Beschriftungsspalte je Dialog
(`panels.align_forms`, gerahmte Reiter über `apart`), gleich breite Felder
(`panels.even_fields`, `op_dialog.even_value_fields`); eine Zeile aus Feld und
Knöpfen endet mit `addStretch`. Beschriftungen ohne Doppelpunkt, keine zweimal
im Dialog. **Hat der Dialog eine Rückseite, setzen die Zeilen vorn, die
dastehen, die Spalte** (`dialogs.align_to_the_front`): Eine längere
Beschriftung hinten oder eine bedingte vorn bricht um, die Lesezeile *Stelle*
richtet beim Erscheinen neu aus (RM-518, höchstens 24 px hinter der längsten);
wer zwei Formulare hat, richtet aus (`test_ui_dialogs`).

**Ein Dialog, eine Form** (RM-518): Abschnitte sind flache Überschriften, kein
`QGroupBox` (Ausnahmen mit Grund im Wächter in `test_ui_dialogs`); Außenrand
`WIDE`.

**Klappen:** überall `panels.collapsible` (`sectionHeading`; eine von Hand
gebaute fängt `test_every_section_heading_is_built_by_collapsible`); zugeklappt
nennt sie ihren Inhalt (`contents=`, Wächter in `test_interface_limits`;
mit `heading_row=` steht die Überschrift in einer Zeile, der Inhalt im Tooltip),
`remember=` hält den Zustand des Kunden — nie an einer Klappe, die sich selbst
öffnet. Werte, die sich ein- und ausschalten lassen, sind eine Schalterzeile
mit eingerückten Feldern, kein ankreuzbarer Rahmen. Bei `ContentHeight`-Dialogen
werden Anfangsgröße und bedientes Klappen getrennt gemessen; eigenes Wachsen
gilt nicht als Nutzergröße. Ein Ausgang ist `RejectRole` — als `AcceptRole`
macht ihn die Knopfleiste zum Hauptknopf.

**Was eine Angabe bestimmt, steht vor ihr** (Entscheidung Robert): was eine
Liste füllt, eine Vorgabe setzt oder sperrt, davor; ein Schalter bei dem, was
er schaltet; ein Zustandssatz bei seinem Gegenstand.
Druckeinstellungen: Slicer, Drucker, Düse, Platte, Filamente, Qualität,
Profile des Slicers, Grundlage, Werte; *Werte mitgeben* bei der Übergabe
(`test_the_print_dialog_asks_in_the_order_its_answers_depend_on`). Register:
`tests/test_dependency_order.py`. Vorn davon nur Fülldichte und Stützen;
Zustand und Mitgabe über den Knöpfen, außerhalb des Rollbereichs.

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

Ein Widget ohne Elternteil **ist** ein Top-Level-Fenster. Weggeräumt wird mit
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
- **Eine Karte aus vielen festen Zeilen rollt, statt sich zu stauchen**
  (`overlay.FittedScroller`, der Prüfbericht): Erst gibt die Liste bis zu ihrer
  Mindesthöhe nach, dann rollt der Inhalt; die rechte Zone rechnet ihren
  Wunsch an der Kartenbreite (`natural_height(zone, width=)`). Warum:
  `konzepte/begruendungen/regel-fenster.md`.

`tests/test_overlay.py` hält alle drei („settles on one answer“, „moves a card
once“, „no card is pushed outside its section“). `fit_to_rows` rechnet mit
**einer** Zeilenhöhe — ungleiche Zeilen (Objektbaum) misst `overlay.rows_height`, und
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
  gespeichert, ebenso die Protokollbytes — Vorschau, Versand und Ablage nehmen
  dieselben. Bis der Anhang fertig ist, zeigt der Dialog die Vorbereitung und
  sperrt den Versand; Abwahl und Schließen gehen, ein geschlossener Dialog
  verwirft späte Antworten.


### Formsitzung: Mauszüge und Analyse

- Ein Pinselzug reicht vom Drücken bis zum Loslassen, auch außerhalb des
  Modells. Seine räumlichen Proben teilen die optionale `Stroke.gesture`-Kennung
  im vorhandenen Strichparameter. Kennung null hält alte Einzelzüge lesbar;
  die Zusatzkennung verändert deren Geometrie nicht.
- Zählung, lokales Rückgängig und Wiederholen verwenden diese Gruppe, einschließlich
  noch wartender Arbeiterproben. Eine neue Geste leert lokales Wiederholen;
  Beenden des Editors beendet auch einen noch gehaltenen Pinsel im Navigator.
- Die sichtbare Gestenleiste trägt ihre eigene `MapLegend` mit Skala und Herkunft.
  Ein Kartenwechsel entwertet alte Befunde und Wartehinweise zusammen.
