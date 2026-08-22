# Durchsicht — Funktionen, Wörter und der kürzeste Weg zum geteilten Teil

Eine vollständige Durchsicht der Oberfläche mit einer einzigen Frage im Kopf:
**Wer das hier zum ersten Mal öffnet und ein Teil trennen will — kommt der
an?** Gemessen am gebauten Fenster, nicht am Quelltext: 128 Menüzeilen in drei
Szenenzuständen ausgelesen, alle 84 Operationen mit Titel, Menüweg und
Beschreibungssatz aufgelistet, die Werkzeugzeile Knopf für Knopf, und die neue
Leiste in drei Zuständen gerendert und **angesehen**.

Zwei der Befunde unten stammen aus genau diesem Ansehen und wären am
Quelltext nie aufgefallen.

> **Nachgezählt am 19.08.2026.** Beide Zahlen oben sind Messwerte vom 14.08.
> und keine Invarianten. Die Menüleiste hat allein auf der leeren Szene 136
> anklickbare Zeilen (dazu 32 Untermenüs, zusammen 168 Einträge), und das
> Register zählt **85** Operationen statt 84 — 68 statische plus 17, die
> `app/core/knowledge/parts/ops.py` je Baustein als `insert_<name>` erzeugt.
> Die 85. kam mit dem Schnappverbinder aus Teil 4 (33031da) noch am Abend des
> 14.08. dazu; `git show 33031da^` zählt 84, `git show 33031da` zählt 85. Wer
> die Zahl zitiert, zitiert einen Stichtag: Mit jedem Baustein steigt sie.

> **Stand 14.08.2026, nachrecherchiert am 19.08.2026.** Alles unter „Behoben"
> ist umgesetzt und hat einen Test. Alles unter „Offen" ist gemessen und mit
> Absicht liegen geblieben — mit dem Grund daneben. Was die Nachrecherche
> berichtigt hat, steht als Blockzitat unter der jeweiligen Stelle; die
> Zusammenfassung am Dateiende.

---

## Teil 0 — Was bei solchen Programmen gefordert, gelobt und kritisiert wird

Vor der eigenen Meinung die fremde. Drei Recherchen, und sie zeigen ein
erstaunlich einheitliches Bild.

**Gelobt wird Einfachheit, und zwar ausschließlich.** Tinkercad wird für seine
Oberfläche gelobt und für nichts sonst; die Kritik daran ist immer dieselbe —
es kann zu wenig. Autodesk Fusion (bis 2023 als *Fusion 360* geführt; der
Hersteller nennt es heute durchgehend Autodesk Fusion) wird für seinen Umfang
gelobt und für seine Lernkurve kritisiert. Die Empfehlung, die in fast jedem
Vergleich steht, lautet
sinngemäß: *fang mit dem Einfachen an und wechsle, wenn es nicht mehr reicht*.
Das ist genau die Lücke, in die Solidons gestufte Tiefe zielt — vorn zwei
Felder, hinten alles.

**Kritisiert wird die Reparatur.** Nicht-mannigfaltige Kanten sind der
häufigste Grund, warum ein Modell nicht druckt, und die Klage ist nie „das
Werkzeug fehlt", sondern „ich musste dafür in ein anderes Programm". Ein Modell,
das auf dem Bildschirm gut aussieht und im Slicer Fehler wirft, wird vom Nutzer
dem Drucker zugeschrieben. Solidon meldet das im Prüfbericht — das ist die
richtige Antwort, und sie war schon da.

**Gefordert wird das Trennen mit Verbindern.** Der Cut-Tool mit *Plug*, *Dowel*
und *Snap* ist in Bambu Studio, OrcaSlicer, Creality Print und PrusaSlicer
Standard; die Foren diskutieren nicht mehr *ob*, sondern welche Dübelform man
nimmt (rund, dreieckig, sechskant — die Kantigen erzwingen eine Lage). Wer ein
Teil teilt, will es hinterher zusammenstecken, und zwar ohne dafür modellieren
zu müssen.

