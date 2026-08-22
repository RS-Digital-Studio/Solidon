# Abgleich: konzept-kundensicht-2026-08.md gegen den Code vom 19.08.2026

**Dokumentstand:** 08.08.2026 (letzter Commit an der Datei: `e6ea3a4`, 08.08.2026 —
„Meine eigene Fortschreibung war schon wieder falsch").
**Abstand:** 295 Commits (`git log --oneline --since=2026-08-09 | wc -l` → 295).
**Geprüft am:** 19.08.2026, Arbeitskopie `main`, Kopf `b0415d6`.

Urteile: **stimmt 3 · überholt 7 · falsch 2 · unprüfbar 3** (15 interne Behauptungen).

Kurzfassung der Lage: Die *Befunde* des Dokuments sind heute alle behoben und die
Behebungen halten — daran ist nichts überholt. Überholt sind fast alle **Zahlen**,
und zwei davon waren schon am 08.08. keine Zählung, sondern eine Fehlzählung. Die
gefährlichste Stelle ist nicht eine einzelne Zahl, sondern **Teil 4**: eine
Arbeitsliste mit sechs Punkten, die der eigene Nachtrag zwanzig Zeilen tiefer
vollständig als erledigt meldet.

---

## 1. „Das Register führt 77 Operationen, alle in Menüs, keine tiefer als zwei Ebenen; 72 mit Dialog, 5 ohne"

*Ort:* Kopf Z. 33–34, 2.7 Z. 294–296, Teil 3 Z. 316–320

**Urteil: überholt.**

Beleg:

```
.venv/Scripts/python.exe -c "from app.core.bootstrap import load_operations;
from app.core.registry import REGISTRY; load_operations(); print(len(REGISTRY.all()))"
→ 85
```

Ohne Dialog (Kriterium ist `spec.params.spec()` leer, siehe
`app/ui/main_window.py:4509` — `if spec.params.spec():`):

```
ohne Dialog: 5  ['delete_object', 'intersect_objects', 'place_on_bed',
                 'subtract_objects', 'union_objects']
mit Dialog: 80
```

Am 09.08. standen 62 `@register_op`-Deklarationen im Kern
(`git grep -c "@register_op" 26883f3 -- app/core/`), heute 69 — die 77 waren also
zum Zeitpunkt der Messung stimmig.

Was weiterhin stimmt: **neun** Menüs, **maximale Tiefe 2** (gezählt über die
gebaute Menüleiste), und jede Operation ist über jede Oberfläche erreichbar —
`tests/test_registry_consistency.py:132`
`test_every_operation_reaches_every_surface` prüft Menü, Palette, CLI,
Werkzeugschemata und Handbuch gegen die Registermenge.

**Im Konzept müsste stehen:** „Das Register führt 85 Operationen, alle in Menüs
erreichbar, keine tiefer als zwei Ebenen. 80 kommen mit Dialog, fünf laufen
sofort (`delete_object`, `union_objects`, `subtract_objects`,
`intersect_objects`, `place_on_bed`)."

---

## 2. „Sechs von 77 Operationen tragen ein Tastenkürzel; 2.7 bleibt als einziger Punkt offen, als Design-Entscheidung"

*Ort:* Kastentabelle Z. 26, 2.7, Nachtrag Z. 442–446

**Urteil: überholt** (Nenner), im Kern aber unverändert richtig.

Beleg: sechs Operationen tragen weiterhin ein Kürzel —
`delete_object Del`, `drill_hole Ctrl+B`, `duplicate_object Ctrl+D`,
`rename_object F2`, `rotate_object Ctrl+R`, `translate_object Ctrl+T`.
Der Nenner ist 85, nicht 77.

Der Punkt ist auch heute offen und als Entscheidung geführt:
`ROADMAP.md:3410` — „**Offen:** die Tastenkürzel. Sechs in der Vorgabe ist eine
Entscheidung und keine Lücke".

Zwei Nebenbemerkungen dazu:

- Die Behauptung im Nachtrag, „Wie Fusion und Onshape" bringe **elf
  Ein-Tasten-Kürzel**, ist **falsch** und war es schon damals:
  `app/ui/shortcut_schemes.py:26–38` führt elf Einträge, davon neun mit einer
  Taste (`E Q F C M R H P S`) und zwei mit Modifikator (`Ctrl+D`, `Ctrl+M`).
  Die Datei ist seit `0ee7132` (04.08.2026) inhaltlich unverändert.
- Das Argument „dort ist die Tastatur der schnelle Weg" lässt die
  **Befehlspalette** aus (`app/ui/command_palette.py`, seit `b3d144e`,
  27.07.2026), die jede Operation über die Tastatur erreichbar macht. Das
  entkräftet den Befund nicht, verschiebt aber seine Schwere.

**Im Konzept müsste stehen:** „Sechs von 85 Operationen tragen ein Kürzel. Neben
ihnen erreicht die Befehlspalette jede Operation über die Tastatur. Die
Fusion-Belegung setzt elf Tasten, davon neun einzelne."

---

## 3. „Neun Menüs mit 127 Einträgen, acht Beispiele auf dem Startbildschirm, sieben Analysekarten, 14 Fehlerklassen"

*Ort:* Kopf „Durchgegangen" Z. 32–41, Teil 3 Z. 333–350

**Urteil: überholt** (zwei von vier Zahlen).

| Behauptung | heute | Beleg |
|---|---|---|
| neun Menüs | **9** ✓ | Menüleiste: Datei, Bearbeiten, Objekt, Erzeugen, Ändern, Bausteine, Vorbereiten, Ansicht, Hilfe |
| 127 Einträge | **136** ✗ | dieselbe Zählung: 12 + 8 + 5 + 15 + 34 + 19 + 10 + 23 + 10 |
| acht Beispiele | **neun** ✗ | `app.core.examples.paths()` → 9; neu ist `weg4-figur-formen.p3d` (`5a9418c`, 14.08.2026) |
| sieben Analysekarten | **7** ✓ | `app/core/perceive/maps.py:49` `MapKind = Literal["wall","overhang","defects","curvature","features","fits","support"]` |
| 14 Fehlerklassen | **14** ✓ | ganze `AppError`-Hierarchie: AppError, UserError, GeometryError, InternalError, ValidationError, NeedsSolidError, SketchConflictError, AmbiguityError, UnitUnknownError, BooleanFailedError, NotManifoldError, OutOfBuildVolume, ExternalToolError, LicenceRequired |

Das neunte Beispiel ist kein Beiwerk: **Bauplan §2.2 heißt seit P16 „Vier
Hauptwege"** (`3d-agent-bauplan.md:101`), und
`tests/test_examples.py:23 test_there_is_one_example_per_way` prüft
`ways == ["1","2","3","4"]`. Das Konzept spricht in 1.2 und Teil 4 vom „zweiten
von **drei** Hauptwegen" — auch das ist überholt.

**Im Konzept müsste stehen:** „… alle neun Menüs mit 136 Einträgen · alle neun
Beispiele auf dem Startbildschirm …" und in 1.2 „der zweite von **vier**
Hauptwegen".

---

## 4. „Bausteinkatalog mit 23 Bausteinen, Skizzeneditor mit 24 Werkzeugen, Handbuch mit 33 Kapiteln, Tastenkürzel-Fenster mit 42 Gruppen"

*Ort:* Teil 3 Z. 352–357

**Urteil: falsch** — zwei der vier Zahlen zählen etwas anderes, als sie sagen,
und taten das schon am 08.08.

**Bausteine: 17, nicht 23.**

```
from app.core.knowledge.parts.registry import PARTS, GROUPS
len(PARTS.all()) → 17 ;  len(GROUPS) → 7
```

Am 09.08. waren es 16 (`git grep -c "@register_part" 26883f3` → 4+4+3+2+3 = 16).
Der Katalog baut einen **Baum aus Gruppen** (`app/ui/catalog.py:157–162`), und
16 Bausteine unter 7 Gruppenköpfen ergeben genau die 23 Zeilen, die gezählt
wurden. Es waren nie 23 Bausteine.

**Kürzel-Fenster: 6 Gruppen, nicht 42.**

```
from app.ui.shortcuts_window import entries
len(entries(window.menuBar())) → 36 Kürzelzeilen
Gruppen → 6 {Ansicht 15, Datei 9, Bearbeiten 4, Objekt 3, Ändern 3, Hilfe 2}
```

36 Zeilen plus 6 fettgedruckte Gruppenköpfe (`app/ui/shortcuts_window.py:100–110`)
sind 42 Baumzeilen — dieselbe Verwechslung wie beim Katalog.

**Handbuch: 40 Kapitel, nicht 33.**

```
from app.core import manual; len(manual.pages()) → 40
```

**Skizzeneditor: heute 25 Knöpfe.** `SketchPanel` trägt 15 `QToolButton`
(Auswählen, Punkt, Linie, Kreis, Bogen, Spline, Trimmen, Verlängern, Grundform,
Versetzen, Spiegeln, Hilfsgeometrie, Projizieren, Einpassen, Rückgängig) plus
8 Einträge in deren Aufklappmenüs und 10 Bedingungsknöpfe (Abstand, Deckung,
Waagerecht, Senkrecht, Parallel, Rechtwinklig, Tangential, Symmetrisch, Fest,
Referenzmaß). Welche Teilmenge davon 24 ergab, ist nicht rekonstruierbar; die
heutige Zahl ist 25 Knöpfe.

**Im Konzept müsste stehen:** „Bausteinkatalog mit 17 Bausteinen in sieben
Gruppen · Skizzeneditor mit 15 Werkzeugen und 10 Bedingungen · Handbuch mit 40
Kapiteln · Tastenkürzel-Fenster mit 36 Tasten in sechs Gruppen."

---

## 5. „1986 Einträge im englischen Katalog, keiner leer; kein Registertext ohne englische Entsprechung"

*Ort:* Teil 3 Z. 344–346

**Urteil: überholt.**

```
en.json 2647 leer: 0
es.json 2647 leer: 0
fr.json 2647 leer: 0
it.json 2647 leer: 0
pt.json 2647 leer: 0
```

Der Bestand ist außerdem nicht mehr „der englische Katalog", sondern **fünf
Kataloge** neben der deutschen Quelle (`app/i18n/locales/`). Die
Vollständigkeitsaussage selbst hält:
`.venv/Scripts/python.exe -m pytest -q tests/test_translations.py` läuft grün
(Teil des Laufs mit 662 bestandenen Tests, siehe unten).

**Im Konzept müsste stehen:** „2647 Einträge in jedem der fünf Kataloge (en, es,
fr, it, pt), keiner leer. Kein Registertext ohne Entsprechung in irgendeinem
davon."

---

## 6. Zeilengenaue Quelltextverweise (panels.py:981, panels.py:1018, panels.py:756, overlay.py:160, main_window.py:548, main_window.py:2665, features.py:261, mesh.py:169, print_settings_dialog.py:763)

*Ort:* 1.1, 1.3, 2.1, 2.2, 2.3

**Urteil: überholt** — **kein einziger** der neun Verweise zeigt noch auf das,
was er benennt.

| Verweis im Dokument | zeigt heute auf | wo es wirklich steht |
|---|---|---|
| `panels.py:981` (`MAX_ROWS = 12`) | mitten in `fit_wrapped` | `app/ui/panels.py:1483` — und `MAX_ROWS` ist kein Deckel mehr, sondern die Rückfallzahl, wenn die Überlagerung keinen Raum zugeteilt hat (`panels.py:1541`: `ceiling = room if room is not None else chrome + MAX_ROWS * row_height`) |
| `panels.py:1018` (`fit_to_rows`) | Ende der Datei | `app/ui/panels.py:1522` |
| `panels.py:756` (`setWordWrap(True)` im Prüfbericht) | `context_menu()` | `app/ui/panels.py:1095` |
| `overlay.py:160` (`natural_height`) | vor `rows_height` | `app/ui/overlay.py:258`; und die beschriebene Ursache existiert nicht mehr: `rows_height` misst über `visualRect` (`overlay.py:238`), nicht mehr über `sizeHintForRow` allein |
| `main_window.py:548` (`addStretch(1)`) | `_format_of` | `app/ui/main_window.py:845` |
| `main_window.py:2665` (`object_tree.context_menu()`) | Druckeinstellungs-Dialog | `app/ui/main_window.py:4403` |
| `features.py:261` (Set-Zugriff) | Docstring-Ende von `_facet_faces` | Zeile verschoben, Datei 478 Zeilen |
| `mesh.py:169` (rtree-Kommentar) | trifft noch die richtige Funktion (`on_surface`), aber der zitierte Satz „reproduzierbar daneben — eine Zugriffsverletzung in etwa jedem zwanzigsten Lauf" **steht dort nicht mehr**; der Docstring nennt jetzt 113168 → 1180 Anfragen und „sechzig Auswertungen ohne Fehlgriff" (`app/core/geom/mesh.py:182–189`) | — |
| `print_settings_dialog.py:763` (Mindestbreite 560) | Docstring des Slice-Arbeiters | `app/ui/print_settings_dialog.py:877` (`setMinimumSize(560, 640)` — unverändert) |

**Im Konzept müsste stehen:** die Verweise ohne Zeilennummern, nur mit Symbolnamen
(`panels.MAX_ROWS`, `overlay.natural_height`, …) — Zeilennummern in einem Dokument,
das der Nachtrag am selben Tag überholt, sind Zahlen mit Verfallsdatum.

---

## 7. „Alle Befunde 1.1 bis 2.6 sind behoben, belegt durch b017fde, b3de01e, 0c80417, 06e5e56, 22ce4c6, f49a7fa"

*Ort:* Kastentabelle Z. 15–30, Nachtrag

**Urteil: stimmt.**

Alle sechs Hashes existieren und tragen, was sie sollen:

```
b017fde 2026-08-08 Fünf Befunde passten nicht in eine Karte, neben der achthundert Pixel frei waren
b3de01e 2026-08-08 Vierzigtausend Dreiecke fragten nach dem Abstand zu einer Beschriftung
0c80417 2026-08-08 Das Menü an der Bohrung las ihren Durchmesser als ihre Art
06e5e56 2026-08-08 Die Bohrung begann am Ursprung, und der lag fünfundsechzig Millimeter daneben
22ce4c6 2026-08-08 Die Buchse saß auf einer Oberkante, die es seit dem Aushöhlen nicht gab
f49a7fa 2026-08-08 Acht Befunde standen im Kopf, zwei waren zu sehen
```

Die Behebungen haben elf Tage überlebt und tragen Tests:
`tests/test_overlay.py` führt unter anderem
`test_a_wrapped_finding_is_measured_at_its_real_height` (Z. 332),
`test_findings_that_arrive_later_make_the_card_grow` (Z. 363),
`test_a_card_uses_the_room_a_tall_window_offers` (Z. 408) und
`test_one_action_moves_a_card_once` (Z. 439, die gemeldete Regression).
`tests/test_analysis_ui.py:412` prüft das Merkmalsmenü,
`tests/test_analysis_ui.py:432` die Gruppierung am Körper.

Lauf zur Gegenprobe:

```
.venv/Scripts/python.exe -m pytest -q tests/test_overlay.py tests/test_translations.py \
    tests/test_examples.py tests/test_registry_consistency.py
→ 662 passed in 31.53s
```

Zwei Ergänzungen, die das Dokument nicht mehr kennen kann:

- **2.3** wurde nicht über die Dialogbreite gelöst, sondern über einen
  Kurzhinweis am ganzen Eintrag: `app/ui/print_settings_dialog.py:1641–1649`
  („Er steht jetzt zusätzlich am ganzen Eintrag", `setToolTip` über alle drei
  Spalten). `setMinimumSize(560, 640)` steht unverändert.
- **2.5** wurde gelöst wie vorgeschlagen, aber schärfer: STEP wird nicht
  ausgegraut, sondern **gar nicht angeboten**, wenn kein Körper es tragen kann
  (`app/ui/main_window.py:2875–2876`: `if any(entry.kind == "brep" …)`).

---

## 8. Nachher-Messwerte (Parameteränderung 1,47 s · erstes Öffnen 1,55 s · 1180 rtree-Anfragen · 0 Fehlgriffe in 60 Läufen · Prüfbericht 322 px · Objektbaum 873 px)

*Ort:* Nachtrag, Tabelle Z. 411–424

**Urteil: unprüfbar** — und die Grundlage hat sich seither zweimal verschoben.

Die 1180 Anfragen stehen als Zahl im Code (`app/core/geom/mesh.py:185`) und sind
insofern belegt. Die Zeiten sind Messungen am laufenden Fenster unter echter
Qt-Plattform; sie lassen sich hier nicht nachfahren, und der Leistungslauf gibt
sie nicht her:

```
.venv/Scripts/python.exe -m pytest -q -m performance
→ 13 failed, 6 passed
   sketch_solve_200: 195 ms (bester Lauf bisher 117 ms)  → Faktor 1,67
   map_wall_medium: 7119 ms (bester Lauf bisher 4197 ms) → Faktor 1,70
   blend_union: 2409 ms (bester Lauf bisher 1204 ms)     → Faktor 2,0
```

Alle dreizehn scheitern an der 25-%-Regressionsschwelle gegen den *besten Lauf
auf dieser Maschine*, alle mit fast demselben Faktor (1,6–2,0). Das ist das
Muster von Fremdlast, nicht von dreizehn gleichzeitigen Regressionen — als
Beleg für oder gegen die Zahlen des Nachtrags taugt der Lauf nicht.

Wichtiger: **die Rechnung hinter der Parameteränderung ist seit dem 18.08. eine
andere.** `ROADMAP.md:6514` — „Die Live-Vorschau rechnete den ganzen Stapel neu,
obwohl ihr Docstring seit jeher das Gegenteil zusagt … Der Aufruf reichte ihn nie
durch" (Commit `61d863d`). Die 1,47 s wurden vor dieser Änderung gemessen.

**Im Konzept müsste stehen:** die Zahlen mit Datum und dem Zusatz, dass sie eine
Momentaufnahme sind — und beim Eintrag „Parameteränderung" der Hinweis, dass der
Vorschau-Cache seit dem 18.08.2026 anders arbeitet.

---

## 9. „Kontextmenü: 6 Einträge am Merkmal (vier davon aus applies_to), 7 am Körper nach Kategorie gruppiert"

*Ort:* 2.1, Nachtrag Z. 421–422

**Urteil: stimmt.**

Am Merkmal `hole`: vier Operationen aus `applies_to`
(`align_to_feature`, `countersink_hole`, `plug_hole`, `test_piece`) plus die zwei
Sichtbarkeitseinträge (`_add_visibility`, `app/ui/panels.py:741`) → 6.

Am Körper: 64 Operationen mit `consumes == 1`, über `MAX_MENU_ROWS = 12`
(`app/ui/panels.py:79`), also gruppiert nach Kategorie
(`app/ui/panels.py:766–779`) in **fünf** Gruppen (Ändern 30, Bausteine 19,
Vorbereiten 10, Objekt 3, Erzeugen 2) plus die zwei Sichtbarkeitseinträge → 7
Zeilen.

Geprüft von `tests/test_analysis_ui.py:432 test_a_body_menu_stays_short_enough_to_read`
und `tests/test_acceptance_p0.py:67`.

Randnotiz für die Wartung, nicht für das Konzept: der Docstring in
`app/ui/panels.py:754` sagt weiterhin „An einem ganzen Körper sind es
siebenundfünfzig" — es sind 64.

---

## 10. „Nur noch ein Beispiel öffnet mit Warnung (das Reparatur-Beispiel, gewollt); dose-mit-deckel.p3d hat sieben Operationen und zwei Körper"

*Ort:* 1.2 Z. 116, 2.4, Nachtrag Z. 424

**Urteil: falsch** — und zwar als **Widerspruch im Dokument selbst.**

Die Op-Zahl stimmt: `dose-mit-deckel.p3d` führt sieben Operationen
(`create_box`, `hollow_object`, `insert_cable_gland`, `insert_heatset_m4`,
`label_text`, `create_lid`, `arrange_bed`).

Die Warnungszahl nicht. Alle neun Beispiele ausgewertet
(`load` + `evaluate` mit dem jeweiligen Profil):

```
weg3-generiert-aufbereiten.p3d  10 Befunde, davon 3 Warnungen
    ingest.small_components, ingest.not_watertight, repair.components_removed
dose-mit-deckel.p3d              4 Befunde, davon 1 Warnung
    fit.violated
alle übrigen                     0 Warnungen
```

Es sind also **zwei** Beispiele mit Warnung, nicht eines. Und das war am 08.08.
schon so: Abschnitt 2.4 desselben Dokuments nennt `fit.violated` ausdrücklich
als eine der zwei Warnungen im Dose-Beispiel und schreibt dazu, die Tour erkläre
sie absichtlich. Der Nachtrag zählt dieses Beispiel dann als warnungsfrei.
Behoben wurde nur `boolean.without_effect` (`22ce4c6`), und genau das steht auch
in `ROADMAP.md:3400` — „von acht Beispielen warnt nur noch das, dessen Zweck das
Warnen ist", derselbe Fehler, zusätzlich mit der inzwischen falschen Acht.

**Im Konzept müsste stehen:** „Von neun Beispielen öffnen zwei mit einer Warnung:
das Reparatur-Beispiel (`weg3-generiert-aufbereiten`, drei Warnungen — das ist
sein Zweck) und `dose-mit-deckel` mit `fit.violated`, das die Tour erklärt. Die
wirkungslose Boolesche ist weg."

---

## 11. „Vier von fünf Klicks auf verschiedene Flächen treffen ihr Merkmal; der frühere Befund aus konzept-bedienung.md ist erledigt"

*Ort:* Teil 3 Z. 322–326

**Urteil: unprüfbar.**

Die Trefferquote ist eine Messung über den VTK-Interactor an einer Maschine, die
rendert; unter `QT_QPA_PLATFORM=offscreen` ist sie nicht nachzufahren. Dass der
`vtkCellPicker` trägt, ist im Bestand plausibel, aber nicht durch einen Test mit
dieser Aussage abgesichert.

Kontext dazu: die Durchsicht vom 17.08.2026 (`ROADMAP.md:6403`) hat das laufende
Fenster **im Bild** geprüft und dabei drei Funde gemacht, die am Quelltext
unsichtbar waren — darunter, dass die Achsenanzeige hinter der linken Spalte lag
und auf jedem Handbuchbild in jeder Sprache falsch stand. Eine Messung wie diese
hier verdient dieselbe Behandlung: neu fahren, nicht fortschreiben.

---

## 12. „Analysekarten je 1,41–1,51 s (§31 erlaubt 3 s), Schichtenvorschau 2,67 s bei 200 Schichten, Auto Split 1,77 s, Handbuch 2,5 s"

*Ort:* Teil 3 Z. 333–336, 352–357

**Urteil: unprüfbar.**

Die Budgetzahlen des Bauplans stimmen: `3d-agent-bauplan.md:1435` — „Analysekarte
Wandstärke | unter 3 s, im Hintergrund"; `:1437` „Projekt öffnen aus Plattencache
| unter 1 s"; `:1438` „Parameteränderung → sichtbares Ergebnis | unter 2 s, nur
betroffene Zweige".

Die gemessenen Werte gelten für die kleinen Beispielprojekte und sind mit dem
Leistungslauf nicht vergleichbar: dort läuft die Wandstärkekarte gegen den
mittleren Korpus, mit einer Schranke von 8 s
(`tests/test_performance.py:253 assert taken < 8.0`) und einem besten Lauf von
4197 ms auf dieser Maschine. Siehe auch Punkt 8 zur Lastlage.

---

## 13. „Stand danach: 3168 Tests grün, ruff und mypy sauber"

*Ort:* Nachtrag, Schlusszeile Z. 455

**Urteil: überholt.**

```
.venv/Scripts/python.exe -m pytest -q --collect-only
→ 4246 tests collected
```

135 Einträge in `tests/`. Die Aussage „grün, ruff und mypy sauber" ist für den
08.08. nicht zu widerlegen; für heute wurde sie nicht vollständig nachgefahren
(die vier Tore laufen über `/pruefen`, das gehört nicht in diesen Abgleich). Die
Teilmenge, die zu diesem Dokument gehört, ist grün: 662 bestandene Tests aus
`test_overlay.py`, `test_translations.py`, `test_examples.py`,
`test_registry_consistency.py`.

**Im Konzept müsste stehen:** „Stand danach: 3168 Tests grün (08.08.2026; heute
sind es 4246)."

---

## 14. „test_the_slider_reports_a_factor wurde umgestellt; die Entprellung beträgt 120 ms"

*Ort:* Nachtrag, „Nebenbei aufgefallen" Z. 448–453

**Urteil: stimmt.**

`tests/test_split_ui.py:66 test_the_slider_reports_a_factor`, Docstring:
„Geprüft wird, **dass** der Zeitgeber läuft, nicht wie lange." Der Test prüft
`bar._pending.isActive()` statt einer Dauer.

Die Entprellung: `app/ui/section_bar.py:44 SETTLE_MS = 120`, benutzt von
`app/ui/explode_bar.py:118 self._pending.start(SETTLE_MS)`.

---

## 15. „Teil 4 nennt sechs Punkte als noch zu leistende Arbeit in vorgeschlagener Reihenfolge"

*Ort:* Teil 4, Z. 361–378

**Urteil: überholt — und der schwerste Fund, weil er den Leser in die Irre führt,
ohne dass er das Repository dazu braucht.**

Teil 4 liest sich als Arbeitsplan:

1. Die Höhenrechnung der Karten (1.1) — „Ein Tag Arbeit"
2. Die Vorgabe von „Bohrung setzen" (2.2)
3. Die Wartezeit bei Parameteränderungen (1.2) — „Erst messen, wohin die Zeit geht"
4. Das Kontextmenü füllen (2.1)
5. Die Ladezeit beim ersten Öffnen (2.6)
6. Der rtree-Absturz (1.3) — „Zuerst die Häufigkeit belegen"

Dahinter: 2.3, 2.4, 2.5, 2.7.

**Alle sechs sind erledigt**, fünf davon meldet der Nachtrag derselben Datei
sechzig Zeilen tiefer mit Vorher-/Nachher-Zahlen, den sechsten (1.3) als
Nebenwirkung derselben Ursache. Von den vier „dahinter" genannten sind drei
erledigt; offen ist allein 2.7, und das als Entscheidung. `ROADMAP.md:3372`:
„Alle Punkte bis auf die Tastenkürzel, jeder mit Test und am laufenden Fenster
nachgemessen."

Dasselbe gilt für die Teil-1- und Teil-2-Abschnitte: Sie stehen im
Präsens-Befund („Der Dialog kommt mit x = 0,00 …", „Das Menü … es steht nur
nichts darin", „STEP steht im Exportdialog und geht bei Netzen nie") und tragen
den Erledigt-Vermerk nur als Zitatkasten obendrüber — 2.3, 2.5 und 2.6 nicht
einmal das im Fließtext. Wer quer liest, liest die Befunde.

**Im Konzept müsste stehen:** Teil 4 gestrichen oder auf einen Satz eingedampft
(„Die Reihenfolge, in der abgearbeitet wurde — alle sechs Punkte sind am
08.08.2026 erledigt worden, siehe Nachtrag"), und jeder Befundabschnitt mit einem
Erledigt-Vermerk **in der Überschrift**, nicht nur im Kasten darunter.

---

## Was ich nicht geprüft habe

Die zwölf extern prüfbaren Behauptungen (ElegooSlicer-Bestand 1001/7/42, die
Elegoo-Profilnamen, das rtree-Verhalten von libspatialindex, `QMenu.exec`,
`vtkCellPicker`, die Kürzelbelegung von Fusion und Onshape). Zwei davon haben
einen internen Anteil, den ich mitgeprüft habe: die vier externen Programme sind
weiterhin genau vier (`app/core/tools.py:102–130`: OpenSCAD, Slicer, Ollama,
ComfyUI), und die Fusion-Belegung steht in
`app/ui/shortcut_schemes.py:26–38` (siehe Punkt 2).

## Was seit dem 08.08. dazugekommen ist und im Dokument fehlt

Kein Fund, sondern der Grund, warum sich eine Neuaufnahme lohnt statt einer
Korrektur: `app/ui/` führt heute `generate_dialog.py`, `sculpt_bar.py`,
`paint_bar.py`, `pose_bar.py`, `explode_bar.py` und `section_bar.py` — das
Ergebnis von P16 (organische Modellierung) und des vierten Wegs. Das Dokument
beschreibt eine Oberfläche, die diese Werkzeugleisten nicht hat.
