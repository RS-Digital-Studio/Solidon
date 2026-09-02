# Was neu ist

Diese Datei ist das, was im Update-Fenster steht — und sonst nichts. Sie ist
**keine** Liste der Änderungen, sondern eine Auswahl, und die Auswahl ist die
Arbeit. Ein Punkt gehört hierher, wenn jemand ihn beim Benutzen merkt.

**Wie viele es sind, entscheidet die Fassung und nicht eine Zahl.** Hier stand
eine — „acht Zeilen“, gewachsen an einem Wartungsschritt zwischen 0.1.1 und
0.1.2 — und sie wurde gelesen wie ein Sollwert: 0.2.0 galt als „Ausnahme“ mit
75 Punkten, und beim nächsten Abschnitt setzte der Schreiber wieder bei acht
an und strich, was er darüber hinaus gefunden hatte. Ein halbes Jahr Arbeit und
ein Wartungsschritt haben nicht gleich viel zu sagen. Gestrichen wird, was der
Kunde nicht merkt, nicht was über einer Zahl steht (Entscheidung Robert,
27.08.2026).

Also: keine Commit-Meldungen, keine Modulnamen, keine Paragraphen. „Der Balken
verschwand, während die Anwendung noch vier Sekunden rechnete“ ist ein guter
Commit und ein schlechter Punkt; „Der Fortschritt bleibt stehen, bis wirklich
fertig gerechnet ist“ sagt dasselbe für den, der davorsitzt.

Je Sprache eine Datei in diesem Ordner, wie bei den Katalogen — und alle tragen
dieselben Punkte in derselben Reihenfolge **und derselben Gliederung**: Seit
0.2.0 bündeln `###`-Überschriften die Punkte in Gruppen (Bausteine, Zeichnen,
…), übersetzt je Sprache, die Struktur überall gleich
(`tests/test_changelog.py` prüft beides). `tools/make_download.py` holt daraus
den Abschnitt der aktuellen Version und schreibt ihn — als flache Liste, die
Gliederung ist Sache des Neuerungen-Dialogs — in `website/version.json`.

**0.2.0 zeigt, was das heißt:** 75 Punkte aus 244 Commits, weil zwischen 0.1.5
und 0.2.0 kein Wartungsschritt liegt, sondern ein halbes Jahr Arbeit in einem
Sprung. Die Obergrenze in `app/core/updates.py` ist damals mitgewachsen; sie
begrenzt, was das Fenster zeigen kann, und nicht, was ein Abschnitt sagen
darf.

**Und was nicht hineingehört, gleich wie kundenspürbar es ist:** eine
geschlossene Sicherheits- oder Lizenzlücke. Der Satz „eine Uhr in der Zukunft
verbrannte die Frist“ erzählt jedem, der eine ältere Fassung hat, wo der Hebel
sitzt. Drei solche Punkte standen am 26.08.2026 schon im Abschnitt und sind
wieder heraus (Entscheidung Robert). Wo ein Nutzen bleibt, der ohne den
Mechanismus auskommt — „die Meldung nennt den wirklichen Grund“ —, steht der
Nutzen da und sonst nichts.

## 0.3.0

### Einstieg und Orientierung

- Vier geführte Einstiege erklären die wichtigsten Wege vom ersten Entwurf bis zum druckbaren Ergebnis.
- Der Startbildschirm nutzt auch kleinere und schmalere Fenster vollständig, ohne abgeschnittene Karten oder verdeckte Inhalte.
- Zuletzt verwendete Projekte stehen vor den Einführungstouren und sind dadurch schneller erreichbar.
- Der Startbildschirm bewegt die Auswahl nicht mehr ungefragt und lässt sich vollständig mit Maus und Tastatur bedienen.
- Die Einstiege *Neu*, *Öffnen* und *Beispiele* sind klarer geordnet und beschreiben bereits vor dem Öffnen, wohin sie führen.
- Rückmeldung und freiwillige Unterstützung sind direkt vom Startbildschirm erreichbar und auch mit Tastatur und Hilfstechniken bedienbar.
- Der Chat bleibt auch bei geringer Fensterhöhe benutzbar: Die Eingabe steht fest unten, der Inhalt rollt.
- Die obere Werkzeugleiste bleibt bei geöffneten Projekten und schmalen Fenstern sichtbar, statt aus dem Arbeitsbereich zu rutschen.
- Ein neues Zeichenbeispiel führt direkt in den Skizzenweg und ergänzt die vorhandenen Beispielprojekte.
- Der Startbildschirm hat einen Knopf *Modell öffnen …*, und die Ablagefläche lässt sich auch anklicken.
### Oberfläche und Bedienung

- Menüs besitzen deutlich sichtbare Überschriften und einheitlich ausgerichtete Symbolspalten.
- Die Befehlsübersicht richtet Kürzel und Erklärungen sauber aus, sodass lange Einträge schneller überflogen werden können.
- Umfangreiche Dialoge verwenden einheitliche Spalten und Feldbreiten.
- Die frühere Sammelseite für Haftung, Rückzug und Filament ist in kleinere, logisch benannte Einstellungsbereiche aufgeteilt.
- Alle 56 Druckeinstellungen lassen sich über ihre sichtbaren deutschen Bezeichnungen durchsuchen.
- Die Suche versteht zusätzlich 146 geläufige Begriffe aus Slicern, darunter *perimeters* und *wall loops*.
- Zahlenfelder reagieren zuverlässig auf Pfeile, Schrittweite und Rundung und verändern Werte nicht mehr überraschend.
- Schieberegler haben ein einheitliches Aussehen mit gut greifbarem Griff.
- Die Akzentfarbe bleibt dem Hauptknopf vorbehalten; das aktive Werkzeug ist an seiner Kante erkennbar, ruhende Bedienelemente treten optisch zurück.
- Sehr kurze Berechnungen laufen ohne flackernde Anzeige, mittlere zeigen einen Wartezeiger und lange zusätzlich Fortschritt und Abbruch.
- Werkzeughinweise bleiben bei ausreichender Breite in einer Zeile und brechen bei schmalen Fenstern kontrolliert um.
- Vorschaubilder im Objektbaum sind groß genug, um Formen tatsächlich zu erkennen.
- Die Filamentliste scrollt unabhängig; *Filament anlegen* und *Druckwerte* bleiben auch bei vielen Rollen erreichbar.
- Warnungen und Fehler sind lesbar, ohne ihre Bedeutung ausschließlich über Textfarbe zu vermitteln.
- Deaktivierte Auswahlfelder lassen sich eindeutig von aktiv ausgewählten Feldern unterscheiden.
- Eine 3D-Maus (SpaceMouse) bewegt das Modell mit allen sechs Achsen, sobald sie eingesteckt ist; eine Gerätetaste passt alles ein.
- Die Druckplatte lässt sich mit einem Klick oder Strg+Umschalt+D ausblenden und bleibt so, bis sie wieder gebraucht wird.
### Zeichnen und genaue Eingabe

