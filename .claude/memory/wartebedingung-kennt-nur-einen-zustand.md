---
name: wartebedingung-kennt-nur-einen-zustand
description: Eine Schleife, die auf einen von mehreren Zuständen wartet, hängt bei allen anderen still.
metadata:
  type: feedback
---

`gate_lock.py status` hat drei Antworten: „Das Tor ist frei.", „Das Tor läuft:
<wer>" und „Ein verwaistes Schloss liegt da". Eine Wartebedingung von
3d-druck-7b prüfte am 03.09.2026 auf die erste. Die Maschine war neun Minuten
frei — als verwaistes Schloss —, und die Schleife hätte ewig gewartet.

**Why:** Ein Test, der falsch prüft, wird rot. Eine Wartebedingung, die falsch
prüft, wartet — und Warten sieht aus wie Arbeiten. Der Fehler meldet sich nie
selbst; er kostet, bis jemand von außen fragt. Dieselbe Familie wie
[[gemessene-frage-ist-nicht-die-gestellte]], aber mit dem stilleren Ausgang.

**Und zwanzig Minuten später dieselbe Falle bei mir, mit anderer Ursache.**
Meine Schleife auf 7bs Tor griff `"Das Tor läuft: 3d-druck-7b"`. Sie meldete
sofort „durch", während dieselbe Ausgabe `Das Tor l?uft: 3d-druck-7b … seit 6
min` zeigte: Die Konsolen-Codepage trägt das `ä` nicht, das Muster traf nie,
und ein `until !` auf ein Muster, das nie trifft, ist sofort fertig. Zwei
verschiedene Ursachen, ein Ausgang — **eine falsche Entwarnung ohne
Fehlermeldung.**

**How to apply:** Wer auf einen Zustand wartet, zählt zuerst auf, welche es
gibt, und sagt für jeden, was die Schleife tut — auch für „keiner davon". Kein
Umlaut im Muster: nicht wegen der Sprachregel, sondern weil die Ausgabe eines
Windows-Prozesses ihn nicht zuverlässig trägt. Nach dem Scharfschalten einmal
in die Ausgabedatei sehen, ob die Schleife wirklich noch wartet — das kostet
fünf Sekunden und ist die einzige Probe, die eine sofortige Fehlmeldung fängt.
Eine Obergrenze für die Wartezeit gehört dazu; sie verwandelt einen Hänger in
eine Meldung. Und der Nebenschaden ist real: Ein abgebrochener Wartetask
hinterlässt Waisen ([[abgebrochener-lauf-hinterlaesst-waisen]]).
