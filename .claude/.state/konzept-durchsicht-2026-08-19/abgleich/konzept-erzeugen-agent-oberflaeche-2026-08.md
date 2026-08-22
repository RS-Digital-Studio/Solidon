# Abgleich: konzept-erzeugen-agent-oberflaeche-2026-08.md

**Geprüft am:** 19.08.2026 gegen `main` (b0415d6)
**Dokumentstand laut Kopfzeile:** 12.08.2026 — letzte Änderung an der Datei
aber 18.08.2026 (`c3f4c13`, „Fünf Messberichte gaben den Bestand von damals
für den heutigen aus")
**Geprüft:** 15 intern prüfbare Behauptungen aus der Arbeitsmappe, dazu die
Textstellen darum herum.

## Zählung

| Urteil | Anzahl |
|---|---|
| stimmt | 4 |
| überholt | 8 |
| falsch | 1 |
| unprüfbar | 2 |

---

## Der eine Satz, der über dem ganzen Dokument fehlt

`ROADMAP.md:4663` trägt die Überschrift **„Das Erzeugen-und-Agent-Konzept
abgearbeitet (12.08.2026)"** und darunter sieben abgehakte Punkte. Sechs
davon sind genau die Vorschläge dieses Papiers (L1, D1, A1, A2, M1/H1, die
breiten Bildschirme). Das Papier selbst sagt an keiner Stelle, dass das
passiert ist — es endet mit Teil 9 als Arbeitsliste („Nach Wirkung, nicht nach
Aufwand"), von der fünf der sechs Punkte am selben Tag erledigt wurden.

**Der Widerspruch im Dokument:** Teil 5 wurde am 18.08. nachgezogen (96
Werkzeuge, 110 KB) und trägt sogar den Satz „Gemessen wurde weiter unten bei
88 Werkzeugen … seither ist das Register gewachsen". Wer eine Zahl nachzieht,
liest die Vorschläge zwei Absätze weiter unten mit — und die stehen weiter da,
als wären sie offen. Das Dokument sieht dadurch gepflegt aus und ist es nur in
den Zahlen, nicht in den Handlungsempfehlungen.

Was oben fehlt: *„Umgesetzt am 12.08.2026, siehe ROADMAP.md → Das
Erzeugen-und-Agent-Konzept abgearbeitet. Zwei Punkte fielen anders aus als
vorgeschlagen (A1, L1), einer ist offen geblieben (B1)."*

---

## Teil 1 — Viewport

### B1.1 „Viewport blieb nach dem Laden leer; Fix `_render_now` steht, der Nachweis fehlt"

**Urteil: überholt** — und zwar in beide Richtungen.

*Beleg:*
- `app/ui/viewport.py:1625` `_render_now()` steht und wird aus `show_scene`
  gerufen (`app/ui/viewport.py:1569`).
- `ROADMAP.md:4697–4706`, Abschnitt „Was die Sitzung über das Prüfen gelernt
  hat": *„Ein Messgerät, das seinen Gegenstand verändert, misst nichts."* Der
  VTK-Screenshot rendert neu und reparierte den Zustand, den er zeigen sollte;
  `QWidget.grab()` lässt den OpenGL-Bereich schwarz. Beide „haben mich
  stundenlang einen Viewport-Fehler jagen lassen, **den es in der laufenden
  Anwendung nicht gab**". Gegenprobe war der Stand vom 08.08.: im Prüfskript
  derselbe Fehler, in der Anwendung intakt.
- Die im Papier genannte „nächste Spur" ist ebenfalls abgearbeitet:
  `app/ui/viewport.py:1144` setzt `WA_NoSystemBackground` jetzt auf `True`,
  mit einem Kommentarblock ab Zeile 1135, der genau die Begründung des Papiers
  trägt.

*Was stattdessen dastehen müsste:* „Der Befund war ein Messartefakt. Die
Prüfskripte fuhren `processEvents()` statt `app.exec()`; ein natives
OpenGL-Fenster zeichnet so nur, solange etwas passiert. In der normal
gestarteten Anwendung stand das Bild — auch auf dem Stand vom 08.08.
`_render_now` und `WA_NoSystemBackground=True` sind trotzdem drin und
richtig."

*Folge, wenn man es nicht weiß:* Teil 9 Punkt 1 („Ein Programm, dessen Bild
leer bleibt, hat kein anderes Problem") schickt jemanden auf eine Jagd nach
einem Fehler, der nie in der Anwendung war. Das ist der teuerste Fehlläufer
dieses Dokuments.

---

## Teil 2 — Bild zu 3D

### B2.1 „42,5 s / 1.588.016 Dreiecke; zweiter Lauf 44,9 s / 1.088.166"

**Urteil: unprüfbar** — ComfyUI läuft hier nicht, die Messung ist nicht
nachfahrbar. Konsistent bleibt sie: `ROADMAP.md:4678` zitiert dieselben Zahlen
(„42 s, 1.588.016 Dreiecke, null Merkmale"). Kein Änderungsbedarf, aber der
Satz sollte den Messtag tragen („gemessen am 12.08.2026").

### B2.2 „Die Erzeugen-Kette hat drei Transaktionen; Dezimieren fehlt — D1 offen"

**Urteil: überholt.**

*Beleg:*
- `app/core/generate.py:234–248`: nach *Auf Arbeitsgröße bringen* und
  *Reparaturkette* folgt bedingt eine vierte Transaktion *Auf
  Arbeitsauflösung bringen* (`op="decimate_mesh"`), sobald
  `result.mesh.triangle_count > GENERATED_TRIANGLE_LIMIT` (500 000);
  Ziel ist `GENERATED_TRIANGLE_TARGET` = 200 000
  (`app/core/generate.py:68` und `:73`).
- Test: `tests/test_way_three.py:265`
  `test_a_generated_mesh_arrives_workable` — „assert
  len(generation.transactions) == 3, 'Laden, Reparieren, Dezimieren'".
- Commit `da6e821` (12.08.2026) „Erzeugt, repariert — und dann konnte niemand
  etwas damit anfangen"; `ROADMAP.md:4678`.

*Was stattdessen dastehen müsste:* „Die Kette hat vier Transaktionen: *Modell
erzeugen* → *Auf Arbeitsgröße bringen* → *Reparaturkette* → *Auf
Arbeitsauflösung bringen*. Der vierte Schritt läuft oberhalb von 500 000
Dreiecken und bringt auf 200 000 — genau die Grenze, an der die
Merkmalserkennung aussteigt. D1 ist umgesetzt."

### B2.3 „Am erzeugten Objekt werden 0 Merkmale erkannt; `perceive` winkt oberhalb einer Größengrenze ab"

**Urteil: überholt** (Mechanik stimmt, Ergebnis nicht mehr).

*Beleg:*
- Grenze: `app/core/scene/evaluate.py:72` `FEATURE_LIMIT_TRIANGLES = 200_000`,
  Prüfung `:394`, Meldung `:399` „Für die Merkmalserkennung ist dieses Modell
  zu groß."
- Nachgerechnet: `decimate(mesh, 200_000)` auf eine Icosphäre mit 1 310 720
  Dreiecken liefert exakt 200 000 — die Prüfung ist `>`, also greift die
  Merkmalserkennung danach. Kommando:
  `.venv/Scripts/python.exe -c "…decimate(MeshData(raw=icosphere(8)),
  GENERATED_TRIANGLE_TARGET)…"` → `vorher 1310720 -> nachher 200000 |
  Merkmalsgrenze 200000 | unter Grenze: True`.

*Was stattdessen dastehen müsste:* „Ein erzeugtes Netz kam mit anderthalb
Millionen Dreiecken und damit ohne Merkmale in die Szene. Seit dem 12.08.
dezimiert die Kette selbst auf 200 000 — die Zahl, an der
`FEATURE_LIMIT_TRIANGLES` steht. Die Sackgasse ist zu."

---

## Teil 3 — Lizenzen

### B3.1 „`image_to_mesh.json` setzt `\"model\": \"RMBG-2.0\"`"

**Urteil: überholt.**

*Beleg:*
- `app/core/backends/data/image_to_mesh.json:13` steht heute
  `"model": "INSPYRENET"`; dasselbe in `text_to_mesh.json:56`.
- Commit `7d80045` (12.08.2026) „Das voreingestellte Freistellmodell durfte
  nicht verkauft werden".
- Absicherung: `tests/test_backends.py:505`
  `NON_COMMERCIAL_MODELS = ("RMBG-2.0", "rmbg-2.0", "BEN2")` und
  `:507 test_the_shipped_graphs_name_no_non_commercial_model` — kein
  mitgelieferter Graph darf ein nicht-kommerzielles Modell nennen.
- `ROADMAP.md:4671`.

*Was stattdessen dastehen müsste:* „Der Graph setzte `RMBG-2.0` (CC BY-NC 4.0)
als Vorgabe. Seit dem 12.08. steht dort `INSPYRENET` (MIT); ein Test hält
fest, dass kein mitgelieferter Graph ein nicht-kommerzielles Modell nennen
darf."

### B3.2 „Vorschlag L1 offen — zwei Zeichenketten tauschen"

**Urteil: überholt, aber nur zur Hälfte — und die andere Hälfte wurde
bewusst nicht gemacht.**

*Beleg:*
- Freistellen: getauscht (siehe B3.1).
- Formkern: **nicht** getauscht, mit Begründung. Der Graph nennt weiterhin
  `Hy3D*`-Knoten (`image_to_mesh.json:25,36,42,56,67`) und die Rolle
  `"{model:shape}"` (`:27`). `ROADMAP.md:4674` „**Hunyuan3D bleibt, mit einem
  Satz dazu.**" — ein Wechsel auf Step1X-3D oder TripoSG braucht eine andere
  Knotensammlung in ComfyUI, Solidon liefert keine Gewichte.
- Der Satz steht jetzt an drei Stellen: Modulkopf
  `app/core/backends/mesh.py` (Zeilen 24 f.), Handbuch
  `app/core/manual.py:843`, Website `website/handbuch.html:407`.

*Was stattdessen dastehen müsste:* „L1 ist zur Hälfte umgesetzt: das
Freistellmodell ist getauscht, der Formkern nicht. Hunyuan3D bleibt, weil ein
Wechsel eine andere ComfyUI-Knotensammlung verlangt; stattdessen sagen
Modulkopf, Handbuch und Website, dass die Lizenz für die EU nicht gilt und
welche Modelle frei sind."

### B3.3 „`MODEL_ROLES` erlaubt den Rollentausch ohne Python-Änderung"

**Urteil: stimmt.** `app/core/backends/mesh.py:107` mit den Rollen `image`,
`shape`, `shape_vae`; aufgelöst in `:344`. Der Platzhalter `{model:shape}`
steht im Graphen (`image_to_mesh.json:27`).

---

## Teil 4 — ComfyUI

### B4.1 „Ein zweiter Backend gegen fal.ai passt ins `MeshBackend`-Protokoll — B1 nicht gebaut"

**Urteil: stimmt** (weiterhin offen).

*Beleg:* `app/core/backends/mesh.py:151` `class MeshBackend(Protocol)`, dazu
zwei Umsetzungen: `:254 ComfyBackend`, `:513 ScriptedMeshBackend`. Kein
Treffer für `fal` in `app/` (`grep -rn "fal\.ai\|fal_ai\|falai" app/` leer),
kein Eintrag in `ROADMAP.md`.

*Anmerkung:* B1 ist damit der **einzige** Vorschlag dieses Papiers, der offen
geblieben ist — und der einzige, den die ROADMAP nicht führt. Das gehört als
Satz ins Papier, sonst verschwindet er.

---

## Teil 5 — Lokaler Agent

### B5.1 „96 Werkzeuge (85 Ops + 11 eigene), Schema 110 KB, höchstens acht Schritte"

**Urteil: stimmt, auf den Punkt.**

*Beleg, nachgezählt am 19.08.2026:*
```
.venv/Scripts/python.exe -c "from app.core.bootstrap import load_operations;
 from app.core.agent.tools import tool_schemas; load_operations();
 s=tool_schemas(); print(len(s))"
→ 96
Schemagröße (json.dumps, ensure_ascii=False): 112 852 Zeichen = 110,2 KB
Kompakt: 88 942 Zeichen = 86,9 KB
```
Operationen: 85 (`len(REGISTRY.all())`). Zusatzwerkzeuge: 11
(`app/core/agent/tools.py:56 EXTRA_TOOLS`), Namen stimmen eins zu eins mit der
Aufzählung im Papier. Schrittgrenze: `app/core/agent/session.py:78
MAX_STEPS = 8`.

### B5.2 „Gemessen wurde bei 88 Werkzeugen und 104 KB"

**Urteil: stimmt** als historische Angabe. Das Papier trägt seit `c3f4c13`
(18.08.) beides — Messlage und heutigen Bestand. Genau so soll es sein; die
Stelle ist vorbildlich und braucht keine Änderung.

### B5.3 „qwen3:14b: 4/5 strukturiert, 3/5 richtig … Urteil: ‚Brauchbar: keines.'"

**Urteil: unprüfbar** — Ollama antwortet auf `http://localhost:11434/api/tags`
nicht, `tools/check_local_model.py` ist nicht nachfahrbar. Die Zahlen leben
weiter im Code: `app/core/backends/llm.py:325–336` (Modellwahl) und `:613`
(„gegen die 88 Werkzeuge dieser Anwendung").

*Ein Widerspruch, der auffällt:* Das Urteil „Brauchbar: keines" steht neben
`app/core/backends/llm.py:337 DEFAULT_OLLAMA_MODEL = "qwen3:14b"` — dasselbe
Modell ist die Vorgabe der Anwendung, und `local_model_expectation()` verkauft
es als „für kurze Anweisungen reicht das". Das Papier sollte das Urteil
schärfen: nicht „brauchbar: keines", sondern „für lange Züge brauchbar:
keines".

*Kleiner Bezugsfehler nebenbei:* `llm.py:613` sagt weiterhin „gegen die 88
Werkzeuge dieser Anwendung" — das ist der Bestand vom 12.08., nicht der
heutige (96). Betrifft den Code, nicht das Papier.

### B5.4 „A1 und A2 sind offen"

**Urteil: überholt — beide erledigt, A1 anders als vorgeschlagen.**

*Beleg:*
- Commit `6a3b5ad` (12.08.2026) „Neunundneunzig Kilobyte Schema für ein
  Modell mit kleinem Fenster".
- **A2:** `app/core/backends/llm.py:605 local_model_expectation()` liefert die
  gemessenen Zahlen; gezeigt wird der Satz an der Chatleiste,
  `app/ui/main_window.py:3032`. `ROADMAP.md:4685`.
- **A1 fiel anders aus:** Nicht gefiltert, sondern gekürzt.
  `app/core/agent/session.py:194`
  `tools = list(tool_schemas(self.registry, compact=self.backend.id == "ollama"))`.
  Die Begründung steht in `app/core/agent/tools.py:75–82`: *„``compact`` kürzt
  die Beschreibungen, **ohne ein Werkzeug wegzulassen**. … eine Auswahl, die
  Operationen aussortiert, wäre eine Betriebsart mit anderem Namen (§2.6)."*
  `ROADMAP.md:4681`: „nach `applies_to` zu filtern wäre eine Betriebsart mit
  anderem Namen gewesen."
- Wirkung heute nachgemessen: 110,2 KB → 86,9 KB, alle 96 Werkzeuge bleiben.

*Was stattdessen dastehen müsste:* „A2 ist umgesetzt: der gemessene Satz steht
an der Chatleiste. A1 ist umgesetzt, aber nicht wie vorgeschlagen — nach
`applies_to` zu filtern wäre eine Betriebsart mit anderem Namen gewesen (§2.6).
Gekürzt wurden stattdessen die Beschreibungen: 110 KB → 87 KB, kein Werkzeug
fällt weg. Der größte Posten waren nicht die Operationstexte, sondern die
Parametertexte."

*Folge, wenn man es nicht weiß:* Wer A1 heute so umsetzt, wie es im Papier
steht, baut die Betriebsart ein, die der Bauplan §2.6 verbietet — und die
Begründung dagegen steht nur im Code und in der ROADMAP.

---

## Teil 6 — Anschlussfähigkeit

### B6.1 „Solidon liest GLB seit jeher und schreibt es seit heute"

**Urteil: überholt** (die Zeitangabe, nicht die Sache).

*Beleg:* GLB-Schreiben seit Commit `d4dea28` vom **11.08.2026** („GLB kam
herein und ging nicht hinaus") — also schon einen Tag vor dem Dokumentdatum.
`app/core/export/writer.py:54` führt `glb` in `ExportFormat`, `:665
_glb_bytes`. Tests: `tests/test_export.py:196` (parametrisiert über glb),
`:206 test_glb_keeps_the_measurements_it_was_given`,
`:220 test_glb_carries_the_slot_colours`.

*M1 selbst ist überholt:* `ROADMAP.md:4688` „Anschluss statt Wettlauf" ist
abgehakt, und die Umsetzung ging weiter als vorgeschlagen — es gibt eine
eigene Seite `website/ki-modelle.html` („Wenn das Modell aus einer KI kommt",
zuletzt `acd0ba0` vom 18.08.).

*Was stattdessen dastehen müsste:* „Solidon liest GLB seit jeher und schreibt
es seit dem 11.08.2026. Der Satz für die Website steht seit dem 12.08. auf
`website/ki-modelle.html`."

---

## Teil 7 — Oberfläche

### B7.1 Oberflächenzählungen

**Urteil: gemischt.** Nachgezählt am 19.08.2026 gegen ein offscreen gebautes
`MainWindow(Session(), UiSettings())`:

| Behauptung | heute | Urteil |
|---|---|---|
| acht Beispielkacheln | **neun** | überholt |
| neun Menüs | neun (Datei, Bearbeiten, Objekt, Erzeugen, Ändern, Bausteine, Vorbereiten, Ansicht, Hilfe) | stimmt |
| sechs Werkzeuge in der Zeile | **acht** (section, measure, transform, analysis, layers, explode, split, paint) | **falsch** — am 12.08. waren es schon sieben |
| links drei einklappbare Abschnitte | drei (Objektbaum, Parameter, Verlauf) | stimmt |
| Dialog vorn sechs Werte | dialogabhängig | unprüfbar |
| Musterdialog-Zweisprachigkeit behoben | behoben und abgesichert | stimmt |

*Belege:*
- Beispiele: `len(app.core.examples.EXAMPLES)` → 9. Am Dokumentstand
  (`git show 82b946d:app/core/examples.py`) waren es 8; hinzugekommen ist
  `weg4-figur-formen` mit Commit `5a9418c` (14.08.2026). Nebenbei: der
  Docstring `app/ui/start_screen.py:474` sagt weiterhin „acht Beispiele" und
  ist damit selbst veraltet.
- Menüs: `w.menuBar().actions()` → 9.
- Werkzeugzeile: `w.findChildren(ToolStrip)[0].tools()` → 8 Schlüssel. Am
  Dokumentstand: `git show 82b946d:app/ui/main_window.py | grep -A2
  "self.tools.add(" | grep -o '"[a-z_]*"'` → 7 (ohne `split`). Die Zahl sechs
  war also schon damals zu klein.
- Abschnitte: `app/ui/panels.py:3` „Drei einklappbare Abschnitte … Objektbaum,
  Parameter, Verlauf"; `:1545 collapsible(...)`.
- Auswahlwerte: `tests/test_translations.py:276` prüft, dass jeder
  Auswahlwert über `choice_label()` übersetzt ist oder sich selbst benennt.

### B7.2 „Bei 3413 px zerfällt das Verhältnis"

**Urteil: überholt.**

*Beleg:* Commit `f48a7e3` (12.08.2026) „Auf 3413 Pixeln war die linke Karte
ein Zwölftel des Fensters" — `app/ui/overlay.py` und `tests/test_ui.py`.
`ROADMAP.md:4691`: „**Karten wachsen mit breiten Fenstern**, anteilig und mit
Deckel." Unter etwa 2000 px ändert sich nichts, darüber wachsen die Karten bis
420 bzw. 460 px. Dazu `7fd9303` (15.08.): die Anwendung startet
bildschirmfüllend statt auf 1280 × 820.

*Was stattdessen dastehen müsste:* „Die Karten wachsen anteilig mit dem
Fenster, mit Deckel bei 420 bzw. 460 px; unter 2000 px ändert sich nichts. Der
Befund von 3413 px ist erledigt (12.08.)."

---

## Teil 8 — Handbuch

### B8.1 „35 Seiten, 19.578 Wörter, zwanzig geschrieben"

**Urteil: überholt.**

*Beleg, nachgezählt am 19.08.2026:*
```
.venv/Scripts/python.exe -c "from app.core.bootstrap import load_operations;
 from app.core import manual; load_operations(); ps = manual.pages(); …"
→ Seiten 40 | geschrieben 21 | erzeugt 19 | Wörter 24 889
```
(Die Wortzahl zählt die Rohtexte der Seiten; `tools/make_manual.py` kommt je
nach Zählweise auf einen etwas anderen Wert — die Seitenzahl ist die harte
Zahl.)

*Was stattdessen dastehen müsste:* „Unser Handbuch hat 40 Seiten: 21
geschriebene und 19 erzeugte."

### B8.2 „Fernsteuerungsseite und Operationsreferenz sind unverbunden (H1 offen)"

**Urteil: überholt — und übererfüllt.**

*Beleg:*
- Der vorgeschlagene Absatz steht: `app/core/manual.py:921–927`, Seite
  *Fernsteuerung*: „**Welche Werkzeuge es gibt, steht in diesem Handbuch.**
  Jede Operation der folgenden Kapitel ist eines … Eine eigene
  Schnittstellenliste gibt es deshalb nicht."
- Darüber hinaus gibt es eine **erzeugte** Seite: `app/core/manual.py:1383`
  `Page(key="remote-tools", title=_("Die Werkzeuge der Fernsteuerung"),
  body=remote_text(), generated=True)`, gebaut aus
  `app/core/agent/remote.remote_tools()` — heute **94 Einträge** (96 minus
  `create_from_scad` und `ask_user`, die nicht durch die Leitung gehen,
  `DENIED` in `app/core/agent/remote.py`).
- `ROADMAP.md:4688–4690`.

*Was stattdessen dastehen müsste:* „Die Lücke ist zu: die Fernsteuerungsseite
verweist auf die Registerkapitel, und eine erzeugte Seite *Die Werkzeuge der
Fernsteuerung* listet alle 94 erreichbaren Werkzeuge. Zwei Werkzeuge gehen
absichtlich nicht durch die Leitung."

*Der Satz im Papier, der heute falsch ist:* „Wer Solidon fernsteuern will,
findet nirgends ‚diese 88 Werkzeuge gibt es, mit diesen Parametern'."

---

## Teil 9 — Die Arbeitsliste

| Punkt | Stand am 19.08.2026 |
|---|---|
| 1. Viewport-Befund verfolgen | hinfällig — Messartefakt, `ROADMAP.md:4697` |
| 2. L1 Zeichenketten tauschen | halb erledigt, halb bewusst verworfen, `ROADMAP.md:4671/4674` |
| 3. D1 Dezimieren | erledigt, `app/core/generate.py:234` |
| 4. A1/A2 | erledigt, A1 anders (kompakt statt gefiltert), `app/core/agent/session.py:194` |
| 5. M1 und H1 | erledigt, `website/ki-modelle.html`, `app/core/manual.py:1383` |
| 6. Linke Spalte auf breiten Bildschirmen | erledigt, `f48a7e3` |
| (B1 fal.ai) | **offen**, in keiner Liste geführt |

---

## Was am Dokument zu tun wäre

1. **Kopfzeile mit Stand und Erledigungsvermerk** — ein Kasten unter der
   Überschrift, der auf `ROADMAP.md:4663` zeigt.
2. **Teil 1 umschreiben.** Der Befund war ein Messartefakt; die Lehre daraus
   (Prüfskripte mit `processEvents()` messen ein OpenGL-Fenster nicht) ist
   wertvoller als der behauptete Fehler.
3. **Teil 5, Vorschlag A1 korrigieren.** In der jetzigen Form ist er eine
   Anleitung zu einem Regelverstoß gegen §2.6.
4. **Teil 9 durch eine Statustabelle ersetzen**, mit B1 als einzigem offenen
   Punkt.
5. **Zählwerte in Teil 7 und 8 nachziehen** (neun Kacheln, acht Werkzeuge, 40
   Seiten) oder mit Messdatum versehen.
