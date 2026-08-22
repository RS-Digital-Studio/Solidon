# Abgleich: konzept-erstnutzer-2026-08.md gegen den Stand vom 19.08.2026

Dokumentstand laut Kopf: 14.08.2026. Geprüft am Arbeitsbaum auf `main`,
Kopfcommit `b0415d6`. Alle Zählungen mit `.venv\Scripts\python.exe` gegen das
laufende Register bzw. das offscreen gebaute Fenster.

**Zählung:** 15 interne Behauptungen geprüft — 4 stimmen, 9 überholt,
1 falsch, 1 unprüfbar. Dazu drei Widersprüche im Dokument selbst
(Befunde ohne Zeile in der Statustabelle) und eine Statuszeile, die die
Wirklichkeit überholt hat.

---

## 1. „83 registrierte Operationen; von 77 auf 83 gewachsen"

*Ort:* Teil 5 Befund 5.6, Teil 6.
**Urteil: überholt.**

Beleg:

```
.venv/Scripts/python.exe -c "from app.core.bootstrap import load_operations;
from app.core.registry import REGISTRY; load_operations(); print(len(REGISTRY.all()))"
→ 85
```

Aufteilung: scene 5, repair 1, transform 9, primitive 7, boolean 4, sketch 5,
shaping 5, holes 3, parts 19, prepare 7, import 3, colour 3, label 2,
surface 3, mesh 9.

*Stattdessen:* „85 registrierte Operationen (Stand 19.08.2026); die Zahl war
77, dann 83, jetzt 85."

---

## 2. „`window_commands()` führt 22 Fensterbefehle, fünf davon ohne Kürzel;
nur sechs Operationen tragen ein Kürzel"

*Ort:* Teil 5 Befund 5.6.
**Urteil: überholt** — beide Zahlen und die Pointe.

Beleg (offscreen gebautes Fenster, `build_application([])` nach
`load_operations()`):

```
WINDOW_COMMANDS 60
OHNE KUERZEL   23
```

