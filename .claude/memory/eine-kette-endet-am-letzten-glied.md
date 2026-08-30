---
name: eine-kette-endet-am-letzten-glied
description: "Ein Rückruf, der durch drei Ebenen gereicht und nie aufgerufen wird — und ein Test, der hinter der Lücke ansetzt, mit einer zutreffenden Begründung."
metadata:
  type: feedback
---

**Gebaut, geprüft, nicht angeschlossen.** Am 23.08.2026 in Solidon dreimal an
einem Tag, bei drei Sitzungen: der Plattencache (64), das Ziehen eines Körpers
mit der Maus (b8/ich), der Feedbackbogen-Einhängepunkt. Beim Ziehen war die
Kette lückenlos bis auf das letzte Glied — `begin_body_drag`,
`begin_body_drag_at`, `continue_body_drag`, `finish_body_drag`, der Rückruf
`on_body_drag`, seine Übergabe an `_ViewCallbacks`. Im 175-Zeilen-Rumpf des
Interaktionsstils stand `on_body_drag` dann **genau einmal**: als Parameter.

Gezählt im selben Rumpf zum Vergleich: `on_pick` viermal erwähnt und
aufgerufen, `on_context` dreimal und aufgerufen. **Das ist der Griff, der es
findet** — nicht „gibt es die Funktion?", sondern „wie oft kommt ihr Name im
Rumpf vor, der sie rufen müsste?". Eins heißt: nie gerufen.

**Der Test war da und griff nicht.** Er setzte bei `begin_body_drag_at` an,
also **hinter** der Lücke, und begründete es im Docstring:

> „Offscreen rendert VTK nicht, und ein Picker über einem nie gezeichneten Bild
> trifft nichts — ein Test mit Pixelkoordinaten prüfte hier die Testumgebung."

**Diese Begründung ist wahr.** Sie war es beim Schreiben und ist es heute. Nur
folgt aus ihr nicht, dass der Teil davor ungeprüft bleiben darf — sie erklärt,
warum *dieser* Test dort ansetzt, nicht, warum kein anderer weiter vorn ansetzt.

**Why:** Eine falsche Begründung fällt beim Lesen auf. Eine richtige, die eine
Lücke deckt, liest sich wie eine Erklärung und beendet die Suche. Das ist
dieselbe Falle wie bei einer eleganten Ursache ([[messwerkzeug-misst-sich-selbst]],
Punkt 6): Wer eine Geschichte hat, die aufgeht, hört auf zu prüfen.

**Und die Probe darauf ist zweiteilig — die zweite Hälfte hatte ich lange
nicht.** Am 30.08.2026 habe ich zwei solcher Lücken geschlossen und beide mit
einer Mutation belegt: Griff zurückgebaut, Test wird rot, fertig. Das war die
halbe Antwort. Ein roter Test beweist, dass **mein** Test etwas merkt — nicht,
dass ihn jemand braucht. Erst die Frage „was tut dabei der **bestehende**
Test?" trennt die geschlossene Lücke von der doppelten Absicherung:

| Mutation | `test_units` (bestand) | der neue Test |
|---|---|---|
| `format_volume` verliert kleine Werte *(erstes Glied)* | rot | rot |
| `_show_tries` rechnet wieder selbst in cm³ *(letztes Glied)* | **grün** | rot |

Die erste Zeile hätte für sich genommen bewiesen, dass der neue Test
überflüssig ist. Die zweite ist der ganze Grund für ihn: Der Bestand sah einen
Bruch am letzten Glied nicht, und dem Kunden stand dabei `· 0.0 cm³ ·
geschlossen` da. **Eine Mutationsprobe an einer Kette braucht deshalb einen
Angriff je Glied, nicht einen für die Kette** — und die Zeile, auf die es
ankommt, ist die mit dem *grünen* Altbestand.

**Die schärfste Gestalt bisher, gemessen am 30.08.2026 (5d): Der Test, der
die Rechnung prüft, trug die Begründung des Wirkungsfehlers in seiner eigenen
Assert-Meldung.**

