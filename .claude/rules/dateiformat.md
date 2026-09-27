---
description: "Projektdatei, Import, Export und Slicer-Übergabe — Migration ist Pflicht, und was nicht in die Datei gehört"
paths:
  - "app/core/ingest/**/*.py"
  - "app/core/export/**/*.py"
  - "app/core/scene/project*.py"
---

# Regeln für Projektdatei, Import und Export

## Migration ist Pflicht, nicht Kür

Eine Projektdatei ist zugleich Fehlerbericht und Archiv. Ändert sich das
Format:

1. `format_version` erhöhen
2. Migrationsfunktion `vN → vN+1` schreiben
3. Beispieldatei der alten Version einchecken
4. Test: die alte Datei öffnet und rechnet **korrekt**, nicht nur fehlerfrei
5. Ältere Migrationen bleiben bestehen und werden nie zusammengefasst

## Was nicht in die Datei gehört

Keine absoluten Pfade. Kein ausführbarer Code. Keine eigenen Bausteine — ein
Projekt verweist auf sie namentlich, und fehlt einer, hält die Auswertung an
und sagt welcher (§24.5, §32).

**Eigene Drucker und Materialien reisen als Daten mit** (Version 30,
`Document.carried_profiles`): die Beschreibung, mit der gerechnet wurde —
Name, Bauraum, Düse, Verfahren, Schichtwerte —, nie ein Pfad, nie Code, und
nur für Kennungen, die nicht mitgeliefert sind. Der zweite Rechner rechnet
damit und bietet an, sie zu übernehmen; kennt er einen Drucker gar nicht,
rechnet er mit dem allgemeinen Drucker desselben Verfahrens und sagt es.
Dieselbe Version stellt Passungen aus *Teilen* und *Deckel* auf `auto:` um:
Sie folgen dem Material ihrer Körper statt dem Projektmaterial des
Augenblicks (Migration 29 → 30, `material_fits_v29.p3d`).

**Ein ausgeschalteter Schritt steht in der Datei, mit dem, was er traf**
(Version 32, `Operation.suppressed`): `chosen` (vom Nutzer gewählt oder
mitruhend), `expects` (Schlüssel, Merkmal, Art, Erzeuger und Abdruck jedes
Verweises zum Zeitpunkt des Ausschaltens) und `fits` (die Passungen, die mit
ihm ruhen). Transaktionen eines Umbaus tragen `revision` (`insert`, `move`,
`suppress`, `reactivate`). Die Stufe 31 → 32 schreibt nichts um — eine ältere
Datei hat keinen ausgeschalteten Schritt; die Schemaprüfung weist einen
beschädigten Eintrag und eine unbekannte Umbauart ab
(`project._validate_suppression_schema`).

**Gleich heißt inhaltsgleich, nicht bytegleich** (RM-106). Zwei Plattformen
schreiben dieselbe Projektdatei mit anderen Deflate-Bytes (zlib gegen
zlib-ng); der ZIP-Kopf nennt kein schreibendes System (`CONTAINER_SYSTEM`).
Wer zwei Dateien vergleicht, vergleicht `project.content_digest`, nicht den
Dateihash. Eingecheckte Beispiel- und Belegdateien werden nicht neu
geschrieben, um sie „gleich" zu machen — ihr Hash ist ihr Beleg.

**Der Exportordner ist der Fall, an dem sich das entscheidet** (RM-141,
Version 23). §29 sagt „Ordner, Format und Übergabeart werden je Projekt
gemerkt" — je Projekt, nicht in der Projektdatei. Format und Namensschema
stehen seither in `Document.export_format` und `Document.export_scheme`, denn
sie gehören zum Teil: Ein Gehäuse für den eigenen Slicer bleibt 3MF, ein
Modell für einen Dienstleister bleibt STL. Der **Ordner** steht in
`UiSettings.export_dirs`, geschlüsselt nach Projektpfad — derselbe Schnitt wie
beim Slicer-Pfad neben der Übergabeart: Der zweite Rechner hat einen anderen
Ordner, aber dieselbe Gewohnheit.

**Und die Sichtflächensperre ist der Fall, an dem sich „Dokument oder Ansicht"
entscheidet** (RM-080, Version 24). „Diese Fläche soll schön bleiben" ist eine
Aussage über das Teil, nicht über die Sitzung: Als Ansichtszustand war die
Markierung nach dem Schließen weg, und der Kunde erfuhr es an dem Schnitt, der
durch die Fläche ging, die er schützen wollte. `Document.protected` hält je
Körper die **Merkmalkennungen** — keine Dreiecke, keine Punkte, denn nur die
Kennungen überleben eine Auswertung (§21); die Punktwolke für die Suche rechnet
`split.protected_patches` einmal beim Start. Kein Verlaufsschritt, wie bei den
Druckeinstellungen: Es entsteht keine Geometrie, der Umschalter ist sein
eigener Rückweg. Ein Rezept trägt keine Sperren (`part_file` weist sie ab) —
sie nennen Körper, die es im eingelesenen Baustein unter diesem Namen nicht
gibt.

## Transaktionstitel

