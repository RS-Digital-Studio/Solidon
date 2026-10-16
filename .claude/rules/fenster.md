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
  - "app/ui/card_width.py"
  - "app/ui/feature_list.py"
  - "app/ui/panels.py"
  - "app/ui/layout_lifetime.py"
  - "app/ui/feature_editing.py"
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
  Dokumentidentität/Werkzeugnummer.
- Zeichnen, Formen, Skelett: Kürzel oben, Escape nimmt Unfertiges, Strg+Z
  die letzte Geste, *Fertig* ohne Dialog (RM-561). Formen/Skelett haben
  denselben lokalen Undo-Weg für Menü und Strg+Z, Zeichnen deaktiviert die
  globale Aktion. Leerer Editor nimmt keinen Dokument-Schritt zurück.
- Reiter können in eigene OS-Fenster wechseln. `DetachableTabs` hält ihren
  Platz als Hülle im Stapel; `widget`, `indexOf` und `currentWidget` beziehen
  sich weiter auf den echten Inhalt. Schließen und *Zurück in Solidon* hängen
  denselben Inhalt zurück. Sichtbarkeit und Meldungsmarken folgen dem Reiter,
  nicht seiner Nummer. Die Anordnung liegt nur in `UiSettings.tab_layout`;
  fehlende Monitore begrenzen Fenster auf vorhandene Bildschirmflächen.
- Nichtmodale Dialoge hebt `_DialogsStayAbove` über das Hauptfenster, sonst
  verschwinden sie unter macOS dahinter; nie `Qt::Tool`, das teilt Kürzel.
- Karten rasten auch unten links, unten rechts und am unteren Rand ein.
  `CardPlace` speichert den waagrechten Anteil am unteren Rand; die Unterkante
  bleibt beim Wechsel der Inhaltshöhe erhalten. Die Werkzeugzeile bleibt frei.
- Drei Zonen: links Baum/Parameter/Verlauf, Mitte Viewport, rechts eine Karte
  mit den Reitern Auswahl, Prüfbericht, Chat (F9 blendet sie aus). Keine
  Betriebsarten. Die Karte misst die vordere Seite (`CurrentPageTabs`).
  Linke und rechte Karte liegen bündig an Fensterrand und Leiste
  (`overlay.EDGE`, Entscheidung Robert), rund ist nur die freie Ecke; die
  Auswahlkarte misst Inhalt und Schrift (`card_width.py`); Zeilen und
  Handlungsspalten sind Maßstab, keine Fensterquote. Mögliche senkrechte
  Rollbalken zählen mit Stilmaß unabhängig von Sichtbarkeit, ohne neue
  Mindesthöhe; Grenze ist die logische Hostfläche.
  XYZ-Querbedarf ist unabhängig von der Rasterform; `_fit_fields` zieht
  Feldbreite und -höhe mit der aktuellen Schrift nach.
  Andere Reiter behalten ihre Vorgabe, eigene Reiterfenster ihre Größe.
- **Die Seitenkarten sind verschiebbar** (Bauplan §2.5): Lage als
  `overlay.CardPlace` in `UiSettings.card_places`; gezogen wird ein Umriss
  (`CardGrip`), ein Rand trägt eine Karte (`settled_places`), passt die
  Anordnung nicht, gilt vorübergehend die Stammlage. Ansicht, Ansichtsleiste
  und Tour lesen die Lücke über `free_span`, nie feste Seiten.
  Beim Ziehen zeigen Umriss und Satz das Ergebnis (zweiter Umriss für die
  andere, `_drag_sentence`); schwebend steht die Oberkante (`floating_top`).
- Befunde und Halt holen den Bericht nie nach vorn: `SignalTabBar` zählt, blinkt
  und markiert Ungesehenes; `_focus_report` nur auf Bitte (Statuszähler,
  *Prüfbericht*, Exportprüfung, Slicen, G-Code).
