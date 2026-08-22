# Sondierung: konzept-durchsicht-2026-08-14.md

**Titel:** Durchsicht — Funktionen, Wörter und der kürzeste Weg zum geteilten Teil
**Stand laut Dokument:** Stand 14.08.2026.
**Zweck:** Bestandsaufnahme der gebauten Oberfläche entlang der Frage, ob ein Erstnutzer ein Teil trennen kann — mit den behobenen Befunden (Trennwerkzeug entlang gezeichneter Linie, zwei nur im Bild sichtbare Darstellungsfehler, vier Menüwörter), den abgearbeiteten offenen Punkten und dem Review des eigenen Änderungssatzes.

**Alterung:** 4/5 — Das Dokument ist eine Momentaufnahme des gebauten Fensters: Zählwerte (84 Operationen, 128 Menüzeilen, acht Werkzeuge, vierzehn Bausteine, 26 neue Texte), Pixelmessungen und Testzahlen veralten mit jedem Arbeitsschritt an app/ui/ und app/core/registry/. Dazu kommen Marktaussagen über Slicer-Funktionen (Cut-Tool mit Plug/Dowel/Snap) und fünf externe Links, die sich unabhängig vom Repository ändern. Zeitlos bleiben nur die Begründungen — warum die Verbindung vorgewählt ist, warum die Kamera nicht in den Stapel gehört, warum Fett die zweite Kodierung ist.

## Gliederung

- Durchsicht — Funktionen, Wörter und der kürzeste Weg zum geteilten Teil
- Teil 0 — Was bei solchen Programmen gefordert, gelobt und kritisiert wird
- Teil 1 — Behoben: das Trennen entlang einer gezeichneten Linie
- Teil 2 — Behoben: zwei Fehler, die man nur im Bild sieht
- Teil 3 — Behoben: vier Wörter, an denen ein Anfänger hängen bleibt
- Teil 4 — Die offenen Punkte, und was aus ihnen wurde
- Teil 5 — Was die Durchsicht entlastet hat
- Teil 6 — Der eigene Änderungssatz im Review
- Was gemessen wurde

## Extern prüfbare Behauptungen (18)

- **[niedrig/funktionsumfang] Tinkercad (Autodesk)** — Tinkercad wird ausschliesslich für seine Oberfläche gelobt; die Kritik ist immer, es könne zu wenig  
  _Ort:_ Teil 0
- **[niedrig/funktionsumfang] Autodesk Fusion 360** — Fusion 360 wird für seinen Umfang gelobt und für seine Lernkurve kritisiert  
  _Ort:_ Teil 0
- **[mittel/marktlage] STL-Reparatur-Software / 3D-Druck-Werkzeuge** — Nicht-mannigfaltige Kanten sind der häufigste Grund, warum ein Modell nicht druckt; die Klage lautet, man müsse dafür in ein anderes Programm  
  _Ort:_ Teil 0
- **[hoch/funktionsumfang] Bambu Studio, OrcaSlicer, Creality Print, PrusaSlicer** — Der Cut-Tool mit Plug, Dowel und Snap ist in Bambu Studio, OrcaSlicer, Creality Print und PrusaSlicer Standard  
  _Ort:_ Teil 0 — trägt die Begründung des gesamten Hauptteils
- **[mittel/marktlage] Bambu Lab Forum / 3D-Druck-Communities** — In den Foren wird nicht mehr diskutiert, ob man verbindet, sondern nur welche Dübelform (rund, dreieckig, sechskant)  
  _Ort:_ Teil 0
- **[mittel/marktlage] CAD-Vergleichsartikel (u. a. Shapr3D content library)** — Die Empfehlung in fast jedem Vergleich lautet: mit dem Einfachen anfangen und wechseln, wenn es nicht mehr reicht  
  _Ort:_ Teil 0
- **[mittel/sonstiges] Prusa Knowledge Base** — Quelle Prusa Knowledge Base — Cut tool unter help.prusa3d.com/article/cut-tool_1779 erreichbar  
  _Ort:_ Teil 0, Quellenzeile
- **[niedrig/sonstiges] PrintPal.io** — Quelle PrintPal — Connect 3D prints in your slicer unter printpal.io/resources/connect-3d-prints-without-modelling-in-10-seconds erreichbar  
  _Ort:_ Teil 0, Quellenzeile
- **[niedrig/sonstiges] Bambu Lab Forum** — Quelle Bambu Lab Forum — Using dowels and connectors for large prints, Thread 128276  
  _Ort:_ Teil 0, Quellenzeile
- **[niedrig/sonstiges] 3dprinting.com** — Quelle 3dprinting.com — STL repair software erreichbar  
  _Ort:_ Teil 0, Quellenzeile
- **[niedrig/sonstiges] Shapr3D** — Quelle Shapr3D — Easiest CAD software to learn erreichbar  
  _Ort:_ Teil 0, Quellenzeile
- **[hoch/api] Qt / PySide6 (QPushButton sizeHint)** — Qt rechnet die bevorzugte Knopfbreite aus der normalen Schrift des Widgets, auch wenn das Stylesheet QPushButton:default halbfett zeichnet  
  _Ort:_ Teil 2.1 — trägt die gewählte Behebung
- **[mittel/api] Qt / PySide6 (QTest, Shortcut-Verhalten)** — Ein Kürzel ohne Modifikator feuert nicht, während ein Eingabefeld den Fokus hat (mit QTest.keyClick nachgestellt)  
  _Ort:_ Teil 6
- **[mittel/api] Model Context Protocol (MCP)** — MCP dient als Protokoll der Fernsteuerung durch andere Programme auf demselben Rechner  
  _Ort:_ Teil 4.5