- Kreise werden über den Durchmesser eingegeben; eine M3-Bohrung kann damit direkt als 3,2 mm angelegt werden.
- Eine Durchmesserbedingung bleibt beim Lösen, Speichern und erneuten Öffnen als bearbeitbarer Ausdruck erhalten.
- Maße lassen sich durch Doppelklick direkt bearbeiten, ohne den bisherigen langen Auswahlweg.
- X-, Y- und Z-Position, Winkel und Skalierung können unmittelbar in der Bewegungsleiste eingegeben werden.
- Exakte Eingaben erzeugen denselben rücknehmbaren Arbeitsschritt wie eine Bewegung mit der Maus.
- Mehrere ausgewählte Körper verwenden bei exakter Drehung und Skalierung einen gemeinsamen Mittelpunkt.
- Escape geht beim Zeichnen genau eine Stufe zurück: aktuelle Linie, aktuelles Werkzeug und erst danach die ganze Skizze.
- Wiederholen funktioniert nun auch während einer geöffneten Skizze.
- Eine leere Skizze zeigt einen anklickbaren Hinweis, der die fertigen Grundformen öffnet.
- Der Knopf für die Grundformen heißt nach dem, was ein Klick darauf tut. Die übrigen Formen stehen hinter dem Pfeil daneben.
- Das Schnittwerkzeug öffnet im Körper statt in einer leeren Ansicht außerhalb des Modells.
- Vorder-, Seiten-, Ober- und Gegenansichten rasten zuverlässig auf allen sechs Achsen ein.
- Der Ziehgriff bleibt auch bei flacher oder schräger Kamera sichtbar und zeigt ein brauchbares Maß an.
- Das Messwerkzeug beendet eine Messung mit einer sichtbaren Rückmeldung, statt das Ergebnis scheinbar zu verlieren.
- Beim Hochziehen steht das Maß direkt an der Drahtform, und nach dem Loslassen bleiben alle Werte im Dialog änderbar.
- Die Maße beim Zeichnen folgen dem Raster, nicht dem Mauszeiger — man sieht das Maß, das man wirklich bekommt.
- Kreismaße lassen sich am Feld zwischen Durchmesser und Radius umschalten; die Wahl gilt in Skizze und Dialogen und bleibt gespeichert.
- Ein Kreis mit fester Mitte und bemaßtem Durchmesser gilt als vollständig bestimmt; die Statuszeile meldet kein fehlendes Maß mehr.
### Ansicht, Verlauf und Formen bearbeiten

- Mehrere ausgewählte Körper können gemeinsam verschoben werden.
- Mehrere ausgewählte Körper drehen sich um einen gemeinsamen Mittelpunkt und behalten ihre Abstände zueinander.
- Nach einer Drehung können Körper im selben Arbeitsschritt wieder sauber auf die Druckplatte gesetzt werden.
- Aufeinanderfolgende Bewegungen desselben Körpers werden zu einem verständlichen Verlaufsschritt zusammengefasst.
- Zusammengehörige Arbeitsschritte erscheinen als aufklappbarer Eintrag, statt den Verlauf mit Einzelzeilen zu überladen.
- Eine zusammenhängende Nutzerhandlung lässt sich mit genau einmal Rückgängig vollständig zurücknehmen.
- Verlaufseinträge zeigen ihre Art und eine eindeutige Schrittnummer.
- Heruntergeladene und importierte Modelle können unmittelbar geschnitten werden.
- Ein Klick auf einen Prüfhinweis führt zuverlässig zur betroffenen Stelle, zum Körper oder zum passenden Verlaufsschritt.
- Beim Anspringen eines Fundorts rahmt die Kamera das Ziel ein, statt in einer grauen Nahaufnahme zu landen.
- Benannte Flächen und Hinweise wandern beim Anordnen und Platzieren zusammen mit ihrem Körper.
- Beim Modellieren mit dem Pinsel wird gemeldet, wenn Striche das Modell verfehlen oder keine druckbare Änderung erzeugen.
- Ein Text auf einer Seitenwand steht waagerecht und aufrecht, statt in einem zufälligen Winkel zu liegen; auf Decke und Boden bestimmt weiterhin der eingestellte Winkel die Richtung.
- Steckt ein Schriftzug im Körper, statt auf ihm zu stehen, sagt es die Operation und nennt den Weg: die Fläche anklicken, auf der die Schrift sitzen soll.
- Ausgehöhlte Körper halten die gewünschte Wandstärke auch an schrägen und runden Flächen.
- Eine bewusst vergrößerte Bohrung behält ihren Namen und ihre Passungen, statt im Prüfbericht als verloren zu gelten.
- Kugeln mit sehr vielen Segmenten bleiben ein handliches Netz statt zwanzig Millionen Dreiecke.

### Eigene Bausteine und Austauschdateien

- Eigene Bausteine können als lokale .solidon-part-Datei gespeichert und wieder in den Katalog aufgenommen werden.
- Bausteindateien lassen sich öffnen, hineinziehen und über die Dateizuordnung des Betriebssystems importieren.
- Dateiname und Dateiendung machen sofort sichtbar, dass eine Datei zu Solidon gehört.
- Import, Teilen und lokale Bibliothek verwenden in allen sechs Sprachen vollständige Oberflächentexte.
- Ein eigener Baustein kann vor dem Speichern aus mehreren bearbeitbaren Schritten und Werten aufgebaut werden.
- Beim Weitergeben kann zwischen frei, Namensnennung sowie Namensnennung mit gleichen Bedingungen gewählt werden.
- Bei einem selbst benannten Baustein bleibt der eigene Name gegenüber einem mitgebrachten Namen maßgeblich.
- Herkunft und Weitergabebedingungen bleiben beim Austausch eines Bausteins nachvollziehbar.
- Schnapphaken, Scharnierauge, Lochwandhaken und Fuß besitzen robustere Übergänge ohne eingeschlossene Innenflächen.
- Katalogkarten behalten beim Nachladen ihrer Vorschaubilder Position und ausgewählte Fläche.
- Die Toleranzleiter beschriftet jede Stufe mit ihrer eigenen Nummer.
- Exportierte GLB-Dateien stehen in anderen Programmen aufrecht statt auf der Seite.

### Teilen, Drucken und Filament

- Automatisches Teilen bevorzugt tragfähige Schnittstellen und vermeidet die bisher mögliche dünnste Schwachstelle.
- Für jede Trennstelle wird die passende Verbindungsart einzeln gewählt und als konkrete Form gespeichert.
- Hinweise zu Klebeverbindungen bleiben zusammen mit der gewählten Trennstelle erhalten.
- Automatisches Teilen reagiert auf geänderte Vorgaben reproduzierbar und lässt sich während der Berechnung abbrechen.
- Die Orientierungssuche prüft nur tatsächlich unterschiedliche Lagen und erreicht auch bei anspruchsvollen Körpern das vorgesehene Zeitbudget.
- Große 3MF-Dateien werden schneller erkannt und verarbeitet, ohne das Dateiergebnis zu verändern.
- Material, Passung und Toleranzen richten sich nach der tatsächlich gewählten Filamentrolle beziehungsweise dem belegten Druckerplatz.
- Die Kopfzeile zeigt das tatsächlich verwendete Material und bietet keine zweite widersprüchliche Materialauswahl mehr an.
- Der deaktivierte Knopf *Druckdatei speichern* erklärt, dass die Datei erst beim Slicen entsteht.
- Bereits im selben Arbeitsablauf erledigte Reparaturen werden anschließend nicht erneut als offene Empfehlung angezeigt.
- Passbohrungen öffnen sich an der Trennstelle mit einer Einführfase, und die Rastkante einer Schnappertasche sitzt an der Naht.
- Ein selbst gewählter Stiftdurchmesser muss in die Naht passen; wird er dafür dünner, sagt der Bericht es.

### Prüfbericht, Stabilität, Plattformen und Sprachen

