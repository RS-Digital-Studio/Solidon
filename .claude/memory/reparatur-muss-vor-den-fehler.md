# Eine Reparatur hinter dem Fehler läuft nie

Ein Operationsstapel stoppt am ersten fehlerhaften Schritt. Wird die
vorgeschlagene Reparatur einfach angehängt, erreicht die Auswertung sie nicht;
der Knopf ist sichtbar verdrahtet und funktional trotzdem leer.

Für „Reparieren und erneut versuchen“ gilt deshalb:

- lebende Ziele aus den gespeicherten Eingängen des Fehlerschritts bestimmen,
  nie aus der aktuellen Auswahl;
- die Handlung nur am wirklich angehaltenen Schritt oder für einen
  ausdrücklich benannten, noch vorhandenen Körper anbieten;
- Operationen mit einzeln bearbeitbaren Flächen und Kanten ausschließen — die
  Netzreparatur würde ihre Bauart zerstören und der neue Versuch sicher halten;
- den vollständigen Suffix ab dem Fehler entfernen und neu planen;
- je eindeutigem Eingang eine Reparatur voranstellen;
- alte Fassungen und neue Operationen in genau einer Transaktion tragen;
- Solver leeren, aber Parameter, Ein- und Ausgänge, Startwert, übersetzbare
  Parameter und Merkmalszuordnungen erhalten;
- nach einem bereits ausgeführten Reparaturzug denselben Reparaturknopf im
  Bericht sperren, solange dieser Zug aktiv ist;
- den Knopf beim ersten Klick sofort sperren, bevor die neue Auswertung fertig
  ist — zwei schnelle Klicks bleiben genau eine Transaktion.

Die Gegenprobe braucht einen Teilerfolg: Eine fehlende Wand lässt sich nicht
erfinden. Der erste Klick schließt die kleinen Löcher, der erneute Schritt
stoppt ehrlich, und der Bericht bietet danach „Stellen zeigen“ statt desselben
Rings. Ein Undo stellt den ursprünglichen Suffix und den ersten Knopf wieder
her.
