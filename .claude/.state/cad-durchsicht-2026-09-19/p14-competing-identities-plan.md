# P1.4b – konkurrierende alte Identitäten gemeinsam offenhalten

Ausschließlich lesende Konzeptnachprüfung während des Root-Entwicklungstors.
Keine Produktänderung, kein Test oder Rechenexperiment ausgeführt. Die
konkrete bisherige Solverantwort stammt aus der bereits vorhandenen
unabhängigen P1.4-Gegenprobe; zusätzliche Fehlerfolgen unten werden aus dem
gelesenen Code abgeleitet und nicht als neu ausgeführter Lauf ausgegeben.

## Ergebnis und Abgrenzung

P1.4a beschleunigt die vorhandene Zuordnung und bewahrt absichtlich ihre
Ergebnisse. Die Konzeptzeile `konzept-vollwertiges-cad-2026-09.md:1009`
verlangt zusätzlich korrekte Mehrdeutigkeit bei dichten/symmetrischen Fällen.
Dieser Teil ist noch offen. Eine zufällig erhaltene **alte** Identität wird
nicht dadurch fachlich eindeutig, dass der globale Solver sie reproduzierbar
wählt oder die Ergebnisabbildung technisch injektiv ist.

Kleinste vollständige Folgeeinheit: bestehende Ergebniszuordnung um
konkurrierende alte Ansprüche ergänzen, die betroffenen Identitäten als
gemeinsame Konfliktgruppe offenhalten und gespeicherte/manuelle Antworten
nur als gemeinsam geprüfte injektive Teilabbildung übernehmen. Die
vorhandene Raumfilterung, Kostenformel und der SciPy-Solver bleiben.
Keine neue Matchingbibliothek und kein alternatives Optimierungsverfahren.
Merkmalsobergrenze und Leistung bleiben die gesonderte Release-Aufgabe.

## Belegter Ist-Vertrag und fehlende Sperre

| Anschluss | Gelesener Befund |
|---|---|
| `matching.match`, insbesondere Zeilen 382–419 | Rivalen stammen aus der zugeteilten **alten Zeile**. Unzugeteilte alte Ansprüche werden verwaist; ähnliche Ansprüche in derselben neuen Spalte werden nicht als solche geprüft. |
| Gegenfall alt x=`[0,1,1,1]`, neu x=`[0,0,1]` | Der globale Solver erhält `old_2→new_2` als eindeutig; `old_1` und `old_3` sind gleich gute alte Bewerber. Bei x=0 ist dagegen die Richtung ein alter→zwei neue schon mehrdeutig. |
| `evaluate._with_features`, Zeilen 1820–1853 | Nur `matched.ambiguous` erreicht die Rückfragen. `referenced` unterdrückt Fragen zu unbenutzten alten IDs. Gespeicherte Antworten und neue Antworten werden einzeln in `matched.mapping` geschrieben. Keine Prüfung auf bereits beanspruchte neue Ziele. |
| `matching.resolve`, Zeilen 570–628 | Prüft einen gespeicherten geometrischen Fingerabdruck gegen dessen neue Kandidaten. Kennt keine anderen alten Ansprüche, keine reservierten Ziele und keine Antworten derselben Konfliktgruppe. |
| `matching.apply_mapping:472` | `reverse = {value: key for key, value in result.mapping.items()}` verwirft bei zweimaligem neuen Ziel den früheren alten Schlüssel still. `taken` verhindert Namenskollisionen beim Frischbenennen; es prüft keine Doppelbelegung in `mapping`. |
| `matching.inherit_originators:439` | Übernimmt beim ersten passenden alten Anspruch einen fehlenden `created_by`. Ein späterer Anspruch überschreibt einen nun vorhandenen Erzeuger nicht. |
| `evaluate._feature_originators:1317` | Verhindert eine neue Erzeugerbehauptung für bereits als mehrdeutig erkannte Kandidaten. Es erkennt keine zuvor übersehene Konkurrenz selbst. |
| `_with_features` nach Mehrdeutigkeit | Verwaisungs-/Verweisprüfung kann einen fehlenden Namen bemerken. Die zufällig weitergeführte alte ID ist aber vorhanden; ihr Verweis wird dadurch nicht als falsch erkannt. |
| `History.record_matches:923–929`, `Session._on_finished:3235` | Gespeicherte Antworten werden pro Operation zusammengeführt und das Projekt wird geändert markiert. Keine Zielbelegungsprüfung. |