Der Grund steht in `app/ui/main_window.py:3116` `_menu_commands`: die Palette
liest die Menüleiste seither selbst aus, statt eine Liste von Hand zu führen
(„39 von 136 Menüzeilen fehlten"). Aus 22 handgepflegten Einträgen sind 60
geworden.

Die Pointe des Befundes ist ebenfalls weg: **die Werkzeuge der unteren Leiste
haben Kürzel.** Es sind heute acht, `Alt+1` bis `Alt+8`:

```
section Alt+1 · measure Alt+2 · transform Alt+3 · analysis Alt+4
layers Alt+5 · explode Alt+6 · split Alt+7 · paint Alt+8
```

ROADMAP.md:5592 führt das als erledigt: „**Die acht Werkzeuge haben Kürzel**,
`Alt+1` bis `Alt+8` in der Reihenfolge der Leiste."

Unverändert stimmt nur die zweite Hälfte: sechs Operationen tragen ein Kürzel
(`delete_object`, `drill_hole`, `duplicate_object`, `rename_object`,
`rotate_object`, `translate_object`) — jetzt sechs von 85 statt sechs von 83.

*Stattdessen:* „`window_commands()` führt 60 Fensterbefehle, 23 davon ohne
Kürzel. Die acht Werkzeuge der unteren Leiste tragen seit `Alt+1`…`Alt+8`
eigene Kürzel; offen bleibt allein, dass von 85 Operationen sechs eines
haben."

---

## 3. „5.6 Kürzel für die Werkzeuge — **offen, als Entscheidung**"
(Statustabelle im Kopf)

**Urteil: überholt.** Siehe Beleg oben: ROADMAP.md:5592, Werkzeugleiste trägt
`Alt+1` bis `Alt+8`. Von den vier als offen geführten Punkten ist dieser zu.

*Stattdessen:* Zeile aus dem Offen-Block in den Behoben-Block, mit dem Zusatz
„die Werkzeugkürzel sind gebaut; die Kürzelarmut der Operationen bleibt".

---

## 4. „127 Menüeinträge in drei Szenenzuständen abgefragt; unter *Ändern* sind
alle 34 Einträge aus, *Objekt* ganz aus"

*Ort:* Teil 2 Befund 2.3, Abschnitt „Was gemessen wurde", Teil 6.
**Urteil: überholt** in der Zahl, **stimmt** im Befund.

Beleg (voll geladene Menüleiste, leere Szene):

| Menü | Blattzeilen |
|---|---|
| Datei | 12 |
| Bearbeiten | 8 |
| Objekt | 5 (alle AUS) |
| Erzeugen | 15 |
| Ändern | 34 (alle AUS) |
| Bausteine | 19 (alle AUS) |
| Vorbereiten | 10 |
| Ansicht | 23 |
| Hilfe | 10 |
| **Summe** | **136** |

136 deckt sich mit dem, was der Quelltext selbst zählt
(`app/ui/main_window.py:3116` ff.: „39 von 136 Menüzeilen fehlten") und mit
ROADMAP.md:6591 („38 von 136").

Die 34 unter *Ändern* stimmen weiterhin — die Zahl ist dieselbe geblieben,
die Zusammensetzung nicht (heute: Verbinden 4, Transformation 9, Formgebung 5,
Bohrungen 3, Oberfläche 3, Netz 9, Reparatur 1).

*Stattdessen:* „136 Menüeinträge … unter *Ändern* sind alle 34 aus, *Objekt*
mit seinen fünf Einträgen ganz aus."

---

## 5. „Elf englische Docstrings in `app/` plus fünf in `tests/`" /
Kopftabelle „5.8 … behoben — `799fce5`, jetzt null"

*Ort:* Teil 5 Befund 5.8, Teil 4 Befund 4.7, Kopftabelle.
**Urteil: überholt für `app/`, falsch für `tests/`.**

`app/`: alle elf genannten Stellen tragen heute deutsche Docstrings. Stichprobe:

| Datei | heute |
|---|---|
| `app/ui/command_palette.py:135` | „Tippen, wählen, ausführen." |
| `app/ui/first_run.py:95` | „Eine Seite, vier Fragen, alles überspringbar." |
| `app/ui/session.py:104` | „Ein Auswertungslauf. Besitzt nichts, meldet alles." |
| `app/ui/settings.py:26` | „Alles, was sich das Fenster über Sitzungen hinweg merkt." |
| `app/core/registry/surfaces.py:39` | „Das Menü, in der Reihenfolge des Katalogs (§25)." |
| `app/core/perceive/features.py:477` | „Wie viele getrennte Körper das Netz enthält (§21.1)." |
| `app/core/knowledge/parts/registry.py:85` | „Alles, was über einen Baustein bekannt ist." |
| `app/core/geom/measure.py:85` | „Von Punkt zu Punkt, in Millimetern." |
| `app/core/slice/orientation.py:88` | „Wie viel Stützvolumen … gespart wird, in mm³." |
| `app/core/backends/openscad.py:206` | „Ob sich OpenSCAD überhaupt aufrufen lässt." |

`tests/`: **„jetzt null" gilt dort nicht.** Ein AST-Lauf über `tests/` findet
heute zwölf englische Docstrings:

```
tests/test_project.py:1     "The project container: round trip, checksums, versions, autosave (§16, §32, §38)."
tests/test_project.py:519   "Replace project.json inside an existing container."
tests/test_difference.py:1  "The difference view (Bauplan §18.7)."
tests/test_acceptance_p0.py:50  "§40: at least two operations, visible in menu, palette, context menu, CLI, tools."
tests/test_acceptance_p0.py:98  "§40: undo and redo across ten transactions."
tests/test_agent.py:228     "P4 acceptance: schema-valid before anything is computed."
tests/test_agent.py:431     "§26.2, Leitprinzip 6: ambiguity asks instead of guessing."
tests/test_export.py:159    "§16.3: once, factual, without a lecture."
tests/test_features.py:40   "§40: plate_holes is recognised completely."
tests/test_section.py:21    "A welded cube: 20 mm edge, 8000 mm³, watertight."
tests/test_slice.py:110     "§40: island_tower.stl is recognised."
tests/test_slots.py:310     "The whole way through: scene object, plan, bytes."
```

Und sie sind nicht neu: `git log -S` datiert sie auf den 27./28.07.2026
(`6caed40`, `94532e3`, `4841a49`) — also vor der Zählung. `git show 799fce5
--stat` zeigt, dass der Behebungscommit in `tests/` nur vier Dateien anfasste
(`data/make_corpus.py`, `test_maps.py`, `test_translations.py`, `test_ui.py`).
Die Angabe „fünf in `tests/`" war also schon beim Schreiben zu niedrig.

*Stattdessen:* „Elf englische Docstrings in `app/` — behoben, `app/` ist null.
In `tests/` stehen davon unabhängig zwölf englische Docstrings, die die
Zählung nicht erfasst hatte; sie stehen dort bis heute."

---

## 6. Kopftabelle: 14 Befunde behoben mit den genannten Commit-Kürzeln

**Urteil: stimmt.** Alle zwölf Kürzel liegen noch im Verlauf und tragen die
passende Meldung:

```
2f56d93 2026-08-14 Ein neues Projekt zeigte einen Bauraum, den niemand sah
443058f 2026-08-14 Ausweichen, das die eigene Breite nicht kennt, weicht nicht aus
61fbc01 2026-08-14 Die Seite ließ sich seitlich schieben, und dort war nichts
7fe7c30 2026-08-14 Der Chat ist das Versprechen der Anwendung und stand leer da
b07bcfb 2026-08-14 Bemalen auf einer leeren Szene ist ein Pinsel für nichts
46e2b7c 2026-08-14 Ein Verweis auf ein Fenster, das die Anwendung zuhält, ist keiner
8232923 2026-08-14 Ein Erzeugen im Ändern-Menü, und es fiel am Ausgegrauten auf
799fce5 2026-08-14 Drei kleine Stellen, an denen die Anwendung sich selbst widerspricht
9aa7df9 2026-08-14 Vierzig Kapitel ohne Fuge, und ein Baum ohne Anfang
c2bd852 2026-08-14 Kein Rückfall hilft gegen Maße
b0cb0d1 2026-08-14 Ein Umschalter hinter dem Umschalter, der die Leiste öffnet
5902211 2026-08-14 Eine Legende aus face_10 und pin_3 ist eine Debug-Ausgabe
```

Auch `b017fde` (in Befund 2.1 zitiert) liegt im Verlauf, 08.08.2026.

Stichproben am Code bestätigen die Wirkung:

* 1.1 — `_fit_once_for` (`app/ui/viewport.py:3492`) hat den Zweig „Die leere
  Szene hat auch etwas zu zeigen: den Bauraum".
* 2.2 — `app/ui/chat.py:54` `STARTERS`, Beispielanfragen im leeren Gespräch.
* 2.3 — offscreen gemessen: Werkzeugleiste auf dem Startbildschirm
  `isVisible() == False`, alle acht Werkzeuge `enabled == False` bei leerer
  Szene.
* 2.4 / 5.1 — `app/ui/main_window.py:5678` setzt „Prüfbericht · n";
  `_focus_report(force=True)` (`main_window.py:5715`) überstimmt die Tour.
* 4.2 — `app/ui/settings_dialog.py:157–159`: `remote_port.setEnabled(...)`
  und `remote.toggled.connect(self.remote_port.setEnabled)`. Der Haken heißt
  jetzt „Fernsteuerung durch andere Programme zulassen (MCP)".
* 4.6 — `website/style.css:309–315`: `.hide-small` nur noch unter 44rem,
  „Preis" ist `.hide-tiny` und weicht erst unter 30rem.
* 1.3 — `website/style.css:67` `overflow-x: clip` am `:root`, zusätzlich
  Zeile 93 am `body`; `website/handbuch.html:86` gibt Tabellen ihren eigenen
  `overflow-x: auto`.

---

## 7. „Offen bleiben vier: 2.1 Kartenhöhe, 2.5 Import im vorhandenen Körper,
3.1/3.4 Menüs, 5.6 Kürzel"

**Urteil: überholt.** Es sind noch drei — 5.6 ist zu (siehe 3).

Für die anderen drei fand sich kein Gegenbeleg:

* 2.1 — `app/ui/overlay.py` ist seit dem 14.08.2026 unverändert
  (`git log --since=2026-08-14 -- app/ui/overlay.py` liefert nichts). Die
  ROADMAP-Stelle zur Spaltenhöhe (ROADMAP.md:3749, „Die linke Spalte rechnete
  sich um zweihundert Pixel zu kurz") datiert auf den 08.08.2026, also vor
  dem Befund.
* 2.5 — `Auf dem Bett anordnen` existiert weiter als eigener Menüeintrag
  (`Objekt → Auf dem Bett anordnen`), läuft beim Einfügen nicht von selbst;
  kein ROADMAP-Eintrag dazu.
* 3.1 / 3.4 — siehe 8 und 9.

*Stattdessen:* „Offen bleiben drei: 2.1, 2.5, 3.1/3.4."

---

## 8. Befund 3.1 „Zwei Menüs sind reine Verteiler"

**Urteil: teils überholt.**

*Erzeugen* hat weiter vier Einträge, alle vier Untermenüs (Grundformen,
Import, Skizze, Beschriftung). *Ändern* hat weiter sieben, alle sieben
Untermenüs. Beides gemessen an der gebauten Menüleiste.

*Vorbereiten* nicht mehr: es führt heute **drei** Zeilen — die Untermenüs
„Teilen und Anpassen" und „Farbe" sowie den flachen Eintrag „Automatisch
teilen …". Ein Untermenü namens „Druckvorbereitung" gibt es nicht mehr; damit
ist auch die Beobachtung „eines davon heißt fast wie sein Elternmenü"
gegenstandslos.

*Stattdessen:* Den Satz zu *Vorbereiten* streichen oder ersetzen durch:
„*Vorbereiten* enthält drei Zeilen: zwei Untermenüs und *Automatisch
teilen …*."

---

## 9. Befund 3.2 „Grundformen sortiert alphabetisch und mischt Fremdes hinein"

**Urteil: überholt im Zitat, gültig im Befund.**

Der zitierte Block hat heute fünf statt vier Zeilen, weil `thread_exact` mit
`8232923` hierher umgezogen ist:

```
Kugel anlegen  →  Exakten Gewindebolzen erzeugen
OpenSCAD-Teil anheften   Kugel anlegen
Quader anlegen           OpenSCAD-Teil anheften
Zylinder anlegen         Quader anlegen
                         Zylinder anlegen
```

Der Quader steht damit an **vierter** Stelle, nicht an dritter; das
Expertenwerkzeug an dritter, nicht an zweiter. Die alphabetische Sortierung
selbst hält `tests/test_interface_limits.py:484`
`test_a_menu_is_sorted_the_way_it_is_read` fest — der Test existiert wie
behauptet.

*Stattdessen:* Den Menüblock durch die heutigen fünf Zeilen ersetzen; „an
dritter Stelle" → „an vierter Stelle".

---

## 10. Befund 3.4 „Das Kontextmenü ist die Menüleiste in alphabetischer
Reihenfolge"

**Urteil: stimmt** für den Rechtsklick auf den Körper.

`app/ui/panels.py:750` `_add_operations`: oberhalb von `MAX_MENU_ROWS` wird
nach `group_title(spec.category)` gruppiert und `for title in sorted(groups)`
ausgegeben — alphabetisch. Der Docstring nennt selbst „siebenundfünfzig"
Operationen am ganzen Körper.

Zu ergänzen wäre: Für ein **Merkmal** liegt der Weg bereits so, wie der Befund
ihn fordert — `context_menu()` (`panels.py:728`) ruft
`operations_for_feature(kind)`, und diese Handvoll steht flach im Menü. Die
Klage trifft heute nur noch den Rechtsklick auf den Körper.

---

## 11. Befund 4.1 / 4.3 („geblieben") und 3.2 („bewusst nicht behoben")

**Urteil: 4.1 stimmt, 4.3 teils überholt, 3.2 stimmt.**

4.1: keine Änderung an `app/ui/theme.py` / `app/ui/style.py` zum
Zeichenmodus seit dem 14.08.2026 (die zwei Commits `f608ff4`, `bca7b5e`
betreffen Formularbeschriftungen und Spinbox-Pfeile).

4.3: die zitierten Zeilennummern stimmen nicht mehr — die Regeln stehen in
`app/ui/style.py:292/293`, nicht 161/162 (dort steht heute `_arrow_rules`).
Inhaltlich hat sich etwas geändert: `:hover` färbt nicht nur den Rand, es
wechselt zusätzlich den Hintergrund
(`QFrame#exampleTile:hover { border-color: {highlight}; background: {hover}; }`),
und `:focus` nimmt seit `style.py:217` (`focus = accent_line`) einen eigenen
Farbtoken mit begründetem Kontrast statt „derselben Farbe". Im dunklen Thema
ist `accent_line` derselbe Bernstein, die Kacheln unterscheiden sich also
weiter über Randstärke und Hintergrund statt über Farbe allein.

*Stattdessen:* Zeilennummern auf 292/293 ziehen und den Satz „malt … einen
2 px starken Rand in derselben Farbe" um den Hintergrundwechsel ergänzen.

---

## 12. „`_fit_once_for` in `app/ui/viewport.py:3171` … Startkamera über
`view_from(\"iso\")` in `viewport.py:1056`"

**Urteil: überholt** (Zeilennummern), Sache behoben.

Heute: `_fit_once_for` an `app/ui/viewport.py:3492`, `view_from("iso")` an
`app/ui/viewport.py:1166`, `reset_camera` an `viewport.py:3466`. Die Datei ist
auf 3926 Zeilen gewachsen. Der Docstring von `_fit_once_for` erzählt den
Befund selbst nach („Ohne diesen Zweig stand die Kamera nach *Neues Projekt*
auf (1, -1, 0,8)").

---

## 13. „`_focus_report` (`app/ui/main_window.py:4675`) kehrt bei aktiver Tour
ohne Reiterwechsel zurück, samt zitiertem Codeblock"

**Urteil: überholt.**

Heute `app/ui/main_window.py:5715`, mit neuem Parameter:

```python
def _focus_report(self, force: bool = False) -> None:
    ...
    if not force and self.right.currentWidget() is self.tour and self.tour.active:
        return
```

Der zitierte Codeblock im Dokument zeigt den Zustand ohne `force` und ist
damit nicht mehr der Quelltext. `main_window.py` hat 6029 Zeilen.

---

## 14. Weitere Codestellen mit Zeilennummer: `settings_dialog.py:129`,
`style.py:161/162`, `analysis_bar.py:209`, `style.css:203`, `first_run.py:96`

**Urteil: überholt — alle fünf zeigen heute etwas anderes.**

| Zitat | heute an dieser Zeile | wo es jetzt steht |
|---|---|---|
| `settings_dialog.py:129` (Port ohne Kopplung) | Kommentar zur Benennung des Hakens | Kopplung: `settings_dialog.py:157–159` |
| `style.py:161/162` (hover/focus) | `_arrow_rules` (Spinbox-Pfeile) | `style.py:292/293` |
| `analysis_bar.py:209` (zwei Einträge False/True) | `layout.addWidget(self.selector)` | Das Auswahlfeld ist weg; `analysis_bar.py:253 ff.` erklärt den Wegfall |
| `style.css:203` (`.hide-small`) | `nav.lang details.langs summary::-webkit-details-marker` | `.hide-small`: `website/style.css:310` |
| `first_run.py:96` (englischer Docstring) | Konstruktorzeile | Docstring jetzt `first_run.py:95`, deutsch |

---

## 15. „Die Merkmalskarte legt 24 farbige Kacheln … heißt ‚Feature-Zuordnung',
Winkel als ‚45 grad'"

**Urteil: überholt** (behoben, wie die Tabelle sagt), mit einem Rest.

`git show 5902211`: die Legende bekommt „einen Deckel bei acht", die Namen
kommen aus dem Objektbaum („aus hole_1 wird ‚Bohrung 1 · ⌀4,2 mm'").
`app/ui/analysis_bar.py:160` hält den zweiten Teil fest: „Winkelparameter
schreiben ‚45°', die Karten schrieben ‚45 grad'."

Rest: **Der Kartenname „Feature-Zuordnung" lebt weiter** — in
`app/core/manual.py:233` und in allen fünf Katalogen
(`app/i18n/locales/*.json`, Handbuchkapitel „Analysekarten"). Nur die Karte
selbst heißt inzwischen „Merkmale" (`app/core/perceive/maps.py:149`: „‚Merkmale'
und nicht ‚Feature-Zuordnung'"). Handbuch und Oberfläche nennen dieselbe
Karte also verschieden.

*Stattdessen:* Befund als behoben markieren und den Rest festhalten: „Der
Name *Feature-Zuordnung* steht noch im Handbuchtext (`app/core/manual.py:233`
und alle Kataloge), während die Karte in der Oberfläche *Merkmale* heißt."

---

## 16. „Die englische Oberfläche ist vollständig: 0 deutsche Einträge in 127
Menüzeilen …"

**Urteil: überholt.**

Zwei Zahlen sind alt: 127 → 136 Menüzeilen (siehe 4), und „beide Sprachen" →
sechs. `app/i18n/locales/` führt heute `en.json`, `es.json`, `fr.json`,
`it.json`, `pt.json` neben der deutschen Quelle; `AGENTS.md` nennt dieselben
sechs, `tests/test_translations.py` prüft jede gefundene Datei.

Die Aussage selbst ist damit nicht widerlegt, aber sie deckt heute ein Fünftel
des Bestands ab. Auch „alle sieben Werkzeughinweise übersetzt" ist überholt:
die Leiste führt acht Werkzeuge (`explode`, `split` sind dazugekommen).

*Stattdessen:* „0 deutsche Einträge in 136 Menüzeilen … Geprüft wurde die
englische Fassung; Kataloge gibt es inzwischen für en, es, fr, it und pt."

---

## 17. „Jede der 83 Operationen hat einen Beschreibungssatz, kein Parameter
ohne Erklärung; der vollste Dialog hat acht Frontfelder"

**Urteil: stimmt** — bis auf die Zahl 83.

Nachgezählt über `__param_spec__`:

```
Ops ohne Beschreibung: []
Parameter ohne Erklaerung: 0
front max: [(8,'label_text'), (7,'insert_wall_mount'), (7,'apply_texture'), (6,'screw_lid'), ...]
```

85 Operationen, keine ohne `doc`, kein Parameter ohne `doc`, Höchstwert acht
Felder mit `placement == "front"` (`label_text`) — die Grenze aus dem Dokument
liegt genau dort. Auch die Selbstkorrektur am Dokumentende („Richtig gezählt
liegt keine über acht") hält.

*Stattdessen:* „Jede der 85 Operationen …"

---

## 18. „Kamera-Messwerte nach `start_empty()`: (1.0, −1.0, 0.8) gegen
(474.7, −474.7, 504.7), Bauraum 220 × 220 mm"

**Urteil: überholt** — die Messung beschreibt den Zustand vor `2f56d93`.

Der Bauraum stimmt weiterhin: `app/core/knowledge/profiles.py:36`
`DEFAULT_PRINTER = "generic-220"`, `app/core/knowledge/data/printers.toml:13`
`build_volume = [220.0, 220.0, 250.0]`.

Die Ausgangslage (1.0, −1.0, 0.8) gibt es nicht mehr: `_fit_once_for` passt
seither auch die leere Szene auf den Bauraum ein
(`app/ui/viewport.py:3492 ff.`). Die zweite Zeile der Tabelle ist heute die
einzige.

*Stattdessen:* Die Tabelle als „vorher / nachher" kennzeichnen, nicht als
„wie geliefert".

---

## 19. Website-Messwerte: scrollX 111 / 47 / 270, hero::before 1646 px,
hero::after 1458 px, Handbuchtabelle 645 px

**Urteil: unprüfbar hier** (Browsermessung), aber die Ursachenbehebung ist
belegt: `website/style.css:67` trägt `overflow-x: clip` am `:root` mit genau
diesen Zahlen im Kommentar („um 111 Pixel nach rechts … das Handbuch auf dem
Telefon um 270 von 375"), `website/handbuch.html:86` und
`tools/make_manual.py:133` geben Tabellen `display: block; overflow-x: auto`.

---

## Widersprüche im Dokument selbst

### W1 — Drei Befunde stehen in keiner Zeile der Statustabelle

Die Kopftabelle führt 1.1, 1.2, 1.3, 2.2, 2.3, 2.4, 3.3, 4.2, 4.5, 4.6, 4.7,
5.1, 5.2, 5.3, 5.4, 5.5, 5.8 als behoben; 2.1, 2.5, 3.1/3.4, 5.6 als offen;
3.2, 4.1, 4.3 als bewusst so. **4.4, 5.7 und 5.9 kommen darin nicht vor.**
Wer die Tabelle liest, hält sie für vollständig.

Alle drei sind heute noch offen:

* **4.4 „plate_holes" im ersten Beispielprojekt** —
  `app/examples/weg1-halterung-anpassen.p3d` führt `sources/plate_holes.stl`,
  und `app/core/ingest/ops.py:227` benennt das Objekt mit
  `params.name or Path(source.path).stem`. Im Baum steht also weiter
  `plate_holes`.
* **5.7 Zwei Klappen, zwei Verhalten** —
  `app/ui/print_settings_dialog.py:1004/1005` klappt „Weitere Einstellungen"
  über `box.toggled.connect(self._unfold_tabs)` wirklich zu;
  `slicer_box` (Zeile 1047–1049) ist ebenfalls `setCheckable(True)` /
  `setChecked(False)`, hat aber keine solche Verbindung — die Felder bleiben
  sichtbar. (Der zweite Teil, der abgeschnittene Vorschlag, ist entschärft:
  `profile_note.setWordWrap(True)`, Zeile 1076.)
* **5.9 Zwei modale Fehlerfenster hintereinander** — kein Stapelschutz im
  Quelltext (`app/ui/report_dialog.py`, `app/ui/dialogs.py`), kein Eintrag in
  ROADMAP.md.

### W2 — Der Fließtext beschreibt Zustände, die die eigene Tabelle für
behoben erklärt

Das betrifft Teil 1 (1.1, 1.2, 1.3), Teil 2 (2.2, 2.3, 2.4), Teil 3 (3.3),
Teil 4 (4.2, 4.5, 4.6, 4.7) und Teil 5 (5.1–5.5, 5.8) — alle im Präsens
geschrieben („Was ein Neuling sieht: eine Zeile ‚Modell: ollama:qwen3:14b',
darunter 170 px Leere"), während die Kopftabelle sie als behoben führt. Das
ist im Dokument angelegt und in der Alterungsbewertung der Sondierung schon
benannt; für einen Leser, der nur einen Teil aufschlägt, bleibt es eine Falle.
Konkret irreführend sind heute Teil 3.3 (der Gewindebolzen steht seit
`8232923` unter *Erzeugen → Grundformen*, nicht unter *Ändern → Formgebung*)
und Teil 5.6 (die Werkzeuge haben Kürzel).

---

## Zusammenfassung der Zählungen

| behauptet | heute | Beleg |
|---|---|---|
| 83 Operationen | **85** | Register ausgezählt |
| 6 Ops mit Kürzel | 6 | `shortcut` im Register |
| 22 Fensterbefehle, 5 ohne Kürzel | **60 / 23** | `window_commands()` offscreen |
| 127 Menüzeilen | **136** | Menüleiste ausgezählt; `main_window.py:3116`, ROADMAP:6591 |
| 34 Einträge unter *Ändern* | 34 | Menüleiste, leere Szene |
| 7 Werkzeuge der unteren Leiste | **8** | `win.tools.tools()` |
| 7 Analysekarten | 7 | `app/core/perceive/maps.py:49` |
| 11 englische Docstrings in `app/` | **0** | AST-Lauf |
| 5 englische Docstrings in `tests/` | **12** | AST-Lauf, alle vom 27./28.07. |
| 2 Sprachen | **6** | `app/i18n/locales/` |
| 8 Beispielkacheln | **9** | `len(examples.EXAMPLES)` |
| 8 Frontfelder maximal | 8 | `placement == "front"` |
| Bauraum 220 × 220 mm | 220 × 220 | `printers.toml:13`, `generic-220` |
| 17 Bausteine (nicht behauptet) | 17 | `PARTS.all()` |