- Eine neue Auswahl holt den Reiter Auswahl; Verlassen gilt bis zum Wechsel.
  Nicht aus dem Bericht und nicht beim Wiederherstellen nach einer Auswertung
  (`_SelectionPage.held`), nicht über eine Tour.
  Ein Zug im Bild, der Werte in eine Handlung legt (`FeaturePanel.valuesTaken`),
  holt ihn immer: Sein *Übernehmen* steht dort.
- `announce` ergänzt die Statuszeile um eine passive Quittung (`action_notice`):
  ohne Fokus, Klick, RichText; ab acht Sekunden. Nie über einer Karte, ohne
  Platz nur Statuszeile; der nächste Schritt nimmt beide mit. Fortschritt
  überschreibt sie nicht. Keine neue Zone, kein zweites Live-Ereignis für
  Bildschirmleser.
- Einladungen (`survey.ViewNotice`) bleiben nichtmodal ohne Fokus über der
  Ansicht, nie unter Karten. Neue Overlays bei `keep_clear_of` anmelden.
  Erst Zeigen zählt als gesehen; nur erfolgreiche Datei, Slicen oder Öffnen
  zählen als Anlass. Schwellen, Platzsuche und Rückfragenvertrag stehen in
  `regel-fenster.md`, „Fenster“.
- Die Einladung der leeren Szene steht nicht über Skizze, offenem
  Operationsdialog oder Vorschau: Wer einen dieser Zustände schaltet, ruft
  `_show_invitation`.
- Arbeitsbeginn auf der Startseite ersetzt das leere/offene Projekt über
  `_begin_from_the_start_screen` mit `_may_discard`; `start_empty` meldet Erfolg.
  `run_operation`/`start_sketch` sowie Einfügen/Download wechseln so in den
  Arbeitsbereich; Kürzel und Suche bleiben erreichbar, Vorschau liegt nicht
  hinter der Startseite.
- Eine Geste baut das Fenster einmal: `_on_tree_selection` überlässt Menübau
  dem Merkmalsignal; `_fields_this_round` merkt Merkmal und `FeaturePanel.serial`
  derselben Runde. Bei neuen Signalen die teuren Aufrufe zählen.
- Tour ist ein Angebot: rechter Reiter für Beispiele (`ui/tour.py`, Schritte
  `core/tour.py`), Erkennung über `projectChanged`, Weiter auch ohne. Warnung
  und Vorwahl der Startansicht lassen sie stehen, ein Projektwechsel räumt sie
  ab; Erkennungswerte passen zu `make_examples.py`. Schritte messen ihre Höhe
  (`ContentScroller`), ohne Tooltip, aufklappbar per Klick und Taste (RM-553);
  einen Reiter derselben Karte rahmt die Tour (`point_at`), statt ihn zu holen
  (RM-573).

## Rückfragen

**Eine Meldung ist kein `QMessageBox`, eine Eingabe kein `QInputDialog` oder
`QColorDialog`** (Z5): `message_dialog`, `input_dialog`, am Ort `place_popup`;
nur die Fragen hier bleiben `QMessageBox`. Erfolg und Hinweis quittiert der
Dialog selbst (`acknowledge`, Z2), `inform` nur ein Scheitern (`test_input_dialog`);
eine Fehlermeldung mit Handlung (`show_error`) darf modal sein (Z2-Ausnahme).
Fehler, Warnung, `inform` und eine Quittung ohne Knopf sagen sich dem
Bildschirmleser an (`QAccessibleAnnouncementEvent`), eine Eingabe nicht.

Die gewollten Ausnahmen von Regel 19, und was sie davon abhält, zur Blockade zu
werden:

- **Löschen im Verlauf:** Die Nachfrage nennt mitbetroffene Schritte beim
  Namen, mit Nummer und Titel wie im Verlauf (`history.named_steps`: bis vier
  alle, sonst drei und „und N weitere“), und den Rückweg über Strg+Z.
- **Wiederherstellen nach einem Absturz** und **Verlust einer Generierung**
  fragen: Beides ist ohne Frage unwiderruflich weg.
