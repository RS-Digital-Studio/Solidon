---
paths:
  - "app/core/slice/**/*.py"
  - "app/core/perceive/**/*.py"
---

# Regeln für Schichtanalyse und Wahrnehmung

## Die Abgrenzung, die nicht verhandelbar ist

Solidon baut **keinen G-Code-Slicer**. Die Datei, die auf den Drucker geht,
kommt vom externen Slicer. Was hier entsteht, ist Analyse: Ebene-Mesh-Schnitt,
Konturen, Kennzahlen — in Millisekunden, ohne Fremdprozess.

**Kennzahlen aus Schichtanalyse und G-Code werden nie vermischt** (Regel 14).
Jeder Wert weist seine Herkunft aus. Ein geschätztes Stützvolumen aus der
Schichtanalyse ist etwas anderes als ein gemessenes aus dem G-Code, und der
Prüfbericht sagt welches.

Beschriftung in der Oberfläche: „Schichtanalyse", nicht „Vorschau". Sie zeigt
die Geometrie, nicht die Werkzeugwege.

## Zwei Wege durch den Schnitt, und beide müssen dasselbe rechnen

`app/core/slice/_chain.pyx` verkettet die Konturen einer Schicht übersetzt
(`tools/build_slice_core.py`). Es ist **optional**: fehlt es, geht derselbe
Schnitt über `shapely.polygonize`. Drei Sachen gelten dabei:

- **Der GEOS-Weg bleibt der Bezug.** Er wird nicht entfernt, nicht
  vernachlässigt und nicht als Notlösung behandelt. Er ist der Weg, den jeder
  Klon ohne Compiler nimmt.
- **Jede Änderung an einem der beiden gilt beiden.** `tests/test_slice_core.py`
  hält sie aneinander — Fläche, Löcher, Geometrieart, Überhang. Wer nur einen
  ändert, bekommt dort einen roten Lauf.
- **Der übersetzte Weg ist der schnellere, nicht der genauere.** Er *könnte*
  genauer sein — er kennt die Kante, auf der ein Punkt liegt, und bräuchte
  das Runden auf sechs Nachkommastellen nicht. Er rundet trotzdem, und zwar
  genau wie GEOS. Der erste Anlauf tat es nicht, und eine Abweichung in der
  neunten Stelle kam hinter `buffer` → Extrusion → Boolesche Differenz als
  andere Topologie heraus: 17 erkannte Merkmale statt 14, darunter ein Stift,
  den es nicht gibt. **Zwei Wege durch dieselbe Rechnung dürfen sich nicht in
  der letzten Stelle unterscheiden**, auch nicht zum Besseren hin.

