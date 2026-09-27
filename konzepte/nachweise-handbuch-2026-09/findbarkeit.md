# Findbarkeit und Auslieferung des Handbuchs — Messung

Anlass: Ein Interessent fand es schwierig, aus dem Handbuch zu lernen; Robert
hält es für umständlich und unübersichtlich. Gemessen wird, **wie gut ein Kunde
findet, was er sucht**, über welche Wege er ins Handbuch kommt und wie es
ausgeliefert wird. Nur gelesen und gemessen, nichts im Repository geändert.

## Gemessener Stand

- **Handbuchtext: Commit `228a05572`** (Zweig `handbuch-umbau`), Sprache
  Deutsch. Der Arbeitsbaum `F:\3D Druck.handbuch` wurde **während** der
  Messung umgebaut (`app/core/manual.py` mit neuer Gliederung `OUTLINE`,
  neues `app/core/guides.py`, Seite „Das Fenster auf einen Blick“; Stand
  `git status` 16:59). Gemessen wurde deshalb an einem Abzug von `app/` aus
  `git archive 228a05572` im Scratchpad. Die ersten Läufe um 16:46 und 16:49
  direkt im Arbeitsbaum liefern **dieselben** Ergebnisse (0 Abweichungen über
  50 Suchen und 50 Seiten).
- **Website und PDF:** die eingecheckten Dateien `website/handbuch.html`,
  `website/<sprache>/manual.html`, `Releases/Solidon3D-Handbuch-*.pdf`
  (im Arbeitsbaum unverändert). Sie werden nur beim Paketbau neu erzeugt und
  können hinter dem Quelltext liegen.
- Zeilenangaben zu `app/core/manual.py` beziehen sich auf `228a05572`, alle
  anderen auf den Arbeitsbaum (dort unverändert).

## Bestand

| | Seiten | Token (`split()`) | Wörter¹ | Anteil Wörter |
|---|---:|---:|---:|---:|
| geschrieben (`INTRODUCTION` + 3D-Maus-Seite) | 30 | 16 792 | 16 331 | 37 % |
| erzeugt: Wissensseiten (`knowledge_pages()`) | 5 | 6 470 | 5 509 | 12 % |
| erzeugt: Referenz, eine Seite je Registerkategorie | 15 | 30 391 | 22 580 | 51 % |
| **zusammen** | **50** | **53 653** | **44 420** | 100 % |

¹ Wörter = Token mit mindestens einem Buchstaben oder einer Ziffer, ohne
Bildverweise. Die oft genannten „rund 53 000 Wörter“ sind die Token-Zahl; sie
zählt die Tabellenstriche der Referenz mit (die Referenz hat 143 Tabellen mit
1 114 Zeilen, siehe Teil 3). **Zwei Drittel des Handbuchs (63 %) sind erzeugt.**

Die fünf längsten Seiten sind alle erzeugt: „Bausteine“ (Referenz) 6 483
Wörter, „Die Werkzeuge der Fernsteuerung“ 3 547, „Skizze“ (Referenz) 3 170,
„Merkmale“ (Referenz) 2 737, „Grundformen“ (Referenz) 2 392. Die längste
geschriebene ist „Was Solidon im Modell erkennt“ mit 2 029. Die vollständige
Seitenliste steht im Anhang.

---

## Teil 1 — Suche im Handbuchfenster

### Was die Suche tut

`ManualWindow._filter` (`app/ui/manual_window.py:420-432`):

```text
wanted = needle.strip().casefold()
Treffer, wenn wanted in str(page.title).casefold() oder wanted in page.text().casefold()
```

Im Skript ohne Qt nachgebildet, mit `manual.pages()` nach
`bootstrap.load_operations()`. Daraus folgen sechs Eigenschaften, jede
gemessen:

1. **Teilzeichenfolge ohne Wortgrenze.** „Spiel“ trifft *Beispielprojekt*
   („Die vier Wege“); bei „Text“ enthalten **7 von 14** Trefferseiten das Wort
   nur in *Kontextmenü*, *Textur*, *Quelltext* oder *Klartext*; bei „messen“
   **19 von 24** nur in *gemessen*, *vermessen* und ähnlichen.
2. **Keine Umlaut- und keine Wortformen-Toleranz.** `casefold()` macht aus ß
   ein ss, aber nicht aus ö ein o: „Loch“ (15 Treffer) und „Löcher“ (12)
   haben nur **6 Seiten gemeinsam**; „hohl“ trifft *Aushöhlen* nicht, „Farbe“
   trifft *Färben* nicht, „bohren“ trifft *gebohrt* nicht.
3. **Mehrere Wörter nur als exakte Folge.** „größer machen“, „Loch
   schließen“, „aufs Bett“: je **0 Treffer**; „Maß ändern“: 1.
4. **Keine Rangfolge.** Die gefilterte Liste bleibt in Handbuchreihenfolge
   (`_fill`, Z. 350-372): alle geschriebenen Seiten vor jeder erzeugten, ein
   Titeltreffer zählt nicht mehr als ein Nebensatz. Gegenprobe mit dem
   eigenen Titelwort von 43 Seiten (Tabelle unten): nur **13 von 43** stehen
   dabei auf Rang 1.
5. **Keine Trefferstelle.** Die erste Seite der Liste wird sofort angezeigt
   (`setCurrentRow(0)`, Z. 372) und an den Seitenanfang gestellt
   (`moveCursor(Start)`, Z. 391). Nichts wird hervorgehoben, es gibt keinen
   Sprung zur Fundstelle und keine Suche innerhalb der Seite: Strg+F setzt
   nur den Fokus ins Suchfeld (Z. 321). Bei **7 von 34** gefundenen
   Zielseiten liegt die erste Fundstelle mehr als 400 Wörter unter dem
   Seitenanfang (≈ eine Bildschirmhöhe²), am weitesten bei „Gehäuse“: Wort
   5 368 von 6 483.
6. **Eine Seite steht fast überall dazwischen.** „Die Werkzeuge der
   Fernsteuerung“ wiederholt jede Operation mit ihrer Beschreibung und ist in
   **30 von 38** Suchen ein Treffer, in 4 davon vor der richtigen Seite.

² Schätzung, nicht gemessen: Fenster 980 × 720 (`manual_window.py:281`),
höchstens 80 Zeichen je Zeile (`MAX_CHARACTERS`, Z. 211) — rund 11 Wörter je
Zeile, rund 35 Zeilen je Bild nach Absatzabständen.

Gesucht wird außerdem im Markdown-Quelltext von `page.text()`, nicht in den
Bildunterschriften und Alt-Texten: die setzt erst `_with_figures` (Z.
395-418) für die Anzeige ein.

### Die Suchen

Wie „richtige Seite“ entschieden wurde: nach Lektüre aller 30 geschriebenen
Seiten und der Operationslisten der Referenz — die Seite, auf der ein Kunde
ohne CAD-Kenntnisse erfährt, **wie er die gesuchte Sache tut**. Wo zwei Seiten
das leisten (geschriebene Erklärung und Referenzeintrag), zählt die besser
platzierte; die andere steht in der Begründung. Nummern 1–38 sind die Suchen
aus dem Auftrag, ² markiert zwölf zusätzliche typische Kundensuchen.

