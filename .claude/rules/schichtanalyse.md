---
paths:
  - "app/core/slice/**/*.py"
  - "app/core/perceive/**/*.py"
---

# Regeln für Schichtanalyse und Wahrnehmung

## Die Abgrenzung, die nicht verhandelbar ist

Formwerk baut **keinen G-Code-Slicer**. Die Datei, die auf den Drucker geht,
kommt vom externen Slicer. Was hier entsteht, ist Analyse: Ebene-Mesh-Schnitt,
Konturen, Kennzahlen — in Millisekunden, ohne Fremdprozess.

**Kennzahlen aus Schichtanalyse und G-Code werden nie vermischt** (Regel 14).
Jeder Wert weist seine Herkunft aus. Ein geschätztes Stützvolumen aus der
Schichtanalyse ist etwas anderes als ein gemessenes aus dem G-Code, und der
Prüfbericht sagt welches.

Beschriftung in der Oberfläche: „Schichtanalyse", nicht „Vorschau". Sie zeigt
die Geometrie, nicht die Werkzeugwege.

## Was die Analyse liefert

Überhangfläche je Schicht, Stützvolumen, Querschnittsverlauf, **Inseln**
(Konturen ohne Verbindung nach unten), erste Schichtfläche, Brückenweiten,
kleinste Strukturbreite gegen den Düsendurchmesser. Der Gewinn ist der
Maßstab: hunderte Rotationen in der Orientierungssuche statt drei extern
geslicter Kandidaten.

## Stabile IDs

Feature-Erkennung liefert Provenienz-IDs, an denen Ops und Passungen hängen.
Eine ID muss eine Neuberechnung überleben — sonst zeigt der Op-Stack nach der
nächsten Änderung ins Leere. Mehrdeutige Zuordnung hält an und fragt, statt
die nächstbeste zu nehmen.

Analysekarten sind teuer: sie laufen im Hintergrund, sind abbrechbar und
halten das Budget aus §31 ein (Wandstärke unter 3 s, Schichtanalyse bei
200 000 Dreiecken und 0,2 mm unter 300 ms). Farbskala wahrnehmungsgleich, nie
Regenbogen.