Seit Version 6 trägt ein Titel aus dem Code `title_translatable`: `title` ist
dann die Message-ID (der deutsche Quelltext) und wird erst bei der Anzeige
aufgelöst. Ohne die Markierung ist der Titel wörtlich gemeint — was ein Nutzer
selbst benannt hat, wird nie übersetzt. Wer irgendwo einen Transaktionstitel
vergibt, nimmt `_()` statt `tr()`, sonst friert der Text in der Sprache des
Speicherzeitpunkts ein. Ausnahme: zusammengesetzte Titel wie
`f"{tr('Parameter')} {name}"` bleiben wörtlich — eine Message-ID kennt keine
Platzhalter. Die Titel der Beispiel-Bauer sammelt die Extraktion über
`EXTRA_SOURCES` in `app/i18n/extract.py` mit ein.

## Ein Platzhalterwert kann selbst übersetzbar sein

Ein `TranslatableText` ist Vorlage **plus Werte**, und ein Wert darin ist nicht
zwingend eine Zahl: `perceive.actions._no_way` baut
`_("Dafür ist „{title}“ da.", title=<Titel einer Operation>)`, und der Titel
kommt als `TranslatableText` aus dem Register.

**Werte gehen deshalb durch `translatable_values_to_data` und
`translatable_values_from_data`** (`scene/serialise.py`), nie durch ein rohes
`dict(text.values)`. Das gilt für alle vier Ablagestellen — Parametertitel,
Transaktionstitel, Befundmeldung, Beschriftung eines Auswegs — und für
`cache._name_to_data`, das dieselben Helfer benutzt.

Was ein rohes `dict(...)` kostete, ist am 04.09.2026 gemessen worden: Der
eingebettete Text stand unverändert im Bericht, `json.dumps` in `project.save`
endete mit `Object of type TranslatableText is not JSON serializable`, und
weil das kein `AppError` ist, verlor der Kunde das Speichern ohne
Handlungsvorschlag (Regel 17). Im Plattencache wäre dieselbe Sache still
gewesen — der Eintrag fiele durch den `except`-Zweig, und jedes Projekt
rechnete neu.

**Abgelegt wird die Struktur, nicht der Satz.** Der eingebettete Text behält
Message-ID, Kontext und eigene Werte und übersetzt sich nach dem Laden wieder
selbst. Die beiden kürzeren Wege geben je etwas auf: `str(value)` friert die
Sprache des Speicherzeitpunkts ein, `source_text(value)` legt einem
französischen Kunden einen deutschen Operationstitel mitten in den Satz.
Zahlen bleiben dabei unangetastet — `{free:.1f}` steht so in den Katalogen,
und ein Wert, der als Zeichenkette zurückkäme, machte aus der Formatangabe
einen Fehler.

Dieselbe Regel greift eine Ebene höher beim Auflösen: `TranslatableText.translate(sprache)`
und `source_text()` reichen die verlangte Sprache an ihre Werte weiter, statt
sie über `__str__` gegen die global eingestellte laufen zu lassen.

## Eingangsstufe

Jede geladene Datei durchläuft dieselbe Kette, und das Ergebnis steht in
`sources`: Einheit bestimmen (bei Verdacht **nachfragen**, nicht annehmen),
Vertices verschweißen, entartete Dreiecke entfernen, Normalen vereinheitlichen,
Komponenten zählen (Kleinstteile **melden** statt still löschen), Lage
ermitteln und Aufsetzen anbieten — nicht erzwingen.

**Was zum Lesen eines Formats gehört, ist kein Befund.** Eine STL speichert
jedes Dreieck mit eigenen Ecken; sie zu verschweißen ist Lesen, keine
Reparatur — und „Doppelte Punkte wurden verschweißt." stand als erste Zeile
jedes sauberen STL-Imports im Prüfbericht, ohne Handlung (Bedienweg-Durchsicht
14.09.2026). `normalise(weld_is_reading=True)` verschweißt weiter und schweigt
darüber; `import_model` setzt es an der Endung. Bei OBJ, PLY und 3MF bleibt
der Befund: Dort sind doppelte Punkte eine Eigenschaft der Datei. Und „Das
Modell besteht aus mehreren Teilen." trägt seither die Handlung, die es
nahelegt (`SPLIT_BODIES`, `panels.FINDING_ACTIONS`) — ein Angebot, keine
Ausführung.

**Eine Kopie derselben Schale ist ein Duplikat, keine Baugruppe.** Trägt eine
OBJ, PLY oder 3MF ihre Schale zweimal mit eigenen Ecken, kam sie vorher als
zwei deckungsgleiche Teile mit doppeltem Volumen an (gegenläufig geschrieben
mit dem Volumen null). Seit der Durchsicht 0.5.0 räumt das Einlesen sie ab wie
jedes andere doppelte Dreieck — unter `remove_degenerate`, mit Befund, und nur,
wenn das Netz danach geschlossen ist; berühren sich zwei Körper an einer
Fläche, bleiben sie zwei.

