# Begründungen zu `.claude/rules/druckrat.md`

> Am 08.10.2026 aus `regel-schichtanalyse.md` herausgelöst, als der Abschnitt
> „Vorschlag oder Befund“ eine eigene Regel bekam. Die Absätze sind wörtlich
> übernommen; die Regel steht dort, hier steht, warum.

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

Der Brückenbefund riet über einem Tunnel von 20 mm bis zum Review zu RM-627
(09.10.2026) „oder eine Stütze“, wo der Rat keine verlangt. Er nennt jetzt den
Kanal und den Übergang unter 45 Grad, und eine Brücke daneben misst und zeigt
er ohne die Kanaldecke (Steg über 20 mm neben dem Tunnel: am Steg statt über
dem Tunnel). Gefragt wird nur, was weiter als 15 mm spannen kann: Die
Kanalfrage kostet am Drachen (45°) je Decke 17 bis 96 s, für die sieben Stücke
seiner einen spannenden Schicht 143 s, sechs davon unter 0,3 mm²; mit der
Auswahl 21 statt 3 s kalt, mit gemerktem Stützbedarf 0,9 statt 0,4 s.

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

**Eine lange Brücke über dem Modell braucht ihre Stütze dort** (04.10.2026,
RM-281 Paket 3). Der Wedge-Lock (`F:\3D Dateien`) verlangt Stützen allein
über die Brückenregel: eine Decke von 25,7 mm auf 65 mm², deren Säule auf dem
Modell aufsetzt. Weil die Decke unter den Flächengrenzen blieb, schlug derselbe
Rat „nur vom Bett“ vor, und die beiden Vorschläge hoben sich auf: Übernommen
lieferten Creality Print, OrcaSlicer (Kobra 2), PrusaSlicer und Cura null
Stützbahn, ElegooSlicer 1,1 statt 2,6 m, Bambu Studio 0,8 statt 1,8 m.
Seitdem zählt eine lange Brücke über einem Stück, dessen Säule auf dem
Modell aufsetzt (`ModelSupport.open_pieces`, `analysis.open_bridge_width`),
wie ein großes Stück dort. **Gemessen wird die Brücke dieses Stücks, nicht
die der Schicht**: Die erste Fassung fragte die Schicht, und an der
Waschschüssel (Cura-Raster) war deren Brücke von 17,3 mm das Gewölbe des
Kanals, neben einem offenen Stück von 9,9 mm²; je für sich spannten sie
7,9 und 11,5 mm. Der Rat schaltete „überall“ ein, und Cura stellte trotz
Sperre eine Säule von 42 mm in den Kanal (4,1 m Bahn, vorher keine). **Und die
Kanalsperre spart die Säulen der übrigen Stücke auf dem Modell aus**
(`open_columns`): Im Cura-Raster lag am Wedge-Lock ein Kanalstück von 7 mm²
unter derselben Brücke, die Sperre darum füllte deren Raum, und Cura stützte
mit „Stützen automatisch“ und Sperre gar nicht, ohne Sperre 2,0 m.

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

**Der Brim wird nur so breit vorgeschlagen, wie das Bett Platz lässt**
(04.10.2026, RM-281 Nachtrag). Dieselbe Schüssel passt auf 220 auf 220 mm nur
schräg, mit 0,15 mm Rand; vorgeschlagen war ein Brim von 5 mm, und übernommen
druckte CuraEngine (SV06) den Rand neben das Bett („Rand zerrissen“, 176 statt
2 Züge in der ersten Schicht). `advise.brim_room` misst den Rand in der besten
Drehung (`build_area.free_margin`, dasselbe Winkelraster wie `size_excess`):
Reicht er für den Brim des Profils, bleibt es beim Vorschlag; reicht er für
mindestens drei Bahnen, wird die Breite mitvorgeschlagen; sonst entfällt der
Vorschlag, und der Prüfbericht sagt `settings.brim_no_room` mit der Handlung
„Anderes Druckerprofil wählen“. Ebenso der Skirt; beide fragen dieselbe
Randrechnung wie die Übergabe (`build_area.rim_of`, RM-312): Curas Skirt lief an der schrägen Schüssel über den
Bettrand und riss in 23 Züge; fehlt ihm der Platz, heißt der Vorschlag „keine“.
Am Schnitt des Druckdialogs misst die Schüssel −0,06 mm statt 0,14 mm am Netz;
knapp unter null gilt deshalb als „kein Platz“, nicht als „passt nicht“.

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

**Ein schlanker Körper auf kleinem Fuß wird gebremst, auch über dem Auto-Brim**
(29.09.2026). Roberts Fahnenstangen am Centauri Carbon 2 — Ø 7,7 mm, 122 mm hoch,
46,5 mm² Fuß, Höhe zu Breite 12,6 — rissen samt erster Schicht aus Elegoos
Auto-Brim heraus, der selbst fest lag: Der Brim hält den Fuß, nicht die Stange
darüber. Ab 25 mm liefen nur noch sie, mit Wänden bis 200 mm/s und 5000 bis
10 000 mm/s². `_calm_walls` schlägt deshalb für Körper über `SLENDER_RATIO`
unter `SMALL_FOOTPRINT` Außen- und Innenwand auf `SLENDER_WALL_SPEED` und beide
Beschleunigungen auf `CAREFUL_ACCELERATION` vor, je Teil; in Orca fährt die
Innenwand mit der Grundbeschleunigung. Die Schäfte derselben Platte (Ø 25,7 mm,
200 mm hoch, 518 mm²) liefen mit vollem Tempo sauber und bleiben schnell. An
der Stangenplatte kostete das Tempo 29 Minuten, 30 mm/s hätten 1 h 46 min
gekostet. Offen: Brim ohne Abstand zum Teil (RM-318), die übrigen Slicer
(RM-317).

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

