---
paths:
  - "app/ui/**/*.py"
---

# Regeln für die Oberfläche

PySide6. Die Oberfläche darf `core` benutzen, nie umgekehrt. Sie rechnet keine
Geometrie und ändert keine — sie ruft Ops auf.

## Das Versprechen

**Nichts ist endgültig.** Jede Handlung ist eine Op, jede Op rücknehmbar, jeder
Wert nachträglich änderbar. Praktisch heißt das: **keine Bestätigungsdialoge
vor rücknehmbaren Handlungen**, kein „Möchten Sie wirklich", keine Sackgassen
(Regel 19).

## Texte

Keine feste Zeichenkette in der Oberfläche — alles über `tr()`, deutsch und
englisch. Ein Fehler endet nie mit „fehlgeschlagen": erst was nicht ging, dann
warum, dann was jetzt möglich ist, als anklickbare Handlungen (§2.7). Kein
Stapelabzug im Nutzerdialog.

## Fenster

Höchstens drei sichtbare Zonen: links Objektbaum, Parameter und Verlauf als
einklappbare Abschnitte; Mitte der Viewport; rechts **entweder** Chat **oder**
Prüfbericht, umschaltbar und ganz ausblendbar. Die Umschaltung springt zum
Bericht, wenn eine Warnung entsteht.

Solange ein Beispielprojekt offen ist, hat die rechte Spalte einen dritten
Reiter: die Tour (`app/ui/tour.py`, Schritte in `app/core/tour.py`). Sie
erkennt getane Schritte über `projectChanged` am Dokument und Verlauf, „Weiter"
schaltet jeden Schritt auch ohne Erkennung — Angebot, keine Sperre. Der
Warnungssprung zum Bericht lässt der aktiven Tour den Reiter; jedes andere
Projekt räumt ihn weg. Die Erkennungswerte müssen zu `tools/make_examples.py`
passen — driftet beides, wird `tests/test_tour.py` rot.

**Keine Betriebsarten.** Kein Umschalten zwischen „Bearbeiten" und
„Konstruieren" — es gibt einen Zustand, und der ist die Szene.

## Gestufte Tiefe

Jeder Dialog hat eine kurze Vorderseite und einen aufklappbaren Bereich
„Weitere Einstellungen". Vorn die zwei bis drei Werte, die man ändert; hinten
Toleranzen, Auflösungen, Rückfallverhalten. Die Vorgaben kommen aus dem
Drucker- und Materialprofil. **Eine gute Vorgabe ist mehr wert als eine gute
Einstellmöglichkeit.**

## Die Oberfläche wächst nicht mit

Vielseitigkeit gehört in die Tiefe, nicht an die Oberfläche (§2). Die Zahlen
dazu stehen in `tests/test_interface_limits.py` und werden rot, wenn sie
gerissen werden:

| Grenze | Wert |
|---|---|
| Menüs in der Leiste | ≤ 9 |
| Zeilen in einem Menü (ein Untermenü zählt als eine) | ≤ 12 |
| Umschalter in der Werkzeugzeile | ≤ 8 |
| Felder auf der Vorderseite eines Operationsdialogs | ≤ 8 |
| Menüeinträge je Operation | genau 1 |

Wer eine Zahl erhöhen will, tut das mit Absicht und begründet es im Commit.

**Eine Operation je Handlung, nicht je Variante.** Neun Texturmuster sind ein
Menüeintrag mit einem Auswahlparameter, nicht neun Einträge. Rechteck aus zwei
Ecken oder aus Mitte und Maß ist dasselbe Werkzeug mit einem Umschalter.

**Jede neue Funktion nennt ihren Hauptweg** (§2.2), bevor sie einen Platz
bekommt:

| Weg | Ort an der Oberfläche |
|---|---|
| Weg 1 — fremdes Modell anpassen | Kontextmenü am Merkmal, Vorschlag im Prüfbericht |
| Weg 2 — neu konstruieren | Werkzeugzeile, Menü *Erzeugen* / *Ändern* |
| Weg 3 — generieren | Chat und Generierungsdialog |
| keiner der drei | Untermenü und Befehlspalette, sonst nichts |

**Was zur Auswahl passt, steht vorn.** `applies_to` sortiert nicht nur das
Kontextmenü, sondern auch die Befehlspalette
(`palette_entries(for_feature=...)`). Es ist eine Reihenfolge, keine Auswahl —
eine Palette, die aussortiert, wäre eine Betriebsart mit anderem Namen.

