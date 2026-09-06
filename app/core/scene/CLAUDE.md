# `app/core/scene/` — Dokument, Stapel, Auswertung

Was gerade offen ist und wie daraus Geometrie wird (§12–§16).

Regeln: `.claude/rules/operationen.md`, für die Projektdatei zusätzlich
`.claude/rules/dateiformat.md`.

## Der Kreislauf

Namenlose Wiederherstellungen besitzen eine Sitzungstoken-Kennung und eine
vom Betriebssystem gehaltene Eigentumssperre. Solange deren Sitzung lebt,
bietet `unsaved_recoveries()` sie anderen Sitzungen nicht an; auch allgemeines
Verwerfen löscht sie nicht. Der eigene Sitzungstoken erlaubt das Aufräumen.
Prozessende gibt die Sperre frei, auch wenn keine Aufräumfunktion mehr läuft.

Beim Prüfen verlorener Referenzen benennt `pending_references()` den gerade
anstehenden Schritt. Historisch bereits verbrauchte und erst später erzeugte
Merkmale gehören nicht zu dessen Rückfrage. Am vollständigen Ergebnis werden
die aktiven Passungen geprüft. Die UI kann das unvollständige Ergebnis als
Kandidatenvorschau zeigen, bevor sie nach einer Zuordnung fragt.

```
Project ──> History (Stapel aus Transaktionen)
                │
                ▼
           evaluate()  ── reine Funktion aus
                │         Stack + Quellen + Parametern + Profilen + Startwerten
                ▼
        EvaluationResult (Szene, Befunde, Kennzahlen)
```

**Die Auswertung ist eine reine Funktion** (§15.1). Zweimal ausgewertet ergibt
identisch — `tests/test_evaluation.py` erzwingt es. Deshalb darf nichts, was
das Ergebnis beeinflusst, nur in der Sitzung leben; eine Rückfrage-Antwort
kommt über `OpResult.answered` in den Stapel zurück, so wie es die
Rückfallstufe tut.

## Die Karte

**Das Dokument**

| Datei | Rolle |
|---|---|
| `project.py` | Der Container (§16.1): `save()`, `load()`, Autosave, Wiederherstellung, Prüfsumme |
| `serialise.py` | Dokument zu Daten und zurück — Parameter, Passungen, Quellen, Herkunft, Transaktionen, Chat |
| `migrations.py` | `FORMAT_VERSION` und die Kette `vN → vN+1`. **Ältere Migrationen werden nie zusammengefasst** |
| `gathered.py` | Große Sammelwerte wandern aus dem Stapel in den Container (§12) |
| `foreign.py` | Was eine fremde Projektdatei mitbringt, das nicht nur Geometrie ist (§32) |

**Stapel und Auswertung**

| Datei | Rolle |
|---|---|
| `history.py` | Stapel, Transaktionen, Undo (§15.4, §15.5). `OperationDraft` ist der Schritt, bevor er zählt |
| `bundling.py` | Welche Züge zu einem Schritt verschmelzen (§15.5) — **opt-in je Operation**: wer keine Kumulationsregel hat, bekommt einen eigenen Schritt |
| `evaluate.py` | Die Auswertung (§15.1) — 1 500 Zeilen, das Herz |
| `cache.py` | Ergebnis-Cache über dem Operations-Hash, im Speicher und auf der Platte |
| `hashing.py` | Stabile Hashes: `operation_hash()`, `object_hash()`, `profile_key()` |
| `cancel.py` | Kooperativer Abbruch (§15.6, §2.8) |

**Bedeutung über der Geometrie**

| Datei | Rolle |
|---|---|
| `fits.py` | Passungen zwischen Merkmalen (§14) — Verletzungen werden erkannt, nicht stillschweigend gerechnet |
| `orphans.py` | Merkmalsverweise, die ihr Merkmal verloren haben (§21.3). Statt zu raten: `question_for()` und `candidates_of()` |
| `placement.py` | Dialogvorbelegung und genaue Oberflächenplatzierung am Originalnetz (§18.5) |

**Operationen dieses Gebiets**

`ops.py` (Umbenennen, Löschen, Duplizieren, Muster) · `variants.py` (der
Variantengenerator, §28.3)

## Grenzen

- **Oberflächenplatzierung verändert kein Dokument.** `prepare_surface()`
  bestimmt die zusammenhängende Originalfläche und ihre Randtopologie einmal;
  der Worker hält den unveränderlichen Kontext je Netz und Patch im Cache.
  `at_point()`, `point_with_distances()` und `point_with_centre()` verwenden
  dieselbe Flächenprüfung einschließlich Aussparungen. Zwei geradlinige
  Bezugskanten müssen unabhängig sein; Triangulationsdiagonalen und belegte
  Kreisfacetten liefern keine scheinbaren linearen Maße. Auf gekrümmten
  Flächen bleiben Punkt und Normale nutzbar, aber keine ebenen Abstände.
  Mittelpunkt-Offsets zeigen von der Bohrungsmitte zum Ziel entlang U/V.
- **Ein Sichtstrahl wird am Originalnetz geprüft.** `original_surface_hit()`
  ersetzt unbekannte LOD-Zellen durch Originaldreiecke und berücksichtigt alle
  Schnittebenen. Ihre positive Seite entfällt; künstliche Kappen sind kein
  Platzierungsziel. Ergebnisse und freie Normalen bleiben Float64-Werte.
