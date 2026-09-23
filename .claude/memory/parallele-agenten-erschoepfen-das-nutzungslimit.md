---
name: parallele-agenten-erschoepfen-das-nutzungslimit
description: "Siebzehn Opus-Agenten parallel erschöpften das Sitzungslimit nach rund drei Stunden, alle brachen mitten im Schritt ab — Berichte fortlaufend schreiben lassen, Fortsetzen per SendMessage kostet nichts"
metadata:
  node_type: memory
  type: project
  originSessionId: dabee67e-844a-4be9-9e09-fb2b87f06e5a
  modified: 2026-09-23T03:28:41.669Z
---

Durchsicht vor 0.5.0, 22./23.09.2026: sechzehn Prüfer plus ein Baupaket, alle
opus mit hohem Aufwand, je eigener Worktree. Nach rund drei Stunden brachen
**alle siebzehn gleichzeitig** ab: „You've hit your session limit · resets
3:10am" (HTTP 429). Keiner hatte bis dahin Bericht oder Patch geschrieben —
beides war erst für den Schluss vorgesehen.

Verloren ging trotzdem nichts: Die Arbeit lag in den Worktrees (17 bis 9 000
geänderte Zeilen je Paket), und `SendMessage` an die Agenten-ID setzt den
Agenten mit seinem ganzen Verlauf fort, sobald das Limit zurückgesetzt ist.

**Why:** Parallelität ändert nicht die Gesamtmenge, nur den Zeitpunkt, an dem
das Limit greift — und dann greift es an allen Stellen zugleich, mitten in
einer halb geschriebenen Funktion.

**How to apply:** Bei großen Fächern von Agenten im Auftrag verlangen, dass der
Bericht **fortlaufend** geschrieben und der Patch nach jedem Befund neu
erzeugt wird; nach einem Abbruch zuerst `py_compile` über die geänderten
Dateien (halbe Änderungen), dann fortsetzen. Die Agenten-IDs gehören in eine
Datei außerhalb des Gesprächs (hier `F:\3D Druck.review-050\KOORDINATION.md`),
damit das Fortsetzen auch nach einer Kompaktierung geht. Siehe
[[agentenberichte-sofort-sichern]], [[parallele-reviewer-kollidieren-an-den-raendern]].