**Verschweißen schließt Ränder, es verbindet keine Blätter** (RM-239). Import
und Reparatur fragen dieselbe Funktion (`geom.repair.weld`): Eine Suppe wird
auf `EPS_GEOM` gelesen, danach kommt nur zusammen, was an einem offenen oder
verzweigten Rand liegt oder als Kante unter `EPS_GEOM` zusammenfällt, jede
Punktgruppe wird nach dem Flächenblatt getrennt, zu dem ihre Kopien gehören,
und übernommen wird nur, was das Netz nicht schlechter macht. Was darüber
liegt und heil ist, ist Form: eine Fase von 0,016 µm zwischen zwei Flächen
bleibt, auch wenn sie schmaler ist als die Schweißtoleranz. Wer ein
eingelesenes oder beschädigtes Netz an einer weiteren Stelle verschweißt,
nimmt dieselbe Funktion — zwei Regeln für dieselbe Frage entschieden über
dasselbe Netz verschieden (der Import nahm zurück, was einen dichten Eingang
aufriss, die Reparatur, was die Summe offener und verzweigter Kanten
erhöhte). `Trimesh.merge_vertices` bleibt, wo ein Erzeuger seine eigenen
Stücke zusammenfügt (Drehkörper, Werkzeuge), und in `boolean._tidied`, das
die Ausgabe des Kerns über alles verschweißt, wie ein Slicer es täte, und das
Ergebnis selbst prüft.

**Und sie schließt, was offen ist** (Entscheidung Robert, 22.09.2026: „am
besten beim Import", „alles bei der Reparatur beheben"). Bis dahin meldete der
Import „Das Modell ist nicht geschlossen. Reparieren schließt die offenen
Stellen." — ein Hinweis auf einen Knopf, den der Kunde erst finden musste, und
ein Modell, das bis dahin nicht druckbar war. Jetzt läuft `geom.repair.repair`
an derselben Stelle, mit denselben Schritten, die die Operation fährt, und
**nur**, wenn es etwas zu tun gibt: Ein geschlossener Körper geht ohne eine
Messung durch, ein unverschweißtes Netz wird gar nicht erst gefragt (dort ist
jede Kante ein Rand, und `weld=False` heißt: nicht anfassen). Gemessen am
Korpus `F:\3D Dateien` (171 Dateien, 484 Körper): 366 kamen dicht herein,
**118 offene gehen geschlossen heraus, keiner bleibt offen**, 108 s für alle
zusammen.

Drei Sätze dazu:

* **Was geschlossen wurde, steht im Bericht** — mit Zahl (`repair.holes_filled`,
  `repair.branching_resolved`), und eine Öffnung über `FILL_LOOP_SHARE` der
  Oberfläche zusätzlich als **Warnung** (`repair.wide_hole_filled`): Dort ist
  eine Fläche entstanden, die im Modell nicht war. Am Korpus traf das keinen
  einzigen Körper; an `broken_open.stl` trifft es zu, und dafür steht der Test.
* **Die Antwort auf „ist es dicht" gilt danach neu.** Sie liegt im Cache des
  Netzes, den der Hauptthread abliest; ein `None` an dieser Stelle wurde dort
  zu `False`, und ein geschlossener Körper meldete sich als offen.
* **Die Reparatur bleibt eine Operation.** Wer sie am Stapel sieht, sieht auch
  hier dieselben Befunde — und wer das Ergebnis nicht will, nimmt den
  Ladeschritt mit Strg+Z zurück.

Und diese Grenzen, entschieden von Robert am 24.09.2026 und nach seiner
Vorgabe vom 25.09.2026 („das Beste für den Kunden, den Druck und das Modell“):

* **Eine große Öffnung wird geschlossen, aber mit Ort und Rückweg.**
  `repair.wide_hole_filled` trägt die Stelle der größten Öffnung, *Stelle
  zeigen* und *Offen lassen*. **Offen lassen gilt der großen Öffnung, nicht
  jedem Loch** (RM-241, Entscheidung nach Roberts Vorgabe vom 25.09.2026:
  das Beste für Kunde, Druck und Modell): Es setzt am Ladeschritt
  `wide_holes=False` (*Große Öffnungen schließen*), die kleinen Löcher,
  Nähte und überzähligen Flächen gehen weiter zu, und der Bericht sagt
  `repair.wide_hole_kept` mit *Dicke geben* — eine offene Fläche druckt erst
  mit einer Wand. Vorher schaltete der Knopf `mend` ganz ab. Der Schalter
  gilt jedem Körper der Datei; eine Baugruppe mit mehreren großen Öffnungen
  ist selten, und ein Schalter je Körper wäre im Dialog eine Liste. Ein Ort
  wandert beim Aufsetzen mit dem Körper.
* **Lose offene Splitter gehen beim Schließen, mit Satz** (RM-241, dieselbe
  Entscheidung): Ein offenes Stück unter `SMALL_COMPONENT_SHARE` des größten
  Teils umschließt nichts, druckt nicht und ließ jede Boolesche Operation
  daran scheitern. `repair.splinters_removed` nennt es; *Offene Stellen
  schließen* aus lässt es stehen. Geschlossene Kleinstteile werden weiter nur
  gemeldet (`ingest.small_components`) — §17.1 Schritt 5 trägt den Zusatz.
* **Stecken Teile ineinander, sagt es der Satz** (Bedienweg A5):
  `ingest.multiple_components` fragt am geschlossenen Netz, ob zwei Teile
  einander quer durchdringen (`repair.parts_that_cross`: nur Paare zweier
  Teile im Überlapp ihrer Hüllquader, frühes Ende, eigenes Budget) — dann
  „… die ineinanderstecken" mit *Überschneidungen auflösen* vor *In
  Einzelteile zerlegen*. Berührung an einer Fläche und Spiel wie bei einem
  Kettenglied zählen nicht. Am Korpus `F:\3D Dateien`: 16 von 56
  mehrteiligen Körpern, 3,9 s für alle 485 Körper.
