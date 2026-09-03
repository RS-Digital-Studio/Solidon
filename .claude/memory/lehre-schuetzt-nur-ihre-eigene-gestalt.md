---
name: lehre-schuetzt-nur-ihre-eigene-gestalt
description: "Eine Erinnerung schützt vor dem Fall, in dem sie geschrieben wurde — nicht vor seiner nächsten Gestalt; am 03.09.2026 viermal an einem Abend."
metadata:
  type: feedback
---

Am Abend des 03.09.2026 meldeten **vier** Sitzungen unabhängig denselben
Vorgang: Sie kannten die Erinnerung, die ihren Fehler beschreibt, und machten
ihn trotzdem.

| Sitzung | Notiz, die es beschreibt | wo sie hineinlief |
|---|---|---|
| 7f | `commit-o-nimmt-den-dateistand` | zwei Stunden nach dem Zitieren derselben Notiz an d4 |
| a0 | `geteilter-index-haelt-alten-stand` | `git reset` ohne Pfade, nachdem er drei Sitzungen davor gewarnt hatte |
| 81 | die Lehre stand im **Docstring desselben Werkzeugs** | Lizenzbeilage |
| ich | `deutscher-text-geht-nicht-durch-die-shell` | ein `
` im Heredoc, das zum echten Umbruch mitten in einem String wurde |

**Die Erklärung, die am besten trug** (meine, und 81 hat sie übernommen):
Dass es beim Patchen von **Testtext** passiert, war die Variante, an die ich
nicht gedacht hatte. Die Notiz beschreibt Commit-Meldungen und
Oberflächentexte — also Text, der zum Kunden geht. Ein Assert-Satz in
einem Test ist derselbe Fall und sieht nicht so aus.

a0s Fassung derselben Sache: Er nimmt für die Sprachkataloge seit dem
Mittag konsequent den Blob aus HEAD und behandelte `ROADMAP.md` trotzdem, als
wäre sie seine. *Der Unterschied lag nicht in der Datei, sondern darin,
dass er bei den Katalogen einmal auf die Nase gefallen war und bei der ROADMAP
noch nicht.*

**Why:** Eine Lehre wird an einem Ort gelernt und bleibt dort. Sie ist im
Gedächtnis an ihre **Kulisse** geheftet — an die Datei, das Werkzeug,
die Textsorte — und nicht an ihre Form. Beim nächsten Mal fehlt die
Kulisse, und die Form allein löst nichts aus. Deshalb hilft
**Häufigkeit des Lesens** wenig: 7f hatte die Notiz zwei Stunden vorher in
der Hand.

**How to apply:** Nicht auf Erinnern setzen, sondern die Lehre an die Stelle
schrauben, an der gearbeitet wird:

* **Ein Wächter statt eines Satzes.** Nach dem `_too_small_to_make`-Zwilling
  steht jetzt ein Test über dem Quelltext, der verbietet, die Konstante
  anderswo zu vergleichen — er greift, ohne dass jemand die Regel kennt.
* **Ein Schritt im Skript statt im Kopf.** Der Sollproben-Guard in `/liefern`
  bricht ab; eine Zahl, die nur ausgegeben wird, lässt den Commit
  weiterlaufen ([[behobener-fehler-war-nie-draussen]] hat denselben Bau).
* **Beim Schreiben einer Notiz die nächste Gestalt mitdenken:** Nicht „in
  Commit-Meldungen", sondern „in jedem Text, der durch die Shell geht" —
  und die Gegenprobe dazu ins How-to-apply, nicht nur den Fall.

Und die bescheidene Fassung: Eine Erinnerung verhindert den Fehler nicht, sie
**verkürzt die Suche danach**. 7fs Verlust war in zehn Minuten gefunden,
weil er die Bauart sofort erkannte; ohne die Notiz wäre es ein halber Tag
gewesen.

Verwandt: [[reparierter-fehler-hat-zwillinge]] (die Lehre reist nicht zu den
Geschwistern), [[gemessene-frage-ist-nicht-die-gestellte]],
[[schranke-aus-einem-messwert-ist-geraten]].
