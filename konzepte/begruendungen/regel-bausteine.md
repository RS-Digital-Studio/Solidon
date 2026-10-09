# Begründungen zu `.claude/rules/bausteine.md`

> Stand 27.09.2026. Aus der Regel verschoben, als sie auf das Einzuhaltende
> verdichtet wurde. Die Regel steht dort; hier steht, warum — mit den
> Messwerten und Anlässen ihres Tages.

## Bausteine

Die Formbeschreibung mit zwei Auswertern kam mit P2.7:

> Damit hängt `insert_part` an keiner Installation und bleibt testbar — die
> Entscheidung fiel gegen OpenSCAD als Rechenweg, und seit dessen Ausbau
> (26.08.2026) gibt es die Alternative gar nicht mehr.

Warum Kern und Gang eines Gewindes exakt nie vereinigt werden: „und welche
Fuzzy-Stufe ihn rettet, wechselt von Größe zu Größe (an zwei von achtzehn
Rastergrößen keine)."

## Ein abgezogener Baustein liegt unter seiner Mündung

> Nach oben gebaut steht der Körper vollständig neben dem Bauteil und nimmt
> nichts weg — zweimal geschehen, bei der Passbohrung und der Rasttasche, und
> beide Male sagte der Docstring es längst.

> Eine Bohrung ist bis auf ihre Fase drehsymmetrisch; sie um ihre Tiefe nach
> unten zu schieben ist richtig, solange die Fase eigens an die Mündung
> gesetzt wird. Ein Körper mit einem Oben und einem Unten — eine Rastkante,
> ein Schwalbenschwanz, jede Sperrfläche — kippt dabei um: Die Kante landet am
> tiefen Ende, wo der Haken erst hinkommt, statt zwischen Mündung und Haken zu
> stehen.

Warum die Prüfung die Richtung misst: „Zwei Volumen, die sich treffen, treffen
sich am falschen Ende genauso."

Warum eine Bohrung ohne eigene Tiefe vom Schritt gebohrt wird und nicht vom
Baustein (RM-631):

> Die Mutternfalle reichte fest 10 mm über ihre Tasche hinaus. In einem 40 mm
> dicken Quader blieb ihr Schraubenloch ein Sackloch (z = 27,485 bis 40) und
> hieß Durchgang, auf dem Boden eines 4 mm hohen Spalts bohrte es 6 mm in den
> Backen darüber. Wie dick der Träger ist und was hinter der Fläche steht,
> weiß nur die Operation; jede feste Zahl im Baustein ist an einem Träger zu
> kurz und am nächsten zu lang.

Warum der Deckel bis über die Ebene der Fläche angehoben wird:

> Das Hundertstel über der Mündung reicht nur, solange die Achse senkrecht
> steht; unter 10° blieb über gut der Hälfte jeder Öffnung ein Keil stehen —
> Magnettasche, Schraubenloch, Lagersitz, an beiden Kernen (Durchsicht 0.5.1).

## Ein aufgesetzter Baustein beginnt bei null

> Die Profilklemmschale begann bei der Bundhöhe der Einlage, weil ihr Rahmen
> schon den montierten Zustand des Paares beschrieb, und als Einzelbaustein
> auf einer Fläche stand sie 1,5 mm darüber, zwei Komponenten statt einer
> (16.09.2026). Der Freiraum war richtig und stand am falschen Ort.

Seitdem gilt: „`profile_clamp_ops` gibt `build_shell` die Bundhöhe als
`lift`, die Schale selbst kennt das Maß nicht mehr."

## Was für sich ein Teil ist, steht frei

> Kunden-E-Mail vom 07.10.2026 (RM-562): Kabelclip, Eckwinkel, Rippe,
> Standfuß und Wandhalter ließen sich nur an einen gewählten Körper anfügen.
> Nach *Quader anlegen* ist der Quader gewählt; der Katalog setzte die Rippe
> deshalb an ihn statt neben ihn.

