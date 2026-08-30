---
name: review-immer-vollstaendig
description: "Roberts Vorgabe für die Freigabe-Rolle — jede Freigabe mit vollständiger Diff-Lektüre, keine risikobasierte Stichproben-Ökonomie."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 9c480190-d910-460e-bc5c-c2d37eab6361
  modified: 2026-08-30T05:29:28.461Z
---

Robert am 30.08.2026, auf die offene Frage nach der Review-Tiefe („wenn du
für bestimmte Bereiche volle Zeilenlektüre willst … sag, wo du die Grenze
willst"): **„immer gründlich und sauber"** — keine Grenze, volle Lektüre
überall.

**Why:** Vier Fehler waren zuvor durch risikobasierte Reviews gerutscht
(Katalogzeilen, Drift-Behauptung, gefolgerte Rot-Meldung, unpräzises
Freigabekriterium). Alle wurden gefangen, aber Robert will die Tiefe, nicht
die Ökonomie — Durchsatz ist kein Gegenargument (dieselbe Haltung wie
[[aus-kundensicht-perfekt]]: Aufwand zählt nicht).

**How to apply:** Als Freigabe-Instanz vor jedem Go den vollständigen Diff
jeder Datei lesen — auch bei Website-Texten, erzeugten Dateien und großen
Paketen, nicht nur an Risikostellen. Zusätzlich bleiben: numstat-Sollprobe
je Datei gegen den aktuellen HEAD unmittelbar vor dem Commit, eigene
Nachmessung jeder Behauptung, Katalogfrage bei neuen tr()-Texten.

Ergänzt am 30.08.2026: **„und auch immer komplett aus kundensicht
abarbeiten"** — jede Freigabe stellt ausdrücklich die Kundensicht-Fragen:
Was sieht der Kunde vor und nach dem Fix? Muss er irgendwo raten? Gibt es
aus jedem Zustand einen sichtbaren Weg hinaus? Sprechen alle neuen Texte
Kundenwörter statt Technik? Ein technisch geschlossener Fix, der eine
dieser Fragen offen lässt, ist nicht fertig.

Ergänzt am 30.08.2026, zweite Stufe: **„und du verifizierst das und vorher
gibt es kein commit"** — die Freigabe-Instanz verifiziert jeden Fix
SELBST, bevor ein Commit fällt: die betroffenen Tests und
Abnahmekriterien eigenhändig fahren (unter dem Schloss, wo nötig), bei
Bedienthemen den gebauten Zustand selbst durchgehen. Die Läufe des
Arbeiters sind Vorleistung, nie Ersatz. Ohne eigene grüne Verifikation
kein Go, ohne Go kein Commit — ausnahmslos.
