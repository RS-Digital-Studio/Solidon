# Review RM-622 (`einstellungen/turmabstand`, `fafcd4841..3ac1c73b4`) — solidon3d-review, 09.10.2026

## Mittel
- **M1** Drei neue Aufrufstellen ohne Gegenprobe: Dialog `_accepted_targets` (`:1675`),
  `_with_parts` (`:1728`), Export `_served_elsewhere` (`writer.py:1659/1673`). Mit zwei Tischen
  liefert der Dialogtest mit und ohne Turm `(0.16, ())`; mit drittem ungestütztem Körper:
  gebaut `('PLA-Tisch', 'PETG-Tisch')`, ohne Turm `()`; `accepted_parts` ebenso. Export: Platte 0
  PLA+PETG-Tisch, Platte 1 Block, eigene Wahl 0,16, übernommen 0,24 → gebaut Block 0,24 mit
  `export.part_setting_all`, ohne Turm in `_served_elsewhere` nichts. Fix: dritter Körper im
  Dialogtest, `row.parts` und `accepted_parts` zusichern; Exporttest mit `job=`.
- **M2** `tower_plates` löst den Herstellerprozess je Platte neu auf: 39/153/382 ms für 1/4/8
  Platten; Ratlauf 1 Platte 89–133 ms statt 67–75, 4 Platten 326–561 statt 185–294. In
  `slicer_profiles.single_read()` konstant ~43 ms, Ratlauf 66/201 ms. Fix: `tower_plates` in
  `single_read()`, `_AdviceWorker.work` ganz im Durchgang; `_served_elsewhere` fragt den Turm erst,
  wenn ein Pfad offen ist.

## Leicht
- **L1** `handover._native_process` fängt `ExternalToolError` nicht ab — ein kaputter Prozess
  (fehlende Vorlage im `include`) lässt den ganzen Ratlauf scheitern. Fix: abfangen, `{}`,
  warnen; Test.
- **L2** Zwillinge: `tower_plates`/`_tower_cause` gruppieren gleich; „ganze Schicht?“ an drei
  Stellen (`advise.py:1012`, `handover.py:3053`, `slicer_keys.py:1645`); „rundet hier?“ zweimal
  (`advise.py:970`, `:1009`). Fix: ein Plattenhelfer, ein Prädikat je Frage.
- **L3** `_served_elsewhere` zählt nur nicht gewählte Körper je Platte; Fix: `tower_plates(job)`
  einmal in `write_assembly`.
- **L4** Testtexte: `test_print_settings.py:9004` „0,28 nur, wo ein Teil PETG ist“ stimmt neben
  dem Turm nicht mehr; `test_slice_findings.py:1541` 0,2 liegt auf der Bandgrenze (zusätzlich
  0,18); Sollwerte `:1497–1504` ohne Herkunft.
- **L5** RM-622 weder im Register noch im Archiv; `druckrat.md:80–83` „Band“ doppeldeutig.

Geprüft ohne Befund: `else`-Zweig Dialog, Konsolenweg, `frees_support_layers`, Druckzeit,
`matrix_unit`, CLI, Prusa/Cura ohne Turm, Plattenzuordnung; Cura-Vorschlag im Band richtig
(Cura rundet auf), kein Pendeln, Gleitkomma unkritisch; Regeln 1–22 ohne Verstoß. Changelog:
kein eigener Punkt nötig.

Sonden im Scratchpad der Sitzung: `turm_kosten.py`, `ratlauf_kosten.py`, `kaputte_kette.py`,
`gegenprobe_teile.py`, `gegenprobe_auftrag.py`, `gemischte_platte.py`.