- Gleichartige Prüfbefunde werden gebündelt, ohne den Bezug zu den betroffenen Körpern und Stellen zu verlieren.
- Zahlen und Messwerte im Prüfbericht besitzen vollständige Bezeichnungen statt unverständlicher Einzelwerte.
- Scheitert eine Reparatur, wird der unveränderte Ausgangskörper vollständig wiederhergestellt.
- Ein geschlossenes importiertes Netz wird nicht mehr durch das vorschnelle Entfernen eines problematischen Dreiecks aufgerissen.
- Aktionsknöpfe aus dem Prüfbericht halten ein bereits geschlossenes Fenster nicht mehr unbemerkt im Speicher.
- Mitgelieferte Bausteine und die Freischaltung werden beim Start ohne gegenseitiges Blockieren geladen.
- Die 3D-Ansicht wird vor dem Fenster sauber beendet; dadurch schließen Windows-, Linux- und macOS-Fenster zuverlässiger.
- Die Titelleiste folgt unter Windows 11 dem Farbschema der Anwendung; andere Plattformen bleiben unverändert.
- Unter Linux mit einer Wayland-Sitzung startet Solidon und zeigt die 3D-Ansicht; fehlt dem System eine Bibliothek dafür, startet die Anwendung trotzdem und sagt, welche fehlt.
- Standardschaltflächen wie Öffnen, Speichern und Abbrechen wechseln ihre Sprache sofort, ohne Neustart.
- Automatisch erzeugte Körper- und Bausteinnamen wechseln auch nach bereits verwendeten zwischengespeicherten Inhalten korrekt die Sprache.
- Übersetzungen und Berichtswerte sind in Deutsch, Englisch, Spanisch, Französisch, Italienisch und Portugiesisch auf demselben Stand.
- Ein Teil ohne Befunde bietet im Prüfbericht direkt den Knopf *An den Slicer übergeben …* an.
- Jede Analysekarte erklärt beim Zeigen, was sie zeigt, und die Einheitenfrage beim Einlesen nennt die Einheiten mit Namen.
- Ein Teil, das das Druckbett füllt, wird ohne Rückfrage in Millimetern gelesen.
- Dünne Rippen neben dicken Platten werden als dünne Stelle erkannt, und Brücken werden an ihrer wirklich freien Weite gemessen.
- Ein Teil, das auf sich selbst steht, bekommt keine Stützen vom Druckbett empfohlen.
- Die Druckempfehlungen prüfen alle Geschwindigkeiten, rechnen die erste Schicht mit ihren eigenen Maßen und melden ein Bett oder einen Bauraum, der für das Material zu kalt bleibt.
- Übereinander liegende Laschen behalten jede ihre Bohrung, und feine Kratzer gelten weder als Bohrung noch als Zapfen.
### Chat und Modellunterstützung

- Der Chat begrüßt mit seinem konkreten Zweck und startet nicht mehr mit einer leeren Fläche oder technischen Modellbegriffen.
- Technische Token-Zähler wurden aus der normalen Kundenoberfläche entfernt.
- Gleichlautende Hinweise zu verlorenen Formdetails erreichen den Assistenten gezählt statt einzeln.
- Der Erzeugen-Dialog macht aus Text oder Bild über ein lokales ComfyUI ein Modell und übernimmt es in dieselbe bearbeitbare Szene.
- Der mitgelieferte TripoSG-Ablauf erzeugt eine GLB, die anschließend automatisch repariert, auf Maß gebracht und auf Druckbarkeit geprüft wird.
- Lokales Ollama und lokales ComfyUI rechnen nacheinander, damit sie die Grafikkarte nicht gleichzeitig belegen.
- Nach einem Agentenvorschlag oder einer 3D-Erzeugung gibt Solidon lokale Modelle und Grafikspeicher wieder frei.
- Beim Abbrechen entfernt Solidon nur den eigenen ComfyUI-Auftrag; andere dort laufende Aufträge bleiben unberührt.
- Vor der ersten Nutzung eines Cloud-Modells zeigt Solidon verständlich, welche Inhalte den Rechner verlassen.
- Der Dialog für Zusatzprogramme zeigt nur, was noch fehlt, und beschreibt den Zustand von ComfyUI in einfachen Worten.
## 0.2.2


### Zeichnen und Formen

- Im Skizzenmodus lassen sich Punkte, Linien, Kreise und Konturen direkt in der Ansicht auswählen und ziehen. Markierung und Griff zeigen zusätzlich, was bewegt wird.
- Die Zeichenebene bleibt im Raum stehen, wenn Sie zwischen Drauf-, Vorder- und Seitenansicht wechseln. So erkennen Sie ihre wirkliche Lage statt dreimal dasselbe Bild zu sehen.
- Ein Rechteck lässt sich mit eingetippter Breite und Höhe fertigstellen. Die Maße bleiben als Bedingungen erhalten, statt nach dem Zeichnen wieder verloren zu gehen.
- In der Vorder- oder Seitenansicht ziehen Sie einen geschlossenen Umriss zur Höhe auf. Zahl und Drahtvorschau wachsen mit; ein eingetippter Wert setzt die Höhe genau.
- Ziehen Sie den Umriss nach außen, entsteht ein Körper; ziehen Sie ihn nach innen, entsteht eine sichtbare Tasche. Pfeil und Kreuz machen beide Richtungen greifbar.
- Beim Erzeugen eines Quaders, Zylinders oder Skizzenkörpers erscheint die Vorschau schon während der Eingabe. Neue Körper blieben vorher bis zum Anwenden unsichtbar.
- Zeichenwerkzeuge sagen, was der nächste Klick bewirkt. Bedingungen erklären ihre Wirkung und die Auswahl; die Freiheitsgrade stehen in verständlichen Sätzen da.
- Quader, Zylinder, Bohrung und Aushöhlen stehen nur noch einmal im Menü. Das Häkchen „Flächen und Kanten später bearbeiten“ ersetzt den zweiten Eintrag, der vorher „exakt“ hieß.
- Dieses Häkchen hält Fasen, Verrundungen, Formschrägen, versetzte Flächen und den STEP-Export offen. Der Dialog nennt den Nutzen, statt nach einem Rechenkern zu fragen.
- Die Leiste beim Zeichnen benennt den nächsten Schritt: Hochziehen, Abtragen oder Fertig. Fehlt ein geschlossener Umriss oder ein ausgewählter Körper, steht auch das dort.
- Eine gesetzte Bedingung nimmt ein zweiter Klick auf denselben Knopf zurück; ein Rechtsklick auf den Punkt zeigt, was an ihm hängt. Vorher kam jedes Mal eine weitere dazu, bis nichts mehr ging.
- Die Bedingungsleiste zeigt nur, was zur getroffenen Auswahl passt. Ist nichts ausgewählt, steht dort ein Satz statt zehn ausgegrauter Fachwörter.
- Grundkörper entstehen „auf dem Druckbett“ statt „auf Z = 0“, und das Zeichenwerkzeug heißt „Kurve“ wie das, was es zeichnet.

### Bohrungen und Merkmale

- Den Durchmesser einer erkannten Bohrung in einem importierten Modell ändern Sie direkt, ohne die Bohrung neu zu zeichnen oder ein CAD-Programm zu öffnen.
- Die geänderte Bohrung behält Lage und Richtung und funktioniert an Netzen wie an exakten Körpern. Auch eine schräge Bohrung bleibt auf ihrer ursprünglichen Achse.
- Merkmalsmarkierungen folgen nach einer Neuberechnung der sichtbaren Geometrie. Eine markierte Bohrung bleibt dabei offen und wird nicht von ihrer Markierung verdeckt.
- Häufige Werkzeuge wie Bohrung, Vereinigen und Abziehen liegen im Menü einen Klick näher. Überschriften halten die Gruppen trotzdem verständlich auseinander.

### Bausteine und Normteile

- Druckbare Schrauben und Muttern kommen mit zueinander passendem Gewinde aus dem Katalog. Kopf, Länge, Größe und Spiel lassen sich passend zum Druck wählen.
- Für gängige Kugellager gibt es einen Lagersitz mit Normmaß. Das Lager kann wechselbar mit Spiel oder fest als Presspassung eingesetzt werden.
- Ein Schraubenloch kann jetzt einen Senkkopf oder eine passende Unterlegscheibe einlassen. Die Kopftiefe bestimmt, wie weit beides im Teil verschwindet.
- Die Normtabellen enthalten mehr Unterlegscheiben, Gewindeeinsätze und Kugellager. Technische Größen stehen mit einer Erklärung in der Auswahl statt als rätselhafter Code.
- Magnettaschen, Kabelclips und Kabeldurchführungen nehmen auch eigene Maße an. Zusatzfelder erscheinen nur, wenn die gewählte Variante sie wirklich benutzt.
- Bausteine stehen im Katalog mit Vorschaubildern statt als Liste im Menü. Ein Rechtsklick auf das gewählte Teil führt hin.
- Der Katalog sagt schon vor dem Einsetzen, wenn die Stelle am Körper fehlt. Die meisten Bausteine brauchen eine gewählte Fläche oder Bohrung.

### Drucken und Filament

