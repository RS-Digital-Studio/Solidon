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

## 0.6.0

### Bedienung und System

- Die Demo läuft jetzt bis zum 30. November 2026. Solidon3D 1.0 ist für den 1. Dezember geplant, Ihre Projekte bleiben erhalten.
- Am Mac braucht Solidon jetzt macOS 14 oder neuer. Jeder Mac ab 2018 kann es kostenlos installieren.
- Auf Intel-Macs mit macOS 26 startet Solidon jetzt. Version 0.5.3 blieb dort beim Start hängen.
- Am Mac bricht *Abbrechen* eine laufende Antwort des lokalen Modells sofort ab.
- Am Mac öffnet Return den gewählten Eintrag im Startbildschirm, in *Funktion suchen* und im Prüfbericht.
- Unter Linux kommen Eingaben über Fcitx5 und IBus jetzt auch im Flatpak und im AppImage im Textfeld an.
- Die Deinstallation unter Windows lässt keine Einträge der Dateizuordnung in der Registrierung zurück.
- Entf wirkt auch, wenn der Reiter *Auswahl* den Fokus hat, und entfernt mehrere markierte Körper in einem Schritt. Tut die Taste nichts, nennt die Statuszeile den Grund.
- Der Rechtsklick an Körpern bietet *Objekt entfernen* und bei mehreren *Vereinigen*. *Aushöhlen* steht auch an einer gewählten Fläche, sie wird die Öffnung.
- Die Karten links und rechts lassen sich am Griff verschieben, an den Rand legen oder schweben lassen. *Ansicht → Karten an ihren Platz* legt sie zurück.
- Die Karten lassen sich auch unten links, unten rechts und am unteren Rand anordnen.
- Reiter lassen sich umordnen und in eigene Fenster ziehen, auch auf einen zweiten Bildschirm. Schließen oder *Zurück in Solidon* holt ihren Inhalt zurück.
- Solidon merkt sich die Anordnung. Auch wenn ein Bildschirm fehlt, bleiben die Fenster erreichbar.
- Während neu gerechnet wird, sagt der Prüfbericht *Wird neu berechnet …* und zeigt die bisherigen Zeilen als vorigen Stand. Bisher sahen alte Fehler dabei aus, als gälten sie noch.
- Scheitert die schnelle Rechnung an einem Schritt, rechnet Solidon ihn im selben Lauf gründlich nach, statt anzuhalten.
- Sagt ein Befund, dass ein Schritt nichts bewirkt hat, öffnet er diesen Schritt mit dem passenden Feld.
- Entfernen Sie einen Körper, spricht der Prüfbericht nicht mehr über ihn, und der Verlauf zeigt, welche Schritte danach nichts mehr hinterlassen.
- Eine gewählte Bohrung fällt nach dem Neurechnen nicht mehr still auf ihren Körper zurück. Bisher konnte Entf danach den ganzen Körper entfernen.
- Jede Funktion heißt überall gleich. Das Werkzeug *Teilen* bietet *An Ebene teilen*, *An gezeichneter Linie teilen* und *In Einzelteile aufteilen*.
- Am gewählten Körper steht *Automatisch teilen …* jetzt unter *Vorbereiten*.
- Im ruhenden Fenster ist nur *Bausteine* farbig hervorgehoben. Rot tragen nur Knöpfe, die etwas verwerfen oder löschen, und Rückfragen öffnen mit dem Fokus auf *Abbrechen*.
- Im Zeichenmodus ist der Reiter *Auswahl* ausgeblendet. Die Liste der Bedingungen zeigt die der gewählten Punkte und Linien und jeden Widerspruch.
- In der Parameterkarte steht unter einem Maß nur noch „Nicht verwendet“, wo das zutrifft. Wie viele feste Zahlen sich an Maße binden lassen, sagt der Knopf.
- Der Fehlerbericht hängt ein Absturzprotokoll nur noch an, wenn Solidon wirklich abgestürzt ist.
- Die Karte der Tour ist so hoch wie ihre Schritte. Ein Schritt klappt per Klick oder Leertaste auf, und keine Sprechblase liegt mehr über der Ansicht.
- Zeigt ein Tourschritt auf den Prüfbericht, bleibt die Tour sichtbar. Der Reiter ist gerahmt, und der Schritt sagt, welchen Reiter Sie öffnen.
- Ein Klick auf das i neben einer Handlung im Reiter *Auswahl* öffnet das Handbuch an der Stelle, die sie erklärt.
- Jedes Maß eines Bausteins lässt sich über fx an ein Projektmaß binden, auch wenn noch kein Ausdruck darin steht.
- Nach dem Ziehen am Griff einer Vorschau bleibt keine Zahl über der Ansicht stehen. Eine dabei getippte Zahl verschiebt die Vorschau, nicht den gewählten Körper.
- Nach *Reparieren und erneut versuchen* und verwandten Wegen heißt im Verlauf kein weiterrechnender Schritt mehr „gelöscht“. Hält die Kette erneut an, ist der Schritt markiert.
- Der Knopf *Filamente* steht jetzt in der Kopfzeile. Er listet die Filamente des Projekts und führt ins Filamentlager.
- Ein anderes Filament steht sofort im Bild, auch an Bausteinen und STEP-Teilen, und Solidon rechnet dafür nichts neu. Gewählte Körper zeigen ihre Filamentfarbe unter der Markierung.
- Im Reiter *Auswahl* weist das Filamentfeld erst mit Klick oder Enter zu. Pfeiltasten und Tippen blättern nur, und das Mausrad rollt den Reiter.
- In den übersetzten Fassungen rollt *Neues Filament* nicht mehr seitwärts, wenn das Fenster kürzer ist als sein Inhalt.
- Große Modelle laden spürbar schneller und brauchen weniger Arbeitsspeicher, auch mit langem Verlauf und auf Rechnern mit 8 GB.
- Auch in einem langen Verlauf rechnet ein neuer Schritt kaum länger als der erste.
- Rückgängig und Wiederholen gehen schneller, und nicht mehr gebrauchter Arbeitsspeicher wird gleich wieder frei.
- Das Auflösen von Überschneidungen und der Export als 3MF gehen deutlich schneller.
- Die Arbeitsfläche wird beim Öffnen großer 3MF-Dateien schneller angezeigt.
- Ein eingefügtes Modell steht danach im Bild, auch wenn es neben einem herangezoomten Modell landet.
- Im Bausteinkatalog steht *Bausteine verwalten* offen, solange es noch keinen eigenen Baustein gibt.

### Drucken und Übergabe an den Slicer

- Unter Linux erzeugt Solidon die Druckdatei jetzt auch mit Cura als Flatpak oder AppImage.
- Unter Linux stehen die Drucker von OrcaSlicer, Bambu Studio, ElegooSlicer und Creality Print als AppImage sofort zur Wahl, auch wenn der Slicer noch nie geöffnet wurde.
- Der Druckdialog bietet die Drucker des gewählten Slicers an, wie *Erste Schritte* und *Einstellungen*. Ein so übernommener Drucker bleibt bei seinem Slicer.
- Im Druckdialog lässt sich der Slicer wechseln wie in *Erste Schritte*, auch über *Programm wählen …* für einen, den Solidon nicht selbst findet.
- Ein Drucker aus Solidons Liste und derselbe aus dem Slicer gelten als ein Gerät. Der Druckdialog wählt das Slicerprofil mit der richtigen Düse, und die Druckdatei trägt den Startcode.
- Ohne gemerktes Slicerprofil nehmen Export und Hauptfenster, was der Druckdialog für den Drucker vorschlägt, samt Maschine und Prozess des Herstellers.
- Zur Wahl stehen nur noch Slicer, mit denen Solidon arbeitet, dazu Resin-Slicer wie ChituBox und Lychee. Bambu Studio als AppImage zählt jetzt dazu.
- Startcode und Bauraum kommen nur noch von genau Ihrem Drucker, nicht von einem anderen Modell derselben Reihe.
- Der Druckdialog ordnet die Profile des Slicers deutlich schneller zu, beim Öffnen und nach jedem Slicerwechsel.
- Die geschätzte Druckzeit liegt näher an der des Slicers, bei Teilen mit Stützen deutlich näher.
- Ob Stützen und Skirt auf dem Bett Platz haben, misst die Prüfung nur noch unter den Überhängen. Teile nahe am Rand bekommen keine grundlose Warnung mehr.
- Übernommene Vorschläge lassen kaum noch Überhänge ohne Stütze, die eine brauchen. *Kanäle frei halten* sperrt nur noch Raum, aus dem keine Stütze mehr herauskäme.
- Setzen Stützen unter kleinen Überhängen auf dem Modell auf, schlägt Solidon Baumstützen vor. Sie hinterlassen dort weniger Spuren.
- Bei kleinen Spitzen schlägt Solidon ein niedrigeres *Mindesttempo beim Bremsen* vor, damit sie nicht weich werden. Die Einstellung geht an jeden Slicer.
- Schmale Ränder, die sich selbst tragen, bleiben mit *Ränder ohne Stütze* frei. Der Druck braucht so deutlich weniger Stütze.
- Stützen lösen sich leichter und sauberer: Der Abstand folgt Material und Schichthöhe jedes Teils, auch bei mehreren Materialien auf einer Platte. Die Trennschicht folgt der Fläche darüber.
- Steht eine Stütze auf dem Teil, schlägt Solidon auch darunter eine Trennschicht vor, damit ihr Fuß keine Spuren hinterlässt. Unter Baumstützen nur bei Slicern, die sie dort drucken.
- Unter Baumstützen und neben einem Reinigungsturm schlägt Solidon den Stützabstand in ganzen Schichten vor, so wie der Slicer ihn druckt.
- Mit Cura und Gitterstützen schlägt Solidon den Stützabstand vor, der zum Material passt, denn Cura druckt ihn dort genau. Wo Cura aufrundet, nennt das Feld den gedruckten Wert.
- Bei PLA schlägt Solidon für viele feine Spitzen mehr Abstand zu den Baumstützen darunter vor. Dadurch bleiben dort weniger Reste der Baumspitzen.
- Für PETG schlägt Solidon volle Kühlung an der Stütze vor. Sie löst sich so leichter vom Teil.
- Neu in den Druckeinstellungen: *Trennschichten unten*, *Lücke in der Trennschicht* und *Volle Kühlung an der Stütze*.
- Das Feld *Abstand nach oben* heißt jetzt *Abstand oben und unten* und gilt für beide Seiten der Stütze.
- Lehnt der Slicer Filamente mit zu verschiedenen Temperaturen auf einer Platte ab, nennt Solidon jetzt Grund und Ausweg, statt nur zu melden, dass keine Druckdatei entstand.
- Im Druckdialog bleiben Drucker, Filamente und Qualität auch bei vergrößerter Schrift ganz sichtbar. Lange Beschriftungen brechen dafür um.
- Der Prüfbericht rechnet schneller und braucht weniger Arbeitsspeicher.
- Unter Linux mit Flatpak meldet Solidon einen Absturz des Slicers jetzt als Absturz, statt nur zu sagen, dass keine Druckdatei entstand.

### Gewinde, Bohrungen und Normteile

- Gewinde gibt es jetzt in jedem Durchmesser bis 1000 mm, ob mit *Druckbares Gewinde*, in einer Bohrung, mit *Schraube erstellen* oder *Drehdeckel erzeugen*.
- Auch normale Bohrungen lassen sich jetzt bis 1000 mm Durchmesser anlegen und wieder verschließen. Große Bohrungen und Senkungen behalten ihre runde Form.
- Schrauben, Muttern und Scheiben gibt es nach ISO von M1,6 bis M64. Für andere Größen leitet *Eigenes Maß* die Maße aus den Nachbargrößen ab und sagt das.
- Mit *Passend zur Bohrung* baut *Stift für Bohrung* das Gegenstück: in eine Senkung einen bündigen Senkkopf, in ein Innengewinde ein Außengewinde gleicher Größe und Steigung.
- An einem gedruckten Innengewinde bietet die Auswahl *Stift für Bohrung* direkt an.
- Liegt in einer Bohrung ein getrenntes Teil wie ein Stift, sagen die Handlungen an der Bohrung das und bieten *In Einzelteile aufteilen* an. Bisher verschmolz der Stift still mit der Platte.
- Neu ist der *Gewindebolzen*, eine Gewindestange oder Stiftschraube ohne Kopf, mit Fase an beiden Enden und demselben druckbaren Gewinde wie Schraube und Mutter.
- Auch in Bohrungen von Bausteinen wie Schraubenloch, Einpressbuchse und Mutternfalle baut *Stift für Bohrung* den passenden Stift. Liegt die Bohrung nicht im Körper, sagt es das.
- Von Hand auf eine Fläche gesetzt, schneidet die Mutternfalle ihre Tasche ins Material. Bisher stand die Tasche darüber, und nur das Schraubenloch wurde gebohrt.
- Das Schraubenloch der Mutternfalle geht genau durch das Teil, auch durch ein dickes. Bisher endete es 10 mm unter der Tasche oder bohrte jenseits eines Spalts in die Gegenseite.
- Von unten eingelegt liegt die Tasche der Mutternfalle unter der Fläche, ihr Schlitz führt hinab. Bisher saß sie halb darüber, die Schraube in der Fläche.
- Reicht die Bohrung eines Bausteins nicht durch das Teil, heißt sie jetzt Sackloch. Bisher hieß sie Durchgang.
- Ist die Wand dicker als bei *Kabeldurchführung* oder *Schlauchtülle* eingetragen, sagt der Schritt es und öffnet die Wandstärke. Bisher endete der Durchgang still im Material.
- Liegt ein getrenntes Teil in einer Senkung, einem Langloch, einer Pfanne, einer Kehle oder einem Gewinde, sagen die Handlungen das. Bisher wurde es abgeschnitten oder verschmolz.

### Bausteine

- Bausteine, die für sich ein Teil sind, etwa Kabelclip, Rippe oder Mutter, entstehen ohne Auswahl als eigener Körper auf einer freien Stelle der Druckplatte, auch im leeren Projekt.
- Auch eigene Bausteine entstehen so als eigener Körper und hängen nicht an einem Körper, der schon im Projekt liegt.
- Mit *Auswahl als Baustein speichern* kommt der gewählte Körper mit genau den Schritten, die ihn bauen. Käme ein zweiter Körper mit, sagt der Dialog es vor dem Speichern.
- Wandhalter, Rohrschellen, Profilklemmen und Halter nehmen jede Schraube von M3 bis M64. Passt eine Größe nicht zu den übrigen Maßen, sagt der Baustein, was zu ändern ist.

### Bearbeiten und Zeichnen

- Verschieben Sie ein Merkmal, reist sein Material mit, wie es ist, und die alte Stelle wird sauber gefüllt. Wo das nicht geht, sagt es die Auswahl gleich.
- An Wulst und Kehle bietet die Auswahl nur noch an, was die Operation auch ausführt.
- Liegt neben einer Wand eine Verrundung, sagt *Formschräge anstellen* vor der Rechnung, dass sie im Weg ist, und nennt *Merkmal entfernen* als Ausweg.
- Schneiden Sie einen Teil des Körpers weg, verschwinden auch Fasen, Gewinde und Mutterntaschen von Bausteinen, die darin lagen.
- In *Deckel erzeugen* und *Drehdeckel erzeugen* heißt ein leeres Feld für die Höhe der Öffnung „Oberkante“, und 0 ist die Höhe des Betts. Ältere Projekte behalten ihre Öffnung.
- Eine Winkelbedingung in einer kleinen Skizze wirft die Linien nicht mehr um.
- Ein Körper entsteht mit drei Klicks: *Zeichnen* oben in der Werkzeugleiste (Strg+Umschalt+E), dann Ecke, Gegenecke, Höhe. Nach außen fügt er an, nach innen schneidet er.
- Beim Aufziehen lassen sich die Maße tippen. Ein Doppelklick auf den Schritt öffnet seine Maße, und unter *Art* wird daraus ohne neues Zeichnen ein Drehkörper oder ein Lochfeld.
- Aus dem Skizzeneditor führt *Fertig* zurück in die Ansicht, der nächste Klick setzt die Höhe. Escape legt den Umriss beiseite, Strg+Z holt ihn zurück.
- Lässt sich ein neuer Schritt nicht rechnen, bleibt der Entwurf im Bild, und *Reparieren und erneut versuchen* rechnet ihn ohne neuen Klick.
- Zum *Formen* gibt es vier Werkzeuge mit je einem Knopf und Kürzel. Die Stärke ist eine Stufe von 1 bis 10, und mehrfaches Überstreichen derselben Stelle türmt nichts mehr auf.
- Der Pinsel passt zur Größe des Körpers. Ist das Netz für ihn zu grob, gleicht *Formen* die Dreiecke beim ersten Zug selbst an, und ein Strg+Z nimmt beides zurück.
- Beim Spiegeln liegt die Ebene dort, wo der Körper sich selbst gleicht, auch wenn ein Teil weit zur Seite ragt.
- Formen folgt der Maus flüssig, und auch ein Schritt mit hunderten Pinselzügen ist schnell gerechnet.
- Im *Skelett* setzt jeder Klick nach dem ersten einen Knochen, Enter beendet die Kette, Ziehen an einem Gelenk beugt, und *Fertig* legt alles ohne Dialog ab.
- Ein Skelett beugt nur, was an seinen Knochen hängt, der Rest des Körpers bleibt stehen. Ältere Projekte rechnen wie gespeichert.
- Mit Strg oder Umschalt wählen Sie mehrere Kanten und verrunden oder fasen sie in einem Schritt. Ein Klick auf eine Ecke wählt alle Kanten, die dort zusammenlaufen.
- An einem exakten Körper zeigt die Hervorhebung einer Kante auch die tangential anschließenden, die *Verrunden* und *Fase anbringen* mitnehmen.
- Was die Auswahl an einem Merkmal anbietet, führt die Operation mit genau diesen Werten aus. Was grau steht, sagt sie mit demselben Satz, auch über Chat und Kommandozeile.
- Als Stelle der Kopie schlägt *Merkmal verdoppeln* anderthalb Breiten neben dem Original vor, mit einer Wand dazwischen und nie entlang seiner Achse.
- An einer Senkung schlägt *Merkmal drehen* den größten Winkel vor, unter dem sie eine bleibt, und sagt, wenn eine Drehung das Merkmal nur auf sich selbst legt.
- Träfe eine Handlung ein getrenntes Teil neben dem Merkmal oder berührte ein gesetztes Merkmal anderes Material nur auf einer Linie, sagt Solidon das, statt den Körper zu beschädigen.

### Erzeugen mit KI

- Der Erzeugen-Dialog rechnet lokal mit TRELLIS.2 und FLUX.2 [klein] statt mit TripoSG und SDXL. Aus Text entsteht zuerst ein Bild und daraus das Modell.
- Die Einrichtung nennt vor dem Laden Lizenzen und Größen der Modelle. Sie entfernt Solidons alte TripoSG-Einrichtung und sagt vorher, welche Ordner das sind und wie groß.
- Dünne Wände, etwa an einer Vase, kommen geschlossen und mit Dicke an.
- Der Assistent antwortet in der Sprache, in der Sie schreiben.
- Mit lokalem Modell hat der Assistent so viel Raum wie mit einem gehosteten und schafft Aufträge mit bis zu zwölf Schritten.
- Erzeugte Modelle kommen öfter geschlossen an. Wo sich Flächen nur berühren, trennt Solidon sie, und kleine Falten der Oberfläche glättet es, statt eine Selbstkreuzung zu melden.
- Ist ein Versuch schon beim Erzeugen zerfallen, sagt der Dialog es vor dem Übernehmen und bietet *Noch ein Versuch* an.
- Ist ein erzeugtes Modell nur eine dünne Haut um einen Hohlraum, sagt es der Dialog vor dem Übernehmen und der Prüfbericht danach, jeweils mit dem Weg zu einem neuen Versuch.
- Vor dem Herunterladen nennen *Chat einrichten* und *ComfyUI einrichten*, wie viel Grafikspeicher und Platz ein Modell braucht und ob dieser Rechner das hat.
- Auf einem Mac schlägt *Chat einrichten* ein lokales Modell vor, das in den gemeinsamen Speicher passt, und sagt, wann ein Schlüssel für ein gehostetes Modell besser ist.

## 0.5.3

### Bedienung und System

- Rechts steht eine Karte mit den Reitern *Auswahl*, *Prüfbericht* und *Chat*. Neue Warnungen holen den Prüfbericht nicht mehr nach vorn, sein Reiter zeigt sie mit Zeichen und Zahl.
- Oben im Fenster finden Sie jede Funktion über *Funktion suchen* (Strg+Umschalt+P). Die Karte der Funktionen ist geordnet wie die Menüleiste.
- In der Auswahl ist an einem Merkmal eine Handlung zur Zeit offen. Die übrigen nennen zugeklappt ihre Werte.
- Operationsdialoge zeigen vorn höchstens vier Felder und einen Satz. Selten geänderte Werte stehen unter *Weitere Einstellungen*, Grenzen unter *Wann nicht?*.
- Eine Null mit Bedeutung heißt im Feld, was sie bewirkt, etwa „automatisch“, „ohne“ oder „aus dem Material“.
- Alle Dialoge haben dieselbe Form mit flachen Abschnitten und einer gemeinsamen Kante für die Beschriftungen, auch Einstellungen, KI-Dialog und Freischaltung.
- Der Prüfbericht zeigt zuerst die Befunde, darüber eine Zeile mit Status und Zählern. *Exportieren …* steht neben *An den Slicer übergeben …*.
- Befunde, Tourschritte und Hinweise sind kürzer. Wo ein Knopf die Handlung anbietet, wiederholt der Satz sie nicht.
- Die Handlung *Modell nachbauen* steht am gewählten Körper.
- Der Startbildschirm zeigt die vier Einstiege groß oben. *Erste Schritte* fragt Sprache, Slicer und Drucker und klappt den Rest zu.
- Der Bausteinkatalog zeigt je Kachel Bild und Titel. An einer Bohrung zeigt *Passende Bausteine …* nur, was in eine Bohrung gehört.
- Im Dialog *Auswahl als Baustein speichern* steht je Maß eine Zeile mit Vorgabe und Grenzen.
- Unter Windows klickt Solidons eigener Mauszeiger wieder genau an seiner Spitze. Bisher lag der Klick einige Pixel daneben.
- Die Suche im Handbuch bricht nicht mehr mit einem Fehler ab, wenn ein weiteres Zeichen keinen Treffer mehr findet.
- Nehmen Sie einen Schritt zurück oder löschen ihn, während *Diesen Schritt ändern* offen ist, schließt sich der Dialog und sagt es.
- Ein seltenes Einfrieren der Anwendung während der Druckprüfung ist behoben.
- Am Mac nennen Sätze mit Tastenkürzel die Tasten des Mac, also ⌘, ⇧ und ⌥.
- Am Mac löscht die Rücktaste Körper, Merkmale, Verlaufsschritte und Linien in einer Zeichnung.
- Unter Linux nimmt auch das Kürzel, das Tour und Hinweise zum Wiederholen nennen, einen Schritt wieder vor.

### Drucken und Übergabe an den Slicer

