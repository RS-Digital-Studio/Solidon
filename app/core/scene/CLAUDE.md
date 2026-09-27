# `app/core/scene/` — Dokument, Stapel, Auswertung

Was gerade offen ist und wie daraus Geometrie wird (§12–§16).

Das Platzierungswerkzeug von `resize_hole` erhält am Langloch den bisherigen
Verstellweg und seine Richtung. Für `slot_hole` folgt die Vorschau der
Zielbreite einschließlich Materialkompensation; eine fehlende Zielbreite
übernimmt das gemessene Maß ohne erneuten Zuschlag.

Die Merkmalszuordnung erhält denselben Abbruch wie die Auswertung:
`matching.match(check_cancelled=watch.raise_if_cancelled)` gilt für native,
neu erkannte und deklarierte Merkmale. Gespeicherte Antworten werden über
`matching.resolve` mit demselben Rückruf erneut verglichen. Ein Abbruch beendet
den Aufrufer, bevor er Zuordnung oder Ergebnis veröffentlicht; es entsteht
kein neues Token.

`evaluate(question_context=...)` reicht die tatsächliche ungeklärte Ausgabe
als vergängliche `EvaluationResult`-Vorschau an die Rückfrage. Neue Ausgaben
erben dabei keinen Hash der alten Körper. Vollständige Gruppen werden je
Körper gesammelt, vollständige Antworten erst nach allen Ausgaben einer
Operation veröffentlicht. Abbruch hinterlässt keine Teilantwort. Native
referenzierte geometrische Konkurrenz hält vor der Veröffentlichung an;
generische Netzgruppen benennen keine native Topologie um.

**Ein alter Flächenbezug am exakten Körper gilt nur mit Beleg.** Nach jedem
Ausgabeübergang eines exakten Körpers — auch nach einem Cachetreffer und auch
bei Operationen ohne `touches_features` — prüft `_with_features`, ob jedes
alte Merkmal, das ein **späterer** Verbraucher oder eine aktive Passung noch
braucht (`_needed_after`, dieselbe zeitliche Grenze wie
`orphans.pending_references`), auf einem von drei Wegen belegt ist:
unverändert durchgereicht, von der Operation selbst als
`OpResult.feature_continuations` ausgestellt (`FeatureContinuation`, körper-
qualifiziert, ordinal je Ausgabe, auf Struktur geprüft in
`_checked_continuations`, im Ergebniscache als `CachedResult.continuations`
mitgeführt) oder durch die eindeutige geometrische Zuordnung auf **denselben**
Namen mit gültiger aktueller Auswahl — oder auf ein bis auf Rechenrauschen
unverändertes Merkmal unter anderem Namen (`_unchanged_continuations`, das
unter dem alten Namen weitergeführt wird). Ein frisch vergebener gleicher Name,
ein veränderter Partner unter anderem Namen und eine ausgelassene Zuordnung sind nicht
belegt (`_unproven_native_references`); die Kette hält atomar an der
Erzeugergrenze mit `NativeReferenceLost`, der Befund nennt den späteren
Verbraucher, und `EvaluationResult.blocked_references` trägt die Bezüge zum
Verweisfilter: `orphans.check(blocked=...)` meldet sie als `feature.blocked`,
ohne Namensexistenz als Auflösung und ohne Frage gegen die alte Szene.
Belege stellen `resize_hole` (Bohrung und belegter Boden aus
`_preserved_exact_features`) und jede exakte Merkmalshandlung aus
(`prepare_ops._exact_features_after`, über `_exact_cavity_result`,
`_exact_copy_result` und `_thread_result`).

**Was die Zuordnung nicht belegt, wählt der Kunde am neu gebauten Körper**
(`_native_reselection`): je nicht belegtem altem Bezug die aktuellen
Merkmale derselben Art mit gültiger Auswahl, die noch kein **belegter** alter
Name beansprucht, über denselben Frageweg und dieselbe Gruppen-, Fingerabdruck-
und Atomizitätsmechanik wie am Netz (`_answer_matches` mit `scope`). Die neu
zu wählenden Namen fallen vorher aus der Zuordnung, und ihr geometrisch
gefundener Nachfolger unter anderem Namen steht als erste Antwort da — sonst
fehlte gerade er unter den Antworten, und jede Antwort scheiterte an
`mapping_with_decisions`, weil der alte Name schon zugeordnet war. Die
Wahl wird als Alias unter dem alten Namen veröffentlicht (`apply_mapping`,
mit aktuellen Maßen, Dreiecken und Teilträgern) und liegt in
`Operation.matches` in der eigenen Domäne `native-group:` mit `scope` —
roher Erzeugerschlüssel plus Ausgabeindex, nicht der Objekthash danach, der
die Wahl selbst enthielte. Eine Netzantwort (`group:`) gibt native
Konkurrenz nie frei, ein anderer Scope fragt neu, alte Einzelantworten
gelten hier nicht. „Nicht weiterführen" und ein fehlender Kandidat halten die
Kette wie oben an und werden am exakten Körper nicht festgeschrieben; ohne
jemanden zum Fragen (Kommandozeile, Agent) trägt der Halt die Kandidaten als
`choose:`-Vorschläge. Projektformat 28 trägt den Datensatz mit fünf Feldern
(Migration 27→28 ohne Datenumschreibung, `example_v28.p3d`); Cache und
Verlauf brauchten dafür nichts Neues — der Folgehash enthält das Alias,
`_copy_operation_matches` filtert weiter nach Ausgabekörper.

**Und Kanten werden vor dem Cache gebunden** (`edge_binding.bind_edges`,
P1.4c.4b). Ein Kantenfeld (`kind="edges"`) trägt gerundete Schlüssel, und
zwei Kanten können denselben tragen — die zwei Ränder eines Spalts von vier
Tausendstel Millimetern, oder ein alter Rohrschlüssel an beiden Rändern.
`_evaluate` löst jedes aktive Kantenfeld (`depends_on` erfüllt, Schlüssel
vorhanden) am ersten Eingang auf, in dem Kern, den die Operation gleich
benutzt (`geom.edges.edges_in_kernel`; `OperationSpec.edges_on_mesh` für den
Wulst), **bevor** `cache.get` läuft: Bei einer Kollision fragt es über
denselben `ask`, zeigt die Kandidaten als `EdgeTarget` (Token, Körper, Zug,
Anzeigefakten) am gültigen Eingangsstand und gibt der Operation die
bestätigte Auswahl als Indizes in `OpContext.bound_edges` mit — der Kern
löst keinen Schlüssel ein zweites Mal auf. Der Fingerabdruck der gebundenen
Kanten (`edge_fingerprint`) geht in den Operationsschlüssel des Verbrauchers:
Eine andere Antwort ist ein anderer Cacheeintrag. Die Antwort liegt in
`Operation.matches` in der dritten Domäne `edge-answer:` — am **Eingang**,
Feld, Schlüsselbündel und der Fassung des Eingangs (`scope` = sein
Objekthash; ein anderer Eingang fragt neu), veröffentlicht erst nach dem
vollständig gelungenen Schritt (Projektformat 29, Migration 28→29 ohne
Datenumschreibung, `example_v29.p3d`; `_copy_operation_matches` filtert sie
nach Eingangskörper, der Projektleser prüft sie gegen `in`). Der
**Aliasfall** — die gewählte Kante trägt einen eindeutigen aktuellen
Schlüssel — wird zum Parameter über `EvaluationResult.answers`, wie die
Einheitenfrage. Ohne jemanden zum Fragen ist die Kollision ein
`AmbiguityError`-Befund mit den Token als `choose:`-Vorschlägen; eine
Gruppenauswahl bindet nichts.