* **Was stehen bleibt, ist keine Zeile** (Bedienweg A4): Ein Verschweißen oder
  Entfernen leerer Dreiecke, das ausblieb, weil es das Netz aufgerissen hätte,
  geht ins Protokoll, nicht in den Bericht — geschehen ist nichts, und der
  Kunde kann nichts tun (am Korpus vor RM-239 41 und 23 von 485 Körpern).
* **Eine Fläche ohne Dicke bleibt offen.** Ihren Rand zu schließen legte eine
  zweite Fläche deckungsgleich auf die erste; der Bericht sagt
  `repair.no_thickness` mit *Dicke geben*.
* **Was sich nicht entscheiden lässt, wird gemeldet, nicht gerichtet.** Eine
  Schale, die ganz in einer anderen liegt und nach außen zeigt, ist ein
  verkehrter Hohlraum oder ein doppeltes Teil (`repair.part_inside`, mit Ort);
  Import und Reparatur sagen es mit demselben Befund.

Die Eingangsstufe ist die Op `load`, damit ihre Parameter im Stack sichtbar
und änderbar bleiben.

**GLB-/GLTF-Koordinaten werden am Ladeschritt versioniert.** Neue Importe
speichern `coordinates="gltf"` und lesen Meter/Y-oben. Bestehende Projekte,
deren gespeicherte Undo-Fassungen und die darin eingebetteten
Generatorquellen behalten `legacy_raw`; die gemeinsame Migration gilt auch
für Rezeptdokumente. **Eine neu erzeugte GLB (Weg 3) speichert ebenfalls
`gltf`** mit der Einheit `mm`: TripoSG schreibt Y-oben wie jede glTF-Datei,
roh gelesen lag jeder erzeugte Körper auf dem Rücken (RM-086, gemessen an
fünf erzeugten Netzen). Die Achsen folgen dem Format, die Meter nicht — die
Größe setzt der eigene Schritt `fit_to_size`. Eine explizite Einheit hat
Vorrang. Der Rohleser und die separate Zielgrößenskalierung ändern ihren
Vertrag dadurch nicht.
**Die Meter-Lesart wird nicht geglaubt, wenn sie unplausibel ist.** glTF
schreibt Meter vor, aber die Datei sagt es nicht selbst; ein Generator
liefert den Einheitswürfel. Fällt das Modell in Metern unter zehn Millimeter
oder über die doppelte Bauraumdiagonale, stellt der Ladeschritt die
Einheitenfrage mit Meter als erster Antwort (Regel 21). Eine 3MF-Einheit ist
dagegen eine Aussage der Datei und wird ohne Frage angewandt.

**ZIP-Dubletten dürfen nur bei bytegleichem Inhalt passieren.** Alle Einträge
zählen vor dem Inhaltsvergleich zu Archivanzahl, Entpackgröße und
Kompressionsverhältnis. Eine identische CRC ist kein Gleichheitsbeweis. Der
Vergleich liest begrenzte Blöcke; fehlerhafte oder widersprüchliche Kopien
bleiben abgewiesen. Weder die eingebettete noch die externe Quelle wird für
diese Prüfung umgeschrieben.

Eine Datei aus dem Netz (`core/ingest/fetch.py`) geht **denselben** Weg:
`Session.import_payload` ist die gemeinsame Stelle, `import_model` liest nur
die Platte und ruft sie auf. Zwei Importwege wären zwei Stellen, an denen die
Einheitenfrage vergessen werden kann. Was aus dem Netz kommt, trägt seine
Herkunft in `Source.origin` (§16.3), wird nur über `http`/`https` geholt, und
die Größengrenze wird **während** des Lesens geprüft — `Content-Length` ist
eine Behauptung des Servers. Eine Adresse, unter der HTML liegt, ist eine
Modellseite und keine Modelldatei; sie wird als solche gemeldet, nicht
ausgewertet.

## Formate

3MF ist eine **Baugruppe**, keine einzelne Datei: mehrere Objekte, Stückzahlen,
Materialgruppen je Dreieck, Transformationen. Wer es als ein Mesh liest,
verliert genau das. STL kennt keine Einheiten und keine Farbe.

**STEP ist seit Version 33 ebenfalls eine Baugruppe** (P7.4): jede
Komponenteninstanz ein exakter Körper mit Weltlage, Namen und Flächenfarben,
gelesen über XCAF (`brep.step.read_assembly`, Vorrang von Name und Farbe
dort). Fünf Sätze dazu:

* **Die Quelle bleibt die STEP-Datei.** Im Dokument stehen der Ladeschritt
  und die Kennungen der übernommenen Körper (`load_step.bodies`, eine
  JSON-Liste von Instanzpfaden) — keine Formen, keine Farben, kein Pfad.
  Beim Öffnen liest derselbe Schritt dieselbe eingebettete Datei (Regel 12,
  13). Eine Kennung, die die Datei nicht mehr trägt, hält an und sagt, wo man
  neu wählt.
* **Leer heißt: der Stand vor P7.4.** Ein Schritt ohne `bodies` liest die
  Datei wie bisher als einen Körper (`step.read`), damit ein altes Projekt
  dasselbe Teil ergibt; die Migration 32 → 33 schreibt nichts um
  (`step_assembly_v32.p3d`). `*` ist der gemeldete Rückfall, wenn XCAF die
  Datei nicht auflöst — ein Körper, und der Prüfbericht sagt, dass Namen und
  Farben fehlen.
