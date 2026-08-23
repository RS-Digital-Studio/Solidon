# Was neu ist

Diese Datei ist das, was im Update-Fenster steht — und sonst nichts. Sie ist
**keine** Liste der Änderungen: Von 97 Commits zwischen 0.1.1 und 0.1.2 stehen
hier acht Zeilen, und die Auswahl ist die Arbeit. Ein Punkt gehört hierher,
wenn jemand ihn beim Benutzen merkt.

Also: keine Commit-Meldungen, keine Modulnamen, keine Paragraphen. „Der Balken
verschwand, während die Anwendung noch vier Sekunden rechnete" ist ein guter
Commit und ein schlechter Punkt; „Der Fortschritt bleibt stehen, bis wirklich
fertig gerechnet ist" sagt dasselbe für den, der davorsitzt.

Je Sprache eine Datei in diesem Ordner, wie bei den Katalogen — und alle tragen
dieselben Punkte in derselben Reihenfolge (`tests/test_changelog.py`).
`tools/make_download.py` holt daraus den Abschnitt der aktuellen Version und
schreibt ihn in `website/version.json`.

## 0.1.4

- Solidon sieht beim Start nach, ob es eine neuere Fassung gibt, und bietet sie an. Geladen und installiert wird erst auf Ihre Bestätigung; abschalten lässt es sich in den Einstellungen.
- Ein lokales Sprachmodell darf jetzt zehn Minuten rechnen. Vorher brach der Chat nach zwei Minuten ab und bat um einen Fehlerbericht — für eine Rechnung, die einfach länger dauerte.
- Ein Ring wird als ein Merkmal erkannt und nicht mehr als drei übereinanderliegende Wülste.
- Der Eintrag „Fläche aufdicken“ tut jetzt, was er verspricht. Vorher versetzte er die Fläche.
- Der Fenstertitel nennt das geöffnete Modell, auch wenn es noch keine Projektdatei dazu gibt.
- Beim Zeichnen steht das Maß an der Spitze der Linie statt am Fensterrand.
- Ein gesperrter Menüeintrag sagt jetzt, warum er gesperrt ist. Der Grund stand vorher da und war unsichtbar.
- Hält die Berechnung an, steht dabei, an welchem Schritt und warum.
- Der Fehlerbericht nimmt den Stand der Szene mit: Objekte mit Maßen, Merkmale, Parameter und den Verlauf. Damit lässt sich ein Fehler nachstellen, statt ihn zu erraten.
- Mehrere Abstürze beim Schließen von Fenstern und Dialogen sind behoben.
- Die Versionsdatei ist unterschrieben, und Solidon prüft die Unterschrift, bevor es ein Update anbietet.
- Die Druckfläche heißt überall Bett und ihre Belegung Platte — so, wie die Slicer es nennen.

## 0.1.3

- Der exakte Kern kann jetzt bohren: „Exakte Bohrung setzen“ arbeitet direkt am exakten Körper, ohne den Umweg über ein Netz.
- Verrundungen und Fasen werden zuverlässiger erkannt. Eine Verrundung wurde vorher gelegentlich als Zapfen gemeldet — mit einem Durchmesser, den es nicht gab.
- Die mitgelieferten Beispiele begrüßen nicht mehr mit Warnungen, die keine sind.
- Der Startbildschirm passt auf kleine Bildschirme, ohne zu rollen.
- Ein angeklicktes Merkmal färbt sich selbst. Vorher nahm der ganze Körper die Auswahlfarbe an, und man sah nicht, was gemeint war.
- Der Objektbaum nennt zu jedem erkannten Merkmal sein Maß.
- Exportierte Netze enthalten keine leeren Dreiecke mehr.
- Zweimal gespeichert ergibt zweimal dieselbe Datei.
- Die fünf Übersetzungen sind durchgesehen. Fachbegriffe heißen jetzt so, wie die Slicer sie nennen.
- Die Werkzeugzeile ist aufgeräumt: Das breiteste Feld war das, das man am seltensten braucht.
- Ein zweiter Programmfehler stellt kein zweites Fenster mehr über das erste.

## 0.1.2

- Getippte Kommazahlen werden überall richtig gelesen. „12,5" blieb zwölfeinhalb — vorher konnte daraus 125 werden, ohne Rückfrage und ohne Hinweis.
- Jedes der sechsundfünfzig Felder in den Druckeinstellungen sagt jetzt, was es bewirkt, wenn man es bewegt.
- Druckzeit und Materialbedarf werden genauer geschätzt, vor allem bei ausgehöhlten Teilen.
- Die Übergabe an den Slicer trifft die Platte. Bei CuraEngine lagen Teile daneben.
- Beim Trennen mit Verstiftung sitzen die Gegenlöcher in der richtigen Hälfte.
- Millimeter und Zoll gelten jetzt überall, wo eine Zahl steht — auch in den Werkzeugleisten und beim Bemalen.
- Der Fortschritt bleibt stehen, bis wirklich fertig gerechnet ist, und das Fenster bleibt dabei bedienbar.
- Alle Tastenkürzel stehen jetzt in einer Übersicht: im Hilfemenü unter „Tastenkürzel", oder mit einem Druck auf die Fragezeichentaste.