**Eine Decke ist als Ganzes Kanal oder Brücke (05.10.2026).** Am Wedge-Lock
an der 0,25er Düse (Kobra S1 und S1 Max, 0,08 mm) galten zwei Ausrundungen
von zusammen 0,0 mm² am Fuß einer 25-mm-Brücke als Kanaldecke: Ihr Ort liegt
an der Beinwand, und dort fasst der Raum keinen Kreis von `CHANNEL_WIDTH`. Die
vier Schichten Brücke darüber hingen außerhalb eines Kanals und verlangten
Stützen, die Kanalstücke die Sperre, und die Sperre deckte die ganze Decke:
0 statt 6,6 m Stütze in Anycubic Slicer Next, obwohl `channel_space` die
Grundrisse der offenen Säulen schon aussparte. Bei 0,2 mm gab es kein solches
Stück. Die Ursache ist die Frage an einem einzelnen Ort, deshalb fragt
`_Ceilings` die Decke: Stücke benachbarter Schichten gehören zusammen, wenn das
untere dem oberen so nahe liegt wie das Material seiner Schicht (0,13856 gegen
0,13827 mm am Wedge-Lock, bis auf `OVERHANG_MARGIN`). Entschieden wird nach
Fläche und nur in eine Richtung: Die Waschschüssel hat im CC2-Raster eine
Decke mit 186 mm² im Kanal und 44 mm² offen, deren offenes Stück selbst
16,3 mm spannt; „eine lange Brücke macht die Decke offen“ hätte ihren Kanal
freigegeben, „ein offenes Stück macht alles offen“ ebenso. Im Korpus
`F:\3D Dateien` nimmt die Regel nur Kanalstücke, deren Ort höchstens 0,63 mm
neben der Wand der Schicht darunter liegt — Wandstreifen von Gewölben über
Räumen weiter als `CHANNEL_WIDTH` (Pool-Wasserfall, Kumiko-Organizer, die
Waschschüssel in ihrer Dateilage bis 2,6 mm); nach *Druckoptimal ausrichten*
behält die Waschschüssel jedes Kanalstück.

**Eine Kanaldecke liegt zwischen ihren Auflagen, und gesperrt wird nur Raum,
an den man nicht hinkommt (08.10.2026, RM-566).** Roberts Drache
(`F:\3D Dateien\Drache.p3d`, 2,9 Mio. Dreiecke, 171 × 122 × 130 mm) druckte am
Centauri Carbon 2 mit übernommenen Vorschlägen Kiefer, Kinnstacheln und
Flügelbögen in die Luft. 738 Überhangstücke galten als Kanaldecken: Schuppen,
Stacheln und Flügelansatz hängen in Räumen, die keinen Kreis von 30 mm fassen,
und ihre Säulen setzen auf dem Modell auf. Die Sperre im Umkreis von 15 mm um
jede Kanalsäule war mit 259 000 mm³ größer als der Drache (220 000 mm³). Im
G-Code (Anteil der Überhangfläche außerhalb der Kanaldecken mit Stützbahn bis
1,2 mm darunter, `.claude/.state/drache-2026-10-08/gcode_stuetzen.py`) stützte
der ElegooSlicer 71,9 % statt 97,7 % ohne Sperre, der OrcaSlicer 47,4 % statt
100 %. Kanaldecken zählt der Messwert nicht mit: Ihre Stütze soll fehlen, und
mit ihnen sah jede Sperre wie ein Verlust aus, auch die richtige.

Was nicht trug, in der Reihenfolge der Versuche: „Irgendein Stück spannt“
(Bahnrichtung mit Halt an beiden Enden) — in den Zwickeln zwischen Schuppen
spannt fast immer ein Splitter. „Jedes Stück der obersten Schicht spannt“ —
der Wasserkanal der Waschschüssel ist ein gekrümmtes Band, und an seiner
Mündung hängt oben ein Splitter an einer Wand. Eine Breitengrenze für
einseitige Stücke — die Gewölbestreifen der Schüssel sind bis 4,8 mm breit, die
Knochenspitze am Flügel 2,2 mm. „Zwei getrennte Auflagen oder der halbe Rand“
— ein Eckregal an zwei angrenzenden Wänden schloss damit immer, ebenso eine
Kragplatte mit einem Stift an ihrer Wurzel, und ein Krümel derselben Decke
schloss die ganze. Halt am eigenen Material — unter dem Streifen k+1 einer
schrägen Unterseite liegen die Streifen 1 bis k derselben Decke und dazwischen
je ein Band der Überhangzugabe; ein Kiefer mit gewölbter Unterseite wurde Kanal
(Review 1: bis 187 von 288 mm² gesperrt), eine Konsole mit 17° Unterseite über
einem Graben ganz (Review 2). Die Größe als Bedingung für „Kanal“ — dann
zählten die Schlitze eines Kotschiebers aus dem Korpus als Überhang, und der
Rat verlangte Stützen, wo sich jede Schlitzdecke selbst trägt. Eine Grenze für
die Spannweite (nirgends weiter als `CHANNEL_WIDTH / 2` von der Auflage) —
sie änderte am Drachen nichts und machte das Gewölbe eines Halters aus dem
Korpus, in der Aufsicht 40 mm breit, zur offenen Decke. Und eine Flächengrenze
für die Sperre allein (Sperre nur für Decken, die ohne sich zu schließen Stütze
bräuchten): Sie hielt den Drachen im ElegooSlicer frei, aber nicht im
Cura-Raster (Winkel 50°: 40 gesperrte Säulen, 96,3 statt 100 %) und nicht bei
130 % Größe (94,3 statt 98,7 %). Den Zuschlag schob der Schreiber erst nach dem
Aussparen hinaus, wieder in die ausgesparten Säulen.

Die Ursache am Drachen zeigt das Cura-Raster: In einer Falte der Flughaut, im
Innern eines hohlen Flügelknochens, hängt eine echte Kanaldecke. Ihr Umkreis
von 15 mm lief aus dem Knochen heraus in den offenen Raum unter dem Flügel, und
dort liegen die Überhänge, die Stütze brauchen. Der Slicer liest sie mit seiner
eigenen Regel; genau ausgespart hielt Solidons Grundriss ihre Stütze nicht.