- Neu ist Anycubic Slicer Next mit allen 39 Anycubic-Druckern, unter Windows, macOS und Linux.
- Unter Linux findet Solidon OrcaSlicer, Bambu Studio und PrusaSlicer als Flatpak samt Ihren Druckern und Profilen, auch aus Solidons eigenem Flatpak.
- Slicer als AppImage bieten unter Linux auch ihre eingerichteten Herstellerdrucker an.
- Auf dem Mac erzeugt Solidon die Druckdatei jetzt auch mit Cura. Bisher fand es nur Curas Fenster.
- Creality Print 7 bringt seine eigenen Drucker und den zuletzt gewählten mit.
- Die Druckerlisten nennen jeden Drucker einmal, ohne Düsenvarianten. Die Düse wählen Sie im Druckdialog.
- Eine im Druckdialog gewählte Düse bleibt erhalten, wenn Sie danach die Einstellungen speichern.
- Wechseln Sie für PrusaSlicer oder SuperSlicer die Düse, bekommt der Slicer das passende Druckerprofil dazu.
- Solidon bietet mehr Drucker an, auch solche, deren Profil Bett oder Düse nicht nennt, etwa Creality CR-20 und Anycubic i3 Mega in PrusaSlicer.
- Der Druckdialog zeigt vorn Slicer, Drucker, Düse, Filamente, Qualität, Fülldichte und Stützen, der Rest steht unter *Weitere Einstellungen*.
- Jeder Grund eines Vorschlags im Druckdialog passt in eine Zeile. *Druckdatei speichern* erscheint, sobald es eine Druckdatei gibt.
- Teile, die oben breiter sind als am Fuß, bekommen keine Randwarnung mehr, wenn Brim und Skirt auf dem Bett bleiben.
- Übernommene Stützen kommen auch bei feiner Schicht unter Brücken an. Bisher konnte *Kanäle frei halten* sie dort ganz wegnehmen.
- Sind Stützen eingeschaltet und kommt im Slicer keine an, sagt Solidon es nach dem Slicen und nennt den Ausweg.
- OrcaSlicer und ElegooSlicer erzeugen die Druckdatei auch, wenn ein Herstellerprofil Werte enthält, die sie selbst ablehnen. Solidon nennt jeden ersetzten Wert.
- Nennt ein Profil eine Baumstützenspitze schmaler als die Stützbahn, hebt Solidon sie an, damit der Slicer mit Stützen rechnet.
- Übernimmt ein Slicer eine Einstellung anders, nennt der Hinweis das Feld und beide Werte und führt in den Druckdialog.
- Unter Linux bietet Solidon auch PrusaSlicer und OrcaSlicer aus dem Paketverwalter samt ihren Herstellerdruckern an.
- Auf einem Mac, dessen Dateisystem Groß- und Kleinschreibung unterscheidet, findet Solidon die Herstellerdrucker im Programmpaket des Slicers.

### Bohrungen, Langlöcher und Teilen

- Ein Gewinde oder eine Einpressbuchse in einer gewählten Bohrung hält nicht mehr mit „außerhalb der Fläche“ an. Ist die Bohrung zu weit, nennt Solidon passende Größen.
- An einer gewählten Bohrung stehen im Bild nur Durchmesser, Tiefe und zwei Kantenmaße. Bezüge heißen nach ihrer Seite, etwa „Außenkante links“.
- In Zoll nennt der Satz über einer Bohrung ihr Maß in Zoll.
- Das Vorschauband nennt in einer Zeile, was sich ändert, Längen in Ihrer Anzeigeeinheit.

### Formen, Schrift und Zeichnen

- Halter und Platten mit Bohrungen, Senkungen und Schrift baut *Modell nachbauen* jetzt als Umriss mit abgezogenen Taschen nach. Findet es keinen Aufbau, sagt es das.
- Übernehmen Sie beim Zeichnen den Schnitt eines umgewandelten Körpers, kommen seine Kreise und Bögen als Kreise und Bögen an.
- Lässt sich ein Teil nicht in Flächen und Kanten umwandeln, nennt Solidon Grund und Ausweg, statt mit einem unerwarteten Fehler zu enden.

### Erzeugen mit KI

- Der KI-Hinweis sagt je Ziel in zwei Sätzen, was gesendet wird. Weil sich der Text geändert hat, bestätigen Sie ihn einmal neu.
- Die Beschreibungen der empfohlenen lokalen Modelle sind kürzer.

## 0.5.2

### Neue Formen und Bausteine

- Neu ist die Grundform *Rohr anlegen*: Außendurchmesser und Höhe, dazu wahlweise Wandstärke oder Innendurchmesser, in einem Schritt.
- Neu ist der Baustein *Lasche mit Loch*: eine flache Lasche an jeder Fläche, Loch und Maße passend zur Schraube von M3 bis M8.
- Neu ist die *Rohrschelle* für gängige Rohre von 15 bis 40 mm oder jedes eigene Maß bis 110 mm, mit Klemmschraube M3 bis M6 und dem Spiel aus Ihrem Material.
- Neu ist der Assistent *Behälter mit Deckel*: rund oder eckig, mit Schraub-, Steck- oder Klappdeckel, auf Wunsch mit Fächern, Einsatz und Streulöchern. Alle Hauptmaße stehen als Parameter bereit.
- Vier Halter entstehen in einem Schritt mit echten Flächen und Kanten: U-Form, rund, Gabel und Ablage, befestigt mit Schlüsselloch, Schraublöchern, Lochwand-Haken oder Klemme.
- Neu sind *Bajonettverschluss* und *Rastdrehscheibe*, je als passendes Paar, und *Steckhülse und Stangenverbinder* für zwei bis vier Stangen.
- Neu sind die *Schlauchtülle*, deren Durchgang gleich durch die Wand geht, die *Kanalnaht* für Rinnen sowie *Raumboden*, *Raumwand* und *Fensterscheibe* für gesteckte Räume.
- Eine leere Szene zeigt, wie Sie anfangen: Quader, Zylinder, Zeichnen, Bausteine oder eine Datei, die Sie hineinziehen.
- Neue Körper entstehen auf dem Bett statt an einem gewählten Körper und sind danach gewählt. An einer gewählten Fläche setzen sie am Klickpunkt oder mittig an, auf Wunsch gleich mit dem Teil verbunden.
- Bausteine wie Magnettasche oder Schraubenloch sitzen dort, wo Sie auf die Fläche klicken. Ihr Abstand zu zwei Kanten bleibt, wenn sich das Teil später ändert.
- Die *Nutfeder für Aluprofil* passt zu Motedis 20 × 20 B-Typ Nut 6 und 30 × 30 B-Typ Nut 8, ihr Kopf folgt der Form der Nut. Die drei bisherigen Größen bleiben als ältere Maße wählbar.
- Im Prüfbericht baut *Modell nachbauen* ein eingelesenes Teil nach, auch Winkel, Kehlen und Senkungen, vergleicht es in der gewählten Grenze mit dem Original und übernimmt es in einem Schritt.
- Die *Profilklemme mit Einlagen* beginnt mit dem Material des Projekts in beiden Materialfeldern. Bisher waren beide leer.
- Die Bausteinsuche findet die *Nutfeder für Aluprofil* auch unter Nutenstein und T-Nut, und ihre Beschreibung sagt, worin sie sich von einem Nutenstein mit Gewinde unterscheidet.
- Ein Deckel aus *Deckel erzeugen* bekommt auf Wunsch ein Scharnier, mitgedruckt oder mit Stift aus *Stift für Bohrung*, und sein Kragen ist zum Aufklappen gekürzt.
- Mit *Gegenform einlassen* bekommt ein Einsatz Taschen für Werkzeuge, aus denen sie gerade wieder herauskommen.

### Drucken und Übergabe an den Slicer

- Die Vorbereitung des 3MF-Exports lässt sich abbrechen. Bei mehreren Druckplatten nutzt Solidon bereits berechnete Schichten und Vorschläge wieder.
- Beim Öffnen älterer Projekte werden unbenutzte Filamente nicht mehr an den Slicer übergeben. Die Profile der benutzten Filamente bleiben zugeordnet.
- Weitere Modelle finden auch hinter der zwölften Druckplatte einen freien Platz. Mitgebrachte Platten behalten ihre Aufteilung.
- Weitere Modelle kommen bei unterschiedlichen Filamenten auf getrennte Druckplatten, wenn der Drucker nicht genügend Düsen hat.
- Beim Wechsel von Drucker oder Slicer wird die bisherige Druckplattenwahl nicht mehr auf das neue Profil übertragen.
- Schlanke Teile rücken beim Anordnen näher zur Mitte. Der Brim-Abstand lässt sich einstellen; für kleine Standflächen wird ein direkt anschließender Brim vorgeschlagen.
- Beschädigte Profile in PrusaSlicer und SuperSlicer werden gemeldet. Solidon verwendet dann seine vollständigen Druckwerte.
- Druckwerte für einzelne Teile kommen zuverlässiger im Slicer an. Werte, die nur für die ganze Platte gelten, werden am betroffenen Teil erklärt.
- Übernehmen Sie einen Brim nur für ein schlankes Teil, behalten die übrigen Teile Ihre eigene Wahl der Haftung, und das Feld nennt die Teile, für die der Brim gilt.
- Bei Orca und Prusa bremst ein übernommener Vorschlag für eine Passung nur noch die betroffenen Teile.
- Auch kleine übernommene Änderungen der Druckeinstellungen bleiben beim Export erhalten.
- Cura übernimmt die Profilwerte für abrupte Geschwindigkeitsänderungen, auch getrennt für Wände, Füllung und die erste Schicht.
- Ist in Cura ein anderer Drucker aktiv, nennt die Übergabe beide Drucker und zeigt, wo Sie Curas Auswahl übernehmen können.
- Ein Absturz von ElegooSlicer und OrcaSlicer beim Schneiden mehrfarbiger Modelle mit Gitterstützen ist behoben.
- Nach dem Slicen vergleicht Solidon auch Stützmaterial und Modellschichten je Druckplatte. Der Prüfbericht zeigt die interne Schätzung und die Werte aus der Druckdatei.
- Die Material-Gegenprobe vergleicht nur das gedruckte Modell. Spülmaterial wird getrennt gezeigt; unvollständig lesbare Mengen werden kenntlich gemacht.
- Die Gegenprobe der Druckzeit rechnet ab der ersten Schicht mit den Tempi Ihres Druckers, auch mit Stützen, und meldet nicht mehr bei fast jedem Druck eine starke Abweichung.
- Die Schichtanalyse rechnet an Hohlkörpern und Modellen mit vielen Decken mehrfach schneller und erhält feine Konturen. Die Ansicht der Schichten nutzt, was der Prüfbericht schon gerechnet hat.
- Bei ineinandergesteckten Teilen zählt die Druckanalyse eingeschlossene Luft nicht mehr als Material. Das verbessert auch die Erkennung von Überhängen und nötigen Stützen.
- Beim ersten Start und in den Einstellungen wählen Sie zuerst den Slicer und dann einen seiner Drucker. Die Liste hat ein Suchfeld, Bauraum und Düse kommen aus dem Profil des Slicers.
- Klicken Sie beim ersten Start auf *Speichern und starten*, während Solidon noch die Drucker des Slicers sucht, friert die Anwendung nicht mehr ein.
- Die Düse wählen Sie im Druckdialog aus den Größen, die Ihr Drucker kennt, und der Slicer bekommt das passende Profil dazu.
- Der Druckdialog fragt in der Folge, in der eins vom anderen abhängt: Slicer, Drucker, Düse, Platte, Filamente und Qualität, danach die Werte.
- Mit Creality Print 7.2 und 7.3 können Sie die Druckdatei jetzt direkt aus Solidon erzeugen.
- Mit Cura übernimmt Solidon auf Wunsch den Drucker, den Cura gerade nutzt, samt eigener Düse. Ein in Cura umbenannter Drucker wird wiedererkannt.
- Cura rechnet jetzt mit der Düse, die Sie gewählt haben, auch bei Druckern aus Curas eigener Liste, und Drucker mit dem Nullpunkt in der Bettmitte behalten ihn.
- Drucker mit dem Nullpunkt außerhalb der Bettecke, etwa Deltas, BIBO oder Dremel, bekommen die Teile dort, wo Solidon sie hinlegt. Bisher lagen sie am Rand, oder der Slicer ordnete neu an.
- An Bambu Studio gehen Düsenvariante und die Temperaturen Ihrer Spulen mit, bis in die 3MF-Datei.
- Wählen Sie im Druckdialog Brim, Skirt, Raft oder *Automatisch*, stehen dort nur die Maße, die Ihr Slicer dafür bekommt, ohne Felder, die nichts bewirken würden.
- Eine Zahl außerhalb ihrer Grenze bleibt im Feld stehen, die Grenze steht daneben, und *Slicen* wartet, bis sie stimmt. Bisher wurde sie still gekürzt.
- Hohe, schlanke Teile auf kleinem Fuß bekommen ruhigere Wände vorgeschlagen, mit 60 mm/s und weniger Beschleunigung. Solche Stangen rissen sonst am Centauri Carbon 2 ab.
- Mit Cura nennt der Prüfbericht die Teile, die solche Werte nur mitbekommen, weil Cura sie bloß für die ganze Platte annimmt.
- Solidon schlägt *Außenwand zuerst* nur noch für das Teil vor, das es braucht, und nie für eines mit Stützen.
- Auch in der schnellen Suche prüft *Druckoptimal ausrichten*, ob ein Teil sicher steht. Steht eines nirgends sicher, richtet sie die übrigen trotzdem aus und nennt es im Prüfbericht.
- Jedes Teil kommt mit *Auf dem Bett anordnen* auf die erste Platte, auf der es Platz hat. Der Minigolf-Satz braucht so vier statt sechs Platten.
- Ziehen Sie einen Körper im Bild auf ein anderes Bett, liegt er danach auf dessen Platte.
- Kommt ein weiteres Modell hinzu, ob aus einer Datei, einem Download oder erzeugt, zeigt das Bild die Platte, auf der es liegt.
- Ein weiteres Modell kommt an die freie Stelle, die der Plattenmitte am nächsten liegt, statt hinten links in die Ecke.
- Nach dem ersten *Im Slicer öffnen* rechnet Solidon den Verlauf nicht mehr neu.
- Die Gegenprobe mit SuperSlicer meldet keinen übergangenen Startcode mehr, wo keiner übergangen wurde.
- SuperSlicer stürzt bei runden Teilen nicht mehr ab: Die Schrägnaht, die er nicht kennt, bekommt er nicht mehr.
- SuperSlicer erhält Gitterstützen mit Hinweis, wenn Baumstützen gewählt waren. Die Nahtwahl „Nächstgelegen“ kommt ohne falsche Warnung an.
- TPU findet in PrusaSlicer und SuperSlicer das passende Filamentprofil samt Startwerten. Fehlt ein Profil, nennt Solidon die eigene Materialtabelle als Grundlage.
- Cura beachtet die Beschleunigungsgrenzen und meldet begrenzte eigene Werte. Volle Füllschichten drucken mit dem Fülltempo; nur die Oberseite erhält das Oberflächentempo.
- Cura nimmt die kleinste Lüfterleistung und die Schichtzeitschwelle aus dem Profil Ihres Druckers. Bisher lief der Lüfter schon in der ersten Schicht an, wo er ruhen sollte.
- Kammertemperaturen kommen im richtigen Slicerfeld an. Druckerprofile ohne regelbare Kammerheizung erklären jetzt, warum der Wert nicht wirkt.
- Das Füllmuster „Linien“ kommt in Bambu Studio und Creality Print als Linien an und wird nicht mehr durch Gitter oder Würfel ersetzt.
- Solidon meldet nach dem Schneiden auch Einstellungen, die PrusaSlicer oder die Orca-Slicer verworfen haben. Abweichende Rand-, Wand- und Stützarten werden ebenfalls erkannt.
- Die Filament-Vorwahl nimmt Generic oder die Marke Ihres Druckers statt eines fremden Sonderfilaments, etwa am Bambu A1 Generic PETG statt BETA PETG.
- Auch an STEP-Flächenmodellen, bei Drehungen um fast 180° und an teilweise erkannten Flächen gelingen *Druckoptimal ausrichten*, *Drehen* und *Verschieben*. Der Körper bleibt exakt.
- Eine langsamere Außenwand gilt in PrusaSlicer und der Orca-Familie auch für kleine Umfänge wie Bohrungen und Stiele.
- Die eingestellte Stützdichte wird in PrusaSlicer und der Orca-Familie korrekt übernommen. Das Feld beginnt bei 1 %. Für einen Druck ohne Stützen wählen Sie „Keine“.
- Bei Mehrfarbdrucken mit OrcaSlicer, ElegooSlicer, Bambu Studio und Creality Print erhält der Reinigungsturm eine zur Bettgröße passende Startposition.
- Zu große Teile meldet Solidon vor dem Slicerstart. Findet es für mehrere Teile keinen Platz auf einer Platte, können Sie sie auf mehrere Platten anordnen lassen.
- Sonderzeichen im Projekt- oder Benutzernamen verhindern die Druckdatei nicht mehr. Cura findet auch Modelle mit türkischen oder chinesischen Namen.
- Solidon ordnet überlappende Teile vor dem Schneiden mit PrusaSlicer oder Cura auf dem Druckbett an und meldet, wenn es keine passende Anordnung findet.
- Meldet PrusaSlicer oder SuperSlicer eine leere erste Schicht, nennt Solidon das Teil und bietet Aufsetzen aufs Bett sowie passende Druckeinstellungen an.
- Warnungen von PrusaSlicer und SuperSlicer stehen auch nach gelungenem Slicen im Prüfbericht, eine leere Schicht als Fehler. Der Abstand zum Raft ist eigens einstellbar.
- Teilt der Slicer eine Platte auf mehrere Druckdateien auf, meldet Solidon das und bietet Anordnen oder den Export an. Bisher übernahm es still nur eine der Dateien.
- Oben im Prüfbericht steht, ob die Übergabe bereit ist, eine Entscheidung braucht oder nicht empfohlen wird, und was ungeprüft ist. Ohne Befunde gilt ein Teil nicht mehr von selbst als druckbereit.
- Ein gewählter Befund nennt seine Folge für den Druck, und jede angebotene Handlung sagt, was sie außerdem verändert.
- Nach Export oder *Im Slicer öffnen …* liest Solidon die Datei noch einmal ein. Der Beleg im Prüfbericht nennt Dateien, Druckziel, Material, Druckwerte und ob die Datei dem Auftrag entspricht.
- Auf der Kommandozeile als 3MF exportiert, behält ein einfarbiger Körper beim erneuten Öffnen sein Filament.
- Die Kommandozeile nennt bei Druckwerten für einzelne Teile, welche Teile es sind und welchen Wert sie bekommen.
- Übernehmen Sie Stützen für eine lange Brücke über dem Teil selbst, kommen sie jetzt auch dort an. Bisher kam „Nur vom Bett“ dazu, und mehrere Slicer druckten die Brücke ohne Stütze.
- Kleine liegende Teile wie Schrauben bekommen keine Stützen mehr vorgeschlagen, wo eine Schnittkante fälschlich eine schwebende Stelle ergab.
- Läuft ein Teil oben in eine Kante aus, die der Slicer nicht druckt, meldet Solidon nach dem Slicen kein abgeschnittenes Modell mehr.
- Ist die erste Schicht eines Teils schmaler als eine Bahn, nennt die Meldung nach dem Slicen die Wandbahnen und den Raft als Ausweg.
- SuperSlicer behält die Anordnung aus Solidon und schiebt die Teile nicht mehr bis an den Bettrand; der Skirt bleibt auf dem Bett.
- Passt ein Teil nur schräg gestellt auf das Druckbett, geht es gedreht an OrcaSlicer, Bambu Studio und ElegooSlicer; reicht Creality Print der Rand dafür nicht, sagt Solidon das vorher.
- Einen Brim schlägt Solidon nur so breit vor, wie das Bett Platz lässt.
- Reicht der Rand um ein Teil in eine Sperrfläche des Druckbetts, sagt das die Prüfung vor dem Export.
- Kreuzen sich im Slicer die Bahnen zweier Teile oder eines Teils und des Reinigungsturms, sagt die Meldung das und bietet Auswege an.
- Steht der Brim auf automatisch, warnt Solidon vor dem Export, wenn er über das Bett oder in eine Sperrfläche wachsen kann, und bietet eine feste Brimbreite an.
- Stützen und Skirt am Bettrand zählen in der Prüfung vor dem Export mit der Verbreiterung der ersten Stützschicht, die das Slicerprofil nennt.
- Aus STEP-Teilen exportierte STL-Dateien enthalten keine Dreiecke ohne Fläche.

### Bohrungen, Langlöcher und Teilen