- Jede Filamentspule kann eigene Temperaturen, Kühlung, Rückzug und Materialwerte tragen. Die Werte bleiben auch erhalten, wenn Sie die Qualitätsstufe wechseln.
- Die Werte der einzelnen Spulen erreichen 3MF-Datei und Slicer für den richtigen Materialplatz. Eine Farbe nimmt nicht mehr versehentlich die Druckwerte einer anderen mit.
- Beim ersten Start übernimmt Solidon die im Slicer eingelegten Filamente mit Name, Typ, Farbe und Herstellerprofil. Die Spulen müssen nicht noch einmal angelegt werden.
- Mitgelieferte Beispiele überschreiben den gewählten Drucker und das Material nicht mehr mit den Einstellungen, mit denen ihre Vorschaubilder gebaut wurden.
- Im Linux-Flatpak findet und startet Solidon Slicer auf dem Rechner, auch als AppImage. Der gemeinsame Arbeitsordner ist für beide Programme erreichbar.
- Beim Teilen entstehen Passstifte an der einen Hälfte und die passenden Löcher an der anderen. Die Meldung nennt ihre Zahl oder sagt, dass die Schnittfläche dafür zu klein ist.
- Nach dem Teilen rücken die Hälften auseinander. Stifte und Löcher verschwinden dadurch nicht mehr zwischen zwei deckungsgleichen Schnittflächen.
- Werden zwei Körper vereinigt, behalten beide ihre Filamentbeschreibung samt Namen. Vorher konnte die Beschreibung der zweiten Farbe dabei verlorengehen.
- Beim Export auf mehrere Platten werden Farbwechsel je Platte gezählt. Materialreine Platten melden keine Wechsel mehr, die beim Drucken gar nicht stattfinden.
- Scheitert der eingestellte Slicer, bietet die Meldung den Wechsel zu einem anderen an. Vorher blieb nur der Export — auch wenn zwei arbeitende Slicer daneben lagen.
- Die fertige Druckdatei lässt sich direkt im Fenster des Slicers öffnen, mit dessen eigenen Profilen. Welche Übergabe Sie benutzen, merkt sich das Projekt.
- Die Druckdatei wird gegen die Höhe des Modells geprüft. Ein Teil, das unter dem Druckbett steckt, fällt damit vor dem Druck auf — nicht erst an der halben Höhe am Drucker.
- ElegooSlicer nimmt Aufträge wieder an. Und ordnet ein Slicer die Teile selbst an, steht das als Hinweis im Prüfbericht, statt die geplante Plattenbelegung stillschweigend zu ersetzen.
- Der Prüfbericht stapelt keine alten Messwerte mehr: Ein neuer Lauf ersetzt sie, derselbe Sachverhalt steht einmal da, und Befunde nennen das Objekt beim Namen statt einer Nummer.
- Die gemerkten Slicer-Profile wissen, zu welchem Slicer sie gehören. Nach einem Wechsel wird kein fremdes Profil mehr in das neue Programm übernommen.
- Ein Sperr-Grund unter den Druckeinstellungen verschwindet, sobald er nicht mehr gilt. Vorher blieb „braucht ein Druckerprofil“ neben einem längst freien Knopf stehen.

### Chat und 3D-Erzeugung

- Die Einstellungen trennen Cloud- und lokale Modelle sichtbar. Bevor ein Cloud-Schlüssel eingetragen wird, steht dort, welche Daten den Rechner verlassen.
- Die Prüfung eines langsamen 3D-Generators hält den Dialog nicht mehr fest. Währenddessen steht dort, was geprüft wird und wie zusätzliche Programme eingerichtet werden.
- Die Zuordnung erkannter Merkmale bleibt auch bei großen Modellen flüssig. Hunderte Merkmale werden gemeinsam statt nacheinander verglichen.
- Anfragen an Ollama und ComfyUI auf demselben Rechner umgehen den Firmenproxy. Ein laufender lokaler Dienst wird dadurch nicht mehr fälschlich als unerreichbar gemeldet.
- Im Linux-Flatpak laufen Einrichtung und Start lokaler Zusatzprogramme auf dem Rechner statt im Sandkasten. ComfyUI wird auch an üblichen Linux- und macOS-Orten gefunden.
- Der Erzeugen-Knopf ist nur klickbar, wenn der Klick auch etwas auslöst. Fehlt etwas, steht daneben, was — und ein Knopf, der zur Behebung führt.
- Schlägt die Erzeugung fehl, steht ComfyUIs eigene Fehlerzeile im Dialog, samt dem Schritt, in dem sie entstand. Genau diese Zeile braucht, wer um Hilfe fragt.
- Tippt ein Sprachmodell seinen Werkzeugaufruf als Text, statt ihn auszuführen, erklärt der Vorschlag das — samt dem Weg über „Werkzeuge prüfen“. Vorher stand rohes JSON im Gespräch.
- Das Handbuch hat die neue Seite „Welche Modelle Solidon benutzt“: welche geprüft sind, woher sie kommen, wie lange sie brauchen — und welche Datei für den Textweg wohin gehört.
- Ein sehr kleiner erzeugter Körper zeigt sein echtes Volumen statt „0 mm³“ neben „geschlossen“.
- Bei den KI-Modellen fürs Erzeugen wählen Sie je Aufgabe selbst, welches rechnet — wie beim Sprachmodell. „Automatisch“ bleibt die Vorgabe und nimmt das, was passt.

### Ansicht und Bedienung

- Die Parameterleiste zeigt Maße kompakt und dauerhaft. Einheit, Grenzen und Ausdruck lassen sich dort rücknehmbar ändern, ohne dass die eigentliche Zahl aus dem Blick rutscht.
- Eigene Werkzeugzeiger folgen auf Windows, macOS und Linux der eingestellten Systemgröße. Ihr Klickpunkt liegt wieder an der gezeichneten Spitze statt daneben.
- Darüberfahren und Auswählen sind in der Ansicht klar verschieden markiert. Analyse- und Unterschiedsfarben bleiben dabei wichtiger als eine Ganzkörpermarkierung.
- Menüs, Hinweise und Handbuch verwenden einheitliche Wörter für Einsteiger. Fachbegriffe werden dort erklärt, wo sie zum ersten Mal gebraucht werden.
- Der Unterstützen-Dialog erklärt vor dem Öffnen von PayPal, dass die Zahlung freiwillig ist und keine Funktionen freischaltet. Scheitert der Browser, lässt sich der Link kopieren.
- Aushöhlen und andere abhängige Werkzeuge zeigen nur Felder, die für die gewählte Variante gelten, und erklären ausgeblendete Werte einheitlich.
- Die mitgelieferten Beispiele öffnen mit einer geführten Tour. Rechts steht Schritt für Schritt, was zu tun ist, und die Tour erkennt selbst, wenn ein Schritt erledigt ist.
- Die Handlungsvorschläge zu einem Fehler bleiben beim Speichern erhalten. Nach dem Öffnen eines Projekts stand vorher nur noch der Fehler da, ohne den Weg heraus.
- Die Orientierungssuche prüft jede Lage nur noch einmal. Mehrfach vorgeschlagene Lagen kosteten Rechenzeit, ohne ein anderes Ergebnis zu liefern.
- Verlaufsschritte lassen sich löschen und mit Strg+Z zurückholen. Die Nachfrage davor nennt die Schritte, die auf dem gelöschten aufbauen.
- Ein Doppelklick auf einen zusammengefassten Verlaufsschritt sagt, wo die einzelnen Schritte stehen. Vorher tat er nichts, obwohl die geführten Touren genau diese Geste lehren.
- Wird eine Datei beim Einlesen abgewiesen, verschwindet die Ladeanzeige. Vorher blieb sie stehen, als werde noch an einer Datei gerechnet, die gar nicht angenommen wurde.
- Solidon startet schneller, und die Schichtanalyse rechnet zügiger. Die großen Rechenbibliotheken werden erst geladen, wenn wirklich gerechnet wird.
- Fehlermeldungen zeigen die Angaben, auf die ihre Sätze verweisen. „Der Anfang der Antwort steht daneben“ — jetzt steht er wirklich daneben, samt Adresse und Anbieter.
- Die Räte „Dreiecke verringern“ und „Seite im Browser öffnen“ sind jetzt Knöpfe, die genau das tun, statt Sätze, die es beschreiben.
- Antwortet ein Dienst nicht, nennt der Dialog die Adresse zum Nachsehen im Browser und sammelt den Startversuch unter „Einzelheiten“. Hinweise zeigen nur auf Knöpfe, die es gerade gibt.
- Die Aufklapplisten der Leisten unter der Ansicht bleiben offen, bis Sie wählen. Vorher konnte sich eine Liste sofort wieder schließen, weil sie sich unter dem Zeiger wegschob.
- Das Dickenfeld der Schnittleiste wartet, bis Sie zu Ende getippt haben. Vorher schnitt es bei jedem Tastendruck — erst mit 3 mm und dann mit 30.
- Der Prüfbericht wählt nach dem Öffnen den obersten Befund mit einer Handlung vor. „Auf das Bett setzen“ steht damit sofort als Knopf da, ohne dass man die Listenzeile erst anklicken muss.
- Der Hinweis auf sehr kleine Einzelteile bietet jetzt den Knopf „Kleine Teile entfernen“ an. Vorher sagte er nur, dass nichts gelöscht wurde, und ließ Sie den Weg selbst suchen.
- Erledigte Reparaturen beim Einlesen stehen als Hinweis im Prüfbericht, nicht mehr als Warnung. Der Bericht ging sonst bei jedem zweiten Modell gelb auf, obwohl es nichts zu tun gab.
- Der Hinweis zur abgebrochenen Paketverwaltung nennt den Knopf bei seinem vollen Namen — in allen sechs Sprachen. „Details“ allein war in fünf davon eine kleine Suche.

