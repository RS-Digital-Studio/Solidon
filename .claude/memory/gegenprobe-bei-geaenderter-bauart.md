---
name: gegenprobe-bei-geaenderter-bauart
description: "Eine Mutation an der neuen Zeile prüft nicht, ob der alte Fehler gefangen wird — wenn der Fix die Bauart ändert, muss die Gegenprobe die alte nachbauen."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 4e2b249b-1d42-4020-bb0e-bdcf350ef625
  modified: 2026-08-30T05:50:23.261Z
---

Am 30.08.2026 am ComfyUI-Startzustand: Der Abbruch stand erst als Merkmal am
Dialog und wanderte dann ans Ergebnis (`StartResult.stopped`). Die Gegenprobe
mutierte `if start_result.stopped:` zu `if False:` — und **der Test blieb
grün**.

Der Grund ist die Bauart selbst: Mit dem Zustand am Ergebnis kehrt der
Erfolgszweig vorher zurück, die mutierte Zeile wird im geprüften Ablauf nie
erreicht. Die Mutation bestätigte nur, dass die neue Zeile erreichbar ist —
und das war sie nicht einmal.

Rot wurde die Probe erst, als sie die **alte Bauart nachbaute**: Merkmal am
Dialog, gesetzt beim Abbrechen, gelesen beim Ergebnis. Dann fiel der Test mit
genau dem Satz, um den es ging: „der Fehlschlag wurde verschluckt: 'ComfyUI:
Lokales Backend läuft jetzt.'"

**Why:** Eine Gegenprobe soll zeigen, dass der Test **den Fehler** fängt, nicht
dass die neue Zeile läuft. Wo ein Fix einen *Wert* ändert, treffen sich beide
Fragen; wo er die *Bauart* ändert, fallen sie auseinander — und die bequeme
Mutation beantwortet die falsche.

**How to apply:** Vor der Mutation fragen: *Ändert der Fix einen Wert oder eine
Bauart?* Bei einem Wert genügt die Zeile. Bei einer Bauart wird der alte
Zustand nachgebaut — das ist mehr Arbeit und die einzige Probe, die etwas
aussagt. Ein Zeichen für den Unterschied: Wenn die Mutation grün bleibt, ist
sie nicht zu schwach, sondern sie prüft die falsche Frage.

Siehe [[fix-der-nicht-gruen-macht]] (dieselbe Logik in der anderen Richtung)
und [[waechter-zaehlt-das-falsche]].
