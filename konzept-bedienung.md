# Konzept — Bedienung, Gestaltung und Zeichnen

Aus einem Lauf am echten Programm, 4. August 2026. Gestartet über
`app.ui.app`, bedient über Maus und Tastatur; kein Aufruf über die API. Zum
Vergleich lief Autodesk Fusion daneben, weil das die Anwendung ist, aus der
die meisten Nutzer kommen.

**Durchgegangen:** Erstinbetriebnahme · Wiederherstellung · Startbildschirm ·
alle acht Menüs samt Untermenüs · Viewport in zwei Navigationsschemata ·
Objektbaum, Parameterleiste, Verlauf, Prüfbericht, Chat · alle sieben
Werkzeuge der Viewportleiste · Analysekarten · Schichtenvorschau ·
Bohrung setzen · Formschräge · Bausteinkatalog mit Suche und Einfügen ·
Grundformen · Kollisionsprüfung · Skizzeneditor · Parameter · Varianten ·
Material kalibrieren · Automatisch teilen · Modell erzeugen ·
Druckeinstellungen · Einstellungen · Zusätzliche Programme · Export ·
Tastenkürzel · Über · helles und dunkles Thema · Handbuch ·
**alle sieben Beispielprojekte mit ihren Touren**.

Alles unten ist nachgestellt, nicht abgeleitet. Wo etwas nur teilweise stimmt
oder sich nicht wiederholen ließ, steht das dabei.

---

## Teil 1 — Die drei Befunde, aus denen fast alles andere folgt

### 1.1 Der Viewport nimmt keine Klicks entgegen

Das Vorgabeschema heißt „Wie in Cura — links wählt, rechts dreht". Das
Handbuch schreibt auf der Seite *Das Fenster* wörtlich: „Linke Maustaste wählt
aus". Getestet über zwei verschiedene Eingabewege, beide sauber zugestellt —
der Beweis: nach Umstellung auf „Wie im CAD" dreht derselbe Zug die Kamera.

| Handlung | erwartet | tatsächlich |
|---|---|---|
| Klick auf den Körper | Objekt ausgewählt | „Keine Auswahl" |
| Klick auf eine Bohrung, Merkmale eingeblendet | Merkmal ausgewählt | nichts |
| Zwei Klicks bei „Abstand messen" | Bemaßung | keine Zahl, keine Linie |
| Rechtsklick auf einen Körper | Kontextmenü | nichts |

In `viewport.py:1240` steht der Grund offen: `_left_down` kehrt im
slicer-Schema mit einem `return` zurück, der Kommentar daneben sagt „Left
selects". Das Auswählen wurde nie angeschlossen. Picking läuft überhaupt nur,
wenn Messen, Bemalen oder die Merkmalsüberlagerung aktiv sind — und selbst
dann kommt keine Auswahl zustande.

§18.5 nennt das Zeigen auf ein Merkmal „die wichtigste Einzelfunktion": *der
Nutzer muss nicht wissen, dass eine Bohrung `hole_3` heißt — er zeigt darauf.*
Genau das geht nicht. Auswählen geht ausschließlich über den Objektbaum.

**Die Folge zieht sich durch alles.** Weil man nicht zeigen kann, fragt jeder
Dialog nach Koordinaten:

* *Bohrung setzen* öffnet mit Position X/Y/Z = 0,00. Bei der geladenen Platte
  liegt der Ursprung an einer Ecke; ausgeführt kratzt die Bohrung ein Stück
  Kante weg. Das Programm sagt dazu nur „Die Bohrung wurde um die
  Materialtoleranz vergrößert."
* Der Baustein *Kabeldurchführung* hat ein Feld **„An Merkmal"** — ein leeres
  Textfeld. Man müsste `face_2` hineinschreiben; im Objektbaum sind die Namen
  bei Standardbreite abgeschnitten und sehen alle gleich aus.
* *Quader anlegen* setzt den Körper an den Ursprung, mitten in die vorhandene
  Platte. Der Prüfbericht meldet die Durchdringung nicht von selbst.
* **Tour-Schritt 3 von Weg 3 ist dadurch nicht ausführbar** (siehe 4.2).

**Zu tun**

1. `_left_down` im slicer-Schema ruft den Picker; ein Treffer wählt Objekt
   oder Merkmal, ein Fehlschlag hebt die Auswahl auf. Kleinster Eingriff mit
   der größten Wirkung im ganzen Dokument.
2. Picking dauerhaft an. Was der Klick bedeutet, entscheidet der Modus — nicht
   ob überhaupt gepickt wird.
3. Rechtsklick auf Körper und Merkmal öffnet das Kontextmenü aus `applies_to`.
   Das ist der im Bauplan vorgesehene Ort für Weg 1.
4. Jeder Positionsparameter bekommt einen Knopf „Im Bild zeigen": der Klick
   füllt die Zahlenfelder, die Zahlen bleiben sichtbar und änderbar. §11 bleibt
   gewahrt — die Zahl ist die Wahrheit, das Zeigen die bequeme Eingabe.
5. „An Merkmal" wird eine Auswahlliste der erkannten Merkmale, mit Durchmesser
   und Fläche im Eintrag.
6. Vorgabeposition ist die Mitte der obersten Fläche des gewählten Objekts,
   nicht der Ursprung. Neue Objekte werden neben die vorhandenen gelegt.

### 1.2 Die Kamera arbeitet gegen den Nutzer

**„Alles einpassen" (Pos1) passt auf den Bauraum ein, nicht auf die Objekte.**
Mit dem Elegoo Centauri Carbon 2 heißt das: ein 256er Drahtquader füllt das
Bild, das 80-mm-Teil ist ein Fleck darin. Zweimal ausgelöst, über Taste und
über Menü — die Ansicht ändert sich nicht, weil sie schon „eingepasst" ist.

**Das Mausrad zoomt zur Bildmitte, nicht zum Zeiger.** Handbuch und
Code-Kommentar (`viewport.py:1209`) behaupten beide das Gegenteil. Nachgemessen:
der Punkt unter dem Zeiger wandert beim Zoomen weg.

**Jede Auswahländerung setzt die Kamera zurück.** Herangezoomt, dann im
Objektbaum etwas angeklickt — der Zoom ist weg. Bei jedem Arbeitsschritt.

**Der Schnitt-Regler läuft über den Bauraum statt über das Teil.** Bei einem
8 mm dicken Brett steht der Regler nach einem Zug in der Mitte auf 23,1 mm —
weit über dem Teil, kein Schnitt zu sehen. Erst 4,0 mm von Hand eingetippt
zeigt den Querschnitt. Das Teil belegt einige Prozent der Reglerlänge.

**Dasselbe beim Gizmo:** es richtet sich nach der Szene, nicht nach dem
Objekt, und ist auf einem 80-mm-Teil ein Gebilde aus dünnen Linien von etwa
vierzig Pixeln — zu klein zum Greifen, und die drei Achsen sind allein über
Rot/Grün/Blau unterschieden (Regel 18 verlangt eine zweite Kodierung).

**Zu tun**

1. „Alles einpassen" meint die Objekte. Der Bauraum ist Kulisse. Ohne Objekte
   den Bauraum, sonst die Objekte mit etwas Rand; bei Auswahl auf die Auswahl.
2. Nach dem Öffnen einmal einpassen — auf das Geladene.
3. Kamera überlebt Auswahl und Neuberechnung: Position vor dem Neuaufbau
   sichern, danach zurücksetzen. Nur „Einpassen" und die Achsansichten ändern
   sie.
4. Zoom auf den Zeiger — oder Handbuch und Kommentar sagen die Wahrheit.
5. Schnittregler und Gizmo skalieren mit dem Objekt, nicht mit dem Bauraum.
   Gizmo-Achsen bekommen X/Y/Z-Beschriftungen.

### 1.3 Nichts sagt, dass das Teil nicht auf dem Bett liegt

Das wiederhergestellte Projekt hatte seinen Körper mittig auf z = 0 — die
untere Hälfte steckt unter der Bauplatte. Belegt durch die Schichtenvorschau:

> Schicht 1/40 · z −3.90 mm · 3915 mm²

Zwanzig von vierzig Schichten liegen unter dem Bett. Die Schichtanalyse rechnet
sie klaglos durch. Der Prüfbericht meldete „0 × Fehler · 0 × Warnung ·
1 × Hinweis". Die Druckeinstellungen schrieben unter *Was dieses Teil
verlangt*: **„Nichts einzuwenden."**