`Operation.matches` speichert vollständige Antwortgruppen je Ausgabekörper
und alter Anspruchsmenge. `perceive.match_records` ist die gemeinsame reine
Schemaquelle für Projektleser und Wiedererkennung; Kandidatenindices sind
lokal zur Gruppe, Nichtfortführung ist ausdrücklich gespeichert. Alte
Einzelantworten liegen ab Format 27 unverändert unter `legacy`, auch in
beiden gespeicherten `edited_ops`-Seiten. Die Migration erfindet keine Lage
oder Körperzuständigkeit; unbrauchbare Altabdrücke bleiben lediglich lesbar.

Die Frage vor der langen Vollerkennung (§21.1; was sie zusagt, steht in
`kern.md`) hat ihre Orte in `evaluate.py`: `_full_recognition_allowed` für
einen großen Körper, `_ask_once_for_large_bodies` für mehrere aus einem
Import, beide über `_asked_about_recognition`, `_recognition_choice` für
die gespeicherte Wahl am Ladeschritt (`recognition-answer:`, an
Ausgabekörper und Netzinhalt gebunden, dieselbe strikte Struktur wie der
Projektleser aus `perceive.match_records`), `_skipped_recognition` für den
Befund `perceive.too_large` in seinen vier Fassungen.
`_WatchedAsk.optional` zählt sie nicht als Frage des Schritts, damit der
Import auf die Platte geht. `recognition_of` baut je Lauf die Wahl je Körper
(`_BodyRecognition`), die Folgeschritte lesen; der Speicherfehler-Rückweg
steht in `_with_features`, der Merker dazu in `perceive.local`;
`_remeasured` übersetzt einen Halt der örtlichen Nachmessung in den Satz des
Schritts. `on_recognition_answer` meldet eine Antwort sofort, die Sitzung hält
sie fest. `History.reopen_recognition` nimmt die Wahl je Körper am
Ladeschritt zurück, ohne Transaktion und ohne Lizenzgrenze wie
`record_matches`; `history.recognition_reopenable` sagt Panel und
Kommandozeile, ob es etwas zurückzunehmen gibt. Die Prüfung erfolgt nach dem
rohen Operationscache und vor jeder Erkennung; eine Absage schreibt keinen
leeren Eintrag in den Erkennungsmerker.

`History.record_matches` ersetzt ganze Einträge ohne weitere Transaktion
und übernimmt ihre verschachtelten Werte als eigene Kopie. Vor Undo/Redo
sichert die gerade verlassene Änderungsseite ihre aktuellen Antworten nur
bei übereinstimmender Operationsfassung: Name, Ein-/Ausgänge, Parameter,
Startwert und Übersetzungsmarkierung. Solverauskunft und Antworten selbst
sind keine neue Fassung. Serializer und wiederhergestellte Fassungen teilen
keine veränderlichen Antwortlisten; eine andere frühere Fassung bleibt erhalten.
Wechselt ein Schritt seine Ausgabekörper, behält nur seine Vorher-Fassung
die Gruppen weggefallener Körper. Verbleibende Gruppen und Altantworten
werden weder umbenannt noch auf neue Körper übertragen.

Maßquellen reisen mit `Feature.params` durch Auswertung, Historienübernahme
und beide Cacheebenen. Der Plattencodec speichert `measure_sources` ausdrücklich;
alte Daten ohne Quelle bleiben unbekannt. Ein neuer Fit behält seine Quelle,
auch wenn er einen erzeugten Namen erbt. Projektdateien speichern weiterhin
Operationen und Werte statt abgeleiteter Merkmalsresultate. `bore_advice`
unterscheidet belegte native Maße, Schätzungen und Vorgabemaße; ein passender
Zahlenbereich allein belegt kein ursprüngliches Schraubenmaß.

`Feature.surface_patches` trägt die belegten analytischen Teilflächen und
ihre Originaldreiecke ebenfalls durch beide Cacheebenen. Der Plattencodec
prüft den gemeinsamen Trägervertrag und die Merkmalszugehörigkeit; beschädigte
Einträge werden neu gerechnet. **Nicht geprüft wird die Dreieckszahl des
gespeicherten Netzes**: Der Cache trägt die **rohe** Ausgabe einer Operation,
und die darf Merkmale ihres Eingangs mit dessen Dreiecksnummern durchreichen
(der Bausteinwirt, das Reparieren) — erst `_with_features` bindet sie an das
neue Netz, beim Treffer wie beim frischen Lauf. Vorbereitete Objekte in den
Cache zu legen war der andere Weg und ist verworfen: Ein warmer Treffer lief
damit nicht idempotent durch `_with_features` (Weg 3, 21.09.2026). Beim Lesen
von der Platte fasst `_warm_figures` Volumen, Fläche, Dichtheit und Teilezahl
im Arbeiter an, damit das Fenster sie nur noch abliest.
Trägervektoren bleiben nach JSON unveränderliche Tupel. Merkmals- und
Teilträgerindizes zählen zum vorhandenen Speicherbudget hinzu.
Übernimmt ein erzeugter Name eine neue erkannte Fläche, reisen deren aktuelle
Teilträger mit. Ein nicht mehr belegter alter Name behält keinen alten
Formnachweis. Am vollständig ausgewerteten Endstand benennt ein
Informationsbefund pro Körper die verfügbare Abweichungskarte; Zahlen und
Ortsmarke entstehen erst durch deren ausdrückliche Berechnung.

Regeln: `.claude/rules/operationen.md`, für die Projektdatei zusätzlich
`.claude/rules/dateiformat.md`.

`fits.pair_problem`, die angebotenen Passungsarten und die spätere Prüfung
verwenden denselben Vertrag: Ein Gewindepaar braucht bekannte gleiche
`handedness` (`right` oder `left`) zusätzlich zu Innen-/Außenrolle und
Steigung. Fehlende Angaben bleiben unbekannt, auch wenn sie auf beiden Seiten
fehlen. Unterschiedliche Drehrichtungen erzeugen einen Befund mit Rückweg
über Gegenstückwahl oder Rücknahme der Spiegelung. Seit P2.5 messen beide
Kerne die Händigkeit (`helix.Helix.handedness`, `brep.thread`); ein Gewinde
ohne sie sagt weiter „nicht gemessen“, nicht „stimmt nicht überein“. Und
zwei gemessene Steigungen sind auf ihre **Unsicherheit** gleich, nicht auf
`EPS_GEOM` (`_pitch_uncertainty`): die Wendelabweichung des exakten Lesers,
eine Rasterstufe `PITCH_STEP` am Netz, null bei einem Erzeuger — 0,99 am
Netz gegen 1,0000 am exakten Körper ist dieselbe Steigung.

`placement.seat_of` prüft beide Mündungen einer erkannten Bohrung. Bei
Bohrung und Langloch muss die Flächennormale vom Hohlraum weg zeigen; der
Sacklochboden ist deshalb keine Trägerfläche. Liegt die Mündung hinter einer
Fase, sucht ein zweiter Durchgang entlang der Achse bis `mouth_reach` weiter
(Regel in `operationen.md`); `mouth_on` beantwortet dieselbe Frage an einer
schon vorbereiteten Fläche, und `surface_values(..., mouth=...)` rückt die
Mitte nur auf der eigenen Mündungsfläche nicht um die Fase (G5).
`prepare_tool` zeigt für `slot_hole` mit Länge =
Breite die runde Bohrung (`prepare.is_round_length`). `mouth_outline` gewinnt den
Werkzeugumriss aus der konvexen Hülle der Mündungspunkte (§21.1).
Die Nachbarschaft exakter Originalkanten nutzt den privaten Trimesh-Cache
als Beschleunigung. Fehlt dessen Lese- oder Schreibschnittstelle, bleibt
dieselbe Berechnung ohne Cache verfügbar; echte Spalten bleiben offen.