- **Die lange Merkmalserkennung wird angeboten** (§21.1): Oberhalb der
  automatischen Grenze nennt die Frage Dauer und Speicherbedarf; die
  Alternative, auch das Schließen, lädt mit begrenzter Erkennung. Der Befund
  `perceive.too_large` trägt *Alle Merkmale erkennen* an jedem Folgeschritt
  des Körpers, wo am Ladeschritt eine Wahl steht
  (`history.recognition_reopenable`), an einer Sammelzeile für alle ihre
  Körper; am Speicherfehler zuletzt und nicht hervorgehoben.
- **Export** (§29): Eine geschriebene Datei holt kein Undo zurück. Der Export
  prüft, bringt den Bericht nach vorn und fragt erst ab
  `warning` (`dialogs.confirm_export`; der Lizenzhinweis §16.3 ist `info`),
  Weitergehen als Vorgabe; der Dialog nennt die ersten Sätze.
- **Slicer-Übergabe:** `confirm_handover` fragt vor *Slicen* und *Im Slicer
  öffnen* nur bei **Fehlern** der gewählten Platten, nicht bei Warnungen;
  Weitergehen ist die Vorgabe.
- **Danach weiß der Kunde, wo die Datei liegt:** *Ordner zeigen* steht neben der
  Ankündigung, solange sie steht (`announce` nimmt ihn mit der nächsten mit),
  und öffnet über `QDesktopServices`.
- **Wer nur hinsieht, wird nicht gefragt:** Beim Schließen fragt das Fenster nur,
  wenn etwas verloren ginge, das nicht in den Dateien des Kunden steht
  (`Session.only_imported`). `Session.modified` bleibt; das Schließen ohne
  Frage räumt die Sicherung selbst weg.

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
  wer ihn braucht. Was ein *Objekt entfernen* mitnimmt, steht zugeklappt darunter
  (`removal_groups`), sonst mit „(Ergebnis entfernt)“.
- **Die Tastatur kann alles, was die Maus kann:** Einfg, Alt+Pfeil, Leertaste,
  Esc — am Verlauf und nur dort, wie Entf.
- **Mit Einfügemarke zeigt die ganze Oberfläche den Stand davor**
  (`Session.displayed_document`), und jede Operation über `Session.apply` landet
  dort. Abläufe mit eigener Buchführung (Teilen mit Stiften, Deckel, Gegenstück,
  Auto Split, Erzeugen, Agentenvorschlag) sagen ab, mit *Einfügen beenden* als
  Weg; Export und Druckeinstellungen beenden das Einfügen zuerst. Erzeugen fragt vor dem Start
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
  können den Halt lösen), Rückgängig, *Schritt löschen* und die Wege am
  haltenden Befund (`revision.halt_finding`, im Bericht `action_refusal(at_halt=)`).
- **Die Oberfläche sagt es vorher** (`_halt_reason`, die erste Frage in
  `_reason_locked`): Aktion, Suche und Karte tragen den Grund mit
  Schrittnummer und Titel, ebenso Automatisch teilen, Einfügen, Erzeugen,
  Zeichnen, Formen, Skelett und der Filamentwähler — dieselbe Bauart wie Lizenz-
  und Gestensperre. Die Werkzeugzeile bleibt frei — Messen, Analyse, Schichten
  lesen nur. Das Merkmalfenster gehört dazu
  (`FeaturePanel.set_locked`): graue Knöpfe **und** der Grund als sichtbare
  Zeile, dazu in Kurzhilfe, Statuszeile und zugänglicher Beschreibung; die
  Sperre überlebt den Neuaufbau der Zeilen und fällt nach einem Undo
  (`test_a_halted_chain_takes_no_new_step_and_names_the_way_on`). Die
  Freischaltung sagt sichtbar nur die Zeile unter dem Suchfeld.

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
- Ohne Knopf nach `error_handlers` bietet `handled_actions` *Eingabe
  korrigieren* mit Rat im Tooltip. Satz statt Knopf (`unhandled_advice`): ohne
  Handler, `NEEDS_OP` ohne Schritt, nicht `left_out`. Knopfzeile, Kontextmenü
  und Vorwahl teilen den Abgleich.