- Der Winkel eines Langlochs an einer eingelesenen Bohrung zeigt in die erwartete Richtung und bleibt so, wenn Sie die Feinheit ändern.
- Ein Langloch in einer Seitenwand, die nach links oder rechts zeigt, lässt sich kürzen, schmaler ziehen und drehen. Ältere Projekte behalten ihre Langlöcher, bis Sie den Schritt ändern.
- An STEP-Körpern gilt ein Langloch in einer schrägen Fläche nicht mehr als seitlich überstehend, und ein zweiter Zug an einem Langloch, das in eine Stufe läuft, füllt den Körper nicht mehr auf.
- Ein Langloch durch eine schräge oder gefaste Platte zeigt an STEP-Körpern seine ganze Tiefe, und seine Kopie über den Rand hinaus meldet an STL- und STEP-Teilen dasselbe.
- An einem Körper mit echten Flächen und Kanten sitzt ein Baustein nach einer Bohrung auf der gewählten Fläche, und *Drehdeckel erzeugen* gelingt auch am Rand einer ausgehöhlten Dose.
- Zwei Platten, die sich berühren, bleiben an einer Bohrung ein Körper und behalten ihr Material, ob Sie sie ziehen, ändern, versetzen oder schließen. Ein Stift darüber bleibt stehen.
- Ein Zug an einer Bohrung, durch die zwei Körper gehen, meldet keinen Zerfall mehr, wo keiner entsteht.
- Schneidet eine Bohrung den Körper durch, sagt der Prüfbericht es einmal, mit der Teilezahl am Ende, und schweigt, sobald der Körper wieder ein Stück ist.
- Muster auf Zylinderflächen eingelesener Modelle bleiben beim Ändern geschlossen.
- Im Verlauf eines STEP-Körpers lassen sich Schritte umstellen oder davor einfügen, auch wenn ein späterer Schritt eine Bohrung meint. Der Verweis folgt der Bohrung.
- Eine einfache Bohrung oder ein Langloch, mit neuer Richtung versetzt oder verdoppelt, bleibt an einem STEP-Körper exakt.
- Ein erkanntes Merkmal mehr als einen Meter vom Nullpunkt entfernt behält beim Ändern seinen Ort. Bisher kürzte das Feld die Zahl still, und die Bohrung wanderte.
- Trifft ein Schritt ein Teil, dessen Oberfläche sich selbst kreuzt, hält er an und zeigt die Stelle. Daneben rechnet er weiter und warnt, dass sich die Teile nicht vereinigen ließen.
- Eine Figur schneidet *Modell teilen* auch an ihrer Spiegelnaht geschlossen, und die Stifte sitzen schon in der Vorschau.
- Streift ein Schnitt eine Wand nur, nennt *Modell teilen* die Stelle und führt zur Lage des Schnitts, statt an den Stiften zu scheitern.
- Abschneiden schneidet jetzt auch schräg: Vorn wählen Sie die *Ebene* — an einer Achse mit Neigung, parallel zu einer Fläche, durch eine Kante oder durch drei Punkte, die Sie im Bild anklicken.
- Ein STEP-Körper bleibt beim Abschneiden ein STEP-Körper, mit seinen Flächen, Kanten und Namen.
- Ein frisch erzeugter Drehdeckel gilt im Prüfbericht nicht mehr als zu eng für seinen Hals.
- Lässt sich eine Bohrung an einem STEP-Körper nicht sauber schneiden, bohrt Solidon sie am Dreiecksmodell, statt einen kaputten Körper weiterzugeben.
- Haben Sie beim Laden „Sofort laden“ gewählt, erkennen auch die Stücke von *Modell teilen* nicht minutenlang nach; „Alle Merkmale erkennen“ holt es nach.
- Wählen Sie *Modell teilen* in einer Sammelzeile des Prüfberichts für mehrere Körper, teilt Solidon sie nacheinander. Bisher wurde nur der erste geteilt.
- Deckt beim *Vereinigen* ein Körper eine Bohrung ganz oder teilweise zu, steht das mit Ort und verbliebenem Hohlraum im Prüfbericht.
- Kreismuster und *Spiegeln* nehmen ihre *Drehmitte* von einem Körper, einem Merkmal, einem Punkt oder dem Ursprung. Die Mitte bleibt fest, auch wenn sich der Körper später bewegt.
- Ein Zug in der Öffnung einer gewählten Senkbohrung lässt den Körper stehen, und die Statuszeile nennt den Weg zum Langloch. Bisher verschob er den ganzen Körper.
- Wird die Maßkarte einer Bohrung hoch, bleiben die übrigen Maße neben dem Körper, und der Griff zum Verschieben sitzt an der Mündung statt mitten im Teil.
- Wählen Sie eine Bohrung, die Sie in Solidon gesetzt haben, steht ihr Durchmesser nur noch in der Maßkarte im Bild. Bisher stand er rechts ein zweites Mal.
- Eine Richtung, die Sie rechts für ein Langloch eintragen, übernimmt auch die Maßkarte im Bild, und *Übernehmen* bleibt frei. Bisher fiel sie dort auf 0° zurück.
- Kegel, auch flache und kurze, Rundungen und schmale Flächen erkennt Solidon an mehr Modellen gleich, ob das Modell verschoben, gedreht oder skaliert ist.
- Eine gewölbte Oberseite heißt auch an STEP-Körpern *Gerundete Seite* statt *Verrundung*, und rundum verrundete STL-Teile zeigen ihre Rundungen einzeln wie dasselbe Teil aus STEP.
- An Buchstaben und geschwungenen Umrissen eingelesener Modelle erscheinen keine falschen Verrundungen mehr.
- Rippen-, Waben- und Noppenfelder einer eingelesenen Datei erkennt Solidon je als ein Muster, und *Merkmale an dieser Stelle erkennen* fasst die Zellen eines Felds zusammen.
- Ein kleines Feld, das Solidon nur als einzelne Merkmale liest, fassen Sie mit *Als Muster zusammenfassen* zu einem Muster zusammen. Muster in STEP-Dateien erkennt Solidon direkt.
- Auch in Projekten aus älteren Versionen zählen die Stücke einer automatischen Teilung durch, und ein gelöschter oder ausgeschalteter Schnitt zählt nicht mehr mit.
- Eine Bohrung, die Sie längs einer schrägen Fläche verdoppeln, versetzen oder vervielfachen, bleibt an STL- und STEP-Teilen dieselbe Bohrung mit denselben Maßen und Meldungen.
- Nach *Merkmal vervielfachen* bohrt eine Kopie an STEP-Teilen nicht mehr bis an die Oberseite durch, und eine grob facettierte STL-Bohrung gilt weiter als durchgehend.
- Ein Gewinde wird mit *Merkmal ändern* größer oder kleiner, ohne durch die Wand zu brechen, und das Gegengewinde einer Gewindepassung ändert sich mit.
- Ein gedrucktes Gewindepaar besteht seine Passungsprüfung: Beide Gewinde nennen ihr gebautes Maß, und die Prüfung erwartet das Spiel beider Hälften.
- Beim *Fügeweg prüfen* drehen Teile auch, oder sie werden erst eingesetzt und dann gedreht wie ein Bajonett.
- Ein Stück aus *Prüfstück erzeugen* schneidet dasselbe Fenster aus beiden Teilen einer Passung und nennt das Spiel.
- Eine Senkbohrung, die nach dem Verdoppeln, Versetzen oder Vervielfachen ganz im Material endet, meldet nicht mehr, sie rage über die Kante.
- Reicht die Senkung einer Kopie über eine Seite hinaus, findet Solidon die Kopie an STL- und STEP-Teilen gleich wieder.
- Verdoppeln Sie eine Bohrung entlang ihrer eigenen Achse ins Leere, behält das Original an STL-Teilen seinen Namen, und die Kopie heißt verloren wie an STEP-Teilen.
- Eine Kehle oder ein Wulst, den ein Durchbruch in zwei Bögen teilt, steht an STEP-Teilen als ein Ring im Baum, wie an STL- und 3MF-Teilen.
- Gleiche Merkmale an STEP-Teilen, etwa zwei Stücke einer Kegelfläche, behalten ihre Namen, wenn Sie anderswo bohren, verdoppeln, eine Bohrung ändern oder einen Baustein einsetzen.
- Zusammengehörige Merkmale stehen im Objektbaum als Gruppe, und Kammern und Verschlüsse ändern sich als Ganzes: Innenmaß, Tiefe, Spiel und Drehweg.

### Verrunden und Fasen

- Verrunden einer Kantengruppe an einem STEP-Körper rundet jetzt die Kanten, die gehen, statt ganz abzusagen. Jede ausgelassene Kante findet *Stelle zeigen*.
- Kanten an einer Wand, die nicht dicker ist als der Radius, bleiben scharf, und der Prüfbericht nennt den Radius, der dort passt. Bisher sagte die ganze Rundung ab.
- Hat ein STEP-Körper an einer gewählten Stelle keine eigene Kante, bietet der Prüfbericht *Flächenbearbeitung beenden und erneut versuchen* an. Am Dreiecksmodell wird sie mitgerundet.
- Fehlt Platz für den Austausch mit dem Rechenprozess, rechnet Solidon den Schritt trotzdem und sagt es im Prüfbericht. Bisher brach er mit dem Rat ab, gröber zu rechnen.

### Formen, Schrift und Zeichnen

- Mit *Auf beiden Seiten* setzt *Text aufbringen* die Schrift auch auf die Rückseite, von außen lesbar. Das passt für Fahnen, Schilder und Anhänger.
- Schriftzüge werden genauer gesetzt: Die Buchstaben stehen an ihrer Stelle, und runde Bögen folgen der Schrift, statt bei kleinen Größen bis zu 2 Prozent Fläche zu verlieren.
- Die Symmetrie beim *Formen* spiegelt an der Mitte des Körpers, auch abseits der Bettmitte. Ältere Projekte behalten ihre Form.
- Der Formpinsel wirkt nur auf die Seite, die ihm zugewandt ist. Abtragen an einer dünnen Platte drückt die Unterseite nicht mehr mit.
- Ein Formzug auf der Spiegelebene wirkt einmal statt doppelt, und knapp daneben gehen Zug und Spiegelbild glatt ineinander über.
- Der Skeletteditor zeigt Knochen und Gelenk im Bild, und ein Gelenk sitzt in der Mitte des Körpers statt auf seiner Haut, sodass die Figur gleichmäßig beugt.
- In den übersetzten Fassungen heißt die Stärke des Formpinsels nicht mehr wie eine Wanddicke.
- Sticht ein Formzug durch die Wand oder macht er sie zu dünn, steht das im Prüfbericht und vor dem Export, mit *Stelle zeigen* und *Zug zurücknehmen*.
- Im Fenster rechnet *Weich verschmelzen* jetzt fein, solange der Körper nicht sehr groß ist.
- Reicht ein Baustein wie ein Schlüsselloch über den Rand seiner Fläche, auch nur mit Senkung oder Fase, oder in eine Wand dahinter, steht das im Prüfbericht.
- Ein getipptes Maß wie Länge 40 streckt eine Zeichnung nur in dieser Richtung. Der Körper daraus bleibt geschlossen und liegt auf dem Bett.
- SVG-Zeichnungen kommen richtig an: Drehungen, Scherungen, abgerundete Ecken, Ellipsen und elliptische Bögen stimmen, und ausgeblendete Ebenen bleiben draußen.
- Das Ziel von *An Merkmal ausrichten* ist anfangs leer, und der erste Klick ins Bild füllt es. *Übernehmen* wartet bis dahin, statt den Körper still an die falsche Seite zu setzen.
- Eine Datei in Metern, die auch in Zoll aufs Bett passen würde, liest Solidon nicht mehr still falsch, sondern fragt nach der Einheit.
- Ein weiterer Zug in eine eben gegrabene Mulde gräbt tiefer, auch mit einem kleinen Pinsel. Bisher blieb er wirkungslos und galt als verfehlt.
- Beim *Formen* zeigt das Fenster jeden Zug gleich schnell, auch nach vielen Zügen, und große Sitzungen rechnen ihre Vorschau im Hintergrund. Bisher wurde es mit jedem Zug langsamer.
- Mit *Stand festschreiben* legt Solidon eine Formsitzung so fein ab, wie Export und Druck sie rechnen, und das Fenster bleibt bedienbar. Bisher wurde die gröbere Ansicht abgelegt.
- Ein Doppelklick auf *Formen* im Verlauf öffnet die Sitzung mit ihren Zügen wieder. Strg+Z nimmt einen ganzen Zug zurück, und *Fertig* ändert denselben Schritt.
- Der Eintrag *Aus Skizze erzeugen …* beginnt sofort zu zeichnen, die Zeichenebene zeigt ihren Nullpunkt, und ein Doppelklick im Verlauf öffnet eine Zeichnung wieder im Zeichenmodus.
- Beim *Formen* und im Skeletteditor zeigt die Leiste Wandstärke oder Überhang als Karte mit Legende und meldet einen Zug über den Bauraum. Nach dem Beugen sagt sie, wie es sich druckt.
- Eine aufgebrachte Textur wählen Sie als Ganzes. Im Auswahlfenster stehen dann *Textur ändern* und *Textur entfernen*.
- Schrift folgt einem Bogen oder läuft um eine Rundung, und *Schrift einlegen* setzt sie bündig in eigener Farbe ein.

### Erzeugen mit KI

- Abbrechen während *Noch ein Versuch* bricht nur den laufenden Versuch ab. Die fertigen bleiben zur Wahl.
- Jeder Versuch in der Liste nennt seinen Satz oder sein Bild und den Startwert. Passt Ihre Eingabe nicht mehr zum gewählten Versuch, sagt der Dialog, welcher übernommen wird.
- Das Bildmodell holt *Bildmodell einrichten …* auch, wenn die übrigen Gewichte schon da sind.
- Nennt ein Fehler beim Erzeugen die Einrichtung als Ausweg, steht sie als Knopf im Dialog.
- Während ein Modell erzeugt wird, bleibt das Fenster bedienbar. Der Dialog tritt zur Seite, und die Statusleiste zeigt Fortschritt, Zeit und *Abbrechen*.
- Der Erzeugen-Dialog nennt das Volumen in der Größe, in der das Teil ankommt.
- Ein erzeugtes Modell nimmt ein einziges Strg+Z wieder zurück. Bisher brauchte es dafür drei bis vier.
- Sagt *Übernehmen* beim Erzeugen ab, bleibt der Dialog mit allen Versuchen offen und nennt den Weg, statt das Netz zu verwerfen.

### Bedienung und System

- Auf dem Mac beendet sich Solidon nicht mehr kurz nach dem Start. In Version 0.5.1 geschah das auf jedem Mac, auch ohne angeschlossene 3D-Maus.
- Der Haken *Maße als Parameter anlegen* steht beim ersten Mal an und merkt sich danach Ihre letzte Wahl, auch über einen Neustart.
- Dialoge öffnen in der Größe ihres Inhalts, ohne Leerraum, und eine Größe, die Sie selbst gezogen haben, bleibt.
- Export, *Slicen* und *Im Slicer öffnen* bekommen immer die feine Rechnung, nicht die gröbere Ansicht des Fensters. Rundungen und Kegel kommen so mit voller Auflösung in die Datei.
- Ein Export während einer laufenden Berechnung wartet auf das neue Ergebnis. Bisher konnte die Datei noch das alte Maß tragen.
- Exportieren Sie nur einen Teil der Szene, nennen Dateidialog und Bestätigung den Umfang, etwa „1 von 2 Körpern“.
- Ein Maß jenseits seiner Grenze lehnt die Parameterleiste ab, statt das Bild leer stehen zu lassen.
- In der Parameterleiste zählt jeder Pfeilschritt, und der Fokus bleibt im Feld.
- In der Parameterleiste tragen die Maße zweier Quader ihre Nummer, und ein Maß mit eigenem Arbeitsbereich hat einen Regler.
- Wartet ein Schritt auf eine Rückfrage, bleibt *Übernehmen* frei, und die Frage kommt.
- Im Dialog einer Operation stehen die Beschriftungen in einer Spalte, die Felder gleich breit, und jeder Schalter vor dem, was er schaltet.
- Haken in Listen sind in jeder Zeile lesbar, und Farben stehen als runder Punkt daneben.
- Die Befehlspalette erklärt Werkzeuge und Dateiaktionen in einem Satz.
- Nach einem Wechsel des Parameters beginnt *Varianten erzeugen* bei dessen Wert.
- Scheitert das Speichern einer Kalibrierung, bleiben die bisherigen Werte erhalten.
- Im Beispielprojekt zum zweiten Weg folgen die Schraubenlöcher Breite und Stärke.
- Das Fenster *Neuerungen* und die Website zeigen Hervorhebungen als Schrift statt als Sternchen.
- In allen Übersetzungen heißen Merkmale, Knöpfe und Druckbegriffe überall gleich, und Meldungen setzen Satzzeichen, wie die jeweilige Sprache es verlangt.
- Der Knopf, der den Verbrauch vom Filamentlager abbucht, heißt in den Übersetzungen jetzt wie eine Buchung, und Hinweise nennen Handlungen wie das Fenster, etwa *Dreiecke angleichen*.
- Die Anrede ist einheitlich: Spanisch, Portugiesisch und Französisch siezen, Italienisch duzt. Drei spanische und portugiesische Meldungen, die das Gegenteil sagten, sind berichtigt.
- Während ein Dialog seine Vorschau zeigt, kommen Leerzeichen in jedem Textfeld an, auch im Rückmeldebogen und im Chat, und Haken und Knöpfe nehmen die Leertaste an.
- Beim *Skalieren* bleibt ein Körper auf dem Bett stehen, statt unter die Platte zu sinken, und die Ansicht rahmt ihn nach, wenn er größer wird.
- Einige Befunde, die einen Schritt meinen, öffnen ihn zum Ändern, etwa *Größe ändern* nach *Auf Maß bringen*.
- Eine Sammelzeile im Prüfbericht wie *Auf den Bauraum verkleinern* ist über alle Körper ein einziger Rückgängig-Schritt.
- Die Hilfe zu einer Operation springt im Handbuch direkt zu ihrem Eintrag, und die Referenz nennt Felder und Auswahlen so, wie sie im Dialog heißen.
- Lasten andere Programme den Rechner aus, bricht *Abbrechen* eine lange Rechnung in unter einer Sekunde ab, statt nach Sekunden einen Neustart zu verlangen.
- Ein lokales Sprachmodell darf im Chat zwölf statt acht Schritte je Auftrag gehen und löst so mehr Aufträge, die aus mehreren Teilen bestehen.
- Das Auswahlfenster passt wieder in seine Spalte, und die Maßspalte im Objektbaum zeigt das Maß ganz, etwa „Ø5,19 mm“ statt „…“.
- An einer Bohrung öffnet *Merkmal ändern* direkt *Bohrung ändern* mit Vorschau, statt nur auf diesen Weg zu verweisen.
- Klicken Sie während einer laufenden Vorschau auf *Übernehmen*, rechnet Solidon die Änderung nur noch einmal. Bisher rechnete es sie danach ein zweites Mal.
- Die Differenzansicht schraffiert Hinzugekommenes und Entferntes in zwei Richtungen, sodass sich beides auch ohne Farbe unterscheiden lässt.
- Fragt Solidon beim Öffnen nach der Einheit einer Datei, stehen die Maße in Ihrer Anzeigeeinheit und mit dem Dezimalzeichen Ihrer Sprache.
- Ziehen Sie eine Datei herein, die Solidon nicht öffnet, etwa aus Blender, nennt es den Weg über 3MF, STEP oder STL. G-Code geht an *G-Code gegenprüfen*.
- Mehrere Dateien öffnen Sie in einem Schritt. Sie behalten ihre Lage zueinander, ein Strg+Z nimmt alle zurück, und gleiche Importhinweise stehen gebündelt im Prüfbericht.
- Über dem Verlauf zeigt *Vorher/Nachher* mit einem Regler jeden früheren Stand. *Hier weiterarbeiten* fügt dort neue Schritte ein, und Ihre Schrittnamen bleiben.
- Mit *nach* setzt *Verschieben* die Mitte, die Bodenmitte, eine Ecke oder ein Merkmal auf eine feste Lage und *Drehen* den Körper in feste Winkel, auch bei mehreren Körpern.
- Kopieren Sie den Link einer Modellseite, steht er in *Modell aus dem Netz* schon im Feld, und Solidon zeigt den Weg über den Browser.
- Kann ein Dialog nicht übernehmen, steht der Grund auch unter seinen Feldern und nicht nur im Band über dem Bild.
- Nach Strg+Y nennt die Statuszeile den Schritt, der wieder angewendet wurde, wie nach Strg+Z.
- Vorschaubilder von Beispielen und Bausteinen zeigen die Höhe nach oben. Bisher wiesen hohe Teile darin nach unten.
- Mitgelieferte Beispiele öffnen mit Ihrem Drucker und Material. Bisher rechneten sie mit dem allgemeinen Drucker.
- Kann Solidon die Wahl *Werte mitgeben* nicht speichern, steht der Hinweis direkt am Schalter.
- Lasten andere Programme den Rechner unter Windows voll aus, bleibt eine Rechnung an einem großen Modell nicht mehr minutenlang stehen.
- Längen in Meldungen stehen mit dem Dezimalzeichen Ihrer Sprache.
- Nach dem Laden eines großen Modells bleibt die Ladeanzeige stehen, bis die Ansicht das Modell zeigt.
- Ein Klick auf eine Zeile im Prüfbericht wählt ihre Körper auch dann, wenn sich die Liste dabei verschiebt.
- Feste Zahlen lassen sich mit einem Klick an ein Projektmaß binden, und der Plattenwähler nennt die Körper je Platte und zeigt die gewählte ganz.

## 0.5.1

### Drucken und Übergabe an den Slicer

