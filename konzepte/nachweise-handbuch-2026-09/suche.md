# Suche im Handbuch: vorher und nachher (HB-6)

Messung vom 27.09.2026 auf dem Zweig `handbuch-umbau` nach `3d2af85fd`, Sprache
Deutsch. Gehört zu §7 von
[`konzept-handbuch-2026-09.md`](../konzept-handbuch-2026-09.md). Die Suchen und
ihre Zielseiten stehen ausführbar in `tests/test_manual_search.py`
(`CUSTOMER_SEARCHES`); wer eine Zahl braucht, fährt den Test oder misst am
heutigen Stand nach.

## Wie gemessen wurde

- **Suchen:** die 50 aus [`findbarkeit.md`](findbarkeit.md), Teil 1 — 38 aus
  dem Auftrag, zwölf zusätzliche (²).
- **Zielseiten:** wie in `findbarkeit.md`. Dazu kommen die Bildanleitungen, wo
  sie die Antwort sind (*Ein Loch bohren* für „Loch“, „Bohrung“, „Löcher“;
  *Ein Modell prüfen und drucken* für „Slicer“), bei „Gehäuse“ die Referenz
  *Teilen und Anpassen* mit *Aushöhlen*, bei „Bambu“ die Druckerliste und bei
  „Zoll“ die Referenz *Import* mit der Einheit.
- **Vorher** ist die Suche, die das Fenster bis dahin hatte (Zeichenfolge in
  Titel oder Text, Liste in Handbuchreihenfolge), auf den **heutigen** Seiten.
  Deshalb weicht „vorher“ von den 50 Prozent in `findbarkeit.md` ab: Die
  Bildanleitungen stehen vorn und sind selbst Ziele.
- **Nachher** ist `app/core/manual_search.py`.

## Kennzahlen

| | 38 aus dem Auftrag, vorher | nachher | alle 50, vorher | nachher |
|---|---:|---:|---:|---:|
| richtige Seite unter den ersten drei | 25 | **38** | 31 | **49** |
| … davon ganz oben, also sofort angezeigt | 7 | **35** | 11 | **45** |
| ohne Treffer | 4 | **0** | 8 | **0** |

Eine Suche dauert im Median 2,6 Millisekunden, höchstens 13. Den Index baut das
Fenster beim ersten Suchwort, nicht beim Öffnen (rund 100 Millisekunden).

## Die Suchen