Darum zählt nur eine gewählte Stelle, an die der Baustein gehört, und eine
gerundete Seite trägt einen Flächenbaustein, wie das Handbuch es verspricht.
Am Träger beginnt eine Schraube an der Mündung, der Schaft darunter; ohne
Träger hing er unter dem Druckbett, und die lösbare Mutter schwebte um ihr
Spiel darüber. Im Ursprung lag ein neuer Körper ganz im ersten Grundkörper
(Review B, M1), deshalb die freie Stelle wie beim Laden. Ausgelassen wurden
Rastnase, Schnappverbindung, Schnappverbinder, Scharnierauge, Lasche, Nutfeder
und Lochwand-Einhänger (sie wirken nur am Träger) und das druckbare Gewinde,
das in einer Bohrung oder auf einer Fläche sitzt. Der freie Bolzen ist ein
eigenes Teil (Robert, 08.10.2026: „Beim Baustein Schraube und Bolzen sind
schon Unterschiede“): der *Gewindebolzen* aus demselben Gewindekern, mit
Gesamtlänge, Gewinden an den Enden und Fase. Die Fase schneidet nicht durch die
Gänge; ein Kegel quer durch die Wendel tessellierte am exakten Kern undicht.

Das Netz eines frei gesetzten Erzeugers rollt nicht mit ``keeps_up``, nur seine
Merkmale. So rechnete er schon immer; rollte das Netz, tauschten die erkannten
Flächen der symmetrischen Rohrschelle in alten Projekten die Kennung (Review B,
G1, Entscheidung des Koordinators).

## Was vereinigt wird, kann nur weiter werden

> Die Haltelippe der Magnettasche stand als eigener Kegel neben dem
> Taschenzylinder, wurde mit ihm vereinigt und verschwand darin. Das Werkzeug
> war über die ganze Höhe zylindrisch, und die Lippe hielt in keiner
> Einstellung etwas fest — auch nicht bei `play = 0`, wo die Rechnung darüber
> noch stimmte.

Zur Einführschräge: „sie muss die Mündung weiten, und ein Schaft mit dem
schmalen Kegeldurchmesser verengt stattdessen den Sitz (Fußtasche, derselbe
Tag)."

Warum an der engsten Stelle gemessen wird: „Ein Querschnitt durch die Mitte
eines Kegels zeigt den Mittelwert; die erste Messung tat das und meldete
„hält nicht" für einen Stand, der hielt."

## Zwei Fehler übereinander zeigen eine harmlose Zahl

> Dreimal an einem Tag lagen zwei Fehler so, dass sie einander zudeckten:
>
> * Die Einführfase der Einpressbuchse rechnete `(outer - hole) / 2 + 0,3`,
>   und in der Tabelle stand bei allen sechs Größen zweimal die Bohrung. Die
>   Fase war konstant 0,3 mm — eine plausible Zahl, aus einer Formel, die
>   nichts rechnete.
> * Die Haltelippe verengte um feste 0,2 mm gegen ein Profilspiel von 0,20
>   bis 0,35 **und** wurde vereinigt statt abgezogen. Beide Fehler zeigten
>   dieselbe Öffnung: so weit wie die Tasche.
> * Der Lochwand-Einhänger baute Rechtecke in ein Langloch **und** ließ
>   0,25 mm Sinkweg. Der gebaute Körper war wasserdicht, einteilig und maß in
>   jeder Richtung, was er sollte.
>
> Daraus folgt nichts über das Suchen, sondern etwas übers Glauben: **Eine
> Zahl, die stimmen könnte, ist kein Beleg.**

## Ein Maß, das aus einem fremden Maß folgt, ist ein Fehler in Wartestellung

