# Review fix/welle4-baumleser (Prüfer rvw4)

Gegenstand: `bddfd5fc1` auf `1e4dec783` (5 Dateien), dazu der Merge
`e79410c55` (welle4 `bb269dc54` in den Zweig). Worktree `F:\sl-w4fix`, nur
gelesen. Alle Läufe auf den Kernen außer 8–11 gepinnt, Exit-Code aus der Datei.

**Urteil: kann landen.** Es gibt keinen schweren und keinen mittleren Fund. Die
zwei niedrigen Funde (N1, N2) halten die Landung nicht auf.

## Funde

**N1 (niedrig): Das Warten speichert sein Ergebnis, sichert den Leerlauf aber nicht zu.**
Stelle: `tests/test_filament_workflow.py:1064-1070`.
`idle` erscheint nur in der Fehlermeldung. Auf dem Erfolgsweg liest es
niemand, und der Test sichert nirgends zu, dass die feine Rechnung endete,
bevor er `session.last_result` liest (Z. 1076). Die Form genügt dem Wächter,
weil er Zuweisungen zulässt. Seine Absicht („sichert zu, dass er eintrat“,
`test_toolchain.py:920`) erfüllt sie nur halb.

Die handgebaute Schleife ist ein Zwilling von `tests/ui_helpers.wait_until`,
das dieselbe Datei an Z. 923 schon benutzt. Sie hat außerdem eine andere Frist:
höchstens rund 20 s statt 60 s. Bei leerlaufender Sitzung kehrt
`wait_for_idle(100)` sofort zurück (`session.py:6904`), und die 200 Runden sind
dann in Millisekunden vorbei.

Das tatsächliche Risiko ist klein. `_export_when_current`
(`main_window.py:10263-10271`) schreibt nur, wenn `session.busy` falsch ist, und
damit ist ein gefülltes `workers` praktisch Leerlauf.

Fix: Statt der Schleife
`wait_until(qt_app, lambda: bool(workers))`, danach
`assert session.wait_for_idle(60_000)` vor Z. 1071. Dieser Vorschlag ist nicht
gefahren, weil der Baum nur gelesen werden durfte.

**N2 (niedrig, Kundensicht): Der Knopf öffnet die Druckeinstellungen ohne Zielzeile.**
Stelle: `app/core/export/writer.py:3115` und `:3131` (am Merge `:3118` und `:3134`).
Der Weg ist verdrahtet: `Finding.suggestions` → `panels.actions_for`
(Vorschläge vor `FINDING_ACTIONS`, CANCEL gefiltert) → Prüfberichtsknopf
`_run_action_for` → `dialogs.handlers_of` → `main_window.py:27082`
`action_print_settings(field=values.get("field"))`. Die Befunde erreichen den
Bericht über `writer.py:2865` und `main_window._export_done:10407`. Weil in
`values` kein `field` steht, öffnet sich der Dialog oben, ohne gehobene Zeile.

- **Bäume:** Der richtige Ort, denn die Stützart ist eine Druckeinstellung.
  Mit `"field": "support.style"` in `values` hebt der Dialog die Zeile
  (`show_setting`, `print_settings_dialog.py:4428`; Muster RM-312 in
  `main_window.py:9591`). Neuer Text ist dafür nicht nötig.
- **Turm:** Der Satz nennt „eine eigene Platte“ als Weg. Die Platte setzt aber
  *Verschieben* (`translate_object`, Parameter `plate`, `geom/ops.py` um
  Z. 420/445), nicht der Druckdialog. Dort hilft nur das Abschalten der
  feinen Schichten. Ehrlicher wäre `"field": "layers.fine_layer_height"`
  (Feld in `print_fields.py:172`; ob der Dialog es hebt, habe ich nicht
  geprüft). Ein eigener Knopf „Auf eine eigene Platte legen“ bräuchte Handler
  und Text in sechs Katalogen und gehört als Registerpunkt in `ROADMAP.md`,
  nicht in diesen Fix.

Regel 17 ist für beide Befunde erfüllt: Es gibt einen Weg.

## Die vier Prüfpunkte

