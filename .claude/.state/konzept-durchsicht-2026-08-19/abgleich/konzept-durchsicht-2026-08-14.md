# Abgleich: konzept-durchsicht-2026-08-14.md

Geprüft am 19.08.2026 gegen `main` (b0415d6). Grundlage: die fünfzehn intern
prüfbaren Behauptungen der Sondierung, jede am Dokumenttext nachgelesen.

**Zählung:** stimmt 8 · überholt 4 · falsch 2 · unprüfbar 1

Zwischen dem Stand des Dokuments (14.08.2026) und heute liegen 103 Commits.

---

## 1 — „84 Operationen" (Einleitung, Teil 4.2, Teil 5)

**Behauptung:** „alle 84 Operationen mit Titel, Menüweg und Beschreibungssatz
aufgelistet" (Zeile 6), „Sechs Kürzel auf 84 Operationen" (Zeile 189), „Jede
der 84 Operationen hat einen Beschreibungssatz" (Zeile 238).

**Urteil: überholt.**

**Beleg:**

```
.venv/Scripts/python.exe -c "from app.core.bootstrap import load_operations; from app.core.registry import REGISTRY; load_operations(); print(len(REGISTRY.all()))"
→ 85
```

Die Zahl ist nicht erst später gewachsen, sie war schon am Ende desselben
Tages falsch: Von den 69 `@register_op`-Stellen erzeugt eine
(`app/core/knowledge/parts/ops.py`) je Baustein ein `insert_<name>`. Mit dem
Schnappverbinder aus Teil 4 kam der 85. Eintrag dazu — 68 statische plus 17
Bausteine. `git show 33031da^` zählt 16 Bausteine (= 84 Ops), `git show
33031da` zählt 17 (= 85). 33031da ist derselbe Commit, den Teil 4 beschreibt.

**Nachgeprüft und weiterhin richtig:** kein Registereintrag ohne `doc`, kein
Parameter ohne `doc`, und `label_text` ist mit acht Feldern der vollste Dialog
auf der Vorderseite (`placement="front"`), Grenze acht. Nur die Zahl 84 stimmt
nicht.

**Stattdessen:** „alle 85 Operationen …" bzw. „Sechs Kürzel auf 85
Operationen". Wer sie zitiert, sollte dazuschreiben, dass 17 davon aus der
Bausteinbibliothek erzeugt werden und die Zahl mit jedem neuen Baustein steigt.

---

## 2 — „128 Menüzeilen in drei Szenenzuständen ausgelesen" (Einleitung)

**Urteil: überholt.**

**Beleg:** Menüleiste aus `build_application([])` nach `load_operations()`,
leere Szene, rekursiv gezählt (Skript unter
`…/scratchpad/menucount2.py`):

```
leaves 136   submenus(incl top) 32   sum 168
```

136 anklickbare Zeilen allein im Grundzustand. Das Dokument zählt über drei
Szenenzustände und kommt auf 128 — schon ohne Methodenstreit liegt die heutige
Zahl darüber, und mindestens eine Zeile ist mit `insert_snap_connector`
dazugekommen.

**Stattdessen:** entweder ohne Zahl („die Menüleiste vollständig ausgelesen")
oder mit Datum und Methode: „136 anklickbare Menüzeilen auf der leeren Szene,
gezählt am 19.08.2026".

---

## 3 — „Das Trennwerkzeug ist der achte Umschalter" (Teil 1, Teil 4.2, Teil 5)

**Behauptung:** Tabelle in Teil 1, Zeile 68: „achter Umschalter der
Werkzeugzeile, Symbol `split`"; Teil 5, Zeile 245: „der achte Umschalter von
selbst mit".

**Urteil: falsch** — und zwar schon am 14.08.

**Beleg:** `app/ui/main_window.py:894–990` meldet die Werkzeuge in dieser
Reihenfolge an, und `ToolStrip.add` hängt jeden Knopf ans Ende der Zeile
(`app/ui/tool_strip.py:185`):

```
section · measure · transform · analysis · layers · explode · split · paint
```

`split` ist der **siebte**, `paint` der achte. Die Kürzel werden über
`enumerate(self.tools.tools(), start=1)` vergeben
(`app/ui/main_window.py:807`), das Trennwerkzeug bekommt also **Alt+7**, Alt+8
öffnet das Bemalen. Das Handbuch sagt es richtig: „Werkzeug *Trennen* unten in
der Werkzeugzeile (Alt+7)" (`app/core/manual.py`, Kapitel Teilen; ebenso in
allen fünf Katalogen, z. B. `app/i18n/locales/en.json:885`).

