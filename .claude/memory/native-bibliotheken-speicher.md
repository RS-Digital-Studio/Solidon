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
Instabilitätsproblem), MSI MPG Z690 CARBON WIFI, 2×32 GB DDR5 auf 4800 MHz,
zwei unerwartete Neustarts in dreißig Tagen, keine WHEA-Einträge, nie eine
Speicherdiagnose gelaufen. Microcode im August 0x12F, am 27.09.2026 **0x133**
(BIOS 1.O0 vom 01.04.2026) — die Fehler bleiben. Das passt zu Intels Aussage:
Die Microcode-Stände verhindern weitere Schädigung, eine bereits geschädigte
CPU reparieren sie nicht; dafür gibt es die um zwei auf fünf Jahre
verlängerte Garantie der 13. und 14. Generation.

**Wann sie falsch rechnet, gemessen am 27.09.2026** (Einzelheiten in
[[ast-walk-reisst-im-torlauf]]): in Fenstern **niedriger Gesamtlast**, wenn
ein einzelner rechnender Prozess auf einem der beiden bevorzugten P-Kerne
läuft (logisch 8–11, Scheduling-Klasse 2) und die mit 184–188 % des
Nenntakts takten. Unter Volllast (Takt 167–175 %) fiel dort nichts. Dieselbe
Nachstellung aus reiner Standardbibliothek stürzte unter Python 3.14.7
**und 3.13.14** ab — weder Solidon noch eine native Bibliothek noch eine
CPython-Version ist nötig. Auf die übrigen P-Kerne gepinnt (Maske `F0FF`)
blieben Nachstellung und Sprachprüfung in denselben Zeiträumen 0 von 204
rot, frei geplant oder auf die bevorzugten Kerne gepinnt 22 von 384. Die
Ereignisanzeige trägt passende Spuren: `STATUS_ILLEGAL_INSTRUCTION`
(`c000001d`) mitten in OpenBLAS (23.09.2026) und eine Zugriffsverletzung mit
einer Heapadresse als Befehlszeiger (24.09.2026).

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
- Offen, Roberts Entscheidung: Austausch über Intels Garantie, bis dahin im
  BIOS die Intel Default Settings. Solange die CPU bleibt, entstehen
  Release-Pakete auf dieser Maschine mit dem Risiko eines stillen
  Rechenfehlers — doppelt bauen und vergleichen oder in der CI bauen.

Siehe [[rtree-abstuerze-im-langen-lauf]], das denselben Cluster von außen
beschreibt, und [[leistungstests-fremdlast]] für die andere Sorte
Fehlzuschreibung.

## „Diesmal ging es durch" ist keine Eigenschaft — und ein Abriss verschluckt still

Am 04.09.2026 riss `test_ui.py` am Stück nach 188 von 448 Tests ab, Exit 139,
**ohne eine einzige FAILED-Zeile**. Portioniert zu 70 lief dieselbe Datei
komplett durch: 448 grün, jede Portion Exit 0. Ich habe daraus „portioniert
kein Abriss" gemacht — und eine halbe Stunde später riss derselbe portionierte
Aufruf in Teil 3 nach 39 von 70 ab.

**Ein sauberer Lauf ist eine Beobachtung, keine Eigenschaft.** Bei einer
lastabhängigen Ursache sagt er nur, dass die Last diesmal reichte. Dieselbe
Form wie [[schranke-aus-einem-messwert-ist-geraten]], nur in der negativen
Richtung: nicht „der Wert ist so groß", sondern „das Problem gibt es nicht".

**Gefährlicher ist die stille Hälfte.** `Exit 139, rot=0` sieht beim
Überfliegen aus wie ein Erfolg, und die verschluckten Tests fehlen ohne
Meldung — beim ersten Mal 260 von 448, beim zweiten 31 von 70. Wer nur auf
FAILED-Zeilen sieht, liest einen grünen Lauf, der zu 42 Prozent stattgefunden
hat.

**Die Gegenmaßnahme ist eine Zahl, nicht ein Blick** — und sie ist gebaut:
`suite-getrennt.sh` portioniert jede Fensterdatei über 60 Tests von selbst,
vergleicht je Portion **gesammelt gegen gelaufen** (`nicht_gelaufen`), trennt
den Abriss beim Abbau vom echten Fehlschlag (`zaehlt_als_fehler`) und
**halbiert eine Portion, die Tests verschluckt hat, bis hinunter zu vier**,
statt sie als Befund liegenzulassen.

**Wer das nachbaut, baut schlechter.** Ich habe es am 04.09.2026 getan und es
erst gemerkt, als 3d-druck-81 das vorhandene Skript las statt es nur zu
benutzen. Zwei Fallen kennt `fortschritt()` dort, die mein Nachbau nicht
hatte: `Fatal Python error` steuert ein `F` bei, das als roter Test gelesen
wird, und `Extension modules:` ein `Ex`. Meine Protokolle enthielten beides
zufällig nicht — meine Zahlen stimmten also aus Glück, nicht aus Bauart.

Der Fehler war **`test_ui.py` einzeln am Stück zu fahren**. Über
`suite-getrennt.sh` passiert das nicht; der 34-Minuten-Lauf und der Abriss nach
188 kamen beide daher.

Was vom Nachbau bleibt, ist die Handregel für den Fall, dass man doch einmal
selbst zählt: nur **reine** Fortschrittszeilen nehmen — „8 passed in 1.59s"
bringt drei `s` und einen Punkt mit und macht aus acht Tests zwölf — und den
Zähler an einem Protokoll mit bekanntem Ausgang prüfen, nicht an sich selbst
([[messwerkzeug-misst-sich-selbst]]).
