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

**Die Werkzeugzeile der Skizze bekommt einen Überlaufknopf.** Achtzehn Knöpfe
in einer Zeile sind auf einem 1366er Laptop nicht bedienbar, und die
Hausgrenze steht schon: `test_interface_limits.py` erlaubt acht Werkzeuge. Die
acht häufigsten bleiben, der Rest wandert darunter — welche acht, wird an
Fusion abgelesen und nicht geraten.

**Die Menütiefe entscheidet ein Zeilenbudget, nicht die Zahl der Kategorien.**
`MENU_GROUPS` schaut heute auf die Kategorien; die Hausgrenze ist aber eine
Zeilengrenze (zwölf je Menü). Passen die Zeilen aller Kategorien einer Gruppe
hinein, stehen sie flach mit Trennstrichen. *Erzeugen* wird damit flach — der
Quader kostet zwei Klicks statt drei —, *Ändern* bleibt tief. Die
Neun-Menü-Grenze bleibt unberührt, es ist also kein Tausch.

**„Andere Objekte wählen" nimmt die vorhandene Auswahl sofort — und wartet
sichtbar, wenn keine da ist.** Der Grund ist die Erwartung, nicht der Klick:
Wer die Handlung anklickt, erwartet, dass er *jetzt* wählen kann. Ein Modus,
der das tut, ist erwartungskonform; einer, der eine Statuszeile zeigt und
einen zweiten Klick auf dieselbe Handlung verlangt, ist es nicht. Regel 19
verbietet **unsichtbare** Zustände, nicht angezeigte — der Befund bleibt
hervorgehoben, Escape beendet folgenlos. *Rückfallbedingung:* Lässt sich die
Hervorhebung nicht von normalem Auswählen unterscheiden, gilt die einfache
Variante. Ein Modus, der aussieht wie kein Modus, ist schlechter als keiner.

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