**Konkrete Folge aus dem Code:** Bei `mapping={a:x, b:x}` kann
`inherit_originators` den Erzeuger von a an x hängen, während `reverse`
anschließend x unter b benennt. Das Ergebnis ist kein zweites identisches
Objekt, sondern ein still verlorener alter Anspruch mit möglicherweise
widersprüchlicher Herkunft. Eine spätere Kollisionssperre ist in diesen
gelesenen Pfaden nicht vorhanden.

Die vorhandenen Tests sichern überwiegend ein altes Merkmal zwischen zwei
neuen Kandidaten, unbeantwortete Rückfragen, Fingerabdruck nach Umnummerierung
und eine gespeicherte Antwort. Sie sichern nicht mehrere Antworten mit
demselben Ziel. Der P1.4a-Gegenfall hält die alte Antwort ausdrücklich als
Referenz fest; P1.4b muss genau diesen fachlichen Erwartungswert ändern.

## 1. Minimaler Konfliktvertrag im Matcher

`mapping` enthält ausschließlich fachlich freigegebene und injektive Paare.
`ambiguous` darf zusätzlich einen alten Anspruch mit **einem** neuen Kandidaten
enthalten: unklar ist dann dessen alte Identität, nicht seine neue Position.
Das ist eine präzise Erweiterung der Feldbedeutung; sie muss im Dataclass-
Vertrag und den Verbrauchern stehen. Ein neues persistiertes Merkmalsmodell
ist dafür nicht nötig. Zusammenhängende Konfliktgruppen lassen sich aus
dieser kleinen bipartiten Auskunft ableiten.

Vorgeschlagener enger Aufbau auf dem vorhandenen Solverergebnis:

1. Vorhandene Zeilenrivalen unverändert ermitteln. Diese bleiben ein
   legitimer Anlass zur Rückfrage, auch wenn der globale Solver eine
   eindeutige Gesamtsumme gefunden hat.
2. Für bislang **nicht freigegebene alte Ansprüche**, insbesondere
   unzugeteilte/verwaiste alte Zeilen, die akzeptierten Kandidaten gegen
   deren gegenwärtigen zugeteilten alten Besitzer prüfen. Ein zusätzlicher
   Anspruch ist ein Rivale, wenn seine Originalkosten unter derselben
   vorhandenen Grenze `zugeteilte_Kosten*(1+AMBIGUITY_MARGIN)+AMBIGUITY_FLOOR`
   liegen. Keine neue Zahl, kein Vergleich gegen `KIND_PENALTY` als
   angeblichen geometrischen Bestwert. Besitzer und Rivalen werden gemeinsam
   offen, statt dem Besitzer eine sichere alte Identität zu bescheinigen.
3. Enthält eine offene Kandidatenliste ein Ziel aus einem noch freigegebenen
   Paar, muss die Gruppe diesen Besitzer einbeziehen oder den Kandidaten
   begründet als bereits fest belegt ausweisen. Empfohlen: bei geometrisch
   ermittelten Zuordnungen gemeinsame Gruppe mit diesem Besitzer bilden;
   eine belegte native Historienabbildung oder bereits gemeinsam bestätigte
   Nutzerentscheidung kann dagegen wirklich fest sein. Eine beliebige
   erste Solverwahl ist kein solcher Beleg.
4. Über geteilte Ziele und zugehörige Besitzer die Gruppen schließen. Alle
   betroffenen alten IDs aus `mapping` und aus bloßer `orphaned`-Behauptung
   entfernen; ihre noch möglichen aktuellen Nachfolger in `ambiguous`
   erhalten. Solange keine Entscheidung vorliegt, wird keine von ihnen an
   die aktuelle Geometrie umbenannt und keine Herkunft daraus geerbt.