* **Farben werden Filamentslots nur, wenn die Datei zwei oder mehr kennt**
  — dieselbe Regel wie bei der 3MF. Die eine Farbe, in der ein CAD-Programm
  alles zeigt, hat niemand als Filament gewählt. Flächen ohne Farbe bleiben
  am neutralen Slot null; mehr als acht Farben je Körper sind ein Befund.
* **Die Auswahl ändert sich nur, solange niemand auf ihr baut.** Die Liste
  nennt die Zahl der Ausgänge (`produces_from`); `History.change_params`
  weist eine andere Zahl **und** einen Austausch gleicher Zahl ab, sobald ein
  späterer Schritt die Körper benutzt (`members_in_use`) — sonst träfe er
  still einen anderen Körper.
* **Hinaus schreibt `step.write_bodies`**: Name wörtlich, Filamentfarben je
  Fläche, Umlaute nach ISO 10303-21 kodiert. Eine Rundreise ergibt dieselben
  Körper, Namen und Farben.

Dreieckszahl und Dateigröße sind beim Import gedeckelt — mit klarer Meldung
statt Speicherüberlauf.

**Ein 3MF-Modell wird nie am Stück geparst.** `ET.fromstring` über 195 MB
Modell-XML hielt den GIL 4 bis 5 s, und der Speicherbereiniger lief danach über
3,5 Millionen `Element`-Objekte — das Fenster stand, obwohl der Import im
Arbeiter lief (Durchsicht 0.5.1, FENSTER-03). Wer den Baum braucht, liest ihn
über `threemf._parse_model` innerhalb von `_reading_trees`: stückweise, nach
jedem Stück eingefroren (`gc.freeze`), am Ende in Scheiben freigegeben und
aufgetaut. Nichts bleibt eingefroren (`gc.get_freeze_count() == 0`, Test). Wer
nur zählt, baut die Geometrie gar nicht (`_StructureOnly`).

## Was welcher Slicer bekommt

**Eine Stützsperre gehört zu ihrem Objekt, und jede Familie schreibt sie
anders** (`slicer_keys.helpers_as_parts`). Die Orca-Familie bekommt sie als
eigenes Teil: Das Objekt hat zwei Komponenten, Körper und Sperre, und
`model_settings.config` nennt die zweite `support_blocker`. PrusaSlicer
bekommt sie als Bereich: Ihre Dreiecke hängen hinter denen des Körpers, die
Prusa-Beilage nennt sie `SupportBlocker`, und das Modell trägt
`slic3rpe:Version3mf` — ohne diese Angabe übergeht PrusaSlicer seine Beilage.
**Jede Familie liest nur ihre Schreibweise, und die andere druckt sie als
Kunststoff**: als Bereich der ElegooSlicer (+22,8 g an der Waschschüssel), als
Komponente PrusaSlicer (+38,8 g), gemessen am 26.09.2026. Geprüft wird eine
Sperre deshalb an der **Modellbahn** mit und ohne sie — nicht an der Stütze:
Eine als Kunststoff gedruckte Sperre verdrängt die Stütze auch.
Geschrieben wird sie nur in die direkte Übergabe, nicht in eine gespeicherte
3MF.

`write_assembly` schreibt eine 3MF-Baugruppe — außer für `cura`. `CuraEngine`
liest kein 3MF (die 3MF-Seite sitzt in Curas Fenster, nicht in der
Rechenmaschine dahinter), und ein 3MF endete dort in „Der Slicer hat keine
Druckdatei geschrieben", ohne dass irgendwo stand, warum. Cura bekommt ein STL
mit allen Teilen der Platte; Namen und Materialslots liest es ohnehin nicht,
und die Einstellungen kommen bei ihm über die Kommandozeile.

**Mehrere Platten: eine Datei, wo der Slicer Platten kennt**
(`knows_plates`). Die Orca-Familie speichert ihre Projekte mit je einem
`plate`-Block und den Teilen plattenweise **im Raster** — `ceil(sqrt(n))`
Spalten, die Zeilen nach unten, ein Fünftel Bett Luft (`plate_origin`,
`SLICER_PLATE_GAP`; aus `PartPlate.cpp` gelesen und am installierten ElegooSlicer
gemessen: fünf Platten auf 256 mm liegen bei x = 128, 435,2, 742,4 und in
der zweiten Zeile bei y = −179,2). Bis zum 11.09.2026 stand hier „eine Reihe,
ein Achtel", nachgemessen an `BowlingGame.3mf` — die Messung nahm an, zwei
Objekte stünden plattenlokal an derselben Stelle, und bei vier Platten lagen
die Buchstaben der dritten und vierten im Slicer neben allem. Genau diese
Datei schreibt `write_assembly` ohne `plate`; die Blöcke zählen durch (Rang,
nicht Solidons Plattennummer), denn aus ihrer Zahl rechnet der Slicer die
Spalten. *Im Slicer öffnen* gibt ihr deshalb alle
gewählten Platten in einer Datei — ein Fenster, nicht vier: Vier Starts des
ElegooSlicers auf einmal stritten um dieselbe Filamentbibliothek, bis einer
mit „remove_all: Zugriff verweigert" abbrach (Robert, 11.09.2026).
PrusaSlicer und Cura kennen eine Platte je Datei und bekommen weiter je
eine; der Konsolenlauf (*Slicen*) rechnet ohnehin je Platte eine
Druckdatei. Solidons Anordnung reist dabei nur mit, wenn sie auf **jeder**
gewählten Platte hält (`arrangement_holds`).