- In PrusaSlicer, ElegooSlicer, Bambu Studio, Creality Print und OrcaSlicer gilt das Profil des Herstellers. Solidon schreibt nur, was Sie ändern oder an Vorschlägen übernehmen.
- Die Stufe *Standard* druckt mit Tempo und Beschleunigung aus dem Herstellerprofil, statt jeden Drucker auf 40 mm/s zu bremsen. Am Centauri Carbon 2 sind große Teile so 40 bis 50 Prozent früher fertig.
- Übernommene Vorschläge gelten nur dem Teil, das sie braucht: Stützen, Brim und die Werte einer Passung, in jedem unterstützten Slicer. Der Druckdialog nennt die Teile.
- Druckt ein Teil stehend ohne Stützen, lässt *Druckoptimal ausrichten* es stehen, statt es auf Stützen zu legen. Ein Minigolf-Satz aus 16 Teilen passt so auf eine Platte statt auf vier.
- Passt ein Teil in keiner Lage aufs Bett, sagt der Druckdialog schon vor dem Slicen, um wie viel es zu groß ist, und bietet *Modell teilen* und *Auf den Bauraum verkleinern* an.
- Auch wo sich Teile eines Modells nur berühren, gelingt *Modell teilen*, und die Verbinder sitzen an jeder Naht richtig herum in ihren Löchern. Vorher meldete der Bericht dort Kollisionen.
- Den Überhangwinkel nimmt Solidon aus dem Herstellerprofil Ihres Druckers, bei Elegoo, Bambu und Creality 60 statt 45 Grad. Fasen und flache Schrägen bekommen keine unnötigen Stützen mehr.
- An runden Außenwänden schlägt Solidon eine *Schrägnaht* vor, in jedem unterstützten Slicer. Der Druck dauert dadurch 2 bis 4 Prozent länger.
- Rechnet Ihr Slicer den Brim selbst, wie ElegooSlicer, Bambu Studio, Creality Print und OrcaSlicer, schlägt Solidon keinen eigenen vor. Der des Slicers gibt hohen Teilen mehr Rand.
- Die Stufen *Fein*, *Entwurf* und *Belastbar* wählen jetzt den passenden Prozess Ihres Slicers, etwa „0.12mm Fine“ bei *Fein*.
- Der Druckdialog zeigt, was gedruckt wird: Grundlage ist das Herstellerprofil, Ihre eigenen Werte sind markiert und lassen sich einzeln zurücksetzen.
- Die Druckplatte wählen Sie im Druckdialog, und die Betttemperatur folgt ihr. Gibt der Hersteller die Platte für Ihr Filament nicht frei, sagt Solidon es vor dem Druck.
- Ohne *Vorschläge übernehmen* bekommt kein Teil mehr ungefragt einen Brim, weder beim Export noch bei der Übergabe an den Slicer.
- Neu ist der Vorschlag *Kanäle frei halten*: Übernommen sperrt die Übergabe die Stützen in den Kanälen, in jedem unterstützten Slicer. Das Cura-Fenster bekommt die Sperre und die Werte je Teil mit.
- Eine Decke über einem Wasserkanal oder Tunnel holt keine Stützen mehr aufs Modell. Braucht sonst keine Stelle Stützen auf dem Modell, schlägt Solidon sie nur vom Bett vor.
- Der Druckdialog zeigt seine Vorschläge schneller, am Bohrmaschinenhalter nach 4,3 statt 7,6 Sekunden.
- Projekte aus 0.5.0 drucken mit dem Tempo Ihres Druckers. Was Sie darin selbst eingestellt hatten, bleibt erhalten.
- Das Tempo der ersten Schicht gilt jetzt auch für ihre Füllung. Vorher legte der Slicer den Boden mit dem Tempo des Herstellers, am Centauri Carbon 2 mit 105 mm/s.
- Mit PrusaSlicer beginnt der Druck jetzt wie bei Prusa selbst, mit Bettvermessung, Spüllinie und Druckerprüfung.
- PETG geht an PrusaSlicer jetzt als PETG hinaus, nicht mehr als PLA.
- In OrcaSlicer bekommt jeder Drucker seine eigene Maschine und deren Standardprozess vorgewählt, der Sovol SV06 nicht mehr die High-Speed-Ausführung, der Ender-3 V3 nicht mehr „0.12mm Fine“.
- Neu sind der Creality Ender-3 V3 SE und der V3 KE. Bisher bekam ein SE die Werte des viel schnelleren Ender-3 V3.
- Gleiche Kopien rechnet *Druckoptimal ausrichten* nur einmal und ist am selben Minigolf-Satz in weniger als einem Drittel der Zeit fertig.
- Die Qualitätsstufen im Druckdialog stehen jetzt in der Sprache der Oberfläche.
- Auch das Tempo der Leerfahrten kommt vom Drucker: Der Centauri Carbon 2 fährt sie mit 500 statt 150 mm/s, wie in Elegoos eigenem Profil.
- Haben Sie den Überhang Ihres Druckers gemessen, stützt auch der Slicer erst ab diesem Winkel, solange Schichthöhe und Bahnbreite der Messung gelten.
- Auch der Prüfbericht rechnet Überhänge jetzt mit dem Winkel, ab dem Ihr Slicerprofil stützt.
- Reicht ein Brim, Skirt oder Raft über das Bett hinaus, sagt Solidon es bei der Übergabe an den Slicer und bietet *Auf dem Bett anordnen* an.
- Lehnt der Slicer ein zu hohes Teil ab, nennt Solidon beide Höhen und bietet *Modell teilen*, *Auf den Bauraum verkleinern* und einen anderen Drucker an.
- Lehnt der Slicer ein Teil ab, das nicht auf seine Platte passt, nennt Solidon den Grund und bietet *Modell teilen*, *Auf den Bauraum verkleinern* und *Auf dem Bett anordnen* an.
- Bleibt Bambu Studio nach dem Slicen hängen, übernimmt Solidon die fertige Druckdatei, statt nach fünf Minuten abzusagen.
- Mit Cura lassen sich auch große Modelle slicen. Vorher endete der Lauf dort ohne Druckdatei, etwa am Eiffelturm mit 313 000 Dreiecken.
- Kann Creality Print eine 3MF nur in seinem Fenster rechnen, sagt Solidon das und führt zu *Im Slicer öffnen …*.
- Hat die erste Schicht schmale Stege, auch wenige lange an einem großen Teil, schlägt Solidon vor, sie mit 50 mm/s zu legen. Die kurzen Bahnen haften so besser.
- Eine längere *Mindestzeit je Schicht* schlägt Solidon nur noch vor, wo Ihr Profil keine trägt. Vorher kam der Vorschlag an fast jedem Teil mit Fase oder Spitze.
- Wo Ihr Slicer das Tempo selbst nach dem Volumenstrom begrenzt, schlägt Solidon dafür kein eigenes Tempolimit mehr vor.
- Übernehmen Sie die Werte eines Filamentprofils und wechseln danach das Filament, gelten wieder die Werte des neuen.
- Die erste Schicht druckt jetzt so breite Bahnen wie das Profil Ihres Druckers, an der 0,4er Düse meist 0,5 mm. Mit Cura fährt der Kopf dazwischen nicht mehr im Schritttempo.
- Mit Cura beginnt der Druck jetzt mit dem Startcode Ihres Druckers, wie beim Hersteller. Kennt Cura den Drucker nicht oder fehlt der Startcode in der Druckdatei, sagt Solidon es.
- Mit Cura fährt die erste Schicht jetzt mit der Beschleunigung aus dem Profil des Herstellers statt mit der vollen Druckbeschleunigung.
- Stützen aus Cura entstehen jetzt nach dem Muster der Werksprofile: zusammenhängend, mit lockerer Decke und gemäßigtem Tempo.
- Mit Cura fahren überhängende Wände jetzt langsamer, wie beim Hersteller. Drucke mit vielen Überhängen dauern dadurch bis zu rund 20 Prozent länger.
- Mit Cura druckt die Füllung jetzt nach den Wänden, und Leerfahrten meiden Stützen und ziehen auf langen Wegen das Filament zurück.
- Das Profil für das Cura-Fenster passt jetzt zu dem Drucker, der in Cura eingerichtet ist. Bisher lehnte Cura es bei manchen Druckern ab oder zeigte es nicht an.
- Den Volumenstrom bietet der Druckdialog für Cura nicht mehr als Einstellung an, denn Cura liest ihn nicht.
- Gitterstützen kommen als echtes Gitter beim Slicer an, mit wechselnder Richtung je Schicht, statt als lose Linien, die sich im Druck verschieben.
- Steht ein Teil auf vielen kleinen Füßen, schlägt Solidon einen Brim vor, wo Ihr Slicer keinen eigenen rechnet, auch wenn die Füße zusammen genug Fläche hätten.
- Ein schmaler schräger Streifen an der Außenwand gilt im Prüfbericht nicht mehr als weit gespannte Brücke.
- Schrift, die als eigenes Teil dicht an einer Wand steht, beginnt im Prüfbericht nicht mehr in der Luft, und Solidon schlägt dafür keine Stützen mehr vor.
- Den Hinweis, die Toleranzen Ihres Materials zu kalibrieren, zeigt der Prüfbericht nur noch an Modellen mit Passungen. Nur dort rechnet Solidon mit ihnen.
- Die Übergabe an Cura überträgt die ersten Schichten ohne Lüfter als Hochlauf. Gewarnt wird nur noch, wenn die fertige Druckdatei wirklich abweicht.
- Nach *Auf den Bauraum verkleinern* steht das Teil weiter auf dem Bett. Vorher hob es sich an, und der Bericht meldete es als schwebend.
- Passt ein Teil nur mit schmalerem Rand aufs Bett, liegt es nach *Auf dem Bett anordnen* in der Mitte, statt über die Kante zu ragen, und der Bericht nennt den schmaleren Rand.
- An großen Modellen findet *Modell teilen* die Naht bis zu doppelt so schnell, an mehrfarbigen in einem Bruchteil der Zeit. Geteilt wird wie vorher.
- Teilt Solidon ein Modell automatisch in drei oder mehr Stücke, zählen die Namen durch und nennen die Verbinder, etwa „Wandleiste 2 von 3 · Stifte und Löcher“.
- Eine gedruckte Schraube, Mutter oder Dichtung aus den Bausteinen gilt im Prüfbericht nicht mehr als zerfallener Körper. Sie ist ein eigenes Teil, und das ist gewollt.
- Gedruckte Schrauben und Muttern haben auch am Kopf und an der Auflage Spiel und bleiben lösbar, wenn man sie gleich mitdruckt. Ältere Projekte melden die Änderung beim Öffnen.
- Mit einer Senkkopfschraube aus den Bausteinen bleibt ein Körper aus Flächen und Kanten beim Exportieren dicht: Teil und Schraube gehen je geschlossen in die Datei.

### Bohrungen bearbeiten

- Eine Bohrung mit Senkung auf der einen und Fase auf der anderen Seite lässt sich kippen, versetzen und verdoppeln. Vorher sagte Solidon dort ab.
- Eine gekippte Bohrung oder Senkung schneidet nichts mehr weg, was vor ihrer Mündung steht, etwa eine Rippe oder die Waben daneben.
- Eine Senkbohrung in einer gewölbten Fläche lässt sich versetzen, auch per Klick im Bild. Nach Versetzen, Kippen oder Entfernen schließt die alte Stelle glatt mit der Fläche.
- Eine Senkbohrung mit gerundeter Mündungskante auf einer ebenen Fläche lässt sich samt Rundung versetzen, verdoppeln und entfernen. Vorher blieb eine Mulde zurück.
- Sackloch, Langloch und Aufweitung in einer schrägen Fläche sowie gekippte Sackbohrungen wie eine Magnettasche ohne Lippe bleiben an der Mündung ganz offen. Vorher blieb dort eine dünne Haut.
- Versetzen und Verdoppeln warnen, wenn die Wand zur Nachbarbohrung zu dünn wird oder aufreißt.
- Läuft eine Bohrung nach dem Versetzen, Verdoppeln oder Kippen seitlich aus dem Teil, sagt Solidon es auch an abgesetzten Stellen. Eine Kopie, die nicht entstanden ist, fällt auf.
- Eine versetzte oder verdoppelte Bohrung aus einer STL-Datei meldet in dünnen Platten nicht mehr fälschlich, sie gehe nicht mehr durch.
- Auf Rippen und in Waben meldet eine gekippte Bohrung nicht mehr fälschlich, sie rage über die Kante.
- Nach dem Versetzen, Kippen oder Verdoppeln zeigt das Merkmalfenster die Maße, die das Ergebnis wirklich hat.
- Bohren, Versetzen, *Bohrung ändern* und der Zug zum Langloch lassen das Modell abseits der Bohrung, wie es war. Die Erkennung danach ist an großen Modellen deutlich schneller fertig.
- Misslingt an einem Körper aus Flächen und Kanten, etwa aus einer STEP-Datei, ein Bohrungsschnitt unbemerkt, erkennt Solidon das und rechnet neu. Vorher konnte ein kaputter Körper zurückbleiben.
- An Körpern aus Flächen und Kanten stehen Bohrungsschritte nach Sekunden: An einer Lochplatte aus einer STEP-Datei dauert *Bohrung ändern* 2 statt rund 120 Sekunden.
- An Körpern aus Flächen und Kanten gibt *Tasche schneiden* keinen fehlerhaften Körper mehr zurück.
- Ein Langloch lässt sich kürzer ziehen. Auf seine eigene Breite gezogen, wird es wieder eine runde Bohrung.
- Den Griff am Ende eines Langlochs fassen Sie überall in der Öffnung, und er springt beim ersten Zug nicht mehr zur Hand.
- Langlöcher nehmen beim Versetzen und Verdoppeln ihre Fasen und ihre schräge Mündung mit. Vorher blieben die Fasen an der alten Stelle stehen.
- Eine Magnettasche aus den Bausteinen lässt sich versetzen, verdoppeln, vervielfachen und entfernen, samt der Lippe, die den Magneten hält.
- An einer Magnettasche ändert *Bohrung ändern* mit *Senkung, Stufen und Verengung mitnehmen* den Durchmesser samt Lippe. *Nur Bohrungsdurchmesser* behält die Öffnung und warnt, wenn es zu eng wird.
- Schräg zur Fläche gesetzt, bleibt die Öffnung einer Magnettasche, eines Schraubenlochs oder eines Lagersitzes frei. Vorher stand ein Keil Material darüber.
- Steht eine Magnettasche oder Schlüsselloch-Aufhängung schräg zur Fläche, sagt Solidon, dass ihre Lippe nur auf einer Seite hält, und bietet *Eingabe korrigieren* an.
- Trägt ein Baustein wie eine Magnettasche an der gewählten Stelle nichts ab, sagt Solidon es und rät, die Fläche anzuklicken.
- An einer Magnettasche mit Lippe sagt *Zum Langloch ziehen* auch an Körpern aus Flächen und Kanten ab, statt die Lippe zu durchschneiden.
- Setzen Sie ein Gewinde, eine Einpressbuchse oder eine Mutternfalle an eine Bohrung, nennt der Dialog oben die Größe, die passt, und wählt genau diese vor.
- An einer Senkung schneidet *Merkmal ändern* das neue Maß, als wäre sie gleich so gesenkt. Vorher sagte Solidon ab oder ließ eine dünne Haut quer über der Bohrung stehen.
- Stecken Teile eines Modells ineinander, vereinigt Solidon sie vor dem Rechnen, so wie sie gedruckt werden. Volumen und Bohrungen stimmen dann, und der Bericht sagt es.
- Weiten Sie eine Bohrung auf, zeigt die genaue Vorschau das ganze abgetragene Material, auch an großen Modellen, bei einem Ansichtsschnitt und an Körpern mit eingeschlossenen Kanälen.
- Beim Tippen eines Maßes an einer großen Figur steht die grobe Vorschau in unter einer Sekunde statt nach bis zu neunzehn, und die Vorschau einer Bohrung darauf gelingt.
- Rechnet ein Schritt an einem offenen Modell nur angenähert und wächst dabei das Volumen, nennt der Bericht die Abweichung und bietet *Erst reparieren, dann neu rechnen* an.

### Verrunden und Fasen

- Die Kantenwahl *Waagerecht*, *Oben* oder *Unten* nimmt den Rand einer seitlichen Bohrung nicht mehr mit. Wer ihn meint, wählt ihn einzeln; ältere Projekte rechnen wie gespeichert.
- Am eingelesenen Modell wird der Rand einer Bohrung so tief verrundet oder angefast wie am konstruierten Teil. Vorher fiel die Rundung bei großen Radien bis zu einem Fünftel zu flach aus.
- Passt das Maß nicht an jede Kante einer Kantenwahl wie *Alle* oder *Senkrecht*, bearbeitet Solidon die passenden und zeigt die anderen mit *Stelle zeigen*, statt ganz abzusagen.

### Maße im Bild

- Von Bohrung zu Bohrung stehen die Maße im Bild in einem Drittel der Zeit. Der erste Klick auf ein Merkmal hält das Fenster auch an großen Modellen nicht mehr an.
- Ein Klick auf eine Bohrung zeigt keine Zwischenbilder mehr: Auswahlfenster und Maßkarte erscheinen gleich an ihrem Platz, ohne zu springen.
- Ein Klick auf die Pfeile einer gewählten Bohrung hält die Auswahl nicht mehr fest: Die nächste Bohrung lässt sich wie gewohnt anklicken.
- Escape an den Maßen im Bild verwirft den Entwurf und hebt die Auswahl auf, wie *Abbrechen*.
- Ein Klick auf *Übernehmen* verfällt nicht mehr still, und Maße, die Sie nicht getippt haben, bleiben genau so, wie sie gemessen wurden.
- Ein begonnener Bohrungsentwurf geht nicht mehr nebenbei verloren: Ein Klick in den Prüfbericht, ein Werkzeugwechsel oder Strg+Z bittet erst, ihn zu übernehmen oder abzubrechen.
- Beim Tippen einer Koordinate verschwinden die Maßfelder nicht mehr nach der zweiten Ziffer.
- An großen Modellen antwortet *Wandstärke messen* etwa viermal so schnell.
- Ein Klick mitten in eine gesenkte Bohrung wählt die Bohrung statt ihrer Senkung, und die Maße nennen ihre Kante nach der Seite, etwa „Außenkante links“ statt „Außenkante 4“.
- Ist eine Kante oder ein Abstand gewählt, steht im Auswahlfenster nicht mehr „Kein Merkmal gewählt …“.

### Erkennen

- Merkmale werden bis 1,5 Millionen Dreiecke von selbst erkannt. Bis fünf Millionen fragt Solidon vorher und nennt den Speicherbedarf und die Dauer auf Ihrem Rechner.
- Wer die volle Erkennung ablehnt, holt sie später mit *Alle Merkmale erkennen* im Prüfbericht oder auf der Kommandozeile nach. Dauert sie zu lange, lädt *Ohne Merkmalserkennung laden* das Modell ohne.
- An großen Modellen findet *Merkmale an einer Stelle erkennen* Flächen, wo es vorher zu viele Dreiecke meldete. Die Stelle lässt sich auch per Tastatur wählen.
- An großen Modellen beginnt *Merkmale an einer Stelle erkennen* gleich mit der Suche. Vorher rechnete es erst das ganze Modell neu, am Mausoleum-Drachen 40 Sekunden je Versuch.
- Große Modelle und Gitter werden deutlich schneller erkannt: ein erzeugtes Puppenhausbett mit 1,2 Millionen Dreiecken in 27 statt 174 Sekunden. Abbrechen wirkt dabei nach wenigen Sekunden.
- Kopien und gedrehte oder verschobene Teile übernehmen die Merkmale ihres Ursprungs, statt sie neu zu suchen. Ein Projekt mit vielen gleichen Teilen rechnet so in weniger als der halben Zeit.
- Nach einer Bohrung nennt die Fläche eines konstruierten Körpers ihre heutige Größe, und eine neue Bohrung fehlt nicht mehr im Baum, wenn vorher eine andere geändert wurde.
- Schriftzüge und Streben stehen im Baum als gerundete Seiten statt als Dutzende Verrundungen mit wechselnden Radien.
- Umrisse aus Bögen und Geraden werden Bogen für Bogen mit ihrem Radius erkannt. *In Flächen und Kanten umwandeln* geht dadurch um ein Vielfaches schneller.
- Ein abgesetzter Zapfen gilt nicht mehr als Gewinde. Zylinder und Bohrungen, die diese Verwechslung verschluckt hatte, sind wieder da.
- Die Lippe einer Magnettasche heißt im Baum Verengung und nennt ihre Öffnung. Keine Handlung macht mehr eine Senkung daraus.
- Nach *Kanten verfeinern* erkennt Solidon Verrundungen, Bohrungen und Schriftzüge wie am Original, auch nach einer weiteren Bohrung. Gleiche Rundungen behalten ihren Namen, auch nach *Verschieben*.
- Ein Muster um einen runden Griff, etwa ein Rändel am Deckel, behält beim Weiterbearbeiten seine Mitte und Richtung.
- Nach *Teilen* und *Abschneiden* behält eine geteilte Fläche ihren Namen am größten Stück, und Passungen daran bleiben gültig.
- Klicken Sie die Randkante einer liegenden Bohrung an, heißt sie „Senkrecht“, so wie sie steht.
- Hat ein Modell mehr als 5 000 Merkmale, behält Solidon die größten, statt ohne jedes Merkmal dazustehen. Skalieren bringt ihre Namen nicht durcheinander.
- Ein Baustein mit einem einzigen Merkmal heißt im Baum wie im Verlauf, etwa „Magnettasche“ statt „Sackbohrung 1“.

### Einlesen und Reparieren

- Ein großes Modell steht nach dem Einlesen gleich im Bild, seine Merkmale folgen. Vorher erschien es erst, wenn die Erkennung fertig war.
- Eine 3MF aus Bambu Studio, OrcaSlicer oder ElegooSlicer mit mehreren Platten legt jedes Teil auf seine Platte, an seine Stelle darauf. Vorher kamen alle auf eine, viele neben das Bett.
- Eine 3MF mit mehreren Platten, die zu einem Projekt dazukommt, behält ihre Platten und reiht sie hinter die vorhandenen.
- Ein weiteres Modell kommt an die erste freie Stelle der Druckplatten, sonst auf eine neue Platte, und bleibt dort liegen. Vorher lag es an den Koordinaten seiner Datei, meist neben dem Bett.
- Auch ein Modell aus *Modell erzeugen* steht danach aufgesetzt an der ersten freien Stelle der Druckplatten.
- Ein Modell ohne eigene Farben bleibt nach dem Schließen seiner Löcher in der Farbe des Körpers. Vorher wurde es grau, und *Textur in Filamente umrechnen* machte ein graues Filament daraus.
- Fehlt einem Modell ein Stück Bohrungswand oder ein Teil eines Senkungskegels, schließt Solidon die Lücke als Wand, nicht als Deckel quer durch die Bohrung.
- Offene Nähte werden beim Einlesen und Reparieren geschlossen, ohne Teile zu verbinden, die sich nur berühren. Ein heiles Modell bleibt unverändert.
- Überschneidungen löst *Reparieren* jetzt von selbst auf. Stecken die Teile eines eingelesenen Modells ineinander, bietet der Prüfbericht *Überschneidungen auflösen* an.
- Eine Fläche ohne Dicke bleibt offen und bietet *Dicke geben* an. Eine große Öffnung nennt ihren Ort mit *Stelle zeigen*, und *Offen lassen* lässt nur sie offen.
- Nach dem Schließen einer Öffnung beim Einlesen umrandet *Stelle zeigen* die ganze neue Fläche in eigener Farbe.
- Ein umgestülptes Teil neben einem Hohlkörper wird gerichtet, ohne dass der Hohlraum verloren geht. Ein Teil im Material eines anderen wird gemeldet statt geraten.
- Der Prüfbericht nach dem Einlesen ist kürzer: Befunde, die das Ergebnis widerlegt, fallen weg, und wo sich etwas tun lässt, steht ein Knopf statt eines Ratschlags.
- Die Netzfehlerkarte zeigt heile Stellen in der Farbe des Körpers, damit einzelne Fehler auffallen, und trägt *Reparieren* direkt in der Legende. Einen einzigen Körper wählt sie selbst.
- Die Suche nach Überschneidungen kommt auch an Modellen mit Fächern aus schmalen Dreiecken bis zum Ende. Netzfehlerkarte und Reparatur sehen dann das ganze Modell.
- Eine 3MF aus PrusaSlicer lädt Modifikatoren, Stützsperren und Stützverstärker nicht mehr als festes Material. Eine Aussparung wird vom Teil abgezogen.
- Mit *Kanten verfeinern* bleiben alle Merkmale erhalten, und es entstehen bis zu viermal weniger Dreiecke: ein Bohrmaschinenhalter bei 1 mm Kantenlänge in fünf Sekunden statt vierzehn Minuten.
- Ein geschlossenes Modell bleibt dabei dicht und behält seine Filamentfarben. Bei zu vielen Dreiecken nennt Solidon eine Kantenlänge, die wirklich geht.
- Die Vorschau von *Kanten verfeinern* und *Dreiecke verringern* steht in Sekunden, statt das Fenster anzuhalten, und eine zu feine Länge sagt sofort ab.
- Ist ein Modell für *Kanten verfeinern* zu fein, bietet der Prüfbericht *Dreiecke verringern und erneut versuchen* mit einer Zahl an, die wirklich trägt.
- Würde *Glätten* einen Körper umstülpen, sagt Solidon es und bietet *Kanten verfeinern und erneut versuchen* mit einer Kantenlänge an, die trägt.
- Große Baugruppen lesen schneller ein: Die Reparatur beim Einlesen eines Piratenschiffs mit 1,2 Millionen Dreiecken braucht rund 30 Prozent weniger Zeit.
- Beim Öffnen großer 3MF-Dateien bleibt das Fenster bedienbar, auch während das Modell gelesen wird.
- Lesen Sie eine umbenannte Kopie einer schon geöffneten Datei ein, trägt der Körper den neuen Namen. Vorher hieß er wie die erste Datei.
- An großen Netzen rechnet *Offene Fläche schließen* in Sekunden, bei 122 752 Dreiecken 1,8 statt 24 Sekunden.

### Handbuch und Website

- Fünfzehn Anleitungen zeigen Schritt für Schritt in Bildern aus der Anwendung, wie man ein Modell prüft, druckt und repariert, ein Teil baut, teilt und beschriftet oder zweifarbig druckt.
- Das Handbuch beginnt bei „Wo fange ich an?“ und führt von dort zu jeder Anleitung. F1 im Dialog einer Operation schlägt ihre Anleitung oder ihren Eintrag auf.
- Ein Übersichtsbild erklärt das Fenster: Jede Nummer im Bild steht für einen Bereich.
- Die Suche im Handbuch findet die passende Seite auch mit Alltagswörtern, zeigt sie zuerst und schlägt sie an der Stelle auf, an der das Wort steht.
- Die Referenz nennt bei jeder Operation, wo sie im Menü oder im Auswahlfenster zu finden ist.
- Die Erklärseiten sind um ein Drittel kürzer. Gibt es zu ihrem Thema eine Anleitung in Bildern, steht der Verweis darauf am Ende der Seite.
- Auf der Website und im PDF ist das Handbuch gegliedert wie in der Anwendung, von den ersten Schritten bis zum Nachschlagen. Im PDF führen Lesezeichen zu jedem Kapitel.

### Bedienung und System

