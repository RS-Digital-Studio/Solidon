# Nachprüfung RM-706 — Fixrunde zum Review (Spitze `29de72b5d`)

Gegenstand: Worktree `F:\sl-rm706`, Zweig `einstellungen/abdruck-eingaenge-rm706`, Spitze
`29de72b5d` (enthält origin/welle4 `ac244486b`). Fix-Diff `35aef0b10..847ceeb49` ohne den Merge,
17 Dateien. Erstreview: `review_rm706.md`. Prüfer rv706, Scratch `scratchpad\rv706\`. Nur
gelesen und gemessen. Im Worktree ist nichts geändert (`git status` sauber, Läufe mit `-B`, ohne
Cacheprovider, `--basetemp` im Scratch). Begonnen 22:58.

## Urteil

**Kann landen nach N1. Eine weitere Prüfung ist nicht nötig.** Alle neun Funde des Reviews sind
behoben; S1, M1, M2 und L1 sind mit den Sonden des Erstreviews am Endstand gemessen. Die drei
Fragen des Koordinators stehen ebenfalls:

- Öffnen/Speichern, ein Spulenwechsel gleicher Sorte und ein Sprachwechsel kippen den Abdruck
  nicht.
- Die Beispielsonde bleibt bei 12/13 gegen 0.5.3 und 13/13 gegen den Stand vor RM-706.
- Der Exportweg rechnet den Bedarf im Arbeiter und hat einen sauberen Fehlerweg.

**N1 (mittel)** ist neu und kommt aus dem Fix zu M2. Die Wahl der Grundlage geht für die
Orca-Familie als **absoluter Dateipfad** in den Abdruck ein. Ein Slicer, der beim Update den
Ordner wechselt, macht damit jeden Druck neu, und das ist genau der Fall, den der Changelog als
behoben nennt. Creality Print legt Installation und Nutzerdaten in Ordnern mit Versionsnummer ab.
Der Fix ist klein: der Profilname statt des Pfads, dazu ein Test. **N2 (leicht)** kann mit, muss
aber nicht.

## Je Fund des Reviews

| Fund | Commit | Nachgeprüft | Ergebnis |
|---|---|---|---|
| S1 Kalibrierung | `52bf0223d` | `sonde_material.py` am Endstand: +0,02 mm Spiel und Lochzugabe an Deckel, Passteil, Gehäuse | **behoben.** Alle vier Platten bekommen einen anderen Abdruck (Dose P0 `6c5662e3…` → `e9c425e4…`, P1 `f3c1fe1f…` → `c87bb3d7…`; Passung `4e852e54…` → `9ee2510c…`; Gehäuse `e9fea280…` → `dca1c35a…`) |
| M1 Antworten | `50bc38a8a` | `sonde_kanten.py`: rechte und linke Kante | **behoben.** `bodies()` verschieden, Abdruck `de5d3d8e…` gegen `6c70e22a…`. Zur Ordnung der Kandidaten siehe N2 |
| M2 eigener Prozess | `d08de7771` | Fenstersonde am echten Dialog, Grundlage aus `_setup_snapshot()` wie `_slice`/`_open_in_slicer` | **behoben.** 0,28 mm (Entwurf) `21d35694…` gegen 0,15 mm (eigener Prozess) `cb80e871…`; ohne `base` wären sie gleich wie vorher. Export: Anschlusstest prüft, dass Datei und Abdruck dieselbe Grundlage tragen. Zur Form der Kennung siehe N1 |
| L1 Streueingänge | `9e610cb47` | `sonde_streu.py` | **behoben.** `bodies()` kennt `obj_1` und `obj_2`, der Abdruck bleibt druckgleich (`8cc55d25…` vor und nach dem Verschieben). Benutzt wird dieselbe Funktion wie in der Auswertung |
| L2 Wächter | `d0e358abb`, `c58199816` | Test gelesen | **behoben.** Jede Lesart von `_with_nested_context` über jede registrierte Operation braucht ein Gegenstück in `_read_beside`, die Untergrenze liegt bei mehr als 20 Lesarten. `matches` deckt M1 mit eigenen Tests |
| L3 Rezepte | `8a5079a30` | Code gelesen, Test des Bauagenten | **behoben.** Das Rezept wird über `recipe.from_data` in der Breite durchlaufen, wie in `_collect_dependencies` |
| L4 Changelog | `3760b182d` | sechs Sprachen gelesen | **behoben.** „Ab dieser Version …“ in allen sechs Sprachen, EN jetzt „Previously, such a print counted as new.“ Gliederung gleich, `test_changelog`/`test_text_length` grün |
| L5 ein Gang | `6a31ffaa9` | Code gelesen | **behoben.** `settled()` rechnet einmal im Arbeiter; der Anschlusstest zählt einen Gang für zwei Platten. Gemessen vom Bauagenten: 594 → 141 ms CPU |

## Fragen des Koordinators

**Was den Abdruck nicht kippen darf** (`sonde_stabil.py`, fünf Beispiele:
`dose-mit-deckel`, `schild-zweifarbig`, `skizze-mit-massen`, `gehaeuse-mit-bausteinen`,
`zu-gross-automatisch-teilen`; Eingänge und feste Grundlage):

| Prüfung | Ergebnis |
|---|---|
| Sprachwechsel de → en → fr, je neu ausgewertet | gleich, 5/5 |
| Spule A gegen Spule B am selben Slot, und gegen gar keine Bindung | gleich, 5/5 |
| Speichern → Öffnen, zweimal hintereinander | gleich, 5/5 |
| Projekt, das noch nie gespeichert war (ganze Zahlen, Projektmaß als Ausdruck), gegen nach dem Öffnen | gleich |

Sprachunabhängig ist auch die Kennung der Grundlage: Pfade, Prusa-Abschnittsnamen und
`cura-instance:`-Kennungen enthalten keinen übersetzten Text.

**S1 bewusst grob:** `_fixed_profile` ist `profile_key(process=False)`. Die Druckerwerte darin
(Bauraum, Sperrzonen) kommen aus Solidons Tabellen oder einer einmaligen Übernahme aus dem Slicer
(`slicer_profiles`, beim Anlegen des Druckers), nicht laufend aus dem Slicer. Ein Slicer-Update
kippt den Abdruck darüber also nicht.

**M1, Rang nach Lage:** Solange der gespeicherte Datensatz steht, ist der Rang stabil, denn
gerechnet wird aus den gespeicherten Zahlen. Eine druckgleiche Änderung am Ergebnis berührt
`matches` nicht. Wird die Frage neu gestellt, etwa weil sich der Scope mit `cache_version`
ändert, kann der Rang trotzdem kippen (N2).

**M2, Export:** `_usage_for` läuft im Exportarbeiter innerhalb von `single_read`, der Hauptthread
ist nicht betroffen. Die Kosten:

- Mit Druckeinstellungen in der Datei nimmt er das schon gestufte Setup, es kostet nichts dazu.
- Ohne Einstellungen ruft er `for_stage` einmal, ebenfalls im Arbeiter.

Fehlerweg: Eine `AppError` endet wie bisher in `failed`, bevor geschrieben wird.
`for_stage(None, …)` gibt `None` zurück, ein Export ohne Slicer bleibt also heil. Neu ist nur,
dass ein Export *ohne* Einstellungen in der Datei Slicerprofile liest. Das ist derselbe Weg wie
mit Einstellungen, `ExternalToolError` wird abgefangen; kein Befund.

## Neue Befunde

### N1 (mittel) — Die Grundlage geht als absoluter Pfad in den Abdruck ein

`app/core/filament_usage.py:509–519`, `_base_choice` (Docstring: „Wo der Slicer liegt, zählt
nicht“), gibt `[flavour, machine_profile, base_process]` zurück. Beide Profilfelder sind
`slicer_profiles.identity()`, und das ist für die Orca-Familie `str(entry.path)`
(`slicer_profiles.py:4077–4092`): Bei ElegooSlicer, OrcaSlicer, Bambu Studio, Creality Print und
Anycubic ist die Kennung also der absolute Pfad der Profildatei. Prusa (Abschnittsname) und Cura
(`cura-instance:`) sind portabel.

**Beleg** (`sonde_grundlage.py`, an den installierten Slicern, nur gelesen):

- Creality Print: `['orca', 'C:\\Program Files\\Creality\\Creality Print 7.2\\resources\\profiles\\…\\machine\\….json', 'C:\\Program Files\\Creality\\Creality Print 7.2\\…\\process\\….json']`.
- Dieselbe Wahl, dieselben Profilnamen unter `Creality Print 7.3`: anderer Abdruck
  (`8275cca9…` → `c3cc92fc…`).
- ElegooSlicer: ebenso Pfade unter `C:\Program Files\ElegooSlicer\…`.
- Creality Print führt die Fassung im Namen der Ordner: Installation `Creality Print 7.2`,
  Nutzerdaten `AppData\Roaming\Creality\Creality Print\7.0` und `7.3`, mit `migration`.

Die Folge: Ein Update von Creality Print in einen neuen Ordner macht jeden schon gebuchten Druck
neu. Dasselbe gilt für eine Neuinstallation an anderer Stelle, eigene Prozesse unter
`user/<Konto>` nach einer Anmeldung im Slicer und denselben Druck auf einem anderen Rechner. Bei
*Ohne Rückfrage buchen* zieht der nächste Export ein zweites Mal ab. Das ist der Fehler, den
RM-706 behebt und den der Changelog als behoben nennt („auch wenn … sich das Herstellerprofil im
Slicer ändert“).

**Fix:** In `_base_choice` die portable Form statt der Kennung, also den Profilnamen, wie er in
die Projektdatei reist (`profile_file`: „in die Projektdatei gehört der Name“):

- für Pfadkennungen der Name der Profildatei (`SlicerProfile.name`, ersatzweise
  `Path(kennung).stem`),
- Prusa und Cura unverändert.

Test: dieselbe Wahl unter zwei Wurzeln ergibt denselben Abdruck, ein anderer Prozessname einen
anderen. Am Stand `29de72b5d` muss er rot sein. In `verbrauch.md` („Ihre **Wahl** zählt“) gehört
„als Name, nicht als Pfad“ dazu.

### N2 (leicht) — Die Ordnung der Kandidaten kippt am Rundungsrauschen

`app/core/filament_usage.py:424–447`, `_rank`/`_place`/`_leaves`: Die Kandidaten werden nach den rohen
Gleitkommazahlen geordnet, zuerst nach der Lage. Liegen zwei Kandidaten in der ersten Koordinate
bis auf Rauschen gleich, entscheidet das letzte Bit und nicht die Koordinate, in der sie sich
wirklich unterscheiden. Bei achsparallelen Teilen ist das häufig: zwei Kanten eines Spalts in y,
zwei Bohrungen einer Reihe.

**Beleg** (`sonde_stabil.py`, Datensatz wie gespeichert, gewählt jedes Mal die Kante bei
y = 0,004):

| Rauschen | Rang |
|---|---|
| keines | 1 |
| erste Kante 1 ulp weiter | 0 |
| zweite Kante 1 ulp weiter | 1 |

Das wirkt nur, wenn die Frage neu gestellt und gleich beantwortet wird, also nach einem
`cache_version`-Schritt (Scope neu) mit geänderten Netzbits. Dann kippt der Abdruck. Das liegt auf
der sicheren Seite, widerspricht aber der Zusage im Docstring („Eine neu gestellte und gleich
beantwortete Frage behält den Abdruck“).

**Fix:** in `_leaves` Zahlen vor dem Vergleich runden, etwa auf 1e-6. Rauschen wird dann zum
Gleichstand, und das nächste Feld entscheidet. Test: 1 ulp Rauschen ergibt denselben Rang.

## Läufe

Alle gepinnt (FFFFF0FF), Exit-Code im Skript direkt nach dem Befehl gelesen.

| Lauf | Ergebnis | Exit |
|---|---|---|
| `sonde_material.py` (S1), `sonde_kanten.py` (M1), `sonde_streu.py` (L1) am Endstand | siehe Tabelle | 0 |
| Fenstersonde eigener Prozess (M2), `PYTHONPATH` auf den Worktree, `app.__file__` geprüft | 1 passed | 0 |
| `sonde_stabil.py` | 0 Probleme, Rang bei Rauschen verschieden (N2) | 0 |
| `sonde_grundlage.py` | siehe N1 | 0 |
| Beispielsonde am Endstand (`sonde706.py`, Beispiele aus `v0.5.3`) | gegen 0.5.3 12/13 über den Vorabdruck (nur `gehaeuse-mit-bausteinen` nicht), gegen welle3-Ende 13/13; druckgleich: Abdruck bleibt 13/13, Vorabdruck kippt 13/13; Netze 21/21 bitgleich | 0 |
| Worktree, ohne Fenster, `-n 4`, 23 Dateien: stored_inputs, fingerprint/gap/atomic-Verlauf, raft, filament_usage, filament_inventory, filaments, edge_binding, export, print_settings, cache, directory_docs, roadmap, changelog, text_length, wording, translations, shared_constants, language_rules, registry_consistency, agent_mirror, core_isolation | 3956 passed, 8 skipped | 0 |
| Worktree, Fenster `test_filament_workflow` / `test_filament_usage_ui` / `test_ui_export` | 39 / 45 / 48 passed (5 deselected) | 0 / 0 / 0 |

`git status` im Worktree danach sauber, Spitze `29de72b5d`.
