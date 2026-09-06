# `app/ui/` — die Oberfläche

PySide6. Darf `app.core` benutzen, die Gegenrichtung ist verboten (§8). Die
Oberfläche rechnet keine Geometrie und ändert keine — **sie ruft Ops auf.**

Die Regeln dieses Gebiets stehen in `.claude/rules/` und laden sich selbst —
**vier Dateien, je nachdem, was man anfasst:**

| Regeldatei | Lädt bei |
|---|---|
| `oberflaeche.md` | jeder Datei hier — Texte, Zahlen, Grenzen, Barrierefreiheit |
| `ansicht.md` | `viewport.py`, `overlay.py`, `cursors.py` und den Leisten |
| `wartezeit.md` | `session.py`, `loading.py`, `leash.py`, `splash.py`, `main_window.py` |
| `zeichenflaeche.md` | `sketch_editor.py` |

Hier steht die Karte, dort das Gesetz.

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
  Ergebnis fragen, nicht nach dem Grund.
- **`Scene.objects` ist ein Wörterbuch.** Darüber zu iterieren gibt die
  Kennungen. Die Folgemeldung `'str' object has no attribute 'mesh'` sieht
  aus wie ein leerer Import und ist keiner.

- **Das Fenster liest über `import_model_async`, nicht über `import_model`.**
  Der synchrone Weg steht daneben und bleibt — Kommandozeile und Tests
  brauchen einen, der wirft. Das Fenster braucht einen, der meldet: Bei einer
  3MF zählt `import_plan` die ganze Baugruppe, bevor eine Operation entsteht,
  und das dauert bei 63 MB vierzehn Sekunden. Oberhalb von
  `PLAN_IN_WORKER_ABOVE` läuft das im Arbeiter, der Fehler kommt über
  `importFailed`. Wer in einem Test `session.import_model` patcht, patcht
  damit einen Weg, den das Fenster nicht mehr geht — fünf Tests in
  `test_ui.py` hingen daran (03.09.2026).

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
ist ein offener Punkt) · `main_window.py` (**rund 8 900 Zeilen** — das
Hauptfenster, §2.5) · `splash.py` · `first_run.py` (der erste Start) ·
`start_screen.py` (die ersten fünf Minuten, §2.3) · `header.py`

**Brücke zum Kern**

`session.py` (§7, §15.6) · `leash.py` (die Halteleine für Arbeiter-Threads — und für Ereignisfilter,
die ihr überwachtes Objekt überleben: `stop_watching_the_dying`)

**Ansicht**

`viewport.py` (**rund 8 200 Zeilen** — §18, §2.9) · `render/` (der Renderer
hinter der Ansicht, eigene `CLAUDE.md`: der Vertrag `api.py`, pygfx über wgpu
in `gfx_renderer.py`, gebaut über `factory.py`, Kameraführung, Formen,
Bewegungsgriff) · `overlay.py` (Zonen über der
Ansicht statt neben ihr) · `loading.py` (Ladeanzeige, §2.8) · `cursors.py` ·
`placement_flow.py` (Oberflächenplatzierung aus dem Operationsdialog, §18.5) ·
`spacemouse.py` (die 3D-Maus als zweite Hand an derselben Kamera: HID-Leser
über hidapi, auf dem Mac der Treiberweg über das 3Dconnexion-Framework des
Kunden, die Abbildung als reine Funktion — Regel in `ansicht.md`).
**`camera_step` hat drei Aufrufer, nicht einen:** die Kappe, das Kippen mit
dem gedrückten Rad und die Flugtasten. Wer dort an einer Achse dreht, dreht
an allen dreien

**Platzieren bleibt eine Operation.** Der Operationsdialog übergibt Werte an
`PlacementFlow`; der Controller zeigt nur einen temporären Werkzeugaktor und
Maßpfeile. `Session.placement_async()` berechnet Originalfläche und
`PlacementTool` außerhalb des Qt-Threads. Mausbewegungen und Maßänderungen
verwenden diese Kontexte; der Merkmalskörper wird dabei nicht erneut gebaut.
Der Kontext gehört zu Eingaben und Werten, verspätete Ergebnisse werden über
Generation und Laufkennung verworfen. `Position übernehmen` bestätigt den
vorhandenen Dialog und erzeugt genau dessen Transaktion; Escape behält die
Zahlen ohne neuen Verlaufsschritt. Beim Bearbeiten eines historischen Schritts
liefert `Session.placement_before()` dessen tatsächlichen Eingang. Auch ein
fehlerhafter Schritt bleibt damit korrigierbar. `result_current` und
`Viewport.is_scene_applied()` sperren Ziele bis zur aktuellen sichtbaren Szene.
Maßfelder erhalten ihre Float64-Werte und werden gemeinsam außerhalb der
tatsächlich sichtbaren `OverlayHost`-Karten angeordnet; Verbindungslinien halten
verschobene Felder ihren Maßpfeilen zugeordnet.