- Große Rechnungen wie Vorschau und *Kanten verfeinern* laufen in einem eigenen Prozess: Das Fenster bleibt bedienbar, und *Abbrechen* wirkt sofort. Dafür läuft ein zweiter Solidon-Prozess mit.
- Beim Laden und bei langen Rechnungen zählt eine Uhr die verstrichene Zeit mit, auch wenn der Fortschritt stillsteht, und die Restzeit springt nicht mehr, wenn ein neuer Teil der Rechnung beginnt.
- Die automatische Sicherung läuft neben dem Fenster und hält es auch an großen Modellen nicht mehr an. Lässt sie sich nicht schreiben, sagt Solidon es.
- Ein Modell auf einem langsamen oder nicht antwortenden Laufwerk friert das Fenster beim Öffnen nicht mehr ein.
- Ist eine Datei aus *Zuletzt geöffnet* verschoben worden, sagt Solidon das und bietet *Andere Datei wählen* an.
- Eine Datei, die sich nicht lesen ließ, landet nicht mehr in *Zuletzt geöffnet*, und die nächste Datei meldet beim Laden nicht deren Namen.
- Eine Datei ohne lesbares Modell bleibt nicht mehr als erster Schritt stehen, an dem jede weitere Datei mit „Die Kette hält an“ scheiterte.
- Zuletzt geöffnete Projekte auf der Startseite öffnen mit einem Klick.
- Ist nichts gewählt, bietet das Auswahlfenster an, was für alle Körper gilt: *Druckoptimal ausrichten*, *Auf dem Bett anordnen* und *Überschneidungen prüfen*.
- Nach *Modell teilen* stehen alle Teile ganz im Bild.
- Jeder angehaltene Schritt im Prüfbericht hat einen Knopf: *Eingabe korrigieren* öffnet ihn mit dem Cursor im betroffenen Feld.
- Nach *Modell teilen* sagt der Prüfbericht in einem Satz, dass die Stücke noch aneinanderliegen, statt in über zwanzig Zeilen, und Zeilen zum alten Körper tragen keine leeren Knöpfe mehr.
- Eine frei gezogene Zeichnung ohne Maß erzeugt keinen Hinweis mehr im Prüfbericht.
- Stehen im Prüfbericht nur Hinweise, sagt er oben „Druckbereit“, und ein Hinweis zur Einrichtung ist nicht mehr wie eine Warnung vorgewählt.
- Warnungen im Prüfbericht tragen einen Knopf: *Merkmal zeigen* an einer Passung, die nicht passt, *Druckeinstellungen öffnen* an Befunden zu Bett, Stützen, Düse und Brim.
- Ein Fehlerbericht nennt Ordner unter Ihrem Benutzerverzeichnis ohne Ihren Benutzernamen, auch wenn Solidon selbst dort installiert ist.
- In *Erste Schritte* steht der Drucker Ihres Slicers gleich beim Öffnen. Vorher kam der Vorschlag erst nach Sekunden, und *Fertig* übernahm bis dahin den allgemeinen Drucker.
- Nach dem Einlesen trägt die Titelleiste den Namen des Modells statt „Unbenannt“, und *Erste Schritte* nennt Slicer beim Namen statt beim Dateinamen.
- Den Slicer wählen Sie im Druckdialog über den Profilen, auch wenn dieser Abschnitt zugeklappt ist.
- Einen Drucker, den Sie im Druckdialog wählen, bekommt auch das nächste neue Projekt. Ist Ihr Slicer auf einen anderen Drucker eingestellt, bietet der Dialog diesen mit einem Klick an.
- Wählen Sie einen anderen Drucker oder Slicer, gilt das gemerkte Maschinenprofil des vorigen nicht mehr.
- In der Parameterleiste und im Dialog einer Operation wird eine getippte Zahl außerhalb der Grenzen abgelehnt statt still gekürzt, und Solidon nennt die Grenze.
- Die Nachfrage vor dem Löschen eines Schritts nennt die abhängigen Schritte, die mitgehen.
- Der Verlauf nennt einen geänderten Parameter mit seiner Beschriftung und zeigt den Wert davor und danach.
- Der Griff an einer gewählten Fläche zeigt nur noch den Pfeil, mit dem Sie sie verschieben.
- Ohne Text sagt *Text aufbringen*, dass der Text fehlt, statt die Vorschau für nicht verfügbar zu erklären.
- Nach dem Zeichnen steht rechts wieder der Reiter von vorher, etwa der Prüfbericht. Bisher stand dort der Chat, und *An den Slicer übergeben …* lag verdeckt.
- Die *Befehlspalette …* findet Operationen in jeder Sprache auch über Alltagswörter, etwa „copy“ oder „calamita“. Bisher kannte sie solche Wörter nur auf Deutsch.
- Beim Speichern mit *Auswahl als Baustein speichern …* prüft Solidon die Wandstärken des Bausteins um ein Vielfaches schneller.
- In den Übersetzungen heißen *Trennen* und *Teilen* jetzt überall verschieden, Tasten wie auf der Tastatur, und die italienische Oberfläche duzt durchgehend.

### Assistent mit lokalem Modell

- Die Modellauswahl empfiehlt auch ein kleineres Modell für Karten ab 10 GB Grafikspeicher und nennt je Modell den Speicherbedarf und wie gut es mehrteilige Aufträge schafft.
- Der Assistent bekommt nur die Handlungen ausführlich, die zur Anfrage passen. So bleibt Platz für Verlauf und Antwort, und Aufträge gelingen deutlich öfter.
- Das lokale Modell bleibt nach einer Antwort drei Minuten geladen, und die nächste Frage wartet nicht mehr auf den Modellstart.
- Eine Antwort, die kein Ende findet, bricht nach einer festen Länge ab und wird als abgeschnitten gemeldet, statt die Grafikkarte bis zur Zeitgrenze von zehn Minuten zu belegen.

## 0.5.0

### Erkennen

- Die Erkennung an eingelesenen Modellen ist um ein Vielfaches schneller: Eine Lochplatte mit 200 000 Dreiecken steht in einer Sekunde, eine glatte Freiform brauchte vorher Minuten.
- Kleine Flächen wie die Spitze eines Nockens, angeschnittene Bohrungen und Mündungsfasen werden am Netz und am exakten Körper gleich erkannt.
- Geschlossene Hohlräume und verschachtelte Luftkammern werden als Ganzes erkannt. Eine Bohrung, die in einen Hohlraum führt, erscheint nicht mehr als Phantom.
- Importierte Gewinde werden vermessen: Steigung, Gangzahl, Rechts- oder Linksgang und Nenndurchmesser. Auch gespiegelte Teile behalten die richtige Händigkeit.
- Kegel, Kugeln und Ringe behalten ihre echten Maße, und das Merkmalfenster sagt, woher ein Maß stammt: gemessen, eingepasst oder aus dem Schritt.
- Ein gespiegeltes, skaliertes oder gemustertes Teil führt seine Merkmale mit. Veraltete Merkmale bleiben nicht neben neuen stehen.
- STEP-Dateien mit Freiformflächen behalten ihre Bohrungen bearbeitbar, auch nach Speichern, Wiederöffnen und Zurücknehmen.
- Nach einer Änderung bleibt jedes Merkmal, das es noch gibt, unter seinem Namen. Kommen zwei Kandidaten in Frage, fragt Solidon, statt zu raten.
- Ein Klick auf eine Bohrung an einem Modell mit 360 000 Dreiecken antwortet in einem Viertel der Zeit.
- Eine Senkung, die zwei Langlöcher gleich berührt, bleibt eine Kegelfläche, statt in einem der beiden zu verschwinden.
- Besteht ein Modell aus mehreren Schalen und lässt sich nicht sicher lesen, ob eine davon Luft einschließt, steht das als Warnung im Prüfbericht.
- Ein geschlossenes Modell gibt seinen Speicher frei; vorher blieben einige hundert Megabyte je Modell liegen.
- Ein Modell mit vielen kleinen Flächen, etwa einem Wabenmuster, behält seine Bohrungen und Rundungen. Vorher stand es ohne ein einziges Merkmal da.
- Ein Noppenfeld mit 1 400 Kuppen erkennt sich in vier Sekunden statt in zwölf.

### Muster

- Ein Wabenmuster, ein Rändel, Rippen, Wellen oder Noppen stehen im Baum als ein Muster mit Teilung, Zellbreite und Tiefe — auch um einen Griff. Vorher waren es Hunderte Flächen.
- Ein Muster lässt sich mit einem Klick entfernen oder mit neuer Teilung, Zellbreite und Tiefe neu setzen. Die Zellen bleiben, wo sie waren.
- Eine Textur um einen Zylinder folgt der Rundung: Rillen sind überall gleich tief, und ein Muster um den ganzen Umfang schließt ohne Naht. Die Teilung rückt dafür auf das Maß, das aufgeht.

### Zeichnen

- Zeichnen auf einem gewählten Teil zeigt nur noch dieses Teil im Bild; die übrigen bleiben verborgen, bis *Nachbarn zeigen* sie wieder einblendet.
- Hochziehen auf einer gewählten Fläche fügt den neuen Körper an, statt anzuhalten — vorher ging es nie über die Skizze hinaus.
- Eine Tasche schneidet dort, wo Sie sie gezeichnet haben, auch wenn die Fläche nicht in der Mitte des Teils liegt.
- Verrunden und Fasen an einem bemaßten Rechteck lassen dessen Maße unverändert.
- Zeichnen Sie an mehreren gewählten Teilen, fragt Solidon, an welchem; das Ziel lässt sich in der Leiste jederzeit wechseln.
- Escape wirft eine begonnene Zeichnung nicht mehr weg.
- Eine schon hochgezogene Zeichnung lässt sich für die nächste Tasche weiterverwenden, ohne sie neu zu zeichnen.
- Ein Klick auf eine Fläche bietet *Hier zeichnen* und *Loch oder Aussparung zeichnen* direkt an.

### Bearbeiten am exakten Modell

- Grundkörper entstehen immer mit echten Flächen und Kanten. Der Haken „Flächen und Kanten später bearbeiten“ ist gefallen; alte Projekte rechnen unverändert.
- Bohrung, Langloch, Senkung, Zapfen, Kuppel und Kegelstumpf bleiben am exakten Körper exakt, wenn Sie sie versetzen, verdoppeln, drehen oder entfernen.
- Wulst und Kehle lassen sich versetzen, verdoppeln, drehen, ändern und entfernen. Ein Gewinde lässt sich ändern und verschließen.
- Ein Gewinde bekommt sein Gegenstück am anderen Teil auf Knopfdruck, im Tabellenmaß und als eine Passung.
- Alle Bausteine der Bibliothek bauen am exakten Körper exakt, von der Verschraubung bis zur Dichtnut.
- Nach einem Radiuswechsel verrundet Solidon die richtige Kante, auch wenn zwei Rundungen nah beieinander liegen.
- Liegen zwei Kanten an derselben Stelle, fragt Solidon, welche gemeint ist, statt eine zu nehmen.
- Übernehmen wartet, bis die Vorschau das aktuelle Ergebnis zeigt. Ein Klick auf ein veraltetes Bild schreibt nichts Falsches.
- Filamentfarben bleiben an exakten Körpern erhalten und folgen jeder neuen Vernetzung.
- Volumen und Fläche eines exakten Körpers kommen in Millisekunden statt in Sekunden.
- Ein Gewinde einzusetzen dauerte im Messlauf 0,38 bis 0,41 Sekunden statt 8 bis 13 Sekunden. Ein Gewindebolzen M6 × 1 mit 12 mm Länge entstand als vollständige Operation in 0,55 Sekunden.
- Vereinigen, Abziehen und Auf das Bett setzen fragen an exakten Körpern nicht mehr, ob umgewandelt werden soll. Sie bleiben exakt.
- Wird eine Bohrung versetzt, bleiben an der alten Stelle keine überzähligen Dreiecke zurück, und eine verdeckte Senkung verliert nichts von ihrem Volumen.
- Reparieren lässt ein sauberes Modell unverändert, auch am exakten Körper.
- Das Gegenstück zu einem Gewinde entsteht im Hintergrund. Das Fenster bleibt so lange bedienbar.

### Bohren und Maße im Bild

- Eine angeklickte Bohrung zeigt ihre Maße sofort im Bild: Abstände zu den Kanten, Mitte und Durchmesser, mit Zahlenfeldern zum Tippen.
- Die Maßfelder stehen neben dem Teil statt darauf, und ihre Linien kreuzen sich nicht.
- Der Bezug eines Maßes, Kante, Mitte oder Achse, lässt sich per Rechtsklick auf das Maß wechseln oder im Modell anklicken.
- Was im Bild steht, steht rechts im Auswahlfenster nicht noch einmal.
- Nach dem Zug zum Langloch bleiben die Maße stehen, auch wenn Sie die Ansicht drehen. Die Knöpfe zum Ziehen stehen immer am gewählten Loch.
- Beim Wählen einer Bohrung konnte die 3D-Ansicht auf manchen Grafikkarten ausfallen. Das ist behoben.
- Ein Zug am Griff übersteht ein Bild mitten im Zug, und eine Radraste über einem Maßfeld zoomt die Ansicht, statt das Maß zu verstellen.
- Das erste Escape bei der Bezugswahl nimmt nur die Wahl zurück; die getippten Werte bleiben.
- Bei „Senkung und Stufen mitnehmen“ lässt sich die Bohrung auch über die Maße versetzen. Schaft und Senkung wandern zusammen, in einem Schritt.
- Lehnt Solidon ein Maß ab, steht der Grund über der Vorschau, nicht mehr nur „konnte nicht berechnet werden“.
- Die Maßfelder bleiben stehen, wo sie standen, wenn Sie einen Wert ändern. Das Maß, in dessen Feld Sie tippen, leuchtet im Bild.
- Die Knöpfe zum Langloch wirken auch, während die Maße der Bohrung im Bild stehen: Übernehmen zieht dann das Langloch — mit einem neuen Durchmesser daneben in einem Schritt, in der neuen Breite.

### Verlauf

- Im Verlauf lässt sich ein neuer Schritt vor einem vorhandenen einfügen, statt ihn nur ans Ende anzuhängen.
- Ein Schritt im Verlauf lässt sich mit der Maus an eine andere Stelle ziehen oder Zeile für Zeile verschieben.
- Ein Schritt lässt sich ausschalten und später wieder einschalten, ohne ihn zu löschen; abhängige Schritte ruhen mit.
- Verweist ein späterer Schritt auf ein Merkmal, das der Umbau umbenannt hat, folgt Solidon ihm und meldet es.
- Würde ein Umbau des Verlaufs einen späteren Schritt anhalten, sagt Solidon ab und ändert nichts.

### Prüfen und Drucken

- Resin-Drucker sind da: Zwei allgemeine Geräte nach Bauraum stehen in der Druckerliste, ein eigener lässt sich mit Pixelgröße und Mindestwand anlegen.
- Ein Resin-Projekt bekommt keine Ratschläge zu Düse, Brim oder Brücken mehr, und die Mindestwand kommt aus dem Druckerprofil.
- Die Datei lässt sich in jedem Programm öffnen, auch im Slicer eines Resin-Herstellers, dessen Einstellungen Solidon nicht kennt.
- Exakte Körper werden für einen Resin-Drucker so fein vernetzt, wie seine Pixel es verlangen; der Prüfbericht nennt das Maß.
- Passungen prüfen die wirklichen Körper in ihrer Einbaulage. Der Export lässt sich vorher abbrechen.
- Die Formabweichung zeigt, welche Flächen einer Vernetzung wie weit vom Original entfernt liegen.
- Läuft eine Wandstärke keilförmig aus, sagt Solidon es und rät, die Außenwand zuerst zu drucken.
- Die Orientierungssuche stellt ein Gitter mit schmalem Rand auf seinen Rand, und ein Gitter aus kurzen Stegen braucht keine Stützen.
- Der Steckbrief für den Assistenten sagt zur gewählten Stelle dasselbe wie das Merkmalfenster.
- Die Formabweichung an einer Dose mit Deckel rechnet in einem Zehntel Sekunde statt in zwölf.
- Getrennt liegende Druckteile bekommen keine Warnung zur Einbaulage mehr. Die Passung meldet nur, was sie gemessen hat.
- Die Orientierungssuche an einem Modell mit über einer Million Dreiecken dauert fünf Sekunden statt einer halben Minute.
- Sehr kleine Abstände stehen in der Analysekarte als Dezimalzahl, nicht als Zehnerpotenz.
- Die Formabweichung an Rundungen und Ringen ist so genau wie an Ebenen und Zylindern — und die Karte rechnet dabei schneller als vorher.
- Der Bauteillüfter folgt wieder der Kurve aus dem Druckerprofil, statt bei jeder Schicht auf voller Drehzahl zu laufen.

### Einlesen

- Eine eingelesene Baugruppe lässt sich mit einem Klick als Ganzes auf das Bett setzen. Die Teile behalten ihre Lage zueinander.
- Ein glTF ohne plausible Größe wird nicht mehr in Metern geglaubt. Solidon fragt nach der Einheit und zeigt die Maße je Lesart.
- Ein Modell mit offenen Stellen wird beim Einlesen geschlossen, statt nur gemeldet: Löcher im Netz, umgekehrte Flächen, Kanten mit drei Flächen. Große Öffnungen nennt der Prüfbericht eigens.
- Ein eingelesenes ausgehöhltes Teil lässt sich mit einem Gitter füllen: Solidon bestimmt den Innenraum über die Entlüftungsbohrung und sagt, dass es ihn so bestimmt hat.
- Dreiecke verringern zerreißt geschlossene Modelle nicht mehr. Wo die Form es nicht anders zulässt, nennt der Prüfbericht die Zahl der Teile, in die das Modell zerfallen ist.
- Dreiecke verringern erreicht sein Ziel jetzt auch an Hülsen, Ringen und Gehäusen mit Durchbrüchen.
- Eine eingelesene STEP-Baugruppe kommt als einzelne Körper mit ihren Namen und Flächenfarben, nicht als ein verschmolzenes Ganzes.
- Vor der Übernahme einer STEP-Baugruppe wählen Sie, welche Körper Sie brauchen; ein gespiegeltes Teil bleibt ein Spiegelbild.
- Der STEP-Export schreibt Namen und Flächenfarben in die Datei; ein wieder eingelesenes Teil trägt seinen Namen unverändert.

### Bedienung und System

- Jede Handlung quittiert ihr Ergebnis kurz dort, wo Sie geklickt haben, zusätzlich zur Statuszeile.
- Ein Programmfehler hinterlässt ein lokales Protokoll, das dem Supportbericht beiliegt. Von allein wird nichts gesendet.
- Die Einrichtung für „Modell aus Text“ holt das fehlende Bildmodell selbst, statt Sie auf einen Ordner zu verweisen.
- Solidon startet in der Hälfte der Zeit.
- Bei einem gewählten Merkmal bleibt der Tooltip erhalten, und ein Hinweis zum Griff wischt die letzte Quittung nicht mehr weg.
- Hält ein Schritt des Assistenten die Auswertung an, nimmt der Vorschlag ihn ganz zurück und zeigt den Stand davor.
- Ein Modell mit 200 000 Dreiecken zu verschieben oder zu drehen antwortet in einer halben Sekunde statt in acht.
- Rückgängig antwortet sofort statt nach zweieinhalb Sekunden.
- Beim Ändern des Bohrungsdurchmessers an der Lochplatte stand die erste Vorschau im Messlauf nach 0,57 Sekunden, jede weitere nach 0,13 Sekunden.
- Aushöhlen rechnete an den drei gemessenen Modellen 7 bis 25 Prozent schneller.
- Ein Menüpunkt und ein leiser Hinweis in der Ansicht führen zur freiwilligen Unterstützung von Solidon über PayPal oder GoFundMe.
- Die Karte des Fragebogens zeigt jetzt auch im hellen Thema die richtigen Farben.

- Die Windows-Anwendung und die Setup-Datei sind digital signiert. Die Signatur bestätigt den Herausgeber und macht nachträgliche Änderungen erkennbar.

## 0.4.4

### Bearbeiten

- Die Formschräge stellt alle senkrechten Seiten an, auch die schmalen, und kommt mit eingelesenen Modellen zurecht.
- Weich verschmelzen hinterlässt glatte Seitenflächen statt ausgefranster Kanten.

### Auswählen und Bedienen

- Eine Spule im Filamentlager kann bis zu vier Farben haben. Bambu Studio, OrcaSlicer und ElegooSlicer bekommen alle Farben, andere Slicer die erste.
- Eine angeklickte Kante zeigt nur noch die Handlungen, die an einer Kante etwas bewirken.
- Ohne Auswahl bleibt der Weg zu den Bausteinen sichtbar.
- Das Suchfeld steht nur dort, wo es etwas zu finden gibt.
- Eine Trennwand im Organizer führt zu ihrem Fächereditor statt zu den Handlungen ihrer Fläche.
- Der Dialog zum Setzen einer Bohrung sagt, dass Sie die Stelle im Bild anklicken.
- Im Dialog „Modell erzeugen“ behält das Beschreibungsfeld seine Höhe, auch wenn der Hinweis zum fehlenden Zusatzprogramm erscheint.

### Bewegen und Prüfen

- Die Druckvorschläge kommen deutlich schneller: eine Figur mit 2,3 Millionen Dreiecken in Sekunden statt Minuten, und ein zweites Öffnen des Druckdialogs misst nicht noch einmal.
- Eine eingelesene Spule anderer Materialart, die kein Teil benutzt, ließ den Slicer ohne ein Wort abbrechen. Jetzt bekommt jede Spule einer Platte ein vollständiges Profil.
- Hat der Slicer kein Herstellerprofil für Ihre Materialart, sagt der Druckdialog das und nimmt Solidons Werte — statt eines Profils für ein anderes Material.
- Zwei Körper lassen sich ineinanderschieben, um sie zu vereinigen oder weich zu verschmelzen. Zurückgeholt wird nur, was neben der Druckfläche landet.
- Verweist eine Passung auf ein Merkmal, das es nicht mehr gibt, führt ein Knopf in den Verlauf.
- Druckoptimal ausrichten und Auf dem Bett anordnen legen Teile verschiedener Filamente auf eigene Platten, damit eine Düse nicht ständig spült. Mehrere Düsen tragen Sie im Druckdialog ein.

### Filamentlager

- Eine Rücknahme im Buchungsverlauf lässt sich wieder rückgängig machen — am selben Knopf.
- Wer an einer Spule nur Name oder Lagerort ändert, stellt keinen neuen Bestand fest; ihre Buchungen bleiben rücknehmbar.
- Nach einer Rücknahme bucht „Ohne Rückfrage buchen“ einen erneuten Druck wirklich, statt nur „gebucht“ zu sagen.
- Kauf- und Öffnungsdatum haben einen Kalender in Ihrer Sprache. Eine abgewiesene Spule kommt in den Dialog zurück, statt zu verschwinden.
- Die Übernahme aus dem Slicer legt eine gleichnamige Spule anderer Farbe neu an, statt Ihre Handspule umzufärben.
- Lässt sich die Lagerdatei nicht lesen, holt ein Knopf den letzten Stand zurück — Solidon sichert ihn bei jedem Speichern selbst.
- Die Detailseite nennt Restmenge, Kaufdatum und Preis; die achtstellige Kennung steht nur noch dort, wo zwei Spulen gleich heißen.

## 0.4.3

### Erkennen und Bearbeiten

