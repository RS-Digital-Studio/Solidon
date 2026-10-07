# „Merkmal verschieben" mit Maßen — welche Arten haben die Felder, welche nicht, und warum

Kundenrückmeldung zu 0.5.3 (S-20261006-5be329): „das Verschieben mit Maßen bei
Bohrungen ist gut, bei anderen Merkmalen fehlen sie". Nur gelesen und gemessen,
im Repository nichts geändert.

## Kurzfassung

- **Die X/Y/Z-Felder fehlen nirgends aus Datenmangel.** Alle 734 erkannten
  Merkmale aus sieben Modellen tragen `centre`, und `x/y/z` lesen genau daraus
  (`actions.py:367-370`). Wo die Zeile *Merkmal verschieben* steht, stehen
  auch die drei Felder mit dem gemessenen Ort.
- **Die Zeile fehlt, wo `move_feature` nicht gilt** — und das Panel blendet
  jede nicht geltende Handlung seit `fad4a15c5` (15.09.2026) **samt Grund**
  aus. Am Kundenmodell haben 16 von 190 Merkmalen die Zeile, 174 nicht:
  117 Verrundungen, 42 Flächen (davon 6 Schrägflächen), 9 gerundete Seiten,
  6 Sackbohrungen mit Zapfen darin.
- **Die Flächen sind der Kern der Rückmeldung.** Im Verlauf des Kunden stehen
  drei *Fläche versetzen* am Stift mit −22,11372262396192, −19,71390184533827
  und −68,85665912145475 mm — ungerundet, also gezogen. Der Flächengriff legt
  den Schritt sofort an (`main_window.py:15030`), ohne Zahlenfeld und ohne
  *Übernehmen*; an einer Bohrung schlägt derselbe Zug nur vor, und die Zahl
  steht rechts. Das ist „Verschieben mit Maßen" gegen „Verschieben ohne".