Die Maßfläche belegt über eine `QRegion`-Maske nur Linien, Pfeilspitzen und
Zuordnungsmarken. Dort zeichnet sie deckend neu; der übrige Bereich bleibt dem
nativen Renderer. Ein vollflächiges `WA_NoSystemBackground`-Widget ist über
beiden Renderern ausgeschlossen.
Die Maske nimmt die tatsächlichen Rechtecke aller Zahlenfelder und
Beschriftungen aus; die native Stapelreihenfolge allein schützt deren
Lesbarkeit nicht. Die gefüllte Werkzeugvorschau zeigt ihre Oberfläche ohne
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
wiederholt alle Bohrungsdreiecke.
Die Öffnungszielhilfe verlängert keine axialen Bohrungsgrenzen. Seitlicher
Randfang gilt nur am sichtbaren Eintritt oder bei einem belegten Treffer des
wirklichen Bohrungszylinders; eine Rückwand bleibt eine Sichtgrenze.
Nur Bohrungen, Senkungen (`cone` mit `recess`) und Innengewinde bilden axiale
Öffnungsziele. Rundungen, Ringnuten und äußere Flächen bleiben Dreieckstreffer.
Die Rückrechnung liest den beim Aktoraufbau gespeicherten Versatz und die
tatsächlich gezeichneten Körper. Während eines neuen Ansichtsauftrags und
nach dessen Fehler bleibt dieses letzte Bild die Grundlage des Picks;
angeforderte Platten- oder Explosionszustände greifen erst mit dem neuen Bild.
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
`tool_strip.py` · `analysis_bar.py` · `section_bar.py` · `split_bar.py` ·
`transform_bar.py` · `explode_bar.py` · `sculpt_bar.py` · `pose_bar.py` ·
`scale_widget.py` · `facts.py` (was das Teil kostet, während man daran baut)

Die Legende in `analysis_bar.py` verteilt bei vielen benannten Kartenstufen
ihre Beispiele über den gesamten Farbbereich und nennt die Zahl ausgelassener
Stufen. Jeder Beispielname behält exakt die Farbe seiner ursprünglichen Stufe.
Bei kontinuierlichen Karten stammen Farbraum und inverse Skalenwerte aus
`AnalysisMap`: Die Krümmung verwendet eine logarithmisch abgestufte Farbrampe,
deren Legende weiterhin physische Millimeterwerte nennt und die Abstufung
ausweist. Der Viewport reicht die transformierten Werte an beide Renderer;
Messwerte, Schwellwerte und Hervorhebungen bleiben unverändert.

**Dialoge**

| Datei | Besonderheit |
|---|---|
| `op_dialog.py` | **Wird aus dem Parameterschema erzeugt** (§10, §2.4). Kein Dialog wird von Hand gebaut — wer einen tippt, hat das Register umgangen |
| `dialogs.py` | Fragen und Fehler (§2.7), Freischaltung mit Online- und Dateiweg sowie freiwillige Förderung |
| `print_settings_dialog.py` | Druckeinstellungen und Slicer-Übergabe (§29) |
| `print_disclosure.py` | Der Hinweis davor: dass diese Werte Erfahrungswerte sind und mit einer 3MF mitreisen — und die Wahl, ob sie das sollen (§29) |
| weitere | `settings_dialog` · `generate_dialog` (Weg 3) · `recipe_dialog` · `variants_dialog` · `comfy_dialog` · `install_dialog` · `support_dialog` · `update_dialog` · `changes_dialog` |

**Editor**

`sketch_editor.py` (**rund 4 800 Zeilen** — §30.1, Stufe zwei)

**Agent**

`chat.py` (§26.3, §2.5) · `snapshots.py` (Ansichten für den Agenten) ·
`remote_server.py` (MCP im Fenster)

## P0-08 — KI-Hinweis an der Sendegrenze

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

## §29 — was die Datei mitnimmt

`print_disclosure.py` steht vor dem ersten Öffnen der Druckeinstellungen und
sagt dreierlei: Die Werte sind Erfahrungswerte; sie reisen mit einer
gespeicherten 3MF und mit der Übergabe an den Slicer; für Ergebnis und
Schäden gelten die Nummern 10 und 11 des Lizenzvertrags. Anders als der
KI-Hinweis sperrt er nichts — hier verlässt nichts das Gerät, und die Wahl
darunter entscheidet erst über das Speichern.

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

**Erscheinung**

`style.py` (Stylesheet, Typografie-Skala, Abstandsraster, §19.3) · `theme.py`
(hell und dunkel) · `window_chrome.py` (die Titelleiste trägt die Farben der
Anwendung — Windows malt sie weiter, es bekommt nur gesagt, in welcher Farbe;
ein Wächter am Ereignisstrom, damit kein Dialog vergessen wird) ·
`palette.py` (**Farbe trägt nie allein Bedeutung**,
§19.1) · `icons.py` · `motion.py` (Bewegung an einer Stelle, nicht an
zwanzig) · `labels.py` (kurze Texte, auf die sich mehrere Teile einigen)

