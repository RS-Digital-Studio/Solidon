---
name: beheben-statt-notieren
description: "Roberts Anweisung vom 02.09.2026 — was ich finde, behebe ich, auch Optimierungen; ein Registereintrag ist kein Ersatz für die Reparatur"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c1806dc1-e846-4999-89d4-b8c3c4636d14
  modified: 2026-09-02T16:41:42.077Z
---

Robert, 02.09.2026, während des Releases 0.3.0: „du solltest auch immer
beheben, nicht nur notieren, wenn du etwas findest, ebenso Optimierungen."
Davor an alle drei Sitzungen: „ich will keine Bugs usw. mehr in 0.3.0, alles
jetzt beheben, was ihr findet."

**Why:** An dem Tag lagen im Register von `ROADMAP.md` Punkte, die eine
Sitzung als „wartet auf" eingetragen hatte, statt sie zu bauen — die
Stiftseite bei Auto Split, die Deckungslücke der CI, die xcb-Bibliotheken im
Linux-Paket („Empfehlung 0.3.1"). Robert hat jede dieser Empfehlungen
gedreht: Es kommt in 0.3.0, und zwar vollständig. Ein Fund, der als Notiz
liegen bleibt, ist für ihn ein Fund, den jemand liegen gelassen hat — auch
wenn die Notiz gut begründet ist. Das gilt ausdrücklich auch für
Optimierungen: Eine Stelle, die messbar langsam ist, wird beschleunigt, nicht
als „Befund" gemeldet.

**How to apply:**
- Fund → Messung → Behebung → Test, in dieser Sitzung. Das Register ist für
  das, was eine **Entscheidung** von Robert braucht oder eine Sache außerhalb
  des Repositorys (ein Mac, ein Zertifikat, ein Konto) — nicht für Arbeit,
  die ich selbst tun kann.
- „Zu groß für heute" ist keine Begründung, solange Robert wartet: sagen, was
  es kostet, und bauen. Er entscheidet über Umfang, nicht ich.
- Liegt die Datei bei einer anderen Sitzung: die Messung liefern und die
  Behebung dort anstoßen — Arbeitsteilung ist kein Notieren.
- Optimierung heißt gemessen: vorher/nachher, dieselbe Frage.

Siehe auch [[aus-kundensicht-perfekt]] (derselbe Maßstab) und
[[tests-und-rendern-nur-das-noetigste]] (die Läufe, die dabei nicht mehr den
Takt vorgeben).
