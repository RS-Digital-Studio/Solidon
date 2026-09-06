---
name: fremde-prozesskette-nach-abbruch
description: "Nach einem Prozessabbruch laufen eigene Testketten als Waisen weiter — aber die Elternkette taugt nicht mehr zur Zuordnung, und ein Kill trifft die falsche Sitzung."
metadata:
  type: feedback
  originSessionId: 604362f2-7546-4f58-8ac6-a717d093adc0
  modified: 2026-09-06T07:37:57.114Z
---

Am 06.09.2026 stürzte meine Sitzung mitten in einem Suite-Lauf im Worktree
ab. Die Kette `run.sh → suite-getrennt.sh → pytest` lief als Waise weiter
(das Log wuchs noch 40 Minuten). Beim Aufräumen habe ich die Zuordnung „meins
oder fremd" über die Elternkette entschieden: Alles, was nicht Nachkomme des
fremden `gate_lock.py run --who 3d-druck-1e` war, galt als meins. Damit habe
ich einen pytest-Prozess **der anderen Sitzung** (test_sketch_editor.py)
beendet — ihr Torlauf wurde an dieser Datei rot, ohne dass der Code es war.

**Why:** Unter Windows bleibt `ParentProcessId` als Zahl stehen, wenn das
Elternteil stirbt; `bash -c` und `exec`-Ketten lassen Zwischenglieder früh
enden. Eine Kette, in der ein Glied fehlt, sieht in jeder Baumsuche aus wie
eine Waise — auch die des Nachbarn. Und die eigene Zuordnung (Datei X
gehört zu meinem Log) war prüfbar: Mein Log stand bei `test_interface_limits`,
die andere Suite lag alphabetisch längst bei `test_sculpt_session`.

**How to apply:** Fremde Testprozesse nie über die Elternkette töten. Meins
ist, was nachweislich in *meine* Ausgabedatei schreibt (Dateiname im
Kommandozeilenargument, `$OUT`, Reihenfolge der Testdateien im eigenen Log).
Im Zweifel den Rest seine Datei zu Ende laufen lassen — er startet ohne
Eltern keine nächste — und stattdessen der anderen Sitzung sofort sagen,
welche Datei sie neu fahren muss. Vor jedem Suite-Start je Lauf einen
eigenen Ordner mit Marker ([[gekillter-lauf-schreibt-weiter]],
[[abgebrochener-lauf-hinterlaesst-waisen]]).
