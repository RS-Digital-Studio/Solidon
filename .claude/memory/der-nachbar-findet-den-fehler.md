---
name: der-nachbar-findet-den-fehler
description: "Fast keinen Fehler, der zählte, fand der, der ihn gemacht hatte — Melden schlägt Sorgfalt, weil der Urheber im falschen Gebiet sucht."
metadata:
  type: feedback
---

Beobachtung von 50 am Ende des 30.08.2026, an einem Tag mit fünf parallelen
Sitzungen und über sechzig Landungen: **Von den Fehlern, die zählten, hat
fast keinen der gefunden, der ihn gemacht hat.** d3 und 15 fanden 50s
Bezeichner und Katalogtexte, 72 fand ihren Rückbau erst über einen fremden
Bericht, 50 fand 72s Zwischenstand nur, weil die Freigabe die naheliegendere
Erklärung vorschlug — und der rote Test, der stundenlang auf main lag, fiel
in einem Lauf auf, der aus einem ganz anderen Grund gestartet war.

**Why:** Wer eine Änderung macht, sucht in dem Gebiet, an das er denkt. Die
Nachbarsitzung sucht woanders — nicht weil sie klüger ist, sondern weil ihr
Blick nicht von der eigenen Absicht gelenkt wird. Deshalb sind Sitzungen,
die einander ihre Funde **melden**, mehr wert als Sitzungen, die sorgfältiger
arbeiten: Sorgfalt skaliert nicht über den eigenen blinden Fleck hinaus,
Melden schon. Und der Grund ist nicht Fleiß, sondern **Blickrichtung**:
Sorgfältiger zu arbeiten hätte keinen der Fälle des Tages gefangen — anders
hinzusehen schon, **und das kann man sich nicht selbst verordnen** (50,
30.08.2026).

**How to apply:**
- Ein Fund in fremdem Gebiet wird **gemeldet, nie stillschweigend geheilt** —
  die Meldung trägt die Messung (Datei, Zeile, Gegenprobe), nicht den
  Verdacht. Stilles Heilen nimmt dem Urheber die Lehre und dem Melder die
  Prüfung, ob er richtig zugeordnet hat.
- Umgekehrt: Wer eine fremde Meldung bekommt, behandelt sie als Geschenk und
  nicht als Vorwurf — die Antwortzeit auf Meldungen ist der Takt, der das
  System trägt.
- Für die Freigabe: Bei einem plausiblen Eigenverdacht („das ist sicher die
  bekannte Familie") zuerst die naheliegendere Fremderklärung anbieten —
  zweimal an diesem Tag war der laufende Nachbar die Ursache, nicht die
  Familie ([[geteilter-baum-misst-zeitpunkt]]).

Verwandt: [[schutz-verliert-ein-geschwister]] (die Geschwisterfrage nach dem
eigenen Fix), [[parallele-sitzungen-solidon3d]].


## 03.09.2026: neun Sitzungen, fünf Fälle, keiner vom Urheber gefunden

Dieselbe Beobachtung an einem Tag mit neun parallelen Sitzungen, und diesmal
mit der **Form** der Fehler dazu. Keiner davon war Nachlässigkeit:

| Fall | gemessen wurde | geglaubt wurde | gefunden von |
|---|---|---|---|
| Farbe des Suchtreffers | `accent_line` bringt 3,01 | das reiche für Text | der Nächste, der die Regel nachlas |
| Handbuchzeile über gesperrte Knöpfe | der Tooltip trägt den Grund | die Zusage sei eingelöst | ein Wächter über drei Kanäle |
| `input_sha256` im Rechtemanifest | die Summe vom Erzeugungstag | es dokumentiere Herkunft | der Upload, der abbrach |
| eine Kontrastzahl in einer Meldung | die Schrift auf dem Balken | es gelte der Legende | die Sitzung, die gemessen hatte |
| ein Wächter über eine Bauart | er findet Füllfarben als Schrift | er prüfe Schwellen | der, der ihn gebaut hatte |

**Die Bauart ist immer dieselbe: richtig gemessen, an der falschen Stelle
geglaubt.** Die Messung stimmt, und ihre Geltung reicht weiter als der Ort, an
dem sie gemacht wurde. Das ist der Grund, warum Sorgfalt hier nicht hilft —
niemand prüft eine Zahl nach, die er selbst korrekt erhoben hat.

Was hilft, ist die Frage nach der Geltung: **Wofür wurde das belegt?** Bei
3,01 stand die Antwort im Kommentar daneben (WCAG 1.4.11, Umrandungen). Beim
Tooltip stand sie in Regel 18 (drei Kanäle). Bei `input_sha256` stand sie im
Quelltext der Prüfung. Jedes Mal war sie auffindbar, und jedes Mal hat sie
niemand gesucht, weil die Zahl ja stimmte.

Und die Ergänzung zur Zurechnung, die den Punkt erst schließt: **Vier der fünf
wurden von einer anderen Sitzung gefunden, der fünfte von einem Wächter.**
Nicht ein einziger vom Urheber — auch dann nicht, wenn er den Fehler eine
Stunde später in einer Nachricht erklärte. Wer eine Zahl weitergibt, sagt
deshalb dazu, **wo sie gemessen wurde**; das ist billiger als jede Nachprüfung
und fängt genau diese Familie.