- Vorgewählt werden nur Fehler und Warnungen mit Handlung (`_preselect`). Nach
  einer Befundhandlung bleibt der Fokus im Bericht (`_focus_parked`): an der
  nächsten Befundzeile, sonst an der Übergabe.
- Lokale Erkennung behält die Zielkörper des Befunds; erst der Originaltreffer
  bestimmt einen. Baumauswahl ersetzt dieses Ziel nicht. Maus und Tastatur
  verwenden denselben Treffer.
- Befundklick (§2.7): Ort → Kameraflug und `mark_finding`; sonst Körper → Auswahl
  und Rahmen (`reset_camera`), neues Projekt → `frame_next_scene`;
  sonst `op_id` → `HistoryPanel.point_at`. Ortsmarken: `ansicht.md`, „Was
  gefärbt wird“, Einzelheiten in `regel-fenster.md`.

## Das Merkmalfenster

- **Offen ist genau eine Handlung, die scharfe** (RM-510): `_arm` klappt auf
  (`_open_only`), die Knopfzeile steht darunter (`feature_footer`), ein Kopf macht scharf, Zugeklapptes nennt seine Werte. Ohne
  Auswahl schweigt es; die Anleitung entfällt nach dem ersten Merkmalklick.
  Am Anker einer Gruppe („Kammer 1“ im Baum) führt ihre Handlung
  (`actions.group_action_first`), sonst stünde *Fläche versetzen* mit 0 mm offen.
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
- **Eine Absage steht als Zeile mit ihrem Grund** (RM-535): `_show_feature_rows`
  lässt keine aus. *Merkmal verschieben* führt an Zapfen, Senkung, Kugel und Ring
  ins Bild wie *Bohrung ändern* (`MEASURED_WHILE_MOVED`).
- **Ein zusammengelegter Grund spricht für alle, unter denen er steht:**
  `_folded` macht aus gleich begründeten Absagen eine Zeile („Hier nicht möglich:
  Verschieben, …, Entfernen. <Satz>“); der Satz verneint die
  **Voraussetzung**, nicht eine Handlung („trägt kein Maß, an dem sich Lage
  oder Größe ändern ließen“), und nennt den Weg, der bleibt.
- **Die Spalte rollt nur senkrecht** (RM-488): `panels.ColumnScroller` nimmt
  die Mindestbreite des Inhalts und meldet sie mit `tell_the_zone` bis zur
  Karte, sonst steht sie einige Runden zu schmal; Auswahlfelder baut
  `column_choice`, sonst verlangt ihr längster Eintrag die Spalte.
- **Das i einer Handlung** zeigt beim Darüberfahren ihren Satz, der Klick
  öffnet `manual.help_for_action` (RM-554).
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
  unangetastet; abgelehnt wird nur eine Drehung an einem gebundenen Wert. Jedes
  Zahlenfeld des Schritts trägt im Merkmalfenster fx, mit oder ohne Ausdruck
  (`_expression_entry`, §13, RM-555) — nur in den Handlungen dieses Schritts
  (`_schemas_of`), nie in gleichnamigen Feldern der Nachbarn.
- **Entf** nimmt an Dach oder Einzelmerkmal den Schritt des Bausteins
  (`MainWindow._delete_the_chosen_feature`), nie den Körper; ohne Baustein gilt
  `remove_feature`; greift auch das nicht (Fläche, Gewinde, Verrundung), fällt
  der Körper — mit Ansage und Strg+Z (Regel 19). Ohne Merkmal nimmt Entf alle
  markierten Körper (`on_bodies`). *Ausblenden* heißt am Merkmal *Körper
  ausblenden*.
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
  mit eigenem Editor (`perceive.actions.COLLECTED_KINDS`) steht in
  `FeatureAction.elsewhere`, und ein Knopf öffnet den Dialog des Schritts. Ein
  neuer Sammelparameter trägt seine Art dort ein.
- **Ein Langloch aus einem Schritt gehört dazu:** Hat `slot_hole` es gezogen,
  ändert *Übernehmen* diesen Schritt (`_prepare_slot_change`,
  `_commit_slot_change`) und legt keinen zweiten obenauf. Wer eine Operation
  baut, die ein Merkmal aus ihrem früheren Schritt noch einmal anfasst, fragt
  zuerst `created_by`.