| Nr. | Suche | Treffer | Richtige Seite und Begründung | Rang der richtigen Seite | Erste Fundstelle dort (Wort / Wörter der Seite) | Wort im Handbuch? |
|---:|---|---:|---|---:|---:|---|
| 1 | Loch | 15 | „Die ersten fünfzehn Minuten“: Schritt 5–6 setzt genau ein Loch (Fläche wählen, *Bohrung setzen*). Referenz „Merkmale“ erst Rang 14 | **1** | 26 / 570 | ja |
| 2 | Bohrung | 29 | wie „Loch“; davor steht nur „Was Solidon ist“ (ein Werbesatz). Referenz „Merkmale“ Rang 25 | **2** | 351 / 570 | ja |
| 3 | Gewinde | 7 | „Die Bausteine“ nennt die Mutternfalle als Weg zum belastbaren Gewinde und *gedrucktes Gewinde* in einer Aufzählung; erklärt wird *Druckbares Gewinde* erst in der Referenz „Bausteine“ (Rang 6, Eintrag bei Wort 696 von 6 483) | **2** | 189 / 752 | ja |
| 4 | Gehäuse | 3 | Kein Kapitel baut ein Gehäuse. Passend: *Aushöhlen* („ein Kasten aus einem Quader“, Referenz „Formgebung“) — nicht unter den Treffern — und *Deckel erzeugen* (Referenz „Bausteine“, Rang 3, getroffen nur über den Standfuß bei Wort 5 368) | **3** | 5 368 / 6 483 | nur als Beispiel — *Kasten* (3 Treffer, „Formgebung“ Rang 3) |
| 5 | Deckel | 8 | Referenz „Bausteine“ (*Deckel erzeugen*, *Drehdeckel erzeugen*); die fünf geschriebenen Treffer davor nennen einen Deckel nur als Beispiel | **7** | 358 / 6 483 | ja |
| 6 | drehen | 13 | „Bewegen und Färben“ (Drehringe am Griff, Knopf *Drehen*); Referenz „Transformation“ Rang 9. Wer die *Ansicht* drehen will, findet „Das Fenster“ auf Rang 2 | **4** | 2 / 834 | ja |
| 7 | verschieben | 8 | „Bewegen und Färben“ | **3** | 1 / 834 | ja |
| 8 | spiegeln | 5 | Referenz „Transformation“ (*Spiegeln*, bei Wort 1 004 von 1 192); Rang 1 und 2 sind das Skizzenwerkzeug und die Symmetrie beim Formen | **4** | 1 004 / 1 192 | ja |
| 9 | Maß ändern | 1 | „Was Solidon im Modell erkennt“ (*Bohrung ändern*, Wort 901 von 2 029). Den allgemeinen Weg — Schritt im Verlauf öffnen, Zahl ändern — erklärt „Der Verlauf“, der nicht getroffen wird | **1** | 901 / 2 029 | einmal, als Nebensatz |
| 10 | größer machen | 0 | „Bewegen und Färben“ bzw. Referenz „Transformation“ (*Skalieren*, *Auf Maß bringen*) | **—** | — | nein — das Handbuch sagt *Skalieren* (4 Treffer, Ziel Rang 1) und *Auf Maß bringen*; „größer“ allein: 11 Treffer, keine der beiden Zielseiten |
| 11 | skalieren | 4 | „Bewegen und Färben“ | **1** | 78 / 834 | ja |
| 12 | rückgängig | 7 | „Der Verlauf“ | **1** | 241 / 386 | ja |
| 13 | Slicer | 19 | „Drucken“ (*Slicen*, *Im Slicer öffnen*); davor sieben Seiten, die den Slicer nur nennen | **8** | 21 / 504 | ja |
| 14 | exportieren | 9 | „Auf das Bett und hinaus“ (Export nach STL, 3MF, STEP) — der Titel sagt nicht, dass es um den Export geht | **6** | 2 / 420 | ja |
| 15 | zu groß | 2 | „Wenn das Teil nicht auf das Bett passt“ fehlt unter den Treffern; gefunden wird der Absatz „Zu groß für das Bett?“ in „Auf das Bett und hinaus“, der auf *Trennen* verweist | **1** | 68 / 420 | ja |
| 16 | teilen | 18 | „Wenn das Teil nicht auf das Bett passt“; die Referenz „Teilen und Anpassen“ (Suchwort im Titel) steht auf Rang 16 | **4** | 0 / 553 | ja |
| 17 | Text | 14 | „Beschriften“; 7 der 14 Trefferseiten enthalten „text“ nur in *Kontextmenü*, *Textur*, *Quelltext* oder *Klartext* | **8** | 0 / 351 | ja, meist als Wortteil |
| 18 | Schrift | 7 | „Beschriften“; davor vier Seiten mit *Schriftzug* oder *Beschriftung* als Nebensache | **5** | 0 / 351 | ja |
| 19 | Rundung | 11 | „Was Solidon im Modell erkennt“; erste Fundstelle Wort 76 (Erkennung), der Absatz zum Verrunden einer Kante erst ab Wort 1 343 | **1** | 75 / 2 029 | ja |
| 20 | abrunden | 0 | „Was Solidon im Modell erkennt“ bzw. Referenz „Formgebung“ (*Verrunden*) | **—** | — | nein — *Verrunden* (5 Treffer, Ziel Rang 1) |
| 21 | Fase | 10 | „Was Solidon im Modell erkennt“ (Kantenabsatz); Referenz „Formgebung“ Rang 7 | **1** | 1 373 / 2 029 | ja |
| 22 | Mutter | 7 | „Die Bausteine“ (Mutternfalle) | **2** | 21 / 752 | ja |
| 23 | Schraube | 10 | „Die Bausteine“ (Schraubenloch, Mutternfalle); Referenz „Bausteine“ Rang 10 | **4** | 24 / 752 | ja |
| 24 | Magnet | 7 | „Die Bausteine“ — dort nur ein Wort in einer Aufzählung (Wort 483); die Magnettasche erklärt die Referenz „Bausteine“ (Rang 7, Wort 2 301) | **4** | 483 / 752 | ja |
| 25 | reparieren | 8 | „Die ersten fünfzehn Minuten“ (Schritt 4); „Wenn etwas nicht geht“ Rang 4; Referenz „Reparatur“ Rang 8 | **1** | 296 / 570 | ja |
| 26 | Loch schließen | 0 | „Wenn etwas nicht geht“ (*Reparieren* „schließt kleine Löcher“), Referenz „Reparatur“ bzw. *Bohrung verschließen* | **—** | — | nein — *schließt kleine Löcher*, *Bohrung verschließen*; „Löcher schließen“: 1 Treffer, falsche Seite |
| 27 | hohl | 8 | *Aushöhlen* (Referenz „Formgebung“ Rang 4, „Teilen und Anpassen“ Rang 7); getroffen über *Hohlkehle* und *Hohlraum*, denn „aushöhlen“ enthält „hohl“ nicht | **4** | 1 001 / 1 144 | nur als Wortteil — *aushöhlen* (4 Treffer, Ziel Rang 3) |
| 28 | Wandstärke | 13 | „Hinsehen, bevor gedruckt wird“ | **1** | 32 / 505 | ja |
| 29 | Stütze | 9 | „Drucken“ (Stützen in den Druckeinstellungen); „Auf das Bett und hinaus“ Rang 3 | **2** | 94 / 504 | ja |
| 30 | Überhang | 10 | „Hinsehen, bevor gedruckt wird“ (Analysekarte *Überhang*) | **1** | 38 / 505 | ja |
| 31 | Farbe | 12 | „Bewegen und Färben“; der Abschnitt *Färben* beginnt bei Wort 598 von 834 | **4** | 668 / 834 | ja |
| 32 | zweifarbig | 0 | „Bewegen und Färben“ (*Filament auf eine Fläche*), Referenz „Filament“ | **—** | — | nein — *Zweifarbendruck* (3 Treffer, „Beschriften“ Rang 1), *Mehrfarbendruck* (nur Wörterbuch), *mehrfarbig* (2 Treffer, nur Referenz) |
| 33 | Skizze | 8 | „Zeichnen“ — der Titel enthält das Suchwort nicht | **3** | 239 / 1 427 | ja |
| 34 | zeichnen | 7 | „Zeichnen“ — obwohl das Suchwort der Titel ist | **4** | 0 / 1 427 | ja |
| 35 | Kreis | 8 | „Zeichnen“ (Kreis, Taste C) | **1** | 252 / 1 427 | ja |
| 36 | Passung | 17 | „Material, Toleranzen, Passungen“ — Suchwort im Titel, trotzdem Rang 4 von 17 | **4** | 0 / 299 | ja |
| 37 | Spiel | 13 | „Material, Toleranzen, Passungen“; „Die vier Wege“ trifft nur über *Beispielprojekt* | **4** | 2 / 299 | ja, auch als Wortteil |
| 38 | Toleranz | 12 | „Material, Toleranzen, Passungen“ | **3** | 0 / 299 | ja |
| 39 | Löcher ² | 12 | „Die ersten fünfzehn Minuten“ (Fundstelle: Löcher im Netz, Schritt 3); Referenz „Merkmale“ fehlt — „Loch“ und „Löcher“ liefern verschiedene Listen | **1** | 258 / 570 | ja |
| 40 | gravieren ² | 0 | „Beschriften“ (*Text aufbringen*, vertieft) | **—** | — | nein — *vertieft* (6 Treffer, Ziel Rang 2) |
| 41 | Logo ² | 0 | „Zeichnen“ (SVG hochziehen) oder Referenz „Oberfläche“ (*Relief auflegen*) | **—** | — | nein — *SVG* (4 Treffer, „Zeichnen“ Rang 2) |
| 42 | Zoll ² | 0 | „Die ersten fünfzehn Minuten“ (Einheit beim Einlesen) | **—** | — | nein — *Einheit* (20 Treffer, Ziel Rang 1) |
| 43 | Scharnier ² | 4 | „Die Bausteine“ (Filmscharnier, Bolzenscharnier) | **2** | 161 / 752 | ja |
| 44 | Clip ² | 4 | „Die Bausteine“ (Kabelclip, Wort 456) | **1** | 456 / 752 | ja |
| 45 | Strg+Z ² | 10 | „Der Verlauf“ | **5** | 86 / 386 | ja |
| 46 | aufs Bett ² | 0 | Referenz „Transformation“ (*Auf das Bett setzen*) bzw. „Auf das Bett und hinaus“ | **—** | — | nein — *auf das Bett* (9 Treffer, Ziel Rang 2) |
| 47 | glätten ² | 3 | „Formen“ (Pinsel *Glätten*) und Referenz „Netz glätten und vereinfachen“ (Rang 3) | **1** | 151 / 368 | ja |
| 48 | kopieren ² | 2 | Referenz „Szene“ (*Objekt duplizieren*) oder „Transformation“ (*Kopien in Reihe oder Kreis*) — beide fehlen; die zwei Treffer sind *Anleitung kopieren* | **—** | — | nur in anderer Bedeutung — *duplizieren* (2 Treffer, Ziel Rang 2) |
| 49 | messen ² | 24 | „Hinsehen, bevor gedruckt wird“ (*Messen*); 19 der 24 Trefferseiten enthalten nur *gemessen*, *vermessen* und ähnliche | **2** | 67 / 505 | ja |
| 50 | Bambu ² | 6 | „Drucken“ (Slicer-Übergabe) | **3** | 164 / 504 | ja |