| Nr. | Suche | vorher: Rang / Treffer | nachher: Rang / Treffer | Erste Seite nachher | Fundstelle |
|---:|---|---:|---:|---|---|
| 1 | Loch | 2 / 17 | 1 / 15 | Ein Loch bohren | Seitenanfang |
| 2 | Bohrung | 2 / 30 | 1 / 30 | Ein Loch bohren | *Bohrung* |
| 3 | Gewinde | 1 / 7 | 1 / 18 | Bausteine (Referenz) | *Gewinde* |
| 4 | Gehäuse | 3 / 3 | 1 / 6 | Formgebung (Referenz) | *Aushöhlen* |
| 5 | Deckel | 7 / 8 | 1 / 10 | Bausteine (Referenz) | *Deckel* |
| 6 | drehen | 3 / 13 | 1 / 22 | Bewegen und Färben | *drehen* |
| 7 | verschieben | 3 / 9 | 1 / 20 | Bewegen und Färben | *verschieben* |
| 8 | spiegeln | 4 / 5 | 1 / 7 | Transformation (Referenz) | *Spiegeln* |
| 9 | Maß ändern | 1 / 1 | 2 / 25 | Parameter und Ausdrücke | *Maß* |
| 10 | größer machen | — / 0 | 1 / 19 | Transformation (Referenz) | *Skalieren* |
| 11 | skalieren | 1 / 4 | 1 / 5 | Transformation (Referenz) | *Skalieren* |
| 12 | rückgängig | 1 / 7 | 1 / 7 | Der Verlauf | *Rückgängig* |
| 13 | Slicer | 2 / 20 | 1 / 24 | Drucken | *Slicer* |
| 14 | exportieren | 4 / 9 | 1 / 10 | Auf das Bett und hinaus | *exportieren* |
| 15 | zu groß | 1 / 2 | 1 / 12 | Auf das Bett und hinaus | *Zu groß* |
| 16 | teilen | 4 / 18 | 1 / 44 | Teilen und Anpassen (Referenz) | Seitenanfang |
| 17 | Text | 4 / 14 | 1 / 11 | Beschriften | *Text* |
| 18 | Schrift | 4 / 7 | 1 / 42 | Beschriften | *Schrift* |
| 19 | Rundung | 3 / 11 | 1 / 33 | Formgebung (Referenz) | *Verrunden* |
| 20 | abrunden | — / 0 | 1 / 5 | Formgebung (Referenz) | *Verrunden* |
| 21 | Fase | 2 / 10 | 1 / 10 | Formgebung (Referenz) | *Fase* |
| 22 | Mutter | 2 / 7 | 1 / 7 | Die Bausteine | *Mutter* |
| 23 | Schraube | 3 / 10 | 1 / 17 | Bausteine (Referenz) | *Schraubenloch mit Senkung* |
| 24 | Magnet | 3 / 7 | 1 / 7 | Bausteine (Referenz) | *Magnet* |
| 25 | reparieren | 1 / 8 | 1 / 9 | Die ersten fünfzehn Minuten | *Reparieren* |
| 26 | Loch schließen | — / 0 | 1 / 7 | Merkmale (Referenz) | *Bohrung verschließen* |
| 27 | hohl | 4 / 8 | 1 / 9 | Formgebung (Referenz) | *Aushöhlen* |
| 28 | Wandstärke | 3 / 14 | 1 / 15 | Hinsehen, bevor gedruckt wird | *Wandstärke* |
| 29 | Stütze | 2 / 9 | 2 / 21 | Transformation (Referenz) | *Druckoptimal ausrichten* |
| 30 | Überhang | 2 / 10 | 1 / 12 | Hinsehen, bevor gedruckt wird | *Überhang* |
| 31 | Farbe | 3 / 12 | 1 / 12 | Filament (Referenz) | *Filament zuweisen* |
| 32 | zweifarbig | — / 0 | 1 / 3 | Beschriften | *Zweifarbendruck* |
| 33 | Skizze | 3 / 8 | 1 / 8 | Skizze (Referenz) | Seitenanfang |
| 34 | zeichnen | 5 / 8 | 1 / 28 | Zeichnen | Seitenanfang |
| 35 | Kreis | 1 / 8 | 2 / 9 | Transformation (Referenz) | *Kreis* |
| 36 | Passung | 2 / 17 | 1 / 33 | Material, Toleranzen, Passungen | *Passung* |
| 37 | Spiel | 5 / 14 | 1 / 19 | Material, Toleranzen, Passungen | *Spiel* |
| 38 | Toleranz | 2 / 12 | 1 / 13 | Material, Toleranzen, Passungen | *Toleranz* |
| 39 | Löcher ² | 1 / 12 | 2 / 12 | Wonach Solidon urteilt (Referenz) | *Löcher* |
| 40 | gravieren ² | — / 0 | 1 / 3 | Beschriftung (Referenz) | *Text aufbringen* |
| 41 | Logo ² | — / 0 | 1 / 2 | Oberfläche (Referenz) | *Relief auflegen* |
| 42 | Zoll ² | — / 0 | 1 / 4 | Import (Referenz) | *Modell einfügen* |
| 43 | Scharnier ² | 2 / 4 | 1 / 4 | Die Bausteine | *Scharnier* |
| 44 | Clip ² | 1 / 4 | 1 / 3 | Bausteine (Referenz) | *Clip* |
| 45 | Strg+Z ² | 1 / 10 | 4 / 10 | Zeichnen | *Strg+Z* |
| 46 | aufs Bett ² | — / 0 | 1 / 3 | Transformation (Referenz) | *Bett* |
| 47 | glätten ² | 1 / 3 | 1 / 3 | Netz glätten und vereinfachen (Referenz) | Seitenanfang |
| 48 | kopieren ² | — / 2 | 1 / 10 | Szene (Referenz) | *Objekt duplizieren* |
| 49 | messen ² | 6 / 25 | 1 / 31 | Hinsehen, bevor gedruckt wird | *Messen* |
| 50 | Bambu ² | 3 / 6 | 1 / 6 | Material, Drucker, Normteile (Referenz) | *Bambu* |