Die Platzierungsbezüge sind vergänglich und gehören zu genau einer
`PreparedSurface`: `with_reference` prüft Kennung **und** unveränderte
Geometrie, `at_point(references=...)` hält diese Auswahl beim Zug fest.
Außenkanten haben Vorrang vor inneren Kanten; belegte Langlochrichtungen
liefern zusätzliche Achsen, Bohrungen und Zapfen ihre tatsächlichen Mitten.
`MAX_REFERENCE_CONDITION` begrenzt die dimensionslose Verstärkung auf zehn
Anzeigeschritte. Das ist eine Bediengrenze, keine geometrische Unsicherheit
oder Fertigungstoleranz. Dicht kreisförmige Konturen liefern keine Geraden,
auch ohne globales Lochmerkmal; daraus entstehen keine erfundenen Mitten.
`seat_of` füllt ausschließlich die eigene Öffnung, andere Ausschnitte und
Bezüge bleiben bestehen. Gespeichert werden weiterhin Operationswerte,
keine `edge_0`-Bindung; dauerhafte Assoziativität gehört zum separaten
Referenzvertrag (§13, §18.11).

`placement.original_surface_hit` prüft Originaldreiecke blockweise und
abbrechbar. `geom.mesh.ray_hits` liefert Abstand und Dreiecksindex gemeinsam;
ein zusätzlicher räumlicher Suchindex ist dafür unnötig. Der nächste zulässige
Treffer berücksichtigt alle aktiven Schnittebenen und behält seine Originalkennung.

Spulenbindungen in `PrintSettings` speichern die vollständige Druckfilament-
Identität und eine lokale Kennung, niemals Pfade. `slot_profiles` bleibt eine
Folge von Slicer-Profilnamen. Die Migration ergänzt leere Bindungen; sie rät
keine physische Spule aus alten Namen. Das gemeinsame Namensformat erhält
übersetzbare Vorlagen samt Werten und wird vor dem Deserialisieren geprüft.
`DocumentState.spool_bindings` nimmt die physische Spulenwahl mit derselben
Transaktion wie die Filamentzuweisung zurück: `None` heißt unbeteiligt,
eine leere Folge entfernt die Bindungen. Andere Druckwerte und die stabile
Projektkennung bleiben erhalten. Datei- und Undo-Seiten benutzen dieselben
Serialisierungs- und Schemahelfer.

Herstellerprofile stehen in `PrintSettings.slot_profile_bindings` an derselben
vollständigen Filamentidentität. `None` erhält den alten Positionsvertrag,
eine leere Folge enthält ausdrücklich keine Zuordnung. Die Migration
ergänzt keine geratenen Identitäten; die Sitzung bindet alte Profilpositionen
an der ursprünglichen vollständigen Szene. Doppelte Identitäten und örtliche
Dateipfade werden vor dem Laden abgewiesen. Profilnamen dürfen Materialzusätze
wie `PLA/PETG` enthalten; daraus entsteht kein Dateizugriff.

Parameter mit `kind="features"` speichern eine Liste stabiler Merkmalkennungen.
Jeder fehlende Verweis wird einzeln aufgelöst, auch nach einem Cachetreffer.
Wenn eine leere Auswahl den ganzen Körper bedeutet, darf „Verweis streichen“
den Wirkungsbereich nicht vergrößern. Abbrechen erhält den fehlenden Verweis.

**Die Verweisfrage nennt, wer fragt, und streicht nur auf ausdrücklichen
Wunsch** (`orphans.question_for`, `removal_choice`): die Passung beim Namen,
den Schritt beim Titel aus dem Register, und als letzte Antwort „Passung
löschen“ beziehungsweise „Ohne dieses Merkmal rechnen“ — nie ein nackter
Strich. Jede andere Antwort, auch Abbrechen oder eine ohne Wahl geschlossene
Frage (`QuestionDeclined`), lässt den Verweis stehen; der Befund
(`feature.orphaned`, `feature.blocked`) trägt seinen Weg (`_way_forward`:
Schritt und Feld mit *Eingabe korrigieren*, eine Passung mit *Verlauf
zeigen*). Eine Skizze auf abgeleiteter Ebene behält beim Neuzuordnen jede
Ableitung darüber (`_on_another_face`): Versatz, Neigung und Ausdrücke,
nur die Fläche darunter wechselt.
Eine Körpervorbelegung entfernt nur ihre selbst geometrisch abgeleiteten
Einzel- und Mehrfachverweise. Ausdrücklich gewählte Merkmale und nachträglich
übergebene Werte behalten Vorrang; aus einer Körperwahl wird keine Flächenwahl.

Merkmalsverweise bedingt ausgeblendeter Felder bleiben gespeichert, werden
aber nur bei aktiver Parameterbedingung aufgelöst. `orphans._feature_fields()`
folgt dafür `depends_on` einschließlich äußerer Bedingungen und Schemavorgaben
für ältere Schritte, sowohl bei einzelnen Kennungen als auch bei Listen.

## Der Kreislauf

Darstellungswechsel werden erst nach vollständig vorbereiteten Ausgaben
gemeldet. Die unveränderten Eingangskennungen der rohen Ergebnisse belegen
die Nachfolger; neue Deckel oder Dichtungen gelten dadurch nicht als Verlust
ihres erhaltenen Trägers. Werden alle Ausgaben vernetzt, erhalten auch
verbrauchte exakte Werkzeuge einen eigenen Befund. Er nennt Eingangskennung,
damaligen Namen, betroffene Ausgaben und Operation. Die vollständige Aussage
ersetzt den allgemeinen Befund eines direkten Op-Aufrufs; bei einem Halt
entsteht keine Erfolgsmeldung über eine nicht übernommene Konvertierung.

Namenlose Wiederherstellungen besitzen eine Sitzungstoken-Kennung und eine
vom Betriebssystem gehaltene Eigentumssperre. Solange deren Sitzung lebt,
bietet `unsaved_recoveries()` sie anderen Sitzungen nicht an; auch allgemeines
Verwerfen löscht sie nicht. Der eigene Sitzungstoken erlaubt das Aufräumen.
Prozessende gibt die Sperre frei, auch wenn keine Aufräumfunktion mehr läuft.
Das gemeinsame Primitiv `paths.lock_file()` trägt auch die Lebensdauersperre
des Absturzprotokolls; `_lock_recovery()` bleibt der bisherige Projekteinstieg.

Beim Prüfen verlorener Referenzen benennt `pending_references()` den gerade
anstehenden Schritt. Historisch bereits verbrauchte und erst später erzeugte
Merkmale gehören nicht zu dessen Rückfrage. Am vollständigen Ergebnis werden
die aktiven Passungen geprüft. Die UI kann das unvollständige Ergebnis als
Kandidatenvorschau zeigen, bevor sie nach einer Zuordnung fragt.

```
Project ──> History (Stapel aus Transaktionen)
                │
                ▼
           evaluate()  ── reine Funktion aus
                │         Stack + Quellen + Parametern + Profilen + Startwerten
                ▼
        EvaluationResult (Szene, Befunde, Kennzahlen)
```

**Die Auswertung ist eine reine Funktion** (§15.1). Zweimal ausgewertet ergibt
identisch — `tests/test_evaluation.py` erzwingt es. Deshalb darf nichts, was
das Ergebnis beeinflusst, nur in der Sitzung leben; eine Rückfrage-Antwort
kommt über `OpResult.answered` in den Stapel zurück, so wie es die
Rückfallstufe tut.

**Und die Antwort ändert den Schlüssel des Schritts — das Ergebnis liegt
schon darunter.** `record_answers` schreibt `unit: mm` an die Stelle von
`unit: auto`; der Schritt hat danach einen anderen Operations-Hash, und bis
zum 22.09.2026 lief der Import beim nächsten Schritt ein zweites Mal.
`_key_after_answers` bildet den Schlüssel des nächsten Laufs auf demselben
Weg (`resolve_params` über die zusammengeführten Parameter, dann
`operation_hash`) und legt das Ergebnis auch dort ab, mit derselben
Herkunftsregel für die Platte. Erst damit trifft „Projekt öffnen aus
Plattencache" (§31) ein importiertes Modell überhaupt: Beim Wiederöffnen
steht die Antwort im Dokument, nicht die Frage.

