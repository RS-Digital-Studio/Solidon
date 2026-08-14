# Konzept — Solidon3D mit den Augen eines Anfängers

Aus dreizehn Bedienläufen am echten Programm, 13. und 14. August 2026, im Vollbild
(2560 × 1369 px), plus vier Läufen über die Website im installierten
QtWebEngine. Gestartet über `build_application`, bedient über den
Qt-Ereignisweg — dieselben Wege, die eine Maus nimmt. Alles unten ist gemessen
oder fotografiert. Wo eine erste Lesart am Bild falsch war, steht die Messung,
die sie widerlegt hat.

Die Frage war nicht „ist es fertig", sondern: **Wer das hier zum ersten Mal
öffnet — sieht der, was er sehen muss?**

> **Stand 14.08.2026.** Abgearbeitet, jeder Fund mit Test und am laufenden
> Fenster nachgemessen. Offen bleiben vier, und zwar als Entscheidung.
>
> | Befund | Stand |
> |---|---|
> | 1.1 Kamera im Nullpunkt nach *Neues Projekt* | behoben — `2f56d93` |
> | 1.2 Vier Bedienelemente unter den Karten | behoben — `443058f` |
> | 1.3 Website scrollt seitlich | behoben — `61fbc01` |
> | 2.2 Chat ohne ein einziges Beispiel | behoben — `7fe7c30` |
> | 2.3 Werkzeugzeile graut nicht aus | behoben — `b07bcfb` |
> | 2.4 Warnung unsichtbar hinter dem Reiter | behoben — `46e2b7c` |
> | 3.3 Erzeugen-Op im Ändern-Menü | behoben — `8232923` |
> | 4.2 Port immer bedienbar · 4.5 Handbuchverzeichnis · 4.6 Preis auf Mobil · 4.7 englische Docstrings | behoben — `799fce5`, `9aa7df9`, `61fbc01` |
> | 5.1 Kettenabbruch verweist auf zugehaltenes Fenster | behoben — `46e2b7c` |
> | 5.2 Fehlertext der Rückfallkette | behoben — `c2bd852` |
> | 5.3 Zwei Schalter für die Schichtansicht | behoben — `b0cb0d1` |
> | 5.4 Legende aus `face_10`, Kartenname, Gradzeichen | behoben — `5902211` |
> | 5.5 Tabulator · Objektbaum ohne Anfang | behoben — `799fce5`, `9aa7df9` |
> | 5.8 Elf englische Docstrings | behoben — `799fce5`, jetzt null |
> | **2.1 Karten nutzen die Fensterhöhe nicht** | **offen** |
> | **2.5 Import landet im vorhandenen Körper** | **offen, als Entscheidung** |
> | **3.1 Verteilermenüs · 3.4 Kontextmenü** | **offen, als Entscheidung** |
> | **5.6 Kürzel für die Werkzeuge** | **offen, als Entscheidung** |
>
> Nicht behoben und bewusst so: **3.2** (alphabetische Sortierung der
> Grundformen) — sie ist eine begründete Entscheidung, die
> `test_a_menu_is_sorted_the_way_it_is_read` festhält. **4.1** (halb
> umgeschaltetes Thema nach dem Zeichenmodus) und **4.3** (Fokus sieht aus wie
> Mausüberfahrt) sind geblieben; beide brauchen mehr als eine Zeile und keinen
> Befund über sich hinaus.

