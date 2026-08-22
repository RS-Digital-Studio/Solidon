# Eigene Funde — an der laufenden Oberfläche gemessen

Nicht aus dem Code geschlossen, sondern am Bild und an Zahlen. Die Aufnahmen
liegen in `../aufnahmen/`, die Skripte, die sie erzeugen, daneben.

Alle Aufnahmen entstehen mit `QScreen.grabWindow` und **nicht** mit
`QWidget.grab`: Der Viewport zeichnet über OpenGL, und `grab` malt an ihm
vorbei — ein schwarzes Rechteck, wo das Modell steht. Wer das übersieht, meldet
einen leeren Viewport, der keiner ist (mir zweimal passiert, siehe unten).

---

## 1. Das Raster im Skizzeneditor ist unsichtbar — dunkel

**Stelle:** `app/ui/sketch_editor.py:1535-1537`

```python
minor = QColor(palette.mid().color())
minor.setAlpha(60)
major = QColor(palette.mid().color())
major.setAlpha(140)
```

`Mid` ist eine Palettenrolle, die `theme.build_palette` **nie setzt** — sie
kommt aus Qts Vorgabe und ist in beiden Themen `#282828`. Gemischt über die
Zeichenfläche ergibt das:

| Thema | Nebenlinie | Hauptlinie |
|---|---|---|
| dunkel (`base` `#1b1f25`) | `#1e2125`, Kontrast **1,02** | `#222326`, Kontrast **1,05** |
| hell (`base` `#ffffff`) | `#cccccc`, Kontrast 1,61 | `#888888`, Kontrast **3,55** |

Im dunklen Thema ist das Raster damit nicht vorhanden — nachgemessen an
`app/images/manual/de/sketch-mode.png`, Zeile y=450: 552 Punkte `#1b1f25`,
dazwischen `#1d2025` und `#1c2025`. Im hellen Thema ist die Hauptlinie
**kräftiger als die Trennlinienfarbe des Themas selbst** (`line` bringt 2,43).

Belegt durch den direkten Vergleich: `aufnahmen/light-skizze.png` zeigt ein
sauberes CAD-Raster, `app/images/manual/de/sketch-mode.png` zeigt keines —
gleicher Code, gleiche Zeichnung.

Dazu: „Am Raster fangen" steht auf **an** mit 1 mm Weite. Gefangen wird also
auf ein Raster, das niemand sieht.

**Fix, gerechnet statt geschätzt** — Zielkontrast 1,35 für die Nebenlinie und
2,0 für die Hauptlinie, ausgehend von der `line`-Farbe des Themas:

| Thema | Nebenlinie | Hauptlinie |
|---|---|---|
| dunkel | `#2f363f` (1,36) | `#464f5c` (2,00) |
| hell | `#dbdee3` (1,35) | `#b1b8c3` (2,00) |

Der Weg dahin: die Werte in die Tabelle `THEMES` aufnehmen und in
`build_palette` als `Midlight` (Nebenlinie) und `Mid` (Hauptlinie) setzen; im
Zeichnen dann `palette.midlight()` und `palette.mid()` **ohne Alpha**. Das
behebt die Ursache — eine ungesetzte Rolle — und nicht nur ihre Wirkung an
dieser einen Stelle.

---

## 2. Gesperrte Bedienelemente behalten den vollen Akzent

**Stelle:** `app/ui/theme.py:133-143` — die Disabled-Gruppe bekommt nur
`Text`, `ButtonText` und `WindowText`, **nicht** `Highlight`.

Referenzvergleich (`aufnahmen/probe_disabled.py`): dasselbe Widget zweimal
gerendert, einmal bedienbar, einmal gesperrt, dann die Akzentpunkte gezählt.

```
dark:  Akzent #f0a54a — bedienbar 2638 Punkte, gesperrt 2638 Punkte
light: Akzent #f0a54a — bedienbar 2638 Punkte, gesperrt 2638 Punkte
```

**Pixelgleich, in beiden Themen.** Betroffen ist alles, was Fusion mit
`Highlight` zeichnet: die Rille des Reglers und der Fortschrittsbalken. Zu
sehen in `aufnahmen/tool-section.png` — der Schnittregler ist gesperrt
(`SectionBar._update_enabled`, `app/ui/section_bar.py:199-204`), trägt aber
eine gefüllte Akzentrille und liest sich als bedienbar.

