# Eine Warnungsmarke ist semantischer Zustand

Eine kurzlebige Marke im 3D-Fenster besteht nicht nur aus ihren VTK-Aktoren.
Ein Aufbau derselben Szene — etwa nachdem eine Analysekarte fertig gerechnet
ist — kann die Aktoren aus dem Renderer nehmen, obwohl ihre Python-Referenzen
weiterleben. Dann meldet der Code „Marke vorhanden“, während der Nutzer nichts
mehr sieht.

Die Regel:

- Punkt, Text und Zielkörper bleiben für die ursprüngliche kurze Frist als
  semantischer Ansichts-Zustand erhalten.
- Ein Neuaufbau derselben `EvaluationResult` zeichnet daraus Ring und
  Beschriftung erneut, startet den Zeitgeber aber nicht neu. Ist der
  Zielkörper ausgeblendet oder liegt auf einer anderen gewählten Platte,
  bleibt die Marke bis zu ihrem Ablauf nur gemerkt und zeichnet nicht in den
  leeren Raum.
- Ein neues oder leeres Ergebnis verwirft semantischen Zustand und native
  Aktoren gemeinsam; derselbe Punkt könnte an neuer Geometrie etwas anderes
  bedeuten.
- Der Oberflächenbeleg klickt eine echte Berichtszeile, wartet auf die fertige
  Karte, prüft die Aktoren im nativen Renderer und wartet anschließend auch
  den Ablauf der Frist ab. Ein Screenshot direkt nach dem Klick allein sieht
  die Regression nicht.

Der Fund vom 31.08.2026 entstand beim Passungsbefund: Der Klick setzte Ring
und Beschriftung korrekt, die asynchron fertige Passungskarte baute die Szene
Millisekunden später neu auf und nahm beides wieder weg.