„Stütze“ führt zuerst auf *Druckoptimal ausrichten*: In der Palette meint
„Stützen“ genau diese Operation, und ihre Beschreibung sagt, dass sie Stützen
spart. Die Erklärseite *Drucken* folgt auf Rang zwei. „Strg+Z“ (Rang 4) ist die
einzige Suche außerhalb der ersten drei: Das Kürzel steht auf fast jeder
geschriebenen Seite, und eine Fensteraktion wie *Rückgängig* kennt der Kern
nicht als Operation.

## Was die Messung entschieden hat

Jede dieser Einstellungen ist am Satz der 50 Suchen gemessen, nicht gesetzt.

- **Titel vor Kurzfassung vor Stichwort vor Fließtext.** Überschriften und
  fett gesetzte Stichwörter bilden ein eigenes Feld: Die Referenz setzt jede
  Operation als Überschrift, die geschriebenen Seiten beginnen ihre Absätze
  mit dem Stichwort. Ohne dieses Feld stand bei „spiegeln“ das
  Skizzenwerkzeug vor *Spiegeln*, bei „Deckel“ ein Beispielsatz vor *Deckel
  erzeugen*.
- **Das ganze Wort zählt die Hälfte mehr als ein Wortanfang.** Mit einem
  Viertel landete „hohl“ bei der *Hohlkehle*, mit dem Ganzen fiel „Stütze“ auf
  Rang drei.
- **Faltung, Trefferstärke und Kundenwörter der Befehlspalette.** Eine eigene
  Wortliste des Handbuchs (zuletzt 17 Einträge, 38 von 38 unter den ersten
  drei) wurde gebaut, gemessen und wieder entfernt: Sie hätte dieselbe Frage
  beantwortet wie `registry.search.CUSTOMER_WORDS` und wäre
  auseinandergelaufen. Die
  Palette hatte „Gehäuse“ und „Zoll“ nicht; beide stehen jetzt dort, in allen
  sechs Sprachen, und die Palette findet sie mit.
- **Kein Vorsprung für Kundenwörter.** Mit zehn Punkten Vorsprung überholte
  *Druckoptimal ausrichten* bei „Überhang“ die Erklärseite. Ohne Vorsprung
  zählt eine Seite mit der besseren von zwei Antworten: dem, was getippt
  wurde, und dem Titel der Operation, die das Kundenwort meint.
- **Je Wort verglichen.** Ein Titel aus zwei Wörtern sammelte sonst doppelt:
  Bei „Loch“ schlug die Anleitung bei *Bohrung setzen* auf statt oben.
- **Der Titel einer Operation zählt nur als Wortfolge.** Sonst traf *Insert
  model* (englisch, über „inch“) jede Seite mit „model“ im Titel.
- **Gemeinsame Faltung heißt auch gemeinsame Grenze.** Die Palette schreibt
  „ö“ als „oe“, damit „aushoehlen“ *Aushöhlen* findet. „Löcher“ und „Loch“
  teilen damit keinen Wortanfang mehr, und „Löcher“ zeigt die Anleitung auf
  Rang zwei statt eins. Das ist so entschieden: Dieselbe Eingabe soll in
  Palette und Handbuch dasselbe finden.

## Gegenprobe

25 deutsche Suchen außerhalb des Satzes („vergrößern“, „Ansicht drehen“,
„Druckzeit“, „STL“, „Gewinde M3“, „Stützen entfernen“, „Lizenz“ …) und je
Sprache zehn bis sechzehn Wörter („round edges“, „enclosure“, „inch“,
„redondear“, „boîtier“, „foro“, „polegada“ …) wurden von Hand durchgesehen. Alle
zeigen eine plausible erste Seite. Eine Anfrage wie „aumentar temperatura“
holt nicht mehr *Skalieren* nach vorn: Ein Kundenwort zählt nur, wenn die
Suche genau diese Wendung ist.
