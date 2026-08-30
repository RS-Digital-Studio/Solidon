# `app/core/scene/` — Dokument, Stapel, Auswertung

Was gerade offen ist und wie daraus Geometrie wird (§12–§16).

Regeln: `.claude/rules/operationen.md`, für die Projektdatei zusätzlich
`.claude/rules/dateiformat.md`.

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
| `placement.py` | Was ein angeklicktes Merkmal für die Parameter bedeutet (§18.5) — daher kommt die Dialogvorbelegung |

**Operationen dieses Gebiets**

`ops.py` (Umbenennen, Löschen, Duplizieren, Muster) · `variants.py` (der
Variantengenerator, §28.3)

## Grenzen

- **`OpContext.scene` ist nur lesend** (Regel 3). Ops erzeugen Objekte, sie
  ändern keine.
- **Objektzahländerung hält die Auswertung an** statt sie zu verschlucken.
- **Keine absoluten Pfade** in der Projektdatei (Regel 12), **kein
  ausführbarer Code** darin (Regel 13).
- Format geändert? Dann alle fünf Schritte: Version, Migration,
  Beispieldatei, Test, alte Migrationen behalten.
