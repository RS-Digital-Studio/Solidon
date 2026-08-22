# Konzept — Solidon3D aus Kundensicht, vollständig nachgefahren

Aus zehn Bedienläufen am echten Programm, 8. August 2026. Gestartet über
`app.ui.app`, **im Vollbild** (2560 × 1369 px), bedient über den Qt-Ereignisweg
und den VTK-Interactor — also über dieselben Wege, die eine Maus nimmt. Alles
unten ist gemessen oder fotografiert, nicht abgeleitet. Wo eine erste Messung
falsch war, steht die Korrektur dabei.

> **Stand 08.08.2026, nachrecherchiert am 19.08.2026.** Die Befunde 1.1 bis 2.6
> sind behoben, jeder mit Test
> und am laufenden Fenster nachgemessen; die Zahlen dazu stehen im
> [Nachtrag](#nachtrag--was-daraus-wurde-08082026-derselbe-tag) am Ende dieser
> Datei. 2.7 stand hier bis zum 22.08.2026 als offene Design-Frage — welche
> Operationen ein Tastenkürzel verdienen. **Sie ist entschieden:** vierzehn von
> 86 Operationen tragen heute eines (`Ctrl+B` Bohrung, `Ctrl+H` Aushöhlen,
> `Ctrl+D` Duplizieren, `Del`, `F2` und weitere), dazu `Alt+1` bis `Alt+8` für
> die acht Werkzeuge. **Damit ist kein Punkt dieses Dokuments mehr offen.**
>
> | Befund | Stand |
> |---|---|
> | 1.1 Karten wachsen nicht mit | behoben — `b017fde` |
> | 1.2 Parameteränderung 9–15 s | behoben — `b3de01e` |
> | 1.3 rtree reißt den Prozess | behoben — dieselbe Ursache wie 1.2 und 2.6 |
> | 2.1 Kontextmenü mit zwei Einträgen | behoben — `0c80417` |
> | 2.2 Bohrung öffnet auf dem Ursprung | behoben — `06e5e56` |
> | 2.3 Grund-Spalte abgeschnitten | behoben |
> | 2.4 Vorzeigebeispiel mit zwei Warnungen | behoben — `22ce4c6` |
> | 2.5 STEP im Exportdialog | behoben |
> | 2.6 Erstes Öffnen dauert acht Sekunden | behoben — 8,0 → 1,55 s |
> | 2.7 Sechs von 77 mit Tastenkürzel | entschieden — vierzehn von 86 Operationen tragen ein Kürzel, dazu `Alt+1`–`Alt+8` für die Werkzeuge (geprüft 22.08.2026) |
>
> Nachgereicht am selben Tag: die Karte wuchs weiterhin nicht, wenn Befunde
> **nach** der Auswertung dazukamen — im Handbuchbild acht im Kopf gezählt,
> zwei zu sehen (`f49a7fa`).
>
> **Elf Tage später, 19.08.2026:** Die Behebungen halten, keine ist
> zurückgenommen, jede trägt ihren Test — `tests/test_overlay.py:332`
> `test_a_wrapped_finding_is_measured_at_its_real_height`, `:363`
> `test_findings_that_arrive_later_make_the_card_grow`, `:408`
> `test_a_card_uses_the_room_a_tall_window_offers`, `:439`
> `test_one_action_moves_a_card_once`, dazu `tests/test_analysis_ui.py:412`
> und `:432` für die beiden Kontextmenüs. Was **nicht** hält, sind die
> Zählungen: 295 Commits liegen dazwischen, und fast jede Zahl unten ist heute
> eine andere. Zwei davon waren schon am 08.08. keine Zählung, sondern eine
> Fehlzählung — die 23 Bausteine und die 42 Kürzelgruppen (siehe Teil 3). Der
> heutige Wert steht jeweils daneben; die Sammelübersicht am Ende unter
> [Nachrecherchiert am 19.08.2026](#nachrecherchiert-am-19082026).

**Durchgegangen:** Erstinbetriebnahme mit frischem Nutzerverzeichnis ·
Startbildschirm mit allen acht Beispielen (heute neun — `weg4-figur-formen.p3d`
kam am 14.08.2026 dazu, `5a9418c`) · alle neun Menüs mit 127 Einträgen (heute
136) · alle 77 damals registrierten Operationen (heute 85), davon 72 Dialoge
einzeln geöffnet und
vermessen (heute 80 mit Dialog, fünf ohne) · Viewport mit Auswahl, Merkmalen,
Kontextmenü, beiden Messarten ·
alle sieben Analysekarten · Schichtenvorschau · Objektbaum, Parameterleiste,
Verlauf, Prüfbericht, Chat, Tour · Bausteinkatalog mit Suche · Skizzeneditor ·
Kalibrieren, Einstellungen, Varianten, Tastenkürzel, Über, Fehlerbericht,
Zusätzliche Programme · Druckeinstellungen mit Profilsuche · Export in vier
Formate und das Zurücklesen · Slicer-Erkennung · Handbuch · Auto Split ·
Rückgängig · Übersetzungskatalog · alle 14 Fehlerklassen.

---

## Teil 1 — Die drei Befunde, aus denen die Arbeit folgt

### 1.1 Die Karten wachsen nicht mit dem Fenster — überall wird Text abgeschnitten

> **Behoben am 08.08.2026** (`b017fde`). Beide Rechnungen fragten nach der
> Höhe und bekamen eine Antwort, die den Inhalt nicht kannte: `sizeHintForRow`
> kennt den Wortumbruch nicht, und der Zeilendeckel war eine Konstante.

Das ist der Befund, den man auf jedem Bildschirmfoto sieht, und er trifft jede
Zone des Fensters gleichzeitig. Gemessen im Vollbild, also dort, wo am meisten
Platz da ist:

| Karte | ist hoch | Inhalt braucht | verfügbar | Folge |
|---|---|---|---|---|
| Objektbaum, aufgeklappt | 321 px | 751 px | 1188 px | 430 px fehlen, Rollbalken |
| Parameter (vier Maße) | — | — | — | „Wandstärke" halb abgeschnitten |
| Verlauf (sieben Schritte) | — | — | — | „Beschriftung" abgeschnitten |
| Prüfbericht, 5 Befunde | 316 px | mehr als 316 | 1188 px | Rollbalken bei fünf Zeilen |
| Prüfbericht, 20 Befunde | 826 px | mehr als 826 | 1188 px | 13 von 20 lesbar |
| Chat | 170 px | — | 1188 px | Eingabefeld 211 × 60 px |
| Tour | 336 px | 349 px | 1188 px | jeder Schritt endet auf „…" |

Die linke Karte ist dabei **1129 px hoch** und unten zu einem Viertel leer,
während der Objektbaum darüber scrollt. Leerraum und abgeschnittener Inhalt
in derselben Karte, übereinander.

**Zwei Ursachen, beide belegbar.**

Links ist es ein fester Zeilendeckel. `MAX_ROWS = 12` in `app/ui/panels.py`
(am 08.08. Zeile 981, heute 1483), gesetzt über `setFixedHeight` in
`panels.fit_to_rows` (heute `panels.py:1522`). Zwölf Zeilen sind zwölf Zeilen — ob
das Fenster 800 px hoch ist oder 1369. Der Kommentar dort nennt den Grund
(„damit ein Baum mit fünfzig Teilen nicht die ganze Spalte nimmt"), und der
ist richtig; die Antwort darauf darf nur keine Konstante sein.

Rechts ist es die Höhenrechnung der Zone. `overlay.natural_height` (am 08.08.
Zeile 160, heute `overlay.py:258`) summiert `sizeHint()` plus die
Korrektur aus `rows_height`, und `rows_height` fragt für ein `QListWidget`
über `sizeHintForRow`. Der Prüfbericht setzt aber `setWordWrap(True)`
(am 08.08. `panels.py:756`, heute `panels.py:1095`) — ein umgebrochener Befund ist zwei
oder drei Zeilen hoch, und die Rechnung hält ihn für eine. Deshalb wird die
Zone auf einen Wert gedeckelt, der kleiner ist als ihr eigener Inhalt: bei
**fünf** Befunden steht ein Rollbalken da, mit 872 px freier Fläche daneben.

Der Chat hat das Problem in seiner reinsten Form: er hat anfangs keinen
Inhalt, also bekommt er keine Höhe — 170 px, davon 60 px Eingabefeld. Das ist
kein Chatfenster, das ist ein Briefschlitz.

**Zu tun**

1. Der Zeilendeckel wird ein Anteil der verfügbaren Höhe statt einer Zahl.
   Die drei Abschnitte links teilen sich, was übrig ist, statt es an
   `addStretch(1)` (am 08.08. `main_window.py:548`, heute `main_window.py:845`)
   zu verlieren.
2. `rows_height` rechnet für umbrechende Listen mit `heightForWidth` der
   Zeile statt mit `sizeHintForRow`. Prüfbar an genau dem Fall, der jetzt
   scheitert: fünf Befunde im Prüfbericht, kein Rollbalken.
3. Chat und Prüfbericht bekommen eine Mindesthöhe, die sich am Platz
   bemisst und nicht am Inhalt. Ein leerer Chat auf 600 px sieht aus wie ein
   Chat; einer auf 170 px sieht aus wie ein Fehler.

> **Erledigt — und die beschriebene Ursache gibt es nicht mehr.** `rows_height`
> misst heute über `visualRect` statt über `sizeHintForRow` allein
> (`app/ui/overlay.py:238`), und `MAX_ROWS` ist kein Deckel mehr, sondern die
> Rückfallzahl für den Fall, dass die Überlagerung gar keinen Raum zugeteilt
> hat: `panels.py:1541` rechnet
> `ceiling = room if room is not None else chrome + MAX_ROWS * row_height`
> (`b017fde`, 08.08.2026; nachgereicht `f49a7fa`). Geprüft am 19.08.2026.

---

### 1.2 An einem Maß zu drehen kostet neun bis fünfzehn Sekunden

> **Behoben am 08.08.2026** (`b3de01e`). 14,6 von 15,9 Sekunden lagen in
> `trimesh.proximity.on_surface`, gerufen aus der Slot-Übertragung — 113168
> Anfragen an einen rtree-Index für eine Beschriftung.

§31 setzt für „Parameteränderung → sichtbares Ergebnis" **unter 2 s, nur
betroffene Zweige". §2.2 beschreibt Weg 2 mit „an den Hauptmaßen drehen, das
Modell folgt sofort". Gemessen an `dose-mit-deckel.p3d` — sieben Operationen,
zwei Körper, das kleinste denkbare Projekt:

| Änderung | Dauer |
|---|---|
| `hoehe` 40 → 60 | **14,75 s** |
| `hoehe` 60 → 45 | **9,49 s** |
| `hoehe` 45 → 40 | 0,75 s |

Der dritte Wert ist kein Widerspruch, sondern die Erklärung: 40 war der
Ausgangswert, das Ergebnis lag im Cache. **Jeder neue Wert kostet neun bis
fünfzehn Sekunden, jeder schon dagewesene unter einer.** Beim Drehen an einem
Maß ist jeder Wert neu — das ist die Handlung, um die es geht.

Ohne Fremdlast gemessen (1 % CPU, kein anderes Programm), dreimal
wiederholt. Das ist der Faktor fünf bis sieben über dem eigenen Budget, an der
Stelle, die der Bauplan als zweiten von drei Hauptwegen führt. *(Es sind
inzwischen **vier**: §2.2 heißt seit P16 „Vier Hauptwege"
(`3d-agent-bauplan.md:101`), und `tests/test_examples.py:23`
`test_there_is_one_example_per_way` prüft `ways == ["1","2","3","4"]`.)*

**Zu tun**

1. Messen, wohin die Zeit geht — Auswertung, Feature-Erkennung oder das
   Zurückzeichnen im Viewport. Der Cache-Treffer bei 0,75 s zeigt, dass der
   Weg *ohne* Rechnen schnell ist; die Zeit liegt also im Rechnen.
2. §31 nennt „nur betroffene Zweige". Prüfen, ob eine Höhenänderung
   tatsächlich nur die abhängigen Operationen neu rechnet oder alle sieben.
3. Bis das gelöst ist: die Vorschau während des Ziehens in Entwurfsqualität
   und das Feine erst beim Loslassen — §31 sieht die zwei Stufen vor.

> **Erledigt, und seither ein zweites Mal angefasst.** `b3de01e` (08.08.2026)
> nahm die 113168 Anfragen aus der Slot-Übertragung heraus. Am 18.08.2026 kam
> `61d863d` dazu: „Die Live-Vorschau rechnete den ganzen Stapel neu, obwohl ihr
> Docstring seit jeher das Gegenteil zusagt … Der Aufruf reichte ihn nie durch"
> (`ROADMAP.md:6514`). Die 1,47 s aus dem Nachtrag wurden **vor** dieser
> Änderung gemessen und sind damit ein Wert vom 08.08., kein heutiger.

---

### 1.3 Der Prozess stirbt gelegentlich mitten in der Arbeit

> **Behoben am 08.08.2026** — nicht durch eine eigene Maßnahme, sondern als
> Nebenwirkung von `b3de01e`: derselbe Vorfilter, der 1.2 und 2.6 löst, nimmt
> dem rtree-Index 99 von 100 Anfragen ab. Wer den Index kaum noch fragt, greift
> auch kaum noch daneben.

In diesem Audit einmal in zehn Läufen: nach einer Parameteränderung eine
Zugriffsverletzung in `rtree`, unmittelbar danach

```
SystemError: setobject.c:2676: bad argument to internal function
```

in `app/core/perceive/features.py` (am 08.08. Zeile 261; die Zeile ist seither
verschoben, die Datei zählt heute 478) — beim Nachschlagen in
einem gewöhnlichen Python-Set. Danach ein Segmentation fault, der Prozess weg.

Der Code kannte die Ursache und sagte es offen (am 08.08. `mesh.py:169`): rtree
greift „reproduzierbar
daneben — eine Zugriffsverletzung in etwa jedem zwanzigsten Lauf". *(Der Satz
steht dort nicht mehr: `app/core/geom/mesh.py:182–189` nennt heute 113168 → 1180
Anfragen und „sechzig Auswertungen ohne Fehlgriff".)* Der
Wiederholversuch an einer Kopie ist die richtige Antwort auf den *Aufruf*.
Er heilt aber nicht den Speicher: wenn eine Fremdbibliothek in fremde Seiten
schreibt, fällt kurz darauf etwas anderes um — hier ein Set, das mit Geometrie
nichts zu tun hat.

Die Warnung „proximity query stumbled over its index" erschien in vier der
zehn Läufe, der Absturz in einem. Die automatische Sicherung samt
Wiederherstellungsfrage beim Start ist die Milderung und funktioniert — die
laufende Sitzung ist trotzdem fort.

**Zu tun**

1. Feststellen, welcher Aufruf den Index baut, und ob er sich vermeiden
   lässt. `trimesh` benutzt rtree für die Nachbarschaftssuche; wo nur der
   nächste Punkt auf der Oberfläche gebraucht wird, gibt es Wege ohne Index.
2. Ist er nicht zu vermeiden: den Index in einem eigenen Prozess halten.
   Eine Zugriffsverletzung dort kostet einen Aufruf, nicht die Sitzung.
3. Die Häufigkeit belegen statt schätzen: denselben Ablauf hundertmal fahren
   und zählen. „Jeder zwanzigste Lauf" steht als Kommentar im Code und ist
   die einzige Zahl, die es dazu gibt.

> **Erledigt über Weg 1 — der Index wird kaum noch gefragt.** Statt ihn in einen
> eigenen Prozess zu legen, fällt er weitgehend weg: 113168 → 1180 Anfragen je
> Auswertung, 0 Fehlgriffe in 60 Läufen (`app/core/geom/mesh.py:182–189`). Die
> Häufigkeit ist damit gezählt, nicht mehr geschätzt — aber nur *nach* dem
> Vorfilter. **Offen bleibt**, wie oft libspatialindex daneben greift, wenn man
> ihn oft fragt: die Recherche vom 19.08.2026 hat zum Fehlerbild von rtree /
> libspatialindex nichts gefunden, die „jeder zwanzigste Lauf" bleiben eine
> Beobachtung dieses Hauses ohne Beleg von außen.

---

## Teil 2 — Weitere Befunde

### 2.1 Das Kontextmenü im Bild bietet zwei Einträge

> **Behoben am 08.08.2026** (`0c80417`). `_feature_kind` las die Spalte mit
> dem Maß statt der mit der Art; ein Durchmesser als Merkmalsart findet
> zuverlässig keine Operation.

Rechtsklick auf einen Körper, mit und ohne Auswahl, öffnet ein Menü mit
**„Ausblenden"** und **„Alles andere ausblenden"**. Sonst nichts.

§18.5 sieht dort die Operationen aus `applies_to` vor — den Weg, auf dem man
etwas tut, ohne den Namen des Merkmals zu kennen. Das Menü wird korrekt aus
`object_tree.context_menu()` geholt
([main_window.py:2665](app/ui/main_window.py:2665)); es steht nur nichts darin.
Wer eine Bohrung senken will, geht weiter über die Menüleiste.

### 2.2 „Bohrung setzen" öffnet auf einem Punkt neben dem Teil

> **Behoben am 08.08.2026** (`06e5e56`). Die Vorgabe ist jetzt die Mitte der
> obersten Fläche des gewählten Körpers; ein angeklicktes Merkmal gewinnt.

Der Dialog kommt mit `x = 0,00 · y = 0,00 · z = 0,00 · depth = 0,00` — auch
wenn ein Körper ausgewählt und vorher eine Fläche angeklickt wurde. Ob das
trifft, hängt daran, wo das Teil liegt:

| Projekt | Hüllquader | Ursprung im Teil | Ergebnis |
|---|---|---|---|
| `weg1-halterung-anpassen` | x −40…40, y −25…25 | ja | Bohrung greift |
| `dose-mit-deckel` | x −120…−40, y −120…−65 | **nein, 65 mm daneben** | „Der Schnitt hat nichts abgetragen" |

Das zweite ist der Normalfall, nicht die Ausnahme: sobald „Auf dem Bett
anordnen" gelaufen ist — und das gehört zu jeder Druckvorbereitung — liegt
das Teil im negativen Quadranten, und die Vorgabe des Dialogs zeigt ins Leere.

Die Anwendung meldet es danach sauber und mit Handlungsvorschlag („Position
prüfen oder an einer Fläche ausrichten"). Der Vorschlag kommt nur eine
Operation zu spät.

**Zu tun:** Vorgabe ist die Mitte der obersten Fläche des gewählten Körpers,
nicht der Ursprung. Ist ein Merkmal angeklickt, ist es dessen Ort.

### 2.3 Im Druckeinstellungs-Dialog ist der Grund abgeschnitten

Die Tabelle „Was dieses Teil verlangt" hat drei Spalten — Einstellung,
Vorschlag, Grund — und die dritte endet in jeder Zeile auf „…":

> „Das Projekt hat Passungen. …" · „Hohe Beschleunigung schwi…" ·
> „Die Außenwand zuerst zu le…"

Der Grund ist das, was den Vorschlag rechtfertigt. Der Dialog ist 561 px
breit auf einem 2560 px breiten Bildschirm; die Mindestbreite steht auf 560
([print_settings_dialog.py:763](app/ui/print_settings_dialog.py:763)).

**Zu tun:** Die Tabelle bekommt die Breite, die ihre dritte Spalte braucht,
oder der Grund wandert in eine zweite Zeile unter den Vorschlag.

### 2.4 Das Vorzeigebeispiel öffnet mit zwei Warnungen

`dose-mit-deckel.p3d` ist das Beispiel „Alles zusammen". Beim Öffnen stehen
fünf Befunde im Prüfbericht, davon zwei Warnungen:

- `boolean.without_effect` — „Der Schnitt hat nichts abgetragen — das
  Werkzeug liegt neben dem Körper."
- `fit.violated` — „Die Passung sitzt loser als vorgesehen."

Die Tour erklärt die zweite ausdrücklich („Deshalb steht die Passung auch im
Prüfbericht"). Die erste erklärt niemand — ein Schnitt im mitgelieferten
Projekt, der nichts tut. Wer das Beispiel öffnet, um zu sehen, was Solidon
kann, sieht zuerst, dass etwas nicht stimmt.

**Zu tun:** Entweder die Operation im Beispiel richtigstellen, oder sie
entfernen. Ein Beispiel ist Dokumentation (§37.2), und eine Warnung darin ist
eine Aussage.

### 2.5 STEP steht im Exportdialog und geht bei Netzen nie

Der Exportdialog bietet vier Formate an: STL, 3MF, OBJ, STEP. Die ersten drei
schreiben und lesen sich sauber zurück:

| Format | geschrieben | Rücklauf |
|---|---|---|
| STL | 2 Dateien, 2005 KB, 0,01 s | 3 Körper, „Doppelte Punkte wurden verschweißt" |
| 3MF | 2 Dateien, 321 KB, 0,28 s | 3 Körper |
| OBJ | 2 Dateien, 1544 KB, 0,04 s | 3 Körper |
| STEP | — | `NeedsSolidError` |

Die Fehlermeldung ist vorbildlich: „STEP hält Flächen und Kanten fest. Ein
Netz hat keine — dafür bleiben STL und 3MF." Sie kommt nur, nachdem der Nutzer
Format, Ordner und Namen gewählt hat.

**Zu tun:** Formate, die für die aktuelle Auswahl nicht gehen, stehen
ausgegraut im Dialog, mit demselben Satz als Hinweis daneben.

### 2.6 Der erste Ladevorgang dauert acht Sekunden, jeder weitere eine halbe

§31 setzt „Projekt öffnen aus Plattencache unter 1 s". Gemessen:

- **erstes Öffnen in einer frischen Sitzung: 7,9–8,3 s** (dreimal
  reproduziert, verschiedene Läufe)
- jedes weitere Öffnen im selben Prozess: 0,2–0,4 s

Die 8 s sind also nicht das Auswerten, sondern das, was beim ersten Rechnen
nachgeladen wird — trimesh, manifold3d, die Netzbibliotheken. Der Kunde
erlebt das genau einmal pro Sitzung, aber immer an derselben Stelle: beim
ersten Klick auf ein Beispiel, mit leerem Fenster davor.

**Zu tun:** Die schweren Einfuhren während des Startbilds anstoßen statt beim
ersten Öffnen. Der Ladebildschirm läuft ohnehin und hat dort noch Luft.

### 2.7 Sechs von 77 Operationen haben ein Tastenkürzel

Das Register führt 77 Operationen, alle in Menüs erreichbar, keine tiefer als
zwei Ebenen. Sechs davon tragen ein Kürzel. Für ein Programm, das mit CAD
verglichen wird, ist das wenig — dort ist die Tastatur der schnelle Weg.

Die Belegung ist umschaltbar („default" und „fusion",
[shortcut_schemes.py](app/ui/shortcut_schemes.py)), das Gerüst steht also.

---

## Teil 3 — Was trägt

Das gehört ins selbe Dokument, sonst liest sich die Liste oben wie eine
Bilanz, und die wäre falsch.

**Die Erstinbetriebnahme ist fertig.** Frisches Nutzerverzeichnis, Dialog
520 × 474 px, alle drei Auswahllisten vorbelegt, alle vier externen Programme
richtig erkannt (OpenSCAD, ElegooSlicer, Ollama gefunden; ComfyUI fehlt und
sagt es). Der Zustand wird gemerkt. Regel 18 eingehalten: „gefunden" und
„fehlt" stehen als Wort und als Zeichen da, nicht als Farbe.

**Der Operationskatalog ist vollständig und konsistent.** 77 Operationen, alle
in Menüs, alle mit Titel, Erklärsatz und Knopfkasten. 72 Dialoge einzeln
geöffnet: keiner defekt, keiner ohne Fenstertitel, keiner höher als 427 px,
alle 380 px breit. Fünf Operationen laufen ohne Dialog sofort — genau die,
bei denen es nichts zu fragen gibt (Regel 19).

**Der Viewport nimmt Klicks an.** Klick auf den Körper wählt `obj_2` und das
Merkmal `face_7`, der Objektbaum folgt, ein Klick daneben hebt auf. Vier von
fünf Klicks auf verschiedene Flächen treffen ihr Merkmal. Der frühere Befund
aus `konzept-bedienung.md` ist erledigt; der `vtkCellPicker` trägt.

**Messen trägt, beide Arten.** Abstand zwischen zwei Punkten: 48,91 mm.
Wandstärke mit einem Klick: 2,0 mm. *(Eine erste Messung meldete hier einen
Fehler — der zweite Klick war danebengegangen. Nachgefahren mit Punkten, die
beide einen Weltpunkt liefern, trägt es.)*

**Die Analysen sind im Budget.** Alle sieben Karten — Wandstärke, Überhang,
Netzfehler, Krümmung, Feature-Zuordnung, Passungen, Stützbedarf — je 1,41 bis
1,51 s, im Hintergrund. §31 erlaubt 3 s. Die Schichtenvorschau steht nach
2,67 s mit 200 Schichten. Auto Split braucht 1,77 s.

**Die Druckeinstellungen finden von selbst das Richtige.** 1001 Maschinen,
7 Prozesse, 42 Filamente aus dem Bestand des Slicers, und vorbelegt sind
*Elegoo Centauri Carbon 2 0.4 nozzle · 0.20mm Standard @Elegoo CC2 · Elegoo
PETG @ECC2* — die drei, die zusammengehören. Acht Reiter, 54 beschriftete
Felder, dazu die Vorschlagstabelle mit Übernahme-Knopf. Der Slicer wird als
Orca-Familie erkannt.

**Die Sprache ist vollständig.** 1986 Einträge im englischen Katalog, keiner
leer. Kein einziger Registertext — Titel, Erklärsatz, Parameterbeschriftung —
ohne englische Entsprechung.

**Fehler enden nie mit „fehlgeschlagen".** Alle 14 Fehlerklassen tragen
zwischen einem und vier Handlungsvorschlägen, keine offenen Platzhalter in
Titel oder Grund. Regel 17 hält.

**Und der Rest der Oberfläche steht.** Bausteinkatalog mit 23 Bausteinen und
funktionierender Suche, jeder Eintrag mit „− nimmt Material weg" als zweiter
Kodierung. Skizzeneditor mit 24 Werkzeugen auf voller Fläche. Handbuch mit 33
Kapiteln in 2,5 s. Tastenkürzel-Fenster mit 42 Gruppen. Rückgängig stellt den
Stapel wieder her (7 → 8 → 7). Die Abfrage beim Schließen mit ungesicherten
Änderungen ist richtig — Schließen ist nicht rücknehmbar.

> **Zwei dieser vier Zahlen zählen Baumzeilen, nicht Dinge — und taten das
> schon am 08.08.** Der Katalog baut einen Baum aus Gruppen
> (`app/ui/catalog.py:157–162`): 16 Bausteine unter 7 Gruppenköpfen ergaben
> genau die 23 gezählten Zeilen. Es waren nie 23 Bausteine; heute sind es
> **17 in sieben Gruppen**. Dasselbe beim Kürzel-Fenster: 36 Kürzelzeilen
> plus 6 fettgedruckte Gruppenköpfe (`app/ui/shortcuts_window.py:100–110`)
> sind 42 Baumzeilen — es sind **sechs** Gruppen, nicht 42.
>
> Von den anderen beiden ist eine gewachsen und eine nicht mehr
> nachvollziehbar: Das Handbuch hat heute **40 Kapitel** (`manual.pages()`).
> Der Skizzeneditor trägt 15 Werkzeugknöpfe, 8 Einträge in deren
> Aufklappmenüs und 10 Bedingungsknöpfe; welche Teilmenge davon 24 ergab,
> lässt sich nicht rekonstruieren.
>
> Richtig hieße der Satz: „Bausteinkatalog mit 17 Bausteinen in sieben
> Gruppen · Skizzeneditor mit 15 Werkzeugen und 10 Bedingungen · Handbuch mit
> 40 Kapiteln · Tastenkürzel-Fenster mit 36 Tasten in sechs Gruppen."

---

## Teil 4 — Vorschlag zur Reihenfolge

> **Alle sechs Punkte sind abgearbeitet — diese Liste ist Geschichte, keine
> Arbeit.** Sie steht hier als Begründung der Reihenfolge, in der gebaut
> wurde. Wer sie als Rückstand liest, liest sie falsch: Der Nachtrag am Ende
> desselben Dokuments meldete schon am 08.08.2026 alle Befunde 1.1 bis 2.6
> als behoben, und die Behebungen halten bis heute (19.08.2026, nachgeprüft
> an `main`). Die Belege stehen bei den Befunden selbst; die Sammelstelle ist
> `ROADMAP.md`, Abschnitt „Aus Kundensicht vollständig nachgefahren".

1. **Die Höhenrechnung der Karten** (1.1). Ein Tag Arbeit, sichtbar auf jedem
   Bildschirmfoto, betrifft jede Zone. Prüfbar an fünf Befunden ohne
   Rollbalken.
2. **Die Vorgabe von „Bohrung setzen"** (2.2). Kleiner Eingriff, verhindert
   die häufigste stille Fehlbedienung.
3. **Die Wartezeit bei Parameteränderungen** (1.2). Der zweite von drei
   Hauptwegen hängt daran. Erst messen, wohin die Zeit geht.
4. **Das Kontextmenü füllen** (2.1). Es ist der im Bauplan vorgesehene Ort
   für Weg 1, und der Aufhänger steht schon.
5. **Die Ladezeit beim ersten Öffnen** (2.6). Verschieben statt beschleunigen.
6. **Der rtree-Absturz** (1.3). Der schwerste, aber auch der aufwendigste —
   und der einzige, den eine automatische Sicherung schon abfedert. Zuerst
   die Häufigkeit belegen.

Dahinter: die abgeschnittene Grund-Spalte (2.3), das Beispiel mit der
wirkungslosen Booleschen (2.4), STEP im Exportdialog (2.5), Tastenkürzel (2.7).

---

## Anhang — wie gemessen wurde

Zehn Läufe über ein Fahrgerüst, das die Anwendung mit **echter Qt-Plattform**
startet (offscreen hat auf dieser Maschine null Schriftfamilien) und
`showMaximized()` benutzt, damit die Größenverhältnisse denen entsprechen, vor
denen ein Nutzer sitzt. Ein Wachhund auf `activeModalWidget` und
`activePopupWidget` protokolliert und schließt, was sonst den Lauf anhält —
ein `QMenu.exec()` blockiert wie ein modaler Dialog, ist aber keiner.

Geklickt wird über den VTK-Interactor (`SetEventPosition` +
`InvokeEvent("LeftButtonPressEvent")`), also durch dieselbe Stilklasse, die
auch eine echte Maus durchläuft. Operationen laufen über
`window.run_operation(spec)` — der Weg des Menüklicks, samt Vorbelegung,
Vorschau und Transaktion.

Bildschirmfotos über `screen().grabWindow()` und nicht über `widget.grab()`:
der Qt-Painter weiß nichts von dem, was OpenGL in den Viewport gezeichnet hat.

Ohne Fremdlast gemessen — 1 % CPU-Last über alle Läufe, kein anderes Programm.
Das war hier schon einmal die Ursache falscher Leistungsbefunde und wurde
deshalb vorher geprüft.

---

## Nachtrag — was daraus wurde (08.08.2026, derselbe Tag)

Alle Punkte aus Teil 1 bis 2.6 sind behoben, jeder mit Test und jeder am
laufenden Fenster nachgemessen. Was sich geändert hat, in Zahlen:

| Gemessen | vorher | nachher |
|---|---|---|
| Prüfbericht, 5 Befunde | 316 px, Rollbalken | 322 px, kein Rollbalken |
| Objektbaum aufgeklappt | 321 px bei 751 Bedarf | 873 px bei 871 Bedarf |
| Chat, Zone / Verlauf | 170 / 49 px | 334 / 203 px |
| Tour, Rollbereich | 139 von 152 px | 139 von 139 px |
| Parameteränderung | 8,3 s (9–15 s je neuem Wert) | **1,47 s** |
| Erstes Öffnen einer Sitzung | 8,0 s | **1,55 s** |
| rtree-Anfragen je Auswertung | 113 168 | **1 180** |
| rtree-Fehlgriffe in 60 Läufen | ~3 erwartet | **0** |
| Kontextmenü am Merkmal | 2 Einträge | 6 (die vier aus `applies_to`) |
| Kontextmenü am Körper | 59 Einträge | 7 (nach Kategorie gruppiert) |
| „Bohrung setzen" an der Dose | 0,00 / 0,00 / 0,00 | −82,23 / −93,06 / 40,05 |
| Beispiele mit Warnung | 2 | 1 (das Reparatur-Beispiel, gewollt) |

**Die eine Ursache hinter dreien.** 1.2 (Wartezeit), 1.3 (Absturz) und 2.6
(erstes Öffnen) hingen an derselben Stelle: die Slot-Übertragung suchte für
jedes Dreieck des Ergebnisses den Abstand zu jeder Quelle. Bei der Dose waren
das vierzigtausend Dreiecke gegen eine Beschriftung aus sechshundert — und die
Grenze, ab der ein Dreieck nicht mehr auf einer Oberfläche liegt, sind zwei
Zehntel Millimeter. Für fast alle stand das Ergebnis vorher fest. Der
Vorfilter ist keine Näherung: über vier Beispielprojekte und dreiunddreißig
Aufrufe stimmt jedes Dreieck mit der alten Rechnung überein.

**Eine Regression, gemeldet und behoben.** Die erste Version der Raumzuteilung
las die Höhen, die sie gerade selbst gesetzt hatte. Die linke Spalte lief
daraufhin bei jeder Aktion auf und ab — neunhundertfünf Geometriewechsel für
ein einziges Aufklappen. Gerechnet wird jetzt nur mit dem verfügbaren Raum und
dem Bedarf; beide hängen nicht an der gesetzten Höhe. Gemessen: Auswahl null
Bewegungen, Aufklappen eine, Parameteränderung null.

**Nicht geändert: die Tastenkürzel (2.7).** Sechs in der Vorgabe ist eine
Entscheidung und keine Lücke — die Belegung ist umschaltbar, und „Wie Fusion
und Onshape" bringt elf Ein-Tasten-Kürzel für alle, die aus einem CAD kommen.
Wer die Vorgabe erweitern will, entscheidet damit, welche Operationen ein
Kürzel *verdienen*; das ist eine Design-Frage und keine Reparatur.

**Nebenbei aufgefallen:** `test_the_slider_reports_a_factor` legte ein
`processEvents` zwischen die Reglerstufen und das Auslösen von Hand. Dauerte
das länger als die 120 ms der Entprellung — und unter der vollen Suite tut es
das —, feuerte der Zeitgeber dort schon und das Signal kam zweimal. Allein
grün, in der Suite rot. Er prüft jetzt, dass etwas angemeldet ist, nicht wie
lange es dauert.

Stand danach: **3168 Tests grün**, ruff und mypy sauber.

---

## Nachrecherchiert am 19.08.2026

Fünfzehn Aussagen dieses Dokuments über den eigenen Code nachgeprüft, 295
Commits nach seinem Stand: **drei stimmen, sieben sind überholt, zwei waren
schon am 08.08. falsch, drei sind nicht mehr prüfbar.**

**Die Befunde selbst sind nicht das Problem — sie halten alle.** Überholt sind
fast ausschließlich *Zahlen*, und das war absehbar: Ein Dokument, das den
Zustand eines Fensters zählt, altert mit jedem Commit an diesem Fenster.

**Zwei Fehlzählungen von Anfang an**, beide derselben Art: Es wurden
Baumzeilen gezählt und Dinge dazugeschrieben. 23 „Bausteine" waren 16
Bausteine unter 7 Gruppenköpfen, 42 „Kürzelgruppen" waren 36 Kürzel unter 6
Gruppenköpfen. Wer eine Baumansicht zählt, zählt die Köpfe mit.

**Ein Widerspruch im Dokument selbst:** Abschnitt 2.4 nennt `fit.violated` als
Warnung des Dose-Beispiels und erklärt, die Tour gehe absichtlich darauf ein —
der Nachtrag zählt dasselbe Beispiel dann als warnungsfrei. Es sind **zwei**
Beispiele mit Warnung, nicht eines: `weg3-generiert-aufbereiten` (drei
Warnungen, das ist sein Zweck) und `dose-mit-deckel` (`fit.violated`). Derselbe
Fehler steht in `ROADMAP.md:3400`, dort zusätzlich mit der inzwischen falschen
Acht.

**Kein einziger der neun Zeilenverweise stimmt noch.** `panels.py:981` zeigt
heute mitten in `fit_wrapped`, `main_window.py:2665` in den
Druckeinstellungs-Dialog, `overlay.py:160` vor `rows_height`. Die Lehre steht
in der Zahl: Zeilennummern in einem Dokument, das derselbe Tag schon überholt
hat, sind Zahlen mit Verfallsdatum — künftig nur noch Symbolnamen
(`panels.MAX_ROWS`, `overlay.natural_height`).

**Was gewachsen ist:** 77 Operationen → 85 (80 mit Dialog, fünf ohne) · 127
Menüeinträge → 136 · acht Beispiele → neun · 33 Handbuchkapitel → 40 · 1986
englische Katalogeinträge → 2564 · 3168 Tests → 4246. Sieben Analysekarten und
14 Fehlerklassen sind unverändert.

**Nicht mehr prüfbar und deshalb offen gelassen:** die Nachher-Messwerte
(Parameteränderung 1,47 s, erstes Öffnen 1,55 s, 1180 rtree-Anfragen, null
Fehlgriffe in 60 Läufen, die Pixelhöhen) und die Zeiten der Analysekarten. Sie
stammen aus einem Fahrgerüst mit echter Qt-Plattform im Vollbild; der Aufbau
ist hier nicht wiederholt worden, und ohne ihn wäre jede neue Zahl eine andere
Messung, kein Vergleich. Sie bleiben als datierte Messwerte stehen.
