# `app/core/scene/` — Dokument, Stapel, Auswertung

Was gerade offen ist und wie daraus Geometrie wird (§12–§16).

Regeln: `.claude/rules/operationen.md`, für die Projektdatei zusätzlich
`.claude/rules/dateiformat.md`.

`placement.seat_of` prüft beide Mündungen einer erkannten Bohrung. Bei
Bohrung und Langloch muss die Flächennormale vom Hohlraum weg zeigen; der
Sacklochboden ist deshalb keine Trägerfläche. `mouth_outline` gewinnt den
Werkzeugumriss aus der konvexen Hülle der Mündungspunkte (§21.1).

Spulenbindungen in `PrintSettings` speichern die vollständige Druckfilament-
Identität und eine lokale Kennung, niemals Pfade. `slot_profiles` bleibt eine
Folge von Slicer-Profilnamen. Die Migration ergänzt leere Bindungen; sie rät
keine physische Spule aus alten Namen. Das gemeinsame Namensformat erhält
übersetzbare Vorlagen samt Werten und wird vor dem Deserialisieren geprüft.
`DocumentState.spool_bindings` nimmt die physische Spulenwahl mit derselben
Transaktion wie die Filamentzuweisung zurück: `None` heißt unbeteiligt,
eine leere Folge entfernt die Bindungen. Andere Druckwerte und die stabile
Projektkennung bleiben erhalten. Datei- und Undo-Seiten benutzen dieselben
Serialisierungs- und Schemahelfer.

Herstellerprofile stehen in `PrintSettings.slot_profile_bindings` an derselben
vollständigen Filamentidentität. `None` erhält den alten Positionsvertrag,
eine leere Folge enthält ausdrücklich keine Zuordnung. Die Migration
ergänzt keine geratenen Identitäten; die Sitzung bindet alte Profilpositionen
an der ursprünglichen vollständigen Szene. Doppelte Identitäten und örtliche
Dateipfade werden vor dem Laden abgewiesen. Profilnamen dürfen Materialzusätze
wie `PLA/PETG` enthalten; daraus entsteht kein Dateizugriff.

Parameter mit `kind="features"` speichern eine Liste stabiler Merkmalkennungen.
Jeder fehlende Verweis wird einzeln aufgelöst, auch nach einem Cachetreffer.
Wenn eine leere Auswahl den ganzen Körper bedeutet, darf „Verweis streichen“
den Wirkungsbereich nicht vergrößern. Abbrechen erhält den fehlenden Verweis.
Eine Körpervorbelegung entfernt nur ihre selbst geometrisch abgeleiteten
Einzel- und Mehrfachverweise. Ausdrücklich gewählte Merkmale und nachträglich
übergebene Werte behalten Vorrang; aus einer Körperwahl wird keine Flächenwahl.

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

Auch beim nachträglichen Ändern von Operationseingängen gilt der Zustand
unmittelbar vor diesem Schritt: bereits verbrauchte und erst später erzeugte
Objekte sind keine zulässigen Eingänge. Verlauf und Auswertung prüfen dieselbe
Eingangsanzahl aus dem Register, bevor Geometrie gerechnet wird.

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

**Drei Fragen beantwortet erst der Endstand**, und deshalb stehen sie in
`evaluate.py` und in keiner Operation: `check_placement` (liegt der Körper auf
dem Bett), `check_bodies_in_one_place` (zwei Körper am selben Ort) und
`check_thin_walls` (was von der Wand übrig ist, RM-127). Ihnen allen ist
dasselbe gemeinsam: Die Antwort hängt an einem **Verhältnis**, das ein
späterer Schritt noch umdreht. Eine Wand steht in keinem Merkmal — sie
entsteht zwischen einer Bohrung und dem Mantel um sie herum
(`perceive.relations.thinnest_sleeve` — dieselbe Regel wie `sleeve_at`, aber
in einem Durchgang über den ganzen Körper statt einem je Merkmal), und wer
aufbohrt und danach außen wächst, hat am Ende eine gute. Die Grenze kommt je
Körper aus `profiles.analysis_limits`: Körpermaterial und tatsächlich benutzte
Spulen bestimmen die Mindestwand samt ihrer Kalibrierung. Unbekannte Materialien
übernehmen keine fremde Kalibrierung (Regel 7); ohne Profil gibt es keine Aussage.
Gemeldet wird je Körper einmal,
die dünnste Stelle, mit beiden Merkmalen und dem Ort der Bohrung — damit der
Klick im Prüfbericht irgendwohin führt (§2.7).