- **[mittel/funktionsumfang] Ollama** — Ein lokales Ollama ist neben einem API-Schlüssel der zweite Weg, den Chat zum Laufen zu bringen  
  _Ort:_ Teil 4.5
- **[mittel/sonstiges] FDM-3D-Drucker allgemein (Brückenfähigkeit)** — Eine Brücke von 0,9 mm legt jeder Drucker; mit der Naht nach unten entsteht kein Überhang  
  _Ort:_ Teil 4, Schnapper-Absatz — trägt die Entscheidung für den Baustein
- **[hoch/sonstiges] Schnappverbinder-Auslegung (Konstruktionsregel)** — Zehn zu eins ist das Verhältnis aus Länge zu Armstärke für die Federkraft eines Schnappers  
  _Ort:_ Teil 4 — daraus folgen 8 mm Mindestlänge
- **[mittel/sonstiges] VTK / Qt offscreen-Plattform** — VTK und die Offscreen-Plattform kommen im verwendeten Container nicht zusammen; window.grab() über dem OpenGL-Fenster bricht ab  
  _Ort:_ Was gemessen wurde

## Intern prüfbare Behauptungen (15)

- **[hoch]** Solidon hat 84 Operationen  
  _Prüfen:_ load_operations() aufrufen und die Registereinträge zählen (app/core/registry/), oder .venv\Scripts\python.exe -m app.cli.main mit der Op-Liste  
  _Ort:_ Einleitung, Teil 4.2, Teil 5
- **[mittel]** 128 Menüzeilen in drei Szenenzuständen ausgelesen  
  _Prüfen:_ Menüleiste aus build_application([]) erneut auslesen und zählen (app/ui/)  
  _Ort:_ Einleitung
- **[mittel]** Die Werkzeugzeile hat acht Umschalter; das Trennwerkzeug ist der achte, Symbol split  
  _Prüfen:_ Werkzeugzeilen-Definition in app/ui/ prüfen  
  _Ort:_ Teil 1, Teil 4.2, Teil 5
- **[hoch]** Trennen entlang gezeichneter Linie ist gebaut: zwei Klicks, Ebene aus Linie und Blickrichtung, eine Transaktion, Passungspaar je Stift (§14)  
  _Prüfen:_ Registereintrag der Split-Op und die zugehörigen Oberflächentests in tests/ suchen; Bauplan §14 gegenlesen  
  _Ort:_ Teil 1
- **[mittel]** Gemessen: 11 Geometrietests und 15 Oberflächentests zum Trennwerkzeug  
  _Prüfen:_ Testdateien zum Split-Werkzeug zählen: .venv\Scripts\python.exe -m pytest -q -k split --collect-only  
  _Ort:_ Teil 1
- **[hoch]** plan_pins und add_pins nehmen jetzt eine Ebene statt einer Achse  
  _Prüfen:_ Signaturen von plan_pins/add_pins im Code prüfen (grep in app/core/)  
  _Ort:_ Teil 1
- **[mittel]** Drei Verbinderquerschnitte zur Wahl: rund, Sechskant, Schwalbenschwanz; kein Schnapper als Querschnitt  
  _Prüfen:_ Parameterschema der Split-/Pin-Op auf die Formliste prüfen  
  _Ort:_ Teil 1
- **[hoch]** style.make_primary() setzt setDefault(True) und die halbfette Schrift; alle sieben Hauptknöpfe gehen darüber; ein Test verbietet setDefault(True) ausserhalb von style.py  
  _Prüfen:_ grep nach setDefault in app/ui/ und nach make_primary; zugehörigen Test in tests/ laufen lassen  
  _Ort:_ Teil 2.1
- **[mittel]** Der Hauptknopf ist nach der Behebung 115 px breit (vorher 104 px verfügbar, 89 px halbfette Textbreite)  
  _Prüfen:_ sizeHint().width() des Knopfes unter der echten Plattform erneut messen  
  _Ort:_ Teil 2.1
- **[hoch]** Vier Menütitel umbenannt: Boolesch → Verbinden und Abziehen, Druckvorbereitung → Teilen und Anpassen, Dezimieren → Dreiecke verringern, Muster → Kopien in Reihe oder Kreis  
  _Prüfen:_ Menütitel in app/ui/ und die fünf Kataloge in app/i18n/locales/ prüfen  
  _Ort:_ Teil 3
- **[mittel]** Automatisch teilen … steht jetzt unter Vorbereiten statt unter Bearbeiten  
  _Prüfen:_ Menüaufbau in app/ui/ prüfen  
  _Ort:_ Teil 3
- **[hoch]** Alle fünf offenen Punkte aus Teil 4 sind abgearbeitet; die ausführliche Fassung steht in der Roadmap  
  _Prüfen:_ ROADMAP.md, Abschnitt der Durchsichtsfunde, gegenlesen  
  _Ort:_ Teil 4
- **[mittel]** Die acht Werkzeuge haben Alt+1 bis Alt+8; für die Operationen bleibt es bei sechs Kürzeln  
  _Prüfen:_ shortcut-Felder der Registereinträge und die Werkzeugzeile prüfen; Registerkonsistenztest  
  _Ort:_ Teil 4.2
- **[hoch]** snap_connector ist der vierzehnte Baustein; Mindestlänge 8 mm, Naht muss 5,4 mm hergeben, SNAP_RATIO liegt im Repository  
  _Prüfen:_ register_part-Einträge in app/core/knowledge/parts/ zählen und snap_connector samt SNAP_RATIO prüfen  
  _Ort:_ Teil 4, Schnapper-Absatz
- **[mittel]** Fünf Sprachkataloge sind vollständig: 26 neue Texte, vier geänderte Menütitel, drei verwaiste Einträge entfernt  
  _Prüfen:_ .venv\Scripts\python.exe -m pytest tests/test_translations.py -q  
  _Ort:_ Teil 5