### Kennzahlen

| | 38 Suchen aus dem Auftrag | alle 50 |
|---|---:|---:|
| richtige Seite unter den ersten drei | **19 = 50 %** | 25 = 50 % |
| … davon auf Rang 1, also sofort angezeigt | 11 = 29 % | 14 = 28 % |
| richtige Seite gefunden, aber Rang 4 bis 8 | 15 = 39 % | 16 = 32 % |
| **ohne Treffer** | **4 = 11 %** | 8 = 16 % |
| Treffer, aber keine richtige Seite darunter | 0 | 1 (*kopieren*) |
| **mittlere Trefferzahl** | **8,9** (Median 8; ohne Nullsuchen 10,0) | 8,1 (Median 8) |
| höchste Trefferzahl | 29 (*Bohrung*) | 29 |
| mittlerer Rang der richtigen Seite, wo gefunden | 3,1 (Median 3) | 2,9 (Median 3) |
| erste Fundstelle > 400 Wörter unter dem Seitenanfang | 7 von 34 gefundenen | 8 von 41 |
| „Die Werkzeuge der Fernsteuerung“ unter den Treffern | 30 von 38 | 36 von 50 |

Lesart: Jede zweite Suche aus dem Auftrag bringt die richtige Seite nicht
unter die ersten drei, und nur in 11 von 38 Fällen zeigt das Fenster sofort
die richtige Seite. Scharf gezählt ist die Quote noch niedriger: bei
*Gehäuse* (Rang 3) kommt der Treffer nur über den Standfuß zustande, bei
*Maß ändern* (Rang 1) über einen Nebensatz zu Bohrungen.

### Gegenprobe: das eigene Titelwort

Gesucht wurde je Seite ein Wort aus ihrem Titel; gemessen, auf welchem Rang
die Seite selbst steht (43 Seiten mit einem brauchbaren Titelwort):

| Rang der Seite bei ihrem Titelwort | Seiten |
|---|---:|
| Rang 1 | 13 |
| Rang 2–3 | 11 |
| Rang 4–8 | 17 |
| schlechter als Rang 8 | 2 |

