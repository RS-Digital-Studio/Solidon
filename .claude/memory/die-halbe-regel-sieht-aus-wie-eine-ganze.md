---
name: die-halbe-regel-sieht-aus-wie-eine-ganze
description: "Eine Prüfung, die den Hauptwert kennt und seinen Nachbarn nicht, fällt niemandem auf — man liest zwei ordentliche Prüfungen und glaubt, die Funktion tue ihre Aufgabe. Gemessen: ein Feld von sieben."
metadata:
  type: feedback
---

`_from_machine` in `slice/advise.py` trug den Satz „Was die Maschine nicht kann,
muss vor dem Druck gesagt werden" im Docstring. Am 03.09.2026 systematisch
gemessen: Es löste ihn für **ein** Feld von sieben ein.

| geprüft | nicht geprüft |
|---|---|
| `temperature.nozzle` | `temperature.nozzle_first_layer` |
| `layers.layer_height` | `layers.first_layer_height` |
| | `temperature.bed`, `temperature.bed_first_layer` |
| | `layers.line_width` nach unten |

Der Kunde konnte 400 Grad erste Schicht und 150 Grad Bett einstellen — das
Feld erlaubt es, sein Drucker kann 260 und 100, und der Bericht blieb leer.

**Why:** Das Muster ist immer dasselbe — geprüft wird der Hauptwert, nie sein
`_first_layer`-Nachbar. Und genau deshalb fällt es nicht auf: Wer die Funktion
liest, sieht zwei ordentliche Prüfungen und schließt, sie tue ihre Aufgabe.
Eine ganz fehlende Regel sucht man; eine halbe hält man für vollständig.

Dieselbe Form an anderer Stelle desselben Tages: Die Plattenverteilung
gruppierte nach dem Spulennamen und kannte das Material am Teil nicht; die
Auswahl der Slicer-Felder las die Übersetzungstabelle und kannte zwei weitere
Wege nicht.

**How to apply:** Wer eine Regel für einen Wert schreibt, schreibt sie für
seine **Geschwister** mit — jedes `_first_layer`, jedes `_max`, jedes zweite
Ende eines Paares. Und statt fünf Einzelregeln entsteht besser eine Tabelle
plus ein Wächter, der sie durchgeht: `MACHINE_LIMITS` nennt jedes Feld mit
einer Maschinengrenze, und der Test setzt jeden Wert darüber und verlangt ein
Wort. Fünf Regeln beheben fünf Fälle; die Tabelle behebt die Klasse — und ein
sechstes Feld ohne Eintrag macht den Lauf rot.

Die Frage, die es findet, ist billig und heißt nicht „ist die Regel richtig",
sondern: **Für welche Werte gilt sie, und welche davon prüft sie wirklich?**
