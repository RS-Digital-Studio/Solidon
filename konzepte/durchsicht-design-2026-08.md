# Durchsicht: Design und Anmutung aller Panels und Dialoge

**Stand:** Erhebung abgeschlossen, 30.08.2026 · **Anlass:** Roberts Frage, ob
Design, Layout und Modernität je systematisch geprüft wurden — sie waren es
nicht, die D-Serie prüfte Funktion und Bedienung · **Maßstab:** „komplett
hochwertig, schön, modern, innovativ, selbsterklärend und intuitiv", für
Kunden ohne CAD-Kenntnisse · **Registerpunkt:** die G-Pakete in `ROADMAP.md`

**Methode:** Echte Qt-Plattform (offscreen hat keine Schriftfamilien), dunkles
und helles Thema, Deutsch und Französisch, geladenes Beispielprojekt
`dose-mit-deckel.p3d` plus Leerzustände. 158 Belegbilder im Scratchpad der
Erhebungssitzung (`design-durchsicht/`, vergänglich — die Messwerte stehen
hier). Ein Zwischenbefund (Viewport im hellen Thema dunkel) fiel als
Prüfstandsartefakt: Der Aufbau rief `MainWindow._apply_settings()` nicht, der
echte Startweg tut es; alle hellen Aufnahmen wurden danach neu gemacht.

Die Statustabellen dieses Dokuments altern — offene Arbeit steht im Register
von `ROADMAP.md` und nirgends sonst.

---

## Kritisch

**B1 — Jede Menü-Überschrift ist unsichtbar; das Stylesheet frisst sie.**
`app/ui/style.py:541` (`QMenu::separator`) gegen `main_window.py:2008`
(`addSection`). In *Erzeugen*, *Ändern*, *Vorbereiten*, *Ansicht* stehen
zwischen den Gruppen nackte Trennstriche; die Kategorienamen, die der Code mit
fünfzehn Zeilen Begründung setzt, erscheinen nie. Gegenprobe gemessen: dasselbe
Menü mit und ohne Anwendungs-Stylesheet — mit fehlt der Text restlos. 114
Menüeinträge stehen in unbenannten Blöcken.

**B2 — Die Prozentzahl im Fortschrittsbalken wird ab der Hälfte unlesbar.**
`style.py:558–564`: zentrierter Text auf dem Bernstein-Chunk. Kontrast heller
Text auf Bernstein im dunklen Thema: **1,69** (AA verlangt 4,5). Das dunkle
Thema ist die Voreinstellung, und über 10 s stünde dort laut `wartezeit.md`
zusätzlich die Schätzung — im selben Balken.

**B3 — Der waagerechte Rollbalkengriff wird zur 2-Pixel-Linie.**
`style.py:529`: `min-height` wirkt nur senkrecht, `min-width` fehlt. Bei
Seitenschritt 20 von 10000 ist der Griff weder sichtbar noch greifbar.

**B4 — Der Bausteinkatalog steht rund zehn Sekunden als Textwüste da.**
27 von 29 Kacheln ohne Bild direkt nach dem Öffnen, kein Balken, kein
Platzhalter, kein Satz — §2.6 begründet den Katalog gerade damit, dass ein
räumliches Teil als Textzeile die schlechtere Darstellung sei; `wartezeit.md`
verlangt ab 2 s Fortschritt mit Abbrechen.

