---
name: korpusprobe-vor-einer-neuen-merkmalsart
description: "Eine neue Merkmalsart wird vor dem Commit über den ganzen lokalen Korpus (tests/data und F:\\3D Dateien) gefahren — die Fehltreffer stecken in Modellen, die kein Test kennt: ein Schild mit 24 erhabenen Buchstaben war ein „Rauschmuster“, obwohl alle acht Texturtests grün waren"
metadata:
  node_type: memory
  type: feedback
  originSessionId: f56e0441-974f-4150-ac77-8e36658dc05b
  modified: 2026-09-22T09:40:00.000Z
---

Gemessen am 22.09.2026 an RM-207 (Muster als Merkmal): 53 Tests grün — alle
acht Texturen von `apply_texture` erkannt, entfernt, geändert, der Halter mit
196 Waben richtig. Dann die Sonde über 193 Dateien in `tests/data` und
`F:\3D Dateien`: drei Treffer. Der Halter (richtig), eine Taschentuchbox mit
sieben Wellenrillen (richtig) — und `Bitte_im_Sitzen.3mf`, ein Schild mit 24
erhabenen Buchstaben, als „Rauschmuster": gleich tief, verstreut, ein Drittel
Deckung, nicht von Streuflecken zu unterscheiden. Kein Test hätte das
gefunden, denn kein Test baut ein Schild. Die Grenze für Rauschen liegt
seither bei 40 Flecken (`patterns.MIN_NOISE`), die Nachbarsitzung fand mit
derselben Probe das Kumiko-Gitter (7 295 Flächen, kein Muster — richtig).

**Why:** Eine Erkennung, die etwas Neues sieht, sieht es überall — auch dort,
wo es nicht ist. Die Tests messen, was die Erkennung sehen soll; was sie
fälschlich sieht, steht nur in Modellen, die niemand für sie gebaut hat.

**How to apply:** Vor dem Commit einer neuen Merkmalsart oder Sammelform die
Erkennung über den ganzen lokalen Korpus fahren (Sonde: je Datei Arten
zählen, Treffer mit Zahlen ausgeben) und jeden Treffer einzeln ansehen — der
Halter ist der Nachweis, das Schild der Befund. Siehe
[[was-die-suite-nicht-findet]] und [[downloads-ordner-als-3mf-korpus]].