Seitdem gilt eine Decke als Kanal, wenn ihr Grundriss zwischen seinen Auflagen
liegt — zu `CEILING_SPANNED` in der Hülle der gehaltenen Randstücke oder
ringsum gehalten, und gehalten nur von Material neben ihrem geschlossenen
Grundriss (`_Ceilings.closes`, entschieden nach Fläche); sie zählt dann nicht
zum Stützbedarf, gleich wie klein. **Gesperrt wird nur Raum, an den man nicht
hinkommt**: zu eng für den Kreis der Kanalfrage (`_narrow`) oder ringsum
umschlossen, ein Loch der Fläche (`_enclosed`). Die Schüssel in Dateilage verliert so den Sperrraum
unter halber Säulenhöhe (147 906 → 28 862 mm³); dort stellte ohne Sperre der
PrusaSlicer 140,6 m Stütze hin, mit der kleineren Sperre keiner der beiden
gemessenen Slicer — sie trug nur die Decke, und die ist gesperrt. Den Umkreis
`CHANNEL_WIDTH / 2` bekommt eine Decke, die ohne sich zu schließen Stütze
bräuchte (`worth_support`, gefragt am größten Stück); der Wasserkanal hat
922 mm² (in Drucklage 176 mm², 86 mm² auf einmal), die größte Tasche am
Drachen 96 mm². Stützbedarf und Aussparung fragen dieselbe Regel am Feld:
Wo eine Decke über Stütze oder keine entscheidet, fällt der Zweifel auf
Stütze. Als Feld gefragt, sperrte der Drache bei 130 % eine zweite Decke
(149 mm² in 48 Streifen) und nahm fast doppelt so viel stützbedürftige Fläche
unter die Sperre, 451 statt 236 mm² (Review 3). **Die übrigen Kanaldecken bekommen keine
Sperre**, auch keine kleine: Mit Umkreis um jede Taschendecke stützte der
ElegooSlicer den Drachen zu 87,8 %, mit zwei Bahnbreiten um ihren Grundriss
noch zu 96,7 % statt 97,7 %. Was dafür offen bleibt, ist erreichbar — am
Countercleaner aus dem Korpus 29 m Stütze in einer Kehle, die nach zwei
Seiten offen ist, unter einer Decke, die sich selbst trägt.

Ausgespart werden die Säulen der Überhänge, die selbst Stütze brauchen: Inseln
und Stücke, deren Decke ohne ihre Kanalstücke als Feld (`_field`, die Streifen
in der Aufsicht vereinigt) `worth_support` genügt — auch eine schräge
Unterseite, die in Streifen unter 10 mm² zerfällt. Was Solidon für
selbsttragend hält, darf unter die Sperre: Ein Stachel neben einer gesperrten
Tasche (Feld 12 bis 24 mm²) verliert dort bis zu 81 % seiner Unterseite
(Review 2 und 3). An der Mündung des Wasserkanals hängt ein offenes Stück von
11 mm², das sich selbst trägt; ausgespart, holte der ElegooSlicer es mit einem
Ast quer durch den Kanal (1,4 m). Mit ihren Kanalstücken gefragt, galt jedes
offene Stück dort als stützbedürftig, und gehalten hat es nur die Ausnahme im
umschlossenen Raum (Review 3). **Im umschlossenen Raum wird nur ausgespart, was
von oben erreichbar ist**: Eine Stütze in einer Kammer holt niemand heraus; eine
schräge Fläche im Rohrbogen des Wasserkanals, die selbst Stütze bräuchte, holte
der ElegooSlicer sonst ebenso (1,6 m). Enger gefasst kam der Ast wieder: „eng
und umschlossen“ 0,7 m, denn der Rohrbogen ist weit. Umschlossen heißt aber ein
Loch im Schnitt, und das ist auch das Innere jedes oben offenen Gefäßes: Ein
Sims 14 × 14 mm in einem Becher von Ø 68 mm, 6 mm neben einem gesperrten
Tunnel, lag zu 65 % im Sperrraum (Review 2, RM-571). Nach dem Loch gefragt,
trennt nichts den Becher von der Schüssel: „zur Hälfte überdacht“ nahm ihr den
Sperrraum fast ganz (169 209 → 9 468 mm³), denn ihr Kanal liegt im oben
offenen Becken (0–14 % des Lochs überdacht).

