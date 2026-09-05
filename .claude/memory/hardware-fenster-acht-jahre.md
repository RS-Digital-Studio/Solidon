---
name: hardware-fenster-acht-jahre
description: Roberts Maßstab für Hardwareunterstützung — die letzten acht Jahre müssen laufen (Stand 09/2026 ab 2018); ältere Karten sind kein Kriterium für Renderer- oder Bibliothekswahl
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f205bb02-89f3-41d7-a514-397ddd2fe07b
  modified: 2026-09-05T15:02:57.698Z
---

Robert am 05.09.2026, bei der Wahl des Renderers: „Solange wir immer die
letzten 8 Jahre abdecken, ist mir das egal.“ Eine Grafikkarte oder ein Rechner
älter als acht Jahre muss Solidon nicht tragen; die Mindestanforderung darf
sich daran orientieren.

**Why:** Die Diskussion um wgpu (Vulkan 1.1/DX12/Metal, Grenze etwa 2012 bis
2015) hat gezeigt, dass eine Ausschlussliste ohne Maßstab in beide Richtungen
zu Fehlschlüssen führt; das Fenster von acht Jahren ist der Maßstab.

**How to apply:** Bei jeder Bibliotheks- oder Renderer-Entscheidung prüfen,
ob Hardware ab (heute minus acht Jahre) läuft, nicht ob jede jemals verkaufte
Karte läuft. Das Fenster wandert mit dem Datum. VMs und Remote-Desktop
bekommen CPU-Rendering (WARP, lavapipe, llvmpipe); das gilt als „läuft".
Siehe [[viewport-zwei-renderer-messen]].