### Plattformen und behobene Fehler

- Für Linux gibt es neben dem Flatpak auch ein AppImage. Damit lässt sich Solidon ohne Flatpak-Installation als einzelne ausführbare Datei starten.
- Ein aus Solidon gestartetes Windows-Update zeigt nur den Fortschritt und öffnet Solidon danach wieder. Beim manuell gestarteten Setup bleibt die Start-Auswahl am Ende erhalten.
- Das Linux-Flatpak lässt sich aus Solidon heraus aktualisieren.
- Rückmeldungen an den Support lassen sich auch aus dem Linux-Paket senden. Dem Paket fehlte dafür bisher der Netzzugang.
- Auf macOS werden feine Risse im STL-Netz eines Gewindes beim Export vernäht, ohne ein bereits schlechter gewordenes Netz zu übernehmen.
- Die Update-Prüfung liest auch einen umfangreichen mehrsprachigen Changelog. Hinweise enden nicht mehr mitten im Wort, und lange Neuerungslisten verhindern die Prüfung nicht.
- Der Über-Dialog zeigt im gebauten Paket wieder die Hinweise zu allen mitgelieferten Bibliotheken.
- Der Fehlerbericht nennt echte Bibliotheksfassungen sowie Sitzung und Eingabemethode. Ein Strich bedeutet nicht mehr fälschlich, dass eine notwendige Bibliothek fehlt.
- Beim Reparieren importierter Netze bringen einzelne fremde Metadaten die Reparatur nicht mehr zum Absturz.
- Erfolgreiches Aushöhlen nennt nun auch bei exakten Körpern Wandstärke und entferntes Volumen, statt nach einer gelungenen Rechnung still zu bleiben.

## 0.2.1


### Farben und Filament

- Flächen und Teile färben Sie mit zwei Gesten statt mit einem Pinsel: Ein Klick färbt eine Fläche, ein Klick das ganze Teil. Ändert ein früherer Schritt die Maße, wandert die Farbe mit.
- Ein Klick auf die Oberseite färbt die Oberseite — die Grenze der Fläche kommt aus der Erkennung, ohne Radius und ohne Zielen.
- Das Filament wählen Sie mit Namen und Farbe — „PETG Rot“ statt einer Nummer. Auch der Chat versteht das.
- Zwanzig Spulen im Regal sind zwanzig Filamente in der Vorwahl. Vier Spulen desselben Materials in vier Farben sind vier Einträge, nicht einer.
- Die Farbe eines Filaments und seine Temperaturen gehören jetzt zusammen. Vorher konnte die Einstellung von Rot auf dem weißen Filament landen.
- Dieselbe Farbe bekommt dieselbe Düse — auch auf der zweiten Platte.
- Im Viewport steht die echte Filamentfarbe. Ein Filament ohne eigene Farbe ist grau, und die Auswahl bleibt daran erkennbar.
- Färben steht jetzt dort, wo man Farbe sucht — vorher lag es unter „Vorbereiten“.
- Das Feld „Farbe des Teils“ zeigte im hellen Thema eine andere Farbe als die Ansicht daneben.
- Wer „PETG“ tippte, bekam „Dieses Materialprofil ist nicht bekannt“. Das Feld ist jetzt eine Auswahl mit den Namen, die es wirklich gibt.
- Die Vorauswahl „— keines —“ wurde beim Übernehmen abgelehnt. Jetzt steht dort ein Wert, den der Dialog auch annimmt.
- Der Farbwähler zeigte Rot, und nach dem Abwählen war das Teil grau.

### Bausteine

- Ein Bolzenscharnier, das fertig beweglich aus dem Drucker kommt. Nichts zusammenstecken, nichts einlegen — der Drucker lässt den Spalt offen.
- Ein Baustein kann mehrere Teile zusammenfassen. So speichern Sie auch bewegliche oder zusammengesetzte Modelle als einen wiederverwendbaren Eintrag im Katalog.
- Den Stift ins Loch legen ging nicht, obwohl beide Merkmale da waren. Jetzt schon.

### Drucken und Slicer

- Beim Slicen wählen Sie, welche Platten mitgehen. Wer Platte 2 slicen wollte, bekam bisher drei Dateien und die Spulen von Platte 1.
- Solidon schreibt dem Slicer jetzt auch Maschinen- und Prozessprofil aus, statt auf seinen Bestand zu verweisen. Sieben Angaben standen in der Datei, hundertsechsunddreißig fuhr der Slicer.
- Der Anfahrcode kommt aus dem Druckerprofil des Herstellers, statt selbst geschrieben zu werden.
- Was keine Bahn mehr legt, sagt die Düse: zu dünne Wände stehen als Befund im Prüfbericht statt als Vorschlag.
- Die Wandstärke-Untergrenze kommt aus dem Materialprofil. Zwei feste Zahlen standen dort, und beide waren falsch — am Centauri sind es 0,84 mm.
- Der Knopf zum Slicen lud zum Klick, obwohl drei Sätze später nichts folgte.
- Eine G-Code-Datei mit der Endung .nc ließ sich öffnen, aber im Öffnen-Dialog nicht finden.

### Was Solidon am Modell sieht

- An eingelesenen Dateien erkennt Solidon jetzt auch dann Bohrungen und Taschen, wenn das Netz ungeschweißt ist. Vorher fand die Erkennung dort nichts.
- Der Prüfbericht meldet „mehrere Teile“ nur noch, wenn es welche sind. Eine Platte aus einem Stück galt bisher als 796 Teile.
- Dieselbe Datei wird nicht mehr fünfzehnmal untersucht. Das spart die Sekunden, die vorher beim Öffnen vergingen.
- Wenn das Vereinfachen nicht so weit kommt wie gewünscht, sagt Solidon es. Bisher blieben 992 Dreiecke stehen, wo 400 gefordert waren, ohne ein Wort.
- Derselbe Hinweis steht einmal im Prüfbericht, nicht nach jedem Schritt erneut.
- Zwei Körper an derselben Stelle sahen aus wie einer, und niemand sagte es.
- Nach dem Vereinigen zeigte ein Merkmal auf ein anderes Loch als vorher.

### Chat und Agent

