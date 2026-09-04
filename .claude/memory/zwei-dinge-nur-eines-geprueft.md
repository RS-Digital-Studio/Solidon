---
name: zwei-dinge-nur-eines-geprueft
description: "Die Fehlerklasse hinter einem Abend voller Funde — zwei Dinge gehören zusammen, aber nur eines wird geprüft; die Zahl ist nur der häufigste Fall."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e44e7ebf-a72f-4543-a02a-0efbcc35b48d
  modified: 2026-09-03T20:55:50.397Z
---

Am 03.09.2026 fielen an einem Abend 39 Funde an, und fast alle hatten dieselbe
Form. Die erste Fassung des Musters (3d-druck-c7): **welche zwei Dinge hängen
an derselben Zahl, obwohl sie verschiedene Aufgaben haben?** Drei Fälle an
einem Tag — der Griff und die Marke teilten die Größe, dann die Lage, dann die
Lebensdauer. Dazu `select` und `measure` als derselbe Farbwert: Der Kunde kann
„gewählt" und „Vorschau" nicht unterscheiden, und wer den Code liest, auch
nicht.

**Die schärfere Fassung entstand am selben Abend:** Es muss gar keine Zahl
sein. `_view_offset` im Viewport rechnet den Plattenversatz richtig, seit sie
ihn kennt; ihr Docstring **zählt auf**, wer mitwandert — Merkmalsfläche,
Beschriftung, Griffscheibe, Differenz, Maße, Fangmarke. In `show_scene`
standen davon zwei. Die Rechnung war gepflegt, die Liste derer, die sie
auslösen, nicht.

Also: **Zwei Dinge, von denen nur eines geprüft wird.** Die geteilte Zahl ist
der häufigste Fall, nicht der einzige.

**Drei Spielarten, alle am 03./04.09.2026 belegt:**

1. **Zwei teilen eine Zahl** — Griff und Marke die Größe, `select` und
   `measure` den Farbwert.
2. **Eine Aufzählung in Prosa macht eine Zusage** — `_view_offset` zählt im
   Docstring auf, wer mitwandert; in `show_scene` standen zwei von sechs.
3. **Der Räumer existiert und wird nicht gerufen** — `clear_name()` hat einen
   Docstring, der genau verbietet, was ohne seinen Aufruf geschieht; der
   Knetschalter wird nach jedem Zug zurückgenommen, nur beim Betreten nicht.
   **Diese dritte ist die unangenehmste: Die Begründung steht schon da.** Wer
   die Stelle liest, findet einen Kommentar, der die Sache erklärt, und liest
   darüber hinweg, weil sie erklärt *aussieht*.

**Und die Gegenprobe dazu (3d-druck-c7):** Eine Funktion, die den
offensichtlichen Weg **nicht** geht, hat meistens einen Grund — und der steht
selten daneben. `_selected_bounds` las `_selected` direkt statt der Auskunft
daneben; der naheliegende Fix hätte die Kamera gar nicht mehr einpassen
lassen, sobald ein Merkmal gewählt ist. Ein Bedienfehler wäre durch einen
schlimmeren ersetzt worden, mit dem guten Gefühl, konsistent zu sein.

**Why:** Diese Fehler sind nie ein Absturz und nie eine rote Zeile. Sie sind
stumm, und stumm bleibt stehen — beide Viewport-Fälle waren seit v0.1.1 in
jeder ausgelieferten Fassung. Ein Docstring, der aufzählt, wirkt wie eine
Zusage und altert wie ein Kommentar; kein Test liest ihn.

**How to apply:** Bei jedem Fund fragen, was zu der gefundenen Sache **gehört**
und ob es dieselbe Prüfung hat. Wo eine Prosa-Aufzählung eine Zusage macht,
einen Wächter dagegen bauen — über den **Syntaxbaum**, nicht über `grep`: Ein
`grep` findet den Namen auch im Kommentar, und genau ein Kommentar behauptete
hier zwei Sitzungen lang, die Sache sei erledigt
([[zusicherung-wird-stumpf-ohne-rot-zu-werden]]). Verwandt und oft dasselbe von
der anderen Seite: [[reparierter-fehler-hat-zwillinge]],
[[die-halbe-regel-sieht-aus-wie-eine-ganze]], [[schutz-verliert-ein-geschwister]].
