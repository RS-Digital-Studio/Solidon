---
name: datei-die-vor-dem-patch-modifiziert-war-geht-nur-als-blob
description: "Im geteilten Baum entscheidet der git status VOR meinem Patch, welche Datei direkt in den Commit darf — eine dort schon als M gelistete Datei geht nur als Blob aus HEAD plus meinen Hunks; sonst committe ich fremde Arbeit (280dbe51, 14.09.2026)"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 1ca7314c-d749-4b85-aac6-9da0d8f5da54
  modified: 2026-09-14T16:48:18.331Z
---

Am 14.09.2026 hat mein Commit 280dbe51 vier Dateien mit fremden ungestageten
Hunks mitgenommen (ops.py, operationen.md, konzept-einfache-bedienung,
test_operation_ui.py): Ich hatte `git status --short` **vor** dem Patch
gelesen, die vier standen dort als ` M`, und ich habe die Ausgabe als „meine
Änderungen" gelesen — obwohl ich die Dateien noch gar nicht angefasst hatte.
Danach war die Liste im Commit-Skript aus dem Gedächtnis geschrieben, nicht
aus dieser Messung.

**Why:** Der Hunk-Zähler nach dem Patch kann eigene und fremde Zeilen nicht
mehr trennen; die einzige Messung, die es kann, ist der Status **davor**. Wer
sie liest, aber nicht in die Commit-Liste übernimmt, hat nichts gemessen
([[messung-traegt-nur-am-ort-ihrer-messung]],
[[katalogschreiber-ueberschreibt-still]]).

**How to apply:** Erster Befehl jeder Einheit: `git status --short --
<alle Dateien, die ich anfassen werde>` in eine Datei; jede Zeile mit ` M`
kommt in die Blob-Liste des Commit-Skripts, nur unmodifizierte Dateien in
`git add`. Vor dem Commit noch einmal: `git diff HEAD --numstat` je
Direkt-Datei muss genau meine Hunks zählen. Nach dem Commit den geteilten
Index nur für die eigenen Pfade zurücksetzen (`git reset -q -- <meine>`),
weil er fremd gestagete Dateien tragen kann.

**Zweites Mal, 15.09.2026 (98bf029e):** Die Blobs waren sauber gebaut — aus
HEAD plus eigenen Hunks —, nur vier Dateien galten als „ganz eigen" und kamen
als Arbeitskopie hinein, gemessen an einem `numstat` von einer Stunde davor.
Dazwischen hatte die RM-172-Sitzung `actions.py` und `test_feature_panel.py`
angefasst; HEAD war danach halb (ihr Kern ungestaged, ihr Panel committet,
`test_translations` rot an ihrem Satz). Berichtigt in b0b7c61c. Die Lehre
verschärft: **Es gibt keine „ganz eigene" Datei im geteilten Baum** — jeder
Blob ist HEAD plus eigene Ersetzungen, und der Builder zählt `git diff
HEAD:<pfad> <blob>` gegen die erwarteten Zeilen, unmittelbar vor dem Commit.
Und `git apply --unidiff-zero` setzt kontextlose Hunks an ihre **neue** Zeile;
mit weggelassenen fremden Hunks landet der Code dreizehn Zeilen daneben —
Hunks selbst anwenden, über alte Zeile plus eigenen Versatz, mit Prüfung der
entfernten Zeilen (`scratchpad/commit/apply_hunks.py` dieser Sitzung).
