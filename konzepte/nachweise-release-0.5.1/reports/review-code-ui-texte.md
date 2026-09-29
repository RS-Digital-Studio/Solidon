# Durchsicht Code: Pakete ui-handbuch-051 und texte-051 (Release 0.5.1)

Unabhängige Code-Durchsicht, nur lesend im Hauptbaum. Eigene Arbeitsbäume:
`wt-revcode` (`bbc16f9ad`), `wt-revcode2` (`ec0298b15`), `wt-revbase` (`aa82afdff`),
`wt-revmerge` (main `cbef27715` + `ec0298b15`, `merge --no-commit`); nach der Durchsicht
wieder entfernt. Alle Läufe gepinnt über `skripte/lauf-wt.sh`, Protokolle
`laeufe/rev-code-*.txt`. Sonden gesichert unter `sonden/review-code/`:
`test_zz_review_probe_*.py` (liefen als `tests/test_zz_review_probe*.py` im jeweiligen
Baum) und `probe_bounded.py`, `probe_focus.py`, `probe_tracking.py` (offscreen-Widget,
Nutzerordner in Temp gebogen, `python <sonde>` aus dem Baum). Vom Textpaket nur die
Codeanteile; Texte und Übersetzungen prüft der zweite Prüfer.

## Urteil

- **ui-handbuch-051: mergebar ja.** Kein Blocker. U-1 bis U-5 vor dem Tag beheben
  (U-1 bis U-3 sind Verhaltensfehler der neuen Grenzablehnung, U-4/U-5 Unterlagen);
  beim Merge M-2.
- **texte-051: in dieser Form nicht mergebar.** T-1 bricht *Modell teilen* ab drei
  Stücken mit schräger Naht. Mit dem geprüften Patch `reports/review-code-t1-fix.patch`
  mergebar; beim Merge M-1 (Zahl 1343) und M-3.

## Blockiert den Merge

### T-1 texte — Automatisch teilen scheitert ab drei Stücken, sobald eine Naht schräg ist

- **Stelle:** `app/core/split.py:419-435` (`apply_planned`) schreibt `piece_count`,
  `number_a`, `number_b` in **jeden** Entwurf; `app/core/split.py:218` legt eine schräge
  Naht als `split_line` an (RM-080 T3); `app/core/geom/prepare_ops.py:16874-16961`
  (`SplitLineParams`) kennt die drei Felder nicht, `:16985-17013` (`split_line`) reicht
  sie nicht weiter. `History._check_params` (`history.py:2609-2620`) weist sie ab.
- **Beleg:** Sonde mit dem Z-Körper aus `test_autosplit.z_shape`, erster Stab 250 mm
  länger, `centauri-carbon-2` (`laeufe/rev-code-t3.txt`):

      PROBE centauri-carbon-2 L250.0 R0.0: drafts=['split_pinned', 'split_line']
      PROBE centauri-carbon-2 L250.0 R0.0: APPLY FAILED ValidationError: Die Eingabe war so nicht verwendbar.: Diesen Parameter gibt es bei dieser Operation nicht.
      PROBE centauri-carbon-2 L250.0 R0.0: field=number_a

  Derselbe Plan am Stand davor `aa82afdff` (`rev-code-t3-basis.txt`): drei Stücke
  `['1_z A · Stifte', '1_z B A · Stifte', '1_z B B · Löcher']` — Regression. Am Merge-Stand
  main + texte ebenso rot (`rev-code-m2.txt`).
- **Kundensicht:** Ein langes Teil, dessen letzte Naht schräg besser liegt (Winkel,
  Strebe, Z-Form), lässt sich nicht mehr automatisch teilen; der Prüfbericht nennt einen
  Parameter, den der Kunde nie gesetzt hat.
