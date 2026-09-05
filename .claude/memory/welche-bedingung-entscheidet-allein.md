---
name: welche-bedingung-entscheidet-allein
description: "Fünf Bedingungen sahen alle tragend aus; gezählt entschied genau eine je allein. Ohne diese Zählung dokumentiert man Wirkung, die keine ist."
metadata:
  node_type: memory
  type: feedback
  originSessionId: 880d8f7a-c07e-4b8f-b374-5bef80997d00
  modified: 2026-09-04T14:52:28.535Z
---

Am 04.09.2026 hatte die neue Wendelerkennung fünf Bedingungen, jede mit
Messwerten im Docstring begründet. Die Mutationsprobe — jede Bedingung einzeln
abschalten und schauen, ob ein Test rot wird — meldete bei fünf von sieben
Schaltern **„nicht gefangen"**.

Das war zuerst irritierend und dann die eigentliche Auskunft: Eine einzelne
Lockerung erzeugt keinen Fehlalarm, weil die übrigen Bedingungen denselben Fall
ohnehin ablehnen. Die richtige Frage ist deshalb nicht „bricht etwas, wenn ich
sie entferne", sondern **„welche Bedingung ist bei welchem Fall die einzige,
die ablehnt"**. Gezählt über Korpus, Kundendatei und Grenzfälle:

- In **zwei** von rund fünfzig abgelehnten Fällen entschied eine Bedingung
  allein — beide Male dieselbe (die Gangtiefe).
- Die vier übrigen waren an 33 bis 46 Ablehnungen beteiligt und an keiner
  allein.
- Zwanzig von dreiundzwanzig Korpusdateien fielen schon an einer **Vorstufe**
  heraus (zu wenige scharfe Kanten) und erreichten keine der fünf.

Vor dieser Zählung hätte ich beschrieben, die Konzentration und die
Windungszahl trügen die Trennung. Sie tun es nicht; sie sind Tiefenstaffelung.

**Why:** Ein Docstring, der jede Bedingung mit Zahlen begründet, liest sich wie
ein Beleg, dass jede gebraucht wird. Beides ist wahr und verschieden: Die
Zahlen zeigen, dass eine Bedingung bei *diesen* Fällen richtig liegt, nicht,
dass sie je den Ausschlag gibt. Wer das nicht trennt, verteidigt später eine
Zahl, die nichts entscheidet — und lockert im Zweifel die, die alles trägt.
Verwandt: [[fuenf-tests-eine-lage]], [[mutation-die-den-fall-nicht-trifft]].

**How to apply:** Bei mehreren Filtern über derselben Frage einmal je Fall
**alle** Ablehnungsgründe erheben, nicht nur den ersten (kein `return` beim
ersten Treffer in der Messung — Liste sammeln). Dann zwei Zahlen ausgeben: „wie
oft beteiligt" und „wie oft allein". Die zweite Spalte sagt, welche Bedingung
einen Test verdient und welche Formulierung in die Doku gehört. Die anderen
bleiben — sie decken, was der Korpus nicht enthält —, aber sie werden als
Staffelung beschrieben und nicht als Trennung.

**Und die Gegenprobe muss die Voraussetzung stehen lassen.** Mein erster Test
für die tragende Bedingung stauchte ein Gewinde radial glatt: Damit waren auch
die scharfen Kanten weg, es entstand gar kein Kandidat, und der Test war grün,
ohne die Bedingung je zu erreichen. Die tragende Fassung **streckt** das
Gewinde stattdessen in die Länge — Kanten und Windungen bleiben, nur das
Verhältnis, das geprüft wird, kippt. Wer eine Gegenprobe baut, prüft zuerst,
dass sie überhaupt bis zur fraglichen Stelle kommt.
