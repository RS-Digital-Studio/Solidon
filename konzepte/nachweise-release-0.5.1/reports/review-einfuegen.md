# Review: Zweig `einfuegen-freier-platz` — ein weiteres Modell an eine freie Stelle

Geprüft: `origin/einfuegen-freier-platz`, Endcommit `cf1015de2`, Basis `cbef27715`,
drei Commits (`eea4565ea`, `746ec8ebd`, `cf1015de2`), 38 Dateien, +960/−111.
Merge-Ziel: `origin/main` auf `f22906b16` (140 Commits über der Basis).
Jede Zeile des Diffs gelesen, dazu die berührten Funktionen ganz, Karten
`app/core/{geom,ingest,scene}/CLAUDE.md`, Regeln `dateiformat.md`,
`operationen.md`, `oberflaeche.md`, `tests.md`, `zwillinge.md`, Bauplan §17.1,
§25, §29, der Sitzungsbericht `output/review/einfuegen-2026-09-28/bericht.md`.

Arbeitsbäume (eigene, am Ende entfernt): `wt-reveinf` (Zweig), `wt-reveinf-merge`
(Probe-Merge mit main, nicht committet), `wt-reveinf-basis` (Basis, für die
Zuordnung fremder Befunde). Alle Läufe gebunden (`/affinity FFFFF0FF`), Ergebnisse
in `F:\3D Druck.review-051\laeufe\rev-einf-*.txt`, Sonden in
`F:\3D Druck.review-051\sonden\einfuegen\`.

## Urteil

**Mergebar: nein, nicht in dieser Form.** Ein Fund blockiert (F1): Jedes weitere
Modell hängt jetzt an allem, was vor ihm im Stapel steht, und am Drucker. Wird
davor etwas gelöscht oder geändert oder der Drucker gewechselt, rückt das Modell
an eine andere Stelle, und Schritte danach, die eine Position tragen (Bohrung aus
einem Klick), treffen nicht mehr oder sitzen still daneben. Das braucht vor dem
Merge Roberts Entscheidung. Alles andere ist beim Merge (zwei triviale
Konflikte) oder vor dem Tag lösbar; Tests, Typen und Format sind in Ordnung.

## Funde nach Schwere

### Blockiert den Merge

**F1 — Ein weiteres Modell wandert mit dem, was davor steht; Positionen danach verlieren ihr Ziel**

- Stellen: `app/core/ingest/ops.py:412` und `:595–628` (`_to_a_free_spot`),
  `app/core/ingest/step_ops.py:474–481`, `app/core/geom/ops.py:585–597`,
  `app/core/geom/prepare.py:2763–2819` (`first_free_spot`), Schlüssel
  `app/core/scene/evaluate.py:4691`.
- Beleg (Sonden gegen den Zweig, jeweils mit Gegenprobe `free_spot` aus):
  - **Erstes Modell löschen** (`p4_downstream_drill.py`, `laeufe/rev-einf-p4.txt`):
    B liegt nach dem Import bei x −123…−83, y 93…123; gebohrt (Ø 6, Volumen
    23 941,91 → 23 339,81 mm³). Ladeschritt von A gelöscht → B springt nach
    x −20…20, y −15…15, das Volumen ist wieder 23 941,91: die Bohrung trifft nichts
    mehr (`boolean.without_effect` „Der Schnitt hat nichts abgetragen …“,
    `bore.over_the_edge`). Ohne `free_spot` bleiben B und die Bohrung.
  - **Ein Maß davor ändern** (`p5_silent_shift.py`, `rev-einf-p5.txt`): A, B, B in X
    um 10 % skaliert, dann C (legt sich rechts neben B), Bohrung in C. Faktor im
    Verlauf auf 20 % geändert → C rückt von x −76…−56 nach −74…−54, die Bohrung
    bleibt am alten Weltort und sitzt **2 mm neben der gebohrten Stelle am Teil**
    (Schwerpunktversatz 0,1789 → 0,2504), Volumen gleich, **kein Befund**. Ohne
    `free_spot` unverändert.
  - **Drucker wechseln** (`p10_printer_switch.py`, `rev-einf-p10.txt`): Dasselbe
    Dokument mit Creality K1 (220er Bett) statt Centauri Carbon 2 (256er) → B rückt
    um 18 mm in x und y (x −105…−65, y 75…105), die Bohrung trifft nicht mehr
    (`boolean.without_effect`). Liegt die Bohrung weiter innen, sitzt sie still
    18 mm daneben. Ohne `free_spot` unverändert.
- Warum es zählt: Vor dem Zweig war ein weiteres Modell stabil (Dateikoordinaten),
  das erste hängt nur an sich selbst (Mitte = Ursprung). Der Zweig streicht dazu
  bewusst den Grundsatz aus dem Docstring von `ingest.plan.import_plan` —
  „Sonst hinge das Ergebnis daran, was sonst noch in der Szene steht“ (Basis,
  `plan.py`) — und ersetzt ihn durch „rechnet die Operation aus der Szene vor
  ihr“. Reproduzierbar (§15.1) bleibt es, stabil nicht mehr. P5 ändert Geometrie
  ohne ein Wort (Regel 21: nie stillschweigend). Die Klasse ist im Bauplan bekannt:
  §29 „Ein Zug am Griff meint einen Platz, kein Maß … Ordnet ein früherer Schritt
  … neu an, startet der Körper woanders“ — dort gibt es die Rückholung
  (`back_onto_bed`), für frei gelegte Modelle nichts. Die Löschnachfrage (Regel 19,
  Ausnahme) nennt B nicht als betroffen (`History.removal_closure` fragt nur
  Ein- und Ausgänge), obwohl B wandert. Druckerwechsel ist ein Alltagsschritt im
  Druckdialog.
- Fix (Empfehlung): **einmal legen, dann festhalten.** Die Op rechnet die freie
  Stelle beim ersten Lauf wie jetzt und gibt sie als Antwort zurück
  (`OpResult.answered`, derselbe Weg wie die Einheitenfrage §15.7:
  `History.record_answers` schreibt ohne eigene Transaktion, `_key_after_answers`
  legt das Ergebnis gleich unter den neuen Schlüssel). Mit der festgehaltenen
  Stelle (z. B. ein Parameter `spot` mit Versatz und Platte) liest der Schritt die
  Szene nicht mehr; `reads_scene` gilt dann nur, solange `free_spot` an und
  `spot` leer ist. Danach bleibt das Modell liegen, wenn davor etwas geht, sich
  ändert oder der Drucker wechselt — wie in jedem Slicer —, und F7 entfällt
  mit. Liegt Format 38 vor dem Tag, deckt es den neuen Parameter mit ab. Die
  Alternative (Stelle im Plan aus `Session.last_result` rechnen) greift weiter in
  Plan, Kommandozeile und Weg 3 ein. Beides ändert den freigegebenen Satz in §17.1
  („die freie Stelle rechnet die Op aus der Szene vor ihr“) — daher Entscheidung
  Robert: festhalten vor dem Merge, oder das Wandern für 0.5.1 bewusst annehmen
  und als Registerpunkt führen.

### Beim Merge

**F2 — Zwei Konflikte mit main, beide trivial; im Probe-Merge grün**

- `.claude/rules/oberflaeche.md:58` (Parameterzahl): Zweig 1340, main 1343.
  Richtig ist **1346** — im Probe-Merge aus dem Register gezählt (142 Operationen,
  1346 Parameter); `test_the_rule_files_count_the_operations_parameters_and_tools_they_claim`
  prüft es.
- `app/i18n/locales/it.json:1864`: main hat die zwei Nachbarzeilen geändert
  („Die Platte ist fertig …“ mit Handbuchlink, „passaggio“), der Zweig fügt
  „Die Platten der Datei kommen hinter die vorhandenen, ab Platte {number}.“
  ein. Auflösung: beide Zeilen von main plus die neue Zeile des Zweigs.
- `app/core/geom/prepare_ops.py` läuft ohne Konflikt durch: main hat
  `ArrangeParams.spacing` nicht angefasst, das Ergebnis trägt
  `default=ARRANGE_SPACING`. `evaluate.py`, `types.py`, `loader.py` ebenfalls
  sauber; `moved_findings` von main führt jetzt auch `Finding.outline` mit, also
  wandert beim Legen an die freie Stelle auch der Rand einer geschlossenen
  Öffnung mit.
- Nachweis im eigenen Baum `wt-reveinf-merge` mit genau dieser Auflösung:
  Kern 21 Dateien 2931 passed, 4 skipped, 32 abgewählt, Exit 0
  (`rev-einf-merge-1`); zehn Fenstertests einzeln grün (`rev-einf-mui-01…10`);
  mypy 333 Dateien, ruff, format 1051 Dateien, alle Exit 0.

### Vor dem Tag

**F3 — `dateiformat.md` steht nach dem Merge 3 Byte unter der Grenze und trägt ein Datum**

- `.claude/rules/dateiformat.md:88–94`. Größen: Basis 27 443, Zweig 27 948,
  main 30 212, **Merge 30 717 von 30 720 Byte** (`RULE_LIMIT_KB = 30`,
  `tests/test_directory_docs.py:403/413`). Der Test bleibt grün, aber der nächste
  Satz irgendeiner Sitzung in dieser Regel macht das Tor rot.
- Der Absatz bringt mit „Robert 28.09.2026“ das erste Datum in diese Regel; die
  Unterlagenregel sagt, Datumsangaben gehören in Konzepte und Git
  (`CLAUDE.md`, Unterlagen-Pyramide).
- Fix: „(`free_spot`, Format 38, Entscheidung Robert)“ statt des Datums, und den
  Absatz auf den Kern kürzen (Lage im Ladeschritt, neue Lageschalter brauchen
  Vorgabe und Formatstufe). `operationen.md` beantwortet die Frage des Auftrags:
  **der Zweig ändert sie nicht** (Basis, Zweig, main und Merge je 30 716 Byte); der
  Satz dafür steht in `app/core/scene/CLAUDE.md`, Karte nach dem Merge 16 890 von
  25 600 Byte.

**F4 — Der Cache-Schlüssel von `fit_to_size.free_spot` hat keinen Wächter**

- `tests/test_cache.py:1929` parametriert nur `load` und `load_step`.
- Beleg (Mutation im eigenen Baum, danach zurückgestellt): `reads_scene=True` an
  `app/core/geom/ops.py:539` entfernt → `test_way_three.py`, `test_cache.py`,
  `test_transform.py`, `test_registry_consistency.py`: **1224 passed, Exit 0**
  (`rev-einf-mut-fit`). Ohne den Schalter käme ein erzeugtes Modell nach einer
  Änderung davor mit alter Lage aus dem Cache.
- Fix: den Test über alle Parameter mit `reads_scene` aus dem Register fahren und
  zusichern, dass die Menge mindestens `load.free_spot`, `load_step.free_spot`,
  `fit_to_size.free_spot` enthält; dazu ein Weg-3-Test mit `ResultCache`, in dem
  eine Änderung am ersten Modell die Lage des erzeugten verschiebt. (Entfällt zum
  Teil, wenn F1 festgehalten wird.)

**F5 — Bauplan- und Docstring-Wortlaut stimmen an drei Stellen nicht**

- `3d-agent-bauplan.md:1151–1152` „Ein Ladeschritt ohne `free_spot` behält die
  Lage seiner Datei“ — falsch für das erste Modell (`centre`, `place_on_bed`,
  kein `free_spot`, wird verschoben). §25 (`:1916–1917`) sagt es richtig: „ohne
  Lageentscheidung“. Fix: dieselbe Formulierung in §17.1 (Bauplan nur mit Ansage).
- `app/core/geom/prepare.py:2779–2781` „Eine leere Platte nimmt das Modell immer,
  und dort liegt es mittig“ — nicht für ein zu großes Modell: 300 × 300 mm kommt
  auf Platte 2 bei x −123…177, y −177…123 (`p7_no_bed_fits.py`, (a)), weil
  `_into_the_middle` nur Achsen zentriert, die passen.
- Sitzungsbericht, „Bewusst offen“ 4: „(zu hoch, zu groß) kommt auf eine neue
  leere Platte“ — ein 300 mm hohes Modell bleibt auf Platte 1 hinten links
  (`p7`, (b)); gemeldet wird es richtig (`arrange.out_of_build_volume`, z 44 mm).
  Nur der Satz ist falsch, das Verhalten ist vertretbar.

**F6 — Register und Changelog**

- Kein Registerpunkt in `ROADMAP.md` (Zweig und main: kein Treffer für „freie
  Stelle“/`free_spot`). Offen und dort zu führen: die Fenstertests des Zweigs
  gelten erst mit dem Release-Tor (Bericht, Punkt 6), F1 falls angenommen, F7 bis
  F15.
- Der Changelog-Vorschlag „Ein erzeugtes Modell steht nach dem Erzeugen auf der
  Platte“ stimmt nicht immer (F8). Fix: „kommt aufgesetzt an die erste freie
  Stelle“.

### Nach 0.5.1

**F7 — Eine Änderung davor rechnet jedes spätere Modell ganz neu**

- `app/core/scene/evaluate.py:4691–4697`: `#scene` sind die Hashes aller Objekte,
  und ein Objekthash enthält Operationsschlüssel und Merkmale
  (`object_hash(key, …, features=…)`). Gebraucht werden nur Grenzen und Platte.