Gefragt wird deshalb die Säule, je Scheibe (`_open_above`, RM-571, 09.10.2026):
Liegt im Saum von zwei Bahnbreiten um ihren Grundriss, mit ihr durch freien
Raum der Scheibe verbunden, mindestens eine Bahn breit ein Schacht, über dem bis
über das Teil hinaus kein Material liegt und der einen Kreis von `CHANNEL_WIDTH`
fasst, bleibt sie frei. Der Saum hängt an der Säule, weil hinter einer dünnen
Wand die Luft außerhalb des Teils liegt. Er ist rund, an jeder Ecke gleich weit:
Mit Gehrung reichte er an einer spitzen Ecke bis zehn Bahnbreiten, und eine Nase,
deren Spitze 3 mm vor einer Öffnung lag, machte einen Sims erreichbar, der ohne
Nase gesperrt blieb (Review von RM-571). Die Weite des Schachts ist derselbe
Kreis, an dem `_narrow` entscheidet, ob man an einen Raum herankommt; durch einen
engeren Spalt holt niemand eine Stütze heraus. Zuerst genügte eine Bahn breit,
und damit galt ein Becher mit Deckel und einem Schlitz ab 0,5 mm neben dem Sims
als offen (4 statt 64 % des Simses im Sperrraum, Review). Unter einer Bahn kommt
sicher nichts heraus, aber dass eine Bahn genügt, hatte niemand belegt. Die
Bahnbreite bleibt als Mindestbreite, mit der Saum und Schacht sich berühren; der
Sperrraum selbst verlangt mehr als zwei Bahnbreiten, eine Bahn samt Abstand.
Der Schacht steht senkrecht, und das ist eine bekannte Grenze (Nachprüfung von
RM-571): Ein schräges Loch der Weite 2R in einem Deckel der Dicke H zählt nur mit
seiner senkrechten Durchsicht 2R / cos θ − H · tan θ. Ein Loch Ø 34 mm in einem
Deckel von 20 mm, 20° geneigt, sieht senkrecht 28,9 mm; der Sims daneben liegt zu
64 % im Sperrraum statt zu 4 % und druckt dort ohne Stütze, obwohl das Loch quer
zu seiner Achse weit genug bliebe. Den Schacht entlang seiner Achse zu suchen
hieße, den Himmel je Richtung neu zu schichten, für eine seltene Form.
Ausgespart wird die ganze Säule, auch was von ihr unter einem Dach liegt: Ihr
Stück braucht selbst Stütze. Am Wedge-Lock nahm eine Sperre über der Säule einer
Brücke ihr die ganze Stütze (Cura 0,0 statt 2,0 m). Was ein Slicer unter einer
zur Hälfte gesperrten Säule stellt, ist nicht gemessen, und dass man die Stütze
an ihrem offenen Ende ganz herauszieht, ist eine Annahme. Eine L-förmige Säule
aus dem offenen Becher in den Tunnel bleibt so im Tunnel frei; nur ausgespart,
was nicht eng ist, läge dieser Teil ganz im Sperrraum (Test
`test_a_reachable_column_is_spared_whole`). Ein
Streifen vom offenen Becher 14 mm in den Tunnel, an dem das im Review auffiel,
ist mit dem Schacht nicht mehr erreichbar: Die Tasche zwischen Block und
Becherwand, aus der er kommt, ist 16 mm weit. Am Becher berührt der Sims den
Schacht in allen elf Scheiben unter ihm und liegt bis auf die Naht an der
Blockwand frei (2 %, die Bahnbreite, die sein Überhang an der Wand nicht
mitzählt). An der Schüssel in Drucklage (50°, 55°, 60°) und in Dateilage (55°,
60°) berührt keines der 4 bis 32 Überhangstücke im Sperrraum den Himmel — auch
nicht die Stücke an der Mündung, die unter dem Dach des Ausgusses hängen —, und
ihr Sperrraum bleibt gleich (Drucklage 186 704, 177 017 und 169 243 mm³,
Dateilage 53 009 und 46 468 mm³). Im Slicer, Vorschläge übernommen, Stützbahn
unter dem Sims vorher und nachher, in Klammern der Slicer ohne Sperre:
ElegooSlicer CC2 2,41 → 6,06 m (6,07), OrcaSlicer Kobra 2 2,62 → 4,35 m (4,35),
PrusaSlicer MK4S 1,95 → 4,64 m (4,67), Cura SV06 2,57 → 4,40 m (4,40); im
Tunnel in allen vier 0,0 m (ohne Sperre 2,2 bis 6,6 m). Die Schüssel in
Drucklage behält in allen vier ihren Sperrkörper (gleiches Volumen) und 0,0 m
Stütze im Wasserkanal, ihre Stützbahn ist dieselbe wie vorher; über den Korpus
`F:\3D Dateien` (243 Körper) ändert sich kein Vorschlag und kein
Sperrvolumen. Der Himmel über dem Saum entsteht je Säule
einmal von oben nach unten (`_sky_above`); je Scheibe von unten gefragt, kostete
der Becher jede Schicht über dem Sims einmal je Scheibe. Gekostet hat die
Frage am Becher 0,08 → 0,17 s für den Sperrraum (Median aus acht Läufen im
Wechsel, Wandzeit); an Schüssel, Drache und Eiffelturm, wo keine ausgesparte
Säule im Umschlossenen steht, nichts — gefragt werden nur Säulen, die den
Sperrraum schneiden, und die Schüssel in Dateilage wird damit schneller
(5,6 → 2,9 s). Der Schacht sucht seinen Himmel in einem Fenster, das 30 mm über
den Saum hinausreicht; das kostet am Becher 0,23 → 0,58 s CPU-Zeit gegenüber
dem Stand mit einer Bahn als Maß (Median aus acht Läufen im Wechsel, unter
Fremdlast, die Wandzeit sagte dabei nichts). Ohne Vereinfachung des Himmels nach
jeder Schicht waren es 1,1 s, denn jede Schicht schneidet die Becherwand an
etwas anderen Punkten, und der Himmel wuchs auf 3 916 Ecken. Seit eine Schicht,
die den Himmel nicht mehr schneidet, nur noch danach gefragt wird
(`SKY_SKIP_INSET`, aus der Nachprüfung), kostet der Becher 0,64 → 0,28 s, also
so viel wie vor dem Schacht; ein Becher als Kegelstumpf, dessen Wand jede
Schicht neu schneidet, bleibt bei 0,42 → 0,45 s (CPU, Median im Wechsel, alle
Scheiben gleich). Am Eiffelturm (8,6 → 8,7 s), an Schüssel und Drache fragt
keine Säule nach dem Schacht, und der Sperrraum bleibt überall gleich. Der
Zuschlag einer Bahnbreite kommt vor dem Aussparen; ein Loch, in dem keine Bahn
samt Abstand Platz hat, schließt sich (ein Krümel von 0,33 mm² im Kanal,
ausgespart mit Zuschlag: 1,5 m Stütze im OrcaSlicer). Vorgeschlagen wird die
Sperre nur, wenn sie Raum sperrt. Gesperrt wird nur, wo eine Bahn samt
Abstand Platz hat (`channel_space`); Hülle und Scheibenhöhe begründet der
Abschnitt zu `support.block_channels` weiter oben.

Gemessen am Endstand: Im ElegooSlicer bekommt der Drache keine Sperre mehr und
ist zu 97,7 % gestützt wie ohne Solidon. Im Cura-Raster und bei 130 % Größe
sperrt Solidon den Hohlraum im Flügelknochen, den der Slicer ohne Sperre mit
Stütze füllt, die nie mehr herauskommt, und stützt 96,8 statt 100 % bzw.
97,6 statt 98,7 %. Die Waschschüssel in Drucklage druckt in ElegooSlicer,
OrcaSlicer, PrusaSlicer und Cura wie vorher: keine Stütze im Wasserkanal (ohne
Sperre 12,8 m im ElegooSlicer, 50,7 m im PrusaSlicer).

**Eine schräge Unterseite ist ein Feld (08.10.2026, RM-570).** Ein Kinn mit
18° flacher Unterseite zerfällt im Schnitt in 31 Streifen von höchstens
6,4 mm², zusammen 189 mm². Gefragt war das größte Stück, und unter
`OVERHANG_LAYER_MINIMUM` sagte der Rat „keine Stützen“ — in der Aufsicht ist es
eine Fläche von 189 mm². Seitdem zählt, wenn das größte Stück die Grenze
verfehlt und die Summe über 100 mm² liegt, auch die größte Decke als Feld
(`largest_sloped_patch` über `_field`): ihre Streifen vereinigt, nicht
summiert, ohne Kanalstücke, und nur, wo sie im Mittel breiter sind als
`OVERHANG_MARGIN` — sonst ist es eine Wand, die sich auffängt. Erst ab einer
Summe von 150 gefragt, blieb ein Feld von 134 mm² „keine Stützen“ (Review 3).
**Auch der Stützort fragt das Feld** (`ModelSupport.open_field`, so viel, wie
davon auf dem Modell aufsetzt): Sonst verlangte der Rat am Kinn über der Brust
Stützen und zugleich „nur vom Bett“, und das Kinn druckte weiter in die Luft.
Der Gitterbecher bleibt ohne Stütze, und im Korpus (242 Körper) ändert sich
außer der Sperre kein Vorschlag. Die Feldfrage über den ganzen Körper kostet am
Drachen 8,2 s CPU. **Der Prüfbericht nennt die Stelle** (RM-572,
`findings.small_overhang_findings`): Wo der Rat über die Fläche Stützen
verlangt und kein Stück die Meldeschwelle erreicht, zeigt er die Schicht mit
der meisten Überhangfläche an ihrem größten Stück. Er fragt dieselbe Antwort
(`support_need`), aber nur, wo er auch eine andere Lage sucht — höchstens acht
Körper, ab 1 cm³ Stützraum —, denn sie ist seine teuerste Frage. Nur der
Flächenweg zählt: Inseln und lange Brücken haben eigene Zeilen, und
Inselstücke, Kanaldecken und Ränder gehen weder in die Fläche noch in den Ort
ein.

