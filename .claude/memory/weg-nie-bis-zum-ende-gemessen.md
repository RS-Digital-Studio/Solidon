---
name: weg-nie-bis-zum-ende-gemessen
description: Ein Weg, der nie bis zum Ende lief, ist an jeder Stelle ungeprüft — zwölf Tag-Läufe, zwölf verschiedene Orte, kein einziger Fehler zweimal
metadata:
  type: project
---

Das Release 0.3.0 brauchte in der Nacht vom 02. auf den 03.09.2026 **zwölf
Tag-Läufe**. Jeder scheiterte an einer anderen Stelle, und **keine einzige
Ursache wiederholte sich**: Suite auf drei Plattformen (Speichergrenze auf
Darwin, Deskriptorpfade, bash 3.2, Schriftmetrik, Tokendatei, hidapi), dann
die Paketjobs (Byte-Nachweis über erzeugte Beispiele, GCC-Fassung aus dem
Interpreter, OpenSSL 3.0.13 statt 3.0.21), dann die Prüfjobs (`build/` gab es
nicht, Verzeichniseintrag im tar als `//` gelesen, `from tools import` ohne
Stamm im Pfad, `$LASTEXITCODE` nach einer Warnung), dann der Upload selbst
(die Argumentprüfung wies die Pakete ab, die sie hochladen soll; eine
`.jsonl` des Zählers galt als unbekanntes Medium).

**Why:** Bis dahin hatte die CI die Matrix nie zu Ende gefahren, und die
Releaseakte war nie über ein echtes Paket gelaufen. Jede Zeile hinter der
ersten Abbruchstelle war damit ungeprüft — nicht falsch geschrieben, sondern
nie ausgeführt. Der Aufwand entstand nicht durch schlechten Code, sondern
dadurch, dass zwölf ungeprüfte Stellen hintereinander lagen und jede erst
sichtbar wurde, wenn die davor fiel.

**How to apply:** Bei einem Weg, der zum ersten Mal ganz laufen soll, mit
zehn Anläufen rechnen und sie nicht als Rückschläge werten — jeder deckt
genau eine ungeprüfte Stelle auf. Wer die Zeit nicht hat, misst vorher
gezielt die Stellen, die nie liefen (`workflow_dispatch` über den ganzen
Weg), statt sie beim Release zu finden. Und: Nach dem ersten vollständigen
Lauf ist der Weg belegt, nicht vorher — [[pruefjob-nur-beim-tag-hat-nie-gemessen]].
