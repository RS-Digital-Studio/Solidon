---
name: zahl-beschreibt-die-regel-nicht-das-bild
description: getComputedStyle liest nach einer Animation den Basiswert aus der CSS-Regel — der Bildschirm zeigt etwas anderes
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5f85192a-8b20-4339-ba08-13913837d58c
  modified: 2026-08-31T05:56:42.268Z
---

Am 31.08.2026 meldete meine Messung fünf unsichtbare Elemente im Hero der
Startseite — die H1, den Vorspann, den CTA, die gesamte Kernbotschaft:

```
unsichtbar im Bild: 5
  H1, P.hero-kicker, P.lead, P.hero-act, P.hero-kauf
  je animation: rise 0.55s
```

Gemessen nach **zwei Sekunden** Wartezeit bei 0,55 Sekunden Animationsdauer.
Das wäre der schwerste Befund des Tages gewesen. Der Screenshot derselben Lage
zeigte alles vollständig sichtbar.

**Die Ursache:** Nach einer abgeschlossenen CSS-Animation ohne
`animation-fill-mode: forwards` gibt `getComputedStyle(e).opacity` den
**Basiswert aus der Regel** zurück — hier `0` —, während der Bildschirm den
Endzustand zeigt.

**Why:** `getComputedStyle` heißt „computed" und klingt nach dem, was gilt. Es
ist aber der Wert der Kaskade und nicht der des Bildes; was dazwischenliegt,
sind Animationen, Übergänge und der Compositor.

**How to apply:** Für Sichtbarkeit `element.checkVisibility({opacityProperty:
true, visibilityProperty: true})` nehmen — das rechnet den Renderzustand. Und
die Regel, die diesen Fall gefangen hat: **Jeder Unsichtbar-Treffer wird im
Bildschirmfoto nachgesehen, bevor er ein Befund wird.** Bei fünf Treffern
kostet das eine Minute.

Das ist das Web-Geschwister von [[qt-luegt-vor-dem-anzeigen]] (`isVisible` und
`hasFocus` antworten falsch, solange nichts angezeigt wurde) und
[[text-gesetzt-heisst-nicht-gezeigt]] (`QMenu` verschluckt Tooltips, der Wert
sagt nichts über die Sichtbarkeit). Drei Umgebungen, ein Satz: **Der Wert, den
eine API zurückgibt, ist nicht der Zustand, den ein Mensch sieht.**

Es war der vierte Fehlbefund desselben Musters an einem Vormittag und der
erste, den ich vor dem Melden fing. Die drei davor: ein `<h3>` in einem
CSS-Kommentar, 1671 überlaufende Tabellenteile auf einer Seite im Aufbau, eine
zweite H1 im `display: none`-Deckblatt fürs PDF. Jedes Mal beschrieb die Zahl
etwas **Benachbartes** — den Kommentar statt des Elements, den Aufbau statt
des Zustands, die Regel statt des Bildes. Verwandt:
[[gemessene-frage-ist-nicht-die-gestellte]].