- **Karte:** nur `perceive.actions.OFFERED_AT_A_PART` (*Stift für Bohrung* an
  Innengewinde und Bohrung), danach `not_offered_at`.

## Der Hauptknopf

Wächter `test_style.py`.

- Hauptknopf nur über `style.make_primary` (Akzent und Halbfett), abgeben mit
  `leading=False`, nie `setDefault(True)`; wer führt, sagt `leading_action`.
- Höchstens ein Akzentknopf je Fenster: Hinweishandlungen (`ErrorNotice`, Rat,
  Übermaß) sind normale Knöpfe. Ohne Handlung `no_primary`, sonst macht Qt den
  ersten `autoDefault`-Knopf zum Default.
- `make_danger` genau an `DestructiveRole`, nie mit `make_primary`, nie an
  Abbrechen/Schließen. Rückfragen vor Verwerfen oder Löschen: `no_primary`,
  Fokus und Escape auf Abbrechen.
- Ruhezustand: nur *Bausteinkatalog …* im Akzent, Kartenrand in `line`, aktiver Reiter
  in Schriftfarbe (`test_resting_state.py`). Ein angebotener Merkmalauftrag
  führt auch gesperrt; `FeatureEditPriority` ändert dabei keinen Fokus.
- Fokus verschiebt keinen Akzent (`_FocusTakesNoAccent`); Enter gehört dem per
  Tab gewählten Knopf (`test_enter_key.py`).
- Stylesheets an einen `objectName`, nie typlos an einen Vorfahren. Klicktests
  belegen keine Knopffarbe.
- Umschalter nennen das Werkzeug, Knöpfe die Handlung; `test_interface_limits.py`.

## Ein Dialog, der höher ist als sein Inhalt

Überschüssiger Raum braucht **eine** Stelle: ein `addStretch`, wo Leere nicht
stört, oder ein Widget, das ihn nutzt. Statusmeldungen misst
`style.WrappedNote`.

**Dialoggröße nach Auslöser:** `ContentHeight` misst den natürlichen Inhalt
einmal nach dem Anzeigen, die Höhe erst bei fertiger Breite (Umbruch).
Manuelle Breite und Höhe gelten für die Dialoglebensdauer; Mehrinhalt rollt,
Aktionsknöpfe bleiben außen. Die Höhenuntergrenze sind vollständige äußere
Knöpfe plus eine aktuelle Inhaltszeile und gegebenenfalls Querleiste; nur
darunter muss eine Nutzerhöhe wachsen (`dialog_footer`, `karte-app-ui.md`).
Ausdrückliches Klappen darf die automatische Höhe am festen Fensteranker
anpassen, bis zum Bildschirmrand, der Rest rollt. Passives (Prüfung, Status,
Suche, Reiter, bedingte Zeilen) wächst nach der Anfangsmessung um verdeckten
Inhalt bis zur Bildschirmhöhe, nach Klappen ab dem Anker, und schrumpft nie
(RM-487). `contentSizeChanged` führt auch Listen- und Schriftwechsel diesem
passiven Größenweg zu. Kurzer Anfangsbedarf ist kein dauerhaftes
Viewport-Minimum: Der innere Rollbereich gibt Platz an die Knopfleiste ab.
Beim Öffnen, Monitorwechsel, geänderter nutzbarer Fläche oder logischer DPI
sichern `DialogScrollArea` und `fit_dialog_to_screen` die Erreichbarkeit.
Anfangsbreite samt zugeklappten Teilen und Balken: `style.expanded_width`
(RM-342 D-N5). `ContentHeight.fit` misst und legt ohne senkrechten Balken
und verbreitert um fehlende Mindestbreite samt Balken; jede Klappe misst
`explicit` (FD-198 bis FD-200).
`_hidden_height` zieht eine rangefreie AsNeeded-Querleiste nicht ab.

