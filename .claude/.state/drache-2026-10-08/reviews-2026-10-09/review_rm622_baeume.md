# Review RM-622 Baum-Erweiterung (`F:/sl-turm`, Diff gegen `f605411f9`) — solidon3d-review, 09.10.2026

## Mittel
- **M1** Dialog (`print_settings_dialog.py:1502`, `self.settings.support.style` mit Übernahme) und
  Export (`writer.py:2513–2517`, `split.base.support.style`) fragen `rounding_plates` mit
  verschiedener Art. Elegoo tree(auto), Grundlage aus, Baum übernommen: Dialog `frozenset()`,
  Export `{0}`; Zeile „0,2 · Kinn“, Datei schreibt Kinn und Tisch 0,2. Fix: Arbeiter mit
  `split_for_parts(...).base`; Test Kinn+Tisch.
- **M2** Dialogfilter `ignored_under_trees` auf die zusammengeführte Platte statt je Körper
  (`:1650–1656`); Creality, eigenes Gitter, Kinn+Tisch: Dialog streicht untere Trennschicht, Export
  je Teil gibt sie dem Tisch. Fix: je Körper/Spule vor `combine` filtern.
- **M3** Ursache „trees“ gilt der ganzen Datei (`writer.py:2795–2799`, `_tree_supports`): Platte
  Gitter + Kinn Baum + Tisch 0,28 → Tisch druckt genau, Befund sagt Rundung; Elegoo tree(auto)
  mit übernommenem „automatisch“ → Teil nur `enable_support=1`, Befund „eigene Schichthöhe“ falsch.
  Fix: je Teil an `part_values[id].effective` fragen; gemischt beide Sätze.
- **M4** „Liegt die Stütze auf den Modellschichten?“ mehrfach hergeleitet und auseinander:
  SuperSlicer (tree → Gitter) rundet trotzdem; „hybrid“ auf diesem Zweig kein gültiger Wert;
  `tree_hybrid` in Orca ist laut `TreeSupport.cpp` **nicht** synchron (nur `smsTreeOrganic` geht in
  den organischen Generator, `:1756–1759`; Hybrid über `plan_layer_heights` mit Zwischenebenen,
  `:3349–3408`); Prusa-„hybrid“ (→ Gitter) würde gerundet; Herstellerprozesse mit `tree_hybrid`
  oder `tree_slim` machen aus „tree“ keinen organischen Baum; Prusa „automatisch“ mit `organic`
  (BIBO, CocoaPress, Rigid3D) nicht erkannt. Fix: eine Auskunft je Programm (Stil nach
  `substitute`, auto über `support_type` + `support_style` bzw. Prusa `organic`), vom Aufrufer an den
  Rat wie `whole_layers`; Hybrid hier streichen.

## Leicht
- **L1** Am Feld kein Satz zur Rundung unter Bäumen (`slicer_keys.limitation` nur Cura); „Trennschichten
  unten“ unter Bäumen bei Bambu/Creality/Anycubic/Prusa eine Attrappe.
- **L2** Abstandsvorschlag setzt den Baumvorschlag voraus: Kunde lehnt „Bäume“ ab, behält „Abstand“
  → PETG-Gitter 0,2 statt 0,28. Fix: im Export mit der Art fragen, die das Teil bekommt.
- **L3** Docstrings und Regeltext veraltet (`advise.py:244–246`, `:930–935`, `:974–985`,
  `:1017–1022`; `writer.py:1324–1325`, `:2930–2932`; `druckrat.md:80`, `:84`).
- **L4** Tests: `test_print_settings.py:9277` nur „Baumstützen“ im Text; UI-Filtertest ein Körper;
  Fälle zu M1–M3 fehlen.
- **L5** Anycubic: `support_interface_bottom_layers = -1` (wie oben), gedruckt Gitter 4, Bäume 0 —
  Wortlaut „geschrieben zwei“ stimmt dort nicht.
- **L6** Neuer Befund ohne Ausweg (Vorschlag „Mit Gitterstützen gilt er genau.“); Changelog verspricht
  die untere Trennschicht pauschal — Satz zu Bäumen in allen sechs Sprachen.

Ohne Befund: Regeln 1–22, Sprache, Programmmarken, Leistung (`single_read`), Konsolenweg, Cura.
Offen aus der Vorprüfung: RM-622 im Register/Archiv. Nachprüfung nötig (mehrere mittlere).
Sonden: Scratchpad `review_rm622b\`.
