# Konstruktionshinweise für FDM

Diese Hinweise sind Entwurfshilfen, keine zugesicherten Druckeigenschaften.
Gerät, Düse, Linienbreite, Schichthöhe, Material und Lastfall zuerst aus der
aktuellen Konfiguration bestimmen. Konkrete Richtwerte als Startwerte für
ein Prüfstück kennzeichnen, nicht als Normmaß oder pauschale Materialkonstante.

## Wand und Orientierung

Wandstärke mit der im Slicer tatsächlich erzeugten Bahnplanung abgleichen.
Variable Linienbreiten und Lückenfüllung machen die Regel „nur ganze Vielfache
des Düsendurchmessers“ unzureichend. Dünne Stellen in der Schichtvorschau prüfen;
Wandstärke und Perimeterzahl passend zu Belastung und Geometrie wählen.

Überhänge, Brücken, sichtbare Flächen und Festigkeitsrichtung zusammen abwägen.
Eine Winkelgrenze allein garantiert keine stützfreie Oberfläche. Bei waagerechten
Bohrungen können Nacharbeit, andere Orientierung oder eine geeignete Kontur helfen;
dabei Funktionsmaße und Montagebedingungen erhalten. Den Slicer extern verwenden,
seine Prognose von einem tatsächlichen Probedruck unterscheiden.

## Spiel eindeutig definieren

Für einen runden Stift gilt: Durchmesserspiel = Bohrungsdurchmesser minus
Stiftdurchmesser. Radiales Spiel ist bei konzentrischer Lage die Hälfte davon.
Das Spiel nicht noch einmal beiden Partnern vollständig zuschlagen.

- Spielpassung: gewünschte Beweglichkeit und zulässiges Wackeln festlegen,
  dann mit dem konkreten Profil ein Paar als Prüfstück drucken.
- Presspassung: beabsichtigte Überdeckung und zulässige Verformung festlegen;
  ein positives Sollspiel allein beschreibt keine Presspassung.
- Schnappverbindung: Montageweg, Federweg, Rückhalt und wiederholte Betätigung
  prüfen. Ein kollisionsfreier Endzustand sagt nichts über die Montage.
- Gewinde: Steigung, Profil und Flankenspiel als Paar über den Eingriffsweg
  prüfen. Eine Boolesche Differenz allein misst keinen umlaufenden Spalt.

Schwindung und Maßfehler am tatsächlichen Material und Profil messen. Keine
pauschale Rangfolge „Material A braucht immer mehr Spiel als Material B“.
Elefantenfuß an Passflächen durch eine geeignete Fase oder gemessene
Slicerkompensation berücksichtigen; dieselbe Korrektur nicht doppelt anwenden.

## Verbindung und Festigkeit

Normmaße aus der vorhandenen Tabelle, Einpressbuchsen aus der Maßzeichnung des
konkreten Herstellers übernehmen. Werkzeugzugang, Randabstand, Schraubenlänge,
Montagereihenfolge und mögliche Spaltkräfte mitprüfen.

FDM-Teile können richtungsabhängig versagen. Lastpfad, Kerben, Schichthaftung,
Temperatur und Kriechen sind wichtiger als eine isolierte Infill-Prozentzahl.
Perimeter und Infill erfüllen unterschiedliche Aufgaben; Gyroid macht das
fertige Teil nicht automatisch in allen Richtungen gleich fest. Eine zulässige
Last erfordert einen passenden Nachweis am konkreten Teil und Druckprozess.

## Dichtheit

Topologische Wasserdichtheit des Meshs und Flüssigkeitsdichtheit des Drucks
sind verschiedene Eigenschaften. Perimeter, Schichthöhe, Fluss, Nähte und
Temperatur am konkreten Behälter abstimmen. Eine bestimmte Zahl von Bahnen
oder Deckschichten garantiert keine Dichtheit.

Bei einer Dichtung Materialverträglichkeit, Anpressung, Nut und Medium prüfen;
TPU ist eine mögliche Lösung, kein universeller Ersatz für eine passende
Dichtung. Für die beabsichtigte Temperatur, Dauer und gegebenenfalls den Druck
einen Versuch definieren. Eine Dichtheitsprobe belegt keine Eignung für
Lebensmittel oder andere zusätzliche Anforderungen.

## Weiterführende Primärquellen

Am 11.09.2026 als allgemeine Herstellerhinweise geprüft; Aussagen auf das
konkrete Gerät und Material übertragen, nicht als Elegoo-Profil ausgeben:

- [Prusa: Modellieren für den 3D-Druck](https://help.prusa3d.com/article/modeling-with-3d-printing-in-mind_164135)
- [Prusa: Infill und Perimeter](https://help.prusa3d.com/article/infill_42)
- [Prusa: Flüssigkeitsdichte Drucke](https://help.prusa3d.com/article/watertight-prints_112324)
