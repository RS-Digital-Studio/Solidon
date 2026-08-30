---
name: verursacher-wird-gemessen-nicht-gelesen
description: "`git log -- <dateien>` nennt den letzten Commit an *einer* der Dateien, nicht den an der gesuchten — der oberste Treffer ist eine Vermutung."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 33442ae8-b3cf-4eef-bce4-cf827af80603
  modified: 2026-08-27T04:31:50.064Z
---

**Wer einen Fehler einem Commit zuschreibt, prüft mit `git show --stat`, ob
der Commit die fragliche Datei überhaupt anfasst.** `git log --oneline -3 --
datei_a datei_b` beantwortet „welcher Commit hat zuletzt *eine* dieser Dateien
berührt" — nicht „welcher hat `datei_b` berührt". Der oberste Treffer sieht
trotzdem aus wie die Antwort.

Am 27.08.2026 zweimal in einer Stunde, in einem Baum mit vier Sitzungen:

| Behauptet | Gemessen |
|---|---|
| „`7e323e31` hat `create_lid` gebrochen" | fasst `lid.py` gar nicht an — es war `c2e07d84` |
| „`2aaf792b` ist von d1" | war es nicht; d1s vier Commits waren andere |

Beide Male war der **Befund** richtig und gemessen — origin war rot, meine
Zeilen waren mitgegangen. Falsch war nur die Zurechnung, und die war der Teil,
den ich nicht gemessen hatte.

**Why:** Der Schaden ist nicht die Peinlichkeit, sondern dass jemand am
falschen Ort sucht — genau das, wovor ich eine Stunde vorher eine andere
Sitzung gewarnt hatte, als sie mir einen fremden Zwischenstand zuschrieb. In
einem geteilten Arbeitsbaum ist „wer war das" nie aus dem Verlauf zu lesen:
Alle committen unter demselben Namen, und die Reihenfolge sagt nichts über die
Urheberschaft.

**How to apply:** Den Befund melden, die Zurechnung trennen. Wer einen
Verursacher nennt, hat vorher `git show --stat <hash>` gelesen und die Datei
darin gesehen; wer ihn nicht nennen kann, schreibt „Verursacher unklar" und
liefert die Messung. Und beim Zuschreiben an eine **Sitzung** gilt dasselbe
eine Ebene höher: Ein Commit gehört dem, der ihn geschrieben hat, und das steht
in seinem Inhalt, nicht in seiner Position im Verlauf.

Verwandt: [[commit-o-nimmt-den-dateistand]] (dort geht es um die Zurechnung
*eigener* Commits), [[messwerkzeug-misst-sich-selbst]] und
[[bekannte-familie-erklaert-nicht-den-ausloeser]].

**Nachtrag vom 30.08.2026 — dieselbe Lehre für Reproduktion statt Attribution.**
Ein Befund lautete „ElegooSlicers Kommandozeile nimmt keinen Auftrag an — auch
mit ihren eigenen Systemprofilen". Eine Parallelsitzung slicte damit zweimal
sauber. Widerlegt war der Befund in Sekunden; **nicht mehr feststellbar war,
was ich damals eigentlich gefahren hatte** — die Zeile stand nur im
Terminal-Puffer, und der war fort.

Attribution braucht `git log -S` auf den Zeileninhalt, Reproduktion braucht die
**wörtliche Kommandozeile**. Beide sind Rohdaten, beide sterben mit dem Puffer,
wenn niemand sie festhält. Wer einen Befund meldet, schreibt den Aufruf mit
hinein, solange er noch dasteht — hinterher ist eine erinnerte Zeile kein Beleg,
sondern eine zweite Vermutung über der ersten.
