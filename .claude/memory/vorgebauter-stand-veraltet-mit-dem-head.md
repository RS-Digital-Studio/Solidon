---
name: vorgebauter-stand-veraltet-mit-dem-head
description: "Ein vorab zusammengesetzter Commitstand (Katalog, Hunk-Auswahl) ist gegen den HEAD seiner Bauzeit gebaut — committet eine andere Sitzung dazwischen, nimmt er deren Änderung still zurück."
metadata:
  type: feedback
---

Am 25.09.2026 habe ich die Kataloge für einen Commit aus „HEAD plus meine
Schlüssel" vorgebaut und zwanzig Minuten später committet. Dazwischen hatte
eine andere Sitzung drei Übersetzungen eingetragen und committet (75aaf46e9).
Mein Commit 933c891a3 setzte den alten Stand und nahm sie wieder heraus;
aufgefallen ist es nur, weil ich danach `git diff <fremd> <meins>` las.
Behoben in e8d99f8c1. Die HEAD-Prüfung in meinem Commitwerkzeug schlug nicht
an, weil sie nur prüfte, dass HEAD sich **während** des Aufbaus nicht bewegt —
nicht seit dem Bau der Quelldateien.

**Why:** Ein zusammengesetzter Stand (JSON-Katalog aus HEAD + Auswahl,
Hunk-Auswahl aus `difflib` gegen `git show HEAD:`) trägt den HEAD seiner
Bauzeit in sich. Im geteilten Baum committen andere Sitzungen minütlich.

**How to apply:** Vor jedem Commit mit vorgebauten Dateien
`git log <bau-head>..HEAD -- <datei>` für jede davon — leer muss es sein,
sonst neu bauen. Oder den Stand erst unmittelbar vor dem Commit bauen. Nach
dem Commit `git diff <vorheriger HEAD> HEAD -- <gemischte Dateien>` lesen:
Zeilen mit `-`, die nicht meine sind, sind ein Verlust. Gehört zu
[[geteilter-index-nach-fremdem-commit-veraltet]] und
[[katalogschreiber-ueberschreibt-still]].