- Flache Sackbohrungen, kleine Funktionsflächen und kurze Gewinde werden zuverlässiger erkannt. Die Böden der Magnettaschen gehören zu ihren Bohrungen.
- Bohrungen lassen sich samt Senkung und Einlauf maßhaltig ändern. Auch nach einer größeren Durchmesseränderung bleibt der Sackboden zugeordnet.
- An großen Netzen können Sie Merkmale gezielt an einer Stelle erkennen und sofort bearbeiten. Erkennung und Änderung lassen sich gemeinsam zurücknehmen.
- Auswahl und Vorschau zeigen den vollständigen Körper. Konturen und Beschriftungen machen die gewählte Stelle deutlich; unveränderte Schrift bleibt ohne orange Flecken.
- Kanten lassen sich an jedem Körper anklicken und verrunden oder fasen — auch an eingelesenen Modellen.
- Bohrungen, Zylinder und Rundungen entstehen auf Windows, macOS und Linux aus denselben Punkten. Ein Projekt wird auf jedem Rechner gleich erkannt und gleich bearbeitet.

### Konstruieren

- Organizer erhalten gebundene Fachmaße, einzeln änderbare Trennwände und wiederholte Fächer. Wanne, Rand, Boden und Fuß ergänzen die Bausteinbibliothek.
- Loch-, Langloch- und Wabenfelder folgen einem gezeichneten Bereich. Freizuhaltende Flächen, Randabstände und Mindeststege bleiben berücksichtigt.
- Profilklemmen entstehen aus zwei Schalen und zwei passenden Einlagen. Runde, ovale und gezeichnete Gegenprofile sind möglich; die Einlagen lassen sich später austauschen.
- Eine geschlossene Zeichnung oder gewählte Öffnung erzeugt Dichtnut und separate Dichtung. Material, Querschnitt und Überstand sind einstellbar; Restwände werden geprüft.
- Oberflächenmuster reichen bis zum Flächenrand und lassen Bohrungen frei. Vorhandene Muster lassen sich direkt über die Auswahl weiterbearbeiten.
- Abschneiden behält eine Seite einer Ebene und schließt die Schnittfläche — für glatte Rückwände und Wände auf einer Höhe. Rundungen neben leicht schrägen Wänden lassen sich wieder ändern.

### Einlesen und Bedienen

- SVG- und DXF-Konturen wählen Sie vor dem Erzeugen sichtbar aus. GLB- und GLTF-Dateien kommen mit ihren richtigen Maßen und ihrer richtigen Ausrichtung an.
- Projektmaße bleiben bis in Bausteinskizzen und Platzierungsvorschauen wirksam. Beim Einpassen berücksichtigt die Ansicht alle sichtbaren Druckplatten.
- Filamente lassen sich aus dem Regal entfernen. Die ersten Schritte beginnen beim Slicer; Rückmeldungen öffnen schnell und bereiten ihre Anhänge im Hintergrund vor.
- Entf an einer Fläche entfernt den Körper und sagt es; Strg+Z holt ihn zurück. Bei flachem Blick folgt ein gezogener Körper dem Zeiger, und die gewählte Fläche bleibt beim ersten Klick der Skizze.
- Der lokale Chat bekommt ein größeres Fenster und kürzt Ihre Anfrage nicht mehr.
- Der Düsendurchmesser lässt sich am Drucker einstellen. Die Übergabe wählt dann die passende Maschine im Slicer, auch wenn dort eine andere Düse eingestellt ist.
- Reparieren schließt Modelle, die sich an einer Kante selbst berühren, statt sie weiter aufzureißen.

## 0.4.2

### Zeichnen

- Zwei Klicks setzen ein regelmäßiges Vieleck: erst die Mitte, dann eine Ecke. Die Eckenzahl stellen Sie vorher ein — drei bis zwölf. Ein getippter Durchmesser bleibt als Maß stehen.
- Ein Langloch entsteht aus zwei Klicks auf die Mitten der runden Enden; die Breite steht daneben in der Leiste. Beide Enden bleiben gleich groß, die Flanken gerade.
- Vier neue Bedingungen: Winkel in Grad zwischen zwei Linien, gleich lang beziehungsweise gleich groß, Punkt auf der Mitte einer Linie, konzentrisch für zwei Kreise oder Bögen.
- Ein gezogener Punkt bleibt am Zeiger, und die Nachbarn folgen: Eine Ecke des Rechtecks zieht die beiden Seiten mit, eine Linie streckt die Form. Vorher kam die Ecke nur ein Stück weit.
- Ein geklicktes Rechteck ist frei: kein Festpunkt, keine Maße, solange Sie keine tippen. Eine getippte Breite oder Höhe bleibt als Maß stehen — so wie in Fusion.
- Formen aus dem Menü lassen sich verschieben; die Maße aus dem Menüeintrag bleiben. Ein Maß im Bild ändern Sie per Doppelklick auf seine Karte.
- Verrunden und Fase im Skizzeneditor: auf eine Ecke zeigen, Radius oder Maß tippen, klicken. Die Rundung bleibt beim Ziehen an ihrer Ecke, die Fase macht eine schräge Kante.
- Hält eine Bedingung einen Punkt fest, sagt die Zeile, welche — und dass ein Rechtsklick auf den Punkt sie löst. Vorher blieb der Punkt stumm stehen.
- Fest heißt fest: Ein festgesetzter Punkt folgt keinem Zug mehr. Linien, die genau waagerecht oder senkrecht liegen, bleiben es, auch wenn Sie später an einer Ecke ziehen.

### Konstruieren und Ändern

- Ein Langloch drehen dreht es — statt ein zweites quer darüber zu schneiden. Und wer ein Langloch bearbeitet, das er selbst gezogen hat, ändert diesen Schritt; der Verlauf bekommt keinen zweiten.
- Eine STL, die Sie nach „Bohrung ändern“, „Merkmal verschieben“ oder „Fase anbringen“ an einem eingelesenen Modell exportieren, kommt im Slicer geschlossen an. Vorher riss die Naht beim Verschweißen.
- Nennen Sie im Chat nur eine Achse — „Bohrung auf x = 20“ —, wandert das Loch nur dort. Vorher sprang es in den beiden anderen Achsen auf null.
- Verrunden sagt vorher, dass ein exakter Körper einen kleineren Radius zulässt als ein Netz, und was dann hilft: ein kleinerer Radius oder weiterarbeiten am Netz.
- Dieselbe Datei zweimal geöffnet ergibt zwei unterscheidbare Namen: „halter“ und „halter 2“. Vorher hießen beide Körper gleich, im Baum wie im Prüfbericht.
- Meldungen, die auf die Werte rechts verweisen, nennen das Fenster so, wie es heißt: Auswahl. Vorher stand dort „Merkmalfenster“, und so heißt kein Fenster.
- Der Schritt „Dreiecke verringern“ sagt es, wenn ein Teil schon weniger Dreiecke hat als die eingetragene Zahl — dann gibt es nichts zu verringern. Vorher blieb es stumm, wie es war.
- Der Schritt „Stellung geben“ ohne Skelett meldet, dass die Knochen im Skeletteditor entstehen — zwei Klicks je Knochen. Vorher bewegte der Schritt stumm nichts.
- Eine Bohrung, die Sie versetzen, drehen, verdoppeln oder ändern, sagt es, wenn sie dabei über die Kante des Teils gerät — wie beim Bohren. Vorher stand nur das Ergebnis im Bild.
- Versetzen und Verdoppeln einer Bohrung mit Senkung lassen das Volumen des Teils unverändert. Vorher fehlte danach bis zu ein Kubikmillimeter.
- Zerfällt ein Teil durch einen Schritt in lose Stücke, steht es im Prüfbericht — mit dem Weg zurück über Strg+Z.

### Erkennen

- Eine runde Wand — das Ende einer Lasche, der Boden einer Nut — heißt jetzt so. Vorher stand dort „Verrundung“ mit einer Kante, die es nicht gibt. Der Radius lässt sich ändern.
- Eine Bohrung mit Nasen in der Wand, etwa der Ring eines Bajonettverschlusses, ist eine Bohrung. Vorher stand dort ein Langloch so lang wie breit, und jede Handlung hätte die Nasen entfernt.
- Ein Langloch mit Fase am Rand ist ein Langloch; die Fase gehört dazu. Vorher standen an einem Rahmen 126 einzelne Senkungen im Baum.
- Eine Kerbe oder das runde Ende einer Lasche ist keine Bohrung mehr, und zwei Stücke derselben runden Wand stehen als eines im Baum.
- Ein Stück Kegel ohne eigenen Rand heißt Kegelfläche. Es lässt sich ansehen, aber nicht allein bearbeiten — und das steht an jeder Zeile.
- Die Innenwand eines Rades mit Speichen ist keine Bohrung, und ein Becher mit einem Loch im Boden ist kein Durchgang. Vorher schnitt „Versetzen“ dort die Speichen weg.
- Große Modelle werden bis zu dreißigmal schneller erkannt: Ein Uhrenteil mit 500 Bögen brauchte zwei Minuten, jetzt vier Sekunden.

### Ansicht und Bedienung

- Ein Haken im Dialog schaltet jetzt auf der ganzen Zeile — auch beim Klick auf sein Wort. Vorher traf nur das kleine Kästchen, und „Oben öffnen“ beim Aushöhlen schien nicht zu reagieren.
- Kann eine Vorschau nichts zeigen, steht im Bild, warum — etwa „Diese Ebene teilt das Objekt nicht“. Ändert sich am Volumen nichts, sagt das Band das; rechnet es länger, auch das.
- Der Schritt „Teilen“ beginnt in der Mitte des Teils statt auf seiner Unterseite. Die Zahl bleibt änderbar.
- Ein Werkzeug, das an diesem Teil nichts tun kann, steht grau im Menü und sagt, warum — „Offene Fläche schließen“ an einem geschlossenen Teil, „Zerlegen“ an einem Stück, „Gitter füllen“ ohne Hohlraum.
- Filament zuweisen zeigt die Farbe schon in der Vorschau; Dreiecke angleichen und Unterteilen zeigen das neue Netz mit seinen Kanten. Die Leertaste holt das Vorher.
- Aushöhlen an einem Teil mit Löchern in der Hülle sagt jetzt, dass die Hülle das Problem ist, und bietet „Reparieren und erneut versuchen“ an — statt zu melden, kein Rechenweg habe funktioniert.
- Am gewählten Merkmal steht grau, was dort nur scheitern könnte — etwa „Merkmal drehen“ an einer gesenkten Bohrung —, mit dem Grund. Und die Vorschau sagt, wenn erst beim Übernehmen eine Frage kommt.
- Ein Feld, das bei der gewählten Grundform nichts tut, steht nicht mehr grau im Dialog — es erscheint mit der Grundform, die es braucht. Ein Rechteck zeigt vorn vier Felder statt acht.
- Bei 150 oder 200 Prozent Bildschirmskalierung greifen Fang, Griffe und Marken wieder so weit wie bei 100 Prozent. Der Ziehgriff steht in voller Größe, und ein leicht wackliger Klick bleibt ein Klick.
- An einem großen Modell kommt die Vorschau in unter einer Sekunde statt in mehreren: Solidon rechnet sie gröber und schreibt „Grobe Vorschau“ ins Bild. Übernommen wird weiterhin genau.
- Der Schritt „An gezeichneter Linie trennen“ beginnt in der Mitte des Teils statt auf seiner Unterseite — wie „Teilen“. Vorher zeigte die Vorschau nur, dass die Ebene nichts trennt.
- Der Schritt „An Merkmal ausrichten“ bittet Sie jetzt, das zweite Merkmal zu wählen, statt Ihnen eine Schreibweise zu erklären.
- Der Start wartet nicht mehr auf die Grafikkarte: Sie wird gesucht, während das Fenster entsteht. Auf Rechnern, die lange dafür brauchten, stand das Programm dabei sekundenlang still.
- Was an einem Merkmal nicht geht, steht grau mit dem Grund — demselben Satz, den die Operation nach dem Klick gesagt hätte. Die Sätze sind kürzer geworden.

### Dateien und Export

- Eine 3MF aus dem Slicer öffnet jetzt auch dann, wenn die Farben nicht eindeutig lesbar sind: Das Modell kommt einfarbig an, und der Prüfbericht sagt, warum. Vorher blieb die Datei ganz zu.
- Bemalte Flächen aus Bambu Studio, Orca und Elegoo kommen genau so an, wie sie gemalt wurden — auch wenn die Farbe mitten durch ein Dreieck läuft. Vorher galt das als „nicht eindeutig“.
- Ein Textrelief aus dem Elegoo-Slicer oder Bambu Studio in der Datei hielt den Import auf. Jetzt öffnet die Datei.
- Modifikatoren und Stützblocker aus dem Slicer erscheinen nicht mehr als Körper, und eine Aussparung („Negativteil“) wird abgezogen — wie im Slicer.

### Bausteine und Passungen

- Ein Baustein für Bohrungen — Einpressbuchse, Mutternfalle, Lagersitz, Gewinde, Schraube — sitzt sofort in der Bohrung, die Sie gewählt haben, statt auf der Mitte der Fläche.
- Ziehen Sie einen Baustein am Griff im Bild, bewegt sich der ganze Baustein — auch an einer Kante des Schlüssellochs. Vorher wanderte nur das eine Merkmal, der Rest blieb stehen.
- Haken und Löcher eines Bausteins stehen rechts als Anzahl — nicht mehr als „2,00 mm“. Und nach „Maße ändern“ bleibt der Baustein gewählt, auch wenn er danach andere Merkmale trägt.

## 0.4.1

### Konstruieren und Ändern

- Verrunden und Fasen greifen jetzt auch an einem eingelesenen Modell: Kante im Bild wählen, Radius oder Breite eingeben. Vorher ging das nur an einem Körper, den Sie selbst gezeichnet haben.
- Fläche versetzen und Formschräge arbeiten ebenfalls am eingelesenen Modell, und eine erkannte Rundung lässt sich dort jetzt ändern oder ganz wegnehmen.
- Fläche versetzen bewegt die Fläche, auf die Sie geklickt haben. An einer Treppe bleiben die übrigen Stufen stehen, statt alle zugleich zu wandern.
- Lochkreis und Lochraster sind beim Zeichnen eigene Grundformen mit eigenen Maßen — Anzahl, Teilkreis, Durchmesser. Vorher waren sechs Löcher sechs Kreise von Hand.
- Neu ist „Wulst anlegen“: eine runde Leiste entlang der gewählten Kanten — außen als Wulst, in einem Innenwinkel als Kehlnaht. Ein exakter Körper wird dabei zum Netz; Rückgängig holt ihn zurück.
- Eine Kante wählen Sie jetzt im Bild: erster Klick der Körper, zweiter die Kante. Länge und die Knöpfe Verrunden und Fase stehen rechts. Vorher musste man sie in einer Liste wiedererkennen.
- An einem Rohr lassen sich Innen- und Außenrand getrennt verrunden oder fasen. Vorher hießen beide gleich, und die Bearbeitung traf einen von beiden.
- Die Formschräge lässt die Standfläche stehen, auch wenn das Teil nicht auf der Nullhöhe liegt. Vorher wurde ein angehobenes Teil unten mit verjüngt.
- Entlang einer Bahn führen beginnt mit dem richtigen Querschnitt und behält Öffnungen im Umriss — ein Ring bleibt ein Rohr, statt am Anfang verzerrt und innen voll zu werden.
- Ein eingesetztes Gegenstück-Paar zählt als Änderung: Es wird mitgesichert und beim Schließen erfragt. Vorher konnte es stillschweigend verloren gehen.
- Das Schloss neben einem festgesetzten Maß im Skizzeneditor ist jetzt ein gezeichnetes Symbol mit Erklärung. Auf manchem Rechner stand dort ein Kästchen.

### Bohren und Platzieren

- Beim Setzen einer Bohrung machen Sie daraus mit einem Haken ein Langloch: Sie geben Länge und Richtung ein, die Vorschau zeigt beides mit.
- Eine Bohrung, die schon im Modell steckt, ziehen Sie nachträglich zu einem Langloch — der Durchmesser bleibt, wie er gemessen wurde.
- Das Langloch wird über die ganze Länge um die Materialtoleranz geweitet. Der Weg, den eine Schraube darin hat, bleibt der, den Sie eingegeben haben.
- Ragt ein Langloch an einem Ende über die Kante, sagt Solidon es — auch wenn seine Mitte tief im Material sitzt.
- Ein Langloch steht im Objektbaum als Langloch, mit Breite und Länge — auch in einem Modell, das Sie geöffnet haben und das jemand anders gezeichnet hat.
- Ein vorhandenes Langloch ziehen Sie nachträglich länger; seine Richtung bleibt dabei, wo sie war.
- Eine gewählte Bohrung oder ein Langloch stellen Sie mit „Im Bild einstellen“ direkt im Bild ein: ein Griff zum Versetzen und Drehen, Knöpfe zum Ziehen, Maßlinien zu Kanten und Mitten.
- Erst „Übernehmen“ rechts macht daraus einen Schritt, Escape verwirft. Ein gezogenes Langloch zeigt dabei seine Länge und behält seine Form, wenn Sie es am Griff versetzen.
- Ein leeres Koordinatenfeld heißt „lass das Loch, wo es ist“. Damit setzen Sie eines auch in die Mitte des Teils — vorher der einzige Ort, den es nicht erreichte.
- Eine Bohrung versetzen Sie über „Bohrung ändern“ jetzt auch am exakten Körper — und am Netz wandert sie wirklich. Wandert sie über den Rand, sagt Solidon, dass sie kein Loch mehr ist.
- Die Breite eines Langlochs ändern Sie mit „Bohrung ändern“. Der Weg, den die Schraube darin hat, bleibt.
- Schneidet eine Bohrung oder ein Langloch das Teil ganz durch, sodass es in Stücke zerfällt, sagt der Prüfbericht das — statt nur, das Loch rage über die Kante.

### Erkennen

- Eine Senkung über einer Bohrung bleibt auch an einem Teil erhalten, das runde, geschwungene Flächen hat — vorher fiel sie dort weg, und Bohrung und Senkung ließen sich nicht mehr gemeinsam versetzen.
- Ein Hohlraum ganz im Material, ohne Verbindung nach außen, steht als Lufteinschluss im Objektbaum — mit seinem Volumen. Vorher stand dort eine Bohrung, die es nicht gab.
- Bei einem stark gekrümmten Modell sagt Solidon jetzt, was gemessen wurde, statt es einen Scan zu nennen — und welche Merkmale an einer solchen Fläche wegfallen.
- Die Merkmalserkennung großer, organisch geformter Modelle ist rund ein Viertel schneller geworden. Erkannt wird dabei dasselbe wie vorher.
- Bleibt zwischen einer Bohrung und der Wand um sie herum weniger Material, als Ihr Werkstoff trägt, steht das im Prüfbericht — gemessen am fertigen Teil.
- Die Netzfehlerkarte markiert jetzt auch Flächen, die einander durchdringen. Vorher sah sie nur offene und verzweigte Kanten und nannte ein solches Modell sauber.
- Die Schichtanalyse eines fein geriffelten Teils braucht nur noch halb so lang; gemeldet werden dieselben Stellen wie vorher.
- Ob eine Brücke als zu lang gilt, hängt jetzt von Ihrer Düse ab: Zwei Bahnen einer 0,4er-Düse sind 0,84 mm, nicht ein runder Millimeter. Kleinere Änderungen meldet der Chat nicht mehr als „+0,00 cm³“.
- Die Gewindeerkennung braucht nur noch einen Bruchteil des Speichers und lässt sich abbrechen.
- Lässt sich ein Körper wegen eines offenen Netzes nicht teilen, steht die Reparatur als Knopf am Befund.
- Lässt sich ein Schnitt nicht deckeln, sagt Solidon, dass das Modell nicht geschlossen ist — und wie es weitergeht — statt auf den Schnitt zu zeigen.

### Beschriften

- Für eine Beschriftung stehen acht Schriften zur Wahl statt drei — dazu Fett und Kursiv. Fett trägt bei gleicher Höhe dickere Striche und bleibt lesbar, wo der normale Schnitt verschmiert.
- Neben den geraden Schriften liegen jetzt eine runde und eine geschriebene bei — die beiden gibt es nur in einem Schnitt. Alle acht reisen mit dem Programm, ein Projekt sieht überall gleich aus.
- Ist eine Schrift für Ihre Düse zu fein, sagt Solidon, ab welcher Höhe sie trägt — statt sie zu drucken und zulaufen zu lassen.
- Die gerundeten Seiten eines Buchstabens — der Bogen des D, der Mantel des o — stehen jetzt im Objektbaum wie die geraden und nehmen ein eigenes Filament an. Vorher fehlten sie dort ganz.

### Bausteine und Passungen

- Ein Baustein aus dem Katalog steht sofort im Bild: auf der gewählten Fläche oder oben auf dem Körper, mit Maßlinien und Griff. Ein Klick setzt ihn um, „Übernehmen“ fügt ihn ein.
- Zerlegen Sie einen Körper mit einer Passung in Einzelteile, fragt Solidon, welches Teil die Passung jetzt meint — statt Sie zur Rücknahme der Schritte zu schicken.
- Die Einpressbuchse M2,5 bekommt ihr Einbauloch nach Datenblatt: 4,0 mm statt 3,6. Ein älteres Projekt mit dieser Buchse sagt beim Öffnen, dass sich das Maß geändert hat.
- Die Warnung vor einem brechenden Schnapparm rechnet mit der ungünstigen Druckrichtung: Ein Arm, der quer zu den Schichten biegt, trägt weniger, und das steht jetzt im Satz.
- Der Variantengenerator graviert jedem Teil seinen Wert auf die Oberseite. Ist ein Teil zu klein für eine lesbare Zahl, sagt es der Prüfbericht und nennt die Reihenfolge auf der Platte.

### Ansicht und Bedienung

