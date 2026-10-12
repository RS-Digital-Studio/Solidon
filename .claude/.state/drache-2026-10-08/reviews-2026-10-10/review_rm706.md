# Review RM-706 — Der Abdruck einer Buchung hängt an den gespeicherten Eingängen

Gegenstand: Worktree `F:\sl-rm706`, Zweig `einstellungen/abdruck-eingaenge-rm706`, Spitze
`35aef0b10` (Merge origin/welle4 `e734a0b44`), eigener Diff `git diff origin/welle4...35aef0b10`
(Commits `bee9d1b74`, `41073152e`, 20 Dateien). Prüfer rv706. Scratch: `scratchpad\rv706\`.
Nur gelesen und gemessen; im Worktree nichts geändert (Läufe mit `-B`,
`PYTHONDONTWRITEBYTECODE`, ohne Cacheprovider, `--basetemp` im Scratch; `git status` danach
sauber). Begonnen 21:26, Urteil 22:05 (Systemuhr).

## Urteil

**Nicht landen, solange S1 offen ist.** Der Umbau trägt, was er verspricht: Druckgleiche
Änderungen, Slicer-Updates und neue Grundlagen lassen den Abdruck stehen, gemessen an allen
Beispielen und am Probemerge mit RM-698 Sparen. Buchungen aus 0.5.3 und vom Stand vor RM-706
werden über den Vorabdruck erkannt, *Ohne Rückfrage buchen* hält dabei nicht an.

Die Gegenrichtung hat drei Lücken, alle gemessen: Zwei verschiedene Drucke bekommen denselben
Abdruck. Dann bucht *Ohne Rückfrage buchen* den zweiten Druck nicht, sondern schreibt seine Menge
auf den ersten Vorgang. Unter RM-705 waren es jeweils zwei Drucke.

- **S1 (schwer):** nach einer Kalibrierung (Bauplan §28.3), dem Hauptweg „Deckel klemmt,
  kalibrieren, neu drucken“.
- **M1 (mittel):** bei anders beantworteter Kanten- oder Merkmalsfrage.
- **M2 (mittel):** bei einem eigenen Prozess im Slicer.

**S1, M1 und M2 gehören in einen Zug vor der Landung.** Jeder Fix ändert die Bildung des Abdrucks.
Solange RM-706 nicht ausgeliefert ist, geht das ohne weiteren Vorabdruck, nur `PINNED_BOOKING`
zieht nach. Nach einer Auslieferung bräuchte jeder Fix eine weitere Stufe in `former_fingerprints`.

**Es drängt nichts:** RM-698 Sparen (`506ca0755`) ändert keine Netzbits. Gemessen sind 21 von 21
Körpern bitgleich und der Vorabdruck aus Cache und frisch gleich (Zusatzpunkt unten). Erst die
Varianten A bis C des Entwurfs „schmale Netze“ müssen auf RM-706 warten.

**Nachprüfung: ja**, wegen eines schweren und zweier mittlerer Befunde. Sie kann kurz sein:
drei neue Tests, die je am Stand `35aef0b10` rot sind, dazu die Beispielsonde noch einmal
(Vorabdruck 12/13 und 13/13, druckgleich 13/13).

## Zusatzpunkt des Koordinators: Probemerge mit welle4 `506ca0755` (RM-698 Sparen)

**(1) Probemerge** ohne Worktree: `git merge-tree --write-tree 506ca0755 35aef0b10` → Exit 0,
**kein Konflikt**, Baum `ba5df7708`; automatisch zusammengeführt nur die sechs
`changelog/*.md`. Codekopie per `git archive` nach `scratchpad\rv706\kmerge`.

**(2) Beispielsonde am Probemerge** (`sonde706.py` des Bauagenten, Beispiele aus `v0.5.3`,
gepinnt, Exit 0):

| Vergleich | Ergebnis |
|---|---|
| Buchungen aus 0.5.3 (`rv705\beisp\ergebnis.k053`) | 12 von 13 über den Vorabdruck, nur `gehaeuse-mit-bausteinen` nicht (bewusste Bausteinänderungen, wie bisher) |
| Buchungen vom Stand vor RM-706 (`koord\beisp_w3end`) | 13 von 13 über den Vorabdruck |
| Netze gegen welle3-Ende | 21 von 21 Körpern bitgleich |
| Abdrücke Probemerge gegen Zweig `35aef0b10` | 13 von 13 gleich |
| druckgleich verändert | Abdruck bleibt 13/13, Vorabdruck kippt 13/13 |

**Vorabdruck aus Cache und frisch** (`sonde_cache.py`, zwei Prozesse je Satz: `schreiben` füllt
einen Plattencache im Scratch, `lesen` öffnet in einem neuen Prozess). Verglichen werden je Körper
Prüfsumme über `vertices.tobytes()`/`faces.tobytes()` samt Datentypen und je Platte Abdruck,
Vorabdruck und Altabdrücke, jeweils gegen A:

- A frisch ohne Cache (gemerkte Schritte vergessen); B1/B2 Speicher-Cache kalt und warm;
- C1 Plattencache nach dem Öffnen (4–7 Plattentreffer je Projekt, frühere Einträge werden
  über `_lean_earlier_disk_hit` schlank); C2 derselbe Cache noch einmal (Speichertreffer auf
  schlanken Einträgen, `trim`/`_restore_shown`);
- D letzter Schritt aus und wieder an am selben Cache (der Strg+Z-Fall aus der Nachprüfung N2).

| Satz | Abweichungen von A | Datentypen |
|---|---|---|
| zwölf Beispiele aus `v0.5.3` | **0** | überall `float64/int64` |
| zwölf Beispiele des Probemerges | **0** | überall `float64/int64` |

`skizze-mit-massen` hat keinen Plattentreffer (exakter Körper, `MeshCodec.stores` legt nur Netze
ab), die übrigen elf je 4–7.

**Der int32-Fall ist in `506ca0755` nicht gebaut.** Gemeint ist Variante C des Entwurfs
`entwurf-schmale-netze-2026-10.md`, „weitet beim Lesen wieder auf int64“.
`MeshData.to_bytes` schreibt `float64`/`int64`, `from_bytes` liest über `trimesh` zurück, und
`MeshData.lean` baut ein neues Netz über denselben Feldern. Gemessen ist also der gemergte
Stand. Für Variante C muss dieselbe Sonde erneut laufen (`lauf6.sh`, Ordner `kmerge` ersetzen),
und dort ist jede Abweichung schwer.

**Tests am Probemerge** (Kopie `kmerge`, `PYTHONPATH` auf die Kopie, `app.__file__` geprüft):
stored_inputs, fingerprint_history, gap_history, filament_usage, `test_cache.py`,
directory_docs, changelog, roadmap, text_length und wording ergeben **520 passed, 4 skipped,
1 failed**. Der eine rote Test ist `test_memories_stay_out_of_the_repository`: Er ruft
`git ls-files` auf, und das endet in der Archivkopie ohne `.git` mit Status 128. Ein Codebefund
ist das nicht. Die Budgets von Karten und Regeln sind auch nach dem Merge grün.

## Befunde

### S1 (schwer) — Eine Kalibrierung ändert den Druck, nicht den Abdruck

`app/core/filament_usage.py:379–388` (`_machine`): Vom Material geht nur die Kennung ein.
Spiel, Presssitz, Lochzugabe, Elefantenfuß und Schrumpf gehen aber in jede Geometrie mit einem
`auto:<material>`-Maß ein: Deckel, Passungen, Bausteine, Lochfelder (`profiles.for_object`,
`container_ops`, `lid`, `pins`, `profile_clamp_ops`). Bisher standen sie über `profile_key` und
die Netzbits im Abdruck. Bauplan §28.3 sagt dazu: „Werte landen im Materialprofil … rechnen alle
bestehenden Projekte danach mit den kalibrierten Werten neu.“ `types.Tolerance` sagt dasselbe.

**Beleg** (`sonde_material.py`, Spiel und Lochzugabe je +0,02 mm wie nach einer Messung,
dieselbe Materialkennung, gepinnt, Exit 0):

| Beispiel | Netze | Abdruck | Vorabdruck |
|---|---|---|---|
| `dose-mit-deckel` | Dose 34833,937 → 34839,152 mm³, Deckel 31723,834 → 31711,436 mm³ | gleich (P0 `61c4fe06…`, P1 `682eb87b…`) | verschieden |
| `passung-nach-materialwechsel` | Passteil 20628,490 → 20619,642 mm³ | gleich (`afbcae64…`) | verschieden |
| `gehaeuse-mit-bausteinen` | beide Körper anders | gleich (`2584a4a4…`) | verschieden |

Der Kundenweg nach §28.3 lautet: drucken, der Deckel klemmt, kalibrieren, neu drucken. Dabei
bekommt der zweite Druck den Abdruck des ersten. *Ohne Rückfrage buchen* findet den ersten
Vorgang und schreibt die Menge des zweiten darauf; gebucht ist am Ende **ein** Druck. Das
Verhalten bei gleichem Abdruck hält `test_automatic_booking_keeps_a_booking_under_the_former_fingerprint`
fest: 42 g, dann 47 g, der Bestand sinkt um 47 g und nicht um 89 g. Der Dialog meldet
„schon gebucht“.

**Fix:** Je Körper die Werte seines Materials in den Abdruck nehmen, also
`profiles.for_object(profile, body).material`. Das Projektmaterial, eigene Materialien eines
Körpers oder einer Spule und mitreisende Profile (`carried_profiles`) sind damit gedeckt. Zu den
Werten gehören die, die `hashing._profile_parts` als fest führt: `clearance`, `press`,
`hole_compensation`, `elephant_foot` und `shrinkage`. Die Mechanikwerte kommen dazu, wenn eine
Operation aus ihnen Maße rechnet. Druckerwerte wie Bauraum und Sperrzonen können draußen bleiben,
sie bestimmen nur Lage und Platte.

Das ist bewusst grob und folgt dem Cache-Schlüssel, der dieselben Werte in jeden Schritt nimmt.
Eine Kalibrierung kippt so auch den Abdruck eines schlichten Quaders. Sie ist selten, und
lieber kippt der Abdruck, als dass zwei Drucke ihn teilen. Eine genauere Fassung („nur Schritte,
die Material lesen“) bräuchte eine Angabe am Register, die es nicht gibt.

**Test:** dieselbe Datei mit kalibriertem Spiel ergibt einen anderen Abdruck, ein Slicer-Update
weiter nicht. Am Stand `35aef0b10` muss er rot sein.

Regel `verbrauch.md` („Drucker und Material zählen mit ihrer Kennung, nicht mit ihren
Tabellenwerten“), Archiv und `karte-app-core.md` ziehen nach.

### M1 (mittel) — Gespeicherte Antworten (`Operation.matches`) fehlen im Abdruck

`app/core/filament_usage.py:225–237` (`_stored_bodies`): Ein Schritt geht mit Name, Werten,
Startwert, Eingängen, Lesarten und Bausteinfassung ein, nicht aber mit `operation.matches`. Dort
stehen zwei Arten von Antworten:

- **Kantenantworten** (`edge-answer:`). `scene/edge_binding.py` sagt dazu: „eine andere Antwort
  ist eine andere Geometrie des Verbrauchers“. Deshalb steht `binding_context` im
  Cache-Schlüssel (`evaluate.py`, `binding_context = {**binding.context, **surface_binding.context}`).
- **Merkmalszuordnungen** (§21.3). Nach ihnen findet ein späterer Schritt sein Merkmal.

Archiv und Bericht nennen „keine Zuordnungsantwort“ als Entscheidung. Für die Geometrie trägt
diese Entscheidung nicht.

**Beleg** (`sonde_kanten.py`, Dokument und Register aus `tests/test_edge_binding.py`, gepinnt,
Exit 0):

- Aufbau: gleiche Parameter, die Antwort einmal rechte, einmal linke Kante. Beide sind mit
  `record_matches` gespeichert und ohne Frage neu ausgewertet.
- Netze verschieden: Prüfsumme `b2470e83…` gegen `e2cab80f…`, die Rundung liegt bei
  x = +0,07…+0,59 bzw. −0,59…−0,07 mm.
- `StoredInputs.bodies()` gleich, **Abdruck gleich** (`0d57bef3…`), Vorabdruck verschieden.

Der Fall ist seltener als S1, weil eine Mehrdeutigkeit anders beantwortet werden muss, etwa nach
einer erneuten Frage. Er verletzt aber denselben Vertrag.

**Fix:** Die Entscheidungen aus `matches` gehören in den Schritt, nicht der rohe Datensatz:

- `scope` muss draußen bleiben. Er ist der Hash des Eingangs und steigt mit `cache_version`
  (`test_a_saved_answer_holds_only_for_the_same_input_version`).
- Die Kandidaten tragen Rohkoordinaten und gehören ebenfalls nicht hinein.
- Hinein gehören je Datensatz Domäne, Körper, Feld und Schlüssel, dazu je Entscheidung der
  gewählte Kandidat als Rang in einer geometrischen Ordnung der Kandidaten oder `not_carried`.
- Wo das nicht trägt, nimmt der betroffene Körper zusätzlich seine Netzprüfsumme mit.

Test: zwei Antworten ergeben zwei Abdrücke. Eine nach einem `cache_version`-Schritt neu gefragte
und gleich beantwortete Frage behält den Abdruck.

### M2 (mittel) — Ein eigener Prozess im Slicer ändert den Druck, nicht den Abdruck

`app/core/filament_usage.py:348–376` (`_owned_settings`) und `print_settings_dialog.py:5735–5788`
(`_show_own_process`, `_process_picked`). Gehört der gewählte Prozess zu keiner Stufe, bleibt
`settings.quality` stehen. Das Feld zeigt dann „Eigener Prozess“, die Grundlage und mit ihr die
Schichthöhe folgt dem Prozess (`_rebase`). Gemerkt wird die Wahl am Gerät
(`ui_settings.slicer_base_process`), nicht im Projekt. Der Abdruck sieht beides nicht.

**Beleg** (`eigenprozess\test_sonde_eigenprozess.py`, am echten Dialog mit Fenster, Aufbau wie
`test_the_quality_picks_the_manufacturers_process`, PrusaSlicer-Bündel MK4S, gepinnt,
1 passed, Exit 0):

| Prozess | Feld Qualität | `quality` | Schichthöhe | Abdruck |
|---|---|---|---|---|
| `0.28mm DRAFT` | Entwurf | `draft` | 0,28 | `11ab5af7…` |
| `0.15mm SPEED` (eigener Prozess) | Eigener Prozess | `draft` | 0,15 | `11ab5af7…` |

`explicit` ist in beiden Fällen leer, der Vorabdruck verschieden. Ein Druck mit 0,28 mm und einer
mit 0,15 mm Schicht tragen also einen Namen. Dasselbe gilt für ein anderes Maschinenprofil und
für einen Wechsel des Slicers bei gleicher Stufe.

**Fix:** Die *Wahl* der Grundlage gehört zum Druck, ihr Inhalt nicht. Gemeint ist ihre Kennung
(Slicerart, Maschinen- und Prozessprofil), mindestens der Prozess, sobald er nicht der Stufe folgt
(`_follows_stage`). Beide Wege kennen sie: der Plattenauftrag als `job.setup`, der Export als
`_chosen_setup_now()`.

Einfacher wäre es, die wirksamen Schichtwerte (`layers.*`) mitzunehmen. Dann kippt aber auch ein
Slicer-Update, das die Schichthöhe einer Stufe ändert, was selten vorkommt und dann ohnehin ein
anderer Druck ist. Test: eigener Prozess ergibt einen anderen Abdruck, ein Slicer-Update mit
gleichem Profilnamen nicht.

### L1 (leicht) — Altdateien mit überzähligen Erzeugereingängen fallen auf die Netzbits zurück

`app/core/filament_usage.py:238–240`. `_stored_bodies` bildet `evaluate._without_stray_inputs`
nicht nach. Ein Erzeuger mit Eingängen, wie er in Dateien vor dem 07.09.2026 vorkommt, verbraucht
im Abdruck den genannten Körper. Die Auswertung lässt ihn stehen
(`evaluate.creator_inputs_dropped`).

**Beleg** (`sonde_streu.py`): Die Szene hat `obj_1` und `obj_2`, `bodies()` kennt nur `obj_2`.
`obj_1` geht deshalb über `digest("unstored", …)` mit seinen Netzbits ein, und druckgleich
verschoben kippt der Abdruck (`67adca5b…` → `1eedd4fe…`). Zwei Drucke teilen dabei keinen Abdruck,
es geht nur die Stabilität verloren.

**Fix:** denselben Filter anwenden, am besten die Funktion der Auswertung selbst. Test mit dieser
Datei.

### L2 (leicht) — Zwilling der Auswertung ohne Wächter

`_stored_bodies` bildet den Gang der Auswertung nach: Reihenfolge, ausgeschaltete Schritte,
unbekannter Schritt und Eingangsfilter. `_read_beside` bildet die Lesarten aus
`_with_nested_context` und `binding_context` nach. Kein Test lässt beide dieselbe Frage
beantworten. Zweimal sind sie schon auseinandergelaufen (M1, L1).

Die Regel sagt „gehört die Lesart in `_read_beside` wie in `evaluate._with_nested_context`“. Sie
lädt aber weder bei `scene/evaluate.py` noch bei `scene/edge_binding.py` oder `registry/params.py`,
also genau dort nicht, wo eine neue Lesart entsteht. Ein Docstring ist kein Wächter
(`zwillinge.md`, Klasse „gewollt“: ein Test, der beide gleich antworten lässt).

**Fix:** ein Wächter über das Register. Je Parameterart, die `_with_nested_context` liest
(`SOURCE_KINDS`, `feature`/`features`/`targets_feature`, Skizzenebene, `nested_references()`,
`reads_scene`, `reads_other_bodies`), wird der Gelesene geändert, und `bodies()` muss sich ändern.
Dazu kommt ein Fall für `matches`. Die `paths:` von `evaluate.py` aus Budgetgründen nicht
erweitern.

### L3 (leicht) — Rezepte nennen die Fassung ihrer eingebetteten Bausteine nicht

`app/core/filament_usage.py:340–345` (`_part_versions`). Die Fassung eines Rezepts ist der Hash
des Rezepts (`recipe.fingerprint`). Ein darin gesetzter Bibliotheksbaustein mit neuer `PartChange`
ändert die Geometrie, das Rezept und der Abdruck bleiben aber gleich. Das ist selten, weil es ein
eigenes Rezept mit einem später geänderten Bibliotheksbaustein voraussetzt.

**Fix:** `used_parts` für Rezepte rekursiv über `recipe_data` gehen und deren Fassungen
mitnehmen, so wie `_collect_dependencies` es tut.

### L4 (leicht) — Changelog: englischer Satz holpert, und der Satz gilt erst ab dieser Version

`changelog/en.md`: „Until now the print then counted as new.“ Vorschlag: „Previously, such a
print counted as new.“

In allen sechs Sprachen gilt die Zusage „bleibt ihrem Druck zugeordnet“ für Buchungen ab dieser
Version. Buchungen aus 0.5.x hängen am Vorabdruck und kippen mit dem nächsten Update, das
Netzbits ändert, also RM-698 A bis C. Vorschlag: „Ab dieser Version bleibt eine Buchung …“. Wer
das nicht will, muss im Changelog von RM-698 den Verlust für ältere Buchungen nennen.

Die Ursache `39933e994` liegt in `v0.4.0` bis `v0.5.3`, die Behebung ist richtig eingeordnet.
Länge, Testfamilie und Gliederung sind grün (`test_changelog`, `test_text_length`).

### L5 (leicht, Leistung) — `bodies()` läuft je Platte neu

`print_settings_dialog.py:2268` (`_OpenInSlicerWorker._open_all`): `prepare` wird je Platte
gerufen, also je Platte ein ganzer Gang über den Stapel. Eine **verknüpfte** Quelle wird dabei
jedes Mal ganz gelesen und gehasht (`ProjectSources.identity` merkt sie absichtlich nicht). Bei
vier Platten und einer großen verknüpften STL sind das vier Lesezüge im Arbeiter.

**Fix:** `bodies()` einmal je Auftrag rechnen, im Arbeiter, und an `prepare` weiterreichen.
Messung vorher und nachher.

## Was hält (geprüft, kein Befund)

- **Druckgleich:** Umsortieren, Verschieben um `PRINT_LIMIT/4`, float32 und alles zusammen lassen
  den Abdruck stehen, an 13 von 13 Platten der Beispiele. `cache_version` geht nicht ein, ebenso
  wenig Slicer-Grundlage, Spulenbindung und `mesh.slots`. Die Belegung kommt aus den Schritten,
  `assigned` trägt die Identität je benutztem Slot.
- **Eingänge:**
  - Ausgeschaltete Schritte, `stopped_at` und unbekannte Schritte werden behandelt wie in der
    Auswertung.
  - Projektmaße gehen samt Kette ein, als Ausdruck und plattformgleich. Ausdrücke lesen nur
    Parameter (`_FUNCTIONS`: `min`, `max`, `abs`, `round`), die Einheit eines Parameters rechnet
    nicht.
  - Quellen: Inhaltsprüfsumme vor und nach dem Speichern gleich, Pfadtrenner plattformgleich.
  - Bausteinfassung, auch für eigene Bausteine als Datei-Abdruck.
  - Startwert, Duplizieren (`leaves_inputs_unchanged`), Umbenennen und Prüfen
    (`unchanged_effect`), Spiegeln und Anordnen als Schritte.
  - Sichtflächen (`Document.protected`) liest nur die Planung der Sitzung, keine Operation.
    Passungen liest keine Operation für Maße. Übersetzbar markiert sind nur Namen.
- **Vorabdruck:** belegte Gleichheit, `identities` in `_previous`, `_legacy_bookings`,
  `_reversed_count` und `expected_history`. Nachbuchen behält den Abdruck des Vorgangs, die
  Konfliktprüfung in `filaments.book` bleibt. `UsageNotice._completed` heißt nach dem Angebot.
  *Ohne Rückfrage buchen* hält bei einer Buchung aus 0.6.0 nicht an, weil `_legacy_bookings` leer
  ist, sobald eine Identität trifft.
- **Snapshot:** `deepcopy(document)` und `snapshot` brauchen am Drachen (41 MB Quelle) und an den
  größten Beispielen unter 1 ms (`sonde_kosten.py`). Die Quellbytes werden geteilt, nicht
  kopiert, und das Fenster arbeitet auf einer eigenen Kopie weiter. Export und beide Slicerwege
  geben die Eingänge mit (alle Bauorte von `_PlateJob` und `_ExportWorker` geprüft). Nur
  `_StockWorker` rechnet ohne, und der benutzt den Abdruck nicht. Die Fenstertests halten den
  Anschluss, auch ohne `main_window.py` in den `paths:` der Regel.
- **Regeln:** 1, 3 bis 6, 10 bis 13, 17, 20 und 22 sind nicht berührt oder eingehalten
  (kein Qt im Kern, kein neuer Text, keine Abhängigkeit, Bezeichner englisch, Kommentare deutsch
  mit Umlauten). Die stillen `suppress(AppError)` in `_read_beside`/`_declared` sind begründet:
  Ein unlesbarer Ausdruck hält die Auswertung vor diesem Schritt an. Der Archiveintrag steht
  (`test_roadmap` grün). Die Kartenbudgets sind am Zweig und am Probemerge grün.
- **`PINNED_BOOKING`** ist ein Festwert ohne Herkunft von außen und als solcher benannt. Er hält
  die Bildung fest und muss mit S1, M1 und M2 neu gesetzt werden. Einen Vorabdruck braucht es
  dafür nicht, solange RM-706 nicht ausgeliefert ist.

## Läufe

Alle gepinnt (FFFFF0FF), Exit-Code im Skript direkt nach dem Befehl gelesen.

| Lauf | Ergebnis | Exit |
|---|---|---|
| Worktree, ohne Fenster: 20 Dateien (stored_inputs, fingerprint/gap/atomic-Verlauf, raft, filament_usage, filament_inventory, filaments, edge_binding, directory_docs, roadmap, changelog, text_length, wording, translations, shared_constants, language_rules, registry_consistency, agent_mirror, core_isolation) | 2562 passed, 4 skipped | 0 |
| Worktree, Fenster `test_filament_workflow.py` | 39 passed | 0 |
| Worktree, Fenster `test_filament_usage_ui.py` | 45 passed | 0 |
| Beispielsonde am Zweig (`sonde706.py`, Kopie) | gegen 0.5.3 12/13, gegen welle3-Ende 13/13 (Vorabdruck), druckgleich 13/13, Abdrücke = Lauf des Bauagenten | 0 |
| `sonde_kanten.py` (M1), `sonde_material.py` (S1), `sonde_streu.py` (L1), `sonde_kosten.py` | siehe Befunde | 0 |
| Fenstersonde eigener Prozess (M2) | 1 passed | 0 |
| Probemerge `merge-tree` | kein Konflikt | 0 |
| Probemerge: Beispielsonde, Cache-Sonde (2 × 2 Prozesse) | siehe Zusatzpunkt, 0 Abweichungen | 0 |
| Probemerge: Tests (10 Dateien) | 520 passed, 4 skipped, 1 failed (`git ls-files` in der Archivkopie) | 1 (Kopie) |

`tools/affected_tests.py` meldet für die Dateien des Diffs die Suite (Bauagent), deshalb gezielt
gewählt.

## Gelesen

- Jede Zeile des Diffs: `filament_usage.py` (Kern und UI), `main_window.py`,
  `print_settings_dialog.py`, vier Testdateien, `verbrauch.md`, `app/core/CLAUDE.md`,
  `karte-app-core.md`, `karte-tests.md`, Archiv und sechs Changelogs.
- Gegengehalten an:
  - `evaluate._evaluate`: Schleife, `_without_stray_inputs`, `_without_absent_inputs`,
    `_missing_inputs`, `_with_nested_context`, `nested_references`, Op-Hash mit
    `binding_context`;
  - `hashing` (`digest`, `_profile_parts`, `profile_key`, `operation_hash`);
  - `edge_binding`, `History.record_matches`, `Operation.matches`;
  - `profiles` (`for_process`, `for_object`, `_material_from_table`), Bauplan §28.3;
  - `parts.registry` (`used_parts`, `mark_source`), `parts.user`, `parts.recipe`;
  - `ProjectSources.identity`, `_read_linked_source`, `PrintSettings` (`explicit`,
    `plate_choices`), die Prozesswahl im Dialog;
  - `_auto_book`, `_previous`, `_legacy_bookings`, `UsageDialog._book`, `UsageNotice`,
    `_StockWorker`, alle Aufrufer von `prepare`.
- Für den Zusatzpunkt `cache.py` (Diff `e734a0b44..506ca0755`), `transform._copy_to_move`,
  `MeshData.lean`/`to_bytes`/`from_bytes` und der Entwurf „schmale Netze“.
