---
paths:
  - "3D Drucker/**"
---

# Regeln für den Ordner „3D Drucker"

Hier liegen die echten Druckprojekte — **kein Programmcode, aber seit dem
22.08.2026 im Repository.** Bis dahin schloss `.gitignore` den Ordner aus, mit
der Begründung, er gehöre nicht zum Programm; fachlich stimmt das, praktisch
hieß es, dass die Projekte nur auf einer von drei Maschinen lagen. Auf dem
Laptop fehlte der Ordner vollständig.

`3D Drucker/CLAUDE.md` ist die Referenz für Drucker, Filamentbestand, Zubehör
und laufende Projekte; sie wird mitgeladen, sobald hier gearbeitet wird. Was
dort steht, wird hier nicht wiederholt.

**Was hier nicht abgelegt wird:** erzeugte STL- und G-Code-Dateien, die ein
Skript wiederherstellt. Das parametrische Skript ist die Quelle, die Datei
daraus ist das Ergebnis — dieselbe Regel wie beim Referenzkorpus, und sie zählt
hier doppelt, weil Netze schnell hundert Megabyte wiegen und aus der Historie
nicht mehr herausgehen. Ein Netz gehört dazu, wenn es **nicht** reproduzierbar
ist: ein eingescanntes Bauteil, ein heruntergeladenes Fremdmodell, ein von Hand
nachgebessertes Ergebnis.

## Immer an die eigene Werkstatt denken

Elegoo Centauri Carbon 2, Bauraum **256 × 256 × 256 mm**, 0,4-mm-Düse aus
gehärtetem Stahl. Ein Entwurf, der nicht auf diese Platte passt oder ein
Filament braucht, das nicht im Bestand ist, ist kein Entwurf, sondern eine
Bestellung — dann das sagen.

Materialwahl in einem Satz: draußen ASA, flexibel TPU 95A, innen PLA,
technisch/abrasiv PETG-CF mit gehärteter Düse.

## Konstruieren

- **Parametrisch**, nicht als Einzelstück: Python (trimesh/manifold3d) oder
  OpenSCAD, mit benannten Maßen oben in der Datei. OpenSCAD ist auf dieser
  Maschine **nicht installiert** — `.scad` bleibt Referenz, gerechnet wird in
  Python.
- **Jedes Teil wird vor dem Export geprüft**: wasserdicht, eine Komponente,
  Wandstärke über dem Mindestmaß, keine Selbstdurchdringung. Ein STL, das
  nicht geprüft wurde, wird nicht als fertig gemeldet.
- **Passmaße gehören gemessen, nicht geschätzt.** Wo ein Maß aus einer Quelle
  stammt, steht die Quelle im Kommentar; wo es geschätzt ist, steht das auch
  — und dann kommt zuerst ein kleines Prüfstück, nicht das ganze Teil.
- **Verschrauben statt kleben** (M3/M4), Dichtung über TPU-Einlage in einer
  Nut. PEI-Flüssigkleber ist Betthaftung, kein Bauteilkleber.
- Druckgerecht denken: Überhänge unter 45°, keine Stützen wo vermeidbar,
  Belastungsrichtung quer zur Schichtebene meiden, Elefantenfuß einplanen.

## Ordnung

Ein Projekt je nummeriertem Ordner, Iterationen als `Versuch N/`, aktueller
Stand im Projekt-Root. Zu jedem eigenen Teil eine
`*_Bauteil-Spezifikation.md`: Maße, Materialwahl, Druckhinweise, offene
Messungen. `_material.3mf` ist eine fertig geslicte Datei.

## Haltung

Der Drucker ist keine Simulation. Ein Teil, das erst nach acht Stunden Druck
als falsch auffällt, kostet echtes Material — lieber ein Prüfstück, eine
Rückfrage oder eine Messung mehr. Wo ein Druckteil Sicherheit betrifft, wird
das ausdrücklich benannt und die Sicherung bleibt zusätzlich dran.
