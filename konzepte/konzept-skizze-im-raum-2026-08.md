# Konzept — Die Skizze in den Raum

Stand 24.08.2026. Anlass ist ein Befund von Robert an der laufenden Anwendung:

> „schau dir das 2d zeichnen an, ich finde es sehr umständlich und wofür ist es
> genau? am viewport ändert sich nichts, bei draufsicht, seitenansicht usw
> sieht man auch keinen unterschied"

Drei Beobachtungen, ein gemeinsamer Grund. Dieses Dokument belegt den
Ist-Zustand, benennt den Grund, trifft die Entscheidungen und schneidet die
Arbeit in Pakete.

**Verhältnis zu den bestehenden Unterlagen.** `konzepte/konzept-bedienung.md`
Teil 4 hat den Skizzeneditor am 13.08.2026 gegen Fusion gemessen und neun
Lücken gefunden; alle neun sind abgearbeitet (`ROADMAP.md`, „Skizze
bedienerisch fertig"). Jene Durchsicht verglich die **Ausstattung des
Zeichenblattes**. Dieses Dokument vergleicht das **Verhältnis von Blatt und
Raum** — eine Frage, die dort nicht gestellt wurde. Es widerspricht ihr nicht,
es liegt darunter.

---

## §1 Ist-Zustand, belegt

Jede Aussage hier steht mit ihrer Stelle. Was nicht belegt ist, steht nicht
hier.

### 1.1 Was eine Skizze ist

Bauplan §30.1: Eine Skizze ist **kein eigenes Dokument**, sondern der
Parameterwert der Operation, die sie verbraucht — `sketch_extrude`,
`sketch_pocket`, `sketch_revolve`, `sketch_sweep`
(`app/core/sketch/ops.py:272` ff.). Bearbeiten ist `change_params` auf dem
Schritt im Verlauf, dieselbe Regel wie für jede andere Zahl (§15).

Der Zweck dahinter ist eine Produktentscheidung, und §30.1 sagt sie
ausdrücklich: *so wenig Fremdprogramme wie möglich.* Das fremde CAD vor dem
Import ist der größte verbliebene Anlass, Solidon zu verlassen.

### 1.2 Wo eine Skizze liegt

Vier Möglichkeiten. Drei feste Ebenen — `plane:xy`, `plane:xz`, `plane:yz` —
und `feature:<id>`, eine erkannte planare Fläche eines Körpers. Der Modulkopf
von `app/core/sketch/planes.py` bewertet sie selbst:

> „Sie ist die interessantere, denn sie ist der Weg, auf einem vorhandenen
> Teil weiterzubauen, statt daneben."

Der Rahmen wird bei jeder Auswertung neu aus dem Körper gerechnet, nicht
gespeichert; in der Projektdatei steht nur die Feature-ID. Das ist sauber
gelöst und hängt an den stabilen IDs aus §21.

**Diese Fähigkeit ist vollständig vorhanden und wird nicht angefasst.**

### 1.3 Der Bruch: ein Versprechen, das nur ein Weg einlöst

`sketch_pocket` (`app/core/sketch/ops.py:370`) trägt `consumes=1`,
`applies_to=("face",)` und im `doc` den Satz:

> „Ein Klick auf eine Fläche trägt den Ort vorab ein."

Über den **Operationsdialog** wird das eingelöst: `OpDialog.take_feature`
(`app/ui/op_dialog.py:1028`) trägt ein angeklicktes Merkmal in jeden Parameter
mit `kind="feature"` ein, und `MainWindow._on_feature_picked`
(`app/ui/main_window.py:5085`) reicht den Klick dorthin weiter.

Über den **Skizzenmodus** wird es nicht eingelöst. Dort ist die Ebene ein
Klappfeld (`app/ui/sketch_editor.py:2516`), gefüllt mit Zeilen der Form
„Fläche an Gehäuse — 2 400 mm², oben" (`app/ui/main_window.py:3813`). Es gibt
**keinen Codepfad**, der eine im Viewport angeklickte Fläche als Skizzenebene
übernimmt.

Der Grund dafür steht im nächsten Abschnitt und ist derselbe wie für alles
andere.

### 1.4 Der Grund: der Viewport ist weg

`MainWindow.start_sketch` (`app/ui/main_window.py:3945`) tauscht den
3D-Viewport aus dem Widget-Stapel heraus:

```python
self.middle_stack.addWidget(panel)
switch(self.middle_stack, panel)
```

Daraus folgt alles, was Robert beobachtet hat:

| Beobachtung | Ursache |
|---|---|
| „am Viewport ändert sich nichts" | Es gibt keinen Viewport mehr — er liegt unter dem Panel |
| „bei Draufsicht, Seitenansicht kein Unterschied" | Die Ansichtsaktionen sind ausgegraut (`app/ui/main_window.py:824`), und die Ziffern 1–3 belegt der Ebenenwechsel |
| „umständlich" | Die Ebenenwahl ist **reiner Text** — siehe unten |

`SketchCanvas.set_plane` (`app/ui/sketch_editor.py:670`) sagt es selbst:

> „Sie entscheidet, wohin extrudiert wird — nicht, wie gezeichnet wird … Das
> steht in der Beschriftung, nicht in einer gedrehten Ansicht."

XY und die Deckfläche eines Gehäuses sehen auf dem Schirm identisch aus. Es
gibt keine räumliche Rückmeldung darüber, wo man gerade zeichnet.

### 1.5 Warum der Stapeltausch gewählt wurde

Kein Versehen. `app/ui/main_window.py:1104` begründet ihn:

> „ein Modus, der die Ansicht ersetzt, ist ehrlicher als ein Qt-Widget über
> einem OpenGL-Fenster: was man dort sieht, gehört zwei Zeichenwegen, und
> einer von beiden hat immer gerade nicht neu gezeichnet."

Dagegen steht der Modulkopf von `app/ui/overlay.py`, der Kind-Widgets über dem
Plotter als tragfähig **misst** — Knopf, Eingabefeld und `childAt` an derselben
Stelle. Beide haben für ihren Fall recht: Die Overlay-Karten stehen fest im
Bild, eine Skizze muss sich mit der Kamera mitbewegen. §3 löst das auf.

### 1.6 Was bereits vorhanden ist

Der Umbau ist billiger, als er klingt, weil fast jedes Teilstück ein Muster im
Haus hat:

| Gebraucht | Vorhanden |
|---|---|
| Kamera auf eine Ebene richten | `Viewport.view_from` setzt `camera_position` (`viewport.py:4456`); `planes.frame_of` liefert Ursprung und Achsen |
| Modell abblenden | Anzeigemodus `transparent`, Deckkraft 0,45 (`viewport.py:92`) |
| Bildschirmpunkt → Weltpunkt | `Viewport._world_at` über `vtkCellPicker` (`viewport.py:4563`) |
| Ein weiterer Zeigemodus | `_on_picked` verzweigt bereits nach `_splitting`, `_boning`, `_sculpting`, `_painting` (`viewport.py:3090`) |
| Skizze auf einer Fläche | `feature:<id>` samt Rahmenrechnung — fertig (§1.2) |
| Koordinatenrechnung des Canvas | Genau zwei Methoden: `_to_screen`, `_to_world` (`sketch_editor.py:1105`) |

---

## §2 Der Maßstab draußen

### 2.1 SindriCAD, Stand 24.08.2026

Nachgeholt an diesem Tag; die Vorgängerzahlen stehen in
`konzepte/konzept-sindricad.md`.

| | 04.08. | 19.08. | 24.08. |
|---|---|---|---|
| Version | 0.1.81 | 0.1.171 | **0.1.179** |
| Sterne | 20 | 141 | **144** |
| Offene Fehlerberichte | — | 2 | **5** |
| Letzter Push | — | 19.08. | **24.08., 01:42 UTC** |

Wochencommits weiterhin 51, 32, 41, 35, 87, 66, 39 — unverändert Ein-Personen-
Tempo, ungebrochen.

**Der Satz, auf den es ankommt**, steht im Modulkopf von
`src/sketch/sketchMode.ts`:

> „enter on a plane (camera squares to it, model dims, grid appears)"

Also: derselbe 3D-Viewport, die Kamera dreht sich auf die Ebene, das Modell
bleibt stehen und wird abgeblendet, ein Raster kommt dazu. Die Kamerasperre
ist über eine Palettenoption „Look At" lösbar.

Dazu aus dem README:

> „Press/Pull dispatches on what you click: a body face is pushed or pulled
> along its normal, a sketch profile goes to Extrude, an edge goes to Fillet.
> One key for the three things you reach for most."

Ein Werkzeug, das aus dem Angeklickten schließt, was gemeint ist.

**Ein Vorsprung für Solidon.** `src/sketch/plane.ts` trägt den Kommentar
„base planes now, faces later". Unsere Flächenebenen sind fertig gerechnet
(§1.2), ihre offenbar nicht. Das README behauptet allerdings Skizzenebenen aus
importierten Teilen — der Code widerspricht dem an dieser Stelle. **Nicht als
gesichert weitergeben.**

### 2.2 Woran es wirklich hängt

Der Vergleich mit Fusion in `konzept-bedienung.md` Teil 4 zählte Werkzeuge.
Der Unterschied, der Robert aufgefallen ist, steht in keiner Zeile jener
Tabelle, weil die Tabelle die falsche Achse hatte:

| | Fusion / SindriCAD / Onshape | Solidon heute |
|---|---|---|
| Skizzenmodus | Kamera schwenkt auf die Ebene | Viewport wird ersetzt |
| Modell während des Zeichnens | sichtbar, abgeblendet | unsichtbar |
| Ebenenwahl | Fläche im Bild anklicken | Klappfeld mit Textzeilen |
| Wo die Skizze liegt | im Raum, sichtbar | auf einem Blatt ohne Ort |
| Drehen während des Zeichnens | jederzeit | nicht möglich |

Alle fünf Zeilen haben dieselbe Ursache: §1.4.

---

## §3 Entscheidungen

### A — Die Skizze liegt im Viewport, nicht an seiner Stelle

Der Stapeltausch entfällt. `start_sketch` schwenkt die Kamera auf die
Skizzenebene, blendet das Modell ab und legt ein Raster auf die Ebene. Der
Viewport bleibt der Viewport.

*Begründung:* §1.4 — es ist die gemeinsame Ursache aller drei Beobachtungen.

### B — Gelöste Geometrie ist Weltgeometrie, nicht Bildschirmgeometrie

Alles, was auf der Skizzenebene liegt — Elemente, Punkte, Fangkreuz,
Vorschaulinie, Bedingungssymbole —, geht als VTK-Netz in die Szene. Ein
Zeichenweg, kein Versatz, korrekt aus jeder Blickrichtung.

*Begründung:* Löst den Einwand aus §1.5 an der Wurzel statt ihn zu umgehen.
Regel 2 deckt es: „Was der Editor zeigt, während er offen ist, ist eine
Vorschau und kein Dokumentzustand."

**Diese Entscheidung steht und fällt mit G.** Ohne sie wäre die Skizze in der
Suite unprüfbar — siehe dort.

### G — Rechnung und Darstellung sind getrennt, sonst ist nichts geprüft

**Offscreen gibt es keinen Plotter.** `Viewport._available()`
(`app/ui/viewport.py:396`) gibt `False` zurück, sobald `QT_QPA_PLATFORM` auf
`offscreen`, `minimal` oder `vnc` steht, und `tests/conftest.py` setzt
`offscreen` für die gesamte Suite. Gemessen am 24.08.2026:

```
_available(): False
plotter: None
```

Jede Methode mit `if self.plotter is None: return` — und das sind über zwanzig
— ist in der Suite ein Rückgabebefehl. Kamerastellung, Abblendung und Aktoren
sind dort **grundsätzlich ungeprüft**. Ein Test, der `_actors` vor und nach
einem Schritt vergleicht, vergleicht zwei leere Wörterbücher und ist grün ohne
Aussage. (Befund von `formwerk-be`, 24.08.2026, an der eigenen Diagnose
erlebt.)

Der heutige Editor ist davon nicht betroffen, weil er ein reines `QWidget` mit
`QPainter` ist — **das** ist der Grund, aus dem er die Auflage „offscreen
testbar" aus §30.1 erfüllt. Entscheidung B nimmt ihm diese Eigenschaft. Sie
ist deshalb nur zulässig, wenn alles Prüfbare vorher aus VTK heraus ist:

- **Kameravorgabe** ist eine reine Funktion `camera_for_plane(frame, …)` →
  Position, Blickpunkt, Oben. Der Viewport *setzt* sie nur.
- **Ebenenkoordinaten** — Weltpunkt ↔ `(u, v)` — sind reine Funktionen über
  dem `PlaneFrame`.
- **Was gezeichnet wird** ist eine reine Funktion
  `sketch_geometry(solved, frame)` → Punkt- und Linienfelder. Der Viewport
  reicht sie an VTK weiter, ohne sie zu verändern.
- **Die Zeigerposition ist eine einspeisbare Größe.** Die Interaktionslogik
  bekommt Ebenenkoordinaten herein; ob sie aus `_world_at` stammen oder aus
  einem Test, weiß sie nicht. Damit bleiben die rund 3 300 Zeilen
  Zeichenlogik offscreen prüfbar.

*Begründung:* `viewport.py` trennt bereits so — `shadow_points`,
`outline_of`, `clip_polygon`, `bed_outline`, `gizmo_labels`, `volume_edges`
stehen als freie Funktionen im Modulkopf und sind einzeln getestet, obwohl der
Plotter darunter fehlt. Dieses Paket erfindet kein Muster, es hält sich an
eins.

**Was ungeprüft bleibt, wird benannt, nicht behauptet:** dass VTK das
Berechnete auch anzeigt. Dafür gibt es einen Prüfstand mit echtem Fenster und
`QTimer.singleShot`-Kette (nicht Warteschleife — die hängt dort), und der
zugehörige Schritt steht als manueller Schritt im Paket, nicht als grüner
Test. `.claude/rules/oberflaeche.md`, Abschnitt „Was nur das Bild zeigt".

### C — Das Raster ist die Pickfläche

`_world_at` benutzt einen `vtkCellPicker` und trifft damit nur Geometrie. Das
Raster auf der Skizzenebene **ist** Geometrie. Damit liefert ein Klick oder
eine Mausbewegung über der Ebene einen Weltpunkt, auch wo kein Körper steht —
ohne eine zweite Rechenart und ohne Änderung an `_world_at`.

*Begründung:* Der Mauszeiger wird dadurch ein Ebenenpunkt wie jeder andere.
Es gibt kein zweites Bezugssystem, das mit dem ersten synchron gehalten werden
müsste. Diese Entscheidung ist der Grund, aus dem D möglich ist.

**Unabhängig bestätigt.** `formwerk-d1` hat am 24.08.2026 am Referenzkorpus
gemessen: Ein Sichtstrahl senkrecht von oben in eine Durchgangsbohrung trifft
**kein einziges Dreieck** — die Zylinderwand liegt parallel zum Strahl, und
`_world_at` gibt `None`. Ohne Rasterebene hätte die Zeichenfläche also
ausgerechnet dort Löcher, wo der Körper welche hat: Über einer Bohrung ließe
sich kein Punkt setzen. Mit ihr trifft der Picker immer.

### D — Drehen bleibt jederzeit erlaubt

Keine Kamerasperre als Bedingung für die Korrektheit. Die Kamera steht beim
Eintritt senkrecht auf der Ebene, weil das die bequeme Ausgangslage ist; wer
dreht, dreht, und die Skizze dreht mit.

*Begründung:* Ein erster Entwurf machte die Interaktion von einer gesperrten
Kamera abhängig. `formwerk-20` hat dagegengehalten, dass Drehen während des
Zeichnens in jedem CAD ein normaler Handgriff ist und verschwindende Werkzeuge
als Aussetzer gelesen werden — bei einem Auftrag, der mit „umständlich"
beginnt, das falsche Geschäft. Entscheidung C macht die Sperre überflüssig.

**Grenzfall, benannt:** Bei streifendem Blick trifft der Picker die
Rasterebene kaum noch. Das ist kein Sperrgrund, sondern eine Meldung — die
Statuszeile sagt es, und ein Griff stellt die Ansicht zurück auf die Ebene.

### E — Fläche anklicken beginnt die Skizze dort

Der Weg, den `sketch_pocket` seit je verspricht (§1.3): Fläche im Viewport
anklicken, „Skizze auf dieser Fläche", die Ebene **ist** gewählt. Das Klappfeld
bleibt als zweiter Weg bestehen — für die drei Grundebenen und für die
Tastatur.

*Begründung:* §1.3. Ein Versprechen, das ein Weg hält und der andere nicht,
ist die teuerste Sorte Fund (`ROADMAP.md`, Rangfolge Punkt 2).

### F — Was bildschirmfest bleibt, bleibt Qt

Werkzeugleiste, Bedingungsliste, Statuszeile und das Maßfeld am Zeiger bleiben
Qt-Widgets. Sie hängen an keiner Position im Modell.

*Begründung:* Für sie gilt der gemessene Befund aus `app/ui/overlay.py`, nicht
die Warnung aus `main_window.py:1104` — sie bewegen sich nicht mit der Kamera.

---

## §4 Nicht-Ziele

Ausdrücklich **nicht** Teil dieses Umbaus:

- **Kein neues Datenmodell.** `Sketch`, `SketchConstraint`, der Solver und die
  Serialisierung bleiben unangetastet. Die Skizze bleibt ein Parameterwert
  (§30.1) — es entsteht kein zweiter Dokumentbegriff.
- **Keine neuen Zeichenwerkzeuge und keine neuen Bedingungen.** Die
  Ausstattung ist nach `konzept-bedienung.md` Teil 4 vollständig; dieses
  Dokument ändert, *wo* gezeichnet wird, nicht *womit*.
- **Kein assoziatives Skizzenmuster und kein Text als Kontur.** Beides wurde
  bewusst abgelehnt (`ROADMAP.md`); SindriCAD hat beides, und das ändert hier
  nichts.
- **Kein Ersatz für `push_face`.** Fläche direkt ziehen bleibt ein eigener Weg
  mit Ziehgriff (`main_window.py:4510`). Ob daraus später ein Press/Pull nach
  SindriCAD-Art wird, das aus dem Angeklickten schließt, ist eine eigene
  Entscheidung und steht hier nicht.
- **Keine Live-Vorschau der Extrusion** in diesem Umbau. Sinnvoll, aber
  trennbar — und ein Paket, das ohne die anderen keinen Wert hat.

---

## §5 Leitplanken

- **Additiv, dann umschalten, dann abbauen.** Der neue Weg entsteht neben dem
  Stapeltausch; das Panel bleibt funktionsfähig, bis ein einzelnes,
  benanntes Paket den Schnitt macht. Erst danach fällt toter Code.
- **Ein Commit je Paket, jedes Paket endet grün.** Das Tor ist die geteilte
  Suite plus Leistungstests, `ruff check`, `ruff format --check`, `mypy`.
- **Referenzzahl der Sammelgruppe: 3554 passed, 23 skipped.** Steht dort nach
  einem Paket weniger, sind Tests verloren gegangen, ohne rot zu werden — bei
  Arbeit am Skizzeneditor der wahrscheinlichere Schadensfall als ein roter
  Test. (Datenpunkt von `formwerk-20`, 24.08.2026.)
- **`python tools/check_env.py` vor dem ersten Lauf.** Fehlt `pytest-xdist`,
  antwortet die Sammelgruppe mit `unrecognized arguments: -n` und Exit 4 — und
  das Tor meldet *einen* Fehllauf, während nichts gelaufen ist.
- **Offscreen testbar bleibt Pflicht** (§30.1). Was sich nur mit echter GL
  prüfen lässt, bekommt einen Test auf der Rechenebene und einen benannten
  manuellen Schritt — nicht „ungeprüft".
- **Fremde Gebiete.** `app/ui/main_window.py` gehört `formwerk-be`,
  das Merkmals-Picking im Viewport `formwerk-d1`. Beide sind angefragt; P3
  baut auf dem Ergebnis von `formwerk-d1` auf, nicht daneben.

---

## §6 Pakete

Jedes Paket nennt seine Verifikation zweigeteilt: **grün** ist, was die Suite
offscreen wirklich prüfen kann (Entscheidung G); **Bild** ist, was nur der
Prüfstand mit echtem Fenster zeigt und deshalb als manueller Schritt
protokolliert wird — nicht als Test, der bestünde, weil er nichts tut.

| Nr. | Inhalt | Umfang | Verifikation | Stand |
|---|---|---|---|---|
| P0 | Reine Funktionen ohne VTK: `camera_for_plane`, Weltpunkt ↔ `(u, v)`, `sketch_geometry` (Entscheidung G) | S | **grün:** Achse gegen die Ebenennormale, Hin- und Rückrechnung als Umkehrung, Geometrie einer bekannten Skizze gegen erwartete Zahlen | offen |
| P1 | `Viewport.view_on_plane(frame)` setzt die Vorgabe aus P0; Raster als pickbarer Actor auf der Ebene (Entscheidung C) | S | **grün:** ohne Plotter kehrt beides folgenlos zurück, kein Absturz. **Bild:** Kamera steht senkrecht, Raster liegt in der Ebene, Picken trifft es | offen |
| P2 | Skizzengeometrie in die Szene (Entscheidung B); Zeigerposition wird einspeisbar (G) | L | **grün:** Skizze auf `feature:<id>` liegt in der Ebene der Fläche; eingespeiste Zeigerpunkte erzeugen dieselben Elemente wie heute die Mausereignisse; zweimal zeichnen ergibt identische Punkte | offen |
| P3 | Fläche anklicken → Skizze dort (E). Zeigemodus `_sketching` in `_on_picked`, Kontextmenüeintrag | M | **grün:** ein eingespeister Flächentreffer setzt `sketch.plane` auf `feature:<id>`, das Klappfeld zeigt dieselbe Wahl. **Bild:** Klick auf die Deckfläche beginnt dort | offen |
| P4 | **Der Schnitt.** `start_sketch` schwenkt statt zu tauschen; Modell abgeblendet; Ansichtsaktionen und Ziffern wieder frei (A, D) | L | **grün:** `middle_stack` wechselt die Seite nicht mehr; Ansichtsaktionen sind aktiv **und wirken** — geprüft an der Kameravorgabe, nicht am `enabled`-Zustand; Escape kommt heraus. **Bild:** der Schwenk | offen |
| P5 | Abbau: `SketchPanel` als Vollbildseite entfällt; `SketchField`/`SketchEditorDialog` bleiben (zweiter Weg über den Op-Dialog) | M | **grün:** Referenzzahl der Suite unverändert, kein toter Import | offen |
| P6 | Doku: `konzept-bedienung.md` Teil 4 um die Raumachse ergänzen, `ROADMAP.md` fortschreiben, Handbuch und Abbildung nachziehen | S | `make_manual.py` läuft; Abbildung neu | offen |

**P0 ist neu und steht vorn**, weil G es verlangt: Was nicht vor VTK
gerechnet wird, ist später nicht mehr prüfbar.

**Eine Fehlerbauform, auf die P4 ausdrücklich achtet.** `formwerk-be` hat am
24.08.2026 einen Knopf gefunden, der formal verdrahtet war — der Test prüfte,
dass jede angebotene Handlung einen Handler *hat* — und der nichts bewirkte.
Das Wiederfreigeben der Ansichtsaktionen ist dieselbe Bauform: ein Zustand
wird gesetzt, und niemand prüft die Wirkung. Deshalb prüft P4 die
Kameravorgabe und nicht `isEnabled()`.

**Rückfalloption für P4**, das riskanteste Paket: Der Stapeltausch bleibt bis
P5 im Code. Erweist sich das Schwenken auf einer echten Grafikkarte als
untragbar, ist die Rücknahme eine Zeile.

**Übergabe-Notizen** werden je Paket hier ergänzt — was das nächste Paket
wissen muss, Abweichungen vom Konzept ausdrücklich als solche markiert,
Commit-Hashes nachgetragen.

---

## §7 Offen

- **Antwort von `formwerk-be`** zu `app/ui/main_window.py` (P3, P4 brauchen
  sie) und von `formwerk-d1` zum Merkmals-Picking (P3 baut darauf auf).
- **Der `flat_offsets`-Fund von `formwerk-20`:** `flat_offsets`
  (`sketch_editor.py:373`) ist wortgleich `edit.offsets_of`, `_flat_points`
  (`:383`) wortgleich `edit.flat_points`, elf Aufrufstellen. Mitzunehmen in
  P2, das die Koordinatenrechnung ohnehin anfasst.
- **Ob Drehen beim Zeichnen wirklich häufig ist** — Entscheidung D nimmt es
  an, gemessen ist es nicht. Die Annahme kostet nichts, solange C trägt;
  fiele C, wäre sie neu zu prüfen.