- Beleg (`p3_cache_recompute.py`, `rev-einf-p3.txt`): Nur der Name von A geändert
  (Grenzen gleich) → B (327 680 Dreiecke) lädt neu: 2 statt 1 Fehltreffer,
  0,86 s statt 0,02 s. Bei zehn weiteren Modellen lädt jedes neu; ein 63-MB-3MF
  kostet laut Code-Kommentar 14 s.
- Fix: entfällt mit F1. Sonst den Schlüssel auf den Abdruck der übrigen Körper
  (Kennung, Platte, Grenzen) setzen statt auf ihre vollen Hashes.

**F8 — Ein erzeugtes Modell mit losem Krümel darunter schwebt nach der Reparatur**

- `app/core/generate.py:271` legt in `fit_to_size`, danach laufen
  `repair` (mit `small_components`) und gegebenenfalls `decimate_mesh`.
- Beleg (`p1_generated_floater.py`, `rev-einf-p1.txt`): Kugel mit einem Krümel
  (Radius 0,01) 0,1 Einheiten darunter → Krümel auf z = 0 gesetzt, von der
  Reparatur entfernt → Körper **5,21 mm über dem Bett**, `arrange.above_bed`.
  Ohne Krümel: aufgesetzt, mittig. Dezimieren geprüft (`p2b_decimate_bottom.py`):
  327 680 → 99 482 Dreiecke hält die Unterseite auf 0; erst 327 680 → 20 000 hebt
  sie um 0,105 mm. Weg 3 dezimiert nur von über 1 Mio. auf 750 000 — dort nicht
  beobachtet. (`p2` mit 1,3 Mio. Dreiecken nach 15 min abgebrochen, ersetzt
  durch `p2b`.)
- Vor dem Zweig lag ein erzeugtes Modell halb unter dem Bett; es ist also besser
  als vorher, hält aber die Zusage „am fertigen Maß gelegt“ nicht, wenn die Form
  danach noch schrumpft.
- Fix: nach der Reparaturkette legen — etwa `repair` hält einen aufgesetzten
  Eingang aufgesetzt, oder die Lage wird im letzten Schritt der Kette gesetzt.

**F9 — Tote Haken und widersprüchliche Befunde, wenn `free_spot` an ist**

