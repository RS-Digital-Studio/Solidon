---
name: sandbox-sieht-keine-eingabegeraete
description: Ein Prüfskript aus der Sitzungs-Sandbox empfängt keine Eingabegeräte (HID, Raw Input, SendInput) — vier leere Aufzeichnungen am 02.09.2026, die nichts über das Gerät sagten
metadata:
  type: feedback
---

Am 02.09.2026 blieben vier Aufzeichnungen der SpaceMouse leer: zweimal HID
über `hidapi`, zweimal Windows Raw Input, dazu ein `SendInput`-Selbsttest, der
0 zurückgab. Alle liefen aus dem Bash-Werkzeug der Sitzung. Derselbe
HID-Leser lieferte ohne Sandbox (`dangerouslyDisableSandbox`) sofort 4572
Berichte in fünfzig Sekunden.

**Why:** Die Sandbox trennt den Prozess von den Eingabegeräten des Desktops.
Eine leere Messung sah aus wie „der Treiber hält das Gerät" und schickte eine
Stunde in die falsche Richtung (Raw Input, 3DxWare-Programmliste).

**How to apply:** Alles, was ein Gerät, den Desktop oder eingespeiste
Eingaben braucht — HID, Raw Input, Bildschirmfotos echter Fenster,
Tastatur-Simulation —, läuft ohne Sandbox. Und vor dem Schluss „das Gerät
schweigt" erst prüfen, ob der Prozess überhaupt Eingaben sieht (eine bekannte
Quelle wie die normale Maus mitlesen). Siehe [[was-habe-ich-gerade-gemessen]].
