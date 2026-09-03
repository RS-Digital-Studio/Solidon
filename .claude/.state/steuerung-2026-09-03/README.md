# Die Steuerung von Hand fahren

`fahre_steuerung.py` öffnet ein echtes Solidon-Fenster und fährt die
Navigation durch: die drei Maustasten, das Rad, die sechs Flugtasten, eine
unbelegte Taste und eine Flugtaste im falschen Schema. Gemessen wird die
Kamerastellung vorher und nachher.

```
.venv\Scripts\python.exe -u .claude\.state\steuerung-2026-09-03\fahre_steuerung.py
```

Exit 0 heißt: alles tut, was `_NAVIGATION` verspricht.

## Warum das kein Test ist

**Offscreen gibt es keinen Plotter.** Die Suite fährt mit
`QT_QPA_PLATFORM=offscreen`, und dort bleibt `Viewport.plotter` auf `None` —
ein Test kann VTK also gar nicht erst nach der Bewegung fragen. Die vier
Wächter in `tests/test_viewport_decisions.py` prüfen deshalb die *Tabelle*
(jedes Schema belegt jede Taste, jedes trägt einen Namen), und
`tests/test_spacemouse.py` prüft die *Rechnung*. Dass VTK die Bewegung, die
die Tabelle nennt, auch ausführt, prüft nichts davon — das ist die Lücke, die
dieses Werkzeug schließt. Zu fahren nach jeder Änderung an `_NAVIGATION`, am
Interaktionsstil oder an `camera_step`.

## Drei Fallen, alle gemessen am 03.09.2026

**Millimeter sagen nichts.** Jede Bewegung skaliert mit der Entfernung zum
Blickpunkt. In einer leeren Szene steht die Kamera anderthalb Millimeter vom
Blickpunkt, und ein voller Flugschritt ist dann 0,2 mm — was wie ein Befund
aussieht und keiner ist. Der Prüfstand setzt deshalb vor jeder Messung
dieselbe Ausgangslage (300 mm) und rechnet in Anteilen der Entfernung.

**Bildpunkte sagen hier gar nichts.** Das VTK-Renderfenster bleibt in dieser
Umgebung bei 160×160, auch wenn das Fenster 1400×900 misst und das Widget auf
1000×700 gesetzt wird. Fragen der Art „trägt ein Zug von 120 Punkten 120 Punkte
weit?" sind damit nicht zu beantworten — beim Kunden sind beide Skalen
dieselbe, hier nicht.

**Kein `session.apply`.** Ein Körper wäre schön, aber `apply` wartet auf seinen
Arbeiter, und dieser Prüfstand hält den Hauptthread. Für Kamerabewegungen
braucht es ihn nicht: Bett und Bauraum stehen ohnehin in der Szene.

## Und eine über den Prüfstand hinaus

Die Flugtasten wollen **gehalten** werden. Seit `866950b6` schaltet der
Anschlag den Flug nur ein; gefahren wird in einem eigenen Takt. Wer drückt und
sofort misst, sieht null Bewegung.