**Das Mindesttempo bremst Spitzen, damit die Mindestzeit greift (08.10.2026,
RM-580).** Am Drachen erreichten die obersten 12 mm in keinem Slicer die
Mindestschichtzeit des Herstellers: Der Slicer bremst eine kurze Schicht nur
bis zum Mindesttempo, und Elegoo, Bambu und Creality nennen für PLA 20 mm/s.
Gemessen als Schichten, deren schnellster Extrusionsvorschub nicht über dem
Mindesttempo liegt (`.claude/.state/drache-2026-10-08/gcode_anschlag.py`):
ElegooSlicer 34 → 15, Bambu Studio 34 → 15, Creality Print 44 → 28,
OrcaSlicer (Kobra 2) 36 → 27, Cura 21 → 16; PrusaSlicer 19 → 19, dort laufen
dieselben Schichten viermal so langsam. Übrig sind je die letzten 2 bis 4 mm
der Spitzen, so klein, dass auch 5 mm/s die Mindestzeit nicht erreichen.
Vorgeschlagen wird ein kleineres Mindesttempo, nicht eine längere
Mindestzeit: Die stimmen die Hersteller auf ihre Lüfter ab, und mit 15 s
überstimmte der Rat sie im Druckerplan der Gesamtprüfung 97-mal. Gefragt wird,
ob über einen Millimeter Höhe Schichten mit dem eingestellten Tempo nicht
einmal die halbe Mindestzeit brauchen; der Weg einer kleinen Schicht ist ihre
Fläche durch die Bahnbreite. Im Korpus (242 Körper) bekommen 47 den
Vorschlag, alle mit kleinen Querschnitten. Die Zeitschätzung rechnet seitdem
mit dem Mindesttempo der Einstellungen, damit sie nach der Übernahme stimmt.

**Bäume, wo kleine Überhänge auf dem Modell ansetzen (08.10.2026,
RM-581).** Ein Gitter setzt mit jeder Säule auf dem Modell auf, ein Baum mit
wenigen Füßen. Am Drachen setzten die Gitter der Hersteller 212 bis 324 mm²
auf dem Modell auf, Solidons Bäume 4 bis 66 mm² (`gcode_auflage.py`). Elegoo
und Bambu stützen ohnehin mit Bäumen; „automatisch“ heißt bei Orca, Prusa,
Creality und Cura Gitter. Unter einer großen flachen Decke hängt die
Unterseite zwischen den Baumspitzen durch, und die Wikis von OrcaSlicer und
Prusa raten dort zu Hybrid- oder normaler Stütze
(`konzepte/recherche-slicer-einstellungen-2026-10.md`); flach heißt
ein Stück über `OVERHANG_LAYER_WORTH_SUPPORT` auf einer Schicht.

**Gitter unter der flachen Decke, Hybrid bei beidem (09.10.2026, RM-584).** Bis
dahin blieb unter einer flachen Decke die Art des Herstellers — bei Elegoo und
Bambu also Bäume, unter denen sie durchhängt. Gemessen an einer Tischplatte mit
Kinn in allen sieben Programmen (`output/drache-2026-10-08/stil-rm584*`): Hybrid
kommt in Elegoo, Orca, Bambu, Creality und Anycubic als `tree_hybrid` an und
stützt die Decke mit Gitter, die Details mit Ästen (ElegooSlicer 71 300 mm
Stützbahn gegen 146 364 mm unter reinen Bäumen). PrusaSlicer und Cura kennen kein
Hybrid; dort schlägt der Rat unter einem gewählten Baum gleich Gitter vor.
**„Automatisch“ bleibt, wo es keine Bäume heißt** (Durchsicht RM-584, M1): Bei
PrusaSlicer stützt es mit dem Stil des Prozesses, am MK4S `snug`, den die
Recherche (Nr. 4) für flache Decken neben `tree_hybrid` empfiehlt; Cura schreibt
dafür `normal`, dieselbe Übergabe wie Gitter. Der Grund „Große flache Decken
hängen zwischen Baumspitzen durch“ stand dort über einer Stütze ohne Spitzen.
Hybrid verlangt kleine Stücke auf dem Modell neben der Decke: Am Tisch setzt
nur die Platte selbst auf dem Sockel auf, und „Bäume für Details“ stand über
einem Teil ohne Detail (L7). Gitter und Baum zweier Körper werden nur Hybrid,
wo die Art der Platte gilt; die Orca-Familie schrieb sonst je Objekt Gitter und
Baum, und die Zeile zeigte Hybrid (M3). **Zwei Wände für hohe Bäume** (Recherche
Nr. 5): Ab 100 mm brechen Bäume mit einer Wand. Am ElegooSlicer an einem 120 mm
hohen Turm mit Insel ergab Hybrid mit zwei Wänden 14 % mehr Stützmaterial; unter
organischen Bäumen war der G-Code mit einer und zwei Wänden derselbe — dort
schlägt Solidon die Wände nicht vor. Das gilt gefüllten Bäumen: Der Slicertest
der Durchsicht fand am Neptune 4, dessen Prozess das Grundmuster `default` führt
und Bäume hohl druckt, mit zwei Wänden 13 234 statt 12 211 Bewegungen, auch ohne
eigene Stützschichthöhe; mit `rectilinear` war der G-Code derselbe
(`handover.hollow_trees`). Den Abstand oben runden hohle Bäume wie organische:
Am Neptune 4 druckten 0,28 mm bei 0,2 mm Schicht wie 0,2 mm, 0,4 mm anders.
Creality Print liest die Wände als `tree_support_wall_count_tree`, mit Vorgabe 0,
und die Grundlage liest denselben Schlüssel. Derselbe Test bestätigte OrcaSlicer und Anycubic
Slicer Next; Bambu Studio (ohne die Schlüssel der organischen Äste) las die
Wandzahl auch unter seinen Bäumen, Creality Print 7.2 überall, aber nur als
`tree_support_wall_count_tree` — den gemeinsamen Namen überging es auch unter
Hybrid. PrusaSlicer zählt keine
Wände: Seine Doppelwand ab einem Astquerschnitt (`support_tree_branch_diameter_double_wall`,
Vorgabe 3 mm) ist ein Maß, und eine geschriebene Wand schaltete sie ohne Bündel
ab (M5). Die Säulenhöhe reicht bis zum Bett, wenn ein Teil der Säule es
erreicht: Bis zur ersten Berührung gemessen, war eine Platte auf 150 mm über
einem Turm von 120 mm 30 mm hoch (L1). Der Fuß hoher Bäume ist noch offen (RM-584).

