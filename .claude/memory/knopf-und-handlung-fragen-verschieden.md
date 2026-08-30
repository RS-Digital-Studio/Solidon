---
name: knopf-und-handlung-fragen-verschieden
description: "Ein Knopf wird freigegeben, wenn A gilt, und die Handlung dahinter steigt aus, wenn B fehlt — dazwischen liegt ein Bereich, in dem der Klick folgenlos bleibt."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: cc0c50ad-6ea5-4d75-b0d4-2e514a473ea3
  modified: 2026-08-30T06:53:41.489Z
---

Am 30.08.2026 zweimal an einem Vormittag gefunden, von zwei Sitzungen
unabhängig:

| Stelle | Freigabe | Ausführung | Bereich dazwischen |
|---|---|---|---|
| `GenerateDialog` | `readiness is not ABSENT` | `readiness is READY` | `UNKNOWN`, `NO_NODES`, `NO_MODEL` |
| Slicen-Knopf (fb) | Vorprüfung im Dialog | Prüfung im Kern | die Profilfrage |

Im ersten Fall war *Erzeugen* klickbar, und der Klick tat **nichts**: kein
Lauf, kein Balken, kein Satz. Gemessen mit einer Attrappe je Lage — Backend
0-mal gerufen, Zustandstext unverändert.

**Why:** Beide Bedingungen wachsen getrennt. Die Freigabe entsteht beim
Bauen der Oberfläche, die Prüfung beim Schreiben der Handlung, und keine der
beiden Stellen sieht die andere. Sie stimmen am Anfang überein, weil derselbe
Mensch sie kurz nacheinander schreibt; auseinander laufen sie beim ersten
neuen Zustand — hier waren es die vier `Readiness`-Lagen, die eine frühere
Fassung als Wahrheitswert hatte.

Ein gesperrter Knopf ist dabei **besser** als ein toter: Er hat den Satz
daneben, der ihn erklärt, und meist den zweiten Knopf, der die Lage behebt
(Regel 17). Ein klickbarer Knopf ohne Wirkung sagt dem Kunden, er habe etwas
falsch gemacht.

**How to apply:** Beide Stellen fragen **dieselbe** Sache — eine Eigenschaft,
eine Methode, ein Ausdruck, den beide rufen. Nicht zwei Ausdrücke, die
dasselbe bedeuten sollen.

Die Prüffrage beim Lesen: *Gibt es einen Zustand, in dem der Knopf freigegeben
ist und die Handlung still zurückkehrt?* Am schnellsten beantwortet man sie
nicht durch Lesen, sondern durch Klicken — je Zustand einmal
`button.click()` und danach zählen, ob das Backend gerufen wurde. Siehe
[[pruefstand-geht-den-weg-der-oberflaeche]].

**Und die Gegenprobe zur Ausbreitung ist gefahren:** Eine AST-Suche über
`app/ui/` nach Klassen mit `setEnabled` und Methoden mit stillem
`if …: return` fand neun Kandidaten — acht Fehlalarme (Nachzügler-Schutz,
Null-Prüfungen, `toggled`-Signale, Signalunterdrückung beim Befüllen), einer
war der bekannte. **Das Muster ist eine Häufung von Einzelfällen, kein
systemischer Riss**, und die Suche sieht ohnehin nur die erste Anweisung einer
Methode. Wer sie wiederholt, weiß das vorher.
