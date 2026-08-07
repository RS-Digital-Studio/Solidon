# Konzept — Solidon3D aus Kundensicht, vollständig nachgefahren

Aus zehn Bedienläufen am echten Programm, 8. August 2026. Gestartet über
`app.ui.app`, **im Vollbild** (2560 × 1369 px), bedient über den Qt-Ereignisweg
und den VTK-Interactor — also über dieselben Wege, die eine Maus nimmt. Alles
unten ist gemessen oder fotografiert, nicht abgeleitet. Wo eine erste Messung
falsch war, steht die Korrektur dabei.

**Durchgegangen:** Erstinbetriebnahme mit frischem Nutzerverzeichnis ·
Startbildschirm mit allen acht Beispielen · alle neun Menüs mit 127 Einträgen ·
alle 77 registrierten Operationen, davon 72 Dialoge einzeln geöffnet und
vermessen · Viewport mit Auswahl, Merkmalen, Kontextmenü, beiden Messarten ·
alle sieben Analysekarten · Schichtenvorschau · Objektbaum, Parameterleiste,
Verlauf, Prüfbericht, Chat, Tour · Bausteinkatalog mit Suche · Skizzeneditor ·
Kalibrieren, Einstellungen, Varianten, Tastenkürzel, Über, Fehlerbericht,
Zusätzliche Programme · Druckeinstellungen mit Profilsuche · Export in vier
Formate und das Zurücklesen · Slicer-Erkennung · Handbuch · Auto Split ·
Rückgängig · Übersetzungskatalog · alle 14 Fehlerklassen.

---

## Teil 1 — Die drei Befunde, aus denen die Arbeit folgt

### 1.1 Die Karten wachsen nicht mit dem Fenster — überall wird Text abgeschnitten

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

Links ist es ein fester Zeilendeckel. `MAX_ROWS = 12` in
[panels.py:981](app/ui/panels.py:981), gesetzt über `setFixedHeight` in
[`fit_to_rows`](app/ui/panels.py:1018). Zwölf Zeilen sind zwölf Zeilen — ob
das Fenster 800 px hoch ist oder 1369. Der Kommentar dort nennt den Grund
(„damit ein Baum mit fünfzig Teilen nicht die ganze Spalte nimmt"), und der
ist richtig; die Antwort darauf darf nur keine Konstante sein.

Rechts ist es die Höhenrechnung der Zone.
[`natural_height`](app/ui/overlay.py:160) summiert `sizeHint()` plus die
Korrektur aus `rows_height`, und `rows_height` fragt für ein `QListWidget`
über `sizeHintForRow`. Der Prüfbericht setzt aber `setWordWrap(True)`
([panels.py:756](app/ui/panels.py:756)) — ein umgebrochener Befund ist zwei
oder drei Zeilen hoch, und die Rechnung hält ihn für eine. Deshalb wird die
Zone auf einen Wert gedeckelt, der kleiner ist als ihr eigener Inhalt: bei
**fünf** Befunden steht ein Rollbalken da, mit 872 px freier Fläche daneben.

Der Chat hat das Problem in seiner reinsten Form: er hat anfangs keinen
Inhalt, also bekommt er keine Höhe — 170 px, davon 60 px Eingabefeld. Das ist
kein Chatfenster, das ist ein Briefschlitz.

**Zu tun**

1. Der Zeilendeckel wird ein Anteil der verfügbaren Höhe statt einer Zahl.
   Die drei Abschnitte links teilen sich, was übrig ist, statt es an
   `addStretch(1)` ([main_window.py:548](app/ui/main_window.py:548)) zu
   verlieren.
2. `rows_height` rechnet für umbrechende Listen mit `heightForWidth` der
   Zeile statt mit `sizeHintForRow`. Prüfbar an genau dem Fall, der jetzt
   scheitert: fünf Befunde im Prüfbericht, kein Rollbalken.
3. Chat und Prüfbericht bekommen eine Mindesthöhe, die sich am Platz
   bemisst und nicht am Inhalt. Ein leerer Chat auf 600 px sieht aus wie ein
   Chat; einer auf 170 px sieht aus wie ein Fehler.

---

### 1.2 An einem Maß zu drehen kostet neun bis fünfzehn Sekunden

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
Stelle, die der Bauplan als zweiten von drei Hauptwegen führt.

**Zu tun**

1. Messen, wohin die Zeit geht — Auswertung, Feature-Erkennung oder das
   Zurückzeichnen im Viewport. Der Cache-Treffer bei 0,75 s zeigt, dass der
   Weg *ohne* Rechnen schnell ist; die Zeit liegt also im Rechnen.
2. §31 nennt „nur betroffene Zweige". Prüfen, ob eine Höhenänderung
   tatsächlich nur die abhängigen Operationen neu rechnet oder alle sieben.
3. Bis das gelöst ist: die Vorschau während des Ziehens in Entwurfsqualität
   und das Feine erst beim Loslassen — §31 sieht die zwei Stufen vor.

---

### 1.3 Der Prozess stirbt gelegentlich mitten in der Arbeit

In diesem Audit einmal in zehn Läufen: nach einer Parameteränderung eine
Zugriffsverletzung in `rtree`, unmittelbar danach

```
SystemError: setobject.c:2676: bad argument to internal function
```

in [features.py:261](app/core/perceive/features.py:261) — beim Nachschlagen in
einem gewöhnlichen Python-Set. Danach ein Segmentation fault, der Prozess weg.

Der Code kennt die Ursache und sagt es offen
([mesh.py:169](app/core/geom/mesh.py:169)): rtree greift „reproduzierbar
daneben — eine Zugriffsverletzung in etwa jedem zwanzigsten Lauf". Der
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

---

## Teil 2 — Weitere Befunde

### 2.1 Das Kontextmenü im Bild bietet zwei Einträge

Rechtsklick auf einen Körper, mit und ohne Auswahl, öffnet ein Menü mit
**„Ausblenden"** und **„Alles andere ausblenden"**. Sonst nichts.

§18.5 sieht dort die Operationen aus `applies_to` vor — den Weg, auf dem man
etwas tut, ohne den Namen des Merkmals zu kennen. Das Menü wird korrekt aus
`object_tree.context_menu()` geholt
([main_window.py:2665](app/ui/main_window.py:2665)); es steht nur nichts darin.
Wer eine Bohrung senken will, geht weiter über die Menüleiste.

### 2.2 „Bohrung setzen" öffnet auf einem Punkt neben dem Teil

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

---

## Teil 4 — Vorschlag zur Reihenfolge

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