- `app/core/ingest/ops.py:91–117`, `app/core/ingest/step_ops.py:72–96`: Mit
  `free_spot` setzt die Op selbst auf (`prepare.py:2816`, z = −minimum) und
  überstimmt „Mittig“. „Auf das Bett setzen“ auszuschalten ändert dann nichts,
  „Mittig“ einzuschalten auch nicht; der Dialog zeigt drei gleichrangige Haken.
  Wer die Dateilage will, muss zwei Haken finden (so auch der Testhelfer
  `keep_the_files_place`).
- Mit „Mittig“ und `free_spot` zugleich sagen Baugruppe und STEP „… mittig auf
  das Bett gesetzt“ (`ingest/ops.py:405–411`, `step_ops.py:467–472`) und direkt
  danach „Das Modell kam an die erste freie Stelle …“.
- Fix: `depends_on=("free_spot", (False,))` an `place_on_bed` und `centre` (der
  Dialog graut sie mit Grund aus, wie `wide_holes`), und `centre=params.centre and
  not params.free_spot` an beiden Stellen.

**F10 — Der Befund „erste freie Stelle“ steht auch, wo es keine gab**

- `app/core/geom/prepare.py:2835–2846`, angehängt in `ingest/ops.py:627` und
  `geom/ops.py:597` ohne Bedingung.
- Beleg (`p7`): (a) 300 × 300 mm → „kam an die erste freie Stelle auf Platte 2“
  neben `arrange.out_of_build_volume` (49 mm über); (c) nach zwölf vollen Platten →
  „… auf Platte 12“ neben `arrange.off_the_plate` (14 mm neben dem Bett, nur
  `info`). Außerdem steht der Satz, wenn sich nichts bewegt hat — dasselbe Modul
  nennt das Lärm (`_group_on_bed`: „ein Befund über eine Verschiebung um null
  wäre Lärm“).
- `prepare.py:2819` ist unerreichbar (die Schleife endet immer mit `return` an
  `plate == final`).
- Fix: `first_free_spot` sagt mit zurück, ob die Stelle passt; sonst ein eigener
  Satz („Auf keiner Platte war Platz — das Modell liegt neben Platte 12“) mit
  Ausweg; ohne Verschiebung kein Befund; toten Rückfall streichen.

**F11 — „Dieselbe Regel wie Auf dem Bett anordnen“ gilt ohne Filamenttrennung**

- *Auf dem Bett anordnen* trennt nach Filament, sobald mehr Filamente als Düsen
  auf dem Bett liegen (`prepare_ops.py:16956`, `_filament_groups`);
  `first_free_spot` kennt keine Filamente. Eine mehrfarbige 3MF kann so auf einer
  Platte mit fremdem Filament landen, die das Anordnen getrennt hätte.
- Fix: in §17.1 benennen oder die Gruppen an `first_free_spot` geben.

**F12 — Zwilling: der Abstand steht noch zweimal als Zahl**

- `ARRANGE_SPACING` (`prepare.py:2303`) soll „eine Stelle“ sein, aber
  `arrange_on_bed(spacing: float = 5.0)` (`:2579`) und
  `back_onto_bed(spacing: float = 5.0)` (`:2891`) behalten die Zahl.
  `zwillinge.md`: ungewollt → zusammenlegen.
- Fix: beide Vorgaben auf `ARRANGE_SPACING`.

**F13 — Hinter der zwölften Platte gelten zwei Regeln**

- `plates_behind` (`ingest/ops.py:631–633`) zählt ohne Grenze weiter (eine 3MF mit
  Platten kann Platte 13 und mehr belegen), `first_free_spot` betrachtet nur
  Platten bis `MAX_PLATES − 1` (`prepare.py:2806`). Liegt schon etwas auf Platte
  13, landet ein weiteres Modell neben Platte 12 statt auf einer leeren späteren.
- Fix: eine Regel für beide (Grenze in `plates_behind` oder die belegten Platten
  jenseits der Grenze in `first_free_spot` mitzählen).

**F14 — Bei gewählter Einzelplatte ist das neue Modell unsichtbar**

- `app/ui/header.py:522` behält die betrachtete Platte, `MainWindow._on_import_finished`
  (`main_window.py:19669`) wechselt nicht. Kommt das Modell auf eine andere Platte,
  steht es nicht im Bild; nur der Info-Befund nennt die Platte. Teilweise alt (vor
  dem Zweig kam es auf Platte 1 und fehlte, wenn Platte 2 gewählt war), der Zweig
  macht den Fall häufiger.
- Fix: nach dem Import `_show_the_plate_of(neues Objekt)` (`main_window.py:10346`,
  dieselbe Wahl wie im Plattenfeld) oder ein Ausweg „Platte zeigen“ am Befund
  `arrange.free_spot`.

**F15 — Beobachtung: das zweite Modell steht in der hinteren linken Ecke**

- Auf dem 256er Bett bei x −123, y 123, das erste in der Mitte. Folgt aus §29
  (hinterste, dann linkeste Stelle); zentriert wird nur eine Platte, die ganz neu
  angeordnet wird. Robert wollte beim Anordnen „startpunkt mitte“ (§29,
  09.09.2026). Keine Regelverletzung — eine Produktfrage: Kandidaten nach Abstand
  zur Plattenmitte ordnen, wenn die Ecke nicht gewollt ist.

## Fremd — nicht vom Zweig, auf der Basis ebenso

- `tests/test_operation_ui.py::test_the_body_state_lock_lifts_where_the_body_brings_what_is_asked`
  ist rot auf dem Zweig (`rev-einf-ui-20`) und auf `cbef27715`
  (`rev-einf-basis-ui20`). Vermutliche Ursache: `tests/helpers.py:209` ersetzt
  `ops.normalise` durch `partial(loader.normalise, mend=False)`, aber `load`
  übergibt `mend=params.mend` ausdrücklich (`ingest/ops.py:373`, Basis `:359`),
  und das Schlüsselwort des Aufrufs schlägt das des `partial` — der Körper wird
  geschlossen, *Offene Fläche schließen* ist gesperrt.
- `tests/test_ingest.py::test_a_second_model_is_not_dragged_into_the_first` endet
  nach „1 passed“ mit **Exit 127**, auf Zweig (`rev-einf-ui-01`, `-01b`) und Basis
  (`rev-einf-basis-ui01`). Der Test wartet nicht auf die Auswertungsarbeiter der
  Sitzung, die er mit zwei Importen startet. Im Release-Tor zählt der Code.

## Geprüft, ohne Befund

**Checkliste „Dateiformat ändern“**

1. `format_version` 37 → 38 (`migrations.py:29`).
2. Migration `_place_further_models_freely` (37 → 38, schreibt nichts um) —
   richtig, weil ein Schritt ohne Schalter wie gespeichert rechnet; die Stufe ist
   nötig, denn ein älteres Programm hielte am unbekannten Parameter an
   (`registry/params.py:481–486`, `constraint="unknown"`).
3. Belegdatei `tests/data/projects/further_model_v37.p3d` (Format 37,
   `app_version` 0.5.1, zwei Ladeschritte über den Plan, zweiter ohne
   Lageentscheidung); dazu `example_v38.p3d`, wie `EXAMPLE_FILE` sie verlangt.
4. `test_v37_a_further_model_keeps_the_place_of_its_file` prüft die Koordinaten,
   nicht nur das Öffnen.
5. Ältere Migrationen unberührt (nur eine Zeile angehängt).

**0.5.0 und ältere Dateien.** 0.5.0 schreibt **Format 33**, nicht 36
(`git show v0.5.0:app/core/scene/migrations.py`, `FORMAT_VERSION = 33`).
`p9_old_formats.py`: dieselbe Datei als Format 33, 36 und 37 öffnet mit 38 und
rechnet wie gespeichert (zweiter Würfel bei −10/−10/−10, kein `free_spot` im
Schritt). Ein Kunde mit 0.5.0 sieht an einer Datei aus 0.5.1 „Diese Projektdatei
ist neuer als das Programm.“ mit „Nach einer neuen Version sehen“ und
„Abbrechen“ — wie schon bei Format 34 bis 37.

