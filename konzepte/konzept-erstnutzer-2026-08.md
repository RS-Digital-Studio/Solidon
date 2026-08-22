# Konzept — Solidon3D mit den Augen eines Anfängers

Aus dreizehn Bedienläufen am echten Programm, 13. und 14. August 2026, im Vollbild
(2560 × 1369 px), plus vier Läufen über die Website im installierten
QtWebEngine. Gestartet über `build_application`, bedient über den
Qt-Ereignisweg — dieselben Wege, die eine Maus nimmt. Alles unten ist gemessen
oder fotografiert. Wo eine erste Lesart am Bild falsch war, steht die Messung,
die sie widerlegt hat.

Die Frage war nicht „ist es fertig", sondern: **Wer das hier zum ersten Mal
öffnet — sieht der, was er sehen muss?**

> **Stand 14.08.2026, nachrecherchiert am 19.08.2026, gegen den Code geprüft am
> 22.08.2026.** Abgearbeitet, jeder Fund mit Test und am laufenden Fenster
> nachgemessen.
>
> Die Prüfung am 22.08. hat die Tabelle unten zur Hälfte umgeschrieben, und das
> ist die Lehre dieses Dokuments: **Von den sechs Punkten, die es am 19.08. noch
> als offen führte, waren vier längst behoben** — 2.1, 2.5, 3.4 und die drei, die
> „von Anfang an in keiner Zeile dieser Tabelle" standen (4.4, 5.7; 4.3 ebenso).
> Niemand hatte sie nachgezogen, weil sie in keinem Register standen und kein
> Test sie zählte.
>
> **Wirklich offen sind zwei**, 3.1 und 5.9, und die stehen seit dem 22.08. im
> Register von `ROADMAP.md`. Einer ist unentschieden (4.1) und dort bewusst
> nicht eingetragen: Ein Punkt, von dem niemand weiß, ob er existiert, ist eine
> Messung und keine Arbeit.
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
> | 5.4 Legende aus `face_10`, Kartenname, Gradzeichen | behoben — `5902211`; der Name *Feature-Zuordnung* steht noch im Handbuch |
> | 5.5 Tabulator · Objektbaum ohne Anfang | behoben — `799fce5`, `9aa7df9` |
> | 5.6 Kürzel für die Werkzeuge | behoben — `Alt+1` bis `Alt+8` (ROADMAP.md:5592) |
> | 5.8 Elf englische Docstrings in `app/` | behoben — `799fce5`, in `app/` jetzt null; in `tests/` stehen zwölf, die die Zählung nie erfasst hatte |
> | 2.1 Karten nutzen die Fensterhöhe nicht | behoben — `ba1e455`; `_share_room` teilt die Zonenhöhe zu, festgehalten von `test_a_card_uses_the_room_a_tall_window_offers` |
> | 2.5 Import landet im vorhandenen Körper | behoben als **Vorschlag**, nicht als Automatik — `panels.py:134` hängt *Auf das Bett setzen* an den Befund `arrange.below_bed`. §17.1 setzt bewusst nicht von selbst |
> | 3.4 Kontextmenü | behoben — `panels.py:878`: am Merkmal die passenden Operationen flach, am ganzen Körper nach Kategorie gruppiert |
> | 4.3 Fokus sieht aus wie Mausüberfahrt | behoben — `style.py:309`: Hover färbt die Fläche, Fokus setzt den Rahmen |
> | 4.4 „plate_holes" im ersten Beispielprojekt | behoben — `make_examples.py:51` setzt `name="Halterung"` |
> | 5.7 Zwei Klappen, zwei Verhalten | behoben — beide über `collapsible(…, open_now=False)`; der abgeschnittene Vorschlag durch `setWordWrap(True)` |
> | **3.1 Erzeugen und Ändern sind reine Verteilermenüs** | **offen, als Entscheidung** — seit 22.08.2026 im Register von `ROADMAP.md` |
> | **5.9 Zwei modale Fehlerfenster** | **offen** — `main_window.py:6376`, seit 22.08.2026 im Register |
> | 4.1 Thema nach dem Zeichnen | **Verdacht verkleinert, nicht entschieden** — siehe den Kasten unter 4.1 selbst |
>
> Nicht behoben und bewusst so: **3.2** (alphabetische Sortierung der
> Grundformen) — sie ist eine begründete Entscheidung, die
> `test_a_menu_is_sorted_the_way_it_is_read`
> (`tests/test_interface_limits.py:484`) festhält. **4.1** (halb
> umgeschaltetes Thema nach dem Zeichenmodus) und **4.3** (Fokus sieht aus wie
> Mausüberfahrt) sind geblieben; beide brauchen mehr als eine Zeile und keinen
> Befund über sich hinaus. Bei 4.3 hat sich der Code seither bewegt, ohne dass
> der Befund ganz verschwunden wäre — siehe dort.
>
> **Wo der Fließtext unten im Präsens steht, beschreibt er den 14. August.**
> Was seither eingelöst wurde, trägt an Ort und Stelle einen Erledigt-Vermerk;
> die Messwerte bleiben stehen, weil ein Messwert vom 14. August am 19. August
> nicht falsch ist, sondern datiert.

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
| vor `2f56d93` (13.08.2026) | `(1.0, −1.0, 0.8)` | 220 × 220 mm gesetzt |
| nach `reset_camera()`, und seit `2f56d93` von selbst | `(474.7, −474.7, 504.7)` | dieselbe |