**Wichtige Begrenzung:** Nicht schlicht alle nahen Spaltennachbarn als
Mehrdeutigkeit deklarieren. Zwei unveränderte, nahe Bohrungen haben jeweils
ihren eigenen besseren und freien Nachfolger; sie dürfen nicht bei jedem
Lauf fragen. Konkurrenz entsteht hier durch einen bisher nicht sicher
untergebrachten Anspruch bzw. eine bereits offene Alternativwahl. Der
unveränderte 1056er Rasterfall mit getrennten strikten Minima bleibt still.

Die formale Abnahme dieser Regel braucht sowohl symmetrische
Viele-alte→wenige-neue-Fälle als auch alternierende Zuordnungen und unveränderte
Nachbarmerkmale. Sie ist eine absichtliche fachliche Änderung gegenüber P1.4a;
kein Anspruch auf identisches altes `MatchResult` für diese Konfliktfälle.

## 2. Gemeinsame Antwortübernahme statt erster Antwort gewinnt

Eine Konfliktgruppe wird vorübergehend in einem lokalen Entscheidungssatz
bearbeitet. Keines ihrer Paare wird während einzelner Fragen direkt in das
veröffentlichte `matched.mapping` geschrieben. Bereits außerhalb der Gruppe
eindeutig belegte neue Ziele sind reserviert. Jeder Gruppenentscheid muss
denselben aktuellen neuen Kandidaten höchstens einmal belegen.

Für das eine neue Merkmal x bei drei alten Identitäten a/b/c lautet die
Frage sinngemäß: „Mehrere bisherige Merkmale könnten diesem Formdetail
entsprechen. Welcher bisherige Bezug soll erhalten bleiben?“ Zur Wahl stehen
a/b/c und „Keinen bisherigen Bezug übernehmen“. Die Antwort entscheidet
ausdrücklich, welche alte Identität fortgeführt wird. Die anderen gelten
danach als nicht fortgeführt; ihre bisherigen Verweise müssen sichtbar
verwaisen bzw. nach dem vorhandenen Verweisweg bearbeitet werden.

Bei mehreren neuen Zielen bleibt der Ablauf schrittweise, aber mit einer
gemeinsamen Belegung: nur noch zulässige alte/neue Paare anbieten, besetzte
Ziele nicht nochmals auswählen lassen, eine bewusste Änderung einer schon
getroffenen Gruppenwahl gemeinsam zurücknehmen. Nicht alle Permutationen
als Liste erzeugen. Abbrechen lässt die ganze Gruppe und die Operation
unveröffentlicht. Ein fehlender Ask-Verbraucher erhält einen verständlichen
`AmbiguityError` mit Handlungsmöglichkeiten, wie bisher.

Der `referenced`-Filter bleibt: Eine vollständig unreferenzierte offene
Gruppe löst keine unnötige Frage aus und behält aktuelle frische Namen.
Sobald eine alte ID der Gruppe verwendet wird, muss die Frage aber den
**gesamten** relevanten Wettbewerb nennen. Allein den verwiesenen alten
Anspruch übrigzulassen und dadurch zum Gewinner zu machen wäre wieder Raten.

Ein kleiner gemeinsamer Übernahmehelfer prüft vor dem Abschluss:
Schlüssel gehören zu dieser Gruppe, Ziele existieren und sind zulässig,
Zielwerte sind paarweise verschieden und kollidieren nicht mit bestätigten
außenliegenden Paaren. Erst dann werden Mapping, offene/verwaiste IDs,
`fresh` und Erzeugerauskunft gemeinsam aktualisiert. Dieselbe Injektivitäts-
Prüfung muss als letzte Grenze vor `inherit_originators` und `apply_mapping`
gelten. Ungültige Ergebnisse werden angehalten, niemals per `dict`-Reihenfolge
oder stiller Zielentfernung „repariert“.