**Ränder tragen sich selbst (08.10.2026, RM-582).** Der Eiffelturm aus dem
Korpus ist ohne Stützen gedacht („一体无支撑“). Der Rat verlangte Stützen wegen
der Ränder seiner Plattformen — oben ein Kranz, der in drei Schichten 2,6 mm
über den Schaft wächst, darunter Ränder unter 1 mm —, und die Slicer stellten
dafür Baumstämme außen am Turm hoch: ElegooSlicer 831 m, OrcaSlicer 558 m,
PrusaSlicer 294 m, Cura 311 m. Im Schaft selbst sperrte die Kanalsperre
schon. Gemessen wird die ganze Decke, nicht das Stück: Die Streifen einer
schrägen Unterseite ragen je Schicht kaum über die vorige, ein Kinn als
Ganzes aber 18 mm über die Kehle. Und die Fläche, nicht der Umriss: Eine flache
Decke zwischen zwei Wänden hat alle Ecken auf den Wänden und spannt in der
Mitte trotzdem weit (der breite Tunnel aus `test_slice_findings` fiel mit dem
Umriss als Maß zuerst darunter). Was jenseits der 3 mm liegt, darf
höchstens 5 % des Felds sein (`LEDGE_SPILL`, das Rauschen der Puffer) und
samt seinem Ansatz für sich keine Stütze lohnen (`worth_support`). Ein Saum
taugte nicht: Die 19 Streifen einer Fase von 52° über 5 mm haben zusammen zehn
Meter Umfang, und ein Saum von 0,05 mm machte sie zum Rand. Der Anteil allein
ließ an einem langen Flansch eine Lasche durch, die allein Stütze bräuchte;
eine feste Grenze von 10 mm² verlangte für Flansch und kleine Lasche, die sich
je für sich tragen, Stützen unter dem ganzen Flansch; und ohne Ansatz gemessen
hatte eine Lasche von 14,5 mm ab der Wand nur 92 statt 114 mm². Eckspitzen
unter 10 mm² wachsen nicht mit: An einer gezahnten Säule mit zwanzig Ecken
verlangten sie sonst zusammen Stützen (vier Reviews vom 08.10.2026). Am
Eiffelkranz liegen 1,0 von 214 mm² jenseits, an der Fase 124 von 281. **Eine
Decke, die eine Öffnung überspannt, ist kein Rand**, auch wenn sie nur 3 mm
breit ist: Eine Ringschulter im Becher legt ihre Bahnen als Sehnen über die
Öffnung, an beiden Enden auf der Wand — der Schaden des Gewürzbehälters.
Bahnen mit Halt an beiden Enden gibt es nur, wenn die Auflage das freie Stück
von außen fasst und es breiter ist als zwei Bahnen. Der Kranz um einen hohlen
Schaft und der Rand einer offenen Plattform hängen an ihrer Innenkante, eine
Stufe im Becher schmaler als zwei Bahnen spannt nicht; sie bleiben Ränder. Wie
breit zwei Bahnen sind, sagt der Schnitt (an der 0,4er Düse 0,84 mm): Eine
Stufe von 1 mm ist dort schon eine Schulter. Gefragt wird
geometrisch, nicht an der Brückenweite der Schicht: Der Stützschnitt der
Übergabe misst keine Brücken, und die Sperre hätte die Schulter wieder als
Rand gesperrt. Ein Rand spannt deshalb wirklich keine Brücke — eine
einseitige Konsole misst ihre Diagonale —, und Rat und Bericht schweigen dort
gleich, **je Stück, nicht je Schicht** (RM-627, 09.10.2026): Ein Kragen von
2 mm um eine Wand, vom Kinn unterbrochen, meldete 46,2 mm, sobald ein
Kinnstreifen von 4 mm² auf seiner Schicht lag, und an einer Wand mit U-Kragen
schaltete ein Sporn von 8,5 mm² daneben die Stützen ein. Gemessen werden
deshalb nur die Kerne der übrigen Stücke (`span_beside`), nicht die freien
Flächen, die sie berühren: Eine Flanke zwischen etwa 14 und 45 Grad legt je
Schicht ein Band frei, schmaler als die Zugabe des Überhangs, das Rand und
Sporn zu einer freien Fläche verbindet — an einer Wand mit zwei solchen
Flanken spannte die Schicht wieder 40,1 statt 6,2 mm (Review). Weil der Slicer nach seinem Winkel jede flache Unterseite stützt,
sperrt `support.spare_ledges` die Überhangfläche der Ränder in der Übergabe,
um eine Bahnbreite hinaus und ohne die Überhänge, die Stütze brauchen; Stämme
anderer Stützen laufen durch eine Sperre hindurch. Am Eiffelturm stehen mit
Solidons Vorschlägen 216 statt 869 m Stütze im ElegooSlicer, in OrcaSlicer 163
statt 592, in PrusaSlicer 81 statt 367 und in Cura 104 statt 358 m (gegen
„Stützen automatisch“); der Rest steht unter den Bögen unten. Im Korpus
bekommen 45 von 242 Körpern den Vorschlag, und 7 brauchen keine Stützen mehr:
Ihr einziger Überhang waren Ränder.

