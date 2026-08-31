---
name: schwelle-misst-die-falsche-achse
description: "Dieselbe Klasse Fehler, die eine Messung wertlos macht, steckt auch im ausgelieferten Code — dort trifft sie den Kunden, und je schlimmer der Fall, desto stiller wird sie."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5f85192a-8b20-4339-ba08-13913837d58c
  modified: 2026-08-31T09:19:54.942Z
---

Am 31.08.2026 habe ich einen ganzen Vormittag lang Messungen gebaut, die eine
andere Frage beantworteten als die gestellte — dreimal hintereinander, jedes
Mal gefangen. Danach fand ich denselben Fehler in `app/core/geom/mesh_ops.py`,
seit Monaten ausgeliefert.

`SIMPLIFY_MISSED` entschied, ob eine Vereinfachung sich beim Kunden meldet.
Sie fragte: **wie viel wurde gegenüber dem Eingang reduziert?** Gemeint war:
**wie weit liegt das Ergebnis am Ziel vorbei?**

| verlangt | bekommen | daneben | meldete |
|---|---|---|---|
| 400 | 992 | 2,5× | ja |
| 600 | 74 592 | **124×** | **nein** |

Die Schwelle belohnte kräftige Reduktion mit Schweigen. **Je schlimmer der
Fall, desto stiller** — und das ist kein Zufall dieses Falles, sondern die
Signatur der ganzen Klasse: Wenn eine Prüfung auf der falschen Achse steht,
wächst der Fehler oft genau dort, wo die Prüfung nach unten zeigt.

**Why:** Ich hatte diese Klasse den ganzen Tag als *Messfehler* behandelt — als
etwas, das man beim Prüfen vermeidet. Sie ist aber genauso ein *Codefehler*,
und dort kostet sie mehr: Eine Messung, die die falsche Frage stellt, führt
mich in die Irre; eine Schwelle im Produkt, die die falsche Frage stellt,
führt jeden Kunden in die Irre, und niemand merkt es, weil sie ja meldet — nur
in den falschen Fällen.

Der Docstring daneben war vollständig, richtig und half nicht: Er erklärte
sorgfältig, warum „ein paar Dreiecke neben der Vorgabe" kein Befund sind. Die
Absicht war goldrichtig, nur die Achse war falsch gewählt — und ein Kommentar,
der die Absicht gut begründet, liest sich als Beleg, dass die Umsetzung sie
trifft. Vergleiche [[benannte-falle-schuetzt-nicht]].

**How to apply:** Bei jeder Schwelle, jedem Filter, jeder `if`-Bedingung, die
entscheidet, ob etwas gemeldet wird: **die Größe hinschreiben, die sie misst,
und die Größe, die gemeint ist.** Stehen dort zwei verschiedene Sätze, ist die
Achse falsch — auch wenn die Zahl für die häufigen Fälle stimmt.

Der Griff, der es hier aufgedeckt hat, war der aus
[[suche-prueft-ihre-eigene-trefferzahl]]: eine **Gegenzahl** in derselben
Ausgabe. Meine Messtabelle zeigte „Ziel 20 000 → 74 592" und „Ziel 600 →
74 592" nebeneinander — dieselbe Zahl für zwei verschiedene Vorgaben ist ein
Widerspruch, den man nicht übersieht. Ohne die Ist-Spalte hätte ich nur
gesehen, dass keine defekten Kanten entstehen, und den Fall abgehakt.

Verwandt: [[gemessene-frage-ist-nicht-die-gestellte]] (dieselbe Wurzel im
Messen) und [[zwei-schwellen-eine-frage]] (dort liegt zwischen zwei Schwellen
ein Bereich, in dem beide Antworten falsch sind — hier steht eine Schwelle auf
der falschen Achse).