Die auffälligsten: „Drucken“ → Kapitel „Drucken“ Rang 7 von 18; „Verlauf“ →
„Der Verlauf“ Rang 7 von 25; „Bausteine“ → „Die Bausteine“ Rang 6 und die
Referenz „Bausteine“ **Rang 15 von 16**; „Filament“ → Referenz „Filament“
**Rang 14 von 15**; „Merkmale“ → Referenz „Merkmale“ Rang 7 von 8;
„Szene“ → Referenz „Szene“ Rang 8 von 9. Median über alle 43: Rang 3.

### Befund Teil 1

- Die Suche findet **Wörter, keine Themen**: 4 von 38 Kundensuchen finden
  nichts, weil das Handbuch ein anderes Wort benutzt (*abrunden* →
  *Verrunden*, *zweifarbig* → *Zweifarbendruck*, *größer machen* →
  *Skalieren*, *Loch schließen* → *schließt kleine Löcher*).
- Wo sie etwas findet, **ordnet sie nicht**: im Mittel 8,9 Treffer in
  Handbuchreihenfolge, die richtige Seite im Median auf Rang 3 — und der
  Titel einer Seite zählt nicht mehr als ein Nebensatz in einer anderen.
- Nach dem Treffer **zeigt sie die Stelle nicht**: kein Hervorheben, kein
  Sprung; 7 von 34 gefundenen Zielseiten verlangen mehr als eine
  Bildschirmhöhe Suchen, die Referenzseite „Bausteine“ bei *Gehäuse* rund
  13 (Wort 5 368 bei ≈ 400 Wörtern je Bild).

---

## Teil 2 — Einstiege und Wege

### Wo man hineinkommt

| Einstieg | Auslöser | Code | Öffnet | Text, der das Handbuch beschreibt |
|---|---|---|---|---|
| *Hilfe → Handbuch …* | Menü oder F1 (`QKeySequence.StandardKey.HelpContents`) | `main_window.py:4370-4378` | keine bestimmte Seite: beim ersten Öffnen Listenplatz 1 „Was Solidon ist“, danach die zuletzt gezeigte Seite samt altem Suchfilter | **„Jede Operation mit ihren Werten, nach Bereichen sortiert.“** (Statuszeile und Tooltip, `_add_action` Z. 4763-4765) |
| Befehlspalette, Eintrag *Handbuch …* | Palette | `main_window.py:9394` | wie oben | Kürzel fest als „F1“ eingetragen, auch unter macOS, wo `HelpContents` nicht F1 ist |
| Startbildschirm, Knopf *Handbuch* | Klick | `start_screen.py:894-900` → `main_window.py:3318-3319` | „Die ersten fünfzehn Minuten“ (`FIRST_MINUTES`), Suchfeld geleert (`show_page`, `manual_window.py:434-440`) | Tooltip „Die ersten fünfzehn Minuten, von vorn erklärt.“ |
| Statusleiste *3D-Maus-Hilfe → Handbuch öffnen* | nur sichtbar, wenn eine 3D-Maus gesperrt ist | `main_window.py:3576-3594`, `6929-6935` | „Wenn die 3D-Maus nicht reagiert“ | — |
| Kommandozeile `docs --manual` | `python -m app.cli.main docs --manual` | `app/cli/main.py:243-249`, `765-771` | das ganze Handbuch als Markdown auf die Konsole | *docs* ohne Schalter: „Erzeugte Referenz ausgeben“ |
| Operationsdialog | — | `op_dialog.py` | **kein Einstieg**: kein Hilfeknopf, keine F1-Belegung, kein Verweis; „Handbuch“ steht dort nur in Kommentaren (Z. 253, 363, 543, 1676, 2213) | — |

`action_manual` (`main_window.py:6883-6912`) hat vier Aufrufer: Hilfe-Menü
und Palette ohne Seite, Startbildschirm mit `"start"`, 3D-Maus-Hilfe mit
`"spacemouse-access"`. Die Beschreibung im
Hilfe-Menü nennt nur die erzeugte Hälfte; dass es 30 geschriebene Kapitel zum
Lernen gibt, sagt sie nicht. (Nebenbei: der Kommentar über `FIRST_MINUTES`,
`manual.py:78`, nennt den Knopftext noch „Handbuch — die ersten fünfzehn
Minuten“; der Knopf heißt heute „Handbuch“, der Rest steht im Tooltip.)

### Wohin F1 führt

| Wo der Kunde gerade ist | Ergebnis von F1 | Beleg |
|---|---|---|
| Hauptfenster oder Startbildschirm | Handbuch öffnet, **ohne Bezug zur Lage**: erste bzw. zuletzt gezeigte Seite | `action_manual()` ohne `page`; Nachbau: F1 löst die Menüaktion aus (1 von 1) |
| Skizzenmodus | dasselbe — **nicht** das Kapitel „Zeichnen“ | Der Skizzenmodus liegt im Hauptfenster (`SketchPanel` an Ansicht und rechtem Reiter, `main_window.py:9956 ff.`); `sketch_editor.py` belegt F1 nicht (keine Fundstelle für `Key_F1`/`HelpContents`) |
| Offener Operationsdialog, Fokus im Dialog | **nichts** | Der Dialog ist ein eigenes, nicht modales Fenster (`_open_operation_dialog`, `main_window.py:17801 ff.`, bewusst ohne `exec()`); die Menüaktion hat den Kontext des Hauptfensters. Nachbau mit derselben Anordnung (`QAction` mit `HelpContents` im Menü, `QDialog` als Kind mit `show()`): F1 im Hauptfenster 1 Auslösung, F1 im Dialog **0** |
| Handbuchfenster selbst | nichts (eigenes Fenster, gleicher Grund); Esc schließt es, Strg+F setzt den Fokus ins Suchfeld | `manual_window.py:321-322` |

Der Nachbau ist ein eigenes Skript ohne Solidon-Code (Scratchpad
`fb_f1_probe.py`, offscreen); er belegt das Qt-Verhalten der Anordnung, nicht
die laufende Anwendung.

### Kontextbezogene Hilfe

**Es gibt keine.** `manual.find(key)` ist dafür gebaut („für den Weg von
einer Operation in ihr Kapitel“, `manual.py:2845-2850`) und wird in `app/`
**nirgends aufgerufen** (Suche nach `manual.find`: 0 Aufrufer). Keine
Operation, kein Dialog, kein Prüfbefund führt in ein Kapitel. Zwei Schlüssel
kommen außerdem doppelt vor — `sketch` („Zeichnen“ und Referenz „Skizze“) und
`parts` („Die Bausteine“ und Referenz „Bausteine“); `find` und
`ManualWindow.show_page` (Z. 437-440) nehmen jeweils die erste, also die
geschriebene Seite. Ein künftiger Weg „Operation → ihr Referenzkapitel“ käme
bei diesen beiden Kategorien auf der falschen Seite an. Die Website löst das
mit dem Ankervorsatz `ref-` (`tools/make_manual.py:440-452`), das Fenster nicht.

### Im Fenster: keine sichtbare Gliederung