**Cache: kein veralteter Treffer gefunden.** Der Objekthash kommt aus dem
Operationsschlüssel (Parameter, Eingangshashes, Profil, Qualität), damit trägt
`#scene` jede Lage- und Plattenänderung davor, auch gelöschte und ruhende
Schritte. `profile_key` enthält `build_volume`, `printable_area`,
`bed_exclusions`, `printable_height`. Der Schlüssel nach einer Antwort
(`_key_after_answers`) geht durch dieselbe Funktion. Alte Schritte behalten ihren
Schlüssel (`resolve_params` sieht nur gespeicherte Werte), und ihr Ergebnis ist
unverändert — `cache_version` durfte bleiben. `test_the_free_place_follows_the_model_before_it`
lief grün (`rev-einf-1`); die Gegenprobe der Sitzung (laut Bericht: Schalter aus →
drei Tests rot) habe ich nicht wiederholt, nur die für `fit_to_size` (F4).
Unnötig neu gerechnet wird dagegen (F7).

**Lage.** `p6_fill_plates.py`: Bambu P1S (Sperrzone vorn links) und Centauri
Carbon 2 (Sperrzone vorn rechts), ein Würfel und 25 Quader 50 × 50 × 10 über den
Plan: je 16 auf Platte 1 und 10 auf Platte 2, kein Paar unter 5 mm, keines
außerhalb der Fläche oder in einer Sperrzone, alle aufgesetzt, keine Warnung.
Baugruppe als Block (3MF, Abstand 40 mm bleibt; STEP-Instanzen exakt) und 3MF mit
Platten hinter der letzten belegten per Tests bestätigt. Deterministisch: kein
Zufall, gleiche Eingabe gleiche Lage; die Qualitätsstufe wirkt nur über
Hüllquader, und Grundkörper runden ihre Segmente auf Vielfache von vier
(`primitive_ops._round_segments`), haben also in beiden Stufen dieselben Grenzen.
Zu groß, zu hoch, zwölf Platten: `p7` — gemeldet wird jeweils, nur der Satz ist
falsch (F10).

**Rückgängig.** Ein Import ist eine Transaktion (`History.apply` mit einem
Entwurf); die Lage entsteht bei der Auswertung. Weg 3 hatte schon vorher mehrere
Transaktionen (`Generation.transactions`).

**Regeln** (am Diff gelesen). 1 kein Qt im Kern (nur `core`-Importe); 2 und 3 Lage nur in Ops,
`ctx.scene` nur gelesen (`standing_in`, `plates_behind`); 4 keine neue Op, neue
Parameter mit Titel, Vorgabe, `doc`, Übersetzung; 6 keine `==` auf Fließkomma
(`is_zero`, Ganzzahlvergleiche); 7 `ARRANGE_SPACING` ist ein Anordnungsabstand,
keine Materialtoleranz; 9 kein Zufall; 12 relative Pfade in den Belegdateien;
17 keine neue Ausnahme; 20 Texte über `_()`; 22 keine Abhängigkeit. Bezeichner
englisch.

**Texte.** Fünf Kataloge je fünf neue Schlüssel, im Probe-Merge vollständig
(`test_translations`). Die Verweise treffen die Titel im jeweiligen Katalog:
„Arrange on the bed“/„Centre on the bed“, «Organizar sobre la cama»/«Centrar
sobre la cama», « Disposer sur le plateau »/« Centrer sur le plateau »,
«Disponi sul piano»/«Centra sul piano», «Dispor na mesa»/«Centrar na mesa»; die
Platte heißt überall wie im Plattenwähler (Plate, Bandeja, Plaque, Piatto,
Placa).

**Statisch (Zweig).** mypy win32, `--platform linux`, `--platform darwin` je 330
Dateien ohne Befund; `ruff check` und `ruff format --check` (1043 Dateien) grün.

## Läufe

| Lauf | Inhalt | Ergebnis |
|---|---|---|
| `rev-einf-1` | Kern, 15 Dateien des Gebiets (Zweig) | 2616 passed, 4 skipped, 25 abgewählt, Exit 0 |
| `rev-einf-ui-01…24` | 24 Fenstertests einzeln (Zweig) | 22 grün mit Exit 0; `-01` passed mit Exit 127, `-20` rot — beide auf der Basis ebenso |
| `rev-einf-basis-ui01`, `-ui20` | dieselben zwei auf `cbef27715` | Exit 127 nach passed; rot |
| `rev-einf-merge-1` | Kern, 21 Dateien (Probe-Merge) | 2931 passed, 4 skipped, 32 abgewählt, Exit 0 |
| `rev-einf-mui-01…10` | 10 Fenstertests einzeln (Probe-Merge) | alle grün, Exit 0 |
| `rev-einf-mypy`, `-linux`, `-darwin`, `-ruff`, `-format` | Zweig | Exit 0 |
| `rev-einf-merge-mypy`, `-ruff`, `-format` | Probe-Merge | Exit 0 (333 / 1051 Dateien) |
| `rev-einf-mut-fit` | Mutation F4 | 1224 passed, Exit 0 (Lücke) |
| `rev-einf-p1`, `-p2b`, `-p3`, `-p4`, `-p5`, `-p6`, `-p7`, `-p9`, `-p10` | Sonden | siehe Funde |

---

## Nachtrag bc901772c

Geprüft: Endcommit `bc901772c` („Die freie Stelle eines weiteren Modells wird
einmal gerechnet und bleibt im Schritt“), ein Commit über `cf1015de2`, 30 Dateien,
+805/−232, jede Zeile des Diffs gelesen, dazu der Bericht des Agenten
`output/review/einfuegen-2026-09-28/nachtrag-f1.md`. Robert hat F1 entschieden:
„Einmal legen, festhalten“. Merge-Ziel jetzt `origin/main` auf `67ec1044d`.
Eigene Arbeitsbäume `wt-reveinf2` (Zweig), `wt-reveinf2-merge` (Probe-Merge,
nicht committet), `wt-reveinf-alt` (`cf1015de2`, nur für Gegenproben) — am Ende
entfernt. Läufe gebunden, in `laeufe/rev-einf2-*.txt`; Sonden in
`sonden/einfuegen/nachtrag/`.

### Urteil

**Mergebar: nein.** Das Festhalten hält auf dem ersten Weg (erster Import in ein
Projekt). Zwei Funde blockieren:

- **N1**: Kommt der erste Lauf eines suchenden Ladeschritts aus dem Cache, wird
  die Stelle nie festgehalten, und das Modell wandert wieder samt Bohrung, wie
  vor dem Fix. In der echten Sitzung nachgestellt: ab dem dritten Projekt mit
  denselben zwei Dateien und nach jedem Neustart.
- **N2**: Eine 3MF, deren Teile alle auf einer späteren Platte der Datei
  stehen, landet auf der falschen Platte und überlappt dort, was schon liegt.
  Das ist eine Regression gegenüber `cf1015de2`.

Beide Fixes sind klein. N3 bis N6 gehören in denselben Zug.

### Was hält (Beleg)

- Die drei Sonden aus dem ersten Durchgang stehen jetzt als Tests in
  `tests/test_free_spot_kept.py` (p4 Löschen, p5 Maß davor, p10
  Druckerwechsel: Lage, Volumen, Bohrungsversatz). Sie laufen grün
  (`rev-einf2-1`, im Probe-Merge `rev-einf2-merge-1`).
- **Undo/Redo nach dem Festhalten** hält: Die Stelle bleibt im Schritt, nach dem
  Löschen von A bleibt B (`p12_cache_hit_paths.py` Fall 1). `History.undo` legt
  die lebende Fassung samt Antworten weg (`history.py:2680`).
