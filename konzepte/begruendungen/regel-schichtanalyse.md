# Begründungen zu `.claude/rules/schichtanalyse.md`

> Stand 27.09.2026. Aus der Regel verschoben, als sie auf das Einzuhaltende
> verdichtet wurde. Die Regel steht dort; hier steht, warum — mit den
> Messwerten und Anlässen ihres Tages.

Die Absätze sind wörtlich aus der Fassung vor der Verdichtung übernommen
(Commit `0372e5184`, dazu ein Absatz aus dem Zweig `uebergabe-gesamtpruefung`).
Wo eine Überschrift der Regel neu ist oder ihr Datum verloren hat, steht die
ursprüngliche darunter.

## Zwei Wege durch den Schnitt, und beide müssen dasselbe rechnen

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

[Hinweis zur Verdichtung: Die Messung „Der kompilierte Kern, nachgerechnet“
steht heute in `ROADMAP-ARCHIV.md`, nicht mehr in `ROADMAP.md`.]

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
  deckeln die Temperatur, ein offener Bauraum bekommt keine Kammertemperatur,
  und **die Leerfahrt kommt vom Drucker** (`PrinterProfile.travel_speed`, aus
  dem Standardprozess des Herstellerprofils). Ein Projekt von vorher bekommt
  sie als Vorschlag. Anlass: Die Waschschüssel ging mit den allgemeinen
  150 mm/s an einen Centauri Carbon 2, dessen Hersteller 500 fährt, bei 530
  Leerfahrten je Schicht — und zog ab Schicht 1 Fäden. **Dasselbe gilt dem
  Drucktempo** (`speed_*`, `acceleration`, `outer_wall_acceleration`): Es
  gilt für „Standard", jede andere Stufe behält ihr Verhältnis dazu
  (`print_settings._paced`), und `flow_factor` hebt den Volumenstrom des
  Materials auf das Hotend des Druckers (Centauri 21 statt 12 mm³/s).
  **Danach fördert kein Tempo mehr, als das Filament fließt**
  (`print_settings.flow_speed_limit`, dieselbe Rechnung wie die
  Volumenstromregel): Die Herstellertempi gelten seinem schnellsten
  Filament, und der Slicer bremst selbst — stünde das schnellere Tempo in
  der Datei, meldete die Beratung an jedem Teil vier Warnungen, ohne dass
  jemand etwas eingestellt hat. Ein älteres Projekt behält seine Tempi;
  schneller wird nichts vorgeschlagen, denn langsamer behebt keinen Fehler.
- **Was Solidon meint, wird geschrieben, auch das Muster.** „Gitter" ging bis
  zum 25.09.2026 als An/Aus und Art hinaus, das Muster blieb beim Hersteller —
  bei Elegoo `rectilinear`, Linien in einer Richtung, die als freistehende
  Wände umkippen. `rectilinear-grid` (Orca, PrusaSlicer) und `grid` (Cura,
  Linienabstand mal zwei) halten das Versprechen des Feldes; Bäume behalten
  das Muster des Herstellers (`slicer_keys._only`).

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

**„Viel auf einmal" heißt an einem Stück, nicht auf einer Schicht.** Die
Stützfrage las die Überhangfläche je Schicht als Summe, und ein Gitterbecher
(20.09.2026) trug auf seiner schlimmsten Schicht 278 mm² — in 56
Stegunterseiten zu je 5 mm², jede über 4,7 mm frei, jede trägt sich selbst,
gedruckt ohne eine Stütze. Die Summe sah darin dieselbe Decke wie beim
Deckel mit 138 mm² an einem Stück. Gefragt wird deshalb das größte
zusammenhängende Stück (`largest_overhang_patch`); ein Ergebnis, das seine
Stücke nicht mitbringt, gilt schichtweise als eines. Lange freie Stege fängt
die Brückenregel weiter ab.

**Ab welchem Winkel gestützt wird, sagt der Drucker, nicht die Startregel**
(27.09.2026). Bis dahin rechnete jeder Drucker mit 45 Grad, und die Übergabe
schrieb sie als Stützwinkel über den Wert des Herstellers. Am Minigolf-Satz
(`F:\3D Dateien\Mini+Golf+All+Set-P1S_stls`) verlangte das für die Fase einer
2-mm-Bodenplatte und 45 bis 55 Grad geneigte Wände Stützen (320 mm² in
Stücken bis 25 mm²). Der ElegooSlicer legte daraufhin 46 m Stütze in die
untersten 5 mm, 11 m davon in Schicht 1. Roberts erste Schicht am Centauri
Carbon 2 war ein treppenförmiger Stützfuß mit einem Brim aus 7 216 Stücken,
5 700 davon kürzer als ein Millimeter. Elegoo stützt ab 60 Grad, und ohne
Stütze ist das Teil dasselbe, 20 min schneller. Die Grenze steht deshalb je
Drucker in `printers.toml` (`overhang_limit`, Standardprozess im Slicer des
Herstellers). `Profile.overhang_limit_degrees` fragt Probe, Drucker,
Startregel in dieser Folge, und `print_settings.resolve` schreibt denselben
Winkel als `support.threshold_angle`. Ein Projekt von vorher bekommt ihn als
Vorschlag. **Wer einen Winkel an einer Stelle einführt, reicht ihn bis in jede
Vorauswahl durch**: Die Orientierungsheuristik urteilte bis dahin fest mit 45.

Mit Entscheidung L (Stufe L der Übergabe auf dem Herstellerprofil) rechnet die
Auswertung mit `Session.evaluation_profile` — den wirksamen Einstellungen des
Fensters, im Hauptthread vor jedem Lauf geholt —, Druckdialog-Rat und
Kanalsperre der Übergabe mit `profiles.for_process(..., effective=True)`.
Projekte aus 0.5.0 tragen 45 Grad ohne eigene Wahl; deshalb gilt die Schwelle
aus einem gespeicherten Satz nur als eigene Wahl. Kommt die Grundlage mit
anderer Schwelle erst nach dem Lauf, wertet das Fenster neu aus
(`Session.evaluation_follows`). (Aus der Regel verschoben, als sie beim Merge
der Release-Sitzung 0.5.1 über ihr Budget wuchs.)

**Und ein Überhangwinkel wird an der Normalen mit dem Sinus verglichen.** Eine
Fläche, die um α gegen die Senkrechte überhängt, trägt die Normale z = −sin α;
über der Grenze heißt z < −sin(Grenze). Die Vorauswahl verglich mit dem
Kosinus, und bei 45 Grad sind beide dieselbe Zahl, bitgenau. Mit 60 Grad hätte
sie ab 30 Grad Überhang gezählt statt ab 60. Wer eine Winkelgrenze an einer
Normalen prüft, prüft sie an einem Winkel ungleich 45
(`test_orient.py::test_the_preselection_counts_overhangs_against_the_printers_limit`).

