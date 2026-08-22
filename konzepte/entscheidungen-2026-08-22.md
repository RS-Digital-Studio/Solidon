# Entscheidungen vom 22./23.08.2026 — was entschieden wurde und von wem

Diese Datei begann als Liste von Fragen an Robert. Sie ist jetzt das Protokoll
der Antworten: Fünf hat er selbst getroffen, bevor er schlafen ging, die
übrigen 3d-druck-64 unter seiner Vollmacht — erst „mach alles, damit es immer
perfekt für Kunden ist", dann erweitert auf „Bedienung, Produktrichtung und
Bauplanänderungen, alles kannst du entscheiden".

**Wozu sie so dasteht:** Jede Entscheidung trägt ihren Grund, damit sie sich
umdrehen lässt, ohne den Code zu lesen. Wer eine für falsch hält, braucht nur
den Absatz und nicht die Datei darunter.

---

## Nachtrag vom 23.08.2026: drei von diesen Entscheidungen haben die Messung nicht überstanden

Und alle drei aus demselben Grund. Sie stützten sich auf eine Zahl aus der
Roadmap, die etwas anderes zählte, als sie zu zählen schien:

| Entscheidung | die Zahl, auf die sie sich stützte | was sie wirklich war |
|---|---|---|
| *Erzeugen* wird flach | „Grundformen hat vier Zeilen" | die Zeilen **einer** Kategorie; die Gruppe hat achtzehn |
| Überlaufknopf für die Skizzenzeile | „achtzehn Knöpfe" | 15 Knöpfe **und 3 Felder**; die Felder kosten das Doppelte |
| „die Hausgrenze steht schon" | `MAX_TOOLS = 8` | gilt der Werkzeugzeile unter dem Viewport, nicht dem Editor |

**Das Muster ist nicht Nachlässigkeit, sondern eine Eigenschaft von
Zusammenfassungen.** Eine Roadmap-Zeile ist geschrieben worden, um einen
Befund festzuhalten — nicht, um später als Rechengrundlage zu dienen. Wer sie
als solche benutzt, übernimmt eine Zahl mitsamt einer Bedeutung, die nie
geprüft wurde: „vier Zeilen" war richtig, „achtzehn Knöpfe" war richtig, und
beide Male stimmte der Bezug nicht.

**Die Regel, die daraus folgt, kostet Minuten und hat dreimal Stunden
gespart:** Eine Entscheidung, die auf einer Zahl steht, misst diese Zahl
zuerst nach — an dem, worüber sie eine Aussage macht. Nicht die Roadmap fragen,
sondern das gebaute Fenster, das Register, den Körper.

Der Beleg dafür, dass es funktioniert: Alle drei Rücknahmen kamen **vor** dem
Bauen, keine danach. Und zwei davon fand nicht der, der entschieden hatte.

---

## Von Robert selbst entschieden

| Frage | Entscheidung | Stand |
|---|---|---|
| Woher weiß ein Merkmal, welcher Schritt es erzeugt hat? | **Ein Feld an `Feature`** (`created_by`), nicht das ID-Präfix aus §21.2 — die ID ist ein Schlüssel und trägt schon eine Bedeutung | gebaut (3d-druck-3a) |
| Heißt die Exportdatei `Halterung.stl` oder `Bracket.stl`? | **Quellsprache, Name im Dialog sichtbar** — eine sichtbare Vorgabe, die stabil ist, schlägt eine unsichtbare, die wandert | gebaut (`c9833cc`) |
| Die 33 Referenzringe in `app/ui/` | **Alle umbauen** | gebaut; Abnahme ist der Freigabetest je Klasse, nicht die Liste |
| Zweites Fehlerfenster und „Andere Objekte wählen" | **Beides bauen** | gebaut (3d-druck-b8) |
| §35 eine Testart „Anschluss" geben | **„ja, mach rein"** — auf direkte Frage von 3d-druck-33 | gebaut (`452c4b5`), fünfmal angewandt |

---

## Unter Vollmacht entschieden (3d-druck-64)

### Bedienung

**„Zuletzt geöffnet" wird auf vier Zeilen gekürzt, die Kacheln bleiben.**
Gemessen kostet die Liste 172 px und frisst genau den Gewinn von `571422e`
auf, sobald jemand die Anwendung ein paarmal benutzt hat. Vier Zeilen decken
den häufigsten Klick. An den Kacheln wird nicht gerührt: 96 von 112 Pixeln
sind das Vorschaubild, und das ist die einzige Stelle, an der der
Startbildschirm etwas **zeigt** statt beschreibt.

