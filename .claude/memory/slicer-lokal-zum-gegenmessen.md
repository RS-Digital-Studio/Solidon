---
name: slicer-lokal-zum-gegenmessen
description: "CuraEngine und PrusaSlicer liegen lokal — ein Vergleichslauf beider gegen dieselbe Geometrie entscheidet Slicer-Befunde, statt sie zu vermuten."
metadata: 
  node_type: memory
  type: project
  originSessionId: eb6dfb8a-f67c-4e4d-8f44-dde29a1bab09
  modified: 2026-08-08T10:05:39.742Z
---

Auf dieser Maschine liegen beide Slicer installiert und ohne Fenster
aufrufbar:

- `C:\Program Files\UltiMaker Cura 5.13.0\CuraEngine.exe`, Definitionen unter
  `share\cura\resources\definitions\` (`fdmprinter.def.json`,
  `fdmextruder.def.json`)
- `C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe`

**Warum:** Am 2026-08-08 stand „Cura läuft durch, fördert aber nichts" seit
Tagen als Vermutung in der Roadmap. Ein Lauf mit `handover._command(...)` und
`subprocess.run` klärte ihn in Minuten — und drehte den Befund um: die Datei
förderte, nur ihr Kopf schwieg. Ohne den zweiten Slicer daneben wäre offen
geblieben, ob die dann gelesenen Zahlen stimmen; PrusaSlicer lieferte den
Maßstab (21 min gegen 20,9).

**How to apply:** Bei jedem Zweifel an der Slicer-Übergabe ein Skript in den
Scratchpad, das `write_config` und `_command` von Solidon benutzt und beide
Slicer auf dieselbe Geometrie wirft — nie den Aufruf von Hand nachbauen, sonst
misst man das Skript. Einen Testkörper immer **auf** die Platte setzen (z 0..h);
ein um den Ursprung zentrierter Würfel wird unterhalb z=0 abgeschnitten, und
die halbe Höhe erklärt dann scheinbar falsche Kennzahlen. Vergleichswerte für
den 20-mm-Würfel bei Standardqualität stehen in `ROADMAP.md` unter „Cura läuft
Ende zu Ende". Siehe [[zeichnen-an-fusion-orientieren]] für dieselbe Methode
gegenüber Fusion.
