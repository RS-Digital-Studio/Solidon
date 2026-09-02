---
name: gestellte-daten-widersprechen-echten-daneben
description: "Ein erzeugtes Bild oder Beispiel mit gestellten Werten widerspricht den echten Werten daneben — das Handbuch zeigte „wasserdicht\" über „an drei Stellen offen\"; Erzeugnisse aus echten Läufen, und wer gestellte Daten braucht, nimmt ein Beispiel, das sie wirklich hat"
metadata: 
  node_type: memory
  type: feedback
  originSessionId: c1806dc1-e846-4999-89d4-b8c3c4636d14
  modified: 2026-09-02T17:42:29.138Z
---

Gesehen am 02.09.2026 beim Ansehen der neuen Handbuchbilder: Der
Prüfbericht trug vier **gestellte** Befunde („an drei Stellen offen", „14
Dreiecke zeigen nach innen", „Einheit stand nicht in der Datei") — über der
echten Kopfzeile „wasserdicht", an einer Dose, die Solidon selbst gebaut
hatte, mit einem Reparieren-Knopf, an dem nichts zu reparieren war. Das
Werkzeug (`tools/make_figures.py`) hatte die Befunde eingefügt, „damit das
Bild alle Sorten zeigt", und der Riegel in `test_manual.py` prüfte nur, dass
es sie in sechs Sprachen gab.

**Why:** Ein Kunde liest das Handbuch, um dem Werkzeug zu vertrauen. Ein
Bild, in dem sich zwei Zeilen widersprechen, sagt ihm, dass das Werkzeug
sich widerspricht — nicht, dass jemand die Aufnahme gestellt hat. Die Suite
sieht das nicht: Sie prüft, dass die Datei da ist und die Texte übersetzt
sind. Gesehen hat es nur, wer das Bild angesehen hat (siehe
[[was-die-suite-nicht-findet]]).

**How to apply:**
- Erzeugnisse (Bilder, Beispiele, Belege) entstehen aus echten Läufen. Wer
  eine bestimmte Sorte zeigen will (eine Warnung, einen Fehler), nimmt das
  Beispiel, das sie **wirklich** hat — `passung-nach-materialwechsel.p3d`
  öffnet mit Absicht mit einer Warnung —, statt sie einem anderen anzudichten.
- Gestellte Werte bleiben erlaubt, wo sie nichts Echtes daneben haben (ein
  Körpername im leeren Dialog, ein Druckername in den Einstellungen) — und
  auch dort nur, wenn die Kopfzeile nicht das Gegenteil sagt.
- Nach jedem Erzeugerlauf die Bilder **ansehen**, nicht nur zählen: Datei
  da, Zeitstempel frisch, und dann das Bild — an einem Nachmittag fünf
  Kundenfehler in neun Bildern (40,01 mm, Schrift versenkt, Schrift quer,
  doppelte Flächennamen, dieser Widerspruch).

Siehe auch [[eingestellter-wert-ist-nicht-das-ergebnis]] und
[[beheben-statt-notieren]].
