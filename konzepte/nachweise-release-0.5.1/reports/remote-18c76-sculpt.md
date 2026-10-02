# Quellenreview: Formzug ins Leere

Fester Diff `d86489212bbb917af05f8aaf205a92d4fd65ed0f` → `18c76d96b11765d49406e85feb9a214088fab399`, Lieferung `105b2ba0d`. Sämtliche geänderten Zeilen in `app/core/geom/sculpt.py` und `tests/test_sculpt.py` sowie die erforderlichen Etappen-, Spiegel-, Serialisierungs-, Berichts- und UI-Anschlüsse gelesen.

## P2 — Ein wirksamer Spiegelzug wird als wirkungslos in der alten Etappe gelassen

**Stelle:** `app/core/geom/sculpt.py:383–385`; Anschluss `:203–207`, `:303–332` und `app/ui/main_window.py:11686–11698,11761–11766` im Zielstand.

Die neue zweite `_reaches`-Prüfung fragt nur den ursprünglichen Klickpunkt. Trifft dieser weder die Ausgangsfläche noch deren bereits verformte Fassung, gibt `_surface_for` jetzt die Ausgangsfläche und `cut=False` zurück. Die tatsächliche Auswertung prüft dagegen mit `_mirrored` auch alle Spiegelkopien. Eine solche Kopie kann ausschließlich einen bereits verschobenen Eckpunkt erreichen. Dann ist gerade eine neue Etappe nötig: In der Ausgangsfläche greift sie nichts, nach dem bisherigen Zug dagegen schon. Vor dem Diff gab dieser Zweig die verformte Fläche und `True` zurück; jetzt verliert derselbe neu erzeugte Zug seine Wirkung. `_surface_for` bekommt weder `stroke_at(..., symmetry=...)` noch die aktuelle globale Spiegelauswahl. Im Fenster wird die globale Symmetrie erst durch `_sculpt_shown` auf die erzeugten Züge gelegt.

**Konkreter quellenbasierter Gegenfall, nicht ausgeführt:** Ein geschlossenes Prisma hat `y,z ∈ [−10,10]`, die linke Wand `x=−10` und die rechte Wand `x=9+0,1y`. Seine Hüllmitte ist der Ursprung. Die linke Wand ist zusätzlich über ihren Mittelpunkt `M=(−10,0,0)` trianguliert, die rechte Wand nur über ihre vier Ecken. Mit X-Spiegelung zuerst bei M um 1 mm abtragen, Pinselradius 0,4 mm. Nur M liegt in der Pinselkugel und wird zu `M′=(−9,0,0)` verschoben. Anschließend auf `P=(9,0,0)` in der rechten Fläche klicken, gleicher Radius, Werkzeug Abtragen. P erreicht vor wie nach der ersten Etappe keine Ecke; sein Spiegelpunkt `−P` erreicht vor der Etappe ebenfalls keine Ecke, danach aber genau M′. Die neue Entscheidung lässt den zweiten Zug in der ersten Etappe und damit ausfallen. Der alte Zweig beginnt eine neue Etappe und lässt die Spiegelkopie wirken. Der Hinweis auf ein grobes Netz sperrt diesen Kundenweg nicht.

**Korrekturrichtung:** Die Etappenentscheidung muss die tatsächlich wirksamen Spiegelorte und dieselbe feste Spiegelmitte wie die Auswertung berücksichtigen. Nur wenn auch diese nach der Etappe nichts greifen, darf der neue Verzicht auf die Etappe greifen. Eine Regression soll den neu erzeugten, gespiegelten Zug bis zur realen Auswertung prüfen, einschließlich einer ausschließlich auf der verformten Fläche wirksamen Kopie. Das folgt aus dem gemeinsamen Vorschau-/Operationsvertrag (Regel 2, Konzept P16 §7.1 und Modulvertrag), nicht aus einer gewünschten zusätzlichen Funktion.

Der neue Test `test_a_stroke_that_reaches_nothing_starts_no_stage` (`tests/test_sculpt.py:240–255`) trifft den beabsichtigten Fall ohne Symmetrie und prüft eine nichtleere Etappenliste. Er deckt den Spiegelanschluss nicht ab. Sein Berichtssatz im Docstring wird dort nicht eigens ausgeführt; vorhandene Tests sichern die allgemeine Meldung verfehlter Züge, aber nicht diesen Gegenfall.

## Übrige Wirkung und Grenzen

- Explizites `cut=True`, die drei geordneten Werkzeuge und ein Zug nach einem solchen bleiben durch den unveränderten `fresh`-Zweig erhalten. Ein erreichbarer Ausgangspunkt behält den bisherigen KD-Abstand und Grenzwert. Der vorhandene echte Muldenfall ohne Spiegelung bleibt quellenlogisch erreichbar.
- Gespeicherte Striche enthalten Normalen und `cut`; die Operation entscheidet Etappen nicht erneut. Bestehende Dateien, Undo und ihre Auswertung ändern durch diesen Diff nicht ihre Parameterbedeutung. Ein zusätzlicher Op-/Dateiformatsprung ist für diese reine Stricherzeugung nicht erforderlich. Die vorhandene Etappenmemoisierung bleibt nach Netzidentität, Zugpräfix und Etappengrenze gebunden.
- Neu kommt im bisherigen Fehlzweig eine weitere KD-Abfrage auf der bereits berechneten Fläche hinzu. Daraus wird weder eine gemessene Leistungsregression noch ein neuer Abbruchbefund behauptet. Die bereits vorhandene synchrone Rechnung wird hier nicht als neuer Fund wiederholt.
- Keine Tests, Produktimporte, Geometrie-, Fenster-, Render- oder Leistungsläufe; der Gegenfall ist analytisch aus den Quellzweigen abgeleitet, keine ausgeführte Sonde. Keine Produkt-, QA-, Index- oder Roadmapänderung. Das zentrale vollständige Tor bleibt erforderlich und wurde hier nicht durchgeführt.

Zielquellen SHA-256:
- `app/core/geom/sculpt.py`: `d8bc21fa37e7e90dbd481758a39d53d3c792b50df39e106a21d7fb4c5dbc4cc5`
- `tests/test_sculpt.py`: `c5a1949efaa64cdeb1c314675bc2843cd6f6db2a96a130be9f9902f28eb388b7`

**Kann dieser Diff unverändert rein? Nein — der Spiegelanschluss muss geklärt werden.**