- **Fix (geprüft):** `reports/review-code-t1-fix.patch` — die drei Felder als
  `_piece_count_param()`, `_number_a_param()`, `_number_b_param()` (Muster
  `_first_pin_param`, eine Quelle für beide Operationen, keine neuen Texte) in
  `SplitPinnedParams` **und** `SplitLineParams`, `split_line` reicht `numbers` und
  `piece_count` an `_cut_and_pin`. Regressionstest
  `test_autosplit.py::test_a_run_with_a_tilted_seam_numbers_its_pieces_too` (Z-Körper mit
  `longer=250`, Plan `['split_pinned', 'split_line']`, Namen „1 von 3 … 3 von 3“): ohne Fix
  rot am Merge-Stand (`rev-code-t8-ohnefix.txt`, dieselbe `ValidationError`), mit Fix grün
  (`rev-code-t8.txt`); mit Fix `test_registry_consistency.py`, `test_split_line.py` und die
  RM-229-Tests 1076 passed, einzig die Parameterzahl rot (`rev-code-t4.txt`, siehe M-1);
  `ruff check`/`format --check` grün, mypy nicht gefahren.

## Beim Merge

### M-1 texte + main — Parameterzahl in `oberflaeche.md`

- `.claude/rules/oberflaeche.md:58`, Wächter `test_registry_consistency.py:1084-1112`.
  main hat mit `6e8d0bedc` (RM-279) 1334 → 1337 gesetzt, das Textpaket auf seiner Basis
  ebenfalls 1334 → 1337. Gleiche Zeile, kein Konflikt, falsche Summe.
- **Beleg:** am Merge-Stand main + texte (`rev-code-m1.txt`):
  `AssertionError: oberflaeche.md nennt 1337 Parameter, gezählt sind 1340`.
- **Fix:** nach dem Merge 1340 eintragen, mit dem T-1-Patch 1343.

### M-2 ui + main — Konflikt in `part_ranges.toml`

- `git merge-tree --write-tree main bbc16f9ad`: `CONFLICT (content)` in
  `app/core/knowledge/data/part_ranges.toml`. Das Paket hat für neun Bausteine aus
  `fasteners.py`/`testbodies.py` nur den Abdruck neu gefahren; main hat `fasteners.py`
  seitdem selbst geändert (`06dc3a5b9`, `b42806f06`, `94aa590eb`, `9e3a8d8a9`). Keine Seite
  stimmt am Merge-Stand.
- **Fix:** nicht von Hand auflösen, sondern am Merge-Stand `tools/check_part_ranges.py`
  für die Bausteine fahren, deren Abdruck der Test als veraltet meldet.

### M-3 ui + texte — Konflikt in `it.json`

- `git merge-tree --write-tree bbc16f9ad ec0298b15`: zwei Konfliktstücke in
  `app/i18n/locales/it.json` (bei „Mit dem gewählten Schritt …“ und „Strg+Z …“).
