---
name: kette-mit-semikolon-laeuft-nach-dem-kill-weiter
description: "Wer das erste Glied einer mit ; verketteten Hintergrundkette killt, startet das zweite — unter dem Torschloss lief so die Leistungsreihe los, während ich glaubte, alles sei beendet"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c8bf1d70-6f46-4992-9b9e-5becddfdbd88
  modified: 2026-09-06T13:28:10.305Z
---

Am 06.09.2026 startete ich `gate_lock run suite…; echo Exit; gate_lock run
pytest -m performance` als Hintergrundaufgabe, entschied dann, den Lauf
abgekoppelt neu zu starten, und beendete den Prozessbaum des ersten Glieds.
Der Shell-Wrapper lebte weiter, wertete den Kill als Exit des ersten Befehls
und startete das zweite Glied: Die Leistungstests nahmen das Schloss, und
`gate_lock status` meldete plötzlich meinen eigenen Namen mit einer neuen
Prozessnummer.

**Why:** `;` heißt „danach, egal wie“. Ein Kill trifft ein Glied, nicht die
Kette; der Wrapper macht mit dem nächsten weiter, und das nimmt Schloss,
Kerne und Ausgabedateien, als wäre nichts gewesen.

**How to apply:** Beim Beenden eines Laufs zuerst den **Wrapper** (die
Shell der Kette) beenden, dann die Blätter — oder die Kette von vornherein
mit `&&` bauen, damit ein gekilltes Glied sie abbricht. Danach
`gate_lock status` lesen und die Prozessnummer mit der eigenen vergleichen.
Siehe [[eigenen-lauf-ueber-die-elternkette-beenden]],
[[hintergrundlauf-stirbt-mit-der-sitzung]].