> Der Schnappverbinder hat es vorgemacht: Seine Armlänge kam aus der
> Einbindetiefe eines **Passstifts** (`1,5 mal Ø`), und der Durchmesser ist
> 12 Prozent der Nahtbreite. Beide Regeln sind für sich richtig — ein Stift
> ist so tief eingebunden, wie er dick ist, das ist Scherfestigkeit —, und
> zusammengekettet ergaben sie eine Bedingung, die niemand aufgeschrieben
> hätte: Ein Federarm hätte eine Naht von 44 mm gebraucht. Gemessen fiel jede
> gewöhnliche Naht auf runde Stifte zurück, dokumentiert und freundlich, und
> das Werkzeug griff nie.

## Test über den ganzen Bereich — mit Nachweis, nicht bei jedem Lauf

> **Der Lauf über alle Bausteine ist am 03.09.2026 aus der Suite gefallen**
> (Entscheidung Robert). Er kostete damals rund eine Minute je Baustein, fast
> alles in der Selbstdurchdringung, und machte aus einem Torlauf von Minuten
> einen von einer halben Stunde. **Seit dem 22.09.2026 steht dahinter ein
> Nachweis:** […] Dazwischen lagen drei Wochen, in denen der Katalog für
> mitgelieferte Bausteine „in der Suite geprüft" annahm, und acht Bausteine nie
> gefahren waren.

Warum jedes Längenmaß beide Grenzen trägt: „der Überhangfächer lief so bis
zum 22.09.2026 nie mit breiten oder langen Stufen."

Warum ein Feld ohne Wirkung keine Ecken zählt: Mit dem eigenen Maß hätte das
Schraubenloch 1536 Ecken gehabt, 400 davon verschieden — der Nenndurchmesser
verdoppelte jede Tabellengröße, für die er gar nicht gilt. Der volle Nachweis
des Gewindes brauchte so 2870 s, weil jede der acht Größen die Ecken Ø 1000 ×
200 mm wiederholte (je rund 34 s, 190 000 Dreiecke); über `MAX_CORNERS` hätte
keine Größenreihe bis M64 gepasst (06.10.2026, RM-532).

## Ein Gewindepaar wird als Paar geprüft

> Bis zum 22.09.2026 begann der Netzgang genau am unteren Ende, und an der
> Unterseite jeder Mutter stand ein Umlauf Material im Gang: bei M8 und
> 0,2 mm Spiel 2,3 mm³ Überdeckung, während beide Teile jeden Einzeltest
> bestanden. Der exakte Zwilling hatte den Vorlauf von einem Umlauf schon;
> `build.threaded` baut ihn seitdem auch am Netz.

Warum ein Gewinde nicht an der Tabelle endet: Bis zum 06.10.2026 kannte der
Baustein nur M2 bis M8, *Schraube erstellen* reichte bis Ø 100 und der
Drehdeckel bis Ø 400 — drei Grenzen für dieselbe Frage. Ein Kunde fand für das
Innengewinde in seinem Rohr mit 60 mm keinen Weg (Vorgang
S-20261006-c66299); Robert: „keine Beschränkungen". Mit dem größeren Maß kam
die Sehnenzahl: Feste achtundvierzig je Umlauf wichen bei Ø 500 um 0,53 mm
von der Rundung ab, mehr als das Spiel eines Paars.

Warum der Netzkern in der Sehnenmitte überdeckt: Mit der Tabelle bis M64
überdeckten sich gedruckte Schraube und Mutter ab M12, gleich an welcher
Stelle (M20 0,27 mm³, M42 10 mm³). Die Splitter lagen in der Sehnenmitte am
Kammradius der Mutter, und sie begannen bei 0,011 mm Sehnentiefe — genau der
Überdeckung von Kern und Gang. Doppelte Sehnen oder ein Kern, der auch in der
Sehnenmitte überdeckt, ließen sie verschwinden; gewählt ist der Kern, weil er
keine Dreiecke kostet und bis M8 nichts ändert.

