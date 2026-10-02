# RM-290: Abgeschlossene Text- und Hinweisprüfung, 02.10.2026

Die Punkte a–h sind im Commit `6ce767031be8e703d5937368aaa471d843771767` auf `origin/main` integriert.
Der geprüfte Commitbaum ist `6a9da085d79d872de74c5c12550d921e79a5e281`.
Das zentrale vollständige Entwicklungstor bestand 18.972 Fälle, 62 wurden
übersprungen; Suite/Ruff/Format/mypy jeweils Exit 0. Quelle und Teststand blieben
während des Tors unverändert. Eigenreview, unabhängige Quellprüfung und abschließende
zentrale Produkt-/Selektionsprüfung sind ohne offene Befunde abgeschlossen.

## Erfüllte Einzelpunkte

| Punkt | Änderung und wirklicher Prüfweg |
|---|---|
| a | Örtliches *Merkmal bearbeiten* und die Änderungsoperation unterscheiden sich in fr/it einschließlich Handbuchzitaten. Operationstitel verwenden den vereinbarten Imperativ. |
| b/g | *Trennen* und *Abschneiden* sind en Cut/Crop sowie it Taglia/Tronca; die fünf beanstandeten italienischen Titel stehen im tu-Imperativ. Der Wortlautwächter vergleicht für dieses semantische Paar auch das erste Verb mehrteiliger Namen. |
| c | Beide Hinweise schreiben „nebeneinanderlegen“. `split_pinned` und `split_line` haben jeweils Op-Cacheversion 3 statt 2; keine globale Cache- oder Geometrieänderung dieser Textgruppe. |
| d | Der konkrete Lei-Satz war bereits korrigiert. Der neue Wächter erkennt den Indikativ bei tatsächlich belegter Kundenanrede; Modell-/Substantivgegenfälle bleiben zulässig. |
| e | `_part_advice` liest den echten `measure_status` der Maßquellen. Nicht-native Bohrungen erhalten einen vollständigen neutralen Einschätzungsrahmen. Einargument-Rückruf, Vorbelegung, unavailable und None-Rückfall bleiben erhalten. |
| f | Sämtliche fr/it-Katalogwerte einschließlich Handbuch verwenden gerade Apostrophe. Der neue Wächter erfasst auch verschiedene Einträge; zwei zusätzlich aufgedeckte alte Werte wurden vor der endgültigen Integration korrigiert. |
| h | Der tatsächlich ausgelieferte italienische Leersatz spricht den Kunden mit tu an. Ein eigener Wächter prüft genau diesen Schlüssel. |

## Dauerhafte Wächter im Repository

- `tests/test_placement.py`: `test_part_bore_advice_qualifies_every_non_native_measure`
  liest echte `measure_sources` über `measure_status`, einschließlich exact für
  facets/parameter. Die weiteren `test_part_bore_advice_*` prüfen negative Antworten,
  Einargument-Rückruf, unavailable, None und sechs übersetzte vollständige Rahmen.
- `tests/test_translations.py`: `test_italian_reviewed_operation_titles_use_the_second_person`,
  `test_italian_customer_clause_guard_keeps_model_and_noun_counterexamples`,
  `test_french_and_italian_use_straight_apostrophes_everywhere`,
  `test_apostrophe_guard_control_checks_separate_entries` und
  `test_italian_empty_feature_hint_uses_second_person`.
- `tests/test_cache.py::test_split_cache_recalculates_old_single_cut_translation`:
  zwei tatsächliche Operationen, gültiges `new_project`-Dokument und ausdrückliche
  Zeichenkettenkennungen; der alte deutschsprachige Cachehinweis wird neu berechnet,
  Wiederöffnen und warmer Folgecache bleiben korrekt.

## Tatsächliche Vorher-/Nachher-Nachweise

Zwölf echte alte Katalogwächterfälle wurden verworfen; dieselben zwölf aktuellen
bestanden (Gesamt-Exit 1 der absichtlich negativen Serie). Beide gültig aufgebauten
Splitcache-Gegenproben mit ausschließlich alter Registry-Cacheversion 2 scheiterten
am deutschen Althinweis, 2 failed/Exit 1, keine Setupfehler. Die neue Version 3 bestand
beide Fälle. Frühere eigene Import-/Aufbau-/Ruff-Fehler wurden behoben und sind keine
negativen Produktgegenproben.

Der enge frühere Nachlauf bestand 92 Fälle, davon sechs separat RM-285-Bereichsprüfer;
967 wurden abgewählt, Exit 0. Ein frischer Nachgang nach unabhängigen Testbefunden
bestand 26 Fälle, Exit 0. Die spätere abgegrenzte RM-290-Auswahl benennt 87 Fälle:
64 neue und 23 bestehende Übersetzungsfälle. Ein gesonderter gemeinsamer 87er-Lauf
wurde vor dem zentralen Tor nicht behauptet. Fünf bestehende Platzhalterwächter
bestanden zusätzlich. Maßquellen-/Leersatz-/Cachetestkorrekturen wurden unabhängig
rückgeprüft, bevor das vollständige zentrale Tor gefahren wurde.

Der erste zentrale Torlauf war tatsächlich rot: 2 failed, 18.970 passed, 62 skipped.
Er fand zwei weitere gerade Apostrophe erfordernde Katalogwerte (fr/it). Nach deren
Korrektur und erneutem unabhängigen Review lief das vollständige Tor frisch mit
18.972 passed/62 skipped/Exit 0. Der rote erste Lauf ersetzt diesen Abschluss nicht.

## Selektionsgrenze

Der tatsächliche Commitdiff enthält je Sprache drei neue und zwei entfernte Schlüssel.
Bestehende Werte wurden geändert: en 1, es 0, fr 816, it 428, pt 0; insgesamt 1.245.
Die früher im gesamten gemeinsamen Arbeitsbaum rekonstruierten 1.246 Werte sind keine
Commitdiffzahl. Zwei fremde neue fr-Schlüssel waren in der ausgewählten Produktbasis
noch nicht vorhanden, ein geometrischer fr-Satz war bereits korrigiert; die endgültigen
zwei zusätzlichen Altwertkorrekturen sind dagegen im obigen Commit enthalten.
Die separate RM-285-Bereichsprüferzeile ist kein Teil dieser RM-290-Auswahl.

Die Entwicklungstore sind keine Fenster-, Renderer-, Leistungs- oder neue Paketabnahme.
Geänderte Handbuchwerte stammen aus den Katalogen; neue Bilder/Handbuchartefakte werden
erst beim Release erzeugt. Die abgeschlossene Einheit steht datiert in `ROADMAP-ARCHIV.md`.
