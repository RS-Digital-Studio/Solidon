# Abgleich: `.claude/konzept-live-durchsicht-2026-08.md`

Geprüft am 19.08.2026 gegen den Stand von `main` (b0415d6). Geprüft wurden die
fünfzehn intern nachschlagbaren Behauptungen der Arbeitsmappe; die externen
(Fusion, ElegooSlicer, OCC, VTK) bleiben hier außen vor.

**Zusammenfassung:** 8× stimmt, 5× überholt, 1× falsch, 1× unprüfbar. Dazu
**zwei Widersprüche im Dokument selbst** — der Kasten am Kopf sagt „drei
Pakete" und „offen blieb allein die fehlende Passung", während der Nachtrag in
Abschnitt 3 und der Erledigt-Vermerk unter B3 beides widerlegen.

---

## W1 — Widerspruch im Dokument: die fehlende Passung

**Stelle:** Kasten am Kopf, Zeilen 10–14: „Die fünfzehn Funde sind in **drei**
Paketen erledigt … **Offen blieb allein die fehlende Passung**, die dort
ebenfalls vermerkt ist."

**Urteil: widerspruch_im_dokument / überholt**

**Beleg:**
- Derselbe Fund trägt unter B3 (Zeilen 251–257) den Vermerk „**Erledigt**, aber
  nicht in den Ops" mit Verweis auf `app/core/lid_flow.py`.
- Der Nachtrag in Abschnitt 3 (Zeilen 462–468) sagt: „Alle **vier** Pakete und
  A2 sind durch (nachgeprüft am Code, 14.08.2026)."
