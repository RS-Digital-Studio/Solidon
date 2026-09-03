---
name: renderfenster-bleibt-briefmarkengross
description: "In dieser Umgebung bleibt VTKs Renderfenster bei 160x160, egal wie groß Fenster und Widget sind — jede Messung in Bildpunkten misst damit die Umgebung."
metadata: 
  node_type: memory
  type: project
  originSessionId: e44e7ebf-a72f-4543-a02a-0efbcc35b48d
  modified: 2026-09-03T17:05:14.327Z
---

Ein Prüfstand, der ein echtes Solidon-Fenster öffnet (1400×900) und den
Viewport auf 1000×700 zwingt, bekommt trotzdem:

    Viewport-Widget:    1000 x 700
    VTK-Renderfenster:  160 x 160

Das Renderfenster folgt der Widget-Größe hier nicht. Gemessen am 03.09.2026.

**Why:** Alles, was VTK in Bildpunkten rechnet, hängt daran — Pan, Rotate, das
Verhältnis „ein Zug von 120 Punkten trägt wie weit". Ein Zug über 120 Punkte
bewegte die Kamera um das 5,33-fache dessen, was den Punkt unter dem Zeiger
stehen ließe. Das sieht nach einem groben Bedienfehler aus („Verschieben ist
fünfmal zu schnell"), ist aber nicht von der Anwendung zu trennen, solange der
Renderer 160×160 meldet und die Ereignisse in einer anderen Skala kommen. Beim
Kunden sind beide Skalen dieselbe.

**How to apply:** Kamerabewegungen relativ zur **Entfernung** messen, nicht in
Bildpunkten und nicht in Millimetern — dieser Anteil ist von der
Fenstergröße unabhängig (eine Sekunde Flug = eine Entfernung, ein Kippschritt
= 23 % der Entfernung). Wo eine Frage doch an Bildpunkten hängt („klebt der
Inhalt am Zeiger?"), ist sie hier **nicht** zu beantworten: Robert fühlt sie in
zwei Sekunden am echten Bildschirm, ein Prüfstand hier nie. Und die
Widget-Größe vorher ausgeben — nach `show()` steht sie ohne Zutun auf 160×160,
weil das Layout erst durchrechnet, wenn das Fenster wirklich auf dem Schirm
ist.

Verwandt: [[messwerkzeug-misst-sich-selbst]], [[qt-luegt-vor-dem-anzeigen]],
[[pruefstand-misst-seine-nachstellung]], [[vtk-sagt-ja-und-tut-nichts]].
