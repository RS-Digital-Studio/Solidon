---
name: anker-nach-dem-formatierer
description: "Ein Suchanker, der durch ruff format gelaufen ist, passt nicht mehr auf den gelesenen Text — die Ersetzung greift halb, und der Rest ist still falsch. Vor jedem Patch den Text neu lesen, den man ersetzen will."
metadata:
  type: feedback
---

Am 03.09.2026 zweimal in zwei Sitzungen, in verschiedenen Gestalten:

* Eine Umbenennung deutscher Bezeichner ersetzte den Schleifenkopf und **nicht
  den Rumpf**: Der Suchtext stammte aus der Datei vor `ruff format`, und der
  Formatierer hatte die Zeilen darin umgebrochen. Gefangen hat es `ruff` mit
  „Variable nicht benutzt" — nach einem abgebrochenen Commit.
* Bei 3d-druck-a0 verschluckte ein Bash-Heredoc die `\n` eines Patchskripts,
  und ein anderer Anker stand zweimal im Baum.

**Why:** Ein halb gegriffener Patch ist gefährlicher als einer, der gar nicht
greift. Er hinterlässt einen Zustand, den niemand geschrieben hat: hier einen
Schleifenkopf mit englischen Namen über einem Rumpf mit deutschen. Und er
meldet sich nicht — die Datei ist syntaktisch heil, der Test läuft, und erst
ein Wächter zwei Schritte später stolpert darüber.

**How to apply:** Den Text, den man ersetzen will, **unmittelbar vor dem
Patch** aus der Datei lesen — nicht aus dem Gedächtnis, nicht aus einer
früheren Ausgabe, und nie über einen Formatierer hinweg. Jede Ersetzung zählt
ihre Treffer und bricht ab, wenn es nicht genau einer ist
([[patchskript-schneidet-fremdes-weg]] ist die Schwester dieses Punktes). Wo
ein Anker aus mehreren Zeilen besteht, ist er nach jedem `ruff format`
verdächtig.

Und die Umkehrung, weil sie billig ist: Nach einem Patch, der Namen ändert,
einmal `ruff check` fahren. „Variable nicht benutzt" und „Name nicht
definiert" sind genau die Meldungen, die eine halb gegriffene Umbenennung
erzeugt.

Verwandt: [[deutscher-text-geht-nicht-durch-die-shell]] — dieselbe Familie,
eine Ebene tiefer.
