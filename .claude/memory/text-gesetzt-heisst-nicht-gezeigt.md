---
name: text-gesetzt-heisst-nicht-gezeigt
description: "Ein Test, der den Wert eines Hinweistextes prüft, sagt nichts darüber, ob Qt ihn anzeigt — QMenu verschluckt Tooltips, bis toolTipsVisible gesetzt ist."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 5f85192a-8b20-4339-ba08-13913837d58c
  modified: 2026-08-31T08:14:09.615Z
---

**Ein Text, der gesetzt ist, ist nicht dadurch ein Text, den jemand liest.**
Am 23.08.2026 in Solidon: `kind_requirement` formuliert den Grund, warum eine
Operation des exakten Kerns an einem Netz nicht geht, `_add_operation` schreibt
ihn mit `setToolTip` an die gesperrte Handlung — und `QMenu` warf ihn weg.
`toolTipsVisible` ist von Haus aus **falsch**; die Menüleiste setzte es an
ihren drei Stellen, das Kontextmenü am Körper und das der Skizze nicht.
Untermenüs erben es nicht.

Der Test daneben war grün und blieb es: Er prüfte `action.toolTip()`, also den
**Wert**. Der war immer richtig. Die ganze Kette stand da und war unsichtbar,
und keine Prüfung hätte das je gemeldet.

**Why:** Eine Zusage über einen Text ohne Zusage über seine Sichtbarkeit ist
die Hälfte einer Prüfung — und die fehlende Hälfte ist die, die den Kunden
betrifft. Das gilt über Qt hinaus: überall dort, wo ein Rahmen (Menü, Tooltip,
Vorleser, Statusleiste, Konsole) entscheidet, ob ein gesetzter Wert erscheint.

**How to apply:** Wer einen Hinweis an ein Bedienelement schreibt, prüft im
selben Test, dass der Rahmen ihn zeigt — bei Qt `menu.toolTipsVisible()`, samt
Untermenüs. Und ein Testfall bekommt eine Gegenprobe, die belegt, dass er
überhaupt an einem gesperrten Element misst: `assert locked, "ohne einen
gesperrten Eintrag prüft dieser Test nichts"`. Verwandt mit
[[messwerkzeug-misst-sich-selbst]] und [[oberflaeche-von-hand-fahren]].

---

**Der schärfste Fall derselben Sache, am 31.08.2026 im eigenen Test:** Die
Statuszeile des Skizzeneditors bekam einen Verweis, damit die Einladung an der
leeren Skizze irgendwohin führt. Mein Test prüfte

```
assert '<a href="sketch-shapes">' in panel.status.text()
```

und die Mutation `setTextFormat(RichText)` → `PlainText` ließ ihn **grün**.
Denn `text()` gibt zurück, was gesetzt wurde — der vollständige Markup steht
auch in einem PlainText-Label drin. Er wird dort nur als sichtbare spitze
Klammer angezeigt statt als Verweis.

Das ist eine Stufe schlimmer als der Tooltip oben: Dort fehlte dem Wert der
Rahmen, hier trägt der Wert den Rahmen **in sich** und wird trotzdem nicht so
dargestellt. Ein String, der aussieht wie das Ergebnis, ist besonders
überzeugend — er enthält ja genau das gesuchte Zeichen.

Die Zeile, die fehlte:

```
assert panel.status.textFormat() == Qt.TextFormat.RichText
```

**Gefunden hat es nicht das Lesen, sondern die Gegenprobe** — zwei Mutationen
gefahren, eine fiel, eine blieb grün. Ohne sie wäre ein Test in die Suite
gegangen, der seinen eigenen Gegenstand nicht prüft. Es ist dasselbe Muster
wie [[zahl-beschreibt-die-regel-nicht-das-bild]] (`getComputedStyle` gibt den
Kaskadenwert, nicht das Bild) am selben Tag, nur in Qt statt im Browser: **Was
eine API zurückgibt, ist nicht, was ein Mensch sieht** — und ein Test, der nur
den Rückgabewert liest, erbt diese Lücke.