Die Seitenliste ist eine flache `QListWidget` mit 50 Titeln, ohne Nummer,
Zwischenüberschrift oder Trenner (`_fill`, `manual_window.py:350-370`). Die
einzige Unterscheidung — Statustipp „Erklärung, kein Nachschlagewerk“ bzw.
„Alle Operationen dieses Bereichs“ (Z. 363-369) — **erscheint nie**:
`ManualWindow` legt keine Statusleiste an (kein `statusBar()` in der Datei),
und Qt zeigt Statustipps nur dort. Nachbau (`fb_statustip_probe.py`): Das
Handbuchfenster hat keine Statusleiste, das Hauptfenster erhält den Tipp
nicht. Der Tooltip wiederholt nur den Titel (Z. 368).

### Verweise zwischen Seiten

- **Markdown-Links: 0** in 50 Seiten (ohne Bildverweise). Sie würden auch
  nicht wirken: `_open_link` (`manual_window.py:327-346`) öffnet nur
  `https`-Adressen der eigenen Website; ein Sprung auf ein anderes Kapitel ist
  im Fenster nicht vorgesehen.
- **Verweise als Text: 11** in den 30 geschriebenen Seiten — 5 mit Titel
  (*Bewegen und Färben* → *Was Solidon im Modell erkennt*, *Der Verlauf* →
  *Eigene Bausteine*, *Eigene Bausteine* → *Parameter und Ausdrücke*, *Auf das
  Bett und hinaus* → *Drucken*, *Zusätzliche Programme einrichten* → *Welche
  Modelle Solidon benutzt*), 6 als Umschreibung („das Kapitel über die
  Merkmale“, „im Kapitel davor“, „weiter unten“, „aus dem vorigen Kapitel“,
  „im nächsten Kapitel“, „der folgenden Kapitel“). Keiner ist anklickbar.
- **Zwei davon stimmen nicht:**
  - „Welche Modelle das sind und woher sie kommen, steht im **nächsten**
    Kapitel“ (*Zusätzliche Programme einrichten*, `manual.py:1859-1860`): Das
    nächste Kapitel ist „Oberflächen und Füllungen“ (Platz 24); gemeint ist
    Platz 31.
  - „Jede Operation der folgenden Kapitel ist eines … **Eine eigene
    Schnittstellenliste gibt es deshalb nicht**“ (*Fernsteuerung*,
    `manual.py:2001-2006`): Genau diese Liste ist Platz 34, „Die Werkzeuge der
    Fernsteuerung“ (`remote_text`, `manual.py:2406 ff.`, 3 547 Wörter).

### Befund Teil 2

- Vier Einstiege führen ins Handbuch (Menü/F1, Palette, Startbildschirm,
  3D-Maus-Hilfe), **keiner aus der Arbeit heraus**: kein Operationsdialog,
  kein Prüfbefund, kein Werkzeug öffnet ein passendes Kapitel; F1 öffnet
  immer dieselbe Stelle und im Operationsdialog gar nichts.
- Das Hilfe-Menü beschreibt das Handbuch als Nachschlagewerk („Jede
  Operation mit ihren Werten“) — der einzige Satz, den ein Kunde vor dem
  Öffnen liest, verschweigt die Einführung.
- Zwischen den Seiten gibt es keinen einzigen Link, und zwei der elf
  Textverweise führen ins Leere.

---

## Teil 3 — Ausgabewege

Alle drei Ausgaben tragen denselben Text in derselben Reihenfolge
(`manual.as_markdown` / `as_html`, `tools/make_manual.py:673-742`): Fenster,
Website, PDF. Gelesen, nicht ausgeführt: `tools/make_manual.py`.

### Website

| Sprache | Datei | Größe | Wörter³ | Bilder (Bildschirmfotos PNG / SVG) | Tabellen (Zeilen) | Verzeichnis |
|---|---|---:|---:|---|---:|---:|
| de | `website/handbuch.html` | 444 KB | 44 466 | 41 (9 / 32) | 143 (1 114) | 50 |
| en | `website/en/manual.html` | 426 KB | 48 995 | 41 (9 / 32) | 143 (1 114) | 50 |
| es | `website/es/manual.html` | 455 KB | 51 891 | 41 (9 / 32) | 143 (1 113) | 50 |
| fr | `website/fr/manual.html` | 480 KB | 51 602 | 41 (9 / 32) | 143 (1 113) | 50 |
| it | `website/it/manual.html` | 455 KB | 48 634 | 41 (9 / 32) | 143 (1 114) | 50 |
| pt | `website/pt/manual.html` | 449 KB | 49 765 | 41 (9 / 32) | 143 (1 114) | 50 |

³ Token mit Buchstabe oder Ziffer im `<main>` ohne Verzeichnis
(`html.parser`, Scratchpad `fb_site.py`).

**Eine Seite für alles.** Deckblatt (nur im Druck), `<h1>`, ein Satz Vorspann
und das Verzeichnis, danach alle 50 Kapitel hintereinander. Keine Suche auf der
Seite außer der des Browsers; `site.js` markiert beim Lesen nur den aktuellen
Verzeichniseintrag (`site.js:22-56`), das Verzeichnis selbst bleibt aber am
Seitenanfang und läuft nicht mit. Zurück kommt man über „Inhalt“ in der
stehenden Kopfzeile (`make_manual.py:396-417`).

**Das Verzeichnis** (`nav.toc`, `make_manual.py:455-489`): Überschrift
„Inhalt“, eine nummerierte Liste 01–30 in zwei Spalten, dann ein gedämpfter
Zwischentitel **„Referenz — jede Operation mit ihren Werten“** und die Liste
31–50. Die Nummern stehen auch über den Kapiteln.

- **Geschriebenes und Erzeugtes sind getrennt, Anfang und Fortgeschrittenes
  nicht.** Die 30 geschriebenen Kapitel sind eine Liste: 02 „Die ersten
  fünfzehn Minuten“ steht in derselben Reihe wie 15 „Bausteindateien
  austauschen“, 23 „Zusätzliche Programme einrichten“, 26 „Fernsteuerung“, 27
  „Freischaltung“ und 30 „Wenn die 3D-Maus nicht reagiert“; Hilfe bei
  Problemen (28) und Wörterbuch (29) stehen mittendrin zwischen Freischaltung
  und 3D-Maus.
- **Der Zwischentitel stimmt für 5 von 20 Einträgen nicht:** 31–35 („Welche
  Modelle Solidon benutzt“, „Wonach Solidon urteilt“, „Material, Drucker,
  Normteile“, „Die Werkzeuge der Fernsteuerung“, „Meldungen im Wortlaut“) sind
  keine Operationen.
- Im **Fenster** gibt es diese Trennung gar nicht (Teil 2: flache Liste, der
  Statustipp erscheint nie).

**Länge — gemessen**, nicht geschätzt: QtWebEngine (offscreen, ohne
dauerhaftes Profil, mit den eigenen Webschriften der Seite, alle geladen),
`website/handbuch.html` über `file://`, Höhe per JavaScript abgefragt
(Scratchpad `fb_web_height.py`). Ab 1 366 px Breite ist das Layout gleich, weil
`main` auf 74 rem begrenzt ist.