**Die Werkzeugzeile der Skizze bekommt einen Überlaufknopf — zurückgenommen
am 23.08.2026.** Der Befund bleibt (1007 Bildpunkte Mindestbreite, auf einem
1366er Laptop nicht bedienbar); die Begründung trägt nicht, und die Lösung
greift am falschen Ende an. Nachgemessen am gebauten Editor mit Thema
(3d-druck-b8):

    Mindestbreite der Zeile        1007   (der Registerwert stimmt exakt)
    Posten darin                     18   15 Knöpfe + 3 Felder
    12 einfache Knöpfe à 37          444   45 %
    „Grundform" (Aufklappmenü)       153   15 %
    zwei Zahlenfelder à 163          326   33 %

**Vier Knöpfe unter einen Überlaufknopf zu legen spart 148 Bildpunkte** — die
zwei Zahlenfelder allein kosten mehr als das Doppelte. Und der Satz „die
Hausgrenze steht schon" ist falsch: `MAX_TOOLS = 8` gilt `window.tool_strip`,
der Werkzeugzeile **unter dem Viewport**. Für den Skizzeneditor gibt es diese
Grenze nicht; sie müsste erst gesetzt werden.

Der wirksamste Kandidat ist damit ein anderer als der entschiedene: das
Raster-Feld, eine Dauereinstellung, die man einmal setzt und die 163 Punkte in
einer Werkzeugzeile belegt. Die Rechnung dazu legt 3d-druck-b8 vor — an Fusion
abgelesen, nicht geraten.

**Die Menütiefe entscheidet ein Zeilenbudget, nicht die Zahl der Kategorien.**
`MENU_GROUPS` schaut heute auf die Kategorien; die Hausgrenze ist aber eine
Zeilengrenze (zwölf je Menü). Passen die Zeilen aller Kategorien einer Gruppe
hinein, stehen sie flach mit Trennstrichen. Die Neun-Menü-Grenze bleibt
unberührt, es ist also kein Tausch.

**Nachgemessen am 23.08.2026 — und der zweite Satz der Entscheidung fällt.**
Hier stand: *„Erzeugen wird damit flach — der Quader kostet zwei Klicks statt
drei."* Das trägt nicht:

    Objekt        scene                                     5 Zeilen  ->  flach
    Erzeugen      primitive 5, import 3, sketch 5, label 2  18        ->  bleibt tief
    Ändern        boolean 4, transform 9, shaping 5,
                  holes 3, surface 3, mesh 9, repair 1      40        ->  bleibt tief
    Bausteine     parts                                     20        ->  eigene Ebene
    Vorbereiten   prepare 6, colour 3                       10        ->  flach möglich

(Zeilen einschließlich der Trennstriche zwischen den Kategorien, ohne die
zusammengelegten Zwillinge aus `MENU_TWINS`.)

**Der Fehler in der ursprünglichen Entscheidung ist genau der, den sie beheben
wollte.** Sie stützte sich auf den Satz aus der Roadmap, „Grundformen hat vier
Zeilen" — und das ist die Zahl **einer** Kategorie, nicht der Gruppe. *Erzeugen*
hat vier Kategorien mit zusammen 15 Einträgen. Die Entscheidung hat also
Kategorien gezählt, wo sie Zeilen zählen wollte.

**Was bleibt, ist ein kleinerer, aber echter Gewinn:** *Vorbereiten* passt mit
zehn Zeilen ins Budget. Neun Operationen sparen damit einen Klick — darunter
das Ausrichten fürs Drucken und das Teilen, also Schritte am Ende fast jeder
Kette.

**Nicht gebaut, sondern gemessen und weitergegeben.** Der Menübau steht in
`app/ui/main_window.py:1577` und gehört 3d-druck-b8; eine Regel im Kern, die
niemand ruft, wäre der Nichtanschluss, den wir an einem Tag dreimal gefunden
haben. Ob ein Klick bei neun Operationen den Umbau wert ist, entscheidet, wer
die Oberfläche hält — mit diesen Zahlen statt mit einer Vermutung.