**Eine Decke im Kanal verlangt keine Stütze auf dem Modell** (25.09.2026).
„Überall" war die Antwort auf jede Säule, die auf dem Modell endet — auch auf
die im Wasserkanal der Waschschüssel, den der Slicer daraufhin 40 mm hoch mit
Stütze füllte (Robert: „sinnlos und gehen durch das Modell"). Gefragt wird
jetzt je Stück (`analysis.model_support`): Fasst der freie Raum unmittelbar
**unter** der Decke keinen Kreis von `CHANNEL_WIDTH` (30 mm), der das Stück
enthält, liegt sie in einem Kanal und schließt sich als Brücke oder Gewölbe.
Unter der Decke, nicht auf halber Höhe: Der Kanal der Schüssel ist dort 42 mm
weit und unter seinem Gewölbe 22. Kanalstücke fallen aus dem Stützbedarf, und
was außen auf dem Modell aufsetzt, zählt nur über dieselben zwei Wege wie der
Stützbedarf selbst (ein Stück über `OVERHANG_LAYER_WORTH_SUPPORT` oder die
Summe über `OVERHANG_WORTH_SUPPORT`). Gegenfälle mit Zahl stehen an der
Konstante: Tisch, Kasten mit Innenregal (74 mm), verschlossener Hohlkörper
(54 mm) und weiter Tunnel (65 mm) behalten „überall". Wer die Grenze
anfasst, misst beide Reihen nach und fährt die Schüssel im Slicer.

**Eine Insel ist nie eine Kanaldecke** (26.09.2026). Sie hat nichts unter
sich, an dem eine Brücke ansetzen könnte; setzt sie auf dem Modell auf, heißt
es „überall", gleich wie klein (`ModelSupport.island_on_model`). Die frühere
Bedingung „keine Inseln" vor „nur vom Bett" ist dafür entfallen — eine Insel
über dem Bett erreicht das Bett.

**Und „nur vom Bett" hält einen Kanal nicht in jedem Slicer frei.** Orcas
organische Bäume wuchsen trotzdem hinein und führten die Stämme durch die
Wand. Deshalb der Vorschlag `support.block_channels`: Die Übergabe legt dann
eine Stützsperre in die 3MF, gebaut aus dem freien Kanalraum
(`analysis.channel_space` — je Millimeterscheibe die freie Fläche im Umkreis
der Kanalsäulen innerhalb der konvexen Hülle der Schicht, verbunden mit einer
Säule). Die Hülle ist die richtige Grenze: Ohne sie reichte die Sperre an
einem Tunnel 15 mm aus der Mündung. **Und jede Scheibe reicht eine
Scheibenhöhe in die Decke**: Der Slicer fragt die Sperre an der
Überhangfläche, in deren eigener Schicht, und dort ist die Decke Material.
Gemessen im ElegooSlicer an der Schüssel, Stütze im Sperrkörper: „Gitter
überall" 87,8 → 0,0 m, „Baum nur vom Bett" 22,5 → 1,7 m, in PrusaSlicer
„Gitter überall" 91,0 → 6,5 m; die Modellbahn bleibt gleich. **Die Zahlen vom
Vortag (22,9 → 0,5 m, 6,2 → 0,7 m) waren falsch**: Die Sperre wurde damals als
Kunststoff gedruckt und füllte den Kanal (`dateiformat.md`, „Was welcher
Slicer bekommt").
**Vorschlag, nicht Automatik:** Was ohne „Vorschläge übernehmen" zum Slicer
geht, sind die Standardeinstellungen (Entscheidung Robert, 26.09.2026).

**Die kleine Standfläche wird auch je Fuß gefragt** (26.09.2026). Die
Brim-Regel las die Summe, und die Waschschüssel steht in Drucklage auf zwölf
Füßen zu je rund 108 mm², zusammen 1417 mm² — kein Vorschlag, und Nutzer des
Designerprofils melden eine hebende Ecke. Steht ein Körper auf mehreren
Inseln und hat keine davon `SMALL_FOOTPRINT`, heißt es jetzt Brim
(`advise._on_small_feet`). Dieselbe Zahl, keine neue: Keiner der Füße hält,
was ein Teil für sich braucht. Im Korpus (447 Körper) trifft sie außer der
Schüssel sechs — Eiffelturm auf vier Beinen, Katze auf drei Pfoten, Schaber
auf zwei Auflagen; die Summenregel trifft 202. Orcas `auto_brim` fragt den
Hüllquader und legte an der Schüssel um einen Fuß einen Rand. **Nur als
Vorschlag:** `for_part` setzt beim Export weiterhin nur die Summenregel und
den schlanken Körper je Teil. Und wo die Stütze auf dem Bett bis an die Füße
reicht, legt der Slicer den Rand nur, wo Platz ist — an der Schüssel mit
Gitter vom Bett 236 mm.

**Schmale Stege bekommen eine langsame erste Schicht** (27.09.2026). Auf
Roberts Minigolf-Platte am Centauri Carbon 2 rissen zwischen den Löchern die
kurzen Bodenbahnen der ersten Schicht; Elegoos Standard legt deren Füllung
mit 105 mm/s. Mit 50 mm/s für die ganze erste Schicht lief derselbe Druck
sauber. Liegt ein Anteil der ersten Schicht von mindestens
`advise.NARROW_WEB_SHARE` in Stegen schmaler als `NARROW_WEB_LINES` Bahnen
(`analysis.narrow_share`) und ist die erste Schicht schneller als
`NARROW_WEB_SPEED`, schlägt `advise` dieses Tempo vor. Die Grenzen sind an
drei Modellen gemessen (Platte 22 %, Wedge-Lock 4 %, Schüssel 2 %); die
Gesamtprüfung über den Korpus prüft sie nach. Über dem Herstellerprofil
bremst der Vorschlag nur: Wände, die der Hersteller langsamer legt, bleiben
(Regel zur Übergabe in `dateiformat.md`).

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

[Hinweis zur Verdichtung: Seit „Entscheidung F“ der Übergabe geht die
Betttemperatur nur noch dann auf jede Platte, wenn die aufliegende unbekannt
ist (`handover._with_every_plate`); ist sie bekannt, setzt
`handover._on_the_plate` nur deren Schlüssel. Die Regel sagt das jetzt so.]

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

**Die Orientierungssuche misst Stützräume am Ersatznetz und den Stand am
Original.** Auf 20 000 Dreiecke ausgedünnt reicht ein Körper, um Stützräume
zu ordnen; ein 2 mm breiter flacher Rand überlebt die Ausdünnung aber nicht
als Ebene. Der Gitterbecher (94 990 Dreiecke, 20.09.2026) stand am Ersatznetz
mit dem Rand nach unten auf 5 mm², am Original auf 594 — die Suche verwarf
die Lage, die ohne Stützen druckt. `judge(footing_mesh=…)` misst
Aufstandsfläche und Schwerpunktlage am Original, die Vorauswahl bewertet
Ausgangslage, Achsen und große Körperflächen dort ebenfalls, und **die sechs
Achsen werden immer geschnitten**: Die Heuristik ordnet nach Standfläche
gegen nach unten zeigende Fläche, und an einem Gitter zeigt in jeder Lage
die Hälfte nach unten — jede liegende Lage stand vor der stehenden, und die
Schichtanalyse sah die richtige nie. Geschnitten werden damit höchstens
`FINALISTS` plus sechs Achsen plus die Ausgangslage; am Gitterbecher sind es
zwölf in 22 Sekunden, und wo die Zeit hingeht, steht in der Karte des
Moduls.

**Auto Splits Vorauswahl hält der billigsten stehenden Lage einen Platz.**
Auto Split schneidet je Teilstück nur drei Lagen (`best_face_candidate`,
`SUPPORT_ORIENTATION_CANDIDATES`), und schon eine Hälfte ohne stehende Lage
macht den Preis der Naht „unbekannt“. Seit die Überhanggrenze aus dem
Druckerprofil kommt (60 Grad an Elegoo, Bambu, Creality), wird eine
Schnittfläche, leicht gekippt, druckbar, und die Heuristik (Auflage gegen
Überhang gegen Höhe) reiht Kippungen auf eine Kante und liegende Lagen, die
rollen, vor die Lage auf dem Stift: Am gestreckten Prüfkörper des
Leistungstests lagen vorn drei Richtungen unter einem Grad auseinander, die
stehende Lage auf Rang 62, und alle sechs Nähte kosteten „unbekannt“. An 127
Modellen aus dem Korpus, je in der Mitte der längsten Achse geteilt, stand
an vier Hälften (zwei Modelle) bei 45 Grad eine der drei, bei 60 keine. Eine
Winkelsperre zwischen den gewählten Richtungen half nicht: Die Kippungen
liegen auf einem Kreis um die Schnittnormale.

Steht keine der drei vorderen, geht der letzte Platz deshalb an die Lage mit
dem kleinsten geschätzten Stützraum (`Orientation.support`), die nach
demselben Urteil wie danach steht: Auflage in halber Schichthöhe des
Druckers, Schwerpunkt über ihrer Hülle, was eine Linie davon trägt
(`orientation._stands_on`, ohne Schnitt durch den ganzen Körper; ein Test
hält beide Antworten gleich). **Nach der Schätzung, nicht nach der
Heuristik**: Die Heuristik weiß nicht, wie hoch ein Überhang hängt, und
reihte am Balken mit gekreuzten Überhängen das ferne Ende (geschätzt
254 883 mm³) knapp vor die Schnittfläche (6 419 mm³); die Nahtpreise lagen
dadurch an echten Nähten 1,4- bis 39-fach zu hoch. **Ohne Vorprüfung an der
geschätzten Auflage**: Die zählt nur Dreiecke, die fast genau nach unten
zeigen, und ein gestreckter Ring, dessen Hälften flach auf gut 600 mm²
stehen, behielt mit ihr jede Naht „unbekannt“. Geschnitten werden weiter
genau drei Lagen. Was die Prüfung kostet, fängt `_contact` auf: Es sucht die
Dreiecke an der Aufstandsebene über die Ecken darunter statt über alle Ecken
aller Dreiecke, 2 statt 5 ms an einer Hälfte mit 100 000 Dreiecken, und
dieselben Dreiecke — das Urteil rechnet damit bitgleich.

**Und die dritte Breite ist keine Zahl, sondern eine Strecke.** `taper_length`
misst je Schicht, wie viel Außenkontur auf einem **Keil** liegt: einer Wand,
deren Stärke stetig über mehrere Bahnen läuft, statt gleich zu bleiben oder
zu springen. Gemessen wird der Abstand der Außenkontur zur nächsten
Innenkontur alle Millimeter, vektorisiert in GEOS; gezählt wird, was zwischen
0,6 und 4 mm liegt und sich gegenüber dem Partner vier Millimeter weiter um
mindestens 0,15 mm unterscheidet, ab acht Millimetern am Stück. Eine
gleichmäßige Wand hat keinen Anstieg, auch um eine Rundung; eine Trennwand,
die rechtwinklig anschließt, springt aus dem Band, und ihr Partner zählt
nicht. Ein Teil ohne Innenkontur hat keine Wand in diesem Sinn.

Warum das eine eigene Messung ist: Ein Slicer mit variabler Bahnbreite
wechselt auf einem Keil die Wandzahl Bahn für Bahn, und die Übergangsstücke
der zuerst gelegten Innenwände wölben die Außenwand darüber. Gemessen am
Organizer vom 20.09.2026 (Außenwand 1,0 mm, in jedem spitzen Ende ein Becher,
der die Wand berührt): 24 mm Umfang von 1,0 auf 3,0 mm, an 460 von 500
Schichten, gedruckt mit Solidons Werten aus 0.4.3 — ein Band aus Rillen über
die ganze Höhe, an beiden Enden, nur an der Keilstelle. Daraus der Vorschlag
„Außenwand zuerst" (`advise.py`), sobald ein Fünftel der Schichten einen Keil
trägt, der Wandgenerator variabel ist und keine Stützen nötig sind: Eine
zuerst gelegte Außenwand kragt an steilen Überhängen ohne Innenwand neben sich
vor, und dort wäre der Tausch der schlechtere. Was das kostet, ist gemessen:
0,1 s an den 500 Schichten des Organizers, nichts am Gitterbecher, dessen
Stege keine Innenkontur haben.

**Und gemessen wird der Keil an jeder fünften gemessenen Schicht**
(`TAPER_SAMPLE`, 21.09.2026), die dazwischen tragen den Wert der zuletzt
gemessenen. Der Keil ist eine Eigenschaft der Wand über ihre Höhe, der Leser
fragt nach einem Fünftel aller Schichten — fünf Schichten Unschärfe an jedem
Ende ändern die Antwort nicht, und an einer Vase kostete die Messung an jeder
Schicht ein Drittel der ganzen Analyse (303 ms von 1276). Was die Stichprobe
nicht mehr sieht, steht als Test in `test_slice.py`: Ein Keil, der kürzer ist
als fünf Schichten, wird je nach Lage verfehlt oder fünffach gezählt — beides
unter jeder Schwelle, die ihn liest. Wer ihn je Schicht braucht, fragt
`taper_length(shape)` selbst.

## Die Öffnung zählt, was der Form fehlt

Die kleinste Strukturbreite fragt eine morphologische Öffnung mit gefasten
Ecken. **Deren Flächenbilanz ist keine Antwort**: Die gefaste Aufweitung eines
spitz endenden Stücks treibt eine Nadel über die Form hinaus, und die Fläche
draußen gleicht den Verlust drinnen aus — am 22.09.2026 meldete ein
Organizer „mindestens 2 mm", wo 0,47 mm stehen. Drei Dinge gelten deshalb:

- Ein **Nein** darf aus der Bilanz kommen (sie ist eine untere Schranke), ein
  **Ja** nur aus dem, was der Form fehlt (`_protrusion`).
- Splitter der Erosion unter `WIDTH_SIMPLIFY` werden nicht aufgeweitet.
- Was vom Anfangspunkt eines Rings abhängt — Douglas-Peucker, eine Abtastung
  in festen Schritten —, bekommt die geordnete Kontur (`_canonical`). Sonst
  rechnen der übersetzte und der GEOS-Weg verschiedene Zahlen.

Wer eine dieser drei Stellen anfasst, vergleicht an echten Modellen gegen die
exakte Differenz `Form − Öffnung`, Schicht für Schicht, und misst die Zeit
in beide Richtungen: vorher/nachher und auf einem wie auf sechs Arbeitern.

## Die Befunde im Prüfbericht kommen nach der Auswertung

`slice/findings.py` berichtet Inseln, frei hängende Flächen, lange Brücken,
die schmalste Stelle und eine Lage mit weniger Stützen — **jeder Befund mit
Ort und Handlung und mit `source="internal"`**. Er läuft im Arbeiter nach der
Auswertung (`ui/print_findings_flow.py`), nie in ihr: eine Schichtanalyse
kostet an 200 000 Dreiecken Sekunden, und die Auswertung läuft bei jedem
Klick. Gemerkt wird am Netz; der Schlüssel nennt alles, was das Ergebnis
bestimmt (Raster, Winkel, Brückenbreite, Drucker).

## Stabile IDs

**Eine geteilte Fläche heißt am größten Stück weiter** (27.09.2026,
Durchsicht 0.5.1, R4; `evaluate._divided_partners`). Ein Stück hat weder Lage
noch Größe der alten Fläche, also findet die Zuordnung es nicht; gesucht wird
es in ihrer Ebene, innerhalb ihrer alten Dreiecke. Drei Grenzen:
Gleich große Stücke sind eine Frage und keine Wahl (Regel 21) — gestellt,
sobald ein Verweis daran hängt. Die alten Dreiecke gelten nur, wenn sie diese
Fläche sind (Normale und Ebene); Nummern, die eine Operation an ihrem eigenen
Ergebnis vergeben hat, geben keinem Stück einen Namen. Und nach einer
Bewegung wird nicht gesucht. Eine Operation, die eine querende Fläche teilt,
gibt sie beiden Hälften mit (`prepare_ops._features_after_split`).

**Zwillinge entscheidet die Lage ihrer Oberfläche** (28.09.2026, Paket muster
der Release-Sitzung 0.5.1; `matching.settled_by_surface`). Drei Bögen eines
Grats haben für den Merkmalsvektor dieselbe Mitte, Achse und Größe; `match`
meldete sie nach jedem Schritt mehrdeutig, ohne Verweis kamen sie unter neuen
Namen zurück, mit Verweis als Frage. Am Korpus waren es nach *Kanten
verfeinern*, *Bohrung setzen* und *Verschieben* je 355, 167 und 165 Merkmale an
über 40 Körpern (Siebhalter-Ring, Rankenclip, Filterball, Besteckkörbe,
Bildschirmabdeckungen), danach keines. Gemessen wird der flächengewichtete
Schwerpunkt der Dreiecke — unabhängig von der Teilung, daher trägt er auch das
Verfeinern —, der alte im Eingangsnetz samt Bewegung. Der Vorsprung gilt in
Millimetern (Faktor `AMBIGUITY_MARGIN` plus `units.MAX_FACET_SAG`), nicht mit
der Untergrenze der Zuordnung: Die Stufen einer geprägten Schrift liegen 0,08 mm
übereinander, und die alte Oberfläche liegt bis auf Rundung genau auf einer.
Gleich große Stücke einer geteilten Fläche bleiben eine Frage; deshalb läuft
die Entscheidung vor `_divided_partners`.

Ein Verlust ohne Verweis wird **einmal je Körper und Schritt** gemeldet, nie je
Merkmal (`perceive.orphaned`/`perceive.mended`, Zahl und Kennungen in den
Werten). Ein Formschritt kann viele erkannte Flächen verlieren; ihre Kennungen
bleiben vollständig im Befund erhalten. Ein Verlust mit Verweis bleibt je
Merkmal eine Warnung — diese
Zusammenfassung darf ihn nie aufnehmen (§21.3).

Analysekarten sind teuer: sie laufen im Hintergrund, sind abbrechbar und
halten das Budget aus §31 ein (Wandstärke unter 3 s, Schichtanalyse bei
200 000 Dreiecken und 0,2 mm unter 300 ms). Farbskala wahrnehmungsgleich, nie
Regenbogen.

## Jede Schwelle der Erkennung wird an beiden Seiten gemessen

Neu als Überschrift: Die Regel fasst die „Wer … anfasst, misst beide
Seiten“-Sätze der einzelnen Erkennungsregeln zusammen. Die Modellreihen
stehen bei ihren Regeln in den folgenden Abschnitten.

## Ein Löserlauf entfällt nur mit dem Nein des Stapels

*Warum der Stapel schnell rechnen darf* (Review stapel, B3): `kern.md` erlaubt
schnelle Wege für Anzeige, Bericht und exakt nachgeprüfte Vorauswahlen. Das
Nein des Stapels prüft niemand nach — es nimmt den echten Lauf weg. Getragen
wird es von seinen Abständen: Unter `platform_noise()` (ein ULP auf BLAS,
einsum, LAPACK, Winkelfunktionen) kippte an fünf Beulenkugeln mit 1 484
Läufen kein Urteil und keines war falsch (Review-Sonde G); ohne Abstände gab
es unter 4 700 synthetischen Aufgaben genau ein falsches Nein (Ring an einem
Zylinderstück, Sonde H), mit Abständen keines. Beides steht als Test in
`tests/test_refine.py`.

*Was der Stapel festhält* (Review stapel, B1 und B4): Er liest jede Lesung
der Runde vorab; der Merker hält davon nur `SUPPORT_CACHE_LIMIT`, und
`classify` las jede ein zweites Mal, ebenso `_rigid_key` (Freiform der
Leistungstests 3 896 statt 1 949 Lesungen). Deshalb antworten beide in der
Runde aus dem Wissen des Stapels. Die Lesungen der Runde hält er bewusst fest,
solange sie läuft, und das kostet Speicher: Am Meshy-Murmelbrett hält das Wissen
192 bis 226 MiB je Runde — knapp die Hälfte der Lesungen gehört zu Flecken ohne
Plan, dazu kommen in der Stückrunde 54 MiB Kennzahlen, die erst der Nachtrag
festhält. Die Spitze des ganzen `detect` steigt dort um rund 90 MiB (2 388 → 2 481
MiB, gemessen gegen `aa82afdff`; +3,9 % Arbeitssatz, +3,6 % zugesagter Speicher)
für rund ein Viertel weniger Rechenzeit. Hebel für später: die Kennzahl als
16-Byte-Abdruck statt des Feldes halten, das nähme die 54 MiB weg (Review
stapel, B9). Der Stapellauf selbst
behält vom Weg nur das laufende Maximum von Plan-Schatten-Abstand und Betrag;
der ganze Weg wog an einem vollen Block 149 MiB. Die Blockgröße folgt der
gemessenen Spitze (`BATCH_BYTES`, `BATCH_PEAK_FACTOR`): am Meshy-Murmelbrett
höchstens 64 statt 299 MiB je Block, Urteile Problem für Problem gleich.

RM-209, RM-132, RM-193 (Paket stapel der Release-Sitzung 0.5.1). Eine
Verfeinerung, die ihr Budget ausschöpft, liefert nichts (RM-210) — an der
Kumiko-Schale 442 von 467 Kegelläufen, am Meshy-Murmelbrett 4 995 von 15 800
Kegel- und 1 487 von 5 203 Ringläufen, jeder hundert Auswertungen lang. Neun
Siebe aus Fleckmerkmalen sind gemessen und verworfen (Tabelle in RM-209), und
ein Nachweis aus der Geometrie scheidet aus: Einen fast ebenen Splitter nähert
ein Kegel mit 85° beliebig gut an; ob der Löser dorthin kommt, steht nur im
Lauf.

Deshalb rechnet `refine.exhausted` den Lauf selbst, für alle Flecken einer
Runde zugleich — SciPys `trf_no_bounds` Zweig für Zweig in NumPy — und
übernimmt nur das sichere Nein. Gemessen gegen den echten Lauf (Sonden
`p55`, `p59`, `p63` im Paket stapel):

- Weg nach hundert Auswertungen: median 2,5e-14, höchstens 2,8e-11 relativ in
  den Parametern; gleiche Auswertungszahl in 465 von 467 Kegelläufen der
  Kumiko-Schale.
- An jedem bestätigten Lauf dieselbe Schrittfolge wie im echten Lauf, dieselbe
  Zahl innerer Newton-Schritte, und die Abweichung in den Größen, an denen
  Zweige hängen, nutzt höchstens 5,8e-4 des Abstands zur Schwelle
  (`DECISION_MARGIN`; Kumiko, Drache, Meshy).
- Keine falsche Absage an allen Läufen von Kumiko-Schale, Drache, Freiform und
  Meshy-Murmelbrett (21 000 Läufe, 4 846 sicher vergeblich an Meshy).

Die feste Arbeit je Runde (gut hundert NumPy-Aufrufe, die Zerlegung je Problem
etwa vier Mikrosekunden) lohnt sich erst in Gruppen von einigen Dutzend
Problemen; darunter rechnet der echte Löser (`MIN_BATCH`). Große Flecken mit
Tausenden Stützpunkten spart der Stapel nicht: Dort ist die Rechnung, nicht der
Aufruf, das Teure.

## Auf einer Freiform sind Kugel, Ring, Kegel und Verrundung keine Merkmale

*Ursprüngliche Überschrift: „Auf einer Freiform sind Kugel, Ring, Kegel und
Verrundung keine Merkmale (05.09.2026)“*

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

### Die Haut wird nicht in Splitter zerlegt

*Ursprüngliche Überschrift: „Die Haut wird nicht in Splitter zerlegt
(22.09.2026, RM-193)“*

Roberts Drache aus TripoSG (325 244 Dreiecke) ist bei der 30-Grad-Trennung
**ein** Fleck mit 93 Prozent der Oberfläche; die Nachtrennung nach Krümmung
machte daraus 27 577 Stücke, Median zwei Dreiecke, und jedes ging durch
Zylinder, Kegel, Kugel und Torus — 33 der 37 Sekunden für null Merkmale, und
am Ende verwarf der Filter oben ohnehin alles. Entscheidung Robert: das Beste
für alle draußen, auch für den Zahntechniker.

* **Die Haut ist die zerfallende Fläche über zwei Dritteln der
  Oberfläche** — Flecken ohne Grundform, die nach Krümmung in
  `FREEFORM_SPLINTERS` oder mehr Stücke unter `FREEFORM_PIECE_SHARE`
  zerfallen, **über alle Flecken zusammen** (`FREEFORM_SKIN_SHARE`). Die
  Summe, weil die Zauberturm-Figuren ihre Haut in zwei Flecken tragen (44 und
  32 Prozent); die zwei Drittel, weil darunter Konstruiertes liegt: ein Rohr
  mit Gewinde bei 57 und 60, ein Scraper-Griff bei 51, ein Wandhalter bei 55
  — mit einer Schwelle von der Hälfte verloren alle drei ihre Verrundungen,
  Senkungen und Ringe. Figuren, Scans und erzeugte Netze liegen bei 71 bis 94.
* **Das Urteil fällt einmal je Körper, zwischen den beiden Runden** — nach
  `classify` über alle Flecken und nach `_split_patches_by_curvature` über die
  gescheiterten, vor dem ersten Splitstück. Nicht je Fleck und nicht beim
  ersten Fehlschlag: Dann hinge es daran, welcher Fleck zuerst scheitert.
* **Dass die Stücke dadurch zurückgestellt werden, kostet an zehn von 489
  Korpuskörpern Merkmalsgrenzen — gemessen, nicht geschätzt.** Wer ein Stück
  später einpasst, zeigt ihm eine vollständigere Ringkandidatenliste, und
  `_cylinder_beside_a_torus` entscheidet daraufhin anders: am
  Gartenschlauchhalter ein Kegel mehr, am Beckenreiniger werden aus drei
  Verrundungen fünf kleinere, an der Kumiko-Schale drei weniger. Dieselben
  Rundungen, anders geschnitten. Das ist der Preis dafür, dass das Urteil
  nicht mehr an der Reihenfolge hängt; wer die Runden wieder verschränkt,
  bekommt die Reihenfolgeabhängigkeit zurück und die Bowlingkugel dazu.
* **Gezählt wird nur, was keine Grundform ergeben hat — und das steht erst
  fest, wenn jeder Fleck einmal eingepasst wurde.** `_fitted` läuft deshalb in
  zwei Runden: erst `classify` über alle Flecken, dann die Nachtrennung über
  die gescheiterten, dann deren Stücke. Der Preis dafür, es früher zu wollen,
  ist am 22.09.2026 gemessen: Drei Bowlingkugeln aus `BowlingGame.3mf` sind je
  **ein** Fleck über 65 024 Dreiecke mit einer Kugel vom Rückstand 0,0, und
  sie zerfallen nach Krümmung in 662 Stücke, 659 davon Splitter. Ein Donut,
  ein Kegel, ein Ball — jede Grundform, die ein ganzes Modell ist, zerfällt
  wie eine Figur. **Nur der Fit trennt sie.** Ohne diesen Zusatz verlor auch
  eine Kugel auf einem Sockel mit 0,02 mm Rauschen ihre Kugel und ihren
  Zapfen.
* **Eine Abkürzung ist gemessen und ausgebaut: „auf der Haut nur den Zylinder
  fragen".** Kegel, Kugel und Ring verwirft der Filter dort ohnehin, und am
  Riesenfleck des Drachen (307 059 Dreiecke) kosten alle vier Fits 1 332 ms
  gegen 255 für den Zylinder allein — 0,6 s an der ganzen Erkennung. Sie
  setzt aber voraus, was sie sparen will: Dass ein Fleck die Haut ist und
  nicht selbst eine Grundform, weiß man erst nach dem Fit. Die Bowlingkugel
  hat sie gekostet.
* **Gelesen werden die Stücke von Gewicht, die Splitter nur ohne Haut.** So
  bleiben der tangential eingeblendete Zapfen und die Verrundung auf einer
  Figur Kandidaten, und ein konstruiertes Teil verliert nichts: Fällt das
  Urteil gegen die Haut, wird gelesen wie bisher. Was die Haut an Bohrungen
  und Flächen trägt, liegt an ihren Rändern und ist längst ein eigener Fleck.
* **Das Urteil kommt aus der Haut, nicht mehr nur aus der Zählung.** Ohne
  eingepasste Splitter zählt eine Freiform kaum Rundformen; `is_a_freeform`
  nimmt deshalb `Fitted.freeform_skin` vor die Zählung, und die Zählung
  trägt weiter die verrauschte Freiform ohne Haut (120 610 Flecken). Der
  Befund `perceive.freeform` kommt seit dem auch mit null weggelassenen
  Formen (`recognised_as_freeform`), und sein Satz behauptet keine Suche
  mehr, die nicht stattfand.
* **Wer eine der drei Zahlen anfasst, misst an beiden Seiten** — an der
  zerfallenden Fläche des Korpus `F:\3D Dateien` (170 Dateien, 464 Körper):
  Konstruiertes null bis 60 Prozent, mit den vier höchsten Fällen Pool-Rohr
  57 und 60, Wandhalter 55, Scraper-Griff 51; Figuren, Scans und erzeugte
  Netze 71 bis 94 (Katze 71, Zauberturm 75 bis 88, Schüssel 89, Drache 93,
  Retro-Maus 94). Der Scan-Körper der Tests liegt mit 63,6 Prozent **unter**
  der Schwelle und wird weiter ganz gelesen — sein Urteil kommt aus der
  Zählung, und der Test dazu patcht die Schwelle, weil er die Mechanik prüft
  und nicht die Zahl. Und an den Splittern selbst: Drache 27 554, Schüssel
  7 385, Scan-Körper 1 640 gegen Kapsel, Ellipsoid, Buchstabe und
  `generated_figure.stl` mit null bis einem.
* **Raue Tafeln machen einen Körper für sich zur Haut** (RM-235,
  25.09.2026): große Facetten, die an der Ebenheitsprüfung scheitern und
  deren Knicke gemischt und stark sind (`features._rough_facet_area`,
  `FREEFORM_ROUGH_SHARE`, `_MIX`, `_BEND`). Ein erzeugtes Netz trägt ebene
  Partien als verrauschte Tafel — weder Fläche noch Fleck —, und die
  Splitterregel sieht sie nicht: Das Puppenhausbett galt mit 34 Prozent
  Splittern nicht als Haut, und 96 893 Splitter wurden eingepasst. Zwei Wege
  sind gemessen und verworfen, und beide kosten Konstruiertes: **alle**
  verrauschten Facetten zu zählen (sanft gekrümmte CAD-Flächen scheitern an
  derselben Prüfung — Wedge-Lock 40, Siebhalter 35 Prozent) und die rauen
  Tafeln **zur Splittersumme** zu zählen (ein konstruiertes Teil mit
  56 Prozent Splittern kippte). Als eigener Auslöser trennt der raue Anteil
  breit: erzeugte Möbel, Figurenteile, Zaubersockel 50 bis 96 Prozent,
  danach nichts bis 30, Konstruiertes höchstens 23.

### Was an einer Bohrung hängt, bleibt

*Ursprüngliche Überschrift: „Was an einer Bohrung hängt, bleibt (10.09.2026)“*

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

## Ohne Wendel ist ein Gewinde eine Fläche, deren Gänge ineinanderlaufen

*Ursprüngliche Überschrift: „Ohne Wendel ist ein Gewinde eine Fläche, deren
Gänge ineinanderlaufen (25.09.2026, RM-219)“*

`features._without_thread_turns` verwirft Zylinder ohne Wendelbeleg nur, wenn
sie **an einem Teil** liegen, **dieselbe Materialseite** tragen und jeder
weitere Abschnitt in den Lauf **hineinläuft und mehr Neues bringt, als er mit
ihm teilt** (`_one_run`). Jede dieser Bedingungen folgt aus der Wendel selbst:
eine Fläche, eine Seite, eine stetig steigende Helix. Keine braucht eine neue
Zahl.

Vorher genügten ein Radius im Vertrag der Fitstreuung (acht Prozent) und ein
Fortschritt über der Schweißtoleranz. Gemessen über 208 Dateien und die
gedruckten Gewinde M3 bis M8 mit abgeschalteter Wendelsuche: Die Regel fand
kein belegtes Gewinde — die gedruckten bilden gar keinen Stapel, die Düse
`Pool-Fountain_Nozzle` fängt die Wendelsuche —, verwarf aber in 13 Dateien
echte Zylinder: die Flaschentaschen R 49 und Säulen R 22 des Flaschenhalters
(Wandstücke, die um Hundertstel versetzt beginnen), den Mantel R 15 der Düse,
die Bögen der Buchstaben am Screen-Cover, 30 von 45 Zylindern am Besenhalter.

**Wer die Regel anfasst, misst beide Seiten**: gedruckte Gewinde ohne
Wendelsuche (bilden sie einen Stapel, und wird er erkannt?) und den ganzen
Korpus je Stapel mit Radiusstreuung, Materialseite und Überlappung der
Abschnitte. Eine Rückfallregel, die im Korpus nie ihren Fall trifft, zeigt
dort nur ihre Fehlgriffe.

## Ein Bogen hat einen Radius und liegt auf seinem Kreis

*Ursprüngliche Überschrift: „Ein Bogen hat einen Radius und liegt auf seinem
Kreis (25.09.2026, RM-219)“*

`features._arcs_of_a_prism` trennt extrudierte Umrisse in ihre Bögen, und
`_exactly_an_arc` nimmt ein Stück nur als gezeichneten Bogen an. Drei Sätze,
alle am Korpus gemessen:

* **Jede glatte Kurve ist auf kurzer Strecke ein Kreis.** Ihr Abstand zum
  Kreis wächst mit der dritten Potenz der Länge; Splinestücke von vier bis
  acht Streifen treffen einen Kreis bis auf Hundertstel eines Mikrometers
  (Werkzeugbox, Eiffelturm) und bestehen `fit_cylinder`. Eine Kreisprüfung an
  kurzen Stücken beweist nichts über Konstruktionsabsicht — sie beweist erst
  etwas, wenn das Stück zusammen mit einem über das ganze Stück gleichen
  Radius und genauen Ecken kommt.
* **Die Trennschwelle liegt über dem Rauschen, nicht darin.** Der Radius je
  Dreieck streut an einem CAD-Prisma bis 2,4 Prozent; bei 2 Prozent Schwelle
  schnitt die Trennung echte Bögen an zufälligen Stellen und Splines in
  Stücke, die auf Kreise passten. `PRISM_ARC_JUMP` steht in der Lücke bis zum
  kleinsten gezeichneten Wechsel (6,3 Prozent).
* **Wo die Schätzung selbst Rauschen ist, wird nicht getrennt**
  (`PRISM_QUIET_SHARE`). Das kostet wenige echte Bögen in lauten Stücken; sie
  bleiben, was sie vorher waren.

Wer eine der drei Zahlen anfasst, misst beide Seiten: die Bögen des
Besenhalters und der anderen Konstruktionen (Radien mit wenigen
Nachkommastellen, genau rund) gegen Schriftzüge, Logos, Griffe und den
Eiffelturm, je Datei die neuen Verrundungen mit Kreisfehler und Radius.

**Ein geteilter Streifen leiht seinen Radius nur nach innen** (27.09.2026,
Durchsicht 0.5.1, R1). Nach *Kanten verfeinern* hat ein Dreieck mitten im
Mantelstreifen keinen eigenen Radius; `features._through_the_piece` gibt ihm
den kleinsten seiner Nähte. Zwei Bedingungen, beide am Korpus erzwungen: nur
Dreiecke **ganz im Inneren** der Facette, und nur wo die Nähte sich auf einen
Radius **einigen** (`PRISM_ARC_JUMP`). Ohne sie änderte die Regel ungeteilte
Körper — Fächer aus vier Dreiecken um einen Mittelpunkt lesen an ihren Nähten
R 1,4 und R 4,0 zugleich. Wer sie lockert, fährt den Korpus gegen den
Vorstand (`p42_korpus_erkennen.py`) und verlangt null geänderte Körper.

[Hinweis zur Verdichtung: `p42_korpus_erkennen.py` ist eine Sonde außerhalb
des Repositories; die Regel sagt deshalb nur „gegen den Vorstand“.]

## Ein Umriss mit wanderndem Radius ist eine gerundete Seite

*Ursprüngliche Überschrift: „Ein Umriss mit wanderndem Radius ist eine
gerundete Seite (26.09.2026, RM-243)“*

`features._wandering_outline` entscheidet über die Stücke eines Flecks
**zusammen**, nie über eines allein. Was das Stück selbst hergibt, trennt
nicht — gemessen an Screen-Cover, Flaschenhalter, Toilettenpapierhalter,
Eiffelturm, Bohrerhalter, Rack, Pegboards und Besenhalter, damit es niemand
ein zweites Mal misst:

* **Kreisfehler:** Buchstabenstücke liegen 0,8 bis 9,8 µm neben ihrem
  Kreis, die echten Flaschentaschen R 49 5,4 bis 7,3 µm, eine echte R 2 am
  Pegboard 1,7 µm. Beides ist die Float32-Rundung der STL.
* **Anteil springender Nähte** (`PRISM_QUIET_SHARE`): Der Flaschenhalter
  springt an 25 bis 65 Prozent seiner Nähte, so viel wie die Buchstaben.
* **Überstrichener Winkel:** Buchstabenstücke bis 43,5 Grad, eine echte R 2
  am Pegboard 34,2 Grad.
* **Ähnliche Kreise im selben Fleck:** fängt nur die Hälfte der Buchstaben
  (deren Stücke liegen zwischen Splittern), und derselbe Radius auf zwei
  Ecken ist keine Wanderung.
* **Ein anderes Stück liegt auf dem Kreis** (`_lies_on_the_cylinder`, über
  alle Stücke): Splitter aus zwei Dreiecken liegen auf jedem nahen Kreis.

Was trennt, sind zwei Sätze über die Nachbarschaft:

* **Ein bestätigter Kreis ist ein Bogen.** Das Rauschen zerteilt einen
  echten Bogen in Stücke, die alle auf seinem Kreis liegen; ein Spline trägt
  auf jedem Stück einen eigenen. Bestätigt heißt: ein zweites Stück von
  Gewicht mit derselben Seite, Radius und Achse wie in `_same_cylinder`,
  und eines liegt auf dem Kreis des anderen (`_lies_on_the_cylinder`) —
  oder ein gezeichneter Bogen (`_exactly_an_arc`). Ein bestätigter Kreis
  hält die Folge an. Ohne diesen Satz ist ein Korbbogen R 10 · R 16 · R 10
  verloren: Ein Stück über der Naht zweier Bögen passt auf einen
  Zwischenkreis (R 15,1) und täuscht eine steigende Folge vor. **Beide
  Richtungen zu verlangen ist zu streng:** Dann verlieren 20 von 72
  verrauschten Korbbögen echte Bögen. Der Preis der einen Richtung ist
  bekannt: Mit den zehn Mikrometern von `_lies_on_the_cylinder` liegt ein
  kurzes Stück auch auf einem Kreis mit vier Prozent anderem Radius, und so
  bestätigen sich am Scheitel einer verrauschten Ellipse und an zwei
  Buchstabenstücken R 11,2 Splinestücke gegenseitig — sie bleiben stehen.
* **Zwei Wechsel in dieselbe Richtung sind ein Verlauf.** Unbestätigte
  Kreise, die über Splitter und formlose Stücke aufeinanderfolgen und
  tangential ineinander übergehen, mit einem Radiusschritt unter
  `CURVATURE_JUMP`: Hat einer einen engeren und einen weiteren Nachbarn,
  wandert der Umriss. Eine Flaschentasche mit ihrer engeren Einlaufrundung
  hat einen Wechsel, ein Korbbogen zwei gegeneinander. **Eine Untergrenze für
  den Schritt trennt nicht:** Mit `PRISM_ARC_JUMP` (5 %) blieb der
  Rucksackhalter gleich, aber am Screen-Cover kamen 13 Buchstabenstücke
  zurück — Buchstaben wandern oft in Schritten von einem bis drei Prozent.

**Im wandernden Fleck bleiben die bestätigten und gezeichneten Kreise
stehen, der Rest fällt.** Am Schmierwerkzeug von Elegoo liegen im selben
Fleck wie die Splinestücke ein Halbrund R 4,2 aus dreizehn Stücken und zwei
Bögen R 6,75 über 81 Grad; mit allem, was nicht gezeichnet war, fielen sie
mit. Am Screen-Cover bleibt so der exakte R 22,975 aus dem Schriftzug des
Originals. **Und zurückgezogen wird nach der Zusammenlegung, nur was ganz
auf vorgemerkten Dreiecken liegt** (`_off_the_outline`): Vorher verlor der
Eiffelturm an zwei seiner vier Bögen R 24 über 172 Grad ein Bruchstück, das
im wandernden Nachbarfleck lag.

Welche Bedingung ein konstruierter Fall hält und welche der Korpus: In
`test_features.py` wird die Regel rot ohne Bestätigung, mit beidseitiger,
ohne gezeichnete Bögen als bestätigt, ohne das Schonen bestätigter Kreise,
mit einem Wechsel statt zweien und mit teilweisem Rückzug. Die
Tangentenprüfung hält der Toilettenpapierhalter (ohne sie fallen dort sechs
Verrundungen R 20,8 bis R 29,9). Die Grenze `CURVATURE_JUMP` für einen
Schritt und das Durchlaufen formloser Stücke hält kein eigener Fall; sie
stehen aus der Sache — ein Sprung über die Hälfte ist eine Kante der
Krümmung und keine Wanderung, und formlose Stücke liegen zwischen den
Kreisen einer verrauschten Ellipse. Wer eine der Bedingungen anfasst, fährt beide Seiten: die
Schriftzüge und Streben gegen Flaschentaschen, Besenhalter, Rack,
Pegboards, Bohrerhalter, Schmierwerkzeug, Toilettenpapierhalter und die
Korbbögen aus `test_features.py`.

## Eine Verengung ist keine Senkung

*Ursprüngliche Überschrift: „Eine Verengung ist keine Senkung (27.09.2026,
Durchsicht 0.5.1, R3)“*

Ein hohler Kegel ist eine **Verengung**, wenn sein weites Ende auf seiner
Bohrung sitzt und das enge die Mündung ist — die Haltelippe einer
Magnettasche (`features.narrowings_marked`, an beiden Kernen). Die Richtung
allein reicht nicht; vier Bedingungen, jede an einem Korpuskörper erzwungen,
an dem die schwächere Fassung falsch lag:

* **Das weite Ende mehrheitlich auf einer Bohrung** — ein eingepasster Kegel
  am Töpfchendeckel lag zur Hälfte an der Außenfläche.
* **Das enge Ende auf keiner Bohrung** — sonst ist es eine Stufe mit
  schrägem Absatz.
* **Das enge Ende offen**: Die dritte Ecke der Nachbardreiecke liegt weiter
  außen als ihre Naht. Eine Fase am Grund einer Tasche liegt innen (Düsenbox),
  eine Wulst läuft auf der engen Weite weiter (Siebring).
* **Eine Öffnung und keine Spitze**: weiter als die Vergleichstoleranz des
  Körpers — flache Kegelböden enden in einer Spitze (Murmelbahn).

Im Zweifel bleibt der Kegel, was er war. Wer eine Bedingung lockert, fährt
den Korpus und sieht sich jeden neu markierten Kegel an; bis heute ist keiner
darunter eine Lippe. Was eine Verengung nicht anbietet, steht bei ihren
Handlungen (`perceive.actions.cone_reason`, `not_offered_at`). Die
Einlaufprofile der Bohrungswerkzeuge tragen sie mit ihrem eigenen Profil
(`prepare_ops._narrowing_outline`, Durchsicht 0.5.1, rest-lippe): *Bohrung
ändern* in beiden Umfängen. Versetzen, Verdoppeln,
Vervielfachen und Entfernen der ganzen Kette gehen an beiden Kernen über die
eigenen Flächen der Tasche, samt Lippe (am exakten Körper
`prepare_ops._exact_chain_own_cavity`, dasselbe Flag über
`_narrows_outward`).

**Was die Handlungen hinterlassen, muss die Erkennung wieder als Verengung
lesen** — und sie liest nur eine offene Mündung an einer Wand aus ganzen
Facetten. Am Netz ließ der Neuschnitt den Ring der alten Mündung in der
Deckfläche stehen (0,125 mm um die neue, engere) und eine Ecke in der Mitte
jeder Wandkante am Boden; die Lippe hieß danach wieder „Senkung“, oder die
Tasche war eine gerundete Seite. Deshalb liegt das Ergebnis dort ohne Narben.
**Gekippt liest sie die Lippe nicht mehr als Verengung**: Auf der hohen Seite
schneidet die Fläche die Lippe weg (der Kegel ist dann ein Teilstück), auf der
tiefen führt die Öffnung als Schacht ihrer Weite bis zur Fläche, und ein
Zylinder, der mit der engen Weite weiterläuft, ist nach der dritten Bedingung
oben eine Stufe, keine Mündung. Am exakten Körper stand sie dann als Kegel
(„Senkung“) im Baum, am Netz mit Tasche und Schacht als gerundete Seite.
Nachgemessen mit dem gebauten Drehweg (Durchsicht 0.5.1, rest-muendung,
RM-262): Der exakte Kern liest Tasche, einen **angeschnittenen** Kegel ohne
Verengung und den Schacht als Zylinderstück — das Teilstück berührt die Tasche,
also keine Kette, und Versetzen sagt danach „kein eigener Körper“; das Netz
liest nur eine gerundete Seite, die Tasche ist keine Bohrung mehr (Lippe unter
der Knickgrenze, keine Krümmungssprünge zwischen 3,98 und 4,13 mm Radius).
Deshalb kippt *Merkmal drehen* eine Kette mit Verengung nicht
(`perceive.actions.narrowing_reason`); der Drehweg liegt als Patch bereit,
bis beide Erkennungen Tasche, Lippe und Schacht als Kette lesen. Dieselbe gekippte Lippe entsteht aber,
wenn die Magnettasche mit einer Richtung eingesetzt wird, die nicht senkrecht
auf der Fläche steht — ein offener Registerpunkt (Bericht rest-lippe), keine
Regel zum Lockern ohne Korpuslauf.

## Ein Hohlraum ohne Weg nach außen ist keine Bohrung

*Ursprüngliche Überschrift: „Ein Hohlraum ohne Weg nach außen ist keine
Bohrung (10.09.2026)“*

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
  und dieser Satz sagt welcher. **Und was nicht lesbar war, verschwindet
  auch nicht still**: Kann die native Differenz ein Schalenpaar nicht
  lesen, gibt die Erkennung keine Einschlüsse aus und nennt der Auswertung
  über `features.unreadable_void_shells` die Schalenzahl — der Befund dazu
  gehört in dieselbe Bauart wie `perceive.freeform`, nicht in ein
  Protokoll, das der Kunde nie sieht (21.09.2026).
* **Enthaltensein wird gezeigt, nicht gerechnet, wo es geht.** Das vierte
  Tor fragte je Schalenpaar eine native Differenz — am Quader mit acht
  Kammern 1,2 s für acht Antworten, die ein Strahl in 30 ms gibt. Der
  Strahl ist nur dann exakt, wenn die Schalen sich nicht kreuzen; das belegt
  ein Zertifikat über die Hüllquader der Dreiecke, und fehlt es, rechnet die
  Differenz wie zuvor. Ein Strahl, der eine Kante trifft, entscheidet
  nichts und nimmt die nächste Richtung — geraten wird an keiner Stelle.
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

## Eine Formtoleranz wird an fremden Netzen gemessen, nicht nur an eigenen

*Ursprüngliche Überschrift: „Eine Formtoleranz wird an fremden Netzen
gemessen, nicht nur an eigenen (15.09.2026)“*

[Hinweis zur Verdichtung: Der Abschnitt ist in der Regel auf drei
Überschriften verteilt — diese, „Das Panel bietet nur an, was die Operation
hält“ und „Viele gleiche Zellen sind ein Muster, und die Grenze zur Bohrung
ist eine Entscheidung“. Seine Aufzählungspunkte stehen hier unter der jeweils
neuen Überschrift.]

Der Fund: `radial_cylinder` prüfte die Ecken einer runden Wand gegen die
Schweißtoleranz — ein Millionstel der Diagonale, 0,2 µm an einem Körper von
170 mm. Solidons eigene Netze aus double-Rechnung halten das; der Siebhalter
eines Kunden nicht: Sein Kragen Ø 57,00 lag 0,3 µm neben dem Kreis (Float32
der STL), sein Nutboden Ø 54,36 3,9 µm. Beide Zylinder fielen durch, und im
Objektbaum stand „Verrundung R27,18" mit vier grauen Zeilen, die eine Kante
nannten, die es nicht gibt. Und im selben Modell kam die Bohrung eines
Bajonettrings mit drei Nasen als „Langloch Ø 57,39 auf 57,39 mm" heraus —
ein Stadion mit Weg 0,00005 mm, angenommen, weil der Weg nur größer als
`EPS_GEOM` sein musste.

* **Schweißtoleranz und Formtoleranz sind zwei Fragen.** Die erste sagt, ob
  zwei Ecken derselbe Ort sind; die zweite, ob Ecken auf einer Form liegen.
  Eine Formfrage bekommt eine Zahl, die ein importiertes Netz einhalten kann
  (`features.ROUND_WALL_TOLERANCE`, 10 µm — ein Fünftel von
  `units.MAX_FACET_SAG`), und die an den echten Dateien aus dem
  Downloads-Korpus gemessen ist, nicht nur am eigenen.
* **Ein Fit behauptet nichts unter seiner eigenen Auflösung.** Ein Stadion
  mit einem Weg unter `STADIUM_TOLERANCE · Radius` ist von einem Kreis nicht
  zu unterscheiden und wird keines (`StadiumFit.good`). Was der Zylinderfit
  ablehnt, darf ein anderer Fit nicht mit einer weicheren Frage annehmen.
* **Eine runde Wand heißt runde Wand.** Ein Zylinderausschnitt über 180 Grad
  (`radial`) gehört zu keiner Kante; Objektbaum und Steckbrief sagen „Runde
  Wand", das Panel begründet die grauen Zeilen mit
  `actions.ROUND_WALL_HAS_NO_PLACE` statt mit der Kante. Geht die Wand
  tangential in ihre Nachbarn über (`tangent`,
  `features.tangent_walls`), ist auch der Radius nicht für sich
  zu ändern — Panel und Operation sagen es mit demselben Satz
  (`actions.WALL_BLENDS_INTO_ITS_NEIGHBOURS`).

* **Ein Kegel unter dem vollen Umlauf ist keine Senkung und keine
  Verjüngung.** Er gehört zum Langloch, an dessen Mantel er grenzt
  (Mündungsfase, geht darin auf), oder zur Bohrung daneben (Senkung einer
  angeschnittenen Bohrung, bleibt); sonst heißt er Kegelfläche (`partial`)
  und trägt keine Körperhandlung — Panel und `_movable_feature` sagen es mit
  `actions.CONE_PIECE_HAS_NO_BODY` (`features._partial_cones_folded`). Er
  bleibt im Bestand, weil die Freiformprobe an den erkannten Formen zählt.
  126 „Senkungen" an 33 Langlöchern eines Rahmens waren der Anlass.
* **Ein Fleck auf der vorhandenen Wand gehört zu ihr.** Zwei Zylinderflecken
  werden zusammengeführt, wenn der gemeinsame Fit nicht schlechter streut
  als seine Teile — oder wenn der neue Fleck im Vertrag von
  `CYLINDER_SPREAD` auf dem schon eingepassten Zylinder liegt
  (`features._lies_on_the_cylinder`). Sonst bleibt der vierte Bogen einer
  Bohrung draußen, weil ein Fit über mehr Punkte immer etwas mehr streut.

* **Die Langlochsuche rechnet je Bogen, nicht je Paar.** Flutung, Flanken
  und Stadionfit hängen an Bogen und Achse (`slots._Reach`), und die Maske
  einer Achse ist ihr Schlüssel, nicht die gerundete Achse allein. Ein
  Stadionfit über den ganzen Mantel darf die Breite nicht unter das Maß der
  Bögen drücken (`STADIUM_TOLERANCE`) — sonst stand ein „Langloch 0,01 auf
  97 mm" im Baum.

## Das Panel bietet nur an, was die Operation hält

* **Das Panel bietet an einer Verrundung nur an, was die Operation hält.**
  `actions.fillet_blocked` stellt die Frage der Bearbeitung vorher: Grenzt
  der Bogen quer zu seiner Achse nicht an genau zwei ebene Flächen
  (`features.replaces_an_edge`, von `geom/edges.py` in `sharp_corner`
  gelesen) — oder treffen die zwei Ebenen den Bogen schräg statt tangential
  —, stehen *Entfernen* und *Radius ändern* grau mit
  `edges.NOT_BETWEEN_TWO_PLANES`, und `sharp_corner` sagt dasselbe. Zwei
  Ebenen, die einen Bogen nur schneiden, ergaben an einem Modellgleis eine
  Kante, die es nicht gibt, und ein stilles Falschergebnis. Vorher versprach das Panel an 50 von 52
  Bögen aus 34 Netzmodellen, was die Operation nach dem Klick ablehnte
  (15.09.2026). Der Name bleibt Verrundung.
* **Das Panel bietet nur an, wofür die Operation einen Körper baut.**
  `actions.no_own_body` fragt vorher, was `prepare_ops._tool_for` fragt: Eine
  Bohrung oder Senkung mit berührtem fremdem Rand ohne Kette trägt
  `NO_OWN_BODY`, ein Kegel oder eine Kuppel ohne Körper aus den Flächen
  (`has_own_body`) trägt `NO_BODY_FROM_FACES` — an Versetzen, Verdoppeln,
  Drehen, Entfernen und Ändern. Kundentexte kurz: zwei Sätze, der Rückweg im
  zweiten.

* **Ein Körper, der nach einer Merkmalsänderung zerfällt, sagt es.** Die
  Auswertung zählt die Teile vor und nach jeder Operation mit
  `touches_features` und meldet mehr Teile als Warnung
  (`feature.body_split`, `evaluate._split_findings`) — der Rückweg steht im
  Satz. Gemessen: *Merkmal entfernen* an einem Zapfen, der der Körper selbst
  war, ließ 50 Teile zurück, und der Bericht schwieg. Ein gewollt loses Teil
  zählt nicht (`leaves_separate_parts`, `bausteine.md`); das Urteil steht
  einmal in `geom.boolean.body_split`. Meldet der Schritt den Zerfall selbst,
  schweigt die Auswertung: Am Würfel 20 mm mit einem Langloch 100 mm quer
  durch standen bis zum 29.09.2026 zwei Sätze über denselben Zerfall im
  Bericht, der der Bohrung (`bore.splits_the_body`, mit Grund und *Eingabe
  korrigieren*) und darunter dieser.
* **Ein konvexes Werkzeug aus den Flächen wurzelt in seiner Grundfläche und
  spart die Hohlräume aus, die durch es laufen** (`prepare_ops._rooted`,
  `_without_cavities`, gebündelt in `_placing_tool`). Kegel und Kuppel
  kommen aus `_feature_body`, ihr Deckel lag genau in der Grundfläche — die
  Vereinigung ließ zwei Schalen, und eine Bohrung durch den Kegel war danach
  ein Sackloch. Der Sockel gilt nur dem Setzen; das Abtragen an der alten
  Stelle bekommt ihn nicht. Und das Abtragwerkzeug eines Zapfens umschreibt
  sein Vieleck wie der Stopfen einer Bohrung (`_closed_at`), sonst bleiben
  Splitter zwischen den Facetten (48 Reste von 0,003 mm³ an einer Nabe).

## Viele gleiche Zellen sind ein Muster, und die Grenze zur Bohrung ist eine Entscheidung

* **Viele gleiche Zellen sind ein Muster, und die Grenze zur Bohrung ist
  eine Entscheidung** (`perceive/patterns.py`, RM-207): Ein Gitter ab neun
  deckungsgleichen Zellen (Streifen ab sechs), eine Streuung gleich tiefer
  Zellen ab vierundzwanzig (Rauschen ab vierzig — ein Schild mit zwei
  Dutzend erhabenen Buchstaben sah in der Korpusprobe genauso aus). Runde
  Zellen werden nur als Noppe gefaltet, wenn sie blind und höchstens doppelt
  so tief wie breit sind, erst ab zwanzig und nur im Wabengitter, in dem
  `apply_texture` Noppen setzt: Ein Lochblech mit 81 durchgehenden Bohrungen
  bleibt 81 Bohrungen, zwölf Magnettaschen bleiben Taschen, 25 im
  Quadratraster auch — an allen gelten die Bohrungshandlungen, und die nähme
  ein Muster ihnen weg. Sechseckige Löcher haben keine und werden auch
  durchgehend zum Muster; in einem Gitter, das Solidon so nicht zeichnet,
  heißen sie `other` und lassen sich entfernen, nicht neu setzen. Jeder Stil
  wird nur in seinem Gitter neu gezeichnet (`_GENERATOR_LATTICE`). Gefaltet
  wird nach allen Einzelformen und **vor** dem
  Freiformfilter, sonst zählen tausend Zellwände als Rundformen-Anteil. Was
  ein Muster ausmacht, steht am Netz: Mündung, Tiefe, Seite, Teilung — kein
  Verweis auf einen Trägernamen, der beim Umbenennen altert. Der Träger darf
  ein Zylinder sein: gemessen wird dann in seiner Abwicklung, und ein Muster
  trägt Achse und Durchmesser statt nur einer Normalen. Wer einen Körper auf
  den Mantel legt — den Stopfen, der eine Zelle füllt —, legt ihn auf dessen
  Facetten, nicht auf den Kreis: Bündig mit dem Kreis stand er zwischen zwei
  Ecken über der Facette, und die Stufe machte aus dem Mantel hundert
  Flächen. Ein Werkzeug, das nur die Ecken biegt, hat seinen Boden in der
  Mitte um die Sehnenabweichung tiefer als am Rand — erst teilen, dann
  biegen. **Geteilt wird konform** (`patterns._cut_at`), nicht mit
  `split_by_plane` und einer Vereinigung danach: Eine Facettengrenze geht
  bei jeder Zelle, die mittig auf einer Kante des Vielecks sitzt, genau durch
  eine Ecke des verfeinerten Stopfens, und dort ließ die Vereinigung Finnen
  stehen, aus denen `manifold3d` einen Keil verwarf (vier Hohlräume nach dem
  Entfernen von 48 Taschen, 23.09.2026). Zugedeckt hatte das die Rundung der
  Facettenwinkel auf sechs Stellen — wer eine Auskunft genauer macht, sucht
  die Verbraucher, die an ihrem Rauschen hingen. Ein vertiefter Stopfen endet
  an den Stirnflächen des Stifts (`Frame.span`), und die Aufweitung zum Boden
  einer Tasche mit parallelen Wänden gilt nur dem Umfang. Stopfen und neu
  gezeichnetes Muster teilen den Mündungssaum (`_mouth_with_margin`): Ein
  bereits gefüllter Streifen gehört zum neuen Feld. Am Stirnrand reicht nur
  das Schneidwerkzeug über die gemessene Stirnfläche hinaus; seine Verlängerung
  bezieht sich auf diese Ebene, nicht auf den angenäherten Umrisspunkt.

* **Unter gleichen Zellen wählt eine feste Weltrichtung** (28.09.2026, RM-275;
  `patterns.SEAM_DIRECTION`). Um einen Zylinder sind alle Zellen gleich; am
  Gewürzdeckel (24 Mulden, jede ein Randstück) lag die Naht der Abwicklung der
  ersten Ebenenachse gegenüber und genau auf einer Mulde, und welcher Seite sie
  zufiel, entschied das Vorzeichen einer Summe nahe null: Schon beim Laden
  stand die Mitte bei einem Teil der Deckel eine halbe Teilung links, bei den
  anderen rechts, und nach *Merkmal verschieben* weit weg sprang sie an vier
  von zwölf. Aus ganzen Zellen war die Naht die größte von lauter gleich großen
  Lücken — ebenfalls Rundung. Jede Wahl auf einem Kreis kippt irgendwo; die
  Richtung (1, φ, φ²) legt die Kippe auf Winkel, die kein konstruiertes Muster
  trifft (58,28° um Z und X, 69,09° um Y), statt auf die Weltachsen, an denen
  Rändel konstruiert werden. Gleich groß heißt bis auf `SAME_MEASURE`; ein
  Teilfeld behält seine eine große Lücke. Der Anker (nächste Zelle zur Mitte)
  hat bei gerader Zellenzahl zwei gleich nahe; auch dort entscheidet die
  Richtung.