Vorweg, damit die Liste unten nicht das falsche Bild gibt: Startbildschirm,
Erststart-Dialog, Operationsdialoge, Prüfbericht, Bausteinkatalog und Handbuch
sind sehr gut. Die Operationsdialoge machen es vor — Beschreibungssatz oben,
fünf Felder, „Weitere Einstellungen" zugeklappt, Hauptknopf heißt „Bohrung
setzen" und nicht „OK". Der Prüfbericht zählt oben mit („0 × Fehler · 1 ×
Warnung · 2 × Hinweis"), jeder Befund trägt Symbol *und* Farbe *und* Text. Die
Website erklärt das Programm besser, als die meisten Programme sich selbst
erklären.

Die Befunde betreffen fast alle **den leeren Anfang und die Ränder** — genau
die Stellen, an denen ein Anfänger steht und ein Kenner nie mehr hinsieht.

---

## Teil 1 — Die drei, die der erste Eindruck sind

### 1.1 Nach „Neues Projekt" steht die Kamera im Nullpunkt

Wer auf dem Startbildschirm den Hauptknopf drückt — den orangen, den
vorbelegten — bekommt eine fast leere dunkle Fläche mit einem Achsenkreuz
unten links. Keine Druckplatte, kein Bauraum, kein Maßstab. Der häufigste
zweite Gedanke dürfte sein, dass etwas kaputt ist.

Gemessen, direkt nach `start_empty()`:

| | Kameraposition | Bauraum |
|---|---|---|
| wie geliefert | `(1.0, −1.0, 0.8)` | 220 × 220 mm gesetzt |
| nach `reset_camera()` | `(474.7, −474.7, 504.7)` | dieselbe |

Die Kamera steht anderthalb Millimeter vom Ursprung entfernt in einem
220-Millimeter-Bauraum. Ein Druck auf `Pos1` („Alles einpassen") repariert es
sofort — die Druckplatte steht dann mit Raster und Maßzahlen im Bild.

Die Ursache steht in `app/ui/viewport.py:3171`: `_fit_once_for` passt nur ein,
wenn `has_objects` wahr ist. Die Startkamera wird beim Aufbau über
`view_from("iso")` gesetzt (`viewport.py:1056`) — zu einem Zeitpunkt, an dem
der Bauraum noch nicht bekannt ist. Danach kommt `show_build_volume`, aber
niemand richtet die Kamera daran aus. `reset_camera` könnte es: sein Docstring
sagt ausdrücklich „Ohne Körper bleibt der Bauraum das Maß" — er wird in diesem
Fall bloß nie gerufen.

Belege: `20-leer-wie-geliefert.png`, `21-leer-nach-einpassen.png`.

### 1.2 Im Zeichenmodus liegen vier Bedienelemente unter den schwebenden Karten

Weg 2 beginnt mit dem Knopf „Zeichnen" in der Werkzeugzeile. Was dann aufgeht,
ist links und rechts von den Karten überdeckt. Gemessen in Fensterkoordinaten:

```
Skizzenfeld       0, 69    2560 x 1269
object_tree      12, 114    332 x  120   deckt ab
parameters       12, 266    332 x   96   deckt ab
history_panel    12, 399    332 x  100   deckt ab
right          2216,  81    332 x  344   deckt ab
```

Darunter liegen konkret:

| Element | Ort | Was es ist |
|---|---|---|
| `QComboBox` | x = 284, y = 107 | **die Ebenenwahl** — worauf gezeichnet wird |
| `QPushButton` „Abstand D" | x = 284, y = 143 | die erste Zwangsbedingung |
| `QToolButton` „Rückgängig" | x = 2199, y = 70 | das Zurücknehmen im Editor |
| `QLabel` „Bedingungen" | x = 1980, y = 175 | die Überschrift der Bedingungsspalte |

Die Ebenenwahl ist laut Gebietsregel „die Angabe, die in der Projektdatei
landet" und trägt eigens die Ziffern 1, 2, 3 als Kürzel. Sichtbar ist von ihr
der rechte Rand.

Beleg: `60-zeichnen-ueberdeckung.png`, Messung im Laufprotokoll.

### 1.3 Die Website lässt sich seitlich schieben

`window.scrollTo(600, 0)` und danach `window.scrollX` abgefragt:

| Seite | Breite | scrollX danach | scrollWidth / clientWidth |
|---|---|---|---|
| `index.html` | 1440 | **111** | 1536 / 1425 |
| `index.html` | 390 | **47** | 422 / 375 |
| `handbuch.html` | 390 | **270** | 645 / 375 |

Auf dem Telefon lässt sich das Handbuch um 270 von 375 Pixeln nach rechts
schieben — drei Viertel der Bildbreite, und dort ist nichts.

Zwei verschiedene Ursachen, eine gemeinsame Lücke:

* **Was überragt.** Auf der Startseite `div.hero::before` (1646 px breit bei
  `left: −235 px`) und `div.hero::after` (1458 px bei −141 px) — die Scheine
  hinter dem Kopfbereich. Im Handbuch eine **Tabelle mit 645 px Breite**, die
  keinen eigenen Rollbereich hat.
* **Warum der vorhandene Riegel nicht greift.** `body { overflow-x: clip }`
  ist gesetzt, aber der Rollbereich gehört dem Wurzelelement, und dort steht
  `overflow-x: visible`. Gegenprobe im laufenden Browser:
  `document.documentElement.style.overflowX = 'clip'` → `scrollX` bleibt 0 auf
  allen drei Seiten.

Für die Scheine ist Abschneiden die richtige Antwort. Für die Tabelle nicht —
abgeschnitten wäre sie unlesbar; sie braucht einen eigenen `overflow-x: auto`.

---

## Teil 2 — Übersichtlichkeit auf einem großen Bildschirm

### 2.1 Die Karten nutzen die Höhe nicht, und schneiden dabei Text ab

Bei 1369 px Fensterhöhe enden die drei linken Abschnitte bei y = 499. Die
rechte Karte ist 344 px hoch. Darunter: gut 900 px leere Fläche — und
gleichzeitig schneidet die Tour ihre eigenen Schritte ab. Im Bild
`10-beispiel-weg1.png` steht Schritt 1 vollständig, die Schritte 2 bis 5 enden
je mit „…", und die Karte hat einen eigenen Rollbalken.

Das ist nicht der alte Befund „Karten wachsen nicht mit dem Inhalt" (behoben,
`b017fde`) — sie wachsen mit dem Inhalt, aber sie nehmen sich den freien Platz
darunter nicht, wenn der Inhalt mehr bräuchte als der Inhalt hergibt.

### 2.2 Der Chat ist eine leere schwarze Box

Weg 3 und das Versprechen, mit dem die Anwendung antritt. Was ein Neuling
sieht: eine Zeile „Modell: ollama:qwen3:14b", darunter 170 px Leere, darunter
ein Feld „Was soll geändert werden?" und „Senden".

Kein Beispielsatz, kein Vorschlag, keine Andeutung dessen, was dieses Ding
kann. Der Erststart-Dialog wirbt für den Chat, das Handbuch hat ein Kapitel
darüber, die Website zeigt ihn — und die Stelle selbst sagt nichts. Drei bis
vier anklickbare Beispielanfragen im leeren Zustand wären hier die billigste
gute Tat des ganzen Programms.

Beleg: `31-rechts-1.png`.

### 2.3 Die Werkzeugzeile unten graut nicht aus, die Menüs aber schon

Bei leerer Szene, ausgelesen statt abgelesen:

```
an   Schnitt      (seine Felder: AUS)
an   Messen
an   Bewegen
an   Analyse
an   Schichten
an   Bemalen
```

Die Menüs machen es vorbildlich — im selben Zustand sind alle 34 Einträge
unter *Ändern* aus, das ganze Menü *Objekt* ist aus, *Bausteine* ist aus. Das
ist §2.6, sauber umgesetzt. Die Werkzeugzeile, die dem Anfänger näher liegt
als jedes Menü, folgt derselben Regel nicht: „Bemalen" auf einer leeren Szene
ist ein Pinsel für nichts.

Dasselbe auf dem Startbildschirm: dort ist die Menüleiste auf *Datei* und
*Hilfe* reduziert — gut —, aber die Werkzeugzeile zeigt unverändert alle fünf
Knöpfe, „Speichern" und „Zeichnen" eingeschlossen. Zwei Maßstäbe in einem
Fenster.

### 2.4 Eine Warnung bleibt unsichtbar, solange eine Tour läuft

Ein fremdes Netz eingefügt, das nicht geschlossen ist. Der Prüfbericht hat es
korrekt: „Das Modell ist nicht geschlossen" als Warnung. Zu sehen ist davon
nichts — die rechte Spalte zeigt weiter die Tour, und der Reiter „Prüfbericht"
sieht aus wie vorher: kein Zähler, kein Zeichen, keine Farbe.

Dass der Sprung der aktiven Tour den Reiter lässt, ist die richtige
Entscheidung (sie steht so in der Gebietsregel). Dann muss aber der Reiter
selbst sprechen — „Prüfbericht · 1 ⚠" statt „Prüfbericht".

Belege: `62-fremdmodell-befunde.png` gegen `ausschnitt-bericht.png`.

### 2.5 Ein eingefügtes Modell landet im vorhandenen Körper

Dasselbe Netz steckte nach dem Einfügen halb in der Platte und halb unter dem
Bett. Beides wird gemeldet („Ein Objekt steckt unter der Druckplatte"), keines
wird behoben. *Objekt → Auf dem Bett anordnen* gibt es, es läuft nur nicht von
selbst. Beim ersten Einfügen ist das die Sorte Überraschung, die man sich
selbst zuschreibt.

---

## Teil 3 — Wo die Menüs einen Anfänger im Stich lassen

### 3.1 Zwei Menüs sind reine Verteiler

*Erzeugen* enthält vier Einträge, alle vier sind Untermenüs. *Ändern* enthält
sieben, alle sieben sind Untermenüs. *Vorbereiten* enthält zwei, beide
Untermenüs — eines davon heißt „Druckvorbereitung", also fast wie sein
Elternmenü.

Wer einen Quader will, klickt dreimal: Erzeugen → Grundformen → Quader
anlegen. „Grundformen" hat vier Zeilen; die Grenze liegt bei zwölf.

### 3.2 „Grundformen" sortiert alphabetisch und mischt Fremdes hinein

```
Kugel anlegen
OpenSCAD-Teil anheften
Quader anlegen
Zylinder anlegen
```

Der häufigste Fall steht an dritter Stelle, und an zweiter steht ein
Expertenwerkzeug, das mit „Grundform" nichts zu tun hat. Alphabetisch ist eine
Sortierung, die keine Frage beantwortet.

### 3.3 Ein Erzeugen-Eintrag lebt im Ändern-Menü

*Ändern → Formgebung* bei leerer Szene, ausgelesen:

```
AUS  Exakt aushöhlen
an   Exakten Gewindebolzen erzeugen      <— der einzige aktive Eintrag
AUS  Fase anbringen
AUS  Fläche versetzen
AUS  Formschräge anstellen
AUS  Verrunden
```

Ein Gewindebolzen ist ein neuer Körper, keine Formgebung — deshalb ist er als
Einziger anklickbar, wenn nichts da ist, was man formen könnte. Er gehört
unter *Erzeugen*, und dann stimmt auch, dass *Formgebung* auf leerer Szene
komplett aus ist.

### 3.4 Das Kontextmenü ist die Menüleiste in alphabetischer Reihenfolge

Rechtsklick auf den gewählten Körper:

```
Ausblenden · Alles andere ausblenden · Bausteine ▸ · Erzeugen ▸ ·
Objekt ▸ · Vorbereiten ▸ · Ändern ▸
```

Fünf Untermenüs, alphabetisch, dieselben wie oben. Die Gebietsregel sagt, dass
`applies_to` das Kontextmenü sortiert — auf dieser Ebene ist davon nichts zu
sehen. Wer auf eine Bohrung rechtsklickt, will nicht die Menüleiste, er will
die drei Sachen, die man mit einer Bohrung tut.

---

## Teil 4 — Kleinigkeiten, jede einzeln billig

**4.1 Ein Themenwechsel nach dem Zeichnen kommt nur halb an.** Abfolge:
Projekt öffnen → Zeichnen ein → Zeichnen aus → helles Thema. Der Himmel wird
hell (RGB 244,246,248), die Druckplatte bleibt dunkel (37,42,49). Beim Start
mit hellem Thema oder beim Wechseln ohne Zeichnen davor stimmt sie (167,172,175).
Belege: `61-hell-nach-zeichnen.png` gegen `50-hell-von-anfang-an.png`.

**4.2 Der Port der Fernsteuerung ist immer bedienbar**, auch wenn der Haken
„Fernsteuerung über MCP zulassen" fehlt — `settings_dialog.py:129` koppelt das
Feld nirgends an die Auswahl. Und „MCP" steht dort unerklärt; im Erststart
heißt derselbe Bereich „Chat einrichten", im Menü „Zugang zum Sprachmodell".
Drei Namen für benachbarte Dinge.

**4.3 Fokus und Mausüberfahrt sehen auf den Beispielkacheln gleich aus.**
`style.py:161` färbt bei `:hover` den Rand im Akzent, `:162` malt bei `:focus`
einen 2 px starken Rand in derselben Farbe. Auf dem Bildschirmfoto tragen zwei
Kacheln denselben orangen Rahmen, und nichts sagt, welche von beiden Enter
auslösen würde.

**4.4 Das erste Beispielprojekt zeigt „plate_holes".** Ein Bezeichner mit
Unterstrich, englisch, im Objektbaum eines deutschen Beispiels, das der
Startbildschirm als „Der häufigste Fall" anpreist.

**4.5 Das Inhaltsverzeichnis des Handbuchs ist eine flache Liste von über
vierzig Einträgen.** Zwischen „Meldungen im Wortlaut" (erzählter Teil) und
„Szene, Reparatur, Transformation, Grundformen …" (aus dem Register erzeugte
Referenz) steht kein Trenner und keine Überschrift.

**4.6 Auf dem Telefon verliert die Website „Funktionen" und „Preis".**
`style.css:203` blendet beide über `.hide-small` aus, ohne Ersatz — kein
Klappmenü, kein Anker weiter unten. Der Preis ist die erste Frage, die ein
Interessent hat.

**4.7 `FirstRunDialog` trägt einen englischen Docstring** („One page, four
questions, everything skippable.", `first_run.py:96`) in einer Datei, deren
übrige Kommentare deutsch sind. Es ist nicht der einzige — die vollständige
Zählung steht in [Teil 6](#teil-6--was-die-zweite-runde-fand).

---

## Teil 5 — Was die zweite Runde fand

Fünf weitere Läufe, 14. August 2026, an denselben Wegen entlang, aber tiefer:
die Werkzeuge der unteren Leiste einzeln eingeschaltet, alle sieben
Analysekarten, der Weg zum Drucker, die Fehlerpfade, die Tastatur allein und
die Anwendung auf Englisch.

### 5.1 „Die Kette hält an — siehe Prüfbericht", und der Bericht bleibt zu

Eine Bohrung von 200 mm Durchmesser in eine 80 × 50-Platte. Das ist Unsinn,
und das Programm behandelt ihn richtig: die Kette hält an, der letzte gültige
Stand bleibt im Bild, der Verlauf markiert den Schritt mit „**!** Bohrung zu
gross", die Statusleiste sagt „Die Kette hält an — siehe Prüfbericht."

Der Prüfbericht ist in diesem Moment nicht offen. Rechts steht die Tour, und
sie bleibt stehen: `_focus_report` (`main_window.py:4675`) kehrt bei aktiver
Tour ohne Wechsel zurück.

```python
if self.right.currentWidget() is self.tour and self.tour.active:
    # Die Tour zeigt selbst auf den Prüfbericht, wenn er dran ist —
    # ein Reiterwechsel unter der Anleitung weg wäre ihr Ende.
    return
```

Für eine Warnung im normalen Ablauf ist das die richtige Entscheidung. Für
einen Kettenabbruch nicht: Hier verweist die Anwendung im selben Atemzug
ausdrücklich auf ein Fenster, das sie selbst geschlossen hält — und der Reiter
trägt weiterhin keinen Zähler (Befund 2.4).

Beleg: `B-bohrung-zu-gross.png`.

### 5.2 Der Fehlertext am Ende der Rückfallkette sagt dem Anfänger nichts

Derselbe Fall, der Befund im Bericht: **„Auch die letzte Rückfallstufe hat kein
brauchbares Ergebnis geliefert."** Das ist die Sprache des Rechenkerns, nicht
die des Nutzers, und es fehlt der Handlungsvorschlag, den Regel 17 verlangt.
Was hier wahr wäre: der Bohrer ist größer als das Teil — prüfbar, bevor die
Kette anläuft, und in einem Satz erklärbar.

Vier Rückfallstufen laufen für ein Ergebnis, das aus den Maßen vorher
feststeht.

### 5.3 „Schichten" hat zwei Schalter für eine Handlung

Der Werkzeugknopf *Schichten* schaltet die Leiste ein. Was dann dasteht, ist
ein Auswahlfeld mit „Keine Schichtanalyse" und ein toter Regler. Erst wer im
Feld auf „Schichtanalyse" umstellt, sieht etwas — dann allerdings sofort und
gut: „Schicht 1/200 · z 0,10 mm · 4387 mm²", beide Teile im Querschnitt.

Im Code sind es zwei Einträge mit den Werten `False` und `True`
(`analysis_bar.py:209`) — ein An-aus-Schalter hinter einem An-aus-Schalter. Der
Hinweistext darüber sagt derweil „Durch die Höhe fahren und den Querschnitt
ansehen", was in diesem Zustand nicht geht und nicht sagt, warum.

Belege: `81-werkzeug-layers.png`, `90-schichten-gewaehlt.png`.

### 5.4 Die Legende der Merkmalskarte ist eine Debug-Ausgabe

Analyse → *Feature-Zuordnung* färbt den Körper und legt darunter 24 farbige
Kacheln über die ganze Fensterbreite:

```
ohne Merkmal · face_1 · face_10 · face_11 · face_2 · face_3 · face_4 · face_5 ·
face_6 · face_7 · face_8 · face_9 · hole_1 … hole_5 · lid_cavity · pin_1 … pin_4
```

Interne Kennungen, alphabetisch sortiert — `face_10` und `face_11` stehen
zwischen `face_1` und `face_2`. Die sechs anderen Karten machen es vor:
Wandstärke zeigt „0,35 mm · 1,31 mm · 2,28 mm …", Überhang „0 … 90 grad",
Netzfehler „in Ordnung · offene Kante · Non-Manifold".

Zwei Kleinigkeiten in derselben Zeile: Die Karte heißt als einzige halb
englisch **„Feature-Zuordnung"**, obwohl die Begriffszuordnung Merkmal →
`feature` festlegt und die Legende daneben „ohne Merkmal" schreibt. Und die
Winkel stehen als **„45 grad"** statt „45°".

Beleg: `82-karte-5-features.png`.

### 5.5 Neun Tabulatorschritte bis zum Hauptknopf

Der Startbildschirm mit der Tastatur, Station für Station:

```
 1.–8.  exampleTile  (die acht Beispielkacheln)
 9.     QPushButton: Neues Projekt
10.     QPushButton: Projekt öffnen …
11.     QPushButton: Handbuch — die ersten fünfzehn Minuten
```

Der vorbelegte Hauptknopf ist die neunte Station, weil `show_examples()` im
Konstruktor vor den Knöpfen steht und Qt der Aufbaureihenfolge folgt. Für die
Maus ist die Anordnung richtig; für die Tastatur ist sie umgekehrt.

Dazu: Der Objektbaum hat nach dem Öffnen eines Projekts **kein aktuelles
Element** (`currentItem()` ist `None` bei einer vorhandenen Zeile) — wer per
Tabulator hinkommt und eine Pfeiltaste drückt, bewegt nichts.

### 5.6 Die sichtbarsten sechs Handlungen haben keine Tastenkürzel

`window_commands()` führt 22 Fensterbefehle. Fünf davon haben ein leeres Kürzel
— und es sind ausgerechnet die Werkzeuge der unteren Leiste:

```
Ctrl+N  Neu            …            Ansicht: Schnitt
Ctrl+O  Öffnen …       …            Ansicht: Messen
Ctrl+S  Speichern      …            Ansicht: Bewegen
Home    Alles einpassen …           Ansicht: Analyse
F1      Handbuch …     …            Ansicht: Schichten
```

Von 83 registrierten Operationen tragen sechs ein Kürzel. Das ist derselbe
offene Punkt wie 2.7 aus der Kundensicht-Durchsicht — nur ist die Zahl der
Operationen seither von 77 auf 83 gewachsen und die der Kürzel nicht.

### 5.7 Im Druckdialog steht ein zugeklappter Bereich offen

*Weitere Einstellungen* ist zugeklappt und zeigt nichts — richtig. *Profile des
Slicers* daneben ist ebenfalls zugeklappt und zeigt trotzdem seine sechs
Auswahlfelder (Drucker, Grundprofil, Filament, Körper, Schrift, Slot 3), alle
leer, dazu „Der Profilbestand wird durchgesehen …". Zwei Klappen, zwei
Verhalten.

Und der einzige Vorschlag, den der Dialog macht, ist rechts abgeschnitten:
„Das Projekt hat Passungen. Die Außenwand auf das Sollmaß zu rechnen statt auf
die Bahnmitte ist genau …" — kein Umbruch, keine zweite Zeile.

Beleg: `91-druckeinstellungen.png`.

### 5.8 Elf englische Docstrings, wo die Regel Deutsch verlangt

Die Sprachregelung gilt als abgeschlossen („der Bestand ist vollständig
nachgezogen"). Gezählt über den Syntaxbaum von `app/`:

| Datei | Zeile | Stelle |
|---|---|---|
| `app/ui/command_palette.py` | 37 | `CommandPalette` — „Type, pick, run." |
| `app/ui/first_run.py` | 95 | `FirstRunDialog` |
| `app/ui/session.py` | 100 | `_EvaluationWorker` |
| `app/ui/settings.py` | 25 | `UiSettings` |
| `app/ui/main_window.py` | 4901 | `registered_operations` |
| `app/core/registry/surfaces.py` | 38 | `menu_tree` |
| `app/core/perceive/features.py` | 464 | `component_count` |
| `app/core/knowledge/parts/registry.py` | 84 | `PartSpec` |
| `app/core/geom/measure.py` | 84 | `distance` |
| `app/core/slice/orientation.py` | 87 | `improvement` |
| `app/core/backends/openscad.py` | 171 | `available` |

Dazu fünf in `tests/`. Alle elf sind Einzeiler — genau die Sorte, die eine
Übersetzungsrunde übersieht.

### 5.9 Zwei modale Fehlerfenster hintereinander

Zwei fehlgeschlagene Operationen nacheinander erzeugen zwei modale
*Fehlerbericht*-Fenster, die sich stapeln. Der Text darin ist vorbildlich —
„Das war ein Programmfehler, nicht Ihre Schuld. Hier wird ein Bericht
zusammengestellt — verschickt wird nichts." —, aber zweimal hintereinander
wegzuklicken ist einmal zu viel.

---

## Teil 6 — Was die zweite Runde entlastet hat

Vier Sachen wurden gezielt gesucht und nicht gefunden. Sie stehen hier, weil
ein nicht gefundener Fehler dieselbe Arbeit gekostet hat wie ein gefundener.

**Die englische Oberfläche ist vollständig.** Am laufenden Fenster geprüft, nicht
am Katalog: 0 deutsche Einträge in 127 Menüzeilen, 0 im Operationsdialog, 0 im
Bausteinkatalog, 0 in den Touren, alle sieben Werkzeughinweise übersetzt. Der
eine Treffer meiner Suche war „…Nothing is lost here: und…" — Qts eigene
Kürzung von „undo".

**Jede Operation sagt, was sie tut.** 83 Operationen: keine ohne
Beschreibungssatz, kein Parameter ohne Erklärung. Der vollste Dialog hat acht
Felder auf der Vorderseite (`label_text`), die Grenze liegt bei acht.

**Die Website ist handwerklich sauber.** Sieben Bilder, alle mit Alt-Text; kein
toter Sprungmarken-Verweis auf sieben Seiten; Impressum, AGB, EULA, Widerruf
und Datenschutz vollständig gegliedert; kleinste Fließtextgröße 12,8 px.

**Die Preise stehen in beiden Sprachfassungen.** Der erste Verdacht — auf
Englisch fehle der Preis — kam von der Schreibweise: die deutsche Seite
schreibt „49 €", die englische „€49". Inhaltlich identisch, 0/49/79 hier wie
dort.

---

## Was gemessen wurde

Dreizehn Läufe über `build_application([])` im Vollbild, Nutzerverzeichnisse in
einen Temp-Ordner umgebogen (also mit echtem Erststart), dazu die
Zustandsabfrage aller 127 Menüeinträge in drei Szenenzuständen — leer, Projekt
offen, Objekt gewählt. Fotografiert: Startbildschirm, Erststart, leeres
Projekt, alle neun Menüs mit allen Untermenüs, Beispielprojekt mit Tour, Chat,
Prüfbericht, Operationsdialog vorn und hinten, Kontextmenü, Skizzeneditor,
Bausteinkatalog, Einstellungen, Handbuch, helles Thema in drei Abfolgen,
Fremdmodell mit Befunden, alle sieben Werkzeuge der unteren Leiste einzeln,
alle sieben Analysekarten, Druckeinstellungen mit allen acht Reitern, drei
absichtlich unsinnige Operationen, die Tabulatorkette auf zwei Bildschirmen
und die gesamte Oberfläche auf Englisch. Website: Startseite und Handbuch bei
1440 und 390 px, dazu Überstandsmessung, Gegenprobe im laufenden Browser und
eine Strukturabfrage über alle sieben Seiten.

Ein Wachhund räumte modale Fenster weg und schrieb auf, was er wegräumte —
sonst bleibt jeder Lauf am ersten Fehlerdialog stehen, und niemand erfährt, an
welchem.

Die Bilder liegen im Arbeitsordner dieser Sitzung, nicht im Repository.

**Vier eigene Lesarten waren falsch** und wurden von der Messung widerlegt.
Sie stehen hier, weil sie sonst als Befund im Bericht stünden:

* Das Menü *Objekt* sah am Bild aktiv aus und ist vollständig ausgegraut —
  grau und weiß sind im dunklen Thema am verkleinerten Bild kaum zu trennen.
* Der waagerechte Überstand der Website stammt von zwei Pseudo-Elementen, die
  `querySelectorAll` nicht findet, nicht von einem sichtbaren Element.
* Zwanzig Operationen schienen die Grenze von acht Feldern auf der Vorderseite
  zu reißen. Das Kriterium war falsch: die Suite zählt `placement == "front"`,
  nicht ein Attribut `advanced`. Richtig gezählt liegt keine über acht.
* Auf der englischen Seite schien der Preis zu fehlen. Sie schreibt „€49", die
  deutsche „49 €".