**Der Stützkontakt folgt dem Material der Spule (09.10.2026, RM-583).** Narben
und verschweißte Stützen kommen am häufigsten von einem Abstand, der nicht zu
Schicht und Material passt, von fehlenden Trennschichten, wo die Stütze auf dem
Modell steht, und von einer Trennschicht, die unter kleinen Flächen zu dicht
sitzt (`konzepte/recherche-slicer-einstellungen-2026-10.md`, Nr. 1, 2, 3, 7):
PLA etwa eine Schicht, PETG das 1,25- bis 1,5-Fache, darüber volle Kühlung.
Ein Projektmaterial gibt es dafür nicht (Robert, 08.10.2026: „immer nach dem
verwendeten Material“) — PLA und PETG auf einer Platte brauchen verschiedene
Abstände, deshalb gehen Abstand und Trennschichten je Teil und der Lüfter je
Spule. Gemessen an zwei gestützten Stufenkörpern auf einer Platte, einer mit
Objektwerten (`.claude/.state/drache-2026-10-08/kontakt_je_teil.py`, Lagen je
Höhe gezählt, Raster 2 mm, Bambus Übergangslage als Stütze): Der Abstand oben
kommt in allen acht Programmen an, 0,4 mm gegen 0,2 am Bezug (Anycubic 0,1;
SuperSlicer bei 0,15er Schichten 0,53 gegen 0,33). Die Trennschichten kommen
wie geschrieben an, Prusa und Cura genau (geschrieben 5 oben und 0 unten gegen
2 und 2). Die Orca-Familie zählt anders: oben eine Übergangslage mehr (Orca,
Elegoo, Creality und Anycubic 6 gegen 3), unten die Kontaktlage dazu (Bezug 3
statt 2; Bambu druckt sie bei null als gewöhnliche Stütze,
`SupportCommon.cpp`). Das Herstellerprofil meint dieselbe Zählung, also gleicht
Solidon nichts aus. Die weite Lücke legt je Ebene deutlich weniger Bahn (Orca
1044 gegen 1617 mm, Prusa 944 gegen 2512); Cura nimmt sie nur für die ganze
Platte, denn ihr Linienabstand gehört dem Stützextruder. Mit dem echten Rat
bekommt das PLA-Teil 0,2 und das PETG-Teil 0,28 mm. **Die Orca-Familie rundet den Abstand
auf ganze Schichten, wenn die Stütze die Schichthöhe des Modells hat**
(`Slicing.cpp`), und Elegoos Prozesse für C2 und CC2 stellen es so ein: Aus
0,28 wurden im ElegooSlicer 0,2. Setzt Solidon einen Abstand zwischen zwei
Schichten, schaltet die Übergabe `independent_support_layer_height` ein; der
ElegooSlicer druckt dann 0,28. Mit zwei Filamenten baut die Orca-Familie einen
Reinigungsturm und schaltet die eigene Höhe selbst wieder ab
(`PrintConfig.cpp`, `normalize_fdm_2`; „je Objekt“ mit mehreren Objekten baut
keinen, glatter Zeitraffer immer einen) — Orca, Elegoo, Creality und Bambu
druckten das PETG-Teil neben PLA mit 0,2, PrusaSlicer mit 0,28. Mit Turm legt
die Orca-Familie die Stütze auf die Schichten des Modells und rundet zur
nächsten (`SupportMaterial.cpp`); PLA bei 0,08 mm Schicht bekam so aus 0,10
eine Schicht, 0,08, unter dem Minimum. Neben einem Turm rät Solidon deshalb
wie bei Cura gleich ganze Schichten innerhalb der Materialgrenzen (RM-622, `writer.tower_plates`,
Dialog und Export aus derselben Frage), und ein Wert im Band zwischen zwei
Schichten bekommt dort wie bei Cura die ganze Schicht vorgeschlagen, weil der
Slicer ihn nicht so druckt. Gemessen im ElegooSlicer mit PLA und PETG bei
0,08 mm: vorher 0,08 am PLA- und 0,16 am PETG-Teil (geschrieben 0,10 und
0,12), nachher an beiden 0,16 wie geschrieben, oben und unten. Für einen
eigenen Wert zwischen zwei Schichten sagt der Export die Rundung, statt still
zu runden, und dann nur das: Dass die eigene Höhe gilt, stimmt mit Turm nicht.

**Unter Bäumen ebenso** (RM-622): Am PETG-Drachen kamen die geschriebenen 0,28 mm
in keinem Programm an — alle Ebenen lagen auf dem 0,2-mm-Raster. Gegenprobe an zwei
gestützten Körpern aus PETG (`output/drache-2026-10-08/kontakt-stil`): Mit Gitter
druckten ElegooSlicer, OrcaSlicer, Bambu Studio, Creality Print, Anycubic Slicer
Next und PrusaSlicer 0,28 mit eigenen Zwischenebenen, mit organischen Bäumen alle
sechs 0,2 ohne eine. Bäume liegen auf den Schichten des Modells, auch mit
`independent_support_layer_height`; Solidon rät unter ihnen ganze Schichten, auch
unter „automatisch“, wenn der Herstellerprozess mit Bäumen stützt (Elegoo, Bambu),
und sagt bei einem eigenen Wert die Rundung. Bambu Studio, Creality Print, Anycubic
Slicer Next und PrusaSlicer druckten unter Bäumen auch keine untere Trennschicht
(unter Gitter druckten sie untere Lagen, unter Bäumen keine); in diesen vier
schlägt Solidon sie unter Bäumen nicht vor, ElegooSlicer und OrcaSlicer druckten
zwei und bekommen sie. Organisch heißt der Generator `TreeSupport3D`,
dessen Ebenen auf dem Raster des Modells liegen (`TreeSupportCommon.hpp:610` und
`:289`, gleich in Orca, Bambu, Creality und Anycubic); `tree_hybrid`, `tree_slim`
und `tree_strong` planen eigene Stützebenen (`TreeSupport.cpp:1756–1759`,
`:3349–3408`). Deshalb fragt `handover.organic_styles` den Stil des
Herstellerprozesses, und SuperSlicer, der statt Bäumen Gitter druckt, rundet nicht.
Ohne gefundenes Programm gilt die Familie der Datei: „Baum“ ist organisch, denn alle
sechs gemessenen Programme drucken ihn so, und eine ganze Schicht gilt unter jeder
Stütze genau. Gefragt wird mit der Art, mit der das Teil druckt
(`advise.printed_style`): Lehnt der Kunde den vorgeschlagenen Baum ab — im Dialog
abgewählt, im Export nicht übernommen —, druckt das Teil das Gitter der Platte, und
Abstand wie untere Trennschicht gelten ihm. Mit dem abgelehnten Baum gefragt, bekam
das Kinn bei Bambu Studio weder 0,28 mm noch eine untere Trennschicht. Ebenso fragt
der Dialog die Stützart gegen die Grundlage wie der Export, der einen übernommenen
Baum nur dem Teil gibt, das ihn verlangt; sonst verschwanden die Zeilen des Tischs,
sobald der Baum des Kinns übernommen war. Feldsatz und Rat lesen dieselbe Auskunft:
Leitete das Feld „organisch“ selbst her, sagte es unter `tree_hybrid` „gerundet“
neben einem Rat, der nicht rundete.