**Was `_with_features` sonst noch spart.** Meldet eine Operation eine
Bewegung, bekommt `_with_features` den Eingang derselben Stelle
(`source_mesh`) und ruft `perceive.features.carry_detection`: Ist die Ausgabe
belegbar der starr bewegte Zwilling, trifft `detect` danach den Merker statt
zu rechnen (§21.2 ohne die 1,3 s Neuerkennung je Verschieben). Dasselbe für
eine feiner geteilte Ausgabe (*Kanten verfeinern*): Belegt
`perceive.features.refined_twin` die Teilung, überträgt
`carry_refined_detection` den Merker in die Nachfahren jedes Dreiecks — auch
nach dem Wiederöffnen, denn der Plattencache legt den Herkunftsvermerk neben
das Netz (`cache._refinement_to_disk`, `_refinement_from_disk`). Und
`evaluate(..., detect_features=False)` — der Weg der Live-Vorschau — lässt
die Erkennung aus, wo kein späterer Schritt und keine Passung ein Merkmal
des Körpers braucht: Der Körper behält, was die Operation ausgab, ohne
Zuordnung und ohne Waisenbefund, wie bei `perceive.too_many`; was der Merker
kennt, kommt trotzdem. Die Szene einer solchen Auswertung ist ein Bild, kein
Dokumentstand. **Derselbe Weg zeigt ein Modell vor seinen Merkmalen**
(KUNDE-14): `EvaluationResult.recognition_left_out` nennt die Körper, deren
Erkennung ausgelassen wurde — oder deren Frage vor der Vollerkennung noch
aussteht, denn ein Lauf ohne Erkennung fragt nicht und schreibt kein
„ausgelassen“. Ein zweiter Lauf mit Erkennung und demselben Cache trifft die
Schritte im Cache und rechnet nur die Erkennung; ihr Anteil wächst über den
Bereich des Schritts (`_StepProgress`, `features.detect(progress=...)`).

**Eine geteilte Fläche ist nicht verloren** (`_divided_in_place`, RM-217):
Steht nach dem Schritt eine Fläche in derselben Ebene und gleich gerichtet
innerhalb der alten, fällt die alte aus dem Hinweis `perceive.orphaned` — eine
Bohrung über die Kante teilt die angeschnittene Seite, ohne dass etwas fort
ist. Gemessen wird an den Dreiecken der alten Fläche im Netz, auf das sie
zeigen: `source_mesh`, und wo es fehlt, weil ein Eingang mehrere Ausgaben hat
(*Teilen*), `origin_mesh` — sonst verlor die zweite Hälfte jede geteilte
Fläche.

**Und sie heißt am größten Stück weiter** (`_divided_partners`, R4 der
Durchsicht 0.5.1): Findet eine alte Fläche — erkannt oder erzeugt — keinen
Partner, trägt das größte freie Stück in ihrer Ebene ihren Namen, samt
Dreiecken und neu gemessener Fläche; nach *Teilen* in jeder Hälfte, in der
ein Stück liegt (die Operation gibt eine querende Fläche beiden mit,
`prepare_ops._features_after_split`). Gleich große Stücke sind eine offene
Frage (`MatchResult.ambiguous`, Regel 21), die `_answer_matches` stellt,
sobald ein Verweis daran hängt. Die alten Dreiecke kommen vom Eingang desselben
Körpers, wo die Operation eine Fläche ohne sie weitergab
(`_with_triangles_before`, *Abschneiden*), und gelten nur, wenn sie diese
Fläche sind (`_old_face`: Normale und Ebene). Nach einer Bewegung wird nicht
gesucht. Eine erzeugte Fläche ohne Stück, die der Schritt beschnitten hat
(`_cut_by_the_step`), fällt aus dem Körper, statt ohne Dreiecke mit altem Maß
stehenzubleiben; zeigt eine Passung darauf, sagt es `perceive.generated_lost`.

**Die Zuordnungsfrage fragt, was etwas trägt, zuerst — und nur, was eine
Antwort hat** (`_answer_matches`). Verwiesene alte Merkmale kommen vor
unverwiesenen (stabile Sortierung); bleibt einem unverwiesenen nichts zur
Wahl, wird es ohne Dialog nicht weitergeführt und wie eine Antwort
festgehalten. Ein verwiesenes ohne Nachfolger wird weiter gefragt — an ihm
hängt etwas, und Abbrechen beginnt die Gruppe neu.

**Eine ohne Wahl geschlossene Frage hält den Schritt an, nicht die
Rechnung.** Die Sitzung meldet sie als `errors.QuestionDeclined` (Unterklasse
von `OperationCancelled`; eine überholte Frage bleibt ein gewöhnlicher
Abbruch). Jede Frage eines Schritts läuft durch `_WatchedAsk`; dort wird
daraus ein `AmbiguityError` mit `QUESTION_LEFT_OPEN` und den Knöpfen
*Eingabe korrigieren* (öffnet den Schritt, beim Übernehmen kommt die Frage
wieder) und *Verlauf zeigen*. Der Stand davor bleibt sichtbar; der Befund
steht am Schritt.

**Ein erklärtes Merkmal sucht seinen erkannten Partner an seiner Stelle**
(`matching.declared_partners`, `matching.near_its_declaration`): quer zur
Achse innerhalb seiner Breite (Durchmesser, beim Langloch die Länge), entlang
der Achse innerhalb seiner Tiefe, wo eine erklärt ist. Die Zuordnung
toleriert zwischen zwei Schritten 8 % der Diagonale; was die Operation selbst
gesetzt hat, steht dort, wo sie es sagt — sonst nahm eine verschobene Senkung
die der Nachbarbohrung, und deren Name verwaiste. Dieselbe Stelle entscheidet
unter Konkurrenten: Wer seinen umkämpften Kandidaten allein an seiner Stelle
hat, bekommt ihn, wer dort keinen hat, ist verwaist — sonst blieb ein
erkannter Verbinderstift ohne Namen, und die Nummern der Verbinder rückten.

**Und ein neues Merkmal bekommt keinen Namen, den ein Mitreisender trägt**
(`matching.apply_mapping(..., reserved=...)`, RM-222). Was die Operation
selbst ausgibt (`declared`), was ungeprüft mitreist (`unchecked`) und was
starr mitbewegt bleibt (`rigid_orphans`), wird nach der Zuordnung
eingehängt; bekam eine neu erkannte Bohrung als ersten freien Namen den
einer vorher geänderten, überschrieb die geänderte sie, und die neue fehlte
im Baum ohne Befund.

**Ein verwiesenes erkanntes Merkmal, das ein Schritt unkenntlich macht,
meldet sich am Schritt** (`perceive.referenced_lost`, Warnung mit
`CORRECT_INPUT` und `SHOW_HISTORY`). Gezählt wird, wer **nach** dem Schritt
noch darauf zeigt (`needed`, `_needed_after`) — was der Schritt selbst
verbraucht, fehlt danach niemandem.

Auch beim nachträglichen Ändern von Operationseingängen gilt der Zustand
unmittelbar vor diesem Schritt: bereits verbrauchte und erst später erzeugte
Objekte sind keine zulässigen Eingänge. Verlauf und Auswertung prüfen dieselbe
Eingangsanzahl aus dem Register, bevor Geometrie gerechnet wird.

Löschtitel lesen die Operationstitel aus dem Register ihrer `History`.
Die einzelnen Namen bleiben verschachtelte übersetzbare Werte, auch beim
Speichern und Wiederöffnen. Erst die Anzeige löst die gewählte Sprache auf.

Historische Ladeschritte behalten `coordinates="legacy_raw"`: Die Migration
schreibt den bisherigen Koordinatenvertrag auch in gespeicherte
`edited_ops`-Fassungen. Dadurch ändern weder Öffnen noch Undo alte
GLB-/GLTF-Quellen. Ausdrücklich gespeicherte Einheiten bleiben unverändert.

