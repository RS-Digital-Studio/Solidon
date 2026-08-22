---
name: native-bibliotheken-speicher
description: "Sporadische rote Läufe kommen von der Maschine, nicht vom Code — erst wiederholen, dann urteilen, und nie zuerst im eigenen Diff suchen."
metadata: 
  node_type: memory
  type: project
  originSessionId: 493de4ef-2355-4029-9d86-1e68996c4909
  modified: 2026-08-13T01:08:23.426Z
---

Die sporadischen roten Läufe in diesem Projekt haben **eine** gemeinsame
Wurzel, und sie liegt nicht im Code: **diese Maschine rechnet gelegentlich
falsch.** Am 07.08.2026 Schritt für Schritt eingegrenzt, jede Variante im
eigenen Prozess:

| Aufbau | Ergebnis |
|---|---|
| fertige Zahlenfelder + Trimesh, `rtree` geladen | 30/30 |
| XML lesen + `np.array`, `rtree` geladen | 29/30 |
| dasselbe, **`rtree` gesperrt** | 27/30 |
| `np.array` über reine Zeichenketten, **ohne XML** | 39/40 |
| `np.fromiter` über Pythons `int()` | 57/60 |
| reine Gleitkommaarbeit über SIMD | 40/40 |
| reine Python-Arithmetik auf 32 Kernen | 72/72 |

**Alle Verdächtigen sind ausgeschlossen.** Nicht `rtree` (ohne es bleibt es
rot, mit ihm und fertigen Feldern grün — die erste Diagnose war falsch), nicht
der XML-Leser (`lxml` verhält sich gleich, ohne XML bleibt es rot), nicht
NumPys String-Parser (Pythons `int()` ist genauso betroffen), nicht
Speicherdruck (49 GB frei), nicht Versionsdrift (alles nach `constraints.txt`),
nicht eine beschädigte Installation (`--force-reinstall` ändert nichts).

Die Symptome: `OverflowError: int too big to convert`, `ValueError: invalid
literal for int() with base 10: '98968'` über eine gültige Zahl,
`SystemError: error return without exception set`, Zugriffsverletzungen — und
einmal **still eine falsche Summe**: 9.599.875.422 statt 9.599.880.000, ohne
jede Ausnahme.

Die Maschine: i9-13900K (Raptor Lake, die Familie mit dem bekannten
Instabilitätsproblem), Microcode 0x12F, 2×32 GB DDR5 auf 4800 MHz, zwei
unerwartete Neustarts in dreißig Tagen, keine WHEA-Einträge, nie eine
Speicherdiagnose gelaufen.

**Ein weiterer Fall, 13.08.2026** — diesmal *reproduzierbar*, was die Sache
nicht zu einem Codefehler macht:

```
pytest tests/test_slice.py tests/test_performance.py -q -p no:randomly
→ TypeError: cannot unpack non-iterable int object
  app/core/slice/analysis.py:377, in `for other, others in enumerate(inside)`
```

`inside` ist dort `list[list[int]]`, und `enumerate` kann darüber keine ints
liefern — die Zeile ist korrekt. Jede Datei **einzeln** ist grün, `test_slice`
plus **nur** der betroffene Performance-Test ebenfalls; rot wird es erst mit
der ganzen `test_performance.py` davor, also unter Last. Symptom derselben
Familie: nicht die Zeile ansehen, sondern die Kombination.

**Wie anwenden:**

- Ein einzelner roter Lauf von `test_real_models.py` oder `test_examples.py`
  sagt nichts — erst wiederholen, dann urteilen.
- **Nie zuerst im eigenen Diff suchen.** Keiner dieser Fehler kam aus eigenem
  Code, und die Suche dort hat einen halben Tag gekostet.
- Zwei Stellen tragen ein Pflaster: `app/core/geom/mesh.on_surface` (be6cbcb)
  und `app/core/export/threemf._numbers_from` (e12bd6b) wiederholen einmal und
  lassen den zweiten Fehlschlag durch. Gegen ein Symptom gebaut, nicht gegen
  die Ursache — und wenn die Maschine der Grund ist, ist das genau richtig.
- Offen: MemTest86 oder die Windows-Speicherdiagnose über Nacht.

Siehe [[rtree-abstuerze-im-langen-lauf]], das denselben Cluster von außen
beschreibt, und [[leistungstests-fremdlast]] für die andere Sorte
Fehlzuschreibung.