- **Speichern und wieder öffnen**: Die Stelle steht in der Datei
  (`spot_x −103, spot_y 108, spot_plate 1`); nach dem Öffnen und nach dem Löschen
  von A bleibt B (`p11_kept_paths.py` Fall e).
- **B vor A verschoben** (`plan_move`): A bleibt mittig, B an seiner Stelle
  (`p11` Fall f). Neu gefasste Schritte tragen ihre Parameter samt Stelle
  (`History._clone`, `history.py:1802–1857`).
- **Druckerwechsel nach dem Festhalten**: `test_another_printer_leaves_the_next_model_and_its_bore` grün.
- **Kopieren des Ladeschritts**: Die Oberfläche hat keinen Weg, einen Schritt zu
  kopieren (gesucht in Sitzung, Fenster, Verlauf). Umbau und Wiederholung nach
  einer Reparatur nehmen die Stelle mit, und das ist richtig.
- Kommandozeile: `run_evaluation` schreibt die Antworten fest
  (`cli/main.py:217`); `command_import` speichert danach.

### Funde

#### Blockiert den Merge

**N1 — Kommt der erste Lauf eines suchenden Schritts aus dem Cache, bleibt die Stelle offen**

- Stellen: `app/core/scene/evaluate.py:725–731` (Treffer: `result = cached`,
  keine Antwort), `:1188` (`pending.append((key, result, not watched.used))`: der
  suchende Schlüssel geht auch auf die Platte, denn gefragt wird nicht),
  `app/core/scene/cache.py:134–148` (`CachedResult` hat kein Feld für Antworten),
  `app/ui/session.py:5537` (festgehalten wird nur `result.answers`).
- Beleg, jeweils mit eigenem Plattencache wie die Sitzung
  (`disk_backed_cache`, `record_answers` nach jedem gültigen Lauf):
  - `p12` Fall 3: zweites Projekt mit denselben Dateien → Stelle `None`; A
    gelöscht → B springt von (−123, 93) nach (−20, −15), **wandert**.
  - `p12` Fall 4: nach einem Neustart (frischer Speicher, dieselbe Platte) →
    ebenso.
  - `p12` Fall 2: Strg+Z vor dem ersten Ergebnis, dann Strg+Y → Stelle `None`,
    wandert.
  - Kontrollfall 5 (anderer Dateiname für B) → festgehalten, bleibt.
  - **Echte Sitzung** (`p13_session_path.py`, offscreen, `Session.import_payload`
    mit Bild zuerst): Projekt 1 und 2 halten fest. Projekt 3 mit denselben zwei
    Dateien und Projekt 4 nach einem Neustart halten nicht fest; A gelöscht → B
    von (−105, 75) nach (−20, −15). Dass Projekt 2 noch hält, ist Zufall: Dort
    kam schon A aus dem Cache und behielt `unit: auto`, das änderte den Hash vor
    B. Derselbe Mechanismus lässt die Einheitenantwort von A ab dem zweiten
    Projekt offen. Bei der Einheit ist das harmlos, weil die Heuristik nicht von
    der Szene abhängt. Bei der freien Stelle ist es F1.
  - Im Probe-Merge mit main unverändert (`rev-einf2-p12-merge`).
- Warum es zählt: Der Bauplan verspricht jetzt „wird davor etwas gelöscht oder
  geändert oder der Drucker gewechselt, wandert es nicht“ (§17.1). Auf diesen
  Wegen wandert es, und Schritte danach treffen nicht mehr — der Schaden aus F1.
  Wer dieselben Teile ein zweites Mal in ein Projekt holt, trifft darauf. Der
  Plattencache überlebt Projektwechsel und Neustart
  (`ResultCache.clear` leert nur den Speicher). Die neuen Tests sehen es nicht:
  `test_free_spot_kept.py` und `test_ingest.py` werten ohne Cache aus, jeder Lauf
  rechnet und liefert seine Antwort.
- Fix: **Die Antwort reist mit dem Ergebnis.** `CachedResult.answered`
  kommt in den Speicher und in `objects.json` der Platte, dazu
  `CACHE_FORMAT_VERSION + 1`. Bei einem Treffer setzt `evaluate`
  `answers[operation.id]` aus dem Eintrag. Das Zusammenlegen der Bildantworten in
  `_EvaluationWorker._evaluate` wird damit überflüssig. Test: `p12` Fall 2 bis 4
  als Tests mit einem Plattencache im Temp-Ordner. Suchende Ergebnisse gar nicht
  mehr abzulegen wäre die Alternative, aber dann rechnet der Ladeweg mit Bild
  zuerst den Import zweimal.

**N2 — Eine 3MF mit ihren Teilen auf einer späteren Platte der Datei landet auf der falschen Platte**

- Stelle: `app/core/ingest/ops.py:648` —
  `plate=entry.plate + placed.plate` gilt jetzt auch ohne Plattenaufteilung.
  Der Leser nummeriert mit leeren Platten
  (`threemf._plate_layout`: „Auch leere Platten zählen“). Eine Datei mit leerer
  Platte 1 und allem auf Platte 2 bringt also `part.plate = 1`, obwohl
  `several_plates` falsch ist.
- Beleg (`p17_plates_and_refusal.py`, Fall A; Szene: Würfel auf Platte 1, eine
  Platte 240 × 240 auf Platte 2, dann die 3MF): Die freie Stelle wird für Platte 1
  gerechnet (Befund „… auf Platte 1“, `spot_plate 1`). Der Körper steht aber auf
  **Platte 2** bei x −123…−113, y 113…123, **mitten in der 240er Platte**
  (x −123…117, y −117…123). Auf `cf1015de2` steht derselbe Körper auf Platte 1
  ohne Überlappung (`rev-einf2-p17-alt`, damals `plate=plate`).
- Warum es zählt: Überlappende Körper druckt der Slicer verschmolzen, und der
  Bericht sagt nichts. Nur `arrange.bodies_in_one_place` meldet deckungsgleiche
  Körper. Der Befund nennt die falsche Platte. Dateien aus Bambu Studio, Orca
  und ElegooSlicer tragen ihre Platten, und der Plan setzt `plates` für jede
  neue 3MF.
- Fix: Die Platte der Stelle nur bei `keep_layout` addieren, sonst `plate=placed.plate`
  wie in `cf1015de2`. Dazu `p17` Fall A als Test.

#### Vor dem Tag

**N3 — Die festgehaltene Stelle passt nicht in ihr eigenes Feld; die Kette hält am Ladeschritt**

- Stelle: `app/core/geom/prepare.py:2857–2872` (`spot_param`: `minimum=-1000.0`,
  `maximum=1000.0`).
- Beleg (`p15_spot_range.py`): Ein weiteres Modell von 2500 mm Länge bekommt
  beim ersten Lauf `spot_x = 1127`. Nach dem Festhalten hält der nächste Lauf am
  Ladeschritt an: „Der Wert liegt über dem zulässigen Höchstwert.“ (`spot_x`,
  `maximum 1000`), das Modell ist fort. 300 und 1200 mm laufen durch. Leeren des
  Felds hilft nicht, es wird wieder 1127 gerechnet. Heraus kommt nur, wer
  *An eine freie Stelle legen* ausschaltet.
- Warum es zählt: Die Grenze liegt ab etwa 2,25 m Länge (256er Bett). Selten,
  aber genau der Weg „zu groß → Automatisch teilen“, und der Kunde bekommt eine
  Absage über ein Feld, das er nie gesetzt hat (Regel 17 verlangt einen Weg
  hinaus).
- Fix: Grenzen der Felder weit fassen (etwa ±100 000 mm; das Minimum braucht der
  Dialog nur für den leeren Zustand). Test: 2,5 m zweimal auswerten.

**N4 — Ein Modell an der Einfügemarke landet auf einem festgehaltenen**

- Stelle: `app/ui/session.py:2202` (mit Einfügemarke geht auch ein Import über
  `_insert`), `app/core/geom/prepare.py` `placed_at_free_spot` (sucht an der Szene
  vor dem Schritt; das spätere, festgehaltene Modell steht dort noch nicht).
