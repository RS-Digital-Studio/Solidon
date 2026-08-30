---
name: zahl-im-fliesstext-hat-begleiter
description: "Eine Zahl in Prosa steht selten allein — daneben rechnet eine zweite mit, und oft zählt ein Satz die Dinge auf."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: f1fa50e5-23de-4673-8c99-66e1556eff5d
  modified: 2026-08-30T23:50:51.819Z
---

Am 31.08.2026 kam ein zehntes Beispielprojekt dazu. Die Website nannte die
Neun an **dreißig** Stellen: sechs Ziffern in Statistikblöcken, vierundzwanzig
ausgeschriebene Zahlwörter, sechs Sprachen. Ein Test fand genau **eine** davon
— die Ziffer auf der deutschen Seite.

**Zwei Sorten Begleiter, die ein Zahlentausch übersieht:**

- **Die mitrechnende Zahl.** „Vier der neun … die übrigen **fünf**." Wer nur
  „neun" → „zehn" tauscht, hinterlässt eine Rechnung, die nicht mehr aufgeht.
  Bei zehn sind es sechs.
- **Der aufzählende Satz.** „Zehn Beispiele liegen bei — eines je Weg, dazu
  Bausteine, Beschriftung, Kalibrierung, Druckvorbereitung und eine Dose mit
  Deckel." Das sind vier plus fünf. **Eine Zehn über einer Liste von neun
  Dingen findet kein Test und jeder Leser.**

**Die Regel:** Wer eine Zahl im Fließtext ändert, liest den ganzen Satz und den
davor — und sucht nach der Differenz (`n − x`) und nach der Aufzählung. In
sechs Sprachen sechsmal, denn die Formulierung unterscheidet sich, die Falle
nicht.

**Zwei Werkzeug-Lehren aus demselben Lauf:**

- **Feste Anker versagen an umbrechendem HTML.** „Nine example projects are
  waiting on the start\n          screen" trifft kein Anker aus einer Zeile;
  mein erster Versuch verfehlte 17 von 30 Stellen und ließ die Dateien halb
  geändert zurück. Ersetzt wird das Zahlwort **im Kontext seines Bezugsworts**,
  mit `\s+` zwischen den Wörtern — und danach wird gezählt, wie viele alte
  Vorkommen übrig sind. Null oder es war nicht vollständig.
- **Die Kontrollfrage war zu weit gestellt.** „Steht ‚esquisse' in der Datei?"
  antwortete mit Ja — aus dem *Dateinamen eines Belegbilds*. Erst die Frage
  „steht es in **diesem Satz**?" zeigte, dass das Wort in allen sechs Sprachen
  fehlte statt in dreien. Siehe [[gemessene-frage-ist-nicht-die-gestellte]].

Verwandt mit [[texte-altern-mit-ihrer-grenze]] und
[[abgelesene-zahl-altert-still]] — dort altert eine Zahl im Code, hier eine im
Satz.