- `app/core/lid_flow.py` existiert (1058 Zeilen ab `"""Deckel erzeugen als
  Ablauf …`), `tests/test_lid_flow.py` hat sieben Tests, alle grün
  (`pytest tests/test_lid_flow.py` → Teil von „169 passed in 45.35s").
- `ROADMAP.md:2336` führt „**Keine Operation legt eine Passung an**" mit
  Haken `[x]`; alle fünfzehn Punkte des Abschnitts „Live gegen Fusion und den
  ElegooSlicer" (ROADMAP.md:2310–2369) sind abgehakt, keiner offen.
- Die Zahl „drei Pakete" widerspricht Abschnitt 3, der vier Pakete aufzählt
  (Zeilen 470, 478, 490, 500).

**So müsste der Satz lauten:**
> **Stand 14.08.2026: abgearbeitet.** Alle fünfzehn Funde sind in vier Paketen
> plus A2 erledigt — die ROADMAP führt sie unter „Live gegen Fusion und den
> ElegooSlicer" einzeln mit Haken, keiner ist offen geblieben. Die Passung
> entsteht dabei nicht in den Ops, sondern in `app/core/lid_flow.py` (Regel 3).

*(Nebenbefund außerhalb des Auftrags: `ROADMAP.md:2307–2308` trägt denselben
stehengebliebenen Halbsatz „mit Ausnahme der fehlenden Passung", obwohl der
Punkt zwanzig Zeilen darunter abgehakt ist.)*

---

## B1 — Ausgangslage: 2756 Tests in 267 s, nach C2 „die 2809 Tests"

**Stelle:** Zeile 16 („Ausgangslage: `pytest -m "not performance"` grün, 2756
Tests in 267 s"), Zeile 357 („die 2809 Tests laufen durch").

**Urteil: überholt**

**Beleg:**
```
.venv/Scripts/python.exe -m pytest -q -m "not performance" --collect-only
→ 4232/4251 tests collected (19 deselected) in 2.87s
```
Seit dem 05.08.2026 sind rund 1480 Tests dazugekommen (686 Commits seit dem
01.08.2026).

**So müsste der Satz lauten:**
> Ausgangslage am 05.08.2026: `pytest -m "not performance"` grün, 2756 Tests in
> 267 s (Stand 19.08.2026: 4232 Tests).

Und unter C2: „die 2809 Tests laufen durch" → „die Suite lief unverändert
durch (damals 2809 Tests)". Beide Zahlen sind Momentaufnahmen und gehören als
solche datiert, sonst liest man sie als heutigen Stand.

---

## B2 — Alle fünfzehn Funde erledigt, ROADMAP führt sie mit Haken

**Stelle:** Kasten Zeile 10–14, Abschnitt 3 Zeile 462–468.

**Urteil: stimmt** (bis auf den unter W1 behandelten Halbsatz)

**Beleg:** `ROADMAP.md:2291–2369`, Abschnitt „Live gegen Fusion und den
ElegooSlicer": fünfzehn Listenpunkte, alle `- [x]`. Kein `- [ ]` im ganzen
Abschnitt (`grep -c "\- \[ \]" ROADMAP.md` → 12, sämtlich in anderen
Abschnitten ab Zeile 4435).

---

## B3 — `Solid.bounds` über `BRepBndLib.AddOptimal_s`; Test vorhanden

**Stelle:** A1, Erledigt-Vermerk Zeilen 97–104.

**Urteil: stimmt**

**Beleg:**
- `app/core/brep/kernel.py:184` — `BRepBndLib.AddOptimal_s(self.shape, box, False, False)`,
  darüber ab Zeile 173 der Kommentar, der die Wahl gegen `Add_s` begründet.
- Zweite Verwendung: `app/core/brep/profiles.py:571`.
- `tests/test_brep.py:50` — `test_the_bounding_box_comes_from_the_shape_not_from_the_triangles`,
  grün.

---

## B4 — `drill`: Parameter `anchor`, Migration 6 → 7, `drilled_v6.p3d`

**Stelle:** A2, Erledigt-Vermerk Zeilen 139–159.

**Urteil: stimmt** (mit einer Kleinigkeit unter „Fix")

**Beleg:**
- `app/core/geom/prepare_ops.py:62` — `_ANCHORS = ("mouth", "centre")`;
  Zeile 172–180: `anchor: str = param(…, default="mouth", choices=_ANCHORS,
  placement="advanced", …)`. Die Operation heißt im Register `drill_hole`
  (`prepare_ops.py:190`), nicht `drill`; `drill` ist die Geometriefunktion in
  `app/core/geom/prepare.py:125`.
- `app/core/scene/migrations.py:114` — `_keep_bores_centred` („6 → 7"),
  eingetragen in `MIGRATIONS` (Zeile 144).
- `tests/data/projects/drilled_v6.p3d` liegt eingecheckt;
  `tests/test_project.py:483` prüft
  `mesh.volume == pytest.approx(31276.892, abs=0.01)`.
- Der Gegenwert 31 231,74 mm³ steht in keinem Test, ist aber rechnerisch
  stimmig: 31 276,89 − 31 231,74 = 45,15 mm³ = π·(6,2/2)²·1,5 — also genau die
  Hälfte einer 3 mm tiefen Bohrung Ø 6,2 (kompensiert). Die Zahl ist damit
  bestätigt, nur nicht durch die Suite gedeckt.

**Fix (klein):** Im Vermerk „`drill` bekam `anchor`" durch „`drill_hole` bekam
`anchor`" ersetzen — der Registername ist der, den ein Leser sucht.

---

## B5 — Bausteinbibliothek Version 2, sechzehn Bausteine, drei geändert

**Stelle:** A2, Erledigt-Vermerk Zeilen 142–149.

**Urteil: überholt** (in zwei Zahlen)

**Beleg:**
```
.venv/Scripts/python.exe -c "from app.core.knowledge.parts import PARTS; print(len(PARTS.all()))"
→ 17
```
- `app/core/knowledge/parts/registry.py:258` — `LIBRARY_VERSION: Final = "3"`,
  mit dem Kommentar darüber: „Version 3: das Spiel von Mutternfalle und Gewinde
  kommt aus dem Materialprofil statt aus einer festen Vorgabe
  (`PLAY_FROM_PROFILE` in `fasteners.py`)".
- `MOUTH_AT_ORIGIN` steht weiterhin mit `version="2"`,
  `date="2026-08-05"` (registry.py:263) und hängt an genau drei Bausteinen:
  `mounting.py:73`, `mounting.py:248`, `structure.py:165`.
- Sechzehn → siebzehn: der siebzehnte ist `snap_connector`, hinzugekommen mit
  `33031da` („Alles Offene abgearbeitet …", 14.08.2026).
  Gegenprobe: `git grep -h "@register_part" 55d033d -- app/core/knowledge/parts/ | wc -l` → 16,
  heute → 17.
- Die drei Volumina sind **unverändert richtig**, nachgemessen am heutigen Code:
  `magnet_pocket 150.37`, `keyhole 343.36`, `cable_gland 308.76` (Platte
  60×60×20, Werkzeug auf z = 20, `boolean("difference", …)` — dieselbe Anordnung
  wie `tests/test_parts.py:162 test_a_subtractive_part_reaches_into_the_material`).

**So müsste der Satz lauten:**
> *Die Bausteine:* alle sechzehn damaligen nachgemessen … Die Bibliothek ging
> dafür auf Version 2, der Änderungseintrag `MOUTH_AT_ORIGIN` sagt, was das für
> alte Projekte heißt. (Heute steht sie auf Version 3 und zählt siebzehn
> Bausteine — Version 3 betrifft das Spiel von Mutternfalle und Gewinde, nicht
> diesen Fund.)

---

## B6 — Der Satz über den wirkungslosen Schnitt steht in `geom/boolean.py`

**Stelle:** A3, Erledigt-Vermerk Zeilen 177–182.

**Urteil: stimmt**

**Beleg:**
- `app/core/geom/boolean.py:392` — „Der Schnitt hat nichts abgetragen — das
  Werkzeug liegt neben dem Körper. …", Befundcode `boolean.without_effect`.
- `tests/test_parts.py:380` — `assert "boolean.without_effect" in codes` am
  Testfall Magnettasche; die Gegenprobe steht direkt darunter
  (`test_a_part_that_hits_the_body_stays_quiet`, Zeile 383). Beide grün.

---

## B7 — Die Passung entsteht in `app/core/lid_flow.py`, `tests/test_lid_flow.py` hält es fest

**Stelle:** B3, Erledigt-Vermerk Zeilen 251–257.

**Urteil: stimmt**

**Beleg:**
- `app/core/lid_flow.py` existiert; der Modul-Docstring begründet die Wahl mit
  Regel 3 und §15.1 („eine Op bekommt ihre Szene nur lesend … der Ablauf steht
  deshalb daneben, wie `split.apply_split` beim Verstiften").
- `unique_name()` (lid_flow.py:56) sammelt die bestehenden Passungsnamen ein —
  genau das, was der Vermerk behauptet.
- `tests/test_lid_flow.py` mit sieben Tests, darunter
  `test_a_second_lid_gets_its_own_name` und `test_undo_takes_the_fit_with_it`.
  Alle grün.
- Ergänzung aus der ROADMAP (Zeile 2336–2343), die im Konzept fehlt: die
  Passung reist „über ein `fits`-Feld an `OpResult`" (`app/core/types.py:866`,
  `fits: tuple[Fit, ...] | None = None`) — nachgetragen und nicht mitgegeben,
  weil erst der Verlauf die Objekt-IDs vergibt.
- `_from_fits` und die drei Regeln existieren weiter:
  `app/core/slice/advise.py:144` und `:524`.

---

## B8 — `gcode.compare` läuft dreimal; ursprünglicher Einzelaufruf `main_window.py:1642`

**Stelle:** B4, Zeilen 265–266 und Erledigt-Vermerk 275–279.

**Urteil: überholt** (die Aussage stimmt, die Zeilennummer stimmt nicht mehr)

**Beleg:**
```
grep -n "compare(" app/ui/main_window.py
2798:  gcode.compare(estimate.support_volume, measured, "support").findings
2827:  findings += gcode.compare(estimate.grams, grams, "material").findings
2829:  findings += gcode.compare(estimate.seconds / 60.0, metrics.print_minutes, "time").findings
```
Drei Aufrufe, in `_compare_support` (Zeile 2793) und `_compare_totals`
(Zeile 2802). Beide Zusatzprüfungen sind so bewacht, wie der Vermerk sagt:
`if grams is not None and estimate.grams > 0.0` bzw.
`if metrics.print_minutes is not None and estimate.seconds > 0.0`.
Die Schwelle steht unverändert bei `app/core/slice/gcode.py:32` —
`DEVIATION_LIMIT = 0.15`. Der Ort des einstigen Einzelaufrufs ist heute
`main_window.py:2798`, nicht `:1642`.

**So müsste der Satz lauten:**
> `gcode.compare` hat die 15-%-Schwelle und wurde an genau einer Stelle gerufen
> — damals `main_window.py:1642`, heute `_compare_support` in
> `main_window.py:2793` — für das Stützvolumen.

Generell: Zeilennummern in einem Konzept altern schneller als alles andere; ein
Funktionsname (`_compare_support`) hält.

---

## B9 — Schätzung 12 g / 46 min gegen G-Code 10,0 g / 37 min; `slice/estimate.py` braucht Arbeit

**Stelle:** B4, Zeilen 261–273.

**Urteil: unprüfbar** (die Messung), **aber: der Hinweis ist unverändert offen
und nirgends verfolgt**

**Beleg:**
- Die Zahlen stammen aus einem Lauf gegen den installierten ElegooSlicer; ohne
  denselben Lauf ist am Repository nichts nachzuprüfen.
- `app/core/slice/estimate.py` hat seit dem 05.08.2026 **keine inhaltliche
  Änderung** gesehen:
  `git log --since=2026-08-05 -- app/core/slice/estimate.py` → ein Commit,
  `8a15cbc` („Acht Fehlertexte der Mesh-Erzeugung sprachen nur Englisch …"),
  eine reine Übersetzung. Die Abweichung dürfte also unverändert bestehen.
- In `ROADMAP.md` gibt es dazu **keinen offenen Punkt**: `grep -n "estimate"`
  findet nur die abgehakten Zeilen 281–286 und 2447. Der Satz „genau dieser
  Satz ist der Hinweis, dass `slice/estimate.py` Arbeit braucht" hat damit kein
  Gegenstück in der Arbeitsliste.

**So müsste der Satz lauten:** unverändert lassen, aber mit einem Vermerk:
> *Weiter offen (Stand 19.08.2026):* Die Gegenprobe meldet die Abweichung
> inzwischen — behoben ist sie nicht. `slice/estimate.py` ist seit dem
> 05.08.2026 unverändert, und die ROADMAP führt dazu keinen Punkt.

---

## B10 — `History._outputs_for` plant für `takes_whole_scene` ohne Eingaben keine Ausgänge

**Stelle:** B5, Zeilen 283–296.

**Urteil: stimmt**

**Beleg:**
- `app/core/scene/history.py:394` `_outputs_for`, Zeilen 402–411:
  ```
  if spec.produces == VARIABLE and not draft.inputs:
      if spec.takes_whole_scene:
          return ()
  ```
  mit dem Kommentar, der den Fund fast wörtlich wiedergibt.
- `tests/test_whole_scene_ops.py:53`
  `test_arranging_without_inputs_changes_nothing`, Zeile 73:
  `assert after.complete, "eine Operation ohne Wirkung darf das Dokument nicht anhalten"`
  — die im Fix verlangte Ergänzung ist da. Grün.

---

## B11 — Der Viewport benutzt `vtkCellPicker` „an beiden Stellen"

**Stelle:** C1, Erledigt-Vermerk Zeilen 324–329 (und die Fix-Zeile 319).

**Urteil: falsch** (in der Formulierung „an beiden Stellen")

**Beleg:**
- `vtkCellPicker` kommt in `app/ui/` genau **einmal** vor:
  `app/ui/viewport.py:3657` in `_world_at` (Toleranz `PICK_TOLERANCE`,
  Zeile 3665).
- Die zweite Stelle gibt es nicht mehr: `_enable_picking`
  (`app/ui/viewport.py:3682 ff.`) hat einen leeren Rumpf — „Nichts mehr zu tun
  — der eigene Stil löst das Picking selbst aus. Vorher stand hier
  `plotter.enable_point_picking`. Das hat nie funktioniert …". Sie wurde also
  **entfernt**, nicht auf einen Zellpicker umgestellt.
- Der Rest des Vermerks stimmt: `objectPicked` ist ein Signal
  (`viewport.py:927`), wird an vier Stellen ausgelöst (2486, 3620, 3635, 3677)
  und im Fenster verdrahtet (`main_window.py:861`). Auswahl und Kontextmenü
  laufen beide über `_select_at` (`viewport.py:3625`).
- `git log -S vtkCellPicker -- app/ui/viewport.py` → ein Commit, `edf3cb7`
  („Der Klick kam an und hatte niemanden", 05.08.2026 23:27).

**So müsste der Satz lauten:**
> **Erledigt.** Gepickt wird nur noch an einer Stelle, und dort mit
> `vtkCellPicker`: `_world_at` in `app/ui/viewport.py`. Die zweite Stelle —
> `plotter.enable_point_picking` — ist ersatzlos weg; sie hat nie funktioniert,
> weil pyvista den Renderer über seinen eigenen Interactor-Stil sucht und
> Solidon einen eigenen setzt. Der Viewport gibt das Getroffene über
> `objectPicked` heraus …

---

## B12 — Nach C2: Zylinder 4 Merkmale, Würfel 6, Achteck 10, Trennwinkel 30°

**Stelle:** C2, Erledigt-Vermerk Zeilen 350–357.

**Urteil: stimmt** (bis auf zwei Zahlen, die kein Test hält)

**Beleg:**
- `app/core/perceive/features.py:86` — `CURVATURE_LIMIT = 30.0`, angewandt in
  Zeile 243 (`rounded = (angles > EPS_ANGLE) & (angles < CURVATURE_LIMIT)`);
  der Kommentar ab Zeile 77 nennt „bei zwölf Segmenten sind es 30, bei acht 45".
- `tests/test_features.py:294`
  `test_a_cylinder_has_three_faces_and_not_fifty`:
  `assert sorted(kinds) == ["face", "face", "hole", "pin"]` — vier Merkmale,
  der Mantel als `pin`. Genau die Aufzählung des Vermerks.
- Würfel 6: `tests/test_features.py:123`
  `test_the_six_faces_of_a_cube_are_found` → `assert len(faces) == 6`.
- Achteck 10: `tests/test_features.py:315`
  `test_a_coarse_prism_keeps_its_sides` → `assert len(faces) == 10`, mit dem
  Docstring „Die Grenze zwischen Rundung und Kante liegt bei dreißig Grad".
- „Platte mit Stift 7" und „Kugel keines" haben kein Gegenstück mit fester Zahl:
  `test_a_pin_is_recognised_as_one` (Zeile 252) prüft `len(found) == 1`,
  `test_a_generated_mesh_does_not_drown_in_faces` (Zeile 180) prüft nur
  `not faces`. Die beiden Zahlen sind Messwerte, keine Zusicherungen.
- Alle genannten Tests grün.

---

## B13 — `FeatureKind` führt `pin`; Mesh-Weg `detect_pins`, B-Rep-Weg `hollow`; Bauplan führt `pin`

**Stelle:** C3, Erledigt-Vermerk Zeilen 371–377.

**Urteil: stimmt**

**Beleg:**
- `app/core/types.py:53` —
  `FeatureKind = Literal["hole", "face", "edge_loop", "pin", "thread"]`.
- Mesh-Weg: `app/core/perceive/features.py:205` `def detect_pins(mesh)`,
  gerufen in Zeile 119; `kind="pin"` in Zeile 218.
- B-Rep-Weg: `app/core/brep/features.py:105–106` —
  `hollow = face.Orientation() == TopAbs_REVERSED` /
  `return "hole" if hollow else "pin", {…}`.
- Bauplan: `3d-agent-bauplan.md:410` —
  `kind: Literal["hole", "face", "edge_loop", "pin", "thread"]`, dazu die
  Beispiele `op4.pin_1` (Zeile 409, 956) und `op5.pin_1` (Zeile 1054, 626).
- Tests: `test_a_pin_is_recognised_as_one`,
  `test_a_pin_on_a_plate_is_not_reported_as_a_bore`,
  `test_a_bore_is_not_reported_as_a_pin` (tests/test_features.py:252, 265, 269),
  alle grün.

---

## B14 — `sketch_bar` in der unteren Zone, `SketchPanel` aus P15 Etappe 3, Dialog und Modus teilen das Panel

**Stelle:** C4, Erledigt-Vermerk Zeilen 394–398.

**Urteil: stimmt**

**Beleg:**
- `app/ui/main_window.py:1011` erzeugt `self.sketch_bar`; Zeile 1083 hängt sie
  in `bottom_layout` einer schwebenden Karte („overlayCard", Zeile 1078). Der
  Kommentar Zeile 1074 sagt es selbst: „Werkzeugzeile und Skizzenleiste
  schweben zusammen unten in der Mitte." Sie läuft also nicht mehr über die
  volle Fensterbreite und liegt nicht mehr unter den Seitenbereichen.
- Stapel im mittleren Bereich: `main_window.py:3276` erzeugt das `SketchPanel`,
  Zeile 3281–3282 `self.middle_stack.addWidget(panel)` / `switch(...)`.
- Dasselbe Panel im Dialog: `app/ui/sketch_editor.py:2656` —
  `self.panel = SketchPanel(text, parameter_values, self, surroundings)`;
  die Klasse selbst ab `sketch_editor.py:2027`.
- P15 ist laut `ROADMAP.md:2242` „vollständig abgearbeitet"; der Skizzenmodus
  ohne Dialog steht dort ausdrücklich unter „Was dazukam" (Zeile 2251).

*Kleine Präzisierung:* Die `sketch_bar` ist **nicht** Teil des `SketchPanel`,
sondern ein eigenes Widget des Hauptfensters in derselben unteren Karte wie
`sculpt_bar`, `pose_bar` und die Werkzeugzeile. Der Vermerk formuliert das
richtig („gehört zur unteren Zone") — wer ihn zusammenfasst, sollte es nicht zu
„Teil des SketchPanel" verkürzen.

---

## B15 — `first_run._printer_from_slicer()`, `hollow_object` mit „oben öffnen", `writer._step_bytes`

**Stelle:** C5 (Zeilen 413–418), C7 (Zeilen 449–454), C6 (Zeilen 431–435).

**Urteil: stimmt**

**Beleg:**
- `app/ui/first_run.py:256` `def _printer_from_slicer()`, darin Zeile 275–276
  `slicer_profiles.chosen_machine(flavour, found)` und
  `slicer_profiles.printer_for(machine, profiles.printer_profiles())`.
  Die zitierte Reihenfolge steht wörtlich in Zeile 144:
  `chosen = settings.printer or _printer_from_slicer() or profiles.DEFAULT_PRINTER`
  — im Konzept ohne das Modulpräfix `profiles.`, sonst identisch.
- `app/core/geom/prepare_ops.py:410` — `open_top: bool = param(title=_("Oben
  öffnen"), default=False, doc=_("Nimmt die Decke über dem Hohlraum weg. Aus dem
  hohlen Körper wird eine Dose, und *Deckel erzeugen* findet die Öffnung, die es
  braucht."))`, durchgereicht in Zeile 465 an `hollow(...)`. Ein Baustein
  „Behälter" wurde nicht gebaut — wie der Vermerk sagt.
- `app/core/export/writer.py:730` — `def _step_bytes(body, name="")`, gerufen in
  Zeile 654 mit dem Objektnamen. Die zwei Tests existieren:
  `tests/test_brep.py:182 test_the_object_name_travels_into_the_step_file` und
  `tests/test_brep.py:197 test_a_step_export_carries_the_name_from_the_scene`.
  Beide grün.

---

## Was daraus für die Konzeptdatei folgt

Das Dokument ist als **Messprotokoll** in gutem Zustand: von fünfzehn internen
Behauptungen halten neun unverändert, und keine der Erledigt-Vermerke ist
hohl — jede Codestelle, die sie nennen, existiert und ist getestet.

Vier Sorten Alterung, alle mit derselben Ursache — undatierte Momentaufnahmen:

1. **Der Kasten am Kopf ist stehengeblieben** (W1). Er sagt „drei Pakete" und
   „offen blieb allein die fehlende Passung", während zweihundert Zeilen weiter
   „alle vier Pakete und A2 sind durch" steht und B3 die Passung abhakt. Wer
   nur den Kopf liest, geht mit einem falschen Bild weg. Das ist die einzige
   Änderung, die dringend ist.
2. **Zahlen ohne Datum** (B1, B5): 2756/2809 Tests → 4232; sechzehn Bausteine →
   siebzehn; Bibliotheksversion 2 → 3. Als historische Werte richtig, als
   Gegenwart falsch. Ein „(Stand 05.08.2026)" hinter jeder Zahl genügt.
3. **Eine Zeilennummer** (B8): `main_window.py:1642` zeigt heute woanders hin.
   Funktionsnamen statt Zeilennummern.
4. **Eine Ungenauigkeit im Vermerk** (B11): „`vtkCellPicker` an beiden Stellen"
   — es ist eine Stelle, die zweite ist ersatzlos entfallen.

Nicht zu ändern, aber zu vermerken: der Hinweis auf `slice/estimate.py` (B9)
ist der einzige Inhalt des Dokuments, der auf etwas zeigt, das weder erledigt
noch in der ROADMAP verfolgt ist.