- Beleg (`p18_insert_mark.py`, `History.plan_insert` vor Bs Ladeschritt, wie
  `Session._insert`): C und B stehen **deckungsgleich** bei x −123…−83,
  y 93…123. Außer dem Hinweis `arrange.bodies_in_one_place` (info) kommt kein
  Befund, bei ungleichen Modellen gar keiner. Auf `cf1015de2` wich B aus
  (x −78…−38), wanderte dabei aber (F1).
- Fix: Mit Einfügemarke rechnet die Sitzung die Stelle am Endstand
  (`last_result`) und schreibt sie gleich in den Entwurf (`spot_x`, `spot_y`,
  `spot_plate`), statt sie suchen zu lassen. Sonst in §17.1 benennen und
  melden.

**N5 — *Modell erzeugen*: ein Strg+Z nimmt nur das Aufsetzen, im Normalfall unsichtbar**

- Stelle: `app/core/generate.py:319–324` (eigene Transaktion „Auf das Bett
  setzen“).
- Beleg (`p16_generate_undo.py`): vier Transaktionen („Modell erzeugen“, „Auf
  Arbeitsgröße bringen“, „Reparaturkette“, „Auf das Bett setzen“). Kugel ohne
  Krümel: tiefster Punkt 0,0 mit und ohne den letzten Schritt. Ein Strg+Z
  ändert also nichts Sichtbares. Mit Krümel schwebt der Körper nach einem Strg+Z
  wieder 5,21 mm (`arrange.above_bed`).
- Antwort auf die Frage des Koordinators: Strg+Z nimmt nur das Aufsetzen zurück,
  nicht das Erzeugen. Das war vorher nicht anders — Weg 3 hatte schon drei bis
  vier Transaktionen, ein Strg+Z nahm die Reparatur. Regel 16 gilt dem
  Agentenvorschlag, und der Agent erzeugt keine Modelle (`app/core/agent` ruft
  `from_text`/`add_generated` nicht); Regel 2 ist erfüllt (`place_on_bed` ist
  eine Op). Neu ist ein Schritt ohne Wirkung und ohne Satz. `_place_inputs_on_bed`
  meldet keinen `transform.without_effect` („Eine Operation, die nichts bewirkt
  hat, sagt das“, `operationen.md`).
- Fix: `place_on_bed` in die Transaktion des letzten Kettenschritts (Reparatur
  oder Dezimieren) — ein Strg+Z nimmt dann Kettenschritt und Aufsetzen zusammen,
  wie vor dem Nachtrag.

**N6 — `arrange.no_free_spot` bietet, was nicht hilft, und sagt es bei Übergröße falsch**

- Stellen: `app/core/geom/prepare.py:2823` (`fits_on_bed` prüft auch die Höhe),
  `:2952–2960`.
- Beleg (`p17` Teil B): Bei 300 × 300 mm und bei 20 × 20 × 300 mm kommen je zwei
  Warnungen, `arrange.no_free_spot` mit *Auf dem Bett anordnen* und
  `arrange.out_of_build_volume`. Anordnen macht kein 300er Teil passend. Das
  eigene Modul lehnt so einen Rat ab („Ein Vorschlag, der nichts löst, ist
  schlimmer als keiner“, `_overfull`). Beim zu hohen Teil sagt der Satz
  „steht über die Druckfläche hinaus“, aber es ist zu hoch. Nach zwölf vollen
  Platten passt beides (Platte 12, *Anordnen* kann neu verteilen).
- Fix: `no_free_spot` nur, wenn die Grenze von zwölf Platten der Grund ist (das
  Modell passte auf ein leeres Bett). Übergröße sagt `check_build_volume` mit
  seinen Auswegen.

#### Beim Merge

**N7 — Die Prozesswache von main fährt den Pfad der freien Stelle nicht**

- main stellt `load` und `load_step` von den Prozesswerten frei
  (`reads_process=False`). Der Beleg `_STEPS_WITHOUT_PROCESS` fährt `load` nur
  mit `{"source", "unit"}` (`tests/test_cache.py:740` auf `67ec1044d`), also ohne
  `free_spot`.
- Beleg (`p14_process_guard_free_spot.py` im Probe-Merge, mit mains
  `_guarded_run`): `load` suchend mit Nachbar, `load` festgehalten, `load_step`
  suchend — alle ohne Zugriff auf einen Prozesswert. Die Freistellung bleibt
  richtig.
- Fix: Beim Merge diese drei Läufe in den Beleg aufnehmen. Die Kombination
  entsteht erst dort.

#### Nach 0.5.1

**N8 — Der Plattenwechsel nach dem Import (F14) gilt nur für Dateien vom Pfad**

- `app/ui/main_window.py:19724–19730`: gesetzt in `_on_import_confirmed`, das
  nur mit `_recent_candidate` läuft. Ein Download (`_pending_download`) und ein
  erzeugtes Modell wechseln die Platte nicht. Einen Fenstertest gibt es nicht
  (sagt der Bericht selbst). In den Registerpunkt „Freie Stelle: Fenstertests
  und Abnahme“ aufnehmen.

### Merge mit main `67ec1044d`

- **Drei Konflikte**, im eigenen Baum gelöst:
  - `.claude/rules/oberflaeche.md:58`: **1355** Parameter (im Probe-Merge aus
    dem Register gezählt: 1337 Basis + 6 von main + 12 vom Zweig).
  - `app/core/scene/CLAUDE.md:144`: der Satz des Zweigs hinter
    `(_DAMAGED_ENTRY)` und danach mains neuer Absatz zu `reads_process`.
  - `app/i18n/locales/it.json:1867`: mains zwei Zeilen plus die Zeile „Die Platten
    der Datei kommen hinter …“.
- **`reads_process` und `reads_scene` vertragen sich.** Das eine steuert den
  Profilteil des Schlüssels (`hashing.profile_key(process=…)`), das andere nur
  `#scene` in `_with_nested_context`. `_key_after_answers` gibt auf main
  `process=spec.reads_process` mit, der Schlüssel nach der Antwort gleicht also
  dem des nächsten Laufs. Die Bettgeometrie, die die freie Stelle liest
  (`build_volume`, `printable_area`, `bed_exclusions`, `printable_height`), steht
  in `_profile_parts` als fester Wert, auch ohne Prozesswerte (N7).
  `fit_to_size` behält die Vorgabe (liest die Mindestwand).
- Größen nach dem Merge: `dateiformat.md` 30 323 (F3 erledigt),
  `operationen.md` **30 719 von 30 720** — mains eigener Stand, der Zweig fasst die
  Datei nicht an, aber ein Byte Luft ist die nächste rote Zeile —,
  `app/core/scene/CLAUDE.md` 18 074 von 25 600.
- Probe-Merge grün: Kern 21 Dateien **3055 passed**, 4 skipped, 32 abgewählt,
  Exit 0 (`rev-einf2-merge-1`). 15 Fenstertests einzeln grün (`rev-einf2-mui-01…15`),
  `-02` endet wie auf der Basis nach „passed“ mit Exit 127. mypy win32/linux/darwin
  je 333 Dateien, ruff, format 1052 Dateien, alle Exit 0.

### Stand der Funde aus dem ersten Durchgang