## Wartezeit

| Dauer | Anzeige |
|---|---|
| unter 0,2 s | nichts |
| bis 2 s | Mauszeiger und Statusleiste |
| darüber | Fortschritt mit **Abbrechen**, Oberfläche bedienbar |
| über 10 s | zusätzlich eine Schätzung, wenn möglich |

Die letzte gültige Darstellung bleibt sichtbar — nie ein leerer Viewport, nie
ein blockierendes Fenster. Lange Rechnungen laufen nicht im Qt-Hauptthread.

### Wer einen Arbeiter startet, hält ihn fest

Ein `QThread` bekommt hier keinen Qt-Elternteil; ihn hält allein die
Python-Referenz. Fällt sie weg, während der Thread noch läuft, zerstört der
Speicherbereiniger das C++-Objekt unter ihm — eine Zugriffsverletzung ohne
Zeile, irgendwann später und selten reproduzierbar.

**Nie als Lambda, das blind `None` schreibt:**

```python
worker.finished.connect(lambda: setattr(self, "_worker", None))  # falsch
```

Das geht zweimal schief. `finished` kommt, während Qt den Thread noch abräumt —
zu früh zum Loslassen. Und es trifft das Feld, nicht den Arbeiter: wird ein
Vorgänger fertig, nachdem sein Nachfolger im Feld steht, löscht er dessen
Referenz.

**Richtig** ist ein benannter Slot, der seinen *eigenen* Arbeiter erkennt und
ihn danach der gemeinsamen Halteleine übergibt:

```python
worker.finished.connect(lambda done=worker: self._worker_done(done))


def _worker_done(self, worker: Any) -> None:
    if self._worker is worker:
        self._worker = None
    self._hold_until_done(worker)
```

`_hold_until_done` legt ihn in `_retired` und lässt ihn erst los, wenn
`isRunning()` nein sagt. Ein ersetzter Arbeiter geht denselben Weg über
`_retire`. `wait_for_workers` wartet am Ende auf alle — auch auf die in
`_retired`, sonst überlebt einer sein Fenster und nimmt den Prozess mit.

## Barrierefreiheit

- **Keine Bedeutung allein über Farbe** (Regel 18). Immer eine zweite
  Kodierung: Muster, Schraffur, Symbol, Beschriftung.
- Differenzansicht in Blau/Orange als Vorgabe, nicht Rot/Grün.
- Analysekarten mit wahrnehmungsgleicher Palette (Viridis-Art), kein
  Regenbogen — der erzeugt Kanten, wo keine sind.
- Alles über die Befehlspalette erreichbar; Kürzel stehen daneben, so lernt man
  sie nebenbei. Undo und Redo gelten überall, auch im Chat.
- HiDPI, skalierbare Schrift, Kontrast in hellem und dunklem Thema,
  Anzeigeeinheit zwischen Millimeter und Zoll umschaltbar.

## Tests

Oberflächentests laufen offscreen (`QT_QPA_PLATFORM=offscreen`, von
`tests/conftest.py` gesetzt). Eine neue Ansicht ohne Test in `tests/test_ui.py`
oder einer der spezielleren Dateien ist unfertig.

## Die Ansicht

Umgebungsverdeckung und Kontaktschatten weichen, solange eine Analysekarte
läuft: beide dunkeln nach, und die Karte färbt nach Zahlen — der abgelesene
Wert wäre ein anderer als der gemeldete. Beide hängen deshalb an einer
Eigenschaft (`ambient_occlusion`, `contact_shadows`) und nicht am Zustand des
Plotters: offscreen gibt es keinen, und ein Test, der sich dort überspringt,
prüft nie etwas.

Der Kontaktschatten ist **selbst projiziert**, nicht `enable_shadows`: VTKs
Schattenwurf verschattet ganze Seitenflächen schwarz und lässt die Ränder der
Platte auslaufen. Geworfen wird entlang einer festen Lichtrichtung — senkrecht
projiziert liegt der Schatten unter dem Körper und ist von ihm verdeckt.

Zahlen an Bildern werden **angesehen, nicht nur gerechnet**. Der Radius der
Umgebungsverdeckung stand mit plausibler Begründung auf dem schwächsten Wert
seiner Messreihe; der doppelte ViewCube fiel erst im neu aufgenommenen
Handbuchbild auf.