| Ansicht | Seitenhöhe | Bildschirmhöhen | 30 geschriebene Kapitel | 20 erzeugte Kapitel | Verzeichnis |
|---|---:|---:|---:|---:|---:|
| 1920 × 970 (Full-HD-Browser) | 182 312 px | **188** | 66,5 | 119,6 | 1,3 |
| 1366 × 650 (Laptop) | 182 312 px | **280** | 99,3 | 178,5 | 1,9 |
| 390 × 760 (Telefon) | 335 661 px | **442** | 119,3 | 318,4 | 3,1 |

- **Tabellen nehmen 36 %** der Seitenhöhe ein (65 843 px), auf dem Telefon
  51 %; Bilder 8 %. Das erste Kapitel beginnt bei 1 614 px, also nach 1,7
  Bildschirmhöhen.
- Die längsten Kapitel (Bildschirmhöhen bei 1920 × 970): „Bausteine“
  (Referenz) **28,7**, „Die Werkzeuge der Fernsteuerung“ 13,4, „Skizze“
  (Referenz) 12,0, „Grundformen“ 11,5, „Merkmale“ 11,2. Das längste
  geschriebene: „Die Bausteine“ 6,1 (zehn Bilder), „Zeichnen“ 5,9, „Was
  Solidon im Modell erkennt“ 5,8, „Die ersten fünfzehn Minuten“ 4,3.

**Bilder:** 41, davon 34 verschiedene (Wiederholungen: *split* dreimal,
*layers*, *part-fit-ladder*, *drill*, *part-nut-trap*, *texture* je zweimal).
**9 sind Bildschirmfotos der Oberfläche** (PNG): Startbildschirm,
Prüfbericht, Hauptfenster, Operationsdialog, Zeichenmodus, Ergebnis einer
Skizze, Bausteinkatalog, Eigener Baustein, Druckeinstellungen. Die übrigen 32
sind Zeichnungen und gerenderte Körper (SVG); auch „Das Fenster“ erklärt sich
über ein Schema, nicht über ein Foto. 37 Bilder stehen in den 30 geschriebenen
Kapiteln, 4 in den 20 erzeugten. **15 der 30 geschriebenen Kapitel haben kein
Bild** — darunter das längste, „Was Solidon im Modell erkennt“ (2 029 Wörter),
sowie „Bewegen und Färben“ (834), „Wenn etwas nicht geht“ (890) und
„Beschriften“ (351). Gewicht: 444 KB HTML plus 1,98 MB für die 34 Bilder.

### PDF

| Sprache | Datei | Größe | Blätter |
|---|---|---:|---:|
| de | `Releases/Solidon3D-Handbuch-de.pdf` | 13,9 MB | 197 |
| en | `…-en.pdf` | 13,3 MB | 187 |
| es | `…-es.pdf` | 14,2 MB | 212 |
| fr | `…-fr.pdf` | 14,6 MB | 215 |
| it | `…-it.pdf` | 14,1 MB | 213 |
| pt | `…-pt.pdf` | 14,1 MB | 208 |

Gelesen mit `pypdf` aus der vorhandenen `.venv` (Scratchpad `fb_pdf.py`). A4,
erzeugt am 24.09.2026 für Version 0.5.0 (Metadaten), gedruckt aus derselben
HTML-Seite über Chromium (`write_pdf`, `make_manual.py:771 ff.`).

Aufteilung des deutschen PDF nach den benannten Zielen der Kapitel:

| Blätter | Inhalt | Anteil |
|---|---|---:|
| 1 | Deckblatt | |
| 2–3 | Verzeichnis, 50 verlinkte Einträge (40 + 10 Links) | |
| 4–48 | 30 geschriebene Kapitel | 45 Blätter = 23 % |
| 49–68 | 5 Wissensseiten | 20 Blätter = 10 % |
| 69–197 | 15 Referenzkapitel | **129 Blätter = 65 %** |

Die Referenz „Bausteine“ allein belegt 32 Blätter, „Skizze“ 19, „Merkmale“ 16,
„Grundformen“ 15, „Die Werkzeuge der Fernsteuerung“ 9. Die Kopfzeile nennt das
laufende Kapitel, die Fußzeile „Handbuch · Solidon3D 0.5.0 · Seite n von 197“.

- **Keine Lesezeichen:** Die PDF-Gliederung ist in allen sechs Dateien leer
  (`reader.outline`: 0 Einträge). Die Seitenleiste eines PDF-Betrachters
  zeigt also keine Kapitel; springen geht nur über das Verzeichnis auf Blatt
  2–3.
- **Neun tote Verweise je PDF, 54 insgesamt:** Jedes Bildschirmfoto trägt
  einen Link nach `file:///F:/3D%20Druck/website/handbuch/<sprache>/….png`.
  Ursache: `_staged` (`make_manual.py:628-662`) legt um jedes Bildschirmfoto
  einen Verweis auf die Bilddatei — auf der Website richtig (antippen,
  vergrößern) —, und der Chromium-Druck macht daraus den absoluten Pfad des
  Bau-Rechners. Beim Kunden führt der Klick ins Leere und zeigt den Pfad.

### Befund Teil 3

- Die Website ist **eine einzige Seite von 188 Bildschirmhöhen** (Full HD),
  auf dem Telefon 442; 64 % der Höhe sind die 20 erzeugten Kapitel, 36 %
  Tabellen.
- Das Verzeichnis trennt Geschriebenes von Erzeugtem, aber nicht **Anfang von
  Vertiefung**, und sein Zwischentitel beschreibt 5 der 20 Einträge falsch.
- **9 von 41 Bildern zeigen die Oberfläche**; 15 der 30 Kapitel zum Lernen
  sind reiner Text.
- Das PDF hat 197 Blätter, zu 76 % Referenz und Wissen, **keine Lesezeichen**
  und je neun Links auf `F:\3D Druck`.

---

## Teil 4 — Die erzeugte Referenz

20 Seiten mit `generated=True`: 5 Wissensseiten aus `knowledge_pages()`
(`manual.py:2771-2826`) und 15 Kategorieseiten aus dem Register
(`documentation`, `app/core/registry/surfaces.py:633-705`). Gezählt am
HEAD-Abzug (Scratchpad `fb_reference.py`). „Weg“ = die Beschreibung einer
Operation nennt, wo man sie in der Oberfläche findet (rechts, Menü, Knopf,
Klick, Kontextmenü, *Datei →* …; Tabellen ausgenommen).

### Die fünf Wissensseiten