**Bettkoordinaten für jede Familie** (`wants_bed_coordinates`). Solidon
rechnet um den Ursprung, der Drucker misst von der Ecke — und der Slicer
bekommt die Welt des Druckers: die Teile um den halben Bauraum verschoben
**und** ein Bett von `0` bis `256`, in derselben Übergabe. Bis zum 05.09.2026
bekamen Cura und PrusaSlicer stattdessen Solidons Welt erklärt
(`machine_center_is_zero`, eine Bettform von `-128` bis `128`) und die Teile
unverschoben; der Slicer war mit sich im Reinen und schrieb Bahnen bei
`-13,6`, die es auf einem MK4S oder Centauri nicht gibt, während die eigene
Gegenprobe gegen denselben erfundenen Ursprung maß (Gesamtreview, CORE-17,
mit PrusaSlicer 2.9.6 gemessen). Die ältere Messung „um den halben Bauraum
verschoben" — Würfel bei -10…10, im G-Code bei 118…138 — war die Bettmitte;
PrusaSlicers „All objects are outside of the print volume" kam aus dem
Widerspruch zwischen verschobenen Teilen und zentriert erklärtem Bett. Wer
das eine ändert, ändert das andere mit — beides fragt dasselbe Prädikat.

**Ein Programm ohne Familie bekommt STL um den Ursprung** (`other`, seit
RM-071). Es ist das eine Format, das jeder Slicer liest — auch der
rudimentäre Hersteller-Slicer eines Resin-Druckers —, und einen Bauraum,
zu dessen Ecke sich verschieben ließe, kennt Solidon dort nicht. Übersetzt
wird nichts, gerechnet wird nichts: Der Konsolenweg sagt für diese Familie
ab, das Öffnen läuft.

**Und ein exakter Körper geht so fein hinaus, wie der Drucker es braucht.**
`writer.mesh_for_export` fragt `Profile.export_deflection` — ein Achtel des
kleinsten Details, gedeckelt von der Zahl des Kerns — und vernetzt neu, wenn
das Profil feiner verlangt als der Körper hat. Anzeige und Erkennung bleiben
bei der Vernetzung des Körpers; die Datei geht in den Slicer, und an
50-µm-Pixeln ist eine Facette von fünf Hundertsteln eine Stufe. Der Befund
`export.tessellated` sagt es einmal je Export, nie je Körper.

## Auf dem Herstellerprofil wird nur die Abweichung geschrieben

**Entscheidung Robert, 27.09.2026** (Bauplan §29). Solidon schrieb bis dahin
jeden Tabellenwert über das Profil des Herstellers — am Centauri Carbon 2 45
Prozess- und 22 Filamentwerte, darunter Gitter statt Elegoos Baum, kein
Auto-Brim, eine erste Schicht von 0,25/0,449 mm und die Faustregel von 45
Grad. Roberts Minigolf-Druck bekam davon einen Stützfuß in Schicht 1
(46,4 m Stütze; mit Elegoos Satz 0 m). Seitdem gilt:

- **Nur `chosen`, `accepted`, das Gemessene und die Werte der Stufe gehen
  über das Herstellerprofil.** Wer einen neuen Weg in die Übergabe baut,
  fragt `manufacturer.written_paths` — ein Wert ohne Herkunft ist Grundlage
  und steht schon im Profil. Die Stufe legt ihre Werte
  (`manufacturer.STAGE_PATHS`) nur über den Standardprozess der Maschine;
  ein selbst gewählter Prozess ist die Stufe.
- **Was ohne Partner nicht wirkt, geht mit ihm** (`handover.COUPLED_PATHS`):
  eine Haftungsart mit den Maßen aller Arten, eine Lüfter-Obergrenze mit dem
  unteren Ende. Eine gewählte Haftungsart bringt ihr Maß mit, wenn es auf
  null steht (`print_settings._with_a_measure`). Wer einen neuen gekoppelten
  Wert findet, trägt ihn dort ein.
- **`with_path` setzt keine Herkunft.** Eine Eingabe im Dialog ist
  `with_choice`, ein übernommener Vorschlag `with_accepted`
  (`advise.apply`), das Zurücksetzen `without_choice`. Eine Rücklesung aus
  einem Profil ist keine Wahl.
- **Die Druckplatte ist eine Angabe, keine Vermutung.** Ohne `curr_bed_type`
  nimmt die Konsole „Cool Plate" — gemessen mit 35 °C Bett für PLA. Es gilt
  die im Druckdialog gewählte Platte (`SlicerSetup.plate`), sonst die
  Standardplatte der Maschine oder ihres Modells; Elegoos
  `default_bed_type = 4` ist die texturierte PEI-Platte (belegt an 34
  gespeicherten Projekten). Nur ein Drucker ohne Plattenwahl
  (`support_multi_bed_types` fehlt) hat die eine Betttemperatur
  `hot_plate_temp` (`manufacturer.SINGLE_PLATE`); einer mit Wahl und ohne
  Standardplatte bekommt keine geratene, sondern den Befund
  `slicer.plate_unknown`. Die Betttemperatur der Grundlage kommt nur aus dem
  Schlüssel der aufliegenden Platte. Eine 0 °C des Herstellers sperrt die
  Platte für das Filament: Die Grundlage liest dort nichts, und
  `slicer.plate_refuses_filament` führt in die Druckeinstellungen. Eine
  eigene Betttemperatur schreibt die Übergabe trotzdem in den Schlüssel
  dieser Platte — sie ist die Wahl des Kunden.
