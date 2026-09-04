---
name: katalogschreiber-ueberschreibt-still
description: "katalog[quelle] = wert fragt nicht, ob dort schon etwas steht — eine gewählte Übersetzung verschwindet, ohne dass ein Lauf rot wird."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 880d8f7a-c07e-4b8f-b374-5bef80997d00
  modified: 2026-09-04T13:37:10.313Z
---

Am 04.09.2026 habe ich drei neue Katalogeinträge für die Senkung nachgezogen,
mit dem naheliegenden Muster:

```python
katalog[quelle] = wörter[sprache]
```

Zwei der fünf Sprachen hatten den Schlüssel „Senkung" schon: Französisch als
**Fraisure**, Portugiesisch als **Escareamento**. Beide wurden still durch
meine Fassung ersetzt (Fraisage, Escareado). `test_translations` blieb grün —
es prüft **Vollständigkeit**, nicht Veränderung.

Die vorgefundenen Wörter waren dabei die besseren („fraisage" ist das Fräsen,
„fraisure" die Senkung selbst), und darum geht es nicht einmal: Sie waren
gewählt. Ein Katalogeintrag, der sich still ändert, ist eine Änderung am Text
des Kunden, die niemand beschlossen hat.

**Why:** Ein Wörterbuch-Zuweisen unterscheidet nicht zwischen „neu" und
„ersetzt", und die Suite hat keinen Wächter dafür — sie kann keinen haben, denn
eine geänderte Übersetzung ist von einer verbesserten nicht zu unterscheiden.
Aufgefallen ist es nur, weil ich aus einem anderen Anlass den eigenen Commit
Zeile für Zeile durchgesehen habe.

**How to apply:** Zwei Griffe, und beide kosten Sekunden.

Im Skript eine Zusicherung, die abbricht:

```python
vorhanden = [quelle for quelle in NEU if quelle in katalog]
assert not vorhanden, f"{sprache}: stünde schon da — {vorhanden}"
```

Und danach die Zählung — **mit `HEAD`**, sonst vergleicht git gegen den
veralteten Index und meldet Löschungen, die längst committet sind:

```
git diff HEAD --numstat -- app/i18n/locales/*.json
```

Ein Katalogschreiber, der nur ergänzt hat, zeigt dort „N hinzu, **0**
gelöscht". Jede Zahl in der zweiten Spalte ist ein überschriebener Eintrag.

Der `--numstat`-Griff kommt von 3d-druck-11, die ihn nach meinem Hinweis
sofort an ihren eigenen Läufen gefahren hat; die `HEAD`-Ergänzung ist die
Antwort darauf, dass er in diesem Baum ohne sie lügt. Verwandt:
[[uebersetzung-neu-statt-flicken]], [[geteilter-index-haelt-alten-stand]].

**Und dieselbe Falle hat eine zweite Gestalt:** Wer die Datei über
`json.dumps(..., sort_keys=True)` neu schreibt, macht aus einem Einzeiler eine
Vollüberschreibung. Bei einer bereits sortierten Datei ist das folgenlos —
schreibt aber gleichzeitig jemand anders, gewinnt der Letzte mit seinem
Lesestand, und die fremde Zeile ist weg, ohne dass ein Diff sie je gezeigt
hätte.