| Platz | Seite | Wörter | Inhalt | Taugt zum | Beleg |
|---:|---|---:|---|---|---|
| 31 | Welche Modelle Solidon benutzt | 793 | 3 Tabellen (14 Zeilen) zu Sprach- und Erzeugungsmodellen, Größen, Messungen | Nachschlagen — nur wer Chat oder Erzeugen einrichtet | kein Wort zur Konstruktion |
| 32 | Wonach Solidon urteilt | 226 | die 9 Regeln der Regelsammlung (Version 4) | kaum — an den Agenten gerichtet | „Diese Regeln liegen dem Agenten bei jeder Anfrage vor“; Innenwörter *Op/Ops* (3), *ask_user*, *Primitiven*, *Koinzidente Flächen*, *Booleschen Ops* |
| 33 | Material, Drucker, Normteile | 445 | 3 Tabellen (34 Zeilen): Spiel je Material, Bauraum je Drucker, Schraubenmaße | Nachschlagen | beantwortet „woher kommt dieser Wert?“ |
| 34 | **Die Werkzeuge der Fernsteuerung** | **3 547** | 153 Einträge mit Leitungsnamen in Backticks | **gar nicht — für Programmierer** | siehe unten |
| 35 | Meldungen im Wortlaut | 498 | 35 Meldungen, je mit den Knöpfen, die dann angeboten werden | Nachschlagen einer gesehenen Meldung | „Was hilft“ nennt nur Knopfnamen, keine Erklärung; bei 1 Meldung nur *Abbrechen* |

**„Die Werkzeuge der Fernsteuerung“ — für wen?** Für jemanden, der ein
**fremdes Programm per MCP** an Solidon anschließt: Der Docstring von
`remote_text` (`manual.py:2406-2416`) sagt es selbst — die Liste sei „genau
das, was jemand braucht, der eine Gegenstelle einrichtet“. Die Fernsteuerung
ist ab Werk aus (Seite „Fernsteuerung“, `manual.py:1976 ff.`). Gemessen:

- 153 Einträge: **alle 142 Operationen des Registers**, dazu 10 Werkzeuge der
  Agentenschicht (`read_report`, `set_parameter`, `undo_transaction` …) und
  die gesperrte Rückfrage `ask_user`. Jede der 142 Beschreibungen steht
  **wörtlich auch in der Referenz** (142 von 142) — die Seite ist eine zweite,
  gekürzte Referenz, gegliedert nach denselben 15 Kategorien.
- 153 Namen in Backticks (`arrange_bed`, `drill_hole` …), die nur eine
  Gegenstelle senden muss.
- Kosten für alle anderen: 3 547 Wörter (8 % des Handbuchs), 13,4
  Bildschirmhöhen auf der Website, 9 PDF-Blätter, und **Treffer in 30 von 38
  Kundensuchen** (Teil 1), in vier davon vor der richtigen Seite.
- Sie widerspricht der geschriebenen Seite „Fernsteuerung“, die sagt, eine
  eigene Schnittstellenliste gebe es nicht (Teil 2).

### Die fünfzehn Kategorieseiten

| Platz | Seite | Wörter | Operationen | Parameterzeilen | Bilder | „Wann nicht“ | Titel doppelt | Kürzel |
|---:|---|---:|---:|---:|---:|---:|---:|---:|
| 36 | Szene | 413 | 6 | 11 | 0 | 1 | 0 | 4 |
| 37 | Reparatur | 152 | 1 | 7 | 0 | 0 | 0 | 1 |
| 38 | Transformation | 1 192 | 10 | 41 | 0 | 0 | 0 | 4 |
| 39 | Grundformen | 2 392 | 13 | 145 | 0 | 0 | 5 | 0 |
| 40 | Verbinden und Abziehen | 213 | 4 | 2 | 0 | 1 | 0 | 3 |
| 41 | Skizze | 3 170 | 10 | 124 | 0 | 4 | 0 | 0 |
| 42 | Formgebung | 1 144 | 6 | 28 | 0 | 5 | 0 | 1 |
| 43 | Merkmale | 2 737 | 13 | 113 | 1 | 0 | 1 | 1 |
| 44 | **Bausteine** | **6 483** | **48** | **268** | 1 | 17 | 10 | 0 |
| 45 | Teilen und Anpassen | 1 595 | 9 | 53 | 1 | 5 | 0 | 1 |
| 46 | Import | 535 | 3 | 24 | 0 | 0 | 0 | 0 |
| 47 | Filament | 347 | 4 | 15 | 0 | 0 | 0 | 0 |
| 48 | Beschriftung | 556 | 2 | 27 | 0 | 0 | 0 | 0 |
| 49 | Oberfläche | 759 | 3 | 26 | 1 | 2 | 0 | 0 |
| 50 | Netz glätten und vereinfachen | 892 | 10 | 16 | 0 | 6 | 0 | 0 |
| | **zusammen** | **22 580** | **142** | **900** | **4** | **41** | **16** | **15** |

„Titel doppelt“ zählt je Seite die zweite Operation mit gleichem Titel. Über
das ganze Register tragen **17 Titel je zwei Operationen** (34 von 142), etwa
„Kegel anlegen“ als `create_cone` und `create_brep_cone`, „Bohrung setzen“ als
`drill_hole` und `drill_brep_hole`, „Aushöhlen“ einmal unter „Formgebung“ und
einmal unter „Teilen und Anpassen“. Die Überschrift unterscheidet sie nur am
Leitungsnamen in Klammern.

Jeder Eintrag hat denselben Aufbau (`surfaces.py:667-704`): Überschrift mit
Leitungsname, **ein bis zwei Sätze** Beschreibung (142 Beschreibungen: Median
19,5 Wörter, höchstens 49), bei 41 Operationen ein „Wann nicht“, eine
Kennzeile und die Parametertabelle.

**Zum Lernen taugt keine der 15 Seiten, zum Nachschlagen alle.** Gemessen:

- **Kein Weg zur Operation:** 2 von 142 Beschreibungen sagen, wo man die
  Operation in der Oberfläche findet; 15 nennen ein Tastenkürzel. Die
  Zuordnung zu Menü und Auswahlfenster (`MENU_GROUPS`, `PANEL_CATEGORIES`,
  `app/core/registry/registry.py:117-145`) kommt in der Referenz nicht vor.
- **Drei Viertel Tabelle:** 16 912 der 22 580 Wörter (75 %) stehen in
  Parametertabellen — 900 Zeilen, jede mit dem internen Schlüssel in Backticks
  (`feature`, `largest` …).
- **Innensprache im Kundentext:** Alle 142 Einträge tragen die Kennzeile
  „Objekte: 1 → 1 · umkehrbar · ohne Zufall“; **72 der 900 Parameterzeilen**
  nennen als Bereich englische Programmwerte (*rectangle, circle, slot,
  polygon, drawn*; *centre, origin, bed*; *round, hex, dovetail*).
- **Kaum Bilder:** 4 Bilder für 142 Operationen.
- Wertvoll für Lernende sind die **41 „Wann nicht“-Absätze** — sie stehen
  aber nur hier, in Seiten von 1 bis 29 Bildschirmhöhen.

### Befund Teil 4

- Die erzeugten Seiten machen 63 % der Wörter, 64 % der Website-Höhe und
  76 % der PDF-Blätter aus; sie sind **Nachschlagewerk ohne Weg in die
  Oberfläche** (2 von 142 Einträgen nennen ihn).