Genau dort setzt der Hauptteil dieser Durchsicht an.

Quellen: [Prusa Knowledge Base — Cut tool](https://help.prusa3d.com/article/cut-tool_1779) ·
[PrintPal — Connect 3D prints in your slicer](https://printpal.io/resources/connect-3d-prints-without-modelling-in-10-seconds) ·
[Bambu Lab Forum — Using dowels and connectors](https://forum.bambulab.com/t/using-dowels-and-connectors-for-large-prints/128276) ·
[3dprinting.com — STL repair software](https://3dprinting.com/software-guides/stl-repair-software/) ·
[Shapr3D — Easiest CAD software](https://www.shapr3d.com/content-library/easiest-cad-software-to-learn)

---

## Teil 1 — Behoben: das Trennen entlang einer gezeichneten Linie

Vorher gab es drei Wege, ein Teil zu teilen, und **keiner davon ging über das
Bild**: *An Ebene teilen* und *Teilen und verstiften* wollen einen
Achsenbuchstaben und eine Zahl, *Automatisch teilen* sucht selbst. Wer weiß,
**wo** getrennt werden soll — und das weiß man, wenn man das Teil ansieht —,
musste diese Stelle in eine Koordinate übersetzen.

Jetzt: **Werkzeugzeile → Trennen → zwei Klicks → Jetzt trennen.**

| | |
|---|---|
| Werkzeug | siebter Umschalter der Werkzeugzeile, Symbol `split`, `Alt+7` |
| Geste | zwei Punkte auf dem Teil; der dritte Klick fängt von vorn an |
| Ebene | die Linie plus die Blickrichtung — der Schnitt geht gerade in den Bildschirm hinein |
| Verbindung | vorgewählt: Stifte in der einen Hälfte, Löcher in der anderen |
| Ergebnis | eine Transaktion, ein Undo — Passungen inbegriffen (§14) |

> **Hier stand „achter Umschalter", und das war schon am 14.08. falsch.**
> `main_window` meldet die Werkzeuge in der Reihenfolge `section · measure ·
> transform · analysis · layers · explode · split · paint` an
> (`app/ui/main_window.py:894–990`), und `ToolStrip.add` hängt jeden Knopf
> ans Ende (`app/ui/tool_strip.py:185`). `split` ist der **siebte**, `paint`
> der achte; die Kürzel vergibt `enumerate(..., start=1)`
> (`main_window.py:807`), also `Alt+7`. Das Handbuch hatte recht und dieses
> Dokument unrecht — „Werkzeug *Trennen* unten in der Werkzeugzeile (Alt+7)"
> steht so in `app/core/manual.py` und in allen fünf Katalogen.
> `git show 49d4c73:app/ui/main_window.py` — der Commit, der das Werkzeug
> **und** dieses Dokument anlegt — zeigt dieselbe Reihenfolge. Derselbe
> Fehler steht in `ROADMAP.md:5511`.

> **Und die Passungen liefen damals an der Transaktion vorbei.** Der Satz
> „ein Undo — plus ein Passungspaar je Stift" stimmte am 14.08. nicht: Die
> Paare wurden nach dem Aufruf ins Dokument geschrieben, ein Undo nahm die
> Teilung zurück und ließ sie stehen. Behoben am 15.08. mit `5f5cfd4` über
> `History.apply(..., changes=ChangeFn)`
> (`app/core/scene/history.py:206–226`) — seitdem stimmt er.
>
> „Je Stift ein Paar" gilt inzwischen mit zwei ausgewiesenen Ausnahmen: Wird
> ein schon geschnittenes Stück erneut geteilt, entfallen die geerbten Paare
> mit dem Hinweis `split.fit_dropped` (`app/core/split.py:212,280,305`); und
> wo hinter der Naht zu wenig Material steht, entstehen gar keine Stifte —
> `plan_pins` misst die Tiefe und meldet `split.seam_too_thin` (`52826ef`,
> 15.08.).

**Die Verbindung ist vorgewählt, nicht versteckt.** Zwei geklebte Hälften ohne
Stifte muss jemand von Hand in Deckung halten, während der Kleber greift; das
ist die Arbeit, die dieses Werkzeug abnehmen soll. Der Haken lässt sich
herausnehmen — das ist ein Handgriff weniger, als ihn zu suchen.

**Die Kamera steht nicht im Stapel.** Die Blickrichtung wird einmal gelesen,
wenn der Knopf gedrückt wird, und was in die Operation geht, sind Zahlen: eine
Ebene aus Normale und Lage. Eine Op, die die Kamera läse, gäbe beim zweiten
Auswerten ein anderes Teil (§11.2). Ein Test hält das fest.

**Die Stifte stehen senkrecht auf der Schnittfläche.** Das war der eigentliche
Aufwand: Die Verstiftung rechnete bis dahin mit einem Achsenbuchstaben, weil
Auto Split nur achsparallele Ebenen legt. Auf einer 45-Grad-Fläche steht ein so
aufgestellter Stift schief in seiner eigenen Bohrung. `plan_pins` und
`add_pins` nehmen jetzt eine Ebene statt einer Achse; gedreht wird mit
derselben Matrix wie der Schnitt, nur invertiert — drei Sonderfälle für drei
Achsen sind weggefallen, statt einen vierten zu bekommen.

Gemessen: 11 Geometrietests (Ebene aus zwei Punkten, schiefer Schnitt gegen
das analytische Volumen, Stiftachse gleich Ebenennormale, zweimal gerechnet
gleich) und 15 Oberflächentests am gebauten Fenster.

> **Nachgezählt am 19.08.2026: 28 und 34.** Die Zahlen oben sind der Stand
> des ersten Commits (`49d4c73`) und waren noch am selben Tag überholt
> (`33031da`: 25 und 25). Heute zählt `--collect-only`: 28 in
> `tests/test_split_line.py`, 25 in `tests/test_split_tool.py`, 9 in
> `tests/test_split_ui.py`.

### Was das Werkzeug nicht kann, und warum

**Der Schnitt ist eine Ebene, keine Kurve.** Die Linie legt fest, wo und wie
schräg getrennt wird; von dort läuft die Ebene gerade durch das Teil. Um eine
Rundung herum zu trennen hieße, eine Freiformfläche zu erzeugen, sie
wasserdicht zu schließen und beide Hälften daran zu schneiden — das ist ein
eigenes Stück Arbeit und kein Nebenprodukt. Der Vorbehalt steht am
Registereintrag und damit im Dialog, im Handbuch und beim Agenten.

**Drei Formen, kein Schnapper.** Rund, Sechskant und Schwalbenschwanz stehen
als Querschnitt zur Wahl, in der Leiste direkt neben der Stiftzahl. Der
Schnapper fehlt mit Absicht: Er ist kein Querschnitt, sondern ein federnder Arm
— siehe Teil 4.

> **Dieser Absatz widerspricht Teil 4 desselben Dokuments, und Teil 4 hat
> recht.** Der Schnapper ist gebaut, im selben Commit wie dieses Dokument
> (`33031da`, 14.08.2026): `CONNECTOR_SHAPES = ("round", "hex", "dovetail",
> "snap")` (`app/core/geom/prepare_ops.py:74`), die Leiste bietet alle vier
> an (`app/ui/split_bar.py:108–111`), das Handbuch listet vier Punkte. Der
> Kommentar über der Liste beantwortet genau den Einwand oben: „Der
> Schnapper ist kein Querschnitt … er steht hier trotzdem in derselben
> Liste, weil er für den Nutzer dieselbe Entscheidung ist."
>
> Es sind also **vier Verbinder**: drei Querschnitte und ein Mechanismus mit
> eigenem Baustein. Der braucht eine Naht von mindestens 5,4 mm, sonst wird
> rund daraus (`split.snap_too_small`).
>
> *Nebenbefund im Code:* Der Docstring von `PinPlan.shape`
> (`app/core/geom/pins.py:111`) nennt weiterhin nur „``round``, ``hex`` oder
> ``dovetail``", obwohl `plan_pins` „snap" verarbeitet (`:205`).

---

## Teil 2 — Behoben: zwei Fehler, die man nur im Bild sieht

Beide sind beim Rendern der neuen Leiste aufgefallen, nicht beim Lesen des
Quelltexts. Der zweite betrifft das ganze Programm.

### 2.1 Auf dem Hauptknopf stand „etzt trenne"

Das Stylesheet zeichnet `QPushButton:default` mit `font-weight: 600`, also
halbfett. Qt rechnet die bevorzugte Breite aber aus der **normalen** Schrift
des Widgets. Gemessen:

| | „Jetzt trennen" |
|---|---|
| Textbreite normal | 77 px |
| Textbreite halbfett | 89 px |
| `sizeHint().width()` | 104 px |
| verfügbar in der Leiste | 104 px |

104 minus Innenabstand ist weniger als 89 — vorn und hinten ein Buchstabe ab.
In einem Dialog fällt das nie auf, weil dort jeder Knopf mehr Platz bekommt,
als er verlangt; in einer engen Leiste bekommt er genau seine bevorzugte
Breite.

Behoben an einer Stelle: `style.make_primary()` setzt `setDefault(True)` **und**
die halbfette Schrift am Widget, damit die Breitenrechnung sie kennt. Alle
sieben Hauptknöpfe der Anwendung gehen jetzt darüber; ein Test misst gegen die
Schrift, mit der wirklich gezeichnet wird, ein zweiter verbietet
`setDefault(True)` außerhalb von `style.py`. Der Knopf ist danach 115 px breit.

Die andere Möglichkeit wäre gewesen, das Fett zu streichen. Sie ist die
schlechtere: Fett ist neben der Akzentfarbe die zweite Kodierung dafür, welcher
Knopf der Hauptknopf ist (Regel 18).

### 2.2 Die Sternchen standen als Sternchen da

Der Hinweis lautete „*Jetzt trennen* schneidet das Teil dort durch" — als
Hervorhebung gemeint, als Sternchen gezeichnet. Die Leiste zeigt reinen Text.
Jetzt stehen dort Anführungszeichen.

---

## Teil 3 — Behoben: vier Wörter, an denen ein Anfänger hängen bleibt

Alle vier sind Menüzeilen, also das, was jemand liest, **bevor** er etwas
weiß. Der Bezeichner bleibt in allen vier Fällen unverändert; geändert ist die
Zeile im Menü, und die fünf Sprachkataloge ziehen mit.

| vorher | jetzt | warum |
|---|---|---|
| *Boolesch* | **Verbinden und Abziehen** | Richtig, üblich — und genau die Sorte Wort, an der hängen bleibt, wer zum ersten Mal zwei Körper zusammenfügen will |
| *Druckvorbereitung* | **Teilen und Anpassen** | Stand als Untermenü unter der Gruppe *Vorbereiten*: zwei Ebenen, fast dasselbe Wort |
| *Dezimieren* | **Dreiecke verringern** | Der Fachbegriff sagt dem nichts, der ein zu großes Netz vor sich hat |
| *Muster* | **Kopien in Reihe oder Kreis** | *Textur aufbringen* hat einen Parameter „Muster", und der meint Rändel und Wabe — dasselbe Wort für zwei Sachen |

### Und ein Eintrag ist umgezogen

*Automatisch teilen …* stand unter **Bearbeiten**, zwei Menüs entfernt von den
anderen Wegen, ein Teil zu trennen. Es steht dort, weil es technisch kein
Registereintrag ist, sondern ein Ablauf über mehreren Operationen — eine
Einteilung nach der Bauart der Funktion, nicht danach, wonach jemand sucht. Es
steht jetzt unter **Vorbereiten**, unter einem Trennstrich, direkt unter
*Teilen und Anpassen*. Wer ein zu großes Teil hat, findet dort alle vier Wege
beieinander.

---

## Teil 4 — Die offenen Punkte, und was aus ihnen wurde

Alle fünf sind abgearbeitet; die ausführliche Version steht in der Roadmap.

**4.1 Drei Menüeinträge für einen Schnitt** — behoben. `MENU_TWINS` hing an
einer festen Beschriftung („Exakter Körper (B-Rep)") und taugte damit für
nichts als die zwei Rechenkerne. Die Beschriftungen liegen jetzt in
`TWIN_TOGGLES`; wer dort fehlt, bekommt keinen Haken, sondern hat einen Wert im
Dialog des Partners. *An Ebene teilen* lebt seither unter *Teilen*, mit der
Null im Feld *Passstifte*.

**4.2 Sechs Kürzel auf 84 Operationen** (heute 85) — die acht Werkzeuge haben
jetzt `Alt+1` bis `Alt+8`. Für die Operationen selbst bleibt es bei sechs; das
ist eine Vergabe in einem Zug und keine Nebenarbeit.

**4.3 Die Hälften hießen „A" und „B"** — behoben, sie heißen jetzt
„… A · Stifte" und „… B · Löcher".

**4.4 Ein Passungspaar ohne Stifte** — behoben, an beiden Stellen. Die Zahl der
Paare kommt aus derselben Planung, die die Operation gleich noch einmal macht.

**4.5 Drei Namen für benachbarte Dinge** („Chat einrichten", „Zugang zum
Sprachmodell", „Fernsteuerung über MCP") — behoben. Die ersten beiden waren
**derselbe Dialog**: `KeyDialog`, auf dem Erstlaufbildschirm als *Chat
einrichten* angeboten und im Menü als *Zugang zum Sprachmodell*. Wer den einen
gesehen hatte, suchte den anderen nicht. Geblieben ist der Name, der die Sache
aus Sicht des Nutzers nennt — er sieht den Chat, nicht das Modell dahinter —
und der beide Wege aus §27 trägt: Ein Schlüssel *und* ein lokales Ollama sind
zwei Arten, den Chat zum Laufen zu bringen.

Der dritte ist etwas anderes und heißt deshalb weiter *Fernsteuerung*; die
Zeile darunter („Port der Fernsteuerung") und das Handbuchkapitel tragen
denselben Namen, und ein neues Wort hier hätte einen Namensbruch behoben und
den nächsten angelegt. Geändert ist, was fehlte: „über MCP" nannte das
Protokoll, nicht den Handelnden. Jetzt steht dort *Fernsteuerung durch andere
Programme zulassen (MCP)*. Die ausführliche Version — „Solidon von anderen
Programmen auf diesem Rechner fernsteuern lassen" — sagte nicht mehr und zog
den Dialog auf Französisch von 566 auf 768 Bildpunkte; gemessen, dann
verworfen.

**Und einer blieb bewusst offen — bis ich ihn nachgerechnet habe:** der
Schnapper. Er stand hier mit drei Gründen, und zwei davon haben eine Messung
nicht überlebt. Der Hinterschnitt in der Gegenseite ist keine Überhangfläche,
über die ein Baustein etwas sagen müsste, sondern eine Brücke von 0,9 mm — die
legt jeder Drucker, und mit der Naht nach unten gibt es gar keinen Überhang.
Und die Federkraft wird nicht geraten: zehn zu eins ist das Verhältnis aus
Länge zu Armstärke, und es stand als `SNAP_RATIO` längst im Repository.

Was blieb, ist der Grund, der ihn zum eigenen Baustein macht und nicht zu einem
Wert in der Formliste: Rund, Sechskant und Schwalbenschwanz sind Querschnitte,
der Schnapper ist ein Paar aus Federarm und Tasche. Er ist jetzt genau das —
`snap_connector`, der vierzehnte Baustein. Die echte Grenze ist eine Zahl: Aus
zehn zu eins und zwei Außenwänden folgen 8 mm Mindestlänge, und die Naht muss
5,4 mm hergeben. Darunter wird rund daraus, und der Prüfbericht sagt warum.

## Teil 5 — Was die Durchsicht entlastet hat

Gezielt gesucht und nicht gefunden — steht hier, weil es dieselbe Arbeit
gekostet hat.

**Jede der 84 Operationen hat einen Beschreibungssatz** (heute 85), und keiner
davon erklärt den Namen; sie erklären die Wirkung. Der vollste Dialog hat acht
Felder auf der Vorderseite (`label_text`), die Grenze liegt bei acht. Kein
Parameter ohne `doc`. Am 19.08.2026 nachgeprüft: alles drei gilt weiter.

**Die Menüs grauen vorbildlich aus.** Auf der leeren Szene ist unter *Ändern*
keine Zeile anklickbar, *Objekt* ist ganz aus, und die Werkzeugzeile folgt
derselben Regel — jeder Umschalter geht von selbst mit, weil `set_usable` alle
nimmt.

**Die Sprachkataloge sind vollständig geblieben.** 26 neue Texte für das
Trennwerkzeug, vier geänderte Menütitel, drei verwaiste Einträge entfernt —
alle fünf Sprachen, geprüft in beide Richtungen.

---

## Teil 6 — Der eigene Änderungssatz im Review

Nach dem Bauen dasselbe noch einmal, diesmal am fertigen Diff: 46 Dateien
gelesen wie fremder Code. Neun Funde, alle behoben, jeder mit einem Test.

**Ein Fehler steckte in der Methode.** Ich hielt den Diff gegen `main` — und
`main` liegt hinter dem Stand, auf dem diese Arbeit aufgesetzt hat. Ich las
also Änderungen einer Nebensitzung als meine und hätte sie beinahe „behoben".
Verglichen wird gegen den eigenen Ausgangspunkt, nicht gegen den Zweig, in den
es später geht.

**Die kantigen Verbinder waren größer, als sie sagten.** `hexagon()` nimmt die
Schlüsselweite, `dovetail()` die breite Seite; beide bekamen den Durchmesser
roh durchgereicht. Bei 6 mm maß der Sechskant 6,93 Umkreis, der
Schwalbenschwanz 8,49 — dessen Ecke allein nahm 1,24 mm von den 1,6 mm
Wandreserve, die die Stiftplanung stehen lassen wollte. Wer einen dickeren
Verbinder will, soll den Durchmesser erhöhen und ihn nicht durch die Formwahl
geschenkt bekommen.

**Eine Zusage im Docstring, die der Code nicht hielt.** `fitting_pins()` gab
ohne Netz null zurück, versprochen war die gewünschte Zahl. Null heißt hier
„keine Passung eintragen" — eine stillschweigend falsche Antwort statt einer
offenen Frage.

**Eine Begründung, die eine Messung nicht überlebt hat.** Im Kommentar stand,
ein Kürzel ohne Modifikator feuere auch beim Tippen im Chat. `QTest.keyClick`
gegen ein fokussiertes Eingabefeld sagt: tut es nicht. Der Grund für
`Alt+Ziffer` bleibt, aber er ist ein anderer — die nackten Ziffern gehören der
Darstellung, `Ctrl` und Ziffer den Kameras.

**Zwei Fehler an den Namen der Hälften.** `half_names()` schnitt am letzten
„ · " ab und warf alles dahinter weg: aus „Halter · Version 2" wurde
„Halter A · Stifte". Und `split_plane` ging an der Funktion vorbei, stapelte
also beim zweiten Teilen „… A · Stifte A". Abgeschnitten wird jetzt nur, was
einer der eigenen Zusätze ist — in der Quelle wie in jedem der fünf Kataloge,
sonst verlöre ein auf Spanisch geteiltes und auf Deutsch weitergeteiltes
Projekt die Regel.

**Und vier Kleinigkeiten**, die einzeln nichts wiegen und zusammen die
nächste Durchsicht in die Irre schicken: ein Docstring, der ein Kreuz
beschrieb, wo eine Kugel gezeichnet wird; Enden ohne `name`, also nicht
einzeln abräumbar; derselbe Umschaltertext zweimal wörtlich im Register; und
eine Menüsuche über den *übersetzten* Gruppentitel, die auf Deutsch
funktioniert und sonst nirgends.

---

## Was gemessen wurde

`build_application([])` mit umgebogenen Nutzerverzeichnissen, dazu
`load_operations()` von Hand — ohne das baut sich ein Fenster mit elf statt 84
Operationen auf, und das ist die Falle, in die diese Durchsicht als Erstes
gelaufen ist. Ausgelesen: die Menüleiste vollständig mit Zustand und Kürzel je
Zeile, die Werkzeugzeile mit Hinweistext, das Register mit Titel, Menüweg,
Beschreibung, Vorbehalt und der Zahl der Felder je Dialogseite. Gerendert und
angesehen: die Trennleiste in drei Zuständen, der Hauptknopf einzeln gegen
einen gewöhnlichen. Gefahren: die vollständige Suite, Datei für Datei.

Nicht gemessen: das laufende Fenster als Bild. Der Container hier bringt VTK
und die Offscreen-Plattform nicht zusammen — `window.grab()` über dem
OpenGL-Fenster bricht ab, und zwar auch auf dem unveränderten Stand. Was
davon abhängt, steht in dieser Durchsicht nicht.

**Für Teil 6** kam dazu: der Umkreis der drei Verbinderformen an gebauten
Netzen gemessen, das Kürzelverhalten mit `QTest.keyClick` gegen ein
fokussiertes Eingabefeld nachgestellt, und die zwei Testdateien, die in diesem
Container abbrechen, gegen einen Worktree auf dem unveränderten Ausgangsstand
gehalten — sechs Läufe hier, sechs dort. Sie brechen dort genauso ab.

---

## Nachrecherchiert am 19.08.2026

Fünfzehn Aussagen dieses Dokuments über den eigenen Code nachgeprüft, gegen
`main` (b0415d6), 103 Commits nach dem Stand vom 14.08.: **acht stimmen, vier
sind überholt, zwei waren schon damals falsch, eine ist nicht mehr prüfbar.**

**Die beiden Fehler von Anfang an** — beide in Teil 1, beide von Teil 4
desselben Dokuments widerlegt:

- Das Trennwerkzeug ist der **siebte** Umschalter (`Alt+7`), nicht der achte.
  Das Handbuch sagte es die ganze Zeit richtig. Derselbe Fehler steht in
  `ROADMAP.md:5511`.
- „Drei Formen, kein Schnapper" — es sind **vier**, und der Schnapper kam im
  selben Commit wie dieses Dokument.

**Was die Zeit überholt hat:** die 84 Operationen (heute 85 — die 85. kam noch
am Abend des 14.08. mit dem Schnappverbinder), die 128 Menüzeilen (136 allein
auf der leeren Szene), die Testzahlen 11 und 15 (heute 28 und 34), und die
Zusage „ein Undo — plus ein Passungspaar je Stift": Die Passungen liefen am
14.08. an der Transaktion vorbei und wurden erst am 15.08. hineingezogen.

**Was unverändert gilt:** kein Registereintrag ohne `doc`, kein Parameter ohne
`doc`, `label_text` als vollster Vorderseiten-Dialog mit acht Feldern, die
Kamera außerhalb des Stapels, `plan_pins` mit Ebene statt Achse, die
ausgrauenden Menüs, `style.make_primary()` mit sieben Hauptknöpfen.

**Ein Nebenbefund im Code:** Der Docstring von `PinPlan.shape`
(`app/core/geom/pins.py:111`) kennt den Schnapper nicht, obwohl `plan_pins`
ihn verarbeitet.

**Zur Außenwelt** hat dieses Dokument wenig zu sagen, und das wenige stimmt
weiter: Tinkercad wird für seine Einfachheit gelobt und für seinen Umfang
kritisiert, Fusion umgekehrt. Ein Name hat sich geändert — *Fusion 360* heißt
seit 2023 **Autodesk Fusion**; im Text oben ist er nachgezogen.