- **Was sich nicht übersetzen lässt, wird nicht umgedeutet**
  (`Foundation.foreign`): `crosshatch` bleibt `crosshatch`, geschrieben wird
  es nicht, und der Druckdialog zeigt am Feld „Hersteller: crosshatch".
- **Die Gegenprobe hält, was Solidon schreibt, und eine Stichprobe der
  Grundlage** (`handover.FOUNDATION_SAMPLE`). Listen je Düsenvariante gelten
  mit dem ersten Eintrag (`handover._printed`), den der Slicer ohne
  Variantenwahl druckt.
- **Die Abnahme ist der Konfigurationsblock**: Ohne Vorschläge ist Solidons
  G-Code-Konfiguration gleich der des Herstellerprofils allein, bis auf
  Namen, Objektmarken und `filament_self_index`. Der Stand der Messungen
  steht in `ROADMAP.md` (RM-281).
- **Ältere Dateien ordnet die Migration gegen jede Auflösung ein, mit der
  eine Version schrieb** (`print_settings.legacy_choices`): die heutige und
  die von 0.5.0 (`resolve(..., legacy=True)`). Wer die Auflösung ändert,
  prüft die Einordnung an einer Datei, die die alte Version selbst
  gespeichert hat (`tests/data/projects/print_settings_v33.p3d`).

## Die drei Stufen der Übergabe

Was ein Slicer bekommt, entsteht in dieser Reihenfolge, und `values_for` ist
die einzige Stelle, an der sie zusammenkommen:

1. **Zuordnung** (`as_mapping`) — die Tabellen aus `slicer_keys`, dazu was
   sich allein aus den Einstellungen umrechnen lässt.
2. **Maschine** (`_machine_keys`) — Bauraum, Düse, und was `CuraEngine`
   sonst nirgends findet.
3. **Abgeleitetes** (`_cura_dependants`) — nur für Cura, und nur danach: die
   Ableitung rechnet auf Werte aus beiden Stufen.

Wer eine Stufe einzeln benutzt, bekommt einen halben Satz. Für Prusa und Orca
ist die dritte leer.

## CuraEngine löst keine Vererbung auf

In `fdmprinter.def.json` trägt jede abgeleitete Einstellung zweierlei: einen
`value`-Ausdruck und einen `default_value`. Das Fenster wertet den Ausdruck
aus, die Rechenmaschine dahinter nimmt den Vorgabewert. Ein geschriebener Wert
bleibt damit an seinem Schlüssel stehen und erreicht die nicht, aus denen
gerechnet wird — die Bahnbreite ihre zwölf Bahnbreiten nicht, die Füllung
ihren Linienabstand nicht.

Gemessen an einem 20-mm-Würfel: **1100 mm Filament statt 818, 753 Sekunden
statt 660.**

Wer eine Cura-Zuordnung ergänzt, prüft deshalb immer mit: hängt etwas an dem
neuen Schlüssel? Reine Kopien kommen in `CURA_MIRRORED`, einfache Faktoren in
`CURA_SCALED`, Gerechnetes in `_cura_computed` — dort **die Formel aus der
Definition**, nicht die eigene Meinung darüber, was richtig wäre. Was
absichtlich wegbleibt, kommt mit Begründung in `CURA_UNTOUCHED`;
`tests/test_print_settings.py` lässt keine dritte Möglichkeit zu.

## Winkel zählen nicht überall gleich

`support.threshold_angle` misst **gegen die Senkrechte**: 0° stützt jeden
Überhang, 90° keinen. Das ist Curas Zählweise. PrusaSlicer und die
Orca-Familie messen gegen die **Horizontale** und drehen die Bedeutung damit
um — für sie rechnet `_angle_from_horizontal` in `90 − Wert`. Gemessen an
einem Keil mit 30° Neigung: die beiden kippen zwischen 20 und 40, Cura
zwischen 50 und 70.

## Eine gelungene Übergabe ist noch kein vollständiger Druck

Ein Slicer, der mit Exit 0 zurückkommt und eine Datei hinterlässt, hat damit
nicht gesagt, dass der Auftrag darin steht. **Gemessen am 12.09.2026 mit Bambu
Studio 2.3**: derselbe Würfel einfarbig 4,31 g, zweifarbig 2,82 g — ein
Filament statt zwei, ein Drittel weniger Material, kein Werkzeugwechsel, kein
Wort in Ausgabe oder Protokoll. OrcaSlicer und ElegooSlicer rechnen dieselbe
Platte aus denselben Dateien mit beiden Spulen und 102 Werkzeugwechseln; die
Übergabe war also in Ordnung.

Deshalb wird **nach** dem Lauf geprüft, was hineingehörte (`spools_left_out`,
siehe die Karte des Gebiets). Wer eine neue Zusage an den Slicer gibt, fragt
sich, woran man ihr Einlösen in der fertigen Datei erkennt — eine Zusage, die
nur die Übergabe kennt, wird bei einem fremden Programm irgendwann still
gebrochen.

