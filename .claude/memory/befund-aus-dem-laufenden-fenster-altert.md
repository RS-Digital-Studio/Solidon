---
name: befund-aus-dem-laufenden-fenster-altert
description: "Ein Fehler, den Robert in der laufenden App zeigt, kann im Baum längst behoben sein — vor dem Bauen am aktuellen Stand nachstellen."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: bdf65ac0-308e-4055-a003-34cf5d719e1e
  modified: 2026-09-09T06:20:31.333Z
---

Robert meldet Befunde aus der App, die er gerade offen hat. **Dieses Fenster
trägt den Stand seines Starts**, nicht den des Arbeitsbaums — und an dieser
Maschine committen an einem Tag mehrere Sitzungen in dieselben Dateien.

Am 09.09.2026: „versteifungsrippe hat auch nur eine seite, die anderen sind
beim modell gelandet". Der Befund stimmte für sein Fenster. Im Baum war er
schon behoben — dieselbe Stunde, durch die Bausteinarbeit einer anderen
Aufgabe (`parts_version` 16), die kurz zuvor hinausgegangen war. Gebaut wurde
daraufhin ein Kernumbau (Herkunft je Dreieck durch jede Operation), der am
Ende bei keinem der 27 Bausteine eine Fläche umhängte und verworfen wurde.

**Why:** Ein Befund aus einem laufenden Fenster ist eine Beobachtung über
einen Stand, nicht über den Code. Wer ihn ohne Nachstellen zur Aufgabe macht,
baut gegen eine Vergangenheit — und merkt es erst, wenn die Gegenprobe
„vorher gegen nachher" am Ende steht statt am Anfang.

**How to apply:** Vor der ersten Zeile Code den gemeldeten Fall am **aktuellen
HEAD** nachstellen und den Unterschied zeigen — bei Oberflächenbefunden über
ein Offscreen-Fenster, das dieselbe Datei öffnet und die fragliche Struktur
ausgibt (`QT_QPA_PLATFORM=offscreen`, `MainWindow.open_path`, Baumzeilen
drucken). Kostet zwei Minuten. Ist der Fall weg, ist die Antwort „das hat
Aufgabe X heute miterledigt" — und Roberts App braucht nur einen Neustart.

Verwandt: [[gegenprobe-bei-geaenderter-bauart]] (die Gegenprobe gehört an den
Anfang, nicht ans Ende), [[testprojekt-trifft-den-fall-nicht]],
[[messung-galt-fuer-den-stand-davor]].