- Während der Agent arbeitet, steht im Chat, welcher Schritt läuft und welches Werkzeug. Vorher war es bis zu einer Minute still.
- Die Liste der lokalen Modelle sagt bei jedem, wie zuverlässig es Werkzeuge aufruft und wie lange es braucht. Ein Modell, das nur darüber schreibt, ist jetzt als solches erkennbar.
- Bricht die Verbindung zum lokalen Sprachmodell ab, sagt Solidon das — und nennt einen Weg weiter, statt einen Programmfehler zu melden.
- Dasselbe gilt, wenn die Verbindung zum Bilddienst abbricht.
- Der Chat nennt auch kleine Volumenänderungen. Eine gesetzte Bohrung meldete sich bisher als „+0,00 cm³“, und der Vorschlag sah folgenlos aus.

### Ansicht und Bedienung

- Der Objektbaum nennt Zapfen und Gewinde beim Namen, mit Durchmesser und Steigung.
- Ein Schritt, der zwei Körper erzeugt, steht mit zwei Zeilen im Baum — vorher stand dort einer.
- Wer mehr Körper auswählt, als eine Operation nimmt, sieht jetzt, welche verrechnet werden.
- Drucken zeigte dieselbe Zeit an zwei Stellen verschieden — „10 h 5 min“ unten, „605 min“ im Dialog.
- Zahlen und Einheiten stehen überall gleich: Eine Zeile und ihr eigener Tooltip nannten dasselbe Volumen verschieden, und in Zoll gar nichts.
- Ein Maß mit einem Ausdruck lässt sich an jedem Zahlenfeld einschalten — das Handbuch zeigt den Knopf jetzt auch.
- Das Raster im Skizzeneditor zeigte die Weite von dem Moment, in dem man ihn betrat.
- Zwei Textfelder meldeten sich als freiwillig und waren es nie.

### Behoben

- Duplizieren gab dem Original eine neue Kennung, und der Körper verschwand aus der Ansicht.
- Ein exakter Körper, von dem eine Bohrung nichts übrig ließ, stand als leeres Objekt im Baum und ließ sich speichern.
- Die Differenzansicht und die Analysekarten blieben bei exakten Körpern stumm.
- Eine unbekannte Feldart machte jedes Feld still zu einem Textfeld.
- Ein Dialog ließ sich bestätigen, legte einen Schritt in den Verlauf — und im Bild änderte sich nichts.
- Drehen um null Grad lief stumm durch, statt zu sagen, dass nichts geschieht.
- Das Neuerungen-Fenster zeigte fünfundsiebzig Punkte als eine Wand. Jetzt sind sie gegliedert, und die Ankündigung kommt in Ihrer Sprache.

## 0.2.0


### Bausteine
- Eigene Bausteine ohne eine Zeile Code: Wählen Sie Schritte im Verlauf aus und legen Sie sie als Baustein in den Katalog — mit eigenen Feldern, Vorschaubild und frei wählbarem Wertebereich.
- Ein selbst gebauter Baustein reist in der Projektdatei mit. Wer sie öffnet, kann Ihr Teil einsetzen, ohne dass bei ihm etwas installiert sein muss.
- Fünf neue Bausteine im Katalog: Lochwand-Einhänger, Eckwinkel, Standfuß, Kabelclip und Scharnierauge.
- Der Lochwand-Einhänger hält jetzt auch, wenn jemand das Teil beim Abnehmen anhebt — eine federnde Zunge rastet hinter der Platte ein. Abschaltbar, wenn Sie das Teil oft abnehmen.
- Wandhalter, Rippe, Nutfeder, Rastnase, Schnappverbindung und Filmscharnier stehen jetzt im Menü einer angeklickten Fläche. Wer dort einen Wandhalter setzen wollte, fand alles außer ihm.
- Wer einen Baustein aus dem Katalog einsetzt, ohne eine Stelle zu wählen, wird gefragt. Bisher saß er im Nullpunkt, halb im Teil und halb unter der Platte.
- Der Bausteinkatalog lässt sich auch ohne Modell ansehen. Das Einsetzen ist dann gesperrt und sagt warum, statt erst nach der Bestätigung abzusagen.
- Die Mutternfalle und die Kopffreiheit des Schraubenlochs trugen nichts ab: Beide bauten über der Fläche statt darunter.
- Die Magnettasche hält den Magneten wieder: Die Haltelippe wurde bisher an die Tasche angesetzt statt aus ihr ausgespart und verschwand darin.
- Das Schlüsselloch hängt jetzt senkrecht, so dass die Schraube sich beim Absinken verklemmt. Quer liegend wanderte sie seitlich, und der Kopf fand zu wenig Platz.
- Die Mutternfalle trifft die Mutter: Für M5, M6 und M8 stand eine zu geringe Höhe in der Tabelle, bei M5 um sechs Zehntel.

### Zeichnen
- Beim Zeichnen zeigt das Raster, wonach gefangen wird, die Rasterweite lässt sich eintippen, Maße stehen am Zeiger, und die Leiste sagt, auf welcher Fläche Sie zeichnen.
- Im Zeichenmodus wirken die Tastenkürzel wieder — Linie, Kreis, Bogen, Trimmen, Versatz, Strg+Z —, und der Rechtsklick öffnet das Menü der Zeichnung statt das des Modells.
- Einpassen holt die Zeichnung wieder ins Bild, und ein Klick fünf Millimeter neben einem Punkt rastet nicht mehr auf ihn ein.
- Eine Hilfslinie bleibt eine Hilfslinie, auch nachdem sie getrimmt, verlängert, versetzt oder gespiegelt wurde. Bisher wurde eine Mittellinie dabei zur Profilkante und trennte das Teil.
- Der Dialog eines Schritts zeigt die Maße Ihrer Zeichnung statt der Vorgabewerte, und ein Kreis steht mit seinem Durchmesser da, nicht mit dem halben.
- Eine Tasche aus einer Zeichnung mit Loch behält das Loch. Bisher fräste sie die Insel mit weg.
- Ein gezeichnetes Loch wird abgezogen, gleich in welcher Richtung Sie es gezeichnet haben. Bisher kam je nach Klickreihenfolge ein volleres Teil heraus.
- Trimmen schneidet nur noch innerhalb der eigenen Strecke, und Verlängern findet auch Kreise und Bögen als Ziel — bisher sah es nur Linien.
- Ein Übergang zwischen zwei Zeichnungen behält ihre Löcher, und eine Tasche auf einer Seitenwand schneidet in die Wand statt von oben.
- Ein Umriss, der sich selbst kreuzt, wird an der Zeichnung gemeldet, statt einen Körper zu ergeben, der nicht dicht ist und trotzdem exportiert wird.
- Eine Zeichnung mit Loch im Loch behält alle Ebenen, und Projizieren nimmt die Ebene, auf der Sie zeichnen — bisher fiel die dritte Ebene weg und der Schnitt kam von unten.
- Beim Skalieren auf eine bestimmte Breite wurde eine Hilfslinie mitgemessen. Aus fünfzig Millimetern wurden fünf.

### Verlauf und Schritte
- Im Verlauf lassen sich mehrere Schritte auf einmal auswählen.
- Die Grenzen eines Maßes lassen sich nachträglich ändern — bisher galt, was beim Anlegen eingetragen wurde, für immer.
- Einen Schritt nachträglich zu ändern lässt sich zurücknehmen. Bisher entfernte Strg+Z die falsche Handlung und ließ den geänderten Wert stehen.
- Ein Schritt, der auf eine Fläche eines anderen Körpers zeigt, rechnet nach jeder Änderung neu. Bisher blieb ein ausgerichtetes Teil an der alten Stelle, auch nach dem Schließen.
- Merkmale behalten ihre Namen, wenn ein Teil zum Drucken gedreht oder verschoben wird. Schritte und Passungen, die auf sie zeigen, laufen nicht mehr ins Leere.
- Verschwindet die Fläche, bis zu der extrudiert wird, zeigt der Fehler auf dieses Feld und rät, eine andere zu wählen — statt auf die Zeichenebene.

