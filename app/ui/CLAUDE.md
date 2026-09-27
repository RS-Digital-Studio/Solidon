# `app/ui/` — die Oberfläche

PySide6. Darf `app.core` benutzen, die Gegenrichtung ist verboten (§8). Die
Oberfläche rechnet keine Geometrie und ändert keine — **sie ruft Ops auf.**

`loading.ProgressTiming` führt für eine Auswertung genau eine Uhr und einen
Zeittext. Statuszeile und Ladeschleier lesen denselben Sekundentakt, auch ohne
neue Fortschrittsmeldung oder Animation. Der Schleier kann verschwinden,
während die Uhr für die Statuszeile weiterläuft. Antwortzeit einer Kernfrage
zählt als verstrichen, aber nicht als Rechenzeit der Restschätzung. Stand
die vorige Zeile bei 0 % und kommt eine neue mit einem Anteil, zählt die
Schätzung ab dort (`_counted_fraction`).

Die Frage vor der Vollerkennung und jede andere Rückfrage ohne Kandidaten im
Bild mit zwei oder drei kurzen Antworten zeigt die Antworten als Knöpfe
(`AskDialog(as_buttons=…)`, entschieden von `main_window._answers_as_buttons`);
Liste und Antwortknopf bleiben als Ablage der Wahl. Die Suche an einer Stelle
rechnet in der Qualität der Sitzung (`LocalRecognitionDialog(quality=…)`), sonst
trifft sie keinen Schritt im Cache. Nach jeder Rechnung fordert `_on_busy` die
gewählte Analysekarte neu an (`_resume_map_after_idle`). Slicer heißen überall
wie auf der Packung (`labels.slicer_title`).

Beim Laden zeigt die Sitzung das Modell vor seiner Erkennung
(`Session.picture_first`, `pictureChanged` → `MainWindow._on_picture`,
`Session.picture`); ein Import, dessen Datei am Ladeschritt scheitert, wird
zurückgenommen (`importRejected`/`importConfirmed`, `_recent_candidate`). Das
Fadenkreuz der Stellenwahl sind vier deckende Arme um eine freie Mitte
(`viewport._ReticleArm`). Die Netzfehlerkarte wählt einen einzigen Körper selbst
(`_lone_visible_body`), die Rückfragekarte lädt nur ein, wo sie Platz hat
(`SurveyNotice.has_room`).

Nachlaufende Befunde erhalten die gewählte Zeile des Prüfberichts über die
gemeinsame Befundidentität, auch wenn neue Fehler die Reihenfolge ändern.
Nur wenn die bisherige Zeile entfällt oder ausgefiltert wird, gilt die
bestehende Vorauswahl einer angebotenen Handlung. Prüfungen lesen die
aktuellen Handlungsknöpfe aus dem Layout; ausgebaute Qt-Kinder können bis
zur Verarbeitung von `deleteLater` noch am Elternobjekt hängen.

Maßbeschriftungen lesen `Feature.measure_sources` über die gemeinsame
Kernauskunft. `labels.feature_measure` gruppiert gleiche Zusätze; verschiedene
Quellen bleiben je Zahl benannt. Baum, Viewport und Merkmalpanel benutzen
dieselben Texte. Tooltip, Statushinweis und Vorlesetext erklären die Quelle
ohne erfundene Genauigkeit. Die gemeinsame Feldfabrik kennzeichnet den
unveränderten Ausgangswert; aktuelle Zielwerte bleiben editierbar. Historische
Maßgruppen zeigen Schrittvorgaben und die Auskunft „Am fertigen Teil“ getrennt.
Die Viewport-Auskunft folgt dem tatsächlich dargestellten Vorschaukörper und
weicht vorübergehend der vorhandenen Fangpunktansage.

Die Exportvorprüfung nutzt den gemeinsamen Fortschritt und `CancelSignal`.
Ein kurzer gesperrter Übergang entscheidet Abbruch und Schreibbeginn zusammen;
nach dem ersten Schreibbeginn wird der gesamte Auftrag ohne Abbruch beendet.
Ein verspäteter Prüfbericht nach angenommenem Abbruch öffnet keinen Dialog.
Phasensignal, Abbruchquittung und endgültiges Workerende halten Anzeige und
Workerbezug getrennt, damit auch beim asynchronen Ende kein Folgeauftrag läuft.
Fensterkreuz und `release` brechen die Vorprüfung ebenfalls ab. Ergebnisrückrufe
sind schwach gebunden und prüfen Fensterlebensdauer und Arbeiterkennung; das
Threadende bleibt an der vorhandenen Leine. Eine Bestätigung darf `finished`
zustellen, aber weder ein beendetes Fenster noch einen ersetzten Versuch
anschließend fortsetzen.

