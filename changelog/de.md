# Was neu ist

Diese Datei ist das, was im Update-Fenster steht — und sonst nichts. Sie ist
**keine** Liste der Änderungen: Von 97 Commits zwischen 0.1.1 und 0.1.2 stehen
hier acht Zeilen, und die Auswahl ist die Arbeit. Ein Punkt gehört hierher,
wenn jemand ihn beim Benutzen merkt.

Also: keine Commit-Meldungen, keine Modulnamen, keine Paragraphen. „Der Balken
verschwand, während die Anwendung noch vier Sekunden rechnete“ ist ein guter
Commit und ein schlechter Punkt; „Der Fortschritt bleibt stehen, bis wirklich
fertig gerechnet ist“ sagt dasselbe für den, der davorsitzt.

Je Sprache eine Datei in diesem Ordner, wie bei den Katalogen — und alle tragen
dieselben Punkte in derselben Reihenfolge (`tests/test_changelog.py`).
`tools/make_download.py` holt daraus den Abschnitt der aktuellen Version und
schreibt ihn in `website/version.json`.

**0.2.0 ist die ausdrückliche Ausnahme von allem darüber**, und sie hebt es
nicht auf: 73 Punkte aus 244 Commits, weil Robert alles behalten wollte —
zwischen 0.1.5 und 0.2.0 liegt kein Wartungsschritt, sondern ein halbes Jahr
Arbeit in einem Sprung, samt einem Absturz, den der Kunde von heute noch hat.
Wer den nächsten Abschnitt schreibt, fängt wieder bei acht Zeilen an; die
Obergrenze in `app/core/updates.py` ist mitgewachsen und trägt den Vermerk,
dass eine weitere Erhöhung eine Begründung braucht.

**Und was nicht hineingehört, gleich wie kundenspürbar es ist:** eine
geschlossene Sicherheits- oder Lizenzlücke. Der Satz „eine Uhr in der Zukunft
verbrannte die Frist“ erzählt jedem, der eine ältere Fassung hat, wo der Hebel
sitzt. Drei solche Punkte standen am 26.08.2026 schon im Abschnitt und sind
wieder heraus (Entscheidung Robert). Wo ein Nutzen bleibt, der ohne den
Mechanismus auskommt — „die Meldung nennt den wirklichen Grund“ —, steht der
Nutzen da und sonst nichts.

## 0.2.0