- **Werkzeugvorschau und Operation teilen die Geometrie.** `prepare_tool()`
  liefert einen unveränderlichen `PlacementTool` mit lokalem Körper und
  ausgewähltem Merkmalsversatz. `surface_values(..., prepared_tool=...)`
  berechnet daraus neue Koordinaten ohne weiteren Körperbau; dieser Kontext
  gehört zu genau den gewählten Eingaben. `placement_tool()` bleibt der
  kompatible reine Mesh-Zugriff. Mündung oder Basis liegt bei null. Nur der
  temporäre Anzeigeaktor erhält den `frame_of()`-Rahmen am Treffer. Winkel,
  Einsenkung und Schnittspiegelung stecken bereits im Werkzeug. Bausteine
  deklarieren ihre Richtungsfelder über `normal_fields()`, damit gleichnamige
  Rezeptmaße erhalten bleiben. Beim Merkmalsversetzen ist `source` zusammen
  mit `feature` Pflicht; vollständige Bohrketten bilden ein Werkzeug.

- **Vergebene Merkmalskennungen bleiben reserviert.** Die Auswertung führt
  `SceneObject.reserved_feature_ids` über Zwischenoperationen fort und
  verhindert eine neue Zuordnung gelöschter Namen. Cache und Objekthash
  tragen die sortierte Sammlung; ein Projekt rekonstruiert sie aus den Ops.
- **Der Ergebniscache versioniert geometrische Auskünfte.** Alte Einträge
  ohne den aktuellen Formatstand sind Fehltreffer. Auch Änderungen erzeugter
  Geometrie und Merkmalsmetadaten gehören zu dieser Kompatibilitätsgrenze.
  Ein exakter mitgeführter
  Innenraum zählt zum Speicherbudget und zur Objektidentität.

- **Die Merkmalerkennung nimmt bis zu eine Million Dreiecke je Körper an.**
  `FEATURE_LIMIT_TRIANGLES` begrenzt die Auswertung; Importhinweise und
  Generator-Reduktion lesen dieselbe Grenze. Karten, Darstellung und die
  höchstens tausend zuzuordnenden Merkmale haben eigene Leistungsbudgets.
  Eine Anhebung wird an echten feinen Netzen einschließlich der oberen
  Gegenprobe gemessen; die Geometrie wird für die Erkennung nicht reduziert.
- **`OpContext.scene` ist nur lesend** (Regel 3). Ops erzeugen Objekte, sie
  ändern keine.
- **Reparieren und erneut versuchen ersetzt den angehaltenen Suffix atomar.**
  Die Reparatur steht vor dem fehlerhaften Schritt; dieser und alle jüngeren
  Schritte werden mit neuen Kennungen neu geplant. Alte Fassungen liegen in
  `DocumentChange.before.edited_ops`, ihre Entfernung in `after.edited_ops`.
  Reparatur und neue Fassungen gehören zu einer Transaktion, damit ein Undo
  exakt den alten Suffix zurückholt. Die gemeinsame Zielprüfung in
  `repair_targets()` verlangt lebende Eingänge und schließt Operationen des
  exakten Kerns aus: Eine Netzreparatur würde ihre bearbeitbaren Flächen in
  feste Dreiecke umwandeln und den erneuten Versuch unbrauchbar machen.
- **Objektzahländerung hält die Auswertung an** statt sie zu verschlucken.
- **Keine absoluten Pfade** in der Projektdatei (Regel 12), **kein
  ausführbarer Code** darin (Regel 13).
- Format geändert? Dann alle fünf Schritte: Version, Migration,
  Beispieldatei, Test, alte Migrationen behalten.

Bedingte Passungen speichern `when_positive=(operation_id, parameter_name)`.
`fits.pair_problem` prüft die fachliche Eignung für die Auswertung und die
manuelle Anlage gemeinsam; `pair_kinds` bietet nur passende neue Beziehungen
an. Durchmesser allein belegen keine Innen-/Außenrolle. Deckelmerkmale tragen
dafür `fit_role` am Erzeuger; Gewinde tragen `internal` und eine positive
Steigung. Historische radiale Passungen an Gewinden bleiben radiale Prüfungen;
die Gewindepassung prüft zusätzlich die Steigung. Bündige Flächen werden mit
normalisierten Normalen auf Parallelität und Ebenenabstand geprüft.
`fits.active_fits(document)` liest das aktuelle Op-Feld einschließlich
Projektparameterausdrücken. Ausschließlich gültige Werte <= 0 deaktivieren
die Passung; fehlender Schritt oder ungültiger Ausdruck bleibt ein Befund.
Das Dokument behält auch inaktive Beziehungen für spätere Änderungen und Undo;
Auswertung und Slicer verwenden die aktuell aktiven Passungen.
Eine Neuplanung des Suffix überträgt die Bedingung mit der Alt-Neu-Zuordnung
der Schrittkennungen in derselben `DocumentChange`. Ausdrückliches Entfernen
des Bedingungsschritts entfernt seine gebundenen Beziehungen; Undo stellt
Schritte und Bedingungen gemeinsam wieder her. Unbekannte Verweise aus einer
Datei bleiben dagegen prüfbare Fehler und werden nicht still gelöscht.

Migration 19→20 rekonstruiert die gespeicherten Verlaufszustände über den
regulären Undo-Vertrag. Eindeutige alte Deckelpaare erhalten dort die jeweils
gültige Schrittkennung; belegte flache Deckel ohne jemals gespeicherte
Beziehung erhalten eine bedingte Passung aus `lid_flow.fit_for_lid`.
Ausdrücklich entfernte Passungen werden dadurch nicht neu angelegt.
