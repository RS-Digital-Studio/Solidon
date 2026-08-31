---
name: zeuge-wird-beim-messen-ueberschrieben
description: "Im geteilten Baum ändert sich der Prüfling unter der Messung — vor jeder Wiederholung `git diff HEAD --stat` auf die gemessenen Dateien, bevor man den eigenen Messweg verdächtigt."
metadata:
  type: feedback
---

Am 31.08.2026 maß ich am elften Beispielprojekt einen Ort außerhalb seines
Körpers — die Kamera flog beim Klick auf eine Warnung ins Leere, belegt am
Bildschirmfoto. Zehn Minuten später gab dieselbe Messung einen richtigen Wert.
Ich habe daraufhin meinen Befund zurückgezogen, weil ich ihn nicht mehr
belegen konnte.

**Die Erklärung war einfach und lag in einer Datei, die ich nicht geprüft
habe:** Eine Nachbarsitzung hatte den Fehler in `app/core/scene/evaluate.py`
behoben und ihre 41 Zeilen **uncommittet im Arbeitsbaum** liegen. Ab ~12:20
maß ich den reparierten Code. Meine Tabelle liest sich damit lückenlos —
12:15/12:16 vor dem Fix falsch über *beide* Wege, ab 12:26 richtig über
*beide* Wege.

**Why — und das ist der eigentliche Fehler:** Ich *habe* auf Änderungen
geprüft, und zwar sorgfältig: `app/examples/*.p3d`, `lid.py`, `maps.py`,
Zeitstempel, `git diff HEAD`, kein Commit seit dem letzten Stand. Nur
`evaluate.py` war nicht dabei — die Datei, die Merkmale mitwandern lässt, also
genau der Prüfling.

Warum sie fehlte: Ich hatte eine Ursachen-Erzählung („`create_lid` schreibt
die Lage fest, `arrange_bed` überholt sie") und habe die Dateien geprüft, die
**zu dieser Erzählung** gehören. Die Prüfung folgte der Hypothese statt der
Messung. Danach habe ich Cache, Messweg und Reihenfolge durchprobiert — alles
aufwendiger als die eine Zeile, die gefehlt hat.

**How to apply:** Bevor man bei zwei abweichenden Läufen den eigenen Messweg
verdächtigt, **`git diff HEAD --stat` auf die gemessenen Dateien** — und
„gemessen" heißt: die Kette vom Eingang bis zur Zahl, nicht die drei, die man
für die Ursache hält. Drei Sekunden, und die Frage ist beantwortet.

Die zweite Hälfte, die mich mehr gekostet hat als die erste: **Wenn zwei Läufe
verschieden antworten, ist die Differenz selbst die Auskunft.** Meine zwei
Werte unterschieden sich um exakt −67 / +77 — die Körpermitte, also genau die
Verschiebung, deren Fehlen der Befund war. Die Zahl stand die ganze Zeit da.
Ich habe die Abweichung als Störung behandelt und Reproduktion gejagt, statt
sie auszurechnen.

Ausgegangen ist es gut, aber nicht durch mich: Die Nachbarsitzung fand die
Ursache **am Quelltext** — benannte Merkmale wandern nur mit einer gemeinsamen
Matrix mit, das Anordnen liefert keine; 6 von 11 Beispielen betroffen, nach
dem Fix 0. Meine Erzählung war richtig, und ich konnte sie mit meinen Mitteln
nicht mehr belegen.

Geschwister: [[zustandswert-widerlegt-keinen-haenger]] (dort war eine
Momentaufnahme zu wenig — hier war der Prüfling beweglich),
[[fremde-zwischenstaende-verfaelschen-messungen]],
[[geteilter-baum-misst-zeitpunkt]] und [[messung-galt-fuer-den-stand-davor]].