Das ist genau der Fehler, den der Kommentar in `theme.py` für die
Schriftrollen schon beschreibt: „Ein gesperrtes Ankreuzfeld war pixelgleich mit
einem bedienbaren". Für `Highlight` ist er offen.

**Fix:** in `build_palette` auch
`ColorGroup.Disabled, ColorRole.Highlight → colours["disabled"]` setzen.
Nebenbei fehlt dem Stylesheet jede `QSlider`-Regel (`app/ui/style.py` kennt
keine) — der Griff ist dadurch Fusion-Vorgabe und in `tool-layers.png` kaum zu
treffen.

---

## 3. Die „0" der Plattenskala liegt an der Ecke — der Nullpunkt ist die Mitte

**Stelle:** `app/ui/viewport.py:591-606`

```python
marks.append(((side, -half_depth - BED_SCALE_GAP, 0.0), f"{abs(side):.0f}"))
...
marks.append(((-half_width - BED_SCALE_GAP, -half_depth - BED_SCALE_GAP, 0.0), "0"))
```

Die Platte liegt symmetrisch um den Ursprung (`half_width = width / 2`), und
ein Körper aus `create_box` steht in ihrer Mitte. Bei 220 mm heißt das an der
Vorderkante von links nach rechts: **„0" bei x = −110, „100" bei x = −100,
„50" bei −50, „50" bei +50, „100" bei +100.** Die Null steht zehn Millimeter
neben der Hundert, und die Zahlen sind Abstände von der Mitte, während die Null
an der Ecke klebt. `abs()` nimmt zudem beiden Seiten das Vorzeichen — dieselbe
„100" liegt zweimal im Bild.

Zu sehen in `aufnahmen/real-leer.png`.

**Der Test hält den Fehler fest**, `tests/test_analysis_ui.py:1806`:
`assert labels.count("0") == 1, "der Nullpunkt gehört beiden Kanten, steht aber
einmal da"` — er gehört keiner der beiden Kanten an dieser Stelle.

**Fix:** je Kante ihre eigene, vorzeichenbehaftete Skala mit der Null in der
Mitte (−100, −50, 0, 50, 100). Das passt zu den Positionsfeldern der Dialoge,
die ebenfalls vorzeichenbehaftet sind. Test und Zusicherung ziehen nach.

Zum Vergleich: die Skizzenfläche macht es richtig (`_paint_scale`,
`app/ui/sketch_editor.py:1561` ff.) — dort stehen −60 … 60 mit Vorzeichen.

---

## 4. Die Kamera passt ohne Luft ein

**Stelle:** `app/ui/viewport.py:3479-3483`

```python
bounds = self._object_bounds()
if bounds is None:
    self.plotter.reset_camera()
else:
    self.plotter.reset_camera(bounds=bounds)
```

`reset_camera(bounds=…)` passt **genau** ein. In `aufnahmen/cam-3-quader.png`
berührt ein 40 × 30 × 10 großer Quader links und rechts den Bildrand, in
`aufnahmen/tour-1-offen.png` läuft die Halterung bis an die Kante. Die
Druckplatte ist dabei aus dem Bild heraus, es fehlt also auch der
Größenvergleich, für den sie da ist.

**Ohne Körper** nimmt der Einpassvorgang alle Aktoren, also den 250 mm hohen
Bauraumrahmen. Die Platte rutscht damit ins untere Drittel und verschwindet
teilweise hinter der schwebenden Werkzeugzeile — gemessene Kamerastellung nach
*Neues Projekt*: Brennpunkt `(0, 0, 124,9)`, das ist die Mitte des Bauraums,
nicht die der Platte (`aufnahmen/cam-1-neu.png`).

**Fix:** die Grenzen um 10–12 % um ihre Mitte weiten, bevor sie an
`reset_camera` gehen; für die leere Szene die Platte einpassen statt des
Rahmens. Danach nachsehen, nicht nur rechnen (dieselbe Lehre wie beim
Schattenwurf im ROADMAP).

---

## 5. Vier von acht Werkzeugen öffnen in einem Zustand, in dem ihr eigener Hinweis nicht gilt

