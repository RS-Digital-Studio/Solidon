# Begründungen zu `.claude/rules/dateiformat.md`

> Stand 27.09.2026. Aus der Regel verschoben, als sie auf das Einzuhaltende
> verdichtet wurde. Die Regel steht dort; hier steht, warum — mit den
> Messwerten und Anlässen ihres Tages.

## Migration ist Pflicht, nicht Kür

**Umrechnen statt melden** (30.09.2026, Format 39). Der Winkel eines
Langlochs zählt seitdem gegen `prepare.slot_frame`; bis Format 38 meinte
derselbe Wert an einer Achse im Messrauschen eine andere Richtung — an der
vernetzten Teppichecke dasselbe Langloch -168,5°, 132,0° oder 91,8° je nach
Feinheit. Ein Hinweis beim Öffnen hätte dem Kunden gesagt, dass sein Langloch
jetzt anders liegt, und ihn die alte Richtung suchen lassen, die er schon
gedruckt hat. Der alte Rahmen ist aus derselben Achse berechenbar, also trifft
die Umrechnung sie genau. Bei *Bohrung setzen* steht die Normale im Schritt,
die Migration rechnet sofort um; bei *Zum Langloch ziehen* gibt erst die
Erkennung die Achse, darum trägt der Schritt `measured_frame`, und die Op legt
den umgerechneten Winkel über `answered` zurück — wie die freie Stelle eines
weiteren Modells (Format 38). Belegt an `slot_angle_frame_v38.p3d`, geschrieben
vom Stand davor (`test_project.test_v38_a_slot_keeps_the_world_direction_it_was_cut_with`).

## Was nicht in die Datei gehört

Zu den mitreisenden Druckern und Materialien: Passungen aus *Teilen* und
*Deckel* „folgen dem Material ihrer Körper statt dem Projektmaterial des
Augenblicks".

Zum ausgeschalteten Schritt: „Die Stufe 31 → 32 schreibt nichts um — eine
ältere Datei hat keinen ausgeschalteten Schritt".

> **Gleich heißt inhaltsgleich, nicht bytegleich** (RM-106). Zwei Plattformen
> schreiben dieselbe Projektdatei mit anderen Deflate-Bytes (zlib gegen
> zlib-ng); der ZIP-Kopf nennt kein schreibendes System (`CONTAINER_SYSTEM`).

Wie sich „Dokument oder Einstellung" am Exportordner entschied:

> **Der Exportordner ist der Fall, an dem sich das entscheidet** (RM-141,
> Version 23). §29 sagt „Ordner, Format und Übergabeart werden je Projekt
> gemerkt" — je Projekt, nicht in der Projektdatei. Format und Namensschema
> stehen seither in `Document.export_format` und `Document.export_scheme`,
> denn sie gehören zum Teil: Ein Gehäuse für den eigenen Slicer bleibt 3MF,
> ein Modell für einen Dienstleister bleibt STL. Der **Ordner** steht in
> `UiSettings.export_dirs`, geschlüsselt nach Projektpfad — derselbe Schnitt
> wie beim Slicer-Pfad neben der Übergabeart: Der zweite Rechner hat einen
> anderen Ordner, aber dieselbe Gewohnheit.

Und an der Sichtflächensperre:

> **Und die Sichtflächensperre ist der Fall, an dem sich „Dokument oder
> Ansicht" entscheidet** (RM-080, Version 24). „Diese Fläche soll schön
> bleiben" ist eine Aussage über das Teil, nicht über die Sitzung: Als
> Ansichtszustand war die Markierung nach dem Schließen weg, und der Kunde
> erfuhr es an dem Schnitt, der durch die Fläche ging, die er schützen
> wollte.

> Kein Verlaufsschritt, wie bei den Druckeinstellungen: Es entsteht keine
> Geometrie, der Umschalter ist sein eigener Rückweg. Ein Rezept trägt keine
> Sperren (`part_file` weist sie ab) — sie nennen Körper, die es im
> eingelesenen Baustein unter diesem Namen nicht gibt.

