# `app/core/scene/` — Dokument, Stapel, Auswertung

Was gerade offen ist und wie daraus Geometrie wird (§12–§16). Regeln in
`.claude/rules/`: `operationen.md` („Szene: Platzierung, Kennungen, Cache,
Projektdatei"), `kern.md`, `dateiformat.md`. Herleitungen:
`konzepte/begruendungen/karte-app-core-scene.md`.

## Der Kreislauf

```
Project ──> History (Stapel aus Transaktionen)
                │
                ▼
           evaluate()  ── reine Funktion aus
                │         Stack + Quellen + Parametern + Profilen + Startwerten
                ▼
        EvaluationResult (Szene, Befunde, Kennzahlen)
```

**Die Auswertung ist eine reine Funktion** (§15.1): Was das Ergebnis
beeinflusst, lebt nie nur in der Sitzung; eine Antwort kommt über
`OpResult.answered` in den Stapel (`_key_after_answers`).

`History.change_params(..., changes=...)` übernimmt die vollständige
`DocumentChange` zusammen mit den geänderten Schrittfassungen. Passungen und
benannte Maße gehören beim Deckelwechsel zur selben Undo-/Redo-Geste.

**Prüfungen haben einen eigenen Durchführungsstand.**
`EvaluationResult.check_states` und `evaluate(check_status=...)` melden
`CheckState` getrennt von Befunden. `completed` bedeutet vollständig
ausgeführt, nicht fehlerfrei. Fehlende bestätigte Grundlagen übergibt der
Aufrufer als `missing_basis`; die betroffenen Endprüfungen bleiben
`not_started`. Körper-/Profilwechsel, Undo/Redo und Öffnen rechnen die
Abschlussprüfungen neu. Der Operationscache und die Projektdatei speichern
keine Fertigmarken. Vorschauen ohne erkannte Merkmale belegen keine allgemeine
Wand- oder Formprüfung; diese beiden Prüfungen gelten nur ihren benannten
Merkmalen. Der Empfänger ordnet Callbackmeldungen der Auftragsrevision zu.

## Die Karte

| Datei | Rolle |
|---|---|
| `project.py` | Der Container (§16.1): `save()`, `load()`, Autosave, Wiederherstellung, Prüfsumme, `content_digest` |
| `serialise.py` | Dokument zu Daten und zurück — Parameter, Passungen, Quellen, Herkunft, Transaktionen, Chat |
| `migrations.py` | `FORMAT_VERSION` und die Kette `vN → vN+1`; Parameterausdrücke bleiben erhalten, wertabhängige Altformat-Umrechnungen tragen einen Marker und laufen mit den aufgelösten Werten bei jeder Auswertung; **ältere Migrationen werden nie zusammengefasst** |
| `gathered.py` | Große Sammelwerte wandern aus dem Stapel in den Container (§12) |
| `foreign.py` | Was eine fremde Projektdatei außer Geometrie mitbringt (§32) |
| `history.py` | Stapel, Transaktionen, Undo (§15.4, §15.5); `OperationDraft`, `RevisionPlan`, `discarded` (Bericht, Verlauf) |
| `revision.py` | Den Verlauf umbauen: `dependencies`, `step_needs`, `revise`, `verdict`, `commit`; `searched_at_the_end` lässt Eingefügtes seine freie Stelle am Endstand suchen |
| `rebuild.py` | Nachbau (§42): P4.0/Netzfits, Formvergleich, benannte Maße, atomare Übernahme |
| `bundling.py` | Welche Züge zu einem Schritt verschmelzen (§15.5), **opt-in je Operation** |
| `evaluate.py` | Die Auswertung (§15.1); `EvaluationResult.question_reference` trägt bei einer offenen Zuordnungsfrage den bisherigen Bezug mit Ansichtsdreiecken nur vorübergehend zur Ansicht; gemerkte Zuordnungsschritte (RM-593) |
| `edge_binding.py` | Gewählte Kanten **vor** dem Verbrauchercache binden (§21.3) |
| `cache.py` | Ergebnis-Cache über dem Operations-Hash, Speicher und Platte; Speicherebene in Bytes begrenzt samt Merkern, ältere Einträge schrumpfen vor dem Verdrängen (RM-567) |
| `hashing.py` | `operation_hash()`, `object_hash()`, `profile_key()`, `feature_digest` |
| `parameter_usage.py` | Direkte und abgeleitete Parameterverwendung je Operationsfeld (§13) |
| `parameter_binding.py` | Feste Zahlen, die zu Projektmaßen passen, und ihre Bindung (`projektmasse.md`) |
| `cancel.py` | Kooperativer Abbruch (§15.6, §2.8) |
| `fits.py` | Passungen (§14), nie still gerechnet; `fit_kinds_for`: Passungsarten, `allowances_for`: Ausgleich im Modell, je Körper (Druckdialog, Export je Teil) |
| `orphans.py` | Verweise ohne Merkmal (§21.3): `question_for()`, `candidates_of()`, `lineage()` |
| `placement.py` | Dialogvorbelegung und Oberflächenplatzierung am Originalnetz (§18.5); `seat_on_face`: ein Erzeuger auf gewählter Fläche, in ihrer Ebene über das Bett gehoben; `seat_of`: wo sitzt, was schon da ist; `prepare_tool()` liefert in `PlacementTool` den effektiven Werkzeugwinkel und die Kernachse für die Vorschau; Altwinkel, migrierte Richtungen und Nullnormalen: Begründungen, „Platzierung“ |
| `ops.py` | Umbenennen, Löschen, Duplizieren, Muster |
| `variants.py` | Der Variantengenerator (§28.3): `_marked` graviert den Wert ein, wo Material für drei Schichten plus Mindestwand steht (`label_ops.too_thin_to_print`), sonst `variants.no_mark`; fein, mit geteiltem Cache; ein Druckauftrag, kein Dokumentzustand (Regel 2) |

## Stolperfallen

### Auswertung

- **Flächenbindungen** löst `placement.bind_surface` vor dem Verbrauchercache
  aus dem aktuellen Träger, seinem gespeicherten Rahmen und den Bezugskanten
  auf. `surface_at_feature` misst an gekrümmten exakten Flächen Punkt und
  Normale über `brep.canonical.projected_surface_point`; die Auswahl bleibt
  an den Originaldreiecken. Diese bewusste Abhängigkeit auf den optionalen
  exakten Kern ist ausschließlich träge, ohne neuen eifrigen Importkreis.

- **Örtlich erkannte Muster** ersetzen ihre vollständig enthaltenen
  Einzelmerkmale auch nach dem Zusammenführen mit dem Vorgängerbestand.
  Deren frühere Kennungen bleiben reserviert; ein späterer Bezug auf eine
  Zelle wird nicht zum Bezug auf das ganze Muster.
- **Erzeugte Texturen** (auch `grouped`, `bound_to_its_surface`) werden in
  `_with_features` an ihre wirkliche Oberfläche gebunden.
  `_textures_from_other_inputs` übernimmt belegte Reste weiterer Eingänge
  (Vereinigung, Schnitt, Zerlegen loser Teile). Die Herkunft bleibt Teil der
  Kennung, damit das Entfernen einer anderen Textur keinen gespeicherten
  Folgebezug verschiebt. Ausdrücklich entfernte Texturen bindet keine
  Restfläche neu.
- **`SceneObject.frame`** trägt den dauerhaften Ausgangsrahmen als affine
  Matrix. Ohne Eingang beginnt er mit `IDENTITY_FRAME`; eindeutige Vorfahren
  und `dataclasses.replace` führen ihn fort, `moved_object` bildet ihn mit
  derselben Matrix wie die Geometrie ab. Maßstab und Spiegelung bleiben darin
  sichtbar; `None` bleibt unbekannt. Boolesche beziehen sich ausdrücklich auf
  den ersten gespeicherten Eingang. Cache und `object_hash` tragen den Rahmen;
  Altprojekte rekonstruieren ihn allein aus ihrem Operationsstack.

- **`_with_features`** bindet nach jedem Ausgabeübergang, auch am Cachetreffer,
  die Merkmale ans neue Netz; ohne Erkennung bleibt die Ausgabe, ohne Zuordnung
  und Waisenbefund. Die Bewegung je Ausgabe sagt `_motion_of`: die gemeldete,
  sonst der belegte Bewegungsvermerk am Netz (`perceive.features.moved_from`)
  mit seinem Eingang, dem eigenen, wo es ihn gibt; die Vorschau überträgt nur,
  was ein Folgeschritt liest — so gehen Ausrichten, Anordnen und Musterkopien über
  mehrere Körper denselben Weg wie ein einzelnes Verschieben. Belege am exakten Körper (Regel in `operationen.md`):
  `_needed_after`, `_checked_continuations`, `_unchanged_continuations`,
  `_unproven_native_references`, `blocked_references` →
  `orphans.check(blocked=)`; ausgestellt von `_preserved_exact_features` und
  `prepare_ops._exact_features_after`. Jeder neu bauende Schritt
  bewahrt eindeutig zugeordnete, geometrisch unveränderte Vorgänger unter ihrer
  bisherigen Kennung, wenn beide Merkmalsmengen höchstens
  `FEATURE_LIMIT_COUNT` Einträge enthalten — auch ohne bekannten Folgebezug;
  Unbelegte alte Namen bleiben reserviert, damit ein späterer Verbraucher
  weder die Vergabe ändert noch ein neues Merkmal eine alte Kennung übernimmt.
  Eine von der Operation belegte `FeatureContinuation` wird nach dem allgemeinen
  Matcher erzwungen und hält auch absichtlich geänderte Merkmale unter ihrer
  Kennung. Beim Umbenennen unveränderter Nachbarn und nach einer ausdrücklichen
  Neuwahl nimmt `_native_alias_mapping` alle bereits gleichnamig belegten
  Merkmale in die Teilzuordnung mit, damit neue Merkmale deren Namen nicht
  zuerst beanspruchen. Andere offene Zuordnungen bleiben unbelegt.
  Unbelegtes wählt der Kunde
  (`_native_reselection`): Die neu zu wählenden Namen verlassen vorher die
  Zuordnung, ihr geometrischer Nachfolger steht als erste Antwort da; eine
  `group:`-Antwort gibt native Konkurrenz nie frei.
- **Kanten** bindet `_evaluate` vor `cache.get` am ersten Eingang im Kern der
  Operation (`edges_in_kernel`, `edges_on_mesh`), fragt mit `EdgeTarget`; der
  Fingerabdruck (`edge_fingerprint`) geht in den Schlüssel, die Antwort erst
  nach dem gelungenen Schritt in `edge-answer:`, ein eindeutiger Schlüssel als
  Parameter (`EvaluationResult.answers`); eine Gruppenauswahl bindet nichts.
- **`Operation.matches`** hält vollständige Antwortgruppen je Ausgabekörper
  (`group:`, `native-group:` mit rohem Erzeugerschlüssel plus Ausgabeindex,
  `edge-answer:`, `recognition-answer:`); Schema `perceive.match_records`,
  Kandidatennummern lokal, Nichtfortführung ausdrücklich, Altes unter `legacy`
  — die Migration erfindet keine Lage. Ohne jemanden zum Fragen trägt der Halt
  `choose:`-Vorschläge.
- **Kein halbes Ergebnis**: `matching.match` und `resolve` bekommen den Abbruch
  (`check_cancelled`); er veröffentlicht nichts und erzeugt kein Token.
  `question_context` zeigt der Frage eine vergängliche Vorschau; Antworten
  erscheinen erst nach allen Ausgaben, neue Ausgaben erben keinen Hash; native
  Konkurrenz um einen Verweis hält vorher an, Netzgruppen benennen keine native
  Topologie um. Jede Ausgabe wird samt Zuordnung und Hash vorbereitet, bevor
  Eingänge verbraucht werden; Cache und Fertigmeldung erst nach der letzten
  Abschlussprüfung, außer dem Urteil der vollen Kette (`_FullChain`, `kern.md`).
- **Die Frage vor der Vollerkennung** (Regel in `kern.md`):
  `_full_recognition_allowed`, `_ask_once_for_large_bodies`,
  `_recognition_choice`, `_skipped_recognition` (`perceive.too_large`),
  `_WatchedAsk.optional`, `recognition_of`, `_remeasured`; nach dem rohen
  Cache, vor der Erkennung; eine Absage schreibt nichts in den Merker. Über
  `FEATURE_LIMIT_TRIANGLES` misst `_measured_locally` bekannte Merkmale nach
  (unverändert, starr bewegt oder fein geteilt nicht). `recognition_left_out`
  nennt, was noch unerkannt ist.
- **Eine geteilte Fläche ist nicht verloren** (`_divided_in_place`, an
  `source_mesh`, sonst `origin_mesh`; `REMOVAL_CODES` zählen nicht) **und heißt
  am größten Stück weiter** (`_divided_partners`, nach *Teilen* in jeder
  Hälfte; gleich große sind `MatchResult.ambiguous`); alte Dreiecke nur, wenn
  sie diese Fläche sind (`matching.planar_source`, `pieces_in_place`); nach
  einer Bewegung wird nicht gesucht;
  eine beschnittene erzeugte Fläche ohne Stück fällt heraus
  (`perceive.generated_lost`), ebenso ein erzeugtes Merkmal, das dieser
  Schritt ganz aus dem Körper schnitt (`_cut_away_here`, `gone_here`).
- **Die Zuordnungsfrage** (`_answer_matches`) fragt Verwiesenes zuerst, auch
  ohne Nachfolger, Abbrechen beginnt die Gruppe neu; verwiesen heißt am Netz
  **nach** dem Schritt (`_needed_after`) — den eigenen Verweis löst der Schritt
  an seinem Eingang auf, eine Textur fragt nicht nach der Fläche, die sie
  ersetzt hat; Unverwiesenes ohne Wahl
  wird ohne Dialog nicht weitergeführt. `_WatchedAsk` macht aus einer
  geschlossenen Frage `QUESTION_LEFT_OPEN` mit *Eingabe korrigieren* und
  *Verlauf zeigen*.
- **Ein erklärtes Merkmal findet seinen Partner an seiner Stelle**
  (`declared_partners`, `near_its_declaration`: quer innerhalb der Breite,
  längs innerhalb der Tiefe; sonst 8 % der Diagonale) und gewinnt so gegen
  Konkurrenten; ein neues bekommt keinen Namen eines Mitreisenden
  (`apply_mapping(reserved=)`). `perceive.referenced_lost` zählt nur, wer
  **nach** dem Schritt zeigt.
- **Der Endstand**: `check_thin_walls` nimmt die Grenze je Körper aus
  `profiles.analysis_limits`; `check_form_deviation` meldet nur über
  `MAX_FACET_SAG`, Zahlen erst in der Karte. Lagebefunde eines Schritts fallen,
  wo `check_placement` sie am Endstand nicht bestätigt
  (`_without_undone_placements`), der Plattenrat mit ihnen.
  `_without_repeats` erhält unterschiedliche Merkmalziele, Orte und Konturen;
  identische Befunddaten bleiben zuletzt, in der bisherigen Berichtsfolge.
  Rohe Operationsbefunde bleiben unverändert,
  auch beim erneuten Abschluss aus dem Cache.
  `_without_outdated` zählt Material nur für `bore.splits_the_body` sowie
  `label.fell_apart`, `texture.fell_apart`, `parts.hanging_loose`,
  `blend.still_apart` und `sketch.join_apart`: nativ über `solid_count`, am
  Netz über `repair.material_part_count`. Innenhäute sind keine losen Teile;
  ohne vollständigen Beleg bleibt der Befund. Nur `values['count']` des
  Bohrungsbefunds wird bei mehreren Teilen frisch nachgeführt, bei einem
  entfällt der Befund.
  Die übrigen Zähler behalten `component_count`, mit getrennten Merkern je
  Objekt. Der echte Abbruchtoken erreicht auch den Schalenaufbau; erst nach
  dem Abschluss werden Bericht und Cache freigegeben. Der Bericht übernimmt
  Ersatzbefunde auch bei unveränderter Zeilenzahl.
  `_finding_from` übernimmt `location` und `outline` aus einer Ausnahme als
  räumliche Felder und lässt sie aus den Anzeigewerten heraus.
- **Darstellungswechsel** melden sich erst nach vollständig vorbereiteten
  Ausgaben; unveränderte Eingangskennungen belegen Nachfolger (ein neuer Deckel
  ist kein Verlust seines Trägers); ganz vernetzt bekommt jedes verbrauchte
  exakte Werkzeug einen Befund mit Kennung, Name, Ausgaben und Operation; ein
  Halt meldet keinen Erfolg.
- **Ein exakter Körper wird nicht neu erkannt**: `features_of` in der bauenden
  Operation; `transform.moved_object` rechnet Maße und Dreiecke mit,
  `_carried_along`/`_shift_between` führen geerbte nach. `features_of`
  nummeriert Bohrungen nach Lage — eine neue links nimmt der alten den Namen,
  ein späterer Verweis hält mit `NativeReferenceLost`, und `revise` schreibt
  nichts; am Netz folgt der Verweis seinem Merkmal.
- **Eingänge** gelten im Zustand direkt vor dem Schritt; Verlauf und Auswertung
  prüfen ihre Zahl am Register. Ein Programmfehler der Erkennung hält am
  Schritt. Alte Farbschritte mit Punkt und Radius halten an
  (`legacy_point_paint`), ihre Felder sind keine Eingaben des Dialogs.
- **`parameter_usage`** hängt an jedem Ergebnis, ein Fehler getrennt in
  `parameter_usage_error` — `None` ist nie „ungenutzt"; Skizzen, Stellungen,
  Aufteilungen über `nested_references(strict=True)`, ihre Bezüge auch im Hash;
  Ketten ohne lesenden Schritt bleiben ungenutzt.

### Cache und Hashes

- **Was eine Operation liest, steht im Schlüssel**: Profil jedes Eingangs mit
  eigenem Material (`_body_profiles`, mit Kalibrierung), jedes gelesene
  Drucker- und Materialfeld (`profile_key`), `material_params`,
  `OperationSpec.cache_version` (der geladene Stand), `CACHE_FORMAT_VERSION`
  (Stand der Erkennung, kein Projektformat). Beschädigtes wird neu gerechnet
  (`_DAMAGED_ENTRY`). Die übrigen Körper unter `#scene` mischt
  `_with_nested_context` für `OperationSpec.reads_other_bodies` immer ein, für
  einen Schalter mit `ParamSpec.reads_scene` nur, solange er an ist und seine
  Antwortfelder (`answered_by`) leer sind (`registry.params.reads_scene`).
  Die Antworten reisen mit dem Eintrag (`CachedResult.answered`, auch auf der
  Platte): Ein Treffer gibt sie weiter wie ein frischer Lauf.
- **Prozesswerte nur im Schlüssel eines Schritts, der sie liest**: Schichthöhe,
  Bahnbreite, Stützschwelle und was aus ihnen folgt (`hashing._profile_parts`)
  setzt der Druckdialog. **Die Vorgabe liest** (`OperationSpec.reads_process`),
  denn ein falscher Treffer liefert veraltete Geometrie; `False` nur mit Beleg
  über die Operation und alles, was sie aufruft, eingetragen in
  `_STEPS_WITHOUT_PROCESS` (`tests/test_cache.py`), das jede davon an einem
  wachenden Profil laufen lässt. Wer einer freigestellten Operation einen
  Prozesswert zu lesen gibt, nimmt `False` heraus. Der volle `profile_key`
  bleibt bytegleich — er benennt auch Filamentbuchungen.
- **Merkmale reisen typgenau durch beide Ebenen** (`_stored_feature_to_data`;
  `feature_to_data` ist der Folgehash): Maßquellen und `surface_patches`
  (Vertrag geprüft, im Speicherbudget; ein alter Name ohne Beleg behält keinen
  Formnachweis). Die Erkennung je Netz ist ein eigener Eintrag
  (`load_detection`). **Nicht geprüft wird die Dreieckszahl**: Der Cache
  trägt die **rohe** Ausgabe; erst `_with_features` bindet, Vorbereitetes
  cacht er nie. `_warm_figures` fasst Kennzahlen im Arbeiter an. Exakte
  Körper bleiben im Speicher, neue Träger rechnen neu;
  Teilungsvermerke (`_refinement_to_disk`) und mitgetragene Maße
  (`_carried_to_disk`) neben dem Netz, Bewegungsvermerke im Eintrag; belegt
  erst die Erkennung am Eingang.
- **`object_hash(features=)`** bindet die veröffentlichten Merkmale
  (`feature_digest`: Nummern als `int64`, Zahlen über `float()`;
  `FeatureMemo`); gleiche reservierte Namen beweisen keine gleiche Bindung; der
  rohe `operation_hash` bleibt frei von Antworten.
- **Muster** bewegen Kopien über `transform.moved_object` (Körperart und
  Flächenzuordnung bleiben); nur ein unverändert geerbtes Merkmal folgt der
  Matrix (`_inherited_features` vergleicht alle Felder), über dem
  Merkmalsbudget kehren keine alten Maße zurück.

### Verlauf

- **`record_matches`** ersetzt ganze Einträge als Kopie; vor Undo/Redo sichert
  die verlassene Seite ihre Antworten nur bei gleicher Fassung (Name, Ein- und
  Ausgänge, Parameter, Startwert, Übersetzungsmarke); nichts wird umbenannt
  oder auf neue Körper übertragen.
- **`History.apply`** führt lebende Kennungen je Schritt fort; ein im Bündel
  verbrauchter Eingang ist ungültig, die Absage ändert nichts.
  `bundling.stays_exact` beendet ein Bündel, das nicht mehr der Summe der
  Schritte entspräche (Fälle im Docstring).
- **Ein Startwert ohne Vorgabe folgt aus dem Entwurf** (`history._seed_of`:
  Operation, Eingänge, Werte), nie aus dem Zufall (RM-493).
- **Umbau** (Regel in `kern.md`): `plan_insert`, `plan_move`, `plan_suppress`,
  `plan_reactivate` → `RevisionPlan` → `revise` (`ReferenceSight`, `sights`,
  `fit_sights`; `verdict` fragt Herkunft, Abdruck, Lage) → `commit`. Neu
  gefasst ab der ersten Änderung (`_moved_order`, `_clone`, alte Kennungen als
  `None` in `edited_ops`); `valid_targets` nennt Gründe (`_order_problem`).
  `plan_insert(changed=)`: neue Werte späterer Schritte, eine Transaktion
  unter `title`; fremde Kennung oder `produces_from` → `InternalError`.
- **Ausgeschaltet** (`Operation.suppressed`): `history.step_off`,
  `step_resting`; `_absent_objects`, `_without_absent_inputs`,
  `needs_resting_step`, `fits.paused_fits`, `orphans.references` fragt nicht;
  mitgenommen wird, wessen Verweis sonst verlöre, sonst *Diesen Schritt mit
  ausschalten*; `_roots_of` holt zurück.
- **Erneut versuchen**: `repair_and_retry`, `split_and_retry`,
  `decimate_and_retry`, `remesh_and_retry`, alle über `_retried_after`.
  Löschtitel kommen aus dem Register der `History`, übersetzbar.

### Verweise

- **Passungsschlüssel** bleiben `fit:<Name>:a/b`; der freie Name darf selbst
  Doppelpunkte tragen. `orphans.fit_name_from_key` liest bis zum letzten
  Seitenmarker, auch für Abhängigkeiten und Ruhevermerke beim Umbau.
- **`kind="features"`**: jeder fehlende Verweis einzeln, auch nach einem
  Treffer; heißt leer „ganzer Körper", vergrößert „Verweis streichen" den
  Bereich nie; Abbrechen behält. Ausgeblendete Felder lösen sich nur aktiv auf
  (`_feature_fields` folgt `depends_on`).
- **Die Verweisfrage nennt, wer fragt** (Passung beim Namen, Schritt beim
  Registertitel; `question_for`, `removal_choice`) und streicht nur auf
  ausdrücklichen Wunsch; jede andere Antwort, auch `QuestionDeclined`, lässt
  den Verweis stehen, der Befund trägt den Weg (`_way_forward`). Eine Skizze
  auf abgeleiteter Ebene behält ihre Ableitung (`_on_another_face`). Eine
  Körpervorbelegung entfernt nur selbst abgeleitete Verweise; ausdrücklich
  Gewähltes geht vor, aus einer Körperwahl wird keine Flächenwahl.
- **`pending_references()`** nennt den anstehenden Schritt, ohne Verbrauchtes
  und später Erzeugtes; Passungen prüft erst das vollständige Ergebnis.

### Passungen

- **Ein Vertrag** für `pair_problem`, `pair_kinds` und Prüfung: Gewinde
  brauchen bekannte gleiche `handedness`, Rolle und Steigung — fehlend heißt
  „nicht gemessen", verschieden ein Befund mit Rückweg; Steigungen sind auf
  ihre Unsicherheit gleich (`_pitch_uncertainty`), nie auf `EPS_GEOM`.
  Durchmesser belegen keine Rolle (`fit_role`, `internal`); alte radiale
  Passungen an Gewinden bleiben radial.
- **Radiale Netzmaße** tragen `radial_min`/`radial_max`; unbelegtes Spiel ist
  `fit.mesh_uncertain`, nie ein Kollisionsnachweis; Presspassungen dürfen
  überdecken, Spielpassungen melden mögliche Überdeckung auch unter der
  Anzeigeauflösung. Die Grenzen ersetzen weder Spiel noch Einbauprüfung.
- **`fits.check(cancelled=)`** prüft Körper nur in belegter Lage
  (`_pose_proven`; sonst `overlap` → `None`, kein Befund): Netze direkt, native
  auf privaten Kopien, keine Längentoleranz als Volumengrenze;
  `fit.geometry_approximate`, `fit.geometry_failed` (nie Freiheit),
  `fit.press_unverified`, `fit.collision`. Kollisionsfreiheit gilt nur der
  Lage. `flush` hält seine Ebenenregel (normierte Normalen), daneben dieselbe
  Körperprobe.
- **Bedingte Passungen** (`when_positive`, `active_fits`: nur gültige Werte ≤ 0
  schalten ab) bleiben im Dokument; ein fehlender Schritt ist ein Befund, eine
  fehlende Dokumentangabe ein Programmfehler; ein Umbau trägt die Bedingung in
  derselben `DocumentChange` mit. Migration 19→20 legt Deckelpaare über
  `lid_flow.fit_for_lid` an, nie entfernte neu.

### Platzierung

- **`seat_of`**: Die Normale zeigt vom Hohlraum weg, ein Sacklochboden trägt
  nicht; nur die eigene Öffnung wird gefüllt; Fase und `mouth_on`: Regel in
  `operationen.md`. `prepare_tool` zeigt bei Länge = Breite die runde Bohrung;
  `mouth_outline` nimmt die Hülle der Mündungspunkte (§21.1). `resize_hole`
  behält am Langloch Weg und Richtung; bei `slot_hole` folgt die Vorschau der
  Zielbreite, ohne zweiten Zuschlag.
- **Bezüge sind vergänglich** und gehören einer `PreparedSurface`
  (`with_reference`, `at_point(references=)`): Außenkanten vor inneren, belegte
  Langlochrichtungen und Mitten zählen, Kreiskonturen geben keine Geraden;
  `MAX_REFERENCE_CONDITION` ist eine Bediengrenze. Gespeichert werden Werte,
  keine `edge_0`-Bindung (§13, §18.11). Der Trimesh-Cache für exakte
  Originalkanten beschleunigt nur; ohne ihn gilt dieselbe Rechnung.
- **`original_surface_hit`** prüft blockweise und abbrechbar, beachtet alle
  Schnittebenen, behält die Kennung.
- **`bore_step_of`/`seat_for_bore_step`** binden eine Bohrung an ihren
  `drill_hole`-Schritt (Verträge im Docstring); `_feature_originators` stempelt
  beide Kerne, `inherit_originators` erbt, Importe bekommen keinen geratenen
  Ursprung; `DRILL_OPERATIONS` bindet beide Zwillinge an dieselbe Platzierung.
  `prepare_tool` reicht aufgelöste Maße an Skizzenbausteine.

### Projektdatei

- **Revisionsherkunft**: `Transaction.renumbered` hält die belegte Zuordnung
  alter zu neuer Schrittkennung bei Einfügen, Verschieben und den Wegen „… und
  erneut versuchen“ (`revision="insert"`, RM-547). Sichtbare Titel folgen dieser
  Herkunft; Positionsnummern bleiben reine Anzeige. Alte Dateien ohne Zuordnung
  werden nicht durch Parametergleichheit verbunden; ihre erneuten Versuche
  erkennt `types.replanned_steps` an der Gestalt.

- **Spulen** (`PrintSettings`): Filamentidentität und lokale Kennung, nie
  Pfade, Namensvorlagen übersetzbar und vor dem Lesen geprüft; die Migration
  rät keine Spule; `DocumentState.spool_bindings` (`None` unbeteiligt, leer
  entfernt) geht mit derselben Transaktion zurück. `slot_profile_bindings`:
  `None` ist der alte Positionsvertrag, gebunden an der ursprünglichen Szene,
  leer ausdrücklich keine Wahl; doppelte Identitäten und Pfade werden
  abgewiesen, ein Name wie `PLA/PETG` öffnet keine Datei.
- **Verknüpfte Quellen**: unerreichbar hindert weder Speichern noch Öffnen, der
  Abdruck bleibt; Rechnen verlangt die Prüfsumme; fremder Inhalt, Größe oder
  ein Pfad außerhalb des Projektordners werden abgewiesen.
- **Nachbau**: Dokumentkopien prüfen Kandidaten (Grundkörper, Stützebenen,
  Stufen `_without_holes`, Profilkörper `_prismatic` mit Quertaschen
  `_cross_pockets`) am Original; unbekannte Flächen sperren nach bestandener
  Formprüfung. `commit` vergleicht Stand und Quellen erneut (`SourceAccess`);
  Maße, Attribute und Passungsfolgen sind eine Transaktion.
- **Mitreisende Profile** (Regel in `dateiformat.md`): `save` erneuert sie
  (`MAX_CARRIED_PROFILES`), `profiles.carry`, `scene_profile`,
  `carried_findings`; alle Wege fragen dieselbe Rückfallfunktion.
- **Wiederherstellung**: Sitzungstoken und Betriebssystemsperre
  (`paths.lock_file()`, `_lock_recovery()`); lebende fremde bietet
  `unsaved_recoveries()` nicht an, Verwerfen löscht sie nicht, das Prozessende
  gibt sie frei.