`ToolStrip.add` nimmt einen `reset`-Rückruf, der beim **Schließen** läuft
(`app/ui/tool_strip.py:225-235`). Ein Rückruf fürs **Öffnen** gibt es nicht,
also steht jede Leiste beim Aufklappen auf ihrem Anfangswert — und der ist bei
vier von acht „aus":

| Werkzeug | Zustand beim Öffnen | Hinweis daneben | Aufnahme |
|---|---|---|---|
| Schnitt | „Kein Schnitt", Regler gesperrt | „Ziehen Sie den Regler durch das Teil" | `tool-section.png` |
| Messen | „Nicht messen" | „Zwei Punkte im Bild anklicken" | `tool-measure.png` |
| Bewegen | Haken „Gizmo" leer, kein Griff im Bild | „Am Griff im Bild ziehen, oder Werte eintippen" | `tool-transform.png` |
| Analyse | „Keine Karte" | „Karte wählen — …" (ehrlich) | `tool-analysis.png` |

Bei *Bewegen* stimmt auch die zweite Hälfte des Satzes nicht: Zahlenfelder gibt
es in dieser Leiste nicht, nur Rasterfang und Winkelfang.

**Fix:** ein `start`-Rückruf in `Tool`, in `activate()` beim Öffnen gerufen.
Schnitt → Achse Z, Messen → *Abstand messen*, Bewegen → Gizmo an. *Analyse*
bleibt, wie es ist: eine Karte kostet Rechenzeit, und der Hinweis sagt es.
Kein Test hält den heutigen Öffnungszustand fest (geprüft: `tests/test_ui.py`,
`test_split_tool.py`, `test_analysis_ui.py`, `test_interface_limits.py`).

---

## 6. Der Bausteinkatalog zeigt 4 von 19 Bausteinen

**Stelle:** `app/ui/catalog.py:55-60` — `TILE_ICON = 96`, `TILE_WIDTH = 164`,
`TILE_HEIGHT = 190`.