Der Fehler war von Anfang an drin: `git show 49d4c73:app/ui/main_window.py`
(der Commit, der das Werkzeug und dieses Dokument anlegt) zeigt dieselbe
Reihenfolge mit `paint` hinter `split`. Er steht außerdem in
`ROADMAP.md:5511` („Achter Umschalter in der Werkzeugzeile").

**Stattdessen:** „siebter Umschalter der Werkzeugzeile, Symbol `split`,
`Alt+7`". In Teil 5 genügt „jeder Umschalter von selbst mit".

---

## 4 — „Eine Transaktion, ein Undo — plus ein Passungspaar je Stift (§14)" (Teil 1)

**Urteil: überholt** (heute richtig, damals unvollständig — und die Zusage
„je Stift" hat inzwischen zwei ausgewiesene Ausnahmen).

**Beleg:**

* Am 14.08. liefen die Passungen **an** der Transaktion vorbei. Commit
  `5f5cfd4` (15.08.2026, „Sechs Passungen zeigten ins Leere"): „die Paare
  [wurden] bisher nach dem Aufruf ins Dokument geschrieben, also an der
  Transaktion vorbei: Ein Undo nahm die Teilung zurück und ließ sie stehen."
  Behoben durch `History.apply(..., changes=ChangeFn)`
  (`app/core/scene/history.py:206–226`) — seitdem stimmt der Satz.
* „Ein Passungspaar je Stift" gilt nicht mehr ausnahmslos: Wird ein schon
  geschnittenes Stück erneut geteilt, entfallen die Paare mit dem Hinweis
  `split.fit_dropped` (`app/core/split.py:212, 280, 305`).
* Und es entstehen nicht in jedem Fall Stifte: `plan_pins` misst seit
  `52826ef` (15.08.) die Materialtiefe hinter der Naht und meldet
  `split.seam_too_thin`, wo die Mindesteinbindung fehlt.

**Stattdessen:** „eine Transaktion, ein Undo — Passungen inbegriffen (seit
15.08. über `History.apply(changes=…)`); je gesetztem Stift ein Passungspaar,
beim Weiterteilen entfallen die geerbten Paare mit `split.fit_dropped`."

---

## 5 — „11 Geometrietests und 15 Oberflächentests" (Teil 1)

**Urteil: überholt.**

**Beleg:**

```
.venv/Scripts/python.exe -m pytest tests/test_split_line.py --collect-only -q  → 28
.venv/Scripts/python.exe -m pytest tests/test_split_tool.py --collect-only -q  → 25
.venv/Scripts/python.exe -m pytest tests/test_split_ui.py   --collect-only -q  →  9
```

Die Zahlen des Dokuments sind der Stand des ersten Commits (`49d4c73`: 11
Testfunktionen in `test_split_line.py`, 19 in dem dort neu angelegten
`test_split_tool.py`) und wurden noch am selben Tag überholt (`33031da`: 25 und
25). Seither unverändert.

**Stattdessen:** „Gemessen: 28 Geometrietests in `tests/test_split_line.py` und
34 Oberflächentests in `tests/test_split_tool.py` und `tests/test_split_ui.py`."

---

## 6 — „`plan_pins` und `add_pins` nehmen jetzt eine Ebene statt einer Achse"

**Urteil: stimmt.**

**Beleg:** `app/core/geom/pins.py:136–143` — `plan_pins(mesh, plane:
SectionPlane, *, count, wall, shape)`. `add_pins`
(`app/core/geom/pins.py:350–357`) nimmt den `PinPlan`, und der führt die
Richtung als `normal` mit, ausdrücklich als „die Normale der Trennebene"
(`app/core/geom/pins.py:101–108`).

---

## 7 — „Drei Formen, kein Schnapper" (Teil 1) — Widerspruch im Dokument

**Behauptung:** Zeile 105: „Rund, Sechskant und Schwalbenschwanz stehen als
Querschnitt zur Wahl … Der Schnapper fehlt mit Absicht"; Tabelle Zeile 80 der
Sondierung ebenso.

**Urteil: falsch** — Teil 4 desselben Dokuments (Zeile 228) sagt, der
Schnapper sei gebaut.

**Beleg:** `app/core/geom/prepare_ops.py:74`

```python
CONNECTOR_SHAPES = ("round", "hex", "dovetail", "snap")
```

Vier Werte, und der Kommentar darüber erklärt genau den Fall, den Teil 1
verneint: „Der Schnapper ist kein Querschnitt … er steht hier trotzdem in
derselben Liste, weil er für den Nutzer dieselbe Entscheidung ist."
Eingeführt hat das `git log -S` → `33031da` (14.08.2026), also derselbe
Commit, den Teil 4 beschreibt. Die Leiste bietet alle vier an
(`app/ui/split_bar.py:108–111`, Schleife über `CONNECTOR_SHAPES`), das Handbuch
listet vier Punkte inklusive „Schnapper" (`app/core/manual.py`, Kapitel
Teilen).

**Stattdessen:** „Vier Verbinder zur Wahl: rund, Sechskant, Schwalbenschwanz —
und der Schnapper. Die ersten drei sind Querschnitte, der vierte ist ein
Mechanismus mit eigenem Baustein; er braucht eine Naht von mindestens 5,4 mm,
sonst wird rund daraus (`split.snap_too_small`)."

*Nebenbefund im Code:* Die Docstring von `PinPlan.shape`
(`app/core/geom/pins.py:111`) nennt weiterhin nur „``round``, ``hex`` oder
``dovetail``", obwohl `plan_pins` „snap" verarbeitet
(`app/core/geom/pins.py:205`).

---

## 8 — `style.make_primary()`, sieben Hauptknöpfe, Test gegen `setDefault`

**Urteil: stimmt.**

**Beleg:** `app/ui/style.py:82–103` setzt `setDefault(True)` **und**
`QFont.Weight.DemiBold`. Aufgerufen wird es an genau sieben Stellen:
`main_window.py:1066`, `op_dialog.py:999`, `pose_bar.py:56`,
`print_settings_dialog.py:1417`, `sculpt_bar.py:129`, `split_bar.py:125`,
`start_screen.py:406`. `setDefault(True)` steht in `app/ui/` nur noch in
`style.py:99`; der Wächter ist
`tests/test_style.py::test_every_default_button_of_the_surface_goes_through_make_primary`
(Zeile 333–349).

---

## 9 — „Der Knopf ist danach 115 px breit" (Teil 2.1)

**Urteil: unprüfbar** in dieser Umgebung.

**Beleg:** Die Messung braucht die echte Qt-Plattform; unter
`QT_QPA_PLATFORM=offscreen` — den `tests/conftest.py` setzt — hat Qt auf
dieser Maschine keine Schriftfamilie, jede Textbreite ist damit
bedeutungslos (CLAUDE.md, Abschnitt „Befehle"). Die Erklärung dahinter ist
belegt und unverändert: `app/ui/style.py:86–98` nennt dieselben 77 gegen 89
Bildpunkte.

**Stattdessen:** Zahl behalten, aber mit Datum und Plattform versehen, sonst
liest sie sich wie eine Invariante.

---

## 10 — Vier Menütitel umbenannt (Teil 3)

**Urteil: stimmt.**

**Beleg:**

| jetzt | Stelle |
|---|---|
| Verbinden und Abziehen | `app/core/registry/registry.py:44` (`"boolean"`) |
| Teilen und Anpassen | `app/core/registry/registry.py:53` (`"prepare"`) |
| Dreiecke verringern | `app/core/geom/mesh_ops.py:397` |
| Kopien in Reihe oder Kreis | `app/core/scene/ops.py:227` |

Alle vier stehen in allen fünf Katalogen (z. B. `app/i18n/locales/en.json:832,
1418, 2099, 2172`). `.venv/Scripts/python.exe -m pytest
tests/test_translations.py -q` → 112 passed.

---

## 11 — „Automatisch teilen …" steht unter *Vorbereiten* (Teil 3)

**Urteil: stimmt.**

**Beleg:** `app/ui/main_window.py:1455–1481` — die Gruppe wird über die
**Kategorie** `prepare` gesucht, nicht über den übersetzten Titel, davor ein
`addSeparator()`; fehlt die Gruppe, bleibt *Bearbeiten* der Platz.

*Nebenbefund im Code:* `app/core/tour.py:535` sagt weiterhin „Für eigene Teile
macht das **Bearbeiten → Automatisch teilen** in einem Zug" — die geführte Tour
schickt den Nutzer ins falsche Menü.

---

## 12 — „Alle fünf offenen Punkte aus Teil 4 sind abgearbeitet" (Teil 4)

**Urteil: stimmt.**

**Beleg:** `ROADMAP.md:5546–5548` („Offen, mit Grund — Alle fünf sind
inzwischen abgearbeitet") und der Abschnitt „Die offenen Punkte abgearbeitet
(14.08.2026)" ab `ROADMAP.md:5549`. Stichproben im Code: `TWIN_TOGGLES` statt
fester Beschriftung (`app/ui/main_window.py:113, 4518–4534`), Hälftennamen
„… A · Stifte" / „… B · Löcher" (`app/core/geom/prepare_ops.py:86–89, 122–143`),
`fitting_pins()` (`app/core/split.py:107`), Menüzeile „Fernsteuerung durch
andere Programme zulassen (MCP)" (`app/ui/settings_dialog.py:141`),
`snap_connector` (`app/core/knowledge/parts/mechanics.py:457`).

---

## 13 — „Acht Werkzeuge mit Alt+1 bis Alt+8, sechs Kürzel für Operationen"

**Urteil: stimmt** (die Zuordnung *welches* Werkzeug welche Ziffer bekommt,
siehe Befund 3).

**Beleg:** `app/ui/main_window.py:806–809`. Registerkürzel:

```
delete_object Del · drill_hole Ctrl+B · duplicate_object Ctrl+D
rename_object F2 · rotate_object Ctrl+R · translate_object Ctrl+T
```

— sechs, unverändert.

---

## 14 — „`snap_connector` ist der vierzehnte Baustein; 8 mm, 5,4 mm, `SNAP_RATIO`"

**Urteil: stimmt**, mit einer Präzisierung, die das Nachzählen sonst scheitern
lässt.

**Beleg:** `PARTS.all()` liefert **17** Einträge; drei davon sind
Kalibrierkörper (`fit_ladder`, `wall_ladder`, `overhang_fan`, Gruppe
`calibration`). Ohne sie sind es 14, und `snap_connector` ist der vierzehnte.
`grep -c "@register_part"` ergibt 17 — wer so zählt, findet die Aussage falsch.
`SNAP_RATIO = 10.0` (`app/core/knowledge/parts/mechanics.py:32`),
`SNAP_MIN_REACH = 8.0` mit der 5,4-mm-Rechnung im Kommentar
(`app/core/geom/pins.py:74–81`), der Befund `split.snap_too_small`
(`app/core/geom/pins.py:477`).

**Stattdessen:** „`snap_connector` — der vierzehnte Baustein der Bibliothek
(17 Registereinträge, drei davon Kalibrierkörper)."

---

## 15 — „Fünf Sprachkataloge vollständig: 26 neue Texte, vier Titel, drei verwaiste weg"

**Urteil: stimmt.**

**Beleg:** `git show 49d4c73 -- app/i18n/locales/en.json` → 32 hinzugefügte,
3 entfernte Schlüsselzeilen; die vier umbenannten Menütitel sind Teil der 32,
es bleiben 28 für das Trennwerkzeug im weiteren Sinn — die Größenordnung des
Dokuments trägt. Alle fünf Kataloge haben heute identisch 2647 Einträge,
`tests/test_translations.py` läuft grün (112 passed).

---

## Was beim Lesen zu einer falschen Entscheidung führt

1. **Alt+8 öffnet nicht das Trennen, sondern das Bemalen** (Befund 3). Der
   Fehler steht an drei Stellen im Dokument und einmal in `ROADMAP.md:5511`.
2. **Der Schnapper steht in der Formliste** (Befund 7). Teil 1 verneint, was
   Teil 4 desselben Dokuments baut; wer nur Teil 1 liest, hält eine gebaute
   Funktion für offen.
3. **84 Operationen** (Befund 1) — die Zahl wandert durch drei Abschnitte und
   war am Abend ihres eigenen Stichtags schon 85.
4. **„Ein Passungspaar je Stift, eine Transaktion"** (Befund 4) — die
   Transaktion stimmte damals nicht, die Ausnahmslosigkeit stimmt heute nicht.
5. **Testzahlen 11/15** (Befund 5) — wer damit einen Regressionsvergleich
   aufsetzt, misst gegen einen Stand, den es nur für einen halben Tag gab.