Historische Farbschritte mit Punkt und Radius bleiben unverändert erhalten.
Die Auswertung hält mit `evaluate.legacy_point_paint` an diesem Schritt an
und bietet seine rohen Werte sowie den Verlauf an. Die alten Felder werden
nicht als korrigierbare Eingaben des heutigen Flächendialogs ausgegeben.

Nicht erreichbare verknüpfte Quellen verhindern weder Speichern noch Öffnen
der Projektwerte. Der Bericht nennt die Quelle; der bisherige Abdruck bleibt
erhalten. Auswertung und Quellenzugriff verlangen weiterhin die passende
Prüfsumme. Abweichender Inhalt, Größenverletzungen oder ein Pfad außerhalb
des Projektordners werden auch beim Speichern und Öffnen abgewiesen.
Erneute Erreichbarkeit entfernt den alten Verknüpfungshinweis.

**Eigene Drucker und Materialien reisen als Beschreibung mit**
(`Document.carried_profiles`, ab Format 30): Name, Bauraum, Düse, Verfahren,
Schichtwerte — keine Pfade, kein Code (Regel 12, 13). `save` erneuert sie aus
Drucker, Material und den `set_material`-Schritten (höchstens
`MAX_CARRIED_PROFILES`); beim Öffnen legt `profiles.carry` sie in eine eigene
Schicht, `profiles.scene_profile` rechnet mit ihnen, und
`carried_findings` bietet an, sie zu übernehmen. Ein Drucker, den weder der
Rechner noch die Datei kennt, fällt auf den allgemeinen Drucker desselben
Verfahrens zurück, mit Befund und Wahl — `Session.profile`, Kopfzeile,
Druckdialog und Kommandozeile fragen dieselbe Funktion.

**Die Projektdatei ist inhaltsgleich, nicht bytegleich** (RM-106): Jeder
ZIP-Kopf trägt `CONTAINER_SYSTEM` (0) statt des schreibenden Systems; die
Deflate-Bytes hängen weiter von der zlib der Plattform ab (Windows-CPython
packt mit zlib-ng). Gleichheit prüft `project.content_digest` über Namen,
Längen und entpackte Inhalte. Eingecheckte Beispiel- und Belegdateien bleiben
an ihre Originalbytes gebunden; neu geschrieben wird nur, was ein Test
ausdrücklich erzeugt.

**Was eine Operation liest, steht im Schlüssel** — auch das Profil jedes
Eingangs mit eigenem Material (`evaluate._body_profiles`, mit Kalibrierung)
und jedes Drucker- und Materialfeld in `profile_key`, das eine Operation
liest (die Düsenzahl eingeschlossen); ein Feld, das keine liest, steht
ausdrücklich benannt daneben. Ein beschädigter Plattencache-Eintrag wird
verworfen und neu gerechnet (`cache._DAMAGED_ENTRY`), nie zum Absturz.

**Ein Bündel hält nur, solange es genau bleibt** (`bundling.stays_exact`):
Die Sitzung beendet ein Bündel, wenn die Summe der Züge nicht mehr dasselbe
ergäbe wie die einzelnen Schritte — etwa weil eine Bettkorrektur
(`transform.nudged_onto_bed`) dazwischen lag oder um die Körpermitte gedreht
wird. Mehrere Schritte, die zusammen wechseln müssen, gehen in **einer**
Transaktion (`History._swap_operations`, `use_part_states` für den
gespeicherten Bausteinstand). Varianten rechnen in der feinen Stufe und
teilen einen Cache (`variants.build`). Ein Programmfehler der
Merkmalserkennung hält am Schritt an wie einer der Operation.

**Den Verlauf umbauen heißt: planen, isoliert rechnen, übernehmen**
(RM-188 P7, Konzept vollwertiges CAD §13.9). Einfügen, Verschieben, Aus- und
Einschalten beginnen in `History.plan_insert` / `plan_move` /
`plan_suppress` / `plan_reactivate` und enden als `RevisionPlan`: die
Transaktion mit `revision`, die neu gefasste Folge, die Umnummerierung, beim
Ausschalten die mitgenommenen Schritte und der Dokumentstand beim Planen
(`mark`). `revision.revise` rechnet `plan.document(base)` isoliert und
vergleicht jeden Merkmalsverweis und jede Passung mit dem, was sie vorher
trafen: Vor jedem Schritt hält die Auswertung eine `ReferenceSight` fest
(`EvaluationResult.sights`, `fit_sights`), das Urteil fragt Herkunft, dann
Abdruck, dann Lage (`revision.verdict`, reine Python-Arithmetik wie
`kern.md` verlangt). Folgt ein Merkmal unter anderem Namen, schreibt der Plan
den Verweis um (`orphans.with_reference`, Befund
`history.reference_followed`); ist es fort oder mehrdeutig, fragt er
(`AmbiguityError` mit Kandidaten) oder sagt ab, ohne etwas zu schreiben.
`revision.commit` übergibt an `History.commit` — ein veralteter Plan wird
abgesagt — als **eine** Transaktion; Strg+Z legt die alte Folge mit ihren
alten Kennungen zurück.

**Die Kennung ist die Reihenfolge.** Die Auswertung sortiert nach
`Operation.id`, deshalb fassen Einfügen und Verschieben die Folge ab der
ersten geänderten Stelle unter neuen Kennungen neu (`_moved_order`, `_clone`
gemeinsam mit `_retried_after`): dieselben Werte, dieselben Körper, derselbe
Startwert. Die alten Kennungen stehen in `changes.after.edited_ops` als
`None` — neu gefasst, nicht gelöscht; der Verlauf blendet sie aus
(`panels.replanned_steps`). Welche Stelle geht, sagt `History.valid_targets`
aus `revision.dependencies` (Körper aus Ein- und Ausgängen, Merkmale aus den
Sichtungen) mit dem Grund für jede andere (`_order_problem`).

**Ein ausgeschalteter Schritt bleibt im Verlauf und rechnet nicht**
(`Operation.suppressed`, `Suppression`: `chosen` — gewählt oder mitruhend,
`expects` — was seine Verweise trafen, `fits` — die Passungen, die mit ihm
ruhen). `evaluate` überspringt ihn mit Info-Befund (`history.step_off`,
`history.step_resting`, Handlung *Schritt einschalten*); ein Körper, den nur
er anlegt, fehlt (`_absent_objects`), und ein Ganzszenenschritt wie Anordnen
nimmt, was da ist (`_without_absent_inputs`). Wer einen fehlenden Körper
braucht, ruht beim Planen mit; kommt er trotzdem an die Reihe, hält
`evaluate.needs_resting_step` an. `fits.paused_fits` nimmt ruhende Passungen
aus der Prüfung, `orphans.references` fragt nicht nach ruhenden Schritten.
Beim Ausschalten nimmt `revise` jeden Schritt mit, dessen Verweis sein
Merkmal verlöre; hielte die Kette an einem anderen an, schreibt es nichts und
bietet *Diesen Schritt mit ausschalten* an. Einschalten holt die
mitruhenden zurück (`_roots_of`).

## Die Karte

**Das Dokument**

| Datei | Rolle |
|---|---|
| `project.py` | Der Container (§16.1): `save()`, `load()`, Autosave, Wiederherstellung, Prüfsumme |
| `serialise.py` | Dokument zu Daten und zurück — Parameter, Passungen, Quellen, Herkunft, Transaktionen, Chat |
| `migrations.py` | `FORMAT_VERSION` und die Kette `vN → vN+1`. **Ältere Migrationen werden nie zusammengefasst** |
| `gathered.py` | Große Sammelwerte wandern aus dem Stapel in den Container (§12) |
| `foreign.py` | Was eine fremde Projektdatei mitbringt, das nicht nur Geometrie ist (§32) |

