---
name: serverstand-sofort-selbst-pruefen
description: Fragt Robert nach dem Stand auf dem Server oder einer Ausliefer-Kette, wird sofort gemessen und nachgezogen — nicht erst nachgefragt, ob er das will
metadata:
  type: feedback
---

Robert, 15.09.2026, auf die Frage „warum ist 0.4.1 noch auf dem server?": „mach
doch gleich immer automatisch alles".

**Why:** Eine Frage nach einem Zustand draußen (Server, version.json, Pakete,
Download-Kasten) ist ein Auftrag, ihn zu prüfen und in Ordnung zu bringen —
nicht eine Bitte um eine Einschätzung aus dem Gedächtnis oder eine Rückfrage,
ob nachgezogen werden soll. Die Regel „Release nur auf Anfrage" bleibt; die
Frage selbst ist die Anfrage, wenn das Repository schon weiter ist als der
Server.

**How to apply:** Sofort messen — `version.json` auf dem Server gegen die im
Repository, `HEAD`-Anfragen auf jedes Paket mit Content-Length gegen die
lokale Größe, `updates.check()` so fahren, wie die installierte App fragt,
Versionsnennungen auf den Seiten zählen. Weicht der Server ab, nachziehen
(Upload, Download-Kasten), dann berichten, was war und was jetzt ist. Stimmt
alles, sagen, seit wann und durch welchen Commit. Siehe auch
[[version-vor-jedem-bau-erhoehen]] und [[download-kasten-vier-pakete]].