- **Auflösung:** die bestehenden Einträge in der Fassung des Textpakets („Trascina …“,
  „… c'è un passaggio …“), die sechs neuen Einträge des Oberflächenpakets dazu, die zwei
  alten Löschsätze („… spätere abhängige Schritte gelöscht. Strg+Z …“) entfallen, weil das
  Oberflächenpaket ihren Schlüssel entfernt hat. Die neuen it-Texte des Oberflächenpakets
  sprechen schon „passaggio“ und keine Anrede; „L’inserto adatto …“ trägt einen
  typografischen Apostroph (Frage an den Textprüfer, `test_no_entry_mixes_two_apostrophes`
  prüft nur Mischung).

## Vor dem Tag beheben

### U-1 ui — Parameterleiste verwirft die ganze Eingabe bei einer Nachkommastelle zu viel

- **Stelle:** `app/ui/labels.py:535-543` (`BoundedSpin.validate` macht aus **jedem**
  `Invalid` mit lesbarer Zahl ein `Intermediate`, auch bei zu vielen Nachkommastellen),
  wirksam in `app/ui/panels.py:3514-3520` (Parameterleiste, `setKeyboardTracking(False)`).
- **Beleg:** `laeufe/rev-code-u5.txt`, Feld 0,1–100, Wert 40, Anzeige zwei Stellen:

      NumberSpin  tracking=False typed='12,34'  enter=('12,34', 12.34) tab-away-after-0,125=('0,12', 0.12)
      BoundedSpin tracking=False typed='12,345' enter=('40,00', 40.0)  tab-away-after-0,125=('40,00', 40.0)

  Mit `keyboardTracking` (Operationsdialog) bleibt es bei 12,34 wie vorher.
- **Kundensicht:** Wandstärke 2,00, getippt „1,875“, Eingabetaste — im Feld steht wieder
  2,00, das Maß bleibt, kein Wort. Vorher kam 1,87 an. Genau die stille Verwerfung, die das
  Paket abschaffen will.
- **Fix:** In `validate` nur dann auf `Intermediate` heben, wenn die Zahl außerhalb der
  Grenzen liegt **und** höchstens `decimals()` Nachkommastellen hat; sonst Qts Urteil.
  Test in `test_value_labels.py`: `BoundedSpin`, `setKeyboardTracking(False)`, „12,345“ +
  Eingabetaste → 12,34 wie `NumberSpin`.

### U-2 ui — Stückzahl über der Grenze: Knopf aktiv, Klick ohne Wirkung

- **Stelle:** `app/ui/op_dialog.py:2011-2027` (`_follow_source_pending` nimmt `CountField`
  aus der Ablehnungskette aus) gegen `:2104-2107` (`can_accept` fragt `refusal()` auch am
  `CountField`). Zwei Stellen, eine Frage (`zwillinge.md`).
- **Beleg:** `laeufe/rev-code-u1.txt`, *Objekt duplizieren*, Stückzahl 105 bei Höchstwert
  100: `hint='105 liegt über der Obergrenze 100.' button_enabled=True tooltip=''
  can_accept=False`. Ein Klick scheitert an `can_accept()` und geht in `preview_defer`
  (`main_window.py:18191-18228`): bei stehender Vorschau folgenlos, sonst mit der Zusage
  „Wird übernommen, sobald die Vorschau steht.“, die nicht eintritt (nach dem Code; der
  Klick selbst ist nicht am Fenster nachgestellt).
- **Fix:** die Ablehnung am `CountField` in dieselbe Kette (oder `CountField.valid` fragt
  `spin.refusal()`), eine Funktion für Knopfzustand und `can_accept`. Test: Stückzahl über
  dem Höchstwert sperrt den Knopf mit dem Satz.

### U-3 ui — Felder mit „wie gemessen“ nennen eine falsche Grenze

- **Stelle:** `app/ui/op_dialog.py:218-220` legt den Sonderwert eine Stelle unter das
  Minimum; `app/ui/labels.py:562-576` (`BoundedSpin.refusal`) nennt `self.minimum()`.
- **Beleg:** `laeufe/rev-code-u1.txt`:
  `resize_hole depth schema-min=0.0 … '-2,00 mm liegt unter der Untergrenze -0,01 mm.'`,
  `slot_hole diameter schema-min=0.2 … '0,10 mm liegt unter der Untergrenze 0,19 mm.'`.
- **Kundensicht:** *Bohrung ändern*, Tiefe (vorn im Dialog): Der Satz nennt −0,01 mm als
  Untergrenze, richtig ist 0.
- **Fix:** `ValueField.refusal()` im Zahlenmodus mit den Schemagrenzen (`_as_shown(entry.
  minimum)`/`maximum`) formulieren oder `BoundedSpin` eigene Ablehnungsgrenzen geben.
  Test über beide optionalen Felder mit Minimum.

### U-4 ui — Regeln widersprechen dem Code

- `.claude/rules/fenster.md:212-213`: „`mark_finding`: Ring in Auswahlfarbe vor dem
  Material“ — seit dem Paket `FINDING_COLOUR`, und `ansicht.md` sagt jetzt das Gegenteil.
  Ebenso `konzepte/begruendungen/regel-fenster.md:237`.
- `.claude/rules/dateiformat.md:63`: nennt `f"{tr('Parameter')} {name}"` als wörtlich
  gespeicherten Titel; das Paket speichert ihn übersetzbar (`session._parameter_title`).
- **Fix:** beide Stellen nachziehen.

### U-5 ui — Die neue Regel „Eine Grenze lehnt ab“ behauptet mehr, als gebaut ist

- `.claude/rules/oberflaeche.md` (neuer Absatz „Eine Grenze lehnt ab, sie kürzt nicht“):
  „Wo der Kunde Grenzen tippt, steht ein `labels.BoundedSpin`“. Das Merkmalfenster
  (`panels.py:5946-5955`, Grenzen aus `configure_feature_field` `:5996-6009`) und die
  Druckeinstellungen (`print_settings_dialog.py:1270-1271`, `setRange(field.minimum,
  field.maximum)`) sind `LengthSpin`/`NumberSpin` mit echten Grenzen und kürzen weiter
  still.
- **Fix vor dem Tag:** Satz auf die zwei gebauten Orte eingrenzen und den Rest als Punkt
  ins Register von `ROADMAP.md`; umstellen erst nach U-1.

## Nach 0.5.1

### T-2 texte — Zählung veraltet, wenn ein Schnitt des Laufs gelöscht wird

- `prepare_ops.py:340-345` (`stem_of`) liest die gespeicherte Zählung des Schritts.
- **Beleg:** `laeufe/rev-code-t11.txt`, Leiste 600 mm, drei Stücke, letzter Schnitt
  gelöscht: `['Leiste 1 von 3 · Stifte', 'Leiste · Löcher']`. Ausschalten des Schnitts
  wirkt nach dem Code gleich (nicht eigens nachgestellt).
- **Fix:** Zählung beim Löschen/Ausschalten nachführen oder bei Nummer 0 ohne weiteren
  Schnitt auf A/B zurückfallen; Punkt ins Register.

### U-6 ui — fx aus mit einem Ausdruck jenseits der Grenze klemmt still

- `op_dialog.py:559-571` (`_switch`): `setValue` klemmt, `_core` hält den Ausdruckswert.
- **Beleg:** `rev-code-u1.txt`: `PROBE-FX-OFF schema-max=1000.0 spin=1000.0 value=1000.0
  refusal='' hint=… visible=False`.
- **Fix:** die Zahl als Text ins Feld setzen, damit `BoundedSpin` sie ablehnt.

### U-7 ui — Sätze der Bausteine sagen an gemessenen Bohrungen eine Größe als Tatsache

- `placement.py:431-433` steht vor dem Zweig `status.source != "native"` (`:434-458`,
  Entscheidung Durchsicht 0.5.0: „Eine Messung nennt eine Größe als Einschätzung“). An
  einer STL heißt es jetzt „Bohrungsmaß: 5,20 mm (eingepasst). In diese Bohrung passt ein
  Innengewinde M6.“ bzw. „Diese Bohrung ist das Durchgangsloch einer Schraube M5.“ Satz
  und Vorauswahl stimmen überein (das war der Befund), nur die Einschätzung fehlt.
- **Fix:** `at_hole_advice` den Messstatus mitgeben oder für Messungen „vermutlich“
  formulieren — mit dem Textprüfer abstimmen.

### U-8 ui — Kurzhilfe einer Grenzänderung zeigt „40,00 mm → 40,00 mm“

- `panels.py:1109-1134` (`_changed_parameters`) vergleicht nur den Wert; `edit_parameter`
  (Grenzen, Einheit) trägt denselben Titel. **Fix:** gleiche Werte weglassen oder die
  geänderte Grenze nennen.

### U-9 ui — Test mit zu großem Namen

- `test_viewport_decisions.py::test_the_finding_mark_never_wears_the_colour_of_the_selection`
  vergleicht nur zwei Konstanten. Gegenprobe (Ring zurück auf `SELECTED_COLOUR`): bleibt
  grün (`rev-code-g1.txt`); rot wird nur der Fenstertest
  `test_a_finding_with_a_rim_outlines_the_new_face`. **Fix:** Namen auf das Geprüfte
  eingrenzen; die Zusage trägt der Fenstertest.

### T-3 texte — Verbotstests über geladene Kataloge ohne Mengenzusicherung

- `test_translations.py`: `test_french_names_the_escape_key_as_its_keyboard_does`,
  `test_italian_says_tu_outside_the_manual`, `test_no_entry_mixes_two_apostrophes` prüfen
  eine aus `read_catalog`/`_manual_only` erhobene Menge ohne „nicht leer“
  (`tests.md`, „Ein Verbotstest über eine leere Menge ist immer grün“). **Fix:** je eine
  Zeile `assert len(geprüft) > …`.

## Testqualität und Gegenproben

- **Alle neun neuen Fenstertests laufen grün** am Stand `bbc16f9ad` (`rev-code-w1.txt`
  5 passed, `rev-code-w2.txt` 4 passed; `-o faulthandler_timeout=120`, je höchstens fünf).
- **Gegenproben ui** (Verdrahtung zurückgenommen, `rev-code-g1.txt`, `rev-code-g2.txt`):
  `spec=spec` am `bore_advice`-Aufruf, `gizmo_build` in `set_gizmo`, `FINDING_COLOUR` am
  Ring, Absagezweig in `_answer_now`, `outline=` in `repair`, `_parameter_title` in
  `change_parameter`, `named_steps` in der Löschnachfrage, `BoundedSpin.validate` — jeder
  zugehörige Test wird rot. Grün bleiben die Kerntests, die nur die herausgezogene Funktion
  prüfen (`test_the_grip_draws_only_what_a_drag_can_do`,
  `test_a_parameter_change_is_named_as_the_panel_names_it`,
  `test_the_question_before_a_deletion_names_the_steps_that_go_with_it`, U-9): Die
  Verdrahtung sichern allein die Fenstertests — das Release-Tor muss sie fahren.
- **Gegenproben texte:** die neuen Wächter gegen die Kataloge von `aa82afdff`
  (`rev-code-t5.txt`): 13 rot (Werkzeug/Operation in fünf Sprachen, Échap, tu/Lei,
  Apostroph fr, Innenwand fr, Skizzenbild in vier Sprachen). RM-229: Zählung in
  `apply_planned` und `carries` zurückgenommen (`rev-code-t6.txt`): beide Tests rot.
- **Neue Kerntests ui** am Stand `bbc16f9ad`: 14 passed (`rev-code-u4.txt`).

## Geprüft ohne Befund

- **Löschnachfrage (Regel 19):** Die Liste kommt aus `removal_closure` — derselben
  Funktion, mit der `History.remove_operations` löscht — in Stapelfolge; Nummer und Titel
  wie im Verlauf. Parameter berührt das Löschen nicht. Passungen an verschwindenden Körpern
  gehen mit, ohne genannt zu werden; das war vorher genauso, Strg+Z holt sie zurück (kein
  Paketfehler, gegebenenfalls Registerpunkt).
- **Verlauf „Parameter Breite“:** nach Speichern, Laden und Sprachwechsel
  (`rev-code-u3.txt`): `de=Parameter Breite`, `en=Parameter Width`; der Titel reist als
  Struktur (`dateiformat.md`, übersetzbare Werte). Alte Projekte behalten ihren wörtlichen
  Titel.
- **Gewindegröße:** aus der Normteiltabelle (`standards`), über dieselben Funktionen wie
  die Vorauswahl (`size_for_*`); die Schranken im Satz „kein Normgewinde“ sind das
  Komplement derselben Bedingung; keine Streuzahl (Regel 7/8). Einziger Aufrufer mit
  `spec` fragt mit `ask=False`, eine Frage mit Antwortweg geht also nicht verloren.
- **Grenzablehnung und Ausdrücke:** Der Ausdrucksmodus vergleicht den ausgewerteten Wert
  (mm) mit den Schemagrenzen wie das Drehfeld; Division durch null endet als `AppError`
  und sperrt nichts. Fokuswechsel im Fenster und Fensterwechsel behalten die abgelehnte
  Zahl (`rev-code-u2.txt`). Einheiten: Zoll über `_as_shown`, Suffix im Satz.
- **Griff an der Fläche:** `_on_gizmo_released` nahm an einer Fläche schon vorher nur den
  Weg entlang der Normalen (`viewport.py:15141-15153`); was an Ringen und Querpfeilen
  gezogen wurde, verfiel. Es fehlt also kein Weg. Bausteinflächen behalten den vollen
  Griff (`part=`), der Ring um die Bohrachse (Langlochrichtung) hängt an Bohrungen, die
  weiter Ringe tragen. Kugel und Hohlraum ohne Ringe entspricht `rotate_feature.applies_to`
  und der Funktionsseite („drehen für alle außer der Kugelfläche“). `fits()` wird nur am
  Platzierungsgriff gefragt, der die Vorgaben behält.
- **Stelle zeigen:** Rand und Mitte reisen gemeinsam (`moved_findings`, Plattencache),
  werden in der Ansicht um denselben Versatz verschoben; Regel 18 erfüllt (Rand, Ring,
  Satz auf eigenem Grund). `CACHE_FORMAT_VERSION` blieb 31, obwohl Cache-Befunde jetzt
  einen Rand tragen — betrifft nur Entwicklercaches der Fassung 31: 0.5.0 lieferte 27,
  `make_guides.py` rechnet in einem frischen Nutzerordner.
- **Text aufbringen:** `_PreviewWorker` sendet `refused` vor `done(None)`; der
  Hauptfadenweg ebenso; ein echter Fehler behält Protokoll und Traceback.
- **RM-229:** alte Projekte rechnen dieselbe Geometrie, fehlende Felder → 0 → Buchstaben;
  `cache_version="1"` und `CACHE_FORMAT_VERSION` im Schlüssel (`hashing.py:116`) — kein
  alter Eintrag kann antworten. Zählung in der Folge der fertigen Stücke (A liegt auf der
  kleineren Seite), an Läufen mit 3, 4 und 5 Stücken nachgesehen (`rev-code-t2.txt`).
  Fremde Bausteinbohrungen zählen nicht als Verbinder (Bausteinmerkmale heißen
  `screw_hole_bore_1`, `rev-code-t7.txt`). Erste Stiftnummer und Passungen unverändert.
- **Regeln 1, 2, 3, 6, 10–15, 20–22:** kein Qt im Kern, keine Geometrie außerhalb einer
  Op, keine neuen Toleranzkonstanten, alle neuen Oberflächentexte über `tr()`/`_()`, keine
  Abhängigkeit, kein Formatwechsel (main steht ohnehin auf Format 37).

## Kundensicht

- **ui:** Die sieben Punkte lösen, was die Handbuchbilder zeigten; aus Kundensicht bleiben
  U-1 (Parameterleiste verwirft Nachkommastellen still), U-2 (Knopf ohne Wirkung) und U-3
  (falsche Zahl im Satz).
- **Handbuchsatz des Pakets** („Liegt eine getippte Zahl außerhalb der Grenzen, übernimmt
  Solidon sie nicht: Die Zahl bleibt markiert stehen, darunter steht die Grenze, und
  *Parameter ändern …* führt direkt dorthin.“): inhaltlich richtig für die Parameterleiste,
  der Knopf heißt so. „Dorthin“ bleibt unklar, und drei Glieder nach dem Doppelpunkt lesen
  sich wie eine Aufzählung. Kürzer: „Eine Zahl außerhalb der Grenzen übernimmt Solidon
  nicht. Darunter steht die Grenze, und *Parameter ändern …* öffnet sie.“ Erst nach U-1
  stimmt der Satz auch für Nachkommastellen.
- **texte:** „Wandleiste 2 von 3 · Stifte und Löcher“ sagt, was das Stück trägt; T-1 und
  T-2 sind die Stellen, an denen der Kunde etwas anderes sieht.