In einem 900 × 620 großen Fenster (`aufnahmen/katalog-900.png`) sind vier
Bausteine sichtbar, im 1180er Fenster neun. Jede Kachel trägt drei Textzeilen
(Name, Parameterliste, „– nimmt Material weg"), was die Höhe treibt; eine
Gruppe mit einem einzigen Eintrag („Einlegeteile") kostet eine volle Zeile von
230 Punkten. Die Spalte rechts, in der die Beschreibung stünde, bleibt dabei
leer — dort steht „Wählen Sie einen Baustein".

Dazu ein Umbruchfehler: bei zweizeiligem Namen fällt die dritte Zeile aus der
Kachel („Schnappverbinder für eine Naht / Durchmesser, Länge" in
`app/images/manual/de/catalog.png`).

**Fix:** Kachel auf etwa 132 × 150 bei 80er Bild, die Parameterzeile aus der
Kachel in die Detailspalte (die ohnehin leer steht) und in den Tooltip. Dann
passen alle 19 ohne Rollen ins Fenster.

---

## 7. Der leere Chat ist ein Loch mit Vorschlägen darunter

`aufnahmen/chat-leer.png`: Der leere Gesprächsverlauf nimmt etwa 350 Punkte
Höhe als schwarze Fläche mit Rahmen; die vier Beispielfragen stehen darunter am
Fensterboden. Der Hinweis oben („Der Chat braucht einen Zugang zu einem
Sprachmodell") und der Knopf „Chat einrichten …" sind gut — die Aufteilung
kehrt nur die Reihenfolge der Wichtigkeit um.

**Fix:** solange nichts gefragt wurde, die Beispiele **in** die leere Fläche
setzen; der Verlauf wächst von oben, sobald es einen gibt.

---

## 8. Der Generierungsdialog sagt, was fehlt, und bietet nichts an

`aufnahmen/generate.png`: „Es läuft kein Generator. Solidon spricht lokal mit
ComfyUI — ohne das bleibt dieser Weg zu, alles andere funktioniert weiter."
Kein Knopf, kein Verweis, keine Anleitung. Der Chat macht es an derselben
Stelle richtig („Chat einrichten …"). Das ist die halbe Antwort von §2.7.

**Fix:** derselbe Weg wie im Chat — ein Knopf, der die Einrichtung erklärt.

---

## 9. Das Handbuchbild des Operationsdialogs zeigt Totraum, den es nicht gibt

`tools/make_figures.py:71` erzwingt `DIALOG = (520, 460)`. Die Dialoge wachsen
aber korrekt mit ihrem Inhalt — gemessen:

```
op-drill_hole        380x303 (sizeHint 290x303)
op-hollow_object     380x233
op-create_lid        380x298
op-split_plane       380x157
op-label_text        380x427
op-repair            380x143
```

Auf `app/images/manual/de/op-dialog.png` stehen deshalb rund 200 Punkte Leere
zwischen dem letzten Feld und „Weitere Einstellungen", und die Zahlenfelder
sind auf 330 Punkte gestreckt. Das Bild wirkt unfertig, obwohl der Dialog es
nicht ist.

**Fix:** im Figurenskript `adjustSize()` statt der festen Höhe (Breite darf
gesetzt bleiben).

---

## 10. Kleinere, belegte Sachen

* **„2 × Teile"** — `app/ui/panels.py:1371`: das × vor einem Plural ist falsches
  Deutsch. Entweder „2 Teile" oder „2 × Teil".
* **Prüfbericht ohne Befunde** (`aufnahmen/real-leer.png`): „Keine Befunde.",
  darunter ein Suchfeld, ein Filter „Alle" und ein leerer Kasten von etwa 240
  Punkten. Zwei Bedienelemente ohne Gegenstand.
* **Die Tour kürzt ihre kommenden Schritte** (`aufnahmen/tour-1-offen.png`):
  vier von fünf Zeilen enden mit „…", obwohl unter ihnen 150 Punkte frei sind.
  `app/ui/tour.py:360` — `text.set_wrapped(index == self._current)`. Der
  Schrittbereich liegt in einer `QScrollArea` (`tour.py:143`), Umbrechen ist
  also gefahrlos; `StepLabel` selbst bleibt, wie es ist (der Test in
  `tests/test_style.py:286` prüft das Widget, nicht die Regel).
* **Statuszeile rechts** (`aufnahmen/tour-1-offen.png`): „Demo — noch 73 Tage,
  bis zum 30.10.2026 **20 g · 1 h 19 min**" — Gewicht und Druckzeit stehen ohne
  Trennung und ohne Bezeichnung neben dem Demo-Hinweis.
* **Bemalen zeigt die Slotnummer, nicht die Farbe**
  (`aufnahmen/tool-paint.png`): „Slot 1". Womit man malt, ist eine Farbe; der
  Druckdialog zeigt sie als Feld, das Werkzeug nicht.
* **Der Trennen-Bereich hat 130 Punkte Totraum**
  (`aufnahmen/tool-split.png`): Hinweiszeile oben, Bedienzeile unten, dazwischen
  nichts.
* **Der Druckdialog trägt zwei leere Rahmen**
  (`aufnahmen/print-settings.png`): unter „Weitere Einstellungen" ein leerer
  Kasten, und „Profile des Slicers" steht als gesperrte Gruppe mit drei leeren
  Auswahlfeldern da, während darunter „Der Profilbestand wird durchgesehen …"
  läuft. Außerdem ist „Weitere Einstellungen" hier ein **Ankreuzfeld**, in den
  Operationsdialogen ein aufklappbares Dreieck — zwei Formen für dieselbe Sache.
* **Die Typografie-Skala ist in 21 von 30 Oberflächendateien nie benutzt.**
  `set_level` steht in neun (chat, dialogs, facts, first_run, header, op_dialog,
  panels, start_screen, style). Ohne Stufe sind alle Texte Grundgröße — im
  Druckdialog, im Skizzeneditor, in allen sieben Werkzeugleisten, in den
  Einstellungen, in der Tour, im Katalog. Beispiel: `QLabel(tr("Bedingungen"))`
  in `app/ui/sketch_editor.py:2326` ist eine Abschnittsüberschrift und sieht aus
  wie Inhalt.
* **`BaseParams.fields()` bricht mit `TypeError`**, wenn eine Operation keine
  eigene Parameterklasse hat: `delete_object` benutzt `BaseParams` direkt, und
  das ist keine Dataclass (`app/core/types.py:695-705`). Heute ruft nur der
  Bausteinbau die Methode, es fällt also nichts um — aber der nächste
  Aufrufer stolpert.
* **Der Skizzeneditor nennt rohe Punktnummern**
  (`app/images/manual/de/sketch-mode.png`): „Deckung (1, 2)", „Abstand 120,00
  (0, 1)". Die Klammern sind Indizes des Datenmodells, und die Maße stehen ohne
  Einheit. Dazu zwei unbeschriftete Zahlenfelder in der Leiste („2,00 mm",
  „0,00 mm"), die sich nur über Tooltips erklären.

---

## Zwei Behauptungen, die an der Gegenprüfung gestorben sind

Beide standen kurz auf meiner Liste. Sie stehen hier, weil das Verfahren
wichtiger ist als der Fund.

**Das rote „Bild" im Generierungsdialog.** Auf `aufnahmen/generate.png` schien
die Beschriftung „Bild" rot zu sein, während „Beschreibung" weiß war — ein
Feld im Fehlerzustand, dachte ich. Abgetastet ergaben die Punkte `#8d5845` und
`#34589a` **neben** einem Kern aus `#e6e9ee`: Subpixel-Fransen der
ClearType-Darstellung. Es gibt keine Farbe im Code, und es gibt keinen Fund.
Dieselbe Falle wie beim Komma im ROADMAP, und dieselbe Antwort: erst messen.

**Das fehlende Menü *Erzeugen*.** Mein erstes Aufnahmeskript rief
`build_application()` und bekam eine Menüleiste mit acht Einträgen statt neun,
alle Operationseinträge gesperrt — und der Hinweis im leeren Objektbaum
verwies auf ein *Erzeugen*, das nicht da war. Die Ursache war das Skript:
`build_application` füllt das Register **nicht**, das tut `main()`
(`app/ui/app.py:132`). Mit `load_operations()` davor stehen neun Menüs, alle
innerhalb der Grenzen von `.claude/rules/oberflaeche.md` (Datei 12 Zeilen —
genau am Limit).

Was davon bleibt, ist eine Beobachtung ohne Dringlichkeit: Ein Fenster, das aus
einem leeren Register gebaut wird, sieht aus wie ein defektes Programm und sagt
das nicht. Für die ausgelieferte Anwendung belanglos, für jeden Test und jedes
Werkzeug, das `build_application` benutzt, eine Stolperstelle.

---

## Was gezielt geprüft und in Ordnung war

* **Die Dialoge wachsen mit ihrem Inhalt** — 143 bis 427 Punkte Höhe, kein
  `setFixedSize`.
* **Die Standardknöpfe sind deutsch.** `install_qt_translations`
  (`app/ui/app.py:33`) lädt Qts eigenen Katalog; alle sechs Sprachen laden
  nachweislich (`qtbase_de.qm` … `qtbase_pt.qm` liegen in der Umgebung). Nur
  wer den Aufruf umgeht — wie mein erstes Skript — sieht „Cancel".
* **Die Textfarben des hellen Themas sind korrekt.** Der Eindruck, alles sei
  blass, kam von der Kantenglättung: der dunkelste Punkt in Menü, Überschrift,
  Feldwert, Werkzeugzeile und Statuszeile ist überall `#1c2026`, also die
  Themafarbe selbst.
* **Die Skizzenskala trägt Vorzeichen** (−60 … 60), anders als die Plattenskala.
* **Das Ausblenden der Explosionsansicht** bei einem einzigen Körper ist
  begründet und im Code gegen `set_usable` abgegrenzt
  (`app/ui/tool_strip.py:268-292`) — kein Fund.
* **Die Umgebung entspricht `constraints.txt`** (`tools/check_env.py`).
* **Der kalte Start liegt bei 3,9 s** bis zum aufgebauten Fenster, mit
  Ladebildschirm und Fortschritt darüber.
* **Grenzwerte gehalten:** 9 Menüs, längstes Menü 12 Zeilen, 8 Werkzeuge,
  höchstens 8 Felder auf einer Dialogvorderseite (`label_text`).
* **Der Basislauf der Suite ist grün** (`pytest -m "not performance"`, exit 0),
  gemessen vor jeder Änderung.
