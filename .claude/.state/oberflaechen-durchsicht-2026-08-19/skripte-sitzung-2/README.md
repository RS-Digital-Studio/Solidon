# Die Messskripte der zweiten Sitzung

Jede Zahl in `FORTSETZUNG-SITZUNG-2.md` und in den Commit-Meldungen kommt aus
einem dieser Skripte. Sie liegen hier, damit die Messung wiederholbar ist —
eine Zahl, die niemand nachrechnen kann, ist eine Behauptung.

Alle laufen über die Umgebung des Projekts:

```
.venv\Scripts\python.exe -X utf8 .claude\.state\oberflaechen-durchsicht-2026-08-19\skripte-sitzung-2\<datei>
```

**Zwei Regeln, beide teuer gelernt:**

* **Aufnahmen und Schriftmaße brauchen die echte Plattform.** Offscreen hat Qt
  auf dieser Maschine null Schriftfamilien; jede Breite, die dort gemessen wird,
  gehört einer anderen Schrift als der gezeigten. Am Objektbaum sagte die
  Offscreen-Messung „die Maßspalte ist überall gekürzt" (168 Bedarf, 102 Platz),
  die echte Plattform „alles da" (83 von 89). Die Skripte hier setzen
  `QT_QPA_PLATFORM` deshalb **nicht**.
* **`load_operations()` vor `build_application()`**, sonst baut die Menüleiste
  aus einem leeren Register, und `QScreen.grabWindow(window.winId())` statt
  `QWidget.grab`, sonst ist der Viewport im Bild schwarz.

| Skript | Was es misst |
|---|---|
| `links.py` | jeden Verweis und jede Sprungmarke aller 29 Webseiten gegen den Dateibestand — die Wurzel `/` gehört der Seite, nicht dem Laufwerk |
| `pruef_druckdialog.py` | den Druckdialog: Gruppen, Reiter, Feldbreiten, gesperrte Felder ohne Grund (726 Bildpunkte je Feld) |
| `messe_baum.py` | den Objektbaum im laufenden Fenster: Spaltenbreiten gegen den Bedarf der Schrift, mit der wirklich gezeichnet wird |
| `messe_leisten.py` | alle acht Werkzeugkarten nebeneinander — Höhe, Leistenhöhe, unsichtbare Beschriftungen (Trennen 241, die anderen 81–112) |
| `messe_trennen.py`, `messe_split2.py` | die Trennleiste im Einzelnen: Breite null für den Satz, 160 Punkte Höhe dafür |
| `shoot_viewport.py` | die Ansicht mit Projekt, Auswahl und in beiden Themen |
| `shoot_shadow.py` | zwei Aufnahmen desselben Bildes, mit und ohne die Schattenaktoren |
| `sweep_shadow.py` | fünf Schattenrichtungen, je ein Bildpaar, und die Zahl der abgedunkelten Punkte (4 · 1457 · 2988 · 4889 · 5053) |
| `shoot_extremes.py` | leere Szene, 2-mm-Teil, 400-mm-Teil — der Fall, in dem die Kamera im Körper stand |
| `shoot_split.py` | die Werkzeugkarte des Trennwerkzeugs als Bild, vorher und nachher |
| `skip.py` | hat den Sprung an den Inhalt in 23 von Hand gepflegte Seiten eingesetzt (einmalig, hier als Beleg, was mechanisch geändert wurde) |
| `regen_manual.py` | schreibt nur die sechs Handbuchseiten neu, ohne Abbildungen und PDF |
| `roadmap_fix.py`, `roadmap_body.py` | haben Register und Abschnitt der ROADMAP nachgezogen (einmalig, siehe oben) |

Die Bilder dazu liegen in `../aufnahmen-sitzung-2/`. Vier der Aufnahmen aus dem
Richtungsvergleich waren byteweise identisch — es ist immer dasselbe Bild ohne
Schatten; geblieben ist eine davon (`sweep-ohne-schatten.png`).