- Eigene Bausteine ohne eine Zeile Code: Wählen Sie Schritte im Verlauf aus und legen Sie sie als Baustein in den Katalog — mit eigenen Feldern, Vorschaubild und geprüftem Wertebereich.
- Ein selbst gebauter Baustein reist in der Projektdatei mit. Wer sie öffnet, kann Ihr Teil einsetzen, ohne dass bei ihm etwas installiert sein muss.
- Fünf neue Bausteine im Katalog: Lochwand-Einhänger, Eckwinkel, Standfuß, Kabelclip und Scharnierauge.
- Der Lochwand-Einhänger hält jetzt auch, wenn jemand das Teil beim Abnehmen anhebt — eine federnde Zunge rastet hinter der Platte ein. Abschaltbar, wenn Sie das Teil oft abnehmen.
- Eine gewählte Fläche zählt: Bohrung, Baustein und Skizze kommen dorthin, wo Sie hingezeigt haben. Vorher kostete jede Operation an einer Fläche zwei Klicks.
- Wandhalter, Rippe, Nutfeder, Rastnase, Schnappverbindung und Filmscharnier stehen jetzt im Menü einer angeklickten Fläche. Wer dort einen Wandhalter setzen wollte, fand alles außer ihm.
- Wer einen Baustein aus dem Katalog einsetzt, ohne eine Stelle zu wählen, wird gefragt. Bisher saß er im Nullpunkt, halb im Teil und halb unter der Platte.
- Der Bausteinkatalog lässt sich auch ohne Modell ansehen. Das Einsetzen ist dann gesperrt und sagt warum, statt erst nach der Bestätigung abzusagen.
- Beim Zeichnen zeigt das Raster, wonach gefangen wird, die Rasterweite lässt sich eintippen, Maße stehen am Zeiger, und die Leiste sagt, auf welcher Fläche Sie zeichnen.
- Im Zeichenmodus wirken die Tastenkürzel wieder — Linie, Kreis, Bogen, Trimmen, Versatz, Strg+Z —, und der Rechtsklick öffnet das Menü der Zeichnung statt das des Modells.
- Einpassen holt die Zeichnung wieder ins Bild, und ein Klick fünf Millimeter neben einem Punkt rastet nicht mehr auf ihn ein.
- Eine Hilfslinie bleibt eine Hilfslinie, auch nachdem sie getrimmt, verlängert, versetzt oder gespiegelt wurde. Bisher wurde eine Mittellinie dabei zur Profilkante und trennte das Teil.
- Der Dialog eines Schritts zeigt die Maße Ihrer Zeichnung statt der Vorgabewerte, und ein Kreis steht mit seinem Durchmesser da, nicht mit dem halben.
- Im Verlauf lassen sich mehrere Schritte auf einmal auswählen.
- Die Grenzen eines Maßes lassen sich nachträglich ändern — bisher galt, was beim Anlegen eingetragen wurde, für immer.
- Die Anwendung verschwindet nicht mehr wortlos, wenn ein Maß geändert, eine Zeichnung gelesen oder ein Schnitt gerechnet wird. Dieselben Rechnungen laufen dabei bis zu sechzigmal schneller.
- Einen Schritt nachträglich zu ändern lässt sich zurücknehmen. Bisher entfernte Strg+Z die falsche Handlung und ließ den geänderten Wert stehen.
- Aushöhlen und Verstiften lassen sich wirklich abbrechen. Bei einem gescannten Teil stand der Knopf bisher minutenlang still.
- Ein Schritt, der auf eine Fläche eines anderen Körpers zeigt, rechnet nach jeder Änderung neu. Bisher blieb ein ausgerichtetes Teil an der alten Stelle, auch nach dem Schließen.
- Die Materialschätzung für Stützen war um ein Vielfaches daneben: Gerechnet wurde die Fläche unter dem Überhang statt der Säule darunter.
- Die Brückenweite misst die Strecke, die wirklich frei überspannt wird. Ein Kabelkanal meldete bisher die Breite seines Hüllquaders und bekam den falschen Rat.
- Senken traf je Achse nur eine Richtung. Von der falschen Seite angeklickt trug es nichts ab und sagte nichts.
- An gestuften Teilen bohrten und stopften Bohrung und Stopfen in die Luft: Die Richtung kam aus dem Hüllquader statt aus dem Material an der Stelle.
- Ein durchgehender Stopfen füllte nur die halbe Bohrung — und ließ ringsum den Spalt stehen, um den die Bohrung für das Material aufgeweitet worden war.
- Gitter füllen setzte Stäbe neben das Teil statt in seinen Hohlraum.
- Die Entlüftung eines ausgehöhlten Teils endet im Hohlraum statt durch die Decke, und die Gewindenut des Drehdeckels reißt kein Loch mehr in seine Decke.
- Vereinigen, Abziehen und Bemalen sagen jetzt, wenn nichts geschehen ist. Bisher blieb ein Schritt im Verlauf über einem unveränderten Bild stehen.
- Zerfällt ein Teil, weil ein Baustein den Träger nicht mehr berührt, meldet der Prüfbericht es als Fehler und empfiehlt, was hilft. Bisher stand die Stückzahl nur als Angabe da.
- Merkmale behalten ihre Namen, wenn ein Teil zum Drucken gedreht oder verschoben wird. Schritte und Passungen, die auf sie zeigen, laufen nicht mehr ins Leere.
- Ein Gewinde in einer angeklickten Bohrung schnitt nur deren untere Hälfte. Dasselbe traf die Einpressbuchse.
- Ein Innengewinde wird abgezogen, wie sein Text es sagt. Bisher wuchs stattdessen ein Bolzen in das Kernloch hinein.
- Die Mutternfalle und die Kopffreiheit des Schraubenlochs trugen nichts ab: Beide bauten über der Fläche statt darunter.
- Die Magnettasche hält den Magneten wieder: Die Haltelippe wurde bisher an die Tasche angesetzt statt aus ihr ausgespart und verschwand darin.
- Das Schlüsselloch hängt jetzt senkrecht, so dass die Schraube sich beim Absinken verklemmt. Quer liegend wanderte sie seitlich, und der Kopf fand zu wenig Platz.
- Die Mutternfalle trifft die Mutter: Für M5, M6 und M8 stand eine zu geringe Höhe in der Tabelle, bei M5 um sechs Zehntel.
- Ein Teil, das dünner ist als eine Druckschicht, wird nicht mehr hochkant gestellt.
- Automatisch teilen rechnet den Stiftüberstand zur Bettgrenze und lässt keine Passungen zurück, die auf verschwundene Stellen zeigen.
- Eine Tasche aus einer Zeichnung mit Loch behält das Loch. Bisher fräste sie die Insel mit weg.
- Ein gezeichnetes Loch wird abgezogen, gleich in welcher Richtung Sie es gezeichnet haben. Bisher kam je nach Klickreihenfolge ein volleres Teil heraus.
- Trimmen schneidet nur noch innerhalb der eigenen Strecke, und Verlängern findet auch Kreise und Bögen als Ziel — bisher sah es nur Linien.
- Ein Übergang zwischen zwei Zeichnungen behält ihre Löcher, und eine Tasche auf einer Seitenwand schneidet in die Wand statt von oben.
- Ein Umriss, der sich selbst kreuzt, wird an der Zeichnung gemeldet, statt einen Körper zu ergeben, der nicht dicht ist und trotzdem exportiert wird.
- Eine Zeichnung mit Loch im Loch behält alle Ebenen, und Projizieren nimmt die Ebene, auf der Sie zeichnen — bisher fiel die dritte Ebene weg und der Schnitt kam von unten.
- Nach „Fläche versetzen“ lassen sich die Flächen des Teils wieder anklicken. Bisher blieb nichts übrig, worauf man zeichnen, bohren oder eine Passung setzen konnte.
- Verschwindet die Fläche, bis zu der extrudiert wird, zeigt der Fehler auf dieses Feld und rät, eine andere zu wählen — statt auf die Zeichenebene.
- Ein Klick auf eine Bohrung schlägt die Schraube vor, die wirklich hindurchgeht — und nennt den gemessenen Durchmesser dazu.
- Große Dateien aus einem Slicer öffnen zügig, ohne dass das Fenster einfriert. Bisher las schon das bloße Zählen der Körper die ganze Datei in den Speicher.
- Auch bei einer Baugruppe wirkt „Auf das Bett setzen“ jetzt: Sie geht als Ganzes nach unten, die Teile behalten ihre Lage zueinander. Bisher geschah nichts, kommentarlos.
- Zwei eingelesene Dateien gleichen Namens gehen nicht mehr verloren. Die zweite überschrieb bisher die erste, und das Projekt ließ sich danach nicht mehr öffnen.
- Eine Adresse ohne Dateiendung sagt jetzt, dass dort eine Webseite steht und wo der Download-Knopf ist, statt „Format nicht erkannt“.
- Die Filamentmenge aus einer G-Code-Datei stimmt wieder. Ein Befehl am Dateiende ließ alles davor anders rechnen und verdoppelte die Summe.
- Beim Skalieren auf eine bestimmte Breite wurde eine Hilfslinie mitgemessen. Aus fünfzig Millimetern wurden fünf.
- Beim Export überschrieben sich gleichnamige Teile: eine Datei, zwei Erfolgsmeldungen, ein Teil weg.
- Beim Öffnen eines Projekts steht sofort eine Ladeanzeige. Bisher blieb die Mitte des Fensters sekundenlang schwarz oder zeigte den Startbildschirm — das sah nach Absturz aus.
- Ein Klick in die Ansicht trifft nur, was Sie sehen — kein ausgeblendetes Teil, keines von einer anderen Platte. Nach dem Bewegen-Modus stechen die Kanten nicht mehr durch alle Flächen.
- Die Achsansichten von Strg+0 bis Strg+6 rahmen wieder das Modell, statt Druckplatte und Bauraum mit ins Bild zu nehmen.
- Wer ein Teil weit verschoben hat und danach dreht, dreht wieder um das Teil statt um einen Punkt daneben.
- Ein Maß in der Ansicht steht in der Einheit, die Sie eingestellt haben, ein Themenwechsel färbt Druckplatte und Bauraum mit um, und bei mehreren Platten sitzen Etikett und Griff am Teil statt daneben.
- Was ein eingesetzter Baustein mitbringt, steht im Objektbaum unter seinem Namen, und der Knoten bietet an, genau diesen Schritt zu ändern.
- Der Schatten unter dem Teil zeigt jedes Stück einzeln und tritt leiser auf. Zerfällt ein Körper, sieht man es jetzt am Schatten.
- Bleibt eine Rechnung im Hintergrund stecken, sagt die Anwendung es. Legende, Schichtanalyse und die Suche nach einer neuen Version blieben sonst für immer stehen.
- Abbrechen verwirft auch den bereits eingereihten nächsten Lauf, und der Fortschrittsbalken verschwindet nicht mehr über einer Datei, die noch geschrieben wird.
- Die im Installer gewählte Sprache gilt sofort, sonst die des Systems. Und eine im Fenster gewählte Sprache wirkt gleich, statt erst beim nächsten Start.
- Ein Sprachwechsel wirkt jetzt im ganzen Fenster. Die Druckeinstellungen blieben bisher in der Sprache, in der die Anwendung gestartet war.
- Die mitgelieferten Beispiele nennen ihre Maße in Ihrer Sprache. „Breite, Tiefe, Höhe“ stand dort bisher deutsch, auch in einer englischen Oberfläche.
- Die Kommandozeile spricht die eingestellte Sprache. Sie gab bisher deutsche Hilfe und deutsche Fehlertexte aus, gleich was gewählt war.
- Ein Drucker- oder Materialwechsel behält, was Sie selbst eingestellt haben. Bisher wurde der ganze Satz zurückgesetzt, ohne Ansage.
- Die Filamentwahl je Materialslot kommt beim Slicer an. Gespeichert wurde bisher der Anzeigetext statt des Profils.
- Bei „Speichern unter“ wird jetzt die Projektendung angehängt. Eine als halter.stl gespeicherte Projektdatei war beim Öffnen ein unlesbares Fremdmodell.
- Ein geändertes Projekt geht nicht mehr verloren, wenn Sie eine Datei auf den Startbildschirm ziehen — es wird vorher gefragt.
- Ein Vorschlag des Chats, der Schritte zurücknimmt, sagt vorher, welche mitgehen. Und Abbrechen bricht wirklich ab, statt im Hintergrund weiterzurechnen.
- Der Chat schafft wieder acht Schritte je Frage statt vier, und die Kostenzeile rechnet nicht mehr zu hoch.
- Was mit einer Rückmeldung an den Support geht, steht vorher im Wortlaut da — auch das Protokoll. Und kommt sie nicht an, nennt die Meldung den wirklichen Grund.


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