| Fund | Stand am `bc901772c` |
|---|---|
| F1 Wandern | im ersten Importweg behoben; offen auf den Cachewegen (N1) |
| F2 Konflikte | jetzt drei (siehe oben) |
| F3 `dateiformat.md` | behoben (ein Satz, ohne Datum, 30 323 nach dem Merge) |
| F4 Wächter `fit_to_size` | behoben: Mutation `reads_scene` weg → `test_cache.py` bricht beim Sammeln ab (Exit 2, `rev-einf2-mut`) |
| F5 Wortlaut | behoben (§17.1 „ohne Lageentscheidung“, Docstring) |
| F6 Register, Changelog | Texte für die Release-Sitzung liegen im Bericht des Agenten; Changelog-Satz richtig |
| F7 Neurechnen | entfällt nach dem Festhalten |
| F8 Krümel | behoben (Aufsetzen nach der Kette); dafür N5 |
| F9 tote Haken | behoben (`depends_on`, kein zweiter Befund) |
| F10 Befund | ohne Bewegung kein Befund, Absage eigener Code; dafür N6 |
| F11, F13, F15 | Registertexte liegen vor (nach 0.5.1) |
| F12 Zwilling | behoben |
| F14 Plattenwechsel | für Dateien vom Pfad; N8 |

### Läufe (Nachtrag)

| Lauf | Inhalt | Ergebnis |
|---|---|---|
| `rev-einf2-1` | Kern, 16 Dateien (Zweig) | 2624 passed, 4 skipped, 25 abgewählt, Exit 0 |
| `rev-einf2-merge-1` | Kern, 21 Dateien (Probe-Merge) | 3055 passed, 4 skipped, 32 abgewählt, Exit 0 |
| `rev-einf2-mui-01…15` | 15 Fenstertests einzeln (Probe-Merge) | alle passed; `-02` Exit 127 wie auf der Basis |
| `rev-einf2-mypy`, `-linux`, `-darwin`, `-ruff`, `-format` | Zweig | Exit 0 (330 / 1044 Dateien) |
| `rev-einf2-merge-mypy`, `-linux`, `-darwin`, `-ruff`, `-format` | Probe-Merge | Exit 0 (333 / 1052 Dateien) |
| `rev-einf2-mut` | Mutation F4 | Sammelfehler in `test_cache.py`, Exit 2 (Wächter greift) |
| `rev-einf2-p11`, `-p12`, `-p12-merge`, `-p13` | Festhalten auf Kundenwegen | siehe N1 und „Was hält“ |
| `rev-einf2-p14` | Prozesswache mit freier Stelle | kein Prozesswert gelesen |
| `rev-einf2-p15` | Feldgrenze | 2500 mm hält am Ladeschritt (N3) |
| `rev-einf2-p16` | Weg 3, Strg+Z | N5 |
| `rev-einf2-p17`, `-p17b`, `-p17-alt` | Platten der Datei, Absage | N2, N6 |
| `rev-einf2-p18`, `-p18-alt` | Einfügemarke | N4 |

---

## Nachtrag e85c77ed0

Geprüft: Endcommit `e85c77ed0`, drei Commits über `bc901772c` (`eeafc867e` N1,
`8c343fc00` N2, `e85c77ed0` N3–N6), 13 Dateien, +565/−58. Jede Zeile des Diffs
gelesen, dazu der Bericht der Sitzung `output/review/einfuegen-2026-09-28/nachtrag-2.md`.
Merge-Ziel `origin/main` auf `54344dbb7`; seit `67ec1044d` kam dort nur ein
Commit (Signierübergabe, `tools/make_installer.py`, `tests/test_packaging.py`).
Eigene Arbeitsbäume `wt-reveinf3` (Zweig), `wt-reveinf3-merge` (Probe-Merge,
nicht committet) und `wt-reveinf-bc` (`bc901772c`, nur für Gegenproben), am Ende
entfernt. Läufe in `laeufe/rev-einf3-*.txt`, Sonden in
`sonden/einfuegen/nachtrag2/`.

### Urteil

**Mergebar: ja.** N1 bis N6 sind behoben, jeweils am echten Weg nachgemessen,
und es gibt keinen neuen Fund, der den Merge aufhält. Beim Merge sind vier
Konflikte nach der Vorgabe unten zu lösen. Dazu gehört mains Prozesswache um
den Pfad der freien Stelle ergänzt (N7 aus dem vorigen Nachtrag, sachlich
belegt ohne Befund).

### Die Fragen des Koordinators

**1. N1 im Kundenweg — bleibt die Stelle?** Ja.

- Echte Sitzung (`p19_session_kept.py`, offscreen, Bild zuerst, Plattencache):
  Projekt 1, 2 und 3 mit denselben zwei Dateien, Projekt 4 nach einem Neustart
  und Strg+Z sofort nach dem Import von B mit Strg+Y danach. In jeder Runde
  stehen Einheit (`mm`) und Stelle (−85, 90) im Schritt. Wird A gelöscht,
  bleibt B bei (−105, 75). Vorher hielt ab Projekt 3 nichts mehr (`p13`).
  Im Probe-Merge dasselbe (`rev-einf3-p19-merge`).
- Am Kern mit Plattencache (`p12_cache_hit_paths.py`): alle fünf Fälle
  „bleibt“, darunter Strg+Z vor dem Ergebnis, zweites Projekt und Neustart.

**1b. Kann eine Antwort aus dem Cache falsch sein?** Nein, die Rechnung
schließt es aus, und die Sonde bestätigt es.

- Solange die Stelle leer ist, liest der Schritt die Szene. Sein Schlüssel
  enthält dann `#scene`, die Hashes **aller** Objekte davor samt Kennung
  (`evaluate._with_nested_context`). Jeder Objekthash kommt aus dem Schlüssel
  des Schritts, der das Objekt erzeugt hat, also aus Parametern, Eingängen,
  Quelleninhalt und Profil. Dazu kommen die Bettwerte des Profils
  (`hashing._profile_parts`, feste Werte) und der Inhalt der eigenen Datei.
  Das sind alle Eingänge von `first_free_spot`. Gleicher Schlüssel heißt also
  gleiche Stelle.
- Ist die Stelle gesetzt, fällt `#scene` weg. Ein Treffer kommt dann nur noch
  unter dem Schlüssel nach der Antwort, dessen Parameter die Antwort schon
  enthalten; weitergegeben wird dieselbe Zahl, und `record_answers` ändert
  nichts (`merged == params`, kein falsches „geändert“).
- Sonde `p20_cached_answer_right.py`: dieselbe Datei B nach verschiedenen
  ersten Modellen (Würfel, 230er Platte, Würfel mit anderem Namen, Würfel in cm),
  einmal frisch, einmal mit geteiltem Plattencache. Jede Antwort gleicht der
  frischen Rechnung (−103/108/1, 0/0/2, −103/108/1, 0/0/2). Nur die exakt
  gleiche Folge traf den Cache und bekam dieselbe Antwort.
- Eine erfragte Antwort (`ctx.ask`: Einheit, `sections`, `open_side`,
  `opening_signature`) geht nie auf die Platte (`to_disk = not watched.used`).
  Im Speicher gilt sie nur derselben Sitzung; beim Projektwechsel wird der
  Speicher geleert (`Session._reset_for`). Ein Treffer gibt dort dieselbe
  Entscheidung für denselben Schritt weiter, wie die Sitzung es will.

**2. Bildantworten nicht mehr zusammengelegt; Einfügen über den Planer im Arbeiter.**
Kein Rückschritt gefunden.

- Einheitenfrage (`p22_session_unit_question.py`, `plate_cm.stl` und
  `bracket_inch.stl` als zweites Modell, Antwort über `askRequested`): je
  **eine** Frage, die Antwort steht danach im Schritt, die Stelle auch, und B
  bleibt beim Löschen von A. Die erkannte Einheit ohne Frage steht in jeder
  Runde von `p19` im Schritt. Ist der Eintrag verdrängt oder fehlt der Cache,
  rechnet der zweite Lauf neu und antwortet selbst (Rückfrage über
  `_pending.replay`).
- Wartezeit (`p23_insert_timing.py`, Kugel mit 327 680 Dreiecken): angehängt
  2,03 s bis zur Ruhe, an der Einfügemarke 2,07 s. Die Lade-Operation rechnet
  **einmal**, denn der Einfügeort trifft den Schlüssel nach der Antwort, den
  der Probelauf am Ende abgelegt hat. Eine Bohrung an der Marke (liest die
  Szene nicht) bleibt bei 0,02 bis 0,03 s (`p21` b).
