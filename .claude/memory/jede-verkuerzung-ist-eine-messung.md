---
name: jede-verkuerzung-ist-eine-messung
description: "head, [:165], ein Kontextfenster, grep ohne Wortgrenze — vier Arten, die Ausgabe zu kürzen, und jede kürzt die Antwort mit."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: e44e7ebf-a72f-4543-a02a-0efbcc35b48d
  modified: 2026-09-03T00:10:39.761Z
---

Vier Fehlbefunde in **einer** Prüfung am 03.09.2026, alle selbst gefangen, alle
aus derselben Wurzel — ich suchte, ob die Website den unsignierten Stand in
allen sechs Sprachen erklärt:

| Griff | maß | die Antwort war |
|---|---|---|
| deutsche Suchwörter gegen übersetzte Seiten | ob *mein Wort* dort steht | die Texte sind übersetzt |
| `grep -c 'chmod'` | **Spra-chmod-ell** | „chmod" kommt nirgends vor |
| `t[start-260:start+90]` mit `[-260:]` | das Ende **vor** dem Treffer | der Treffer stand dahinter |
| `print(b[:165])` je Block | den Anfang jedes Absatzes | der Beleg stand ab Zeichen 166 |

Der letzte ist der teuerste, weil er wie Sorgfalt aussieht: Ich kürzte, um die
Ausgabe lesbar zu halten, und schnitt genau die Stelle weg, wegen der ich las.

> **Jede Verkürzung der Ausgabe ist selbst eine Messung — und sie beantwortet
> die Frage, die ich beim Kürzen im Kopf hatte, nicht die, die ich stelle.**

**Why:** Die drei bekannten Fallen ([[suche-prueft-ihre-eigene-trefferzahl]],
[[gemessene-frage-ist-nicht-die-gestellte]], [[waechter-zaehlt-das-falsche]])
warnen vor dem *Filter*. Diese hier sitzt eine Stufe später, im `head`, im
Slice, im Kontextfenster — dort, wo man nicht mehr misst, sondern nur noch
anzeigt. Genau deshalb prüft sie niemand.

**How to apply:** Wo der Befund „X fehlt" lautet, kommt vor der Meldung ein
**ungekürzter** Blick auf eine Stelle, an der X stehen müsste — und der
strukturelle Anker schlägt das Wort (`class="pruefhinweis"` zählte in allen
sechs Sprachen fünf, während meine Wortsuche vier Sprachen für leer hielt).
Wortsuchen bekommen `\b`. Und `[:N]` ist beim Suchen verboten: erst finden,
dann kürzen — nie umgekehrt.

Verwandt: [[zwei-zeilen-sind-nicht-die-funktion]] ist dieselbe Bewegung am
Quelltext statt an der Ausgabe.