**Hilfe und Bedienung**

`manual_window.py` · `tour.py` · `shortcuts_window.py` ·
`shortcut_schemes.py` (zwei Belegungen, eine Quelle) · `command_palette.py`

**Navigationstasten gehören dem fokussierten Inhalt.** Der gemeinsame
`NavigationKeys`-Filter schützt Pos1, Ende, Bild auf und Bild ab in Listen,
Bäumen, Text- und Zahlenfeldern sowie Reglern (`QAbstractSlider`). Beim
Fokuswechsel zur Ansicht gelten wieder die Fensterbefehle; Ziffern der
Darstellungsarten bleiben auch im Inhalt Fensterbefehle.

**Einstellungen** `settings.py` · `survey.py`

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
- **Gebündelte Befunde behalten nur gemeinsame Klickziele.** Gleiche Kennung,
  Schwere, Meldung, Herkunft, Körper, Schritt und Handlungen bilden eine
  gezählte Zeile; andere Handlungen trennen das Bündel. Ort, Merkmalsziele und
  Werte trennen allgemeine Befunde ebenfalls. Nur verlorene
  Formdetails werden trotz verschiedener alter Kennungen ab zwei Einträgen
  gebündelt; ihre internen Kennungen stehen ausschließlich in Tooltip und
  zugänglicher Beschreibung. Körper und Schritt stehen sichtbar an der Zeile.
  Der Klick zeigt beide, aber keine Merkmalskarte einer Stelle, die nicht mehr
  existiert. Der Kerntext bleibt kanalneutral; nur das Panel nennt den Klick.
- **Und der Objektbaum bündelt nach derselben Regel wie der Prüfbericht.**
  Gleichnamige *erkannte* Merkmale stehen ab `BUNDLE_FROM` unter einem
  zugeklappten Dach („Hohlkehle (17)"), die Maßspalte bleibt dort leer — ein
  Dach über siebzehn Radien hat kein Maß. Was aus einem Baustein kam, gruppiert
  weiter nach seinem Schritt; die zwei Dächer schließen einander nicht aus.
  Gemessen an `build_tray_v3.step`: 234 erkannte Merkmale, rund fünfzig
  sichtbare Zeilen „Hohlkehle R13,98 mm" untereinander, die die linke Spalte
  füllten und Parameter und Verlauf hinausdrückten. Der Bericht daneben zeigte
  dieselbe Menge längst als eine Zeile. `_restore` klappt das Dach auf, wenn
  das gewählte Merkmal darin liegt — sonst wäre ein Klick im Viewport auf eine
  Verrundung wieder ins Leere gegangen.
- **Ein zusammenhängender Bohrungshohlraum ist ein vollständiger Ast.**
  Bohrung, kegelige Übergänge und zylindrische Senkungen werden in der
  Reihenfolge von `perceive.relations.cavity_chains` ineinander gehängt; eine
  Kette mit drei Flächen darf nicht auf ein Paar gekürzt werden. Der Objektbaum
  fragt die Bulk-Auskunft genau einmal je `SceneObject`, damit die Randringe
  eines großen Netzes nicht für jedes Merkmal neu entstehen. Das
  Merkmalspanel reicht das `MeshData` optional bis `actions_for` durch:
  Aufrufer ohne Netz behalten die bisherige Paar-Auskunft, die Oberfläche mit
  Netz nennt auch bei der vollständigen Kette vorab das gemeinsame Versetzen.
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

## Zustandsbindung in asynchronen Bedienwegen

- Quellenarbeiter gehören zu genau einem Projekt und gegebenenfalls zu einem
  beim Start gewählten Zielkörper. Späte Signale dürfen weder einen später
  gewählten Körper bearbeiten noch den Zustand eines anderen Projekts melden.
- `Viewport.sceneApplied` bestätigt die tatsächlich aufgebaute Szene.
  Schnittgrenzen und Kandidatenmarkierungen werden danach synchronisiert,
  nicht schon beim Einreihen des Szenenaufbaus.
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
- Analysekarten tragen eine Anfragekennung und ihre ausgewertete Szene bis
  zu Ergebnis, Größenabsage und Fehler. Ein Kartenwechsel entfernt die alten
  Farben sofort; auch ein Treffer im Cache oder „keine Karte“ entwertet
  verspätete Antworten des vorherigen Arbeiters.
- Der Wechsel aus dem modalen Druckdialog ins Filamentpanel schließt zuerst
  den Dialog; ein sichtbarer Rückweg öffnet die Druckeinstellungen wieder.
  Spulen werden über Name, Farbe, Materialprofil und Materialart unterschieden.
  Alte Werte ohne Materialbindung werden erst nach ausdrücklicher Übernahme
  und Bestätigung einer Spule zugeordnet.
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