`PlacementFlow` bietet den Wechsel echter Kanten, Mitten und belegter Achsen
als Kontextmenü des Maßes an (`_reference_menu`: Rechtsklick oder Menütaste,
über `popup` statt `exec`, weggeräumt beim Zugehen). Das Auswahlfeld hinter
jedem Maß ist am 21.09.2026 gefallen (RM-197, Robert: „das mit bezug ändern
hintendran brauche ich garnicht"). Menü und Modellklick nutzen dieselbe
`PreparedSurface` (`_reference_entries`). Fremde Körper und andere Flächen
sind kein Treffer; Mehrdeutigkeit nennt den Weg zum Menü und öffnet nichts
von selbst. Der Referenzwechsel hält den Zielpunkt fest; ein späterer Zug
behält die gewählten Bezüge und Vorzeichen. Die Absage zu parallelen Bezügen
kommt aus dem Kern (`placement._reference_error`), nicht aus einem zweiten
Satz der Oberfläche. Durchgezogene Bezugslinie, gestrichelte nötige
Verlängerung und benanntes Maßfeld erklären den signierten Abstand zur
Zielmitte, keinen Wandabstand. Während einer Modellbezugsauswahl wird keine
Übernahme vorgemerkt. Escape verwirft über den gemeinsamen Editor.
Die numerischen Operationswerte bleiben der einzige gespeicherte Auftrag;
eine dauerhafte Kantenassoziation wird nicht behauptet (§18.11, §19).
Die Fokuskette folgt dem Auge: die zwei Kantenmaße, dann die Mitten
(`setTabOrder` beim Aufbau).

**Und die Felder stehen neben dem Körper, solange man ihn ganz sieht**
(RM-197, und Robert am Halter, 22.09.2026: „solange man den körper
vollständig sieht"): `_body_on_screen` führt die projizierte Hülle des
Trägers als belegtes Rechteck, mit demselben Abstand wie um den Setzpunkt —
aber nur, wenn die Hülle ganz im Maßraum liegt und ihr Freiraum dort noch
Platz lässt; ragt der Körper hinaus oder füllt er das Bild, stehen die Felder
an ihrer Maßlinie, auf dem Körper (Kandidaten um die Linienmitte, je eine
bis drei Feldhöhen weiter). Die Verbindungslinie je Feld sagt, welches Maß
es bemaßt — sie endet in der **Mitte** der Maßlinie, nicht am
nächstgelegenen Punkt. Ein Feld deckt möglichst keine **fremde** Maßlinie
und keine fremde Verbindung (`_clear_of_lines`; die eigene Linie zählt nicht,
auf ihr sitzt die Zahl wie auf einer Zeichnung), aber es wandert dafür
höchstens `STICKY_FIELDS` Feldhöhen weiter als der nächste zulässige Platz —
Bezugskanten und Verlängerungen sind lang und bleiben erkennbar, wenn ein
Feld ein Stück davon deckt. Das Vorschauband ist ein Hindernis. **Die
Felder bleiben stehen** (Robert: „danach springen sie auch alle und tauschen
sich"): `_places_that_still_serve` behält je Feld den Platz des letzten
Aufbaus (`_field_slots`), solange er frei, im Bild, nahe am Maß und nicht
über fremder Tinte ist, die der neue Platz freiließe; die übrigen Felder
finden um die stehenden herum ihren Platz, und nur mehr Kreuzungen als in
der frischen Anordnung geben die frische frei. Verbindungen kreuzen sich
nicht, soweit ein Tausch es löst (Robert: „aufpassen dass sich die
maßlinien nicht kreuzen"): `_untangle` tauscht nach der Platzsuche paarweise
die Plätze zweier Felder, solange das Kreuzungen spart und beide am fremden
Platz frei stehen (`_fits`, `_crossings` — dieselben Funktionen wie die
Stehregel); ein breites Feld über zwei schmalen behält seine Kreuzung. Ob
zwei Strecken sich schneiden, sagt der Kern (`profile.strictly_crossing`),
nicht eine zweite Rechnung hier. **Das Maß mit dem Fokus leuchtet**
(`dimension_focus`, Akzentfarbe und breiterer Strich — Regel 18): Wer in ein
Feld klickt, sieht im Bild Maßlinie, Bezugskante und Verbindung dazu, auch
in der Tiefenstufe. **Und Übernehmen der Maßgruppe meint das gezogene
Langloch**, wenn an der gebundenen Bohrung ein Zug wartet
(`Viewport.waiting_slot_drag`, `MainWindow.slot_drag_takes_the_accept` — die
eine Antwort für Weiche, Notiz und Knopf): dann geht der Abschluss den Weg
des Merkmalfensters (`apply_slot_drag`) mit der Stelle aus den Feldern.
Trägt das Feld daneben einen neuen Durchmesser, wird daraus **ein** Schritt
(Entscheidung Robert, 22.09.2026): *Zum Langloch ziehen* mit der Stelle und
der neuen Breite (`_slot_with_width`, `SlotHoleParams.diameter`) — zwei
Schritte gingen nicht, weil das Langloch nach dem Zug neu heißt und der
zweite seinen Namen erst nach der Auswertung kennte.

**Die Maßtinte liegt im Renderer, nicht als Widget über ihm** (`_Dimensions`,
RM-198). Bis zum 21.09.2026 war sie ein maskiertes Qt-Widget über der nativen
Renderfläche; die Maske hatte je schräger Linie ein Rechteck je Bildzeile, und
bei 1682 Rechtecken verlor der Vulkan-Treiber das Gerät — „Parent device is
lost" im nächsten `submit`, ohne Fehler davor; 1380 liefen, unter D3D12
alles. Seither gehen Unterlage, Striche, Pfeile und Marken über `add_lines`
und `add_surface` mit `keep_in_front` in den Renderer, wie die
Merkmalslinien; die Zahlenfelder bleiben Qt-Fenster und liegen ohnehin über
dem Bild. Die Listen der Klasse tragen logische Bildpunkte, `refresh` legt
sie über `display_to_world` auf eine feste Tiefe — **in Renderer-Elemente
mit fester Kapazität** (fünf Linien- und drei Flächenelemente, NaN-gepolsterte
Segmentpuffer, kollabierte Dreiecke), die je Aufbau nur `set_data` in place
bekommen; neu entstehen sie erst, wenn die Kapazität reißt (Review Ansicht #7:
10 Elemente je Aufbau entfernt und angelegt kosteten 12 der 22 ms je
Kamerageste). `segments` sagt Tests, wo Tinte liegt. Je Aufbau holt sie drei
Weltpunkte und rechnet den Rest affin (`Renderer.display_to_world` sagt das
zu; je Punkt die Kamera zu invertieren kostete 15 ms je Aufbau), das
Geräteverhältnis kommt vom Renderer (`device_ratio`, `ansicht.md`), und
gegen Griff und Knöpfe trägt sie `draw_order` unter null. Die Overlaykarten
tragen weiter Masken — runde Ecken, wenige Rechtecke. Die Aussparung um den Griff
(`clearing`, aus `Viewport.gizmo_reach`) ist seither Kosmetik — die Tinte
ist nicht anklickbar —, und eine Linie, die ganz darin läge, kommt ganz, mit
beiden Pfeilen: Nach dem Zug zum Langloch greift der Griff über Knöpfe und
Umriss hinaus, und ein Maß von 10 mm zur Außenkante hatte sonst ein Feld,
aber keine Linie (Robert, 21.09.2026: „manche maßlinien fehlen aber").
Wer eine Zahl in ein Maßfeld tippt, wird dabei nicht überschrieben: Jeder
Tastendruck geht als Wert in den Entwurf, und die zwei Rückwege — Maßgruppe
und Merkmalfenster — schreiben während des Lesens nichts zurück
(`_place_from_feature_panel`, `reading`; aus „8,00" wurde sonst „8,00,00 mm").
Ein Feld, das der Schritt nie trug und nur seine Vorgabe zeigt (*Langloch* an
einer runden Bohrung), geht nicht in den Auftrag; `request_in_view` nimmt die
scharfe Handlung, wo sie einen Weg ins Bild hat, und ein Druck auf das Loch
zieht das Langloch auch, wenn seine zwei Knöpfe schon stehen.
Eine getippte Koordinate führt die Stelle: innerhalb der Fläche wandern
Maßlinien und Werkzeug mit (`move_to(..., on_plane_only=True)`); eine Zahl
senkrecht dazu verlässt die Fläche, und dann geht die Maßgruppe mit der
Platzierung — die getippten Werte reichen vorher ans Merkmalfenster weiter
(`_hand_quiet_placement_to_panel`), wo die normale Feldvorschau sie annimmt,
als wären sie dort getippt. Ein Klick auf Übernehmen, während das Werkzeug
noch rechnet, wird in der Maßgruppe nicht gemerkt: Der Knopf ist grau, und ein
Übernehmen gilt erst nach dem Bild, das der Kunde gesehen hat.

Die Regeln dieses Gebiets stehen in `.claude/rules/` und laden sich selbst —
**vier Dateien, je nachdem, was man anfasst:**

| Regeldatei | Lädt bei |
|---|---|
| `oberflaeche.md` | jeder Datei hier — Texte, Zahlen, Grenzen, Barrierefreiheit |
| `ansicht.md` | `viewport.py`, `overlay.py`, `cursors.py` und den Leisten |
| `wartezeit.md` | `session.py`, `loading.py`, `leash.py`, `splash.py`, `main_window.py`, `outline_dialog.py`, `step_dialog.py`, `organizer_dialog.py`, `local_recognition.py`, `local_recognition_flow.py`, `print_findings_flow.py` |
| `zeichenflaeche.md` | `sketch_editor.py` |

Hier steht die Karte, dort das Gesetz.

`MainWindow.announce` gibt dieselbe Rückmeldung zusätzlich als passive,
umgebrochene Quittung am Maus- beziehungsweise Tastaturort aus. `_ActionNotice`
verwendet die vorhandene `SketchSelectionBadge`-Darstellung im bestehenden
Overlay. Fortschritt besitzt ihren Text und Zeitgeber nicht; neue Meldungen
ersetzen die alte. Projektwechsel, ausgeblendeter Arbeitsbereich und
Fensterabbau räumen Quittung und Zeitgeber gemeinsam ab. Die Statuszeile
bleibt erhalten, ein zweites Live-Ereignis wird nicht erzeugt.
**Ein Hinweis ist keine Quittung:** `announce(text, receipt=False)` schreibt
nur die Statuszeile, solange der Hinweis gilt, und ein leerer Hinweis stellt
die letzte Quittung wieder her — so laufen die Griffsätze der Ansicht
(`gizmoStatus` → `_on_gizmo_status`), ohne Blase und ohne die Ansage des
letzten Exports samt *Ordner zeigen* zu wischen.

Merkmalsnamen erscheinen bereits beim Überfahren ohne eingeschaltete
Gesamtüberlagerung. `_set_hover_target` und `_redraw_features` entfernen beim
Wegfahren nur den Hovernamen; eine echte Auswahl bleibt beschriftet.
`LabelStyle.always_visible` regelt die Tiefendarstellung, nicht die Auswahl
dauerhaft einzublendender Namen.

Bettbefunde eines unveränderten mehrteiligen Imports bieten gemeinsames
Aufsetzen an. Gruppierung, Beschriftung und Handler verwenden
`ingest.plan.imported_group_for_bed` mit tatsächlichen Szenenkörpern;
verschiedene Imports werden nicht in einer
handlungsfähigen Sammelzeile vermischt. Der Handler prüft den gebundenen
Umfang erneut und schreibt genau einen `place_group_on_bed`-Schritt. Die
spätere Objektauswahl und frühere Szenenobjekte bestimmen diesen Umfang nicht.

`MainWindow._show_start_screen()` schaltet mit der Startfläche auch den
Projektkopf und die Bearbeitungsmenüs aus. Ein geöffnetes oder neu angelegtes
leeres Projekt zeigt sie wieder. Der Rückweg aus einem Editor richtet sich
nach der aktuellen Fläche und blendet den Projektkopf nicht bedingungslos ein.

Bei Texturen bindet „Gesamte Fläche“ die ausgewählte Flächenkennung; nur
wirksame Maße erscheinen. Der Operationsdialog behält denselben Startwert
bis zum Übernehmen. Seine Vorschau reduziert flächengebundene Eingaben nicht,
damit Ränder und Bohrungen dem tatsächlichen Ergebnis entsprechen.

Das Merkmalpanel bearbeitet eine Textur über ihren vorhandenen Verlaufsschritt.
`texture_steps_of` folgt nur ausgeführten Schritten rückwärts zum angezeigten
Körper. Eine belegte `created_by`-Zuordnung öffnet die Felder unmittelbar;
ohne sicheren Flächenbezug ergänzt eine ausdrückliche Texturwahl die normalen
Flächenhandlungen. Zahlenfelder verwenden `ValueField`, damit Maßausdrücke
und ausgeblendete Originalwerte erhalten bleiben. Vorschau und Übernehmen
verwenden denselben Schritt und Startwert; „Weitere Einstellungen …“ führt
in seinen vollständigen Dialog. Der feste Ganzflächenbezug unterdrückt dort
den Bewegungsgriff bis zum Wechsel auf ein Rechteck oder zum Schließen.

Nicht anwendbare Handlungen erscheinen weder im Merkmalpanel noch in dessen
Schnellaktionen und Operationsgruppen. Die Filamentzuweisung bietet
„Entfernen“ nur bei belegter Auswahl. Vorübergehend gesperrte Eingabefelder
behalten ihre Werte und Rückmeldung während einer laufenden Auswertung.

Die Vorschau zeigt den vollständigen Ergebniskörper und die farbigen
Differenzvolumen. Deren `coplanar_overlay` verhindert, dass eine deckungsgleiche
Ergebnisfläche die Änderungsmarkierung verdeckt. Der Rasterversatz erhält
Verdeckung und Weltkoordinaten; Vorschau, Dokument und Export teilen weiter
dieselbe Geometrie. Das gilt auch beim Wechsel eines vorhandenen Musters,
wenn gleichzeitig Material hinzukommt und wegfällt.

## Vorschau und Auswahl

`QuietHost` hält den gemeinsamen Maßentwurf. `feature_field` und
`feature_field_values` verwenden dieselben Felder, Einheiten und
Ausdruckswerte in Panel und Bild. Die Maßgruppe besitzt ihre Editoren;
Panelgegenstücke sind gesperrt und ihr zusätzlicher Abschluss ausgeblendet.
`requires_displayed_preview` ist die Eingabepflicht des Editors, getrennt
vom abgeleiteten `preview_required`. Beide Zwillinge brauchen vor Übernehmen
das dargestellte aktuelle Ergebnis. `accepted(values)` liefert bool;
`finished` folgt erst auf Erfolg. Frühes Enter wird nie nachgeholt.

Ein begonnener Maßentwurf hält seine Auswahl auch gegenüber Berichtsklicks,
direkten Gesteneditoren und lokaler Erkennung. Diese Nutzereinstiege prüfen
`_quiet_command_allowed` vor dem ersten Zustandswechsel. Passive Maße geben
ihren Eingabeweg beim Werkzeugwechsel frei. Dokument-Undo/Redo wartet auf
den Abschluss des Entwurfs; das eigene Undo von Skizze, Formen und Skelett
behält Vorrang. Ein fremder Drehring prüft die Sperre vor `take_values`,
damit eine abgelehnte Handlung nicht schon im Panel aktiv wird.
Die Wiederherstellung einer verworfenen Zeichnung prüft denselben Einstieg,
bevor sie das aufgehobene Exemplar verbraucht.
`ToolStrip.activation_allowed` prüft vor Leistenwechsel und Werkzeugstart;
eine Absage stellt auch die Umschalter auf den bisherigen Zustand zurück.
Trennen nutzt diese Prüfung und prüft beim Übernehmen der Schnittebene
erneut. Beginnt umgekehrt eine Maßbearbeitung, schließt sie ein aktives
Trennwerkzeug; passive Maße lösen diesen Wechsel nicht aus. Rein
betrachtende Werkzeuge bleiben während des Entwurfs verfügbar.

Ungültige Außen- und Mittenabstände erklären sich über denselben sichtbaren
Maßhinweis und sperren beide Abschlüsse sofort (`_invalid_distance`). Die
eingegebene Zahl bleibt korrigierbar; eine gültige Korrektur entfernt den
Hinweis und aktualisiert die Freigabe.

Der Auftrag bindet Dokument, Ergebnis, Körper, Merkmal, Originalschritt und
belegten Gruppenumfang. Das Hauptfenster bereitet Vorschau und Commit aus
dieser Bindung vor, nicht aus inzwischen neu aufgebauten Panelzeilen.
`bore_step_of` und `bore_action` liefern eindeutig belegte ursprüngliche
Bohrungswerte; ihre Vorschau rechnet alle Folgeschritte. Unberührte Ausdrücke
und historische Koordinaten bleiben erhalten. Erkannte Bohrungen ohne
solche Herkunft ändern über `resize_hole` Durchmesser, Lage und Tiefe — die
Tiefe ist ein Feld mit dem gemessenen Wert, leer oder unverändert bleibt sie.
An einer Gruppe reist sie nur, wenn sie am gewählten Loch geändert wurde
(`relations.params_for_members(op=…)`). Beginn, Auswahlbindung und Verwerfen stehen in
Bauplan §18.11 und `.claude/rules/griffe.md`.

Historische Flächenhilfen gehören ausschließlich zur dargestellten
Prefixszene. Über der vollständigen Folgeauswertung bleiben sie ausgeblendet;
Fachwerte und Vorschaufreigabe bestehen weiter. Eine echte neue Eingabe zeigt
den Prefix erneut und entwertet die alte Gesamtvorschau. Geänderte Bohrwerte
lassen den Sitz neu prüfen: Ein früherer Mundpunkt darf nach einer
Tiefenänderung nicht stehen bleiben. Ist kein eindeutiger Sitz belegt,
bleiben die Originalwerte ohne erfundene Flächenhilfen bearbeitbar.

`Session` rechnet historische Werteänderungen und Zwillingswechsel über
dieselben `History`-Methoden wie die Übernahme. Ihre Vorschau enthält auch
die Befunde der neu gerechneten Folgeschritte. Beim Umschalten eines
Erzeugers ergänzt der Vergleich beider Dokumentstände einen tatsächlich
verlorenen exakten Körper; ein Erzeuger selbst hat keinen Eingang, aus dem
der Auswerter diesen Verlust ableiten könnte. Exakte Eingänge werden für
eine schnelle Vorschau nicht durch vorgeschaltete Netzreduktion ersetzt.
Agentenvorschauen verwenden dieselbe `DocumentChange` wie die Annahme:
neue Parameter, Passungen und Druckwerte werden auf der Arbeitskopie
angewandt. Auch ein Vorschlag, der ausschließlich ein vorhandenes Hauptmaß
ändert, erhält eine Vorschau der dadurch veränderten Geometrie.

`labels.exact_conversion_lines()` formuliert die Wirkung vor der Übernahme
gemeinsam für Operationsvorschau und wartenden Agentenvorschlag. Der
Prüfbericht erhält Operation, damaligen Körpernamen, Ausgaben und Rückweg
aus dem Kernbefund. Informationsstufe bedeutet hier keine automatische
Annahme. Beide Körperarten behalten gleichwertige Namen im Objektbaum;
ihre Kurzhilfe erklärt die Darstellung von Rundungen.

`FeaturePanel` und Platzierungsträger trennen `block_apply(reason)` von der
Dokumentsperre: Gesperrt wird nur, was ein Problem hat; **Warten auf die
Vorschau ist keine Sperre.** Ein Klick auf *Übernehmen* vor dem Bild bindet
sich an die erwartete Freigabe (`_PreviewApproval.pending_click`,
`MainWindow._apply_when_previewed`) und läuft in `_preview_rendered`, sobald
das Bild steht und kein Problem dagegen spricht — sonst sagt die Statuszeile
das Problem (Entscheidung Robert, 21.09.2026). Die Frage nach der Freigabe
(`preview_check`) bindet nichts; nur der Klick (`preview_defer` an Dialog,
Panel und `QuietHost`, `then=` an `_preview_can_apply`) tut es.
Ein Wechsel der scharfen Handlung im Panel ist keine Wertänderung
(`handlingArmed`, nicht `valuesChanged`): Das Fenster bindet den Auftrag der
neuen Handlung und lässt die Vorschau der alten fallen, gerechnet wird erst
bei einem echten Wert; und die Maßgruppe im Bild bindet beim Aufbau nur
(`show_values` in `_place_from_feature_panel`), die Uhr stellt der erste Zug
oder die erste Zahl (`host.begun`). Stehen Maße im Bild (`set_measuring`), trägt die
Maßgruppe Übernehmen und Abbrechen, die Knöpfe unten im Panel sind verborgen —
und mit ihnen der Block der Handlung, deren Maße im Bild stehen (Strich und
Zeile je Handlung in `_blocks`; RM-199, Robert: „durchmesser ist ja im
viewport, kann im merkmalpanel entfernt werden"). Die übrigen Handlungen des
Merkmals bleiben, und mit dem Ende des Messens kommt der Block zurück. Im
Zwilling daneben (`LEADS_INTO_THE_VIEW`: *Bohrung ändern* und *Zum Langloch
ziehen*) weichen außerdem die Felder, die die Maßgruppe schon trägt — Breite
oder Durchmesser, X, Y, Z, Materialtoleranz (`FeaturePanel._in_the_view`,
über `_follow_conditions` wie ein Feld mit unerfüllter Bedingung); stehen
bleiben Länge und Richtung beziehungsweise Tiefe und Änderungsumfang.
*Abbrechen* der Maßgruppe verwirft den Entwurf und hebt die Auswahl auf, wie
ein Klick ins Leere (`QuietHost.cancel` → `MainWindow._measures_cancelled`;
Regel in `griffe.md`); Escape tut dasselbe (`_escape`, `PlacementFlow.step_back`).
Ohne Messen steht *Abbrechen* unten, solange eine Feldvorschau aus dem Panel
wartet — ein Merkposten oder eine angeforderte Vorschau, nicht der Auftrag,
den das Anzeigen eines Merkmals ohnehin bindet (`offer_cancel`,
`_offer_feature_cancel`); ein Klick verwirft sie und baut die Felder aus dem
Schritt neu (`_cancel_from_feature_panel`).
Eine Vorschau mit einem `explained`-Satz zum Ergebnis (die Vernetzung eines
exakten Körpers) ist kein Problem und sperrt die Freigabe nicht; ein
erschienener Körper hat keinen Nachherkörper und gilt nicht als unvollständig;
ohne 3D-Ansicht gilt das Ergebnis als gezeigt, sobald es da ist; eine
Vorschau, deren Antwort während der Auswertung verfiel, wird mit der Ruhe der
Session einmal neu angefordert (`_resume_preview_after_idle`); und eine
Bauartänderung ohne bewegtes Dreieck (*Flächenbearbeitung beenden*) ist keine
leere Vorschau — ihr Befund ist die Auskunft, kein Grund
(`Session._preview_outcome`). `can_accept()` wird auch nach Texteingabe und nach den
endgültigen Platzierungswerten geprüft. Ein früher Klick wartet auf das Bild
seiner eigenen Freigabe — nie auf ein älteres: eine geänderte Zahl, ein
geändertes Dokument oder ein Projektwechsel entwerten die Freigabe samt Klick.
Identische Platzierungswerte lösen keine erneute Änderung aus. Die Revision
und der geprüfte Auftrag gehören dem Hauptfenster, die Träger halten keine
zweite Vorschauverwaltung. Auch Chat-Übernehmen und die Rückkehr zu einem
wartenden Vorschlag nach einem anderen Editor verwenden diesen Auftrag.
Konvertierungsbefunde erzwingen die Freigabe selbst dann, wenn der exakte
Körper erst innerhalb des Vorschlags entsteht. Eine feldlose Operation an
exakten Körpern läuft ohne Dialog, wenn sie nicht umwandeln kann
(`_order_may_convert`: Register verlangt ein Netz, oder die Eingänge sind
gemischt) — Regel 19 gilt auch dort.

`seal_dialog.py` sammelt Dichtweg, Trägerfläche, bestätigte Öffnung und optionale
Gegenfläche als einen zusammengehörigen Parameterblock. Der Feldtext zeigt
nur den gewählten Weg; Kontursignaturen sind unsichtbare Daten. Zeichnen
verwendet den bestehenden Skizzeneditor samt `Surroundings`, Öffnungen die
wirklichen Innenringe der ausdrücklich gewählten Fläche. Analyse und
Zeichenpfade entstehen im abbrechbaren Arbeiter. Bild, Liste und Tastatur
markieren dieselbe Kontur; jede neue Anfrage sperrt alte Antworten über ihre
Revision. Der Dialog schreibt keine Operation. Maße und Materialien bleiben
im normalen Operationsdialog, der anschließend dasselbe Ergebnis vorschaut
und übernimmt. `release` hält abgebrochene Arbeiter bis zum sicheren Ende.

`seal_flow.py` bindet diesen Viererblock an den Operationsdialog. Im Verlauf
bereitet ein abbrechbarer Arbeiter die Eingänge vor dem bearbeiteten Schritt
vor; Zeichnungsumgebung und Öffnungswahl lesen denselben festen Stand. Eine
Projektänderung oder das Schließen verwirft späte Antworten. Nur der normale
Operationsdialog schreibt die Transaktion. Inaktive, über `depends_on`
verborgene Maße koppeln sich nicht an eine bestätigte Zeichnung. Die Kopplung
von Länge und Breite gilt für die Grundkontur `sketch`; Führungswege und
Gegenprofile verändern keine Maße ihres Querschnitts.

Freies Zeichnen bewahrt den eindeutig gefundenen Zielkörper vor dem Abbau
des Zeichenpanels. Die anschließende Operationswahl liest `needed_inputs`:
Schnittwerkzeuge erklären einen fehlenden Körper und übernehmen einen bereits
gefundenen Körper in dieselbe Auswahl wie andere Operationswege.
Die Liste bricht Beschreibungen bei Größenänderungen um und scrollt nur senkrecht.
Eine leer abgeschlossene zielgebundene Zeichnung meldet über `announce`, dass
nichts übernommen wurde. Verwerfen und der freie Abschluss behalten ihre
eigenen Rückwege.

**Gezeichnet wird für genau einen Körper** (Robert, 23.09.2026): den
gewählten, ohne Auswahl einen neuen. `MainWindow._resolve_sketch_body` findet
ihn, `_apply_sketch_body` zieht Ansicht (`Viewport.set_sketch_focus`), Leiste
(Feld *Ziel*, *Nachbarn zeigen*, Frage bei mehreren) und Zeichenfläche
(`_sketch_surroundings(only=…)`) nach. Die Regeln dazu stehen in
`.claude/rules/zeichenflaeche.md`, Abschnitt „Ein Körper, ein Ziel".

Ausdrücklich erforderliche Materialrollen beginnen ohne Auswahl und sperren
Übernehmen mit dem jeweiligen Feldtitel. Optionale Materialfelder behalten
„Wie das Projekt“. Eine nur bedingt benötigte Zeichnung startet nicht den
Zeichenmodus vor der Formwahl; der normale Dialog zeigt den aktiven Zweig.

`local_recognition.py` erkundet einen festen Dokument-, Profil- und Quellenstand
im Arbeiter. LOD-Strahlen werden am Original aufgelöst, auch die möglichen
Merkmalhandlungen entstehen dort. Radiuswechsel entwerten Auswahl und Freigabe
sofort; nur die jüngste Generation wird angezeigt. Originaltreffer und beantwortete
Mehrdeutigkeit reisen im Erkennungsauftrag mit. Erkennung und Bearbeitung teilen
Vorschau und Übernahme; `preview_revision` schützt auch die Fehlerfreigabe.
Die Fehlerursache `local_<reason>` bleibt beim Übergang vom Auswertungsbefund
zum Dialog erhalten. Je Grund stehen die Wege, die sein Satz nennt, als Knöpfe
da (`local_recognition._LOCAL_WAYS`, der erste als Hauptknopf): *Andere Stelle
wählen* über `pickRequested`, *Suchradius vergrößern* und *verkleinern* um
`RADIUS_STEP` mit sofortiger neuer Suche (ein Ausdruck im Feld bleibt und
bekommt den Fokus), *Dreiecke verringern* und *Netz reparieren* über
`operationRequested` — der Ablauf schließt die Suche und öffnet die Operation
für genau diesen Körper. Ein Grund ohne Eintrag führt weiter ins Suchradiusfeld.
Die ebene Fläche am Treffer steht immer in der Liste, auch über den
Suchradius hinaus (`_with_the_face_at_the_seed`); jedes andere Merkmal nur, wenn
es ganz im Suchraum liegt. Der Pendelschutz (`local_exhausted`) spricht erst,
wenn Suchrand und Budget höchstens einen `RADIUS_STEP` auseinanderliegen, und
ein Fund setzt ihn zurück. *Alle Merkmale erkennen* hängt am Körper, nicht am
Schritt des Befunds, und steht nur, wo am Ladeschritt eine Wahl steht
(`panels._recognition_reopenable` über `history.recognition_reopenable`);
eine Sammelzeile gibt alle ihre Körper mit (`recognition_objects`), und
`Session.reopen_recognition` tut ohne gespeicherte Wahl nichts, sonst
vergisst es auch den Speichermerker. Nach einem Abbruch während der
bestätigten Vollerkennung — auch unter einer gespeicherten Zustimmung — steht
*Ohne Merkmalserkennung laden* in der Statuszeile
(`Session.load_without_recognition`); ein fertiger Lauf nimmt ihn weg
(`_show_scene`). Die Antwort selbst setzt den Stern im Titel, sobald sie
ankommt (`_record_recognition_answer` sendet `projectChanged`).
Kann die Auswahl nicht beginnen, sagt `LocalRecognitionFlow._refusal` warum:
Rechnung läuft, exakter Körper (Satz aus `labels.kind_requirement`), kein
Treffer — der Einstieg aus dem Bericht kehrte vorher stumm zurück.
Der Großmodellbericht startet denselben Ablauf und bindet die Stellenauswahl
an die Körper seines Befunds. Bei Sammelzeilen bestimmt der Oberflächenklick
einen dieser Körper; eine fremde Baumauswahl bleibt ohne Bedeutung.
Im bereits aktiven Auswahlzustand bietet `Viewport.set_surface_picker` ein
Fadenkreuz mit Pfeiltasten, Umschalt für Feinschritte und Enter zur Auswahl.
Maus und Tastatur führen über denselben Originaltreffer. Abbruch, Dialogöffnung
und Projektwechsel entfernen Fadenkreuz und Tastaturbindung gemeinsam.
`local_recognition_flow.py` hält die Erkundung ausschließlich in der temporären
Ansicht. Erst die Dialogannahme schreibt eine gemeinsame `Session.apply`-Transaktion.
Abbruch und Projektwechsel säubern Vorschau, Auswahlgriff und Rückfragen;
`release()` wartet auf den gesonderten Arbeiterabbau.
Die reine Auswahl verwendet `mark_preview(..., changes=False)`: Der Hinweis
bleibt sichtbar, Änderungslegende und Vorhervergleich erscheinen erst beim Bearbeiten.

Beim Einpassen der Kamera zählt der sichtbare Körperumfang einschließlich
Platten- und Explosionsversatz. Ausgeblendete Körper und andere Einzelplatten
vergrößern diesen Rahmen nicht. Die Geometrie selbst bleibt in ihren Modellkoordinaten.

Skizzenfelder lesen die Pflichtangabe aus ihrem Parameterschema. Eine fehlende
oder nicht lösbare Pflichtzeichnung sperrt Übernehmen und nennt das betroffene
Feld mit seinem Korrekturhinweis. Optionale Zusatzzeichnungen zeigen ihren
eigenen Zweck; sie versprechen keine ersatzweise Grundform. Beim Feldschnitt
sind Bereich und Ausschlüsse getrennte Skizzenwerte. Der Weg aus dem Verlauf
in den Raum führt den Feldnamen mit und kehrt zu demselben Schritt zurück.

`organizer_dialog.py` zeigt den gespeicherten Fachbaum, nummerierte Draufsicht
und tatsächlich berechnetes Ergebnis. `OrganizerLayoutField` trägt den Layouttext
unsichtbar als Daten und zeigt nur Zusammenfassung und Wahlknopf. Ein Arbeiter
löst Maße und Layout auf, baut die Geometrie und projiziert sie; nur dessen
aktuelle Antwort gibt Übernehmen frei. Änderungen während einer Rechnung merken
den letzten Auftrag vor, `release()` verwirft späte Antworten.
`layout_only=True` liefert beim Wiederbearbeiten nur die neue Aufteilung zurück;
die äußeren Maßausdrücke bleiben im Operationsdialog. Ein Bezugwechsel bewahrt
gebundene Außenwerte und nennt Vorher-/Nachhermaße. Im eigenständigen Dialog
übernehmen ungebundene Zahlen die gerade sichtbare Größe. Einzelne Wandhöhen
gelten für die geklickte Instanz; eine Fachvorlage nennt ausdrücklich, wie viele
Fächer ihre Maße gemeinsam verwenden.
Eine Wandwahl löscht die vorherige Baumzeile als Auswahl. Draufsicht und
Ergebnisprojektion zeigen dieselbe Auswahl mit Kontur und Text. Die Ergebnisfarbe
folgt nur den geometrisch belegten Dreiecken des fertigen Körpers und bleibt in
der Tiefensortierung. Ein Auswahlwechsel verwendet das vorhandene Mesh erneut;
nur die Projektion läuft neu im Arbeiter.

`outline_dialog.py` zeigt SVG-/DXF-Profile als nummerierte Zeichnung und
Checkboxliste neben ihrer berechneten Extrusion. Innenringe bleiben am Profil;
nicht extrudierbare Profile bleiben mit Begründung sichtbar. Einlesen,
Profilprüfung, Zeichenpfade und Ergebnisprojektion laufen im Arbeiter.
`values()` liefert ausschließlich `load_outline`-Werte: Konturkennungen als
JSON-Liste, Höhe und Zielbreite. Erst eine zur aktuellen Auswahl passende
Vorschau gibt Übernehmen frei. Je Dialog rechnet höchstens ein Arbeiter;
Änderungen merken nur den letzten Auftrag vor. `release()` verwirft späte
Antworten und wartet über die gemeinsame Leine auf das Threadende.

`ContourField` zeigt Anzahl und Wahlknopf statt des gespeicherten JSON-Texts.
Das Schema nennt dafür `kind="contours"`; `OperationDialog` liest `value()`
und verbindet Änderungs- und Gültigkeitssignal wie bei den anderen Wählern.
Beim erneuten Wählen sperrt `OutlineDialog(selection_only=True)` seine Maße:
Nur die Konturauswahl fließt zurück, bestehende Maßausdrücke bleiben erhalten.
In der Konturliste stehen Haken und ausdrücklicher Status neben dem Bild;
der Zeilenfokus übermalt den Haken nicht. Nebenknöpfe erhalten keinen
automatischen Default, der feste Hauptknopf bleibt `make_primary`.

`step_dialog.py` ist die Importauswahl einer STEP-Baugruppe (P7.4): jeder
Körper als Zeile mit Haken, Namen, Maßen, Farbfeld und der Farbe als Wort im
Tooltip (Regel 18), daneben die Lage des betrachteten Körpers in der
Baugruppe. Die Vorschau zeichnet **Hüllquader** aus den Maßen der Auswahl im
Arbeiter — die echte Vernetzung kostete an 200 Teilen 5,9 s und das Bild 3,6 s.
`Session.choose_step_bodies` hält eine Baugruppe mit mehr als einem Körper vor
ihrem ersten Schritt an (`stepImportRequested`), `finish_step_import` übernimmt
die Wahl genau einmal oder verwirft die eingebettete Quelle. Ohne Plan (aus
„Diesen Schritt ändern“) liest der Dialog die Datei selbst im Arbeiter.
`StepBodiesField` erbt vom `ContourField`, damit der Operationsdialog Wert,
Gültigkeit und Signale an derselben Art abfragt; der leere Wert ist der Stand
vor P7.4, die ganze Datei als ein Körper.

Das Hauptfenster schaltet `Session.choose_outline` für seine asynchronen
Importwege ein. `outlineImportRequested` hält vor dem ersten Schritt an;
`finish_outline_import` prüft die Projektgeneration und übernimmt die Antwort
genau einmal. Abbrechen räumt die eingebettete Quelle auf. Menü, Dateidialog,
Drag-and-drop und Download teilen diesen Weg. Der synchrone Sitzungsimport
behält seinen ausdrücklichen Auftrag ohne interaktive Zwischenwahl.

`OrganizerLayoutField` öffnet über das Hauptfenster den `OrganizerDialog`.
Der Facheditor erhält aufgelöste Außenmaße und die Projektparameter; nur sein
Layoutwert fließt in den übergeordneten Operationsdialog zurück. Dessen
Maßausdrücke bleiben erhalten. Abbrechen, Projektwechsel und Fensterabbau
verwerfen späte Antworten. Der Layoutwert wird erst durch `create_organizer`
im Operationsstapel zu Dokumentgeometrie.

Die Parameterleiste liest Verwendungsdaten aus dem aktuellen
`EvaluationResult`, ohne Skizzen im Qt-Hauptthread zu parsen. Ungenutzte Maße
tragen einen sichtbaren Text und erklären den Ausdruck im Operationsfeld.
Benutzte Maße nennen ihre lesenden Schritte. Während der Auswertung und bei
einer unklaren Abfrage bleibt die Aussage unbekannt; alte Ergebnisse dürfen
keinen gerade geänderten Parameter als ungenutzt bezeichnen.

Die geometrische Vorschau zeigt den vollständigen Nachherkörper aus
`Difference.result`. Hinzugefügtes und entferntes Material erklärt die
Änderung zusätzlich; eine gescheiterte Differenzrechnung darf das vorhandene
Ergebnis nicht verbergen. Neu vernetzte Vorschaukörper liefern beim Picking
keine Dreiecksnummer aus dem Originalnetz.

Große Vorschaukörper und alle Ansichtsschnitte werden gemeinsam durch den
Ansichtsarbeiter auf eigenen Netzkopien vorbereitet. Währenddessen zeigt das
Band ausdrücklich das Vorhermodell an; erst die fertige aktuelle Generation
ersetzt Geometrie, Konturen und Etiketten. Abbruch und Fensterabbau verwerfen
auch bereits eingereihte Antworten. Dezimierte Netze bleiben ausschließlich
in der Ansicht und werden beim Vorhervergleich wiederverwendet.

Merkmalskontur und Etikett lesen den gerade gezeigten Körper. Entfernte
Kettenglieder erhalten keine alte Markierung über dem neuen Ergebnis.
Bohrung, Senkung und belegte tangentiale Eintrittsflächen teilen eine Kontur;
deren Tiefenversatz kommt in Bildpunkten aus dem Renderer. Beim
Vorher-Vergleich kehren Geometrie, Maße und Markierung gemeinsam zurück.

Der Objektbaum und die Auswahlüberschrift nennen bei der Hauptbohrung schon
die belegten Stufen, Senkungen und Verengungen (`labels.cavity_name`). Ein
Kegel, der die Mündung verengt (`narrowing`, die Haltelippe einer
Magnettasche), heißt Verengung, und die Maßspalte nennt die Weite, die er
lässt (`opening`) — nicht das weite Ende an der Tasche. Untergeordnete
Abschnitte behalten ihre eigenen Namen und Kennungen. Dieselbe Kettenauskunft
steuert Gruppierung, Beschriftung und Auswahl; ein Verwendungszweck wie
„Magnettasche“ wird aus einer bloßen Sackbohrung nicht abgeleitet.
Ein belegtes `through=False` heißt bereits im Baum und am Merkmal
„Sackbohrung“; ohne diesen Nachweis bleibt die neutrale Bezeichnung „Bohrung“.

`Session._preview_outcome` trägt Befunde ausschließlich der vorgeschauten
Schritte in `SceneDifference.findings`. Warnungen bleiben neben einer
erfolgreichen Ergebnisvorschau sichtbar. Der getrennte Absageweg bleibt
Vorschauen vorbehalten, die tatsächlich kein Ergebnis liefern.

## Filamente und lokales Lager

`FirstRunDialog` fragt Slicer vor Drucker; `_PrinterSurvey` liest passende
Profile außerhalb des Qt-Hauptthreads und verwirft Antworten früherer Auswahlen.
„Benutzerdefiniert“ sammelt Name, Verfahren, Bauraum und die Maße des
Verfahrens direkt im Formular — Düse und Düsenzahl bei FDM, Pixelgröße und
Mindestwand bei Resin (`_technology_changed` blendet die fremden Zeilen
aus). Die Druckerliste ist nach Verfahren gruppiert (`_group_printers`:
nicht wählbare Köpfe, nur wenn beide Gruppen da sind); die Resin-Geräte
hängen an keinem FDM-Slicer und bleiben stehen, wenn ein Slicer die Liste
filtert, und ein Programm ohne Familie bekommt den Satz, dass Solidon seine
Drucker nicht kennt. Das Vorgabematerial folgt dem Drucker
(`profiles.material_for`).
`custom_printer_draft` und `restore_custom_printer_draft` erhalten ungespeicherte
Eingaben beim Sprachwechsel. `inventoryRequested` öffnet nach Übernahme der
Einrichtung das Filamentlager über das Hauptfenster.

Löschen entfernt eine Spule über `filaments.archive(identifier)` aus dem aktiven
Lager. Rechtsklick und sichtbarer Mülleimerknopf verwenden denselben Weg;
„Archivierte Spulen anzeigen“ und „Wiederherstellen“ bewahren den Rückweg samt
Kennung und Buchungsverlauf. Ein Rechtsklick nimmt die angeklickte Spule als
Ziel, unabhängig von einer vorherigen Auswahl. Plus- und Mülleimersymbole
kommen als themenabhängige SVGs aus `icons.py`.

`InventoryView` reiht bestätigte Lagerhandlungen geordnet ein; Rückmeldungen
gelten nur ihrem aktiven Arbeiter. Abgebrochene Suchen bleiben bis zum Threadende
gehalten und dürfen spätere Aufträge nicht verändern.
Der Abbrechen-Knopf einer Lagersuche setzt denselben `CancelSignal`, den die
Profil-Dateisuche und Vererbung prüfen. Er beendet die Suche kooperativ;
gespeicherte Lagerhandlungen werden weiterhin vollständig ausgeführt.
Die Rücknahmeausnahme bei jüngerer Bestandsfeststellung bleibt an Spule und
Vorgang gebunden. Ein Wechsel von Detail, Regal, Filter oder Journalauswahl
verwirft das Angebot; verspätete Konflikte öffnen es nicht in einer anderen
Ansicht — **gezeigt wird die Absage trotzdem**, mit dem Namen der Spule
davor, denn ein Klick, der nichts bewirkte, darf nicht stumm bleiben.
Eingereihte Rücknahmen bewahren ihren ursprünglichen Zielkontext. Der
Rücknahmeknopf hat zwei Richtungen: auf einem zurückgenommenen Vorgang heißt
er „Rücknahme rückgängig machen" und ruft `restore_booking` — deshalb
braucht die Rücknahme keine Nachfrage (Regel 19). Im Detail verschwinden
„Lager verlassen" und „Spule von Hand anlegen" aus dem Kopf; Esc geht
denselben Weg wie der jeweilige Zurück-Knopf (`_escape`). Die Detailseite
nennt Restmenge, Kauf- und Öffnungsdatum und Preis als Fakten
(`calendar_day` für gespeicherte ISO-Tage). Ohne eine einzige Spule stehen
Satz und beide Wege mittig (`empty_panel`), Suche, Gruppierung und der
Importknopf unten sind ausgeblendet; eine Suche ohne Treffer behält die
Suchleiste. Die Zusammenfassung zählt Archivierte getrennt.

Weist der Kern eine Spule aus dem Dialog an einem Feld ab, öffnet
`InventoryView._rejected` den Dialog mit derselben Eingabe erneut
(`retry_entry` an `_run`, `NewFilamentDialog.focus_field`) — Name, Lagerort
und Bestand gehen mit der Abweisung nicht verloren; Konflikte und die
unlesbare Datei sind davon ausgenommen. Datumsfelder sind `DateField`
(`labels.py`): Kalender in der Anzeigesprache, „Unbekannt" als eigener Wert,
lostippen ab „Unbekannt" mit oder ohne Trennzeichen, gespeichert ISO.
Sichtbare Spulenzeilen tragen die achtstellige Kennung nur, wo zwei sonst
gleich hießen (`spool_labels`); Kurzhilfe und zugängliche Beschreibung
tragen sie immer (`spool_label`). Der Spulenname auf der Karte bekommt zwei
Zeilen, bevor er in der Mitte gekürzt wird (`name_lines`); die Schraffur
des Wickels heißt „Bestand unbekannt" und nichts anderes (`coil_fill`).

`FilamentField` und `FilamentPanel` schreiben über `CatalogueWrites` außerhalb
des Qt-Hauptthreads. Die Steuerung gehört dem obersten Fenster und hält
bestätigte Aufträge über verworfene Kinddialoge hinaus. Erst die erfolgreiche
Speicherung aktualisiert die Auswahl; `MainWindow.wait_for_workers` wartet
die Aufträge vor dem Schließen ab. Operationsdialoge berücksichtigen den
`pending`-Zustand des Filamentfelds auch bei direktem `accept()`.

Lesefehler im Lager bewahren die letzte gültige Ansicht und zeigen den
fachlichen Sicherungs- oder Wiederholungsweg — als Knöpfe
(`_read_handlers` in `InventoryView` und `FilamentPanel`: `restore_backup`,
`set_aside_file`, `retry`), nicht als Rat. Unerwartete Ausnahmen werden protokolliert und als interner Fehler
kenntlich gemacht. `problem_text` setzt Titel und Detail in zwei Zeilen und
`spoken_values` lässt `field` und `constraint` weg: Das sind Adressen für
den Code, keine Angaben für den Kunden.
`ErrorNotice` bewahrt Angaben und Vorschläge auch in eingebetteten Anzeigen.
Nur örtlich verdrahtete Wiederholungs- oder Korrekturhandlungen verändern das
Lager oder die Auswahl; bestätigte Schreibaufträge behalten ihre ursprünglichen
Daten. Neue Zustände sperren und entfernen alte Fehlerknöpfe. Während einer
laufenden Buchung bleiben ihre Folgeaktionen gesperrt und ihr Hinweis lesbar.
Lagerleser verwenden die gemeinsame nach Dateistempel erneuerte Momentaufnahme;
Lesefehler bleiben auch in Vorwahl, Filamentpanel und Startkachel sichtbar.
Ein Lesefehler aus dem **Aufbau** des Filamentfelds erreicht seine Empfänger
erst beim Anzeigen (`FilamentField.showEvent`): `_fill` läuft im Konstruktor,
und der Operationsdialog verbindet `choiceNotice` und `choiceProblem` danach.
Die Startkachel zeigt dafür einen kurzen Satz und trägt Ursache und
Sicherungsweg in Kurzhilfe und Beschreibung; der ganze Fehler passt nicht auf
eine Kachel.
Spulendetail und Buchungsvorschlag verbinden Spulen und Journal aus jeweils
genau einem vollständigen Stand.

`filament_inventory.py` zeigt und verwaltet Spulen ohne Renderer; `filament_picker.py`
enthält den gemeinsamen Spulendialog und die Übernahme konfigurierter Slicerfilamente.
Den Profilbestand des Slicers für *Slicer-Profil → Wählen …* liest
`_SlicerFilamentSearch` im Arbeiter, mit Balken und *Abbrechen* im Dialog —
gemessen 4 bis 27 s an 5962 Profilen; `wait_for_profiles` stellt die Antwort in
Tests zu.
`filament_assignment.py` zeigt die Schnellauswahl. Beide Auswahlwege melden
`spoolChosen`, ohne lokale Kennungen in Geometrieparameter zu schreiben.
`main_window.py` führt die Zuweisungsoperationen aus und speichert die Bindung
getrennt in den Druckeinstellungen. Ein Katalogwechsel aktualisiert Wahlangebote,
nicht die eingebetteten Filamente einer geöffneten Szene.
Die Bestätigung prüft die angezeigte Druckidentität erneut gegen das Lager;
eine reine Bestandsänderung bleibt zulässig. Bei geänderten oder archivierten
Spulen zeigt die Auswahl einen bleibenden Hinweis und lädt ihre Angebote neu.
`spoolChosen(None)` verwirft eine vorgemerkte Lagerbindung. Von Hand veränderte
Filamentangaben werden nur als ausdrücklich ungebundene Projektwerte übernommen.
Schnellauswahl und Projektübersicht lesen tatsächlich verwendete Mesh-Slots;
verwaiste Definitionen werden nicht als belegte Filamente dargestellt.
Die Schnellauswahl teilt eine Sloterhebung je ganz gewähltem Körper zwischen
Beschriftung und Entfernen-Knopf.
Der Objektbaum erhebt die Belegung einmal je Körperaufbau. Seine Flächenzeilen
lesen nur die Dreiecke des jeweiligen Merkmals und zeigen dafür Farbe, Namen
und zugängliche Beschreibung aus derselben Slotdefinition.
Eine gemischte Auswahl benennt ganze Körper und einzelne Flächen getrennt.
„Filament entfernen“ benutzt denselben Umfang. Die ausgewählten Körper und
Flächen werden als `clear_filament`-Operationen in einer Transaktion abgelegt;
Strg+Z nimmt den gesamten Zug zurück. Neutrale Flächen bieten keine Abwahl an.
Der gemeinsame Editor für `kind="features"` zeigt eine Checkliste und eine
ausdrückliche Ganzkörperwahl. Alte Einzelwerte werden übernommen; ein leerer
Zwischenzustand sperrt Anwenden und vergrößert keine laufende Vorschau.
Die Hauptaktionen der Auswahl wechseln bei schmaler Spalte in eine Spalte,
statt die Karte horizontal aufzuweiten. Journalzeiten werden mit
`labels.local_timestamp` im lokalen Gebietsschema dargestellt.
Die Filamentübersicht lässt Qt das Beiwerk ihrer Liste bei der tatsächlichen
Breite messen (`totalHeightForWidth`). Wunsch, Mindesthöhe und Zuteilung
enthalten denselben umbrochenen Hinweis und nur sichtbare Bedienelemente.
Breite, Schrift, Stil und Sichtbarkeit erneuern diesen Höhenvertrag.

Filament-, Slicerprofil- und Körperwahldialoge werden nach jeder modalen
Antwort im `finally` zur Löschung vorgemerkt. Nur kopierte Fachdaten reisen
in nachfolgende Lagerarbeiter; der offene Besitzer hält keine beendeten Dialoge.

Spulenkarten zeichnen die Restmenge zusätzlich zur Farbe als Zahl und
Füllstand; unbekannter und archivierter Bestand tragen sichtbare Texte.
Die Lagerzusammenfassung unterscheidet Leerzustand, eine Spule und mehrere Spulen.
Nennfüllung, Restmenge und Lagerort stehen im Spulendialog vorn. Kurze
Kennungen unterscheiden gleiche Etiketten; Details und zugängliche
Beschreibungen bewahren die Kennung unabhängig von dieser Verkürzung.

`filament_usage.py` hält Angebote erfolgreicher Ausgaben ohne Zeitlimit bereit.
`slot_title` benennt das Druckfilament auch ohne eigenen Namen; Buchungsdialog
und Bestandsbedarf im Druckdialog verwenden dieselbe Beschriftung.
Beim Anlegen einer Spule im Buchungsdialog bleiben gewählte Spulen, manuelle
Mengen und Aufteilungen erhalten. Die neue Spule füllt höchstens eine noch
freie Hauptposition und bleibt in allen passenden Auswahllisten erreichbar.
Ein Dialogwechsel übernimmt sie mit `auto_book=False`, damit der Transfer keinen
neuen Buchungsanlass schafft. Lagerzugriff und atomare Journaländerungen laufen
über Arbeiter; Aufteilung, Wiederholungsdruck und manuelle Korrektur sind
ausdrückliche Handlungen. Jede Menge nennt ihre Herkunft, jeder belegbare Preis
die gespeicherte Währung. Druckvorbereitung und Bestandswarnung bleiben getrennt
von der Buchung. Die Einstellung liegt lokal, die Vorbereitungskennung im Projekt.
Die erste automatische Buchung benutzt eine aus dem Fingerabdruck abgeleitete
Vorgangskennung, damit gleichzeitige Zustellungen denselben Abzug treffen.
Beim Schließen zählen laufende und eingereihte Lagerhandlungen mit.
Wartet der Druckdialog beim Schließen auf Arbeiter, sperrt er nur die
Eingaben und Handlungen. Zustandszeile und Fortschritt behalten ihre normale
Darstellung, bis der letzte Arbeiter beendet ist.
Nichtbuchung wird nur am Knopf „Nicht buchen“ gemerkt: Die Ausgabe bleibt
mit „Nicht gebucht — ansehen …“ erreichbar und wird bei erneutem Angebot
nicht automatisch gebucht. Eine spätere ausdrückliche Buchung ersetzt diesen
Zustand; Escape und Fensterschließen treffen keine neue Entscheidung.
Der Buchungsstatus folgt dem ausgewählten Ausgabe-Fingerabdruck. Manuelle
Korrekturen übergeben den gelesenen Vorgangsstand, damit ein älterer Dialog
keine jüngere Aufteilung überschreibt. Der Auswahl-Export ordnet gespeicherte
Herstellerprofile anhand der Druckfilamentidentität seiner tatsächlichen
Teilmenge zu; deren neue Werkzeugnummern sind kein Index in die Gesamtszene.
Die Sitzung bindet alte positionsgebundene Herstellerprofile an der letzten
vollständigen Szene. Der Druckdialog schreibt neue Wahlen nach dieser
Identität und erhält sie beim Qualitätswechsel. Die Umstellung der Darstellung
ändert keine Druckwerte; Undo und Redo finden weiterhin dieselben Filamente.
Ein nicht verfügbares gebundenes Profil bleibt mit Originalnamen als ungelöst
sichtbar. Befüllen der Liste wählt kein anderes Profil. Ein ausdrücklich
geändertes Herstellerprofil erhält die gewählte physische Spule; automatische
Buchung prüft deren Eignung weiterhin gesondert.
Für die ausdrückliche Wertübernahme hält der Druckdialog das gewählte
`SlicerProfile` einschließlich seines Prusa-Abschnitts fest. Der Dateipfad
allein beschreibt bei Herstellerbündeln noch kein bestimmtes Filament.

Der Dialog erscheint, bevor jemand nach Slicern gesucht hat: `_SlicerWorker`
fragt `discover.find_programs` außerhalb des Qt-Hauptthreads, vorläufig gilt
der gemerkte Pfad (`_remembered_slicer`), und `_slicers_found` übernimmt Liste
und Wahl. `recheck_slicer` benutzt denselben Arbeiter; `wait_for_slicers()` ist
der Weg, auf seine Antwort zu warten. Das Schließen wartet nicht auf sie
(`_settle` lässt `_SlicerWorker` aus); den Thread hält die Leine, `release`
wartet beim Abbau auf ihn, und `MainWindow.wait_for_workers` fragt über
`leash.wait_for_all` auch nach dem, was ein weggeräumter Dialog hinterließ.
Regel und Messung in `.claude/rules/wartezeit.md`.

## Der Weg durch die Schicht

```
main_window.py   Menüs, Auswahl, Zustand
      │  ruft eine Operation auf
      ▼
session.py       die Brücke zum Kern: Stapel, Auswertung, Threads
      │  wertet aus (im Arbeiter-Thread)
      ▼
app.core         rechnet
      │  EvaluationResult
      ▼
viewport.py      zeigt an
```

`session.py` ist die einzige Stelle, an der die Oberfläche den Kern anfasst.
Wer an ihr vorbei rechnet, bricht Regel 2.

## Die fünf Dinge, die an `session.py` überraschen

Ende zu Ende gemessen am 27.08.2026 — vier Anläufe gingen daran verloren,
bevor es jemand wusste:

- **`session.last_result` ist die ausgewertete Szene.** Ein
  `session.scene` gibt es nicht.
- **`evaluate_now()` ist der synchrone Weg** — für Kommandozeile, Tests und
  Export. Er gibt das Ergebnis zurück, statt es nur anzustoßen.
- **`session.apply()` endet mit `evaluate_async()`.** Nach dem Aufruf steht
  das Ergebnis noch **nicht**. Und es wirft nicht: Fehler kommen über das
  Signal `failed`. Ein `try` um den Aufruf läuft ins Leere — nach dem
  Ergebnis fragen, nicht nach dem Grund. Dasselbe gilt für
  `create_counterpart` und `create_thread_counterpart`: Die Schritte stehen
  sofort, die Passung kommt mit der Auswertung (`_finish_after`,
  `_run_finishers`) und meldet sich über `counterpartFinished`; ein
  Projektwechsel dazwischen lässt den Abschluss verfallen. Abgeschlossen wird
  nur mit einem **aktuellen** Ergebnis (`result_current`) — eines mit
  eingereihtem Nachlauf gehört zum Stand vor dem Einsetzen.
- **Vorschau und Agentenzug rechnen auf einem `_Snapshot`**, gezogen im
  Hauptfaden (`preview_async`, `propose_async`): Dokumentkopie, Szene davor,
  Profil. Der Arbeiter kopiert nur diesen Stand, nie das lebende Dokument.
  `project_generation` nennt das offene Dokument als Zähler — Zahlenzeile und
  lokale Erkennung erkennen daran einen Dokumentwechsel.
- **Der Auswertungsarbeiter fasst die Kennzahlen an** (`_warm_metrics`):
  Volumen, Oberfläche, Wasserdichtheit und Teilezahl jedes Körpers sind
  danach gemerkt, und `describe_selection`, `_measure_up` und `_update_facts`
  lesen im Hauptthread nur noch. Dazu die Hohlraumketten des Objektbaums
  (`relations.cavity_chains`): `show_scene` fragt sie je Körper, die Antwort
  liegt im Cache des Netzes — der erste Aufruf kam aus dem Hauptthread und
  kostete an einer Platte mit 204 000 Dreiecken 414 ms je Szenenaufbau.
- **Die Live-Vorschau des Dialogs erkennt keine Merkmale** (`preview_async`
  → `_preview_outcome(detect_features=False)`): Sie zeigt Geometrie und
  Differenz, und die Erkennung am geänderten Körper kostete je getippter Zahl
  an 204 000 Dreiecken 1,1 der 2,2 Sekunden. Der Agentenweg (`preview_scene`)
  erkennt weiter — sein Steckbrief liest die Merkmale. Und die grobe Stufe
  greift auch beim Ändern eines Schritts (`_coarse_steps_before`, Regel in
  `wartezeit.md`): 40 ms je getippter Zahl ab der zweiten.
- **Die Modellfrage läuft im Arbeiter** (`_BackendProbe` im Fenster): Bis
  `backend_known` steht, sagt der Chat „Sprachmodell wird gesucht …";
  `set_agent_backend` beantwortet sie, auch mit „keins".
- **Und hinter einen Halt nimmt es keinen Schritt an.** Solange
  `last_result.stopped_at` steht, schreibt `apply` mit Entwürfen nichts und
  meldet über `failed` die Absage aus `halt_in_the_way` — mit den Handlungen
  des Halts; `halted_step()` nennt Kennung und Titel des Schritts. Ein Test,
  der nach einem Halt weiterbauen will, löst ihn erst (Undo, `change_params`,
  `recount_and_retry`). Die Regel steht in `oberflaeche.md`.
- **Mit Einfügemarke ist `last_result` der Stand davor.** Solange
  `Session.inserting` steht, wertet die Sitzung `displayed_document()` aus —
  die Schritte vor der Marke, ohne Passungen —, und `apply` fügt dort ein
  (`_insert`, isoliert gerechnet im `_RevisionWorker`). Wer das fertige Teil
  braucht, beendet das Einfügen zuerst (`stop_inserting`, dann
  `wait_for_idle`), wie Export und Druckeinstellungen es tun.
- **`Scene.objects` ist ein Wörterbuch.** Darüber zu iterieren gibt die
  Kennungen. Die Folgemeldung `'str' object has no attribute 'mesh'` sieht
  aus wie ein leerer Import und ist keiner.

- **Das Fenster liest über `import_model_async`, nicht über `import_model`.**
  Der synchrone Weg steht daneben und bleibt — Kommandozeile und Tests
  brauchen einen, der wirft. Das Fenster braucht einen, der meldet: Bei einer
  3MF zählt `import_plan` die ganze Baugruppe, bevor eine Operation entsteht,
  und das dauert bei 63 MB vierzehn Sekunden. Eine Datei vom Pfad liest
  `_ReadWorker`, geplant wird danach immer im Arbeiter (RM-224); für eine
  Nutzlast ohne Pfad gilt `PLAN_IN_WORKER_ABOVE`. Der Fehler kommt über
  `importFailed`, **ein Test wartet also mit `wait_for_idle`**, bevor er nach
  dem Öffnen etwas prüft. Wer in einem Test `session.import_model` patcht,
  patcht damit einen Weg, den das Fenster nicht mehr geht — fünf Tests in
  `test_ui.py` hingen daran (03.09.2026).

**Und oberhalb von 150 000 Dreiecken rechnet sie grob.** `Session._preview_outcome`
legt dann eine `decimate_mesh`-Operation auf dieselbe Zahl vor die
Entwurfsschritte — auf dem Anzeigeweg (`method="fast"`, `_coarse_params`), in
der Dokumentkopie, die die Vorschau ohnehin anlegt, und für beide Seiten der
Differenz dieselbe (`_coarse_before`). `_coarse_before` rechnet **zuerst** und
unter eigenem Signal (`_coarse_cancel`, Sperre `_coarse_lock`) und merkt die
grobe Szene je Szene und Schritt: Eine abgelöste Vorschau verliert die
Verkleinerung nicht mehr. `supersede_preview` löst eine Vorschau ab und lässt
die Vorbereitung laufen, `cancel_preview` hält beides an. Gibt der Kern am
groben Netz auf (`_kernel_gave_up`), rechnet sie genau. Der Weg meldet sich
über `_PreviewWorker.coarse` ans Fenster (`MainWindow._preview_coarse`), und
das Band sagt „Grobe Vorschau". Schranke, Ziel, Messreihen und die zwei Wege,
die absichtlich genau bleiben, stehen in `.claude/rules/wartezeit.md`.

**Und über zwei Sekunden mit Balken und *Abbrechen*.** `preview_async(progressed=…)`
meldet über `_PreviewWorker.progressed` Anteil und Schritt der Auswertung; das
Fenster führt dafür den Fortschrittsbesitzer `"preview"`
(`_start_preview_progress`, `_preview_progressed`, `_finish_preview_progress`),
und *Abbrechen* geht an `MainWindow._cancel_preview_run`: Rechnung angehalten,
Vorschaukörper weg, Band „Vorschau abgebrochen — …", Dialog offen.

  Einleseplan und Auswertung teilen sich `busy` und `busyChanged`. Erst die
  zugestellten Endsignale beider Arbeiter beenden den Fortschritt; weder die
  leere Startauswertung noch ein Importfehler dürfen den noch laufenden
  anderen Arbeiter ausblenden. So bleibt auch Abbrechen bis zum Ende erreichbar.

## Die Karte

Zwei benannte Merkmale verschiedener Körper werden im Objektbaum gemeinsam
gewählt. Das Merkmalpanel zeigt beide Körper und Merkmale, die vom Kern
geeigneten Passungsarten und deren materialfolgendes Sollmaß. Erst
„Passung anlegen“ ruft einmal `Session.add_fit` auf; ein Undo entfernt die
Beziehung. Vor dem Schreiben werden Projekt, Ergebnisstand, Auswahl und
Eignung erneut geprüft. Bestehende ungeordnete Paare werden angezeigt statt
doppelt angelegt. Rohrmaße liest das Panel aus `relations.sleeve_at`; es
speichert dafür keine zusätzliche Beziehung. Nach einem Baumneuaufbau werden
Auswahl, Tastaturzeile und Sichtbarkeit anhand der heutigen Kennungen
wiederhergestellt; ein verzögerter Scroll-Aufruf hält keine alten Baumzeiger.

**Rahmen und Einstieg**

`app.py` (Einstiegspunkt, §38) · `qt_platform.py` (welche Qt-Plattform die
3D-Ansicht braucht — entschieden vor der `QGuiApplication`, ohne Qt-Import;
Qt 6 nähme in einer Wayland-Sitzung sonst Wayland, und der wgpu-Fensterweg ist
nur unter X11 und Xwayland geprüft — nativer Wayland-Betrieb von rendercanvas
ist ein offener Punkt) · `main_window.py` (das Hauptfenster, §2.5 — die
größte Datei des Gebiets; eine Zeilenzahl stand hier und alterte) · `splash.py` · `first_run.py` (der erste Start) ·
`start_screen.py` (die ersten fünf Minuten, §2.3) · `header.py` (Projektname,
Druckerwechsel und die tatsächlich in der Szene verwendeten Filamente)

Der Modul- und der Paketstart in `app.py` richten den gemeinsamen lokalen
Absturzschutz vor dem ersten Qt-Import ein. Ein bloßer Import installiert
keine Prozesshooks; der programmatische `main()`-Aufruf ergänzt denselben
idempotenten Start. Qt-Arbeiter behalten ihren vorhandenen Fehlerweg, ohne
einen zweiten Bericht über den Prozessschutz auszulösen.

Der Supportdialog hält normale Protokollzeilen und vorhandene Absturzstapel
als gemeinsamen Schnappschuss aus `report.diagnostic_attachments()` fest.
Vorschau, Versand und Ablage benutzen genau diese Bytes, auch nach Abwahl
und erneutem Anhaken und auch bei anfangs leeren Dateien. Der Nutzer sieht
die Anhänge vor dem Senden; ein Absturz löst keinen Versand aus.

**Brücke zum Kern**

`session.py` (§7, §15.6) · `leash.py` (die Halteleine für Arbeiter-Threads — und für Ereignisfilter,
die ihr überwachtes Objekt überleben: `stop_watching_the_dying`)

**Ansicht**

`viewport.py` (§18, §2.9) · `render/` (der Renderer
hinter der Ansicht, eigene `CLAUDE.md`: der Vertrag `api.py`, pygfx über wgpu
in `gfx_renderer.py`, gebaut über `factory.py`, Kameraführung, Formen,
Bewegungsgriff) · `overlay.py` (Zonen über der
Ansicht statt neben ihr; dazu die Regel, dass nur ihre direkten Kinder und die
der Ansicht ein eigenes natives Fenster bekommen — `keep_widgets_alien`,
`hold_above_the_view`, Regel in `ansicht.md`) · `loading.py` (Ladeanzeige,
§2.8) · `cursors.py` · `app_events.py` (der eine Filter an der Anwendung:
Mauszeiger, Fensterchrom, Navigationstasten, Nutzungsuhr, Dateiempfang und
der Vorher-Vergleich melden dort ihre Ereignisarten an, statt je einen
eigenen Filter zu hängen — Regel in `wartezeit.md`) ·
`placement_flow.py` (Oberflächenplatzierung aus dem Operationsdialog, §18.5) ·
`spacemouse.py` (die 3D-Maus als zweite Hand an derselben Kamera: HID-Leser
über hidapi, auf dem Mac der Treiberweg über das 3Dconnexion-Framework des
Kunden, die Abbildung als reine Funktion — Regel in `ansicht.md`).
Ein gefundenes, aber nicht zugängliches Gerät zählt als gesehen. Der Leser
unterscheidet die Zugriffssperre von einer leeren oder gescheiterten Suche;
der Controller meldet sie einmal je Sitzung und sucht weiter. Das Fenster
zeigt dazu einen Hilfezugang in der Statusleiste. Die kopierte Linux-Regel
begrenzt `uaccess` auf die erkannte USB-Hersteller-/Produktkennung; weder
globale Schreibrechte noch eine automatische Berechtigungsänderung gehören dazu.
**`camera_step` hat drei Aufrufer, nicht einen:** die Kappe, das Kippen mit
dem gedrückten Rad und die Flugtasten. Wer dort an einer Achse dreht, dreht
an allen dreien

Flugtasten folgen den Qt-Tastenkennungen, auch wenn Strg ihren Ereignistext
verändert. Loslassen und Fokusverlust beenden den Takt und stellen den
Kameraruhezustand einschließlich Schatten wieder her.

**Wer eine Fläche braucht, kommt gleich hin — wer keine braucht, behält
seinen Dialog.** `placement_flow.starts_by_itself(spec)` zieht die Grenze an
`consumes`: Baustein, Beschriftung und Bohrung sitzen auf etwas und gehen
sofort in die Platzierung; die fünf Grundkörper entstehen aus eigenen Maßen an
eigenen Koordinaten und bleiben beim Dialog. Dort zeigt die Live-Vorschau den
Körper, sobald der Dialog offen ist — `Session.preview_async` rechnet ihn
ohnehin, und `request()` überspringt sie nur, solange die Platzierung läuft.
`start()` versteckt den Dialog, und Breite, Tiefe und Höhe stehen nirgends
sonst; wer die Maße ändern wollte, musste sonst Escape drücken, tippen und neu
platzieren. Der Knopf bleibt für den, der doch auf eine Fläche will.

**Und diese Vorschau lässt sich anfassen.** `Viewport.set_preview_gizmo`
hängt denselben Bewegungsgriff an den `added:`-Aktor der Vorschau, den
`set_gizmo` sonst an die Auswahl hängt — ohne Skalierwürfel, denn Breite,
Tiefe und Höhe stehen im Dialog daneben. Der Zug meldet sich über
`previewDragged` als **Matrix** und nicht als `TransformSteps`: Er wird keine
Operation, sondern Zahlen, und `primitive_ops.placement_values_of` rechnet
daraus Ort, Richtung und Winkel — die Umkehrung von `placement_transform`,
gegen ihn geprüft. `_grips_its_preview` entscheidet, wer ihn bekommt: wer
seinen Dialog behält und die Felder dafür hat — heute zwölf Operationen,
die sieben Grundkörper samt dem Gewindebolzen und die vier freistehenden
Bausteine.

**Und die Maßfelder lassen ihm seinen Platz.** Sie sind Qt-Widgets über der
Renderfläche, und was dort liegt, nimmt die Zeigerereignisse an — der Griff
wäre sichtbar und tot. `Viewport.gizmo_reach()` nennt Ursprung und Reichweite,
`PlacementFlow` hält daraus ein eigenes gesperrtes Rechteck frei (als zweites
und nicht als größerer Radius: Der Griff sitzt an der Bohrungsmitte, der
Setzpunkt an ihrer Mündung).

**Und er kommt nie neben den Griff der Auswahl.** Der hängt am zuletzt
gewählten Körper und trägt einen Skalierwürfel; die Vorschau daneben zeigt
den Körper, den der Dialog gerade anlegt. Wer den Würfel anfasste, änderte
die Maße eines fremden Teils, während die des neuen im offenen Dialog
stehen. `set_preview_gizmo(True)` nimmt ihn deshalb ab und
`set_preview_gizmo(False)` baut ihn wieder auf — `_detach_gizmo` lässt den
Schalterzustand in Ruhe, die Entscheidung bleibt also stehen.

**Ein Griff, der nicht in `_dispatch_pointer` steht, ist sichtbar und tot.** Er
wird gezeichnet, nimmt aber kein Zeigerereignis an, und jede Geste fällt
durch zur Kameraführung — wer den Quader in seiner Vorschau verschieben
wollte, schwenkte die Ansicht. Die Vorfahrt dort ist die eine Stelle, an
der ein neuer Griff eingetragen wird; `tests/test_viewport_decisions.py`
liest sie im Quelltext gegen die Griff-Felder des Aufbaus. Der Griff wird nach jedem
Neuzeichnen der Vorschau frisch angehängt; er rechnet gegen die Matrix seines
Ziels beim Anhängen, und die Vorschau kommt bei jeder Wertänderung neu.

**Ein Langloch aus einem Schritt ändert diesen Schritt** (15.09.2026). Hat ein
`slot_hole`-Schritt das Langloch gezogen (`Feature.created_by`), gehen
*Übernehmen* im Merkmalfenster, die stille Platzierung und der Zug an den
Langlochknöpfen in **diesen** Schritt (`MainWindow._prepare_slot_change`) —
kein zweiter im Verlauf, kein Kreuz im Bild. Beide Abschlüsse, Merkmalfenster
und Maßgruppe (`_commit_preview_order`), schreiben über
`_commit_slot_change`: Rastet das Langloch auf genau die Bohrung zurück, aus
der der Schritt es gezogen hat (`_slot_step_undone`, gelesen an
`EvaluationResult.sights`), fällt der Schritt, mit Quittung und Strg+Z als
Rückweg (Regel in `griffe.md`). Geschrieben wird nur, was vom
gemessenen Wert abweicht; die Felder tragen die Toleranz des Schnitts. Ein
erkanntes Langloch ohne Schritt geht weiter als neuer Schritt an den Kern.
Alle Langlöcher öffnen dieselbe Maßgruppe für Länge, Richtung und Breite;
die Herkunft entscheidet nur über den gespeicherten Auftrag. Der Wechsel
von `resize_hole` zu `slot_hole` übergibt den begonnenen Breiten- und
Positionsentwurf. Eine noch offene Tiefenänderung bleibt im Bohrungseditor,
weil die Langlochoperation diese Änderung nicht ausdrückt.
`_reshape_slot_from_values` führt Maßfelder, Griff und Umriss mit derselben
effektiven Breite nach. `Viewport.reshape_slot` bindet den Entwurf auch dann,
wenn sein Griff während des Editorwechsels gerade abgebaut ist.
Der Panelabschluss übernimmt den vollständigen geprüften Auftrag; das
verkürzte Griffsignal ersetzt keine Breiten- oder Toleranzparameter.

**Ein Loch hat eine Länge, und die ist eine Geste.** `slot_handle.py` hängt
zwei Knöpfe an ein gewähltes Loch (`hole` oder `slot` — welche Arten, sagt
`slot_feature_kinds()` aus dem `applies_to` von *Zum Langloch ziehen*), gezogen
wird in der Ebene seiner Mündung. Der Zug gibt beides zugleich: die **Länge**
aus dem Abstand zur Mitte, die **Richtung** aus dem Winkel dazu — gegen
dieselbe Rahmenachse gezählt, gegen die `prepare.slot_profile` schneidet und
`prepare_ops.slot_angle_of` misst. Der Umriss im Bild kommt aus derselben
Funktion wie der Schnitt; beim Loslassen meldet `slotDragged` Kennung, Länge
und Winkel, und `MainWindow._on_slot_dragged` macht daraus **einen** Schritt.

Er sitzt genau dort, wo der Skalierwürfel nicht sitzt: Der gilt dem ganzen
Körper, ein Merkmal hat keine Größe, die er ändern könnte — ein Loch aber hat
eine. Die Form trägt die Bedeutung (Regel 18): Pfeil schiebt, Ring dreht,
Würfel skaliert, **Knopf zieht in die Länge**; das `L` daneben ist dieselbe
Schreibweise wie das `S` am Würfel.

**Und er hängt an einer eigenen Artenmenge.** `slot_handle_feature()` fragt
`slot_hole`, `gizmo_feature()` fragt `move_feature` — ein Langloch trägt heute
die eine Fähigkeit und die andere nicht, und über einen Kamm geschoren
verlöre es beide. An einem Langloch steht deshalb der Knopf **ohne**
Bewegungsgriff; drei Pfeile, die keine Operation einlöst, wären schlimmer als
keine.

**Und die Knöpfe stehen auch, wo der Bewegungsgriff gesperrt ist** (RM-197,
21.09.2026). Der Maßeditor sperrt an einer gewählten Bohrung den Merkmalsgriff
(`set_feature_gizmo_blocked`) und hängt seinen Platzierungsgriff an den
Werkzeugkörper; `set_gizmo` lässt in beiden Lagen nur Pfeile, Ringe und Würfel
weg (`only_knobs`) und baut Flächenscheibe und Langlochknöpfe weiter auf,
`grip_placement` holt sie nach dem ersten Griff zurück. **Der Bewegungsgriff
der Platzierung bleibt über Kamerageste und Radraste erhalten**: Statt je
Zeichnen frisch zu entstehen, bleibt er, solange `Gizmo.fits` dieselbe
Zielmatrix, Drehung und denselben Maßstab bestätigt — und ein gedrückter
Griff (`pressing`) wird nie unter der Hand ersetzt (Review Ansicht #3 und #7).
Während eines Zugs an den Knöpfen zeichnet `SlotHandle` nicht selbst; die Marke folgt über
`_on_slot_interacted`, und nur wenn `_repaint_preview` nichts gezeichnet hat,
rendert der Viewport nach — ein Bild je Mausbewegung statt zwei (RM-200, die
Regel in `griffe.md`).

**Der Zug endet im Merkmalfenster, nicht im Verlauf** (Robert, 10.09.2026):
Wohin etwas gehört, sagt die Stelle, an der man loslässt; wie **lang** es ist,
sagt eine Zahl, und zwanzig Millimeter trifft niemand mit der Maus. Nach dem
Loslassen bleibt der Umriss stehen, und `Viewport.slotProposed` schreibt Länge
und Richtung in die Felder unter *Zum Langloch ziehen*; erst das Übernehmen
dort macht daraus die Operation. Die Eingabetaste an der Zugleiste ist der
kurze Weg dorthin, Escape verwirft.

**Und danach bleibt das Langloch gewählt.** Ein Übernehmen im Merkmalfenster
merkt sich Merkmal und Stelle (`_feature_to_keep`, `_resume_near`);
`_reselect_the_renamed` sucht nach der Auswertung an dieser Stelle, weil
`hole_1` im Schritt zu `slot_1` wird und der Baum nur wiederherstellt, was es
noch gibt. Getrennt von `_measures_to_resume`: Das eine wählt wieder aus, das
andere bringt die Maßlinien zurück — und nur, wer aus dem Bild heraus
übernommen hat, will beides.

**Eine eigene Leiste unten hatte er bis zum 11.09.2026** (`slot_bar.py`), mit
denselben zwei Zahlen und einem zweiten Übernehmen — zwei Bedienstellen über
demselben Loch (Robert: „auch 2 mal übernehmen einmal unten und einmal
rechts"). Sie ist gefallen; was von ihr bleibt, ist die Frage
`Viewport.slot_drag_waits()`: **der Zustand und nicht ein Widget** — Umriss im
Bild, gemerktes Merkmal, noch kein Schritt.

Erst ein Zug über die gemeinsame Klickschwelle beginnt eine Vorschau;
Zurückziehen auf den Druckpunkt räumt sie wieder ab. Der Richtungsfang
entspricht dem Drehring.
Die Merkmalsfelder schalten schon beim Fokussieren ihre Handlung scharf;
deren Titel steht über *Übernehmen*. Die Eingabetaste in einem Feld übernimmt
sie — dieselbe Handlung, die der Knopf meint, und nur solange er sie annimmt.
Feldlose Handlungen haben einen eigenen
Knopf. Bei Bausteinauswahl bleiben die Handlungen am erzeugenden Schritt;
sein Entfernen nutzt die Folgeauskunft des Verlaufs (§19).

**Die Knopfzeile wohnt beim Träger, nicht im Rollinhalt** (`FeaturePanel.footer`,
13.09.2026). `MainWindow._build_feature_dock` hängt sie unter den Rollbereich;
wer das Panel allein baut, findet sie unten in seinem Layout. Wegen dieses
Umzugs beantwortet `isVisibleTo(panel)` an ihren Knöpfen nicht mehr, was sie
soll — gefragt wird `isHidden()` (`_apply_stands`).

`set_locked(grund)` sperrt Felder und beide Knöpfe und schreibt den Grund in
eine sichtbare Zeile der Knopfzeile **und** in Kurzhilfe, Statuszeile und
zugängliche Beschreibung (Regel 18). Gerufen wird sie aus `_update_actions`
mit demselben `_halt_reason`, der Menü, Werkzeugzeile und Befehlspalette
sperrt; sie überlebt den Neuaufbau der Zeilen und fällt nach einem Undo ohne
Neuauswahl.

Solange ein Langlochzug wartet (`slot_drag_waits`), nimmt `PlacementFlow`
keine Platzierungsklicks an. Die Platzierung eines **neuen** Werkzeugs aus
dem Dialog tritt dabei ganz zurück — Felder, Vorschau, Leiste. Die
**gebundene Maßgruppe** am gewählten Loch bleibt dagegen stehen, mit Linien
und Feldern, und zeichnet bei jeder Kameradrehung neu (21.09.2026, Robert:
„wenn wir das langloch ziehen und dann die ansicht drehen sind die maße
weg"); nur der runde Umriss der Mündung weicht dem gezogenen des Griffs, und
`slotProposed` löst den Aufbau gleich beim Loslassen aus. Escape stellt die
bisherige Platzierungsabsicht wieder dar; das Übernehmen verwendet weiterhin
den einen Langlochschritt.

**Ein gewähltes Merkmal bekommt seinen Griff ohne Werkzeug.** Der Schalter
gehört dem Werkzeug *Bewegen* und gilt dem ganzen Körper — dort trägt der
Griff den Skalierwürfel, und der ändert auf einen Zug die Maße des Teils.
Am Merkmal ist der Klick selbst die Ansage (Robert, 10.09.2026: „über den
viewport sehen wir weder maße noch etwas zum verschieben, verlängern, drehen
usw"); der Würfel bleibt dabei weg.

**Und die Maße wie beim Setzen kommen auf Knopfdruck.** Wer ein Loch gewählt
hat, findet im Merkmalfenster *Im Bild einstellen*; der Knopf bringt die
Flächenplatzierung mitsamt Maßlinien zu den Kanten und einem Zahlenfeld je Maß
in die Szene. `FeaturePanel.inViewRequested` bleibt getrennt von
`operationRequested`, weil das eine zeigt und das andere schreibt.

**Er steht einmal je Merkmal, nicht je Handlung** (`_settle_in_view`). Die
Maßlinien zeigen die Stelle des Lochs, und die ist dieselbe, gleich ob man
gerade den Durchmesser oder die Länge ansieht; an der scharfen Handlung
aufgehängt verschwände der Knopf, sobald jemand ein Feld von *Merkmal drehen*
anfasst.

**Unter den Handlungen steht ein Haken, der keine ist: *Vor Trennnähten
schützen*** (`FeaturePanel.protectionToggled`, RM-080). „Diese Fläche soll
schön bleiben" — die eine Kundengeste der Trennen-Serie. Der Haken schreibt
keinen Schritt: `Session.set_protected` trägt die Merkmalkennung in
`Document.protected` ein, markiert das Projekt als geändert und meldet
`projectChanged`; `MainWindow._on_project` gibt den Stand über
`Viewport.show_protected` ins Bild (Tönung und Schraffur, Farbrolle
`protected`), und `selection_label` hängt „geschützt" an — die zweite Kodierung
(Regel 18). Ob sich ein Merkmal sperren lässt und was auf dem Haken steht,
sagt der Kern (`perceive.actions.protection_of`): geschützt wird, was
Dreiecke hat. Gelesen wird die Sperre genau einmal, in `Session.split_async`,
als Punktwolken für `plan_split`; bleibt neben ihr keine Ebene, trägt der
Befund `split.blocked_by_protection` den Knopf *Sperren aufheben und erneut
teilen* (`_release_protection_after_error`, Körper aus dem Befund).

**Und die Platzierung trägt dabei kein Fenster** (`QuietHost`, 11.09.2026).
Bis dahin startete sie von selbst und hing an einem Operationsdialog, der
daneben stand und Durchmesser, X, Y und Z ein zweites Mal zeigte — dieselben
Zahlen, die rechts im Merkmalfenster stehen, nach einer Operation sogar mit
anderen Werten (Robert: „werte im dialog und in der rechten merkmalleiste
doppelt, sehr verwirrend für den Kunden"). Was der Fluss von seinem Träger
braucht, steht in `PlacementHost`; `MainWindow.end_quiet_placement` räumt ihn
ab, denn ohne Fenster meldet niemand sein Ende.

Die stille Platzierung gehört zu einem festen Körper und Merkmal. Eine andere
Auswahl räumt sie ab; das kurzzeitige Leeren beim Wiederherstellen derselben
Baumauswahl wird erst nach der Ereignisrunde bewertet. Vor dem Übernehmen
prüft ihr Rückruf zusätzlich Träger, Dokument und Auswertung, damit ein alter
Auftrag keine inzwischen gleich benannte Stelle verändert.

Träger und Merkmalsfelder gleichen ihre Werte in beide Richtungen ab.
Bildpositionen aktualisieren die Felder ohne Wechsel der aktiven Handlung
(`take_values(..., arm=False)`); getippte Maße erneuern das Platzierungswerkzeug.
Koordinaten innerhalb der Trägerfläche führen die Maßlinien nach, freie
Koordinaten außerhalb wechseln in die normale Feldvorschau. Ein Übernehmen
während des Werkzeugaufbaus wartet auf dessen Ergebnis; Abbruch, Kontextwechsel
und neuere Eingaben löschen diese wartende Übernahme.

**Sie beginnt dabei dort, wo das Merkmal schon sitzt** (`_begin_at_feature`,
10.09.2026). Bis dahin fing jede Platzierung bei „Auf eine Oberfläche zeigen"
an — richtig für ein Werkzeug, das noch nirgends sitzt, falsch für eine
Bohrung, die schon da ist: Ihre Stelle steht fest, offen sind die **Maße**.
Die Fläche ohne Klick liefert `placement.seat_of`; der Rest ist derselbe Weg
wie nach einem Treffer und endet gleich in Stufe zwei. Wo es keine Trägerfläche
gibt, bleibt es beim Zeigen — kein Fehler, ein Rückfall. Welche Handlungen
das anbieten, sagt der Kern (`placement.supports_surface_placement`), nicht
eine Liste in der Oberfläche.

**Und dort zielt der Zeiger nicht** (`_seated_at_feature`, 11.09.2026). Die
Stelle gehört dem Merkmal; eine Mausbewegung darüber verschob sie samt aller
Maßlinien unter der Hand, und die Abstände liefen vom Zeiger statt von der
Bohrungsmitte (Robert: „wir wollen aber bei der bohrung das mittelloch"). Ein
**Klick** ist die ausdrückliche Ansage, das Loch woanders hinzusetzen, und
danach zielt wieder der Zeiger — beim Setzen einer neuen Bohrung ändert sich
nichts.

**Eine Geste im Bild räumt sie ab** (`_drop_stale_measures`). Was dort steht,
gilt für einen Stand, den die Geste gerade ändert: Der Zug am Bewegungsgriff
versetzt das Loch, der am Langlochgriff macht es länger. Der Knopf bringt sie
danach zurück — an derselben Stelle, mit den neuen Zahlen.

**Ein Merker (`_measured_for`) und zwei Wächter standen hier bis zum
11.09.2026** und hingen alle am Selbststart: Er sprang nach jeder Auswertung
neu an, verwarf dabei offene Dialoge und fragte bei zurückgenommenen Schritten
nach. Mit ihm sind sie gefallen. Was von der Frage bleibt, ist die Zusage von
§18.5: Ein Klick auf ein Merkmal ist eine **Eingabe**, wo ein Dialog auf eines
wartet — und das entscheidet weiterhin `_on_feature_picked`.

**Der Werkzeugkörper gehört dazu, sonst bleibt der Knopf grau.**
`PlacementFlow` gibt *Übernehmen* nur frei, wenn `placement.prepare_tool` einen
Körper geliefert hat; `_creation_tool` kennt dafür einen eigenen Zweig für
`slot_hole` und `resize_hole`, der Mitte, Achse und Tiefe aus dem **Merkmal**
liest. Wer eine weitere Operation in `supports_surface_placement` einträgt,
trägt sie auch dort ein — sonst zeigt die Oberfläche Maßlinien und eine Leiste,
die „Übernehmen" sagt, und nichts davon geht.

**Zwei Wege dürfen nicht auf dasselbe Loch schreiben.** Der Zug am
Langlochgriff macht ein Langloch, der Dialog *Bohrung ändern* eine runde
Bohrung; nebeneinander offen nahm der eine zurück, was der andere gerade getan
hatte. `Viewport.slotStarted` meldet das Übernehmen des Langlochzugs, und
das Fenster schließt daraufhin die Platzierung an derselben Stelle. **Beim
Übernehmen und nicht beim Ziehen**: Solange der Zug wartet, ist nichts
geschehen (Regel 2) — und die Maße sollen währenddessen im Bild stehen.

**Platzieren geht in drei Stufen** (Robert, 09.09.2026). Zeigen und klicken
legt die **Stelle** fest (`_settle`) — der Klick schließt nicht mehr ab, denn
er nähme jede Vorgabe mit, die daran hängt, und bei einer Bohrung heißt
`depth = 0` durch das ganze Teil. Dann stehen die **Maße** offen: die Abstände
zu den Kanten als Zahlenfelder, eintippbar. Erst das Übernehmen führt in die
**Tiefe** (`_begin_depth`), wo es eine gibt — sonst schließt Stufe 2 ab.

Wer eine Tiefe hat, sagt `deepens()`: Das Werkzeug sitzt auf etwas
(`consumes != 0`) **und** führt ein Längenfeld dafür (`parts.ops.depth_field`).
Beides ist nötig — ein Quader trägt ein Feld namens `depth`, und das ist seine
Bauteiltiefe, nicht die Eindringtiefe. **Und der Name allein entscheidet
nicht:** `depth_field` fragt zusätzlich die Abtragsrichtung, sonst zöge die
Stufe an der vorstehenden Nase von `insert_latch` oder an einer erhabenen
Beschriftung. Die Regel dazu steht in `app/core/knowledge/parts/CLAUDE.md`.

**Die Stufe beginnt mit einer Tiefe, nicht mit der Null.** Bei `depth = 0`
bohrt die Operation durch das ganze Teil; wer die Stufe betrat und ohne zu
ziehen übernahm, bekam genau das, was sie abschaffen soll. Vorbelegt wird mit
dem Material unter der Mündung, und der Zug fällt nicht unter
`LEAST_DEPTH_MM` — sonst führte ein Zug nach *oben*, der flacher machen soll,
am Ende des Wegs hindurch. Die Null bleibt über das Maßfeld erreichbar, wo sie
ausgeschrieben dasteht.

In der Tiefenstufe kehrt sich um, was Stufe 1 zeigt: Der Werkzeugkörper tritt
**vor** (der Umriss sagt nichts über die Tiefe), das Modell wird durchscheinend
und die Kamera schwenkt quer zur Werkzeugachse — bei aufrechter Achse auf
Augenhöhe der Mündung. Die Kantenmaße weichen den Bezugsmaßen der Tiefe:
Maßlinie zur Spitze, Maßlinie zur Rückseite mit der Wand, die stehen bleibt,
und eine Marke auf halber Materialstärke. Der Zug misst **absolut** — die
Spitze liegt unter dem Zeiger, gerechnet aus der Bildrichtung der Achse und dem
Maßstab an der Stelle (`_pixels_per_mm_at`) — und rastet über
`transform.snap_to_marks` kurz an Mitte und Rückseite ein. Was die Platzierung
dort **nicht** nimmt, gehört der Kamera: Drehen, Zoomen und Kippen bleiben frei.

**Beide Größen werden je Bewegung neu geholt, nicht einmal beim Betreten.**
Die Bildrichtung der Achse war es von Anfang an; der Maßstab nicht, und die
Ansicht rechnet perspektivisch — nach einem Zoom um k war die Tiefe um k
daneben. Ebenso zählt, gegen welches Material gemessen wird: `_material_below`
schießt einen Strahl und nimmt den **ersten Austritt**, nicht den fernsten
Punkt des Hüllquaders. In der 2 mm starken Decke einer Box stand sonst
„Wand: 18,0 mm" im Bild, und das Einrasten hielt an Marken im Hohlraum.

**Eine getippte Zahl hält, und ein Zug an der Kamera setzt nichts fest.**
Beides sind Sperren über dasselbe Feld (`_depth_set`): Wer die Zahl eingibt,
hat entschieden — der Zug misst absolut und überschriebe sie sonst bei der
nächsten Bewegung, und der Weg zum Knopf führt über die Renderfläche. Und wer
die linke Taste zum Schieben drückt, meint nicht die Tiefe; unterschieden wird
an der Zugschwelle des Systems (`_barely_moved`), wie überall in der Ansicht.

**Drei Fallen, alle drei einmal zugeschnappt:** Ein Feld, dessen Sichtbarkeit
gesetzt wird, aber weiter eingesammelt wird, zeigt die Platzierungsschleife
danach wieder (`place` sammelt in der Tiefenstufe nichts mehr). Die Leiste
steht unten mittig über der Werkzeugzeile, und der Raum für die Maßfelder ist
seither der **über** ihr. Und was nach der Leiste nicht selbst gehoben wird,
liegt darunter und ist nicht anklickbar — Tiefenfeld und Wandzahl stehen
deshalb in derselben Liste wie die Kantenmaße.

**Platzieren bleibt eine Operation.** Der Operationsdialog übergibt Werte an
`PlacementFlow`; der Controller zeigt nur einen temporären Werkzeugaktor und
Maßpfeile. Der Dialog **bleibt dabei stehen**: Er trägt die Maße, die man beim
Platzieren braucht, und verschwand genau dann, wenn man sie sehen wollte. `Session.placement_async()` berechnet Originalfläche und
`PlacementTool` außerhalb des Qt-Threads. Mausbewegungen und Maßänderungen
verwenden diese Kontexte; der Merkmalskörper wird dabei nicht erneut gebaut.
Der Kontext gehört zu Eingaben und Werten, verspätete Ergebnisse werden über
Generation und Laufkennung verworfen. `Position übernehmen` bestätigt den
vorhandenen Dialog und erzeugt genau dessen Transaktion; Escape behält die
Zahlen ohne neuen Verlaufsschritt — **und geht je Stufe genau eine zurück**
(`PlacementFlow.step_back`, RM-205): Tiefe → Maße → Zielen → Dialog. Aus dem
Dialog führt ein Klick auf das Modell zurück und setzt dort die Stelle
(`_resume` über `Viewport.set_placement_resume`, sendet `surfaceRequested`);
der Dialog zeigt dazu seinen Platzierungssatz und den Tastaturknopf
`aim_again` weiter. `show_placement_hint(on, paused=...)` hält beide Aussagen
getrennt: Der Fluss meldet bei `back()` die Pause, beim aktiven Zielen und
beim endgültigen Ende verschwindet der Rückkehrknopf. Beim Ändern eines
Schritts gibt es nur eine Stufe, dort geht Escape ganz zurück; am gewählten
Merkmal (`QuietHost`) tut es, was *Abbrechen* tut — verwerfen und abwählen. Die Mausbewegung fragt im 16-ms-Takt nach der
Fläche, nicht erst im Stillstand: eine Frage zur Zeit, ihr Ende nimmt die
jüngste Stelle, und eine überholte Antwort behält die vorbereitete Fläche
(`_surface_known`) samt der einen Netzkopie des Arbeiters (`_surface_mesh`). Beim Bearbeiten eines historischen Schritts
liefert `Session.placement_before()` dessen tatsächlichen Eingang. Auch ein
fehlerhafter Schritt bleibt damit korrigierbar. `result_current` und
`Viewport.is_scene_applied()` sperren Ziele bis zur aktuellen sichtbaren Szene.
Der historische Eingang bleibt der Bezug für Auswahl und Maße. Die vollständige
Endvorschau fordert über `show_preview_base()` die aktuelle Ergebnisszene an
und wartet auf `sceneApplied`. Eine erneute Flächensuche entwertet die
Vorschaufreigabe und stellt zuerst den historischen Eingang wieder dar.
Maßfelder erhalten ihre Float64-Werte und werden gemeinsam außerhalb der
tatsächlich sichtbaren `OverlayHost`-Karten angeordnet; Verbindungslinien halten
verschobene Felder ihren Maßpfeilen zugeordnet.

Die Maßtinte — Linien, Pfeilspitzen, Zuordnungsmarken — liegt im Renderer
(`_Dimensions`, oben unter RM-198); ein Qt-Widget mit Maske über der
pygfx-Renderfläche gibt es seit dem 21.09.2026 nicht mehr, und ein
vollflächiges `WA_NoSystemBackground`-Widget darüber bleibt ausgeschlossen.
Die Zahlenfelder sind Qt-Fenster und liegen von sich aus über dem Bild —
deckend, ohne Maske; `occupied` hält beim Verteilen die **Felder** von
Setzpunkt, Griff, Körper und voneinander fern, die Tinte darunter spart
nichts aus. Die gefüllte Werkzeugvorschau zeigt ihre Oberfläche ohne
innere Dreieckskanten.
Resize eigener Maßfelder ist ein Layoutergebnis und startet keinen weiteren
Aufbau; nur Viewport und Rendererwidget verändern die verfügbare Fläche.

**Die Auswahl behält den sichtbaren Treffer.** Ein Oberflächen-Pick trägt
Körper, Weltpunkt und Dreieck bis zur Merkmalsauswahl und Messung. Nur wenn
das gezeichnete Netz das unveränderte Originalnetz ist, bestimmt seine
Dreieckskennung das Merkmal direkt; Schnitt- und vereinfachte Netze nutzen
den Ortsfang. Platten- und Explosionsversatz werden für jeden Körper getrennt
zurückgerechnet. Ein Treffer gehört seinem Körper, auch wenn ein kleinerer
Hüllquader davor liegt. Die Öffnungszielhilfe gibt Körper und Merkmal gemeinsam
zurück. Dreieckszuordnung und vorbereitete Bohrungsachsen werden pro Auswertung
gespeichert und beim Szenenaufbau verworfen; Hover projiziert dadurch nicht
wiederholt alle Bohrungsdreiecke. **Wem ein Dreieck gehört, sagt der Kern**
(`relations.cell_owner_table`, P1.5): bei Verschachtelung das innerste
Merkmal, bei zwei, die sich nur überlappen, niemand (`CONTESTED`) — dann
greift der Ortsfang, und der nimmt bei gleichem Abstand das kleinere Merkmal
und dann den Namen, nicht das zuerst vorbereitete (`_feature_hit`).
Die Öffnungszielhilfe verlängert keine axialen Bohrungsgrenzen. Seitlicher
Randfang gilt nur am sichtbaren Eintritt oder bei einem belegten Treffer des
wirklichen Bohrungszylinders; eine Rückwand bleibt eine Sichtgrenze.
Nur Bohrungen, Langlöcher, Senkungen (`cone` mit `recess`) und Innengewinde
bilden axiale Öffnungsziele (`_is_opening_feature`). Ein Langloch zielt mit
seinem Umriss, nicht mit einem Kreis um die Mitte: `_BoreTarget` trägt Weg und
Richtung (`_slot_frame`), `bore_span` rechnet dann gegen das Stadion
(`_stadium_span`), und `_feature_inside` misst gegen die Mittellinie. Rundungen,
Ringnuten und äußere Flächen bleiben Dreieckstreffer.
Die Rückrechnung liest den beim Aktoraufbau gespeicherten Versatz und die
tatsächlich gezeichneten Körper. Während eines neuen Ansichtsauftrags und
nach dessen Fehler bleibt dieses letzte Bild die Grundlage des Picks;
angeforderte Platten- oder Explosionszustände greifen erst mit dem neuen Bild.
Ansichtsarbeiter bekommen eigene Netzkopien für Schnitt und Dezimierung;
bei exakten Körpern wird nur ihre Anzeigetessellation kopiert. Cachetreffer
werden vor der Verdrängung als zuletzt verwendet markiert.
Dieselbe Trennung gilt für die Platzierung: `placement_flow.for_a_worker`
kopiert das Szenennetz **im Hauptthread**, bevor `prepare_surface`, `seat_of`
oder `original_surface_hit` im Nebenthread darauf rechnen — sie füllen sonst
dieselben trägen trimesh-Caches, an denen der Hauptthread währenddessen
Hüllquader, Dreiecke und Kanten liest. Die Kopie bleibt je Szenennetz über
den Fluss hinaus, und wer an ihr rechnet, tut es unter ihrem Schloss
(`on_the_copy`; Regel in `wartezeit.md`). Sie nimmt die trimesh-Merker des
Originals flach mit (`features.copy_with_answers`: dieselben schreibgeschützten
Felder, eigene neue Einträge, und die geteilten Antworten der Erkennung). Eine Kopie je Netz, nicht je Aufgabe — zwei
Kopien nebeneinander verloren am Fenster gegen den GIL und die geteilten
Merker (gemessen, Docstring von `for_a_worker`).
Auch die Durchsicht der Druckplatte liest die zuletzt aufgebaute Szene und
deren sichtbare Körpermenge. Ihre Entscheidung wird bis zu einem Wechsel
dieser beiden Eingaben behalten; Kamerabewegungen lösen keine erneute exakte
CAD-Grenzenberechnung aus. Maßgeblich bleiben die ursprünglichen Körpergrenzen,
nicht die vereinfachten oder beschnittenen Anzeigeaktoren.
Merkmalsnamen und Maße stehen auf einem Feld in den Themenfarben, wie
Skizzenmaße. Der Text bleibt damit auch über heller Geometrie lesbar;
Merkmalsfläche und Ankerpunkt tragen weiterhin die Auswahl- beziehungsweise
Merkmalsfarbe.
Beschriftungen und Markierungsflächen benutzen dieselben Schnitt- und
Schichtebenen wie die Körper. Das automatische Schichtoverlay benennt nur
Merkmale, deren Dreiecke die aktuelle Ebene schneiden; die Anker liegen im
sichtbaren Schnitt. Auswahl und Hover dürfen erhaltene Geometrie darunter
benennen. Vollständig abgeschnittene Merkmale verlieren ihre Darstellung,
ihre Auswahl bleibt bestehen. Auswahl, Hover, Schutz und Kandidaten werden
ohne zusätzliche Schnittkappen begrenzt. Beim Schließen der Schicht gilt
wieder der unveränderte Merkmalschalter.
Markierungsflächen heben gemeinsame Originaleckpunkte gemeinsam an, mit den
flächengewichteten Normalen ausschließlich ausgewählter Dreiecke. Erst danach
werden die Punkte zur Dreiecksliste expandiert und geschnitten; weder fremde
Nachbarflächen noch ein Verschweißen gleicher Koordinaten verändern den Patch.
Die Akkumulation und Kreuzprodukte bleiben auf die ausgewählten Dreiecke begrenzt.
Das normale Merkmalslayout reserviert zuerst Leseraum für Auswahl und Hover.
Automatische Namen erscheinen nur an kollisionsfreien Plätzen nahe ihrem
Anker; alle Merkmalsmarker, Flächen und Baumziele bleiben erhalten. Versetzte
Namen sind mit dem dargestellten Merkmalsanker verbunden. Die Bildraumrechnung
berücksichtigt Kartenränder, interne Leisten und Gerätepixeldichte und folgt
Kamera sowie Größenänderungen. Sie benutzt nur Projektion und Textmaße, keine
Geometriesuche oder GPU-Rücklesung. Gleiche Kamera- und Layoutdaten werden
wiederverwendet; gleiche Textlisten und Linienzahlen verschieben vorhandene
Rendererobjekte. Bei Körpervorschauen folgen Marker, Text, Verbindungslinien
sowie Auswahl- und Hoverflächen der Matrix und Position ihres Körperaktors.
`select_feature_refs` hält objektübergreifende Merkmalsauswahl als vollständige
Paare aus Körper- und Merkmalskennung; gleiche lokale Kennungen bleiben getrennt.
Das erste gültige Paar führt die Körperauswahl, mehrere Paare erzeugen kein
scheinbares Einzelmerkmal. Jede Körpergruppe behält ihre eigene Auswahlfläche,
Vorschaumatrix und Schnittbegrenzung. `select_features` bleibt der Adapter für
Merkmalskennungen am führenden Körper; Neuauswertung und Abwahl räumen alte Paare ab.
Getrennte Konturaktoren sind ebenfalls ihrem Körper zugeordnet: Freier Zug,
Gizmo und Skalierwürfel gleichen ihre Matrix und Position vor dem vorhandenen
Gestenbild ab, auch ohne Merkmalsanzeige. Unveränderte Werte werden nicht erneut
gesetzt; Rücknahme und Szenenabbau nehmen die Konturen vollständig mit.
Die gespeicherten Originalanker bleiben unverändert; Rücknahme, Kamerawechsel
und die nächste Szene lesen denselben jeweils sichtbaren Aktorstand.
Der freie Körperzug wechselt bei genau einem gewählten Körper eine Merkmalsauswahl
vor seiner Vorschau über `objectPicked` auf die Körperstufe. Eine gemischte
Mehrfachauswahl bleibt vollständig erhalten; der gemeinsame Anschluss bestätigt
dieselbe Körpermenge, die die Vorschau bewegt;
das gezielte Merkmalwerkzeug behält seine eigene Merkmalsoperation.
Verbindungen reichen bis zum Textanker und liegen unter dem deckenden
Beschriftungsfeld; die größere Kollisionsreserve begrenzt keine sichtbare Linie.
Die Schutzschraffur berücksichtigt dieselben Schnittgrenzen
auch bei ihrer zusätzlichen Anhebung gegen Flimmern.
Flächenmarker in Schnitt- und Schichtansichten wählen einen Kandidaten aus dem
sichtbaren Rest eines einzelnen Originaldreiecks. Die vektorisierte Zuordnung
verhindert Mittelpunkte im leeren Zwischenraum nichtkonvexer oder getrennter Reste.
Bohrungs- und Achsenmitten sowie die unbeschnittene Darstellung bleiben erhalten.

Ausdrückliches Einpassen zeichnet einmal über den gemeinsamen Viewport-Pfad.
Die interne Kamerarahmung zeichnet noch nicht: Szenenaufbau und Achsansicht
stellen erst ihren fertigen Zustand dar. Die Rahmung berücksichtigt die
gemeldete freie Kartenfläche und Gerätepixeldichte; perspektivisch zählen
alle acht Hüllquaderpunkte mit ihrer Tiefe. Eine Karte zu öffnen verändert
den gewählten Ausschnitt im Körpermodus nicht.

**Panels und Leisten**

`panels.py` (die drei Panels links, Prüfbericht rechts, §2.5) ·
`selection_operations.py` (Körperoperationen in einer eigenen Karte unter der
von Bericht und Chat — beide Karten stapelt `overlay.CardColumn` als eine
Zone; einmal aus dem Register aufgebaut, bei Auswahlwechseln nur
nachgeführt — eine Gruppe über `OPEN_UP_TO` beginnt zugeklappt, und
`PICKER_HANDLES` lässt dem Filament-Schnellwähler darüber seine Handlung) ·
`tool_strip.py` · `analysis_bar.py` · `section_bar.py` · `split_bar.py` ·
`transform_bar.py` · `explode_bar.py` · `sculpt_bar.py` · `pose_bar.py` ·
`scale_widget.py` (der Würfel am Körper) · `slot_handle.py` (die zwei Knöpfe am
Loch — bestätigt wird im Merkmalfenster) ·
`facts.py` (was das Teil kostet, während man daran baut)

`CardColumn` liest seine Karten aus dem besitzenden Layout; einzeln gelöschte
Widgets bleiben dadurch nicht in einer zweiten Liste für die Maske stehen.
Sein Ereignisfilter bestellt wie jeder sterbliche Filter beim `Destroy` ab
— und beim `DeferredDelete`, denn ein über `deleteLater` gehendes Widget
bekommt `Destroy` am Filter nicht mehr (21.09.2026, `leash.py`).

Die Legende in `analysis_bar.py` verteilt bei vielen benannten Kartenstufen
ihre Beispiele über den gesamten Farbbereich und nennt die Zahl ausgelassener
Stufen. Jeder Beispielname behält exakt die Farbe seiner ursprünglichen Stufe.
Bei kontinuierlichen Karten stammen Farbraum und inverse Skalenwerte aus
`AnalysisMap`: Die Krümmung verwendet eine logarithmisch abgestufte Farbrampe,
deren Legende weiterhin physische Millimeterwerte nennt und die Abstufung
ausweist. Der Viewport reicht die transformierten Werte an den Renderer;
Messwerte, Schwellwerte und Hervorhebungen bleiben unverändert.

Benannte Stufen färben Bild und Legende aus **einer** Tabelle
(`palette.category_colours`). Bei den Karten aus `NEUTRAL_FIRST_MAPS`
(Netzfehler, Passungen) trägt die erste Stufe — „in Ordnung", „unbeteiligt" —
die Körperfarbe (`Viewport.body_colour`, als `neutral` an `show_legend`); die
Stufen darüber behalten die Rampe. An der Netzfehlerkarte steht in der Legende
*Reparieren*, wenn ein Schritt dort etwas ändern kann
(`MainWindow._offer_repair_on_the_map`, `_repair_can_help`): nicht gleich nach
einem Reparaturschritt, nach einem schließenden Einlesen nur an
Überschneidungen. Der Klick legt genau einen Reparaturschritt an.

Die Formabweichung zeigt obere Abstandsgrenzen ganzer Dreiecksflächen. Ihre
Legende nennt ausgewertete und unbekannte Flächen; bei vollständig unbekannter
Karte entfallen Zahlenrampe und Maximum. Das Maximalintervall gilt ausschließlich
für bekannte Flächen. Seine Grenzen und die numerische Facettenspanne werden
über `labels.length_bound` nach außen gerundet. `resolution` bleibt die
Rasterweite; die numerische Spanne ist keine Fertigungstoleranz. Herkunft und
Grund der fehlenden Werte stammen aus derselben Karte, auch im Kurzhinweis
und in der zugänglichen Beschreibung.

Ausgetauschte Kacheln, Programmzeilen, Spulendetails und Legenden werden vor
`deleteLater()` verborgen; das Entfernen aus dem Layout beendet ihre Sichtbarkeit
nicht. Die Füllung und Dicke der Schichtbalken bleiben fachlich gebunden, ihre
Randfarbe übernimmt der globale Stil über `layerLegendStroke` bei jedem Themenwechsel.

**Dialoge**

Operationsdialoge gehören dem Projekt, in dem sie geöffnet wurden. Ein
Projektwechsel schließt sie und verwirft ihre Vorschau. Varianten wechseln
Schema, Felder und Eingänge gemeinsam; gemeinsame Werte gehen mit,
varianteneigene Werte bleiben beim Zurückwechseln erhalten.
Die alten Formularzeilen werden dabei herausgenommen und verborgen, bleiben
bis zum vollständigen Neuaufbau lebend und werden anschließend über
`deleteLater()` freigegeben. Komplettierer werden vorher von ihren Feldern gelöst.
Ganze Zahlen benutzen denselben Verweis-/Formelweg wie Maße, außer wenn die Anzahl schon
beim Planen die Ergebniskennungen bestimmt. Quellenmerkmale bleiben an ihren
Eingangskörper gebunden, Klickziele tragen Körper und Merkmal gemeinsam.
`schemaChanged` bindet neu erzeugte Skizzenfelder wieder an den Raumeditor.
Der Feldname reist durch den Raumeditor zurück; mehrere Skizzen derselben
Operation ersetzen einander nicht. Bestehende Zeichnungen behalten ihre Ebene.
Freistehende Prüfkörper benutzen im Katalog `creation_name()` und brauchen
keinen Träger. Gemischte Bausteine zeigen `PlacementTool.addition` zusätzlich
zum Schnittkörper, mit gemeinsamer Platzierung und gemeinsamem Abbau.

Der Operationsdialog verwendet beim Erstaufbau und Variantenwechsel dieselbe
Promotion über `_promoted_fields`. Entschiedene Positionen kommen anhand von
`placement_fields` stets als vollständige XYZ-Gruppe nach vorn. Würden dadurch
mehr als acht Felder vorn stehen, bleibt die ganze Gruppe hinten; Fachparameter
behalten ihre Seite. Vorbelegte Richtungswerte ändern ihre Schemaseite nicht.

| Datei | Besonderheit |
|---|---|
| `op_dialog.py` | **Wird aus dem Parameterschema erzeugt** (§10, §2.4). Kein Dialog wird von Hand gebaut — wer einen tippt, hat das Register umgangen. `block_apply(reason)` sperrt *Übernehmen* von außen mit Grund — für das Band, dessen Grund eine Handlung trägt. `offer_naming=True` hängt vorn den Haken *Maße als Parameter anlegen* an, `names_dimensions()` liest ihn; die Parameter legt das Fenster an (`_named_dimensions`, §13). Die Stückzahl (`produces_from`) ist ein `CountField`: fx wie jedes Zahlenfeld, zur ganzen Zahl aufgelöst, bevor sie den Stapel erreicht (die Kennungen vergibt er vorher). `aim_again` führt nach Escape aus der Platzierung zurück in Stufe 1 (RM-205) |
| `dialogs.py` | Fragen und Fehler (§2.7), Freischaltung mit Online- und Dateiweg sowie freiwillige Förderung über PayPal oder GoFundMe (`DonationDialog`: Satz von Robert, drei Punkte „wofür" mit Symbol, zwei gleichwertige Anbieterknöpfe ohne Akzent, die Grenze als eine `caption`-Zeile, *Ohne Geld helfen* mit Link-Kopie und `feedback_wanted` für den vorhandenen Rückmeldedialog; `AboutDialog.support_wanted` für den Verweis). Eine Adresse im Browser öffnet `open_link`: ohne Browser liegt sie danach in der Zwischenablage und steht im Satz — `QDesktopServices.openUrl` direkt ruft niemand, der den Rückgabewert nicht liest |
| `print_settings_dialog.py` | Druckeinstellungen, Analyse des Ausgabeumfangs im tatsächlichen Schichtraster, slotbezogene Empfehlungen und Slicer-Übergabe (§29). An einem Resin-Drucker zeigt er nur, was gilt (`_reduce_for_resin`, `_fit_to_technology` nach einem Druckerwechsel): Drucker, Material, Platten, Programm und *Im Slicer öffnen* als Hauptknopf — Stufe, Wände, Füllung, Vorschläge, Düse, Slicen und Druckdatei sind verborgen, `settings_for_export` gibt keine Werte mit. Ein Programm ohne Familie (`other`) sperrt Slicen mit Grund und lässt Öffnen frei. Vor *Slicen* und *Im Slicer öffnen* fragt `dialogs.confirm_handover`, wenn der Prüfbericht Fehler der gewählten Platten trägt (`_may_hand_over`) |
| `print_disclosure.py` | Der Hinweis davor: dass diese Werte Erfahrungswerte sind und mit einer 3MF mitreisen — und die Wahl, ob sie das sollen (§29) |
| weitere | `settings_dialog` · `generate_dialog` (Weg 3) · `recipe_dialog` · `variants_dialog` · `comfy_dialog` · `install_dialog` · `support_dialog` · `update_dialog` · `changes_dialog` |

**Editor**

`sketch_editor.py` (§30.1, Stufe zwei)

`SketchCanvas.planes_are_parallel` liefert dieselbe Richtungsprüfung für den
Erhalt einer Flächenebene beim Einrasten und das Ziehgriffangebot.
`SketchPanel.offer_faces` erhält beim Neubefüllen den Kamerablick im Feld;
fällt die Ansichtsfläche weg, wechseln Feld und Kamera zur Zeichenebene.
`viewport.place_sketch_cards` verteilt Maß- und Griffkarten gemeinsam im
Bildraum; alle Karten bleiben erhalten.
Die Vorschau von Verrunden und Fase übernimmt die neue nicht konstruierende
Kante aus dem Kernergebnis; der virtuelle Eckpunkt dient nur der Maßbindung.

**Agent**

`chat.py` (§26.3, §2.5) · `snapshots.py` (Ansichten für den Agenten) ·
`remote_server.py` (MCP im Fenster; lesende Analysen wie die
Orientierungssuche gibt das Fenster als `core.agent.remote.Deferred` zurück —
nur der Schnappschuss entsteht im Hauptthread, `WindowBridge._compute` rechnet
im Serverthread mit Abbruch und Zeitgrenze)

**Prüfbericht**

`print_findings_flow.py` — nach jeder Auswertung die Befunde der
Schichtanalyse (`core.slice.findings`) im Arbeiter; ein neuer Stand löst den
laufenden ab, ein veralteter Stand liefert nichts nach

## P0-08 — KI-Hinweis an der Sendegrenze

Im Chat stehen Mangel- und Lizenzgrund direkt über dem passenden
Einrichtungs- oder Freischaltknopf im Rollbereich. Die reine Modellzeile
bleibt bei der Eingabe; beim Entsperren kehrt die Modellverfügbarkeit zurück.

`ai_disclosure.py` hält den sichtbaren Informationstext, den lokalen
Anzeigenachweis und die gemeinsame Sperre zusammen. `ensure_ai_disclosure`
steht vor jedem echten LLM-Modellaufruf: im Hauptfenster unmittelbar vor
`Session.propose_async`, im Chat-Einrichtungsdialog vor den beiden echten
Aufrufen der Ollama-Werkzeugprobe. Erst ein vollständig aufgebauter,
erreichbarer und zugänglicher Dialog öffnet den genau danach angeforderten Zug;
Zurück, Escape,
Schließen, ein unbekanntes Backend sowie Darstellungs- oder Speicherfehler
senden nichts.

Der Anbietertext folgt der tatsächlichen Nutzlast aus `agent/context.py` und
`session.py`, nicht einer verkürzten Produktbeschreibung: Für Anthropic nennt
er neben der aktuellen Nachricht den textlichen Szenensteckbrief,
Prüfbericht, begrenzten Chatverlauf, Anweisungen/Regeln/Werkzeugschemata und
die bei bildfähigen Modellen automatisch gerenderten Szenenansichten. Nicht
übertragen werden die Projektdatei und die Netzgeometrie selbst.

Ollama ist nicht gleichbedeutend mit „lokal“: Der eingetragene Dienst darf auf
einem zweiten Rechner liegen. Der Hinweis zeigt deshalb die von Geheimnissen,
Pfad, Abfrage und Fragment bereinigte Zieladresse und unterscheidet Loopback
von einem entfernten Ziel. Der entfernte Text nennt denselben Arbeitskontext;
die Werkzeugprobe nennt ihren festen technischen Auftrag ohne Projekt- oder
Chatinhalt.

Der Nachweis besteht ausschließlich aus Textfassung, Backend-Typ,
Zielklasse/Zieladresse und UTC-Zeitpunkt in `UiSettings`. Er reist nicht im
Projekt; Text-, Anbieter-, Local→Remote- und Hostwechsel schließen die Sperre
wieder, und die Einstellungen können ihn zurücksetzen. Weil `ChatPanel` vor
seinem Signal leert, hält es bis zur Entscheidung den unbearbeiteten
Eingabetext: Bei einem Abbruch kommen auch Leerraum und Zeilenumbrüche
vollständig und markiert ins Feld zurück.

Weg 3 nutzt denselben zugänglichen Dialog mit eigenem Erzeugertext vor dem
Start des Arbeiters. ComfyUI erhält Beschreibung oder Bild, Startwert,
Erzeugungsablauf und Modellwahl; der Hinweis unterscheidet Loopback und
Remote. Sein separater `generation_disclosure_*`-Nachweis bindet Textfassung,
Datenarten, bereinigtes Ziel und UTC-Zeitpunkt. Ein Chatnachweis ersetzt ihn
nicht. Der Auftrag hält eine Kopie des geprüften Comfy-Backends; wechselt das
Ziel während des Hinweises, verlangt der Dialog einen neuen Start. Abbruch,
Darstellungs- und Speicherfehler starten keinen Arbeiter. Der Rücksetzknopf in
den Einstellungen entfernt beide Nachweise erst beim Speichern.

## §29 — der Bericht kommt vor der Datei

`_ExportWorker` hört im ersten Lauf an der Prüfung auf: Findet sie etwas ab
`warning`, meldet er es über `checked` und endet.
`MainWindow._export_checked` legt die Befunde in den Prüfbericht, rückt ihn
nach vorn und fragt über `dialogs.confirm_export`; ein Ja startet einen
zweiten Lauf mit **demselben** Bericht (`checked=`), statt ein zweites Mal zu
prüfen.

`_start_export` sammelt die Auswahl einmal und kopiert Dokument und lokale
Einstellungen für diesen Auftrag. Die Bestätigung bekommt den geprüften
Arbeiter; dessen `after_check` reicht Körper, Quellen, Profile, Ziel und
Bericht gemeinsam an den Schreibdurchgang weiter. Ein Auswahlwechsel, eine
neue Auswertung oder ein anderes Projekt im Fenster verändern diese Datei
nicht. Ein ausdrücklich neu gestarteter Export liest den heutigen Stand.

Das gemerkte Exportformat wird gegen die aktuelle Auswahl geprüft. Besteht
sie nur aus Netzen, fällt ein gemerktes STEP für den Dialog auf 3MF zurück;
Dateiendung und Namensvorschlag folgen diesem angebotenen Format. Ein
Abbruch des Dialogs lässt die Projektpräferenz stehen, sodass eine spätere
B-Rep-Auswahl weiterhin STEP vorschlägt.

Der Arbeiter des ersten Laufs ist während des Dialogs noch am Auslaufen, und
der modale Dialog dreht die Ereignisschleife weiter. `_export_worker_done`
räumt ausschließlich sein eigenes Feld; `_run_export` verbindet beide
Durchgänge mit derselben Fortschritts- und Fehlerbehandlung.

**Die Szene reist mit** (`scene=`, `document=`), weil zwei der fünf Fragen aus
§29 in keinem einzelnen Körper stehen — eine verletzte Passung und eine Wand
unter der Mindeststärke. Dasselbe gilt für die Übergabe an den Slicer:
`_PlateJob` trägt beide Felder, und ihr Bericht war bis dahin um diese zwei
Zeilen ärmer.

## §29 — was die Datei mitnimmt

Fehler der Druckempfehlung zeigen ausführbare Vorschläge aus `handlers_of`
als Knöpfe; Rückwege ohne Handler bleiben als Text erhalten. Jede neue
Prüfung entfernt die alten Handlungen, und ein Klick liest den aktuellen Fehler.

`print_disclosure.py` steht vor dem ersten Öffnen der Druckeinstellungen und
sagt, wie die Erfahrungswerte entstehen, wann sie mitgegeben werden und dass
die Werte vor dem Druck zu prüfen sind. Anders als der
KI-Hinweis sperrt er nichts — hier verlässt nichts das Gerät, und die Wahl
darunter entscheidet erst über das Speichern.

Nur „Verstanden“ übernimmt die Dateibeilage und merkt den Hinweis. Escape
und Fensterschließen lassen beide Werte unverändert; der Druckdialog bleibt
auch über diesen Rückweg erreichbar.

Ein fehlgeschlagenes Speichern liefert `FAILED` und löscht den vorgemerkten
Hinweisnachweis, damit ein späterer Versuch tatsächlich erneut speichern kann.
Die gerade bewusst gewählte Dateibeilage bleibt für die laufende Sitzung erhalten.

Drei Stellen tragen sie: Der Hinweis fragt einmal je Textfassung, der
Umschalter im Kopf des Druckdialogs zeigt und ändert sie, und
`settings_for_export()` beantwortet damit die Frage, was eine Datei
mitbekommt. Der Merker steht in `UiSettings` (Fassung und UTC-Zeitpunkt) und
reist nie in einer Projektdatei.

**Der Fehler dahinter, weil er die Bauart erklärt:** Bis zum 03.09.2026 trug
**jede** exportierte 3MF Solidons Werte. Der Kern konnte es anders
(`writer._plate_settings` gibt bei fehlenden Einstellungen ein leeres
Verzeichnis), aber die Anwendung löste an ihrer eigenen Stelle auf — der
Ausgang war zugemauert. Dazu schrieb schon das **bloße Öffnen** des Dialogs
die Werte ins Dokument, denn `set_print_settings` lief nach `exec()` ohne
Rückfrage, und der Dialog hat nur „Schließen". `PrintSettingsDialog.has_changes`
misst deshalb am Anfangszustand und nicht an einer Liste von Knöpfen.

**Bibliothek**

`catalog.py` (Bausteinkatalog, §24.3) · `filament_picker.py` (Farbe und Name
statt einer Zahl von 0 bis 7)

**Ein eigener Baustein lässt sich wieder öffnen** (RM-147 E6): *Zum Bearbeiten
öffnen …* steht neben *Aus Bibliothek entfernen* und gilt derselben Menge —
eigene und eingelesene Rezepte, sonst ist der Knopf unsichtbar.
`MainWindow._edit_part` fragt wie beim Öffnen einer Datei, ob das offene
Projekt weg darf, und `Session.open_draft` macht daraus ein namenloses
Projekt; die Herkunft steht als `Session.draft_origin` am Dokument und fällt
mit ihm (`_reset_for`). Der Rezeptdialog belegt daraus Titel, Gruppe, Lizenz,
Autor, die freigegebenen Maße und die benannten Stellen vor — dann heißt sein
Knopf *Baustein ersetzen*, und ein anderer Titel legt einen zweiten an.

**Der Verlauf stellt einen Schritt in den anderen Rechenkern** (P2.8):
`HistoryPanel` bietet an jedem Grundkörperschritt den Satz aus
`registry.kernel_switch_label` an (`None` ohne Zwilling, an Bohren und
Aushöhlen, und in den exakten Kern ohne Kern) und sendet
`kernelSwitchRequested`; `MainWindow.switch_kernel` ruft
`Session.change_kernel` — die zweite Sperre (kein späterer Schritt braucht
den exakten Körper) wirft der Kern. Der Haken in den Operationsdialogen ist
gefallen — die Regel dazu steht in `oberflaeche.md`.

**Der Verlauf lässt sich umbauen** (RM-188 P7). `HistoryPanel` sagt nur, was
gewollt ist — `insertRequested`, `moveRequested`, `suppressRequested`,
`reactivateRequested`, `stopInsertRequested` — aus Kontextmenü
(`_add_revision_entries`), Tastatur (`_list_action`: Einfg, Alt+Pfeil,
Leertaste) und Ziehen (`_HistoryList`: legt nie selbst ab, fragt beim
Ziehen `places` nach gültigen Stellen und meldet den Grund über `refused`).
Neu gefasste Zeilen blendet es aus (`replanned_steps`), Einfügen und
Verschieben stehen als Protokollzeile mit ihrer Folge darunter
(`_add_revision_rows`), Zustand und Abhängigkeit als Wort an der Zeile
(`step_state`, `needs_tip`), die Einfügemarke als eigene Zeile
(`MARKER_ROLE`). `MainWindow._wire_history_revisions` verbindet das mit der
Sitzung: `Session.revise_history` plant sofort (eine unmögliche Stelle sagt
es ohne Wartezeit) und rechnet im `_RevisionWorker`; `revisionDone`,
`revisionCancelled` und `insertionChanged` gehen an die Statuszeile. Die
Regeln dazu stehen in `oberflaeche.md`. Escape gehört einmal dem
Hauptfenster: `_escape` beendet nach offenen Werkzeugen und Maßen das
Einfügen über `Session.stop_inserting`, bevor es die Auswahl verlässt.
Die Verlaufsaktion erhält dafür keine zweite Kürzelbindung.

**Ein Paar ist kein Baustein, sondern zwei** (RM-147 E1): *Gegenstücke setzen …*
steht deshalb im Menü *Bausteine* neben dem Katalog und nicht darin.
`counterpart_dialog.py` fragt genau zwei Dinge — welches Paar und wie groß —,
denn das Wo steht schon fest, wenn er aufgeht: Es sind die beiden Stellen, die
im Objektbaum markiert sind (`MainWindow._counterpart_targets`). Die Maßfelder
baut er aus dem **Bausteinschema** (`PartSpec.params.spec()`); welche davon
gemeinsam sind, sagt `Pair.shared` im Kern. Ein Paarwechsel tauscht sie
vollständig — was stehenbliebe, verspräche eine Wirkung, die die andere Hälfte
nicht kennt.

**Ist eine der zwei Stellen ein Gewinde, bleibt der Dialog zu** (P2.6,
Entscheidung 15): Das Gegenstück ist das gegengleiche Gewinde am anderen
Teil, im Maß des vorhandenen — ein Dialog wäre eine Frage ohne
Antwortmöglichkeit. `MainWindow._thread_among` erkennt die Lage,
`Session.create_thread_counterpart` legt Schritt und Gewindepassung an
(`core/counterpart.thread_counterpart_draft`), und die Absagen des Kerns —
kein Tabellenmaß, linksgängig, dasselbe Teil — kommen als Fehlerdialog.

`Session.create_counterpart` übernimmt beide Hälften und hängt nach der
Auswertung die Passung an dieselbe Transaktion. Erst danach läuft die
gemeinsame Änderungsnachbereitung: Das Projekt gilt als ungespeichert, die
automatische Sicherung erfasst das Paar, und die Auswertung prüft seine
Passung mit. Ein Undo nimmt beide Hälften und die Passung zusammen zurück.

**Der Menüeintrag beantwortet die Frage selbst**, statt sie nach dem Klick als
Dialog zu stellen: Ohne zwei markierte Stellen an zwei Teilen ist er gesperrt
und trägt den Grund. Beide Stellen — Riegel und Fehlerdialog für den Weg über
Palette und Kürzel — lesen ihn aus `main_window.counterpart_needs_two()`; zwei
Formulierungen derselben Auskunft laufen auseinander, und hier stünden sie
nacheinander vor demselben Kunden. Zurückgestellt wird der eigene
Erklärungssatz über `_pick_hint`, dieselbe Bauart wie bei *Formen* und
*Skelett*: Wer den Hinweis beim Freigeben auf `""` setzt, macht aus einem
bedienbaren Eintrag einen stummen.

**Und die Vorschau geht denselben Weg wie beim Operationsdialog** (§18.7):
`counterpart.drafts_for` sagt, was entstünde, `Session.preview_async` rechnet
es im Arbeiter, `_show_preview` zeigt es. Der Dialog rechnet dabei nichts — er
meldet über `valuesChanged`, dass Paar oder Maß sich bewegt haben, und der
Zeitgeber im Fenster entprellt auf 300 ms. Ein Paar ist die Lage, in der eine
Vorschau am meisten wert ist: Ob die zwei Hälften zueinander passen, sieht man
ihnen an und den Zahlen nicht. `_clear_preview` steht im `finally` — die
Vorschau gehört dem Dialog und geht mit ihm, gleich ob übernommen oder
abgebrochen.

**Und das Band über dem Bild sagt, was die Vorschau nicht zeigen kann.**
`Session.preview_async` nimmt neben `then` einen zweiten Rückruf
`explained`: Wirft die Operation, oder hält die Kette an einem Befund an,
kommt vor dem `None` der Satz aus dem Kern — `_PreviewWorker.explained`,
gelesen von `_reason_of` (das übersetzte Detail, sonst der Titel) und
`_stop_reason` (der Befund mit der `op_id` des Halts, derselbe, den
`evaluate._why_it_stopped` fürs Protokoll liest). `MainWindow._preview_explained`
legt ihn ins Band („Keine Vorschau: …"), `_preview_reason` merkt ihn, damit
das folgende `_show_preview(None)` ihn stehen lässt. Eine Differenz ohne
`changed` heißt „am Volumen ändert sich nichts", und `_preview_busy` sagt
nach 0,2 s ohne Ergebnis „wird gerechnet …" (§2.8). `PreviewBanner.note`
bricht um und `place()` deckelt die Breite am Bild — ein Grund aus dem Kern
ist länger als eine Zeile. Die Regel dazu steht in `oberflaeche.md` („Ein
Haken in einer Formularzeile antwortet auf der ganzen Zeile").

**Und wo die Zahl „nichts" sagt, zeigt das Bild trotzdem etwas** (RM-169):
Trägt ein Eintrag der Differenz `retriangulated` oder `recoloured`, verbirgt
`Viewport._cover_body` den eigenen Aktor des Körpers (`_covered`) und legt den
Körper danach an seine Stelle — mit Kanten in der Farbe von „Hinzugekommen"
bei neuen Dreiecken, mit seinen Slotfarben (`_slot_colours`, dieselbe
Auflösung wie beim Szenenaufbau) bei neuen Farben. **Der Deckel ist der Körper
fürs Zeigen** (`_cover_actors`): `_world_at` sucht ihn mit, denn der eigene
Aktor ist verborgen, und ein Klick, der nur `_actors` fragte, traf unter der
Farbvorschau nichts — *Filament auf eine Fläche* bekommt seine zweite Fläche
über genau diesen Klick. Seine Dreiecksnummer gilt bei gleichen Dreiecken
(Farbe), bei neuen nicht. Er geht denselben Weg wie der Körper in
`_apply_scene` — Schnittebene, Opazität und Kanten der Darstellungsart
(`_body_opacity`) — und liegt nicht auf einem ausgeblendeten Körper oder
einer fremden Platte (`_in_view`), nicht unter einer Analysekarte und nicht
über `DISPLAY_DECIMATION_ABOVE`; dort trägt das Band den Satz.
`_redraw_difference` zeigt Verborgenes zuerst wieder, also auch beim Halten
der Leertaste und beim Schließen. Das Band sagt „das Netz ändert sich, das
Volumen nicht" oder „nur die Farbe ändert sich". Zwei weitere Gründe reisen
über `explained`: die
erste **Warnung** der vorgeschauten Schritte, wenn die Differenz leer bleibt
(`Session._warning_of` — *Textur in Filamente* ohne Farbinformation), und die
**Rückfrage**, an der die stille Vorschau anhält (`_QuestionPending` aus
`_no_questions` — *Merkmal entfernen* an einer gesenkten Bohrung). Beide
standen bis zum 14.09.2026 als „am Volumen ändert sich nichts" im Band.

**Und was ein Körper mitbringen muss, fragt das Menü vorher** (RM-168):
`_reason_locked` fragt als letzte Stufe `labels.body_requirement` mit den
Fakten aus `_body_facts_of_selection` — geschlossen, Stücke, Hohlraum, einmal
je Körper und Auswertung gerechnet (`_body_facts`, Schlüssel ist
`result_generation`), am Körper, den die Operation bekäme (`_first_chosen`:
Klickreihenfolge wie `inputs_for`, nicht Baumreihenfolge). Die Angabe steht
im Register (`requires_body`), die Regel in `operationen.md`.

Ein `InstallDialog` lässt eine begonnene Installation beim Schließen
geordnet auslaufen und zeigt diesen Zustand. Er beendet nur das Warten auf
einen gestarteten Fremddienst; den Dienst selbst besitzt Solidon nicht.
`MainWindow.wait_for_workers` bezieht alle eigenen Installationsdialoge ein,
damit auch das Schließen der ganzen Anwendung denselben Vertrag einhält.

**Bausteine setzt man auf eine Fläche, nicht in ein Loch.** Der Knopf
*Bausteine* am Fuß des Auswahlfensters steht nur ohne Merkmal und an einer
gewählten Fläche (`SelectionOperations.set_context`); an einer Bohrung, einer
Verrundung oder einem Zapfen führte er in einen Katalog, aus dem nichts an
diese Stelle passt — unter einer Liste, für die man erst scrollen muss.

Merkmalsanalyse und Bausteinkatalog bleiben getrennte Wege an der rechten
Seite. Das Auswahlfeld führt zu beiden und baut keines von beiden nach. Seine
Operationen stammen aus dem Operationsregister — Körperoperationen über
`body_operations`, die Merkmalshandlungen über `feature_operations` aus
demselben `applies_to`, aus dem der Doppelklick im Baum seine erste passende
Handlung nimmt; eine Handlung mit `also_on_body` steht an beiden Stufen und
bekommt einen Knopf. An einer angeklickten Kante stehen neben den
`EDGE_OPERATIONS` die `EDGE_VARIANTS` des Kerns (*Verrunden mit Verlauf*). **Das Auswahlfeld ist für diese Handlungen der einzige Ort**
(`PANEL_CATEGORIES`, `.claude/rules/oberflaeche.md`): Die Menüleiste trägt
nur noch, was keine Auswahl braucht, und das Kontextmenü an Körper und Merkmal
keine Operationen. Sie verwenden dieselbe Freigabe wie Menü und Palette und
gehen ausnahmslos durch `MainWindow.launch_operation`, damit Gesten-Editoren
und Undo erhalten bleiben. Seine Gruppen sind einklappbare Abschnitte
(`panels.collapsible`), sein Knopf *Bausteine* ein Hauptknopf.

Welche Handlungen **vorn** stehen, beantwortet `quick_names(bodies,
feature_kind)`: bei mehreren Körpern die Booleschen, bei einem einzelnen
Bohren, Aushöhlen und Teilen, an einem gewählten Merkmal die seiner Art —
das Merkmal hat Vorrang vor der Menge. *Merkmal vervielfachen*
(`pattern_feature`, P6.7) steht an jeder Art, die es annimmt, vorn: Es hat
keine gemessenen Werte, die das Merkmalfenster als Felder zeigen könnte, und
steht deshalb nicht in `ACTION_ORDER`, sondern öffnet den Dialog mit dem
gewählten Merkmal in `at_features`. Die Knöpfe dieser Lagen entstehen
einmal (`all_quick_names`) und werden nur ein- und ausgehängt; was oben
stehen kann, steht nicht auch in der Suchliste darunter. Was am gewählten
Merkmal nichts Sinnvolles tut, obwohl seine Art es trägt, nennt der Kern
(`perceive.actions.not_offered_at`, *Senken* an einer Verengung);
`set_context(left_out=...)` nimmt es vorn und aus der Liste.

**Was aus einem Baustein kam, meint den Baustein.** Ein Schlüsselloch
bringt zwölf Merkmale mit — zwei Bohrungen, **zehn Verrundungen** und die
Fläche, auf der es sitzt. Die Verrundungen tragen für sich keine einzige
Handlung (`REGISTRY.for_feature("fillet")` ist leer), und an der Fläche
standen die Handlungen einer Fläche: Bohren, Tasche, Fläche ziehen. Wer
eine Schlitzkante anklickt, hat aber das Schlüsselloch gemeint (Befund
Robert, 10.09.2026). `MainWindow.part_step_of` fragt deshalb die
Provenienz und die Kategorie des Schritts — `parts`, nicht eine Namensliste,
die beim nächsten Baustein schwiege —, und `FeaturePanel.show_part` zeigt
statt der Merkmalszeilen die drei Handlungen des Bausteins: Maße ändern,
verschieben, entfernen (`perceive.actions.part_actions`).

**Und sie gelten dem Schritt, nicht dem einzelnen Merkmal.**
`resize_feature` auf die runde Tasche gesetzt bohrte sie auf und ließe den
Schlitz stehen. Was die Größe wirklich ändert, ist die Schraubengröße im
Schritt. Die Werte kommen von dort und gehen dorthin zurück
(`stepChangeRequested`, `stepRemoveRequested`) — **nicht** über
`operationRequested`, das bei jeder Korrektur ein zweites Schlüsselloch
über das alte legte. Aus gemessenen Maßen ließe sich ohnehin nichts
zurückschreiben: Aus zwei Durchmessern käme keine Schraubengröße zurück.

**Im Baum gilt dasselbe.** Das Bausteindach wählt seine zwölf Kinder mit
(`selected_features`), und zwölf Merkmale sind für eine Passung zehn zu
viel: Dort stand „Wählen Sie genau zwei aus", wo jemand gerade ein Ding
angeklickt hatte. `_common_part_step` fragt, ob die **ganze** Auswahl aus
einem Schritt stammt — eine Bohrung des Schlüssellochs und eine fremde
daneben sind zwei Dinge und kein Baustein.

**Und im Bild gilt es auch** (14.09.2026). Ein Zug am Griff eines
Bausteinmerkmals — `featureMoved`, `featureTurned`, der Körpergriff über
`transformDragged` und die Bewegen-Leiste — läuft zuerst durch
`MainWindow._move_the_part`: Versatz auf `x`/`y`/`z` des Schritts, Drehung
um den eigenen Anker über die Rundreise `placement_transform` →
`placement_values_of` (dieselbe wie am Griff der Vorschau eines
Grundkörpers), an einem benannten `at_feature` nur um dessen Achse. Bis
dahin wurde daraus ein `move_feature` auf die Tasche des Schlüssellochs,
und der Schlitz blieb stehen. Damit der Griff auch an einer Verrundung oder
einem Gewinde hängt, die für sich keine Operation tragen, fragt
`Viewport.gizmo_feature` das Fenster über `moves_as_a_part` — eine
schwache Frage, keine gebundene Methode (`wartezeit.md`). Während des Zugs
wandert der ganze Baustein und wird neben der Fläche rot (RM-174, `griffe.md`).
Seit dem 16.09.2026 gilt das auch an einer **Fläche** des Bausteins
(`gizmo_target` kennt dort kein Press/Pull), bei gewähltem **Dach** im Baum
(`_move_the_part` fragt `_common_part_step`, wenn `selected_feature`
schweigt) und für eine an einen Parameter **gebundene** Achse: Der Versatz
wandert in den Ausdruck (`expressions.shifted`, `=@staerke + 5`) statt
abgelehnt zu werden. Ein gewähltes **Dach** trägt den Griff an einem seiner
Merkmale (`_part_grip_anchor` → `Viewport.set_part_grip`), und die **Bohrung**
eines Bausteins bekommt ihn ohne *Im Bild einstellen*. **Entf** an
Bausteinmerkmalen nimmt den Schritt (`_delete_the_chosen_feature`), an einem
Merkmal mit Operation dessen Zwilling, und an einer Fläche oder einem Merkmal
ohne Handlung den Körper — mit Ansage und Strg+Z (Regel in `oberflaeche.md`);
der Filament-Schnellwähler färbt an einer Bausteinfläche alle
Flächen des Bausteins (`_part_faces_of_selection`, `_filament_targets`). Ein
**gebundener** Wert zeigt im Merkmalfenster sein Ausdrucksfeld
(`FeaturePanel._part_fields`), statt den Aufbau der Liste abzubrechen.

**Ein Baustein bleibt gewählt, wenn *Maße ändern* seine Merkmale tauscht.**
`_change_part_step` merkt den Schritt (`_part_to_keep`), und
`_reselect_the_part` wählt nach der Auswertung eines seiner Merkmale, wenn
der Baum das angeklickte nicht mehr fand — sonst stand rechts das leere
Fenster.

**Und ein Baustein für Bohrungen sitzt in der gewählten Bohrung.**
`PlacementFlow._begin_on_a_face` fragt vor der Fläche `_hole_to_seat_in`:
Trägt der Dialog eine Bohrung als `at_feature` und gehört der Baustein in
Bohrungen (`PartSpec.at_hole`), liefert `placement.seat_of` die Mündung —
der Weg von *Bohrung ändern* —, der Satz sagt „Sitzt in der Bohrung", Griff
und Klick gelten wie auf der Fläche. Ein Schraubenloch folgt der Bohrung
nicht.

**Und was das Merkmalsfenster darüber schon als Feld zeigt, steht hier gar
nicht.** `_shown_as_fields()` liest `perceive.actions.ACTION_ORDER` — dieselbe
Liste, aus der `FeaturePanel` seine Zeilen baut —, und `quick_names` wie
`_fits_the_level` schneiden sie heraus. An einer Bohrung standen sonst
*Bohrung ändern*, *Merkmal drehen* und *Merkmal verdoppeln* zweimal im selben
Fenster: oben mit dem gemessenen Wert und einem Knopf, darunter als Knopf, der
denselben Weg noch einmal anbietet. Der Kegel hat deshalb eine eigene Zeile in
`QUICK_FEATURES` — seine einzige verbleibende Handlung ist *Senken*, und ohne
den Eintrag stünde sie an keiner der beiden Stellen.

### Ein Merkmalklick baut nicht neu, was schon steht (RM-204)

`FeaturePanel.show_feature` und `show_edge` halten die Zeilen des vorigen
Merkmals zurück (`_keep_rows_for_reuse`) und vergeben sie an Handlungen
derselben Signatur (`_row_signature`: Operation, Feldnamen, -arten und
Auswahlwerte; nie bei Schritt, `elsewhere` oder Ausdrucksfeld). Eine Zeile ist
ein `_ActionRow`; ihre Wege (`_run_row`, `_take_row`, `_row_in_view`,
`_row_values`) lesen Schlüssel, Operation und Felder beim Aufruf aus der Zeile,
nicht beim Bau. Werte, Grenzen und Herkunft schreibt
`configure_feature_field` (Signale geblockt, Kurzhilfe vorher geleert),
Beschriftung, Namen, Erklärung und Merker `_fill_row`; was keiner nimmt, geht
mit `_drop_spare_rows`. Die Fokuskette wird nach einer Wiederverwendung neu
gezogen (`_settle_row_order`, Halte über `_focus_stops` ohne Innenleben).
Die Kernauskunft (Hohlraumkette, Handlungen, Geschwister) merkt
`_answers_for` je Merkmal für einen Körper und eine Merkmalsliste; gerechnet
wird sie in `feature_answers` (rein, ohne Qt). **An einem großen Körper rechnet
sie der Arbeiter** (`MainWindow._answer_in_worker`, ab
`ANSWERS_IN_WORKER_FROM` Dreiecken, an der Arbeiterkopie unter ihrem Schloss):
Bis die Antwort da ist, zeigt `show_pending` Name, Maß und einen Satz, keine
Zeile zum Klicken; `remember_answers` legt sie ab, und der Aufbau läuft mit
`allow_worker=False` noch einmal. Die Antwort eines abgelösten Arbeiters wird
gemerkt, solange die Auswertung dieselbe ist; gebaut wird nur, was noch gewählt
ist. Jeder Aufbau endet mit `_lay_out_now` — die Höhe des Fensters pflanzt sich
sonst über mehrere Ereignisrunden fort, und die Malrunde käme dazwischen
(Regel in `ansicht.md`, „Die Ansicht bestellt ihr Bild").
Sichtbarkeit wechselt nur über `_set_shown`; `clear(rebuilding=True)` lässt
die Knopfzeile bis `_settle_apply` stehen. Verborgen wird **ausdrücklich**:
Eine eben ins sichtbare Layout gesetzte Zeile meldet `isHidden()`, und Qt
zeigt sie danach mit `_q_showIfNotHidden`, wenn niemand sie ausdrücklich
verborgen hat (`WA_WState_ExplicitShowHide`). Ein Test vergleicht ein
wiederverwendetes Fenster mit einem frisch gebauten Zustand für Zustand
(`test_feature_panel.py`, `_panel_state`).

Die Maßgruppe startet erst, wenn das Fenster auf „Messen" steht
(`set_measuring` vor `PlacementFlow.start`): Der Start blendet Felder über der
Grafikfläche ein, und das malt sofort. Ihre Karte bleibt verborgen, solange
die Trägerfläche am Merkmal gerechnet wird (`PlacementFlow._seat_waits`), und
erscheint an ihrem Platz, nicht erst am Rückfallplatz oben rechts.
Leiste, Maßkarte, Kanten-, Mitten- und Tiefenmaß und die Maßtinte gehen von
Fluss zu Fluss (`_build_floating` einmal, `_wire_floating` je Fluss,
`_park_floating` beim Abbau, `_take_parked_floating` beim nächsten Aufbau);
`start` baut dabei einmal auf (`_redraw_held`), und `end_quiet_placement`
räumt den Rücklauf aus dem eigenen `dispose` nicht ein zweites Mal
(`_ending_quiet_placement`).

Die Klickkette davor meldet einmal: `ObjectTree.select_feature` leert die
Auswahl geblockt, und `MainWindow._on_features_selected` baut an Bohrung und
Senkung nicht ein zweites Mal, was `featureSelected` derselben Runde schon
gebaut hat (`_fields_this_round`, `FeaturePanel.serial`).

### Die Fase an einer Kante: Art, Felder, Seiten im Bild (P6.2)

Die Kantenzeile kommt aus `perceive.actions.edge_actions`: vorn das Maß aus
`EDGE_OPERATIONS`, dahinter `EDGE_SHAPE_FIELDS` (bei *Fase anbringen* Art,
zweiter Abstand, Winkel, *Seiten tauschen*). `ActionField.depends_on` reicht
die Bedingung des Schemas durch; `FeaturePanel._follow_conditions` blendet
Feld **und** Beschriftung aus, solange `registry.params.inactive_dependency`
nein sagt — beim Füllen der Zeile und bei jeder Meldung vor `valuesChanged`.
Gesperrt wird dort nicht (das gehört `_settle_lock`), und der Wert bleibt
stehen. `show_edge(parameter_values=…)` gibt jeder Kantenzeile die
`ValueField`s des Dialogs (Ausdrücke, Einheit), je Zeile über
`_texture_fields`, weil Verrunden und Wulst beide einen `radius` führen;
Kantenzeilen werden deshalb nicht wiederverwendet (RM-204 oben).

Im Bild zeigt `Viewport.show_chamfer_sides(values, parameter_values)` an der
gewählten Kante zwei Marken aus `edge_ops.chamfer_marks`: je Fläche eine
Maßlinie bis zur Berührlinie, `chamfer_mark_texts` „1 · …" (Bezugsfläche,
breiter, bei Winkel mit „· 30°") und „2 · …". Die Seitenauskunft merkt
`_edge_sides` je Auswertung; die Marken folgen `_redraw_edge_patch`, dem Zug
am Körper und fallen mit der Kante (`select_edge`, `_drop_edge`). Ein Klick
auf die äußere Hälfte einer Marke (`_chamfer_mark_at`, vor Kante und Fläche)
sendet `chamferSidesSwapRequested`; `MainWindow._swap_chamfer_sides` schaltet
`FeaturePanel.toggle_field("chamfer_edges", "flip_sides")` — derselbe Haken,
dieselbe Vorschau. `MainWindow._follow_chamfer_sides` (aus
`_on_handling_armed` und `_on_feature_values_changed`) versorgt die Marken und
nennt beide Flächen als Hinweis in der Statuszeile („Fase: Fläche 1 oben,
Fläche 2 rechts", `_face_side`); `_update_actions` nimmt den Hinweis weg,
sobald keine Marke mehr steht. Tests: `test_feature_panel.py` (Zeile,
Bedingungen, Fokuskette, Namen), `test_ui.py` (Ende zu Ende mit Klick,
Übernehmen, Undo), `test_viewport_decisions.py` (Beschriftung).

### Das Merkmalsfenster hat einen Knopf, nicht fünf (10.09.2026)

Vier bis fünf Handlungen stehen an einer Bohrung untereinander, und jede trug
ihren eigenen Knopf: fünf Zeilen, die fünfmal dasselbe sagten. Es ist jetzt
**einer unten**, und er führt die Handlung aus, an der zuletzt jemand einen
Wert geändert hat (`FeaturePanel._arm`, `_runs`). Vier Entscheidungen daran:

* **Er heißt „Übernehmen"** und trägt nicht den Handlungstitel — der wechselte
  sonst mit jedem Klick ins nächste Feld. Welche Handlung gemeint ist, steht
  über ihm; für den Bildschirmleser trägt er sie als zugänglichen Namen (§19.1).
* **Er steht wirklich unten.** Er entsteht beim Aufbau des Panels und liegt
  damit vor allem, was `show_feature` später einfügt; `_settle_apply` hängt ihn
  und den Haken ans Ende, nachdem alle Zeilen stehen.
* **Der Haken „Auf alle N gleichartigen anwenden" steht direkt darüber** — auch
  er einer statt vier, und die Zahl wechselt mit der scharfen Handlung, denn
  die Gruppen sind je Handlung verschieden. Ohne Geschwister ist er weg statt
  ausgegraut, und er verliert dabei seinen Haken: ausgeblendet auf „an" griffe
  er wieder, sobald eine Handlung mit Gruppe drankommt.
* **Er trägt die Akzentfarbe** (`style.make_primary`) samt der Schriftfarbe
  darauf, und halbfett daneben — Bedeutung nie allein über Farbe (Regel 18).

**Die Erklärung sitzt am „i" neben der Überschrift.** Drei Zeilen Fließtext je
Handlung füllten das Fenster; der Absatz steht jetzt im Tooltip eines kleinen
Zeichens (`_explain`, `_extend_explanation`). Drei Quellen speisen ihn in
dieser Reihenfolge: der Satz zur Lage (`note`), der Grund der Handlung, und der
`doc`-Satz aus dem Register — der letzte trägt immer, denn jede Operation hat
einen (Regel 4). **Ein `QToolButton` und kein `QLabel`**: Ein Label zeigt
seinen Tooltip nur, solange die Maus genau darauf steht, und achtzehn
Bildpunkte trifft niemand zuverlässig. Für den Bildschirmleser hängt der Text
an der **Überschrift** — ein Tooltip wird nicht vorgelesen.

**Und ein Strich trennt die Handlungen** (`style.rule`). An einer Bohrung
folgen auf drei Zahlenfelder wieder drei; wer nicht auf die Überschriften
sieht, liest sie als eine Reihe.

**Eine Beschriftung, die nicht in ihre Spalte passt, bricht um** — Qt schnitte
sie sonst zu „Bohrung versch…", und ein abgeschnittener Titel nennt seine
Handlung nicht mehr. `_wrap_label` misst gegen die Schrift, mit der wirklich
gezeichnet wird, und holt das Beiwerk des Knopfes aus der Differenz zu seinem
Wunschmaß; höchstens zwei Zeilen, darunter bleibt Qts Auslassung. Der
ungebrochene Titel steht als `operationTitle` am Knopf, weil `text()` sich
ändert und die Suche darunter den ganzen Titel braucht.

Die Kopfzeile nennt keine globale Materialzusage. Sie liest Körpermaterialien
und die über `mesh.slot_indices` tatsächlich belegten Materialslots der
aktuellen Auswertung, unterscheidet Slotname, Materialart und Farbcode und
zählt mehrere Filamente. Eine leere Zuordnung bedeutet vollständig Slot 0;
ungenutzte Definitionen zählen nach einem Übermalen nicht weiter. Kurztext und
Tooltip teilen dieselbe Erhebung, damit große Netze ihre Flächenzuordnung nur
einmal je Aktualisierung durchlaufen. Bei mehreren steht die
klare Anzahl in der knappen Leiste, die vollständige Liste im Tooltip und im
zugänglichen Namen. Der Druckerknopf öffnet die Druckeinstellungen des offenen
Projekts. Ein Wechsel
dort behält Projektmaterial, Slotprofile, Farben und SlotOverrides; Vorgaben
für neue Projekte sind ein eigener Weg in den Einstellungen.

**Erscheinung**

`style.py` (Stylesheet, Typografie-Skala, Abstandsraster, §19.3) · `theme.py`
(hell und dunkel) · `window_chrome.py` (die Titelleiste trägt die Farben der
Anwendung — Windows malt sie weiter, es bekommt nur gesagt, in welcher Farbe;
ein Wächter am Ereignisstrom, damit kein Dialog vergessen wird) ·
`palette.py` (**Farbe trägt nie allein Bedeutung**,
§19.1) · `icons.py` · `motion.py` (Bewegung an einer Stelle, nicht an
zwanzig) · `labels.py` (kurze Texte, auf die sich mehrere Teile einigen; dazu
`wheel_needs_focus`, damit das Rad ein Feld erst mit Fokus dreht — Regel in
`oberflaeche.md`)

Das Anmelden des Fensterchroms ist idempotent: Beide Startwege teilen den
Wächter der Anwendung, sodass ein Ereignis nur einmal nachzeichnet.

Beim Ablösen einer Auswahlblende übernimmt der Renderer alle noch offenen
Farbziele der vorigen Blende. Sonst bleibt bei einer schnellen
Mehrfachauswahl der zuerst gewählte Körper auf seiner Zwischenfarbe stehen.
Eine unveränderte Auswahl startet keine neue Animation.

`MainWindow.release` wartet auf Arbeiter und trennt die Sitzung. Der
pygfx-Renderer hat eine eigene Lebensdauer: Anwendung und Tests schließen ihn
ausdrücklich, solange seine Canvas lebt, und stellen erst danach Qts
aufgeschobene Fensterlöschung im Hauptthread zu. Ein Test-Pin schützt ein neu
gebautes Hauptfenster oder einen einzelnen Viewport nur bis zu genau diesem
geordneten Teardown; Fenster werden nicht über mehrere Tests angesammelt.
Der modale Bausteinkatalog hält seine Vorschau-Zeitgeberkette mit `release()`
an, bevor `_exec_catalog` im `finally` seine Löschung vormerkt. Das gilt auch
beim Abbrechen: Ein eingereihter gebundener Rückruf hält sonst die Pythonhülle
des bereits nativ gelöschten Dialogs fest.
Eine `WorkerLeash` hält ihren Fensterbesitzer nicht zurück: Der Besitzer hält
die Leine bereits, alle Zeitgeber gehören dem langlebigen Keeper und die
Fertigrückrufe verwenden schwache Verweise. Damit entsteht um Qt-Fenster kein
Python-Zyklus, dessen Abbau in einen späteren Worker- oder Widgetaufbau fällt.
Fertige Arbeiter trennen ihre eigenen Signale einschließlich aller Überladungen
über Qts Metamethoden; `started` und `destroyed` bleiben verbunden. Die Trennung
benötigt keine globalen Warnfilter und fängt keine Warnung eines anderen Threads ab.

**Hilfe und Bedienung**

`manual_window.py` · `tour.py` · `shortcuts_window.py` ·
`shortcut_schemes.py` (zwei Belegungen, eine Quelle) · `command_palette.py`

Die Befehlspalette trennt Titel und Kürzel nur in der ersten Zeile. Ein
Sperrgrund oder erklärender Satz bleibt darunter in der Titelspalte; das
rechtsbündige Kürzel behält die Höhe der ersten Zeile.

**Navigationstasten gehören dem fokussierten Inhalt.** Der gemeinsame
`NavigationKeys`-Filter schützt Pos1, Ende, Bild auf und Bild ab in Listen,
Bäumen, Text- und Zahlenfeldern sowie Reglern (`QAbstractSlider`). Beim
Fokuswechsel zur Ansicht gelten wieder die Fensterbefehle; Ziffern der
Darstellungsarten bleiben auch im Inhalt Fensterbefehle.

Der Objektbaum wertet `customContextMenuRequested` in den bereits gelieferten
Viewport-Koordinaten aus. Eine zweite Umrechnung verschiebt den Treffer um die
Kopfzeilenhöhe.

**Ein Kontextmenü gehört seinem Klick.** Objektbaum, Parameterleiste, Verlauf,
Prüfbericht und die Ansicht bauen es je Rechtsklick neu, als Kind ihres Panels
— ohne `deleteLater()` nach dem `exec` bleibt jedes liegen, samt seiner
Aktionen und der Rückrufe daran (gemessen: dreißig Rechtsklicks, dreißig
zusätzliche `QMenu`-Kinder). Weggeräumt wird wie überall mit `hide`/
`deleteLater` und nie über `setParent(None)`. Text- und Zahlenfelder behalten normale Zeicheneingaben vor
fensterweiten Einzeltasten-Kürzeln; die Linux-Auslieferung verwendet dafür den
geprüften X11-/Xwayland-Pfad.

Beim Tippen im Rückmeldefeld prüft die Sendefreigabe nur Bogen und Nachricht.
Protokoll und Sitzungsanhang entstehen für Vorschau oder Sendung, nicht pro
Tastendruck; `ticket()` verwendet denselben zusammengesetzten Nachrichtentext.

Der Selbstversand des Supportberichts verwendet im Flatpak asynchron
`Email.ComposeEmail` über QtDBus und übergibt Betreff und Inhalt unkodiert als
Portalwerte. Außerhalb des Flatpaks bleibt `QDesktopServices` mit `mailto:`.
Der Qt-6.11-Pfad über eine vorab kodierte `mailto:`-Adresse ist ausgeschlossen,
weil `PrettyDecoded` Prozentfolgen erneut auswertet.
Vor dem Methodenaufruf abonniert der Dialog `Request.Response` über seinen
`handle_token`. Erfolg, Abbruch und Fehler beenden den Ablauf; beim Schließen
trennt der Dialog die Signalverbindung und schließt den Portal-Request.

**Einstellungen** `settings.py` · `survey.py` (Bogen, Nutzungsuhr und die zwei Einladungen über der Ansicht: `SurveyNotice` und `SupportNotice` auf der Basis `ViewNotice`, die die oberste freie Stelle zwischen den gemeldeten Karten sucht — `keep_clear_of`, `spot`)

## Grenzen

- **Keine feste Zeichenkette** — alles über `tr()` (Regel 20).
- **Das Handbuch beantwortet fremde Ressourcen mit leeren Daten.** `None`
  würde Qts eigenen Dateileser freigeben. Nur `figure:` wird über den lokalen
  Abbildungskatalog aufgelöst; Links bleiben eine getrennte Klickentscheidung.
- **Eine Kartenbewegung endet mit ihrem Qt-Objekt.** Die Animation verwendet
  `DeleteWhenStopped`, auch beim Ersetzen einer noch laufenden Bewegung.
- **Sprachabhängige Qt-Formate lesen die aktive Solidon-Sprache.**
  `QLocale()` ohne Argument folgt der Prozesssprache; für ausgeschriebene
  Datumswerte deshalb `QLocale(get_language())` verwenden und alle
  ausgelieferten Sprachen am gerenderten Fenster prüfen.
- **Berichtshandlungen lesen ihren Zielkörper aus Befund oder Dokument.** Eine
  aktuelle Auswahl ist kein Ersatz. „Reparieren und erneut versuchen“ steht
  nur am aktuell angehaltenen Netzschritt mit lebenden Eingängen oder an einem
  ausdrücklich benannten, noch vorhandenen Körper. Der Knopf wird nicht erneut
  angeboten, wenn unmittelbar davor bereits alle Eingänge in derselben aktiven
  Transaktion repariert wurden, und sperrt sich beim ersten Klick bis zum neuen
  Ergebnis. Berichtshandlungen stehen vollbreit untereinander, damit auch
  längere Übersetzungen in der schmalen Karte vollständig bleiben.
- **Gleiche Meldungen werden eine gezählte Zeile, die Zahl davor in
  Klammern** (Robert, 11.09.2026; `REPORT_BUNDLE_FROM = 2`). Gleiche Kennung,
  Schwere, Meldung, Herkunft, Schritt und Handlungen bilden das Bündel —
  Körper, Ort, Merkmale und Werte **nicht mehr**: „(9) Ausrichtung über die
  Schichtanalyse gesucht." statt neun Zeilen. Was die Mitglieder unterscheidet,
  trägt die Zeile anders: die Körper als Liste (`_BODIES_ROLE`), Name und
  Werte je Mitglied im Tooltip, ein gemeinsamer Körper sichtbar an der Zeile.
  **Der Klickvertrag bleibt**: Eine Zeile über mehrere Körper wählt beim Klick
  alle (`bundleActivated` → `_on_bundle_activated` → `ObjectTree.select_objects`),
  nie den ersten zufälligen; ihre Handlung fragt, für welche Körper sie
  gelten soll (`BodyChoiceDialog`) — und geht dann einen von drei Wegen
  (`_run_action_for`): eine **Operation** wird ein Schritt je Körper in einer
  Transaktion (`actionOnBodies`), eine Handlung **an einem Körper**
  (`_PER_BODY_ACTIONS`) läuft je Körper mit dessen eigenem Befund
  (`_MEMBERS_ROLE`, nie mit dem des ersten), alles andere läuft einmal. Sie
  trägt keinen Ort und keine Merkmale, wo die Mitglieder verschiedene haben;
  ohne Körper (die Gegenprobe aus dem G-Code für Material und Zeit) heißen
  ihre Mitglieder im Tooltip *Einträge*, nicht *Objekte*. Bei verlorenen
  Formdetails zählt der Kern bereits je Körper und Schritt: Zeile, Tooltip
  und Bildschirmleser zeigen dieselbe Summe dieser Mengen. Die Kopfzeile
  zählt weiterhin die Befunde. Der Kerntext bleibt kanalneutral.
- **Und der Objektbaum bündelt nach derselben Regel wie der Prüfbericht.**
  Erkannte Merkmale mit gleichem Namen **und gleichem Maß** stehen ab
  `BUNDLE_FROM` unter einem zugeklappten Dach („Hohlkehle (17) · R13,98 mm").
  Der Name allein reichte dafür nicht: Ein Schlüsselloch bringt zehn
  Hohlkehlen mit *verschiedenen* Radien mit, und die verschwanden hinter einer
  Zeile, die Gleichartigkeit behauptete, wo keine war (Befund Robert,
  09.09.2026). Seit der Schlüssel das Maß enthält, tragen alle Kinder eines
  Dachs dasselbe — deshalb steht es jetzt in der Maßspalte, statt leer zu
  bleiben. Was aus einem Baustein kam, gruppiert
  weiter nach seinem Schritt; die zwei Dächer schließen einander nicht aus.
  Gemessen an `build_tray_v3.step`: 234 erkannte Merkmale, rund fünfzig
  sichtbare Zeilen „Hohlkehle R13,98 mm" untereinander, die die linke Spalte
  füllten und Parameter und Verlauf hinausdrückten. Der Bericht daneben zeigte
  dieselbe Menge längst als eine Zeile. `_restore` klappt das Dach auf, wenn
  das gewählte Merkmal darin liegt — sonst wäre ein Klick im Viewport auf eine
  Verrundung wieder ins Leere gegangen.
- **Ein Bausteindach über einer einzigen Zeile entfällt.** „Schraubenloch mit
  Senkung" trägt genau ein direktes Kind — die Bohrung, an der die Senkung
  schon hängt —, und die Dachzeile wiederholte damit nur, was darunter steht;
  angeklickt meinte sie den ganzen Körper, und im Auswahlfenster standen alle
  Körperoperationen. Der Weg zum Schritt geht dabei nicht verloren: Er steht in
  `Feature.created_by`, und Doppelklick wie „Diesen Schritt ändern" lesen ihn
  von dort, wenn `_STEP_ROLE` fehlt. **Und die Zeile übernimmt den Namen des
  Dachs**: Sie steht dann für den Baustein, ein Klick öffnet ihn rechts, und
  der Verlauf nennt ihn beim selben Titel — als „Sackbohrung 1" hieß eine
  Magnettasche im Baum anders als überall sonst. Die Art steht in der
  Kurzhilfe, die Kennung bleibt
  (`test_a_part_with_one_row_carries_its_own_name`).
- **Ein zusammenhängender Bohrungshohlraum ist ein vollständiger Ast.**
  Bohrung, kegelige Übergänge und zylindrische Senkungen werden in der
  Reihenfolge von `perceive.relations.cavity_chains` ineinander gehängt; eine
  Kette mit drei Flächen darf nicht auf ein Paar gekürzt werden. Der Objektbaum
  fragt die Bulk-Auskunft genau einmal je `SceneObject`, damit die Randringe
  eines großen Netzes nicht für jedes Merkmal neu entstehen. Das
  Merkmalspanel reicht das `MeshData` optional bis `actions_for` durch:
  Aufrufer ohne Netz behalten die bisherige Paar-Auskunft, die Oberfläche mit
  Netz nennt auch bei der vollständigen Kette vorab das gemeinsame Versetzen.
  Sammeldächer zählen nur ihre direkten, freien Merkmale. Untergeordnete
  Senkungen zählen weder zur Schwelle noch zur Beschriftung eines anderen Dachs.
- **Kurzlebige Warnungsmarken sind semantischer Ansichts-Zustand.** Ring und
  Beschriftung im nativen Renderer sind nur die Darstellung. Baut eine
  Analysekarte dieselbe Auswertung neu auf, werden beide aus Punkt, Text und
  Körper erneut gezeichnet, ohne die ursprüngliche Frist zu verlängern. Ist
  der Körper ausgeblendet oder liegt auf einer anderen gewählten Platte,
  bleibt auch seine Marke unsichtbar. Ein neues Auswertungsergebnis verwirft
  Zustand und Aktoren gemeinsam.
- **Keine Bestätigungsdialoge vor rücknehmbaren Handlungen** (Regel 19), mit
  der ausdrücklich gewünschten Ausnahme für das Löschen im Verlauf: Sie
  nennt mitbetroffene Schritte und den Rückweg über Strg+Z.
- **Keine Bedeutung allein über Farbe** — immer eine zweite Kodierung
  (Regel 18).
- **Höchstens neun Menüs, zwölf Zeilen je Menü, acht Werkzeuge, acht Felder
  vorn** — `tests/test_interface_limits.py` zählt nach.
- **Nichts rechnet im Qt-Hauptthread**, was länger dauert als ein Lidschlag
  (§2.8).
- **Der Raumvertrag schaltet keine Laufzeit-Introspektion über Qt-Typen.**
  `overlay.is_room_taker` prüft die vier aufrufbaren Methoden ausdrücklich;
  `isinstance` gegen ein `runtime_checkable Protocol` kann während eines
  Shiboken-Resize unvollständige Typdaten sehen und den Layoutlauf abbrechen.

## Zustandsbindung in asynchronen Bedienwegen

Der Einstellungsdialog hält ungespeicherte Antworten in einem eigenen Entwurf.
Sprachwechsel bauen ihn sofort neu auf und nehmen auch einen vorgemerkten
KI-Hinweis-Reset mit. Speichern übernimmt die Werte; Abbrechen verwirft sie
und stellt Sprache sowie Qt-Katalog des ursprünglichen Fensters wieder her.

Beim Sprachwechsel der ersten Schritte werden Antworten für den Neuaufbau
übertragen. Erst die Annahme setzt `first_run_done`; die Sprachwahl beendet
die Einrichtung nicht. **Schließen, Übernehmen und der Sprachwechsel warten
nicht auf die Programmsuche** — die Halteleine hält den Arbeiter; der alte
Dialog der Sprachschleife geht über `deleteLater`, nicht über `release`.
*Eigenes Modell öffnen …* meldet den Import nur an: `action_first_run` liest
die Datei erst, nachdem der Dialog zu ist und `_adopt_defaults` das Projekt
angelegt hat — sonst ersetzte das leere Projekt den Plan einer großen Datei.

Die Druckerliste steht an drei Orten (Erststart, Einstellungen,
Druckvorbereitung) und wird an allen dreien gleich gebaut:
`first_run.add_printer_choices` ordnet nach Verfahren und Titel,
`group_printer_choices` setzt je Verfahren einen nicht wählbaren, halbfetten
Kopf. Der eigene Drucker fragt die Schichthöhe mit (leer = abgeleitet, der
abgeleitete Wert steht im Feld).

Unerwartete Fehler beim Erzeugen oder Einrichten von ComfyUI verlassen den
Wartezustand als `InternalError`. Die gemeinsame Fehleranzeige verbindet den
Berichtsknopf mit den Fehlerhandlungen des Hauptfensters.

Im Erzeugen-Dialog gehören Fortschrittsbalken und Schritttext dem laufenden
Auftrag. Änderungen an der nächsten Beschreibung sperren weiterhin einen
zweiten Start und überschreiben weder den Fortschritt noch seinen Zustand.

- Quellenarbeiter gehören zu genau einem Projekt und gegebenenfalls zu einem
  beim Start gewählten Zielkörper. Späte Signale dürfen weder einen später
  gewählten Körper bearbeiten noch den Zustand eines anderen Projekts melden.
- `Viewport.sceneApplied` bestätigt die tatsächlich aufgebaute Szene.
  Schnittgrenzen und Kandidatenmarkierungen werden danach synchronisiert,
  nicht schon beim Einreihen des Szenenaufbaus.
- Zuordnungsfragen tragen ihre tatsächliche Zwischengeometrie über
  `Session.announce_question` fadenlokal im bestehenden `AskRequest`.
  Kandidaten sind Merkmale als Paare aus Körper und Kennung — oder Kanten
  als `EdgeTarget` (P1.4c): Token, Körper, Zug und Anzeigefakten. Der
  Dialog zeigt je Token die Kantenzeile (`edge_label`, `AskDialog(labels=)`)
  und gibt das Token zurück; die Ansicht zeichnet den Zug als Linie vor dem
  Material in derselben Kandidatenverwaltung (`Viewport._draw_edge_candidate`),
  beschriftet mit derselben Zeile, die betonte breiter. Die Betonung folgt der
  markierten Zeile über `weak_slot(..., forward=True)` — ohne `forward`
  verwirft der Empfänger die Signalargumente, und die Betonung blieb bis zum
  20.09.2026 auf der ersten Zeile stehen.
  `temporary_preview` zeigt sie ausschließlich im Viewport; Dokument,
  Bericht, Verlauf und `last_result` bleiben auf dem gültigen Stand.
  Projektgeneration, Arbeiteridentität und Abbruch binden Frage und Antwort.
  `questionInvalidated` schließt eine bereits offene Auswertungsfrage nach
  Abbruch oder eingereihtem Nachlauf. Die Gültigkeitsprüfung vor und nach
  dem Dialogaufbau schützt auch eine frühere Entwertung; ein bereits
  gesetztes Antwort-Ereignis geht vor dem Arbeiter-Warten nicht verloren.
  `AskDialog.set_ready` sperrt Auswahl, Enter und Doppelklick bis zur
  aufgebauten Kandidatenszene; Abbrechen bleibt erreichbar. Danach bekommt
  die Liste den Fokus zurück: Während des Aufbaus lag er auf *Abbrechen*,
  dem einzigen Knopf, der ging, und Enter verwarf die Frage (21.09.2026;
  der OK-Knopf ist seither der Hauptknopf). Der Frageweg
  räumt Markierungen und Signalbindungen ab und stellt vor `reply` die
  aktuelle gültige Szene wieder ein. Projektwechsel legen keine alte Szene
  zurück; Fensterabbau gibt wartende Fragen vor dem Warten auf Arbeiter frei.
  Auch ein Ansichts- oder Dialogfehler beantwortet zuerst mit Abbruch und
  nutzt anschließend die bestehende Fehleranzeige. Waisenfragen behalten
  ihren bisherigen Ergebnisweg.
- Die Merkmals-Sammelwahl stammt aus `relations.alike_for_actions`: ein
  gemeinsamer Aufruf pro Auswahl liefert getrennte Gruppen je Handlung.
  Das Panel zeigt deren Belege und ungeklärte Zuordnungen; vor Anwendung wird
  die Gruppe am aktuellen Zustand erneut geprüft. Ein Schritt pro kanonischem
  Ziel bleibt zusammen eine Transaktion.
- Eine Normauskunft über eine Bohrungskette richtet sich nach dem engsten
  Abschnitt. Das Panel benennt Aufweitungen und verwendet im Hinweis dieselbe
  lokale Zahlenanzeige wie im Maßfeld. Unsichere Zuordnung wird erklärt, nicht
  als unbeantwortbare Frage formuliert.
- Druckergebnisse und laufende Druckaufträge tragen den Kontext aus Szene,
  Platte, Druckeinstellungen und Slicerprofilen. Änderungen entwerten die
  Ausgabe auch dann, wenn das fertige Arbeitersignal bereits eingereiht ist.
- Druckempfehlungen analysieren genau die gewählten Platten im tatsächlichen
  Schichtraster. Der kurzlebige Auftragsschnappschuss bewahrt keine Messung
  über Änderungen an Szene oder Raster hinweg. Angenommene Filamentwerte
  werden als identitätsgebundene Slotüberschreibung aus dem effektiven Profil
  aufgebaut; unberührte Herstellerwerte und ausdrückliche Abwahlen bleiben
  erhalten. Fehlende Messwerte werden nicht als passende Einstellungen gezeigt.
  Nicht übertragbare Filamentvorschläge bleiben mit Grund sichtbar, ohne
  Übernahmemöglichkeit. Fortschritt, Fehler und Abbruch prüfen dieselbe
  Anfragekennung wie der erfolgreiche Abschluss.
  Eine passende Überhangkalibrierung wird über `profiles.for_process` auf
  die tatsächlichen Druckwerte bezogen. Bei mehreren Materialien zählt für
  die gemeinsame Körperanalyse der strengste Winkel. Der Messwertspeicher
  enthält diesen Winkel und verwirft Ergebnisse bei geändertem Grenzwert.
- Die automatische G-Code-Gegenprobe vergleicht mit dem im Arbeiter
  eingefrorenen `SliceComparison` des ausgegebenen Auftrags. Sie liest dafür
  weder eine spätere Szene noch spätere Druckwerte. Ohne belegbare
  Materialaufteilung bleibt die betroffene Schätzung unbekannt.
- Analysekarten binden Anfrage, unveränderten Dokumentstand, ausgewertete Szene,
  Körper, Kartenart und Profil bis zu Ergebnis, Größenabsage und Fehler.
  Fortschritt und Abbruch benutzen den gemeinsamen Fortschrittsbereich.
  Ein Kartenwechsel entfernt die alten Farben sofort; auch ein Treffer im
  Cache oder „keine Karte“ entwertet verspätete Antworten des Vorgängers.
  Ein Baumaufbau (Einheit, Thema, Ausblenden) ist keine neue Auswahl: Der
  Objektbaum leert sich unter `QSignalBlocker` und meldet einmal aus
  `_restore`, sonst brach die Leerung dazwischen die laufende Karte ab. Ein
  ausdrücklicher Abbruch hält, bis der Kunde Körper oder Kartenart wechselt
  (`_map_cancelled_for`, 21.09.2026).
  Der gebundene Berichtsklick wird bei warmem und leerem Cache genauso beendet
  wie beim Arbeiterergebnis. Die Formabweichung markiert ausschließlich ihren
  wirklichen Zeugen samt unterer Punktdistanz, nie das Mittel mehrerer Flächen
  oder die obere Schranke als Punktwert. Ein Einheitenwechsel zeichnet Karte
  und Ortsmarke neu, ohne eine Rechnung oder abgebrochene Anfrage zu starten.
- Der Wechsel aus dem modalen Druckdialog ins Filamentpanel schließt zuerst
  den Dialog; ein sichtbarer Rückweg öffnet die Druckeinstellungen wieder.
  Spulen werden über Name, Farbe, Materialprofil und Materialart unterschieden.
  Alte Werte ohne Materialbindung werden erst nach ausdrücklicher Übernahme
  und Bestätigung einer Spule zugeordnet.
- Die Kopfzeile der Druckeinstellungen bleibt auch bei 520 bis 620 Pixeln
  breit lesbar: Qualität und Mitgabe stehen zusammen, der Drucker erhält eine
  eigene volle Zeile, Filamentliste und Wechselknopf die dritte. Nur die
  Filamentliste darf umbrechen; Auswahlfelder und Handlungen werden nicht
  gekürzt oder aus dem Dialog geschoben.
- Session hält die Eigentumssperre ihrer namenlosen Wiederherstellung bis zum
  Projektwechsel oder echten Fensterschluss. Ein Oberflächen-Neuaufbau bei
  Sprachwechsel beendet dieses Eigentum nicht.

## Testen

Die Tests laufen offscreen; `tests/conftest.py` setzt `QT_QPA_PLATFORM`
selbst. Zwei Fallen, beide gemessen:

- **Qt lügt vor dem Anzeigen.** `setExpanded`, `isVisible` und `hasFocus`
  antworten falsch, solange nichts angezeigt wurde — ein Test kann grün
  bleiben gegen einen Zweig, der nie läuft.
- **Gesetzt heißt nicht gezeigt.** `QMenu` verschluckt Tooltips; ein Test über
  den Wert eines Hinweises sagt nichts über seine Sichtbarkeit.

Die Suite baut über siebenhundert Fenster mit Ansicht nacheinander auf und
reißt am Stück ab. Fensterdateien werden **je Prozess einzeln** gefahren —
siehe `CLAUDE.md` im Wurzelverzeichnis.

Die Platzierungsvorschau nimmt die Projektparameter in ihren Werkzeugschlüssel
auf. Der Arbeiter löst abhängige Maße einmal auf und reicht sie sowohl an
gewöhnliche Operationswerte als auch an eingebettete Bausteinskizzen weiter.
Gleichbleibender Skizzentext darf nach einer Maßänderung kein altes Werkzeug
sichtbar lassen.