## 3. Gespeicherte Antworten und Projektformat

`resolve` bleibt ein geometrischer Kandidatenauflöser, keine Zuteilung.
Alle gespeicherten Antworten der Gruppe zunächst als Vorschläge auflösen,
anschließend gemeinsam prüfen. Zwei Fingerabdrücke, die aktuell dasselbe
neue Merkmal treffen, dürfen weder durch Einfügereihenfolge noch durch
„wer zuerst aufgelöst wurde“ gewinnen. Die widersprüchliche Gruppe fragt
erneut. Ein knapp unterscheidbarer Fingerabdruck bleibt ebenfalls offen.

Eine frühere gewöhnliche Einzelauswahl beweist nicht automatisch, welche
Identität nach einer neuen Verschmelzung mehrerer alter Merkmale überleben
soll. Für diese neue Wettbewerbsart deshalb einen eng begrenzten gespeicherten
Entscheidungskontext vorsehen: betroffener Körper, Menge der alten Ansprüche,
geometrisch wiedererkennbare Zielauskünfte und ausdrückliche Fortführung bzw.
Nichtfortführung. Aktuelle neue Erkennungs-IDs sind weiterhin keine dauerhafte
Identität. Geänderte Beteiligte, verschwundene Ziele oder widersprüchliche
Antworten machen den Wettbewerb wieder offen.

Der kleinste dauerhafte Ort bleibt `Operation.matches`, ergänzt um eine
ausdrückliche Kennzeichnung dieser Gruppenentscheidung. Kein zweiter
Antwortcache und keine neue globale Sitzungsverwaltung. Vor Umsetzung die
konkrete Serialisierungsform festlegen; weil neue Entscheidungsbedeutung und
gespeicherte Nichtfortführung hinzukommen, die Repository-Checkliste für
Dateiformatänderungen einhalten: Formatversion, Migration und Altdateifall.
Das derzeit lockere Dict-Schema in `project.py:905` ist keine Ausnahme von
dieser Regel. Alte reine Fingerabdrücke bleiben im gewöhnlichen Einzelfall
gültig; ohne Wettbewerbskontext sind sie für einen neuen gemeinsamen
Identitätskonflikt keine automatische Freigabe.

Nur eine vollständig geprüfte Gruppe in `recorded`/`EvaluationResult.matches`
übernehmen. Mehrkörperoperationen benötigen dabei einen Körperbezug:
`matches.setdefault(operation.id, {}).update(recorded)` vereinigt derzeit
Antworten mehrerer Ausgaben allein nach alter Feature-ID. Derselbe Name
`hole_1` an zwei Körpern darf den neuen Gruppenkontext nicht überschreiben.
`History.record_matches`, Projektrundreise und Session-Dirtystatus verwenden
weiter den bestehenden Weg. Kein neuer Undo-Schritt nur für die Rückfrage;
die Entscheidung vollendet die auslösende Operation.

## 4. Cache, native/Netz-Verbraucher und Oberfläche

**Nachgelesene native Sicherung:** `brep.edit.transformed_with_faces` verlangt
nach `ModifiedShape` eine vollständige bijektive alte→neue Flächenabbildung
(`edit.py:1054–1074`). `geom.transform.moved_object:210–283` führt damit
Flächen und Teilträger unter ihren vorhandenen Namen nach und behält nur
geometrisch exakt weitergeführte Merkmale. `_carried_along:1222` bewegt
zusätzlich nur wirklich unverändert durchgereichte Merkmalseinträge. Dies
ist eine echte P2.1-Sicherung; sie wird von P1.4b nicht ersetzt.

