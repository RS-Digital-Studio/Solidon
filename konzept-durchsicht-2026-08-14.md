# Durchsicht — Funktionen, Wörter und der kürzeste Weg zum geteilten Teil

Eine vollständige Durchsicht der Oberfläche mit einer einzigen Frage im Kopf:
**Wer das hier zum ersten Mal öffnet und ein Teil trennen will — kommt der
an?** Gemessen am gebauten Fenster, nicht am Quelltext: 128 Menüzeilen in drei
Szenenzuständen ausgelesen, alle 84 Operationen mit Titel, Menüweg und
Beschreibungssatz aufgelistet, die Werkzeugzeile Knopf für Knopf, und die neue
Leiste in drei Zuständen gerendert und **angesehen**.

Zwei der Befunde unten stammen aus genau diesem Ansehen und wären am
Quelltext nie aufgefallen.

> **Stand 14.08.2026.** Alles unter „Behoben" ist umgesetzt und hat einen
> Test. Alles unter „Offen" ist gemessen und mit Absicht liegen geblieben —
> mit dem Grund daneben.

---

## Teil 0 — Was bei solchen Programmen gefordert, gelobt und kritisiert wird

Vor der eigenen Meinung die fremde. Drei Recherchen, und sie zeigen ein
erstaunlich einheitliches Bild.

**Gelobt wird Einfachheit, und zwar ausschließlich.** Tinkercad wird für seine
Oberfläche gelobt und für nichts sonst; die Kritik daran ist immer dieselbe —
es kann zu wenig. Fusion 360 wird für seinen Umfang gelobt und für seine
Lernkurve kritisiert. Die Empfehlung, die in fast jedem Vergleich steht, lautet
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
| Werkzeug | achter Umschalter der Werkzeugzeile, Symbol `split` |
| Geste | zwei Punkte auf dem Teil; der dritte Klick fängt von vorn an |
| Ebene | die Linie plus die Blickrichtung — der Schnitt geht gerade in den Bildschirm hinein |
| Verbindung | vorgewählt: Stifte in der einen Hälfte, Löcher in der anderen |
| Ergebnis | eine Transaktion, ein Undo — plus ein Passungspaar je Stift (§14) |

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

### Was das Werkzeug nicht kann, und warum

**Der Schnitt ist eine Ebene, keine Kurve.** Die Linie legt fest, wo und wie
schräg getrennt wird; von dort läuft die Ebene gerade durch das Teil. Um eine
Rundung herum zu trennen hieße, eine Freiformfläche zu erzeugen, sie
wasserdicht zu schließen und beide Hälften daran zu schneiden — das ist ein
eigenes Stück Arbeit und kein Nebenprodukt. Der Vorbehalt steht am
Registereintrag und damit im Dialog, im Handbuch und beim Agenten.

**Nur Stifte, keine Schwalbenschwänze und keine Schnapper.** Die Slicer bieten
drei Formen; hier ist eine umgesetzt, und zwar die, die als einzige beiden
Hälften eine ebene Auflage lässt. Schwalbenschwanz und Schnapper sind eine
Erweiterung des Parameters, keine zweite Operation — sie stehen in der Roadmap.

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

## Teil 4 — Offen, mit Grund

**4.1 Drei Menüeinträge für einen Schnitt.** *An Ebene teilen*, *Teilen und
verstiften* und *An gezeichneter Linie trennen* stehen nebeneinander, und der
erste ist der zweite mit `pins = 0`. Das Hausprinzip sagt „eine Operation je
Handlung, nicht je Variante", und das Werkzeug dafür gibt es: `MENU_TWINS`
nimmt einem Zwilling den Menüeintrag und lässt ihn über Palette und Verlauf
erreichbar. Nur ist dieses Werkzeug **fest auf B-Rep verdrahtet** — es hängt an
jeden Zwilling einen Haken „Exakter Körper (B-Rep)", und `menu_path` schreibt
„(Umschalter „Exakt")" hinter den Weg. Für das Paar hier wäre beides gelogen.

Der saubere Weg ist, `MENU_TWINS` von der Beschriftung zu trennen, statt einen
dritten Fall hineinzudrücken. Das ist eine eigene Änderung mit eigenem Test,
und sie gehört nicht in denselben Commit wie ein neues Werkzeug. **In der
Roadmap.**

**4.2 Sechs Kürzel auf 84 Operationen**, und die Werkzeuge der unteren Leiste
haben keines. Steht seit zwei Durchsichten offen und ist es weiter: Kürzel
vergibt man einmal und vollständig, nicht acht auf einmal. `Ctrl+B`, `Ctrl+D`,
`Ctrl+R`, `Ctrl+T`, `Del`, `F2` — mehr ist es nicht.

**4.3 Der Objektbaum nennt die Hälften „A" und „B".** Nach dem Verstiften trägt
die eine die Stifte und die andere die Löcher, und genau das würde beim
Zusammenbau helfen. Betrifft aber `split_pinned` und Auto Split mit, also auch
eingecheckte Beispielprojekte und die Tour — eine Umbenennung mit Folgen, keine
Zeile.

**4.4 Ein Passungspaar entsteht auch dann, wenn die Schnittfläche für Stifte
zu klein war.** `plan_pins` meldet das sauber als Befund und setzt keine
Stifte; das Dokument bekommt trotzdem seine `Fit`-Einträge, weil an dieser
Stelle noch niemand weiß, was die Auswertung daraus macht. Bestand seit Auto
Split, nicht neu — und mit dem gezeichneten Trennen jetzt an einer zweiten
Stelle. Gehört zusammen behoben.

**4.5 Drei Namen für benachbarte Dinge**: „Chat einrichten" (Erststart),
„Zugang zum Sprachmodell" (Menü), „Fernsteuerung über MCP" (Einstellungen).
Steht aus der Erstnutzer-Durchsicht offen und ist es geblieben.

---

## Teil 5 — Was die Durchsicht entlastet hat

Gezielt gesucht und nicht gefunden — steht hier, weil es dieselbe Arbeit
gekostet hat.

**Jede der 84 Operationen hat einen Beschreibungssatz**, und keiner davon
erklärt den Namen; sie erklären die Wirkung. Der vollste Dialog hat acht Felder
auf der Vorderseite (`label_text`), die Grenze liegt bei acht. Kein Parameter
ohne `doc`.

**Die Menüs grauen vorbildlich aus.** Auf der leeren Szene ist unter *Ändern*
keine Zeile anklickbar, *Objekt* ist ganz aus, und die Werkzeugzeile folgt
derselben Regel — der achte Umschalter von selbst mit, weil `set_usable` alle
nimmt.

**Die Sprachkataloge sind vollständig geblieben.** 26 neue Texte für das
Trennwerkzeug, vier geänderte Menütitel, drei verwaiste Einträge entfernt —
alle fünf Sprachen, geprüft in beide Richtungen.

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
