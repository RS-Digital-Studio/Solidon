---
name: verrauschte-tafel-trennt-nicht-von-sanfter-kruemmung
description: Verrauschte Facetten allein trennen erzeugte Netze nicht von konstruierten — erst gemischte und starke Knicke als eigener Auslöser tun es; gemessen 25.09.2026 an F:\3D Dateien
metadata:
  type: project
---

Erzeugte Netze (Puppenhausmöbel in `F:\3D Dateien\3D Drucker\Puppenhaus\moebel\`)
tragen ebene Partien als **verrauschte Tafel**: eine große Facette, deren
Normalen bis 4° streuen. Sie ist weder Fläche (`EPS_ANGLE` 0,01°) noch Fleck,
also sah die Splitterregel sie nicht, und das Bett galt mit 34 Prozent Splittern
nicht als Haut — 96 893 Splitter wurden eingepasst.

Drei Wege, gemessen an 189 Körpern mit verrauschten Facetten:

1. **Alle verrauschten Facetten zur Haut zählen** — verworfen: Konstruiertes
   trägt ebenso viel (Wedge-Lock Top 40 %, Siebhalter 35 %). Sanft gekrümmte
   CAD-Flächen und Float32-Rauschen fast ebener Flächen scheitern an derselben
   Prüfung.
2. **Raue Tafeln (gemischt und stark geknickt) zur Splittersumme zählen** —
   verworfen: `宠物便便器.3mf` (konstruiert, 56 % Splitter) kippte über die
   Schwelle.
3. **Raue Tafeln als eigener Auslöser** (`FREEFORM_ROUGH_SHARE` 0,4, Knicke
   gemischt ≥ 0,3, 90-%-Wert ≥ 0,1°) — umgesetzt: erzeugte Möbel, Figurenteile,
   Zaubersockel 50 bis 96 %, danach nichts bis 30, Konstruiertes höchstens 23.
   Bett 106 → 26,5 s, Stuhl 27 → 6,2 s, an 20 Modellen dieselben Merkmale.

**Why:** Die Haut-Regel ist Roberts Entscheidung (RM-193); wer sie berührt,
misst an beiden Seiten. Streuung allein ist kein Rauschen — erst die Mischung
der Knickrichtungen trennt Rauschen von Krümmung, und die Knickstärke trennt es
von Float32.

**How to apply:** Wer eine Freiformschwelle anfasst, fährt die Sonde
`_rough_facet_area` und den Hautanteil über den ganzen Korpus und sucht die
Lücke, bevor er eine Zahl setzt; eine Summe zweier Anteile verschiebt Körper,
die schon nahe an der Schwelle liegen. Verwandt: [[index-messen-und-pruefen]].