**Und eine Prüfung dieser Art zählt die Flächen, nicht die Deklaration.** Ein
Körper darf einen Materialslot tragen, den keines seiner Dreiecke benutzt. Wer
dagegen prüft, meldet bei jedem solchen Druck einen Verlust, der keiner ist —
und ein Fehlalarm, den der Kunde dreimal gesehen hat, nimmt dem echten Befund
die Wirkung.

## Ein Absturz ist keine Absage

Beide enden ohne Druckdatei, und bis zum 12.09.2026 bekamen beide denselben
Satz: „Der Slicer hat keine Druckdatei geschrieben", dazu den Rat, das
Slicer-Profil zu prüfen. Bei einem Absturz ist dort nichts zu finden.
`crashed()` unterscheidet sie am Rückgabewert — POSIX zählt Signale negativ,
Windows meldet einen `NTSTATUS` ab `0xC0000000` —, und die Prüfung steht
**vor** den Ausgabeprüfungen: Ein abgestürztes Programm schreibt keinen Satz,
an dem sie greifen könnten.

Gemessen an Creality Print 7.2, das auf dieser Maschine nie eingerichtet war:
dreimal `0xC0000005` mitten im eigenen Start, lange bevor es das Modell ansieht.

## Ein Wert gehört an einen Schlüssel, der dasselbe meint

Eine Zeile in `slicer_keys` darf einen Solidon-Wert nur unter einen Namen
schreiben, der **dieselbe Sache** meint. Zwei Enden einer Kurve sind zwei
Einstellungen, auch wenn ein Wert an beiden „passt". Bis zum 23.09.2026 stand
`cooling.fan_speed` unter `fan_max_speed` **und** `fan_min_speed` (Prusa und
Cura ebenso): Der Lüfter lief bei PLA in jeder Schicht voll, gemessen am
ElegooSlicer mit `M106 S255` in 134 von 136 Schichten, obwohl Elegoos Profil
50 bis 100 % vorsieht (Befund Robert). Und weil die Rücklesetabelle nur das
obere Ende kannte, überschrieb Solidon selbst ein Herstellerprofil, das es
richtig gelesen hatte.

Wer eine Zeile ergänzt, fragt deshalb: Hat der Slicer daneben einen
Gegenwert — Minimum zum Maximum, Schwelle zur Kurve, Schalter zum Anteil?
Dann braucht Solidon ein eigenes Feld dafür, eine Zeile in jeder Familie, eine
Zeile in den Rücklesetabellen und einen Wert im Materialprofil. Ein Anteil,
der nur mit einem Schalter wirkt, schreibt den Schalter mit
(`_positive_switch`): Ohne `reduce_fan_stop_start_freq` schaltete der
ElegooSlicer den Lüfter bei jeder PLA-Schicht über 60 s ganz ab.

Ein solches Feld, das eine ältere Datei nicht kennt, ist keine Vorgabe der
Dataclass, sondern eine Frage an dieselbe Stelle, die ein neues Projekt
fragt: Unteres Ende und Schwelle der Lüfterkurve kommen beim Öffnen aus dem
Material (`print_settings.fan_curve`), und der alte eine Wert bleibt, was er
im Dialog hieß — das obere Ende (Entscheidung der Durchsicht, 23.09.2026:
Der Mindestwert war nie eine Wahl des Kunden, sondern der Fehler). Einen
Formatsprung braucht das nicht, solange ein älteres Programm die neuen
Schlüssel still übergeht (`_group_from_data` filtert nach bekannten Feldern)
und die Datei dort so druckt, wie es vorher jede druckte.

## Wie eine Zuordnung geprüft wird

Ein falscher Schlüsselname fällt nicht von selbst auf — kein Slicer meldet
ihn. Zwei Wege führen hin, und sie decken verschiedene Slicer ab:

- **Prusa und Orca schreiben ihre Konfiguration in den G-Code.** `verify()`
  vergleicht sie gegen das Geschriebene: 53 von 53 beim einen, 56 von 56 beim
  anderen.
- **CuraEngine schreibt dort nichts** — null von 47. Für es liegt die Auskunft
  daneben: `fdmprinter.def.json` nennt jeden gültigen Schlüssel der
  installierten Version. `unknown_keys()` liest sie zur Laufzeit, der Test
  `test_every_cura_key_exists_in_the_definition` beim Bauen.

In dieser Lücke saß `outer_inset_first`: ein Name aus Cura 4, in Cura 5
verworfen, ohne Fehler und ohne Warnung — null von fünfzig Lagen begannen
außen, obwohl der Wert geschrieben war.

## Einstellungen reisen mit der exportierten Datei

Eine 3MF soll man drucken können, nicht erst einrichten. Beide Familien lesen
dafür eine Beilage, in verschiedenen Formaten:

| Slicer | Beilage | Format |
|---|---|---|
| Orca-Familie | `Metadata/project_settings.config` | JSON |
| PrusaSlicer | `Metadata/Slic3r_PE.config` | `; schlüssel = wert` je Zeile |

PrusaSlicer **überspringt die erste Zeile** dieser Datei — bei ihm steht dort
seine eigene Kennung. Ohne `PRUSA_CONFIG_HEADER` fiel der alphabetisch erste
Schlüssel lautlos heraus. Cura bekommt seine Einstellungen ohnehin über die
Kommandozeile; seine 3MF-Seite sitzt im Fenster.
