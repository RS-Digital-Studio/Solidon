# Platzieren ohne Dialog — Stelle, dann Tiefe (09.09.2026)

> **Stand:** Entwurf. Die erste Stufe ist gebaut (der Umriss auf der
> Oberfläche, `mouth_outline`); die zweite — Tiefe durch Ziehen — ist
> beschrieben und nicht beauftragt. Die Befunde stammen aus Roberts Runde
> durch die laufende Anwendung am 09.09.2026.

## Der Anlass

Drei Beobachtungen an einem Abend, alle beim Setzen einer Bohrung:

> „bei der vorschau mit der bohrung ist es noch relativ langsam"
>
> „es wäre besser, wenn wir eher den Hohlraum am Körper sehen, als den
> Zylinder der Bohrung der durch das Material geht"
>
> „wenn wir bohrung setzen anwählen wollen wir gleich über den viewport die
> bohrung setzen, über den dialog geht auch, aber man soll keinen extra button
> klicken müssen"

Und, nach Rückfrage, was genau stört:

> „der zylinder außerhalb und dass man nicht genau sieht wo das loch ist, vor
> allem wenn man noch dabei die ansicht dreht und bewegt"
>
> „es reicht mir, wenn ich den kreis auf der oberfläche in orange sehe"
>
> „höchstens dann wenn man die tiefe noch einstellt wäre die andere ansicht
> interessant"

Der letzte Satz trägt den ganzen Entwurf: **Der Körper zeigt genau eine Sache,
die der Kreis nicht kann — die Tiefe.** Also zeigt man ihn dort und sonst nicht.

## Was gebaut ist (Stufe 1)

| | vorher | jetzt |
|---|---|---|
| Was man beim Zeigen sieht | halbtransparenter Zylinder, auch außerhalb des Materials | der Umriss der Mündung auf der Fläche, in der Farbe des Abgetragenen |
| Wie der Modus startet | Klick auf „Im Modell platzieren" | von selbst, sobald eine platzierbare Operation gewählt ist |
| Flächenerkennung je Mausbewegung | 4,4 ms im Median, 52 ms im schlechtesten Fall | 0,1 ms und 4,6 ms |

`placement.mouth_outline` liegt im Kern und liefert den Umriss in U/V der
Mündungsebene — bei einer Bohrung Ø5 sind das 32 Punkte auf Radius 2,60 mm.
Der Werkzeugkörper wird weiter **gebaut** (an ihm hängt, ob gesetzt werden
kann) und nur nicht mehr **gezeigt**, solange es einen Umriss gibt. Ein
Werkzeug ohne Mündung in der Fläche — eine Mutternfalle etwa — behält ihn,
weil er dort die einzige Auskunft ist.

## Was Robert für Stufe 2 entworfen hat

> „evtl das platzieren ohne dialog, wenn man ihn platziert sieht man die
> bohrung von der seite transparent das modell und stellt die tiefe ein, da
> können wir aber auch über den viewport machen dann einfach die maus nach
> unten oder so bewegen und man sieht die länge, mit maßeingabe abständen usw"

Als Ablauf gelesen:

```
Operation wählen
   │
   ▼
Stufe 1  — zeigen und setzen
   Der Umriss folgt dem Zeiger, Abstände zu den Kanten stehen als Maßfelder da.
   Klick legt die Stelle fest.
   │
   ▼
Stufe 2  — Tiefe
   Das Modell wird durchscheinend, die Bohrung ist von der Seite zu sehen.
   Die Maus nach unten zieht die Tiefe auf; die Länge steht als Zahl daneben
   und ist eintippbar.
   │
   ▼
Bestätigen  → eine Operation, ein Schritt im Verlauf
```

## Was daran schon trägt

Vier Dinge sind vorhanden und müssten nicht neu gebaut werden:

1. **Der zweistufige Zustand.** `PlacementFlow` hat `active`, `_frozen` und
   `_commit_pending` — die Maschinerie für „Stelle steht, Eingabe läuft
   weiter" ist da.
2. **Die Maßfelder mit Zahleneingabe.** `_measures` und `_centre_measures`
   sind `LengthSpin`-Felder an der Maßlinie; ein Tiefenfeld wäre das fünfte
   derselben Art, samt Ausdrucksmodus und Einheitenumschaltung.
