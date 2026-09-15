---
name: eigene-toleranz-gilt-nicht-fuer-fremde-netze
description: "Eine Schwelle, die an Solidons eigenen Netzen (double, Schweißtoleranz 1e-6 der Diagonale) grün ist, weist jede importierte Datei ab — die trägt Float32 und die Toleranz eines fremden Kerns; Siebhalter+X1C.3mf ist das Bajonett-Referenzstück dafür"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 547e48ad-5377-40d8-82e6-9426b9bf8c3a
  modified: 2026-09-15T03:53:31.819Z
---

`radial_cylinder` prüfte die Ecken einer runden Wand gegen `weld_tolerance`
— 0,2 µm an einem 170-mm-Körper. Am Siebhalter eines Kunden
(`C:\Users\rober\Downloads\Siebhalter+X1C.3mf`, 15.09.2026) lag der Kragen
Ø 57,00 0,3 µm neben seinem Kreis (Float32 der STL), der Nutboden Ø 54,36
3,9 µm (zwei Eckenreihen um 2 µm verschieden). Beide sind Zylinder, beide
fielen durch, und im Baum stand „Verrundung R27,18" mit vier grauen Zeilen,
die eine Kante nannten. Seither gilt `ROUND_WALL_TOLERANCE` (10 µm).

Dieselbe Datei ist das Referenzstück für einen **Bajonettverschluss**: Halter
mit umlaufender Nut unter einem Kragen mit drei Lücken (45°/165°/285°), Ring
mit drei Nasen (25° breit, 1,42 mm tief) in einer Bohrung Ø 57,4. Kein
Gewinde — die Wendelsuche lehnt zu Recht ab. Die Nasenbohrung kam als
„Langloch Ø 57,39 auf 57,39" heraus (Stadion mit Weg 0,00005 mm).

**Why:** Jede Zahl im Kern ist an dem gemessen, was gerade da war — und das
waren Solidons eigene Netze aus double-Rechnung. Ein importiertes Netz hat
eine andere Genauigkeitsklasse (Float32 der STL, CAD-Kerntoleranz ~1 µm,
Facettierung), und eine Schwelle darunter macht jede Kundendatei zum
Sonderfall, ohne dass ein Test rot wird. Siehe [[testprojekt-trifft-den-fall-nicht]]
und [[downloads-ordner-als-3mf-korpus]].

**How to apply:** Wer eine Toleranz für eine Formfrage („liegt auf einem
Kreis", „ist ein Prisma", „Weg ist null") setzt, misst sie einmal an den
sechzehn Downloads-Dateien und nicht nur am eigenen Korpus; ein Wert unter
einem Mikrometer ist fast sicher eine Schweiß- und keine Formtoleranz. Ein
Ergebnis „so lang wie breit" oder „Verrundung über 180°" ist ein Fund und
keine Messung.