**Stapel und Auswertung**

| Datei | Rolle |
|---|---|
| `history.py` | Stapel, Transaktionen, Undo (§15.4, §15.5). `OperationDraft` ist der Schritt, bevor er zählt; `RevisionPlan` der Umbau, bevor er zählt |
| `revision.py` | Den Verlauf umbauen (RM-188 P7): `dependencies`, `step_needs`, `revise` (isoliert rechnen, Verweise folgen lassen, fragen oder absagen), `commit` |
| `bundling.py` | Welche Züge zu einem Schritt verschmelzen (§15.5) — **opt-in je Operation**: wer keine Kumulationsregel hat, bekommt einen eigenen Schritt |
| `evaluate.py` | Die Auswertung (§15.1) |
| `edge_binding.py` | Ausdrücklich gewählte Kanten **vor** dem Verbrauchercache am aktuellen Eingang binden; Kollisionen fragen, die Antwort liegt als `edge-answer:` in `Operation.matches` (§21.3, P1.4c) |
| `cache.py` | Ergebnis-Cache über dem Operations-Hash, im Speicher und auf der Platte |
| `hashing.py` | Stabile Hashes: `operation_hash()`, `object_hash()`, `profile_key()` |
| `parameter_usage.py` | Direkte und abgeleitete Projektparameterverwendungen je Operationsfeld (§13) |
| `cancel.py` | Kooperativer Abbruch (§15.6, §2.8) |

`evaluate()` ergänzt jedes Ergebnis um `parameter_usage`: belegte direkte
und abgeleitete Leser im aktuellen Operationsstapel. Die Geometrieauswertung
bleibt in `_evaluate()`. Ein Fehler der Verwendungsabfrage erhält ihr Ergebnis
und steht separat in `parameter_usage_error`; `None` darf nicht als leere
Verwendungsliste ausgegeben werden. Skizzen, Stellungen und Organizer-Aufteilungen
teilen die strengen Sammler aus `nested_references(strict=True)`. Dieselben
Layoutbezüge fließen in den Operationshash ein, auch wenn der Ausdruck nur
an einer einzelnen Trennwand oder einer Rasterzahl steht. Reine Parameterketten ohne
lesenden Schritt bleiben ungenutzt. Diese Auskunft wird nicht ins Projekt
geschrieben und ändert weder Parameterwerte noch Netzgeometrie.

Zusätzliche Materialrollen einer Operation stehen in `material_params` am
Registereintrag. Der Cache berücksichtigt deren vollständige geometrisch
relevante Profile mit dem aktuellen Druckprozess, einschließlich Kalibrierung.
Eine geänderte Einlagenpassung darf deshalb trotz gleicher Profilkennung
kein Ergebnis einer früheren Kalibrierung laden.