**B5 — Das Vorschaubild im Objektbaum ist ein vier Pixel großer Fleck.**
`panels.py:3236`: Zeilenhöhe × 1,2, mindestens 18 — bei fünffacher
Vergrößerung keine Form erkennbar. Der Docstring nennt das Problem selbst
(„ein Quader war ein Punkt"); es besteht fort. Kostet Spaltenbreite, liefert
nichts.

**B6 — Die Akzentfarbe steht an vier bis sechs Stellen gleichzeitig.**
Ohne jede Auswahl tragen vier Elemente die Akzentkante (Kartenspalte,
Prüfbericht-Karte, Werkzeugzeile, aktiver Reiter); in der Bewegen-Karte vier
Akzentflächen auf einmal. Bernstein bedeutet zugleich „ausgewählt", „aktiv",
„Hauptknopf", „Karte", „nimmt Material weg" (Katalog) und „diese Zahl ist
wichtig" (Ablaufdatum, Versionsnummer). Systemebene, betrifft jedes Fenster.

## Mittel

**B7** — `QSlider` ist das einzige unformatierte Bedienelement: kantiges
Rechteck im dunklen, weißer Kreis im hellen Thema; gesperrt sieht der Griff
bedienbar aus.
**B8** — Operationsdialog: drei verschiedene rechte Feldkanten (325/395/535 im
Bohrdialog), auch linke Kanten springen.
**B9** — Druckeinstellungen mischen zwei Abschnittsformen: gerahmte `QGroupBox`
mit eingelassenem Titel (Qt 2010) über rahmenlosen Aufklappern.
**B10** — Druckeinstellungen: rechts der Felder ~375 von 630 Punkten leer über
acht Zeilen; darunter ein 130 Punkte hoher fast leerer Ergebniskasten.
**B11** — Einstellungsdialog: zwei Formularraster (Felder ab x≈150 oben, x≈70
unten) im selben Dialog.
**B12** — Einheit in eckigen Klammern in der Beschriftung („Durchmesser
[mm]") — `oberflaeche.md` verbietet genau das; die Leisten machen es richtig
(„20,00 mm" im Wert). Klammer wandert bei Zoll-Umschaltung nicht mit.
**B13** — „fx" ist rahmenlos, ~60 Punkte vom Feld entfernt, und für Laien
bedeutungslos — liest sich als abgeschnittenes Etikett.
**B14** — „…"-Knopf der Parameterzeile: reiner Text, als Bedienelement nicht
erkennbar.
**B15** — Zahlenfeld: Auf/Ab-Zielfläche ~10×11 Punkte, Trennstrich vom Rahmen
verdeckt (`subcontrol-origin: border`); Combobox-Pfeilfeld schneidet die
gerundete Ecke von innen an.
**B16** — Prüfbericht färbt den ganzen Befundsatz in der Rollenfarbe — das
Symbol leistet die zweite Kodierung bereits; die dringlichste Farbstufe hat den
niedrigsten Kontrast (4,52).
**B17** — Der Chat begrüßt mit einem leeren schwarzen Kasten (~190 Punkte);
die vier Beispielanfragen stehen darunter; erste Zeile ist
„Modell: ollama:qwen3:14b".
**B18** — Generierungsdialog: zwei Drittel leere Fläche, einziger vollbreiter
Knopf der Anwendung, „Generator wird geprüft …" als nackte Textzeile.
**B19** — Die Erklärsätze der Werkzeugkarten sind kursiv — als einzige Texte
der Anwendung, zwei bis drei Zeilen auf dunklem Grund.
**B20** — Die Skizzenkarte ist ein zerfallener Textblock: drei Absätze, einer
zentriert mit versprengtem Label „Skizze", derselbe Satz doppelt (Karte und
Viewport-Sprechblase), dazu die freischwebende Kapsel „Keine Auswahl".
**B21** — Aufgeklappte Filamentkarte wird mitten in einer Zeile abgeschnitten,
während darunter ~590 von 1300 Punkten leer stehen — die bekannte
Höhenzuteilungs-Falle an einer weiteren Karte.
**B22** — Der Hauptknopf bedeutet nicht überall dasselbe: Im Kürzelfenster
trägt „Schließen" den Akzent; fünf Dialoge haben gar keinen akzentuierten
Knopf, weil der Hauptknopf anfangs gesperrt ist.
**B23** — Befehlspalette: Kürzel in zwei springenden Spalten (x≈100/x≈180),
keine Kategorien, keine Symbole.
**B24** — Statuszeile verschmilzt zwei Auskünfte: „…bis zum 30.10.2026  51 g ·
3 h 30 min" — Lizenz und Verbrauch nur durch Leerzeichen getrennt; Kopfzeile
ebenso („…220 mm   PLA").
**B25** — Katalogkacheln ohne Ruheform (Fläche nur bei hover/selected), Titel-
Grundlinien fluchten nicht, Renderings nicht normiert, Umbruchlöcher >120
Punkte.
**B26** — Freischaltung: 90 Punkte hohes Mehrzeilenfeld für einen einzeiligen
Schlüssel, 60 Punkte unmotivierte Leere, die eigentliche Anleitung als
leiseste Zeile, „Solidon kaufen" als Nebenknopf — den Akzent trägt das
Ablaufdatum.
**B27** — Startbildschirm endet auf halber Höhe (bildschirmfüllend bleibt die
untere Hälfte leer); Kachel-Unterzeile viermal identisch; ein Knopf doppelt so
breit wie seine Nachbarn; Kopf ohne Marke.
**B28** — Filamentdialog: Die Farbe ist ein ~12-Punkte-Quadrat in 460 Punkten
Breite — die wichtigste Eigenschaft als unauffälligstes Element; der Knopf
heißt „OK" statt seiner Handlung (einziger der Anwendung).
**B29** — Vier Wartezustände als nackte Textzeilen; im Zusatzprogramme-Dialog
dieselbe Aussage dreifach.
**B30** — `QSplitter::handle` hat Kontrast 1,0 zum Fenster — die Fuge ist
unsichtbar, bis man sie überfährt.

## Kosmetisch

**B31** — Verlauf: nur Baustein-Zeilen nummeriert, keine Symbole (17
Kategoriesymbole in `icons.py` ungenutzt), kein Zebra.
**B32** — Gesperrte Ankreuzfelder/Regler kaum von bedienbaren unterscheidbar.
**B33** — Icon-Lücken in Menügruppen („Aus Skizze erzeugen …", „Automatisch
teilen …"); Menüs ohne Symbolspalte sind 22 Punkte anders eingerückt.
**B34** — Handbuch: Verzeichniseinträge ohne Auslassungszeichen abgeschnitten,
Fließtext ohne rechten Rand bei ~110 Zeichen Zeilenlänge.
**B35** — Helles Thema: `object` und `edge` zu nah — der Körper wird zur
flachen Silhouette, die Druckplatte ist das auffälligste Element.
**B36** — Nachkommastellen uneinheitlich: Textur „40,000", Bohrung „4,20".
**B37** — Werkzeugknopf im Ruhezustand rahmenlos — zwei von drei Modusknöpfen
der Bewegen-Karte sehen nicht wie Knöpfe aus.
**B38** — Erststart ohne vertikalen Rhythmus (60/50/20 Punkte, kein
gemeinsames Vielfaches trotz `style.SPACE`).
**B39** — Rechtsbündige Knöpfe fluchten nicht (Zusatzprogramme x≈553/540);
Trennleiste mit ~200 Punkten Lücke vor den Knöpfen.
**B40** — Kein Sprachlängenbruch bei 2560 Punkten; aber der Symbol-Umschalt-
Schwellwert der Bewegen-Leiste ist sprachabhängig (Französisch schaltet
früher auf unbeschriftete Symbole).

Der Nebenbefund der Erhebung (Regeltext „acht Umschalter", gebaut sind
sieben) war zum Zeitpunkt der Meldung bereits behoben (`258999b6`).

## Die drei stärksten Stellen

1. **Der Startbildschirm** — führt ohne ein Wort Anleitung in die vier Wege;
   die einzige Ansicht, die aussieht wie eine Anwendung von 2026.
2. **Das Kürzelfenster** — die einzige Liste, in der Struktur, Ausrichtung
   und Dichte zusammenstimmen.
3. **Der Symbolsatz** — 61 Zeichen, ein Strichstil, `currentColor`, Größe an
   der Schrift: kein Stilbruch über alle Menüs und Leisten.

## Die drei schwächsten Stellen

1. **Der Bausteinkatalog** — zehn Sekunden Textwüste, dann rahmenlose Kacheln
   mit nicht normierten Renderings; ausgerechnet das Fenster, das die
   Bibliothek verkaufen soll.
2. **Die Skizzenkarte** — der einzige Bereich, in dem das Layout sichtbar
   zerfallen ist.
3. **Die Menüleiste** — jede Kategoriebenennung wird vom eigenen Stylesheet
   verschluckt.