### Werkzeuge und Geometrie
- Senken traf je Achse nur eine Richtung. Von der falschen Seite angeklickt trug es nichts ab und sagte nichts.
- An gestuften Teilen bohrten und stopften Bohrung und Stopfen in die Luft: Die Richtung kam aus dem Hüllquader statt aus dem Material an der Stelle.
- Ein durchgehender Stopfen füllte nur die halbe Bohrung — und ließ ringsum den Spalt stehen, um den die Bohrung für das Material aufgeweitet worden war.
- Gitter füllen setzte Stäbe neben das Teil statt in seinen Hohlraum.
- Die Entlüftung eines ausgehöhlten Teils endet im Hohlraum statt durch die Decke, und die Gewindenut des Drehdeckels reißt kein Loch mehr in seine Decke.
- Vereinigen, Abziehen und Bemalen sagen jetzt, wenn nichts geschehen ist. Bisher blieb ein Schritt im Verlauf über einem unveränderten Bild stehen.
- Zerfällt ein Teil, weil ein Baustein den Träger nicht mehr berührt, meldet der Prüfbericht es als Fehler und empfiehlt, was hilft. Bisher stand die Stückzahl nur als Angabe da.
- Ein Gewinde in einer angeklickten Bohrung schnitt nur deren untere Hälfte. Dasselbe traf die Einpressbuchse.
- Ein Innengewinde wird abgezogen, wie sein Text es sagt. Bisher wuchs stattdessen ein Bolzen in das Kernloch hinein.

### Drucken und Slicer
- Die Materialschätzung für Stützen war um ein Vielfaches daneben: Gerechnet wurde die Fläche unter dem Überhang statt der Säule darunter.
- Die Brückenweite misst die Strecke, die wirklich frei überspannt wird. Ein Kabelkanal meldete bisher die Breite seines Hüllquaders und bekam den falschen Rat.
- Ein Teil, das dünner ist als eine Druckschicht, wird nicht mehr hochkant gestellt.
- Automatisch teilen rechnet den Stiftüberstand zur Bettgrenze und lässt keine Passungen zurück, die auf verschwundene Stellen zeigen.
- Auch bei einer Baugruppe wirkt „Auf das Bett setzen“ jetzt: Sie geht als Ganzes nach unten, die Teile behalten ihre Lage zueinander. Bisher geschah nichts, kommentarlos.
- Die Filamentmenge aus einer G-Code-Datei stimmt wieder. Ein Befehl am Dateiende ließ alles davor anders rechnen und verdoppelte die Summe.
- Ein Drucker- oder Materialwechsel behält, was Sie selbst eingestellt haben. Bisher wurde der ganze Satz zurückgesetzt, ohne Ansage.
- Die Filamentwahl je Materialslot kommt beim Slicer an. Gespeichert wurde bisher der Anzeigetext statt des Profils.

### Ansicht und Bedienung
- Eine gewählte Fläche zählt: Bohrung, Baustein und Skizze kommen dorthin, wo Sie hingezeigt haben. Vorher kostete jede Operation an einer Fläche zwei Klicks.
- Ein Klick auf eine Bohrung schlägt die Schraube vor, die wirklich hindurchgeht — und nennt den gemessenen Durchmesser dazu.
- Nach „Fläche versetzen“ lassen sich die Flächen des Teils wieder anklicken. Bisher blieb nichts übrig, worauf man zeichnen, bohren oder eine Passung setzen konnte.
- Beim Öffnen eines Projekts steht sofort eine Ladeanzeige. Bisher blieb die Mitte des Fensters sekundenlang schwarz oder zeigte den Startbildschirm — das sah nach Absturz aus.
- Ein Klick in die Ansicht trifft nur, was Sie sehen — kein ausgeblendetes Teil, keines von einer anderen Platte. Nach dem Bewegen-Modus stechen die Kanten nicht mehr durch alle Flächen.
- Die Achsansichten von Strg+0 bis Strg+6 rahmen wieder das Modell, statt Druckplatte und Bauraum mit ins Bild zu nehmen.
- Wer ein Teil weit verschoben hat und danach dreht, dreht wieder um das Teil statt um einen Punkt daneben.
- Ein Maß in der Ansicht steht in der Einheit, die Sie eingestellt haben, ein Themenwechsel färbt Druckplatte und Bauraum mit um, und bei mehreren Platten sitzen Etikett und Griff am Teil statt daneben.
- Was ein eingesetzter Baustein mitbringt, steht im Objektbaum unter seinem Namen, und der Knoten bietet an, genau diesen Schritt zu ändern.
- Der Schatten unter dem Teil zeigt jedes Stück einzeln und tritt leiser auf. Zerfällt ein Körper, sieht man es jetzt am Schatten.

### Dateien und Export
- Zwei eingelesene Dateien gleichen Namens gehen nicht mehr verloren. Die zweite überschrieb bisher die erste, und das Projekt ließ sich danach nicht mehr öffnen.
- Eine Adresse ohne Dateiendung sagt jetzt, dass dort eine Webseite steht und wo der Download-Knopf ist, statt „Format nicht erkannt“.
- Beim Export überschrieben sich gleichnamige Teile: eine Datei, zwei Erfolgsmeldungen, ein Teil weg.
- Bei „Speichern unter“ wird jetzt die Projektendung angehängt. Eine als halter.stl gespeicherte Projektdatei war beim Öffnen ein unlesbares Fremdmodell.
- Ein geändertes Projekt geht nicht mehr verloren, wenn Sie eine Datei auf den Startbildschirm ziehen — es wird vorher gefragt.

### Geschwindigkeit und Stabilität
- Die Anwendung verschwindet nicht mehr wortlos, wenn ein Maß geändert, eine Zeichnung gelesen oder ein Schnitt gerechnet wird. Dieselben Rechnungen laufen dabei bis zu sechzigmal schneller.
- Aushöhlen und Verstiften lassen sich wirklich abbrechen. Bei einem gescannten Teil stand der Knopf bisher minutenlang still.
- Große Dateien aus einem Slicer öffnen zügig, ohne dass das Fenster einfriert. Bisher las schon das bloße Zählen der Körper die ganze Datei in den Speicher.
- Bleibt eine Rechnung im Hintergrund stecken, sagt die Anwendung es. Legende, Schichtanalyse und die Suche nach einer neuen Version blieben sonst für immer stehen.
- Abbrechen verwirft auch den bereits eingereihten nächsten Lauf, und der Fortschrittsbalken verschwindet nicht mehr über einer Datei, die noch geschrieben wird.

### Sprachen
- Die im Installer gewählte Sprache gilt sofort, sonst die des Systems. Und eine im Fenster gewählte Sprache wirkt gleich, statt erst beim nächsten Start.
- Ein Sprachwechsel wirkt jetzt im ganzen Fenster. Die Druckeinstellungen blieben bisher in der Sprache, in der die Anwendung gestartet war.
- Die mitgelieferten Beispiele nennen ihre Maße in Ihrer Sprache. „Breite, Tiefe, Höhe“ stand dort bisher deutsch, auch in einer englischen Oberfläche.
- Die Kommandozeile spricht die eingestellte Sprache. Sie gab bisher deutsche Hilfe und deutsche Fehlertexte aus, gleich was gewählt war.

### Chat und Support
- Ein Vorschlag des Chats, der Schritte zurücknimmt, sagt vorher, welche mitgehen. Und Abbrechen bricht wirklich ab, statt im Hintergrund weiterzurechnen.
- Der Chat schafft wieder acht Schritte je Frage statt vier, und die Kostenzeile rechnet nicht mehr zu hoch.
- Was mit einer Rückmeldung an den Support geht, steht vorher im Wortlaut da — auch das Protokoll. Und kommt sie nicht an, nennt die Meldung den wirklichen Grund.

### OpenSCAD
- Für Freiformen wird kein zweites Programm mehr gebraucht: Was OpenSCAD konnte, können die Zeichenwerkzeuge und die Bausteine — eine Installation weniger, um die Sie sich kümmern müssen.
- Ein Projekt mit OpenSCAD-Quelltext öffnet weiterhin, alles andere darin rechnet wie bisher. Der Prüfbericht nennt den Schritt, und „Werte ansehen“ kopiert seinen Quelltext heraus.