## Transaktionstitel

Warum zusammengesetzte Titel wörtlich bleiben: „eine Message-ID kennt keine
Platzhalter."

## Ein Platzhalterwert kann selbst übersetzbar sein

Das Beispiel: „`perceive.actions._no_way` baut
`_("Dafür ist „{title}“ da.", title=<Titel einer Operation>)`, und der Titel
kommt als `TranslatableText` aus dem Register."

> Was ein rohes `dict(...)` kostete, ist am 04.09.2026 gemessen worden: Der
> eingebettete Text stand unverändert im Bericht, `json.dumps` in
> `project.save` endete mit
> `Object of type TranslatableText is not JSON serializable`, und weil das
> kein `AppError` ist, verlor der Kunde das
> Speichern ohne Handlungsvorschlag (Regel 17). Im Plattencache wäre dieselbe
> Sache still gewesen — der Eintrag fiele durch den `except`-Zweig, und jedes
> Projekt rechnete neu.

> Die beiden kürzeren Wege geben je etwas auf: `str(value)` friert die
> Sprache des Speicherzeitpunkts ein, `source_text(value)` legt einem
> französischen Kunden einen deutschen Operationstitel mitten in den Satz.
> Zahlen bleiben dabei unangetastet — `{free:.1f}` steht so in den Katalogen,
> und ein Wert, der als Zeichenkette zurückkäme, machte aus der Formatangabe
> einen Fehler.

## Eingangsstufe

Warum STL-Verschweißen kein Befund ist:

> Eine STL speichert jedes Dreieck mit eigenen Ecken; sie zu verschweißen ist
> Lesen, keine Reparatur — und „Doppelte Punkte wurden verschweißt." stand
> als erste Zeile jedes sauberen STL-Imports im Prüfbericht, ohne Handlung
> (Bedienweg-Durchsicht 14.09.2026). […] Bei OBJ, PLY und 3MF bleibt der
> Befund: Dort sind doppelte Punkte eine Eigenschaft der Datei.

Zur doppelten Schale:

> Trägt eine OBJ, PLY oder 3MF ihre Schale zweimal mit eigenen Ecken, kam sie
> vorher als zwei deckungsgleiche Teile mit doppeltem Volumen an (gegenläufig
> geschrieben mit dem Volumen null). Seit der Durchsicht 0.5.0 räumt das
> Einlesen sie ab wie jedes andere doppelte Dreieck — unter
> `remove_degenerate`, mit Befund, und nur, wenn das Netz danach geschlossen
> ist; berühren sich zwei Körper an einer Fläche, bleiben sie zwei.

Das Verschweißen im vollen Wortlaut, mit dem Grund für die eine Funktion:

> **Verschweißen schließt Ränder, es verbindet keine Blätter** (RM-239).
> Import und Reparatur fragen dieselbe Funktion (`geom.repair.weld`): Eine
> Suppe wird auf `EPS_GEOM` gelesen, danach kommt nur zusammen, was an einem
> offenen oder verzweigten Rand liegt oder als Kante unter `EPS_GEOM`
> zusammenfällt, jede Punktgruppe wird nach dem Flächenblatt getrennt, zu dem
> ihre Kopien gehören, und übernommen wird nur, was das Netz nicht schlechter
> macht. Was darüber liegt und heil ist, ist Form: eine Fase von 0,016 µm
> zwischen zwei Flächen bleibt, auch wenn sie schmaler ist als die
> Schweißtoleranz. Wer ein eingelesenes oder beschädigtes Netz an einer
> weiteren Stelle verschweißt, nimmt dieselbe Funktion — zwei Regeln für
> dieselbe Frage entschieden über dasselbe Netz verschieden (der Import nahm
> zurück, was einen dichten Eingang aufriss, die Reparatur, was die Summe
> offener und verzweigter Kanten erhöhte). `Trimesh.merge_vertices` bleibt,
> wo ein Erzeuger seine eigenen Stücke zusammenfügt (Drehkörper, Werkzeuge),
> und in `boolean._tidied`, das die Ausgabe des Kerns über alles
> verschweißt, wie ein Slicer es täte, und das Ergebnis selbst prüft.

