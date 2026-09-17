---
name: arm-rechnet-anders-als-x86
description: "Dieselbe Boolesche Operation liefert auf dem Mac der CI ein anderes Netz als auf Windows und Ubuntu — FMA auf ARM64, und manifold3d sagt zur Reproduzierbarkeit nichts zu."
metadata: 
  node_type: memory
  type: project
  originSessionId: 11ce8bae-a094-481e-ae5e-5d3e828e7368
  modified: 2026-09-17T17:29:07.636Z
---

`macos-latest` läuft seit April 2024 **nur noch auf ARM64**; Windows- und
Ubuntu-Runner sind x86_64. Auf ARM64 entstehen FMA-Instruktionen von selbst, auf
x86 erst mit Opt-in — `a×b+c` rundet dort einmal statt zweimal. Und
**manifold3d sagt Topologie zu, nicht Numerik**: „guaranteed manifold output",
kein Wort zu bitgleichen Ergebnissen über Plattformen.

Gemessen am 17.09.2026 an `resize_hole`: dasselbe Verkleinern liefert hier 1178
Dreiecke und auf dem Mac 1176. Die Senkung trägt 241 statt 240, und ihr Rand
läuft dort durch einen Punkt — eine Acht statt zweier Kreise. Alle Maße blieben
gleich (Ø 11,928, Winkel 89,838), nur die Triangulierung nicht.

**Was daraus folgt:** Keine Erkennung und kein Test darf von der exakten
Triangulierung eines Boolschen Ergebnisses abhängen. Eine festgeschriebene
Dreieckszahl **nach** einer Booleschen Operation schreibt eine Plattform fest;
an einem direkt konstruierten Körper (ein Würfel hat 12) ist sie harmlos.
Reparieren lässt es sich nicht bei uns — manifold3d kommt als Wheel, und
`-ffp-contract=off` wäre dessen Bauflag.

Siehe [[plattformen-funktionieren-gleich]] und
[[eigene-toleranz-gilt-nicht-fuer-fremde-netze]].
