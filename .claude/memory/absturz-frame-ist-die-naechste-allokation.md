---
name: absturz-frame-ist-die-naechste-allokation
description: "Bei einer Heap-Beschädigung nennt der Stapelabzug die nächste Allokation, nicht die Ursache — und deshalb wandert er"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5f85192a-8b20-4339-ba08-13913837d58c
  modified: 2026-08-30T21:30:03.657Z
---

Wandert der oberste Frame eines Absturzes zwischen mehreren Stellen, die alle
**Speicher anfordern**, ist keine davon die Ursache. Sie sind der Zeitpunkt:
Die Beschädigung ist längst passiert, und die erste größere Allokation danach
fällt darüber.

Gemessen am 30.08.2026, `test_print_settings_ui.py`, vier Läufe:

| | Position | oberster Frame |
|---|---|---|
| mit Messplugin | 33 | `_label` (ein `QLabel` entsteht) |
| mit Messplugin | 31 | `_build_tabs` |
| ohne Plugin | 33 | `_label` |
| ohne den Sprachwechsel-Test | 34 | `_make_setting_editor` |

Darunter in allen vieren dieselbe Kette bis zum Fixture, das den nächsten
Dialog **baut**. Das Register führte den Riss bis dahin als „im Teardown der
Aufräum-Fixture" — er liegt im Aufbau.

**Why:** Vier Anläufe hatten am Zeitpunkt angesetzt (zwei gc-Varianten,
`deleteLater`, der Fenster-Pin) und alle nichts gebracht. Wer den Frame für
die Ursache hält, repariert die Stelle, an der es auffällt.

Und die naheliegendste Ursachenklasse ist damit **nicht** belegt, sondern
widerlegt: Handles 270→358, Speicher 102→208 MB, gc-Objekte 89k→141k — alle
drei springen **einmal** (ein Modul lädt) und sind danach flach. Fenster
schwingen 10–63 ohne Trend, tote Wrapper 0, hängende Arbeiter 0. Nichts läuft
voll.

**How to apply:** Frame und Position notieren, aber als *Zeitpunkt* melden.
Was den **Ort** zeigt, ist der Page Heap (`gflags /p /enable python.exe /full`,
danach `/disable`) — er lässt jede Allokation an einer Seitengrenze enden, und
ein Überschreiber bricht dort ab, wo er stattfindet. Verwandt:
[[gemessene-frage-ist-nicht-die-gestellte]] und
[[bekannte-familie-erklaert-nicht-den-ausloeser]]. Der Messaufbau liegt in
`.claude/.state/mengen-riss-2026-08-30/`.