Der Schalter `independent_support_layer_height` richtet sich nach den
geschriebenen Abständen der Teile, die nicht unter organischen Bäumen drucken
(`handover.support_gaps_by_style`), nicht nach den Zielen aller Spulen; unter
Bäumen wirkte er nicht und wäre eine Abweichung vom Herstellerprofil ohne Grund.
Steht er gegen den Herstellerprozess, sagt es ein Befund: Die Stütze liegt dann
auch auf eigenen Höhen (0,47, 0,75, 1,02 mm statt nur auf denen des Modells). Cura
rechnet immer in ganzen Schichten, deshalb rät Solidon dort das Vielfache
innerhalb der Materialgrenzen — bei 0,08 mm Schicht für PLA zwei Schichten statt einer
unter dem Minimum —, und die Cura-Grundlage trägt es auch: Solidons 0,2 war
bei 0,28 und 0,12 mm Schicht keines, und jede Übergabe in Entwurf und Fein
warnte, auch ohne Stützen. Über mehrere Körper führt der Druckdialog den
Stützkontakt getrennt zusammen und fragt ihn wie der Export gegen die
Grundlage: Gegen die Übernahme gefragt, brachte jedes Übernehmen die
Gegenzeile (Tisch 0,2, Kinn 0,5 und zurück; PLA 0,15, PETG 0,21 und zurück),
und nach dem größten Wert verschwand die Zeile des PLA-Teils ganz. Ein vor
0.6.0 kalibriertes Material kennt die neuen Werte nicht und bekommt sie aus
dem mitgelieferten Eintrag, wie die Druckeinstellungen je Eintrag. Für TPU nennt
keine Quelle einen Abstand; ohne Werte bleibt er beim Hersteller.

**Über Baumspitzen zwei Schichten** (RM-584): Roberts Drache (PLA, CC2, 0,2 mm)
behielt an Kinn und Kopfstacheln Reste der Bäume. Jede der 64 Bartstacheln beginnt
als Insel von im Median 0,07 mm²; unter 1 mm² baut der Slicer an der Spitze keine
Trennschicht (`minimum_roof_area`, `TreeSupport3D.cpp:1151`), und die Spitze steht
eine Schicht unter dem Modell. Zwei Schichten Abstand senkten die Kontaktfläche
mit 0,2 mm Luft am Kinn von 59,4 auf 6,9 mm², an den Stacheln von 92,4 auf 3,6 mm²,
für eine Minute und 0,7 g; PrusaSlicer und Cura gleich. XY-Abstand, Astabstand,
Baumdichte, Trennschichtabstand und andere Baumarten halfen nicht; drei Schichten
ließen die Bartspitzen durchhängen können. An großen Decken fällt dafür die
Trennschicht weg — deshalb gilt der Abstand erst ab vielen solchen Inseln: An 165
Modellen hat der Drache 199, danach eine Baugruppe 49 und ein Schachturm 34;
die Schwelle steht bei 100.
Gemessen ist nur PLA (`support_tip_gap`); ohne Wert bleibt der Abstand des
Materials. Bericht: `output/drache-2026-10-09/rueckstaende/bericht.md`.

**Und jede Spitze mit Trennschicht** (RM-704): Der dritte Drache (0,4 mm oben,
volle Elegoo-Grundlage) hatte saubere Kopfstacheln, aber eine faserige,
durchhängende Kieferunterseite. Gemessen im G-Code (ElegooSlicer, Unterseite
x 106–137, y 92–118, z 84–99): Gegen den zweiten Druck (0,2 mm) trugen die
flachen Teile 22 statt 54 %, die schrägen Ränder 26 statt 34 %, und was trug,
stand 0,4 statt 0,2 mm darunter, auf nackten Spitzen (Trennschicht 2–5 %).
Astabstand, Astwinkel, XY-Abstand, Wände, Trennschichtlagen und -abstand und der
untere Abstand änderten am Kinn nichts; 0,2 oben stellte den zweiten Druck her
und mit ihm die Reste an den Stacheln (Kontakt 94 mm²). Eine Spitze, deren
Querschnitt `minimum_roof_area` übersteigt, erzwingt die Trennschicht an jeder
Spitze (`force_tip_to_roof`, `TreeSupport3D.cpp:1286`): Mit 1,13 mm (kleinster
solcher Wert auf Hundertstel) trug ein Viertel der Kieferunterseite eine
Trennschicht, der Kontakt an Kinn und Stacheln sank weiter (7,0 → 4,0 und
3,2 → 1,9 mm²), für fünf Minuten und 0,03 g; 1,2 und 1,4 mm wirkten gleich.
Getragen ist die flache Kieferunterseite damit kaum mehr (25 statt 22 %; im
zweiten Druck 54 %): Was trägt, liegt auf Trennschicht und haftet weniger an, ob
das Kinn nicht mehr durchhängt, zeigt erst Druck 4. Die Kosten: 49 statt 31
Stützfüße auf dem Modell (14,3 statt 8,5 mm²), neue am Kopf auf 105–112 mm, an Hals
und Brust und drei sehr kleine an den Vorderbeinen auf etwa 21 mm.
PrusaSlicer und Cura führen eigene Spitzenschlüssel, geschnitten ist dort nichts.
Das Vorderbein, das beim Abnehmen brach, hatte kaum mehr Stütze als im zweiten
Druck (Umfang mit Stütze in 1 mm 2 gegen 3–5 %, mit der Spitze 0,2 mm² Auflage),
aber zwei statt drei Wände; daraus wird kein Rat, solange ein Bruch die einzige
Messung ist.
Bericht: `.claude/.state/drache-2026-10-08/berichte-2026-10-10/drache3.md`.
