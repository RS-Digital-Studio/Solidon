---
name: geprueft-fuehlt-sich-wie-vollstaendig-an
description: "Wer eine Hälfte einer Regel geprüft hat, hält die andere für erledigt — weil er geprüft hat; zweimal am 04.09.2026 belegt"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c871cf4c-c8ca-4522-a5ff-943087562544
  modified: 2026-09-04T07:21:15.659Z
---

Am 04.09.2026 habe ich in einem Baum mit sechs parallelen Sitzungen zweimal
dieselbe Regel gebrochen (`.claude/rules/tests.md`, „Wer das Schloss belegt
sieht, schreibt nicht"). Der zweite Bruch ist der lehrreiche.

**Erster Bruch, ohne Prüfung:** Ich habe `app/ui/viewport.py` geändert,
während daneben ein Torlauf fuhr, ohne vorher nachzusehen. Kostete einen
Torlauf.

**Zweiter Bruch, mit Prüfung:** Ich habe committet, während solidon-b4s Tor
lief, und vorher überlegt. Mein Schluss: „Ein Commit schreibt nichts in den
Arbeitsbaum, ihr Lauf bleibt unberührt." Der Satz stimmt für **Dateien** und
ist für **Last** falsch — und das Schloss steht wegen der Last. Der
`pre-commit`-Hook dieses Repositories fährt zwei Testdateien (rund zehn
Sekunden CPU), der `post-commit`-Hook pusht. Aufgefallen ist es nicht mir,
sondern solidon-2f.

**Und 2f hat am selben Tag denselben Satz benutzt, mit einem anderen blinden
Fleck:** Sie schrieb e9 „ein Commit berührt den Arbeitsbaum nicht, also
unbedenklich" — und übersah dabei nicht die Last, sondern die
**Zuständigkeit**: dass ein Commit eine Freigabe braucht, die eine Sitzung
einer anderen nicht erteilen kann. Zwei verschiedene blinde Flecken, ein
Muster.

> **Wer eine Hälfte geprüft hat, hält die andere für erledigt — weil er
> geprüft hat.**

Der Mechanismus ist nicht Nachlässigkeit: Die geleistete Prüfung fühlt sich
wie Vollständigkeit an, und man hört auf zu suchen, sobald man **eine** Antwort
hat. Es ist dieselbe Mechanik wie in `.claude/memory/benannte-falle-schuetzt-nicht.md`
des Repositories (ein Modul, das eine Falle richtig benennt, ist gegen sie
nicht immun), nur nach innen gewendet.

**Wie ich das anwende:** Wenn ich eine Regel gegen eine Handlung prüfe, frage
ich nicht „gilt sie?", sondern „**wogegen** schützt sie, und berührt meine
Handlung das?". Beim Prüfschloss sind es zwei Dinge — Arbeitsbaum und
Rechenlast —, und ein Commit trifft das zweite über seine Hooks. „`git commit`
kostet nichts" denkt an git und nicht an das, was dieses Repository daran
gehängt hat.

Verwandt: [[fremde-messung-vor-der-weitergabe-pruefen]],
[[weitergabe-die-handlung-entscheidet]]