- „Die Werkzeuge der Fernsteuerung“ ist eine **zweite Referenz für
  MCP-Anbinder** (142 von 142 Beschreibungen doppelt), 3 547 Wörter lang und in
  30 von 38 Kundensuchen im Weg.
- Die Referenz spricht die Sprache des Registers: Leitungsnamen, englische
  Auswahlwerte (72 Zeilen), „umkehrbar · ohne Zufall“ und 17 doppelt
  vergebene Titel.

---

## Die wichtigsten Befunde

1. **Die Suche bringt jede zweite Kundensuche nicht unter die ersten drei**
   (19 von 38) und zeigt nur 11 von 38 Mal sofort die richtige Seite — sie
   filtert per Teilzeichenfolge in Handbuchreihenfolge, ohne Rangfolge, ohne
   Trefferstelle (`manual_window.py:420-432`); 4 von 38 Suchen finden nichts,
   weil das Handbuch andere Wörter benutzt.
2. **Kein Weg aus der Arbeit ins passende Kapitel:** `manual.find` hat 0
   Aufrufer, F1 öffnet immer dieselbe Stelle und im Operationsdialog nichts;
   die einzige Beschreibung im Hilfe-Menü nennt nur die Referenz.
3. **Zwei Drittel sind Nachschlagewerk:** 63 % der 44 420 Wörter sind
   erzeugt, 2 von 142 Referenzeinträgen sagen, wo die Operation in der
   Oberfläche steht; 75 % der Referenzwörter stehen in Tabellen.
4. **Eine Seite für alles:** Die Website-Seite ist 188 Bildschirmhöhen lang
   (Telefon 442), das PDF 197 Blätter ohne Lesezeichen und mit 9 toten
   `file:///F:/3D%20Druck/…`-Links je Sprache; Anfänger- und
   Fortgeschrittenenkapitel stehen ungetrennt in einer Liste.
5. **„Die Werkzeuge der Fernsteuerung“** ist eine zweite Referenz für
   MCP-Anbinder (3 547 Wörter, 142 von 142 Beschreibungen doppelt) und steht in
   30 von 38 Kundensuchen unter den Treffern.

---

## Anhang: Seitenliste (Stand `228a05572`)

| Platz | Schlüssel | Titel | Art | Wörter | Bilder |
|---:|---|---|---|---:|---:|
| 1 | what | Was Solidon ist | geschrieben | 180 | 0 |
| 2 | start | Die ersten fünfzehn Minuten | geschrieben | 570 | 5 |
| 3 | window | Das Fenster | geschrieben | 830 | 1 |
| 4 | looking | Hinsehen, bevor gedruckt wird | geschrieben | 505 | 1 |
| 5 | features | Was Solidon im Modell erkennt | geschrieben | 2 029 | 0 |
| 6 | moving | Bewegen und Färben | geschrieben | 834 | 0 |
| 7 | sketch | Zeichnen | geschrieben | 1 427 | 4 |
| 8 | ways | Die vier Wege | geschrieben | 212 | 1 |
| 9 | sculpting | Formen | geschrieben | 368 | 0 |
| 10 | history | Der Verlauf | geschrieben | 386 | 1 |
| 11 | parameters | Parameter und Ausdrücke | geschrieben | 388 | 1 |
| 12 | tolerances | Material, Toleranzen, Passungen | geschrieben | 299 | 3 |
| 13 | parts | Die Bausteine | geschrieben | 752 | 10 |
| 14 | own-parts | Eigene Bausteine | geschrieben | 592 | 1 |
| 15 | exchange | Bausteindateien austauschen | geschrieben | 391 | 0 |
| 16 | print | Drucken | geschrieben | 504 | 1 |
| 17 | resin | Harz statt Filament: Resin-Drucker | geschrieben | 193 | 0 |
| 18 | export | Auf das Bett und hinaus | geschrieben | 420 | 4 |
| 19 | splitting | Wenn das Teil nicht auf das Bett passt | geschrieben | 553 | 1 |
| 20 | variants | Ausprobieren statt raten: Varianten und Kalibrieren | geschrieben | 215 | 1 |
| 21 | chat | Der Chat | geschrieben | 298 | 0 |
| 22 | generating | Ein Modell erzeugen lassen | geschrieben | 299 | 0 |
| 23 | extras | Zusätzliche Programme einrichten | geschrieben | 1 038 | 0 |
| 24 | surfaces | Oberflächen und Füllungen | geschrieben | 339 | 2 |
| 25 | labels | Beschriften | geschrieben | 351 | 0 |
| 26 | remote | Fernsteuerung | geschrieben | 210 | 0 |
| 27 | activation | Freischaltung | geschrieben | 282 | 0 |
| 28 | trouble | Wenn etwas nicht geht | geschrieben | 890 | 0 |
| 29 | glossary | Wörterbuch | geschrieben | 739 | 0 |
| 30 | spacemouse-access | Wenn die 3D-Maus nicht reagiert | geschrieben | 237 | 0 |
| 31 | models | Welche Modelle Solidon benutzt | Wissen | 793 | 0 |
| 32 | rules | Wonach Solidon urteilt | Wissen | 226 | 0 |
| 33 | profiles | Material, Drucker, Normteile | Wissen | 445 | 0 |
| 34 | remote-tools | Die Werkzeuge der Fernsteuerung | Wissen | 3 547 | 0 |
| 35 | messages | Meldungen im Wortlaut | Wissen | 498 | 0 |
| 36 | scene | Szene | Referenz | 413 | 0 |
| 37 | repair | Reparatur | Referenz | 152 | 0 |
| 38 | transform | Transformation | Referenz | 1 192 | 0 |
| 39 | primitive | Grundformen | Referenz | 2 392 | 0 |
| 40 | boolean | Verbinden und Abziehen | Referenz | 213 | 0 |
| 41 | sketch | Skizze | Referenz | 3 170 | 0 |
| 42 | shaping | Formgebung | Referenz | 1 144 | 0 |
| 43 | holes | Merkmale | Referenz | 2 737 | 1 |
| 44 | parts | Bausteine | Referenz | 6 483 | 1 |
| 45 | prepare | Teilen und Anpassen | Referenz | 1 595 | 1 |
| 46 | import | Import | Referenz | 535 | 0 |
| 47 | colour | Filament | Referenz | 347 | 0 |
| 48 | label | Beschriftung | Referenz | 556 | 0 |
| 49 | surface | Oberfläche | Referenz | 759 | 1 |
| 50 | mesh | Netz glätten und vereinfachen | Referenz | 892 | 0 |

Hilfsskripte (nur im Scratchpad dieser Sitzung, nicht im Repository):
`fb_search.py` (Suche, Teil 1), `fb_titles.py` (Titelwort, Wortzahlen,
Kennzahlen), `fb_f1_probe.py` und `fb_statustip_probe.py` (Qt-Nachbauten,
Teil 2), `fb_site.py`, `fb_web_height.py`, `fb_pdf.py` (Teil 3),
`fb_reference.py` (Teil 4). Die Suche selbst ist drei Zeilen und oben
wiedergegeben; jede Zahl lässt sich damit an `228a05572` nachrechnen.