Die Warnungen **in** den Operationen bleiben, wo sie stehen: `hollow` spricht
über den Wert, den jemand eingetragen hat, und der bleibt wahr, gleich was
danach kommt.

**Bedeutung über der Geometrie**

| Datei | Rolle |
|---|---|
| `fits.py` | Passungen zwischen Merkmalen (§14) — Verletzungen werden erkannt, nicht stillschweigend gerechnet |
| `orphans.py` | Merkmalsverweise, die ihr Merkmal verloren haben (§21.3). Statt zu raten: `question_for()` und `candidates_of()`. **Die Kandidaten folgen der Objektidentität durch den Stapel** (`lineage()`, RM-023): Nach einer Zerlegung trägt nur das erste Stück die alte Kennung, und der Verweis findet sein Merkmal am abgetrennten Körper wieder — aber nur dort, nicht an jedem fremden mit demselben Namen |
| `placement.py` | Dialogvorbelegung und genaue Oberflächenplatzierung am Originalnetz (§18.5). `seat_of` beantwortet die Frage daneben: **wo sitzt, was schon da ist** — die Trägerfläche eines erkannten Merkmals samt seiner Mündung, für die Maßlinien am gewählten Merkmal |

**Operationen dieses Gebiets**

`ops.py` (Umbenennen, Löschen, Duplizieren, Muster) · `variants.py` (der
Variantengenerator, §28.3)

Der Variantengenerator **graviert jedem Teil seinen Wert in die Oberseite**
(`_marked`, RM-147) — eingelassen, mit der Größe aus dem Teil und der
Untergrenze aus der Düse (`label_ops.too_thin_to_print`). Der Objektname trägt
ihn nur in der Szene, und die ist zu, sobald die Teile vom Bett kommen; wo kein
Platz dafür ist, steht `variants.no_mark` im Bericht statt einer Zahl, die
niemand lesen kann. Dass hier Geometrie außerhalb einer Operation entsteht, ist
dieselbe Ausnahme wie beim Anordnen daneben: Was zurückkommt, ist ein
Druckauftrag und kein Dokumentzustand (Regel 2).

Unter der gesamten Schrift prüft `_marked` den Materialraum bis zur
Gravurtiefe plus Mindestwandstärke des Profils. Fehlt dort Material, bleibt
das Teil mit `variants.no_mark` unverändert. Die Gesamthöhe allein reicht
nicht: Auch ein hoher Hohlkörper kann eine dünne Decke haben.

`History.apply` führt während der Planung die lebenden Objektkennungen nach
jedem Schritt fort. Ein im selben Bündel verbrauchter Eingang ist für den
nächsten Schritt ungültig; die Ablehnung lässt das Dokument unverändert.
Die Auswertung bereitet alle Ausgabeobjekte einschließlich Merkmalszuordnung,
Hashes und Namen vor, bevor sie Eingänge verbraucht. Eine angehaltene
Zuordnung liefert dadurch den letzten vollständig gerechneten Szenenzustand.

`OperationSpec.cache_version` bezeichnet den implementierten Bausteinstand.
Der Operationshash enthält diesen Wert zusätzlich zu Parametern und
Eingängen. Ein ersetztes Rezept entwertet dadurch auch bereits vorhandene
Ergebnisse im Speicher- und Dateicache. Die Version beschreibt den geladenen
Code beziehungsweise die registrierten Rezeptdaten, nicht eine inzwischen
anderweitig geänderte Datei.

Lineare und kreisförmige Muster bewegen Kopien über `moved_body`. Eine starre
Bewegung erhält einen exakten Körper; die Kopie bleibt anschließend im
B-Rep-Kern bearbeitbar.

## Grenzen

Was hier einzuhalten ist, steht in `.claude/rules/operationen.md` unter
„Szene: Platzierung, Kennungen, Cache, Projektdatei“ — die Karte nennt nur,
wo es eingelöst wird: `placement.py` (Oberflächenplatzierung, Sichtstrahl,
geteilte Werkzeuggeometrie), `evaluate.py` (reservierte Merkmalskennungen,
Objektzahländerung, `OpContext.scene` nur lesend), `cache.py` (versionierte
geometrische Auskünfte), `history.py` (`repair_and_retry` — Reparieren und
erneut versuchen — und `split_and_retry` daneben, dasselbe Muster mit *In
Einzelteile zerlegen* statt der Reparatur, beide über `_retried_after`),
`project.py` und `migrations.py` (keine absoluten Pfade, kein Code, die
fünf Schritte eines Formatwechsels). Die Dreiecksgrenze der
Merkmalerkennung, `FEATURE_LIMIT_TRIANGLES`, liegt in `perceive/`.

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
