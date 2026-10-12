# Kontrolle RM-589: Fix-Diff der Schlussprüfung

Prüfling: Worktree `F:\sl-loecher`, Zweig `einstellungen/loecher-rm589`, Stand `971b05eaa`.
Geprüft wurde nur der Fix-Diff: `37c0ea161` (S1, S2), `1ddd29607` (S3), `971b05eaa` (Archiv,
Budget) und die Regeldatei aus dem Merge `cfc151878`. Grundlage sind
`reviews-2026-10-10/review_rm589_schluss.md` und `berichte-2026-10-10/rm589c.md`.
Sonden und Ausgaben liegen in `scratchpad\rv589k\`: Kopie `mut` = `971b05eaa` per
`git archive` für Sonden und Tore, Kopie `mut2` für die Mutationen. Alles lief gepinnt
(`FFFFF0FF`), `app` jeweils aus der Kopie. Am Worktree habe ich nichts geändert,
`git status` ist vorher und nachher leer.

## Urteil

**Nicht, bis K1 behoben ist.** Für K1 reicht eine Behebung ohne neue Prüfrunde.
S1 ist für alle genannten Wege behoben: Ausrichten, Drehen, Spiegeln, Teilen, Deckel,
*Stift für Bohrung*, *Behältereinsatz*, Kopie, Duplizieren und Kopien in Reihe oder Kreis,
auch Kreis um x mit gekippten Kopien. Die bekannten Reste liegen auf der sicheren Seite und
verhalten sich wie `main`. S2 hält in jedem Fall gegen den Schnitt, in beiden Kernen und
beiden Qualitätsstufen. Die S3-Tests prüfen, was sie sollen: Jede der vier Mutationen macht
sie rot. Alle Tore sind grün.

Offen bleibt ein leichter Rest derselben Bauart wie S1, aber auf der unsicheren Seite:
Ein Schritt nach dem Einziehen nimmt das Band an Ort und Stelle weg, oder der Körper wird
vor dem Einziehen gekippt und danach zurückgedreht. In beiden Fällen bekommt er weiter
„Erste Schicht einziehen → 0“ und druckt ohne Einzug am Bett. Auf `main` zieht der Slicer
dort ein.

## Funde

### Leicht

**K1 Nach *Abschneiden* oder *Abziehen* unten und nach Kippen, Einziehen und Zurückdrehen
zählt der Fuß, obwohl am Bett kein eingezogenes Band liegt.**
`app/core/scene/fits.py:592-609` (`_foot_on_the_bed`). Dort genügt ein `FOOT_OP` auf der
eigenen Linie zusammen mit Rahmen-Z nach oben. Schritte an Ort und Stelle zählen als Linie,
auch wenn sie das Band wegnehmen. Der Rahmen sagt nur, wie der Körper jetzt steht, und nicht,
wie er beim Einziehen stand.

- Beleg ist die Sonde `k1b.py` (K1 Max, PETG, Fuß 0,2 mm im Profil). Als Wahrheit dient der
  gerechnete Körper: Der Umriss 0,1 mm über der Unterseite muss rundum im Umriss 1,0 mm
  darüber liegen, eingezogen um 0,05 mm.

  | Schritte | allowances | Rahmen-Z | Band am Bett eingezogen |
  |---|---|---|---|
  | Turm, Fuß, *Abschneiden* z 5 „oben behalten“ | `('foot',)` | (0,0,1) | **nein** |
  | Turm, Fuß, Quader unten *abziehen* | `('foot',)` | (0,0,1) | **nein** |
  | Turm, Drehen x 90, Fuß, Drehen x −90 | `('foot',)` | (0,0,1) | **nein** (Band an einer Seite) |
  | Quader, Drehen x 180, Fuß, Drehen x 180 | `('foot',)` | (0,0,1) | **nein** (Band oben) |
  | Gegenprobe: Turm, Fuß, *Abschneiden* z 30 „unten behalten“ | `('foot',)` | (0,0,1) | ja |

- Folge: Übernommen stellt der Rat den Einzug des Slicers auf 0, und die neue Unterseite
  druckt mit Elefantenfuß. Das ist dieselbe Wirkung, die S1 am liegenden Turm gemessen hat
  (OrcaSlicer: Schicht 1 nur 0,080 statt 0,380 mm schmaler als die Mitte). RM-589
  verschlechtert diese Wege gegenüber `main`.
- Häufigkeit: selten. Der Nutzer muss nach dem Einziehen selbst abschneiden oder abziehen,
  oder zweimal drehen. Der Prüfbericht bietet *Abschneiden* nicht an (`cut_away` steht nur in
  `registry/search.py:301` und `ui/panels.py:591`).
- Die Unterlagen sagen mehr, als der Code hält. Der Docstring von `_foot_on_the_bed`
  (`fits.py:586-587`) sagt: „wurde er vorher gekippt, zählt er nicht“. Zurückgedreht zählt
  er aber. Auch `allowances_for` (`fits.py:422-423`), `.claude/rules/druckrat.md` und der
  Archiveintrag (`ROADMAP-ARCHIV.md`, „Er zählt jetzt nur, wo das eingezogene Band am Bett
  liegt“) versprechen mehr.

**Fix:** In `_foot_on_the_bed` nach dem Treffer auf der Linie am fertigen Körper bestätigen,
dass das Band am Bett eingezogen ist. Höhe `h` und Betrag `a` kommen aus dem Fußschritt
(`_step_values`: `height`, `amount` oder `elephant_foot` des Materials). Dann muss
`cross_section(Unterseite + h/2)` in `cross_section(Unterseite + h + δ).buffer(-a/2)` liegen.
Das kostet zwei Schnitte und nur dann, wenn ein Fußschritt auf der Linie liegt. Die
Rahmenprüfung darf bleiben.

Tests am gerechneten Körper, mit dem Sollwert aus dem Schnitt wie beim S2-Test:

| Schritte | Soll |
|---|---|
| Abschneiden unten | `()` |
| Abschneiden oben | `foot` |
| Drehen x 90, Fuß, x −90 | `()` |
| Wenden, Fuß, Wenden | `()` |

Danach Docstrings, Regel und Archiv auf den neuen Stand bringen.

Wahlweise und genauer: Mit dieser Bestätigung lässt sich Bedingung (2) auf die ganze
Herkunft (`_producing`) lockern. Dann zählen auch die untere Hälfte eines waagerechten und
beide Hälften eines senkrechten Schnitts, so wie das gestempelte Merkmal, das der Bauagent
als neuen Punkt vorschlägt. Der Testfall „waagerecht geteilt“ erwartet für die untere Hälfte
`()`. Das ist die bewusste sichere Seite und nicht die Lage des Bands, und das sollte der
Test sagen.

## S1: `_foot_on_the_bed` am gerechneten Körper

Sonden `k1.py` und `k1b.py` (eigene) sowie `n1.py` und `n1b.py` (des Schlussprüfers),
erneut an `971b05eaa` gefahren, alle mit EXIT=0.

| Fall | allowances | Band am Bett | Urteil |
|---|---|---|---|
| Turm unverändert, angeordnet, aufs Bett, Drehen z 90, Spiegeln x | `foot` | ja | richtig |
| Kopie, Duplizieren ×3, Reihe, Kreis um z (je Kopie) | `foot` | ja | richtig |
| Kreis um x: Original / Kopien 90°, 180°, 270° | `foot` / `()` | ja / nein | richtig |
| Vereinigen A(Fuß)+B, B+A | `foot` | Mischfall | wie bisher |
| Ausrichten liegend (Turm), Drehen x 90 und y 90 | `()` | ja | sichere Seite |
| Ausrichten stehend (Quader 30×30×10) | `foot` | ja | richtig |
| Drehen x 180, Spiegeln z | `()` | nein | richtig |
| Teilen waagerecht: untere / obere Hälfte | `()` / `()` | ja / nein | sicher / richtig |
| Teilen senkrecht: beide Hälften | `()` | ja | sichere Seite |
| Deckel: Gehäuse / Deckel | `foot` / `()` | ja / nein | richtig |
| *Stift für Bohrung*: Träger / Stift | `holes, foot` / `()` | ja / nein | richtig |
| *Behältereinsatz*: Behälter / Deckel / Einsatz | `foot` / `()` / `()` | ja / nein / nein | richtig |
| erst drehen, dann ausgleichen | `()` | ja | sichere Seite |
| Ausrichten, ausgleichen, Ausrichten | `()` | ja | sichere Seite |
| *Abschneiden*/*Abziehen* unten; kippen, ausgleichen, zurück | `foot` | **nein** | **K1** |

Die Sonde `n1.py` stimmt in jeder Zeile mit dem Bericht des Bauagenten überein (`n1.txt`).
`n1b.py` ergibt für den liegenden Turm `()` mit Rahmen-Z (0,−1,0). Der Fall „Keil“ scheitert
an der Sonde selbst, denn `create_wedge` gibt es nicht.

**Der bekannte Rest liegt auf der sicheren Seite.** Das gilt für „erst drehen, dann
ausgleichen“, die untere Hälfte waagerecht, beide Hälften senkrecht und den nach dem
Ausgleich wieder liegenden Körper. Laut Schnitt ist das Band am Bett jedes Mal eingezogen,
und es kommt kein Rat. Der Slicer zieht also zusätzlich ein, im Profil 0,2 mm im Modell
plus 0,15 mm im K1-Max-Prozess. Die erste Schicht wird schmaler, einen Wulst gibt es nicht.
`main` verhält sich hier genauso, weil der Slicer dort immer einzieht. Das habe ich
hergeleitet und nicht am Slicer gemessen. Gemessen sind beide Einzelfälle aus dem Bericht
des Bauagenten (0,380 und 0,480 mm).

Gegenprobe der S1-Tests per Mutation (`lauf_mut.sh`, `mut.txt`):

| Mutation | Ergebnis |
|---|---|
| ohne Lageprüfung | 4 rot (Ausrichten, gekippt, gewendet, Spiegeln z) |
| `abs(up)` statt Vorzeichen | 2 rot (gewendet, Spiegeln z) |
| jeder neue Körper zählt wie eine Kopie | 2 rot (waagerecht geteilt, Deckel) |
| Grundlauf | 12 bestanden |

## S2: `_closes_between_mouths` gegen den Schnitt

Sonde `k2.py` (Kobra 2, PETG, Ø 6 mit Haken). Der Schnitt prüft alle 0,05 mm, ob ein
Polygon einen Innenring hat.

| Fall | alt | neu | Mündungen | Schnitt | allowances |
|---|---|---|---|---|---|
| senkrecht in waagerechter Platte 8 mm (fine, draft) | ja | ja | ja | ja | `holes` (unverändert) |
| senkrecht in waagerechter Platte 1 mm | ja | ja | ja | ja | `holes` |
| waagerecht (Achse x) | nein | nein | nein | nein | `()` |
| Sackloch senkrecht 4 von 8 | ja | ja | ja | ja | `holes` (unverändert) |
| gebohrt, dann um 30° / 50° gekippt | ja | ja | ja | ja | `holes` |
| gebohrt, dann um 56° gekippt; 4 mm um 45° | nein | nein | nein | nein | `()` |
| Platte 3 mm/60°, dann senkrecht gebohrt (fine, draft) | **ja** | nein | nein | nein | `()` (S2 behoben) |
| exakter Kern: senkrecht / Platte 3 mm/60° senkrecht gebohrt | ja / **ja** | ja / nein | ja / nein | ja / nein | `holes` / `()` |
| ohne Haken | ja | ja | ja | ja | `()` |
| zwei sich kreuzende Bohrungen | ja / nein | ja / nein | `None` (Formel) | ja | `holes` |

Das neue Urteil stimmt in jedem Fall mit dem Schnitt überein. Je Körper braucht
`allowances_for` höchstens 16 ms CPU, `_welded` ist je Körper gemerkt. Nicht gemessen habe
ich „Sackloch von unten“ (die Sonde nannte die Achse `-z`, keine Auswahl) und das Langloch
(falsche Parameter in der Sonde). Das sind Sondenfehler, keine Befunde.

Gegenprobe: Mit `between = None` werden 2 Fälle rot (3/60, 4/45), der Grundlauf hat 10
bestanden.

## S3: die zwei Tests per Mutation

`mut2`, `profiles.py`. Nach jeder Mutation ist die Datei wieder hash-gleich
(`87a98a67…`):

| Mutation | rot |
|---|---|
| Liste `measured` übergangen | `…keeps_what_was_measured[measured1]`, `…travels_with_what_was_measured` |
| Altweg ohne Startwert leer | `…keeps_what_was_measured[None]` |
| `_as_table` ohne `measured` | `…travels_with_what_was_measured` |
| Liste durch alle Kalibrierfelder ersetzt | `[measured1]`, `…travels…` |
| Grundlauf | 3 bestanden |

Die Tests prüfen den Vertrag: Ohne `measured` und ohne Startwert gilt jeder eingetragene Wert
als gemessen, die Liste reist durch Speichern, Öffnen auf dem zweiten Rechner und erneutes
Speichern. Mit `"elephant_foot" in table` sichert der Test zu, dass die erwartete Menge nicht
leer ist.

## Rest des Fix-Diffs

Die Kürzung von `.claude/rules/dateiformat.md` verschiebt Wissen, sie löscht keins:
`PartPlate.cpp` und RM-228 stehen in `konzepte/begruendungen/regel-dateiformat.md`, RM-589
ist dort nachgetragen, und `regel-druckrat.md` gibt es. Die Datei hat 30 680 Byte, das Budget
liegt bei 30 × 1024 = 30 720. Es bleiben **40 Byte**; nach dem nächsten Merge von welle3
also gleich `test_directory_docs.py` fahren. Der Wächter `COPY_OPS` prüft Register und Flag
(`test_the_copies_the_foot_follows_hand_their_input_on`).

## Tore

| Lauf | Ergebnis |
|---|---|
| `ruff check --no-cache .` (Kopie) | All checks passed, EXIT=0 |
| `ruff format --no-cache --check .` (Kopie) | 1206 Dateien, EXIT=0 |
| `mypy` (Kopie, Cache im Scratch) | 374 Dateien, keine Fehler, EXIT=0 |
| `test_text_length.py`, `test_directory_docs.py`, `test_advise.py`, `test_profiles.py` ohne Fenster, `-n 4` (Kopie) | 242 bestanden, 3 übersprungen, 1 rot, EXIT=1 |
| `test_directory_docs.py` im Worktree (ohne Cache, ohne Bytecode) | 13 bestanden, 3 übersprungen, EXIT=0, `git status` danach leer |

Der eine rote Test ist `test_memories_stay_out_of_the_repository`. Er ist ein Artefakt der
Kopie: Ein `git archive` hat kein Repository, also scheitert `git ls-files`. Im Worktree ist
er grün, und das Budget von `dateiformat.md` hält. Damit bestehen `test_text_length.py`,
`test_advise.py` und `test_profiles.py` vollständig.

Nicht gelaufen: volles Tor, CI, Fenstertests, Slicer (Auftrag).
