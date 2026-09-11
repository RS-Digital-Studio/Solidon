---
name: checkout-reflex-loescht-eigene-arbeit
description: "Ein `git checkout -- pfad/` als „Aufräumen nach einem Skript, das vielleicht halb geschrieben hat“ warf am 11.09.2026 alle ungespeicherten Katalogänderungen einer Sitzung weg — die Regel „niemals reverten“ gilt auch für den eigenen Reflex"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 9445bc01-20af-4b3c-9e8f-c80a1769a381
  modified: 2026-09-11T15:34:17.902Z
---

Am 11.09.2026 brach ein Katalogskript an einer Zusicherung ab, **bevor** es
eine Datei geschrieben hatte. Ich rief trotzdem `git checkout -- app/i18n/locales/`,
um „einen halben Stand“ auszuschließen — und verlor damit drei frühere,
noch nicht committete Katalogänderungen derselben Sitzung (zwei Texte, vier
Wörter, ein entfernter Waisen-Schlüssel). Wiederhergestellt nur, weil die
drei Skripte noch im Scratchpad lagen.

**Why:** Ein Revert stellt nicht „das Skript von eben“ zurück, sondern den
letzten Commit — alles Ungestagete dazwischen ist weg, auch fremde Arbeit
im selben Baum ([[zweite-sitzung-im-selben-baum]]). Die Hausregel „niemals
reverten“ steht nicht wegen Roberts Änderungen da, sondern wegen genau dieses
Reflexes.

**How to apply:**
- Vor einem Skript, das mehrere Dateien schreibt: erst prüfen (alle
  Zusicherungen), dann schreiben — oder je Datei in eine Kopie schreiben und
  am Ende umbenennen. Ein Abbruch nach der ersten geschriebenen Datei wird so
  gar nicht erst zum Fall.
- Ist doch etwas halb geschrieben: `git diff` lesen und **vorwärts**
  berichtigen (das Skript idempotent machen und erneut fahren), nie
  `checkout`/`restore`/`stash`.
- Katalogskripte nach dem Muster von `katalog7.py` sind idempotent (`if quelle
  not in katalog`) — sie dürfen beliebig oft laufen; darauf verlassen statt
  zurückzusetzen.
