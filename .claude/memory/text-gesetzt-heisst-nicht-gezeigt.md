---
name: text-gesetzt-heisst-nicht-gezeigt
description: "Ein Test, der den Wert eines Hinweistextes prüft, sagt nichts darüber, ob Qt ihn anzeigt — QMenu verschluckt Tooltips, bis toolTipsVisible gesetzt ist."
metadata:
  type: feedback
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
