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
- **Der Bauraum hat je Familie andere Koordinaten** (`handover.bed_box`). Cura
  und PrusaSlicer bekommen von Solidon eine Maschine um den Ursprung, die
  Orca-Familie lädt ihr eigenes Profil und misst von der Ecke. Beides zu
  verwechseln kostet einen falschen Befund bei jedem Lauf.

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
fördert der Antrieb mehr, als das Hotend flüssig bekommt, die Bahn wird dünner
als gerechnet, und an den Einstellungen sieht man nichts. Zwei Auswege, beide
werden genannt und keiner erzwungen: heißer, solange die Maschine das kann,
sonst langsamer.

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

Vorgeschlagen wird die **Wandzahl**, nicht die Füllung — Wände liegen
deterministisch um den Zapfen, Füllung trifft ihn statistisch.

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
(`merge_slots`), über Name und Farbe. Ein Slot ist ein Filament, kein
Objektmerkmal — zwei Teile in derselben Farbe kommen aus derselben Düse. Die
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
Stelle** einer ungestützten Fläche, also der einbeschriebene Kreis; für eine
Brücke ist das die richtige Zahl, weil ein 0,2-mm-Ausläufer eine 40-mm-Öffnung
nicht leichter macht. Wer die eine für die andere nimmt, bekommt entweder
Rippen, die niemand sieht, oder Brücken, die keine sind.

## Stabile IDs

Feature-Erkennung liefert Provenienz-IDs, an denen Ops und Passungen hängen.
Eine ID muss eine Neuberechnung überleben — sonst zeigt der Op-Stack nach der
nächsten Änderung ins Leere. Mehrdeutige Zuordnung hält an und fragt, statt
die nächstbeste zu nehmen.

Analysekarten sind teuer: sie laufen im Hintergrund, sind abbrechbar und
halten das Budget aus §31 ein (Wandstärke unter 3 s, Schichtanalyse bei
200 000 Dreiecken und 0,2 mm unter 300 ms). Farbskala wahrnehmungsgleich, nie
Regenbogen.