Warum beim Import geschlossen wird, und was es am Korpus ergab:

> **Und sie schließt, was offen ist** (Entscheidung Robert, 22.09.2026: „am
> besten beim Import", „alles bei der Reparatur beheben"). Bis dahin meldete
> der Import „Das Modell ist nicht geschlossen. Reparieren schließt die
> offenen Stellen." — ein Hinweis auf einen Knopf, den der Kunde erst finden
> musste, und ein Modell, das bis dahin nicht druckbar war. […] Gemessen am
> Korpus `F:\3D Dateien` (171 Dateien, 484 Körper): 366 kamen dicht herein,
> **118 offene gehen geschlossen heraus, keiner bleibt offen**, 108 s für
> alle zusammen.

Zur Warnung bei großen Öffnungen: „Dort ist eine Fläche entstanden, die im
Modell nicht war. Am Korpus traf das keinen einzigen Körper; an
`broken_open.stl` trifft es zu, und dafür steht der Test." Zum Netzcache: „Sie
liegt im Cache des Netzes, den der Hauptthread abliest; ein `None` an dieser
Stelle wurde dort zu `False`, und ein geschlossener Körper meldete sich als
offen."

Die Grenzen des Schließens entschied Robert am 24.09.2026 und nach seiner
Vorgabe vom 25.09.2026 („das Beste für den Kunden, den Druck und das
Modell"), zum Teil als RM-241. Die Gründe im Wortlaut:

> — eine offene Fläche druckt erst mit einer Wand. Vorher schaltete der Knopf
> `mend` ganz ab. Der Schalter gilt jedem Körper der Datei; eine Baugruppe
> mit mehreren großen Öffnungen ist selten, und ein Schalter je Körper wäre
> im Dialog eine Liste.

> Ein offenes Stück unter `SMALL_COMPONENT_SHARE` des größten Teils umschließt
> nichts, druckt nicht und ließ jede Boolesche Operation daran scheitern.

Ineinandersteckende Teile (Bedienweg A5): „Am Korpus `F:\3D Dateien`: 16 von
56 mehrteiligen Körpern, 3,9 s für alle 485 Körper."

Was ausblieb, ist keine Zeile (Bedienweg A4): „geschehen ist nichts, und der
Kunde kann nichts tun (am Korpus vor RM-239 41 und 23 von 485 Körpern)."

Zu GLB und glTF:

> TripoSG schreibt Y-oben wie jede glTF-Datei, roh gelesen lag jeder erzeugte
> Körper auf dem Rücken (RM-086, gemessen an fünf erzeugten Netzen). Die
> Achsen folgen dem Format, die Meter nicht — die Größe setzt der eigene
> Schritt `fit_to_size`.

> glTF schreibt Meter vor, aber die Datei sagt es nicht selbst; ein Generator
> liefert den Einheitswürfel.

Zum Weg aus dem Netz: „Zwei Importwege wären zwei Stellen, an denen die
Einheitenfrage vergessen werden kann."

Warum die Antwort auf „ist es dicht“ nach dem Schließen neu gesetzt wird:
Ein `None` im Netzcache las der Hauptthread als `False`, und ein
geschlossener Körper meldete sich offen.

Eine Fläche ohne Dicke bleibt offen, weil geschlossen eine zweite Fläche
deckungsgleich darauf läge.

## Formate

Zu 3MF: „Wer es als ein Mesh liest, verliert genau das."

STEP als Baugruppe kam mit P7.4. Die Gründe der fünf Sätze:

- Ein Schritt ohne `bodies` liest einen Körper, „damit ein altes Projekt
  dasselbe Teil ergibt".
- Zu den Farben: „Die eine Farbe, in der ein CAD-Programm alles zeigt, hat
  niemand als Filament gewählt."
- Zur Auswahl: „— sonst träfe er still einen anderen Körper."

Warum ein 3MF-Modell nie am Stück geparst wird:

> `ET.fromstring` über 195 MB Modell-XML hielt den GIL 4 bis 5 s, und der
> Speicherbereiniger lief danach über 3,5 Millionen `Element`-Objekte — das
> Fenster stand, obwohl der Import im Arbeiter lief (Durchsicht 0.5.1,
> FENSTER-03).

Warum die Blöcke beim Parsen so klein sind: So lange, wie ein Stück den GIL
hält, wartet jeder Griff des Hauptthreads. `findall(".//…")` über das Modell
lief in C durch alle Ecken und Dreiecke.

## Was welcher Slicer bekommt

Zur Stützdichte (RM-475): PrusaSlicer und die Orca-Familie rechnen
`support_density = Linienabstand / (Lücke + Linienabstand)`
(`SupportParameters`); Solidon schrieb die Teilung Bahnbreite / Dichte als
Lücke, und gedruckt wurden 15 % als 12 %, 50 % als 31 %. Eine Lücke null ist
die dichteste Stütze (am Pilz 28,9 cm³ statt 5,8 cm³). Die Umkehrung lautet
`Lücke = s / Dichte − s`, mit `s = Breite − Höhe · (1 − π/4)` der
Stützbahn. Bahnbreite statt `s` im Zähler würde weiter zu wenig Stütze
ergeben, auch wenn Schreiben und Rücklesen übereinstimmen.

Die Rücklesung nimmt die Stützbahnbreite des Herstellerprofils. Bei
automatischer Breite gilt zuerst die allgemeine Bahnbreite, danach die
Düse; Prozentwerte beziehen sich bei Orca auf die Düse, bei Prusa auf die
Schichthöhe. Eine ausdrücklich geschriebene Dichte schreibt auch die zur
Umrechnung verwendete Stützbahnbreite. Ändern sich Schichthöhe oder
Bahnbreite, wird der Abstand mitgerechnet, damit die gewählte Dichte bleibt.

Das Prozentfeld beginnt bei 1 %, dem kleinsten positiven ganzzahligen
Eingabewert; das ist keine technische Untergrenze des Slicers. Ohne Stützen
wählt der Nutzer „Keine“. Gespeicherte Nullwerte bleiben beim Öffnen
erhalten. Eine aktive Übergabe mit 0 % hält mit einem Hinweis auf die
Druckeinstellungen an, weil eine Stützdichte von 0 % keinen endlichen
Linienabstand ergibt.

Die Messung zur Stützsperre:

> **Jede Familie liest nur ihre Schreibweise, und die andere druckt sie als
> Kunststoff**: als Bereich der ElegooSlicer (+22,8 g an der Waschschüssel),
> als Komponente PrusaSlicer (+38,8 g), gemessen am 26.09.2026. Geprüft wird
> eine Sperre deshalb an der **Modellbahn** mit und ohne sie — nicht an der
> Stütze: Eine als Kunststoff gedruckte Sperre verdrängt die Stütze auch.

> **CuraEngine bekommt sie als eigenes Netz** mit `anti_overhang_mesh=true`
> (`slicer_keys.takes_mesh_settings`) — gemessen im Prüfbericht Cura
> (Abschnitt 1.5): 18 476 Stützbewegungen wurden 0, die Modellbahn blieb bis
> auf zwei Bewegungen gleich.

Warum Cura kein 3MF bekommt:

> `CuraEngine` liest kein 3MF (die 3MF-Seite sitzt in Curas Fenster, nicht in
> der Rechenmaschine dahinter), und ein 3MF endete dort in „Der Slicer hat
> keine Druckdatei geschrieben", ohne dass irgendwo stand, warum. […] Namen
> und Materialslots liest es ohnehin nicht, und die Einstellungen kommen bei
> ihm über die Kommandozeile.

Das Plattenraster, seine Messung und die frühere, widerlegte Annahme:

> (`plate_origin`, `SLICER_PLATE_GAP`; aus `PartPlate.cpp` gelesen und am
> installierten ElegooSlicer gemessen: fünf Platten auf 256 mm liegen bei
> x = 128, 435,2, 742,4 und in der zweiten Zeile bei y = −179,2). Bis zum
> 11.09.2026 stand hier „eine Reihe, ein Achtel", nachgemessen an
> `BowlingGame.3mf` — die Messung nahm an, zwei Objekte stünden plattenlokal
> an derselben Stelle, und bei vier Platten lagen die Buchstaben der dritten
> und vierten im Slicer neben allem. Genau diese Datei schreibt
> `write_assembly` ohne `plate`; die Blöcke zählen durch (Rang, nicht
> Solidons Plattennummer), denn aus ihrer Zahl rechnet der Slicer die
> Spalten.

Warum alle Platten in eine Datei gehen: „Vier Starts des ElegooSlicers auf
einmal stritten um dieselbe Filamentbibliothek, bis einer mit „remove_all:
Zugriff verweigert" abbrach (Robert, 11.09.2026)."

Die Bettkoordinaten und der Fehler davor:

> Solidon rechnet um den Ursprung, der Drucker misst von der Ecke — und der
> Slicer bekommt die Welt des Druckers […]. Bis zum 05.09.2026 bekamen Cura
> und PrusaSlicer stattdessen Solidons Welt erklärt
> (`machine_center_is_zero`, eine Bettform von `-128` bis `128`) und die Teile
> unverschoben; der Slicer war mit sich im Reinen und schrieb Bahnen bei
> `-13,6`, die es auf einem MK4S oder Centauri nicht gibt, während die eigene
> Gegenprobe gegen denselben erfundenen Ursprung maß (Gesamtreview, CORE-17,
> mit PrusaSlicer 2.9.6 gemessen). Die ältere Messung „um den halben Bauraum
> verschoben" — Würfel bei -10…10, im G-Code bei 118…138 — war die Bettmitte;
> PrusaSlicers „All objects are outside of the print volume" kam aus dem
> Widerspruch zwischen verschobenen Teilen und zentriert erklärtem Bett.

Warum der Nullpunkt dem Drucker gehört (RM-424, 02.10.2026): Rund 45
Maschinenprofile der Orca-Familie und mehrere Prusa-Bündel (BIBO) haben ihr
Bett um den Ursprung oder versetzt dazu; die Erhebung zentrierte die Kontur
und warf den Ursprung weg, die Übergabe verschob dann immer um das halbe
Bett. Gemessen: Ein Würfel aus der Bettmitte lag am DeltaMaker 2 (OrcaSlicer,
ElegooSlicer) bei (138 / 120) in der 3MF, der Slicer ordnete selbst neu an
und druckte ihn bei (0 / 60); PrusaSlicer lehnte den BIBO2 mit „außerhalb des
Bauraums“ ab; am Creality CR-6 SE (Bambu Studio, Bett ab x = 5) lag er 5 mm
neben der Mitte. Mit `bed_origin` liegen alle mittig, CuraEngine ohne
Druckerdefinition über `mesh_position_*` auch am Dremel 3D45 (-15 / 0).

Warum ein Programm ohne Familie STL um den Ursprung bekommt (`other`, seit
RM-071): „Es ist das eine Format, das jeder Slicer liest — auch der
rudimentäre Hersteller-Slicer eines Resin-Druckers —, und einen Bauraum, zu
dessen Ecke sich verschieben ließe, kennt Solidon dort nicht."

Warum ein exakter Körper neu vernetzt hinausgeht: „die Datei geht in den
Slicer, und an 50-µm-Pixeln ist eine Facette von fünf Hundertsteln eine
Stufe."

## Auf dem Herstellerprofil wird nur die Abweichung geschrieben

Der Anlass der Entscheidung (Robert, 27.09.2026):

> Solidon schrieb bis dahin jeden Tabellenwert über das Profil des Herstellers
> — am Centauri Carbon 2 45 Prozess- und 22 Filamentwerte, darunter Gitter
> statt Elegoos Baum, kein Auto-Brim, eine erste Schicht von 0,25/0,449 mm
> und die Faustregel von 45 Grad. Roberts Minigolf-Druck bekam davon einen
> Stützfuß in Schicht 1 (46,4 m Stütze; mit Elegoos Satz 0 m).

Zur Druckplatte: Ohne `curr_bed_type` nimmt die Konsole „Cool Plate" —
„gemessen mit 35 °C Bett für PLA"; Elegoos `default_bed_type = 4` ist „belegt
an 34 gespeicherten Projekten".

Zum mitbedienten Schlüssel: „Der Vorschlag „Innenwand 142" hob an der Kobra 2
die Lückenfüllung von 100 auf 142 mm/s."

Zum bremsenden Vorschlag: „„Erste Schicht 50 mm/s" an schmalen Stegen legt die
Füllung langsamer und lässt Wände, die der Hersteller mit 40 legt, bei 40."

Die Kette des Prusa-Bündels war Stufe C der Übergabe auf dem Herstellerprofil.
Warum der gelesene Bestand gehalten wird: „ungespeichert stand der
Druckdialog je Profilwahl fünf Sekunden."

Der Stand der Messungen zur Abnahme steht in `ROADMAP.md` unter RM-281.

Warum ein Objektwert nie die ganze Einstellungsgruppe trägt: Sonst schriebe
er Solidons Tabellenwerte über die des Herstellers (Review der
Gesamtprüfung 0.5.1, B1).

Warum der Rat je Teil bis zum Fixpunkt fragt: Die Keil-Regel verlangt
Arachne, und beide Pfade gehen je Teil. Der Split setzte beide auf Elegoos
`classic` zurück, der Rat je Teil fragte einmal dort, und kein Teil bekam
„Außenwand zuerst“ — `_unserved` legte es an alle, auch an eine Schüssel mit
49° nach innen kippender Wand, die Stützen brauchte (Fehldruck am Centauri
Carbon 2, 29.09.2026). Nur übernommene Werte gehen in die Kette, sonst löste
ein nicht übernommener Vorschlag eine Folgeregel aus.

Warum Export und Druckdialog den Rat je Teil an einer Stelle fragen: Sonst
nennt die Zeile im Dialog ein Teil, das die Datei nicht bekommt.

Warum der Rat je Teil auch ohne die plattenweiten Übernahmen gefragt wird:
Trug die Grundlage sie schon, schwieg er an der Stange, und bei Cura standen
Innenwandtempo 60 und Grundbeschleunigung 2000 der Stange auch am Block,
ohne Befund (RM-430, Review 02.10.2026).

Warum der gemessene Überhangwinkel bei anderer Schichthöhe oder Bahnbreite
zurückfällt: Sonst stützten Analyse und Slicer nach einer Probe, die für
diesen Druck nichts sagt.

Warum die Prusa-Kette ihre technischen Werte mitbringt: Mit den drei
`*_settings_id` wählt das Fenster die installierten Profile und zeigt nur
Solidons Abweichung als „geändert“; Prusas Vorgabe stützt nur an gemalten
Verstärkern, daher `support_material_auto = 1`; ohne `filament_retract_*`
überstimmt das Filament den Rückzug.

**Die Lüfterkurve bleibt beim Hersteller (RM-228, Konsolidierung 03.10.2026).**
Orca und PrusaSlicer lesen sie aus dem Filamentprofil des Herstellers und
schreiben sie nur auf eigene Wahl; Hilfs-, Kammer-, Überhang- und Bügellüfter
kennt Solidon nicht und schreibt sie nie (am CC2 und MK4S gegen das
Herstellerprofil allein gemessen: alle Lüfterschlüssel gleich). Cura bekam
dagegen Solidons ganze Materialkurve; die PLA-Schwelle 80 s hob jede erste
Schicht unter 80 s an (Okarina 49 % in Schicht 1 trotz Pause). Unteres Ende
und Schwelle kommen deshalb aus der Druckerdefinition (`fdmprinter`: Formel
`cool_fan_speed`, 10 s); das obere Ende bleibt der Materialwert, weil die
Konsole kein Cura-Materialprofil bekommt und `fdmprinter` jedem Material
100 % gibt.

## CuraEngine rechnet keine Formeln

Was ein geschriebener Wert nicht erreicht, und die Messung:

> Ein geschriebener Wert bleibt damit an seinem Schlüssel stehen und
> erreicht die nicht, aus denen gerechnet wird — die Bahnbreite ihre zwölf
> Bahnbreiten nicht, die Füllung ihren Linienabstand nicht. Die Erbkette
> selbst löst CuraEngine auf, auch die einer Druckerdefinition (gemessen am
> 27.09.2026 mit 5.13) […]

> Gemessen an einem 20-mm-Würfel: **1100 mm Filament statt 818, 753 Sekunden
> statt 660.**

Zu den Werksprofilen (Stufe D, 27.09.2026): „Ihre Formeln erreichen die
Konsole so wenig wie die von `fdmprinter`; ohne Solidons Zeile gälte also
nicht das Profil des Herstellers, sondern das allgemeine."

Warum `-d` den Ordner `extruders` nennt: Über `CURA_ENGINE_SEARCH_PATH` fand
CuraEngine die Extruderzüge unter Windows nicht.

Die Maschine steht nicht in `values_for`, weil sie Installation und fertige
Werte braucht.

## Der Startcode kommt vom Hersteller, die Platzhalter füllt Solidon

Eigene oder übernommene Beschleunigungen oberhalb der Maschinengrenze werden
als Befund mit angefordertem und geschriebenem Wert weitergegeben, auch je
Teil. `SlicerConfig.written` bleibt der tatsächliche Wert; der ursprüngliche
Wunsch steht in `findings`. Fensterprofile und 3MF-Objektwerte begrenzt
derselbe Mechanismus an der aktiven Cura-Instanz. Ein numerischer Text in
`value` zählt als endliches Zahlenliteral, ein Ausdruck bleibt unbekannt.

Ohne Druckerwert oder ausdrückliche Wahl gibt Cura keine Stufenbeschleunigung
vor. Numerische Bewegungsgrenzen und die Leerfahrt kommen aus der
Definitionskette; Platten- und Netzwerte sowie die Rückstellung vor dem
Endcode halten deren X-/Y-Grenze ein. CuraEngine liest in Definitionen nur
`default_value`; numerisches `value` muss deshalb ausdrücklich hinausgehen.
Formeln bleiben unbekannt. Der Standardwert `machine_acceleration` braucht
denselben Deckel: Cura schreibt ihn vor dem Endcode nochmals mit `M204`.

Die Entscheidung Roberts vom 26.08.2026 lautete: „Der Anfahrcode bleibt der
des Herstellers". Warum Solidon füllt: „gemessen:
`START_PRINT EXTRUDER_TEMP={…}` stand wörtlich im G-Code". Die Rechnung
`{machine_depth - 5}` stammt aus dem Endcode des Neptune 4:

> Das Konzept sah hier zunächst nur Textersetzung vor; ohne die Rechnung
> hielte jede Übergabe an den Neptune 4 und 4 Plus an (Stufe D, 27.09.2026).

## Das Cura-Profil gehört dem Drucker, der in Cura aktiv ist

> Gemessen an der Installation 5.13: mit `draft` abgelehnt an Neptune 4 und
> Centauri Carbon, unsichtbar an K1 Max, Ender-3 V3 SE und KE und SV06; mit
> der Stufe der aktiven Maschine überall sichtbar.

Passt kein eingerichteter Drucker, entsteht keine Datei: Ein still
verschwindendes Profil ist schlimmer als keines.

## Winkel zählen nicht überall gleich

> Gemessen an einem Keil mit 30° Neigung: die beiden kippen zwischen 20 und
> 40, Cura zwischen 50 und 70.

## Eine gelungene Übergabe ist noch kein vollständiger Druck

> Ein Slicer, der mit Exit 0 zurückkommt und eine Datei hinterlässt, hat damit
> nicht gesagt, dass der Auftrag darin steht. **Gemessen am 12.09.2026 mit
> Bambu Studio 2.3**: derselbe Würfel einfarbig 4,31 g, zweifarbig 2,82 g —
> ein Filament statt zwei, ein Drittel weniger Material, kein
> Werkzeugwechsel, kein Wort in Ausgabe oder Protokoll. OrcaSlicer und
> ElegooSlicer rechnen dieselbe Platte aus denselben Dateien mit beiden Spulen
> und 102 Werkzeugwechseln; die Übergabe war also in Ordnung.

> — eine Zusage, die nur die Übergabe kennt, wird bei einem fremden Programm
> irgendwann still gebrochen.

> — und ein Fehlalarm, den der Kunde dreimal gesehen hat, nimmt dem echten
> Befund die Wirkung.

## Ein Absturz ist keine Absage

> Beide enden ohne Druckdatei, und bis zum 12.09.2026 bekamen beide denselben
> Satz: „Der Slicer hat keine Druckdatei geschrieben", dazu den Rat, das
> Slicer-Profil zu prüfen. Bei einem Absturz ist dort nichts zu finden.

> Gemessen an Creality Print 7.2, das auf dieser Maschine nie eingerichtet
> war: dreimal `0xC0000005` mitten im eigenen Start, lange bevor es das Modell
> ansieht.

`crashed()` steht vor den Ausgabeprüfungen, weil ein abgestürztes Programm
keinen Satz schreibt; der Rat, das Slicer-Profil zu prüfen, führte ins Leere.

## Über Erfolg entscheidet die Druckdatei, nicht das Prozessende

Bambu Studio legt Druckdatei und `result.json` ab und endet manchmal nicht
mehr (Gesamtprüfung, 27.09.2026).

## Ein Wert gehört an einen Schlüssel, der dasselbe meint

> Bis zum 23.09.2026 stand `cooling.fan_speed` unter `fan_max_speed` **und**
> `fan_min_speed` (Prusa und Cura ebenso): Der Lüfter lief bei PLA in jeder
> Schicht voll, gemessen am ElegooSlicer mit `M106 S255` in 134 von 136
> Schichten, obwohl Elegoos Profil 50 bis 100 % vorsieht (Befund Robert). Und
> weil die Rücklesetabelle nur das obere Ende kannte, überschrieb Solidon
> selbst ein Herstellerprofil, das es richtig gelesen hatte.

Zum Schalter eines Anteils: „Ohne `reduce_fan_stop_start_freq` schaltete der
ElegooSlicer den Lüfter bei jeder PLA-Schicht über 60 s ganz ab."

Warum der alte eine Wert das obere Ende bleibt: „(Entscheidung der
Durchsicht, 23.09.2026: Der Mindestwert war nie eine Wahl des Kunden, sondern
der Fehler)". Auf diesen Absatz verweist
`konzepte/nachweise-herstellerprofil-2026-09/karte-einstellungen-uebergabe.md`
mit alten Zeilennummern; er steht jetzt im zweiten Absatz dieses Abschnitts
der Regel.

## Wie eine Zuordnung geprüft wird

> `verify()` vergleicht sie gegen das Geschriebene: 53 von 53 beim einen, 56
> von 56 beim anderen. […] **CuraEngine schreibt dort nichts** — null von 47.

> In dieser Lücke saß `outer_inset_first`: ein Name aus Cura 4, in Cura 5
> verworfen, ohne Fehler und ohne Warnung — null von fünfzig Lagen begannen
> außen, obwohl der Wert geschrieben war.

## Einstellungen reisen mit der exportierten Datei

Eine 3MF soll man drucken können, nicht erst einrichten. PrusaSlicer
**überspringt die erste Zeile** seiner Beilage (seine Kennung); ohne
`PRUSA_CONFIG_HEADER` fiele der alphabetisch erste Schlüssel lautlos heraus.