- Die Handlungen an einem gewählten Körper oder Merkmal stehen rechts an einem Ort, in Gruppen zum Zuklappen, mit Suchfeld. Die Menüs Objekt, Ändern und Vorbereiten sind dafür weg; Kürzel gelten weiter.
- Der Rechtsklick auf Körper oder Fläche zeigt nur noch, was es dort allein gibt: den Schritt dahinter, die Skizze auf der Fläche, das Ausblenden. Der Knopf „Bausteine“ steht in Akzentfarbe.
- Hält die Kette an einem Schritt an, sind die Handlungen gesperrt und nennen den Grund; ein Versuch zeigt gleich die Auswege des Prüfberichts. Vorher landete der Schritt still dahinter, nie gerechnet.
- Der Plattenwähler in der Kopfzeile steht neben dem Druckernamen, nicht mehr darüber — auch wenn die Platten erst mit dem geöffneten Projekt dazukommen.
- Der Prüfbericht fasst gleiche Meldungen zu einer Zeile zusammen, die Zahl steht in Klammern davor. Ein Klick darauf wählt alle betroffenen Teile; eine Handlung fragt, für welche sie gelten soll.
- Die rechte Spalte mit Prüfbericht, Chat und Tour ist etwas schmaler geworden; der Platz geht an das Modell.
- Beim Messen schaltet die Ansicht auf gerade Projektion um und danach zurück. Perspektivisch zielt man daneben, je weiter die Strecke von der Bildmitte weg liegt.
- Wer ein Modell nur ansieht, wird beim Schließen nicht mehr nach dem Speichern gefragt. Eingelesene Dateien stehen dafür jetzt unter „Zuletzt geöffnet“.
- Schieben Sie einen Körper am Griff über den Rand des Druckbetts, holt Solidon ihn auf eine freie Stelle zurück. Ein getippter Wert wird ausgeführt, wie Sie ihn eingeben.
- Die Sprachwahl im Einstellungsdialog wirkt sofort; Ihre übrigen Eingaben bleiben, Abbrechen stellt die Sprache zurück. Das gilt auch in der ersten Einrichtung, die ein Wechsel nicht mehr beendet.
- Nach einer Viertelstunde Arbeit fragt Solidon einmal je Version nach Ihrer Rückmeldung. Antworten oder wegklicken — in dieser Version kommt die Frage dann nicht wieder.
- Ist die 3D-Maus gesperrt, nennt Solidon den Weg zur Freigabe, statt sie stillschweigend zu übergehen.
- Der Weg zum Drucker heißt im Menü „Drucken vorbereiten …“ statt „Druckeinstellungen …“. Der Dialog dahinter ist derselbe.
- Die Eingabetaste in einem Maßfeld rechts übernimmt den Schritt, und die Tabulatortaste geht die Felder von oben nach unten durch.
- Die Befehlspalette wählt den besten Treffer vor, nicht den ersten ausführbaren. „Verrund“ und Enter legten vorher einen Quader an.
- Ziehen Sie einen Körper mit der Maus, bleibt er auch über dem leeren Hintergrund am Zeiger, statt stehen zu bleiben und zu springen, sobald wieder etwas darunter liegt.
- Auch nach dem Öffnen eines Projekts ruckelt der erste Klick ins Modell nicht mehr; die Vorbereitung dafür läuft, sobald die Körper stehen.
- Feine Radbewegungen — Touchpad, hochauflösende Maus — zoomen jetzt, statt verloren zu gehen.
- Fliegen mit gehaltener Strg-Taste hört auf, sobald Sie die Taste loslassen. Vorher flog die Ansicht weiter.
- Bei hoher Bildschirmskalierung treffen Sie die Griffe so leicht wie bei 100 %.
- Nach einem Befundwechsel erschienen Knöpfe des Prüfberichts kurz als eigene kleine Fenster. Das ist vorbei.
- Die Schichtkontur eines Teils auf der zweiten Platte liegt auf diesem Teil, nicht neben dem ersten.
- Auf dem Startbildschirm stehen nur noch die Menüs, die dort etwas tun.
- Ein zweiter Baustein derselben Art — etwa ein zweiter Drehdeckel — bekommt eine Nummer, statt wie der erste zu heißen.

### Dateien und Export

- Vor dem Schreiben zeigt der Export, was der Prüfbericht gefunden hat — eine dünne Wand, eine verletzte Passung. Sie entscheiden, ob die Datei trotzdem entsteht.
- Ordner, Format und Namensschema merkt sich Solidon je Projekt. Entstehen mehrere Dateien, steht das Namensmuster im Feld und lässt sich ändern.
- Beim Einlesen eines Modells bleibt der Fortschritt stehen, bis das Modell wirklich da ist, und die Anzeige sagt „Modell wird gelesen“ statt „Projekt wird geladen“. Abbrechen bleibt erreichbar.
- Eine beantwortete Rückfrage, welches Merkmal ein Schritt meint, bleibt beantwortet — auch nach dem Schließen und Wiederöffnen des Projekts.
- Ist die verknüpfte Datei eines Projekts nicht erreichbar, lässt es sich trotzdem speichern und öffnen; der Prüfbericht nennt die Quelle. Fehlen Rechte, heißt es nicht mehr „beschädigt“.

### Druckbett und Übergabe

- Passt ein Körper aus losen Teilen — etwa ein Schriftzug — als Ganzes auf kein Bett, bietet der Prüfbericht an, ihn zu zerlegen und gleich auszurichten: ein Klick, und die Teile liegen auf den Platten.
- Im Slicer öffnen gibt ElegooSlicer, Orca und Bambu Studio alle Platten in einer Datei — ein Fenster statt eines je Platte.
- Der Prüfbericht nennt bei Zerlegung, Beschriftung und Textur die Zahl im Satz, wo vorher ein Platzhalter in Klammern stand.
- Ein Schriftzug, dem Sie ein Filament zugewiesen haben, behält es beim Zerlegen in Buchstaben. Vorher kam er im Slicer auf einem zweiten, grauen Filament an, das zugewiesene lag daneben.
- Mit mehreren Platten liegen die Teile im Slicer jetzt dort, wo er seine Platten hat: im Raster, wie er es selbst anlegt. Vorher standen die Buchstaben der dritten und vierten Platte neben allem.
- Bleibt beim Slicen eine Spule ungenutzt, sagt Solidon es mit ihrem Namen. Vorher meldete der Slicer Erfolg, und im Druck fehlte ein Filament.
- Stürzt ein Slicer ab, sagt Solidon das so. Vorher hieß es, er habe keine Druckdatei geschrieben.
- Creality Print wird als Slicer erkannt und steht im Druckdialog zur Wahl, mit seinen Druckern, Prozessen und Filamenten.
- Der Druckdialog öffnet sofort mit dem zuletzt gewählten Slicer; die Suche nach weiteren läuft im Hintergrund. Vorher konnte der Klick auf Drucken zehn Sekunden lang nichts zeigen.
- Die Slicerauswahl zeigt alle installierten Programme — auch ein zweites Flatpak oder ein zweites AppImage. Vorher fehlte je Fundort das zweite.
- Ein Filament aus einem PrusaSlicer-Herstellerbündel kommt mit seinen eigenen Werten in der Übergabe an, nicht mit denen des ersten Filaments der Datei.
- Bei der Übergabe als STL — etwa an Cura — sagt Solidon, dass Einstellungen je Teil nicht mitreisen, und nennt den Vorschlag für die ganze Platte, statt zu behaupten, sie seien gesetzt.

### Filamente und Lager

- Das Filamentlager lässt sich auch auf einem FAT32-Stick, einer exFAT-Platte oder einer Netzfreigabe speichern. Vorher scheiterte dort jedes Speichern.
- Lässt sich das Lager nicht lesen, sagt Solidon es auch im Filamentwähler, mit dem Knopf „Erneut versuchen“ — statt einer leeren Liste.
- Der aus der Druckdatei gemessene Verbrauch zählt auch Material, das ohne Bahn gefördert wird, und rechnet Rückzüge nicht doppelt. Schreibt der Slicer die Menge selbst, gilt seine Zahl.
- Wer beim Abbuchen „Nicht buchen“ wählt, wird für diese Ausgabe nicht erneut gefragt; sie bleibt unter „Nicht gebucht“ erreichbar.
- Legen Sie im Buchungsdialog eine neue Spule an, bleiben gewählte Spulen, eingetragene Mengen und Aufteilungen stehen.
- Der Objektbaum zeigt an Körper und Fläche nur die Filamente, die dort wirklich liegen — eine Fläche mit eigenem Filament trägt ihres, nicht die Liste des ganzen Körpers.
- Abbrechen bei der Suche nach Filamentprofilen wirkt sofort.

### Chat und KI

- Vor der ersten Anfrage an einen Modell-Erzeuger sagt Solidon, welche Daten dorthin gehen.
- Belegt ein anderer Lauf die Grafikkarte, wartet der Chat sichtbar, statt still zu stehen.

### Update, Installation und System

- Die Mac-Pakete sind signiert und notarisiert. Der Umweg über „Datenschutz & Sicherheit“ → „Trotzdem öffnen“ entfällt.
- Unter „Unterstützen“ steht neben PayPal jetzt GoFundMe zur Wahl; erst Ihr Klick öffnet den Browser, und ohne Browser lässt sich die Adresse kopieren.
- Liegt Ihr Kaufcode auf einem Laufwerk, dessen Dateirechte sich nicht setzen lassen — FAT, Netzfreigabe —, bleibt er lesbar. Vorher galt er dort als nicht vorhanden.

## 0.4.0

### Konstruieren und Ändern

- Gegenstücke wie Passstift und Bohrung setzen Sie in einem Schritt auf beide Teile. Die gemeinsamen Maße geben Sie einmal ein, und eine Rücknahme nimmt das Paar zurück.
- Zwischen zwei Umrissen aufspannen nimmt zwei eigene Zeichnungen: rund unten, eckig oben. So entsteht der Adapter von einem Rohr auf einen Kanal.
- Entlang einer Bahn führen folgt einer gezeichneten Bahn mit mehreren Ecken und Bögen statt nur einem gleichmäßigen Bogen. An scharfen Ecken schneidet Solidon auf Gehrung.
- Verrunden und Fasen greifen jetzt auch an einer einzelnen Kante. Sie wählen sie in einer Liste, die jede Kante mit ihrer Lage und ihrer Länge nennt.
- Ein Baustein geht in einem Schritt an mehrere Stellen: Vier Bohrungen bekommen ihre Einpressbuchsen gemeinsam, und eine Rücknahme nimmt alle vier zurück.
- Neu ist *Fügeweg prüfen*: Es führt ein Teil in seine Endlage und meldet, wo es unterwegs anstößt — auch wenn beide Teile in der Endlage zusammenpassen.
- Jeden Baustein können Sie als OpenSCAD-Quelltext ausgeben, aus dem Katalog heraus oder über die Kommandozeile.
- Am exakten Kern lässt sich auch auf eine schräge Fläche bohren, mit Senkung und Aufweitung; Muster und Steckmontagen bleiben dabei erhalten.

### Bohren und Platzieren

- Beim Setzen einer Bohrung zeigt die Vorschau den Umriss der Mündung statt eines halbdurchsichtigen Zylinders. Die Stelle, auf die es ankommt, bleibt frei.
- Die Vorschau folgt der Maus flüssig: Die Flächensuche unter dem Zeiger rechnet nicht mehr bei jeder Bewegung von vorn.
- Die Maßfelder weichen der Stelle aus, an der die Bohrung entsteht, statt über ihr zu stehen.
- Wer eine Operation wählt, die im Modell platziert wird, platziert sofort; der Knopf davor entfällt.
- Nach dem Übernehmen der Maße stellen Sie die Tiefe mit der Maus ein. Das Modell wird durchscheinend, und die Ansicht schwenkt zur Seite, damit Sie in das Loch hineinsehen.
- Beim Ziehen rastet die Tiefe kurz an den Stellen ein, die etwas bedeuten: an der Mitte des Materials und an seiner Rückseite.
- Quader, Kugel und die anderen Grundkörper verschieben und drehen Sie schon in der Vorschau, mit demselben Griff wie am fertigen Körper.
- Die Grundkörper haben einen Drehwinkel bekommen: Die Richtung sagt, wohin der Körper zeigt, der Winkel, wie er dabei herumsteht.
- Wer in einen Zylinder, eine Kugel oder einen Ring bohrt, bekommt nicht mehr bei jeder Bohrung die Warnung, sie rage über den Rand hinaus.
- Eine Bohrung mit Senkung wird auf Nachfrage ganz entfernt, statt die Senkung ohne Weg zurück stehen zu lassen.

### Merkmale und Auswahl

- An einer angeklickten Bohrung stehen nur noch die Handlungen, die dort etwas bewirken — vorher standen dort auch Text aufbringen und Filament zuweisen.
- Jede Handlung an einem Merkmal steht einmal statt zweimal, und ein Bausteindach über einer einzigen Zeile entfällt.
- An einer vorhandenen Senkung ist *Senken* wieder erreichbar.
- Im Objektbaum bündeln sich gleichartige Merkmale nur noch, wenn auch ihr Maß gleich ist. Zehn Hohlkehlen mit verschiedenen Radien stehen wieder einzeln da.
- Ein Körper mit zugewiesenem Filament zeigt seine Auswahl wieder im Bild, statt grau zu bleiben wie alle anderen.
- Die Felder am Merkmal tragen ihren Namen: Ein Bildschirmleser sagt jetzt, wozu ein Feld gehört, statt sechsmal Drehfeld, 0,00.

### Bausteine und Passungen

- Ihre eigenen Bausteine öffnen Sie aus dem Katalog wieder zum Bearbeiten, auch wenn das Projekt, aus dem sie stammen, nicht mehr da ist.
- Die Toleranzleiter übernimmt das gemessene Maß der Bohrung, an der Sie sie öffnen, statt einer festen Vorgabe von 6 mm.
- Schnapphaken und Klemmzungen rechnen mit Material und Federweg statt mit einer Faustregel. Solidon meldet einen Arm, der beim ersten Einrasten bricht.
- Die drei Kalibrierkörper entstehen ohne Hilfskörper, und die Toleranzleiter wird als zwei nummerierte Leisten gedruckt, die ineinandergesteckt werden.
- Die Federwarnung misst den tatsächlichen Arm, das Filmscharnier bewegt sich, und die Kabelzugentlastung trägt bis in Vorschau und Ausgabe.
- Ein Baustein legt bei Bedarf tragendes Material vor, bevor er schneidet; und ihre Vorschau sitzt auch ohne Träger richtig.
- Ein Baustein erklärt, welche Kombination von Maßen er nicht bauen kann, statt sie still zu kappen.

### Filamente und Lager

- Ihr Filamentbestand hat einen eigenen Ort: eine Kachel auf der Startseite und ein Regal statt einer Liste, mit dem Füllstand als Wicklung auf der gezeichneten Spule.
- Zwei Spulen mit demselben Namen bleiben auseinandergehalten. Jede führt ihren eigenen Rest, und die angebrochene ist die interessante.
- Beim Slicen und beim Übergeben fragt Solidon, ob es den Verbrauch abbuchen soll. Nach dem Slicen ist es die gemessene Menge aus der Druckdatei, sonst eine Schätzung.
- Jede Buchung ist rücknehmbar, jede Spule führt ihren Verlauf, und ohne Rückfrage bucht nur, wer das ausdrücklich einstellt.
- Ein zugewiesenes Filament lässt sich wieder entfernen, ohne dass die Nachbarflächen ihres dabei verlieren.
- Eine bemalte Fläche kommt in Orca und PrusaSlicer mit ihrem Filament an, nicht mehr ohne.
- Nach einer Abwahl landet das Herstellerprofil nicht mehr beim falschen Filament.
- Im Regal sind Suche und Hauptaktionen beieinander, und Lagerort und Nennfüllung stehen im Spulendialog.

### Drucken und Vorbereiten

- Solidon findet den Bestand von Cura: Drucker, Prozessprofile und Filamente, die vorher unsichtbar blieben.
- Von PrusaSlicer übernimmt Solidon die eingelegten Filamente und den zuletzt eingestellten Drucker.
- Kennt Ihr Slicer den eingestellten Drucker gar nicht, sagt Solidon das — statt Sie in eine Liste zu schicken, in der nichts steht.
- Die Qualitätsstufe zu wechseln dauert Sekunden statt einer knappen Minute, und das Fenster bleibt dabei bedienbar.
- Die Beratung zu den Druckeinstellungen sieht alle Körper der Platte statt nur der Auswahl. Was ein Körper braucht, bleibt erhalten, auch wenn der daneben ohne auskommt.
- Sie rechnet im Hintergrund, nennt den Körper, zeigt ihren Fortschritt und lässt sich abbrechen.
- Eine lange Brücke wird an ihren tatsächlichen Auflagern bewertet, und der Überhangwinkel gilt für Drucker, Düse, Schichthöhe und Linienbreite, unter denen er gemessen wurde.
- Zu hohes Tempo wird an der betroffenen Bahnart begrenzt, statt Düse und Bett immer weiter aufzuheizen.
- Abgewählte Vorschläge bleiben abgewählt, und ein Wechsel von Filament, Szene, Platte oder Qualität entwertet ein veraltetes Ergebnis sofort.
- Der Abstand beim Anordnen rechnet Druckbetthaftung und Stützstruktur mit: Beide zählen zwischen zwei Nachbarn doppelt.
- Angeordnet wird in der Mitte des Betts, wie in den Slicern daneben, statt in der hinteren linken Ecke.
- Druckoptimal ausrichten legt die gedrehten Teile danach neu hin. Ein Körper, der sich hinlegt, braucht mehr Fläche und steckte vorher im Nachbarn.
- Die zweite Filamentauswahl unter den Slicer-Profilen ist verschwunden. Sie wiederholte den Filamentwähler; die Profilwerte zu holen steht jetzt als eigener Knopf da.
- Druckoptimal ausrichten nimmt alle Körper der Szene, nicht nur die markierten. So wandert danach das ganze Bett in die Mitte, statt dass ein gedrehtes Teil einem stehenden ausweicht.

### Ansicht und Bedienung

- Der Mauszeiger von Solidon steht im ganzen Fenster und in jedem Dialog, nicht mehr nur in der 3D-Ansicht.
- Ein Wechsel der Variante im Operationsdialog beendet die Anwendung nicht mehr.
- Ein offener Operationsdialog übersteht keinen Projektwechsel mehr unbemerkt.
- Lange Hinweise werden nicht mehr abgeschnitten, während daneben Platz frei bleibt.
- Über die Kommandozeile ließ sich *Filament zuweisen* nicht aufrufen; jetzt schon.
- Der erste Klick und die erste Drehung ruckeln nicht mehr: Was die Ansicht dafür vorbereiten muss, geschieht jetzt beim Start.

### Update, Installation und System

- Unter *Neuerungen* stehen die letzten drei Versionen. Der vollständige Verlauf aller Fassungen steht auf solidon3d.de und bleibt dort nachlesbar.

### Handbuch und Website

- Die Bilder auf solidon3d.de zeigen das Modell in ganzer Breite statt als Streifen zwischen den Panelen.
- Handbuch und Website nennen jede Operation, die es gibt, samt der neuen Merkmalseditoren.

## 0.3.5

### Ansicht

- Die 3D-Ansicht zeichnet mit einer neuen Grafikschicht. Sie spricht die Grafikkarte über Direct3D 12, Vulkan oder Metal an und bleibt auch bei mehreren Millionen Dreiecken flüssig.
- Vertiefungen und Kanten treten plastischer hervor: Die Ansicht dunkelt Ecken ab, zieht Tiefenlinien und trifft beim Anklicken den Punkt, auf den Sie zeigen.
- Körperkanten stehen als feines Drahtgitter über der Fläche, und Beschriftungen bleiben ruhig stehen, statt beim Drehen zu zittern.
- Merkmalsnamen überlagern sich nicht mehr, und ihre Marken bleiben auch im Schnitt sichtbar.
- Die Achsenanzeige unten links füllt ihr Feld in jeder Blickrichtung, und ihre Buchstaben sind ganz zu sehen.
- Die festen Ansichten drehen die Kamera um den Punkt, auf den Sie sehen. Ihr Ausschnitt bleibt erhalten, statt auf die ganze Szene zurückzuspringen; dafür ist weiter *Einpassen* da.
- Wer durch eine Öffnung auf eine dahinterliegende Fläche zeigt, wählt diese Fläche und nicht den Rand der Öffnung.
- Große Modelle bauen sich schneller auf, weil Kanten und Flächennormalen nur noch einmal je Körper gerechnet werden.
- Fehlt dem Rechner die Grafikunterstützung für die Ansicht, nennt die Anwendung die beiden Pakete, die installiert werden müssen.
- Kippen Sie die Ansicht nahe an eine Achse, rastet sie dort ein und behält dabei Ihre Drehung, statt in eine feste Lage zu springen.

### Handlungen zur Auswahl

- Prüfbericht und Chat schließen rechts mit ihrem eigenen Rand ab. Die Handlungen zur Auswahl stehen darunter in einer eigenen Karte, und zwischen beiden ist das Modell zu sehen.
- Welche Handlungen vorn stehen, richtet sich nach der Auswahl: bei mehreren Körpern Vereinigen, Abziehen und Schnittmenge, bei einem einzelnen Bohrung setzen, Aushöhlen und Teilen.
- An einer angeklickten Bohrung stehen dort Senken und Bohrung verschließen, an einer Fläche Bohrung setzen, Tasche schneiden und Fläche versetzen.
- Ein gewählter Körper zeigt seine Filamente unmittelbar an und lässt sie dort ändern.
- Weitere Operationen findet ein Suchfeld in derselben Karte; Merkmale und Bausteine bleiben in ihren eigenen Bereichen.
- Die rechte Spalte ist breiter geworden: Die Handlungen zur Auswahl stehen vollständig da, statt sich auf halber Breite zu drängen.

### Konstruieren und Ändern

- Vereinigen, Abziehen und Schneiden nehmen alle gewählten Körper auf einmal, nicht nur genau zwei.
- Verrunden bricht die Anwendung nicht mehr ab, wenn der Radius größer ist als die Wand, die er verrunden soll.
- Ein Körper aus dem exakten Kern bleibt exakt, wenn Sie ihn nur verschieben oder drehen. Verrunden und Fasen bleiben danach möglich.
- Das Bohrwerkzeug ragt nur noch an der Mündung über den Körper hinaus und lehnt Durchmesser ab, die das Teil um ein Vielfaches übersteigen.
- Bündig ausrichten heißt bündig bis auf einen Winkel und nicht bis auf einen einzelnen Punktabstand.
- Dreiecke verringern hört an einer benannten Auflösung auf, und die Gitterfüllung erfindet keinen Innenraum mehr, den es nicht gibt.
- Der Skizzeneditor trifft Bögen auf dem Vollkreis, findet Kreisränder, löscht mit Entf das gewählte Element und lässt Wiederholen nicht offen stehen.
- Die Rückmeldung beim Formen erklärt kleine Änderungen nicht mehr für wirkungslos.
- Schalter einer Operation, die von sich aus an sind, lassen sich auf der Kommandozeile jetzt auch abschalten.
- Ein Fehler in einer Operation nennt seine Ursache: im Protokoll, in der Abbruchzeile und im Fehlerbericht.
- Abgelehnte Eingaben in Platzierung, Netzspeicher und Rezepten kommen mit Handlungsvorschlag statt als nackte Fehlermeldung.
- Bausteine erklären, welche Parameterkombinationen sie nicht bauen, statt Maße still zu kappen.
- Eine unpassende Zahl gewählter Körper wird vor der Berechnung gemeldet, statt eine Eingabe unbemerkt auszulassen.
- Das Platzieren auf einer Oberfläche ändert das Dokument erst beim Übernehmen; eine verworfene Vorschau lässt nichts zurück.
- Buchstaben und Zahlen bleiben im Eingabefeld — Navigationstasten greifen erst, wenn dort nicht getippt wird.
- In Einzelteile zerlegen macht aus mehreren losen Körpern in einer Datei je ein eigenes Objekt — was sich nicht berührt, ist nicht ein Teil.

### Merkmale

- Ein eingelesener Scan trägt keine erfundenen Kuppeln und Pfannen mehr; bisher entstanden sie zu Hunderten aus glatt gerundeten Flächen.
- Mehrere Gewinde auf einer Platte werden einzeln benannt, nicht als ein Merkmal zusammengefasst.
- Kugel, Torus und Kegel weisen ihre Krümmung aus, Zylindermitten stimmen mit den Endringen, und Gewindegänge folgen der Achse.
- Das Merkmalsfeld bietet Passungen nur an, wenn ein zweiter Körper gewählt ist, und kennt jede Gruppe des Kerns.
- Automatische Schnittpassungen vergeben keinen Namen zweimal.
- Die Merkmalserkennung kommt bei komplexen Netzen schneller zum selben Ergebnis.

### Drucken und Vorbereiten

