---
name: gefilterte-codeansicht-zeigt-keine-zugehoerigkeit
description: "Eine über grep gefilterte Codeansicht zeigt Einrückung, aber nicht, zu welchem Block eine Zeile gehört — für Fragen zum Kontrollfluss den Block zusammenhängend lesen"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 2f8c31f4-7257-4631-8686-eb5ef75b3986
  modified: 2026-09-07T08:20:56.595Z
---

Am 07.09.2026 habe ich einer Korrektur einer anderen Sitzung **richtig
misstraut und dann falsch geprüft** — und das Ergebnis der falschen Prüfung
Robert als Erklärung erzählt.

**Was ich tat:** Um zu prüfen, ob `_settle_sketch_view` sein Signal auch dann
sendet, wenn eine Ansicht gefunden wurde, habe ich den Rumpf so gelesen:

    sed -n "$n,$((n+75))p" datei | grep -n "emit\|return\|def \|found"

Heraus kam unter anderem:

    30:        if found is not None:
    31:            direction, up = table[found]
    43:            return found
    44:        self.sketchViewChanged.emit(found or "")

Aus den zwölf Leerzeichen in Zeile 43 habe ich geschlossen, das frühe
`return found` gehöre zu `if found is not None:` — das Signal würde also
ausgerechnet im interessanten Fall nie gesendet. Darauf habe ich eine
Hypothese gebaut und sie weitergegeben.

**Tatsächlich** stand zwischen 31 und 43 ein `if not sketching:`, und das frühe
`return` gehörte dorthin. Im Skizzenmodus wird **immer** gesendet. Die
Korrektur der anderen Sitzung war vollständig richtig.

> **Ein Filter erhält die Einrückung und entfernt die Zeilen, die
> Zugehörigkeit stiften.** Zwölf Leerzeichen können zu jedem umschließenden
> Block gehören; welcher es ist, steht in den Zeilen, die der Filter
> weggeworfen hat.

**Warum das besonders sticht:** Der Fehler lag nicht im Misstrauen, sondern in
der Methode. Eine Prüfung, die ich selbst gefahren habe, trage ich mit mehr
Gewicht vor als eine fremde Behauptung — „ich habe nachgelesen" schließt die
Frage. Eine falsche Eigenprüfung ist deshalb schlechter als geglaubte fremde
Auskunft. Dieselbe Mechanik wie in
[[geprueft-fuehlt-sich-wie-vollstaendig-an]]: die geleistete Prüfung fühlt sich
wie Vollständigkeit an.

**Wie ich das anwende:** `grep` darf einen Block **finden**, nie über ihn
entscheiden.

* Frage nach Vorkommen, Namen, Signaturen → Filter ist richtig.
* Frage nach Kontrollfluss („läuft die Zeile?", „in welchem Zweig?",
  „mit welcher Bedingung?") → den Block **zusammenhängend** lesen, also
  `sed -n 'a,bp'` ohne Pipe, und die Grenzen weit genug setzen.
* Und bei ungestagten Änderungen im Baum gegen **HEAD** lesen
  (`git show HEAD:pfad`), sonst prüft man einen Zwischenstand —
  siehe [[kein-stash-auf-fremder-arbeit]].
