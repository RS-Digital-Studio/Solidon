# Nachweise: Solidons Übergabe gegen die Herstellerprofile (27.09.2026)

Die vier Berichte, auf denen
[`konzept-herstellerprofil-als-grundlage-2026-09`](../konzept-herstellerprofil-als-grundlage-2026-09.md)
steht. Entstanden nach Roberts gescheitertem Minigolf-Druck am Centauri
Carbon 2; je Slicerfamilie von einem nur lesenden Prüfer geschrieben, mit
Messungen im installierten Slicer. Unverändert abgelegt — Zeilennummern und
Messwerte gelten für den Stand `46fa73c17` samt der damals uncommitteten
Überhanggrenze je Drucker.

| Bericht | Gegenstand | Kern |
|---|---|---|
| [orca-familie.md](orca-familie.md) | ElegooSlicer 1.5.3.4, OrcaSlicer 2.4.2, Bambu Studio 02.08.02.61, Creality Print 7.2 | Minigolf-Kette (46,4 m Stütze → 0 m mit Elegoos Stützsatz), Abgleich an zwölf Druckern, Befunde B-00 bis B-17 |
| [prusaslicer.md](prusaslicer.md) | PrusaSlicer 2.9.6, Bündel `PrusaResearch.ini` 2.4.14 | 284 von 347 wirksamen Werten sind eingebaute Vorgaben statt Prusa-Profil; Befunde B1 bis B11, N1 bis N8 |
| [cura.md](cura.md) | CuraEngine 5.13.0 | Startcode von `fdmprinter`, erste Schicht mit 12 000 mm/s², Stützsperre und Stützen je Netz gemessen möglich; Befunde B1 bis B12 |
| [karte-einstellungen-uebergabe.md](karte-einstellungen-uebergabe.md) | Einstellungsweg im Code | Wo Werte entstehen, gespeichert, zurückgelesen und geschrieben werden; welche Tests die heutigen Verträge halten |

Die Rohdaten der Messungen (G-Code, aufgelöste Profile, Sondenskripte) lagen
unter `output/review/slicer-audit-2026-09-27/` auf der Entwicklungsmaschine
und reisen nicht mit dem Repository.
