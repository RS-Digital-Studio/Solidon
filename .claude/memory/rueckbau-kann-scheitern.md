---
name: rueckbau-kann-scheitern
description: "Eine Mutationsprobe mit try/finally lässt die Mutation stehen, wenn das Zurückschreiben selbst scheitert — im geteilten Baum passiert das."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: cc0c50ad-6ea5-4d75-b0d4-2e514a473ea3
  modified: 2026-08-30T17:34:28.046Z
---

Am 30.08.2026 blieb ein `if False:` in `app/ui/main_window.py` stehen. Die
Gegenprobe hatte sauber gebaut ausgesehen: Mutation schreiben, Test fahren, im
`finally` den Urtext zurückschreiben, dazu ein Hash-Vergleich gegen fremde
Schreibzugriffe. Das Zurückschreiben selbst warf `OSError [Errno 22]` — eine
Nachbarsitzung hatte die Datei im selben Moment offen —, und danach lief nichts
mehr, was es hätte merken können.

**Why:** Der Hash-Vergleich prüfte die falsche Richtung. Er beantwortete „hat
jemand anderes geschrieben?" und nicht „ist mein Rückbau angekommen?". Ein
`finally` sieht aus wie eine Garantie, ist aber nur ein *Versuch* — es garantiert,
dass der Block **läuft**, nicht dass er **gelingt**. Gemerkt habe ich es an einem
`grep`, das ich aus einem anderen Grund fuhr; das Skript meldete einen sauberen
Lauf. 72 hat den Fall auf sich angewandt und alle elf eigenen Mutationsdateien
gegen HEAD verglichen — dieselbe Prüfung, nur am Ergebnis statt an der Absicht.

**How to apply:**

* Rückbau **mit Wiederholung**: mehrere Versuche mit kurzer Pause, dann
  ausdrücklich abbrechen und sagen, dass die Datei die Mutation noch trägt.
* Danach **Endvergleich**: `datei.read_text() != urtext` → Alarm. Eine Zeile,
  und sie nimmt die Sorge ganz weg.
* Nach jeder Probenserie einmal `git diff HEAD -- <die mutierten Dateien>` —
  am Ergebnis prüfen, nicht am Skript.
* Im geteilten Baum gilt zusätzlich: Eine Probe, die eine Datei verändert, an
  der jemand anderes arbeitet, gehört eigentlich in einen eigenen Worktree
  ([[sonde-im-geteilten-baum]]). Die Wiederholung ist der billige Ersatz, wenn
  die Probe klein und kurz ist.

Dieselbe Familie wie [[text-gesetzt-heisst-nicht-gezeigt]] und
[[messwerkzeug-misst-sich-selbst]], eine Ebene tiefer: **geschrieben heißt
nicht angekommen.** Verwandt: [[index-altert-zwischen-lesen-und-commit]] — auch
dort war der Prüfschritt richtig und der Zeitpunkt falsch.