Die Prüfung existiert — sie sagt „Ein Objekt steht über den Bauraum hinaus",
aber erst, wenn man *Objekt → Kollisionen prüfen* von Hand aufruft.

**Zu tun**

1. Lage zum Bauraum ist eine ständige Prüfung nach jeder Auswertung, mit dem
   Vorschlag „Auf die Platte legen".
2. Beim Import einmal absetzen — als eigener, rücknehmbarer Schritt im Verlauf.
   (Das Beispielprojekt Weg 1 hat genau diesen Schritt; der freie Import nicht.)
3. Die Schichtanalyse widerspricht, statt unter Null zu rechnen.

---

## Teil 2 — Gestaltung

Der schwächste Teil der Anwendung, und der erste, den jemand sieht.

### 2.0 Warum es aussieht, wie es aussieht

„Sieht standard aus" ist kein Geschmacksurteil, sondern hat drei nachweisbare
Ursachen.

**Erstens: Es gibt keine Formsprache, nur eine umgefärbte Qt-Palette.**
`theme.py` setzt eine `QPalette` — also Hintergrund-, Text- und
Auswahlfarben — und sonst nichts. Ein Stylesheet für die Anwendung existiert
nicht: in `app/` stehen **sechs** `setStyleSheet`-Aufrufe, und fünf davon sind
Einzelfälle (ein Farbfeld, zwei Überschriften, der Ablagerahmen, ein
Farbknopf). Damit erbt jeder Knopf, jedes Eingabefeld, jeder Reiter und jede
Liste das Standardaussehen von Qt Fusion. Es gibt keine eigenen Eckradien,
keine Abstufung zwischen Haupt- und Nebenknopf, keine Hover-, Fokus- oder
Aktiv-Zustände über den Qt-Vorgaben, keine Trennlinien mit Absicht. Das
Ergebnis ist nicht hässlich — es ist **unverwechselbar unverwechselbar**: Es
sieht aus wie jede andere Qt-Anwendung.

**Zweitens: Es gibt keine Typografie-Skala.** Zwei Stellen setzen eine
Schriftgröße (`20px` und `24px` für Überschriften), alles andere läuft in der
Systemgröße. Damit sind Titel, Beschriftung, Wert, Hilfetext und Statuszeile
**gleich laut**. Das Auge bekommt keine Führung: Im Objektbaum ist der
Objektname so groß wie sein Maß, im Prüfbericht ist ein Fehler so groß wie ein
Hinweis, in einem Dialog ist die Beschriftung so groß wie der Wert.

**Drittens: Es gibt keinen Raster- oder Abstandsrhythmus.** 50 Aufrufe von
`setSpacing`/`setContentsMargins` über die Oberfläche verteilt, jeder für sich
entschieden. Elemente stehen deshalb mal 4, mal 6, mal 12 Pixel auseinander,
und die Panels haben keine gemeinsame Innenkante. Das erzeugt den Eindruck,
dass „irgendwie alles ein bisschen daneben sitzt", ohne dass man einen
einzelnen Fehler benennen kann.

**Zu tun**

1. **Ein Stylesheet für die Anwendung** (`app/ui/style.qss`, aus dem Thema
   gefüllt), das Knöpfe, Felder, Listen, Reiter, Kopfzeilen und Trenner einmal
   definiert — mit Zuständen (normal, hover, fokus, aktiv, gesperrt).
2. **Eine Typografie-Skala** mit vier Stufen: Titel, Abschnitt, Fließtext,
   Nebentext. Größe *und* Gewicht *und* Farbe je Stufe. Der Nebentext (Maße,
   Einheiten, Herkunft) wird dabei kleiner und gedämpfter — er soll lesbar
   sein, nicht mitreden.
3. **Ein Abstandsraster** aus einer Zahl (4 oder 8 px) und ihren Vielfachen.
   Panels bekommen dieselbe Innenkante. Danach sitzt nichts mehr „daneben",
   weil es nichts mehr dazwischen gibt.

### 2.0.1 Warum es unübersichtlich wirkt

Das Fenster hat drei Zonen, wie der Bauplan es vorsieht — aber alle drei sind
**gleich schwer**. Links stapeln sich Objektbaum, Parameter und Verlauf als
drei gleich gestaltete Kästen mit gleich aussehenden Kopfzeilen; keiner ist
wichtiger als die anderen, keiner wächst mit seinem Inhalt. Bei der geladenen
Platte belegt der Objektbaum 500 Pixel für zwölf Zeilen und der Verlauf 300
Pixel für vier — die leeren Flächen sind größer als die Inhalte.

Rechts konkurrieren Prüfbericht, Chat und Tour als gleichrangige Reiter, obwohl
zwei davon meistens nichts zu sagen haben. Unten liegen sieben Umschalter
nebeneinander, die nach demselben Muster gebaut sind, aber sehr Verschiedenes
tun: „Schnitt" ändert die Ansicht, „Bewegen" ändert die Geometrie, „Analyse"
rechnet.

Und über allem: **Nichts zeigt, was gerade gilt.** Kein aktives Werkzeug ist
hervorgehoben (bis auf den eingerasteten Knopf), kein Menü hat ein Häkchen beim
aktiven Thema oder Navigationsschema, keine Statuszeile sagt, in welchem
Zustand man ist.

**Zu tun:** Die drei linken Abschnitte wachsen mit ihrem Inhalt und klappen
zu, wenn sie leer sind. Reiter rechts nur zeigen, wenn sie Inhalt haben.
Aktive Zustände sichtbar machen — im Menü mit Haken, in der Werkzeugzeile mit
einer Akzentlinie, in der Statuszeile mit einem Wort.

### 2.0.2 Warum es nicht intuitiv ist

Drei Muster, die sich durch die ganze Anwendung ziehen:

* **Was aussieht wie Text, ist Text — auch wenn es klickbar ist.** Die sieben
  Beispiele auf dem Startbildschirm sind eine Liste ohne Rahmen, ohne Hover,
  ohne Cursor-Wechsel. Die Merkmale im Objektbaum ebenso. Der Nutzer probiert
  nicht, was nicht nach Knopf aussieht.
* **Der erste Klick tut nichts Sichtbares.** Drei der sieben Werkzeuge öffnen
  eine Leiste, in der man dasselbe noch einmal einschalten muss („Bewegen" →
  Häkchen „Gizmo", „Bemalen" → Häkchen „Bemalen", „Analyse" → Karte wählen).
  Wer „Bewegen" drückt und nichts passieren sieht, drückt es wieder aus.
* **Der Ort der Wirkung ist nicht der Ort der Handlung.** Ein Fehlschlag
  erscheint rechts im Prüfbericht, während der Dialog in der Mitte
  verschwindet. Eine Kollision erscheint als Textzeile, nicht am Körper. Ein
  Merkmal wählt man links im Baum aus, sehen tut man es in der Mitte.

**Zu tun:** Anklickbares sieht anklickbar aus (Rahmen, Hover, Zeigerwechsel).
Ein Werkzeug schaltet sich mit dem Klick ein, nicht mit dem zweiten. Und die
Rückmeldung erscheint dort, wo gehandelt wurde — im Dialog, am Körper, an der
Zeile.

### 2.0.3 Die Live-Vorschau gibt es — man sieht sie nur nicht

Das ist der überraschendste Fund dieser Runde. `main_window.py:2322–2340` baut
genau das, was fehlt: `dialog.valuesChanged` ist über einen 300-ms-Timer an
`session.preview_async(...)` gehängt, das Ergebnis geht als Differenz an
`viewport.show_difference()`, und `request()` läuft schon beim Öffnen des
Dialogs. Die Rechenzeit spricht ebenfalls dafür — `evaluate_cached` liegt bei
**0,28 ms**.

Im Lauf ist mir davon nichts aufgefallen, und dafür gibt es zwei Gründe:

1. **Der Dialog steht mittig über dem Teil.** *Bohrung setzen* öffnet bei
   (752, 413) in einem 1920 × 1150-Fenster — also genau dort, wo die Kamera
   das Modell zeigt. Die Vorschau entsteht hinter dem Dialog.
2. **Der Dialog ist modal** (`dialog.exec()`). Man kann nicht drehen, nicht
   zoomen, nicht wegschieben, um die Vorschau zu beurteilen — und wenn das
   Teil verdeckt ist, hilft nur Abbrechen.