Der allgemeine native Formänderungszweig ist anders: `brep.features.features_of`
benennt nach aktueller Topologiereihenfolge und Artzähler neu, und
`_with_features:1391` benutzt `match` nur zur Erzeugerübernahme. Er ruft kein
Mesh-`apply_mapping` auf. `carried_face_slots` benutzt Builder-History für
Filamentattribute und sperrt dort widersprüchliche Attributansprüche; dies
ist keine allgemeine Sperre für alte Feature-IDs. `orphans._resolves:382`
prüft wiederum nur die Existenz des Namens im Körper. Eine vorhandene,
aber geometrisch konkurrierende gleichlautende native Kennung würde dort
nicht erneut als unklar erkannt. Die gelesenen STEP-Tests belegen stabile
Namen beim erneuten Laden derselben Datei, nicht beliebige Formänderungen.

Für den engen ersten Schritt genügt deshalb neben der gemeinsamen
Eindeutigkeitssperre und dem Mesh-Antwortvertrag eine ausdrückliche native
Sperre: keine Erzeugerübernahme aus konkurrierenden Paaren; bei einem
referenzierten alten Anspruch ohne native History-Bestätigung vor Rückgabe
des nativen Ergebnisses mit nachvollziehbarer offener Zuordnung anhalten.
Die bloße Existenz desselben Namens darf diesen Halt nicht umgehen.
Unreferenzierte aktuelle native Merkmale behalten ihre Topologiekennungen.
Eine spätere ausdrückliche Referenzneuwahl schreibt den bestehenden
`FeatureRef` um; sie benennt nicht pauschal native Flächen wie Meshmerkmale
um. Damit kann P1.4b enger umgesetzt werden, ohne eine bereits vollständige
native Dialogauflösung für jeden Formänderungsfall zu behaupten.

- `_with_features` läuft auch nach einem Cachetreffer. Die neue Entscheidung
  muss in kalten, warmen und Plattenläufen gleich entstehen; Antworten bleiben
  nach diesem Vertrag außerhalb des Operationshashs.
- `prepare_ops` benutzt `match/apply_mapping` bereits **innerhalb** einer
  Operation, und `CachedResult` trägt deren Merkmalsnamen/-herkunft. Daher
  reicht „Zuordnung läuft nach Cache“ nicht als Beweis gegen alte falsche
  Identitäten. Die bestehende Cache-Kompatibilitätsversion ist bei der
  fachlichen Umstellung anzuheben; sie geht bereits in den Operationshash ein
  und entwertet auch die Speicherebene. Keine neue Cachegattung.
- Ungeklärte/abgebrochene Gruppen dürfen weder Teilobjekte noch Teilantworten
  veröffentlichen oder den abschließenden `pending`-Cachezugang erreichen.
  Das bestehende vorbereitete Ergebnis und der `AppError`-Fang bieten den
  Anschluss; mehr als eine Ausgabe je Operation ausdrücklich prüfen.
- `local._query_is_complete`, Deklarationsabgleich und die Vorbereitungshelfer
  nehmen nur ein freigegebenes Mapping als positiven Beleg. Mehrdeutigkeit
  darf nicht in „gefunden, daher Vorgabename übernehmen“ verwandelt werden.
- Der native Zweig übernimmt derzeit Erzeuger aus `match`, fragt dort aber
  nicht. Native Topologie-/Historienbelege bleiben vorrangige echte Belege;
  rein geometrische Konkurrenz darf weder `created_by` noch einen alten
  Verweis beglaubigen. Native Kennungen nicht pauschal wie Mesh-Erkennungsnamen
  umbenennen. Dieselben fachlichen Gegenfälle für native und Netzmerkmale
  sowie gemischte Operationsübergänge vorsehen.
- `AskRequest` trägt bereits `preview` und körperqualifizierte Kandidaten,
  `MainWindow._on_ask` hebt sie hervor. Matchingfragen reichen momentan nur
  `question/choices` durch; der vorhandene `announce`-Weg wird vor allem von
  `orphans.check` bedient. Für die Gruppenfrage den tatsächlichen
  Zwischenstand samt aktuellen Zielmerkmalen über diesen vorhandenen Weg
  anschließen. Alte Identität und aktuelles Formdetail klar benennen;
  alte IDs nicht gegen die neue Szene als vermeintliche neue Flächen auflösen.
  Wenn eine Antwortzeile eine alte Identität nennt, braucht die Ansicht eine
  explizite Zuordnung der Zeile zum gezeigten aktuellen Ziel, nicht die
  derzeitige Suche nur nach identischem ID-Text.