## 0.1.5

- Skizziert wird jetzt in der Ansicht selbst: Die Zeichenfläche legt sich über das Modell, statt es zu ersetzen, und ein Klick in die Ansicht setzt einen Punkt auf der Skizzenebene.
- Das Raster der Zeichenfläche zeigt wieder das, wonach gefangen wird. Es stand zeitweise auf einem Zehntelmillimeter und lag zur Hälfte hinter der Bedienleiste.
- Ein Klick mitten in eine Bohrung wählt die Bohrung. Vorher traf er die Fläche daneben oder nichts — in der Draufsicht hob er die Auswahl sogar auf.
- Ein Klick in einen rechteckigen Ausschnitt wählt das Teil, statt die Auswahl aufzuheben.
- Der Chat findet Ihr lokales Modell jetzt unter jeder Schreibweise der Adresse. Bisher musste dort die vollständige Adresse mit /api/chat stehen.
- Ein Zugangsschlüssel, den der Anbieter ablehnt, sperrt Ihr lokales Modell nicht mehr aus. Der Chat wechselt selbst zum nächsten verfügbaren Modell, statt weiter denselben Schlüssel zu schicken.
- Fehlermeldungen des Chats sagen jetzt, welches Modell gemeint ist. Bisher stand über einem Schlüsselfehler nur, das Sprachmodell habe nicht geantwortet.
- Das Feld für die Adresse eines Dienstes nennt ein Beispiel und sagt, dass dort kein Ordner hingehört. Wer trotzdem einen einträgt, bekommt es noch einmal mit dem Grund darüber.
- Der Einrichtungsdialog stürzt nicht mehr ab, wenn in einem Adressfeld ein Ordnerpfad steht oder im Schlüsselfeld ein versehentlich kopierter Text.
- Aufklappmenüs zeigen wieder alle Einträge. Sobald ein Feld den Tastaturfokus hatte, fehlte im geöffneten Menü ein halber Eintrag.
- Strg+Z und Strg+Y stehen jetzt am Menüeintrag, so wie die übrigen vierzehn Tastenkürzel. Sie funktionierten immer, nur genannt hat sie nichts.
- Fehlermeldungen beim Zeichnen sagen, welche Grenze gerissen ist. Über „zwischen drei und vierundsechzig Ecken“ stand vorher nur „Die Eingabe war so nicht verwendbar“.
- Zusammengelegte Handlungen stehen im selben Menü und erscheinen in der Befehlssuche nur noch einmal — etwa Aushöhlen und Exakt aushöhlen.
- Ein Menüeintrag „Gewinde“ sagt jetzt, wohin das Gewinde kommt — in eine Bohrung oder auf einen Bolzen.
- Die spanische Oberfläche nennt Merkmale überall gleich. In derselben Liste standen vorher zwei Wörter für dieselbe Sache.
- Die Anwendung gibt Speicher wieder frei, wenn ein Fenster geschlossen wird, und räumt beim Beenden sauberer auf.
- Das Bild, das mit einer Rückmeldung mitgeht, zeigt jetzt auch das Modell. Bisher stand in der Mitte eine schwarze Fläche — ausgerechnet dort, wo das Teil steht, um das es geht.


## 0.1.4

- Während der Demo fragt Solidon einmal nach: Nach einer halben Stunde Arbeit legt sich eine Karte über die Ansicht und fragt, wie es läuft. Sie hält nichts an, und ohne Ihren Klick geht nichts hinaus.
- Wer eine Fläche anklickt und einen Baustein einsetzt, bekommt ihn senkrecht auf dieser Fläche statt senkrecht nach oben. An einer Seitenwand stand ein Schraubenloch vorher quer zur Wand.
- Ein Baustein an einer Bohrung übernimmt deren Maß. An einer Bohrung mit 5,19 mm schlug die Einpressbuchse vorher M3 vor — die trägt dort nichts ab.
- Ein Klick, bei dem die Hand ein wenig wackelt, wählt wieder aus, statt das Teil ein Zehntel zu verschieben.
- Ein ausgewähltes Teil lässt sich direkt mit der Maus verschieben — anfassen und ziehen, ohne vorher „Bewegen“ zu holen. Der Griff bleibt für das Genaue: achsweise und in Rasterschritten.
- Von unten schaut man durch die Druckplatte hindurch. Wer die Unterseite eines Teils bearbeitet, dreht die Ansicht darunter und sieht das Teil statt der Platte.
- Eine Bohrung lässt sich auch anwählen, indem man mitten hineinklickt — nicht nur auf ihre Wand.
- Die Befehlssuche versteht jetzt auch Alltagswörter: „kopieren“, „löschen“, „öffnen“ und „färben“ führten vorher nirgendwohin, obwohl es alle vier gibt.
- Die Suche findet auch, wer nicht das Fachwort kennt. Wer „verstärken“, „einrasten“ oder „verschrauben“ eintippt, landet bei der Versteifungsrippe, der Rastnase und dem Schraubenloch.
- Zwei Menüeinträge hießen beide „vernetzen“. Sie heißen jetzt „Kanten verfeinern“ und „Dreiecke angleichen“ — das erste teilt lange Kanten, das zweite gleicht die Dreiecksgrößen an.
- Die Anwendung spricht die Sprache, die Sie anderswo hören: „exakter Körper“ statt „B-Rep“, Bett statt Druckfläche, Platte für die Belegung.
- Solidon sieht beim Start nach, ob es eine neuere Fassung gibt, und bietet sie an. Geladen und installiert wird erst auf Ihre Bestätigung; abschalten lässt es sich in den Einstellungen.
- Ein lokales Sprachmodell darf jetzt zehn Minuten rechnen. Vorher brach der Chat nach zwei Minuten ab und bat um einen Fehlerbericht — für eine Rechnung, die einfach länger dauerte.
- Ein Ring wird als ein Merkmal erkannt und nicht mehr als drei übereinanderliegende Wülste.
- Der Eintrag „Fläche aufdicken“ tut jetzt, was er verspricht. Vorher versetzte er die Fläche.
- Der Fenstertitel nennt das geöffnete Modell, auch wenn es noch keine Projektdatei dazu gibt.
- Beim Zeichnen steht das Maß an der Spitze der Linie statt am Fensterrand.
- Ein gesperrter Menüeintrag sagt jetzt, warum er gesperrt ist. Der Grund stand vorher da und war unsichtbar.
- Der Fehlerbericht nimmt den Stand der Szene mit: Objekte mit Maßen, Merkmale, Parameter und den Verlauf. Damit lässt sich ein Fehler nachstellen, statt ihn zu erraten.
- Mehrere Abstürze beim Schließen von Fenstern und Dialogen sind behoben.

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

- Getippte Kommazahlen werden überall richtig gelesen. „12,5“ blieb zwölfeinhalb — vorher konnte daraus 125 werden, ohne Rückfrage und ohne Hinweis.
- Jedes der sechsundfünfzig Felder in den Druckeinstellungen sagt jetzt, was es bewirkt, wenn man es bewegt.
- Druckzeit und Materialbedarf werden genauer geschätzt, vor allem bei ausgehöhlten Teilen.
- Die Übergabe an den Slicer trifft die Platte. Bei CuraEngine lagen Teile daneben.
- Beim Trennen mit Verstiftung sitzen die Gegenlöcher in der richtigen Hälfte.
- Millimeter und Zoll gelten jetzt überall, wo eine Zahl steht — auch in den Werkzeugleisten und beim Bemalen.
- Der Fortschritt bleibt stehen, bis wirklich fertig gerechnet ist, und das Fenster bleibt dabei bedienbar.
- Alle Tastenkürzel stehen jetzt in einer Übersicht: im Hilfemenü unter „Tastenkürzel“, oder mit einem Druck auf die Fragezeichentaste.
