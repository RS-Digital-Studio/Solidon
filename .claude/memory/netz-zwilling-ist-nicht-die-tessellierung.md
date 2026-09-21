---
name: netz-zwilling-ist-nicht-die-tessellierung
description: "Ein netzgebohrter Zwilling und die Tessellierung des exakten Körpers sind zwei Netze — Paritätstests müssen beide fahren, sonst deckt die Naht in Bändern den Fall nicht"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7708995f-8153-4da1-9385-1fa5f014d252
  modified: 2026-09-21T22:56:05.830Z
---

Am 22.09.2026 sagte der Netzweg (`perceive.features._is_through`) an der
Aufweitung Ø 9 über einer Durchgangsbohrung `True`, der exakte Kern
`False` — aber nur am **tessellierten exakten Körper** (BRepMesh legt den
Übergangskegel in vier Bänder, der Abschnitt sah nur das Band an der
Endebene); der netzgebohrte Zwilling (ein Ring) sagte `False`, und der
Paritätstest verglich nur ihn. Fix: die Nachbarflächen des Mantels in ganzer
Länge fragen, wie `_axis_covered` am exakten Kern.

**Why:** Dieselbe Geometrie hat als Netz zwei Gestalten — die Boolesche am
Netz und die Tessellierung des B-Rep —, und die Erkennung liest Flecken,
nicht Geometrie. Ein Paritätstest, der nur den bequemen Zwilling nimmt,
besteht an der Gestalt, die der Kunde nie sieht.

**How to apply:** Netz-gegen-exakt-Tests fahren beide Netze
(`to_mesh(deflection)` des exakten Körpers **und** den netzgebohrten
Zwilling), mit mindestens zwei Deflections; wer nur eines fährt, schreibt
hin, welches und warum. Siehe [[lehre-schuetzt-nur-ihre-eigene-gestalt]]
und [[eigene-toleranz-gilt-nicht-fuer-fremde-netze]].