- Die Ausrichtungssuche urteilt zweistufig: zweihundert Lagen aus den Flächennormalen, davon neun in der Schichtanalyse.
- Ihr Fortschrittsbalken läuft bis zum Ende, auch wenn nichts zu schneiden war.
- Der Slicer bekommt die Welt des Druckers und nicht die von Solidon, und ein eigenes Profil behält seine Herstellerbasis.
- Eigene Slicerprofile stehen vor dem gleichnamigen Herstellerprofil, und ein AppImage findet seinen Bestand.
- Die Bereinigung nach dem Einlesen behält die Filamentzuweisungen.
- Der Drucker gehört zum Projekt und lässt sich in der Kopfzeile wie im Druckdialog wechseln; zugewiesene Filamente, Farben und eigene Druckwerte bleiben erhalten.
- Jeder Körper trägt sein Filament im Objektbaum: ein Farbfeld vor dem Namen, ein Klick darauf weist ein anderes zu.
- Mehrere Rollen derselben Materialart bleiben dabei an Namen und Farbe unterscheidbar.
- Die Operationen dazu heißen nach ihrer Sache: *Filament zuweisen* und *Filament auf eine Fläche* statt *Teil färben* und *Fläche färben*.
- Die Slicer-Übergabe rechnet jede Spule gegen ihre eigene Materialart; eigene Druckwerte behalten Vorrang.
- Dauert die Stützkarte zu lange, endet die Berechnung mit einer Erklärung und bietet das Verringern der Dreiecke an.
- Der Druckdialog bleibt auch in schmalen Fenstern vollständig bedienbar.
- Druckoptimal ausrichten richtet alle gewählten Körper aus und nicht nur den ersten.

### Dateien und Projekte

- Eine 3MF mit vielen Verdopplungsebenen wird abgelehnt, bevor aus 432 Byte tausend Körper werden.
- Eine kleine Projektdatei fordert keine Gigabyte Speicher mehr an.
- Eine GLB-Datei in Millimetern kommt in Millimetern an und nicht als Meter.
- Ein gescheitertes Speichern nimmt die letzte Sicherung nicht mehr mit, und Abbrechen bricht den Import wirklich ab.
- Ein verspäteter Fehler beim Einlesen räumt nicht die Quelle des nächsten Projekts weg.
- Lässt sich der Cache-Ordner nicht anlegen, bleibt das fertig gerechnete Ergebnis trotzdem stehen.
- Ein unvollständiger Variantensatz wird nicht mehr stillschweigend exportiert.
- Die verworfene Zeichnung lässt sich mit Rückgängig zurückholen, und ein zweites Verlaufsobjekt lässt kein veraltetes Wiederholen stehen.
- Zwei Fehlerberichte derselben Sekunde überschreiben sich nicht mehr.
- Ausdrücklich gewählte Eingaben überstehen Speichern und erneutes Öffnen, statt von einer Vorgabe ersetzt zu werden.
- Abbrechen beendet auch die Berechnung, die zu einer Variante noch läuft.

### Chat und KI

- Ein Zusatzwerkzeug mit falschem Feldtyp reißt den Zug des Agenten nicht mehr ab.
- Der Agent nennt zu Skizzenvarianten nur Menüwege, die es gibt.
- Bei der Bildgenerierung kommen die Gewichte ganz oder gar nicht an, und ein einzelner Wert im Strukturfeld löst keine unbestellte Erzeugung aus.
- Ein lokales Modell wird auch dann gemessen, wenn es über HTTPS auf einem eigenen Port antwortet.
- Der Hinweis auf KI-Beteiligung gilt erst mit geschriebenem Nachweis, und ein Sprachwechsel beendet die Fernbedienung nicht.
- Die ComfyUI-Einrichtung übernimmt vollständig vorhandene Modellgewichte, statt sie erneut zu laden.

### Update, Installation und System

- Als Mindestversion gilt macOS 13, gleich in Paket, Installer und auf der Website.
- Dreizehn Bibliotheken stehen auf ihren neuesten stabilen Fassungen, und der exakte Kern spricht OpenCASCADE 8.
- Ein Paket ohne Vertrauensanker im System bringt seinen eigenen Satz mit, gleich auf welcher Plattform.
- Ein Download bricht nicht mehr nach einer festen Gesamtzeit ab, und eine tröpfelnde Antwort hält die zugesagte Frist ein.
- Im Flatpak findet die Anwendung die Paketverwaltung des Rechners.
- Unter Linux und macOS endet ein Abbruch nicht mehr nur am Elternprozess.
- Der Linux-Menüeintrag findet den Starter auch ohne Eintrag im Suchpfad.
- Auf dem Mac sagt der Update-Dialog, dass Solidon nach dem Installer von selbst zurückkommt.
- Die 3D-Maus liest auf dem Mac durch den Treiber des Herstellers, statt neben ihm zu warten.
- Die Startseite erkennt das System vor dem ersten Bild, und die Anforderungstabelle wird nicht abgeschnitten.
- Ein abgelehnter Anhang gilt der Rückmeldung nicht mehr als fehlender.
- Der Filamentwähler bleibt nach einem Abbruch auf der richtigen Spule und zeigt auch die achte.
- Eine von Hand geöffnete Support-Mail trägt auch im Flatpak lesbaren Betreff und Text; ein Abbruch lässt den Bericht stehen.

### Handbuch und Website

- Handbuch und Bedienbelege zeigen die überarbeitete Oberfläche in allen sechs Sprachen.
- Die Zeichnungen des Handbuchs halten den Textkontrast auch in ihren Nebenbemerkungen.
- Das Handbuchfenster lädt nur seine eigenen Abbildungen und keine fremden Bilder.
- Die Website sagt an einer Stelle, was den Rechner verlässt.
- Die Einführung behauptet kein geschlossenes Loch mehr, wenn Rückgängig nur den Durchmesser zurückstellt.

## 0.3.4

### Erkannte Merkmale bearbeiten

- Eine Bohrung und ihre verknüpfte Senkung werden beim Verschieben gemeinsam versetzt — gleich, welche der beiden gewählt wurde. Der Merkmalbereich weist vor der Änderung auf die Kopplung hin.
- Beim Ändern einer Bohrung bleibt ihre Senkung im Objektbaum zugeordnet und kann direkt mitangepasst werden.
- Der Merkmalbereich fasst gleiche Ablehnungen zusammen und benennt die betroffenen Feldgruppen klar.

### Merkmalserkennung

- Gewinde in importierten Modellen werden zuverlässiger erkannt; falsche Kegel, Zapfen und Kugeln daran erscheinen nicht mehr als eigene Merkmale.
- Schmale Nähte zwischen zusammengefügten Formen erzeugen nicht mehr zahlreiche falsche Merkmale.
- Die Merkmalserkennung großer, detailreicher Modelle ist spürbar schneller.

### Analysekarten

- Analysekarten stehen für mehr große Modelle zur Verfügung.
- Ist eine Analysekarte für ein Modell zu groß, bietet die Meldung direkt *Dreiecke verringern* an.
- Die Analyse des Stützbedarfs großer Modelle ist deutlich schneller.

## 0.3.3

### Anzeige und Auswahl

- Der erste Klick wählt das Teil, der zweite die Bohrung darunter, ein Klick daneben hebt die Auswahl auf — und die eingestellte Steuerung gilt dabei durchgehend.
- Beim Drehen bleibt der Horizont waagerecht: Die Ansicht steht nach einer Geste so aufrecht wie vorher, in jeder der fünf Steuerungen.
- Die in den Einstellungen gewählte Steuerung und das Thema stehen auch im Menü *Ansicht* angehakt.
- Mehrere gewählte Körper bleiben nach einer Neuberechnung gewählt, und ein Zug bewegt sie zusammen.

### Arbeiten am Projekt

- Ein Projekt lässt sich auch dann speichern, wenn an einem Merkmal ein Hinweis hängt.
- Der Wechsel zwischen zwei Analysekarten desselben Körpers zeigt sofort, was schon gerechnet ist.
- Ein neues Projekt beginnt ohne Reste einer Vorschau, die beim Wechsel noch offen stand.
- Über die Fernsteuerung nimmt *Zurücknehmen* genau den genannten Schritt zurück und nicht den obersten.

## 0.3.2

### Erkannte Merkmale bearbeiten

- Beim Versetzen, Drehen und Entfernen einer Bohrung bleibt an der alten Stelle kein Material stehen — auch an Teilen mit Nut oder Innenraum.
- Auch *Bohrung verschließen* füllt genau die Bohrung: Der Pfropfen ragt nicht mehr in eine Nut und macht das Teil nicht dicker.
- Eine Kugelpfanne wird auch in fein vernetzten Modellen als Kugelfläche erkannt und nicht als Senkung; sie trägt damit die Handlungen, die zu ihr gehören.
- Eine verdoppelte Bohrung bekommt eine eigene Kennung und nicht die einer zuvor gelöschten; eine Passung zeigt damit weiter auf das Merkmal, das sie meint.
- Auch beim Drehen sagt eine durchgehende Bohrung, wenn sie an der neuen Lage nicht mehr durchgeht.
- Ein neu erzeugtes Merkmal steht im Objektbaum am Ende und nicht mitten zwischen den älteren.
### Anzeige und Auswahl

- Die Vorschau verschwindet, sobald die Änderung übernommen ist; bisher lag der Vergleichskörper mit dem Band „noch nicht übernommen“ über der fertigen Bohrung.
- Die Leertaste blendet wieder nur dort zwischen Vorher und Nachher um, wo eine Vorschau steht, und nicht mehr überall in der Anwendung.
- Eine Bohrung leuchtet nicht mehr in der Auswahlfarbe, wenn gar nichts ausgewählt ist.
- Drehbogen, Schatten, Zugmarken und der Ring des Pinsels verschwinden mit dem Vorgang, an dem sie hängen — auch beim Werkzeugwechsel, Zurücknehmen oder Schließen.
- Ein Maß bleibt bei seinem Teil, auch wenn die Ansicht auf eine andere Druckplatte oder auf alle umschaltet.
### Drucken und Arbeitsspeicher

- Passt nicht alles auf eine Platte, entstehen so viele Platten wie nötig; bisher blieb der Rest neben dem Bett liegen, wo er nicht druckbar ist.
- Der Merkmalsspeicher großer Modelle bleibt begrenzt; bisher konnte er bis zu einem Gigabyte belegen.
## 0.3.1

### Erkannte Merkmale bearbeiten

- Erkannte Merkmale lassen sich verschieben, drehen, verdoppeln und entfernen: eine Bohrung, ein Zapfen oder eine Kuppel — die Kuppel ohne Drehen, weil sie keine Lage hat.
- In der Größe ändern lässt sich jetzt auch ein Zapfen oder eine Kuppel; bisher konnte das nur eine Bohrung.
- Die gemessenen Werte stehen dabei schon in den Feldern — der Umweg über Verschließen und Neubohren an abgeschriebenen Zahlen entfällt.
- Eine versetzte Bohrung bleibt dieselbe Bohrung: Jede Passung, die auf sie zeigt, behält ihren Bezug.
- Wo eine Handlung für ein Merkmal keinen Sinn hat, steht sie weiter da und sagt in einem Satz, warum — statt still zu fehlen.
- Ein eigenes Fenster *Merkmal* geht rechts auf, sobald das erste Merkmal angeklickt ist, und zeigt, was dort gemessen wurde; es lässt sich abziehen, zumachen und zurückholen.
- Jede Zahl darin ist änderbar: Ort, Durchmesser, Tiefe und Achse werden im Feld gesetzt, ohne Dialog dazwischen.
- Eine geänderte Zahl zeigt sich als Vorschau im Bild, bevor sie gilt.
- Ein Haken *Auf alle gleichartigen anwenden* ändert eine ganze Lochreihe in einem Zug, mit einem einzigen Schritt zum Zurücknehmen.
- Zwei markierte Merkmale nennen ihren Abstand von Mitte zu Mitte und je Achse.
- Eine Bohrung nennt ihre Normgröße — „misst 5,19 mm, das Durchgangsloch für M5“ — und sagt auch, wenn keine passt.
- Eine zweite Bohrung wie die erste entsteht durch Verdoppeln, statt Maße von Hand nachzutippen.
- Die Entf-Taste entfernt das gewählte Merkmal und nicht mehr den ganzen Körper.
- Ein Doppelklick auf eine Zeile der Objektliste öffnet, was sie ändert — bei einem erkannten Merkmal den passenden Dialog, bei einem selbst erzeugten den Schritt mit seinen Maßen.
- Eine durchgehende Bohrung, die nach dem Versetzen nicht mehr durchgeht, sagt es — und eine Senkung, die ihre Bohrung zuziehen würde, lässt sich nicht versetzen.
- Wer eine Bohrung so weit verkleinert, dass sie keine mehr ist, bekommt eine Erklärung statt der Aufforderung, einen Fehlerbericht zu schreiben.
- An einer Fläche führt ein Knopf in den Bausteinkatalog, statt Zeilen zu zeigen, die nur sagen, was dort nicht geht.
### Bewegen, Drehen und Auswählen

- Der Bewegungsgriff sitzt an dem, was gewählt ist — bei einer Bohrung an ihrer Öffnung statt in der Mitte des Teils.
- Bewegt wird, was ausgewählt ist: Mit markierter Bohrung versetzen Griff und Leiste die Bohrung, nicht mehr das ganze Teil.
- Beim Ziehen zeigt eine durchsichtige Vorschau, wohin die Bohrung wandert, und ein blasses Abbild, wo sie herkommt.
- Der Schatten läuft beim Verschieben mit und zeigt damit die Höhe über der Platte.
- Beim Drehen zeigt ein Bogen, wie weit gedreht wurde, und dass der Winkel auf einem Vielfachen von 45 Grad einrastet.
- Kleine Drehungen kommen an — bisher verschluckte ein unsichtbarer Winkelfang jeden Zug unterhalb der Rastweite.
- Die Bewegen-Leiste bietet an einer Fläche nur an, was dort möglich ist, und nennt den Grund am Knopf statt in einer Meldung nach dem Klick.
- Der Knopf *Anwenden* ist weg: Angewandt wird mit der Eingabetaste im Feld oder durch Ziehen am Griff — und zwar genau einmal, nicht doppelt.
- Ein verschobenes Teil springt nach dem Loslassen nicht mehr kurz an die alte Stelle zurück.
- Ein Rechtsklick in der Objektliste trifft die Zeile, auf die man zeigt, und nicht die zwei darüber.
### Ansicht und Objektbaum

- Die Ansicht hat eine eigene Steuerung, und sie ist die neue Vorgabe: Links ziehen verschiebt, rechts dreht, das gedrückte Mausrad kippt, das Rad zoomt.
- Mit W, A, S und D fliegt man durch die Szene, Q und E kippen — der Flug geht durch ein Teil hindurch, während der Zoom davor stehen bleibt.
- Wer eine andere Steuerung gewohnt ist, wählt sie in den Einstellungen: Die Schemata für Cura, für Bambu Studio, Orca und PrusaSlicer, für das CAD und für Blender bleiben.
- Der Eintrag *Einpassen* rahmt das angeklickte Teil formatfüllend; ohne Auswahl wie bisher die ganze Szene.
- Ein Teil unter der Druckplatte ist zu sehen — durchsichtig ist jetzt das Bett und nicht das Modell.
- Halbdurchsichtige Körper werden in der richtigen Tiefenfolge gezeichnet, unabhängig von der Reihenfolge ihrer Entstehung.
- Die eingestellte Ansicht bleibt erhalten, statt beim nächsten Schritt zurückzufallen.
- Auswahl und Umschalten im 3D-Fenster laufen mit weichen Übergängen statt harter Sprünge.
- Ab vier gleichnamigen Merkmalen steht im Objektbaum eine aufklappbare Sammelzeile mit ihrer Anzahl, statt hunderter Einzelzeilen.
- Angezeigt wird nur, was ein Drucker herstellen kann: Merkmale unter einem halben Millimeter fallen weg — an einem Schlauchhalter 296 von 1130.
- Verrundungen mit Radius null verschwinden damit aus dem Objektbaum.
- Ein Klick auf einen Körper kostet keine Wartezeit mehr; an einer Baugruppe von 63 MB waren es drei Viertel einer Sekunde.
- Umschalten der Darstellung und Bildaufbau großer Modelle brauchen ein Drittel der früheren Zeit.
### Zeichnen und genaue Eingabe

- Länge und Breite einer gewählten Zeichnung sind bedienbar; die Zeichnung folgt der geänderten Zahl samt ihren Maßen.
- Ein falsch gesetztes Maß lässt sich einzeln zurücknehmen, statt nur zusammen mit allen anderen.
- Wer eine Skizze hochgezogen hat, findet im Dialog auch den Weg zum Abziehen wieder.
- Ein getipptes Maß gilt, wie es getippt wurde: Aus 0,1 wird nicht mehr 0,166667.
- Der Einheitendialog fragt nach Millimetern und zeigt eine Zahl statt „nan“.
- Das Feld der Fase heißt Breite, und die Meldung dazu spricht auch von der Breite statt vom Radius.
- Ein Klick in die Rinne eines Reglers setzt ihn an die angeklickte Stelle, nicht eine Seite weiter.
- Beim Messen fängt der Zielpunkt an den Kanten des Modells und nicht an Linien, die im Bild nicht vorkommen.
### Öffnen, Speichern und Austauschdateien

- Das erste Modell eines Projekts liegt mittig auf dem Druckbett, statt dort, wo seine Datei es ablegt; jedes weitere behält seine Lage.
- Eine kaputte Datei wird beim Öffnen abgelehnt, statt angenommen zu werden und beim Speichern im Projekt zu landen.
- Die Absage nennt den Grund — leer, abgeschnitten, keine STL, kein 3MF, ohne Dreiecke, mit unbrauchbaren Koordinaten — und bietet *Andere Datei wählen* an.
- Der abgebrochene Download einer Modelldatei wird als solcher erkannt.
- Dateien über acht Megabyte werden mit Ladeanzeige und Fortschritt gelesen, statt das Fenster vierzehn Sekunden ohne Rückmeldung stehen zu lassen.
- Ein Dateiname kommt so auf der Platte an, wie er eingegeben wurde — mit Leerzeichen, Umlauten, Klammern und Plus.
- Ein Modell lässt sich als 3MF ohne Solidons Druckwerte speichern, wenn es im Slicer unverändert ankommen soll.
- Wo STEP an einem Netz nicht möglich ist, bietet die Absage *Als 3MF speichern* gleich an.
- Ein zu fein vernetztes Modell bekommt *Dreiecke verringern* als Knopf am Befund, nicht nur als Rat im Text.
- Ein Befund, der mehrere Körper betrifft, lässt sich für alle auf einmal beheben — mit Auswahl, welche, und einem Strg+Z für die ganze Handlung.
- Der Befehl *Auto Split* sagt, wenn ein Schnitt eine offene Fläche hinterlässt, und ein Schnitt durch einen bearbeitbaren Körper lässt die Bühne nicht mehr leer.
- Wer ein Teil unter die Maschinengrenze skaliert, bekommt einen Befund; bisher gab es den nur für zu groß.
- Eigene Bausteine tragen denselben Warnhinweis wie die mitgelieferten.
### Drucken, Slicer und Filament

- Der Druckdialog zeigt die Profile, die zum eingestellten Drucker passen, statt eines Bestands von 1001 Einträgen.
- Bei einem Elegoo Centauri Carbon sind es vier, und das richtige ist vorausgewählt.
- Ein Wechsel des Druckers im Projekt zieht Bauraum, Düse und Startcode mit — ein Prusa-Projekt bekommt nicht mehr die Maschine des Elegoo.
- Der Slicer bekommt die Maschinenangabe mit und liefert eine Druckdatei zurück, statt den Lauf mit „nicht zum Drucker passend“ abzubrechen.
- Steht der Slicer auf einem anderen Drucker als das Projekt, sagt Solidon es, statt es stillschweigend hinzunehmen.
- Der Hinweis auf ein fehlendes Profil nennt den Drucker, um den es geht.
- Die Filamentliste bleibt leer, solange kein Maschinenprofil gewählt ist, und nennt diesen Grund, statt 5962 Rollen anzubieten.
- Die Filamentauswahl lässt sich nach Hersteller, Material und den Werten eines Profils filtern.
- Wo Solidon einen Rand setzt, steht dabei, welches Teil ihn braucht und warum.
- Was die Maschine nicht kann, wird an allen betroffenen Feldern gesagt und nicht nur an einem.
- Empfehlungen aus dem Prüfbericht, die der Slicer nicht annimmt, versprechen keine Wirkung mehr.
- Objekte aus verschiedenen Materialien landen auf getrennten Druckplatten — die TPU-Dichtung nicht mehr auf der Platte des PETG-Gehäuses.
- Der Druckhinweis gibt einen Rat, statt auf Nummern des Lizenzvertrags zu verweisen.
### Meldungen, Knöpfe und Auskunft

- Gesperrte Knöpfe nennen jetzt am Knopf, was ihnen fehlt — mit der Maus, über die Tastatur und für einen Bildschirmleser.
- Betroffen sind unter anderem *Slicen* und *Im Slicer öffnen* ohne eingerichteten Slicer, *Einfügen* im Bausteinkatalog und *Erzeugen* im Modell-Dialog.
- Absagen enden nicht mit dem Satz allein, sondern mit dem Weg heraus.
- Ein unerwarteter Fehler wird in der eingestellten Sprache erklärt, statt einen englischen Innentext vorzulesen.
- Der Über-Dialog nennt, wer hinter Solidon steht und wer auf eine Rückmeldung antwortet.
- Ein Link auf eine ältere Fassung führt auf die aktuelle statt auf eine Fehlerseite.
- Die Windows-Installation läuft auch auf Rechnern durch, auf denen sie bisher mit „fehlerhaftes File“ abbrach; die Setup-Datei ist dafür 23 Megabyte größer.
### Chat und Modellunterstützung

- Ist ein Verweis auf ein Merkmal mehrdeutig, hält der Chat an, hebt die Kandidaten im Bild hervor und fragt nach — mit dem Körper, an dem jeder hängt.
- Ordnet der Chat Objekte auf Druckplatten an, ist das Ergebnis danach im Bild zu sehen.
- Ein Befund über eine Baugruppe zeigt auf den Körper, um den es geht, und trägt seine Handlung; wo keine steht, ist er ein reiner Hinweis.
- Der Chat kennt die neuen Handlungen an erkannten Merkmalen und führt sie auf Zuruf aus.
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
- Unter Linux mit einer Wayland-Sitzung startet Solidon und zeigt die 3D-Ansicht; fehlt dem System eine Bibliothek dafür, startet die Anwendung trotzdem und sagt, welche fehlt.

- Gleichartige Prüfbefunde werden gebündelt, ohne den Bezug zu den betroffenen Körpern und Stellen zu verlieren.
- Zahlen und Messwerte im Prüfbericht besitzen vollständige Bezeichnungen statt unverständlicher Einzelwerte.
- Scheitert eine Reparatur, wird der unveränderte Ausgangskörper vollständig wiederhergestellt.
- Ein geschlossenes importiertes Netz wird nicht mehr durch das vorschnelle Entfernen eines problematischen Dreiecks aufgerissen.
- Aktionsknöpfe aus dem Prüfbericht halten ein bereits geschlossenes Fenster nicht mehr unbemerkt im Speicher.
- Mitgelieferte Bausteine und die Freischaltung werden beim Start ohne gegenseitiges Blockieren geladen.
- Die 3D-Ansicht wird vor dem Fenster sauber beendet; dadurch schließen Windows-, Linux- und macOS-Fenster zuverlässiger.
- Die Titelleiste folgt unter Windows 11 dem Farbschema der Anwendung; andere Plattformen bleiben unverändert.
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