- Einfügen an der Marke (`p21_session_insert.py` a): C bekommt seine Stelle
  (−40, 90) im Schritt, B behält (−85, 90), keine Überlappung. Auf `bc901772c`
  lagen beide deckungsgleich bei (−85, 90) (`rev-einf3-p21-bc`).
- Abbruch sofort nach dem Einfügen (`p21` c): Die Schritte bleiben, die Marke
  steht, kein Fehler. Eine eingebettete Quelle `src_3` bleibt im Dokument
  zurück, auf `bc901772c` genauso (siehe „Vorbestehend“).
- Fehlerweg: Eine Absage des Planers kommt über `failedWith` wie bei jedem
  Umbau, ein Abbruch über `OperationCancelled` (`_RevisionWorker.work`). Hält die
  Kette beim Probelauf an, bleibt der Entwurf unverändert, wie
  `searched_at_the_end` es sagt. Der Probelauf hängt nur Entwürfe ans Ende, die
  die Szene lesen: Laden und Auf-Maß-Bringen mit offener Stelle. Ein Laden hat
  keinen Eingang, der am Ende fehlen könnte. *Modell erzeugen* geht an der
  Marke vorbei (`generate.into_project` baut seine eigene `History`) — das
  war vorher schon so.

**3. Cache 33 gegen main 32.** In Ordnung. Im Merge bleibt `CACHE_FORMAT_VERSION = 33`,
die Begründungsliste führt 32 (main, `reads_process`) und 33 (Zweig,
`answered`) nacheinander. 33 ist größer als beide Stände, also verwirft der
gemergte Bau jeden Eintrag aus einem Bau mit 32 oder mit 31. Der Plattenordner
trägt dazu die Fassung und einen Baustempel (`paths.py:94`, `_build_stamp`),
ein Release beginnt ohnehin mit leerem Ordner.

**4. Probe-Merge mit `54344dbb7`** — siehe unten.

### Stand N1 bis N8

| Fund | Stand am `e85c77ed0` | Beleg |
|---|---|---|
| N1 Antwort aus dem Cache | behoben | `p19` Sitzung, `p12`, `p20`; Tests mit `DiskCache` und Bedingung „kam von der Platte“ |
| N2 Platte der Datei | behoben: Teil auf Platte 1 neben dem Würfel, keine Überlappung | `p17` A (`rev-einf3-p17_plates_and_refusal`) |
| N3 Feldgrenze | behoben (`SPOT_LIMIT` 100 000 mm): 2500 mm rechnet beim zweiten Lauf durch | `p15` |
| N4 Einfügemarke | behoben, anders als vorgeschlagen und richtig begründet: Mit Marke zeigt `last_result` den Stand davor | `p21` a gegen `-bc`, `p23` |
| N5 Strg+Z bei *Modell erzeugen* | behoben: drei Transaktionen, ein Strg+Z nimmt Reparatur und Aufsetzen, tiefster Punkt danach 0,0 (auch mit Krümel) | `p16` |
| N6 Absage | behoben: zu breit und zu hoch nur `out_of_build_volume`, zwölf volle Platten `no_free_spot` mit *Auf dem Bett anordnen* | `p17` B |
| N7 Prozesswache | offen, beim Merge (die Freistellung stimmt: `p14` im Probe-Merge ohne Prozesswert) | `rev-einf3-p14-merge` |
| N8 Plattenwechsel nur vom Pfad | Registertext liegt vor (nach 0.5.1) | Bericht der Sitzung |

### Beim Merge

- **Vier Konflikte**, im eigenen Baum so gelöst (`resolve_merge3.py`):
  - `.claude/rules/oberflaeche.md`: **1355** Parameter der 142 Operationen (aus
    dem Register gezählt).
  - `app/core/scene/CLAUDE.md`: der Absatz des Zweigs hinter
    `(_DAMAGED_ENTRY)` (mit dem neuen Satz zu `CachedResult.answered`), danach
    mains Absatz zu `reads_process`.
  - `app/core/scene/cache.py`: die Begründungszeile 32 von main, dann 33 vom
    Zweig, Wert 33.
  - `app/i18n/locales/it.json`: mains zwei Zeilen plus „Die Platten der Datei
    kommen hinter …“.
- **N7**: In `_STEPS_WITHOUT_PROCESS` (`tests/test_cache.py`) drei Läufe mit
  `free_spot` ergänzen: `load` suchend mit Nachbar, `load` mit festgehaltener
  Stelle, `load_step` suchend. Die Kombination entsteht erst mit dem Merge.
- Größen nach dem Merge: `dateiformat.md` 30 323, `operationen.md` 30 719
  (mains Stand, vom Zweig unberührt, ein Byte Luft), `app/core/scene/CLAUDE.md`
  18 295 von 25 600.
- Probe-Merge grün: Kern 24 Dateien **3240 passed**, 4 skipped, 36 abgewählt,
  Exit 0 (`rev-einf3-merge-1`). 20 Fenstertests einzeln (`rev-einf3-mui-01…20`,
  darunter die vier aus `test_history_revision_ui.py` und der Bildweg) alle
  passed; `-06` endet wie auf der Basis nach „passed“ mit Exit 127. mypy
  win32/linux/darwin je 333 Dateien, ruff, format 1052 Dateien, alle Exit 0.

### Vorbestehend — nicht vom Zweig

- **Ein abgebrochener Import an der Einfügemarke lässt seine Quelle im Dokument**
  (`p21` c: `src_3` bleibt nach `Session.cancel`, auf `bc901772c` ebenso). Mit
  dem nächsten Speichern reiste sie in die Projektdatei. `import_payload` räumt
  eine abgewiesene Quelle aus (`_drop_source`), der Umbauarbeiter nach einem
  Abbruch nicht. Nach 0.5.1: im Abbruch- und Absageweg von `_insert`
  ausräumen, was `_embed_source` eben eingetragen hat.

### Läufe (Nachtrag e85c77ed0)

| Lauf | Inhalt | Ergebnis |
|---|---|---|
| `rev-einf3-1` | Kern, 19 Dateien (Zweig) | 2820 passed, 4 skipped, 29 abgewählt, Exit 0 |
| `rev-einf3-merge-1` | Kern, 24 Dateien (Probe-Merge) | 3240 passed, 4 skipped, 36 abgewählt, Exit 0 |
| `rev-einf3-mui-01…20` | 20 Fenstertests einzeln (Probe-Merge) | alle passed; `-06` Exit 127 wie auf der Basis |
| `rev-einf3-mypy`, `-linux`, `-darwin`, `-ruff`, `-format` | Zweig | Exit 0 (330 / 1044 Dateien) |
| `rev-einf3-merge-mypy`, `-linux`, `-darwin`, `-ruff`, `-format` | Probe-Merge | Exit 0 (333 / 1052 Dateien) |
| `rev-einf3-p19`, `-p19-merge` | N1 in der Sitzung | bleibt in allen Runden |
| `rev-einf3-p12_cache_hit_paths` | N1 am Kern | alle fünf Fälle bleiben |
| `rev-einf3-p20` | Antwort aus dem Cache richtig? | jede gleich der frischen Rechnung |
| `rev-einf3-p21`, `-p21-bc` | Einfügemarke, Abbruch | behoben; Quelle nach Abbruch vorbestehend |
| `rev-einf3-p22` | Einheitenfrage mit Bild zuerst | eine Frage, Antwort und Stelle im Schritt |
| `rev-einf3-p23` | Wartezeit an der Marke | 2,07 s gegen 2,03 s, einmal geladen |
| `rev-einf3-p14-merge` | Prozesswache mit freier Stelle | kein Prozesswert |
| `rev-einf3-p15_spot_range`, `-p16_generate_undo`, `-p17_plates_and_refusal` | N3, N5, N2/N6 | behoben |