Die Kamera stand anderthalb Millimeter vom Ursprung entfernt in einem
220-Millimeter-Bauraum. Ein Druck auf `Pos1` („Alles einpassen") reparierte es
sofort — die Druckplatte steht dann mit Raster und Maßzahlen im Bild.

Die Ursache stand in `app/ui/viewport.py`: `_fit_once_for` passte nur ein,
wenn `has_objects` wahr ist. Die Startkamera wird beim Aufbau über
`view_from("iso")` gesetzt — zu einem Zeitpunkt, an dem
der Bauraum noch nicht bekannt ist. Danach kommt `show_build_volume`, aber
niemand richtete die Kamera daran aus. `reset_camera` könnte es: sein Docstring
sagt ausdrücklich „Ohne Körper bleibt der Bauraum das Maß" — er wurde in
diesem Fall bloß nie gerufen.

> **Erledigt.** `_fit_once_for` (`app/ui/viewport.py:3492`) hat den Zweig „Die
> leere Szene hat auch etwas zu zeigen: den Bauraum" und erzählt den Befund im
> eigenen Docstring nach (`2f56d93`, 14.08.2026). Die erste Zeile der Tabelle
> oben gibt es nicht mehr; die zweite ist heute die einzige. Der Bauraum ist
> unverändert `generic-220` (`app/core/knowledge/data/printers.toml:13`,
> `build_volume = [220.0, 220.0, 250.0]`).
>
> **Die drei Zeilennummern im Text stimmen nicht mehr** (Stand 19.08.2026):
> `_fit_once_for` steht bei 3492 statt 3171, `view_from("iso")` bei 1166 statt
> 1056, `reset_camera` bei 3466. Die Datei ist auf 3926 Zeilen gewachsen.

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

> **Erledigt.** `443058f` (14.08.2026) — „Ausweichen, das die eigene Breite
> nicht kennt, weicht nicht aus". Die Messung oben bleibt als Zustand vom
> 14. August stehen.
>
> Der Fall hat eine Norm hinter sich, die im Befund noch fehlte: WCAG 2.2
> nennt seit ihrer Veröffentlichung das Erfolgskriterium **2.4.11 Focus Not
> Obscured (Minimum), Stufe AA** — ein fokussiertes Bedienelement darf nicht
> von anderem Inhalt verdeckt werden. Eine Ebenenwahl, von der nur der rechte
> Rand sichtbar ist, ist genau dieser Fall.
> <https://www.w3.org/WAI/standards-guidelines/wcag/new-in-22/> (abgerufen
> 19.08.2026)

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

> **Erledigt, und genau so, wie der Befund es trennt.** `website/style.css:67`
> trägt `overflow-x: clip` am `:root` (zusätzlich Zeile 93 am `body`), die
> Zahlen 111 und 270 stehen dort im Kommentar. `website/handbuch.html:86` und
> `tools/make_manual.py:133` geben Tabellen `display: block; overflow-x: auto`
> — der Erzeuger und die erzeugte Seite, sonst wäre es beim nächsten Lauf
> wieder weg (`61fbc01`, 14.08.2026).
>
> Die Browsermessungen selbst waren am 19.08.2026 nicht nachprüfbar; belegt
> ist die Ursachenbehebung im Quelltext, nicht ein neuer Messwert.

---

## Teil 2 — Übersichtlichkeit auf einem großen Bildschirm

### 2.1 Die Karten nutzen die Höhe nicht, und schneiden dabei Text ab