Dazu kommt: Es gibt **keinen Hinweis, dass eine Vorschau läuft.** Kein „Was Sie
sehen, ist noch nicht übernommen", keine Kennzeichnung der Differenz in der
Legende, kein Umschalter Vorher/Nachher.

**Zu tun**

1. **Den Dialog aus der Mitte nehmen.** Er dockt an eine Fensterkante oder wird
   eine Leiste am Rand — der Viewport bleibt frei. Das ist der billigste Weg,
   aus einer vorhandenen Funktion eine sichtbare zu machen.
2. **Nicht modal.** Drehen, Zoomen und Einpassen bleiben erreichbar, während
   der Dialog offen ist. Der Stapel wird ohnehin erst bei „Übernehmen"
   angefasst — die Sperre schützt nichts.
3. **Die Vorschau kennzeichnen**: eine Zeile im Viewport („Vorschau — noch nicht
   übernommen") und die Differenzfarben aus `palette.py` in der Legende.
4. **Ein Umschalter Vorher/Nachher** (Leertaste gedrückt halten), weil man
   einen Unterschied nur sieht, wenn man beides kennt.
5. Wo eine Op zu lange rechnet für 300 ms, zeigt die Vorschau den Umriss statt
   des fertigen Körpers — lieber grob und sofort als exakt und zu spät.

### 2.1 Der Startbildschirm

Bei 1920 × 1150 sieht er so aus: „Formwerk" klein oben links. Darunter
1000 Pixel Nichts. In der Bildmitte schwebt der Satz „Modell oder Projekt hier
ablegen / STL · 3MF · OBJ · GLB · .p3d" — **ohne Rahmen, ohne Feld, ohne
Symbol.** Man sieht nicht, dass das eine Ablagefläche ist. Zwei
Standard-Qt-Knöpfe („Neues Projekt", „Projekt öffnen …") in gewöhnlicher
Größe. Der Link „Handbuch — die ersten fünfzehn Minuten" steht in derselben
Zeile **1700 Pixel weiter rechts**. Die sieben Beispiele sind eine
untereinandergesetzte Textliste ohne Bild, ohne Beschreibung, ohne erkennbare
Anklickbarkeit. Darunter eine leere Box über 400 Pixel Höhe mit dem Satz
„Noch nichts geöffnet."

Fusions Startseite daneben: eine schmale Spalte mit Hub-Auswahl, zwei
Hauptknöpfen und der Navigation (Aktuell · Projekte · Mein Fusion ·
**Beispiele**), unten die Verweise (Neue Funktionen · Produktdokumentation ·
Selbststudium · Forum). Rechts der Inhalt mit Suchfeld, Umschalter zwischen
Liste und Kacheln — und der leere Zustand als **Bild plus Überschrift plus
Satz plus Knopf**: „Noch keine Daten vorhanden. / Erstellen oder öffnen Sie
zunächst ein Dokument."

Der Unterschied ist nicht Geschmack. Fusion macht den leeren Zustand zu etwas,
das aussieht wie Absicht; Formwerk sieht aus wie ein Formular, dem die Felder
fehlen.

**Zu tun**

1. Inhalt auf eine Spalte begrenzter Breite (etwa 900 px) und **mittig
   setzen**, statt über 1900 px zu verteilen.
2. Das Ablagefeld wird ein Feld: gestrichelter Rahmen, Symbol, Hover-Zustand.
3. Beispiele als **Kacheln** mit Vorschaubild, Titel und einem Satz — das
   Rendern kann `tools/make_figures.py`, das es schon gibt.
4. „Neues Projekt" bekommt visuelles Gewicht (Primärknopf), „Projekt öffnen"
   bleibt sekundär.
5. Der Handbuch-Link wandert neben die Knöpfe.
6. Die leere Zuletzt-Liste wird eine Zeile, keine 400-Pixel-Box.

### 2.2 Der Startbildschirm ist nach dem ersten Start unerreichbar

*Datei → Neu* zeigt ihn **nicht** wieder — man landet in einer leeren Szene mit
Bauraum. Damit sind Beispielprojekte und alle sieben Touren nach dem ersten
Start nur noch über *Öffnen* mit Pfadkenntnis zu erreichen. Zweimal geprüft.

Dazu: Nach *Neu* blieben **orangene Merkmalsmarkierungen des vorigen Objekts
im Viewport stehen**, obwohl Objektbaum und Prüfbericht leer waren.

**Zu tun:** *Neu* führt auf den Startbildschirm; ein Menüpunkt *Hilfe →
Beispiele* zeigt sie jederzeit. Beim Projektwechsel den Viewport vollständig
räumen.

### 2.3 Das helle Thema ist unfertig

Umgeschaltet über *Ansicht → Helles Thema*:

* **Nur der Viewport wird hell.** Menüleiste, Werkzeugleiste, Objektbaum,
  Parameter, Verlauf, Tour und Statusleiste bleiben dunkel. Das Fenster
  zerfällt in zwei Hälften.
* **Alle Symbole der Viewport-Werkzeugleiste verschwinden.** „Schnitt",
  „Messen", „Bewegen", „Analyse", „Schichten", „Explosion", „Bemalen" stehen
  als Text da, davor eine Lücke, wo das Symbol war. Auch die Häkchen in der
  Tour sind weg.
* **Zurückschalten auf Dunkel stellt nicht alles zurück.** Die Abschnittsköpfe
  „Objekte", „Parameter" und „Verlauf" blieben hell — über den Projektwechsel
  hinweg, bis zum Neustart.

**Zu tun:** Ein Thema ist eine Palette für die ganze Anwendung, nicht für den
Viewport. Symbole als Vektoren mit Farbe aus dem Thema, nicht als helle
Bitmaps. Der Wechsel setzt jedes Element neu — am besten über ein einziges
Stylesheet, das getauscht wird.

### 2.4 Farbe — vier Farbwelten, kein System

`theme.py` schreibt die richtige Regel gleich in seinen eigenen Docstring:
*„Farben, die Bedeutung tragen, leben in `palette.py`; was hier steht, ist nur
der Rahmen darum."* Befolgt wird sie nicht. Ausgezählt über alle Hexwerte in
`app/`:

| Bedeutung | Werte im Code | wo |
|---|---|---|
| Warnung / Achtung | `#e0a33c` · `#d99048` · `#b4611c` | Bericht und Insel · SVG dunkel · SVG hell |
| Hinweis / Akzent blau | `#6da3d6` · `#6ba3dd` · `#3b82c4` · `#7fb2e5` · `#cfe3f5` | Bericht · SVG · Differenz · Schichtkontur · Merkmalsbeschriftung |
| Fehler rot | `#d05a5a` · `#c92a2a` · `#8b3a3a` | Bericht und Überhang · Rot/Grün-Palette · Rückseiten |
| Auswahl | `#3d6ea5` / `#2f6fb0` **blau** gegen `#f0a54a` **orange** | Objektbaum gegen Viewport |

Die letzte Zeile ist die auffälligste: **dieselbe Handlung, zwei Farbfamilien.**
Ein Objekt anwählen färbt seine Zeile im Baum blau und seinen Körper im
Viewport orange. Nichts verbindet die beiden optisch.

Die vier Farbwelten stammen aus vier Quellen, die einander nicht kennen:

1. `theme.py` — Rahmen, hell und dunkel gepaart, Kontrast gegen WCAG AA geprüft
2. `palette.py` — die bedeutungstragenden Farben, vorbildlich gebaut
3. `viewport.py:101–145` — **neun eigene Konstanten** (Auswahl, Messlinie,
   Rückseite, Schichtkontur, Insel, Überhang, Merkmalsbeschriftung), die
   keinem Thema folgen. `OBJECT_COLOUR = "#b9c4d0"` ist eine wörtliche Kopie
   von `theme.py: object` — zwei Wahrheiten für denselben Ton.
4. `drawing.py:75–90` — eine **dritte** Palette (`paper`, `ink`, `muted`,
   `accent`, `warn`, `fill`), eigenes Hell/Dunkel-Paar

Dazu eine fünfte, die gar nicht mitspielt: **Das Anwendungssymbol** trägt ein
gebranntes Orange (`#3a1c06` → `#b96428` → `#e08b4e`), das in der Oberfläche
**an keiner Stelle vorkommt**. Formwerk hat damit keine sichtbare Markenfarbe —
der Ton, der im Startmenü und in der Taskleiste für die Anwendung steht, taucht
im Programm nie wieder auf.

**Das erklärt auch 2.3.** Die neun Viewport-Konstanten sind themenlos; deshalb
bleiben Auswahl, Messlinien und Schichten im hellen Thema in ihren
dunkeltauglichen Tönen, während der Rest umschaltet. Der Test
`test_the_viewport_follows_the_theme` prüft nur, dass `viewport_colours()`
unterschiedliche Werte liefert — nicht, dass die Modulkonstanten mitziehen.

**Was daran gut ist und bleiben muss.** `palette.py` ist der sauberste Teil der
ganzen Oberfläche: jede Farbe ist ein `Encoding(farbe, muster, zeichen, name)`,
trägt also von Bauart her eine zweite Kodierung (Regel 18). Es gibt drei
Differenzpaletten — Blau/Orange als Vorgabe, Rot/Grün und Graustufen als
Alternativen —, eine Viridis-Rampe statt Regenbogen, und
`relative_luminance()` rechnet den Textkontrast aus, statt ihn zu raten. Sieben
Tests halten das fest.

**Zu tun**

1. **Eine Farbquelle.** `palette.py` bekommt die semantischen Rollen (`select`,
   `warn`, `info`, `error`, `measure`, `layer`, `island`, `overhang`,
   `feature`) je Thema; `viewport.py` und `drawing.py` lesen von dort statt
   eigene Konstanten zu führen. Danach hat „Warnung" einen Wert, nicht drei.
2. **Eine Auswahlfarbe.** Entweder der Baum färbt in der Viewport-Auswahlfarbe
   oder umgekehrt — aber nicht blau hier und orange dort.
3. **Die Markenfarbe in die Oberfläche holen.** Das Bernstein des Symbols ist
   ein guter Akzent: er unterscheidet Formwerk vom Qt-Standardblau, das jede
   zweite Desktop-Anwendung trägt. Er passt zu warmem Filament, und die
   Auswahl im Viewport benutzt ihn bereits — er müsste nur überall gelten:
   Primärknopf, Fokusrahmen, aktiver Reiter, Fortschritt.
4. **Ein Test, der jede Rolle einmal zählt.** Kommt derselbe Sinngehalt an zwei
   Stellen mit verschiedenen Werten vor, wird der Lauf rot — sonst driftet es
   beim nächsten Modul wieder auseinander.

### 2.5 Symbole und Kodierung

* **Der Bausteinkatalog** gibt jedem Baustein eine große Vorschau, aber
  „Rastnase", „Filmscharnier" und „Schnappverbindung" sind drei fast gleiche
  graue Keile; „Magnettasche" ist ein orangener Kreis. Was subtraktiv und was
  additiv ist, unterscheidet **allein die Farbe des Bildes** — ohne Legende
  (Regel 18). Trotz Rasterlayout braucht der Dialog eine waagerechte
  Bildlaufleiste, und Gruppen mit einem Baustein verbrauchen eine ganze Zeile.
* Fusions Vergleichsdialog macht dasselbe besser: sechs klar verschiedene
  Symbole, Auswahl über Rahmen **und** Hintergrund, und rechts eine
  Detailspalte, die die gewählte Kachel in zwei Sätzen erklärt.
* **Zusätzliche Programme** kodiert „vorhanden" und „fehlt" über „+" und „−".
  Zweite Kodierung ist damit erfüllt, aber Haken und Kreuz wären lesbar.
* **Die Analysekarten** verwenden eine wahrnehmungsgleiche Palette — richtig.

**Zu tun:** Vorschauen so zeichnen, dass sich benachbarte Bausteine
unterscheiden; ein Abzeichen (nicht die Bildfarbe) für „nimmt Material weg";
Detailspalte im Katalog; Raster ohne waagerechtes Scrollen.

### 2.5 Kleinere Brüche im Bild

* Die Kartenliste in der Analyse-Leiste klappt nach unten **über den unteren
  Fensterrand hinaus**.
* *Ansicht → Navigation* zeigt vier Schemata, **keines mit Häkchen**; ebenso
  Dunkles/Helles Thema. Der aktive Zustand ist unsichtbar.
* Drei der sieben Werkzeuge in der Viewportleiste (Bewegen, Bemalen, Analyse)
  öffnen eine Leiste, in der man **noch einmal dasselbe einschalten muss**
  („Gizmo", „Bemalen", „Karte wählen"). Der erste Klick tut nichts Sichtbares.
* Der Bauraum wird als Drahtquader über die volle Höhe gezeichnet; aus der
  Vorgabeansicht sieht man nur eine Raute weit über dem Bett schweben, die
  senkrechten Kanten erscheinen erst beim Drehen.
* Das Achsenkreuz oben rechts besteht aus farbigen Kugeln mit X/Y/Z und tut
  nichts. Fusions ViewCube ist ein beschrifteter Würfel, den man anklickt.
* Der Chat ohne Sprachmodell ist eine leere Fläche über 800 Pixel. Drei
  Beispielanfragen dort wären der billigste Weg, Weg 3 erklärbar zu machen.

---

## Teil 3 — Das interaktive Tutorial

Alle sieben Beispielprojekte haben eine Tour, alle sind **inhaltlich sehr gut
geschrieben** — fachlich präzise, im richtigen Ton, mit dem Warum statt nur dem
Wie. Die Umsetzung nimmt ihnen die Wirkung.

### 3.1 Die Tour hängt am ersten Schritt

Bei **Weg 1** habe ich Schritt 2 vollständig ausgeführt (den Bohrungsdurchmesser
im Verlauf von 4,20 auf 6,00 geändert). Die Tour blieb auf **Schritt 1/5**
stehen. Ein Klick auf „Weiter" sprang dann auf **3/5** und hakte beide ab — die
Erkennung hatte gegriffen, sie war nur blockiert.

Bei **Weg 2** dasselbe, deutlicher: Parameter `Breite` von 60 auf 90 geändert,
das Teil ist gefolgt (Halter 90 × 40 × 11 mm). Die Tour: weiterhin
**Schritt 1/4**, Schritt 2 ohne Häkchen.

Der Grund ist immer derselbe: Der erste Schritt ist eine **Beobachtung**, keine
Handlung — „Sehen Sie links in den Verlauf …", „Links unter Parameter stehen
…" — und lässt sich nie erkennen. Von den sieben Touren beginnen **fünf** so.

**Zu tun:** Schritte tragen ein Merkmal „nur lesen" und haken sich nach dem
Anzeigen selbst ab; oder die Erkennung prüft alle offenen Schritte statt nur
des aktuellen. Zweiteres ist billiger und robuster.

### 3.2 Eine Tour verlangt etwas, das die Anwendung nicht kann

Weg 3, Schritt 3, wörtlich:

> „Maße entstehen danach als eigene Schritte, nicht durch Vermessen des Netzes:
> **klicken Sie eine Fläche an, dann Rechtsklick → Bohrung setzen.**"

Nachgestellt: Klick auf den Körper — keine Auswahl. Rechtsklick — kein
Kontextmenü. Der Schritt ist nicht ausführbar (Ursache: 1.1).

### 3.3 Die Tour zeigt nichts

Alle Schritte stehen gleichzeitig untereinander, der aktuelle ist fett mit
einem Pfeil. Schritt 1 sagt „Sehen Sie links in den Verlauf" — es gibt keinen
Pfeil dorthin, kein Aufleuchten, keine Hervorhebung. Das ist eine Liste, keine
Führung. Schritt 5 von Weg 1 verweist auf den Prüfbericht, der ein **anderer
Reiter** ist: hinsehen heißt, die Tour zu verlassen.

Der Abschlusstext („Das war Weg 1: einlesen, reparieren, ändern …") steht ganz
unten nach 500 Pixeln Leere, und es gibt von dort keinen Weg zur nächsten Tour.

**Zu tun:** Den aktuellen Schritt groß, die übrigen eingeklappt. Jeder Schritt
nennt sein Ziel-Element und lässt es kurz aufleuchten (ein Rahmen um den
Verlaufsbereich genügt). Prüfbericht und Tour nebeneinander statt in
konkurrierenden Reitern, solange die Tour läuft. Am Ende ein Knopf auf die
nächste Tour.

### 3.4 Die Tour nennt Dinge anders als die Oberfläche

Weg 2, Schritt 1: „Links unter Parameter stehen **breite, tiefe und staerke**."
In der Parameterleiste steht: **Breite · Tiefe · Stärke**. Der Nutzer sucht
„staerke" und findet „Stärke". Die Tour zitiert die internen Schlüssel — und
die sind deutsche Stämme in ASCII-Transkription, also weder englisch (wie
`AGENTS.md` für Bezeichner verlangt) noch mit echtem Umlaut (wie für alles
andere verlangt). Dieselbe Schreibweise steckt in den Dateinamen der Beispiele:
`gehaeuse-mit-bausteinen.p3d`, `aushoehlen-und-teilen.p3d`.

---

## Teil 4 — Zeichnen, an Fusion gemessen

Der Skizzeneditor kann inhaltlich viel: Punkt, Linie, Kreis, Bogen, Spline,
sechs fertige Grundformen, zehn Zwangsbedingungen, eine Bedingungsliste und
die Statuszeile „Bestimmt — alle Freiheitsgrade sind vergeben". Das eingefügte
Rechteck trug elf Bedingungen und war sofort vollbestimmt. Die Substanz stimmt.

Nebeneinandergelegt mit Fusions Skizzenmodus fehlt vor allem Orientierung:

| | Fusion | Formwerk |
|---|---|---|
| Ursprung | sichtbarer Punkt, rote X- und grüne Y-Achse durchgezogen | nichts |
| Maßstab | beschriftete Achsen (−125 … 75) am Raster | nichts |
| Werkzeuge | eigenes Register mit großen Symbolen, gruppiert | Textknöpfe |
| Ändern-Gruppe | Verrunden, Trimmen, Verlängern, Versetzen, Spiegeln, Muster | **fehlt ganz** |
| Bezugnahme | Projizieren, Konstruktionsgeometrie | **fehlt ganz** |
| Palette | Fang, Raster, Aufschneiden, Profil, Punkte, Bemaßungen … | nichts |
| Abschluss | großer grüner Haken oben rechts *und* Knopf in der Palette | kleiner Textknopf unten |
| Kürzel | L Linie · R Rechteck · C Kreis · D Bemaßung · T Trimmen · O Versetzen | **keine** |

Nachgestellt: `L`, `R` und `C` im Skizzeneditor bewirken nichts — „Auswählen"
bleibt aktiv. Rechtsklick öffnet ein Kontextmenü, das nur die
Bedingungsleiste dupliziert und im Normalfall vollständig ausgegraut ist; es
klappt zudem nach links weg statt am Zeiger auf.

**Der Widerspruch in der Fusion-Belegung.** `app/ui/shortcut_schemes.py` bietet
seit dem letzten Commit eine Fusion-nahe Tastenbelegung — sie deckt aber nur
Modellieren ab (E, Q, F, C, M, R, H, P, S). Bei Fusion sind `R` und `C`
**Rechteck** und **Kreis** im Skizzenmodus; Formwerk vergibt sie an Drehen und
Fasen, und für die Zeichenwerkzeuge hat die Tabelle gar nichts. Wer aus Fusion
kommt, greift beim Zeichnen ins Leere und löst beim Modellieren etwas anderes
aus als erwartet.

**Zu tun**

1. **Ursprung, Achsen und Maßstab zeichnen.** Ohne die weiß man nicht, wo man
   ist. Billigste Einzelmaßnahme des ganzen Editors.
2. **Zeichenkürzel im Skizzenmodus**, an Fusion: `L` `R` `C` `A` `D` `T` `O`
   `X`, `Esc` beendet das Werkzeug. Die Kürzel stehen neben den Knöpfen, so
   lernt man sie nebenbei (§19.2).
3. Die Fusion-Belegung wird **kontextabhängig**: im Skizzenmodus die
   Zeichenkürzel, außerhalb die Modellierkürzel — genau wie Fusion es macht.
   Dann kollidieren R und C nicht mehr.
4. **Trimmen, Verlängern, Versetzen, Spiegeln** ergänzen. Ohne Trimmen ist
   jede Kontur, die nicht aus einer Grundform kommt, Handarbeit.
5. **Projizieren** — eine Kante des vorhandenen Körpers in die Skizze holen.
   Bei Weg 1 (fremdes Modell anpassen) ist das der Normalfall, nicht die
   Ausnahme.
6. **Maß beim Zeichnen eintippen**, Tab wechselt das Feld. In Fusion zeichnet
   man selten und bemaßt fast immer.
7. Die Bedingungsliste nennt Punktindizes („Deckung (1, 2)", „Fest (0)"). Beim
   Überfahren muss die betroffene Geometrie aufleuchten, sonst ist die Liste
   nicht lesbar.
8. Der Abschluss wird sichtbar: ein deutlicher Knopf oben rechts statt eines
   Textknopfs unten.
9. Die alte Werkzeugleiste (Schnitt, Messen, Bewegen …) im Skizzenmodus
   ausblenden — sie tut dort nichts und steht als zweite Leiste darunter.

---

## Teil 5 — Rückmeldung, Fehler, Verlauf

### 5.1 Fehler sagen das Falsche, und sagen es leise

*Formschräge anstellen* auf ein Netz angewandt — die Operation braucht einen
B-Rep-Körper, das steht sogar im Dialogtext. Der Dialog schließt sich, im
Viewport passiert nichts, im Verlauf erscheint `! Formschräge anstellen`. Im
Prüfbericht steht:

> Ein Wert liegt außerhalb des zulässigen Bereichs.

Es war kein Wert außerhalb eines Bereichs — der Winkel 2,00° war einwandfrei.
Es steht nicht dabei, **welcher** Wert. Und es steht kein Handlungsvorschlag
dabei, was Regel 17 ausdrücklich verlangt. Zu erwarten wäre: *„Formschräge
braucht einen exakten Körper. plate_holes ist ein Netz."* — mit den Knöpfen
*In exakten Körper umwandeln* und *Abbrechen*.

Dazu die Zustellung: **eine fehlgeschlagene Handlung meldet sich nirgends im
Blickfeld.** Die einzige Spur ist eine Zeile im rechten Bereich, den man
ausblenden kann.

### 5.2 Eine Handlung, deren Rückmeldung man übersieht

**Korrektur zur ersten Fassung dieses Abschnitts.** Dort stand, *Bearbeiten →
Automatisch teilen* auf einem passenden Teil sage „nichts". Das war falsch:
Formwerk schreibt „Dieses Objekt passt bereits auf das Bett." in die
Statusleiste. Im Lauf ist mir das entgangen, weil ich nach einer Menüaktion
Verlauf und Prüfbericht angesehen habe — und dort steht nichts, richtigerweise.

Was bleibt, ist schwächer und trotzdem wahr: Die Statusleiste ist der Ort für
Wartezeit (§2.8), nicht für das Ergebnis einer Handlung, die man gerade aus
einem Menü ausgelöst hat. Der Blick ist dort, wo der Mauszeiger war. Zum
Vergleich derselbe Fall, gut gelöst: *Varianten erzeugen* sperrt seinen Knopf
und schreibt daneben „Dieses Projekt hat keine Parameter — ohne einen gibt es
nichts zu variieren." Das sieht man, ohne es zu suchen.

Getestet war die Zusage bis dahin nicht; jetzt hält
`tests/test_split_ui.py::test_a_part_that_fits_gets_told_so` sie fest.

### 5.3 Befunde ohne Bezug, Befunde doppelt

* „Zwei Objekte überschneiden sich." — welche zwei? „Ein Objekt steht über den
  Bauraum hinaus." — welches, und um wie viel? Kein Name, keine Zahl, kein
  Klickziel.
* Nach Kollisionsprüfung **und** Export stand „Ein Objekt steht über den
  Bauraum hinaus" **zweimal** in der Liste.
* **Der Export läuft durch, obwohl das Ergebnis nicht druckbar ist**: zwei sich
  durchdringende Körper, einer außerhalb des Bauraums — die STL wird
  geschrieben.

  **Korrektur zur ersten Fassung.** Dort stand „kommentarlos" und der
  Vorschlag, mit „Trotzdem exportieren / Erst in Ordnung bringen" zu fragen.
  Beides ist falsch. Kommentarlos war es nicht: die Exportprüfung lief und
  meldete den Bauraum, ich hatte den Befund für den älteren aus der
  Kollisionsprüfung gehalten (siehe das Duplikat eine Zeile darüber). Und
  fragen darf der Export nicht — Bauplan §29 schreibt vor: „Exportprüfung vor
  dem Schreiben, **als Bericht, nicht als Blockade** … Wer trotzdem
  exportieren will, kann das — er weiß dann nur, was er tut." Ein
  Bestätigungsdialog wäre zudem Regel 19.

  Was bleibt, steht in demselben Satz: *er weiß dann, was er tut* — und das
  setzt voraus, dass er es **vorher** weiß. Die Befunde erschienen nach dem
  Schreiben.

  Und was unabhängig davon fehlt: Ein Exportdialog gibt es nicht, nur den
  Windows-Dateidialog. Was bei mehreren Objekten hineinkommt, wird nicht
  gefragt, und Vorgabeformat ist STL, obwohl das Projekt Materialslots kennt.

### 5.4 Der Verlauf

* **Entf im Verlaufsbereich löscht das Objekt aus der Szene.** Der Fokus lag im
  Verlauf, ein Eintrag war markiert; die Taste griff auf die Objektauswahl
  durch. Die daraus entstandene Operation „Objekt entfernen" stand danach im
  Stapel — **ohne Wirkung und ohne Fehlerzeichen**, das Objekt blieb sichtbar.
* **Kein Kontextmenü.** Bei einem non-destruktiven Stapel ist „Schritt
  entfernen / stilllegen / bis hierher zurück" die naheliegendste Handlung
  überhaupt. Nur Doppelklick öffnet die Parameter wieder — und beschriftet den
  Dialog mit „Operation 3", obwohl es der zweite Eintrag ist.
* **Interne Namen im Verlauf.** Weg 2 zeigt:
  `Grundkörper` · `Schraubenlöcher` · `2 insert_screw_hole` ·
  `3 insert_screw_hole` · `Versteifung`. Zwei eingerückte Zeilen mit dem
  englischen Registernamen und einer Zahl davor, zwischen deutschen Titeln.
* Der Knopf im wiedergeöffneten Dialog heißt weiterhin „Bohrung setzen",
  obwohl er einen bestehenden Schritt ändert. „Übernehmen" wäre richtig.

### 5.5 Ein Absturz, nicht reproduzierbar

Nach längerer Arbeit (Themenwechsel, Skizzeneditor, mehrere Beispiele) ist
Formwerk beim Ändern eines Projektparameters **ohne Meldung verschwunden** —
kein Fenster, kein Prozess. In einer frischen Sitzung ließ sich derselbe
Ablauf nicht wiederholen; die Parameteränderung lief dort sauber durch (Halter
folgte von 60 auf 90 mm), mit einer Qt-Warnung `QLineEdit::setSelection:
Invalid start position (22)`. Kein bewiesener Fehler, aber ein Fund, der eine
Untersuchung verdient: eine Anwendung, die schweigend verschwindet, verliert
mehr als eine Sitzung.

**Zu tun (5.1–5.5)**

1. Typprüfungen vor Parameterprüfungen, mit eigenem Text und der Umwandlung
   als Vorschlag.
2. Fehlschlag bleibt im Dialog sichtbar, statt ihn zu schließen.
3. Jeder Befund nennt Objekte und Zahl und ist anklickbar (Auswahl + Kamera).
4. Befunde zusammenfassen statt anhäufen.
5. Jede Handlung endet in einer Aussage — auch „hier war nichts zu tun", und
   an einer Stelle, die man sieht, ohne sie zu suchen.
6. Export zeigt seine Befunde, **bevor** er schreibt — als Bericht, nicht als
   Blockade (§29). Dazu ein Exportdialog mit Umfang, Format und Namensschema.
7. Entf gilt nach Fokus; Kontextmenü im Verlauf; Verlaufstitel immer
   übersetzt; Knopfbeschriftung nach Handlung.
8. Absturzursache suchen — Qt-Warnung als Spur, Absturzprotokoll schreiben.

---

## Teil 6 — Texte

Beim Öffnen von *Quader anlegen* steht im Dialog:

> Legt einen Quader an. **Erst in der Bausteinbibliothek suchen (§39).**

Eine Regel aus `rules.toml`, geschrieben für das Sprachmodell, steht im
`doc`-Feld der Operation (`primitive_ops.py:78`) — also dort, wo der Nutzer sie
liest. Wer auf „Quader anlegen" klickt, hat sich entschieden.

| Stelle | steht da | sollte dastehen |
|---|---|---|
| Hilfe → Zusätzliche Programme | „OpenCASCADE — Exakte Kanten … (§30)" | ohne § |
| Bausteindialog | `cable-5`, `ptfe-4x2` | „Rundkabel Ø5 mm", „PTFE-Schlauch 4×2 mm" |
| Material kalibrieren | `petg — Startwert` | „PETG" |
| Viewport, Objektbaum | `face_2 · 3915 mm²` | „Oberseite · 3915 mm²" |
| Objektbaum, Statusleiste | `80.00 × 50.00 × 8.00 mm` | mit Komma, wie in den Dialogen |
| Druckeinstellungen | Farbe: `#4A90D9` | Farbfeld mit Namen |
| Datei-Menü | „Beenden · **Verlassen**" | Alt+F4 oder nichts |
| Über | „Copyright (c) 2026" | © |

Die Zahlen sind der schärfste Fall: In Weg 2 stehen **vierzig Pixel
voneinander entfernt** „Halter 60.00 × 40.00 × 11.00 mm" und das Eingabefeld
„60,00 mm". Zwei Schreibweisen derselben Zahl im selben Blick.

**Der Tastenkürzel-Dialog** (Hilfe → Tastenkürzel) hat zwei eigene Fehler:

* Die Kürzel stehen **englisch**: `Ctrl+Z`, `Ctrl+S`, `Home`, `Del` — während
  dieselben Kürzel in den Menüs deutsch stehen: `Strg+Z`, `Strg+S`, `Pos1`,
  `Entf`.
* Die Fußzeile sagt: „Alles ist außerdem über die Befehlspalette erreichbar —
  **Strg+G**." `Strg+G` öffnet *Modell erzeugen*. Die Befehlspalette liegt auf
  `Strg+Umschalt+P`.
* Der Dialog listet 17 Befehle. Die fünfzehn Kürzel für Darstellung (`1`–`6`)
  und Kameravorgaben (`Strg+0`–`Strg+6`) fehlen vollständig.

**Zu tun**

1. Zwei Textquellen trennen: `doc` ist Nutzertext, die Agentenregel steht in
   der Regelsammlung. Ein Test, der `doc`-Felder auf „§" prüft, hält das fest.
2. Normteil- und Materialschlüssel bekommen Anzeigenamen; Merkmale bekommen
   sprechende Namen (`face_2` bleibt die ID).
3. **Ein Ort für Zahlenformatierung**, den Baum, Statusleiste, Bericht,
   Beschriftungen und Skizzenmaße gemeinsam benutzen. Deutsch heißt Komma.
4. Kürzel-Anzeige über `QKeySequence.toString(NativeText)` und in der
   Anwendungssprache — an einer Stelle, für Menü und Dialog.
5. Der Kürzel-Dialog wird aus derselben Quelle erzeugt wie die Menüs, sonst
   driftet er weiter.

---

## Teil 7 — Handbuch

Die geschriebenen Seiten sind **das Beste an der Anwendung**: klar, kurz,
ehrlich auch bei dem, was Formwerk nicht kann („kein Slicer", „keine Cloud"),
mit Sätzen wie „Jeder Schritt bleibt eine Zahl". Die Seite *Das Fenster* hat ein
gezeichnetes Schema. Zwei Dinge trüben das:

* **Die Seite *Das Fenster* beschreibt eine Navigation, die es nicht gibt** —
  „Linke Maustaste wählt aus … das Mausrad zoomt dorthin, wo der Zeiger steht".
  Zwei von vier Aussagen stimmen nicht (1.1, 1.2). Solange der Code nicht folgt,
  ist das Handbuch an der wichtigsten Stelle falsch.
* **Der erzeugte Referenzteil ist roh.** Die Seite *Reparatur* zeigt eine
  Tabelle mit `fill_holes`, `weld`, `degenerate`, `normals`,
  `small_components`, `self_intersections` — den internen englischen Namen, in
  Monospace, in einem deutschen Handbuch. Die Vorgaben stehen als `True` und
  `False`. Die Spalten „Einheit" und „Bereich" sind vollständig leer. Keine
  Abbildung, obwohl `tools/make_figures.py` und `app/images/` existieren.

**Zu tun:** Referenztabellen mit den übersetzten Parameterbezeichnungen (der
Schlüssel als kleiner Zusatz); `True`/`False` als „an"/„aus"; leere Spalten
weglassen statt leer zeigen; je Operation ein Vorher-Nachher-Bild aus dem
Abbildungskatalog. Und die Fenster-Seite stimmt, sobald 1.1 und 1.2 erledigt
sind — bis dahin muss sie beschreiben, was ist.

---

## Teil 8 — Einrichtung und Aufstellung

* **Die Grundformen stehen unter *Ändern → Boolesch*** — Quader, Zylinder,
  Kugel, die exakten Varianten und „OpenSCAD-Teil anheften", in einem Menü, das
  *Ändern* heißt, in einer Gruppe, die *Boolesch* heißt, obwohl nichts
  verschnitten wird. Das Menü *Erzeugen* hat Import, Skizze und Beschriftung —
  keine Grundform. Innerhalb der Gruppe ist die Reihenfolge gemischt (Quader,
  Exakter Quader, Exakter Zylinder, Zylinder, OpenSCAD, Kugel).
* **Die Erstinbetriebnahme wirkt nicht auf das offene Projekt.** Gewählt:
  Elegoo Centauri Carbon 2, PETG. In den Druckeinstellungen stand danach
  „Allgemeiner FDM-Drucker 220 mm" und PLA. Die Einstellungen erklären es
  („Diese Werte gelten für das nächste neue Projekt") — die Erstinbetriebnahme
  sagt es nicht, und beim ersten Start ist das offene Projekt genau das, mit
  dem weitergearbeitet wird.
* Sie verweist auf *Bearbeiten → Einstellungen*; die externen Programme stehen
  aber unter **Hilfe → Zusätzliche Programme** — Konfiguration im Hilfemenü.
* **Das Slicer-Profil ist mit einem fremden Drucker vorbelegt:** „Afinia
  H+1(HS) 0.4 nozzle", der erste Eintrag des installierten Bestands, dazu der
  ehrliche Satz „Zu diesem Drucker passt kein Profil von selbst — bitte
  auswählen." Wer den Satz überliest, sliced mit einem fremden Profil.
* **Die Druckerliste ist unsortiert:** Anycubic, Bambu ×4, **Elegoo Centauri
  Carbon 2**, Creality ×3, Elegoo Neptune ×2, Allgemeiner FDM-Drucker, Prusa
  ×3, Sovol. Fast alphabetisch, mit dem Centauri an der Stelle, an der er
  nachgetragen wurde.
* **Der Objektbaum passt seine Spalten nicht an.** Bei Standardbreite sind alle
  Merkmalsnamen abgeschnitten (`hole_…`, `face_…`), und die Spalte „Maße" zeigt
  bei Merkmalen den Typ („hole", „face") statt der Maße. Auf dreifache Breite
  gezogen bleibt die Spalte schmal. Der Durchmesser existiert — er steht in der
  Statusleiste (`plate_holes · hole_1 · Ø5.19 mm`).
* Die Wiederherstellung fragt „Die automatische Sicherung öffnen?" ohne zu
  sagen, von wann sie ist, was darin steht und was „Nein" mit ihr macht. Ebenso
  „Diese Änderung verwirft 2 zurückgenommene Schritte" ohne deren Namen. Beide
  Male heißen die Knöpfe „Ja"/„Nein" — während der Dialog *Ungesicherte
  Änderungen* es an derselben Stelle vorbildlich macht: „Speichern",
  „Verwerfen", „Abbrechen".
* „Rückgängig" und „Wiederholen" stehen **unten** im Bearbeiten-Menü, nach den
  Spezialfunktionen.
* *Material kalibrieren* nennt „Schwindung 0,004" ohne Einheit, während alle
  anderen Felder „mm" führen — und verweist nirgends auf den Toleranz-Testkörper,
  aus dem die gemessenen Werte kommen sollen.

---

## Teil 9 — Die Karten

**Wandstärke.** Am 8 mm dicken Brett zeigte die Legende 7,26 · 25,41 · 43,55 ·
61,70 · 79,85 mm. Die Karte misst korrekt — nur misst sie an den Stirnflächen
quer durch die ganze Länge des Teils. Die Skala spannt damit über 80 mm, und
der Bereich, um den es beim Drucken geht (unter zwei Extrusionsbreiten), fällt
in eine einzige Farbstufe. Die Karte kann ihre eigene Frage nicht beantworten.
Die Fußzeile „17 × nicht bestimmbar" bleibt unerklärt.

**Schichtenvorschau.** Der Text verspricht „Durch die Höhe fahren und den
Querschnitt ansehen". Der Schieber läuft, die Zahlen stimmen — das Modell
bleibt vollständig undurchsichtig stehen, sichtbar wird nur eine dünne Kontur
darunter.

**Merkmalsüberlagerung.** Drei Beschriftungen (`face_2`, `face_4`, `face_6`)
schweben über dem Teil und verdecken es teilweise; die vier Bohrungen, nach
denen das Modell benannt ist, bekommen keine.

**Zu tun:** Skala der Wandstärkenkarte bei einem druckrelevanten Wert deckeln
(Vorschlag: das Zehnfache der Extrusionsbreite), alles darüber in eine Farbe.
„Nicht bestimmbar" erklären. Die Schichtenvorschau blendet aus, was oberhalb
liegt. Beschriftungen beim Überfahren statt dauerhaft, Bohrungen mit
Durchmesser.

---

## Teil 10 — Reihenfolge

Nach Wirkung je Aufwand.

**Zuerst — ohne das ist die Anwendung nicht von Hand bedienbar**

1. Linksklick wählt aus; Picking dauerhaft an; Rechtsklick öffnet das
   Kontextmenü am Merkmal
2. „Alles einpassen" meint die Objekte; nach dem Öffnen einmal einpassen
3. Kamera überlebt Auswahl und Neuberechnung
4. „Im Bild zeigen" an jedem Positionsparameter; „An Merkmal" als Liste
5. Lage zum Bauraum als ständige Prüfung; Import legt auf die Platte

**Danach — das Tutorial soll tragen, was es verspricht**

6. Tour hakt Beobachtungsschritte selbst ab (oder prüft alle offenen)
7. Aktueller Schritt groß, übrige eingeklappt; Ziel-Element hervorheben
8. Tour und Prüfbericht gleichzeitig sichtbar; Abschluss führt weiter
9. Tourtexte nennen die Parameter so, wie die Oberfläche sie zeigt

**Dann — Gestaltung**

9a. **Den Op-Dialog aus der Bildmitte nehmen und nicht-modal machen** — damit
    wird die vorhandene Live-Vorschau sichtbar. Größte Wirkung je Aufwand im
    ganzen Gestaltungsteil, weil die Funktion schon da ist
9b. Vorschau kennzeichnen; Vorher/Nachher auf der Leertaste
9c. Ein Stylesheet, eine Typografie-Skala, ein Abstandsraster
9d. Eine Farbquelle für alle Rollen; eine Auswahlfarbe; Markenfarbe einsetzen
10. Helles Thema vollständig; Symbole aus dem Thema; Wechsel setzt alles neu
11. Startbildschirm: begrenzte Breite, echtes Ablagefeld, Beispiele als
    Kacheln — und über *Neu* wieder erreichbar
12. Katalogvorschauen unterscheidbar, Abzeichen statt Bildfarbe, Detailspalte
13. Aktive Auswahl in Menüs markieren; Kartenliste innerhalb des Fensters
14. Bauraum dezenter; Gizmo und Schnittregler nach Objektgröße

**Parallel — Zeichnen auf Fusion-Niveau**

15. Ursprung, Achsen, Maßstab
16. Zeichenkürzel (L R C A D T O X), kontextabhängige Fusion-Belegung
17. Trimmen, Verlängern, Versetzen, Spiegeln
18. Projizieren und Konstruktionsgeometrie
19. Maß beim Zeichnen eintippen; Bedingungen beim Überfahren hervorheben

**Und laufend — Vertrauen**

20. Fehler mit richtiger Ursache und Vorschlag, sichtbar im Dialog
21. Jede Handlung endet in einer Aussage
22. Befunde mit Objekt, Zahl und Klickziel; keine Duplikate
23. Export zeigt seine Befunde vor dem Schreiben (§29: Bericht, keine
    Blockade); Exportdialog mit Umfang und Format
24. Entf nach Fokus; Kontextmenü im Verlauf; interne Namen raus
25. Agententexte aus den Nutzerdialogen; § raus; Zahlen mit Komma; Kürzel
    deutsch und vollständig
26. Absturzursache suchen und Absturzprotokoll schreiben

---

## Stand (5. August 2026, zweiter Eintrag)

Dreiundfünfzig Commits, die Suite bei 2718 Tests. Was von der Reihenfolge oben
erledigt ist und was nicht:

**Erledigt** — 1 bis 4, 6 bis 14 einschließlich 9a–9d, 20, 22 bis 25.

Damit sind die Gruppen „Zuerst", „Danach" und „Dann — Gestaltung" durch. Die
Anwendung hat eine Formsprache (Stylesheet, vier Typografiestufen, ein
Abstandsraster von 4 px), das helle Thema kommt überall an, der Startbildschirm
ist einer, der Katalog erklärt seine Kacheln, und Bauraum, Gizmo und
Schnittregler richten sich nach dem Teil statt nach der Kulisse.

Zwei Funde entstanden erst beim Umsetzen, beide nur im Bild sichtbar: das
Einpassen rechnete richtig und wurde von pyvista sofort wieder verworfen
(`camera_set`), und die Panel-Kopfzeilen wurden vom neuen Stylesheet zu drei
bernsteinfarbenen Balken. Wer Gestaltung ändert, muss sie ansehen.

**Aus Teil 8 und 9 ebenfalls erledigt:** die Grundformen liegen unter
*Erzeugen*, alle Menüs sind nach ihren Titeln sortiert statt nach den
englischen Bezeichnern, die Druckerliste ist alphabetisch, Rückgängig steht
oben, die Erstinbetriebnahme erreicht das offene Projekt, das Slicer-Profil
belegt keinen fremden Drucker mehr vor, die Verwerfen-Frage nennt die
Schritte, die Schwindung steht als Prozentwert da, der Objektbaum trennt Name
und Maß und nennt Flächen nach ihrer Richtung, die Wandstärkenskala endet bei
einem druckrelevanten Wert, die Schichtanalyse schneidet, und die
Merkmalsüberlagerung beschriftet auch, was im Material steckt.

**Teilweise**

* **5** — die Bauraumprüfung läuft nach jeder Auswertung. Was fehlt: der
  Import legt nicht auf die Platte. `load` hat den Parameter (`place_on_bed`),
  seine Vorgabe ist `False`, und sie zu drehen ändert jedes bestehende
  Projekt — das ist eine Entscheidung, keine Reparatur.
* **21** — die Aussage gibt es (5.2), und jetzt hält sie ein Test fest. Offen
  bleibt die Stelle: die Statusleiste sieht nach einer Menüaktion niemand an.
* **26** — die Absturzursache ist gefunden und behoben (eine Referenzschleife
  zwischen Python und VTK, siehe 5.5); ein Absturzprotokoll gibt es weiterhin
  nicht.
* **11** — der Startbildschirm ist neu, die Beispiele sind Kacheln. Ohne
  Vorschaubild: `tools/make_figures.py` könnte sie rendern, dann müssten sie
  mitgeliefert und bei jeder Beispieländerung erneuert werden.
* **Teil 9** — die Merkmalsbeschriftungen stehen dauerhaft, nicht beim
  Überfahren. Sie sind ein Schalter, den man einschaltet, um sie zu sehen; ob
  das reicht, zeigt der nächste Lauf.

**Die fünf Zeichenpunkte 15 bis 19 sind ebenfalls durch.** Der Skizzeneditor
hat Ursprung, Achsen und Maßstab; die Kürzel liegen wie in Fusion und gelten
nur im Skizzenmodus; Trimmen, Verlängern, Versetzen und Spiegeln gibt es;
Projizieren holt die Kanten des Körpers herein, und Hilfsgeometrie trägt
Bedingungen, ohne ein Profil zu bilden; ein Maß lässt sich beim Zeichnen
eintippen, und die Bedingungsliste zeigt beim Überfahren, wovon sie spricht.
Dazu die beiden letzten Punkte aus Teil 4: die Ansichtswerkzeuge sind im
Skizzenmodus weg, und „Fertig" sieht aus wie der Abschluss.

Auch hier kam der wichtigste Fund erst beim Umsetzen. `R` und `C` liegen im
Fusion-Schema auf Drehen und Fasen — und Qt lässt bei zwei aktiven Kürzeln
derselben Taste **keines** von beiden feuern. Die Zeichenkürzel wären also
nicht zweitrangig gewesen, sondern wirkungslos. Gemessen mit einer Sonde, die
vorher und nachher zählt, welche Kürzel auf welcher Taste aktiv sind.

**Das Handbuch ist ebenfalls durch.** Der erzeugte Referenzteil nennt die
Parameter bei ihrem Titel und führt den Schlüssel daneben; ein Schalter steht
als „an" oder „aus"; leere Spalten fallen weg; jede Kategorieseite öffnet mit
einer Abbildung aus demselben Katalog, den die geschriebenen Seiten benutzen.
Die Faktenzeile nennt Merkmalsarten statt Registerschlüssel.

Die Seite *Das Fenster* stimmt wieder — und zwar weil der Code nachgezogen
hat, nicht weil der Satz weichgespült wurde: das Mausrad zoomt jetzt wirklich
dorthin, wo der Zeiger steht. VTKs Trackball-Stil dollyt entlang der
Kamera-Achse; an der echten Kamera gemessen bleibt der Punkt jetzt auf
0,000000 mm stehen.

**Und ein Fund am Ende, wieder nur im Bild sichtbar:** `make_figures.py` baute
seine Anwendung ohne `apply_theme`. Die Bildschirmfotos zeigten Formwerk mit
Qt-Vorgaben — Kacheln ohne Rahmen, Knöpfe ohne Abstufung, der Titel in
Fließtextgröße. Ein Handbuch, das etwas anderes zeigt als die Anwendung, ist
an der Stelle falsch, an der man ihm am ehesten glaubt.

**Offen** — die Vorschaubilder für die Beispielkacheln. `tools/make_figures.py`
könnte sie rendern; sie müssten mitgeliefert und bei jeder Beispieländerung
erneuert werden.

Bis hierher waren es Fehler — Dinge, die etwas anderes taten, als sie sagten,
und die Gestaltung, die keine war. Das Konzept ist damit abgearbeitet; was
bleibt, ist der nächste Lauf durch die Anwendung.

---

## Was gut ist und so bleiben soll

* **Der Ton.** „Ohne die zieht jeder Ruck am Kabel direkt an der Lötstelle."
  „Jeder Schritt bleibt eine Zahl." „Erst teilen, dann aushöhlen — nicht
  umgekehrt." Die Texte sind das Beste an der Anwendung, und die sieben Touren
  sind inhaltlich vorbildlich.
* **Die gestufte Tiefe** ist überall durchgehalten: kurze Vorderseite,
  „Weitere Einstellungen" dahinter.
* **Der Parameter-Dialog** erklärt sich selbst, mit Beispielen in den
  Platzhaltern („zum Beispiel breite", „= @breite/2 + 5").
* **Der Skizzeneditor rechnet richtig**: elf Bedingungen an einem Rechteck,
  Vollbestimmtheit erkannt und benannt.
* **Weg 2 hält sein Versprechen**: eine Zahl geändert, das ganze Teil folgt —
  Schraubenlöcher und Versteifung bleiben, wo sie hingehören.
* **Ehrliche Sperren**: „Dieses Projekt hat keine Parameter — ohne einen gibt
  es nichts zu variieren." „Der Chat braucht einen Zugang zu einem
  Sprachmodell. Alles andere funktioniert ohne." „Es läuft kein Generator."
  „Dieses Objekt passt bereits auf das Bett." Jede dieser Stellen sagt, warum
  gerade nichts passiert — die letzte nur an einem Ort, den man nach einer
  Menüaktion nicht ansieht (5.2).
* **Der Dialog *Ungesicherte Änderungen*** benennt seine Knöpfe nach der
  Handlung — die Vorlage für alle anderen.
* **Zusätzliche Programme** sagt bei jedem Werkzeug, wofür es gut ist, und
  dass keines Pflicht ist.
* **Material kalibrieren** erklärt in zwei Sätzen, warum gemessene Werte ins
  Profil und nicht ins Modell gehören.
