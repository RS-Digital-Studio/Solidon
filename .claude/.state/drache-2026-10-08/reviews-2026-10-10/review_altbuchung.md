# Review rvalt — `fix/altbuchung-rueckfrage` (`a705e1077`, `3d9b32e54`)

Prüfer rvalt (solidon3d-review), 11.10.2026 05:57–06:25. Nur gelesen und gemessen; im Worktree
`F:\sl-altbuchung` nichts geändert (`git status` nach den Läufen leer). Gegenstand: Rückfrage für
Buchungen aus 0.5 ohne Abdrucktreffer (`ui._same_amounts`), Texte, Test mit 0.5.3-Daten, Regel,
Archiv, Changelog mit G1.

**Probemerge** ohne Ref und ohne Worktree: `git merge-tree --write-tree origin/welle4 3d9b32e54`
(welle4 = `b3505824d`) → Baum `d502dbb7f`, konfliktfrei, Unterschied zu welle4 genau die 18
Dateien des Zweigs. Abzüge per `git archive` unter `F:\tmp-agenten\rvalt\`: `merge` (Probemerge),
`w4` (welle4 ohne Fix), `k053` (v0.5.3), `vorE` (`a72079433`, RM-706 ohne E). Sonden und
Ausgaben im Scratch `…\78c2d72e-…\scratchpad\rvalt\`. Alle Läufe gepinnt (`FFFFF0FF`), TEMP und
`--basetemp` unter `F:\tmp-agenten\rvalt`; `app.__file__` je Lauf geprüft.

## Urteil

**Nicht in dieser Form.** Der Fix tut, was er für Buchungen aus 0.5 verspricht (Test echt rot/grün,
Beispielsonde 2/11/0 nachgestellt), aber er gilt für **jede** frühere Buchung des Projekts, auch für
Buchungen aus 0.6.0: *Ohne Rückfrage buchen* hält jetzt bei jeder geänderten Variante mit gleicher
Menge an, wo welle4 buchte (M1, neu durch den Zweig, im Changelog nicht genannt). Daneben bleibt ein
zweiter Abzug in sechs Ausgabewegen, die vor E und in 0.5.3 keinen hatten (M2, nicht vom Zweig
verursacht, in welle4 genauso).

**Kann landen nach M1.** Entweder (a) Code: die Rückfrage nur für Buchungen, die vor RM-706 entstanden
sein können — dann Nachprüfung mit den drei Sonden unten; oder (b) ohne weitere Prüfung: Changelog
und Regel sagen, dass die Rückfrage für jede frühere Buchung des Projekts mit gleichen Spulen und
Mengen gilt, auch im Modus *Ohne Rückfrage buchen*; M2 als neuer Punkt ins Register. L1–L3 sind ohne
weitere Prüfung behebbar.

## Läufe

| Lauf | Ort | Ergebnis | Datei |
|---|---|---|---|
| ohne Fenster, `-n 4`: alle 14 `test_filament*`, Pflichtliste (shared_constants, language_rules, registry_consistency, toolchain, finding_ways, finding_actions, hard_rules, errors, core_isolation, interface_limits, value_labels), translations, wording, directory_docs, roadmap, changelog, changelog_website, text_length, changes_view, updates, corpus, orphans, action_effects, print_settings_ui, ui_export, error_plain_text | Probemerge | 4257 passed, 8 skipped, 5 failed, Exit 1 — die 5 brauchen Git (`git ls-files`/`ls-tree`/`rev-parse` im Archivabzug ohne `.git`) | `lauf1.txt` |
| die 5 Git-Fälle (3× toolchain, `test_memories_stay_out_of_the_repository`, `test_every_corpus_file_has_its_line_in_the_readme`) | Worktree, ohne Cache und Bytecode | 5 passed, Exit 0 | `git5.txt` |
| Fenster je Datei: `test_filament_usage_ui` / `test_filament_workflow` / `test_filament_inventory_ui` | Probemerge | 45 / 39 / 70 passed (1 deselected), je Exit 0 | `fenster_*.txt` |
| `ruff check`, `ruff format --check`, `mypy` | Probemerge | Exit 0 / 0 (1231 Dateien) / 0 (378 Dateien) | `ruff.txt`, `format.txt`, `mypy.txt` |
| Rotprobe: neuer Test + Daten an welle4 ohne Fix | `w4` | `test_a_053_…` rot (`[] == ['rm706-altbuchung-053']`), beide Gegentests grün, Exit 1 | `rot.txt` |
| Beispielsonde (`sonde_altbuchung.py` der anderen Sitzung, byte-gleich kopiert; Schlüssel neu aus eigenem `v0.5.3`-Abzug, gleich denen der anderen Sitzung) | `w4` / Probemerge | vorher 2 erkannt, 0 zur Prüfung, 11 NICHT; nachher 2 erkannt, 11 zur Prüfung, 0 NICHT | `beisp_vorher.out`, `beisp_nachher.out` |

Die `affected_tests`-Auswahl meldet „426 von 456 — das ist die Suite“ (Kataloge); daher die
gezielte Auswahl oben samt Pflichtliste und `test_text_length`.

## Funde

### M1 (mittel, neu durch den Zweig) — Die Rückfrage trifft auch Buchungen aus 0.6.0: *Ohne Rückfrage buchen* hält bei jeder geänderten Variante gleicher Menge an

- **Wo:** `app/ui/filament_usage.py:156-160` — `_legacy_bookings` wendet `_same_amounts` auf jede
  Buchung des Lagers an, nicht nur auf solche, die vor RM-706 entstanden sein können.
- **Beleg** (`sonde_variante.py`, leeres Lager, nur 0.6.0): *Halter konstruieren* ausgegeben und
  gebucht, dann eine Bohrung um 2 mm verschoben (Abdruck `b0aaa90c…` → `61569b48…`, Schätzung
  beide 9,812 g). Probemerge: Schätzung und G-Code 23,45 g je „Rückfrage (Frühere
  Filamentbuchung prüfen)“, Bestand unverändert. welle4: beide Male gebucht. Ebenso `V12` der
  Lückensonde (neue Platte, eigener Abdruck, gleiche Menge → Rückfrage).
- **Warum:** Seit RM-706 benennt der Abdruck den Druck (`verbrauch.md`, Kopf); ein anderer Abdruck
  aus 0.6.0 ist ein anderer Druck, die Frage hat dort keine Mehrdeutigkeit zu klären. Gleiche
  Menge haben aber gerade die häufigen Iterationen — Temperatur, Geschwindigkeit, Lüfter (G-Code-
  Gramm gleich), verschobene oder umbenannte Merkmale (Volumen gleich) — auch Fehldruck,
  Rücknahme und neuer Lauf mit geänderter Temperatur: `_same_amounts` fragt `reversed_at` nicht ab,
  die zurückgenommene Buchung der Vorgängervariante wird Kandidat (für 0.5.3 gemessen: `V6`;
  derselbe Abdruck nach Rücknahme bucht weiter selbst). Der Kunde hat den Modus
  gewählt, um nicht gefragt zu werden; eine Ablehnung gilt nur bis zum Neustart (`_declined`),
  danach fragt dieselbe Ausgabe wieder. Der Changelog (`changelog/de.md:148`) und die Regel
  (`verbrauch.md:73-77`) sprechen nur von Buchungen aus 0.5. Nie still — die Gegenrichtung der
  Aufgabe hält: Ein neuer Druck wird nie still als alt behandelt, immer mit Rückfrage.
- **Fix (Entscheidung Koordinator):** (a) die Rückfrage auf Buchungen beschränken, die älter als
  RM-706 sein können. `filaments.book` verlangt vom Abdruck nur einen nichtleeren Text
  (`filaments.py:1391-1392`), und RM-706 ist nicht ausgeliefert: Ein Kennzeichen in Abdrücken ab
  RM-706 (etwa ein Präfix in `prepare`) trennt sie ohne Formatschritt; es verschiebt die in Tests
  festgehaltenen Abdrücke (`PINNED_BOOKING` u. a.). Dann gilt `_same_amounts` nur für Buchungen
  ohne Kennzeichen.
  Gegenprobe: `sonde_variante.py` bucht wieder selbst, `sonde_altbuchung.py` bleibt 2/11/0.
  (b) Wer die Frage für alle Buchungen will: Changelog-Punkt und Regel sagen es so.

### M2 (mittel, vorbestehend in welle4) — Sechs Ausgabewege ziehen eine Buchung aus 0.5 weiter ein zweites Mal ab

- **Wo:** `app/ui/filament_usage.py:174-187` — die Bedingungen von `_same_amounts`.
- **Beleg** (`sonde_luecken.py`: die eingecheckte 0.5.3-Buchung, 23,45 g G-Code, dann die Ausgabe
  in Varianten; „zusätzlich“ = Abzug über die Buchung aus 0.5.3 hinaus für denselben Druck):

  | Variante | v0.5.3 | vor E (`a72079433`) | welle4 | Probemerge |
  |---|---|---|---|---|
  | V1 gleiche Ausgabe (G-Code 23,45 g, Spule A) | Treffer, 0 | Treffer, 0 | +23,45 | Rückfrage, 0 |
  | V2 nach G-Code-Buchung als 3MF exportiert (Schätzung 9,81 g) | Treffer, 0 (G-Code bleibt) | Treffer, 0 | +9,81 | **+9,81** |
  | V3 dieselbe Ausgabe, andere Spule gebunden | nichts gebucht | nichts | +23,45 | **+23,45** |
  | V4 Projekt umbenannt / unter neuem Namen gespeichert | Treffer, 0 | Treffer, 0 | +23,45 | **+23,45** |
  | V5 G-Code nach Slicer-Update 23,40 / 23,50 g | Halt (Fehlermeldung), 0 | Halt, 0 | +23,4/+23,5 | **+23,4/+23,5** (23,401/23,499: Rückfrage) |
  | V7 in 0.5.3 auf zwei Spulen aufgeteilt | nichts | nichts | +23,45 | **+23,45** |
  | V10 in 0.5.3 Schätzung gebucht (9,81 g), jetzt G-Code | Buchung auf 23,45 g korrigiert | korrigiert | +23,45 | **+23,45** (zusammen 33,26 g) |
  | V11 in 0.5.3 von Hand 25,0 g, jetzt G-Code | nichts | nichts | +23,45 | **+23,45** |
  | V6 zurückgenommen, V8 Menge unbekannt, V9 ungebunden | gebucht / nichts / nichts | ebenso | gebucht / nichts / nichts | Rückfrage / nichts / Rückfrage — kein zweiter Abzug |

  V2 und V10 sind die Wege, die `_auto_book` eigens für denselben Druck führt (G-Code bleibt,
  Schätzung wird zum G-Code); die Schätzung ist an allen Ständen gleich (9,812162810505225 g, Δ 0),
  und `filament_key` aus 0.5.3 gleich dem heutigen. Mehrfarbe und mehrere Platten: kein eigener
  Fehler (Beispielsonde: `schild-zweifarbig` mit drei Positionen, `dose-mit-deckel` mit zwei
  Platten je zur Prüfung).
- **Warum:** derselbe Kundenschaden wie M1 des Integrationsreviews, im Modus *Ohne Rückfrage
  buchen* still; im Modus *Nachfragen* (Vorgabe) fehlt dem Dialog in diesen Fällen jeder Hinweis
  auf die frühere Buchung. Regel 21: Eine Buchung desselben Projekts und Druckfilaments, deren Menge
  aus einer anderen Quelle stammt, ist mehrdeutig und wird geraten.
- **Fix:** zusammen mit M1(a), dann ohne Reibung für 0.6.0: für Buchungen ohne Kennzeichen Mengen
  nur bei gleicher Quelle vergleichen (G-Code mit G-Code, Schätzung mit Schätzung); eine Position
  von Hand, eine aufgeteilte Position und eine andere Spule machen einen Kandidaten statt eines
  stillen Abzugs. Der umbenannte Projektname (V4) bleibt Grenze — die Buchung kennt nur den Namen —
  und wird im Archiv genannt. Ohne M1(a) als neuer Punkt ins Register.

### L1 (leicht) — Die neuen Tests halten nur zwei der Bedingungen fest

- **Wo:** `tests/test_filament_usage_stored_inputs.py:868-901`.
- **Beleg** (`mutanten.py` am Probemerge-Abzug, je Mutation die sieben `test_filament_usage*`-Dateien;
  Kontrolle „`_same_amounts` nie“ rot): grün blieben 8 von 8 — Spulenbedingung weg (`:184-185`),
  aufgeteilte Positionen zählen (`:181`), Positionszahl egal (`:176`), unbekannte Menge nicht
  abgefangen (`:181`; dann `abs(float - None)` → `TypeError` im Lagerarbeiter), Rücknahmetext
  vertauscht (`:198`), Toleranz 0,4 g, leerer Projektname zählt, zurückgenommene Buchung zählt
  nicht. Die Zusicherung `"denselben Spulen und Mengen" in …` (`:882`) passt auf beide neuen Texte
  — `tests.md`, „An der Aussage vorbei“.
- **Fix:** je Bedingung ein Fall (andere Spule, aufgeteilt, Positionszahl, unbekannte Menge,
  Grenze 0,049/0,05 g, zurückgenommen mit ganzem Satz), Vergleich mit dem ganzen Satz über
  `tr(...)`.

### L2 (leicht) — Unterlagen sagen etwas anderes, als der Code tut

- „eine Menge, die das Lager gleich zeigt“ (`app/ui/filament_usage.py:138-139`, `:172`;
  `verbrauch.md:75`; `ROADMAP-ARCHIV.md:48003`): Der Code prüft |Δ| < 0,05 g. 23,45 und 23,40
  zeigt das Lager beide als „23,4“ — kein Kandidat; 23,45 und 23,499 zeigt es als „23,4“ und
  „23,5“ — Kandidat (`filament_inventory.py:978`, `{grams:.1f}`). Fix: „höchstens 0,05 g
  auseinander (halbe Anzeigestufe)“.
- `ROADMAP-ARCHIV.md:47999-48000`: „Paket E … der Vorabdruck traf danach nur noch 2 von 13“ — nach E
  waren es 3 von 13 (Integrationsreview, Tabelle), 2 von 13 erst mit F (*Figur formen*). Fix: beide
  Zahlen mit ihrem Paket.
- `verbrauch.md:72`: „0.5.0 bleibt unerkannt“ steht direkt über dem neuen Punkt, der auch Buchungen
  aus 0.5.0 anbietet (0.5.0 schreibt `project_name` und `filament_key` mit demselben `_line_key`).
  Fix: „über einen Altabdruck“ ergänzen.
- `tests/data/README.md:226` und Test `:824`: „nach einem Slicerlauf (23,45 g aus dem G-Code)“ —
  `schreibe_altbuchung.py` lief keinen Slicer, es buchte 23,45 g mit Quelle `gcode`. Das Projekt
  trägt keine Spulenbindung (`print_settings: null`), der Test setzt die Spule an der Zeile (`:864`);
  so wie eingecheckt würde *Ohne Rückfrage buchen* das Projekt gar nicht buchen. Fix: Herkunft so
  nennen, wie sie ist, oder die Bindung mit 0.5.3 schreiben (`with_spool`, speichern).

### L3 (leicht) — Changelog FR

- `changelog/fr.md:124`: „… avec le même projet, les mêmes bobines et quantités comme antérieure et
  demande …“ — „comme antérieure“ hängt ohne Bezugswort. Fix: „comme déjà enregistrée“.

## Geprüft, ohne Befund

- **Prämisse des Tests:** am Stand vor E trifft derselbe Aufbau die 0.5.3-Buchung über den
  Vorabdruck (`b6af97b1…` unter `former_fingerprints`), am Probemerge nicht — die Ursache ist E. Der
  Abdruck nach RM-706 (`b0aaa90c…`) ist vor und nach E gleich.
- **Gegenrichtung:** Kein Weg behandelt einen Druck still als alt; jeder Kandidat endet in der
  Rückfrage (Automodus: `ValidationError` mit Handlungsvorschlag „Buchung prüfen …“, Regel 17;
  Dialog: Hinweis und „Weiteren Druck buchen“, „Nicht buchen“ bleibt). Die Verdrahtung im Dialog
  (`:542`, mit `self.request`) läuft im bestehenden Test
  `test_dialog_warns_and_offers_explicit_new_print_without_old_selection`.
- **Texte:** zwei neue Quelltexte über `tr()`, in allen fünf Katalogen, Wortwahl wie die
  vorhandenen Brim/Raft-Sätze (EN „consumption record“, ES/PT „registro/registo … anulado“, FR
  „consommation … enregistrée puis annulée“, IT „registrazione … annullata“, Spule je „bobina/
  bobine/spool“ wie im Bestand); `test_text_length`, `test_translations`, `test_wording` grün.
- **Changelog:** sechs Sprachen, je 168 Punkte, gleiche Folge; Sammelpunkt (G1) mit den sieben
  Feldnamen genau wie in den Katalogen, der RM-586-Punkt in allen sechs gestrichen; die
  weggefallenen Nebensätze machen keine falsche Aussage. Der Altbuchungspunkt ist als Eigenschaft
  gesagt (Ursache E in keinem Tag) und stimmt für 0.5.0–0.5.3 unter seinen Bedingungen — bis auf
  M1, wo er zu eng ist. `test_changelog` grün (≤ `MAX_FIELD_LENGTH`).
- **Handwerk:** `_legacy_bookings` läuft im Lagerarbeiter, nicht im Qt-Hauptthread; kein stiller
  `except`; keine zweite Stelle mit derselben Auskunft.

## Hinweis (vorbestehend, kein Fund dieses Zweigs)

Ein Kandidat lässt sich nicht als „derselbe Druck“ übernehmen: Der Dialog bietet nur „Weiteren Druck
buchen“ oder „Nicht buchen“, und die Ablehnung gilt bis zum Neustart. Im Automodus hält deshalb jede
weitere Ausgabe desselben Projekts erneut an, bis einmal gebucht wird — wie bisher für 0.5.1, durch
den Zweig jetzt für die meisten Buchungen aus 0.5.

## Sonden für die Nachprüfung

`sonde_luecken.py` (Varianten V1–V12; Aufruf `<wurzel> <053|neu> <daten> <arbeitsordner>
<mengen.json>`), `sonde_variante.py` (Gegenrichtung 0.6.0), `sonde_altbuchung.py` (Beispiele,
Kopie), `mutanten.py` (Testschärfe) — alle im Scratch `rvalt\`, je mit `*.sh` gepinnt.

---

## Nachprüfung Stufe 2 — `2e549dc94` (`9399f5bab` + Merge welle4 `86a8fb3fa`)

11.10.2026 06:42–06:55. Stufe 1 (Fix b, L1–L3) liegt als `86a8fb3fa` auf welle4; `origin/welle4`
steht dort, die Zweigspitze ist damit der Probestand. Abzüge per `git archive`: `s2`
(`2e549dc94`), `s2m` (Kopie für Mutationen), `s1` (`86a8fb3fa`). Worktree nur gelesen
(`git status` leer, HEAD `2e549dc94`).

### Urteil

**Kann landen.** M1 und M2 sind behoben, wie gefordert gemessen; kein schwerer oder mittlerer Fund.
Zwei leichte Restpunkte (N1 Testlücke, N2 Kundensicht) brauchen keine weitere Prüfung; N2 ist eine
Abwägung für den Koordinator und hält die Landung nicht auf.

### Läufe am Stand `2e549dc94`

| Lauf | Ergebnis | Datei |
|---|---|---|
| ohne Fenster, `-n 4`, dieselbe Auswahl wie oben (alle `test_filament*`, Pflichtliste mit `test_value_labels`, `test_text_length`, `test_translations`, `test_wording`, `test_changelog`, `test_roadmap`, `test_directory_docs` u. a.) | 4274 passed, 8 skipped, 5 failed, Exit 1 — die 5 Git-Fälle (Archiv ohne `.git`) | `s2_lauf.txt` |
| die 5 Git-Fälle im Worktree (`2e549dc94`, ohne Cache und Bytecode) | 5 passed, Exit 0 | `s2_git5.txt` |
| Fenster je Datei: `test_filament_usage_ui` / `test_filament_workflow` / `test_filament_inventory_ui` | 45 / 39 / 70 passed (1 deselected), je Exit 0 | `s2_fenster_*.txt` |
| `ruff check`, `ruff format --check`, `mypy` | Exit 0 / 0 (1231 Dateien) / 0 (378 Dateien) | `s2_ruff.txt`, `s2_format.txt`, `s2_mypy.txt` |

### (1) Sonden

- **Lückensonde** (`s2_luecken.out`, dieselbe 0.5.3-Buchung, 23,45 g): V1, V2, V3, V5 (23,401 /
  23,499 / 23,40 / 23,50 / 23,5000001 g), V6, V7, V8, V9, V10, V11, V12 je „Rückfrage (Frühere
  Filamentbuchung prüfen)“, kein Abzug. Nur **V4** (Projekt umbenannt) bucht 23,45 g ein zweites
  Mal — die im Archiv genannte Grenze. V8 (Menge unbekannt) und V9 (ungebunden) fragen jetzt, wo
  0.5.3 nichts tat; das ist die sichere Richtung.
- **Variantensonde** (`s2_variante.out`, nur 0.6.0, Bohrung 2 mm verschoben, Abdruck
  `si1-b0aaa90c…` → `si1-61569b48…`, Menge 9,812 g beide): Schätzung und G-Code buchen die geänderte
  Variante ohne Rückfrage, Bestand 480,38 g bzw. 453,1 g — wie welle4 vor dem Fix.
- **Beispielsonde** (`s2_beisp.out`, Schlüssel aus dem eigenen `v0.5.3`-Abzug): 2 erkannt,
  11 zur Prüfung, 0 ohne Treffer.

### (2) Abdrücke ohne Zeichen aus 0.6.0, Zeichen an einer Buchung aus 0.5

- **Kein Buchungsweg erzeugt in 0.6.0 einen Abdruck ohne Zeichen.** `prepare` setzt das Zeichen,
  sobald Eingänge da sind (`app/core/filament_usage.py:996`); ohne Eingänge rechnet nur
  `_StockWorker` (`print_settings_dialog.py:2069`, Bestandsanzeige, bucht nicht). Der Export gibt
  immer `StoredInputs.snapshot` mit (`main_window.py:10226`), der einzige `_PlateJob` ebenso
  (`print_settings_dialog.py:9201-9221`; Slicen, Übergabe je Platte und als ein Projekt lesen
  `job.inputs`). Neue Vorgänge entstehen nur in `UsageDialog._book` und `_auto_book` über
  `_booking_fingerprint` — neu mit dem Abdruck der Anfrage (Zeichen), ein bestehender Vorgang mit
  seinem eigenen. Kein Import oder Zusammenführen von Lagerdateien (`restore_backup` stellt die
  Datei unverändert wieder her, `_migrate_list` kennt keine Buchungen), kein Buchungsweg in CLI
  oder Agent.
- **Nachbuchen:** `filaments.book` lehnt für eine Vorgangskennung einen anderen Abdruck als
  Konflikt ab (`filaments.py:1418-1420`). Eine Buchung aus 0.5, die ihr Vorabdruck noch trifft
  (2 von 13), bleibt beim Nachbuchen ohne Zeichen — sie stammt aus 0.5, also richtig; ein Vorgang
  aus 0.6.0 behält sein Zeichen.
- **Umgekehrt** kann eine Buchung aus 0.5 das Zeichen nicht tragen: 0.5 schrieb nur
  32-stellige Hex-Abdrücke, und der Abdruck eines Vorgangs ist unveränderlich (oben).
- Der Abdruck erscheint nirgends in der Oberfläche; das Zeichen bleibt unsichtbar.

### (3) Gespeicherte Abdrücke von Entwicklungsständen, `PINNED_BOOKING`

- Die Bildung selbst ist unverändert: `PINNED_BOOKING` ist `si1-` + dasselbe `3aa49b71…` wie vorher,
  der Vorabdruck bleibt ohne Zeichen und gleich (`1a29d39b…` für *Halter konstruieren* an welle4 und
  Stufe 2). Mutation „`prepare` ohne Zeichen“ macht zwei Tests rot (unten).
- RM-706 (`bee9d1b74`) steht in keinem Tag und nicht auf main (`git tag --contains` leer,
  `merge-base --is-ancestor` nein). Buchungen ohne Zeichen aus RM-706 gibt es also nur in Lagern
  von Entwicklungsständen (welle4 und Zweige). Dort gilt eine solche Buchung jetzt als Buchung aus
  0.5: kein Abdrucktreffer mehr, Rückfrage mit dem Satz „… aus Solidon 0.5 …“, nie ein stiller
  zweiter Abzug. Für Kunden ohne Wirkung; wer am eigenen Lager prüft, sieht die Rückfrage.

### (4) Tests, Texte, Changelog, Regel, Archiv

- **Mutationen** (`mutanten_s2.py` an `s2m`, je die sieben `test_filament_usage*`-Dateien;
  Kontrolle „`_earlier_print` nie“ rot, Originale zurück): rot 8 von 9 — Zeichen nicht abgefragt,
  `prepare` ohne Zeichen, Projekt egal, leerer Projektname zählt, Filamente als Teilmenge (`<=`),
  ein gemeinsames Filament genügt, zurückgenommene Buchung zählt nicht, Rücknahmetext vertauscht.
  Grün bleibt nur „Filamente als Obermenge (`>=`)“ → N1.
- **Texte:** zwei neue Quelltexte über `tr()` („… eine (zurückgenommene) Buchung aus Solidon 0.5
  mit denselben Filamenten …“), alle fünf Kataloge, Wortwahl wie der Bestand (record/registro/
  registo/registrazione/consommation); die beiden alten Schlüssel sind aus allen Katalogen entfernt.
  `test_text_length`, `test_translations`, `test_wording` grün.
- **Changelog:** sechs Sprachen, je 169 Punkte, Altbuchungspunkt 155–173 Zeichen, als Eigenschaft
  gesagt; er stimmt mit dem Code überein (Buchung aus 0.5, dasselbe Projekt, dieselben Filamente,
  Rückfrage). Der FR-Satz aus L3 ist neu geschrieben und trägt sein Bezugswort.
- **Regel** (`verbrauch.md`, Punkt „Abdrücke ab 0.6.0 tragen ein Zeichen“) und **Archiv**
  (Nachtrag RM-706: 3 von 13 nach E, 2 von 13 mit F, Wege aus M2, Zeichen, Grenze V4, Herkunft der
  Testdaten ohne Slicerlauf) sagen, was der Code tut.

### N1 (leicht) — Eine Ausgabe mit einem Filament mehr als die Buchung aus 0.5 hält kein Test fest

- **Wo:** `tests/test_filament_usage_stored_inputs.py`, `NOT_EARLIER_CASES`; Code
  `app/ui/filament_usage.py:179-181` (Mengengleichheit der Filamente).
- **Beleg:** Mutation `==` → `>=` bleibt grün (238 passed). „ein Filament mehr“ prüft nur die
  Buchung mit einem Filament mehr, nicht die Ausgabe.
- **Fix:** ein Fall „Ausgabe mit einem Filament mehr“ (`((_SLOT…), (_OTHER_SLOT…))` gegen
  `_SLICED`), Erwartung kein Kandidat.

### N2 (leicht, Kundensicht, Entscheidung Koordinator) — Bei einem Projekt mit Buchung aus 0.5 fragt jede neue Variante, auch nachdem der Kunde schon gebucht hat

- **Beleg** (`sonde_iteration.py`, `s2_iteration.out`): Lager mit der 0.5.3-Buchung von *Halter
  konstruieren*, vier Ausgaben mit je verschobener Bohrung, jede Rückfrage mit „Weiteren Druck
  buchen“ beantwortet: **4 von 4 Ausgaben halten an**; dieselbe Ausgabe ein zweites Mal fragt nicht.
  Grund: Die Buchung aus 0.5 bleibt Kandidat, solange es sie gibt — auch zurückgenommen —, und jede
  geänderte Variante hat einen neuen Abdruck ohne eigene Buchung.
- **Was der Kunde sieht:** Im Modus *Ohne Rückfrage buchen* hält jede Änderung an einem Projekt, das
  er unter 0.5 gebucht hatte, einmal an, ohne Ende; im Modus *Nachfragen* trägt der Dialog dort
  immer den Hinweis und „Weiteren Druck buchen“. Kein falscher Bestand. Aus dem Zustand führt nur
  Buchen oder Ablehnen bis zum Neustart; ein Umbenennen des Projekts beendet es (V4).
- **Fix, falls gewollt:** Eine Buchung aus 0.5 ist kein Kandidat mehr, sobald es für dasselbe
  Projekt und dieselben Filamente eine Buchung mit Zeichen gibt, die nach ihr angelegt wurde
  (`created_at`) — der Kunde hat dieses Projekt dann unter 0.6.0 schon beantwortet. Restfall: Wer
  danach den alten Stand aus 0.5 unverändert noch einmal ausgibt, ohne ihn zu drucken, bekommt
  einen stillen Abzug. Ohne Fix: so lassen und in der Regel einen Satz dazu.

### Sonden Stufe 2

`s2_sonden.sh` (Lücken-, Varianten-, Beispielsonde), `sonde_iteration.py` mit `iteration.sh`,
`mutanten_s2.py` mit `mut_s2.sh`, `s2_lauf.sh`, `s2_git5.sh` — im Scratch `rvalt\`.