**(1) Der Umzug ist verhaltensgleich, und es gibt keinen Zyklus.**
- AST-Vergleich mit `ast_compare.py`: Alle 21 Testfunktionen und die
  verbliebenen Helfer (`captured`, `_bound_middle`, `_profile`, `_record`) sind
  nach der Umbenennung AST-identisch. Die acht verschobenen Helfer
  (`edge_pair_mesh/brep`, `edge_pair`, `edge_document`, `edge_registry`,
  `EdgeChooser`, `right_box`, `left_box`) gleichen den alten, wenn man von
  Docstring und den lokalen Importen in `edge_registry` absieht
  (`load_operations`, `REGISTRY`: dieselben Objekte). Die Konstanten
  40/30/20, 0.004 und `COLLIDING_EDGE_KEY` sind wortgleich. Die Aliase in
  `test_edge_binding.py:60-62` zeigen auf dieselben Objekte.
- Testzahl von `test_edge_binding.py`: vorher 44, nachher 44, die Knoten-IDs
  sind identisch (`diff` leer).
- RM-706-Test: `edge._profile()` ist zu `profiles.make_profile("centauri-carbon-2", "petg")` geworden, was derselbe Wert ist.
- Importe: `app.core.registry` ist schon geladen, wenn die alte `helpers.py`
  ihre `app`-Module importiert hat (`import_probe.py pre`). `EdgeTarget` und
  `OpContext` liegen in Modulen, die schon importiert sind. Es kommt also kein
  neues Modul dazu und kein Zyklus entsteht.
- Importzeit `tests.helpers` (frische Prozesse, im Wechsel, n=8 je Seite):
  alt im Mittel 1,071 s (min 0,980 s), neu 1,067 s (min 1,000 s). Ein
  Unterschied ist nicht messbar.

**(2)** Siehe N2: Der Knopf wird angeboten und führt in den Druckdialog. Für
die Bäume ist das der richtige Weg, für den Turm nur ein Teilweg.

**(3)** Siehe N1: Das Ergebnis dient nur der Diagnose, eine Zusicherung des
Leerlaufs fehlt.

**(4) Läufe**

| Stand | Lauf | Ergebnis | Exit |
|---|---|---|---|
| `bddfd5fc1` | toolchain + finding_ways + edge_binding + usage_stored_inputs, ohne Fenster | 253 bestanden + 1 übersprungen = 254 gesammelt | 0 |
| `bddfd5fc1` | `test_filament_workflow.py` mit Fenster (`-m "not performance"`) | 39/39 | 0 |
| `e79410c55` | beide Wächter + finding_ways + edge_binding + usage_stored_inputs | 92/92 | 0 |
| `e79410c55` | `test_toolchain.py` mit `-rs` | 163 bestanden, 1 übersprungen | 0 |
| `e79410c55` | `test_export.py`, die fünf Tests zu feinen Schichten, Bäumen und Turm | 9/9 | 0 |
| `e79410c55` | `ruff check` und `ruff format --check` über die 5 Dateien | grün | 0 / 0 |
| `e79410c55` | `mypy` (Konfiguration: `app`) | 375 Dateien ohne Befund | 0 |

Der übersprungene Test ist `test_toolchain.py:3125`: „kein Paket unter
website/dl/“. Er hängt an der Umgebung und hat mit dem Fix nichts zu tun.

## Merge `e79410c55` verliert nichts

Der Merge-Beitrag (`git diff bb269dc54 e79410c55`) gleicht dem Fix-Diff
(`git diff 1e4dec783 bddfd5fc1`) Zeile für Zeile. Er weicht nur in den zwei
Hunk-Köpfen von `writer.py` ab, die um 3 Zeilen versetzt sind. Welle4 hat seit
`1e4dec783` von den fünf Dateien nur `writer.py` angefasst
(`part_advice`/`_values_for`, RM-584-Nachtrag) und dabei keine neue
Befundstelle angelegt. Am Merge tragen beide Befunde
`suggestions=(OPEN_PRINT_SETTINGS,)`.

## Grenzen

Gelesen habe ich den vollständigen Diff, die drei Wächter, den Handlerweg in
`panels`, `dialogs` und `main_window` sowie `_layer_heights` und
`_tower_causes`. Nicht gefahren habe ich das ganze Tor am Merge, das der
Koordinator fährt, und die Fensterdatei am Merge. Unter den fünf Dateien hat
der Merge nur `writer.py` geändert. N1 und N2 sind als Fix beschrieben, aber
nicht ausprobiert.
