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

## 0.2.0

- Eigene Bausteine ohne eine Zeile Code: Wählen Sie Schritte im Verlauf aus und legen Sie sie als Baustein in den Katalog — mit eigenen Feldern, Vorschaubild und geprüftem Wertebereich.
- Ein selbst gebauter Baustein reist in der Projektdatei mit. Wer sie öffnet, kann Ihr Teil einsetzen, ohne dass bei ihm etwas installiert sein muss.
- Sechs neue Bausteine im Katalog: Lochwand-Einhänger, Wandhalter, Eckwinkel, Standfuß, Kabelclip und Scharnierauge.
- Der Lochwand-Einhänger hält jetzt auch, wenn jemand das Teil beim Abnehmen anhebt — eine federnde Zunge rastet hinter der Platte ein. Abschaltbar, wenn Sie das Teil oft abnehmen.
- Eine gewählte Fläche zählt: Bohrung, Baustein und Skizze kommen dorthin, wo Sie hingezeigt haben. Vorher kostete jede Operation an einer Fläche zwei Klicks.
- Beim Zeichnen zeigt das Raster, wonach gefangen wird, die Rasterweite lässt sich eintippen, Maße stehen am Zeiger, und die Leiste sagt, auf welcher Fläche Sie zeichnen.
- Im Verlauf lassen sich mehrere Schritte auf einmal auswählen.
- Die Grenzen eines Maßes lassen sich nachträglich ändern — bisher galt, was beim Anlegen eingetragen wurde, für immer.
- Die Materialschätzung für Stützen war um ein Vielfaches daneben: Gerechnet wurde die Fläche unter dem Überhang statt der Säule darunter.
- Senken traf je Achse nur eine Richtung. Von der falschen Seite angeklickt trug es nichts ab und sagte nichts.
- An gestuften Teilen bohrten und stopften Bohrung und Stopfen in die Luft: Die Richtung kam aus dem Hüllquader statt aus dem Material an der Stelle.
- Ein durchgehender Stopfen füllte nur die halbe Bohrung — und ließ ringsum den Spalt stehen, um den die Bohrung für das Material aufgeweitet worden war.
- Gitter füllen setzte Stäbe neben das Teil statt in seinen Hohlraum.
- Ein Gewinde in einer angeklickten Bohrung schnitt nur deren untere Hälfte. Dasselbe traf die Einpressbuchse.
- Die Mutternfalle und die Kopffreiheit des Schraubenlochs trugen nichts ab: Beide bauten über der Fläche statt darunter.
- Ein Teil, das dünner ist als eine Druckschicht, wird nicht mehr hochkant gestellt.
- Automatisch teilen rechnet den Stiftüberstand zur Bettgrenze und lässt keine Passungen zurück, die auf verschwundene Stellen zeigen.
- Eine Tasche aus einer Zeichnung mit Loch behält das Loch. Bisher fräste sie die Insel mit weg.
- Ein Klick auf eine Bohrung schlägt die Schraube vor, die wirklich hindurchgeht — und nennt den gemessenen Durchmesser dazu.
- Eine Datei aus einem Slicer kam mit doppelten Körpern an: Ein Teil mit siebzehn Objekten wurde siebzehnmal gelesen, mit doppeltem Volumen und doppelter Druckzeit.
- Beim Skalieren auf eine bestimmte Breite wurde eine Hilfslinie mitgemessen. Aus fünfzig Millimetern wurden fünf.
- Beim Export überschrieben sich gleichnamige Teile: eine Datei, zwei Erfolgsmeldungen, ein Teil weg.
- Ein Sprachwechsel wirkt jetzt im ganzen Fenster. Die Druckeinstellungen blieben bisher in der Sprache, in der die Anwendung gestartet war.
- Ein Drucker- oder Materialwechsel behält, was Sie selbst eingestellt haben. Bisher wurde der ganze Satz zurückgesetzt, ohne Ansage.
- Die Filamentwahl je Materialslot kommt beim Slicer an. Gespeichert wurde bisher der Anzeigetext statt des Profils.
- Ein geändertes Projekt geht nicht mehr verloren, wenn Sie eine Datei auf den Startbildschirm ziehen — es wird vorher gefragt.
- Ein Vorschlag des Chats, der Schritte zurücknimmt, sagt vorher, welche mitgehen. Und Abbrechen bricht wirklich ab, statt im Hintergrund weiterzurechnen.
- Eine falsch gestellte Uhr nimmt die Demo nicht mehr mit: Ein Rechner, dessen Datum in der Zukunft stand, verbrannte die Frist dauerhaft.
- Wer eine Lizenz hat, wird bei einer beschädigten Programmdatei nicht mehr zum Kauf aufgefordert, sondern erfährt, was wirklich los ist.
- Eine Projektdatei von jemand anderem sagt vor dem ersten Rechnen, wenn sie Quelltext für ein externes Programm mitbringt — auf jedem Weg und in jeder Verschachtelung.


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

- Getippte Kommazahlen werden überall richtig gelesen. „12,5" blieb zwölfeinhalb — vorher konnte daraus 125 werden, ohne Rückfrage und ohne Hinweis.
- Jedes der sechsundfünfzig Felder in den Druckeinstellungen sagt jetzt, was es bewirkt, wenn man es bewegt.
- Druckzeit und Materialbedarf werden genauer geschätzt, vor allem bei ausgehöhlten Teilen.
- Die Übergabe an den Slicer trifft die Platte. Bei CuraEngine lagen Teile daneben.
- Beim Trennen mit Verstiftung sitzen die Gegenlöcher in der richtigen Hälfte.
- Millimeter und Zoll gelten jetzt überall, wo eine Zahl steht — auch in den Werkzeugleisten und beim Bemalen.
- Der Fortschritt bleibt stehen, bis wirklich fertig gerechnet ist, und das Fenster bleibt dabei bedienbar.
- Alle Tastenkürzel stehen jetzt in einer Übersicht: im Hilfemenü unter „Tastenkürzel", oder mit einem Druck auf die Fragezeichentaste.