**Vier Fragen beantwortet erst der Endstand**, und deshalb stehen sie in
`evaluate.py` und in keiner Operation: `check_placement` (liegt der Körper auf
dem Bett), `check_bodies_in_one_place` (zwei Körper am selben Ort),
`check_thin_walls` (was von der Wand übrig ist, RM-127) und
`check_form_deviation` (liegen belegte Punkte neben der Form, die sie tragen:
`fit_error` über `units.MAX_FACET_SAG` — ein Befund mit Maß am schlimmsten
Merkmal, der Weg in die Analysekarte „Formabweichung" nach §18.4; bis zum
21.09.2026 stand an jedem Körper mit belegten Flächen stattdessen ein Satz,
dass es die Karte gibt, und kein Quader erreichte mehr „druckbereit"). Den
ersten dreien ist
dasselbe gemeinsam: Die Antwort hängt an einem **Verhältnis**, das ein
späterer Schritt noch umdreht. Eine Wand steht in keinem Merkmal — sie
entsteht zwischen einer Bohrung und dem Mantel um sie herum
(`perceive.relations.thinnest_sleeve` — dieselbe Regel wie `sleeve_at`, aber
in einem Durchgang über den ganzen Körper statt einem je Merkmal), und wer
aufbohrt und danach außen wächst, hat am Ende eine gute. Die Grenze kommt je
Körper aus `profiles.analysis_limits`: Körpermaterial und tatsächlich benutzte
Spulen bestimmen die Mindestwand samt ihrer Kalibrierung. Unbekannte Materialien
übernehmen keine fremde Kalibrierung (Regel 7); ohne Profil gibt es keine Aussage.
Gemeldet wird je Körper einmal,
die dünnste Stelle, mit beiden Merkmalen und dem Ort der Bohrung — damit der
Klick im Prüfbericht irgendwohin führt (§2.7).

Die Warnungen **in** den Operationen bleiben, wo sie stehen: `hollow` spricht
über den Wert, den jemand eingetragen hat, und der bleibt wahr, gleich was
danach kommt.

**Bedeutung über der Geometrie**

| Datei | Rolle |
|---|---|
| `fits.py` | Passungen zwischen Merkmalen (§14) — Verletzungen werden erkannt, nicht stillschweigend gerechnet |
| `orphans.py` | Merkmalsverweise, die ihr Merkmal verloren haben (§21.3). Statt zu raten: `question_for()` und `candidates_of()`. **Die Kandidaten folgen der Objektidentität durch den Stapel** (`lineage()`, RM-023): Nach einer Zerlegung trägt nur das erste Stück die alte Kennung, und der Verweis findet sein Merkmal am abgetrennten Körper wieder — aber nur dort, nicht an jedem fremden mit demselben Namen |
| `placement.py` | Dialogvorbelegung und genaue Oberflächenplatzierung am Originalnetz (§18.5). `seat_of` beantwortet die Frage daneben: **wo sitzt, was schon da ist** — die Trägerfläche eines erkannten Merkmals samt seiner Mündung, für die Maßlinien am gewählten Merkmal |

`placement.bore_step_of` verbindet eine eindeutig gekoppelte Bohrung mit ihrem
abgeschlossenen ursprünglichen `drill_hole`-/`drill_brep_hole`-Schritt. Maßgeblich
sind Merkmalsherkunft und die zeitliche Eingabe-/Ausgabekette; eine gleiche
frisch vergebene Kennung oder der letzte Objekterzeuger genügt nicht. Der Helfer
rechnet keinen Verlauf und liefert ausschließlich ursprüngliche Schrittwerte,
auch nach Transformationen. Mehrere lebende Nachkommen, nicht belegte Ketten
und spätere Formänderungen wie `resize_hole` ergeben keine Einzelzuordnung.
Die historische Vorschau samt Folgeauswertung bleibt beim bestehenden
`change_op`-Weg. `evaluate._feature_originators` stempelt wirklich neue Netz-
und exakte Merkmale gleich; vorhandene Erzeuger übernimmt gemeinsam
`perceive.matching.inherit_originators`, auch im regulären `apply_mapping`.
Importmerkmale und mehrdeutige Kandidaten erhalten keinen geratenen Ursprung.
`placement.seat_for_bore_step` bestätigt den ursprünglichen Flächenbezug am
Prefixkörper aus aufgelösten Schrittwerten, ohne ein Hilfsmerkmal zu erfinden.
Bei endlicher Tiefe muss die ursprüngliche Mündung auf der Fläche liegen;
durchgehend wird genau eine zusammenhängende Materialsäule verlangt. Der
Anzeigepunkt ersetzt weder Originalposition noch Mittenanker im Entwurf.
`DRILL_OPERATIONS` bindet beide DrillParams-Zwillinge außerdem an dieselbe
Platzierbarkeit, den Flächenanker und den vorhandenen lokalen Bohrwerkzeugbau.
Die Auswahl einer neuen Fläche setzt bei beiden den Mündungsanker; ohne
ausdrückliche Lageänderung bleibt der ursprüngliche Auftrag erhalten.

**Operationen dieses Gebiets**

`ops.py` (Umbenennen, Löschen, Duplizieren, Muster) · `variants.py` (der
Variantengenerator, §28.3)

Der Variantengenerator **graviert jedem Teil seinen Wert in die Oberseite**
(`_marked`, RM-147) — eingelassen, mit der Größe aus dem Teil und der
Untergrenze aus der Düse (`label_ops.too_thin_to_print`). Der Objektname trägt
ihn nur in der Szene, und die ist zu, sobald die Teile vom Bett kommen; wo kein
Platz dafür ist, steht `variants.no_mark` im Bericht statt einer Zahl, die
niemand lesen kann. Dass hier Geometrie außerhalb einer Operation entsteht, ist
dieselbe Ausnahme wie beim Anordnen daneben: Was zurückkommt, ist ein
Druckauftrag und kein Dokumentzustand (Regel 2).

Unter der gesamten Schrift prüft `_marked` den Materialraum bis zur
Gravurtiefe plus Mindestwandstärke des Profils. Die Tiefe entspricht drei
Druckschichten einschließlich der im Projekt gewählten Schichthöhe; die
kleinste Schrift ergibt sich aus ihrer Kontur und der schmalsten Druckbahn.
Fehlt dort Material, bleibt
das Teil mit `variants.no_mark` unverändert. Die Gesamthöhe allein reicht
nicht: Auch ein hoher Hohlkörper kann eine dünne Decke haben.

`History.apply` führt während der Planung die lebenden Objektkennungen nach
jedem Schritt fort. Ein im selben Bündel verbrauchter Eingang ist für den
nächsten Schritt ungültig; die Ablehnung lässt das Dokument unverändert.
Die Auswertung bereitet alle Ausgabeobjekte einschließlich Merkmalszuordnung,
Hashes und Namen vor, bevor sie Eingänge verbraucht. Eine angehaltene
Zuordnung liefert dadurch den letzten vollständig gerechneten Szenenzustand.

`OperationSpec.cache_version` bezeichnet den implementierten Bausteinstand.
Der Operationshash enthält diesen Wert zusätzlich zu Parametern und
Eingängen. Ein ersetztes Rezept entwertet dadurch auch bereits vorhandene
Ergebnisse im Speicher- und Dateicache. Die Version beschreibt den geladenen
Code beziehungsweise die registrierten Rezeptdaten, nicht eine inzwischen
anderweitig geänderte Datei.

`CACHE_FORMAT_VERSION` versieht auch den Operationshash mit dem Stand der
Geometrie- und Merkmalsauskunft. Eine geänderte Erkennung entwertet damit
Speicher- und Platteneinträge gemeinsam. Dokumentwerte und gespeicherte
Operationen bleiben dabei unverändert; die Cacheversion ist kein Projektformat.

`object_hash(features=..., check_cancelled=...)` bindet die tatsächlich
veröffentlichten Merkmale an Folgeschritte: Zuordnungsschlüssel, vollständige
Geometrieparameter, Originaldreiecke und Teilträger, Quellen und Erzeuger.
Der gemeinsame `cache.feature_to_data`-Codec trägt dieselbe Auskunft auf die
Platte. Stabile Teilhashes entstehen nacheinander je Merkmal mit demselben
Abbruchrückruf (`hashing.feature_digest`: Dreiecksnummern als `int64`-Bytes,
Fließkommawerte über `float()`, damit ein `np.float64` und seine Rundreise
durch die Platte denselben Schlüssel tragen); eine Gesamt-JSON aller Merkmale
wird nicht aufgebaut. Innerhalb einer Auswertung hält `FeatureMemo` den
Teilhash je Merkmalsobjekt — ein Merkmal, das unverändert durch fünf Schritte
reist, wird einmal gehasht.
Gleiche reservierte Namen beweisen keine gleiche Bindung. Der rohe
Operationshash bleibt dagegen unabhängig von gespeicherten Zuordnungsantworten,
weil das Operationsergebnis vor seiner aktuellen Zuordnung wiederverwendet wird.

Das gilt auch für zuvor unerkannte analytische Träger in NURBS: Ein neu
bestätigtes Flächen- oder Bohrungsmerkmal muss durch Import und Folgeoperationen
hindurch neu berechnet werden. Exakte Körper werden weiterhin nur im Speicher
gehalten; der Plattencache bewahrt ausschließlich seine unterstützten Netze.

`parameter_uses` beginnt bei den Feldern des aktuellen Operationsstapels und
folgt deren Projektparametern durch die Ausdrucksabhängigkeiten. Jeder
Parameter erhält seine direkten und abgeleiteten Fundstellen mit Schritt
und Feld; reine Referenzketten ohne lesende Operation bleiben ungenutzt.
Skizzen und Stellungen verwenden `nested_references(strict=True)`. Dessen
Sammler parsen ihren Text einmal und reichen unlesbare Inhalte als Fehler
weiter: Ohne verlässliche Auskunft darf keine Leeranzeige „ungenutzt“ behaupten.

Lineare und kreisförmige Muster bewegen Kopien über `transform.moved_object`.
Der gemeinsame Weg erhält Körperart, native Flächenzuordnung und die
Merkmale im Ergebnisraum; die Kopie bleibt anschließend im selben Kern
bearbeitbar. Die unveränderte erste Kopie benötigt keine Transformation.

Muster führen die Merkmale je Kopie im Ergebnisraum mit, ohne gemeinsame
Transformationsmatrix. Bei Einzelausgaben folgt nur ein unverändert geerbtes
Merkmal der gemeldeten Matrix. `_inherited_features` vergleicht dafür alle
Feature-Felder und die kanonischen Parameterwerte; JSON-Listen aus dem
Plattencache und gleichwertige Tupel gelten gleich. Ausdrücklich neu berechnete
Merkmale werden nicht nochmals transformiert. Die globale und lokale
Zuordnung lesen dieselbe maßbewusste Transformationsauskunft; auch bei
überschrittenem Merkmalsbudget dürfen keine ungeprüften alten Maße zurückkehren.

## Grenzen

Was hier einzuhalten ist, steht in `.claude/rules/operationen.md` unter
„Szene: Platzierung, Kennungen, Cache, Projektdatei“ — die Karte nennt nur,
wo es eingelöst wird: `placement.py` (Oberflächenplatzierung, Sichtstrahl,
geteilte Werkzeuggeometrie), `evaluate.py` (reservierte Merkmalskennungen,
Objektzahländerung, `OpContext.scene` nur lesend), `cache.py` (versionierte
geometrische Auskünfte), `history.py` (`repair_and_retry` — Reparieren und
erneut versuchen — und `split_and_retry` daneben, dasselbe Muster mit *In
Einzelteile zerlegen* statt der Reparatur, `decimate_and_retry` mit *Dreiecke
verringern*, alle über `_retried_after`),
`project.py` und `migrations.py` (keine absoluten Pfade, kein Code, die
fünf Schritte eines Formatwechsels). Die Dreiecksgrenze der
Merkmalerkennung, `FEATURE_LIMIT_TRIANGLES`, liegt in `perceive/local.py`;
`evaluate.py` exportiert den bisherigen Namen weiter. Oberhalb der Grenze
misst `_measured_locally` bekannte Merkmale örtlich nach (`detect_known`,
mit `required` aus `_needed_after`), bei unveränderten Dreiecken
(`_same_triangles`) gar nicht und nach einer belegten starren Bewegung nur,
was die Bewegung nicht exakt trägt (`standing`, derselbe Beleg
`perceive.features.moved_twin` wie für `carry_detection`), nach einer
belegten Teilung gar nicht — die übertragenen Merkmale stehen
(`refined_twin`, `refined_features`);
`recognition_of` trägt die Ladewahl je Körper durch den Lauf. Was dabei
gilt, steht in `kern.md`.

**Ein exakter Körper wird nicht neu erkannt.** Die Erkennung misst an
Dreiecken; ein `Solid` hat keine, seine Merkmale liest
`brep.features.features_of` aus der Topologie, und zwar in der Operation, die
ihn baut. `transform.moved_object` berechnet bei einer Transformation bereits
die aktuellen Merkmalsmaße und ordnet ihre Dreiecksauswahl über die native
Flächenhistorie neu zu. Unverändert geerbte Merkmale anderer Operationen
führt `evaluate._carried_along` anhand der gemeldeten Matrix nach, oder anhand
der reinen Verschiebung, die `_shift_between` aus zwei Hüllquadern abliest.
Schon ausdrücklich nachgeführte Merkmale werden nicht nochmals bewegt.

**Am exakten Körper sagt ein Umbau öfter ab als am Netz.** `features_of`
nummeriert Bohrungen nach Lage; eine neue links von einer vorhandenen nimmt
ihr den Namen, und hängt ein späterer Verweis daran, hält die Auswertung mit
`NativeReferenceLost` an — auch ohne Umbau, wer in dieser Reihenfolge baut.
Ein Verschieben oder Einfügen, das diese Reihenfolge herstellt, läuft in
denselben Halt; `revise` schreibt dann nichts (im Fenster und auf der
Kommandozeile stellt der Kern vorher seine Rückfrage). Am Netz folgt derselbe
Verweis seinem Merkmal. Offen unter RM-188 P7.

Bedingte Passungen speichern `when_positive=(operation_id, parameter_name)`.
Ihre Prüfung verlangt das zugehörige Dokument; fehlt es beim Aufruf, ist
das ein Programmfehler und kein ungültiger Kundenparameter.
`fits.pair_problem` prüft die fachliche Eignung für die Auswertung und die
manuelle Anlage gemeinsam; `pair_kinds` bietet nur passende neue Beziehungen
an. Durchmesser allein belegen keine Innen-/Außenrolle. Deckelmerkmale tragen
dafür `fit_role` am Erzeuger; Gewinde tragen `internal` und eine positive
Steigung. Historische radiale Passungen an Gewinden bleiben radiale Prüfungen;
die Gewindepassung prüft zusätzlich die Steigung. Bündige Flächen werden mit
normalisierten Normalen auf Parallelität und Ebenenabstand geprüft.
Radiale Netzmaße tragen neben dem geschätzten Kreisradius das tatsächliche
Band `radial_min`/`radial_max`. Ein zum Profil passendes Kreismaß belegt bei
groben Facetten noch kein Spiel: `fits.check` prüft zusätzlich die konservative
Differenz beider Bänder. Ein nicht belegtes Spiel erscheint als
`fit.mesh_uncertain`, kein daraus behaupteter Kollisionsnachweis. Fehlende
Bandhälften oder ungültige Werte bleiben ausdrücklich nicht messbar.
Presspassungen dürfen beabsichtigte Überdeckung tragen; Spielpassungen
erhalten bei möglicher Überdeckung auch innerhalb der Anzeigeauflösung einen
Befund. Diese Grenzen ersetzen weder Fertigungsspiel noch eine Einbauprüfung.

Zusätzlich prüft `fits.check(..., cancelled=...)` bei radialen Paaren die
tatsächlichen vollständigen Körper in der aktuellen Lage — **nur, wenn die
Lage belegt ist** (`_pose_proven`). Unterschiedliche Platten, fehlende
Achse/Mitte/Tiefe, seitlicher Versatz und fehlende axiale Überlappung sind
**kein Befund**: Angeordnete Druckteile belegen keine Einbaulage, und eine
Warnung darüber war nicht behebbar (*Anordnen* zieht die Teile gerade
auseinander) — sie stand bis zum 21.09.2026 an jedem Passungsbeispiel. Eine
leere Verschneidung ist ebenfalls kein Befund; die Zahl dazu gibt
`fits.overlap(scene, fit)` als `GeometryProbe` (Quelle, Volumen,
`intersects`) — die eigene Auskunft für die Passungskarte und jeden, der das
Maß braucht, ohne den Bericht zu lesen. Netze laufen unverändert durch die
direkte Verschneidung mit gültiger leerer Ausgabe, ohne Reparatur, Jitter oder
Voxel. Native Körper
werden auf privaten Kopien validiert und nichtdestruktiv verschnitten; auch
Prüfkennzeichen der Originale bleiben erhalten. Ein gültiger nativer Kontakt
ohne Solid ist leer, jeder Solid mit positivem integriertem Volumen zählt
als Überdeckung. Keine Längentoleranz wird als Volumengrenze verwendet.
Gemischte Zwillinge liefern ausdrücklich eine Netznäherung
(`fit.geometry_approximate`: Warnung bei Überschneidung, sonst Hinweis).
`fit.geometry_failed` ersetzt keinen Fehler durch Kollisionsfreiheit; Abbruch
wird weitergereicht. `fit.press_unverified` ist ein Hinweis: Übermaß ist bei
einer Presspassung vorgesehen, und die starre Probe bestätigt weder Montage
noch Verformung — sie nennt die gemessene Überschneidung, oder dass es keine
gibt. `fit.collision` bleibt die Warnung. Kollisionsfreiheit gilt
ausschließlich für die geprüfte Lage, nicht für den Montageweg oder das
Druckverhalten. Maßbefunde bleiben daneben bestehen.
Auswertung veröffentlicht Cacheeinträge und Fertigmeldung erst nach allen
Abschlussprüfungen und deren letzter Abbruchkontrolle.

`flush` behält seine Ebenenregel aus Normalen und Abstand: gleichgerichtete
oder getrennte koplanare Flächen sind zulässig, Kontakt ist keine Bedingung.
Daneben läuft dieselbe vollständige Körperprobe ohne radiale Voraussetzungen.
Zwei verschiedene Körper auf derselben Platte werden in ihrer aktuellen Lage
geprüft; verschiedene Platten und zwei Merkmale desselben Körpers sind keine
Lage und kein Befund, und `overlap` gibt dort `None` statt eines erfundenen
Nullvolumens. Auch ein nicht messbares Ebenenpaar kann bei auflösbaren
Körperverweisen einen unabhängigen Körperbefund tragen. Fehlende Merkmale
bleiben Fehler. Die bündigen Körpertexte bestätigen weder Flächenkontakt noch
Montageweg; Ebenenverletzung und Körperbefund bleiben nebeneinander sichtbar.
Bericht, Steckbrief, Analysekarte und Export übernehmen dieselben Befunde.

`fits.active_fits(document)` liest das aktuelle Op-Feld einschließlich
Projektparameterausdrücken. Ausschließlich gültige Werte <= 0 deaktivieren
die Passung; fehlender Schritt oder ungültiger Ausdruck bleibt ein Befund.
Das Dokument behält auch inaktive Beziehungen für spätere Änderungen und Undo;
Auswertung und Slicer verwenden die aktuell aktiven Passungen.
Eine Neuplanung des Suffix überträgt die Bedingung mit der Alt-Neu-Zuordnung
der Schrittkennungen in derselben `DocumentChange`. Ausdrückliches Entfernen
des Bedingungsschritts entfernt seine gebundenen Beziehungen; Undo stellt
Schritte und Bedingungen gemeinsam wieder her. Unbekannte Verweise aus einer
Datei bleiben dagegen prüfbare Fehler und werden nicht still gelöscht.

Migration 19→20 rekonstruiert die gespeicherten Verlaufszustände über den
regulären Undo-Vertrag. Eindeutige alte Deckelpaare erhalten dort die jeweils
gültige Schrittkennung; belegte flache Deckel ohne jemals gespeicherte
Beziehung erhalten eine bedingte Passung aus `lid_flow.fit_for_lid`.
Ausdrücklich entfernte Passungen werden dadurch nicht neu angelegt.

`placement.prepare_tool` und `placement_tool` reichen aufgelöste Projektmaße
an Bausteine mit `kind="sketch"` weiter. Die Zeichnung bleibt ein gespeicherter
Ausdruck; nur der vorübergehende Bau erhält Zahlenwerte.