Der Grund für das Ganze steht als Messung in `ROADMAP.md` („Der kompilierte
Kern, nachgerechnet"): Derselbe Durchlauf kostet 608 ms in Python und 11 ms
übersetzt. **Eine Python-Idee mehr bringt dort nichts** — drei sind gemessen
und alle drei landen in derselben Größenordnung.

## Die Einstellungen bleiben trotzdem hier

Kein eigener Slicer heißt **nicht** kein eigenes Profil. `PrintSettings`
(§29) hält alles, was gedruckt wird — Schichten, Wände, Füllung,
Temperaturen, Kühlung, Geschwindigkeiten, Stützen, Haftung, Rückzug,
Filamentfarbe. `export/handover.py` schreibt daraus die Konfiguration des
externen Slicers, ruft ihn und liest den G-Code zurück. Der Slicer führt aus,
er entscheidet nicht mehr.

Drei Sachen, die dabei nicht verhandelbar sind:

- **Aufgelöst wird aus drei Ebenen** — Qualitätsstufe, Material, Drucker, in
  dieser Reihenfolge. Die Düse skaliert die Schichthöhe, die Maschinengrenzen
  deckeln die Temperatur, ein offener Bauraum bekommt keine Kammertemperatur.
- **Das Maschinenprofil wird nicht erfunden.** Bettform, Anfahrwege, Start-
  und Endcode kennt Solidon nicht; sie kommen aus dem Bestand des Slicers.
  Bei der Orca-Familie gilt das auch für das Prozessprofil: Solidon liest das
  benannte Systemprofil und legt seine Werte darüber, sonst bricht der Lauf
  mit „process not compatible with printer" ab, bevor er das Modell ansieht.
- **Ein neuer Slicer kostet eine Tabelle**, keinen Eingriff — `slicer_keys.py`
  ist das Wörterbuch, `handover.py` der Ablauf.

**Bei `CuraEngine` gehen die Werte zweimal hinaus.** Es hält zwei Ebenen —
global und Extruder-Zug —, und das meiste, was einen Druck ausmacht, liest es
vom Zug. Was nur global steht, wird nicht übernommen, sondern von der Vorgabe
der Definition überschrieben; was nur auf dem Zug steht, fehlt der
Zeitrechnung. Beide Male dasselbe zu setzen kommt am selben Ort heraus und
spart es, `settable_per_extruder` aus der Definition zu lesen.

**Was der Kopf einer Cura-Datei sagt, ist keine Messung.** `Filament used`,
`MINX` und `TIME` schreibt CuraEngine, *bevor* es rechnet; im Fenster werden
sie ersetzt, von der Kommandozeile aus bleiben sie stehen — `;TIME:6666` sieht
mit 111 Minuten plausibel aus und gilt für jedes Modell. Gelesen wird deshalb
die Datei selbst: die E-Achse für das Material, die letzte `TIME_ELAPSED` für
die Zeit. Ein Kopfwert gilt weiter, wo er einen trägt — er kennt Vorgänge, die
keine Bahn zeigt.

**Und der Bauraum wird an den Bahnen nachgemessen.** `gcode.printed_extent`
liest, wohin die Datei wirklich druckt, `handover.off_the_bed` beurteilt es.
Der Anlass ist derselbe Slicer: CuraEngine prüft seinen Bauraum **nicht** — ein
Würfel 150 mm neben der Mitte auf einem Bett von 220 mm kam als Druckdatei
zurück, die bei x 130,2 bis 169,8 druckt, mit `MINX` auf dem unbesetzten
Anfangswert. PrusaSlicer rückt in solchen Fällen selbst in die Mitte, die
Orca-Familie schreibt nichts. Drei Dinge gelten dabei:

- **Die Bogenformen zählen mit.** Eine Kreiswand mit Bogenanpassung besteht
  **nur** aus `G2`/`G3`; wer nur `G1` liest, verliert genau die Ausmaße eines
  Zylinders.
- **Die Stelle wird über alle Bewegungen nachgeführt**, auch die leeren: Z steht
  so gut wie nie in derselben Zeile wie die Bahn, und ein `G1 Y30 E0.5` behält
  sein X von vorher.
- **Die Druckdatei wird in Maschinenkoordinaten geprüft** (`handover.off_the_bed`).
  Bei allen unterstützten Familien liegt der Ursprung an der Bettecke.
  Die Verschiebung der Eingabegeometrie ist davon getrennt: CuraEngine führt
  sie selbst aus, Prusa- und Orca-Projekte enthalten sie bereits. Nennt die
  Druckdatei ihre Bettkontur, hat diese Vorrang vor dem Druckerprofil.

Gemeldet, nicht gesperrt (§29), und unter einer Bahnbreite gar nicht: die Bahn
liegt mit ihrer halben Breite ohnehin neben der Mitte, die gemessen wird.

## Vorschlag oder Befund

`slice/advise.py` schließt aus Geometrie, Material und Maschine auf
Einstellungen. Die Unterscheidung ist verbindlich:

- Was ein Wert behebt, wird ein **Vorschlag** (`SettingAdvice`) — mit Pfad,
  altem Wert, neuem Wert und **Begründung**. Ohne Grund kein Vorschlag: eine
  Zahl, die niemand nachprüfen kann, ist schlechter als die Vorgabe.
- Was kein Wert behebt, wird ein **Befund** (`Finding`). ASA auf einem offenen
  Drucker bleibt heikel, auch wenn Lüfter und Brim schon stimmen; das als
  Vorschlag zu verkleiden hieße, eine richtige Einstellung zu ändern.

Übernommen wird auf Klick, nie von allein.

**Ein Vorschlag je Einstellung**, und `was` ist immer der Ausgangswert. Regeln,
die auf denselben Wert zielen, werden zusammengeführt; die spätere gewinnt,
weil sie den Stand der früheren gesehen hat. Der Volumenstrom läuft deshalb
zuletzt: er hängt an Schichthöhe, Bahnbreite und Tempo, an denen die anderen
Regeln gedreht haben können.

**Der Volumenstrom ist die Grenze, die kein Feld zeigt.** Schichthöhe mal
Bahnbreite mal Geschwindigkeit gegen `max_flow` des Materials — darüber
fördert der Antrieb mehr, als das Profil zulässt. Vorgeschlagen wird ein
rechnerisch passendes Tempo für jede betroffene Bahnart; die erste Schicht
verwendet ihre eigenen Maße. Eine Temperatur-Volumenstrom-Kurve ist nicht
hinterlegt. Deshalb gibt es keine pauschale Temperaturanhebung. Auch eine
kleine Standfläche überschreibt keine Filamenttemperaturen; sie begründet
einen Haftungsvorschlag.
Liegt schon das kleinste einstellbare Tempo über dem Volumenstrom, hält die
Beratung mit einem Vorschlag zur Schichthöhe, Bahnbreite oder zum gemessenen
Profilwert an. Eine leere Liste wäre in diesem Fall keine Entwarnung.

**Mehrere Körper werden gemeinsam beurteilt.** `advise.combine` berücksichtigt
auch Körper, deren Einstellungen bereits passen. Ein einzelner Würfel darf
deshalb die Stützen eines anderen Körpers nicht abschalten. Filamentwerte
werden je tatsächlichem Slot aufgelöst und nur innerhalb desselben Slots
zusammengeführt; gemeinsame Prozesswerte müssen für alle gewählten Körper
passen. Bereits abgewählte Vorschläge bleiben bei einer Neuberechnung
abgewählt.

**Die Druckanalyse benutzt das Druckraster.** `slice_body` erhält die normale
und die erste Schichthöhe aus den effektiven Druckeinstellungen. Der Dialog
misst genau den Ausgabeumfang im Hintergrund und verwirft Ergebnisse, deren
Szene, Platte oder Raster nicht mehr aktuell ist. Fehlende, abgebrochene oder
fehlgeschlagene Messung ist keine Entwarnung. Die Orientierungssuche behält
ohne explizite Erstschichthöhe ihr gleichmäßiges Suchraster.

**Was in Geometrie gerechnet ist, wird nicht so gedruckt.** Die Stiftplanung
sucht auf der Schnittfläche Platz für einen Kreis; der Drucker legt dort einen
Ring aus Wänden mit Muster darin, und genau in diesem Muster sitzt die
Verbindung. `solid_core` misst das am Querschnitt — `Durchmesser minus zweimal
Wandzahl mal Bahnbreite`, so wie man es am geschnittenen Teil nachmisst.

Gemeldet wird erst, wenn der Füllkern **breiter** ist als das Material um ihn
herum, und der Vorschlag geht genau bis zu dieser Schwelle, nicht bis
vollmassiv: Bis zum vollen Querschnitt wären es bei einem 8-mm-Zapfen zehn
Wände auf dem ganzen Teil. Ein Vorschlag, den niemand annimmt, macht die
daneben unglaubwürdig.

Vorgeschlagen wird zunächst die **Wandzahl** — Wände liegen deterministisch
um den Zapfen, lockere Füllung trifft ihn vom Muster abhängig. Bei vollständig
gefülltem Kern entfällt dieser Vorschlag. Der Materialanteil beschreibt die
rechnerische Querschnittsfüllung, keine nachgewiesene mechanische Festigkeit.

**Und über einer bestimmten Dicke wird gar nichts vorgeschlagen.** Der Satz
darüber galt bis zum 03.09.2026 nur für den kleinen Fall; der große lief
weiter. Gemessen mit einem Verbinder von Ø 60 mm, wie ihn das Teilen eines
großen Körpers erzeugt: Vorschlag **36 Wände**, das Feld im Dialog reicht bis
20. „Vorschläge übernehmen" schrieb 36 ins Dokument, die an den Slicer
übergebene Datei trug `wall_loops: 36`, und der Dialog zeigte daneben 20 —
Anzeige und Datei sagten Verschiedenes, und 36 Bahnen à 0,42 mm sind 15 mm
Wandstärke.

`MOST_WALLS_WORTH_SUGGESTING` deckelt das, und die Zahl ist die Obergrenze
des Feldes, in das der Vorschlag hineingeht. Der Kern darf die Oberfläche
nicht fragen (Regel 1), also trägt er seine eigene — dass beide dieselbe
führen, hält `tests/test_print_settings_ui.py` fest.

Daraus die allgemeine Form, denn sie gilt jeder künftigen Regel hier:

> **Ein Vorschlag ist ein Knopf, kein Hinweis.** Was er trägt, landet auf
> Klick im Dokument und von dort in der Datei, die zum Slicer geht. Ein Wert,
> den das Feld daneben nicht darstellen kann, ist deshalb kein zu großer
> Vorschlag, sondern ein stiller Unterschied zwischen dem, was der Kunde
> sieht, und dem, was er druckt.

Dieselbe Vorsicht gilt jeder künftigen Regel über ein gedrucktes Maß: Was die
Geometrie als Material führt, ist erst dann Material, wenn eine Bahn darin
liegt.

## Das Maschinenprofil des Slicers

`export/slicer_profiles.py` liest den Bestand des installierten Slicers. Vier
Eigenheiten, die dabei nicht angenommen werden dürfen:

- **Die Ordnertiefe ist nicht einheitlich** — Bambu legt in `machine/`, Elegoo
  in `machine/ECC2/`. Gesucht wird nach dem Ordnernamen irgendwo im Pfad.
- **Verträglichkeit wird vererbt.** Ein Profil je Familie trägt
  `compatible_printers`, die Geschwister erben sie über `inherits`. Wer nur
  das eigene Feld liest, bietet eines von sieben an.
- **Eigene Profile tragen kein `type`** und kein `instantiation` — sie erben
  und stehen unter `from: User`. Genau die gehören in die Liste.
- **Zugeordnet, nicht erfragt.** `printer_model`, Düse und
  `default_print_profile` reichen. Trifft nichts, bleibt die Auswahl leer:
  eine falsche Vorauswahl sieht aus wie eine Entscheidung.
- **Ein Slicerwechsel leert die Auswahl** (`_clear_profile_choices`), und zwar
  am **Anfang** der Suche — `_start_profile_search` kehrt für `prusa` und `cura`
  früh zurück, und was am Ende geleert würde, bliebe dort stehen. Sonst bekommt
  CuraEngine ein `-j` auf eine Orca-Datei und ist nach einer Zehntelsekunde tot.
  Umgekehrt gilt: Wo es nichts zu wählen gibt, wird nichts gemerkt, sonst
  löscht ein Cura-Lauf das Profil des nächsten Orca-Laufs.

## Was geschrieben wird, ist nicht alles, was im Modell steht

Skirt, Brim und Raft sind Maße **ihrer jeweiligen Art**, keine unabhängigen
Schalter — die Slicer lesen sie aber als solche. Wer alle drei schreibt,
bekommt alle drei: einen Raft unter einem Teil, für das „Skirt" eingestellt
war. `_only_chosen_adhesion` nullt deshalb die Maße der nicht gewählten Arten.

Dieselbe Vorsicht gilt für jede künftige Einstellung, die eine Art *und* ihre
Maße hat. Der Fehler ist geräuschlos, kostet Material und Zeit und fällt erst
auf der Platte auf.

## Die Druckdatei gehört dem Nutzer

Der Lauf endet nicht bei den Kennzahlen. Was der Slicer schreibt, liegt im
Arbeitsordner und verschwindet mit ihm — es muss speicherbar sein, sonst war
der ganze Weg eine Zahl auf dem Bildschirm. Vorgeschlagen werden Ordner und
Name des Projekts.

Die Druckeinstellungen selbst gehören ins **Projekt** (`format_version` 4),
nicht in die Anwendungskonfiguration: sie beschreiben das Teil, nicht den
Rechner. Slicer-Pfad und Profilwahl bleiben dagegen bei der Anwendung — ein
Projekt wird auch auf einem Rechner geöffnet, wo ein anderer Slicer liegt.

## Die Einstellungen reisen in der Datei mit

`threemf.write_assembly` schreibt neben der Geometrie auch
`Metadata/project_settings.config` — was die Orca-Familie in einer
Projektdatei führt, gebaut von `handover.project_settings`. Ohne sie ist eine
exportierte 3MF nur Geometrie: der Slicer öffnet sie mit dem Profil, das
gerade eingestellt ist, und alles, was Solidon über Temperatur, Tempo und
Kühlung dieses Teils weiß, ist beim Öffnen weg.

Zwei Eigenheiten, die dabei nicht angenommen werden dürfen:

- **Filamentschlüssel sind Listen**, einer je Extruder; `from` und `name`
  dagegen nicht — sie beschreiben die Datei, nicht einen Platz. Welche
  Schlüssel je Extruder gehen, sagt die Übersetzungstabelle selbst über ihre
  Sektion; eine zweite Liste daneben ist beim nächsten Zuwachs falsch.
- **Die Betttemperatur geht auf jede Druckplatte.** `curr_bed_type` gehört der
  Maschine, die Temperatur dem Material, und Solidon kennt nur das zweite.
  Stand sie allein auf `hot_plate_temp` und der Slicer las „Cool Plate", ging
  ein PETG-Druck mit 35 Grad Bett hinaus — dieselbe Falle wie bei den
  Haftungsarten, wo ein ungenutztes Maß als eigener Schalter wirkt.

`profile_file` fragt `find_profiles` **nach der Art, die es sucht**. Die
Vorgabe kennt nur Maschinen und Prozesse; wer ohne Angabe nach einem Filament
sucht, findet nie eines — und dann fehlt das ganze Herstellerprofil, nicht nur
sein Name.

Und die Pfade zum Slicer sind **absolut**, bevor er läuft: `slice_model` setzt
sein eigenes Arbeitsverzeichnis. Ein relativer Pfad besteht die Vorprüfung —
sie sucht im Verzeichnis des Aufrufers — und scheitert erst im Slicer, als
„No such file".

## Eine Platte ist eine Datei

Was zusammen gedruckt wird, geht als **eine 3MF-Baugruppe** hinaus
(`threemf.write_assembly`), nicht als eine Datei je Objekt. Der Unterschied
ist nicht das Format: ein Slicer, der eine Baugruppe bekommt, ordnet sie als
Ganzes an und schreibt eine Druckdatei. Bekommt er fünf Dateien, entscheidet
er über ihre Zusammengehörigkeit selbst, und was Solidon über die Platte
weiß, ist verloren.

Die Materialslots werden dabei über **alle** Teile zusammengelegt
(`merge_slots`), über Name, Farbe, Materialprofil und Materialart. Ein Slot ist
ein Filament, kein Objektmerkmal — dieselbe Farbe allein beweist nicht dieselbe
Spule. Die
Reihenfolge der zusammengelegten Liste *ist* die Extruderbelegung.

**Und jede Platte ist ein Lauf.** Eine Szene mit mehr Teilen, als auf ein Bett
passen, ist der Normalfall (§25); die Übergabe geht sie deshalb einzeln durch,
mit eigener Baugruppe, eigenen Slots, eigener Anordnungsprüfung und eigener
Druckdatei. Der Name trägt die Plattennummer, sonst schreibt die zweite die
erste über. Das gilt für alle drei Familien — die Orca-Familie könnte mehrere
Platten in einer Projektdatei führen, Cura und PrusaSlicer nicht.

Zeit und Material addieren sich über die Platten (`gcode.combine`), denn
zweimal gedruckt ist zweimal. Die **Schichtzahl nicht**: sie beschreibt eine
Platte, über zwei summiert wäre sie eine Zahl, die es nirgends gibt. Und fehlt
ein Wert bei einer Platte, fehlt die Summe — sonst stünde eine Gesamtzeit da,
die zu kurz ist, ohne dass jemand es sehen kann.

## Die Gegenprobe ersetzt die Dokumentation

`handover.verify` liest die Konfigurationskommentare der erzeugten Druckdatei
und meldet, was der Slicer anders übernommen hat, als Solidon es schrieb.
Das ist die einzige Auskunft, die vom Programm selbst kommt statt aus einer
Beschreibung, die für die installierte Version gelten mag oder nicht — und
damit prüft sich auch ein Slicer, den beim Bauen der Tabelle niemand vorliegen
hatte.

Gemeldet wird nur, was **nachweislich** abweicht. Ein Schlüssel, den die Datei
nicht nennt, sagt nichts: kein Slicer schreibt alles, und eine Gegenprobe, die
bei jedem Lauf zwanzig Fehler meldet, wird nach dem dritten Mal übersehen.
Verglichen wird nachsichtig — `0.2` gegen `0.20`, `15%` gegen `15`, eine Liste
aus einem Element gegen dieses Element.

## Die Schätzung ist eine Näherung mit Herkunft, keine Rechnung

`slice/estimate.py` beantwortet „was kostet das" in Mikrosekunden, damit die
Zahl beim Ziehen an einem Parameter stehen bleiben kann. Zwei Dinge daran sind
teuer erkauft:

**Die Schale ist die Differenz zweier Körper, nicht Fläche mal Dicke.**
`Oberfläche mal Wandstärke` zählt jede Kante doppelt — beim 20-mm-Würfel
3024 mm³ statt 2659 — und der Fehler ist kein Rauschen, sondern ein Aufschlag:
gemessen +5 bis +22 Prozent an vier analytischen Körpern und +10 bis +41 an
sieben Modellen. Gerechnet wird über die mittlere Wanddicke `3V/A` (für Kugel
und Würfel genau der Inkugelradius) und den Kern als deren dritte Potenz.

**Und ein Modell an kompakten Körpern zu prüfen, prüft es nicht.** Der
Zwischenstand mit Hüllmaßen traf Würfel, Kugel, Blech und Stab auf zwei
Prozent und lag bei zwei flachen Regalteilen 41 und 49 Prozent zu niedrig: Ein
Hüllquader hält einen Rahmen aus dünnen Stegen für einen flachen Klotz. Wer die
Rechnung anfasst, prüft **beide** Familien — kompakt und dünnwandig —, und
`tests/test_estimate.py` hält je einen Fall dafür.

Was die Schätzung nicht kann und nicht können soll: Stützen, Schürze, Rand,
Fahrwege, Nahtstellen, Lückenfüllung. Sie trägt `source="internal"`, steht neben
dem gemessenen Wert und wird nie mit ihm vermischt (Regel 14).

## Was die Analyse liefert

Überhangfläche je Schicht, Stützvolumen, Querschnittsverlauf, **Inseln**
(Konturen ohne Verbindung nach unten), erste Schichtfläche, Brückenweiten,
kleinste Strukturbreite gegen den Düsendurchmesser. Der Gewinn ist der
Maßstab: hunderte Rotationen in der Orientierungssuche statt drei extern
geslicter Kandidaten.

Zwei Breiten, zwei Fragen — und sie sind nicht dieselbe Zahl.
`minimum_width` ist die **kleinste Struktur** einer Schicht: eine
morphologische Öffnung (erodieren, wieder aufweiten) und die Frage, ab welcher
Breite dabei Material verloren geht. Der größte einbeschriebene Kreis
beantwortet das nicht — eine 0,3-mm-Rippe neben einer 20-mm-Platte hatte darin
bis zum 02.09.2026 keine Spur. `spanning_width` ist die **weiteste freie
Stelle** einer ungestützten Fläche, also der einbeschriebene Kreis. Als
Brückenweite genügt sie bei umlaufender Auflage. Bei offenen Seiten werden
Richtungen entlang der Konturkanten und ihrer Normalen geprüft; beide Enden
jeder freien Bahn müssen aufliegen. Eine kurze, aber ungestützte Querrichtung
verkürzt keinen Steg. Ohne beidseitig getragene Richtung bleibt das Ergebnis
eine konservative geometrische Schätzung, keine Werkzeugbahnplanung.

**Die Öffnung sagt Nein aus den Teilen und Ja aus der ganzen Form** (RM-109).
Der Flächenverlust ist eine Summe über die getrennten Konturen einer Schicht,
und jeder Summand ist nicht negativ: Reißt schon der dünnste Teil das Budget,
steht das Nein fest, und die restlichen zweitausendachthundert müssen nicht
mehr gepuffert werden. Umgekehrt gilt das nicht — berühren sich die Öffnungen
zweier Teile, zählt die geteilte Fläche in der Summe doppelt, der Teileweg
unterschätzt den Verlust also. Ein Ja kommt deshalb immer aus der ganzen Form,
und `WIDTH_SCAN_PARTS` deckelt, wie viel vergebliche Arbeit der Teileweg davor
kosten darf. Wer an dieser Stelle etwas ändert, prüft beide Richtungen gegen
`_opening_loss` über der ganzen Form — die Halbierung fragt jede Weite
einzeln, und eine verschobene Antwort verschiebt die gemeldete Breite.

**Ab wann eine freie Fläche eine Brücke ist, sagt der Drucker** (Regel 7,
RM-097). Es sind zwei Extrusionsbahnen — darunter kragt die Wandlinie selbst
vor und liegt zur Hälfte auf der Schicht darunter, darüber muss der Slicer
quer spannen. Die Zahl stand als runder Millimeter im Code und begründete sich
mit „zwei Bahnen einer 0,4er-Düse": Das sind 0,84. `slice_body` nimmt sie als
`bridge_from` entgegen, wie den Überhangwinkel daneben und aus demselben
Grund — die Schichtanalyse bleibt von Profilen entkoppelt und nimmt Zahlen.
Hereingegeben wird `Profile.minimum_wall_thickness`, über
`profiles.analysis_limits` die größte Mindestwand der tatsächlich verwendeten
Materialien.

Gemessen an zwei Pfeilern mit 1,0 mm Spalt und einer Decke darüber: Der
Centauri meldet 0,9 mm Brücke, eine 0,8er Düse schweigt zu Recht, und die alte
Codezahl schwieg für beide. **Wer die Zahl zwischenspeichert, nimmt sie in den
Schlüssel** — der Messwertspeicher des Druckdialogs trägt sie neben dem
Winkel, denn sein Geometriekontext kennt die Materialien nicht.

Eine einzelne variable Arachne-Bahn kann eine dünne Wand drucken. Die
Zwei-Bahn-Betrachtung begründet daher keine allgemeine Aussage, dass eine
Wand nicht druckbar sei. Unterhalb der angesetzten Mindestbahnbreite fordert
der Befund eine Kontrolle der tatsächlichen Materialbahnen im Slicer.

## Stabile IDs

Feature-Erkennung liefert Provenienz-IDs, an denen Ops und Passungen hängen.
Eine ID muss eine Neuberechnung überleben — sonst zeigt der Op-Stack nach der
nächsten Änderung ins Leere. Mehrdeutige Zuordnung hält an und fragt, statt
die nächstbeste zu nehmen.

Analysekarten sind teuer: sie laufen im Hintergrund, sind abbrechbar und
halten das Budget aus §31 ein (Wandstärke unter 3 s, Schichtanalyse bei
200 000 Dreiecken und 0,2 mm unter 300 ms). Farbskala wahrnehmungsgleich, nie
Regenbogen.

## Auf einer Freiform sind Kugel, Ring, Kegel und Verrundung keine Merkmale (05.09.2026)

Eine gekrümmte Fläche passt örtlich immer auf eine Kugel; die Nachtrennung an
Krümmungssprüngen zerlegt einen Scan oder eine Figur in Dutzende Flecken, und
jeder fittet. Ein Kiefer-Scan eines Kunden trug so 281 Rundformen und einen
echten Zapfen. `features.is_a_freeform` entscheidet an der fertigen Liste
(mindestens zwölf Kugeln und Ringe, mindestens sieben Zehntel aller
Merkmale — die Zahlen und die Modelle dazu stehen an den Konstanten),
`_shapes_on_a_freeform` nimmt dann die vier Rundformen heraus. Drei Sätze
dazu:

* **Bohrung, Zapfen, Fläche, Kantenzug und Gewinde bleiben.** Eine
  Zylindereinpassung erfüllt eine Freiform nur dort, wo wirklich ein Zylinder
  steckt; der Zapfen des Kunden war echt.
* **Nicht still.** `freeform_dropped` nennt die Zahl, und die Auswertung macht
  daraus `perceive.freeform` (Regel 17). Ein Merkmal, das verschwindet, ohne
  dass ein Satz sagt warum, ist schlimmer als eines, das dasteht.
* **Und der Satz nennt die Messung, nicht die Herkunft** (12.09.2026, RM-151).
  Er hieß „Dieses Modell ist eine Freiform, etwa ein Scan"; das liest ein Kunde
  als Aussage über sein Bauteil, und Roberts konstruierter `garden-hose-holder`
  kam mit einem Rundformanteil von 0,701 gegen die Schwelle 0,700 dorthin — um
  ein Tausendstel. Was er jetzt sagt, ist prüfbar: Die Oberfläche ist
  überwiegend gekrümmt, und an einer solchen sind die vier Rundformen keine
  Merkmale. **Ein zweiter Zustand** — „überwiegend rund" gegen „Freiform" —
  **kommt nicht**: Er kostete eine zweite Schwelle in einer Lücke, die schmal
  ist, und zwei Sätze, deren Grenze niemand nachmisst, sind schlechter als
  einer, der wahr ist.
* **Wer die Schwelle anfasst, misst an beiden Seiten** — an der Nozzle-Box
  (konstruiert, 59 Prozent rund) und an der Retro-Maus (Figur, 77 Prozent).
  Dazwischen liegt die Lücke, und sie ist schmal. Die Merkmals*zahl* und der
  Rand der Flecken (Knick oder Ebene) trennen nicht; beides ist gemessen und
  steht am Modul.

### Was an einer Bohrung hängt, bleibt (10.09.2026)

Die Lücke oben ist schmal, und am 10.09.2026 ist ein Modell hineingefallen:
Roberts `garden-hose-holder.3mf` ist ein konstruierter Halter, dessen
geschwungener Bogen 194 nicht veröffentlichte Kugel- und Ringkandidaten trägt.
Rundformanteil **0,701 gegen die Schwelle 0,700** — ein Tausendstel —, und mit
den 51 erfundenen Kegeln fielen auch seine vier echten 90-Grad-Senkungen.

**Nicht die Schwelle wurde nachgezogen, sondern die Frage geschärft.** Ein
Zehntel Prozent an einer Zahl zu drehen, die siebzehn Modelle trennt, träfe den
nächsten Grenzfall mit demselben Fehler. Stattdessen bleibt, was sich
**belegen** lässt: eine Rundform, die an der Mündung einer Bohrung sitzt, die
selbst bleibt (`features.sits_at_the_mouth_of`). Eine Freiform hat dort keine
Bohrung, an der eine Erfindung hängen könnte.

**Zwei Messungen, und sie sagen Verschiedenes.** Der *Filter* rettet am Halter
genau 4 von 55 Kegeln und an jeder Figur des Korpus null. Die *Bedingung*
trifft daneben an `plate_countersunk.stl`, `plate_countersunk_blind.stl` und
`plate_chamfer_and_taper.stl` je die echte Senkung und nicht die Verjüngung —
diese drei sind aber **keine Freiformen** (`freeform_dropped` ist dort null)
und laufen durch den Filter gar nicht. Wer den ersten Satz mit dem zweiten
belegt, belegt ihn mit Modellen, die die Stelle nie erreichen.

**Wer die Bedingung anfasst, misst beide Reihen nach** — der Preis einer zu
weiten Fassung sind 55 Kegel statt vier.

Und die Folge, die den Anlass erst sichtbar machte: Ohne die Senkung findet
`relations.cavity_chain_at` die Kette Bohrung-Senkung-Bohrung nicht mehr. Ein
weggefiltertes Merkmal nimmt die Nachbarschaften mit, die es trägt.

## Ein Hohlraum ohne Weg nach außen ist keine Bohrung (10.09.2026)

Dasselbe Modell trug acht eigene geschlossene Schalen mit **negativem**
Volumen, je Ø 2 auf 9 mm — Negativkörper, die ein CAD oder Slicer mitschrieb
und nie boolesch abzog, gemessen zu 100 Prozent innerhalb des Hauptkörpers.
Nach `_one_body` liegen ihre nach innen zeigenden Mäntel im selben Netz, und
für `detect_holes` sah das aus wie eine Bohrung: dieselben Normalen, derselbe
Kreis, nur ohne Öffnung. Der Objektbaum zeigte acht Bohrungen, die man weder
sehen noch bohren kann (Robert: „Bohrungen, die im Inneren des Materials sind,
was nicht sein kann").

`detect_voids` gibt sie als eigene Merkmalsart `void` aus, und
`_voids_instead_of_phantom_bores` nimmt weg, was mehrheitlich auf ihrer Schale
liegt. Vier Sätze dazu:

* **Vier Tore, drei topologische und eine geometrische Probe.** Das Netz ist
  dicht, sein Umlaufsinn einheitlich, es hat mehr als eine Komponente — und
  die Schale liegt im Material der **festen** Komponenten. An einem offenen
  Netz sagt ein Vorzeichen nichts; dort wird nicht geraten (Regel 21), und die
  Bohrungen bleiben, wie sie waren. Über den ganzen Korpus trifft das null
  Mal, auch nicht an `two_components.stl` oder `broken_selfint.stl`.

  **Das vierte Tor fragt gegen das Material, nicht gegen „alles andere".** Der
  erste Anlauf nahm je Kandidat alle übrigen Komponenten als Umgebung, die
  anderen Hohlraumschalen eingeschlossen — und damit fiel jeder Einschluss
  durch, der einen Nachbarn hatte: Der nächste Ort lag auf **dessen** Mantel,
  und dort steht die Normale quer zum Versatz. Gemessen an zwei Taschen Ø 2 in
  einem Quader: bei 2,5 und 5,0 mm Achsabstand null von zwei, bei 8,0 mm
  beide. Zurück waren genau die Phantombohrungen, wegen derer die Sache
  angefangen hat. Am Kundenmodell fiel es nicht auf — dort liegen die acht
  weit genug auseinander, und das ist Glück und keine Zusicherung.
* **Benannt, nicht verschwiegen** (Regel 17). Ein Einschluss ist im Zweifel
  ein Defekt: Beim Drucken bleibt Luft darin. Ihn stillschweigend wegzufiltern
  machte den Objektbaum richtig und den Kunden ahnungslos (Entscheidung
  Robert, 10.09.2026 — gegen die Alternativen „nur Befund" und „nur
  wegfiltern"). **Er steht im Objektbaum und nicht im Prüfbericht**: Es gibt
  keinen `perceive.void`, weil die Merkmalsart selbst die Auskunft ist —
  „Lufteinschluss 3 · 28 mm³". Wer beides will, baut den Befund in derselben
  Bauart wie `perceive.freeform` (`scene/evaluate.py`); heute ist es einer,
  und dieser Satz sagt welcher.
* **Und er ist nicht gesperrt.** Der erste Entwurf sperrte alles mit der
  Begründung, an einen eingeschlossenen Hohlraum komme kein Werkzeug heran —
  und das war messbar falsch: `test_a_cavity_inside_the_body_moves_without_
  losing_material` versetzt seit dem 03.09.2026 eine Kugelhöhle in einem
  Würfel, und an Roberts Bauart nachgemessen bleibt das Volumen des Ganzen auf
  **0,000000 mm³** genau gleich. `void` steht deshalb in `MOVABLE_KINDS`.

  Was fehlt, ist nicht die Erreichbarkeit, sondern das **Maß**: Ein Einschluss
  ist, was ein Negativkörper hinterlassen hat, und seine Form steht allein in
  seinen Flächen — Größe und Drehung haben nichts, woran sie ansetzen könnten.
  **Verdoppeln fehlt aus einem anderen Grund**, und der ist keine Geometrie:
  Eine zweite Luftblase im Material legt niemand an (Robert, 10.09.2026).
  Deshalb `DUPLICABLE_KINDS` neben `MOVABLE_KINDS` — zwei Fragen, zwei Listen.
* **Und er ist nicht immer ein Fehler.** Die Aussparung für einen eingegossenen
  Magneten und ein vergessener Negativkörper sind topologisch dieselbe Sache.
  Welche von beiden vorliegt, weiß nur der Kunde; Solidon benennt, was da ist,
  und urteilt nicht.
