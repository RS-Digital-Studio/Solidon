---
name: repository-ist-nur-beim-release-oeffentlich
description: Solidon liegt normalerweise als privates Repository; öffentlich ist es nur für einen Release — deshalb brechen CI-Läufe im Alltag mit einer Abrechnungsmeldung ab, und das ist kein Befund
metadata:
  type: project
---

`RS-Digital-Studio/Solidon` ist **privat** und wird **nur für einen Release**
auf öffentlich geschaltet (Robert, 22.09.2026 — nach eigener Aussage
mindestens das zehnte Mal gesagt, und bis dahin nirgends aufgeschrieben).

**Was das für die CI heißt:** Actions-Minuten sind für öffentliche
Repositories kostenlos, für private nicht. Solange Solidon privat liegt,
brechen die Läufe nach Sekunden ab mit

> The job was not started because recent account payments have failed or your
> spending limit needs to be increased.

Am 22.09.2026 standen so zehn rote Läufe hintereinander in `gh run list`, alle
mit vier bis sieben Sekunden Laufzeit. **Das ist kein Fehler im Projekt, kein
kaputter Workflow und nichts, was einen Release blockiert** — es ist der
Normalzustand zwischen zwei Releases.

**Why:** Ein roter Lauf sieht aus wie ein Befund, und ein Lauf von vier
Sekunden sieht aus wie ein früher Abbruch im Workflow. Wer die Annotation
nicht liest, sucht die Ursache im Code und findet dort nichts. Und wer sie
liest, hält sie für einen Blocker und fragt Robert, statt zu arbeiten.

**How to apply:**

- Rote Kurzläufe mit dieser Meldung **nicht** als Fehler behandeln und nicht
  zum Anlass für Rückfragen nehmen. Die Laufzeit unterscheidet sie:
  Sekunden statt Minuten, und kein einziger Schritt gelaufen.
- Wer wissen will, ob gerade ein Lauf möglich ist, fragt die Sichtbarkeit:
  `gh repo view --json isPrivate --jq .isPrivate`. `false` heißt, die
  Release-Phase läuft und die CI misst wirklich.
- Ein Lauf, der **vor** der Umschaltung gestartet wurde, misst nichts. Nach
  dem Umschalten neu auslösen, nicht das alte Ergebnis lesen
  ([[messung-galt-fuer-den-stand-davor]]).
- Nach dem Release geht das Repository wieder auf privat; ab dann sind rote
  Kurzläufe wieder erwartbar.