- **Zwei Widersprüche zwischen Feld und Rechnung:** Wulst und Kehle tragen
  X/Y/Z, aber `move_feature` sagt an 4 von 4 geprüften Ringen ab. Die
  Sackbohrungen mit Zapfen (die „Taschen" im Kundenmodell) sind im Panel
  gesperrt, die Operation rechnet dort aber.
- **Zweite Deutung:** Maße *im Bild* (Maßgruppe mit Kantenabständen) gibt es
  nur an Bohrung und Langloch — über *Bohrung ändern* bzw. *Zum Langloch
  ziehen* (`LEADS_INTO_THE_VIEW`, `panels.py:7419`). Zapfen, Senkung,
  Verjüngung, Wulst, Kugel und Einschluss haben nur Griff und Felder rechts.
  Bewusste Entscheidung (Robert, 10.09.2026), aber genau der Unterschied, den
  ein Kunde „mit Maßen" nennen würde.

## Messaufbau

- Stand: `git archive` von HEAD `3a5d607f3` in den Zustandsordner
  (`head_tree/`, plus das ungetrackte `_chain…pyd`). `actions.py`,
  `prepare_ops.py` und `panels.py` sind dort identisch mit `v0.5.3`
  (`git diff --stat v0.5.3 HEAD` zeigt nur sechs Zeilen in `main_window.py`).
  Der Arbeitsbaum ließ sich nicht verwenden: Eine andere Sitzung hatte
  `selection_operations.py` gerade halb bearbeitet (`NameError: PaletteEntry`
  beim Fensterbau).
- Fenstersonde `probe_panel.py` (offscreen, APPDATA/LOCALAPPDATA in Temp,
  `RecordingRenderer` aus `tests/render_fakes.py` für die Maßgruppe):
  Projekt/Modell öffnen, warten bis Erkennung stabil, je Merkmal
  `panels.feature_answers` (derselbe Weg wie das Panel), dann je Art und
  Unterart ein Merkmal über `object_tree.select_feature` wählen und die
  gebaute Karte lesen (Zeilen, Felder, sichtbar/gesperrt, Maßgruppe, Griff),
  zuletzt `move_feature` am Kern mit 0,5 mm in +X (ohne Verlauf), Volumen,
  Dichtheit, Befunde und Neuerkennung am Ergebnis; zum Vergleich
  `push_face` 0,5 mm an jeder Flächenprobe.
- Gezielte Nachproben `probe_core.py` (andere Versätze an Zapfen, Tasche,
  Verjüngung), `probe_card.py` (Auswahlkarte an einer Fläche).
- Modelle: Kundensitzung `sitzung.p3d` (BroomHolder 127 688 Dreiecke,
  184 Merkmale; Stift 544 Dreiecke, 6 Merkmale), `mini-pot-x1.stl`,
  `Wedge-Lock (Base).stl` (Langloch), `large-screwdriver-holder-with-honeycomb-pattern.stl`
  (Muster), `garden-hose-holder.3mf` (Lufteinschlüsse, Kehle),
  `pegboard-gs-100-v2.step` (exakter Kern), `tests/data/threads/m10_rechts.step`
  (Gewinde).
- Die Maschine trug währenddessen rund 60 fremde Python-Prozesse; Zeiten
  sind deshalb nicht repräsentativ.

## Tabelle je Merkmalsart

Spalten: Anzahl im Kundenmodell / in allen sieben Modellen; Zeile *Merkmal
verschieben* in der Karte; Felder; Grund, falls nicht; ob `move_feature` am
Kern rechnet (0,5 mm, sonst angegeben).

| Art (Unterart) | Kunde / gesamt | Zeile | X/Y/Z | Grund, falls nicht | rechnet `move_feature`? |
|---|---|---|---|---|---|
| Bohrung, durchgehend | 3 / 14 | ja | ja, gemessener Ort; dazu Maßgruppe im Bild (`resize_hole`) | – | ja; ΔV 0,000 mm³ (BroomHolder, Wabenhalter, pegboard exakt), Kette mit Senkung reist mit, am Ziel wiedererkannt |
| Sackbohrung, frei | 0 / 7 | ja | ja, plus Maßgruppe | – | ja (pegboard −0,86 mm³; mini-pot `bore.over_the_edge`) |
| Sackbohrung mit Zapfen darin („Tasche um Zapfen") | 6 / 6 | nein, ausgeblendet; Satz `HOLE_IS_NOT_EMPTY` als Notiz | – | `no_own_body` → `hole_is_clear` (`actions.py:1050-1057`) | **ja** — 0,2 mm: −0,044 mm³, Loch am Ziel wiedererkannt; 0,5 mm: −0,096 mm³, danach zwei Sackbohrungen weniger erkannt. **Widerspruch Panel ↔ Operation** |
| Langloch | 0 / 1 | ja | ja, plus Maßgruppe (`slot_hole`) | – | ja, ΔV 0,000, wiedererkannt |
| Zapfen | 7 / 8 | ja | ja; keine Maßgruppe | – | rechnet; Ergebnis teils falsch, siehe Nebenbefunde |
| Senkung | 2 / 17 | ja (13), grau (4) | ja; keine Maßgruppe | grau: `NO_BODY_FROM_FACES` (mini-pot), `NO_OWN_BODY` (pegboard) | ja, ΔV 0,000 (gemeinsam mit der Bohrung) |
| Verjüngung | 2 / 5 | ja | ja; keine Maßgruppe | – | rechnet; Stift-Endfase +2 218 mm³ bei 0,2 mm (unplausibel) |
| Kegelfläche (Kegelstück) | 0 / 95 | nein | – | `CONE_PIECE_HAS_NO_BODY` (`actions.py:1203`) | nein, Absage mit demselben Satz |
| Pfanne/Kuppel | 0 / 3 | 1 ja, 2 nein | ja, wo Zeile | `NO_BODY_FROM_FACES` | geprüfte Pfanne: nein, Absage; die mit Zeile nicht gefahren |
| Wulst / Kehle | 2 / 5 | ja | ja | – | **nein** — Netz: `TORUS_NOT_SEPARABLE` (BroomHolder, mini-pot, Schlauchhalter), exakt: `GeometryError` „konnte die neue Wand nicht … schließen" (pegboard). **Felder ohne Wirkung** |
| Lufteinschluss | 0 / 8 | ja | ja | – | ja, ΔV 0,000, wiedererkannt |
| Fläche (achsparallel, innen) | 36 / 128 | nein | – | `NOT_APPLICABLE["face"]` (`actions.py:252-257`); der Weg ist *Fläche versetzen* | Absage; `push_face` rechnet (ΔV = Fläche × 0,5 mm in jeder Probe) |
| Schrägfläche | 6 / 56 | nein | – | dito | dito |
| Verrundung (Kante) | 117 / 358 | nein | – | `NOT_APPLICABLE["fillet"]` (`actions.py:269-273`) | nein, Absage |
| Runde Wand | 0 / 2 | nein | – | `ROUND_WALL_HAS_NO_PLACE` | nein |
| Gerundete Seite | 9 / 19 | nein | – | `NOT_APPLICABLE["curved_face"]` (`actions.py:258-263`) | nein, Absage |
| Muster | 0 / 1 | nein | – | `NOT_APPLICABLE["pattern"]` (`actions.py:264-268`) | nein, Absage |
| Gewinde | 0 / 1 | nein | – | `THREAD_STAYS_WHERE_IT_IS` (`actions.py:168-171, 208`) | nein, Absage |
| Offene Kante | 0 / 0 | nein | – | `NOT_APPLICABLE["edge_loop"]` | nicht gefahren (kein Fall im Korpus) |

Summe aller sieben Modelle: 734 Merkmale, 0 ohne `centre`, 62 mit X/Y/Z.
Kundenmodell: 16 von 190 mit Feldern, davon 2 (Wulst) ohne Wirkung.

„Taschen" im Kundenbaum sind zwei funktionale Gruppen *Tasche mit offenem
Rand* (13 Merkmale: 11 Verrundungen, 2 Innenflächen). Für eine Gruppe gibt es
nur *Kammer ändern*, und das sagt hier ab („Rand oder Wände dieser Tasche sind
durchbrochen …"), wird also ebenfalls ausgeblendet. Ein *Tasche verschieben*
gibt es nicht.

## Warum die Felder fehlen — die verantwortlichen Stellen

Zeilennummern: `app/core/...` gilt für HEAD und Arbeitsbaum gleich (dort
unverändert); `app/ui/...` nach HEAD `3a5d607f3`.

1. **Schema — nicht die Ursache.** `MoveFeatureParams` führt `x`, `y`, `z`
   vorn für jede Art (`prepare_ops.py:3645-3684`).
2. **Wertequelle — nicht die Ursache.** `_FROM_FEATURE` liest `x/y/z` aus
   `centre` (`actions.py:367-370`), `_carried_by` lässt sie stehen, sobald
   `centre` da ist (`actions.py:641-657`). Jede Erkennung beider Kerne setzt
   `centre` (gemessen 734/734).
3. **Register — die Hauptursache.** `move_feature.applies_to =
   MOVABLE_KINDS = ("hole", "pin", "cone", "sphere", "void", "slot", "torus")`
   (`prepare_ops.py:829`, `4443`). Für jede andere Art liefert `actions_for`
   die Zeile mit `op=None` und dem Satz aus `NOT_APPLICABLE` /
   `NOT_APPLICABLE_HERE` (`actions.py:755`, `843-854`, `_no_way` `1411-1417`).
4. **Je Merkmal gesperrt.** Auch bei einer erlaubten Art wird die Zeile grau:
   `cone_piece_blocked` (`actions.py:1203`), `torus_is_the_body` (`224`),
   `no_own_body` mit `HOLE_IS_NOT_EMPTY`, `NO_BODY_FROM_FACES`, `NO_OWN_BODY`
   (`1017-1082`), angewandt in `actions_for` (`759-771`).
5. **Darstellung — warum der Kunde nicht einmal den Grund liest.**
   `FeaturePanel._show_feature_rows` überspringt jede Zeile mit `op=None`
   (`panels.py:8907-8910`); nur an Bohrung, Langloch und Kegel ohne jede
   Handlung steht der Satz einmal als Notiz (`8925-8929`). Eingeführt mit
   `fad4a15c5` („unpassende Aktionen ausblenden"), gehalten von
   `tests/test_feature_panel.py:1899` (`test_a_handling_that_does_not_apply_is_hidden`).
6. **Fläche: Zug ohne Zahl.** `_on_face_dragged` legt `push_face` sofort als
   Schritt an (`main_window.py:15030-15060`); der Merkmalszug dagegen schlägt
   nur vor und füllt die Felder (`_on_feature_move_proposed`,
   `main_window.py:14620-14640`, Robert 11.09.2026). Eine Zahl gibt es an der
   Fläche nur während des Zugs im Ziehwertband (`viewport.py:16200-16218`) und
   über den Kartenknopf *Fläche versetzen*, der einen Dialog mit „Weg"
   (Vorgabe 2 mm) öffnet (`probe_card.py`: Knopf sichtbar und frei).
7. **Maße im Bild** nur über `LEADS_INTO_THE_VIEW = {"slot_hole",
   "resize_hole"}` (`panels.py:7419`); `request_in_view` nimmt die erste
   Handlung mit diesem Weg (`main_window.py:17804`). `move_feature` könnte
   es technisch (`placement.supports_surface_placement` → `True`, gemessen).

## Bewusste Entscheidungen mit Beleg

| Was | Beleg |
|---|---|
| Verrundung nicht versetzbar („gehört zu ihrer Kante") | `actions.py:269-273`; Panel-Kommentar zu `_folded` |
| Fläche nicht über *Merkmal verschieben*, sondern *Fläche versetzen* | `actions.py:252-257`; `tests/test_feature_panel.py:2016` verlangt an der Fläche „alle `op is None`" |
| Gewinde wird nicht bewegt | `actions.py:165-171`, `208`; `operationen.md` „ein Gewinde wird nicht bewegt" |
| Muster bleibt auf seiner Fläche | `actions.py:264-268` |
| Lufteinschluss versetzbar, nicht verdoppelbar (Robert 10.09.2026) | `prepare_ops.py:809-840`; `tests/test_features.py:4244` (`offered == {"move_feature", "remove_feature"}`); `schichtanalyse.md` |
| Wulst/Kehle tragen alle fünf Handlungen (P2.6) | `actions.py:279-283`; `tests/test_features.py:2468` — nur an Kennzahlen, nicht am Netz |
| Nicht geltende Handlungen werden ausgeblendet | Commit `fad4a15c5`; `konzepte/begruendungen/karte-app-ui.md:1079`; `tests/test_feature_panel.py:1899`. **Widerspricht** `app/core/perceive/CLAUDE.md:172` („Was nicht gilt, steht trotzdem da") und `fenster.md` („`_folded` macht aus gleich begründeten Absagen eine Zeile") — das Zusammenlegen ist im Panel heute wirkungslos |
| Verschieben/Verdoppeln führen nicht ins Bild, sondern rechnen auf Klick (Robert 10.09.2026) | Docstring `LEADS_INTO_THE_VIEW`, `panels.py:7411-7419` |
| Flächenzug wird sofort ein Schritt | Docstring `_on_face_dragged`; `tests/test_ui.py:13580` (`test_dragging_a_face_reaches_the_document`) |

Einen Roadmap-Punkt, der das Fehlen der Felder an diesen Arten festhält,
gibt es nicht (`ROADMAP.md` durchsucht nach `move_feature`, „verschieben",
„versetzen").

## Nebenbefunde

1. **Wulst/Kehle: Felder, die nichts tun.** Panel fragt nur `torus_is_the_body`
   (alle Dreiecke = Ring); die Operation prüft in `_torus_rims`
   (`prepare_ops.py:14707-14768`) zwei gleiche, ebene Randringe und sagt
   sonst `TORUS_NOT_SEPARABLE`. Ergebnis an allen vier Probe-Ringen: X/Y/Z
   stehen, *Übernehmen* endet mit Absage. Der Anschlusstest
   `test_the_operation_refuses_exactly_what_the_panel_greys_out`
   (`tests/test_features.py:2421`) prüft nur je Art mit Kunstmerkmal, nicht
   je Merkmal am Netz.
2. **Sackbohrung mit Zapfen: umgekehrt.** `_tool_for` lässt `HOLE_IS_NOT_EMPTY`
   durch, wenn `_air_of_the_bore` einen Körper liefert
   (`prepare_ops.py:2681-2700`, `2812`) — gebaut für die Haltelippe einer
   Magnettasche (BOHRUNG-13), greift aber auch beim „Topf mit Zapfen", den
   `HOLE_IS_NOT_EMPTY` ausdrücklich meint. Panel sperrt, Chat/CLI/Griff rechnen.
3. **Griff an Merkmalen ohne Zeile.** `gizmo_feature` fragt nur die Art
   (`viewport.py:14147`). An gesperrten Merkmalen erlaubter Art (Tasche um
   Zapfen, Kegelstück, Pfanne ohne Körper) hängt ein Verschiebegriff; ein Zug
   endet in `take_values` → `False` und der Ansage „Die neue Stelle steht
   rechts unter Auswahl." (`main_window.py:14638`) — dort steht nichts. An
   Verrundung und gerundeter Seite sitzt der Griff am **Körper**; ein Zug
   bewegt den ganzen Körper, obwohl ein Merkmal gewählt ist.
4. **Rechnet, aber Ergebnis falsch, ohne Befund** (an `solidon3d-geometrie`):
   - BroomHolder `pin_1` (Ø 5,44 in Tasche Ø 6,12): 0,2 mm → ΔV 0,000,
     wiedererkannt. 0,5 mm (in die Taschenwand) → **−189,25 mm³**, danach
     4 statt 6 Zapfen erkannt, keiner am Ziel, kein Befund.
   - mini-pot `pin_1` (Ø 30): ΔV **+240,65 mm³** bei 0,2 / 0,5 / 1,0 mm
     gleich, bei 5 mm +2 129,5 mm³; nach dem Versatz in X kein Zapfen mehr
     erkannt.
   - Stift `cone_3` (Endfase, „Verjüngung" Ø 33,8): 0,2 mm → **+2 218 mm³**.
   - Kunde-Stift `hole_12` 0,5 mm: +4,75 mm³ (Mündung läuft in die 5-mm-Fase,
     plausibel).
5. **Wartezeit im Panel** am BroomHolder (Weg über `_FeatureAnswersWorker`
   ab 20 000 Dreiecken): 23,7 s bis zu den Handlungen an `hole_1`, 10,5 s an
   `cone_1`, im ersten Lauf nach 10 s noch „Die Handlungen werden ermittelt …".
   Gemessen unter Fremdlast — nachmessen, bevor daraus ein Punkt wird.

## Umsetzungsvorschlag

Ziel: An jeder Art, an der Verschieben **rechnet**, steht dieselbe Zeile mit
Zahlenfeldern wie an der Bohrung — und nur dort. Gemessen gilt das heute
schon für Bohrung, Langloch, Zapfen, Senkung, Verjüngung, Kugel und
Einschluss. Zu tun bleiben drei Dinge.

### 1. Fläche: *Fläche versetzen* als Zeile mit Maßfeld

Größter Hebel: 42 von 190 Merkmalen beim Kunden, und genau der Zug, den er
dreimal gemacht hat.

- `actions.py:138` — erste Zeile `("move_feature", "push_face")`. Die Arten
  überschneiden sich nicht (`push_face` gilt nur `face`, `move_feature` nie),
  die Zeile heißt an der Fläche nach dem Register *Fläche versetzen*.
  In der Sonde (Tupel im Prozess ersetzt) entsteht damit genau ein Feld
  `distance` „Weg"; `reason_against("move_feature", "face")` sagt dann im
  Chat/CLI „Dafür ist „Fläche versetzen“ da." statt des Flächensatzes.
- `actions.py:570` `_value_of` — der Weg beginnt bei **0 mm**, nicht bei der
  Schemavorgabe 2,0 (gemessen: ohne Ausnahme stünde 2,00 mm vorbelegt, ein
  *Übernehmen* versetzte still). Eine kleine Tabelle neben `_SHIFTED_BY`,
  etwa `_STARTS_AT_ZERO = frozenset({("push_face", "distance")})`,
  `measurement=None`, weil nichts gemessen ist.
- `main_window.py:15030` `_on_face_dragged` — der Zug schlägt vor wie am
  Merkmal: `feature_panel.take_values("push_face", {"distance": d})`, die
  Vorschau läuft, *Übernehmen* rechnet; nur wenn `take_values` `False` sagt,
  bleibt der sofortige Schritt. Das ändert die dokumentierte Zusage im
  Docstring und `tests/test_ui.py:13580`.
- Der Kartenknopf *Fläche versetzen* verschwindet dann von selbst
  (`selection_operations._shown_as_fields` liest `ACTION_ORDER`); anpassen:
  `tests/test_selection_operations.py:118`.
- Tests: `tests/test_feature_panel.py:2016` (Vorbedingung „alle `op is None`"
  an der Fläche) umstellen; neu: Fläche zeigt *Fläche versetzen* mit Weg
  0 mm, ein Zug füllt das Feld ohne Schritt, *Übernehmen* schreibt
  `push_face` mit `face` und `distance`; `test_features.py:2421` bleibt grün
  (an der Fläche gilt `push_face`, `move_feature` verweist darauf).
- Unterlagen: `app/core/perceive/CLAUDE.md` (Abschnitt Panel), `fenster.md`
  (Merkmalfenster), `griffe.md` (Flächenzug). Neue Kundentexte braucht es
  nicht; Titel und Feld kommen aus dem Register.

### 2. Feld und Rechnung fragen dieselbe Funktion

- **Wulst/Kehle:** Die Randprüfung aus `_torus_rims` als gemerkte
  Kernfrage herausziehen (z. B. `prepare_ops.torus_refusal(mesh, feature)` →
  `TORUS_IS_THE_BODY` / `TORUS_NOT_SEPARABLE` / `None`) und in `actions_for`
  statt `torus_is_the_body` fragen (`actions.py:721`). Dann steht die Zeile
  grau, wo die Rechnung absagt — an allen vier Probe-Ringen. Der exakte
  Absagefall (Schließen scheitert erst im Defeaturing) ist vorab nicht billig
  zu klären; er bleibt beim Rechnen und gehört als Punkt ins Register.
- **Tasche um Zapfen:** Empfehlung: die Operation folgt dem Panel.
  `_air_of_the_bore` nur zulassen, wo das Material im Zylinder am Rand liegt
  (Lippe), nicht auf der Achse (Zapfen) — eine gemeinsame Funktion für
  `_tool_for` und `no_own_body`. Nur die Luft um einen stehenden Zapfen zu
  versetzen, drückt den Zapfen in die Wand (0,5 mm: zwei Sackbohrungen
  verschwinden aus der Erkennung). Was der Kunde dort vermutlich will —
  Tasche **mit** Zapfen versetzen — ist eine neue Fähigkeit und ein
  eigener Registerpunkt.
- **Griff:** `Viewport.gizmo_feature` hängt den Verschiebegriff nur an ein
  Merkmal, dessen Zeile *Merkmal verschieben* gilt (Antwort des Panels,
  `FeaturePanel.known_answers`), statt nur die Art zu fragen. An gesperrten
  Merkmalen kein toter Zug mehr.
- **Wächter:** ein Anschlusstest über Korpusnetze: Für jedes Merkmal, an dem
  `actions_for` *Merkmal verschieben* anbietet, wirft `move_feature` mit
  kleinem Versatz keine `ValidationError` — und umgekehrt. Heute würde er an
  Wulst/Kehle und an der Tasche um Zapfen rot.

### 3. Wo nichts rechnet: sagen, statt schweigen

Verrundung, gerundete Seite, Muster, Gewinde, Kegelstück, Kugel/Kegel ohne
Körper: Felder ohne Operation wären eine Zusage ohne Wirkung. Empfehlung:
die eine zusammengelegte Absage wieder als Zeile zeigen, so wie `fenster.md`
und `perceive/CLAUDE.md` es noch beschreiben („Verschieben, Drehen und
Verdoppeln — eine Verrundung gehört zu ihrer Kante"). Das nimmt
`fad4a15c5` teilweise zurück und braucht Roberts Entscheidung; bis dahin
widersprechen sich Code und die zwei Unterlagen.

## Offene Fragen an Robert

1. Flächenzug als Vorschlag mit *Übernehmen* statt sofortigem Schritt
   (Vorschlag 1) — ändert eine dokumentierte Zusage.
2. Absagen wieder sichtbar (Vorschlag 3) oder ausgeblendet lassen und die
   zwei Unterlagen angleichen.
3. Maße im Bild auch für Zapfen, Senkung, Verjüngung, Wulst, Kugel und
   Einschluss: `move_feature` in `LEADS_INTO_THE_VIEW` aufnehmen nimmt dem
   Knopf den unmittelbaren Klick (Entscheidung vom 10.09.2026).
4. Tasche um Zapfen: absagen (Empfehlung) oder als Paar versetzen (neuer
   Punkt).

## Dateien

Im Ordner `scratchpad/verschieben/`: `probe_panel.py`, `probe_core.py`,
`probe_card.py`, `scan_kinds.py`, `summarize2.py`; Rohdaten
`sitzung2.jsonl` (Kunde, vollständiger Lauf), `minipot2.jsonl`,
`wedgebase2.jsonl`, `honeycomb2.jsonl`, `hose.jsonl`, `pegboard.jsonl`,
`thread_step.jsonl`, `core_sitzung.jsonl`, `core_minipot.jsonl`, `card.txt`,
`scan.jsonl`; der exportierte Stand liegt in `head_tree/`.