3. **Der Werkzeugkörper.** Er wird bereits gebaut und ist in Stufe 2 genau
   das, was gezeigt werden soll — die Sichtbarkeit ist heute schon eine
   Bedingung und keine feste Zusage.
4. **Regel 2 bleibt gewahrt.** Der Entwurf sammelt Gesten in Parameterwerte,
   und die Geometrie entsteht bei der Auswertung — genau der Fall, den
   `AGENTS.md` ausdrücklich erlaubt („Eine Op darf beliebig viele Nutzergesten
   zu einem Schritt zusammenfassen").

## Sieben offene Entscheidungen

Keine davon ist technisch schwer; jede ändert die Bedienung.

1. **Wann endet Stufe 1?** Klick und loslassen, oder gedrückt halten und
   ziehen? Ein Klick ist verträglicher mit dem heutigen Ablauf, ein Ziehen
   spart einen Zug.
2. **Was tut die Maus in Stufe 2?** „Nach unten" ist im Bild nicht dasselbe
   wie „in den Körper hinein" — bei gedrehter Ansicht zeigt die Bohrachse
   irgendwohin. Kandidaten: die Bewegung auf die Achse projizieren (richtig,
   aber bei achsparalleler Sicht mehrdeutig), oder immer die Bildschirm-Y-Achse
   (vorhersagbar, aber falsch, sobald die Ansicht steht).
3. **Wie kommt man zurück?** Esc bringt heute den Dialog. Braucht Stufe 2 ein
   eigenes Zurück in Stufe 1?
4. **Wie durchscheinend wird das Modell?** Und was passiert mit den anderen
   Körpern der Szene — die stören beim Blick auf den Schnitt.
5. **Was ist die Tiefe bei einem Baustein?** Eine Mutternfalle hat eine, ein
   Lochwand-Einhänger nicht. Ohne eine Regel dafür hat Stufe 2 an der Hälfte
   der platzierbaren Operationen keinen Sinn — denkbar ist, sie an
   `mouth_outline` zu koppeln: Wer keinen Umriss hat, hat auch keine
   Zieh-Tiefe.
6. **Was, wenn die Tiefe schon im Dialog steht?** Ein Wert, den der Kunde
   eingetippt hat, darf eine Mausbewegung nicht stillschweigend überschreiben.
7. **Gilt der Selbststart auch für Stufe 2?** Also: Wird nach dem Klick sofort
   gezogen, oder erst nach einer weiteren Geste?

## Die Frage, die vor allen anderen steht

**Ist das der Weg für alle platzierbaren Operationen oder nur für Bohrungen?**
Es gibt 32 Bausteine und mehrere bohrende Operationen; ein Ablauf, der nur bei
einer davon greift, ist ein Sonderfall in der Bedienung — und §2 sagt, dass
Vielseitigkeit in die Tiefe gehört und nicht an die Oberfläche.

Der Umriss aus Stufe 1 beantwortet das schon auf seine Art: Er erscheint, wo
das Werkzeug eine Mündung in der Fläche hat, und wo nicht, bleibt es beim
Körper. Dieselbe Unterscheidung könnte Stufe 2 tragen.

## Was daran gemessen ist

- Die Zeiten der Flächenerkennung (4,4 / 52 ms vorher, 0,1 / 4,6 ms nachher)
  an `Filamenthalter-Solidon3D.p3d` und `-M6.p3d`, 09.09.2026.
- Der Umriss einer Bohrung Ø5: 32 Punkte, Radius 2,60 mm — mit der
  Kompensation aus dem Materialprofil, nicht dem Nennmaß.
- Die Kosten der Alternativen zum Umriss, an Roberts Modell:
  Schnittmenge 4,0 ms, Differenz 6,0 ms, beide ohne Rückfallstufe. Sie
  scheiden nicht am Preis aus, sondern daran, dass sie an der **Position**
  hängen und damit bei jeder Mausbewegung neu wären.

## Was daran Vermutung ist

- Dass „Maus nach unten" sich gut anfühlt, ist nicht erprobt — die
  Projektionsfrage aus Punkt 2 entscheidet es.
- Ob ein durchscheinendes Modell die Bohrung wirklich lesbar macht, hängt am
  Renderer und ist nicht gemessen.