**Formulare: eine Zeilenform, eine Kante.** Keine Beschriftung über dem Feld
(`DontWrapRows`); das Fenster wird so breit wie seine breiteste Zeile, eine
zugeklappte Rückseite zählt mit. Eine Beschriftungsspalte je Dialog
(`panels.align_forms`, gerahmte Reiter über `apart`), jedes Layout (auch Karten)
mit Rasterabstand (nie Qts 6), gleich breite Felder
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
Für Druckerwahl und Druckdialog gilt `druckerwahl.md`.

## `setParent(None)` macht ein Kind zum Fenster

Vor Einzelabbau aus weiterlebendem Layout löst `layout_lifetime.detach_from_layout`
das Widget; `removeWidget` entwertet gehaltene Itemhüllen. Weggeräumt wird mit
`hide()` und `deleteLater()`, nie über den Elternteil.
Nach `exec` Rückgabewerte im `try` lesen, den Dialog im `finally` freigeben.
Nichtmodale Dialoge geben sich am `finished`, über `WA_DeleteOnClose` oder
im Endrückruf frei (`test_dialog_lifetime.py`).

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

`OverlayHost._share_room` verteilt die Höhe einer Zone auf ihre `RoomTaker`
(`test_overlay`): nie mit gerade gesetzten Höhen (`extra_height`,
nicht `natural_height`); abgezogen wird, was nicht den Karten gehört; jede
Karte nennt ihren Boden (`least_height`, nie über ihrem Wunsch); viele feste
Zeilen rollen (`FittedScroller`). Ungleiche Zeilen misst `rows_height`, und
`wanted_height` fragt dieselbe Quelle; Inhalt unter der Liste samt Abstand
gehört in beide Rechnungen. Reiterrahmen: `QTabWidget.sizeHint()` minus
höchste Wunschhöhe der sichtbaren Seiten, nie minus `stack.sizeHint()`.

**Gesetzt wird einmal je Durchlauf** (`_place_later`, gleitend; `resizeEvent`
und `reflow` sofort, auch im Gleiten); wer misst, legt fest
(`guide_targets._settle_cards`). **Wer Inhalt wachsen lässt, sagt es bis zur
Zone** (`tell_the_zone`, dann `reflow`), sonst wächst sie zweimal.

## Rückmeldung und Fehlerbericht

Ein Dialog für beides (`support_dialog.py`; `report_error` mit `kind=crash`,
§33.1). Von allein geht nichts (`kern.md`, „Fehler“); die Vorschau zeigt alles
samt Anhängen; das Bildschirmfoto entsteht vorher (`window_shot` im Fenster,
nur das Solidon-Fenster, ohne neues Rendern; unter Windows `PrintWindow`, weil
`grabWindow` kein D3D12 sieht); *Bericht ablegen* steht immer, *Selbst per
E-Mail senden* erst nach gescheitertem Versand (§37.2); Sitzung und Protokoll
entstehen einmal im Arbeiter und gelten für Vorschau, Versand und Ablage, bis
dahin ist der Versand gesperrt. Warum und wie: `regel-fenster.md`.


### Formen und Skelett: Gesten

- Ein Pinselzug reicht vom Drücken bis zum Loslassen, auch neben dem Modell;
  seine Proben teilen `Stroke.gesture`, jede Geste ist eine Etappe
  (`Stroke.brush` 2, alte rechnen wie gespeichert). Zählung und lokales
  Rückgängig nehmen die Gruppe samt wartender Proben; Beenden lässt den Pinsel los.
- Zu grobes Netz gleicht der Arbeiter an, neu wie geöffnet; ins Dokument erst
  mit *Fertig* und neuen Zügen, eine Transaktion (`insert_before(changed=)`).
  Scheitert es, kein zweiter Versuch.
- Skelett: n Knochen, n + 1 Klicks, Enter beendet die Kette, Ziehen am Gelenk
  beugt (gebundener Winkel: Satz statt Zug), *Fertig* ohne Dialog. Escape
  nimmt nur Unfertiges.
- Die Gestenleiste trägt ihre `MapLegend`; ein Kartenwechsel entwertet Befund
  und Wartehinweis.
