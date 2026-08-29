---
name: testprojekt-trifft-den-fall-nicht
description: "Ein selbst gebautes Testprojekt trifft die Fälle nicht, die ein ausgeliefertes mitbringt — der Test war grün, die Anwendung brach an allen neun Beispielen ab."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4e2b249b-1d42-4020-bb0e-bdcf350ef625
  modified: 2026-08-29T21:13:39.159Z
---

`solidon3d info` brach am 29.08.2026 an **allen neun** ausgelieferten
Beispielprojekten mit einem Programmfehler ab. Ein Test dafür gab es:
`test_info_describes_the_evaluated_scene`, grün seit Monaten.

Er baut sein Projekt selbst — `new`, dann `import cube_clean.stl`. Dort heißt
das Objekt „cube_clean", eine gewöhnliche Zeichenkette. In einem
ausgelieferten Projekt heißt es „Dose Deckel" und ist ein `TranslatableText`,
weil es aus einem Baustein stammt. `f"{name:<24}"` bricht daran.

**Ein selbst gebautes Testprojekt enthält, was der Test hineinlegt.** Ein
ausgeliefertes enthält, was die Anwendung wirklich erzeugt: Bausteine,
benannte Parameter, zusammengesetzte Transaktionen, übersetzbare Namen. Die
Lücke dazwischen ist genau der Bereich, in dem Kunden arbeiten.

**Why:** Ein Test, der seine eigenen Eingaben herstellt, prüft den Code gegen
die Vorstellung seines Autors davon, wie die Daten aussehen. Die
Referenzdateien in `tests/data/` sind dagegen fremd — und `app/examples/`
sind die einzigen, die der Kunde selbst öffnet.

**How to apply:** Wo ein Befehl oder eine Ansicht ein *Projekt* verarbeitet,
gehört mindestens ein Lauf über `app/examples/*.p3d` dazu — parametrisiert
über alle neun, nicht über eines. Die Gegenprobe zeigte, warum: Acht der neun
fielen ohne den Fix, das neunte (`drucker-kalibrieren`) hat keine
Bausteinobjekte und wäre auch vorher grün geblieben. Neun Läufe kosten sechs
Sekunden.

Siehe [[was-die-suite-nicht-findet]] und
[[reparierter-fehler-hat-zwillinge]] — der Fix stand hier drei Zeilen tiefer
schon richtig da, samt Kommentar, warum er nötig ist.
