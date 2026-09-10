# Wo geht die Zeit beim Bewegen hin? (10.09.2026)

Zwei Prüfstände am **echten** Fenster — offscreen gibt es keinen Renderer, und
dann misst man den Rückfall statt der Sache. `WA_DontShowOnScreen` hält das
Fenster dabei vom Bildschirm fern.

```
.venv\Scripts\python.exe .claude\.state\tempo-2026-09-10\tempo.py ergebnis.txt
.venv\Scripts\python.exe .claude\.state\tempo-2026-09-10\leerer-pick.py leer.txt
```

`tempo.py` legt Stoppuhren um jede Stelle, die ein Zeigerereignis durchläuft,
und fährt drei Gesten: bewegen ohne Taste, drehen, schieben. Dazu drei
Drehrunden nacheinander mit den Zeiten **je Ereignis** — ein Ausreißer beim
ersten ist ein Aufwärmen, einer in der Mitte ist ein Fehler.

`leerer-pick.py` beantwortet die Frage, die daraus folgte: Baut ein Pick auf
der leeren Szene schon die Pipeline auf? Ja — 420 ms leer, danach 4,4 ms am
geöffneten Modell.

## Was der erste Lauf ergab

| Geste | Median je Ereignis | Höchstwert |
|---|---|---|
| bewegen ohne Taste | 0,00 ms | 0,14 ms |
| Kamera drehen | 0,39 ms | **494 ms** (nur das erste Ereignis) |
| Kamera schieben | 0,35 ms | 4,40 ms |

Der Ausreißer war der erste `pick_surface` überhaupt — der Aufbau des
wgpu-Renderdurchgangs für die Kennungen. Er traf, wer als Erstes klickte
(505 ms) oder als Erstes drehte (485 ms), und danach nie wieder. Behoben über
`Viewport._warm_the_picker`; die Regel steht in `.claude/rules/ansicht.md`.

## Drei Fallen dabei

* **Der Prüfstand klickt schneller als jeder Mensch.** Ohne eine Sekunde
  Bedenkzeit nach dem Öffnen feuert der Aufwärm-Timer erst nach dem Klick, und
  die Messung zeigt die alte Zahl.
* **Das Renderfenster bleibt 160×160.** Für einen Pick ohne Belang, für jede
  Messung in Bildpunkten nicht.
* **Millimeter sagen nichts**, weil jede Kamerabewegung mit der Entfernung
  skaliert. Gemessen wird Zeit.

## Eine Falle beim Nachmessen, die es vorher nicht gab

Seit `Viewport._warm_the_picker` wärmt die **Anwendung selbst** beim Start auf.
`leerer-pick.py` misst danach 3,2 statt 420 ms auf der leeren Szene — nicht
weil die Pipeline billig geworden wäre, sondern weil sie schon steht. Wer die
ursprüngliche Zahl sehen will, nimmt den Aufruf in `_apply_scene` für einen
Lauf heraus; wer prüfen will, ob die Behebung noch wirkt, liest genau diese
3,2 ms als Beleg.