Warum eine Schraube nicht an der Tabelle endet: Robert, 06.10.2026: „die
Gewinde usw sollten alle Größen unterstützen" und „nicht mehr begrenzen".
Die Tabelle trägt die ISO-Reihe M1.6 bis M64; dazwischen und darüber ist
ein Maß abgeleitet und sagt es, statt eine Normgröße vorzutäuschen.

## Was eine Richtung hat, wird an ihr gemessen

> Rastnase und Schnapphaken standen bis zum 22.09.2026 verkehrt herum — die
> Nase auf ihrer Spitze, der Haken mit der Schräge zum Fuß —, und keine
> Kennzahl sah es: Volumen, Wasserdichtheit und Hülle stimmten.

## Version

Die Liste vor der Verdichtung:

> 1. `parts_version` erhöhen
> 2. Änderungsverlauf ergänzen: was, wann, warum, mit Auswirkung auf die Maße
> 3. Beim Öffnen meldet die Anwendung die *benutzten* geänderten Bausteine,
>    mit der Wahl zwischen neu rechnen und altem Stand

*Anmerkung bei der Verdichtung (27.09.2026, am Code geprüft):* Punkt 1 meinte
die Konstante `LIBRARY_VERSION` in `parts/registry.py` — `parts_version` ist
das Feld im Dokument, gegen das `check.py` beim Öffnen vergleicht. Punkt 2 ist
der `PartChange` in `changes=` am Baustein (`version`, `date`, `reason`,
`effect`); der Stand des Bausteins kommt aus `changes[-1].version`. Punkt 3
galt nur noch für Rezepte: Für Bibliothek und eigene `.py` ist der neue Stand
eine Migration (siehe „Eine Wahl nur, wo es einen alten Stand gibt"). Neu in
der Regel steht `tools/make_examples.py` nach der Änderung, wie in der
Checkliste von `AGENTS.md`.

## Eigene Bausteine sind kein Plugin-System

Regel 13 galt hier „in der Fassung vom 24.08.2026: die Regel schützt vor
ausführbarem Code".

## Ein Rezept ist der eigene Baustein ohne Python

Rezepte sind seit dem 25.08.2026 gebaut. Die Wahl zwischen altem und neuem
Stand kam mit RM-138, `own` umfasst beide Gestalten seit dem 25.08.2026
(„§24.5 will die Kennzeichnung im Katalog"), und der Weg zurück
(`recipe.draft`) kam mit RM-147 E6 am 09.09.2026. Warum Beilagen im Katalog
stehen müssen: „und der Entwurf hielte an einer Stelle an, die mit der Arbeit
des Kunden nichts zu tun hat."

## Ein Paar ist zwei Bausteine und eine Passung

Der Ablauf entstand als RM-147 E1. Warum die Auswertung keine Passung
schreiben darf: „sonst käme bei jedem Neurechnen eine dazu." Warum die
Kennung gelesen wird: „Eine vorher hingeschriebene Kennung ist eine
Vermutung, und eine Passung darauf geht still ins Leere." Warum die Tabelle
der Paare gegen die Bibliothek geprüft wird: „die erste Fassung der Tabelle
war geraten, und `printed_screw` kennt kein `diameter`, sondern `size` und
`play`."

## Herkunft der Normteiltabelle

Die Werte von M1,6 bis M64 stammen von Händler- und Nachschlageseiten
(PreciFast, Aspen Fasteners, fasten.it, schraube-mutter.de, wermac,
mechcodex, engineeringhardware, Wikipedia), nicht von Herstellerblättern —
für große Größen zeigt kaum ein Hersteller seine Maßtabelle frei. Der Zweck
der Regel aus §24.2 ist, keine Normtabelle abzuschreiben; Zahlen sind frei.
Deshalb zählen solche Seiten, wenn eine Stichprobe sie gegen eine zweite
Quelle hält; die zweite Durchsicht von RM-532 hat das für jede Spalte getan
und eine Abweichung gefunden (M1.6 Kernloch 1,3 statt 1,25 nach DIN 336).
