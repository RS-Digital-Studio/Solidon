---
name: oeffnen-zum-schreiben-vor-dem-lesen-leert-die-datei
description: "open(p, 'w').write(f(open(p).read())) leert die Datei, bevor sie gelesen wird — am 25.09.2026 ging so fremde, ungestagte ROADMAP-Arbeit verloren; Lesen und Schreiben immer in zwei Anweisungen"
metadata:
  type: feedback
---

Am 25.09.2026 (RM-247) stand in einem Hilfsskript
`io.open(p, "w", …).write(fix(io.open(p, …).read()))`. Python wertet den
Empfänger vor dem Argument aus: Das Öffnen mit `"w"` **kürzt die Datei auf
null**, erst danach liest `fix` — eine leere Datei, und die Zusicherung darin
schlug fehl. `ROADMAP.md` war danach leer, samt 55 ungestagten Zeilen einer
anderen Sitzung (RM-246, RM-242). Zurück kamen sie nur, weil vor dem Pull
`git diff --binary > lokal-vor-pull.patch` gesichert worden war.

**Why:** Im geteilten Baum ([[zweite-sitzung-im-selben-baum]]) gehört eine
Datei selten einem allein; was ungestaged ist, hat keine zweite Kopie. Ein
Fehler, der die eigene Arbeit kostet, ist ärgerlich — dieser kostet fremde.

**How to apply:**
- Lesen und Schreiben immer getrennt: `text = read(); neu = fix(text);
  write(neu)` — dann bricht ein Fehler in `fix` vor dem Schreiben ab.
- Vor jedem Umschreiben einer geteilten Datei (ROADMAP, Kataloge, MEMORY.md)
  eine Kopie in den Scratchpad legen; vor einem Pull ohnehin
  `git diff --binary` sichern.
- Geht trotzdem etwas verloren: aus der Sicherung stückweise an eindeutigen
  Kontextzeilen einsetzen, die Zeilenzahl gegen den letzten bekannten
  `git diff --stat` halten und der Sitzung sagen, der es gehört.