Der Startbildschirm — das Erste, was ein Kunde sieht — blieb bei 714 Pixeln
Breite, bei jeder Fenstergröße von 1280 bis 3413. Die Rechnung dahinter war
richtig: `_fit_the_columns` stellte auf 1360 und drei Kachelspalten um, sobald
der Platz da war. Nur **zieht `setMaximumWidth` nicht**, es erlaubt; zwischen
zwei Stretch-Feldern ohne eigenen Faktor bekam die Spalte ihre `sizeHint`.

Dafür gab es einen Test. Er prüfte `_columns == 3`, und seine Assert-Meldung
lautete:

> „die Breite ist da und wird nicht benutzt"

Genau das geschah, während er grün war. Der Satz beschreibt den Zustand, den
der Test nicht messen konnte — er misst die Entscheidung, nicht ihre Folge.

**Was daraus folgt, ist eine Frage an jeden Test mit einer erklärenden
Assert-Meldung:** Prüft er, was sein Satz behauptet? Wo der Satz von einer
*Wirkung* spricht („wird benutzt", „steht da", „kommt an") und die Zusicherung
eine *Entscheidung* liest (ein Flag, ein Zähler, eine gesetzte Eigenschaft),
liegt genau ein Glied dazwischen. Bei Qt ist dieses Glied besonders oft leer:
`setMaximumWidth`, `setEnabled`, `setVisible` und `setToolTip` sagen alle,
was erlaubt oder gesetzt **ist** — nicht, was der Kunde sieht.

**How to apply:**

1. **Nach dem Bauen den Namen im Rumpf zählen**, der ihn rufen müsste. Ein
   Vorkommen ist die Signatur, nicht der Aufruf.
2. **Testart „Anschluss" (AGENTS.md):** nicht „der Cache kann es", sondern „die
   Anwendung tut es". Der Test setzt an der **Geste** an, nicht an der Methode
   dahinter — bei Qt/VTK notfalls mit attrappiertem Interactor. `EndPan` ohne
   echten Interactor ist ein Segfault; die Kamera-Methoden legt man still.
3. **Wenn ein Docstring erklärt, warum ein Test tiefer ansetzt, ist die Ebene
   darüber ungeprüft.** Das ist kein Verdacht, das ist die Aussage des
   Docstrings. Ein zweiter Test gehört dorthin.
4. Verwandt: [[text-gesetzt-heisst-nicht-gezeigt]] — dort ist der Wert gesetzt
   und wird nicht angezeigt; hier ist der Rückruf gesetzt und wird nicht
   gerufen. Dieselbe Familie.

**Die dritte Gestalt, gefunden am 30.08.2026: der Kern verweist auf etwas, das
die Oberfläche wegwirft.** `AppError.values` trägt Adresse, Knotenname und die
Fehlerzeile des fremden Programms; drei Kern-Stellen schreiben in ihren
`detail` wörtlich „steht daneben", und eine schreibt im Kommentar sogar „der
Dialog hängt die values als eigene Zeilen darunter". Tat er nicht — `show_error`
baute seinen Text aus `title`, `detail` und dem Rat. Der Kunde las „Der Anfang
der Antwort steht daneben", und daneben stand nichts.

Der Unterschied zu den drei Fällen oben: Hier **fehlt kein Aufruf**, hier
endet die Zusage an einer Schichtgrenze. Der Kern hat seinen Teil getan, die
Oberfläche ihren nicht, und keine der beiden Seiten liest die andere.

Der Griff dafür ist ein anderer und ebenso billig: **Nach dem Verweis suchen,
nicht nach dem Namen.** Wer im Kern „daneben", „darunter", „siehe dort" oder
„die Zahlen stehen in" schreibt, hat eine Zusage an eine andere Schicht
gegeben — `grep -rn "steht daneben" app/core/` beantwortet in einer Sekunde,
ob sie eingelöst ist.
