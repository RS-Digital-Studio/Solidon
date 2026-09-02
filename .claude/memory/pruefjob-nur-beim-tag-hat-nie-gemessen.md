---
name: pruefjob-nur-beim-tag-hat-nie-gemessen
description: "Ein Prüfschritt, der nur beim Release läuft, ist bis zum ersten Release eine Behauptung — die Releaseakte hätte 0.3.0 auf allen drei Plattformen abgewiesen, und niemand wusste es."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 979875fd-bfa8-4b06-9f26-64e50bc5303e
  modified: 2026-09-02T16:59:06.727Z
---

Am 02.09.2026 kam „Linux-Releaseakte prüfen" in die CI, fail-closed: keine
native Datei ohne Besitzer, jede Laufzeitfamilie mit Lizenztext, eine
Evidenzdatei mit Quellbelegen. Der Job läuft nur beim Tag. Jeder Tag-Lauf
seither wurde abgebrochen. Als ich das 0.2.1-Paket von der Website auspackte
und die Prüfung darüber fuhr: 135 Dateien ohne Besitzer auf Linux, 30 auf
Windows, 41 auf macOS, und die Evidenzdatei hatte keinen Schreiber. Der Job
war grün, weil er nie gelaufen war.

**Why:** Ein Schritt, der an ein seltenes Ereignis gebunden ist (Tag, Release,
Handstart), wird zwischen zwei Ereignissen von niemandem gefahren, während
alles, was er prüft, sich weiterbewegt. Seine Tests prüfen Attrappen
(`libffi-8.dll` in `tmp_path`), nicht das Artefakt; das Artefakt gibt es nur
im Release. „Fail-closed" macht das nicht besser, sondern teurer: Der erste
echte Lauf ist dann der Release selbst.

**How to apply:** Wer einen Prüfschritt an den Tag bindet, fährt ihn **einmal
über ein echtes Artefakt**, bevor er ihn als Zusicherung führt — die alten
Pakete liegen in `website/dl/` und lassen sich auspacken (`tarfile` ohne
Symlinks; macOS: xar → Payload → cpio). Was der Schritt verlangt und wer es
erzeugt, gehört in denselben Commit: ein Prüfer ohne Erzeuger ist eine
Behauptung. Und im Register steht dann „am Paket X gemessen", nicht „gebaut".
Verwandt: [[paketfix-ist-kein-anwendungsfix]] (dieselbe Woche, dieselbe Form:
gebaut heißt nicht gemessen), [[waechter-sieht-nur-das-getane]],
[[eingechecktes-artefakt-ueberlebt-seinen-erzeuger]].
