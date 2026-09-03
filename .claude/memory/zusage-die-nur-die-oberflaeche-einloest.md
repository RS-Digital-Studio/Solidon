---
name: zusage-die-nur-die-oberflaeche-einloest
description: "Ein Vertrag, den nur das Menü durchsetzt, ist keiner — Chat, Kommandozeile und Agent gehen daran vorbei, und das Ergebnis ist wasserdicht und falsch."
metadata:
  node_type: memory
  type: feedback
---

`applies_to` sagt je Operation, welche Merkmalsarten sie annimmt. Es stand bis
zum 03.09.2026 nur im Menü und im Merkmalspanel: Beide grauten aus, was nicht
paßte, und niemand hatte je gemessen, was die Auswertung selbst tut.

Sie tat es nicht. Gemessen an dem Tag:

- `resize_feature` (Register: Zapfen, Kegel, Kugel) auf eine **Bohrung**
  gerufen lief durch und machte aus 46 997,6 mm³ 45 737,0 — am exakten Kern
  und an der Materialkompensation vorbei, die für ein Loch anders läuft als
  für einen Zapfen. Der Kunde bekäme ein Loch, das beim Drucken zu eng wird.
- `rotate_feature` (Register: Bohrung, Zapfen, Kegel) auf eine **Kuppel**
  gerufen lief ebenfalls durch und nahm 112 von 24 448 mm³ mit.

Beide Male blieb der Körper wasserdicht, und **kein Test wurde rot**.

**Why:** Solidon hat drei Türen zum selben API — Menü, Kommandozeile, Chat.
Eine Prüfung in der Oberfläche schützt genau die Kunden, die durch die
Oberfläche gehen. Die anderen bekommen kein „geht nicht", sondern ein
Ergebnis; und ein falsches Ergebnis ohne Fehlermeldung ist der teuerste
Fehler, den es gibt. Dieselbe Regeldatei sagte übrigens seit langem das
Richtige — „der gute Satz im Kern bleibt, er ist die zweite Hürde, nicht die
erste" —, und die zweite Hürde gab es trotzdem nicht. Siehe
[[benannte-falle-schuetzt-nicht]].

**How to apply:** Wo eine Eigenschaft im Register steht und die Oberfläche
sie liest, muß der Kern sie **selbst** prüfen, bevor er handelt. Die Prüfung
fragt den eigenen Registereintrag, nicht eine Liste im Modul: Eine Liste
daneben weiß beim nächsten Eintrag die Hälfte. Und den Satz zur Absage holt
sich der Kern von dort, wo die Oberfläche ihn auch hernimmt — sonst stehen
zwei Auskünfte über dieselbe Sache im Programm, und eine davon altert
unbemerkt ([[texte-altern-mit-ihrer-grenze]]). Der Wächter dazu prüft beide
Seiten gegeneinander, nicht jede für sich: „was das Panel ausgraut, lehnt der
Kern ab, und mit demselben Wortlaut".
