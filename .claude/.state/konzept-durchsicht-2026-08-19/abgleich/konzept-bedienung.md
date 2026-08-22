# Abgleich: konzept-bedienung.md gegen den Stand vom 19.08.2026

**Geprüft:** 15 intern prüfbare Behauptungen aus der Sondierung, dazu drei
Zählungen, die im Haupttext mitlaufen (Beispiele, Touren, Operationen).

**Zählung:** stimmt 1 · überholt 14 · falsch 0 · unprüfbar 0

**Kernbefund:** Das Dokument ist eine Momentaufnahme vom 4./5. August 2026.
Sein eigener Nachtrag („Stand, 5. August 2026, zweiter Eintrag") entwertet den
Haupttext bereits, ohne ihn zu korrigieren — und seit dem 5. August liegen
**520 Commits**. Vom Haupttext ist praktisch nichts mehr Stand. Wer nur die
Teile 1 bis 9 liest, liest durchgehend Falsches; der Nachtrag selbst ist an
seinen Zahlen (59 Commits, 2736 Tests) und an seinem Schlusssatz („offen bleibt
der nächste Lauf") ebenfalls überholt.

---

## 1 — `_left_down` kehrt im slicer-Schema mit `return` zurück (1.1)

**Behauptung:** `viewport.py:1240`; Linksklick wählt nichts aus, Picking läuft
nur bei Messen/Bemalen/Merkmalsüberlagerung; Rechtsklick öffnet kein
Kontextmenü; Weg 3 Schritt 3 damit nicht ausführbar.

**Urteil: überholt**

**Beleg:**
- `app/ui/viewport.py:3811–3833` — `_left_down` kehrt im slicer-Schema
  weiterhin früh zurück, aber das Picking sitzt inzwischen im Loslassen:
  `app/ui/viewport.py:3844–3857` (`_left_up` → `on_pick(x, y)`, sobald
  `is_click(started, (x, y))`).
- Kontextmenü: `app/ui/viewport.py:930` (`contextMenuAt = Signal(int, int)`),
  `:3623` (Emission), verdrahtet in
  `app/ui/main_window.py:862` → `_on_viewport_context_menu`
  (`app/ui/main_window.py:4393–4403`, holt `object_tree.context_menu()`).
- Commit `edf3cb7` „Der Klick kam an und hatte niemanden" (05.08.2026) nennt
  die drei übereinanderliegenden Ursachen und behebt sie.
- `ROADMAP.md:3341` — „**der Viewport nimmt Klicks an** (`obj_2` und `face_7`,
  Baum folgt) — der Fund aus `konzept-bedienung.md` ist erledigt".

**Was stattdessen dastehen müsste:** „Der Linksklick wählt aus. Das Picking
löst der eigene Interaktorstil im Loslassen aus, wenn niemand gezogen hat
(`viewport.py:_left_up`); der Rechtsklick öffnet das Kontextmenü des
Objektbaums am getroffenen Objekt."

---

## 2 — Kamera arbeitet gegen den Nutzer (1.2)

**Behauptung:** „Alles einpassen" passt auf den Bauraum ein; das Mausrad zoomt
zur Bildmitte (`viewport.py:1209`); jede Auswahländerung setzt die Kamera
zurück.

**Urteil: überholt**

**Beleg:**
- `app/ui/viewport.py:3466–3490` — `reset_camera()` rechnet über
  `_object_bounds()` und nimmt den Bauraum nur, wenn keine Körper da sind;
  Docstring: „Passt auf die Körper ein — nicht auf den Bauraum." Die Zeile
  `self.plotter.camera_set = True` (`:3490`) hält das gegen pyvista fest —
  genau der Fund, den der Nachtrag des Dokuments schon beschreibt.
- `app/ui/viewport.py:3862–3870` — `_wheel_in`/`_wheel_out` rufen
  `_zoom_at_pointer`, dessen Docstring lautet „Zoomt auf die Stelle unter dem
  Zeiger, nicht auf die Bildmitte".
- `app/ui/viewport.py:3492 ff.` — `_fit_once_for()`: eingepasst wird beim
  ersten Aufbau, „Jeder weitere Aufbau lässt die Kamera in Ruhe".

**Was stattdessen dastehen müsste:** „Einpassen meint die Körper, das Mausrad
zoomt zum Zeiger, und die Kamera überlebt Auswahl und Neuberechnung."

---

## 3 — Keine Formsprache: sechs `setStyleSheet`, zwei Schriftgrößen, 50 Abstände ohne Raster (2.0)

**Urteil: überholt** — in allen drei Teilen.

**Beleg:**
- `app/ui/style.py` (496 Zeilen, angelegt in Commit `2a8fc69` „Eine Formsprache,
  wo bisher Qt-Vorgaben standen"). `apply_style()` (`:493–496`) legt **ein**
  Stylesheet über die ganze Anwendung; `app/ui/theme.py:147–159`
  (`apply_theme`) setzt Palette und Stylesheet zusammen.
- Das im Dokument geforderte `app/ui/style.qss` gibt es **bewusst nicht** —
  `app/ui/style.py:12–15` begründet, warum das Stylesheet in Python lebt.
- `grep -rn setStyleSheet app/ --include=*.py | wc -l` → **14** (statt sechs),
  einer davon der globale.
- Typografie-Skala: `app/ui/style.py:LEVELS = ("title","section","body",
  "caption")` mit `SCALE` als relative Faktoren. Keine feste px-Schriftgröße
  mehr im Code (`grep setPointSize` findet nur fünf relative Anpassungen in
  `loading.py`, `sketch_editor.py`, `splash.py`).
- Abstandsraster: `app/ui/style.py:SPACE = 4` mit `TIGHT/NORMAL/ROOMY/WIDE`;
  `tests/test_style.py::test_the_grid_is_one_number_and_its_multiples` und
  `::test_no_layout_invents_its_own_distance` halten es fest. Die Zahl der
  `setSpacing`/`setContentsMargins`-Aufrufe ist auf 118 gestiegen — sie folgen
  jetzt aber alle dem Raster, was der Test prüft.

**Was stattdessen dastehen müsste:** „Die Anwendung hat eine Formsprache:
ein Stylesheet aus `app/ui/style.py`, vier Typografiestufen relativ zur
Systemschrift und ein 4-px-Raster, dessen Einhaltung `tests/test_style.py`
prüft."

---

## 4 — Die Live-Vorschau existiert bereits (2.0.3)

**Behauptung:** `main_window.py:2322–2340`, 300-ms-Timer auf
`session.preview_async`, Ergebnis an `viewport.show_difference`;
`evaluate_cached` bei 0,28 ms; sichtbar ist sie nicht, es fehlt jeder Hinweis
auf eine laufende Vorschau.

**Urteil: überholt** — die Sache stimmt, die Ortsangabe und die Diagnose nicht.

**Beleg:**
- Die Verdrahtung liegt heute in `app/ui/main_window.py:4852–4879`
  (`_wire_preview`), nicht bei 2322. Der 300-ms-Timer und `preview_async`
  stehen dort unverändert.
- Der fehlende Hinweis ist gebaut: `app/ui/main_window.py:4880–4886`
  (`_show_preview`) ruft `viewport.mark_preview(tr("Vorschau — noch nicht
  übernommen"), tr("Leertaste halten: vorher"))`; die Methode selbst liegt in
  `app/ui/viewport.py:2904`. Damit sind auch die „Zu tun"-Punkte 3 und 4 des
  Abschnitts erledigt.
- `evaluate_cached` steht als Budgetposten in `tests/test_performance.py:299`;
  die Zahl 0,28 ms ist eine Einzelmessung von damals und heute nicht mehr die
  Aussage.

**Was stattdessen dastehen müsste:** „Die Live-Vorschau läuft, ist
gekennzeichnet („Vorschau — noch nicht übernommen") und hat den
Vorher/Nachher-Griff auf der Leertaste (`main_window.py:_wire_preview`,
`_show_preview`)."

---

## 5 — Der Op-Dialog ist modal und öffnet mittig über dem Teil (2.0.3)

**Urteil: überholt**

**Beleg:** `app/ui/main_window.py:4824–4851` — `_open_operation_dialog` ruft
`dialog.show()`, nicht `exec()`. Der Docstring benennt die alte Lage wörtlich:
„`exec()` blockierte jede Kameraführung, solange der Dialog offen war … Der
Stapel wird ohnehin erst bei ‚Übernehmen' angefasst — die Sperre schützte
nichts." Ein zweiter offener Operationsdialog wird an derselben Stelle
verhindert (`previous.reject()`).

Die verbliebenen `.exec()`-Aufrufe in `app/ui/` betreffen Meldungsboxen,
Katalog, Einstellungen, Befehlspalette und den Skizzeneditor — keinen
Operationsdialog.

**Was stattdessen dastehen müsste:** „Operationsdialoge sind nicht modal
(`_open_operation_dialog`); drehen, zoomen und einpassen bleiben erreichbar,
während die Vorschau läuft."

---

## 6 — *Datei → Neu* zeigt den Startbildschirm nicht wieder (2.2)

**Urteil: überholt**

**Beleg:** `app/ui/main_window.py:2210–2222` — `action_new()` besteht heute aus
`self._show_start_screen(True)`; der Docstring beschreibt genau den Fund des
Konzepts als behoben. Dazu `action_examples()` (`:2224–2236`) als
*Hilfe → Beispiele*, ebenfalls ein „Zu tun" dieses Abschnitts. Commit
`65b218e` „Sechs kleine Funde der Durchsicht, jeder mit seinem Test".

**Was stattdessen dastehen müsste:** „*Neu* führt auf den Startbildschirm;
*Hilfe → Beispiele* erreicht ihn jederzeit."

---

## 7 — Das helle Thema ist unfertig (2.3)

**Urteil: überholt**

**Beleg:**
- `app/ui/theme.py:147–166` — `apply_theme` setzt Palette **und** Stylesheet
  über die ganze `QApplication` („Schaltet die ganze Anwendung um. Wirkt
  sofort."), plus Zeiger für jedes Fenster.
- Symbole: `app/ui/icons.py:15–20` — `currentColor` wird beim Laden gegen die
  Textfarbe ersetzt, „ein Satz Symbole für beide Themen, keiner, der im
  dunklen unsichtbar wird". Geprüft von
  `tests/test_style.py::test_an_icon_takes_its_colour_when_it_is_drawn` und
  `::test_a_cached_pixmap_is_dropped_when_the_theme_turns`.
- Auch die Tour wirft ihre zwischengespeicherten Zeichen beim Themenwechsel
  weg: `app/ui/tour.py:changeEvent` (Reaktion auf `PaletteChange`).

**Was stattdessen dastehen müsste:** „Ein Themenwechsel erreicht die ganze
Anwendung; die Symbole nehmen ihre Farbe aus dem Thema."

---

## 8 — Vier Farbwelten, neun eigene Viewport-Konstanten, Auswahl blau gegen orange (2.4)

**Urteil: überholt**

**Beleg:**
- `app/ui/palette.py:53–70` — `ROLES` führt heute `select`, `measure`, `info`,
  `warning`, `error`, `layer`, `island`, `overhang`, `feature`, `backface`,
  `axis_x`, `axis_y` an **einer** Stelle. Dazu `ROLES_ON_LIGHT` (`:86`) und
  `ROLES_ON_DARK` (`:99`) mit ausgerechneten WCAG-Werten.
- `app/ui/viewport.py:217–219, 339, 368–373` — `SELECTED_COLOUR`,
  `BACKFACE_COLOUR`, `MEASURE_COLOUR`, `LAYER_COLOUR`, `ISLAND_COLOUR`,
  `OVERHANG_COLOUR`, `FEATURE_LABEL_COLOUR` lesen alle aus `ROLES[...]`.
- Der im Konzept geforderte Test existiert:
  `tests/test_palette.py:82–101 ::test_a_role_has_one_colour_across_the_interface`
  („Jedes Modul führte seine eigenen Konstanten: ‚Warnung' hatte drei Werte,
  ‚Hinweis' fünf.").
- Eine Auswahlfarbe:
  `tests/test_palette.py:104–115 ::test_selecting_looks_the_same_in_the_list_and_in_the_view`
  prüft `theme["highlight"] == ROLES["select"]` für **beide** Themen. `ROLES
  ["select"] == "#f0a54a"` — der Baum färbt jetzt im Bernstein des Viewports,
  nicht mehr in Qt-Blau. Damit ist auch „Markenfarbe in die Oberfläche holen"
  erledigt. Commit `91c8274` „Eine Auswahl war blau in der Liste und orange im
  Bild".

**Was stattdessen dastehen müsste:** „Jede bedeutungstragende Farbe hat einen
Wert, und der steht in `palette.py:ROLES`; `viewport.py` liest von dort. Ein
Test zählt jede Rolle einmal nach, ein zweiter hält Baum und Viewport auf
derselben Auswahlfarbe."

---

## 9 — `test_the_viewport_follows_the_theme` prüft nur, dass `viewport_colours()` unterschiedliche Werte liefert (2.4)

**Urteil: überholt**

**Beleg:** `tests/test_theme_and_palette.py:189–207` — der Test prüft heute
vier Kontrastverhältnisse (Körper gegen Hintergrund ≥ 1,8; Bettraster gegen
Grund ≥ 1,4; Grund gegen Hintergrund ≥ 1,1; Kante gegen Körper ≥ 4,0), nicht
„unterschiedliche Werte". Die Lücke, auf die das Konzept zeigt — die
Modulkonstanten —, deckt seit `tests/test_palette.py:82` ein eigener Test ab.

**Was stattdessen dastehen müsste:** Der Satz kann ersatzlos weg; die Aussage
war ein Argument für einen Test, den es inzwischen gibt.

---

## 10 — Fünf von sieben Touren beginnen mit einem Beobachtungsschritt (3.1–3.3)

**Urteil: überholt** — und die Zahl „sieben" stimmt heute ebenfalls nicht.

**Beleg:**
- `app/ui/tour.py:285–313` — die Weiterschaltung prüft nicht mehr nur den
  aktuellen Schritt. Der Kommentar an Ort und Stelle: „Ein Leseschritt hält
  nur auf, solange nichts dahinter geschehen ist. Wurde die Handlung eines
  späteren Schritts erkannt, ist auch dieser vorbei — sonst stünde die Tour auf
  ‚Schritt 1 von 5', während der Nutzer längst Schritt 2 getan hat."
  Das ist genau die im Konzept als billiger bezeichnete zweite Lösung.
- Hervorhebung des Ziel-Elements: `app/core/tour.py:TourStep.shows`
  („Die Oberfläche lässt den genannten Bereich kurz aufleuchten") und
  `app/ui/tour.py:401 _point_at_current()`.
- Weg 3 Schritt 3 (`app/core/tour.py:287–293`, Text unverändert „klicken Sie
  eine Fläche an, dann Rechtsklick → Bohrung setzen") ist ausführbar, seit
  Klick und Kontextmenü stehen (siehe Befund 1).
- **Zahl:** `app/core/examples.py:EXAMPLES` führt heute **neun** Beispiele
  (`weg1-halterung-anpassen`, `weg2-halter-konstruieren`,
  `weg3-generiert-aufbereiten`, `weg4-figur-formen`, `gehaeuse-mit-bausteinen`,
  `schild-zweifarbig`, `drucker-kalibrieren`, `aushoehlen-und-teilen`,
  `dose-mit-deckel`) und `app/core/tour.py` neun Touren (`grep -c example_id=`
  → 9). Das Dokument sagt an sechs Stellen „sieben".

**Was stattdessen dastehen müsste:** „Neun Beispielprojekte mit neun Touren.
Ein Leseschritt hält die Tour nicht mehr auf, und jeder Schritt lässt den
Bereich aufleuchten, von dem er spricht."

---

## 11 — Im Skizzeneditor bewirken L, R und C nichts (Teil 4)

**Behauptung:** `app/ui/shortcut_schemes.py` deckt nur Modellieren ab
(E, Q, F, C, M, R, H, P, S).

**Urteil: überholt**

**Beleg:**
- `app/ui/sketch_editor.py:1960–1998` — `TOOL_KEYS` (`Esc` Auswählen, `L`
  Linie, `C` Kreis, `A` Bogen, `P` Punkt, `S` Spline, `T` Trimmen),
  `ACTION_KEYS` (`R` Rechteck, `D` Bemaßung, `O` Versetzen, `X`
  Konstruktionsgeometrie), `VIEW_KEYS` (`Home`), `PLANE_KEYS` (`1`/`2`/`3`).
  Das ist die im Konzept geforderte Liste `L R C A D T O X` vollständig.
- Kontextabhängig: derselbe Kommentar sagt „Sie gelten **nur im
  Skizzenmodus**. Außerhalb liegen R und C auf Drehen und Fasen." Umgesetzt
  über `Qt.ShortcutContext.WidgetWithChildrenShortcut`
  (`app/ui/sketch_editor.py:2395–2441`).
- Commit `2874b77` „Beim Zeichnen wusste man nicht, wo man ist".
- `app/ui/shortcut_schemes.py` deckt weiterhin nur Modellieren ab — das ist
  jetzt richtig so und kein Mangel mehr, weil die Zeichenkürzel im Editor
  liegen.

**Was stattdessen dastehen müsste:** „Die Zeichenkürzel liegen wie in Fusion
und gelten nur im Skizzenmodus; die Modellierbelegung bleibt in
`shortcut_schemes.py` und kollidiert deshalb nicht mehr."

---

## 12 — Agentenregel „(§39)" im `doc`-Feld einer Operation (Teil 6)

**Behauptung:** `primitive_ops.py:78`, dem Nutzer angezeigt.

**Urteil: überholt**

**Beleg:**
- `app/core/geom/primitive_ops.py:80` — an der Stelle steht nur noch der
  Kommentar: „‚Erst in der Bausteinbibliothek suchen' stand hier und richtete
  sich an …". Der Satz selbst lebt jetzt allein in
  `app/core/knowledge/data/rules.toml:256`.
- Der im Konzept geforderte Test existiert:
  `tests/test_registry_consistency.py:72–81` —
  `assert "§" not in text, f"{spec.name}: §-Verweis im Nutzertext"`, mit der
  Begründung „‚(§39)', ‚(§30)', ‚(§32)' standen in Dialogtexten und Befunden".
- `grep -rn 'doc=_("[^"]*§' app/core/` findet **keinen** Treffer mehr.

**Was stattdessen dastehen müsste:** „Nutzertext und Agentenregel sind
getrennt; ein Test lehnt jeden §-Verweis in `title`, `doc` und Befund ab."

---

## 13 — Der Tastenkürzel-Dialog: 17 Befehle, englische Kürzel, falsches Strg+G (Teil 6)

**Urteil: überholt**

**Beleg:** `app/ui/shortcuts_window.py`
- Quelle: `entries()` (`:32–58`) liest die **Menüleiste**, nicht mehr zwei
  Teillisten. Der Docstring nennt genau den Fund: „Die fünfzehn Tasten für
  Darstellung (`1` bis `6`) und Kameravorgaben (`Strg+0` bis `Strg+6`) gehen
  weder durch die eine noch durch die andere — sie standen in keiner
  Übersicht".
- Sprache: `:74` — `sequence.toString(QKeySequence.SequenceFormat.NativeText)`,
  mit dem Kommentar „Vorher stand hier der rohe Deklarationstext, und damit
  sprach die Übersicht englisch, während das Menü deutsch sprach."
- Strg+G: `:114` — „Das Kürzel kommt von der Aktion selbst. Hier stand
  ‚Strg+G', und das …".

**Was stattdessen dastehen müsste:** „Die Kürzelübersicht wird aus der
Menüleiste erzeugt, zeigt die Tasten in `NativeText` und nennt die
Befehlspalette mit dem Kürzel ihrer eigenen Aktion."

---

## 14 — „Neunundfünfzig Commits, Suite bei 2736 Tests … Damit ist das Konzept abgearbeitet" (Stand-Abschnitt)

**Urteil: überholt**

**Beleg:**
- `git log --since=2026-08-05 --oneline | wc -l` → **520** Commits seit dem
  Stichtag des Nachtrags (686 seit dem 01.08.2026).
- `.venv/Scripts/python.exe -m pytest -q --collect-only` → **4246 tests
  collected** (statt 2736).
- Der Schlusssatz „Was bleibt, ist der nächste Lauf durch die Anwendung" ist
  eingelöst: `konzept-erstnutzer-2026-08.md` (dreizehn Bedienläufe am
  13./14.08.2026) und `konzept-durchsicht-2026-08-14.md` (Stand 14.08.2026)
  sind genau dieser Lauf, jeweils mit eigener Befundliste.
- Auch die Nebenzahlen der Nachbarunterlagen sind weitergezogen:
  `ROADMAP.md:3339` spricht von „77 Operationen",
  `konzept-durchsicht-2026-08-14.md` von 84 — heute sind es **85**
  (`load_operations(); len(REGISTRY.all())`).

**Was stattdessen dastehen müsste:** Der Stand-Abschnitt braucht eine
Datumsklammer und den Hinweis, dass er nur bis zum 05.08.2026 gilt; die
Zahlensätze gehören ersetzt oder gestrichen, weil sie im Wochentakt altern.

---

## 15 — „Teilweise" offen (Stand-Abschnitt)

**Behauptung:** Import legt nicht auf die Platte (`place_on_bed` = `False`);
kein Absturzprotokoll; Merkmalsbeschriftungen dauerhaft statt beim Überfahren;
Rückmeldung in der Statusleiste übersehbar.

**Urteil: stimmt** — alle vier Punkte sind auch heute offen.

**Beleg:**
- `app/core/ingest/ops.py:53–57` — `place_on_bed: bool = param(..., default=
  False, ...)`; ebenso `app/core/ingest/loader.py:161`
  (`place_on_bed: bool = False`). Unverändert.
- Kein Absturzprotokoll: `grep -rn "excepthook\|faulthandler" app/` findet
  nichts; `app/ui/app.py:main()` installiert keinen Hook. Es gibt nur das
  rotierende `app.log` aus `app/core/log.py` (§33.2), das eine
  Zugriffsverletzung ohne Python-Ausnahme nicht auffängt.
- Merkmalsbeschriftungen: `app/ui/viewport.py:2765–2783` —
  `add_point_labels(..., always_visible=True, name="features")` zeichnet alle
  eingeblendeten Merkmale dauerhaft; es gibt keine Beschriftung beim
  Überfahren. (`_hover_timer` in `:1096–1105` dient dem Zeigerwechsel und dem
  Pinselradius, nicht der Beschriftung.)
- Statusleiste: `app/ui/main_window.py:5180–5199` — `announce()` schreibt
  weiterhin ausschließlich in `status_message`. Ein zweiter Ort (Einblendung
  im Viewport oder am Menü) existiert nicht; `viewport.mark_preview` ist für
  die Vorschau da, nicht für Handlungsergebnisse.

**Was stattdessen dastehen müsste:** Der Abschnitt kann so bleiben — er ist
der einzige Teil des Dokuments, der noch trägt. Sinnvoll wäre nur, ihn als
das kenntlich zu machen, was er ist: die vier verbliebenen Punkte, während
alles darüber erledigt ist.

---

## Widersprüche innerhalb des Dokuments

Das Muster, vor dem die Aufgabenstellung warnt, ist hier der Normalfall und
nicht die Ausnahme:

1. **Teil 1.1 gegen Stand-Punkt 1** — der Haupttext sagt „Das Auswählen wurde
   nie angeschlossen", der Nachtrag zählt Punkt 1 unter „Erledigt". Beide
   stehen unkorrigiert nebeneinander.
2. **Teil 1.2 gegen Stand** — „Das Mausrad zoomt zur Bildmitte" gegen „das
   Mausrad zoomt jetzt wirklich dorthin, wo der Zeiger steht".
3. **Teil 2.0/2.3/2.4 gegen Stand** — „Es gibt keine Formsprache", „Das helle
   Thema ist unfertig", „vier Farbwelten, kein System" gegen „Die Anwendung
   hat eine Formsprache … das helle Thema kommt überall an".
4. **Teil 4 gegen Stand** — die Vergleichstabelle führt „Ändern-Gruppe: fehlt
   ganz", „Bezugnahme: fehlt ganz", „Kürzel: keine"; der Nachtrag meldet
   dieselben fünf Punkte als durch.
5. **Teil 7 gegen Stand** — „Die Seite *Das Fenster* beschreibt eine
   Navigation, die es nicht gibt" gegen „Die Seite *Das Fenster* stimmt
   wieder".
6. **Teil 10 gegen Stand** — die gesamte Reihenfolge 1–14 und 20–25 ist im
   Nachtrag abgehakt, steht aber weiter als Arbeitsliste da.

---

## Was das Dokument heute wert ist

Als Arbeitsliste: nichts mehr — 14 von 15 prüfbaren Behauptungen sind erledigt,
die fünfzehnte steht bereits im eigenen Nachtrag als offen. Als Beleg dafür,
**warum** die Oberfläche heute so aussieht, wie sie aussieht, ist es weiterhin
wertvoll: die Begründungen in `style.py`, `palette.py`, `viewport.py` und
`tour.py` sind wörtlich die Befunde dieses Dokuments. Die ehrlichste
Behandlung wäre eine Datumsklammer oben („Zustand vom 04.08.2026, vollständig
abgearbeitet — siehe die Nachfolger `konzept-durchsicht-2026-08-14.md` und
`konzept-erstnutzer-2026-08.md`") statt einer Zeile-für-Zeile-Korrektur.
