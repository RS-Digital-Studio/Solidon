---
name: sbom-aus-dem-kundenartefakt
description: Eine SBOM aus pip oder der Entwicklungsumgebung ist nur eine Vorschau; ausgeliefert wird die Stückliste aus PyInstallers Zielanalyse und dem fertigen Kundenartefakt.
metadata:
  node_type: memory
  type: project
  modified: 2026-08-31T00:00:00.000Z
---

Eine Laufzeit-Stückliste beantwortet nicht die Frage „Was ist installiert?",
sondern „Was reist in genau diesem Kundenpaket?". `pip freeze` und der
deklarierte Abhängigkeitsbaum nehmen Bauwerkzeuge und optionale Pakete mit, die
PyInstaller gar nicht ausliefert. Umgekehrt verschwinden Qt, OCCT, GEOS und VTK
als native Hauptbibliotheken hinter ihren Python-Rädern, wenn nur
Distributionsnamen betrachtet werden.

Darum merkt sich `packaging/solidon3d.spec` nach PyInstallers `Analysis` die
tatsächlich importierten Distributionen, erzeugt `Solidon3D.cdx.json` aber erst
**nach** dem fertigen `COLLECT` beziehungsweise macOS-`BUNDLE`. Ein Paket kommt
nur hinein, wenn es zum geprüften Laufzeitbaum und zum Analyseergebnis dieses
Zielsystems gehört. Danach werden CPython, PyInstaller-Bootloader,
Kryptografie-, BLAS- und Compilerlaufzeiten sowie jede tatsächlich mitgereiste
PE-, ELF- oder Mach-O-Datei aus dem fertigen Artefakt inventarisiert. Cython,
setuptools und andere reine Bauwerkzeuge sind ausdrücklich ausgeschlossen.

Der Aufruf `python tools/make_sbom.py` ohne Analyse erzeugt nur die
konservative Vorschau unter `build/`; sie wird weder eingecheckt noch
ausgeliefert. Der Paketierlauf schreibt die Datei genau einmal direkt in das
**fertige Artefakt** und prüft sie anschließend gegen
das offizielle CycloneDX-Schema. Unter Windows und Linux ist das der finale
PyInstaller-Ordner, unter macOS ausschließlich die `.app` — der daneben
stehende COLLECT-Zwischenordner zählt nicht als zweites Kundenpaket.

**How to apply:** Nach einer Änderung an Abhängigkeiten, PyInstaller-Hooks,
`hiddenimports`, `datas`, `binaries` oder `excludes` reicht der Vorschautest
nicht. Jede Zielplattform muss das Paket nativ bauen; danach genau eine SBOM im
finalen Artefakt finden, das CycloneDX-Schema prüfen und belegen, dass
Bauwerkzeuge fehlen und jede native Kundendatei einen ausgewiesenen Besitzer
oder ausdrücklich „unbekannt" als Prüfhinweis trägt.