Bei 1369 px Fensterhöhe enden die drei linken Abschnitte bei y = 499. Die
rechte Karte ist 344 px hoch. Darunter: gut 900 px leere Fläche — und
gleichzeitig schneidet die Tour ihre eigenen Schritte ab. Im Bild
`10-beispiel-weg1.png` steht Schritt 1 vollständig, die Schritte 2 bis 5 enden
je mit „…", und die Karte hat einen eigenen Rollbalken.

Das ist nicht der alte Befund „Karten wachsen nicht mit dem Inhalt" (behoben,
`b017fde`, 08.08.2026) — sie wachsen mit dem Inhalt, aber sie nehmen sich den
freien Platz darunter nicht, wenn der Inhalt mehr bräuchte als der Inhalt
hergibt.

> **Weiter offen** (19.08.2026). `app/ui/overlay.py` ist seit dem 14.08.2026
> unverändert; die ROADMAP-Stelle zur Spaltenhöhe (ROADMAP.md:3749, „Die linke
> Spalte rechnete sich um zweihundert Pixel zu kurz") datiert auf den
> 08.08.2026 und liegt damit **vor** diesem Befund, löst ihn also nicht ein.

### 2.2 Der Chat ist eine leere schwarze Box

Weg 3 und das Versprechen, mit dem die Anwendung antritt. Was ein Neuling
sieht: eine Zeile „Modell: ollama:qwen3:14b", darunter 170 px Leere, darunter
ein Feld „Was soll geändert werden?" und „Senden".

Kein Beispielsatz, kein Vorschlag, keine Andeutung dessen, was dieses Ding
kann. Der Erststart-Dialog wirbt für den Chat, das Handbuch hat ein Kapitel
darüber, die Website zeigt ihn — und die Stelle selbst sagt nichts. Drei bis
vier anklickbare Beispielanfragen im leeren Zustand wären hier die billigste
gute Tat des ganzen Programms.

> **Erledigt.** `app/ui/chat.py:54` führt `STARTERS` — anklickbare
> Beispielanfragen im leeren Gespräch (`7fe7c30`, 14.08.2026, „Der Chat ist
> das Versprechen der Anwendung und stand leer da").
>
> Dazu ein Außenfakt, der am 14. August noch Zukunft war und es nicht mehr
> ist: **AI Act Artikel 50 gilt seit dem 02.08.2026.** Er verlangt, dass ein
> Nutzer erfährt, dass er mit einem KI-System spricht, sofern das nicht
> offensichtlich ist — Text, nicht Farbe, nicht Symbol allein. Die Zeile
> „Modell: …" ist ein Modellname, keine solche Angabe.
> <https://artificialintelligenceact.eu/article/50/> (abgerufen 19.08.2026)
>
> Offen und aus dem Wortlaut nicht zu entscheiden: ob ein per LLM erzeugtes
> 3D-Modell oder erzeugter OpenSCAD-Quelltext unter die Kennzeichnungspflicht
> für „synthetische Inhalte" fällt. Artikel 50 nennt Audio, Bild, Video und
> Text; 3D wird nicht genannt, und ein Leitliniendokument der Kommission dazu
> war am 19.08.2026 nicht auffindbar. Das bleibt hier offen und wird nicht
> geraten.
>
> Die Vorbelegung „ollama:qwen3:14b" ist eine Bildschirmbeobachtung vom
> 14.08.2026 und steht so stehen — ob dieses Modell heute noch die
> Voreinstellung ist, war extern nicht belegbar.

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

> **Erledigt, und schärfer als vorgeschlagen.** Offscreen nachgemessen am
> 19.08.2026: auf dem Startbildschirm ist die Werkzeugleiste gar nicht mehr da
> (`isVisible() == False`), und bei leerer Szene sind **alle acht** Werkzeuge
> `enabled == False` (`b07bcfb`, 14.08.2026, „Bemalen auf einer leeren Szene
> ist ein Pinsel für nichts").
>
> Die sechs Zeilen oben sind der Stand vom 14. August. Die Leiste führt heute
> acht Werkzeuge — `explode` und `split` sind dazugekommen.
>
> Auch die Zahl 34 gilt weiter, ihre Zusammensetzung nicht: unter *Ändern*
> stehen heute Verbinden 4, Transformation 9, Formgebung 5, Bohrungen 3,
> Oberfläche 3, Netz 9, Reparatur 1.

### 2.4 Eine Warnung bleibt unsichtbar, solange eine Tour läuft

Ein fremdes Netz eingefügt, das nicht geschlossen ist. Der Prüfbericht hat es
korrekt: „Das Modell ist nicht geschlossen" als Warnung. Zu sehen ist davon
nichts — die rechte Spalte zeigt weiter die Tour, und der Reiter „Prüfbericht"
sieht aus wie vorher: kein Zähler, kein Zeichen, keine Farbe.

Dass der Sprung der aktiven Tour den Reiter lässt, ist die richtige
Entscheidung (sie steht so in der Gebietsregel). Dann muss aber der Reiter
selbst sprechen — „Prüfbericht · 1 ⚠" statt „Prüfbericht".

> **Erledigt, genau so.** `app/ui/main_window.py:5678` setzt den Reitertext auf
> „Prüfbericht · n" (`46e2b7c`, 14.08.2026). Der zweite Teil desselben Commits
> gehört zu 5.1: `_focus_report(force=True)` überstimmt die Tour, wenn die
> Kette anhält.

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

> **Nachgemessen am 22.08.2026 — der Verdacht ist kleiner geworden, der Punkt
> bleibt offen.** Am echten Bildschirm mit lebendem Plotter und geöffnetem
> Beispielprojekt, in genau dieser Reihenfolge:
>
> | | `bed` | `bed_surface` |
> |---|---|---|
> | Start (dunkel) | `#5a6472` | `#2a303a` |
> | nach Zeichnen aus | `#5a6472` | `#2a303a` |
> | nach Thema hell | `#9aa3ae` | `#bcc4ce` |
> | Soll hell | `#9aa3ae` | `#bcc4ce` |
>
> **Die Farbkette folgt dem Thema** (`viewport_colours` → `_bed_colour` /
> `_bed_surface`), auch über Zeichnen ein und aus. Offen bleibt allein, ob die
> *gezeichnete* Ansicht nachzieht — und das ist mit einem Skript **nicht**
> entschieden worden: Ein Zähler über die Bildpunkte des Bildschirmfotos gab
> zuerst eine überzeugende Bestätigung des alten Befunds (258 023 Punkte nahe
> 37,42,49). Die Kontrolle hat sie kassiert: Drei Läufe — mit Zeichnen, ohne
> Zeichnen, und *hell von Anfang an* — lieferten **byteweise identische**
> Zahlen. Ein Lauf, der nie dunkel war, kann den dunklen Befund nicht
> reproduzieren; also misst der Weg über `plotter.screenshot()` das Thema
> nicht. Es braucht ein Auge am Bildschirm, nicht noch ein Skript.
>
> **Ein Test dazu wird bewusst nicht gebaut, und dafür gibt es jetzt eine
> Zahl statt einer Vermutung.** `Viewport.set_theme` steigt bei
> `if self.plotter is None: return` aus, und `_available()` gibt auf der
> Offscreen-Plattform absichtlich `False` zurück — VTK nähme dort den Prozess
> mit. Gemessen über 23 Fensterdateien mit 1597 Tests, mitgeschrieben Zeile für
> Zeile: Von den 40 Methoden des Viewports hinter dieser Wache werden **alle
> vierzig aufgerufen, aber bei dreißig läuft der Rumpf nie** — 497 Zeilen, die
> in keinem Test ausgeführt werden.
>
> Der größte davon ist ausgerechnet **`_draw_one_bed`, 79 Zeilen: die
> Druckplatte.** Damit ist entschieden, warum 4.1 nicht mit einem Test zu
> klären ist — die Methode, die die Platte zeichnet, läuft in der Suite kein
> einziges Mal. Ein headless-Test prüfte die vier Zuweisungen und nie den
> Zeichenpfad: Er sähe aus wie Abdeckung und wäre keine.
>
> Dass es diese Lücke gibt, steht in `.claude/rules/oberflaeche.md` an drei
> Stellen („Offscreen gibt es keinen Plotter, und jeder Setzpfad steigt vorher
> aus"), samt dem Mittel dagegen — einer Attrappe mit der einen benutzten
> Methode, wie in `tests/test_cursors.py`. Neu ist nicht das Phänomen, sondern
> **seine Größe**.

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

> **Behoben, und beide Zahlen sind überholt** (nachgezählt am 19.08.2026).
> Die Werkzeuge der unteren Leiste haben `Alt+1` bis `Alt+8`
> (`ROADMAP.md:5592`). `window_commands()` führt heute **60** Fensterbefehle,
> 23 davon ohne Kürzel — die Liste ist gewachsen, nicht die Lücke. Und das
> Register zählt **85** Operationen statt 83; sechs mit Kürzel, das stimmt
> weiter. Der offene Punkt 2.7 aus der Kundensicht bleibt es: Kürzel für die
> Operationen selbst sind eine Vergabe in einem Zug, keine Nebenarbeit.

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

> **Aus zwei Sprachen sind sechs geworden.** Am 16.08.2026 kamen Spanisch,
> Französisch, Italienisch und Portugiesisch dazu (`app/i18n/locales/`);
> `tests/test_translations.py` prüft seither jede gefundene Datei, nicht mehr
> nur die englische. Die Menüleiste zählt heute 136 Zeilen statt 127, und die
> untere Leiste trägt acht Werkzeuge statt sieben.

**Jede Operation sagt, was sie tut.** 83 Operationen: keine ohne
Beschreibungssatz, kein Parameter ohne Erklärung. Der vollste Dialog hat acht
Felder auf der Vorderseite (`label_text`), die Grenze liegt bei acht.

> **85 Operationen** (19.08.2026) — die Aussage selbst gilt weiter: kein
> Registereintrag ohne `doc`, kein Parameter ohne `doc`, keine Vorderseite mit
> mehr als acht Feldern.

**Die Website ist handwerklich sauber.** Sieben Bilder, alle mit Alt-Text; kein
toter Sprungmarken-Verweis auf sieben Seiten; Impressum, AGB, EULA, Widerruf
und Datenschutz vollständig gegliedert; kleinste Fließtextgröße 12,8 px.

**Die Preise stehen in beiden Sprachversionen.** Der erste Verdacht — auf
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

---

## Nachrecherchiert am 19.08.2026

Neunzehn Aussagen dieses Dokuments über den eigenen Code nachgeprüft: **vier
stimmen, neun sind überholt, eine war falsch, eine ist nicht prüfbar.** Dazu
kamen drei Widersprüche im Dokument selbst.

**Der schwerste Fund ist eine Lücke, kein Fehler.** Die Statustabelle im Kopf
führte siebzehn behobene und vier offene Befunde — und ließ **4.4, 5.7 und
5.9** ganz aus. Wer die Tabelle las, hielt sie für vollständig; alle drei sind
bis heute offen. Sie stehen jetzt drin:

- **4.4** — `app/examples/weg1-halterung-anpassen.p3d` führt weiter
  `sources/plate_holes.stl`, und `app/core/ingest/ops.py:227` benennt das
  Objekt nach dem Dateinamen. Im Baum steht also weiter `plate_holes`.
- **5.7** — `app/ui/print_settings_dialog.py:1004` klappt „Weitere
  Einstellungen" wirklich zu; `slicer_box` (`:1047`) ist ebenfalls
  `setCheckable(True)`, hat aber keine Verbindung — die Felder bleiben
  sichtbar. Der zweite Teil des Befunds ist entschärft (`profile_note`
  bricht um, `:1076`).
- **5.9** — kein Stapelschutz gegen zwei modale Fehlerfenster
  (`app/ui/report_dialog.py`, `app/ui/dialogs.py`), und kein Eintrag in der
  ROADMAP.

**Ein Befund ist seit dem Schreiben zugegangen:** 5.6, die Tastenkürzel der
Werkzeugleiste (`Alt+1` bis `Alt+8`). Offen bleiben damit sechs statt vier.

**Was der Zähler überholt hat:** 83 Operationen → 85 · 127 Menüzeilen → 136 ·
22 Fensterbefehle → 60 (23 ohne Kürzel) · sieben Werkzeuge → acht · acht
Beispielkacheln → neun · zwei Sprachen → **sechs**. Unverändert: sieben
Analysekarten, sechs Operationen mit Kürzel, 34 Einträge unter *Ändern*, acht
Felder als Maximum der Vorderseite, Bauraum 220 × 220 mm.

**Eine Zahl war falsch, nicht überholt:** „fünf englische Docstrings in
`tests/`". Es waren zwölf, und sie sind es noch — die Zählung hat sie nie
vollständig erfasst. In `app/` sind es dagegen heute null, wie behauptet.

**Alle Zeilennummern in diesem Dokument sind verfallen.** Geprüft wurden acht
Verweise (`viewport.py:3171`, `main_window.py:4675`, `settings_dialog.py:129`
und fünf weitere) — keiner zeigt noch auf das, was er benennt. Das ist kein
Vorwurf an das Dokument, sondern die Eigenschaft von Zeilennummern in einem
Repository mit hundert Commits pro Woche. Künftig gehören Symbolnamen dorthin.

**Nicht prüfbar und deshalb offen gelassen:** die Website-Messwerte (scrollX,
`hero::before`, Schriftgrößen) — sie stammen aus dem installierten
QtWebEngine, und ohne denselben Aufbau wäre jede neue Zahl eine andere
Messung. Die Ursachenbehebung dahinter (`61fbc01`) ist am Code belegt.