**„Andere Objekte wählen" nimmt die vorhandene Auswahl sofort — und wartet
sichtbar, wenn keine da ist.** Der Grund ist die Erwartung, nicht der Klick:
Wer die Handlung anklickt, erwartet, dass er *jetzt* wählen kann. Ein Modus,
der das tut, ist erwartungskonform; einer, der eine Statuszeile zeigt und
einen zweiten Klick auf dieselbe Handlung verlangt, ist es nicht. Regel 19
verbietet **unsichtbare** Zustände, nicht angezeigte — der Befund bleibt
hervorgehoben, Escape beendet folgenlos. *Rückfallbedingung:* Lässt sich die
Hervorhebung nicht von normalem Auswählen unterscheiden, gilt die einfache
Variante. Ein Modus, der aussieht wie kein Modus, ist schlechter als keiner.

**`drill_hole` bekommt einen exakten Zwilling — und das Kriterium dafür steht
mit ihm.** Wer einen exakten Quader anlegte und eine Bohrung setzte, hatte
danach ein Netz; damit fielen Fase, Verrundung, Formschräge, Fläche versetzen,
exaktes Aushöhlen, Tasche schneiden und der STEP-Export aus. Der Haken „Exakter
Körper" war eine Sackgasse nach **einem** Schritt, und der Ausweg lautete: jeden
Schritt darüber zurücknehmen, die exakte Operation setzen, den Rest neu bauen.

Eine Bohrung ist die häufigste Operation, die es gibt. Sie ist im B-Rep-Kern
zugleich die einfachste — ein Zylinderschnitt, gemessen auf neun Stellen genau
gegen die geschlossene Formel, wo ein Netz um ein knappes Promille danebenläge.
§25 legt für die Bohrungen keinen Kern fest, es ist also keine Bauplanänderung,
sondern eine Lücke, die er offenlässt.

**Das Kriterium ist die eigentliche Entscheidung**, denn der Punkt in der
Roadmap nennt richtig, dass „senken" und „verschließen" danach vor derselben
Frage stehen. Es lautet **nicht** „geht es im exakten Kern" — dann müsste der
ganze Katalog zweimal gebaut werden, und jede der beiden Fassungen wäre die
halb gepflegte. Es lautet:

> Ein Zwilling entsteht dort, wo der Zweig ohne ihn **endet** — nicht dort, wo
> er möglich wäre.

Nach diesem Maß ist die Bohrung der erste und vorerst einzige Fall: Sie steht
am Anfang fast jeder Kette. *Senken* und *verschließen* setzen eine Bohrung
voraus und stehen damit nie am Anfang; wer sie exakt braucht, hat den Zweig
bereits, und die Frage stellt sich erst, wenn jemand sie tatsächlich vermisst.
Ein Zwilling, den niemand vermisst, ist zwei Schemata, zwei Tests und zwei
Stellen zum Nachbessern.

**Ein Schema für beide, nicht zwei gleichlautende.** ``drill_brep_hole``
benutzt ``DrillParams`` — dasselbe Objekt, nicht eine Kopie. Daran hängt
``change_kernel``: Es reicht die Parameter eines gesetzten Schritts an den
anderen Kern weiter, und wortgleiche Schemata laufen beim nächsten Nachbessern
auseinander. Dasselbe kann das nicht. Der Test dazu prüft ``is``, nicht
Gleichheit.

**Und ein Fund am Rande, der mehr wert ist als er aussieht.** Die Operation
hieß zuerst „Exakt bohren", und `test_theme_and_palette` fiel darüber: Wer
„bohren" in die Befehlssuche tippt, bekam den exakten Zwilling **vor** der
gewöhnlichen Bohrung, weil sein Titel das Wort wörtlich trägt und der andere
nur über den Wortstamm gefunden wird. Der Reihenfolgefehler war die Folge, der
eigentliche Fehler war ein Stilbruch: Die anderen Zwillinge heißen „Exakt**en**
Quader anlegen" — erst die Sache, dann das Beiwort. Sie heißt jetzt „Exakte
Bohrung setzen". *Ein Test über die Bedienoberfläche hat damit eine
Benennungsregel durchgesetzt, die nirgends aufgeschrieben ist.*

### Werkzeuge und Verfahren

**`test_mesh_backend`: die dritte Zusicherung fällt.** Sie prüft die Länge des
Temp-Ordners **dieser Maschine** und sagt nichts über den Kunden; die zwei
davor prüfen den Programmtext und bleiben. Ein Test, der bei umgebogenem
`TEMP` rot wird, kostet jede Sitzung Zeit und schützt niemanden.