- Neue Erklärungstexte als deutsche Quellen plus alle fünf Kataloge. Keine
  pauschale Bestätigungsabfrage; dies ist die nötige inhaltliche Entscheidung
  über eine tatsächlich offene Identität. Fensterdateien werden in der
  Entwicklung nur geändert/statisch geprüft und erst beim Release ausgeführt.

## Abnahmekriterien der separaten Folgeeinheit

1. Der konkrete `[0,1,1,1]→[0,0,1]`-Fall veröffentlicht keine beliebig
   ausgewählte sichere Identität bei x=1. Alle drei alten Ansprüche sind
   offen, obwohl nur ein neuer Kandidat vorhanden ist. Umordnung der Eingabe
   verändert nicht die fachlich offene Anspruchsmenge.
2. Ein stark besserer zulässiger alter Anspruch bleibt ohne Frage erhalten;
   unveränderte nahe Zwillinge und das zertifizierte 1056er Raster bleiben
   korrekt still. Zusätzliche Rückfragen dürfen nicht aus bloßer Nähe folgen.
3. Eine manuelle Gruppenentscheidung erhält genau eine gewählte Identität,
   lässt andere Bezüge ehrlich verwaisen und verbindet nicht Namen und
   Erzeuger verschiedener Vorfahren. Zwei gleichzeitig gewählte gleiche
   Ziele werden am gemeinsamen Übernahmevertrag angehalten.
4. Mehrere alte/mehrere neue Kandidaten, alternierende Rivalenketten,
   rechts-/linksrechteckige Fälle sowie ein Kandidat in einer bereits
   bestätigten Außenbelegung bleiben injektiv und nachvollziehbar.
5. Eine unreferenzierte Gruppe fragt nicht und erbt keine beliebige alte ID.
   Bei nur einer referenzierten alten ID werden konkurrierende unreferenzierte
   Ansprüche trotzdem nicht wegdefiniert.
6. Widersprüchliche gespeicherte Fingerabdrücke auf dasselbe Ziel fragen
   gemeinsam erneut. Ein gültiger gemeinsam bestätigter Entscheid übersteht
   neue Erkennungsnummern, warme/Plattencaches, Speichern/Wiederöffnen und
   Undo/Redo; ein neuer Wettbewerb oder geänderte Beteiligte entwerten nur
   seine nicht mehr belegte Freigabe. Historische Einzelfingerabdrücke bleiben
   für ihren bisherigen gewöhnlichen Anwendungsfall lesbar.
7. Gleiche alte Feature-ID an zwei Ausgabekörpern kollidiert weder beim
   Auflösen noch beim Speichern der Antwort. Abbruch oder fehlender Frager
   lässt keine halbe Gruppen- oder Mehrkörperausgabe zurück.
8. Native, Mesh- und gemischte Pfade bewahren Maßquellen, Teilträger,
   Erzeuger und echte native Topologiebelege; unbewiesene Übernahmen bleiben
   offen. Namensreservierung verhindert späteres Wiederbeleben verworfener IDs.
9. Die Gruppenfrage zeigt den tatsächlichen aktuellen Kandidaten und nennt
   den bisherigen Bezug sowie die Folgen seiner Fortführung. Tastatur,
   Abbruch und Hervorhebung hängen am vorhandenen Ask-/Previewweg. Reale
   Fensterabnahme bleibt ausdrücklich Release-Nachweis.

Damit bleibt P1.4a eine geprüfte algorithmische Verbesserung. P1.4b ist eine
eigene fachliche Korrektur mit nachvollziehbarer Migration und Anschluss,
und erst deren Abnahme erfüllt die Symmetrie-/Mehrdeutigkeitsforderung des
Konzepts. Die höhere Merkmalsobergrenze bleibt darüber hinaus bis zum
beauftragten Release-Leistungsnachweis offen.