**`py-spy` ja — aber nicht in `constraints.txt`.** Installation in die
**Nutzer**-Umgebung. Ein Werkzeug, das man an einen *laufenden* Prozess hängt,
ist kein Bestandteil des Produkts; es gehört zu `git` und dem Debugger, nicht
zu den Abhängigkeiten. Die Lizenzprüfung bleibt unberührt, und der nächste
Klon installiert weiterhin genau das, was die CI hat. **Was hineingehört, ist
der Satz, wie man es ruft** — `py-spy dump --pid N --native`, samt dem Hinweis,
dass die Elternkette auf Windows reißen kann. Es hat den Hänger aufgeklärt, der
drei Torläufe gefressen hatte.

**Eigene Arbeitsbäume ja — aber nicht in dieser Nacht.** Die Machbarkeit ist
belegt (der Code kommt aus dem Worktree, der Interpreter aus der `.venv` des
Hauptbaums). Das stärkste Argument dafür ist kein Zeitargument: *Ein privater
Index schützt vor fremden Dateien, nicht vor einem fremden HEAD* — ein
Regel-Commit ist auf einem fremden Branch gelandet, ohne dass jemand etwas
falsch gemacht hätte. Der Preis sind eigene Branches und vier Merges statt
vier Commits auf `main`. **Ein Umstieg auf Branches, während vier Sitzungen
arbeiten und der Auftrag lautet „am Ende ist alles in `main`", ist genau der
Moment, in dem etwas nicht dort landet.** Vorbereiten ja, umstellen am Morgen.

**Trimesh bleibt vorerst im kritischen Pfad des Starts.** Gemessen: 722 der
790 ms von `load_operations()` sind `app.core.scene.ops`, davon 582 der Import
von trimesh — das Registerfüllen selbst kostet 11,8 ms. Der Umbau wäre eine
Änderung an der Startreihenfolge (die Menüs brauchen das Register, bevor das
Fenster steht), und eine halbe Sekunde von 12,9 s kaltem Start ist nicht die
Stelle, an der ein Kunde etwas merkt. **Der Startpfad gehört als Ganzes
angesehen, nicht an einem Posten optimiert** — dann mit einer Messung von
außen, wie sie beim Tor die Lücke zwischen 9 und 30 Minuten aufgedeckt hat.

---

## Was ausdrücklich **nicht** unter der Vollmacht entschieden wurde

**Die vierte Falle in `CLAUDE.md`** — der Text liegt fertig vor (3d-druck-33):
*Ein roter Lauf, dessen Datei nicht in `git status` steht, hat seine Ursache
außerhalb deiner Änderung; erst `git status` und der Zeitstempel des
Artefakts, dann der Code.* Er ist gut, er hat heute mehrere Sitzungen Zeit
gekostet, und er wartet trotzdem auf Robert.

**Der Grund ist eine Haltung, die zweimal an einem Tag getragen hat.**
3d-druck-64 hatte §35 unter der Vollmacht entschieden und auf Widerspruch
zurückgenommen; 3d-druck-33 hat stattdessen Robert direkt gefragt und in einem
Satz ein „ja, mach rein" bekommen. Ihre Begründung, warum sie es auch unter
der erweiterten Vollmacht so hält:

> Eine Vollmacht, die ich über dich zitiert bekomme, während er schläft, ist
> kein Ersatz für seine Antwort — nicht aus Misstrauen, sondern weil genau das
> die Konstruktion ist, die wir beide für falsch gehalten haben.

Das gilt weiter für `CLAUDE.md`, den Bauplan und `AGENTS.md`: Sie legen fest,
**wie hier gearbeitet wird**, und stehen damit über der Arbeit, nicht darin.
Eine Nacht kostet das, und keine Substanz.

---

## Was weiter Robert gehört

Nichts davon ist eine Entscheidung, die eine Sitzung treffen könnte — es fehlt
jeweils etwas, das man nicht beschließen kann:

- **CI-Dienst und Signaturzertifikat**, Apple-Notarisierung, DMARC-Eintrag,
  das Postfach `support@` — Zugänge und Verträge.
- **Zwei Agenten-Suite-Läufe gegen Sonnet 5** und **P16.10** — beide kosten
  Geld über Roberts Schlüssel.
- **Zwei Messschieberwerte** an einer 2020er und einer 3030er Aluschiene.
- **Ein fremder Rechner** zum Installieren.
